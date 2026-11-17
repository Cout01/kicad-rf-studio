# SPDX-License-Identifier: GPL-3.0-or-later
import shapely
from shapely.geometry import Point

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.geometry.overrides import CLEARANCE, apply_overrides
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.project import load_project, save_project
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
