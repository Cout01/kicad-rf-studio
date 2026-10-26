# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
import math
from itertools import product
from pathlib import Path

import pytest

import kicad_rf_studio.core.mesh.rule as rule
import meshcal
import p0


def row(family, case, n, fit2d, gap=0.15):
    return {"family": family, "case": case, "n": n, "lint": 0, "ratio": 0, "d3": 0, "fit2d": list(fit2d),
            "secs": [["LINE", 0.6, gap]] * len(fit2d)}


def table(over=()):
    """hrun.py's rows of the ten fixtures at n = 2 and 3 (GCPW coupons 1.0 %, microstrip 0.2 %, lpf915 2.0 % at n = 2
    and 4.2 % at n = 3, coupon_gcpw_45 with no section) and of a family "fam" of five boards; `over` maps a key to the
    fields it changes, or to a whole row when that row holds "err"."""
    rows = {}
    for n in (2, 3):
        rows |= {("fixtures", c, n): row("fixtures", c, n, [1.0]) for c in meshcal.GCPW}
        rows |= {("fixtures", c, n): row("fixtures", c, n, [0.2], None) for c in meshcal.MS}
        rows |= {("fixtures", c, n): row("fixtures", c, n, [2.0 if n == 2 else 4.2]) for c in meshcal.N3_EXEMPT}
        rows[("fixtures", "coupon_gcpw_45", n)] = row("fixtures", "coupon_gcpw_45", n, [])
        rows |= {("fam", f"c{i}", n): row("fam", f"c{i}", n, [1.0]) for i in range(5)}
    for key, v in dict(over).items():
        rows[key] = v if "err" in v else {**rows[key], **v}
    return rows


def axes(over=()):
    a = {h: {"facing|1": [0, 0, 0, 0, 0], "facing|2": [1, 1, 0, 0, 0]} for h in meshcal.H}
    for h, key, v in over:
        a[h][key] = v
    return a


LOST = {("fam", "c4", 3): {"fit2d": [3.3]}}  # a board both runs fail
BASE = table({("fixtures", "coupon_gcpw_masked", 2): {"fit2d": [3.77]}, **LOST})  # today: the masked coupon stops
GOOD = table(LOST)  # the masked coupon fixed, nothing lost


def test_the_grid_is_the_designs_48_candidates():  # design 5.1
    grid = [(c["slot_in"], c["gate"], c["served"]) for c in meshcal.CANDIDATES]
    assert grid == list(product([1 / 8, 9 / 64, 5 / 32, 1 / 6, 3 / 16, 5 / 24], [0.0, 2.0, 3.0, 4.2], [False, True]))
    assert len({c["id"] for c in meshcal.CANDIDATES}) == 48 and meshcal.CANDIDATES[0]["id"] == "1-8_none_lone"
    assert meshcal.BASE == {"id": "off", "slot_in": None, "gate": 0.0, "served": False}
    assert meshcal.SHAKE in {c["id"] for c in meshcal.CANDIDATES}


def test_a_candidate_rule_holds_its_values():
    text = (p0.ROOT / "src" / "kicad_rf_studio" / "core" / "mesh" / "rule.py").read_text(encoding="utf-8")
    ns = {}
    exec(compile(meshcal.patch(text, meshcal.CANDIDATES[-1]), "rule.py", "exec"), ns)
    assert (ns["SLOT_IN"], ns["SLOT_GATE"], ns["SLOT_SERVED"]) == (5 / 24, 4.2, True)


def test_a_candidate_that_fixes_the_fixtures_and_loses_nothing_passes():
    r = meshcal.accept(BASE, axes(), GOOD, axes())
    assert (r["c1"], r["c2"], r["c3"], r["c4"], r["pass"]) == (True,) * 5
    assert (r["passes"], r["regressions"], r["gcpw_coupons"], r["gcpw_max"]) == (27, [], [1.0, 1.0], 1.0)


