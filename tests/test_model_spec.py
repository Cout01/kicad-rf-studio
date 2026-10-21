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
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.mesh.gates import mesh_with_lint
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.ports import place
from kicad_rf_studio.core.model.spec import excitation, grid_entry, kappa, model_spec, spec_hash
from test_cli_cost import SEG
from test_gates import mini, project_of
from test_geometry_sections import four_layer, plane
from test_model_ports import lpf_model

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


def test_kappa_is_set_at_f0():  # spec 5.3
    assert kappa(4.5, 0.02, 915e6) == pytest.approx(4.58134e-3, rel=1e-5) and kappa(3.3, None, 915e6) == 0.0


@cache
def lpf_spec():
    board, p, g, e, m = lpf_model()  # tests/test_model_ports.py
    return g, m, model_spec(p, board, g, m, [place(x, m, g.zs) for x in e], [])


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
    assert len(s["metal"]["cylinders"]) == 21 and len(s["metal"]["curves"]) == 15  # C-40
    assert all(c["at"][0] in m.x and c["at"][1] in m.y for c in s["metal"]["curves"])
    assert s["metal"]["lid"]["plate"]["z"] == snap_lid(g.lid, m.z).z1 and s["metal"]["lid"]["plate"]["z"] in m.z  # C-39


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
