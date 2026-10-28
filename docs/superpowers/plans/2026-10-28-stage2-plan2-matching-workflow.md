# Stage 2 · Plan 2 — Matching Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the GUI's matching workflow (design §5.9 item 2): New from a board with a pad picker, the instant retune with E12/E24 snapping and S2P parts, Apply through the CLI's `retune`, Verify with its stale indicator, the Advanced panel and About.

**Architecture:**
- **The retune session is plan 1's project read (Task 1).** `control.open_project` already reads the project and its `ChainResults` on the window's pool, and reads them again whenever project.json or the board changes; `ChainResults.lay` is the layout N-port. An update, `control.retuned`, runs the rows that differ from project.json through `pipeline.assign`, then `pipeline.chain_results` on that held layout: the CLI's own reading and chain, so its numbers and lines equal `retune`'s, in about 5 ms on lpf915, on the GUI thread. A new read carries the user's unapplied rows over part by part (`control.carried`, Task 3).
- **The window (Tasks 2–8)** gains the New form in the Project tab; the parts table with Revert in the Results tab, renamed "Results and retune" (Task 3), whose curves move in place (`outputs.retrace_summary`) and are blitted (Task 4), because a full redraw after `set_data` measured 105 ms on lpf915, over design §5.4's 50 ms; Apply, which runs `retune PROJECT REF=VALUE ...` to its end on the pool (`control.apply`); Verify, started through `control.start` and plan 1's watch; an Advanced tab, which saves project.json under the project lock; and a Help menu. Every result comes back through the normal re-read on project.json's new mtime. Task 9 is the controller's offscreen visual review.

