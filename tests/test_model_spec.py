# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
from dataclasses import replace
from functools import cache

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon, box

from kicad_rf_studio.core.geometry import build_geometry
from kicad_rf_studio.core.geometry.lid import snap_lid
from kicad_rf_studio.core.geometry.mask import smeared_epsilon
from kicad_rf_studio.core.geometry.region import band
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.mesh.gates import mesh_with_lint
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.ports import place
from kicad_rf_studio.core.model.readers import c_box
from kicad_rf_studio.core.model.spec import (K_MAX, excitation, grid_entry, kappa, model_spec, pulse, spec_hash,
                                             verify_spec, with_pml)
from test_cli_cost import SEG
from test_gates import mini, project_of
from test_geometry_sections import four_layer, plane
from test_model_csx import TINY
from test_model_ports import lpf_model
from test_readers import DUMPS, LINES

P915 = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "t_max_s": 40e-9}


def test_the_pulse_for_915_mhz():  # spec 5.8
    e = excitation(P915)
    assert (e["f1"], e["f2"], e["t_max"]) == pytest.approx((457.5e6, 3.0195e9, 40e-9))
    assert e["t0"] == pytest.approx(9 / (2 * math.pi * 1.281e9), rel=1e-12)  # 1.1182 ns
    fm, fw, t0 = 1.7385e9, 1.281e9, e["t0"]
    form = lambda t: (math.sin(2 * math.pi * fm * (t - t0)) * math.exp(-(2 * math.pi * fw * t / 3 - 3) ** 2)
                      * (t < 2 * t0))
    for t in (0.3e-9, 1.1e-9, 2.0e-9, 2.3e-9):  # the last one is past the gate (t < 2 t0)
        got = eval(e["expr"].replace("^", "**"), {"sin": math.sin, "exp": math.exp, "pi": math.pi, "t": t})
        assert got == pytest.approx(form(t), abs=1e-9)


def test_the_pulse_is_spec_5_8s_over_any_band_and_excitation_is_it_over_the_projects():  # design 5.4
    p = pulse(1.85e9, 3.0e9, 30e-9)
    assert (p["f1"], p["f2"], p["t_max"]) == (1.85e9, 3.0e9, 30e-9)
    assert p["t0"] == pytest.approx(9 / (2 * math.pi * 0.575e9)) and p["expr"].startswith("sin(2*pi*2425000000*(t-")
    project = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "t_max_s": 40e-9}
    assert excitation(project) == pulse(*band(project), 40e-9)


def test_with_pml_adds_8_lines_past_each_end_at_its_outer_cell():  # design 5.2
    assert with_pml([0.0, 1.0, 3.0]) == [-8.0, -7.0, -6.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 3.0,
                                         5.0, 7.0, 9.0, 11.0, 13.0, 15.0, 17.0, 19.0]
    assert with_pml([0.1, 0.4, 0.5])[:2] == [-2.3, -2.0]  # quantised to 1e-6 mm


def test_kappa_is_set_at_f0():  # spec 5.3
    assert kappa(4.5, 0.02, 915e6) == pytest.approx(4.58134e-3, rel=1e-5) and kappa(3.3, None, 915e6) == 0.0


@cache
def lpf_spec():
    board, p, g, e, m = lpf_model()  # tests/test_model_ports.py
    return g, m, model_spec(p, board, g, m, [place(x, m, g.zs, g.pieces) for x in e], [])


