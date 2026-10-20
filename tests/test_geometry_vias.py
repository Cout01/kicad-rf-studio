# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pytest
import shapely
from shapely.geometry import Point, box

from kicad_rf_studio.core.geometry.copper import Piece, connectivity, copper_pieces
from kicad_rf_studio.core.geometry.region import build_region
from kicad_rf_studio.core.geometry.vias import via_rods
from kicad_rf_studio.core.geometry.zstack import substrate_h, zstack
from kicad_rf_studio.core.kicad import classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.stackup import kicad_default
from kicad_rf_studio.core.kicad.tracer import Chain
from kicad_rf_studio.core.mesh.protect import Protected, protected_set

FIX = Path(__file__).parent / "fixtures"
T = {"F.Cu": .035, "B.Cu": .035}


def setup(name, start="", end=""):
    """A fixture's board, z-stack, region (3 GHz top of band), copper pieces and protected set. The coupons have no
    pads to trace a chain between (R-P2-1), so their chain is LINE alone."""
    b = load_board(FIX / f"{name}.kicad_pcb")
    chain = trace_chain(b, start, end) if start else Chain("", "", ("LINE",), (), ())
    zs = zstack(b.stackup, b.copper_layers)
    region = build_region(b, chain, [], zs, 3e9)
    pieces, _ = copper_pieces(b, region.crop, T)
    return b, zs, region, pieces, protected_set(b, chain, classify(b), pieces, substrate_h(zs))


def copper(pieces, nets, layer=None):
    return shapely.union_all([pc.polygon for pc in pieces if pc.net in nets and layer in (None, pc.layer)])


def test_fence_vias_near_line_are_solid():  # coupon_gcpw: 42 GND vias 0.6 mm from the line's edges, h = 0.71 mm
    b, zs, region, pieces, prot = setup("coupon_gcpw")
    h, line = substrate_h(zs), copper(pieces, {"LINE"})
    rods = via_rods(b, region.crop, zs, prot)
    near = [r for r in rods if line.distance(Point(r.at)) <= 3 * h]
    assert len(near) == 42 and all(r.solid for r in near)
    assert all(not r.solid for r in rods if line.distance(Point(r.at)) > 3 * h + 0.5)
    # Task 4 ruling: the reach, reach_h·h, runs to a via's ring. At 0.5h (0.355 mm) the fence's rings, 0.3 mm from
    # the line, are within it, though their centres are 0.6 mm away; at 0.3h they are not
    chain, classes = Chain("", "", ("LINE",), (), ()), classify(b)
    assert len(protected_set(b, chain, classes, pieces, h, reach_h=0.5).vias) == 42
    assert protected_set(b, chain, classes, pieces, h, reach_h=0.3).vias == frozenset()


def test_vias_beyond_reach_are_curves():
    # Task 4 ruling: coupon_gcpw has no via beyond reach. lpf915's RF_SMA fence, past the DNP R2, runs 2.7 to 7 mm
    # from the chain's copper
    b, zs, region, pieces, prot = setup("lpf915", "U1.1", "J1.1")
    h, chain = substrate_h(zs), copper(pieces, prot.nets)
    rods = via_rods(b, region.crop, zs, prot)
    far = [r for r in rods if chain.distance(Point(r.at)) > 3 * h + 0.5]
    assert len(far) == 14 and not any(r.solid for r in far)
    assert all(r.solid for r in rods if chain.distance(Point(r.at)) <= 3 * h)


def test_measured_nets_keep_their_own_vias_but_not_other_nets_vias(mini_board):
    # every fixture via is GND: here LINE drops to B.Cu through v1, and v2 is a VDD via 1 mm from the line
    b = mini_board('(segment (start 0 0) (end 10 0) (width 0.5) (layer "F.Cu") (net "LINE") (uuid "l1")) '
                   '(via (at 10 0) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net "LINE") (uuid "v1")) '
                   '(via (at 5 1) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net "VDD") (uuid "v2"))')
    pieces, _ = copper_pieces(b, box(-50, -50, 50, 50), T)
    h = substrate_h(zstack(kicad_default(0.8), b.copper_layers))
    assert protected_set(b, Chain("", "", ("LINE",), (), ()), classify(b), pieces, h).vias == {"v1"}


def test_rod_spans_its_layers():
    b, zs, region, _, prot = setup("coupon_gcpw")
    r = via_rods(b, region.crop, zs, prot)[0]
    slab = {s.copper: s for s in zs if s.kind == "copper"}
    assert (r.z0, r.z1) == (slab["B.Cu"].z0, slab["F.Cu"].z1)
    assert (r.net, r.radius) == ("GND", 0.15)  # the barrel is the 0.3 mm drill; the ring is copper (Task 3)
    assert via_rods(b, box(0, 0, 1, 1), zs, prot) == []  # a via outside the crop is left out


