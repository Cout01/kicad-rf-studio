# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
from pathlib import Path

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from kicad_rf_studio.core.kicad import load_board

FIX = Path(__file__).parent / "fixtures"
MAX_ERR = 0.001  # mm, the arc tolerance of shapes.py


@pytest.mark.parametrize("name", ["pads_zoo", "lpf915", "lpf915-45", "coupon_gcpw_pads"])
def test_pads_match_pcbnew(name):
    b = load_board(FIX / f"{name}.kicad_pcb")
    truth = json.loads((FIX / f"{name}.pads.json").read_text(encoding="utf-8"))
    pads = {p.uuid: p for fp in b.footprints.values() for p in fp.pads}
    assert set(pads) == set(truth)
    for uuid, t in truth.items():
        p = pads[uuid]
        assert p.name == t["name"] and math.dist(p.center, t["center"]) <= 1e-6, p.name
        ref = unary_union([Polygon(ring) for ring in t["polygons"]])
        assert p.polygon.hausdorff_distance(ref) <= 0.005, p.name
        assert p.polygon.symmetric_difference(ref).area <= 2 * MAX_ERR * ref.length + 1e-6, p.name


def test_lpf915_footprints():
    b = load_board(FIX / "lpf915.kicad_pcb")
    assert b.footprints["C1"].value == "100pF" and b.footprints["R2"].dnp and not b.footprints["R1"].dnp
    assert b.footprints["L1"].lib_id == "Inductor_SMD:L_0402_1005Metric"
    assert [p.net for p in b.pads("C2.1")] == ["RF_B"] and b.pads("U1.17")[0].net == "GND"


# --- beyond the brief's two tests: what pcbnew's pad truth cannot show --------------------------------


def footprint(body, at="0 0"):
    return f'(footprint "Lib:Part" (layer "F.Cu") (uuid "f1") (at {at}) (property "Reference" "U9") {body})'


def test_footprint_fields_are_read(mini_board):
    b = mini_board(footprint('(property "Value" "BGA") (attr smd dnp) (solder_mask_margin 0.1)', at="10 5 90"))
    fp = b.footprints["U9"]
    assert (fp.ref, fp.value, fp.mpn, fp.lib_id, fp.uuid, fp.layer) == ("U9", "BGA", None, "Lib:Part", "f1", "F.Cu")
    assert (fp.at, fp.angle, fp.dnp, fp.mask_margin, fp.pads) == ((10.0, -5.0), 90.0, True, 0.1, ())


@pytest.mark.parametrize("name", ["MPN", "Manufacturer Part Number", "manufacturer_part_number"])
def test_mpn_comes_from_any_of_its_usual_property_names(mini_board, name):
    assert mini_board(footprint(f'(property "{name}" "ABC-1")')).footprints["U9"].mpn == "ABC-1"


@pytest.mark.parametrize("attr, dnp", [("(attr smd)", False), ("(attr smd dnp)", True), ("(attr smd) (dnp yes)", True)])
def test_dnp_is_an_attribute_or_a_flag_of_its_own(mini_board, attr, dnp):
    fp = mini_board(footprint(attr)).footprints["U9"]
    assert fp.dnp is dnp and fp.mask_margin is None


def test_pad_layers_nets_and_margins(tmp_path):
    pads = ('(pad "1" thru_hole circle (at 1 0) (size 1 1) (drill 0.5) (layers "*.Cu" "*.Mask") (net 1 "SIG") '
            '(solder_mask_margin 0.05) (uuid "p1")) '
            '(pad "2" thru_hole circle (at 3 0) (size 1 1) (drill 0.5) (layers "F&B.Cu" "B.Mask") (uuid "p2")) '
            '(pad "3" smd rect (at 5 0) (size 1 1) (layers "B.Cu" "B.Paste" "B.Mask") (net 1 "SIG") (uuid "p3")) '
            '(pad "" smd roundrect (at 0 0) (size 1 1) (layers "F.Paste") (roundrect_rratio 0.25) (uuid "p4"))')
    path = tmp_path / "four.kicad_pcb"
    path.write_text('(kicad_pcb (version 20241229) (layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In2.Cu" signal) '
                    f'(2 "B.Cu" signal)) (net 0 "") (net 1 "SIG") {footprint(pads)})', encoding="utf-8")
    p1, p2, p3, p4 = load_board(path).footprints["U9"].pads
    assert (p1.name, p1.kind, p1.net, p1.mask_margin) == ("U9.1", "thru_hole", "SIG", 0.05)
    assert (p1.layers, p1.mask_sides) == (("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"), ("F", "B"))  # "*": every one
    assert (p2.kind, p2.layers, p2.mask_sides, p2.net) == ("thru_hole", ("F.Cu", "B.Cu"), ("B",), "")  # "F&B"
    assert (p2.mask_margin, p3.layers, p3.mask_sides) == (None, ("B.Cu",), ("B",))
    # a paste-only pad is kept, with no copper and no net
    assert (p4.name, p4.kind, p4.layers, p4.mask_sides, p4.net) == ("U9.", "smd", (), (), "")


def test_an_unplated_hole_has_no_copper_whatever_its_layers_say(mini_board):
    pad = '(pad "" np_thru_hole circle (at 0 0) (size 3 3) (drill 3) (layers "*.Cu" "*.Mask") (uuid "h1"))'
    (hole,) = mini_board(footprint(pad)).footprints["U9"].pads
    assert (hole.kind, hole.layers, hole.mask_sides) == ("np_thru_hole", (), ("F", "B"))


