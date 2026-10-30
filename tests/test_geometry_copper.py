# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pytest
import shapely
from shapely import unary_union
from shapely.geometry import LineString, Point, Polygon, box

from kicad_rf_studio.core.geometry.copper import Piece, clean, connectivity, copper_pieces, is_solid, split_holes
from kicad_rf_studio.core.geometry.region import build_region
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.shapes import circle
from kicad_rf_studio.core.kicad.stackup import kicad_default
from kicad_rf_studio.core.kicad.tracer import Chain

FIX = Path(__file__).parent / "fixtures"
T = {"F.Cu": .035, "B.Cu": .035}
BIG = box(-1000, -1000, 1000, 1000)  # a crop that holds every test board


def footprint(pads):
    return f'(footprint "Lib:X" (layer "F.Cu") (uuid "f1") (at 0 0) (property "Reference" "U1") {pads})'


def test_copper_follows_pad_layers(mini_board):
    zoo = load_board(FIX / "pads_zoo.kicad_pcb")
    pieces, _ = copper_pieces(zoo, BIG, T)
    for layer in zoo.copper_layers:  # every pad's copper on exactly its layers; the paste-only pads on none
        pads = unary_union([p.polygon for p in zoo.all_pads() if layer in p.layers])
        assert unary_union([pc.polygon for pc in pieces if pc.layer == layer]).hausdorff_distance(pads) <= 0.010 + 1e-6
    tht = next(p for p in zoo.all_pads() if p.kind == "thru_hole")
    assert {pc.layer for pc in pieces if pc.polygon.contains(Point(tht.center))} == set(tht.layers)
    # R-P2-4: pads_zoo has no np_thru_hole and no MultiPolygon pad, so a mini board holds them, with a paste-only pad
    b = mini_board(footprint(
        '(pad "" np_thru_hole circle (at 0 0) (size 3 3) (drill 3) (layers "*.Cu" "*.Mask") (uuid "h")) '
        '(pad "1" smd custom (at 10 0) (size 1 1) (layers "B.Cu") (options (clearance outline) (anchor rect)) '
        '(primitives (gr_rect (start 2 -0.5) (end 3 0.5) (width 0) (fill yes))) (uuid "m")) '
        '(pad "" smd rect (at 0 5) (size 1 1) (layers "F.Paste") (uuid "p"))'))
    pieces, _ = copper_pieces(b, BIG, T)
    npth = next(p for p in b.all_pads() if p.kind == "np_thru_hole")
    for bare in (npth, next(p for p in b.all_pads() if p.kind == "smd" and not p.layers)):
        assert bare.layers == () and not any(pc.polygon.intersects(bare.polygon.buffer(-1e-3)) for pc in pieces)
    multi = next(p for p in b.all_pads() if p.polygon.geom_type == "MultiPolygon")
    covered = unary_union([pc.polygon for pc in pieces if pc.layer == multi.layers[0]])
    assert multi.layers == ("B.Cu",) and all(covered.contains(g.buffer(-1e-3)) for g in multi.polygon.geoms)


def test_hole_split_keeps_area():
    sq = box(0, 0, 10, 10).difference(Point(3, 3).buffer(1)).difference(Point(7, 6).buffer(1))
    parts = split_holes(sq)
    assert all(not p.interiors and p.is_valid for p in parts)
    assert sum(p.area for p in parts) == pytest.approx(sq.area, abs=1e-6)
    assert unary_union(parts).symmetric_difference(sq).area < 1e-6


