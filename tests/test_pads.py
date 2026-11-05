# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
import typing
from collections import Counter
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.board import Pad

FIX = Path(__file__).parent / "fixtures"
MAX_ERR = 0.001  # mm, the arc tolerance of shapes.py
QFN = "Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm"


@pytest.mark.parametrize("name", ["pads_zoo", "lpf915", "lpf915-45", "coupon_gcpw_pads", "ifa2g4", "ifa2g4_pi",
                                  "meander915", "ifa2g4_pi_shift", "ifa2g4_pi_dxp", "ifa2g4_pi_dxm", "ifa2g4_pi_pour",
                                  "usb2_hs", "usb2_hs_neck", "usb2_hs_gap", "usb2_hs_45", "qspi_clk", "p4b_ms90",
                                  "p4b_ms100", "p4b_sl90", "p4b_ms90_45", "p4b_ms100_45", "p4b_ms90_vic",
                                  "p4b_ms90_cut", "p4c_l90", "p4c_step75", "p4c_step35", "si_pad_coupon",
                                  "si_pad_coupon_tall", "si_line100", "p4e_shift", "p4e_gapp", "p4e_gapm", "p4e_null",
                                  "p4e_vshift", "p4e_shift3", "p4e_gapp3", "p4e_gapm3", "p4e_vshift3"])
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


def test_the_antenna_fixtures():  # Stage 3 design 5.11: KiCad's own RF_Antenna footprints on a stated ground
    ifa, pi, mea = (load_board(FIX / f"{n}.kicad_pcb") for n in ("ifa2g4", "ifa2g4_pi", "meander915"))
    assert ifa.footprints["AE1"].lib_id == pi.footprints["AE1"].lib_id == "RF_Antenna:Texas_SWRA117D_2.4GHz_Left"
    assert mea.footprints["AE1"].lib_id == "RF_Antenna:Texas_SWRA416_868MHz_915MHz"
    assert (ifa.outline.bounds, mea.outline.bounds) == ((87.0, -124.0, 127.0, -94.0), (89.0, -146.5, 129.0, -92.5))
    for b in (ifa, pi):
        assert [(p.net, p.kind) for p in b.footprints["AE1"].pads] == [("RF", "connect"), ("GND", "thru_hole")]
    assert [(a.layer, a.net) for a in ifa.areas if a.source == "graphic"] == [("F.Cu", "")]
    assert Counter(a.layer for a in mea.areas if a.source == "graphic") == {"F.Cu": 10, "B.Cu": 27}
    assert [p.number for p in mea.footprints["AE1"].pads].count("") == 19
    for b, x in ((ifa, 100.0), (pi, 100.0), (mea, 101.0)):
        assert b.pads("U1.1")[0].center == pytest.approx((x, -111.975)) and b.pads("U1.2")[0].net == "GND"
    assert {r: (fp.value, [p.net for p in fp.pads]) for r, fp in pi.footprints.items() if r in ("C2", "L1", "C3")} == {
        "C2": ("1pF", ["RF_A", "GND"]), "L1": ("2.7nH", ["RF_A", "RF"]), "C3": ("1pF", ["RF", "GND"])}
    assert ifa.footprints["C1"].value == "100nF" and "C1" not in mea.footprints
    for b in (ifa, pi, mea):
        assert {(a.layer, a.net) for a in b.areas if a.source == "zone"} == {("F.Cu", "GND"), ("B.Cu", "GND")}


