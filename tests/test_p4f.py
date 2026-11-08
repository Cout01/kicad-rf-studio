# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

import p0
import p4f
from test_p4 import gates  # noqa: F401 (the fixture)

T = {"DIFF_OHM": 1.0, "DB": 0.5, "floor_db": -50.0, "scd21_floor_db": -37.7}


def m(highest=8.05, short=True, scd=(-45.0, -27.35), invalid=()):
    return {"neck": [{"quantity": "tdr_highest", "marker": "short", "delta": highest}],
            "gap": [{"quantity": "scd21_worst", "marker": "", "base": scd[0], "variant": scd[1],
                     "delta": scd[1] - scd[0]}],
            "neck_short": short, "base_short": [True, True], "invalid": list(invalid)}


def test_p4f_judges_the_rows_each_case_is_built_to_move():  # F-2
    assert p4f.decide(m(), T)["verdict"] == {"value": "pass", "fails": [], "owner": []}
    assert p4f.decide(m(highest=3.0), T)["verdict"]["fails"] == []  # 3 x DIFF_OHM, inclusive
    assert p4f.decide(m(highest=2.99), T)["verdict"]["fails"] == ["neck: tdr_highest"]
    assert p4f.decide(m(scd=(-70.0, -55.0)), T)["verdict"]["fails"] == ["gap: scd21_worst"]  # both under -50 dB
    assert p4f.decide(m(scd=(-75.8, -40.0)), T)["verdict"]["fails"] == ["gap: scd21_worst"]  # under Scd21's floor (R-13)
    assert p4f.decide(m(scd=(-75.8, -37.0)), T)["verdict"]["fails"] == []
    assert p4f.decide(m(scd=(-75.8, -40.0)), T)["gap"]["floor_db"] == -37.7
    assert p4f.decide(m(highest=8.05), {**T, "DIFF_OHM": 2.7})["verdict"]["fails"] == ["neck: tdr_highest"]
    assert p4f.decide(m(invalid=["usb2_hs_gap"]), T)["verdict"]["fails"] == ["usb2_hs_gap: valid"]


def test_a_neck_its_own_run_leaves_unmarked_is_an_owner_item():  # design 5.6; plan 3's owner item
    assert p4f.decide(m(short=False), T)["verdict"] == {"value": "pass", "fails": [], "owner": ["neck: short mark"]}


def test_p4f_runs_its_steps_and_writes_its_report(gates):  # design 5.11: the tool on the network fake
    assert p4f.main(["--out", str(gates), "--steps", "usb2_hs,usb2_hs_neck,usb2_hs_bogus"]) == 1  # no such step
    with pytest.raises(SystemExit, match="run P4-E's report first"):
        p4f.main(["--out", str(gates)])
    p0.save(gates / "p4e" / "p4e.json", {"thresholds": {"DIFF_OHM": 1.0, "SE_OHM": 0.5, "IL_DB": 0.05, "DB": 85.7,
                                                        "SKEW_PS": 1.0}})
    assert p4f.main(["--out", str(gates)]) == 0
    text = (gates / "p4f" / "p4f.json").read_text(encoding="utf-8")
    result = json.loads(text)
    assert sorted(result["runs"]) == ["usb2_hs", "usb2_hs_neck"] and result["rows"]["gap"] is None  # the gap unrun
    assert result["thresholds"]["floor_db"] == -50.0 and sorted(result["dc"]) == ["usb2_hs", "usb2_hs_neck"]
    assert result["thresholds"]["DB"] == 0.5 and result["thresholds"]["scd21_floor_db"] == -37.7  # R-13 over P4-E's
    assert result["verdict"]["fails"] == ["neck: tdr_highest", "gap: scd21_worst"]  # one S for every board
    assert result["recorded"]["neck"][-1].startswith("Resolved means larger than the significance threshold")
    assert '"reading"' not in text and '"project"' not in text
    assert (gates / "p4f" / "p4f.md").read_text(encoding="utf-8").startswith("## P4F-1 The judged rows")
