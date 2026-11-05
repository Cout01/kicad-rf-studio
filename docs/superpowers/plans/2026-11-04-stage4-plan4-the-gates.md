# Stage 4 Plan 4: The Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run gates P4-B to P4-F on synthetic coupons and the USB 2.0 fixtures against criteria and references committed before any run, write each gate's report with its machine time predicted and measured, and land the SI defaults, the significance thresholds and the cost refit those gates set.

**Architecture:**
- **Product changes first, then a frozen src.** Two code tasks land what the gates need before any run. Task 1 is the SI cost: the Debye fit's four poles, a Debye cell's weight, the SI speed ratio, no calibration level from a run with Debye, and a note for a Debye request on a loss tangent of 0 (rulings D-3, D-4, K-1). Task 2 is the ring rule, under which an SI job runs past T_max while its port residual falls fast enough (T-1, T-2). src is frozen from Task 9's freeze to Task 14's last report. The defaults, thresholds and refit land after it (Tasks 15–17).
- **Stage 3's machinery, one thin tool per gate.** `tools/p4.py` builds on `p0` and `p3`: enter, a base project from `new --interface` and edited variants, resumable run steps keyed by model, preset and code, one-code records. Each project is a board at a mesh n, a mesh rule and a dielectric. Its run is measured in this process: from the run's chain (`pipeline.chain_results`, `core.post.si.read`), with cost's own SI formula for the time and the product's passivity and reciprocity flags for its validity. `tools/p4b.py` to `p4f.py` each hold their steps, a tested `decide()`, a report writer, and a `criteria.json` and `references.json` committed before their runs. Checkpoint decisions live in `p4`'s constants (`N`, `RULE`, `DIELECTRIC`, `EDITS`, `BENDS_N3`) and in project edits, never in src.
- **The FDTD is judged against the same discretised cut.** P4-B's Zdiff, NEXT and FEXT and P4-E's ±d curvature are referred to the 2D solve of the run's own mesh lines (fit2d's coupled cut and its modes); the exact cut, KiCad's calculator and the 50 Ω figures are recorded beside them.

**Tech Stack:**
- Python ≥ 3.11 (venv 3.14.2), numpy, scipy, scikit-rf 2.2 (`MLine`, `renormalize`), shapely. No new dependency.
- openEMS 0.37.0 and CSXCAD 0.7.0, only in the product's workers (Tasks 9–14 run them for real).
- KiCad 9's bundled Python with its isolated profile, in Task 3 alone (ruling G-4).
- pytest, the fake worker (`KRS_FAKE=network`), `tests/test_p0.in_process`; `tools/catalog.py` (Babel, dev extra).

**Spec:**
- **The design, binding:** `docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md`, §5.12 item 4, with §5.3, §5.4, §5.5, §5.8, §5.9, §5.11, §5.13, §6, §7 and §8.
- **The controller's rulings, binding:** `.superpowers/sdd/stage4-plan4-research/controller-rulings.md`, G-1 to G-4, B-1 to B-6, C-1 to C-4, D-1 to D-5, E-1, E-2, F-1 to F-3, T-1, T-2, K-1 and A-1. The research r1–r4 is beside it.
- **The Stage 1 spec**, `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, where the design reuses it: §3.2, §5.3, §5.4, §5.6, §5.8, §6.3, §6.4 and §9; amendments A-1 to A-57. Task 17 lands A-58 to A-64, with their exact text.
- **Plans 1 to 3:** `docs/superpowers/plans/2026-11-02-stage4-plan1-pins-and-si-hooks.md`, `2026-11-03-stage4-plan2-si-project.md` (its Task 1 is the KiCad-Python precedent) and `2026-11-04-stage4-plan3-si-results.md`. Their records are `docs/validation/2026-11-03-p4-a.md`, `2026-11-03-si-first-run.md` and `2026-11-04-si-results.md`, and their carried items are in `.superpowers/sdd/2026-11-0{3,3,4}-stage4-plan{1,2,3}-rulings-and-minors.md`.
- **Stage 3's plan 4,** for the shape of the run and decision tasks: `docs/superpowers/plans/2026-10-30-stage3-plan4-the-gates.md`.

**Branch:** `stage4-plan4`, from `main` at `155652c87f993ae3abe65a929155c5dbec499002`. This plan is `docs/superpowers/plans/2026-11-04-stage4-plan4-the-gates.md`.
- Commands run from the repo root with `.venv/Scripts/python`.
- A path without a folder is under `src/kicad_rf_studio/`.
- Line references are main's at 155652c; find a moved line by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage4-plan4 main`. Then `git diff --stat 155652c HEAD -- src tests tools po pyproject.toml` must print nothing.
2. Commit this plan on the branch.
3. After Task 17: the whole-branch review, a local fast-forward merge into main, and delete the branch. Nothing is pushed.

## Global Constraints

- **v1, the antenna and plan 2 byte for byte** (design §3, §4): `tests/test_golden_v1.py`, `tests/test_golden_antenna.py` and `tests/test_golden_si.py` stay green on every task. golden_si is re-recorded once, in Task 16's second commit and by ruling A-1, only when a default the gates set (n, the mesh rule, the dielectric or the 45° rule) changes `new --interface`'s output, its refusal or the model. A task that otherwise moves a pin is wrong: stop and get a ruling.
- **SI only behind the schema:** every SI branch tests `core.project.si(data)`. A rule on a model spec tests its SI pulse, the excitation's `window_s`, which only `dc_pulse` writes.
- **openEMS stays in the workers** (Stage 1 §3.1). The CLI, the orchestrator, `core.post`, the gate tools and pytest's own process never import openEMS or CSXCAD.
- **The anti-goals stand** (design §3). Every SI result keeps I_SI_RELATIVE and `si_limits`; a level on a short feature keeps its mark; a difference counts only past its threshold. Nothing in this plan removes them.
- **Messages:**
  - every new or changed message is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, compiled by `.venv/Scripts/python tools/catalog.py` in the same task (run it, set the msgstr, run it again), by the pt-BR design's §6 glossary;
  - numbers keep the decimal point, and a msgstr keeps every identifier, option, quoted text and dotted number of its msgid;
  - the gate tools print plain English, and render catalog lines with `core.messages.english`.
- **Tests:**
  - test-first. A guard that passes on main says so in its run step;
  - tier (a) never runs openEMS, KiCad, the network or a build. It uses the fake worker (`calibrated`, `p0_out`, `KRS_FAKE=network`) and the committed fixtures;
  - KrsError tests check `.code` and `.params`;
  - tests never touch a real KiCad folder, the Documents folder, KiCad's settings or the real data folder.
- **Criteria and references before runs** (design §5.11, G-1):
  - each gate's `tests/fixtures/p4<x>/criteria.json` and `references.json` are committed in its tool's task, before any gate run, and a test of that task pins the replica's numbers in them;
  - the tools refuse to overwrite a references file. Before the freeze, and only then, a references file whose "code" is not the frozen code is deleted and written again (Task 9); none is regenerated during the runs;
  - a gate judges against its committed references, never against a figure its tool computes at run time;
  - a pre-registered branch is taken through a `p4` constant set at a checkpoint and recorded as a deviation, never by editing a criteria or references file.
- **src frozen from Task 9's freeze to Task 14's last report** (G-1):
  - `p0.step` keys every record `key@code_id` (`git rev-parse HEAD:src`), and every report goes through `p3.records`, which refuses records of two codes;
  - a src fix between gates is a controller ruling and voids every earlier gate's records;
  - commits during the gates touch tools/, tests/ and docs/ only.
- **One openEMS command at a time** (G-3):
  - each block is one background PowerShell call from Task 10's template, its exit, times and free RAM in `<GATES>\logs\ledger.txt`;
  - free RAM before a block: 12 GB for a block predicted over 1 h, 8 GB for a shorter one, 17 GB for B3′. Exit 9 (under the floor) tells the owner the free RAM, and the block starts again once its floor holds; a floor is never lowered;
  - tell the owner before any block predicted over 2 h, then start it: the owner's standing instruction is the go for every block, a block over 8 h included (the controller's ruling R-1). B3′ alone waits for the owner's go, since only the owner can free its RAM or turn off the reaper's pressure kill;
  - a reaped block is reported and never restarted unasked;
  - a graceful stop is `New-Item "$g\STOP"`, never a STOP file in a run folder, and the controller deletes `$g\STOP` before the next block.
- **The gates folder** `<GATES>` = `$HOME\krs-gates-si`: outside TEMP and every work tree, and apart from Stage 3's `$HOME\krs-gates`. Every call that runs openEMS types `$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"` in the call, never in a file.
- **Full suite before every commit that touches src, tests, tools, po or pyproject.toml:** `.venv/Scripts/python -m pytest -q`, about 26 minutes at 155652c (2256 passed, 6 skipped) and 2–3 more after Task 3. Run it alone, in the background, waited on, and never alongside a block. A commit that touches docs/ only (a report, the spec) reuses the last green suite at the same src, tests and tools, named in the ledger; the pre-commit privacy gate still runs.
- **Git:**
  - no push; the pre-commit privacy gate runs, never `--no-verify`;
  - no commit message carries a co-author line; use the messages as given;
  - no committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name. Write `<openEMS folder>`, `<KiCad 9 bin folder>`, `<GATES>` and `<RUN>`.
- **Files:** every new `.py` starts with `# SPDX-License-Identifier: GPL-3.0-or-later`. Code and docs are in English.
- **Python** only with a script, `-c` or `-m`: never a bare interactive `python`, least of all in a background shell.
- **KiCad's Python:** only Task 3 runs KiCad 9's bundled Python, by its exact command (G-4). Never KiCad itself, kicad-cli or the owner's profile.
- **Workflow:** `graphify query "<question>"` before reading code, and `graphify update .` after each commit.
- **Ponytail:** reuse `p0` (enter, cli, cli_run, step, records, summary, save, table, versions, machine, edit, model_key, run_path, predicted_s), `p3` (enter, variant, run_step, records, run_steps), `p4a.even_odd_s` and `cohn`, `core.post.si` (read, arrival, si_deltas, compare_verify, db, uniform_grid, mixed_mode), `core.post.checks` (SIGMA_LIMIT, RECIP_LIMIT), `pipeline.chain_results`, `core.post.waves.layout`, `core.mesh.gates.fit2d`, `core.cs2d.pair`, `core.geometry.sections.sections`, `core.model.spec.cell_split`, `make_fixtures`' helpers, and scikit-rf's MLine and renormalize. Put a `ponytail:` comment on each corner cut with a known ceiling.
- **Prototype numbers:** this plan's numbers from the architect's in-memory probes, and those marked as the physics review's replica, stop the task when the code misses them; report both values and the formula. The probes are a text replica of each coupon read through the product's importer, the 2D table, fit2d and the cell counts. The coupons' cells may differ by ±10 % and their dt references by ±5 %; the 2D table's and fit2d's Ω must match to ±0.02.

## Review Focus

1. **A step resumed after its run folder was half written:** a reaped shell, a reboot or a kill mid-run.
   - Expected: the step leaves no record and runs again from scratch, in a new run folder; the dead run's project lock is reclaimed (W_STALE_LOCK), and the orphaned folder is named in the report.
   - Check: Task 4's `test_an_interrupted_step_leaves_no_record_and_runs_again`; each run task's checkpoint names orphaned folders.
2. **A run with Debye refreshing the calibration's level.** D-16 stores each run's speed as its level; a Debye run's is slowed by its serial update, so the next cost would count the Debye weight twice, or a lossless model R times too long.
   - Expected: a run whose spec holds a Debye material refreshes no level.
   - Check: Task 1's `test_a_debye_run_leaves_the_calibrations_levels`.
3. **Two runs whose fingerprints differ by design:** the terminated victim (6 ports) against the cut one (4). `p4.deltas` refuses them, as compare would.
   - Expected: the victim case reads the pair's own 4-port block and calls `si_deltas` directly, with the victim's crosstalk from its own reading.
   - Check: Task 5's `test_the_victim_case_reads_the_pairs_own_block`.
4. **The ring rule on a residual that is flat, rising or slow, on a v1 or antenna pulse, and while the residual's window still holds the pulse at T_max.**
   - Expected: such a job ends at T_max as today, its line at its cut; a v1 or antenna job never meets the rule; a job falling fast enough runs on, at most to 4 × T_max.
   - Check: Task 2's `test_the_ring_rule_runs_on_while_the_residual_falls_fast_enough`, `test_an_si_job_whose_planes_ring_slowly_ends_at_t_max_and_a_v1_one_never_by_the_ring` and `test_a_job_the_ring_rule_ends_reads_where_its_s_ends`; Block 0's 2 ns Debye run.
5. **A default the gates set that moves a pin outside the task that sets it:** golden_si's usb2_hs_45 under the 45° branches, test_si_run's fingerprint pair, new's λ/40 cell and dielectric in older tests.
   - Expected: Task 16 lists each branch's pins and greps for the rest first; plan 4's own fixture tests pin their settings.
   - Check: Task 16 Step 1; Task 3's `built()`.

The stripline FEXT reference, the ±d curvature, a plateau shorter than one rise time and a src change mid-gates are pinned by Tasks 5, 8 and 4's tests and the Global Constraints.

---

## File structure

```
core/model/spec.py (DEBYE_POLES, debye, debye_cells); runs.py (DEBYE_WEIGHT, SI_SPEED, calibrated_mcs); pipeline.py
  (load's note, cost_notes, prepare, cost, simulate's level refresh); messages, po, .mo; tests/test_model_spec.py,
  test_si_model.py, test_si_cost.py, test_model_ports.py, test_cost_model.py, test_si_run.py                     # T1
stoprule.py (RING_*, ring, ceiling, stop_rule); pipeline.py (run_ports, basis_lines, cost_notes); messages, po, .mo;
  tests/fixtures/ring/plane_gap.json; tests/test_stoprule.py, test_si_run.py, test_si_cost.py                    # T2
tools/make_fixtures.py; tests/fixtures/<22 boards>.{kicad_pcb,pads.json}; tests/test_p4_fixtures.py (new),
  test_fixtures.py, test_pads.py, test_stackup.py                                                                 # T3
tools/p4.py (new), tools/p3.py (prefix, make); tests/test_p4.py (new)                                             # T4
tools/p4b.py, tests/fixtures/p4b/{criteria,references}.json, tests/test_p4b.py                                   # T5
tools/p4c.py, tests/fixtures/p4c/{criteria,references}.json, tests/test_p4c.py                                   # T6
tools/p4d.py, tests/fixtures/p4d/{criteria,references}.json, tests/test_p4d.py                                   # T7
tools/p4e.py, tools/p4f.py, tests/fixtures/p4{e,f}/{criteria,references}.json, tests/test_p4e.py, test_p4f.py    # T8
references regenerated before the freeze when stale                                                               # T9
docs/validation/<date>-p4-{b,c,d,e,f}.{md,json}; tools/p4.py constants at checkpoints                             # T10–T14
docs/validation/<date>-p4-refit.{md,json}; runs.py; tests                                                          # T15
core/post/si.py, core/project.py, core/geometry/region.py, cli.py, tools/golden_si.py, messages, po; the tests
  Task 16 lists per branch; tests/fixtures/golden_si.json by ruling                                               # T16
the Stage 1 spec (A-58 to A-64), the Stage 4 design (§5.8, Status)                                                # T17
```

---

### Task 1 [code]: The SI cost: four Debye poles, a Debye cell's weight, the SI speed ratio, and no level from a Debye run

**Files:** Modify `core/model/spec.py` (`DEBYE_DECADES` L177, `debye` L180–204; add `DEBYE_POLES`, `debye_cells`), `runs.py` (add `DEBYE_WEIGHT` beside `PML_WEIGHT`, L36; add `SI_SPEED` and `calibrated_mcs` after `small_speed`, L462), `pipeline.py` (`load` L91–111, `cost_notes` L215–264, `prepare` L267–291 and its callers `cost` and `simulate`, `simulate`'s level refresh L968–974), `core/messages.py`, `po/pt_BR.po` and the `.mo`. Test: `tests/test_model_spec.py`, `tests/test_si_model.py`, `tests/test_si_cost.py`, `tests/test_model_ports.py`, `tests/test_cost_model.py`, `tests/test_si_run.py`.

**Interfaces:**
- Consumes: `spec.cell_split`; `core.kicad.stackup.Stackup.from_json`; `runs.per_job_mcs`; `cli._port`, `ports.si_reference`, `copper_pieces`, `zstack`, `classify`; `test_cli_si.si_project`, `QSPI`.
- Produces:
  - `spec.DEBYE_POLES = (-2.2, -1.4, -0.6, 0.2)`: the poles at f_max·10^e; `spec.debye(eps_r, tan_d, f_max) -> dict`, now with four poles; `spec.debye_cells(spec: dict) -> int`;
  - `runs.DEBYE_WEIGHT = 6.8`, `runs.SI_SPEED = 0.55` and `runs.calibrated_mcs(entry: dict, k: int) -> float`;
  - `pipeline.prepare(model, emit, run_dir=None, *, small=False, si=False)`;
  - the codes W_SI_DEBYE_NO_LOSS {layers}, I_SI_COST_DEBYE {mcells, weight, poles} and I_SI_COST_SPEED {ratio}.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_model_spec.py`: the imports gain `DEBYE_POLES`. `test_a_debye_fit_holds_the_loss_tangent_across_the_band_and_none_at_dc` becomes:

```python
@pytest.mark.parametrize(("eps_r", "tan_d", "tol"), [(4.3, 0.02, 0.035), (3.66, 0.004, 0.03)])  # FR-4; a low-loss one
def test_a_debye_fit_holds_the_loss_tangent_across_the_band_and_none_at_dc(eps_r, tan_d, tol):  # design 5.3; D-3
    d = debye(eps_r, tan_d, 10e9)
    assert DEBYE_POLES == (-2.2, -1.4, -0.6, 0.2)  # four poles 0.8 decade apart, 0.2 decade past each band edge
    assert d["f_relax_hz"] == pytest.approx([10e9 * 10 ** e for e in DEBYE_POLES])
    assert all(v > 0 for v in d["delta"]) and 1 <= d["eps_inf"] < eps_r  # no negative pole, nothing below vacuum
    e = debye_eps(d, np.geomspace(1e8, 1e10, 401))
    assert np.abs(-e.imag / e.real / tan_d - 1).max() <= tol  # measured 3.2 % and 2.5 % (three poles: 6.0, 4.9 %)
    assert debye_eps(d, np.array([DEBYE_F_REF]))[0].real == pytest.approx(eps_r, rel=0.005)
    assert debye_eps(d, np.array([0.0]))[0].imag == 0.0  # no κ: no DC loss
    low = debye_eps(d, np.array([1e5]))[0]
    assert -low.imag / low.real <= 0.01 * tan_d
```

  - `tests/test_si_model.py`: the imports gain `math`, `debye_cells`. Add:

```python
def test_a_debye_models_cells_are_its_substrates_nodes(usb, tmp_path):  # ruling D-4: the cost's weight
    pj = si_project(tmp_path / "d")
    save_project(pj, {**load_project(pj), "dielectric": "debye"})
    project, board, geom, _ = pipeline.load(pj)
    spec = pipeline.build_model(project, board, geom).spec
    assert (debye_cells(spec), math.prod(len(spec["mesh"][a]) for a in "xyz")) == (582291, 2072070)  # share 0.281
    assert debye_cells(usb[2].spec) == 0  # lossless: no Debye material


def test_a_debye_request_on_a_loss_tangent_of_0_runs_that_layer_lossless_and_says_so(tmp_path):  # ruling D-4
    pj = si_project(tmp_path / "d")
    data = {**load_project(pj), "dielectric": "debye"}

    def tan_3(tan):  # dielectric 3, the bottom prepreg, at this loss tangent
        return [{**x, "loss_tangent": tan} if x["name"] == "dielectric 3" else x for x in data["stackup"]["layers"]]
    save_project(pj, {**data, "stackup": {**data["stackup"], "layers": tan_3(0.0)}})
    project, board, geom, notes = pipeline.load(pj)
    assert ("W_SI_DEBYE_NO_LOSS", {"layers": "dielectric 3"}) in notes
    subs = [m for m in pipeline.build_model(project, board, geom).spec["materials"] if m["name"].startswith("substrate")]
    assert [m["name"] for m in subs if "debye" not in m] == ["substrate_0"]  # In2.Cu's slab keeps the mean, 0.01
    for tan, dielectric in ((None, "debye"), (0.0, "lossless")):  # None reads KiCad's 0.02; lossless fits nothing
        save_project(pj, {**data, "dielectric": dielectric, "stackup": {**data["stackup"], "layers": tan_3(tan)}})
        assert "W_SI_DEBYE_NO_LOSS" not in dict(pipeline.load(pj)[3])
```

  - `tests/test_si_cost.py`: the imports gain `runs` and `load_project`, `save_project`. Add, and give `test_the_si_cost_lists_the_2d_table_and_the_runs` `assert dict(ev)["I_SI_COST_SPEED"] == {"ratio": f"{runs.SI_SPEED:g}"}`:

```python
def test_a_debye_models_cost_counts_its_cells_at_their_weight(tmp_path):  # design 5.9; ruling D-4
    setup = {"dt": 1e-13, "node": [0, 1, 2, 3]}
    pj = si_project(tmp_path / "d")
    save_project(pj, {**load_project(pj), "dielectric": "debye"})
    project, board, geom, _ = pipeline.load(pj)
    notes = dict(pipeline.cost_notes(pipeline.build_model(project, board, geom), project, setup, 8, 2, 100.0))
    assert runs.DEBYE_WEIGHT == 6.8  # r1's five-pole probe, until the refit (Task 15)
    assert notes["I_SI_COST_DEBYE"] == {"mcells": "0.58", "weight": f"{runs.DEBYE_WEIGHT:g}", "poles": 4}
    weighted = 2072070 + (runs.DEBYE_WEIGHT - 1) * 582291
    assert notes["I_COST_TIME"]["time"] == pipeline.duration(4 * weighted * (9e-9 / 1e-13) / 100e6)  # 8 runs, 2 at once
    p, b, g, _ = pipeline.load(si_project(tmp_path / "l"))
    assert "I_SI_COST_DEBYE" not in dict(pipeline.cost_notes(pipeline.build_model(p, b, g), p, setup, 8, 2, 100.0))
```

  - `tests/test_model_ports.py`: the imports gain `from kicad_rf_studio.cli import _port`. Add (plan 2's carried item):

```python
def test_an_si_ends_point_reference_within_reach_is_kept():  # plan 2's carried item; Stage 4 design 5.5
    b = load_board(FIX / "coupon_gcpw_pads.kicad_pcb")
    c, zs = classify(b), zstack(b.stackup, b.copper_layers)
    pieces, _ = copper_pieces(b, b.outline, {s.copper: round(s.z1 - s.z0, 6) for s in zs if s.copper})
    p = _port(b, c, "P1", "TP1.1")
    assert p["rule"] == "copper" and p["reference"] == {"point": [100.0, 100.6505], "layer": "F.Cu"}
    assert si_reference(b, c, pieces, zs, "P1", "TP1.1", p["reference"], 4.26) == p["reference"]  # 6 h of 0.71 mm
    assert si_reference(b, c, pieces, zs, "P1", "TP1.1", p["reference"], 0.1) == {"plane": "B.Cu"}
```

  - `tests/test_cost_model.py` (the imports gain `prepare` where missing):

```python
def test_the_calibrations_own_per_job_speed_is_what_no_run_refreshes():  # ruling K-1
    entry = {"threads": 2, "pool": 2, "aggregate_mcs": 400.0, "single": {"2": 180.0}}
    assert [runs.calibrated_mcs(entry, k) for k in (1, 2, 4)] == [180.0, 200.0, 200.0]  # single[threads] at one job
    assert runs.calibrated_mcs({**entry, "single": {}}, 1) == 200.0
    fresh = {**entry, "levels": {"2": 200.0, "1": 180.0}}  # the levels runs.calibrate stores with it
    assert all(runs.per_job_mcs(fresh, k) == runs.calibrated_mcs(fresh, k) for k in (1, 2, 4))
    assert runs.SI_SPEED == 0.55  # plan 2's and plan 3's runs, until the refit (Task 15)


def test_an_si_models_speed_is_si_speed_until_a_run_measures_its_level(calibrated):  # ruling K-1
    lines = np.linspace(0.0, 9.0, 10)
    m = Model(Mesh(lines, lines, lines, 1.0, 0.4, {}, {}), {"ports": [{"part": False}]}, [], 1.5e-12)
    said = []
    assert prepare(m, lambda c, p: said.append((c, p)), si=True) == (2, 1, pytest.approx(200.0 * runs.SI_SPEED))
    assert said == [("I_SI_COST_SPEED", {"ratio": f"{runs.SI_SPEED:g}"})]
    assert prepare(m, lambda *_: None) == (2, 1, 200.0)
    settings = runs.load_settings()
    settings["machines"][runs.machine_key()]["levels"] = {"1": 150.0}  # a run at one job measured it
    runs.save_settings(settings)
    said.clear()
    assert prepare(m, lambda c, p: said.append((c, p)), si=True) == (2, 1, 150.0) and said == []
```

  - `tests/test_si_run.py`: the imports gain `runs` where missing. Add:

```python
def test_a_debye_run_leaves_the_calibrations_levels(tmp_path, calibrated, monkeypatch):  # D-4, D-16; Review Focus 2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "d", QSPI)
    save_project(pj, {**load_project(pj), "dielectric": "debye"})
    assert pipeline.run(pj) == 0
    assert "levels" not in runs.load_settings()["machines"][runs.machine_key()]  # a Debye cell's speed is no plain one's
    save_project(pj, {**load_project(pj), "dielectric": "lossless"})
    assert pipeline.run(pj) == 0
    assert runs.load_settings()["machines"][runs.machine_key()]["levels"] == {"2": 100.0}  # the fake's 5e7 a thread
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_model_spec.py tests/test_si_model.py tests/test_si_cost.py tests/test_cost_model.py "tests/test_si_run.py::test_a_debye_run_leaves_the_calibrations_levels" "tests/test_model_ports.py::test_an_si_ends_point_reference_within_reach_is_kept" -q`. Expected: FAIL with `cannot import name 'DEBYE_POLES'` and `'debye_cells'`, `AttributeError: ... 'calibrated_mcs'`, `prepare() got an unexpected keyword argument 'si'`, `KeyError: 'I_SI_COST_DEBYE'` and a `levels` key after the Debye run. The point test passes on main: it is a guard on plan 2's code.
- [ ] **Step 3: `core/model/spec.py`.**
  - `DEBYE_DECADES = 2` stays, as the fit's band, f_max/100 to f_max. Add `DEBYE_POLES = (-2.2, -1.4, -0.6, 0.2)`, commented "the poles at f_max·10^e: four, 0.8 decade apart and 0.2 past each edge of the fit's band (Stage 4 plan 4 ruling D-3: three spent 86 % of P4-D's 5 % budget against MLine, four 33 %)".
  - `debye`: `poles = [f_max * 10 ** e for e in DEBYE_POLES]`, `f = np.geomspace(f_max / 10 ** DEBYE_DECADES, f_max, 61)`; the rest is unchanged. Its docstring says "four poles, f_max·10^−2.2 to f_max·10^0.2, fitted on 61 log-spaced points from f_max/100 to f_max". The ponytail becomes `# ponytail: four poles ripple tan δ by 3.2 % on FR-4 (three: 6 %); gate P4-D measures their cell weight`.
  - `debye_cells(spec)`: `cell_split({**spec, "materials": debye})[0]` over the materials that hold "debye", 0 without one: "the nodes inside the box of the Debye materials' solids, as cost counts cells". Mark it `# ponytail: the box of every Debye solid, which on a board crop is the crop itself; per-solid counts if a stack has Debye cut-outs`.
- [ ] **Step 4: `runs.py` and `pipeline.py`.**
  - `runs.py`:
    - `DEBYE_WEIGHT = 6.8`, commented "a Debye cell's cost in plain cells (Stage 4 design 5.9): r1's five-pole probe at 4 threads, provisional until gate P4-D measures it at the calibration's threads (openEMS 0.37 updates Debye materials on one thread)".
    - `SI_SPEED = 0.55`, commented "an SI model's speed over the calibration's own per-job speed (Stage 4 plan 4 ruling K-1): plan 2's and plan 3's runs read 0.517–0.573; provisional until the gates' refit".
    - `calibrated_mcs(entry, k)`: "The per-job MC/s that `entry`'s calibration itself gives k jobs at once, which runs.calibrate stores as its levels before any run refreshes one (D-16): single[threads] at one job when it was timed, else aggregate/pool."
  - `load`: after the geometry's notes, an SI project whose `dielectric` is "debye" adds `("W_SI_DEBYE_NO_LOSS", {"layers": ", ".join(names)})` when `names` is not empty: the stackup's layers of kind "dielectric" whose `loss_tangent` reads 0 through `Stackup.from_json(project["stackup"])`. The docstring says a loss tangent the board leaves out reads KiCad's 0.02 (`Layer.__post_init__`), so only 0 runs lossless.
  - `cost_notes`: for an SI spec with Debye cells, `weighted = cells + (runs.DEBYE_WEIGHT - 1) * n`, n = `debye_cells(model.spec)`, set where the antenna's weight is set. After I_SI_COST_JOBS it adds `("I_SI_COST_DEBYE", {"mcells": f"{n / 1e6:.2f}", "weight": f"{runs.DEBYE_WEIGHT:g}", "poles": len(DEBYE_POLES)})`, marked `# ponytail: the registered pole count; the fit drops a pole that fits 0, so a material may hold fewer`. Delete the ponytail "a Debye cell counts as a plain one until gate P4-D measures its weight". The docstring names both.
  - `prepare(..., si=False)`: after the per-job speed is read, `if si and mcs == runs.calibrated_mcs(entry, pool)`: `mcs *= runs.SI_SPEED` and `emit("I_SI_COST_SPEED", {"ratio": f"{runs.SI_SPEED:g}"})`. `cost` and `simulate` pass `si=si(project)`. The docstring says the ratio applies until a run at that level measures it.
  - `simulate`'s refresh reads `if speeds and not antenna(project) and not debye_cells(model.spec):`, commented "a Debye cell's speed is no plain one's: a run with Debye refreshes no level (Stage 4 plan 4 ruling D-4)". The docstring says so.
- [ ] **Step 5: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| W_SI_DEBYE_NO_LOSS | The Debye dielectric needs a loss tangent above 0, and the stackup gives {layers} a loss tangent of 0, so they run lossless. Set their loss tangent in KiCad's board setup, or set "dielectric": "lossless" in project.json. | O dielétrico de Debye precisa de uma tangente de perdas acima de 0, e o empilhamento dá a {layers} uma tangente de perdas de 0, então elas rodam sem perdas. Defina a tangente de perdas delas na configuração da placa do KiCad, ou defina "dielectric": "lossless" no project.json. |
| I_SI_COST_DEBYE | Cells: {mcells} M in the Debye dielectric, {poles} poles each; the time counts each such cell as {weight} cells. | Células: {mcells} M no dielétrico de Debye, {poles} polos em cada uma; o tempo conta cada uma dessas células como {weight} células. |
| I_SI_COST_SPEED | This signal-integrity model's speed is taken as {ratio} × the calibration's per-job speed, the measured ratio of SI models to the calibration's uniform one, until a run with this many jobs at once measures it. | A velocidade deste modelo de integridade de sinal é tomada como {ratio} × a velocidade por tarefa da calibração, a razão medida entre modelos de SI e o modelo uniforme da calibração, até que uma execução com esse número de tarefas simultâneas a meça. |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_model_csx.py tests/test_run.py tests/test_sexpr.py -q`. Expected: PASS. golden_si's specs are lossless, so they do not move.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(si): the SI cost, four Debye poles past the band's edges, a Debye cell's weight and its cost line, 0.55 of the calibration's per-job speed until a run measures its level, no level from a run with Debye, and a note for a Debye request on a loss tangent of 0 (Stage 4 design 5.3, 5.9; plan 4 rulings D-3, D-4, K-1)"
graphify update .
```

---

### Task 2 [code]: The ring rule

**Files:**
- Modify: `stoprule.py` (constants after `LAG_S` L18, `ring`, `ceiling`, `stop_rule` L66–91, `Verdict`'s docstring); `pipeline.py` (`run_ports` L978–1034, `basis_lines` L587–597, `cost_notes`); `core/messages.py`, `po/pt_BR.po` and the `.mo`.
- Create: `tests/fixtures/ring/plane_gap.json`.
- Test: `tests/test_stoprule.py`, `tests/test_si_run.py`, `tests/test_si_cost.py`.

**Interfaces:**
- Consumes: Task 1's cost lines; `stoprule.residual_db`, `PRESETS`; `core.project.GATES_SI`; plan 3's zip, `.superpowers/sdd/2026-11-04-stage4-plan3-si-results.zip` (git-ignored, present).
- Produces:
  - `stoprule.RING_FIT_S = 3e-9`, `RING_SLOPE = -0.3e9` (dB/s), `RING_CEILING = 4`;
  - `stoprule.ring(t: np.ndarray, r_db: np.ndarray, level: float, t_max: float) -> float` and `stoprule.ceiling(exc: dict) -> float`;
  - `pipeline.basis_lines` giving each flagged job at its cut when it has one;
  - the code I_SI_COST_RING {ceiling_ns, time}.

- [ ] **Step 1: The fixture.** Extract the 14 plane-gap jobs that ran past T_max as a path-free JSON in one call. Write the script to `$env:TEMP\krs-ring.py` and run it with `.venv\Scripts\python.exe "$env:TEMP\krs-ring.py" .superpowers\sdd\2026-11-04-stage4-plan3-si-results.zip tests\fixtures\ring\plane_gap.json`:

```python
import json, sys, zipfile
from pathlib import Path
z, out, jobs = zipfile.ZipFile(sys.argv[1]), Path(sys.argv[2]), []
for run in ("gap-run-32ns", "gap-verify-32ns"):  # the 9 ns run's 8 jobs end at T_max: nothing past it to test
    rows, ends = {}, {}
    for line in z.read(f"2026-11-04-stage4-plan3-si-results/evidence/{run}.events.jsonl").decode().splitlines():
        e = json.loads(line)
        if e["code"] == "I_PROGRESS" and float(e["params"]["t_ns"]) >= 6.0:
            rows.setdefault(e["params"]["port"], []).append((float(e["params"]["t_ns"]), float(e["params"]["residual_db"])))
        elif e["kind"] == "verdict" and e["job"]:
            ends[e["params"]["port"]] = float(e["params"]["t_ns"])
    jobs += [{"run": run.removeprefix("gap-"), "port": p, "t_ns": [t for t, _ in r if t <= ends[p]],
              "residual_db": [x for t, x in r if t <= ends[p]]} for p, r in rows.items()]
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"source": "Stage 4 plan 3's usb2_hs_gap: its rerun and its verify at 32 ns, each job's "
                                     "I_PROGRESS t_ns and residual_db from 6 ns to its verdict, as the events printed "
                                     "them", "t_max_s": 9e-9, "level_db": -60.0, "jobs": jobs}) + "\n",
               encoding="utf-8", newline="\n")
