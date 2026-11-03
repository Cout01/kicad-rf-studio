# SPDX-License-Identifier: GPL-3.0-or-later
import copy
from dataclasses import replace
from functools import cache

import numpy as np
import pytest
import shapely
from shapely.geometry import Point, box

from kicad_rf_studio import runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.geometry import build_geometry
from kicad_rf_studio.core.geometry.copper import Piece, copper_pieces, split_holes
from kicad_rf_studio.core.geometry.zstack import Slab, zstack
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.mesh import Mesh
from kicad_rf_studio.core.mesh.gates import mesh_with_lint
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.model.ports import (End, clear_between, ends, nominal_boxes, place, plane_under,
                                              si_reference)
from kicad_rf_studio.core.project import load_project, save_project
from kicad_rf_studio.pipeline import build_model
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


def test_port_boxes_span_the_copper_free_gap_between_their_ends():  # spec 5.6, C-14, D-45
    board, p, g, e, m = lpf_model()
    ports = {q["name"]: q for q in build_model(p, board, g).spec["ports"]}
    p1, p2, c1, c2 = (ports[k] for k in ("P1", "P2", "C1", "C2"))
    assert (p1["dir"], p2["dir"], c1["dir"], c2["dir"]) == ("y", "y", "x", "y")
    # along: from the reference's last line in copper to the signal's first, all of F.Cu counted (the GND pour reaches
    # past U1.2, J1.2 and C2.2, C2.1's RF_B copper past its pad); across: C1 drops its two outer lines, whose edges out
    # end in the pour's fingers between its pads
    assert [[*q["start"][:2], *q["stop"][:2]] for q in (p1, p2, c1, c2)] == [
        pytest.approx([101.119184, -99.712411, 101.868219, -99.88905], abs=1e-6),  # U1.2's side, then U1.1's
        pytest.approx([112.82744, -99.33698, 112.902421, -99.623658], abs=1e-6),  # J1.2's side, then J1.1's
        pytest.approx([103.740804, -100.219158, 103.291384, -99.779563], abs=1e-6),  # C1.2's side, then C1.1's
        pytest.approx([104.714549, -100.479893, 105.238873, -100.290607], abs=1e-6)]  # C2.2's side, then C2.1's
    for q in (p1, p2, c1, c2):
        assert (q["start"][2], q["stop"][2]) == (0.745, 0.78)
        assert {q["start"][0], q["stop"][0]} <= set(m.x.tolist()) and {q["start"][1], q["stop"][1]} <= set(m.y.tolist())
    assert (p1["part"], c1["part"]) == (False, True)


def test_a_copper_rule_reference_takes_the_ground_under_the_point():  # S-3: the y flip of the stored point
    board, p = project_of("coupon_gcpw_pads", "TP1.1", "TP2.1")
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    q = place(e[0], mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2), g.zs, g.pieces)
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
        place(ends(board, q, g.pieces)[0], m, g.zs, g.pieces)
    assert (e.value.code, e.value.params) == ("E_PORT_SPANS", {"name": "P1"})


def test_a_rotated_part_needs_the_switch():  # C-12, C-37
    board, p = project_of("lpf915-45", "U1.1", "J1.1", "--lid-height", "2.5")
    with pytest.raises(KrsError) as e:
        ends(board, p, build_geometry(board, p).pieces)
    assert (e.value.code, e.value.params) == ("E_ROTATED_PART", {"ref": "L1"})


def test_the_rotated_part_message_states_p0bs_result():  # D-34's fail branch
    assert "P0-B measured" in render("E_ROTATED_PART", ref="L1")


def test_a_rotated_part_becomes_a_curve_port_behind_the_switch():  # C-37, spec 5.7
    board, p = project_of("lpf915-45", "U1.1", "J1.1", "--lid-height", "2.5")
    p = {**copy.deepcopy(p), "allow_curve_port": True}
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2)
    l1 = place(next(x for x in e if x.name == "L1"), m, g.zs, g.pieces)
    cx, cy = board.pads("L1.2")[0].center
    assert (l1["kind"], l1["start"][2], l1["stop"][2]) == ("curve", 0.78, 0.78)
    assert l1["start"][:2] == [min(m.x, key=lambda v: abs(v - cx)), min(m.y, key=lambda v: abs(v - cy))]
    assert l1["nodes"] == [l1["start"], l1["stop"]]


