# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio import runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.kicad.stackup import kicad_default
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.waves import grid, layout
from kicad_rf_studio.core.project import load_project, save_project
from kicad_rf_studio.pipeline import expected_loss, load
from networks import star
from test_cli_cost import SEG, by_hand, fail, gcpw, new_project

F, _ = grid(915e6, 3, 1.1)


def coupon(tmp_path, preset="draft"):
    return new_project(tmp_path, "coupon_gcpw_pads", preset=preset)  # tests/test_cli_cost.py


def verdict_codes(run_dir):
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return {e["job"]: e["code"] for e in events if e["kind"] == "verdict"}


def only_run(data):
    """The one run folder a test's run made under the data folder `data`."""
    return next((data / "runs").iterdir())


def test_run_converges_and_records_its_results(tmp_path, calibrated):  # spec 6.1, 3.3, C-29
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    run_dir = Path(r["run_dir"])
    assert [(j["port"], j["verdict"]) for j in r["jobs"]] == [("P1", "converged"), ("P2", "converged")]
    assert r["jobs"][0]["t_cut"] == pytest.approx(9.31e-9, abs=0.1e-9) and r["jobs"][0]["residual_db"] <= -50
    assert all((run_dir / j["waves"]).is_file() for j in r["jobs"])
    assert r["model_hash"] == spec_hash(json.loads((run_dir / "model.json").read_text(encoding="utf-8")))
    assert (r["gates"], r["dt"], r["c_box"]) == ({"fit2d_limit": 0.03, "dt_floor": 0.8}, 1e-13, {})
    kinds = {json.loads(line)["kind"] for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()}
    assert kinds == {"message", "verdict", "cost", "progress", "result"}
    assert not (pj.parent / "project.json.lock").exists()
    # refreshed from openEMS's per-job speed: the fake's 5e7 × 2 threads = 1e8 cells/s a job, × the calibration's pool 2
    assert runs.load_settings()["machines"][runs.machine_key()]["aggregate_mcs"] == pytest.approx(200.0)


def test_results_record_the_preset_and_the_expected_loss(tmp_path, calibrated):  # C-25
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    assert (r["preset"], r["loss_expected"]) == ("draft", pytest.approx(0.00995, abs=3e-5))  # 20 mm, εeff 2.650


def test_a_run_that_keeps_no_s_leaves_the_previous_results(tmp_path, calibrated, monkeypatch, capsys):  # C-24
    monkeypatch.setenv("KRS_FAKE", "nan")
    pj = coupon(tmp_path, "normal")
    save_project(pj, {**load_project(pj), "results": {"jobs": []}})
    assert main(["run", str(pj)]) == 4
    assert load_project(pj)["results"] == {"jobs": []}
    assert any(line.startswith("0 of 2 jobs kept S, in ") for line in capsys.readouterr().out.splitlines())


@pytest.mark.parametrize(("kind", "code", "verdict"), [
    ("nan", 4, "E_JOB_DIVERGED"), ("tmax", 0, "W_JOB_T_MAX"), ("flat", 0, "W_JOB_FLAT"), ("growth", 4, "E_JOB_GROWTH")])
def test_each_verdict_through_run(tmp_path, calibrated, monkeypatch, kind, code, verdict):  # spec 6.3, R3-107
    monkeypatch.setenv("KRS_FAKE", kind)
    pj = coupon(tmp_path, "normal")  # the replays pin these at Normal
    assert main(["run", str(pj)]) == code
    assert verdict_codes(only_run(calibrated))[1] == verdict


def test_the_network_fake_records_the_waves_of_a_known_network(tmp_path, calibrated, monkeypatch):  # C-41, X-12
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = coupon(tmp_path, "normal")
    assert main(["run", str(pj)]) == 0
    p = load_project(pj)
    jobs = p["results"]["jobs"]
    assert [j["verdict"] for j in jobs] == ["converged"] * 2
    assert jobs[0]["t_cut"] == pytest.approx(4.5e-9, abs=0.1e-9)  # measured: 4.502 ns at Normal
    assert np.abs(layout(p, p["results"]).s - star(F, 2)).max() <= 1e-5


def test_a_crashed_job_is_unclassified_and_the_others_finish(tmp_path, capsys, calibrated, monkeypatch):  # RF 4
    monkeypatch.setenv("KRS_FAKE", "crash")  # past the converge cut, then exit 7 with no waves
    monkeypatch.setenv("KRS_FAKE_JOB", "2")
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 4
    run = only_run(calibrated)
    assert verdict_codes(run) == {1: "I_JOB_CONVERGED", 2: "W_JOB_UNCLASSIFIED"} and "results" not in load_project(pj)
    log = run / "job-2-P2" / "log.txt"
    assert any(line.startswith("P2: the worker ended") and str(log) in line for line in capsys.readouterr().out.splitlines())


