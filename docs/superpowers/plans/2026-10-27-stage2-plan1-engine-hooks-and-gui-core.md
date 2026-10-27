# Stage 2 · Plan 1 — Engine Hooks and GUI Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the engine the nine hooks a GUI needs (design §5.2) and build the GUI core on them: a PySide6 main window that opens a project, shows its cost, starts, stops and re-attaches a detached run with live progress, and shows its results under the what-if label.

**Architecture:**
- **Engine first (Tasks 1–4),** each change test-first and result-neutral: `python -m kicad_rf_studio`; `--run-dir DIR` on cost, run and verify; an `end` event from `cli.main`'s `finally` in every run folder a command has by its end; cost's lines as events; the first-use calibration inside the caller's run folder, under its STOP; `runs.lock_holder`; `cli.new()` returning its notes; `snap()`; the output step split into `pipeline.chain_results` and `outputs.draw_summary`, its files byte-identical.
- **Then the GUI (Tasks 5–9)** in `src/kicad_rf_studio/gui/`: the Qt-free `control.py` (the detached start, the events tail, re-attach through the lock and the end events, the project read off the GUI thread) and `window.py` (one main window driven by one 500 ms timer: on its own process in Task 7, re-attaching in Task 8, and with the Results tab drawing summary.png's plots on a `FigureCanvasQTAgg` in Task 9). The GUI process never reaches `runs.run_jobs`: cost and run go through `python -X utf8 -I -m kicad_rf_studio <command> PROJECT --run-dir DIR`, detached. Task 10 is the controller's offscreen visual review.

**Tech Stack:** Python ≥ 3.11 (the dev venv runs 3.14.2). PySide6-Essentials ≥ 6.10.1, < 7 (QtCore, QtWidgets; the offscreen platform in tests). matplotlib's `FigureCanvasQTAgg` (3.11.2 in the venv) and scikit-rf's Smith chart. The stdlib's `subprocess`, `concurrent.futures`, `json`, `dataclasses`, `threading` (tests) and `pathlib`. pytest, with no pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-27-stage2-gui-and-button-design.md` (binding), its §5.9 item 1: §5.1, §5.2 (all nine additions), §5.3's Project-open, Cost, Run, Results and What-if parts, §5.4, §5.6's PySide6 dependency, entry point and import test, §5.7 and §5.8; §3 (anti-goals) and §4 (constraints) bind every task. The research is `.superpowers/sdd/stage2-research/r2-gui/findings.md` and `r3-pack/findings.md` (git-ignored, local). The engine authority is `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, amended here: §3.2 (A-14, Task 2), §3.3 and §6.1 (A-13, Task 2), §3.4 (A-15, Task 5). §7.6's label stays as it is.

**Branch:** `stage2-plan1`, from `main` at `9277b9b`. This plan is `docs/superpowers/plans/2026-10-27-stage2-plan1-engine-hooks-and-gui-core.md`. Commands run from the repo root with `.venv/Scripts/python`.

**Before Task 1 (the controller):**
1. Branch `stage2-plan1` from `main`. `git diff --stat 9277b9b HEAD -- src tests tools pyproject.toml .github` prints nothing; otherwise re-check this plan's line references first.
2. Commit this plan on the branch with the rulings returned with it appended as its last section, `## Controller rulings (2026-10-27; binding)`.
3. After Task 10: the whole-branch review, then a local merge into `main`. Nothing is pushed.

## Global Constraints

- **Python and platforms:** the declared floor stays `>=3.11` and the CI matrix stays as it is; the Windows install uses Python 3.14 (the openEMS 0.37.0 wheels need 3.13 or 3.14); Windows 10/11 and Linux with glibc ≥ 2.34.
- **Dependencies:** this plan adds only `PySide6-Essentials>=6.10.1,<7`, as a core dependency with no extra: no QtCharts, no Addons, no pytest-qt. kicad-python is plan 3's. Install only into the dev venv: `.venv/Scripts/python -m pip install -e .[dev]`.
- **Import rules (design §4):** the core never imports Qt; the GUI never imports openEMS or CSXCAD; `cli` and `worker` import neither Qt nor kicad-python; matplotlib still loads only inside the PNG writer and the GUI (C-5). `kicad_rf_studio/gui/__init__.py` imports Qt only inside `main()`, and `gui/control.py` never; neither loads matplotlib.
- **Process model (design §5.1):** nothing in the GUI process reaches `runs.run_jobs` (the window fixture makes `runs.run_jobs` and `runs.ensure_calibrated` fail in the test process); cost and run start detached through `control.start`; matplotlib draws only on the GUI thread.
- **No run logic in the GUI (design §3):** the GUI calls the engine in the CLI's order and adds no gate, stop rule or reduction; its numbers come only from `pipeline.chain_results`.
- **What-if:** while `pipeline.RETUNE_VALIDATED` is False, every chain result the GUI shows carries `G_WHAT_IF`, whose text is `I_WHAT_IF`'s with "Verify" in place of the command.
- **Messages:** every user-facing string is a code in the one CATALOG of `core.messages`, rendered with `render()`; GUI codes start with `G_`; no `.ts` or `.qm` files. Events stay language-neutral (Stage 1 §3.3). Tests check `KrsError.code` and `.params`, or rendered lines, never `match=`.
- **Licence and files:** GPL-3.0-or-later; an English UI; `# SPDX-License-Identifier: GPL-3.0-or-later` heads every new `.py` file.
- **Tests:** test-first; tier (a) never runs openEMS; Qt tests run under `QT_QPA_PLATFORM=offscreen`, set in `tests/conftest.py`; detached runs go through `tests/fake_cli.py`, whose table of patches the `fake` fixture applies too; before every commit the full suite, `.venv/Scripts/python -m pytest -q` (about 13 minutes before this plan), passes.
- **Privacy:** the pre-commit privacy gate runs on every commit (never `--no-verify`); synthetic fixtures only (`tests/fixtures`); no absolute user path, drive letter followed by a colon and a slash, e-mail address or private name in any committed file. Tests build paths as `Path("venv", "Scripts", "pythonw.exe")`. No test reads the user's data folder: every window's project reads finish before its test's fake data folder goes.
- **Git:** commits carry no co-author line; nothing is pushed and nothing goes to PyPI. Push-gated checks (Linux CI's Qt packages) are written, not run.
- **Workflow:** every implementer runs `graphify query "<question>"` (or `explain`/`path`) from the repo root before reading code, and `graphify update .` after each commit. Ponytail: the laziest solution that works, the repo's functions reused, the fewest files, the stdlib first, a `ponytail:` comment on each corner with a known ceiling.
- **Amendments:** each changed spec line ends with "(A-n, Stage 2 plan 1: controller recommendation, owner unavailable)", and the spec's Status line gets one sentence.

## Review Focus

1. **The GUI closed mid-run, then reopened** (or a run started in another window or a terminal, or one that ended while no window was open): the run goes on; the new window re-attaches through the lock, replays its events, shows Stop and the `G_LOCKED` banner, keeps Cost and Run disabled, and Stop ends it; a window opened after it ended replays it with its end state. Tests (Task 8): `test_a_window_closed_mid_run_leaves_it_running_and_a_new_one_attaches_with_stop` (its third window); Qt-free (Task 6): `test_a_run_going_on_is_found_through_its_lock_and_stops_by_its_stop_file`, and `test_open_project_reads_results_only_while_they_apply` (its `last`).
2. **A run refused before the lock** (another run holds it, no ports, a project that cannot be read): the given folder gets the refusal as a message event, then the end event with exit 2, so the GUI reads `G_END_REFUSED` with the reason, never "running" forever. Tests: `test_a_refusal_before_the_lock_is_a_message_then_the_end_event` (Task 2), the exit-2 row of `test_the_run_state` (Task 6).
3. **The window left to its own timer** (the real app, which no test ticks by hand): the 500 ms timer starts with the window, Open reads the project off the GUI thread, a display that fails once does not stop the next tick, and a save reads the project once, not on every tick; under it, a partial last line in events.jsonl (Windows ends lines with `\r\n`) is held back until its newline arrives and a malformed line is skipped. Tests: `test_the_window_drives_itself_and_survives_a_display_that_fails` (Task 7), the stale step of `test_results_show_the_chain_under_the_what_if_label_and_go_when_stale` (Task 9: no read pending after a further tick), `test_the_tail_holds_back_a_partial_last_line` (Task 6).
4. **A stale lock** (the orchestrator killed by Task Manager, a crash or a reboot): no end event, the lock left with a dead pid. The window that started it reads `G_END_EXITED` with the exit code, another window `G_END_LOST`; Run stays enabled, a cost started meanwhile keeps its tab, and the next run reclaims the lock. Tests: the dead-lock and exited rows of `test_the_run_state` (Task 6), `test_a_killed_run_reads_lost_and_its_stale_lock_does_not_block_the_next` (Task 8).
5. **Stale results** (project.json edited by hand, or the board re-saved with other copper, after the run): the Results tab shows `G_RESULTS_STALE` and no old plot. Tests: `test_open_project_reads_results_only_while_they_apply` (Task 6), the stale step of `test_results_show_the_chain_under_the_what_if_label_and_go_when_stale` (Task 9).

---

## File structure

```
src/kicad_rf_studio/__main__.py  cli.py  runs.py  pipeline.py   # T1–T4: the engine hooks
src/kicad_rf_studio/core/messages.py       # T1 E_RUN_DIR; T2 I_END, detail(); T5–T9 the G_ codes
src/kicad_rf_studio/core/kicad/values.py   # T3 E12, E24, snap
src/kicad_rf_studio/core/post/outputs.py   # T4 draw_summary
src/kicad_rf_studio/gui/__init__.py        # T5 main (a bare window, gui.log); T7 main (the main window)
src/kicad_rf_studio/gui/control.py         # T6 the Qt-free launcher, tail and re-attach
src/kicad_rf_studio/gui/window.py          # T7 MainWindow on its own process; T8 re-attach; T9 ResultsView
pyproject.toml  .github/workflows/ci.yml  docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
tests/test_run_dir.py  test_runs.py  test_verify.py  test_values.py  test_cli_new.py  test_post_outputs.py  test_run.py   # T1–T4
tests/conftest.py  fake_cli.py  test_gui_control.py  test_gui.py   # T5–T9
```

---

### Task 1 [code]: `python -m kicad_rf_studio`, `--run-dir` and `runs.lock_holder`

**Files:**
- Create: `src/kicad_rf_studio/__main__.py`, `tests/test_run_dir.py`.
- Modify: `src/kicad_rf_studio/cli.py` (`_cost` L144–147, `_run` L150–153, `_verify` L162–165, the cost/run/verify parsers L200–212, `main` L223–238); `src/kicad_rf_studio/pipeline.py` (`cost` L310–343, `run` L474–490, `_locked` L493–503, `verify` L719–746); `src/kicad_rf_studio/runs.py` (new functions before `project_lock`, which is L162–185, and `project_lock` itself); `src/kicad_rf_studio/core/messages.py` (after `E_LOCKED`, L88).
- Test: `tests/test_run_dir.py`, `tests/test_runs.py`, `tests/test_verify.py`.

**Interfaces:**
- Consumes: `runs._alive`, `runs.run_dir_for`, `pipeline.project_path`, `messages.reason`; in tests, conftest's `calibrated`, test_cli_cost's `new_project` and test_verify's `verified`.
- Produces:
  - `python -m kicad_rf_studio ARGS` runs `cli.main` (a guarded `__main__.py`).
  - `cost`, `run` and `verify` take `--run-dir DIR` (`type=Path`, `metavar="DIR"`). `cli.main` makes it absolute (a relative DIR is read from the working folder) and makes it (`mkdir(parents=True, exist_ok=True)`) before the command. It refuses with `E_RUN_DIR {path, reason}` when it cannot (`reason(e, "cannot be made")`), or when the folder already holds a run (an `events.jsonl` in it: reason "already holds a run"), writing nothing into it.
  - `pipeline.cost(path: Path, run_dir: Path | None = None) -> int`, `pipeline.run(path: Path, run_dir: Path | None = None) -> int` and `pipeline.verify(path: Path, run_dir: Path | None = None) -> int`: a given folder is the run folder, else `runs.run_dir_for(path.absolute().parent.name)` as before. `_locked(path, body, run_dir=None)` makes it with `exist_ok=True`.
  - `runs.lock_file(project_path: Path) -> Path`: `project.json.lock` beside the project.
  - `runs.lock_holder(project_path: Path) -> dict | None`: None without a lock; else the lock's `{"pid", "run_dir", "started"}` plus `"alive": runs._alive(pid)`; a lock that does not parse yet (made, not yet written) is `{"pid": None, "run_dir": None, "started": None, "alive": True}`.
  - `runs._unlink(path: Path) -> None`: `path.unlink(missing_ok=True)`, retried every 20 ms for about 1 s on `PermissionError`, then once more letting it raise.
  - `project_lock` reads its holder through `lock_holder`: it loops again when the holder is None (released meanwhile); reads a holder whose `pid` is None (still being written) again every 50 ms, 20 times at most, before it counts as held; and deletes the lock, on release and on a stale reclaim, through `_unlink`.
  - CATALOG `"E_RUN_DIR": "Cannot use {path} as the run folder: {reason}. Give another --run-dir."`

- [ ] **Step 1: Write the failing tests.** `tests/test_run_dir.py`:

```python
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
```

  At the end of `tests/test_runs.py` (`import threading` beside its other imports):

```python
def test_the_lock_holder_and_whether_it_lives(tmp_path):  # design 5.1, 5.2 item 6
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    assert runs.lock_file(pj) == lock and runs.lock_holder(pj) is None
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    assert runs.lock_holder(pj) == {"pid": os.getpid(), "run_dir": "R", "started": "S", "alive": True}
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    assert runs.lock_holder(pj)["alive"] is False
    lock.write_text("", encoding="utf-8")  # made by O_EXCL, not yet written: a run starting
    assert runs.lock_holder(pj) == {"pid": None, "run_dir": None, "started": None, "alive": True}


def test_a_lock_released_while_it_is_read_is_taken(tmp_path, monkeypatch):  # was E_INTERNAL (FileNotFoundError)
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    real = runs.lock_holder

    def released(path):  # the holder ends between this run's O_EXCL and its read
        lock.unlink()
        return real(path)

    monkeypatch.setattr(runs, "lock_holder", released)
    with runs.project_lock(pj, tmp_path / "new"):
        assert json.loads(lock.read_text(encoding="utf-8"))["run_dir"] == str(tmp_path / "new")


def test_a_lock_still_being_written_is_waited_for(tmp_path):  # never "running since None in None"
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    lock.write_text("", encoding="utf-8")  # made by O_EXCL, not yet written
    holder = json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"})
    threading.Timer(0.1, lock.write_text, [holder], {"encoding": "utf-8"}).start()
    with pytest.raises(KrsError) as e:
        with runs.project_lock(pj, tmp_path / "new"):
            pass
    assert (e.value.code, e.value.params) == ("E_LOCKED", {"lock": str(lock), "run": "R", "started": "S"})


def test_the_lock_is_released_though_a_reader_holds_it_a_moment(tmp_path):  # the GUI reads it every 500 ms
    pj = tmp_path / "project.json"
    with runs.project_lock(pj, tmp_path / "run"):
        reader = open(runs.lock_file(pj), encoding="utf-8")  # Windows refuses to delete a file open elsewhere
        threading.Timer(0.2, reader.close).start()
    assert not runs.lock_file(pj).exists()
```

  At the end of `tests/test_verify.py`:

```python
def test_verify_uses_the_run_folder_it_is_given(tmp_path, calibrated, monkeypatch):  # Stage 2 design 5.2 item 2
    pj = verified(tmp_path, monkeypatch)
    save_project(pj, {**load_project(pj), "t_max_s": 30e-9})  # T_max is in the model's excitation: stale results
    d = tmp_path / "gui runs" / "v"
    assert main(["verify", str(pj), "--run-dir", str(d)]) == 2
    codes = [json.loads(line)["code"] for line in (d / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert codes[0] == "W_FILLS_AS_SAVED" and "E_RESULTS_STALE" in codes and not list(d.glob("job-*"))
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_run_dir.py tests/test_runs.py tests/test_verify.py -q`. Expected: FAIL — `python -m` exits 1 ("'kicad_rf_studio' is a package and cannot be directly executed"), argparse exits 2 on `--run-dir`, `AttributeError: ... 'lock_file'`; on Windows the held-lock test ends in `PermissionError: [WinError 32]`.
- [ ] **Step 3: Implement.**
  - `src/kicad_rf_studio/__main__.py`: the SPDX line, a docstring ("`python -m kicad_rf_studio` runs the CLI: how Stage 2's GUI starts the orchestrator (design 5.1)"), then `if __name__ == "__main__": sys.exit(main())` with `from kicad_rf_studio.cli import main`.
  - `cli.py`: `--run-dir` on the three parsers; each of `_cost`, `_run`, `_verify` passes `a.run_dir` as the second argument; in `main`, right after `parse_args`, when `getattr(args, "run_dir", None)` is not None: `args.run_dir = args.run_dir.absolute()`, made, `E_RUN_DIR` (`from None`) when the `mkdir` raises an `OSError`, and `E_RUN_DIR` with reason "already holds a run" when `args.run_dir / "events.jsonl"` exists.
  - `pipeline.py`: the signatures of Interfaces; `cost` uses `run_dir = run_dir or runs.run_dir_for(path.absolute().parent.name)` where it picks its folder today (L333); `run` and `verify` end in `_locked(path, _run, run_dir)` and `_locked(path, _verify, run_dir)`.
  - `runs.py`: `lock_file`, `lock_holder` and `_unlink` as Interfaces say, `lock_holder` with `# ponytail: a lock left empty by a hard kill between its creation and its write reads live until deleted; E_LOCKED's advice covers it` and `_unlink` with `# ponytail: Windows refuses to delete a file another process has open (the GUI reads the lock every 500 ms); 1 s of retries, then the error`. In `project_lock`, `lock = lock_file(project_path)`; on `FileExistsError`, `holder = lock_holder(project_path)`; `continue` when it is None; `time.sleep(0.05)` and `continue` while its `pid` is None, 20 times at most; `E_LOCKED` when `holder["alive"]`; else `W_STALE_LOCK` and `_unlink(lock)`, as today; the `finally` calls `_unlink(lock)`.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.** `.venv/Scripts/python -m pytest -q` passes. Then:

```bash
git add src/kicad_rf_studio/__main__.py src/kicad_rf_studio/cli.py src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/runs.py src/kicad_rf_studio/core/messages.py tests/test_run_dir.py tests/test_runs.py tests/test_verify.py
git commit -m "feat: python -m kicad_rf_studio, --run-dir on cost, run and verify, and runs.lock_holder (Stage 2 design 5.2 items 1, 2, 6)"
graphify update .
```

---

### Task 2 [code]: The end event, cost's lines as events, the calibration under the caller's STOP

**Files:**
- Modify: `src/kicad_rf_studio/cli.py` (`main`); `src/kicad_rf_studio/runs.py` (`emit` L188–195, `calibrate` L340–373, `ensure_calibrated` L376–378); `src/kicad_rf_studio/pipeline.py` (`prepare` L222–238, `readout_2d` L268–282, `cost` L310–343, `simulate`'s `prepare` call L564); `src/kicad_rf_studio/core/messages.py` (`I_END` after `I_CALIBRATED` L94; `detail()` after `reason()` L210–213); the Stage 1 spec (Status line L4, §3.2 after L118, §3.3's events bullet L141, §6.1's step 5 L365).
- Test: `tests/test_run_dir.py`; `tests/test_run.py` (L87, L359–361) and `tests/test_verify.py` (L140), whose event lists gain the end event.

**Interfaces:**
- Consumes: Task 1's `--run-dir`, `runs.lock_file`, `runs.lock_holder`, `_locked(path, body, run_dir)`.
- Produces:
  - `runs.emit(run_dir: Path | None, kind: str, code: str, params: dict, job: int | None = None, *, show: bool = True) -> None`: writes the event when `run_dir` is not None, prints its line when `show`; `kind` is progress, verdict, cost, result, message or end.
  - The end event, written last by `cli.main` in a `finally` whenever the command's run folder exists by then: `{"t", "kind": "end", "job": None, "code": "I_END", "params": {"exit_code": int, "command": "cost" | "run" | "verify", "project": str}}`, `project` being `str(pipeline.project_path(args.project).resolve())`. The folder is the `--run-dir` one (Task 1 made it) or, without the flag, the one `cli.main` picks with `runs.run_dir_for(path.absolute().parent.name)` and passes on as the command's `run_dir`, which run and verify make under the lock and cost at its calibration or setup gate, as they make theirs today; a refusal before that leaves no folder and no event. Before it, for an exception `main` catches, a `message` event: `(e.code, e.params)` for a KrsError, `("E_INTERNAL", {"detail": detail(e)})` for any other. Both are `show=False` and never raise (`contextlib.suppress(OSError)`).
  - `messages.detail(error: Exception) -> str`: E_INTERNAL's detail, `" ".join(f"{type(error).__name__}: {error}".split())` cut to 200 characters with "…" (cli.main's L236–237, moved; `main` uses it).
  - `pipeline.readout_2d(geom: Geometry) -> list[tuple[str, dict]]`: `I_2D_HEADER` (or `W_NO_SECTIONS`), then `I_2D_SECTION` or `W_2D_SHORT` per section; it prints nothing.
  - `pipeline.cost(path, run_dir=None)`: a `run_dir` that exists at its start (cli.main made it for `--run-dir`) gets every line as an event from the first: `message` for W_FILLS_AS_SAVED, load()'s notes, prepare's warnings and W_NO_PORTS; `cost` for the readout; `verdict` (job None) for the mesh gates; then the setup gate's and the cost lines' events as today. Otherwise those first lines are printed only, as before. Its folder is picked before `prepare`, which calibrates inside it.
  - `pipeline.prepare(model, emit, run_dir: Path | None = None)` passes `run_dir` to `runs.ensure_calibrated`; `simulate` passes its own.
  - `runs.calibrate(settings: dict, run_dir: Path | None = None) -> dict` and `runs.ensure_calibrated(settings: dict, run_dir: Path | None = None) -> dict`: with a `run_dir`, the calibration's model and jobs go in `run_dir / "calibrate"`, `run_jobs` polls `run_dir` for STOP, and I_CALIBRATING and I_CALIBRATED are message events in `run_dir`; without one, a `calibrate-*` folder of its own and printed lines, as today.
  - CATALOG `"I_END": "The command ended with exit code {exit_code}."`

- [ ] **Step 1: Write the failing tests,** at the end of `tests/test_run_dir.py`:

```python
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
```

  Then the lists that now end with the end event (a run typed without `--run-dir` ends its folder too, A-13): in `tests/test_run.py`, L87's set becomes `{"message", "verdict", "cost", "progress", "result", "end"}` and L361's list ends `*LIMITS, "I_END"]`; in `tests/test_verify.py`, L140 compares with `[*codes, "I_END"]`.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_run_dir.py tests/test_run.py tests/test_verify.py -q`. Expected: the five new tests and the three changed assertions FAIL (no `end` event; the readout printed, not written; the calibration in a `calibrate-*` folder of its own and not stopped).
- [ ] **Step 3: Implement** the Interfaces above.
  - `cli.main`: `run_dir = command = project = None` and `code = 1` before the `try`. After Task 1's `--run-dir` check, for the three commands (`hasattr(args, "run_dir")`): `path = project_path(args.project)` (imported from `pipeline` there: the three commands load it anyway), `command, project = args.command, str(path.resolve())`, `args.run_dir = args.run_dir or runs.run_dir_for(path.absolute().parent.name)` (not made: the command makes it, as before), and only then `run_dir = args.run_dir`, so that an E_RUN_DIR leaves it None. Then `code = args.func(args) or 0`; each `except` sets `code` (2, 130, 1) and prints as today, KrsError and Exception also writing the message event; the `finally` writes the end event; `return code` after the `try` statement. A small `_event(run_dir, kind, code, params)` holds the `show=False` call under `contextlib.suppress(OSError)`, and does nothing unless `run_dir` is not None and is a folder by then.
  - `runs.emit`: the file write under `if run_dir is not None:`, the print under `if show:`.
  - `pipeline.cost`: `run_dir = run_dir or runs.run_dir_for(path.absolute().parent.name)` moves to its top; `say = partial(runs.emit, run_dir if run_dir.is_dir() else None)`, with `# ponytail: a folder made first (--run-dir) gets every line; a terminal cost prints its first lines only, so the GUI's replay of it starts at its calibration or setup gate`; W_FILLS_AS_SAVED, `readout_2d(geom)`'s lines (kind `cost`), the notes, W_NO_PORTS and `model.blocked` (kind `verdict`) go through `say`; then `prepare(model, partial(say, "message"), run_dir)`.
  - `runs.calibrate`: `folder = run_dir / "calibrate" if run_dir else run_dir_for("calibrate")`; `write_spec(folder, spec)` first (it makes `run_dir` too); the two lines through `partial(emit, run_dir, "message")`, which prints only when `run_dir` is None; jobs in `folder`; `run_jobs(jobs, k, run_dir or folder, settings)`.
- [ ] **Step 4: Amend the Stage 1 spec (A-13, A-14).**
  - §3.3, replace the `events.jsonl` bullet with: "- **`events.jsonl`.** One JSON object per line: `{"t", "kind": progress|verdict|cost|result|message|end, "job", "code", "params"}`. The events carry message codes, never text, so they stay language-neutral and are translated only when displayed. A `cost`, `run` or `verify` that has a run folder by its end, the one given with `--run-dir` (§3.2) or one it made, ends it with an `end` event however it ends, short of a hard kill: code `I_END`, with `exit_code`, `command` and `project` (the project file's resolved path), after a `message` event for any refusal or internal error it printed on stderr. So a refusal before the lock and a stop during setup leave a trace in a given folder, and a restarted GUI finds a project's last cost and runs. (A-13, Stage 2 plan 1: controller recommendation, owner unavailable.)"
  - §6.1, step 5 becomes: "5. Every event goes to `events.jsonl`, and stdout gets the same events as translated, readable lines, except the end event, which is never printed, and the `message` event of a refusal or internal error that the command line caught, whose line goes to stderr (§3.3). (A-13, Stage 2 plan 1: controller recommendation, owner unavailable.)"
  - §3.2, after the "**Stage 1 never prompts.**" paragraph, add: "**Run folders given by the caller.** `cost`, `run` and `verify` take `--run-dir DIR`: the run folder to use instead of a new one in the data folder, made at the start (a relative DIR is read from the working folder; one that cannot be made or already holds a run is refused). With it, `cost` writes every line as an event there from its first. The first-use calibration runs inside the command's run folder, in `calibrate/`, and that folder's `STOP` stops it. Stage 2's GUI starts these commands detached, with a new folder each time. (A-14, Stage 2 plan 1: controller recommendation, owner unavailable.)"
  - Status line, append: "On 2026-10-27, Stage 2's plan 1 amended §3.2, §3.3 and §6.1 (A-13, A-14) the same way."
- [ ] **Step 5: Run them again.** `.venv/Scripts/python -m pytest tests/test_run_dir.py tests/test_cli_cost.py tests/test_calibrate.py tests/test_run.py tests/test_verify.py -q`. Expected: PASS (the CLI's printed output is unchanged).
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/cli.py src/kicad_rf_studio/runs.py src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/core/messages.py tests/test_run_dir.py tests/test_run.py tests/test_verify.py docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "feat: the end event in every run folder, cost's lines as events and the calibration under the caller's STOP; spec A-13, A-14 (Stage 2 design 5.2 items 3, 4, 9; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 3 [code]: `cli.new()` returns its notes, and `snap()`

**Files:**
- Modify: `src/kicad_rf_studio/cli.py` (`_new` L66–141: its body becomes the public `new`, and `_new` prints what it returns; `_list`, `_part_note` and `_reference` stay, tools/p0c.py importing `_reference`); `src/kicad_rf_studio/core/kicad/values.py` (end of file).
- Test: `tests/test_cli_new.py` (the new test), `tests/test_values.py` (import L6, the new test).

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `cli.new(board: str | Path, start: str, end: str, f0: float, *, harmonics: int = HARMONICS, preset: str = DEFAULT_PRESET, stackup: str | None = None, lid_height: float | None = None, output: str | Path | None = None) -> tuple[Path, list[tuple[str, dict]]]`: `_new`'s body, the same files, refusals and order, returning project.json's path and the notes `new` prints, `("I_WROTE", {"path": target})` last; it prints nothing. `_new(a)` prints the notes `new(...)` returns. Plan 2's New calls it on a worker thread: cli imports neither Qt nor kicad-python (design §4).
  - `values.E12 = (1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2)` and `values.E24 = (1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1)` (IEC 60063).
  - `values.snap(value: float, series: str) -> float`, for `value > 0` and series `"E12"` or `"E24"`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_values.py` (import `E12, E24, snap` beside the module's other names):

```python
@pytest.mark.parametrize(("value", "series", "snapped"), [
    (4.7e-12, "E12", 4.7e-12), (5.0e-9, "E12", 4.7e-9), (5.0e-9, "E24", 5.1e-9), (9.6e-12, "E12", 10e-12),
    (1.049e-9, "E24", 1.1e-9),  # log space: 1.049 lies past √1.1 = 1.0488, though nearer 1.0 in a straight line
    (1.04e-9, "E24", 1.0e-9), (33.3, "E24", 33.0), (0.0912, "E24", 0.091)])
def test_snap_takes_the_nearest_iec_60063_value_in_log_space(value, series, snapped):  # design 5.2 item 8
    assert snap(value, series) == snapped
    assert (len(E12), len(E24)) == (12, 24) and set(E12) <= set(E24)
```

  At the end of `tests/test_cli_new.py`:

```python
def test_new_returns_the_notes_it_prints(tmp_path, capsys):  # design 5.2 item 5
    path, notes = cli.new(LPF, "U1.1", "J1.1", 915e6, lid_height=2.5, output=tmp_path / "a")
    assert path == tmp_path / "a" / "project.json" and path.is_file() and notes[-1] == ("I_WROTE", {"path": path})
    code, pj = run_new(tmp_path, "--lid-height", "2.5", out=tmp_path / "b")
    assert code == 0 and capsys.readouterr().out.splitlines() == [
        *(render(c, **p) for c, p in notes[:-1]), render("I_WROTE", path=pj)]
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_values.py tests/test_cli_new.py -q`. Expected: FAIL — `ImportError: cannot import name 'E12'` at test_values' collection, `AttributeError: module 'kicad_rf_studio.cli' has no attribute 'new'`.
- [ ] **Step 3: Implement.**
  - `cli.new`: `_new`'s body from `load_board(a.board)` to the notes, each `a.<name>` its parameter, `return target, notes` in place of the print loop; its imports stay where they are, so test_cli_new's monkeypatches on `cli` keep reaching them. `_new(a)` calls `new(a.board, a.start, a.end, a.f0, harmonics=a.harmonics, preset=a.preset, stackup=a.stackup, lid_height=a.lid_height, output=a.output)` and prints each note with `render`.
  - `snap`, at the end of values.py with E12 and E24, its docstring "The `series` value ("E12" or "E24", IEC 60063) nearest to `value` (> 0) in log space, as the decimal it is written as; a tie goes to the lower (Stage 2 design 5.2 item 8)." Its rule, which the tests pin: candidates `float(f"{m}e{e}")` for each m of the series and e from `math.floor(math.log10(value)) - 1` to `+ 1` (decimals, so 4.7e-12 comes back exactly as typed, never 4.7 × 1e-12; three decades, so no edge at a power of ten), the nearest by `abs(math.log(c / value))`, a tie to the lower (`min` keyed on that and `c`).
- [ ] **Step 4: Run them again.** `.venv/Scripts/python -m pytest tests/test_values.py tests/test_cli_new.py -q`. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/cli.py src/kicad_rf_studio/core/kicad/values.py tests/test_cli_new.py tests/test_values.py
git commit -m "feat: cli.new returns its notes, and snap to IEC 60063's E12 and E24 (Stage 2 design 5.2 items 5, 8)"
graphify update .
```

---

### Task 4 [code]: `chain_results` and `draw_summary`, the outputs byte-identical

**Files:**
- Modify: `src/kicad_rf_studio/core/post/outputs.py` (`summary_png` L138–164); `src/kicad_rf_studio/pipeline.py` (`write_outputs` L409–471).
- Test: `tests/test_post_outputs.py` (import L17–18, new test), `tests/test_run.py` (outputs import L21; `star_project` in place of the setup of `test_three_external_ports_and_a_part_port_get_the_label_after_w_not_two_port`, L441–449; the new test).

**Interfaces:**
- Consumes: `layout`, `_split`, `part_impedances`, `loads`, `terminate`, `ideal_schematic`, `loss_budget`, `marker_lines`, `indicator_lines`, `gate_lines`, `RETUNE_VALIDATED`.
- Produces:
  - `pipeline.ChainResults`, a dataclass: `lay: Layout`, `ext: list[int]`, `refs: list[str]`, `chain: np.ndarray | None` (None after a part's refusal), `ideal: np.ndarray | None`, `p_layout: np.ndarray | None` (both only with 2 external ports; `ideal` only with part ports), `what_if: bool` (closed part ports while `RETUNE_VALIDATED` is False), `lines: list[tuple[str, dict]]` (I_BASIS up to W_NOT_TWO_PORT; no I_WHAT_IF, I_OUTPUTS or LIMITS).
  - `pipeline.chain_results(path: Path, project: dict, *, errors_as_lines: bool = False) -> ChainResults`: write_outputs' numbers and lines, no file written; a part's refusal is raised, or with `errors_as_lines` a line with `chain` None. Raises layout's refusals and E_S_SINGULAR.
  - `write_outputs(path, project, command, *, errors_as_lines=False)`: unchanged signature and output, now `chain_results` plus the files: it renders I_WHAT_IF with `verify`'s command for the label, appends `("I_WHAT_IF", ...)` after the lines when `what_if`, then I_OUTPUTS (or E_RESULTS_WRITE) and LIMITS.
  - `outputs.draw_summary(fig, lay: Layout, chain: np.ndarray, ideal: np.ndarray | None, name: str, label: str | None = None) -> tuple`: summary_png's drawing on any matplotlib `Figure` (an Agg one for the PNG, the GUI canvas's), returning its axes `(S21, S11, Smith)`. `summary_png` = `Figure(figsize=(15, 4.5), layout="constrained")`, `draw_summary`, `savefig(png, dpi=100)`.

- [ ] **Step 0: Record the PNG's digest before any edit.**

```bash
.venv/Scripts/python -B -c "import sys, hashlib; sys.path[:0] = ['tests', 'tools']; from test_post_outputs import lay_of, EXT, F; from test_post_chain import PI, PI_Z; from kicad_rf_studio.core.post.chain import ideal_schematic; from kicad_rf_studio.core.post.outputs import summary_png; c = ideal_schematic(PI, PI_Z, F); print(hashlib.sha256(summary_png(lay_of(EXT, c), c, c, 'lpf915', 'L')).hexdigest())"
```

  Expected on today's dev venv (matplotlib 3.11.2): `d0c52580a7c63fe272a056ebcd2f78aafdff176e270b1f75847523c378144f78`. Note whatever it prints; Step 5 must print the same.
- [ ] **Step 1: Write the failing tests.** In `tests/test_post_outputs.py` (import `draw_summary`):

```python
def test_the_png_is_draw_summary_on_an_agg_figure_at_100_dpi():  # Stage 2 design 5.2 item 7
    chain = ideal_schematic(PI, PI_Z, F)
    fig = Figure(figsize=(15, 4.5), layout="constrained")
    ax21, ax11, smith = draw_summary(fig, lay_of(EXT, chain), chain, chain, "lpf915", "L")
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=100)
    assert summary_png(lay_of(EXT, chain), chain, chain, "lpf915", "L") == out.getvalue()
    assert [len(ax.lines) for ax in (ax21, ax11)] == [5, 5]  # layout, ideal and the three marker lines
    assert fig.get_suptitle() == render("I_PLOT_TITLE", name="lpf915") + "\nL" and smith in fig.axes
```

  In `tests/test_run.py` (import `summary_csv, summary_png` with `COLUMNS, LIMITS`), add `star_project` and replace L441–449 of `test_three_external_ports_and_a_part_port_get_the_label_after_w_not_two_port` with `pj, project = star_project(tmp_path, 3)`; then add the new test:

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_outputs.py tests/test_run.py -q`. Expected: FAIL — `ImportError: cannot import name 'draw_summary'`; `AttributeError: ... 'chain_results'`.
- [ ] **Step 3: Implement.**
  - `draw_summary` is `summary_png`'s body from `fig.subplots(1, 3)` to `fig.suptitle(...)`, moved, plus `return ax21, ax11, ax_smith`; matplotlib stays imported inside `summary_png` only.
  - `chain_results` is `write_outputs`' body from `results = project["results"]` (L422) to the end of its `else` branch (L462), moved, with these changes only: the layout Touchstone, `files`, the label's `render` and the `("I_WHAT_IF", ...)` line stay in `write_outputs`; `chain = ideal = p_layout = None` before the `try`; `len(ext)` stands for `p`; it returns `ChainResults(lay, ext, refs, chain, ideal, p_layout, chain is not None and bool(refs) and not RETUNE_VALIDATED, lines)`.
  - `write_outputs` keeps its signature and docstring: `res = chain_results(...)`, then `files` in today's order (layout, chain, summary.csv, summary.png), `label = render("I_WHAT_IF", **what_if) if res.what_if else None`, the I_WHAT_IF line after `res.lines`, and the writing, I_OUTPUTS and LIMITS as today.
- [ ] **Step 4: Run them again.** `.venv/Scripts/python -m pytest tests/test_post_outputs.py tests/test_run.py tests/test_retune.py tests/test_verify.py -q`. Expected: PASS.
- [ ] **Step 5: The digest again.** Step 0's command prints the same digest.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/post/outputs.py src/kicad_rf_studio/pipeline.py tests/test_post_outputs.py tests/test_run.py
git commit -m "refactor: chain_results and draw_summary split out of the outputs, the files byte-identical (Stage 2 design 5.2 item 7)"
graphify update .
```

---

### Task 5 [code]: PySide6-Essentials, the GUI entry point and the import rules

**Files:**
- Create: `src/kicad_rf_studio/gui/__init__.py`, `tests/test_gui.py`.
- Modify: `pyproject.toml` (L12; a table after L18); `tests/conftest.py` (top, and a fixture); `.github/workflows/ci.yml` (a step before L28); `src/kicad_rf_studio/core/messages.py` (`G_APP` after `E_INTERNAL`, L189); the Stage 1 spec (§3.4's dependencies bullet L146, the Status line).
- Test: `tests/test_gui.py`.

**Interfaces:**
- Consumes: `runs.data_dir`.
- Produces:
  - `dependencies` gains `"PySide6-Essentials>=6.10.1,<7"`; `[project.gui-scripts] kicad-rf-studio-gui = "kicad_rf_studio.gui:main"`.
  - `kicad_rf_studio.gui.main(argv: list[str] | None = None) -> int`: when `sys.stderr` is None (pythonw: the gui-scripts entry on Windows has no console, r3 R-2) it first points `sys.stderr` at `runs.data_dir() / "gui.log"`, opened for append in UTF-8 after making the folder, so a slot's traceback lands there; then it imports Qt inside itself, takes `QApplication.instance() or QApplication(sys.argv[:1])`, shows a `QMainWindow` titled `render("G_APP")` and returns `app.exec()`. Task 7 puts the main window in its place.
  - `tests/conftest.py`: `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` right after its imports, before any QApplication; a session fixture `qapp` returning `QApplication.instance() or QApplication([])`, PySide6 imported inside it.
  - `tests/test_gui.py`: `ROOT`, `QT_FREE` (the modules that load no Qt, kicad-python or matplotlib, which Task 6 extends).
  - CATALOG `"G_APP": "kicad-rf-studio"`.

- [ ] **Step 1: Write the failing tests.** `tests/test_gui.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI (Stage 2 design 5): its dependency and entry point, the import rules, and the main window offscreen on
the fake CLI."""
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from PySide6.QtCore import QTimer

from kicad_rf_studio import gui
from kicad_rf_studio.core.messages import render

ROOT = Path(__file__).resolve().parents[1]
QT_FREE = ("kicad_rf_studio.cli", "kicad_rf_studio.worker", "kicad_rf_studio.pipeline", "kicad_rf_studio.runs",
           "kicad_rf_studio.gui")


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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui.py -q`. Expected: FAIL — `ModuleNotFoundError: No module named 'PySide6'` at collection.
- [ ] **Step 3: The dependency and the entry point.** Edit `pyproject.toml` as Interfaces say, then `.venv/Scripts/python -m pip install -e .[dev]`. Expected: `.venv/Scripts/python -c "import PySide6; print(PySide6.__version__)"` prints 6.10.1 or later (6.12.0 on 2026-10-27). Run Step 2's command again: `ModuleNotFoundError: No module named 'kicad_rf_studio.gui'`.
- [ ] **Step 4: Implement** `gui/__init__.py` (a docstring naming the package's two modules, control and window, and the rule that `import kicad_rf_studio.gui` loads no Qt or matplotlib), the conftest lines, `G_APP`.
- [ ] **Step 5: CI and the spec.**
  - `ci.yml`, tier-a, before `pip install`: `- if: runner.os == 'Linux'` with `run: sudo apt-get update && sudo apt-get install -y --no-install-recommends libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3` and the comment `# Qt's offscreen platform still loads these (Stage 2 plan 1); unverified until the first push`.
  - Stage 1 spec §3.4, the dependencies bullet becomes: "- **Dependencies:** numpy, scipy, h5py, matplotlib, shapely and scikit-rf. Stage 2 adds `PySide6-Essentials>=6.10.1,<7` (6.10.1 is the first with Python 3.14 wheels; Essentials only, so no QtCharts or Addons) and kicad-python, as core dependencies with no extra; kicad-python's pin lands with the button (Stage 2 plan 3). (A-15, Stage 2 plan 1: controller recommendation, owner unavailable.)" The Status sentence of Task 2 becomes "amended §3.2, §3.3, §3.4 and §6.1 (A-13 to A-15)".
- [ ] **Step 6: Run them again.** `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_repo.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add pyproject.toml src/kicad_rf_studio/gui/__init__.py src/kicad_rf_studio/core/messages.py tests/conftest.py tests/test_gui.py .github/workflows/ci.yml docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "feat: PySide6-Essentials, the kicad-rf-studio-gui entry and the import rules; spec A-15 (Stage 2 design 4, 5.6, 5.8; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 6 [code]: The Qt-free launcher, tail and re-attach

**Files:**
- Create: `src/kicad_rf_studio/gui/control.py`, `tests/fake_cli.py`, `tests/test_gui_control.py`.
- Modify: `src/kicad_rf_studio/core/messages.py` (the codes below, after `G_APP`); `tests/conftest.py` (`fake` applies `fake_cli.patches`; `FAKE` goes); `tests/test_gui.py` (`QT_FREE` gains `"kicad_rf_studio.gui.control"`).
- Test: `tests/test_gui_control.py`, `tests/test_gui.py`.

**Interfaces:**
- Consumes: Tasks 1–4 (`--run-dir`, the end event, `runs.lock_holder`, `pipeline.chain_results`, `messages.detail`); `runs.data_dir`, `runs.ascii_name`, `spec.spec_hash`.
- Produces, in `kicad_rf_studio.gui.control` (no Qt, no matplotlib):
  - `orchestrator() -> list[str]`: `[python, "-X", "utf8", "-I", "-m", "kicad_rf_studio"]`, python being `python.exe` beside `sys.executable` when that is `pythonw.exe` (any case), else `sys.executable`.
  - `start(prefix: list[str], command: str, project: Path, run_dir: Path) -> subprocess.Popen`: runs `[*prefix, command, str(project), "--run-dir", str(run_dir)]` through `subprocess.Popen`, detached, in `run_dir` (made, and its `cwd`: the orchestrator holds no other folder for hours); stdin `DEVNULL`; stdout to `run_dir / "cli.log"` (opened `"wb"`, closed after `Popen`), stderr `STDOUT`; the environment without `KICAD_API_SOCKET` and `KICAD_API_TOKEN`. Windows: `creationflags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB`, retried once without the breakaway on `PermissionError` (a job that forbids it), with `# ponytail: without breakaway, a job that kills its processes on close still takes the run with it; plan 3 checks KiCad's job`. Elsewhere `start_new_session=True`.
  - `class Tail(path: Path)` with `offset: int = 0` and `read(limit: int = 1 << 20) -> list[dict]`: the complete lines from `offset`, at most `limit` bytes read, cut after the last `b"\n"`; each `json.loads`, a line that does not parse skipped; no file yet: `[]`. `# ponytail: a line longer than limit is never read; events are under 1 KB`.
  - `latest(events: list[dict]) -> list[dict]`: `events` in order without the `progress` events that a later one of the same job replaces (r2 §1: a replay of an 8 h run is about 40k lines).
  - `last_event(run_dir: Path) -> dict | None`: the last complete line of `run_dir/events.jsonl`, read from its last 64 KiB; None without a file or a parsable line, or on an `OSError`. `# ponytail: the last 64 KiB only; a longer last line reads as none`.
  - `ended(project: Path) -> list[tuple[Path, dict]]`: the folders `runs.data_dir() / "runs" / f"{ascii_name(project.parent.name)}-*"` whose last event is an `end` naming `str(project)`, newest first by the event's `t`, a folder it cannot read skipped. `# ponytail: scans every run folder of the project on each read (C-23 keeps them all); an index of run folders if it grows slow`.
  - `last_cost(project: Path, spec_hash: str | None) -> Path | None`: the first of `ended(project)` whose command is `cost`, exit code 0, and whose `model.json` has `spec_hash` (unreadable: no match; `spec_hash` None: None).
  - `Opened`, a dataclass: `project: dict | None`, `spec_hash: str | None`, `results: pipeline.ChainResults | None`, `problem: tuple[str, dict] | None`, `cost: Path | None`, `last: Path | None`.
  - `open_project(path: Path) -> Opened` (the caller passes the resolved project file): `pipeline.load`, `build_model`, `spec_hash` (None without a spec), `results_of`, `chain_results(path, project, errors_as_lines=True)`; the first KrsError is `problem` from there on, any other exception `("E_INTERNAL", {"detail": detail(e)})`; `cost = last_cost(path, spec_hash)`; `last` = the newest of `ended(path)` whose command is run or verify. Never raises; starts nothing.
  - `END = {0: "G_END_DONE", 2: "G_END_REFUSED", 3: "G_END_BLOCKED", 4: "G_END_NOT_KEPT", 130: "G_END_STOPPED"}`.
  - `run_state(run_dir: Path, end: dict | None, holder: dict | None, own: bool, returncode: int | None) -> tuple[str, dict]`, `own` being whether this window started the process and `returncode` its exit code (None while it runs), params always `{"folder": str(run_dir), "exit_code": <the end's, else returncode>, "log": str(run_dir / "cli.log")}`: with an end event, `END.get(exit_code, "G_END_FAILED")`; else, for a process this window started, `G_RUNNING` while it runs and `G_END_EXITED` after; for one it did not start, `G_RUNNING` while a live lock names `run_dir` (compared as Paths), `G_END_LOST` while a dead one does, else `G_ENDED`.
  - `GUI = {"E_LOCKED": "G_LOCKED", "I_RUN_START": "G_RUN_START", "I_WHAT_IF": "G_WHAT_IF", "E_NO_RESULTS": "G_NO_RESULTS", "E_RESULTS_STALE": "G_RESULTS_STALE"}` and `text(code: str, params: dict) -> str` = `render(GUI.get(code, code), **params)`.
  - `tests/fake_cli.py` with `patches(data: Path) -> dict`; in `tests/test_gui_control.py`, `FAKE_CLI`, `FAKE_PREFIX = [sys.executable, "-X", "utf8", "-I", str(FAKE_CLI)]` and `until(check, timeout=60.0)`.
  - CATALOG (exact texts):
    - `"G_RUNNING": "Running in {folder}…"`
    - `"G_END_DONE": "Finished (exit code {exit_code})."`
    - `"G_END_REFUSED": "Refused (exit code {exit_code}): the message above says why and what to do."`
    - `"G_END_BLOCKED": "A gate blocked it (exit code {exit_code}): the verdicts above say which and what to change."`
    - `"G_END_NOT_KEPT": "Not every job kept S (exit code {exit_code}), so the previous results stay; the verdicts above say why."`
    - `"G_END_STOPPED": "Stopped (exit code {exit_code})."`
    - `"G_END_FAILED": "Failed (exit code {exit_code}): the message above says what happened. Please report it."`
    - `"G_END_EXITED": "The process in {folder} exited with code {exit_code} without recording how it ended: it was killed, or it failed at its start ({log} says why). Start it again; the next run reclaims any lock it left."`
    - `"G_END_LOST": "The process of {folder} ended without recording how (it was killed, or the PC restarted). Start it again; the next run reclaims any lock it left."`
    - `"G_ENDED": "The run in {folder}, started from another window or a terminal, has ended. Its verdicts are above, and the results it kept show in Results."`
    - `"G_LOCKED": "A run of this project, started at {started} from another window or a terminal, is going on in {run}. Stop stops it. If no run is going on (its process was killed and its number reused), delete {lock}."`
    - `"G_RUN_START": "Running {runs} jobs, {pool} at once, in {folder}. Stop stops them."`
    - `"G_WHAT_IF": "Relative / what-if: the instant retune is not yet validated against a full simulation of a real board (spec 7.6), so read these chain results as relative. Check the final values with Verify."`
    - `"G_NO_RESULTS": "No results yet: estimate the cost, then run."`
    - `"G_RESULTS_STALE": "The model changed since the last run (a board re-saved in KiCad can change it too), or that run is older than this version, so its results no longer apply. Estimate the cost and run again."`

- [ ] **Step 1: The test-only CLI entry and its one table of patches.** `tests/fake_cli.py`, given whole:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""The test-only CLI entry (Stage 2 design 5.8): `python -X utf8 -I tests/fake_cli.py COMMAND ...` applies the fake's
patches of runs (patches(), which tests/conftest.py's `fake` applies too), with $KRS_FAKE_DATA as the data folder,
then runs cli.main, so a detached orchestrator started by the GUI's code runs tests/fake_worker.py."""
import os
import sys
from pathlib import Path

from kicad_rf_studio import cli, runs


def patches(data: Path) -> dict:
    """The fake's patches of runs: tests/fake_worker.py as the worker, fast polls, `data` as the data folder and an
    openEMS check that passes."""
    return {"WORKER": ("-I", "-u", str(Path(__file__).with_name("fake_worker.py"))), "POLL_S": 0.02,
            "ABORT_WAIT_S": 5.0, "data_dir": lambda: data, "check_openems": lambda: []}


if __name__ == "__main__":
    for name, value in patches(Path(os.environ["KRS_FAKE_DATA"])).items():
        setattr(runs, name, value)
    sys.exit(cli.main())
```

  In `tests/conftest.py`, `FAKE` goes and `fake` becomes (with `from fake_cli import patches`):

```python
@pytest.fixture
def fake(tmp_path, monkeypatch):
    """Workers are tests/fake_worker.py (KRS_FAKE* pick its behaviour), the data folder is under tmp_path, polls are
    fast and the version check passes: fake_cli.patches, which a detached tests/fake_cli.py applies too. Returns the
    data folder."""
    for name, value in patches(tmp_path / "data").items():
        monkeypatch.setattr(runs, name, value)
    return tmp_path / "data"
```

- [ ] **Step 2: Write the failing tests,** `tests/test_gui_control.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI's Qt-free logic (Stage 2 design 5.1, 5.8): the detached start, the events tail, re-attach through the lock
and the end events, and the project read off the GUI thread. Detached runs go through tests/fake_cli.py."""
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.project import load_project, save_project
from kicad_rf_studio.gui import control
from test_cli_cost import new_project

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
    assert control.open_project(tmp_path / "nope.json").problem[0] == "E_PROJECT_UNREADABLE"
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
```

  In `tests/test_gui.py`, `QT_FREE` gains `"kicad_rf_studio.gui.control"`.
- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q`. Expected: FAIL — `ImportError: cannot import name 'control' from 'kicad_rf_studio.gui'`.
- [ ] **Step 4: Implement** `control.py` (the SPDX line; a docstring: "The GUI's Qt-free logic (Stage 2 design 5.1): the detached start, the events tail, re-attach through the lock and the end events, and the project read off the GUI thread. Never imports Qt or matplotlib.") and the catalog codes, as Interfaces say.
- [ ] **Step 5: Run them again.** Same command. Expected: PASS (the POSIX `start` test skipped on Windows, the Windows one elsewhere).
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/core/messages.py tests/conftest.py tests/fake_cli.py tests/test_gui_control.py tests/test_gui.py
git commit -m "feat(gui): the Qt-free launcher, tail and re-attach, tested on a detached fake CLI (Stage 2 design 5.1, 5.8)"
graphify update .
```

---

### Task 7 [code]: The main window on its own process — open, cost, run and stop

**Files:**
- Create: `src/kicad_rf_studio/gui/window.py`.
- Modify: `src/kicad_rf_studio/gui/__init__.py` (`main` opens the main window); `src/kicad_rf_studio/core/messages.py` (the codes below); `tests/test_gui.py`.
- Test: `tests/test_gui.py`.

**Interfaces:**
- Consumes: Task 6's `control` (`orchestrator`, `start`, `Tail`, `latest`, `Opened`, `open_project`, `run_state`, `text`), `runs.run_dir_for`, `pipeline.project_path`, `messages.detail`, `messages.reason`; in tests, conftest's `qapp` and `calibrated`, test_gui_control's `FAKE_PREFIX` and `until`, test_cli_cost's `new_project` and `fail`.
- Produces: `kicad_rf_studio.gui.window.MainWindow(prefix: list[str] | None = None)`, a `QMainWindow` titled `G_APP`, 1200 × 800, `self.prefix = prefix or control.orchestrator()` as the command that starts the orchestrator.
  - Tabs `tabs: QTabWidget` in the CLI's order: Project (`open_button`, `project_status: QLabel`), Cost (`cost_lines: QListWidget`, `cost_status: QLabel`, `cost_button`, `run_button`), Run (`banner: QLabel`, hidden, `jobs: QTableWidget` of 5 columns G_COL_PORT, G_COL_TIME, G_COL_RESIDUAL, G_COL_SPEED, G_COL_VERDICT, `log: QListWidget`, `run_status: QLabel`, `stop_button`). Cost, Run… and Stop start disabled: there is no project yet. Task 9 adds Results.
  - The state tests read: `path: Path | None` (the resolved project file), `opened: control.Opened | None`, `loading: Future | None`, `cost: Path | None` (the cost Run… confirms on), `command: str | None` and `run_dir: Path | None` (the watch), `proc: subprocess.Popen | None` (only what this window started), `pool: ThreadPoolExecutor(1)`, `timer: QTimer` (500 ms on `tick`, started in `__init__`).
  - `browse()` (QFileDialog.getOpenFileName with G_OPEN and G_OPEN_FILTER), `open_project(path: Path)`, `load()`, `start(command: str)`, `run()`, `ask(text: str) -> bool`, `stop()`, `watch(command: str, run_dir: Path, proc: subprocess.Popen | None = None)`, `show_project(opened: control.Opened)`, `show_event(event: dict)`, `tick()`.
  - `gui.main(argv=None)`: `argv = sys.argv[1:] if argv is None else argv` (the gui-scripts entry passes none); builds `MainWindow()`, opens `Path(argv[0])` when given (a project.json or its folder), shows it and runs the app.
  - CATALOG (exact texts): `"G_TAB_PROJECT": "Project"`, `"G_TAB_COST": "Cost"`, `"G_TAB_RUN": "Run"`, `"G_OPEN": "Open a project…"`, `"G_OPEN_FILTER": "Projects (*.json)"`, `"G_COST": "Estimate the cost"`, `"G_RUN": "Run…"`, `"G_STOP": "Stop"`, `"G_LOADING": "Reading the project and building its model…"`, `"G_PROJECT": "{path}: f0 {f0_mhz} MHz, {harmonics} harmonics, preset {preset}."`, `"G_NO_COST": "No cost of this model yet: estimate it, then Run… asks to start the run."`, `"G_COST_REUSED": "The cost in {folder} matches this model: Run… asks to start the run."`, `"G_CONFIRM_TITLE": "Start the run?"`, `"G_CONFIRM_RUN": "Start the run? Its cost:"`, `"G_START_FAILED": "Cannot start {program}: {reason}. Install kicad-rf-studio again."`, `"G_COL_PORT": "Port"`, `"G_COL_TIME": "t (ns)"`, `"G_COL_RESIDUAL": "Residual (dB)"`, `"G_COL_SPEED": "MC/s"`, `"G_COL_VERDICT": "Verdict"`.

- [ ] **Step 1: Write the failing tests,** in `tests/test_gui.py` (imports added at the top: `os`; `import pytest`; `from PySide6.QtWidgets import QFileDialog`; `from kicad_rf_studio import runs`; `from kicad_rf_studio.cli import main`; `from kicad_rf_studio.core.project import load_project`; `from kicad_rf_studio.gui import control`; `from kicad_rf_studio.gui.window import MainWindow`; `from test_cli_cost import fail, new_project`; `from test_gui_control import FAKE_PREFIX, until`):

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui.py -q`. Expected: FAIL — `ModuleNotFoundError: No module named 'kicad_rf_studio.gui.window'`.
- [ ] **Step 3: Implement `MainWindow`.** The tests fix the widgets, texts and states; this fixes the flow. Its internals besides the tested state: `tail`, `end` (the watch's end event), `live` (its process going on) and `mtime` (project.json's `st_mtime_ns` at the last read).
  1. `open_project(path)`: `self.path = pipeline.project_path(str(path)).resolve()`; clear the views and the watch (`command`, `run_dir`, `tail`, `end`, `proc`, `cost`, `opened` to None); `load()`; `tick()`.
  2. `load()`: stamps `self.mtime` (None when the file cannot be stat'ed) before anything else, so that a save is read once, then sets `project_status` to G_LOADING and submits `control.open_project(self.path)` to the pool as `self.loading`.
  3. `tick()`, in this order: nothing without a project; a done `loading` is taken first (`done, self.loading = self.loading, None`), then `self.opened = done.result()` and `show_project(self.opened)` inside a `try` whose `except Exception as e` puts `control.text("E_INTERNAL", {"detail": detail(e)})` in `project_status`; with a watch, `returncode = self.proc.poll()` when this window started it (polled before the tail is read, so an exit it sees has its end event read already), then each event of `control.latest(self.tail.read())` through `show_event`, then `control.run_state(self.run_dir, self.end, None, self.proc is not None, returncode)` rendered into `cost_status` (watch `cost`) or `run_status`, and `live = code == "G_RUNNING"`; without one, `live = False`; a `st_mtime_ns` of project.json other than `self.mtime` starts `load()`; buttons: Cost when not live, Run… when not live and `self.cost` is set, Stop when live.
  4. `show_event(e)`: an `end` sets `self.end` and is never listed; after a cost that ended with exit code 0 it also starts `load()`, whose read finds that cost as the model's (`control.last_cost`), off the GUI thread; a cost watch appends `control.text(code, params)` of every other event to `cost_lines`; a run watch fills job k's row k − 1 (rows added as needed) from a `progress` (port, t_ns, residual_db, speed_mcs) and sends every other event to `log`, a `verdict` with a job k ≥ 1 also filling that row's port and verdict cells.
  5. `watch(command, run_dir, proc=None)`: sets the watch (`command`, `run_dir`, `Tail(run_dir / "events.jsonl")`, `end = None`, `proc`), clears `cost_lines` (cost) or `jobs` and `log` (run), and selects that tab.
  6. `start(command)`: `run_dir = runs.run_dir_for(self.path.parent.name)`; `control.start(self.prefix, command, self.path, run_dir)`, whose `OSError` puts G_START_FAILED (`program=self.prefix[0]`, `reason=reason(e)`) in that command's status and starts nothing; else `watch(command, run_dir, proc)` and `tick()`.
  7. `run()`: the `cost` events of `self.cost`'s folder (`control.Tail(...).read()`, kind `cost`) rendered under G_CONFIRM_RUN and a blank line, through `ask`; on True, `start("run")`. `ask(text)` is `QMessageBox.question(self, render("G_CONFIRM_TITLE"), text) == QMessageBox.StandardButton.Yes`. `stop()` writes `STOP` (empty) into `self.run_dir`.
  8. `show_project(opened)`: `project_status` is G_PROJECT (`f0_mhz=f"{f0_hz / 1e6:g}"`) or `control.text(*opened.problem)` without a project; `self.cost = opened.cost`; unless the watch is a cost (live or ended), `cost_lines` replays `self.cost`'s events with `cost_status` G_COST_REUSED (`folder=self.cost.name`), or is cleared with G_NO_COST. `# ponytail: a cost still running when the window opened is not re-attached (cost takes no lock), and a second one may start beside it; a lock for cost if that matters`.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/gui/__init__.py src/kicad_rf_studio/core/messages.py tests/test_gui.py
git commit -m "feat(gui): the main window opens a project, shows its cost, and starts, follows and stops a run of its own (Stage 2 design 5.1, 5.3)"
graphify update .
```

---

### Task 8 [code]: The main window re-attaches — the lock, the banner and the replay

**Files:**
- Modify: `src/kicad_rf_studio/gui/window.py` (`tick`, `show_project`, `closeEvent`); `tests/test_gui.py`.
- Test: `tests/test_gui.py`.

**Interfaces:**
- Consumes: Task 7's `MainWindow`; `runs.lock_holder`, `runs.lock_file`; `control.run_state`'s holder rows and `control.text("E_LOCKED", ...)`; in tests, Task 7's `window`, `opened`, `items` and `grab`.
- Produces, in `MainWindow`:
  - In `tick()`, right after the project check: `holder = runs.lock_holder(self.path)`. A holder whose `run_dir` is the project's `results/` folder (compared as Paths) is a retune (`pipeline.py:701`, r2 §1): never watched or bannered, and passed to `run_state` as None. Any other holder with a `run_dir` that is not None and not `self.run_dir` is attached with `watch("run", Path(holder["run_dir"]))` when this window's own process is not running and the holder lives, or when it is dead and the window watches nothing (on open), so a cost meanwhile keeps its tab; this happens before the tail is read, with no recursion. `run_state` gets that holder. `banner` shows `control.text("E_LOCKED", {"lock": str(runs.lock_file(self.path)), "run": holder["run_dir"], "started": holder["started"]})` while a holder other than a retune lives and names a `run_dir` and `self.proc` is None, and is hidden otherwise. Cost and Run… are also disabled while any holder lives.
  - `show_project`: without a watch and without a lock, `watch("run", opened.last)` when there is one.
  - `closeEvent(event)`: stops the timer and `self.pool.shutdown(wait=False, cancel_futures=True)`; never stops or kills what this window started.

- [ ] **Step 1: Write the failing tests,** in `tests/test_gui.py` (`import json` added):

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui.py -q`. Expected: the three new tests FAIL (nothing attaches yet: `second.run_dir` is None, and a live lock leaves Cost and Run… enabled).
- [ ] **Step 3: Implement** the Interfaces above in `window.py`.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/window.py tests/test_gui.py
git commit -m "feat(gui): the main window re-attaches through the lock and replays a project's last run (Stage 2 design 5.1, 5.3)"
graphify update .
```

---

### Task 9 [code]: The Results tab under the what-if label

**Files:**
- Modify: `src/kicad_rf_studio/gui/window.py` (`ResultsView`, the fourth tab; `show_project` feeds it); `src/kicad_rf_studio/core/messages.py` (`"G_TAB_RESULTS": "Results"`); `tests/test_gui.py`.
- Test: `tests/test_gui.py`.

**Interfaces:**
- Consumes: `control.Opened`, `control.text`, `outputs.draw_summary`, `outputs.LIMITS`; test_run's `lpf_run`.
- Produces: `kicad_rf_studio.gui.window.ResultsView(QWidget)`: `what_if: QLabel` (word-wrapped), `problem: QLabel`, `canvas: FigureCanvasQTAgg` on `Figure(layout="constrained")`, `lines: QListWidget`, and `display(opened: control.Opened, name: str) -> None`: clears the figure and the lines; `what_if` shows `control.text("I_WHAT_IF", {})` only when the results carry `what_if`; `problem` shows `control.text(*opened.problem)` only with one; with results whose chain is closed and 2 external ports, `draw_summary(fig, lay, chain, ideal, name, <the label or None>)`; whenever there are results, plot or not (a 3-port, a part's refusal), the lines are `control.text` of `results.lines` then `render` of each LIMITS code, and without results none; then `canvas.draw_idle()`. `MainWindow.results` is the fourth tab, and `show_project` ends with `self.results.display(opened, self.path.parent.name)`. PySide6 is imported before `matplotlib.backends.backend_qtagg` at window.py's top.

- [ ] **Step 1: Write the failing tests,** in `tests/test_gui.py` (imports: `from kicad_rf_studio import pipeline`; `from kicad_rf_studio.core.post.outputs import LIMITS`; `from kicad_rf_studio.core.project import save_project`; `from test_run import lpf_run`):

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui.py -q`. Expected: FAIL — `AttributeError: 'MainWindow' object has no attribute 'results'`.
- [ ] **Step 3: Implement** `ResultsView` in window.py (its docstring: "The Results tab (Stage 2 design 5.3, 5.4): summary.png's drawing on a FigureCanvasQTAgg, the what-if label over it while RETUNE_VALIDATED is False, and the result's lines and stated limits; or why there is none.") and the window's fourth tab.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py tests/test_gui.py
git commit -m "feat(gui): the Results tab draws summary.png's plots under the what-if label (Stage 2 design 5.3, 5.4)"
graphify update .
```

---

### Task 10 [run]: The controller's offscreen visual review

Commits nothing. The PNGs stay outside the repo.

- [ ] **Step 1: Grab every screen.** In PowerShell from the repo root: `$env:KRS_GRAB_DIR = "$env:TEMP\krs-grabs"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q; Remove-Item Env:KRS_GRAB_DIR`. Expected: all pass, and `project.png`, `cost.png`, `run.png`, `run-attached.png`, `run-lost.png`, `results.png` and `results-stale.png` in that folder.
- [ ] **Step 2: Look at each PNG** (the Read tool shows images) at 1200 × 800 and check:
  - every word is from the catalog, in English, legible and unclipped, the tabs in the CLI's order (Project, Cost, Run, Results);
  - Project: the G_PROJECT line and the Open button;
  - Cost: the 2D header first, its section line, then the cost lines through "Main cost"; the status; Run… enabled;
  - Run: the P1 and P2 rows with t, residual, MC/s and the verdict; G_RUN_START in the log; the end state;
  - run-attached: the G_LOCKED banner over the table, Stop enabled, Cost and Run… disabled;
  - run-lost: G_END_LOST, Run… enabled;
  - results: three panels (|S21|, |S11|, the Smith chart) with the f0, 2f0 and 3f0 lines and the legend; the what-if label both as the banner and as the title's second line; the lines and the stated limits below;
  - results-stale: no plot, G_RESULTS_STALE.
- [ ] **Step 3: Fix what fails.** Each defect becomes a [code] fix in the owning task's file, test-first where a test can see it (a widget's text, visibility or enabled state), committed as `fix(gui): ...` after the full suite; then Step 1 again. Offscreen text drawn as boxes is a font matter of the offscreen platform: note it for plan 4's release check rather than shipping fonts.

---

## Not in this plan

- **The rest of §5.3** (design §5.9 item 2, plan 2): New from a board with the pad picker (`cli.new` is ready), the retune session with snapping and S2P parts (`snap` is ready), Apply, Verify with its button and stale indicator, the advanced panel, About. Until then G_WHAT_IF names a Verify the GUI does not have yet.
- **kicad-python** and everything of the button (plan 3): the helper, the handoff, the single instance (`QLocalServer`), `install-kicad-plugin`, refill and save, the KiCad 10 output contract, the `plugin.json` checks, kicad-python's §3.4 pin, and a run outliving a launcher job that kills on close and forbids breakaway (KiCad's exec runtime; r2's risk). Only the helper imports kicad-python.
- **Install and release** (plan 4): the README's install section, NOTICE's runtime dependencies, `tools/release_check.py`, and §5.11's real end-to-end run.
- **Preview and Calibrate buttons:** optional in Stage 2 (design §6), and nothing needs them.
- **The redraw measurement and blitting** (design §5.4): they concern the instant retune's redraws (plan 2).
- **G_ wording of E_RESULTS_WRITE's command advice:** it names `retune`, which Apply runs (plan 2).
- **Re-attaching a cost that is still running** when the GUI is reopened: cost takes no lock; the GUI shows the last ended cost and may start another beside it, which on a machine not yet calibrated runs a second calibration beside the first, both measuring contended speeds that size later runs until `kicad-rf-studio calibrate` measures again (ponytail note in `window.py`).
- **A retry of project.json's replace** while another process reads it: the GUI reads project.json only on open, after its mtime changed and after a cost, never on its timer; a read meeting a run's save fails it with E_RESULTS_WRITE, as any program holding the file does today.
- **Qt's own translations and the pt-BR catalog** (design §5.7): after v1.

## Controller rulings (2026-10-27; binding)

The architect's rulings, revised after the four reviews (coverage, feasibility, process safety, quality). Each is a controller recommendation, owner unavailable.

- Ruling: ten tasks, not the suggested eight: the output split (Task 4) is a task of its own, apart from `cli.new` and `snap` (Task 3), and the main window is two, Task 7 on its own process and Task 8 re-attaching — each is a change a reviewer can pass or reject on its own, and the repo's first Qt code should not reach the re-attach logic behind one gate — cost if wrong: two more review gates.
- Ruling: `cli.main` writes the end event in its `finally` whenever the command's run folder exists by then: the `--run-dir` one, made first, or the one `cli.main` picked with `runs.run_dir_for` and the command made itself (under the lock, or at cost's calibration or setup gate); a folder never made gets nothing — design 5.2 item 3 (whenever a run folder is known) and 5.1's re-attach through the end events, so a run typed in a terminal shows its end state in the GUI too; a portless cost and a refusal before the lock still make no folder, so no test writes into the user's data folder — cost if wrong: one more line at the end of each run folder, which three existing assertions now expect.
- Ruling: the end event's params are `exit_code`, `command` and `project` (the resolved project file), its code `I_END`, never printed — `command` lets the GUI find the last cost without reading a folder's contents, resolving makes Windows' short and long names of one folder compare equal, and the CLI's printed output, which many tests pin, stays as it is — cost if wrong: none.
- Ruling: a refusal or an internal error that `cli.main` catches is also a `message` event before the end event, when the folder exists — the design makes a refusal before the lock visible, and the end event alone carries no reason; refusals under the lock are events already (`_locked`); A-13 also amends §6.1 step 5, since these two events never reach stdout — cost if wrong: none.
- Ruling: `cost` writes its first lines (W_FILLS_AS_SAVED, the 2D readout, load()'s notes, prepare's warnings, W_NO_PORTS, the mesh gates) as events when its run folder exists at its start, which `--run-dir` makes so, and prints them only otherwise, as before: `message`, `cost` (the readout) and `verdict` with job None (the mesh gates, as run's model phase writes them) — a terminal cost makes its folder only at its calibration or setup gate, and a portless one never; the Cost tab lists a cost folder's events in order whatever their kind — cost if wrong: a terminal cost replayed in the GUI starts at its calibration or setup gate (ponytail note).
- Ruling: the first-use calibration runs in `<run folder>/calibrate/`, `run_jobs` polling the caller's folder for STOP and its two lines message events there; `runs.emit` with no run folder prints only, so `calibrate` and `cost` each have one call for both modes; `kicad-rf-studio calibrate` keeps a folder of its own — one rule for cost, run and verify (design 5.2 item 9), no `calibrate-*` folder beside a run, and no print-or-emit branch — cost if wrong: none.
- Ruling: `runs.lock_holder` reads a lock that does not parse yet as held by a live run of unknown folder, and `project_lock` reads its holder through it: a lock released meanwhile is retried instead of ending in E_INTERNAL, and one still being written is read again every 50 ms, 20 times at most, before it counts as held; the GUI's banner needs a holder that names its folder — one reader for the CLI and the GUI, and no running since None for a run starting at that instant — cost if wrong: an empty lock left by a hard kill at that instant refuses with E_LOCKED's None fields until deleted, as its advice says (ponytail note).
- Ruling: `project_lock` deletes its lock, on release and on a stale reclaim, through `runs._unlink`, which retries a PermissionError every 20 ms for about 1 s — Windows refuses to delete a file another process has open (probed: WinError 32), and the GUI reads the lock every 500 ms, so a run that kept its results could otherwise end in E_INTERNAL with its lock left behind — cost if wrong: a reader that holds the lock past 1 s still fails the delete (ponytail note).
- Ruling: project.json's replace (`save_project`) is not retried — the GUI reads project.json only on open, after its mtime changed and after a cost, never on its timer, so a read meeting a run's save is a coincidence of the user's, and it fails with E_RESULTS_WRITE as any program holding the file makes it fail today — cost if wrong: a run to run again; retry `os.replace` in `save_project` if it is ever seen.
- Ruling: `--run-dir` is made absolute, and one that cannot be made or already holds a run (an `events.jsonl`) is the refusal E_RUN_DIR, which writes nothing into it — every refusal is a coded error (Stage 1 §8); the lock, results.run_dir and the end event then name a folder every later reader finds, and no run appends to another's events — cost if wrong: one catalog line.
- Ruling: `new` stays in cli.py as a public `cli.new(...)` returning its notes; `_new` prints them; `_list`, `_part_note` and `_reference` stay — design 5.2 item 5 fixes the behaviour and the names are the builder's; moving it into pipeline would cost every `new` about 0.7 s of imports (scikit-rf), move four test monkeypatches and break tools/p0c.py's import of `cli._reference`; cli imports neither Qt nor kicad-python (design 4), so plan 2's GUI may call it on a worker thread — cost if wrong: none.
- Ruling: `snap` is in `core.kicad.values` beside `port_value`, builds its candidates as decimals (`float(f"{m}e{e}")`) over three decades and breaks a tie toward the lower value; the plan states its rule and the eight cases pin it (probed) — 4.7e-12 comes back exactly as typed, with no floor-of-log10 edge at a power of ten — cost if wrong: none.
- Ruling: `ChainResults` carries `what_if`, and its lines stop before the label's; `write_outputs` renders I_WHAT_IF with `verify`'s command, appends it, then I_OUTPUTS and LIMITS — the CLI's files and lines stay byte-identical while the GUI words the label its own way (G_WHAT_IF) — cost if wrong: none.
- Ruling: byte-identity is shown by a one-off digest of summary.png before and after Task 4 (d0c52580…44f78 on today's dev venv, probed again), a test that summary_png is `draw_summary` saved at 100 dpi, and a test that write_outputs' lines and files are chain_results', which writes nothing itself — a committed golden hash would break across matplotlib versions and CI platforms — cost if wrong: none.
- Ruling: kicad-python is not added in plan 1; plan 3 adds `kicad-python>=0.8,<0.9` with the helper and lands its §3.4 pin — only the helper imports it (design 5.5); the no-kipy assertion on cli and worker is written now — cost if wrong: one dependency line in plan 3.
- Ruling: PySide6-Essentials is a core dependency with no extra, and pytest-qt is not added — design 5.6 and 5.8; the tests call the window's `tick()` and wait on files, one drives the window's own timer through `processEvents()`, and QFileDialog is monkeypatched as pytest-qt's own docs do, so nothing needs `waitSignal` — cost if wrong: none.
- Ruling: the Qt-free GUI logic is `gui/control.py`, and `gui/__init__.py` imports Qt only inside `main()`; neither loads matplotlib, pinned by the import test — design 5.8's Qt-free logic tested like the engine, and C-5 for the code the GUI runs on its pool, in the fewest files — cost if wrong: none.
- Ruling: the project read (load, build_model, results_of, chain_results and the run-folder lookups) runs on a `ThreadPoolExecutor(1)` whose future the 500 ms tick takes before it shows it, so a display that fails shows E_INTERNAL and the next tick goes on; `load()` stamps project.json's mtime before it submits, so a save reads the project once; a cost that ends with exit code 0 reads the project again, which finds it as the model's cost, so no run folder is scanned on the GUI thread; no QThread and no signals; matplotlib draws only in the tick — design 5.1 and goal 4, with one mechanism, the timer — cost if wrong: results, and Run… after a cost, show up to 0.5 s after their read, which takes 1–3 s.
- Ruling: one watched process at a time: Cost and Run… are disabled while the watched folder is live and while any run holds the lock — design 5.1 asks it for the lock; cost takes none — cost if wrong: across windows a second cost may start beside a first that is still running, and on a machine not yet calibrated the two calibrate side by side, measuring contended speeds that size later runs until `kicad-rf-studio calibrate` measures again.
- Ruling: a run this window did not start is attached through the lock when it lives, and through a dead lock only when the window watches nothing (on open), so a cost meanwhile keeps its tab; a lock naming the project's results/ is a retune (r2 §1): never watched or bannered, Cost and Run… disabled while it lives; otherwise the newest ended run or verify is replayed. One that ends without an end event reads G_ENDED once its lock is released (a run of an older version, or the moment between the lock's release and the end event) and G_END_LOST while its lock's process is dead — the window never stays running on a folder nobody writes — cost if wrong: a provisional G_ENDED until the end event, written just after the lock's release, replaces it.
- Ruling: five CLI-worded codes show as GUI codes with the same params (E_LOCKED, I_RUN_START, I_WHAT_IF, E_NO_RESULTS and E_RESULTS_STALE as G_LOCKED, G_RUN_START, G_WHAT_IF, G_NO_RESULTS and G_RESULTS_STALE) through `control.text`; every other code shows as the CLI renders it — r2's short list; E_RESULTS_WRITE's command waits for Apply (plan 2) — cost if wrong: a CLI hint reads oddly in the window.
- Ruling: the end state is G_END_DONE, G_END_REFUSED, G_END_BLOCKED, G_END_NOT_KEPT and G_END_STOPPED for exit codes 0, 2, 3, 4 and 130, and G_END_FAILED for any other; this window's own process that exited without an end event reads G_END_EXITED with its exit code and its cli.log, and only another's G_END_LOST — Stage 1's commands exit with exactly these (plan 4's Global Constraints), and design 5.3 asks for the end state with its exit code — cost if wrong: on Windows a killed process and one that failed at its start both exit 1, so G_END_EXITED names both causes.
- Ruling: the tail reads at most 1 MiB a tick, and only the last progress event of each job in a batch reaches the table (`control.latest`) — re-attaching to an 8 h run replays about 40k events over a few ticks without thousands of cell writes per tick (design §3, r2 §1) — cost if wrong: a line over 1 MiB is never read; events are under 1 KB (ponytail note).
- Ruling: the Results tab draws only what summary.png draws (two external ports with the chain closed) and lists the lines and LIMITS whenever there are results, plot or not, and nothing without; the label is both a banner over the plot and the figure title's second line, as in summary.png — design 5.3: everything comes from the same data as summary.png, and every retuned plot carries the label — cost if wrong: none.
- Ruling: G_WHAT_IF is I_WHAT_IF's text with the command replaced by Verify, pinned by a test, though the Verify button is plan 2's — design 5.3 and the owner default (§7.6's text, pointing to Verify) — cost if wrong: for one plan, the label names a button that is not there yet.
- Ruling: Run…'s confirmation goes through `MainWindow.ask(text)`, which tests replace on the instance, and the Open dialog through `browse()`, which one test drives with QFileDialog's static method monkeypatched and the others bypass with `open_project` — a modal dialog would block an offscreen suite — cost if wrong: none.
- Ruling: Cost stays enabled when the GUI's own read of the project failed — the cost then shows the engine's refusal itself, and the GUI adds no gate of its own (design §3) — cost if wrong: none.
- Ruling: `tests/fake_cli.py` holds the fake fixture's five patches as `patches(data)`, which conftest's `fake` applies with monkeypatch and fake_cli applies under `__main__` with $KRS_FAKE_DATA — the fixture's in-process patches never reach a child process (r2 §4), and one table cannot drift — cost if wrong: none.
- Ruling: Task 10's PNGs come from the offscreen tests themselves when `$KRS_GRAB_DIR` is set, not from a separate script — each screen is already driven through its main path there (design 5.8) — cost if wrong: none; the folder is outside the repo.
- Ruling: Linux CI installs libegl1, libgl1, libxkbcommon0, libfontconfig1 and libdbus-1-3 before the tests; the step is written, not run (push-gated) — r2 §4's list of what QtGui may still load offscreen — cost if wrong: the first push's Linux jobs fail at the GUI tests and the list changes.
- Ruling: `messages.detail(error)` holds E_INTERNAL's one-line, 200-character detail for `cli.main`, `control.open_project` and the window's tick alike — DRY — cost if wrong: none.
- Ruling: the stale-results tests change `t_max_s` by hand — T_max is in the model spec's excitation, so the edit makes the results stale without touching the mesh, whose refusals could answer first (both edits read E_RESULTS_STALE on lpf915, probed) — cost if wrong: none.
- Ruling: Cost, Run… and Stop start disabled; `gui.main` reads `sys.argv[1:]` when given no argv, and points a missing `sys.stderr` at `data_dir()/gui.log` — the gui-scripts entry runs pythonw on Windows from this plan on (r3 R-2), where a slot's traceback would be lost, and a click before any project must not reach `start` — cost if wrong: one log file in the data folder.
- Ruling: `control.start` retries without breakaway only on PermissionError (a job that forbids breakaway) and starts the orchestrator with its run folder as working folder — a missing python is no job matter, and a working folder held for hours would block renaming the board's folder once the button starts the GUI there — cost if wrong: in a job that kills on close and forbids breakaway the run still dies with the GUI (ponytail note; plan 3 checks KiCad's job).
- Ruling: design 5.1's first rule is pinned by the window fixture, which makes `runs.run_jobs` and `runs.ensure_calibrated` fail in the test process after the test's own engine calls; the GUI's openEMS rule is checked in-process once a window read and drew results, as test_cli_cost and test_run check theirs, instead of a second QApplication in a subprocess — design 5.1, 5.8 — cost if wrong: none.
- Ruling: `ResultsView` lives in window.py, and `Tail` keeps no count of the lines it skips — the fewest files, and nothing reads the count — cost if wrong: plan 2 splits Results out when the retune session grows it.
- Ruling: no test shows a run outliving the process that started it — in the dev venv the launcher's job lets its children break away silently (probed: KILL_ON_JOB_CLOSE with SILENT_BREAKAWAY_OK, a grandchild outlived its parent with and without CREATE_BREAKAWAY_FROM_JOB), and on Linux nothing kills it, so such a test cannot fail for a missing flag; the threat is a launcher job that forbids breakaway, KiCad's — cost if wrong: plan 3's job-object test finds it.
- Ruling (disclosure): the architect ran only read-only probes, on the repo's synthetic fixtures in a scratch folder: an lpf915 network-fake run with the fake fixture's patches applied in-process (run 8 s, write_outputs 0.55 s, load and build_model 1.53 s, 9 lines before the label), write_outputs on Task 4's synthetic 2-port with C1 (the same 9 codes and 4 files), the summary.png digest twice (identical), the import times of `new`'s modules (0.71 s) and pipeline (1.42 s), the mkdir error behind a file (FileExistsError, already exists as a file), the coupon's readout (one I_2D_SECTION, no load notes) and two hand edits on lpf915 (E_RESULTS_STALE). The reviser ran read-only probes too: the venv launcher's job flags and a grandchild outliving its parent, Windows refusing to delete a file open in the same process (WinError 32) and a 20 ms retry deleting it 0.21 s later, the snap rule on the eight test cases, the summary.png digest (unchanged) and the modules the engine imports (scikit-rf, no matplotlib, no PySide6). PySide6 is not in the dev venv, so no Qt code ran — cost if wrong: none.
