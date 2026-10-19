# SPDX-License-Identifier: GPL-3.0-or-later
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from shapely.ops import unary_union

from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.board import Track, Via
from kicad_rf_studio.core.kicad.sexpr import children, parse, repair
from kicad_rf_studio.core.messages import KrsError

FIX = Path(__file__).parent / "fixtures"


def codes(b): return [c for c, _ in b.warnings]


def test_lpf915_header():
    b = load_board(FIX / "lpf915.kicad_pcb")
    assert b.version >= 20241229 and b.thickness == pytest.approx(0.8)
    assert b.copper_layers == ("F.Cu", "B.Cu")
    assert {"GND", "VDD", "RF_A", "RF_B", "RF_C", "RF_OUT", "RF_SMA"} <= set(b.nets)


def test_coupon_copper():
    b = load_board(FIX / "coupon_gcpw.kicad_pcb")
    line = [t for t in b.tracks if t.net == "LINE"]
    assert line and all(t.width == pytest.approx(0.6) for t in line)
    assert len(b.vias) > 10 and {v.net for v in b.vias} == {"GND"}
    assert {a.layer for a in b.areas if a.net == "GND" and a.source == "zone"} == {"F.Cu", "B.Cu"}
    assert b.outline is not None and b.outline.area > 0


def test_track_polygons():
    seg = Track("F.Cu", "N", 0.2, (0, 0), (1, 0), None, "u")
    assert seg.polygon().area == pytest.approx(0.2 + math.pi * 0.01, rel=1e-3)
    arc = Track("F.Cu", "N", 0.1, (1, 0), (0, 1), (math.sqrt(0.5), math.sqrt(0.5)), "u")
    assert arc.polygon().area == pytest.approx(0.1 * math.pi / 2 + math.pi * 0.0025, rel=2e-3)


def test_kicad10_net_syntax(mini_board):
    k9 = '(net 1 "SIG") (segment (start 0 0) (end 1 0) (width 0.2) (layer "F.Cu") (net 1) (uuid "a"))'
    k10 = '(segment (start 0 0) (end 1 0) (width 0.2) (layer "F.Cu") (net "SIG") (uuid "a"))'
    assert mini_board(k9).tracks[0].net == "SIG"
    b10 = mini_board(k10, version=20250901)
    assert b10.tracks[0].net == "SIG" and "W_BOARD_NEWER" in codes(b10)


def test_repair_warning(mini_board):
    assert ("W_REPAIRED_FILTER_RATIO", {"count": 1}) in mini_board("(teardrops (curved_edges no)filter_ratio 0.9))").warnings


def test_unfilled_zone_warns(mini_board):
    zone = ('(zone (net 0) (net_name "") (layer "F.Cu") (uuid "z") '
            '(polygon (pts (xy 0 0) (xy 1 0) (xy 1 1))))')
    assert "W_ZONE_NOT_FILLED" in codes(mini_board(zone))


def test_missing_outline_warns(mini_board):
    b = mini_board("")
    assert b.outline is None and "W_NO_OUTLINE" in codes(b)


def test_old_version_refused(mini_board):
    with pytest.raises(KrsError) as e:
        mini_board("", version=20231120)
    assert e.value.code == "E_BOARD_VERSION"


# --- beyond the brief's eight tests ------------------------------------------------------------
# --- the file and its header ---------------------------------------------------------------------


def load_text(tmp_path, text):
    p = tmp_path / "x.kicad_pcb"
    p.write_text(text, encoding="utf-8")
    return load_board(p)


@pytest.mark.parametrize("text", ["(kicad_sch (version 20250114))", "()"])
def test_a_file_that_is_not_a_board_is_refused(tmp_path, text):
    p = tmp_path / "x.kicad_sch"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(KrsError) as e:
        load_board(p)
    assert e.value.code == "E_NOT_A_BOARD" and e.value.params == {"path": str(p)}
    assert str(e.value) == f"{p} is not a KiCad board file."