def test_the_lpf915_spec():
    g, m, s = lpf_spec()
    assert json.loads(json.dumps(s)) == s
    assert s["mesh"]["z"] == m.z.tolist() and s["mesh"]["z"][-1] == pytest.approx(26.001447)  # X-6: over the 2.5 mm lid
    assert all(c["z"] in ([0.745, 0.78], [0.0, 0.035]) for c in s["metal"]["copper"])  # C-5: every piece solid
    assert len(s["metal"]["copper"]) == len(g.pieces) + 1  # + R1, a 0R rectangle; R2 is DNP
    names = [x["name"] for x in s["materials"]]
    assert names == ["substrate_0", "mask_F_fill", "mask_F_coat", "mask_B_fill", "mask_B_coat"]
    assert [x["priority"] for x in s["materials"]] == [10, 11, 12, 13, 14]
    sub, _, fcoat, _, bcoat = s["materials"]
    assert (sub["eps"], sub["kappa"], sub["solids"][0]["z"]) == (4.5, pytest.approx(4.58134e-3, rel=1e-5),
                                                                 [0.035, 0.745])
    assert fcoat["solids"][0]["z"] == [0.78, round(0.78 + m.dz0, 6)] and bcoat["solids"][0]["z"] == [round(-m.dz0, 6), 0.0]
    assert fcoat["eps"] == pytest.approx(smeared_epsilon(0.01, 3.3, m.dz0)) and fcoat["kappa"] == 0.0
    assert not any(q["z"] in ([0.78, 0.79], [-0.01, 0.0]) for x in s["materials"] for q in x["solids"])  # X-3
    area = sum(Polygon(zip(q["x"], q["y"])).area for q in fcoat["solids"])
    assert area == pytest.approx(g.masks["F.Cu"].coat.area, abs=1e-3)  # C-6: the 47 openings honoured
    assert len(s["metal"]["cylinders"]) == 26 and len(s["metal"]["curves"]) == 10  # C-40
    assert all(c["at"][0] in m.x and c["at"][1] in m.y for c in s["metal"]["curves"])
    assert s["metal"]["lid"]["plate"]["z"] == snap_lid(g.lid, m.z).z1 and s["metal"]["lid"]["plate"]["z"] in m.z  # C-39


def test_a_0r_rectangle_joins_its_two_nets_and_meets_no_other():  # final review I1
    # R1's hull of its two pads overlapped the GND pour that reaches into the gap between them, so the setup gate read
    # P2 and C3 as shorts (E_PORT_SHORT) and lpf915 could not run
    g, _, s = lpf_spec()
    (r1,) = (Polygon(zip(q["x"], q["y"])) for q in s["metal"]["copper"][len(g.pieces):])  # after the pieces
    assert {pc.net for pc in g.pieces if pc.layer == "F.Cu" and pc.polygon.intersects(r1)} == {"RF_C", "RF_OUT"}


def test_lid_walls_drawn_as_one_closed_ring_are_split():  # X-4
    board, p, g, _, m = lpf_model()
    frame = box(100, -105, 110, -95).difference(box(101, -104, 109, -96))
    s = model_spec(p, board, replace(g, lid=replace(g.lid, walls=MultiPolygon([frame]))), m, [], [])
    walls = [Polygon(zip(w["x"], w["y"])) for w in s["metal"]["lid"]["walls"]]
    assert sum(w.area for w in walls) == pytest.approx(frame.area, abs=1e-6)
    assert not any(w.contains(Point(105, -100)) for w in walls)  # never the frame's .exterior


def test_a_material_with_no_solids_is_left_out():  # openEMS warns on a property with no primitive
    board, p = project_of("coupon_gcpw_pads", "TP1.1", "TP2.1")
    g = build_geometry(board, p)
    s = model_spec(p, board, g, mesh_with_lint(g, g.protected, 2), [], [])
    assert [x["name"] for x in s["materials"]] == ["substrate_0", "mask_B_fill", "mask_B_coat"]  # F mask open everywhere