def test_a_stop_file_stops_the_run_found_from_the_lock(tmp_path, calibrated, monkeypatch):  # C-26, spec 3.1
    monkeypatch.setenv("KRS_FAKE", "slow")
    pj = coupon(tmp_path)

    def stopper():
        while True:
            try:
                run_dir = Path(json.loads((pj.parent / "project.json.lock").read_text(encoding="utf-8"))["run_dir"])
                break
            except (OSError, ValueError):
                time.sleep(0.01)
        while not any(run_dir.glob("job-1-*/port_ut_1")):
            time.sleep(0.01)
        (run_dir / "STOP").write_text("")

    threading.Thread(target=stopper, daemon=True).start()
    assert main(["run", str(pj)]) == 4
    assert set(verdict_codes(only_run(calibrated)).values()) == {"W_JOB_STOPPED"} and "results" not in load_project(pj)
    assert not (pj.parent / "project.json.lock").exists()


def test_ctrl_c_in_the_job_phase_stops_the_run_and_frees_the_lock(tmp_path, calibrated, monkeypatch):  # RF 5
    monkeypatch.setenv("KRS_FAKE", "slow")
    real_sleep, fired = time.sleep, []

    def sleep(s):
        if not fired and any(calibrated.glob("runs/*/job-1-*/port_ut_1")):
            fired.append(1)
            raise KeyboardInterrupt
        real_sleep(s)

    monkeypatch.setattr(time, "sleep", sleep)
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 4 and not (pj.parent / "project.json.lock").exists()
    assert set(verdict_codes(only_run(calibrated)).values()) == {"W_JOB_STOPPED"} and "results" not in load_project(pj)


def test_a_second_ctrl_c_kills_at_once_and_the_jobs_are_recorded(tmp_path, calibrated, monkeypatch):  # final review M2
    # the second press, while run_jobs waited for the stopped jobs to write their data, escaped it: no verdicts, no
    # results, exit 130
    monkeypatch.setenv("KRS_FAKE", "slow")
    monkeypatch.setattr(runs, "free_ram_mb", lambda: 100.0)  # one job at a time: job 1 still runs at the second press
    real_sleep, fired = time.sleep, []

    def sleep(s):
        if len(fired) < 2 and any(calibrated.glob("runs/*/job-1-*/port_ut_1")):
            fired.append(1)
            raise KeyboardInterrupt
        real_sleep(s)

    monkeypatch.setattr(time, "sleep", sleep)
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 4 and len(fired) == 2
    assert set(verdict_codes(only_run(calibrated)).values()) == {"W_JOB_STOPPED"} and "results" not in load_project(pj)


@pytest.mark.parametrize(("edits", "code", "first"), [
    ({"lid_height_mm": None}, 2, render("E_LID_HEIGHT", refs="SH1")),
    ({"lid_height_mm": 2.5, "mesh": {"n": 3}}, 3, "The fine mesh (mesh.n 3) still misses the 2D reference on net RF_B")])
def test_run_stops_before_any_worker(tmp_path, capsys, calibrated, monkeypatch, edits, code, first):  # C-42
    pj = new_project(tmp_path, "lpf915")
    save_project(pj, {**load_project(pj), **edits})
    monkeypatch.setattr(subprocess, "Popen", fail)
    capsys.readouterr()
    assert main(["run", str(pj)]) == code
    assert any(line.startswith(first) for line in capsys.readouterr().out.splitlines())
    assert "results" not in load_project(pj)


def test_run_refuses_a_project_without_ports_or_a_reference(tmp_path, capsys, calibrated):  # O-6
    assert main(["run", str(new_project(tmp_path, "coupon_ms"))]) == 2
    assert capsys.readouterr().err == render("E_NO_PORTS") + "\n"
    pj = coupon(tmp_path)
    d = load_project(pj)
    d["ports"][0]["reference"] = None
    save_project(pj, d)
    assert main(["run", str(pj)]) == 2
    assert render("E_NO_REFERENCE", signal="TP1.1") in capsys.readouterr().out.splitlines()


def test_a_held_lock_refuses_the_run(tmp_path, capsys, calibrated):
    pj = coupon(tmp_path)
    (pj.parent / "project.json.lock").write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}))
    assert main(["run", str(pj)]) == 2 and "Another run of this project" in capsys.readouterr().err


def test_gate_limits_that_differ_are_recorded_and_said(tmp_path, capsys, calibrated):  # C-10
    pj = coupon(tmp_path)
    save_project(pj, {**load_project(pj), "gates": {"fit2d_limit": 0.05, "dt_floor": 0.8}})
    assert main(["run", str(pj)]) == 0
    out = capsys.readouterr().out.splitlines()
    limits = render("W_GATE_LIMITS", fit2d_limit="0.05", dt_floor="0.8")
    assert [out[i + 1] for i, line in enumerate(out) if line.startswith(("Gates passed", "P1: converged",
                                                                         "P2: converged"))] == [limits] * 3
    assert load_project(pj)["results"]["gates"] == {"fit2d_limit": 0.05, "dt_floor": 0.8}


