# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI (Stage 2 design 5): its dependency and entry point, the import rules, and the main window offscreen on
the fake CLI."""
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
from kicad_rf_studio.core.project import load_project, save_project
from kicad_rf_studio.gui import control
from kicad_rf_studio.gui.window import MainWindow
from test_cli_cost import fail, new_project
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


@pytest.fixture
def window(qapp, calibrated, monkeypatch):
    """MainWindow on the fake CLI, shown offscreen, with runs.run_jobs and runs.ensure_calibrated failing in this
    process from the first window on (design 5.1: a test's own engine calls come before it); what it started is
    killed and its project reads awaited at teardown."""
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
        if w.proc is not None and w.proc.poll() is None:
            w.proc.kill()
            w.proc.wait()
        w.close()
        w.pool.shutdown(wait=True)  # a read still going would outlive the fake data folder


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