def test_protected_area_holds_the_chain_its_part_pads_and_the_ground_within_reach():
    b, zs, region, pieces, prot = setup("coupon_gcpw")
    reach, line = 3 * substrate_h(zs), copper(pieces, {"LINE"})
    assert prot.nets == {"LINE"} and prot.boxes == () and set(prot.area) == {"F.Cu", "B.Cu"}
    ground = copper(pieces, {"GND"}, "F.Cu").intersection(line.buffer(reach))
    assert prot.area["F.Cu"].symmetric_difference(line.union(ground)).area < 1e-6
    # B.Cu: the plane under the line, 3h either side of it, as far as the plane goes
    x0, _, x1, _ = copper(pieces, {"GND"}, "B.Cu").bounds
    assert prot.area["B.Cu"].bounds == pytest.approx((x0, -100.3 - reach, x1, -99.7 + reach), abs=1e-6)
    # lpf915: R2 is a (DNP) shunt part, so its pad on RF_SMA is protected, but not the RF_SMA track beyond it
    b, *_, prot = setup("lpf915", "U1.1", "J1.1")
    (pad,) = b.pads("R2.2")
    assert prot.area["F.Cu"].contains(pad.polygon.buffer(-1e-3)) and not prot.area["F.Cu"].intersects(Point(111, -104))


def test_open_in_roi_blocks():  # coupon_ms with a 0.1 mm cut in LINE inside the ROI
    b, zs, region, pieces, prot = setup("coupon_ms")
    nets = {"LINE", "GND"}
    assert connectivity(pieces, [], region.roi, nets, region.crop) == []
    slot = box(109.95, -101, 110.05, -99)
    cut = [Piece(pc.layer, pc.net, q, pc.solid) for pc in pieces
           for q in (shapely.get_parts(pc.polygon.difference(slot)) if pc.net == "LINE" else [pc.polygon])]
    assert ("E_OPEN_IN_ROI", {"net": "LINE"}) in connectivity(cut, [], region.roi, nets, region.crop)
    # with the cut past a shorter ROI, the far half of LINE floats in the margin
    short_roi = box(99, -105, 109, -95)
    assert connectivity(cut, [], short_roi, nets, region.crop) == [("W_OPEN_IN_MARGIN", {"net": "LINE"})]


def test_rods_join_the_layers():
    # coupon_gcpw's GND is two F.Cu pours and the B.Cu plane, one net only through the fence vias
    b, zs, region, pieces, prot = setup("coupon_gcpw")
    nets = {"LINE", "GND"}
    assert connectivity(pieces, via_rods(b, region.crop, zs, prot), region.roi, nets, region.crop) == []
    assert connectivity(pieces, [], region.roi, nets, region.crop) == [("E_OPEN_IN_ROI", {"net": "GND"})]


def test_plated_holes_join_their_layers(mini_board):
    # Task 4 fix: a plated hole (a thru_hole pad) has a barrel, as a via has. LINE comes in on F.Cu to the pin J1.1,
    # whose hole is 0.3 mm off its copper's centre, and leaves on B.Cu. GND's legs J1.2, within reach of LINE, and
    # J1.3, a slot beyond it, are joined on B.Cu only
    pad = ('(pad "{0}" thru_hole circle (at {1}) (size 1.6 1.6) (drill {2}) (layers "*.Cu" "*.Mask") (net "{3}") '
           '(uuid "p{0}"))')
    b = mini_board('(footprint "Lib:SMA" (layer "F.Cu") (at 0 0) (property "Reference" "J1") '
                   + pad.format(1, "0 0", "0.8 (offset 0.3 0)", "LINE") + pad.format(2, "0 2", "0.8", "GND")
                   + pad.format(3, "0 9", "oval 0.8 1.2", "GND") + ') '
                   '(segment (start 0.3 0) (end 10 0) (width 0.5) (layer "F.Cu") (net "LINE") (uuid "l1")) '
                   '(segment (start 0.3 0) (end -10 0) (width 0.5) (layer "B.Cu") (net "LINE") (uuid "l2")) '
                   '(segment (start 0 2) (end 0 9) (width 0.5) (layer "B.Cu") (net "GND") (uuid "g1"))')
    zs, chain = zstack(kicad_default(0.8), b.copper_layers), Chain("", "", ("LINE",), (), ())
    region = build_region(b, chain, [], zs, 3e9)
    pieces, _ = copper_pieces(b, region.crop, T)
    rods = via_rods(b, region.crop, zs, protected_set(b, chain, classify(b), pieces, substrate_h(zs)))
    # a barrel sits at its hole, half its drill wide (a slot's narrower axis) and through the board; the pin's barrel
    # and the leg's within reach are solid
    assert {(r.net, r.at, r.radius, r.solid) for r in rods} == {
        ("LINE", (0.0, 0.0), 0.4, True), ("GND", (0.0, -2.0), 0.4, True), ("GND", (0.0, -9.0), 0.4, False)}
    slab = {s.copper: s for s in zs if s.kind == "copper"}
    assert {(r.z0, r.z1) for r in rods} == {(slab["B.Cu"].z0, slab["F.Cu"].z1)}
    nets, roi, crop = {"LINE", "GND"}, region.roi, region.crop
    assert connectivity(pieces, rods, roi, nets, crop) == []
    assert connectivity(pieces, [], roi, nets, crop) == [("E_OPEN_IN_ROI", {"net": n}) for n in ("GND", "LINE")]