def test_a_model_larger_than_free_ram_runs_one_job_at_a_time(tmp_path, capsys, calibrated, monkeypatch):  # spec 6.4
    monkeypatch.setattr(runs, "free_ram_mb", lambda: 100.0)
    assert main(["run", str(coupon(tmp_path))]) == 0
    out = capsys.readouterr().out.splitlines()
    ram = next(i for i, line in enumerate(out) if line.startswith("One job needs about"))
    assert ram < next(i for i, line in enumerate(out) if line.startswith("Running 2 jobs, 1 at once"))


def test_lpf915_runs_one_job_per_port_and_records_c_box(tmp_path, calibrated, monkeypatch):  # R3-095, C-18
    monkeypatch.setenv("KRS_FAKE", "tmax")
    pj = new_project(tmp_path, "lpf915")
    save_project(pj, {**load_project(pj), "lid_height_mm": 2.5})
    assert main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    assert sorted(d.name for d in Path(r["run_dir"]).glob("job-[1-9]*")) == [
        "job-1-P1", "job-2-P2", "job-3-C1", "job-4-L1", "job-5-C2", "job-6-C3"]
    assert set(r["c_box"]) == {"C1", "L1", "C2", "C3"}
    assert (r["preset"], r["loss_expected"]) == ("normal", pytest.approx(0.00451, abs=3e-5))  # 7.99 mm of sections


@pytest.mark.openems
def test_new_cost_run_on_the_pad_coupon(tmp_path, monkeypatch):  # spec 9.2: P = 2, M = 0, Draft, short T_max
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")  # a fresh machine: cost calibrates first
    pj = coupon(tmp_path)
    save_project(pj, {**load_project(pj), "t_max_s": 3e-10})
    assert main(["cost", str(pj)]) == 0 and main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    assert [j["verdict"] for j in r["jobs"]] == ["t_max", "t_max"] and len(r["model_hash"]) == 64
    for j in r["jobs"]:
        w = np.load(Path(r["run_dir"]) / j["waves"])
        assert w["u"].shape[0] == 2 and np.isfinite(w["u"]).all()
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules


# --- beyond the brief's tests ------------------------------------------------------------------------------------


def test_ctrl_c_before_the_jobs_exits_130_and_leaves_the_results(tmp_path, calibrated, ctrl_c_on_third_poll,
                                                                  monkeypatch):  # spec 6.1 step 6
    monkeypatch.setenv("KRS_FAKE", "hang")  # the setup job runs until the third poll's Ctrl+C
    pj = coupon(tmp_path)
    save_project(pj, {**load_project(pj), "results": {"jobs": []}})
    assert main(["run", str(pj)]) == 130
    assert load_project(pj)["results"] == {"jobs": []} and not (pj.parent / "project.json.lock").exists()


def test_a_setup_gate_blocks_the_run_and_leaves_the_results(tmp_path, capsys, calibrated, monkeypatch):  # C-15
    monkeypatch.setenv("KRS_FAKE_SETUP", json.dumps({"pec": [[1, 1, 1, 1], [1, 2, 1, 2]]}))
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 3
    assert render("E_PORT_SHORT", name="P1") in capsys.readouterr().out.splitlines()
    assert "results" not in load_project(pj)


def test_a_job_stopped_before_it_started_has_no_time_or_residual(tmp_path, calibrated, monkeypatch):  # P26
    monkeypatch.setenv("KRS_FAKE", "slow")
    monkeypatch.setattr(runs, "free_ram_mb", lambda: 100.0)  # one job at a time, so job 2 never starts
    real_sleep, fired = time.sleep, []

    def sleep(s):
        if not fired and any(calibrated.glob("runs/*/job-1-*/port_ut_1")):
            fired.append(1)
            raise KeyboardInterrupt
        real_sleep(s)

    monkeypatch.setattr(time, "sleep", sleep)
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 4
    run = only_run(calibrated)
    events = [json.loads(line) for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["params"] for e in events if e["kind"] == "verdict" and e["job"] == 2] == [
        {"port": "P2", "t_ns": None, "residual_db": None, "log": str(run / "job-2-P2" / "log.txt")}]
    assert "results" not in load_project(pj)


def test_the_expected_loss_takes_the_core_by_the_copper_and_skips_a_short(tmp_path, mini_board_file):  # C-25
    def loss(body):
        pj = by_hand(tmp_path / "p" / "project.json", mini_board_file(body), nets=("SIG",), stackup=kicad_default(0.8))
        return expected_loss(load(pj)[2], 915e6)

    top = loss(gcpw("F.Cu"))
    assert top > 0 and loss(gcpw("B.Cu")) == pytest.approx(top, rel=1e-3)  # B.Cu: the mask below, the core above
    short = SEG.format(5, 15, 35, 15, 0.3, "F.Cu", "SIG", "s") + SEG.format(5, 15.2, 35, 15.2, 0.3, "F.Cu", "GND", "g")
    assert loss(short) == 0.0  # GND overlaps SIG at its cut, so its one section has no εeff (ShortError)