```

  Expected: 14 jobs (8 + 6), about 85 KB, and no path in it.
- [ ] **Step 2: Write the failing tests.**
  - `tests/test_stoprule.py`: the imports gain `json`, `Path`, and `RING_CEILING, ceiling, ring` from stoprule. Add, after `F_MAX`:

```python
RING = json.loads((Path(__file__).parent / "fixtures" / "ring" / "plane_gap.json").read_text(encoding="utf-8"))
SI9 = dc_pulse(F_MAX, 9e-9, 2e-9)  # T_max 9 ns: its ceiling 36 ns


def decay(slope_db_ns, dt=0.04e-9):  # a residual from 6 to 40 ns, -45 dB at 9 ns
    t = np.arange(6e-9, 40e-9, dt)
    return t, -45.0 + slope_db_ns * 1e9 * (t - 9e-9)


def test_the_ring_rule_runs_on_while_the_residual_falls_fast_enough():  # ruling T-2; Review Focus 4
    t, r = decay(-1.0)  # -60 dB at 24 ns, under the ceiling
    assert ring(t, r, -60.0, 9e-9) == math.inf
    for slope in (-0.5, -0.2, 0.0, 0.3):  # -60 dB at 39 ns, past the ceiling; slower than 0.3 dB/ns; flat; rising
        t, r = decay(slope)
        assert ring(t, r, -60.0, 9e-9) == t[np.argmax(t >= 9e-9)]  # T_max, as today
    assert ring(t[t < 9e-9], r[t < 9e-9], -60.0, 9e-9) == math.inf  # nothing past T_max yet
    assert RING_CEILING == 4 and ceiling(SI9) == pytest.approx(36e-9) and ceiling({**EXC, "t_max": 5e-9}) == 5e-9


def test_the_ring_rule_lets_every_plane_gap_job_run_to_its_convergence():  # ruling T-2: plan 3's 14 jobs past T_max
    assert len(RING["jobs"]) == 14
    for job in RING["jobs"]:  # slopes -0.68 to -2.09 dB/ns, the latest projection 23.9 ns
        t, r = np.array(job["t_ns"]) * 1e-9, np.array(job["residual_db"])
        assert (t >= RING["t_max_s"]).sum() >= 300, (job["run"], job["port"])
        assert ring(t, r, RING["level_db"], RING["t_max_s"]) == math.inf, (job["run"], job["port"])


def tail(slope_db_ns, dt=2e-12, t_end=12e-9):
    """SI9's pulse on port 1, then a level on it falling `slope_db_ns` dB/ns from -40 dB at 2 ns: a ringing plane."""
    t_u = np.arange(0, t_end, dt)
    pulse = np.exp(-(2 * math.pi * F_MAX * t_u / 3 - 3) ** 2) * (t_u < 2 * SI9["t0"])
    level = 10 ** ((-40 + slope_db_ns * 1e9 * (t_u - 2e-9)) / 20) * (t_u > 2 * SI9["t0"])
    zero = np.zeros_like(t_u)
    return Records(t_u, np.array([pulse + level, zero]), t_u + dt / 2, np.array([pulse, zero]) / Z0, t_u,
                   np.ones_like(t_u))


def test_an_si_job_whose_planes_ring_slowly_ends_at_t_max_and_a_v1_one_never_by_the_ring():  # T-2; Review Focus 4
    v = stop_rule(tail(-0.25), 0, "normal", SI9)  # 0.25 dB/ns: slower than 0.3, and 1.25 dB over 5 ns, not flat
    assert v.kind == "t_max" and v.t == pytest.approx(9e-9, abs=2e-12)
    assert stop_rule(tail(-1.0), 0, "normal", SI9) is None  # fast enough: it runs on toward 36 ns
    v1 = {key: SI9[key] for key in ("f1", "f2", "t0", "t_max", "expr")}  # no window_s: no SI pulse
    assert stop_rule(tail(-0.25), 0, "normal", v1) is None
```

  - `tests/test_si_run.py`: the imports gain `json`, `Path` and `GATES_SI`. Add:

```python
def test_an_si_runs_jobs_may_run_to_four_times_t_max(tmp_path, calibrated, monkeypatch):  # ruling T-2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    job = json.loads((Path(d["results"]["run_dir"]) / "job-1-P1" / "job.json").read_text(encoding="utf-8"))
    assert job["t_max"] == pytest.approx(4 * d["t_max_s"])


def test_a_job_the_ring_rule_ends_reads_where_its_s_ends():  # ruling T-2: its S is cut at T_max, its last sample later
    jobs = [{"port": p, "verdict": v, "t_cut": cut, "t_stop": stop, "residual_db": -48.0}
            for p, v, cut, stop in (("P1", "t_max", 9e-9, 9.31e-9), ("P2", "t_max", None, 9e-9),
                                    ("P3", "flat", 7e-9, 7.4e-9))]
    lines = pipeline.basis_lines({"jobs": jobs, "run_dir": "R", "preset": "normal", "gates": GATES_SI}, GATES_SI)
    assert [(c, p["t_ns"]) for c, p in lines[1:4]] == [("W_JOB_T_MAX", "9.00"), ("W_JOB_T_MAX", "9.00"),
                                                       ("W_JOB_FLAT", "7.00")]
```

  - `tests/test_si_cost.py`: `test_the_si_cost_lists_the_2d_table_and_the_runs` adds `assert dict(ev)["I_SI_COST_RING"]["ceiling_ns"] == "36"`.
- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_stoprule.py "tests/test_si_run.py::test_an_si_runs_jobs_may_run_to_four_times_t_max" "tests/test_si_run.py::test_a_job_the_ring_rule_ends_reads_where_its_s_ends" "tests/test_si_cost.py::test_the_si_cost_lists_the_2d_table_and_the_runs" -q`. Expected: FAIL with `cannot import name 'ceiling'`, the job's t_max at 9e-9, the ring job's line at 9.31 ns and `KeyError: 'I_SI_COST_RING'`.
- [ ] **Step 4: The code.**
  - **`stoprule.py`:**
    - Constants, commented "an SI job past T_max (Stage 4 plan 4 ruling T-2)": `RING_FIT_S = 3e-9`, `RING_SLOPE = -0.3e9` (dB/s), `RING_CEILING = 4`.
    - `ceiling(exc)`: "The simulated time a job of the excitation `exc` may run to: RING_CEILING × T_max for an SI pulse (one with "window_s"), else its T_max."
    - `ring`, as given, since its edges are the rule:

```python
def ring(t: np.ndarray, r_db: np.ndarray, level: float, t_max: float) -> float:
    """The first t at or past `t_max` where the residual `r_db` (dB, on `t`, s) over its last RING_FIT_S, fitted by a
    least-squares line, does not project `level` by RING_CEILING·t_max: its slope above RING_SLOPE (falling slower
    than 0.3 dB/ns, flat or rising) or its crossing later than that; inf while it does, or before t_max (Stage 4 plan 4
    ruling T-2, read as a fit renewed at every sample: an SI job whose planes ring runs on, the stop rule's converged
    verdict ending it)."""
    # ponytail: a polyfit per sample past T_max; cumulative sums if polls lag on long records
    # ponytail: T-2's 3 ns fit; a route whose window_s passes 3 ns can read its held peak as flat and end at T_max, as
    # before; fit over window_s + 1 ns if such a route rings
    lo = np.searchsorted(t, t - RING_FIT_S, "right")
    for n in np.flatnonzero(t >= t_max):
        tt, rr = t[lo[n]:n + 1], r_db[lo[n]:n + 1]
        ok = np.isfinite(rr)
        if ok.sum() < 2:
            return float(t[n])
        b, a = np.polyfit(tt[ok], rr[ok], 1)
        if b > RING_SLOPE or t[n] + (level - (a + b * t[n])) / b > RING_CEILING * t_max:
            return float(t[n])
    return math.inf
```

    - `stop_rule`: `found` gains `"t_max": ring(rec.t_u, r_db, level, exc["t_max"]) if "window_s" in exc else np.inf`, after "flat", so a tie goes to the earlier kinds. The docstring and `Verdict`'s name the kind "t_max", an SI pulse's verdict at or past T_max.
  - **`run_ports`:** `t_max = ceiling(exc) if t_max is None else t_max`. The docstring says an SI job's openEMS runs to the ceiling, and the stop rule ends it at T_max unless the residual falls fast enough.
  - **`basis_lines`:** each flagged job's `t_ns` is its `t_cut` when it has one, else its `t_stop`: "where its S ends". The `end` map goes.
  - **`cost_notes`:** an SI project adds `("I_SI_COST_RING", {"ceiling_ns": f"{RING_CEILING * t_max * 1e9:g}", "time": duration(seconds(RING_CEILING * t_max))})` after I_SI_COST_DEBYE's place. W_SI_LONG_RUN keeps reading the worst case to T_max, since only planes that ring run past it.
  - The ceiling is not in the model spec, so no spec hash moves, golden_si included.
- [ ] **Step 5: The message,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_SI_COST_RING | A job whose port residual still falls by 0.3 dB/ns or more at T_max, fast enough over its last 3 ns to reach the preset's level by {ceiling_ns} ns, runs on while it keeps doing so, until it converges: up to {time}. | Uma tarefa cujo resíduo nas portas ainda cai 0.3 dB/ns ou mais em T_max, rápido o bastante nos últimos 3 ns para chegar ao nível da predefinição até {ceiling_ns} ns, continua enquanto mantiver esse ritmo, até convergir: até {time}. |

- [ ] **Step 6: Run them again.** Step 3's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_run.py tests/test_si_run.py tests/test_sexpr.py -q`. Expected: PASS. The network fake now synthesises its records to 4 × T_max: tests/test_si_run.py's time may grow by at most 1 min against main's; more is a ruling.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(si): an SI job runs past T_max while its port residual falls fast enough to reach the preset's level by four times T_max, its line at its cut (Stage 4 design 5.4, 5.9; plan 4 rulings T-1, T-2)"
graphify update .
```

---

### Task 3 [code]: The coupons and P4-E's variants

**Files:**
- Modify:
  - `tools/make_fixtures.py` (after `qspi_clk` L447; BOARDS L526–551; `main` L605–620);
  - `tests/test_fixtures.py` (NAMES), `tests/test_pads.py` (`test_pads_match_pcbnew`'s parametrize), `tests/test_stackup.py` (`test_every_fixture_board_carries_its_generators_stackup`).
- Create: `tests/test_p4_fixtures.py`. Written by the tool: `tests/fixtures/<board>.kicad_pcb` and `.pads.json` for the 22 boards below.

**Interfaces:**
- Consumes: `place`, `track`, `via`, `zone`, `rect`, `planes`, `new_board`, `save`, `QFN`, `W_PAIR`, `GAP`, `W_SE`, `STACKUP`, `STACKUP_4L`; `cli.main`, `pipeline.load`, `build_model`, `si_readout`.
- Produces:
  - in `make_fixtures`: `STACKUP_SL`, `STACKUP_2L16`, `W100, S100, W75, W35 = 0.25, 0.28, 0.125, 0.61`, `D_SI, D_SI3 = 0.1, 0.066667`, `TP1MM`, and the builders `pair_coupon`, `stripline`, `l_pair`, `step_line`, `pad_coupon`, `tall_coupon`, `line100`;
  - in `tests/test_p4_fixtures.py`: `P4_NEW: dict[str, list[str]]` (each board's `new` arguments, which `tools/p4.py` imports as golden_si imports `si_args`), `ESTIMATE`, `LINES`, `built(tmp_path, board, **edits)` and the module fixture `build`.
- The boards. All are on STACKUP_4L, except p4b_sl90 (STACKUP_SL) and si_pad_coupon_tall (two layers, 1.6 mm):
  - P4-B: p4b_ms90, p4b_ms100, p4b_sl90, p4b_ms90_45, p4b_ms100_45, p4b_ms90_vic and p4b_ms90_cut;
  - P4-C: p4c_l90, p4c_step75 and p4c_step35;
  - P4-D: si_pad_coupon, si_pad_coupon_tall and si_line100;
  - P4-E at n 2 (d = 0.1 mm): p4e_shift, p4e_gapp, p4e_gapm, p4e_null and p4e_vshift (p4b_ms90_vic shifted one fine cell: NEXT's and FEXT's noise, the controller's ruling on open issue 10);
  - P4-E at n 3 (d = 0.066667 mm): p4e_shift3, p4e_gapp3, p4e_gapm3 and p4e_vshift3. They are generated now, so the n 3 branch never needs KiCad's Python again (G-4).

- [ ] **Step 1: Write the failing tests.**
  - NAMES and `test_pads_match_pcbnew`'s list gain the 22 boards.
  - `test_every_fixture_board_carries_its_generators_stackup`'s four-layer branch reads `path.stem.startswith(("usb2_hs", "qspi_clk", "p4", "si_")) and path.stem != "si_pad_coupon_tall"`. The tall coupon takes the two-layer branch: dielectric = thickness − 0.09 = 1.51.
  - `tests/test_p4_fixtures.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import functools
import json
import math

import pytest
import shapely

from kicad_rf_studio import pipeline
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_si import FIX

PAIR90 = ["--start", "TP1.1", "--end", "TP2.1", "--interface", "usb2-hs", "--pair-with", "TP3.1:TP4.1"]
NET = ["--start", "TP1.1", "--end", "TP2.1", "--interface", "se50"]
USB = ["--start", "J1.3", "--end", "U1.3", "--interface", "usb2-hs", "--pair", "--victim", "TP1.1:TP2.1"]
P4_NEW = {**{b: PAIR90 for b in ("p4b_ms90", "p4b_ms90_45", "p4b_ms90_cut", "p4b_sl90", "p4c_l90", "p4e_shift",
                                 "p4e_gapp", "p4e_gapm", "p4e_null", "p4e_shift3", "p4e_gapp3", "p4e_gapm3")},
          **{b: [*PAIR90, "--victim", "TP5.1:TP6.1"] for b in ("p4b_ms90_vic", "p4e_vshift", "p4e_vshift3")},
          **{b: [*PAIR90[:5], "100base-tx", *PAIR90[6:]] for b in ("p4b_ms100", "p4b_ms100_45")},
          **{b: NET for b in ("p4c_step75", "p4c_step35", "si_pad_coupon_tall", "si_line100")},
          "si_pad_coupon": ["--start", "U1.11", "--end", "U2.3", "--interface", "se50"],
          **{b: USB for b in ("usb2_hs", "usb2_hs_neck", "usb2_hs_gap")}}
# the architect's text replica through the product (cells at n 2 with new's max_cell, dt reference in s): ±10 %, ±5 %
ESTIMATE = {"p4b_ms90": (1369368, 9.0894e-14), "p4b_ms100": (1339954, 8.9893e-14), "p4b_sl90": (3008907, 7.8319e-14),
            "p4b_ms90_45": (10122497, 8.6984e-14), "p4b_ms100_45": (9934463, 8.7257e-14),
            "p4b_ms90_vic": (1571724, 8.8960e-14), "p4b_ms90_cut": (1374758, 9.0894e-14),
            "p4c_l90": (1686608, 8.3873e-14), "p4c_step75": (1955330, 5.9104e-14), "p4c_step35": (1414490, 8.2747e-14),
            "si_pad_coupon": (1201200, 8.0901e-14), "si_pad_coupon_tall": (435418, 1.1064e-13),
            "si_line100": (1216138, 9.3604e-14), "p4e_shift": (1375374, 9.0888e-14), "p4e_gapp": (1351812, 9.2521e-14),
            "p4e_gapm": (1647052, 6.6392e-14), "p4e_null": (1369368, 9.0888e-14), "p4e_shift3": (1375374, 9.0888e-14),
            "p4e_gapp3": (1316700, 9.6952e-14), "p4e_gapm3": (1502732, 8.0539e-14),
            "p4e_vshift": (1578600, 8.8954e-14), "p4e_vshift3": (1578600, 8.8954e-14)}  # vic's, scaled as shift's
LINES = {}  # Step 6: each board's (nx, ny, nz, max_cell_mm) at n 2, recorded once from the generated boards


def built(tmp_path, board, **edits):
    """The board's project by `new` with P4_NEW's arguments, at the gates' first settings (mesh n 2, lossless, LINES'
    λ/40 cell once recorded), so a default Task 16 moves leaves it as it is, then `edits` (mesh keys), and its model."""
    assert main(["new", str(FIX / f"{board}.kicad_pcb"), *P4_NEW[board], "-o", str(tmp_path / board)]) == 0
    pj = tmp_path / board / "project.json"
    d = load_project(pj)
    d["mesh"] |= {"n": 2, **({"max_cell_mm": LINES[board][3]} if board in LINES else {}), **edits}
    save_project(pj, {**d, "dielectric": "lossless"})
    project, board_, geom, notes = pipeline.load(pj)
    return project, board_, geom, notes, pipeline.build_model(project, board_, geom)


@pytest.fixture(scope="module")
def build(tmp_path_factory):
    """built() once a board for the module, at the gates' first settings."""
    return functools.cache(lambda board: built(tmp_path_factory.mktemp(board), board))


@pytest.mark.parametrize("board", sorted(ESTIMATE))
def test_each_p4_board_builds_unblocked_near_its_estimate(build, board):  # G-4: the schedule's real cells
    *_, model = build(board)
    lines = (len(model.mesh.x), len(model.mesh.y), len(model.mesh.z))
    cells, (estimate, dt) = math.prod(lines), ESTIMATE[board]
    assert model.blocked == [] and abs(cells / estimate - 1) <= 0.10 and abs(model.dt_ref / dt - 1) <= 0.05
    assert LINES.get(board, lines)[:3] == lines


