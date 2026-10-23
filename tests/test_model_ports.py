# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from dataclasses import replace
from functools import cache

import numpy as np
import pytest
from shapely.geometry import Point, box

from kicad_rf_studio import runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.geometry import build_geometry
from kicad_rf_studio.core.geometry.zstack import Slab
from kicad_rf_studio.core.mesh import Mesh
from kicad_rf_studio.core.mesh.gates import mesh_with_lint
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.model.ports import End, ends, nominal_boxes, place
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_cost import FIX
from test_gates import project_of
from test_project import edit


@cache
def lpf_model():
    """lpf915 through `new` with a 2.5 mm lid: board, project, geometry, port ends, and the mesh with their boxes."""
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    return board, p, g, e, mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2)


def test_lpf915_ports_in_job_order():
    assert [(x.name, x.role) for x in lpf_model()[3]] == [
        ("P1", "external"), ("P2", "external"), ("C1", "port"), ("L1", "port"), ("C2", "port"), ("C3", "port")]


def test_port_boxes_sit_on_lines_inside_their_pads():  # spec 5.6, C-14
    board, p, g, e, m = lpf_model()
    p1, p2, c1, c2 = (place(x, m, g.zs) for x in (e[0], e[1], e[2], e[4]))
    assert (p1["dir"], p2["dir"], c1["dir"], c2["dir"]) == ("y", "y", "x", "y")
    assert -99.625 < p1["start"][1] < -99.375 and -100.125 < p1["stop"][1] < -99.875  # U1.2, then U1.1
    assert 101.05 < p1["start"][0] < p1["stop"][0] < 101.875
    assert 112.825 < p2["start"][0] < p2["stop"][0] < 112.925  # J1.1 and J1.2 overlap 0.1 mm in x
    assert 103.7 < c1["start"][0] < 104.26 and 102.74 < c1["stop"][0] < 103.3  # C1.2 (reference), then C1.1
    for q in (p1, p2, c1, c2):
        assert (q["start"][2], q["stop"][2]) == (0.745, 0.78)
        assert {q["start"][0], q["stop"][0]} <= set(m.x.tolist()) and {q["start"][1], q["stop"][1]} <= set(m.y.tolist())
    assert (p1["part"], c1["part"]) == (False, True)


def test_a_copper_rule_reference_takes_the_ground_under_the_point():  # S-3: the y flip of the stored point
    board, p = project_of("coupon_gcpw_pads", "TP1.1", "TP2.1")
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    q = place(e[0], mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2), g.zs)
    assert q["dir"] == "y" and q["start"][1] < -100.6505 < -100.5 < q["stop"][1] < -99.5
    assert 99.5 < q["start"][0] < q["stop"][0] < 100.5


def edited(name, start, end, where, value, *more):
    board, p = project_of(name, start, end, *more)
    p = copy.deepcopy(p)
    edit(p, where, value)  # tests/test_project.py
    return board, p


@pytest.mark.parametrize(("where", "value", "code", "params"), [
    (["ports", 0, "reference"], None, "E_NO_REFERENCE", {"signal": "TP1.1"}),
    (["ports", 0, "reference"], {"point": [100.0, 100.6505], "layer": "B.Cu"}, "E_REFERENCE_LAYER",
     {"name": "P1", "signal_layer": "F.Cu", "reference_layer": "B.Cu"}),
    (["ports", 0, "reference"], {"point": [100.0, 100.575], "layer": "F.Cu"}, "E_REFERENCE_POINT",  # in the gap
     {"name": "P1", "point": "(100.000, 100.575)", "layer": "F.Cu"}),
    (["ports"], [], "E_NO_PORTS", {})])
def test_refusals_on_the_coupon(where, value, code, params):
    board, p = edited("coupon_gcpw_pads", "TP1.1", "TP2.1", where, value)
    with pytest.raises(KrsError) as e:
        ends(board, p, build_geometry(board, p).pieces)
    assert (e.value.code, e.value.params) == (code, params)


def test_an_unknown_reference_pad_is_named():
    board, p = edited("lpf915", "U1.1", "J1.1", ["ports", 0, "reference"], {"pad": "U9.2", "uuid": ""})
    with pytest.raises(KrsError) as e:
        ends(board, p, build_geometry(board, p).pieces)
    assert (e.value.code, e.value.params["name"]) == ("E_UNKNOWN_PAD", "U9.2")


def test_a_reference_by_pad_name_alone():  # Review Focus 3
    board, p = edited("lpf915", "U1.1", "J1.1", ["ports", 0, "reference"], {"pad": "U1.2", "uuid": ""},
                      "--lid-height", "2.5")
    assert ends(board, p, build_geometry(board, p).pieces)[0].reference.equals(board.pads("U1.2")[0].polygon)


