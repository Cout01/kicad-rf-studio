# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI (Stage 2 design 5): its dependency and entry point, the import rules, and the main window offscreen on
the fake CLI."""
import gc
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from importlib import metadata
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox

from kicad_rf_studio import button, gui, pipeline, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.post.chain import with_box, z_part
from kicad_rf_studio.core.post.outputs import LIMITS
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import board_file, load_project, parts, save_project
from kicad_rf_studio.gui import control
from kicad_rf_studio.gui.window import FIXTURE, PART, S2P, SNAP, VALUE, MainWindow
from networks import C_BOX, star, terminate_np, write_s2p
from test_cli_cost import FIX, fail, new_project
from test_gui_control import FAKE_PREFIX, press, until
from test_post_chain import M0402
from test_run import lpf_loads, lpf_run
from test_verify import verified

F, _ = grid(915e6, 3, 1.1)
ROOT = Path(__file__).resolve().parents[1]
QT_FREE = ("kicad_rf_studio.cli", "kicad_rf_studio.worker", "kicad_rf_studio.pipeline", "kicad_rf_studio.runs",
           "kicad_rf_studio.gui", "kicad_rf_studio.gui.control", "kicad_rf_studio.button")


def test_pyside6_essentials_is_a_core_dependency_with_the_gui_entry():  # design 5.6, A-15
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "PySide6-Essentials>=6.10.1,<7" in project["dependencies"]
    assert project["gui-scripts"] == {"kicad-rf-studio-gui": "kicad_rf_studio.gui:main"}
    names = {re.split(r"[<>=!~;\[ ]", d, maxsplit=1)[0].lower()
             for d in project["dependencies"] + project["optional-dependencies"]["dev"]}
    assert not names & {"pyside6", "pyside6-addons", "pytest-qt"}  # Essentials only (design 4, 5.8)


def test_kicad_python_is_a_core_dependency_and_imports():  # design 5.6; A-16
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "kicad-python>=0.8,<0.9" in project["dependencies"]  # 0.8: the first line that installs on Python 3.14
    assert metadata.version("kicad-python").startswith("0.8.")
    out = subprocess.run([sys.executable, "-I", "-c", "import kipy.board_types, kipy.packaging.validate"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr  # installed is not importable: its protos refuse an older protobuf


def test_the_engine_the_cli_and_the_gui_package_load_no_qt_kicad_python_or_matplotlib():  # design 4, 5.6, 5.8; C-5
    probe = (f"import sys, {', '.join(QT_FREE)}; "
             "print(sorted({m.split('.')[0] for m in sys.modules} & {'PySide6', 'shiboken6', 'kipy', 'matplotlib'}))")
    out = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr


def test_the_gui_entry_runs_offscreen_and_logs_without_a_console(qapp, fake, monkeypatch):  # design 5.6, 5.8; r3 R-2
    monkeypatch.setattr(sys, "stderr", None)  # pythonw: the gui-scripts entry on Windows has no console
    seen = []  # taken while the app runs: main's own window goes when main returns
    QTimer.singleShot(0, lambda: (seen.extend(qapp.topLevelWidgets()), qapp.quit()))
    assert gui.main([]) == 0
    assert render("G_APP") in [w.windowTitle() for w in seen]
    log = sys.stderr
    log.close()
    assert Path(log.name) == fake / "gui.log"


def grab(widget, name):
    """widget's picture as $KRS_GRAB_DIR/name.png when that is set: the controller's visual review (design 5.8)."""
    if folder := os.environ.get("KRS_GRAB_DIR"):
        Path(folder).mkdir(parents=True, exist_ok=True)
        widget.grab().save(str(Path(folder) / f"{name}.png"))


def items(widget):
    return [widget.item(i).text() for i in range(widget.count())]


@pytest.fixture(autouse=True)
def collected():
    """Each test's garbage collected at its end, on this thread, the GUI's: a window left in a reference cycle (the
    bound method that monkeypatch's undo sets back on an instance makes one) would otherwise be freed wherever the
    collector runs next, a window's pool thread included, which deletes Qt widgets off the GUI thread (probed: an abort
    or an access violation in a later test). Autouse, it is torn down after monkeypatch's undo."""
    yield
    gc.collect()


@pytest.fixture
def window(qapp, calibrated, monkeypatch):
    """MainWindow on the fake CLI, shown offscreen, with runs.run_jobs and runs.ensure_calibrated failing in this
    process from the first window on (design 5.1: a test's own engine calls come before it); what it started is
    killed, its project reads awaited and the windows dropped at teardown (pytest holds `make` a while longer), so
    that collected() frees them."""
    monkeypatch.setenv("KRS_FAKE_DATA", str(calibrated))
    made = []

    def make(prefix=FAKE_PREFIX):
        for name in ("run_jobs", "ensure_calibrated"):
            monkeypatch.setattr(runs, name, fail)
        made.append(MainWindow(prefix=prefix))
        made[-1].show()
        return made[-1]

    yield make
    for w in made:
        for proc in w.started:  # every process it started, not only the watched one
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        w.close()
        w.pool.shutdown(wait=True)  # a read still going would outlive the fake data folder
    made.clear()


def opened(w):
    """w once its project read finished and a tick took it in."""
    if w.loading:
        w.loading.result(timeout=120)
    w.tick()
    return w


