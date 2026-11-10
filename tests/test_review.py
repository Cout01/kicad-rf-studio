# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.review import finding_ids, resolve_f_max, review_board

FIX = Path(__file__).parent / "fixtures"
CLKS = ("CLK_EDGE", "CLK_GAP", "CLK_LOOK", "CLK_MID")


def run(name="emc_review", edit=lambda b: None, **kw):
    b = load_board(FIX / f"{name}.kicad_pcb")
    edit(b)
    return review_board(b, b.stackup, zstack(b.stackup, b.copper_layers), classify(b), **kw)


def digest(rule, kiids, at):
    return hashlib.sha256(json.dumps([rule, kiids, at], separators=(",", ":")).encode()).hexdigest()[:8]


@pytest.mark.parametrize(("f_max", "f0", "project", "expected"), [
    (7e9, 915e6, None, (7e9, "cli", 915e6)),
    (None, 915e6, None, (4.575e9, "carrier", 915e6)),
    (None, 2.44e9, None, (6e9, "carrier", 2.44e9)),
    (None, None, {"schema": 1, "f0_hz": 868e6}, (4.34e9, "carrier", 868e6)),
    (None, None, {"schema": 2, "f0_hz": 870e6, "band": {"f_lo_hz": 840e6, "f_hi_hz": 880e6}},
     (4.3e9, "carrier", 860e6)),  # an antenna's band centre, never its f0_hz
    (None, None, {"schema": 3, "f_max_hz": 10e9}, (6e9, "si", None)),
    (None, None, {"schema": 3, "f_max_hz": 2e9}, (2e9, "si", None)),
    (None, 915e6, {"schema": 3, "f_max_hz": 10e9}, (4.575e9, "carrier", 915e6)),  # --f0 wins over a project's
    (None, None, None, (5e9, "default", None))])
def test_f_max_resolves_in_bc1s_order(f_max, f0, project, expected):  # design 5.1; BC1
    f, source, carrier = resolve_f_max(f_max, f0, project)
    assert f == pytest.approx(expected[0]) and source == expected[1] and carrier == pytest.approx(expected[2])


def test_the_review_of_emc_review_states_its_basis_and_tags_and_numbers_its_two_findings():  # design 5.1 to 5.3
    r = run()
    assert r.settings == {"f_max_hz": 5e9, "f_max_source": "default", "eps_r": 4.5, "l_mm": 1.413, "edge_k": 2.0,
                          "edge_fence": False, "tags": [{"net": n, "source": "pattern:CLK"} for n in CLKS]}
    assert r.notes == [("W_FILLS_AS_SAVED", {}), ("I_REVIEW_RELATIVE", {}),
                       ("I_REVIEW_BASIS", {"f_max_ghz": "5", "source": "T_FMAX_DEFAULT", "eps_r": "4.5",
                                           "l_mm": "1.413", "edge_k": "2"}),
                       ("I_REVIEW_TAGS_PATTERN", {"nets": ", ".join(CLKS)})]
    assert [(f.n, f.rule, f.net, f.tag_source) for f in r.findings] == [(1, "R1", "CLK_GAP", "pattern:CLK"),
                                                                       (2, "R3", "CLK_EDGE", "pattern:CLK")]
    gap, edge = r.findings
    assert (edge.params["n"], edge.params["x_mm"], edge.params["y_mm"]) == ("2", "113.000", "100.600")  # KiCad's frame
    assert float(gap.params["x_mm"]) == pytest.approx(113, abs=1e-3) and gap.params["y_mm"] == "110.000"
    assert r.cover.area > 0 and r.carrier is None and r.clocks == ()


def test_a_findings_id_is_its_rule_and_a_hash_of_its_kiids_and_place_numbered_on_a_clash():  # design 5.3
    f = run().findings[1]
    kiids = sorted(k for ids in f.kiids.values() for k in ids)
    assert f.id == f"R3-{digest('R3', kiids, [113.0, 100.6])}" == run().findings[1].id  # same copper, same id
    assert finding_ids([f, f]) == [f.id, f.id + "-2"]
    assert finding_ids([replace(f, at=(5.0, 0.0))]) == [f"R3-{digest('R3', kiids, [5.0, 0.0])}"]  # never -0.0


def test_the_notes_name_unmatched_flags_skipped_layers_and_nets_with_no_plane():  # design 5.1, 5.3
    assert run(nets=["NOPE"]).notes[3:] == [("I_REVIEW_NO_TAGS", {}), ("W_REVIEW_NET_UNMATCHED", {"pattern": "NOPE"})]

    def unfilled(b):
        b.warnings = [("W_ZONE_NOT_FILLED", {"uuid": "z", "layer": "In1.Cu"})]

    r = run(edit=unfilled)
    assert r.notes[:2] == [("W_ZONE_NOT_FILLED", {"uuid": "z", "layer": "In1.Cu"}), ("W_FILLS_AS_SAVED", {})]
    assert ("W_EMC_LAYER_SKIPPED", {"layer": "In1.Cu"}) in r.notes and r.findings == []  # F.Cu's tracks skipped

    def bare(b):
        b.areas = []

    r = run("usb2_hs", bare)
    assert ("I_REVIEW_TAGS_WALK", {"nets": "MCU_D+, MCU_D-"}) in r.notes
    assert r.notes[-1] == ("I_EMC_NO_REFERENCE", {"nets": "MCU_D+, MCU_D-, USB_D+, USB_D-"})