CASES = [("coupon_gcpw_pads", "TP1.1", "TP2.1", 2), ("coupon_gcpw_pads", "TP1.1", "TP2.1", 3),
         ("lpf915", "U1.1", "J1.1", 2), ("lpf915", "U1.1", "J1.1", 3), ("lpf915-45", "U1.1", "J1.1", 2)]


@pytest.mark.parametrize(("name", "start", "end", "n"), CASES)
def test_every_witness_lies_inside_its_copper_and_every_cap_on_its_box_end(name, start, end, n):  # D-11, r3 B-3, D-45
    more = ("--lid-height", "2.5") if name.startswith("lpf") else ()
    board, p = project_of(name, start, end, *more)
    p = {**p, "allow_curve_port": True}
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), n)
    wrong = []
    for x in e:
        q = place(x, m, g.zs, g.pieces)
        if q["kind"] == "curve":
            wrong += [(x.name, k) for k, (node, cu) in enumerate(zip(q["nodes"], [x.reference, x.signal]))
                      if not cu.contains(Point(node[:2]))]
            continue
        k = "xy".index(q["dir"])
        lo, hi = sorted((q["start"][1 - k], q["stop"][1 - k]))
        rc, sc, rw, sw = q["nodes"]  # a cap node may lie in air: the box's PEC end joins it to the copper (A-6)
        if not (rc[k] == q["start"][k] and sc[k] == q["stop"][k] and lo <= rc[1 - k] == sc[1 - k] == sw[1 - k] <= hi
                and rw[1 - k] == rc[1 - k]):
            wrong.append((x.name, "caps"))
        wrong += [(x.name, i) for i, node, cu in ((2, rw, x.reference), (3, sw, x.signal))
                  if not cu.contains(Point(node[:2]))]
    assert wrong == []


@pytest.mark.parametrize(("name", "start", "end", "n"), CASES)
def test_no_copper_shorts_a_cell_of_a_lumped_port_box(name, start, end, n):  # D-45
    # openEMS keeps PEC on every edge whose midpoint lies in metal but a lumped box's own edges along its axis
    # (operator.cpp:1051-1053, 1681-1741, 2030-2062): a node strictly between the caps that copper touches, at the node
    # (its z edge) or midway to the next line across on either side, shorts the cells beside it
    board, p = project_of(name, start, end, *(("--lid-height", "2.5") if name.startswith("lpf") else ()))
    p = copy.deepcopy({**p, "allow_curve_port": True})
    p["mesh"]["n"] = n
    g = build_geometry(board, p)
    spec = build_model(p, board, g).spec
    metal = shapely.union_all([pc.polygon for pc in g.pieces if pc.layer == "F.Cu"])  # every port here is on F.Cu
    shorted = []
    for q in spec["ports"]:
        if q["kind"] == "curve":
            continue
        k = "xy".index(q["dir"])
        along, across = (np.array(spec["mesh"][a]) for a in ("xy"[k], "xy"[1 - k]))
        (a, b), (lo, hi) = (sorted((q["start"][j], q["stop"][j])) for j in (k, 1 - k))
        rows = np.flatnonzero((across >= lo) & (across <= hi))
        out = across[max(rows[0] - 1, 0):rows[-1] + 2]  # the box's lines across and one beyond each side
        vs = [*across[rows], *(out[1:] + out[:-1]) / 2]
        if any(metal.covers(Point((u, v) if k == 0 else (v, u))) for u in along[(along > a) & (along < b)] for v in vs):
            shorted.append(q["name"])
    assert shorted == []


def test_lpf915_45s_p2_at_n3_is_refused_rather_than_left_open():  # D-45: the gap's ends would touch no copper
    board, p = project_of("lpf915-45", "U1.1", "J1.1", "--lid-height", "2.5")
    p = {**p, "allow_curve_port": True}
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 3)
    with pytest.raises(KrsError) as err:
        place(next(x for x in e if x.name == "P2"), m, g.zs, g.pieces)
    assert (err.value.code, err.value.params) == ("E_PORT_BOX", {"name": "P2"})


def test_lpf915s_p2_moves_to_the_width_line_where_both_pads_have_copper():  # D-11: n = 2 places it
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2)
    p2 = place(next(x for x in e if x.name == "P2"), m, g.zs, g.pieces)
    assert [node[0] for node in p2["nodes"]] == pytest.approx([112.9024] * 4, abs=1e-4)