def test_the_window_costs_then_runs_after_the_confirmation(window, tmp_path, monkeypatch):  # design 5.1, 5.3
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    w = window()
    w.open_project(pj.parent)  # a folder stands for its project.json
    opened(w)
    assert w.path == pj and w.project_status.text() == render(
        "G_PROJECT", path=str(pj), f0_mhz="915", harmonics=3, preset="draft")
    assert w.cost_status.text() == render("G_NO_COST") and not w.run_button.isEnabled()
    grab(w, "project")
    w.cost_button.click()
    assert w.proc is not None  # detached: the fixture makes run_jobs fail in this process
    until(lambda: w.tick() or w.cost_status.text() == render("G_END_DONE", exit_code=0))
    lines = items(w.cost_lines)
    assert lines[:2] == [render("W_FILLS_AS_SAVED"), render("I_2D_HEADER")] and lines[-1].startswith("Main cost: ")
    opened(w)  # the cost's end read the project again, which found it as this model's cost
    assert w.cost == w.run_dir and w.run_button.isEnabled() and w.cost_status.text() == render("G_END_DONE",
                                                                                               exit_code=0)
    save_project(pj, load_project(pj))  # the same model, a new mtime (final review F4)
    w.tick()
    assert w.loading is not None and not w.run_button.isEnabled()  # Run… waits for the re-read
    opened(w)
    assert w.cost == w.run_dir and w.run_button.isEnabled()  # the read found the same cost again
    grab(w, "cost")
    asked = []
    monkeypatch.setattr(w, "ask", lambda text: asked.append(text) or len(asked) > 1)  # No, then Yes
    w.run_button.click()
    assert w.command == "cost" and asked[0].startswith(render("G_CONFIRM_RUN")) and "Worst case: " in asked[0]
    w.run_button.click()  # nothing started on No; now Yes
    until(lambda: w.tick() or w.run_status.text() == render("G_END_DONE", exit_code=0))
    assert [w.jobs.item(r, 0).text() for r in range(w.jobs.rowCount())] == ["P1", "P2"]
    assert w.jobs.item(0, 4).text().startswith("P1: converged at ")
    log = items(w.log)
    assert any(x.startswith("Running 2 jobs") and x.endswith("Stop stops them.") for x in log)
    assert not any("Ctrl+C" in x for x in log) and load_project(pj)["results"]["run_dir"] == str(w.run_dir)
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # design 4, 5.8: the GUI process
    grab(w, "run")


def test_the_window_drives_itself_and_survives_a_display_that_fails(window, qapp, tmp_path, monkeypatch):
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()  # Review Focus 3
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(pj), ""))
    w = window()
    assert not (w.cost_button.isEnabled() or w.run_button.isEnabled() or w.stop_button.isEnabled())  # no project
    w.open_button.click()
    assert (w.timer.interval(), w.timer.isActive(), w.project_status.text()) == (500, True, render("G_LOADING"))
    until(lambda: qapp.processEvents() or w.opened is not None)  # the window's own timer took the read in
    assert w.path == pj and w.loading is None and w.cost_button.isEnabled()
    monkeypatch.setattr(w, "show_project", lambda opened: 1 / 0)  # a display that fails
    w.load()
    until(lambda: qapp.processEvents() or w.loading is None)
    assert w.project_status.text() == control.text("E_INTERNAL", {"detail": "ZeroDivisionError: division by zero"})
    assert w.cost_button.isEnabled() and not w.stop_button.isEnabled()  # that tick went on to the buttons


def test_a_process_that_cannot_start_or_ends_without_its_end_event_says_so(window, tmp_path):  # design 5.3
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    missing = str(tmp_path / "no-python")
    w = window([missing])
    w.open_project(pj)
    opened(w)
    w.cost_button.click()
    assert w.proc is None and w.cost_status.text() == render("G_START_FAILED", program=missing,
                                                             reason="file not found")
    dies = window([sys.executable, "-c", "raise SystemExit(3)"])  # an orchestrator that ends before cli.main
    dies.open_project(pj)
    opened(dies)
    dies.cost_button.click()
    exited = {"folder": str(dies.run_dir), "exit_code": 3, "log": str(dies.run_dir / "cli.log")}
    until(lambda: dies.tick() or dies.cost_status.text() == render("G_END_EXITED", **exited))


def test_the_gui_entry_opens_the_project_it_is_given(qapp, tmp_path, calibrated):  # design 5.6
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    seen = []
    QTimer.singleShot(0, lambda: (seen.extend(qapp.topLevelWidgets()), qapp.quit()))
    assert gui.main([str(pj)]) == 0
    w = next(w for w in seen if isinstance(w, MainWindow) and w.path == pj)  # `seen` keeps it alive past main
    w.close()
    w.pool.shutdown(wait=True)  # its read, before the fake data folder goes


def costed(pj):
    """A cost of pj's model ended in a run folder of its own, as the GUI starts one (in-process: quicker; before the
    test's first window, which makes runs.run_jobs fail)."""
    d = runs.run_dir_for(pj.parent.name)
    assert main(["cost", str(pj), "--run-dir", str(d)]) == 0
    return d


def test_a_window_closed_mid_run_leaves_it_running_and_a_new_one_attaches_with_stop(window, tmp_path, monkeypatch):
    monkeypatch.setenv("KRS_FAKE", "slow")  # Review Focus 1
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    costed(pj)
    first = window()
    first.open_project(pj)
    opened(first)
    monkeypatch.setattr(first, "ask", lambda text: True)
    first.run_button.click()
    until(lambda: first.tick() or first.jobs.rowCount() > 0)
    first.close()
    assert first.proc.poll() is None  # the run goes on without its window
    second = window()
    second.open_project(pj)
    second.tick()
    holder = runs.lock_holder(pj)
    assert second.run_dir == first.run_dir and second.proc is None and second.jobs.rowCount() > 0  # replayed
    assert second.banner.text() == render("G_LOCKED", lock=str(runs.lock_file(pj)), run=holder["run_dir"],
                                          started=holder["started"]) and not second.banner.isHidden()
    assert (second.stop_button.isEnabled(), second.run_button.isEnabled(), second.cost_button.isEnabled()) == (
        True, False, False)
    grab(second, "run-attached")
    second.stop_button.click()
    assert (first.run_dir / "STOP").exists()
    until(lambda: second.tick() or second.run_status.text() == render("G_END_NOT_KEPT", exit_code=4))
    assert any(x.endswith("stopped, so its S is not kept. Run `run` again for results.") for x in items(second.log))
    third = window()  # the run ended while no window watched it
    third.open_project(pj)
    opened(third)
    assert third.run_dir == first.run_dir and third.run_status.text() == render("G_END_NOT_KEPT", exit_code=4)


def test_a_killed_run_reads_lost_and_its_stale_lock_does_not_block_the_next(window, tmp_path, monkeypatch):
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()  # Review Focus 4
    costed(pj)
    w = window()
    w.open_project(pj)
    opened(w)
    monkeypatch.setattr(w, "ask", lambda text: True)
    monkeypatch.setenv("KRS_FAKE", "hang")
    w.run_button.click()
    until(lambda: (runs.lock_holder(pj) or {}).get("pid"))  # written, not only made
    w.proc.kill()  # Task Manager, say: its workers die with it
    w.proc.wait()
    until(lambda: runs.lock_holder(pj)["alive"] is False)  # Windows: the venv launcher's job ends it a moment later
    w.tick()
    exited = {"folder": str(w.run_dir), "exit_code": w.proc.returncode, "log": str(w.run_dir / "cli.log")}
    assert w.run_status.text() == render("G_END_EXITED", **exited) and w.run_button.isEnabled()
    again = window()  # the lock stays behind, stale
    again.open_project(pj)
    assert again.run_dir == w.run_dir and again.run_status.text() == render("G_END_LOST", folder=str(w.run_dir))
    grab(again, "run-lost")
    monkeypatch.delenv("KRS_FAKE")
    again.cost_button.click()  # a cost meanwhile keeps its tab: a dead lock is attached only on open
    until(lambda: again.tick() or again.cost_status.text() == render("G_END_DONE", exit_code=0))
    assert again.command == "cost" and again.tabs.currentIndex() == 1
    monkeypatch.setattr(again, "ask", lambda text: True)
    opened(again)
    again.run_button.click()
    until(lambda: again.tick() or again.run_status.text() == render("G_END_DONE", exit_code=0))