**Tech Stack:** Python ≥ 3.11 (the dev venv runs 3.14.2). PySide6-Essentials 6.12.0: QtCore with `Signal`, and QtWidgets; offscreen in tests. matplotlib 3.11.2's `FigureCanvasQTAgg` with blitting (`copy_from_bbox`, `restore_region`, `draw_artist`, `blit`), and scikit-rf 2.2.0. From the stdlib: `subprocess`, `concurrent.futures`, `importlib.metadata`, `json`, `copy`, `dataclasses`, `math`, `re`, `string`, `time` (tests). pytest, with no pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-27-stage2-gui-and-button-design.md` (binding), its §5.9 item 2:
- §5.3: Project (New from a board, the pad picker, new's notes); Retune (snapping, S2P parts, the in-memory session, Apply); What-if (the label on every retuned plot and table, with Verify and the stale indicator beside it); Verify; Advanced; About.
- §5.4's instant retune.
- §5.1's in-process work (`new` and the session read on a worker thread; the chain update and the drawing on the GUI thread) and its lock rule (Run, Verify, Apply and model edits disabled while any run holds the lock).
- §3 (anti-goals) and §4 (constraints) bind every task.
- §7's owner defaults apply: E24 for L and C, set per part; the what-if wording pointing to Verify.

The research is git-ignored: `.superpowers/sdd/stage2-research/r2-gui/findings.md` (§1–§4 and its risks) and `r3-pack/findings.md` (About's licences). The engine authority is `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (§3.2's `new`, `retune` and `verify`; §7.2; §7.6). This plan does not amend it.

**Branch:** `stage2-plan2`, from `main` at `d0b4582`. This plan is `docs/superpowers/plans/2026-10-28-stage2-plan2-matching-workflow.md`. Commands run from the repo root with `.venv/Scripts/python`.

**Before Task 1 (the controller):**
1. Branch `stage2-plan2` from `main`. `git diff --stat d0b4582 HEAD -- src tests tools pyproject.toml .github` must print nothing; otherwise re-check this plan's line references first.
2. Commit this plan on the branch. Its rulings are its last section, `## Controller rulings (2026-10-28; binding)`.
3. After Task 9: the whole-branch review, then a local merge into `main`. Nothing is pushed.

## Global Constraints

- **Python and platforms:**
  - The declared floor stays `>=3.11`, and the CI matrix stays as it is.
  - The Windows install uses Python 3.14: the openEMS 0.37.0 wheels need 3.13 or 3.14.
  - Windows 10/11, and Linux with glibc ≥ 2.34.
- **Dependencies:** none added. PySide6-Essentials (`>=6.10.1,<7`), matplotlib and scikit-rf are already core dependencies. No QtCharts, no Addons, no pytest-qt. kicad-python is plan 3's.
- **Import rules (design §4):**
  - The core never imports Qt.
  - The GUI never imports openEMS or CSXCAD; the New and retune tests assert it after the engine ran in the GUI process.
  - `cli` and `worker` import neither Qt nor kicad-python.
  - `kicad_rf_studio.gui.control` imports neither Qt nor matplotlib; `tests/test_gui.py`'s `QT_FREE` probe pins this.
  - matplotlib loads only inside the PNG writer and in `gui/window.py`. `outputs.retrace_summary` imports nothing from matplotlib.
- **Process model (design §5.1, §5.4):**
  - Nothing in the GUI process reaches `runs.run_jobs`; the window fixture makes it fail.
  - Verify starts detached through `control.start`. Apply is `retune` run to its end, not detached, through `control.apply` on the window's pool.
  - `new`, the project read and the pad list run on the pool, and only the tick takes their results. The instant retune and every draw run on the GUI thread.
  - The GUI process writes nothing under `results/` (Apply's retune, run and verify write there), and writes project.json only through Advanced's Save, under the project lock.
- **No run logic in the GUI (design §3):**
  - The GUI adds no gate, stop rule or reduction.
  - Its numbers come only from `pipeline.chain_results`.
  - Every refusal is the engine's: `assign`, `part_impedances`, `check_project`, `project_lock`, `new`, `retune`, `verify`.
  - No board file is ever written; Task 2's test checks the board's bytes.
- **What-if:** while `pipeline.RETUNE_VALIDATED` is False, every retuned plot and table carries `G_WHAT_IF` (I_WHAT_IF's text with "Verify" in place of the command), with Verify and the stale indicator beside it.
- **Messages:**
  - Every user-facing string is a code in the one `CATALOG` of `core.messages`, rendered with `render()`. GUI codes start with `G_`. No `.ts` or `.qm` files.
  - The window words a CLI code its own way only through `control.text`'s `GUI` map: plan 1's five codes and this plan's fifteen, each a code whose advice names an option or a command that the window replaces. Every other code shows as the CLI renders it; "Not in this plan" lists the known ones.
  - Events stay language-neutral.
  - Tests check `KrsError.code` and `.params`, or rendered lines, never `match=`.
  - New codes are appended at the end of `CATALOG`, after `"G_COL_VERDICT"` (L228) and the codes earlier tasks added.
- **Licence and files:** GPL-3.0-or-later; an English UI; `# SPDX-License-Identifier: GPL-3.0-or-later` heads every new `.py` file.
- **Tests:**
  - Test-first. Tier (a) never runs openEMS.
  - Qt runs only under `QT_QPA_PLATFORM=offscreen`, which `tests/conftest.py` sets. No modal dialog is ever shown: tests replace `ask`, `QFileDialog` and `QMessageBox` statics.
  - Detached runs go through `tests/fake_cli.py`.
  - `test_gates.project_of` is cached: a test that edits lpf915's project takes `test_post_chain.lpf()`, a deep copy.
  - Every slot is a bound method; a lambda or partial slot keeps a closed window alive (plan 1).
- **Full suite:** before every commit, `.venv/Scripts/python -m pytest -q` passes. It takes about 14 minutes. The shell caps a foreground command at 10 minutes, so run it once in the background, with nothing beside it, and wait for its exit.
- **Privacy:**
  - The pre-commit privacy gate runs on every commit; never use `--no-verify`.
  - Synthetic fixtures only (`tests/fixtures`). A test that writes beside a board first copies it under `tmp_path`.
  - No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name.
- **Git:** no commit carries a co-author line. Nothing is pushed, and nothing goes to PyPI.
- **Workflow:** every implementer runs `graphify query "<question>"` (or `explain` or `path`) from the repo root before reading code, and `graphify update .` after each commit. Ponytail applies: the laziest solution that works, the repo's functions reused, the fewest files, the stdlib first, and a `ponytail:` comment, with its ceiling and its upgrade, on each corner cut.

## Review Focus

1. **A value the engine cannot read is typed:** "15nH" on a C, "0" on a C, or "abc".
   - The row keeps the text, and the lines show assign's refusal in the GUI's words (`G_RETUNE_VALUE`). A value too large to be finite ("9…9pF") is left as typed by snapping, and an update never raises.
   - No curve is drawn for it, and Apply would show retune's own refusal.
   - Tests: the "15nH" step of `test_the_retune_table_snaps_takes_s2p_parts_and_draws_under_the_what_if_label` (Task 3); the non-finite cases of Task 1's snapping and session tests.
2. **An S2P file is missing or not a 2-port.**
   - The refusal is the lines' last line, and no curve is drawn.
   - The plot comes back, under the label, with a good file.
   - Tests: the wrong-port-count step of `test_the_retune_session_gives_retunes_own_numbers_in_milliseconds_and_writes_nothing` (Task 1), and the missing-file step of the Task 3 test above.
3. **Apply is pressed while another run holds the lock.**
   - Apply is disabled while any holder lives.
   - A lock that appears after the click gets retune's own `E_LOCKED` line. Nothing is stored, and the edited rows stay.
   - Test: `test_apply_waits_while_a_run_holds_the_lock_and_shows_retunes_own_refusal` (Task 5).
4. **Verify is pressed with unapplied changes.**
   - It asks to Apply first. Yes applies them, then verify runs the stored values. No starts nothing, and an Apply that retune refuses starts no verify. A project opened while that Apply runs gets neither its G_APPLIED nor its verify.
   - The stale indicator stays lit until a verify of these values on this model.
   - Tests: `test_verify_asks_to_apply_first_runs_detached_and_shows_its_comparison` and `test_verify_is_stale_until_it_ran_these_values_on_this_model` (Task 6).
5. **project.json or the board changes under an open retune session:** a hand edit, a terminal's retune, a cost's, a run's or a verify's end, a board save, or an Advanced Save.
   - The rows are rebuilt from the new read. An unapplied value is kept while the read leaves its part as it was; one whose part changed is dropped, with `G_DROPPED`. The table is disabled while the read goes on.
   - A model change shows `G_RESULTS_STALE`, with no rows and no plot.
   - Tests: `test_a_read_keeps_the_unapplied_rows_whose_part_it_did_not_change` and `test_a_read_keeps_the_unapplied_values_unless_project_json_changed_their_part` (Task 3); `test_advanced_saves_project_json_under_the_lock_and_a_model_change_marks_the_results_stale` (Task 7).

---

## File structure

```
src/kicad_rf_studio/pipeline.py              # T1 chain_results(..., lay=None)
src/kicad_rf_studio/core/kicad/values.py     # T1 value_text
src/kicad_rf_studio/core/post/outputs.py     # T4 _traces, retrace_summary
src/kicad_rf_studio/core/messages.py         # T2–T8 the G_ codes; T3 G_TAB_RESULTS's text
src/kicad_rf_studio/gui/control.py           # T1 Row, SERIES, default_series, snapped, rows, changed, retuned
                                             # T2 pads, message, GUI +7; T3 carried, GUI +6; T5 _env, apply
                                             # T6 verify_stale, verify_lines, Opened.verified, GUI +1
                                             # T7 Field, UNITS, fields, edited, Opened.stored, GUI +1; T8 DEPENDENCIES, about
src/kicad_rf_studio/gui/window.py            # T2 NewForm; T3 the parts table in ResultsView; T4 the blit; T5 Apply
                                             # T6 Verify; T7 AdvancedView; T8 the Help menu
tests/test_run.py  test_values.py  test_post_outputs.py  test_gui_control.py  test_gui.py  fake_cli.py
```

---

### Task 1 [code]: The Qt-free retune session

**Files:**
- Modify:
  - `src/kicad_rf_studio/pipeline.py` (`chain_results`, L436–474);
  - `src/kicad_rf_studio/core/kicad/values.py` (after `snap`, at the end of the file);
  - `src/kicad_rf_studio/gui/control.py` (its docstring; the new names after `text`, L192).
- Test:
  - `tests/test_run.py` (a test right after `test_write_outputs_writes_what_chain_results_holds`, L463–478);
  - `tests/test_values.py` (`port_value` and `value_text` join the values import; two tests);
  - `tests/test_gui_control.py` (imports; three tests).

**Interfaces:**
- Consumes:
  - `pipeline.assign`, `pipeline.chain_results`, `pipeline.ChainResults`;
  - `core.project.parts`;
  - `values.snap`, `values.port_value`, `values.part_kind`, `KrsError`, `messages.detail`.
  - In tests: test_run's `lpf_run`, `lpf_loads` and `star_project`; networks' `star` and `terminate_np`; test_post_chain's `M0402` and `lpf` (a deep copy of the cached lpf915 project); conftest's `calibrated`.
- Produces:
  - `pipeline.chain_results(path: Path, project: dict, *, errors_as_lines: bool = False, lay: Layout | None = None) -> ChainResults`. A given `lay` stands in for `layout(project, project["results"])`: the layout depends only on the run, never on the part values.
  - `values.value_text(value: float, kind: str | None) -> str`, for `value > 0`. The rule:
    - `exp = min(max(3 * math.floor(math.log10(value) / 3 + 1e-9), -12), 9)`;
    - the prefix is `{-12: "p", -9: "n", -6: "u", -3: "m", 0: "", 3: "k", 6: "M", 9: "G"}[exp]`;
    - the unit is `{"C": "F", "L": "H"}.get(kind, "")`;
    - the text is `f"{value / 10 ** exp:g}{prefix}{unit}"`.
    The `1e-9` keeps a decade exact. `port_value` reads every E12 and E24 value back exactly (probed: none of 1,656 cases fails).
  - `control.Row`, a frozen dataclass: `ref: str`, `value: str` (the text as typed), `s2p: str` (a file, "" for none), `connection: str` ("series" or "shunt").
  - `control.SERIES = ("off", "E12", "E24")`.
  - `control.default_series(ref: str) -> str`: "E24" for a C or an L (`part_kind`), else "off".
  - `control.snapped(ref: str, text: str, series: str) -> str`: `text` unchanged when `series` is "off", or `port_value(ref, text)` is None, 0 or not finite (a 400-digit value reads as inf, which `snap` cannot take). Otherwise `value_text(snap(value, series), part_kind(ref))`.
  - `control.rows(project: dict, folder: Path, refs: list[str]) -> list[Row]`. For each ref, its part's value; its S2P file as `str((folder / s2p["file"]).resolve())`, as `part_impedances` resolves it, else ""; and its connection, else "series".
  - `control.changed(project: dict, folder: Path, rows: list[Row]) -> list[str]`: the `REF=RIGHT` assignments of the rows that differ from project.json, in row order.
    - A row with a file is `f"{ref}={Path(folder, row.s2p).resolve()}:{row.connection}"`. It is changed when the part has no file, another resolved file, or another connection; its Value cell does not count.
    - A row without a file is `f"{ref}={row.value}"`. It is changed when the part has a file or another value text.
  - `control.retuned(path: Path, project: dict, stored: pipeline.ChainResults, rows: list[Row]) -> pipeline.ChainResults`: `pipeline.chain_results(path, assign(project, changed(project, path.parent, rows), path.parent), errors_as_lines=True, lay=stored.lay)`, the CLI's own functions in retune's order. Any exception on the way returns `dataclasses.replace(stored, chain=None, ideal=None, p_layout=None, what_if=False, lines=[line])`, the line being a KrsError's `(code, params)` (assign's refusal, E_S_SINGULAR) or `("E_INTERNAL", {"detail": detail(e)})` for any other. It writes nothing and never raises, so no stale curve stays on screen.

- [ ] **Step 1: Write the failing tests.** In `tests/test_run.py`, right after `test_write_outputs_writes_what_chain_results_holds`:

```python
def test_chain_results_takes_the_layout_it_is_given(tmp_path, monkeypatch):  # Stage 2 design 5.3: the retune session
    pj, project = star_project(tmp_path, 2)
    res = pipeline.chain_results(pj, project)
    monkeypatch.setattr(pipeline, "layout", fail)  # the session holds the layout: never read again
    again = pipeline.chain_results(pj, project, lay=res.lay)
    assert again.lay is res.lay and np.array_equal(again.chain, res.chain) and again.lines == res.lines
```

  In `tests/test_values.py`, `port_value` and `value_text` join the values import:

```python
@pytest.mark.parametrize(("value", "kind", "text"), [
    (4.7e-12, "C", "4.7pF"), (15e-9, "L", "15nH"), (100e-12, "C", "100pF"), (5.1e-9, "C", "5.1nF"),
    (1e-6, "C", "1uF"), (4700.0, "R", "4.7k"), (47.0, "R", "47"), (0.091, "R", "91m"), (1e-13, "C", "0.1pF")])
def test_value_text_writes_a_value_as_a_part_value(value, kind, text):  # Stage 2 design 5.3: snapping writes it back
    assert value_text(value, kind) == text


def test_port_value_reads_back_every_e_series_value_value_text_writes():  # no floor-of-log10 edge at a decade
    for m in E24:  # E12 is a part of E24
        for e in range(-13, 10):
            v = float(f"{m}e{e}")
            assert [port_value(ref, value_text(v, ref[0])) for ref in ("C1", "L1", "R1")] == [v, v, v]
```

  The imports of `tests/test_gui_control.py` gain:
  - `from dataclasses import replace`, `import numpy as np` and `import skrf as rf`;
  - `from kicad_rf_studio.core.post.waves import grid`;
  - `parts` in the `core.project` import;
  - `from networks import star, terminate_np`, `from test_post_chain import M0402, lpf` and `from test_run import lpf_loads, lpf_run`;
  - after the imports, `F, _ = grid(915e6, 3, 1.1)`.

  Then the tests:

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_run.py tests/test_values.py tests/test_gui_control.py -q`. Expected: FAIL.
  - `ImportError: cannot import name 'value_text'` at test_values' collection;
  - `TypeError: chain_results() got an unexpected keyword argument 'lay'`;
  - `AttributeError: module 'kicad_rf_studio.gui.control' has no attribute 'snapped'`.
- [ ] **Step 3: Implement** the Interfaces.
  - `chain_results`: add the keyword, then `lay = layout(project, results) if lay is None else lay`. The docstring gains one sentence on `lay`.
  - `value_text`: written with the rule above and the docstring "`value` (> 0) as a part value that port_value reads back exactly: an engineering prefix from p to G, and F for a C or H for an L (4.7pF, 15nH, 4.7k); how snapping writes a value back (Stage 2 design 5.3)".
  - `control.py`:
    - The docstring adds "the retune session (an update of a project read's chain from the parts' rows)".
    - Imports: `dataclasses.replace`, `math`, `KrsError` and `detail` (already there), `parts`, and `part_kind, port_value, snap, value_text`.
    - `retuned` carries `# ponytail: each S2P file is read again on every update, on the GUI thread (about 2, 5 and 19 ms per file of 401, 1601 and 6401 points on lpf915; a file on a slow network share stalls it); cache by (file, mtime_ns), or read on the pool, when several large files pass 50 ms`.
    - `changed` carries `# ponytail: a value typed as TEXT:series reads as an S2P file, as on the command line; refuse the suffix in the Value cell if it confuses users`.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/core/kicad/values.py src/kicad_rf_studio/gui/control.py tests/test_run.py tests/test_values.py tests/test_gui_control.py
git commit -m "feat(gui): the Qt-free retune session: chain_results on a held layout, the changed rows through assign, and snapping written back as a part value (Stage 2 design 5.3, 5.4)"
graphify update .
```

---

### Task 2 [code]: New from a board, with the pad picker

**Files:**
- Modify:
  - `src/kicad_rf_studio/gui/control.py` (`GUI`, L19–20; `pads` and `message` after Task 1's names);
  - `src/kicad_rf_studio/gui/window.py` (imports; `NewForm` before `MainWindow`; `MainWindow.__init__`, L89–124; `tick`, L157–208; the new slots);
  - `src/kicad_rf_studio/core/messages.py` (the codes below).
- Test:
  - `tests/test_gui_control.py` (imports `re`, `string`, `CATALOG, KrsError` beside `render`, and `FIX` beside `new_project`);
  - `tests/test_gui.py`.

**Interfaces:**
- Consumes:
  - `cli.new(...) -> (Path, notes)` and `cli.PRESETS`;
  - `core.kicad.load_board`;
  - `core.kicad.stackup.PRESETS` (`("kicad-default", "jlcpcb-2l")`);
  - `core.project.HARMONICS` (3) and `DEFAULT_PRESET` ("normal");
  - `values.parse_frequency`;
  - plan 1's `MainWindow` (`pool`, `tick`, `open_project`) and `control.text`.
- Produces:
  - `control.pads(board: Path) -> list[str]`: the names REF.PAD of the board's pads with copper (`load_board`, `Pad.layers`), each once, in natural order. The key is `[int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]`, so U1.9 comes before U1.10. It raises load_board's refusals. It carries `# ponytail: every pad with copper, GND's too; new refuses a GND or netless end with its own message`.
  - `control.message(error: Exception) -> str`: `text(error.code, error.params)` for a KrsError, else `text("E_INTERNAL", {"detail": detail(error)})`.
  - `control.GUI` gains `"E_PROJECT_EXISTS": "G_PROJECT_EXISTS"`, `"E_OUTPUT_PATH": "G_OUTPUT_PATH"`, `"E_NO_STACKUP": "G_NO_STACKUP"`, `"E_STACKUP_LAYERS": "G_STACKUP_LAYERS"`, `"W_LID_HEIGHT_MISSING": "G_LID_HEIGHT_MISSING"`, `"I_PART_NO_MODEL": "G_PART_NO_MODEL"` and `"W_NO_REFERENCE": "G_NO_REFERENCE"`.
  - `window.NewForm(QGroupBox)`, titled `G_NEW`. Its widgets:
    - `board: QLineEdit` and `board_button` (G_BROWSE);
    - `start` and `end`: editable `QComboBox`es;
    - `f0: QLineEdit`;
    - `harmonics: QSpinBox` (1–99, value `HARMONICS`);
    - `preset: QComboBox` (the items `cli.PRESETS`, current `DEFAULT_PRESET`);
    - `stackup: QComboBox`: `G_STACKUP_BOARD` with data None, then each name of `stackup.PRESETS` with itself as data;
    - `lid: QDoubleSpinBox`: 0–100, 2 decimals, `setLocale(QLocale.c())`, special value text `G_NONE`, value 0;
    - `folder: QLineEdit` and `folder_button` (G_BROWSE);
    - `create_button` (G_CREATE), `status: QLabel` (word-wrapped) and `notes: QListWidget`;
    - `chosen: str`, the board text whose pads were last read ("" at first).

    It lays them out in a `QFormLayout` with the labels G_NEW_BOARD, G_NEW_START, G_NEW_END, G_NEW_F0, G_NEW_HARMONICS, G_NEW_PRESET, G_NEW_STACKUP, G_NEW_LID and G_NEW_FOLDER. The board and folder rows are each a field with its button. Then come `create_button`, `status` and `notes`.
  - `MainWindow.new_form: NewForm`, on the Project page after `open_button` and `project_status`.
  - `MainWindow.pads_read: Future | None` and `MainWindow.creating: Future | None`.
  - Slots:
    - `pick_board()`: `QFileDialog.getOpenFileName(self, render("G_NEW_BOARD"), "", render("G_BOARD_FILTER"))`; a picked name goes into the board field, then `board_chosen()`.
    - `board_chosen()`, also on the board field's `editingFinished`: for a stripped text that is not empty and not `chosen`, `chosen` becomes it, `folder` becomes `str(Path(text).with_suffix(""))`, and `pads_read = pool.submit(control.pads, Path(text))`. Focus leaving the same board keeps a folder the user typed.
    - `pick_folder()`: `QFileDialog.getExistingDirectory(self, render("G_NEW_FOLDER"))`; a picked name goes into the folder field.
    - `create_project()`.
  - `show_pads(done: Future)` and `created(done: Future)`.
  - CATALOG (exact texts):
    - `"G_NEW": "New from a board"`
    - `"G_NEW_BOARD": "Board"`
    - `"G_NEW_START": "Start pad (REF.PAD)"`
    - `"G_NEW_END": "End pad (REF.PAD)"`
    - `"G_NEW_F0": "f0 (for example 915MHz)"`
    - `"G_NEW_HARMONICS": "Harmonics"`
    - `"G_NEW_PRESET": "Preset"`
    - `"G_NEW_STACKUP": "Stackup"`
    - `"G_NEW_LID": "Shield lid height (mm)"`
    - `"G_NEW_FOLDER": "Project folder"`
    - `"G_NEW_NO_FOLDER": "Choose the project folder: New writes project.json into it."`
    - `"G_BROWSE": "Browse…"`
    - `"G_BOARD_FILTER": "KiCad boards (*.kicad_pcb)"`
    - `"G_STACKUP_BOARD": "The board's own"`
    - `"G_NONE": "none"`
    - `"G_CREATE": "Create the project"`
    - `"G_CREATING": "Reading the board and writing project.json…"`
    - `"G_PROJECT_EXISTS": "{path} already exists. Open it with Open a project…, or choose another project folder."`
    - `"G_OUTPUT_PATH": "Cannot write {path}: {reason}. Choose another project folder."`
    - `"G_NO_STACKUP": "The board has no stackup. Choose the stackup jlcpcb-2l, or kicad-default to accept KiCad's default rule."`
    - `"G_STACKUP_LAYERS": "The stackup has {stackup} copper layers but the board has {board}. Fix the board stackup in KiCad, or choose a matching stackup."`
    - `"G_LID_HEIGHT_MISSING": "Shield {refs} covers the simulated region and no lid height was given; set lid_height_mm in Advanced before you run, or set lid to false to leave the lid out."`
    - `"G_PART_NO_MODEL": "Part {ref} {value}: {role}; no package preset, so as a port a C, L or R takes its ideal value and any other part needs its S2P file, which its row in Results and retune takes."`
    - `"G_NO_REFERENCE": "No reference found for {signal}; set its port's reference (ports[].reference) in Advanced before you run."`

- [ ] **Step 1: Write the failing tests.** In `tests/test_gui_control.py`:

```python
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
```

  In `tests/test_gui.py`:

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q`. Expected: FAIL.
  - `AttributeError: ... no attribute 'pads'`;
  - `KeyError: 'G_PROJECT_EXISTS'`;
  - `AttributeError: 'MainWindow' object has no attribute 'new_form'`.
- [ ] **Step 3: Implement** the Interfaces, then the flow:
  - **`create_project()`:**
    - `f0 = parse_frequency(f.f0.text())` on the GUI thread. Its KrsError puts `control.message(e)` in `status`, and nothing is submitted.
    - A folder field that is empty once stripped puts `render("G_NEW_NO_FOLDER")` in `status`, and nothing is submitted (`new`'s own default, the working directory, means nothing to a GUI).
    - Otherwise: `status` shows G_CREATING, `create_button` is disabled, and `self.creating = self.pool.submit(cli.new, f.board.text(), f.start.currentText().strip(), f.end.currentText().strip(), f0, harmonics=f.harmonics.value(), preset=f.preset.currentText(), stackup=f.stackup.currentData(), lid_height=f.lid.value() or None, output=f.folder.text())`.
  - **`tick()`:** first come plan 1's poll of `started`, then these two, both before `if self.path is None: return`, so that they work before any project is open:
    - a done `pads_read`, taken as plan 1 takes `loading`, goes to `show_pads(done)`;
    - a done `creating`, taken the same way, goes to `created(done)`.
  - **`show_pads(done)`:** each of `start` and `end` is cleared and gets `addItems(names)` and `setCurrentIndex(-1)`, so no pad is picked for the user. An exception puts `control.message(e)` in `status` and leaves the pickers empty.
  - **`created(done)`:** it enables `create_button`.
    - On success, `status` is cleared, `notes` shows `control.text` of each note, and `open_project(path)` follows.
    - On an exception, `status` gets `control.message(e)`.
  - **The window's imports** gain `cli`, `QLocale`, `QGroupBox`, `QFormLayout`, `QLineEdit`, `QComboBox`, `QSpinBox`, `QDoubleSpinBox`, `QHBoxLayout`, `parse_frequency`, `HARMONICS`, `DEFAULT_PRESET`, and `core.kicad.stackup.PRESETS as STACKUPS`.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py tests/test_gui_control.py tests/test_gui.py
git commit -m "feat(gui): New from a board, with the pad picker, new's defaults and its notes (Stage 2 design 5.3)"
graphify update .
```

---

### Task 3 [code]: The retune table in the Results tab

**Files:**
- Modify:
  - `src/kicad_rf_studio/gui/control.py` (`carried`; six `GUI` entries);
  - `src/kicad_rf_studio/gui/window.py`:
    - `ResultsView`, L44–76;
    - in `MainWindow`: `__init__`, `open_project` (L132–142), the tick's read (L179–188) and its buttons (L206–208), `show_project` (L283–305), and the new `retune` and `revert`;
  - `src/kicad_rf_studio/core/messages.py` (the codes; `G_TAB_RESULTS`'s text).
- Test:
  - `tests/test_gui_control.py`;
  - `tests/test_gui.py`. Its imports gain:
    - `import numpy as np`;
    - `from kicad_rf_studio.core.post.chain import with_box, z_part` and `from kicad_rf_studio.core.post.waves import grid`;
    - `parts` in the `core.project` import;
    - `from kicad_rf_studio.gui.window import FIXTURE, PART, S2P, SNAP, VALUE, MainWindow`;
    - `from networks import C_BOX, star, terminate_np, write_s2p`, `from test_post_chain import M0402` and `lpf_loads` beside `lpf_run`;
    - `F, _ = grid(915e6, 3, 1.1)`.

**Interfaces:**
- Consumes:
  - Task 1's `Row`, `SERIES`, `default_series`, `snapped`, `rows`, `changed` and `retuned`;
  - `outputs.draw_summary`, `outputs.LIMITS`;
  - plan 1's `ResultsView` (`what_if`, `problem`, `canvas`, `lines`), `MainWindow.loading` and `control.text`.
- Produces:
  - `control.carried(before: dict | None, after: dict | None, folder: Path, rows: list[Row], fresh: list[Row]) -> tuple[list[Row], bool]`: `fresh` (the new read's rows) with each of `rows` that the user changed against `before` (`changed`) put back in its part's place when `after` holds that part exactly as `before` did (`parts`); and whether any such row was lost (its part changed or gone, or no `after`). Nothing is carried without `before`. It carries `# ponytail: a row whose part project.json changed takes the stored row (G_DROPPED); a per-field merge if users lose work that way`.
  - `control.GUI` gains `E_RETUNE_VALUE`, `E_PART_NO_VALUE`, `E_S2P_MISSING`, `E_S2P_UNREADABLE`, `E_S2P_BAND` and `W_S2P_FIXTURE`, each to the G_ code of the same name after its prefix (`G_RETUNE_VALUE`, `G_PART_NO_VALUE`, `G_S2P_MISSING`, `G_S2P_UNREADABLE`, `G_S2P_BAND`, `G_S2P_FIXTURE`).
  - `window.PART, VALUE, SNAP, S2P, FIXTURE = range(5)`: the parts table's columns.
  - **`ResultsView` gains:**
    - `edited = Signal()`, emitted when a row's value, snapping, S2P file or fixture changed;
    - `parts: QTableWidget(0, 5)`, with headers G_COL_PART, G_COL_VALUE, G_COL_SNAP, G_COL_S2P and G_COL_FIXTURE, the S2P column stretched (`QHeaderView.ResizeMode.Stretch`);
    - `s2p_button` (G_CHOOSE_S2P), `revert_button` (G_REVERT) and `retune_status: QLabel` (word-wrapped);
    - `retune_box: QWidget`, holding `parts` and then the row `buttons: QHBoxLayout` of `s2p_button`, `revert_button` and `retune_status`, hidden without part rows. The view's column becomes `what_if`, `problem`, `retune_box`, `canvas`, `lines`;
    - `series: dict[str, str]`: each part's snapping as the user set it.
  - **`ResultsView`'s methods:**
    - `display(opened: control.Opened, folder: Path | None)` replaces `display(opened, name)`. It shows the problem as plan 1 does, and `show_rows(control.rows(opened.project, folder, res.refs))` when the results have part ports, else `show_rows([])`. `retune_box` shows only with rows. Then `show_chain(opened.results, folder.name if folder else "")`. It never touches `retune_status`.
    - `show_rows(rows: list[control.Row])`, with the table's signals blocked. Part is read-only; Value is editable. Snapping is a `QComboBox` of `SERIES` (texts G_SNAP_OFF, G_SNAP_E12 and G_SNAP_E24; data the series), current `series.get(ref, default_series(ref))`. S2P file is editable. Fixture is a `QComboBox` (G_FIXTURE_SERIES with data "series", G_FIXTURE_SHUNT with data "shunt"), current `row.connection`. Each combo is connected after its current index is set.
    - `rows() -> list[control.Row]`, from the cells (the S2P text stripped, the connection the Fixture combo's data).
    - Slots: `item_changed(item)` on `parts.itemChanged`, `snapping_changed(index)`, `fixture_changed(index)` and `choose_s2p()`.
    - `show_chain(res: pipeline.ChainResults | None, name: str)`.
  - `MainWindow.retune()`, connected to `results.edited`, and `MainWindow.revert()`, connected to `revert_button`.
  - CATALOG:
    - `"G_TAB_RESULTS"`'s text becomes `"Results and retune"`.
    - `"G_COL_PART": "Part"`, `"G_COL_VALUE": "Value"`, `"G_COL_SNAP": "Snapping"`, `"G_COL_S2P": "S2P file"`, `"G_COL_FIXTURE": "S2P fixture"`
    - `"G_SNAP_OFF": "off"`, `"G_SNAP_E12": "E12"`, `"G_SNAP_E24": "E24"`
    - `"G_FIXTURE_SERIES": "series"`, `"G_FIXTURE_SHUNT": "shunt"`
    - `"G_CHOOSE_S2P": "S2P file…"`, `"G_S2P_FILTER": "Touchstone 2-ports (*.s2p)"`, `"G_REVERT": "Revert"`
    - `"G_DROPPED": "project.json changed on disk: the parts it changed show their stored values again, and the values you had not applied to them were dropped."`
    - `"G_RETUNE_VALUE": "Cannot read \"{value}\" as the value of {ref}: a C, L or R takes a value in its own unit (4.7pF, 4p7, 15nH, 50R; a C above 0), and any part takes an S2P file in its row."`
    - `"G_PART_NO_VALUE": "Part {ref} has no value that reads (\"{value}\") and no S2P file, so its port cannot be closed. Give it an S2P file in its row, or, for a C, L or R, a value."`
    - `"G_S2P_MISSING": "Part {ref}: its S2P file {path} does not exist. Choose an existing file in its row, or, for a C, L or R, clear the file to use its value."`
    - `"G_S2P_UNREADABLE": "Part {ref}: {path} is not a Touchstone file that can be read. Check the file, or, for a C, L or R, clear the file to use its value."`
    - `"G_S2P_BAND": "Part {ref}: {path} covers {f_lo}–{f_hi} MHz, not the simulated band {f1}–{f2} MHz, and it is never extrapolated. Choose a file that covers the band, or, for a C, L or R, clear the file to use its value."`
    - `"G_S2P_FIXTURE": "Part {ref}: {path} fits a {fits}-thru measurement better than the {named} fixture it was given. The fixture names how the vendor measured the part, not its place on the board; if the vendor used {fits}-thru, set its fixture to {fits}."`

- [ ] **Step 1: Write the failing tests.** In `tests/test_gui_control.py`:

```python
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
```

  In `tests/test_gui.py`:

```python
def column(table, c):
    return [table.item(k, c).text() for k in range(table.rowCount())]


def test_the_retune_table_snaps_takes_s2p_parts_and_draws_under_the_what_if_label(window, tmp_path, monkeypatch):
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q`. Expected: FAIL.
  - `ImportError: cannot import name 'FIXTURE' from 'kicad_rf_studio.gui.window'` at test_gui's collection;
  - `AttributeError: ... no attribute 'carried'`.
- [ ] **Step 3: Implement** the Interfaces. The tests fix the states; this fixes the flow.
  1. **`show_chain(res, name)`:**
     - `what_if` shows only when `res` carries `what_if`.
     - `lines` holds `control.text` of `res.lines`, then `render` of each LIMITS code, whenever `res` is not None; otherwise it is empty.
     - `fig.clear()`; with a chain on 2 external ports, `draw_summary(fig, res.lay, res.chain, res.ideal, name, label)`, where `label = self.what_if.text() if res.what_if else None`, as plan 1's display does. Then `canvas.draw_idle()`. (Task 4 moves the curves in place instead.)
  2. **The slots:**
     - `item_changed(item)`: on the Value column, `control.snapped(ref, text, series)` written back with the table's signals blocked when it differs. Then `edited.emit()`.
     - `snapping_changed`: finds its row as the one whose Snapping cell widget `is self.sender()`, stores its data in `series[ref]`, snaps that row's value the same way, then emits.
     - `fixture_changed`: emits.
     - `choose_s2p()`: on `parts.currentRow()` (nothing when it is −1), `QFileDialog.getOpenFileName(self, render("G_CHOOSE_S2P"), "", render("G_S2P_FILTER"))`. A picked name goes into that row's S2P cell, whose `itemChanged` emits.
  3. **`MainWindow.retune()`:** clears `retune_status`, then `self.results.show_chain(control.retuned(self.path, self.opened.project, self.opened.results, self.results.rows()), self.path.parent.name)`.
  4. **`MainWindow.revert()`:** clears `retune_status`, then `self.results.display(self.opened, self.path.parent)`, a full draw at the stored values.
  5. **`open_project`** calls `display(control.Opened(None, None, None, None, None, None), None)`, clears `retune_status` and `results.series`. **`show_project`** calls `display(opened, self.path.parent)`.
  6. **The tick's read**, inside its `try`:
     - Before `self.opened` is replaced, it keeps `before, rows = self.opened, self.results.rows()`.
     - After `show_project`: `kept, lost = control.carried(before and before.project, self.opened.project, self.path.parent, rows, self.results.rows())`. When `kept` differs from the view's rows, `self.results.show_rows(kept)` and `self.retune()`, so the kept values are computed on the new read's layout. Then, when `lost`, `retune_status` shows G_DROPPED.
  7. **Among the tick's buttons**, `results.retune_box` is enabled while no read goes on (`self.loading is None`): the busy state of r2's risks, since the last read's layout may belong to a model that is gone.
  8. **The window's imports** gain `Signal` and `QHeaderView`.
- [ ] **Step 4: Run them again.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q`. Expected: PASS, plan 1's Results tests included.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py tests/test_gui_control.py tests/test_gui.py
git commit -m "feat(gui): the retune table in the Results tab: snapping, S2P parts, Revert, and unapplied rows carried over a re-read, under the what-if label (Stage 2 design 5.3)"
graphify update .
```

---

### Task 4 [code]: The curves moved in place and blitted

**Files:**
- Modify:
  - `src/kicad_rf_studio/core/post/outputs.py` (`_traces` before `draw_summary`, which plots its pairs, L138–160; `retrace_summary` after `draw_summary`);
  - `src/kicad_rf_studio/gui/window.py` (`ResultsView`: `__init__`, `display`, `show_chain`, and the new `blit` and `on_draw`).
- Test:
  - `tests/test_post_outputs.py` (`retrace_summary` joins the outputs import);
  - `tests/test_gui.py` (`import time`).

**Interfaces:**
- Consumes: Task 3's `ResultsView` (`show_chain`, `display`, `what_if`, `lines`) and `MainWindow.retune`; `outputs.draw_summary`.
- Produces:
  - `outputs._traces(lay: Layout, s: np.ndarray) -> list`: the four (x, y) pairs of one curve: (GHz, dB of |S21|), (GHz, dB of |S11|), S11's locus (real, imag), and its points at `lay.markers`. `draw_summary` plots these pairs, so summary.png is unchanged (its tests pin `summary_png` as `draw_summary` saved at 100 dpi).
  - `outputs.retrace_summary(axes: tuple, lay: Layout, chain: np.ndarray, ideal: np.ndarray | None) -> list`. It sets the curves that `draw_summary` drew on `axes` (its return, with `ideal` present or absent as drawn) to `chain`'s and `ideal`'s, through `set_data` of `_traces`' pairs, with no draw and no rescale. Curve k of n (layout first, then ideal) is `ax21.lines[k]`, `ax11.lines[k]`, `ax_smith.lines[-2 * n + 2 * k]` and `ax_smith.lines[-2 * n + 2 * k + 1]`. It returns those Line2D, per curve: S21, S11, locus, dots.
  - `ResultsView` gains `axes: tuple | None`, `curves: list` and `bg`; `blit()`; and `on_draw(event)`, connected with `canvas.mpl_connect("draw_event", self.on_draw)`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_post_outputs.py`:

```python
def test_retrace_moves_the_curves_draw_summary_drew_in_place():  # Stage 2 design 5.4: set_data at fixed limits
    one = ideal_schematic(PI, PI_Z, F)
    two = ideal_schematic(PI, {ref: 1.3 * z for ref, z in PI_Z.items()}, F)
    lay, fig, fresh = lay_of(EXT, one), Figure(), Figure()
    axes = draw_summary(fig, lay, one, one, "lpf915", "L")
    limits = [ax.get_ylim() for ax in axes[:2]]
    curves = retrace_summary(axes, lay, two, one)
    assert len(curves) == 8 and {c.axes for c in curves} == set(axes)
    for ax, new in zip(axes, draw_summary(fresh, lay, two, one, "lpf915", "L")):
        assert all(np.array_equal(a.get_xydata(), b.get_xydata()) for a, b in zip(ax.lines, new.lines))
    assert [ax.get_ylim() for ax in axes[:2]] == limits  # no rescale: the limits stay the first draw's
```

  In `tests/test_gui.py`:

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_outputs.py tests/test_gui.py -q`. Expected: FAIL with `ImportError: cannot import name 'retrace_summary'` at test_post_outputs' collection and `AttributeError: 'ResultsView' object has no attribute 'axes'`.
- [ ] **Step 3: Implement** the Interfaces, then the flow:
  1. **`show_chain(res, name)`:** `what_if` and `lines` as in Task 3.
     - With a chain on 2 external ports and `axes` already drawn, `retrace_summary(self.axes, res.lay, res.chain, res.ideal)` moves the curves, then `blit()`.
     - Otherwise `fig.clear()`, and `axes`, `curves` and `bg` go back to None, [] and None. With a plottable chain, `axes = draw_summary(fig, ...)` as in Task 3 follows, then `curves = retrace_summary(axes, ...)` (the data unchanged), each curve set `set_animated(True)`. Then `canvas.draw_idle()`.
     - It carries `# ponytail: the curves keep the limits of the last full draw (the stored values', or the first good values after a refusal); a retune far off clips until Revert or Apply draws again`.
  2. **`display`** sets `axes = None` before its `show_chain`, so a read, Revert and the re-read after Apply draw in full.
  3. **`blit()`:** without `bg`, `canvas.draw()`, whose draw_event runs `on_draw`. Else `canvas.restore_region(bg)`, `curve.axes.draw_artist(curve)` for each curve, and `canvas.blit(fig.bbox)`. It carries `# ponytail: a status line that changes height (G_APPLIED cleared, the stale indicator lit) resizes the canvas, which Qt then redraws once in full; fixed-height status lines if that is felt`.
  4. **`on_draw(event)`:** `bg = canvas.copy_from_bbox(fig.bbox)`, then each curve drawn with `draw_artist`. The blit was measured at 1.1–1.6 ms, against 103–108 ms for a full redraw.
- [ ] **Step 4: Run them again.** `.venv/Scripts/python -m pytest tests/test_post_outputs.py tests/test_gui.py -q`. Expected: PASS, Task 3's and plan 1's Results tests included.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/post/outputs.py src/kicad_rf_studio/gui/window.py tests/test_post_outputs.py tests/test_gui.py
git commit -m "feat(gui): the retune moves the curves in place and blits them, within the 50 ms budget (Stage 2 design 5.4)"
graphify update .
```

---

### Task 5 [code]: Apply through the CLI's retune

**Files:**
- Modify:
  - `src/kicad_rf_studio/gui/control.py` (`_env`, which `start`, L31–49, now uses; `apply`);
  - `src/kicad_rf_studio/gui/window.py` (`ResultsView.apply_button`; in `MainWindow`: `applying`, `changes`, `apply`, `applied`, `open_project`, and the tick);
  - `src/kicad_rf_studio/core/messages.py`.
- Test: `tests/test_gui_control.py` (import `LIMITS`); `tests/test_gui.py`.

**Interfaces:**
- Consumes:
  - Task 1's `changed`;
  - Task 3's `ResultsView` (`retune_box`, `parts`, `buttons`, `retune_status`, `rows`);
  - plan 1's `MainWindow.prefix`, `pool`, `tick`, `live`, `loading`, `run_button` and its `held`;
  - `messages.reason`.
- Produces:
  - `control._env() -> dict`: `os.environ` without `KICAD_API_SOCKET` and `KICAD_API_TOKEN`. `start` uses it too.
  - `control.apply(prefix: list[str], project: Path, assignments: list[str]) -> tuple[int, list[str]]`: runs `[*prefix, "retune", str(project), *assignments]` to its end with `subprocess.run`: stdin closed (`DEVNULL`), no console window (`creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0`), `env=_env()`, and stdout and stderr captured as UTF-8 text with errors replaced. It returns the exit code and `(stdout + stderr).splitlines()`, and raises an OSError when the program cannot start. It carries `# ponytail: the pool's one thread waits for retune (2–4 s), so a project read queued meanwhile waits too; a pool of two if that matters`.
  - `ResultsView.apply_button` (G_APPLY), inserted into `buttons` at index 2, before `retune_status`.
  - `MainWindow.applying: Future | None`.
  - `MainWindow.changes() -> list[str]`: `control.changed(self.opened.project, self.path.parent, rows)` with the view's rows. It returns [] without rows, without a read, or without a project.
  - `MainWindow.apply()`: `self.applying = self.pool.submit(control.apply, self.prefix, self.path, self.changes())`, `retune_status` shows G_APPLYING, then `self.tick()`. With no changes, retune writes the outputs alone (C-19), which a run's E_RESULTS_WRITE advises.
  - `MainWindow.applied(done: Future)`:
    - Exit code 0 shows `render("G_APPLIED", folder=str(self.path.parent / "results"))`.
    - Any other exit code shows the lines joined by "\n": the CLI's own text, because the subprocess prints rendered lines. It carries `# ponytail: retune prints rendered lines, not codes, so its refusals read in the CLI's words (E_LOCKED's STOP); retune writing events would let the window word them`.
    - An OSError shows G_START_FAILED (`program=self.prefix[0]`, `reason=reason(e)`); any other exception shows `control.message(e)`.
  - **`open_project`** also sets `applying` to None: a retune of the previous project ends on its own on the pool, and nothing polls it.
  - **`tick()`:**
    - After its read, a done `applying` is taken and handed to `applied`. The stamp check that follows reads project.json again when retune saved it, which rebuilds the session.
    - `results.retune_box` is enabled while no read goes on (Task 3) and `applying` is None, so the table, S2P file…, Revert and Apply all wait for Apply's re-read.
    - `results.apply_button` is enabled while `applying` is None, no read goes on, nothing watched goes on (`live`), no lock holder lives (`held`, a retune's included) and the last read has results. It starts disabled.
    - `run_button` also waits for `applying` to be None.
  - CATALOG:
    - `"G_APPLY": "Apply"`
    - `"G_APPLYING": "Applying: retune stores the changed values in project.json and writes results/…"`
    - `"G_APPLIED": "Applied: project.json holds these values, and {folder} holds their outputs."`

- [ ] **Step 1: Write the failing tests.** In `tests/test_gui_control.py`:

```python
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
```

  In `tests/test_gui.py`:

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q`. Expected: FAIL with `AttributeError: ... no attribute 'apply'` and `AttributeError: 'ResultsView' object has no attribute 'apply_button'`.
- [ ] **Step 3: Implement** the Interfaces. `apply_button.clicked` connects to `self.apply`.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py tests/test_gui_control.py tests/test_gui.py
git commit -m "feat(gui): Apply runs retune as a short subprocess, refused while the lock is held, and the window reads the project back (Stage 2 design 5.3)"
graphify update .
```

---

### Task 6 [code]: Verify, with the stale indicator

**Files:**
- Modify:
  - `src/kicad_rf_studio/gui/control.py` (`verify_stale`, `verify_lines`; `Opened.verified`; `open_project`, L146–169; one `GUI` entry);
  - `src/kicad_rf_studio/gui/window.py`:
    - in `ResultsView`: `header`, `footer`, `stale`, `verify_button`, `verify_lines`, and `display`;
    - in `MainWindow`: `verify_next`, `verify`, `show_stale`, `applied`, `retune`, `revert`, `show_project`, `show_event` (L210–220), `open_project`, the tick, and `start`'s docstring;
  - `src/kicad_rf_studio/core/messages.py`;
  - `tests/fake_cli.py` (its `__main__` block, L19–22).
- Test: `tests/test_gui_control.py`; `tests/test_gui.py` (`from test_verify import verified`).

**Interfaces:**
- Consumes:
  - plan 1's `MainWindow.start(command)`, `watch`, `show_event`, `ask`, `run_status`, `log`, and `control.Tail`;
  - Task 5's `changes`, `apply`, `applied` and `applying`;
  - `values.port_value`, `core.project.parts`;
  - in tests, test_verify's `verified`.
- Produces:
  - `control.verify_stale(project: dict, rows: list[Row]) -> str | None`:
    - "G_VERIFY_NONE" without a verify block it can read: none, or a hand edit that is not an object with `base_hash` and an object of `values`;
    - "G_VERIFY_STALE" when `verify["base_hash"]` is not `project["results"]["model_hash"]` (a run since), or when a row's value differs by `port_value(ref, ...)` from `verify["values"].get(ref, "")`. A row with an S2P file counts with its part's stored value: Apply keeps that value, and verify runs it, not the file (C-38);
    - else None.
  - `control.verify_lines(project: dict | None) -> list[tuple[str, dict]]`: the `result` events of `Path(project["verify"]["run_dir"]) / "events.jsonl"`, in order, as `(code, params)`, read with `Tail` until it returns nothing. It returns [] without a verify and on any exception (a folder that cannot be read, a hand-edited block), so `open_project` still never raises. It carries `# ponytail: reads verify's whole events.jsonl on each project read (MBs after a long verify); its result lines are its last, so the last 64 KiB would do, as last_event reads`.
  - `control.Opened` gains `verified: list[tuple[str, dict]] = field(default_factory=list)`. `open_project` fills it with `verify_lines(project)`.
  - `control.GUI` gains `"E_VERIFY_VALUE": "G_VERIFY_VALUE"`: Verify's refusal shows in the Run tab, and the CLI's advises `retune PROJECT`.
  - `tests/fake_cli.py`: in `__main__`, when `$KRS_FAKE_CBOX` is set, `from kicad_rf_studio.core.model import spec` and `spec.c_box = lambda *args: float(os.environ["KRS_FAKE_CBOX"])` before `cli.main()`. This is the cell capacitance a detached verify reads from the fake's empty operator dump, as test_verify's `verified()` patches it in-process.
  - **`ResultsView`:**
    - the row `header: QHBoxLayout` (`what_if`, then `stale: QLabel` and `verify_button` (G_VERIFY)) takes `what_if`'s place in the view's column, and the row `footer: QHBoxLayout` (`lines`, then `verify_lines: QListWidget`) takes `lines`' place;
    - `display` fills `verify_lines` with `control.text` of `opened.verified`. `verify_button` and `verify_lines` show only with part rows.
  - **`MainWindow`:**
    - `verify_next: bool = False`.
    - `verify()`, on `verify_button`: with `self.changes()` it asks `render("G_APPLY_FIRST")`; Yes sets `verify_next` and calls `apply()`, and No does nothing. Without changes it calls `self.start("verify")`, with no cost confirmation of its own (design §5.3).
    - `show_stale()`: `control.verify_stale(self.opened.project, rows)` with the view's rows, None without rows. Its code's text goes in `stale`, which is shown only with a code.
    - `retune()`, `revert()` and `show_project` end with `show_stale()`; `open_project` calls it too (no rows: hidden), and sets `verify_next` to False.
    - `applied()` takes `then, self.verify_next = self.verify_next, False` first, and after exit code 0 with `then` calls `self.start("verify")`. A refused Apply starts nothing.
    - `show_event`: the end event of a verify this window started (`self.command == "verify"`) reads the project again (`load()`), as a cost's exit-0 end does: verify writes its result events after it saves project.json, so the read that save started may miss them.
    - Among the tick's buttons, `results.verify_button` is enabled while `applying` is None, no read goes on, nothing watched goes on (`live`), no holder lives (`held`) and the last read has results. It starts disabled.
  - CATALOG:
    - `"G_VERIFY": "Verify"`
    - `"G_VERIFY_NONE": "Not verified yet: Verify runs a full simulation of the stored values, with each part in the grid."`
    - `"G_VERIFY_STALE": "Verify is stale: the values or the model changed since the last verify."`
    - `"G_APPLY_FIRST": "Verify runs the values stored in project.json, and these are not applied yet. Apply them, then verify?"`
    - `"G_VERIFY_VALUE": "Verify puts each part in the grid at its value, but {ref} has \"{value}\": Verify can place only a C, L or R whose value reads (a C above 0). Set {ref}'s value in Advanced (under chain.series, chain.shunt or others), which keeps its S2P file, or clear the file in its row in Results and retune and type the value there, which Apply stores without the file; then press Verify again."`

- [ ] **Step 1: Write the failing tests.** In `tests/test_gui_control.py`:

```python
def test_verify_is_stale_until_it_ran_these_values_on_this_model(tmp_path):  # design 5.3 What-if, Verify
    project = {**lpf(), "results": {"model_hash": "M"}}
    rows = control.rows(project, tmp_path, ["C1", "L1", "C2", "C3"])
    assert control.verify_stale(project, rows) == "G_VERIFY_NONE"
    for broken in ({}, {"base_hash": "M", "values": []}):  # hand edits: read as no verify
        assert control.verify_stale({**project, "verify": broken}, rows) == "G_VERIFY_NONE"
    values = {"C1": "100pF", "L1": "15nH", "C2": "3p3", "C3": "3.3pF"}
    project["verify"] = {"base_hash": "M", "values": values, "run_dir": str(tmp_path / "v")}
    assert control.verify_stale(project, rows) is None  # 3p3 reads as 3.3pF
    with_file = [*rows[:2], replace(rows[2], value="4.7pF", s2p="c2.s2p"), rows[3]]
    assert control.verify_stale(project, with_file) is None  # a part with a file: verify runs its stored value
    assert control.verify_stale(project, [*rows[:2], replace(rows[2], value="4.7pF"), rows[3]]) == "G_VERIFY_STALE"
    assert control.verify_stale({**project, "results": {"model_hash": "N"}}, rows) == "G_VERIFY_STALE"  # a run since
    assert control.verify_lines(project) == [] == control.verify_lines(None) == control.verify_lines({"verify": {}})
    (tmp_path / "v").mkdir()
    events = [("progress", "I_PROGRESS", {}), ("result", "I_VERIFY_COMPARE", {"x": 1}),
              ("message", "E_RESULTS_WRITE", {}), ("result", "I_VERIFY_SCOPE", {})]
    (tmp_path / "v" / "events.jsonl").write_text("".join(
        json.dumps({"t": 0, "kind": k, "job": None, "code": c, "params": p}) + "\n" for k, c, p in events),
        encoding="utf-8")
    assert control.verify_lines(project) == [("I_VERIFY_COMPARE", {"x": 1}), ("I_VERIFY_SCOPE", {})]
```

  In `tests/test_gui.py`:

```python
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q`. Expected: FAIL with `AttributeError: ... no attribute 'verify_stale'` and `AttributeError: 'ResultsView' object has no attribute 'stale'`.
- [ ] **Step 3: Implement** the Interfaces. `start`'s docstring says "(cost, run or verify)". Plan 1's watch already sends a verify to the Run tab and `run_status`.
- [ ] **Step 4: Run them again.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py tests/test_verify.py -q`. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py tests/fake_cli.py tests/test_gui_control.py tests/test_gui.py
git commit -m "feat(gui): Verify runs detached, asks to Apply first, and shows its comparison with the stale indicator (Stage 2 design 5.3)"
graphify update .
```

---

### Task 7 [code]: The Advanced tab

**Files:**
- Modify:
  - `src/kicad_rf_studio/gui/control.py` (`Field`, `UNITS`, `fields`, `edited`; `Opened.stored`; `open_project`; one `GUI` entry);
  - `src/kicad_rf_studio/gui/window.py` (`AdvancedView`; in `MainWindow`: `advanced`, `save`, `show_project`, `open_project`, the tick; imports `check_project`, `load_project`, `save_project`);
  - `src/kicad_rf_studio/core/messages.py`.
- Test: `tests/test_gui_control.py`; `tests/test_gui.py`.

**Interfaces:**
- Consumes:
  - `core.project`'s `check_project`, `save_project`, `load_project`, `HARMONICS`, `DEFAULT_PRESET`, `BAND_FACTOR`, `T_MAX_S`, `EXPAND_H`, `MARGIN_SCALE`, `MESH_N`, `REACH_H` and `GATES`;
  - `runs.project_lock` (results/ as its run folder, as `pipeline.retune` takes it);
  - Task 2's `control.message`; Task 5's `applying`.
- Produces:
  - `control.Field`, a frozen dataclass:
    - `name: str`: a dotted path as shown, such as `region.expand_h` or `chain.series[2].role`;
    - `path: tuple`: the keys and indices down to the leaf;
    - `value: object`;
    - `default: str`: the default as JSON text, "" for none;
    - `unit: str | None`: a G_UNIT_ code.
  - `control.UNITS = {"f0_hz": "G_UNIT_HZ", "t_max_s": "G_UNIT_S", "region.expand_h": "G_UNIT_SUBSTRATE", "mesh.reach_h": "G_UNIT_SUBSTRATE", "lid_height_mm": "G_UNIT_MM", "layers[].thickness_mm": "G_UNIT_MM", "reference.point": "G_UNIT_MM", "model.esl_h": "G_UNIT_HENRY", "model.esr_ohm": "G_UNIT_OHM", "model.cp_f": "G_UNIT_FARAD"}`. It is looked up with a field's last two keys, its indices written as `[]`, so every part's model, in chain.series, chain.shunt and others, gets its unit.
  - `control.fields(data: dict) -> list[Field]`: every leaf of project.json in file order, except under `schema`, `results` and `verify`. Dicts are walked, and so are non-empty lists whose items are all dicts; any other value is a leaf.
    - The defaults are `{"harmonics": HARMONICS, "preset": DEFAULT_PRESET, "band_factor": BAND_FACTOR, "t_max_s": T_MAX_S, "region.expand_h": EXPAND_H, "region.margin_scale": MARGIN_SCALE, "mesh.n": MESH_N.get(str(data.get("preset")), MESH_N[DEFAULT_PRESET]), "mesh.reach_h": REACH_H, "lid_height_mm": None, "lid": None, "gates.fit2d_limit": GATES["fit2d_limit"], "gates.dt_floor": GATES["dt_floor"], "allow_curve_port": False}`, each shown as `json.dumps`. The `str()` keeps a hand-edited preset that is not text (a list) from raising: unchecked data is what Advanced is there to fix.
    - It carries `# ponytail: a list of objects can be edited but not grown, and a reference cannot switch between pad and point here; a text editor does both`.
  - `control.edited(data: dict, edits: dict[tuple, str]) -> dict`: a deep copy with each path's leaf set to `json.loads(text)`. A text that is not JSON stays the text itself, so `draft` needs no quotes.
  - `control.Opened` gains `stored: dict | None = None`: project.json as `load_project` reads it, unchecked, so that a field the checks refuse can be fixed here. It is None when project.json cannot be read. `open_project` keeps the project read, else `load_project(path)`, in the block that finds the board file; when only the board file fails, `stored` is still kept.
  - `control.GUI` gains `"E_PROJECT_FIELD": "G_PROJECT_FIELD"`: Advanced shows it, and the CLI's advises `new`.
  - `window.AdvancedView(QWidget)`:
    - `table: QTableWidget(0, 4)`, with headers G_COL_FIELD, G_COL_VALUE, G_COL_DEFAULT and G_COL_UNIT. Value, as `json.dumps(value, ensure_ascii=False)`, is the only editable column, and it stretches.
    - `save_button` (G_SAVE, starting disabled), `status: QLabel` (word-wrapped), `edits: dict[tuple, str]`, and `paths: list[tuple]`, one per row.
    - `display(stored: dict | None)`: the table refilled from `control.fields` (empty for None), with its signals blocked, and `edits` cleared. `status` is left as it is. It carries `# ponytail: a re-read refills the table and drops unsaved edits; carry them per field, as the retune's rows are, if users lose work`.
    - `item_changed(item)`: `edits[self.paths[item.row()]] = item.text()`.
  - `MainWindow.advanced`: the fifth tab, G_TAB_ADVANCED. `show_project` ends with `self.advanced.display(opened.stored)`; `open_project` calls `self.advanced.display(None)`.
  - `MainWindow.save()`, on `save_button`:
    - Under `runs.project_lock(self.path, self.path.parent / "results")`: `data = control.edited(load_project(self.path), self.advanced.edits)`, then `save_project(self.path, check_project(data, self.path))`. project.json is read afresh under the lock, as run, verify and retune read it, so a save never writes back a stale snapshot, and no engine writer runs meanwhile.
    - An OSError gives `render("G_SAVE_FAILED", path=str(self.path), reason=reason(e, "cannot be written"))`. Any other exception gives `control.message(e)`: E_LOCKED reads as G_LOCKED, E_PROJECT_FIELD as G_PROJECT_FIELD.
    - On success, `status` shows `render("I_WROTE", path=self.path)`, then `self.tick()`. Its stamp check reads the project again, which marks the results stale when the model changed.
  - Among the tick's buttons, `advanced.table` is enabled while no holder lives, and `advanced.save_button` while no holder lives, `applying` is None, no read goes on, and `edits` is not empty.
  - CATALOG:
    - `"G_TAB_ADVANCED": "Advanced"`
    - `"G_COL_FIELD": "Field"`, `"G_COL_DEFAULT": "Default"`, `"G_COL_UNIT": "Unit"`
    - `"G_SAVE": "Save"`
    - `"G_SAVE_FAILED": "Cannot save {path}: {reason}. Close the program that holds it open, then save again."`
    - `"G_PROJECT_FIELD": "{path}: {field} is missing or is not {expected}. Fix it in Advanced, or create the project again with New from a board."`
    - `"G_UNIT_HZ": "Hz"`, `"G_UNIT_S": "s"`, `"G_UNIT_MM": "mm"`, `"G_UNIT_SUBSTRATE": "substrate heights"`, `"G_UNIT_HENRY": "H"`, `"G_UNIT_OHM": "Ω"`, `"G_UNIT_FARAD": "F"`

- [ ] **Step 1: Write the failing tests.** In `tests/test_gui_control.py`:

```python
def test_the_advanced_fields_are_project_jsons_leaves_with_their_defaults_and_units():  # design 5.3 Advanced
    project = {**lpf(), "results": {"run_dir": "R"}, "verify": {"values": {}}}
    by = {f.name: f for f in control.fields(project)}
    assert list(by)[:5] == ["board.path", "board.sha256", "f0_hz", "harmonics", "preset"]
    assert not [name for name in by if name.startswith(("schema", "results", "verify"))]  # records, not settings
    assert (by["t_max_s"].value, by["t_max_s"].default, by["t_max_s"].unit) == (4e-08, "4e-08", "G_UNIT_S")
    assert (by["mesh.n"].default, by["lid_height_mm"].default, by["f0_hz"].default, by["f0_hz"].unit) == (
        "2", "null", "", "G_UNIT_HZ")
    assert (by["chain.series[0].model.esl_h"].unit, by["stackup.layers[0].thickness_mm"].unit) == (
        "G_UNIT_HENRY", "G_UNIT_MM")
    role = by["chain.series[2].role"]
    assert (role.path, role.value) == (("chain", "series", 2, "role"), "copper")
    assert by["classes.gnd_nets"].value == ["GND"]
    broken = {f.name: f for f in control.fields({**project, "preset": ["draft"]})}  # a hand edit to fix here
    assert broken["mesh.n"].default == "2"
    new = control.edited(project, {("preset",): "draft", ("t_max_s",): "3e-08", ("lid",): "false",
                                   ("classes", "gnd_nets"): '["GND", "AGND"]'})
    assert (new["preset"], new["t_max_s"], new["lid"], new["classes"]["gnd_nets"]) == ("draft", 3e-08, False,
                                                                                         ["GND", "AGND"])
    assert project["preset"] == "normal"  # a copy: nothing is saved until Save


def test_open_project_keeps_project_json_as_stored_for_advanced(tmp_path, fake):  # design 5.3 Advanced
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    save_project(pj, {**load_project(pj), "harmonics": 0})  # a hand edit the project's checks refuse
    broken = control.open_project(pj)
    assert broken.problem[0] == "E_PROJECT_FIELD" and broken.project is None and broken.stored["harmonics"] == 0
    assert control.open_project(tmp_path / "nope.json").stored is None
```

  In `tests/test_gui.py`:

```python
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
    a.save_button.click()
    assert (load_project(pj)["t_max_s"], parts(load_project(pj))["C3"]["value"]) == (3e-08, "3.9pF")
    assert a.status.text() == render("I_WROTE", path=pj)
    opened(w)  # the new mtime read the project again: its model changed, so its results are stale
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
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q`. Expected: FAIL with `AttributeError: ... no attribute 'fields'` and `AttributeError: 'MainWindow' object has no attribute 'advanced'`.
- [ ] **Step 3: Implement** the Interfaces.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py tests/test_gui_control.py tests/test_gui.py
git commit -m "feat(gui): the Advanced tab edits project.json's fields with their defaults and units, saved under the project lock (Stage 2 design 5.1, 5.3)"
graphify update .
```

---

### Task 8 [code]: About

**Files:**
- Modify:
  - `src/kicad_rf_studio/gui/control.py` (`DEPENDENCIES`, `about`);
  - `src/kicad_rf_studio/gui/window.py` (the Help menu in `MainWindow.__init__`; `about`, `about_qt`);
  - `src/kicad_rf_studio/core/messages.py`.
- Test:
  - `tests/test_gui_control.py` (imports `tomllib`, `from importlib import metadata` and `from kicad_rf_studio import __version__`);
  - `tests/test_gui.py` (`QMessageBox` beside `QFileDialog`).

**Interfaces:**
- Consumes: `kicad_rf_studio.__version__` ("0.1.0.dev0"), `importlib.metadata.version`.
- Produces:
  - `control.DEPENDENCIES`: the runtime dependencies with their main licences:

    ```python
    (("PySide6-Essentials", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
     ("shiboken6", "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
     ("matplotlib", "Matplotlib License (PSF-based)"), ("numpy", "BSD-3-Clause"), ("scipy", "BSD-3-Clause"),
     ("h5py", "BSD-3-Clause"), ("shapely", "BSD-3-Clause"), ("scikit-rf", "BSD-3-Clause"),
     ("pandas", "BSD-3-Clause"), ("openEMS", "GPL-3.0-or-later"), ("CSXCAD", "LGPL-3.0-or-later"))
    ```

  - `control.about() -> str`: G_ABOUT_TEXT rendered with the version and the dependencies: one G_ABOUT_DEPENDENCY line per entry of DEPENDENCIES, in order, joined by newlines, its version `metadata.version(name)`, or `render("G_NOT_INSTALLED")` on `PackageNotFoundError`.
  - `MainWindow`: a `menuBar()` menu G_MENU_HELP, holding `about_action` (G_ABOUT, triggering `about()`) and `about_qt_action` (G_ABOUT_QT, triggering `about_qt()`).
    - `about()`: `QMessageBox.about(self, render("G_ABOUT"), control.about())`.
    - `about_qt()`: `QMessageBox.aboutQt(self)`.
  - CATALOG:
    - `"G_MENU_HELP": "Help"`
    - `"G_ABOUT": "About kicad-rf-studio"`
    - `"G_ABOUT_QT": "About Qt"`
    - `"G_ABOUT_DEPENDENCY": "{name} {version}: {licence}"`
    - `"G_NOT_INSTALLED": "not installed"`
    - `"G_ABOUT_TEXT": "kicad-rf-studio {version}: simulates the RF parts of a KiCad board with openEMS.\n\nCopyright (C) 2026 the kicad-rf-studio contributors.\n\nThis program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program comes with ABSOLUTELY NO WARRANTY. It includes a copy of CSXCAD's SmoothMeshLines under the GNU Lesser General Public License, version 3 or later. Both licences are at https://www.gnu.org/licenses/.\n\nRuntime dependencies (installed by pip, or by you for openEMS and CSXCAD; not included):\n{dependencies}"`

- [ ] **Step 1: Write the failing tests.** In `tests/test_gui_control.py`:

```python
def test_about_names_the_version_the_licence_notices_and_each_runtime_dependency(monkeypatch):  # design 5.3 About
    real = metadata.version

    def version(name):
        if name in ("openEMS", "CSXCAD"):  # installed apart from pip, if at all
            raise metadata.PackageNotFoundError(name)
        return real(name)

    monkeypatch.setattr(metadata, "version", version)
    text = control.about()
    assert text.startswith(f"kicad-rf-studio {__version__}: ") and "ABSOLUTELY NO WARRANTY" in text
    assert "Copyright" in text and "GNU General Public License" in text  # GPL-3.0's appropriate legal notices
    assert "https://www.gnu.org/licenses/" in text  # GPL-3.0 §5(d)
    for name, licence in control.DEPENDENCIES:
        shown = render("G_NOT_INSTALLED") if name in ("openEMS", "CSXCAD") else real(name)
        assert render("G_ABOUT_DEPENDENCY", name=name, version=shown, licence=licence) in text.splitlines()
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {re.split(r"[<>=!~;\[ ]", d, maxsplit=1)[0].lower() for d in pyproject["project"]["dependencies"]}
    assert declared <= {name.lower() for name, _ in control.DEPENDENCIES}  # every core dependency is named
```

  In `tests/test_gui.py`:

```python
def test_the_help_menu_shows_about_and_qts_about(window, monkeypatch):  # design 5.3 About
    seen = []
    monkeypatch.setattr(QMessageBox, "about", lambda parent, title, text: seen.append((title, text)))
    monkeypatch.setattr(QMessageBox, "aboutQt", lambda parent, title="": seen.append("Qt"))
    w = window()
    assert [a.text() for a in w.menuBar().actions()] == [render("G_MENU_HELP")]
    w.about_action.trigger()
    w.about_qt_action.trigger()
    assert seen == [(render("G_ABOUT"), control.about()), "Qt"]
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_gui.py -q`. Expected: FAIL with `AttributeError: ... no attribute 'about'` and `AttributeError: 'MainWindow' object has no attribute 'about_action'`.
- [ ] **Step 3: Implement** the Interfaces.
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py tests/test_gui_control.py tests/test_gui.py
git commit -m "feat(gui): About shows the version, the licence notices and the runtime dependencies, and Qt's About (Stage 2 design 5.3)"
graphify update .
```

---

### Task 9 [run]: The controller's offscreen visual review

This task commits nothing. The PNGs and the font plugin stay outside the repo.

- [ ] **Step 1: Write the font plugin.** Offscreen Qt on Windows has no fonts, so grabs draw every glyph as a box (plan 1's Task 10). Write `krs_font.py` into `$env:TEMP\krs-font` (made with `New-Item -ItemType Directory -Force`):

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
```

- [ ] **Step 2: Grab every screen.** In PowerShell from the repo root:

  `$env:PYTHONPATH = "$env:TEMP\krs-font"; $env:KRS_GRAB_DIR = "$env:TEMP\krs-grabs-plan2"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q -p krs_font; Remove-Item Env:KRS_GRAB_DIR, Env:PYTHONPATH`

  Expected: all pass. The folder holds `new.png`, `retune.png`, `verify.png` and `advanced.png`, beside plan 1's seven.
- [ ] **Step 3: Look at each PNG** with the Read tool, at 1200 × 800, and check:
  - **All screens:** every word comes from the catalog, in English, legible and unclipped. The tabs read Project, Cost, Run, Results and retune, Advanced, and the Help menu is there.
  - **new:** Open and its line sit above the "New from a board" group. The group shows:
    - Board with Browse…;
    - empty start and end pickers;
    - f0, and Harmonics 3;
    - Preset normal, and Stackup "The board's own";
    - Shield lid height "none";
    - Project folder with Browse…;
    - Create the project.
  - **retune:**
    - the what-if banner, with Verify and "Not verified yet: …" beside it;
    - the parts table (Part, Value, Snapping, S2P file, S2P fixture) with C2 at 5.1pF and E24 on every row;
    - S2P file…, Revert and Apply;
    - three panels with the moved curves, and the lines below, beside the empty verify list.
  - **verify:**
    - the banner with Verify, and no stale indicator;
    - C2 at 4.7pF;
    - G_APPLIED;
    - the verify lines beside the result lines.
  - **advanced:** Field, Value, Default and Unit columns; t_max_s reads 4e-08, 4e-08, s; Save is disabled.
- [ ] **Step 4: Fix what fails.**
  - Each defect becomes a [code] fix in the owning task's file. It is test-first where a test can see it: a widget's text, visibility or enabled state.
  - Each fix is committed as `fix(gui): ...` after the full suite; then Step 2 runs again.
  - A grab of a word-wrapped QLabel taken without an event loop may keep its old height. That is an artifact of `grab()`, as plan 1's run-lost.png showed, not a defect.

---

## Not in this plan

- **The KiCad button (plan 3):**
  - the helper and the handoff that pre-fills the New form (`new_form.board`, `board_chosen()`, then `start` and `end` once `pads_read` ends);
  - narrowing the pad picker to a selected footprint, and the swap;
  - the single instance, refill and save, `install-kicad-plugin`, and kicad-python and its §3.4 pin.
- **Install and release (plan 4):**
  - the README's install section;
  - NOTICE's "Runtime dependencies (not included)", which copies `control.DEPENDENCIES`;
  - the release check, and the offscreen fonts its grabs need;
  - §5.11's real end-to-end run: New on lpf915 at Draft, Cost, Run, a retune with snapping, Apply and Verify, through these code paths.
- **A cache of S2P impedances by (file, mtime_ns), or reading them on the pool.** Measured on lpf915, each S2P part adds its file's read to every update: 2 ms at 401 points, 5 ms at 1601 and 19 ms at 6401. One file stays under the 50 ms budget; four of 6401 points do not, and a file on a slow network share stalls the update for as long as its read. There is a ponytail note in `retuned`.
- **The GUI's own wording of Apply's lines** (E_LOCKED's STOP advice, E_RESULTS_WRITE's command). The subprocess prints rendered text, not codes; a wording would need retune to write events (ponytail note in `applied`).
- **G_ wording for the `preview` advice** of W_LOSS_BUDGET, W_VERIFY_LOSS_BUDGET and E_CBOX. The window has no Preview (design §6), so the CLI's command stays the advice, as plan 1 left W_LOSS_BUDGET.
- **A cost confirmation for Verify.** Design §5.3: its own cost lines show live, with Stop.
- **A test of a verify outliving its window.** Verify starts and is watched through plan 1's `start`, `watch` and `closeEvent`, which plan 1's run test pins; Task 6's lock step pins what a holder disables.
- **Growing a list or switching a reference between pad and point in Advanced.** A text editor does both (ponytail note).
- **Carrying unsaved Advanced edits over a re-read.** Save is one click away, and the retune's rows are carried per part (ponytail note in `AdvancedView.display`).
- **Fixed-height status lines.** A status line that changes height resizes the canvas, which costs one full redraw on that edit (ponytail note in `blit`).
- **Preview and Calibrate buttons:** optional (design §6).
- **Qt's own translations and the pt-BR catalog:** after v1 (design §5.7).

## Controller rulings (2026-10-28; binding)

The architect's rulings, revised after the four reviews (coverage, feasibility, a GUI that never freezes, quality). Each is a controller recommendation, owner unavailable.

- Ruling: nine tasks, not the suggested eight: the two engine hooks fold into Task 1 (`chain_results`' `lay` keyword and `value_text`, a few lines that only the session needs), and the Results tab is two tasks, the retune table (Task 3) and the curves moved in place and blitted (Task 4) — each is a change a reviewer can pass or reject on its own, as plan 1 split its window in two, and the blit is the plan's riskiest Qt mechanism — cost if wrong: one more review gate.
- Ruling: there is no separate session object. The session is plan 1's project read: `Opened.project` and `ChainResults.lay`, read on the pool and read again on every change of project.json or the board. An update is `control.retuned`: assign on the changed rows, then `chain_results` on the held layout. It never raises: a refusal, or any other exception as E_INTERNAL, becomes the lines' one line with no chain — the design's "in-memory session built once and rebuilt when the results change" with the CLI's own reading and chain, no second code path, numbers and lines pinned equal to `retune`'s (probed: difference 0.0, lines equal), and no stale curve left on screen by an exception in a slot — cost if wrong: a session that needs state beyond the read becomes a dataclass in control.py.
- Ruling: a read carries the rows over part by part (`control.carried`). A row the user changed is kept when the new read holds its part exactly as the last one did, and is replaced by the stored row, with G_DROPPED, when the read changed or lost that part. The Snapping choices stay per part (`ResultsView.series`) until another project opens, and kept rows are computed again on the new read's layout (`retune()`) — design 5.3 rebuilds the session "when the results change", and a cost's, a run's or a verify's end, a board save and an Advanced Save all read project.json again without touching the parts; keeping a row whose part changed would silently undo that change on the next Apply — cost if wrong: a value whose part project.json changed is typed again (ponytail note).
- Ruling: no S2P cache — measured on lpf915, each S2P part adds its file's read to every update: 2, 5 and 19 ms for files of 401, 1601 and 6401 points. One file stays under design goal 4's 50 ms; four 6401-point files come to about 80 ms — cost if wrong: a ponytail note in `retuned` names the upgrade (a cache by (file, mtime_ns), or the read on the pool).
- Ruling: blitting is in (Task 4) — measured offscreen at 1180 × 520, a redraw after `set_data` takes 103–108 ms with the constrained layout (about 50 ms with the layout engine off), over design 5.4's 50 ms; a blit takes 1.1–1.6 ms, and `grab()` sees it. The curves are animated, `on_draw` re-captures the background on every full draw (resize included), and a test pins that an update never calls `canvas.draw` and that an edit's whole GUI-thread path (snapping, retuned, the retrace, the lines, the blit) stays under 50 ms. Two cases still draw in full, as Revert does: the first good value after a refusal cleared the plot, and an edit whose status line changes height (G_APPLIED cleared, the stale indicator lit), which resizes the canvas. Both are rare — cost if wrong: about 25 lines in `ResultsView`; hidden curves on a refusal, or fixed-height status lines, if those draws are felt (ponytail notes).
- Ruling: the fixed limits are those of the last full draw: the stored values', or the first good values after a refusal. Revert and the re-read after Apply draw again — design 5.4's fixed limits, without a policy of their own — cost if wrong: a far-off retune clips until Revert (ponytail note).
- Ruling: Results and Retune share one tab, "Results and retune" (G_TAB_RESULTS's text) — one canvas, one label, one lines list; the stored results are the retune at the stored values, so the two views could only disagree — cost if wrong: a catalog line, and a second tab if the owner wants them apart.
- Ruling: snapping applies only when a row's value is committed or its series changes. Opening shows the stored texts unchanged. The default is E24 for a C or an L, and off for an R or any other part. A value that does not read, is 0 or is not finite is left as typed — design §5.3 defaults each part's control to E24, and §7's owner default narrows it to "E24 for L and C, set per part"; snapping on open would make unasked changes; `snap` cannot take infinity (probed: OverflowError on a 400-digit value) — cost if wrong: one line in `default_series`.
- Ruling: `value_text` lives in values.py beside `parse_value` and `snap`, with engineering prefixes and the `1e-9` floor tolerance; the round trip is pinned for every E24 value from 1e-13 to 9.1e9 for C, L and R (probed) — the writer belongs next to the reader it must satisfy — cost if wrong: none.
- Ruling: a value that does not read, or a part's refusal, clears the plot and shows the refusal as the lines' last line in the GUI's words; the row keeps its text — no curve under the what-if label for values that do not read (anti-goal: a weak label) — cost if wrong: one branch in `show_chain`.
- Ruling: only changed rows reach assign and Apply, and S2P files go absolute against the project's folder, resolved as `part_impedances` resolves them. Unchanged parts stay as stored, so a stored part with no readable value shows E_PART_NO_VALUE, not E_RETUNE_VALUE; assign reads a relative file from the working directory, which a GUI does not have. Apply's enabled state never calls `changes()`, so no path is resolved on every tick — cost if wrong: none.
- Ruling: fifteen more CLI codes get GUI wording through `control.GUI`. For New: E_PROJECT_EXISTS, E_OUTPUT_PATH, E_NO_STACKUP, E_STACKUP_LAYERS, W_LID_HEIGHT_MISSING, I_PART_NO_MODEL and W_NO_REFERENCE. For the retune: E_RETUNE_VALUE, E_PART_NO_VALUE, E_S2P_MISSING, E_S2P_UNREADABLE, E_S2P_BAND and W_S2P_FIXTURE. Verify's E_VERIFY_VALUE and Advanced's E_PROJECT_FIELD. A generic test pins the same params and no terminal syntax. W_LOSS_BUDGET, W_VERIFY_LOSS_BUDGET and E_CBOX keep the CLI's `preview` advice, since the window has no Preview (design §6), and so do Apply's printed lines — these name options (`-o`, `--stackup`) or commands (`retune PROJECT …`, `new`) that the window replaces — cost if wrong: fifteen catalog lines; a CLI hint reads oddly where the window has no equivalent.
- Ruling: Apply is `subprocess.run` on the window's pool, with stdout and stderr captured, `CREATE_NO_WINDOW` on Windows and no KiCad API variables; the tick takes its future — not detached (design 5.3), no pipe deadlock, no temporary file, and matplotlib's PNG drawn in the retune process (design 5.4) — cost if wrong: a project read queued behind Apply waits 2–4 s (ponytail note).
- Ruling: Apply shows G_APPLIED on exit code 0, and otherwise its own printed lines, in CLI text (ponytail note). Apply is enabled with no changes too: `retune PROJECT` with no assignments writes the outputs alone (C-19), which is what a run's E_RESULTS_WRITE advises when a held file stopped its outputs. E_RESULTS_WRITE keeps its CLI text, because its command is run, retune or verify by where the write failed. This settles plan 1's deferred wording — cost if wrong: the Run tab names the retune command that Apply runs, and E_LOCKED's STOP advice reads as the CLI's.
- Ruling: Apply is disabled while any lock holder lives (a retune's too), while a watched process goes on, while a project read goes on and while Apply runs. The retune box (the table, S2P file…, Revert and Apply) is disabled during a read and during Apply, and stays editable during a run. Run… also waits for Apply — design 5.1 disables Apply under the lock; r2 keeps the instant preview on but asks for a busy state while the session is read, whose last layout may belong to a model that is gone; a pick or a Revert during Apply would be undone by its re-read; a run started just before Apply's lock would refuse one of the two — cost if wrong: none.
- Ruling: `open_project` forgets the Apply going on and Verify's answer (`applying` None, `verify_next` False), and clears retune_status, the Snapping choices, the stale indicator and the Advanced table. The retune it started ends on its own, unpolled — otherwise its end would show G_APPLIED over another project, and could start a verify of hours on it, unasked — cost if wrong: none.
- Ruling: Verify runs through plan 1's `start` and watch, in the Run tab, with no cost confirmation. With unapplied values it asks G_APPLY_FIRST: Yes applies, and verify starts only after an exit-0 Apply (`verify_next`); No, or an Apply that retune refuses, starts nothing. A verify this window started reads the project again at its end event, because verify writes its result events after it saves project.json — design 5.3: verify reads project.json, and gets no separate cost confirmation — cost if wrong: a multi-hour verify starts on one click (open issue).
- Ruling: the stale indicator shows G_VERIFY_NONE without a verify block it can read (none, or a hand edit), and G_VERIFY_STALE when `base_hash` is not `results.model_hash` or a row's value (by `port_value`) differs from `verify.values`. A row with an S2P file counts with its part's stored value, which Apply keeps and verify runs. The indicator hides when verify is current — r2 §2's data; verify runs the values, not the files (C-38) — cost if wrong: one comparison.
- Ruling: verify's comparison is the result events of project.json's `verify.run_dir`, read in `open_project` (`Opened.verified`) and listed beside the Results lines; `verify_lines` never raises — the rendered I_VERIFY_* params are only in those events, and plan 1's `open_project` never raises — cost if wrong: a long verify's events file is read on each project read (ponytail note).
- Ruling: `tests/fake_cli.py` gains `$KRS_FAKE_CBOX`, the cell C a detached verify reads from the fake's empty operator dump — the in-process `verified()` patch never reaches a child process (r2 §4) — cost if wrong: test-only.
- Ruling: Advanced shows every leaf of project.json except `schema`, `results` and `verify`, as JSON text, with Default and Unit columns for the known fields, the parts' models included (H, Ω and F; the region's and the mesh's reach read "substrate heights"), each unit found by the field's last two keys. Edits parse as JSON, a bare word staying text. It reads `Opened.stored` (`load_project`, unchecked), so a refused field can be fixed in the window, and a preset that is not text still lists. Field names are project.json's own dotted keys, as the CLI's messages name them — design 5.3: every field, with its default and unit — cost if wrong: lists cannot grow there (ponytail note).
- Ruling: Advanced's Save reads project.json afresh under the project lock, with results/ as its run folder as a retune's, applies the edits, checks the result (`check_project`) and writes it (`save_project`). Save is enabled only while no holder lives, nothing applies, no read goes on and there are edits; E_LOCKED and the checks' refusals show in the window's words — design 5.1 disables model edits under the lock; every engine writer (run, verify, retune) writes under the lock from a fresh read, and a snapshot written back could undo a run's results, a verify block or Apply's values, while two writers share one temporary file (save_project's ponytail note); "a model change marks the results stale, exactly as the CLI does" through the stamp's re-read — cost if wrong: an edit whose field a newer project.json lacks ends in E_INTERNAL's line.
- Ruling: About uses a static DEPENDENCIES table with main licences and the installed versions from `importlib.metadata`, and a generic copyright holder, "the kicad-rf-studio contributors". A test checks that every pyproject dependency is listed and that the copyright line is there — the metadata's licence fields are messy (scipy, matplotlib, scikit-rf), and the identity rewrite is the owner's — cost if wrong: one table and one catalog line (open issue).
- Ruling: New's project folder defaults to the board's folder joined with the board's stem, as the README's `-o lpf915`, set when a board is chosen or the board's text changes, so a folder the user typed stays; an empty folder is refused (G_NEW_NO_FOLDER). The pad picker lists every pad with copper in natural order and stays editable. f0 parses on the GUI thread; `cli.new` runs on the pool; Create is disabled while creating — `new`'s default (the working directory) means nothing to a GUI; the engine keeps its refusals (E_START_ON_GND) — cost if wrong: the default folder is one line.
- Ruling: the lid spin box uses `QLocale.c()`, and 0 shows G_NONE (no lid height) — probed: the offscreen platform took the system's decimal comma ("2,50"), while project.json and the CLI write 2.5 — cost if wrong: none.
- Ruling: New's two futures are taken at the top of the tick, before plan 1's "no project" return; `created` opens the project, whose own tick runs inside that tick — one mechanism, the timer (plan 1) — cost if wrong: the rest of that tick runs twice, harmlessly.
- Ruling: `control.message(e)` holds the window's KrsError-or-E_INTERNAL line for its four handlers (pads, New, Apply, Save) — DRY — cost if wrong: none.
- Ruling: `ResultsView` emits `edited` (a Signal) for the window, and a row's combo finds its row through `sender()`; slots are bound methods only. Names avoid QWidget's own: `create_project`, and `header`, `buttons`, `footer` (QWidget has `create()` and `actions()`) — plan 1's rule on lambda slots — cost if wrong: none.
- Ruling: signals within the GUI thread, and the instant retune's draws in its slots, supersede plan 1's "no QThread and no signals; matplotlib draws only in the tick" — design 5.4 asks for an instant update on each edit; every result from the pool (reads, New, the pad list, Apply) is still taken only by the tick, and there is still no QThread — cost if wrong: none.
- Ruling: window.py stays one module, with `ResultsView`, `NewForm` and `AdvancedView`, superseding plan 1's "plan 2 splits Results out when the retune session grows it" — the fewest files; a view moves out when it needs tests of its own — cost if wrong: a window.py of about 600 lines.
- Ruling: `ResultsView.display(opened, folder)` replaces `display(opened, name)`, because rows resolve S2P files from the project's folder; only window code calls it — cost if wrong: none.
- Ruling: there are no Stage 1 spec amendments — nothing here changes a command, a file or an event — cost if wrong: none.
- Ruling (disclosure): the architect ran only read-only probes, on the repo's synthetic fixtures in a scratch folder, with the fake's patches and a scratch data folder:
  - an lpf915 network-fake run;
  - its read (0.78 s) and its layout (7 ms);
  - assign plus chain_results on the held layout: 5.4 ms (assign 0.06 ms);
  - S2P files of 401, 1601 and 6401 points: 7.6, 10.7 and 24.5 ms;
  - offscreen Qt: the first draw at 155 ms; a redraw after set_data at 103–108 ms (constrained) and 49–52 ms (no layout engine); a blit at 1.1–1.6 ms, and `grab()` differing after a blit;
  - the session's chain and lines against chain_results after `retune C2=4.7pF`: max difference 0.0, lines equal;
  - value_text over every E12 and E24 value from 1e-13 to 9.1e9 for C, L and R: no failure;
  - the fixtures' pad lists (lpf915: 36 names; coupon_gcpw_pads: TP1.1 and TP2.1; coupon_ms: none);
  - a 3-port file giving E_S2P_PORTS with its resolved path;
  - Qt's editable combo, itemChanged, `sender()` and the spin box's special text and decimal comma;
  - the installed licence metadata.

  The reviser ran read-only probes too: `cli.new` on a copy of lpf915 with 2 harmonics, the draft preset and the jlcpcb-2l stackup (accepted, its stackup source "jlcpcb-2l", the board's bytes unchanged); `port_value` of a 400-digit C value (inf) and `snap`'s OverflowError on it; `MESH_N.get` of a list (TypeError) and of its `str()` (the default); a shunt-measured S2P file read back to 7e-16 and, read as series, fitting shunt (W_S2P_FIXTURE); a garbage S2P file (E_S2P_UNREADABLE); and the cached `project_of` handing out the dicts that `parts()` edits. No full suite, no openEMS, no visible window — cost if wrong: none.