def test_a_round_pad_with_no_line_inside_its_copper_is_a_coded_refusal():  # D-11: never E_INTERNAL
    mesh = Mesh(np.array([-0.295, 0.295, 0.6, 0.9]), np.array([-0.2, 0.0, 0.2]), np.array([0.745, 0.78]), 0.1, 0.03,
                {}, {})
    end = End("P9", Point(0, 0).buffer(0.3), box(0.5, -0.05, 1.0, 0.05), "F.Cu", "external")
    with pytest.raises(KrsError) as e:
        place(end, mesh, (Slab("copper", 0.745, 0.78, None, None, "F.Cu"),), [])
    assert (e.value.code, e.value.params) == ("E_PORT_BOX", {"name": "P9"})


def synthetic(extra):
    """place() of port P9 on F.Cu between a signal pad at x 0..0.3 and a reference pad at 0.6..0.9 (y -0.5..0.5), two
    mesh lines across inside both (y -0.1 and 0.1), and `extra`, more GND copper."""
    mesh = Mesh(np.array([0.1, 0.2, 0.35, 0.45, 0.55, 0.7, 0.8]), np.array([-0.6, -0.1, 0.1, 0.6]),
                np.array([0.745, 0.78]), 0.1, 0.03, {}, {})
    sig, ref = box(0.0, -0.5, 0.3, 0.5), box(0.6, -0.5, 0.9, 0.5)
    pieces = [Piece("F.Cu", net, q, True) for net, q in (("SIG", sig), ("GND", ref), ("GND", extra))]
    return place(End("P9", sig, ref, "F.Cu", "external"), mesh, (Slab("copper", 0.745, 0.78, None, None, "F.Cu"),),
                 pieces)


def test_a_finger_beside_the_gap_cuts_a_line_across_and_the_nodes_move_off_it():  # D-45
    # the finger holds the midpoint of line -0.1's edge outward at x 0.45, between the caps: -0.1 is cut, and the nodes,
    # which sat on it (a tie goes to the lower line), move to 0.1
    q = synthetic(box(0.41, -0.7, 0.49, -0.3))
    assert (q["dir"], q["start"], q["stop"]) == ("x", [0.7, 0.1, 0.745], [0.2, 0.1, 0.78])
    assert q["nodes"] == [[0.7, 0.1, 0.78], [0.2, 0.1, 0.78], [0.8, 0.1, 0.78], [0.1, 0.1, 0.78]]


@pytest.mark.parametrize("extra", [box(0.32, -0.7, 0.58, 0.7), box(0.41, -0.7, 0.49, -0.08)])
def test_copper_in_the_gap_that_no_box_clears_is_a_coded_refusal(extra):  # D-45
    # never E_INTERNAL, never a cap off its copper: the strip leaves no copper-free line between the pads; the finger
    # covers line -0.1's node at x 0.45, so the gap would end there and the signal's cap would touch only the finger
    with pytest.raises(KrsError) as e:
        synthetic(extra)
    assert (e.value.code, e.value.params) == ("E_PORT_BOX", {"name": "P9"})
    assert "copper-free mesh line between them" in render("E_PORT_BOX", name="P9")


FOUR = (Slab("copper", 0.0, 0.035, None, None, "B.Cu"), Slab("dielectric", 0.035, 0.235, 4.3, 0.02, None),
        Slab("copper", 0.235, 0.27, None, None, "In2.Cu"), Slab("dielectric", 0.27, 1.335, 4.5, 0.02, None),
        Slab("copper", 1.335, 1.37, None, None, "In1.Cu"), Slab("dielectric", 1.37, 1.57, 4.3, 0.02, None),
        Slab("copper", 1.57, 1.605, None, None, "F.Cu"))
GRID = np.round(np.arange(-10, 11) * 0.1, 6)  # lines every 0.1 mm
V_MESH = Mesh(GRID, GRID, np.array([0.0, 0.035, 0.235, 0.27, 1.335, 1.37, 1.57, 1.605]), 0.1, 0.03, {}, {})
PAD = box(-0.15, -0.3, 0.15, 0.3)  # 0.3 × 0.6 mm, longer along y


def plane(layer, net="GND", shape=box(-5, -5, 5, 5)):
    return Piece(layer, net, shape, True)