def test_a_run_no_longer_watched_that_is_killed_reads_lost(window, tmp_path, monkeypatch):  # Review Focus 4, Linux
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()  # final review F2
    costed(pj)
    w = window()
    w.open_project(pj)
    opened(w)
    monkeypatch.setattr(w, "ask", lambda text: True)
    monkeypatch.setenv("KRS_FAKE", "hang")
    w.run_button.click()
    until(lambda: (runs.lock_holder(pj) or {}).get("pid"))  # written, not only made
    proc, run_dir = w.proc, w.run_dir
    w.open_project(pj)  # the run goes on, no longer watched as this window's own
    assert w.proc is None and w.run_dir == run_dir  # re-attached through the live lock
    proc.kill()  # no wait: on Linux only the window may reap it, else os.kill(pid, 0) finds a zombie alive
    until(lambda: w.tick() or runs.lock_holder(pj)["alive"] is False)
    w.tick()
    assert w.run_status.text() == render("G_END_LOST", folder=str(run_dir)) and w.cost_button.isEnabled()


def test_another_runs_lock_disables_cost_and_run_until_it_goes(window, tmp_path):  # design 5.1, 5.3
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    cost, lock = costed(pj), runs.lock_file(pj)
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": str(pj.parent / "results"), "started": "S"}),
                    encoding="utf-8")  # a retune holds it
    w = window()
    w.open_project(pj)
    opened(w)
    assert w.run_dir is None and w.banner.isHidden()  # a retune is waited for, never watched (r2 §1)
    assert (w.cost_button.isEnabled(), w.run_button.isEnabled(), w.stop_button.isEnabled()) == (False, False, False)
    assert w.cost == cost and w.cost_status.text() == render("G_COST_REUSED", folder=cost.name)  # reused: same model
    assert items(w.cost_lines)[0] == render("W_FILLS_AS_SAVED")
    other = tmp_path / "other run"
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": str(other), "started": "S"}), encoding="utf-8")
    w.tick()
    assert w.run_dir == other and w.run_status.text() == render("G_RUNNING", folder=str(other))
    assert (w.cost_button.isEnabled(), w.run_button.isEnabled(), w.stop_button.isEnabled()) == (False, False, True)
    lock.unlink()
    w.tick()
    assert w.run_status.text() == render("G_ENDED", folder=str(other)) and w.banner.isHidden()
    assert (w.cost_button.isEnabled(), w.run_button.isEnabled(), w.stop_button.isEnabled()) == (True, True, False)


def test_a_cost_that_ends_under_another_runs_lock_shows_its_end_before_the_attach(window, tmp_path):  # design 5.1, 5.3
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()  # final review F1
    w = window()
    w.open_project(pj)
    opened(w)
    w.cost_button.click()
    cost, lock, other = w.run_dir, runs.lock_file(pj), tmp_path / "other run"
    until(lambda: w.proc.poll() is not None)  # no tick while the cost runs
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": str(other), "started": "S"}), encoding="utf-8")
    w.tick()  # the tick that sees the cost's exit reads its last lines and its end first
    assert w.command == "cost" and w.cost_status.text() == render("G_END_DONE", exit_code=0)
    assert items(w.cost_lines)[-1].startswith("Main cost: ")
    w.tick()  # then the other run's lock is attached
    assert w.command == "run" and w.run_dir == other
    opened(w)
    assert w.cost == cost  # the exit-0 re-read was kept
    lock.unlink()


def test_a_lock_that_appears_just_before_a_click_keeps_the_new_watch(window, tmp_path):  # design 5.1, 5.3
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()  # final review F12
    w = window()
    w.open_project(pj)
    opened(w)
    assert w.cost_button.isEnabled()  # no lock
    lock, other = runs.lock_file(pj), tmp_path / "other run"
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": str(other), "started": "S"}), encoding="utf-8")
    w.cost_button.click()  # no tick since the lock appeared: the click's own tick is the first to read it
    assert w.command == "cost" and w.proc is not None and w.run_dir != other
    lock.unlink()


def test_results_show_the_chain_under_the_what_if_label_and_go_when_stale(window, tmp_path, monkeypatch):
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # tests/test_run.py: lpf915 on the network fake; Review Focus 5
    w = window()
    w.open_project(pj)
    opened(w)
    res, fig, label = w.opened.results, w.results.canvas.figure, render("G_WHAT_IF")
    assert w.results.what_if.text() == label and not w.results.what_if.isHidden()  # design 5.3: 4 part ports
    assert len(fig.axes) == 3 and fig.get_suptitle() == render("I_PLOT_TITLE", name="lpf915") + "\n" + label
    assert items(w.results.lines) == [control.text(c, p) for c, p in res.lines] + [render(c) for c in LIMITS]
    assert items(w.results.lines)[0].startswith("Results of the run in ")
    w.results.canvas.draw()  # the Qt canvas renders it: draw_idle waits for an event loop the tests do not run
    w.tabs.setCurrentWidget(w.results)
    grab(w, "results")
    monkeypatch.setattr(pipeline, "RETUNE_VALIDATED", True)  # the owner's switch after P0-C
    w.load()
    opened(w)
    assert w.results.what_if.isHidden() and fig.get_suptitle() == render("I_PLOT_TITLE", name="lpf915")
    save_project(pj, {**load_project(pj), "t_max_s": 30e-9})  # a hand edit: T_max is in the model's excitation
    w.tick()  # project.json's mtime: read again
    opened(w)
    w.tick()
    assert w.loading is None  # read once: load() stamped the new mtime (Review Focus 3)
    assert fig.axes == [] and items(w.results.lines) == [] and w.results.problem.text() == render("G_RESULTS_STALE")
    grab(w, "results-stale")


