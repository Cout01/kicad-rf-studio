# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

import p0
import p3a
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.kicad.stackup import kicad_default
from kicad_rf_studio.core.messages import english, render
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.chain import with_box, z_part
from kicad_rf_studio.core.post.outputs import COLUMNS, LIMITS, summary_csv, summary_png
from kicad_rf_studio.core.post.waves import grid, layout
from kicad_rf_studio.core.project import GATES, load_project, parts, save_project
from kicad_rf_studio.pipeline import command_line, expected_loss, load, write_outputs
from networks import C_BOX, read_s, star, synth_records, terminate_np, write_s2p
from test_cli_cost import FIX, SEG, by_hand, fail, gcpw, new_project
from test_post_chain import LPF, M0402
from test_post_waves import fake_run, port

F, _ = grid(915e6, 3, 1.1)


def coupon(tmp_path, preset="draft"):
    return new_project(tmp_path, "coupon_gcpw_pads", preset=preset)  # tests/test_cli_cost.py


def verdict_codes(run_dir):
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return {e["job"]: e["code"] for e in events if e["kind"] == "verdict"}


def only_run(data):
    """The one run folder a test's run made under the data folder `data`."""
    return next((data / "runs").iterdir())


def lpf_project(tmp_path):
    """lpf915's project.json, from a copy of the board (a test may re-save it), with a 2.5 mm lid."""
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes((FIX / "lpf915.kicad_pcb").read_bytes())
    assert main(["new", str(board), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "--lid-height", "2.5",
                 "-o", str(tmp_path / "lpf915")]) == 0
    return tmp_path / "lpf915" / "project.json"


def lpf_run(tmp_path, monkeypatch):
    """lpf915 run on the network fake: its project.json."""
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = lpf_project(tmp_path)
    assert main(["run", str(pj)]) == 0
    return pj


def lpf_loads(model, **values):
    """Z_part ∥ C_BOX of lpf915's part ports in job order, at `values` (F or H) or the board's."""
    v = {**{ref: value for ref, _, value in LPF}, **values}
    return np.stack([with_box(z_part(ref[0], v[ref], model, F), F, C_BOX) for ref in v], -1)


