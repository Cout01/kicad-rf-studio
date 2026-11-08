# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import math
from dataclasses import replace

import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError, english
from kicad_rf_studio.core.post import si
from kicad_rf_studio.core.post.antenna import DELTA_COLUMNS, deltas_csv
from kicad_rf_studio.core.post.si import read, si_delta_lines, si_deltas, si_limits
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_antenna import antenna_project
from test_cli_si import si_project
from test_compare import compared, twin
from test_post_si import F, P100, P2V, ROUTE1, SE, line_s, pair6, pair8
from test_si_run import verified_si

A = math.sqrt(2)  # pair6's coupling to P alone reads 3 dB down, driven differentially


def test_the_thresholds_are_gate_p4es():  # design 5.8; gate P4-E's section 4, with plan 4 ruling R-13's DB and floor
    assert (si.DIFF_OHM, si.SE_OHM, si.IL_DB, si.DB, si.LEVEL_FLOOR_DB, si.SCD21_FLOOR_DB, si.SKEW_PS) == (
        2.2, 1.1, 0.05, 0.5, -50.0, -37.7, 1.0)


def test_scd21_resolves_only_above_its_own_floor():  # plan 4 ruling R-13: zero by symmetry on a symmetric pair
    b = read(pair6(), F, P100, 3.0)

    def at(scd21_db: float, sdd11_db: float):  # b with a flat |Scd21| and |Sdd11| at these levels
        m = b.m.copy()
        m[:, 3, 0], m[:, 0, 0] = 10 ** (scd21_db / 20), 10 ** (sdd11_db / 20)
        return replace(b, m=m)

    def resolved(variant) -> dict:
        return {r["quantity"]: r["resolved"] for r in si_deltas(P100, at(-45.0, -45.0), variant)}

    assert {k: v for k, v in resolved(at(-40.0, -40.0)).items() if k.endswith("_worst")} == {
        "sdd11_worst": True, "scd21_worst": False}  # each 5 dB up: Sdd11 above -50 dB, Scd21 under its -37.7 dB
    assert resolved(at(-37.0, -45.0))["scd21_worst"] is True


def test_the_si_deltas_and_their_significance():  # design 5.8; Review Focus 2
    b = read(pair6(A * 10 ** (-60 / 20), A * 10 ** (-70 / 20)), F, P100, 3.0)
    v = read(pair6(A * 10 ** (-45 / 20), A * 10 ** (-60 / 20), 0.2e-9 + 1.5e-12), F, P100, 3.0)
    rows = si_deltas(P100, b, v)
    assert [(r["quantity"], r["marker"], r["threshold"], r["resolved"]) for r in rows] == [
        ("tdr_lowest", "", 2.2, False), ("tdr_highest", "", 2.2, False), ("sdd21", "marker", 0.05, False),
        ("sdd21", "f_max", 0.05, False), ("sdd11_worst", "", 0.5, False), ("scd21_worst", "", 0.5, True),
        ("skew", "", 1.0, True), ("next", "AUX", 0.5, True), ("fext", "AUX", 0.5, False)]  # FEXT: both under -50 dB
    assert rows[6]["delta"] == pytest.approx(1.498, abs=0.005) and rows[8]["delta"] == pytest.approx(10.0)
    assert (rows[2]["f_hz"], rows[3]["f_hz"], rows[2]["unit"], rows[6]["unit"]) == (240e6, 10e9, "dB", "ps")
    short = read(line_s([(50.0, 4.0, 5.0)], F), F, SE, 4.0)  # no level: the TDR rows hold none
    assert [r["resolved"] for r in si_deltas(SE, short, short)[:2]] == [None, None]
    two = read(pair8(), F, P2V, 3.0)  # each victim its rows, by its first net
    assert [(r["quantity"], r["marker"]) for r in si_deltas(P2V, two, two)[-4:]] == [
        ("next", "AUX"), ("fext", "AUX"), ("next", "AUX2"), ("fext", "AUX2")]