def test_pieces_of_a_pour_cut_by_the_crop_are_hole_free_and_keep_its_area():
    # lpf915's GND pours have a hole each. The crop cuts through both pours and the F.Cu hole; B.Cu's stays whole
    b = load_board(FIX / "lpf915.kicad_pcb")
    x0, y0, x1, y1 = b.outline.bounds
    crop = box(x0 + 7, y0 + 5, x1 - 7, y1 - 5)
    pieces, _ = copper_pieces(b, crop, T)
    for pc in pieces:  # hole-free, valid, normalised and on the 1e-6 mm grid
        assert not pc.polygon.interiors and pc.polygon.is_valid
        assert pc.polygon.equals_exact(shapely.normalize(pc.polygon), 0)
        assert all(round(c, 6) == c for xy in pc.polygon.exterior.coords for c in xy)
    for layer, holes in (("F.Cu", 0), ("B.Cu", 1)):
        on = (layer, "GND")
        group = [a.polygon for a in b.areas if (a.layer, a.net) == on]
        group += [t.polygon() for t in b.tracks if (t.layer, t.net) == on]
        group += [p.polygon for p in b.all_pads() if p.net == "GND" and layer in p.layers]
        group += [circle(v.at, v.diameter / 2) for v in b.vias if v.net == "GND"]  # rings: each via joins F.Cu, B.Cu
        gnd = clean(shapely.GeometryCollection(group), crop)
        assert sum(len(g.interiors) for g in gnd.geoms) == holes
        split = [pc.polygon.area for pc in pieces if (pc.layer, pc.net) == (layer, "GND")]
        assert sum(split) == pytest.approx(gnd.area, abs=1e-6)


def test_clean_simplifies_within_10_um_and_quantises():
    arc = Point(0, 0).buffer(1, quad_segs=256)
    out = clean(arc, box(-5, -5, 5, 5))
    assert out.hausdorff_distance(arc) <= 0.010 + 1e-9
    assert all(round(c, 6) == c for g in out.geoms for xy in g.exterior.coords for c in xy)


def test_clip_one_mm_past_walls_not_at_roi(mini_board):
    # a 30 mm GND trace beside a 10 mm SIG chain: GND keeps its copper past the ROI and the walls, out to the crop
    b = mini_board('(segment (start 10 0) (end 20 0) (width 0.2) (layer "F.Cu") (net "SIG") (uuid "s")) '
                   '(segment (start 0 1) (end 30 1) (width 0.2) (layer "F.Cu") (net "GND") (uuid "g"))')
    region = build_region(b, Chain("", "", ("SIG",), (), ()), [], zstack(kicad_default(0.8), b.copper_layers), 30e9)
    pieces, _ = copper_pieces(b, region.crop, T)
    (piece,) = [pc for pc in pieces if pc.net == "GND"]
    assert piece.polygon.bounds[2] > region.walls[1] > region.roi.bounds[2]
    assert piece.polygon.bounds[2] == pytest.approx(region.crop.bounds[2])
    assert piece.polygon.bounds[0] == pytest.approx(region.crop.bounds[0])


def test_solid_vs_sheet():
    t = 0.035
    assert is_solid(box(0, 0, 0.6, 20), box(0.75, 0, 5, 20), t)  # 0.15 mm gap < 30·t
    assert is_solid(box(0, 0, 5, 20), box(6, 0, 11, 20), t)  # wide, so solid only through its 1 mm gap < 30·t
    assert not is_solid(box(0, 0, 5, 20), box(7, 0, 12, 20), t)  # 5 mm wide, 2 mm gap
    assert is_solid(box(0, 0, 5, 5).union(box(5, 2, 6, 2.5)), Polygon(), t)  # 0.5 mm neck
    assert is_solid(box(0, 0, 5, 5).union(box(5, 2, 7, 2.5)).union(box(7, 0, 12, 5)), Polygon(), t)  # between two
    # a gap inside one polygon is a gap: a 1.5 mm hairpin's 0.3 mm slot, a 0.2 mm slot and a 1 mm hole in a plane
    plane = box(0, 0, 10, 10)
    assert is_solid(LineString([(10, 0), (0, 0), (0, 1.8), (10, 1.8)]).buffer(0.75), Polygon(), t)
    assert is_solid(plane.difference(box(4.9, 2, 5.1, 8)), Polygon(), t)
    assert is_solid(plane.difference(Point(5, 5).buffer(0.5)), Polygon(), t)
    # ...but a 1.1 mm hole is not, nor the corner where a 1.5 mm track leaves a pad at 45°
    assert not is_solid(plane.difference(Point(5, 5).buffer(0.55)), Polygon(), t)
    assert not is_solid(box(0, 0, 3, 3).union(LineString([(3, 1.5), (7.5, 6)]).buffer(0.75)), Polygon(), t)
    # Task 3 rulings: rounded corners are no narrow width, nor are the nanometre slivers an opening shaves off a
    # cleaned outline (coupon_ms's 1.35 mm line, alone on F.Cu, loses 1.4e-6 mm² of them)
    assert not is_solid(box(0, 0, 5, 5).buffer(-0.2).buffer(0.2), Polygon(), t)
    (line,) = [pc for pc in copper_pieces(load_board(FIX / "coupon_ms.kicad_pcb"), BIG, T)[0] if pc.net == "LINE"]
    assert not line.solid
    # coupon_gcpw_pads' two F.Cu GND pours are wide: they are solid through their 0.15 mm gap to LINE
    gcpw = copper_pieces(load_board(FIX / "coupon_gcpw_pads.kicad_pcb"), BIG, T)[0]
    assert [pc.solid for pc in gcpw if (pc.layer, pc.net) == ("F.Cu", "GND")] == [True, True]


