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


def events(run_dir, **match):
    """The events of `run_dir` whose fields equal `match` (all of them without one), in order."""
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [e for e in map(json.loads, lines) if all(e[k] == v for k, v in match.items())]


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


def end(pj, command, exit_code):
    return {"exit_code": exit_code, "command": command, "project": str(pj.resolve())}


def test_cost_writes_every_line_as_an_event_in_the_folder_it_is_given(tmp_path, calibrated, capsys):  # 5.2 items 3, 4
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    p = load_project(pj)
    save_project(pj, {**p, "board": {**p["board"], "sha256": "0" * 64}})  # a load note: W_BOARD_CHANGED
    capsys.readouterr()
    d = tmp_path / "gui runs" / "c"
    assert main(["cost", str(pj), "--run-dir", str(d)]) == 0
    got = events(d)
    assert [(e["kind"], e["code"]) for e in got[:4]] == [("message", "W_FILLS_AS_SAVED"), ("cost", "I_2D_HEADER"),
                                                         ("cost", "I_2D_SECTION"), ("message", "W_BOARD_CHANGED")]
    assert [e["code"] for e in got[4:9]] == ["I_COST_CELLS", "I_COST_SMALLEST", "I_COST_DT", "I_COST_TIME", "I_COST_RAM"]
    assert got[9]["code"].startswith("I_COST_DRIVER_") and {e["kind"] for e in got[4:10]} == {"cost"}
    assert len(got) == 11 and (got[10]["kind"], got[10]["code"], got[10]["params"]) == ("end", "I_END",
                                                                                          end(pj, "cost", 0))
    assert capsys.readouterr().out.splitlines() == [render(e["code"], **e["params"]) for e in got[:-1]]  # end: silent


def test_a_refusal_before_the_lock_is_a_message_then_the_end_event(tmp_path, calibrated, capsys):  # Review Focus 2
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    lock = runs.lock_file(pj)
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    d = tmp_path / "gui runs" / "r"
    capsys.readouterr()
    assert main(["run", str(pj), "--run-dir", str(d)]) == 2
    held = {"lock": str(lock), "run": "R", "started": "S"}
    assert [(e["kind"], e["code"], e["params"]) for e in events(d)] == [
        ("message", "E_LOCKED", held), ("end", "I_END", end(pj, "run", 2))]
    assert capsys.readouterr() == ("", render("E_LOCKED", **held) + "\n")
    portless, e = new_project(tmp_path, "coupon_ms"), tmp_path / "gui runs" / "e"  # by hand: no ports
    assert main(["run", str(portless), "--run-dir", str(e)]) == 2
    assert [x["code"] for x in events(e)] == ["E_NO_PORTS", "I_END"]


def test_a_command_typed_without_a_run_dir_ends_the_folder_it_made(tmp_path, calibrated):  # 5.2 item 3, A-13
    portless = new_project(tmp_path, "coupon_ms")  # by hand: no ports
    assert main(["cost", str(portless)]) == 0 and main(["run", str(portless)]) == 2
    assert not (calibrated / "runs").exists()  # neither made a folder, so neither left an event
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    assert main(["run", str(pj)]) == 0
    assert events(Path(load_project(pj)["results"]["run_dir"]))[-1]["params"] == end(pj, "run", 0)


def test_a_stop_during_setup_and_a_crash_end_with_their_exit_codes(tmp_path, calibrated, monkeypatch):  # 5.2 item 3
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    monkeypatch.setenv("KRS_FAKE", "hang")
    s = tmp_path / "gui runs" / "s"
    s.mkdir(parents=True)
    (s / "STOP").write_text("")  # the setup job never starts
    assert main(["run", str(pj), "--run-dir", str(s)]) == 130
    assert events(s)[-1]["params"] == end(pj, "run", 130) and runs.lock_holder(pj) is None

    def boom(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "simulate", boom)
    x = tmp_path / "gui runs" / "x"
    assert main(["run", str(pj), "--run-dir", str(x)]) == 1
    assert [(e["code"], e["params"]) for e in events(x)][-2:] == [
        ("E_INTERNAL", {"detail": "RuntimeError: boom"}), ("I_END", end(pj, "run", 1))]


def test_the_first_use_calibrates_inside_the_run_folder_under_its_stop(tmp_path, fake, monkeypatch):  # 5.2 item 9
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    d = tmp_path / "gui runs" / "c"
    assert main(["cost", str(pj), "--run-dir", str(d)]) == 0
    codes = [e["code"] for e in events(d)]
    assert (codes.index("I_2D_HEADER") < codes.index("I_CALIBRATING") < codes.index("I_CALIBRATED")
            < codes.index("I_COST_CELLS"))
    assert (d / "calibrate" / "model.json").is_file() and not (fake / "runs").exists()  # no calibrate-* folder
    runs.save_settings({})  # this machine uncalibrated again
    for command in ("cost", "run"):  # run and verify calibrate through simulate's prepare
        s = tmp_path / "gui runs" / f"s-{command}"
        s.mkdir()
        (s / "STOP").write_text("")
        assert main([command, str(pj), "--run-dir", str(s)]) == 130
        assert [e["code"] for e in events(s)][-2:] == ["I_CALIBRATING", "I_END"]
        assert (s / "calibrate" / "model.json").is_file() and "machines" not in runs.load_settings()


def test_a_word_parameter_stays_a_code_in_the_event_and_reads_as_its_term(tmp_path, capsys, fake, monkeypatch):
    # pt-BR design 5.1 and Stage 1 3.3: a fresh machine's calibration cannot load openEMS
    monkeypatch.setenv("KRS_FAKE_EXIT", "2")
    monkeypatch.delenv("CSXCAD_INSTALL_PATH", raising=False)
    pj, run_dir = new_project(tmp_path, "coupon_gcpw_pads", preset="draft"), tmp_path / "r"
    capsys.readouterr()
    assert main(["cost", str(pj), "--run-dir", str(run_dir)]) == 2
    (message,) = events(run_dir, code="E_OPENEMS_DLL")
    assert (message["kind"], message["params"]) == ("message", {"value": "T_UNSET",
                                                                "command": runs.install_command()})
    err = capsys.readouterr().err
    assert render("E_OPENEMS_DLL", **message["params"]) + "\n" in err and "T_" not in err
