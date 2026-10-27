# kicad-rf-studio — Stage 2 design: the GUI client and the KiCad button

- **Date:** 2026-10-27
- **Status:** controller design, written on 2026-10-27 while the owner is unavailable. Every decision below is a
  **controller recommendation, owner unavailable**. The owner may override any of them.
- **Authority:** the Stage 1 spec, `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, stays the engine
  authority, and its Stage 2 lines bind this design: §1.1, §3.1's GUI rules, §3.2's call order and §3.4's dependencies.
  This document is the authority for the GUI client, the KiCad button and their packaging. Where Stage 2 changes the
  Stage 1 spec's text, the change lands as a numbered amendment, A-13 onward, in the plan that implements it (§5.10).
  A-9 to A-12 stay with plan 7's fixes, which did not land.
- **Builder check (2026-10-27):** a fresh builder read this design against the repo and left nothing important open.
  Its five minor points are settled as controller calls in §4, §5.2, §5.3, §5.5 and §6.
- **Evidence:**
  - `docs/validation/2026-10-25-stage1-exit.md`: section 7's Stage 2 estimate, and its plan 7 addendum;
  - `docs/validation/2026-10-24-precheck.md`: the button pre-check;
  - `docs/validation/2026-10-27-p0-b2.md`: plan 7's report;
  - the research of 2026-10-27 in `.superpowers/sdd/stage2-research/`: r1 on KiCad, r2 on the GUI, r3 on packaging
    (git-ignored, local).

## 1. Intent and why

Stage 1 delivered a headless engine and a CLI. A hardware engineer can run the matching workflow (new, cost, run,
retune, verify), but only by typing commands, editing `project.json` and reading the files it writes. The v1 promise also
includes "a GUI that never freezes" (Stage 1 §1.2), and a KiCad toolbar button that sends the open board and the
selection (§1.1). Stage 2 builds that client on the engine as it is.

Stage 1's results shape it:
- **The retune stays "what-if".** P0-B failed at the ceiling, and plan 7's two fixes missed their checks, so
  `RETUNE_VALIDATED` stays False. The instant retune is "relative / what-if" (§7.6), so the GUI must say so on every
  retuned result and keep Verify one click away.
- **The output chain only.** The TX side is not in v1 (A-5), so the GUI serves the output chain.
- **The button mechanism works.** It passed its pre-check (§9.6): KiCad 9.0.7's exec runtime runs a `.cmd` launcher and
  passes `KICAD_API_SOCKET` and `KICAD_API_TOKEN`.
- **The time policy is still open.** Whether Draft or Normal is the default stays the owner's call. The GUI shows the
  preset and its cost, and defaults to whatever `new` defaults to.

## 2. Goals

1. **The button, from KiCad.** In KiCad 9.0.7 or later, or 10.x, the user selects the chain's two end pads and presses
   the toolbar button. The GUI then opens, or comes to the front, on that board with start and end filled in. This takes
   a few seconds and never blocks KiCad.
2. **The matching workflow in the GUI,** in the CLI's order (§3.2):
   - New, from a board, or open an existing `project.json`;
   - Cost, shown before every run;
   - Run, with live progress per job and Stop;
   - Results: S11, S21, harmonic rejection, the Smith chart and the run's messages;
   - Retune: instant, per part, with E12/E24 snapping or an S2P file;
   - Apply, which writes the outputs;
   - Verify, a full run of the final values.
3. **Runs outlive the windows.** A run survives closing the GUI or KiCad. Reopening the GUI re-attaches to the run, or
   shows its outcome.
4. **The GUI never freezes.** Anything that can take longer than about 50 ms runs on a worker thread or in a subprocess.
5. **An advanced panel** exposes `project.json`'s fields, as Stage 1 §1.1 promised.
6. **Install:**
   - README steps for Windows and Linux;
   - `kicad-rf-studio install-kicad-plugin` for the button;
   - an About box with the licence notices.
7. **Tests:**
   - the Qt-free logic is tested like the engine;
   - widget smoke tests run offscreen;
   - the import rules are tested;
   - one real end-to-end run is driven through the GUI's own code paths (§5.11).

## 3. Non-goals and anti-goals

**Non-goals.** None of these is in Stage 2:
- **Engine accuracy work.** A redesign of A-9 or A-10, r3's X-A run and P0-C stay the owner's decisions (plan 7's report,
  §7).
- **Out of v1 scope:** the TX side, complex targets and 3-port switch states (Stage 1 §10, A-5).
- **Live geometry through the API** (r1's option b). The GUI imports the saved `.kicad_pcb` with Stage 1's importer.
- **Distribution extras:** a PCM package, an installer script, a bundled openEMS, a PyInstaller build and a Start-menu
  shortcut.
- **Other platforms:** macOS, and the button for Flatpak KiCad (Flatpak users open the board file).
- **The pt-BR translation.** It follows right after v1 (Stage 1 §1.1). Stage 2 keeps every string translatable.
- **Later scope:** a schematic-side button, antennas (Stage 3) and SI.

**Anti-goals.** Each of these is a failure even if everything else works:
- **A blocking GUI thread:** a frozen window during import, cost, a run, retune or a plot.
- **A lost run:** a run killed or orphaned without trace because the GUI, the button helper or KiCad closed.
- **A weak what-if label:** a retuned result without the label while `RETUNE_VALIDATED` is False, or a label that reads
  softer than §7.6.
- **Run logic in the GUI.** The GUI calls the engine's functions and commands in the CLI's order, and adds no gate, stop
  rule or reduction of its own.
- **Unasked board edits:** the GUI saving or modifying the user's board without an explicit, confirmed action.
- **KiCad settings touched.** The installer writes only its own plugin folder.
- **A privacy leak:** a private name, path or e-mail in a committed file. The privacy gate holds.

## 4. Constraints

- **Import rules,** extending Stage 1 §3.1:
  - the core never imports Qt;
  - the GUI never imports openEMS or CSXCAD;
  - `cli` and `worker` import neither Qt nor kicad-python;
  - the button helper never imports Qt.
- **Platforms:**
  - Python: the package's declared floor (3.11) and the CI matrix stay as they are. The Windows install uses Python 3.14,
    because the openEMS 0.37.0 wheels need 3.13 or 3.14;
  - Windows 10/11, and Linux with glibc ≥ 2.34 (the PySide6 wheels' floor);
  - KiCad 9.0.7 minimum, with 10.x supported.
- **PySide6-Essentials only:** no QtCharts and no Addons.
- **Licence and strings:**
  - GPL-3.0-or-later and an English UI;
  - every user-facing string is a message code in `core.messages`' catalog;
  - §3.3's events stay language-neutral.
- **No push and no PyPI.** Both stay the owner's. Push-gated checks are written but not run, like P0-D and tier (b) in
  Stage 1.
- **The repo's working rules hold:**
  - test-first;
  - subagent-driven plans;
  - the privacy gate on every commit;
  - synthetic fixtures only, never the owner's boards.

## 5. Decisions

### 5.1 Process model

**What runs where.**
- **Never in the GUI process:** any function that reaches `runs.run_jobs`. So cost, run, verify, preview and calibrate run
  as the orchestrator, in a detached subprocess: `python -X utf8 -I -m kicad_rf_studio <command> PROJECT --run-dir DIR`.
  - **Why:** `run_jobs` ties its workers to the process that creates them. On Windows, a job object kills them when that
    process ends. On Linux, `PR_SET_PDEATHSIG` fires when the creating thread ends. A run started inside the GUI would
    die with it (r2 §1).
- **Start flags:**
  - **Windows:** run `python.exe`, the sibling of the GUI's `pythonw.exe`, with `CREATE_NEW_PROCESS_GROUP |
    CREATE_NO_WINDOW`. Add `CREATE_BREAKAWAY_FROM_JOB`, with a fallback that starts without it.
  - **Linux:** `start_new_session=True`.
  - **Both:** stdin from the null device; stdout and stderr to `DIR/cli.log`. Stop writes `DIR/STOP`, which the
    orchestrator already honours.
- **In the GUI process:**
  - on a worker thread: `new`, loading results, and building the retune session;
  - on the GUI thread: the instant retune's chain update, which takes milliseconds, and the redraws.

**Tailing.** A 500 ms `QTimer` reads `events.jsonl` from a saved byte offset and holds back a partial last line. The same
tick checks `project.json`'s modification time and the lock. No `QFileSystemWatcher` (r2 §1).

**Re-attach.**
1. On start, the GUI reads the project's lock, which holds `{pid, run_dir, started}`.
2. It then reads `project.json`'s results and verify.
3. Finally it reads the end events in the project's run folders.

**When the lock is held:**
- A run the GUI did not start is shown read-only, with Stop.
- While any run holds the lock, Run, Verify, Apply and model edits are disabled.
- A stale lock offers `E_LOCKED`'s advice: wait, write `STOP`, or delete the lock.

### 5.2 Engine additions the GUI needs

Each item is a small, test-first engine task that changes no result:
1. `src/kicad_rf_studio/__main__.py`, so that `python -m kicad_rf_studio` runs the CLI.
2. `--run-dir DIR` on cost, run and verify. The folder is created if missing.
3. **An end event.** `cli.main` writes it in a `finally`, whenever a run folder is known: kind `end`, with the exit code
   and the project path. This amends §3.3's list of event kinds. It makes a refusal before the lock, and a STOP during
   setup, visible. It is also how a restarted GUI finds the last cost, since cost takes no lock.
4. cost's 2D readout, load notes and calibration lines as events, as well as printed lines.
5. `pipeline.new()` returning its notes. Today they are inline in `cli._new`.
6. A public `runs.lock_holder(path)`.
7. **Shared drawing.**
   - `write_outputs` is split into a pure `chain_results(...)` and the file writer.
   - A `draw_summary(fig, ...)` is shared by `summary.png` and the GUI.
8. `snap(value, series)`: the nearest E12 or E24 value in log space (IEC 60063).
9. **Calibration under the run folder's STOP.** On first use, cost calibrates in its own run folder today, so
   `DIR/STOP` cannot stop that phase. The calibration honours the caller's run folder.

The names are the builder's; the behaviour is fixed here.

### 5.3 Screens and flow

One main window holds every step, in the CLI's order. Tabs or a stepper are the builder's call.

**Project.**
- Open a `project.json`, or create one with New from a board.
- New mirrors `new`'s options and defaults:
  - the board file;
  - start and end as REF.PAD, with a pad picker fed by Stage 1's importer;
  - f0, harmonics, preset, stackup and lid height.
- `new`'s printed notes become a list in the window.
- A button handoff pre-fills the board and the pads.

**Cost.**
- Shows the 2D Z0 and εeff readout with its label, then the setup-only cost:
  - cells and the smallest cell;
  - dt and the limiting node;
  - time and RAM;
  - the dominant driver.
- It is shown before every run. It is reused while the `spec_hash` in its `model.json` matches the project's.
- Run asks for confirmation on it.

**Run.**
- Per-job progress, verdicts and messages, from the events.
- Stop.
- The end state, with its exit code and message.

**Results.**
- S11 and S21 over the band, with the f0 markers.
- Harmonic rejection.
- The Smith chart.
- The run's messages and warnings.
- Everything comes from the same data as `summary.png`.

**Retune.**
- Each part shows its value with a snapping control: off, E12 or E24, default E24. Free text is accepted. A part can
  instead take an S2P file, marked series or shunt.
- The plots update instantly, from an in-memory session built once and rebuilt when the results change.
- **Apply** stores the values by running `kicad-rf-studio retune PROJECT REF=VALUE ...` as a short subprocess, which
  writes the outputs as the CLI does.

**What-if.**
- While `RETUNE_VALIDATED` is False, every retuned plot and table carries the §7.6 label.
- The label is message `G_WHAT_IF`: `I_WHAT_IF`'s text, with "Check the final values with Verify" in place of the
  command.
- Next to it sit a Verify button and a "verify is stale" indicator, lit when the values or the model have changed since
  the last verify.

**Verify.**
- Runs `verify` detached, like `run`. Its comparison is shown next to the retuned result.
- It acts on the applied values, because the CLI's `verify` reads `project.json`. With unapplied retune changes,
  Verify asks to Apply first.
- It gets no separate cost confirmation: its own cost lines show live.

**Advanced.**
- `project.json`'s fields, with their defaults and units, edited in place.
- Saved with the project's existing writer.
- Disabled while the lock is held.
- A model change marks the results stale, exactly as the CLI does.

**About.**
- The version.
- The GPL-3.0-or-later notices (§5(d)).
- The runtime dependencies and their licences.
- Qt's About.

### 5.4 Plots

- **Library:** matplotlib's `FigureCanvasQTAgg` (matplotlib is already a dependency) and scikit-rf's Smith chart.
- **Drawing code:** the same as `summary.png`, through `draw_summary`.
- **Instant retune:** updates the lines with `set_data` and `draw_idle`, at fixed limits. Blitting is added only if a
  measured redraw on lpf915 exceeds 50 ms.
- **Threading:** matplotlib stays on the GUI thread. File outputs are written by the retune subprocess (Apply), never by
  a GUI worker thread.

### 5.5 The KiCad button

**The plugin.**
- An exec plugin. The `python` runtime cannot host the openEMS wheels: on Windows, KiCad 9 bundles Python 3.11.
- One action, `open`:
  - scope `pcb`, shown by default;
  - 24 and 48 px icons, for light and dark themes;
  - a relative entrypoint: `launch.cmd` on Windows, `launch.sh` (mode 0755) on Linux.
- **Identifier.** Letters and digits only, at least three segments, the first segment letters only. This passes 9.0.7's
  check, 10.x's stricter anchored check and the schema. Stage 2 uses `org.kicadrfstudio.app`. The final identifier is the
  owner's, tied to the account chosen before the first push.
- **Launcher.** It holds the absolute path of the app's environment, written at install time, and calls the helper. PATH
  is never used.

**The helper.** It is Qt-free and imports kicad-python. In order:
1. Connects with `KICAD_API_SOCKET` and `KICAD_API_TOKEN`, retrying on `AS_BUSY`.
2. Reads the board's folder and file name, the selection and KiCad's version.
3. Writes a handoff JSON to the per-user data folder: the board path, the selected pads' KIIDs and footprint
   references, KiCad's version, and `KICAD_API_SOCKET` and `KICAD_API_TOKEN`, so that a later Refill reaches the same
   KiCad.
4. Starts `kicad-rf-studio-gui --handoff FILE` fully detached, with null stdio:
   - Windows: `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`;
   - Linux: `start_new_session`.
5. Exits 0 within about 2 s, with nothing on stdout or stderr.

On failure it writes one stderr line, which KiCad 10 shows, and a line in `button.log`. This quiet contract is required:
KiCad 10 pipes the action's output and reads it only when the action exits.

**KiCad versions.**
- `get_version()` accepts major 9 or 10.
- `check_version()` is never called: it refuses any KiCad newer than kicad-python's build.
- `AS_UNHANDLED` and `AS_UNIMPLEMENTED` read as "not in this KiCad".

**Single instance.** The GUI owns a per-user `QLocalServer`. A second start forwards its handoff to the running window
and exits.

**From the selection to REF.PAD.**
- The selected pads' KIIDs are joined to Stage 1's `Pad.uuid`, from `load_board` on the saved file.
- A selected footprint narrows the pad picker.
- Two pads pre-fill start and end, with a swap. When the importer can tell, the connector side becomes the end.
- A KIID missing from the file means unsaved edits: the GUI says "save the board in KiCad and press the button again".

**Refill.**
- An explicit GUI action, "Refill zones and save in KiCad".
- It asks for confirmation first, because the save also writes every unsaved edit.
- It then runs `refill_zones(block=True)`, then `save()`, then re-imports.
- It replaces §10's deferred "zone refill through kicad-cli" (an amendment).
- This is the only way the GUI saves the board.

**Install.**
- `kicad-rf-studio install-kicad-plugin [--kicad 9.0|10.0] [--remove]` writes the plugin into each existing plugin
  folder, honouring `KICAD_DOCUMENTS_HOME`:
  - Windows: `<Documents>/KiCad/<ver>/plugins/`, using the known Documents folder (a OneDrive redirect included);
  - Linux: `~/.local/share/kicad/<ver>/plugins/`.
- It never edits KiCad's settings. It prints the one step the user must do: Preferences › Plugins › enable the KiCad API,
  then restart KiCad.

### 5.6 Dependencies and packaging

**Dependencies.** Both become core dependencies, as Stage 1 §3.4 says, with no `[gui]` extra:
- `PySide6-Essentials>=6.10.1,<7`: Python 3.14 support starts at 6.10.1.
- `kicad-python>=0.8,<0.9`: 0.8 is the first line that installs on Python 3.14.

A test asserts that importing `kicad_rf_studio.cli` or `kicad_rf_studio.worker` loads no PySide6 or kipy module.

**Entry points:** the existing console script, plus `[project.gui-scripts] kicad-rf-studio-gui`.

**Licensing.**
- pip fetches Qt, so the app redistributes none of it in v1.
- The About box shows the notices.
- NOTICE gains a section "Runtime dependencies (not included)".
- LGPL conveying duties start only with the deferred bundled build.

**Install.**
- The README's install section becomes:
  - the Windows steps, with a concrete venv at `%LOCALAPPDATA%\kicad-rf-studio\venv`;
  - the Linux steps;
  - then `setup-openems` and `install-kicad-plugin`.
- No installer script in Stage 2.

**Release check:** `tools/release_check.py` and a release-check workflow. It covers:
- a build from a clean clone, and an inspection of the wheel;
- an install in a fresh venv, with `pip check`;
- the offscreen GUI smoke test;
- `plugin.json` against the 9.0.7 and 10.x schemas and identifier rules;
- the privacy gate over the history and the built artifacts.

It is written now and run locally where it can be. The push-gated parts wait for the owner, like Stage 1's tiers (b) and
(c).

### 5.7 i18n

- GUI strings are message codes, with a `G_` prefix, in `core.messages`' catalog, rendered with `render()`.
- There are no `.ts` or `.qm` files for our strings.
- Qt's own dialogs will use the qtbase translations that the wheel ships, later.
- The pt-BR catalog follows v1.

### 5.8 Tests

- **Qt-free logic first:**
  - the launcher, the tailer, and the lock and re-attach logic;
  - the retune session and snapping;
  - the handoff, and the helper's contract, with a fake kipy;
  - the installer's files;
  - `plugin.json` against the bundled schema and both identifier rules.
- **Detached runs** in tests use a test-only CLI entry. It installs the suite's fake worker, then calls `cli.main`.
- **Widget smoke tests** run under `QT_QPA_PLATFORM=offscreen`, set in conftest. Each screen is built and driven through
  its main path on the fake worker. `widget.grab()` PNGs serve the controller's visual review and are not committed.
- **Import rules:**
  - no Qt in core, cli or worker;
  - no openEMS or CSXCAD in the GUI process;
  - no Qt in the helper.
- **pytest-qt** is added only if a test needs it.

### 5.9 Plans

Stage 2 runs as four plans. Each is subagent-driven and merged to main before the next is written.

1. **Plan 1: the engine hooks and the GUI core.**
   - §5.2's additions;
   - the dependencies and the gui-scripts entry;
   - the Qt-free launcher, tailer and re-attach;
   - a main window that opens a project, shows cost, starts, stops and re-attaches a run with live progress, and shows
     the results with the what-if label.
2. **Plan 2: the matching workflow.**
   - New from a board, with the pad picker;
   - the retune session, with snapping and S2P parts;
   - Apply;
   - Verify, with the stale indicator;
   - the advanced panel;
   - About.
3. **Plan 3: the KiCad button.**
   - the helper and the handoff;
   - single instance;
   - `install-kicad-plugin` for 9.0 and 10.x;
   - refill and save;
   - the KiCad 10 output contract;
   - the `plugin.json` checks.
4. **Plan 4: install and release.**
   - the README's install section;
   - NOTICE;
   - the release check;
   - the end-to-end check of §5.11.

The pt-BR catalog is the first plan after v1.

### 5.10 Amendments to the Stage 1 spec

These are A-13 onward. Each lands in the plan that implements it:
- the end event, in §3.3;
- `--run-dir` and `install-kicad-plugin`, in §3.2;
- the version pins, in §3.4;
- §10's zone refill, moved to the button's refill action.

### 5.11 Acceptance

Stage 2 is done when all of these hold:
1. **Plans merged.** All four plans are merged, with the suite green, the offscreen GUI tests included.
2. **One real run through the GUI.** The controller has driven one real run offscreen through the GUI's own code paths,
   reading each step's state from the window:
   - New on lpf915 (the repo's fixture) at Draft;
   - Cost;
   - Run, to its end event;
   - a retune with snapping;
   - Apply;
   - Verify.

   Its machine time is about the board's Draft run plus its verify. `cost` prints that estimate first.
3. **The launcher replayed.** The installed plugin's launcher has been replayed from a console-less parent, as in the
   pre-check, against a fake API endpoint:
   - it exits 0 quickly and quietly;
   - it writes the handoff;
   - it starts the GUI detached.
4. **The owner's click-through stays the owner's** (the toolbar click, on a real board). It does not block, like §9.6's
   GUI click.

## 6. Left to the builder

- Module, class and function names.
- The window's layout (tabs or a stepper), its widgets, and the icons' artwork.
- Message code names and texts, within §3.3's rules.
- The poll interval (0.5–1 s), the blitting threshold, and `cli.log`'s name.
- How each plan is cut into tasks.
- The Linux CI packages for offscreen Qt.
- Whether pytest-qt is ever needed.
- Whether Preview and Calibrate get buttons. They are optional in Stage 2.

Where this design and the code disagree, the code's tests and the Stage 1 spec win, and the controller rules on it in the
plan's ledger.

## 7. Owner items this work leaves open

Each item has the default this design applies:
- **Plugin identifier and folder name:** tied to the account chosen before the first push. Default:
  `org.kicadrfstudio.app`.
- **The GUI saving the board through the API.** Default: only through the confirmed refill-and-save action.
- **Cost before every run.** Default: always shown, reusing a matching cost.
- **Default snapping series.** Default: E24 for L and C, set per part.
- **PySide6 as a core dependency.** Default: yes (82 MB download, about 220 MB installed).
- **The what-if wording.** Default: §7.6's text, pointing to Verify.
- **Install source before PyPI.** Default: a GitHub release zip, after the push.
- **A one-command installer.** Default: none in Stage 2.
- **The v1 time policy** (Draft or Normal by default): unchanged from Stage 1.
- **Unchanged owner items:**
  - the toolbar click on a real board (about 2 min);
  - P0-C;
  - the engine redesign (A-9, A-10, r3's X-A run);
  - the identity rewrite and the deny-list review;
  - RFsim/NOTICE;
  - the first push and PyPI.