def test_the_coupons_hit_their_targets_in_the_2d_table(build):  # B-1, C-3, D-1: set through the product's table
    want = {"p4b_ms90": 90.25, "p4b_ms100": 99.81, "p4b_sl90": 90.27, "p4b_ms90_vic": 90.21, "p4e_gapp": 95.17,
            "p4e_gapm": 81.04}
    for board, z in want.items():
        project, b, geom, _, _ = build(board)
        rows = [p for c, p in pipeline.si_readout(b, geom, project) if c == "I_SI_2D_PAIR" and p["length_mm"] == "60.000"]
        assert len(rows) == 2 and all(float(p["z_diff"]) == pytest.approx(z, abs=0.02) for p in rows), board
    for board, z in {"p4c_step75": 75.07, "p4c_step35": 34.94, "si_pad_coupon": 49.96, "si_line100": 51.96,
                     "si_pad_coupon_tall": 48.32}.items():
        project, b, geom, _, _ = build(board)
        lines = {float(p["z0"]) for c, p in pipeline.si_readout(b, geom, project) if c == "I_SI_2D_LINE"}
        assert any(v == pytest.approx(z, abs=0.02) for v in lines), board  # the steps' leads read 49.96


def test_the_ports_take_the_kinds_the_gates_compare(build):  # B-1, D-1
    want = {"p4b_ms90": {"plane"}, "p4b_sl90": {"copper"}, "si_pad_coupon": {"ic"}, "si_pad_coupon_tall": {"copper"},
            "si_line100": {"plane"}, "p4b_ms90_vic": {"plane"}}
    for board, rules in want.items():
        assert {q["rule"] for q in build(board)[0]["ports"]} == rules, board
    assert [c for c, _ in build("p4b_ms90_45")[3]].count("W_STAIRCASED") == 2  # each leg's staircased diagonal


def test_p4es_variants_move_one_thing(build):  # E-1: the shift, the gap ± d, the null edit
    def centres(name):
        return {v["name"]: v["center"] for v in json.loads((FIX / f"{name}.pads.json").read_text(encoding="utf-8")).values()}
    for name, d, of in (("p4e_shift", 0.1, "p4b_ms90"), ("p4e_shift3", 0.066667, "p4b_ms90"),
                        ("p4e_vshift", 0.1, "p4b_ms90_vic"), ("p4e_vshift3", 0.066667, "p4b_ms90_vic")):
        c, base = centres(name), centres(of)
        assert all(abs(c[k][0] - base[k][0] - d) <= 1e-6 and abs(c[k][1] - base[k][1] + d) <= 1e-6 for k in base)
    base = centres("p4b_ms90")
    assert centres("p4e_gapp") == centres("p4e_gapm") == base  # the jogs take the gap's change
    a, b = build("p4b_ms90")[2], build("p4e_null")[2]
    for key in {(p.layer, p.net) for p in a.pieces}:
        pa, pb = (shapely.union_all([p.polygon for p in g.pieces if (p.layer, p.net) == key]) for g in (a, b))
        assert pa.symmetric_difference(pb).area <= 1e-9, key  # the split adds no copper
```

  `p4e_null`'s spec hash is not pinned: the replica's moved by sub-micron mesh rounding, and P4-E decides by it at run time.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_fixtures.py tests/test_pads.py tests/test_stackup.py tests/test_p4_fixtures.py -q`. Expected: FAIL with `FileNotFoundError` on the new boards.
- [ ] **Step 3: `tools/make_fixtures.py`, the builders.** Add after `qspi_clk`:

```python
# Stage 4's gate coupons (design 5.11; plan 4 rulings B-1, C-1, C-3, D-1, E-1): a pair's legs D+ and D- (D+ at y
# 100 + p, KiCad's y down), each from a 1 mm test pad at y 100 ± 1 through a 2 mm lead and a jog to the coupled run
STACKUP_SL = """(stackup
 (layer "F.SilkS" (type "Top Silk Screen")) (layer "F.Paste" (type "Top Solder Paste"))
 (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01)) (layer "F.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 1" (type "prepreg") (thickness 0.25) (material "FR4") (epsilon_r 4.3) (loss_tangent 0.02))
 (layer "In1.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 2" (type "prepreg") (thickness 0.25) (material "FR4") (epsilon_r 4.3) (loss_tangent 0.02))
 (layer "In2.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 3" (type "core") (thickness 0.94) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "B.Cu" (type "copper") (thickness 0.035)) (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
 (layer "B.Paste" (type "Bottom Solder Paste")) (layer "B.SilkS" (type "Bottom Silk Screen"))
 (copper_finish "None") (dielectric_constraints no))
"""  # GND, the pair between 0.25 mm of εr 4.3 on each side (b 0.535, homogeneous), GND, then the core: 1.6 mm (B-1)
STACKUP_2L16 = STACKUP.replace("(thickness 0.71)", "(thickness 1.51)")  # KiCad's two layers at 1.6 mm
W100, S100, W75, W35 = 0.25, 0.28, 0.125, 0.61  # 99.81 Ω, 75.07 Ω and 34.94 Ω in the product's 2D table, mask on
D_SI, D_SI3 = 0.1, 0.066667  # one fine cell of p4b_ms90 at mesh n 2 and n 3: min(w, s, h)/n
TP1MM = "TestPoint:TestPoint_Pad_1.0x1.0mm"


def pair_coupon(b, w=W_PAIR, s=GAP, diag=0.0, aux=None, shift=0.0, split=False):
    """P4-B's coupled microstrip pair (ruling B-1): TP1 (98, 101) to TP2 on D+, TP3 (98, 99) to TP4 on D-, coupled
    60 mm from x 100 to 160 at `w` and `s`; with `diag` a 45° up-diagonal that long between 15 mm straight runs at
    constant pitch; `aux` "vic" a 0.2 mm AUX 0.625 mm off D+ from TP5 (110, 101.15) to TP6 (150, 101.15), "cut" the
    same AUX run on through jogs at x 110 and 150 to y 104 and out to the outline, unported; `shift` adds (shift,
    shift) to every coordinate, the outline's and the planes' included; `split` makes each coupled run two collinear
    tracks meeting at x 130."""
    p = (w + s) / 2
    t, d = p * math.tan(math.pi / 8), round(diag / math.sqrt(2), 4)
    xe, ye = (130 + d, 100 - d) if diag else (160, 100)  # the coupled run's far end, on the centre line
    box = (80, 82, 180, 118) if aux else (94, 70, 160, 106) if diag else (94, 94, 166, 106)

    def at(*xy):
        return tuple(v + shift for v in xy)

    for name, k, near, far in (("D+", 1, "TP1", "TP2"), ("D-", -1, "TP3", "TP4")):
        y = 100 + k * p
        mid = [(115 + k * t, y), (115 + k * t + d, y - d)] if diag else [(130, y)] if split else []
        path = [(98, 100 + k), (100, 100 + k), (100, y), *mid, (xe, ye + k * p), (xe, ye + k), (xe + 2, ye + k)]
        track(b, name, w, *(at(*q) for q in path))
        place(b, TP1MM, near, "TP", at(98, 100 + k), 0, {"1": name})
        place(b, TP1MM, far, "TP", at(xe + 2, ye + k), 0, {"1": name})
    if aux == "vic":
        for ref, x in (("TP5", 110), ("TP6", 150)):
            place(b, TP1MM, ref, "TP", at(x, 101.15), 0, {"1": "AUX"})
        track(b, "AUX", 0.2, at(110, 101.15), at(150, 101.15))
    elif aux == "cut":
        track(b, "AUX", 0.2, *(at(*q) for q in ((box[0] + 0.5, 104), (110, 104), (110, 101.15), (150, 101.15),
                                                 (150, 104), (box[2] - 0.5, 104))))
    box = (*at(box[0], box[1]), *at(box[2], box[3]))
    rect(b, pcbnew.Edge_Cuts, *box)
    planes(b, box)
```

  In `pair_coupon` the diagonal runs from x 115 + k·t; `xe` is 115 + d + 15. The other builders, each with a docstring naming its ruling:
  - **`stripline(b)`** (B-1): D+ and D- on In1.Cu at 0.18 mm and 0.25 mm, pair_coupon's straight path.
    - At each lead's pad end there is a through via (`via(b, at, name)`) under a TP1MM pad on F.Cu: TP1 (98, 101), TP2 (162, 101), TP3 (98, 99), TP4 (162, 99).
    - GND vias stand at (96.5, 99), (96.5, 101), (163.5, 99), (163.5, 101), (98, 96.8), (98, 103.2), (162, 96.8) and (162, 103.2).
    - The outline is (94, 94, 166, 106). F.Cu and In2.Cu get GND zones over (94.5, 94.5)–(165.5, 105.5) at `clearance=0.5`: the pads' port gap, and the vias' antipads.
    - The replica's fit2d read at most 2.68 % at n 2 and 2.34 % at n 3; at 0.15 mm it read 3.1 % and blocked.
  - **`l_pair(b)`** (C-1): for k = +1 (D+, TP1 then TP2) and −1 (D-, TP3 then TP4), the leg runs through (98, 100 + k), (100, 100 + k), (100, 100 + k·p), (120 + k·p, 100 + k·p), (120 + k·p, 80), (120 + k, 80) and (120 + k, 78). Its pads are at (98, 100 + k) and (120 + k, 78). The outline is (94, 74, 126, 106), with `planes`.
  - **`step_line(b, w_mid)`** (C-3): LINE from TP1 (98, 100) at W_SE to x 136, then `w_mid` to x 172, then W_SE to TP2 (210, 100). The leads are 38 mm with the pads' 2 mm, and the middle is 36 mm. The outline is (94, 94, 214, 106), with `planes`.
  - **`pad_coupon(b)`** (D-1): QFN "MCU"s U1 at (100, 100) on pin 11 and U2 at (152.925, 99.5) on pin 3. Each is `{pin: "LINE", "16": "+3V3", "17": "GND"}`, with four GND vias at ±0.45 mm around its centre. LINE runs at W_SE from (101.4625, 99.79) to (151.4625, 99.79), its top edge on the pins'. The outline is (94, 94, 159, 106), with `planes`.
  - **`tall_coupon(b)`** (D-1): `TestPoint:TestPoint_Pad_3.0x3.0mm` TP1 (100, 100) and TP2 (140, 100) on LINE, with a 2.9 mm LINE between them. `TestPoint:TestPoint_Pad_1.5x1.5mm` TP3 (97.25, 100) and TP4 (142.75, 100) are on GND, each with a GND via at its centre. The outline is (94, 94, 146, 106), with a B.Cu GND zone over (94.5, 94.5)–(145.5, 105.5).
  - **`line100(b)`** (D-1): TP1 (98, 100) to TP2 (198, 100) at W_SE. The outline is (94, 94, 202, 106), with `rect(b, pcbnew.F_Mask, *box, filled=True)`: the mask is open, as scikit-rf's MLine has none. It has `planes`.
  - **BOARDS gains:**
    - `"p4b_ms90": pair_coupon`, `"p4b_ms100": lambda b: pair_coupon(b, W100, S100)`, `"p4b_sl90": stripline`;
    - `"p4b_ms90_45": lambda b: pair_coupon(b, diag=33.0)` and `"p4b_ms100_45"` likewise at W100, S100;
    - `"p4b_ms90_vic"` and `"p4b_ms90_cut"` (`aux=`);
    - `"p4c_l90": l_pair`, `"p4c_step75": lambda b: step_line(b, W75)`, `"p4c_step35"` at W35;
    - `"si_pad_coupon": pad_coupon`, `"si_pad_coupon_tall": tall_coupon`, `"si_line100": line100`;
    - `"p4e_shift"` (`shift=D_SI`), `"p4e_gapp"` (`s=GAP + D_SI`), `"p4e_gapm"` (`s=GAP - D_SI`), `"p4e_null"` (`split=True`), `"p4e_vshift"` (`aux="vic", shift=D_SI`), and `"p4e_shift3"`, `"p4e_gapp3"`, `"p4e_gapm3"`, `"p4e_vshift3"` at D_SI3.
  - **`main`:** `STACKS = {"p4b_sl90": (4, 1.6, STACKUP_SL), "si_pad_coupon_tall": (2, 1.6, STACKUP_2L16)}`. A name in STACKS takes its own; one starting with `("usb2_hs", "qspi_clk", "p4", "si_")` takes `(4, 1.6, STACKUP_4L)`; the rest KiCad's default. The docstring says so.
- [ ] **Step 4: Generate only the new boards, under A-3's isolation,** in one PowerShell call. This is the plan's one KiCad-Python exception (G-4); never start KiCad, kicad-cli or the owner's profile:

```powershell
$kp = Join-Path (Get-Location) 'build\kicad-profile'; New-Item -ItemType Directory -Force $kp | Out-Null
Get-ChildItem env: | Where-Object { $_.Name -like 'KICAD*' } | ForEach-Object { Remove-Item "env:$($_.Name)" }
if (Test-Path env:TMPDIR) { Remove-Item env:TMPDIR }
$env:APPDATA = $kp; $env:LOCALAPPDATA = $kp  # the script itself points KICAD_*_HOME, TEMP and TMP at $kp
& "<KiCad 9 bin folder>\python.exe" tools/make_fixtures.py tests/fixtures p4b_ms90 p4b_ms100 p4b_sl90 p4b_ms90_45 p4b_ms100_45 p4b_ms90_vic p4b_ms90_cut p4c_l90 p4c_step75 p4c_step35 si_pad_coupon si_pad_coupon_tall si_line100 p4e_shift p4e_gapp p4e_gapm p4e_null p4e_vshift p4e_shift3 p4e_gapp3 p4e_gapm3 p4e_vshift3
"exit $LASTEXITCODE"; git status --short tests/fixtures
```

  Expected: `exit 0`, and `git status` lists exactly the 44 new files. Any other change stops the task: the golden pins hash the existing boards.
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_board.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_repo.py -q`. Expected: PASS.
  - **A board outside its band, or a 2D target missed by more than 0.02 Ω:** report BLOCKED with both values, for a ruling.
  - **A board blocked by E_FIT2D or E_FIT2D_FINE at no more than 5 %:** p4b_sl90 and p4c_step75 are the replica's thinnest, at 2.68 % and 2.86 %. Record it for Task 4's `p4.EDITS`, `{"gates.fit2d_limit": 0.05}` (Stage 3's ruling 2), and pin that block in the first test.
  - **Any other block:** stops the task for a ruling.
- [ ] **Step 6: Pin the generated boards' lines and λ/40 cells.** Print them in one call, with LOCALAPPDATA and XDG_DATA_HOME at an empty folder under `$env:TEMP` in the same call: `.venv/Scripts/python -c "import sys, tempfile; sys.path[:0] = ['tests']; from pathlib import Path; import test_p4_fixtures as t; d = Path(tempfile.mkdtemp()); print({b: (len(m.mesh.x), len(m.mesh.y), len(m.mesh.z), p['mesh']['max_cell_mm']) for b in sorted(t.ESTIMATE) for p, *_, m in [t.built(d, b)]})"`. Write the dict into `LINES`, then run Step 2's command again. Expected: PASS. They are recorded once, from the boards themselves.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add tools/make_fixtures.py tests/test_fixtures.py tests/test_pads.py tests/test_stackup.py tests/test_p4_fixtures.py tests/fixtures/p4b_* tests/fixtures/p4c_* tests/fixtures/p4e_* tests/fixtures/si_pad_coupon* tests/fixtures/si_line100.*
git commit -m "test(fixtures): the gates' coupons, 90 and 100 ohm microstrip pairs and their 45 degree twins, a homogeneous coupled stripline, a victim terminated and cut, an L-shaped pair, two step lines, two pad coupons and a 100 mm line, and P4-E's shifted (with and without the victim), gap-moved and split variants at n 2 and 3, from KiCad's own footprints (Stage 4 design 5.11; plan 4 rulings B-1, C-1, C-3, D-1, E-1, G-4)"
graphify update .
```

---

### Task 4 [code]: The gates' shared runner, `tools/p4.py`

**Files:** Create `tools/p4.py` and `tests/test_p4.py`. Modify `tools/p3.py`: `step_id` L78, `run_step` L83 and `variant` L63.

**Interfaces:**
- Consumes:
  - `p0.enter`, `cli`, `cli_run`, `step`, `summary`, `save`, `table`, `run_path`, `predicted_s`, `FIX`, `ROOT`;
  - `p3.enter`, `variant`, `run_step`, `records`, `run_steps`;
  - `pipeline.chain_results`, `load_project`, `si_deltas`, `read`, `checks.SIGMA_LIMIT`, `RECIP_LIMIT`, `runs.per_job_mcs`, `calibrated_mcs`, `SI_SPEED`, `DEBYE_WEIGHT`, `spec.debye_cells`, `readers.read_stats`;
  - `test_p4_fixtures.P4_NEW`.