def cut(shape, layer="In1.Cu"):
    """A GND plane `shape` as the copper pipeline leaves it: pieces with no holes (split_holes)."""
    return [Piece(layer, "GND", g, True) for g in split_holes(shape)]


def test_a_vertical_port_runs_from_the_plane_under_a_pad_to_the_pad():  # Stage 4 design 5.5
    assert plane_under(PAD, "F.Cu", FOUR, [plane("In1.Cu")], {"GND"}) == "In1.Cu"
    q = place(End("P1", PAD, PAD, "F.Cu", "external", ref_layer="In1.Cu"), V_MESH, FOUR, [])
    assert q == {"name": "P1", "kind": "lumped", "dir": "z", "start": [0.0, -0.2, 1.37], "stop": [0.0, 0.2, 1.57],
                 "nodes": [[0.0, 0.0, 1.37], [0.0, 0.0, 1.57], [0.0, 0.0, 1.335], [0.0, 0.0, 1.605]], "part": False}
    assert plane_under(PAD, "B.Cu", FOUR, [plane("In2.Cu")], {"GND"}) == "In2.Cu"  # a bottom pad: the plane above
    q = place(End("P2", PAD, PAD, "B.Cu", "external", ref_layer="In2.Cu"), V_MESH, FOUR, [])
    assert (q["start"], q["stop"]) == ([0.0, -0.2, 0.235], [0.0, 0.2, 0.035])  # from the plane: u = V_pad − V_plane
    # the lumped port's order, plane cap, pad cap, then their far faces, which the PEC-roots gate reads
    assert q["nodes"] == [[0.0, 0.0, 0.235], [0.0, 0.0, 0.035], [0.0, 0.0, 0.27], [0.0, 0.0, 0.0]]
    disc = Point(0, 0).buffer(0.2)
    q = place(End("P3", disc, disc, "F.Cu", "external", ref_layer="In1.Cu"), V_MESH, FOUR, [])
    assert (q["start"], q["stop"]) == ([-0.1, 0.0, 1.37], [0.1, 0.0, 1.57])  # a round pad: across its centre


def test_the_plane_under_a_pad_is_the_nearest_one_nets_copper_that_covers_it():  # design 5.5; Review Focus 4
    halves = cut(box(-5, -5, 5, 5).difference(Point(0.05, 3.0).buffer(0.15)))  # an antipad 3 mm off, cut at x 0.05
    assert len(halves) == 2 and plane_under(PAD, "F.Cu", FOUR, halves, {"GND"}) == "In1.Cu"  # neither piece alone
    assert plane_under(PAD, "F.Cu", FOUR, [plane("In2.Cu")], {"GND"}) == "In2.Cu"  # past In1.Cu, bare under the pad
    away = plane("In1.Cu", "SIG", box(1, -1, 2, 1))  # In1.Cu's copper beside the pad, not over it
    assert plane_under(PAD, "F.Cu", FOUR, [away, plane("In2.Cu")], {"GND"}) == "In2.Cu"
    touch = plane("In1.Cu", "SIG", box(0.15, -1, 1, 1))  # on the pad's right edge (x 0.15), with no overlap: beside it
    assert plane_under(PAD, "F.Cu", FOUR, [touch, plane("In2.Cu")], {"GND"}) == "In2.Cu"
    two = (FOUR[0], Slab("dielectric", 0.035, 1.535, 4.5, 0.02, None), Slab("copper", 1.535, 1.57, None, None, "F.Cu"))
    assert plane_under(PAD, "F.Cu", two, [plane("B.Cu")], {"GND"}) == "B.Cu"  # two layers: the bottom copper


@pytest.mark.parametrize("pieces", [
    [],  # no copper under the pad
    cut(box(-5, -5, 5, 5).difference(Point(0, 0).buffer(0.15))),  # an antipad under it, cut as the pipeline cuts it
    [plane("In1.Cu", shape=box(-5, -5, 0.0, 5)), plane("In1.Cu", shape=box(0.1, -5, 5, 5))],  # a split under it
    [plane("In1.Cu", "SIG")],  # copper of a signal net
    [plane("In1.Cu", "SIG", box(-1, -1, 1, 1)), plane("In2.Cu")]])  # another net's copper between the pad and plane
