# Stage 2 · Plan 3 — KiCad Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the GUI its KiCad toolbar button (design §5.9 item 3): a Qt-free helper that KiCad 9.0.7+ and 10.x run from an exec plugin and that hands the open board and the selection to a single-instance GUI, which pre-fills New; `install-kicad-plugin` for KiCad 9.0 and 10.x; and the GUI's confirmed "Refill zones and save in KiCad".

**Architecture:**
- **KiCad's side is one Qt-free module, `src/kicad_rf_studio/button.py`** (Tasks 2, 3, 6). Its helper, `python -X utf8 -I -m kicad_rf_studio.button`, which the installed launcher runs, reads KiCad's version, board and selection through kipy, writes `handoff.json` into the data folder, starts `kicad-rf-studio-gui --handoff FILE` detached and exits 0 with nothing on stdout or stderr. Its installer writes plugin.json, the launcher and stdlib-drawn icons into KiCad's plugin folders, and its `refill` refills and saves the board in the KiCad the handoff came from. kipy is imported only inside the functions that call KiCad, so `cli`, `worker` and `import kicad_rf_studio.button` load none of it.
- **The GUI's side (Tasks 4–6):** a press is New's pad read (`control.handed`: the selected KIIDs joined to Stage 1's `Pad.uuid` from `load_board`, read on the pool and shown by plan 2's `show_pads`), with Swap. `gui.main` forwards its request to the window that runs, or takes a per-user lock file and becomes that window, with a per-user `QLocalServer`. Refill zones and save in KiCad sits behind a confirmation.
- **The tests talk to a fake KiCad** (`tests/fake_kicad.py`): kipy's real client against an nng socket that answers kipy's own protobuf messages the way KiCad 9.0.7 does. Task 2 also pins, against a Windows job object made with ctypes, that a run the GUI starts outlives a KiCad job that kills on close. Task 7 is the controller's replay of the installed launcher from a console-less parent.

**Tech Stack:** Python ≥ 3.11 (the dev venv runs 3.14.2). kicad-python 0.8.0 (`kipy`; it brings protobuf 5.29, pynng 0.9 and jsonschema 4), whose `kipy.packaging.validate.validate_plugin` checks plugin.json. PySide6-Essentials 6.12.0: QtCore's `QLockFile`, QtNetwork's `QLocalServer` and `QLocalSocket`, QtWidgets, and QtGui's `QImage` in a test. From the stdlib: `subprocess`, `ctypes` (the Documents folder, the foreground grant; a job object in a test), `sysconfig`, `argparse`, `json`, `hashlib`, `zlib` and `struct` (the icons), `shutil`, `warnings`. pytest, with no pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-27-stage2-gui-and-button-design.md` (binding), its §5.9 item 3:
- §5.5 in full: the plugin, its identifier and launcher; the helper and the KiCad 10 output contract; the KiCad versions; single instance; from the selection to REF.PAD; Refill; Install.
- §5.3 Project: "A button handoff pre-fills the board and the pads".
- §5.6: the `kicad-python>=0.8,<0.9` pin and the import test.
- §5.8: the handoff and the helper's contract (against a fake KiCad: see the rulings), the installer's files, plugin.json against the bundled schema and both identifier rules, no Qt in the helper.
- §5.10: A-16 (§3.4's pin, Task 1), A-17 (§3.2's `install-kicad-plugin`, Task 3), A-18 (§10's zone refill and §4.3, moved to the button's refill, Task 6).
- §5.11 item 3, the launcher replayed, as Task 7; plan 4's end-to-end check runs it again.
- §3 (anti-goals) and §4 (constraints) bind every task. §7's owner defaults apply: the identifier `org.kicadrfstudio.app`, and the GUI saves the board only through the confirmed refill-and-save action.

The research is git-ignored: `.superpowers/sdd/stage2-research/r1-kicad/findings.md` (primary: kipy 0.5.0 and 0.8.0, KiCad 9.0.7 and 10.0.7), `r3-pack/findings.md` and `r2-gui/findings.md`. The button pre-check is `docs/validation/2026-10-24-precheck.md`. The engine authority is `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, amended here in §3.2, §3.4, §4.3 and §10.

**Branch:** `stage2-plan3`, from `main` at `a6bf7e7`. This plan is `docs/superpowers/plans/2026-10-28-stage2-plan3-kicad-button.md`. Commands run from the repo root with `.venv/Scripts/python`.

**Before Task 1 (the controller):**
1. Branch `stage2-plan3` from `main`. `git diff --stat a6bf7e7 HEAD -- src tests tools pyproject.toml .github` must print nothing; otherwise re-check this plan's line references first.
2. Commit this plan on the branch. Its rulings are its last section, `## Controller rulings (2026-10-28; binding)`.
3. After Task 7: the whole-branch review, then a local merge into `main`. Nothing is pushed.

## Global Constraints

