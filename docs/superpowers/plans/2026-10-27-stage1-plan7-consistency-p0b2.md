# Stage 1 · Plan 7 — Consistency and P0-B2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put a fitted decaying tail on every reported S (A-9), take verify's L-strip inductance off its grid L (A-10), register the box term (A-11), bound the residual near f2 (E-9), and spend the one P0-B2 rerun only if the offline prediction on P0-B's stored records says go (E-10).

**Architecture:**
- **Product, test-first:** p7-tails' frozen v3b method in `core/post/waves.py` (`tail`, `s_matrix(..., t_free)`, `Layout.s_dft` and `Layout.fallback`), its two warnings in `pipeline.write_outputs` and `pipeline._verify`, and tails in `p0.s_of`; then `core/model/spec.strip_dl` and `verify_spec(..., compensate=True)` with E_VERIFY_STRIPS.
- **Dev tools:** A-9's judges E1–E4 as `harness.a9`. A new `tools/p0b2.py` holds A-10's single-L coupon (`single_l`, `fit_dl`, its rule `a10`, `coupon`), the go/no-go `predict` on development data, and, only on go, P0-B2's `run`, `measure`, `decide` and `write`.
- **Order:** each fix's check and decision follow its code at once, so a fail branch reverts only its own phase's commits (its tasks' and any fix commit made for its run), with nothing else on top. A-9 comes first (Tasks 1–4), then A-10 (Tasks 5–8), then the go/no-go (Tasks 9–11). P0-B2 runs only on go (Tasks 12–13). The references and the reports come last (Tasks 14–15).

**Tech Stack:** Python ≥ 3.11 (the dev venv runs 3.14). numpy for the pencil (`linalg.svd`, `pinv`, `eigvals`, `lstsq`) and the DFT. scipy for `optimize.least_squares` and `constants.mu_0`. scikit-rf through `chain.terminate`. The stdlib's `json`, `argparse`, `functools` and `pathlib`. p0's steps, records and machine time. openEMS 0.37.0 and CSXCAD 0.7.0 for Tasks 7 and 13 only. Tests run on pytest.

**Spec:** `docs/superpowers/specs/2026-10-26-engine-accuracy-design.md` §5.2 (binding), with §1–4 and §6. The controller decisions E-1..E-12 are in `.superpowers/sdd/plan7-research/controller-decisions.md` (binding), and the research is p7-tails, p7-Lcheck, p7-box and p7-gate (`findings.md` each; git-ignored, local). The engine authority is `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`:
- §6.3, "After each run", amended by A-9;
- §7.6, the inductor and k bullets, amended by A-10;
- §8's table, one row (A-9);
- §9.3, P0-B, unchanged: P0-B2 is judged by its criterion 1;
- §12, unchanged.

**Branch:** `stage1-plan7`, from `main` after plan 6's merge. This plan is `docs/superpowers/plans/2026-10-27-stage1-plan7-consistency-p0b2.md`. [code] steps run `python -m pytest` with the dev venv active. Every [run] command and every check names `.venv\Scripts\python.exe` and runs from the repo root. Placeholders:
- `<P0-2>` is `%LOCALAPPDATA%\kicad-rf-studio-p0-2`, this round's folder;
- `<P0>` is `%LOCALAPPDATA%\kicad-rf-studio-p0`, Stage 1's, frozen;
- `<R7>` is `.superpowers\sdd\plan7-research\scripts` (git-ignored).

**Before Task 1 (the controller):**
1. Plan 6 is merged into `main`, and `stage1-plan7` is branched from it; note the base commit. `git diff --stat ea0ac09 HEAD -- src tools` (the research's base) prints nothing, or `src/kicad_rf_studio/core/project.py` alone (plan 6's Task 11 comment). Otherwise the controller re-checks this plan's line references and recomputes its expected values (ΔL, the hashes, the cells) on the merged code before item 4.
2. A-9's independent data exists. Run `.venv\Scripts\python.exe -c "import json,sys; from pathlib import Path; d=Path(sys.argv[1]); rd=lambda p: json.loads((d/p).read_text(encoding='utf-8')); [print(s, [j['verdict'] for j in rd(f'steps/{s}.json')['result']['jobs']], Path(rd(p)['results']['run_dir']).name == rd(f'steps/{s}.json')['result']['run_dir']) for s, p in (('p0b-B1', 'p0b/projects/B1/project.json'), ('p0a-pad', 'p0a/projects/coupon_gcpw_pads/project.json'))]" <P0-2>`. It must print six verdicts for `p0b-B1` and two for `p0a-pad`, each one of converged, flat or t_max, and `True` twice (each project holds its step's run). If a record is missing, a job did not keep S, or a project holds another run, stop: the controller amends this plan before Task 1. Note which branch plan 6's Task 10 reported: lpf915's traces and reference regenerated from `p0b-B1`, or its lpf915 branch (both stayed Stage 1's). Task 14 follows it.
3. Copy the research scripts (the session's `s2r\p7\` folders `a9`, `a10`, `abox` and `p0b2`) into `<R7>`. They archive A-11's estimator (E-8), and Task 10's Step 1 may read them, all but `p0b2\scan.py`.
4. Commit this plan on the branch, with the rulings returned with it appended as its last section, `## Controller rulings (2026-10-27; binding)`. This commit pre-registers everything Global Constraints lists under pre-registration (design §4).

**Phases:** A-9 (Tasks 1–4); A-10 (Tasks 5–8); the go/no-go (Tasks 9–11); P0-B2, on go only (Tasks 12–13); the references and the reports (Tasks 14–15). These end the plan early:
- A-9's judges fail or cannot be computed (Task 4's fail branch): Phase 2 still runs, then Task 15. P0-B2 is a no-go by E-10, and no tail means no reference regeneration.
- A-10's check fails or is void (Task 8's fail branch): Task 14 when A-9 was adopted, then Task 15.
- The prediction says no-go, or is not trusted (Task 11): Task 14, then Task 15. P0-B2 is not spent (E-12).
- The timebox's ceiling: the branch Global Constraints name for that point.

## Global Constraints

Plan 6's and plan 5's Global Constraints carry over whole (design §4). The lines below restate the ones this plan touches.

- **Python and files:** Python ≥ 3.11 (the CI floor). Every new source file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`. Everything is in English. Dev tools print plain English; the product prints only CATALOG codes.
- **Dependencies:** the app's runtime dependencies do not change. `tools/p0b2.py` uses the stdlib, numpy, scipy, the product's modules, `p0` and `p0b.harness` only.
- **Imports:** the package never imports `tools/`. Tools import product code by module. pytest has `pythonpath = ["tools"]`.
- **Messages:** every new product string is a code in the one CATALOG of `core.messages`, with plain `{fields}` and pre-formatted numbers, and says what to do next. `render` is `str.format`. Tests check `KrsError.code` and `.params`, or the rendered line, never `match=`.
- **Units:** mm, Hz, s, Ω and H. A part box lies along x or y, so its width axis is `1 - "xyz".index(dir)`.
- **Execution model (D-5..D-10):**
  - [code] tasks are test-first.
  - Each [run] task is one background command, started by the controller and never by a subagent.
  - Tasks 7 and 13 run FDTD, one at a time, on an otherwise idle PC: no pytest, openEMS, EMerge or other run alongside. The idle check is `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'tools'); import p0; print([sum(m in c for c in p0.command_lines()) for m in p0.MARKERS])"`, which must print `[0, 0, 0]`.
  - Task 3 is CPU only and measures no time, so it needs no idle PC. It needs only that no other harness holds `<P0-2>`: `p0.enter` raises E_LOCKED otherwise.
  - From Task 3's start to Task 13's end, `src/` and `tools/` change only by the following:
    - the tasks' own commits;
    - a test-first commit that fixes a command which exited non-zero, made between runs, and only before that run's `a9.json`, `a10.json` or `p0b2.json` exists (plan 5's rule).
  - Such a fix never changes `waves.TAIL_*`, `tail`, `harness.a9`, `A9_*`, `strip_dl` or verify's compensation. Nor does it change `p0b2`'s `COUPON`, `L_COUPON`, `single_l`, `DL_BAND`, `DS21_COUPON_DB`, `FLOOR`, `fit_dl`, `a10`, `DEV`, `BANDS_GHZ`, `bands`, `predict`, `EDITS`, `STEPS`, `JOBS`, `MODE_HZ`, `project`, `measure`'s rules, `decide` or its texts, or `harness.NEW`, `harness.evidence`, `p0.summary`, `p0.criterion1` and `p0.LIMITS1`. A fix made once a step's records exist changes plumbing only (paths, I/O, parsing), never a value a rule reads. A `src/` fix after Task 11's commit reruns Task 11's `predict` before B1 reruns, and a `go` that turns false stops P0-B2, not spent. The report names every such commit, and a fail branch reverts the fix commits made for its run with its tasks' commits.
  - Nothing is committed while a run is in progress. Once P0-B2's B2 record exists, any change to `src/` spends the run (design §5.2).
  - P0 steps are resumable, keyed by model hash plus `p0.code_id()`, and a gate refuses records from two codes. The gates drive the product as subprocesses. Every dB-judged comparison runs at Normal.
  - [decide] tasks apply the pre-registered rules exactly and return each report as text.
- **The P0 folders:**
  - Every command gets `<P0-2>` explicitly (`--out`, `--p0`). The coupon (Task 7) and P0-B2 (Task 13) work in `<P0-2>\p0b2`.
  - `<P0>` stays frozen. Only `p0b2.predict` (Tasks 9–11) and Task 10's scripts read it, read-only: never `p0.enter`, never a write, never a lock.
- **Development data and independent data:**
  - *Development data* are Stage 1's `<P0>` records of P0-B: B1 (model `20f6c687…`) and B2's verify (`9cb3e824…`), that is, verify's long P1 record and the stored comparison. They developed A-9's v3b, A-10's sensitivity, A-11's estimator and the prediction. A check on them is reported, never one of A-9's judges (E-2). The rules computed on them are E-9's attribution rule (Task 10) and the go/no-go with its reproduction check (E-10, Task 11). Task 10 reads only them.
  - *Independent data* are plan 6's `p0b-B1` (lpf915 at reach 3) and P0-A's `p0a-pad` records in `<P0-2>`. Plan 6's Task 10 wrote the committed pad traces from `p0a-pad`, and lpf915's from `p0b-B1` unless it took its lpf915 branch, which left lpf915's traces Stage 1's development records. Before Task 3, no one reduces those records, `tests/fixtures/traces` or `tests/fixtures/p0d` with tails: Before Task 1's check prints verdicts and held runs only, and the suite's stop-rule replays and its plain Draft replay are exempt. Only Task 3 judges them, once. After Task 3 ran, no constant, rule or test of A-9 changes.
  - A-10 is judged on new data, the coupon (Task 7). P0-B2 is judged on its own records (Task 13).