def test_version_messages_carry_the_version(mini_board):
    assert ("W_BOARD_NEWER", {"version": 20250901}) in mini_board(version=20250901).warnings
    assert "W_BOARD_NEWER" not in codes(mini_board(version=20241229))  # KiCad 9 itself is not newer
    with pytest.raises(KrsError) as e:
        mini_board(version=20231120)
    assert e.value.params == {"version": 20231120} and "20231120" in str(e.value)


def test_repair_warning_counts_every_fix(mini_board):
    twice = "(teardrops (curved_edges no)filter_ratio 0.9)) (teardrops (curved_edges no)filter_ratio 0.8))"
    assert ("W_REPAIRED_FILTER_RATIO", {"count": 2}) in mini_board(twice).warnings


def test_a_bare_board_gets_defaults(tmp_path):
    b = load_text(tmp_path, "(kicad_pcb (version 20241229))")
    assert b.thickness == 1.6  # what KiCad assumes when the file does not say
    assert b.pad_to_mask_clearance == 0 and b.solder_mask_min_width == 0
    assert b.copper_layers == () and b.nets == () and b.footprints == {} and b.stackup is None
    assert (b.tracks, b.vias, b.areas) == ([], [], []) and b.mask_graphics == {"F": [], "B": []}
    assert codes(b) == ["W_NO_OUTLINE"]


def test_setup_values_are_read(tmp_path):
    b = load_text(tmp_path, "(kicad_pcb (version 20241229) "
                            "(setup (pad_to_mask_clearance 0.05) (solder_mask_min_width 0.1)))")
    assert b.pad_to_mask_clearance == 0.05 and b.solder_mask_min_width == 0.1


def test_copper_layers_run_top_to_bottom(tmp_path):
    layers = ('(0 "F.Cu" signal) (22 "In10.Cu" signal) (6 "In2.Cu" signal) (2 "B.Cu" signal) '
              '(4 "In1.Cu" signal) (25 "Edge.Cuts" user)')
    b = load_text(tmp_path, f"(kicad_pcb (version 20241229) (layers {layers}))")
    assert b.copper_layers == ("F.Cu", "In1.Cu", "In2.Cu", "In10.Cu", "B.Cu")  # In10 after In2: by number


# --- nets ----------------------------------------------------------------------------------------


def test_nets_follow_the_header_table_without_the_empty_net(mini_board):
    assert mini_board('(net 1 "SIG") (net 2 "GND")').nets == ("SIG", "GND")


def test_nets_of_a_board_without_a_table_come_from_its_items(mini_board):
    k10 = ('(segment (start 0 0) (end 1 0) (width 0.2) (layer "F.Cu") (net "SIG") (uuid "a")) '
           '(via (at 1 1) (size 0.6) (drill 0.3) (net "GND") (uuid "b")) '
           '(footprint "X:Y" (layer "F.Cu") (at 0 0) '
           '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net "PAD_ONLY") (uuid "p")) '
           '(pad "2" smd rect (at 2 0) (size 1 1) (layers "F.Cu") (net "SIG") (uuid "q")))')
    assert mini_board(k10, version=20250901).nets == ("SIG", "GND", "PAD_ONLY")


def test_an_unknown_net_code_is_no_net(mini_board):
    b = mini_board('(segment (start 0 0) (end 1 0) (width 0.2) (layer "F.Cu") (net 7) (uuid "a"))')
    assert b.tracks[0].net == ""


# --- tracks, vias and pads -----------------------------------------------------------------------


def test_tracks_and_vias_are_read_with_y_flipped(mini_board):
    body = ('(net 1 "SIG") '
            '(via (at 5 -3) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 1) (uuid "v1")) '
            '(via blind (at 1 0) (size 0.5) (drill 0.2) (layers "F.Cu" "In1.Cu") (net 1) (uuid "v2")) '
            '(via (at 2 2) (size 0.6) (drill 0.3) (uuid "v3")) '
            '(segment (start 0 0) (end 4 2) (width 0.2) (layer "F.Cu") (net 1) (uuid "s1")) '
            '(arc (start 1 0) (mid 2 1) (end 3 0) (width 0.2) (layer "B.Cu") (net 1) (uuid "a1"))')
    b = mini_board(body)
    assert b.vias[0] == Via((5.0, 3.0), 0.6, 0.3, ("F.Cu", "B.Cu"), "SIG", "v1")
    assert b.vias[1].layers == ("F.Cu", "In1.Cu")  # a blind via keeps its layers
    assert b.vias[2].layers == ("F.Cu", "B.Cu") and b.vias[2].net == ""  # the default
    assert b.tracks[0] == Track("F.Cu", "SIG", 0.2, (0.0, 0.0), (4.0, -2.0), None, "s1")
    assert str(b.tracks[0].start) == "(0.0, 0.0)"  # never -0.0
    assert b.tracks[1].mid == (2.0, -1.0) and b.tracks[1].layer == "B.Cu"


