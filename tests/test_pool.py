# SPDX-License-Identifier: GPL-3.0-or-later
import itertools
import json
import threading
import time
from pathlib import Path

import pytest

from kicad_rf_studio import runs
from kicad_rf_studio.core.messages import KrsError
from test_model_csx import TINY


def tiny_jobs(run_dir, n):
    runs.write_spec(run_dir, TINY)
    return [runs.write_job(runs.job_dir(run_dir, k, f"P{k}"), 1, "run", 1, TINY["excitation"]["t_max"])
            for k in range(1, n + 1)]


def most_at_once(log):
    marks = sorted((float(t), 1 if what == "start" else -1)
                   for what, _, t in (line.split() for line in log.read_text().splitlines()))
    return max(itertools.accumulate(d for _, d in marks))


def test_the_pool_runs_isolated_workers_at_most_pool_at_once(tmp_path, fake, monkeypatch):  # spec 6.1, C-25
    monkeypatch.setenv("KRS_FAKE_LOG", str(tmp_path / "times.txt"))
    run_dir = tmp_path / "run"
    js = tiny_jobs(run_dir, 3)
    out = runs.run_jobs(js, 2, run_dir, {"openems_dir": "/x/openEMS"})
    assert [out[j] for j in js] == [{"code": 0, "stopped": False}] * 3
    env = json.loads((js[0] / "env.json").read_text(encoding="utf-8"))
    assert Path(env.pop("cwd")).resolve() == js[0].resolve()
    assert env == {"isolated": 1, "OPENBLAS_NUM_THREADS": "1", "CSXCAD_INSTALL_PATH": "/x/openEMS"}
    assert most_at_once(tmp_path / "times.txt") <= 2


def test_a_stop_file_aborts_the_running_jobs(tmp_path, fake, monkeypatch):  # C-26
    monkeypatch.setenv("KRS_FAKE", "slow")
    run_dir = tmp_path / "run"
    js = tiny_jobs(run_dir, 3)
    threading.Timer(1.0, lambda: (run_dir / "STOP").write_text("")).start()
    out = runs.run_jobs(js, 2, run_dir, {})
    assert [out[j]["stopped"] for j in js] == [True, True, True]
    assert (js[0] / "ABORT").is_file() and not (js[2] / "log.txt").exists()  # the third never started


def test_ctrl_c_kills_a_job_in_setup_and_leaves_no_process(tmp_path, fake, ctrl_c_on_third_poll,
                                                           monkeypatch):  # Review Focus 5
    monkeypatch.setenv("KRS_FAKE", "hang")
    started = ctrl_c_on_third_poll
    run_dir = tmp_path / "run"
    t = time.monotonic()
    out = runs.run_jobs(tiny_jobs(run_dir, 1), 1, run_dir, {})
    assert list(out.values())[0]["stopped"] and time.monotonic() - t < 3 and started[0].poll() is not None


def test_watch_aborts_only_the_job_it_names(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("KRS_FAKE", "slow")
    run_dir = tmp_path / "run"
    js = tiny_jobs(run_dir, 2)
    out = runs.run_jobs(js, 2, run_dir, {}, watch=lambda job: job == js[0] and (job / "port_ut_1").exists())
    assert (js[0] / "ABORT").exists() and not (js[1] / "ABORT").exists()
    assert out[js[0]] == {"code": 0, "stopped": False}


@pytest.mark.parametrize(("exit_code", "code", "params"), [
    (2, "E_OPENEMS_DLL", {"value": "unset"}), (10, "E_SETUP_FAILED", {}), (7, "E_WORKER_FAILED", {"job": "setup",
                                                                                                 "exit_code": 7})])
def test_a_failed_job_maps_to_one_coded_error(tmp_path, fake, monkeypatch, exit_code, code, params):  # Review Focus 1
    monkeypatch.setenv("KRS_FAKE_EXIT", str(exit_code))
    monkeypatch.delenv("CSXCAD_INSTALL_PATH", raising=False)
    run_dir = tmp_path / "run"
    (job,) = tiny_jobs(run_dir, 1)
    out = runs.run_jobs([job], 1, run_dir, {})
    with pytest.raises(KrsError) as e:
        runs.check_job(job, out[job], "setup", {})
    log = {} if code == "E_OPENEMS_DLL" else {"log": str(job / "log.txt")}
    assert (e.value.code, e.value.params) == (code, {**params, **log})
    with pytest.raises(KeyboardInterrupt):
        runs.check_job(job, {"code": None, "stopped": True}, "setup", {})