def test_pads_that_face_each_other_on_no_axis_are_refused():
    board, p, g, _, m = lpf_model()
    q = copy.deepcopy(p)
    q["ports"][0]["reference"] = {"pad": "C2.2", "uuid": board.pads("C2.2")[0].uuid}  # diagonal to U1.1
    with pytest.raises(KrsError) as e:
        place(ends(board, q, g.pieces)[0], m, g.zs)
    assert (e.value.code, e.value.params) == ("E_PORT_SPANS", {"name": "P1"})


def test_a_rotated_part_needs_the_switch():  # C-12, C-37
    board, p = project_of("lpf915-45", "U1.1", "J1.1", "--lid-height", "2.5")
    with pytest.raises(KrsError) as e:
        ends(board, p, build_geometry(board, p).pieces)
    assert (e.value.code, e.value.params) == ("E_ROTATED_PART", {"ref": "L1"})


def test_a_rotated_part_becomes_a_curve_port_behind_the_switch():  # C-37, spec 5.7
    board, p = project_of("lpf915-45", "U1.1", "J1.1", "--lid-height", "2.5")
    p = {**copy.deepcopy(p), "allow_curve_port": True}
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2)
    l1 = place(next(x for x in e if x.name == "L1"), m, g.zs)
    cx, cy = board.pads("L1.2")[0].center
    assert (l1["kind"], l1["start"][2], l1["stop"][2]) == ("curve", 0.78, 0.78)
    assert l1["start"][:2] == [min(m.x, key=lambda v: abs(v - cx)), min(m.y, key=lambda v: abs(v - cy))]
    assert l1["nodes"] == [l1["start"], l1["stop"]]


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize(("name", "start", "end"), [("coupon_gcpw_pads", "TP1.1", "TP2.1"), ("lpf915", "U1.1", "J1.1"),
                                                   ("lpf915-45", "U1.1", "J1.1")])
def test_every_node_of_every_port_lies_inside_its_copper(name, start, end, n):  # D-11, r3 B-3
    more = ("--lid-height", "2.5") if name.startswith("lpf") else ()
    board, p = project_of(name, start, end, *more)
    p = {**p, "allow_curve_port": True}
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), n)
    outside = []
    for x in e:
        q = place(x, m, g.zs)
        owners = [x.reference, x.signal] if q["kind"] == "curve" else [x.reference, x.signal, x.reference, x.signal]
        outside += [(x.name, k) for k, (node, cu) in enumerate(zip(q["nodes"], owners))
                    if not cu.contains(Point(node[:2]))]
    assert outside == []


def test_lpf915s_p2_moves_to_the_width_line_where_both_pads_have_copper():  # D-11: n = 2 places it
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2)
    p2 = place(next(x for x in e if x.name == "P2"), m, g.zs)
    assert [node[0] for node in p2["nodes"]] == pytest.approx([112.9024] * 4, abs=1e-4)


def test_a_round_pad_with_no_line_inside_its_copper_is_a_coded_refusal():  # D-11: never E_INTERNAL
    mesh = Mesh(np.array([-0.295, 0.295, 0.6, 0.9]), np.array([-0.2, 0.0, 0.2]), np.array([0.745, 0.78]), 0.1, 0.03,
                {}, {})
    end = End("P9", Point(0, 0).buffer(0.3), box(0.5, -0.05, 1.0, 0.05), "F.Cu", "external")
    with pytest.raises(KrsError) as e:
        place(end, mesh, (Slab("copper", 0.745, 0.78, None, None, "F.Cu"),))
    assert (e.value.code, e.value.params) == ("E_PORT_BOX", {"name": "P9"})


@pytest.mark.openems
def test_lpf915_at_n3_passes_the_port_gates(tmp_path, capsys, monkeypatch):  # D-11; about 1–2 min
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    runs.save_settings({"machines": {runs.machine_key(): {"threads": 4, "pool": 1, "aggregate_mcs": 200.0}}})
    pj = tmp_path / "lpf915" / "project.json"
    assert main(["new", str(FIX / "lpf915.kicad_pcb"), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz",
                 "--lid-height", "2.5", "-o", str(pj.parent)]) == 0
    d = load_project(pj)
    d["mesh"]["n"], d["gates"]["fit2d_limit"] = 3, 0.05  # E_FIT2D_FINE's own advice: RF_B reads +4.39 %
    save_project(pj, d)
    capsys.readouterr()
    assert main(["cost", str(pj)]) == 0
    assert render("E_PORT_OPEN", name="P2", end="signal") not in capsys.readouterr().out
