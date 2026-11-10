# SPDX-License-Identifier: GPL-3.0-or-later
import math
from dataclasses import replace
from pathlib import Path

import pytest
import shapely
from shapely.geometry import Point, box

from kicad_rf_studio.core.geometry.region import coarse_cell
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.kicad.board import CopperArea, Footprint, Pad, Track, Via
from kicad_rf_studio.core.kicad.tracer import antenna_kind
from kicad_rf_studio.core.review.planes import Ref, plane_map, plane_nets
from kicad_rf_studio.core.review.rules import exclusions, groups, r1, r2, r3, r4, return_share
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


def test_r3_fires_on_a_track_within_2h_of_the_outline_with_its_share_past_the_edge():  # design 5.2 R3, 5.14
    b, c, pm, tags, gs = setup("emc_review")
    (f,) = r3(b, gs, 2.0)
    assert (f.net, f.layer, f.ref, f.code, f.limit) == ("CLK_EDGE", "F.Cu", Ref("In1.Cu", "GND", 0.2, None),
                                                        "W_EMC_EDGE", 0.4)
    assert f.measured == {"d_mm": 0.35, "h_mm": 0.2, "k": 2.0, "share_pct": 16.5}
    b, c, pm, tags, gs = setup("usb2_hs")
    assert r3(b, gs, 2.0) == []  # the pair about 5 mm in


def test_r3_leaves_out_a_connectors_launch():  # design 5.14 R3 negative; 5.1's exclusions; D-3
    b, c, pm, tags, gs = setup("lpf915", flags=["RF_*"])
    assert r3(b, gs, 2.0) == r3(b, gs, 5.0) == []  # RF_SMA ends 2.24 mm in; J2's hull grown by 3h leaves it 5.7
    b, c, pm, tags, gs = setup("lpf915", flags=["RF_*"], connectors=[])
    assert [(f.net, f.measured["d_mm"]) for f in r3(b, gs, 5.0)] == [("RF_SMA", 2.24)]


def test_the_share_of_return_current_past_the_edge():  # design 5.2 R3: Johnson and Graham; r5
    assert round(100 * return_share(0.4, 0.2, None), 1) == 14.8  # microstrip at 2h
    assert round(100 * return_share(0.4, 0.2, 0.4), 1) == 2.7  # stripline at 2h, b = 2h
    assert return_share(0.0, 0.2, None) == pytest.approx(0.5)


def test_r2_fires_on_flash_clks_vias_from_in1s_ground_to_in2s_supply():  # design 5.14 R2 positive
    b, c, pm, tags, gs = setup("qspi_clk")
    found = r2(b, c, pm, tags, L5)
    assert [(f.net, f.layer, f.ref, f.params["to_layer"], f.params["to_net"], f.measured["return_mm"])
            for f in found] == [
        ("FLASH_CLK", "F.Cu", Ref("In1.Cu", "GND", 0.2, None), "In2.Cu", "+3V3", 2.262),
        ("FLASH_CLK", "F.Cu", Ref("In1.Cu", "GND", 0.2, None), "In2.Cu", "+3V3", 9.773)]
    assert {(f.code, f.limit, f.params["path"]) for f in found} == {("I_EMC_REF_CHANGE", 2.0, "T_EMC_RETURN_CAP")}
    assert found[0].params["nearest"] == "2.262 mm"


def test_r2_is_silent_on_a_bridged_change_and_on_a_same_net_change_with_a_via_near():  # design 5.14 R2 negatives
    b, c, pm, tags, gs = setup("emc_review")
    assert r2(b, c, pm, tags, L5) == []  # C1's pads 0.890 mm from CLK_MID's via

    def ground_in2(b):
        b.areas = [replace(a, net="GND") if a.layer == "In2.Cu" else a for a in b.areas]

    b, c, pm, tags, gs = setup("qspi_clk", ground_in2)
    assert [(f.params["path"], f.measured["return_mm"]) for f in r2(b, c, pm, tags, L5)] == [
        ("T_EMC_RETURN_VIA", 3.444), ("T_EMC_RETURN_VIA", 7.879)]
    b.vias.append(Via((107.0, -98.99), 0.6, 0.3, ("F.Cu", "B.Cu"), "GND", "v"))  # 0.8 mm from the first
    assert [f.measured["return_mm"] for f in r2(b, c, pm, tags, L5)] == [7.879]


def frame(b, ref="SH1"):  # the shield's ring and its pad-covered stretches, longest first, as Step 3 takes them
    pads = shapely.union_all([p.polygon for p in b.footprints[ref].pads if b.footprints[ref].layer in p.layers])
    ring = pads.convex_hull.exterior
    return sorted(shapely.get_parts(shapely.line_merge(ring.intersection(pads.buffer(1e-6)))), key=lambda g: -g.length)


def gnd_vias(points, tag="s"):
    return [Via((p.x, p.y), 0.6, 0.3, ("F.Cu", "B.Cu"), "GND", f"{tag}{k}") for k, p in enumerate(points)]