def test_the_deltas_of_a_net():  # design 5.8; anti-goal 2; Review Focus 3, 5
    n = read(line_s(ROUTE1, F), F, SE, 4.0)
    rows = si_deltas(SE, n, n)
    assert [(r["quantity"], r["marker"], r["threshold"]) for r in rows] == [
        ("tdr_lowest", "short", 1.1), ("tdr_highest", "", 1.1), ("s21", "marker", 0.05), ("s21", "f_max", 0.05),
        ("s11_worst", "", 0.5)]  # the 3 mm bump's level: marked in compare.csv
    assert {r["resolved"] for r in rows} == {False}
    assert [code for code, _ in si_delta_lines(SE, rows)][:2] == ["I_SI_COMPARE_LEVEL_SHORT", "I_SI_COMPARE_LEVEL"]


def test_the_si_delta_lines_and_csv():  # design 5.8
    b = read(pair6(A * 10 ** (-60 / 20), A * 10 ** (-70 / 20)), F, P100, 3.0)
    v = read(pair6(A * 10 ** (-45 / 20), A * 10 ** (-60 / 20), 0.2e-9 + 1.5e-12), F, P100, 3.0)
    rows = si_deltas(P100, b, v)
    lines = si_delta_lines(P100, rows)
    assert [code for code, _ in lines] == [
        "I_SI_COMPARE_LEVEL", "I_SI_COMPARE_LEVEL", "I_SI_COMPARE_INSERTION", "I_SI_COMPARE_INSERTION",
        "I_SI_COMPARE_WORST", "I_SI_COMPARE_WORST", "I_SI_COMPARE_SKEW", "I_SI_COMPARE_XT", "I_SI_COMPARE_XT",
        "I_SI_COMPARE_THRESHOLDS"]
    assert lines[6][1] == {"base": "+0.00", "variant": "+1.50", "delta": "+1.50", "verdict": "T_RESOLVED"}
    assert lines[7][1] == {"kind": "NEXT", "net": "AUX", "base": "-60.00", "variant": "-45.00", "delta": "+15.00",
                           "verdict": "T_RESOLVED"}
    assert lines[-1][1] == {"ohm": "2.2", "il_db": "0.05", "db": "0.5", "floor_db": "-50", "scd21_floor_db": "-37.7",
                            "ps": "1"}
    assert english("I_SI_COMPARE_THRESHOLDS", **lines[-1][1]) == (
        "Resolved means larger than the significance threshold: 2.2 Ω on a TDR level, 0.05 dB on Sdd21 or S21, 0.5 dB "
        "on Sdd11, S11, NEXT and FEXT where the higher of the two levels stands above -50 dB and on Scd21 where it "
        "stands above -37.7 dB, and 1 ps on the skew: the values gate P4-E set from the model's measured noise.")
    short = read(line_s([(50.0, 4.0, 5.0)], F), F, SE, 4.0)
    assert [code for code, _ in si_delta_lines(SE, si_deltas(SE, short, short))][0] == "I_SI_COMPARE_NO_LEVELS"
    table = list(csv.reader(io.StringIO(deltas_csv(rows).decode())))
    assert table[0] == list(DELTA_COLUMNS) and len(table) == 10


def test_compare_two_si_projects_through_their_verifies(tmp_path, calibrated, monkeypatch):  # 5.8, 5.14
    a = verified_si(tmp_path, monkeypatch)
    assert pipeline.verify(a) == 0
    b, run_dir = twin(a, tmp_path / "b"), load_project(a)["verify"]["run_dir"]
    lines = compared(a, b, tmp_path / "out")
    codes = [code for code, _ in lines]
    assert lines[:3] == [("I_SI_RELATIVE", {}),
                         ("I_COMPARE_BASIS", {"role": "T_BASE", "path": str(a), "source": "T_VERIFY",
                                              "run_dir": run_dir}),
                         ("I_COMPARE_BASIS", {"role": "T_VARIANT", "path": str(b), "source": "T_VERIFY",
                                              "run_dir": run_dir})]
    assert "I_SI_COMPARE_NO_LEVELS" in codes
    assert {p["verdict"] for _, p in lines if "verdict" in p} == {"T_NOT_RESOLVED"}
    assert codes[-7:] == ["I_OUTPUTS", *si_limits(load_project(a))]
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["compare.csv", "compare.png"]


