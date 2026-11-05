# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

import p4e
from test_p4 import gates  # noqa: F401 (the fixture)

MODEL = {"tdr_lowest": -2.5, "tdr_highest": -2.5, "sdd21@marker": -0.0078, "skew": 0.0, "scd21_worst": 0.0}


def rows(lo=0.0, hi=0.0, il=0.0, il_max=0.0, s11=(0.0, -20.0), scd=(0.0, -60.0), skew=0.0):
    def r(q, marker, delta, base=0.0):
        return {"quantity": q, "marker": marker, "delta": delta, "base": base, "variant": base + delta}
    return [r("tdr_lowest", "", lo, 84.9), r("tdr_highest", "", hi, 96.0), r("sdd21", "marker", il),
            r("sdd21", "f_max", il_max), r("sdd11_worst", "", s11[0], s11[1]), r("scd21_worst", "", scd[0], scd[1]),
            r("skew", "", skew)]


def test_the_gap_moves_even_part_is_curvature_not_noise():  # E-2; the model from the run's own mesh
    pairs = {"repeat": rows(), "shift": rows(lo=0.12, hi=-0.08), "gapp": rows(lo=4.6, hi=4.6),
             "gapm": rows(lo=-9.6, hi=-9.6)}
    n = p4e.noise(pairs, MODEL)
    assert n["DIFF_OHM"] == pytest.approx(0.12)  # the shift: the even part less the mesh model's is 0
    t = p4e.thresholds(n)
    assert (t["DIFF_OHM"], t["SE_OHM"], t["kept"]["DIFF_OHM"]) == (1.0, 0.5, True)
    flat = p4e.noise(pairs, {**MODEL, "tdr_lowest": 0.0, "tdr_highest": 0.0})  # no curvature taken out
    assert p4e.thresholds(flat)["DIFF_OHM"] == pytest.approx(7.5)  # 3 x 2.5, rounded up to 0.1


def test_a_row_without_a_model_takes_no_gap_term():  # the launches set Sdd21 at f_max and the worst Sdd11
    gap = rows(il=-0.0078, il_max=0.03, s11=(0.2, -20.0))  # Sdd21 at the marker: the model's even part, no noise
    n = p4e.noise({"repeat": rows(), "shift": rows(), "gapp": gap, "gapm": gap}, MODEL)
    assert (n["IL_DB"], n["DB"]) == (0.0, 0.0)
    assert (n["parts"]["sdd21@f_max"]["even"], n["parts"]["sdd11_worst"]["even"]) == (pytest.approx(0.03),
                                                                                      pytest.approx(0.2))


def test_the_thresholds_widen_to_three_times_the_noise_rounded_up():  # design 5.8; E-2: the criteria's design values
    t = p4e.thresholds({"DIFF_OHM": 0.4, "IL_DB": 0.0166, "DB": 0.21, "SKEW_PS": 0.2})
    assert (t["DIFF_OHM"], t["SE_OHM"], t["IL_DB"], t["DB"], t["SKEW_PS"]) == (
        pytest.approx(1.2), pytest.approx(0.6), 0.05, pytest.approx(0.65), 1.0)  # 0.0166 x 3 = 0.0498 < 0.05: kept
    assert t["kept"] == {"DIFF_OHM": False, "IL_DB": True, "DB": False, "SKEW_PS": True}


def test_a_db_row_under_the_floor_on_both_sides_is_no_noise():  # r3: the floor's rows left out
    pairs = {"repeat": rows(scd=(3.0, -70.0)), "shift": rows(), "gapp": rows(), "gapm": rows()}
    assert p4e.noise(pairs, MODEL)["DB"] == 0.0  # -70 to -67 dB: both under -50


def test_the_victims_shift_measures_next_and_fext():  # the controller's ruling on open issue 10
    xt = [{"quantity": q, "marker": "AUX", "delta": d, "base": -30.0, "variant": -30.0 + d}
          for q, d in (("next", 0.2), ("fext", -0.25))]
    n = p4e.noise({"repeat": rows(), "shift": rows(), "gapp": rows(), "gapm": rows(), "vshift": rows() + xt}, MODEL)
    assert n["DB"] == pytest.approx(0.25)  # FEXT's shift: no gap term, no model
    assert p4e.thresholds(n)["DB"] == pytest.approx(0.75)  # over a third of 0.5 dB: three times it


def test_the_null_edit_is_zero_when_its_hash_is_the_bases_else_one_more_pair():  # E-1
    refs = {"model_even": {"2-l80": MODEL}}
    curved = rows(lo=-2.5, hi=-2.5, il=-0.0078)  # the gap's even part the mesh model's: no noise
    base = {"key": "2-l80", "invalid": [], "pairs": {"repeat": rows(), "shift": rows(), "gapp": curved, "gapm": curved,
                                                     "vshift": rows()}}
    assert p4e.decide({**base, "null_equal": True}, refs)["verdict"]["value"] == "pass"
    assert p4e.decide({**base, "null_equal": False}, refs)["verdict"]["value"] == "incomplete"
    unrun = {**base, "pairs": {k: v for k, v in base["pairs"].items() if k != "vshift"}, "null_equal": True}
    assert p4e.decide(unrun, refs)["verdict"]["value"] == "incomplete"  # the victim's shift is a pair too
    over = {**base, "pairs": {**base["pairs"], "null": rows(hi=0.5)}, "null_equal": False}
    assert p4e.decide(over, refs)["verdict"]["value"] == "widened"  # 0.5 > 1/3 ohm
    assert p4e.decide({**base, "null_equal": True, "invalid": ["shift"]}, refs)["verdict"]["fails"] == ["shift: valid"]


def test_the_committed_references_hold_the_mesh_and_the_exact_even_parts():  # E-2
    refs = json.loads(p4e.REFERENCES.read_text(encoding="utf-8"))
    assert set(refs["model_even"]) == {f"{n}-{rule}" for n in (2, 3) for rule in ("l40", "l80", "dfill")}
    assert refs["model_even"]["2-l40"]["tdr_highest"] == pytest.approx(-2.50, abs=0.05)  # the physics review's replica
    assert (refs["exact"]["2"]["tdr_highest"], refs["exact"]["2"]["sdd21@marker"]) == (
        pytest.approx(-2.1486, abs=1e-3), pytest.approx(-0.0078, abs=2e-4))


def test_p4e_runs_its_steps_and_writes_its_report(gates):  # design 5.11: the tool on the network fake
    assert p4e.main(["--out", str(gates), "--steps", "base,repeat,bogus"]) == 1  # no such step
    with pytest.raises(SystemExit, match="never regenerated"):
        p4e.main(["--references"])
    assert p4e.main(["--out", str(gates)]) == 0
    text = (gates / "p4e" / "p4e.json").read_text(encoding="utf-8")
    result = json.loads(text)
    assert sorted(result["runs"]) == ["base", "repeat"] and sorted(result["pairs"]) == ["repeat"]
    assert result["null_equal"] is False  # clean()'s simplification moves the split's edge: its pair is needed
    assert result["noise"]["SKEW_PS"] == 0.0 and result["verdict"] == {"value": "incomplete", "fails": []}
    assert '"reading"' not in text and '"project"' not in text
    assert (gates / "p4e" / "p4e.md").read_text(encoding="utf-8").startswith("## P4E-1 The noise")
