# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
from dataclasses import replace

import pytest
import shapely
from shapely.geometry import Point, Polygon, box

from kicad_rf_studio import cli, pipeline
from kicad_rf_studio.core.geometry.overrides import (CLEARANCE, apply_overrides, blocker, make_overrides,
                                                     read_review, via_size)
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.board import CopperArea, Via
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import board_hash, load_project, save_project
from kicad_rf_studio.core.review import review_board
from kicad_rf_studio.core.review.outputs import review_json
from test_cli_emission import emission_project
from test_cli_new import FIX

SLOT = {"kind": "fill", "layer": "In1.Cu", "net": "GND", "from": "R1-test",
        "polygon_mm": {"exterior": [[116, -103], [117, -103], [117, -97], [116, -97]], "holes": []}}


def via(x, y, net="GND"):
    return {"kind": "via", "at_mm": [x, y], "diameter_mm": 0.6, "drill_mm": 0.3, "layers": ["F.Cu", "B.Cu"],
            "net": net, "from": "R4-test"}


def plane(board, layer, net):
    return shapely.union_all([a.polygon for a in board.areas if (a.layer, a.net) == (layer, net)])


def test_a_fill_fills_the_void_as_the_twin_board_draws_it():  # design 5.9; f3's probe 1
    gap, twin = load_board(FIX / "usb2_hs_gap.kicad_pcb"), load_board(FIX / "usb2_hs.kicad_pcb")
    assert apply_overrides(gap, [SLOT]) == []
    assert [(a.layer, a.net, a.uuid) for a in gap.areas if a.source == "override"] == [("In1.Cu", "GND", "override-0")]
    assert plane(gap, "In1.Cu", "GND").symmetric_difference(plane(twin, "In1.Cu", "GND")).area < 1e-6


def test_an_added_via_cuts_an_antipad_in_other_net_fills_only():  # design 5.9; risk 12
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    assert apply_overrides(b, [via(110.0, -97.0)]) == []
    assert [(v.uuid, v.net) for v in b.vias if v.uuid.startswith("override")] == [("override-0", "GND")]
    r = 0.3 + CLEARANCE
    plus = plane(b, "In2.Cu", "+3V3")
    assert not plus.intersects(Point(110, -97).buffer(r - 1e-3)) and plus.covers(Point(110, -97 - r - 0.05))
    assert plane(b, "In1.Cu", "GND").covers(Point(110, -97).buffer(r))


def test_a_via_on_another_nets_copper_or_by_the_edge_is_left_out_with_a_w_line():  # design 5.9; risk 12
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    assert apply_overrides(b, [via(110.0, -100.275), via(110.0, -94.3)]) == [
        ("W_OVERRIDE_REFUSED", {"from": "R4-test", "x_mm": "110.000", "y_mm": "100.275", "reason": "T_OVERRIDE_COPPER"}),
        ("W_OVERRIDE_REFUSED", {"from": "R4-test", "x_mm": "110.000", "y_mm": "94.300", "reason": "T_OVERRIDE_EDGE"})]
    assert not any(v.uuid.startswith("override") for v in b.vias)


def test_load_applies_the_overrides_and_checks_them_again(tmp_path):  # design 5.9; Review Focus 3
    pj = emission_project(tmp_path / "e")  # coupon_gcpw_pads: LINE from (100, 100) to (120, 100)
    save_project(pj, {**load_project(pj), "overrides": [via(110.0, -100.0), via(110.0, -103.0)]})
    _, board, _, notes = pipeline.load(pj)
    assert ("W_OVERRIDE_REFUSED", {"from": "R4-test", "x_mm": "110.000", "y_mm": "100.000",
                                   "reason": "T_OVERRIDE_COPPER"}) in notes
    assert [v.uuid for v in board.vias if v.uuid.startswith("override")] == ["override-1"]