def test_a_single_trace_has_no_what_if_label(window, tmp_path, calibrated):  # design 5.3
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    assert main(["run", str(pj)]) == 0
    w = window()
    w.open_project(pj)
    opened(w)
    fig = w.results.canvas.figure
    assert w.results.what_if.isHidden() and len(fig.axes) == 3
    assert fig.get_suptitle() == render("I_PLOT_TITLE", name="coupon_gcpw_pads")
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # this process read and drew it (design 4)
    w.open_project(tmp_path / "nope.json")  # final review F8: the old plot goes before the new read is taken in
    assert fig.axes == [] and items(w.results.lines) == [] and w.results.what_if.isHidden()


def test_an_open_window_reads_its_board_again_when_it_is_saved(window, tmp_path):  # Review Focus 5
    board = tmp_path / "coupon_gcpw_pads.kicad_pcb"  # final review F3: a copy, which the test re-saves
    board.write_bytes((FIX / "coupon_gcpw_pads.kicad_pcb").read_bytes())
    assert main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "--preset", "draft",
                 "-o", str(tmp_path / "coupon_gcpw_pads")]) == 0
    pj = (tmp_path / "coupon_gcpw_pads" / "project.json").resolve()
    assert main(["run", str(pj)]) == 0
    w = window()
    w.open_project(pj)
    opened(w)
    assert len(w.results.canvas.figure.axes) == 3
    saved = board_file(pj, load_project(pj))
    assert saved == board.resolve()  # the copy under tmp_path, never the repo's fixture
    saved.write_bytes(saved.read_bytes().replace(b"(width 0.6)", b"(width 0.5)"))  # saved in KiCad, other copper
    assert control.open_project(pj).problem == ("E_RESULTS_STALE", {})  # the edit changed the model
    w.tick()
    assert w.loading is not None  # the save started a read
    opened(w)
    w.tick()
    assert w.loading is None  # read once per save
    assert w.results.canvas.figure.axes == [] and w.results.problem.text() == render("G_RESULTS_STALE")
    assert w.cost is None and not w.run_button.isEnabled()


def test_an_open_window_reads_its_board_again_after_a_save_that_broke_it(window, tmp_path):  # final review F9
    board, text = tmp_path / "coupon_gcpw_pads.kicad_pcb", (FIX / "coupon_gcpw_pads.kicad_pcb").read_bytes()
    board.write_bytes(text)  # a copy, which the test re-saves, as in F3's test
    assert main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "--preset", "draft",
                 "-o", str(tmp_path / "coupon_gcpw_pads")]) == 0
    pj = (tmp_path / "coupon_gcpw_pads" / "project.json").resolve()
    broken = text[:text.rindex(b")")]  # its last closing parenthesis gone, which load_board refuses
    board.write_bytes(broken)  # saved broken before the window opens
    w = window()
    w.open_project(pj)
    opened(w)
    refusal = control.text(*w.opened.problem)
    assert w.opened.problem[0] == "E_PARSE_UNBALANCED" and w.project_status.text() == refusal
    w.tick()
    assert w.loading is None  # no redundant read
    board.write_bytes(text)  # fixed and saved again
    w.tick()
    assert w.loading is not None  # read again, though the last read had no project
    opened(w)
    assert w.project_status.text() == render("G_PROJECT", path=str(pj), f0_mhz="915", harmonics=3, preset="draft")
    board.write_bytes(broken)  # saved broken again
    w.tick()
    assert w.loading is not None
    opened(w)
    assert w.project_status.text() == refusal
    w.tick()
    assert w.loading is None


def test_new_from_a_board_lists_its_pads_writes_the_project_and_opens_it(window, tmp_path, monkeypatch):
    board = tmp_path / "lpf915.kicad_pcb"  # design 5.3 Project; a copy, so the default folder is made beside it
    board.write_bytes((FIX / "lpf915.kicad_pcb").read_bytes())
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(board), ""))
    w = window()
    f = w.new_form
    assert (f.harmonics.value(), f.preset.currentText(), f.stackup.currentData(), f.lid.value(), f.lid.text()) == (
        3, "normal", None, 0.0, render("G_NONE"))  # new's defaults
    f.board_button.click()
    assert f.folder.text() == str(tmp_path / "lpf915")  # the README's `-o lpf915`, beside the board
    w.pads_read.result(timeout=60)
    w.tick()  # no project yet: the tick takes the pads all the same
    assert [f.start.itemText(i) for i in range(f.start.count())] == control.pads(board) and f.start.currentText() == ""
    grab(w, "new")
    f.f0.setText("lots")
    f.create_button.click()
    assert w.creating is None and f.status.text() == render("E_BAD_FREQUENCY", text="lots")
    f.f0.setText("915MHz")
    f.folder.setText("")
    f.board.editingFinished.emit()  # focus left the board field: the same board, so the folder typed stays
    f.create_button.click()
    assert (w.creating, f.folder.text(), f.status.text()) == (None, "", render("G_NEW_NO_FOLDER"))
    f.folder.setText(f" {tmp_path / 'lpf915'} ")  # pasted with spaces around it: new gets it stripped
    f.board.setText(f" {board} ")  # spaces around it (Windows drops a trailing one), no editingFinished: stripped too
    f.start.setCurrentText("U1.1")
    f.end.setCurrentText("J1.1")
    f.harmonics.setValue(2)
    f.preset.setCurrentText("draft")
    f.stackup.setCurrentIndex(f.stackup.findData("jlcpcb-2l"))
    f.lid.setValue(2.5)
    f.create_button.click()
    assert f.status.text() == render("G_CREATING") and not f.create_button.isEnabled()
    path, notes = w.creating.result(timeout=120)
    w.tick()
    pj = tmp_path / "lpf915" / "project.json"
    d = load_project(pj)
    assert path == pj and w.path == pj.resolve()
    assert (d["harmonics"], d["preset"], d["stackup"]["source"], d["lid_height_mm"]) == (2, "draft", "jlcpcb-2l", 2.5)
    assert items(f.notes) == [control.text(c, p) for c, p in notes] and items(f.notes)[-1] == render("I_WROTE", path=pj)
    opened(w)
    assert w.project_status.text() == render("G_PROJECT", path=str(pj.resolve()), f0_mhz="915", harmonics=2,
                                             preset="draft") and f.create_button.isEnabled()
    f.create_button.click()  # the same folder again: new refuses, in the window's words
    w.creating.exception(timeout=120)
    w.tick()
    assert f.status.text() == render("G_PROJECT_EXISTS", path=str(pj))
    assert items(f.notes) == []  # the last New's notes go with a refusal
    assert board.read_bytes() == (FIX / "lpf915.kicad_pcb").read_bytes()  # never written (anti-goal)
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # design 4: new ran in this process
    bad, text = tmp_path / "bad.kicad_pcb", (FIX / "lpf915.kicad_pcb").read_bytes()
    bad.write_bytes(text[:text.rindex(b")")])  # its last closing parenthesis gone, which load_board refuses
    f.board.setText(str(bad))
    w.board_chosen()
    error = w.pads_read.exception(timeout=60)
    w.tick()
    assert error.code == "E_PARSE_UNBALANCED" and f.status.text() == control.message(error)
    assert f.start.count() == f.end.count() == 0  # the pickers left empty
    bad.write_bytes(text)  # fixed on disk and picked again: read again
    w.board_chosen()
    assert w.pads_read is not None
    w.pads_read.result(timeout=60)
    w.tick()
    assert [f.start.itemText(i) for i in range(f.start.count())] == control.pads(bad)


