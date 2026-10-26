# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import numpy as np
import pytest

import p0
import privacy_gate as gate
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.post.chain import terminate, with_box
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import load_project, save_project
from p0b import harness
from test_p0 import in_process

F, _ = grid(915e6, 3, 1.1)


def skewed(f):
    """A passive, reciprocal 6-port whose ports differ (each its own line): networks.star is symmetric in its ports,
    so on it the A/B design only sees C1 + L1 and C2 + C3, and the four C_p cannot be told apart."""
    a, tau = np.array([0.95, 0.94, 0.96, 0.93, 0.97, 0.92]), np.array([0.20, 0.25, 0.10, 0.35, 0.15, 0.30]) * 1e-9
    g = a * np.exp(-2j * np.pi * np.asarray(f)[:, None] * tau)
    return g[:, :, None] * (2 / 6 * np.ones((6, 6)) - np.eye(6)) * g[:, None, :]


P0A = {"rows": [{"verdict": "converged", "growth_db": 0.0}], "pad": {"jobs": [{"verdict": "converged", "growth_db": 0.0}]},
       "stray": {"dt_ratio": 0.45, "trips": True},
       "decisions": {"dt_floor": {"min_ratio": 0.92, "stray_ratio": 0.45, "stray_trips": True}}}


def test_the_p0b_projects_are_fresh_projects_with_their_edits(p0_out, monkeypatch):  # D-32, D-9
    monkeypatch.setattr(p0, "cli", in_process)
    b5, b4, b6 = (load_project(harness.project(p0_out, r)) for r in ("B5", "B4", "B6"))
    assert (b5["mesh"], b5["gates"]["fit2d_limit"], b5["lid_height_mm"]) == ({"n": 3, "reach_h": 6.0}, 0.05, 2.5)
    assert b4["allow_curve_port"] is True and b6["mesh"] == {"n": 2, "reach_h": 6.0}
    assert (p0_out / "boards" / "lpf915-45.kicad_pcb").is_file()
    pj = harness.project(p0_out, "B5")
    d = load_project(pj)
    d["mesh"]["n"] = 2  # an interruption between new and the edits
    save_project(pj, d)
    assert load_project(harness.project(p0_out, "B5"))["mesh"]["n"] == 3


def test_the_empty_box_fit_recovers_the_box_capacitances():  # D-35; r7 §3.5
    refs, empty = ["C1", "L1", "C2", "C3"], {"A": ["C1", "L1"], "B": ["C2", "C3"]}
    c_box = {"C1": 2.388e-15, "L1": 2.735e-15, "C2": 1.397e-15, "C3": 1.390e-15}  # lpf915 at n = 2
    true = {"C1": 1.4e-15, "L1": 3.2e-15, "C2": 1.9e-15, "C3": 0.9e-15}
    w, s = 2 * np.pi * F, skewed(F)

    def closed(run):
        zk = np.stack([1 / (1j * w * true[r]) if r in empty[run] else with_box(np.full(len(F), 50.0 + 0j), F, true[r])
                       for r in refs], -1)
        return terminate(s, [0, 1], zk, F)

    fitted, cond = harness.fit_cp(s, F, c_box, refs, {run: closed(run) for run in empty}, empty)
    assert {r: round(v * 1e15, 3) for r, v in fitted.items()} == {r: round(v * 1e15, 3) for r, v in true.items()}
    assert 1 <= cond < 1e3


def test_the_k_sweep_inductances_give_back_their_k():  # D-39
    dt, c = 5.4043e-14, 2.0e-15
    assert [k for k, _ in harness.kmax_values(dt, c)] == [0.35, 0.40, 0.45, 0.48, 0.50, 0.55]
    for k, l in harness.kmax_values(dt, c):
        assert dt / (2 * math.sqrt(l * c)) == pytest.approx(k, rel=1e-12)