def test_r4_fires_on_lpf915s_unstitched_frame_and_on_the_edge_only_when_asked():  # design 5.14 R4 positive; A7
    b, c, *_ = setup("lpf915")
    (f,) = r4(b, c, L5, False)
    assert (f.rule, f.code, f.net, f.layer, f.params["fence"], f.limit) == ("R4", "W_EMC_FENCE_PITCH", None, "F.Cu",
                                                                            "SH1", 1.413)
    assert f.measured == {"gap_mm": 47.2, "lambdas": 1.67}  # no GND via within 1 mm: the frame pads' whole cover
    assert f.kiids["footprints"] == [b.footprints["SH1"].uuid] and f.params["lambdas"] == "1.67"
    edge = [f for f in r4(b, c, L5, True) if f.params["fence"] == "T_EMC_BOARD_EDGE"]
    assert [(f.layer, f.measured["gap_mm"]) for f in edge] == [(None, 104.43)]  # the outline's whole length


def test_r4_is_silent_on_a_frame_stitched_every_0976_mm_around_its_corners():  # design 5.14 R4 negative; D-1
    b, c, *_ = setup("emc_review")
    assert r4(b, c, L5, False) == []


def test_r4_leaves_the_frames_openings_out_and_fires_on_a_missing_via():  # design 5.2 R4; A7; D-1
    b, c, *_ = setup("lpf915")
    parts = frame(b)
    vias = gnd_vias([p.interpolate(float(k)) for p in parts for k in range(int(p.length) + 1)])  # 1 mm, no opening
    b.vias += vias
    assert r4(b, c, L5, False) == []
    mid = int(parts[0].length) // 2  # the longest stretch's middle via
    b.vias.remove(vias[mid])
    (f,) = r4(b, c, L5, False)
    assert f.measured["gap_mm"] == 2.0 and sorted(f.kiids["vias"]) == sorted([vias[mid - 1].uuid, vias[mid + 1].uuid])


def test_r4_two_vias_side_by_side_leave_the_rest_of_the_frame_open():  # design 5.2 R4; D-1
    b, c, *_ = setup("lpf915")
    longest = frame(b)[0]
    b.vias += gnd_vias([longest.interpolate(0.0), longest.interpolate(1.0)])
    (f,) = r4(b, c, L5, False)
    assert f.measured["gap_mm"] > 40


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


def test_r3_merges_the_flagged_entries_that_meet_and_places_a_part_its_band_misses():  # AR-4
    def clk_edge(*ends, outline=None):  # CLK_EDGE as these 0.5 mm tracks, on this outline
        def edit(b):
            b.tracks = [t for t in b.tracks if t.net != "CLK_EDGE"] + [
                Track("F.Cu", "CLK_EDGE", 0.5, s, e, None, str(i)) for i, (s, e) in enumerate(ends)]
            if outline is not None:
                b.outline = outline
        return edit

    # a T whose three tracks run 0.35 mm from the top edge where they meet, and a track apart
    tee = ((103, -100.6), (113, -100.6)), ((113, -100.6), (123, -100.6)), ((110, -100.7), (113, -100.6))
    b, c, pm, tags, gs = setup("emc_review", clk_edge(*tee, ((130, -100.6), (135, -100.6))))
    assert sorted((f.kiids["tracks"], f.measured["d_mm"]) for f in r3(b, gs, 2.0)) == [(["0", "1", "2"], 0.35),
                                                                                       (["3"], 0.35)]
    # a concave corner at (105, -105), and a track 0.6493 mm from it (d 0.399 mm) where the band's round join, 16
    # chords a quadrant of radius k·h + w/2 = 0.65 mm, reaches 0.6492 mm: the middle of its fifth chord
    a = math.radians(180 + 4.5 * 90 / 16)
    s, e = ((105 + r * math.cos(a), -105 + r * math.sin(a)) for r in (0.6493, 2.6493))
    b, c, pm, tags, gs = setup("emc_review", clk_edge((s, e), outline=box(100, -150, 150, -100).difference(
        box(105, -105, 151, -99))))
    (f,) = r3(b, gs, 2.0)
    assert f.measured["d_mm"] == 0.399 and f.at == pytest.approx(s, abs=1e-3)