def test_pads_are_found_by_ref_and_number(mini_board):
    def pad(ref, n):  # stands in for Task 7's Pad
        return SimpleNamespace(name=f"{ref}.{n}")

    b = mini_board()
    j1 = SimpleNamespace(pads=(pad("J1", 1), pad("J1", 2), pad("J1", 2)))
    b.footprints = {"J1": j1, "U1": SimpleNamespace(pads=(pad("U1", 2),))}
    assert b.pads("J1.2") == [j1.pads[1], j1.pads[2]]  # pads that share a number are all returned
    assert b.pads("J1.3") == [] and b.pads("J2.1") == []


# --- zones ---------------------------------------------------------------------------------------

SQUARE = "(pts (xy 0 0) (xy 2 0) (xy 2 1) (xy 0 1))"


def zone(layer='(layer "F.Cu")', net='(net 0) (net_name "")', uuid="z", fill="", extra=""):
    return f'(zone {net} {layer} (uuid "{uuid}") {extra} (polygon {SQUARE}) {fill})'


def fill(layer="F.Cu", pts=SQUARE):
    return f'(filled_polygon (layer "{layer}") {pts})'


def test_zone_fill_becomes_a_copper_area(mini_board):
    b = mini_board('(net 1 "SIG") ' + zone(net='(net 1) (net_name "SIG")', fill=fill()))
    (a,) = b.areas
    assert (a.layer, a.net, a.source, a.uuid) == ("F.Cu", "SIG", "zone", "z")
    assert a.polygon.bounds == (0, -1, 2, 0) and a.polygon.area == pytest.approx(2)  # y flipped


def test_every_fill_polygon_of_a_zone_is_an_area(mini_board):
    two = fill() + fill(pts="(pts (xy 5 0) (xy 6 0) (xy 6 1))")
    assert [a.polygon.area for a in mini_board(zone(fill=two)).areas] == pytest.approx([2, 0.5])


def test_unfilled_zone_warning_names_the_zone_and_layer(mini_board):
    assert ("W_ZONE_NOT_FILLED", {"uuid": "z", "layer": "F.Cu"}) in mini_board(zone()).warnings


def test_a_zone_on_two_layers_is_filled_or_warned_per_layer(mini_board):
    both = '(layers "F.Cu" "B.Cu")'
    b = mini_board(zone(layer=both, fill=fill("F.Cu") + fill("B.Cu")))
    assert [a.layer for a in b.areas] == ["F.Cu", "B.Cu"] and "W_ZONE_NOT_FILLED" not in codes(b)
    warned = [w for w in mini_board(zone(layer=both)).warnings if w[0] == "W_ZONE_NOT_FILLED"]
    assert warned == [("W_ZONE_NOT_FILLED", {"uuid": "z", "layer": "F.Cu"}),
                      ("W_ZONE_NOT_FILLED", {"uuid": "z", "layer": "B.Cu"})]


@pytest.mark.parametrize("fills", ["", fill()], ids=["unfilled", "filled"])
def test_rule_areas_are_not_copper(mini_board, fills):
    keepout = "(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed))"
    b = mini_board(zone(fill=fills, extra=keepout))
    assert b.areas == [] and codes(b) == ["W_NO_OUTLINE"]