def test_the_p0b_rules():  # D-30, D-33, D-34, D-37..D-39, D-44; O-11; PF-26, PF-28, PF-31; RF 2
    ok = {"ds21_db_f0": 0.05, "ds11_f0": 0.01, "ds_max": 0.02, "nulls": []}
    verdicts = {"B1": ["converged"] * 6, "B2": ["converged"] * 2, "B3": ["converged"] * 4, "B4": ["converged"] * 6,
                "B5": ["converged"] * 6, "B6": ["converged"] * 6, "p0a": ["converged"] * 16}
    sweep = [{"k": k, "verdict": "t_max", "growth_db": 0.0} for k in harness.K_SWEEP[:4]] + [
        {"k": 0.50, "verdict": "growth", "growth_db": 25.0}, {"k": 0.55, "verdict": "diverged", "growth_db": 40.0}]
    m = {"consistency": ok, "tx": ok, "reach": {"ds21_db_f0": 0.02, "ds11_f0": 0.005, "ds_max": 0.008, "nulls": []},
         "verdicts": verdicts, "growth_db": [0.0, 3.2], "kmax": sweep, "emerge": {"verdict": "pass", "reasons": []},
         "dt_ratios": {"p0a_min": 0.92, "B1": 1.05, "B5": 1.01}, "stray": {"dt_ratio": 0.45, "trips": True}}
    d = harness.decide(m)
    assert (d["verdict"]["value"], d["tx"]["pass"], d["reach"]["confirmed"], d["growth"]["confirmed"]) == (
        "pass", True, True, True)
    assert (d["kmax"]["confirmed"], d["kmax"]["k_max"], d["dt_floor"]["confirmed"]) == (True, 0.45, True)
    low = [{**s, "verdict": "growth"} if s["k"] == 0.45 else s for s in sweep]
    assert harness.decide({**m, "kmax": low})["kmax"]["k_max"] == pytest.approx(0.405)
    creeping = [{**s, "growth_db": 14.0} if s["k"] == 0.48 else s for s in sweep]  # t_max, still rising
    d = harness.decide({**m, "kmax": creeping})
    assert (d["kmax"]["confirmed"], d["kmax"]["k_max"], d["growth"]["sweep_caught"]) == (
        False, pytest.approx(0.432), False)
    calm = [{**s, "verdict": "t_max", "growth_db": 0.0} for s in sweep]  # nothing diverged: growth not exercised
    d = harness.decide({**m, "kmax": calm})
    assert (d["kmax"]["confirmed"], d["growth"]["confirmed"]) == (True, False)
    assert not harness.decide({**m, "reach": {**m["reach"], "ds_max": 0.011}})["reach"]["confirmed"]  # PF-28
    assert not harness.decide({**m, "growth_db": [10.5]})["growth"]["confirmed"]
    assert not harness.decide({**m, "verdicts": {**verdicts, "p0a": ["growth"]}})["growth"]["confirmed"]
    assert not harness.decide({**m, "dt_ratios": {**m["dt_ratios"], "B5": 0.84}})["dt_floor"]["confirmed"]
    one_t_max = {**verdicts, "B1": ["converged"] * 5 + ["t_max"]}
    assert harness.decide({**m, "verdicts": one_t_max})["verdict"]["value"] == "fail"
    assert harness.decide({**m, "verdicts": one_t_max, "emerge": None})["verdict"]["value"] == "fail"  # PF-31
    flat_b2 = {**verdicts, "B2": ["converged", "flat"]}
    assert harness.decide({**m, "verdicts": flat_b2})["consistency"]["verify_converged"] is False
    inconclusive = {"verdict": "inconclusive", "reasons": ["coupon_gcpw z0 -5.20 %"]}
    assert harness.decide({**m, "emerge": inconclusive})["verdict"] == {"value": "pass", "fails": [],
                                                                        "emerge_accepted": True}
    assert harness.decide({**m, "emerge": inconclusive, "consistency": {**ok, "ds_max": 0.05}})["verdict"]["value"] == "fail"
    assert harness.decide({**m, "emerge": None})["verdict"]["value"] == "pending"
    unsolved = {"verdict": "inconclusive", "reasons": ["coupon_gcpw z0 -5.20 %", "EMerge 60 um not solved"]}
    assert harness.decide({**m, "emerge": unsolved})["verdict"] == {"value": "pending", "fails": [],
                                                                    "emerge_accepted": False}  # PF-26
    assert harness.decide({**m, "emerge": {"verdict": "fail", "reasons": []}})["verdict"]["value"] == "fail"
    assert harness.decide({**m, "tx": {**ok, "ds_max": 0.04}})["verdict"]["value"] == "pass"  # the twin decides the TX side only


def test_p0b_on_the_fake_worker_writes_a_plain_private_free_gate_json(p0_out, monkeypatch):  # D-40, D-51; RF 3
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)  # verify's cells: the fake's dump is empty
    # P0-B ran B4 (lpf915-45) before P0-A's staircase refusal landed (D-27, PF-57); the harness runs as it ran then
    monkeypatch.setattr(pipeline, "GEOMETRY_GATES", ("E_OPEN_IN_ROI", "E_SHORT_IN_ROI"))
    p0.save(p0_out / "p0a" / "p0a.json", P0A)
    assert harness.main(["--out", str(p0_out)]) == 0  # every step, then p0b.json
    text = (p0_out / "p0b" / "p0b.json").read_text(encoding="utf-8")
    data = json.loads(text)
    json.dumps(data, allow_nan=False)
    assert gate.scan_text(text, [], generic=True) == []
    # PF-31: the fake's verify 2-port is networks.star(F, 2), not the 6-port closed by the parts, so consistency fails,
    # and only it; with it passing, the verdict is pending, since there is no emerge.json yet
    d, same = data["decisions"], {"ds21_db_f0": 0.0, "ds11_f0": 0.0, "ds_max": 0.0}
    assert (d["verdict"]["value"], d["consistency"]["pass"], d["consistency"]["verify_converged"],
            len(d["verdict"]["fails"])) == ("fail", False, True, 1)
    assert harness.decide({**data, "consistency": {**data["consistency"], **same}})["verdict"]["value"] == "pending"
    b1 = data["evidence"]["B1"]
    assert b1["ok"] and all(isinstance(j[key], bool) for j in b1["jobs"] for key in ("event", "abort", "order"))
    assert [s["k"] for s in data["kmax"]] == list(harness.K_SWEEP)


def test_a_step_that_raises_is_logged_and_skipped_and_the_others_still_run(p0_out, monkeypatch, capsys):  # D-6
    monkeypatch.setattr(p0, "cli", in_process)

    def cli_run(pj, command):  # B1's run crashes; B4's stores a stand-in
        if pj.parent.name == "B1":
            raise RuntimeError("B1 crashed")
        return {"exit": 0, "run_dir": None, "jobs": None, "wall_s": None}

    monkeypatch.setattr(p0, "cli_run", cli_run)
    assert harness.main(["--out", str(p0_out), "--only", "B1,B2,B3,B4,kmax"]) == 1
    assert [path.stem for path in (p0_out / "steps").glob("*.json")] == ["p0b-B4"]
    out, err = capsys.readouterr()  # the steps after B1 that need its run are logged, B4 is not
    assert "p0b: failed: B1, B2, B3, kmax" in out and err.count("RuntimeError: p0b: B1 has no record yet") == 3