def test_gaps_inside_a_net_and_to_a_via_ring_make_copper_solid(mini_board):
    # a one-net hairpin of 1.5 mm tracks, 0.3 mm between its arms
    arms = [(10, 0, 0, 0), (0, 0, 0, 1.8), (0, 1.8, 10, 1.8)]
    hairpin = mini_board(''.join(f'(segment (start {x0} {y0}) (end {x1} {y1}) (width 1.5) (layer "F.Cu") (net "RES") '
                                 f'(uuid "s{i}")) ' for i, (x0, y0, x1, y1) in enumerate(arms)))
    assert [(pc.net, pc.solid) for pc in copper_pieces(hairpin, BIG, T)[0]] == [("RES", True)]
    # a B.Cu GND plane 0.15 mm from a SIG via's 0.6 mm ring, which is copper on both layers it joins
    b = mini_board('(gr_poly (pts (xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10)) (stroke (width 0)) (fill yes) '
                   '(layer "B.Cu") (net "GND") (uuid "g")) '
                   '(via (at 10.45 5) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net "SIG") (uuid "v"))')
    pieces, _ = copper_pieces(b, BIG, T)
    assert sorted((pc.layer, pc.net, pc.solid) for pc in pieces) == [
        ("B.Cu", "GND", True), ("B.Cu", "SIG", True), ("F.Cu", "SIG", True)]
    assert all(pc.polygon.hausdorff_distance(Point(10.45, -5).buffer(0.3)) <= 0.010 for pc in pieces if pc.net == "SIG")
    # lpf915's B.Cu GND plane stays a sheet: where its J2 tab meets the pour's rounded corner is a corner, not a gap
    plane = [pc.solid for pc in copper_pieces(load_board(FIX / "lpf915.kicad_pcb"), BIG, T)[0] if pc.layer == "B.Cu"]
    assert plane and not any(plane)


def test_copper_lost_in_cleanup_warns(mini_board):
    # Task 3 ruling: simplify keeps every ring, so only copper thinner than the 1e-6 mm grid vanishes: a 0.1 nm sliver
    sliver = ('(gr_poly (pts (xy 0 0) (xy 5 0) (xy 5 0.0000001) (xy 0 0.0000001)) (stroke (width 0)) (fill yes) '
              '(layer "F.Cu") (net "N1") (uuid "s1"))')
    pieces, w = copper_pieces(mini_board(sliver), BIG, T)
    assert ("W_COPPER_EMPTIED", {"net": "N1", "layer": "F.Cu"}) in w and pieces == []
    assert copper_pieces(mini_board(sliver), box(10, 10, 20, 20), T)[1] == []  # copper outside the crop is no loss


def test_a_join_accepts_touches_within_it_and_no_other():  # Stage 3 design 5.3; RF 2
    rf, gnd = Piece("F.Cu", "RF", box(0, 0, 4, 1), True), Piece("F.Cu", "GND", box(3.5, 0, 6, 1), True)
    roi, crop, join = box(-10, -10, 10, 10), box(-20, -20, 20, 20), box(3.4, -0.1, 4.1, 1.1)
    assert connectivity([rf, gnd], [], roi, ["RF"], crop) == [("E_SHORT_IN_ROI", {"nets": "GND, RF"})]
    assert connectivity([rf, gnd], [], roi, ["RF"], crop, join=join) == []
    other = Piece("F.Cu", "GND", box(-1, 0, 0.2, 1), True)  # a second touch, outside the join
    assert connectivity([rf, gnd, other], [], roi, ["RF"], crop, join=join) == [("E_SHORT_IN_ROI", {"nets": "GND, RF"})]