CASES = {  # one change to the candidate each, and the condition it breaks
    "fixture over 3 % at n 2": ({("fixtures", "lpf915", 2): {"fit2d": [3.2]}}, (), "c1"),
    "fixture that fails the lint": ({("fixtures", "coupon_gcpw", 3): {"lint": 1}}, (), "c1"),
    "fixture that errs": ({("fixtures", "coupon_gcpw_pads", 2): {"family": "fixtures", "case": "coupon_gcpw_pads",
                                                                  "n": 2, "err": "RuntimeError('no convergence')"}}, (), "c1"),
    "fixture whose fit2d is NaN": ({("fixtures", "coupon_gcpw", 2): {"fit2d": [math.nan]}}, (), "c1"),
    "axis regression at 2d": ({}, [("2d", "facing|1", [0, 0, 0, 1, 0])], "c2"),
    "six board regressions": ({("fam", f"c{i}", n): {"d3": 1} for i in range(3) for n in (2, 3)}, (), "c3"),
    "a family below the baseline": ({("fam", "c0", 2): {"fit2d": ["ValueError no line"]}}, (), "c3"),
    "a GCPW coupon past 1.5 %": ({("fixtures", "coupon_dense", 3): {"fit2d": [1.6]}}, (), "c4"),
    "microstrip moved": ({("fixtures", "coupon_ms_masked", 2): {"fit2d": [0.201]}}, (), "c4"),
}


@pytest.mark.parametrize(("over", "axes_over", "broken"), CASES.values(), ids=CASES)
def test_each_acceptance_condition_rejects_its_case(over, axes_over, broken):  # Review Focus 4
    r = meshcal.accept(BASE, axes(), table({**LOST, **over}), axes(axes_over))
    assert not r[broken] and not r["pass"]


def test_a_missing_row_or_axis_counts_as_failed():  # Review Focus 4
    rows, ax = table(LOST), axes()
    del rows[("fam", "c1", 2)], ax["2d"]["facing|1"]
    r = meshcal.accept(BASE, axes(), rows, ax)
    assert (r["c2"], r["c3"], r["regressions"], r["families_below"]) == (False, False, ["fam/c1 n=2"], ["fam"])


def test_a_regression_the_family_wins_back_and_an_old_axis_failure_are_no_rejection():
    traded = table({("fam", "c0", 2): {"fit2d": [3.4]}})  # c0 n = 2 lost, c4 n = 3 won: the family keeps its count
    r = meshcal.accept(BASE, axes(), traded, axes([("5d", "facing|2", [1, 1, 1, 1, 0])]))
    assert r["pass"] and r["regressions"] == ["fam/c0 n=2"] and r["axes_regressions"] == {"unset": 0, "2d": 0, "5d": 0}


def test_the_winner_has_the_most_passes_then_the_smallest_gcpw_coupon_fit2d_then_the_grid_order():  # condition 5
    res = [{"id": "a", "pass": True, "passes": 10, "gcpw_max": 0.5},
           {"id": "b", "pass": True, "passes": 11, "gcpw_max": 1.05},
           {"id": "c", "pass": True, "passes": 11, "gcpw_max": 0.71},
           {"id": "d", "pass": False, "passes": 99, "gcpw_max": 0.1},
           {"id": "e", "pass": True, "passes": 11, "gcpw_max": 0.71}]
    assert meshcal.choose(res) == "c" and meshcal.choose(res[:1] + res[3:4]) == "a" and meshcal.choose(res[3:4]) is None


def test_the_slot_role_is_plan6s_winner():  # the constants are the searched candidate's, as the grid writes them
    c = next(c for c in meshcal.CANDIDATES if c["id"] == "1-6_none_served")
    assert (rule.SLOT_IN, rule.SLOT_GATE, rule.SLOT_SERVED) == (c["slot_in"], c["gate"], c["served"])


def fake_harness(tmp_path, monkeypatch):
    """r1's harness as small files that meshcal.PINNED pins, and meshcal._call writing each output: BASE's rows and
    axes() for every tree, or `bad`'s text for a name in it. Returns (the folder, the calls, bad)."""
    r1, calls, bad = tmp_path / "r1", [], {}
    frozen = {"all_r6.jsonl": "".join(json.dumps(r) + "\n" for r in BASE.values()),
              **{f"ax/a_head{s}.json": json.dumps(axes()["unset"]) for s in ("", "_h2", "_h5")}}
    for name in meshcal.PINNED:
        (r1 / name).parent.mkdir(parents=True, exist_ok=True)
        (r1 / name).write_text(frozen.get(name, "# r1's script\n"), encoding="utf-8")
    monkeypatch.setattr(meshcal, "PINNED", {n: hashlib.sha256((r1 / n).read_bytes()).hexdigest() for n in meshcal.PINNED})

    def call(cmd, env):
        out, src = Path(cmd[2]), Path(env.get("KRS_SRC") or Path(env["KRS_TREE"]) / "src")
        tail = (src / "kicad_rf_studio" / "core" / "mesh" / "rule.py").read_text(encoding="utf-8").splitlines()[-1]
        calls.append((out.name, env.get("KRS_REACH"), env.get("KRS_AXIS_H"), tail))
        out.write_text(bad.get(out.name, frozen["all_r6.jsonl" if out.suffix == ".jsonl" else "ax/a_head.json"]),
                       encoding="utf-8")

    monkeypatch.setattr(meshcal, "_call", call)
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    monkeypatch.setattr(p0, "code_id", lambda: "tree")
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, "unused")
    return r1, calls, bad


