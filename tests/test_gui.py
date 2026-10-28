# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI (Stage 2 design 5): its dependency and entry point, the import rules, and the main window offscreen on
the fake CLI."""
import gc
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog

from kicad_rf_studio import gui, pipeline, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.post.outputs import LIMITS
from kicad_rf_studio.core.project import board_file, load_project, save_project
from kicad_rf_studio.gui import control
from kicad_rf_studio.gui.window import MainWindow
from test_cli_cost import FIX, fail, new_project
from test_gui_control import FAKE_PREFIX, until
from test_run import lpf_run

ROOT = Path(__file__).resolve().parents[1]
QT_FREE = ("kicad_rf_studio.cli", "kicad_rf_studio.worker", "kicad_rf_studio.pipeline", "kicad_rf_studio.runs",
           "kicad_rf_studio.gui", "kicad_rf_studio.gui.control")


def test_pyside6_essentials_is_a_core_dependency_with_the_gui_entry():  # design 5.6, A-15
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "PySide6-Essentials>=6.10.1,<7" in project["dependencies"]
    assert project["gui-scripts"] == {"kicad-rf-studio-gui": "kicad_rf_studio.gui:main"}
    names = {re.split(r"[<>=!~;\[ ]", d, maxsplit=1)[0].lower()
             for d in project["dependencies"] + project["optional-dependencies"]["dev"]}
    assert not names & {"pyside6", "pyside6-addons", "pytest-qt"}  # Essentials only (design 4, 5.8)


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
    f.folder.setText(str(tmp_path / "lpf915"))
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
    assert board.read_bytes() == (FIX / "lpf915.kicad_pcb").read_bytes()  # never written (anti-goal)
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # design 4: new ran in this process
