# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path

import math

from shapely.geometry import LineString, box

from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.kicad.board import CopperArea, Track
from kicad_rf_studio.core.kicad.tracer import is_power
from kicad_rf_studio.core.review.planes import (DOTTED_POWER, PlaneMap, Ref, centre_line, cover, plane_map,
                                                plane_nets, reference)

FIX = Path(__file__).parent / "fixtures"
LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def mapped(name, edit=lambda b: None):
    b = load_board(FIX / f"{name}.kicad_pcb")
    edit(b)
    c = classify(b)
    return b, c, plane_map(b, c, zstack(b.stackup, b.copper_layers))


def line_of(b, net, layer):
    return centre_line(next(t for t in b.tracks if (t.net, t.layer) == (net, layer)))


def dotted(b):  # usb2_hs's +3V3 named as KiCad's +3.3V power symbol names it
    b.areas = [replace(a, net="+3.3V") if a.net == "+3V3" else a for a in b.areas]
    b.nets = tuple("+3.3V" if n == "+3V3" else n for n in b.nets)


def test_the_plane_map_is_each_ground_or_power_nets_zone_fills_by_layer():  # design 5.1
    b, _, pm = mapped("usb2_hs_gap")
    assert {(layer, net) for layer, nets in pm.planes.items() for net in nets} == {("In1.Cu", "GND"),
                                                                                   ("In2.Cu", "+3V3")}
    gnd = pm.planes["In1.Cu"]["GND"]
    assert gnd.covers(LineString([(110, -100), (115, -100)])) and not gnd.intersects(LineString([(116.2, -100),
                                                                                                 (116.8, -100)]))
    assert (pm.layers, pm.skipped, pm.gnd) == (LAYERS, (), frozenset({"GND"}))
    assert [pm.h[k] for k in (("F.Cu", "In1.Cu"), ("F.Cu", "In2.Cu"), ("F.Cu", "B.Cu"), ("B.Cu", "In1.Cu"))] == [
        0.2, 1.24, 1.44, 1.24]  # dielectric only, summed over the slabs between


def test_a_dotted_power_name_is_a_plane_net_though_tracer_power_misses_it():  # design 5.1; f4
    assert DOTTED_POWER.fullmatch("+3.3V") and DOTTED_POWER.fullmatch("+1.8V") and not is_power("+3.3V")
    b, c, pm = mapped("usb2_hs", dotted)
    assert "+3.3V" in plane_nets(b, c) and "+3.3V" not in c.power and set(pm.planes["In2.Cu"]) == {"+3.3V"}


def test_an_unfilled_or_hatched_zones_layer_is_skipped():  # design 5.1
    def warned(b):
        b.warnings = [("W_ZONE_NOT_FILLED", {"uuid": "z", "layer": "In2.Cu"}),
                      ("W_COPPER_DROPPED", {"kind": "T_HATCHED_ZONE", "layer": "In1.Cu", "uuid": "y"}),
                      ("W_COPPER_DROPPED", {"kind": "gr_text", "layer": "B.Cu", "uuid": "t"})]

    assert mapped("usb2_hs", warned)[2].skipped == ("In1.Cu", "In2.Cu")  # top to bottom; text is not a zone


def test_the_reference_is_the_nearest_layer_whose_planes_touch_the_centre_line():  # design 5.2
    b, _, pm = mapped("qspi_clk")
    assert reference(pm, "F.Cu", line_of(b, "FLASH_CLK", "F.Cu")) == Ref("In1.Cu", "GND", 0.2, None)
    assert reference(pm, "B.Cu", line_of(b, "FLASH_CLK", "B.Cu")) == Ref("In2.Cu", "+3V3", 0.2, None)
    own = PlaneMap({"F.Cu": {"GND": box(0, -1, 10, 1)}}, frozenset({"GND"}), LAYERS, (), pm.h)
    assert reference(own, "F.Cu", LineString([(1, 0), (9, 0)])) is None  # never the track's own layer


def test_a_stripline_takes_the_nearer_plane_and_the_span_between_both():  # design 5.2
    b, _, pm = mapped("qspi_clk", lambda b: b.areas.append(CopperArea("B.Cu", "GND", b.outline, "zone", "z")))
    assert reference(pm, "In2.Cu", line_of(b, "FLASH_CLK", "B.Cu")) == Ref("B.Cu", "GND", 0.2, 1.24)


def test_the_majority_net_wins_then_ties_go_below_then_to_ground_then_to_the_first_name():  # design 5.2
    h = {(x, y): 0.2 for x in LAYERS for y in LAYERS if x != y}
    line, plate = LineString([(1, 0), (9, 0)]), box(0, -1, 10, 1)
    pm = PlaneMap({"F.Cu": {"VDD": plate}, "B.Cu": {"VCC": plate}}, frozenset({"GND"}), LAYERS, (), h)
    assert reference(pm, "In1.Cu", line) == Ref("B.Cu", "VCC", 0.2, 0.4)

    def net_of(halves):
        return reference(PlaneMap({"In2.Cu": halves}, frozenset({"GND"}), LAYERS, (), h), "In1.Cu", line).net

    assert net_of({"VDD": box(0, -1, 7, 1), "GND": box(7, -1, 10, 1)}) == "VDD"  # 6 mm of VDD against 2 of GND
    assert net_of({"VDD": box(0, -1, 5, 1), "GND": box(5, -1, 10, 1)}) == "GND"
    assert net_of({"VDD": box(0, -1, 5, 1), "AVDD": box(5, -1, 10, 1)}) == "AVDD"


def test_an_arc_tracks_centre_line_is_its_arc_as_a_polyline():  # design 5.2 (plan 1's close)
    line = centre_line(Track("F.Cu", "CLK", 0.2, (0.0, 0.0), (2.0, 0.0), (1.0, 1.0), "a"))  # a half circle, radius 1
    assert (line.coords[0], line.coords[-1]) == ((0.0, 0.0), (2.0, 0.0))
    assert abs(line.length - math.pi) < 1e-2


def test_a_net_with_no_planes_covers_nothing():  # design 5.2 (plan 1's close)
    _, _, pm = mapped("usb2_hs")
    assert cover(pm, "NO_SUCH_NET").is_empty
