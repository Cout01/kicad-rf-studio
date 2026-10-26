# Stage 1 · Plan 6 — Mesh-rule calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a GCPW slot edge a calibrated inside line, chosen by one pre-registered search over 48 candidates on plan 2's ratchet and confirmed in FDTD by P0-A's re-check, then amend spec §5.4 (A-8) and regenerate P0-D's references from a fresh P0 folder.

**Architecture:**
- **Product, test-first:** a slot-edge role in `core/mesh/rule.py`. It stays off (`SLOT_IN = None`) until Task 6 sets the winner. An axis guard keeps the as-built lines wherever the slot depth would fail the edge lint or the d/3 merge.
- **Dev tools:** `tools/meshcal.py` holds the 48-point grid, the five acceptance conditions in code and a run loop of p0 steps over one patched copy of `src`. Plan 2's ratchet harness (r1's `hrun.py` and the axes harness, pinned by sha256) and the archived boards stay outside the repo. In the old P0-B harness, B1–B5 are pinned to `p0a.PIN`, and p0d's `references` and `traces` gain `--only`.
- **Runs and decisions:** the search (2D only), then P0-A in full and B1 at reach 3 in `<P0-2>`. [decide] tasks apply the pre-registered rules and return each report as text.

**Tech Stack:** Python ≥ 3.11 (the dev venv runs 3.14); numpy, scipy and shapely; cs2d through `core.mesh.gates.fit2d`; the stdlib's `json`, `subprocess`, `shutil`, `hashlib`, `itertools` and `pathlib`; p0's steps, records and machine time. openEMS 0.37.0 and CSXCAD 0.7.0 are used for P0-A and B1 only. Tests run on pytest.

**Spec:** `docs/superpowers/specs/2026-10-26-engine-accuracy-design.md` §5.1 (binding), with §1–4 and §6. The engine authority is `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`:
- §5.4, amended by A-8;
- §5.5, the lint and the fit2d gate, unchanged;
- §9.2, P0-A;
- §12 L673.

The research is `.superpowers/sdd/stage2-plan1-research/`: r1 (the mesh), r4 (the rerun) and r5 (the spec frame). P0-A's pre-registered rules are D-25..D-30 in `.superpowers/sdd/plan5-research/controller-decisions.md`, as `tools/p0a.py` computes them.

**Branch:** `stage1-plan6`, from `main` (1f0fb3b). This plan is `docs/superpowers/plans/2026-10-26-stage1-plan6-mesh-calibration.md`. Phase 1 commands assume the dev venv is active. Every [run] command and every check names `.venv\Scripts\python.exe` and runs from the repo root. Placeholders:
- `<P0-2>` is `%LOCALAPPDATA%\kicad-rf-studio-p0-2`;
- `<R1>` is `.superpowers\sdd\stage2-plan1-research\r1-mesh\scripts` (git-ignored).

**Before Task 1 (the controller):**
1. Commit this plan on the branch, with the controller rulings returned with it appended as its last section, `## Controller rulings (2026-10-26; binding)`. The commit pre-registers the grid, the guard, the pinned evaluator, the acceptance code's contract and every branch below (design §4). Task 2's guard is part of the searched rule: a controller who strikes it removes Task 2 and every guard line before this commit, never after.
2. Copy r1's harness and frozen baseline from the session scratchpad (`s2r\meshcal\work\`):
   - into `<R1>\`: `hrun.py` and `all_r6.jsonl`;
   - into `<R1>\ax\`: `launch.py`, `axrun.py`, `common.py`, `axes.py`, `axes2.py`, `caxes.py`, `a_head.json`, `a_head_h2.json` and `a_head_h5.json`.

   `meshcal.PINNED` (Task 3) holds their sha256. `hrun.py`'s code, not its stale docstring, defines its arguments.
3. Extract the boards, with the archive's top folder stripped:
   `.venv\Scripts\python.exe -c "import zipfile,sys,pathlib; z=zipfile.ZipFile(sys.argv[1]); p='2026-10-20-stage1-plan2-geometry-and-mesh/'; d=pathlib.Path(sys.argv[2]); [((d/n[len(p):]).parent.mkdir(parents=True,exist_ok=True),(d/n[len(p):]).write_bytes(z.read(n))) for n in z.namelist() if n==p+'scratch-T10-r5/all.json' or n.startswith(p+'scratch-T10-r5/boards_') and n.endswith('.kicad_pcb')]" .superpowers\sdd\2026-10-20-stage1-plan2-geometry-and-mesh.zip <P0-2>\meshcal\boards`
   This writes `<P0-2>\meshcal\boards\scratch-T10-r5\all.json` and the 1061 boards in `boards_a\`, `boards_b\` and `boards_h\`, where `hrun.py` looks for them. `all.json`'s ten fixture rows are absolute paths into this checkout's `tests\fixtures`, read as they are; the file is never committed.

**Phases:** code (Tasks 1–4); the search (Task 5); then decide, run and code tasks in the order the results allow (Tasks 6–11). Three things end the plan early:
- no winner, or every passing candidate struck by a product gate test: Task 6's none branch, then Task 11;
- P0-A fails under the winner: Task 8's fail branch, then Task 11;
- the timebox's ceiling: the branch Global Constraints name for that point.

## Global Constraints

Plan 5's Global Constraints carry over whole (design §4); the lines below restate the ones this plan touches.

- **Python and files:** Python ≥ 3.11 (the CI floor). Every new source file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`. Everything is in English. Dev tools print plain English; the product prints only CATALOG codes.
- **Dependencies:** the app's runtime dependencies do not change. `tools/meshcal.py` uses the stdlib and `p0` only.
- **Imports:**
  - The package never imports `tools/`.
  - Tools import product code by module.
  - pytest has `pythonpath = ["tools"]`.
  - `tools/p0b/harness.py` puts `tools/` on `sys.path` first.
- **Messages:** every new product string is a code in the one CATALOG of `core.messages`, with plain `{fields}` and pre-formatted numbers, and says what to do next. `render` is `str.format`, so a literal brace is written `{{` or `}}`. Tests check `KrsError.code` and `.params` or the rendered line, never `match=`.
- **Units and frames:**
  - Units are mm, Hz, s and Ω.
  - `project.json` uses KiCad's frame (y down). Mesh lines, edges and harness points use the internal frame (y up).
  - The candidates' depths and gates are multiples of the edge cell d.
- **Execution model (D-5..D-10):**
  - [code] tasks are test-first.
  - Each [run] task is one background command, started by the controller and never by a subagent. Runs go one at a time, on an otherwise idle PC: no pytest, openEMS, EMerge or other run alongside. The idle check is `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'tools'); import p0; print([sum(m in c for c in p0.command_lines()) for m in p0.MARKERS])"`, which must print `[0, 0, 0]`. Before Tasks 7 and 9, the same command with `('meshcal.py', 'hrun.py', 'launch.py')` in place of `p0.MARKERS` must print `[0, 0, 0]` too: the search's processes are not among p0's markers.
  - From Task 5's start to Task 9's end, `src/` and `tools/` change only by a test-first commit, made between runs, that fixes a command which exited non-zero, and only before that run's `meshcal.json` or `p0a.json` exists (plan 5's rule). Such a commit never changes the slot branch or the `SLOT_*` constants; `meshcal`'s `CANDIDATES`, `PINNED`, `ok`, `passes`, `axis_regressions`, `accept` or `choose`; or `p0a.decide`, `LIMITS` or `rows`' pass rule. It touches the guard only after the shakedown stopped the search, before any candidate step. The reports name every such commit. Nothing is committed while a run is in progress.
  - P0 steps and the search's evaluations are resumable, keyed by model hash (or candidate id) plus `p0.code_id()`, and a gate refuses records from two codes.
  - The gates drive the product as subprocesses. P0-A runs at Normal, and P0-D's references are its records replayed at Draft (D-10, D-48).
  - [decide] tasks apply the pre-registered rules exactly.