def test_a_pad_with_no_plane_under_it_has_no_vertical_port(pieces):  # Review Focus 4
    assert plane_under(PAD, "F.Cu", FOUR, pieces, {"GND"}) is None


def test_a_vertical_port_needs_a_mesh_line_inside_its_pad():  # D-11: a coded refusal, never E_INTERNAL
    tiny = box(0.02, 0.02, 0.08, 0.08)  # between the lines at 0 and 0.1
    with pytest.raises(KrsError) as e:
        place(End("P9", tiny, tiny, "F.Cu", "external", ref_layer="In1.Cu"), V_MESH, FOUR, [])
    assert (e.value.code, e.value.params) == ("E_PORT_BOX", {"name": "P9"})


def test_an_si_end_reaches_a_reference_only_across_clear_copper():  # Stage 4 design 5.5; Review Focus 2
    sig, gnd, mid = box(0, 0, 0.4, 1.35), box(1.3, 0, 1.7, 1.35), box(0.65, 0, 1.05, 1.35)  # micro-B D+, GND, ID
    pieces = [Piece("F.Cu", "D+", sig, True), Piece("F.Cu", "GND", gnd, True)]
    assert clear_between(sig, gnd, pieces, "F.Cu", {"D+", "GND"})
    assert not clear_between(sig, gnd, [*pieces, Piece("F.Cu", "", mid, True)], "F.Cu", {"D+", "GND"})  # the ID pad
    assert clear_between(sig, gnd, [*pieces, Piece("In1.Cu", "", mid, True)], "F.Cu", {"D+", "GND"})  # another layer
    assert not clear_between(sig, box(1, 2, 2, 3), pieces, "F.Cu", {"D+", "GND"})  # apart both ways: no box


def test_an_si_ends_reference_is_v1s_or_the_plane_under_its_pad():  # Stage 4 design 5.5; Review Focus 2
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    c, zs = classify(b), zstack(b.stackup, b.copper_layers)
    pieces, _ = copper_pieces(b, box(94, -106, 134, -94), {s.copper: round(s.z1 - s.z0, 6) for s in zs if s.copper})
    pad = {n: next(p for p in b.pads(n) if p.layers) for n in ("J1.5", "U1.17")}
    j15, u17 = ({"pad": n, "uuid": pad[n].uuid} for n in ("J1.5", "U1.17"))
    assert si_reference(b, c, pieces, zs, "P1", "J1.3", j15, 1.2) == {"plane": "In1.Cu"}  # J1.4 lies between
    assert si_reference(b, c, pieces, zs, "P3", "U1.3", u17, 1.2) == u17  # 0.2 mm across clear copper
    far = {"point": [102.521, 100.183], "layer": "F.Cu"}  # TP1.1's nearest ground copper, 5 mm off
    assert si_reference(b, c, pieces, zs, "P5", "TP1.1", far, 1.2) == {"plane": "In1.Cu"}  # never E_REFERENCE_POINT
    with pytest.raises(KrsError) as e:
        si_reference(b, c, [pc for pc in pieces if pc.layer == "F.Cu"], zs, "P5", "TP1.1", far, 1.2)  # no plane
    assert (e.value.code, e.value.params) == ("E_SI_NO_REFERENCE", {"pad": "TP1.1", "layer": "F.Cu", "reach_mm": "1.2"})


@pytest.mark.openems
@pytest.mark.parametrize("n", [2, 3])
def test_lpf915_passes_the_port_gates(tmp_path, capsys, monkeypatch, n):  # D-11, D-45; about 1–2 min each
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    runs.save_settings({"machines": {runs.machine_key(): {"threads": 4, "pool": 1, "aggregate_mcs": 200.0}}})
    pj = tmp_path / "lpf915" / "project.json"
    assert main(["new", str(FIX / "lpf915.kicad_pcb"), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz",
                 "--lid-height", "2.5", "-o", str(pj.parent)]) == 0
    d = load_project(pj)
    d["mesh"]["n"], d["gates"]["fit2d_limit"] = n, 0.05  # n = 3: E_FIT2D_FINE's own advice, RF_B reads +4.39 %
    save_project(pj, d)
    capsys.readouterr()
    # 3 when a gate blocks: C-15 on all six ports; at n = 2 P2's cap nodes lie in air
    assert main(["cost", str(pj)]) == 0
    assert render("E_PORT_OPEN", name="P2", end="signal") not in capsys.readouterr().out