def test_inner_copper_slabs_are_filled_at_the_mean_of_their_neighbours(mini_board_file):  # C-8, X-1
    top = '(thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.01)'
    board = load_board(four_layer(mini_board_file, SEG.format(5, 10, 35, 10, 0.3, "F.Cu", "SIG", "s")
                                  + plane("In1.Cu"), top=top))
    p = {**mini(), "f0_hz": 915e6, "t_max_s": 40e-9, "stackup": board.stackup.to_json(), "others": []}
    g = build_geometry(board, p)
    s = model_spec(p, board, g, mesh_with_lint(g, g.protected, 2), [], [])
    in1 = next(x for x in g.zs if x.copper == "In1.Cu")
    fill = next(x for x in s["materials"] if x["solids"][0]["z"] == [in1.z0, in1.z1])
    assert fill["eps"] == pytest.approx(4.4)
    assert fill["kappa"] == pytest.approx((kappa(4.5, 0.01, 915e6) + kappa(4.3, 0.02, 915e6)) / 2)
    assert fill["priority"] < 1000  # the metal (Task 9) wins where the copper lies


def test_the_hash_covers_the_model_but_not_the_port_values():  # C-19, spec 7.8
    g, m, s = lpf_spec()
    assert len(spec_hash(s)) == 64 and spec_hash(s) == spec_hash(json.loads(json.dumps(s)))
    grid = grid_entry(s["ports"][2], {"ref": "C4", "value": "0.4pF"})
    assert (grid["R"], grid["C"]) == (None, pytest.approx(0.4e-12))
    assert spec_hash({**s, "grid": [grid]}) != spec_hash({**s, "grid": [{**grid, "C": 0.5e-12}]})
    assert spec_hash({**s, "excitation": {**s["excitation"], "t_max": 20e-9}}) != spec_hash(s)
    assert '"value"' not in json.dumps(s)  # a retune keeps the results


@pytest.mark.parametrize(("ref", "value", "code"), [
    ("C4", "??", "E_PART_VALUE"), ("L9", "10nH", "E_GRID_KIND"), ("D1", "1N4148", "E_GRID_KIND")])
def test_a_grid_part_must_be_a_c_or_r_with_a_readable_value(ref, value, code):  # Review Focus 3
    with pytest.raises(KrsError) as e:
        grid_entry(lpf_spec()[2]["ports"][2], {"ref": ref, "value": value})
    assert (e.value.code, e.value.params["ref"]) == (code, ref)


DT = 1.73972e-13  # the dumps model's dt
VPORTS = [  # on the dumps model's lines: P1 its own port; three part ports in the strip's copper slab, off the strip
    {"name": "P1", "kind": "lumped", "dir": "z", "start": [-5.0, -0.5, 0.0], "stop": [-5.0, 0.5, 0.5], "nodes": [],
     "part": False},
    {"name": "C1", "kind": "lumped", "dir": "y", "start": [2.0, 2.0, 0.5], "stop": [3.0, 1.0, 0.535], "nodes": [],
     "part": True},
    {"name": "L1", "kind": "lumped", "dir": "x", "start": [-1.0, 0.5, 0.5], "stop": [1.0, 1.5, 0.535], "nodes": [],
     "part": True},
    {"name": "R3", "kind": "lumped", "dir": "x", "start": [-3.0, 1.0, 0.5], "stop": [-2.0, 2.0, 0.535], "nodes": [],
     "part": True}]
VSPEC = {**TINY, "mesh": {a: LINES[k].tolist() for k, a in enumerate("xyz")}, "ports": VPORTS, "grid": []}
VPARTS = {"C1": {"ref": "C1", "value": "100pF"}, "L1": {"ref": "L1", "value": "15nH"}, "R3": {"ref": "R3", "value": "50R"}}
STRIPS = [{"x": [-1.0, 0.0, 0.0, -1.0], "y": [1.0, 1.0, 1.25, 1.25], "z": [0.5, 0.535]},
          {"x": [0.25, 1.0, 1.0, 0.25], "y": [1.0, 1.0, 1.25, 1.25], "z": [0.5, 0.535]}]
FILLS = [{"x": [2.0, 3.0, 3.0, 2.0], "y": [1.0, 1.0, 1.5, 1.5], "z": [0.5, 0.535]},  # C1's, across its box's width
         {"x": [2.0, 3.0, 3.0, 2.0], "y": [1.75, 1.75, 2.0, 2.0], "z": [0.5, 0.535]},
         {"x": [-3.0, -2.5, -2.5, -3.0], "y": [1.0, 1.0, 2.0, 2.0], "z": [0.5, 0.535]},  # R3's
         {"x": [-2.25, -2.0, -2.0, -2.25], "y": [1.0, 1.0, 2.0, 2.0], "z": [0.5, 0.535]}]