- **The fresh P0 folder:** every command gets `<P0-2>` explicitly (`--out`, `--p0`). The search works in `<P0-2>\meshcal`. Stage 1's `%LOCALAPPDATA%\kicad-rf-studio-p0` stays frozen: no command in this plan reads or writes it.
- **Pre-registration (OQ1's practice):** these are committed before the run that judges them:
  - the 48-point grid, the five acceptance conditions (Task 3's code and tests), Task 2's guard, the shakedown and the pinned evaluator (`meshcal.PINNED`);
  - P0-A's D-25..D-30 (`tools/p0a.py` as committed);
  - the strike rule of Task 6, every branch of Tasks 6, 8, 9 and 10, and the ceiling's branches.

  No limit, tolerance, rule or expected result moves after its data is seen. There is one search and no second round.
- **D-22:** no other product number changes until a pre-registered rule says so. That covers:
  - fit2d 3 %, the dt floor 0.8, REACH_H 6.0, K_MAX 0.45, T_MAX_S 40 ns, GROWTH_DB 20 and the stop presets;
  - in the rule: the inside depth of every edge outside the slot role's scope (d/4, or d/8 + GRID_TOL where the rule as built puts it), OUT 3d/4, dz0, n, FACE, THIN, SERVE, CUT_SERVE and ALONE.
- **Timebox (D-4, Rec):** counted from 2026-10-22. The target is 2026-11-05 to 2026-11-12 and the ceiling is 2026-11-19. Every [run] task checks the date first. At the ceiling all P0 runs stop; [decide] and [code] tasks on runs that finished still follow. The code state is pre-registered:
  - the search has not finished: Task 6's none branch;
  - P0-A has not finished under a committed winner: Task 8's fail-branch revert, and the addendum says FDTD did not re-check the rule by the ceiling;
  - B1 has not finished after a P0-A pass: B1 is not run, and Task 10 takes its lpf915 branch.

  Task 11 then returns an addendum to `docs/validation/2026-10-25-stage1-exit.md` with the data. Every report and its JSON record elapsed days and machine hours.
- **Reports (D-51, D-52):**
  - Files: `docs/validation/YYYY-MM-DD-mesh-calibration.md` and `YYYY-MM-DD-p0-a.md`, each with a `.json` beside it (`meshcal.json` and `p0a.json` as the tools write them). The tools also render their tables, `meshcal.md` and `p0a.md`, which the reports copy.
  - English, one page where possible, with seven sections in order: 1. verdict; 2. inputs; 3. measured value against limit, pass or fail; 4. decisions, each marked; 5. stated limits and deviations; 6. machine time, predicted against measured; 7. next step.
  - Accuracy is given as |Δ| in % or pp, never as dB at a null.
  - A [decide] subagent returns each report as text. The controller saves it, runs `.venv\Scripts\python.exe tools\privacy_gate.py --staged` and commits it. The P0-A report is dated the day Task 8 runs, and the controller saves it that day, so the `GATES` comment cites a file that exists. Subagents never write report files.
- **Privacy:**
  - Use only the synthetic fixtures and the plan-2 archive's synthetic boards.
  - Never open the owner's boards, KiCad profile or settings, network shares, KiCad recent-file lists or the private research archive.
  - Never print the file `KRS_PRIVATE_LIST` names, nor its path.
  - Committed text, JSON and fixtures hold no absolute path, e-mail address, private name or drive letter followed by a colon and a slash.
  - `meshcal.json` holds ids, family and case names, booleans, numbers and `p0.versions()` only.
- **Recommendations:** every commit and report that applies a controller call says "controller recommendation, owner unavailable".
- **Spec amendment:** A-8 lands only on a P0-A pass, as the last step of Task 8, in its own commit. Each changed line carries "(A-8, plan 6: controller recommendation, owner unavailable)", and the Status line gets one sentence.
- **Workflow:**
  - Every implementer runs `graphify query "<question>"` (or `explain`/`path`) from the repo root before reading code, and `graphify update .` after changing it.
  - Commits carry no co-author line.
  - Never use `--no-verify`.
  - Nothing is pushed.

## Review Focus

1. **A calibration run cut short, or resumed on other code** (a crash, a reboot, Ctrl+C, a harness error on one candidate, a fix commit between attempts). Each evaluation is a p0 step keyed by its candidate and `p0.code_id()`: a finished one is kept, an interrupted one reruns from scratch, changed code reruns every one, and the decision reads records of one code only. Once `meshcal.json` exists, the search is spent and `run` refuses. Tests: plan 5's `test_a_step_runs_once_reruns_when_its_key_or_code_changes_and_a_crash_leaves_nothing` and `test_records_refuse_a_missing_step_or_two_codes` (`tests/test_p0.py`); `test_the_run_resumes_on_the_same_code_and_a_spent_search_refuses` (Task 3).
2. **The guard disagreeing with the axes harness**, which would fail condition 2 for all 48 candidates and spend the one search. `_faults` is the harness's own lint and d/3 checks; a slot pass that raises `RuntimeError` keeps the as-built lines. A changed evaluator file, a baseline unlike r1's frozen one, or an axis regression on the shakedown candidate stops the run before any candidate. Tests: `test_an_axis_the_slot_depth_would_break_keeps_its_as_built_lines` and `test_a_slot_pass_that_does_not_converge_keeps_the_as_built_lines` (Task 2); `test_the_run_refuses_a_changed_harness_and_a_baseline_unlike_r1s` and `test_the_shakedown_stops_the_run_before_any_candidate` (Task 3).
3. **A slot over a thin substrate** (a 4-layer GCPW on 0.2 mm prepreg, with h/d under the gate). `build_mesh` passes the board's own h, so the gate keeps d/4 there, while the slot depth holds on a thick board. Test: `test_the_slot_gate_reads_the_boards_substrate` (Task 1).
4. **Harness rows that are not clean numbers** (a board that failed to build, a fit2d that is a ValueError's text or NaN, a missing row or axis). Each counts as a failure in every condition it touches, never as a crash or a pass, and `meshcal.json` stays plain (`p0.save`). Tests: the "fixture that errs", "fixture whose fit2d is NaN" and "a family below the baseline" rows of `test_each_acceptance_condition_rejects_its_case`, `test_a_missing_row_or_axis_counts_as_failed`, and the plain-JSON assertion of `test_the_run_resumes_on_the_same_code_and_a_spent_search_refuses` (Task 3).
5. **A winner that passes the search but fails a product gate test.** The harness runs at 3 GHz with no lid; the suite's gate tests also use 915 MHz projects, lids, synthetic variants and P0-A's coupons at reach 3. The winner is struck by Task 6's pre-registered rule and the next one comes from the same results; nothing is relaxed. Tests: the suite's gate-asserting tests, such as `test_a_pour_that_follows_the_pads_over_a_substrate_a_few_cells_deep_passes_the_fit2d_gate`, whose 0.6 mm case reads −3.66 % under `1-8_none_served`, and Task 6's G1 test.

---

## File structure

```
src/kicad_rf_studio/core/mesh/rule.py    # T1 SLOT_IN/SLOT_GATE/SLOT_SERVED; T2 lint_hits, _axis, _faults; T6 the winner
src/kicad_rf_studio/core/mesh/gates.py   # T2 edge_lint through rule.lint_hits
tools/meshcal.py  tests/test_meshcal.py  # T3 the grid, PINNED, the run loop, the acceptance; T6 the winner's test
tools/p0b/harness.py  tests/test_p0b.py  # T4 B1–B5 at p0a.PIN, B1's 3 % gate
tools/p0d.py  tests/test_p0d.py          # T4 --only for references and traces
tests/test_mesh_rule.py                  # T1, T2; T6 G1 and re-pins
tests/test_gates.py  tests/test_p0a.py  tests/test_cli_cost.py  tests/test_preview.py  tests/test_model_ports.py  tests/test_p0d_refs.py   # T6
src/kicad_rf_studio/core/messages.py  core/geometry/sections.py  core/project.py  pipeline.py           # T8, by branch
tests/test_cli_cost.py  tests/test_geometry_sections.py  tests/test_p0b.py  tests/test_project.py  tests/test_cli_new.py  tests/conftest.py   # T8, by branch
docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md   # T8 A-8 (pass only)
tests/fixtures/p0d/*.npz  tests/fixtures/traces/*.npz                  # T10
README.md                                                              # T11, if lpf915's cells moved
outside the repo: <R1> (r1's harness), <P0-2>\meshcal (boards, tree, outputs, steps), <P0-2> (P0-A, B1)
```

## Decisions this plan fixes

| Decision | Task |
|---|---|
| `rule.SLOT_IN`, `SLOT_GATE`, `SLOT_SERVED` (off: `None`, `0.0`, `False`) and `_patterns`' slot branch | 1 |
| `rule.lint_hits`, `_axis`, `_faults`, the guard in `xy_lines`; `gates.edge_lint` through `lint_hits` | 2 |
| `tools/meshcal.py`: `CANDIDATES`, `SHAKE`, `PINNED`, `ok`, `passes`, `axis_regressions`, `accept`, `choose`, `run`, `decide`; `<P0-2>\meshcal`'s layout | 3 |
| B1–B5 at `p0a.PIN` with B1's 3 % gate; `p0d.traces(models=)` and `--only` for `references` and `traces` | 4 |
| The winner's constants and re-pins, or the revert | 6 |
| P0-A's branches (D-26..D-30) and A-8 | 8 |
| `tests/fixtures/p0d/*.npz`, `tests/fixtures/traces/*.npz` | 10 |
| The tutorial's cost excerpt; the `GATES` floor clause after B1 | 11 |

## Phase 1 — code

### Task 1 [code]: The slot role, off by default

**Files:**
- Modify: `src/kicad_rf_studio/core/mesh/rule.py` (the constants after `THIN`; `_patterns`, L136–266)
- Test: `tests/test_mesh_rule.py`

**Interfaces:**
- Consumes: `_patterns(edges, d, prefer=(), force=(), h=math.inf)`, `FACE`, `THIN`, `GRID_TOL`; in the tests, `variant`, `build_mesh`, `_patterns` and `GRID_TOL`.
- Produces:
  - `rule.SLOT_IN: float | None = None`, in multiples of d; None is the rule as built.
  - `rule.SLOT_GATE: float = 0.0`, in multiples of d; 0 means no gate.
  - `rule.SLOT_SERVED: bool = False`: False applies the depth to lone slot cells only, True to every served slot cell.
  - The test helper `slot(monkeypatch, inside=1/6, gate=0.0, served=False)` and the constant `PAIR`.
  - `_patterns`, `xy_lines` and `build_mesh` keep their signatures.

- [ ] **Step 1: Write the failing tests** in `tests/test_mesh_rule.py`. Add `import kicad_rf_studio.core.mesh.rule as rule` to the imports.

```python
PAIR = [(110.0, -1), (110.15, 1)]  # metal below 110, a 2d gap at d = 0.075, metal above 110.15: two lone slot edges


def slot(monkeypatch, inside=1 / 6, gate=0.0, served=False):
    """The slot role on (plan 6), with these values."""
    for name, v in (("SLOT_IN", inside), ("SLOT_GATE", gate), ("SLOT_SERVED", served)):
        monkeypatch.setattr(rule, name, v)


@pytest.mark.parametrize("inside", [1 / 8, 1 / 6])  # 1/8 meets the d/8 + GRID_TOL floor
def test_a_lone_slot_edge_gets_the_slot_depth_and_keeps_its_outside_line(monkeypatch, inside):
    d = 0.075
    slot(monkeypatch, inside)
    deep = max(inside * d, d / 8 + GRID_TOL)
    assert sorted(_patterns(PAIR, d)) == [round(110.0 - deep, 6), 110.05625, 110.09375, round(110.15 + deep, 6)]


def test_an_open_edge_keeps_d_over_4(monkeypatch):  # a strip facing no metal has no slot edge
    slot(monkeypatch)
    assert sorted(_patterns([(109.0, 1), (110.0, -1)], 0.075)) == [108.94375, 109.01875, 109.98125, 110.05625]


@pytest.mark.parametrize(("h", "gate", "inside"), [(None, 4.2, 1 / 6), (4.2, 4.2, 1 / 6), (4.1, 4.2, 1 / 4),
                                                   (2.0, 2.0, 1 / 6), (1.9, 2.0, 1 / 4), (0.5, 0.0, 1 / 6)])
def test_the_slot_depth_holds_from_the_gate_on(monkeypatch, h, gate, inside):  # h ≥ gate·d; no h passes every gate
    d = 0.075
    slot(monkeypatch, gate=gate)
    assert round(110.0 - inside * d, 6) in _patterns(PAIR, d, **({} if h is None else {"h": h * d}))


@pytest.mark.parametrize(("served", "pair"), [(False, 1 / 4), (True, 1 / 6)])
def test_a_served_pair_takes_the_slot_depth_only_in_the_served_scope(monkeypatch, served, pair):
    # a strip edge with a pad step 0.2d past it, one served cell, and its GND edge 3d away (within FACE, past ALONE)
    d = 0.075
    slot(monkeypatch, served=served)
    pins = _patterns([(110.0, -1), (110.015, -1), (110.225, 1)], d)
    assert sorted(pins) == [round(110.0 - pair * d, 6), 110.05625, 110.16875, 110.2375]  # the lone GND edge: both


def test_a_slot_edge_the_lint_forces_keeps_the_exact_edge_lines(monkeypatch):  # spec 5.5's re-mesh
    slot(monkeypatch)
    assert sorted(_patterns(PAIR, 0.075, force=[(110.0, -1)])) == [109.98125, 110.05625, 110.09375, 110.1625]


@pytest.mark.parametrize(("thickness", "line"), [("0.71", -100.463042), ("0.2", -100.469313)])
def test_the_slot_gate_reads_the_boards_substrate(tmp_path, monkeypatch, thickness, line):  # Review Focus 3
    # coupon_gcpw's GND edge facing LINE, at -100.4505: h/d 9.4 takes d/6 under a gate of 3; on 0.2 mm, h/d 2.7 keeps d/4
    slot(monkeypatch, gate=3.0)
    geom, prot = variant(tmp_path, "coupon_gcpw", "(thickness 0.71)", f"(thickness {thickness})")
    assert np.isclose(build_mesh(geom, prot, 2).y, line, rtol=0, atol=1.5e-6).any()
```

- [ ] **Step 2: Run** `python -m pytest tests/test_mesh_rule.py -q -k "slot or open_edge"`. Expected: FAIL with `AttributeError: ... has no attribute 'SLOT_IN'`.
- [ ] **Step 3: Implement** in `rule.py`. Add these constants after `THIN`:

```python
SLOT_IN: float | None = None  # ×d: a slot edge's inside depth (design 2026-10-26 §5.1); None keeps d/4, the rule as built
SLOT_GATE = 0.0  # ×d: the slot depth holds where the substrate h is this deep or more; 0: everywhere
SLOT_SERVED = False  # True: also a served cell of several edges whose deepest is a slot edge; False: lone cells only
```

  In `_patterns`, beside `near`, add `def facing(opp: list[float], u: float) -> bool`: an edge of the other side lies within FACE·d outside `u`, that is `bisect_left(opp, u - FACE * d) < bisect_left(opp, u)`. `faces` now uses it. Then follow r1's probe exactly:

```python
            j, served, slotted = k + 1, False, False
            ...
                    top, served, j = us[k] + deep, False, k + 1  # else d/8 in, as shallow as the lint allows
                elif SLOT_IN is not None and h >= SLOT_GATE * d and facing(opp, us[k]) and (SLOT_SERVED or j == k + 1):
                    top, slotted = us[k] + max(SLOT_IN * d, deep), True  # a slot edge's own depth (plan 6)
                elif sum(cut) > 1:  # several cut edges: ... (unchanged)
            ...
            bottom, shared = min(cell[0] - 3 * d / 4 if slotted else top - d if served else low - 3 * d / 4,
                                 2 * low - top - lead), None
```

  The docstring gains one bullet: a slot edge, one that the other side's metal faces across a gap within FACE·d, has its inside line SLOT_IN·d deep (at least d/8 + GRID_TOL) where h ≥ SLOT_GATE·d. It applies in a cell of its own or, with SLOT_SERVED, in any served cell it is the deepest edge of. Its outside line stays 3d/4 out.
- [ ] **Step 4: Run** the slot tests, then `python -m pytest -q`. Expected: all pass. Every other test is unchanged: the role is off, so the P0 model hashes in `tests/fixtures/p0d` still match.
- [ ] **Step 5: Commit.** `git add src/kicad_rf_studio/core/mesh/rule.py tests/test_mesh_rule.py`, then `git commit -m "feat(mesh): a slot edge's own inside depth behind SLOT_IN, off by default (design 2026-10-26 §5.1)"`, then `graphify update .`.

### Task 2 [code]: The axis guard

Why: with h unset, every gate passes, so the axes harness sees each candidate ungated. There r1 measured 3168 axis regressions (2005 lint, 1184 under d/3) for ungated served d/6. Two mechanisms, reproduced on r1's probe tree, break such axes at some depths:
- the grading splits the cell beside a shallower shared edge cell into two cells under d/3;
- the collision fallback leaves one line between two facing edges.

Without this guard, condition 2 would very likely reject all 48 candidates. The guard is part of the searched rule and pre-registered with it (ruling). With it, condition 2 still catches an exception other than `RuntimeError` in a slot pass, and any check where `_faults` and the harness disagree, which the shakedown (Task 3) tests before the search.

**Files:**
- Modify: `src/kicad_rf_studio/core/mesh/rule.py` (`xy_lines`, `_patterns`), `src/kicad_rf_studio/core/mesh/gates.py` (`edge_lint`)
- Test: `tests/test_mesh_rule.py`

**Interfaces:**
- Consumes: Task 1's constants, `slot` and `PAIR`; the test helper `lint`.
- Produces:
  - `rule.lint_hits(lines: np.ndarray, edges: Iterable[Edge], d: float) -> list[tuple[float, str]]`. Each item is the edge's position and its reason: `"on_edge"`, `"inside_too_close"` or `"outside_closer"`.
  - `rule._axis(edges, extent, walls, free, d, coarse, prefer, force, h, slot: bool) -> tuple[np.ndarray, np.ndarray]`.
  - `rule._faults(lines: np.ndarray, edges: list[Edge], d: float) -> bool`.
  - `_patterns(edges, d, prefer=(), force=(), h=math.inf, slot: bool = True)`.
  - `xy_lines` keeps its signature.

- [ ] **Step 1: Write the failing tests.** Add `import math` to the imports.

```python
BROKEN = {  # plan 2's ratchet axes (d = 0.075) that the slot depth d/6 alone breaks (r1's ungated probe)
    "d3": [(110.0, -1), (110.0015, 1), (110.0675, -1)],  # facing|1,44,1: a cell under d/3 at d/6 (a lint hit at d/8–5d/32)
    "lint": [(110.0, -1), (110.009, 1), (110.03, -1), (110.069, -1)],  # stairopp|8,3,8,1: one line between two edges
}
ARGS = ((100.0, 120.0), (80.0, 140.0), [], 0.075, 2.36)  # extent, walls, free, d, coarse


@pytest.mark.parametrize("edges", BROKEN.values(), ids=BROKEN)
def test_an_axis_the_slot_depth_would_break_keeps_its_as_built_lines(monkeypatch, edges):  # Review Focus 2
    built = rule._axis(edges, *ARGS, (), (), math.inf, False)  # the rule as built, whatever the constants say
    slot(monkeypatch)
    alone = rule._axis(edges, *ARGS, (), (), math.inf, True)[0]
    assert np.diff(alone).min() < 0.075 / 3 - GRID_TOL or lint(alone, edges, 0.075)
    on = xy_lines(edges, *ARGS)
    assert np.array_equal(on[0], built[0]) and np.array_equal(on[1], built[1])


def test_a_slot_pass_that_does_not_converge_keeps_the_as_built_lines(monkeypatch):  # Review Focus 2
    built = rule._axis(PAIR, *ARGS, (), (), math.inf, False)
    slot(monkeypatch)
    axis = rule._axis

    def stuck(*a):  # _grade's guard, on the slot pass only
        if a[-1]:
            raise RuntimeError("the mesh grading did not converge")
        return axis(*a)

    monkeypatch.setattr(rule, "_axis", stuck)
    on = xy_lines(PAIR, *ARGS)
    assert np.array_equal(on[0], built[0]) and np.array_equal(on[1], built[1])


def test_an_axis_the_slot_depth_leaves_clean_takes_it(monkeypatch):
    slot(monkeypatch)
    lines, _ = xy_lines(PAIR, *ARGS)
    assert {109.9875, 110.1625} <= set(lines.tolist())
```

- [ ] **Step 2: Run** `python -m pytest tests/test_mesh_rule.py -q -k "would_break or does_not_converge or leaves_clean"`. Expected: the two `would_break` cases and `does_not_converge` FAIL with `AttributeError: ... has no attribute '_axis'`. `leaves_clean` already passes, since Task 1 applies the depth; it guards that the guard keeps a clean axis's slot lines.
- [ ] **Step 3: Implement:**
  - `lint_hits` takes `gates.edge_lint`'s per-axis loop body verbatim: distances to 1e-9 mm, and a tie fails. `edge_lint` becomes `[LintHit(axis, e, reason) for axis in "xy" for e, reason in lint_hits(getattr(mesh, axis), mesh.edges.get(axis, ()), mesh.d)]`; test_gates' six edge-lint tests keep covering that loop.
  - Today's `xy_lines` body becomes `_axis(..., h, slot)`, which passes `slot` to `_patterns`. In `_patterns`, the slot branch's condition starts `slot and SLOT_IN is not None and ...`.
  - `_faults` is the axes harness's own checks, the lint and the d/3 merge: `return bool(lint_hits(lines, edges, d)) or bool(np.diff(lines).min() < d / 3 - GRID_TOL)`. No RATIO check: `_grade` returns only lines that pass it with the edges held (0 ratio faults in r1's six runs of 246,064 axes).
  - `xy_lines`:

```python
    if SLOT_IN is not None:  # ponytail: one failing check reverts the whole axis; per cell, if boards lose the depth so
        try:
            out = _axis(edges, extent, walls, free, d, coarse, prefer, force, h, True)
            if not _faults(out[0], edges, d):
                return out
        except RuntimeError:  # _grade's guard
            pass
    return _axis(edges, extent, walls, free, d, coarse, prefer, force, h, False)
```

  `xy_lines`' docstring gains: the slot depth holds on an axis only where its lines pass the edge lint and the d/3 merge outright; elsewhere the axis keeps the lines of the rule as built.
- [ ] **Step 4: Run** the new tests, then `python -m pytest -q`. Expected: all pass (the role is off).
- [ ] **Step 5: Commit.** `git add src/kicad_rf_studio/core/mesh/rule.py src/kicad_rf_studio/core/mesh/gates.py tests/test_mesh_rule.py`, then `git commit -m "feat(mesh): the slot depth holds on an axis only where its lines pass the lint and the d/3 merge (plan 6 ruling)"`, then `graphify update .`.

### Task 3 [code]: `tools/meshcal.py`, the search and its acceptance

**Files:**
- Create: `tools/meshcal.py`, `tests/test_meshcal.py`

**Interfaces:**
- Consumes:
  - `p0.ROOT`, `p0.enter`, `p0.code_id`, `p0.step`, `p0.records`, `p0.save`, `p0.machine`, `p0.versions`, `p0.table`; Task 1's three constant names.
  - r1's `hrun.py` (argv `out.jsonl manifest.json root`; env `KRS_SRC`, `KRS_REACH`) and `ax/launch.py` (argv `out.json`; env `KRS_TREE`, `KRS_AXIS_H`). Both stay outside the repo. hrun's rows are `{"family", "case", "n", "lint", "ratio", "d3", "fit2d", "secs", ...}` or `{"family", "case", "n", "err"}`. The axes file is `{key: [lint0, lint, ratio, d3, err]}`.
- Produces:
  - `CANDIDATES: list[dict]`: 48 dicts `{"id", "slot_in", "gate", "served"}` in the order depth × gate × scope.
    - Depths: 1/8, 9/64, 5/32, 1/6, 3/16, 5/24, written "1-8", "9-64", "5-32", "1-6", "3-16", "5-24".
    - Gates: 0.0, 2.0, 3.0, 4.2, written "none", "2", "3", "4.2".
    - Scopes: lone, served.
    - Example id: `"1-6_4.2_served"`.
  - `BASE = {"id": "off", "slot_in": None, "gate": 0.0, "served": False}`; `SHAKE = "1-6_none_served"` (r1's ungated served d/6, which broke 3168 axes before the guard).
  - `H = {"unset": "", "2d": "2", "5d": "5"}`, `GCPW = ("coupon_gcpw", "coupon_gcpw_masked", "coupon_gcpw_pads", "coupon_dense", "coupon_gcpw_arc")`, `MS = ("coupon_ms", "coupon_ms_masked")`, `N3_EXEMPT = ("lpf915", "lpf915-45")`, `MAX_REGS = 5`, `GCPW_PCT = 1.5`.
  - `PINNED: dict[str, str]`, the sha256 of each file `run` reads from `<R1>`:

    | file | sha256 |
    |---|---|
    | `hrun.py` | `4b36b980ae74efb2e4183ccda03a1def424031083060e522a59b96bea3f301c0` |
    | `all_r6.jsonl` | `e94da21b6f8364b928961eb3e799565d0d722c39a4281d4a0e7d557e9a9f15c9` |
    | `ax/launch.py` | `c27c50e31a16b7682e2171879004173de092656f9377ae77448f0536a58efce6` |
    | `ax/axrun.py` | `ff6628b8e9599c559f379e7468e13076479bfce9aedc663af663859abfe3e5a1` |
    | `ax/common.py` | `c5f36a957d2f5906bd0badbb6fb2851a5a31fa91e44a57afe2fcfefb11d8d2b3` |
    | `ax/axes.py` | `61e5aa7ddf30fcd0762d3e2c88682d9176992de9b1f6fd813566882502f2ea46` |
    | `ax/axes2.py` | `ab105323f4b167bc7cc42c8e60ca7ea28440e9593adda8ac65e705ad66012807` |
    | `ax/caxes.py` | `7cfec228037cdb25b2a7d45f86ddb5378aaa3c922703d45b4bcb65bf278562d2` |
    | `ax/a_head.json`, `ax/a_head_h5.json` | `9b04f55655d058f6a27a076c22ea3187257c63afa5c7115df8a9d732ed84dafd` |
    | `ax/a_head_h2.json` | `b108a7fcbdd7298828ff256c80c20fdf0faa865f9294bcf3ce3b8b0eb73669ff` |

  - `FROZEN = {"rows/off.jsonl": "all_r6.jsonl", "axes/off-unset.json": "ax/a_head.json", "axes/off-2d.json": "ax/a_head_h2.json", "axes/off-5d.json": "ax/a_head_h5.json"}`.
  - `patch(text: str, cand: dict) -> str`: `text` plus one line, `SLOT_IN, SLOT_GATE, SLOT_SERVED = <slot_in!r>, <gate!r>, <served!r>`.
  - `ok(row) -> bool`, `passes(rows, family=None) -> int`, `axis_regressions(base: dict, axes: dict) -> int`, `accept(base_rows, base_axes, rows, axes) -> dict`, `choose(results) -> str | None`.
  - `_call(cmd: list[str], env: dict) -> None`, `subprocess.run(cmd, env=env, check=True)`: the one seam the tests replace.
  - `run(harness: Path, boards: Path, out: Path, cands: list[dict] | None = None) -> dict` and `decide(out: Path, cands: list[dict]) -> dict`.
  - In `out`: `tree/src` (one copy, rebuilt per step), `rows/<id>.jsonl`, `axes/<id>-<h>.json`, `axes/shakedown-<h>.json`, `steps/meshcal-{off,shakedown,<id>}.json` (p0's records), `meshcal.json` and `meshcal.md`. `meshcal.json` holds `{"base": {"passes", "rows", "axes_failing": {h: n}}, "candidates": [accept's dict plus "id", "slot_in", "gate", "served"], "winner": id or null, "versions": p0.versions(), "machine": p0.machine(records)}`.
  - CLI: `python tools/meshcal.py --harness DIR --boards DIR --out DIR`.

- [ ] **Step 1: Write the failing tests** in `tests/test_meshcal.py` (SPDX first line):

```python
import hashlib
import json
import math
from itertools import product
from pathlib import Path

import pytest

import meshcal
import p0


def row(family, case, n, fit2d, gap=0.15):
    return {"family": family, "case": case, "n": n, "lint": 0, "ratio": 0, "d3": 0, "fit2d": list(fit2d),
            "secs": [["LINE", 0.6, gap]] * len(fit2d)}


def table(over=()):
    """hrun.py's rows of the ten fixtures at n = 2 and 3 (GCPW coupons 1.0 %, microstrip 0.2 %, lpf915 2.0 % at n = 2
    and 4.2 % at n = 3, coupon_gcpw_45 with no section) and of a family "fam" of five boards; `over` maps a key to the
    fields it changes, or to a whole row when that row holds "err"."""
    rows = {}
    for n in (2, 3):
        rows |= {("fixtures", c, n): row("fixtures", c, n, [1.0]) for c in meshcal.GCPW}
        rows |= {("fixtures", c, n): row("fixtures", c, n, [0.2], None) for c in meshcal.MS}
        rows |= {("fixtures", c, n): row("fixtures", c, n, [2.0 if n == 2 else 4.2]) for c in meshcal.N3_EXEMPT}
        rows[("fixtures", "coupon_gcpw_45", n)] = row("fixtures", "coupon_gcpw_45", n, [])
        rows |= {("fam", f"c{i}", n): row("fam", f"c{i}", n, [1.0]) for i in range(5)}
    for key, v in dict(over).items():
        rows[key] = v if "err" in v else {**rows[key], **v}
    return rows


def axes(over=()):
    a = {h: {"facing|1": [0, 0, 0, 0, 0], "facing|2": [1, 1, 0, 0, 0]} for h in meshcal.H}
    for h, key, v in over:
        a[h][key] = v
    return a


LOST = {("fam", "c4", 3): {"fit2d": [3.3]}}  # a board both runs fail
BASE = table({("fixtures", "coupon_gcpw_masked", 2): {"fit2d": [3.77]}, **LOST})  # today: the masked coupon stops
GOOD = table(LOST)  # the masked coupon fixed, nothing lost


def test_the_grid_is_the_designs_48_candidates():  # design 5.1
    grid = [(c["slot_in"], c["gate"], c["served"]) for c in meshcal.CANDIDATES]
    assert grid == list(product([1 / 8, 9 / 64, 5 / 32, 1 / 6, 3 / 16, 5 / 24], [0.0, 2.0, 3.0, 4.2], [False, True]))
    assert len({c["id"] for c in meshcal.CANDIDATES}) == 48 and meshcal.CANDIDATES[0]["id"] == "1-8_none_lone"
    assert meshcal.BASE == {"id": "off", "slot_in": None, "gate": 0.0, "served": False}
    assert meshcal.SHAKE in {c["id"] for c in meshcal.CANDIDATES}


def test_a_candidate_rule_holds_its_values():
    text = (p0.ROOT / "src" / "kicad_rf_studio" / "core" / "mesh" / "rule.py").read_text(encoding="utf-8")
    ns = {}
    exec(compile(meshcal.patch(text, meshcal.CANDIDATES[-1]), "rule.py", "exec"), ns)
    assert (ns["SLOT_IN"], ns["SLOT_GATE"], ns["SLOT_SERVED"]) == (5 / 24, 4.2, True)


def test_a_candidate_that_fixes_the_fixtures_and_loses_nothing_passes():
    r = meshcal.accept(BASE, axes(), GOOD, axes())
    assert (r["c1"], r["c2"], r["c3"], r["c4"], r["pass"]) == (True,) * 5
    assert (r["passes"], r["regressions"], r["gcpw_coupons"], r["gcpw_max"]) == (27, [], [1.0, 1.0], 1.0)


CASES = {  # one change to the candidate each, and the condition it breaks
    "fixture over 3 % at n 2": ({("fixtures", "lpf915", 2): {"fit2d": [3.2]}}, (), "c1"),
    "fixture that fails the lint": ({("fixtures", "coupon_gcpw", 3): {"lint": 1}}, (), "c1"),
    "fixture that errs": ({("fixtures", "coupon_gcpw_pads", 2): {"family": "fixtures", "case": "coupon_gcpw_pads",
                                                                  "n": 2, "err": "RuntimeError('no convergence')"}}, (), "c1"),
    "fixture whose fit2d is NaN": ({("fixtures", "coupon_gcpw", 2): {"fit2d": [math.nan]}}, (), "c1"),
    "axis regression at 2d": ({}, [("2d", "facing|1", [0, 0, 0, 1, 0])], "c2"),
    "six board regressions": ({("fam", f"c{i}", n): {"d3": 1} for i in range(3) for n in (2, 3)}, (), "c3"),
    "a family below the baseline": ({("fam", "c0", 2): {"fit2d": ["ValueError no line"]}}, (), "c3"),
    "a GCPW coupon past 1.5 %": ({("fixtures", "coupon_dense", 3): {"fit2d": [1.6]}}, (), "c4"),
    "microstrip moved": ({("fixtures", "coupon_ms_masked", 2): {"fit2d": [0.201]}}, (), "c4"),
}


@pytest.mark.parametrize(("over", "axes_over", "broken"), CASES.values(), ids=CASES)
def test_each_acceptance_condition_rejects_its_case(over, axes_over, broken):  # Review Focus 4
    r = meshcal.accept(BASE, axes(), table({**LOST, **over}), axes(axes_over))
    assert not r[broken] and not r["pass"]


def test_a_missing_row_or_axis_counts_as_failed():  # Review Focus 4
    rows, ax = table(LOST), axes()
    del rows[("fam", "c1", 2)], ax["2d"]["facing|1"]
    r = meshcal.accept(BASE, axes(), rows, ax)
    assert (r["c2"], r["c3"], r["regressions"], r["families_below"]) == (False, False, ["fam/c1 n=2"], ["fam"])


def test_a_regression_the_family_wins_back_and_an_old_axis_failure_are_no_rejection():
    traded = table({("fam", "c0", 2): {"fit2d": [3.4]}})  # c0 n = 2 lost, c4 n = 3 won: the family keeps its count
    r = meshcal.accept(BASE, axes(), traded, axes([("5d", "facing|2", [1, 1, 1, 1, 0])]))
    assert r["pass"] and r["regressions"] == ["fam/c0 n=2"] and r["axes_regressions"] == {"unset": 0, "2d": 0, "5d": 0}


def test_the_winner_has_the_most_passes_then_the_smallest_gcpw_coupon_fit2d_then_the_grid_order():  # condition 5
    res = [{"id": "a", "pass": True, "passes": 10, "gcpw_max": 0.5},
           {"id": "b", "pass": True, "passes": 11, "gcpw_max": 1.05},
           {"id": "c", "pass": True, "passes": 11, "gcpw_max": 0.71},
           {"id": "d", "pass": False, "passes": 99, "gcpw_max": 0.1},
           {"id": "e", "pass": True, "passes": 11, "gcpw_max": 0.71}]
    assert meshcal.choose(res) == "c" and meshcal.choose(res[:1] + res[3:4]) == "a" and meshcal.choose(res[3:4]) is None


def fake_harness(tmp_path, monkeypatch):
    """r1's harness as small files that meshcal.PINNED pins, and meshcal._call writing each output: BASE's rows and
    axes() for every tree, or `bad`'s text for a name in it. Returns (the folder, the calls, bad)."""
    r1, calls, bad = tmp_path / "r1", [], {}
    frozen = {"all_r6.jsonl": "".join(json.dumps(r) + "\n" for r in BASE.values()),
              **{f"ax/a_head{s}.json": json.dumps(axes()["unset"]) for s in ("", "_h2", "_h5")}}
    for name in meshcal.PINNED:
        (r1 / name).parent.mkdir(parents=True, exist_ok=True)
        (r1 / name).write_text(frozen.get(name, "# r1's script\n"), encoding="utf-8")
    monkeypatch.setattr(meshcal, "PINNED", {n: hashlib.sha256((r1 / n).read_bytes()).hexdigest() for n in meshcal.PINNED})

    def call(cmd, env):
        out, src = Path(cmd[2]), Path(env.get("KRS_SRC") or Path(env["KRS_TREE"]) / "src")
        tail = (src / "kicad_rf_studio" / "core" / "mesh" / "rule.py").read_text(encoding="utf-8").splitlines()[-1]
        calls.append((out.name, env.get("KRS_REACH"), env.get("KRS_AXIS_H"), tail))
        out.write_text(bad.get(out.name, frozen["all_r6.jsonl" if out.suffix == ".jsonl" else "ax/a_head.json"]),
                       encoding="utf-8")

    monkeypatch.setattr(meshcal, "_call", call)
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    monkeypatch.setattr(p0, "code_id", lambda: "tree")
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, "unused")
    return r1, calls, bad


OFF = ["off.jsonl", "off-unset.json", "off-2d.json", "off-5d.json"]


def test_the_run_refuses_a_changed_harness_and_a_baseline_unlike_r1s(tmp_path, monkeypatch, fake):  # Review Focus 2
    r1, calls, bad = fake_harness(tmp_path, monkeypatch)
    (r1 / "ax" / "axes.py").write_text("# changed after the plan's commit\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        meshcal.run(r1, tmp_path / "boards", tmp_path, meshcal.CANDIDATES[:1])
    assert "ax/axes.py" in str(e.value) and calls == []
    (r1 / "ax" / "axes.py").write_text("# r1's script\n", encoding="utf-8")
    bad["off-2d.json"] = json.dumps(axes([("2d", "facing|1", [0, 0, 0, 1, 0])])["2d"])
    with pytest.raises(SystemExit) as e:
        meshcal.run(r1, tmp_path / "boards", tmp_path, meshcal.CANDIDATES[:1])
    assert "a_head_h2.json" in str(e.value) and [c[0] for c in calls] == OFF


def test_the_shakedown_stops_the_run_before_any_candidate(tmp_path, monkeypatch, fake):  # Review Focus 2
    r1, calls, bad = fake_harness(tmp_path, monkeypatch)
    bad["shakedown-5d.json"] = json.dumps(axes([("5d", "facing|1", [0, 1, 0, 0, 0])])["5d"])
    with pytest.raises(SystemExit) as e:
        meshcal.run(r1, tmp_path / "boards", tmp_path, meshcal.CANDIDATES[:1])
    assert meshcal.SHAKE in str(e.value) and [c[0] for c in calls] == [*OFF, *(f"shakedown-{h}.json" for h in meshcal.H)]
    assert calls[-1][3] == "SLOT_IN, SLOT_GATE, SLOT_SERVED = 0.16666666666666666, 0.0, True"


def test_the_run_resumes_on_the_same_code_and_a_spent_search_refuses(tmp_path, monkeypatch, fake):  # Review Focus 1
    r1, calls, _ = fake_harness(tmp_path, monkeypatch)
    cands = meshcal.CANDIDATES[:1]
    d = meshcal.run(r1, tmp_path / "boards", tmp_path, cands)
    one = [f"1-8_none_lone{s}" for s in (".jsonl", "-unset.json", "-2d.json", "-5d.json")]
    assert [c[0] for c in calls] == [*OFF, *(f"shakedown-{h}.json" for h in meshcal.H), *one]
    assert calls[0][:3] == ("off.jsonl", "6", None) and [c[2] for c in calls[1:4]] == ["", "2", "5"]
    assert calls[-4][3] == "SLOT_IN, SLOT_GATE, SLOT_SERVED = 0.125, 0.0, False"
    text = (tmp_path / "meshcal.json").read_text(encoding="utf-8")
    assert json.loads(text) == d and d["winner"] is None and d["base"]["passes"] == 26 and d["machine"]["steps"] == 3
    assert not any(s in text for s in (":\\", ":/", "NaN", "Infinity")) and "| 1-8_none_lone |" in (
        tmp_path / "meshcal.md").read_text(encoding="utf-8")
    (tmp_path / "meshcal.json").unlink()  # a crash after the last step: the rerun runs nothing again
    assert meshcal.run(r1, tmp_path / "boards", tmp_path, cands) == d and len(calls) == 11
    with pytest.raises(SystemExit) as e:
        meshcal.run(r1, tmp_path / "boards", tmp_path, cands)
    assert "spent" in str(e.value) and len(calls) == 11
```

- [ ] **Step 2: Run** `python -m pytest tests/test_meshcal.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'meshcal'`.
- [ ] **Step 3: Implement** `tools/meshcal.py`. The module docstring says: dev-time only, the package never imports it, `# ponytail: single-use, plan 6's one search; the harness and its boards stay outside the repo`, and the run line. The acceptance is the pre-registered rule, so its body is given here:

```python
def ok(row: dict) -> bool:
    """A board row that passes every gate (plan 2's ratchet): built, no lint hit after the one re-mesh, no ratio fault,
    no cell under d/3, every section's fit2d a number under 3 % (D-22)."""
    return "err" not in row and row["lint"] == row["ratio"] == row["d3"] == 0 and all(
        isinstance(v, float) and abs(v) < 3 for v in row["fit2d"])


def passes(rows: dict, family: str | None = None) -> int:
    return sum(ok(r) for (f, _, _), r in rows.items() if family in (None, f))


def axis_regressions(base: dict, axes: dict) -> int:
    """The axes clean in `base` that fail in `axes` (lint after the re-mesh, ratio, d/3 or an error); one `axes`
    lacks counts as failed."""
    return sum(not any(v[1:]) and any(axes.get(key, [1] * 5)[1:]) for key, v in base.items())


def accept(base_rows: dict, base_axes: dict, rows: dict, axes: dict) -> dict:
    """The design's acceptance (§5.1, fixed before the search) of one candidate's rows and axes against the
    baseline's; a row or axis the candidate lacks counts as failed."""
    def get(key):
        return rows.get(key, {"err": "missing"})
    fixtures = [get(k) for k in base_rows if k[0] == "fixtures" and (k[2] == 2 or k[1] not in N3_EXEMPT)]
    regs = [k for k in base_rows if ok(base_rows[k]) and not ok(get(k))]
    below = sorted({f for f, _, _ in base_rows if passes(rows, f) < passes(base_rows, f)})
    axes_regs = {h: axis_regressions(base_axes[h], axes[h]) for h in H}
    gcpw = [v for k in base_rows if k[0] == "fixtures" and k[1] in GCPW for v in get(k).get("fit2d", [None])]
    ms = all(get(k).get("fit2d") == base_rows[k]["fit2d"] for k in base_rows if k[0] == "fixtures" and k[1] in MS)
    c = {"c1": all(map(ok, fixtures)), "c2": not any(axes_regs.values()),
         "c3": len(regs) <= MAX_REGS and all(k[0] != "fixtures" for k in regs) and not below,
         "c4": ms and all(isinstance(v, float) and -GCPW_PCT <= v <= GCPW_PCT for v in gcpw)}
    finite = [v for v in gcpw if isinstance(v, float) and math.isfinite(v)]
    return {**c, "pass": all(c.values()), "passes": passes(rows), "regressions": [f"{f}/{x} n={n}" for f, x, n in regs],
            "families_below": below, "axes_regressions": axes_regs, "ms_unchanged": ms,
            "gcpw_coupons": [min(finite), max(finite)] if finite else None,
            "gcpw_max": max(map(abs, finite), default=None)}


def choose(results: list[dict]) -> str | None:
    """Condition 5: of the candidates that pass, the most passes, then the smallest max |fit2d| over the GCPW
    coupons' sections at n 2 and 3 (condition 4's), then the first in the grid's order."""
    best = min(((-r["passes"], r["gcpw_max"], i) for i, r in enumerate(results) if r["pass"]), default=None)
    return None if best is None else results[best[2]]["id"]
```

  `run`, in this order:
  - SystemExit naming `meshcal.json` ("the one search is spent") when `out/meshcal.json` exists.
  - `out = p0.enter(out)` (it refuses a git work tree and holds `out/harness.lock`). SystemExit when `p0.code_id()` ends in `+dirty`.
  - SystemExit naming every `PINNED` file that is missing from `harness` or whose sha256 differs, before any step.
  - Make `out/rows` and `out/axes`. An evaluation of a candidate rebuilds `out/tree` (`shutil.rmtree`, then `shutil.copytree(p0.ROOT / "src", tree / "src", ignore=shutil.ignore_patterns("__pycache__"))`, then `patch`'s line appended to the tree's `rule.py`). It then calls `_call` with:
    - the rows command `[sys.executable, str(harness / "hrun.py"), str(out / "rows" / f"{id}.jsonl"), str(boards / "scratch-T10-r5" / "all.json"), str(boards)]` and env `{**os.environ, "KRS_SRC": str(tree / "src"), "KRS_REACH": "6"}`;
    - for each h of `H`, the axes command `[sys.executable, str(harness / "ax" / "launch.py"), str(out / "axes" / f"{id}-{h}.json")]` and env `{**os.environ, "KRS_TREE": str(tree), "KRS_AXIS_H": H[h]}`.
  - `p0.step(out, "meshcal-off", "off", ...)` evaluates `BASE`. Then SystemExit naming each frozen file of `FROZEN` whose output differs (rows compared line by line, axes as parsed dicts): "stop and report".
  - `p0.step(out, "meshcal-shakedown", SHAKE, ...)` builds `SHAKE`'s tree, runs its three axes commands into `axes/shakedown-<h>.json` and returns `{h: axis_regressions(off's axes, the shakedown's)}`. Any non-zero count: SystemExit naming `SHAKE` and the counts ("fix Task 2 test-first").
  - `p0.step(out, f"meshcal-{id}", id, ...)` evaluates each of `cands` (default `CANDIDATES`). A failed command raises out of `run` (`# ponytail: stops at the first failed evaluation; a rerun resumes`).
  - Return `decide(out, cands)`.

  `decide`:
  - `p0.records(out, ["meshcal-off", "meshcal-shakedown", *("meshcal-" + id for each of cands)])`: it refuses a missing record or records of two codes.
  - Load off's rows and axes once, then each candidate's rows and three axes files in turn (about 50 MB per axes file in memory), calling `accept` on each.
  - `p0.save(out / "meshcal.json", ...)` with `"rows"` the number of off's rows (2142), `"axes_failing"` the axes failing at each h in off, and `"machine": p0.machine(records)`.
  - `meshcal.md`: the base line, `p0.table(candidates, ["id", "c1", "c2", "c3", "c4", "pass", "passes", "regressions", "families_below", "gcpw_coupons", "gcpw_max"])` and the winner line.
  - Print the winner.
- [ ] **Step 4: Run** the file, then `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit.** `git add tools/meshcal.py tests/test_meshcal.py`, then `git commit -m "feat(tools): meshcal, plan 6's 48 slot-role candidates as p0 steps on plan 2's pinned ratchet and the five pre-registered acceptance conditions (design §5.1)"`, then `graphify update .`.

### Task 4 [code]: The P0 tools for the re-check

**Files:**
- Modify: `tools/p0b/harness.py` (`VARIANTS`, L38–39; `import p0a` after `import p0`), `tools/p0d.py` (`traces`, `main`)
- Test: `tests/test_p0b.py` (L35–47), `tests/test_p0d.py` (`test_references_and_traces_come_from_a_p0_folder`)

**Interfaces:**
- Consumes: `p0a.PIN == {"mesh.reach_h": 3.0}`, `harness.project`, `p0d.references(p0_dir, out, models=MODELS)`.
- Produces:
  - `VARIANTS = {"B1": ("lpf915", {**p0a.PIN, "gates.fit2d_limit": 0.03}), "B4": ("lpf915-45", {"allow_curve_port": True, **p0a.PIN}), "B5": ("lpf915", {"mesh.n": 3, "gates.fit2d_limit": 0.05, **p0a.PIN}), "B6": ("lpf915", {"mesh.reach_h": 6.0})}`. B2 and B3 follow B1. The comment cites the exit report and r4 (B1 alone rebuilds P0-D's lpf915 reference) and says why B1's gate is pinned: under D-29's lower branch, `new`'s default limit could block B1 with E_FIT2D, and `gates` is not in the model spec, so the model hash does not move.
  - `p0d.traces(p0_dir: Path, out: Path, models: tuple[str, ...] = ("coupon_gcpw_pads", "lpf915")) -> list[Path]`, reading only the records of `models`.
  - `p0d.py references|traces ... --only M,...`, as `models --only` (a name outside the command's models is a parser error).

- [ ] **Step 1: Write the failing tests.** Change `test_the_p0b_projects_are_fresh_projects_with_their_edits`:

```python
def test_the_p0b_projects_are_fresh_projects_with_their_edits(p0_out, monkeypatch):  # D-32, D-9; B1-B5 at p0a.PIN (r4)
    monkeypatch.setattr(p0, "cli", in_process)
    b1, b5, b4, b6 = (load_project(harness.project(p0_out, r)) for r in ("B1", "B5", "B4", "B6"))
    assert (b5["mesh"], b5["gates"]["fit2d_limit"], b5["lid_height_mm"]) == ({"n": 3, "reach_h": 3.0}, 0.05, 2.5)
    assert (b1["mesh"], b1["gates"]["fit2d_limit"]) == ({"n": 2, "reach_h": 3.0}, 0.03)  # 3 % under any D-29 branch
    assert (b4["mesh"]["reach_h"], b4["allow_curve_port"], b6["mesh"]) == (3.0, True, {"n": 2, "reach_h": 6.0})
    assert (p0_out / "boards" / "lpf915-45.kicad_pcb").is_file()
    pj = harness.project(p0_out, "B5")
    d = load_project(pj)
    d["mesh"]["n"] = 2  # an interruption between new and the edits
    save_project(pj, d)
    assert load_project(harness.project(p0_out, "B5"))["mesh"]["n"] == 3
```

  At the end of `test_references_and_traces_come_from_a_p0_folder`, after the refusal of B1's t_max job:

```python
    pad = tmp_path / "pad"  # --only: the pad's reference and traces, B1's record never read (plan 6's lpf915 branch)
    assert p0d.main(["references", "--p0", str(p0_out), "--out", str(pad), "--only", "coupon_gcpw_pads"]) == 0
    assert p0d.main(["traces", "--p0", str(p0_out), "--out", str(pad), "--only", "coupon_gcpw_pads"]) == 0
    assert sorted(p.name for p in pad.iterdir()) == ["coupon_gcpw_pads-k1.npz", "coupon_gcpw_pads-k2.npz",
                                                      "coupon_gcpw_pads.npz"]
```

- [ ] **Step 2: Run** `python -m pytest tests/test_p0b.py tests/test_p0d.py -q -k "fresh or come_from"`. Expected: FAIL (B5's `reach_h` reads 6.0; p0d's parser rejects `--only`).
- [ ] **Step 3: Implement** `VARIANTS`, `traces`' `models` and the two `--only` options as in Interfaces.
- [ ] **Step 4: Run** both files, then `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit.** `git add tools/p0b/harness.py tools/p0d.py tests/test_p0b.py tests/test_p0d.py`, then `git commit -m "fix(p0b, p0d): B1 to B5 at p0a.PIN's reach 3 with B1's 3 % gate pinned, and --only for p0d's references and traces (exit report; r4; plan 6 rulings)"`, then `graphify update .`.

## Phase 2 — the search (the controller; nothing is committed)

### Task 5 [run]: The baseline, the shakedown and the 48 candidates

- **Before:**
  - Tasks 1–4 are committed, `git status --porcelain` is empty, and `git rev-parse --short HEAD` is noted.
  - The date is before 2026-11-19; otherwise apply the ceiling's branch.
  - The idle check prints `[0, 0, 0]`.
  - The boards are in place: `(Get-ChildItem <P0-2>\meshcal\boards\scratch-T10-r5 -Recurse -Filter *.kicad_pcb).Count` prints 1061, and `Test-Path <P0-2>\meshcal\boards\scratch-T10-r5\all.json` prints True. `run` checks r1's files against `PINNED` itself.
  - There is room for about 1.45 GB of outputs: `.venv\Scripts\python.exe -c "import shutil,sys; print(shutil.disk_usage(sys.argv[1]).free // 2**30)" <P0-2>` prints 3 or more.
- **Command:** `.venv\Scripts\python.exe tools\meshcal.py --harness <R1> --boards <P0-2>\meshcal\boards --out <P0-2>\meshcal`
- **Expected machine time:** about 5 h, for 49 evaluations and the shakedown (r1 §2):
  - a board run is 64–90 s on 12 processes (1071 boards at n 2 and 3: 2322 sections, 4644 cs2d solves);
  - an axes run is 72–80 s for the baseline (246,064 axes), and about 95–105 s for a candidate, since Task 2's guard adds about 30 %;
  - so an evaluation takes 6–7 min, and the shakedown's three axes runs about 5 min.
- **Expected results (pre-registered; r1's probes, all in the served scope and before the guard):**
  - The baseline: 1966 of 2142 rows pass, and 24,745, 24,744 and 24,745 axes fail at h unset, 2d and 5d. The shakedown shows 0 axis regressions.
  - At gate 4.2 (passes / regressions / GCPW coupons' fit2d range):

    | candidate | passes | regressions | GCPW coupons | conditions |
    |---|---|---|---|---|
    | d/8 + GRID_TOL | 2003 | 6 | −1.22…−0.04 % | fails 3 |
    | d/6 | 2004 | 4 | −0.11…+1.05 % | meets 1, 3 and 4 |
    | 3d/16 | 2004 | 3 | +0.53…+1.73 % | fails 4 |
    | 5d/24 | 2000 | 2 | +1.02…+2.41 % | fails 4 |

  - At gate none: d/6 had 2042 passes and 6 regressions (4 fit2d, 2 d/3), and broke 3168 axes; d/8 had 2003 passes and 49 regressions (47 fit2d, 2 lint), with 5 families below the baseline.
  - With the guard, condition 2 holds for every candidate by construction, and a lint or d/3 regression reverts its axis to the as-built lines, so board rows regress only through fit2d. r1's fit2d-only regressions: at gate 4.2, d/8 4, d/6 2, 3d/16 1, 5d/24 1; at gate none, d/6 4, d/8 47.
  - The expected winner (a prediction, not a rule) is a no-gate candidate at or near d/6, such as `1-6_none_served` with about 2042 passes or more, 4 fit2d regressions and no family below the baseline. Every 3d/16 and 5d/24 candidate is expected to fail condition 4, since the GCPW coupons sit above every gate. The lone scope and the gates 2 and 3 have no prior board-row data.
- **Outputs:** in `<P0-2>\meshcal\`: `rows\<id>.jsonl` (49); `axes\<id>-{unset,2d,5d}.json` and `axes\shakedown-{unset,2d,5d}.json` (150 files of about 9.4 MB); `tree\src`; `steps\meshcal-*.json` (50); `meshcal.json` and `meshcal.md`; `data\` and `harness.lock` (p0.enter).
- **Done when:** the command exits 0 and `.venv\Scripts\python.exe -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print(d['base']['passes'], d['winner'], [c['id'] for c in d['candidates'] if c['pass']], d['machine'])" <P0-2>\meshcal\meshcal.json` prints 1966, the winner (or None), the passing candidates and the machine time.

  A SystemExit names what stopped the run:
  - a pinned file: restore r1's copy;
  - the baseline: Tasks 1–3 changed the rule while off; stop and report;
  - the shakedown: fix Task 2's guard test-first under the fix rule (Global Constraints), then rerun;
  - a dirty src, or a spent search.

  A failed evaluation stops the command too. Rerun the same command: finished steps are kept, and a fix commit reruns every step, since the steps are keyed by code.

## Phase 3 — decisions, runs and references

### Task 6 [decide]: The winner, or none

**Reads:** `<P0-2>\meshcal\meshcal.json` and `meshcal.md` (the controller gives `<P0-2>`). `winner` is the pre-registered choice; apply it as computed.

**Branch none** (`winner` is null, or every passing candidate was struck in Step 3 below). The rule does not change, and there is no second round (design §5.1).
- [ ] **Step 1:** Discard the winner branch's uncommitted edits, if any (`git restore src tests`). Then `git revert --no-commit` the commits of Tasks 3, 2 and 1, newest first (find them by their messages). Task 4 stays. Then `git diff <plan commit> --stat -- src/kicad_rf_studio/core/mesh tests/test_mesh_rule.py tests/test_gates.py` prints nothing.
- [ ] **Step 2:** `python -m pytest -q`. Expected: all pass.
- [ ] **Step 3: Commit.** `git commit -m "revert: plan 6's slot role and its calibration tool — no candidate passed the pre-registered acceptance (design §5.1; controller recommendation, owner unavailable)"`. When candidates were struck, the message says "no passing candidate survived the suite's gate tests" instead.
- [ ] **Step 4:** Return "no winner", and each struck candidate with the test it failed, to the controller, who goes to Task 11.

**Branch winner:**
- [ ] **Step 1: Write the failing tests.**
  - G1, in `tests/test_mesh_rule.py` (add `from kicad_rf_studio.core.mesh.gates import mesh_with_lint`):

    ```python
    G1 = [(*f, n) for f in FIXTURES for n in (2, 3) if n == 2 or not f[0].startswith("lpf915")]


    @pytest.mark.parametrize(("name", "start", "end", "n"), G1)
    def test_every_fixture_section_passes_the_fit2d_gate(name, start, end, n):  # design G1: plan 6's slot role (A-8)
        g, prot = geometry(name, start, end)  # the ratchet's own build (3 GHz, no lid, reach 6): condition 1 in tier (a)
        assert max(map(abs, fit2d(g, mesh_with_lint(g, prot, n))), default=0.0) < 3
    ```

  - The winner's constants, in `tests/test_meshcal.py` (add `import kicad_rf_studio.core.mesh.rule as rule`):

    ```python
    def test_the_slot_role_is_plan6s_winner():  # the constants are the searched candidate's, as the grid writes them
        c = next(c for c in meshcal.CANDIDATES if c["id"] == "<winner id>")
        assert (rule.SLOT_IN, rule.SLOT_GATE, rule.SLOT_SERVED) == (c["slot_in"], c["gate"], c["served"])
    ```

  Run both. Expected: FAIL (coupon_gcpw_masked reads 3.768 % at n = 2; `SLOT_IN` is None).
- [ ] **Step 2:** In `rule.py`, set `SLOT_IN`, `SLOT_GATE` and `SLOT_SERVED` to the winner's values, written as the grid's literals (for example `1 / 6`, `0.0`, `True`), with the comment "plan 6's calibration (design §5.1, A-8)". Run both tests. Expected: PASS.
- [ ] **Step 3: Run the suite, sort every failure by these rules, and re-pin only when rule 2 does not fire:**
  1. A test that asserts a measured value of the rule (a fit2d %, a line's position, an e_fit) gets the value it now measures, at its own precision. A tolerance never changes.
  2. A test that asserts a gate passes (|fit2d| < 3 %, no lint hit, no cell under d/3, a run not blocked) and now fails strikes the winner. Undo Step 2 and the winner's test, keep G1, then run `.venv\Scripts\python.exe -c "import json,sys; sys.path.insert(0,'tools'); import meshcal; d=json.load(open(sys.argv[1],encoding='utf-8')); print(meshcal.choose([c for c in d['candidates'] if c['id'] not in sys.argv[2].split(',')]))" <P0-2>\meshcal\meshcal.json <struck ids>`. It prints the next winner, from the same results with no new run: restart at Step 1 with it. If it prints None, take the none branch.
  3. A test that asserts a gate blocks a synthetic case at a fixed limit, and no longer does, takes `half_its_error` of that case as its limit, never a new literal.

  The known re-pins (from four candidates run on a scratch tree and from the code):
  1. `tests/test_gates.py::test_fit2d_passes_on_rule_mesh`: its two rows, coupon_gcpw at n 2 and coupon_gcpw_masked at n 3, get the values they now read, to 2 decimals. The comment says plan 6's slot role (A-8) moved them, and R-P2-20 read +3.78 % at n = 2 before it.
  2. `tests/test_p0a.py::test_the_references_are_kicad_and_the_45h_2d_line`: `0.0378` becomes the `ref["e_fit"]` the test now reads (reach 3, which `p0a.coupon_model` pins), to 4 decimals, keeping `abs=2e-4`. The comment says R-P2-20 read 0.0378 before plan 6's slot role.
  3. `tests/test_cli_cost.py::test_a_failed_fit2d_still_prints_the_cost_and_exits_3` becomes rule-independent; under d/6 the pad coupon reads about −0.1 %, below any round limit. Add `from kicad_rf_studio.core.mesh.gates import fit2d` and this helper:

     ```python
     def half_its_error(pj: Path) -> float:
         """Half the largest fit2d error of the project `pj`, to one significant digit: a limit its own mesh misses,
         whatever the rule reads (plan 6)."""
         p, board, g, _ = load(pj)
         return float(f"{max(f.err for f in fit2d(g, build_model(p, board, g).mesh)) / 2:.1g}")
     ```

     The test sets `limit = half_its_error(pj)` in `gates`, and asserts `render("W_GATE_LIMITS", fit2d_limit=f"{limit:g}", dt_floor="0.8") in out.splitlines()`.
  4. `tests/test_preview.py::test_a_blocked_gate_is_printed_and_the_model_still_opens` (its "it reads 2.47 %" limit 0.02): `fit2d_limit` becomes `half_its_error(pj)`, imported from `test_cli_cost` beside `fail` and `new_project`.
  5. `tests/test_mesh_rule.py::test_section_edges_keep_their_lines_on_coupon_gcpw_pads` becomes `test_section_edges_keep_their_slot_lines_on_coupon_gcpw_pads`. The GND edges' expected line becomes `round(edge[0] + edge[1] * max(rule.SLOT_IN * m.d, m.d / 8 + GRID_TOL), 6)`: they are lone slot edges at h/d 9.4, so every gate in the grid holds.
  6. `tests/test_model_ports.py::test_port_boxes_span_the_copper_free_gap_between_their_ends`: the four boxes of lpf915 get the coordinates the test now reads, keeping `abs=1e-6`.
  7. Only when `SLOT_SERVED`: in `test_a_facing_cut_edge_keeps_its_d_over_4_line_over_a_substrate_under_4_2_cells`, each row `(h, 1 / 4)` with h ≥ SLOT_GATE expects `rule.SLOT_IN`, and the comment names the slot role.
  8. Mark `tests/test_p0a.py::test_the_harness_builds_the_models_p0a_ran` and `tests/test_p0d_refs.py::test_the_references_are_the_models_p0d_builds_here` with `@pytest.mark.xfail(strict=True, reason="plan 6's slot role moved the P0 models; Task 10 regenerates tests/fixtures/p0d")`.
- [ ] **Step 4:** `python -m pytest -q`. Expected: all pass, 2 xfailed.
- [ ] **Step 5: Commit.** `git commit -am "feat(mesh): a slot edge's inside line at <depth>, gate <gate>, <scope> (plan 6's calibration, design §5.1; controller recommendation, owner unavailable)"`, then `graphify update .`.
- [ ] **Step 6:** Return to the controller: the winner, any struck candidate with the test it failed, and each re-pinned value (old → new).

### Task 7 [run]: P0-A in full in `<P0-2>`

- **Before:**
  - Task 6's winner commit is in, and `git status --porcelain` is empty.
  - The date is before 2026-11-19; otherwise apply the ceiling's branch.
  - Both idle checks print `[0, 0, 0]`.
- **Command:** `.venv\Scripts\python.exe tools\p0a.py --out <P0-2>`. It runs 17 steps: the calibration in `<P0-2>\data`, the 14 coupon runs, the pad coupon through `new`, `cost` and `run`, and the stray-cell setup.
- **Expected machine time:** about 3.1 h. P0-A of 2026-10-24 (§6) took 17 steps and 3.10 machine hours; its 15 timed runs took 10,975 s wall, 1.31× their prediction. The twins take 5480 s of it.
- **Expected results (pre-registered):**
  - The verdict is pass: D-26 pass, D-28 pass, D-29 keep and D-30 confirmed (Stage 1: min ratio 0.9217).
  - Each GCPW row's e_fit is near the winner's fixture fit2d at reach 3, and its δ = e_FDTD − e_fit stays within ±1 pp (Stage 1: −0.14 to −0.24 pp).
  - The microstrip models keep their hashes, so their rows repeat Stage 1's (δ +0.52 to +0.53 pp).
  - D-27 does not refuse. coupon_gcpw's Z0 falls by about its fit2d drop (about 2.5 pp at n 2), which takes the 45° twin from −6.98 % to about −4.6 % at n 2 (design §5.1, the likely case). Advice fires if both twins read smaller at n 3, keep otherwise; the arc's |dz0| may grow at n 3.
- **Outputs:** in `<P0-2>`: `data\kicad-rf-studio\settings.json`; `steps\p0a-*.json` (17); `p0a\p0a.json` and `p0a.md`; `p0a\projects\coupon_gcpw_pads\`.
- **Done when:** the command exits 0 and `.venv\Scripts\python.exe -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print(d['decisions']['verdict'], d['decisions']['twins'], d['decisions']['fit2d']['branch'], d['decisions']['dt_floor'], d['machine'])" <P0-2>\p0a\p0a.json` prints them. Loaded steps keep their S and leave section 6. Exit 1 names the failed steps: fix them test-first under the fix rule, with no run in progress, and rerun. A fix under `src/` reruns every step (PF-52).

### Task 8 [decide]: P0-A's re-check, by plan 5's rules, and amendment A-8

**Reads:** `<P0-2>\p0a\p0a.json` and `p0a.md`; `docs/validation/2026-10-24-p0-a.json`, for the comparison. `decisions` is p0a's own code, unchanged. Apply the branch that fired, exactly. `<date>` is the day this task runs; the controller saves the report under it that day.

**Branch fail** (`decisions.verdict.value == "fail"`, from any cause):
- [ ] **Step 1:** `git revert --no-commit` the commits of Tasks 6, 3, 2 and 1, newest first. Then `git diff <plan commit> --stat -- src/kicad_rf_studio/core/mesh tests/test_mesh_rule.py tests/test_gates.py` prints nothing.
- [ ] **Step 2:** `python -m pytest -q`. Expected: all pass (the old references match the old models again).
- [ ] **Step 3: Commit.** `git commit -m "revert: plan 6's slot role — P0-A's verdict failed under it (design §5.1; controller recommendation, owner unavailable)"`. A-8, B1 and the regeneration do not happen, and the re-check is not repeated.
- [ ] **Step 4:** Return the report text (below). Section 1 quotes `decisions.verdict.fails` and says "P0-A's pre-registered verdict failed under the new rule". It says "FDTD rejected the calibration" only when a listed fail is a D-25 row. Section 5 lists the any-cause rule as a deviation from §5.1's "(any D-25 row out of its limit)". The controller then goes to Task 11.

**Branch pass:** apply D-27, D-29 and D-30. In the texts below:
- `<what>` is "45° line" for coupon_gcpw_45 and "arc" for coupon_gcpw_arc, taken from the `twins` row with the largest |dz0_pct|;
- `<X.X>` is that |dz0_pct| to one decimal;
- `<N>` is that row's n.

- **D-27, `decisions.twins.branch`:**
  - `refuse`: E_STAIRCASED keeps its gate and only its figure changes: "Net {net} has copper that is not axis-aligned (45° segments or arcs), which the mesh staircases. P0-A measured a staircased `<what>` `<X.X>` % off its axis-aligned twin in Z0 at mesh n `<N>`, above the 5 % budget, so the run is blocked. Route the measured nets with horizontal and vertical tracks." `sections()`' docstring follows. New test `test_the_staircase_refusal_states_the_re_checked_error` in `tests/test_cli_cost.py`: `"a staircased <what> <X.X> % off its axis-aligned twin in Z0 at mesh n <N>" in render("E_STAIRCASED", net="RF_B")`. When these equal today's ("45° line", 7.0, 2), nothing changes.
  - `keep`:
    - Code: `sections()` emits `("W_STAIRCASED", {"net": net})`, and its docstring says so. `pipeline.GEOMETRY_GATES = ("E_OPEN_IN_ROI", "E_SHORT_IN_ROI")`.
    - Text: CATALOG loses E_STAIRCASED and gains W_STAIRCASED: "Net {net} has copper that is not axis-aligned (45° segments or arcs), which the mesh staircases. P0-A measured a staircased `<what>` `<X.X>` % off its axis-aligned twin in Z0 at mesh n `<N>`, within the 5 % budget, so the run goes on, but its accuracy is not validated. For a validated result, route the measured nets with horizontal and vertical tracks."
    - Tests:
      - `test_cost_on_45_degree_coupon` returns to its form before dbd28c6: exit 0, `render("W_STAIRCASED", net="LINE")` in its lines, and "staircased" in out.
      - `test_staircased_measured_copper_is_refused_after_p0a` becomes `test_staircased_copper_warns_with_p0as_re_checked_error`: `"E_STAIRCASED" not in CATALOG and pipeline.GEOMETRY_GATES == ("E_OPEN_IN_ROI", "E_SHORT_IN_ROI") and "<X.X> % off its axis-aligned twin in Z0 at mesh n <N>, within the 5 % budget" in render("W_STAIRCASED", net="RF_B")`. `tests/test_cli_cost.py` gains `from kicad_rf_studio import pipeline` and `CATALOG` in its `core.messages` import.
      - The three `E_STAIRCASED` notes in `tests/test_geometry_sections.py` become `W_STAIRCASED`.
      - `tests/test_p0b.py` drops its `GEOMETRY_GATES` monkeypatch and its comment, since that is now the default.
  - `advice`: keep's change, and W_STAIRCASED's template ends " A finer mesh lowers the error: set \"mesh\": {{\"n\": 3}} in project.json." (the braces escaped for `str.format`). Test `test_the_staircase_warning_offers_the_fine_mesh` in `tests/test_cli_cost.py`: `render("W_STAIRCASED", net="RF_B").endswith('set "mesh": {"n": 3} in project.json.')`.
- **D-29, `decisions.fit2d.branch`** (E_FIT2D_FINE stays as it is in every branch):
  - `keep` or `keep-state`: `project.py`'s comment on `GATES` is set by D-30 below. There is no test change. Under `keep-state`, the report states `max_delta_pp` as fit2d's model error.
  - `lower` to L %, plan 5's Task 17 text:
    - `GATES["fit2d_limit"] = L / 100`, with the comment "# P0-A lowered the fit2d limit to L % under plan 6's mesh rule on `<date>` (docs/validation/`<date>`-p0-a.md)".
    - W_GATE_LIMITS' two `0.03` literals become `f"{L / 100:g}"`. Search for `fit2d_limit` and `GATES`, never for `0.03`.
    - One autouse fixture in `tests/conftest.py`: `monkeypatch.setitem(project.GATES, "fit2d_limit", 0.03)`, with `# ponytail: the fixtures were drawn under the 3 % gate; test_the_fit2d_limit_follows_p0a pins the new default`.
    - New test `test_the_fit2d_limit_follows_p0a` in `tests/test_project.py`: `monkeypatch.undo()` first, then `assert GATES["fit2d_limit"] == <L/100> and f"not {<L/100>:g} and 0.8" in CATALOG["W_GATE_LIMITS"]`.
    - `tests/test_cli_new.py::test_new_writes_every_key_and_reads_it_back` compares against `dict(GATES)` (PF-58).
    - B1's project keeps the 3 % gate (Task 4), so B1 still runs.
  - `unpredicted` fails the verdict, so the fail branch applies instead.
- **D-30** (`decisions.dt_floor`, over P0-A's meshes: confirmed iff `min_ratio` ≥ `LIMITS["dt_ratio"]` (0.85) and `stray_trips`; B1's ratio is re-checked in Task 11). The `GATES` comment:
  - When confirmed: "# P0-A confirmed the fit2d limit and the floor on 2026-10-24 and again under plan 6's mesh rule on `<date>` (docs/validation/`<date>`-p0-a.md)".
  - When not confirmed: "# P0-A confirmed the fit2d limit under plan 6's mesh rule on `<date>` (docs/validation/`<date>`-p0-a.md); the dt floor is a stated limit there". The 0.8 floor stays (D-22), and the report states `min_ratio`.
  - `lower` keeps its own first clause and adds the floor clause.
- **D-26, D-28:** report only; both are in the verdict.

- [ ] **Step 1:** Write each fired branch's test, then run it. Expected: FAIL, except for a branch that changes nothing.
- [ ] **Step 2:** Make the code and text changes, then run `python -m pytest -q`. Expected: all pass, with Task 6's 2 xfails.
- [ ] **Step 3: Commit.** `git commit -am "feat: apply P0-A's re-check under plan 6's mesh rule — staircase <branch>, fit2d <branch>, dt floor <confirmed|stated> (D-26..D-30; controller recommendation, owner unavailable)"`, then `graphify update .`.
- [ ] **Step 4: Amendment A-8** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (a spec text change, so no test, as for A-1..A-7):
  - L287 becomes: "at solid-copper edges, lines sit d/4 inside and 3d/4 outside. A slot edge, one that faces metal across a gap of at most 4d, has its inside line `<depth>` deep instead`<gate clause>`, `<scope clause>`, and keeps its outside line 3d/4 out. Its axis keeps the d/4 lines wherever the slot line would fail the edge lint or the d/3 merge. One pre-registered search chose these values over 48 candidates, against plan 2's ratchet of 2142 board rows and 246,064 synthetic axes, and P0-A's FDTD re-check passed on `<date>` (A-8, plan 6: controller recommendation, owner unavailable);". The placeholders:
    - `<depth>` is "d/8 + 3 nm", "9d/64", "5d/32", "d/6", "3d/16" or "5d/24";
    - `<gate clause>` is " where the substrate under the measured nets is at least G·d deep", or nothing for no gate;
    - `<scope clause>` is "in a cell of its own" or "in every cell it serves".
  - L282 becomes: "their reference copper and vias within 6 substrate heights (P0-B raised the reach from 3 on 2026-10-25, D-37) (A-8, plan 6: controller recommendation, owner unavailable);".
  - L673 becomes: "| Protected-set reach, growth threshold (+20 dB) and the k ≤ 0.45 check | P0-B on 2026-10-25: reach 3 h not confirmed, raised to 6 h (D-37; 6 h unchecked against a larger reach, a stated limit); growth not confirmed, a stated limit (D-38); k ≤ 0.45 confirmed (D-39) (A-8, plan 6: controller recommendation, owner unavailable) |".
  - The Status line (L4) gains: "On `<date>`, plan 6's mesh-rule calibration amended §5.4 and §12 (A-8) the same way."
- [ ] **Step 5: Check** that `Select-String -Path docs\superpowers\specs\2026-10-16-stage1-validated-engine-design.md -Pattern "A-8, plan 6"` finds 3 lines, and that `python tools/privacy_gate.py --staged` reports no hit after `git add`.
- [ ] **Step 6: Commit** A-8 alone: `git commit -m "docs(spec): A-8, inside lines by edge role in §5.4 and the reach in §5.4 and §12 (controller recommendation, owner unavailable)"`.
- [ ] **Step 7: Return the report text** (`<date>-p0-a.md`, seven sections), and name `p0a.json` as its JSON.
  1. The verdict.
  2. Inputs: the commit and code, the fresh folder by name only, Normal, n = 2 and 3, `versions`, the calibration, and the winning rule's values.
  3. Measured values: tables A1–A5 from `p0a.md`, and an A0 table that sets Stage 1 against the re-check for each row's `e_fit_pct`, `dz0_pct`, `deeff_pct` and `delta_pp`, and for each twin.
  4. The decisions, marked as in 2026-10-24's report.
  5. Stated limits:
     - plan 5's list (A-1/A-2, KiCad's CPWG bias, the 2D box past the board edge);
     - lpf915 at n 3 stays a stated limit (role (c));
     - D-30's P0-B half is B1's ratio alone, re-checked in Task 11;
     - the guard reverts whole axes;
     - every fix commit made between runs.
  6. Machine time: `predicted_s` against `wall_s`, with loaded steps left out.
  7. The next step: B1 and the regeneration; or, after a revert, Task 11.

### Task 9 [run]: B1 alone at reach 3

- **Before:**
  - Task 8's pass commits are in, and `git status --porcelain` is empty.
  - The date is before 2026-11-19; otherwise apply the ceiling's branch (B1 is not run).
  - Both idle checks print `[0, 0, 0]`.
  - OQ4's hash check:
    1. `.venv\Scripts\python.exe tools\p0d.py models --out <P0-2>\hashcheck --only lpf915`
    2. `.venv\Scripts\python.exe -c "import json,sys,numpy as np; from kicad_rf_studio.core.model.spec import spec_hash; print(spec_hash(json.load(open(sys.argv[1],encoding='utf-8'))) != str(np.load(sys.argv[2])['spec_hash']))" <P0-2>\hashcheck\lpf915.json tests\fixtures\p0d\lpf915.npz`

    The second command is expected to print `True`: lpf915's sections hold slot edges, so its reach-3 model moved. On `False`, B1 is not run: lpf915's old record stands (design §5.1), and Task 10 takes its lpf915 branch.
- **Command:** `.venv\Scripts\python.exe tools\p0b\harness.py --out <P0-2> --only B1`
- **Expected machine time:** about 3.2 h (r4: B1 at reach 3, 3.22 h).
- **Outputs:**
  - `<P0-2>\p0b\projects\B1\project.json`, with `mesh.reach_h` 3.0 and `gates.fit2d_limit` 0.03 (Task 4);
  - `<P0-2>\steps\p0b-B1.json` and its run folder;
  - no `p0b.json`, since the other P0-B steps are not run.
- **Done when:** the command exits 0 and `.venv\Scripts\python.exe -c "import json,sys; sys.path.insert(0,'tools'); import p0; from pathlib import Path; out=p0.enter(Path(sys.argv[1])); r=json.loads((out/'steps'/'p0b-B1.json').read_text(encoding='utf-8')); s=p0.summary(r); print(r['result']['exit'], [j['verdict'] for j in s['jobs']], round(r['wall_s']/3600, 2), r['loaded'], s['dt_ratio'])" <P0-2>` prints `0`, six `converged`, the hours, the loaded flag and B1's dt ratio (Stage 1's B-runs read 1.01–1.065). Any other verdict: B1 is not rerun, since a doubled `t_max_s` enters the model spec and would move lpf915 off the model p0d builds; Task 10 takes its lpf915 branch.

### Task 10 [code]: P0-D's references and the traces from `<P0-2>`

**Files:**
- Modify: `tests/fixtures/p0d/*.npz` (9, or 8 in the lpf915 branch), `tests/fixtures/traces/*.npz` (8, or 2), `tests/test_p0a.py`, `tests/test_p0d_refs.py` (Task 6's marks)

**Interfaces:**
- Consumes: `p0d.references` and `p0d.traces` with Task 4's `--only` (plan 5's Tasks 19 and 20); P0-A's records and `p0b-B1` in `<P0-2>`, read with one `p0.records` call per harness (PF-43).
- Produces: references and traces whose `spec_hash` is the model this code builds.

The lpf915 branch (OQ4 printed False, B1 did not end six converged, or the ceiling fell before B1): every step below leaves `lpf915.npz` and `lpf915-k*.npz` as committed.

- [ ] **Step 1:** Print each committed reference's `spec_hash` (first 8 hex) and `t_cut`, for the report: `.venv\Scripts\python.exe -c "import sys,numpy as np; sys.path.insert(0,'tools'); import p0d; [print(m, str(np.load(f'tests/fixtures/p0d/{m}.npz')['spec_hash'])[:8], np.load(f'tests/fixtures/p0d/{m}.npz')['t_cut']) for m in p0d.MODELS]"`.
- [ ] **Step 2:** Remove Task 6's two `xfail` marks. Run `python -m pytest tests/test_p0a.py tests/test_p0d_refs.py -q`. Expected: FAIL (spec_hash mismatch for the moved models).
- [ ] **Step 3:** Write the fixtures:
  - `python tools/p0d.py references --p0 <P0-2> --out tests/fixtures/p0d`
  - `python tools/p0d.py traces --p0 <P0-2> --out tests/fixtures/traces`

  In the lpf915 branch, add `--only coupon_ms,coupon_ms_masked,coupon_gcpw,coupon_gcpw_masked,coupon_dense,coupon_gcpw_45,coupon_gcpw_arc,coupon_gcpw_pads` to `references` and `--only coupon_gcpw_pads` to `traces`. If `traces` refuses a job that did not converge live, or `p0.save_trace` raises because a job's probe samples alone exceed `p0.TRACE_BYTES` (100,000 B), stop and report.
- [ ] **Step 4:** `git add tests/fixtures/p0d tests/fixtures/traces tests/test_p0a.py tests/test_p0d_refs.py`, then `python tools/privacy_gate.py --staged`. Expected: no hit.
- [ ] **Step 5:** Run `python -m pytest tests/test_p0d_refs.py tests/test_p0a.py tests/test_traces_real.py -q`, then the full suite. Expected: all pass, with no xfail left. In the lpf915 branch, when `test_the_references_are_the_models_p0d_builds_here` fails on lpf915 alone (its model moved, its reference did not), it takes back `@pytest.mark.xfail(strict=True, reason="lpf915's reference predates plan 6's mesh rule: B1 was not rerun on it (stated limit)")`; `test_p0a`'s test still checks the other eight models' hashes. Any other hash that still differs means a commit after P0-A moved a model (only Task 8's lies between, and it touches messages and gates only): stop and report. If `test_traces_real`'s replay misses its live cut, never loosen the bound: stop and report.
- [ ] **Step 6: Commit.** `git commit -m "test: P0-D's references and the traces regenerated from the fresh P0 folder under plan 6's mesh rule (D-48, D-40)"`
- [ ] **Step 7:** Return each reference's `spec_hash` prefix and `t_cut`, old → new, and which branch ran.

### Task 11 [decide]: The calibration report and the README's cost excerpt

**Reads:** `<P0-2>\meshcal\meshcal.json`, `meshcal.md`, `rows\off.jsonl` and `rows\<winner>.jsonl`; the notes returned by Tasks 6, 8 and 10; `<P0-2>\p0a\p0a.json` and Task 9's printed check where they exist; README L48–L57.

- [ ] **Step 1 (only when B1 ran and its dt ratio is under 0.85):** D-30 is then not confirmed over every rule-made P0 mesh. `project.py`'s `GATES` comment takes D-30's "not confirmed" wording, with B1's ratio named. Run the suite, then `git commit -am "docs: the dt floor is a stated limit under plan 6's mesh rule — B1's ratio <r> (D-30; controller recommendation, owner unavailable)"`.
- [ ] **Step 2 (winner and a P0-A pass only):** The controller, on an idle PC with no run in progress, runs these in one PowerShell invocation from the repo root, since `cost` starts openEMS's setup-only worker: `$env:LOCALAPPDATA = "<P0-2>\data"; .venv\Scripts\kicad-rf-studio new tests/fixtures/lpf915.kicad_pcb --start U1.1 --end J1.1 --f0 915MHz --lid-height 2.5 -o <P0-2>\tutorial\lpf915; .venv\Scripts\kicad-rf-studio cost <P0-2>\tutorial\lpf915`. This uses P0-A's calibration and never the per-user data folder. Under D-29's lower branch, the controller first sets `"gates": {"fit2d_limit": 0.03, "dt_floor": 0.8}` in that project.json (plan 5's Task 17), so `cost` prints its W_GATE_LIMITS line. The subagent then edits the README with the printed lines:
  - If the `Cells:` line differs from README L51, replace L51–L53 (Cells, Worst case and RAM) with the printed lines, and under lower add the W_GATE_LIMITS line. The RF_B row (L50) is a 2D readout that the mesh does not move. After that excerpt, add: "Plan 6's mesh rule (spec §5.4, A-8) moved lpf915's lines after P0-B; the run times below are P0-B's."
  - Run `python -m pytest tests/test_repo.py -q`, then commit with `git commit -am "docs: the tutorial's cost excerpt on plan 6's mesh rule"`.
- [ ] **Step 3: Return the calibration report text** (`YYYY-MM-DD-mesh-calibration.md`), and name `meshcal.json` as its JSON.
  1. The verdict: the winner, or "no candidate passed: the rule stays as built"; any struck candidate; P0-A's outcome; whether A-8 landed; whether lpf915's reference was regenerated.
  2. Inputs:
     - the commit and code (`meshcal.json`'s `versions`);
     - r1's harness outside the repo (`<R1>` by its repo-relative path), pinned by sha256;
     - 1061 synthetic boards plus 10 fixtures at n 2 and 3, 2142 rows, reach 6, each board's own top of band (3 GHz but for 14 ms_step boards at 10 and 20 GHz);
     - 246,064 axes at h unset, 2d and 5d;
     - the grid, the guard and the shakedown.
  3. Measured values: `meshcal.md`'s table (one row per candidate: c1–c4, passes, regressions named, families below, GCPW coupon range, `gcpw_max`); the baseline (1966; 24,745 / 24,744 / 24,745); the shakedown's axis regressions; the winner's fixture fit2d against off's, from the two rows files; B1's dt ratio against 0.85; each reference's `spec_hash` prefix and `t_cut`, old → new (Task 10).
  4. Decisions, marked: the winner by condition 5 and any strike, the guard, the harness outside the repo, P0-A's branches, A-8, B1's branch.
  5. Stated limits and deviations:
     - lpf915 and lpf915-45 stay over 3 % at n 3 (the step edge; E_FIT2D_FINE's limit raise remains the remedy);
     - the guard reverts a whole axis;
     - the harness runs at 3 GHz with no lid, about 0.05–0.09 pp below the product's 915 MHz projects;
     - 6 of the 1061 boards have no generator;
     - FDTD checks the rule only through P0-A's coupons and B1;
     - r1's prior probes covered the served scope only;
     - condition 5's second key reads the GCPW coupons, a deviation from §5.1's wording (ruling);
     - lpf915's reference, when Task 10 took its lpf915 branch;
     - every fix commit made between runs.
  6. Machine time: the search's `machine` against about 5 h; P0-A against 3.1 h; B1 against 3.2 h.
  7. The next step: plan 7 (tails, verify's L, the box term, P0-B2).
- [ ] **Step 4 (only when the ceiling applied one of its branches):** return a "## Addendum, `<date>`" for `docs/validation/2026-10-25-stage1-exit.md`, giving plan 6's state, the branch the ceiling applied and its data.

The controller saves the reports, runs the privacy gate, commits them, then decides and merges (design §5.1, step 4).

---

## Not in this plan

- **Plan 7 (design §5.2):**
  - tails on every reported S (G2, A-9);
  - verify's L strips compensated (G3, A-10);
  - the box-term estimator or its registered known difference (A-11);
  - P0-B2 and its pre-registration (G4);
  - P0-D's references again after tails, lpf915's included when Task 10 took its lpf915 branch;
  - the P0-B2 report and its exit-report addendum.
- **Design non-goals (§3):**
  - GUI work, which the Stage 2 spec owns;
  - any limit move outside a pre-registered branch (fit2d 3 %, criterion 1, the stop presets, K_MAX 0.45, T_MAX_S 40 ns, the dt floor, growth);
  - narrowing E_STAIRCASED, previewing a refused box, or any new `project.json` field (O-24);
  - a step-edge role with lint relief: lpf915 and lpf915-45 at n 3 stay a stated limit;
  - running P0-C, which is the owner's step.
- **By the round cap:**
  - a second search, or a candidate chosen any other way than condition 5 and Task 6's strike rule;
  - any parameter outside the grid (IN_open, OUT, dz0, FACE, THIN, SERVE, CUT_SERVE, ALONE, n);
  - the lid faces at reach 6, which plan 5 refused under D-22.
- **Stage 1 evidence, kept as it is:** P0-B's records and reports, and the frozen Stage 1 P0 folder. B2–B6, the K_MAX sweep and EMerge are not rerun.
- **Never committed:**
  - the ratchet harness and its boards, since 6 of the 1061 have no generator;
  - the search's tree and raw outputs, which stay in `<P0-2>\meshcal`.

## Controller rulings (2026-10-26; binding)

The architect's and reviser's rulings, then the controller's. Each is a controller recommendation, owner unavailable.

- Ruling: the ratchet harness stays outside the repo (design 5.1's 'cannot' branch) — the archived generators rebuild 1055 of the 1061 boards, but the 6 ms_pour_vias boards have no generator anywhere in the zip — cost if wrong: none for this search; a later calibration re-extracts the zip.
- Ruling: tools/meshcal.py is committed with the grid, PINNED, the five acceptance conditions and a run loop of p0 steps (p0.enter, p0.step, p0.records, p0.save, p0.machine). Only r1's evaluators and the boards stay outside. There is no decide subcommand, and the module carries a single-use ponytail note — the commit pre-registers the decision rule and the run procedure in tested code, and p0's step machinery gives code keying, resume and atomic records — cost if wrong: about 150 lines of single-use dev tool in the repo.
- Ruling: each evaluation copies src into one shared out/tree, rebuilt per step, with one appended constants line (r1's method), so r1's hrun.py and axes harness run unchanged — the off copy must reproduce r1's frozen all_r6.jsonl and a_head*.json — cost if wrong: about 1 MB of disk.
- Ruling: r1's evaluator and frozen baseline are pre-registered by sha256 in meshcal.PINNED (hrun.py, ax/launch.py, axrun.py, common.py, axes.py, axes2.py, caxes.py, all_r6.jsonl, a_head*.json), and run refuses a missing or changed file before any step — the decision rule is committed but the evaluator lives outside the repo, so without pins it could change after the plan's commit — cost if wrong: a needed harness fix costs a plan amendment before the search.
- Ruling: run checks off's outputs against r1's frozen files right after the off step (rows line by line, axes as parsed dicts) and stops before the shakedown and any candidate — the architect's baseline ruling, now in code instead of a manual check after decide — cost if wrong: a spurious mismatch stops the run after about 5 minutes.
- Ruling: Task 2's axis guard is kept and is part of the searched rule and the pre-registration. The slot depth holds on an axis only where its lines pass the edge lint and the d/3 merge; elsewhere, and after a RuntimeError in the slot pass, the axis keeps the as-built lines. Striking the guard is possible only before the plan's commit — it is needed for condition 2 to be passable (r1's ungated d/6 broke 3168 axes), and with it condition 2 still catches any other exception or a guard/harness disagreement — cost if wrong: struck, the search very likely returns no winner; kept, a slot edge loses its depth along a whole axis wherever one check fails there.
- Ruling: _faults is the lint and the d/3 check only; the RATIO clause is dropped from the code, its docstring and A-8 — _grade only returns lines that pass the ratio with the edges held, and r1's six runs of 246,064 axes show 0 ratio faults — cost if wrong: none; a ratio fault would still show in condition 2.
- Ruling: a shakedown runs before the search. The three axes runs of 1-6_none_served (r1's ungated served d/6) must show 0 axis regressions against off; otherwise run stops before any candidate and Task 2's guard is fixed test-first — a guard/harness mismatch would fail condition 2 for all 48 candidates and spend the one search, and the shakedown sees no fit2d — cost if wrong: about 5 minutes of machine time.
- Ruling: the slot role follows r1's probe exactly: the branch sits after the shallow fallback and before the several-cut-edges pattern; the outside line stays 3d/4 out of the deepest edge; IN_slot = max(SLOT_IN·d, d/8 + GRID_TOL); 'lone' means no other same-side edge within the serve reach (j == k + 1) — r1's measured numbers carry over — cost if wrong: a different reading would not reproduce r1's numbers.
- Ruling: an unset h (math.inf, xy_lines' default) passes every gate — the code's existing default — cost if wrong: none beyond the guard's need.
- Ruling: the constants SLOT_IN (None = off), SLOT_GATE (0.0 = no gate) and SLOT_SERVED (False = lone cells) live in rule.py and are read at call time. Task 1 has no off-by-default test: its unchanged suite and the P0-D hashes prove the role inert. Task 6 pins the winner to the grid's literals with test_the_slot_role_is_plan6s_winner — the smallest switch the tests and the trees can set, plus a check that the constants are exactly the searched candidate — cost if wrong: renaming three constants.
- Ruling: acceptance 1 reads 'passes' as the whole row check (no error, lint 0, ratio 0, d/3 0, every |fit2d| < 3), not fit2d alone — a fixture that trades E_FIT2D for E_EDGE_LINT has not passed — cost if wrong: stricter, never looser; every fixture row passes the other checks today.
- Ruling: acceptance 4's GCPW coupons are coupon_gcpw, coupon_gcpw_masked, coupon_gcpw_pads, coupon_dense and coupon_gcpw_arc, with bounds -1.5 to +1.5 % inclusive; 'microstrip unchanged' means coupon_ms's and coupon_ms_masked's fit2d lists are equal at n 2 and 3 — coupon_gcpw_45 has no section — cost if wrong: a borderline candidate decided differently.
- Ruling: condition 5's second key is the largest |fit2d| over the GCPW coupons' sections at n 2 and 3 (condition 4's set), then the grid's order. This deviates from 5.1's literal 'GCPW families' — over the GCPW-named families' passing rows the key reads 2.971 % in every gated r1 probe, and over all passing gap sections 2.971-2.987 %, so a tie on passes would fall to grid order; over the coupons it reads 1.215, 1.049, 1.728 and 2.408 % for d/8, d/6, 3d/16 and 5d/24 — cost if wrong: only a tie-break changes.
- Ruling: a candidate row or axis that is missing, an error, a ValueError's text or a NaN counts as failed; decide reads p0 records of one code only and refuses a missing record — no winner from partial or mixed data — cost if wrong: none.
- Ruling: the search's outputs live in <P0-2>/meshcal, entered with p0.enter, which refuses a git work tree and holds the lock. run refuses a dirty src, and refuses to start once meshcal.json exists — the search is spent once judged, and a dirty tree would judge uncommitted code — cost if wrong: none.
- Ruling: the run stops at the first failed evaluation, and a rerun resumes from p0's records — a harness failure there is systemic — cost if wrong: one more restart.
- Ruling: from Task 5 to Task 9, a src/ or tools/ commit may only fix a command that exited non-zero, between runs and before that run's meshcal.json or p0a.json exists. It never changes the slot branch, the SLOT_* constants, meshcal's CANDIDATES, PINNED, ok, passes, axis_regressions, accept or choose, or p0a's decide, LIMITS or rows' pass rule. It touches the guard only after a shakedown failure, and the reports name every such commit — this is plan 5's rule plus the pre-registration — cost if wrong: a genuine bug in those pieces ends the search as it stands.
- Ruling: a winner that fails a gate-asserting product test (|fit2d| < 3 %, no lint hit, no cell under d/3, a run not blocked) is struck, and meshcal.choose runs again on meshcal.json's results without it (no new run); with none left, the none branch applies — the rule is pre-registered, no limit moves, and the round cap governs searches, not ties among one search's results; the harness (3 GHz, no lid) cannot see every product case, and 1-8_none_served reads -3.66 % on a pour-following microstrip test — cost if wrong: a few suite runs, or a struck candidate that FDTD would have accepted.
- Ruling: in the none branch (Task 6) and the P0-A fail branch (Task 8), Tasks 1-3 (and 6) are reverted in one commit, after which git diff <plan commit> over core/mesh and the two mesh test files must be empty — ponytail: no dead config, and src is provably back to the rule as built — cost if wrong: about 40 lines to re-add for a future calibration; Task 4 stays either way.
- Ruling: the fail branch fires on p0a's decisions.verdict.value == 'fail' from any cause. The report says 'FDTD rejected the calibration' only when a listed fail is a D-25 row, and lists the any-cause rule as a deviation from 5.1 — p0a.decide's verdict is the pre-registered judgement — cost if wrong: a pad-indicator or mask-shift failure also reverts the rule.
- Ruling: Task 8 judges D-30 over P0-A's meshes (rows and pad) with p0a's own min_ratio and stray_trips, and p0a.decide gets no new flag. Task 9 prints B1's dt ratio and Task 11 re-checks it: under 0.85, the GATES comment's floor clause takes the stated-limit wording in one commit — B1 is a rule-made P0 mesh, so D-30 covers it too — cost if wrong: one comment commit; E_DT_FLOOR at 0.8 guards every run either way.
- Ruling: D-27 has three outcomes in p0a.decide (refuse, advice, keep). Advice is keep's text plus plan 5's n = 3 sentence, with its braces escaped for str.format. The figure comes from the twins row with the largest |dz0_pct|, named '45° line' or 'arc', with its n. The expected outcome is 'not refuse' — the design names only keep and refuse; coupon_gcpw's Z0 falls about 2.5 pp at n 2 under the role, taking the 45-degree twin to about -4.6 %, while the arc's |dz0| may grow at n 3 — cost if wrong: a wording change.
- Ruling: D-29's lower branch stays live despite 3's 'no limit moves', because 5.1 applies D-25..D-30 exactly as plan 5 registered them. B1's project pins gates.fit2d_limit 0.03 (Task 4), and the tutorial project does the same under lower — gates is not in the model spec, so the P0-D lpf915 hash holds, and a lowered default could otherwise block B1 with E_FIT2D — cost if wrong: a stricter gate, never a looser one.
- Ruling: test_cli_cost's failed-fit2d test and test_preview's blocked-gate test are re-pinned rule-independently with half_its_error (half the case's own largest fit2d error, to one significant digit), a helper in test_cli_cost — under d/6 the pad coupon reads about -0.1 %, below any round limit — cost if wrong: two tests compute fit2d themselves.
- Ruling: G1 is held in tier (a) by test_every_fixture_section_passes_the_fit2d_gate over FIXTURES x (2, 3), leaving out lpf915 and lpf915-45 at n 3. It runs on test_mesh_rule's own geometry (3 GHz, no lid, reach 6), so it recomputes condition 1, and it is Task 6's failing test (coupon_gcpw_masked reads 3.768 % at n 2) — about 4 s — cost if wrong: none.
- Ruling: the two hash tests (test_p0a's harness-models test and test_p0d_refs' spec_hash test) carry xfail(strict=True) from Task 6 to Task 10. test_p0d_refs' mark stays only when lpf915 was not regenerated and its hash moved. The trace-replay tests stay green because they replay data only — cost if wrong: none.
- Ruling: Task 4 pins B1, B4 and B5 to p0a.PIN (B2 and B3 follow B1; B6 keeps 6.0), pins B1's gate at 3 %, and gives p0d's references and traces --only, with traces gaining models= — this is r4's and the exit report's ask, plus the lpf915 branch's need to regenerate everything but lpf915 — cost if wrong: about 10 lines of tool code for branches that are unlikely to fire.
- Ruling: OQ4's hash check stays before B1 (design 5.1). On False, B1 is not run, lpf915's reference and its six traces stand as committed, and Task 10 regenerates the other eight references and the two pad traces with --only — the design rules that an unmoved model keeps its record — cost if wrong: nothing expected, since lpf915's sections hold slot edges and its reach-3 hash moved on every candidate a reviewer built.
- Ruling: if B1 does not end six converged, it is not rerun, because t_max_s enters the model spec (excitation.t_max) and OI-6's doubled record would move lpf915 off the model p0d builds. The rule and A-8 stay, Task 10 takes its lpf915 branch, and lpf915's stale reference is a stated limit for plan 7 — P0-A already passed, and reverting it over a CI fixture would discard a validated calibration — cost if wrong: P0-D's lpf915 comparison waits for plan 7's regeneration.
- Ruling: at the ceiling all P0 runs stop, while decide and code tasks on finished runs still follow. Search unfinished: Task 6's none branch. P0-A unfinished under a committed winner: Task 8's fail-branch revert. B1 unfinished after a P0-A pass: Task 10's lpf915 branch. Task 11 then writes the exit-report addendum — the design keeps the rule only after a P0-A pass and wants main green — cost if wrong: a rule reverted for want of time.
- Ruling: A-8 is the last step of Task 8's pass branch, in its own commit, as plan 5's Task 18 did for A-5. It cites P0-A's pass date, not report files; it keeps 'solid-copper'; it calls a slot edge one 'that faces metal across a gap of at most 4d'; and it rewrites 12 L673 with P0-B's actual outcomes (reach raised to 6 h and unchecked beyond, growth a stated limit, k <= 0.45 confirmed) — the calibration report is written after B1, and 'P0-B confirms them' was false for two of the three items — cost if wrong: a wording revision before the owner's review.
- Ruling: the P0-A report is dated the day Task 8 runs and the controller saves it that day; it gets an A0 table setting Stage 1 against the re-check. There is no new P0-D report, but Task 10 returns each reference's spec_hash prefix and t_cut, old to new, for the calibration report — 2026-10-24's report stays as Stage 1 evidence, and the P0-D report's table alone would describe only the old references — cost if wrong: one report more or less.
- Ruling: the README excerpt is regenerated only on a winner with a P0-A pass, and only if the Cells line moved. The controller runs new and cost with LOCALAPPDATA = <P0-2>/data, since cost starts openEMS's setup-only worker, and the subagent replaces L51-L53 (Cells, Worst case, RAM); the RF_B row is a 2D readout the mesh does not move — cost if wrong: a stale tutorial line.
- Ruling: meshcal renders meshcal.md from meshcal.json with p0.table (D-52), and decide loads each candidate's axes files in turn (about 50 MB each in memory, about 7 GB for all at once) — the harnesses render their own tables, and the calibration report copies them — cost if wrong: none.
- Ruling: before Tasks 7 and 9, the idle check also counts meshcal.py, hrun.py and launch.py command lines — p0's markers (worker, emerge_fem, pytest) cannot see the search's 12-process pools — cost if wrong: none.
- Ruling: an exit-report addendum is written only when the ceiling applied one of its branches — the design's timebox rule — cost if wrong: none.
- Ruling: the plan's expected results are predictions. The expected winner is a no-gate candidate at or near d/6 (1-6_none_served at about 2042 passes or more), and every 3d/16 and 5d/24 candidate is expected to fail condition 4 — r1's ungated probes exist, contrary to the draft's 'no prior data', and the guard reverts their d/3 and lint regressions — cost if wrong: a visible surprise, never a rule change.
- Controller ruling (open issue: the axis guard): Task 2's guard stays, as part of the searched rule — the design's "everything else stays as built" fixes the other roles' parameters; the guard defines where the new role applies, and without it condition 2 would very likely reject all 48 candidates — cost if wrong: a slot edge loses its depth along a whole axis wherever any check fails there (a stated limit).
- Controller ruling (open issue: condition 5's second key): it reads the GCPW coupons' sections, because the design's literal key is degenerate (8.855 % in every probe); it only breaks ties — cost if wrong: a tie decided differently.
- Controller ruling (open issue: the P0-A fail branch): it fires on any cause of p0a's pre-registered verdict, not only a D-25 row — stricter than the design, never looser — cost if wrong: a pad-indicator or mask-shift failure also reverts the rule.
- Controller ruling (open issue: the strike rule): a winner that fails a product gate test is struck and the next one is chosen from the same results by condition 5; no test is relaxed and no new search runs — it is pre-registered here, before the search — cost if wrong: a later candidate than the first passing one.
- Controller ruling (disclosure): during this plan's review, one reviewer computed conditions 1 and 4 for all 48 candidates on a scratch tree (condition 1 held for all; condition 4 failed every 3d/16 and 5d/24 candidate). No limit, rule, condition or expectation was changed on that data, and conditions 2 and 3 were not seen. The calibration report states this in section 5 — cost if wrong: none to the decision.
- Controller ruling (setup, done before this commit): branch stage1-plan6 from main 1f0fb3b; r1's harness copied into <R1> with all 11 sha256 equal to meshcal.PINNED; the 1061 boards and all.json extracted into <P0-2>\meshcal\boards.
