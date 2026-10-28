# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI's Qt-free logic (Stage 2 design 5.1, 5.3, 5.8): the detached start, the events tail, re-attach through the
lock and the end events, the project read off the GUI thread, and the retune session. Detached runs go through
tests/fake_cli.py."""
import json
import re
import string
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import skrf as rf

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import CATALOG, KrsError, render
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.outputs import LIMITS
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import board_file, load_project, parts, save_project
from kicad_rf_studio.gui import control
from networks import star, terminate_np
from test_cli_cost import FIX, new_project
from test_post_chain import M0402, lpf
from test_run import lpf_loads, lpf_run

F, _ = grid(915e6, 3, 1.1)
FAKE_CLI = Path(__file__).with_name("fake_cli.py")
FAKE_PREFIX = [sys.executable, "-X", "utf8", "-I", str(FAKE_CLI)]


def until(check, timeout=60.0):
    """Polls `check` every 0.1 s until it holds; fails after `timeout` s."""
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.1)


def ends(run_dir):
    return (control.last_event(run_dir) or {}).get("kind") == "end"


@pytest.mark.parametrize(("exe", "python"), [
    (("venv", "Scripts", "pythonw.exe"), ("venv", "Scripts", "python.exe")),  # a gui-scripts entry on Windows
    (("venv", "bin", "python3"), ("venv", "bin", "python3"))])
def test_the_orchestrator_is_the_console_python_beside_the_guis(monkeypatch, exe, python):  # design 5.1
    monkeypatch.setattr(sys, "executable", str(Path(*exe)))
    assert control.orchestrator() == [str(Path(*python)), "-X", "utf8", "-I", "-m", "kicad_rf_studio"]


def recorder(monkeypatch, refuse_first=False):
    calls = []

    def popen(args, **kw):
        calls.append(SimpleNamespace(args=args, **kw))
        if refuse_first and len(calls) == 1:
            raise PermissionError(13, "the job forbids breakaway")
        return calls[-1]

    monkeypatch.setattr(subprocess, "Popen", popen)
    return calls


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' creation flags")
def test_start_is_detached_windowless_and_breaks_away_when_it_may(tmp_path, monkeypatch):  # design 5.1
    calls = recorder(monkeypatch, refuse_first=True)
    monkeypatch.setenv("KICAD_API_TOKEN", "t")
    monkeypatch.setenv("KICAD_API_SOCKET", "s")
    d = tmp_path / "run"
    control.start(["py"], "cost", tmp_path / "project.json", d)
    base = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    assert [c.creationflags for c in calls] == [base | subprocess.CREATE_BREAKAWAY_FROM_JOB, base]
    assert calls[1].args == ["py", "cost", str(tmp_path / "project.json"), "--run-dir", str(d)]
    assert (calls[1].stdin, calls[1].stderr, calls[1].cwd) == (subprocess.DEVNULL, subprocess.STDOUT, d)
    assert (d / "cli.log").is_file() and not {"KICAD_API_TOKEN", "KICAD_API_SOCKET"} & set(calls[1].env)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sessions")
def test_start_runs_in_a_session_of_its_own(tmp_path, monkeypatch):  # design 5.1
    calls = recorder(monkeypatch)
    control.start(["py"], "run", tmp_path / "project.json", tmp_path / "run")
    assert calls[0].start_new_session is True and not hasattr(calls[0], "creationflags")
    assert calls[0].cwd == tmp_path / "run"


def test_the_tail_holds_back_a_partial_last_line(tmp_path):  # Review Focus 3
    path = tmp_path / "events.jsonl"
    tail = control.Tail(path)
    assert tail.read() == []  # no file yet
    one, two = (json.dumps({"kind": "message", "job": None, "code": c, "params": {}}).encode() for c in "AB")
    path.write_bytes(one + b"\r\n" + two[:9])  # emit writes text mode: \r\n on Windows
    assert tail.read() == [json.loads(one)] and tail.offset == len(one) + 2
    with open(path, "ab") as f:
        f.write(two[9:] + b"\n{not json\n" + one + b"\n")
    assert tail.read(limit=len(two) + 1) == [json.loads(two)]  # at most `limit` bytes a read
    assert tail.read() == [json.loads(one)]  # the line that does not parse is skipped


def test_a_replay_keeps_only_the_last_progress_of_each_job():  # r2 §1: no frozen window on an 8 h run's replay
    events = [{"kind": "progress", "job": 1 + k % 2, "n": k} for k in range(1000)]
    events += [{"kind": "verdict", "job": 1, "n": "v"}, {"kind": "progress", "job": 2, "n": "late"}]
    assert [e["n"] for e in control.latest(events)] == [998, "v", "late"]


def test_the_projects_ended_runs_and_its_last_matching_cost(fake, tmp_path):  # design 5.1, 5.2 item 3, 5.3
    pj, other = tmp_path / "lpf915" / "project.json", tmp_path / "lpf915-45" / "project.json"
    for name, project, command, code, t, spec in [
            ("lpf915-1", pj, "cost", 0, 1.0, {"m": 1}), ("lpf915-2", pj, "run", 4, 2.0, None),
            ("lpf915-3", pj, "cost", 0, 3.0, {"m": 2}), ("lpf915-4", pj, "cost", 3, 4.0, {"m": 1}),
            ("lpf915-45-5", other, "cost", 0, 5.0, {"m": 1}), ("lpf915-6", pj, None, None, 6.0, None)]:
        d = fake / "runs" / name
        d.mkdir(parents=True)
        if spec is not None:
            runs.write_spec(d, spec)
        event = {"t": t, "kind": "end", "job": None, "code": "I_END",
                 "params": {"exit_code": code, "command": command, "project": str(project)}}
        (d / "events.jsonl").write_text(json.dumps(event if command else {"t": t, "kind": "progress"}) + "\n",
                                        encoding="utf-8")
    assert [(d.name, e["params"]["command"]) for d, e in control.ended(pj)] == [
        ("lpf915-4", "cost"), ("lpf915-3", "cost"), ("lpf915-2", "run"), ("lpf915-1", "cost")]
    assert control.last_cost(pj, spec_hash({"m": 1})) == fake / "runs" / "lpf915-1"  # lpf915-4's gate blocked
    assert control.last_cost(pj, spec_hash({"m": 2})) == fake / "runs" / "lpf915-3"
    assert control.last_cost(pj, spec_hash({"m": 3})) is None and control.last_cost(pj, None) is None


@pytest.mark.parametrize(("end", "holder", "own", "returncode", "code"), [
    ({"params": {"exit_code": 0}}, None, True, 0, "G_END_DONE"),
    ({"params": {"exit_code": 2}}, None, False, None, "G_END_REFUSED"),  # Review Focus 2
    ({"params": {"exit_code": 3}}, None, False, None, "G_END_BLOCKED"),
    ({"params": {"exit_code": 4}}, None, False, None, "G_END_NOT_KEPT"),
    ({"params": {"exit_code": 130}}, None, False, None, "G_END_STOPPED"),
    ({"params": {"exit_code": 1}}, None, False, None, "G_END_FAILED"),
    (None, None, True, None, "G_RUNNING"),  # this window's process, going on
    (None, None, True, 3, "G_END_EXITED"),  # Review Focus 4: it exited with no end event, killed or failed at start
    (None, {"run_dir": "R", "alive": True}, False, None, "G_RUNNING"),  # another's run, its lock live
    (None, {"run_dir": "R", "alive": False}, False, None, "G_END_LOST"),  # Review Focus 4: a stale lock
    (None, {"run_dir": "other", "alive": True}, False, None, "G_ENDED"),
    (None, None, False, None, "G_ENDED")])  # its lock gone with no end event yet, or a run of an older version
def test_the_run_state(end, holder, own, returncode, code):  # design 5.1, 5.3
    state, params = control.run_state(Path("R"), end, holder, own, returncode)
    assert (state, params["exit_code"]) == (code, end["params"]["exit_code"] if end else returncode)


def test_the_gui_words_the_cli_advice_its_own_way():  # design 5.3, 5.7
    assert control.text("I_WHAT_IF", {"command": "x"}) == render("G_WHAT_IF")
    assert render("G_WHAT_IF") == render("I_WHAT_IF", command="X").replace("`X`", "Verify")  # §7.6's text
    held = {"lock": "L", "run": "R", "started": "S"}
    assert control.text("E_LOCKED", held) == render("G_LOCKED", **held)
    assert control.text("I_GATES_PASSED", {"dt": "1"}) == render("I_GATES_PASSED", dt="1")


def test_the_pad_picker_lists_each_pad_with_copper_once_in_natural_order():  # design 5.3 Project
    assert control.pads(FIX / "coupon_gcpw_pads.kicad_pcb") == ["TP1.1", "TP2.1"]
    names = control.pads(FIX / "lpf915.kicad_pcb")
    assert len(names) == 36 and names[:4] == ["C1.1", "C1.2", "C2.1", "C2.2"] and names[-9:-7] == ["U1.9", "U1.10"]
    assert control.pads(FIX / "coupon_ms.kicad_pcb") == []  # a pad-less coupon
    with pytest.raises(KrsError) as e:
        control.pads(FIX / "nope.kicad_pcb")
    assert (e.value.code, e.value.params["reason"]) == ("E_BOARD_UNREADABLE", "file not found")


def test_every_gui_wording_keeps_its_cli_params_and_drops_terminal_syntax():  # design 5.3, 5.7
    def fields(code):
        return {name for _, name, _, _ in string.Formatter().parse(CATALOG[code]) if name}

    for cli_code, gui_code in control.GUI.items():  # later tasks' entries too
        assert fields(gui_code) <= fields(cli_code), gui_code  # rendered with the CLI line's own params
        assert not re.search(r"`|--[a-z]|-o |PROJECT", CATALOG[gui_code]), gui_code
    assert control.text("E_PROJECT_EXISTS", {"path": "P"}) == render("G_PROJECT_EXISTS", path="P")
    assert control.message(KrsError("E_NO_STACKUP")) == render("G_NO_STACKUP")
    assert control.message(ZeroDivisionError("division by zero")) == render(
        "E_INTERNAL", detail="ZeroDivisionError: division by zero")


def test_open_project_reads_results_only_while_they_apply(tmp_path, calibrated, monkeypatch):  # Review Focus 1, 5
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    fresh = control.open_project(pj)
    assert (fresh.results, fresh.problem, fresh.cost, fresh.last) == (None, ("E_NO_RESULTS", {}), None, None)
    d = runs.run_dir_for(pj.parent.name)
    assert main(["cost", str(pj), "--run-dir", str(d)]) == 0 and main(["run", str(pj)]) == 0
    ran, r = control.open_project(pj), Path(load_project(pj)["results"]["run_dir"])
    assert ran.problem is None and ran.spec_hash == fresh.spec_hash == load_project(pj)["results"]["model_hash"]
    assert (ran.results.ext, ran.results.what_if, ran.cost, ran.last) == ([0, 1], False, d, r)  # A-13: it ended r
    save_project(pj, {**load_project(pj), "t_max_s": 30e-9})  # a hand edit: T_max is in the model's excitation
    stale = control.open_project(pj)
    assert (stale.results, stale.problem, stale.cost) == (None, ("E_RESULTS_STALE", {}), None)
    assert fresh.board == ran.board == stale.board == board_file(pj, load_project(pj))  # final review F9
    nope = control.open_project(tmp_path / "nope.json")
    assert nope.problem[0] == "E_PROJECT_UNREADABLE" and nope.board is None
    monkeypatch.setattr(pipeline, "load", lambda path: 1 / 0)
    assert control.open_project(pj).problem == ("E_INTERNAL", {"detail": "ZeroDivisionError: division by zero"})


def test_a_run_going_on_is_found_through_its_lock_and_stops_by_its_stop_file(tmp_path, calibrated,
                                                                              monkeypatch):  # 5.1, Review Focus 1
    monkeypatch.setenv("KRS_FAKE_DATA", str(calibrated))
    monkeypatch.setenv("KRS_FAKE", "slow")
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    d = runs.run_dir_for(pj.parent.name)
    proc = control.start(FAKE_PREFIX, "run", pj, d)
    try:
        until(lambda: (runs.lock_holder(pj) or {}).get("run_dir") == str(d))  # written, not only made
        tail, seen = control.Tail(d / "events.jsonl"), []
        until(lambda: seen.extend(tail.read()) or any(e["kind"] == "progress" for e in seen))
        (d / "STOP").write_text("")
        until(lambda: ends(d))
    finally:
        proc.kill()
        proc.wait()
    assert control.last_event(d)["params"] == {"exit_code": 4, "command": "run", "project": str(pj)}  # not kept
    assert [f for f, _ in control.ended(pj)] == [d] and (d / "cli.log").is_file() and runs.lock_holder(pj) is None


@pytest.mark.parametrize(("ref", "text", "series", "shown"), [
    ("C2", "5pF", "E24", "5.1pF"), ("C2", "5pF", "E12", "4.7pF"), ("C2", "5pF", "off", "5pF"),
    ("L1", "4.0nH", "E24", "3.9nH"), ("C2", "4p7", "E24", "4.7pF"), ("C2", "3,9pF", "off", "3,9pF"),
    ("C2", "abc", "E24", "abc"), ("C2", "0", "E24", "0"), ("R1", "0R", "E24", "0R"),
    ("C2", "9" * 400 + "pF", "E24", "9" * 400 + "pF")])  # reads as inf, which snap cannot take
def test_snapping_writes_back_the_nearest_value_as_port_value_reads_it(ref, text, series, shown):  # design 5.3, 7
    assert control.snapped(ref, text, series) == shown
    assert [control.default_series(r) for r in ("C2", "L1", "R1", "FB1")] == ["E24", "E24", "off", "off"]
    assert control.SERIES == ("off", "E12", "E24")


def test_the_rows_and_the_assignments_of_the_changed_ones(tmp_path):  # design 5.3: free text, or an S2P file
    project, folder, refs = lpf(), tmp_path / "lpf915", ["C1", "L1", "C2", "C3"]  # lpf(): a copy, never the cache
    parts(project)["L1"]["s2p"] = {"file": "../parts/l1.s2p", "connection": "series"}
    rows = control.rows(project, folder, refs)
    l1 = str((tmp_path / "parts" / "l1.s2p").resolve())
    assert rows == [control.Row("C1", "100pF", "", "series"), control.Row("L1", "15nH", l1, "series"),
                    control.Row("C2", "3.3pF", "", "series"), control.Row("C3", "3.3pF", "", "series")]
    assert control.changed(project, folder, rows) == []
    edited = [rows[0], replace(rows[1], connection="shunt"), replace(rows[2], value="4p7"),
              replace(rows[3], s2p="c3.s2p")]  # a file named from the project's folder, never the working one
    assert control.changed(project, folder, edited) == [
        f"L1={l1}:shunt", "C2=4p7", f"C3={(folder / 'c3.s2p').resolve()}:series"]
    assert control.changed(project, folder, [replace(rows[1], s2p="")]) == ["L1=15nH"]  # a value clears the file


def test_the_retune_session_gives_retunes_own_numbers_in_milliseconds_and_writes_nothing(
        tmp_path, calibrated, monkeypatch):  # design 5.1, 5.3, 5.4; Review Focus 1, 2
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # tests/test_run.py: lpf915 on the star network fake
    opened = control.open_project(pj)
    rows = control.rows(opened.project, pj.parent, opened.results.refs)
    rows[2] = replace(rows[2], value="4.7pF")
    before = {p: p.stat().st_mtime_ns for p in (pj, *(pj.parent / "results").iterdir())}
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        res = control.retuned(pj, opened.project, opened.results, rows)
        timings.append(time.perf_counter() - start)
    assert min(timings) < 0.05  # the GUI thread's budget (design goal 4); about 5 ms measured on lpf915
    assert {p: p.stat().st_mtime_ns for p in before} == before  # nothing written: Apply writes
    assert res.what_if and res.lay is opened.results.lay
    oracle = terminate_np(star(F, 6), [0, 1], lpf_loads(M0402, C2=4.7e-12))
    assert np.abs(res.chain - oracle).max() <= 1e-5  # the network the fake ran (tests/networks.py)
    three = tmp_path / "x.s3p"
    rf.Network(frequency=rf.Frequency.from_f(F, unit="Hz"), s=star(F, 3), z0=50).write_touchstone(str(three))
    wrong = control.retuned(pj, opened.project, opened.results, [replace(rows[1], s2p=str(three))])
    assert wrong.chain is None and wrong.lines[-1] == ("E_S2P_PORTS", {"ref": "L1", "path": str(three.resolve()),
                                                                        "ports": 3})
    bad = control.retuned(pj, opened.project, opened.results, [replace(rows[2], value="15nH")])
    assert (bad.chain, bad.what_if, bad.lines) == (None, False, [("E_RETUNE_VALUE", {"ref": "C2", "value": "15nH"})])
    assert main(["retune", str(pj), "C2=4.7pF"]) == 0
    stored = pipeline.chain_results(pj, load_project(pj))
    assert np.array_equal(res.chain, stored.chain) and res.lines == stored.lines  # retune's own numbers and lines
    monkeypatch.setattr(pipeline, "chain_results", lambda *a, **k: 1 / 0)  # any other failure: a line, never a raise
    assert control.retuned(pj, opened.project, opened.results, rows).lines == [
        ("E_INTERNAL", {"detail": "ZeroDivisionError: division by zero"})]


def test_a_read_keeps_the_unapplied_rows_whose_part_it_did_not_change(tmp_path):  # design 5.3; Review Focus 5
    before, folder, refs = lpf(), tmp_path / "lpf915", ["C1", "L1", "C2", "C3"]
    rows = control.rows(before, folder, refs)
    edited = [*rows[:2], replace(rows[2], value="4.7pF"), rows[3]]
    applied, other, mine = lpf(), lpf(), lpf()
    parts(applied)["C2"]["value"] = "4.7pF"  # Apply stored it
    parts(other)["C3"]["value"] = "3.9pF"  # a hand edit, or a terminal's retune, of another part
    parts(mine)["C2"]["value"] = "3.9pF"  # ... of the part being retuned
    assert control.carried(before, lpf(), folder, edited, rows) == (edited, False)  # a cost's or a run's read
    assert control.carried(before, applied, folder, edited, control.rows(applied, folder, refs)) == (edited, False)
    other_rows = control.rows(other, folder, refs)
    assert control.carried(before, other, folder, edited, other_rows) == ([*edited[:3], other_rows[3]], False)
    mine_rows = control.rows(mine, folder, refs)
    assert control.carried(before, mine, folder, edited, mine_rows) == (mine_rows, True)
    assert control.carried(before, None, folder, edited, []) == ([], True)  # a read that failed, or results gone stale
    assert control.carried(None, before, folder, [], rows) == (rows, False)  # the first read


def test_apply_runs_retune_to_its_end_without_a_window_and_returns_its_lines(tmp_path, calibrated, monkeypatch):
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # design 5.3 Apply, 5.4
    monkeypatch.setenv("KRS_FAKE_DATA", str(calibrated))
    code, lines = control.apply(FAKE_PREFIX, pj, ["C2=4.7pF"])
    stored = pipeline.chain_results(pj, load_project(pj))
    assert code == 0 and parts(load_project(pj))["C2"]["value"] == "4.7pF"
    assert lines[:len(stored.lines)] == [render(c, **p) for c, p in stored.lines] and lines[-1] == render(LIMITS[-1])
    assert control.apply(FAKE_PREFIX, pj, ["C2=15nH"]) == (2, [render("E_RETUNE_VALUE", ref="C2", value="15nH")])
    with pytest.raises(FileNotFoundError):
        control.apply([str(tmp_path / "no-python")], pj, [])
    seen = []  # what a real run cannot show: no window, no KiCad API variables, stdin closed
    monkeypatch.setenv("KICAD_API_TOKEN", "t")
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: seen.append(kw) or SimpleNamespace(
        returncode=0, stdout="a\n", stderr="b\n"))
    assert control.apply(["py"], pj, ["C2=1pF"]) == (0, ["a", "b"])
    assert seen[0]["stdin"] == subprocess.DEVNULL and "KICAD_API_TOKEN" not in seen[0]["env"]
    assert seen[0]["creationflags"] == (subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