- **Python and platforms:** the declared floor stays `>=3.11` and the CI matrix as it is; the Windows install uses Python 3.14; Windows 10/11 and Linux with glibc ≥ 2.34; KiCad 9.0.7 minimum, with 10.x supported (design §4).
- **Dependencies:** this plan adds only `kicad-python>=0.8,<0.9`, a core dependency with no extra. No pytest-qt, no psutil, and no JSON-schema code or schema file of our own. Install only into the dev venv: `.venv/Scripts/python -m pip install -e .[dev]`.
- **Import rules (design §4):**
  - The core and `gui/control.py` never import Qt; the GUI never imports openEMS or CSXCAD.
  - `cli` and `worker` import neither Qt nor kipy.
  - `kicad_rf_studio.button` never imports Qt, and imports kipy only inside the functions that call KiCad, so `import kicad_rf_studio.button` loads neither (`tests/test_gui.py`'s `QT_FREE` probe). The helper and `install-kicad-plugin` load no Qt when run either (Tasks 2 and 3 check it in a subprocess).
  - matplotlib loads only in the PNG writer and `gui/window.py` (C-5).
- **Process model (design §5.1, §5.5):** nothing in the GUI process reaches `runs.run_jobs`. kipy runs only on the window's pool, never the GUI thread, and the handoff is read there too. Every pool result is taken by the 500 ms tick.
- **KiCad's side (design §5.5):**
  - The helper exits 0 within about 2 s with nothing on stdout or stderr, or 1 with one stderr line and a `button.log` line.
  - It never calls `check_version()`, retries `AS_BUSY` within one 1 s budget for the whole press, and reads `AS_UNHANDLED` and `AS_UNIMPLEMENTED` as "not in this KiCad".
  - It starts the GUI detached: stdin and stdout the null device, stderr appended to `gui.log`, never one of KiCad's pipes.
- **No unasked board edits, no KiCad settings (design §3, §7):** the GUI saves the board only through the confirmed "Refill zones and save in KiCad", only on the board and in the KiCad that the confirmation named, and never writes a board file itself. `install-kicad-plugin` writes only `plugins/kicad-rf-studio` in KiCad's documents folders, never KiCad's settings.
- **Identifier:** `org.kicadrfstudio.app` (design §7's default; the final one is the owner's, tied to the account).
- **Messages:**
  - Every user-facing string is a code in the one `CATALOG` of `core.messages`, plugin.json's name and descriptions included, rendered with `render()`. GUI codes start with `G_`.
  - The helper's lines are ASCII, but for the paths in their params (Task 2 checks the catalog texts).
  - New codes are appended at the end of `CATALOG`, after `"G_ABOUT_TEXT"` (L300) and the codes earlier tasks added.
  - Tests check `KrsError.code` and `.params`, or rendered lines, never `match=`.
- **Licence and files:** GPL-3.0-or-later; an English UI; `# SPDX-License-Identifier: GPL-3.0-or-later` heads every new `.py` file.
- **Tests:**
  - Test-first. Tier (a) never runs openEMS.
  - No test starts KiCad, kicad-cli or any KiCad binary: KiCad is `tests/fake_kicad.py`, at an `ipc://` address under `tmp_path`.
  - No test touches a real KiCad plugin folder, the real Documents folder (one test reads its path, never the folder), KiCad's settings or the real data folder. `tests/conftest.py`'s autouse `no_kicad` points `KICAD_DOCUMENTS_HOME` and `KICAD_CONFIG_HOME` under `tmp_path` and `KICAD_API_SOCKET` at an `ipc://` address no KiCad listens on, and clears `KICAD_API_TOKEN`, for every test (kipy's default socket would be a KiCad the owner has open); a test that needs other values sets them. A subprocess that runs the helper or the GUI gets `LOCALAPPDATA` and `XDG_DATA_HOME` under `tmp_path`, and a GUI also `QT_QPA_PLATFORM=offscreen`. In-process tests use the `fake` fixture's data folder, which also names the GUI's local server and lock file, so no test reaches a GUI the owner has open.
  - Qt only under `QT_QPA_PLATFORM=offscreen`, which `tests/conftest.py` sets. No modal dialog: tests replace `ask`, or patch `QMessageBox.question` so that `ask` itself runs.
  - A stand-in GUI that a test starts detached runs on `pythonw.exe` on Windows, so no console opens; the test kills it at its end, and so is any second GUI process a test starts.
  - Every slot is a bound method; a lambda or partial slot keeps a closed window alive (plan 1).
- **Full suite:** before every commit, `.venv/Scripts/python -m pytest -q` passes. It takes about 15 minutes, and the shell caps a foreground command at 10, so run it once in the background, with nothing beside it, and wait for its exit.
- **Privacy:** the pre-commit privacy gate runs on every commit (never `--no-verify`). Synthetic fixtures only; a test that writes beside a board first copies it under `tmp_path`. No committed file holds an absolute user path, a drive letter followed by a colon and a slash, a UNC share, an e-mail address or a private name: tests build odd paths from `tmp_path`, or as relative text.
- **Git:** no commit carries a co-author line. Nothing is pushed, and nothing goes to PyPI.
- **Workflow:** every implementer runs `graphify query "<question>"` (or `explain` or `path`) from the repo root before reading code, and `graphify update .` after each commit. Ponytail applies: the laziest solution that works, the repo's functions reused, the fewest files, the stdlib first, and a `ponytail:` comment, with its ceiling and its upgrade, on each corner cut.
- **Amendments:** each changed spec line ends with "(A-n, Stage 2 plan 3: controller recommendation, owner unavailable.)", and the spec's Status line gets one sentence, which later tasks widen.

## Review Focus

1. **A second button press while the window is open, or still starting.**
   - The second GUI start forwards its handoff to the running window and exits at once; the window comes to the front, unminimized, and New takes the new selection.
   - Two presses within the first window's startup make one window: a start that finds `gui.lock` held by a live process waits for that window to listen, then forwards. On Windows two servers can listen on one name (probed), and on Linux Qt's listen renames over the name, so no listen refuses: the lock is what keeps one window. A socket file a killed window left (Linux) does not stop the next start.
   - Tests: `test_the_gui_entry_takes_a_handoff_and_a_second_start_forwards_its_own_and_exits` and `test_a_socket_file_left_by_a_killed_window_does_not_stop_the_next` (Task 5).
2. **The selection against the saved board.**
   - KiCad holds edits not yet saved, so a selected pad's KIID, or a selected footprint's reference, is missing from the file: New says G_HANDOFF_UNSAVED ("save the board in KiCad and press the button again") and pre-fills nothing. After Refill zones and save in KiCad, New reads the press again and pre-fills.
   - A selection that is not two pads: none pre-fills nothing; one fills start; three fill nothing, with G_HANDOFF_PADS; footprints narrow the pickers to their pads and the selected ones; a pad with no copper is never an end. A board that fails to load leaves the pickers empty and is read again when picked once fixed (plan 2's F4 rule).
   - Tests: `test_a_handoff_joins_the_selection_to_the_saved_boards_pads` and `test_a_button_press_pre_fills_new_and_swap_swaps_start_and_end` (Task 4); `test_refill_asks_first_then_kicad_refills_and_saves_and_new_reads_the_board_again` (Task 6).
3. **KiCad closes after a press.**
   - The GUI starts with the design's flags, out of KiCad's pipes and console; the runs it starts break away from any job it sits in (plan 1's `control.start`), so they outlive a KiCad job that kills on close, as long as that job allows breakaway (nothing in this process can beat one that forbids it). The window itself, in such a job, closes with KiCad (ponytail note; the click-through checks whether KiCad has a job).
   - Tests: `test_a_run_the_gui_starts_inside_a_kicad_job_that_kills_on_close_outlives_it` and the `runs._alive` check of `test_run_as_kicad_10_runs_it_the_helper_ends_quickly_says_nothing_and_its_gui_holds_no_pipe` (Task 2).
4. **KiCad 10's pipes, and a busy, restarted or unreachable KiCad.**
   - KiCad 10 reads the action's stdout and stderr only once it ends and shows any stderr text: the helper ends in about a second, prints nothing, and the GUI it starts holds none of its pipes.
   - A KiCad still busy when the press's 1 s is up, another KiCad's token, no API server, a KiCad older than 9 or newer than 10, or a new unsaved board: one stderr line and a `button.log` line, exit 1, no handoff, no GUI. During Refill: a save answered busy while the fill runs, or late, is waited for; a closed PCB editor or another board open refuses with its own line.
   - Tests: `test_run_as_kicad_10_runs_it_the_helper_ends_quickly_says_nothing_and_its_gui_holds_no_pipe` and `test_the_helper_says_why_on_one_stderr_line_and_in_button_log_and_starts_nothing` (Task 2); `test_refill_refills_then_saves_only_the_board_the_button_sent` (Task 6).
5. **Paths:** a Documents folder with a space and an accent, or redirected to OneDrive; a Python path with `%`, `!`, an accent, a quote, or a character the console's code page lacks.
   - The installer follows the shell's Documents folder; the launcher quotes the path for its shell and runs from such a folder; a path launch.cmd cannot hold is refused, writing nothing.
   - Tests: `test_kicads_documents_folder_is_its_own_choice_a_onedrive_redirect_included`, `test_the_launcher_quotes_this_pythons_absolute_path_for_its_shell`, `test_the_installed_launcher_runs_the_helper_and_passes_its_line_and_exit_code` and `test_a_python_path_launch_cmd_cannot_hold_is_refused` (Task 3).

---

## File structure

```
pyproject.toml                                 # T1 kicad-python>=0.8,<0.9
src/kicad_rf_studio/button.py                  # T2 the helper and the handoff; T3 the installer; T6 refill
src/kicad_rf_studio/cli.py                     # T3 install-kicad-plugin
src/kicad_rf_studio/gui/__init__.py            # T5 instance_name, forward, main: the lock, the local server, --handoff
src/kicad_rf_studio/gui/control.py             # T1 DEPENDENCIES; T4 Handed, handed, _names
src/kicad_rf_studio/gui/window.py              # T4 swap_button, take_handoff, show_pads takes a press
                                               # T5 serve, incoming, forwarded, act, closeEvent
                                               # T6 refill_button, refill, refilled, ask's title
src/kicad_rf_studio/core/messages.py           # T2–T4, T6 the codes
docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md   # T1 A-16; T3 A-17; T6 A-18
tests/fake_kicad.py  tests/conftest.py         # T2 the fake KiCad, the `kicad` fixture and the `no_kicad` fence
tests/test_button.py                           # T2, T3, T6
tests/test_gui_control.py  tests/test_gui.py   # T1, T2, T4, T5, T6
```

---

### Task 1 [code]: kicad-python as a core dependency

**Files:**
- Modify:
  - `pyproject.toml` (`dependencies`, L12);
  - `src/kicad_rf_studio/gui/control.py` (`DEPENDENCIES` and the comment above it, L460–466);
  - `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (the Status line, L4; §3.4's dependencies bullet, L148).
- Test: `tests/test_gui.py` (`from importlib import metadata` joins its imports).

**Interfaces:**
- Consumes: plan 2's `control.DEPENDENCIES` and `test_about_names_the_version_the_licence_notices_and_each_runtime_dependency`, which requires every core dependency there; plan 1's `QT_FREE` probe, which looks for `kipy` (it pins that `cli` and `worker` never load it).
- Produces:
  - `dependencies` gains `"kicad-python>=0.8,<0.9"`, after `"PySide6-Essentials>=6.10.1,<7"`.
  - `control.DEPENDENCIES` gains, after `("pandas", "BSD-3-Clause")`: `("kicad-python", "MIT")`, `("protobuf", "BSD-3-Clause")`, `("pynng", "MIT")`, `("jsonschema", "MIT")`. The comment above it names them: "...shiboken6 and pandas, which PySide6-Essentials and scikit-rf bring, protobuf, pynng and jsonschema, which kicad-python brings, and openEMS and CSXCAD, which pip does not install".
  - kipy importable in the dev venv, so that the `QT_FREE` probe's `kipy` check bites.

- [ ] **Step 1: Write the failing test,** in `tests/test_gui.py` after `test_pyside6_essentials_is_a_core_dependency_with_the_gui_entry`:

```python
def test_kicad_python_is_a_core_dependency_and_imports():  # design 5.6; A-16
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "kicad-python>=0.8,<0.9" in project["dependencies"]  # 0.8: the first line that installs on Python 3.14
    assert metadata.version("kicad-python").startswith("0.8.")
    out = subprocess.run([sys.executable, "-I", "-c", "import kipy.board_types, kipy.packaging.validate"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr  # installed is not importable: its protos refuse an older protobuf
```

- [ ] **Step 2: Run it.** `.venv/Scripts/python -m pytest tests/test_gui.py -q -k kicad_python`. Expected: FAIL on the pin's assertion.
- [ ] **Step 3: The dependency.** Edit `pyproject.toml` as Interfaces say, then `.venv/Scripts/python -m pip install -e .[dev]`. Expected: `.venv/Scripts/python -I -c "import importlib.metadata as m; print(m.version('kicad-python'), m.version('protobuf'), m.version('pynng'))"` prints `0.8.0`, a 5.29 version of at least 5.29.6 and a 0.9 version. Run `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_gui_control.py -q`: the new test passes, and the About test now FAILS, its `declared <= ...` naming kicad-python.
- [ ] **Step 4: About and the spec.**
  - `control.DEPENDENCIES` and its comment, as Interfaces say.
  - Stage 1 spec §3.4, the dependencies bullet becomes: "- **Dependencies:** numpy, scipy, h5py, matplotlib, shapely and scikit-rf. Stage 2 adds `PySide6-Essentials>=6.10.1,<7` (6.10.1 is the first with Python 3.14 wheels; Essentials only, so no QtCharts or Addons) and `kicad-python>=0.8,<0.9` (0.8 is the first line that installs on Python 3.14; only the KiCad button's helper and the GUI's refill import it, never the command line or the worker), as core dependencies with no extra. (A-15, Stage 2 plan 1; A-16, Stage 2 plan 3: controller recommendations, owner unavailable.)"
  - The Status line gains, at its end: " On 2026-10-28, Stage 2's plan 3 amended §3.4 (A-16) the same way."
- [ ] **Step 5: Run them again.** `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_gui_control.py tests/test_repo.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add pyproject.toml src/kicad_rf_studio/gui/control.py tests/test_gui.py docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "feat: kicad-python>=0.8,<0.9 as a core dependency, named in About; spec A-16 (Stage 2 design 5.6; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 2 [code]: The helper and the handoff

**Files:**
- Create: `src/kicad_rf_studio/button.py`, `tests/fake_kicad.py`, `tests/test_button.py`.
- Modify: `src/kicad_rf_studio/core/messages.py` (the codes below); `tests/conftest.py` (`from pathlib import Path`; the `kicad` fixture and the autouse `no_kicad`); `tests/test_gui.py` (`QT_FREE` gains `"kicad_rf_studio.button"`, L37–38).
- Test: `tests/test_button.py`, `tests/test_gui.py`.

**Interfaces:**
- Consumes: `runs.data_dir`; `core.project.save_project` (it writes whole, through a temporary file); `messages.reason`, `detail`, `render`, `KrsError`; plan 1's `control.start` (in the KiCad-job test). kipy 0.8.0:
  - `kipy.KiCad(socket_path=None, client_name=None, kicad_token=None, timeout_ms=2000)`, `.get_version()` (`.major`, `.minor`, `.patch`), `.get_board()`;
  - `Board.document` (`.board_filename`, `.project.path`), `Board.get_selection(types)`;
  - `kipy.board_types.Pad` (`.id.value`, the KIID) and `FootprintInstance` (`.reference_field.text.value`);
  - `kipy.proto.common.types.KiCadObjectType.KOT_PCB_PAD` and `KOT_PCB_FOOTPRINT`;
  - `kipy.errors.ApiError` (`.code`) and `kipy.errors.ConnectionError`; `kipy.proto.common.ApiStatusCode`.
  - In tests: test_gui_control's `recorder` and `until`; test_cli_cost's `FIX`; conftest's `fake`.
- Produces, in `kicad_rf_studio.button` (no Qt; kipy only inside `_kicad`, `_call` and `read`):
  - `TIMEOUT_MS = 1000` (one API call's wait), `BUSY_S = 1.0` (a press's whole wait on AS_BUSY), `BUSY_WAIT_S = 0.25`.
  - `_kicad(socket: str, token: str, timeout_ms: int = TIMEOUT_MS) -> kipy.KiCad`: `KiCad(socket_path=socket or None, client_name="kicad-rf-studio", kicad_token=token, timeout_ms=timeout_ms)`; an empty socket is kipy's default.
  - `_call(fn, until: float = 0.0)`: `fn()`, asked again `BUSY_WAIT_S` later while KiCad answers `AS_BUSY` and `time.monotonic() + BUSY_WAIT_S < until` (a deadline on `time.monotonic()`; 0, no retry). KiCad's errors become the button's refusals: `AS_BUSY` past the deadline `E_KICAD_BUSY`; `AS_UNHANDLED` and `AS_UNIMPLEMENTED` `E_KICAD_UNSUPPORTED`; `AS_TOKEN_MISMATCH` and kipy's `ConnectionError` `E_KICAD_UNREACHABLE`. Any other error is raised as it is (E_INTERNAL in `main`).
  - `_board_path(board) -> Path`: `Path(board.document.project.path) / board.document.board_filename`; an empty file name (a new board never saved) raises `E_KICAD_NO_BOARD`.
  - `read(socket: str, token: str) -> dict`: `until = time.monotonic() + BUSY_S`, then in this order, each call through `_call(..., until)`, so the press shares one 1 s: `get_version()`, refused with `E_KICAD_VERSION {version}` unless its major is 9 or 10 (`version` is `f"{major}.{minor}.{patch}"`; `check_version()` is never called: it refuses any KiCad newer than kipy's 10.0.6); `get_board()` and `_board_path`; `get_selection([KOT_PCB_PAD, KOT_PCB_FOOTPRINT])`. It returns `{"board": str(path), "pads": [KIIDs of the selected pads], "footprints": [references of the selected footprints], "kicad": version, "socket": socket, "token": token}`.
  - `write_handoff(data: dict) -> Path`: `runs.data_dir() / "handoff.json"`, its folder made, written with `save_project`. An OSError is `E_HANDOFF_WRITE {path, reason}` (`reason(e, "cannot be written")`).
  - `gui_command(handoff: Path) -> list[str]`: `[str(Path(sysconfig.get_path("scripts")) / name), "--handoff", str(handoff)]`, `name` being `kicad-rf-studio-gui.exe` on Windows, else `kicad-rf-studio-gui`: the gui-scripts entry of this environment, never a PATH lookup.
  - `start_gui(command: list[str], folder: Path) -> subprocess.Popen`: `command` started fully detached, with working folder `folder`, stdin and stdout `subprocess.DEVNULL`, and stderr `folder / "gui.log"` opened for append in binary (closed after `Popen`). Windows: `creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP`, the design's flags; elsewhere `start_new_session=True`.
  - `main() -> int`, KiCad's exec action: inside `warnings.catch_warnings()` with `simplefilter("ignore")` (KiCad 10 shows any stderr text), `handoff = write_handoff(read(os.environ.get("KICAD_API_SOCKET", ""), os.environ.get("KICAD_API_TOKEN", "")))`; on Windows `ctypes.windll.user32.AllowSetForegroundWindow(-1)` (ASFW_ANY, its result ignored: KiCad, in the foreground, started this helper, so the window it starts, or the one that window forwards to, may come to the front; design §2 goal 1); then `start_gui(gui_command(handoff), handoff.parent)`, an OSError of which is `E_GUI_START {program: the command's first item, reason}`; returns 0. Any exception: its line (`str(e)` for a KrsError, else `render("E_INTERNAL", detail=detail(e))`) printed to stderr, and appended to `runs.data_dir() / "button.log"` as `f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {line}\n"` in UTF-8 (the folder made first, any OSError there ignored); returns 1. The module ends with `if __name__ == "__main__": sys.exit(main())`.
  - `tests/fake_kicad.py`'s `FakeKiCad`, given whole in Step 1, and conftest's `kicad` and `no_kicad` fixtures.
  - CATALOG (exact texts):
    - `"E_KICAD_UNREACHABLE": "Cannot reach KiCad: it was closed or restarted, or its API is off. In KiCad's PCB editor, with Preferences > Plugins > Enable KiCad API on, press the kicad-rf-studio button again."`
    - `"E_KICAD_BUSY": "KiCad stayed busy (a dialog, a tool or a zone fill is still open or running). Finish it in KiCad, then try again."`
    - `"E_KICAD_UNSUPPORTED": "This KiCad cannot answer a request the kicad-rf-studio button needs: the button needs KiCad 9.0.7 or later, or 10.x."`
    - `"E_KICAD_VERSION": "KiCad {version} is not supported: the kicad-rf-studio button needs KiCad 9.0.7 or later, or 10.x."`
    - `"E_KICAD_NO_BOARD": "KiCad's PCB editor has no saved board open. Open or save the board in KiCad's PCB editor, then press the kicad-rf-studio button again."`
    - `"E_HANDOFF_WRITE": "Cannot write {path}: {reason}. Check that this folder can be written, then press the kicad-rf-studio button again."`
    - `"E_GUI_START": "Cannot start {program}: {reason}. Install kicad-rf-studio again, then run kicad-rf-studio install-kicad-plugin."`

- [ ] **Step 1: The fake KiCad and the fence.** `tests/fake_kicad.py`, given whole:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""A fake KiCad API server for the button's tests (Stage 2 design 5.5, 5.8): kipy's real client talks to it as to KiCad
9.0.7's, through an nng Rep0 socket that answers kipy's own protobuf messages."""
import threading
import time
from pathlib import Path

import pynng
from google.protobuf.empty_pb2 import Empty
from kipy.proto.board import board_types_pb2
from kipy.proto.common import ApiRequest, ApiResponse, ApiStatusCode
from kipy.proto.common.commands import base_commands_pb2, editor_commands_pb2
from kipy.proto.common.types import base_types_pb2
from kipy.util import pack_any

SLOW_S = 1.5  # how late a "SLOW" answer comes: past the helper's 1 s (button.TIMEOUT_MS)


class FakeKiCad:
    """KiCad's API server at `url` (ipc://...), as kipy 0.8 meets KiCad 9.0.7's. Its token is `token`: a request with
    another, non-empty one gets AS_TOKEN_MISMATCH. Its PCB editor has the board file `board` open (GetOpenDocuments:
    its folder and file name) with the pads `pads` (KIIDs) and the footprints `footprints` (references) selected
    (GetSelection); GetVersion answers `version`; RefillZones and Ping answer Empty; SaveDocument writes `save` into
    `board` when given, as KiCad's save writes the edits it holds, and answers Empty. `errors` maps a request's type
    name to what it answers first, one per request: an AS_ status name, or "SLOW", its usual answer SLOW_S late, as
    KiCad answers once its main thread is free of a zone fill or a large save. `seen` lists the requests' type names
    in order, and `tokens` the tokens they carried."""

    def __init__(self, url: str, board: Path, *, pads=(), footprints=(), version=(9, 0, 7), token="K",
                 errors: dict | None = None, save: bytes | None = None):
        self.url, self.board, self.pads, self.footprints = url, Path(board), list(pads), list(footprints)
        self.version, self.token, self.save = version, token, save
        self.errors = {kind: list(names) for kind, names in (errors or {}).items()}
        self.seen, self.tokens = [], []
        self.socket = pynng.Rep0(listen=url)
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self) -> None:
        while True:
            try:
                request = ApiRequest.FromString(self.socket.recv())
                self.socket.send(self.answer(request).SerializeToString())
            except pynng.exceptions.NNGException:  # closed (close())
                return

    def answer(self, request: ApiRequest) -> ApiResponse:
        kind = request.message.TypeName().rsplit(".", 1)[-1]
        self.seen.append(kind)
        self.tokens.append(request.header.kicad_token)
        first = self.errors[kind].pop(0) if self.errors.get(kind) else "AS_OK"
        reply = ApiResponse()
        reply.header.kicad_token = self.token
        if request.header.kicad_token not in ("", self.token):
            reply.status.status = ApiStatusCode.AS_TOKEN_MISMATCH
        elif first not in ("AS_OK", "SLOW"):
            reply.status.status = ApiStatusCode.Value(first)
        else:
            if first == "SLOW":
                time.sleep(SLOW_S)
            reply.status.status = ApiStatusCode.AS_OK
            reply.message.Pack(self.response(kind))
        return reply

    def response(self, kind: str):
        if kind == "GetVersion":
            major, minor, patch = self.version
            return base_commands_pb2.GetVersionResponse(version=base_types_pb2.KiCadVersion(
                major=major, minor=minor, patch=patch, full_version=f"{major}.{minor}.{patch}"))
        if kind == "GetOpenDocuments":
            doc = base_types_pb2.DocumentSpecifier(type=base_types_pb2.DOCTYPE_PCB, board_filename=self.board.name)
            doc.project.name, doc.project.path = self.board.stem, str(self.board.parent)
            return editor_commands_pb2.GetOpenDocumentsResponse(documents=[doc])
        if kind == "GetSelection":
            items = []
            for kiid in self.pads:
                pad = board_types_pb2.Pad()
                pad.id.value = kiid
                items.append(pack_any(pad))
            for ref in self.footprints:
                footprint = board_types_pb2.FootprintInstance()
                footprint.reference_field.text.text.text = ref
                items.append(pack_any(footprint))
            return editor_commands_pb2.SelectionResponse(items=items)
        if kind == "SaveDocument" and self.save is not None:
            self.board.write_bytes(self.save)
        return Empty()  # Ping, RefillZones and SaveDocument

    def close(self) -> None:
        self.socket.close()
        self.thread.join(timeout=5)
```

  In `tests/conftest.py`, after `ctrl_c_on_third_poll`:

```python
@pytest.fixture(autouse=True)
def no_kicad(tmp_path, monkeypatch):
    """No test reaches a real KiCad (Stage 2 design 3): KiCad's documents and settings folders are under tmp_path, and
    its API socket is one no KiCad listens on, since kipy's default would be the KiCad the owner has open. A test that
    needs other values sets them."""
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path / "documents"))
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("KICAD_API_SOCKET", f"ipc://{tmp_path / 'no-kicad.sock'}")
    monkeypatch.delenv("KICAD_API_TOKEN", raising=False)


@pytest.fixture
def kicad(tmp_path):
    """Fake KiCad API servers (tests/fake_kicad.py), each at its own ipc address under tmp_path, with lpf915 open
    unless another board is given; closed at teardown."""
    from fake_kicad import FakeKiCad  # here: kipy and pynng load only in the tests that use it
    made = []

    def make(board=Path(__file__).with_name("fixtures") / "lpf915.kicad_pcb", **kw):
        made.append(FakeKiCad(f"ipc://{tmp_path / f'api{len(made)}.sock'}", board, **kw))
        return made[-1]

    yield make
    for server in made:
        server.close()
```

- [ ] **Step 2: Check the transport once, before any test.** Save this outside the repo (for example as `krs-fake-check.py` in `$env:TEMP`; never committed) and run it from the repo root with `.venv/Scripts/python -I FILE`:

```python
# krs-fake-check.py: a one-off check that kipy's client reaches the fake KiCad (Stage 2 plan 3, Task 2), never committed
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "tests"))
from fake_kicad import FakeKiCad  # noqa: E402
from kipy import KiCad  # noqa: E402

k = FakeKiCad(f"ipc://{Path(tempfile.mkdtemp()) / 'api.sock'}", Path.cwd() / "tests" / "fixtures" / "lpf915.kicad_pcb",
              pads=["a", "b"])
client = KiCad(socket_path=k.url, kicad_token=k.token, timeout_ms=1000)
board = client.get_board()
print(client.get_version().major, board.document.board_filename, [p.id.value for p in board.get_selection()])
k.close()
```

  Expected: `9 lpf915.kicad_pcb ['a', 'b']`. A failure here is the transport's (the `ipc://` form of a Windows path, pynng), not the helper's: fix the fake first.
- [ ] **Step 3: Write the failing tests.** `tests/test_button.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""The KiCad button (Stage 2 design 5.5, 5.8): the helper KiCad runs, its handoff and its quiet contract, a run
outliving KiCad's job, the plugin that install-kicad-plugin writes, and refill and save. KiCad is
tests/fake_kicad.py."""
import contextlib
import ctypes
import json
import os
import signal
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import pytest

from kicad_rf_studio import button, runs
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.messages import CATALOG, render
from test_cli_cost import FIX
from test_gui_control import recorder, until

LPF = FIX / "lpf915.kicad_pcb"
KIID = {p.name: p.uuid for p in load_board(LPF).all_pads()}  # J1.2 is two pads: never selected here
HELPER_CODES = ("E_KICAD_UNREACHABLE", "E_KICAD_BUSY", "E_KICAD_UNSUPPORTED", "E_KICAD_VERSION", "E_KICAD_NO_BOARD",
                "E_HANDOFF_WRITE", "E_GUI_START", "E_INTERNAL")


def gui_python() -> str:
    """The Python a stand-in GUI runs on: pythonw beside this one on Windows, which opens no console when started
    detached."""
    return str(Path(sys.executable).with_name("pythonw.exe")) if sys.platform == "win32" else sys.executable


def test_the_helper_hands_the_selection_to_a_detached_gui_and_prints_nothing(fake, kicad, monkeypatch, capsys):
    # design 5.5 steps 1-5; 10.0.7 is newer than kipy 0.8.0's 10.0.6, which check_version() would refuse
    k = kicad(pads=[KIID["J1.1"], KIID["U1.1"]], footprints=["C1"], version=(10, 0, 7),
              errors={"GetSelection": ["AS_BUSY"]})
    monkeypatch.setenv("KICAD_API_SOCKET", k.url)
    monkeypatch.setenv("KICAD_API_TOKEN", k.token)
    calls = recorder(monkeypatch)
    assert button.main() == 0
    assert capsys.readouterr() == ("", "")  # KiCad 10 shows any stderr text as an error
    handoff = fake / "handoff.json"
    assert json.loads(handoff.read_text(encoding="utf-8")) == {
        "board": str(LPF), "pads": [KIID["J1.1"], KIID["U1.1"]], "footprints": ["C1"], "kicad": "10.0.7",
        "socket": k.url, "token": k.token}
    assert k.seen == ["GetVersion", "GetOpenDocuments", "GetSelection", "GetSelection"]  # AS_BUSY: asked again
    assert set(k.tokens) == {k.token} and not (fake / "button.log").exists()
    name = "kicad-rf-studio-gui.exe" if sys.platform == "win32" else "kicad-rf-studio-gui"
    (call,) = calls
    assert call.args == button.gui_command(handoff) == [
        str(Path(sysconfig.get_path("scripts"), name)), "--handoff", str(handoff)]  # this environment's, not PATH's
    assert (call.stdin, call.stdout, call.cwd) == (subprocess.DEVNULL, subprocess.DEVNULL, fake)
    assert Path(call.stderr.name) == fake / "gui.log"  # its tracebacks: pythonw on a null stderr would lose them
    if sys.platform == "win32":
        assert call.creationflags == subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # design 5.5's
    else:
        assert call.start_new_session is True


@pytest.mark.parametrize(("serve", "token", "code", "params"), [
    ({"errors": {"GetVersion": ["AS_BUSY"] * 4}}, None, "E_KICAD_BUSY", {}),  # still busy when its 1 s is up
    ({"errors": {kind: ["AS_BUSY"] * 3 for kind in ("GetVersion", "GetOpenDocuments", "GetSelection")}}, None,
     "E_KICAD_BUSY", {}),  # one 1 s for the whole press, not one for each call: about 2 s in all (design 5.5)
    ({"errors": {"GetSelection": ["AS_UNHANDLED"]}}, None, "E_KICAD_UNSUPPORTED", {}),  # not in this KiCad
    ({"errors": {"GetOpenDocuments": ["AS_UNIMPLEMENTED"]}}, None, "E_KICAD_UNSUPPORTED", {}),
    ({"version": (8, 0, 9)}, None, "E_KICAD_VERSION", {"version": "8.0.9"}),
    ({"version": (11, 0, 0)}, None, "E_KICAD_VERSION", {"version": "11.0.0"}),
    ({"board": Path("")}, None, "E_KICAD_NO_BOARD", {}),  # a new board KiCad never saved has no file name
    ({}, "another KiCad's", "E_KICAD_UNREACHABLE", {}),  # AS_TOKEN_MISMATCH: KiCad restarted since
    (None, None, "E_KICAD_UNREACHABLE", {}),  # no API server at the socket
    ({"errors": {"GetSelection": ["AS_BAD_REQUEST"]}}, None, "E_INTERNAL",
     {"detail": "ApiError: KiCad returned error:"})])
def test_the_helper_says_why_on_one_stderr_line_and_in_button_log_and_starts_nothing(
        fake, kicad, tmp_path, monkeypatch, capsys, serve, token, code, params):  # design 5.5; Review Focus 4
    k = None if serve is None else kicad(**serve)
    monkeypatch.setenv("KICAD_API_SOCKET", k.url if k else f"ipc://{tmp_path / 'none.sock'}")
    monkeypatch.setenv("KICAD_API_TOKEN", token or (k.token if k else ""))
    calls = recorder(monkeypatch)
    assert button.main() == 1
    line = render(code, **params)
    assert capsys.readouterr() == ("", line + "\n")
    assert (fake / "button.log").read_text(encoding="utf-8").splitlines()[-1].endswith(" " + line)
    assert calls == [] and not (fake / "handoff.json").exists()


def test_a_handoff_that_cannot_be_written_or_a_gui_that_cannot_start_is_its_own_line(fake, kicad, monkeypatch,
                                                                                     capsys):  # design 5.5
    assert all(CATALOG[c].isascii() for c in HELPER_CODES)  # KiCad 10 decodes stderr in a code page nobody can check
    k = kicad()
    monkeypatch.setenv("KICAD_API_SOCKET", k.url)
    monkeypatch.setenv("KICAD_API_TOKEN", k.token)
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text("")  # a file where the data folder goes
    assert button.main() == 1
    assert capsys.readouterr().err == render("E_HANDOFF_WRITE", path=str(fake / "handoff.json"),
                                             reason="already exists as a file") + "\n"
    fake.unlink()
    missing = fake / "no-gui"
    monkeypatch.setattr(button, "gui_command", lambda handoff: [str(missing), "--handoff", str(handoff)])
    assert button.main() == 1
    assert capsys.readouterr().err == render("E_GUI_START", program=str(missing), reason="file not found") + "\n"


def test_run_as_kicad_10_runs_it_the_helper_ends_quickly_says_nothing_and_its_gui_holds_no_pipe(kicad, tmp_path):
    # design 5.5's output contract, 4 and 5.8 (no Qt in the helper, when run), 5.11 item 3; Review Focus 3, 4
    k = kicad(pads=[KIID["U1.1"], KIID["J1.1"]])
    stand_in = tmp_path / "gui.py"  # the GUI's stand-in: says how it was started, then runs on
    stand_in.write_text(
        "import json, os, sys, time\n"
        "with open(os.environ['KRS_FAKE_GUI'] + '.tmp', 'w') as out:\n"
        "    json.dump({'argv': sys.argv[1:], 'pid': os.getpid()}, out)\n"
        "os.replace(os.environ['KRS_FAKE_GUI'] + '.tmp', os.environ['KRS_FAKE_GUI'])\n"
        "time.sleep(10)\n", encoding="utf-8")
    helper = ("import sys; from kicad_rf_studio import button; button.gui_command = lambda handoff: "
              f"[{gui_python()!r}, '-I', {str(stand_in)!r}, '--handoff', str(handoff)]; rc = button.main(); "
              "assert not {'PySide6', 'shiboken6', 'matplotlib'} & {m.split('.')[0] for m in sys.modules}; "
              "sys.exit(rc)")
    local, started = tmp_path / "local", tmp_path / "gui.json"
    env = {**os.environ, "KICAD_API_SOCKET": k.url, "KICAD_API_TOKEN": k.token, "LOCALAPPDATA": str(local),
           "XDG_DATA_HOME": str(local), "KRS_FAKE_GUI": str(started)}
    begin = time.monotonic()
    out = subprocess.run([sys.executable, "-X", "utf8", "-I", "-c", helper], capture_output=True, env=env, timeout=60)
    took = time.monotonic() - begin
    assert (out.returncode, out.stdout, out.stderr) == (0, b"", b"")
    assert took < 5.0  # had the GUI kept the pipes, they would close only at its end, 10 s on
    until(started.exists)
    gui = json.loads(started.read_text(encoding="utf-8"))
    try:
        assert gui["argv"] == ["--handoff", str(local / "kicad-rf-studio" / "handoff.json")]
        assert runs._alive(gui["pid"])  # detached: it outlives the helper
    finally:
        with contextlib.suppress(OSError):
            os.kill(gui["pid"], signal.SIGTERM)


KICAD_JOB = r'''
import ctypes, sys
from pathlib import Path
from kicad_rf_studio.gui import control
k32 = ctypes.WinDLL("kernel32")
k32.OpenJobObjectW.restype = ctypes.c_void_p
job = ctypes.c_void_p(k32.OpenJobObjectW(0x1F001F, False, sys.argv[1]))  # JOB_OBJECT_ALL_ACCESS
assert job.value and k32.AssignProcessToJobObject(job, ctypes.c_void_p(-1))  # this process: a GUI in KiCad's job
folder = Path(sys.argv[2])
run = control.start([sys.executable, "-I", "-c", "import time; time.sleep(30)"], "run", folder / "project.json",
                    folder / "run")
k32.CloseHandle(job)
print(run.pid)
'''


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job objects")
def test_a_run_the_gui_starts_inside_a_kicad_job_that_kills_on_close_outlives_it(tmp_path):
    # design 3 (a lost run) and plan 1's carry-over: the GUI stays in any job KiCad runs its actions in, but the runs
    # it starts leave it (control.start's breakaway), so they outlive KiCad; Review Focus 3
    k32 = ctypes.WinDLL("kernel32")
    k32.CreateJobObjectW.restype = ctypes.c_void_p  # a HANDLE, which the default int would cut to 32 bits
    name = f"Local\\krs-test-job-{os.getpid()}"
    job = ctypes.c_void_p(k32.CreateJobObjectW(None, name))
    info = (ctypes.c_ulonglong * 18)()  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION (x64), as runs._job_object builds it
    info[2] = 0x2000 | 0x800  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
    assert k32.SetInformationJobObject(job, 9, info, ctypes.sizeof(info))
    out = subprocess.run([sys.executable, "-I", "-c", KICAD_JOB, name, str(tmp_path)], capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    pid = int(out.stdout)
    try:
        k32.CloseHandle(job)  # KiCad closes: its job kills every process still in it
        time.sleep(0.5)
        assert runs._alive(pid)  # out of KiCad's job, so the run outlives KiCad
    finally:
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGTERM)
```

  In `tests/test_gui.py`, `QT_FREE` gains `"kicad_rf_studio.button"`: importing the helper loads no Qt, kipy or matplotlib.
- [ ] **Step 4: Run them.** `.venv/Scripts/python -m pytest tests/test_button.py tests/test_gui.py -q`. Expected: FAIL at test_button's collection with `ImportError: cannot import name 'button' from 'kicad_rf_studio'`, and the `QT_FREE` probe failing with `ModuleNotFoundError: No module named 'kicad_rf_studio.button'`.
- [ ] **Step 5: Implement** `button.py` and the catalog codes, as Interfaces say.
  - The module docstring: "The KiCad toolbar button (Stage 2 design 5.5): the helper KiCad's exec action runs (main), which reads the board and the selection through kicad-python and hands them to the GUI. Qt-free; kicad-python is imported only inside the functions that call KiCad, so importing this module loads none."
  - `_call` carries `# ponytail: one 1 s for AS_BUSY over the whole press (the helper must end within about 2 s), and each answer may take TIMEOUT_MS, so three answers just under it take about 3 s; a longer budget if KiCad is seen busy or slow at a click`.
  - `start_gui` carries `# ponytail: no CREATE_BREAKAWAY_FROM_JOB: in a KiCad job that kills on close the window closes with KiCad, though its runs break away (control.start); add it, with control.start's PermissionError fallback, if the click-through shows such a job`.
  - `write_handoff` carries `# ponytail: one fixed file, the latest press winning, through save_project's one temporary name: two presses within one write, or a press while the window reads it (Windows then refuses the replace), end in E_HANDOFF_WRITE and the user presses again; a file per press if users meet it`.
  - `main`'s log write carries `# ponytail: button.log only grows, one line per failed press; a size cap if it ever matters`.
  - `read`'s kipy imports: `from kipy.board_types import FootprintInstance, Pad` and `from kipy.proto.common.types import KiCadObjectType`; `_call`'s: `import kipy.errors` and `from kipy.proto.common import ApiStatusCode` (kipy's `ConnectionError` shadows the builtin: name it `kipy.errors.ConnectionError`).
- [ ] **Step 6: Run them again.** Same command. Expected: PASS. The KiCad-job test (Windows) pins plan 1's `control.start`, which already breaks away; it fails if that flag goes.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/button.py src/kicad_rf_studio/core/messages.py tests/fake_kicad.py tests/conftest.py tests/test_button.py tests/test_gui.py
git commit -m "feat(button): the Qt-free helper KiCad runs hands the board and the selection to a detached GUI, saying nothing (Stage 2 design 5.5, 5.8)"
graphify update .
```

---

### Task 3 [code]: `install-kicad-plugin` for KiCad 9.0 and 10.x

**Files:**
- Modify:
  - `src/kicad_rf_studio/button.py` (the installer, after `main`, before the `__main__` guard);
  - `src/kicad_rf_studio/cli.py` (its docstring, L2–16; `_install_kicad_plugin` after `_calibrate`, L194–198; the parser in `_parser`, L201–238);
  - `src/kicad_rf_studio/core/messages.py`;
  - `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (§3.2's table, after the `calibrate` row, L116; the Status line).
- Test: `tests/test_button.py` (imports `re`, `shutil`, `stat`, `KrsError` beside `CATALOG` and `render`, and `from kicad_rf_studio.cli import main`).

**Interfaces:**
- Consumes: Task 2's module and its helper; `render`, `reason`, `KrsError`; `G_APP` ("kicad-rf-studio").
- Produces, in `kicad_rf_studio.button`:
  - `IDENTIFIER = "org.kicadrfstudio.app"` (design §7's default; the owner's final one is tied to the account), `FOLDER = "kicad-rf-studio"`, `VERSIONS = ("9.0", "10.0")` (KiCad's major.minor folders), `SIZES = (24, 48)`, `ICONS = {"light": (0x33, 0x33, 0x33), "dark": (0xDD, 0xDD, 0xDD)}` (the glyph's colour by theme).
  - `documents() -> Path`, KiCad's `getUserDocumentPath` base: `KICAD_DOCUMENTS_HOME` when set; else on Windows the shell's Documents folder, `ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer)` (CSIDL_PERSONAL, a `create_unicode_buffer(260)`; it follows a OneDrive redirect), an HRESULT other than 0 raising `OSError`; elsewhere `XDG_DATA_HOME`, else `~/.local/share`, expanded.
  - `plugin_folders(version: str | None) -> list[Path]`: `documents() / ("KiCad" if Windows else "kicad") / v / "plugins" / FOLDER` for `v` the given version, else for each of `VERSIONS` whose version folder exists.
  - `plugin_json(entrypoint: str) -> dict`: exactly the dict that `test_the_plugin_passes_kicads_schema_and_both_identifier_rules_and_its_icons_are_pngs` asserts, its names and descriptions rendered from `G_APP`, `G_BUTTON_PLUGIN` and `G_BUTTON_ACTION`.
  - `launcher(python: str, windows: bool) -> str`, with `\n` line ends:
    - Windows: `'@echo off\nsetlocal DisableDelayedExpansion\n"' + python.replace("%", "%%") + '" -X utf8 -I -m kicad_rf_studio.button %*\n'` (a batch file expands `%` even inside quotes, and a registry-set DelayedExpansion would eat a `!`);
    - else: `"#!/bin/sh\nexec '" + python.replace("'", "'\\''") + "' -X utf8 -I -m kicad_rf_studio.button \"$@\"\n"`.
  - `_png(size: int, rgb: tuple[int, int, int]) -> bytes`: a standard RGBA PNG drawn with `zlib` and `struct` (the signature, IHDR, one IDAT of filter-0 rows, IEND, each chunk with its CRC-32): a ring of radius `0.42 * size` and stroke `size / 12` about the centre `(size - 1) / 2`, and its horizontal diameter (a Smith chart's outline), opaque `rgb` on a transparent ground. The test pins the size, a transparent corner, a transparent point inside the ring off the diameter, and the opaque centre.
  - `install(version: str | None = None, remove: bool = False) -> list[tuple[str, dict]]`, the notes the CLI prints:
    - `remove`: deletes each of `plugin_folders(version)` that exists (`shutil.rmtree`), and nothing else, an OSError on the way being `E_PLUGIN_WRITE {path: that folder, reason: reason(e, "cannot be written")}`; `[("I_PLUGIN_REMOVED", {"folder"})...]`, or `[("I_PLUGIN_NONE", {"folder": str(the KiCad|kicad folder)})]` when none was there.
    - Otherwise: `E_NO_KICAD_FOLDER {folder: the KiCad|kicad folder}` without a folder. Each folder gets, made with its parents: `plugin.json` (`json.dumps(plugin_json(entry), indent=2) + "\n"`, UTF-8), the launcher `entry` (`launch.cmd` on Windows, its text's line ends CRLF, encoded `"oem"`, the code page cmd.exe reads a batch file in; `launch.sh` elsewhere, UTF-8, then `chmod 0o755`) and `icon-{theme}-{size}.png` for each theme of `ICONS` and each of `SIZES`. The launcher's Python is `os.path.abspath(sys.executable)`, never resolved (on Linux a venv's python is a symlink out of the venv). Its bytes are made before anything is written, so a `UnicodeEncodeError` is `E_PLUGIN_PYTHON {python}` with nothing written; any OSError is `E_PLUGIN_WRITE {path: the folder, reason: reason(e, "cannot be written")}`. Returns `I_PLUGIN_INSTALLED {folder}` per folder, then `I_PLUGIN_NEXT`.
  - `cli`: `install-kicad-plugin [--kicad {9.0,10.0}] [--remove]` (`choices=("9.0", "10.0")`, `action="store_true"`), its handler `_install_kicad_plugin(a)` importing `button` inside itself (the CLI adds no work at import time) and printing `render(code, **params)` for each of `button.install(a.kicad, a.remove)`.
  - CATALOG (exact texts):
    - `"G_BUTTON_PLUGIN": "Simulates the RF parts of a KiCad board with openEMS."`
    - `"G_BUTTON_ACTION": "Opens kicad-rf-studio on this board, with the selected pads as the chain's start and end."`
    - `"I_PLUGIN_INSTALLED": "Installed the kicad-rf-studio button in {folder}."`
    - `"I_PLUGIN_NEXT": "One step is left, in KiCad: Preferences › Plugins › Enable KiCad API, then restart KiCad. The button then shows in the PCB editor's toolbar."`
    - `"I_PLUGIN_REMOVED": "Removed the kicad-rf-studio button from {folder}."`
    - `"I_PLUGIN_NONE": "There is no kicad-rf-studio button to remove under {folder}."`
    - `"E_NO_KICAD_FOLDER": "No KiCad 9.0 or 10.0 folder in {folder}: start KiCad once, so that it makes its folder there, or name the version with --kicad 9.0 or --kicad 10.0."`
    - `"E_PLUGIN_WRITE": "Cannot write or remove the kicad-rf-studio button in {path}: {reason}. Check that this folder can be written (Windows' Controlled folder access can block it), then run install-kicad-plugin again."`
    - `"E_PLUGIN_PYTHON": "This Python's path, {python}, has a character that launch.cmd cannot hold in the console's code page. Install kicad-rf-studio in a folder whose path has none, then run install-kicad-plugin again."`

- [ ] **Step 1: Write the failing tests,** in `tests/test_button.py`:

```python
SEGMENT = "KiCad" if sys.platform == "win32" else "kicad"  # KiCad's own name for its documents folder
LAUNCHER = "launch.cmd" if sys.platform == "win32" else "launch.sh"
FILES = sorted(["plugin.json", LAUNCHER, "icon-dark-24.png", "icon-dark-48.png", "icon-light-24.png",
                "icon-light-48.png"])


def test_install_kicad_plugin_writes_each_kicad_folder_and_nothing_else(tmp_path, monkeypatch, capsys):
    docs = tmp_path / "Documentos do Zé"  # design 3, 5.5; A-17; a space and an accent, as a Documents path may have
    home, config = docs / SEGMENT, tmp_path / "config"
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(docs))
    for name in ("KICAD_CONFIG_HOME", "APPDATA", "XDG_CONFIG_HOME"):  # every place KiCad 9 and 10 read settings from
        monkeypatch.setenv(name, str(config))
    assert main(["install-kicad-plugin"]) == 2  # no KiCad started here yet
    assert capsys.readouterr().err == render("E_NO_KICAD_FOLDER", folder=str(home)) + "\n"
    settings = [config / v / "kicad_common.json" for v in ("9.0", "10.0")] + [
        config / "kicad" / v / "kicad_common.json" for v in ("9.0", "10.0")]  # KICAD_CONFIG_HOME's; APPDATA's, XDG's
    for f, text in [(s, '{"api": {"enable_server": false}}') for s in settings] + [
            (home / "9.0" / "plugins" / "other" / "plugin.json", "{}"), (home / "10.0" / "fp-lib-table", "()")]:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert main(["install-kicad-plugin"]) == 0
    folders = [home / v / "plugins" / "kicad-rf-studio" for v in ("9.0", "10.0")]
    assert capsys.readouterr().out.splitlines() == [render("I_PLUGIN_INSTALLED", folder=str(f)) for f in folders] + [
        render("I_PLUGIN_NEXT")]
    assert [sorted(p.name for p in f.iterdir()) for f in folders] == [FILES, FILES]
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert {p: after[p] for p in before} == before  # KiCad's settings and other plugins untouched
    assert {p.parent for p in after.keys() - before.keys()} == set(folders)  # only its own folders written
    assert main(["install-kicad-plugin", "--remove"]) == 0  # every version's
    assert capsys.readouterr().out.splitlines() == [render("I_PLUGIN_REMOVED", folder=str(f)) for f in folders]
    assert not any(f.exists() for f in folders) and (home / "9.0" / "plugins" / "other").is_dir()
    assert main(["install-kicad-plugin", "--remove", "--kicad", "9.0"]) == 0
    assert capsys.readouterr().out.splitlines() == [render("I_PLUGIN_NONE", folder=str(home))]
    folders[1].write_text("")  # a file where the plugin's folder goes
    assert main(["install-kicad-plugin", "--kicad", "10.0"]) == 2
    assert capsys.readouterr().err == render("E_PLUGIN_WRITE", path=str(folders[1]),
                                             reason="already exists as a file") + "\n"
    folders[1].unlink()
    shutil.rmtree(home / "10.0")
    assert main(["install-kicad-plugin", "--kicad", "10.0"]) == 0  # a version named is written, its folder made
    assert sorted(p.name for p in folders[1].iterdir()) == FILES and not folders[0].exists()


def test_the_plugin_passes_kicads_schema_and_both_identifier_rules_and_its_icons_are_pngs(tmp_path, monkeypatch,
                                                                                         qapp):  # design 5.5, 5.8
    from kipy.packaging.validate import validate_plugin
    from PySide6.QtGui import QColor, QImage
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path))
    folder = tmp_path / SEGMENT / "10.0" / "plugins" / "kicad-rf-studio"
    assert button.install("10.0") == [("I_PLUGIN_INSTALLED", {"folder": str(folder)}), ("I_PLUGIN_NEXT", {})]
    assert validate_plugin(folder).errors == []  # kipy's bundled schema, $schema, the entrypoint and the icons
    assert json.loads((folder / "plugin.json").read_text(encoding="utf-8")) == button.plugin_json(LAUNCHER) == {
        "$schema": "https://go.kicad.org/api/schemas/v1", "identifier": "org.kicadrfstudio.app",
        "name": "kicad-rf-studio", "description": render("G_BUTTON_PLUGIN"), "runtime": {"type": "exec"},
        "actions": [{"identifier": "open", "name": "kicad-rf-studio", "description": render("G_BUTTON_ACTION"),
                     "show-button": True, "scopes": ["pcb"], "entrypoint": LAUNCHER,
                     "icons-light": ["icon-light-24.png", "icon-light-48.png"],
                     "icons-dark": ["icon-dark-24.png", "icon-dark-48.png"]}]}
    nine = r"[\w\d]{2,}\.[\w\d]+\.[\w\d]+"  # KiCad 9.0.7's IsValidIdentifier, unanchored
    ten = r"[a-zA-Z]{2,}(\.([a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]|[a-zA-Z0-9])){2,}"  # 10.0.7's, anchored
    assert re.search(nine, button.IDENTIFIER) and re.fullmatch(ten, button.IDENTIFIER)
    assert re.fullmatch(r"[A-Za-z]+(\.[A-Za-z0-9]+){2,}", button.IDENTIFIER)  # design 5.5's own rule, the owner's too
    for theme, rgb in button.ICONS.items():
        for size in button.SIZES:
            image = QImage(str(folder / f"icon-{theme}-{size}.png"))
            assert (image.width(), image.height()) == (size, size)
            assert image.pixelColor(0, 0).alpha() == 0 and image.pixelColor(size // 2, size // 4).alpha() == 0
            assert image.pixelColor(size // 2, size // 2) == QColor(*rgb)  # on the diameter, opaque


def test_kicads_documents_folder_is_its_own_choice_a_onedrive_redirect_included(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path))  # design 5.5 Install; Review Focus 5
    assert button.documents() == tmp_path
    monkeypatch.delenv("KICAD_DOCUMENTS_HOME")
    if sys.platform == "win32":  # the shell's Documents folder, as .NET reads it: its path only, never the folder
        shell = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding = "
                                "[Text.Encoding]::UTF8; [Environment]::GetFolderPath('MyDocuments')"],
                               capture_output=True, encoding="utf-8", timeout=60)
        assert button.documents() == Path(shell.stdout.strip())
    else:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        assert button.documents() == tmp_path / "xdg"
        monkeypatch.delenv("XDG_DATA_HOME")
        assert button.documents() == Path("~/.local/share").expanduser()


def test_the_launcher_quotes_this_pythons_absolute_path_for_its_shell():  # design 5.5 Launcher; Review Focus 5
    assert button.launcher("Zé Silva/100%/hi!/python.exe", windows=True) == (
        '@echo off\nsetlocal DisableDelayedExpansion\n"Zé Silva/100%%/hi!/python.exe" -X utf8 -I -m '
        'kicad_rf_studio.button %*\n')
    assert button.launcher("venvs/o'neil/bin/python", windows=False) == (
        "#!/bin/sh\nexec 'venvs/o'\\''neil/bin/python' -X utf8 -I -m kicad_rf_studio.button \"$@\"\n")


def test_the_installed_launcher_runs_the_helper_and_passes_its_line_and_exit_code(tmp_path, monkeypatch):
    docs = tmp_path / "Documentos do Zé"  # design 5.5, 5.11 item 3: KiCad runs the entrypoint in its folder
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(docs))
    install = ("import sys; from kicad_rf_studio.cli import main; rc = main(['install-kicad-plugin', '--kicad', "
               "'10.0']); assert not {'PySide6', 'shiboken6', 'kipy'} & {m.split('.')[0] for m in sys.modules}; "
               "sys.exit(rc)")
    out = subprocess.run([sys.executable, "-I", "-c", install], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr  # design 4: install-kicad-plugin, run, loads neither Qt nor kicad-python
    folder = docs / SEGMENT / "10.0" / "plugins" / "kicad-rf-studio"
    text = button.launcher(os.path.abspath(sys.executable), sys.platform == "win32")
    if sys.platform == "win32":
        assert (folder / LAUNCHER).read_bytes() == text.replace("\n", "\r\n").encode("oem")
    else:
        assert (folder / LAUNCHER).read_text(encoding="utf-8") == text
        assert stat.S_IMODE((folder / LAUNCHER).stat().st_mode) == 0o755
    local = tmp_path / "local"
    env = {**os.environ, "KICAD_API_SOCKET": f"ipc://{tmp_path / 'none.sock'}", "KICAD_API_TOKEN": "",
           "LOCALAPPDATA": str(local), "XDG_DATA_HOME": str(local)}
    out = subprocess.run([str(folder / LAUNCHER)], cwd=folder, env=env, capture_output=True, timeout=60)
    assert (out.returncode, out.stdout) == (1, b"")
    assert out.stderr.decode("utf-8").splitlines() == [render("E_KICAD_UNREACHABLE")]  # the helper's, through cmd or sh
    assert (local / "kicad-rf-studio" / "button.log").read_text(encoding="utf-8").endswith(
        " " + render("E_KICAD_UNREACHABLE") + "\n")


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe reads launch.cmd in the console's code page")
def test_a_python_path_launch_cmd_cannot_hold_is_refused(tmp_path, monkeypatch):  # Review Focus 5
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path))
    python = str(tmp_path / "venv\U0001F642" / "Scripts" / "python.exe")  # in no code page
    monkeypatch.setattr(sys, "executable", python)
    with pytest.raises(KrsError) as e:
        button.install("9.0")
    assert (e.value.code, e.value.params) == ("E_PLUGIN_PYTHON", {"python": python})
    assert not (tmp_path / SEGMENT / "9.0" / "plugins" / "kicad-rf-studio").exists()  # nothing written
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_button.py -q`. Expected: FAIL: `SystemExit: 2` from argparse, which does not know `install-kicad-plugin` yet, and `AttributeError: module 'kicad_rf_studio.button' has no attribute 'install'`.
- [ ] **Step 3: Implement** the Interfaces, the catalog codes and the CLI.
  - `cli.py`'s docstring gains: "`install-kicad-plugin` writes the KiCad toolbar button (button.install) into KiCad's plugin folders, or removes it."
  - `install` carries `# ponytail: KiCad's 9.0 and 10.0 folders only; a KiCad 10.1 makes a 10.1 folder, which VERSIONS then needs. --remove leaves the version and plugins folders, which KiCad makes anyway`.
  - The launcher write carries `# ponytail: a Python path outside the console's code page is refused; its 8.3 short path (GetShortPathNameW) if users meet it`.
- [ ] **Step 4: The spec.**
  - §3.2's table gains, after the `calibrate` row: "| `kicad-rf-studio install-kicad-plugin [--kicad 9.0\|10.0] [--remove]` | Writes the KiCad toolbar button, an exec plugin (`plugin.json`, a launcher holding this environment's Python, and its icons), into `plugins/kicad-rf-studio` of each KiCad 9.0 and 10.0 documents folder that exists, honouring KICAD_DOCUMENTS_HOME, or of the one named; `--remove` deletes it. It never edits KiCad's settings, and prints the one step left: turn on the KiCad API under Preferences › Plugins, then restart KiCad. (A-17, Stage 2 plan 3: controller recommendation, owner unavailable.) |"
  - The Status sentence of Task 1 becomes " On 2026-10-28, Stage 2's plan 3 amended §3.2 and §3.4 (A-16 and A-17) the same way."
- [ ] **Step 5: Run them again.** `.venv/Scripts/python -m pytest tests/test_button.py tests/test_run_dir.py -q` (test_run_dir drives `cli.main`'s other commands). Expected: PASS (the Windows-only tests skipped on Linux).
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/button.py src/kicad_rf_studio/cli.py src/kicad_rf_studio/core/messages.py tests/test_button.py docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "feat(button): install-kicad-plugin writes the exec plugin for KiCad 9.0 and 10.x, checked against KiCad's schema and both identifier rules; spec A-17 (Stage 2 design 5.5; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 4 [code]: New pre-filled from a button press, with Swap

**Files:**
- Modify:
  - `src/kicad_rf_studio/gui/control.py` (imports `classify` beside `load_board`; `Handed`, `handed` and `_names` after `pads`, L381–387, which `_names` now serves);
  - `src/kicad_rf_studio/gui/window.py`:
    - `NewForm`: `swap_button` in the end row (L286), `swap()`;
    - `MainWindow`: `__init__` (L359–362, the new state), the new `take_handoff`, and `show_pads` (L770–783), which takes a press too;
  - `src/kicad_rf_studio/core/messages.py`.
- Test: `tests/test_gui_control.py` (imports `button` beside `pipeline` and `runs`, and `from kicad_rf_studio.core.kicad import load_board`); `tests/test_gui.py` (`button` beside `gui`; `from test_gui_control import FAKE_PREFIX, press, until`).

**Interfaces:**
- Consumes:
  - Task 2's `button.write_handoff` (in tests);
  - `core.kicad.load_board` (`Board.all_pads()`, `Board.footprints`, `Pad.uuid`, `Pad.name`, `Pad.ref`, `Pad.layers`) and `classify(board).connectors`;
  - plan 2's `NewForm` (`board`, `chosen`, `folder`, `start`, `end`, `status`), `MainWindow.board_chosen`, `pads_read`, `show_pads`, `pool`, `tabs` and `tick`.
- Produces:
  - `control._names(pads) -> list[str]`: the names of the pads with copper among `pads`, each once, in natural order (plan 2's rule); `control.pads(board)` becomes `_names(load_board(board).all_pads())`.
  - `control.Handed`, a frozen dataclass: `board: Path`, `socket: str`, `token: str`, `pads: list[str]` (the pickers'), `start: str`, `end: str` ("" for none), `problem: tuple[str, dict] | None` (New's status line).
  - `control.handed(path: Path) -> Handed`, never on the GUI thread: the handoff file `path` (`json.loads`, UTF-8; a file that cannot be read raises, E_INTERNAL in the window) and its board's saved file:
    - `load_board`'s refusal: `Handed(board, socket, token, [], "", "", (code, params))`;
    - a selected KIID missing from the file's pads (all of them, copper or not), or a selected reference missing from `footprints`: KiCad holds edits not yet saved; every pad with copper, nothing pre-filled, `("G_HANDOFF_UNSAVED", {"board": str(board)})`;
    - the pickers: `_names` of the selected footprints' pads and the selected pads when footprints were selected, else every pad with copper;
    - the selected pads with copper, their names each once (`names`): three or more pre-fill nothing, with `("G_HANDOFF_PADS", {"count": len(names)})`; two are start and end, swapped when only the first is a pad of a connector (`classify(...).connectors`), so that the connector's side is the end; one is the start.
    It carries `# ponytail: KiCad's API gives no selection order, so two pads neither of which is a connector's keep the order they came in; Swap fixes it`.
  - `NewForm.swap_button` (G_SWAP), in the end row beside `end`; `NewForm.swap()`, connected in `NewForm.__init__`: start and end exchange their texts (`setCurrentText`).
  - `MainWindow` state: `handoff: Path | None` (the last press taken) and `handed: control.Handed | None` (the last press shown); both None at first.
  - `MainWindow.take_handoff(path: Path)`: `handoff = path`, the Project tab current, New's status cleared, and `pads_read = pool.submit(control.handed, path)`: the press is New's read, which replaces a read in flight, so a slower read of another board never overwrites it, and a board picked after the press wins over it.
  - `MainWindow.show_pads(done: Future)`: plan 2's, whose `done` may now hold a press (a Handed) as well as `control.pads`' names. An exception, and names, as plan 2's. A Handed: `handed` kept; the board field gets `str(handed.board)` and `chosen` the same, or "" when the press has no pads (a refusal: the board, fixed and picked again, is read again, plan 2's F4 rule); the folder `str(handed.board.with_suffix(""))` (as `board_chosen`); each picker is cleared, filled with `handed.pads` and set to `findText` of its pre-fill (`-1` for ""); a problem's line (`control.text`) goes in New's status, which is otherwise left as it is.
  - CATALOG (exact texts):
    - `"G_SWAP": "Swap start and end"`
    - `"G_HANDOFF_UNSAVED": "{board} as saved lacks a pad or a part selected in KiCad, which holds edits not yet saved: save the board in KiCad and press the button again."`
    - `"G_HANDOFF_PADS": "{count} pads are selected in KiCad. Select only the chain's two end pads and press the button again, or pick start and end here."`
  - In tests: `test_gui_control.press(board, pads=(), footprints=(), socket="ipc://s", token="T") -> Path`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_gui_control.py`:

```python
def press(board, pads=(), footprints=(), socket="ipc://s", token="T"):
    """A button press's handoff file (button.write_handoff) for `board`: the pads named REF.PAD by their KIIDs in
    the file (a name the file lacks passes as it is, as a KIID) and the footprints by reference."""
    kiid = {p.name: p.uuid for p in load_board(board).all_pads()}
    return button.write_handoff({"board": str(board), "pads": [kiid.get(n, n) for n in pads],
                                 "footprints": list(footprints), "kicad": "9.0.7", "socket": socket, "token": token})


def test_a_handoff_joins_the_selection_to_the_saved_boards_pads(fake, tmp_path):  # design 5.5; Review Focus 2
    board = FIX / "lpf915.kicad_pcb"
    every = control.pads(board)

    def read(pads=(), footprints=()):
        return control.handed(press(board, pads, footprints))

    assert read(["J1.1", "U1.1"]) == control.Handed(board, "ipc://s", "T", every, "U1.1", "J1.1", None)  # J1: end
    assert (read(["C2.1", "C3.1"]).start, read(["C2.1", "C3.1"]).end) == ("C2.1", "C3.1")  # no connector: as sent
    one, none = read(["C3.1"]), read()
    assert (one.start, one.end, none.start, none.end, none.pads, none.problem) == ("C3.1", "", "", "", every, None)
    narrowed = read(["U1.1"], ["C1", "J1"])  # a footprint narrows the pickers to its pads and the selected ones
    assert (narrowed.pads, narrowed.start, narrowed.problem) == (["C1.1", "C1.2", "J1.1", "J1.2", "U1.1"], "U1.1", None)
    three = read(["C1.1", "C2.1", "C3.1"])
    assert (three.start, three.end, three.problem) == ("", "", ("G_HANDOFF_PADS", {"count": 3}))
    for unsaved in (read(["U1.1", "00000000-0000-0000-0000-000000000001"]), read(footprints=["C9"])):
        assert (unsaved.pads, unsaved.start, unsaved.problem) == (every, "", ("G_HANDOFF_UNSAVED",
                                                                              {"board": str(board)}))
    paste = next(p.uuid for p in load_board(board).all_pads() if not p.layers)  # one of U1's paste-only pads
    assert (read([paste, "C3.1"]).start, read([paste, "C3.1"]).problem) == ("C3.1", None)  # never an end
    nope = tmp_path / "nope.kicad_pcb"
    gone = control.handed(button.write_handoff({"board": str(nope), "pads": [], "footprints": [], "kicad": "9.0.7",
                                                "socket": "ipc://s", "token": "T"}))
    assert (gone.board, gone.pads, gone.problem) == (nope, [], ("E_BOARD_UNREADABLE", {
        "path": str(nope), "reason": "file not found"}))
```

  In `tests/test_gui.py`:

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q`. Expected: FAIL with `AttributeError: module 'kicad_rf_studio.gui.control' has no attribute 'handed'` and `AttributeError: 'MainWindow' object has no attribute 'take_handoff'`; plan 2's New test still passes.
- [ ] **Step 3: Implement** the Interfaces and the codes. `MainWindow`'s docstring adds `handoff` and `handed`, and `pads_read` becomes "the chosen board's pads, or a press (take_handoff)"; `show_pads`' docstring says it takes a press too.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py tests/test_gui_control.py tests/test_gui.py
git commit -m "feat(gui): a button press pre-fills New from KiCad's selection, with Swap (Stage 2 design 5.3, 5.5)"
graphify update .
```

---

### Task 5 [code]: One window per user

**Files:**
- Modify:
  - `src/kicad_rf_studio/gui/__init__.py` (`main`, L10–28; the new `START_WAIT_S`, `instance_name` and `forward`; the docstring);
  - `src/kicad_rf_studio/gui/window.py` (`MainWindow`: `__init__`, the new state; the new `serve`, `incoming`, `forwarded`, `act`; `closeEvent`, L808–814).
- Test: `tests/test_gui.py`.

**Interfaces:**
- Consumes: `runs.data_dir`; Task 4's `take_handoff` and `press`; plan 1's `open_project` and `closeEvent`; QtCore's `QLockFile` (`setStaleLockTime`, `tryLock`, `unlock`); QtNetwork's `QLocalServer` (`listen`, `close`, `setSocketOptions(QLocalServer.SocketOption.UserAccessOption)`, `nextPendingConnection`, `newConnection`, `serverName`, `isListening`) and `QLocalSocket` (`connectToServer`, `waitForConnected`, `write`, `waitForBytesWritten`, `disconnectFromServer`, `waitForDisconnected`, `state`, `canReadLine`, `readLine`, `readyRead`, `disconnected`).
- Produces, in `kicad_rf_studio.gui` (no Qt at import: `main` and `forward` import it inside themselves):
  - `START_WAIT_S = 10.0`: how long a start waits for a window that holds the lock to listen.
  - `instance_name() -> str`: `"kicad-rf-studio-" + hashlib.sha256(str(runs.data_dir()).encode("utf-8")).hexdigest()[:16]`, the GUI's local server: per user, and per test through the `fake` fixture's data folder. It lives here, not in `control`, so a second start forwards without loading `control` (0.8 s: pipeline, numpy, scipy; `runs` takes 0.1 s, Qt 0.09 s).
  - `forward(name: str, request: dict) -> bool`: a `QLocalSocket` connects to `name` within 1000 ms, else False; it writes `json.dumps(request).encode("utf-8") + b"\n"`, waits for the bytes written (its result ignored: on Windows the write may already be done, probed), disconnects, waits up to 1000 ms for the disconnection unless already unconnected, and returns True. It carries `# ponytail: fire and forget: a request written to a window that closes before reading it is lost, and the user presses again; an answer line if users meet it`.
  - `main(argv: list[str] | None = None) -> int`:
    - `sys.stderr` pointed at `gui.log` when it is None (plan 1), first; then `argparse.ArgumentParser(prog="kicad-rf-studio-gui")` with `project` (`nargs="?"`) and `--handoff` (`metavar="FILE"`), parsing `sys.argv[1:]` when `argv` is None; the request `{"project": ..., "handoff": ...}`, each `str(Path(x).absolute())` or None.
    - The app (`QApplication.instance() or QApplication(sys.argv[:1])`), then `forward(instance_name(), request)`: True returns 0 at once, with no window and no event loop.
    - Otherwise the data folder is made and `lock = QLockFile(str(runs.data_dir() / "gui.lock"))`, `setStaleLockTime(0)` (a dead holder's lock is taken over by its PID, never by its age). While `lock.tryLock(0)` fails, another live start holds it and is about to listen: wait 0.2 s and forward again, returning 0 once it goes through, for up to `START_WAIT_S`; then go on without the lock.
    - Then a `QLocalServer` with `UserAccessOption` listens on the name; when `listen` fails the lock is unlocked (a later start may serve), and the window runs without a server. Only then `MainWindow` is imported and built, `win.serve(server, lock)`, `win.act(request)`, and `app.exec()` returned.
    - It carries `# ponytail: a window that holds the lock but never listens (hung at its start) makes a start wait START_WAIT_S, then open a window of its own; Windows lets two servers listen on one name, and Linux's listen renames over it, so the lock, not listen, keeps one window`.
  - `MainWindow` state: `server: QLocalServer | None` and `lock: QLockFile | None`, None at first.
  - `MainWindow.serve(server, lock)`: keeps both (`server.setParent(self)`) and connects `newConnection` to `incoming`.
  - `MainWindow.incoming()`: for each `nextPendingConnection()`, its `readyRead` to `forwarded` and its `disconnected` to its own `deleteLater`.
  - `MainWindow.forwarded()`: each complete line of the sending connection (`self.sender()`, `canReadLine`) is `json.loads(bytes(sock.readLine()))` (a QByteArray is not JSON input: TypeError), then `act`.
  - `MainWindow.act(request: dict)`: the window shown, unminimized (`setWindowState(windowState() & ~Qt.WindowState.WindowMinimized)`), raised and activated; then `take_handoff(Path(request["handoff"]))` when given, else `open_project(Path(request["project"]))` when given. It carries `# ponytail: Windows' foreground lock may flash the taskbar button instead of raising the window, unless the helper's AllowSetForegroundWindow reached it; the click-through checks`.
  - `MainWindow.closeEvent`: plan 1's, after closing the server and unlocking the lock first (both when there), so a later start serves itself instead of waiting on a closing window whose pool may still run.

- [ ] **Step 1: Write the failing tests,** in `tests/test_gui.py`:

```python
def test_the_gui_entry_takes_a_handoff_and_a_second_start_forwards_its_own_and_exits(qapp, fake, tmp_path,
                                                                                     monkeypatch):
    local = tmp_path / "local"  # design 5.5 Single instance; Review Focus 1
    monkeypatch.setattr(runs, "data_dir", lambda: local / "kicad-rf-studio")  # as a second process reads its env
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes((FIX / "lpf915.kicad_pcb").read_bytes())
    handoff = press(board, ["U1.1", "J1.1"])
    seen = []
    QTimer.singleShot(0, lambda: (seen.extend(qapp.topLevelWidgets()), qapp.quit()))
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
    QTimer.singleShot(0, lambda: (seen.extend(qapp.topLevelWidgets()), qapp.quit()))
    assert gui.main([]) == 0
    w = next(x for x in seen if isinstance(x, MainWindow) and x.server and x.server.serverName() ==
             gui.instance_name())
    assert w.server.isListening()  # with an access option Qt binds beside the name and renames over the stale file
    w.close()
    w.pool.shutdown(wait=True)
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui.py -q`. Expected: FAIL: the entry test with `StopIteration` (plan 1's `main` opens `--handoff` as a project, so no window took the press), and on Linux the socket-file test with `AttributeError: module 'kicad_rf_studio.gui' has no attribute 'instance_name'`; plan 1's two entry tests still pass.
- [ ] **Step 3: Implement** the Interfaces. `gui/__init__.py`'s docstring becomes "The GUI client (Stage 2 design 5): `control`, the Qt-free logic, and `window`, the main window; main(), one window per user (instance_name, forward, the lock file). `import kicad_rf_studio.gui` loads no Qt or matplotlib: main() and forward() import Qt inside themselves." `MainWindow`'s docstring adds `server` and `lock`.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS (the socket-file test skipped on Windows).
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/__init__.py src/kicad_rf_studio/gui/window.py tests/test_gui.py
git commit -m "feat(gui): one window per user takes each button press, two starts at once included (Stage 2 design 5.5)"
graphify update .
```

---

### Task 6 [code]: Refill zones and save in KiCad

**Files:**
- Modify:
  - `src/kicad_rf_studio/button.py` (`FILL_WAIT_S` and `refill`, after `start_gui`);
  - `src/kicad_rf_studio/gui/window.py`:
    - `NewForm`: `refill_button` in the board row (L285);
    - `MainWindow`: `__init__` (`refilling`; `refill_button` to `refill`), `tick` (after `creating`, L467–469), `ask` (L596–598), `take_handoff`, and the new `refill`, `refilled`; imports `button`;
  - `src/kicad_rf_studio/core/messages.py`;
  - `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (§4.3's live refill bullet, L202; §10's zone refill line, L629; the Status line).
- Test: `tests/test_button.py`; `tests/test_gui.py` (`from kicad_rf_studio.core.kicad import load_board`).

**Interfaces:**
- Consumes: Task 2's `_kicad`, `_call`, `_board_path`, `BUSY_S`, `BUSY_WAIT_S`; kipy's `Board.refill_zones(block=False)` and `Board.save()`; Task 4's `handed`, `handoff`, `take_handoff` and the press read through `show_pads`; plan 1's `ask`; `control.message`.
- Produces:
  - `button.FILL_WAIT_S = 120.0`.
  - `button.refill(socket: str, token: str, board: Path) -> Path`, the GUI's only way to save the board (design §7): `kicad = _kicad(socket, token, int(FILL_WAIT_S * 1000))`; the board KiCad has open, `_board_path(_call(kicad.get_board, until))` with `until = time.monotonic() + BUSY_S`, an `E_KICAD_UNSUPPORTED` there (AS_UNHANDLED: KiCad's PCB editor was closed since the press, so no handler answers) being `E_KICAD_NO_BOARD`; refused with `E_KICAD_OTHER_BOARD {board, open: that board}`, with nothing sent further, unless it is `board`; then `_call` of its `refill_zones(block=False)` (the same `until`), `time.sleep(BUSY_WAIT_S)` (KiCad only queues the fill), and `_call` of its `save()` with `until = time.monotonic() + FILL_WAIT_S`: asked again while KiCad answers AS_BUSY, and waited for while KiCad's main thread, which answers, holds the fill. Returns `board`. Its docstring says why not `refill_zones(block=True)`: in kipy 0.8.0 that polls forever while KiCad answers AS_BUSY (its counter never grows) and raises on a timed-out Ping (it catches IOError, which kipy's ConnectionError is not); and why the long timeout: the helper's 1 s would read a large board's save as an unreachable KiCad. It carries `# ponytail: a fill or a save longer than FILL_WAIT_S, or a KiCad closed mid-refill, ends in E_KICAD_UNREACHABLE after up to FILL_WAIT_S; each refill's kipy client is closed by the garbage collector`.
  - `NewForm.refill_button` (G_REFILL), in the board row after `board_button`; disabled at first.
  - `MainWindow.ask(text: str, title: str = "G_CONFIRM_TITLE") -> bool`: the question box's title is `render(title)`; plan 1's and plan 2's calls keep their title.
  - `MainWindow.refilling: Future | None`.
  - `MainWindow.refill()`, on `refill_button`: `h = self.handed`, bound before the question (the box is modal, but its event loop runs the tick and the local server, so a press can land while it is open and change `handed`, never the board confirmed); asks `render("G_REFILL_CONFIRM", board=str(h.board))` with the title `"G_REFILL"`; No sends nothing to KiCad. Yes: `refilling = pool.submit(button.refill, h.socket, h.token, h.board)`, New's status G_REFILLING, and `refill_button` disabled at once. It carries `# ponytail: the pool's one thread waits for the refill (seconds; FILL_WAIT_S at most), so a press or a project read meanwhile waits too; a second executor for KiCad's calls if users meet it`.
  - `MainWindow.refilled(done: Future)`: an exception, taken as `show_pads` takes it, puts `control.message(e)` in New's status. Otherwise New's status shows `render("G_REFILLED", board=str(done.result()))` and `pads_read = pool.submit(control.handed, self.handoff)`: the press read again, so what the save wrote pre-fills New, its status left as it is unless that read has a problem. An open project of that board reads itself again through the tick's board stamp (plan 1's F3).
  - `MainWindow.take_handoff`: New's status is cleared only while no refill goes on, so G_REFILLING stays.
  - `tick()`: after `creating`, a done `refilling` is taken and handed to `refilled`; then `refill_button` is enabled while `handed` is not None and `refilling` is None; both before the "no project" return.
  - CATALOG (exact texts):
    - `"G_REFILL": "Refill zones and save in KiCad"`
    - `"G_REFILL_CONFIRM": "Refill every zone of {board} in KiCad, then save the board there? The save also writes every edit not yet saved in KiCad."`
    - `"G_REFILLING": "KiCad is refilling the zones and saving the board…"`
    - `"G_REFILLED": "KiCad refilled the zones and saved {board}."`
    - `"E_KICAD_OTHER_BOARD": "KiCad has {open} open, not {board}, so nothing was refilled or saved. Open {board} in KiCad and press the kicad-rf-studio button again."`

- [ ] **Step 1: Write the failing tests.** In `tests/test_button.py`:

```python
def test_refill_refills_then_saves_only_the_board_the_button_sent(kicad, tmp_path):  # design 5.5 Refill, 7; RF 4
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes(LPF.read_bytes())
    k = kicad(board, save=b"(kicad_pcb)", errors={"SaveDocument": ["AS_BUSY", "AS_BUSY", "SLOW"]})
    assert button.refill(k.url, k.token, board) == board  # busy while KiCad fills, then answered past the helper's 1 s
    assert k.seen == ["GetOpenDocuments", "RefillZones", "SaveDocument", "SaveDocument", "SaveDocument"]
    assert board.read_bytes() == b"(kicad_pcb)"  # what KiCad's save wrote
    other = kicad(tmp_path / "other.kicad_pcb", save=b"x")
    with pytest.raises(KrsError) as e:
        button.refill(other.url, other.token, board)
    assert (e.value.code, e.value.params) == ("E_KICAD_OTHER_BOARD", {"board": str(board),
                                                                      "open": str(tmp_path / "other.kicad_pcb")})
    assert other.seen == ["GetOpenDocuments"]  # nothing refilled, nothing saved
    closed = kicad(board, errors={"GetOpenDocuments": ["AS_UNHANDLED"]})  # KiCad's PCB editor closed since the press
    with pytest.raises(KrsError) as e:
        button.refill(closed.url, closed.token, board)
    assert (e.value.code, closed.seen) == ("E_KICAD_NO_BOARD", ["GetOpenDocuments"])
    with pytest.raises(KrsError) as e:
        button.refill(k.url, "another KiCad's", board)
    assert e.value.code == "E_KICAD_UNREACHABLE"
```

  In `tests/test_gui.py`:

```python
def test_refill_asks_first_then_kicad_refills_and_saves_and_new_reads_the_board_again(window, kicad, tmp_path,
                                                                                      monkeypatch):
    lpf = (FIX / "lpf915.kicad_pcb").read_bytes()  # design 5.5 Refill, 3, 7; Review Focus 2
    kiid = {p.name: p.uuid for p in load_board(FIX / "lpf915.kicad_pcb").all_pads()}
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes(lpf.replace(kiid["U1.1"].encode(), b"00000000-0000-0000-0000-000000000002"))  # U1 placed anew
    k = kicad(board, save=lpf, errors={"SaveDocument": ["AS_BUSY"]})  # KiCad's save writes the edit it holds
    elsewhere, late = kicad(tmp_path / "other.kicad_pcb"), kicad(board)  # another board open; another KiCad's press
    selected = [kiid["U1.1"], kiid["J1.1"]]
    w = window()
    f = w.new_form
    assert not f.refill_button.isEnabled()  # no press yet: no KiCad to ask
    w.take_handoff(press(board, selected, socket=elsewhere.url, token=elsewhere.token))
    w.pads_read.result(timeout=60)
    w.tick()
    assert f.status.text() == render("G_HANDOFF_UNSAVED", board=str(board)) and f.start.currentText() == ""
    assert f.refill_button.isEnabled()
    asked = []
    answers = (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Yes)

    def question(parent, title, text, *rest):  # ask's own code runs, and no modal box opens
        asked.append((title, text))
        if len(asked) == 3:  # a press from another KiCad while the question is open (design 3: no unasked edits)
            parent.take_handoff(press(board, selected, socket=late.url, token=late.token))
            parent.pads_read.result(timeout=60)
            parent.tick()
        return answers[len(asked) - 1]

    monkeypatch.setattr(QMessageBox, "question", question)
    f.refill_button.click()  # No: nothing reaches KiCad
    assert asked == [(render("G_REFILL"), render("G_REFILL_CONFIRM", board=str(board)))] and w.refilling is None
    assert elsewhere.seen == []
    f.refill_button.click()  # Yes, but that KiCad has another board open: nothing refilled or saved
    w.refilling.exception(timeout=60)
    w.tick()
    assert f.status.text() == render("E_KICAD_OTHER_BOARD", board=str(board), open=str(tmp_path / "other.kicad_pcb"))
    assert (elsewhere.seen, w.pads_read, f.refill_button.isEnabled()) == (["GetOpenDocuments"], None, True)
    w.take_handoff(press(board, selected, socket=k.url, token=k.token))
    w.pads_read.result(timeout=60)
    w.tick()
    f.refill_button.click()  # Yes to this board in this KiCad, though another press came while it was asked
    assert f.status.text() == render("G_REFILLING") and not f.refill_button.isEnabled()
    w.take_handoff(w.handoff)  # a press while KiCad refills: the status keeps saying so
    assert f.status.text() == render("G_REFILLING")
    w.refilling.result(timeout=60)
    w.tick()
    assert f.status.text() == render("G_REFILLED", board=str(board)) and f.refill_button.isEnabled()
    assert k.seen == ["GetOpenDocuments", "RefillZones", "SaveDocument", "SaveDocument"] and late.seen == []
    assert board.read_bytes() == lpf and asked == [asked[0]] * 3  # each question names the board, under its title
    w.pads_read.result(timeout=60)
    w.tick()  # the press read again: the selection is in the saved file now
    assert (f.start.currentText(), f.end.currentText(), w.handed.socket) == ("U1.1", "J1.1", late.url)
    assert f.status.text() == render("G_REFILLED", board=str(board))
    grab(w, "refill")
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_button.py tests/test_gui.py -q`. Expected: FAIL with `AttributeError: module 'kicad_rf_studio.button' has no attribute 'refill'` and `AttributeError: 'NewForm' object has no attribute 'refill_button'`.
- [ ] **Step 3: Implement** the Interfaces and the codes.
- [ ] **Step 4: The spec.**
  - §4.3's bullet "- **Live refill** through kicad-python is Stage 2." becomes "- **Live refill** is the KiCad button's action "Refill zones and save in KiCad" (Stage 2): after a confirmation, since the save also writes every unsaved edit, it refills every zone and saves the board through kicad-python, and the board is read again. (A-18, Stage 2 plan 3: controller recommendation, owner unavailable.)"
  - §10's line "- zone refill through `kicad-cli` (Stage 1 shows the banner);" becomes "- zone refill through `kicad-cli`: the KiCad button's "Refill zones and save in KiCad" action (§4.3) takes its place (Stage 1 shows the banner); (A-18, Stage 2 plan 3: controller recommendation, owner unavailable.)"
  - The Status sentence becomes " On 2026-10-28, Stage 2's plan 3 amended §3.2, §3.4, §4.3 and §10 (A-16 to A-18) the same way."
- [ ] **Step 5: Run them again.** Same command. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/button.py src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py tests/test_button.py tests/test_gui.py docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "feat(gui): Refill zones and save in KiCad, after a confirmation, then New reads the board again; spec A-18 (Stage 2 design 5.5; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 7 [run]: The controller replays the installed launcher, and reviews the grabs

This task commits nothing. Every file it makes is under `$env:TEMP`, outside the repo; it never starts KiCad, and never touches a real KiCad folder, the real Documents folder, KiCad's settings or the real data folder. The PowerShell tool keeps no variable between calls, so every block below sets what it uses; run each as one call.

- [ ] **Step 1: Install into an isolated documents folder.** In PowerShell from the repo root, as one call (the install is fenced only while `KICAD_DOCUMENTS_HOME` is set in the same call):

```powershell
$iso = Join-Path $env:TEMP 'krs-plan3-run'
Remove-Item -Recurse -Force $iso -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$iso\docs\KiCad\9.0", "$iso\docs\KiCad\10.0", "$iso\board", "$iso\local" | Out-Null
Copy-Item tests\fixtures\lpf915.kicad_pcb "$iso\board\"
$env:KICAD_DOCUMENTS_HOME = "$iso\docs"
if ($env:KICAD_DOCUMENTS_HOME -ne "$iso\docs") { throw 'not isolated' }; .venv\Scripts\kicad-rf-studio.exe install-kicad-plugin
.venv\Scripts\kicad-python-packager.exe validate "$iso\docs\KiCad\10.0\plugins\kicad-rf-studio"
Remove-Item Env:KICAD_DOCUMENTS_HOME
```

  Expected: two I_PLUGIN_INSTALLED lines and I_PLUGIN_NEXT; then the packager's "Validation passed." (its warning about a requirements.txt concerns the python runtime only).
- [ ] **Step 2: The replay script.** Write `replay.py` into `$env:TEMP\krs-plan3-replay` (made with `New-Item -ItemType Directory -Force`):

```python
# replay.py: the controller's replay of the installed launcher (Stage 2 plan 3, Task 7), never committed. Run with
# the venv's pythonw.exe, which has no console, as KiCad starts an action: KiCad 10 with pipes, KiCad 9 without.
import json, os, subprocess, sys, time
from pathlib import Path

repo, iso = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo / "tests"))
from fake_kicad import FakeKiCad  # noqa: E402
from kicad_rf_studio.core.kicad import load_board  # noqa: E402

board = iso / "board" / "lpf915.kicad_pcb"
kiid = {p.name: p.uuid for p in load_board(board).all_pads()}
plugin = iso / "docs" / "KiCad" / "10.0" / "plugins" / "kicad-rf-studio"
k = FakeKiCad(f"ipc://{iso / 'api.sock'}", board, pads=[kiid["U1.1"], kiid["J1.1"]], version=(10, 0, 7))
env = {**os.environ, "KICAD_API_SOCKET": k.url, "KICAD_API_TOKEN": k.token, "LOCALAPPDATA": str(iso / "local"),
       "XDG_DATA_HOME": str(iso / "local"), "QT_QPA_PLATFORM": "offscreen"}
hide = subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0)  # wxEXEC_HIDE_CONSOLE
result = {}
for press, pipes in (("kicad10", True), ("kicad9", False)):
    begin = time.monotonic()
    p = subprocess.Popen([str(plugin / "launch.cmd")], cwd=plugin, env=env, startupinfo=hide,
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if pipes else None,
                         stderr=subprocess.PIPE if pipes else None)
    try:
        out, err = p.communicate(timeout=30)  # KiCad 10 reads both pipes only once the action ends
    except subprocess.TimeoutExpired:  # a launcher that hangs: its whole tree goes, and its press says so
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        out, err = p.communicate()
    result[press] = {"code": p.returncode, "seconds": round(time.monotonic() - begin, 2),
                     "stdout": (out or b"").decode("utf-8", "replace"),
                     "stderr": (err or b"").decode("utf-8", "replace")}
    time.sleep(8)  # the first press's GUI starts and listens before the second press comes
result["seen"] = k.seen
k.close()
(iso / "replay.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
```

- [ ] **Step 3: Replay, then check.** `Start-Process -Wait` would also wait for the GUI the replay starts (PowerShell 7 waits for the whole process tree), so the replay is waited on by its own process only:

```powershell
$iso = Join-Path $env:TEMP 'krs-plan3-run'
$script = Join-Path $env:TEMP 'krs-plan3-replay\replay.py'
$p = Start-Process -PassThru -FilePath .venv\Scripts\pythonw.exe -ArgumentList @("-I", "`"$script`"", "`"$PWD`"", "`"$iso`"")
$p.WaitForExit(180000) | Out-Null
Get-Content "$iso\replay.json"
Get-Content "$iso\local\kicad-rf-studio\handoff.json"
$gui = Get-CimInstance Win32_Process -Filter "Name = 'kicad-rf-studio-gui.exe'" | Where-Object { $_.CommandLine -like '*krs-plan3-run*' }
"gui processes: $(@($gui).Count)"
"button.log: $(Test-Path "$iso\local\kicad-rf-studio\button.log")"
Get-Content "$iso\local\kicad-rf-studio\gui.log" -ErrorAction SilentlyContinue
```

  A missing `replay.json` means the script failed: run it again with `.venv\Scripts\python.exe` in place of `pythonw.exe` to see its traceback. Then check:
  - `replay.json`: both presses `code` 0; `kicad10`'s `stdout` and `stderr` empty and `seconds` under 2, this first press paying the cold imports (a GUI holding the pipes would have made `communicate` wait, then time out); `seen` is `GetVersion`, `GetOpenDocuments`, `GetSelection`, twice.
  - `handoff.json`: the board `$iso\board\lpf915.kicad_pcb`, the KIIDs of U1.1 and J1.1, `"kicad": "10.0.7"`, the socket and the token `"K"`.
  - `gui processes: 1`: the GUI started detached and outlived both launchers; the second press forwarded to it and exited.
  - `button.log: False`, and `gui.log` empty or missing: no traceback.
- [ ] **Step 4: Close it and clean up,** as one call (`taskkill /T` takes each process's tree, a hung helper under its `cmd.exe` included; the filter leaves this shell alone):

```powershell
$iso = Join-Path $env:TEMP 'krs-plan3-run'
Get-CimInstance Win32_Process | Where-Object { ($_.Name -in @('kicad-rf-studio-gui.exe', 'cmd.exe', 'python.exe', 'pythonw.exe')) -and $_.CommandLine -like '*krs-plan3-run*' -and $_.ProcessId -ne $PID } | ForEach-Object { taskkill /T /F /PID $_.ProcessId 2>$null | Out-Null }
Remove-Item -Recurse -Force $iso, (Join-Path $env:TEMP 'krs-plan3-replay')
```

- [ ] **Step 5: Grab New pre-filled.** Plan 2's font plugin is gone from `$env:TEMP`, so write it whole, with the settle step of plan 2's record: `krs_font.py` into `$env:TEMP\krs-font` (made with `New-Item -ItemType Directory -Force`):

```python
# krs_font.py: a scratchpad pytest plugin for the offscreen grabs, never committed
import os

import pytest

os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ["WINDIR"], "Fonts"))  # before any QApplication


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    yield  # the qapp fixture has made the QApplication by now
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    if app := QApplication.instance():
        app.setFont(QFont("Segoe UI", 9))


from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QWidget  # noqa: E402

_grab = QWidget.grab


def _settled(self, *args):  # plan 2's record: events and deferred deletes run before a review grab
    for _ in range(5):
        QCoreApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return _grab(self, *args)


QWidget.grab = _settled
```

  Then, as one call: `$env:PYTHONPATH = "$env:TEMP\krs-font"; $env:KRS_GRAB_DIR = "$env:TEMP\krs-grabs-plan3"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q -p krs_font -k "button_press or refill"; Remove-Item Env:KRS_GRAB_DIR, Env:PYTHONPATH`. Expected: all pass; the folder holds `handoff.png` and `refill.png`.
- [ ] **Step 6: Look at each PNG** with the Read tool, at 1200 × 800:
  - **handoff:** the Project tab; in "New from a board": the board's path with Browse… and Refill zones and save in KiCad, enabled; start U1.1; end J1.1 beside "Swap start and end"; the project folder ending in `lpf915`; no status line. Every word is the catalog's, in English, legible and unclipped.
  - **refill:** the same form with "KiCad refilled the zones and saved …" as its status line, U1.1 and J1.1 filled, and the Refill button enabled.
- [ ] **Step 7: Fix what fails.** Each defect becomes a [code] fix in the owning task's file, test-first where a test can see it, committed as `fix(button): ...` or `fix(gui): ...` after the full suite; then the failing step runs again. A grab of a word-wrapped QLabel taken without an event loop may keep its old height: an artifact of `grab()`, not a defect (plan 1).

---

## Not in this plan

- **Install and release (plan 4):** the README's install section and its "move the venv, run install-kicad-plugin again" note; NOTICE's runtime dependencies, which copies `control.DEPENDENCIES` (kicad-python, protobuf, pynng and jsonschema now in it); `tools/release_check.py`, which validates plugin.json against the schemas fetched at the 9.0.7 and 10.x tags (kipy's bundled one adds the `footprint_wizard` scope) and may run KiCad's real loader in tier (c); its fresh-venv install check, which must run `python -I -c "import kipy.board_types"` after `pip check` (kicad-python 0.8.0's protos refuse a protobuf runtime older than their 5.29.6 gencode, which its `protobuf>=5.29` pin allows: a shared venv holding 5.29.0 to 5.29.5 installs cleanly and fails at import); §5.11's end-to-end run, which replays this plan's launcher again.
- **The owner's click-through on a real KiCad,** 9.0.7 and 10.x (design §5.11 item 4). Only it shows:
  - KiCad itself setting `KICAD_API_SOCKET`, `KICAD_API_TOKEN` and the plugin folder as the working folder;
  - the click-time `IsFileExecutable` check, and that no console flashes;
  - how KiCad 10 decodes the helper's stderr (its lines are ASCII but for paths, so the worst case is a garbled path);
  - cmd's AutoRun (conda init, clink), which runs before launch.cmd since a .cmd entrypoint runs through `cmd /c` without `/D`: its time counts against the 2 s, and any stderr text it writes shows in KiCad 10;
  - a non-ASCII project folder through `GetOpenDocuments` (KiCad builds it with `ToStdString`): a mangled path shows as load_board's "file not found" in New's status, with the path;
  - whether a click selects the pad or its footprint (both are handled);
  - that a second press brings the open window to the front (Windows' foreground lock; the helper's AllowSetForegroundWindow);
  - that the board Refill saved holds the new fills (KiCad only queues the fill; r1's open question);
  - whether KiCad runs its actions in a job object, and so whether the window closes with KiCad (its runs do not).
- **A missing-Python check in the launcher.** When the venv moves, cmd's or sh's own error (in the system's language) and a non-zero exit show in KiCad 10, and in KiCad 9 nothing does, until the README's re-run of `install-kicad-plugin`.
- **The 8.3 short path for a launch.cmd Python outside the console's code page:** refused with E_PLUGIN_PYTHON (ponytail note).
- **KiCad folders other than 9.0 and 10.0** (a 10.1 needs `VERSIONS`), Flatpak KiCad (design §3: its sandbox cannot run the venv; the installer then finds no folder) and macOS.
- **Removing only the files install wrote:** `--remove` deletes the whole `plugins/kicad-rf-studio`, a folder ours by name; a marker file or the six names if users keep files there.
- **Live geometry through the API, or the unsaved board as a `get_as_string()` snapshot** (design §3; r1 options b and c). `Pad.parent` (KiCad 10.0.6) and `get_items_by_net` (10.0.1) are not used.
- **A KiCad that answers slower than `TIMEOUT_MS`,** or stays busy past the press's 1 s, at a click: the helper says E_KICAD_UNREACHABLE or E_KICAD_BUSY (ponytail note in `_call`).
- **A fill or save longer than `FILL_WAIT_S`, or a KiCad closed mid-refill:** E_KICAD_UNREACHABLE after up to 120 s (ponytail note in `refill`).
- **A second executor for KiCad's calls:** a refill holds the window's one pool thread, so a press or a project read waits for it (ponytail note in `MainWindow.refill`, as plan 2's on Apply).
- **The window leaving KiCad's job:** the GUI starts with the design's flags, so in a KiCad job that kills on close the window closes with KiCad, while its runs break away (ponytail note in `start_gui`; the click-through checks whether KiCad has a job).
- **A file per press, and an answer line for a forward:** one fixed `handoff.json` (ponytail note in `write_handoff`); a forward written to a window that closes at that instant is lost (ponytail note in `forward`).
- **A second start's PROJECT forwarded** to the running window: `act` opens it, as the first start's does, untested apart.
- **The pt-BR catalog and Qt's own translations:** after v1 (design §5.7).

## Controller rulings (2026-10-28; binding)

The architect's rulings, revised after the four reviews (coverage, feasibility against kipy's source and the repo, KiCad and process safety, quality). Each is a controller recommendation, owner unavailable.

- Ruling: seven tasks: the dependency (1), the helper (2), the installer (3), New pre-filled from a press with Swap (4), one window per user (5), refill (6) and the controller's replay (7). Pre-fill and single instance are two tasks, each a feature a reviewer can pass or reject on its own; there is no job task: the GUI starts with the design's flags, and Task 2's KiCad-job test pins the breakaway of the runs, which plan 1's `control.start` already has — cost if wrong: one more review gate.
- Ruling: KiCad's side is one module, `kicad_rf_studio/button.py`: the helper, the handoff writer, the GUI start, the kipy calls (`read`, `refill`) and the installer. kipy is imported only inside the functions that call KiCad, so `import kicad_rf_studio.button` loads no kipy (it joins `QT_FREE`), and `cli` imports `button` only inside its `install-kicad-plugin` handler — the fewest files; the import rules hold at import (QT_FREE) and when run (the KiCad-10 test's helper and the launcher test's install, in subprocesses) — cost if wrong: one module of about 250 lines.
- Ruling: kicad-python is imported by the helper and, through `button.refill`, by the GUI process, on its pool and never at import; this supersedes plan 1's "only the helper imports it" — design §4 forbids it only in `cli` and `worker`, which QT_FREE pins, and Refill must talk to KiCad from the GUI (A-16's text says so) — cost if wrong: none.
- Ruling: the helper's contract is tested with kipy's real client against a fake KiCad API server (`tests/fake_kicad.py`: an nng Rep0 socket answering kipy's own protobuf requests KiCad 9.0.7's way, with its token check, scripted AS_ statuses and "SLOW" answers for KiCad's held main thread), not with a fake kipy module, and a one-off check of its transport runs before the tests (Task 2 Step 2), so a transport fault never shows up as a helper fault. The owner's click-through is the only test with a real KiCad, so the helper's real kipy calls (their message types, the Any packing, the status codes, the token) run here first. One fake serves the helper's tests, refill's, the GUI's and Task 7's replay; pynng and the protos come with kipy, so nothing is added — design §5.8 says "a fake kipy" — cost if wrong: KiCad-side behaviour the fake does not model (busy timing, a real selection's contents) stays the click-through's.
- Ruling: the handoff is one fixed file, `data_dir()/handoff.json`, written whole by `save_project`; the latest press wins, and nothing deletes it. KiCad's token in it is no secret: KiCad accepts a request with an empty token (api_server.cpp), so it only tells a restarted KiCad apart — no accumulation and no clean-up code — cost if wrong: two presses within one write, or a press while the window reads it, end in E_HANDOFF_WRITE and the user presses again (ponytail note).
- Ruling: the GUI is the gui-scripts entry of the helper's own environment, `sysconfig.get_path("scripts")` / `kicad-rf-studio-gui[.exe]`, never a PATH lookup. Its stdin and stdout are the null device, but its stderr is `gui.log`, opened for append: under pythonw a null stderr is a valid file, so `gui.main` would not open `gui.log` and a traceback would be lost. KiCad's pipes are never inherited either way. Its working folder is the data folder, never the plugin folder, which `--remove` deletes, nor KiCad's — design §5.5's "null stdio" serves KiCad 10's pipes, which this keeps — cost if wrong: a few bytes in gui.log.
- Ruling: `start_gui` keeps the design's flags, `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`, with no breakaway. KiCad starts its actions with a plain `wxExecute` (no job object in `api_plugin_manager.cpp` at 9.0.7 or 10.0.7), the venv launcher's job lets the GUI leave silently, and the runs the GUI starts break away in `control.start`, which Task 2's KiCad-job test pins against a job that kills on close and allows breakaway (plan 1's carry-over: "plan 3's job-object test finds it"). Adding the breakaway to the GUI would only keep the window alive in a KiCad job nobody has seen, by copying `control.start`'s fallback — cost if wrong: in a KiCad job that kills on close the window closes with KiCad, losing unsaved Advanced edits and unapplied retune values, while its runs go on (ponytail note; the click-through checks).
- Ruling: the helper's KiCad calls: `KiCad(socket from KICAD_API_SOCKET or kipy's default, client "kicad-rf-studio", the token from KICAD_API_TOKEN, timeout 1000 ms)`; AS_BUSY is asked again 0.25 s later within one 1 s budget for the whole press (`until`, a deadline), not per call, and a test with three busy answers on each of the three calls pins it; `get_version()` accepts majors 9 and 10 and `check_version()` is never called, which a 10.0.7 fake pins (kipy 0.8.0's `check_version` refuses anything newer than 10.0.6); AS_UNHANDLED and AS_UNIMPLEMENTED are E_KICAD_UNSUPPORTED; AS_TOKEN_MISMATCH and no connection are E_KICAD_UNREACHABLE; any other error is E_INTERNAL — design §5.5 and r1 §1; with a per-call budget three busy calls would sleep 2.25 s alone, past the helper's about 2 s — cost if wrong: a KiCad busy for more than 1 s at a click gets E_KICAD_BUSY, and three answers each just under the 1 s timeout take about 3 s (ponytail note).
- Ruling: the selection is asked with the types KOT_PCB_PAD and KOT_PCB_FOOTPRINT; pads travel as KIIDs (`Pad.id.value`) and footprints as references (`reference_field.text.value`); the board is `project.path` joined with `board_filename`, and an empty file name is E_KICAD_NO_BOARD — every call exists in 9.0.7; `Pad.parent` needs 10.0.6 (r1) — cost if wrong: none.
- Ruling: the helper silences warnings, keeps its lines ASCII but for paths ("Preferences > Plugins > Enable KiCad API"; a test checks its catalog texts), runs under `-X utf8 -I`, and on Windows calls `AllowSetForegroundWindow(ASFW_ANY)` before it starts the GUI — KiCad 10 shows any stderr text, decoded with a code page this plan cannot check; `-I` keeps KiCad's own PYTHONPATH or PYTHONHOME out; KiCad, in the foreground, started the helper, which may therefore let the window it starts, or the one a second start forwards to, come to the front (design §2 goal 1), which a forwarding GUI process may lack the right to grant — cost if wrong: an accented path in a failure line reads garbled in KiCad 10's status bar; a window that flashes in the taskbar instead of coming forward (click-through).
- Ruling: `refill` uses `refill_zones(block=False)`, pauses `BUSY_WAIT_S` (KiCad only queues the fill), then `save()` asked again while KiCad answers AS_BUSY, for up to `FILL_WAIT_S` (120 s), on a client whose timeout is `FILL_WAIT_S`; no Ping. This replaces design §5.5's `refill_zones(block=True)`: kipy 0.8.0's blocking form polls forever while KiCad answers AS_BUSY (its counter never grows) and raises on a timed-out Ping (it catches IOError, which kipy's ConnectionError is not). KiCad answers from its main thread, which the fill holds, so the save either waits there and is answered once the fill ends, or is answered AS_BUSY and asked again; the helper's 1 s timeout would read a large board's save as an unreachable KiCad, which a "SLOW" answer pins. AS_UNHANDLED at GetOpenDocuments, whose handler goes with a closed PCB editor (api_server.cpp answers AS_UNHANDLED when no handler takes a request), is E_KICAD_NO_BOARD there, not "this KiCad cannot" — cost if wrong: a fill or save over 120 s, or a KiCad closed mid-refill, ends in E_KICAD_UNREACHABLE after up to 120 s (ponytail note).
- Ruling: refill acts only on the board the user confirmed, in that press's KiCad: `MainWindow.refill` binds the press before the question, and `refill` refuses with E_KICAD_OTHER_BOARD, before anything is sent, unless that KiCad still has that board open — design §3: no unasked board edits; the question is modal, but its event loop runs the tick and the local server, so a press can land while it is open, and that KiCad may have another board open by then — cost if wrong: one call more.
- Ruling: Refill is a button in New's board row, enabled once a press gave a KiCad and while no refill runs. Its confirmation goes through `ask(text, title)`, which gains a title code (default G_CONFIRM_TITLE, so plan 1's and plan 2's questions keep "Start the run?"), and its test patches `QMessageBox.question`, so `ask`'s own code and the title run. After the save, New reads the press again, so that a selection the save wrote pre-fills it; an open project of that board reads itself again through the tick's board stamp; a press during a refill keeps G_REFILLING; the refill runs on the window's one pool thread — design §5.5: refill, save, re-import; no second re-import mechanism, and plan 2's single pool, as Apply — cost if wrong: Refill is not reachable from the Cost or Results tabs, and a press during a long refill pre-fills New only after it (ponytail note).
- Ruling: one window per user. `gui.main` forwards first; when no window takes the request, it takes `gui.lock` in the data folder (QtCore's `QLockFile`, stale only by its holder's PID), and only then listens on a `QLocalServer` named `kicad-rf-studio-` plus 16 hex digits of the SHA-256 of `data_dir()`'s path, with `UserAccessOption`; a start that finds the lock held by a live process forwards again every 0.2 s for up to `START_WAIT_S` (10 s); the window keeps the lock and the server until it closes, and a failed listen unlocks. `instance_name` lives in `gui/__init__.py`, so a second start forwards without loading `control` (measured: 0.8 s, against 0.1 s for `runs` and 0.09 s for Qt). On Windows two servers listen on one name (probed), and on Linux Qt's listen with an access option binds beside the name and renames over it (`qlocalserver_unix.cpp`), so no listen ever refuses: the lock is what makes two presses within a startup one window, and the rename is what replaces a socket file a killed window left — design §5.5 and r1 §2; per user, and per test through the `fake` fixture's data folder — cost if wrong: a window that holds the lock but never listens makes the next start wait 10 s and open its own (ponytail note).
- Ruling: a second start forwards one JSON line, `{"project", "handoff"}` with absolute paths, fire and forget, and the window reads it as `bytes(readLine())` and acts on it as `main` acts on its own (`act`: to the front, then the handoff or the project) — one code path for both starts; `closeEvent` closes the server and unlocks first — cost if wrong: a forward lost when its window closes at that instant (ponytail note).
- Ruling: `control.handed` joins the selected KIIDs to `Pad.uuid` from `load_board` on the saved file and reads it on the pool. One pad fills start; two fill start and end, the connector's pad (`classify`) as the end when only one is a connector's; three or more fill nothing (G_HANDOFF_PADS). Selected footprints narrow the pickers to their pads and the selected ones. A KIID or a reference the file lacks is G_HANDOFF_UNSAVED, with nothing pre-filled; a pad with no copper is never an end; `load_board`'s refusal is New's status with no pads — design §5.5 "From the selection to REF.PAD", and r1's "do not rely on the selection's order" — cost if wrong: one rule in `handed`.
- Ruling: a press is New's pad read: `take_handoff` submits `control.handed` as `pads_read`, replacing a read in flight, and `show_pads` takes a Handed as well as plan 2's names (board field, `chosen`, folder, pickers with start and end, the problem line, and `handed` kept for Refill). `chosen` is cleared for a press with no pads, as for a refused read — plan 2's recorded route (`new_form.board`, `board_chosen()`, then start and end once `pads_read` ends), one future and one tick branch instead of a second copy of New's machinery, plan 2's F4 refusal rule kept for a press, and whichever comes last, a press or a board picked, wins — cost if wrong: `show_pads` has one branch per result type.
- Ruling: Swap is a button beside the end picker, a bound method of `NewForm` — design §5.5 "with a swap" — cost if wrong: none.
- Ruling: `install-kicad-plugin` writes `plugins/kicad-rf-studio` under KiCad's 9.0 and 10.0 version folders that exist (a version folder, not its `plugins`, which KiCad may not have made yet), or under the one named with `--kicad`, made; `--remove` deletes that whole folder, ours by name, and no marker file is kept; an OSError while writing or removing is E_PLUGIN_WRITE; the version and plugins folders stay, since KiCad makes them anyway — design §5.5 Install ("--remove deletes it") and r3 R-3 — cost if wrong: a user who never started KiCad names the version; a file a user put inside our plugin folder goes with it.
- Ruling: KiCad's documents base is `KICAD_DOCUMENTS_HOME`, else on Windows `SHGetFolderPathW(CSIDL_PERSONAL)` through ctypes (wxWidgets' `GetDocumentsDir`; it follows a OneDrive redirect; tested against PowerShell's `[Environment]::GetFolderPath('MyDocuments')`, which reads only the path), else `XDG_DATA_HOME` or `~/.local/share`; the folder below it is `KiCad` on Windows and `kicad` on Linux — KiCad's `paths.cpp` at 9.0.7 and 10.0.7 — cost if wrong: one test spawns PowerShell for about a second.
- Ruling: the icons are drawn at install time by a short stdlib PNG writer (`zlib`, `struct`): a ring and its horizontal diameter, #333333 for light themes and #DDDDDD for dark, at 24 and 48 px — no binary file in the repo, no package data to ship (r3's warning), and no matplotlib in the CLI (C-5); the artwork is the builder's (design §6) — cost if wrong: a plain glyph until an artist draws one.
- Ruling: `launch.cmd` is written in the OEM code page, which cmd.exe reads a batch file in, with CRLF, `setlocal DisableDelayedExpansion` as its second line (a registry-set DelayedExpansion would eat a `!` of the path) and every `%` doubled; a path it cannot hold is E_PLUGIN_PYTHON, with nothing written. `launch.sh` escapes single quotes and is made 0755. The Python is `os.path.abspath(sys.executable)`, never resolved, since a Linux venv's python is a symlink out of the venv — probed: a .cmd, with that `setlocal` too, returns its last command's exit code and passes `%*` and a `!` through — cost if wrong: a user with an unusual character in the venv path installs elsewhere (ponytail note); cmd's AutoRun still runs before it (click-through).
- Ruling: no missing-Python check in the launcher — cmd and sh already write their own line and exit non-zero, which KiCad 10 shows; a fixed English line needs escaping rules of its own — cost if wrong: a moved venv reads as the system's "cannot find the path" until the user runs install-kicad-plugin again.
- Ruling: plugin.json is checked with kipy's own `validate_plugin` (its bundled `api.v1.schema.json`, `$schema`, the entrypoint and the icons), both identifier regexes from KiCad's `api_plugin.cpp`, and design §5.5's own rule (letters and digits, at least three segments, the first letters only), which the owner's final identifier must meet too and which the regexes and the schema are looser than (they take a hyphen). Probed: kipy's bundled schema equals KiCad 9.0.7's and 10.0.7's (which are identical) but for one more scope, `footprint_wizard`, which the plugin does not use — no JSON-schema code or schema file of our own; jsonschema comes with kipy — cost if wrong: plan 4's release check validates against the tagged schemas too.
- Ruling: About lists kicad-python (MIT) and the three packages it brings, protobuf (BSD-3-Clause), pynng (MIT) and jsonschema (MIT) — plan 2's About test requires every core dependency there, and NOTICE copies the list (r3) — cost if wrong: three lines.
- Ruling: no test reaches a real KiCad: `tests/conftest.py`'s autouse `no_kicad` points `KICAD_DOCUMENTS_HOME` and `KICAD_CONFIG_HOME` under `tmp_path` and `KICAD_API_SOCKET` at an unused `ipc://` address for every test, and clears `KICAD_API_TOKEN`; the install test seeds `kicad_common.json` where KiCad 9 and 10 read it (`KICAD_CONFIG_HOME`, `APPDATA`, `XDG_CONFIG_HOME`, all set under `tmp_path`), so its byte-for-byte check would see a settings write — design §3 (KiCad settings touched) and the rule that no test touches a real KiCad folder; kipy's default socket would be a KiCad the owner has open — cost if wrong: a few environment variables per test.
- Ruling: the KiCad-10 contract test runs the helper as a real subprocess with both pipes, and replaces the GUI through `button.gui_command` inside the child's `-c` code, with a pythonw stand-in that records its arguments and runs on for 10 s; it asserts exit 0, no output and under 5 s, and the child asserts that no Qt or matplotlib was loaded once `main` ran (the separate no-Qt probe of kipy goes) — no test-only entry file; what the bound tells apart is pipes held for 10 s or not at all; the 2 s target stays Task 7's measured check — cost if wrong: none.
- Ruling: the second-start test runs `gui.main` in a separate process and pumps this window's events until that process ends, its data folder set through `runs.data_dir` here and `LOCALAPPDATA`/`XDG_DATA_HOME` there, so both name one server and one lock; this window's server is closed while the second start begins and listens again 2 s later, so the second start's wait on the lock is exercised; the second process is offscreen, its stderr names a failure, and it is killed if it still runs at the end — a real second start, with no timing-based quit — cost if wrong: on a machine slower than 2 s to start Python and Qt, the second start forwards straight away and the wait goes unexercised, the test still passing.
- Ruling: no pytest-qt — no test needs `waitSignal`: the second-start test pumps this window's events by hand (`until(lambda: qapp.processEvents() or ...)`) — design §5.8 adds it only if a test needs it — cost if wrong: none.
- Ruling: amendments A-16 (§3.4's pin, Task 1), A-17 (§3.2's `install-kicad-plugin` row, Task 3) and A-18 (§4.3's live refill and §10's zone refill, Task 6), with one Status sentence that later tasks widen — design §5.10, numbered from A-16 since plan 1 took A-13 to A-15 and plan 2 took none — cost if wrong: none.
- Ruling (disclosure): the architect and the reviser ran only read-only probes, in scratch folders: the kicad-python 0.8.0 wheel (its SHA-256 equal to PyPI's), read, never installed: kipy's client (its `ConnectionError` is no IOError; a recv timeout raises it), errors, Board, `get_board` (an empty list is an `ApiError` of AS_BAD_REQUEST), `get_selection`, `refill_zones` (the never-growing counter), `unwrap`, the Any type URLs, `kipy.packaging.validate` and its protos' 5.29.6 runtime check; its bundled schema against KiCad 9.0.7's and 10.0.7's (one scope apart); KiCad 9.0.7's and 10.0.7's `paths.cpp`, `api_plugin.cpp`, `api_plugin_manager.cpp` (KiCad 10 reports stderr whenever it is not empty; plain `wxExecute`, no job object), `api_server.cpp` (AS_UNHANDLED when no handler takes a request) and `api_handler_pcb.cpp` (RefillZones only queues the fill); offscreen QtNetwork (a same-process forward arrived although `waitForBytesWritten` returned False; a missing server fails at once; two servers listened on one name on Windows); `json.loads` of a QByteArray raising TypeError; `QLockFile` across processes (a live holder refuses `tryLock(0)`, a killed one is taken over by its PID with `setStaleLockTime(0)`); a .cmd's exit code, its stderr line and `%*`, with `setlocal DisableDelayedExpansion` too; a job object with KILL_ON_JOB_CLOSE and BREAKAWAY_OK, whose child died without CREATE_BREAKAWAY_FROM_JOB and lived with it; lpf915's pads (U1's four paste-only pads, J1's two J1.2 pads, the connectors J1 and J2); import times (`control` 0.8 s, `runs` 0.1 s, Qt 0.09 s); the venv's scripts folder (it holds `kicad-rf-studio-gui.exe` and `pythonw.exe`). No full suite, no openEMS, no KiCad, no visible window — cost if wrong: none.
- Ruling (the reviser's open issues 1, 2 and 6): the owner's click-through on KiCad 9.0.7 and 10.x keeps every check only a real KiCad can make, as "Not in this plan" lists them: KiCad's environment and working folder for the action, IsFileExecutable and no console flash, KiCad 10's stderr decoding, a non-ASCII project path, what a click selects, a second press raising the window, a save sent during a fill, a closed PCB editor's answer, the refilled board's fills, cmd's AutoRun, and whether KiCad runs its actions in a job. No agent runs it; it is carried over beside P0-C — cost if wrong: a defect it finds is fixed after the merge.
- Ruling (open issue 3): Task 2 Step 2 is the gate for the fake's transport. Should nng's `ipc://` form of a Windows path fail there on the listening side, the fake and the `kicad` fixture listen on `tcp://127.0.0.1:{port}` instead (a free port: a socket bound to port 0, read, then closed), while `no_kicad` and the no-server cases keep an `ipc://` address nobody listens on. The helper is unchanged, since it dials whatever KICAD_API_SOCKET names, and the implementer records the switch in concerns — cost if wrong: KiCad's own Windows transport goes untested until the click-through.
- Ruling (open issues 4 and 5): the Linux-only tests (a killed window's socket file, launch.sh, the XDG paths) first run on CI after the owner's first push, and the second-start test may pass on a slower machine without exercising the lock wait; both stand as ruled above — cost if wrong: a Linux defect found at the first CI run.
- Ruling (open issue 7): AS_NOT_READY stays unmapped and reads as E_INTERNAL naming the ApiError: KiCad answers it only while its API server starts, before its toolbar exists — cost if wrong: one unclear line in a race nobody has seen.
- Ruling (open issue 8): plan 4 takes the fresh-venv `python -I -c "import kipy.board_types"` check after `pip check`, NOTICE's dependency list copied from `control.DEPENDENCIES`, and the release check against the tagged 9.0.7 and 10.x schemas, as "Not in this plan" says; `org.kicadrfstudio.app` stays until the owner names the identifier tied to the account — cost if wrong: none.
- Ruling (agents and the owner's KiCad): no agent lets kipy reach a real KiCad. Every `KiCad()` an implementer or reviewer makes outside the suite names a fake's address (kipy's default socket is the KiCad the owner may have open, with a private board), and nobody runs `install-kicad-plugin`, `button.install`, `button.main` or an installed launcher outside pytest unless KICAD_DOCUMENTS_HOME, LOCALAPPDATA, XDG_DATA_HOME and KICAD_API_SOCKET point under a temporary folder in the same call (Task 7 does so) — design §3 and the privacy rules — cost if wrong: none.