def test_verify_moves_every_part_port_into_the_grid():  # spec 7.6, C-36, D-45
    dump = DUMPS / "operator_dump.vtr"
    v = verify_spec(VSPEC, VPARTS, dump, DT)
    c1, l1, r3 = v["grid"]
    cell = c_box(dump, LINES, [0.0, 1.0, 0.5], [0.25, 1.25, 0.535], 0, DT)
    c1_cell = c_box(dump, LINES, [2.0, 1.5, 0.5], [3.0, 1.75, 0.535], 1, DT)
    assert [q["name"] for q in v["ports"]] == ["P1"] and VSPEC["grid"] == [] and len(VSPEC["ports"]) == 4
    # a C and an R: one cell along the box's axis at its middle, across its whole width (D-45)
    assert (c1["start"], c1["stop"], c1["R"]) == ([2.0, 1.5, 0.5], [3.0, 1.75, 0.535], None)
    # abs=0: approx's default floor of 1e-12 would pass any femtofarad value
    assert c1["C"] == pytest.approx(100e-12 + c1_cell, rel=1e-12, abs=0)
    assert c1_cell == pytest.approx(1.4886e-14, rel=1e-3, abs=0)
    assert (r3["start"], r3["stop"], r3["R"], r3["C"]) == ([-2.5, 1.0, 0.5], [-2.25, 2.0, 0.535], 50.0, None)
    assert "L" not in c1 and "L" not in r3
    assert (l1["dir"], l1["start"], l1["stop"], l1["R"], l1["L"]) == ("x", [0.0, 1.0, 0.5], [0.25, 1.25, 0.535], None,
                                                                      15e-9)
    assert l1["C"] == pytest.approx(cell, rel=1e-12, abs=0) and cell == pytest.approx(5.954e-15, rel=1e-3, abs=0)
    assert v["metal"]["copper"][-6:] == FILLS[:2] + STRIPS + FILLS[2:]
    turned = {**VSPEC, "ports": [*VPORTS[:2], {**VPORTS[2], "start": [1.0, 0.5, 0.5], "stop": [-1.0, 1.5, 0.535]},
                                 VPORTS[3]]}  # the box starts at its higher end, as lpf915's L1 does
    t = verify_spec(turned, VPARTS, dump, DT)
    assert (t["grid"][1]["start"], t["grid"][1]["stop"], t["metal"]["copper"][-4:-2]) == (
        [0.0, 1.0, 0.5], [0.25, 1.25, 0.535], STRIPS)


def test_verify_refuses_what_it_cannot_put_in_the_grid(tmp_path):  # C-36, C-37 (owner-confirmed: K_MAX 0.45)
    dump = DUMPS / "operator_dump.vtr"
    cases = [((VSPEC, {**VPARTS, "L1": {"ref": "L1", "value": "1pH"}}, dump),
              ("E_VERIFY_K", {"ref": "L1", "k": "1.13", "limit": "0.45"})),
             ((VSPEC, {**VPARTS, "R3": {"ref": "R3", "value": "x"}}, dump),
              ("E_VERIFY_VALUE", {"ref": "R3", "value": "x"})),
             ((VSPEC, {**VPARTS, "C1": {"ref": "C1", "value": "0pF"}}, dump),
              ("E_VERIFY_VALUE", {"ref": "C1", "value": "0pF"})),
             ((VSPEC, VPARTS, tmp_path / "none.vtr"), ("E_VERIFY_DUMP", {"path": str(tmp_path / "none.vtr")}))]
    for args, expected in cases:
        with pytest.raises(KrsError) as e:
            verify_spec(*args, DT)
        assert (e.value.code, e.value.params) == expected
    assert K_MAX == 0.45