def test_a_button_press_pre_fills_new_and_swap_swaps_start_and_end(window, tmp_path):  # design 5.3, 5.5; RF 2
    board = tmp_path / "lpf915.kicad_pcb"  # a copy: New's default folder is made beside it
    board.write_bytes((FIX / "lpf915.kicad_pcb").read_bytes())
    w = window()
    f = w.new_form
    f.board.setText(str(tmp_path / "other.kicad_pcb"))
    w.board_chosen()  # a pad list read in flight when the press comes
    stale = w.pads_read
    w.tabs.setCurrentIndex(3)
    f.status.setText(render("G_HANDOFF_PADS", count=3))  # the last press's line
    handoff = press(board, ["J1.1", "U1.1"])
    w.take_handoff(handoff)
    assert (w.tabs.currentIndex(), w.handoff, f.status.text()) == (0, handoff, "")
    assert w.pads_read not in (None, stale)  # the press is New's read now: the slower read of another board loses
    w.pads_read.result(timeout=60)
    w.tick()
    assert (f.board.text(), f.chosen, f.folder.text()) == (str(board), str(board), str(tmp_path / "lpf915"))
    assert [f.start.itemText(i) for i in range(f.start.count())] == control.pads(board)
    assert (f.start.currentText(), f.end.currentText()) == ("U1.1", "J1.1")  # the connector's pad is the end
    assert (w.handed.socket, w.handed.token, w.handed.board) == ("ipc://s", "T", board)
    grab(w, "handoff")
    f.swap_button.click()
    assert (f.start.currentText(), f.end.currentText()) == ("J1.1", "U1.1")
    f.board.editingFinished.emit()  # focus leaving the board KiCad sent: not read again
    assert w.pads_read is None
    w.take_handoff(press(board, ["C2.1"], ["C1", "J1"]))
    w.pads_read.result(timeout=60)
    w.tick()
    assert [f.end.itemText(i) for i in range(f.end.count())] == ["C1.1", "C1.2", "C2.1", "J1.1", "J1.2"]
    assert (f.start.currentText(), f.end.currentText(), f.status.text()) == ("C2.1", "", "")
    w.take_handoff(press(board, ["C1.1", "C2.1", "C3.1"]))
    w.pads_read.result(timeout=60)
    w.tick()
    assert (f.start.currentText(), f.status.text()) == ("", render("G_HANDOFF_PADS", count=3))
    later = tmp_path / "later.kicad_pcb"  # a board not on disk yet: refused, so picking it once it is reads it
    w.take_handoff(button.write_handoff({"board": str(later), "pads": [], "footprints": [], "kicad": "9.0.7",
                                         "socket": "ipc://s", "token": "T"}))
    w.pads_read.result(timeout=60)
    w.tick()
    assert (f.board.text(), f.chosen, f.start.count()) == (str(later), "", 0)  # plan 2's F4 rule, for a press too
    assert f.status.text() == render("E_BOARD_UNREADABLE", path=str(later), reason="file not found")
    later.write_bytes(board.read_bytes())
    w.board_chosen()
    assert w.pads_read is not None
    w.pads_read.result(timeout=60)
    w.tick()
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")  # a handoff file that does not parse
    w.take_handoff(bad)
    error = w.pads_read.exception(timeout=60)
    w.tick()
    assert f.status.text() == control.message(error)
    assert board.read_bytes() == (FIX / "lpf915.kicad_pcb").read_bytes()  # never written (anti-goal)


def test_the_gui_entry_takes_a_handoff_and_a_second_start_forwards_its_own_and_exits(qapp, fake, tmp_path,
                                                                                     monkeypatch):
    local = tmp_path / "local"  # design 5.5 Single instance; Review Focus 1
    monkeypatch.setattr(runs, "data_dir", lambda: local / "kicad-rf-studio")  # as a second process reads its env
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes((FIX / "lpf915.kicad_pcb").read_bytes())
    handoff = press(board, ["U1.1", "J1.1"])
    seen = []
    QTimer.singleShot(0, lambda: (seen.extend(qapp.topLevelWidgets()), qapp.exit()))  # exit: Qt 6's quit closes it
    assert gui.main(["--handoff", str(handoff)]) == 0
    w = next(x for x in seen if isinstance(x, MainWindow) and x.handoff == handoff)  # `seen` keeps it alive
    second, log = None, tmp_path / "second.log"
    try:
        if w.pads_read:
            w.pads_read.result(timeout=60)
        w.tick()
        f = w.new_form
        assert (f.start.currentText(), f.end.currentText()) == ("U1.1", "J1.1")
        assert (w.server.serverName(), w.server.isListening()) == (gui.instance_name(), True)
        w.showMinimized()
        w.server.close()  # as if this window were still starting: it holds gui.lock, but does not listen yet
        press(board, footprints=["C1"])  # the next press, into the same file
        env = {**os.environ, "LOCALAPPDATA": str(local), "XDG_DATA_HOME": str(local), "QT_QPA_PLATFORM": "offscreen"}
        with open(log, "wb") as err:
            second = subprocess.Popen([sys.executable, "-X", "utf8", "-I", "-c",
                                       "import sys; from kicad_rf_studio import gui; sys.exit(gui.main(sys.argv[1:]))",
                                       "--handoff", str(handoff)], env=env, stdout=subprocess.DEVNULL, stderr=err)
        begin = time.monotonic()
        until(lambda: qapp.processEvents() or time.monotonic() - begin > 2)  # it finds the lock held, and waits
        assert w.server.listen(gui.instance_name())  # listening at last: the waiting start forwards to it
        until(lambda: qapp.processEvents() or second.poll() is not None)  # this window's event loop runs meanwhile
        assert second.returncode == 0, log.read_text(encoding="utf-8", errors="replace")  # no window of its own
        until(lambda: qapp.processEvents() or [f.start.itemText(i) for i in range(f.start.count())] == ["C1.1",
                                                                                                         "C1.2"])
        assert not w.isMinimized() and w.tabs.currentIndex() == 0  # brought to the front, on New
    finally:
        if second is not None and second.poll() is None:
            second.kill()
            second.wait()
        w.close()
        w.pool.shutdown(wait=True)