def test_zone_fills_on_mask_layers_open_the_mask(mini_board):
    b = mini_board(zone('(layer "F.Mask")', fill=fill("F.Mask")) + zone('(layer "B.Mask")', fill=fill("B.Mask"))
                   + zone('(layer "F.SilkS")', fill=fill("F.SilkS")) + zone('(layer "F.Mask")', uuid="empty"))
    assert b.areas == []  # not copper, and the silkscreen fill is dropped
    assert [p.area for p in b.mask_graphics["F"]] == pytest.approx([2])
    assert [p.area for p in b.mask_graphics["B"]] == pytest.approx([2])
    assert codes(b) == ["W_NO_OUTLINE"]  # an unfilled zone outside the copper is no concern


def test_a_fill_with_a_hole_is_read_as_a_polygon_with_a_hole(mini_board):
    # KiCad writes the hole of a fill as a zero-width slit from the outline into the hole and back
    ring = ("(pts (xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10) (xy 0 5) (xy 4 5) (xy 4 6) (xy 6 6) (xy 6 4) "
            "(xy 4 4) (xy 4 5) (xy 0 5))")
    (a,) = mini_board(zone(fill=fill(pts=ring))).areas
    assert a.polygon.is_valid and len(a.polygon.interiors) == 1 and a.polygon.area == pytest.approx(96)


# --- graphics ------------------------------------------------------------------------------------


def graphic(kind, geometry, layer="F.Cu", width=0, fill=None, net="", uuid="g"):
    f = "" if fill is None else f"(fill {fill}) "
    return f'({kind} {geometry} (stroke (width {width}) (type default)) {f}(layer "{layer}") {net} (uuid "{uuid}"))'


RECT = "(start 0 0) (end 2 1)"


def test_a_filled_copper_graphic_is_a_copper_area(mini_board):
    b = mini_board('(net 1 "SIG") ' + graphic("gr_rect", RECT, fill="yes", net="(net 1)"))
    (a,) = b.areas
    assert (a.layer, a.net, a.source, a.uuid) == ("F.Cu", "SIG", "graphic", "g")
    assert a.polygon.bounds == (0, -1, 2, 0) and a.polygon.area == pytest.approx(2)
    assert codes(b) == ["W_NO_OUTLINE"]


def test_a_filled_graphic_also_has_its_stroke_around_it(mini_board):
    # KiCad draws the outline of a filled shape too, so 0.2 mm of stroke adds 0.1 mm all around
    (a,) = mini_board(graphic("gr_rect", RECT, width=0.2, fill="yes")).areas
    assert a.polygon.area == pytest.approx(2.2 * 1.2 - (4 - math.pi) * 0.1**2, rel=1e-3)


def test_an_unfilled_graphic_is_only_its_stroke(mini_board):
    (a,) = mini_board(graphic("gr_rect", RECT, width=0.2, fill="no")).areas
    assert len(a.polygon.interiors) == 1
    assert a.polygon.area == pytest.approx(4 * 0.1 * (2 + 1) - (4 - math.pi) * 0.1**2, rel=1e-3)


@pytest.mark.parametrize("kind, geometry, fill, width, area", [
    ("gr_line", "(start 0 0) (end 2 0)", None, 0.4, 2 * 0.4 + math.pi * 0.2**2),
    ("gr_arc", "(start 1 0) (mid 0.7071067811865476 0.7071067811865476) (end 0 1)", None, 0.4,
     0.4 * math.pi / 2 + math.pi * 0.2**2),
    ("gr_circle", "(center 5 5) (end 6 5)", "yes", 0, math.pi),
    ("gr_circle", "(center 5 5) (end 6 5)", "no", 0.4, math.pi * (1.2**2 - 0.8**2)),
    ("gr_poly", "(pts (xy 0 0) (xy 4 0) (xy 0 3))", "yes", 0, 6),
    # an arc inside a polygon stands for its polyline: this half disc is the arc and the chord closing it
    ("gr_poly", "(pts (arc (start 0 1) (mid 1 0) (end 0 -1)))", "yes", 0, math.pi / 2),
], ids=["line", "arc", "disc", "ring", "triangle", "half disc"])
def test_every_graphic_kind_covers_the_copper_it_draws(mini_board, kind, geometry, fill, width, area):
    (a,) = mini_board(graphic(kind, geometry, width=width, fill=fill)).areas
    assert a.polygon.area == pytest.approx(area, rel=2e-3)


