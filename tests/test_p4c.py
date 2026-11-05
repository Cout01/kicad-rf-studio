# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import pytest
from scipy.constants import c as C0

import p4c
from kicad_rf_studio.core.post.si import read
from test_p4 import gates  # noqa: F401 (the fixture)
from test_post_si import F, SE, line_s

STEP = {"z_lead": 50.0, "z_mid": 75.0, "gamma": 0.2, "t_edges_s": [2 * 38e-3 * math.sqrt(3.33) / C0,
        2 * 38e-3 * math.sqrt(3.33) / C0 + 2 * 36e-3 * math.sqrt(3.203) / C0], "delay_s": 36e-3 * math.sqrt(3.203) / C0}
REFS = {"steps": {s: {"2": STEP} for s in p4c.STEP_LINES}}


def pair(ds40=0.004, ds80=0.003, d40=1.0, cells=(1.4e6, 2.5e6, 6.0e6)):
    run = {"delay_s": 340e-12, "valid": True}
    return {"l40": {**run, "cells": cells[0], "delay_s": 340e-12 * d40}, "l80": {**run, "cells": cells[1]},
            "dfill": {**run, "cells": cells[2]}, "ds": {"l40": ds40, "l80": ds80}}


def decide(rule_now="l40", pairs=None, **row):
    steps = {s: {**STEP, "short": [False, False], "valid": True, **row} for s in p4c.STEP_LINES}
    return p4c.decide({"pairs": pairs or {p: pair() for p in p4c.PAIRS}, "steps": steps, "rule_now": rule_now,
                       "n_now": 2}, REFS)


def test_the_step_lines_readings_on_an_ideal_line():  # C-3: half heights in rho, not in ohms
    r = read(line_s([(50.0, 3.33, 38.0), (75.0, 3.203, 36.0), (50.0, 3.33, 38.0)], F), F, SE, 3.3)
    got = p4c.step_row(r, STEP)
    assert (round(got["z_lead"], 2), round(got["z_mid"], 2), round(got["gamma"], 4)) == (50.0, 74.99, 0.1999)
    assert got["delay_s"] == pytest.approx(STEP["delay_s"], rel=1e-4)  # 214.92 against 214.91 ps (ohms: -3.1 %)
    assert got["short"] == [False, False]  # 36 mm sections: no level marked short


def test_the_rule_decision():  # C-1, C-2: the lambda/80 arm runs with the rule's runs
    def rule(**kw):
        return decide(pairs={p: pair(**kw) for p in p4c.PAIRS})["rule"]
    assert rule() == "l40"
    assert rule(ds40=0.0101) == rule(d40=1.0051) == "l80"
    assert rule(ds40=0.023, cells=(1.4e6, 6.1e6, 6.0e6)) == "dfill"  # more cells than the d fill
    assert rule(ds40=0.023, ds80=0.0101) == "dfill"
    assert decide(rule_now="l80")["rule"] == "l80"  # the steps' delay refined it: the more refined of the two


def test_the_step_checks_inclusive_and_their_refinement():  # C-3: each refinement to the check it can move
    assert decide(z_mid=75.0 * 1.015)["verdict"]["value"] == "pass"
    assert decide(z_mid=75.0 * 1.0151)["verdict"]["value"] == "blocked"  # no cell along the line moves a plateau
    assert decide(gamma=0.2101)["verdict"]["value"] == "blocked"
    late = decide(delay_s=STEP["delay_s"] * 1.0201)
    assert (late["verdict"]["value"], late["refine"]) == ("fail", "l80")
    assert decide(rule_now="l80", delay_s=STEP["delay_s"] * 1.0201)["refine"] == "n3"
    assert decide(short=[True, False])["short_rule"] == "owner"  # the short-feature rule's true negative missed
    assert decide(valid=False)["verdict"]["fails"] == ["p4c_step75: valid", "p4c_step35: valid"]


def test_the_yee_grids_phase_error_is_what_the_lambda_80_arm_answers():  # C-2: recorded beside |dS|
    assert p4c.dispersion(0.429232, 3.0629, 60.0, 10e9) == pytest.approx(0.02273, abs=1e-4)
    assert p4c.dispersion(0.214616, 3.0629, 60.0, 10e9) == pytest.approx(0.005683, abs=5e-5)
    assert p4c.route_limit_mm(0.214616, 0.1, 3.0629, 10e9, 0.01) == pytest.approx(134.9, abs=0.5)  # against the d fill


def test_the_committed_references_hold_the_step_lines_and_the_rules_limits():  # C-2, C-3
    refs = json.loads(p4c.REFERENCES.read_text(encoding="utf-8"))
    step = refs["steps"]["p4c_step75"]["2"]
    assert (step["z_lead"], step["z_mid"]) == (pytest.approx(50.747, abs=0.02), pytest.approx(77.214, abs=0.02))
    assert refs["pairs"]["p4b_ms90"]["route_limit_mm"]["l80"] == pytest.approx(134.9, abs=1.0)


def test_p4c_runs_its_steps_and_writes_its_report(gates):  # design 5.11: the tool on the network fake
    assert p4c.main(["--out", str(gates), "--steps", "p4b_ms90-l40,p4b_ms90-dfill,p4c_step75,p4c_l90-l99"]) == 1
    with pytest.raises(SystemExit, match="never regenerated"):
        p4c.main(["--references"])
    assert p4c.main(["--out", str(gates)]) == 0
    text = (gates / "p4c" / "p4c.json").read_text(encoding="utf-8")
    result = json.loads(text)
    assert sorted(result["runs"]) == ["p4b_ms90-dfill", "p4b_ms90-l40", "p4c_step75"]
    assert result["pairs"][0]["ds"] == 0.0 and result["pairs_rule"] is None  # one S at both rules; p4c_l90 unrun
    assert result["verdict"]["value"] == "blocked" and "p4c_step75: z_mid" in result["verdict"]["fails"]  # no step
    assert '"reading"' not in text and '"project"' not in text
    assert (gates / "p4c" / "p4c.md").read_text(encoding="utf-8").startswith("## P4C-1 The pairs")