@pytest.mark.skipif(sys.platform == "win32", reason="a socket file a killed window leaves on Linux")
def test_a_socket_file_left_by_a_killed_window_does_not_stop_the_next(qapp, fake):  # Review Focus 1
    from PySide6.QtCore import QDir
    Path(QDir.tempPath(), gui.instance_name()).write_text("")  # where QLocalServer puts its socket
    seen = []
    QTimer.singleShot(0, lambda: (seen.extend(qapp.topLevelWidgets()), qapp.exit()))  # exit: Qt 6's quit closes it
    assert gui.main([]) == 0
    w = next(x for x in seen if isinstance(x, MainWindow) and x.server and x.server.serverName() ==
             gui.instance_name())
    assert w.server.isListening()  # with an access option Qt binds beside the name and renames over the stale file
    w.close()
    w.pool.shutdown(wait=True)


def column(table, c):
    return [table.item(k, c).text() for k in range(table.rowCount())]


def test_the_retune_table_snaps_takes_s2p_parts_and_draws_under_the_what_if_label(window, qapp, tmp_path, monkeypatch):
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # design 5.3 Retune, What-if; Review Focus 1, 2
    (tmp_path / "parts").mkdir()
    l1 = write_s2p(tmp_path / "parts" / "l1.s2p", z_part("L", 18e-9, None, F), "series", F)
    c3 = write_s2p(tmp_path / "parts" / "c3.s2p", z_part("C", 3.9e-12, None, F), "shunt", F)  # measured shunt
    missing = tmp_path / "parts" / "none.s2p"
    w = window()
    w.open_project(pj)
    opened(w)
    r, fig, label = w.results, w.results.canvas.figure, "\n" + render("G_WHAT_IF")
    stored = ["100pF", "15nH", "3.3pF", "3.3pF"]
    assert column(r.parts, PART) == ["C1", "L1", "C2", "C3"] and column(r.parts, VALUE) == stored
    assert [r.parts.cellWidget(k, SNAP).currentData() for k in range(4)] == ["E24"] * 4  # design 7: E24 for L and C
    assert w.tabs.tabText(3) == render("G_TAB_RESULTS") and not r.retune_box.isHidden()
    r.parts.item(2, VALUE).setText("5pF")  # typed, then snapped to E24
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows())
    assert r.parts.item(2, VALUE).text() == "5.1pF"
    assert np.array_equal(fig.axes[0].lines[0].get_ydata(), 20 * np.log10(np.abs(res.chain[:, 1, 0])))
    assert fig.get_suptitle().endswith(label) and not r.what_if.isHidden()  # the retuned plot, under the label
    assert items(r.lines) == [control.text(c, p) for c, p in res.lines] + [render(c) for c in LIMITS]
    w.tabs.setCurrentWidget(r)
    qapp.processEvents()  # the layout settles
    assert all(r.parts.viewport().rect().contains(r.parts.visualRect(r.parts.model().index(k, PART)))
               for k in range(4))  # visual review V1: every row whole, none cut behind a scroll bar
    grab(w, "retune")
    r.parts.cellWidget(3, SNAP).setCurrentIndex(control.SERIES.index("off"))
    r.parts.item(3, VALUE).setText("5pF")
    r.parts.setCurrentCell(2, VALUE)  # another row current: a Snapping combo snaps its own row
    r.parts.cellWidget(3, SNAP).setCurrentIndex(control.SERIES.index("E12"))
    assert column(r.parts, VALUE) == ["100pF", "15nH", "5.1pF", "4.7pF"]
    r.parts.cellWidget(2, SNAP).setCurrentIndex(control.SERIES.index("off"))
    r.parts.item(2, VALUE).setText("4p7")
    assert r.parts.item(2, VALUE).text() == "4p7"  # free text, kept as typed
    r.parts.item(2, VALUE).setText("15nH")  # Review Focus 1: a value the engine cannot read
    assert items(r.lines)[0] == render("G_RETUNE_VALUE", ref="C2", value="15nH")
    assert fig.axes == [] and r.what_if.isHidden()  # no curve of values that do not read
    r.parts.item(2, VALUE).setText("3.3pF")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(missing), ""))
    r.parts.setCurrentCell(1, S2P)
    r.s2p_button.click()  # Review Focus 2: a file that is not there
    assert render("G_S2P_MISSING", ref="L1", path=str(missing.resolve())) in items(r.lines) and fig.axes == []
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(l1), ""))
    r.s2p_button.click()
    zk = lpf_loads(M0402, C3=4.7e-12)
    zk[:, 1] = with_box(z_part("L", 18e-9, None, F), F, C_BOX)
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows())
    assert np.abs(res.chain - terminate_np(star(F, 6), [0, 1], zk)).max() <= 1e-5 and len(fig.axes) == 3
    assert fig.get_suptitle().endswith(label) and not r.what_if.isHidden()  # drawn again, under the label
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(c3), ""))
    r.parts.setCurrentCell(3, S2P)
    r.s2p_button.click()  # its fixture still series: retune's own warning, in the window's words
    assert render("G_S2P_FIXTURE", ref="C3", path=str(c3.resolve()), named="series", fits="shunt") in items(r.lines)
    r.parts.cellWidget(3, FIXTURE).setCurrentIndex(1)  # shunt
    zk[:, 3] = with_box(z_part("C", 3.9e-12, None, F), F, C_BOX)
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows())
    assert r.rows()[3].connection == "shunt" and np.abs(res.chain - terminate_np(star(F, 6), [0, 1], zk)).max() <= 1e-5
    r.revert_button.click()
    assert column(r.parts, VALUE) == stored and column(r.parts, S2P) == [""] * 4
    assert np.array_equal(fig.axes[0].lines[0].get_ydata(), 20 * np.log10(np.abs(w.opened.results.chain[:, 1, 0])))
    assert fig.get_suptitle().endswith(label) and not r.what_if.isHidden()
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # design 4: the session ran in this process


