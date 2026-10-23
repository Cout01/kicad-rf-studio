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
from kicad_rf_studio.core.messages import KrsError


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