- **Pre-registration (OQ1's practice):** each item below is committed before the run that judges it.
  - A-9's method: Task 1's constants and `tail`, given verbatim. E1–E4 as Task 2 codes them, with `A9_LIMIT` and the void rule. E5. All before Task 3.
  - A-10's closed form (Task 5); the coupon's board, steps and rule (`a10`, void included; Task 6); Task 7's expected values. All before Task 7.
  - E-9's constraints and attribution rule (Task 10, here), before Step 1 forms any estimate.
  - `predict` (Task 9) and the go rule (E-10, Task 11), before Task 11 computes the prediction.
  - P0-B2's blocking items, `run`'s and `measure`'s rules and `decide`'s body (given here; coded in Task 12) and its expected values (Task 11's commit), before Task 13.
  - Every branch of Tasks 3, 4, 8, 10, 11 and 14, and the ceiling's branches.

  No limit, tolerance, rule or expected result moves after its data is seen. A fix that misses its check is not adopted as is; a redesign needs a new pre-registration and new data (design §5.2).
- **D-22:** no other product number changes. That covers the fit2d 3 %, the dt floor 0.8, REACH_H 6.0, K_MAX 0.45, T_MAX_S 40 ns, GROWTH_DB 20, the stop presets, criterion 1 (`p0.LIMITS1`) and KAPPA_LIMIT 10. P0-B2's 80 ns lives in its own project only.
- **Timebox (D-4, Rec):** counted from 2026-10-22. The target is 2026-11-05 to 2026-11-12 and the ceiling is 2026-11-19. Every [run] task checks the date first. At the ceiling all P0 runs stop; [decide] and [code] tasks on runs that finished still follow. The code state is pre-registered:
  - A-9's judges have not run: Task 4's fail branch.
  - The coupon has not finished: Task 8's fail branch.
  - Task 10 has not finished: not attributed, and A-12's code, if committed, reverted. Its own bound is 2026-11-12.
  - P0-B2 cannot finish by the ceiling: Task 13 starts only with 12.2 h to spare; otherwise P0-B2 is not run and not spent.
  - P0-B2 has not finished: not judged; its records stay; P0-C's "do not start" and the §7.6 label stay.

  Task 15 then writes the exit addendum with the data. Every report and its JSON record elapsed days and machine hours.
- **Reports (D-51, D-52):**
  - One plan-7 report, `docs/validation/YYYY-MM-DD-p0-b2.md`, with `YYYY-MM-DD-p0-b2.json` beside it (Task 15), and an addendum to `docs/validation/2026-10-25-stage1-exit.md`.
  - English, one page where possible, seven sections in order: 1. verdict; 2. inputs; 3. measured value against limit, pass or fail; 4. decisions, each marked; 5. stated limits and deviations; 6. machine time, predicted against measured; 7. next step.
  - Accuracy is given as |ΔS| or a null shift, never as dB at a null.
  - A [decide] subagent returns each text. The controller saves it, runs `.venv\Scripts\python.exe tools\privacy_gate.py --staged` and commits it. Subagents never write report files.
- **Privacy:** use only the synthetic fixtures. Never open the owner's boards, KiCad profile or settings, network shares, KiCad recent-file lists or the private research archive. Never print the file `KRS_PRIVATE_LIST` names, nor its path. Committed text, JSON and fixtures hold no absolute path, e-mail address, private name or drive letter followed by a colon and a slash.
- **Recommendations:** every commit and report that applies a controller call says "controller recommendation, owner unavailable".
- **Spec amendments:** A-9 lands only in Task 4's adopt branch, and A-10 only in Task 8's, each in its own commit. Each changed line carries "(A-n, plan 7: controller recommendation, owner unavailable)", and the Status line gets one sentence. A-11 changes nothing: no code, no estimator, no spec text (E-8). A-12 exists only through Task 10's amendment.
- **Workflow:** every implementer runs `graphify query "<question>"` (or `explain`/`path`) from the repo root before reading code, and `graphify update .` after changing it. Commits carry no co-author line. Never `--no-verify`. Nothing is pushed.

## Review Focus

1. **A record too short to fit.** This covers a Draft cut near 4 ns, a fast line that converges 2 ns after the pulse, a T_max of 3 ns, and a one-sample record at a T_max under one probe step. The job keeps its plain DFT and the user reads one W_TAIL_FALLBACK per job, listing the possible causes and a next step; never a crash and never a silent zero tail. Tests (Task 1): `test_a_record_shorter_than_48_samples_after_the_pulse_falls_back`, the one-sample case of `test_a_job_whose_tail_fails_keeps_its_plain_dft`, the new assertions in `test_the_layout_is_reduced_from_the_run_folder` and `test_t_max_jobs_are_reduced_whole_and_flagged`, `test_write_outputs_names_each_job_whose_tail_fell_back_after_the_verdicts` and `test_verify_names_its_own_jobs_whose_tail_fell_back`.
2. **A growing or slow in-band mode** (a flat job, a near-lossless mode). The tail must fall back and never invent a resonance or hide growth. A mode just above f2, like verify's 3.096 GHz one, must not refuse. Tests (Task 1): `test_a_slow_in_band_or_a_growing_mode_falls_back`, `test_an_undamped_mode_above_the_band_does_not_refuse`, `test_a_job_whose_tail_fails_keeps_its_plain_dft`.
3. **An inductor at or below its strips' term in verify** (a pH value, or the K_MAX sweep's). E_VERIFY_STRIPS names it before E_VERIFY_K, and the sweep keeps its uncompensated grid L. Tests (Task 5): the new cases in `test_verify_refuses_what_it_cannot_put_in_the_grid`, and the existing `test_p0b_on_the_fake_worker_writes_a_plain_private_free_gate_json`, whose sweep fails with E_VERIFY_STRIPS without `compensate=False` (Task 5's Step 3 shows that red).
4. **A gate step that keeps no S, or is interrupted, resumed or rerun** (a diverged job, a refusal, a crash, a reboot, a fix commit, a second `run` after the result). The coupon's check reads void, never a pass and never a loop. P0-B2 does not start B2 after a B1 that stored no results, and judges it. A step resumes on the same code, B1 reruns after a `src/` fix, and a spent run refuses. `measure` refuses a project that is not P0-B2's, that holds another run, or whose chain does not reproduce verify's stored comparison. Tests: the void case of `test_the_coupon_check_runs_verify_uncompensated_then_compensated` (Task 6); `test_p0b2_steps_are_keyed_by_the_model_and_b1s_run_and_a_spent_run_refuses`, `test_a_b1_that_stores_no_results_is_judged_and_b2_never_runs` and the refusals in `test_p0b2_on_the_fake_worker_writes_a_plain_private_free_gate_json` (Task 12).
5. **`predict` pointed at the wrong folder** (plan 6's B1 in `<P0-2>`, which has no verify, A-9's independent data, or any folder it could lock). It refuses by DEV's hashes before it reads verify, and writes nothing. Test (Task 9): `test_predict_reads_p0bs_stored_records_only_and_writes_nothing`.

---

## File structure

```
src/kicad_rf_studio/core/post/waves.py    # T1 TAIL_*, tail, s_matrix(t_free), Layout.s_dft/fallback
src/kicad_rf_studio/pipeline.py           # T1 fallback_lines, tail_line in write_outputs and _verify
src/kicad_rf_studio/core/messages.py      # T1 W_TAIL_FALLBACK, W_TAIL_LARGE; T5 E_VERIFY_STRIPS
src/kicad_rf_studio/core/model/spec.py    # T5 MU0, strip_dl, verify_spec(compensate=)
tools/p0.py                               # T1 s_of with tails; T6 holds
tools/p0b/harness.py                      # T1 evidence's docstring; T2 a9, --a9; T5 the sweep's compensate=False; T12 made, _table, _rows
tools/p0d.py                              # T1 references' docstring
tools/p0b2.py  tests/test_p0b2.py         # T6 the coupon and a10; T9 predict; T12 P0-B2 (go only)
tests/test_post_waves.py  tests/test_post_real.py  tests/test_post_outputs.py  tests/test_run.py  tests/test_verify.py
tests/test_p0.py  tests/test_p0d_refs.py  # T1 (test_p0d_refs again in T14)
tests/test_p0b.py                         # T2
tests/test_model_spec.py  tests/test_verify.py   # T5
tests/test_p0d.py                         # T6, T12: p0b2 in the every-tool test
docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md  # T4 A-9, T8 A-10 (adopt branches only)
docs/superpowers/plans/2026-10-27-stage1-plan7-consistency-p0b2.md  # this plan; T10, T11 amendments
tests/fixtures/p0d/*.npz  tests/test_p0d_refs.py  # T14
outside the repo: <P0-2>\p0b\a9.json (T3); <P0-2>\p0b2\ (T7, T11, T13); <P0>, read-only (T9–T11); <R7>
```

## Decisions this plan fixes

| Decision | Task |
|---|---|
| `waves.TAIL_*`, `tail`, `s_matrix(..., t_free)` with its short-record fallback, `Layout.s_dft`, `Layout.fallback`; W_TAIL_FALLBACK, W_TAIL_LARGE; tails in `p0.s_of` | 1 |
| `harness.a9`, `A9_STEPS`, `A9_CUTS`, `A9_LIMIT`, the void rule, `--a9` (once): A-9's judges E1–E4 | 2 |
| A-9 adopted (spec §6.3, §8) or reverted | 4 |
| `spec.MU0`, `strip_dl`, `verify_spec(..., compensate=)`, E_VERIFY_STRIPS; the sweep's `compensate=False` | 5 |
| `p0b2.COUPON`, `L_COUPON`, `DL_BAND`, `DS21_COUPON_DB`, `FLOOR`, `single_l`, `fit_dl`, `a10`, `coupon`; `p0.holds` | 6 |
| A-10 adopted (spec §7.6) or reverted | 8 |
| `p0b2.DEV`, `BANDS_GHZ`, `bands`, `predict` | 9 |
| E-9: attributed (A-12 by amendment) or a stated limit | 10 |
| The go/no-go and P0-B2's pre-registration | 11 |
| `p0b2.EDITS`, `STEPS`, `JOBS`, `MODE_HZ`, `project`, `run`, `measure`, `decide`, `tables`, `write`; `harness.made`, `_table`, `_rows` (go only) | 12 |
| `tests/fixtures/p0d/*.npz` with tails | 14 |

## Phase 1 — tails (A-9)

### Task 1 [code]: A fitted decaying tail on every reported S

**Files:**
- Modify: `src/kicad_rf_studio/core/post/waves.py`. The constants go after `KAPPA_LIMIT` (L15); `tail` is new, before `s_matrix`; `s_matrix` is L26–42, `Layout` L59–69 and `layout` L82–112.
- Modify: `src/kicad_rf_studio/pipeline.py`. The import is L43; two helpers go before `write_outputs`; `write_outputs` is L409–472 (the chain at L445), `verify` L719–747 (docstring) and `_verify` L749–815 (the comparison at L775, I_VERIFY_COMPARE at L799).
- Modify: `src/kicad_rf_studio/core/messages.py`, after `W_JOB_STOPPED` (L123).
- Modify: `tools/p0.py` (`s_of`, L332–356, and its waves import, L33); `tools/p0b/harness.py` (`evidence`'s docstring); `tools/p0d.py` (`references`' docstring).
- Test: `tests/test_post_waves.py`, `tests/test_post_real.py` (L43), `tests/test_post_outputs.py` (`lay_of`), `tests/test_run.py`, `tests/test_verify.py`, `tests/test_p0.py`, `tests/test_p0d_refs.py`.

**Interfaces:**
- Consumes: `stoprule.KEPT`, `chain.terminate`, `checks.compare`. In tests: `networks.synth_records`, `star`; `traces.trace`; test_post_waves' `fake_run` and `port`; test_run's `result_codes`, `GATES`; test_verify's `verified`; test_p0's `EXC40`.
- Produces:
  - `waves.TAIL_WINDOW_S = 6e-9`, `TAIL_ORDER_MAX = 16`, `TAIL_SVD_REL = 1e-3`, `TAIL_FIT_TOL = 1e-2`, `TAIL_GROW = 1e-2`, `TAIL_TAU_MAX_S = 40e-9`, `TAIL_MIN_SAMPLES = 3 * TAIL_ORDER_MAX` (48), `TAIL_WARN = 0.02`.
  - `waves.tail(x: np.ndarray, t: np.ndarray, f: np.ndarray, t_free: float) -> np.ndarray | None`: (C, F), or None when a channel fails.
  - `waves.s_matrix(records, f: np.ndarray, t_free: float | None = None) -> tuple[np.ndarray, np.ndarray, list[int]]`: (S, A, the 0-based jobs that fell back).
  - `Layout` gains `s_dft: np.ndarray` and `fallback: list[str]`, in that order after `flipped`.
  - `pipeline.fallback_lines(lay: Layout, jobs: list[dict]) -> list[tuple[str, dict]]` and `pipeline.tail_line(f: np.ndarray, *pairs: tuple[np.ndarray, np.ndarray]) -> list[tuple[str, dict]]`.
  - CATALOG `W_TAIL_FALLBACK` {port, t_ns} and `W_TAIL_LARGE` {ds, entry, f_mhz}.
  - `p0.s_of(traces, f, preset=None, rows=None)`: its signature unchanged, every record now takes its tail.

The task is four test-first cycles, each seen red for its own reason, and one commit.

- [ ] **Step 1: `tail` and its constants.**
  - In `tests/test_post_waves.py`, import `tail` beside `s_matrix`. Put the four constants after `F, Q = ...` (`fake_run` reads `T0` from Step 2 on), and the helpers and tests at the end of the file:

```python
T0 = 9 / (np.pi * (F2 - F1))  # the synthetic pulse's t0, 9/(2π·fw): fake_run's model.json holds it (A-9)
DT_P = 41.3969e-12  # lpf915's probe step; the tail tests' records
T_FREE = 2.236e-9  # 2·t0 of the 915 MHz band: the pulse's end
MODES = [(1.0, 2.961e9, 10e-9), (0.5, 2.440e9, 13.5e-9)]  # P0-B's co-simulation poles near f2 (p7-tails)


def ring(t, modes):
    """Σ a·e^(−t/τ)·cos(2π·f·t) over `modes` (a, f, τ) as one channel (1, n)."""
    return sum(a * np.exp(-t / tau) * np.cos(2 * np.pi * fm * t) for a, fm, tau in modes)[None]


def continuation(modes, n):
    """The DFT on F of `modes` sampled at k·DT_P for every k ≥ n, from their true poles."""
    ph, out = np.exp(-2j * np.pi * F * DT_P), 0
    for a, fm, tau in modes:
        for z in np.exp((-1 / tau + np.array([2j, -2j]) * np.pi * fm) * DT_P):
            out = out + a / 2 * z ** n * np.exp(-2j * np.pi * F * n * DT_P) / (1 - z * ph)
    return out


def test_tail_is_the_analytic_continuation_of_damped_sinusoids():  # A-9 (E-1); measured 1.1e-13
    t = np.arange(0, 13.21e-9, DT_P)  # 320 samples: P0-B's verify P1 cut
    exact = continuation(MODES, len(t))
    assert np.abs(tail(ring(t, MODES), t, F, T_FREE)[0] - exact).max() <= 1e-8 * np.abs(exact).max()


def test_cut_plus_tail_equals_the_whole_record_dft():  # A-9; measured 9.1e-14
    t, whole = np.arange(0, 13.21e-9, DT_P), np.arange(0, 400e-9, DT_P)
    dft = [ring(x, MODES)[0] @ np.exp(-2j * np.pi * np.outer(x, F)) for x in (t, whole)]
    assert np.abs(dft[0] + tail(ring(t, MODES), t, F, T_FREE)[0] - dft[1]).max() <= 1e-6 * np.abs(dft[1]).max()


@pytest.mark.parametrize("modes", [[(1.0, 1e9, 200e-9)], [(1.0, 1e9, -20e-9)]], ids=["slow in band", "growing"])
def test_a_slow_in_band_or_a_growing_mode_falls_back(modes):  # Review Focus 2
    t = np.arange(0, 13.21e-9, DT_P)
    assert tail(ring(t, modes), t, F, T_FREE) is None


def test_an_undamped_mode_above_the_band_does_not_refuse():  # Review Focus 2: verify's 3.096 GHz mode, above f2
    t = np.arange(0, 13.21e-9, DT_P)
    x = ring(t, [(1.0, 2.961e9, 10e-9)]) + 0.01 * np.cos(2 * np.pi * 3.096e9 * t)
    assert F[-1] < 3.096e9 and tail(x, t, F, T_FREE) is not None


def test_a_record_shorter_than_48_samples_after_the_pulse_falls_back():  # Review Focus 1: Draft cuts near 4 ns
    short, enough = (np.arange(0, end, DT_P) for end in (4.2e-9, 4.25e-9))  # 47 and 48 samples after T_FREE
    assert tail(ring(short, MODES), short, F, T_FREE) is None
    assert tail(ring(enough, MODES), enough, F, T_FREE) is not None
```

  - Run `python -m pytest tests/test_post_waves.py -q`. Expected: FAIL with `ImportError: cannot import name 'tail'`.
  - In `waves.py`, add the constants of Interfaces, each with a one-line comment. Then add `tail`, the method E-1 froze, verbatim:

```python
def tail(x: np.ndarray, t: np.ndarray, f: np.ndarray, t_free: float) -> np.ndarray | None:
    """The DFT (C, F) on f of each channel of x (C, n), sampled at t, continued beyond t[-1] by its fitted decaying
    poles (A-9, p7-tails' v3b, frozen by plan 7): a matrix pencil over the last TAIL_WINDOW_S after t_free (the pulse's
    end, 2·t0), its order the Hankel singular values ≥ TAIL_SVD_REL × the largest, at most TAIL_ORDER_MAX, the
    amplitudes fitted on every pole, the decaying ones alone extrapolated. None when the window holds fewer than
    TAIL_MIN_SAMPLES, or when a channel leaves more than TAIL_FIT_TOL of its norm unexplained, holds a pole growing by
    more than TAIL_GROW over the window, or keeps an in-band pole slower than TAIL_TAU_MAX_S. An all-zero channel
    gets no tail."""
    # ponytail: a pole the pencil puts on or just outside the unit circle without growing by TAIL_GROW is left out of
    # the tail, not refused; the stop rule's flat verdict flags such a job
    dt = t[1] - t[0]
    m0 = np.searchsorted(t, max(t[-1] - TAIL_WINDOW_S, t_free))  # the window starts after the pulse
    n = len(t) - m0
    if n < TAIL_MIN_SAMPLES:
        return None
    ph, out = np.exp(-2j * np.pi * f * dt), np.zeros((x.shape[0], len(f)), complex)
    for ch, y in enumerate(x[:, m0:]):
        if not (norm := np.linalg.norm(y)):
            continue
        _, s, vh = np.linalg.svd(np.lib.stride_tricks.sliding_window_view(y, n // 3 + 1), full_matrices=False)
        v = vh[:min(TAIL_ORDER_MAX, int((s >= TAIL_SVD_REL * s[0]).sum()))].conj().T
        z = np.linalg.eigvals(np.linalg.pinv(v[:-1]) @ v[1:])
        vd = z ** np.arange(n)[:, None]
        c = np.linalg.lstsq(vd, y, rcond=None)[0]
        if np.linalg.norm(vd @ c - y) > TAIL_FIT_TOL * norm or (np.abs(z) ** n > 1 + TAIL_GROW).any():
            return None
        z, c = z[np.abs(z) < 1], c[np.abs(z) < 1]  # decaying poles only beyond the cut
        if (dt / np.abs(1 - z * ph[:, None]).min(0) > TAIL_TAU_MAX_S).any():
            return None  # an in-band pole too slow to extrapolate
        out[ch] = np.exp(-2j * np.pi * f * (t[-1] + dt)) * (c * z ** n / (1 - z * ph[:, None])).sum(1)
    return out
```

  - Run the same command. Expected: pass.

- [ ] **Step 2: `s_matrix(t_free)`, `Layout` and `layout`.**
  - At the end of `tests/test_post_waves.py`:

```python
def upto(rec, t_cut):
    """`rec` cut at t_cut, u and i at the same count, as layout cuts a job."""
    return [(t[:n], u[:, :n], ti[:n], i[:, :n]) for t, u, ti, i in rec for n in [np.searchsorted(t, t_cut, "right")]]


def growing(rec):
    """`rec` with job 0's u and i carrying a mode that grows after 5 ns, as traces' "growth" kind adds it."""
    t, u, ti, i = rec[0]
    g = lambda x: 1e-3 * np.exp(np.maximum(x - 5e-9, 0) / 1.3e-9) * (x > 5e-9) * np.sin(2 * np.pi * 1.5e9 * x)
    return [(t, u + g(t), ti, i - g(ti) / 50), *rec[1:]]


def test_a_job_whose_tail_fails_keeps_its_plain_dft():  # Review Focus 1, 2: per job, u and i together
    rec = synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)
    assert s_matrix(growing(rec), F, 2 * T0)[2] == [0]
    for t_cut in (4e-9, 0.0):  # 43 samples after 2·t0, then one sample, which tail's t[1] lacks: every job falls back
        cut = upto(rec, t_cut)
        S, _, fallen = s_matrix(cut, F, 2 * T0)
        assert fallen == [0, 1, 2] and np.array_equal(S, s_matrix(cut, F)[0])


def test_the_layout_names_the_job_whose_tail_failed(tmp_path):  # A-9
    rec = growing(synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9))
    lay = layout(P915, fake_run(tmp_path, rec, [port("P1"), port("P2"), port("C1", True)]))
    assert lay.fallback == ["P1"] and np.array_equal(lay.s, s_matrix(rec, F, 2 * T0)[0])
    assert np.array_equal(lay.s_dft, s_matrix(rec, F)[0])
```

  - Edit the existing tests in that file:
    - `test_s_is_the_network_the_waves_came_from`: `S, A, fallen = s_matrix(...)`, with `fallen == []` added to its first assert.
    - `test_the_excitation_level_is_the_pulse_spectrum`: `_, A, _ = s_matrix(...)`.
    - `fake_run` writes `json.dumps({"ports": ports, "excitation": {"t0": T0}})`, and its docstring says "model.json (`ports`, and the synthetic pulse's t0 as its excitation)".
    - `test_the_layout_is_reduced_from_the_run_folder` gains `assert lay.fallback == ["P1", "P2", "C1"] and np.array_equal(lay.s, lay.s_dft)  # Review Focus 1: cut at 4 ns`.
    - `test_a_reversed_curve_port_is_normalised_and_the_chain_does_not_change`: `raw = s_matrix(rec, F, 2 * T0)[0]`.
  - `tests/test_post_real.py` L43: `S, A, _ = s_matrix(rec, F)`. `tests/test_post_outputs.py`: `lay_of` returns `Layout(F, [71, 213, 355], s, np.full(len(F), -3.0), ports, flipped or [False] * len(ports), s, [])`.
  - Run `python -m pytest tests/test_post_waves.py tests/test_post_real.py tests/test_post_outputs.py -q`. Expected: FAIL: `s_matrix` takes 2 positional arguments, 2 values do not unpack into 3, and `Layout` has 6 fields and no `fallback`.
  - **`s_matrix(records, f, t_free=None)`.** With `t_free`, each job's U and I add `tail(u, t_u_j, f, t_free)` and `tail(i, t_i_j, f, t_free)`, on its own time base. A job whose record holds fewer than TAIL_MIN_SAMPLES samples keeps both plain without calling `tail` (a one-sample record has no `t[1]`), and so does a job for which either tail is None; its index goes into the returned list. E_S_SINGULAR checks A as before. The docstring gains these rules.
  - **`Layout`.** Its docstring gains: "`s_dft`, the plain DFT's S, normalised the same way; `fallback`, the ports of the jobs whose tail fit failed, whose S is their plain DFT (A-9)".
  - **`layout`.** Read `model.json` once, after the file checks and before the records, into `spec`. Keep both refusals' order. Then `s_dft = s_matrix(records, f)[0]` first, so E_S_SINGULAR refuses exactly as today, and `s, a, fallen = s_matrix(records, f, 2 * spec["excitation"]["t0"])`, under `# ponytail: a second, plain DFT pass for s_dft, and every reduction refits the tails (about 0.3 s on lpf915, no cache); one pass and a cache by run folder if retune slows`. `ports = spec["ports"]`. Return `Layout(f, markers, s * dd, level_db(a), ports, flips, s_dft * dd, [jobs[k]["port"] for k in fallen])` with `dd = np.outer(d, d)`. The docstring says S takes each job's fitted tail beyond its cut (A-9).
  - Run the same command. Expected: pass.

- [ ] **Step 3: The two warnings.**
  - `tests/test_run.py` imports `from traces import trace` and gains this helper beside `test_three_external_ports_get_their_touchstone_and_no_two_port_summary`, which then uses it with `external(tmp_path, rec, 3)`:

```python
def external(tmp_path, rec, n, t_cut=None):
    """A project of `n` external ports and no part whose results are the records `rec` (fake_run), as write_outputs
    reads it."""
    results = {**fake_run(tmp_path, rec, [port(f"P{k}") for k in range(1, n + 1)], t_cut), "preset": "normal",
               "gates": GATES, "c_box": {}, "loss_expected": 0.0}
    ports = [{"name": f"P{k}", "signal": f"J{k}.1", "reference": {"pad": f"J{k}.2", "uuid": ""}} for k in range(1, n + 1)]
    return {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "ports": ports, "others": [],
            "chain": {"nets": ["A"], "series": [], "shunt": []}, "results": results}


@pytest.mark.parametrize(("kind", "t_cut", "large"), [
    ("tmax", 15e-9, [{"ds": "1.3731", "entry": "S11", "f_mhz": "998.8"}]),  # a 6 ns ring cut at 15 ns
    ("converge", 10.7e-9, [])])  # the default fake's 1 ns ring: its tails move S by 5.1e-4
def test_write_outputs_warns_once_when_the_tails_move_the_chain_by_more_than_0_02(tmp_path, kind, t_cut, large):
    rec = [(r.t_u, r.u, r.t_i, r.i) for r in (trace(kind, 2, k) for k in (0, 1))]
    lines = write_outputs(tmp_path / "p" / "project.json", external(tmp_path, rec, 2, t_cut), "c")
    assert [p for c, p in lines if c == "W_TAIL_LARGE"] == large and "W_TAIL_FALLBACK" not in dict(lines)


def test_write_outputs_names_each_job_whose_tail_fell_back_after_the_verdicts(tmp_path):  # Review Focus 1
    rec = synth_records(lambda f: star(f, 3), 3, 457.5e6, 3.0195e9, 1.73972e-13, 10e-9)
    lines = write_outputs(tmp_path / "p" / "project.json", external(tmp_path, rec, 3, 4e-9), "c")
    assert lines[1:4] == [("W_TAIL_FALLBACK", {"port": f"P{k}", "t_ns": "4.00"}) for k in (1, 2, 3)]
```

  - `test_t_max_jobs_are_reduced_whole_and_flagged` asserts `result_codes(r["run_dir"])[:6] == ["I_RESULTS", "I_BASIS", "W_JOB_T_MAX", "W_JOB_T_MAX", "W_TAIL_FALLBACK", "W_TAIL_FALLBACK"]  # Review Focus 1: 3 ns is too short to fit`.
  - `tests/test_verify.py` (it imports `json` already) imports `from kicad_rf_studio.core.post import waves`:

```python
def test_verify_warns_when_the_tails_move_its_s(tmp_path, calibrated, monkeypatch):  # A-9 in verify
    pj = verified(tmp_path, monkeypatch)  # the run on the network fake, whose tails move nothing
    monkeypatch.setenv("KRS_FAKE", "tmax")  # verify's own jobs: 6 ns rings to T_max
    assert main(["verify", str(pj)]) == 0
    events = [json.loads(line) for line in (Path(load_project(pj)["verify"]["run_dir"]) / "events.jsonl")
              .read_text(encoding="utf-8").splitlines()]
    results = [(e["code"], e["params"]) for e in events if e["kind"] == "result"]
    assert [c for c, _ in results[:3]] == ["I_VERIFY_RESULTS", "I_VERIFY_COMPARE", "W_TAIL_LARGE"]
    assert results[2][1] == {"ds": "0.0213", "entry": "S11", "f_mhz": "998.8"}


def test_verify_names_its_own_jobs_whose_tail_fell_back(tmp_path, calibrated, monkeypatch):  # Review Focus 1
    pj = verified(tmp_path, monkeypatch)
    monkeypatch.setattr(waves, "TAIL_FIT_TOL", 0.0)  # no fit passes: every job keeps its plain DFT
    assert main(["verify", str(pj)]) == 0
    events = [json.loads(line) for line in (Path(load_project(pj)["verify"]["run_dir"]) / "events.jsonl")
              .read_text(encoding="utf-8").splitlines()]
    results = [(e["code"], e["params"].get("port")) for e in events if e["kind"] == "result"]
    assert results[:4] == [("I_VERIFY_RESULTS", None), ("I_VERIFY_COMPARE", None), ("W_TAIL_FALLBACK", "P1"),
                           ("W_TAIL_FALLBACK", "P2")] and "W_TAIL_LARGE" not in dict(results)  # the run's fell back too
```

  - Run `python -m pytest tests/test_run.py tests/test_verify.py -q`. Expected: FAIL on the new assertions: no W_TAIL line yet.
  - **`messages.py`,** after `W_JOB_STOPPED`:

```python
    "W_TAIL_FALLBACK": "{port}: its record, cut at {t_ns} ns, takes no fitted tail (fewer than 48 samples after the pulse, a channel's last 6 ns not explained to 1 %, or a growing or slow in-band mode), so its S is the plain DFT cut there and may carry truncation error near a slowly decaying mode. For a longer record, set \"preset\" to \"strict\" in project.json and run `run` again (`verify` again for verify's own jobs).",
    "W_TAIL_LARGE": "The fitted tails beyond the cut times move the reported S by up to {ds} ({entry} at {f_mhz} MHz): a slowly decaying mode was still ringing when the jobs stopped, so the result there rests on the tail fit. Raise t_max_s in project.json and use the strict preset for a result that rests less on it.",
```

  - **`pipeline.py`.** Import `TAIL_WARN` beside `layout`.
    - `fallback_lines(lay, jobs)` returns one `("W_TAIL_FALLBACK", {"port": port, "t_ns": f"{end * 1e9:.2f}"})` per port of `lay.fallback`, in that order, under `# ponytail: one line per job, six on a six-port Draft run; one summary line if users read that as noise`. `end` is that port's job's `t_cut`, or `t_stop` when `t_cut` is None.
    - `tail_line(f, *pairs)` takes the largest complex |S − S_dft| over the pairs, frequencies and entries. When it exceeds TAIL_WARN, it returns `[("W_TAIL_LARGE", {"ds": f"{d:.4f}", "entry": f"S{i + 1}{j + 1}", "f_mhz": f"{f[k] / 1e6:.1f}"})]` for that maximum; otherwise `[]`. That is at most one line (design §5.2).
    - `write_outputs`: `lines += fallback_lines(lay, results["jobs"])` right after the verdict lines (L431–434). In the `else:` branch, right after `chain = terminate(...)`: `lines += tail_line(lay.f, (chain, terminate(lay.s_dft, ext, zk, lay.f)))`. A part's refusal leaves no chain, so no W_TAIL_LARGE then.
    - `_verify`: name `closed = terminate(lay.s, ext, zk, lay.f)` for `compare`. Right after the I_VERIFY_COMPARE append: `lines += [*fallback_lines(own, done), *tail_line(own.f, (own.s, own.s_dft), (closed, terminate(lay.s_dft, ext, zk, lay.f)))]`. verify names its own jobs' fallbacks; the run's are printed by `run` and every `retune`.
    - The docstrings of `write_outputs` and `verify` list the new lines in those places.
  - Run the same command. Expected: pass.

- [ ] **Step 4: Tails in `p0.s_of`.**
  - `tests/test_p0.py` imports `from traces import trace` and `from kicad_rf_studio.core.post import waves`:

```python
def test_s_of_adds_each_records_tail(monkeypatch):  # A-9: s_of's two branches; measured 4.4e-13 and 1.373
    cut = [(trace("tmax", 2, k), k, EXC40, 15e-9) for k in (0, 1)]  # 6 ns rings cut at 15 ns
    late = [(rec, k, exc, None) for rec, k, exc, _ in cut]  # the whole 40 ns record and its tail
    tails, whole = ([p0.s_of(x[:n], F)[0] for n in (2, 1)] for x in (cut, late))  # s_matrix's branch, then a column
    monkeypatch.setattr(waves, "TAIL_MIN_SAMPLES", 10**9)  # no record takes a tail: the plain DFT
    plain = [p0.s_of(cut[:n], F)[0] for n in (2, 1)]
    assert all(np.abs(t - w).max() <= 1e-9 and np.abs(p - w).max() >= 1 for t, w, p in zip(tails, whole, plain))
```

  - `tests/test_p0d_refs.py` imports `from kicad_rf_studio.core.post import waves`, and `test_the_draft_replay_of_the_committed_traces_reproduces_the_references` takes `monkeypatch` and opens with `monkeypatch.setattr(waves, "TAIL_MIN_SAMPLES", 10**9)  # plain until plan 7's Task 14 regenerates the references with tails`.
  - Run `python -m pytest tests/test_p0.py -q -k s_of_adds`. Expected: FAIL: `s_of` still reduces plain, so the 15 ns cut misses the whole record by about 1.35.
  - **`p0.s_of`.** The N-trace branch passes `t_free = 2 * traces[0][2]["t0"]` to `s_matrix`. The one-trace branch adds `tail(u, t_u, f, t_free)` and `tail(i, t_i, f, t_free)` to U and I when its record holds at least TAIL_MIN_SAMPLES samples and neither is None, under `# ponytail: s_of drops the fallen jobs; layout's fallback is the one that names them`. The docstring says every record takes its tail.
  - **Docstrings.** `harness.evidence` gains: "both measure the reported S, tails included (E-4)". `p0d.references` gains: "p0.s_of, tails included".
  - Run `python -m pytest tests/test_p0.py tests/test_p0d_refs.py -q`. Expected: pass.

- [ ] **Step 5: Run** `python -m pytest -q`. Expected: all pass, with no re-pin.
  - Every S-valued assert and every exact list of output codes runs on the network fake or on whole synthetic star records. There the tails move S by at most 6e-9, with no fallback (the reviser's replay: the network fake cuts at 4.34 ns at Draft and at 4.46–4.50 ns at Normal, 51–55 samples after 2·t0; whole 10 ns star records move by 5.4e-9). `test_the_cross_check_closes_both_sides_as_d43_says`' 1e-9 bound holds too, since both its sides reduce through `layout`.
  - The converge fake's tails move S by 2.1e-3 at Draft and 4.1e-4 at Normal, and the tmax fake's by 0.021–0.035. No test asserts S or a code list on them; `test_each_verdict_through_run[tmax]` and `test_lpf915_runs_one_job_per_port_and_records_c_box` now print a W_TAIL_LARGE they do not assert.
  - Any other failure: stop and report. Never re-pin a value or loosen a bound.
- [ ] **Step 6: Commit.** `git add src/kicad_rf_studio/core/post/waves.py src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/core/messages.py tools/p0.py tools/p0b/harness.py tools/p0d.py tests/test_post_waves.py tests/test_post_real.py tests/test_post_outputs.py tests/test_run.py tests/test_verify.py tests/test_p0.py tests/test_p0d_refs.py`, then `git commit -m "feat(post): each record's fitted decaying tail beyond its cut, W_TAIL_FALLBACK and W_TAIL_LARGE (A-9's frozen method; design 5.2, E-1, E-3; controller recommendation, owner unavailable)"`, then `graphify update .`.

### Task 2 [code]: A-9's judges E1–E4

**Files:**
- Modify: `tools/p0b/harness.py` (the waves import; constants after `UNSOLVED`; `a9` after `evidence`; `main`)
- Test: `tests/test_p0b.py`

**Interfaces:**
- Consumes: Task 1's `waves.TAIL_WINDOW_S`, `layout(...).fallback` and `p0.s_of` with tails; `p0.records`, `p0.closed_chain`, `p0.save`, `p0.versions`, `harness._path`, `_traces`; p0a's pad project `<out>/p0a/projects/coupon_gcpw_pads/project.json`.
- Produces:
  - `harness.A9_STEPS = ("p0b-B1", "p0a-pad")`, `A9_CUTS = (13.21e-9, 16e-9, 20e-9)`, `A9_LIMIT = 2e-3`.
  - `harness.a9(out: Path) -> dict`: `{"e1": {"job", "end_s", "cuts", "ds": float | None}, "e2": float, "e3": {step: [ports]}, "e4": {"jobs": ["step/port"], "ds": float | None}, "pass": bool}`.
  - CLI `--a9`: writes `<out>/p0b/a9.json` (a9's dict plus `"versions"`), prints it, starts no run, and refuses once that file exists.

- [ ] **Step 1: Write the failing test** in `tests/test_p0b.py` (add `import p0a` and `from kicad_rf_studio.core.post import waves`):

```python
def test_a9_judges_plan6s_b1_and_the_pad_coupon(p0_out, monkeypatch):  # A-9's E1-E4 (design 5.2, E-2)
    monkeypatch.setenv("KRS_FAKE", "tmax")  # 6 ns rings to T_max: every tail is exact, so every judge reads about 0
    monkeypatch.setattr(p0, "cli", in_process)
    assert p0a.main(["--out", str(p0_out), "--only", "p0a-pad"]) == 0
    monkeypatch.setattr(p0, "code_id", lambda: "other")  # B1 ran on other product code than P0-A (PF-43)
    assert harness.main(["--out", str(p0_out), "--only", "B1"]) == 0
    r = harness.a9(p0_out)
    b1 = [f"p0b-B1/{p}" for p in ("P1", "P2", "C1", "L1", "C2", "C3")]
    assert (r["e1"]["job"], r["e1"]["cuts"], r["e3"], r["e4"]["jobs"], r["pass"]) == (
        "P1", [13.21e-9, 16e-9, 20e-9], {"p0b-B1": [], "p0a-pad": []}, [*b1, "p0a-pad/P1", "p0a-pad/P2"], True)
    assert max(r["e1"]["ds"], r["e2"], r["e4"]["ds"]) <= 1e-9
    assert harness.main(["--out", str(p0_out), "--a9"]) == 0
    saved = json.loads((p0_out / "p0b" / "a9.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in saved.items() if k != "versions"} == r
    with pytest.raises(SystemExit):  # the judges run once
        harness.main(["--out", str(p0_out), "--a9"])
    monkeypatch.setattr(harness, "A9_CUTS", (50e-9,))  # no cut before the 40 ns end: E1 void
    monkeypatch.setattr(harness, "TAIL_WINDOW_S", 1.0)  # no job in E4's domain: E4 void
    r = harness.a9(p0_out)
    assert (r["e1"]["cuts"], r["e1"]["ds"], r["e4"]["ds"], r["pass"]) == ([], None, None, False)
    monkeypatch.setattr(waves, "TAIL_FIT_TOL", 0.0)  # no fit passes: every job keeps its plain DFT
    r = harness.a9(p0_out)
    assert r["e3"] == {"p0b-B1": ["P1", "P2", "C1", "L1", "C2", "C3"], "p0a-pad": ["P1", "P2"]} and not r["pass"]
```

- [ ] **Step 2: Run** `python -m pytest tests/test_p0b.py -q -k a9`. Expected: FAIL with `AttributeError: module 'harness' has no attribute 'a9'`.
- [ ] **Step 3: Implement** the constants of Interfaces, then `a9`. It is the pre-registered judge, so its body is given:

```python
def a9(out: Path) -> dict:
    """A-9's judges (design 5.2, E-2; plan 7 Task 2) on the P0 folder `out`, entered, from the records of A9_STEPS,
    each read on its own (PF-43), and the projects that hold their runs; SystemExit when one does not. "e1": the
    longest p0b-B1 job (its end: t_cut, else t_stop), its own column with tails cut at each of A9_CUTS before its end
    against cut at its end; "e2": B1's chain at ideal values with every job cut 2 ns before its end against as cut;
    "e3": by step, the ports whose job fell back (layout's fallback); "e4": every job whose end less 2 ns leaves
    TAIL_WINDOW_S after 2·t0, its column at its end against 2 ns earlier. Each value is the largest complex |ΔS| on
    the grid. E1 with no cut before the end, or E4 with no job in its domain, is None: void. "pass": E1 and E4 not
    void, e1, e2 and e4 at most A9_LIMIT, and e3 empty."""
    # ponytail: single-use, A-9's one judgement; it stays as the record of how A-9 was judged
    f, rows, e3 = grid(F0, HARMONICS, BAND_FACTOR)[0], [], {}
    for sid, pj in zip(A9_STEPS, (_path(out, "B1"), out / "p0a" / "projects" / "coupon_gcpw_pads" / "project.json")):
        (record,) = p0.records(out, [sid])
        res, data = record["result"], load_project(pj)
        if Path(data.get("results", {}).get("run_dir", "")).name != res["run_dir"]:
            raise SystemExit(f"p0b: {pj} does not hold the run of {sid}; A-9's judges read that run only")
        e3[sid] = layout(data, data["results"]).fallback
        rows += [(f"{sid}/{job['port']}", tr, job["t_stop"] if job["t_cut"] is None else job["t_cut"])
                 for job, tr in zip(res["jobs"], _traces(res["run_dir"], res["jobs"]))]

    def column(tr, t):  # one excitation's own column, tails included, cut at t
        return p0.s_of([(*tr[:3], t)], f)[0]

    def ds(a, b) -> float:
        return float(np.abs(a - b).max())

    name, tr, end = max((r for r in rows if r[0].startswith("p0b-B1/")), key=lambda r: r[2])
    cuts = [c for c in A9_CUTS if c < end]
    e1 = max((ds(column(tr, c), column(tr, end)) for c in cuts), default=None)
    pj = _path(out, "B1")
    early = [(j["t_stop"] if j["t_cut"] is None else j["t_cut"]) - 2e-9 for j in load_project(pj)["results"]["jobs"]]
    e2 = ds(p0.closed_chain(pj, ideal=True)[1], p0.closed_chain(pj, ideal=True, cuts=early)[1])
    four = [(n, tr, t) for n, tr, t in rows if t - 2e-9 - 2 * tr[2]["t0"] >= TAIL_WINDOW_S]
    e4 = max((ds(column(tr, t), column(tr, t - 2e-9)) for _, tr, t in four), default=None)
    return {"e1": {"job": name.split("/")[1], "end_s": end, "cuts": cuts, "ds": e1}, "e2": e2, "e3": e3,
            "e4": {"jobs": [n for n, _, _ in four], "ds": e4},
            "pass": None not in (e1, e4) and max(e1, e2, e4) <= A9_LIMIT and not any(e3.values())}
```

  In `main`, add `parser.add_argument("--a9", action="store_true", help="write p0b/a9.json, A-9's judges on B1's and the pad's records, once, and start no run")`. After `out = p0.enter(...)`, when `a.a9`: SystemExit `f"p0b: {path} exists: A-9's judges run once (plan 7)"` when `path = out / "p0b" / "a9.json"` exists; else `print(json.dumps(p0.save(path, {**a9(out), "versions": p0.versions()}), indent=1))`, then return 0. The module docstring's run line gains `[--a9]`. Add `TAIL_WINDOW_S` to the waves import.
- [ ] **Step 4: Run** the test, then `python -m pytest -q`. Expected: all pass. This suite's `test_traces_real` result (9 passed) is E5.
- [ ] **Step 5: Commit.** `git add tools/p0b/harness.py tests/test_p0b.py`, then `git commit -m "feat(p0b): A-9's pre-registered judges E1-E4 on plan 6's B1 and the pad coupon, --a9 once (design 5.2, E-2)"`, then `graphify update .`.

### Task 3 [run]: A-9's judges, once

- **Before:** Tasks 1–2 are committed, `git status --porcelain` is empty, and `git rev-parse --short HEAD` is noted. The date is before 2026-11-19; otherwise apply the ceiling's branch. No other harness holds `<P0-2>`, and `<P0-2>\p0b\a9.json` does not exist.
- **Command:** `.venv\Scripts\python.exe tools\p0b\harness.py --out <P0-2> --a9`
- **E5** is not rerun: it is Task 2's full suite at its commit, where `test_traces_real` read 9 passed. The stop rule is untouched, and every suite run replays the traces.
- **Expected machine time:** a few seconds (p7-tails: 0.3 s for a six-port with tails).
- **Expected results (predictions, not rules):**
  - E1 judged on all three cuts (Stage 1's longest B1 job ended near 23 ns) and under 2e-3. The development record read 1e-4 from its 16 and 20 ns cuts but 0.0021 from 13.21 ns. That was verify's P1, which holds a verify-only near-lossless 3.096 GHz mode that B1 lacks.
  - E2 about 2e-5 and E4 about 1e-5. These are B1's development analogues: the closed chain with every job 2 ns earlier read 0.00002, and `trunc_2ns` 0.00001, with tails.
  - E3 shows no fallback on B1's six jobs (none on the development B1 under v3b). The pad's two jobs are the open case: their cut, 4.22 ns, leaves exactly 48 probe samples after 2·t0 (2.236 ns), the floor.
  - E4 covers B1's six jobs: the pad's cut less 2 ns falls before the pulse ends.
- **Outputs:** `<P0-2>\p0b\a9.json`. `p0.enter` makes `<P0-2>\harness.lock`, which it removes on exit.
- **Done when:** the command exits 0 and prints the JSON, and `.venv\Scripts\python.exe -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print(d['pass'], d['e1'], d['e2'], d['e3'], d['e4'])" <P0-2>\p0b\a9.json` prints them.
  - A traceback before `a9.json` exists: one test-first plumbing fix under the fix rule, which never touches a9's judging lines, `A9_*`, `waves.TAIL_*`, `tail` or the records; then the same command, once.
  - A SystemExit from `a9` (a record missing, a project holding another run), or a second failure: the judges cannot be computed, and Task 4 takes its fail branch. Nothing is rerun to make the data fit.

### Task 4 [decide]: A-9 adopted, or reverted

**Reads:** `<P0-2>\p0b\a9.json`, Task 3's outcome and E5 (Task 2's suite). The rule (E-2): A-9 is adopted when `pass` is true and E5's 9 tests passed. Otherwise, or when Task 3 could not compute the judges, it is not adopted as is. `<date>` is the day this task runs.

**Branch adopt:**
- [ ] **Step 1: Amendment A-9** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`. This is spec text, so there is no test, as for A-1..A-8.
  - L391 becomes: "- compute S from records **cut at the time the criterion was met**, so the results do not depend on the stop latency, plus each port channel's fitted decaying tail beyond the cut, so they do not depend on a slowly decaying mode either. The tail is a matrix pencil over the last 6 ns after the pulse (at least 48 samples). Its order is the number of Hankel singular values at or above 1e-3 of the largest, at most 16 poles. The amplitudes are fitted on every pole, and the decaying poles alone are extrapolated. A job keeps its plain DFT (W_TAIL_FALLBACK) when a channel leaves more than 1 % of the window unexplained, holds a pole growing by more than 1 % over it, or keeps an in-band pole slower than 40 ns. W_TAIL_LARGE warns when the tails move a reported S by more than 0.02. The method was revised on P0-B's records after its first version failed the two checks planned on them, so those checks were reported instead (0.0021 against 0.002 on verify's long record), and it was adopted on checks pre-registered in plan 7 on plan 6's B1 and the pad coupon, which it passed on `<date>` (A-9, plan 7: controller recommendation, owner unavailable)."
  - After L509 ("| Run exit | …"), add the row: "| Tail fit of a job's record (§6.3) | Warning when it fails (the job keeps its plain DFT) or when the tails move a reported S by more than 0.02 (A-9, plan 7: controller recommendation, owner unavailable) |".
  - The Status line (L4) gains: "On `<date>`, plan 7's tails amended §6.3 and §8 (A-9) the same way."
- [ ] **Step 2: Check** that `Select-String -Path docs\superpowers\specs\2026-10-16-stage1-validated-engine-design.md -Pattern "A-9, plan 7"` finds 2 lines, and that `python tools/privacy_gate.py --staged` reports no hit after `git add`.
- [ ] **Step 3: Commit** A-9 alone: `git commit -m "docs(spec): A-9, each record's fitted tail in §6.3 and §8 (controller recommendation, owner unavailable)"`.
- [ ] **Step 4: Return** E1–E5 as measured against their limits and predictions, for Task 15.

**Branch fail:**
- [ ] **Step 1:** `git revert --no-commit`, newest first, every commit since the plan's commit that touches `src`, `tools` or `tests`: Task 2's, Task 1's and any fix commit made for Task 3. Then `git diff <plan commit> --stat -- src tools tests` prints nothing.
- [ ] **Step 2:** `python -m pytest -q`. Expected: all pass, with the Draft replay at its default again.
- [ ] **Step 3: Commit.** `git commit -m "revert: plan 7's tails — A-9's pre-registered judges failed or could not be computed (design 5.2, E-2; controller recommendation, owner unavailable)"`.
- [ ] **Step 4: Return** each judge that failed or was void, with its value, or why Task 3 could not compute them. The controller goes on with Task 5, and the coupon then judges A-10 on the plain S. After Task 8 the controller goes to Task 15: P0-B2 is a no-go (E-10), and without tails there is no reference to regenerate.

## Phase 2 — verify's L strips (A-10)

### Task 5 [code]: The strips' partial inductance taken off verify's grid L

**Files:**
- Modify: `src/kicad_rf_studio/core/model/spec.py`. `MU0` goes after `EPS0`; `strip_dl` before `verify_spec`; `verify_spec` is L157–193.
- Modify: `src/kicad_rf_studio/core/messages.py`, after `E_VERIFY_K` (L176).
- Modify: `tools/p0b/harness.py` (`kmax_sweep`: its docstring and L226).
- Test: `tests/test_model_spec.py`, `tests/test_verify.py`.

**Interfaces:**
- Consumes: `spec._cell`, `verify_spec`'s port box (`lo`, `hi`, `p`).
- Produces:
  - `spec.MU0 = scipy.constants.mu_0` (H/m).
  - `spec.strip_dl(port: dict, lines: list[list[float]]) -> float` in H. `port` is a model spec port entry whose box lies along x or y; `lines` is `[x, y, z]`.
  - `verify_spec(spec, parts, dump, dt, *, compensate: bool = True) -> dict`.
  - CATALOG `E_VERIFY_STRIPS` {ref, value, dl}.

- [ ] **Step 1: Write the failing tests.** In `tests/test_model_spec.py`, import `strip_dl` beside `verify_spec`:

```python
def test_the_strips_partial_inductance():  # A-10: Ruehli's bar at the cell's width less the bar at the box's width
    lines = [VSPEC["mesh"][a] for a in "xyz"]  # L1's box: 2.0 mm along x, 1.0 mm wide, its cell 0.25 mm, 0.035 mm thick
    assert strip_dl(VPORTS[2], lines) == pytest.approx(4.82342e-10, rel=1e-5, abs=0)
    assert strip_dl(VPORTS[2], [lines[0], [0.5, 1.5], lines[2]]) == 0  # a cell as wide as its box: no strip term
```

  - In `test_verify_moves_every_part_port_into_the_grid`, the tuple's `15e-9` becomes `pytest.approx(15e-9 - 4.823420e-10, rel=1e-6, abs=0)`, and at its end:

```python
    u = verify_spec(VSPEC, VPARTS, dump, DT, compensate=False)  # the K_MAX sweep's construction (A-10)
    assert u["grid"][1]["L"] == 15e-9 and u["metal"] == v["metal"]
    assert [g for g in u["grid"] if g["name"] != "L1"] == [g for g in v["grid"] if g["name"] != "L1"]
```

  - In `test_verify_refuses_what_it_cannot_put_in_the_grid`, the `"1pH"` case expects `("E_VERIFY_STRIPS", {"ref": "L1", "value": "1pH", "dl": "0.482"})`. Add the case `((VSPEC, {**VPARTS, "L1": {"ref": "L1", "value": "483.342pH"}}, dump), ("E_VERIFY_K", {"ref": "L1", "k": "1.13", "limit": "0.45"}))`: its grid L is 0.99999 pH. After the loop:

```python
    with pytest.raises(KrsError) as e:  # Review Focus 3: the sweep's uncompensated path keeps the k check
        verify_spec(VSPEC, {**VPARTS, "L1": {"ref": "L1", "value": "1pH"}}, dump, DT, compensate=False)
    assert (e.value.code, e.value.params) == ("E_VERIFY_K", {"ref": "L1", "k": "1.13", "limit": "0.45"})
```

  - `tests/test_verify.py`: in `test_verify_runs_the_parts_in_the_grid_and_compares`, the tuple's `15e-9` becomes `pytest.approx(1.4875188e-08, rel=1e-6, abs=0)`, lpf915's L1 less 0.124812 nH on plan 6's mesh. The bytes become `b"in grid: L1 15nH as L 1.48752e-08 H with the cell's C 6e-16 F"`.

- [ ] **Step 2: Run** `python -m pytest tests/test_model_spec.py tests/test_verify.py -q`. Expected: FAIL with `ImportError: cannot import name 'strip_dl'`.
- [ ] **Step 3: Implement the compensation.**
  - **`strip_dl`.** The formula is A-10's pre-registered closed form, so its body is given:

```python
def strip_dl(port: dict, lines: list[list[float]]) -> float:
    """The partial inductance (H) that verify's one-cell L adds over the box of `port` on `lines` (A-10): Ruehli's bar
    of the box's length ℓ at the width w_cell of verify's cell (_cell) less the same bar at the box's width w_box, both
    t thick, t the box's z extent, in mm: μ0·ℓ/(2π)·[ln((w_box + t)/(w_cell + t)) + 0.2235·((w_cell + t) −
    (w_box + t))/ℓ]; good to about ±30 %, since it assumes ℓ ≫ w + t."""
    lo, hi = ([f(a, b) for a, b in zip(port["start"], port["stop"])] for f in (min, max))
    p = "xyz".index(port["dir"])
    q = 1 - p  # the box's width axis
    w = _cell(lines[q], lo[q], hi[q])
    a, b, length = hi[q] - lo[q] + hi[2] - lo[2], w[1] - w[0] + hi[2] - lo[2], hi[p] - lo[p]
    return MU0 / (2 * math.pi) * length * 1e-3 * (math.log(a / b) + 0.2235 * (b - a) / length)
```

  - **`verify_spec`.** Insert before `c = c_box(...)` (L183):

```python
        if kind == "L" and compensate:  # A-10: the grid L is the value less the strips' partial inductance
            dl = strip_dl(port, lines)
            if value <= dl:
                raise KrsError("E_VERIFY_STRIPS", ref=ref, value=text, dl=f"{dl * 1e9:.3g}")
            value -= dl
```

    The k check and `values["L"]` then read the compensated L. The refusal order becomes E_VERIFY_VALUE, E_VERIFY_DUMP, then for an L E_VERIFY_STRIPS before E_VERIFY_K. The docstring gains: "an L at its value less strip_dl (A-10), E_VERIFY_STRIPS when that is not above 0; `compensate` False, the K_MAX sweep's, keeps the value".
  - **`messages.py`,** after `E_VERIFY_K`:

```python
    "E_VERIFY_STRIPS": "Part {ref}: verify joins its inductor cell to the pads by strips that add about {dl} nH, which verify takes off the value; \"{value}\" is not above that, so verify cannot place {ref}. Check its value in project.json.",
```

  - Run `python -m pytest tests/test_model_spec.py tests/test_verify.py -q`, then `python -m pytest tests/test_p0b.py -q -k fake_worker`. Expected: the first passes; the second FAILS, because the K_MAX sweep's step raises E_VERIFY_STRIPS (its 14–34 pH on the fake's dt are below lpf915's 125 pH strip term), so `harness.main` returns 1 (Review Focus 3).
- [ ] **Step 4: The sweep uncompensated.** `harness.kmax_sweep`'s L226 becomes `vspec = spec_module.verify_spec(spec, swept, dump, dt, compensate=False)  # the sweep sets the grid L itself (A-10)`, and its docstring reads "…L1 at kmax_values' L, uncompensated (A-10)…". L220, which reads the cell's C at the as-built values, is unchanged: C does not depend on compensation, so the sweep's specs, hashes and the K_MAX evidence stand. Run the fake-worker test again, then `python -m pytest -q`. Expected: all pass. `test_post_real.py`'s openEMS test needs no change: L becomes 14.518 nH and k rises about 1.7 %.
- [ ] **Step 5: Commit.** `git add src/kicad_rf_studio/core/model/spec.py src/kicad_rf_studio/core/messages.py tools/p0b/harness.py tests/test_model_spec.py tests/test_verify.py`, then `git commit -m "feat(verify): the L strips' partial inductance taken off the grid L, E_VERIFY_STRIPS, the K_MAX sweep uncompensated (A-10; design 5.2, E-6; controller recommendation, owner unavailable)"`, then `graphify update .`.

### Task 6 [code]: The single-L coupon and its check

**Files:**
- Create: `tools/p0b2.py`, `tests/test_p0b2.py`
- Modify: `tools/p0.py` (`holds`), `tests/test_p0d.py` (`test_every_tool_enters_its_p0_folder_first`)

**Interfaces:**
- Consumes: `spec.strip_dl`, `pipeline.load`, `build_model`, `layout`, `loads`, `terminate`, `z_part`, `compare`, `port_value`, `PRESETS`; `p0.enter`, `cli`, `cli_run`, `step`, `model_key`, `run_path`, `closed_chain`, `save`, `versions`; in tests, test_p0's `in_process`, test_p0b's `skewed`.
- Produces:
  - `p0.holds(stored: dict, record: dict) -> bool`: whether `stored` (project.json's results or verify) holds the run of the step `record`, `Path(stored.get("run_dir", "")).name == record["result"]["run_dir"]`.
  - `COUPON = ("--start", "TP1.1", "--end", "TP2.1", "--f0", "2.4GHz")`, `L_COUPON = "6.8nH"`.
  - `DL_BAND = (0.0870e-9, 0.1616e-9)`: the closed form's ±30 % on the coupon's L1 box, 0.124283 nH (E-7).
  - `DS21_COUPON_DB = 0.02`, `FLOOR = 10 * PRESETS["normal"][1]`.
  - `single_l(value: str) -> str`.
  - `fit_dl(s, f, c_box: dict, values: dict[str, float], ref: str, measured) -> float`.
  - `a10(verdicts: list[str], dl_h: float | None, ds21_db: float | None) -> dict`: `{"void", "pass"}`, A-10's rule.
  - `coupon(out: Path) -> dict`: `{"dl_cf_h", "band_h", "dl_fit_h": {"uncomp", "comp"} | None, "ds21_uncomp_db", "ds21_comp_db", "verdicts", "void", "pass"}`, every value a plain float, bool, list or None.
  - `main(argv: list[str] | None = None) -> int` with the subcommand `coupon --out DIR`.
  - Its outputs, under `<out>`: the board `boards/coupon_gcpw_l.kicad_pcb`; the project `p0b2/coupon_gcpw_l/project.json`; the steps `a10-run`, `a10-uncomp`, `a10-comp`; and `p0b2/a10.json`.

- [ ] **Step 1: Write the failing tests** in `tests/test_p0b2.py` (SPDX first line):

```python
import json
from pathlib import Path

import pytest

import p0
import p0b2
from kicad_rf_studio import pipeline
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.model.spec import strip_dl
from kicad_rf_studio.core.post.chain import loads, terminate, z_part
from kicad_rf_studio.core.post.waves import grid
from test_p0 import in_process
from test_p0b import skewed

F, _ = grid(915e6, 3, 1.1)


def test_fit_dl_gives_back_a_series_inductance():  # E-7: the fit the coupon check reads ΔL from
    s = skewed(F)[:, :3, :3]
    measured = terminate(s, [0, 1], loads({"L1": z_part("L", 6.8e-9 + 0.1243e-9, None, F)}, ["L1"], {"L1": 3e-15}, F), F)
    assert p0b2.fit_dl(s, F, {"L1": 3e-15}, {"L1": 6.8e-9}, "L1", measured) == pytest.approx(0.1243e-9, rel=1e-6)


@pytest.mark.parametrize(("verdicts", "dl_h", "ds21_db", "rule"), [
    (["converged"] * 7, 0.0870e-9, 0.02, (False, True)), (["converged"] * 7, 0.1616e-9, 0.0, (False, True)),
    (["converged"] * 7, 0.0869e-9, 0.0, (False, False)), (["converged"] * 7, 0.1617e-9, 0.0, (False, False)),
    (["converged"] * 7, 0.124e-9, 0.0201, (False, False)), (["converged"] * 6 + ["t_max"], 0.124e-9, 0.0, (True, False)),
    (["converged"] * 3, None, None, (True, False))])  # the co-simulation alone
def test_a10s_rule_is_e7s(verdicts, dl_h, ds21_db, rule):  # E-7: both parts, edges inclusive; void unless 7 converged
    assert p0b2.a10(verdicts, dl_h, ds21_db) == dict(zip(("void", "pass"), rule))


def test_the_single_l_coupon(tmp_path):  # E-7: coupon_gcpw_pads with an 0402 6.8 nH across a 1 mm cut of its line
    board = tmp_path / "coupon_gcpw_l.kicad_pcb"
    board.write_text(p0b2.single_l(p0b2.L_COUPON), encoding="utf-8")
    assert main(["new", str(board), *p0b2.COUPON, "-o", str(tmp_path / "proj")]) == 0
    project, b, geom, notes = pipeline.load(tmp_path / "proj" / "project.json")
    spec, chain = pipeline.build_model(project, b, geom).spec, project["chain"]
    assert (notes, [(q["ref"], q["value"], q["role"]) for q in chain["series"]], chain["shunt"], project["others"]) == (
        [], [("L1", "6.8nH", "port")], [], [])
    assert [(q["name"], q["part"], q["dir"]) for q in spec["ports"]] == [("P1", False, "y"), ("P2", False, "y"),
                                                                         ("L1", True, "x")]
    assert strip_dl(spec["ports"][2], [spec["mesh"][a] for a in "xyz"]) == pytest.approx(1.24283e-10, rel=1e-4)


def test_the_coupon_check_runs_verify_uncompensated_then_compensated(p0_out, monkeypatch):  # E-7; Review Focus 4
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)  # verify's cells: the fake's dump is empty
    r = p0b2.coupon(p0_out)
    steps = {s: json.loads((p0_out / "steps" / f"{s}.json").read_text(encoding="utf-8"))
             for s in ("a10-run", "a10-uncomp", "a10-comp")}
    grid_l = [next(g["L"] for g in json.loads((Path(steps[s]["result"]["verify"]["run_dir"]) / "model.json")
                                              .read_text(encoding="utf-8"))["grid"] if g["name"] == "L1")
              for s in ("a10-uncomp", "a10-comp")]
    assert grid_l == [pytest.approx(6.8e-9, rel=1e-6), pytest.approx(6.8e-9 - 1.24283e-10, rel=1e-6)]
    assert (r["dl_cf_h"], r["band_h"], r["verdicts"], r["void"]) == (
        pytest.approx(1.24283e-10, rel=1e-4), [0.0870e-9, 0.1616e-9], ["converged"] * 7, False)
    run = steps["a10-run"]
    assert steps["a10-comp"]["key"].startswith(f"{run['key'].split('@')[0]}|{run['result']['run_dir']}@")
    assert {k: v for k, v in json.loads((p0_out / "p0b2" / "a10.json").read_text(encoding="utf-8")).items()
            if k != "versions"} == r
    (p0_out / "steps" / "a10-comp.json").unlink()  # the compensated verify again, keeping no S this time
    monkeypatch.setenv("KRS_FAKE", "nan")
    r = p0b2.coupon(p0_out)
    assert (r["verdicts"], r["dl_fit_h"], r["void"], r["pass"]) == (["converged"] * 5, None, True, False)
```

  - In `tests/test_p0d.py`, `test_every_tool_enters_its_p0_folder_first` gains the case `("p0b2", ["coupon", "--out", "{p0}"], "p0")`, with `import p0b2` and `"p0b2": p0b2.main` in its table.

- [ ] **Step 2: Run** `python -m pytest tests/test_p0b2.py tests/test_p0d.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p0b2'`.
- [ ] **Step 3: Implement** `tools/p0b2.py`, and `p0.holds` as Interfaces gives it.
  - The module docstring: "Plan 7's gate tool (design 2026-10-26 §5.2): A-10's single-L coupon check (E-7), its runs resumable p0.steps in the fresh P0 folder. Dev-time only, like p0: the package never imports it. Run: python tools/p0b2.py coupon --out DIR". Then `# ponytail: single-use, plan 7's checks and its one P0-B2`.
  - `single_l` is the coupon's definition, so its body is given:

```python
def single_l(value: str) -> str:
    """tests/fixtures/coupon_gcpw_pads.kicad_pcb with an 0402 inductor of `value` across a 1 mm cut of its line at
    x 110 (A-10's coupon, E-7): net 3 LINE_B; the line 100→120 split into 100→109.5 on LINE and 110.5→120 on LINE_B;
    TP2's pad on LINE_B; lpf915's L1 footprint at (110, 100) between LINE and LINE_B, its Value `value`. ValueError
    when an edit does not apply exactly once."""
    def once(text: str, old: str, new: str) -> str:
        if text.count(old) != 1:
            raise ValueError(f"p0b2: {old!r} is in the board {text.count(old)} times, not once")
        return text.replace(old, new)

    text = (p0.FIX / "coupon_gcpw_pads.kicad_pcb").read_text(encoding="utf-8")
    lpf = (p0.FIX / "lpf915.kicad_pcb").read_text(encoding="utf-8")
    a = lpf.index('\t(footprint "Inductor_SMD:L_0402_1005Metric"')
    l1 = lpf[a:lpf.index("\n\t(footprint", a + 1) + 1]
    for old, new in (("(at 106.5 100)", "(at 110 100)"), ('(net 4 "RF_B")', '(net 1 "LINE")'),
                     ('(net 5 "RF_C")', '(net 3 "LINE_B")'), ('"Value" "15nH"', f'"Value" "{value}"')):
        l1 = once(l1, old, new)
    text = once(text, '\t(net 2 "GND")\n', '\t(net 2 "GND")\n\t(net 3 "LINE_B")\n')
    text = once(text,
                '\t(segment\n\t\t(start 100 100)\n\t\t(end 120 100)\n\t\t(width 0.6)\n\t\t(layer "F.Cu")\n\t\t(net 1)\n',
                '\t(segment\n\t\t(start 100 100)\n\t\t(end 109.5 100)\n\t\t(width 0.6)\n\t\t(layer "F.Cu")\n\t\t(net 1)\n'
                '\t\t(uuid "00000000-0000-4000-8000-0000000000a1")\n\t)\n'
                '\t(segment\n\t\t(start 110.5 100)\n\t\t(end 120 100)\n\t\t(width 0.6)\n\t\t(layer "F.Cu")\n\t\t(net 3)\n')
    i = text.index('(net 1 "LINE")', text.index("\t(footprint"))  # TP2, the first footprint, at (120, 100)
    text = text[:i] + '(net 3 "LINE_B")' + text[i + len('(net 1 "LINE")'):]
    i = text.index("\t(segment")
    return text[:i] + l1 + text[i:]
```

  - `fit_dl`: least squares over every f and entry, real and imaginary parts, of `terminate(s, [0, 1], loads(z, refs, c_box, f), f) - measured`. Each part port is closed by its ideal `z_part(part_kind(r), values[r], None, f)` with `ref` at `values[ref] + x[0] * 1e-9`, using `scipy.optimize.least_squares(residual, [0.0])`. Return `float(fit.x[0] * 1e-9)`, ΔL in H. Since `values` holds the grid L, the fit returns the strip term whatever value sat in the grid.
  - `a10` is the pre-registered rule (E-7), so its body is given:

```python
def a10(verdicts: list[str], dl_h: float | None, ds21_db: float | None) -> dict:
    """A-10's rule (E-7) on the coupon's job verdicts, the uncompensated pair's fitted ΔL (H) and the compensated
    run's |ΔS21(f0)| (dB): "void" unless all seven jobs converged; "pass" when not void, ΔL inside DL_BAND and
    |ΔS21(f0)| at most DS21_COUPON_DB, both edges inclusive."""
    void = verdicts != ["converged"] * 7
    return {"void": void, "pass": not void and DL_BAND[0] <= dl_h <= DL_BAND[1] and ds21_db <= DS21_COUPON_DB}
```

  - `coupon(out)`, in this order:
    1. Enter: `out = p0.enter(out)`.
    2. Make the project when it is missing: write `<out>/boards/coupon_gcpw_l.kicad_pcb` from `single_l(L_COUPON)`, then `p0.cli("new", str(board), *COUPON, "-o", str(pj.parent))`, raising RuntimeError on a non-zero exit, as `harness.project` does. Then `key = p0.model_key(pj)`.
    3. `run = p0.step(out, "a10-run", key, partial(p0.cli_run, pj, "run"))`.
    4. Only when a10-run stored its results (`run["result"]["jobs"]` is not None): `dl = strip_dl(L1's port, its mesh lines)` from its run folder's `model.json` (`dl_cf_h`, else None), then the steps `a10-uncomp` and `a10-comp`, both keyed `f"{key}|{run['result']['run_dir']}"`. Each work retunes L1 through `p0.cli("retune", str(pj), f"L1={v}")` (RuntimeError on a non-zero exit), then returns `{**r, "verify": load_project(pj)["verify"] if r["jobs"] is not None else None}` with `r = p0.cli_run(pj, "verify")`. For a10-uncomp, v is `f"{(port_value('L1', L_COUPON) + dl) * 1e9:.6f}nH"` (6.924283nH), so verify's grid holds 6.8 nH: the uncompensated construction on A-10's code (E-7). For a10-comp, v is `L_COUPON`.
    5. `verdicts`: the verdicts of the jobs each step stored (cli_run's `jobs`), in step order; a step that stored none, or did not run, adds nothing.
    6. When the seven converged, the fit, on the project's `results` (SystemExit unless `p0.holds` them for a10-run):
       - `lay = layout(project, results)`, the 3-port P1, P2, L1;
       - each pair's measured S is `layout(project, its step's "verify").s`, and its grid L is L1's `"L"` in that verify run's `model.json`;
       - `dl_fit_h[name] = fit_dl(lay.s, lay.f, results["c_box"], {"L1": grid L}, "L1", measured)`;
       - `ds21_uncomp_db = compare(measured_uncomp, p0.closed_chain(pj, ideal=True)[1], lay.f, lay.markers[0], FLOOR)["ds21_db_f0"]`, report only: after a10-comp's retune the project holds L1 at 6.8 nH, so that is verify's own closure;
       - `ds21_comp_db` is a10-comp's stored `verify.compare.ds21_db_f0`.

       Otherwise `dl_fit_h`, `ds21_uncomp_db` and `ds21_comp_db` are None.
    7. `result` holds `dl_cf_h`, `"band_h": list(DL_BAND)`, `dl_fit_h`, both ds21 values, `verdicts` and `a10(verdicts, the uncompensated ΔL, ds21_comp_db)`. `p0.save(out / "p0b2" / "a10.json", {**result, "versions": p0.versions()})`, and return `result`.
  - `main`: argparse with the subcommand `coupon --out DIR`, which prints the saved JSON and returns 0.
- [ ] **Step 4: Run** the two files, then `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit.** `git add tools/p0b2.py tools/p0.py tests/test_p0b2.py tests/test_p0d.py`, then `git commit -m "feat(tools): p0b2's single-L coupon, fit_dl and a10, A-10's pre-registered check (design 5.2, E-7)"`, then `graphify update .`.

### Task 7 [run]: The single-L coupon in FDTD

- **Before:** Tasks 5–6 are committed and `git status --porcelain` is empty. The date is before 2026-11-19; otherwise apply the ceiling's branch. The idle check prints `[0, 0, 0]`.
- **Command:** `.venv\Scripts\python.exe tools\p0b2.py coupon --out <P0-2>`
- **Expected machine time:** about 45–60 min on an idle PC: the co-simulation's 3 jobs take 14–28 min, and each verify's 2 jobs about 14 min. The variant has 3,194,880 cells, 1.24× the pad coupon, which ran 667.5 s wall for 2 jobs (P0-A re-check).
- **Expected results (pre-registered; E-7):**
  - The pass rule (`a10`): every one of the 7 jobs converged, else the check is void; `dl_fit_h.uncomp` lies in [0.0870, 0.1616] nH; and `ds21_comp_db` ≤ 0.02 dB.
  - `dl_cf_h` 0.124283 nH.
  - The judged values: `dl_fit_h.uncomp` about 0.124–0.133 nH (the closed form; the development fit at f ≤ 2 GHz read 0.133), and `ds21_comp_db` ≈ 0.6547 × |ΔL_true − 0.124283| dB, about 0.006 dB at 0.133 nH. So the rule passes only for a true ΔL in about [0.094, 0.155] nH, inside the band.
  - The band is not widened, though an on-mesh PEEC reads 0.0865 nH, just below it (the open risk). A PEEC-like 0.0865 nH is predicted to fail both parts (about 0.025 dB).
  - Report only: `ds21_uncomp_db` about 0.081 dB, from the closed form's 0.6547 dB/nH; and `dl_fit_h.comp` within 0.01 nH of `dl_fit_h.uncomp`.
- **Outputs:** in `<P0-2>`: `boards\coupon_gcpw_l.kicad_pcb`, `p0b2\coupon_gcpw_l\` (the project and its `results\`), `steps\a10-{run,uncomp,comp}.json` with their run folders under `data\`, and `p0b2\a10.json`.
- **Done when:** the command exits 0, and `.venv\Scripts\python.exe -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print(d['pass'], d['void'], d['dl_fit_h'], d['ds21_comp_db'], d['ds21_uncomp_db'], d['verdicts'])" <P0-2>\p0b2\a10.json` prints them.
  - A step that raises stops the command. Fix it test-first under the fix rule and rerun the same command. A `tools/` fix keeps the finished steps; a `src/` fix reruns all three, since their keys end in the code id, so the coupon is judged on one code.

### Task 8 [decide]: A-10 adopted, or reverted

**Reads:** `<P0-2>\p0b2\a10.json`. The rule (E-7): A-10 is adopted when `pass` is true. A void check is not a pass. `<x>` is `dl_fit_h.uncomp` in nH to 4 decimals, `<y>` is `ds21_comp_db` to 3 decimals, and `<date>` is the day this task runs.

**Branch adopt:**
- [ ] **Step 1: Amendment A-10** in the Stage 1 spec.
  - Append to the inductor bullet (L470): "The strips are one cell wide, and over the box's length ℓ they add a partial inductance that the co-simulation's port box does not have. verify takes it off the value: the grid L is L_part − ΔL, with ΔL = (μ0·ℓ/2π)·[ln((w_box + t)/(w_cell + t)) + 0.2235·((w_cell + t) − (w_box + t))/ℓ]. That is Ruehli's bar at the cell's width less the same bar at the box's width, with t the copper thickness, good to about ±30 %; it is 0.125 nH on lpf915's L1. An inductor whose value is not above ΔL is refused and named (E_VERIFY_STRIPS). On the single-L coupon of `<date>`, the fitted ΔL read `<x>` nH against the closed form's 0.124 nH, and the compensated |ΔS21(f0)| `<y>` dB (A-10, plan 7: controller recommendation, owner unavailable)."
  - L471's opening, "the k check, k = dt/(2·√(L·C)) ≤ 0.45, makes sure", becomes "the k check, k = dt/(2·√(L·C)) ≤ 0.45 with L the grid L (the K_MAX sweep set the grid L directly; A-10, plan 7: controller recommendation, owner unavailable), makes sure".
  - The Status line gains: "On `<date>`, plan 7's L-strip compensation amended §7.6 (A-10) the same way."
- [ ] **Step 2: Check** that `Select-String … -Pattern "A-10, plan 7"` finds 2 lines and that the privacy gate reports no hit.
- [ ] **Step 3: Commit** A-10 alone: `git commit -m "docs(spec): A-10, verify's L strips compensated in §7.6 (controller recommendation, owner unavailable)"`.
- [ ] **Step 4: Return** the coupon's values against the rule, the registered predictions and the report-only expectations.

**Branch fail** (a miss or a void check):
- [ ] **Step 1:** `git revert --no-commit`, newest first, every commit since Task 4's last commit that touches `src`, `tools` or `tests`: Task 6's, Task 5's and any fix commit made for Task 7. Then `git diff <Task 4's last commit> --stat -- src tools tests` prints nothing. A fix that is needed without A-10 is then made again in a commit of its own and named in the report.
- [ ] **Step 2:** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 3: Commit.** `git commit -m "revert: plan 7's L-strip compensation — A-10's coupon check <missed|was void> (design 5.2, E-7; controller recommendation, owner unavailable)"`.
- [ ] **Step 4: Return** the miss with its values. P0-B2 is then a no-go (E-10): the controller goes to Task 14 when A-9 was adopted, and then to Task 15.

## Phase 3 — the go/no-go (only when Tasks 4 and 8 both adopted their fix)

### Task 9 [code]: `p0b2.predict`, on development data only

**Files:**
- Modify: `tools/p0b2.py`, `tests/test_p0b2.py`

**Interfaces:**
- Consumes: `layout` with tails, `Layout.s_dft`, `strip_dl`, `loads`, `terminate`, `z_part`, `part_kind`, `port_value`, `parts`, `compare`, `p0.criterion1`, `FLOOR`; in tests, `harness.main`.
- Produces:
  - `DEV = {"B1": "20f6c687", "B2": "9cb3e824"}`: P0-B's stored B1 and verify model hashes.
  - `BANDS_GHZ = ((0.0, 1.0), (1.0, 2.0), (2.0, 2.5), (2.5, 2.8), (2.8, 3.1))`.
  - `bands(a, b, f) -> list[dict]`: `[{"band_ghz", "ds_max", "f_hz", "entry"}]`.
  - `predict(p0_dir: Path) -> dict`: `{"inputs": {"b1", "b2", "dl_h"}, "stored", "uncorrected", "tails", "tails_dl", "bands", "go"}`.
  - The subcommand `predict --p0 DIR`, which prints predict's dict plus `"versions"` as JSON; the module docstring gains P0-B2's go/no-go on P0-B's stored records (E-10) and `| predict --p0 DIR`.

- [ ] **Step 1: Write the failing test** (add `from kicad_rf_studio.core.project import load_project` and `from p0b import harness`):

```python
def test_predict_reads_p0bs_stored_records_only_and_writes_nothing(p0_out, monkeypatch):  # Review Focus 5; E-10
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    assert harness.main(["--out", str(p0_out), "--only", "B1"]) == 0
    pj = p0_out / "p0b" / "projects" / "B1" / "project.json"
    refusal = "p0b2: predict reads P0-B's stored B1 and B2 only (development data, design 5.2); {} holds model {}"
    with pytest.raises(SystemExit) as e:  # plan 6's B1 in <P0-2>: not DEV's model, and no verify yet
        p0b2.predict(p0_out)
    assert str(e.value) == refusal.format(pj, load_project(pj)["results"]["model_hash"][:8])
    assert harness.main(["--out", str(p0_out), "--only", "B2"]) == 0
    data = load_project(pj)
    monkeypatch.setattr(p0b2, "DEV", {"B1": data["results"]["model_hash"][:8], "B2": data["verify"]["model_hash"][:8]})
    before = sorted((p.relative_to(p0_out), p.stat().st_mtime_ns) for p in p0_out.rglob("*"))
    r = p0b2.predict(p0_out)
    assert sorted((p.relative_to(p0_out), p.stat().st_mtime_ns) for p in p0_out.rglob("*")) == before
    stored = {k: data["verify"]["compare"][k] for k in ("ds21_db_f0", "ds11_f0", "ds_max")}
    assert r["stored"] == stored and all(abs(r["tails"][k] - v) <= 1e-12 for k, v in stored.items())  # verify's own path
    assert r["inputs"]["dl_h"] == {"L1": pytest.approx(1.24812e-10, rel=1e-5)}  # lpf915's L1 box on plan 6's mesh
    assert r["go"] is p0.criterion1(r["tails_dl"])["pass"]
    assert [b["band_ghz"] for b in r["bands"]] == [list(b) for b in p0b2.BANDS_GHZ]
    assert p0b2.main(["predict", "--p0", str(p0_out)]) == 0
```

- [ ] **Step 2: Run** `python -m pytest tests/test_p0b2.py -q -k predict`. Expected: FAIL with `AttributeError: module 'p0b2' has no attribute 'predict'`.
- [ ] **Step 3: Implement.**
  - **`bands`.** For each band of BANDS_GHZ holding a point of f in [lo, hi) GHz: the largest complex |b − a| there, its f and its entry `f"S{i + 1}{j + 1}"`. `band_ghz` is `[lo, hi]`.
  - **`predict(p0_dir)`.** It never calls `p0.enter` and writes nothing.
    1. Load `<p0_dir>/p0b/projects/B1/project.json`.
    2. Refuse, with the SystemExit text of the test, at the first of `results.model_hash` and `verify.model_hash` (read with `.get`: a project without verify holds none) that does not start with DEV's prefix. It names that hash's first 8, or "none". So plan 6's B1 refuses on its results' hash before verify is read.
    3. Build `lay = layout(project, results)` and `own = layout(project, verify run)`, each reading its run folder by the absolute path project.json holds. On this code, A-9's tails are inside `s_matrix`.
    4. Compute `dl_h = {q["name"]: strip_dl(q, lines) for q in the run's model.json ports if q["part"] and part_kind(q["name"]) == "L"}`, with `lines` that model.json's mesh. The development verify is uncompensated, so A-10 is emulated on the co-simulation's side: `zk(x) = loads({r: z_part(part_kind(r), port_value(r, parts(project)[r]["value"]), None, f) + 2j·π·f·x·dl_h.get(r, 0) for r in refs}, refs, results["c_box"], f)`, under `# ponytail: A-10 emulated to first order on the co-simulation's side (r2's equivalent); the coupon measured it on its own construction`.
    5. Every comparison is `compare(a, terminate(b, ext, zk(x), f), f, k0, FLOOR)`:
       - "uncorrected" takes `own.s_dft` and `lay.s_dft` at x = 0;
       - "tails" takes `own.s` and `lay.s` at x = 0;
       - "tails_dl" takes the same at x = 1.
    6. `stored` holds verify.compare's three terms. "inputs" holds the two hash prefixes and `dl_h`. "bands" is `bands(own.s, terminate(lay.s, ext, zk(1), f), f)`, and "go" is `p0.criterion1(tails_dl)["pass"]`.
  - **Docstring.** "The go/no-go of P0-B2 on development data only (design 5.2, E-10): central ΔL; A-11 is not adopted (E-8) and is not in it; an A-12 enters only through its own amendment, as its own row."
- [ ] **Step 4: Run** the file, then `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit.** `git add tools/p0b2.py tests/test_p0b2.py`, then `git commit -m "feat(tools): p0b2.predict, P0-B2's go/no-go on P0-B's stored records (development data only; E-10)"`, then `graphify update .`.

### Task 10 [decide]: The residual near f2 — attributed, or a stated limit (E-9)

**Bounds:**
- This is one task. It runs CPU only, on development data only, and ends by 2026-11-12. Unfinished by then, the residual is a stated limit, and A-12's code, if committed, is reverted (the not-attributed branch).
- **Pre-registered here, before Step 1** (design §5.2; E-8, E-9):
  - A-12 is not the box term again: no series term in a part's branch from the port box against verify's in-grid construction, and no refinement of A-11's estimate, its pour, lid or box-end currents included. That physics missed its rule on this data (E-8), and a re-estimate needs new data (design §5.2, A miss), such as r3's X-A run, which this plan does not fund.
  - Nor may A-12 touch an inductor's branch, verify's L cell or its strips: A-10's coupon judged those.
  - An estimate's inputs are the model (model.json, its mesh, the parts) and physics only: no pole, residue, a_db, fit or scan of P0-B's records, r3's or p7-gate's. A closure term takes one formula for every part port of every kind, never one part alone.
  - Step 1 forms at most one frozen estimate per question and returns every estimate it formed. Nothing applies a candidate to `predict`, `compare` or `terminate` before Step 3, which computes the check once.
- **Step 1 may read:** `<P0>`, read-only: `p0b\projects\B1\project.json` and the run folders it names (B1's six jobs, B2's two), with their `model.json`, `waves.npz`, `setup.json` and operator dumps. Also the design, the repo but `tests\fixtures\traces` and `tests\fixtures\p0d` (copies of `<P0-2>`'s records), `.superpowers\sdd\plan7-research\` but p7-gate's F2 and `<R7>\p0b2\scan.py`, and `.superpowers\sdd\stage2-plan1-research\`'s r1, r2, r4 and r5 (r3's fits target this comparison).
- **Step 1 may run:** `.venv\Scripts\python.exe -I -B` scripts in a scratch folder outside the repo and outside both P0 folders, each under 10 minutes of CPU. That includes `tools\p0b2.py predict --p0 <P0>` on the committed code (the baseline only), `waves.tail` on the development records, and `pipeline.load` with `build_model` on copies of `tests\fixtures` boards made in that scratch folder.
- **Step 1 may not:**
  - run openEMS, pytest, a harness, a p0 step, `p0.enter`, or the product's `cost`, `run` or `verify`;
  - read `<P0-2>`;
  - apply a candidate to the comparison, or fit anything to it;
  - write into the repo.

**The baseline:** predict's `tails_dl` on the committed code. Expected: max |ΔS| 0.0318 at f2 on S11, with 33 points above 0.03 from 2.751 to 3.016 GHz, and an S11 phase lead of about +1.2° over 2.1–2.9 GHz.

**The questions,** in this order:
1. **Verify's near-lossless 3.096 GHz mode** (τ 234–7104 ns, verify-only, just above f2; probably why B2's P2 reached T_max): which in-grid construction carries it (L1's cell and strips, a grid C's cell, the fills), and its τ and residues on verify's channels from the v3b fits of B2's records. These are reported, never an estimate's input, and its effect on S is not computed.
2. **The band edge's weak excitation:** the run's and verify's `a_db` near f2, and the S error that the stop rule's 2e-3 tolerance and the tails' fit residual allow there.
3. **Any other construction difference** between the co-simulation and verify that the rules above leave open, estimated from the model alone.

**Attribution rule (pre-registered here):** a cause is attributed only when both hold.
- Its estimate obeys the rules above. It has a formula, inputs and an error band, and is written down in Step 1's text before its check is computed.
- Its central value, applied once to the baseline as predict applies A-10 (a term on the co-simulation's side, or on verify's own S), leaves max |ΔS| up to f2 ≤ 0.025, with |ΔS21(f0)| and |ΔS11(f0)| no larger than the baseline's (A-11's rule).

A cause that is not a construction change, such as question 2's excitation, is reported and never attributed.

- [ ] **Step 1 (a subagent):** the diagnosis. Return, for each question, either the cause ruled out with its numbers, or one frozen estimate: its formula, inputs and band, the construction change it implies, and where that change goes (`verify_spec`, or the closure). Return every other estimate formed too.
- [ ] **Step 2 (the controller):**
  - **No frozen estimate:** the residual is a stated limit, with its numbers; go to Task 11.
  - **A frozen estimate:** stop, and append `## Amendment: A-12 pre-registration (<date>)` to this plan. It holds:
    - Step 1's estimate verbatim, and the attribution rule above as A-12's adoption rule;
    - a full [code] task, test-first on fakes only: Files, Interfaces, the failing test, the implementation and the commit message, for the product change and its row in `predict` (`tails_dl_a12`, which Task 11's `go` then reads; `uncorrected`, `tails` and `tails_dl` stay free of A-12), with how a project or record made before A-12 behaves;
    - that Tasks 3 and 7 stand, since A-12 touches neither the tails nor verify's L;
    - its spec text.

    Commit it with `git commit -m "docs(plan): plan 7's A-12 pre-registration (E-9; controller recommendation, owner unavailable)"`, then carry out that code task.
- [ ] **Step 3 (once, CPU):** `.venv\Scripts\python.exe tools\p0b2.py predict --p0 <P0>` on the code with A-12: its A-12 row against the baseline.
  - **Attributed:** amendment A-12, in its own commit.
  - **Not attributed, or not run by 2026-11-12:** revert A-12's code in one commit, and register A-12 as a known difference with its range, as A-11 is.
- [ ] **Step 4:** Return the section text for Task 15: each question's result, every estimate formed, and A-12's outcome or the stated limit.

### Task 11 [decide]: The go/no-go, and P0-B2's pre-registration

**Reads:** the output of `.venv\Scripts\python.exe tools\p0b2.py predict --p0 <P0>` on the committed code, saved by the controller as `<P0-2>\p0b2\predict.json`; and the outcomes of Tasks 4, 8 and 10.

**Rule (E-10):** go only when all of these hold:
- A-9 was adopted (Task 4), and A-10 was adopted (Task 8);
- `uncorrected` equals `stored` within 1e-9 in each of its three terms, so the plain reduction reproduces P0-B's stored comparison (0.1019400 dB, 0.0108751, 0.0925716; the research matched every printed digit). A miss, or predict refusing, is a no-go: the prediction is not trusted, and the report says why;
- `go` is true: criterion 1 on `tails_dl`, at the central ΔL only, or on A-12's row when Task 10 attributed it.

On today's data the prediction reads 0.0318, a no-go, unless Task 10 attributes a fix.

- [ ] **Step 1:** Run `.venv\Scripts\python.exe tools\p0b2.py predict --p0 <P0> > <P0-2>\p0b2\predict.json` (pwsh 7 writes UTF-8). Check the second rule.
- [ ] **Step 2:** Append `## P0-B2 pre-registration (<date>)` to this plan, filled from predict.json, and commit it with `git commit -m "docs(plan): P0-B2's pre-registration and go/no-go — <go|no-go> (E-10, E-11; controller recommendation, owner unavailable)"`. This commit lands before Tasks 12 and 13. The section holds:
  - **The decision:** go or no-go, or not trusted; the three terms and nulls of the row `go` reads; the five band maxima; `dl_h` (0.1262 nH on the development mesh, the closed form on its models); p7-gate's ×0.7 and ×1.3 row (0.0317 and 0.0318, report only).
  - **Configuration:**
    - `<P0-2>`, steps `p0b2-B1` then `p0b2-B2`;
    - `<P0-2>\p0b2\lpf915\project.json`, made by `new` with harness.NEW (U1.1→J1.1, 915 MHz, lid 2.5 mm) and `mesh.reach_h` 6.0 and `t_max_s` 80 ns set in it;
    - Normal, n 2, the 3 % fit2d gate and the 0.8 dt floor, as `new` writes them.
  - **Blocking:**
    - criterion 1 through `p0.criterion1` on `verify.compare`, with §9.3's limits: |ΔS21(f0)| ≤ 0.1 dB, |ΔS11(f0)| ≤ 0.02, max |ΔS| ≤ 0.03 up to f2, every null shift ≤ 2 %; no stored comparison fails it;
    - B1 6/6 and B2 2/2 converged;
    - D-40's evidence `ok` for both (`cut_delta` ≤ 2e-3, with tails, E-4);
    - both commands exit 0.
  - **A B1 that stores no results** (a job kept no S, or a refusal) is judged, not fixed: B2 is not started, and P0-B2 fails on what B1's records show (Task 12's `run`).
  - **Not blocking:**
    - EMerge, recorded in the report as a deviation from §9.3 L574–577 with no amendment (E-11);
    - B4, dropped by A-5 alone, since plan 6's D-27 advice branch turned E_STAIRCASED into W_STAIRCASED;
    - W_TAIL_FALLBACK and W_TAIL_LARGE, report only.
  - **Known differences, registered:**
    - A-9's tail fit: its reproduction error, E1 as Task 3 measured it (development: 0.0021 at a 13.21 ns cut);
    - A-10: ΔL 0.1248 nH ±30 % on P0-B2's mesh, which moves ΔS21(f0) by +0.062 ± 0.005 dB against the uncompensated construction (the design's +0.059 ± 0.005, recomputed on plan 6's mesh by p7-Lcheck). P0-B2 runs compensated only, so the report quotes predict's tails → tails_dl shift against it, report only;
    - A-11's box term: |ΔS| up to 0.0063 (0.0031–0.0125) near f2, and ΔS21(f0) +0.0021 dB (+0.0010 to +0.0042);
    - E-9's outcome (Task 10): A-12, or the residual as a stated limit with its numbers.
  - **Expected values (predictions, not rules):**
    - B1's model key `8ac8e62a…`, 4,467,060 cells (332 × 195 × 69 lines), fit2d at most 2.374 %;
    - B1's jobs converge at about 12–30 ns, and B1 prints W_TAIL_LARGE (the run chain's tail read 0.0695 on the development data);
    - B2 prints W_TAIL_LARGE too: the closed co-simulation chain's tail read 0.0803 there;
    - B2's P2 converges at about 42 ns, well before 80 ns;
    - criterion 1 as predict printed it;
    - report only: the band table and the value at 2.9705 GHz.
  - **Machine time:** B1 about 19,714 s (5.5 h, B6's count); B2 about 3.3–3.8 h, worst 6.7 h to 80 ns; in all about 8.8–9.3 h, worst 12.2 h.
  - **Ceiling:** one run.
    - An interrupted step leaves no record and resumes.
    - A loaded step keeps its record (FDTD is deterministic) and is left out of section 6 only.
    - A code change after B2's record spends the run; P0-B2 is spent once B2's record or `p0b2.json` exists.
  - **On pass:** withdraw P0-C's "do not start" (controller recommendation, owner unavailable); RETUNE_VALIDATED stays False until P0-C passes (A-4, D-15). **On fail:** the label stays.
- [ ] **Step 3:** On go, go to Task 12. On no-go, or not trusted, go to Task 14: P0-B2 is not spent (E-12).

## Phase 3b — P0-B2 (go only)

### Task 12 [code]: P0-B2's gate in `tools/p0b2.py`

**Files:**
- Modify: `tools/p0b2.py`, `tests/test_p0b2.py`, `tools/p0b/harness.py` (`made`, `_table`, `_rows`), `tests/test_p0d.py`

**Interfaces:**
- Consumes: `harness.NEW`, `harness.evidence`, `harness._cell`, `harness._path`, `harness.VARIANTS`; `p0.edit`, `step`, `records`, `summary`, `closed_chain`, `criterion1`, `save`, `versions`, `machine`, `table`, `holds`, `runs.load_settings`, `runs.machine_key`; Task 9's `bands`, `FLOOR`.
- Produces:
  - `harness.made(out: Path, pj: Path, board: str, edits: dict) -> Path`, and `harness._table(title, items)` and `_rows(limits, **cmps)`, moved out unchanged.
  - `EDITS = {"mesh.reach_h": 6.0, "t_max_s": 80e-9}`, `STEPS = ("p0b2-B1", "p0b2-B2")`, `JOBS = {"B1": 6, "B2": 2}`, `MODE_HZ = 2.9705e9`.
  - `project(out: Path) -> Path`; `run(out: Path) -> dict`; `measure(out: Path) -> dict`; `decide(m: dict) -> dict`; `tables(result: dict) -> str`; `write(out: Path) -> dict`.
  - The subcommands `run --out DIR` and `report --out DIR`.
  - `p0b2.json`'s keys: `gate` ("P0-B2"), `versions`, `calibration` (PF-29: the value only), `project` {mesh, t_max_s, preset, lid_height_mm, model_hash}, `runs` {B1, B2: p0.summary}, `evidence` {B1, B2: harness.evidence}, `verdicts`, `consistency` (the stored `verify.compare`, or None), `bands`, `at_mode` {f_hz, ds}, `warnings` {B1, B2}, `dt_ratios`, `decisions`, `machine`.

- [ ] **Step 1: Write the failing tests** (add `from kicad_rf_studio.core.project import GATES, save_project` and `import privacy_gate as gate`):

```python
BASE = {"consistency": {"ds21_db_f0": 0.05, "ds11_f0": 0.005, "ds_max": 0.02, "nulls": []},
        "verdicts": {"B1": ["converged"] * 6, "B2": ["converged"] * 2},
        "evidence": {"B1": {"ok": True}, "B2": {"ok": True}}, "runs": {"B1": {"exit": 0}, "B2": {"exit": 0}}}
CONSISTENCY = "consistency: the co-simulation against verify fails criterion 1 (spec 9.3)"
STAYS = "'do not start' stays (controller recommendation, owner unavailable)"


def test_the_p0b2_project_is_a_fresh_lpf915_with_its_edits(p0_out, monkeypatch):  # E-11
    monkeypatch.setattr(p0, "cli", in_process)
    pj = p0b2.project(p0_out)
    d = load_project(pj)
    assert pj == p0_out / "p0b2" / "lpf915" / "project.json"
    assert (d["mesh"], d["t_max_s"], d["lid_height_mm"], d["preset"], d["gates"]) == (
        {"n": 2, "reach_h": 6.0}, 80e-9, 2.5, "normal", dict(GATES))
    save_project(pj, {**d, "t_max_s": 4e-8})  # an interruption between new and the edits
    assert load_project(p0b2.project(p0_out))["t_max_s"] == 80e-9


@pytest.mark.parametrize(("change", "fails"), [
    ({}, []), ({"consistency": {"ds_max": 0.03}}, []),  # the limit is inclusive
    ({"consistency": {"ds_max": 0.0301}}, [CONSISTENCY]), ({"consistency": {"ds21_db_f0": 0.1001}}, [CONSISTENCY]),
    ({"consistency": {"ds11_f0": 0.0201}}, [CONSISTENCY]),
    ({"consistency": {"nulls": [{"f_hz": 1e9, "shift": None}]}}, [CONSISTENCY]),
    ({"verdicts": {"B2": ["converged", "t_max"]}}, ["B2: its jobs ended converged, t_max, not every one converged (spec 9.3)"]),
    ({"evidence": {"B2": {"ok": False}}}, ["B2: D-40's live evidence is not ok"]),
    ({"runs": {"B1": {"exit": 2}}}, ["B1: the command exited 2"])])
def test_p0b2_decides_by_criterion_1_and_every_job_converged(change, fails):  # E-11, spec 9.3
    m = {key: {**BASE[key], **change.get(key, {})} for key in BASE}
    d = p0b2.decide(m)
    assert d["verdict"] == {"value": "fail" if fails else "pass", "fails": fails} and d["retune_validated"] is False
    assert d["p0c"] == (STAYS if fails else "ready: withdraw 'do not start' (controller recommendation, owner unavailable)")


def test_p0b2_steps_are_keyed_by_the_model_and_b1s_run_and_a_spent_run_refuses(p0_out, monkeypatch):  # Review Focus 4
    monkeypatch.setattr(p0, "cli", in_process)
    calls = []
    monkeypatch.setattr(p0, "cli_run", lambda pj, command: calls.append(command) or {
        "exit": 0, "run_dir": f"lpf915-{command}", "jobs": [], "wall_s": 1.0})
    monkeypatch.setattr(p0, "model_key", lambda pj: "h")
    monkeypatch.setattr(p0, "code_id", lambda: "c")
    monkeypatch.setattr(p0b2, "write", lambda out: {})
    p0b2.run(p0_out)
    keys = [json.loads((p0_out / "steps" / f"{s}.json").read_text(encoding="utf-8"))["key"] for s in p0b2.STEPS]
    assert keys == ["h@c", "h|lpf915-run@c"] and calls == ["run", "verify"]
    with pytest.raises(SystemExit) as e:
        p0b2.main(["run", "--out", str(p0_out)])
    spent = p0_out.resolve() / "steps" / "p0b2-B2.json"
    assert str(e.value) == (f"p0b2: P0-B2 is spent: {spent} exists (design 5.2: one run); write the report with: "
                            f"report --out {p0_out.resolve()}")
    spent.unlink()  # B2 never finished: run reaches B2 again, and B1's record stands
    p0b2.run(p0_out)
    assert calls == ["run", "verify", "verify"]


def test_a_b1_that_stores_no_results_is_judged_and_b2_never_runs(p0_out, monkeypatch):  # Review Focus 4; E-11
    monkeypatch.setattr(p0, "cli", in_process)
    calls = []
    monkeypatch.setattr(p0, "cli_run", lambda pj, command: calls.append(command) or {
        "exit": 4, "run_dir": None, "jobs": None, "wall_s": None})  # a job diverged: run kept no S
    monkeypatch.setattr(p0, "model_key", lambda pj: "h")
    d = p0b2.run(p0_out)
    assert calls == ["run"] and d["decisions"]["verdict"]["fails"] == [
        CONSISTENCY, "B1: its jobs ended nothing, not every one converged (spec 9.3)",
        "B1: D-40's live evidence is not ok", "B1: the command exited 4",
        "B2: its jobs ended nothing, not every one converged (spec 9.3)", "B2: D-40's live evidence is not ok"]
    with pytest.raises(SystemExit) as e:  # judged, so spent
        p0b2.main(["run", "--out", str(p0_out)])
    assert str(e.value).startswith(f"p0b2: P0-B2 is spent: {p0_out.resolve() / 'p0b2' / 'p0b2.json'} exists")


def test_p0b2_on_the_fake_worker_writes_a_plain_private_free_gate_json(p0_out, monkeypatch):  # E-11; D-51
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    assert p0b2.main(["run", "--out", str(p0_out)]) == 0
    text = (p0_out / "p0b2" / "p0b2.json").read_text(encoding="utf-8")
    data = json.loads(text)
    json.dumps(data, allow_nan=False)
    assert gate.scan_text(text, [], generic=True) == []
    # the fake's verify 2-port is networks.star(F, 2), not the closed 6-port: consistency fails, and only it
    assert data["decisions"]["verdict"] == {"value": "fail", "fails": [CONSISTENCY]}
    assert data["evidence"]["B1"]["ok"] and [b["band_ghz"] for b in data["bands"]] == [list(b) for b in p0b2.BANDS_GHZ]
    assert (p0_out / "p0b2" / "p0b2.md").read_text(encoding="utf-8").startswith("## P0B2-runs")
    pj = p0b2.project(p0_out)
    d = load_project(pj)
    for edited, refusal in (  # measure's refusals
            ({**d, "results": {**d["results"], "run_dir": "elsewhere"}},
             "p0b2: p0b2-B1: the project holds another run, or B1 ran again since; run the harness again"),
            ({**d, "verify": {**d["verify"], "compare": {**d["verify"]["compare"], "ds_max": 1.0}}},
             "p0b2: the harness's chain does not reproduce verify's stored comparison (ds_max "),
            ({**d, "mesh": {"n": 2, "reach_h": 3.0}}, f"p0b2: {pj} is not P0-B2's project (reach 6, t_max_s 80 ns)")):
        save_project(pj, edited)
        with pytest.raises(SystemExit) as e:
            p0b2.measure(p0_out)
        assert str(e.value).startswith(refusal)
```

  - In `tests/test_p0d.py`, `test_every_tool_enters_its_p0_folder_first` gains `("p0b2", ["run", "--out", "{p0}"], "p0")` and `("p0b2", ["report", "--out", "{p0}"], "p0")`.

- [ ] **Step 2: Run** `python -m pytest tests/test_p0b2.py tests/test_p0d.py -q`. Expected: the new tests FAIL with `AttributeError: module 'p0b2' has no attribute ...` (`project`, `decide`, `run`), and the two new tool cases with an argparse SystemExit.
- [ ] **Step 3: Implement.**
  - **`harness.made(out, pj, board, edits)`.** `harness.project`'s body, moved out unchanged: the project `pj`, made by `new` with NEW from the fixture `board` copied into `<out>/boards` when it is missing (RuntimeError on a non-zero exit), then `edits` through `p0.edit` on every call, saved only when they change it. `harness.project(out, run_id)` becomes `made(out, _path(out, run_id), *VARIANTS[run_id])`. `tables`' inner `table` and `rows` move to module level as `_table` and `_rows`, unchanged. `test_the_p0b_projects_are_fresh_projects_with_their_edits` and the fake-worker gate test cover both moves.
  - **`project(out)`.** `harness.made(out, out / "p0b2" / "lpf915" / "project.json", "lpf915", EDITS)`. Its run folders are therefore named "lpf915-…", never "B1-…". `p0d.STEPS["lpf915"]` stays `p0b-B1`.
  - **`run(out)`.** Enter the folder. Raise SystemExit with the spent text (the RF4 test's string), naming the path, once `out/steps/p0b2-B2.json` or `out/p0b2/p0b2.json` exists, B2's record first. Then `pj = project(out)`, followed by:
    - `b1 = p0.step(out, "p0b2-B1", p0.model_key(pj), partial(p0.cli_run, pj, "run"))`;
    - only when B1 stored its results (`b1["result"]["jobs"]` is not None): `p0.step(out, "p0b2-B2", f"{p0.model_key(pj)}|{b1['result']['run_dir']}", partial(p0.cli_run, pj, "verify"))`. A B1 that stored none (a job kept no S, or a refusal) is a measured outcome: B2 is not started, and `write` judges it;
    - `return write(out)`.
  - **`measure(out)`.** It reads `<out>/p0b2/lpf915/project.json` as it is, never through `project()`, which would restore EDITS, and the records of STEPS that exist, in one `p0.records` call (two codes refuse). It raises SystemExit in these cases, in this order:
    - `f"p0b2: {pj} is not P0-B2's project (reach 6, t_max_s 80 ns)"` when the project's `mesh.reach_h` or `t_max_s` differs from EDITS;
    - `f"p0b2: {', '.join(ids)}: the project holds another run, or B1 ran again since; run the harness again"` for each step whose record stored results (`jobs` not None) that the project no longer holds (`p0.holds` on `results` or `verify`), or B2 whose key lacks `f"|{b1_run}@"`;
    - `f"p0b2: the harness's chain does not reproduce verify's stored comparison (ds_max {a:.6g} against {b:.6g})"` when the project holds B2's run and `compare(p0.closed_chain(pj, key="verify")[1], p0.closed_chain(pj, ideal=True)[1], f, k0, FLOOR)["ds_max"]` differs from the stored one by more than 1e-12.

    Per run: "runs" is `p0.summary` of its record, or `{"exit": None, "jobs": []}` without one; "verdicts" its summary's job verdicts (the verdict events when it stored no results); "evidence" `harness.evidence` of a record that has a run folder, else `{"ok": False}`; "warnings" its summary's W_ codes. "consistency" is B2's stored `verify.compare` when the project holds B2's run, else None; `bands` and `at_mode` (the largest complex |ΔS| over the entries at the grid point nearest MODE_HZ) come from those two chains, else None.
  - **`decide(m)`.** It is pure. Its texts are pre-registered, so its body is given:

```python
def decide(m: dict) -> dict:
    """P0-B2's verdict (design 5.2, E-11) on measure's `m`: criterion 1 on the stored comparison (p0.criterion1, spec
    9.3's limits; no comparison fails it), every B1 and B2 job converged, D-40's evidence ok and both commands exited
    0 (a run without a record shows no jobs and no evidence). EMerge, B4 and the W_TAIL codes never decide it.
    RETUNE_VALIDATED waits for P0-C either way (A-4, D-15)."""
    c1 = p0.criterion1(m["consistency"]) if m["consistency"] else None
    fails = [] if c1 and c1["pass"] else ["consistency: the co-simulation against verify fails criterion 1 (spec 9.3)"]
    for run, n in JOBS.items():
        if (ended := m["verdicts"][run]) != ["converged"] * n:
            fails.append(f"{run}: its jobs ended {', '.join(ended) or 'nothing'}, not every one converged (spec 9.3)")
        if not m["evidence"][run]["ok"]:
            fails.append(f"{run}: D-40's live evidence is not ok")
        if (code := m["runs"][run]["exit"]) not in (0, None):  # None: the run has no record
            fails.append(f"{run}: the command exited {code}")
    return {"consistency": c1, "verdict": {"value": "fail" if fails else "pass", "fails": fails},
            "p0c": "'do not start' stays (controller recommendation, owner unavailable)" if fails
            else "ready: withdraw 'do not start' (controller recommendation, owner unavailable)",
            "retune_validated": False}
```

  - **`tables(result)`.** `harness._table`, cells formatted by `harness._cell`, under these headings in order:
    - `## P0B2-runs`: run, exit, cells, dt_ratio, wall_s, predicted_s, warnings;
    - `## P0B2-jobs`: run, port, verdict, t_cut, t_stop, residual_db, event, abort, order;
    - `## P0B2-evidence`: run, cut_delta, trunc_2ns, ok;
    - `## P0B2-consistency`: `harness._rows` of `p0.LIMITS1`'s three terms, the limit row, then the measured row when there is a comparison;
    - `## P0B2-bands`: band_ghz, ds_max, f_hz, entry, then the at_mode row (f_hz, ds); empty without a comparison;
    - `## Decisions`: decision, result.
  - **`write(out)`.** `measure`, `decide` and `tables`, written as `<out>/p0b2/p0b2.json` through `p0.save` and `p0b2.md` beside it. "machine" is `p0.machine` of the records that exist. It returns the JSON as saved.
  - **`main`.** `run --out DIR` calls `run` and prints the verdict. `report --out DIR` enters the folder, calls `write` and starts no run. Both return 0. The module docstring gains P0-B2 itself (E-11) and `| run --out DIR | report --out DIR`.
- [ ] **Step 4: Run** the two files, then `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit.** `git add tools/p0b2.py tools/p0b/harness.py tests/test_p0b2.py tests/test_p0d.py`, then `git commit -m "feat(tools): p0b2's run, measure and decide, P0-B2's pre-registered gate (design 5.2, E-11)"`, then `graphify update .`.

### Task 13 [run]: P0-B2

- **Before:**
  - Task 12 is committed and `git status --porcelain` is empty.
  - Task 11's pre-registration commit is in.
  - Now plus 12.2 h falls before 2026-11-19; otherwise P0-B2 is not run and not spent, and the report says why.
  - The idle check prints `[0, 0, 0]`.
  - There is room for the run folders: `.venv\Scripts\python.exe -c "import shutil,sys; print(shutil.disk_usage(sys.argv[1]).free // 2**30)" <P0-2>` prints 10 or more.
- **Command:** `.venv\Scripts\python.exe tools\p0b2.py run --out <P0-2>`
- **Expected machine time:** about 8.8–9.3 h, worst 12.2 h (Task 11's pre-registration).
- **Expected results:** Task 11's pre-registration, as committed.
- **Outputs:** in `<P0-2>`: `p0b2\lpf915\` (the project and its `results\`), `steps\p0b2-B1.json` and `steps\p0b2-B2.json` with their run folders, `p0b2\p0b2.json` and `p0b2\p0b2.md`.
- **Done when:** the command exits 0, and `.venv\Scripts\python.exe -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print(d['decisions']['verdict'], d['consistency'], d['verdicts'], d['warnings'], d['machine'])" <P0-2>\p0b2\p0b2.json` prints them.
  - A step that raises leaves no record. Fix it test-first under the fix rule, before B2's record exists, and rerun the same command. A fix under `src/` reruns B1, and Task 11's `predict` runs again first: a `go` that turned false stops P0-B2, not spent.
  - Once B2's record or `p0b2.json` exists, P0-B2 is spent: only `report --out <P0-2>` may follow.

## Phase 4 — references and reports

### Task 14 [code]: P0-D's references with tails (only when Task 4 adopted A-9)

**Files:**
- Modify: `tests/fixtures/p0d/*.npz`, `tests/test_p0d_refs.py`

**Interfaces:**
- Consumes: `p0d.references` with `--only` (plan 6's Task 4), reading `<P0-2>`'s P0-A n = 2 steps, `p0a-pad` and `p0b-B1`; the branch plan 6's Task 10 took (Before Task 1, item 2).
- Produces: references whose S is the Draft replay with tails (E-5). The traces are raw records and stay byte-identical.

Plan 6's lpf915 branch (its B1 ran, but not six converged, so lpf915's traces and reference stayed Stage 1's): `lpf915.npz` keeps its f, t_cut and spec_hash, and only its S is replayed with tails from the committed traces (Step 3); its hash test keeps plan 6's xfail.

- [ ] **Step 1:** Print each committed reference's `spec_hash` (first 8 hex) and `t_cut` for the report: `.venv\Scripts\python.exe -c "import sys,numpy as np; sys.path.insert(0,'tools'); import p0d; [print(m, str(np.load(f'tests/fixtures/p0d/{m}.npz')['spec_hash'])[:8], np.load(f'tests/fixtures/p0d/{m}.npz')['t_cut']) for m in p0d.MODELS]"`.
- [ ] **Step 2:** In `test_the_draft_replay_of_the_committed_traces_reproduces_the_references`, remove the `TAIL_MIN_SAMPLES` pin and its `monkeypatch` parameter. Run `python -m pytest tests/test_p0d_refs.py -q`. Expected (a prediction): FAIL for lpf915 only. The pad's two Draft jobs fall back, under 48 samples after 2·t0, while one lpf915 job clears it (6.25 ns in Stage 1's Draft table); Step 1's printout confirms it by t_cut − 2·t0 ≥ 48 probe steps.
- [ ] **Step 3:** Run `python tools/p0d.py references --p0 <P0-2> --out tests/fixtures/p0d`. In plan 6's lpf915 branch, add `--only coupon_ms,coupon_ms_masked,coupon_gcpw,coupon_gcpw_masked,coupon_dense,coupon_gcpw_45,coupon_gcpw_arc,coupon_gcpw_pads`, then replay lpf915's S from its committed traces: `.venv\Scripts\python.exe -c "import io,sys,numpy as np; sys.path.insert(0,'tools'); import p0; from pathlib import Path; p=Path('tests/fixtures/p0d/lpf915.npz'); z=dict(np.load(io.BytesIO(p.read_bytes()))); s,c=p0.s_of([p0.load_trace(t) for t in sorted(Path('tests/fixtures/traces').glob('lpf915-k*.npz'))], z['f'], 'draft'); assert np.array_equal(c, z['t_cut']); np.savez_compressed(p, **{**z, 'S': s})"`.
- [ ] **Step 4:** `git add tests/fixtures/p0d tests/test_p0d_refs.py`, then `python tools/privacy_gate.py --staged`. Expected: no hit.
- [ ] **Step 5:** Run `python -m pytest tests/test_p0d_refs.py tests/test_p0d.py tests/test_traces_real.py -q`, then the full suite. Expected: all pass; in plan 6's lpf915 branch, `test_the_references_are_the_models_p0d_builds_here` keeps its lpf915 xfail. Any other hash that differs means a plan-7 commit moved a model after its record: its reference stays as regenerated, that test takes `@pytest.mark.xfail(strict=True, reason=...)` naming it, and the report states it as a limit. Never loosen a bound.
- [ ] **Step 6: Commit.** `git commit -m "test: P0-D's references regenerated with tails from the fresh P0 folder (A-9, E-5)"`.
- [ ] **Step 7: Return** each reference's `spec_hash` prefix and `t_cut`, old → new, which references changed, and which branch ran.

### Task 15 [decide]: The plan-7 report and the exit addendum

**Reads:**
- `<P0-2>\p0b\a9.json`, `<P0-2>\p0b2\a10.json` and `<P0-2>\p0b2\predict.json`, where they exist, and the `a10-*` and `p0b2-*` step records for the machine time;
- on go, `<P0-2>\p0b2\p0b2.json` and `p0b2.md`;
- the texts returned by Tasks 4, 8, 10 and 14;
- the research's development-data results: p7-tails' checks 1–2, p7-box's A-11 check and p7-gate's prediction table.

`<date>` is the day this task runs.

- [ ] **Step 1:** The controller writes the JSON: `.venv\Scripts\python.exe -c "import json,sys; from pathlib import Path; sys.path.insert(0,'tools'); import p0; d=Path(sys.argv[1]); rd=lambda p: json.loads(p.read_text(encoding='utf-8')) if p.is_file() else None; steps=[rd(p) for p in sorted((d/'steps').glob('*.json')) if p.stem.startswith(('a10-','p0b2-'))]; print(json.dumps({'a9': rd(d/'p0b'/'a9.json'), 'a10': rd(d/'p0b2'/'a10.json'), 'predict': rd(d/'p0b2'/'predict.json'), 'p0b2': rd(d/'p0b2'/'p0b2.json'), 'machine': p0.machine(steps)}, indent=1, ensure_ascii=False))" <P0-2> > docs\validation\<date>-p0-b2.json`.
- [ ] **Step 2: Return the report text** (`<date>-p0-b2.md`, seven sections):
  1. **Verdict.**
     - On go: P0-B2's `decisions.verdict` with its fails, and P0-C's line.
     - On no-go: "P0-B2 was not spent", with the first unmet go condition and its value (A-9's judges, A-10's coupon, the prediction, or its reproduction check).
     - Always: A-9's, A-10's, A-11's and E-9's outcomes; that A-9 was adopted on E1–E5 after E-2 made the design's two development checks report-only (0.0021 against 0.002 on one); RETUNE_VALIDATED False; the §7.6 label stays.
  2. **Inputs:** the commits and code ids (each JSON's `versions`); the folders by name only; Normal; the development and independent data as Global Constraints defines them, and plan 6's branch for lpf915's traces; the frozen v3b constants; the coupon's board.
  3. **Measured value against limit.** Each row is pre-registered against measured:
     - E1–E5 against 0.002 and the predictions, a void judge named;
     - the coupon against [0.0870, 0.1616] nH and 0.02 dB, against its predicted values and effective window, and its report-only values;
     - A-11's registered range, A-9's known difference (E1, development 0.0021), and A-10's +0.062 ± 0.005 dB against predict's tails → tails_dl ΔS21(f0) shift, report only;
     - E-9's questions, with every estimate formed;
     - predict's rows, uncorrected / tails / tails_dl (and A-12's row, if any), with the bands, and p7-gate's ×0.7 / ×1.3 row (0.0317 / 0.0318). The development checks that E-2 reports and does not gate: 0.0021 / 0.0001 / 0.0001 against 0.002, and 0.0316 against 0.035;
     - on go, P0-B2's criterion 1, convergence, evidence, warnings, cells, cut times and B2's P2 time, each against Task 11's expectation.
  4. **Decisions,** each marked: E-1..E-12 as applied; Tasks 4 and 8's branches; Task 10's; the go/no-go; P0-C's recommendation.
  5. **Stated limits and deviations:**
     - EMerge not run (a deviation from §9.3, E-11);
     - B4 dropped (A-5);
     - A-11's known difference;
     - the residual near f2, unless A-12 was adopted; it comes from p7-gate when Task 10 did not run, a deviation from E-9's unconditional task;
     - §5.2's two development checks reported instead of judged (E-2), after the first frozen method failed them; v3b, revised on that data, judged by E1–E5 on new data (§5.2, A miss);
     - Task 10's rules beyond E-9's text: no box-term redesign and no inductor change (E-8, §5.2, A-10's coupon);
     - E4's domain (the pad's cut less 2 ns precedes the pulse's end);
     - W_TAIL_FALLBACK's wording beyond E-3;
     - the Draft replay pinned plain from Task 1 to Task 14 instead of a strict xfail (E-5);
     - v3b's undamped-pole corner;
     - Draft cuts near 4 ns (42–45 probe samples after 2·t0), which leave most Draft jobs on their plain DFT;
     - the coupon's as-saved pour, outside the pad gap;
     - lpf915's reference in plan 6's lpf915 branch, Stage 1's model with its S replayed with tails;
     - every fix commit made between runs.
  6. **Machine time:** Task 3 in seconds; Task 7's steps' `wall_s` against 45–60 min; Task 13 against 8.8–9.3 h, loaded steps left out; the JSON's `machine` and the elapsed days from 2026-10-22.
  7. **Next step:** P0-C on the owner's board when P0-B2 passed (still the owner's step), otherwise "do not start" stays; then Stage 2.
- [ ] **Step 3: Return the addendum** for `docs/validation/2026-10-25-stage1-exit.md`, as "## Addendum, `<date>`: plan 7". It gives A-9, A-10 and A-11, E-9, P0-B2 (passed, failed or not spent, with criterion 1's numbers), P0-C's status, RETUNE_VALIDATED False and the regenerated references. When the ceiling applied a branch, it names that branch and its data.

The controller saves both, runs the privacy gate, commits them, then reviews the whole branch, decides and merges (design §5.2).

---

## Not in this plan

- **A-11 in code** (E-8). Its estimator failed the pre-registered rule (0.0253 > 0.025, and ΔS21(f0) worse). It stays a registered known difference; the scratch estimator is archived in `<R7>`. Nor a re-estimate of the box term, its pour, lid or box-end currents included: that needs new data, such as r3's X-A run (design §5.2, A miss).
- **Any change to v3b,** or a second tail method (E-1, design §5.2). A redesign needs a new pre-registration and new data.
- **Widening A-10's coupon band** toward the on-mesh PEEC's 0.0865 nH (E-7).
- **EMerge for P0-B2** (E-11: not blocking, the owner's option) and **B4** (A-5).
- **P0-C,** which is the owner's step, and **flipping RETUNE_VALIDATED**, which waits for P0-C (A-4, D-15).
- **A second P0-B2:** the ceiling is one run.
- **Design non-goals (§3):** GUI work; any limit move (D-22); narrowing E_STAIRCASED's successor W_STAIRCASED; a step-edge role for lpf915 at n 3.
- **A permanent tier (a) test of E1–E4.** The judges run once on `<P0-2>`; E5's replay test stays in the suite.
- **The traces.** They are raw records and do not change with tails. P0-C's replays (`tools/p0c.py`) take tails through `s_of` with no change.
- **P0-A's rows and decisions.** p0a reduces its coupons' probes with its own DFT (`line_constants`), never `s_matrix`, `s_of` or `layout`, and P0-A is not rerun, so they stand (p7-gate F6). A later P0-A rerun on this code would count a W_TAIL line among the pad's W_ codes, which D-28 reads.
- **The ×0.7 and ×1.3 rows in `predict`:** E-10 uses the central ΔL only, and the report quotes p7-gate's.
- **Stage 1 evidence,** kept as it is: `<P0>`, P0-B's records and reports.

## Controller rulings (2026-10-27; binding)

The architect's and the reviser's rulings. Each is a controller recommendation, owner unavailable.

- Ruling: the tasks follow each fix with its own check and decision (A-9: Tasks 1–4; A-10: Tasks 5–8), not the suggested order of all code first — a fix that misses then reverts its own phase's commits, its run's fix commits included, with nothing else on top — cost if wrong: none; independent CPU work is reordered.
- Ruling: A-9's judges E1–E4 are `harness.a9` in P0-B's harness, which already holds D-40's truncation evidence, and they read `<P0-2>`'s `p0b-B1` and `p0a-pad` records and projects directly, never the committed traces — those traces are written from these very records (plan 6's Task 10), and reading the records keeps the judges valid in plan 6's lpf915 branch — cost if wrong: about 40 lines in harness.py.
- Ruling: E1 takes the longest B1 job's own one-trace column, cut at each of 13.21, 16 and 20 ns below its end, against that column at its end — "its own column" in p7-tails' E1 is the single-excitation column, which no other job mixes into — cost if wrong: E1 measures a column rather than the 6-port.
- Ruling: E4 judges only the jobs whose end less 2 ns leaves a full 6 ns window after 2·t0, which keeps B1's six and drops the pad's two; this deviates from p7-tails' "each committed trace" — the pad converges at 4.22 ns, so its 2 ns-earlier cut falls before the pulse ends at 2.236 ns, where no tail method applies; computed from P0-A's published t_cut, not from any fit — cost if wrong: E4 is judged on B1 alone.
- Ruling: E1 with no cut before the longest job's end, and E4 with no job in its domain, read None (void) and fail `pass` — a judge with no data must never pass by default, as a void coupon fails A-10 — cost if wrong: A-9 not adopted as is if B1's longest job ends at or before 13.21 ns.
- Ruling: E3 judges every job of both records, the pad's two included, although their window holds exactly the 48-sample floor — a clean, fast record that falls back would print W_TAIL_FALLBACK on every single-trace run, a defect the judge exists to see — cost if wrong: A-9 not adopted on a borderline window whose tail would be negligible.
- Ruling: E5 is the existing test_traces_real replay, recorded from Task 2's green suite (9 passed) at its commit, and Task 3 runs only `--a9` — the stop rule is untouched, every suite run replays the traces, and a [run] task is one command — cost if wrong: none.
- Ruling: the fix rule runs from Task 3's start. A traceback in `--a9` before a9.json exists allows one test-first plumbing fix and one rerun; a SystemExit (a record missing, a project holding another run) or a second failure takes Task 4's fail branch; `--a9` refuses once a9.json exists; Before Task 1 checks that each project holds its step's run — A-9's one judgement needs a pre-registered outcome for every failure, and must run once — cost if wrong: A-9 not adopted over a data fault that Before Task 1 should have caught.
- Ruling: the fix rule's frozen list holds every function and constant a rule reads (p0b2's coupon, `a10`, `fit_dl`, `FLOOR`, `predict`, `bands`, P0-B2's NEW, EDITS, STEPS, JOBS, `project`, `measure`'s rules and `decide`; `harness.evidence`, `p0.summary`, `p0.criterion1`, `LIMITS1`); once a step's records exist a fix changes plumbing only; a src/ fix after Task 11 reruns `predict` before B1 reruns — a tools/ fix keeps p0.code_id(), so the FDTD records would stand while a judged value moved — cost if wrong: a genuine defect in a frozen function ends the gate as it stands.
- Ruling: the Draft-replay test is pinned plain by monkeypatching `waves.TAIL_MIN_SAMPLES` to 10**9 in that test from Task 1 to Task 14, instead of strict-xfailed, a deviation from E-5 — P0-D's published Draft cuts are 3.974–4.098 ns for every job but one lpf915 job (6.251 ns), which leaves 42–45 probe samples after 2·t0, under the 48 floor, so the pad's replay keeps its plain DFT on both jobs and would XPASS a strict mark, while lpf915's fails only through that one job — cost if wrong: none; Task 14 removes the pin.
- Ruling: `s_of` takes no `tails` keyword: every record takes its tail, and the two tests that need the plain DFT monkeypatch `TAIL_MIN_SAMPLES` — after Task 14 no caller would pass False — cost if wrong: a later plain replay monkeypatches the same way.
- Ruling: `s_matrix` and `s_of` let a record shorter than TAIL_MIN_SAMPLES fall back without calling `tail`, which stays verbatim — a one-sample record (a T_max under one probe step) passes the plain reduction and would make `tail`'s `t[1]` raise; every other outcome is what `tail` itself returns — cost if wrong: none.
- Ruling: W_TAIL_FALLBACK's text adds the short-record reason and a next step, the strict preset and `run` again (`verify` again for verify's own jobs), a deviation from E-3's wording — Draft cuts make the short case the common one, plan 5's Global Constraints ask every product string to say what to do next, and retune only re-reads the stored records — cost if wrong: a wording change.
- Ruling: W_TAIL_LARGE keeps E-3's text and metric (complex |ΔS| on the chain) and prints ds to 4 decimals, as I_VERIFY_COMPARE prints ds_max; it fires only above 0.02 — cost if wrong: none.
- Ruling: verify's W_TAIL_LARGE judges the larger of verify's own S and the run's closed chain (p7-tails), so on lpf915 B2 is expected to print it, from the closed co-simulation's 0.0803 on the development data. That corrects p7-gate F3's "B2 should not print it" — cost if wrong: one expected value.
- Ruling: verify prints W_TAIL_FALLBACK for its own jobs only — `run` and every `retune` print the run's — cost if wrong: a verify user sees the run's fallbacks only in run's and retune's output.
- Ruling: `layout` reads model.json's excitation before `s_matrix`, with no branch for a model.json without one. test_post_waves' `fake_run` writes the synthetic pulse's t0, and the reversed-curve test compares against `s_matrix` with tails — the product's model.json has held the excitation since 2026-10-21 — cost if wrong: two test edits.
- Ruling: `layout` computes `s_dft` with a second, plain `s_matrix` call made first, so E_S_SINGULAR refuses exactly as today, under a ponytail note — the simplest form; the DFT costs milliseconds — cost if wrong: a few ms per reduction.
- Ruling: v3b, frozen, leaves a numerically undamped pole (|z| ≥ 1 without growing by 1 % over the window) out of the tail instead of refusing; a ponytail comment names it, and the tests use a 200 ns mode, not an undamped cosine, whose outcome depends on rounding — E-1 freezes the method, and the stop rule's flat verdict flags such jobs — cost if wrong: a flat job's tail may miss its undamped part.
- Ruling: the tails add about 0.3 s to each lpf915 run or retune output and about 0.1 s to verify (p7-tails' timing), with no cache, under a ponytail note — retune already recomputes S from the waves every time, and §7.2's instant retune absorbs it — cost if wrong: a slower retune on a large project.
- Ruling: Task 1 is four test-first cycles (tail; s_matrix and layout; the warnings; s_of) in one task and one commit, not four tasks — each red is seen for its own reason, and Task 4's revert stays two task commits — cost if wrong: none.
- Ruling: no re-pin is expected in Task 1, and any failure but the named code-list additions stops the task — the reviser's replay shows every S-valued assert and exact code list on the network fake or whole star records, which the tails move by at most 6e-9 with no fallback — cost if wrong: a stop that a longer list would have avoided.
- Ruling: `strip_dl(port, lines)` takes the port box and the mesh lines, so verify_spec, the coupon and predict compute ΔL one way; its tests are VSPEC's box (0.482342 nH), a cell as wide as its box (0), the coupon (0.124283 nH) and lpf915 through test_verify (14.875188 nH) — DRY — cost if wrong: none.
- Ruling: Task 5 adds the compensation before the sweep's `compensate=False`, so the fake-worker gate test is seen failing with E_VERIFY_STRIPS from the sweep first — Review Focus 3's red — cost if wrong: none.
- Ruling: the coupon and predict live in a new `tools/p0b2.py` (Tasks 6 and 9), while P0-B2's `run`, `measure`, `decide`, `tables` and `write` are built only on go (Task 12, after Task 11's commit, before the run); its docstring and the every-tool test name only the subcommands that exist — on today's data the prediction is a no-go (0.0318), so building them first would leave about 150 lines of dead tool code — cost if wrong: Task 12 sits between the go decision and the run.
- Ruling: A-10's rule is the pure `p0b2.a10(verdicts, dl_h, ds21_db)`, given here and tested on its edges: void unless all seven jobs converged (the co-simulation's three and both verify runs' two each), a void check is not a pass, and a step that stores no results skips what follows and reads void, never a loop — stricter than E-7's "every job of both runs", never looser, and coded like decide so a fix commit cannot move it — cost if wrong: a slow coupon job costs A-10.
- Ruling: the coupon's uncompensated run retunes L1 to 6.8 nH plus its closed-form ΔL printed to 6 decimals (6.924283 nH), so the grid holds 6.8 nH within 3e-16 H, on A-10's code and one code id (E-7's retune route) — cost if wrong: none.
- Ruling: Task 7 registers the coupon's judged values before it runs: ΔL about 0.124–0.133 nH, ds21_comp ≈ 0.6547 × |ΔL_true − 0.124283| dB, an effective pass window of about [0.094, 0.155] nH, and the PEEC-like 0.0865 nH predicted to fail both parts — OQ1's practice — cost if wrong: none.
- Ruling: reuse over copies — `harness.made` holds `harness.project`'s body for p0b2.project, `harness._table` and `_rows` serve p0b2.tables, `p0.holds` checks a held run in coupon and measure, the coupon's ds21_uncomp reads `p0.closed_chain(pj, ideal=True)`, and p0b2 uses `harness.NEW` directly; the coupon keeps its own project lines (its board is generated text) and harness.measure keeps its own line — the shortest diff that leaves P0-B's gate code alone — cost if wrong: none.
- Ruling: predict returns "stored", "uncorrected", "tails" and "tails_dl" (and, by amendment only, A-12's row). Its test checks "tails" against a fake run's stored comparison within 1e-12, since plan 7's verify computed that one with tails. Task 11 checks "uncorrected" against P0-B's stored comparison within 1e-9 before it trusts the prediction, and a miss or a refusal is a no-go — Stage 1's code computed that comparison, a library's last bits must not stop the go/no-go, and an untrusted prediction must not spend the run — cost if wrong: a reduction error under 1e-9 goes unseen, far below criterion 1's resolution.
- Ruling: predict emulates A-10 on the co-simulation's side by adding jω·ΔL (central: 0.1262 nH, the closed form on the development models) to each inductor's ideal Z_part, r2's first-order equivalent, under a ponytail note; the ×0.7 and ×1.3 rows are not recomputed, and the report quotes p7-gate's 0.0317 and 0.0318 — E-10: central ΔL only — cost if wrong: none.
- Ruling: predict reads the run folders by the absolute paths project.json holds, with no remap, and refuses by DEV's hashes, results first, before it reads verify — the frozen folder never moved, and plan 6's B1 has no verify — cost if wrong: none.
- Ruling: Task 10 (E-9) runs only when A-9 and A-10 were both adopted, a deviation from E-9's unconditional task stated in the report (otherwise the residual is p7-gate's). It reads only `<P0>`, read-only, runs CPU scripts outside the repo and ends by 2026-11-12. An attribution needs an estimate frozen before its check, with no input fitted to or scanned on P0-B's records, and A-11's rule: max |ΔS| up to f2 ≤ 0.025 with no worse |ΔS21(f0)| or |ΔS11(f0)| than predict's baseline — the design and E-9; with no go/no-go to feed, the task would only report — cost if wrong: one bounded task.
- Ruling: A-12 may not be the box term again (no series term in a part's branch from the port box against verify's construction, no refinement of A-11's estimate, its pour, lid or box-end currents included) nor touch an inductor's branch or verify's L cell and strips; Step 1 may not read p7-gate's F2 and scan.py, r3's fits or the committed fixtures, may not apply a candidate to the comparison, and returns every estimate formed, at most one frozen per question — E-8 and §5.2's "A miss" bar re-estimating a missed fix on the same data, and the go/no-go must not rest on a correction chosen by its effect on the comparison — cost if wrong: a genuine new cause waits for new data.
- Ruling: an attributed cause becomes A-12 only through a plan amendment, committed before its code and its one check, that holds a full [code] task (Files, Interfaces, a failing test on fakes, the commit), its own predict row `tails_dl_a12` that `go` then reads while uncorrected, tails and tails_dl stay free of it, the behaviour of a project made before A-12, and its spec text; a miss, or no check by 2026-11-12, reverts its code and registers it like A-11 — the design's pre-registration; no interface is pre-specified for a fix the research does not support — cost if wrong: one amendment.
- Ruling: P0-B2's pre-registration registers A-9's known difference (E1; development 0.0021 at 13.21 ns) and A-10's +0.062 ± 0.005 dB, the design's +0.059 ± 0.005 recomputed on plan 6's mesh, reported against predict's tails → tails_dl shift — "every fixed item registers its expected known difference" (design §5.2) — cost if wrong: none.
- Ruling: a P0-B2 B1 that stores no results (a job kept no S, or a refusal) is a measured outcome: `run` does not start B2, `write` judges what exists (verdicts from the verdict events, evidence not ok, no comparison failing criterion 1, an exit of None skipped), and P0-B2 is spent once B2's record or p0b2.json exists; a step that raises still leaves no record and resumes — the one run must never end without a verdict, and decide's exit and convergence texts must be reachable — cost if wrong: an environment refusal spends the run.
- Ruling: B4's drop rests on A-5 alone — plan 6's D-27 advice branch turned E_STAIRCASED into W_STAIRCASED, so the design's second reason, "E_STAIRCASED refuses lpf915-45", is stale — cost if wrong: none.
- Ruling: EMerge's absence from P0-B2 is a deviation from §9.3 recorded in the report, with no amendment (E-11) — cost if wrong: none.
- Ruling: P0-D's references are regenerated in Task 14 from `<P0-2>`'s records, only when A-9 was adopted, and the traces stay byte-identical; in plan 6's lpf915 branch, lpf915.npz keeps its f, t_cut and spec_hash and only its S is replayed with tails from the committed traces. A reference whose Draft jobs all fall back regenerates to the same bytes — tails change only the replayed S, and numpy writes npz members at a fixed timestamp — cost if wrong: none.
- Ruling: one plan-7 report, `<date>-p0-b2.md`, with one JSON assembled from a9.json, a10.json, predict.json and p0b2.json, plus the machine time of every a10- and p0b2- step and the elapsed days, and the exit addendum — D-51/D-52 ask for one report with its JSON per gate, the pre-gate checks are P0-B2's inputs, and every report records its machine time even on a no-go — cost if wrong: one report instead of three.
- Ruling: `harness.a9`, `p0b2.coupon` and predict's CLI add `p0.versions()` to what they save or print, and the functions themselves return none — the report's inputs need the code ids, and the tests compare the functions' dicts — cost if wrong: none.
- Ruling: the report states that E-2 made the design's two development checks report-only after the first frozen method failed them, and A-9's spec line says so (0.0021 against 0.002) — otherwise the record reads as a moved expectation — cost if wrong: none.
- Ruling: Before Task 1 checks `git diff --stat ea0ac09 HEAD -- src tools` — the research and every expected value ran on ea0ac09, before plan 6's merge — cost if wrong: none.
- Ruling: at the ceiling, unrun judges or an unfinished coupon take that fix's fail branch; an unfinished Task 10 is "not attributed", A-12's code reverted; P0-B2 starts only with 12.2 h to spare before the ceiling, and an unfinished P0-B2 is not judged, the label and "do not start" staying — the design's timebox — cost if wrong: a fix reverted for want of time.
- Ruling (disclosure): the architect ran the frozen v3b only on the repo's synthetic test records (tests/traces.py, tests/networks.py), to set the tests' exact values: 1.3731 at S11 998.8 MHz for a 6 ns ring cut at 15 ns, 0.0213 at 40 ns, 5.1e-4 for the default fake, and 43 and 47/48 samples at the short cuts. It read the published t_cut of P0-A's re-check (4.22 ns) and P0-D's Draft cut table. It never ran the method on `<P0>`, `<P0-2>` or the committed traces — cost if wrong: none.
- Ruling (disclosure): the reviser replayed the frozen v3b and stoprule.stop_rule only on the repo's synthetic records and the fake worker's kinds. Every pinned value above reproduced (also 1.1e-13 and 9.1e-14). The network fake cuts at 4.34 ns at Draft and 4.46–4.50 ns at Normal, 51–55 samples after 2·t0, and its tails move S by at most 1e-9; whole 10 ns star records by 5.4e-9; the converge fake by 2.1e-3 at Draft and 4.1e-4 at Normal; the tmax fake by 0.021–0.035. A one-sample record passes the plain reduction (κ 1.00006) and makes `tail` raise IndexError, and numpy 2.5.4 writes npz members at a fixed 1980 timestamp. Nothing ran on `<P0>`, `<P0-2>` or the committed traces — cost if wrong: none.
- Ruling (controller, on the reviser's first open issue): Task 10's narrowed constraints stand, and r3's X-A run (verify with C1 alone in the grid, about 3 h of FDTD) is not funded in plan 7 — re-estimating a missed fix needs new data under a new pre-registration (design §5.2, A miss), which belongs to a later plan; Task 15's next step names it as the owner's option — cost if wrong: P0-B2 most likely a no-go in plan 7 (0.0318 > 0.03), while A-9 and A-10 merge anyway (E-12).
- Ruling (controller, on the reviser's other open issues): the reviser's deviations list, the void E1 rule, A-10's known coupon risk under the unwidened band (E-7), a P0-B2 B1 that stores no results spending the run, and the fix rule's wider frozen list all stand as written; a later P0-A rerun's W_TAIL lines are that plan's concern ("Not in this plan") — every item was fixed before its data — cost if wrong: none beyond each ruling's own.