OFF = ["off.jsonl", "off-unset.json", "off-2d.json", "off-5d.json"]


def test_the_run_refuses_a_changed_harness_and_a_baseline_unlike_r1s(tmp_path, monkeypatch, fake):  # Review Focus 2
    r1, calls, bad = fake_harness(tmp_path, monkeypatch)
    (r1 / "ax" / "axes.py").write_text("# changed after the plan's commit\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        meshcal.run(r1, tmp_path / "boards", tmp_path, meshcal.CANDIDATES[:1])
    assert "ax/axes.py" in str(e.value) and calls == []
    (r1 / "ax" / "axes.py").write_text("# r1's script\n", encoding="utf-8")
    bad["off-2d.json"] = json.dumps(axes([("2d", "facing|1", [0, 0, 0, 1, 0])])["2d"])
    with pytest.raises(SystemExit) as e:
        meshcal.run(r1, tmp_path / "boards", tmp_path, meshcal.CANDIDATES[:1])
    assert "a_head_h2.json" in str(e.value) and [c[0] for c in calls] == OFF


def test_the_shakedown_stops_the_run_before_any_candidate(tmp_path, monkeypatch, fake):  # Review Focus 2
    r1, calls, bad = fake_harness(tmp_path, monkeypatch)
    bad["shakedown-5d.json"] = json.dumps(axes([("5d", "facing|1", [0, 1, 0, 0, 0])])["5d"])
    with pytest.raises(SystemExit) as e:
        meshcal.run(r1, tmp_path / "boards", tmp_path, meshcal.CANDIDATES[:1])
    assert meshcal.SHAKE in str(e.value) and [c[0] for c in calls] == [*OFF, *(f"shakedown-{h}.json" for h in meshcal.H)]
    assert calls[-1][3] == "SLOT_IN, SLOT_GATE, SLOT_SERVED = 0.16666666666666666, 0.0, True"


def test_the_run_resumes_on_the_same_code_and_a_spent_search_refuses(tmp_path, monkeypatch, fake):  # Review Focus 1
    r1, calls, _ = fake_harness(tmp_path, monkeypatch)
    cands = meshcal.CANDIDATES[:1]
    d = meshcal.run(r1, tmp_path / "boards", tmp_path, cands)
    one = [f"1-8_none_lone{s}" for s in (".jsonl", "-unset.json", "-2d.json", "-5d.json")]
    assert [c[0] for c in calls] == [*OFF, *(f"shakedown-{h}.json" for h in meshcal.H), *one]
    assert calls[0][:3] == ("off.jsonl", "6", None) and [c[2] for c in calls[1:4]] == ["", "2", "5"]
    assert calls[-4][3] == "SLOT_IN, SLOT_GATE, SLOT_SERVED = 0.125, 0.0, False"
    text = (tmp_path / "meshcal.json").read_text(encoding="utf-8")
    assert json.loads(text) == d and d["winner"] is None and d["base"]["passes"] == 26 and d["machine"]["steps"] == 3
    assert not any(s in text for s in (":\\", ":/", "NaN", "Infinity")) and "| 1-8_none_lone |" in (
        tmp_path / "meshcal.md").read_text(encoding="utf-8")
    (tmp_path / "meshcal.json").unlink()  # a crash after the last step: the rerun runs nothing again
    assert meshcal.run(r1, tmp_path / "boards", tmp_path, cands) == d and len(calls) == 11
    with pytest.raises(SystemExit) as e:
        meshcal.run(r1, tmp_path / "boards", tmp_path, cands)
    assert "spent" in str(e.value) and len(calls) == 11