def test_a_barrel_sits_at_its_hole_on_the_grid():
    # Task 4 fix: pads_zoo's thru_hole pads ZOO1.6 and ZOO1.7 lie in a footprint turned 30 degrees. ZOO1.7's hole is
    # offset (0.3, 0.2) from its copper, which pcbnew centres at (108.421281, -114.938268)
    b = load_board(FIX / "pads_zoo.kicad_pcb")
    rods = via_rods(b, box(0, -200, 200, 0), zstack(b.stackup, b.copper_layers),
                    Protected(frozenset(), {}, frozenset(), ()))
    assert {r.at for r in rods} == {(105.5, -116.598076), (108.098076, -115.098076)}


def test_parts_that_run_out_of_the_crop_may_join_outside_it(mini_board):
    # Task 4 fix: the pieces are clipped to the crop, so a net's parts that run out of it may be one on the board. VDD's
    # two legs reach into the ROI and close 60 mm away, past the crop: no open. A VDD island that stays in the crop is a
    # break, in the ROI when it reaches the ROI, even across the ROI's edge
    seg = '(segment (start {} {}) (end {} {}) (width 0.5) (layer "F.Cu") (net "{}") (uuid "{}"))'
    b = mini_board(seg.format(0, 0, 10, 0, "LINE", "l") + seg.format(2, -1.5, 2, -60, "VDD", "v1")
                   + seg.format(8, -1.5, 8, -60, "VDD", "v2") + seg.format(2, -60, 8, -60, "VDD", "v3"))
    zs = zstack(kicad_default(0.8), b.copper_layers)
    region = build_region(b, Chain("", "", ("LINE",), (), ()), [], zs, 3e9)
    pieces, _ = copper_pieces(b, region.crop, T)
    nets, roi, crop = {"LINE", "VDD"}, region.roi, region.crop
    assert connectivity(pieces, [], roi, nets, crop) == []
    near, far = (Piece("F.Cu", "VDD", box(4.5, y, 5.5, y + 1), False) for y in (2, 10))  # the ROI ends at y = 2.38
    assert connectivity([*pieces, near], [], roi, nets, crop) == [("E_OPEN_IN_ROI", {"net": "VDD"})]
    assert connectivity([*pieces, far], [], roi, nets, crop) == [("W_OPEN_IN_MARGIN", {"net": "VDD"})]


def test_short_in_margin_warns(mini_board):  # a LINE stub runs out of the ROI onto a GND pour, inside the crop
    rect = '(gr_poly (pts (xy {0} {1}) (xy {2} {1}) (xy {2} {3}) (xy {0} {3})) (stroke (width 0)) (fill yes) '
    b = mini_board('(segment (start 0 0) (end 10 0) (width 0.5) (layer "F.Cu") (net "LINE") (uuid "l1")) '
                   '(segment (start 5 0) (end 5 8) (width 0.5) (layer "F.Cu") (net "LINE") (uuid "l2")) '
                   + rect.format(0, 8, 10, 12) + '(layer "F.Cu") (net "GND") (uuid "g")) '
                   # Task 4 ruling: copper with no net floats. Here it touches LINE and lies in two parts
                   + rect.format(1.5, -0.5, 2.5, 0.5) + '(layer "F.Cu") (uuid "f1")) '
                   + rect.format(20, 8, 21, 9) + '(layer "F.Cu") (uuid "f2"))')
    crop = box(-50, -50, 50, 50)
    pieces, _ = copper_pieces(b, crop, T)
    nets = {"LINE", ""}
    assert connectivity(pieces, [], box(-1, -3, 11, 3), nets, crop) == [("W_SHORT_IN_MARGIN", {"nets": "GND, LINE"})]
    assert connectivity(pieces, [], box(-1, -9, 11, 3), nets, crop) == [("E_SHORT_IN_ROI", {"nets": "GND, LINE"})]