def test_the_si_fixtures():  # Stage 4 design 5.11: four layers, KiCad's own footprints, a USB 2.0 pair, a QSPI clock
    usb, qspi = (load_board(FIX / f"{n}.kicad_pcb") for n in ("usb2_hs", "qspi_clk"))
    for b in (usb, qspi):
        assert b.copper_layers == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu") and b.thickness == pytest.approx(1.6)
        assert [(x.thickness, x.epsilon_r) for x in b.stackup.layers if x.kind == "dielectric"] == [
            (0.2, 4.3), (1.04, 4.5), (0.2, 4.3)]
        assert {(a.layer, a.net) for a in b.areas if a.source == "zone"} == {("In1.Cu", "GND"), ("In2.Cu", "+3V3")}
        # three netted pads or more: the tracer never reads an IC as a two-pad part
        assert all(len([p for p in f.pads if p.net]) >= 3 for r, f in b.footprints.items() if r[0] == "U")
    fp = usb.footprints
    assert [fp[r].lib_id for r in ("J1", "U2", "U1")] == ["Connector_USB:USB_Micro-B_Molex-105017-0001",
                                                          "Package_TO_SOT_SMD:SOT-23-6", QFN]
    assert [(p.number, p.net) for p in fp["U2"].pads] == [("1", "USB_D-"), ("2", "GND"), ("3", "USB_D+"),
                                                         ("4", "USB_D+"), ("5", "VBUS"), ("6", "USB_D-")]
    assert {r: (fp[r].value, [p.net for p in fp[r].pads]) for r in ("R1", "R2", "C1")} == {
        "R1": ("22", ["USB_D+", "MCU_D+"]), "R2": ("22", ["USB_D-", "MCU_D-"]), "C1": ("100nF", ["+3V3", "GND"])}
    for name, (x, y) in {"J1.2": (98.4625, 99.675), "J1.3": (98.4625, 100.325), "J1.5": (98.4625, 101.625),
                         "U1.2": (128.5375, 99.75), "U1.3": (128.5375, 100.25), "R1.1": (122.99, 100.445),
                         "TP1.1": (108, 101.15), "TP2.1": (120, 101.15)}.items():
        assert math.dist(usb.pads(name)[0].center, (x, -y)) <= 1e-6, name
    assert usb.pads("J1.4")[0].net == "" and usb.outline.bounds == (94.0, -106.0, 134.0, -94.0)
    assert {t.width for t in usb.tracks if t.net in ("USB_D+", "USB_D-", "MCU_D+", "MCU_D-")} == {0.3, 0.6}
    assert {t.width for t in usb.tracks if t.net == "AUX"} == {0.2}
    assert {(t.layer, t.width) for t in qspi.tracks if t.net == "FLASH_CLK"} == {("F.Cu", 0.33), ("B.Cu", 0.33)}
    assert [v.net for v in qspi.vias].count("FLASH_CLK") == 2
    assert math.dist(qspi.pads("U2.6")[0].center, (119.525, -99.75)) <= 1e-6 and qspi.pads("U2.4")[0].net == "GND"
    neck, gap, bend = (load_board(FIX / f"usb2_hs_{n}.kicad_pcb") for n in ("neck", "gap", "45"))
    assert {t.width for t in neck.tracks if t.net == "USB_D+"} == {0.2, 0.3, 0.6}
    assert any(a.polygon.contains(Point(116.5, -100)) for a in usb.areas if a.layer == "In1.Cu")
    assert not any(a.polygon.contains(Point(116.5, -100)) for a in gap.areas if a.layer == "In1.Cu")
    assert sum(min(abs(t.end[0] - t.start[0]), abs(t.end[1] - t.start[1])) > 0.5 for t in bend.tracks) == 4


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


@pytest.mark.parametrize("shape, size, drill, layers", [
    ("circle", "3 3", "3", ()),  # the hole takes the whole pad
    ("circle", "4 4", "3", ("F.Cu", "B.Cu")),  # a ring of copper is left
    ("rect", "3 3", "3", ("F.Cu", "B.Cu")),  # the corners are left
    ("circle", "3 3", "3 (offset 0.2 0)", ("F.Cu", "B.Cu")),  # the copper sits off the hole
    ("oval", "3 2", "oval 3 2", ()),
], ids=["covered-circle", "ring", "rect", "offset", "covered-oval"])
def test_an_unplated_hole_has_copper_only_where_it_leaves_some(mini_board, shape, size, drill, layers):
    pad = f'(pad "" np_thru_hole {shape} (at 0 0) (size {size}) (drill {drill}) (layers "*.Cu" "*.Mask") (uuid "h"))'
    (hole,) = mini_board(footprint(pad)).footprints["U9"].pads
    assert (hole.kind, hole.layers, hole.mask_sides) == ("np_thru_hole", layers, ("F", "B"))


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


def custom_pad(primitive, anchor, size=0.2):
    return footprint(f'(pad "1" smd custom (at 0 0) (size {size} {size}) (layers "F.Cu") '
                     f'(options (clearance outline) (anchor {anchor})) (primitives {primitive}) (uuid "p1"))')


@pytest.mark.parametrize("primitive, anchor, area", [
    # the circle anchor, 0.2 mm across, is exactly the line's round start cap
    ("(gr_line (start 0 0) (end 2 0) (width 0.2))", "circle", 2 * 0.2 + math.pi * 0.1**2),
    ("(gr_arc (start 1 0) (mid 0 1) (end -1 0) (width 0.2))", "circle", math.pi * 0.2 + 2 * math.pi * 0.1**2),
    ("(gr_circle (center 0 0) (end 1 0) (width 0) (fill yes))", "rect", math.pi),
    ("(gr_circle (center 2 0) (end 3 0) (width 0.2))", "rect", math.pi * (1.1**2 - 0.9**2) + 0.04),  # a ring
    ("(gr_rect (start -1 -0.5) (end 1 0.5) (width 0) (fill yes))", "rect", 2),
], ids=["line", "arc", "disc", "ring", "rect"])
def test_custom_pad_is_its_anchor_and_its_primitives(mini_board, primitive, anchor, area):
    assert mini_board(custom_pad(primitive, anchor)).pads("U9.1")[0].polygon.area == pytest.approx(area, rel=2e-3)


