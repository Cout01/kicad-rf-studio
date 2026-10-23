# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import io
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

import p0
from kicad_rf_studio import runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.spec import excitation
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import load_project
from kicad_rf_studio.stoprule import stop_rule
from networks import network_trace, star, terminate_np
from test_model_csx import TINY
from test_post_chain import M0402
from test_run import lpf_loads, lpf_run

F, _ = grid(915e6, 3, 1.1)


def in_process(*args):
    """p0.cli inside this process, so that the `fake` fixture's worker runs; other test files import it."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(list(args))
    return code, out.getvalue()


EXC40 = excitation({"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "t_max_s": 40e-9})
TWO = {**TINY, "excitation": EXC40,  # the fake's traces converge at about 10.7 ns at Normal; TINY's 1 ns never would
       "ports": [TINY["ports"][0], {**TINY["ports"][0], "name": "P2", "start": [3.0, 3.0, 0.0], "stop": [3.0, 3.0, 1.0],
                                    "nodes": [[3.0, 3.0, 0.0], [3.0, 3.0, 1.0], [3.0, 3.0, 0.0], [3.0, 3.0, 1.0]]}]}


def test_enter_points_every_child_at_the_p0_data_folder(tmp_path, monkeypatch):  # D-7
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, "unused")  # restored after the test
    out = p0.enter(tmp_path / "p0 ação")
    assert (os.environ["LOCALAPPDATA"], os.environ["XDG_DATA_HOME"]) == (str(out / "data"),) * 2
    assert runs.data_dir() == out / "data" / "kicad-rf-studio" and (out / "harness.lock").is_file()
    code, text = p0.cli("new", str(p0.FIX / "coupon_gcpw_pads.kicad_pcb"), "--start", "TP1.1", "--end", "TP2.1",
                        "--f0", "915MHz", "-o", str(out / "proj"))
    assert code == 0 and "εr" in text  # a real child process, its UTF-8 text intact
    assert p0.enter(out) == out  # this process holds the lock already


def test_one_harness_per_p0_folder(tmp_path, monkeypatch):  # D-5
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, "unused")
    out = tmp_path / "p0"
    out.mkdir()
    (out / "harness.lock").write_text(json.dumps({"pid": os.getppid(), "run_dir": "x", "started": "y"}),
                                      encoding="utf-8")  # a live process that is not this one
    with pytest.raises(KrsError) as e:
        p0.enter(out)
    assert e.value.code == "E_LOCKED"


def test_a_p0_folder_inside_a_git_work_tree_is_refused(tmp_path):  # D-7, D-46
    inside = (p0.FIX, p0.FIX / "lpf915.kicad_pcb", p0.ROOT / "no-such-folder" / "x", p0.ROOT / ".git" / "x")
    assert all(map(p0.inside_git, inside)) and not p0.inside_git(tmp_path)
    with pytest.raises(SystemExit):
        p0.enter(p0.ROOT / "build" / "p0")
    assert not (p0.ROOT / "build" / "p0").exists()


def test_a_step_runs_once_reruns_when_its_key_or_code_changes_and_a_crash_leaves_nothing(tmp_path, fake,
                                                                                          monkeypatch):  # D-6; RF 1
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    calls = []

    def work():
        calls.append(1)
        return {"x": np.float64(1.5), "ok": np.bool_(True), "a": np.arange(3), "z": np.complex128(1 + 2j),
                "nan": math.nan, "p": Path("job-1-P1") / "waves.npz"}

    first, again = p0.step(tmp_path, "s1", "k1", work), p0.step(tmp_path, "s1", "k1", work)
    assert calls == [1] and first["result"] == again["result"] == {"x": 1.5, "ok": True, "a": [0, 1, 2],
                                                                   "z": [1.0, 2.0], "nan": None, "p": "waves.npz"}
    p0.step(tmp_path, "s1", "k2", work)
    monkeypatch.setattr(p0, "code_id", lambda: "other")
    p0.step(tmp_path, "s1", "k2", work)
    assert calls == [1, 1, 1]

    def dies():
        raise RuntimeError("reboot")

    with pytest.raises(RuntimeError):
        p0.step(tmp_path, "s2", "k1", dies)
    assert sorted(p.name for p in (tmp_path / "steps").iterdir()) == ["s1.json"]


def test_a_step_is_marked_loaded_beside_another_process_or_a_failed_check(tmp_path, fake, monkeypatch):  # D-6
    assert any("pytest" in c for c in p0.command_lines())  # the real check sees this test run
    monkeypatch.setattr(p0, "command_lines", lambda: ["python -I -u -m kicad_rf_studio.worker job.json", "x.exe"])
    rec = p0.step(tmp_path, "s", "k", lambda: {})
    assert rec["loaded"] and (rec["load"]["workers"], rec["load"]["emerge"], rec["load"]["pytest"]) == (1, 0, 0)
    monkeypatch.setattr(p0, "command_lines", lambda: ["x.exe"])
    assert not p0.step(tmp_path, "t", "k", lambda: {})["loaded"]

    def broken():
        raise OSError("no powershell")

    monkeypatch.setattr(p0, "command_lines", broken)
    rec = p0.step(tmp_path, "u", "k", lambda: {})
    assert rec["loaded"] and rec["load"]["workers"] is None


def test_a_step_refuses_a_stop_file_and_a_data_folder_outside_its_p0_folder(tmp_path, fake, monkeypatch):  # D-7
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    (tmp_path / "STOP").write_text("")
    with pytest.raises(SystemExit):
        p0.step(tmp_path, "s", "k", lambda: {})
    (tmp_path / "STOP").unlink()
    with pytest.raises(SystemExit):
        p0.step(tmp_path / "elsewhere", "s", "k", lambda: {})  # the fake's data folder is not inside it
    assert not (tmp_path / "steps").exists()


def test_records_refuse_a_missing_step_or_two_codes(tmp_path, fake, monkeypatch):  # D-51; Global Constraints
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    p0.step(tmp_path, "a", "k", lambda: {})
    p0.step(tmp_path, "b", "k", lambda: {})
    assert p0.machine(p0.records(tmp_path, ["a", "b"]))["steps"] == 2
    assert set(p0.versions()) == {"commit", "code", "python", "openems", "csxcad", "os", "cpus"}
    with pytest.raises(SystemExit):
        p0.records(tmp_path, ["a", "c"])
    monkeypatch.setattr(p0, "code_id", lambda: "other")
    p0.step(tmp_path, "b", "k2", lambda: {})
    with pytest.raises(SystemExit):
        p0.records(tmp_path, ["a", "b"])
    assert p0.table([{"a": 1.23456, "b": None}], ["a", "b"]).splitlines()[2] == "| 1.235 | – |"


def test_run_model_runs_only_the_excited_ports_and_records_its_gates(tmp_path, calibrated):  # D-9, D-17
    run = p0.run_model(p0.model_of(TWO), "normal", "two", [1])
    (job,) = run["jobs"]
    assert (job["port"], job["verdict"]) == ("P1", "converged")
    assert [code for code, _ in run["blocked"]] == ["E_DT_FLOOR"]  # the fake's dt on 1 mm cells: recorded, not applied
    folder = p0.run_path(run["run_dir"])
    assert (folder / job["waves"]).is_file() and not (folder / job["job"] / "et").exists()
    assert not list(folder.glob("job-2-*")) and run["run_dir"] != p0.run_model(p0.model_of(TWO), "normal", "two", [])["run_dir"]


def test_a_stopped_run_is_never_recorded(tmp_path, calibrated, ctrl_c_on_third_poll, monkeypatch):  # D-6; RF 1
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    with pytest.raises(KeyboardInterrupt):
        p0.step(tmp_path, "s", "k", lambda: p0.run_model(p0.model_of(TWO), "normal", "two", [1]))
    assert not (tmp_path / "steps" / "s.json").exists()


def test_a_trace_round_trips_and_replays_to_its_live_cut(tmp_path, calibrated):  # D-40
    run = p0.run_model(p0.model_of(TWO), "normal", "two", [1])
    job = run["jobs"][0]
    path = p0.save_trace(p0.run_path(run["run_dir"]) / job["job"], 2, run["setup"]["dt"], 1, TWO["excitation"],
                         job["t_cut"], tmp_path / "t.npz")
    rec, k, exc, t_cut = p0.load_trace(path)
    assert sorted(np.load(path).files) == ["e", "exc", "i", "k", "t_cut", "t_i", "t_u", "te", "u"]
    assert (k, t_cut) == (0, job["t_cut"]) and stop_rule(rec, k, "normal", exc).t == job["t_cut"]
    assert path.stat().st_size <= 50_000


def test_a_trace_thins_only_its_energy_rows_and_refuses_probes_over_50_kb(tmp_path):  # D-40, PF-12, PF-13, PF-15
    rng = np.random.default_rng(0)

    def job(name, samples, rows):
        """A one-port job folder: `samples` random probe samples and `rows` random energy rows."""
        folder = tmp_path / name
        folder.mkdir()
        t = np.arange(samples) * 1e-11
        for q in "ui":
            lines = (f"{a}\t{b}\n" for a, b in zip(t, rng.normal(size=samples)))
            (folder / f"port_{q}t_1").write_text("".join(lines), encoding="utf-8")
        (folder / "openEMS_run_stats.txt").write_text(
            "".join(f"0.1\t{n}\t5e7\t{e}\n" for n, e in enumerate(rng.random(rows))), encoding="utf-8")
        return folder

    exc = {"f1": 1e9, "f2": 2e9, "t0": 1e-9}
    path = p0.save_trace(job("long", 100, 20_000), 1, 1e-12, 1, exc, None, tmp_path / "out" / "long.npz")
    rec, _, _, t_cut = p0.load_trace(path)
    assert len(rec.t_u) == len(rec.t_i) == 100 and 0 < len(rec.te) < 20_000 and t_cut is None  # NaN stored
    assert path.stat().st_size <= 50_000
    with pytest.raises(ValueError) as e:
        p0.save_trace(job("dense", 4_000, 10), 1, 1e-12, 1, exc, None, tmp_path / "dense.npz")
    assert "dense" in str(e.value) and not (tmp_path / "dense.npz").exists()


def test_s_of_cuts_or_replays_each_record_and_reduces_it():  # D-35, D-48
    traces = [(network_trace(2, k, EXC40["f1"], EXC40["f2"], 1e-13, 40e-9), k, EXC40, None) for k in (0, 1)]
    s, t_cut = p0.s_of(traces, F, "draft")
    assert np.abs(s - star(F, 2)).max() <= 1e-5 and (t_cut < 40e-9).all()
    assert p0.s_of(traces[:1], F, "draft")[0].shape == (len(F), 2, 1)
    whole, cuts = p0.s_of(traces, F)  # no preset: each record's own t_cut, here none, so whole
    assert np.abs(whole - star(F, 2)).max() <= 1e-5 and np.isnan(cuts).all()
    three = [(network_trace(3, k, EXC40["f1"], EXC40["f2"], 1e-13, 40e-9), k, EXC40, None) for k in (0, 1)]
    assert np.abs(p0.s_of(three, F, rows=[0, 1])[0] - star(F, 3)[:, :2, :2]).max() <= 0.05  # port 3 stays loaded


def test_the_closed_chain_of_a_run_at_its_models_ideal_values_cuts_and_boxes(tmp_path, calibrated,
                                                                             monkeypatch):  # D-34, D-37, D-43
    pj = lpf_run(tmp_path, monkeypatch)  # tests/test_run.py: lpf915 on the network fake
    results = load_project(pj)["results"]
    assert p0.model_key(pj) == results["model_hash"]
    f, s, k0 = p0.closed_chain(pj)
    assert k0 == 71 and np.abs(s - terminate_np(star(F, 6), [0, 1], lpf_loads(M0402))).max() <= 1e-5
    f, s, _ = p0.closed_chain(pj, ideal=True, f=F[[71, 213]])
    assert np.abs(s - terminate_np(star(F, 6), [0, 1], lpf_loads(None))[[71, 213]]).max() <= 1e-5
    same = p0.closed_chain(pj, cuts=[j["t_cut"] for j in results["jobs"]], cbox=results["c_box"])[1]
    assert np.abs(same - p0.closed_chain(pj)[1]).max() == 0


def test_criterion_1_reads_the_spec_limits_and_no_null_as_na():  # spec 9.4 criterion 1
    ok = {"ds21_db_f0": 0.1, "ds11_f0": 0.02, "ds_max": 0.03, "nulls": []}
    assert p0.criterion1(ok) == {"ds21_db_f0": True, "ds11_f0": True, "ds_max": True, "nulls": "n/a", "pass": True}
    assert not p0.criterion1({**ok, "ds_max": 0.0301})["pass"]
    assert p0.criterion1({**ok, "nulls": [{"f_hz": 2.7e9, "shift": -0.021}]})["nulls"] is False
    assert p0.criterion1({**ok, "nulls": [{"f_hz": 2.7e9, "shift": None}]})["pass"] is False  # an unmatched null


def test_the_small_helpers():  # D-16; P0-B's dotted edits
    assert p0.predicted_s(6, 4, 2_694_450, 5.4043e-14, 17e-9, 120.0) == pytest.approx(
        2 * 2_694_450 * (17e-9 / 5.4043e-14) / 120e6)
    assert p0.edit({"mesh": {"n": 2}}, {"mesh.n": 3, "gates.fit2d_limit": 0.05}) == {
        "mesh": {"n": 3}, "gates": {"fit2d_limit": 0.05}}