def test_blocker_meets_another_nets_pad_copper_graphic_and_via_on_a_layer_of_its_span():  # design 5.9; Task 10's review
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    fp, side = next(iter(b.footprints.values())), box(110, -101, 111, -100)  # each item reaches x = 111 at y = -100.5
    items = [({"X1": replace(fp, pads=(replace(fp.pads[0], net="X", layers=("B.Cu",), polygon=side),))}, [], []),
             ({}, [CopperArea("In2.Cu", "X", side, "graphic", "g")], []),
             ({}, [], [Via((110.5, -100.5), 1.0, 0.5, ("In1.Cu", "In2.Cu"), "X", "v")])]
    x = 111 + 0.3 + CLEARANCE - 0.01  # a 0.6 mm via's disc grown by CLEARANCE reaches 0.01 mm past x = 111
    for footprints, areas, vias in items:
        b.footprints, b.areas, b.vias, b.tracks = footprints, areas, vias, []
        assert blocker(b, (x, -100.5), 0.3, "GND", ("F.Cu", "B.Cu")) == "T_OVERRIDE_COPPER"
        assert blocker(b, (x + 0.05, -100.5), 0.3, "GND", ("F.Cu", "B.Cu")) is None


def test_a_fill_loses_another_nets_track_grown_by_the_clearance():  # design 5.9; Task 10's review
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    aux = next(t for t in b.tracks if t.net == "AUX")  # F.Cu, 0.2 mm wide along y = -101.15 from x = 108 to 120
    fill = box(110, -102, 112, -101)
    assert apply_overrides(b, [{"kind": "fill", "layer": "F.Cu", "net": "GND", "from": "R1-test",
                                "polygon_mm": {"exterior": list(fill.exterior.coords), "holes": []}}]) == []
    expected = fill.difference(aux.polygon().buffer(CLEARANCE)).area
    assert expected < fill.area - 0.5
    assert sum(a.polygon.area for a in b.areas if a.source == "override") == pytest.approx(expected, abs=1e-6)


def reviewed(name, edit=None, **kw):
    """The board `name` as cli._load reads it, edited in memory by `edit`, and its review.json as a dict."""
    path = FIX / f"{name}.kicad_pcb"
    board, stack, zs, classes = cli._load(path, None)
    if edit:
        edit(board)
    return board, json.loads(review_json(review_board(board, stack, zs, classes, **kw), str(path), board_hash(path)))


def first(review, rule, **match):
    return next(f for f in review["findings"] if f["rule"] == rule and all(f[k] == v for k, v in match.items()))


def test_r1s_fill_is_its_void_on_the_reference_layer(tmp_path):  # design 5.9; f3
    board, review = reviewed("usb2_hs_gap", nets=["USB_D*"])
    f = first(review, "R1")
    (fill,), notes = make_overrides(board, review, f["id"], None, str(tmp_path / "review.json"))
    assert (fill["kind"], fill["layer"], fill["net"], fill["from"], notes) == ("fill", "In1.Cu", "GND", f["id"], [])
    assert Polygon(fill["polygon_mm"]["exterior"]).area == pytest.approx(6.0)


def test_r4_densifies_a_gap_with_ceil_gap_over_p_minus_1_vias_like_its_first(tmp_path):  # design 5.9
    board, review = reviewed("emc_review", f_max=8e9)  # L 0.883 mm: SH1's 0.976 mm gaps fire
    path, f = str(tmp_path / "review.json"), first(review, "R4")
    a, b = (next(v for v in board.vias if v.uuid == u) for u in f["kiids"]["vias"])
    entries, _ = make_overrides(board, review, f["id"], 0.4, path)
    n = math.ceil(f["measured"]["gap_mm"] / 0.4) - 1
    assert len(entries) == n == 2
    for k, e in enumerate(entries, 1):
        assert e["at_mm"] == pytest.approx([a.at[q] + (b.at[q] - a.at[q]) * k / (n + 1) for q in (0, 1)])
        assert (e["diameter_mm"], e["drill_mm"], tuple(e["layers"]), e["net"], e["pitch_mm"]) == (
            a.diameter, a.drill, a.layers, a.net, 0.4)
    with pytest.raises(KrsError) as e:
        make_overrides(board, review, f["id"], 1.0, path)
    assert (e.value.code, e.value.params["reason"]) == ("E_OVERRIDE_NONE", "T_OVERRIDE_PITCH")


def test_r2_between_two_nets_has_no_in_app_variant(tmp_path):  # design 5.9
    board, review = reviewed("qspi_clk", nets=["*CLK"])
    with pytest.raises(KrsError) as e:
        make_overrides(board, review, first(review, "R2")["id"], None, str(tmp_path / "review.json"))
    assert (e.value.code, e.value.params["reason"]) == ("E_OVERRIDE_NONE", "T_OVERRIDE_TWO_NETS")


