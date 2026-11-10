# SPDX-License-Identifier: GPL-3.0-or-later
import json

import golden_review
import pytest


@pytest.mark.parametrize("name", golden_review.CASES)
def test_the_review_writes_its_golden_review_json_byte_for_byte(name, tmp_path, monkeypatch):  # design 5.14; 5.17 item 2
    monkeypatch.chdir(tmp_path)
    golden = (golden_review.GOLDEN / f"{name}.json").read_bytes().replace(b"\r\n", b"\n")  # a CRLF checkout
    assert golden_review.golden_bytes(name) == golden


def test_the_goldens_name_their_board_by_file_and_hash_and_hold_each_rules_positive():  # design 5.14's table
    data = {n: json.loads((golden_review.GOLDEN / f"{n}.json").read_text(encoding="utf-8")) for n in golden_review.CASES}
    assert {n: d["board"]["path"] for n, d in data.items()} == {n: f"{n}.kicad_pcb" for n in data}
    assert all(len(d["board"]["sha256"]) == 64 and d["cavities"] == [] for d in data.values())
    assert {n: [f["rule"] for f in d["findings"]] for n, d in data.items()} == {
        "emc_review": ["R1", "R3"], "usb2_hs": [], "usb2_hs_gap": ["R1", "R1"], "qspi_clk": ["R2", "R2"],
        "lpf915": ["R4"]}
    assert data["lpf915"]["settings"]["l_mm"] == 1.545 and data["lpf915"]["settings"]["f_max_source"] == "carrier"
    assert data["usb2_hs_gap"]["findings"][0]["measured"]["run_mm"] == 1.0
    assert data["emc_review"]["findings"][0]["measured"] == {"run_mm": 6.0, "extent_mm": 10.0, "l_mm": 1.413}
