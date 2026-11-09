# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path

import pytest
import shapely
from shapely.geometry import Point, box

from kicad_rf_studio.core.geometry.region import coarse_cell
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.kicad.board import CopperArea, Footprint, Pad, Via
from kicad_rf_studio.core.kicad.tracer import antenna_kind
from kicad_rf_studio.core.review.planes import Ref, plane_map, plane_nets
from kicad_rf_studio.core.review.rules import exclusions, groups, r1
from kicad_rf_studio.core.review.tags import tag

FIX = Path(__file__).parent / "fixtures"
L5 = coarse_cell(5e9, 4.5)  # 1.4132 mm: λ/20 at the default f_max and εr 4.5


def setup(name, edit=lambda b: None, flags=(), connectors=None):
    b = load_board(FIX / f"{name}.kicad_pcb")
    edit(b)
    c = classify(b, None if connectors is None else {"connectors": connectors})
    pm = plane_map(b, c, zstack(b.stackup, b.copper_layers))
    tags, _ = tag(b, c, plane_nets(b, c), flags)
    return b, c, pm, tags, groups(b, pm, tags, exclusions(b, c))[0]


def test_r1_fires_on_each_usb_line_over_in1s_slot_at_exactly_1_mm():  # design 5.14 R1 positive; risk 6
    b, c, pm, tags, gs = setup("usb2_hs_gap")
    found = r1(b, pm, gs, L5)
    assert sorted((f.net, f.layer, f.ref, f.measured["run_mm"], f.measured["extent_mm"]) for f in found) == [
        ("USB_D+", "F.Cu", Ref("In1.Cu", "GND", 0.2, None), 1.0, 6.0),
        ("USB_D-", "F.Cu", Ref("In1.Cu", "GND", 0.2, None), 1.0, 6.0)]
    assert {(f.code, f.limit, f.measured["l_mm"]) for f in found} == {("W_EMC_GAP_CROSSING", 1.0, 1.413)}
    assert all(len(set(ids)) == len(ids) for f in found for ids in f.kiids.values())  # one KIID per zone
    b, c, pm, tags, gs = setup("usb2_hs")
    assert r1(b, pm, gs, L5) == []  # design 5.14 R1 negative


def test_r1_fires_on_a_void_and_looks_through_a_cut_out_to_ground_below():  # design 5.2 R1, 5.14
    b, c, pm, tags, gs = setup("emc_review")
    (f,) = r1(b, pm, gs, L5)  # CLK_LOOK has GND under its cut-out; CLK_MID's antipads are 0.45 mm runs
    assert (f.net, f.ref, f.measured["run_mm"], f.measured["extent_mm"]) == (
        "CLK_GAP", Ref("In1.Cu", "GND", 0.2, None), 6.0, 10.0)


def test_r1_counts_another_nets_island_on_the_reference_layer_as_a_void():  # design 5.2 R1: a split
    island = box(111.0, -103.0, 114.0, -97.0)

    def split(b):
        b.areas = [replace(a, polygon=a.polygon.difference(island)) if a.layer == "In1.Cu" else a for a in b.areas]
        b.areas.append(CopperArea("In1.Cu", "+3V3", island, "zone", "s"))

    b, c, pm, tags, gs = setup("usb2_hs", split)
    assert sorted((f.net, f.ref.net, f.measured["run_mm"], f.measured["extent_mm"]) for f in r1(b, pm, gs, L5)) == [
        ("USB_D+", "GND", 3.0, 6.0), ("USB_D-", "GND", 3.0, 6.0)]


def test_a_lone_holes_void_is_its_antipad_and_any_other_void_counts():  # design 5.2 R1; D-2
    hole = Point(112.0, -100.475).buffer(0.8)  # 0.2 mm off USB_D+, 0.75 mm off USB_D- (a 0.56 mm chord)

    def holed(b):
        b.areas = [replace(a, polygon=a.polygon.difference(hole)) if a.layer == "In1.Cu" else a for a in b.areas]

    b, c, pm, tags, gs = setup("usb2_hs", holed)
    (f,) = r1(b, pm, gs, L5)
    assert f.net == "USB_D+" and 1.5 < f.measured["run_mm"] < 1.6
    b.vias.append(Via((112.0, -100.475), 0.6, 0.3, ("F.Cu", "B.Cu"), "AUX", "v"))  # diameter/2 + 0.6 = 0.9 >= 0.8
    assert r1(b, pm, gs, L5) == []  # its drill/2 + 0.6 = 0.75 would not reach the hole's edge
    b.vias.pop()
    at = (112.0, -100.475)
    pad = Pad("X1", "1", "p", "AUX", "thru_hole", b.copper_layers, ("F", "B"), at, Point(at).buffer(0.3), None, at, 0.3)
    b.footprints["X1"] = Footprint("X1", "", None, "", "f", "F.Cu", at, 0.0, False, (pad,), None)
    assert r1(b, pm, gs, L5) == []  # D-2: its copper's 0.3 + 0.6 = 0.9 >= 0.8; its drill/2 + 0.6 = 0.75 would not


def test_exclusions_hold_connectors_keepout_footprints_and_printed_antennas():  # design 5.1; A4
    b = load_board(FIX / "lpf915.kicad_pcb")
    hulls = exclusions(b, classify(b))  # J1, a U.FL with a keep-out, and J2, the edge SMA
    assert len(hulls) == 2 and all(any(h.covers(Point(p.center)) for h in hulls)
                                   for ref in ("J1", "J2") for p in b.footprints[ref].pads if p.layers)
    b.footprints["C4"] = replace(b.footprints["C4"], keepout=True)
    assert len(exclusions(b, classify(b))) == 3
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    graphics = shapely.union_all([a.polygon for a in b.areas if a.ref == "AE1"])
    assert antenna_kind(b, "AE1") == "printed" and [h.covers(graphics) for h in exclusions(b, classify(b))] == [True]
    b, c, pm, tags, gs = setup("usb2_hs_gap")
    kept = groups(b, pm, tags, [Point(116.5, -100.0).buffer(0.1)])[0]  # grown by 3h = 0.6 mm, it spans the slot
    assert r1(b, pm, kept, L5) == []


# --- beyond the brief's tests ----------------------------------------------------------------------------------------


def test_a_skipped_layer_as_near_as_the_reference_leaves_a_track_out_and_a_track_with_no_plane_names_its_net():  # AR-5
    b, c, pm, tags, gs = setup("usb2_hs")

    def grouped(skipped, planes=pm.planes):
        found, lost = groups(b, replace(pm, skipped=skipped, planes=planes), tags, exclusions(b, c))
        return len(found), lost

    # the USB pair and its MCU side on F.Cu reference In1.Cu at h 0.2: the track's own layer and In2.Cu, 1.24 mm
    # away, leave them in
    assert [grouped(s) for s in ((), ("F.Cu",), ("In2.Cu",), ("In1.Cu",))] == [(4, []), (4, []), (4, []), (0, [])]
    assert grouped((), {}) == (0, ["MCU_D+", "MCU_D-", "USB_D+", "USB_D-"])
    assert grouped(("B.Cu",), {}) == (0, [])  # a skipped layer might have been their reference
