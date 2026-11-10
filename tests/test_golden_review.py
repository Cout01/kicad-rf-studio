# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess

import golden_review
import pytest


@pytest.mark.parametrize("name", golden_review.CASES)
def test_the_review_writes_its_golden_review_json_byte_for_byte(name, tmp_path, monkeypatch):
    # design 5.14; 5.17 item 2
    monkeypatch.chdir(tmp_path)
    golden = (golden_review.GOLDEN / f"{name}.json").read_bytes().replace(b"\r\n", b"\n")  # a CRLF checkout
    assert golden_review.golden_bytes(name) == golden


def test_the_goldens_name_their_board_by_file_and_hash_and_hold_each_rules_positive():  # design 5.14's table
    data = {n: json.loads((golden_review.GOLDEN / f"{n}.json").read_text(encoding="utf-8"))
            for n in golden_review.CASES}
    assert {n: d["board"]["path"] for n, d in data.items()} == {n: f"{n}.kicad_pcb" for n in data}
    assert all(len(d["board"]["sha256"]) == 64 and isinstance(d["cavities"], list) for d in data.values())
    assert {n: [f["rule"] for f in d["findings"]] for n, d in data.items()} == {
        "emc_review": ["R1", "R3"], "usb2_hs": [], "usb2_hs_gap": ["R1", "R1"], "qspi_clk": ["R2", "R2"],
        "lpf915": ["R4"]}
    assert data["lpf915"]["settings"]["l_mm"] == 1.545 and data["lpf915"]["settings"]["f_max_source"] == "carrier"
    assert data["usb2_hs_gap"]["findings"][0]["measured"]["run_mm"] == 1.0
    assert data["emc_review"]["findings"][0]["measured"] == {"run_mm": 6.0, "extent_mm": 10.0, "l_mm": 1.413}


PLAN1 = "1f57b80"  # plan 1's close: the goldens as plan 1 recorded them


@pytest.mark.parametrize("name", golden_review.CASES)
def test_the_re_recorded_goldens_differ_from_plan_1s_only_in_cavities(name):  # ruling 2
    shown = subprocess.run(["git", "show", f"{PLAN1}:tests/fixtures/review/{name}.json"], capture_output=True,
                           cwd=golden_review.GOLDEN.parents[2])
    if shown.returncode:
        pytest.skip("plan 1's commit is not in this clone")
    old_b = shown.stdout.replace(b"\r\n", b"\n")
    new_b = (golden_review.GOLDEN / f"{name}.json").read_bytes().replace(b"\r\n", b"\n")  # a CRLF checkout
    assert new_b[:new_b.index(b'"cavities"')] == old_b[:old_b.index(b'"cavities"')]  # every byte before, findings too
    old, new = json.loads(old_b), json.loads(new_b)
    assert old["cavities"] == [] and new.keys() == old.keys()


def golden(name):
    return json.loads((golden_review.GOLDEN / f"{name}.json").read_text(encoding="utf-8"))


def pair(name, nets):
    return max((c for c in golden(name)["cavities"] if c["nets"] == nets), key=lambda c: c["area_mm2"])


def test_e_e7_the_slot_lowers_the_first_mode_and_lpf915s_stitched_pair_has_no_dc_mode():  # design 5.12 E-E (7)
    whole, slotted = (pair(n, [["GND"], ["+3V3"]])["modes"][1]["f_hz"] for n in ("usb2_hs", "usb2_hs_gap"))
    assert slotted <= 0.95 * whole  # r2 measured 1.865 -> 1.676 GHz, -10.1 %
    lpf = pair("lpf915", [["GND"], ["GND"]])
    assert lpf["posts"] > 0 and min(m["f_hz"] for m in lpf["modes"]) >= 1e6
    rim = pair("emc_review", [["GND"], ["GND"]])
    assert rim["posts"] == 1 and min(m["f_hz"] for m in rim["modes"]) >= 1e6
    assert pair("emc_review", [["GND"], ["+3V3"]])["modes"][0]["f_hz"] == 0.0