def test_copper_graphic_without_net_warns(mini_board):
    b = mini_board(graphic("gr_rect", RECT, fill="yes"))
    assert b.areas[0].net == "" and ("W_NETLESS_COPPER", {"uuid": "g", "layer": "F.Cu"}) in b.warnings


def test_graphics_on_mask_layers_open_the_mask(mini_board):
    b = mini_board(graphic("gr_rect", RECT, "F.Mask", fill="yes") + graphic("gr_rect", RECT, "B.Mask", fill="yes"))
    assert b.areas == [] and codes(b) == ["W_NO_OUTLINE"]  # no net is expected on a mask opening
    assert [p.area for p in b.mask_graphics["F"]] == pytest.approx([2])
    assert [p.area for p in b.mask_graphics["B"]] == pytest.approx([2])


def test_graphics_on_other_layers_are_left_alone(mini_board):
    drawings = (graphic("gr_rect", RECT, "F.SilkS", fill="yes")
                + graphic("gr_line", "(start 0 0) (end 1 1)", "Dwgs.User")
                + graphic("gr_poly", "(pts (xy 0 0) (xy 1 1))", "Cmts.User", fill="yes"))  # too short for a polygon
    b = mini_board(drawings)
    assert (b.areas, b.mask_graphics, codes(b)) == ([], {"F": [], "B": []}, ["W_NO_OUTLINE"])


# --- outline -------------------------------------------------------------------------------------


def edge(kind, geometry):
    return graphic(kind, geometry, "Edge.Cuts", 0.05, "no" if kind in ("gr_rect", "gr_circle", "gr_poly") else None)


BOARD = edge("gr_rect", "(start 0 0) (end 10 6)")


def rounded_board():
    """10 x 6, corner radius 1: four lines joined by four arcs."""
    s = math.sqrt(0.5)
    parts = [("gr_line", "(start 1 0) (end 9 0)"), ("gr_line", "(start 10 1) (end 10 5)"),
             ("gr_line", "(start 9 6) (end 1 6)"), ("gr_line", "(start 0 5) (end 0 1)"),
             ("gr_arc", f"(start 9 0) (mid {9 + s} {1 - s}) (end 10 1)"),
             ("gr_arc", f"(start 10 5) (mid {9 + s} {5 + s}) (end 9 6)"),
             ("gr_arc", f"(start 1 6) (mid {1 - s} {5 + s}) (end 0 5)"),
             ("gr_arc", f"(start 0 1) (mid {1 - s} {1 - s}) (end 1 0)")]
    return " ".join(edge(kind, geometry) for kind, geometry in parts)


def test_outline_closes_from_lines_and_arcs(mini_board):
    b = mini_board(rounded_board())
    assert b.outline.area == pytest.approx(60 - (4 - math.pi), rel=1e-3) and not b.outline.interiors
    assert codes(b) == []


def test_a_closed_shape_inside_the_outline_is_a_cutout(mini_board):
    b = mini_board(BOARD + edge("gr_circle", "(center 5 3) (end 6 3)"))
    assert len(b.outline.interiors) == 1 and b.outline.area == pytest.approx(60 - math.pi, rel=2e-3)


def test_the_outline_is_the_outermost_loop_even_when_its_cutout_is_the_larger_face(mini_board):
    b = mini_board(edge("gr_rect", "(start 0 0) (end 10 10)") + edge("gr_rect", "(start 0.5 0.5) (end 9.5 9.5)"))
    assert b.outline.area == pytest.approx(19) and len(b.outline.interiors) == 1


@pytest.mark.parametrize("body", [
    BOARD + BOARD,  # the outline drawn twice
    (edge("gr_line", "(start 0 0) (end 10 0)") + edge("gr_line", "(start 10 0) (end 10 6)")
     + edge("gr_line", "(start 10 6) (end 0 6)") + edge("gr_line", "(start 0 6) (end 0 -2)")),  # a line overshoots
], ids=["doubled", "overshoot"])
def test_untidy_outline_lines_still_close_the_board(mini_board, body):
    assert mini_board(body).outline.area == pytest.approx(60)


