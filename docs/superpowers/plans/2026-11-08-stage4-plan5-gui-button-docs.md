# Stage 4 Plan 5: The GUI, the Button and the Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open, make, retune, verify and compare signal-integrity projects in the GUI, pre-fill New from a track, arc or via selected in KiCad, document the SI workflow in the README and the release check, and close Stage 4 with one SI project run end to end through the window and its exit record.

**Architecture:**
- **The CLI's functions, composed once.** A pure `pipeline.si_view(project, res)` comes out of `write_outputs`: the reading and lines that `run` and `retune` print are the ones the window shows on a read and on each retune, carried in `ChainResults.reading`. `draw_si(..., gui=True)` draws the window's figure without the limits foot and with no |S| panel stretched under −100 dB by an exact zero, and `retrace_si` moves its curves in place for the blit.
- **An SI retune runs off the GUI thread.** Its chain update and reading took 68 ms in memory on usb2_hs's 8-port layout (scikit-rf's Circuit 28 ms, the layout's indicators 11 ms, se2gmm 26 ms), over Stage 2's 50 ms (Stage 2 design §2 goal 4), so the window submits it to a one-thread executor of its own and only retraces and blits on the GUI thread. v1's and the antenna's stay as they are.
- **The window gains, nothing more:** New's SI kind calling `cli.new_si` as New calls `cli.new`; Compare's SI quantities (`control.cells`); the button's tracks, arcs and vias through a tracer walk (`si_candidates`, `p_side`). Then the README's SI tutorial, one cheap release-check step, an opt-in real-run test with a fake-backed dry run of the same body, the controller's runs on a copy of gate P4-F's plane-gap run, and the Stage 4 exit record.

**Tech Stack:** Python ≥ 3.11 (dev venv 3.14.2), PySide6-Essentials (offscreen in tests), matplotlib's QtAgg canvas, numpy, scipy, scikit-rf 2.2, kicad-python 0.8 (button and `tests/fake_kicad.py` only); no new dependency. openEMS 0.37.0 and CSXCAD 0.7.0 in the workers only (Tasks 13 and 14). pytest (`openems` marker); `tools/catalog.py` (Babel, dev extra).

**Spec:**
- **The design, binding:** `docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md`, §5.12 item 5: §5.10 in full, the README's SI tutorial on the USB 2.0 fixture, the release check and the Stage 4 exit record; §5.14 items 3 and 4; with §1, §3, §6, §7 and §8.
- **The Stage 1 spec** `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (A-1 to A-64; Task 16 adds A-65 to A-69) and Stage 2's design `docs/superpowers/specs/2026-10-27-stage2-gui-and-button-design.md` (§2 goal 4, §5.3, §5.4, §5.5) for the GUI's and the button's rules.
- **Plans 1 to 4** (`docs/superpowers/plans/2026-11-02-stage4-plan1-pins-and-si-hooks.md`, `2026-11-03-stage4-plan2-si-project.md`, `2026-11-04-stage4-plan3-si-results.md`, `2026-11-04-stage4-plan4-the-gates.md`) and their "Not in this plan"; their archives `.superpowers/sdd/2026-11-03-stage4-plan1-rulings-and-minors.md`, `2026-11-03-stage4-plan2-rulings-and-minors.md`, `2026-11-04-stage4-plan3-rulings-and-minors.md`, `2026-11-05-stage4-plan4-rulings-and-minors.md` (git-ignored); the records `docs/validation/2026-11-03-p4-a.md`, `2026-11-03-si-first-run.md`, `2026-11-04-si-results.md`, `2026-11-06-p4-b.md`, `2026-11-07-p4-c.md`, `2026-11-07-p4-d.md`, `2026-11-07-p4-e.md`, `2026-11-08-p4-f.md`, `2026-11-08-p4-refit.md`, and Stage 3's exit record `docs/validation/2026-11-02-stage3-exit.md` (the acceptance harness and the record's model).
- **Research** (git-ignored): `.superpowers/sdd/stage4-plan5-research/` r1 (the GUI), r2 (the button), r3 (docs and release), r4 (acceptance and exit).

**Branch:** `stage4-plan5`, from `main` at `5302aae`. This plan is `docs/superpowers/plans/2026-11-08-stage4-plan5-gui-button-docs.md`. Commands run from the repo root with `.venv/Scripts/python`. A path without a folder is under `src/kicad_rf_studio/`. Line references are main's at `5302aae`; find a moved line by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage4-plan5 main`; `git diff --stat 5302aae HEAD -- src tests tools po pyproject.toml` prints nothing.
2. Commit this plan on the branch.
3. After Task 17: the whole-branch review, a local fast-forward merge into `main`, the branch deleted. Nothing is pushed.

## Global Constraints

- **v1, the antenna and SI byte for byte:** their golden models and outputs stay as `tests/test_golden_v1.py`, `tests/test_golden_antenna.py` and `tests/test_golden_si.py` pin them; only `tests/fixtures/golden_antenna.json`'s `"code"` stamp changes (Task 11). A task that moves another pin is wrong: stop for a ruling, never re-record.
- **The CLI's outputs unchanged but ruling 18's list, with rulings 7's and 13's own:** compare's new refusal on a differing current target_ohm, marker_hz or rise_s (Task 3); every command's E_PROJECT_FIELD {field lines, expected T_EXPECT_SI_OWN_NETS} on a hand-edited project whose lines share a net (Task 3, ruling 7); argparse's "invalid REF.PAD:REF.PAD value" in place of "invalid _ends value" (Task 11, ruling 13); I_SI_NO_LOSS in si_lines' place of W_NO_SECTIONS; the reworded W_JOB_T_MAX, I_SI_COST_SPEED and E_S2P_BAND; W_STAIRCASED_SI on an SI project (Task 2). `si_summary.png`, `compare.png` and every CSV keep their bytes.
- **SI only behind the schema:** every SI branch tests `core.project.si(data)`; v1's and the antenna's GUI paths, their retune on the GUI thread included, stay as they are.
- **openEMS in workers only** (Stage 1 §3.1): the CLI, the orchestrator, `core.post`, the GUI process and pytest's own process never import openEMS or CSXCAD; each window test ends with `assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules`.
- **Qt offscreen in tests** (`tests/conftest.py`), no modal dialog in a test: `QFileDialog.getOpenFileName` and `MainWindow.ask` are monkeypatched; pool work is awaited with `.result(timeout=…)` or `.exception(timeout=…)`, then `w.tick()`; an SI retune with `w.retuning.result(timeout=…)`, then `w.take_retune()`, but where a test lets the event loop take it.
- **Messages:** every new or changed user-facing string is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, compiled by `.venv/Scripts/python tools/catalog.py` in the same task (run it, set each empty msgstr, run it again); templates unique; a G_ wording keeps a subset of its CLI line's params and no terminal syntax (`tests/test_gui_control.py::test_every_gui_wording_keeps_its_cli_params_and_drops_terminal_syntax`); a G_ message that names a widget gets a `QUOTED` entry (`tests/test_sexpr.py`); numbers keep the decimal point; pt-BR keeps the catalog's terms (linha, par diferencial, vítima, alvo, marcador, ilha, trilha, via, checagem; "campo" for a form row, never "linha") and the glossary's nevers (`tests/test_sexpr.py::test_the_pt_br_catalog_keeps_the_glossarys_nevers`: never "rodar" nor "favor").
- **Tests:** test-first; a guard that passes on main says so in its run step. Tier (a) never runs openEMS, KiCad, the network or a build: the fake CLI (`FAKE_PREFIX`), the fake worker (`calibrated`, `KRS_FAKE=network`), `tests/fake_kicad.py`, handoff files from `press`. `KrsError` tests check `.code` and `.params`. Tests never touch a real KiCad folder, the real Documents folder, KiCad's settings or the real data folder (`no_kicad`, `fake`), and never write under `tests/fixtures`.
- **Full suite** before every commit that touches src, tests, tools, po or pyproject.toml: `.venv/Scripts/python -m pytest -q`, about 31 minutes at `5302aae` (2446 passed, 6 skipped), alone, in the background, waited on. After a task that touches `gui/` or a message, also, in PowerShell, `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q; Remove-Item Env:KRS_TEST_LANGUAGE` (42 passed, 3 skipped at `5302aae`). A commit that touches docs/ or README.md alone reuses the last green suite at the same src, tests and tools, named in the ledger.
- **The gates' folder** `<GATES>` (`krs-gates-si` in the user's home) is never written; its `data\kicad-rf-studio\settings.json` and its `steps` folder are never opened; it is never any command's data folder. Task 13 copies one project and one board out of it and reads that project's run folder in place.
- **Git:** no push; the pre-commit privacy gate runs on every commit, never `--no-verify`; no commit message carries a co-author line; the messages as given. No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name: write `<openEMS folder>`, `<KiCad 9 bin folder>`, `<GATES>`, `<RUN>`, `<VARIANT>`, `<KRS_E2E_DIR>`, `<run folder>`.
- **Files:** every new `.py` starts with `# SPDX-License-Identifier: GPL-3.0-or-later`; code and docs in English.
- **Python** only with a script, `-c` or `-m`: never a bare interactive `python`, least of all in a background shell.
- **Never two pytest processes at once.**
- **Workflow:** `graphify query "<question>"` before reading code; `graphify update .` after each commit. Ponytail: reuse `cli.new_si`, `draw_si`, `si_lines`, `read`, `compare_projects`, `control.retuned`, `partner_ends`, the pool, `Tail`, `sentences()`, `combo()`, Stage 3's real-run harness, `verified_si`, the fake worker, `press` and `tests/fake_kicad.py`; the standard library and the installed dependencies; a `ponytail:` comment on each corner cut with a known ceiling.

## Review Focus

1. **An SI retune computed on the GUI thread, or its figure redrawn in full on each edit** (a frozen window: `control.retuned` measured 68 ms on usb2_hs, `draw_si` 176–370 ms a draw, r1). Expected: the edit only submits the retune; its end retraces and blits, taken by the window's own timer. Check: Task 5's `test_an_si_retune_runs_off_the_gui_thread_and_blits_within_the_budget` (the edit and the take each under 50 ms, `canvas.draw` never called, `pipeline.layout` failing throughout, the axes unchanged) and the end of `test_only_the_latest_si_retune_is_drawn_and_a_revert_or_a_read_drops_it` (an edit the event loop alone takes through `tune_timer`, which then stops), in pt-BR too.
2. **A stale SI retune drawn over a newer edit, a Revert or a new read** (the off-thread retune's race). Expected: only the latest submission is shown; Revert, a read and another project drop the one in flight. Check: Task 5's `test_only_the_latest_si_retune_is_drawn_and_a_revert_or_a_read_drops_it`, on Scc21, a curve the network fake's retune moves.
3. **The button pre-filling the N side, the ESD array's flow-through pads as the ends, or a form that Create refuses.** Expected: an N track names the P net and its partner; usb2_hs's four IC or connector pads (J1.3, U1.3, U2.3, U2.4) pre-fill no end and are named; two end pads pre-fill the connector's first (J1.3 → U1.3, the tutorial's); a single net's press sets se50 and creates as pre-filled. Check: Task 9's `test_a_press_on_a_track_arc_or_via_pre_fills_its_line` (MCU_D- gives net MCU_D+; usb2_hs gives G_HANDOFF_SI_ENDS with count 4) and its window test (qspi_clk's press creates new_si's own project), and Task 8's `test_the_buttons_line_is_the_walk_through_its_parts_on_the_p_side`.
4. **A compare writing in the variant's folder, or two SI projects read at different targets.** Expected: compare writes into the base's `compare/` only, and refuses two projects whose current target_ohm, marker_hz or rise_s differ. Check: Task 3's `test_compare_reads_each_si_project_at_its_current_target_marker_and_rise`; Task 7's window test (the variant's folders' mtimes unchanged); Task 12's acceptance on `<VARIANT>`.
5. **A stale verify read as current through an SI bypass** (`port_value` reads both `0R` and `open` on a C as None). Expected: an SI line's 0R against open is stale. Check: Task 4's `test_an_si_verify_is_stale_when_a_bypass_changes`.

The GUI's SI lines drifting from the CLI's are pinned by construction (Task 1's `si_view` against the run's printed lines, Task 5's Results test against them); `si_summary.png`'s and `compare.png`'s bytes by Task 1's guard and digests; the 1200 × 800 fit with the SI rows by Task 6; the d-fill refusal by Task 7.

---

## File structure

```
core/post/si.py (SYMBOLS, draw_si's gui, retrace_si), pipeline.py (ChainResults.reading, si_view, write_outputs);
  tests/test_post_si.py, tests/test_si_run.py                                                                   # T1
core/post/si.py (si_lines), core/geometry/__init__.py (build_geometry), messages, po, .mo, README.md (:146);
  tests/test_post_si.py, tests/test_si_geometry.py, tests/test_p4_fixtures.py, tests/test_sexpr.py              # T2
pipeline.py (SI_READ_AT, si_result), core/project.py (check_project), messages, po, .mo; tests/test_si_compare.py,
  tests/test_project.py                                                                                          # T3
gui/control.py (open_project, default_series, retuned, verify_stale, UNITS, fields), messages, po, .mo;
  tests/test_gui_control.py                                                                                      # T4
gui/window.py (TABLE_2D, TUNE_MS, ResultsView, MainWindow), messages, po, .mo; tests/test_gui.py                  # T5
gui/window.py (NewForm, create_project, show_pads, show_project), gui/control.py (GUI, text), messages, po, .mo;
  tests/test_gui.py, tests/test_gui_control.py, tests/test_sexpr.py                                              # T6
gui/control.py (QUANTITIES, MARKS, INSERTION, cells, compare), messages, po, .mo; tests/test_gui_control.py,
  tests/test_gui.py (stamps), tests/test_sexpr.py                                                                # T7
button.py (read), core/kicad/tracer.py (p_side, si_candidates); tests/fake_kicad.py, tests/test_button.py,
  tests/test_si_lines.py                                                                                         # T8
gui/control.py (Handed, handed, _si_handed), gui/window.py (show_pads), messages, po, .mo; tests/test_gui_control.py,
  tests/test_gui.py, tests/test_sexpr.py                                                                         # T9
README.md, tools/release_check.py; tests/test_repo.py, tests/test_release_check.py                               # T10
NOTICE, tests/fixtures/golden_antenna.json, cli.py (_ends); tests/test_repo.py, tests/test_cli_si.py               # T11
tests/test_gui.py (si_through, the acceptance, its dry run), README.md (Development setup)                          # T12
the controller's runs; fixes in their owning files                                                                # T13, T14
README.md (excerpts); the Stage 1 spec (A-65 to A-69); docs/validation/<date>-stage4-exit.md, the design's Status # T15-T17
```

The `.mo` is `src/kicad_rf_studio/locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo`; every task that adds or changes a message commits it with `po/pt_BR.po` and `po/kicad_rf_studio.pot`.

---

### Task 1 [code]: The SI view, the window's figure and its retrace

**Files:**
- Modify: `core/post/si.py` (`draw_si` :353-406; new `SYMBOLS` before it and `retrace_si` after it); `pipeline.py` (imports :54-55; `ChainResults` :626-641; new `si_view` after `chain_results` :644-688; `write_outputs`' SI branch :722-728).
- Test: `tests/test_post_si.py`, `tests/test_si_run.py`.

**Interfaces:**
- Consumes: `read`, `si_lines`, `_span`, `distance_mm`, `db`, `si_limits`, `si_png`; the tests' `pair6`, `P100`, `SE`, `ROUTE1`, `line_s`, `F` (test_post_si), `si_project` (test_cli_si), `result_lines` (test_match_antenna), `calibrated`.
- Produces:
  - `core.post.si.SYMBOLS = {"Sdd21": (1, 0), "Sdd11": (0, 0), "Scc21": (3, 2), "Scd21": (3, 0), "S21": (1, 0), "S11": (0, 0)}`: each |S| curve's mixed-mode entry, by the label draw_si gives it.
  - `draw_si(fig, curves, project, title, label=None, gui=False) -> list`.
  - `retrace_si(axes: list, r: Reading) -> list | None`.
  - `pipeline.si_view(project: dict, res: ChainResults) -> tuple[Reading | None, list[tuple[str, dict]]]`.
  - `ChainResults.reading: Reading | None = None`, its last field.

- [ ] **Step 1: The guard and the bytes, on main.** `tests/test_post_si.py` gains (the import from `core.post.si` already holds `db`, `draw_si` and `read`):

```python
def test_draw_si_draws_each_s_curve_by_its_symbol_as_before():  # ruling 18: a guard for Task 1's SYMBOLS
    for r, project, want in ((read(pair6(0.05, 0.02), F, P100, 3.0), P100,
                              (("Sdd21", 1, 0), ("Sdd11", 0, 0), ("Scc21", 3, 2), ("Scd21", 3, 0))),
                             (read(line_s(ROUTE1, F), F, SE, 4.0), SE, (("S21", 1, 0), ("S11", 0, 0)))):
        curves = draw_si(Figure(), [("p", r)], project, "T")[1].lines[:-1]  # the marker's line last
        assert [c.get_label() for c in curves] == [s for s, _, _ in want]
        assert all(np.array_equal(c.get_ydata(), db(r.m[:, i, j])) for c, (_, i, j) in zip(curves, want))
```

  Run `.venv/Scripts/python -m pytest tests/test_post_si.py -q -k each_s_curve`: PASS on main (a guard). Then record in the ledger the digests of si_png's bytes, one curve, two curves (compare.png's draw) and a net:

```bash
.venv/Scripts/python -c "import hashlib, os, sys; os.environ['LANGUAGE'] = 'en'; sys.path[:0] = ['tests', 'tools']; from test_post_si import F, P100, ROUTE1, SE, line_s, pair6; from kicad_rf_studio.core.post.si import read, si_png; p, n = read(pair6(0.05, 0.02), F, P100, 3.0), read(line_s(ROUTE1, F), F, SE, 4.0); print([hashlib.sha256(si_png(c, j, 'T', 'L')).hexdigest()[:16] for c, j in (([('a', p)], P100), ([('a', p), ('b', p)], P100), ([('n', n)], SE))])"
```

- [ ] **Step 2: Write the failing tests.** `tests/test_post_si.py` (the import from `core.post.si` gains `retrace_si`):

```python
def test_the_windows_si_figure_has_no_foot_no_s_under_minus_100_db_and_moves_in_place():  # ruling 1; RF 1
    pair = read(pair6(0.05, 0.02), F, P100, 3.0)  # an ideal pair: its Scd21 an exact zero, FLOOR_DB
    assert draw_si(Figure(), [("p", pair)], P100, "T")[1].get_ylim()[0] < -100  # si_summary.png's, as before
    fig = Figure()
    axes = draw_si(fig, [("p", pair)], P100, "T", "label", gui=True)
    assert not [t for t in fig.texts if render("I_LIMIT_SI_CROP") in t.get_text()]  # the limits go to the lines
    assert axes[1].get_ylim()[0] == -100.0 and axes[2].get_ylim()[0] >= -100.0
    quiet = draw_si(Figure(), [("p", read(pair6(), F, P100, 3.0))], P100, "T", gui=True)  # exact-zero crosstalk
    assert quiet[2].get_ylim()[0] < -100 and not any(ax.yaxis_inverted() for ax in [*axes, *quiet])  # autoscaled
    other = read(pair6(0.1, 0.05, 0.2e-9 + 2e-12), F, P100, 3.0)  # NEXT, FEXT and the N leg moved
    limits = [(ax.get_xlim(), ax.get_ylim()) for ax in axes]
    moved = retrace_si(axes, other)
    assert moved == [*axes[0].lines, *axes[1].lines[:-1], *axes[2].lines]  # the marker's line stays where it is
    assert [(ax.get_xlim(), ax.get_ylim()) for ax in axes] == limits  # at the limits drawn
    k = (other.t >= -2 * other.rise[0]) & (other.t <= (other.t_far or 0) + 2 * other.rise[1])
    assert np.array_equal(axes[0].lines[0].get_ydata(), other.z[k])
    assert np.array_equal(axes[0].lines[1].get_ydata(), other.z_link[k])
    assert [line.get_marker() for line in axes[0].lines[2:]] == ["x" if s else "o" for _, _, s in other.levels]
    assert np.array_equal(axes[1].lines[3].get_ydata(), db(other.m[:, 3, 0]))  # Scd21
    assert np.array_equal(axes[2].lines[1].get_ydata(), db(other.m[:, 5, 0]))  # FEXT into AUX
    cut = read(np.zeros((len(F), 6, 6), complex), F, P100, 3.0)  # nothing passes the line: no level
    assert cut.levels is None and retrace_si(axes, cut) is None  # another count of levels: the window draws in full
    net = draw_si(Figure(), [("n", read(line_s(ROUTE1, F), F, SE, 4.0))], SE, "T", gui=True)  # S21 and S11, no xt
    m = read(line_s([(50.0, 4.0, 15.0), (61.0, 4.0, 30.0), *ROUTE1[2:]], F), F, SE, 4.0)  # its 60 Ω at 61 Ω
    assert len(net) == 2 and retrace_si(net, m) == [*net[0].lines, *net[1].lines[:-1]]
    assert np.array_equal(net[1].lines[0].get_ydata(), db(m.m[:, 1, 0]))  # S21, found by its label
```

  `tests/test_si_run.py` (imports gain `from dataclasses import replace`):

```python
def test_the_si_view_is_what_run_prints_and_write_outputs_reports(tmp_path, calibrated, monkeypatch):  # RF 1, ruling 1
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    res = pipeline.chain_results(pj, p, errors_as_lines=True)
    reading, lines = pipeline.si_view(p, res)
    assert lines == result_lines(p["results"]["run_dir"])[1:len(lines) + 1]  # run printed them after I_RESULTS
    assert np.array_equal(reading.m, read(res.chain, res.lay.f, p, p["results"]["route"]["eeff"]).m)
    outputs = pipeline.write_outputs(pj, p, "x", errors_as_lines=True)
    assert outputs[:len(lines)] == lines
    assert [c for c, _ in outputs[len(lines):]] == ["I_WHAT_IF", "I_OUTPUTS", *si_limits(p)]
    assert pipeline.si_view(p, replace(res, chain=None)) == (None, res.lines)  # a part's refusal: no reading
    assert res.reading is None  # chain_results leaves it to si_view's callers
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_post_si.py tests/test_si_run.py -q`. Expected: FAIL (`cannot import name 'retrace_si'`; `module 'kicad_rf_studio.pipeline' has no attribute 'si_view'`).
- [ ] **Step 4: `core/post/si.py`.**
  - `SYMBOLS` as in Interfaces, before `draw_si`, with `# |S| curves' mixed-mode entries by their labels: draw_si draws them, retrace_si finds them`. `draw_si`'s local `symbols` becomes the names `("Sdd21", "Sdd11", "Scc21", "Scd21")` for a pair and `("S21", "S11")` for a net, each plotted from `SYMBOLS[name]`; its output does not change (Step 1's guard and digests prove it).
  - `draw_si(..., gui=False)`: the `fig.supxlabel` only without `gui`; with it, after the legends, each |S| panel (`axes[1:]`) gets `lo, hi = ax.get_ylim()` then `ax.set_ylim(max(lo, min(-100.0, hi - 40.0)), hi)`, with `# ponytail: −100 dB at the lowest, and 40 dB under the top at least, so a panel whose curves all lie under −100 dB (an exact-zero victim, a far one) keeps its autoscale; a floor per panel if users ask`. Docstring gains: "With `gui` (the window's Results canvas, plan 5) there is no foot, the limits being the window's lines, and an |S| panel whose top lies above −60 dB has its bottom at −100 dB at the lowest, where an exact zero (FLOOR_DB) would stretch it to −300 dB and squeeze every curve a retune moves at those limits (a panel with every curve under −100 dB keeps its autoscale, never inverted); si_png never passes it, so si_summary.png and compare.png keep their bytes."
  - `retrace_si(axes, r)`, after `draw_si`: `k = _span(r)`; `axes[0].lines[0]` and `[1]` `set_data(distance_mm(r.t[k], r.eeff), r.z[k])` and `r.z_link[k]`; the level markers `axes[0].lines[2:]`, one per level, each `set_data([distance_mm(t, r.eeff)], [z])` and `set_marker("x" if short else "o")`, but first `return None` when their count is not `len(r.levels or ())`; each of `axes[1].lines[:-1]` `set_ydata(db(r.m[:, i, j]))` with `i, j = SYMBOLS[line.get_label()]`; with three axes, `axes[2].lines` taken in pairs (NEXT, FEXT) against the victims' ports `range(4 if paired else 2, r.m.shape[1], 2)` (paired: `"Sdd21" in` the |S| labels), NEXT `db(r.m[:, v, 0])`, FEXT `db(r.m[:, v + 1, 0])`; no draw, no rescale. Returns `[*axes[0].lines, *axes[1].lines[:-1], *(axes[2].lines if len(axes) > 2 else [])]`. Docstring: "Moves the curves that draw_si drew of one reading on `axes` (its return) to the reading `r`, at the limits drawn (the GUI's instant retune, Stage 4 design 5.10): both TDRs on _span(r), each level's marker and its mark, each |S| curve by its label (SYMBOLS) and each victim's NEXT and FEXT. Returns those Line2D, or None when `r` holds another count of levels than drawn, which a full draw then shows." Comment `# ponytail: a level that appears or goes (an arrival found or lost) costs one full draw; a fixed pair of marker lines if users meet it often`.