def test_a_read_keeps_the_unapplied_values_unless_project_json_changed_their_part(window, tmp_path, monkeypatch):
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # design 5.3: rebuilt when the results change; Review Focus 5
    w = window()
    w.open_project(pj)
    opened(w)
    r, fig = w.results, w.results.canvas.figure
    r.parts.cellWidget(2, SNAP).setCurrentIndex(control.SERIES.index("off"))
    r.parts.item(2, VALUE).setText("4.7pF")
    save_project(pj, load_project(pj))  # no part changed: as a cost's, a run's or a verify's end reads it again
    w.tick()
    assert w.loading is not None and not r.retune_box.isEnabled()  # busy while the read goes on
    opened(w)
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows())
    assert column(r.parts, VALUE)[2] == "4.7pF" and r.retune_status.text() == "" and r.retune_box.isEnabled()
    assert r.parts.cellWidget(2, SNAP).currentData() == "off"  # set per part (design 7)
    assert np.array_equal(fig.axes[0].lines[0].get_ydata(), 20 * np.log10(np.abs(res.chain[:, 1, 0])))
    d = load_project(pj)
    parts(d)["C3"]["value"] = "3.9pF"  # a hand edit of another part (values are not in the model)
    save_project(pj, d)
    w.tick()
    opened(w)
    assert column(r.parts, VALUE) == ["100pF", "15nH", "4.7pF", "3.9pF"] and r.retune_status.text() == ""
    parts(d)["C2"]["value"] = "3.9pF"  # a hand edit, or a terminal's retune, of the part being retuned
    save_project(pj, d)
    w.tick()
    opened(w)
    assert column(r.parts, VALUE)[2] == "3.9pF" and r.retune_status.text() == render("G_DROPPED")


def test_a_retune_moves_the_curves_in_place_and_blits_them_within_the_budget(window, qapp, tmp_path, monkeypatch):
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # design 5.4, goal 4: a redraw measured over 50 ms on lpf915
    w = window()
    w.open_project(pj)
    opened(w)
    r, fig = w.results, w.results.canvas.figure
    w.tabs.setCurrentWidget(r)
    qapp.processEvents()  # the first paint draws the canvas, and on_draw keeps its background for the blits
    axes, draws, real = list(fig.axes), [], r.canvas.draw
    monkeypatch.setattr(r.canvas, "draw", lambda: draws.append(1) or real())
    timings = []
    for text in ("5pF", "3.3pF", "5pF"):  # each snapped on commit: the GUI thread's whole path, end to end
        start = time.perf_counter()
        r.parts.item(2, VALUE).setText(text)
        timings.append(time.perf_counter() - start)
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows())
    assert min(timings) < 0.05 and r.parts.item(2, VALUE).text() == "5.1pF"
    assert draws == [] and fig.axes == axes == list(r.axes)  # moved in place and blitted, never redrawn
    assert np.array_equal(r.curves[0].get_ydata(), 20 * np.log10(np.abs(res.chain[:, 1, 0])))
    assert fig.get_suptitle().endswith("\n" + render("G_WHAT_IF")) and not r.what_if.isHidden()
    r.parts.item(2, VALUE).setText("15nH")  # a refusal clears the plot; the next good value draws it in full
    assert fig.axes == [] and r.curves == []
    r.parts.item(2, VALUE).setText("3.3pF")
    assert len(fig.axes) == 3
    assert np.array_equal(r.curves[0].get_ydata(), 20 * np.log10(np.abs(w.opened.results.chain[:, 1, 0])))


def test_apply_stores_the_values_through_retune_and_the_window_reads_them_back(window, tmp_path, monkeypatch):
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # design 5.3 Apply
    w = window()
    w.open_project(pj)
    opened(w)
    r, summary = w.results, pj.parent / "results" / "summary.csv"
    applied, written = render("G_APPLIED", folder=str(pj.parent / "results")), summary.stat().st_mtime_ns
    assert r.apply_button.isEnabled()  # nothing changed: retune writes the outputs alone (C-19)
    r.apply_button.click()
    w.applying.result(timeout=120)
    w.tick()
    assert r.retune_status.text() == applied and summary.stat().st_mtime_ns != written and w.loading is None
    r.parts.item(2, VALUE).setText("4.7pF")
    r.apply_button.click()
    assert r.retune_status.text() == render("G_APPLYING") and not r.parts.isEnabled() and not r.apply_button.isEnabled()
    w.applying.result(timeout=120)
    w.tick()
    assert r.retune_status.text() == applied and parts(load_project(pj))["C2"]["value"] == "4.7pF"
    assert w.loading is not None and not r.retune_box.isEnabled()  # project.json's new mtime: read again
    opened(w)
    assert column(r.parts, VALUE) == ["100pF", "15nH", "4.7pF", "3.3pF"] and r.retune_status.text() == applied
    assert r.apply_button.isEnabled() and r.parts.isEnabled()
    r.parts.item(2, VALUE).setText("3.3pF")
    r.apply_button.click()
    old = w.applying
    w.open_project(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))  # another project meanwhile
    old.result(timeout=120)
    opened(w)
    assert w.applying is None and r.retune_status.text() == ""  # its end is not the open project's


def test_apply_waits_while_a_run_holds_the_lock_and_shows_retunes_own_refusal(window, tmp_path, monkeypatch):
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # design 5.1; Review Focus 3
    w = window()
    w.open_project(pj)
    opened(w)
    r = w.results
    r.parts.item(2, VALUE).setText("4.7pF")
    lock = runs.lock_file(pj)
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    w.tick()
    assert not r.apply_button.isEnabled()  # disabled while any run holds the lock
    w.apply()  # the lock came between the click and retune: retune refuses it itself
    w.applying.result(timeout=120)
    w.tick()
    assert r.retune_status.text() == render("E_LOCKED", lock=str(lock), run="R", started="S")  # the CLI's own line
    assert parts(load_project(pj))["C2"]["value"] == "3.3pF" and r.parts.item(2, VALUE).text() == "4.7pF"
    lock.unlink()
    w.tick()
    assert r.apply_button.isEnabled()  # enabled again once the lock goes, the value still unapplied