def test_compare_refuses_si_projects_it_cannot_compare(tmp_path, calibrated, monkeypatch):  # 5.8; Review Focus 4
    a = verified_si(tmp_path, monkeypatch)
    assert pipeline.verify(a) == 0
    b, old = twin(a, tmp_path / "b"), twin(a, tmp_path / "old")
    d = load_project(b)
    d["verify"]["fingerprint"] = {**d["verify"]["fingerprint"], "ends": ["J1.3", "J1.2", "U1.3", "U1.2"]}  # no victim
    d["target_ohm"] = 85.0  # another current target: compare reads it, not the record's (plan 5)
    save_project(b, d)
    d = load_project(old)
    del d["results"]["route"]  # plan 2's results
    save_project(old, d)
    for variant, code, params in [(b, "E_COMPARE_SETTINGS", {"fields": "ends, target_ohm"}),
                                  (old, "E_COMPARE_NO_RESULT", {"path": str(old)})]:
        with pytest.raises(KrsError) as e:
            pipeline.compare_projects(a, variant, tmp_path / "out")
        assert (e.value.code, e.value.params) == (code, params)
    ant = antenna_project(tmp_path / "ant")

    def board_read(*_):
        raise AssertionError("a board was read")

    with monkeypatch.context() as m:  # each project's kind, before any board is read
        m.setattr(pipeline, "load", board_read)
        for base, variant in ((a, ant), (ant, a)):
            with pytest.raises(KrsError) as e:
                pipeline.compare_projects(base, variant, tmp_path / "out")
            assert (e.value.code, e.value.params) == ("E_COMPARE_KIND", {"path": str(variant)})
    assert not (tmp_path / "out").exists()


def test_compare_reads_each_si_project_at_its_current_target_marker_and_rise(tmp_path, calibrated, monkeypatch):
    a = verified_si(tmp_path, monkeypatch)  # ruling 5, plan 3's deferred item; Review Focus 4
    assert pipeline.verify(a) == 0
    b = twin(a, tmp_path / "b")
    for path in (a, b):  # edited alike after the verify: no part of the model, so the results stay current
        save_project(path, {**load_project(path), "target_ohm": 85.0})
    assert pipeline.si_result(a)["fingerprint"]["target_ohm"] == 85.0  # as Results reads it
    assert load_project(a)["verify"]["fingerprint"]["target_ohm"] == 90.0  # the record keeps the run's
    compared(a, b, tmp_path / "out")  # both read at 85 Ω: exit 0
    save_project(b, {**load_project(b), "target_ohm": 90.0, "marker_hz": 250e6, "rise_s": 1e-9})
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(a, b, tmp_path / "out2")
    assert (e.value.code, e.value.params) == ("E_COMPARE_SETTINGS", {"fields": "marker_hz, rise_s, target_ohm"})
    assert not (tmp_path / "out2").exists()


def test_compare_reads_a_partless_si_projects_run(tmp_path, calibrated, monkeypatch):  # 5.7, 5.8; Review Focus 5
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    d = load_project(pj)
    for line in d["lines"]:
        for q in line["chain"]["series"]:
            q["role"] = "copper"  # R1 and R2 copper: no part port
    save_project(pj, d)
    assert pipeline.run(pj) == 0
    for call, code in ((lambda: pipeline.retune(pj, ["R1=33"]), "E_RETUNE_NO_PARTS"),
                       (lambda: pipeline.verify(pj), "E_VERIFY_NO_PARTS")):
        with pytest.raises(KrsError) as e:
            call()
        assert (e.value.code, e.value.params) == (code, {})
    lines = compared(pj, twin(pj, tmp_path / "b"), tmp_path / "out")
    assert [p["source"] for code, p in lines if code == "I_COMPARE_BASIS"] == ["T_RUN", "T_RUN"]