- [ ] **Step 5: `pipeline.py`.**
  - The import from `core.post.si` gains `Reading`; `ChainResults` gains, last, `reading: Reading | None = None`, its docstring "…; and an SI chain's reading when si_view gave one (the GUI's read and retune keep it, plan 5), else None".
  - `si_view(project, res)`, after `chain_results`: without `res.chain`, `(None, [*res.lines])`; else `reading = read(res.chain, res.lay.f, project, project["results"]["route"]["eeff"])` and `(reading, [*res.lines, *si_lines(project, reading, project["results"]["route"])])`. Docstring: "An SI result's reading and lines (Stage 4 design 5.6, 5.10), no file written: with a chain, read of it at the run's route's εeff, and chain_results' `res` lines followed by si_lines; without one (a part's refusal), None and `res`'s lines. What write_outputs reports before its label, I_OUTPUTS and limits, and what the GUI shows on a read and on each retune, so the two never differ."
  - `write_outputs`: `lines = [*res.lines]` stays for v1; for an SI project `reading, lines = si_view(project, res)`, and with a reading the three SI files as now. Its docstring says the SI lines are si_view's.
- [ ] **Step 6: Run them again.** Step 3's command, then `.venv/Scripts/python -m pytest tests/test_golden_si.py tests/test_si_compare.py tests/test_golden_v1.py -q`. Expected: PASS. Then Step 1's digest command: the same three digests as the ledger's.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "refactor(si): the SI reading and lines out of write_outputs as si_view, shared by the CLI and the GUI, and the window's figure without its foot, with no |S| stretched under -100 dB and its curves moved in place by retrace_si (Stage 4 design 5.6, 5.10)"
graphify update .
```

---

### Task 2 [code]: The CLI's words that change

**Files:**
- Modify: `core/post/si.py` (`si_lines` :296-297 and its docstring); `core/geometry/__init__.py` (`build_geometry`, after the antenna's feed check :132-134); `core/messages.py` (W_STAIRCASED :30 neighbour, I_SI_COST_SPEED :158, W_JOB_T_MAX :180, E_S2P_BAND :196, G_S2P_BAND :420, new I_SI_NO_LOSS and W_STAIRCASED_SI); `po/*`; the `.mo`; `README.md` (:146, the v1 tutorial's verify excerpt).
- Test: `tests/test_post_si.py` (`test_a_route_with_no_level_says_why` :245-251), `tests/test_si_geometry.py` (:51, :111), `tests/test_p4_fixtures.py` (:96), `tests/test_sexpr.py`.

**Interfaces:**
- Produces: I_SI_NO_LOSS in si_lines' last place when `route["loss_db"]` is None; an SI project's staircase notes as `("W_STAIRCASED_SI", {"net": net})`; the reworded templates below, their params unchanged.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_post_si.py`: `test_a_route_with_no_level_says_why`'s last line becomes `assert none[-1] == ("I_SI_NO_LOSS", {}) and "I_SI_LOSS_CONDUCTOR" not in dict(none)`.
  - `tests/test_si_geometry.py:51`: the set gains `"W_STAIRCASED_SI"`, so the straight usb2_hs still guards against a staircase warning in its SI words (a guard: it passes on main, where no code emits it).
  - `tests/test_si_geometry.py:111`: `assert ("W_STAIRCASED_SI", {"net": "USB_D+"}) in notes and len(geom.stairs) == 4 and "W_STAIRCASED" not in dict(notes)`.
  - `tests/test_p4_fixtures.py:96`: `.count("W_STAIRCASED_SI") == 2`. v1's and the antenna's W_STAIRCASED stay pinned by `tests/test_cli_cost.py:96-106` and `tests/test_antenna_geometry.py:32`, unedited.
  - `tests/test_sexpr.py` (the import from `core.messages` gains `english`):

```python
def test_plan_5s_words_say_where_s_ends_what_refreshes_the_si_speed_and_where_a_load_is_read():  # rulings 2, 4, 13
    assert english("W_JOB_T_MAX", port="P1", t_ns="22.48", residual_db="-55.0").startswith(
        "P1: not converged where its S ends, at 22.48 ns with a residual of -55.0 dB: at T_max, or,")
    assert "any run, of any kind, with this many jobs at once" in CATALOG["I_SI_COST_SPEED"]
    assert "1.9 times" in CATALOG["I_SI_COST_SPEED"]  # a pool-2 SI run, priced high (docs/validation/2026-11-08-p4-refit.md)
    assert all("MHz its load is read over" in CATALOG[code] for code in ("E_S2P_BAND", "G_S2P_BAND"))
    assert "−2.27 %" in CATALOG["W_STAIRCASED_SI"] and "+5.35 %" in CATALOG["W_STAIRCASED_SI"]  # gate P4-B
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_si.py tests/test_si_geometry.py tests/test_p4_fixtures.py tests/test_sexpr.py -q`. Expected: FAIL (W_NO_SECTIONS in si_lines, W_STAIRCASED on usb2_hs_45, `KeyError: 'W_STAIRCASED_SI'`); the :51 guard passes.
- [ ] **Step 3: The code and the README's line.**
  - `si_lines`: `return lines + [("I_SI_NO_LOSS", {})]` in W_NO_SECTIONS' place; its docstring names I_SI_NO_LOSS.
  - `build_geometry`, after the antenna's feed check: `if si(project):  # gate P4-B's 45° pairs, in an SI project's own words (A-58)` then `stairs = [("W_STAIRCASED_SI", p) if c == "W_STAIRCASED" else (c, p) for c, p in stairs]`; the docstring's SI paragraph says so.
  - `README.md:146`, the v1 tutorial's verify excerpt, becomes the same job's line in the new words, `english("W_JOB_T_MAX", port="P2", t_ns="39.99", residual_db="-69.7")` once Step 4 has reworded it, so the README never quotes a line the product no longer prints.
- [ ] **Step 4: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_SI_NO_LOSS (new) | No loss estimate: the measured line has no straight, axis-aligned section whose 2D cut reads, so neither the copper's nor the dielectric's loss over its route is estimated, and its distances take the stack's largest εr. | Sem estimativa de perda: a linha medida não tem trecho reto alinhado aos eixos cujo corte 2D se leia, então nem a perda no cobre nem a do dielétrico ao longo da rota dela são estimadas, e as distâncias dela tomam o maior εr do empilhamento. |
| W_STAIRCASED_SI (new) | Net {net} has copper that is not axis-aligned (45° segments or arcs), which the mesh staircases. Gate P4-B measured a staircased 45° pair −2.27 % (90 Ω) and +5.35 % (100 Ω) off its axis-aligned twin at mesh n 2, the second past the 5 % budget, so the run goes on, but a 45° pair's accuracy is not validated, and whether such a pair is refused or run at a finer mesh is not decided yet. For a validated result, route the measured nets with horizontal and vertical tracks. | A rede {net} tem cobre que não está alinhado aos eixos (segmentos a 45° ou arcos), que a malha aproxima em degraus. A checagem P4-B mediu, com malha n 2, um par a 45° em degraus −2.27 % (90 Ω) e +5.35 % (100 Ω) distante do gêmeo alinhado aos eixos, o segundo além da tolerância de 5 %; então a execução continua, mas a precisão de um par a 45° não é validada, e ainda não está decidido se um par assim é recusado ou executado com malha mais fina. Para um resultado validado, roteie as redes medidas com trilhas horizontais e verticais. |
| W_JOB_T_MAX (changed) | {port}: not converged where its S ends, at {t_ns} ns with a residual of {residual_db} dB: at T_max, or, for a signal-integrity job whose residual still fell fast enough there, past it, where that fall slowed or the ring rule's ceiling came. S is kept and flagged; raise t_max_s in project.json for a converged result. | {port}: não convergiu onde o S dele termina, em {t_ns} ns, com resíduo de {residual_db} dB: em T_max ou, numa tarefa de integridade de sinal cujo resíduo ainda caía rápido o bastante ali, depois dele, onde essa queda diminuiu ou chegou o teto da regra do anel. O S é mantido e sinalizado; aumente t_max_s no project.json para ter um resultado convergido. |
| I_SI_COST_SPEED (changed) | This signal-integrity model's speed is taken as {ratio} × the calibration's per-job speed, the gates' measured ratio of SI models to the calibration's uniform one, until any run, of any kind, with this many jobs at once measures that level. With two jobs at once the gates measured SI models at 1.229 × it, so such a run is priced about 1.9 times long, on the safe side. | A velocidade deste modelo de integridade de sinal é tomada como {ratio} × a velocidade por tarefa da calibração, a razão medida pelas checagens entre modelos de SI e o modelo uniforme da calibração, até que qualquer execução, de qualquer tipo, com esse número de tarefas simultâneas meça esse nível. Com duas tarefas simultâneas, as checagens mediram os modelos de SI a 1.229 × ele, então uma execução assim é estimada cerca de 1.9 vezes mais longa, por segurança. |
| E_S2P_BAND (changed) | Part {ref}: {path} covers {f_lo}–{f_hi} MHz, not the {f1}–{f2} MHz its load is read over, and it is never extrapolated. Give a file that covers that band, or, for a C, L or R, a value with `retune PROJECT {ref}=VALUE`. | Componente {ref}: {path} cobre {f_lo}–{f_hi} MHz, não os {f1}–{f2} MHz em que a carga dele é lida, e nunca é extrapolado. Indique um arquivo que cubra essa banda, ou, para um C, L ou R, um valor com `retune PROJECT {ref}=VALUE`. |
| G_S2P_BAND (changed) | Part {ref}: {path} covers {f_lo}–{f_hi} MHz, not the {f1}–{f2} MHz its load is read over, and it is never extrapolated. Choose a file that covers that band, or, for a C, L or R, clear the file to use its value. | Componente {ref}: {path} cobre {f_lo}–{f_hi} MHz, não os {f1}–{f2} MHz em que a carga dele é lida, e nunca é extrapolado. Escolha um arquivo que cubra essa banda, ou, para um C, L ou R, limpe o arquivo para usar o valor dele. |

- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_cli_cost.py tests/test_antenna_geometry.py tests/test_golden_si.py tests/test_si_run.py tests/test_repo.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po README.md
git commit -m "fix(si): the CLI's words plan 5 changes: no loss estimate said as such, W_JOB_T_MAX where its S ends, I_SI_COST_SPEED what refreshes the level and the pool-2 overprice, E_S2P_BAND the band a load is read over, and an SI project's staircase warning with gate P4-B's 45-degree pairs (Stage 4 design 5.3, 5.6, 5.9)"
graphify update .
```

---

### Task 3 [code]: Compare at the current target, marker and rise, and two lines never on one net

**Files:**
- Modify: `pipeline.py` (new `SI_READ_AT` before `si_result`; `si_result` :1272-1281); `core/project.py` (`check_project` :380-419); `core/messages.py` (new T_EXPECT_SI_OWN_NETS); `po/*`; the `.mo`.
- Test: `tests/test_si_compare.py` (`test_compare_refuses_si_projects_it_cannot_compare`'s variant edit, and a new test), `tests/test_project.py` (`test_an_si_field_out_of_its_range_is_named`'s parametrize).

**Interfaces:**
- Consumes: `verified_si`, `twin`, `compared`, `si_dict`.
- Produces: `pipeline.SI_READ_AT = ("target_ohm", "marker_hz", "rise_s")`; `si_result(path)["fingerprint"]` holds project.json's current values of those three over the record's; `check_project`'s E_PROJECT_FIELD `{"field": "lines", "expected": "T_EXPECT_SI_OWN_NETS"}`.

- [ ] **Step 1: Write the failing tests.** `tests/test_si_compare.py`, new:

```python
def test_compare_reads_each_si_project_at_its_current_target_marker_and_rise(tmp_path, calibrated, monkeypatch):
    a = verified_si(tmp_path, monkeypatch)  # ruling 5, plan 3's deferred item; Review Focus 4
    assert pipeline.verify(a) == 0
    b = twin(a, tmp_path / "b")
    for path in (a, b):  # edited alike after the verify: no part of the model, so the results stay current
        save_project(path, {**load_project(path), "target_ohm": 85.0})
    assert pipeline.si_result(a)["fingerprint"]["target_ohm"] == 85.0  # as Results reads it
    assert load_project(a)["verify"]["fingerprint"]["target_ohm"] == 90.0  # the record keeps the run's
    compared(a, b, tmp_path / "out")  # both read at 85 Ω: exit 0
    save_project(b, {**load_project(b), "target_ohm": 90.0, "marker_hz": 250e6, "rise_s": 1e-9})
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(a, b, tmp_path / "out2")
    assert (e.value.code, e.value.params) == ("E_COMPARE_SETTINGS", {"fields": "marker_hz, rise_s, target_ohm"})
    assert not (tmp_path / "out2").exists()
```

  `test_compare_refuses_si_projects_it_cannot_compare`'s variant edit becomes (its expected `{"fields": "ends, target_ohm"}` unchanged):

```python
    d = load_project(b)
    d["verify"]["fingerprint"] = {**d["verify"]["fingerprint"], "ends": ["J1.3", "J1.2", "U1.3", "U1.2"]}  # no victim
    d["target_ohm"] = 85.0  # another current target: compare reads it, not the record's (plan 5)
    save_project(b, d)
```

  `tests/test_project.py`, `test_an_si_field_out_of_its_range_is_named`'s parametrize gains:

```python
    (lambda d: {"lines": [d["lines"][0], {**d["lines"][1], "chain": {**d["lines"][1]["chain"],
                                                                     "nets": ["USB_D-", "MCU_D+"]}}, d["lines"][2]]},
     "lines", "T_EXPECT_SI_OWN_NETS"),  # MCU_D+ on two lines: new refuses it (E_SI_LINE_SHARED), and so does Save
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_si_compare.py tests/test_project.py -q`. Expected: FAIL (the record's 90.0 in the fingerprint; compare exits 0 on the differing three; no E_PROJECT_FIELD on lines; the refusal test's fields read "ends" alone).
- [ ] **Step 3: The code.**
  - `pipeline.SI_READ_AT` with `# an SI reading's settings that no model spec holds: read at project.json's current values, as Results reads them (A-67); the tolerance is left out, since no delta reads it and compare.png draws the base's band alone`. `si_result`'s fingerprint: `{**record["fingerprint"], **{key: project[key] for key in SI_READ_AT}}`; docstring gains "Its fingerprint holds project.json's current SI_READ_AT, which it reads at, over the record's, so two projects edited alike compare at those values and two edited apart are refused (E_COMPARE_SETTINGS)."
  - `check_project`, in the SI checks between the roles' "lines" and "pair": `("lines", "T_EXPECT_SI_OWN_NETS", len(nets) == len(set(nets)))` with `nets = [n for line in lines for n in line["chain"]["nets"]]`; the docstring adds "its lines' nets each on one line (as `new` refuses with E_SI_LINE_SHARED)".
- [ ] **Step 4: The message,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| T_EXPECT_SI_OWN_NETS | a list of lines whose nets are each their own: no net on two lines | uma lista de linhas cujas redes são de cada uma: nenhuma rede em duas linhas |

- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_si.py tests/test_cli_si.py tests/test_compare.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "fix(si): compare reads each SI project at its current target, marker and rise and refuses two that differ; check_project refuses two lines on one net, as new does (Stage 4 design 5.1, 5.8)"
graphify update .
```

---

### Task 4 [code]: control opens, retunes and verifies an SI project, and gives Advanced its SI fields

**Files:**
- Modify: `gui/control.py` (imports :25-36; `open_project` :219-264; `default_series` :310-312; `retuned` :366-389; `verify_stale` :416-436; `UNITS` :614-618; `fields` :631-667); `core/messages.py` (G_SI_LATER :356 removed; G_RETUNE_SHORT_SHUNT, G_RETUNE_OPEN_SERIES, G_RETUNE_ANTENNA_VALUE :414-416 reworded); `po/*`; the `.mo`.
- Test: `tests/test_gui_control.py` (`test_an_si_project_is_refused_until_plan_5` :582-590 replaced; the snapping parametrize :324-336 gains three rows; new tests).

**Interfaces:**
- Consumes: Task 1's `si_view` and `ChainResults.reading`; `INTERFACES`, `SI_F_MAX`, `SI_TOLERANCE`, `SI_DIELECTRIC` (core.project); the tests' `si_project`, `si_dict`, `calibrated`.
- Produces:
  - `open_project` and `retuned`: an SI project's `ChainResults` with si_view's `lines` and `reading`; `retuned`'s refusal with `reading=None`.
  - `default_series(ref: str, project: dict | None = None) -> str`.
  - `verify_stale` reading an SI line's bypasses; `fields` with an SI project's defaults; `UNITS` gains `"f_max_hz"`, `"marker_hz"` (G_UNIT_HZ), `"rise_s"`, `"window_s"` (G_UNIT_S), `"target_ohm"` (G_UNIT_OHM), `"mesh.max_cell_mm"` (G_UNIT_MM).

- [ ] **Step 1: Write the failing tests,** in `tests/test_gui_control.py` (imports gain `from kicad_rf_studio.core.post.si import si_limits` and `from test_cli_si import si_project`). The plan-2 refusal test goes:

```python
def test_an_si_project_opens_with_the_clis_reading_and_lines(tmp_path, calibrated, monkeypatch):  # 5.10; ruling 1
    from test_project import si_dict
    p = tmp_path / "unread" / "project.json"
    p.parent.mkdir()
    save_project(p, si_dict())  # its board is not beside it: the read stops there, Advanced still gets it
    unread = control.open_project(p)
    assert unread.problem[0] == "E_BOARD_UNREADABLE" and unread.stored == si_dict()
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "usb2_hs").resolve()
    assert control.open_project(pj).problem == ("E_NO_RESULTS", {})  # opened, no longer refused
    assert pipeline.run(pj) == 0
    opened, d = control.open_project(pj), load_project(pj)
    reading, lines = pipeline.si_view(d, pipeline.chain_results(pj, d, errors_as_lines=True))
    assert (opened.problem, opened.results.refs, opened.results.lines) == (None, ["R1", "R2"], lines)
    assert np.array_equal(opened.results.reading.m, reading.m) and "G_SI_LATER" not in CATALOG


def test_the_si_retune_session_gives_retunes_reading_and_lines_and_reads_no_waves(tmp_path, calibrated, monkeypatch):
    monkeypatch.setenv("KRS_FAKE", "network")  # design 5.7, 5.10; ruling 3
    pj = si_project(tmp_path / "usb2_hs").resolve()
    assert pipeline.run(pj) == 0
    opened = control.open_project(pj)
    rows = [replace(row, value="24") for row in control.rows(opened.project, pj.parent, opened.results.refs)]
    with monkeypatch.context() as m:  # the stored layout serves the session: no waves read
        m.setattr(pipeline, "layout", lambda *a, **k: 1 / 0)
        res = control.retuned(pj, opened.project, opened.results, rows)
    lines = []
    assert pipeline.retune(pj, ["R1=24", "R2=24"], lambda c, p: lines.append((c, p))) == 0
    assert lines[:len(res.lines)] == res.lines
    assert [c for c, _ in lines[len(res.lines):]] == ["I_WHAT_IF", "I_OUTPUTS", *si_limits(load_project(pj))]
    d = load_project(pj)
    assert np.array_equal(res.reading.m, pipeline.si_view(d, pipeline.chain_results(pj, d))[0].m)
    bad = control.retuned(pj, opened.project, opened.results, [replace(rows[0], value="open"), rows[1]])
    assert (bad.chain, bad.reading, bad.lines) == (None, None, [("E_RETUNE_OPEN_SERIES", {"ref": "R1"})])
    assert control.text(*bad.lines[0]) == render("G_RETUNE_OPEN_SERIES", ref="R1")


def test_an_si_verify_is_stale_when_a_bypass_changes():  # Stage 4 design 5.7; ruling 3; Review Focus 5
    from test_project import si_dict
    d = si_dict()
    d["lines"][0]["chain"]["series"] = [{"ref": "C1", "value": "0R"}]  # an AC-coupling capacitor bypassed
    d = {**d, "results": {"model_hash": "M"}, "verify": {"base_hash": "M", "values": {"C1": "0R"}, "run_dir": "v"}}

    def stale(c1):
        return control.verify_stale(d, [control.Row("C1", c1, "", "series")])

    assert stale("0R") is None and stale("open") == "G_VERIFY_STALE"  # port_value reads both as None


def test_advanced_shows_an_si_projects_fields_with_its_interfaces_defaults_and_units():  # ruling 8
    from test_project import si_dict
    d = si_dict()
    by = {f.name: f for f in control.fields(d)}
    assert not {"kind", "schema"} & set(by)
    names = ("f_max_hz", "rise_s", "marker_hz", "target_ohm", "tolerance", "dielectric", "window_s", "t_max_s",
             "mesh.max_cell_mm", "gates.dt_floor", "region.expand_h", "lid")
    assert {n: (by[n].default, by[n].unit) for n in names} == {
        "f_max_hz": ("10000000000.0", "G_UNIT_HZ"), "rise_s": ("5e-10", "G_UNIT_S"),
        "marker_hz": ("240000000.0", "G_UNIT_HZ"), "target_ohm": ("90.0", "G_UNIT_OHM"), "tolerance": ("0.1", None),
        "dielectric": ('"lossless"', None), "window_s": ("", "G_UNIT_S"), "t_max_s": ("", "G_UNIT_S"),
        "mesh.max_cell_mm": ("null", "G_UNIT_MM"), "gates.dt_floor": ("0.6", None),
        "region.expand_h": ("6.0", "G_UNIT_SUBSTRATE"), "lid": ("true", None)}  # null: the d fill (gate P4-C)
    for interface in ("custom", ["x"]):  # the user's own, and a hand edit that is not text, which Advanced must open
        listed = {f.name: f.default for f in control.fields({**d, "interface": interface})}
        assert [listed[n] for n in ("f_max_hz", "rise_s", "marker_hz", "target_ohm")] == [""] * 4
```

  The snapping parametrize gains `("R1", "25", "E24", "24"), ("R1", "25", "E12", "27"), ("R1", "open", "E24", "open")`, and its body `assert [control.default_series(r, {"schema": 3}) for r in ("R1", "C1", "FB1")] == ["E24"] * 3` after its v1 line (ruling 3: every SI part port).
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py -q`. Expected: FAIL (G_SI_LATER for the SI project, `Opened.results` without `reading`, `default_series()` takes 1 positional argument, the stale bypass read equal, Advanced's SI defaults empty and unitless).
- [ ] **Step 3: `gui/control.py`.**
  - `open_project`: the G_SI_LATER guard and its ponytail (:231-233) go; after the antenna's branch, `elif si(project):` `reading, lines = pipeline.si_view(project, res)` and `res = replace(res, lines=lines, reading=reading)`. Docstring: "…an SI project's lines and reading are pipeline.si_view's, the CLI's (Stage 4 design 5.10)…", G_SI_LATER's mention gone.
  - `retuned`: `elif si(new):` the same si_view on the chain of the stored layout; the refusal's `replace(stored, …)` gains `reading=None`; docstring "an SI project's lines and reading are si_view's on the stored layout, so its session reads no waves file either".
  - `default_series(ref, project=None)`: `"E24"` when `part_kind(ref)` is C or L or `project is not None and si(project)`, else `"off"`; docstring "…, and for every part port of an SI project (Stage 4 design 5.7: E24 by default), an R included".
  - `verify_stale`: `bypass(ref, text) if antenna(project) or si(project) else None`; docstring "an antenna's or an SI line's 0R and open…".
  - `UNITS` gains the six entries of Interfaces.
  - `fields`, SI branch: `defaults.update` with `"tolerance": SI_TOLERANCE`, `"dielectric": SI_DIELECTRIC`, `"mesh.max_cell_mm": None` beside lid, region.expand_h and gates.dt_floor; then, when `preset := INTERFACES.get(str(data.get("interface")))` (read through str(), as the preset is, so a hand-edited interface that is not text cannot raise), its `rise_s`, `marker_hz` and `target_ohm` and `"f_max_hz": SI_F_MAX`. Docstring: the SI defaults are the interface preset's, none for custom or an interface that does not read, and `mesh.max_cell_mm` shows null, the d fill.
  - Imports gain `INTERFACES`, `SI_DIELECTRIC`, `SI_F_MAX` and `SI_TOLERANCE` (core.project).
- [ ] **Step 4: The messages,** through the catalog tool; G_SI_LATER's entry and msgstr go:

| Code | English | pt-BR |
|---|---|---|
| G_RETUNE_SHORT_SHUNT (changed) | {ref} joins the chain to {net}: 0 Ω there would short the chain to {net}. In the Value column, 0R replaces a series part with a short, and open removes a part like this one. | {ref} liga a cadeia a {net}: 0 Ω ali poria a cadeia em curto com {net}. Na coluna Valor, 0R troca um componente em série por um curto, e open retira um componente como este. |
| G_RETUNE_OPEN_SERIES (changed) | {ref} is a series part of the chain: open there would cut it, an antenna off its feed or a line in two. In the Value column, 0R replaces it with a short; open removes a shunt part. | {ref} é um componente em série da cadeia: em aberto ali, ele a cortaria, separando uma antena da alimentação ou partindo uma linha em duas. Na coluna Valor, 0R o troca por um curto; open retira um componente shunt. |
| G_RETUNE_ANTENNA_VALUE (changed) | Cannot read "{value}" as the value of {ref}: on an antenna's chain or a signal-integrity line, a C, L or R takes a value in its own unit (4.7pF, 4p7, 15nH, 50R), 0R replaces a series part with a short and open removes a shunt part (a C of 0 F could mean either, so it is refused), and any part takes an S2P file in its row. | Não foi possível ler "{value}" como o valor de {ref}: na cadeia de uma antena ou numa linha de integridade de sinal, um C, L ou R recebe um valor na própria unidade (4.7pF, 4p7, 15nH, 50R), 0R troca um componente em série por um curto e open retira um componente shunt (um C de 0 F poderia ser qualquer um dos dois, então é recusado), e qualquer componente recebe um arquivo S2P na linha dele na tabela. |

- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(gui): control opens, retunes and verifies an SI project through si_view, E24 for every SI part port, an SI line's bypasses in the stale indicator and Advanced's SI defaults and units (Stage 4 design 5.7, 5.10)"
graphify update .
```

---

### Task 5 [code]: The window's Results for SI, its retune off the GUI thread and Run…'s confirmation

**Files:**
- Modify: `gui/window.py` (module docstring :1-11; imports :29-36; new `TABLE_2D` and `TUNE_MS` beside COLUMNS; `ResultsView` docstring :92-104, `show_rows` :179, `show_chain` :229-273, `blit`'s ponytail :278-281; `MainWindow` docstring :494-511, `__init__` :513-568, `open_project` :576-596, `run` :766-774, `show_project` :789-822, `retune` :824-833, `revert` :835-840, new `take_retune`, `closeEvent` :1151-1162); `core/messages.py` (new G_PROJECT_SI); `po/*`; the `.mo`.
- Test: `tests/test_gui.py` (imports; `dispose` :123-131; new tests).

**Interfaces:**
- Consumes: Task 1's `draw_si(gui)`, `retrace_si`, `ChainResults.reading`; Task 4's `retuned`, `default_series(ref, project)`, `fields`; the tests' `verified_si` (test_si_run).
- Produces:
  - `window.TABLE_2D = ("I_SI_2D_HEADER", "I_SI_2D_PAIR", "I_SI_2D_LEG", "I_SI_2D_LINE", "W_2D_SHORT", "I_SI_SHORT_ROUTE")`; `window.TUNE_MS = 20`.
  - `MainWindow.tuner` (`ThreadPoolExecutor(1)`), `retuning` (`Future | None`, the latest SI retune), `tune_timer` (`QTimer`, every TUNE_MS while one goes on) and `take_retune() -> None`.
  - G_PROJECT_SI {path, interface, target, start, end, preset}.

- [ ] **Step 1: Write the failing tests,** in `tests/test_gui.py` (imports gain `from concurrent.futures import Future`, `from kicad_rf_studio.core.post.si import db, si_limits`, `TABLE_2D` from `gui.window`, `from test_cli_si import si_project`, `from test_si_run import verified_si`, `result_lines` beside `pi_run`); `dispose` gains `w.tuner.shutdown(wait=True)` after the pool's. `verified_si(tmp_path, monkeypatch)` runs usb2_hs on the network fake before any window (the fixture fails run_jobs from then on). On that fake, Sdd21, Scd21, NEXT and FEXT are exact zeros that no retune moves (probed), so a retune is checked on Scc21, `axes[1].lines[2]`, which R1 and R2 move by 0.1 to 1.6 dB:

```python
def test_an_si_project_shows_its_tdr_mixed_mode_s_and_crosstalk_with_the_clis_lines(window, qapp, tmp_path,
                                                                                     monkeypatch):  # 5.10; ruling 1
    pj = verified_si(tmp_path, monkeypatch).resolve()
    w = window()
    w.open_project(pj)
    opened(w)
    d, r, fig = load_project(pj), w.results, w.results.canvas.figure
    assert w.project_status.text() == render("G_PROJECT_SI", path=str(pj), interface="usb2-hs", target="90",
                                             start="J1.3", end="U1.3", preset="normal")
    assert column(r.parts, PART) == ["R1", "R2"] and column(r.parts, VALUE) == ["22", "22"]
    assert [r.parts.cellWidget(k, SNAP).currentData() for k in range(2)] == ["E24", "E24"]  # ruling 3
    lines = w.opened.results.lines
    assert lines == result_lines(d["results"]["run_dir"])[1:len(lines) + 1]  # what run printed, by construction
    assert items(r.lines) == [control.text(c, p) for c, p in lines] + [render(c) for c in si_limits(d)]
    assert len(fig.axes) == 3 and fig.get_suptitle() == "\n".join(
        [render("I_PLOT_SI_TITLE", name="usb2_hs"), render("I_SI_RELATIVE"), render("G_WHAT_IF")])
    assert not [t for t in fig.texts if render("I_LIMIT_SI_CROP") in t.get_text()] and r.axes[1].get_ylim()[0] >= -100
    assert not any(ax.yaxis_inverted() for ax in r.axes)  # the fake's crosstalk, exact zeros, keeps its autoscale
    w.tabs.setCurrentWidget(r)
    qapp.processEvents()
    assert min(ax.get_window_extent().height for ax in fig.axes) >= 100  # three panels in one row at 1200 x 800
    grab(w, "si-results")
    a = w.advanced
    rows = {a.table.item(k, 0).text(): k for k in range(a.table.rowCount())}
    assert not {"kind", "schema"} & set(rows) and a.table.item(rows["mesh.max_cell_mm"], 2).text() == "null"
    assert [a.table.item(rows["target_ohm"], c).text() for c in (2, 3)] == ["90.0", render("G_UNIT_OHM")]
    w.tabs.setCurrentWidget(a)
    qapp.processEvents()
    grab(w, "si-advanced")
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules


def test_an_si_retune_runs_off_the_gui_thread_and_blits_within_the_budget(window, qapp, tmp_path, monkeypatch):
    pj = verified_si(tmp_path, monkeypatch).resolve()  # Stage 2 design 2 goal 4; Review Focus 1
    w = window()
    w.open_project(pj)
    opened(w)
    r, fig = w.results, w.results.canvas.figure
    w.tabs.setCurrentWidget(r)
    qapp.processEvents()  # the first paint draws the canvas and keeps its background for the blits
    axes, draws, real = list(r.axes), [], r.canvas.draw
    monkeypatch.setattr(r.canvas, "draw", lambda: draws.append(1) or real())
    monkeypatch.setattr(pipeline, "layout", fail)  # the stored layout serves every retune: no waves read
    edits, takes = [], []
    for typed in ("25", "33", "25"):  # each snapped on commit to E24, SI's default
        start = time.perf_counter()
        r.parts.item(0, VALUE).setText(typed)
        edits.append(time.perf_counter() - start)
        assert isinstance(w.retuning, Future)  # submitted, not computed here
        w.retuning.result(timeout=60)
        start = time.perf_counter()
        w.take_retune()
        takes.append(time.perf_counter() - start)
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows())
    assert column(r.parts, VALUE) == ["24", "22"] and min(edits) < 0.05 and min(takes) < 0.05
    assert w.retuning is None and draws == [] and list(r.axes) == axes  # moved in place and blitted, never redrawn
    assert np.array_equal(r.axes[1].lines[2].get_ydata(), db(res.reading.m[:, 3, 2]))  # Scc21
    assert items(r.lines) == [control.text(c, p) for c, p in res.lines] + [render(c) for c in si_limits(load_project(pj))]
    assert fig.get_suptitle().endswith("\n" + render("G_WHAT_IF")) and r.stale.text() == render("G_VERIFY_NONE")
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules


def test_only_the_latest_si_retune_is_drawn_and_a_revert_or_a_read_drops_it(window, qapp, tmp_path, monkeypatch):
    pj = verified_si(tmp_path, monkeypatch).resolve()  # Review Focus 1, 2
    w = window()
    w.open_project(pj)
    opened(w)
    r = w.results
    r.parts.item(0, VALUE).setText("33")
    first = w.retuning
    r.parts.item(1, VALUE).setText("33")
    assert w.retuning is not first  # the newer edit's; the first is never shown
    w.retuning.result(timeout=60)
    w.take_retune()
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows())
    assert np.array_equal(r.axes[1].lines[2].get_ydata(), db(res.reading.m[:, 3, 2]))  # both at 33 Ω
    r.parts.item(0, VALUE).setText("47")
    pending = w.retuning
    r.revert_button.click()
    assert w.retuning is None and column(r.parts, VALUE) == ["22", "22"]
    pending.result(timeout=60)
    w.take_retune()  # nothing to take: the stored values' curves stay
    assert np.array_equal(r.axes[1].lines[2].get_ydata(), db(w.opened.results.reading.m[:, 3, 2]))
    r.parts.item(0, VALUE).setText("47")
    pending = w.retuning
    save_project(pj, load_project(pj))  # a read: the unapplied row is carried over it and retuned again
    w.tick()
    opened(w)
    assert w.retuning is not pending and column(r.parts, VALUE) == ["47", "22"]
    w.retuning.result(timeout=60)
    w.take_retune()
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows())
    assert np.array_equal(r.axes[1].lines[2].get_ydata(), db(res.reading.m[:, 3, 2]))
    r.parts.item(1, VALUE).setText("33")  # the event loop alone takes this one: tune_timer polls take_retune
    until(lambda: qapp.processEvents() or w.retuning is None)
    res = control.retuned(pj, w.opened.project, w.opened.results, r.rows())
    assert np.array_equal(r.axes[1].lines[2].get_ydata(), db(res.reading.m[:, 3, 2])) and not w.tune_timer.isActive()


def test_an_si_cost_lists_its_2d_table_first_and_run_asks_on_the_estimate_alone(window, tmp_path, monkeypatch):
    pj = si_project(tmp_path / "usb2_hs").resolve()  # design 5.9, 5.10; ruling 4
    w = window()
    w.open_project(pj)
    opened(w)
    w.cost_button.click()
    until(lambda: w.tick() or w.cost_status.text() == render("G_END_DONE", exit_code=0))
    codes = [e["code"] for e in events(w.run_dir, kind="cost")]
    table = [k for k, code in enumerate(codes) if code in TABLE_2D]
    assert table and max(table) < codes.index("I_COST_TIME") and "I_SI_COST_RING" in codes
    opened(w)
    asked = []
    monkeypatch.setattr(w, "ask", lambda text: asked.append(text) or False)
    w.run_button.click()
    shown = [(e["code"], control.text(e["code"], e["params"])) for e in events(w.cost, kind="cost")]
    assert [text for code, text in shown if code == "I_COST_TIME"][0] in asked[0]
    assert not [text for code, text in shown if code in TABLE_2D and text in asked[0]]  # the table stays in Cost
    grab(w, "si-cost")
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui.py -q -k "si_"`. Expected: FAIL (`cannot import name 'TABLE_2D'`; then E_INTERNAL's `KeyError: 'f0_hz'` from show_project).
- [ ] **Step 3: `ResultsView`.**
  - `show_rows`: `control.default_series(row.ref, self.shown.project)`.
  - `show_chain(res, name)`: `is_si = res is not None and si(self.shown.project)`; the lines end with `si_limits(self.shown.project)` for SI (ANTENNA_LIMITS and LIMITS as now); an SI plot needs `res.reading` (`plot = res is not None and (res.reading is not None if is_si else <today's test>)`). The retrace branch and its fall-through are what the tests leave open:

```python
        if plot and self.axes is not None:
            if is_si:
                moved = retrace_si(self.axes, res.reading)
            elif ant:
                moved = retrace_antenna(self.axes, res.lay.f, res.chain[:, 0, 0], self.shown.project)
            else:
                moved = retrace_summary(self.axes, res.lay, res.chain, res.ideal)
            if moved is not None:  # an SI reading with another count of levels is drawn in full below
                self.blit()
                return
```

    and the full draw gains, before v1's `elif plot:`, `elif plot and is_si:` `self.axes = draw_si(fig, [(name, res.reading)], self.shown.project, render("I_PLOT_SI_TITLE", name=name), label, gui=True)` and `self.curves = retrace_si(self.axes, res.reading)` (the data unchanged). The docstring gains "An SI chain (Stage 4 design 5.10) draws draw_si's figure for the window (gui: no foot, the limits in the lines) with its reading, moved by retrace_si."
  - `blit`'s ponytail names SI's full draw too: "…a quarter of a second for an antenna's six panels or an SI figure's three…".
- [ ] **Step 4: `MainWindow`.**
  - `__init__`: `self.tuner, self.retuning = ThreadPoolExecutor(1), None`; `self.tune_timer = QTimer(self)`, `setInterval(TUNE_MS)`, `timeout` → `take_retune`. `TUNE_MS = 20` with `# an SI retune's poll: about 70 ms of scikit-rf on the tuner's thread, then its blit (Stage 2 design 2 goal 4)`.
  - `retune()`: the args `(self.path, self.opened.project, self.opened.results, self.results.rows(), self.opened.far, self.opened.far_lay)`; for an SI project, `self.retuning.cancel()` when one is set (an older edit's, never shown, dropped if not begun), then `self.retuning = self.tuner.submit(control.retuned, *args)` and `self.tune_timer.start()`; else `show_chain(control.retuned(*args), …)` as now; `show_stale()` either way. Comment `# ponytail: an SI retune queued behind an older one waits for it (about 70 ms each); a coalescing queue if fast typing lags`.
  - `take_retune()`: with no `retuning`, or once it is done, the timer stops; once done, `done, self.retuning = self.retuning, None` and `self.results.show_chain(done.result(), self.path.parent.name)`. Docstring: "The tuner's end, polled every TUNE_MS while an SI retune goes on (tune_timer): once the latest (`retuning`) ended, its chain shown (show_chain: moved in place and blitted). An earlier one is never shown, as `retuning` names the latest, and open_project, show_project and revert drop the one in flight."
  - `open_project`'s reset line, `show_project`'s first line and `revert`'s first line set `self.retuning = None`.
  - `run()`: the confirmation's lines leave out `TABLE_2D`'s codes for an SI project (`si(self.opened.project)`), v1's readout lines as now.
  - `show_project`: an SI project's line is `render("G_PROJECT_SI", path=str(self.path), interface=p["interface"], target=f"{p['target_ohm']:g}", start=line["start"], end=line["end"], preset=p["preset"])`, `line = p["lines"][0]["chain"]`.
  - `closeEvent`: `self.tune_timer.stop()` beside the timer's and `self.tuner.shutdown(wait=False, cancel_futures=True)` beside the pool's.
  - Docstrings: the module's, the class's state list (`tuner`, `retuning`, `tune_timer`), `retune`'s and `show_project`'s. Imports: `si` (core.project), `draw_si`, `retrace_si`, `si_limits` (core.post.si).
- [ ] **Step 5: The message,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| G_PROJECT_SI | {path}: signal integrity, interface {interface}, target {target} Ω, {start} → {end}, preset {preset}. | {path}: integridade de sinal, interface {interface}, alvo de {target} Ω, {start} → {end}, predefinição {preset}. |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_gui_control.py -q`. Expected: PASS, v1's and the antenna's window tests unchanged.
- [ ] **Step 7: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(gui): Results for an SI project: the TDR with its target band, the mixed-mode S and the crosstalk under the CLI's own lines, its retune run off the GUI thread and blitted, and Run's confirmation without the 2D table (Stage 4 design 5.10)"
graphify update .
```

---

### Task 6 [code]: New makes an SI project

**Files:**
- Modify: `gui/window.py` (`NewForm` :299-394; `create_project` :991-1028; `show_pads` :1030-1064; `show_project`'s SI line, Task 5's); `gui/control.py` (`GUI` :40-50; `text` :287-294); `core/messages.py`; `po/*`; the `.mo`.
- Test: `tests/test_gui.py` (new test; `test_the_window_fits_1200_by_800_and_its_tabs_need_no_scrolling` :219-224), `tests/test_gui_control.py`, `tests/test_sexpr.py` (`QUOTED`).

**Interfaces:**
- Consumes: `cli.new_si(board, start, end, interface, *, pair, pair_with, victims, f_max, target, preset, stackup, lid_height, output)`; `parse_frequency`; `INTERFACES`, `SI_F_MAX`; `combo()`, `beside()`.
- Produces:
  - `NewForm.kind` gains `("si", "G_KIND_SI")`; `interface` (QComboBox: each of INTERFACES by its name as data and text, then G_INTERFACE_CUSTOM with `"custom"`), `f_max` (QLineEdit), `target` (QDoubleSpinBox, 1 to 1000 Ω, 1 decimal, C locale), `pair` (combo of `(None, "G_PAIR_NONE")`, `("rule", "G_PAIR_RULE")`, `("given", "G_PAIR_PICK")`, `"rule"` current), `pair_with` (two editable QComboBox), `pair_row` (layout), `victims` (two tuples of two editable QComboBox), `victim_rows` (two layouts), `interface_changed()`, `pair_changed()`.
  - `control.GUI` gains `"E_SI_NEEDS_PAIR": "G_SI_NEEDS_PAIR"`, `"E_SI_NOT_PAIR": "G_SI_NOT_PAIR"`, `"E_SI_PARTNER": "G_SI_PARTNER"`, `"E_SI_LINE_SHARED": "G_SI_LINE_SHARED"`, `"W_SI_LONG_PORT": "G_SI_LONG_PORT"`; `control.text` gives I_SI_PAIR's `how` T_PAIR_WITH as `render("G_PAIR_PICKED")`.
  - G_PROJECT_SI's `interface` for custom: `render("G_INTERFACE_CUSTOM")`, as New's combo names it.

- [ ] **Step 1: Write the failing tests.** `tests/test_gui_control.py`:

```python
def test_the_window_words_a_picked_partner_without_the_clis_option():  # ruling 6
    picked = control.text("I_SI_PAIR", {"p": "USB_D+", "n": "USB_D-", "how": "T_PAIR_WITH"})
    assert picked == render("I_SI_PAIR", p="USB_D+", n="USB_D-", how=render("G_PAIR_PICKED")) and "--" not in picked
    assert control.text("I_SI_PAIR", {"p": "A", "n": "B", "how": "T_PAIR_RULE"}) == render(
        "I_SI_PAIR", p="A", n="B", how="T_PAIR_RULE")
```

  `tests/test_gui.py`; the 1200 × 800 test becomes:

```python
def test_the_window_fits_1200_by_800_and_its_tabs_need_no_scrolling(window):  # pt-BR design 3; ruling 6
    w = window()
    for kind in ("chain", "antenna", "si"):  # only the active kind's rows show
        w.new_form.kind.setCurrentIndex(w.new_form.kind.findData(kind))
        hint = w.minimumSizeHint()  # English probed at 5302aae: 830 x 518 for the chain
        assert hint.width() <= 1200 and hint.height() <= 800, kind
    # a tab never elides or narrows (scroll buttons appear instead), so every label is whole when the bar fits
    assert w.tabs.tabBar().sizeHint().width() <= w.tabs.width()
```

  and, new:

```python
def test_new_makes_an_si_project_from_its_interface_its_pair_and_its_victims(window, tmp_path, monkeypatch):
    board = tmp_path / "usb2_hs.kicad_pcb"  # design 5.10; ruling 6
    board.write_bytes((FIX / "usb2_hs.kicad_pcb").read_bytes())
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(board), ""))
    w = window()
    f = w.new_form
    f.board_button.click()
    w.pads_read.result(timeout=60)
    w.tick()
    f.kind.setCurrentIndex(f.kind.findData("si"))
    assert all(f.form.isRowVisible(x) for x in (f.end_row, f.interface, f.f_max, f.target, f.pair_row, *f.victim_rows))
    assert not any(f.form.isRowVisible(x) for x in (f.f0, f.harmonics, f.antenna, f.band_row))
    assert [f.interface.itemText(k) for k in range(4)] == ["usb2-hs", "100base-tx", "se50", render("G_INTERFACE_CUSTOM")]
    assert (f.interface.currentData(), f.pair.currentData(), f.f_max.text(), f.target.value()) == (
        "usb2-hs", "rule", "10GHz", 90.0)  # the preset's band and target, shown disabled
    assert not (f.f_max.isEnabled() or f.target.isEnabled() or f.pair_with[0].isEnabled())
    assert f.victims[1][0].count() == len(control.pads(board))  # every picker lists the board's pads
    f.start.setCurrentText("J1.3")
    f.end.setCurrentText("U1.3")
    f.victims[0][0].setCurrentText("TP1.1")
    f.victims[0][1].setCurrentText("TP2.1")
    f.create_button.click()
    path, notes = w.creating.result(timeout=120)
    w.tick()
    same = cli.new_si(board, "J1.3", "U1.3", "usb2-hs", pair=True, victims=[("TP1.1", "TP2.1")],
                      output=tmp_path / "cli")[0]
    assert path == tmp_path / "usb2_hs" / "project.json" and load_project(path) == load_project(same)
    assert items(f.notes) == [control.text(c, p) for c, p in notes]  # new --interface's own call, nothing duplicated
    opened(w)
    grab(w, "new-si")

    def create(folder):  # Create into `folder`, then the status line once new ended or refused
        f.folder.setText(str(tmp_path / folder))
        f.create_button.click()
        if w.creating is not None:
            w.creating.exception(timeout=120)
            w.tick()
        return f.status.text()

    f.pair.setCurrentIndex(f.pair.findData("given"))
    f.pair_with[0].setCurrentText("J1.2")
    f.pair_with[1].setCurrentText("U1.2")
    assert create("picked") == "" and "--pair-with" not in " ".join(items(f.notes))
    f.victims[1][0].setCurrentText("TP1.1")
    f.victims[1][1].setCurrentText("TP2.1")  # the second row reaches new: AUX on two lines
    assert create("two") == render("G_SI_LINE_SHARED", start="TP1.1", end="TP2.1", net="AUX")
    f.victims[1][1].setCurrentText("")
    assert create("half") == render("G_SI_ENDS_HALF") and w.creating is None  # nothing starts
    f.victims[1][0].setCurrentText("")
    f.victims[0][0].setCurrentText("J1.3")
    f.victims[0][1].setCurrentText("U1.3")  # a victim on the measured line's nets
    assert create("shared") == render("G_SI_LINE_SHARED", start="J1.3", end="U1.3", net="USB_D+")
    for box in f.victims[0]:
        box.setCurrentText("")
    f.pair.setCurrentIndex(f.pair.findData(None))
    assert create("nopair") == render("G_SI_NEEDS_PAIR", interface="usb2-hs")
    f.interface.setCurrentIndex(f.interface.findData("se50"))
    assert (f.pair.currentData(), f.target.value()) == (None, 50.0)  # the preset sets the pair and the target
    f.pair.setCurrentIndex(f.pair.findData("rule"))
    assert create("se50pair") == render("G_SI_NOT_PAIR", interface="se50")
    f.interface.setCurrentIndex(f.interface.findData("custom"))
    assert f.f_max.isEnabled() and f.target.isEnabled()
    f.f_max.setText("abc")
    assert create("custom") == render("E_BAD_FREQUENCY", text="abc")
    f.f_max.setText("10GHz")  # a pair at 50 Ω, Custom: the project line names it as the combo does
    assert create("custom") == ""
    opened(w)
    assert w.project_status.text() == render("G_PROJECT_SI", path=str((tmp_path / "custom" / "project.json").resolve()),
                                             interface=render("G_INTERFACE_CUSTOM"), target="50", start="J1.3",
                                             end="U1.3", preset="normal")
    assert board.read_bytes() == (FIX / "usb2_hs.kicad_pcb").read_bytes()
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

  `tests/test_sexpr.py`'s `QUOTED` gains `"G_SI_NEEDS_PAIR": ("G_NEW_PAIR", "G_NEW_INTERFACE", "G_INTERFACE_CUSTOM")`, `"G_SI_NOT_PAIR": ("G_NEW_PAIR", "G_INTERFACE_CUSTOM")`, `"G_SI_PARTNER": ("G_NEW_PAIR",)`, `"G_SI_LONG_PORT": ("G_INTERFACE_CUSTOM",)` and `"G_SI_ENDS_HALF": ("G_NEW_PAIR",)`.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py tests/test_sexpr.py -q -k "picked or fits_1200 or makes_an_si or quoted"`. Expected: FAIL (`findData("si")` is −1, no `interface`, the missing codes).
- [ ] **Step 3: `NewForm`.** The rows, in order: G_NEW_BOARD, G_NEW_KIND, G_NEW_START, G_NEW_END (`end_row`), G_NEW_ANTENNA, G_NEW_F0, G_NEW_HARMONICS, G_NEW_BAND (`band_row`), G_NEW_INTERFACE (`interface`), G_NEW_F_MAX (`f_max`), G_NEW_TARGET (`target`), G_NEW_PAIR (`pair_row`: `pair`, then `pair_with`), G_NEW_VICTIM with n 1 and 2 (`victim_rows`, each `beside` its two pickers), G_NEW_PRESET, G_NEW_STACKUP, G_NEW_LID, G_NEW_FOLDER.
  - `kind_changed()`: the antenna's and band's rows for an antenna; `end_row` for a chain or SI; `f0` and `harmonics` for a chain; interface, f_max, target, pair_row and both victim rows for SI; the rows to hide first, as now.
  - `interface_changed()` (on `interface.currentIndexChanged`, and once at the end of `__init__`): f_max and target enabled only for custom; for a preset, `f_max` shows `f"{SI_F_MAX / 1e9:g}GHz"`, `target` its `target_ohm`, and `pair` its mode, `"rule"` when `INTERFACES[name]["pair"]` else None (`findData`); custom keeps what they hold.
  - `pair_changed()` (on `pair`'s slot, and once): both `pair_with` pickers enabled only for `"given"`.
  - Docstring: the SI kind's rows, Custom, the pair's three modes and the victims. Imports gain `INTERFACES` and `SI_F_MAX` (core.project). Comment `# ponytail: a partner by the rule is shown in new's notes (I_SI_PAIR), not before Create; a live preview if users ask for it`.
- [ ] **Step 4: The window.**
  - `create_project`, the SI kind: in the try, `f_max = parse_frequency(f.f_max.text())` for custom, else None; after it, before the folder check, `victims` (each row's two texts, stripped) and `pair_with` (the two pickers' texts for `"given"`, else None): any victim row with one end only, or a `"given"` pair with an empty end, puts G_SI_ENDS_HALF in the status line and starts nothing; then `self.pool.submit(cli.new_si, board, start, end, interface, pair=mode == "rule", pair_with=pair_with, victims=[v for v in victims if all(v)], f_max=f_max, target=f.target.value() if custom else None, **options)` with the chain's options. Docstring names the SI kind and its refusals.
  - `show_pads`: every picker, start, end, both `pair_with` and the four victim pickers, gets `names`, start and end picked as now and the others none.
  - `show_project`: G_PROJECT_SI's `interface` is `render("G_INTERFACE_CUSTOM")` for `"custom"`, else the preset's name, as the combo lists them.
- [ ] **Step 5: `control`.** `GUI` gains the five entries of Interfaces; `text`, after W_S2P_FIXTURE's branch: `elif code == "I_SI_PAIR" and params["how"] == "T_PAIR_WITH": params = {**params, "how": render("G_PAIR_PICKED")}` with `# new_si's note names --pair-with`; the docstring says so.
- [ ] **Step 6: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| G_KIND_SI | Signal integrity | Integridade de sinal |
| G_NEW_INTERFACE | Interface | Interface |
| G_INTERFACE_CUSTOM | Custom | Personalizada |
| G_NEW_F_MAX | f_max (for example 10GHz) | f_max (por exemplo 10GHz) |
| G_NEW_TARGET | Target (Ω) | Alvo (Ω) |
| G_NEW_PAIR | Pair | Par |
| G_PAIR_NONE | None (a single-ended net) | Nenhum (uma rede single-ended) |
| G_PAIR_RULE | By KiCad's pair rule | Pela regra de pares do KiCad |
| G_PAIR_PICK | Picked: the partner's two end pads | Escolhido: as duas pontas do par |
| G_PAIR_PICKED | its two end pads, picked here | suas duas pontas, escolhidas aqui |
| G_NEW_VICTIM | Victim {n} (start and end pads) | Vítima {n} (ilhas inicial e final) |
| G_SI_ENDS_HALF | A victim needs both its end pads, and so does a partner picked in the Pair row: pick both, or leave a victim's two empty. | Uma vítima precisa das duas ilhas das pontas, e um par escolhido no campo Par também: escolha as duas, ou deixe vazias as duas de uma vítima. |
| G_SI_NEEDS_PAIR | Interface {interface} is a differential pair's: in the Pair row, take the partner by KiCad's pair rule or pick its two end pads, or, for a single-ended net, choose se50 or Custom in the Interface row. | A interface {interface} é de um par diferencial: no campo Par, tome o par pela regra de pares do KiCad ou escolha as duas pontas dele, ou, para uma rede single-ended, escolha se50 ou Personalizada no campo Interface. |
| G_SI_NOT_PAIR | Interface {interface} is a single-ended net's: in the Pair row, choose None, or choose the interface Custom for a pair. | A interface {interface} é de uma rede single-ended: no campo Par, escolha Nenhum, ou escolha a interface Personalizada para um par. |
| G_SI_PARTNER | The partner of net {net} (pad {pad}) on {ref} is {partner} by KiCad's pair rule or the DP/DM alias, with pads {pads} on {ref}, where one is needed. In the Pair row, pick the partner's two end pads. | O par da rede {net} (ilha {pad}) em {ref} é {partner} pela regra de pares do KiCad ou pelo apelido DP/DM, com ilhas {pads} em {ref}, onde uma é necessária. No campo Par, escolha as duas pontas do par. |
| G_SI_LINE_SHARED | The line from {start} to {end} runs on net {net}, which an earlier line of this project holds: each line needs nets of its own. Pick the partner's two end pads, or a victim's, on another net. | A linha de {start} a {end} passa pela rede {net}, que uma linha anterior deste projeto já tem: cada linha precisa de redes próprias. Escolha as duas pontas do par, ou as de uma vítima, em outra rede. |
| G_SI_LONG_PORT | Port {name} spans {length_mm} mm from its pad to its reference, more than λ/20 at f_max ({limit_mm} mm): its launch reads as an inductive bump, which the TDR marks as the port's own. A lower f_max, with the interface Custom, shortens it in wavelengths. | A porta {name} se estende por {length_mm} mm da ilha até a referência, mais que λ/20 em f_max ({limit_mm} mm): a entrada dela aparece como um degrau indutivo, que o TDR marca como da própria porta. Um f_max menor, com a interface Personalizada, a encurta em comprimentos de onda. |

- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_gui_control.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 8: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(gui): New makes an SI project: its kind, the interface presets or Custom, the pair by KiCad's rule or picked, up to two victims, through cli.new_si, with new's refusals in the window's words (Stage 4 design 5.10)"
graphify update .
```

---

### Task 7 [code]: Compare for SI

**Files:**
- Modify: `gui/control.py` (`QUANTITIES`, `DIGITS` :558-563; new `MARKS`, `INSERTION` and `cells`; `compare` :566-590); `gui/window.py` (module and `CompareView` docstrings); `core/messages.py`; `po/*`; the `.mo`.
- Test: `tests/test_gui_control.py`, `tests/test_gui.py` (a module-level `stamps`, a new test), `tests/test_sexpr.py` (`QUOTED["G_COMPARE_KIND"]` gains `"G_KIND_SI"`).

**Interfaces:**
- Consumes: Task 3's current-value compare; Task 6's G_KIND_SI; the tests' `verified_si`, `twin`, `antenna_project`.
- Produces: `QUANTITIES` gains `"tdr_lowest": "G_QUANTITY_TDR_LOWEST"`, `"tdr_highest": "G_QUANTITY_TDR_HIGHEST"`, `"skew": "G_QUANTITY_SKEW"`; `MARKS = {"short": "G_MARK_SHORT", "marker": "G_MARK_MARKER"}`; `DIGITS` gains `"Ω": 2, "ps": 2`; `INSERTION = ("sdd21", "s21")`; `cells(rows: list[dict[str, str]]) -> list[list[str]]`; `tests/test_gui.py`'s `stamps(*roots) -> dict`.

- [ ] **Step 1: Write the failing tests.** `tests/test_gui_control.py`:

```python
def test_the_compare_tables_cells_word_each_si_quantity_and_mark_and_round_as_the_lines():  # ruling 5
    def row(quantity, marker, f_hz, base, variant, unit, delta, threshold, resolved):
        return dict(zip(DELTA_COLUMNS, (quantity, marker, f_hz, base, variant, unit, delta, unit, threshold, resolved)))

    rows = [row("tdr_highest", "short", "", "95.01", "97.22", "Ω", "2.21", "2.2", "True"),
            row("sdd21", "marker", "240000000.0", "-1.9123", "-1.9", "dB", "0.0123", "0.05", "False"),
            row("scd21_worst", "", "", "-45.56", "-27.89", "dB", "17.67", "0.5", "True"),
            row("skew", "", "", "1.5", "-0.5", "ps", "-2.0", "1.0", "True"),
            row("next", "AUX", "", "-25.72", "-19.37", "dB", "6.35", "0.5", "True")]
    assert control.cells(rows) == [
        [render("G_QUANTITY_TDR_HIGHEST"), render("G_MARK_SHORT"), "", "95.01", "97.22", "Ω", "+2.21", "Ω", "2.20",
         render("T_RESOLVED")],
        ["Sdd21", render("G_MARK_MARKER"), "240.0", "-1.912", "-1.900", "dB", "+0.012", "dB", "0.050",
         render("T_NOT_RESOLVED")],  # an insertion to 3 decimals, as si_delta_lines prints it
        ["Scd21", "", "", "-45.56", "-27.89", "dB", "+17.67", "dB", "0.50", render("T_RESOLVED")],
        [render("G_QUANTITY_SKEW"), "", "", "+1.50", "-0.50", "ps", "-2.00", "ps", "1.00", render("T_RESOLVED")],
        ["NEXT", "AUX", "", "-25.72", "-19.37", "dB", "+6.35", "dB", "0.50", render("T_RESOLVED")]]  # skew signed


def test_compare_gives_two_si_projects_table_in_the_windows_words(tmp_path, calibrated, monkeypatch):  # ruling 5
    a = verified_si(tmp_path, monkeypatch).resolve()
    assert pipeline.verify(a) == 0
    b = twin(a, tmp_path / "b")
    code, lines, cells = control.compare(a, b)
    assert code == 0 and lines[0] == ("I_SI_RELATIVE", {})
    assert [row[0] for row in cells] == [render("G_QUANTITY_TDR_LOWEST"), render("G_QUANTITY_TDR_HIGHEST"), "Sdd21",
                                         "Sdd21", "Sdd11", "Scd21", render("G_QUANTITY_SKEW"), "NEXT", "FEXT"]
    assert [row[1] for row in cells] == ["", "", render("G_MARK_MARKER"), "f_max", "", "", "", "AUX", "AUX"]
    insertion = next(p for c, p in lines if c == "I_SI_COMPARE_INSERTION")
    assert (cells[2][2], cells[2][3], cells[2][6]) == ("240.0", insertion["base"], insertion["delta"])
    assert sorted(p.name for p in (a.parent / control.COMPARE_FOLDER).iterdir()) == ["compare.csv", "compare.png"]
```

  (imports gain `from kicad_rf_studio.core.post.antenna import DELTA_COLUMNS` beside ANTENNA_LIMITS, `from test_compare import twin` and `from test_si_run import verified_si`.) `tests/test_gui.py` gains, beside `items`, the helper Task 12 calls too, then the test:

```python
def stamps(*roots):
    """Each of `roots` and everything under it, by its st_mtime_ns: a folder read in place keeps them all."""
    return {p: p.stat().st_mtime_ns for root in roots for p in [root, *root.rglob("*")]}


def test_compare_two_si_projects_in_the_window_into_the_bases_folder(window, qapp, tmp_path, monkeypatch):
    a = verified_si(tmp_path, monkeypatch).resolve()  # design 5.8, 5.10; ruling 5; Review Focus 4
    assert pipeline.verify(a) == 0
    b, cell, target = (twin(a, tmp_path / name) for name in ("b", "cell", "target"))
    d = load_project(cell)
    d["verify"]["fingerprint"]["mesh"]["d_fill"] = False  # verified with a set cell, not the d fill
    save_project(cell, d)
    save_project(target, {**load_project(target), "target_ohm": 85.0})  # read at 85 Ω, as Results would show it
    ant = antenna_project(tmp_path / "ant").resolve()
    watched = (b.parent, Path(load_project(a)["results"]["run_dir"]), Path(load_project(a)["verify"]["run_dir"]))
    before = stamps(*watched)
    w = window()
    w.open_project(a)
    opened(w)
    c = w.comparison
    assert c.status.text() == render("G_COMPARE_NONE")

    def choose(project):
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *x, **k: (str(project), ""))
        c.variant_button.click()
        w.tick()

    choose(b)
    c.compare_button.click()
    code, lines, cells = w.comparing.result(timeout=120)
    w.tick()
    assert code == 0 and items(c.lines) == [control.text(x, p) for x, p in lines] and len(cells) == 9
    assert [[c.table.item(k, j).text() for j in range(10)] for k in range(c.table.rowCount())] == cells
    w.tabs.setCurrentWidget(c)
    qapp.processEvents()
    assert not c.picture.pixmap().isNull() and (a.parent / "compare" / "compare.png").is_file()
    assert stamps(*watched) == before and not (b.parent / "compare").exists()  # read in place, never written
    grab(w, "compare-si")
    for project, shown in ((ant, render("G_COMPARE_KIND", path=str(ant))),
                           (cell, render("E_COMPARE_SETTINGS", fields="mesh")),  # the fingerprint's d_fill
                           (target, render("E_COMPARE_SETTINGS", fields="target_ohm"))):
        choose(project)
        c.compare_button.click()
        w.comparing.exception(timeout=120)
        w.tick()
        assert (c.status.text(), c.lines.count(), c.table.rowCount()) == (shown, 0, 0)
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py tests/test_sexpr.py -q -k "compare or quoted"`. Expected: FAIL (`module ... has no attribute 'cells'`; then E_INTERNAL's `KeyError: 'tdr_lowest'`).
- [ ] **Step 3: `control.cells(rows)`** takes `control.compare`'s comprehension and widens it: the quantity `render(QUANTITIES[q])` when in QUANTITIES, else the symbol as si_delta_lines writes it, `q.upper()` for next and fext, else `q.removesuffix("_worst").capitalize()` (Sdd21, S11, Scd21), with `# symbols, the same in both languages (pt-BR design 5.1), so no catalog code`; the marker `render(MARKS[m])` when in MARKS, else as compare.csv holds it; base and variant to `3 if q in INSERTION else DIGITS[unit]` digits, signed for the skew as its line signs them (`"+"`), delta (signed) and threshold to `3 if q in INSERTION else DIGITS[delta_unit]`; f in MHz to one decimal; an empty cell empty; the verdict as now. `compare` returns `cells(list(csv.DictReader(f)))`. Docstrings: `cells`' says what each column shows; `compare`'s names SI projects and `cells`.
- [ ] **Step 4: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| G_QUANTITY_TDR_LOWEST | Lowest TDR level | Nível mais baixo do TDR |
| G_QUANTITY_TDR_HIGHEST | Highest TDR level | Nível mais alto do TDR |
| G_QUANTITY_SKEW | Intra-pair skew | Skew intrapar |
| G_MARK_SHORT | short feature | trecho curto |
| G_MARK_MARKER | marker | marcador |
| G_COMPARE_NONE (changed) | Open an antenna or a signal-integrity project, then choose the variant to compare it with. | Abra um projeto de antena ou de integridade de sinal e escolha a variante a comparar com ele. |
| G_COMPARE_KIND (changed) | {path} is not of the kind Compare the projects takes here: two antenna projects or two signal-integrity projects, made with New from a board and the kind Antenna or Signal integrity. | {path} não é do tipo que o botão Comparar os projetos compara aqui: dois projetos de antena ou dois projetos de integridade de sinal, criados com Novo projeto a partir de uma placa e o tipo Antena ou Integridade de sinal. |
| G_COMPARE_NO_RESULT (changed) | {path} has no result that Compare the projects can use: a run of its current model, made by this version, with no part port on its chain or lines, or, with part ports, a verify of that run at the values project.json holds. Run it (a board re-saved since its run needs one), then press Verify for a project with part ports. | {path} não tem resultado que o botão Comparar os projetos possa usar: uma execução do modelo atual dele, feita por esta versão, sem porta de componente na cadeia ou nas linhas ou, com portas de componentes, uma verificação dessa execução com os valores que o project.json guarda. Execute-o (uma placa salva de novo desde a execução precisa de uma) e depois pressione Verificar num projeto com portas de componentes. |

- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_gui.py tests/test_gui_control.py tests/test_sexpr.py -q`. Expected: PASS, the antenna's compare tests unchanged.
- [ ] **Step 6: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(gui): Compare for SI projects: the deltas table with each quantity and mark in the window's words, rounded and signed as the lines, written into the base's own folder (Stage 4 design 5.8, 5.10)"
graphify update .
```

---

### Task 8 [code]: The button hands over tracks, arcs and vias, and the tracer walks their line

**Files:**
- Modify: `button.py` (`read` :72-90); `core/kicad/tracer.py` (new `p_side` and `si_candidates` after `partner_ends` :293-309); `tests/fake_kicad.py` (:26-84).
- Test: `tests/test_button.py` (:40-77's exact handoff; a new test), `tests/test_si_lines.py`.

**Interfaces:**
- Consumes: kipy 0.8's `Track`, `ArcTrack`, `Via` (`kipy.board_types`) and `KiCadObjectType.KOT_PCB_TRACE` (11), `KOT_PCB_ARC` (13), `KOT_PCB_VIA` (12); tracer's `_walk`, `_links`, `_copper`, `partner_net`, `_ALIAS`.
- Produces:
  - `button.read(...)`'s handoff gains `"tracks"`: the selected tracks', arcs' and vias' KIIDs, after `"footprints"`.
  - `tracer.p_side(net: str, nets: Collection[str]) -> str` and `tracer.si_candidates(board: Board, classes: Classes, net: str) -> tuple[list[str], list[Pad]]`.
  - `FakeKiCad(..., tracks=(), arcs=(), vias=())`, each a list of KIIDs, packed as `board_types_pb2.Track`, `Arc` and `Via`; GetSelection answers only the request's `types`.

- [ ] **Step 1: Write the failing tests.** `tests/test_button.py`: the first test's handoff dict gains `"tracks": []` after `"footprints"`; new:

```python
def test_a_press_hands_the_selected_tracks_arcs_and_vias_by_their_kiids(fake, kicad, monkeypatch):  # 5.10; ruling 9
    def pressed(**selection):
        k = kicad(**selection)
        monkeypatch.setenv("KICAD_API_SOCKET", k.url)
        monkeypatch.setenv("KICAD_API_TOKEN", k.token)
        assert button.main() == 0
        return json.loads((fake / "handoff.json").read_text(encoding="utf-8"))

    recorder(monkeypatch)
    data = pressed(pads=[KIID["U1.1"]], tracks=["t-1"], arcs=["a-1"], vias=["v-1"])
    assert (data["pads"], data["footprints"], data["tracks"]) == ([KIID["U1.1"]], [], ["t-1", "a-1", "v-1"])
    assert pressed(arcs=["a-2"])["tracks"] == ["a-2"]  # KOT_PCB_ARC asked for: the fake answers only asked types
```

  `tests/test_si_lines.py` (imports gain `load_board` beside `classify`, `FIX` beside the test_tracer helpers, and `p_side` and `si_candidates` beside `partner_net`):

```python
def test_the_buttons_line_is_the_walk_through_its_parts_on_the_p_side():  # design 5.10 as A-66 amends it; RF 3
    assert [p_side(n, NETS) for n in ("USB_D-", "USB_D+", "D_N_1", "CLKN", "/eth/TX-", "USB_DM", "A_DN", "A_DM",
                                      "+3V3")] == [
        "USB_D+", "USB_D+", "D_P_1", "CLKP", "/eth/TX+", "USB_DP", "A_DP", "A_DP", "+3V3"]
    for board, net, nets, pads in (
            ("usb2_hs", "USB_D+", ["USB_D+", "MCU_D+"], ["J1.3", "U1.3", "U2.3", "U2.4"]),  # the ESD array's two
            ("usb2_hs", "AUX", ["AUX"], []), ("qspi_clk", "FLASH_CLK", ["FLASH_CLK", "QSPI_CLK"], ["U1.11", "U2.6"]),
            ("lpf915", "RF_A", ["RF_A", "RF_B", "RF_C", "RF_OUT"], ["J1.1", "U1.1"])):
        b = load_board(FIX / f"{board}.kicad_pcb")
        walked, found = si_candidates(b, classify(b), net)
        assert (walked, sorted(p.name for p in found)) == (nets, sorted(pads)), board
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_button.py tests/test_si_lines.py -q`. Expected: FAIL (`FakeKiCad() got an unexpected keyword argument 'tracks'`; `cannot import name 'p_side'`).
- [ ] **Step 3: `tests/fake_kicad.py`.** `__init__` gains `tracks=(), arcs=(), vias=()` (KIIDs); `answer` passes the request to `response(kind, request)`; GetSelection unpacks `editor_commands_pb2.GetSelection` from `request.message` and packs, in this order, only the asked types: pads (KOT_PCB_PAD), footprints (KOT_PCB_FOOTPRINT), tracks as `board_types_pb2.Track`, arcs as `board_types_pb2.Arc` and vias as `board_types_pb2.Via` (KOT_PCB_TRACE, KOT_PCB_ARC, KOT_PCB_VIA), each `item.id.value = kiid`. The docstring names the three and the filter.
- [ ] **Step 4: `button.read`.** `types` gains KOT_PCB_TRACE, KOT_PCB_ARC and KOT_PCB_VIA; the handoff gains `"tracks": [item.id.value for item in selected if isinstance(item, (Track, ArcTrack, Via))]` after `"footprints"`; docstring "…, its selected pads (KIIDs), footprints (references) and tracks, arcs and vias (KIIDs, as "tracks"), …".
- [ ] **Step 5: `tracer`.**
  - `p_side(net, nets)`: `net` itself when partner_net finds none; else its partner when `net` is the N side, a stem (the name past its trailing digits and underscores) ending in `-` or `N` by the rule, or the alias's `M`; else `net`. Docstring: "The P side of the pair `net` belongs to, among the board's `nets` (Stage 4 plan 5's button, A-66): its partner when partner_net pairs it as the N side (a `-` or an upper-case N by KiCad's rule, DM by the alias), else `net` itself, also when it has no partner."
  - `si_candidates(board, classes, net)`: `nets = list(_walk(_links(board, classes), net))` and the copper pads on them (`_copper`) of each footprint that is one of `classes.connectors` or has three or more copper pads. Docstring: "The line through `net` for the KiCad button (Stage 4 design 5.10 as A-66 amends it): the nets a walk through its two-pad parts reaches (_walk over _links, as trace_chain walks), `net` first, and the copper pads on them of connectors and of footprints with three or more copper pads, choose_reference's IC or connector rule. An ESD array's pads count: no flow-through rule drops them." Comments `# ponytail: choose_reference's rule written again here, not shared: choose_reference needs which rule holds (connector or IC), this only whether one does; a shared predicate when a third caller comes` and `# ponytail: an ESD array's flow-through pads count as ends, so usb2_hs pre-fills none (G_HANDOFF_SI_ENDS names the four); a flow-through rule if users meet it, sparing a USB-C connector's A6/B6`.
- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_gui.py -q -k "press or handoff"`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(button): a press hands over the selected tracks, arcs and vias by their KIIDs, and the tracer walks their line through its parts on the pair's P side (Stage 4 design 5.10)"
graphify update .
```

---

### Task 9 [code]: A selected track, arc or via pre-fills New's SI line

**Files:**
- Modify: `gui/control.py` (imports; `Handed` :476-492; `handed` :495-555; new `_si_handed`); `gui/window.py` (`show_pads` :1030-1064; `take_handoff`'s docstring :972-983); `core/messages.py`; `po/*`; the `.mo`.
- Test: `tests/test_gui_control.py` (`press` :189-194 gains `tracks`; new `track_of` and test), `tests/test_gui.py`, `tests/test_sexpr.py` (`QUOTED["G_BUTTON_ACTION"]` stays `("G_NEW",)`).

**Interfaces:**
- Consumes: Task 8's `p_side`, `si_candidates`, `"tracks"`; Task 6's `NewForm.interface`, `pair`, `pair_with`, `victims`; `partner_net`, `partner_ends`, `classify`, `_names`, `INTERFACES`.
- Produces: `Handed` gains, last, `net: str = ""` and `partner: str = ""` (kind `"si"`); `control._si_handed(b: Board, track_nets: list[str], selected: list[Pad]) -> tuple[str, str, list[str], tuple[str, dict] | None]`, the line's (net, partner, [start, end] or [], problem); G_HANDOFF_SI_ENDS {net, count, pads}, G_HANDOFF_NETS {count, nets}, G_HANDOFF_SI_NET {net}.

- [ ] **Step 1: Write the failing tests.** `tests/test_gui_control.py`: `press(board, pads=(), footprints=(), socket="ipc://s", token="T", tracks=())` writes `"tracks": list(tracks)` after `"footprints"`, and:

```python
def track_of(board, net, via=False):
    """The KIID of the first track, or via, of `net` in the saved `board`."""
    b = load_board(board)
    return next(t.uuid for t in (b.vias if via else b.tracks) if t.net == net)


def test_a_press_on_a_track_arc_or_via_pre_fills_its_line(fake):  # design 5.10 as A-66 amends it; RF 3
    usb, qspi, arc = (FIX / f"{name}.kicad_pcb" for name in ("usb2_hs", "qspi_clk", "coupon_gcpw_arc"))

    def read(board, tracks, pads=(), footprints=()):
        return control.handed(press(board, pads, footprints, tracks=tracks))

    q = read(qspi, [track_of(qspi, "FLASH_CLK")])
    assert (q.kind, q.net, q.partner, q.start, q.end, q.problem) == ("si", "FLASH_CLK", "", "U1.11", "U2.6", None)
    assert q.pads == control.pads(qspi)
    v = read(qspi, [track_of(qspi, "FLASH_CLK", via=True)])  # a via alone: the same line through R1
    assert (v.start, v.end) == ("U1.11", "U2.6")
    four = ("G_HANDOFF_SI_ENDS", {"net": "USB_D+", "count": 4, "pads": "J1.3, U1.3, U2.3, U2.4"})
    p = read(usb, [track_of(usb, "USB_D+")])
    assert (p.kind, p.net, p.partner, p.start, p.end, p.problem) == ("si", "USB_D+", "USB_D-", "", "", four)
    n = read(usb, [track_of(usb, "MCU_D-")])  # the N side: the P net and its partner
    assert (n.net, n.partner, n.problem) == ("MCU_D+", "MCU_D-", (four[0], {**four[1], "net": "MCU_D+"}))
    assert read(usb, [track_of(usb, x) for x in ("USB_D+", "USB_D-", "MCU_D+")]).problem == four  # one line
    box = read(usb, [track_of(usb, "USB_D+")], (), ["R1", "R2"])  # a box selection's parts narrow no picker
    assert (box.pads, box.problem) == (control.pads(usb), four)
    ends = read(usb, [track_of(usb, "USB_D+")], ["U1.3", "J1.3"])  # its ends selected: the connector's first
    assert (ends.start, ends.end, ends.problem) == ("J1.3", "U1.3", None)
    legs = read(usb, [track_of(usb, "USB_D-")], ["J1.2", "U1.2"])  # the N leg's own ends, taken to the P side
    assert (legs.net, legs.start, legs.end, legs.problem) == ("USB_D+", "J1.3", "U1.3", None)
    nets = read(usb, [track_of(usb, "AUX"), track_of(usb, "USB_D+")])
    assert (nets.kind, nets.start, nets.problem) == ("si", "", ("G_HANDOFF_NETS", {"count": 2, "nets": "AUX, USB_D+"}))
    assert read(usb, [track_of(usb, "AUX")]).problem == ("G_HANDOFF_SI_ENDS", {"net": "AUX", "count": 0,
                                                                                "pads": "T_NONE"})
    gnd = read(usb, [track_of(usb, "GND", via=True)])
    assert (gnd.kind, gnd.problem) == ("si", ("G_HANDOFF_SI_NET", {"net": "GND"}))
    curve = read(arc, [next(t.uuid for t in load_board(arc).tracks if t.mid is not None)])
    assert (curve.net, curve.problem) == ("LINE", ("G_HANDOFF_SI_ENDS", {"net": "LINE", "count": 0, "pads": "T_NONE"}))
    assert read(usb, ["00000000-0000-0000-0000-000000000001"]).problem == ("G_HANDOFF_UNSAVED", {"board": str(usb)})
    ifa = FIX / "ifa2g4_pi.kicad_pcb"
    assert read(ifa, [track_of(ifa, "RF_A")], (), ["AE1"]).kind == "antenna"  # the antenna's rules first
    assert (read(usb, [], ["J1.3", "U1.3"]).kind, read(usb, [], ["J1.3", "U1.3"]).end) == ("chain", "J1.3")  # v1's
```

  `tests/test_gui.py` (imports gain `track_of` from test_gui_control):

```python
def test_a_press_on_a_track_pre_fills_new_with_the_si_kind_its_interface_its_pair_and_its_ends(window, tmp_path):
    qspi, usb = tmp_path / "qspi_clk.kicad_pcb", tmp_path / "usb2_hs.kicad_pcb"  # 5.10; ruling 9; RF 3
    for board in (qspi, usb):
        board.write_bytes((FIX / board.name).read_bytes())
    w = window()
    f = w.new_form
    w.take_handoff(press(qspi, tracks=[track_of(qspi, "FLASH_CLK")]))
    w.pads_read.result(timeout=60)
    w.tick()
    assert (f.kind.currentData(), f.interface.currentData(), f.pair.currentData(), f.start.currentText(),
            f.end.currentText(), f.status.text()) == ("si", "se50", None, "U1.11", "U2.6", "")  # a single net
    assert f.form.isRowVisible(f.pair_row) and not f.form.isRowVisible(f.f0)
    f.create_button.click()  # the pre-fill creates as it stands
    path, _ = w.creating.result(timeout=120)
    w.tick()
    assert load_project(path) == load_project(cli.new_si(qspi, "U1.11", "U2.6", "se50", output=tmp_path / "cli")[0])
    w.take_handoff(press(usb, tracks=[track_of(usb, "MCU_D-")]))
    w.pads_read.result(timeout=60)
    w.tick()
    assert (f.kind.currentData(), f.interface.currentData(), f.pair.currentData(), f.start.currentText(),
            f.status.text()) == ("si", "usb2-hs", "rule", "", render("G_HANDOFF_SI_ENDS", net="MCU_D+", count=4,
                                                                    pads="J1.3, U1.3, U2.3, U2.4"))
    assert [f.victims[0][0].itemText(k) for k in range(f.victims[0][0].count())] == control.pads(usb)
    grab(w, "handoff-si")
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q -k "press or handoff"`. Expected: FAIL (`Handed` has no `net`; the tracks ignored, v1's rules).
- [ ] **Step 3: `control.handed`.** It reads `tracks = data.get("tracks", [])` (`# a handoff written before plan 5's helper has none`) and joins them by KIID, `nets_of = {t.uuid: t.net for t in b.tracks} | {v.uuid: v.net for v in b.vias}` (an arc is a Track with `mid`); a KIID the file lacks joins the unsaved check. After the antenna's branch, with tracks, `net, partner, ends, problem = _si_handed(b, [nets_of[k] for k in tracks], selected)` and `Handed(board, socket, token, _names(b.all_pads()), *(ends or ["", ""]), problem, "si", kinds=kinds, net=net, partner=partner)`: the pickers every pad with copper, so a box selection's footprints narrow none; v1's rules follow as now. `_si_handed`, test-first, takes these rules in order (classes `classify(b)`; a selected pad counts with copper, `p.layers`):
  1. The nets: the tracks', then the selected pads', each once in that order, ground, power and netless ones dropped (`classes.gnd | classes.power`, `""`); none left: `("", "", [], ("G_HANDOFF_SI_NET", {"net": track_nets[0] or "T_NONE"}))`.
  2. Each net taken on its pair's P side (`p_side(net, b.nets)`) and walked (`si_candidates`); nets whose walks reach the same nets are one line, named by the first one's P net; two lines or more: `("", "", [], ("G_HANDOFF_NETS", {"count": …, "nets": their P nets ", "-joined in that order}))`.
  3. One line: `net` its P net and `partner` `partner_net(net, b.nets)`'s ("" for none). Its ends: the selected pads on its walked nets, by name, each once, in the order they came in; with none there and exactly two selected, the first two that `partner_ends(b, classes, *their names)` gives (an N leg's own ends, taken to the P side; its KrsError skips this rule); else its candidates' names (`_names`).
  4. Exactly two: start and end, swapped when only the second is a connector's (`classes.connectors`), so that the connector's side is the start, as every SI project of the repo runs (si_args, the tutorial, P4-F: J1.3 → U1.3; design 5.11: the MCU at the far end); any other count: `[]` and `("G_HANDOFF_SI_ENDS", {"net": net, "count": …, "pads": ", "-joined or "T_NONE"})`.

  `handed`'s docstring gains the SI rule after the antenna's: "- tracks, arcs or vias selected (Stage 4 design 5.10 as A-66 amends it): the SI kind, the pickers every pad with copper; their nets and the selected pads', ground, power and netless ones dropped (none left: G_HANDOFF_SI_NET), each taken on its pair's P side (p_side) and walked through its two-pad parts (si_candidates); two lines or more: G_HANDOFF_NETS; else `net` and its `partner`, and as its end pads the selected pads on the line (an N leg's two taken to the P side by partner_ends), else its IC or connector pads: exactly two pre-fill start and end, the connector's side the start, any other count G_HANDOFF_SI_ENDS, no ESD rule." `Handed`'s docstring names `net` and `partner`. Imports gain `p_side`, `partner_ends`, `partner_net`, `si_candidates`.
- [ ] **Step 4: `show_pads`,** for a press of the SI kind that names a line (`read.net`), after the kind: the interface fitted to it, `"se50"`, the one single-ended preset, when it has no partner and a pair's preset is set, `"usb2-hs"`, New's default, when it has one and se50 is set, Custom kept (`findData`); then `f.pair` `"rule"` with a partner, else None. A press that names no line leaves both. `take_handoff`'s docstring names the SI kind and the interface.
- [ ] **Step 5: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| G_HANDOFF_SI_ENDS | {count} IC or connector pads lie on the line through {net} ({pads}). Pick the start and end pads here, or select the line's two end pads in KiCad with one of its tracks and press the button again. | Ilhas de CI ou de conector na linha que passa por {net}: {count} ({pads}). Escolha aqui as ilhas inicial e final, ou selecione no KiCad as duas ilhas das pontas da linha com uma das trilhas dela e pressione o botão de novo. |
| G_HANDOFF_NETS | Tracks or pads of {count} lines are selected in KiCad ({nets}). Select one line's tracks, or its pair's, and press the button again, or pick its pads here. | Trilhas ou ilhas de linhas selecionadas no KiCad: {count} ({nets}). Selecione as trilhas de uma linha, ou do par dela, e pressione o botão de novo, ou escolha as ilhas dela aqui. |
| G_HANDOFF_SI_NET | The tracks and vias selected in KiCad are on {net}, a ground, power or netless net, which is no signal line. Select a track of the line to measure and press the button again. | As trilhas e vias selecionadas no KiCad estão em {net}, uma rede de terra, de alimentação ou sem rede, que não é uma linha de sinal. Selecione uma trilha da linha a medir e pressione o botão de novo. |
| G_HANDOFF_UNSAVED (changed) | {board} as saved lacks a pad, a part, a track or a via selected in KiCad, which holds edits not yet saved: save the board in KiCad and press the button again. | A versão salva de {board} não tem uma ilha, um componente, uma trilha ou uma via selecionada no KiCad, que guarda edições ainda não salvas: salve a placa no KiCad e pressione o botão de novo. |
| G_BUTTON_ACTION (changed) | Opens kicad-rf-studio on this board and pre-fills New from a board with the selected pads, with a selected antenna and its radio pin, or with a selected track, arc or via of a signal-integrity line. | Abre o kicad-rf-studio nesta placa e preenche Novo projeto a partir de uma placa com as ilhas selecionadas, com uma antena selecionada e o pino do rádio dela, ou com uma trilha, um arco ou uma via selecionada de uma linha de integridade de sinal. |

  `plugin.json` renders G_BUTTON_ACTION (`tests/test_button.py:259` renders it too); the manifest's shape, `install-kicad-plugin` and the launcher do not change.
- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_button.py tests/test_gui.py tests/test_gui_control.py tests/test_sexpr.py -q`. Expected: PASS, v1's and the antenna's press tests unchanged.
- [ ] **Step 7: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add src tests po
git commit -m "feat(button): a selected track, arc or via pre-fills New with the SI kind, an interface that fits its line, its P net and partner, and its two IC or connector pads, the connector's first, when it has exactly two (Stage 4 design 5.10)"
graphify update .
```

---

### Task 10 [code]: The README's SI tutorial and the release check's si step

**Files:**
- Modify: `README.md` (Install step 5 :34; Development setup step 6 :295; new `## Signal-integrity tutorial` after the antenna tutorial's limits, before `## Development setup` :288); `tools/release_check.py` (docstring :2-14; new `si`; `NEEDS`, `STEPS` :207-208).
- Test: `tests/test_repo.py`, `tests/test_release_check.py` (`test_the_antenna_step_…`'s STEPS assertion :133; a new test).

**Interfaces:**
- Consumes: `release_check.run`, `program`, `isolated`, `failed`; `CATALOG`, `DIFF_OHM`, `SE_OHM`.
- Produces: `release_check.si(tmp: Path) -> tuple[str, str]`; `NEEDS["si"] = "install"`; `STEPS = (build, install, gui, antenna, si, plugin, privacy)`.

- [ ] **Step 1: Write the failing tests.** `tests/test_repo.py` (imports gain `from kicad_rf_studio.core.post.si import DIFF_OHM, SE_OHM`):

```python
def test_the_readme_has_an_si_tutorial():  # Stage 4 design 5.12 item 5; ruling 11
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.index("\n## Antenna tutorial\n") < readme.index("\n## Signal-integrity tutorial\n") < readme.index(
        "\n## Development setup\n")
    tutorial = readme.split("\n## Signal-integrity tutorial\n", 1)[1].split("\n## ", 1)[0]
    pair = "--start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1"
    for command in (f"new tests/fixtures/usb2_hs.kicad_pcb {pair} -o usb2_hs", "cost usb2_hs", "run usb2_hs",
                    "retune usb2_hs R1=24 R2=24", "verify usb2_hs",
                    f"new tests/fixtures/usb2_hs_gap.kicad_pcb {pair} -o usb2_hs_gap", "run usb2_hs_gap",
                    "retune usb2_hs_gap R1=24 R2=24", "verify usb2_hs_gap", "compare usb2_hs usb2_hs_gap -o compare"):
        assert f"kicad-rf-studio {command}\n" in tutorial, command
    assert "\n### What these results do not tell you\n" in tutorial and CATALOG["I_SI_RELATIVE"] in tutorial
    assert f"{DIFF_OHM:g} Ω" in tutorial and f"{SE_OHM:g} Ω" in tutorial  # the short band and compare's thresholds
    assert "a track, arc or via" in readme.split("\n## Install\n", 1)[1].split("\n## ", 1)[0]
```

  `tests/test_release_check.py`: the antenna test's STEPS assertion becomes `["build", "install", "gui", "antenna", "si", "plugin", "privacy"]`, and:

```python
def test_the_si_step_runs_new_interface_on_the_releases_own_fixture_and_reads_schema_3(tmp_path, monkeypatch):
    fixture = ROOT / "tests" / "fixtures" / "usb2_hs.kicad_pcb"  # Stage 4 design 5.12 item 5; ruling 12
    with zipfile.ZipFile(tmp_path / "source.zip", "w") as z:
        z.write(fixture, "tests/fixtures/usb2_hs.kicad_pcb")
    line = {"chain": {"series": [{"role": "port"}], "shunt": []}}  # R1, then R2: a part port each
    seen, data = [], {"schema": 3, "kind": "si", "ports": [{}] * 6, "lines": [line, line]}

    def run(command, **kw):  # the fresh venv's new: it writes project.json where -o says
        seen.append((command, kw["env"]))
        out = Path(command[command.index("-o") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "project.json").write_text(json.dumps(data), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(release_check, "run", run)
    assert release_check.si(tmp_path)[0] == "PASS"
    (command, env), = seen
    assert command[:2] == [release_check.program(tmp_path, "kicad-rf-studio"), "new"]
    assert command[3:12] == ["--start", "J1.3", "--end", "U1.3", "--interface", "usb2-hs", "--pair", "--victim",
                             "TP1.1:TP2.1"]
    assert Path(command[2]).read_bytes() == fixture.read_bytes() and env["QT_QPA_PLATFORM"] == "offscreen"
    data = {**data, "ports": [{}] * 5}
    assert release_check.si(tmp_path)[0] == "FAIL"  # 7 ports where a run takes 8
    assert release_check.NEEDS["si"] == "install"
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_repo.py tests/test_release_check.py -q`. Expected: FAIL (no SI tutorial; `module 'release_check' has no attribute 'si'`).
- [ ] **Step 3: `tools/release_check.py`.** `si(tmp)` mirrors `antenna`: the fixture extracted from `tmp/source.zip` to `tmp/source`; `[program(tmp, "kicad-rf-studio"), "new", <it>, "--start", "J1.3", "--end", "U1.3", "--interface", "usb2-hs", "--pair", "--victim", "TP1.1:TP2.1", "-o", str(tmp / "si")]` through `run(command, timeout=300, env=isolated(tmp))`; a non-zero exit `failed(...)`; then `ports = len(data.get("ports", [])) + sum(q.get("role") == "port" for x in data.get("lines", []) for q in x["chain"]["series"] + x["chain"]["shunt"])`; `(schema, kind, ports)` other than `(3, "si", 8)` gives `("FAIL", f"…/si/project.json: schema {schema!r}, kind {kind!r}, {ports} ports")`, else `("PASS", "new wrote an SI project, schema 3, 8 ports, from tests/fixtures/usb2_hs.kicad_pcb in the fresh venv")`. Docstring "(e) `new --interface` … its project.json schema 3, kind si and 8 ports, the pair's 4, the victim's 2 and R1's and R2's: the installed tracer's pair rule and schema 3 at no cost (no openEMS runs)". `NEEDS["si"] = "install"`, `STEPS` as in Interfaces; plugin and privacy become (f) and (g); the module docstring says seven steps and names `si`.
- [ ] **Step 4: `README.md`.** Install step 5 ends "…: select the chain's two end pads, the antenna footprint (or one of its pads) and the radio pin, or a track, arc or via of a signal-integrity line, and press the kicad-rf-studio button. After updating kicad-rf-studio, run `install-kicad-plugin` again: the button's tooltip, which says what it takes, is written there." Development setup step 6's release-check sentence gains "and `new --interface` on `tests/fixtures/usb2_hs.kicad_pcb`" after its antenna fixture. Then this section, after the antenna tutorial's limits; Task 15 adds each step's lines, from the acceptance run, after its command fence:

````markdown
## Signal-integrity tutorial

This takes `usb2_hs`, the synthetic four-layer USB 2.0 high-speed board in `tests/fixtures`: a micro-B connector J1, the pads of a six-pin ESD array U2 on the pair, a 22 Ω 0402 series resistor on each leg (R1 and R2) and an MCU-like QFN U1 at the far end, with a neighbour net, AUX, running beside part of the route between the test points TP1 and TP2. It goes through `new --interface`, `cost`, `run`, `retune` and `verify`, then compares it with `usb2_hs_gap`, the same board with a slot in the plane under the pair. Run the commands as in the Tutorial above.

The times were measured on the development PC (Windows 11, 16 CPUs) at the Normal preset, `new`'s default, by the run through the GUI that closed Stage 4 (`docs/validation/<date>-stage4-exit.md`). That run compared with the plane-gap board that gate P4-F had run (`docs/validation/2026-11-08-p4-f.md`), retuned and verified for it, so the gap's run time is P4-F's and its verify time that preparation's. `cost` prints your own machine's estimate before every run, and no runtime is promised. The excerpts are real output of that run; `<run folder>` stands for a run's folder in the per-user data folder, and `usb2_hs`, `usb2_hs_gap` and `compare` for the projects' and the compare's folders.

**`new --interface`** traces the measured line from the connector's pin J1.3 through R1 to the MCU's pin U1.3, takes its partner by KiCad's pair rule (`--pair`: USB_D+ with USB_D-, ending at J1.2 and U1.2) and AUX between TP1.1 and TP2.1 as a victim, and writes a signal-integrity project for the `usb2-hs` interface: 90 Ω differential ± 10 %, the link's 500 ps edge and a 240 MHz marker, simulated to 10 GHz. R1 and R2 are part ports, so their values can be retuned.

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/usb2_hs.kicad_pcb --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o usb2_hs
```

**`cost`** first lists the 2D table, every straight section's impedance against the target band, in seconds and before any run; then the cells, the runs broken down into the lines' ends, the victim's and the part ports, the worst case, and the time a job whose planes ring may take past T_max.

```
<venv>\Scripts\kicad-rf-studio cost usb2_hs
```

**`run`** runs one job per port: the pair's four ends, the victim's two and the part ports R1 and R2. It gives the TDR along the route against the target band, the mixed-mode S (Sdd21, Sdd11, Scc21 and Scd21), the skew and the crosstalk into AUX, for any values of R1 and R2.

```
<venv>\Scripts\kicad-rf-studio run usb2_hs
```

**`retune`** closes the part ports at new values, with no new run: 24 Ω, the value the GUI's E24 snapping gives a typed 25 Ω. `0R` replaces a series part with a short.

```
<venv>\Scripts\kicad-rf-studio retune usb2_hs R1=24 R2=24
```

**`verify`** runs one job per external port with R1 and R2 in the grid at their values, as ideal parts, and compares the result with the retune's.

```
<venv>\Scripts\kicad-rf-studio verify usb2_hs
```

**`compare`** reads both projects' verified results, which must share every setting, and marks each difference resolved or not. First the same steps on the plane-gap board, then the compare, which writes `compare.csv` and `compare.png` into `compare`:

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/usb2_hs_gap.kicad_pcb --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o usb2_hs_gap
<venv>\Scripts\kicad-rf-studio run usb2_hs_gap
<venv>\Scripts\kicad-rf-studio retune usb2_hs_gap R1=24 R2=24
<venv>\Scripts\kicad-rf-studio verify usb2_hs_gap
<venv>\Scripts\kicad-rf-studio compare usb2_hs usb2_hs_gap -o compare
```

In the GUI, New's kind Signal integrity takes the start and end pads, the interface, the pair (none, KiCad's rule or its two end pads picked) and up to two victims; the Cost tab lists the 2D table before the estimate; Results shows the TDR with the target band, the mixed-mode S and the crosstalk, and retunes R1 and R2 with E24 snapping; the Compare tab compares the open project with a variant. The KiCad button pre-fills New with the signal-integrity kind, the pair and an interface that fits it from a selected track, arc or via, and with the line's two end pads, the connector's first, when it has exactly two IC or connector pads: on `usb2_hs` the ESD array's pads make four, so pick J1.3 and U1.3, or select them in KiCad with a track of the pair.

### What these results do not tell you

- Every signal-integrity result carries this line: "Relative: these signal-integrity results compare variants of one board under identical settings; they do not predict measured performance."
- A TDR level marked short lies on a feature shorter than two resolution lengths, so it is not that feature's impedance; on this route about 1.1 resolution lengths lie between the launches, and the 2D table gives a straight section's impedance. A level within 2.2 Ω of a pair's target (1.1 Ω of a single net's) marks no feature, and the same values are compare's thresholds on a TDR level, three times the model's measured noise (gate P4-E, `docs/validation/2026-11-07-p4-e.md`).
- Copper staircased at 45° or along arcs is only warned about: gate P4-B measured a 45° pair 2.27 % (90 Ω) and 5.35 % (100 Ω) off its axis-aligned twin at mesh n 2, and whether such a pair is refused or run at a finer mesh is not decided yet (`docs/validation/2026-11-06-p4-b.md`).
- The dielectric is lossless by default, so S holds no dielectric loss, and the loss lines estimate it with the copper's. `"dielectric": "debye"` in project.json is the option, at a cost: a Debye cell weighs about 109 plain cells, so this board would run about 33 times slower (gate P4-D, `docs/validation/2026-11-07-p4-d.md`).
- A job whose port residual still falls fast enough at T_max runs on, up to four times T_max: the planes' cavity resonances ring in a lossless model, and they depend on the crop, so their frequencies and depths are no predictions. `cost` prints the time to that ceiling.
- `cost` prices a run of two jobs at once about 1.9 times too long, on the safe side, until a run with that many jobs at once measures the speed (`docs/validation/2026-11-08-p4-refit.md`).
- Copper is a perfect conductor; packages, dies and the connector's body are absent, and the ESD array is its pads alone; the ports are lumped at the pads.
- The retune stays what-if: `verify` checks the layout reduction with ideal parts, not the vendor parts.
````

  The `<date>` is the exit record's, filled in Task 15.
- [ ] **Step 5: Run them again.** Step 2's command. Expected: PASS (the README's code-span check finds `compare` and `new` real subcommands).
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add README.md tools/release_check.py tests/test_repo.py tests/test_release_check.py
git commit -m "docs(readme): the signal-integrity tutorial on the USB 2.0 fixture and its limits; the release check runs new --interface in the fresh venv (Stage 4 design 5.12 item 5)"
graphify update .
```

---

### Task 11 [code]: NOTICE, golden_antenna's stamp and argparse's name for REF.PAD:REF.PAD

**Files:**
- Modify: `NOTICE` (:15-22); `tests/fixtures/golden_antenna.json` (:2, the `"code"` value alone); `cli.py` (`_ends` :55-60).
- Test: `tests/test_repo.py`, `tests/test_cli_si.py`.

- [ ] **Step 1: Write the failing tests.** `tests/test_repo.py` (imports gain `json`):

```python
def test_notice_names_each_kicad_calculator_file_the_tests_port():  # ruling 13; P4-A's c_microstrip.cpp
    ported = set(re.findall(r"pcb_calculator/transline/(\w+\.(?:cpp|h))",
                            (ROOT / "tests" / "kicad_lines.py").read_text(encoding="utf-8")))
    entry = next(e for e in (ROOT / "NOTICE").read_text(encoding="utf-8").split("\n\n\n")
                 if e.startswith("KiCad line-calculator formulas"))
    assert ported == {"microstrip.cpp", "c_microstrip.cpp", "coplanar.cpp", "transline.cpp", "units.h"}
    assert ported <= set(re.findall(r"\b\w+\.(?:cpp|h)\b", entry))


def test_every_golden_pin_names_a_clean_product_tree():  # ruling 13: golden_antenna's +dirty stamp (plan 4's R-11)
    stamps = {p.name: json.loads(p.read_text(encoding="utf-8"))["code"]
              for p in sorted((ROOT / "tests" / "fixtures").glob("golden_*.json"))}
    assert sorted(stamps) == ["golden_antenna.json", "golden_si.json", "golden_v1.json"]
    assert [name for name, code in stamps.items() if not re.fullmatch(r"[0-9a-f]{40}", code)] == []
    assert stamps["golden_antenna.json"] == "e5469200427c76d82e9d2893363696ead16cf351"  # R-11's src tree, at 8faa7d6
```

  `tests/test_cli_si.py`:

```python
def test_a_bad_pair_of_ends_is_named_by_its_form(capsys):  # plan 2's minor; ruling 13
    with pytest.raises(SystemExit) as e:
        main(["new", str(USB), "--start", "J1.3", "--end", "U1.3", "--interface", "usb2-hs", "--victim", "TP1.1"])
    assert e.value.code == 2 and "invalid REF.PAD:REF.PAD value: 'TP1.1'" in capsys.readouterr().err
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_repo.py tests/test_cli_si.py -q`. Expected: FAIL (c_microstrip.cpp not in NOTICE; the `+dirty` stamp; "invalid _ends value").
- [ ] **Step 3: The fixes.**
  - NOTICE's KiCad line-calculator entry: Upstream "…files pcb_calculator/transline/microstrip.cpp, c_microstrip.cpp, coplanar.cpp, transline.cpp and units.h"; Here "…the microstrip, edge-coupled microstrip and grounded coplanar waveguide formulas ported to Python…"; its column layout kept.
  - `golden_antenna.json`: `"code": "e5469200427c76d82e9d2893363696ead16cf351",`, every other byte as it is (`git diff --stat` shows one line).
  - `cli.py`, after `_ends`: `_ends.__name__ = "REF.PAD:REF.PAD"  # argparse names a type in its error: invalid REF.PAD:REF.PAD value`.
- [ ] **Step 4: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_antenna.py -q`. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add NOTICE tests/fixtures/golden_antenna.json src/kicad_rf_studio/cli.py tests/test_repo.py tests/test_cli_si.py
git commit -m "fix: NOTICE names the coupled microstrip's KiCad source, golden_antenna's stamp names R-11's clean src tree, and argparse names REF.PAD:REF.PAD in its errors (plans 2 and 4's minors)"
graphify update .
```

---

### Task 12 [code]: One SI project through the window, opt-in, and its dry run on the fake

**Files:**
- Modify: `tests/test_gui.py` (after the Stage 3 acceptance); `README.md` (Development setup step 6 :295).

**Interfaces:**
- Consumes: Tasks 4 to 7's widgets and fields, Task 5's `TABLE_2D` and Task 7's `stamps`; Stage 3's harness (`fail`, `until`, `opened`, `grab`, `items`, `column`, `dispose`, `events`); `pipeline.si_result`, `pipeline.fingerprint`, `board_file`, `verified_si`.
- Produces: `SI_VALUES = {"R1": "24", "R2": "24"}`; `si_through(w, out, variant, say, monkeypatch, scd21) -> Path`; the opt-in `test_one_si_project_through_the_window_new_cost_run_retune_apply_verify_compare`, skipped unless `KRS_E2E_DIR` and `KRS_E2E_SI_VARIANT` (a verified plane-gap project.json) are set; `test_the_si_acceptance_runs_its_steps_on_the_fake`, tier (a).

- [ ] **Step 1: Write the tests,** in `tests/test_gui.py` after `test_one_antenna_project_through_the_window_…`:

```python
SI_VALUES = {"R1": "24", "R2": "24"}  # a typed 25 Ω snapped to E24, SI's default (ruling 3); plan 3 verified them


def si_through(w, out, variant, say, monkeypatch, scd21):
    """Stage 4 design 5.14 item 3 on the window `w`: New (the SI kind on a copy of usb2_hs in out/board: J1.3 to U1.3,
    usb2-hs, KiCad's pair rule, the victim TP1.1:TP2.1), Cost, Run, the retune (R1 and R2 typed 25, snapped to 24),
    Apply, Verify, then Compare against the verified `variant`, read only, its Scd21 resolved when `scd21` (the real
    run's; the fake's twin resolves nothing). Each step's lines go through say(step, begin, lines); validity lines are
    printed, never asserted. Returns the base's project file."""
    def ended(timeout):
        until(lambda: w.tick() or w.proc.poll() is not None, timeout=timeout)
        w.tick()

    def printed():  # what the terminal prints but its progress, as the CLI renders it
        return [render(e["code"], **e["params"]) for e in events(w.run_dir) if e["kind"] not in ("progress", "end")]

    vd = load_project(variant)
    watched = (variant.parent, Path(vd["results"]["run_dir"]), Path(vd["verify"]["run_dir"]))
    before = stamps(*watched)
    board, pj = out / "board" / "usb2_hs.kicad_pcb", out / "board" / "usb2_hs" / "project.json"
    board.parent.mkdir(parents=True)
    board.write_bytes((FIX / "usb2_hs.kicad_pcb").read_bytes())
    begin, f = time.monotonic(), w.new_form
    f.board.setText(str(board))
    w.board_chosen()
    w.pads_read.result(timeout=60)
    w.tick()
    f.kind.setCurrentIndex(f.kind.findData("si"))
    f.start.setCurrentText("J1.3")
    f.end.setCurrentText("U1.3")
    f.victims[0][0].setCurrentText("TP1.1")
    f.victims[0][1].setCurrentText("TP2.1")
    assert (f.interface.currentData(), f.pair.currentData(), f.preset.currentText()) == ("usb2-hs", "rule", "normal")
    f.create_button.click()
    made, notes = w.creating.result(timeout=120)
    assert made == pj
    w.tick()
    opened(w)
    assert w.project_status.text() == render("G_PROJECT_SI", path=str(pj.resolve()), interface="usb2-hs", target="90",
                                             start="J1.3", end="U1.3", preset="normal")
    assert pipeline.fingerprint(load_project(pj)) == pipeline.si_result(variant)["fingerprint"]  # before an hour goes
    grab(w, "e2e-usb2_hs-new")
    say("usb2_hs new", begin, [render(c, **p) for c, p in notes])
    begin = time.monotonic()
    w.cost_button.click()  # a fresh data folder calibrates this machine first
    ended(3600)
    assert w.cost_status.text() == render("G_END_DONE", exit_code=0), w.cost_status.text()
    codes = [e["code"] for e in events(w.run_dir, kind="cost")]
    assert codes[0] == "I_SI_2D_HEADER" and codes.index("I_SI_2D_PAIR") < codes.index("I_COST_TIME")
    assert "I_SI_COST_RING" in codes
    say("usb2_hs cost", begin, printed())
    opened(w)
    assert w.cost == w.run_dir and w.run_button.isEnabled()
    grab(w, "e2e-usb2_hs-cost")
    asked = []
    monkeypatch.setattr(w, "ask", lambda text: asked.append(text) or True)
    begin = time.monotonic()
    w.run_button.click()
    shown = [(e["code"], control.text(e["code"], e["params"])) for e in events(w.cost, kind="cost")]
    assert w.command == "run" and [text for code, text in shown if code == "I_COST_TIME"][0] in asked[0]
    assert not [text for code, text in shown if code in TABLE_2D and text in asked[0]]  # ruling 4: the table in Cost
    ended(12 * 3600)
    assert (w.end["params"]["exit_code"], w.run_status.text()) == (0, render("G_END_DONE", exit_code=0)), \
        w.run_status.text()
    (kept,) = events(w.run_dir, code="I_RESULTS")
    assert (kept["params"]["kept"], kept["params"]["runs"]) == (8, 8)
    say("usb2_hs run", begin, printed())
    grab(w, "e2e-usb2_hs-run")
    opened(w)
    r, begin = w.results, time.monotonic()
    assert column(r.parts, PART) == ["R1", "R2"]
    for k in (0, 1):
        r.parts.item(k, VALUE).setText("25")  # snapped to E24's 24
    assert column(r.parts, VALUE) == list(SI_VALUES.values()) and not r.what_if.isHidden()
    w.retuning.result(timeout=120)
    w.take_retune()
    w.tabs.setCurrentWidget(r)
    grab(w, "e2e-usb2_hs-retune")
    r.apply_button.click()
    code, lines = w.applying.result(timeout=300)
    w.tick()
    assert code == 0 and r.retune_status.text() == render("G_APPLIED", folder=str(pj.parent / "results"))
    assert {ref: q["value"] for ref, q in parts(load_project(pj)).items() if ref in SI_VALUES} == SI_VALUES
    say("usb2_hs retune", begin, lines)
    opened(w)
    begin = time.monotonic()
    r.verify_button.click()  # applied: verify starts at once
    assert w.command == "verify"
    ended(12 * 3600)
    assert (w.end["params"]["exit_code"], w.run_status.text()) == (0, render("G_END_DONE", exit_code=0)), \
        w.run_status.text()
    opened(w)
    assert load_project(pj)["verify"]["values"] == SI_VALUES and r.stale.isHidden()
    assert w.opened.verified[0][0] == "I_VERIFY_RESULTS"
    assert items(r.verify_lines) == [control.text(c, p) for c, p in w.opened.verified]
    say("usb2_hs verify", begin, printed())
    w.tabs.setCurrentWidget(r)  # verify's watch selected the Run tab
    grab(w, "e2e-usb2_hs-verify")
    begin = time.monotonic()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(variant), ""))
    w.comparison.variant_button.click()
    w.tick()
    w.comparison.compare_button.click()
    code, lines, cells = w.comparing.result(timeout=600)
    w.tick()
    assert code == 0 and w.comparison.table.rowCount() == len(cells) == 9
    assert (pj.parent / "compare" / "compare.png").is_file() and stamps(*watched) == before  # the variant read in place
    if scd21:  # design 5.14 item 3: the plane gap's mode conversion; its TDR row may go either way at 2.2 Ω
        assert (cells[5][0], cells[5][9]) == ("Scd21", render("T_RESOLVED"))
    say("compare", begin, [render(c, **p) for c, p in lines])
    w.tabs.setCurrentWidget(w.comparison)
    grab(w, "e2e-compare")
    return pj


# ponytail: run by hand only; its body runs in the suite on the fake (test_the_si_acceptance_runs_its_steps_on_the_fake),
# so only the real workers' side can lag. Its setup copies Stage 3's real-run test's, which stays as Stage 3's exit
# record ran it
@pytest.mark.openems
@pytest.mark.skipif(not (os.environ.get("KRS_E2E_DIR") and os.environ.get("KRS_E2E_SI_VARIANT")),
                    reason="one SI project through the window (Stage 4 design 5.14 item 3): set KRS_E2E_DIR to an empty "
                    "folder outside the repository and KRS_E2E_SI_VARIANT to a verified plane-gap project.json")
def test_one_si_project_through_the_window_new_cost_run_retune_apply_verify_compare(qapp, monkeypatch):
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
    variant = Path(os.environ["KRS_E2E_SI_VARIANT"]).resolve()  # <VARIANT>/projects/<name>/project.json
    assert pipeline.si_result(variant)["source"] == "T_VERIFY"  # usable before an hour is spent
    vd = load_project(variant)
    assert (board_file(variant, vd).name, vd["verify"]["values"]) == ("usb2_hs_gap.kicad_pcb", SI_VALUES)
    masks = [(str(out), "<KRS_E2E_DIR>"), (str(variant.parents[2]), "<VARIANT>")]

    def say(step, begin, lines):  # the record and the README quote these: no machine path shows in them
        line = " | ".join(lines)
        for real, shown in masks:
            line = line.replace(real, shown)
        print(f"e2e {step}: {time.monotonic() - begin:.0f} s: {line}", flush=True)

    w = MainWindow()  # the real orchestrator (control.orchestrator)
    w.show()
    try:
        si_through(w, out, variant, say, monkeypatch, scd21=True)
        assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # design 4: the GUI process
    finally:
        dispose([w])  # a failed step leaves no run going


def test_the_si_acceptance_runs_its_steps_on_the_fake(window, tmp_path, monkeypatch):  # ruling 14, tier (a)
    monkeypatch.setenv("KRS_FAKE_CBOX", "6e-16")  # the detached verify's cell C, as verified_si patches it here
    variant = verified_si(tmp_path / "variant", monkeypatch, FIX / "usb2_hs_gap.kicad_pcb").resolve()
    assert pipeline.retune(variant, [f"{ref}={v}" for ref, v in SI_VALUES.items()], lambda c, p: None) == 0
    assert pipeline.verify(variant) == 0
    w = window()
    si_through(w, tmp_path / "e2e", variant, lambda *args: None, monkeypatch, scd21=False)
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui.py -q -k "si_project_through or si_acceptance" -rs`. Expected: the dry run PASSES and the real one is 1 skipped with its reason. Each step of the dry run already runs on the fake: usb2_hs's 8-port run and its verify on the network fake (`verified_si` and `test_verify_puts_an_si_lines_parts_in_the_grid_and_compares`, `tests/test_si_run.py`); the fake worker's setup writes the empty operator dump that verify needs for a project with part ports (`tests/fake_worker.py:94-95`); the detached verify reads its cell C from `KRS_FAKE_CBOX` (`tests/fake_cli.py`, as the window's verify tests at `tests/test_gui.py:1028` and `:1219` set it); and the window's SI cost, Results and retune are Task 5's.
- [ ] **Step 3: `README.md`,** Development setup step 6 gains, after the antenna's sentence: "One signal-integrity project through the GUI, `usb2_hs` at Normal run, retuned, verified and compared with a verified plane-gap project, runs with `KRS_E2E_DIR` set to an empty folder outside the repository and `KRS_E2E_SI_VARIANT` to that project's `project.json`: `python -X utf8 -m pytest tests/test_gui.py -k si_project_through -s`. It takes about usb2_hs's run plus its verify, about 1.5 h on the development PC, after the variant's own run, retune and verify by the command line."
- [ ] **Step 4: Full suite, the GUI tests in pt-BR, commit, graph.**

```bash
git add tests/test_gui.py README.md
git commit -m "test(gui): one SI project through the window, opt-in: New, Cost with its 2D table, Run, a snapped retune, Apply, Verify and a compare against a verified plane-gap variant read in place, and the same body on the fake (Stage 4 design 5.14 item 3)"
graphify update .
```

---

### Task 13 [run]: The tip, the release check and the plane-gap variant

The controller's. Each block is one PowerShell call from the repo root; a long one runs in the background, waited on. Never kill python.exe or openEMS by name: they may be the owner's. `<RUN>` is `$env:TEMP\krs-s4p5`.

- [ ] **Step 1: The tip.** The full suite in the background, then the GUI tests in pt-BR. Expected: all pass; record the counts and `git rev-parse HEAD:src` in the ledger.
- [ ] **Step 2: The fake-backed grabs in both languages.** If `$env:TEMP\krs-font\krs_font.py` is gone, write it again as Stage 2 plan 3's Task 7 Step 5 gives it whole (`docs/superpowers/plans/2026-10-28-stage2-plan3-kicad-button.md`). Then:

```powershell
$env:PYTHONPATH = "$env:TEMP\krs-font"
foreach ($lang in @("en", "pt_BR")) {
  $env:KRS_TEST_LANGUAGE = $lang; $env:KRS_GRAB_DIR = "$env:TEMP\krs-grabs-s4p5-$lang"
  .venv\Scripts\python.exe -m pytest tests/test_gui.py -q -p krs_font -k "si_project or si_retune or si_cost or makes_an_si or two_si or on_a_track or si_acceptance or fits_1200" }
Remove-Item Env:KRS_GRAB_DIR, Env:KRS_TEST_LANGUAGE, Env:PYTHONPATH
```

  Look at `si-results`, `si-advanced`, `si-cost`, `new-si`, `compare-si`, `handoff-si` and the `e2e-*` grabs in each folder with the Read tool: at 1200 × 800 every word is the catalog's, legible and unclipped; the three panels stand in one row, each readable and none upside down, under the title's three lines and no foot; New shows only the SI rows, the f_max and target fields greyed for a preset; Compare's table shows Sdd21, Scd21, NEXT and FEXT as symbols and its levels, skew and marks in the language. A defect is a fix in its owning task's file, test-first where a test can see it, its own `fix(gui): …` commit after the full suite and the GUI tests in pt-BR, then `graphify update .`. A 100 px assertion that fails only under `krs_font` is such a defect, the canvas in a scroll area its pre-authorized fix (Stage 3's open issue 2).
- [ ] **Step 3: The release check,** in the background: `.venv\Scripts\python.exe tools/release_check.py *> "$env:TEMP\krs-s4p5-release.log"`. Expected: exit 0 and seven PASS lines (build, install, gui, antenna, si, plugin, privacy), no NOTE line; plugin's PASS proves the longer G_BUTTON_ACTION meets KiCad 9.0.7's and 10.0.7's schemas.
- [ ] **Step 4: The variant's copy and pre-check A,** seconds, read-only on `<GATES>`: P4-F's gap project and its board copied keeping their relative path; the run still current for the copy's model; its recorded fingerprint against a fresh `new` of the committed usb2_hs differing only in the mesh's `d_fill` (A-57's fix came after P4-F).

```powershell
$run = Join-Path $env:TEMP "krs-s4p5"; $v = Join-Path $run "variant"; $g = Join-Path $HOME "krs-gates-si"
New-Item -ItemType Directory -Force (Join-Path $v "projects"), (Join-Path $v "boards") | Out-Null
Copy-Item -Recurse (Join-Path $g "projects\usb2_hs_gap-n2-dfill") (Join-Path $v "projects")
Copy-Item (Join-Path $g "boards\usb2_hs_gap.kicad_pcb") (Join-Path $v "boards")
$env:LOCALAPPDATA = Join-Path $v "data"; $env:XDG_DATA_HOME = $env:LOCALAPPDATA; $env:LANGUAGE = "en"
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"
$p = Join-Path $v "projects\usb2_hs_gap-n2-dfill\project.json"
.venv\Scripts\python.exe -X utf8 -c "import sys; from pathlib import Path; from kicad_rf_studio import cli, pipeline; from kicad_rf_studio.core.project import board_file, load_project; p = Path(sys.argv[1]); d, b, geom, _ = pipeline.load(p); pipeline.results_of(d, pipeline.build_model(d, b, geom)); rec = d['results']['fingerprint']; new = pipeline.fingerprint(load_project(cli.new_si('tests/fixtures/usb2_hs.kicad_pcb', 'J1.3', 'U1.3', 'usb2-hs', pair=True, victims=[('TP1.1', 'TP2.1')], output=Path(sys.argv[2]))[0])); print(board_file(p, d).name, sorted(k for k in new if new[k] != rec.get(k)), {k: x for k, x in new['mesh'].items() if rec['mesh'].get(k) != x}, 'verify' in d)" $p (Join-Path $run "fresh-a")
```

  Expected: `usb2_hs_gap.kicad_pcb ['mesh'] {'d_fill': True} False`. A call's variables and environment do not persist: every later call of this task starts with this block's `$run`, `$v`, `$p` and environment lines, never its two copies. Its board is byte for byte `tests/fixtures/usb2_hs_gap.kicad_pcb` (sha256 `e009559b…`). A traceback with E_RESULTS_STALE (the gap's model hash moved), or other fields, is the fallback (Step 5's last block), recorded as a deviation.
- [ ] **Step 5: The variant's retune and verify.** First tell the owner, in pt-BR: "Vou executar agora a verificação da variante com gap no plano (cerca de 3.6 a 4.5 h, uns 3 GB de RAM no pico; preciso de 14 GB livres para começar). Se puder, feche programas pesados até ela terminar." Then, each its own call with the environment of Step 4: the retune, seconds, in the foreground:

```powershell
.venv\Scripts\python.exe -X utf8 -m kicad_rf_studio retune $p R1=24 R2=24 *> (Join-Path $run "variant-retune.log")
```

  then the verify, in the background, the floor first:

```powershell
$free = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
if ($free -lt 14) { "free RAM $free GB, under the 14 GB floor: not started"; exit 9 }
"src $(git rev-parse HEAD:src)" > (Join-Path $run "variant-verify.log")
.venv\Scripts\python.exe -X utf8 -m kicad_rf_studio verify $p *>> (Join-Path $run "variant-verify.log")
```

  Expected: both exit 0; verify calibrates its fresh data folder first (about 25 s), then 6 of 6 jobs keep S near 23 ns (plan 3's at λ/40: 2 h 35 min), its lines I_VERIFY_RESULTS, I_SI_RELATIVE, I_VERIFY_COMPARE_SI and the levels; a W_RECIPROCITY or W_PASSIVITY is a stated limit (R-12's tie), recorded, not a failure. A floor that does not hold waits and starts again once it holds; a floor is never lowered. A reaped block is reported and restarted only on the owner's word: `verify` does not resume a folder, so it starts over.
  **Fallback** (pre-check A failed, or B below finds the run stale), recorded as a deviation, +4.4–5.8 h: on a fresh `<VARIANT>` (`Remove-Item -Recurse -Force $v` first, then its `projects` and `boards` folders made again), `Copy-Item tests\fixtures\usb2_hs_gap.kicad_pcb (Join-Path $v "boards")`, then `new` into `(Join-Path $v "projects\usb2_hs_gap")` with the tutorial's arguments, `cost`, `run` (in the background, at the floor, after the owner's warning), `retune … R1=24 R2=24` and `verify` as above; `$p` is then that project's project.json.
- [ ] **Step 6: Pre-check B,** seconds, right before Task 14:

```powershell
.venv\Scripts\python.exe -X utf8 -c "import sys; from pathlib import Path; from kicad_rf_studio import cli, pipeline; from kicad_rf_studio.core.project import board_file, load_project; p = Path(sys.argv[1]); v, d = pipeline.si_result(p), load_project(p); new = pipeline.fingerprint(load_project(cli.new_si('tests/fixtures/usb2_hs.kicad_pcb', 'J1.3', 'U1.3', 'usb2-hs', pair=True, victims=[('TP1.1', 'TP2.1')], output=Path(sys.argv[2]))[0])); print(v['source'], board_file(p, d).name, d['verify']['values'], 'same settings' if v['fingerprint'] == new else sorted(k for k in new if new[k] != v['fingerprint'].get(k)))" $p (Join-Path $run "fresh-b")
```

  with Step 4's environment. Expected: `T_VERIFY usb2_hs_gap.kicad_pcb {'R1': '24', 'R2': '24'} same settings`.

---

### Task 14 [run]: The acceptance run through the window

- [ ] **Step 1: The run** (§5.14 item 3). Tell the owner in pt-BR first: "Vou executar agora o teste de aceitação pela janela (cerca de 1.2 a 1.6 h, uns 3 GB de RAM no pico; preciso de 14 GB livres para começar)." Then, in the background, after Task 13 Step 5's floor lines:

```powershell
$run = Join-Path $env:TEMP "krs-s4p5"; $e2e = Join-Path $run "e2e"
Remove-Item -Recurse -Force $e2e -ErrorAction SilentlyContinue
$env:KRS_E2E_DIR = $e2e; $env:KRS_E2E_SI_VARIANT = Join-Path $run "variant\projects\usb2_hs_gap-n2-dfill\project.json"
$env:PYTHONPATH = "$env:TEMP\krs-font"; $env:CSXCAD_INSTALL_PATH = "<openEMS folder>"
"src $(git rev-parse HEAD:src)" > (Join-Path $run "e2e.log")
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_gui.py -k si_project_through -s -q -p krs_font *>> (Join-Path $run "e2e.log")
```

  On the fallback, `KRS_E2E_SI_VARIANT` names `variant\projects\usb2_hs_gap\project.json`. `tests/conftest.py` sets `LANGUAGE=en` for the test and every process it starts, so the e2e lines are English (ruling 11). Expected at the end: `1 passed`, after `e2e usb2_hs new`, `cost`, `run`, `retune`, `verify` and `e2e compare`, with `<KRS_E2E_DIR>` and `<VARIANT>` for the folders. Soft expectations, reported and never failed on: the run's 8 jobs near 3.07 ns in about 39–49 min (P4-F: 39 min at four at once); verify 29–38 min; compare: Scd21 about +17.7 dB, NEXT about +6.4 dB and FEXT about +7.8 dB resolved (P4-F's run chain), the highest TDR level's delta near +2.06 to +2.21 Ω either side of 2.2 Ω. `1 skipped` means openEMS did not import: check `CSXCAD_INSTALL_PATH`. To stop it, only the app's own STOP in the newest folder of `$e2e\data\kicad-rf-studio\runs`. After a reaped pytest the detached orchestrator may outlive it, holding the project lock and the CPU: STOP it the same way, or kill it by the PID that `runs.lock_holder(<the base's project.json>)` names; restart only on the owner's word, into an empty `KRS_E2E_DIR`.
- [ ] **Step 2: The grabs,** `$e2e\grabs`, with the Read tool: `e2e-usb2_hs-new` (the SI kind, usb2-hs, KiCad's rule, TP1.1 and TP2.1, Normal), `-cost` (the 2D table's rows then the estimate, Run… enabled), `-run` (P1 to P6, R1 and R2 with their verdicts, Finished (exit code 0)), `-retune` (24 and 24; the three panels under the relative and what-if lines), `-verify` (Results: the stale indicator hidden, verify's lines beside), `e2e-compare` (the lines, the ten-column table with its symbols, marks and verdicts, the overlays). Record the run's validity lines as printed.
- [ ] **Step 3: Fix what fails, and the rerun rule.** Each defect is a [code] fix in its owning task's file, test-first where a test can see it, committed as `fix(...)` after the full suite and the GUI tests in pt-BR, then `graphify update .`. A fix under `src/` but a message's wording (`core/messages.py` and the `.mo`) runs Task 13's pre-check B and Step 1 again (about 1.5 h). A fix that moves the SI model spec's hash, `__version__` or a fingerprint input makes pre-check B fail: Task 13 Steps 4 to 6 again, or their fallback, then Step 1. Any other fix reruns nothing, and the record names the product code id the run ran at.

---

### Task 15 [doc]: The README's excerpts

- [ ] **Step 1:** After each command fence of the Signal-integrity tutorial, a fence of that step's lines from `<RUN>\e2e.log`, its ` | ` separators as line breaks and its folders as the tutorial writes them: `<KRS_E2E_DIR>\board\usb2_hs\compare` as `compare` (replaced first), `<KRS_E2E_DIR>\board\usb2_hs` as `usb2_hs`, `<VARIANT>\projects\usb2_hs_gap-n2-dfill` (or the fallback's `usb2_hs_gap`) as `usb2_hs_gap`, and every run's folder as `<run folder>`; no other placeholder. new: I_STACKUP, I_CLASSES, I_SI_INTERFACE, I_SI_PAIR, both I_CHAIN, I_SI_VICTIM, the ports, I_SI_DEFAULTS and I_WROTE; cost: the 2D table's rows, the cells, dt, I_COST_TIME, I_SI_COST_JOBS, I_SI_COST_RING, the RAM and the main cost; run: the eight verdicts, I_RESULTS, I_BASIS, the indicators and the SI lines; retune: the SI lines and the what-if line; verify: I_VERIFY_RESULTS, I_VERIFY_COMPARE_SI, the levels and I_VERIFY_SCOPE_SI; compare, after the five-command block: the TDR, insertion, worst, skew and crosstalk lines, the thresholds and I_OUTPUTS. Each step's time from its `e2e` line follows its command, as the Tutorial does; the compare block says compare's own time, the gap's run time P4-F's (4 h 25 min, `docs/validation/2026-11-08-p4-f.md`) and its verify's Task 13 Step 5's, its new and retune seconds; on the fallback, the gap's own times. The second paragraph's `<date>` becomes the exit record's.
- [ ] **Step 2:** `.venv/Scripts/python -m pytest tests/test_repo.py -q` passes; reuse the last green suite (docs only); commit `docs(readme): the signal-integrity tutorial's excerpts and times, from the acceptance run (Stage 4 design 5.12 item 5)`; `graphify update .`.

---

### Task 16 [doc]: Amendments A-65 to A-69

- [ ] **Step 1: The Stage 1 spec,** each paragraph tagged as given:
  - **A-65, §3.2,** after "Stage 2's GUI calls the same functions…": "**Signal integrity in the GUI** (Stage 4): New makes an SI project through `new --interface`'s own function, with the interface (the presets, or Custom with its f_max and target), the pair (none, KiCad's rule or its two end pads picked) and up to two victims; the Cost tab lists the 2D table before the estimate, which Run…'s confirmation leaves out; Results shows the reading and lines that `run` and `retune` print (one function, `si_view`, serves both): the TDR with its target band, the mixed-mode S (a net's S21 and S11) and the crosstalk, the stated limits in its lines and no |S| panel stretched under −100 dB by an exact zero. Every SI part port snaps to E24 by default. An SI retune's chain update and reading took 68 ms on the USB 2.0 fixture in memory (scikit-rf's Circuit and se2gmm), so it runs on a thread of its own and the GUI thread only moves the curves and blits them (Stage 2 design §2 goal 4); v1's and the antenna's stay on the GUI thread. Compare compares two SI projects into the base's own folder, its table in the window's words; Advanced shows an SI project's defaults and units. (A-65, Stage 4 plan 5: controller recommendation, owner unavailable.)"
  - **A-66, §4.6,** at its end: "**The KiCad button's line** (Stage 4; it amends the Stage 4 design's §5.10): a selected track, arc or via (kicad-python's KOT_PCB_TRACE, KOT_PCB_ARC and KOT_PCB_VIA, handed over by KIID as `tracks`) names its net, taken on its pair's P side when KiCad's pair rule or the DP/DM alias makes it the N side. "The net" is the line this walk reaches from it through its two-pad parts, since the literal net pre-fills no fixture, and its end pads are the selected pads on that line (an N leg's two taken to the P side), else the copper pads on it of connectors and of footprints with three or more copper pads (choose_reference's rule). Exactly two pre-fill New's start and end, the connector's first, as every SI project the repo makes runs; any other count is named in New's status line and the user picks: on the USB 2.0 fixture the ESD array's pads make four, and no flow-through rule drops them. New's interface is fitted to the line, se50 for a single net under a pair's preset and usb2-hs for a pair under se50, Custom kept, and its pair follows the partner. Ground, power and netless tracks are dropped, tracks of two lines name both, and the pickers list every pad with copper, whatever footprints are selected. A selected pair of pads keeps the chain's pre-fill. (A-66, Stage 4 plan 5: controller recommendation, owner unavailable.)"
  - **A-67, §3.2,** the "Signal-integrity results" paragraph, after A-57's tag: "compare reads each SI project at its current target, marker and link rise time, as Results shows them, none of which the model spec holds (an edit of them leaves the results current), and refuses two projects that differ in any of them (E_COMPARE_SETTINGS names it); the tolerance takes no part, since no delta reads it. (A-67, Stage 4 plan 5: controller recommendation, owner unavailable.)"
  - **A-68, §7.8,** at its end: "An SI project's lines never share a net: `new` refuses it (E_SI_LINE_SHARED), and so does the project file's check (E_PROJECT_FIELD on lines), so neither a hand edit nor Advanced's Save stores one. (A-68, Stage 4 plan 5: controller recommendation, owner unavailable.)"
  - **A-69, §9.1 (d):** "…the offscreen GUI smoke test, `new --antenna` and `new --interface` on the release's own 2.4 GHz antenna and USB 2.0 fixtures (schema 2; schema 3 with its 8 ports), `plugin.json` against…", the tag "(A-69, Stage 4 plan 5: controller recommendation, owner unavailable.)" after A-20's.
  - The Status line gains "On <date>, Stage 4's plan 5 amended §3.2, §4.6, §7.8 and §9.1 (A-65 to A-69) the same way."
- [ ] **Step 2:** `.venv/Scripts/python -m pytest tests/test_repo.py -q` passes; commit `docs(spec): A-65 to A-69, the GUI for SI, the button's line, compare at current values, one net a line and the release check's new steps (Stage 4 plan 5; controller recommendation, owner unavailable)`; `graphify update .`.

---

### Task 17 [doc]: The Stage 4 exit record and the close

- [ ] **Step 1: The exit record,** `docs/validation/<date>-stage4-exit.md`, `<date>` the day it is written, after Stage 3's, Markdown only, no machine path (`<KRS_E2E_DIR>`, `<VARIANT>`, `<GATES>`, `<RUN>`, `<openEMS folder>`):
  1. **Verdict:** one bold line (Stage 4 done or not by design §5.14), then one table, a row per item: 1, the five plans merged (plans 1 to 4 at `8e758b3`, `3a5a610`, `155652c`, `5302aae`; plan 5 fast-forward after this record) and the suite green in English and the GUI tests in pt-BR (Task 13 Step 1's counts, or the last run's); 2, the gates (section 3); 3, the acceptance run (below); 4, the owner's items (section 8). Then item 3's subsection: the e2e log as printed (its `src <id>` line first), a bullet per step (Cost: its 2D table, I_SI_COST_RING, the calibration; Run: 8 of 8, its confirmation without the 2D table; the retune and its snap, 25 to 24; Apply; Verify: its values, |ΔS|, the levels; Compare: the resolved rows, both basis lines, the variant's files unchanged), the grabs (Task 14 Step 2), the validity lines as printed (a crossing is a stated limit, R-12's tie), the soft check against P4-F, openEMS absent from the GUI process.
  2. **Inputs:** the branch, its HEAD and product code id; a table of plans 1 to 5 (scope, commits: 14, 16, 12, 33 and plan 5's, merge commit, the suite there: plan 4's 2446 passed, 6 skipped, pt-BR GUI 42 passed, 3 skipped); the designs; the git-ignored archives (`.superpowers/sdd/2026-11-0*-stage4-plan*-rulings-and-minors.md` and plan 5's); the evidence deleted afterwards (`<RUN>`: the e2e folder, the variant, the grabs and logs, their sizes first).
  3. **The gates,** one row each: P4-A pass (36 of 50 rows gated; KiCad's calculator recorded, not gated); P4-B fallback (all 20 checks pass, n 2, p4b_ms100_45 +5.35 % a miss with B3′ declined: the 45° rule the owner's, W_STAIRCASED a warning; the cut victim's refusal kept; R-8 to R-10); P4-C fallback (the d fill stays, max_cell_mm null; λ/40 |ΔS| 0.0130/0.0326 against 0.01; the step lines pass); P4-D "fail on one invalid run, the tall coupon's horizontal port, by R-12's current-probe tie, its fallbacks in force: the vertical port kept, lossless the default" (the DC point within 2.1e-4; Debye +5.5 to 24.3 % and w 108.8); P4-E widened (DIFF_OHM 2.2 Ω, SE_OHM 1.1 Ω, IL_DB 0.05 dB, SKEW_PS 1 ps; DB 0.5 dB and Scd21's floor −37.7 dB by R-13); P4-F pass (the neck +7.14 Ω against 6.6 Ω, 1.08×; the gap's Scd21 +17.67 dB); the refit (SI_SPEED 0.663, DEBYE_WEIGHT 108.8, A-62); P4-G the owner's (A-64). Machine hours: about 46 h (P4-B 18.2, P4-C 4.52, P4-D 11.59, P4-E 6.00, P4-F 5.78).
  4. **The release check, run locally:** Task 13 Step 3's seven lines as printed, its wall time.
  5. **The README's SI tutorial:** its excerpts are the acceptance run's; the gap's run time P4-F's, its verify time Task 13's; the same commands' CLI path is `docs/validation/2026-11-04-si-results.md`'s, at λ/40.
  6. **Stated limits and deviations:** the variant (P4-F's run at product code `e546920`, verified at plan 5's, or the fallback); Normal; the what-if label (P0-C the owner's); P4-D explained; verify's ideal 24 Ω parts against the 0402 package models; the highest TDR row near 2.2 Ω; the reciprocity margin (P4-F's 0.0153–0.0187 against 0.02) and the acceptance's own figures; the SI retune off the GUI thread (68 ms measured); the −100 dB floor in the window only, the PNGs' −300 dB stretch kept (ruling 18), and a window panel whose curves all lie under −100 dB autoscaled; the loss lines after an edited marker_hz name the new marker but hold the run's estimate (plan 3's); then one line per known limit and deferred minor of plans 1 to 5's ledgers, as Stage 3's §6 lists them, the minors fixed later left out.
  7. **Machine time:** per step, the estimate printed before it against the measured time; the release check's wall time; Stage 4's total: the first run (26 min), plan 3's results runs (`2026-11-04-si-results.md` §8), the gates (about 46 h), the variant's preparation and the acceptance.
  8. **Next step, the owner's items,** one table (item | default this work applied | what it gates), each a controller recommendation, owner unavailable, deduplicated and grouped:
     - **Carried from Stages 1 to 3:** the first push and its identity rewrite (none done); the deny-list review; P0-C ("do not start"); A-9 and A-10 (not started; the what-if label stays); RFsim and NOTICE; the click-through on KiCad 9.0.7 and 10.x, now with a track, arc or via (does GetSelection honour the type filter; does Select Connected also select pads; about 2 min, non-blocking); the plugin identifier `org.kicadrfstudio.app`; the review of A-13 to A-40; the native review of `po/pt_BR.po` with Stage 4's terms (perna, diafonia, skew intrapar, trecho, comprimento de resolução, tangente de perdas, teto, resíduo nas portas, aproxima em degraus, campo, pontas); Linux and the workflows after the push; the golden pins bound to this PC, golden_si among them; P3-F; one row for the rest of Stage 2's §7, citing `docs/validation/2026-10-29-stage2-exit.md` §7.
     - **Design §7's defaults, as designed:** the first interfaces (USB 2.0 HS, a QSPI clock); the presets at 10 GHz; the two TDRs; lossless (P4-D); the dt floor 0.6; a perfect conductor with loss lines; the selected region kept; no masks, IBIS or ideal driver; EMC later; ESD arrays and chokes as stated limits; net classes not read; runtime shown, never promised; 45° warned (the rule the owner's); stripline as a reference; the thresholds as P4-E widened them; EMerge (P4-G) optional.
     - **Amendments A-41 to A-69,** each a controller recommendation: A-41 to A-47 (plan 1), A-48 to A-53 (plan 2), A-54 to A-57 (plan 3), A-58 to A-64 (plan 4), A-65 to A-69 (plan 5).
     - **Plans 1 to 3:** P4-A's deviations (Cohn at 0.1 µm; Kirschning–Jansen at 35 µm gated only where t/h ≤ 0.035; εeff and the 0.2 mm stack recorded; the even/odd 4-port in tools; the vertical port to the nearest plane past bare layers); the fixtures' redesign (four layers, a 0.25 mm gap, a 0.33 mm line); E_SI_LINE_SHARED and E_RETUNE_SI; R6-1; an ESD array joined only inside its package and bridging a multi-pad part's same-net pads (not modelled); the short-feature rule (kept; P4-F's true positive); the SI fingerprint's fields (max_cell's value out, d_fill and lid in); the four msgid changes; R8-1, superseded by the ring rule.
     - **Plan 4 and the gates,** each with no product change, a fix that moves pins waiting for a plan that records them: the 45° rule (B3′ about 3.9 h expected, 8.7 h worst); the probe-node tie (R-5); the lumped port's current-probe tie (R-12), which sets usb2_hs's reciprocity margin; choose_reference's float tie (R-9); the ground-signal launch's FEXT (R-10); under-stitched planes ringing under lossless (R-8; κ at the band's centre the option); Debye (a faster update, Debye only where the field is, the isolation twin, the accuracy miss's cause); the d fill coarser than λ/40 on thick boards (R-11); arc-vertex mesh lines and a symmetric pair mesh (a lower DIFF_OHM and Scd21 noise); a null on the victim coupon; Scd21 near its floor; shared mesh lines; a refinement around launches and corners; MB_PER_MCELL 170, provisional; a speed for each pool; a launch criterion for the vertical port; clean()'s description dependence (R-4); the two rows that do not resolve at Task 16's thresholds; the neck's 1.08× margin.
     - **New in plan 5:** the variant from P4-F's gap run read in place (or the fallback); the acceptance at Normal; `<GATES>` (krs-gates-si) kept, its deletion the owner's; the SI retune off the GUI thread; the −100 dB floor in the window only, read as 40 dB under a panel's top at least (open issue: ruling 1's literal floor inverted an all-under −100 dB panel); a press fitting New's interface to its line (se50 for a single net, usb2-hs for a pair under se50, Custom kept), New's default usb2-hs; the SI pre-fill's connector first, v1's last; one G_SI_ENDS_HALF for a half victim or partner; Compare's symbols untranslated, its marks translated; the button's walk (A-66), no ESD flow-through rule, the N side P-normalised, an N leg's selected ends taken to the P side, the handoff's `tracks` key, the tooltip after `install-kicad-plugin` runs again; compare at current values (A-67); one net a line (A-68); W_STAIRCASED_SI's wording ("not decided yet" for the owner's 45° rule); the link TDT not drawn (in si_tdr.csv); the loss lines after an edited marker_hz.
     Then: plan 5's local fast-forward merge with its branch deleted, nothing pushed; `<RUN>` deleted on the controller's go after it, its sizes recorded; `<GATES>` kept.
- [ ] **Step 2: The design's Status line,** `docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md`, gains at its end: "Stage 4 closed on `<date>` with plan 5's GUI, button and docs (exit record `docs/validation/<date>-stage4-exit.md`)."
- [ ] **Step 3: Commit,** the last green suite reused (docs only):

```bash
git add docs/validation docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md
git commit -m "docs(validation): the Stage 4 exit record: design 5.14's four items with their evidence, the acceptance run through the window, the machine time and the owner's items"
graphify update .
```

- [ ] **Step 4: Close.** The whole-branch review; after any later commit, the suites again and the record's sections 1 and 2 brought up to date; then the local fast-forward merge into `main` and the branch deleted. Nothing is pushed. Then `<RUN>`, the grab folders and the logs deleted, their sizes recorded first; `<GATES>` stays.

---

## Not in this plan

- **A per-pool SI speed:** the owner's (plan 4's refit, `docs/validation/2026-11-08-p4-refit.md`); I_SI_COST_SPEED says a pool-2 run is priced about 1.9 times long, on the safe side, until a run refreshes its level.
- **The 45° rule:** the owner's (P4-B fallback, B3′ declined); W_STAIRCASED_SI states P4-B's twins and leaves the run going.
- **P4-G, EMerge as a second solver:** the owner's (design §5.11, A-64).
- **The owner's gate items** (R-4, R-5, R-8 to R-12, the Debye twin, shared mesh lines, MB_PER_MCELL, a launch criterion): each would move pins; the exit record lists them with their defaults.
- **The link TDT's panel:** not drawn; it stays in `si_tdr.csv`, and the skew line gives the arrivals (ruling 2).
- **The −100 dB floor in the CLI's PNGs:** `si_summary.png` and `compare.png` keep their bytes (ruling 18); an exact zero still stretches their |S| axis to −300 dB.
- **One marker frequency for the loss and S lines:** each line keeps naming its own (plan 3's ruling); usb2-hs's 240 MHz lies on the grid.
- **The loss lines after an edited marker_hz:** they name the current marker but hold the run's estimate, computed at the run's marker (plan 3's route); a run, or a recomputation from the board (1.7 s), would fix it.
- **An ESD flow-through rule for the button:** none (ruling 9); the status line names the four candidates and the user picks them, or selects the two end pads with a track (a `ponytail:` in `si_candidates`).
- **The real-KiCad click-through with tracks, arcs and vias** on KiCad 9.0.7 and 10.x: the owner's.
- **A live partner preview in New:** none (ruling 6); new's I_SI_PAIR note and G_SI_PARTNER cover it.
- **A widget for the 2D table:** the Cost tab's sentences (ruling 4).
- **The release check's cost, fake worker or SI GUI step:** none (ruling 12); the GUI step's smoke builds the window with the SI rows.
- **The overlays on a canvas in Compare:** compare.png at its own size, as Stage 3.
- **A window test of a single net's Results:** no window code is a net's own; Task 1 pins draw_si's and retrace_si's net figure, and Task 9's window test creates qspi_clk's project.

## Controller rulings (2026-11-08; binding)

The controller's nineteen rulings stand as given, but where a ruling of the architect's below reads one with its stated reason; the architect's follow, as the four reviews revised them (a revision names its finding). Each is a controller recommendation made while the owner is unavailable.

- Ruling 1 (the controller's): the GUI opens SI projects: G_SI_LATER goes; a pure `pipeline.si_view(project, res) -> (Reading, lines)` out of write_outputs serves write_outputs, open_project and retuned, the CLI's outputs unchanged, `ChainResults.reading` added; show_project's G_PROJECT_SI; draw_si(gui=True) without the foot, the limits in the lines; no |S| bottom under −100 dB; retrace_si moves the curves and level markers in place at fixed limits and the window blits; the 50 ms rule tested as the existing timing test does — design §5.10, r1 — cost if wrong: a second figure path.
- Ruling 2 (the controller's): Results for SI: the link TDT not drawn; each line names its own frequency; I_SI_NO_LOSS in W_NO_SECTIONS' place; W_JOB_T_MAX reworded with no new code; the short marks follow DIFF_OHM and SE_OHM — plan 3's and 4's deferred items — cost if wrong: a few lines.
- Ruling 3 (the controller's): E24 for every SI part port (25 → 24 in E24, 27 in E12; 0R and open kept, the R rows in the snapping test); verify_stale reads SI bypasses; retuned through si_view on the stored layout — plan 3's Not in this plan — cost if wrong: a wrong stale mark.
- Ruling 4 (the controller's): the 2D table stays sentences in Cost; Run…'s confirmation leaves out I_SI_2D_*, W_2D_SHORT and I_SI_SHORT_ROUTE; I_SI_COST_SPEED reworded (any run refreshes the level; pool 2 priced about 1.9× high) — plan 4's Close — cost if wrong: one dialog.
- Ruling 5 (the controller's): Compare for SI: symbols, new codes for the TDR levels and the skew, digits by quantity, the marks translated; compare reads current target_ohm, marker_hz and rise_s and refuses differing ones (E_COMPARE_SETTINGS); G_COMPARE_KIND, G_COMPARE_NO_RESULT and the three G_RETUNE_* reworded for both kinds; never the variant's folder; a d-fill against a set-cell project refused — plan 3's deferred item — cost if wrong: one refusal.
- Ruling 6 (the controller's): New's SI kind with only the active kind's rows, the interface combo with Custom's fields, the pair's three modes, two victim rows, `cli.new_si` submitted as `cli.new` is, no live preview, G_ wordings for the reachable E_SI_*, control.text mapping I_SI_PAIR's how, the 1200 × 800 test in both languages — design §5.10 — cost if wrong: a row.
- Ruling 7 (the controller's): check_project refuses two lines on one net (T_EXPECT_SI_OWN_NETS) — plan 2's item — cost if wrong: one check.
- Ruling 8 (the controller's): Advanced for SI: the preset's defaults (none for Custom), SI_TOLERANCE, SI_DIELECTRIC, max_cell_mm's null, the units, kind and schema hidden — r1 — cost if wrong: a column.
- Ruling 9 (the controller's): the button takes tracks, arcs and vias as `tracks`, fake_kicad honours the types; the walk amends design §5.10 (A-66): si_candidates and p_side; Handed's net and partner; r2's edge cases; no ESD heuristic; pads keep v1; G_BUTTON_ACTION and G_HANDOFF_UNSAVED reworded; the README's reinstall note; the click-through the owner's — r2 — cost if wrong: a press that pre-fills nothing.
- Ruling 10 (the controller's): every new or changed message a CATALOG code with its msgstr; no terminal syntax in GUI wordings; the GUI tests in pt-BR — pt-BR design — cost if wrong: a msgstr.
- Ruling 11 (the controller's): the README's "## Signal-integrity tutorial" after the antenna's, on the committed fixtures, with its commands, its excerpts from the acceptance run in English, its limits list, its prose independent of the gap's TDR row, pinned by test_repo; Install's and Development setup's sentences — design §5.12 item 5 — cost if wrong: a paragraph.
- Ruling 12 (the controller's): the release check's si step on usb2_hs from source.zip, schema 3, kind si, 8 ports; no cost, fake worker or GUI step — r3 — cost if wrong: one step.
- Ruling 13 (the controller's): NOTICE names c_microstrip.cpp; golden_antenna's stamp e5469200427c76d82e9d2893363696ead16cf351 with a 40-hex test; _ends' readable name; W_STAIRCASED's SI variant with P4-B's twins — r3 — cost if wrong: none.
- Ruling 14 (the controller's): the opt-in acceptance test (§5.14 item 3) with Stage 3's harness, its steps and checks, validity printed never asserted, grabs under KRS_E2E_DIR, no openEMS in the GUI process, and a fake-backed dry run of the same body in tier (a) — r4 — cost if wrong: a rerun.
- Ruling 15 (the controller's): P4-F's gap run reused: copied with its board, its own fresh data folder, a read-only pre-check, then the CLI's retune and verify at 14 GB free (3.6–4.5 h); the fallback +4.4–5.8 h as a deviation; then the window (1.2–1.6 h), pt-BR warnings first, r4's rerun rule — r4 — cost if wrong: about 4 h.
- Ruling 16 (the controller's): the Stage 4 exit record after Stage 3's, with §5.14's items (the gates as stated), the acceptance and machine time, the owner's items from plans 1 to 5 with A-41 to the last amendment; the design's Status line; krs-gates-si kept, its deletion the owner's — design §5.14 item 4 — cost if wrong: none.
- Ruling 17 (the controller's): amendments from A-65 on in the Stage 1 spec, tagged — design §5.13 — cost if wrong: a paragraph.
- Ruling 18 (the controller's): no product default changes; the golden models and outputs unchanged but golden_antenna's stamp; the CLI's outputs unchanged but the listed refusal and wordings — design §3 — cost if wrong: a pin.
- Ruling 19 (the controller's): the order: refactors and guards, control, the window, New, Compare, the button, docs and small fixes, the acceptance test, the [run] tasks, then the excerpts, the amendments and the record — cost if wrong: a reorder.
- Ruling (measured; reads ruling 1): an SI retune runs on a one-thread executor of the window's own (`tuner`), polled every 20 ms; the GUI thread only submits it and, at its end, retraces and blits — `control.retuned` took 68 ms in memory on usb2_hs's 8-port layout (chain_results 39 ms: scikit-rf's Circuit 28 ms, the layout's indicators 11 ms; read 29 ms: se2gmm 26 ms), the validated functions the CLI shares, so on the GUI thread it would break Stage 2's goal 4 by construction; v1's and the antenna's stay synchronous, their tests unchanged — cost if wrong: about 25 lines and one executor.
- Ruling: the latest SI retune wins: `retuning` names it, an older one is cancelled if not begun and never shown, and open_project, show_project and revert drop the one in flight; the window's own `tune_timer` takes it, which Task 5 checks once with no direct `take_retune` (finding 2) — Review Focus 1, 2 — cost if wrong: one stale frame, or an edit never drawn.
- Ruling (reads ruling 1 with ruling 18): the −100 dB floor applies with `gui=True` alone, so si_summary.png and compare.png keep their bytes, which Task 1's guard (draw_si's |S| curves by symbol) and digests (si_png before and after) check (finding 22) — ruling 18's list, with rulings 7's and 13's own changes, is exhaustive (finding 23) — cost if wrong: one condition.
- Ruling (reads ruling 1; finding 9): the window's floor is `max(lo, min(−100, hi − 40))`: −100 dB at the lowest on an |S| panel whose top lies above −60 dB, else 40 dB under its top, so a panel whose curves all lie under −100 dB keeps its autoscale; ruling 1's literal "no |S| bottom under −100 dB" turned such a panel upside down (probed: the network fake's exact-zero crosstalk (−316.5, −283.5) became (−100, −283.5), a −130 dB victim (−100, −132.5)), so Tasks 1 and 5 assert no axis inverted — open issue 1 — cost if wrong: one line.
- Ruling: retrace_si returns None when the reading holds another count of levels than drawn, and show_chain then draws in full; `SYMBOLS` serves draw_si and retrace_si, which keeps ruling 1's `retrace_si(axes, reading)` (finding 22's project argument not taken); Task 1 pins it on a pair and on a net (finding 3) — ponytail — cost if wrong: a rare 0.2–0.4 s draw.
- Ruling: si_view without a chain gives (None, res.lines), and retuned's refusal sets `reading=None`, so a refused edit never shows the stored reading — ruling 1 — cost if wrong: none.
- Ruling (revision): Task 5's retune checks read Scc21 (`axes[1].lines[2]`, `m[:, 3, 2]`), not Sdd21: on the network fake Sdd21, Scd21, NEXT and FEXT are exact zeros that no retune moves, so an Sdd21 check passes on any reading, while R1 and R2 move Scc21 by 0.1 to 1.6 dB (probed on the feasibility critic's run) — Review Focus 1, 2 — cost if wrong: a test that cannot fail.
- Ruling: `SI_READ_AT` is overlaid on the record's fingerprint in `si_result`; the tolerance stays out (no delta reads it; compare.png draws the base's band alone); test_si_compare's refusal test now edits the current target, since the record's no longer counts — ruling 5 — cost if wrong: one key.
- Ruling: `control.cells` comes out of `control.compare`, so the "short" mark and the rounding are tested on hand rows (the network fake reads no level); its quantity is the symbol si_delta_lines writes (`q.upper()`, `q.removesuffix("_worst").capitalize()`), with no `control.SYMBOLS` beside core.post.si's (finding 28), and the skew's base and variant are signed as its line signs them (finding 12) — ponytail — cost if wrong: none.
- Ruling: New's SI rows: f_max a text field read by parse_frequency, as f0 is, and the target a spin box in the C locale that always reads, so Custom needs no new refusal; for a preset both show its values, disabled; the pair combo's modes None, "rule", "given"; one G_SI_ENDS_HALF for a half victim or an empty picked partner, before the folder's check; I_SI_PAIR's how T_PAIR_WITH shown as G_PAIR_PICKED; G_SI_NEEDS_PAIR also names the Interface row's se50 or Custom for a single-ended net (findings 15, 24); Task 6 creates through the second victim row (finding 6) — ruling 6 — cost if wrong: one message.
- Ruling (finding 19): G_PROJECT_SI names a custom interface by New's combo label (G_INTERFACE_CUSTOM) and a preset by its name, as the combo lists them; it lands in Task 6 with G_INTERFACE_CUSTOM — ruling 6 — cost if wrong: one word.
- Ruling (findings 11, 20): Advanced reads an SI project's interface through str(), as it reads the preset, so a hand-edited interface that is not text opens with no defaults, never E_INTERNAL — ruling 8 — cost if wrong: none.
- Ruling: the button: `handed` reads `data.get("tracks", [])`; the tracks join Board.tracks and Board.vias by KIID; the SI branch follows the antenna's, its pickers every pad with copper, so a box selection's footprints narrow none (findings 13, 14); selected pads on the line replace the candidates, an N leg's two taken to the P side by partner_ends (finding 16); GND, power and netless nets drop (none left: G_HANDOFF_SI_NET); the pair mode follows the partner, and the interface fits the line: se50 for a single net under a pair's preset, usb2-hs, New's default, for a pair under se50, Custom kept (findings 4, 15, 24: a single net's pre-fill otherwise always met G_SI_NEEDS_PAIR, whose advice led to G_SI_PARTNER) — r2's table, ruling 9 — cost if wrong: a press that needs one click more.
- Ruling (findings 5, 17): the SI pre-fill puts the connector's pad first, where v1's puts it last: every SI project of the repo runs J1.3 → U1.3 (si_args, the tutorial, P4-F, the acceptance) and design 5.11 puts the MCU at the far end; the fingerprint holds the ends, so a reversed press would never compare with the tutorial's gap project, and a victim picked in the tutorial's order would read NEXT at the far end — open issue 3 — cost if wrong: a Swap click.
- Ruling: `si_candidates` returns Pad objects, which control's `_names` orders and dedups; choose_reference's rule is written again in it, as choose_reference needs which rule holds (connector or IC) and this only whether one does (finding 28: an extraction that kept the behaviour would move no pin); its ESD shortcut carries a `ponytail:` (finding 24); `p_side` sits beside partner_net — ponytail — cost if wrong: two copies of one condition.
- Ruling: `_si_handed`'s rules are prose, as Stage 3 plan 5 gave the antenna's, with its signature pinned, (net, partner, ends, problem), and its body test-first (finding 25) — format — cost if wrong: none.
- Ruling (reads ruling 11): the README's excerpts write a run folder as `<run folder>` and the projects by the tutorial's folder names, as the other two tutorials do, `<RUN>`, `<GATES>`, `<VARIANT>` and `<KRS_E2E_DIR>` meaning nothing to a reader running these commands; they stay in the exit record — Stage 3 plan 5's revised ruling — cost if wrong: a few placeholders.
- Ruling (findings 8, 10): README.md:146, the v1 tutorial's verify excerpt, becomes the same job's line in W_JOB_T_MAX's new words with its params, in Task 2's commit, as ruling 18 rewords the line for every kind — cost if wrong: one README line.
- Ruling (reads ruling 15): the copy reads the gap's run folder in place, under `<GATES>`' data folder, read-only through its results' run_dir (the e2e test snapshots its mtimes); `<GATES>`' data folder is never any command's data folder, its settings.json and steps never opened — reuse needs the run's waves, which live there — cost if wrong: one folder copied and one record edited.
- Ruling: `KRS_E2E_SI_VARIANT` is always a verified project.json, the fallback run by the CLI; the e2e masks `<KRS_E2E_DIR>` and `<VARIANT>` (the variant's third parent) — ruling 15 — cost if wrong: a rerun.
- Ruling: the acceptance's body is one helper, `si_through`, shared by the real test and its dry run, which asserts no resolved row (the fake's twin resolves nothing); it checks New's project line and fingerprint against the variant's before Cost, Run's confirmation (the estimate in it, no 2D row) and verify's lines, as Stage 3's `through()` does (finding 18), with one module-level `stamps` beside Stage 3's own copies (finding 27); its dry run is expected to pass from pieces that already run on the fake, cited in Task 12 (finding 26) — ruling 14, Stage 3's lag — cost if wrong: one rerun.
- Ruling (reads ruling 12): "8 ports" counts the jobs a run takes: project.json's six external ports and R1's and R2's part ports — cost if wrong: one number.
- Ruling: W_STAIRCASED_SI says "not decided yet" where ruling 13 says the owner's 45° rule, as a user-facing line names no owner — cost if wrong: a msgstr.
- Ruling: A-69 records §9.1 (d)'s release check steps, the antenna's (never recorded) and SI's, since the spec lists the steps — ruling 17 — cost if wrong: a paragraph.
- Ruling: seventeen tasks: each feature's control lands with the widget that first needs it (Stage 3's ruling), and the CLI's changed words form one task, one reviewer's gate — ruling 19 — cost if wrong: a reorder.
- Ruling: Run…'s confirmation filter applies to SI projects alone; v1's readout lines stay in v1's confirmation — design §3 — cost if wrong: none.
- Ruling: G_COMPARE_NONE is reworded too, as it names antennas only — ruling 5's purpose — cost if wrong: one msgstr.
- Ruling: the pt-BR msgstrs keep the glossary's nevers: I_SI_COST_SPEED says "por segurança", never "a favor" (finding 1, `test_the_pt_br_catalog_keeps_the_glossarys_nevers`), and G_RETUNE_ANTENNA_VALUE's table row is "na linha dele na tabela", apart from an SI "linha" (finding 21) — ruling 10 — cost if wrong: a msgstr.
- Ruling: the window run starts at 14 GB free too, though under 2 h — R-6c's floor, conservative — cost if wrong: a wait.
- Ruling (disclosure, the architect's): probes in a scratch folder with the repo's venv, in memory, no openEMS, KiCad, worker or suite: the SI retune's pieces on a fabricated 8-port usb2_hs layout (68 ms), si.read's profile (se2gmm 26 of 29 ms), draw_si's artists and limits on synthetic pairs, the readings the retrace test uses (levels on pair6, none on a zero chain), `snapped` (R1 25 to 24 in E24, 27 in E12), `bypass` and `port_value` on R and C, the walk and p_side on usb2_hs, qspi_clk, lpf915 and coupon_gcpw_arc, the fixtures' tracks, arcs and vias, kipy's types, a fresh usb2_hs project's six ports, P4-F's gap project (its board byte for byte the committed fixture, its run's record and fingerprint), the pt-BR terms of `po/pt_BR.po`'s neighbouring entries — cost if wrong: none.
- Ruling (disclosure, the revision's): read-only probes in a scratch folder on the feasibility critic's network-fake usb2_hs run, no test, worker or openEMS: which curves a retune of R1 and R2 moves (Sdd21, Scd21, NEXT and FEXT exact zeros; Sdd11 under 1e-4 dB; Scc21 0.1–1.6 dB), and the floor's two forms on draw_si's figures of that reading, of pair6(0.05, 0.02), of pair6() and of a −130 dB victim; and the msgstrs of this plan against the catalog's KEEP and never rules and QUOTED's labels — cost if wrong: none.

## Open issues, ruled by the controller (2026-11-08; owner unavailable)

The revision left four open issues. Each ruling below is a controller recommendation, made while the owner is unavailable, and binds as the rulings above do.

1. **The window's |S| floor.** Confirmed as the plan reads ruling 1: `max(lo, min(−100, hi − 40))`, with `gui=True` alone. A panel with a curve above −60 dB is never stretched under −100 dB by an exact zero. A panel whose curves all lie under −100 dB keeps its autoscale and is never inverted; Tasks 1 and 5 assert it. The CLI's PNGs keep their bytes (ruling 18).
2. **A press fits New's interface to its line.** Confirmed: se50 for a single net under a pair's preset, usb2-hs for a pair under se50, Custom kept, nothing else changed. The interface moves only where the one set cannot hold the pressed line. A pre-fill that Create always refuses would defeat design §5.10's pre-fill. A-66 records it.
3. **The connector's pad first in the SI pre-fill.** Confirmed. It is v1's order reversed for SI alone:
   - every SI project the repo makes runs J1.3 → U1.3;
   - the fingerprint holds the ends;
   - NEXT and FEXT are named from the start.

   A user who wants the other order swaps the ends in New. A-66 records it.
4. **Task 12's dry run, which no role has run yet.** Task 12's implementer runs it in Step 2, and any failure is fixed test-first:
   - a fault in the harness or the fake is fixed there, in Task 12's own files;
   - a product defect the dry run exposes on the window's detached SI run and verify path is fixed in its owning file, named in the report and reviewed with Task 12.

   A fix that would move a golden pin, a fingerprint input or the SI model spec's hash, or that contradicts a ruling, is not made: the implementer stops for a ruling (BLOCKED).