def test_verify_asks_to_apply_first_runs_detached_and_shows_its_comparison(window, tmp_path, monkeypatch):
    pj = verified(tmp_path, monkeypatch).resolve()  # tests/test_verify.py: lpf915 on the network fake; Review Focus 4
    monkeypatch.setenv("KRS_FAKE_CBOX", "6e-16")  # the detached verify's cell C, as verified() patches it here
    w = window()
    w.open_project(pj)
    opened(w)
    r, asked = w.results, []
    assert r.stale.text() == render("G_VERIFY_NONE") and not r.stale.isHidden() and r.verify_button.isEnabled()
    r.parts.item(2, VALUE).setText("15nH")  # a value retune refuses
    monkeypatch.setattr(w, "ask", lambda text: asked.append(text) or False)
    r.verify_button.click()  # unapplied values: Apply first? No: nothing starts
    assert asked == [render("G_APPLY_FIRST")] and w.applying is None and w.command != "verify"
    monkeypatch.setattr(w, "ask", lambda text: asked.append(text) or True)
    r.verify_button.click()  # Yes, but retune refuses the value: no verify of the stored ones
    assert w.applying is not None and not r.verify_button.isEnabled()  # disabled while Apply runs
    w.applying.result(timeout=120)
    w.tick()
    assert w.command != "verify" and not w.verify_next
    assert r.retune_status.text() == render("E_RETUNE_VALUE", ref="C2", value="15nH")  # retune's own line
    r.parts.item(2, VALUE).setText("4.7pF")
    r.verify_button.click()  # Yes: Apply, then verify
    w.applying.result(timeout=120)
    w.tick()  # Apply stored them: verify starts on them, with no cost confirmation of its own
    assert (w.command, w.proc is not None, len(asked)) == ("verify", True, 3)
    until(lambda: w.tick() or w.run_status.text() == render("G_END_DONE", exit_code=0))
    assert any(x.startswith("Worst case: ") for x in items(w.log))  # its own cost lines, live
    opened(w)  # its end read the project again, comparison included
    assert load_project(pj)["verify"]["values"]["C2"] == "4.7pF" and r.stale.isHidden()
    assert [c for c, _ in w.opened.verified][:2] == ["I_VERIFY_RESULTS", "I_VERIFY_COMPARE"]
    assert items(r.verify_lines) == [control.text(c, p) for c, p in w.opened.verified]
    w.tabs.setCurrentWidget(r)
    grab(w, "verify")
    r.parts.item(1, VALUE).setText("12nH")
    assert r.stale.text() == render("G_VERIFY_STALE") and not r.stale.isHidden()
    again = window()  # re-attached like a run: a window opened later replays the verify that ended
    again.open_project(pj)
    opened(again)
    assert again.run_dir == w.run_dir and again.run_status.text() == render("G_END_DONE", exit_code=0)
    lock = runs.lock_file(pj)
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": str(pj.parent / "results"), "started": "S"}),
                    encoding="utf-8")  # another window's retune holds it
    w.tick()
    assert not r.verify_button.isEnabled()  # design 5.1: disabled while any run holds the lock
    lock.unlink()
    w.tick()
    assert r.verify_button.isEnabled()
    r.verify_button.click()  # 12nH unapplied: Apply, then verify; but another project is opened meanwhile
    old = w.applying
    w.open_project(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))
    old.result(timeout=120)
    opened(w)
    assert (w.applying, w.verify_next, w.command) == (None, False, None)  # no verify of the project now open


def test_advanced_saves_project_json_under_the_lock_and_a_model_change_marks_the_results_stale(
        window, tmp_path, monkeypatch):
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # design 5.1, 5.3 Advanced; Review Focus 5
    w = window()
    w.open_project(pj)
    opened(w)
    a, lock = w.advanced, runs.lock_file(pj)
    row = {a.table.item(k, 0).text(): k for k in range(a.table.rowCount())}
    assert [a.table.item(row["t_max_s"], c).text() for c in range(4)] == ["t_max_s", "4e-08", "4e-08",
                                                                          render("G_UNIT_S")]
    assert "results.run_dir" not in row and not a.save_button.isEnabled()
    w.tabs.setCurrentWidget(a)
    grab(w, "advanced")
    a.table.item(row["harmonics"], 1).setText("0")
    w.tick()
    a.save_button.click()  # the project's own checks refuse it; nothing is written
    assert a.status.text() == render("G_PROJECT_FIELD", path=str(pj), field="harmonics",
                                     expected="a whole number above 0") and load_project(pj)["harmonics"] == 3
    a.table.item(row["harmonics"], 1).setText("3")
    a.table.item(row["t_max_s"], 1).setText("3e-08")  # T_max is in the model's excitation
    w.tick()
    d = load_project(pj)
    parts(d)["C3"]["value"] = "3.9pF"  # a terminal's retune after the last read: Save keeps it
    save_project(pj, d)
    w.results.parts.item(2, VALUE).setText("4.7pF")  # an unapplied value, which the stale read drops
    a.save_button.click()
    assert (load_project(pj)["t_max_s"], parts(load_project(pj))["C3"]["value"]) == (3e-08, "3.9pF")
    assert a.status.text() == render("I_WROTE", path=pj)
    opened(w)  # the new mtime read the project again: its model changed, so its results are stale
    assert w.results.retune_status.text() == render("G_DROPPED")
    assert w.results.problem.text() == render("G_RESULTS_STALE") and w.results.retune_box.isHidden()
    assert w.results.canvas.figure.axes == [] and a.edits == {}
    a.table.item(row["t_max_s"], 1).setText("4e-08")
    w.tick()
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    a.save_button.click()  # a run took the lock after the last tick: Save refuses, as the engine's writers do
    assert a.status.text() == render("G_LOCKED", lock=str(lock), run="R", started="S")
    assert load_project(pj)["t_max_s"] == 3e-08
    w.tick()
    assert not a.table.isEnabled() and not a.save_button.isEnabled()  # disabled while the lock is held
    lock.unlink()


def test_the_help_menu_shows_about_and_qts_about(window, monkeypatch):  # design 5.3 About
    seen = []
    monkeypatch.setattr(QMessageBox, "about", lambda parent, title, text: seen.append((title, text)))
    monkeypatch.setattr(QMessageBox, "aboutQt", lambda parent, title="": seen.append("Qt"))
    w = window()
    assert [a.text() for a in w.menuBar().actions()] == [render("G_MENU_HELP")]
    w.about_action.trigger()
    w.about_qt_action.trigger()
    assert seen == [(render("G_ABOUT"), control.about()), "Qt"]