SIDES = ("(start 0 0) (end 10 0)", "(start 10 0) (end 10 6)", "(start 10 6) (end 0 6)")


@pytest.mark.parametrize("last_side", [
    "(start 0 6) (end 0 0.000001)",  # stops 1 nm short of the corner
    "(start 0 6) (end 0.000001 0.000001)",  # ends 1 nm inside it
    "(start 0 6) (end -0.000001 -0.000001)",  # ends 1 nm outside it
], ids=["short", "inside", "outside"])
def test_a_corner_that_misses_by_a_nanometre_still_closes(mini_board, last_side):
    b = mini_board(" ".join(edge("gr_line", g) for g in (*SIDES, last_side)))
    assert b.outline is not None and b.outline.area == pytest.approx(60, rel=1e-6)
    assert "W_NO_OUTLINE" not in codes(b)


def test_an_arc_that_stops_a_nanometre_short_still_closes(mini_board):
    body = rounded_board()
    assert body.count("(end 10 1)") == 1  # the end of the first arc, where the line from (10, 1) takes over
    b = mini_board(body.replace("(end 10 1)", "(end 10.000001 1)"))
    assert b.outline is not None and b.outline.area == pytest.approx(60 - (4 - math.pi), rel=1e-3)


def test_an_open_outline_is_no_outline(mini_board):
    b = mini_board(" ".join(edge("gr_line", g) for g in SIDES))
    assert b.outline is None and "W_NO_OUTLINE" in codes(b)


@pytest.mark.parametrize("kind, geometry, area", [
    ("gr_circle", "(center 0 0) (end 5 0)", 25 * math.pi),
    ("gr_poly", "(pts (xy 0 0) (xy 4 0) (xy 0 3))", 6),
], ids=["round board", "polygon board"])
def test_any_closed_edge_shape_can_be_the_outline(mini_board, kind, geometry, area):
    assert mini_board(edge(kind, geometry)).outline.area == pytest.approx(area, rel=2e-3)


# --- the fixture boards --------------------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(FIX.glob("*.kicad_pcb")), ids=lambda p: p.stem)
def test_fixture_loads_whole_and_without_warnings(path):
    b = load_board(path)
    root = parse(repair(path.read_text(encoding="utf-8"))[0])
    assert b.warnings == [] and b.outline is not None and b.outline.is_valid
    assert len(b.tracks) == len(children(root, "segment")) + len(children(root, "arc"))
    assert len(b.vias) == len(children(root, "via"))
    assert len(b.areas) == sum(len(children(z, "filled_polygon")) for z in children(root, "zone"))
    assert all(a.polygon.is_valid and not a.polygon.is_empty for a in b.areas)


def test_outline_of_a_rectangle_is_flipped_like_everything_else():
    assert load_board(FIX / "coupon_ms.kicad_pcb").outline.bounds == (99, -105, 121, -95)


def test_the_mask_free_coupon_has_one_opening_over_the_board():
    assert [p.bounds for p in load_board(FIX / "coupon_ms.kicad_pcb").mask_graphics["F"]] == [(99, -105, 121, -95)]
    assert load_board(FIX / "coupon_ms_masked.kicad_pcb").mask_graphics == {"F": [], "B": []}


@pytest.mark.parametrize("name, net", [("coupon_gcpw", "LINE"), ("coupon_gcpw_45", "LINE"),
                                       ("coupon_gcpw_arc", "LINE"), ("lpf915", "RF_A")])
def test_tracks_and_zone_fills_agree_in_position_and_shape(name, net):
    """pcbnew filled these zones 0.15 mm (and its own 0.5 um margin) away from the trace, arc included."""
    b = load_board(FIX / f"{name}.kicad_pcb")
    trace = unary_union([t.polygon() for t in b.tracks if t.net == net])
    gap = min(a.polygon.distance(trace) for a in b.areas if a.layer == "F.Cu" and a.net == "GND")
    assert gap == pytest.approx(0.1505, abs=0.001)