def test_r2_names_its_via_tracks_and_return_reads_none_without_one_and_a_return_via_must_span_both_layers():  # AR-1
    b, c, pm, tags, gs = setup("qspi_clk")
    via = next(v for v in b.vias if v.net == "FLASH_CLK")
    sides = sorted(t.uuid for t in b.tracks if t.net == "FLASH_CLK" and via.at in (t.start, t.end))
    f = r2(b, c, pm, tags, L5)[0]
    assert f.kiids == {"tracks": sides, "vias": [via.uuid], "zones": [], "pads": [],
                       "footprints": [b.footprints["C1"].uuid]}
    assert (f.at, f.bounds) == ((107.0, -99.79), (106.7, -100.09, 107.3, -99.49))  # the via's 0.6 mm disc
    del b.footprints["C1"]
    assert [(f.measured["return_mm"], f.params["nearest"]) for f in r2(b, c, pm, tags, L5)] == [(None, "T_NONE")] * 2

    def no_in2(b):
        b.areas = [a for a in b.areas if a.layer != "In2.Cu"]

    def ground_in2(b):
        b.areas = [replace(a, net="GND") if a.layer == "In2.Cu" else a for a in b.areas]

    b, c, pm, tags, gs = setup("qspi_clk", no_in2)
    assert r2(b, c, pm, tags, L5) == []  # both sides over In1.Cu's GND: the same layer and net
    b, c, pm, tags, gs = setup("qspi_clk", ground_in2)
    b.vias.append(Via((107.0, -98.99), 0.3, 0.15, ("F.Cu", "In1.Cu"), "GND", "m"))  # stops short of In2.Cu
    assert [f.measured["return_mm"] for f in r2(b, c, pm, tags, L5)] == [3.444, 7.879]
    b.vias.append(Via((107.0, -98.89), 0.3, 0.15, ("In2.Cu", "In1.Cu"), "GND", "u"))  # buried, 0.9 mm off
    (f,) = r2(b, c, pm, tags, L5)
    assert f.kiids["vias"] == sorted(v.uuid for v in b.vias if v.at in ((117.0, -99.79), (124.475, -97.3)))


def test_r4_places_a_gap_mid_stretch_round_the_rings_start_and_fences_only_ground_vias_within_reach():  # A7; AR-11
    b, c, *_ = setup("lpf915")
    parts = frame(b)  # parts[0] runs left along the ring's last side to its start, then 3.3 mm up its first
    vias = gnd_vias([p.interpolate(float(k)) for p in parts for k in range(int(p.length) + 1)])
    b.vias += vias[:3] + vias[4:]
    (f,) = r4(b, c, L5, False)
    assert (f.at, f.bounds) == ((96.125, -110.75), (95.825, -110.75, 97.125, -110.05))  # s2 to s4, round the corner
    assert f.kiids == {"tracks": [], "vias": ["s2", "s4"], "zones": [], "pads": [],
                       "footprints": [b.footprints["SH1"].uuid]}
    b.vias += [Via((96.125, -111.75), 0.6, 0.3, ("F.Cu", "B.Cu"), "AUX", "x"),  # not ground
               Via((96.125, -111.751), 0.6, 0.3, ("F.Cu", "B.Cu"), "GND", "y")]  # 1.001 mm off the ring
    assert [f.measured["gap_mm"] for f in r4(b, c, L5, False)] == [2.0]
    b.vias.append(Via((96.125, -111.75), 0.6, 0.3, ("F.Cu", "B.Cu"), "GND", "z"))  # FENCE_REACH off: 1.0 to s2 and s4
    assert r4(b, c, L5, False) == []


def test_r4_measures_the_board_edges_fence_along_an_outline_that_covers_itself():  # A7; D-1
    b, c, *_ = setup("lpf915")
    b.vias += gnd_vias([Point(122.54, -95.0), Point(122.54, -105.0)], "e")  # 0.5 mm in from the right edge, 10 apart
    edge = [f for f in r4(b, c, L5, True) if f.params["fence"] == "T_EMC_BOARD_EDGE"]
    # max(10, 10 - 0.5 - 0.5), then the rest of the 104.43 mm outline less both insets
    assert [(f.measured["gap_mm"], f.at, f.kiids["vias"], f.kiids["footprints"]) for f in edge] == [
        (10.0, (123.04, -100.0), ["e0", "e1"], []), (93.43, (94.825, -100.5), ["e0", "e1"], [])]


def test_a_route_split_into_segments_reads_as_one_line():  # AR-2, AR-5: a track's piece of route (plan 1's close)
    def split(b):
        (t,) = [t for t in b.tracks if t.net == "CLK_GAP"]
        b.tracks = [u for u in b.tracks if u is not t] + [
            replace(t, start=(103 + 2.5 * k, -110.0), end=(105.5 + 2.5 * k, -110.0), uuid=f"g{k}") for k in range(8)]

    b, c, pm, tags, gs = setup("emc_review", split)
    (f,) = [f for f in r1(b, pm, gs, L5) if f.net == "CLK_GAP"]
    assert (f.measured["run_mm"], f.measured["extent_mm"]) == (6.0, 10.0)


def test_a_track_whose_only_skipped_layer_is_its_own_names_its_net():  # AR-5 (plan 1's close)
    def bare(b):
        b.areas = [a for a in b.areas if a.source != "zone"]
        b.warnings.append(("W_ZONE_NOT_FILLED", {"layer": "F.Cu"}))

    b, c, pm, tags, gs = setup("emc_review", bare)
    assert pm.skipped == ("F.Cu",) and "CLK_GAP" in groups(b, pm, tags, exclusions(b, c))[1]