def result_codes(run_dir):
    events = [json.loads(line) for line in (Path(run_dir) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return [e["code"] for e in events if e["kind"] == "result"]


def test_run_converges_and_records_its_results(tmp_path, calibrated, monkeypatch):  # spec 6.1, 3.3, C-29
    monkeypatch.setattr(runs, "sizing", lambda entry, cells: (2, 2))
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
    assert kinds == {"message", "verdict", "cost", "progress", "result", "end"}
    assert not (pj.parent / "project.json.lock").exists()
    entry = runs.load_settings()["machines"][runs.machine_key()]
    # the fake's 5e7 × 2 threads a job, at 2 jobs
    assert (entry["aggregate_mcs"], entry["levels"]) == (400.0, {"2": pytest.approx(100.0)})


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


def test_a_partial_stats_file_counts_as_missing(tmp_path, calibrated, monkeypatch):  # C1
    # a job killed while openEMS wrote openEMS_stats.txt ended the run E_INTERNAL: read_stats raised IndexError
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setenv("KRS_FAKE_STATS", "partial")
    pj = coupon(tmp_path, "normal")
    assert main(["run", str(pj)]) == 0
    assert [j["verdict"] for j in load_project(pj)["results"]["jobs"]] == ["converged"] * 2


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
        with np.load(Path(r["run_dir"]) / j["waves"]) as w:
            assert w["u"].shape[0] == 2 and np.isfinite(w["u"]).all()
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules


def test_run_writes_the_outputs_of_a_known_network(tmp_path, calibrated, monkeypatch):  # spec 3.2, 7.3, C-26..C-30
    pj = lpf_run(tmp_path, monkeypatch)
    out = pj.parent / "results"
    assert sorted(p.name for p in out.iterdir()) == ["chain.s2p", "layout.s6p", "summary.csv", "summary.png"]
    assert np.abs(read_s(out / "layout.s6p") - star(F, 6)).max() <= 1e-5
    assert np.abs(read_s(out / "chain.s2p") - terminate_np(star(F, 6), [0, 1], lpf_loads(M0402))).max() <= 1e-5
    assert result_codes(load_project(pj)["results"]["run_dir"]) == [
        "I_RESULTS", "I_BASIS", "I_MARKER", "I_MARKER", "I_HR", "I_MARKER", "I_HR", "I_PASSIVITY", "I_RECIPROCITY",
        "W_LOSS_BUDGET", "I_WHAT_IF", "I_OUTPUTS", *LIMITS]  # the star's lines lose 19 % or more
    assert "far_field" not in load_project(pj)["results"]  # a v1 run's results gain no key


def test_a_single_trace_writes_its_two_port_and_summary(tmp_path, calibrated, monkeypatch):  # spec 7.3, C-31, C-24
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 0
    out = pj.parent / "results"
    assert sorted(p.name for p in out.iterdir()) == ["layout.s2p", "summary.csv", "summary.png"]
    assert np.abs(read_s(out / "layout.s2p") - star(F, 2)).max() <= 1e-5
    rows = list(csv.reader(io.StringIO((out / "summary.csv").read_text(encoding="utf-8"))))
    assert rows[0] == list(COLUMNS) and rows[72][1] == "f0" and rows[72][7:11] == ["", "", "", ""]
    assert result_codes(load_project(pj)["results"]["run_dir"]) == [
        "I_RESULTS", "I_BASIS", "I_MARKER_TRACE", "I_MARKER_TRACE", "I_HR_TRACE", "I_MARKER_TRACE", "I_HR_TRACE",
        "I_PASSIVITY", "I_RECIPROCITY", "W_LOSS_BUDGET", "I_OUTPUTS", *LIMITS]
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    monkeypatch.setenv("KRS_FAKE", "nan")
    assert main(["run", str(pj)]) == 4  # a run that keeps no S leaves results/ as it was
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_t_max_jobs_are_reduced_whole_and_flagged(tmp_path, calibrated, monkeypatch):  # R-4, X-2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = coupon(tmp_path)
    save_project(pj, {**load_project(pj), "t_max_s": 3e-9})  # T_max before 2·t0 + 1 ns: the rule cannot converge
    assert main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    assert [(j["verdict"], j["t_cut"]) for j in r["jobs"]] == [("t_max", None)] * 2
    assert result_codes(r["run_dir"])[:4] == ["I_RESULTS", "I_BASIS", "W_JOB_T_MAX", "W_JOB_T_MAX"]
    head = (pj.parent / "results" / "layout.s2p").read_text(encoding="ascii").split("#")[0]
    assert ", preset draft: P1 t_max at " in head and ", P2 t_max at " in head


def test_three_external_ports_get_their_touchstone_and_no_two_port_summary(tmp_path):  # C-31
    rec = synth_records(lambda f: star(f, 3), 3, 457.5e6, 3.0195e9, 1.73972e-13, 10e-9)
    results = {**fake_run(tmp_path, rec, [port("P1"), port("P2"), port("P3")]), "preset": "normal", "gates": GATES,
               "c_box": {}, "loss_expected": 0.0}
    ports = [{"name": f"P{k}", "signal": f"J{k}.1", "reference": {"pad": f"J{k}.2", "uuid": ""}} for k in (1, 2, 3)]
    project = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "ports": ports, "others": [],
               "chain": {"nets": ["A"], "series": [], "shunt": []}, "results": results}
    lines = write_outputs(tmp_path / "p" / "project.json", project, "c")
    assert sorted(p.name for p in (tmp_path / "p" / "results").iterdir()) == ["layout.s3p"]
    assert [c for c, _ in lines] == ["I_BASIS", "I_PASSIVITY", "I_RECIPROCITY", "W_NOT_TWO_PORT", "I_OUTPUTS", *LIMITS]
    assert lines[3] == ("W_NOT_TWO_PORT", {"ports": 3})


def test_a_narrow_band_s2p_leaves_the_layout_n_port(tmp_path, calibrated, monkeypatch, capsys):  # Review Focus 3
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = lpf_project(tmp_path)
    f = np.linspace(1e9, 3e9, 41)
    write_s2p(pj.parent / "c1.s2p", z_part("C", 100e-12, None, f), "series", f)
    d = load_project(pj)
    parts(d)["C1"]["s2p"] = {"file": "c1.s2p", "connection": "series"}
    save_project(pj, d)
    assert main(["run", str(pj)]) == 2
    assert "results" in load_project(pj)
    assert sorted(p.name for p in (pj.parent / "results").iterdir()) == ["layout.s6p"]
    out = capsys.readouterr().out.splitlines()
    assert render("E_S2P_BAND", ref="C1", path=str(pj.parent / "c1.s2p"), f_lo="1000.0", f_hi="3000.0", f1="457.5",
                  f2="3015.6") in out
    assert out[-len(LIMITS):] == [render(code) for code in LIMITS]  # spec 7.5: printed with every result


def test_a_held_output_file_still_prints_the_results_and_the_limits(tmp_path, calibrated, monkeypatch,
                                                                     capsys):  # final review F7, spec 7.5
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = lpf_project(tmp_path)
    real = os.replace

    def replace(src, dst):  # a spreadsheet holds summary.csv
        if Path(dst).name == "summary.csv":
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    capsys.readouterr()
    assert main(["run", str(pj)]) == 2
    run_dir = Path(load_project(pj)["results"]["run_dir"])  # the results are recorded
    codes = [json.loads(line)["code"] for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert codes[codes.index("I_RESULTS"):] == [
        "I_RESULTS", "I_BASIS", "I_MARKER", "I_MARKER", "I_HR", "I_MARKER", "I_HR", "I_PASSIVITY", "I_RECIPROCITY",
        "W_LOSS_BUDGET", "I_WHAT_IF", "E_RESULTS_WRITE", *LIMITS, "I_END"]  # no I_OUTPUTS
    out = capsys.readouterr().out.splitlines()
    assert render("E_RESULTS_WRITE", path=str(pj.parent / "results" / "summary.csv"), reason="permission denied",
                  command=command_line("kicad-rf-studio", "retune", str(pj))) in out
    assert out[-len(LIMITS):] == [render(code) for code in LIMITS]


def test_the_retune_is_labelled_what_if_until_p0c_passes(tmp_path, calibrated, monkeypatch, capsys):  # D-15, A-4
    pj = lpf_run(tmp_path, monkeypatch)
    label = render("I_WHAT_IF", command=command_line("kicad-rf-studio", "verify", str(pj)))
    assert "I_WHAT_IF" in result_codes(load_project(pj)["results"]["run_dir"])
    assert b"! Relative / what-if: " in (pj.parent / "results" / "chain.s2p").read_bytes()
    monkeypatch.setattr(pipeline, "RETUNE_VALIDATED", True)
    capsys.readouterr()
    assert main(["retune", str(pj)]) == 0
    assert label not in capsys.readouterr().out
    assert b"Relative / what-if" not in (pj.parent / "results" / "chain.s2p").read_bytes()


def test_a_classified_job_leaves_no_excitation_arrays(tmp_path, calibrated):  # D-17
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 0
    jobs = sorted(Path(load_project(pj)["results"]["run_dir"]).glob("job-[12]-*"))
    assert len(jobs) == 2 and all((j / "waves.npz").is_file() for j in jobs)
    assert [p for j in jobs for p in (j / "et", j / "ht") if p.exists()] == []


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


def test_the_setup_gate_blocks_metal_within_the_pml(tmp_path, calibrated):  # design 5.2: a setup gate; RF 5
    def blocked(spec, name):
        model = p0.model_of(spec)
        return [code for code, _ in pipeline.setup_gate(model, {"gates": GATES}, tmp_path / name,
                                                          runs.load_settings(), 2)[1]]

    s = p3a.dipole(p3a.SHORT_MM)
    assert "E_METAL_IN_PML" not in blocked(s, "clear")
    s["metal"]["curves"].append({"at": [0.0, 0.0], "z": [s["mesh"]["z"][0], -6.0]})
    assert blocked(s, "deep").count("E_METAL_IN_PML") == 1


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


def star_project(tmp_path, ext):
    """A run of `ext` external ports and one shunt part port, C1, reduced from the star's waves, and its project (no
    board): project.json's path and the project."""
    n = ext + 1
    rec = synth_records(lambda f: star(f, n), n, 457.5e6, 3.0195e9, 1.73972e-13, 10e-9)
    results = {**fake_run(tmp_path, rec, [*(port(f"P{k}") for k in range(1, n)), port("C1", part=True)]),
               "preset": "normal", "gates": GATES, "c_box": {"C1": C_BOX}, "loss_expected": 0.0}
    ports = [{"name": f"P{k}", "signal": f"J{k}.1", "reference": {"pad": f"J{k}.2", "uuid": ""}} for k in range(1, n)]
    c1 = {"ref": "C1", "pads": ["C1.1", "C1.2"], "nets": ["A", "GND"], "value": "1pF", "dnp": False, "role": "port",
          "model": None, "s2p": None}
    return tmp_path / "p" / "project.json", {
        "f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "ports": ports, "others": [],
        "classes": {"gnd_nets": ["GND"], "power_nets": [], "connectors": [], "shields": []},
        "chain": {"nets": ["A"], "series": [], "shunt": [c1]}, "results": results}


def test_three_external_ports_and_a_part_port_get_the_label_after_w_not_two_port(tmp_path):  # D-15, PF-6
    pj, project = star_project(tmp_path, 3)
    lines = write_outputs(pj, project, "c")
    assert [c for c, _ in lines][-len(LIMITS) - 3:] == ["W_NOT_TWO_PORT", "I_WHAT_IF", "I_OUTPUTS", *LIMITS]
    assert b"! Relative / what-if: " in (pj.parent / "results" / "chain.s3p").read_bytes()


def test_with_pt_br_active_chain_s2p_keeps_the_english_what_if_line(tmp_path, pt_br):  # pt-BR design 5.3
    pj, project = star_project(tmp_path, 2)
    write_outputs(pj, project, "c")
    what_if = {"command": command_line("kicad-rf-studio", "verify", str(pj))}
    assert render("I_WHAT_IF", **what_if) != english("I_WHAT_IF", **what_if)  # pt-BR is active
    assert ("! " + english("I_WHAT_IF", **what_if)).encode() in (pj.parent / "results" / "chain.s2p").read_bytes()


def test_write_outputs_writes_what_chain_results_holds(tmp_path):  # Stage 2 design 5.2 item 7, byte for byte
    pj, project = star_project(tmp_path, 2)
    res = pipeline.chain_results(pj, project)
    assert not (pj.parent / "results").exists()  # pure: the GUI calls it on a worker thread (design 5.4)
    assert (res.ext, res.refs, res.what_if, res.chain.shape) == ([0, 1], ["C1"], True, (len(F), 2, 2))
    assert [c for c, _ in res.lines] == ["I_BASIS", "I_MARKER", "I_MARKER", "I_HR", "I_MARKER", "I_HR",
                                         "I_PASSIVITY", "I_RECIPROCITY", "W_LOSS_BUDGET"]
    what_if = {"command": command_line("kicad-rf-studio", "verify", str(pj))}
    folder = pj.parent / "results"
    assert write_outputs(pj, project, "c") == [
        *res.lines, ("I_WHAT_IF", what_if),
        ("I_OUTPUTS", {"files": "chain.s2p, layout.s3p, summary.csv, summary.png", "folder": str(folder)}),
        *((code, {}) for code in LIMITS)]
    assert (folder / "summary.csv").read_bytes() == summary_csv(res.lay, res.chain, res.ideal, res.p_layout, 0.0)
    assert (folder / "summary.png").read_bytes() == summary_png(res.lay, res.chain, res.ideal, "p",
                                                                render("I_WHAT_IF", **what_if))


def test_chain_results_takes_the_layout_it_is_given(tmp_path, monkeypatch):  # Stage 2 design 5.3: the retune session
    pj, project = star_project(tmp_path, 2)
    res = pipeline.chain_results(pj, project)
    monkeypatch.setattr(pipeline, "layout", fail)  # the session holds the layout: never read again
    again = pipeline.chain_results(pj, project, lay=res.lay)
    assert again.lay is res.lay and np.array_equal(again.chain, res.chain) and again.lines == res.lines


def test_run_ports_runs_only_the_ports_it_is_given_to_their_t_max(tmp_path, calibrated):  # D-9: the harnesses' jobs
    project, board, geom, _ = load(coupon(tmp_path))
    model, run_dir = pipeline.build_model(project, board, geom), runs.run_dir_for("ports")
    setup, _, _ = pipeline.setup_gate(model, project, run_dir, runs.load_settings(), 2)
    done, speeds, _ = pipeline.run_ports(model, run_dir, setup, 2, 1, "draft", GATES, [2], 3e-9)  # 40 ns converges
    assert [(j["port"], j["verdict"], j["waves"]) for j in done] == [("P2", "t_max", "job-2-P2/waves.npz")]
    assert verdict_codes(run_dir) == {2: "W_JOB_T_MAX"} and speeds == [1e8]  # the fake's 5e7 × 2 threads
    assert [p.name for p in run_dir.glob("job-[1-9]*")] == ["job-2-P2"]


def test_run_ports_keeps_going_when_windows_holds_a_jobs_et(tmp_path, calibrated, monkeypatch):  # D-17
    project, board, geom, _ = load(coupon(tmp_path))
    model, run_dir = pipeline.build_model(project, board, geom), runs.run_dir_for("held")
    setup, _, _ = pipeline.setup_gate(model, project, run_dir, runs.load_settings(), 2)
    unlink = Path.unlink

    def held(path, missing_ok=False):  # an antivirus or the indexer still holds job 1's et
        if path.name == "et" and path.parent.name == "job-1-P1":
            raise PermissionError(13, "The process cannot access the file", str(path))
        unlink(path, missing_ok)

    monkeypatch.setattr(Path, "unlink", held)
    done, speeds, _ = pipeline.run_ports(model, run_dir, setup, 2, 2, "draft", GATES)
    assert [(j["port"], j["verdict"]) for j in done] == [("P1", "converged"), ("P2", "converged")]
    assert speeds == [1e8, 1e8]  # the fake's 5e7 × 2 threads, each job's
    assert [p.relative_to(run_dir).as_posix() for p in run_dir.glob("*/[eh]t")] == ["job-1-P1/et"]  # left in place