def test_a_footprint_zone_is_read_in_board_coordinates(mini_board):
    """KiCad writes a footprint's zone in board coordinates, so the footprint's (10, 5, 90°) must not move it."""
    pts = "(pts (xy 11 4) (xy 13 4) (xy 13 6) (xy 11 6))"
    zone = (f'(zone (net 1) (net_name "GND") (layer "F.Cu") (uuid "fz") (polygon {pts}) '
            f'(filled_polygon (layer "F.Cu") {pts}))')
    b = mini_board('(net 1 "GND") ' + footprint(zone, at="10 5 90"))
    (a,) = b.areas
    assert (a.layer, a.net, a.source, a.uuid) == ("F.Cu", "GND", "zone", "fz")
    assert a.polygon.equals(Polygon([(11, -4), (13, -4), (13, -6), (11, -6)]))


def test_pads_that_share_a_number_are_all_kept():
    b = load_board(FIX / "pads_zoo.kicad_pcb")
    assert [p.layers for p in b.pads("J2.2")] == [("F.Cu",), ("B.Cu",), ("F.Cu",), ("B.Cu",)]
    assert b.footprints["J3"].layer == "B.Cu" and b.footprints["J3"].angle == 150


def test_a_per_layer_padstack_warns_and_uses_the_main_shape(mini_board):
    pad = ('(pad "1" smd rect (at 0 0) (size 1 2) (layers "F.Cu") (uuid "p1") '
           '(padstack (mode front_inner_back) (layer "Inner" (shape circle) (size 3 3))))')
    b = mini_board(footprint(pad))
    assert ("W_PADSTACK", {"pad": "U9.1"}) in b.warnings
    assert b.pads("U9.1")[0].polygon.area == pytest.approx(2)


def test_footprint_graphics_are_placed_and_sorted_like_board_graphics(mini_board):
    """A footprint at (10, 5) turned 90°: copper is a netless area, mask an opening, Edge.Cuts the outline."""
    def graphic(kind, geometry, layer, uuid, fill=""):
        return f'({kind} {geometry} (stroke (width 0) (type solid)) {fill} (layer "{layer}") (uuid "{uuid}"))'

    corners = ["-2 -1", "2 -1", "2 1", "-2 1", "-2 -1"]  # a 4 x 2 loop, which the turn makes 2 x 4
    body = (graphic("fp_rect", "(start 1 0) (end 2 1)", "F.Cu", "cu", "(fill yes)")
            + graphic("fp_poly", "(pts (xy 0 0) (xy 1 0) (xy 0 1))", "B.Mask", "mask", "(fill yes)")
            + graphic("fp_circle", "(center 0 0) (end 1 0)", "F.SilkS", "silk", "(fill yes)")
            + "".join(graphic("fp_line", f"(start {s}) (end {e})", "Edge.Cuts", f"e{s}")
                      for s, e in zip(corners, corners[1:])))
    b = mini_board(footprint(body, at="10 5 90"))
    (a,) = b.areas
    assert (a.layer, a.net, a.source, a.uuid) == ("F.Cu", "", "graphic", "cu")
    assert a.polygon.bounds == pytest.approx((10, -4, 11, -3))
    assert b.warnings == [("W_NETLESS_COPPER", {"uuid": "cu", "layer": "F.Cu"})]
    (mask,) = b.mask_graphics["B"]
    assert mask.bounds == pytest.approx((10, -5, 11, -4)) and b.mask_graphics["F"] == []
    assert b.outline.bounds == pytest.approx((9, -7, 11, -3)) and b.outline.area == pytest.approx(8)


def custom_pad(primitive, anchor):
    return footprint(f'(pad "1" smd custom (at 0 0) (size 0.2 0.2) (layers "F.Cu") '
                     f'(options (clearance outline) (anchor {anchor})) (primitives {primitive}) (uuid "p1"))')


@pytest.mark.parametrize("primitive, anchor, area", [
    # the circle anchor, 0.2 mm across, is exactly the line's round start cap
    ("(gr_line (start 0 0) (end 2 0) (width 0.2))", "circle", 2 * 0.2 + math.pi * 0.1**2),
    ("(gr_arc (start 1 0) (mid 0 1) (end -1 0) (width 0.2))", "circle", math.pi * 0.2 + 2 * math.pi * 0.1**2),
    ("(gr_circle (center 0 0) (end 1 0) (width 0) (fill yes))", "rect", math.pi),
    ("(gr_circle (center 2 0) (end 3 0) (width 0.2))", "rect", math.pi * (1.1**2 - 0.9**2) + 0.04),  # a ring
    ("(gr_rect (start -1 -0.5) (end 1 0.5) (width 0) (fill yes))", "rect", 2),
    ("(gr_poly (pts (xy 0 0) (xy 2 0) (xy 0 2)) (width 0))", "rect", 2 + 0.04 - 0.01),  # a polygon is always filled
], ids=["line", "arc", "disc", "ring", "rect", "poly"])
def test_custom_pad_is_its_anchor_and_its_primitives(mini_board, primitive, anchor, area):
    assert mini_board(custom_pad(primitive, anchor)).pads("U9.1")[0].polygon.area == pytest.approx(area, rel=2e-3)