def test_a_custom_pad_whose_primitives_miss_the_anchor_is_a_multipolygon(mini_board):
    pad = mini_board(custom_pad("(gr_circle (center 2 0) (end 3 0) (width 0.2))", "rect")).pads("U9.1")[0]
    assert isinstance(pad.polygon, MultiPolygon) and len(pad.polygon.geoms) == 2  # the anchor and the ring
    assert typing.get_type_hints(Pad)["polygon"] == Polygon | MultiPolygon  # and the annotation says so


FILLED = 4 + 4 * 2 * 0.05 + math.pi * 0.05**2  # the 2 x 2 square and the outer half of its 0.1 mm stroke
STROKE = 8 * 2 * 0.05 + (math.pi - 4) * 0.05**2  # the 0.1 mm band along the square's sides alone


@pytest.mark.parametrize("fill, area", [
    ("(fill yes)", FILLED), ("(fill solid)", FILLED), ("", FILLED),  # with no flag a polygon is filled (legacy)
    ("(fill no)", STROKE), ("(fill none)", STROKE),
], ids=["yes", "solid", "absent", "no", "none"])
def test_a_custom_pad_polygon_follows_its_fill_flag(mini_board, fill, area):
    # the square's top side runs through the pad's centre, so the 0.1 mm anchor lies inside the stroke either way
    square = f"(gr_poly (pts (xy -1 0) (xy 1 0) (xy 1 2) (xy -1 2)) (width 0.1) {fill})"
    pad = mini_board(custom_pad(square, "circle", size=0.1)).pads("U9.1")[0]
    assert pad.polygon.area == pytest.approx(area, rel=2e-3)


# --- footprints that share a reference ----------------------------------------------------------------


def footprint_ref(ref, uuid, at="0 0"):
    """A footprint called `ref` with one pad, whose uuid is the footprint's plus "p"."""
    return (f'(footprint "Lib:Part" (layer "F.Cu") (uuid "{uuid}") (at {at}) (property "Reference" "{ref}") '
            f'(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (uuid "{uuid}p")))')


def test_footprints_that_share_a_reference_are_all_kept(mini_board):
    b = mini_board(footprint_ref("REF**", "a") + footprint_ref("REF**", "b", at="5 0"))
    assert [(key, fp.ref, fp.uuid) for key, fp in b.footprints.items()] == [
        ("REF**", "REF**", "a"), ("REF**#2", "REF**#2", "b")]  # the first keeps its reference
    assert [p.uuid for p in b.pads("REF**.1")] == ["ap"]
    (second,) = b.pads("REF**#2.1")  # its pad carries the new reference
    assert (second.uuid, second.ref, second.name) == ("bp", "REF**#2", "REF**#2.1")
    assert b.warnings.count(("W_DUPLICATE_REF", {"refs": "REF**"})) == 1


def test_copies_are_numbered_in_file_order_and_reported_once(mini_board):
    refs = ["U1", "REF**", "U1", "REF**", "U1", "C1"]
    b = mini_board("".join(footprint_ref(ref, f"f{i}") for i, ref in enumerate(refs)))
    assert list(b.footprints) == ["U1", "REF**", "U1#2", "REF**#2", "U1#3", "C1"]
    assert [w for w in b.warnings if w[0] == "W_DUPLICATE_REF"] == [("W_DUPLICATE_REF", {"refs": "REF**, U1"})]


def test_a_copy_never_takes_the_name_of_another_footprint(mini_board):
    b = mini_board(footprint_ref("U1", "a") + footprint_ref("U1#2", "b") + footprint_ref("U1", "c"))
    assert {key: fp.uuid for key, fp in b.footprints.items()} == {"U1": "a", "U1#2": "b", "U1#3": "c"}
    assert len([w for w in b.warnings if w[0] == "W_DUPLICATE_REF"]) == 1


def test_distinct_references_raise_no_duplicate_warning(mini_board):
    b = mini_board(footprint_ref("U1", "a") + footprint_ref("U2", "b"))
    assert list(b.footprints) == ["U1", "U2"] and "W_DUPLICATE_REF" not in [code for code, _ in b.warnings]
