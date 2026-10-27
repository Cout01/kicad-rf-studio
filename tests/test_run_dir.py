# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage 2's engine hooks (design 5.2): python -m kicad_rf_studio, --run-dir, the end event, cost's lines as events
and the calibration in the caller's run folder."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_cost import new_project


def events(run_dir):
    return [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_python_m_runs_the_cli(tmp_path):  # design 5.2 item 1
    nope = tmp_path / "nope.json"
    out = subprocess.run([sys.executable, "-X", "utf8", "-I", "-m", "kicad_rf_studio", "cost", str(nope)],
                         capture_output=True, text=True, encoding="utf-8")
    assert (out.returncode, out.stderr) == (
        2, render("E_PROJECT_UNREADABLE", path=str(nope), reason="file not found") + "\n")


@pytest.mark.parametrize("command", ["cost", "run", "verify"])
def test_the_run_dir_reaches_the_command_made_and_absolute(tmp_path, monkeypatch, command):  # design 5.2 item 2
    seen = []
    monkeypatch.setattr(pipeline, command, lambda path, run_dir=None: seen.append((path, run_dir)) or 0)
    monkeypatch.chdir(tmp_path)  # a relative DIR is read from here, and passed on absolute
    assert main([command, str(tmp_path / "p.json"), "--run-dir", str(Path("gui runs", "a"))]) == 0
    d = tmp_path / "gui runs" / "a"
    assert seen == [(tmp_path / "p.json", d)] and d.is_dir()


def test_a_run_dir_that_cannot_be_used_is_refused(tmp_path, capsys):  # every refusal a code (Stage 1 §8)
    (tmp_path / "f").write_text("")
    held = tmp_path / "held"
    held.mkdir()
    (held / "events.jsonl").write_text("{}\n", encoding="utf-8")  # another run's folder
    for d, why in ((tmp_path / "f" / "d", "already exists as a file"), (held, "already holds a run")):
        assert main(["cost", str(tmp_path / "p.json"), "--run-dir", str(d)]) == 2
        assert capsys.readouterr().err == render("E_RUN_DIR", path=str(d), reason=why) + "\n"
    assert (held / "events.jsonl").read_text(encoding="utf-8") == "{}\n"  # nothing added to it, ever


def test_cost_and_run_use_the_run_folder_they_are_given(tmp_path, calibrated):  # design 5.1, 5.2 item 2
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    c, r = tmp_path / "gui runs" / "c", tmp_path / "gui runs" / "r"
    assert main(["cost", str(pj), "--run-dir", str(c)]) == 0
    assert (c / "model.json").is_file() and (c / "job-0-setup" / "setup.json").is_file()
    assert main(["run", str(pj), "--run-dir", str(r)]) == 0  # r exists already: cli.main made it
    assert load_project(pj)["results"]["run_dir"] == str(r) and (r / "job-1-P1" / "waves.npz").is_file()
    assert not (calibrated / "runs").exists()  # no folder of their own
