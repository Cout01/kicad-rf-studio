# Stage 3 Plan 5: The GUI, the Button and the Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Open, retune, verify and compare antenna projects in the GUI, pre-fill New with a printed antenna from the KiCad button, document the antenna workflow in the README and the release check, and close Stage 3 with one antenna project run end to end through the window and its exit record.

**Architecture:**
- **The CLI's functions, composed once.** A pure `pipeline.antenna_lines` comes out of `antenna_outputs`, so the window's antenna lines are the CLI's by construction. `control.open_project` reads an antenna's far field, its source and the run's layout at its frequencies on the pool (`Opened.far`, `far_source`, `far_lay`), and the retune session reuses them, so an edit reads no file. `draw_antenna` returns its axes and `retrace_antenna` moves S11 in place for the blit, as v1's `draw_summary` and `retrace_summary` do; on the window's canvas it puts the six panels in one row and leaves the limits to the window's lines.
- **The window gains, nothing more:** New's Kind, Antenna footprint and Band rows, calling `cli.new_antenna` exactly as New calls `cli.new`; a Compare tab running `pipeline.compare_projects` on the pool into the base's own `compare/` folder; the button's antenna rules in `control.handed`. Then the README's antenna tutorial, one cheap release-check step, an opt-in real-run test, the controller's acceptance run and the Stage 3 exit record.

**Tech Stack:** Python ≥ 3.11 (dev venv 3.14.2), PySide6-Essentials (offscreen in tests), matplotlib's QtAgg canvas, numpy, h5py, scikit-rf; no new dependency. openEMS 0.37.0 and CSXCAD 0.7.0 in the workers only (Task 10's run). pytest (`openems` marker); `tools/catalog.py` (Babel, dev extra).

**Spec:**
- `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md` (binding): §5.12 item 5, that is §5.10, the README's antenna tutorial on the 2.4 GHz fixture, the release check and the Stage 3 exit record; §5.14 items 3 and 4; with §1, §3 (v1 byte for byte), §7 and §8.
- Stage 2's design `docs/superpowers/specs/2026-10-27-stage2-gui-and-button-design.md` (§5.1, §5.3, §5.5, §5.11) for the GUI's and the button's rules. The Stage 1 spec (A-1 to A-40) is not amended by this plan.
- Plans 1 to 4 (`docs/superpowers/plans/2026-10-29-stage3-plan1-far-field-engine.md`, `2026-10-29-stage3-plan2-antenna-project.md`, `2026-10-30-stage3-plan3-matching-and-comparison.md`, `2026-10-30-stage3-plan4-the-gates.md`) and their "Not in this plan"; the records `docs/validation/2026-10-30-antenna-matching-run.md`, `2026-11-01-p3-d.md`, `2026-11-01-p3-e.md`, and Stage 2's exit record `docs/validation/2026-10-29-stage2-exit.md` (the acceptance harness and the record's model).
- Research (git-ignored): `.superpowers/sdd/stage3-plan5-research/` r1 (the GUI), r2 (the button), r3 (docs and release), r4 (acceptance and exit).

**Branch:** `stage3-plan5`, from `main` at `bdab44a`. This plan is `docs/superpowers/plans/2026-11-01-stage3-plan5-gui-button-docs.md`. Commands run from the repo root with `.venv/Scripts/python`. Line references are `main`'s at `bdab44a`; find a moved line by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage3-plan5 main`; `git diff --stat bdab44a HEAD -- src tests tools po pyproject.toml` prints nothing.
2. Commit this plan on the branch.
3. After Task 11: the whole-branch review, a local fast-forward merge into `main`, the branch deleted. Nothing is pushed.

## Global Constraints

- **v1 byte for byte** (design §3, §4): v1's projects, model specs, `spec_hash`, `model.json`, `project.json`, `new`'s lines and `results/` files stay as `tests/test_golden_v1.py` and the v1 suites pin them. A task that moves a pin is wrong: stop for a ruling, never re-record.
- **The CLI's outputs unchanged but the snap:** every CLI line stays as it is, and every file but the antenna results computed at the far field's frequencies: the five antenna CSVs (farfield.csv, antenna_summary.csv, verify_farfield.csv, verify_summary.csv, compare.csv) then hold project.json's exact `far_field.f_hz`, and the values computed there (S11, Zin, P_acc, P_inc, η, the gains) and the far-field panels of antenna_summary.png and verify_summary.png move in their last digits (Task 1). `tests/test_match_antenna.py`, `tests/test_run_antenna.py` and `tests/test_compare.py` stay green with no edit: `git diff --stat bdab44a -- tests/test_match_antenna.py tests/test_run_antenna.py tests/test_compare.py` prints nothing at every commit.
- **Antenna only:** every new branch tests `core.project.antenna(data)`. v1's GUI stays as it is but for two rulings: a selected module or chip footprint's refusal on a press (Task 7) and G_RESULTS_WRITE's wording (Task 6). Advanced's Default column, capped at 320 px (Task 4), keeps v1's widths, which stay far under the cap.
- **openEMS in workers only** (Stage 1 §3.1): the CLI, the orchestrator, `core.post`, the GUI process and pytest's own process never import openEMS or CSXCAD; each window test of Tasks 4 to 7 and 9 ends its GUI work with `assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules`.
- **Qt offscreen in tests** (`tests/conftest.py`), no modal dialog in a test: `QFileDialog.getOpenFileName` and `MainWindow.ask` are monkeypatched; the pool's work is awaited with `.result(timeout=…)` or `.exception(timeout=…)`, then `w.tick()`.
- **Messages:** every new or changed user-facing string is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, compiled by `.venv/Scripts/python tools/catalog.py` in the same task (run it, set each empty msgstr, run it again). Templates are unique (`tests/test_sexpr.py`); a G_ wording of a CLI line keeps a subset of its params and drops terminal syntax (`tests/test_gui_control.py::test_every_gui_wording_keeps_its_cli_params_and_drops_terminal_syntax`); a G_ message that names a widget gets a `QUOTED` entry in `tests/test_sexpr.py`, its pt-BR holding the widget label's msgstr word for word; numbers keep the decimal point; pt-BR keeps the catalog's terms (ilha, componente em série, componente shunt, ajuste, execução, verificação, predefinição, cadeia de casamento, campo distante).
- **Tests:** test-first. Tier (a) never runs openEMS, KiCad, the network or a build: the fake CLI (`FAKE_PREFIX`), the fake worker (`calibrated`, `KRS_FAKE=network`), handoff files from `press`. `KrsError` tests check `.code` and `.params`. Tests never touch a real KiCad folder, the real Documents folder, KiCad's settings or the real data folder (`no_kicad`, `fake`), and never write under `tests/fixtures`. Window tests live in `tests/test_gui.py`, which also runs in pt-BR.
- **Full suite** before every commit: `.venv/Scripts/python -m pytest -q`, about 20 minutes, alone, in the background, waited on. After a task that touches `src/kicad_rf_studio/gui/` or a message, also, in PowerShell, `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q; Remove-Item Env:KRS_TEST_LANGUAGE`: the window's 1200 × 800 test (`test_the_window_fits_1200_by_800_and_its_tabs_need_no_scrolling`) and the antenna figure's 100 px panels (Task 4) hold in both languages.
- **The gates' folder** `<GATES>` (`krs-gates` in the user's home) is read, never written: Task 10 reads its verified pour in place, and the controller deletes the folder after the merge (Task 11).
- **Git:** no push; the pre-commit privacy gate runs on every commit, never `--no-verify`; no commit message carries a co-author line; the messages as given. No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name: `<openEMS folder>`, `<GATES>`, `<KRS_E2E_DIR>`, `<run folder>`.
- **Files and workflow:** every new `.py` starts with `# SPDX-License-Identifier: GPL-3.0-or-later`; code and docs in English. `graphify query "<question>"` before reading code; `graphify update .` after each commit. Ponytail: reuse `cli.new_antenna`, `antenna_kinds`, `classify`, `draw_antenna`, `compare_projects`, `antenna_result`, the pool, `sentences()`, the fake worker, `press` and Stage 2's real-run harness; the standard library and the installed dependencies; a `ponytail:` comment on each corner cut with a known ceiling. Python only with a script, `-c` or `-m`: never a bare interactive `python`.

## Review Focus

1. **The antenna figure on the GUI thread: a retune edit that redraws it in full, or panels that collapse at 1200 × 800.** A full draw of the 1 × 2 antenna figure measured 238–302 ms (r1) and the six-panel one is more; an edit must move S11, its Smith locus and dots in place and blit. And the 2 × 3 grid under its title and five-line limits foot collapses on the Results canvas (1178 × 403 px with the parts' rows: 28 px axes in English, 13 px and constrained layout given up in pt-BR; 76 and 60 px without the foot), so the window's figure stands in one row with no foot (113 px axes and up in both languages, with or without the parts' rows; probed by three reviews and the reviser). Check: Task 1's `test_the_figures_curve_moves_in_place_and_the_windows_figure_stands_in_one_row` (the 1 × 6 grid, no foot); Task 4's `test_verify_brings_an_antennas_far_field_and_the_retune_blits_on_its_six_panels` (no `canvas.draw`, the fastest of three edits under 50 ms, the axes unchanged, every axes at least 100 px tall), `test_an_antennas_retune_takes_0r_and_open_refuses_the_converse_and_blits` on the 1 × 2 figure and `test_an_antenna_shows_s11_the_smith_chart_its_far_field_and_where_it_comes_from` (100 px, M = 0), each run in pt-BR too.
2. **A far field or a layout read on the GUI thread on each edit** (h5 and waves files; a frozen window over a slow disk). They are read once, on the pool, into `Opened`. Check: Task 3's `test_the_retune_session_of_an_antenna_gives_retunes_lines_and_reads_nothing` (`far_of`, `layout` and `current_verify` fail during the session) and Task 4's six-panel test (`pipeline.far_of`, `pipeline.layout`, `h5py.File` and `numpy.load` fail during the edits).
3. **The GUI's antenna lines drifting from the CLI's** (a second composition of s11_lines, the far field's lines and the what-if lines). One pure `antenna_lines` serves both. Check: the three protected test files, which pin antenna_outputs' lines, unedited and green; Task 2's `test_the_antenna_lines_are_its_outputs_lines_and_read_nothing_given_their_far_field` (antenna_lines' lines are the head of antenna_outputs'); Task 3's session lines equal to `pipeline.retune`'s for `L1=0R C2=open C3=open` after a verify.
4. **A stale verify read as current through a bypass** (`port_value` reads `0R` on an L or a C, and `open`, as None, so `0R` against `open` reads equal). Check: Task 3's `test_an_antennas_verify_is_stale_when_a_bypass_changes` (both ways; `0` against `0R` on an L and `1p` against `1pF` still current).
5. **A compare writing into the variant's folder, or against the wrong variant,** which may be another project's or the gates' (`compare_projects` writes to the working folder by default; the gates' d-ifa2g4_pi_dxp is verified at the same values as the pour). Check: Task 6's window test snapshots the variant's folder and run folder (mtimes unchanged, no `compare/` there) and writes into the base's `compare/`; Task 9's acceptance asserts the same on the gates' pour, after checking that it is the pour (its board file `ifa2g4_pi_pour.kicad_pcb`) verified at PI_VALUES.

---

## File structure

```
src/kicad_rf_studio/core/post/antenna.py, pipeline.py (far_of), core/project.py (far_field_hz), core/model/spec.py
  (antenna_t_max), cli.py; tests/test_post_antenna.py, tests/test_project.py, tests/test_antenna_lines.py (new)  # T1
src/kicad_rf_studio/pipeline.py (antenna_lines, antenna_outputs, s11_at, current_verify, run), runs.py;
  tests/test_antenna_lines.py, tests/test_runs.py                                                            # T2
src/kicad_rf_studio/gui/control.py, core/messages.py, po/pt_BR.po, the .mo; tests/test_gui_control.py, tests/test_sexpr.py # T3
src/kicad_rf_studio/gui/window.py (ResultsView, AdvancedView, show_project, retune), messages, po; tests/test_gui.py # T4
src/kicad_rf_studio/gui/control.py (GUI, _antennas, board_choices, BANDS), gui/window.py (NewForm, board_chosen,
  show_pads, create_project), messages, po; tests/test_gui_control.py, tests/test_gui.py, tests/test_sexpr.py  # T5
src/kicad_rf_studio/gui/control.py (compare), gui/window.py (CompareView, MainWindow), messages, po;
  tests/test_gui_control.py, tests/test_gui.py, tests/test_sexpr.py                                          # T6
src/kicad_rf_studio/gui/control.py (Handed, handed), gui/window.py (show_pads), messages, po;
  tests/test_gui_control.py, tests/test_gui.py, tests/test_sexpr.py                                          # T7
README.md, tests/test_repo.py, tools/release_check.py, tests/test_release_check.py                          # T8
tests/test_gui.py (the acceptance), README.md (Development setup)                                            # T9
the controller's runs; fixes in their owning files                                                           # T10
README.md (excerpts), docs/validation/<date>-stage3-exit.md, the Stage 3 design's Status line               # T11
```

The `.mo` is `src/kicad_rf_studio/locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo`; every task that adds a message commits it with `po/pt_BR.po` and `po/kicad_rf_studio.pot`.

---

### Task 1 [code]: The far field's exact frequencies, the figure's curve and window layout, and the band's defaults

**Files:**
- Modify: `src/kicad_rf_studio/core/post/antenna.py` (`far_field_of` :132-142, `_panels` :288-334, `draw_antenna` :337-347; new `retrace_antenna`); `src/kicad_rf_studio/pipeline.py` (`far_of` :856-864 and its callers at :616, :628, :998 and :1206); `src/kicad_rf_studio/core/project.py` (new `far_field_hz`, which `make_antenna_project` :148 uses); `src/kicad_rf_studio/core/model/spec.py` (new `antenna_t_max`, beside `pulse` :52); `src/kicad_rf_studio/cli.py` (`new_antenna` :198, :213-214).
- Create: `tests/test_antenna_lines.py`.
- Test: `tests/test_post_antenna.py`, `tests/test_project.py`.

**Interfaces:**
- Consumes: `read_far_field`, `port_powers`, `efficiencies`, `_markers`, `_db`, `pulse_band`, `pulse`, `air_gap`; the tests' `antenna_dict`, `band_grid`, `dip`, `far_of` (test_post_antenna's), `antenna_project`, `pi_run`, `calibrated`.
- Produces:
  - `core.post.antenna.far_field_of(paths: dict[str, Path], waves: Path, f_hz: Sequence[float] = ()) -> dict`: each grid's `.f` snapped to the nearest of `f_hz` within a relative 1e-6.
  - `pipeline.far_of(record: dict, project: dict | None = None) -> dict | None`: with `project`, its `far_field.f_hz` passed on; every pipeline caller passes the project.
  - `draw_antenna(fig, f, s11, project, far, name, label=None, gui=False) -> tuple`: `(ax11, ax_smith)`, `_panels`' return; with `gui` (the window's canvas), the far field's panels in one row (`_panels(..., one_row=True)`) and no ANTENNA_LIMITS at the foot.
  - `retrace_antenna(axes: tuple, f: np.ndarray, s11: np.ndarray, project: dict) -> list`: moves and returns `[axes[0].lines[0], axes[1].lines[-2], axes[1].lines[-1]]`.
  - `core.project.far_field_hz(f_lo: float, f_hi: float) -> list[float]`; `core.model.spec.antenna_t_max(f_lo: float, f_hi: float) -> float`.

- [ ] **Step 1: Write the failing tests.** `tests/test_post_antenna.py` (imports gain `shutil`, `h5py` and `retrace_antenna`):

```python
def test_far_field_of_snaps_openems_float32_frequencies_to_the_projects(tmp_path):  # plan 3's deferred item; ruling 8
    exact = [2441750000.0, 2409277777.7777777]  # f0 and the next of the 2.4 GHz band's list: not round numbers
    for g in ("sphere", "elevation", "azimuth"):
        shutil.copyfile(FAR / f"{g}.h5", tmp_path / f"{g}.h5")
    with h5py.File(tmp_path / "sphere.h5", "r+") as h5:
        h5["nf2ff"].attrs["Frequency"] = np.array(exact, dtype=np.float32)  # as openEMS stores them: ...016, ...696
    paths = {g: tmp_path / f"{g}.h5" for g in ("sphere", "elevation", "azimuth")}
    far = far_field_of(paths, FAR / "waves.npz", exact)
    assert far["sphere"].f.tolist() == exact and far["elevation"].f.tolist() == [2449999872.0]  # 3e-3 away: kept
    rows = antenna_csv(far, np.full(2, 0.5 + 0j)).decode().splitlines()[1:]
    assert [row.split(",")[0] for row in rows] == ["2409277777.7777777", "2441750000.0"]  # the project's, ascending
    assert far_field_of(paths, FAR / "waves.npz")["sphere"].f.tolist() == [2441750016.0, 2409277696.0]  # none given


def test_the_figures_curve_moves_in_place_and_the_windows_figure_stands_in_one_row():  # design 5.10; rulings 1, 7
    d = antenna_dict()
    f = band_grid(d)
    k = [int(np.flatnonzero(f == v)[0]) for v in (2.4e9, 2.44175e9, 2.4835e9)]
    moved = (0.5 * dip(f, 2.45e9)).astype(complex)
    for far in (far_of(), None):
        fig = Figure()
        axes = draw_antenna(fig, f, dip(f).astype(complex), d, far, "proj", gui=True)
        lines = retrace_antenna(axes, f, moved, d)
        grid = [(1, 6) if far else (1, 2)] * len(fig.axes)  # the window's: one row, readable at 1200 x 800
        assert [ax.get_subplotspec().get_geometry()[:2] for ax in fig.axes] == grid
        assert not [t for t in fig.texts for code in ANTENNA_LIMITS if render(code) in t.get_text()]  # no foot
        assert len(fig.axes) == (6 if far else 2) and lines == [axes[0].lines[0], axes[1].lines[-2], axes[1].lines[-1]]
        assert np.array_equal(lines[0].get_ydata(), 20 * np.log10(np.abs(moved)))
        assert np.array_equal(lines[1].get_xdata(), moved.real) and np.array_equal(lines[2].get_ydata(), moved[k].imag)
```

  `tests/test_project.py` (imports gain `far_field_hz` and `from kicad_rf_studio.core.model.spec import antenna_t_max`):

```python
def test_the_bands_defaults_are_new_antennas():  # Stage 3 design 5.4, 5.5; the GUI's Advanced shows them (plan 5)
    assert far_field_hz(2.4e9, 2.4835e9) == [  # as <GATES>' verified pour holds them: compare's fingerprint
        2441750000.0, 2400000000.0, 2409277777.7777777, 2418555555.5555553, 2427833333.3333335, 2437111111.111111,
        2446388888.888889, 2455666666.6666665, 2464944444.4444447, 2474222222.2222223, 2483500000.0]
    bands = ((863e6, 870e6), (902e6, 928e6), (2.4e9, 2.4835e9))
    assert [antenna_t_max(*band) for band in bands] == [85e-9, 79e-9, 30e-9]
```

  `tests/test_antenna_lines.py`, new:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""The antenna's lines and files that the CLI and the GUI share (Stage 3 design 5.5–5.7, 5.10; plan 5)."""
import csv
import io

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_antenna import antenna_project
from test_match_antenna import pi_run


def test_an_antenna_csv_holds_the_projects_exact_far_field_frequencies(tmp_path, calibrated):  # ruling 8
    pj = antenna_project(tmp_path / "p")
    d = load_project(pj)
    save_project(pj, {**d, "far_field": {**d["far_field"], "f_hz": [2.44175e9, 2.4e9, 2.45e9]}})
    assert pipeline.run(pj) == 0  # the fake's transform records 2.45 GHz as float32: 2449999872 Hz
    summary = (pj.parent / "results" / "antenna_summary.csv").read_text(encoding="utf-8")
    assert [row["f_hz"] for row in csv.DictReader(io.StringIO(summary))] == ["2400000000.0", "2450000000.0"]
    far = (pj.parent / "results" / "farfield.csv").read_text(encoding="utf-8").splitlines()
    assert (far[1].split(",")[0], far[-1].split(",")[0]) == ("2400000000.0", "2450000000.0")


def test_every_far_field_read_takes_the_projects_frequencies(tmp_path, calibrated, monkeypatch):  # ruling 8
    pj = pi_run(tmp_path, monkeypatch)
    seen, real = [], pipeline.far_field_of
    monkeypatch.setattr(pipeline, "far_field_of",
                        lambda paths, waves, f_hz=(): seen.append(list(f_hz)) or real(paths, waves, f_hz))
    assert pipeline.verify(pj) == 0  # verify_farfield.csv and verify_summary.csv
    assert pipeline.retune(pj, [], lambda code, params: None) == 0  # the what-if η_tot
    assert pipeline.antenna_result(pj)["source"] == "T_VERIFY"  # compare.csv
    assert seen == [load_project(pj)["far_field"]["f_hz"]] * 3