- Produces:
  - in `p3`: `step_id(name, command, prefix="p3")`, `run_step(out, name, command="run", prefix="p3")`, `variant(out, name, board, edits, make=base)`;
  - in `p4`:
    - `N: int = 2`, `RULE: str = "l40"` (or "l80", "dfill"), `DIELECTRIC: str = "lossless"`, `EDITS: dict[str, dict] = {}`, `BENDS_N3: str = "pending"` (or "declined");
    - `enter(out) -> Path`, `base(out, board) -> Path`;
    - `name(board, n=None, rule=None, dielectric=None, tag="") -> str` and `settings(base: dict, n=None, rule=None, dielectric=None) -> dict`;
    - `project(out, board, n=None, rule=None, dielectric=None, tag="", extra=None) -> tuple[str, Path]`;
    - `run_step(out, name) -> dict` and `records(out, ids) -> list[dict]`;
    - `plateau(r: Reading, t0: float, t1: float) -> float | None` and `reading(pj: Path, project: dict) -> tuple[Reading | None, str | None]`;
    - `measure(out, name) -> dict | None` and `plain(m: dict) -> dict`;
    - `deltas(a: dict, b: dict) -> list[dict]` and `predicted_s(spec, dt, t, pool, jobs, entry) -> float`;
    - `rows(out) -> list[dict]`, `refit(rows) -> dict`, `refit_record(out, w, dest) -> dict`;
    - `run_steps` (p3's);
  - in `tests/test_p4.py`: the fixture `gates`.

- [ ] **Step 1: Write the failing tests,** `tests/test_p4.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
import subprocess
import sys

import pytest
from scipy.constants import c as C0

import p0
import p4
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.post.si import Reading, read
from kicad_rf_studio.core.project import load_project
from test_p0 import in_process
from test_post_si import F, SE, line_s


@pytest.fixture
def gates(p0_out, monkeypatch):
    """p0_out entered as <GATES>: the CLI in this process on the network fake, no other process seen, and the gates'
    own checkpoint constants kept out."""
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    for key, value in (("N", 2), ("RULE", "l40"), ("DIELECTRIC", "lossless"), ("EDITS", {}), ("BENDS_N3", "pending")):
        monkeypatch.setattr(p4, key, value)
    return p4.enter(p0_out)


def test_a_run_step_runs_the_product_once_and_measures_it(gates, monkeypatch):  # G-1; design 5.11
    name, pj = p4.project(gates, "p4b_ms90")
    assert name == "p4b_ms90-n2-l40" and load_project(pj)["mesh"]["n"] == 2
    record = p4.run_step(gates, name)
    assert record["step"] == "p4-p4b_ms90-n2-l40-run" and record["result"]["exit"] == 0
    monkeypatch.setattr(p0, "cli_run", lambda *a: pytest.fail("a recorded step ran again"))
    assert p4.run_step(gates, name) == record
    m = p4.measure(gates, name)
    assert (m["pool"], m["cal_mcs"], m["speeds_mcs"], m["debye_cells"]) == (2, 200.0, [100.0] * 4, 0)
    assert isinstance(m["reading"], Reading) and m["reading_error"] is None and m["valid"] is True
    events = [json.loads(x) for x in (p0.run_path(m["run_dir"]) / "events.jsonl").read_text("utf-8").splitlines()]
    cost = {e["code"]: e["params"] for e in events if e["kind"] == "cost"}
    assert cost["I_COST_TIME"]["time"] == pipeline.duration(m["worst_s"])  # cost's SI formula, SI_SPEED applied
    assert not {"reading", "project"} & set(p4.plain(m)) and json.dumps(p4.plain(m))


def test_the_settings_follow_the_checkpoint_constants(gates, monkeypatch):  # G-1: decisions in tools constants
    base = load_project(p4.base(gates, "p4b_ms90"))
    cell = base["mesh"]["max_cell_mm"]
    assert p4.settings(base) == {"mesh.n": 2, "mesh.max_cell_mm": cell, "dielectric": "lossless"}
    monkeypatch.setattr(p4, "N", 3)
    monkeypatch.setattr(p4, "RULE", "l80")
    assert p4.settings(base) == {"mesh.n": 3, "mesh.max_cell_mm": round(cell / 2, 6), "dielectric": "lossless"}
    assert p4.settings(base, rule="dfill", dielectric="debye")["mesh.max_cell_mm"] is None
    assert p4.name("si_line100", dielectric="debye", tag="v") == "si_line100-n3-l80-debye-v"
    monkeypatch.setattr(p4, "EDITS", {"p4b_sl90": {"gates.fit2d_limit": 0.05}})
    assert load_project(p4.project(gates, "p4b_sl90")[1])["gates"]["fit2d_limit"] == 0.05


def test_an_interrupted_step_leaves_no_record_and_runs_again(gates, monkeypatch):  # G-3; Review Focus 1
    name, pj = p4.project(gates, "p4c_step35")
    real = p0.cli_run

    def reaped(*a):  # the shell reaped mid-run: cli_run raises, so p0.step stores nothing
        raise RuntimeError("reaped")

    monkeypatch.setattr(p0, "cli_run", reaped)
    with pytest.raises(RuntimeError):
        p4.run_step(gates, name)
    assert not (gates / "steps" / f"p4-{name}-run.json").exists() and p4.measure(gates, name) is None
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()  # the dead run's project lock, its pid gone: runs.project_lock reclaims it (W_STALE_LOCK)
    lock = pj.with_name("project.json.lock")
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    monkeypatch.setattr(p0, "cli_run", real)
    assert p4.run_step(gates, name)["result"]["exit"] == 0 and not lock.exists()


def test_a_gate_is_never_assembled_from_two_product_codes(gates):  # G-1: one code across all runs
    for sid, code in (("p4-a-n2-l40-run", "x"), ("p4-b-n2-l40-run", "y")):
        p0.save(gates / "steps" / f"{sid}.json", {"step": sid, "code": code})
    with pytest.raises(SystemExit):
        p4.records(gates, ["p4-a-n2-l40-run", "p4-b-n2-l40-run"])


def test_a_plateau_needs_a_window_of_one_rise_time():  # plan 3's Review Focus 2: no level, never a number
    r = read(line_s([(50.0, 3.2, 10.0), (75.0, 3.2, 36.0), (50.0, 3.2, 10.0)], F), F, SE, 3.2)
    t_r = r.rise[0]
    mid = p4.plateau(r, 2 * 10e-3 * math.sqrt(3.2) / C0 + t_r, 2 * 46e-3 * math.sqrt(3.2) / C0 - t_r)
    assert mid == pytest.approx(75.0, abs=0.05)  # 74.99 over 180 ps
    assert p4.plateau(r, 1e-9, 1e-9 + 0.99 * t_r) is None
    assert p4.plateau(r, 1.5e-9 - t_r / 2, 1.5e-9 + t_r / 2) is not None  # one rise time, to rounding


def test_the_rows_and_the_si_speed_refit(gates):  # K-1: the refit's rows from the gates' own runs
    for board in ("p4c_step35", "si_line100"):
        p4.run_step(gates, p4.project(gates, board)[0])
    rows = p4.rows(gates)
    assert [r["step"] for r in rows] == ["p4-p4c_step35-n2-l40-run", "p4-si_line100-n2-l40-run"]
    assert {(r["node_mcs"], r["cal_mcs"], r["debye_cells"]) for r in rows} == {(100.0, 200.0, 0)}
    assert p4.refit(rows) == {"si_speed": 0.5, "range": [0.5, 0.5], "by_pool": {2: 0.5}, "rows": 2}
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_p4.py tests/test_p3.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p4'`; test_p3 passes (a guard).
- [ ] **Step 3: `tools/p3.py`.** `step_id(name, command, prefix="p3")` returns `f"{prefix}-{name}-{command}"`. `run_step(out, name, command="run", prefix="p3")` passes the prefix on. `variant(out, name, board, edits, make=base)` calls `make(out, board)` where it called `base`. The docstrings name both. P3's keys and tests stand.
- [ ] **Step 4: `tools/p4.py`.** Module docstring:

  > The gates P4-B to P4-F's shared runner (Stage 4 design 5.11, plan 4 ruling G-1), on p0's and p3's machinery:
  > - the gates folder;
  > - a base project per board from `new --interface` (test_p4_fixtures.P4_NEW);
  > - its variants at a mesh n, a mesh rule and a dielectric;
  > - resumable run steps keyed by model, preset and code;
  > - the one-code check;
  > - in-process measurements of a run's chain, with cost's own SI time and the product's validity flags;
  > - the deltas compare would read;
  > - the SI cost refit's rows.
  >
  > Checkpoint decisions are this module's constants N, RULE, DIELECTRIC, EDITS and BENDS_N3, never src. Dev-time only, like p0.

  - **Constants:**
    - `N = 2`: "mesh n, P4-B's checkpoint (B-6)";
    - `RULE = "l40"`: "the SI rule, "l40" (new's λ/40), "l80" (λ/80) or "dfill" (max_cell_mm null), P4-C's checkpoint (C-2, C-3)";
    - `DIELECTRIC = "lossless"`: "P4-D's checkpoint (§5.3's rule)";
    - `EDITS: dict = {}`: "project edits by board, Task 3's recorded fit2d blocks (Stage 3 ruling 2's limit)";
    - `BENDS_N3 = "pending"`: "the owner's answer on a 45° twin's n 3 run (B-4): "pending", or "declined" when no go comes by P4-F's report".
  - **`enter`:** `p3.enter`. It imports `P4_NEW` by `sys.path.append(str(p0.ROOT / "tests"))`, as golden_si does.
  - **`base(out, board)`:** p3.base's body with `p0.cli("new", str(kept), *P4_NEW[board], "-o", str(pj.parent))`.
  - **`name(...)`:** `f"{board}-n{n or N}-{rule or RULE}"`, then `-debye` when the dielectric (or DIELECTRIC) is "debye", then `-{tag}` when given.
  - **`settings(base, ...)`:** `{"mesh.n", "mesh.max_cell_mm", "dielectric"}`. The max cell is the base's λ/40 for "l40", `round(it / 2, 6)` for "l80", and None for "dfill".
  - **`project(out, board, ...)`:** `p3.variant(out, name(...), board, settings(load_project(base(out, board)), ...) | EDITS.get(board, {}) | (extra or {}), make=base)`; it returns (name, path).
  - **`run_step`:** `p3.run_step(out, name, "run", prefix="p4")`. `records` is `p3.records`.
  - **`plateau(r, t0, t1)`:** "the median of r.z over t0 ≤ t ≤ t1; None when (t1 − t0)/r.rise[0] < 1 − 1e-9 (one rise time, to rounding) or no sample falls there".
  - **`reading(pj, project)`:** `pipeline.chain_results(pj, project)`, then `read(res.chain, res.lay.f, project, project["results"]["route"]["eeff"])`. It returns (the Reading, None), or (None, the KrsError's code) on a refusal, or (None, None) with no chain. A coupon's chain is its layout.
  - **`measure(out, name)`:** None without the step's record. Otherwise:
    - `p0.summary(record)`, with "predicted_s" and "worst_s" recomputed by `predicted_s` against the spec (the run folder's model.json) and `entry = record["load"]["calibration"]`;
    - "speeds_mcs": each job's openEMS_stats speed in MC/s (p3.measure's three lines); "node_mcs": their median;
    - "cal_mcs": `runs.calibrated_mcs(entry, pool)`; "debye_cells": `debye_cells(spec)`;
    - "converged": every job "converged"; "valid": converged, with the summary's sigma ≤ `checks.SIGMA_LIMIT` and recip ≤ `checks.RECIP_LIMIT` (the product's flags); "blocked": the record's exit is 3; "t_stop_s": the longest kept t_stop;
    - "fingerprint": the results' fingerprint; "project": project.json as loaded;
    - "reading" and "reading_error": `reading(pj, project)` when the step exited 0 and project.json's results are that run's (run_dir names match), else (None, None).
  - **`plain(m)`:** m without "reading" and "project".
  - **`deltas(a, b)`:** `si_deltas(a["project"], a["reading"], b["reading"])` on two measures. It raises ValueError naming the differing keys when their fingerprints differ, as compare refuses.
  - **`predicted_s(spec, dt, t, pool, jobs, entry)`:** cost_notes' SI time, commented `# mirrors pipeline.cost_notes and prepare(si=True)`:
    - weighted cells = cells + (DEBYE_WEIGHT − 1)·debye_cells;
    - mcs = per_job_mcs(entry, pool), × SI_SPEED when it equals calibrated_mcs(entry, pool);
    - `p0.predicted_s(jobs, pool, weighted, dt, t, mcs)`.
  - **`rows(out)`:** each `p4-…-run` record not loaded, through `measure`: `{"step", "pool", "cells", "debye_cells", "node_mcs", "cal_mcs"}`, a row lacking any of them left out. Mark it `# ponytail: measure reads each run's Reading too, unused here; a cost-only reader at hundreds of steps`.
  - **`refit(rows)`:**
    - "si_speed": the median of node_mcs/cal_mcs over the rows with no Debye cell, to 3 significant digits;
    - "range": [min, max] of those ratios; "by_pool": {pool: median}; "rows": their count.
  - **`refit_record(out, w, dest)`:** writes `dest.json` (`{"rows", "result", "w", "before": {"SI_SPEED", "DEBYE_WEIGHT"}}`) through `p0.save`, and `dest.md` (the rows' table with each ratio, then the result) through `p0.table`. It returns the JSON.
  - The ponytail: `# ponytail: no keep-awake call (the sleep timeout is 0); a reaped or rebooted step reruns`.
- [ ] **Step 5: Run them again.** Step 2's command. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/p4.py tools/p3.py tests/test_p4.py
git commit -m "test(gates): the shared runner of gates P4-B to P4-F on Stage 3's machinery, projects by board, mesh n, rule and dielectric, resumable run steps, one-code records, in-process SI measurements with cost's own time and the product's validity flags, and the SI speed refit's rows (Stage 4 design 5.11; plan 4 rulings G-1, G-3, K-1)"
graphify update .
```

---

### Task 5 [code]: P4-B's tool, the coupled coupons

**Files:** Create `tools/p4b.py`, `tests/fixtures/p4b/criteria.json`, `tests/fixtures/p4b/references.json` (written by the tool) and `tests/test_p4b.py`.

**Interfaces:**
- Consumes: Task 4's `p4.*`; `p4a.even_odd_s`, `cohn`; `core.mesh.gates.fit2d`; `cs2d.pair`; `sections.cross_section`; `si.compare_verify`, `si_deltas`, `arrival`; `tests/kicad_lines.coupled_microstrip`; skrf's `Network.renormalize`; `test_post_si.F`, `P100`, `pair6`.
- Produces:
  - `CRITERIA` (the dict), `REFERENCES` (the path, `p0.FIX / "p4b" / "references.json"`);
  - `COUPONS = ("p4b_ms90", "p4b_ms100", "p4b_sl90")`, `BENDS = {"p4b_ms90_45": "p4b_ms90", "p4b_ms100_45": "p4b_ms100"}`, `VICTIM = ("p4b_ms90_vic", "p4b_ms90_cut")`;
  - `next_peak(s, f, f_q, lobe=2.0) -> tuple[float, float]`, `fext_db(s, f, z, f_hi=None) -> float`, `victim(project, vic: Reading, cut: Reading) -> dict`;
  - `references() -> dict`, `measure(out) -> dict`, `decide(m: dict, refs: dict) -> dict`, `write(out) -> dict`, `main(argv=None) -> int`.

- [ ] **Step 1: The criteria,** `tests/fixtures/p4b/criteria.json`:

```json
{"source": "Stage 4 design 5.11, gate P4-B; plan 4 rulings B-1 to B-6: Zdiff is the median of the localising differential TDR from 2 t_r to t_far - 2 t_r, judged against fit2d's coupled Zdiff on the run's own mesh (the 2D solve of the same discretised cut: a miss is a pipeline bug, which blocks) and recorded against cs2d's exact cut and KiCad's calculator; n 2 against n 3 judged on each coupon's plateau over its own mesh's fit2d Zdiff, n 2 the reference, n 3 the SI default when any moves by more than n_rel, with fit2d's own n 2 to n 3 move, each n's error against the exact cut, and the runs' largest |dS| and TDT arrivals recorded; NEXT the peak of the layout's P-near to N-near over 0 < f <= lobe x f_q, against the even/odd model of the coupled run's modes on the run's own mesh lines at 50 ohm, the exact cut's model recorded; FEXT the peak of P-near to N-far over 0 < f <= lobe x f_q after renormalising every port to those modes' sqrt(Ze Zo), at most fext_db for the stripline, its full band, its 50 ohm peak and the launch's worst |S11| recorded; the 45 degree twins at n 2 whatever the decided n, each level at the diagonal's centre in round-trip time, the median over t_r, within bend_rel of its straight twin's plateau at the same n; a twin that misses runs at n 3 only with the owner's go, and one blocked at its setup counts as a miss; each run valid (every job converged, passivity and reciprocity under the product's flags); a None reading fails; the cut victim recorded on the pair's own 4-port block, the refusal kept",
 "zdiff_rel": 0.015, "n_rel": 0.01, "next_db": 0.5, "lobe": 2.0, "fext_db": -40.0, "bend_rel": 0.05}
```

- [ ] **Step 2: Write the failing tests,** `tests/test_p4b.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import pytest

import p4b
from kicad_rf_studio.core.post.si import read
from p4a import even_odd_s
from test_post_si import F, P100, pair6

MS = {"next_db": -17.546, "f_q_hz": 0.6895e9, "z_ref": 50.28}  # a coupon's mesh modes' model at one n
REFS = {"coupons": {c: {"fit2d": {"2": {"z0_mesh": z2, **MS}, "3": {"z0_mesh": z3, **MS}}}
                    for c, z2, z3 in (("p4b_ms90", 91.153, 90.711), ("p4b_ms100", 100.271, 101.32),
                                      ("p4b_sl90", 91.71, 92.383))},
        "bends": {"p4b_ms90_45": {"t_mid_s": 399.6e-12}, "p4b_ms100_45": {"t_mid_s": 399.6e-12}}}


def row(plateau, next_db=-17.546, fext=-60.0, valid=True, level=None, blocked=False):
    return {"plateau_ohm": plateau, "next_db": next_db, "fext_db": fext, "valid": valid, "level_ohm": level,
            "blocked": blocked}


def z(c, n=2):
    return REFS["coupons"][c]["fit2d"][str(n)]["z0_mesh"]


def full(**over):  # every step run and passing: each coupon on its own mesh's fit2d value, the bends on their twins'
    m = {f"{c}-n{k}": row(z(c, k)) for c in p4b.COUPONS for k in (2, 3)}
    m |= {f"{b}-n2": row(None, level=z(t)) for b, t in p4b.BENDS.items()}
    return {**m, "victim": {"ds_pair": 0.0}, "bends_n3": "pending"} | over


def test_the_p4b_rules_keep_n2_and_the_warning_on_good_runs():  # design 5.11; B-4, B-6
    d = p4b.decide(full(), REFS)
    assert d["decisions"] == {"mesh_n": 2, "staircase": "warn", "cut_victim": "refusal kept"}
    assert d["verdict"] == {"value": "pass", "fails": []}


def test_each_p4b_check_inclusive_with_its_fallback():  # design 5.11's fallbacks
    def verdict(**over):
        return p4b.decide(full(**over), REFS)
    assert verdict(**{"p4b_ms100-n3": row(z("p4b_ms100", 3) * 1.0099)})["decisions"]["mesh_n"] == 2
    moved = verdict(**{"p4b_ms100-n3": row(z("p4b_ms100", 3) * 1.0101)})  # the FDTD's own move past 1 %: n 3 (B-6)
    assert moved["decisions"]["mesh_n"] == 3 and moved["verdict"] == {"value": "fallback", "fails": []}
    raw = verdict(**{"p4b_ms100-n3": row(z("p4b_ms100", 2) * 1.0105)})  # +1.05 % raw, the move fit2d predicts
    assert raw["decisions"]["mesh_n"] == 2
    bug = verdict(**{"p4b_ms90-n2": row(z("p4b_ms90") * 1.0151)})
    assert bug["verdict"]["value"] == "blocked" and "p4b_ms90-n2: zdiff" in bug["verdict"]["fails"]
    assert verdict(**{"p4b_ms90-n2": row(z("p4b_ms90"), next_db=-17.046)})["verdict"]["fails"] == []  # 0.5 dB
    assert verdict(**{"p4b_ms90-n2": row(z("p4b_ms90"), next_db=-17.036)})["verdict"]["value"] == "fail"
    assert verdict(**{"p4b_sl90-n2": row(z("p4b_sl90"), fext=-40.0)})["verdict"]["fails"] == []
    assert verdict(**{"p4b_sl90-n2": row(z("p4b_sl90"), fext=-39.9)})["verdict"]["fails"] == ["p4b_sl90-n2: fext"]
    assert verdict(**{"p4b_ms90-n2": row(z("p4b_ms90"), valid=False)})["verdict"]["fails"] == ["p4b_ms90-n2: valid"]
    assert verdict(**{"p4b_ms90-n2": row(None)})["verdict"]["fails"][0] == "p4b_ms90-n2: no reading"
    assert p4b.decide({k: v for k, v in full().items() if k != "p4b_sl90-n3"}, REFS)["verdict"]["value"] == "incomplete"
    unrun = p4b.decide(full(victim=None), REFS)
    assert unrun["decisions"]["cut_victim"] is None and unrun["verdict"]["value"] == "incomplete"


def test_the_45_degree_rule():  # B-4: the twins at n 2; n 3 only for a twin that missed, with the owner's go
    off = {"p4b_ms90_45-n2": row(None, level=z("p4b_ms90") * 1.051)}
    assert p4b.decide(full(**off), REFS)["decisions"]["staircase"] is None  # its n 3 run first
    declined = p4b.decide(full(**off, bends_n3="declined"), REFS)
    assert declined["decisions"]["staircase"] == "owner" and declined["verdict"]["value"] == "fallback"
    n3 = {"p4b_ms90_45-n3": row(None, level=z("p4b_ms90", 3))}
    assert p4b.decide(full(**off, **n3), REFS)["decisions"]["staircase"] == "n3"
    up = {"p4b_ms100-n3": row(z("p4b_ms100", 3) * 1.0101)}  # n 3 the default already: the staircase passes there
    assert p4b.decide(full(**off, **n3, **up), REFS)["decisions"]["staircase"] == "warn"
    worse = {"p4b_ms90_45-n3": row(None, level=z("p4b_ms90", 3) * 1.06)}
    assert p4b.decide(full(**off, **worse), REFS)["decisions"]["staircase"] == "refuse"
    blocked = {"p4b_ms90_45-n3": row(None, blocked=True)}  # its setup refused at n 3
    assert p4b.decide(full(**off, **blocked), REFS)["decisions"]["staircase"] == "refuse"
    assert p4b.decide(full(**{"p4b_ms90_45-n2": row(None, level=z("p4b_ms90") * 1.049)}), REFS)[
        "decisions"]["staircase"] == "warn"


def test_next_is_read_on_its_first_lobe_against_the_even_odd_model():  # B-3
    s = even_odd_s(58.9864, 3.5015, 45.1268, 3.0629, 60.0, F)  # the 90 ohm coupon's modes, 50 ohm ports
    assert p4b.next_peak(s, F, 0.6895e9) == (pytest.approx(-17.546, abs=1e-3), 685e6)


def test_stripline_fext_is_read_on_its_first_lobe_at_root_ze_zo():  # B-3; the launches' FEXT lies above it
    f_q = 2.99792458e8 / (4 * 60e-3 * math.sqrt(4.3))  # 0.602 GHz
    s = even_odd_s(56.0141, 4.3, 45.1337, 4.3, 60.0, F)  # the stripline's modes: sqrt(Ze Zo) 50.28 ohm
    assert p4b.fext_db(s, F, 50.0, 2 * f_q) == pytest.approx(-64.46, abs=0.01)
    assert p4b.fext_db(s, F, math.sqrt(56.0141 * 45.1337), 2 * f_q) <= -250.0  # none at its own reference
    late = s.copy()
    late[F > 5e9, 3, 0] = late[F > 5e9, 0, 3] = 0.1  # a launch's FEXT from 5 GHz up
    assert p4b.fext_db(late, F, 50.0, 2 * f_q) == pytest.approx(-64.46, abs=0.01) and p4b.fext_db(late, F, 50.0) > -21
    assert p4b.fext_db(even_odd_s(70.0, 4.3, 45.0, 4.3, 60.0, F), F, 50.0) == pytest.approx(-32.30, abs=0.01)


def test_the_victim_case_reads_the_pairs_own_block():  # B-5; Review Focus 3: 6 ports against 4
    vic = read(pair6(0.05, 0.02), F, P100, 3.0)
    cut = read(pair6()[:, :4, :4], F, {**P100, "lines": P100["lines"][:2]}, 3.0)
    v = p4b.victim(P100, vic, cut)
    assert [r["quantity"] for r in v["rows"]] == ["tdr_lowest", "tdr_highest", "sdd21", "sdd21", "sdd11_worst",
                                                  "scd21_worst", "skew"]  # the pair's rows: the cut has no victim
    assert v["ds_pair"] == 0.0 and (v["next_db"], v["fext_db"]) == (pytest.approx(-29.03, abs=0.01),
                                                                   pytest.approx(-36.99, abs=0.01))


def test_the_committed_references_hold_the_replicas_numbers():  # G-1; design 5.11: committed before any run
    refs = json.loads(p4b.REFERENCES.read_text(encoding="utf-8"))
    for c, (z2, z3) in {"p4b_ms90": (91.153, 90.711), "p4b_ms100": (100.271, 101.32),
                        "p4b_sl90": (91.71, 92.383)}.items():
        mesh = refs["coupons"][c]["fit2d"]
        assert (mesh["2"]["z0_mesh"], mesh["3"]["z0_mesh"]) == (pytest.approx(z2, abs=0.02), pytest.approx(z3, abs=0.02))
        assert all(m["z0_mesh"] == pytest.approx(2 * m["z_odd"], rel=1e-9) for m in mesh.values())  # Zdiff = 2 Zodd
    exact = refs["coupons"]["p4b_ms90"]["exact"]
    assert (exact["z_diff"], exact["next_db"]) == (pytest.approx(90.2537, abs=0.02), pytest.approx(-17.546, abs=0.01))
    assert refs["coupons"]["p4b_sl90"]["exact"]["fext50_db"] == pytest.approx(-64.46, abs=0.05)
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_p4b.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p4b'`.
- [ ] **Step 4: `tools/p4b.py`.** Module docstring:

  > P4-B, the coupled coupons (Stage 4 design 5.11; plan 4 rulings B-1 to B-6): the 90 and 100 Ω microstrip pairs and the coupled stripline at n 2 and n 3, the 45° twins at n 2 (n 3 for a twin that missed, with the owner's go), and the terminated against the cut victim. Each is run through the product at the SI rule and lossless. Their Zdiff, NEXT and FEXT are judged against the 2D solve of their own mesh lines in `tests/fixtures/p4b/references.json`, by `criteria.json`, and p4b.json and p4b.md are written in <out>/p4b. Run: `python tools/p4b.py --out DIR [--steps board-nK,...] [--references]`.

  - **Readers:**
    - `next_peak(s, f, f_q, lobe)`: the highest `db(s[:, 1, 0])` over 0 < f ≤ lobe·f_q, with its f;
    - `fext_db(s, f, z, f_hi)`: `db` of S[:, 3, 0]'s peak over 0 < f ≤ f_hi (the whole grid when None) after `rf.Network(..., z0=50.0, s_def="power").renormalize(z)` on a copy;
    - `victim(project, vic, cut)`: {"rows": `si_deltas(project, vic, cut)` (the pair's rows; the cut has no victim's), "ds_pair": the largest |vic.s − cut.s| over the pair's block `[1:, :4, :4]`, "next_db" and "fext_db": vic.xt[0]'s peaks}. Its docstring says the two fingerprints differ by design ("ends"), so it never goes through `p4.deltas`.
  - **`references()`:** computed in memory in a temporary folder, each board's base by `new` with `P4_NEW`, lossless, at the SI rule.
    - Per coupon and n (2 and 3): its 60 mm coupled section's `fit2d` Fit (z0_mesh, z0_ref, err) and, as fit2d builds it, `on = pair(cross_section(sec, geom.pieces, geom.zs, geom.masks.get(sec.layer), "smeared", mesh.dz0, partners=geom.partners(sec.net)), mesh.y, mesh.z)`: its z_even, eps_even, z_odd, eps_odd; f_q_hz = c/(4·60 mm·√((εe + εo)/2)); next_db and next_hz, `next_peak` of `even_odd_s` at those modes on `uniform_grid(10e9)`; z_ref = √(z_even·z_odd). They go under `fit2d[str(n)]`.
    - Per coupon, "exact": the same of cs2d's `pair` on the exact cut with the mask, plus z_diff and fext50_db (the model's full-band FEXT at 50 Ω).
    - Recorded only: `kicad` for the microstrips (`coupled_microstrip(w, s, 0.2, 0.035, 4.3)`'s Zdiff; ruling B-2), and `cohn` for the stripline (`cohn(0.18, 0.25, 0.535, 4.3)`).
    - Per bend, `t_mid_s` = 2·(2 + (1 − p) + 15 + 16.5) mm·√εodd/c, at the twin's exact modes.
    - It also stores "code" (`p0.code_id()`) and "versions".
    - The replica's numbers: ms90 exact 58.9864 / 3.5015 / 45.1268 / 3.0629 Ω and εeff, 90.2537 Ω, NEXT −17.546 dB at 685 MHz, fit2d 91.153 Ω at n 2 and 90.711 at n 3; ms100 exact 99.8145 Ω, fit2d 100.271 and 101.32; sl90 exact 56.0141 / 45.1337 Ω, εr 4.3 both, 90.2674 Ω, fit2d 91.71 and 92.383, FEXT at 50 Ω −64.46 dB.
  - **Steps:** `--steps` takes `<board>-n<k>` for the boards of COUPONS, BENDS and VICTIM. Each runs `p4.run_step(out, p4.project(out, board, n=k, rule="l40", dielectric="lossless")[0])`.
  - **`measure(out)`:** each recorded step's row from `p4.measure` and its reading `r`, t_r = r.rise[0], at its coupon's `fit2d[str(n)]` references:
    - "plateau_ohm" = `p4.plateau(r, 2·t_r, t_far − 2·t_r)` (None without t_far or a reading);
    - "next_db" = `next_peak(r.s, r.f, ref.f_q_hz, lobe)`'s dB; "fext_db" = `fext_db(r.s, r.f, ref.z_ref, lobe·ref.f_q_hz)`; "fext_full_db" = `fext_db(r.s, r.f, ref.z_ref)`; "fext50_db" = `fext_db(r.s, r.f, 50.0)`; "launch_db" = the largest `db(r.s[:, 0, 0])`;
    - "level_ohm" = `p4.plateau(r, t_mid_s − t_r/2, t_mid_s + t_r/2)` for a bend;
    - "valid", "blocked", "reading_error", "sigma" and "recip" (recorded), "cells", "t_stop_s", "predicted_s", "worst_s" and "wall_s";
    - per coupon with both runs, "n_ds" = `compare_verify(r2, r3)["ds_max"]` and "n_delay_rel" = |arrival₃/arrival₂ − 1| of their TDTs, recorded;
    - "victim": `victim(vic_project, vic, cut)` when both victim runs read, else None; "bends_n3": `p4.BENDS_N3`.
  - **`decide(m, refs)`:** each limit inclusive and a None value a fail:
    - **Checks per recorded coupon step,** at its n's `fit2d` references:
      - `zdiff`: |plateau/z0_mesh − 1| ≤ zdiff_rel; a None plateau is "no reading";
      - `next`: |next_db − ref.next_db| ≤ next_db;
      - `fext`: for the stripline, fext_db ≤ the limit;
      - `valid`: the run's flag.
    - **`mesh_n`:** with eₖ = plateauₖ/z0_meshₖ, 2 when every coupon's |e₃/e₂ − 1| ≤ n_rel, 3 when any exceeds it, None when one lacks either run.
    - **`staircase`,** each bend judged as |level/(its twin's plateau at that n) − 1| ≤ bend_rel, a missing twin run leaving it undecided:
      - "warn" when every bend passes at n 2;
      - else, for each bend that missed: with its n 3 run, "warn" when they pass and mesh_n is 3, "n3" when they pass and mesh_n is 2, "refuse" when one fails or is blocked at setup; without it, "owner" when bends_n3 is "declined", else None.
    - **`cut_victim`:** "refusal kept" when m["victim"] is not None, else None.
    - **The verdict:** "blocked" on any zdiff fail (design §5.11: a pipeline bug); else "fail" on another check's fail; else "incomplete" while a decision is None or a coupon step is missing; else "fallback" when mesh_n is 3 or staircase is "n3", "refuse" or "owner"; else "pass".
    - It returns `{"checks", "decisions", "verdict": {"value", "fails"}}`. A fail names its step and check, as `"p4b_ms90-n2: zdiff"`.
  - **`write(out)`**, after `p4.records` over the recorded steps:
    - p4b.json: versions, criteria, the references' scalars, `p4.plain` rows, decisions, `p0.machine` and calibration;
    - p4b.md, by `p0.table`: P4B-1 the checks with limit, value and pass, each coupon's n 2 against n 3 (plateaus net of fit2d, fit2d's own move, |ΔS|, the arrival), the decisions and the verdict; P4B-2 the runs (cells, pool, t_stop, predicted to t_stop and to T_max, wall); P4B-3 the victim case, saying the two runs' fingerprints differ by design.
  - **`main`:** `--references` writes REFERENCES through `p0.save`, with SystemExit "P4-B's references are committed once, before its runs, and never regenerated" when the file exists. `--steps` runs them through `p4.run_steps`. Without either it writes the report. It returns 1 when a step raised.
- [ ] **Step 5: Run them again,** then write the references: `.venv/Scripts/python -X utf8 tools/p4b.py --references` with LOCALAPPDATA and XDG_DATA_HOME at an empty folder under `$env:TEMP` in the same call, then Step 3's command again. Expected: PASS, the references test included. A miss stops the task.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/p4b.py tests/test_p4b.py tests/fixtures/p4b
git commit -m "test(p4b): gate P4-B's steps, readers and pre-registered checks, Zdiff, NEXT and FEXT against the 2D solve of the run's own mesh, n 2 against n 3 net of fit2d's own move, the 45 degree rule at n 2 and the victim case on the pair's own block, with its references committed before any run (Stage 4 design 5.11; plan 4 rulings B-1 to B-6)"
graphify update .
```

---

### Task 6 [code]: P4-C's tool, the SI rule and the TDR's steps

**Files:** Create `tools/p4c.py`, `tests/fixtures/p4c/criteria.json`, `tests/fixtures/p4c/references.json` (written by the tool) and `tests/test_p4c.py`.

**Interfaces:**
- Consumes: Task 4's `p4.*`; `si.arrival`, `compare_verify`; `fit2d`; `si_readout`; `test_post_si.line_s`, `F`, `SE`.
- Produces:
  - `CRITERIA`, `REFERENCES` (the path), `PAIRS = ("p4b_ms90", "p4c_l90")`, `STEP_LINES = ("p4c_step75", "p4c_step35")`, `ORDER = ("l40", "l80", "dfill")`;
  - `step_edges(r, rho_levels: tuple[float, float, float]) -> tuple[float, float]`, `step_row(r, ref: dict) -> dict`;
  - `dispersion(cell_mm, eeff, length_mm, f) -> float`, `route_limit_mm(cell_mm, d_mm, eeff, f, ds_max) -> float`;
  - `references()`, `measure(out)`, `decide(m, refs) -> dict`, `write(out)`, `main(argv=None)`.

- [ ] **Step 1: The criteria,** `tests/fixtures/p4c/criteria.json`:

```json
{"source": "Stage 4 design 5.11, gate P4-C; plan 4 rulings C-1 to C-4: the rule's runs at lambda/40 and at the lambda/80 arm (max_cell halved) against the d fill's (max_cell_mm null) on the straight 90 ohm pair (P4-B's run) and an L-shaped pair at the decided n, |dS| the largest over every entry and 0 < f <= f_max of the two layouts, the delay the TDT's arrival, every run valid; lambda/40 kept when both pairs pass; else lambda/80 when both pass at it with fewer cells than the d fill, else the d fill stays; the Yee grid's phase error, beta L (beta dx)^2/24 at f_max, and the route length up to which the rule meets ds_max recorded; the step lines at the decided rule: each plateau (lead from t_r to its predicted edge - t_r, middle between its edges +- t_r) against fit2d's Z0 on the run's mesh and gamma from the two plateaus against fit2d's, a miss a pipeline discrepancy that no cell along the line moves, which blocks; the middle's delay half the time between its edges, each edge the half height of the reflection coefficient between the plateaus either side, against L sqrt(eeff)/c, a miss refined: the lambda/80 arm when the rule is lambda/40, then n 3; the rule decided the more refined of the pairs' and the steps'; their levels unmarked, the short-feature rule's true negative, a mark an owner item",
 "ds_max": 0.01, "delay_rel": 0.005, "plateau_rel": 0.015, "gamma_abs": 0.01, "step_delay_rel": 0.02}
```

- [ ] **Step 2: Write the failing tests,** `tests/test_p4c.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import pytest
from scipy.constants import c as C0

import p4c
from kicad_rf_studio.core.post.si import read
from test_post_si import F, SE, line_s

STEP = {"z_lead": 50.0, "z_mid": 75.0, "gamma": 0.2, "t_edges_s": [2 * 38e-3 * math.sqrt(3.33) / C0,
        2 * 38e-3 * math.sqrt(3.33) / C0 + 2 * 36e-3 * math.sqrt(3.203) / C0], "delay_s": 36e-3 * math.sqrt(3.203) / C0}
REFS = {"steps": {s: {"2": STEP} for s in p4c.STEP_LINES}}


def pair(ds40=0.004, ds80=0.003, d40=1.0, cells=(1.4e6, 2.5e6, 6.0e6)):
    run = {"delay_s": 340e-12, "valid": True}
    return {"l40": {**run, "cells": cells[0], "delay_s": 340e-12 * d40}, "l80": {**run, "cells": cells[1]},
            "dfill": {**run, "cells": cells[2]}, "ds": {"l40": ds40, "l80": ds80}}


def decide(rule_now="l40", pairs=None, **row):
    steps = {s: {**STEP, "short": [False, False], "valid": True, **row} for s in p4c.STEP_LINES}
    return p4c.decide({"pairs": pairs or {p: pair() for p in p4c.PAIRS}, "steps": steps, "rule_now": rule_now,
                       "n_now": 2}, REFS)


def test_the_step_lines_readings_on_an_ideal_line():  # C-3: half heights in rho, not in ohms
    r = read(line_s([(50.0, 3.33, 38.0), (75.0, 3.203, 36.0), (50.0, 3.33, 38.0)], F), F, SE, 3.3)
    got = p4c.step_row(r, STEP)
    assert (round(got["z_lead"], 2), round(got["z_mid"], 2), round(got["gamma"], 4)) == (50.0, 74.99, 0.1999)
    assert got["delay_s"] == pytest.approx(STEP["delay_s"], rel=1e-4)  # 214.92 against 214.91 ps (ohms: -3.1 %)
    assert got["short"] == [False, False]  # 36 mm sections: no level marked short


def test_the_rule_decision():  # C-1, C-2: the lambda/80 arm runs with the rule's runs
    def rule(**kw):
        return decide(pairs={p: pair(**kw) for p in p4c.PAIRS})["rule"]
    assert rule() == "l40"
    assert rule(ds40=0.0101) == rule(d40=1.0051) == "l80"
    assert rule(ds40=0.023, cells=(1.4e6, 6.1e6, 6.0e6)) == "dfill"  # more cells than the d fill
    assert rule(ds40=0.023, ds80=0.0101) == "dfill"
    assert decide(rule_now="l80")["rule"] == "l80"  # the steps' delay refined it: the more refined of the two


def test_the_step_checks_inclusive_and_their_refinement():  # C-3: each refinement to the check it can move
    assert decide(z_mid=75.0 * 1.015)["verdict"]["value"] == "pass"
    assert decide(z_mid=75.0 * 1.0151)["verdict"]["value"] == "blocked"  # no cell along the line moves a plateau
    assert decide(gamma=0.2101)["verdict"]["value"] == "blocked"
    late = decide(delay_s=STEP["delay_s"] * 1.0201)
    assert (late["verdict"]["value"], late["refine"]) == ("fail", "l80")
    assert decide(rule_now="l80", delay_s=STEP["delay_s"] * 1.0201)["refine"] == "n3"
    assert decide(short=[True, False])["short_rule"] == "owner"  # the short-feature rule's true negative missed
    assert decide(valid=False)["verdict"]["fails"] == ["p4c_step75: valid", "p4c_step35: valid"]


def test_the_yee_grids_phase_error_is_what_the_lambda_80_arm_answers():  # C-2: recorded beside |dS|
    assert p4c.dispersion(0.429232, 3.0629, 60.0, 10e9) == pytest.approx(0.02273, abs=1e-4)
    assert p4c.dispersion(0.214616, 3.0629, 60.0, 10e9) == pytest.approx(0.005683, abs=5e-5)
    assert p4c.route_limit_mm(0.214616, 0.1, 3.0629, 10e9, 0.01) == pytest.approx(134.9, abs=0.5)  # against the d fill


def test_the_committed_references_hold_the_step_lines_and_the_rules_limits():  # C-2, C-3
    refs = json.loads(p4c.REFERENCES.read_text(encoding="utf-8"))
    step = refs["steps"]["p4c_step75"]["2"]
    assert (step["z_lead"], step["z_mid"]) == (pytest.approx(50.747, abs=0.02), pytest.approx(77.214, abs=0.02))
    assert refs["pairs"]["p4b_ms90"]["route_limit_mm"]["l80"] == pytest.approx(134.9, abs=1.0)
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_p4c.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p4c'`.
- [ ] **Step 4: `tools/p4c.py`.** Module docstring:

  > P4-C, the SI mesh rule and the TDR (Stage 4 design 5.11; plan 4 rulings C-1 to C-4). The rule at λ/40 and its λ/80 arm run against the d fill on P4-B's straight 90 Ω pair and an L-shaped pair at P4-B's n; the step lines run at the decided rule. They are judged against `tests/fixtures/p4c/criteria.json` and `references.json`, and p4c.json and p4c.md are written in <out>/p4c. Run: `python tools/p4c.py --out DIR [--steps ...] [--references]`.

  - **`dispersion(cell_mm, eeff, length_mm, f)`:** β·L·(β·Δx)²/24, β = 2πf√eeff/c. **`route_limit_mm(cell_mm, d_mm, eeff, f, ds_max)`:** ds_max over the per-mm difference of `dispersion` at the cell and at d.
  - **`step_edges(r, (rho_lead, rho_mid, rho_after))`:** the reflection ρ = (z − target)/(z + target) on r.t. The first edge is where ρ first crosses (rho_lead + rho_mid)/2 at t ≥ t_r; the second is where it next crosses (rho_mid + rho_after)/2. Each is interpolated linearly. The Ω half height read 3.1 % short on the ideal line, the ρ half height 0.007 %.
  - **`step_row(r, ref)`:** t_a and t_b are ref's predicted edges.
    - z_lead = `p4.plateau(r, t_r, t_a − t_r)`; z_mid = `p4.plateau(r, t_a + t_r, t_b − t_r)`; z_after = `p4.plateau(r, t_b + t_r, t_b + (t_a − t_r))`.
    - gamma = (z_mid − z_lead)/(z_mid + z_lead); delay_s = half the time between `step_edges`.
    - "short" is the levels' marks (`r.levels`), the short-feature rule's true negative that P4-F's report cites.
  - **`references()`:** in memory, lossless at the SI rule.
    - Per step line and n (2 and 3): z_lead and z_mid (fit2d's z0_mesh at that n: 50.747 / 77.214 Ω at n 2 on step75 in the replica), gamma from them, eeff_lead and eeff_mid (cs2d with the mask: 3.330, 3.203 or 3.462), `t_edges_s` (2·38 mm·√eeff_lead/c, plus 2·36 mm·√eeff_mid/c) and delay_s, under `steps[board][str(n)]`.
    - Per pair: the λ/40 and λ/80 max cells, d, the coupled run's length (60 and 40 mm), εodd, `dispersion` at both cells and at d (0.0227 and 0.0057 on the 60 mm pair), and `route_limit_mm` at each rule (about 28 and 135 mm).
  - **Steps:** `--steps` takes `p4b_ms90-dfill`, `p4b_ms90-l80`, `p4c_l90-l40`, `p4c_l90-dfill`, `p4c_l90-l80`, `p4c_step75` and `p4c_step35`, all at `p4.N` and lossless. The pairs run at the named rule, the step lines at `p4.RULE`. The straight pair's λ/40 run is P4-B's step: same project, same record.
  - **`measure(out)`:** per pair and rule, {"cells", "delay_s": arrival(r.t, r.tdt), "valid"}, and "ds" {rule: `compare_verify(r_rule, r_dfill)["ds_max"]`}. Per step line, `step_row` at the references for `p4.N`, plus "valid". "rule_now": `p4.RULE`, "n_now": `p4.N`.
  - **`decide(m, refs)`:**
    - A pair passes at a rule when that run is valid, ds ≤ ds_max and |delay/delay_dfill − 1| ≤ delay_rel.
    - **The pairs' rule:** "l40" when both pass at λ/40; else "l80" when both pass at λ/80 and each has fewer cells than its d fill, otherwise "dfill"; None while a needed run is missing.
    - **"rule":** the more refined (ORDER) of the pairs' rule and m["rule_now"].
    - **The steps,** at refs for m["n_now"]: plateau (z_lead and z_mid within plateau_rel) and gamma (within gamma_abs) misses are "blocked"; a delay miss (|delay/ref − 1| > step_delay_rel) is a "fail" with "refine": "l80" when rule_now is "l40", else "n3" when n_now is 2, else "controller"; an invalid run is "<step>: valid".
    - **"short_rule":** "true negative" when every step row's short is [False, False], else "owner" (an owner item, not a fail).
    - **The verdict:** "blocked", else "fail", else "incomplete" (the rule None or a step missing), else "fallback" (rule "l80" or "dfill"), else "pass".
  - **`write`** and **`main`:** as P4-B's. P4C-1 holds the pairs (|ΔS|, delays, cells, the dispersion estimate and each rule's route limit), P4C-2 the steps and the short marks, P4C-3 the runs.
- [ ] **Step 5: Run them again,** then `tools/p4c.py --references` as Task 5's Step 5, then Step 3's command again. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/p4c.py tests/test_p4c.py tests/fixtures/p4c
git commit -m "test(p4c): gate P4-C's steps and checks, the SI rule and its lambda/80 arm against the d fill with the rule's route-length limit, and the step lines' plateaus, reflection and delay read at the reflection's half heights, each miss refined by what can move it, with its references committed before any run (Stage 4 design 5.11; plan 4 rulings C-1 to C-4)"
graphify update .
```

---

### Task 7 [code]: P4-D's tool, ports, the DC point and loss

**Files:** Create `tools/p4d.py`, `tests/fixtures/p4d/criteria.json`, `tests/fixtures/p4d/references.json` (written by the tool) and `tests/test_p4d.py`.

**Interfaces:**
- Consumes: Task 4's `p4.*`; `core.post.waves.layout`; `core.project.parts`; `spec.debye_cells`; skrf's `media.MLine`; `test_cli_si.si_project`.
- Produces:
  - `CRITERIA`, `REFERENCES` (the path), `VERTICAL = {"si_pad_coupon": "In1.Cu", "si_pad_coupon_tall": "B.Cu"}`;
  - `make_vertical(pj: Path, plane: str) -> None`;
  - `dc_s(pj: Path) -> tuple[list[str], np.ndarray]` and `dc_check(pj: Path, ref: dict) -> float`;
  - `il_ref(f: np.ndarray) -> np.ndarray` and `il_metric(s: np.ndarray) -> np.ndarray`;
  - `share(spec: dict) -> float`, `weight(lossless_mcs, debye_mcs, f) -> float`, `slowdown(w, f) -> float`;
  - `references()`, `measure(out)`, `decide(m) -> dict`, `write(out)`, `main(argv=None)`; p4d.json's top-level "debye": {"w", "f_usb", "predicted", "measured", "il_ok", "il_worst", "dc_loss"}.

- [ ] **Step 1: The criteria,** `tests/fixtures/p4d/criteria.json`:

```json
{"source": "Stage 4 design 5.3, 5.4, 5.5 and 5.11, gate P4-D; plan 4 rulings D-1 to D-5: the vertical port against the horizontal on each pad coupon, the median of the localising TDR from t_r to t_far - t_r, within plateau_rel: the plateau tests the port's impedance scale, not its launch, so each port's launch (the largest |S11| up to f_max and the TDR's largest departure from the plateau within the first t_r) is recorded; graded: both pass, kept; the 0.2 mm coupon passes and the 1.51 mm one not, a vertical port longer than lambda/20 at f_max in the stack's highest er refused; the 0.2 mm one fails, a controller ruling (no blanket refusal); the DC point: the largest | |S_layout(0)| - |2P - I| | over every entry, P the projector onto the cut space of the node-by-port incidence of the ports' copper (nets joined by copper parts), from the committed references, within dc_abs on every lossless P4-D project and every recorded usb2_hs layout (a Debye run's DC point carries its slowest pole's tail, about 0.002 by a TEM model, and is judged by its DC loss alone); Debye on the 100 mm line: IL = -10 log10(|S21|^2/(1 - |S11|^2)), the Debye run's less its lossless twin's (the walls' and radiation's), within max(il_db, il_rel x IL_ref) of scikit-rf's MLine dielectric loss (Djordjevic-Sarkar, t 35 um: the model's copper is PEC) over f_lo_hz to f_max, and 1 - |S11(0)|^2 - |S21(0)|^2 <= dc_loss; the cell weight w = 1 + (R - 1)/f, R the median job MC/s lossless over Debye, f the Debye run's share of cells; the USB 2.0 fixture's slowdown 1 + f_usb (w - 1) predicted, run with Debye only inside run_usb; Debye the default when accurate and the slowdown, measured else predicted, is at most slowdown_max; every run valid",
 "plateau_rel": 0.015, "dc_abs": 0.01, "il_db": 0.05, "il_rel": 0.05, "f_lo_hz": 1e8, "dc_loss": 0.005,
 "slowdown_max": 1.5, "run_usb": [1.25, 1.75]}
```

- [ ] **Step 2: Write the failing tests,** `tests/test_p4d.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import numpy as np
import pytest

import p4d
from test_cli_si import si_project

USB_DC = np.array([[1 / 3, 0, 2 / 3, 0, 0, 0, 2 / 3, 0], [0, 1 / 3, 0, 2 / 3, 0, 0, 0, 2 / 3],
                   [2 / 3, 0, 1 / 3, 0, 0, 0, 2 / 3, 0], [0, 2 / 3, 0, 1 / 3, 0, 0, 0, 2 / 3], [0, 0, 0, 0, 0, 1, 0, 0],
                   [0, 0, 0, 0, 1, 0, 0, 0], [2 / 3, 0, 2 / 3, 0, 0, 0, 1 / 3, 0], [0, 2 / 3, 0, 2 / 3, 0, 0, 0, 1 / 3]])


def test_the_usb_fixtures_dc_reference_is_its_copper_projector(tmp_path):  # D-2: S = 2P - I
    names, s = p4d.dc_s(si_project(tmp_path / "u"))
    assert names == ["P1", "P2", "P3", "P4", "P5", "P6", "R1", "R2"]
    assert np.abs(s) == pytest.approx(np.abs(USB_DC), abs=1e-12)


def test_mlines_dielectric_loss_is_the_reference():  # D-1, D-3: t 35 um, PEC copper
    assert p4d.il_ref(np.array([1e8, 1e9, 5e9, 10e9])) == pytest.approx([0.0279, 0.2827, 1.4267, 2.8679], abs=1e-4)


def test_the_insertion_loss_metric_corrects_the_mismatch():
    s = np.zeros((1, 2, 2), complex)
    s[0, 0, 0], s[0, 1, 0] = 0.3, np.sqrt(0.9 * (1 - 0.09))
    assert p4d.il_metric(s)[0] == pytest.approx(-10 * np.log10(0.9))


def test_the_debye_weight_and_the_usb_slowdown():  # design 5.3; D-3
    assert p4d.weight(200.0, 50.0, 0.28) == pytest.approx(1 + 3 / 0.28)  # R 4 on a 28 % share
    assert p4d.slowdown(11.714, 0.281) == pytest.approx(1 + 0.281 * 10.714)


def test_the_p4d_decisions():  # design 5.11's fallbacks; D-3, D-5
    def m(short=1.0, tall=1.0, dc=0.001, accurate=True, dc_loss=0.0, w=11.0, f_usb=0.281, measured=None, invalid=()):
        return {"ports": {"si_pad_coupon": {"h": 50.0, "v": 50.0 * short},
                          "si_pad_coupon_tall": {"h": 48.0, "v": 48.0 * tall}},
                "dc": {"x": dc}, "invalid": list(invalid),
                "debye": {"il_ok": accurate, "dc_loss": dc_loss, "w": w, "f_usb": f_usb, "measured": measured}}
    d = p4d.decide(m())
    assert (d["port"], d["dielectric"], d["verdict"]["value"]) == ("kept", "lossless", "pass")  # 3.8x predicted
    assert p4d.decide(m(tall=1.0151))["port"] == "graded" and p4d.decide(m(short=1.0151))["port"] == "ruling"
    assert p4d.decide(m(dc=0.0101))["verdict"]["value"] == "fail"  # a lossless DC miss: the controller's
    near = p4d.decide(m(w=2.4))  # 1.39 predicted: inside [1.25, 1.75], so usb2_hs runs with Debye
    assert (near["dielectric"], near["debye"]["run_usb"]) == (None, True)
    assert p4d.decide(m(w=2.4, measured=1.5))["dielectric"] == "debye"
    assert p4d.decide(m(w=2.4, measured=1.51))["dielectric"] == "lossless"
    assert p4d.decide(m(w=1.5))["dielectric"] == "debye"  # 1.14 predicted: outside, the prediction decides
    assert p4d.decide(m(w=1.5, accurate=False))["dielectric"] == "lossless"
    assert p4d.decide(m(w=1.5, dc_loss=0.0051))["dielectric"] == "lossless"
    assert p4d.decide(m(invalid=["si_line100-debye"]))["verdict"]["fails"] == ["si_line100-debye: valid"]


def test_the_committed_references_hold_the_curve_and_the_projectors():  # G-1; D-2: judged against them
    refs = json.loads(p4d.REFERENCES.read_text(encoding="utf-8"))
    assert refs["il_ref"]["db"][-1] == pytest.approx(2.8679, abs=1e-3) and refs["il_ref"]["f_hz"][0] >= 1e8
    assert set(refs["dc"]) == {"si_pad_coupon", "si_pad_coupon_tall", "si_line100", "usb2_hs", "usb2_hs_neck",
                               "usb2_hs_gap"}
    assert np.abs(refs["dc"]["usb2_hs"]["s"]) == pytest.approx(np.abs(USB_DC), abs=1e-12)
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_p4d.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p4d'`.
- [ ] **Step 4: `tools/p4d.py`.** Module docstring:

  > P4-D, ports, pulse and loss (Stage 4 design 5.3–5.5, 5.11; plan 4 rulings D-1 to D-5). It runs:
  > - the vertical port against the horizontal one on two pad coupons;
  > - the DC point against the ports' copper connectivity;
  > - a 100 mm line, lossless and Debye, against scikit-rf's MLine;
  > - the Debye cell weight and the USB 2.0 fixture's predicted slowdown.
  >
  > Each is judged against `tests/fixtures/p4d/criteria.json` and the committed `references.json`, and p4d.json and p4d.md are written in <out>/p4d. Run: `python tools/p4d.py --out DIR [--steps ...] [--references]`.

  - **`make_vertical(pj, plane)`:** sets every external port's `reference` to `{"plane": plane}` and its `rule` to "plane", saving only on a change. Dotted edits cannot reach a list.
  - **`dc_s(pj)`:**
    - The layout's ports are the model's, external then parts.
    - Each external port's branch runs from its signal pad's net to its reference's net. A "pad" reference takes the pad's net; a "point" takes the net of the piece covering it on its layer; a "plane" takes the net of the plane piece under the signal pad's centroid.
    - Each part port's branch runs between its two pads' nets. Nets joined by a part of role "copper" are one node.
    - A is the node-by-port incidence (+1 signal, −1 reference); P = Aᵀ(AAᵀ)⁺A; S = 2P − I.
    - It returns (names, S). Mark it `# ponytail: PEC copper, so the network is ideal wires; real copper moves DC S by about R/100 (1.5e-3 on 100 mm), recorded`.
  - **`dc_check(pj, ref)`:** with `lay = layout(project, project["results"])`, the largest | |lay.s[0]| − |ref["s"]| | over every entry, after checking the port names are ref's. A part port's sign is its box's orientation, which the reference does not read. A -v project takes its board's entry: its plane is on the reference's net.
  - **`il_ref(f)`:** `8.686 * MLine(frequency=rf.Frequency.from_f(f, unit="Hz"), z0_port=50, w=0.33e-3, h=0.2e-3, t=35e-6, ep_r=4.3, tand=0.02, rho=1.68e-8, diel="djordjevicsvensson", f_low=1e3, f_high=1e12, f_epr_tand=1e9).alpha_dielectric * 0.1`, with warnings suppressed.
  - **`il_metric(s)`:** −10·log10(|S21|²/(1 − |S11|²)).
  - **`share(spec)`:** `debye_cells(spec) / cells`. `weight`: 1 + (R − 1)/f with R = lossless/Debye. `slowdown`: 1 + f·(w − 1).
  - **`references()`:** computed in memory, the only caller of `dc_s` and `il_ref`:
    - "il_ref": {"f_hz", "db"} on `uniform_grid(10e9)`'s points from f_lo_hz, and "call", its MLine call's parameters;
    - "dc": {board: {"names", "s"}}, the 2P − I of each P4-D base and of usb2_hs, usb2_hs_neck and usb2_hs_gap;
    - "z0", each coupon's 2D Z0; "copper_ds" 1.5e-3, the 100 mm line's R/100; "code" and "versions".
  - **Steps** (at `p4.N` and `p4.RULE`):
    - `si_pad_coupon-h`, `si_pad_coupon-v`, `si_pad_coupon_tall-h` and `si_pad_coupon_tall-v` (a v step runs its project with tag "v" after `make_vertical`);
    - `si_line100` (lossless) and `si_line100-debye`;
    - `usb2_hs` and `usb2_hs-debye`, the conditional pair (D-3). The lossless one is P4-F's base, the same step.
  - **`measure(out)`:**
    - "ports": each coupon's h and v plateaus `p4.plateau(r, t_r, t_far − t_r)`, their launches (the largest `db(r.s[:, 0, 0])`, and the largest |z − plateau| for t ≤ t_r), recorded;
    - "dc": {project: `dc_check(pj, refs["dc"][board])`} for every recorded lossless P4-D project and every recorded lossless `usb2_hs*` step in `<out>`;
    - "debye":
      - "il_ok", the Debye line's IL less its lossless twin's against `refs["il_ref"]` over f_lo_hz ≤ f ≤ f_max within max(il_db, il_rel·IL_ref), with "il_worst", its worst ratio and f;
      - "dc_loss", 1 − |S11(0)|² − |S21(0)|² of the Debye run; "il_lossless_db", the twin's IL, recorded as the walls' and radiation's floor;
      - "w" from the two runs' node_mcs and the Debye run's `share`; "f_usb", the share of usb2_hs's Debye model at `p4.N` and `p4.RULE`, built in memory; "measured", the usb2_hs pair's node_mcs ratio when both ran, else None;
    - "invalid": the recorded steps whose run is not valid.
  - **`decide(m)`:**
    - **The port:** "kept" when both coupons' |v/h − 1| ≤ plateau_rel, "graded" when only the tall one misses, "ruling" when the 0.2 mm one misses.
    - **The DC point:** passes when every value ≤ dc_abs.
    - **Debye:** "predicted" = slowdown(w, f_usb); "run_usb" = predicted in run_usb and measured None.
    - **`dielectric`:** "lossless" unless il_ok and dc_loss ≤ the limit; then "debye" when (measured, else predicted outside run_usb) ≤ slowdown_max; None while run_usb.
    - **The verdict:** "fail" on a DC miss, a port "ruling" or an invalid run (each a controller ruling, src being frozen); else "incomplete" while the dielectric is None; else "fallback" when the port is "graded" or Debye is inaccurate; else "pass".
  - **`write`** and **`main`:** as P4-B's. p4d.json's top level adds "debye": {"w", "f_usb", "predicted", "measured", "il_ok", "il_worst", "dc_loss"}, which Task 15 reads. P4D-1 holds the ports and their launches, P4D-2 DC, P4D-3 Debye and speed, P4D-4 the runs.
- [ ] **Step 5: Run them again,** then `tools/p4d.py --references` as Task 5's Step 5, then Step 3's command again. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/p4d.py tests/test_p4d.py tests/fixtures/p4d
git commit -m "test(p4d): gate P4-D's steps and checks, the vertical port against the horizontal with its graded fallback and its launch recorded, the DC point against the copper's committed projector, Debye's loss over its lossless twin against scikit-rf's MLine, the cell weight and the USB fixture's slowdown, with its references committed before any run (Stage 4 design 5.11; plan 4 rulings D-1 to D-5)"
graphify update .
```

---

### Task 8 [code]: P4-E's and P4-F's tools, the noise floor and the positive control

**Files:** Create `tools/p4e.py`, `tools/p4f.py`, `tests/fixtures/p4e/criteria.json`, `tests/fixtures/p4e/references.json` (written by the tool), `tests/fixtures/p4f/criteria.json`, `tests/fixtures/p4f/references.json`, `tests/test_p4e.py` and `tests/test_p4f.py`.

**Interfaces:**
- Consumes: Task 4's `p4.*`; `p0.model_key`; `core.post.si` (mixed_mode, db, si_delta_lines); `p4a.even_odd_s`; `fit2d`, `cs2d.pair`; `p4d.dc_check`, `p4d.REFERENCES`.
- Produces:
  - `p4e`: `CRITERIA`, `REFERENCES` (the path), `BOARDS = {2: {"shift": "p4e_shift", "gapp": "p4e_gapp", "gapm": "p4e_gapm", "vshift": "p4e_vshift"}, 3: {...the "3" boards}}`, `NULL = "p4e_null"`, `VICTIM = "p4b_ms90_vic"`;
    - `key(row: dict) -> str` ("sdd21@marker", else the quantity);
    - `noise(pairs: dict[str, list[dict]], model_even: dict) -> dict`;
    - `thresholds(noise: dict) -> dict`;
    - `null_equal(out: Path) -> bool`;
    - `references()`, `measure(out)`, `decide(m, refs) -> dict`, `write(out)`, `main(argv=None)`;
  - `p4f`: `CRITERIA`, `CASES = ("usb2_hs", "usb2_hs_neck", "usb2_hs_gap")`, `measure(out)`, `decide(m, t) -> dict`, `write(out)`, `main(argv=None)`.

- [ ] **Step 1: The criteria.**
  - `tests/fixtures/p4e/criteria.json`:

```json
{"source": "Stage 4 design 5.8 and 5.11, gate P4-E; plan 4 rulings E-1, E-2 and the controller's ruling on the plan's open issue 10: on P4-B's 90 ohm coupon at the decided n, rule and dielectric (its own base step, P4-B's or P4-C's run when the settings are equal), si_deltas of the base against the same run twice, the whole board shifted one fine cell, the gap moved +d and -d, and the null edit when its spec hash is not the base's; on P4-B's terminated-victim coupon at the same settings, si_deltas of its base against the whole board shifted one fine cell (vshift), which gives NEXT's and FEXT's noise; per quantity noise = max(|repeat|, |shift|, |null|, |vshift|, |even - model even|), even = (d+ + d-)/2, the last term only on a row with a model: the TDR rows (fit2d's coupled Zdiff on the run's own mesh lines at that n and rule), sdd21 at the marker (the even/odd model at those mesh modes, 90 ohm), the skew and scd21 (zero by the pair's symmetry); sdd21 at f_max and the worst sdd11, which the launches set, take no gap term, their even and odd parts recorded; next and fext have no gap pair, so their noise is the victim's shift; the exact cut's even part recorded; a dB row of a pair left out when both its levels lie under floor_db; each design value kept when its noise lies under a third of it, else three times the noise rounded up to its step; SE_OHM = DIFF_OHM/2, unmeasured on a pair",
 "factor": 3, "floor_db": -50.0, "design": {"DIFF_OHM": 1.0, "IL_DB": 0.05, "DB": 0.5, "SKEW_PS": 1.0},
 "steps": {"DIFF_OHM": 0.1, "IL_DB": 0.01, "DB": 0.05, "SKEW_PS": 0.1},
 "constants": {"DIFF_OHM": ["tdr_lowest", "tdr_highest"], "IL_DB": ["sdd21@marker", "sdd21@f_max"],
               "DB": ["sdd11_worst", "scd21_worst", "next", "fext"], "SKEW_PS": ["skew"]}}
```

  - `tests/fixtures/p4f/criteria.json`:

```json
{"source": "Stage 4 design 5.11, gate P4-F; plan 4 rulings F-1 to F-3: usb2_hs, its neck-down and its plane gap, each by run at new's values and the decided settings, compared through their runs' chains (no retune or verify), the gap under the ring rule; judged: the neck's highest TDR level's delta at least neck_factor x DIFF_OHM and the gap's Scd21 change resolved, each run valid; the neck run's own highest level marked short (the short-feature rule's true positive; the delta row's mark carries the base's levels, short already) checked, a miss an owner item; every other row recorded, with the ladder model's predictions as soft notes",
 "neck_factor": 3}
```

  - `tests/fixtures/p4f/references.json`, written by hand in this step and committed before any run:

```json
{"source": "plan 4 research r3 section 2: an ideal-line ladder model of usb2_hs (the 2D table's sections, 22 ohm and 0.5 nH a leg, 0.2 nH launches) through core.post.si; soft notes, never criteria",
 "neck": {"tdr_highest_delta_ohm": 8.05, "tdr_lowest_delta_ohm": 3.29, "pointwise_max_ohm": 11.3},
 "gap": {"tdr_highest_delta_ohm": [2.2, 3.9], "plan3_preview": {"tdr_highest_delta_ohm": 2.21, "scd21_worst_delta_db": 17.65}}}
```

- [ ] **Step 2: Write the failing tests.**
  - `tests/test_p4e.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

import p4e

MODEL = {"tdr_lowest": -2.5, "tdr_highest": -2.5, "sdd21@marker": -0.0078, "skew": 0.0, "scd21_worst": 0.0}


def rows(lo=0.0, hi=0.0, il=0.0, il_max=0.0, s11=(0.0, -20.0), scd=(0.0, -60.0), skew=0.0):
    def r(q, marker, delta, base=0.0):
        return {"quantity": q, "marker": marker, "delta": delta, "base": base, "variant": base + delta}
    return [r("tdr_lowest", "", lo, 84.9), r("tdr_highest", "", hi, 96.0), r("sdd21", "marker", il),
            r("sdd21", "f_max", il_max), r("sdd11_worst", "", s11[0], s11[1]), r("scd21_worst", "", scd[0], scd[1]),
            r("skew", "", skew)]


def test_the_gap_moves_even_part_is_curvature_not_noise():  # E-2; the model from the run's own mesh
    pairs = {"repeat": rows(), "shift": rows(lo=0.12, hi=-0.08), "gapp": rows(lo=4.6, hi=4.6),
             "gapm": rows(lo=-9.6, hi=-9.6)}
    n = p4e.noise(pairs, MODEL)
    assert n["DIFF_OHM"] == pytest.approx(0.12)  # the shift: the even part less the mesh model's is 0
    t = p4e.thresholds(n)
    assert (t["DIFF_OHM"], t["SE_OHM"], t["kept"]["DIFF_OHM"]) == (1.0, 0.5, True)
    flat = p4e.noise(pairs, {**MODEL, "tdr_lowest": 0.0, "tdr_highest": 0.0})  # no curvature taken out
    assert p4e.thresholds(flat)["DIFF_OHM"] == pytest.approx(7.5)  # 3 x 2.5, rounded up to 0.1


def test_a_row_without_a_model_takes_no_gap_term():  # the launches set Sdd21 at f_max and the worst Sdd11
    gap = rows(il_max=0.03, s11=(0.2, -20.0))
    n = p4e.noise({"repeat": rows(), "shift": rows(), "gapp": gap, "gapm": gap}, MODEL)
    assert (n["IL_DB"], n["DB"]) == (0.0, 0.0)
    assert (n["parts"]["sdd21@f_max"]["even"], n["parts"]["sdd11_worst"]["even"]) == (pytest.approx(0.03),
                                                                                      pytest.approx(0.2))


def test_the_thresholds_widen_to_three_times_the_noise_rounded_up():  # design 5.8; E-2: the criteria's design values
    t = p4e.thresholds({"DIFF_OHM": 0.4, "IL_DB": 0.0166, "DB": 0.21, "SKEW_PS": 0.2})
    assert (t["DIFF_OHM"], t["SE_OHM"], t["IL_DB"], t["DB"], t["SKEW_PS"]) == (
        pytest.approx(1.2), pytest.approx(0.6), 0.05, pytest.approx(0.65), 1.0)  # 0.0166 x 3 = 0.0498 < 0.05: kept
    assert t["kept"] == {"DIFF_OHM": False, "IL_DB": True, "DB": False, "SKEW_PS": True}


def test_a_db_row_under_the_floor_on_both_sides_is_no_noise():  # r3: the floor's rows left out
    pairs = {"repeat": rows(scd=(3.0, -70.0)), "shift": rows(), "gapp": rows(), "gapm": rows()}
    assert p4e.noise(pairs, MODEL)["DB"] == 0.0  # -70 to -67 dB: both under -50


def test_the_victims_shift_measures_next_and_fext():  # the controller's ruling on open issue 10
    xt = [{"quantity": q, "marker": "AUX", "delta": d, "base": -30.0, "variant": -30.0 + d}
          for q, d in (("next", 0.2), ("fext", -0.25))]
    n = p4e.noise({"repeat": rows(), "shift": rows(), "gapp": rows(), "gapm": rows(), "vshift": rows() + xt}, MODEL)
    assert n["DB"] == pytest.approx(0.25)  # FEXT's shift: no gap term, no model
    assert p4e.thresholds(n)["DB"] == pytest.approx(0.75)  # over a third of 0.5 dB: three times it


def test_the_null_edit_is_zero_when_its_hash_is_the_bases_else_one_more_pair():  # E-1
    refs = {"model_even": {"2-l80": MODEL}}
    base = {"key": "2-l80", "invalid": [], "pairs": {"repeat": rows(), "shift": rows(), "gapp": rows(), "gapm": rows(),
                                                     "vshift": rows()}}
    assert p4e.decide({**base, "null_equal": True}, refs)["verdict"]["value"] == "pass"
    assert p4e.decide({**base, "null_equal": False}, refs)["verdict"]["value"] == "incomplete"
    unrun = {**base, "pairs": {k: v for k, v in base["pairs"].items() if k != "vshift"}, "null_equal": True}
    assert p4e.decide(unrun, refs)["verdict"]["value"] == "incomplete"  # the victim's shift is a pair too
    over = {**base, "pairs": {**base["pairs"], "null": rows(hi=0.5)}, "null_equal": False}
    assert p4e.decide(over, refs)["verdict"]["value"] == "widened"  # 0.5 > 1/3 ohm
    assert p4e.decide({**base, "null_equal": True, "invalid": ["shift"]}, refs)["verdict"]["fails"] == ["shift: valid"]


def test_the_committed_references_hold_the_mesh_and_the_exact_even_parts():  # E-2
    refs = json.loads(p4e.REFERENCES.read_text(encoding="utf-8"))
    assert set(refs["model_even"]) == {f"{n}-{rule}" for n in (2, 3) for rule in ("l40", "l80", "dfill")}
    assert refs["model_even"]["2-l40"]["tdr_highest"] == pytest.approx(-2.50, abs=0.05)  # the physics review's replica
    assert (refs["exact"]["2"]["tdr_highest"], refs["exact"]["2"]["sdd21@marker"]) == (
        pytest.approx(-2.1486, abs=1e-3), pytest.approx(-0.0078, abs=2e-4))
```

  - `tests/test_p4f.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import p4f

T = {"DIFF_OHM": 1.0, "DB": 0.5, "floor_db": -50.0}


def m(highest=8.05, short=True, scd=(-45.0, -27.35), invalid=()):
    return {"neck": [{"quantity": "tdr_highest", "marker": "short", "delta": highest}],
            "gap": [{"quantity": "scd21_worst", "marker": "", "base": scd[0], "variant": scd[1],
                     "delta": scd[1] - scd[0]}],
            "neck_short": short, "base_short": [True, True], "invalid": list(invalid)}


def test_p4f_judges_the_rows_each_case_is_built_to_move():  # F-2
    assert p4f.decide(m(), T)["verdict"] == {"value": "pass", "fails": [], "owner": []}
    assert p4f.decide(m(highest=3.0), T)["verdict"]["fails"] == []  # 3 x DIFF_OHM, inclusive
    assert p4f.decide(m(highest=2.99), T)["verdict"]["fails"] == ["neck: tdr_highest"]
    assert p4f.decide(m(scd=(-70.0, -55.0)), T)["verdict"]["fails"] == ["gap: scd21_worst"]  # both under -50 dB
    assert p4f.decide(m(highest=8.05), {**T, "DIFF_OHM": 2.7})["verdict"]["fails"] == ["neck: tdr_highest"]
    assert p4f.decide(m(invalid=["usb2_hs_gap"]), T)["verdict"]["fails"] == ["usb2_hs_gap: valid"]


def test_a_neck_its_own_run_leaves_unmarked_is_an_owner_item():  # design 5.6; plan 3's owner item
    assert p4f.decide(m(short=False), T)["verdict"] == {"value": "pass", "fails": [], "owner": ["neck: short mark"]}
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_p4e.py tests/test_p4f.py -q`. Expected: FAIL with `ModuleNotFoundError`.
- [ ] **Step 4: `tools/p4e.py`.** Module docstring:

  > P4-E, the noise floor (Stage 4 design 5.8, 5.11; plan 4 rulings E-1, E-2). It runs P4-B's 90 Ω coupon at the decided settings, its own base and against it the same run twice, the board shifted one fine cell and its gap moved ± d, and the null edit when its spec hash is not the base's; and P4-B's terminated-victim coupon against itself shifted one fine cell, for NEXT's and FEXT's noise. The noise per quantity and the thresholds compare then uses are judged against `tests/fixtures/p4e/criteria.json` and `references.json`, and p4e.json and p4e.md are written in <out>/p4e. Run: `python tools/p4e.py --out DIR [--steps base,repeat,shift,gapp,gapm,null,vbase,vshift] [--references]`.

  - **`noise(pairs, model_even)`:**
    - Per key: the largest |Δ| over every pair but gapp and gapm (repeat, shift, null and vshift, each when present), and, when the key is in `model_even`, |(Δ_gapp + Δ_gapm)/2 − model_even[key]|. The even and odd parts, (Δ+ ± Δ−)/2, are recorded for every key the gap pairs hold.
    - A dB row of a pair is skipped when max(base, variant) ≤ floor_db.
    - Per constant, the max over its keys (0.0 when none).
    - It returns {constant: value, "parts": {key: {"repeat", "shift", "null", "vshift", "even", "model_even", "odd"}}}, None where a pair or a model is absent.
  - **`thresholds(noise)`:** for each constant T at CRITERIA["design"], keep T when noise < T/3. Else factor·noise, rounded up to its step (`math.ceil(round(x / step, 9)) * step`, to 6 decimals). Then `SE_OHM = DIFF_OHM / 2`. "kept" holds per constant. It never reads si.py, so a rerun after Task 16 judges the same way.
  - **`null_equal(out)`:** `p0.model_key` of the base project and of `NULL`'s at the decided settings, compared.
  - **`references()`:** for n 2 (D_SI boards) and n 3 (the "3" boards), at each rule ("l40", "l80", "dfill"), lossless: p4b_ms90's, the gapp's and the gapm's 60 mm coupled section on the run's own mesh lines, as P4-B's references build them (fit2d's coupled z0_mesh and `on`'s modes).
    - "model_even"[f"{n}-{rule}"]: the TDR rows (tdr_lowest and tdr_highest) take (Zd(s + d) + Zd(s − d))/2 − Zd(s) of those z0_mesh; "sdd21@marker" the same of `db(mixed_mode(even_odd_s(modes), f, 90.0, True)[48, 1, 0])` (240 MHz); "skew" and "scd21_worst" 0.0.
    - "exact"[str(n)]: the same two even parts from cs2d's pair on the exact cut with the mask; the replica gives −2.1486 Ω and −0.0078 dB at n 2, and the physics review's mesh replica about −2.50 Ω at n 2 on λ/40.
    - "code" and "versions".
  - **Steps:** "base" is `p4.project(out, "p4b_ms90")`; "repeat" is the same with tag "rep"; "shift", "gapp" and "gapm" are `BOARDS[p4.N]`'s boards; "null" is `NULL`, which returns without a run when `null_equal` holds; "vbase" is `p4.project(out, VICTIM)` and "vshift" is `BOARDS[p4.N]["vshift"]`. Each runs at `p4.N`, `p4.RULE` and `p4.DIELECTRIC`; p0.step returns P4-B's or P4-C's record for "base", and P4-B's B4 record for "vbase", when its key is the same.
  - **`measure(out)`:** {"key": f"{p4.N}-{p4.RULE}", "pairs": {step: p4.deltas(base, variant)} with "vshift": p4.deltas(vbase, vshift) (both hold the victim, so their fingerprints agree and the rows include next and fext), "null_equal", "invalid": the steps whose run is not valid}.
  - **`decide(m, refs)`:** noise at refs["model_even"][m["key"]], then thresholds.
    - The verdict is "fail" on an invalid run ("<step>: valid"); else "incomplete" while a pair is missing (vshift included), or the null differs and its pair is missing; else "pass" when every constant is kept, else "widened". The design's fallback is that rule itself.
    - It returns `{"noise", "thresholds", "verdict": {"value", "fails"}}`.
- [ ] **Step 5: `tools/p4f.py`.** Module docstring:

  > P4-F, the positive control (Stage 4 design 5.11; plan 4 rulings F-1 to F-3). It runs usb2_hs, its neck-down and its plane gap at new's values and P4-B to P4-D's settings, under the ring rule, compared through their runs. The rows each case is built to move are judged against `tests/fixtures/p4f/criteria.json` with P4-E's thresholds, and p4f.json and p4f.md are written in <out>/p4f. Run: `python tools/p4f.py --out DIR [--steps usb2_hs,usb2_hs_neck,usb2_hs_gap]`.

  - **`measure(out)`:**
    - {"neck": p4.deltas(base, neck), "gap": p4.deltas(base, gap)};
    - "neck_short": the neck reading's own highest level's mark (`levels[1][2]`); "base_short": the base's two marks;
    - each run's verdicts, t_stop and times, and "invalid";
    - "dc": `p4d.dc_check` of each layout against `p4d.REFERENCES`' entry (D-2);
    - "thresholds": `<out>/p4e/p4e.json`'s, with "floor_db" from `p4e.CRITERIA` (SystemExit "run P4-E's report first" without it).
  - **`decide(m, t)`:** fails are "neck: tdr_highest" (delta < neck_factor·DIFF_OHM), "gap: scd21_worst" (|delta| ≤ DB, or max(base, variant) ≤ floor_db) and "<step>: valid"; "neck: short mark" (neck_short False) is an owner item. It returns `{"neck", "gap", "verdict": {"value": "pass" | "fail", "fails", "owner"}}`.
  - **`write`:**
    - P4F-1: the judged rows, the neck's own mark against the base's, and P4-E's thresholds;
    - P4F-2: every other row of both pairs, recorded, rendered by `english("I_SI_COMPARE_*", ...)` from `si_delta_lines` with the base's project;
    - P4F-3: the runs, their t_stop against T_max and the ceiling, DC checks and times;
    - the references' soft notes.
- [ ] **Step 6: Run them again,** then `tools/p4e.py --references` as Task 5's Step 5, then Step 3's command again. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add tools/p4e.py tools/p4f.py tests/test_p4e.py tests/test_p4f.py tests/fixtures/p4e tests/fixtures/p4f
git commit -m "test(p4e,p4f): gates P4-E and P4-F, the noise per quantity with the gap's curvature on the run's own mesh taken out where a model holds and the thresholds at three times it, the null edit by its spec hash, and the positive control judged on the rows each case moves and the neck's own mark, with their criteria and references committed before any run (Stage 4 design 5.8, 5.11; plan 4 rulings E-1, E-2, F-1 to F-3)"
graphify update .
```

---

### Task 9 [run]: Block 0's smoke run in TEMP, the references and the freeze

The controller's. Nothing here is committed but stale references (Step 3).

- [ ] **Step 1: The smoke, before the freeze,** Task 10's template in one background call, waited on, with `$g` at `Join-Path $env:TEMP 'krs-plan4-smoke'` (a fresh folder: remove it first), floor 12, and the script written in the same call after the folder is made: `Set-Content -Encoding utf8 "$g\smoke.py" -Value @'…'@` with the code below, then `& .venv\Scripts\python.exe -X utf8 "$g\smoke.py" $g *> "$g\logs\smoke.log"` in the template's run line.

```python
import json, sys
from pathlib import Path
sys.path[:0] = ["tools", "tests"]
import p0, p4, p4d
from test_p4_fixtures import P4_NEW
out = p4.enter(Path(sys.argv[1]))  # TEMP: its own data folder and calibration
refs = json.loads(p4d.REFERENCES.read_text(encoding="utf-8"))
for board in [b for b in P4_NEW if not b.startswith("usb2_hs")]:
    code, _ = p0.cli("cost", str(p4.project(out, board)[1]))  # p4.EDITS apply
    print(board, "cost", code, flush=True)
for board, kw, dc in (("si_pad_coupon_tall", {"tag": "v"}, True), ("si_line100", {}, True), ("usb2_hs", {}, True),
                      ("si_line100", {"dielectric": "debye", "extra": {"t_max_s": 2e-9}}, False)):
    name, pj = p4.project(out, board, **kw)
    if kw.get("tag") == "v":
        p4d.make_vertical(pj, p4d.VERTICAL[board])
    rec, m = p4.run_step(out, name), p4.measure(out, name)
    print(name, rec["result"]["exit"], [j["verdict"] for j in m["jobs"]], m["t_stop_s"], m["valid"], flush=True)
    if dc:
        print(name, "dc", p4d.dc_check(pj, refs["dc"][board]), flush=True)
run = p0.run_path(m["run_dir"])
spec, job = (json.loads((run / f).read_text(encoding="utf-8")) for f in ("model.json", "job-1-P1/job.json"))
print("debye poles", {len(x["debye"]["f_relax_hz"]) for x in spec["materials"] if "debye" in x}, "t_max", job["t_max"])
```

  Expected, about 1.2 h:
  - every cost exits 0, with no E_DT_FLOOR, E_PORT_*, E_UNUSED_PRIMITIVE or E_FIT2D;
  - the tall vertical run, the lossless line and usb2_hs converge, valid, each DC check ≤ 0.01;
  - the 2 ns Debye run exits 0 with its jobs "t_max" at 2 ns (its 2 ns window still holds the pulse there: the ring rule's stop path), S kept, job.json's t_max 8e-9 and four poles per Debye material.

  A DC miss stops the plan for a controller ruling: design §5.4's DC-free fallback (r2 §2's outline, about 60 lines) becomes a code task before the freeze. Any other failure is debugged with superpowers:systematic-debugging and fixed test-first in its task's module, in its own commit, then this step again.
- [ ] **Step 2: The suites.** After a smoke fix only, the full suite in the background; else Task 8's run stands. Then `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass; record the counts.
- [ ] **Step 3: The references and the freeze.**
  - For each of p4b, p4c, p4d and p4e, compare its references.json's "code" with `git rev-parse HEAD:src`. Where they differ (a smoke fix touched src), delete the file, run that tool's `--references` as Task 5's Step 5, run its test file, and commit them in one tests commit, the full suite first: `git commit -m "test(gates): the references written again on the frozen code before any gate run (plan 4 Global Constraints)"`. Record which in the ledger.
  - Record `git rev-parse HEAD:src` in the ledger. src is frozen from here to Task 14's last report. Delete the smoke folder.

---

### Task 10 [run]: P4-B

Each block is one PowerShell call in the background, waited on, from this template. Each step names `<block>`, `<tool>`, `<steps>` and `<floor>` (GB):

```powershell
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"; $g = Join-Path $HOME "krs-gates-si"
New-Item -ItemType Directory -Force "$g\logs" | Out-Null; $t = Get-Date
$free = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
"<block> start $($t.ToString('s')) free $free GB" | Add-Content "$g\logs\ledger.txt"
if ($free -lt <floor>) { "<block> not started: $free GB free" | Add-Content "$g\logs\ledger.txt"; exit 9 }
& .venv\Scripts\python.exe -X utf8 tools\<tool>.py --out $g --steps <steps> *> "$g\logs\<block>.log"
$code = $LASTEXITCODE; $free = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
"<block> $($t.ToString('s')) $((Get-Date).ToString('s')) exit $code free $free GB" | Add-Content "$g\logs\ledger.txt"
```

**The template's rules:**
- `<floor>` is 12 for a block predicted over 1 h, 8 for a shorter one, 17 for B3′.
- A report is the template's first line, then `& .venv\Scripts\python.exe -X utf8 tools\<tool>.py --out $g`.
- Exit 9: tell the owner the free RAM, and start the block again once its floor holds; never lower a floor.
- A block that exits 1 names its failed step in its log: superpowers:systematic-debugging, never a blind rerun.
- A reaped block is reported to the owner and restarted only on the owner's word. Its finished steps are kept, and its orphaned run folder is named in the report.
- A graceful stop's `$g\STOP` is deleted before the next block.
- **After each block, a checkpoint in the plan's ledger:** the exit, each step's verdicts, validity and t_stop, its predicted time (to t_stop and to T_max, from cost's formula) against measured, any loaded step, and any orphaned run folder.

The times assume 190 MC/s a job above 2.5 M cells and 146 MC/s (−30 %, r4's risk 4) below, 2 jobs at once, dt 1.08 × its reference, and jobs stopping near 4 ns on the 60 mm coupons, 5–5.5 ns on the 100–110 mm lines and 3 ns on usb2_hs. On the likely path (n 2, λ/80 from C1, lossless) the gates take about 19 h expected and 39 h worst with Block 0, and about 1.2 h and 2.6 h more for P4-E's victim pair (the controller's ruling on open issue 10); n 3 adds about 15 h and 32 h.

- [ ] **Step 1: Block B1,** `<tool>` p4b, `<steps>` p4b_ms90-n2, floor 8. About 13 min (29 min to T_max). **CP-B1:** the report's ms90 zdiff check. "blocked" is a pipeline bug: stop for systematic debugging and a ruling on the freeze.
- [ ] **Step 2: Block B2,** `<steps>` p4b_ms90-n3,p4b_ms100-n2,p4b_ms100-n3,p4b_sl90-n2,p4b_sl90-n3, floor 12. About 2.5 h (5.7 h to T_max): tell the owner first. **CP-B2: n** (B-6, as this plan's ruling reads it).
  - The interim report's `decisions.mesh_n` decides it, each coupon's plateau over its own mesh's fit2d Zdiff.
  - If it is 3: set `p4.N = 3` (a tools commit, the full suite first: `git commit -m "chore(p4): mesh n 3 for every later gate, as P4-B's FDTD moved more than 1 % from n 2 to n 3 net of fit2d's own move (plan 4 ruling B-6; controller recommendation, owner unavailable)"`). Every later block runs at n 3; P4-E takes its "3" boards.
  - A next, fext or valid fail stops for a controller ruling.
- [ ] **Step 3: Block B3,** `<steps>` p4b_ms90_45-n2,p4b_ms100_45-n2 at n 2 whatever `p4.N` is (B-4), floor 12. About 2.5 h (5.6 h to T_max), 10.1 and 9.9 M cells, about 1.7 GB a job: tell the owner first. **CP-B3: the 45° rule.**
  - "warn": go on.
  - None (a twin missed at n 2): ask the owner for B3′. With the owner's go, Block B3′ runs `<steps>` `<twin>-n3` for each twin that missed, floor 17: the product sizes a 21.7 M-cell job at 3.7 GB (MB_PER_MCELL 170) where r1 measured 7.5 GB, so it starts 2 jobs. Its first command is that twin's n 3 `cost` (`p0.cli("cost", ...)` on `p4.project(out, twin, n=3)[1]`): E_FIT2D_FINE at no more than 5 % goes into `p4.EDITS` as Task 3's rule says, any other block records the twin "blocked". About 3.9 h expected and 8.7 h worst a twin, 15 GB: with the reaper's pressure kill disabled at the owner's start, or at an hour the owner names.
  - No go by P4-F's report: set `p4.BENDS_N3 = "declined"` in a tools commit; the 45° rule is the owner's and W_STAIRCASED stays.
- [ ] **Step 4: Block B4,** `<steps>` p4b_ms90_vic-n<N>,p4b_ms90_cut-n<N>, floor 8 (12 at n 3). About 35 min (1.3 h to T_max).
- [ ] **Step 5: The P4-B report.** The p4b report, then `docs/validation/<date>-p4-b.md`, with `<date>-p4-b.json` a byte copy of `p4b.json`. Its sections, in order:
  1. The verdict and any fallback taken.
  2. Inputs: the commands with `<GATES>` and `<openEMS folder>`, the versions, the fresh calibration (no host key), the boards and their edits.
  3. Measured against limits: P4B-1 to P4B-3, Zdiff, NEXT and FEXT against the run's own mesh, with the exact cut, KiCad's calculator, FEXT's full band and 50 Ω peak and the launches recorded.
  4. Decisions, each "controller recommendation, owner unavailable": n, the 45° rule, the cut victim.
  5. Stated limits and deviations: fit2d's own n 2 to n 3 move per coupon (the ms100 replica read +1.05 %) and each n's error against the exact cut; the launches' blur; B-2's recorded KiCad figure; the victim case outside compare, its fingerprints differing by design.
  6. Machine time per block, predicted against measured.
  7. Next step.

  It holds no path and no host name. The suite run of the last tools commit stands (a docs-only commit), then `git commit -m "docs(validation): gate P4-B, the coupled coupons, n and the 45 degree rule (Stage 4 design 5.11; controller recommendation, owner unavailable)"`, then `graphify update .`. If B3′ runs later, the report is amended in a docs commit before Task 15.

---

### Task 11 [run]: P4-C

Blocks follow Task 10's template with `<tool>` p4c, at `p4.N`.

- [ ] **Step 1: Block C1,** `<steps>` p4b_ms90-dfill,p4c_l90-l40,p4c_l90-dfill,p4b_ms90-l80,p4c_l90-l80, floor 12. The λ/80 arm runs with the rule's runs: the Yee grid's phase error predicts λ/40's miss (about 0.021 against the d fill on 60 mm, 0.014 on 40 mm). At n 2: 5.98, 1.69, 7.88, 2.46 and 2.93 M cells, about 2.8 h (6.2 h to T_max): tell the owner first. At n 3 about 6.4 h (14 h). **CP-C1: the rule.**
  - "l40": go to C3.
  - "l80" or "dfill": set `p4.RULE` in a tools commit: `chore(p4): the SI rule <l80 | dfill> for every later gate (plan 4 ruling C-2; controller recommendation, owner unavailable)`.
- [ ] **Step 2: Block C3,** `<steps>` p4c_step75,p4c_step35, floor 8. About 40 min (1.3 h to T_max) at λ/80. **CP-C3:**
  - pass: go on;
  - "blocked" (a plateau or Γ miss against the same-mesh fit2d): stop, as P4-B's zdiff, for systematic debugging and a ruling;
  - a delay "fail": the pre-registered refinement the report names. "l80": `p4.RULE = "l80"` in a tools commit, C3 again. "n3": `p4.N = 3`, C1 to C3 again. A second miss goes to the controller.
- [ ] **Step 3: The P4-C report,** `docs/validation/<date>-p4-c.md` and `.json`, Task 10's sections.
  - §3 holds the pairs' |ΔS| and delays beside the dispersion estimate and each rule's route-length limit, the steps' plateaus, Γ and delay, and their levels' marks: the short-feature rule's true negative (a mark is an owner item).
  - §5 states C-4: shared mesh lines change no code. p4e_gapp's run edge lies 25 µm from its pads' inner edges (41.7 µm on p4e_gapp3), recorded with its fit2d reading; fit2d and the edge lint block what such edges spoil; merging them or exempting a feature is an owner item. It also states the rule's route-length limit and that VIA_MARGIN_MM stays unvalidated (no pair crosses a via).
  - Commit (docs only): `docs(validation): gate P4-C, the SI mesh rule against the d fill and the TDR's step lines (Stage 4 design 5.11; controller recommendation, owner unavailable)`.

---

### Task 12 [run]: P4-D

Blocks follow Task 10's template with `<tool>` p4d, at `p4.N` and `p4.RULE`.

- [ ] **Step 1: Block D1,** `<steps>` si_pad_coupon-h,si_pad_coupon-v,si_pad_coupon_tall-h,si_pad_coupon_tall-v, floor 8. About 16 min (36 min to T_max). **CP-D1:** the port outcome, "kept", "graded" or "ruling". "ruling" stops for the controller: no blanket refusal (D-5).
- [ ] **Step 2: Block D2,** `<steps>` si_line100,si_line100-debye, floor 8. About 48 min (1.6 h to T_max) at λ/80, the Debye run about 3.7 times the lossless. **CP-D2:** il_ok and its worst ratio, dc_loss, w, f_usb and the predicted slowdown, and the DC check on every lossless P4-D project. A DC miss stops for the controller.
  - Inside [1.25, 1.75]: Block D3 runs `<steps>` usb2_hs,usb2_hs-debye, floor 12, about 1.5 h.
  - **CP-D3: the dielectric.** If it is "debye", set `p4.DIELECTRIC = "debye"` in a tools commit: `chore(p4): the Debye dielectric for every later gate (Stage 4 design 5.3's rule; controller recommendation, owner unavailable)`. P4-E's base step then runs its own project.
- [ ] **Step 3: The P4-D report,** `docs/validation/<date>-p4-d.md` and `.json`.
  - §3 holds the ports and their launches, DC, the Debye accuracy with its worst ratio and frequency, and the lossless twin's IL floor.
  - §4 holds the port decision, the dielectric default and the pole count.
  - §5 says the plateau tests the vertical port's impedance scale, not its launch; the Debye update runs on one openEMS thread, so w holds at the calibration's threads; a Debye run's DC point carries its slowest pole's tail and refreshes no level. On an accuracy miss, the isolation twin of plan 1's open issue 3 is the owner's (this plan's ruling).
  - Commit (docs only): `docs(validation): gate P4-D, the vertical port, the DC point and the Debye dielectric's accuracy and cost (Stage 4 design 5.11; controller recommendation, owner unavailable)`.

---

### Task 13 [run]: P4-E

- [ ] **Step 1: Block E1,** `<tool>` p4e, `<steps>` base,repeat,shift,gapp,gapm,null,vbase,vshift, floor 12. At n 2 and λ/80 about 2.8 h (6.2 h to T_max), the base being C1's p4b_ms90-l80 run and the vbase B4's run when the settings are equal; the null returns without a run when its hash is the base's. Tell the owner first. **CP-E:** the noise per quantity, its parts, and the thresholds kept or widened.
- [ ] **Step 2: The P4-E report,** `docs/validation/<date>-p4-e.md` and `.json`.
  - §3 holds every pair, each quantity's repeat, shift and even part against the mesh model's (the exact cut's beside it), and the odd part, with the rows that take no gap term named. It says whether the repeat was bit-identical.
  - §4 holds the five thresholds.
  - §5 says the noise rests on one coupon and its victim twin (as P3-D's did on one); DB is measured on Sdd11 and Scd21, and on NEXT and FEXT through the victim coupon's one-cell shift alone, with no gap term there (no model); SE_OHM is scaled; DIFF_OHM and SE_OHM are also the short-feature rule's band; and p4e_gapp's 25 µm edge gap.
  - Commit (docs only): `docs(validation): gate P4-E, the noise floor and the significance thresholds (Stage 4 design 5.8, 5.11; controller recommendation, owner unavailable)`.

---

### Task 14 [run]: P4-F

- [ ] **Step 1: Block F1,** `<tool>` p4f, `<steps>` usb2_hs,usb2_hs_neck, floor 12. About 1.4 h (4.2 h to T_max) at λ/80; the base is D3's run when it ran.
- [ ] **Step 2: Block F2,** `<steps>` usb2_hs_gap, floor 12. About 4.2 h at n 2 and λ/80 by plan 3's measured run, its jobs converging near 20.5–23.5 ns under the ring rule, and 6.9 h to its 36 ns ceiling: tell the owner first, and run it alone. At n 3 about 8.6 h (14 h): tell the owner first (ruling R-1). **CP-F:** the verdict.
  - If the gap's jobs end "t_max" at 9 ns while their residual falls faster than 0.3 dB/ns (a fault of the ring rule's run-on path), F2 runs again with `t_max_s` 32 ns in `p4.EDITS` (plan 3's R8-1), a recorded deviation from F-3 with no src change.
  - A fail is design §5.11's "the thresholds hide real effects: refine and repeat P4-E". The controller rules between P4-E at the λ/80 arm or at n 3; this plan's rulings register no third option. A missing short mark is the owner's item, not a refinement.
- [ ] **Step 3: The P4-F report,** `docs/validation/<date>-p4-f.md` and `.json`.
  - §3 holds the judged rows, every other row recorded, each run's t_stop against T_max and the ceiling, and the DC checks.
  - §4 holds the verdict, with the short-feature rule's FDTD check: the neck run's own mark as its true positive (the base's levels already short), P4-C's unmarked step plateaus as its true negative.
  - §5 holds the soft notes against the ladder model.
  - Commit (docs only): `docs(validation): gate P4-F, the neck-down and plane-gap positive control (Stage 4 design 5.11; controller recommendation, owner unavailable)`.
  - src's freeze ends here. `<GATES>` stays until the Stage 4 exit record, as plan 5's acceptance may reuse its projects.

---

### Task 15 [decision]: The cost refit

**Files:** Modify `runs.py` (`SI_SPEED`, `DEBYE_WEIGHT`), `tests/test_cost_model.py` and `tests/test_si_cost.py`. Create `docs/validation/<date>-p4-refit.md` and `.json`.

- [ ] **Step 1: The fit,** in one call: `$env:PYTHONPATH = "tools"; $g = Join-Path $HOME "krs-gates-si"; & .venv\Scripts\python.exe -X utf8 -c "import json, p4; from pathlib import Path; w = json.loads((Path(r'$g') / 'p4d' / 'p4d.json').read_text(encoding='utf-8'))['debye']['w']; p4.refit_record(p4.enter(Path(r'$g')), w, Path('docs/validation/<date>-p4-refit'))"`.
  - The record gives `<s>`, si_speed from every lossless run row; its range; its by-pool medians; and `<w>`, P4-D's weight. r3 expects about 0.55.
  - The cause K-1 names (openEMS compressing the uniform probe's operator) goes in the record only if the gates' job logs show it: search them for openEMS's count of unique SSE operators and quote what is found; without it the record says the cause is unconfirmed.
- [ ] **Step 2: Write the product's failing tests.** The literal pins move: `runs.SI_SPEED == <s>` in test_cost_model and `runs.DEBYE_WEIGHT == <w>` in test_si_cost; every other assertion reads the constants. Run them: FAIL on the old values.
- [ ] **Step 3: `runs.py`.** `SI_SPEED = <s>` and `DEBYE_WEIGHT = <w>`, their comments citing `docs/validation/<date>-p4-refit.md`, `<date>-p4-d.md` and the threads they hold at. Run them again: PASS.
- [ ] **Step 4: Full suite, commit, graph.**

```bash
git add src tests docs/validation
git commit -m "feat(cost): an SI model's speed and a Debye cell's weight refitted from gates P4-B to P4-F (Stage 4 design 5.9; plan 4 rulings K-1, D-3)"
graphify update .
```

---

### Task 16 [decision]: The defaults and the thresholds the gates set

**Files**, by the reports' decisions:
- `core/post/si.py` (the constants); `core/project.py` (add `SI_MESH_N` beside `MESH_N`, `SI_DIELECTRIC`, `make_si_project`); `core/geometry/region.py` (`SI_CELLS`); `cli.py` (`new_si`); `tools/golden_si.py` (`CASES`);
- `core/messages.py`, `po/pt_BR.po`, the `.mo`;
- the tests each branch moves (Step 1); `tests/fixtures/golden_si.json`, by ruling A-1, in the second commit.

- [ ] **Step 1: Write the failing tests,** one per decision taken, before its change. First `grep -rn "0.412576\|0.4141\|2072070\|582291\|λ/40\|usb2_hs_45\|\"lossless\"\|mesh_n" tests` and list in the task's report every hit a decision moves; each is re-pinned here, test-first.
  - **Always:** `tests/test_si_compare.py`'s threshold columns and `test_the_si_delta_lines_and_csv`'s thresholds dict take P4-E's values, re-pinned only where a value moved; tests/test_post_si.py's levels tests where DIFF_OHM or SE_OHM moved (they are levels()' band); `I_SI_COMPARE_THRESHOLDS` renders the new msgid; a new `test_the_thresholds_are_gate_p4es` pins `(DIFF_OHM, SE_OHM, IL_DB, DB, LEVEL_FLOOR_DB, SKEW_PS) == (<d>, <d>/2, <il>, <db>, -50.0, <ps>)`.
  - **mesh_n 3:** `new --interface` writes `mesh.n` 3 at the normal preset and I_SI_DEFAULTS' `mesh_n` reads 3 (test_cli_si.py:54); test_project.py's `si_dict` mesh n (L319); Task 1's pins (test_si_model's `(582291, 2072070)`, test_si_cost's weights); a v1 `new` still writes `MESH_N["normal"]` 2.
  - **rule l80:** `si_max_cell(10e9, 3.3) == pytest.approx(0.206288)` (test_mesh_rule.py:973, λ/80); test_cli_si.py:51 and :54 (about 0.207, "λ/80"); Task 1's pins.
  - **rule dfill:** `new --interface` writes `max_cell_mm` null and I_SI_DEFAULTS renders its d-fill text (test_cli_si.py:51, :54); test_si_model.py:30 (the d fill now); test_si_run.py's `test_an_si_fingerprint_leaves_out_what_the_lines_set` (both None); test_si_geometry's builds at the project's max_cell; Task 1's pins.
  - **dielectric debye:** `new --interface` writes "debye" (test_cli_si.py:34, :54; test_project.py:317); test_si_model.py:23 (a Debye material on each lossy substrate); Task 1's lossless asserts (`debye_cells(usb[2].spec) == 0`, no I_SI_COST_DEBYE on a default project).
  - **staircase n3:** usb2_hs_45's `new` writes mesh.n 3 and prints I_SI_STAIRCASED_N3 {nets}; usb2_hs keeps n 2; test_si_run.py:153's fingerprint pair now differs by mesh.n, asserted so.
  - **staircase refuse:** usb2_hs_45's `new` raises E_SI_STAIRCASED {net: "USB_D+"} (code and params) and writes nothing; test_si_geometry.py:108 and test_si_run.py:153 take usb2_hs_45's board through `build_geometry` or another fixture; `golden_si.CASES` drops usb2_hs_45.
  - **port graded:** a mini board (`mini_board_file`) whose end pad has only a plane 1.51 mm under it raises E_SI_LONG_PORT {name, length_mm, limit_mm}. usb2_hs's 0.2 mm vertical ports still pass.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_si.py tests/test_si_compare.py tests/test_cli_si.py tests/test_project.py tests/test_si_model.py tests/test_si_cost.py tests/test_si_run.py tests/test_si_geometry.py tests/test_mesh_rule.py -q`. Expected: FAIL on each decision's test.
- [ ] **Step 3: The changes,** each SI-only, with v1's and the antenna's constants untouched.
  - **Always:** si.py's `DIFF_OHM, SE_OHM` and `IL_DB, DB, LEVEL_FLOOR_DB, SKEW_PS` take P4-E's values. Their comment becomes "gate P4-E (`docs/validation/<date>-p4-e.md`): the design's value where the model's noise lay under a third of it, else three times that noise; SE_OHM = DIFF_OHM/2; DIFF_OHM and SE_OHM are also levels()' band".
  - **mesh_n 3:** add `SI_MESH_N = 3` beside `MESH_N` in `core/project.py`; `make_si_project` writes `max(MESH_N[preset], SI_MESH_N)`.
  - **l80:** `SI_CELLS = 80`, and I_SI_DEFAULTS' "(λ/40 at f_max" becomes "(λ/80 at f_max", in en and pt-BR.
  - **dfill:** `new_si` writes `max_cell_mm=None`, and its I_SI_DEFAULTS line takes the d-fill msgid of Step 4's table, without `max_cell_mm` and `eeff`.
  - **debye:** `SI_DIELECTRIC = "debye"`.
  - **staircase n3 or refuse:** `new_si` reads `sections(board, <the measured lines' nets>, pieces)`'s W_STAIRCASED notes, the rule the warning already applies: n 3 with I_SI_STAIRCASED_N3 {nets}, or E_SI_STAIRCASED {net} for the first.
  - **graded:** `new_si` refuses a port with a "plane" reference longer than W_SI_LONG_PORT's limit (λ/20 at f_max in the stack's highest εr), raising E_SI_LONG_PORT {name, length_mm, limit_mm}. A horizontal port keeps the warning.
- [ ] **Step 4: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_SI_COMPARE_THRESHOLDS (always) | Resolved means larger than the significance threshold: {ohm} Ω on a TDR level, {il_db} dB on Sdd21 or S21, {db} dB on Sdd11, S11, Scd21, NEXT and FEXT where the higher of the two levels stands above {floor_db} dB, and {ps} ps on the skew, each the design's value or three times the model's noise that gate P4-E measured, whichever is larger. | Resolvido significa maior que o limiar de significância: {ohm} Ω num nível do TDR, {il_db} dB em Sdd21 ou S21, {db} dB em Sdd11, S11, Scd21, NEXT e FEXT onde o maior dos dois níveis fica acima de {floor_db} dB, e {ps} ps no skew, cada um o valor do design ou três vezes o ruído do modelo que a checagem prévia P4-E mediu, o que for maior. |
| I_SI_DEFAULTS (dfill branch) | Preset {preset} (provisional default), T_max {t_max_ns} ns, stop window {window_ns} ns, mesh n {mesh_n} with the cell d throughout the protected extent (gate P4-C), dielectric {dielectric}, timestep floor {dt_floor}, region and protected reach {reach_h} substrate heights ({reach_mm} mm). | Predefinição {preset} (padrão provisório), T_max {t_max_ns} ns, janela de parada de {window_ns} ns, malha n {mesh_n} com a célula d em toda a extensão protegida (checagem prévia P4-C), dielétrico {dielectric}, piso do passo de tempo {dt_floor}, região e alcance protegido de {reach_h} alturas de substrato ({reach_mm} mm). |
| I_SI_STAIRCASED_N3 (n3 branch) | {nets} have copper that is not axis-aligned, which the mesh staircases: gate P4-B validated a staircased pair at mesh n 3, so this project takes n 3, and a project compared with it needs n 3 too. | {nets} têm cobre que não está alinhado aos eixos, que a malha aproxima em degraus: a checagem prévia P4-B validou um par em degraus na malha n 3, então este projeto usa n 3, e um projeto comparado com ele também precisa de n 3. |
| E_SI_STAIRCASED (refuse branch) | Net {net} has copper that is not axis-aligned (45° segments or arcs), and gate P4-B found a staircased pair outside 5 % of its axis-aligned twin at mesh n 2 and 3. Route the measured lines with horizontal and vertical tracks. | A rede {net} tem cobre que não está alinhado aos eixos (segmentos a 45° ou arcos), e a checagem prévia P4-B achou um par em degraus fora de 5 % do gêmeo alinhado aos eixos nas malhas n 2 e 3. Roteie as linhas medidas com trilhas horizontais e verticais. |
| E_SI_LONG_PORT (graded branch) | Port {name} would reach the plane under its pad across {length_mm} mm, more than λ/20 at f_max ({limit_mm} mm), where gate P4-D found the vertical port off the horizontal one. Add ground copper beside the pad, or lower --f-max. | A porta {name} alcançaria o plano sob a ilha por {length_mm} mm, mais que λ/20 em f_max ({limit_mm} mm), onde a checagem prévia P4-D achou a porta vertical diferente da horizontal. Adicione cobre de terra ao lado da ilha, ou diminua o --f-max. |

- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_sexpr.py -q`. Expected: PASS. test_golden_si fails only on the cases a default moved.
- [ ] **Step 6: The first commit.** The full suite: its only failures are test_golden_si's moved cases, as plan 2's F1 had them (none when no default moved golden_si). Then:

```bash
git add src tests po tools/golden_si.py
git commit -m "feat(si): the defaults and significance thresholds gates P4-B to P4-E set, SI-only (Stage 4 design 5.3, 5.5, 5.8; plan 4 ruling A-1; controller recommendation, owner unavailable)"
graphify update .
```

- [ ] **Step 7: golden_si, by ruling A-1** (only when mesh_n, the rule, the dielectric or the 45° rule moved it). `git status --short src` prints nothing; delete `tests/fixtures/golden_si.json`; `.venv/Scripts/python tools/golden_si.py` records it from this clean src; `.venv/Scripts/python -m pytest tests/test_golden_si.py -q` passes, and only the moved cases' digests changed. Full suite, then `git add tests/fixtures/golden_si.json`, `git commit -m "test(golden): golden_si recorded once from a clean src after the gates' defaults (plan 4 ruling A-1; plan 2's F1b precedent)"` and `graphify update .`.

---

### Task 17 [decision]: The amendments, the design's §5.8, and the close

- [ ] **Step 1: The amendments,** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`. Each bracket is the reports' outcome, each `<x>` their value.
  - **A-58, §5.4,** a bullet after A-53's:
    > "- **The SI mesh after the gates** (Stage 4): gate P4-B ran its 90 Ω and 100 Ω microstrip pairs and its coupled stripline at mesh n 2 and 3. Each Zdiff plateau read within <y> % of fit2d's coupled value on the run's own mesh, and the FDTD's own move from n 2 to n 3, net of fit2d's, was at most <x> % [, so n 2 stayed | , so n 3 became an SI project's default]; fit2d's own move and each n's error against the exact cut are recorded. Gate P4-C compared the SI rule with the d fill on a straight and an L-shaped pair [: λ/40 passed, |ΔS| <x> and the delay within <y> % | : λ/40 read |ΔS| <x>, the Yee grid's phase error, and λ/80 passed with <c> M cells against the d fill's <d> M, so max_cell is λ/80 | : the d fill stays, `mesh.max_cell_mm` null by default]. That phase error grows with the route, so the rule meets |ΔS| ≤ 0.01 up to about <L> mm of route, a stated limit. Its step lines read their plateaus within <z> % and the reflection within <g>. A staircased 45° pair, a 33 mm diagonal between straight runs, read <x> % from its axis-aligned twin at n 2 [: W_STAIRCASED stays a warning | : a measured line off the axes takes n 3, and a project compared with it needs n 3 too | : `new` refuses a measured line off the axes | : the 45° rule stays the owner's, W_STAIRCASED a warning]. Shared mesh lines change no code: p4e_gapp's run edge lies 25 µm from its pads' and fit2d read it at <e> %, and fit2d and the edge lint block what such edges spoil; a merge or an exemption is the owner's. VIA_MARGIN_MM stays unvalidated against the d fill: no gate pair crosses a via (`docs/validation/<date>-p4-b.md`, `<date>-p4-c.md`). (A-58, Stage 4 plan 4: controller recommendation, owner unavailable.)"
  - **A-59, §5.3:**
    - The SI bullet's "one pole a decade from f_max/100 to f_max" becomes "four poles 0.8 decade apart, from f_max·10^−2.2 to f_max·10^0.2, fitted from f_max/100 to f_max (tan δ within 3.2 % of the stackup's on FR-4)".
    - Its "Gate P4-D sets the default." becomes:
      > "A Debye request on a dielectric whose loss tangent is 0 runs it lossless and says so (W_SI_DEBYE_NO_LOSS); a loss tangent the board leaves out reads KiCad's 0.02. Gate P4-D ran a 100 mm line lossless and with Debye: the Debye run's insertion loss less its lossless twin's, which holds the walls' and radiation's, [stayed within | left] max(0.05 dB, 5 %) of scikit-rf's MLine dielectric loss with Djordjevic–Sarkar from 0.1 GHz to f_max (worst <r> of the limit at <f> GHz), with no DC loss above <l>, its slowest pole's tail included; a Debye cell weighs <w> plain cells at <t> threads, since openEMS 0.37 updates Debye materials on one thread, so the USB 2.0 fixture would run <s> times slower [(predicted) | (measured)]: the default is [lossless, Debye an option | Debye]. A run with Debye refreshes no calibration level (`docs/validation/<date>-p4-d.md`). (A-59, Stage 4 plan 4: controller recommendation, owner unavailable.)"
  - **A-60, §5.6 and §5.8:**
    - §5.6's SI-reference bullet gains:
      > " Gate P4-D compared the vertical port with the horizontal one on a QFN pad coupon (0.2 mm) and a two-layer 1.6 mm coupon (1.51 mm) [: both within 1.5 % in the TDR's plateau, so the vertical port keeps the line's impedance scale at both heights; the plateau does not see the launch, which is recorded (worst |S11| <a> against <b>, the launch's TDR peak <p> against <q> Ω on the tall coupon), and W_SI_LONG_PORT still warns past λ/20 | : the 0.2 mm port within 1.5 % and the 1.51 mm one not, so a vertical port longer than λ/20 at f_max in the stack's highest εr is refused (E_SI_LONG_PORT), a horizontal one still warned] (A-60)."
    - §5.8's SI-pulse bullet gains:
      > " The DC point matched the ports' copper connectivity, S = 2P − I with P the projector onto the cut space of the node-by-port incidence, within <x> on every lossless P4-D project and the USB 2.0 fixtures' layouts (a Debye run's DC point carries its slowest pole's tail and is judged by its DC loss), so this section's DC-free fallback is not needed (`docs/validation/<date>-p4-d.md`). (A-60, Stage 4 plan 4: controller recommendation, owner unavailable.)"
  - **A-61, §6.3,** a paragraph after A-52's:
    > "**SI runs whose planes ring** (Stage 4): an SI job's openEMS runs to four times T_max; past T_max the stop rule fits a line to the port residual over its last 3 ns at every sample and lets the job run on while that line falls at least 0.3 dB/ns and reaches the preset's level by four times T_max, ending it otherwise as before (a residual flat, rising, falling slower or reaching the level later), its W_JOB_T_MAX line at the time its S ends. On Stage 4 plan 3's plane-gap variant, which rang past its 9 ns T_max, the rule let the 14 jobs of its 32 ns run and verify run to where they converged (20.5–23.5 ns), the latest projection 23.9 ns and the slopes −0.68 to −2.09 dB/ns (the 9 ns run's 8 jobs never passed T_max); gate P4-F's plane-gap run [converged at <t> ns with no hand edit of T_max | ended at T_max and ran again at t_max_s 32 ns, a recorded deviation]. `cost` names the ceiling and its time (I_SI_COST_RING); W_SI_LONG_RUN still reads the worst case to T_max, since only planes that ring run past it. The ceiling is not in the model spec, so no model hash moves. (A-61, Stage 4 plan 4: controller recommendation, owner unavailable.)"
  - **A-62, §6.4.** The SI bullet's "The cost lines count v1's cells at the calibration's speed, which an SI run refreshes as v1's does" gains "; an SI model runs at <s> times the calibration's own per-job speed until a run at its pool level measures that level (I_SI_COST_SPEED), the ratio gates P4-B to P4-F's runs refitted from the plan's provisional 0.55 (<n> runs, <a>–<b>); a run with Debye refreshes no level". Its "A Debye cell counts as a plain one until gate P4-D measures its weight." becomes:
    > "A Debye cell counts as <w> plain cells, the weight gate P4-D measured at <t> threads (I_SI_COST_DEBYE) (`docs/validation/<date>-p4-refit.md`). (A-62, Stage 4 plan 4: controller recommendation, owner unavailable.)"
  - **A-63, §3.2.** A-57's paragraph's "each resolved above 1 Ω on a differential TDR level and 0.5 Ω on a single-ended one, 0.05 dB on Sdd21, 0.5 dB on the rest where the higher of the two levels stands above −50 dB, and 1 ps on the skew: the design's registered values until gate P4-E sets them" becomes:
    > "each resolved above <d> Ω on a differential TDR level and <d/2> Ω on a single-ended one, <il> dB on Sdd21, <db> dB on the rest where the higher of the two levels stands above −50 dB, and <ps> ps on the skew: the design's values, each kept where gate P4-E's measured noise lay under a third of it and else set at three times that noise (`docs/validation/<date>-p4-e.md`); gate P4-F resolved the neck-down's highest TDR level by <x> Ω, [at least | under] three times the differential threshold, the neck run's own level [marked | not marked] short, and the plane gap's Scd21 by <y> dB (`docs/validation/<date>-p4-f.md`). (A-63, Stage 4 plan 4: controller recommendation, owner unavailable.)"
  - **A-64, §9,** a new section after §9.10: "### 9.11 P4-B to P4-G (Stage 4)" with:
    > "Gates P4-B to P4-F (Stage 4 design §5.11) run through `tools/p4.py` and `tools/p4b.py` to `p4f.py` by the product's CLI in one gates folder, against criteria and references committed before their runs (`tests/fixtures/p4b` to `p4f`), each referred to the 2D solve of the run's own mesh where the design names fit2d. **P4-B** runs coupled microstrip pairs of 90 and 100 Ω and a homogeneous coupled stripline at mesh n 2 and 3, their 45° twins at n 2 and a victim terminated against one cut by the walls: Zdiff within 1.5 % of fit2d's value on the run's mesh, the FDTD's own n 2 to n 3 move within 1 %, NEXT within 0.5 dB of the even/odd model of the mesh's modes on its first lobe, the stripline's FEXT at √(Ze·Zo) on its first lobe at most −40 dB, the 45° twin within 5 %; result <v>. **P4-C** compares the SI rule and its λ/80 arm with the d fill on a straight and an L-shaped pair (|ΔS| ≤ 0.01, delay within 0.5 %), and reads 50→75→50 and 50→35→50 step lines (plateaus within 1.5 % of fit2d, Γ within 0.01, delay within 2 %); result <v>. **P4-D** compares the vertical port with the horizontal on two pad coupons, the DC point with the copper's projector 2P − I (within 0.01), and a 100 mm Debye line's loss over its lossless twin with scikit-rf's MLine (max(0.05 dB, 5 %)), and measures the Debye cell weight and the USB 2.0 fixture's slowdown; result <v>. **P4-E** measures the noise floor on the 90 Ω coupon: the same run twice, the board shifted by one fine cell and the gap moved ± d, its even part less the mesh model's where a model holds, the null edit by its spec hash, and its terminated-victim twin shifted by one fine cell for NEXT and FEXT; result <v>. **P4-F** resolves the neck-down's highest TDR level and the plane gap's Scd21 against the USB 2.0 fixture; result <v>. **P4-G**, EMerge as a second solver, stays the owner's. The reports are `docs/validation/<date>-p4-{b,c,d,e,f}.md` and the refit's `<date>-p4-refit.md`; machine time <h> h against this plan's estimate of about 20 h expected and 42 h worst on its likely path, before its conditional runs. (A-64, Stage 4 plan 4: controller recommendation, owner unavailable.)"
  - **§10** loses nothing. **The Status line** gains at its end: " On <date>, Stage 4's plan 4 amended §3.2, §5.3, §5.4, §5.6, §5.8, §6.3, §6.4 and §9 (A-58 to A-64) the same way."
- [ ] **Step 2: The design's §5.8,** in `docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md`.
  - "Gate P4-E keeps each default whose measured noise proper lies under a third of it, and widens the others to three times that noise (as A-39 did)." becomes "Gate P4-E kept <the kept ones> and set <the widened ones> at three times the measured noise (`docs/validation/<date>-p4-e.md`, A-63); P4-F resolved its positive control at them."
  - Its Status line gains "Amended on <date> by plan 4 with the gates' results (P4-B to P4-F, `docs/validation/<date>-p4-*.md`)."
- [ ] **Step 3: Commit** (docs only). `git add docs/superpowers/specs`, `git commit -m "docs(spec): Stage 1 spec A-58 to A-64 and the design's thresholds from gates P4-B to P4-F (Stage 4 design 5.13; controller recommendation, owner unavailable)"` and `graphify update .`.
- [ ] **Step 4: The suites in both languages:** the full suite in the background, then `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass; record the counts.
- [ ] **Step 5: Close.** The whole-branch review; Step 4 again after any later commit; a local fast-forward of main; delete the branch. Nothing is pushed.

---

## Not in this plan

- **P4-G, EMerge as a second solver:** the owner's (design §5.11, §7), recorded in A-64.
- **Plan 5:**
  - the GUI and the button (design §5.10);
  - the README's SI tutorial on the USB 2.0 fixture;
  - the release check;
  - the acceptance run through the window (design §5.14 item 3; `<GATES>`' usb2_hs projects may serve it);
  - the Stage 4 exit record.
- **A via coupon** (design §6 leaves it to the plan): via stubs resonate near 24 GHz or above on boards up to 1.6 mm (r2), past f_max, so none joins the gates; VIA_MARGIN_MM stays unvalidated against the d fill, as A-58 states.
- **A launch criterion for the vertical port:** the design binds P4-D's port to the plateau and records the launch; a bound on the launch would be the owner's.
- **The Debye isolation twin** (plan 1's open issue 3): on an accuracy miss lossless stays the default, so the twin would explain a miss that changes no default. It is an owner item, with r2 §3's recipe.
- **A fix for shared mesh lines** (C-4): a merge of near-coincident edges or a per-feature exemption is the owner's; fit2d and the lint block what they spoil.
- **A max_cell that follows the route's length:** the rule's route-length limit is recorded instead.
- **Time-gated FEXT:** the first-lobe gate with the full band and the launch's |S11| recorded answers the launches.
- **A compare row for the largest pointwise ΔZ** (r3's O4), and **Debye on the lines' layers only** (r2's open question): the owner's.
- **Design §5.4's DC-free fallback:** written only when Block 0's DC check fails, as its own code task before the freeze.
- **N_TDR and a trust floor:** unchanged, unless P4-C's step plateaus fail late in time, and then by a ruling.
- **arrival()'s own reason for a TDT at half its peak at its first sample** (plan 3's F3): no coupon meets it.
- **Plan 2's and plan 3's other carried items:** check_project's shared-net refusal, E24 as an SI part's default and the G_ wordings; compare reading project.json's current target rather than its fingerprint's: plan 5.

## Controller rulings (2026-11-04; binding)

Each is the architect's reading of the binding rulings, or a new decision, revised after the plan's four reviews. Each is a controller recommendation, made while the owner is unavailable.

- Ruling: G-1 to G-4, B-1 to B-6, C-1 to C-4, D-1 to D-5, E-1, E-2, F-1 to F-3, T-1, T-2, K-1 and A-1 are followed as written, except where a ruling below reads one (B-4's pool, B-6's metric, D-4's None, D-5's λ, E-2's rows, T-2's extension) — they bind — cost if wrong: none.
- Ruling: seventeen tasks; Task 1 is the SI cost (D-3, D-4, K-1) and Task 2 the ring rule alone (T-1, T-2); every code task lands before any run, so src freezes once — G-2, Stage 3's plan 4 — cost if wrong: a reorder.
- Ruling: P4-B judges Zdiff, NEXT and FEXT against the run's own discretised cut, fit2d's coupled z0_mesh and its modes on the mesh lines; the exact cut and KiCad's calculator are recorded — design §5.11 ("against fit2d: a pipeline bug"), B-2, B-3 — cost if wrong: a pipeline bug inside the cut's own mesh error, which fit2d's 3 % gate bounds.
- Ruling: B-6 is read on the FDTD's own convergence: n 3 when a coupon's plateau over its own mesh's fit2d Zdiff moves more than 1 % from n 2 (the reference) to n 3; fit2d's own move and each n's error against the exact cut are recorded; NEXT, FEXT and validity are judged at each n — fit2d's mesh error is not monotonic in n (ms90 +1.00/+0.51/+1.53 % at n 2/3/4), so a raw 1 % rule would set n 3 on where edges fall — cost if wrong: n 2 kept where the discretised cut alone moves Zdiff past 1 %, inside fit2d's 3 %.
- Ruling: NEXT and the stripline's FEXT are judged on their first lobe, f ≤ 2·f_q, FEXT after renormalising to the mesh modes' √(Ze·Zo); the full band, the 50 Ω peak and the launch's |S11| are recorded — B-3 sets no band, and the stripline's via launches turn its NEXT into FEXT above the lobe — cost if wrong: one band.
- Ruling: the coupons' geometry is Task 3's (the 100 Ω pair w 0.25, s 0.28; steps 0.125 and 0.61 mm; the stripline's 0.5 mm clearances, eight stitching vias and STACKUP_SL written out as a literal; a 33 mm diagonal) — B-1, C-3, D-1 — cost if wrong: a coupon redesign.
- Ruling: sections under three resolution lengths (the L-pair's 20 mm legs, the 45° twins' 15 mm runs) carry no plateau: the L-pair is judged on |ΔS| and delay, a twin at its diagonal's centre — design §6 — cost if wrong: none.
- Ruling: Task 3 also generates P4-E's n 3 boards — G-4 — cost if wrong: three unused boards.
- Ruling: the load-and-build tests bound cells (10 %) and dt (5 %) by the replica, then pin each board's lines and λ/40 cell once; `built()` keeps the gates' first settings, so Task 16's defaults leave it as it is — G-4 — cost if wrong: one recording.
- Ruling: a board blocked by E_FIT2D at no more than 5 % runs with gates.fit2d_limit 0.05 through p4.EDITS — Stage 3 ruling 2 — cost if wrong: a looser fit2d gate on one coupon.
- Ruling: p4 reuses p3 through two default parameters; checkpoints are p4's N, RULE, DIELECTRIC, EDITS and BENDS_N3 — G-1 — cost if wrong: a rename.
- Ruling: each board's new arguments live once in P4_NEW, which tools/p4.py imports as golden_si imports si_args — golden_si's precedent — cost if wrong: none.
- Ruling: the gates measure in-process from each run's chain, never through compare; the victim case reads the pair's own 4-port block and calls si_deltas directly, as the two runs' fingerprints differ by design ("ends") — F-1, B-5 — cost if wrong: none.
- Ruling: each step's predicted time is cost's SI formula on the calibration its step saw at its start, pinned equal to the run's I_COST_TIME — G-2 — cost if wrong: none.
- Ruling: SI_SPEED applies in prepare(si=True) while the level equals runs.calibrated_mcs, the figure runs.calibrate stores as levels[pool] and levels["1"]; the refit's reference is that figure — K-1, r3 §4 — cost if wrong: a first SI run's prediction off by the refit's error.
- Ruling: DEBYE_WEIGHT starts at 6.8 over debye_cells, cell_split of the Debye materials (582,291 of 2,072,070 on usb2_hs), and a run with Debye refreshes no calibration level — D-4, D-16 — cost if wrong: a Debye run's speed unrecorded.
- Ruling: W_SI_DEBYE_NO_LOSS names the dielectrics whose loaded tan δ is 0; D-4's None reads KiCad's 0.02 in the importer (Layer.__post_init__), so it runs lossy — D-4 — cost if wrong: none.
- Ruling: the ring rule's ceiling is not in the spec; run_ports gives openEMS 4 × T_max; past T_max the fit is renewed at every sample, since a single extension to T-2's first projection would end plan 3's gap jobs 7–39 % short of their convergence (r3 §3); W_SI_LONG_RUN stays on T_max; a flagged job's line reads its cut — T-1, T-2 — cost if wrong: an old results file read as current.
- Ruling: the ring fixture is the 14 jobs of plan 3's 32 ns run and verify, each with 300 or more samples past T_max; the 9 ns run's 8 never passed it — T-2 — cost if wrong: none.
- Ruling: the fit window stays T-2's 3 ns; a route whose window passes 3 ns may end at T_max as before (a ponytail) — T-2 — cost if wrong: a long ringing route stopped at T_max.
- Ruling: P4-C's λ/80 arm runs in C1 with the rule's runs, the Yee phase error predicting λ/40's miss; the rule's route-length limit is recorded — C-2 — cost if wrong: 41 min when λ/40 passes.
- Ruling: P4-C's step delay is read at the reflection's half heights — C-3 — cost if wrong: one estimator.
- Ruling: C-3's refinement follows the failing check: a plateau or Γ miss against the same-mesh fit2d blocks, as no cell along the line moves it; a delay miss takes λ/80, then n 3; the rule is the more refined of the pairs' and the steps' — C-3 — cost if wrong: a plateau miss read as a pipeline discrepancy.
- Ruling: C-4's shared mesh lines change no code; p4e_gapp's 25 µm edge gap (41.7 µm on gapp3) is recorded with its fit2d reading — C-4 — cost if wrong: real boards with such edges refused until the owner's fix.
- Ruling: D-5's graded refusal lands only on its branch (Task 16), with W_SI_LONG_PORT's limit, λ/20 in the stack's highest εr, the vertical port's own medium, rather than λ_eff — D-5 — cost if wrong: ports between 0.71 and 0.83 mm refused that λ_eff would keep.
- Ruling: P4-D's port passes on the design's plateau; the launch is recorded and A-60 claims only the impedance scale — design §5.11 — cost if wrong: a launch difference unjudged.
- Ruling: the DC reference compares |S| entry by entry against the committed references; Debye runs stay out of the DC set and are judged by their DC loss; a lossless DC miss after the freeze is the controller's — D-2 — cost if wrong: an orientation sign unchecked.
- Ruling: Debye's accuracy is judged on its insertion loss less its lossless twin's — D-1, D-3 — cost if wrong: a wall or radiation loss that Debye changes counted as dielectric.
- Ruling: Block 0 in TEMP runs every new board's cost through p4.project, the tall vertical port, the lossless line and usb2_hs to convergence with their DC checks, and a 2 ns Debye run (the ring's stop path); a DC miss writes §5.4's fallback before the freeze, and stale references are written again before B1 — G-1, G-2 — cost if wrong: about 1.2 h.
- Ruling: the 45° twins run at n 2 whatever N is; n 3 runs per twin that missed, only with the owner's go and 17 GB free, the product sizing two jobs (no option sets a pool of 1, and editing the calibration's pool would skew per_job_mcs and the refit); a blocked n 3 twin reads "refuse"; no go by P4-F's report leaves the 45° rule the owner's — B-4, G-3 — cost if wrong: a day of machine time, or the rule unvalidated.
- Ruling: P4-E follows E-1 on p4b_ms90, with its own base step; the null runs only when its hash differs. The controller's ruling on open issue 10 adds p4b_ms90_vic against its one-cell shift, for NEXT's and FEXT's noise — E-1 — cost if wrong: one run, and about 1.2 h for the victim's pair.
- Ruling: P4-E's gap term subtracts the mesh model's even part (fit2d's coupled Zdiff and its modes' Sdd21 on the run's own lines, per n and rule; the exact cut's recorded) and applies only where a model holds; Sdd21 at f_max and the worst Sdd11, which the launches set, take the repeat, shift and null alone; the design values come from the criteria — E-2 — cost if wrong: a launch-set curvature left out of the noise.
- Ruling: P4-F judges the neck's delta at no less than 3 × DIFF_OHM and the gap's Scd21 resolved; the neck run's own short mark is checked, a miss the owner's item — F-2, plan 3's owner item — cost if wrong: a control read narrowly.
- Ruling: if P4-F's gap ends at T_max while falling faster than 0.3 dB/ns, F2 reruns at t_max_s 32 ns by project edit, a deviation from F-3 with no src change — F-3, G-1 — cost if wrong: a hand edit of T_max.
- Ruling: the Debye isolation twin is not built — an owner item — cost if wrong: a miss's cause unexplained.
- Ruling: Task 16 records golden_si in a second commit from a clean src — A-1, plan 2's F1b — cost if wrong: one commit with test_golden_si red.
- Ruling: a docs-only commit reuses the last green suite at the same src, tests and tools — Global Constraints — cost if wrong: none; the privacy gate runs.
- Ruling: the amendments run A-58 (§5.4), A-59 (§5.3), A-60 (§5.6, §5.8), A-61 (§6.3), A-62 (§6.4), A-63 (§3.2) and A-64 (§9.11), each bracket filled from its report — A-1 — cost if wrong: a paragraph moved.
- Ruling: the new pt-BR follows plan 3's glossary and the catalog's (A rede, tangente de perdas, resíduo nas portas, aproxima em degraus) — pt-BR design §6 — cost if wrong: a few msgstrs.
- Ruling (disclosure): the architect's and the reviewers' probes ran only in scratch folders with the repo's venv and an isolated data folder: coupon replicas through new_si, the 2D table, fit2d and build_model, the Debye fits, the ring rule on plan 3's jobs, the projector, MLine, the even/odd peaks and the estimators on ideal lines; no openEMS, no KiCad binary, no suite — cost if wrong: none.

## Open issues, ruled by the controller (2026-11-05; owner unavailable)

These are the reviser's open issues, each with the controller's ruling. The controller confirmed eleven of the twelve on 2026-11-05 and amended the tenth. Two rulings of the controller's own follow them. Each is a controller recommendation, made while the owner is unavailable. The plan's text above already carries the amendments.

1. **B-6's reading.** This plan reads B-6 as the FDTD's convergence net of fit2d's own move from n 2 to n 3, which departs from the literal raw comparison. On the replica's ms100, fit2d itself moves +1.05 %, so a raw comparison would set n 3 at about 2.3 times the cost with no gain in accuracy.
   **Ruling:** confirmed. n 3 becomes the SI default only when a coupon's plateau over its own mesh's fit2d Zdiff moves more than 1 % from n 2 to n 3. The raw move, fit2d's own move and each n's error against the exact cut are recorded beside it. The rule binds from Task 5's commit of P4-B's criteria.json.
2. **The schedule.**
   - The likely path (n 2, λ/80 from C1, lossless) takes about 19 h expected and 39 h worst with Block 0. That passes design 5.11's 10–25 h, though it is inside r3's 60 h.
   - n 3 adds about 15 h expected and 32 h worst; B3′ about 4–9 h a twin; the conditional D3 about 1.5 h.
   - Each full suite costs about 28 min of wall time between blocks.

   **Ruling:** accepted, with about 1.2 h expected and 2.6 h worst more for issue 10's victim pair. The owner was told 10–60 h. Each report records its time, predicted against measured, and A-64 records the total. A block over 2 h is announced first (ruling R-1).
3. **B3′'s RAM.** The product sizes a 21.7 M-cell job at 3.7 GB (MB_PER_MCELL 170), where r1 estimated 7.5 GB, so it starts two jobs. B3′ therefore needs 17 GB free. B-4's pool of 1 cannot be reached without a change to src.
   **Ruling:** as written. B3′ runs only with the owner's go, since only the owner can free 17 GB or start Claude Code with the reaper's pressure kill off (`CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1`). At CP-B3, the controller tells the owner in pt-BR what B3′ needs: about 3.9 h expected and 8.7 h worst a twin, and 15 GB. If no go comes by P4-F's report, BENDS_N3 is set to "declined".
   - The product's RAM figure is still unmeasured. MB_PER_MCELL is 170, provisional; r1's estimate is about 375 bytes a cell at 20 M cells.
   - P4-B's report states this. It is an owner item, beside P0-C.
4. **The ring rule's run-on path.** It first meets a real worker at P4-F's gap block, after the freeze. A fault there takes the pre-registered fallback, a project edit to t_max_s 32 ns, which deviates from F-3.
   **Ruling:** as written. Block 0's 2 ns Debye run shows that openEMS is given the ceiling (job.json's t_max) and that the stop path works. The ring logic is pinned on plan 3's 14 jobs. F2's fallback stands, and if taken it is recorded as a deviation.
5. **W_JOB_T_MAX's text.** When the ring rule ends a job past T_max, the text still says "reached T_max (t ns)", although t is now the cut.
   **Ruling:** as written. A-61 states that the line's time is where its S ends. If plan 5's Results page shows such a line, plan 5's wording review gives it a message of its own; this is a plan 5 item, beside the G_ wordings.
6. **P4-D's launch.** P4-D's port gate cannot see the launch, so "graded" is unlikely to trigger.
   **Ruling:** as written. The launch is recorded, and a launch criterion is an owner item.
7. **The mesh-model numbers** come from the physics review's 2D replica.
   **Ruling:** as written. A references test that misses its replica number stops its task, BLOCKED with both values and the formula, for a ruling. No assertion loosens.
8. **The staircase "n3" branch.** Under it, a 45° variant compares with its straight twin only when both run at n 3.
   **Ruling:** as written. I_SI_STAIRCASED_N3 says so.
9. **E_SI_LONG_PORT's λ.** It uses W_SI_LONG_PORT's λ/20 in the stack's highest εr (0.707 mm at 10 GHz), not D-5's λ_eff/20 (about 0.83 mm).
   **Ruling:** as written. One limit serves the warning and the refusal. If the graded branch is taken, A-60 states that ports between the two lengths are refused.
10. **P4-E's DB on Sdd11 and Scd21 alone.** NEXT's and FEXT's noise was inferred rather than measured, and the ±d term is skipped on Sdd21 at f_max and the worst Sdd11.
    **Ruling:** amended.
    - P4-E adds P4-B's terminated-victim coupon against itself shifted one fine cell, so NEXT's and FEXT's own mesh noise joins DB's. Compare judges them with DB.
    - Task 3 generates p4e_vshift and p4e_vshift3. Tasks 8 and 13 add the steps vbase and vshift.
    - The victim's pair takes no gap term, as no model holds there.
    - The ±d term stays skipped where the launches set the row.
11. **p4e_gapp's 25 µm edge gap.** The replica read it unblocked, at +0.66 % at n 2 and +2.27 % at n 3.
    **Ruling:** as written. A block of p4e_gapp or p4e_gapp3 by E_FIT2D at no more than 5 % goes into p4.EDITS by Task 3's rule, recorded. A larger block stops Task 3 for a ruling.
12. **Plan 2's and plan 3's other carried items:** check_project's shared-net refusal, E24 as an SI part's default, the G_ wordings, and compare reading project.json's current target.
    **Ruling:** they stay with plan 5.

**Ruling R-1, the owner's go.** The owner's standing instruction is the go for every block of Tasks 9–14, a block over 8 h included: not to stop to ask, and to follow the controller's recommendations.
- Before a block predicted over 2 h, the controller tells the owner in pt-BR, then starts it once its RAM floor holds.
- A block under its floor waits and starts again once the floor holds. A floor is never lowered.
- B3′ alone waits for the owner's explicit go (issue 3).
- A reaped block is reported, and restarted only on the owner's word.

The Global Constraints, Task 10's template rules and Task 14's F2 carry this ruling.

**Ruling R-2, the victim under a shift.** `pair_coupon`'s AUX victim and its pads take `shift` like every other coordinate, as its docstring says. Task 3's variant test checks the vshift pads against p4b_ms90_vic's.

**Owner items this plan adds,** each a controller recommendation until the owner reviews it:
- A-58 to A-64;
- the defaults and thresholds the gates set;
- the 45° rule, if it stays the owner's;
- a launch criterion for the vertical port;
- the product's RAM per cell (MB_PER_MCELL, beside P0-C);
- the Debye isolation twin;
- the fix for shared mesh lines;
- the native review of the new msgstrs: tangente de perdas, teto, resíduo nas portas, aproxima em degraus.

**A stop in any task.** A prototype number the code misses, a pin that moves, a board that blocks outside Task 3's rule, or a fixture that refuses is reported BLOCKED with both values and the formula that differs, and the controller rules. No limit and no assertion loosens to pass.