def test_r2s_return_via_is_one_via_of_the_planes_net_within_d_on_both_planes(tmp_path):  # design 5.9
    def ground_in2(b):  # test_review_rules' same-net case: In2.Cu's +3V3 renamed GND
        b.areas = [replace(a, net="GND") if a.layer == "In2.Cu" else a for a in b.areas]

    board, review = reviewed("qspi_clk", ground_in2, nets=["*CLK"])
    f = first(review, "R2")
    assert (f["params"]["from_net"], f["params"]["to_net"]) == ("GND", "GND")
    (v,), notes = make_overrides(board, review, f["id"], None, str(tmp_path / "review.json"))
    signal = (f["at_mm"][0], -f["at_mm"][1])  # KiCad's frame to the importer's
    (x, y), r = v["at_mm"], v["diameter_mm"] / 2
    assert (v["kind"], v["net"], v["from"], notes) == ("via", "GND", f["id"], [])
    assert math.dist((x, y), signal) <= f["limit"] and blocker(board, (x, y), r, "GND", tuple(v["layers"])) is None
    assert all(plane(board, layer, "GND").covers(Point(x, y).buffer(r))
               for layer in (f["params"]["from_layer"], f["params"]["to_layer"]))


def test_r3s_fence_runs_between_the_track_and_the_edge_where_it_clears(tmp_path):  # design 5.9
    board, review = reviewed("usb2_hs", nets=["USB_D-"], edge_k=30.0)
    f = first(review, "R3", net="USB_D-")
    entries, _ = make_overrides(board, review, f["id"], 1.0, str(tmp_path / "review.json"))
    assert len(entries) >= 5 and {(e["kind"], e["net"], e["pitch_mm"]) for e in entries} == {("via", "GND", 1.0)}
    for e in entries:
        (x, y), r = e["at_mm"], e["diameter_mm"] / 2
        assert -99.725 < y < -94.0 and blocker(board, (x, y), r, "GND", tuple(e["layers"])) is None
        assert plane(board, f["ref_layer"], "GND").covers(Point(x, y).buffer(r))


def test_r3_with_no_room_by_the_edge_gives_no_variant(tmp_path):  # design 5.9: emc_review's CLK_EDGE, 0.35 mm in
    board, review = reviewed("emc_review")
    with pytest.raises(KrsError) as e:
        make_overrides(board, review, first(review, "R3")["id"], None, str(tmp_path / "review.json"))
    assert e.value.params["reason"] == "T_OVERRIDE_NO_ROOM"


def test_a_review_of_another_board_or_without_the_finding_gives_no_variant(tmp_path):  # design 5.9
    board, review = reviewed("usb2_hs_gap", nets=["USB_D*"])
    path = str(tmp_path / "review.json")
    for data, reason in (({**review, "board": {**review["board"], "sha256": "0" * 64}}, "T_REVIEW_OTHER_BOARD"),
                         (review, "T_REVIEW_NO_FINDING")):
        with pytest.raises(KrsError) as e:
            make_overrides(board, data, "R9-00000000", None, path)
        assert (e.value.code, e.value.params["path"], e.value.params["reason"]) == ("E_OVERRIDE_REVIEW", path, reason)


def test_a_review_file_that_does_not_read_or_is_not_of_schema_1_gives_no_variant(tmp_path):  # design 5.9
    path = tmp_path / "review.json"
    for text, reason in (("{", "T_NOT_JSON"), ('{"schema": 2}', "T_REVIEW_SCHEMA"), ("[1]", "T_REVIEW_SCHEMA")):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(KrsError) as e:
            read_review(path, "R1-0")
        assert (e.value.code, e.value.params) == ("E_OVERRIDE_REVIEW", {"path": str(path), "finding": "R1-0",
                                                                        "reason": reason})
    with pytest.raises(KrsError) as e:
        read_review(tmp_path, "R1-0")  # a folder
    assert e.value.params["reason"] == "T_NOT_A_FILE"


def test_an_added_vias_size_is_its_nets_most_common_a_tie_to_the_smaller_and_kicads_default_with_none():  # design 5.9
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    ends = (b.copper_layers[0], b.copper_layers[-1])
    b.vias = [Via((0.0, 0.0), d, d / 2, ends, "X", f"v{n}") for n, d in enumerate((0.8, 0.8, 0.5))]
    assert via_size(b, "X") == (0.8, 0.4, ends)
    b.vias = b.vias[1:]
    assert (via_size(b, "X"), via_size(b, "GND")) == ((0.5, 0.25, ends), (0.6, 0.3, ends))