```

  `2441750016.0` and `2409277696.0` are numpy's float32 of the two (the architect's probe). The fake's own fixture records 2449999872 and 2400000000 Hz, 1.5e-3 from the default list's nearest 2.4464 GHz, so `tests/test_run_antenna.py:86` keeps its `2449999872.0`, and on the default list only the spy sees a caller (verify's :1206, the what-if's :628, compare's :998) left without the project.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_antenna.py tests/test_project.py tests/test_antenna_lines.py -q`. Expected: FAIL (`cannot import name 'retrace_antenna'`, `cannot import name 'far_field_hz'`, `far_field_of() takes 2 positional arguments but 3 were given`, `2449999872.0` in the CSV).
- [ ] **Step 3: `core/post/antenna.py`.**
  - `far_field_of(paths, waves, f_hz=())`: each grid read, then its `.f` replaced (`dataclasses.replace`) by the nearest of `f_hz` wherever `np.isclose(nearest, f, rtol=1e-6, atol=0)`, else kept; P_acc and P_inc are then taken at the snapped sphere frequencies. Docstring gains: "`f_hz` (project.json's far_field.f_hz): openEMS stores the recorded frequencies as float32, up to about 128 Hz off at 2.4 GHz, so each is snapped to the nearest of them within a relative 1e-6 and keeps its recorded value otherwise; with none, none is snapped." Comment `# ponytail: a frequency within 1e-6 of none of f_hz keeps openEMS's float32 value; nothing records another today`.
  - `_panels(..., one_row=False) -> tuple`: with `one_row` and every curve's far field, the six panels on a 1 × 6 grid (`add_subplot(1, 6, n)`, n 1 to 6 as now) in place of 2 × 3; returns `(ax11, ax_smith)`, its docstring "…; with `one_row`, the far field's panels beside S11 and the Smith chart in one row. Returns the S11 axes and the Smith chart's."
  - `draw_antenna(..., gui=False) -> tuple`: `_panels(..., one_row=gui)`; the foot (`fig.supxlabel` of ANTENNA_LIMITS) only without `gui`; returns `_panels`' axes. Docstring gains "Returns the S11 and Smith axes, which retrace_antenna moves. With `gui` (plan 5's Results canvas) the far field's panels stand in one row and the limits are left to the window's lines, which end with them: at 1200 × 800 the 2 × 3 grid under its title and five-line foot collapses (probed: 28 px axes in English, none in pt-BR); antenna_png never passes it, so its bytes stay."
  - `retrace_antenna(axes, f, s11, project) -> list`, after `draw_antenna`: `set_data` of |S11| in dB (`_db`) against `f / 1e9` on `axes[0].lines[0]` (the band's level lines are drawn after the curve), of the locus on `axes[1].lines[-2]` and of its dots at `_markers(project, f)` on `axes[1].lines[-1]`; no draw, no rescale. Docstring: "Moves the curve that draw_antenna drew on `axes` (its return) to `s11` (F,) on `f`, as retrace_summary moves v1's (the GUI's instant retune, Stage 3 design 5.10): |S11| in dB, the S11 axes' first line; the Smith locus and its dots at f_lo, f0 and f_hi, the chart's last two lines. Returns those Line2D."
- [ ] **Step 4: The rest.**
  - `pipeline.far_of(record, project=None)`: `far_field_of(..., project["far_field"]["f_hz"] if project else ())`; docstring "with `project`, its far_field.f_hz, to which far_field_of snaps the recorded frequencies". Its callers pass the project: `far_of(results, project)` (:616), `far_of(v, project)` (:628), `far_of(record, project)` (:998), `far_of(data["verify"], project)` (:1206). The default keeps `tests/test_match_antenna.py:239`'s one-argument call unedited.
  - `core/project.py`: `far_field_hz(f_lo, f_hi)`, its body :148's expression moved verbatim, docstring "An antenna's far-field frequencies as `new` writes them (Stage 3 design 5.5): f0, the band's centre, then 10 evenly from f_lo to f_hi."; `make_antenna_project`'s far_field takes it.
  - `core/model/spec.py`: `antenna_t_max(f_lo, f_hi)`, docstring "An antenna's default T_max in s (Stage 3 design 5.4, A-28): 2·t0 + 60/f0 of its band's pulse (pulse_band, pulse), f0 the band's centre, rounded up to a whole ns."; it imports `pulse_band` from `core.project` (spec already imports from it; project cannot import spec). `cli.new_antenna` takes `t_max = antenna_t_max(f_lo, f_hi)` in place of :213-214, and imports `antenna_t_max` in place of `pulse`.
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_cli_antenna.py tests/test_match_antenna.py tests/test_run_antenna.py tests/test_compare.py -q`. Expected: PASS, the three protected files unedited.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "fix(antenna): the far field's float32 frequencies snapped to project.json's in every read, the summary figure's curve moved for a blit and its one-row layout for the window, and the band's defaults as helpers (Stage 3 design 5.5, 5.10)"
graphify update .
```

---

### Task 2 [code]: The antenna's lines, shared by the CLI and the GUI, and the small guards

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py` (`s11_at` :565-571, `current_verify` :574-583, `antenna_outputs` :586-643, `run`'s docstring :647-659); `src/kicad_rf_studio/runs.py` (`openems_versions` :74-80).
- Test: `tests/test_antenna_lines.py`, `tests/test_runs.py`.

**Interfaces:**
- Consumes: Task 1's `far_of(record, project)`; `chain_results`, `s11_lines`, `far_field_lines`, `eta_what_if_lines`, `layout`, `command_line`, `antenna_png`; the tests' `pi_run` (test_match_antenna), `antenna_project`, `calibrated`.
- Produces:
  - `pipeline.antenna_lines(path: Path, project: dict, res: ChainResults, *, errors_as_lines: bool = False, far=_UNREAD, far_lay: Layout | None = None) -> tuple[list[tuple[str, dict]], dict | None, Layout | None]`: the lines, the far field they read, and the run's layout at its frequencies when the what-if took or built one.
  - `pipeline.s11_at(path: Path, project: dict, f: np.ndarray, lay: Layout | None = None) -> tuple[np.ndarray, np.ndarray]`.
  - `pipeline.current_verify(project)`: None without `results`.
  - `runs.openems_versions()` raising E_OPENEMS_MISSING for a probe that times out or prints other than two versions.

- [ ] **Step 1: Write the failing tests,** appended to `tests/test_antenna_lines.py` (imports gain `numpy as np`, `pytest`, `KrsError`, `ANTENNA_LIMITS` and `from kicad_rf_studio.core.post.waves import layout`):

```python
def fail(*args, **kwargs):
    raise AssertionError("read again")


def gone(*args, **kwargs):  # a far-field file moved or deleted after current_verify looked
    raise KrsError("E_RESULTS_WAVES", path="P")


def test_the_antenna_lines_are_its_outputs_lines_and_read_nothing_given_their_far_field(
        tmp_path, calibrated, monkeypatch):  # Stage 3 design 5.7, 5.10; Review Focus 3
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.verify(pj) == 0
    d = load_project(pj)
    res = pipeline.chain_results(pj, d, errors_as_lines=True)
    lines, far, far_lay = pipeline.antenna_lines(pj, d, res, errors_as_lines=True)
    pngs, png = [], pipeline.antenna_png
    monkeypatch.setattr(pipeline, "antenna_png", lambda *args: pngs.append(args[3]) or png(*args))
    outputs = pipeline.antenna_outputs(pj, d, "x", errors_as_lines=True)
    assert outputs[:len(lines)] == lines and [c for c, _ in outputs[len(lines):]] == [
        "I_WHAT_IF", "I_OUTPUTS", *ANTENNA_LIMITS]
    assert pngs == [None]  # verify's far field goes into no file of the run's (design 5.7): two panels, as now
    assert [c for c, _ in lines].count("I_ANTENNA_ETA_WHAT_IF") == 2  # the fake verify's far field: 2 frequencies
    assert np.array_equal(far["sphere"].f, pipeline.far_of(d["verify"], d)["sphere"].f)
    assert far_lay.f.tolist() == sorted(far["sphere"].f.tolist())
    for name in ("far_of", "current_verify", "layout"):
        monkeypatch.setattr(pipeline, name, fail)
    again, same, lay = pipeline.antenna_lines(pj, d, res, far=far, far_lay=far_lay)
    assert again == lines and same is far and lay is far_lay
    assert pipeline.antenna_lines(pj, d, res, far=None)[0][-1] == (
        "I_ANTENNA_NO_FAR_FIELD", {"command": pipeline.command_line("kicad-rf-studio", "verify", str(pj))})


def test_a_runs_far_field_is_in_its_lines_and_one_that_cannot_be_read_is_a_line(tmp_path, calibrated, monkeypatch):
    pj = antenna_project(tmp_path / "m0")  # M = 0: its run is its far-field run (design 5.5)
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    res = pipeline.chain_results(pj, d)
    lines, far, far_lay = pipeline.antenna_lines(pj, d, res)
    assert [c for c, _ in lines].count("I_ANTENNA_FAR_FIELD") == 2 and far_lay is None and len(far["sphere"].f) == 2
    monkeypatch.setattr(pipeline, "far_of", gone)
    with pytest.raises(KrsError):
        pipeline.antenna_lines(pj, d, res)
    lines, far, _ = pipeline.antenna_lines(pj, d, res, errors_as_lines=True)
    assert lines[-1] == ("E_RESULTS_WAVES", {"path": "P"}) and far is None
    assert "I_ANTENNA_FAR_FIELD" not in [c for c, _ in lines]


def test_the_what_ifs_far_field_reads_in_its_try(tmp_path, calibrated, monkeypatch):  # plan 3's deferred minor
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.verify(pj) == 0
    monkeypatch.setattr(pipeline, "far_of", gone)
    lines = pipeline.antenna_outputs(pj, load_project(pj), "x", errors_as_lines=True)
    codes = [c for c, _ in lines]
    assert ("E_RESULTS_WAVES", {"path": "P"}) in lines and "I_ANTENNA_ETA_WHAT_IF" not in codes
    assert codes[-6:] == ["I_OUTPUTS", *ANTENNA_LIMITS]  # the files and the limits still come


def test_s11_at_takes_the_layout_it_is_given_and_current_verify_needs_results(tmp_path, calibrated, monkeypatch):
    pj = pi_run(tmp_path, monkeypatch)
    d = load_project(pj)
    f = np.array([2.45e9, 2.4e9])  # not ascending: the answer comes back in f's order
    s11, p = pipeline.s11_at(pj, d, f)
    lay = layout(d, d["results"], np.sort(f))
    monkeypatch.setattr(pipeline, "layout", fail)
    again = pipeline.s11_at(pj, d, f, lay)
    assert np.array_equal(again[0], s11) and np.array_equal(again[1], p)
    assert pipeline.current_verify({"verify": {"base_hash": "M", "values": {}}}) is None  # never a KeyError
```

  `tests/test_runs.py`:

```python
@pytest.mark.parametrize("probe", [subprocess.TimeoutExpired(["python"], 120),  # a probe that hung
                                   subprocess.CompletedProcess([], 0, "0.37.0\n", "")])  # one word printed
def test_a_probe_that_hangs_or_prints_one_version_reads_as_openems_missing(monkeypatch, probe):  # plan 3's minor
    def run(cmd, **kw):
        if isinstance(probe, Exception):
            raise probe
        return probe

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(KrsError) as e:
        runs.openems_versions()
    assert (e.value.code, e.value.params) == ("E_OPENEMS_MISSING", {"python": sys.executable,
                                                                   "command": runs.install_command()})
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_antenna_lines.py tests/test_runs.py -q`. Expected: FAIL (`module 'kicad_rf_studio.pipeline' has no attribute 'antenna_lines'`; `s11_at() takes 3 positional arguments`; current_verify's `KeyError: 'results'`; the probe's TimeoutExpired raised).
- [ ] **Step 3: `pipeline.antenna_lines`,** after `current_verify`, and `antenna_outputs` on it. The branch order, the sentinel and the try's scope are what the tests leave open:

```python
_UNREAD = object()  # antenna_lines' far field when its caller read none (None, read, is "none")


def antenna_lines(path, project, res, *, errors_as_lines=False, far=_UNREAD, far_lay=None):
    lines = [*res.lines]
    run_far = bool(project["results"].get("far_field"))
    if res.chain is None:
        return lines, None, None
    lines += s11_lines(project, res.lay.f, res.chain[:, 0, 0])
    if not (run_far or res.refs):
        return lines, None, None
    try:  # the far field's whole read: a run or verify folder moved meanwhile is one line (ruling 9)
        if far is _UNREAD:
            record = project["results"] if run_far else current_verify(project)
            far = record and far_of(record, project)
        if run_far:
            lines += far_field_lines(far) if far else []
        elif far:
            # ponytail: η_rad from verify's ideal network (no package model), the network assumed not to radiate nor
            # to change the board's own loss; the line says what-if
            if far_lay is None:
                far_lay = layout(project, project["results"], np.sort(far["sphere"].f))
            lines += eta_what_if_lines(far, s11_at(path, project, far["sphere"].f, far_lay)[1])
        else:
            lines.append(("I_ANTENNA_NO_FAR_FIELD", {"command": command_line("kicad-rf-studio", "verify", str(path))}))
    except KrsError as err:  # far_of's, layout's or s11_at's E_RESULTS_WAVES
        if not errors_as_lines:
            raise
        lines.append((err.code, err.params))
        far = far_lay = None
    return lines, far, far_lay
```

  The try holds the far field's whole read, current_verify to s11_at, one step wider than ruling 9's far_of: layout and s11_at read the run's waves that chain_results has just read, so only a folder moved between the two lands there, as one line. The ponytail comment is antenna_outputs' own (:626-627), moved with its branch.
  Docstring: "An antenna's lines (Stage 3 design 5.5–5.7), no file written: what antenna_outputs reports before its label and files, and what the GUI shows on a read and on each retune: chain_results' `res` lines (I_BASIS up to the indicators); with a chain, s11_lines on its S11, then the run's far field's far_field_lines (results.far_field, M = 0), or with part ports eta_what_if_lines of a current verify's far field with this chain's P_layout at its frequencies (s11_at on `far_lay`, the run's layout there, ascending, built when None), else I_ANTENNA_NO_FAR_FIELD, which offers `verify`. `far` stands for that far field when given (None: there is none); else it is read (far_of; current_verify first with part ports). A KrsError on that read is raised, or, with `errors_as_lines`, the last line in place of those lines. Returns the lines, the far field they read (None without one) and, for the what-if, the layout at its frequencies."
  `antenna_outputs`: its lines become `lines, far, _ = antenna_lines(path, project, res, errors_as_lines=errors_as_lines)`; the run's far field, `far if results.get("far_field") else None`, alone writes farfield.csv and antenna_summary.csv (with `s11_at(path, project, far["sphere"].f)[0]`, outside any try, as now) and goes to `antenna_png` (positional, as now; verify's far field goes into no file, design 5.7); then I_WHAT_IF, the write, I_OUTPUTS or E_RESULTS_WRITE and ANTENNA_LIMITS as now. Its docstring says its lines are antenna_lines'.
- [ ] **Step 4: The guards.**
  - `s11_at(path, project, f, lay=None)`: a given `lay`, the run's layout at `np.sort(f)`, stands in for the one it builds; docstring "A given `lay` (the run's layout at f ascending, which the GUI's retune session holds, plan 5) stands in for it."
  - `current_verify`: None when project.json has no `results` (`project.get("results")`), before its base_hash comparison; docstring "…; None without results either".
  - `run`'s docstring gains, before its last sentence: "An antenna's run (Stage 3) saves its results with far_field null and its settings fingerprint, taken before the jobs; with no part port it then transforms its far field and saves again, a transform that fails being an E_ line (_run); its outputs are antenna_outputs'."
  - `runs.openems_versions`: a `subprocess.TimeoutExpired`, and a ValueError from an output that is not two words, raise E_OPENEMS_MISSING with the same params as a non-zero exit; docstring "Raises E_OPENEMS_MISSING, also for a probe that times out or prints other than the two versions."
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_match_antenna.py tests/test_run_antenna.py tests/test_compare.py tests/test_run.py tests/test_golden_v1.py -q`. Expected: PASS; `git diff --stat bdab44a -- tests/test_match_antenna.py tests/test_run_antenna.py tests/test_compare.py` prints nothing.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "refactor(antenna): the antenna's lines out of its outputs, shared by the CLI and the GUI; s11_at takes a layout, current_verify needs results, the what-if's far field reads in its try, and a hung or odd openEMS probe is E_OPENEMS_MISSING (Stage 3 design 5.7, 5.10)"
graphify update .
```

---

### Task 3 [code]: control opens, retunes and verifies an antenna, and reads Advanced's antenna data

**Files:**
- Modify: `src/kicad_rf_studio/gui/control.py` (imports :20-27, `GUI` :31-37, `Opened` :181-198, `open_project` :201-233, `retuned` :335-351, `verify_stale` :378-392, `UNITS` :478-481, `fields` :494-511); `src/kicad_rf_studio/core/messages.py`; `po/*`; the `.mo`.
- Test: `tests/test_gui_control.py` (`test_an_antenna_project_is_refused_until_plan_5` :428-434 replaced), `tests/test_sexpr.py` (`QUOTED`).

**Interfaces:**
- Consumes: Task 2's `antenna_lines`; Task 1's `far_field_hz`, `antenna_t_max`; `core.geometry.region.air_gap`, `ANTENNA_BOUNDARY`, `FAR_FIELD_STEP`, `bypass`; the tests' `pi_run`, `antenna_project`, `antenna_dict`.
- Produces:
  - `Opened` gains `far: dict | None = None` (the far field the plot shows), `far_source: tuple[str, str] | None = None` (`("T_RUN" | "T_VERIFY", that run's run_dir)`) and `far_lay: Layout | None = None` (`core.post.waves.Layout`).
  - `retuned(path, project, stored, rows, far: dict | None = None, far_lay: Layout | None = None) -> pipeline.ChainResults`.
  - `verify_stale(project, rows)` reading an antenna's bypasses.
  - `fields(data)` with an antenna's defaults; `UNITS` gains `"band.f_lo_hz"`, `"band.f_hi_hz"`, `"far_field.f_hz"` (G_UNIT_HZ), `"air_gap_mm"` (G_UNIT_MM) and `"far_field.step_deg"` (G_UNIT_DEG).
  - `GUI` gains `"E_RETUNE_SHORT_SHUNT": "G_RETUNE_SHORT_SHUNT"`, `"E_RETUNE_OPEN_SERIES": "G_RETUNE_OPEN_SERIES"`, `"E_RETUNE_ANTENNA_VALUE": "G_RETUNE_ANTENNA_VALUE"`, `"I_ANTENNA_NO_FAR_FIELD": "G_ANTENNA_NO_FAR_FIELD"`.

- [ ] **Step 1: Write the failing tests,** in `tests/test_gui_control.py` (imports gain `ANTENNA_LIMITS`, `from test_cli_antenna import antenna_project` and `from test_match_antenna import pi_run`); the plan-2 refusal test goes:

```python
def test_an_antenna_project_opens_with_its_far_field_and_where_it_comes_from(tmp_path, calibrated):  # design 5.10
    from test_project import antenna_dict
    p = tmp_path / "unread" / "project.json"
    p.parent.mkdir()
    save_project(p, antenna_dict())  # its board is not beside it: the read stops there, Advanced still gets it
    unread = control.open_project(p)
    assert unread.problem[0] == "E_BOARD_UNREADABLE" and unread.stored == antenna_dict()
    assert unread.board == board_file(p, antenna_dict()) and unread.far is None
    pj = antenna_project(tmp_path / "m0").resolve()
    assert pipeline.run(pj) == 0  # M = 0: its run is its far-field run
    opened, d = control.open_project(pj), load_project(pj)
    assert (opened.problem, opened.results.refs, opened.far_lay) == (None, [], None)
    assert opened.far_source == ("T_RUN", d["results"]["run_dir"]) and len(opened.far["sphere"].f) == 2
    outputs = pipeline.antenna_outputs(pj, d, "x", errors_as_lines=True)
    n = len(opened.results.lines)
    assert outputs[:n] == opened.results.lines and [c for c, _ in outputs[n:]] == ["I_OUTPUTS", *ANTENNA_LIMITS]
    assert opened.stored == d and opened.board == board_file(pj, d)


def test_the_retune_session_of_an_antenna_gives_retunes_lines_and_reads_nothing(
        tmp_path, calibrated, monkeypatch):  # design 5.7, 5.10; Review Focus 2, 3
    pj = pi_run(tmp_path, monkeypatch).resolve()
    assert pipeline.verify(pj) == 0
    opened, d = control.open_project(pj), load_project(pj)
    assert opened.far_source == ("T_VERIFY", d["verify"]["run_dir"])
    assert opened.far_lay.f.tolist() == sorted(opened.far["sphere"].f.tolist())
    rows = [replace(row, value=value) for row, value in
            zip(control.rows(d, pj.parent, opened.results.refs), ("0R", "open", "open"))]  # the feed line alone
    with monkeypatch.context() as m:  # read once, on the pool: an edit reads no far field and no waves
        for name in ("far_of", "layout", "current_verify"):
            m.setattr(pipeline, name, lambda *a, **k: 1 / 0)
        res = control.retuned(pj, opened.project, opened.results, rows, opened.far, opened.far_lay)
    lines = []
    assert pipeline.retune(pj, ["L1=0R", "C2=open", "C3=open"], lambda c, p: lines.append((c, p))) == 0
    assert lines[:len(res.lines)] == res.lines and [c for c, _ in res.lines].count("I_ANTENNA_ETA_WHAT_IF") == 2
    assert [c for c, _ in lines[len(res.lines):]] == ["I_WHAT_IF", "I_OUTPUTS", *ANTENNA_LIMITS]
    bad = control.retuned(pj, opened.project, opened.results, [replace(rows[0], value="open")], opened.far,
                          opened.far_lay)
    assert (bad.chain, bad.lines) == (None, [("E_RETUNE_OPEN_SERIES", {"ref": "L1"})])
    assert control.text(*bad.lines[0]) == render("G_RETUNE_OPEN_SERIES", ref="L1")
    none = control.retuned(pj, opened.project, opened.results, rows)  # no far field given: none, nothing read
    assert ("I_ANTENNA_NO_FAR_FIELD" in [c for c, _ in none.lines]
            and control.text("I_ANTENNA_NO_FAR_FIELD", {"command": "x"}) == render("G_ANTENNA_NO_FAR_FIELD"))


def test_an_antennas_verify_is_stale_when_a_bypass_changes(tmp_path):  # design 5.7; Review Focus 4
    project = load_project(antenna_project(tmp_path / "pi", FIX / "ifa2g4_pi.kicad_pcb"))
    project = {**project, "results": {"model_hash": "M"},
               "verify": {"base_hash": "M", "values": {"L1": "0R", "C2": "open", "C3": "1pF"}, "run_dir": "v"}}

    def stale(l1, c2, c3):
        return control.verify_stale(project, [control.Row(ref, value, "", "series")
                                              for ref, value in (("L1", l1), ("C2", c2), ("C3", c3))])

    assert stale("0R", "open", "1pF") is None and stale("0", "OPEN", "1p") is None  # an L of 0 is a short
    assert stale("open", "open", "1pF") == stale("0R", "0R", "1pF") == "G_VERIFY_STALE"  # 0R against open
    assert stale("0R", "open", "1.2pF") == "G_VERIFY_STALE"


def test_advanced_shows_an_antennas_fields_with_its_own_defaults_and_units():  # design 5.10; ruling 5
    from test_project import antenna_dict
    d = antenna_dict()
    by = {f.name: f for f in control.fields(d)}
    assert not {"kind", "copper", "harmonics", "band_factor"} & set(by)  # sheet copper is not offered (A-35)
    assert {name: (by[name].default, by[name].unit) for name in (
        "t_max_s", "region.expand_h", "lid", "air_gap_mm", "boundary", "far_field.step_deg", "band.f_lo_hz")} == {
        "t_max_s": ("3e-08", "G_UNIT_S"), "region.expand_h": ("6.0", "G_UNIT_SUBSTRATE"), "lid": ("true", None),
        "air_gap_mm": ("31.228381", "G_UNIT_MM"), "boundary": ('"pml_8"', None),
        "far_field.step_deg": ("5", "G_UNIT_DEG"), "band.f_lo_hz": ("", "G_UNIT_HZ")}
    far = by["far_field.f_hz"]
    assert json.loads(far.default) == d["far_field"]["f_hz"] and far.unit == "G_UNIT_HZ"
    broken = {f.name: f for f in control.fields({**d, "band": "x"})}  # a hand edit Advanced is there to fix
    assert (broken["t_max_s"].default, broken["air_gap_mm"].default, broken["boundary"].default) == ("", "", '"pml_8"')
    v1 = {f.name: f.default for f in control.fields(lpf())}
    assert (v1["t_max_s"], v1["region.expand_h"], v1["lid"]) == ("4e-08", "3.0", "null")  # v1's as before
```

  `tests/test_sexpr.py`'s `QUOTED` gains `"G_RETUNE_SHORT_SHUNT": ("G_COL_VALUE",)`, `"G_RETUNE_OPEN_SERIES": ("G_COL_VALUE",)` and `"G_ANTENNA_NO_FAR_FIELD": ("G_VERIFY",)`.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_sexpr.py -q`. Expected: FAIL (E_PROJECT_SCHEMA for the antenna project, `Opened` has no `far_source`, `retuned()` takes 4 positional arguments, the missing codes).
- [ ] **Step 3: `gui/control.py`.**
  - `open_project`: the E_PROJECT_SCHEMA guard (:212-214) and the antenna nulling of `stored` and the board file (:229-230) go, with their ponytail comments; `SCHEMA` and `SCHEMA_ANTENNA` leave the imports. After `chain_results`, for an antenna: `lines, far, far_lay = pipeline.antenna_lines(path, project, results, errors_as_lines=True)`, `results = replace(results, lines=lines)`, and the source `("T_RUN", project["results"]["run_dir"])` when results.far_field is set, else `("T_VERIFY", project["verify"]["run_dir"])`, None without a far field. Docstrings: Opened's "…the far field the plot shows (`far`: the run's with no part port, else the current verify's; None without one), its `far_source` (T_RUN or T_VERIFY, and its run folder) and `far_lay`, the run's layout at its frequencies for the what-if η_tot, all read here, on the pool (Stage 3 design 5.10)"; open_project's "an antenna's lines are pipeline.antenna_lines', the CLI's". Comment `# ponytail: a far-field file of another layout (read_far_field's ValueError) reads as E_INTERNAL for the whole read`.
  - `retuned(..., far=None, far_lay=None)`: for an antenna, the chain's lines become `pipeline.antenna_lines(path, new, res, errors_as_lines=True, far=far, far_lay=far_lay)[0]`, `new` being the assigned project; the docstring names `far` and `far_lay` (Opened's) and says an antenna's session reads no file.
  - `verify_stale`: for an antenna, a value reads as `bypass(ref, text)` when that is not None, else `port_value(ref, text)`; v1's reading unchanged. Docstring gains "an antenna's 0R and open read as the bypasses they are (Stage 3 design 5.7), which port_value reads as None".
  - `fields`: for an antenna, `kind` and `copper` are left out with schema, results and verify; the defaults gain `lid` true, `region.expand_h` REACH_H, `boundary` ANTENNA_BOUNDARY and `far_field.step_deg` FAR_FIELD_STEP; `t_max_s`, `air_gap_mm` and `far_field.f_hz` are `antenna_t_max(f_lo, f_hi)`, `air_gap(f_lo)` and `far_field_hz(f_lo, f_hi)` of its band, computed under `contextlib.suppress(Exception)` so that a band that does not read leaves them without a default, never v1's T_max (`# a hand-edited band that does not read: its defaults are left out, as Advanced must open it`). v1's defaults unchanged.
  - The imports gain `Layout` (core.post.waves), `bypass` (core.kicad.values), `air_gap` (core.geometry.region), `antenna_t_max` (core.model.spec) and `ANTENNA_BOUNDARY`, `FAR_FIELD_STEP` and `far_field_hz` (core.project).
- [ ] **Step 4: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| G_RETUNE_SHORT_SHUNT | {ref} joins the antenna's chain to {net}: 0 Ω there would short the chain to {net}. In the Value column, 0R replaces a series part with a short, and open removes a part like this one. | {ref} liga a cadeia da antena a {net}: 0 Ω ali poria a cadeia em curto com {net}. Na coluna Valor, 0R troca um componente em série por um curto, e open retira um componente como este. |
| G_RETUNE_OPEN_SERIES | {ref} is a series part of the antenna's chain: open there would cut the antenna off its feed. In the Value column, 0R replaces it with a short; open removes a shunt part. | {ref} é um componente em série da cadeia da antena: em aberto ali, ele separaria a antena da alimentação. Na coluna Valor, 0R o troca por um curto; open retira um componente shunt. |
| G_RETUNE_ANTENNA_VALUE | Cannot read "{value}" as the value of {ref}: on an antenna's chain a C, L or R takes a value in its own unit (4.7pF, 4p7, 15nH, 50R), 0R replaces a series part with a short and open removes a shunt part (a C of 0 F could mean either, so it is refused), and any part takes an S2P file in its row. | Não foi possível ler "{value}" como o valor de {ref}: na cadeia de uma antena, um C, L ou R recebe um valor na própria unidade (4.7pF, 4p7, 15nH, 50R), 0R troca um componente em série por um curto e open retira um componente shunt (um C de 0 F poderia ser qualquer um dos dois, então é recusado), e qualquer componente recebe um arquivo S2P na linha dele. |
| G_ANTENNA_NO_FAR_FIELD | No far field for this run: a run with part ports records none, as its jobs hold ports where the matching parts sit; Verify runs one job with each part in the grid at its value, as an ideal part, and records it. | Sem campo distante para esta execução: uma execução com portas de componentes não registra nenhum, pois as tarefas dela têm portas onde ficam os componentes de casamento; o botão Verificar executa uma tarefa com cada componente na grade com o valor dele, como componente ideal, e o registra. |
| G_UNIT_DEG | degrees | graus |

- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_match_antenna.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(gui): control opens, retunes and verifies an antenna project, its far field read once on the pool, an antenna's bypasses in the stale indicator and its Advanced fields (Stage 3 design 5.10)"
graphify update .
```

---

### Task 4 [code]: The window's Results and Advanced for an antenna

**Files:**
- Modify: `src/kicad_rf_studio/gui/window.py` (imports :27-33, `ResultsView` :85-265, `AdvancedView` :314-358, `show_project` :642-667, `retune` :669-676); `core/messages.py`; `po/*`; the `.mo`.
- Test: `tests/test_gui.py`.

**Interfaces:**
- Consumes: Task 1's `draw_antenna` (axes, `gui`) and `retrace_antenna`; Task 3's `Opened.far`, `far_source`, `far_lay`, `retuned(..., far, far_lay)` and `fields`; `ANTENNA_LIMITS`, `core.project.antenna`.
- Produces: `ResultsView.shown: control.Opened` (the read on display, set by `display`); `show_chain(res, name)` drawing an antenna; `DEFAULT_COLUMN_MAX = 320`, Advanced's Default column's width at most; G_PROJECT_ANTENNA, G_FAR_FIELD_FROM.

- [ ] **Step 1: Write the failing tests,** in `tests/test_gui.py` (imports gain `h5py`, `ANTENNA_LIMITS`, `from test_cli_antenna import antenna_project` and `from test_match_antenna import pi_run`):

```python
def test_an_antenna_shows_s11_the_smith_chart_its_far_field_and_where_it_comes_from(window, qapp, tmp_path):
    pj = antenna_project(tmp_path / "ifa2g4").resolve()  # design 5.6, 5.10; Review Focus 1
    assert pipeline.run(pj) == 0  # before the window, whose fixture fails run_jobs here from then on: M = 0, the fake
    w = window()
    w.open_project(pj)
    opened(w)
    d, r, fig = load_project(pj), w.results, w.results.canvas.figure
    assert w.project_status.text() == render("G_PROJECT_ANTENNA", path=str(pj), ref="AE1", f_lo_mhz="2400",
                                             f_hi_mhz="2483.5", preset="normal")
    assert r.retune_box.isHidden() and r.verify_button.isHidden() and r.what_if.isHidden()  # nothing to retune
    assert [ax.name for ax in fig.axes] == ["rectilinear"] * 3 + ["polar"] * 3  # S11, Smith, η; three cuts at f0
    assert fig.get_suptitle().endswith("\n" + render("G_FAR_FIELD_FROM", source="T_RUN",
                                                     run_dir=Path(d["results"]["run_dir"]).name))
    shown = [control.text(c, p) for c, p in w.opened.results.lines]
    assert items(r.lines) == shown + [render(c) for c in ANTENNA_LIMITS]
    assert "I_ANTENNA_FAR_FIELD" in [c for c, _ in w.opened.results.lines]
    a = w.advanced
    rows = {a.table.item(k, 0).text(): k for k in range(a.table.rowCount())}
    assert not {"kind", "copper"} & set(rows)
    assert [a.table.item(rows["far_field.step_deg"], c).text() for c in (2, 3)] == ["5", render("G_UNIT_DEG")]
    w.tabs.setCurrentWidget(r)
    qapp.processEvents()  # the first paint draws the figure at the tab's size
    assert min(ax.get_window_extent().height for ax in fig.axes) >= 100  # one row, no foot (probed: 113 px and up)
    grab(w, "antenna-results")
    w.tabs.setCurrentWidget(a)
    qapp.processEvents()
    assert not a.table.horizontalScrollBar().isVisible()  # the far-field list's default cut at 320 px
    grab(w, "antenna-advanced")
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules


def test_an_antennas_retune_takes_0r_and_open_refuses_the_converse_and_blits(window, qapp, tmp_path, monkeypatch):
    pj = pi_run(tmp_path, monkeypatch).resolve()  # ifa2g4_pi on the network fake; design 5.7; Review Focus 1
    w = window()
    w.open_project(pj)
    opened(w)
    r, fig = w.results, w.results.canvas.figure
    assert column(r.parts, PART) == ["L1", "C2", "C3"] and column(r.parts, VALUE) == ["2.7nH", "1pF", "1pF"]
    assert len(fig.axes) == 2 and render("G_ANTENNA_NO_FAR_FIELD") in items(r.lines)  # no far field before verify
    assert r.stale.text() == render("G_VERIFY_NONE") and not r.what_if.isHidden()
    w.tabs.setCurrentWidget(r)
    qapp.processEvents()  # the first paint draws the canvas and keeps its background for the blits
    axes, draws, real = list(fig.axes), [], r.canvas.draw
    monkeypatch.setattr(r.canvas, "draw", lambda: draws.append(1) or real())
    timings = []
    for k, typed in ((0, "0R"), (1, "0.127pF"), (2, "open")):  # each snapped on commit: 0.127pF to E24's 0.13pF
        start = time.perf_counter()
        r.parts.item(k, VALUE).setText(typed)
        timings.append(time.perf_counter() - start)
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows(), w.opened.far, w.opened.far_lay)
    assert column(r.parts, VALUE) == ["0R", "0.13pF", "open"] and min(timings) < 0.05
    assert draws == [] and fig.axes == axes  # moved in place and blitted, never redrawn
    assert np.array_equal(r.curves[0].get_ydata(), 20 * np.log10(np.abs(res.chain[:, 0, 0])))
    assert items(r.lines) == [control.text(c, p) for c, p in res.lines] + [render(c) for c in ANTENNA_LIMITS]
    r.parts.item(0, VALUE).setText("open")  # the series part opened: refused, in the window's words
    assert items(r.lines)[0] == render("G_RETUNE_OPEN_SERIES", ref="L1") and fig.axes == []
    r.parts.item(0, VALUE).setText("0R")
    r.parts.item(2, VALUE).setText("0R")  # the shunt to GND shorted: refused
    assert items(r.lines)[0] == render("G_RETUNE_SHORT_SHUNT", ref="C3", net="GND")
    r.parts.item(2, VALUE).setText("open")
    r.parts.item(1, VALUE).setText("0pF")  # a C of 0 F, neither bypass: refused, snapping leaves it as typed
    assert items(r.lines)[0] == render("G_RETUNE_ANTENNA_VALUE", ref="C2", value="0pF")
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules


def test_verify_brings_an_antennas_far_field_and_the_retune_blits_on_its_six_panels(
        window, qapp, tmp_path, monkeypatch):  # design 5.7, 5.10; Review Focus 1, 2
    pj = pi_run(tmp_path, monkeypatch).resolve()
    monkeypatch.setenv("KRS_FAKE_CBOX", "6e-16")  # the detached verify's cell C, as pi_run patches it here
    w = window()
    w.open_project(pj)
    opened(w)
    r = w.results
    r.verify_button.click()  # the stored values: verify starts at once
    assert w.command == "verify"
    until(lambda: w.tick() or w.run_status.text() == render("G_END_DONE", exit_code=0))
    opened(w)  # its end read the project again, its far field with it
    d, fig = load_project(pj), r.canvas.figure
    assert w.opened.far_source == ("T_VERIFY", d["verify"]["run_dir"]) and r.stale.isHidden()
    assert [ax.name for ax in fig.axes].count("polar") == 3
    assert fig.get_suptitle().endswith("\n".join(["", render("G_WHAT_IF"), render(
        "G_FAR_FIELD_FROM", source="T_VERIFY", run_dir=Path(d["verify"]["run_dir"]).name)]))
    w.tabs.setCurrentWidget(r)
    qapp.processEvents()
    assert min(ax.get_window_extent().height for ax in fig.axes) >= 100  # the six in one row, beside the parts' rows

    def no_read(*args, **kwargs):
        raise AssertionError("a file read on the GUI thread")

    for owner, name in ((pipeline, "far_of"), (pipeline, "layout"), (h5py, "File"), (np, "load")):
        monkeypatch.setattr(owner, name, no_read)
    axes, draws, real = list(fig.axes), [], r.canvas.draw
    monkeypatch.setattr(r.canvas, "draw", lambda: draws.append(1) or real())
    timings = []
    for typed in ("1.2pF", "1pF", "1.2pF"):
        start = time.perf_counter()
        r.parts.item(2, VALUE).setText(typed)
        timings.append(time.perf_counter() - start)
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows(), w.opened.far, w.opened.far_lay)
    assert min(timings) < 0.05 and draws == [] and fig.axes == axes
    assert np.array_equal(r.curves[0].get_ydata(), 20 * np.log10(np.abs(res.chain[:, 0, 0])))
    assert [c for c, _ in res.lines].count("I_ANTENNA_ETA_WHAT_IF") == 2  # the retune's own η_tot, what-if
    assert r.stale.text() == render("G_VERIFY_STALE")
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
    grab(w, "antenna-verify")
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui.py -q -k "antenna"`. Expected: FAIL (the project's line is E_INTERNAL's `KeyError: 'harmonics'` from show_project, nothing is drawn for one external port, and Advanced's horizontal scroll bar shows).
- [ ] **Step 3: `gui/window.py`.**
  - `show_project`: an antenna's line is G_PROJECT_ANTENNA with `ref` its antenna.ref, `f_lo_mhz`/`f_hi_mhz` its band's `f"{x / 1e6:g}"` and its preset; v1's G_PROJECT as before.
  - `ResultsView.display` keeps `opened` as `self.shown` before anything else (the docstring says so); `__init__` sets `self.shown = control.Opened(None, None, None, None, None, None)`.
  - `ResultsView.show_chain(res, name)`: with `ant = res is not None and antenna(self.shown.project)` (a result always comes with its project; the blank Opened that open_project displays has none, and `antenna(None)` raises), the lines end with ANTENNA_LIMITS instead of LIMITS; a plot needs a chain (one external port); with axes drawn, `retrace_antenna(self.axes, res.lay.f, res.chain[:, 0, 0], p)` and the blit, as v1's, `p` being `self.shown.project`; else the full draw `self.axes = draw_antenna(fig, res.lay.f, res.chain[:, 0, 0], p, self.shown.far, name, label, gui=True)`, its curves `retrace_antenna(...)` animated, where `label` joins with "\n" the what-if label (when `res.what_if`) and, with `self.shown.far_source = (source, run_dir)`, `render("G_FAR_FIELD_FROM", source=source, run_dir=Path(run_dir).name)`, None when both are absent. Comment `# ponytail: with part ports the η and cut panels stay the current verify's while the retune moves S11, labelled so; the instant far field by superposition (design 7) would move them too`. v1's branch unchanged. Docstring: "An antenna's chain (Stage 3 design 5.10) draws draw_antenna's figure for the window (gui: the six panels in one row, the limits in the lines) with the far field of the read (the run's, or the current verify's while the retune moves S11), the title's last line saying which run it comes from, and is moved by retrace_antenna."
  - `ResultsView.blit`'s ponytail gains the antenna's numbers: "…which Qt then redraws once in full (about 0.1 s for v1's figure, a quarter of a second for an antenna's six panels, as on the first edit after a verify); fixed-height status lines (setRetainSizeWhenHidden) if that is felt".
  - `AdvancedView`: the Default column (2) `QHeaderView.ResizeMode.Interactive` in `__init__`, and at the end of each `display` fitted to its contents but at most `DEFAULT_COLUMN_MAX = 320` px, a module constant beside FIELD_COLUMNS (`self.table.resizeColumnToContents(2)`, then `self.table.setColumnWidth(2, min(self.table.columnWidth(2), DEFAULT_COLUMN_MAX))`), with `# ponytail: a default past 320 px (an antenna's far-field list) is elided; drag the column to read it whole`. v1's widest default takes 103 px, so v1's columns stay as they are (probed: [367, 441, 103, 211] px); an antenna's far_field.f_hz default, 200 characters, would otherwise widen the column to 2407 px and leave the Value column, the only editable one, 100 px. The class docstring says so.
  - `MainWindow.retune` passes `self.opened.far, self.opened.far_lay` to `control.retuned`. The imports gain `ANTENNA_LIMITS`, `draw_antenna` and `retrace_antenna` (core.post.antenna) and `antenna` (core.project).
- [ ] **Step 4: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| G_PROJECT_ANTENNA | {path}: antenna {ref}, band {f_lo_mhz} to {f_hi_mhz} MHz, preset {preset}. | {path}: antena {ref}, banda de {f_lo_mhz} a {f_hi_mhz} MHz, predefinição {preset}. |
| G_FAR_FIELD_FROM | Efficiency and pattern: the {source} in {run_dir}. | Eficiência e diagrama: a {source} em {run_dir}. |

- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_gui.py -q`. Expected: PASS, v1's Results and Advanced tests unchanged.
- [ ] **Step 6: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(gui): Results for an antenna: S11 with the band, the Smith chart, the efficiencies and the cuts of the run that holds the network in one row, labelled with that run, the retune moved in place by blit, and Advanced's long defaults cut at 320 px (Stage 3 design 5.10)"
graphify update .
```

---

### Task 5 [code]: New makes an antenna project

**Files:**
- Modify: `src/kicad_rf_studio/gui/control.py` (`GUI`; new `_antennas`, `board_choices`, `BANDS`); `src/kicad_rf_studio/gui/window.py` (module docstring :1-10, `NewForm` :268-311, `board_chosen` :771-781, `create_project` :801-820, `show_pads` :822-849); `core/messages.py`; `po/*`; the `.mo`.
- Test: `tests/test_gui_control.py`, `tests/test_gui.py`, `tests/test_sexpr.py` (`QUOTED`).

**Interfaces:**
- Consumes: `antenna_kinds`, `classify`, `load_board`, `_names`; `cli.new_antenna(board, start, antenna, band, *, preset, stackup, lid_height, output)`; `parse_band`; `control.text`; the tests' `KINDS` (test_antenna_kicad), `mini_board_file`.
- Produces:
  - `control._antennas(b: Board) -> dict[str, str]`: the board's antenna footprints by reference (antenna_kinds), classify's connectors left out: New's list and a press's (Task 7).
  - `control.board_choices(board: Path) -> tuple[list[str], dict[str, str]]`: New's one read, the pads with copper and `_antennas`.
  - `control.BANDS = (("868 MHz (863–870 MHz)", 863e6, 870e6), ("915 MHz (902–928 MHz)", 902e6, 928e6), ("2.4 GHz (2400–2483.5 MHz)", 2.4e9, 2.4835e9))`.
  - `NewForm.form` (its QFormLayout), `kind` (QComboBox, data `"chain"` or `"antenna"`), `antenna` (QComboBox, data the reference), `band` (QComboBox, data `(f_lo, f_hi)` or None for Custom), `band_text` (QLineEdit, enabled only for Custom), `band_row` and `end_row` (their rows' layouts), `kind_changed()`, `band_changed()`, `show_antennas(kinds: dict[str, str], antenna: str = "") -> None`.
  - `GUI` gains `"E_ANTENNA_MODULE": "G_ANTENNA_MODULE"` and `"E_ANTENNA_CHIP": "G_ANTENNA_CHIP"`; G_NEW_KIND, G_KIND_CHAIN, G_KIND_ANTENNA, G_NEW_ANTENNA, G_NEW_BAND, G_BAND_CUSTOM, G_NO_ANTENNA.

- [ ] **Step 1: Write the failing tests.** `tests/test_gui_control.py` (imports gain `from test_antenna_kicad import KINDS`):

```python
def test_new_reads_a_boards_pads_and_antennas_once_but_its_connectors(mini_board_file):  # design 5.10; r2
    pads, kinds = control.board_choices(FIX / "ifa2g4_pi.kicad_pcb")
    assert pads == control.pads(FIX / "ifa2g4_pi.kicad_pcb") and kinds == {"AE1": "printed"}
    assert control.board_choices(FIX / "lpf915.kicad_pcb")[1] == {}  # J1, a U.FL with a keep-out, is a connector
    assert control.board_choices(mini_board_file(KINDS))[1] == {
        "AE1": "printed", "AE2": "chip", "AE3": "chip", "AE4": "chip", "AE5": "chip", "U2": "module", "U3": "module",
        "U4": "printed"}
    assert [(label, f_lo, f_hi) for label, f_lo, f_hi in control.BANDS] == [
        ("868 MHz (863–870 MHz)", 863e6, 870e6), ("915 MHz (902–928 MHz)", 902e6, 928e6),
        ("2.4 GHz (2400–2483.5 MHz)", 2.4e9, 2.4835e9)]  # design 5.10, 7's presets
```

  `tests/test_gui.py` (imports gain `Qt` from PySide6.QtCore, `cli`, and `from test_antenna_kicad import KINDS`):

```python
def test_new_makes_an_antenna_project_from_its_kind_its_antenna_and_its_band(window, tmp_path, monkeypatch,
                                                                            mini_board_file):  # design 5.10
    board = tmp_path / "ifa2g4_pi.kicad_pcb"
    board.write_bytes((FIX / "ifa2g4_pi.kicad_pcb").read_bytes())
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(board), ""))
    w = window()
    f = w.new_form
    assert f.kind.currentData() == "chain" and f.form.isRowVisible(f.f0) and not f.form.isRowVisible(f.antenna)
    assert f.band.currentData() == (2.4e9, 2.4835e9) and not f.band_text.isEnabled()
    f.board_button.click()
    w.pads_read.result(timeout=60)
    w.tick()
    f.kind.setCurrentIndex(f.kind.findData("antenna"))
    assert f.form.isRowVisible(f.antenna) and f.form.isRowVisible(f.band_row)
    assert not any(f.form.isRowVisible(x) for x in (f.end_row, f.f0, f.harmonics))
    assert [f.antenna.itemText(k) for k in range(f.antenna.count())] == ["AE1"] and f.antenna.currentData() == "AE1"
    f.start.setCurrentText("U1.1")
    f.create_button.click()
    path, notes = w.creating.result(timeout=120)
    w.tick()
    same = cli.new_antenna(board, "U1.1", "AE1", (2.4e9, 2.4835e9), output=tmp_path / "cli")[0]
    assert path == tmp_path / "ifa2g4_pi" / "project.json" and load_project(path) == load_project(same)
    assert items(f.notes) == [control.text(c, p) for c, p in notes]  # new --antenna's own call, nothing duplicated
    opened(w)
    assert w.project_status.text() == render("G_PROJECT_ANTENNA", path=str(path.resolve()), ref="AE1",
                                             f_lo_mhz="2400", f_hi_mhz="2483.5", preset="normal")
    grab(w, "new-antenna")
    f.band.setCurrentIndex(f.band.findData(None))  # Custom: findData matches None, never an equal tuple (probed)
    assert f.band_text.isEnabled()
    f.band_text.setText("2400MHz")
    f.folder.setText(str(tmp_path / "custom"))
    f.create_button.click()
    assert w.creating is None and f.status.text() == render("E_BAD_BAND", text="2400MHz")
    f.band_text.setText("2400MHz:2483.5MHz")
    f.create_button.click()
    assert load_project(w.creating.result(timeout=120)[0])["band"] == {"f_lo_hz": 2.4e9, "f_hi_hz": 2.4835e9}
    w.tick()
    f.board.setText(str(mini_board_file(KINDS)))
    w.board_chosen()
    w.pads_read.result(timeout=60)
    w.tick()
    assert [f.antenna.itemText(k) for k in range(f.antenna.count())] == [
        "AE1", "AE2", "AE3", "AE4", "AE5", "U2", "U3", "U4"]
    assert [f.antenna.model().item(k).isEnabled() for k in range(8)] == [True] + [False] * 6 + [True]
    tip = Qt.ItemDataRole.ToolTipRole
    for k, code, ref in ((1, "G_ANTENNA_CHIP", "AE2"), (5, "G_ANTENNA_MODULE", "U2")):  # rich text: Qt wraps it
        assert f.antenna.itemData(k, tip).startswith("<p>") and render(code, ref=ref) in f.antenna.itemData(k, tip)
    lpf = tmp_path / "lpf915.kicad_pcb"
    lpf.write_bytes((FIX / "lpf915.kicad_pcb").read_bytes())
    f.board.setText(str(lpf))
    w.board_chosen()
    w.pads_read.result(timeout=60)
    w.tick()
    f.create_button.click()  # no printed antenna (J1, a connector, is not listed): nothing starts
    assert (f.antenna.count(), w.creating, f.status.text()) == (0, None, render("G_NO_ANTENNA"))
    f.board.setText(str(tmp_path / "nope.kicad_pcb"))
    w.board_chosen()
    w.pads_read.exception(timeout=60)
    w.tick()
    refusal = f.status.text()  # the read's refusal, which show_pads put there
    f.create_button.click()  # a board never read: its refusal stays, never G_NO_ANTENNA
    assert refusal and (f.antenna.count(), w.creating, f.status.text()) == (0, None, refusal)
    assert board.read_bytes() == (FIX / "ifa2g4_pi.kicad_pcb").read_bytes()
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

  `tests/test_sexpr.py`'s `QUOTED` gains `"G_ANTENNA_MODULE": ("G_KIND_CHAIN",)`, `"G_ANTENNA_CHIP": ("G_KIND_CHAIN",)` and `"G_NO_ANTENNA": ("G_KIND_CHAIN",)`.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q -k "new_makes or new_reads or new_from or button_press"`. Expected: FAIL (`module ... has no attribute 'board_choices'`, `NewForm` has no `kind`), the v1 New and press tests still passing.
- [ ] **Step 3: `gui/control.py`.**
  - `_antennas(b)`: `antenna_kinds(b)` without `classify(b).connectors`; docstring "The antenna footprints of the board `b` by reference, as antenna_kinds reads them, classify's connectors left out (Stage 3 design 5.10, r2: a U.FL with a keep-out reads as a module): New's list and a press's." Comment `# ponytail: classify's connectors are skipped, which closes plan 2's ceiling for a U.FL with a keep-out; a converter with a keep-out still reads module (listed disabled, refused on a press) and a custom-library module that draws copper still reads printed; a class test if users meet them`.
  - `board_choices(board)`: one `load_board`, its `_names(b.all_pads())` and `_antennas(b)`; docstring "New's read of the board file `board` (Stage 2 design 5.3, Stage 3 design 5.10): its pads with copper, as pads lists them, and its antenna footprints by reference (_antennas). Raises load_board's refusals." `pads` stays: its product caller goes, and v1's tests read the pickers against it (eight lines).
  - `BANDS` with the comment `# New's band presets (Stage 3 design 5.10, 7): numbers and units only, the same in both languages (pt-BR design 3), so no catalog code`.
  - `GUI` gains the two entries; the imports gain `antenna_kinds` (core.kicad.tracer).
- [ ] **Step 4: `NewForm`.** The rows, in order: G_NEW_BOARD, G_NEW_KIND (`kind`: G_KIND_CHAIN `"chain"`, G_KIND_ANTENNA `"antenna"`), G_NEW_START, G_NEW_END (`end_row`), G_NEW_ANTENNA (`antenna`, not editable), G_NEW_F0, G_NEW_HARMONICS, G_NEW_BAND (`band_row`: `band`, then `band_text`), G_NEW_PRESET, G_NEW_STACKUP, G_NEW_LID, G_NEW_FOLDER; then Create, the status line and the notes as before. `band` holds each of `control.BANDS` as `(label, (f_lo, f_hi))`, then G_BAND_CUSTOM with None, and starts on the 2.4 GHz preset by its index, `setCurrentIndex(2)`: `findData` finds None and str data, but a tuple only as the very object stored (probed on PySide6 6.12). `kind_changed()` (on `kind.currentIndexChanged`, and once at the end of `__init__`): `form.setRowVisible` of `antenna` and `band_row` on the antenna kind, of `end_row`, `f0` and `harmonics` on the chain kind. `band_changed()` (on `band.currentIndexChanged`, and once): `band_text` enabled only for Custom. `show_antennas(kinds, antenna="")`: the combo cleared, then each footprint by reference (its text and data), a module's or a chip antenna's item disabled (`model().item(k).setEnabled(False)`) with `control.text("E_ANTENNA_MODULE" | "E_ANTENNA_CHIP", {"ref": ref})` as its tooltip (`Qt.ItemDataRole.ToolTipRole`) in rich text, `f"<p>{html.escape(text, quote=False)}</p>"`, which Qt word-wraps (a plain tooltip of some 250 characters runs about 1600 px wide); `antenna` picked when given and listed, else the first printed one, else none (`setCurrentIndex(-1)`: Qt keeps a disabled first item current otherwise). Comment `# ponytail: a disabled entry's reason is its tooltip; a 200-character item would widen the window past 1200`. The class docstring names the kind, the antenna, the band and Custom. The imports gain `html`.
- [ ] **Step 5: The window.**
  - `board_chosen` submits `control.board_choices` in place of `control.pads`; `show_pads` takes its `(pads, kinds)`: the pads in the pickers as before and `f.show_antennas(kinds)`; a refused read empties both. A press (`control.Handed`) is shown as before (Task 7 adds its kind and antenna).
  - `create_project`: with the antenna kind, `ref = f.antenna.currentData()`; None starts nothing, and gives G_NO_ANTENNA in the status line only after a read that succeeded (`f.chosen` set and no `pads_read` pending), else leaves the status line as it is (a refused read's refusal, or a read going on, whose end fills the combo); then the band `f.band.currentData() or parse_band(f.band_text.text())` (a KrsError: `control.message` in the status line), then the folder's G_NEW_NO_FOLDER as before; then `self.pool.submit(cli.new_antenna, board, start, ref, band, preset=…, stackup=…, lid_height=…, output=…)` with the same board, start, preset, stackup, lid and folder arguments as `cli.new`'s call. The chain kind unchanged. The imports gain `parse_band`.
  - Docstrings: the module's (control.pads becomes control.board_choices), board_chosen's and show_pads' (the board's pads and antennas, board_choices), and create_project's (the antenna kind and its refusals).
- [ ] **Step 6: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| G_NEW_KIND | Kind | Tipo |
| G_KIND_CHAIN | Matching chain | Cadeia de casamento |
| G_KIND_ANTENNA | Antenna | Antena |
| G_NEW_ANTENNA | Antenna footprint | Footprint da antena |
| G_NEW_BAND | Band | Banda |
| G_BAND_CUSTOM | Custom (F_LO:F_HI) | Personalizada (F_LO:F_HI) |
| G_NO_ANTENNA | No printed antenna on this board: an antenna project needs one whose copper is drawn in the board file. A matching chain can still be simulated: choose the kind Matching chain. | Nenhuma antena impressa nesta placa: um projeto de antena precisa de uma cujo cobre esteja desenhado no arquivo da placa. Uma cadeia de casamento ainda pode ser simulada: escolha o tipo Cadeia de casamento. |
| G_ANTENNA_MODULE | {ref} is a module: its antenna's copper is inside the module, not in the board file, so it cannot be simulated as an antenna. The matching chain up to it still can: choose the kind Matching chain, with a pad of {ref} as the end pad. | {ref} é um módulo: o cobre da antena dele fica dentro do módulo, não no arquivo da placa, então ela não pode ser simulada como antena. A cadeia de casamento até ele ainda pode: escolha o tipo Cadeia de casamento, com uma ilha de {ref} como ilha final. |
| G_ANTENNA_CHIP | {ref} is a chip antenna: its radiator is inside the part's body and the board file holds only its pads, so it cannot be simulated as an antenna. The matching chain up to it still can: choose the kind Matching chain, with a pad of {ref} as the end pad. | {ref} é uma antena chip: o radiador fica dentro do corpo do componente e o arquivo da placa só tem as ilhas dela, então ela não pode ser simulada como antena. A cadeia de casamento até ela ainda pode: escolha o tipo Cadeia de casamento, com uma ilha de {ref} como ilha final. |

- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_gui_control.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 8: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(gui): New makes an antenna project: its kind, the antenna footprint from one board read with modules and chip antennas disabled, the start pad and the band presets, through cli.new_antenna (Stage 3 design 5.10)"
graphify update .
```

---

### Task 6 [code]: The Compare tab

**Files:**
- Modify: `src/kicad_rf_studio/gui/control.py` (`GUI`; new `COMPARE_FOLDER`, `QUANTITIES`, `DIGITS`, `compare`); `src/kicad_rf_studio/gui/window.py` (new `CompareView`, `COMPARE_COLUMNS`; `MainWindow.__init__`, `tick`, `open_project`; new `pick_variant`, `compare_variant`, `compared`); `core/messages.py`; `po/*`; the `.mo`.
- Test: `tests/test_gui_control.py`, `tests/test_gui.py` (and `test_every_list_of_sentences_wraps_at_its_width` :201-210 gains the Compare list), `tests/test_sexpr.py` (`QUOTED`).

**Interfaces:**
- Consumes: `pipeline.compare_projects(base, variant, output, emit)`, `DELTA_COLUMNS`, `control.message`, `control.text`; the tests' `twin` and `edited` (test_compare), `lpf_project` (test_run), `antenna_project`.
- Produces:
  - `control.COMPARE_FOLDER = "compare"`; `control.QUANTITIES = {"resonance": "G_QUANTITY_RESONANCE", "bandwidth_10db": "G_QUANTITY_BANDWIDTH", "eta_tot": "G_QUANTITY_ETA_TOT", "peak_gain": "G_QUANTITY_PEAK_GAIN"}`; `control.DIGITS = {"MHz": 1, "%": 1, "dBi": 2, "dB": 2}`; `control.compare(base: Path, variant: Path) -> tuple[int, list[tuple[str, dict]], list[list[str]]]`.
  - `window.COMPARE_COLUMNS = ("G_COL_QUANTITY", "G_COL_MARKER", "G_COL_F_MHZ", "T_BASE", "T_VARIANT", "G_COL_UNIT", "G_COL_DELTA", "G_COL_DELTA_UNIT", "G_COL_THRESHOLD", "G_COL_RESOLVED")`.
  - `CompareView` with `variant_button`, `variant` (QLabel), `compare_button`, `status`, `lines` (`sentences()`), `table`, `picture` (a QLabel in a QScrollArea) and `display(lines: list[str], cells: list[list[str]], picture: Path | None) -> None`.
  - `MainWindow.comparison` (the view), `variant: Path | None`, `comparing: Future | None`.
  - `GUI` gains `"E_COMPARE_KIND": "G_COMPARE_KIND"`, `"E_COMPARE_NO_RESULT": "G_COMPARE_NO_RESULT"`, `"E_RESULTS_WRITE": "G_RESULTS_WRITE"`.

- [ ] **Step 1: Write the failing tests.** `tests/test_gui_control.py`:

```python
def test_compare_runs_into_the_bases_own_folder_and_gives_its_table_in_the_windows_words(tmp_path, calibrated):
    from test_compare import twin  # design 5.8, 5.10
    a = antenna_project(tmp_path / "a").resolve()
    assert pipeline.run(a) == 0
    b = twin(a, tmp_path / "b")
    code, lines, cells = control.compare(a, b)
    assert code == 0 and lines[0] == ("I_ANTENNA_RELATIVE", {})
    assert [row[0] for row in cells] == [render(q) for q in ("G_QUANTITY_RESONANCE", "G_QUANTITY_BANDWIDTH",
                                                             *["G_QUANTITY_ETA_TOT"] * 3, "G_QUANTITY_PEAK_GAIN")]
    said = dict(lines)  # each delta's line, rounded as the table rounds it
    res, gain = said["I_COMPARE_RESONANCE"], said["I_COMPARE_GAIN"]
    assert (cells[0][3], cells[0][6], cells[5][2], cells[5][4]) == (res["base_mhz"], res["shift_mhz"],
                                                                    gain["f_mhz"], gain["variant_dbi"])
    assert sorted(p.name for p in (a.parent / control.COMPARE_FOLDER).iterdir()) == ["compare.csv", "compare.png"]
    assert not (b.parent / control.COMPARE_FOLDER).exists()
```

  `tests/test_gui.py` (imports gain `from kicad_rf_studio.gui.window import COMPARE_COLUMNS`, `from test_compare import edited, twin`, `from test_run import lpf_project`); in `test_every_list_of_sentences_wraps_at_its_width`, `lists` gains `w.comparison.lines` and the count becomes 6:

```python
def test_compare_runs_on_the_pool_into_the_bases_folder_and_never_the_variants(window, qapp, tmp_path, monkeypatch):
    a = antenna_project(tmp_path / "a").resolve()  # design 5.8, 5.10; Review Focus 5
    assert pipeline.run(a) == 0
    b, wrong, lpf = twin(a, tmp_path / "b"), twin(a, tmp_path / "wrong"), lpf_project(tmp_path).resolve()
    fresh = antenna_project(tmp_path / "fresh").resolve()  # never run: nothing compare can use
    edited(wrong, fingerprint={**load_project(wrong)["results"]["fingerprint"], "preset": "strict"})
    watched = (b.parent, Path(load_project(a)["results"]["run_dir"]))

    def stamps():
        return {p: p.stat().st_mtime_ns for root in watched for p in [root, *root.rglob("*")]}

    before = stamps()
    w = window()
    w.open_project(a)
    opened(w)
    c = w.comparison
    assert w.tabs.tabText(4) == render("G_TAB_COMPARE") and c.status.text() == render("G_COMPARE_NONE")
    assert not c.compare_button.isEnabled()

    def choose(project):  # Variant…, then the tick that enables Compare
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *x, **k: (str(project), ""))
        c.variant_button.click()
        w.tick()

    choose(b)
    assert (w.variant, c.variant.text(), c.compare_button.isEnabled()) == (b.resolve(), str(b.resolve()), True)
    c.compare_button.click()
    assert c.status.text() == render("G_COMPARING") and not c.compare_button.isEnabled()
    code, lines, cells = w.comparing.result(timeout=120)
    w.tick()
    assert code == 0 and items(c.lines) == [control.text(x, p) for x, p in lines] and c.status.text() == ""
    assert [c.table.horizontalHeaderItem(k).text() for k in range(10)] == [render(x) for x in COMPARE_COLUMNS]
    assert [[c.table.item(k, j).text() for j in range(10)] for k in range(c.table.rowCount())] == cells
    assert len(cells) == 6 and c.table.item(0, 9).text() == render("T_NOT_RESOLVED")  # against its copy
    w.tabs.setCurrentWidget(c)
    qapp.processEvents()
    assert not c.picture.pixmap().isNull() and c.picture.size() == c.picture.pixmap().size()  # whole, by scrolling
    assert (a.parent / "compare" / "compare.png").is_file()
    assert stamps() == before and not (b.parent / "compare").exists()  # read in place, never written
    grab(w, "compare")
    real = os.replace

    def held(src, dst):  # a viewer holds compare.png
        if Path(dst).name == "compare.png":
            raise PermissionError(13, "in use")
        real(src, dst)

    with monkeypatch.context() as m:
        m.setattr(os, "replace", held)
        c.compare_button.click()
        assert w.comparing.result(timeout=120)[0] == 2
    w.tick()
    assert render("G_RESULTS_WRITE", path=str(a.parent / "compare" / "compare.png"),
                  reason="T_PERMISSION_DENIED") in items(c.lines)
    assert c.table.rowCount() == 0 and c.picture.pixmap().isNull()
    for project, shown in ((lpf, render("G_COMPARE_KIND", path=str(lpf))),
                           (fresh, render("G_COMPARE_NO_RESULT", path=str(fresh))),
                           (wrong.resolve(), render("E_COMPARE_SETTINGS", fields="preset"))):
        choose(project)
        c.compare_button.click()
        w.comparing.exception(timeout=120)
        w.tick()
        assert (c.status.text(), c.lines.count(), c.table.rowCount()) == (shown, 0, 0)
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

  `tests/test_sexpr.py`'s `QUOTED` gains `"G_COMPARE_KIND": ("G_COMPARE", "G_NEW", "G_KIND_ANTENNA")` and `"G_COMPARE_NO_RESULT": ("G_COMPARE", "G_VERIFY")`.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q -k "compare or sentences"`. Expected: FAIL (`module ... has no attribute 'compare'`, `MainWindow` has no `comparison`).
- [ ] **Step 3: `control.compare(base, variant)`:** `pipeline.compare_projects(base, variant, base.parent / COMPARE_FOLDER, emit)` with `emit` appending each line; then, when it exited 0, compare.csv's rows (`csv.DictReader`) as the table's cells, else []. Each row's DELTA_COLUMNS in order, as text: the quantity in the window's words (`render(QUANTITIES[...])`); the marker, the unit and the delta unit as the CSV holds them; f in MHz to one decimal; base and variant to their unit's digits, the delta (signed, `+`) and the threshold to the delta unit's, as delta_lines rounds them (`DIGITS`); an empty cell for an empty one; the verdict as T_RESOLVED for "True", T_NOT_RESOLVED for "False", else empty. Docstring: "Compare (Stage 3 design 5.8, 5.10), off the GUI thread: compare_projects of the project files `base` and `variant` into the base's own folder's compare/ (COMPARE_FOLDER), never the variant's; its lines and, when it exited 0, compare.csv's rows as the Compare table shows them (cells: DELTA_COLUMNS, the quantity in the window's words, f in MHz, the numbers rounded as the lines round them). Returns (exit code, lines, cells). Raises compare_projects' refusals (E_COMPARE_KIND, E_COMPARE_NO_RESULT, E_COMPARE_SETTINGS)." Comments `# ponytail: compare/ is replaced on each compare; one folder per variant if users keep several` and `# ponytail: compare_png draws on this pool thread while the GUI thread may draw the Results canvas: separate Figures, and matplotlib keys its font cache by thread; a lock around both if a crash ever shows`.
- [ ] **Step 4: `CompareView` and the window.**
  - `CompareView(QWidget)`: a row of `variant_button` (G_COMPARE_VARIANT), `variant` (word-wrapped, stretched) and `compare_button` (G_COMPARE, disabled); `status` (word-wrapped, G_COMPARE_NONE); `lines` (`sentences()`); `table` (`QTableWidget(0, 10)`, headers `render` of COMPARE_COLUMNS, `NoEditTriggers`, its horizontal header `ResizeToContents`); `picture`, a QLabel set in a `QScrollArea` with `setWidgetResizable(True)`: a label whose pixmap is set after `setWidget` keeps its old size otherwise (probed: 12 × 14 px, no scroll range) (`# ponytail: compare.png at its own size in a scroll area, which keeps the window's 1200 × 800; scaled to the tab's width if users want it whole`). `display(lines, cells, picture)`: the lines; one table row per cell list, each cell its text; `picture` as a QPixmap, an empty one for None.
  - `MainWindow`: `self.comparison = CompareView()`, its tab G_TAB_COMPARE between Results and Advanced (tab 4); `self.variant = self.comparing = None`; `comparison.variant_button` → `pick_variant` (the file picked with G_COMPARE_VARIANT and G_OPEN_FILTER, `pipeline.project_path(name).resolve()` kept as `variant` and shown; nothing on Cancel); `comparison.compare_button` → `compare_variant` (`self.comparing = self.pool.submit(control.compare, self.path, self.variant)`, G_COMPARING, then a tick). `tick`, after its project check: a finished `comparing` taken (`compared`), then `compare_button` enabled while `variant` is set and no compare goes on. `compared(done)`: a refusal's `control.message` in the status line and the view emptied; else the status line cleared and `display([control.text(c, p) for c, p in lines], cells, self.path.parent / control.COMPARE_FOLDER / "compare.png" if code == 0 else None)`. `open_project` drops `comparing` (a compare of the previous project ends on the pool unread), empties the view and sets G_COMPARE_NONE; `variant` stays. Docstrings: the class's and MainWindow's state lists name `comparison`, `variant` and `comparing`. The imports gain `QPixmap` and `QScrollArea`.
- [ ] **Step 5: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| G_TAB_COMPARE | Compare | Comparação |
| G_COMPARE_VARIANT | Variant… | Variante… |
| G_COMPARE | Compare the projects | Comparar os projetos |
| G_COMPARING | Comparing… | Comparando… |
| G_COMPARE_NONE | Open an antenna project, then choose the variant to compare it with. | Abra um projeto de antena e escolha a variante a comparar com ele. |
| G_COMPARE_KIND | {path} is not an antenna project: Compare the projects compares two antenna projects, made with New from a board and the kind Antenna. | {path} não é um projeto de antena: o botão Comparar os projetos compara dois projetos de antena, criados com Novo projeto a partir de uma placa e o tipo Antena. |
| G_COMPARE_NO_RESULT | {path} has no result that Compare the projects can use: a run of its current model, made by this version, with no part on the chain, or, with part ports, a verify of that run at the values project.json holds. Run it (a board re-saved since its run needs one), then press Verify for a project with part ports. | {path} não tem resultado que o botão Comparar os projetos possa usar: uma execução do modelo atual dele, feita por esta versão, sem componente na cadeia ou, com portas de componentes, uma verificação dessa execução com os valores que o project.json guarda. Execute-o (uma placa salva de novo desde a execução precisa de uma) e depois pressione Verificar num projeto com portas de componentes. |
| G_RESULTS_WRITE | Cannot write {path}: {reason}. Close the program that holds it open (a spreadsheet or an image viewer, say), then press the button that wrote it again. | Não foi possível gravar {path}: {reason}. Feche o programa que o mantém aberto (uma planilha ou um visualizador de imagens, por exemplo) e depois pressione de novo o botão que o gravou. |
| G_COL_QUANTITY | Quantity | Grandeza |
| G_COL_MARKER | Marker | Marcador |
| G_COL_F_MHZ | f (MHz) | f (MHz) |
| G_COL_DELTA | Delta | Delta |
| G_COL_DELTA_UNIT | Delta unit | Unidade do delta |
| G_COL_THRESHOLD | Threshold | Limiar |
| G_COL_RESOLVED | Resolved | Resolvido |
| G_QUANTITY_RESONANCE | Resonance | Ressonância |
| G_QUANTITY_BANDWIDTH | -10 dB bandwidth | Largura de banda a -10 dB |
| G_QUANTITY_ETA_TOT | Total efficiency | Eficiência total |
| G_QUANTITY_PEAK_GAIN | Peak gain | Ganho de pico |

  T_BASE, T_VARIANT and G_COL_UNIT are reused as headers: a template is its own msgid, so "Base", "Variant" and "Unit" cannot be new codes. The quantities take compare's lines' own words (I_COMPARE_RESONANCE, I_COMPARE_BANDWIDTH, I_COMPARE_ETA, I_COMPARE_GAIN) in both languages.
- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_gui_control.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(gui): the Compare tab: a variant compared on the pool into the base's own compare folder, never the variant's, with its lines, its deltas table in the window's words and its overlays (Stage 3 design 5.8, 5.10)"
graphify update .
```

---

### Task 7 [code]: The button pre-fills an antenna

**Files:**
- Modify: `src/kicad_rf_studio/gui/control.py` (`Handed` :409-420, `handed` :423-454); `src/kicad_rf_studio/gui/window.py` (`show_pads`, `take_handoff`'s docstring); `core/messages.py` (G_BUTTON_ACTION reworded); `po/*`; the `.mo`.
- Test: `tests/test_gui_control.py`, `tests/test_gui.py`, `tests/test_sexpr.py` (`QUOTED`).

**Interfaces:**
- Consumes: Task 5's `_antennas`, `NewForm.kind` and `show_antennas`; `press`.
- Produces: `Handed` gains, after `problem`, `kind: str = "chain"`, `antenna: str = ""` and `kinds: dict[str, str] = field(default_factory=dict)` (the press board's antenna kinds, connectors left out, as board_choices gives them); G_HANDOFF_ANTENNAS {count, refs}, G_HANDOFF_START {count}.

- [ ] **Step 1: Write the failing tests,** in `tests/test_gui_control.py`; `test_a_handoff_joins_the_selection_to_the_saved_boards_pads` keeps every assert (lpf915's J1 is a connector, so `narrowed.problem` stays None) and gains `assert narrowed.kind == "chain"`:

```python
def test_a_press_on_an_antenna_gives_its_kind_and_never_its_own_pad_as_the_start(fake):  # design 5.10; r2
    board = FIX / "ifa2g4_pi.kicad_pcb"

    def read(pads=(), footprints=()):
        return control.handed(press(board, pads, footprints))

    every = [name for name in control.pads(board) if not name.startswith("AE1.")]
    assert read(["U1.1"], ["AE1"]) == control.Handed(board, "ipc://s", "T", every, "U1.1", "", None, "antenna", "AE1",
                                                     {"AE1": "printed"})
    for pads in (["AE1.1"], ["AE1.2"], ["AE1.1", "AE1.2"]):  # its own pads select it (new refuses them as start)
        h = read(pads)
        assert (h.kind, h.antenna, h.start, h.problem) == ("antenna", "AE1", "", None)
    assert (read(["AE1.2", "U1.1"]).antenna, read(["AE1.2", "U1.1"]).start) == ("AE1", "U1.1")
    two = read(["U1.1", "C1.1"], ["AE1"])
    assert (two.antenna, two.start, two.problem) == ("AE1", "", ("G_HANDOFF_START", {"count": 2}))


def test_a_press_on_two_antennas_or_on_a_module_or_a_chip_antenna_says_so(fake, mini_board_file):  # design 5.10
    board = mini_board_file(KINDS)

    def read(footprints):
        return control.handed(press(board, (), footprints))

    both = read(["AE1", "U4"])
    assert (both.kind, both.antenna, both.problem) == ("antenna", "", ("G_HANDOFF_ANTENNAS",
                                                                       {"count": 2, "refs": "AE1, U4"}))
    for ref, code in (("U2", "E_ANTENNA_MODULE"), ("U3", "E_ANTENNA_MODULE"), ("AE2", "E_ANTENNA_CHIP"),
                      ("AE4", "E_ANTENNA_CHIP")):
        h = read([ref])
        assert (h.kind, h.antenna, h.problem) == ("chain", "", (code, {"ref": ref}))  # v1's chain still applies
    assert read(["R1"]).problem is None and read(["AE1", "U2"]).kind == "antenna"  # a printed one wins
```

  `tests/test_gui.py`:

```python
def test_a_press_on_an_antenna_pre_fills_new_and_a_modules_shows_its_refusal(window, tmp_path, mini_board_file):
    board = tmp_path / "ifa2g4_pi.kicad_pcb"  # design 5.10; r2
    board.write_bytes((FIX / "ifa2g4_pi.kicad_pcb").read_bytes())
    w = window()
    f = w.new_form
    w.take_handoff(press(board, ["U1.1"], ["AE1"]))
    w.pads_read.result(timeout=60)
    w.tick()
    assert (f.kind.currentData(), f.antenna.currentData(), f.start.currentText(), f.status.text()) == (
        "antenna", "AE1", "U1.1", "")
    assert f.form.isRowVisible(f.antenna) and not f.form.isRowVisible(f.f0)
    grab(w, "handoff-antenna")
    w.take_handoff(press(mini_board_file(KINDS), (), ["U2"]))
    w.pads_read.result(timeout=60)
    w.tick()
    assert (f.kind.currentData(), f.status.text()) == ("chain", render("G_ANTENNA_MODULE", ref="U2"))
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

  `tests/test_sexpr.py`'s `QUOTED` gains `"G_BUTTON_ACTION": ("G_NEW",)`.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q -k "press or handoff"`. Expected: FAIL (`Handed` takes 8 positional arguments, the antenna's pad as the start).
- [ ] **Step 3: `control.handed`,** after the board's read: `kinds` is `_antennas(b)` (Task 5), passed to every Handed but load_board's refusal. After the unsaved check, the printed antennas among the selected footprints and the footprints of the selected pads, in the order they came in, decide:
  - one or more: kind `"antenna"`; the pickers every pad with copper but the antennas' (`_names`); the pads with copper off the antennas, by name, are the others; two antennas or more: antenna "" and G_HANDOFF_ANTENNAS {count, refs ", "-joined}; else antenna the one, the start the one other pad, and two others or more G_HANDOFF_START {count} with no start; the end "" (Stage 3 design 5.10: the antenna's own pads are never the start: `new` refuses AE1.1 with E_SAME_PADS and AE1.2 with E_START_ON_GND, r2's probe).
  - none: v1's rules as today; then, when v1's own problem is None, a selected footprint (not a selected pad's) that is a module or a chip antenna gives `("E_ANTENNA_MODULE" | "E_ANTENNA_CHIP", {"ref": ref})`, kind "chain".
  The docstring gains these rules and their precedence: the board's refusal, unsaved, the antenna's own (ANTENNAS, then START), then a module's or chip's.
- [ ] **Step 4: The window.** `show_pads`, for a press: `f.kind` set to `read.kind` (`findData`) and `f.show_antennas(read.kinds, read.antenna)`, besides what it does today; `take_handoff`'s docstring names the antenna kind.
- [ ] **Step 5: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| G_HANDOFF_ANTENNAS | {count} printed antennas are selected in KiCad ({refs}). Select one and press the button again, or pick it here. | Antenas impressas selecionadas no KiCad: {count} ({refs}). Selecione uma e pressione o botão de novo, ou escolha-a aqui. |
| G_HANDOFF_START | {count} pads besides the antenna's are selected in KiCad. Select the antenna with the one pad that feeds it, the radio pin, and press the button again, or pick the start pad here. | Ilhas selecionadas no KiCad além das da antena: {count}. Selecione a antena com a única ilha que a alimenta, o pino do rádio, e pressione o botão de novo, ou escolha a ilha inicial aqui. |
| G_BUTTON_ACTION (changed) | Opens kicad-rf-studio on this board and pre-fills New from a board with the selected pads, or with a selected antenna and its radio pin. | Abre o kicad-rf-studio nesta placa e preenche Novo projeto a partir de uma placa com as ilhas selecionadas, ou com uma antena selecionada e o pino do rádio dela. |

  `plugin.json` renders G_BUTTON_ACTION (`tests/test_button.py:259` renders it too); an installed button keeps the old tooltip until `install-kicad-plugin` runs again. The helper, the handoff file, the manifest's shape, `install-kicad-plugin` and `tests/fake_kicad.py` do not change.
- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_button.py tests/test_gui.py tests/test_gui_control.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(button): a selected printed antenna, or one of its pads, pre-fills New with the antenna kind and the radio pin; a module or a chip antenna shows its refusal (Stage 3 design 5.10)"
graphify update .
```

---

### Task 8 [code]: The README's antenna tutorial and the release check's antenna step

**Files:**
- Modify: `README.md` (Install step 5 :34; Development setup step 6 :158; new `## Antenna tutorial` between `## Tutorial` and `## Development setup`); `tools/release_check.py` (docstring :2-13, new `antenna`, `NEEDS`, `STEPS` :189-190).
- Test: `tests/test_repo.py`, `tests/test_release_check.py`.

**Interfaces:**
- Consumes: `release_check.run`, `program`, `isolated`, `failed`; `CATALOG`.
- Produces: `release_check.antenna(tmp: Path) -> tuple[str, str]`; `NEEDS["antenna"] = "install"`; `STEPS = (build, install, gui, antenna, plugin, privacy)`.

- [ ] **Step 1: Write the failing tests.** `tests/test_repo.py`:

```python
def test_the_readme_has_an_antenna_tutorial():  # Stage 3 design 5.12 item 5
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.index("\n## Tutorial\n") < readme.index("\n## Antenna tutorial\n") < readme.index(
        "\n## Development setup\n")
    tutorial = readme.split("\n## Antenna tutorial\n", 1)[1].split("\n## ", 1)[0]
    band = "--start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz"
    for command in (f"new tests/fixtures/ifa2g4_pi.kicad_pcb {band} -o ifa2g4_pi", "cost ifa2g4_pi",
                    "run ifa2g4_pi", "retune ifa2g4_pi L1=0R C2=0.13pF C3=1pF", "verify ifa2g4_pi",
                    f"new tests/fixtures/ifa2g4_pi_pour.kicad_pcb {band} -o ifa2g4_pi_pour",
                    "compare ifa2g4_pi ifa2g4_pi_pour -o compare"):
        assert f"kicad-rf-studio {command}\n" in tutorial, command
    assert "\n### What these results do not tell you\n" in tutorial and CATALOG["I_ANTENNA_RELATIVE"] in tutorial
```

  `tests/test_release_check.py`:

```python
def test_the_antenna_step_runs_new_on_the_releases_own_fixture_and_reads_schema_2(tmp_path, monkeypatch):
    fixture = ROOT / "tests" / "fixtures" / "ifa2g4_pi.kicad_pcb"  # Stage 3 design 5.12 item 5; r3
    with zipfile.ZipFile(tmp_path / "source.zip", "w") as z:
        z.write(fixture, "tests/fixtures/ifa2g4_pi.kicad_pcb")
    seen, schema = [], {"schema": 2, "kind": "antenna"}

    def run(command, **kw):  # the fresh venv's new: it writes project.json where -o says
        seen.append((command, kw["env"]))
        out = Path(command[command.index("-o") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "project.json").write_text(json.dumps(schema), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(release_check, "run", run)
    assert release_check.antenna(tmp_path)[0] == "PASS"
    (command, env), = seen
    assert command[:2] == [release_check.program(tmp_path, "kicad-rf-studio"), "new"]
    assert command[3:9] == ["--start", "U1.1", "--antenna", "AE1", "--band", "2400MHz:2483.5MHz"]
    assert Path(command[2]).read_bytes() == fixture.read_bytes() and env["QT_QPA_PLATFORM"] == "offscreen"
    schema = {"schema": 1}
    assert release_check.antenna(tmp_path)[0] == "FAIL"  # no kind: read with .get, a FAIL line
    assert [s.__name__ for s in release_check.STEPS] == ["build", "install", "gui", "antenna", "plugin", "privacy"]
    assert release_check.NEEDS["antenna"] == "install"
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_repo.py tests/test_release_check.py -q`. Expected: FAIL (no Antenna tutorial; `module 'release_check' has no attribute 'antenna'`).
- [ ] **Step 3: `tools/release_check.py`.** `antenna(tmp)`, docstring "(d) `new --antenna` by the fresh venv's console script on the release's own tests/fixtures/ifa2g4_pi.kicad_pcb, taken from tmp/source.zip, isolated: its project.json schema 2 and kind antenna, the installed importer and schema 2 at no cost (no openEMS runs)": the fixture extracted to `tmp / "source"`, then `[program(tmp, "kicad-rf-studio"), "new", <it>, "--start", "U1.1", "--antenna", "AE1", "--band", "2400MHz:2483.5MHz", "-o", str(tmp / "antenna")]` through `run(command, timeout=300, env=isolated(tmp))`; a non-zero exit is `failed(...)`; project.json's `schema` and `kind`, each read with `.get`, other than 2 and "antenna" give `("FAIL", f"…/antenna/project.json: schema {schema!r}, kind {kind!r}")`; else `("PASS", "new wrote an antenna project, schema 2, from tests/fixtures/ifa2g4_pi.kicad_pcb in the fresh venv")`. `NEEDS["antenna"] = "install"`, `STEPS = (build, install, gui, antenna, plugin, privacy)`; plugin's and privacy's letters become (e) and (f); the module docstring says six steps and names this one.
- [ ] **Step 4: `README.md`.** Install step 5 (:34) ends "…: select the chain's two end pads, or the antenna footprint (or one of its pads) and the radio pin, and press the kicad-rf-studio button." Development setup step 6 (:158): after "starts the GUI there offscreen," it gains "runs `new --antenna` there on `tests/fixtures/ifa2g4_pi.kicad_pcb`,". Then, after the Tutorial and before Development setup, this section; Task 11 adds each step's lines, from the acceptance run, after its command fence:

````markdown
## Antenna tutorial

This takes `ifa2g4_pi`, the synthetic 2.4 GHz board in `tests/fixtures` (KiCad's `Texas_SWRA117D_2.4GHz_Left` inverted-F, after TI's application note SWRA117D, fed from the radio's pad U1.1 through a pi network of 0402 parts: series L1, shunts C2 and C3), through `new --antenna`, `cost`, `run`, `retune` and `verify`, then compares it with `ifa2g4_pi_pour`, the same board with a ground pour inside the antenna's clearance. Run the commands as in the Tutorial above.

The times were measured on the development PC (Windows 11, 16 CPUs) at the Normal preset, `new`'s default, by the run through the GUI that closed Stage 3 (`docs/validation/<date>-stage3-exit.md`); that run compared with the pour that gate P3-E had verified, so the pour's run and verify times are P3-E's (`docs/validation/2026-11-01-p3-e.md`). `cost` prints your own machine's estimate before every run, and no runtime is promised. The excerpts are real output of that run; `<run folder>` stands for a run's folder in the per-user data folder, and `ifa2g4_pi`, `ifa2g4_pi_pour` and `compare` for the projects' and the compare's folders.

**`new --antenna`** finds the antenna footprint AE1 and its feed pad, traces the chain from the radio's pin U1.1 to it, and writes an antenna project for the band: `--antenna` takes the place of `--end` and `--band F_LO:F_HI` that of `--f0`. The whole board is simulated, in an air box with a PML absorber, and every part on the chain is a part port, so the network can be retuned.

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/ifa2g4_pi.kicad_pcb --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o ifa2g4_pi
```

**`cost`** splits the cells into board, air and PML, and prints the worst case before any run.

```
<venv>\Scripts\kicad-rf-studio cost ifa2g4_pi
```

**`run`** runs one job per port, P1 at the radio's pin and the part ports L1, C2 and C3, four at once. It gives S11 at the radio's pin for any part values, and no far field: a part port is not a part.

```
<venv>\Scripts\kicad-rf-studio run ifa2g4_pi
```

**`retune`** closes the part ports at new values, with no new run. These came from an E24 search over the run's layout, the values the GUI's snapping gives (C2 typed as 0.127pF snaps to 0.13pF). `0R` replaces a series part with a short and `open` removes a shunt part: `retune ifa2g4_pi L1=0R C2=open C3=open` shows the antenna through its feed line.

```
<venv>\Scripts\kicad-rf-studio retune ifa2g4_pi L1=0R C2=0.13pF C3=1pF
```

**`verify`** runs one job with every part in the grid at its applied value, as an ideal part, and records the far field: the radiation and total efficiency, the directivity, gain and realized gain, and the three cuts at f0 in `verify_summary.png`. After it, `retune` also prints the what-if total efficiency of each new set of values.

```
<venv>\Scripts\kicad-rf-studio verify ifa2g4_pi
```

**`compare`** reads both projects' verified results, which must share every setting, and marks each difference resolved or not. First the same steps on the pour board, then the compare, which writes `compare.csv` and `compare.png` into `compare`:

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/ifa2g4_pi_pour.kicad_pcb --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o ifa2g4_pi_pour
<venv>\Scripts\kicad-rf-studio run ifa2g4_pi_pour
<venv>\Scripts\kicad-rf-studio retune ifa2g4_pi_pour L1=0R C2=0.13pF C3=1pF
<venv>\Scripts\kicad-rf-studio verify ifa2g4_pi_pour
<venv>\Scripts\kicad-rf-studio compare ifa2g4_pi ifa2g4_pi_pour -o compare
```

In the GUI, New's kind Antenna takes the antenna footprint, the start pad and a band preset; Results shows S11 with the band shaded, the Smith chart and, from the run that holds the network, the efficiencies and the three cuts, its title naming that run; the Compare tab compares the open project with a variant. The KiCad button pre-fills New with the antenna kind when the antenna footprint, or one of its pads, is selected with the radio's pin.

### What these results do not tell you

- Every antenna result carries this line: "Relative: these antenna results compare variants of one board under identical settings; they do not predict measured performance."
- The board is alone in free space: no enclosure, hand, battery or cable. TI's AN043 measured a 5–10 MHz shift from a cable's position alone.
- Copper is a perfect conductor, so the radiation efficiency reads high; the parts' bodies are absent, and the parts off the chain are approximated.
- A difference is resolved only above 0.3 % of f0 for a frequency and 0.2 dB for an efficiency or a gain, at least three times the model's measured noise floor (gate P3-D, `docs/validation/2026-11-01-p3-d.md`). This antenna's resonance moves about 1.9 % per mm of its position near the ground's corner, which compare resolves.
- The retune stays what-if until P0-C: `verify` checks the layout reduction with ideal parts, not the vendor parts, and here its ideal network reads −12.5 dB at f0 where the retune's 0402 presets read −17.4 dB.
- Chip antennas and modules are refused, the matching chain up to their pad still runs as in the Tutorial, and sheet copper is not offered.
- A radio pin, feed and antenna pad in one line can be refused by the fit2d gate; raising `gates.fit2d_limit` in project.json is at your own risk.
- `meander915` is no 915 MHz example: on its synthetic board it resonates above its band.
````

  The `<date>` is the exit record's, filled in Task 11.
- [ ] **Step 5: Run them again.** Step 2's command. Expected: PASS (the README's code-span check finds `compare` a real subcommand).
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add README.md tools/release_check.py tests/test_repo.py tests/test_release_check.py
git commit -m "docs(readme): the antenna tutorial on the 2.4 GHz fixture and its limits; the release check runs new --antenna in the fresh venv (Stage 3 design 5.12 item 5)"
graphify update .
```

---

### Task 9 [code]: One antenna project through the window, opt-in

**Files:**
- Modify: `tests/test_gui.py` (after the Stage 2 real run); `README.md` (Development setup step 6 :158).

**Interfaces:**
- Consumes: Tasks 3 to 6's widgets and `Opened` fields; Stage 2's harness in `tests/test_gui.py` (`fail`, `until`, `opened`, `grab`, `items`, `column`, `dispose`, `events`); `pipeline.antenna_result`, `board_file`.
- Produces: `test_one_antenna_project_through_the_window_new_cost_run_retune_apply_verify_compare`, skipped unless `KRS_E2E_DIR` and `KRS_E2E_VARIANT` are set; `KRS_E2E_VARIANT` is a verified ground-pour `<GATES>/projects/<name>/project.json`, read in place, or the word `window`, which runs the pour through the window first (+1.5 h).

- [ ] **Step 1: Write the test,** in `tests/test_gui.py` after `test_one_real_run_through_the_window_new_cost_run_retune_apply_verify`:

```python
PI_VALUES = {"L1": "0R", "C2": "0.13pF", "C3": "1pF"}  # plan 3's E24 search; the gates verified the pour at them


# ponytail: run by hand only, so it can lag the window's API until it next runs; the fake-backed tests above pin each
# step's widgets meanwhile. Its setup copies Stage 2's real-run test's, which stays as Stage 2's exit record ran it
@pytest.mark.openems
@pytest.mark.skipif(not (os.environ.get("KRS_E2E_DIR") and os.environ.get("KRS_E2E_VARIANT")),
                    reason="one antenna project through the window (Stage 3 design 5.14 item 3): set KRS_E2E_DIR to an "
                    "empty folder outside the repository and KRS_E2E_VARIANT to a verified ground-pour project.json, "
                    "or to window")
def test_one_antenna_project_through_the_window_new_cost_run_retune_apply_verify_compare(qapp, monkeypatch):
    out = Path(os.environ["KRS_E2E_DIR"]).resolve()
    assert not out.is_relative_to(ROOT), "KRS_E2E_DIR must be outside the repository"
    out.mkdir(parents=True, exist_ok=True)
    assert not any(out.iterdir()), "KRS_E2E_DIR must be empty: a fresh data folder, as on a new install"
    assert qapp.platformName() == "offscreen"
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, str(out / "data"))
    monkeypatch.setenv("KRS_GRAB_DIR", str(out / "grabs"))
    for name in ("run_jobs", "ensure_calibrated"):
        monkeypatch.setattr(runs, name, fail)  # no run in the GUI process
    masks = [(str(out), "<KRS_E2E_DIR>")]
    reuse = os.environ["KRS_E2E_VARIANT"] != "window"
    if reuse:  # <GATES>/projects/<name>/project.json, read in place: usable before an hour is spent
        variant = Path(os.environ["KRS_E2E_VARIANT"]).resolve()
        masks.append((str(variant.parents[2]), "<GATES>"))
        assert pipeline.antenna_result(variant)["source"] == "T_VERIFY"
        vd = load_project(variant)  # design 5.14 item 3: the pour, verified at the same values
        assert (board_file(variant, vd).name, vd["verify"]["values"]) == ("ifa2g4_pi_pour.kicad_pcb", PI_VALUES)

    def ended(timeout):
        until(lambda: w.tick() or w.proc.poll() is not None, timeout=timeout)
        w.tick()

    def say(step, begin, lines):  # the record and the README quote these: no machine path shows in them
        line = " | ".join(lines)
        for real, shown in masks:
            line = line.replace(real, shown)
        print(f"e2e {step}: {time.monotonic() - begin:.0f} s: {line}", flush=True)

    def printed():  # what the terminal's command prints but its progress, as the CLI renders it
        return [render(e["code"], **e["params"]) for e in events(w.run_dir) if e["kind"] not in ("progress", "end")]

    def through(name):  # New, Cost, Run, a snapped retune, Apply and Verify of one board copy
        board, pj = out / "board" / f"{name}.kicad_pcb", out / "board" / name / "project.json"
        board.parent.mkdir(exist_ok=True)
        board.write_bytes((FIX / f"{name}.kicad_pcb").read_bytes())
        begin, f = time.monotonic(), w.new_form
        f.board.setText(str(board))
        w.board_chosen()
        w.pads_read.result(timeout=60)
        w.tick()
        f.kind.setCurrentIndex(f.kind.findData("antenna"))
        f.start.setCurrentText("U1.1")
        assert (f.antenna.currentData(), f.band.currentData(), f.preset.currentText()) == (
            "AE1", (2.4e9, 2.4835e9), "normal")  # New's defaults; the band and the preset are in compare's fingerprint
        f.create_button.click()
        made, notes = w.creating.result(timeout=120)
        assert made == pj
        w.tick()
        opened(w)
        assert w.project_status.text() == render("G_PROJECT_ANTENNA", path=str(pj), ref="AE1", f_lo_mhz="2400",
                                                 f_hi_mhz="2483.5", preset="normal")
        grab(w, f"e2e-{name}-new")
        say(f"{name} new", begin, [render(c, **p) for c, p in notes])
        begin = time.monotonic()
        w.cost_button.click()  # a fresh data folder: it calibrates this machine first
        ended(3600)
        assert w.cost_status.text() == render("G_END_DONE", exit_code=0), w.cost_status.text()
        assert events(w.run_dir, code="I_COST_SPLIT")  # the board's, the air's and the PML's cells
        say(f"{name} cost", begin, printed())
        opened(w)
        assert w.cost == w.run_dir and w.run_button.isEnabled()
        grab(w, f"e2e-{name}-cost")
        asked = []
        monkeypatch.setattr(w, "ask", lambda text: asked.append(text) or True)
        begin = time.monotonic()
        w.run_button.click()
        (cost_time,) = events(w.cost, code="I_COST_TIME")
        assert w.command == "run" and control.text(cost_time["code"], cost_time["params"]) in asked[0]
        ended(12 * 3600)
        assert (w.end["params"]["exit_code"], w.run_status.text()) == (0, render("G_END_DONE", exit_code=0)), \
            w.run_status.text()
        (kept,) = events(w.run_dir, code="I_RESULTS")
        assert (kept["params"]["kept"], kept["params"]["runs"]) == (4, 4)
        assert events(w.run_dir, code="I_ANTENNA_NO_FAR_FIELD")  # part ports: verify records it
        say(f"{name} run", begin, printed())
        grab(w, f"e2e-{name}-run")
        opened(w)
        r, begin = w.results, time.monotonic()
        assert column(r.parts, PART) == ["L1", "C2", "C3"] and len(r.canvas.figure.axes) == 2
        r.parts.item(0, VALUE).setText("0R")  # L1 bypassed
        r.parts.item(1, VALUE).setText("0.127pF")  # snapped to E24's 0.13pF (design 7's default)
        assert column(r.parts, VALUE) == list(PI_VALUES.values()) and not r.what_if.isHidden()
        w.tabs.setCurrentWidget(r)
        grab(w, f"e2e-{name}-retune")
        r.apply_button.click()
        code, lines = w.applying.result(timeout=300)
        w.tick()
        assert code == 0 and r.retune_status.text() == render("G_APPLIED", folder=str(pj.parent / "results"))
        assert {ref: q["value"] for ref, q in parts(load_project(pj)).items() if ref in PI_VALUES} == PI_VALUES
        say(f"{name} retune", begin, lines)
        opened(w)
        begin = time.monotonic()
        r.verify_button.click()  # applied: verify starts at once
        assert w.command == "verify"
        ended(12 * 3600)
        assert (w.end["params"]["exit_code"], w.run_status.text()) == (0, render("G_END_DONE", exit_code=0)), \
            w.run_status.text()
        opened(w)
        d = load_project(pj)
        assert d["verify"]["values"] == PI_VALUES and r.stale.isHidden()
        assert w.opened.verified[0][0] == "I_VERIFY_RESULTS"
        assert items(r.verify_lines) == [control.text(c, p) for c, p in w.opened.verified]
        assert all((Path(d["verify"]["run_dir"]) / p).is_file() for p in d["verify"]["far_field"].values())
        assert w.opened.far_source == ("T_VERIFY", d["verify"]["run_dir"])
        assert [ax.name for ax in r.canvas.figure.axes].count("polar") == 3  # the cuts at f0, drawn
        say(f"{name} verify", begin, printed())
        w.tabs.setCurrentWidget(r)  # verify's watch selected the Run tab
        grab(w, f"e2e-{name}-verify")
        return pj

    w = MainWindow()  # the real orchestrator (control.orchestrator)
    w.show()
    try:
        if not reuse:
            variant = through("ifa2g4_pi_pour")
        vd = load_project(variant)
        watched = (variant.parent, Path(vd["results"]["run_dir"]), Path(vd["verify"]["run_dir"]))

        def stamps():
            return {p: p.stat().st_mtime_ns for root in watched for p in [root, *root.rglob("*")]}

        before = stamps()
        pj = through("ifa2g4_pi")
        begin = time.monotonic()
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(variant), ""))
        w.comparison.variant_button.click()
        w.tick()
        w.comparison.compare_button.click()
        code, lines, cells = w.comparing.result(timeout=600)
        w.tick()
        resonance = next(p for c, p in lines if c == "I_COMPARE_RESONANCE")
        assert code == 0 and resonance["verdict"] == "T_RESOLVED" and w.comparison.table.rowCount() == len(cells) == 6
        assert not w.comparison.picture.pixmap().isNull() and (pj.parent / "compare" / "compare.png").is_file()
        assert stamps() == before  # the variant read in place, never written
        say("compare", begin, [render(c, **p) for c, p in lines])
        w.tabs.setCurrentWidget(w.comparison)
        grab(w, "e2e-compare")
        assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # design 4: the GUI process
    finally:
        dispose([w])  # a failed step leaves no run going
```

- [ ] **Step 2: Collect it.** `.venv/Scripts/python -m pytest tests/test_gui.py -q -k antenna_project_through -rs`. Expected: 1 skipped, with its reason (neither variable is set): it collects and its imports hold.
- [ ] **Step 3: `README.md`,** Development setup step 6 gains, after its real-run sentence: "One antenna project through the GUI, `ifa2g4_pi` at Normal run, retuned, verified and compared with a verified ground-pour project, runs with `KRS_E2E_DIR` set to an empty folder outside the repository and `KRS_E2E_VARIANT` to that project's `project.json`, or to `window` to make the pour through the GUI first: `python -X utf8 -m pytest tests/test_gui.py -k antenna_project_through -s`. It takes about the pi project's run plus its verify, 1.6 h on the development PC (3.1 h with `window`)."
- [ ] **Step 4: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add tests/test_gui.py README.md
git commit -m "test(gui): one antenna project through the window, opt-in: New, Cost, Run, a snapped retune, Apply, Verify and a compare against a verified ground pour read in place (Stage 3 design 5.14 item 3)"
graphify update .
```

---

### Task 10 [run]: The acceptance run

The controller's. Each block is one PowerShell call from the repo root; a long one runs in the background, waited on. Never kill python.exe or openEMS by name: they may be the owner's.

- [ ] **Step 1: The tip.** The full suite in the background, then the GUI tests in pt-BR. Expected: all pass; record the counts and `git rev-parse HEAD:src` in the ledger.
- [ ] **Step 2: The fake-backed grabs in both languages.** If `$env:TEMP\krs-font\krs_font.py` is gone, write it again as Stage 2 plan 3's Task 7 Step 5 gives it whole (`docs/superpowers/plans/2026-10-28-stage2-plan3-kicad-button.md`). Then:

```powershell
$env:PYTHONPATH = "$env:TEMP\krs-font"
foreach ($lang in @("en", "pt_BR")) {
  $env:KRS_TEST_LANGUAGE = $lang; $env:KRS_GRAB_DIR = "$env:TEMP\krs-grabs-plan5-$lang"
  .venv\Scripts\python.exe -m pytest tests/test_gui.py -q -p krs_font -k "antenna or compare or press or new_makes" }
Remove-Item Env:KRS_GRAB_DIR, Env:KRS_TEST_LANGUAGE, Env:PYTHONPATH
```

  Look at `antenna-results`, `antenna-advanced`, `antenna-verify`, `new-antenna`, `compare` and `handoff-antenna` in each folder with the Read tool: at 1200 × 800 every word is the catalog's, legible and unclipped; the six panels stand in one row, each readable, under the title's lines (relative, what-if, the far field's run); Advanced's Default column stops at 320 px and its Value column keeps its room, with no horizontal scroll bar; New shows no f0 or harmonics row in the antenna kind; the deltas table's headers, quantities, numbers (rounded as the lines round them) and verdicts are the language's. A defect is a fix in its owning task's file, test-first where a test can see it, its own `fix(gui): …` commit after the full suite and the GUI tests in pt-BR, then `graphify update .`. A 100 px assertion that fails only under `krs_font` (Segoe UI 9 moves Qt's widget heights) is such a defect.
- [ ] **Step 3: The release check,** in the background: `.venv\Scripts\python.exe tools/release_check.py *> "$env:TEMP\krs-plan5-release.log"`. Expected: exit 0 and six PASS lines (build, install, gui, antenna, plugin, privacy), about 100 s, no NOTE line.
- [ ] **Step 4: The pre-check,** seconds, read-only: the gates' pour still reads current, it is the pour verified at the tutorial's values, and a fresh `new` on the committed fixture has its settings.

```powershell
$v = Join-Path $HOME "krs-gates\projects\d-ifa2g4_pi_pour\project.json"; $p = Join-Path $env:TEMP "krs-plan5-precheck"
Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue
.venv\Scripts\python.exe -X utf8 -c "import sys; from pathlib import Path; from kicad_rf_studio import cli, pipeline; from kicad_rf_studio.core.project import board_file, load_project; p = Path(sys.argv[1]); v, d = pipeline.antenna_result(p), load_project(p); b = pipeline.fingerprint(load_project(cli.new_antenna('tests/fixtures/ifa2g4_pi.kicad_pcb', 'U1.1', 'AE1', (2.4e9, 2.4835e9), output=Path(sys.argv[2]))[0])); print(v['source'], board_file(p, d).name, d['verify']['values'], 'same settings' if b == v['fingerprint'] else sorted(k for k in b if b[k] != v['fingerprint'].get(k)))" $v $p
Remove-Item -Recurse -Force $p
```

  Expected: `T_VERIFY ifa2g4_pi_pour.kicad_pcb {'L1': '0R', 'C2': '0.13pF', 'C3': '1pF'} same settings`. A traceback with E_COMPARE_NO_RESULT (the pour's model hash moved), another board or other values, or a list of fields is the fallback: Step 5 with `$env:KRS_E2E_VARIANT = "window"` (+1.5 h), recorded as a deviation.
- [ ] **Step 5: The run** (§5.14 item 3), in the background, waited on, about 1.6 h:

```powershell
$e2e = Join-Path $env:TEMP "krs-plan5-e2e"
Remove-Item -Recurse -Force $e2e -ErrorAction SilentlyContinue
$env:KRS_E2E_DIR = $e2e; $env:KRS_E2E_VARIANT = Join-Path $HOME "krs-gates\projects\d-ifa2g4_pi_pour\project.json"
$env:PYTHONPATH = "$env:TEMP\krs-font"; $env:CSXCAD_INSTALL_PATH = "<openEMS folder>"
"src $(git rev-parse HEAD:src)" > "$env:TEMP\krs-plan5-e2e.log"
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_gui.py -k antenna_project_through -s -q -p krs_font *>> "$env:TEMP\krs-plan5-e2e.log"
```

  Expected at the end: `1 passed`, after the lines `e2e ifa2g4_pi new`, `cost`, `run`, `retune`, `verify` and `e2e compare`, each with `<KRS_E2E_DIR>` and `<GATES>` for the folders. Soft expectations, reported and never failed on: the run's 4 jobs about 1 h 2–4 min; verify about 28–30 min, at 2446.6 MHz and −12.5 dB as the gates' base verified (P3-D's repeat was bit-identical); compare: "Resonance: 2446.6 MHz to 2358.2 MHz, a shift of -88.5 MHz (-3.62 % of f0): resolved.", η_tot −1.07, −2.00 and −2.73 dB resolved, the peak gain −0.44 dB resolved, the bandwidth not compared (the pour has no −10 dB band). `1 skipped` means openEMS did not import: check `CSXCAD_INSTALL_PATH`. To stop it, only the app's own STOP: `New-Item -ItemType File (Join-Path (Get-ChildItem "$env:TEMP\krs-plan5-e2e\data\kicad-rf-studio\runs" -Directory | Sort-Object Name | Select-Object -Last 1).FullName STOP)`.
- [ ] **Step 6: The grabs,** `$env:TEMP\krs-plan5-e2e\grabs`, with the Read tool: `e2e-ifa2g4_pi-new` (the antenna kind, AE1, U1.1, the 2.4 GHz preset, Normal), `-cost` (the board/air/PML split, Worst case, Run… enabled), `-run` (P1, L1, C2, C3 with their verdicts, Finished (exit code 0)), `-retune` (0R, 0.13pF, 1pF; S11 and the Smith chart under the relative and what-if lines; the no-far-field line in the window's words), `-verify` (the Results tab: the six panels in one row, the title naming verify's run folder, the stale indicator hidden, verify's lines beside), `e2e-compare` (the lines, the ten-column table with its quantities, rounded numbers and verdicts, the overlays).
- [ ] **Step 7: Fix what fails, and the rerun rule.** Each defect is a [code] fix in its owning task's file, test-first where a test can see it, committed as `fix(...)` after the full suite and the GUI tests in pt-BR, then `graphify update .`. A fix that changes anything under `src/` but a message's wording (`core/messages.py` and the `.mo`) runs Steps 4 and 5 again (about 1.6 h); any other fix does not, and the record names the product code id the run ran at.

---

### Task 11 [doc]: The README's excerpts, the Stage 3 exit record and the close

- [ ] **Step 1: The README's excerpts.** After each command fence of the Antenna tutorial, a fence of that step's lines from `$env:TEMP\krs-plan5-e2e.log`, its ` | ` separators as line breaks, the folders written as the Tutorial writes them: the base's compare folder (`<KRS_E2E_DIR>\board\ifa2g4_pi\compare`) as `compare`, replaced first, then the base's project folder as `ifa2g4_pi`, the pour's as `ifa2g4_pi_pour`, a run's folder as `<run folder>`. new: I_ANTENNA, I_ANTENNA_JOIN, I_CHAIN, I_PORT, I_BAND, I_ANTENNA_DEFAULTS, I_WROTE; cost: the cells, their split, dt, Worst case, RAM; run: the four verdicts, I_RESULTS, the resonance, the three markers, both bandwidths, the no-far-field line; retune: the resonance, the markers, the bandwidths and the what-if line; verify: I_VERIFY_RESULTS, the resonance, the markers, the comparison and shift, the f0 far-field line, I_VERIFY_SCOPE_ANTENNA; compare, after the five-command block: the resonance, the bandwidth, the three η_tot lines, the gain, the thresholds and I_OUTPUTS. The second paragraph's `<date>` becomes the exit record's, and each step's time from its `e2e` line is said after its command, as the Tutorial does; the compare block says compare's own time, and the pour's run and verify times P3-E's (1 h 4 min and 27 min, `docs/validation/2026-11-01-p3-e.md`), its new and retune taking seconds. On the fallback (`window`), the pour's own `e2e` lines give its times and the paragraph's sentence on P3-E goes. `tests/test_repo.py` passes; the full suite, then commit `docs(readme): the antenna tutorial's excerpts and times, from the acceptance run (Stage 3 design 5.12 item 5)` and `graphify update .`.
- [ ] **Step 2: The exit record,** `docs/validation/<date>-stage3-exit.md`, `<date>` the day it is written, after Stage 2's, Markdown only, no machine path (`<KRS_E2E_DIR>`, `<GATES>`, `<openEMS folder>`):
  1. **Verdict:** one bold line (Stage 3 done or not by design §5.14), then one table, a row per item: 1, the five plans merged (plans 1 to 4 at `47aff31`, `39a570f`, `749c30e`, `bdab44a`; plan 5 fast-forward after this record) and the suite green in English and the GUI tests in pt-BR (Task 10 Step 1's counts, or the last run's); 2, the gates (section 3); 3, the acceptance run (below); 4, the owner's items (section 8). Then item 3's subsection: the e2e log as printed (the `src <id>` head line first), then a bullet per step: Cost (Worst case, the I_COST_SPLIT line, the calibration), Run (4 of 4, I_ANTENNA_NO_FAR_FIELD), the retune and its snap (0.127pF to 0.13pF), Apply, Verify (|ΔS11| at f0 and at most, the shift, the far-field files, the cuts drawn, the stale indicator hidden), Compare (the resolved deltas, both basis lines, the pour's files unchanged, the variant checked as the pour at PI_VALUES); the grabs (Task 10 Step 6); the soft check against the gates' base verify; openEMS absent from the GUI process.
  2. **Inputs:** the branch, its HEAD, the product code id (`git rev-parse HEAD:src`); a table of plans 1 to 5 (scope, commits, merge commit, the suite there); the designs; the git-ignored ledgers (`.superpowers/sdd/2026-1*-stage3-plan*-rulings-and-minors.md` and plan 5's); the evidence deleted afterwards (the e2e folder, the grabs, the logs, `<GATES>` after the merge).
  3. **The gates,** one row each: P3-A pass (`2026-10-29-p3-a.md`); P3-B pass (`2026-10-31-p3-b.md`); P3-C pass, every default kept, sheet copper not offered as its fallback (it moved the meander by 0.87 % against 0.5 %, A-35) (`2026-11-01-p3-c.md`); P3-D "fail on its pre-registered ±d criterion, explained: the ±0.3 mm moves gave −0.53 % and +0.59 % and up to 0.32 dB against 0.2 % and 0.1 dB, the position's slope (about 1.9 % per mm near the ground's corner) 20 times the even part; its fallback, the thresholds at three times the measured noise, applied with the noise proper (0.029 % and 0.029 dB, CP-D) leaves 0.3 % and 0.2 dB, which P3-E resolved at" (`2026-11-01-p3-d.md`); P3-E pass, −3.62 % of f0, 12.1 times the threshold (`2026-11-01-p3-e.md`); the refit, PML weight 8.92 and the small speed 0.559 at one job and 0.718 at four (A-38, `2026-11-01-p3-refit.md`); P3-F the owner's (A-40). Machine hours: P3-A's and about 33 h for P3-B to P3-E.
  4. **The release check, run locally:** Task 10 Step 3's six lines as printed, its wall time.
  5. **The README's antenna tutorial:** its excerpts are the acceptance run's, the pour's run and verify times P3-E's; the same commands' CLI path is `docs/validation/2026-10-30-antenna-matching-run.md`'s.
  6. **Stated limits and deviations:** the pour read in place from `<GATES>` at product code `cab329c`, its settings, model, board and values checked current by Task 10 Step 4 (or the fallback, recorded); Normal, not Stage 2's Draft (compare's fingerprint holds the preset); the what-if label stays (`RETUNE_VALIDATED` False, P0-C the owner's); P3-D explained; verify's ideal network against the 0402 presets (−12.5 against −17.4 dB at f0); the float32 frequencies fixed in plan 5 (the antenna CSVs now hold project.json's frequencies, their values moved in the last digits); a converter with a keep-out still read as a module (listed disabled in New, refused on a press: plan 2's tracer ceiling, its connector half closed by plan 5); the click-through with an antenna, the owner's; then one line per deferred minor and known limit in plans 1 to 5's ledgers, as Stage 2's §5 lists its plans', the minors fixed later left out.
  7. **Machine time:** per step, the estimate printed before it (Worst case; a fresh data folder prints no prediction line) against the measured time; the release check's wall time; Stage 3's total: the first run (25 min), the matching run (2 h 4 min), the gates (about 33 h), the acceptance (about 1.6 h, 3.1 h on the fallback).
  8. **Next step, the owner's items,** one table (item | default this work applied | what it gates), each a controller recommendation, owner unavailable, deduplicated from plans 1 to 5's ledgers and grouped:
     - **Carried from Stages 1 and 2:** the first push and its identity rewrite (none done); the deny-list review; P0-C ("do not start"); the engine redesign A-9/A-10 (not started; the what-if label stays); RFsim and NOTICE (now with KiCad's footprint library); the click-through on KiCad 9.0.7 and 10.x, now with the antenna pre-fill (about 2 min, non-blocking); the plugin identifier `org.kicadrfstudio.app`; the review of A-13 to A-40, each a controller recommendation; the native review of `po/pt_BR.po` with Stage 3's codes, plan 5's G_ wordings among them; Linux and the workflows after the push; the golden output pins bound to this PC's environment (re-recording them is a controller ruling); and one row for the rest of Stage 2's §7 table, unchanged by Stage 3 (PyPI; the install source and the README's release link; a one-command installer; the Windows Sandbox clean-machine run; the README's Linux steps on a real distribution; a tag-equals-version check; the protobuf floor; the release check's private list; the v1 time policy; the GUI's board save, cost before every run, the snapping series, PySide6 as a core dependency and the what-if wording), citing `docs/validation/2026-10-29-stage2-exit.md` §7.
     - **Design §7's defaults, as designed:** the whole board for antennas; chip and module antennas refused; the band presets 868 (863–870), 915 (902–928) and 2.4 GHz (2400–2483.5) plus custom; −10 dB with a −6 dB marker; absolute numbers shown with the relative label; PML_8 at λ/4 with MUR a project option and no fallback (A-36); solid copper, sheet not offered (A-35); runtime measured, not promised; placeholders as ports; the parts off the chain; the far field only from jobs that hold the network, the superposition deferred; the enclosure deferred; EMerge (P3-F) the owner's.
     - **Engine rulings of plans 2 to 4:** the capacitor rule (A-27); one lid with W_LIDS_LEFT_OUT; the converse refusals (0 Ω in series only, open in shunt only); verify's ideal network kept ideal (each part at its preset reactance at f0 the option); the fingerprint without `lid`; the post-hoc statistics CP3, CP5 and CP-D kept; E_DT_FLOOR at mesh n ≥ 3 on a staircased 45° track (lower `gates.dt_floor`); no product fix for the pad-in-line fit2d conflict (a comment and E_FIT2D's advice); sheet copper for wide gaps only (not offered); the detuned 915 MHz fixture (left; a tuned meander is future work); no matched M = 0 2.4 GHz fixture (the tutorial uses the pi variant); the cost refit (applied: every antenna cost line changed); runtime (25 min a 2.4 GHz job, about 6.7 h the meander's worst case, about 33 h the gates).
     - **New in plan 5:** the acceptance's compare against `<GATES>`' pour read in place (or the fallback); the acceptance at Normal; deleting `<GATES>` (about 0.6 GB) after the merge; the plot's efficiency and cuts from the current verify while the retune moves S11, labelled; the window's antenna figure in one row, the limits in the lines; Advanced's long defaults cut at 320 px; Compare writing into `<base project folder>/compare`, replaced each time, its table in the window's words and rounded as the lines; New's Band starting on 2.4 GHz; modules and chip antennas listed disabled with their reason as a tooltip, connectors skipped; G_NO_ANTENNA pointing to the matching chain; a module's or chip's refusal on every press that selects one; G_RESULTS_WRITE's wording (press the button that wrote it again) in Run and Verify too; the new G_BUTTON_ACTION reaching installed buttons only after `install-kicad-plugin` runs again.
     Then: plan 5's local fast-forward merge with its branch deleted, nothing pushed; `<GATES>` deleted on the controller's go after it.
- [ ] **Step 3: The design's Status line,** `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md`, gains at its end: "Stage 3 closed on `<date>` with plan 5's GUI, button and docs (exit record `docs/validation/<date>-stage3-exit.md`)."
- [ ] **Step 4: Commit,** the full suite and the GUI tests in pt-BR first:

```bash
git add docs/validation docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md
git commit -m "docs(validation): the Stage 3 exit record: design 5.14's four items with their evidence, the acceptance run through the window, the machine time and the owner's items"
graphify update .
```

- [ ] **Step 5: Close.** The whole-branch review; after any later commit, Step 4's suites again and the record's sections 1 and 2 brought up to date; then the local fast-forward merge into `main` and the branch deleted. Nothing is pushed. Then delete `$env:TEMP\krs-plan5-e2e`, the grab folders and the logs; then, on the controller's go, `<GATES>`.

---

## Not in this plan

- **The instant far-field retune by superposition:** deferred by the design (§3, §7). The plot's efficiency and cuts are the current verify's, labelled with its run, and the what-if η_tot lines give the retune's own value.
- **A tuned 915 MHz fixture:** plan 4's owner item; `meander915` resonates above its band, so the tutorial and the acceptance use the 2.4 GHz pi variant and the README warns against it.
- **Sheet copper in the GUI:** not offered (gate P3-C, A-35); Advanced hides `copper`, and the field and its branch stay.
- **P3-F, EMerge as a second solver:** the owner's (design §5.11, A-40).
- **SI (signal integrity):** a later stage, after Stage 3's exit.
- **The overlays on a canvas** (`draw_compare`, with the curves back from `compare_projects`): compare.png as a pixmap at its own size, in a scroll area; scaled to the tab's width if users want it whole.
- **The far-field frequencies in MHz in Advanced:** its value cell is JSON edited in place; Hz with its unit, the long default elided at 320 px.
- **A converter with a keep-out read as a module:** classify's connectors are skipped (Task 5's `_antennas`), but a DC-DC converter or another part with a keep-out still lists as a disabled module in New and gives a press that selects it G_ANTENNA_MODULE: plan 2's tracer ceiling, a class test if users meet it.
- **The real-KiCad click-through with an antenna** (does a click on the radiator select its footprint?): it joins the owner's click-through; the README says "the antenna footprint (or one of its pads)".
- **Apply's refusals in the window's words:** Apply prints the CLI's rendered lines (Stage 2's ponytail); the retune table refuses E_RETUNE_* in the window's words before Apply.
- **A fake-backed dry run of the acceptance test:** its widgets are the fake-backed tests' of Tasks 4 to 7, its New step Task 5's (the default band asserted, never looked up by findData), and the test checks its variant with `antenna_result`, its board file and its values before the first job; a test bug met at its compare costs one rerun.
- **The three obsolete `#~` entries in `po/pt_BR.po`** (plan 4's minor): Babel keeps them; harmless.

## Controller rulings (2026-11-01; binding)

The controller's fourteen rulings stand as given; the architect's follow, revised after the four reviews where marked, then the reviewer's. Each is a controller recommendation made while the owner is unavailable.

- Ruling 1 (the controller's): the GUI opens antenna projects: `control.open_project`'s schema-2 guard goes; a pure `antenna_lines` out of `antenna_outputs` serves both, so the GUI's lines equal the CLI's by construction (`tests/test_match_antenna.py`, `test_run_antenna.py` and `test_compare.py` unedited); `s11_at` takes a cached layout; `Opened` carries the far field, its source and its layout, read on the pool; `show_project` and `ResultsView` handle an antenna (`draw_antenna` on the canvas, its curve moved by `retrace_antenna` for the blit, ANTENNA_LIMITS); with part ports the efficiency and cut panels show the current verify's far field, labelled with its source, while the retune moves S11, the what-if η_tot lines giving the retune's own value — design §5.10, r1 — cost if wrong: a second figure layout for part ports.
- Ruling 2 (the controller's): New gains Kind (matching chain or antenna); for an antenna, an Antenna combo from one board read (printed antennas enabled; modules and chip antennas listed, disabled, with their G_ reason; classify's connectors skipped), the start pad, and a Band combo of 868 MHz (863–870), 915 MHz (902–928), 2.4 GHz (2400–2483.5) and Custom (`values.parse_band`); `create_project` calls `cli.new_antenna` exactly as it calls `cli.new`, nothing duplicated — design §5.10, §7, r1, r2 — cost if wrong: one combo.
- Ruling 3 (the controller's): retune, Apply and Verify for an antenna: `control.retuned` through `chain_results` and `antenna_lines` with the cached far-field layout; `verify_stale` compares bypasses (0R against open is stale); the retune table takes 0R and open; E_RETUNE_SHORT_SHUNT, E_RETUNE_OPEN_SERIES, E_RETUNE_ANTENNA_VALUE, E_ANTENNA_MODULE, E_ANTENNA_CHIP, E_COMPARE_KIND, E_COMPARE_NO_RESULT and I_ANTENNA_NO_FAR_FIELD get G_ wordings without terminal syntax in `control.GUI` — plan 3's "Not in this plan", r1 — cost if wrong: a wrong stale mark in the acceptance, whose L1 is 0R.
- Ruling 4 (the controller's): a Compare tab: Variant… opens a project; Compare runs `pipeline.compare_projects(base, variant, <base project folder>/compare, emit)` on the pool, never writing in the variant; its lines, a deltas table from compare.csv and compare.png as a pixmap; refusals through `control.message` — design §5.8, §5.10, r1 — cost if wrong: one tab.
- Ruling 5 (the controller's): Advanced for an antenna: its fields with their own defaults and units (the air gap, the boundary, the far-field frequencies and angle step, its T_max and region); copper, kind and schema hidden (sheet is not offered, plan 4); `flat_s` not listed — r1 — cost if wrong: a row.
- Ruling 6 (the controller's): the button: `control.Handed` gains kind and antenna; a selected printed antenna footprint, or one of its pads, gives the antenna kind and that antenna; another footprint's pad gives the start; the antenna's own pads are never the start (E_SAME_PADS or E_START_ON_GND otherwise); two antennas give G_HANDOFF_ANTENNAS; a selected module or chip antenna gives its refusal in New's status line, the kind left matching chain; classify's connectors are skipped; `show_pads` sets the kind and the antenna; G_BUTTON_ACTION is reworded; the helper, the handoff file, the manifest and `install-kicad-plugin` do not change — r2 — cost if wrong: a press that pre-fills the wrong kind.
- Ruling 7 (the controller's): every new message is a CATALOG code with its pt-BR msgstr, r1's and r2's wordings the default; numbers keep the decimal point; the GUI tests run in pt-BR too, and the 1200 × 800 test holds with the Compare tab and New's extra rows — pt-BR design — cost if wrong: a clipped label.
- Ruling 8 (the controller's): the float32 far-field frequencies: `far_field_of` snaps each to project.json's `far_field.f_hz` within a relative 1e-6 (`far_of` passes the project); a test rewrites a fixture h5's frequencies as float32; the antenna CSVs' first column then holds the project's exact frequencies — plan 3's deferred item, r3 — cost if wrong: CSV digits.
- Ruling 9 (the controller's): the small guards: `current_verify` returns None without results; the what-if `far_of` reads inside its try; `openems_versions`' TimeoutExpired and ValueError become E_OPENEMS_MISSING before any job; `run()`'s docstring — plan 3's deferred minors, r3 — cost if wrong: none.
- Ruling 10 (the controller's): the README gains "## Antenna tutorial" after "## Tutorial", on the committed `ifa2g4_pi` and `ifa2g4_pi_pour`: `new --antenna`, `cost`, `run`, a snapped retune (L1=0R C2=0.13pF C3=1pF), `verify`, `compare` against the pour; excerpts from the acceptance run, this PC's times; a "What these results do not tell you" list from design §1 and §7; `tests/test_repo.py` pins the commands; one cheap release-check step on the antenna fixture (no fake worker, no GUI pages); NOTICE unchanged, its fixture-board entry already covering the variants — design §5.12 item 5, r3 — cost if wrong: a README paragraph.
- Ruling 11 (the controller's): the acceptance (§5.14 item 3) is an opt-in real-run test in `tests/test_gui.py` (the `openems` marker; skipped unless KRS_E2E_DIR and KRS_E2E_VARIANT are set), Stage 2's harness: New, Cost, Run (4 of 4 kept, I_ANTENNA_NO_FAR_FIELD), a snapped retune, Apply, Verify (the far-field files, the cuts drawn, the stale mark gone), Compare against the gates' verified `d-ifa2g4_pi_pour`, read in place (its files' mtimes unchanged; the resonance resolved); grabs under KRS_E2E_DIR; openEMS never imported by the GUI process; the controller runs it (about 1.6 h) after a pre-check; fallback: the pour through the window too (+1.5 h), recorded — design §5.14 item 3, r4 — cost if wrong: 1.5 h.
- Ruling 12 (the controller's): the Stage 3 exit record `docs/validation/<date>-stage3-exit.md`, after Stage 2's: §5.14's four items with their evidence (P3-D "fail on its move criterion, explained", P3-F the owner's), the acceptance run, the machine time and the owner's items consolidated from plans 1 to 5, deduplicated, grouped, each with its default; the gates' folder deleted by the controller after the record is merged — design §5.14 item 4, r4 — cost if wrong: none.
- Ruling 13 (the controller's): no product default changes; v1 byte for byte (the golden pins); the CLI's outputs unchanged but the float32 snap in the antenna CSVs — design §3 — cost if wrong: a pin moved.
- Ruling 14 (the controller's): the order: the pipeline and post refactors and guards, control, the window's Results and Advanced, New, Compare, the button, the docs and the release check, the acceptance test, then the controller's run, the README's excerpts from it and the exit record — the GUI reuses the refactors, and every code task lands before the run — cost if wrong: a reorder.
- Ruling (revised after review): Task 1 (core.post, core.project, spec) comes before Task 2 (pipeline), since `antenna_lines` calls `far_of(record, project)`, which Task 1 introduces with its four callers; the snap, the figure's curve and window layout, and the band's defaults are one task of small core changes, each pinned by its own test; the openEMS probe's guard joins ruling 9's other guards in Task 2 — ruling 14 leaves the two's order open — cost if wrong: one more review gate.
- Ruling (revised after review): `far_of(record, project=None)`: the default keeps `tests/test_match_antenna.py:239`'s one-argument call unedited (ruling 1), and every pipeline caller passes the project (ruling 8); a spy on `far_field_of` pins verify's, the what-if's and compare's reads, which the fake's default list cannot show — cost if wrong: none.
- Ruling (revised after review): `antenna_lines(path, project, res, *, errors_as_lines=False, far=_UNREAD, far_lay=None) -> (lines, far, far_lay)`, a module sentinel telling "not read" from "read: none", as `core.project`'s `_MISSING` does; its try holds the far field's whole read (current_verify to s11_at), one step wider than ruling 9's far_of, and verify's ponytail comment moves with the what-if branch; `antenna_outputs` gives only the run's far field to its files and its PNG, never verify's, so the CLI's bytes stay, a spy on antenna_png pinning it — r1's recommendation made exact — cost if wrong: one parameter.
- Ruling: the new pipeline tests live in a new `tests/test_antenna_lines.py`, since the three protected files stay unedited — ruling 1 — cost if wrong: one file.
- Ruling: `draw_antenna` returns its axes (S11, Smith) and `retrace_antenna` moves the S11 axes' first line and the Smith chart's last two, as `draw_summary` and `retrace_summary` do for v1; `antenna_png` ignores the return, so its bytes stay — r1 — cost if wrong: none.
- Ruling (review): the window's antenna figure is `draw_antenna(..., gui=True)`: the far field's panels in one row, the limits foot left to the window's lines, which end with them; antenna_png never passes it — the 2 × 3 grid under its title and five-line foot collapses on the Results canvas at 1200 × 800 (28 px axes in English, constrained layout given up in pt-BR; 76 and 60 px without the foot; one row without it 113 px and up in both languages, probed by three reviews and the reviewer); a canvas in a scroll area at 750 px was the alternative, hiding the cuts at 1200 × 800 — cost if wrong: a keyword and an assert.
- Ruling (revised after review): the band's defaults become helpers, `antenna_t_max` in `core/model/spec.py` (beside `pulse`; `core.project` cannot import spec) and `far_field_hz` in `core/project.py`, used by `cli.new_antenna`, `make_antenna_project` and Advanced; the 2.4 GHz list is pinned literally, as the gates' pour holds it, since antenna_dict calls the helper itself — r1 — cost if wrong: two functions.
- Ruling (revised after review): control's antenna work for Results and Advanced is one task (Task 3); New's board read and band presets land with New (Task 5), as Compare's control lands with Compare and the button's with the button: each feature's control first, then its window, inside its task, ruling 14's order kept; each message lands in the task whose widget shows it: G_ANTENNA_MODULE, G_ANTENNA_CHIP and G_NO_ANTENNA with New (Task 5), whose G_KIND_CHAIN their QUOTED entries name — the reviews: Task 3 held three features — cost if wrong: one more review gate.
- Ruling: `Handed` also carries `kinds`, the press board's antenna kinds with connectors skipped, so a press fills New's Antenna combo from its one read (ruling 6 named two fields; the combo needs the board's candidates) — cost if wrong: one field.
- Ruling (review): one helper, `control._antennas(b)` (Task 5), gives New's list and a press's kinds, its ponytail naming the connector half closed and the converter half left — the reviews — cost if wrong: none.
- Ruling: a module's or chip's refusal on a press comes from a selected footprint only, not from a selected pad's footprint: a v1 user picking a module's pad as the chain's end gets none; a printed antenna counts from either — r2's table — cost if wrong: one line on some presses.
- Ruling (revised after review): G_RESULTS_WRITE joins `control.GUI` (r1's proposal): Compare's lines go through `control.text`, and E_RESULTS_WRITE advises a terminal command; its wording advises pressing the button that wrote the file again, no more (Apply rewrites neither verify's files nor compare's, and is hidden without part ports), so it needs no QUOTED entry; it also rewords Run's and Verify's E_RESULTS_WRITE in the window — the G_ rule test — cost if wrong: one message.
- Ruling (revised after review): Compare's table shows compare.csv's ten DELTA_COLUMNS as `control.compare`'s cells: the quantity in the window's words (four G_QUANTITY_ codes, compare's lines' own words), f in MHz, the numbers rounded as delta_lines rounds them (DIGITS), the verdict as T_RESOLVED or T_NOT_RESOLVED, the header fitted to its contents; its headers are seven new G_COL_ codes (G_COL_F_MHZ among them) with T_BASE, T_VARIANT and G_COL_UNIT reused, as a template is its own msgid (`tests/test_sexpr.py`); for the same reason the tab is G_TAB_COMPARE "Compare" and the button G_COMPARE "Compare the projects" — the reviews: unrounded floats and English identifiers in a pt-BR window — cost if wrong: header words.
- Ruling (revised after review): compare.png sits in a QScrollArea at its own size, the area's widget resizable (a label whose pixmap changes after setWidget keeps 12 × 14 px otherwise, probed): a pixmap label alone would set the tab's minimum to the PNG's 1500 × 1050 and break the 1200 × 800 test; compare_png draws on the pool beside the canvas's draws (separate figures; matplotlib keys its font cache by thread), a ponytail comment — ponytail — cost if wrong: a scroll bar.
- Ruling: `control.compare` returns its cells only on exit 0; on 2 (a held file) the lines carry G_RESULTS_WRITE and the table and the picture are emptied, so no stale table shows — cost if wrong: none.
- Ruling (revised after review): New's Band starts on the 2.4 GHz preset, the band of the tutorial's board and of design §1's first case, set by its index: `findData` finds None and str data, but tuple data only as the very object stored (probed on PySide6 6.12); the presets are literal labels, numbers and units being the same in both languages — r1 — cost if wrong: one index.
- Ruling (revised after review): the Antenna combo lists references only, a disabled entry's reason its tooltip, in rich text so that Qt word-wraps it: a 200-character item would widen the window past 1200, and a plain tooltip runs some 1600 px wide — the size test — cost if wrong: a hover.
- Ruling (review): `show_antennas` keeps the press's antenna current, else the first printed one, also after a press on two: G_HANDOFF_ANTENNAS names both and asks to pick, and none current would make Create's refusal G_NO_ANTENNA, wrong for a board with two — cost if wrong: a project of the shown antenna.
- Ruling (review): G_NO_ANTENNA says what still applies (the matching chain, QUOTED G_KIND_CHAIN, design §5.1, §8 risk 8) and shows only after a read that succeeded (`chosen` set, no read pending); a refused read's refusal stays, and a read going on fills the combo — cost if wrong: a silent Create while a read runs.
- Ruling: G_FAR_FIELD_FROM names the run folder's name, not its path, in the figure's title, which wraps at the figure's width — cost if wrong: a longer title.
- Ruling: `verify_stale` reads bypasses for an antenna only (the bypass when there is one, else `port_value`), so v1's indicator stays — design §3 — cost if wrong: none.
- Ruling: Advanced's band-dependent defaults are computed under a guard, a band that does not read leaving them out, never v1's T_max: Advanced must open a project its checks refuse — Stage 2 design §5.3 — cost if wrong: none.
- Ruling (review): Advanced's Default column is fitted to its contents but at most 320 px (Interactive, after each display), so an antenna's 200-character far-field default keeps ruling 5 without squeezing the Value column (2407 px against 100 px otherwise); v1's widths stay as they are (probed); a global maximum section size would also cut v1's 367 px field names — cost if wrong: a dragged column.
- Ruling (revised after review): KRS_E2E_VARIANT is a verified pour's `<GATES>/projects/<name>/project.json`, read in place and checked before the first job by `antenna_result` (T_VERIFY), its board file (`ifa2g4_pi_pour.kicad_pcb`) and its verify values (PI_VALUES; the gates' d-ifa2g4_pi_dxp is verified at them too), or the word `window` for the fallback; the variant's project folder and its two run folders are snapshotted; `<GATES>` is masked as the variant's third parent — r4 — cost if wrong: a rerun.
- Ruling (revised after review): the pre-check is `antenna_result` on the pour, its board file and verify values printed, plus a fresh `new`'s fingerprint against the pour's, seconds and read-only: compare's own two conditions and the variant's identity, stronger than ruling 11's model-hash check alone — r4 — cost if wrong: none.
- Ruling (revised after review): the README's excerpts name the tutorial's own folders (`ifa2g4_pi`, `ifa2g4_pi_pour`, `compare` for the base's compare folder, `<run folder>`), as the v1 tutorial does, in place of ruling 10's `<RUN>` and `<GATES>`, which mean nothing to a reader running these commands; the exit record keeps `<KRS_E2E_DIR>` and `<GATES>` — cost if wrong: a few placeholders.
- Ruling (revised after review): the excerpts come from the acceptance's e2e lines, which print what the terminal prints (each step's events rendered as the CLI renders them, in English, without progress; `new`'s notes; Apply's retune output; compare's lines); on the planned path the pour's run and verify are not run, so the compare block carries compare's lines and time and the pour's times are P3-E's, cited (1 h 4 min and 27 min); the README's section lands in Task 8 without them — ruling 14's order — cost if wrong: none.
- Ruling (revised after review): the release check's new step is `antenna` (it needs install; between gui and plugin), on the fixture taken from the release's own source zip, its order and need pinned by a unit test and named in the README's Development setup step 6; lpf915 is not added, the installed importer being exercised once — r3 — cost if wrong: one more call.
- Ruling (revised after review): the fake-backed grabs of the antenna pages, `antenna-advanced` among them, are reviewed in both languages before the acceptance run (Task 10 Step 2) — Stage 2's visual review — cost if wrong: minutes.
- Ruling (revised after review): the acceptance reruns after any fix under `src/` but a message's wording; any other fix does not, and the record names the product code id it ran at — the reviews: the first rule missed code the run exercises (cli.new_antenna, core/post/antenna.py, far_of, s11_at, chain_results) — cost if wrong: 1.6 h.
- Ruling: the Compare tab sits between Results and Advanced (tab 4): the tests address tabs 0 to 3 alone by index — cost if wrong: none.
- Ruling (revised after review): `board_choices` (Task 5) takes New's read, one `load_board` for the pads and the kinds; `control.pads` loses its one product caller and stays as v1's tests' oracle (eight lines read the pickers against it) — ponytail — cost if wrong: two lines kept.
- Ruling (review): the acceptance test copies Stage 2's opt-in setup (about 15 lines) instead of hoisting it: Stage 2's test stays as its exit record ran it, and both run by hand only — cost if wrong: two copies to keep in step.
- Ruling (disclosure, the architect's): the architect's probes ran in a scratch folder with the repo's venv, in memory, with no openEMS, no KiCad and no run: `control.fields` of `antenna_dict` (its leaves, and v1's defaults on them); the 2.4 GHz band's far-field list and its float32 values (2441750016 and 2409277696 for the first two; relative errors under 4.6e-8); `antenna_kinds` on the fixtures (AE1 printed on the 2.4 GHz boards and meander915; lpf915's J1 a "module" among the connectors J1 and J2); the presets' T_max (85, 79 and 30 ns) and air gaps (86.846019, 83.091036 and 31.228381 mm); the fake far-field fixture (the sphere's 2449999872 and 2400000000 Hz as float32; the cuts at one frequency); `draw_antenna`'s axes (3 lines on S11, 6 on the Smith chart; 2 or 6 axes, 3 of them polar); the pi chain (L1 series RF_A–RF; C2 shunt RF_A–GND; C3 shunt RF–GND; chain nets RF_A and RF); `bypass` (0 on an L, 0R on any part, OPEN in any case) and `port_value` (1p equal to 1pF); PySide6's combo data (tuples and None round trip; `findData` finds None and str data, a tuple only as the very object stored, as the reviews corrected), a disabled first item staying current, `QFormLayout.setRowVisible` and `isRowVisible` on a layout, a QScrollArea's and a QTableWidget's 70-pixel minimums; ifa2g4_pi's pads; `snapped` giving 0.13pF for 0.127pF and keeping 0R and open. No suite ran — cost if wrong: none.
- Ruling (disclosure, the reviewer's): probes in a scratch folder with the repo's venv, offscreen, no openEMS, no KiCad, no run: the antenna figure on the Results canvas at 1200 × 800 in both languages (2 × 3 with its foot: 28 and 13 px axes, constrained layout given up in pt-BR; without it 76 and 60 px; one row without it 113 px and up, with and without the parts' rows); Advanced's columns with the Default column capped at 320 px (v1's [367, 441, 103, 211] px unchanged, an antenna's [367, 236, 320, 211] with no scroll bar, a 200 px Value column in pt-BR); `findData` on an equal tuple (−1) and on None (found); 0pF on a C (snapping leaves it, `bypass` and `port_value` refuse it); the gates' pour and dxp projects (both verified at PI_VALUES, their boards ifa2g4_pi_pour and ifa2g4_pi_dxp, far_field.f_hz equal to project.py's expression); P3-E's pour times (3862 and 1647 s); matplotlib 3.11.2's font cache keyed by thread; the revised test snippets and the pre-check parse. No suite ran — cost if wrong: none.

## Open issues, ruled by the controller (2026-11-01; owner unavailable)

The reviser's six open issues are ruled here, each a controller recommendation.

1. **The rulings stand as revised.** The window's antenna figure is `draw_antenna(..., gui=True)`: its six panels sit in one row, and the limits foot is left to the window's lines. `antenna_png` never passes the keyword, so the CLI's PNG is unchanged. Advanced's Default column is capped at 320 px, keeping ruling 5's far-field default visible.
2. **A 100 px assertion that fails only under `krs_font`** (Segoe UI 9 moves Qt's widget heights) is a layout defect, fixed in Task 10 Step 2. The pre-authorized fix is the canvas in a scroll area, test-first where a test can see it, in its own `fix(gui): …` commit. — cost if wrong: one fix commit.
3. **compare.png stays at its own size in a scroll area.** If Task 10 Step 2's grab review finds the Compare tab unusable at 1200 × 800, scaling the picture to the viewport's width is the pre-authorized fix (one call). — cost if wrong: a scroll bar.
4. **compare_png drawing on the pool thread** beside the Results canvas is a recorded residual risk. The figures are separate, and matplotlib 3.11.2 keys its font cache by thread; a lock is the upgrade if a crash ever shows. — cost if wrong: one lock.
5. **G_RESULTS_WRITE's wording** ("press the button that wrote it again") stands for every writer: Run, Verify, Compare, an M = 0 run and a single trace. Apply's cheaper path for part ports stays unsaid. — cost if wrong: one sentence.
6. **Ruling 14 is read per feature:** `board_choices` and `BANDS` land with New (Task 5), `compare` with the Compare tab (Task 6) and `handed` with the button (Task 7). Each control function lands with the widget that first needs it. — cost if wrong: none.
