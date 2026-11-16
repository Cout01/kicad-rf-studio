# Stage 5 Plan 3: The Emission Kind, Gate E-A and the Go/No-Go Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Part B's core, kept hidden: a schema-4 "emission" project that `new --emission` writes and `run` simulates as one verify-style driven job on Stage 3's whole-board PML and NF2FF engine, with its stop branch, its far field at 3 m per V and per mA with energy closure, its overrides, fingerprint, n(f) and cost; gate E-A on two closed forms, its criteria frozen before its run; then, only after E-A passes, the go/no-go probe's fixtures, frozen criteria and four runs, whose record decides whether plans 4 and 5 run.

**Architecture:**
- **The pins** (`tools/golden_s5.py`, `tests/fixtures/golden_s5.json`): every shared output this plan's edits reach that the three golden suites do not hash, recorded at `a87bcc1` before any shared edit. The three golden tools and their JSONs stay as they are.
- **The project** (`core/project.py`): `SCHEMA_EMISSION = 4`, `emission()`, the band, the far-field list and `make_emission_project`. `cli.new_emission` sits behind hidden options that a separate parser reads, so the usage line and every existing abbreviation stay as they are. The window refuses a schema-4 file before reading it (G_KIND_LATER), naming no kind.
- **The model:** Stage 3's whole board in air (`board_region`, `air_box`, PML_8), lossless, driven by the emission pulse. The pulse's `"emission": true` is the spec's one emission marker: it picks the stop rule's emission branch and `build_csx`'s NF2FF cap of 64. A termination's `"R"` and the near-field plane are written only in emission specs.
- **The run** (`pipeline`): three jobs in one run folder. The setup job runs on `model_spec`'s spec (`model.json`, whose hash the results, the null check and the fingerprint use); the driven job and the NF2FF transform run on `verify_spec`'s spec (`driven.json`). `stoprule.tail_fit` reads the driven job's waves at its end.
- **The post** (`core/post/emission.py`): the rows, the CSVs, the lines, the limit line, and n(f) with its floor.
- **The overrides** (`core/geometry/overrides.py`): made from one review finding by hidden `new` options, stored as explicit geometry, applied in `pipeline.load` behind `emission(project)` before `build_geometry`, and checked again for clearance at every load.
- **The gates:** `tools/ea.py` runs E-A's two hand-written specs through `p0`; `tools/probe.py` runs the probe's four projects through the product's `run`, one per call. Both key their steps by the product tree and the tools tree, write a record from whatever steps exist, and are tested with the fake worker. Only the controller runs openEMS.

**Tech Stack:**
- Python 3.14 (dev venv 3.14.2);
- numpy, scipy (`signal.find_peaks`, `constants`), shapely, h5py (through `core/post/farfield.py`), all already dependencies;
- pytest, and `tools/catalog.py` (Babel, dev extra).

**Spec:**
- **The design, binding:** `docs/superpowers/specs/2026-11-09-stage5-emc-design.md`, §5.15's plan 3 row. Read with it: §5.1 (a schema-4 project in the review's f_max order), §5.6 to §5.11, §5.12's E-A row and the gates' rules, §5.13, §5.14 (the probe's boards), §5.16's plan 3 amendments, §5.17 items 1 to 3, §6, §7 and §8 risks 1 to 4 and 10 to 13.
- **The controller's decisions** (git-ignored): `.superpowers/sdd/stage5-research/controller-decisions.md`, B1 to B12 and BC3 to BC6.
- **The research** (git-ignored), in `.superpowers/sdd/stage5-research/`: r3-emission, f1 (the stop rule, the loaded Q), f2 (the floor, the runtimes), f3 (the overrides, the fingerprint), r5 (E-A's closed forms), critic, builder-check and design-review.
- **Plans 1 and 2, as merged,** with their rulings files `.superpowers/sdd/2026-11-10-stage5-plan1-rulings-and-minors.md` and `2026-11-16-stage5-plan2-rulings-and-minors.md`; plan 2's E-E record `docs/validation/2026-11-16-e-e-cavity.md`.
- **The Stage 1 spec:** A-1 to A-77. Task 19 adds A-78 to A-83.
- **The pt-BR design:** §5.1 (a whole message per grammar) and §6 (glossary, tone, quoted labels).

**Branch:**
- `stage5-plan3`, from `main` at `a87bcc1`.
- Commands run from the repo root with `.venv/Scripts/python`.
- A path without a folder is under `src/kicad_rf_studio/`.
- Line references are main's at `a87bcc1`. Find a moved line by its quoted text.

**Machine time:**
- E-A (Task 14): 1–2 h by the design (r3 estimated under 0.5 h). `tools/ea.py --cost` predicts it first.
- The probe (Task 17): about 5 h, four runs at about 1.25 h each by f2. `tools/probe.py --cost NAME` predicts each run first.
- Every prediction is the tool's own figure, which already weights the PML (`runs.PML_WEIGHT`) and the small-model speed (`runs.SMALL_SPEED[1]`). E-E's "6.1 times" compared a run with an unweighted figure (`p0.predicted_s`) and is never applied to these figures.
- Each task's suites take about 38 + 6 min. Task 1's pins add about 1–2 min (three fake runs, their costs and a verify), Task 15's guard about 2–3 min (two whole-board probe models).

**Before Task 1 (the controller):**
1. Run `git switch -c stage5-plan3 main`.
2. Commit this plan on the branch.
3. Record the baseline from plan 2's close at `a87bcc1`: 2616 passed and 7 skipped; in pt-BR, 55 passed and 4 skipped.
4. Rule the open issues at the end of this plan. All nine were ruled on 2026-11-16, before Task 1; see "Open issues, ruled by the controller".

## Global Constraints

**From the design (verbatim):**
- §3, anti-goals:
  - "Any change to v1's, the antenna's or SI's model specs, spec hashes or output bytes. `NF2FF_MAX` stays 11 for the antenna."
  - "A pass/fail verdict, a severity tier beyond the catalog's W_ and I_ prefixes, or an absolute emission claim. Every number carries its relative label (§5.8 fixes the units)."
  - "A new dependency."
  - "A fixture that is not synthetic. The public boards f4 measured stay evidence and are never committed. No owner board, file or setting is read."
  - "Pushing."
- §4:
  - "openEMS 0.37.0 and CSXCAD 0.7.0 as installed; Windows 10/11 and Linux; Python 3.14; KiCad 9 and 10 boards. `OLDEST_SUPPORTED` in `core/kicad/board.py` stays as it is."
  - "No new dependency. numpy, scipy (`scipy.sparse`, `scipy.sparse.linalg.eigsh`, `scipy.special`), shapely and matplotlib are already in. kicad-python stays pinned `>=0.8,<0.9`."
  - "Fixtures are synthetic boards built by `tools/make_fixtures.py` under KiCad 9's pcbnew, in the isolated profile of Stage 1 §9.1 (A-3's isolation), as Stage 4 built its own."
  - "Every new message has its pt-BR msgstr in the same commit. Every G_ text keeps the existing rule: no backtick, flag or terminal syntax."
- §5.6:
  - "Every emission-only key is written only in emission specs, so no other kind's spec hash moves (B11)."
  - "Until a go: `--emission` is hidden from the usage line; E_NEW_KIND's text, with its pt-BR, does not name it; the GUI has no emission kind (B10)."
- §5.8: "They are never in dBµV/m. There is never a horizontal limit or margin line, and never a standard's name on a result."
- §5.12: "numerical references are committed as JSON before the gate's runs, and never regenerated during them".
- §5.13:
  - "There is one attempt. A rerun is allowed only for a pipeline bug that a new test reproduces on the first record, and both records are kept."
  - "After the first run, no fixture, band, preset, T_max or criterion changes."

**This plan's own:**
- **Pins** (ruling 2):
  - Task 1 records the shared outputs the three golden suites do not yet hash, before any shared edit.
  - From Task 2 on, `tests/test_golden_v1.py`, `test_golden_antenna.py` and `test_golden_si.py` stay green and unchanged, and so do `golden_v1.json`, `golden_antenna.json`, `golden_si.json` and `golden_s5.json`. Every task that edits src runs them with `-rs`, and on this PC no golden test is skipped.
  - A pin that moves stops the task for a ruling.
- **The `antenna(` calls:** Task 2's Step 1 checks its table against the head. Each later edit follows its assigned side.
- **Imports:**
  - `core/post/emission.py` and `core/geometry/overrides.py` import numpy, scipy and shapely, and never openEMS, CSXCAD, Qt or matplotlib.
  - Only a worker imports openEMS (`build_csx`).
- **Never a real KiCad** (ruling 13):
  - Tests talk only to `tests/fake_kicad.py`; kipy never reaches a real socket.
  - Only Task 15 runs KiCad 9's Python, under A-3's isolation.
  - Qt runs offscreen only.
- **openEMS:**
  - Only Tasks 14 and 17, the controller's, run it outside pytest.
  - Implementer tasks use the fake worker (`fake`, `calibrated`, `p0_out`).
- **The kind stays hidden** (ruling 9): no task adds `--emission` or its variant options to the usage line, names the kind in E_NEW_KIND or in a G_ text, or adds an emission kind to the GUI.
- **Messages:**
  - Every user-facing line is a `CATALOG` code with its pt-BR msgstr, added by the task that first emits it (see Messages).
  - Run `.venv/Scripts/python tools/catalog.py`, set each new msgstr, then run it again.
  - New W_/I_/E_ rows go before `"E_INTERNAL"`; G_ rows after `"G_REFILLED"`; T_FMAX_EMISSION after `"T_FMAX_DEFAULT"`; other T_ rows after the last `T_EXPECT_` row.
  - Numbers and identifiers keep their spelling in pt-BR (`test_sexpr.py`'s KEEP).
  - Gate prose in pt-BR says "checagem", never "verificação".
  - No new or Stage 5 msgid holds "dBµV", "dBuV", "FCC", "CISPR", "margin(s)" or "pass(es, ed)" as a word, but the two released phrases AR-1 allows. Task 2's scan test enforces this from its commit on.
- **Tests:**
  - Write them first. `KrsError` tests check `.code` and `.params`.
  - Tests never write under `tests/fixtures`. The exceptions are Task 1's recording, Task 13's and Task 16's `--criteria` steps, and Task 15's generator.
  - Closed forms are computed in the tests from `scipy.constants` or the formula, never remembered.
- **Suites,** before every commit that touches src, tests, tools, po or pyproject.toml:
  - `.venv/Scripts/python -m pytest -q -rs`;
  - then, in PowerShell: `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q; Remove-Item Env:KRS_TEST_LANGUAGE`.
  - Each runs alone, in the background, and is waited on. **Never run two pytest processes at once.** A docs-only task reuses the previous task's results.
- **Git:**
  - No push. The privacy gate runs on every commit, and `--no-verify` is never used.
  - **No commit message carries a co-author line.** Use the messages as given.
  - No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address, a host name or a private name. Write `<openEMS folder>`, `<KiCad 9 bin folder>` and `<EMC_GATES>`.
  - Read history with `git log --format="%h %s"` only.
- **Files:** every new `.py` starts with `# SPDX-License-Identifier: GPL-3.0-or-later`.
- **Python** runs only with a script, `-c` or `-m`. Never run a bare interactive `python`, never feed one through a pipe or a heredoc, least of all in a background shell. A CLI probe outside pytest sets `LANGUAGE=en`, and `PYTHONUTF8=1` when its output is redirected.
- **Workflow:**
  - Run `graphify query "<question>"` before reading code, and `graphify update .` after each commit.
  - Ponytail: write the smallest code that does what the design says, with a `ponytail:` comment on each corner cut that has a known ceiling.
  - Reuse what exists:
    - `cli._load`, `_port`, `_write`, `_head_notes`, `_part_note`, `_port_note` and `_list`;
    - `board_region`, `air_gap`, `air_cell`, `air_box`, `with_pml`, `pulse`, `pulse_band`, `verify_spec`, `far_field_box` and `cell_split`;
    - `run_ports`, `far_field`, `basis_lines`, `outputs.write`, `read_far_field` and `port_powers`;
    - `p0.enter`, `step`, `records`, `run_model`, `model_of`, `run_path`, `save`, `table`, `versions`, `machine` and `code_id`;
    - `p3a.dipole`, `review_board`, `review_json`;
    - `golden_v1.record`, `sha`, `env`, `CASES`; `golden_antenna._board`, `BANDS`; `golden_si.CASES`; `test_cli_si.si_args`;
    - make_fixtures' `rect`, `square`, `place`, `track`, `arc`, `via`, `fence`, `fence_points`, `to_gnd`, `pad_at` and `decoupled`.

## Review Focus

Each line names the test that pins it and the task that owns that test.

1. **An emission band that holds no far-field frequency.** `--f0 2.4GHz --f-max 4.8GHz` and `--f0 3GHz` (whose capped f_max equals f_lo = 2·f0) are empty; `--band 300MHz:900MHz` holds no carrier harmonic and no point of the 1–6 GHz grid. Each must be refused with E_EMISSION_BAND before anything is written, never a project.json that every later command refuses. Check: Task 3's `test_an_empty_emission_band_is_refused_before_anything_is_written`.
2. **An emission project opened in today's window.** A user who ran the hidden `new --emission` opens its project.json in the GUI. It must read as one plain refusal that names no kind (G_KIND_LATER), with Advanced still showing the file, never E_INTERNAL from the window's v1 branch, which reads `harmonics`. Check: Task 2's `test_an_emission_project_is_refused_by_the_window_and_named_by_no_kind`.
3. **A board edited after its variant was made,** so that an added via now sits on another net's copper. That via must be left out at load with W_OVERRIDE_REFUSED, never a silent short. Check: Task 10's `test_load_applies_the_overrides_and_checks_them_again`.
4. **A tail that is quiet, short, or holds a ring that does not decay, alone or beside decaying ones.**
   - A quiet or short tail fits no ring and truncates nothing.
   - A non-decaying envelope has no Q and truncates every frequency; its decaying neighbours keep their Q.

   Checks: Task 5's `test_a_quiet_tail_and_a_short_one_fit_nothing` and `test_a_held_ring_has_no_q_and_truncates_every_frequency_beside_decaying_ones`.
5. **A hand-edited schema 1–3 project carrying `overrides`, a port `"R"` or `"near_field": true`.**
   - The overrides are refused (E_PROJECT_FIELD).
   - The `"R"` and the plane never reach a v1, antenna or SI spec, so no hash moves.

   Checks: Task 2's `test_overrides_belong_to_schema_4_alone` and Task 4's `test_no_other_kind_writes_an_r_or_a_near_field_plane`.

---

## Messages

The English text is the msgid. The pt-BR text follows the pt-BR design §6 with this glossary:
- emissão relativa; campo distante; plano de campo próximo; onda incidente; fonte;
- fechamento de energia; avaliado; truncado; ressonância; Q ajustado; fator de truncamento;
- variante; alteração (override); vazio preenchido; via adicionada; passo (pitch); isolamento (clearance);
- "não um veredito de conformidade", as I_REVIEW_RELATIVE has it; portadora; harmônico; caixa de ar; absorvedor; tampa; espaçamento de ar; janela, as the existing lines have them.

The new pt-BR terms join the owner's native review.

| Task | Code {params} | EN |
| --- | --- | --- |
| 2 | `T_EXPECT_EMISSION` | the text "emission" |
| 2 | `T_EXPECT_EMISSION_BAND` | a number above band.f_lo_hz |
| 2 | `T_EXPECT_EMISSION_FAR_FIELD_HZ` | a list of 1 to 64 frequencies in Hz, each from band.f_lo_hz to band.f_max_hz |
| 2 | `T_EXPECT_NEAR_FIELD` | false, or true with f0_hz set: the plane records the carrier's harmonics |
| 2 | `T_EXPECT_DRIVEN_R` | absent: the first port is the driven one, a 50 Ω source |
| 2 | `T_EXPECT_OVERRIDES` | a list of fill and via entries as `new` writes them |
| 2 | `T_EXPECT_NO_OVERRIDES` | absent: only an emission project holds overrides |
| 2 | `T_FMAX_EMISSION` | the project band's f_max, at most 6 GHz |
| 2 | `G_KIND_LATER` {path} | {path} is a project of a kind this window does not open. |
| 3 | `I_EMISSION_DEFAULTS` {carrier, f_lo_mhz, f_max_mhz, f1_mhz, preset, t_max_ns, mesh_n, air_gap_mm, boundary, count, step_deg} | Relative emission, not a compliance verdict: carrier {carrier}, band {f_lo_mhz} to {f_max_mhz} MHz, the pulse from {f1_mhz} MHz up to it; preset {preset}, T_max {t_max_ns} ns (2·t0 + 60/f_c), mesh n {mesh_n}, the whole board in air with an air gap of {air_gap_mm} mm (λ/4 at f_lo) to a {boundary} absorber, a lossless dielectric, far-field frequencies: {count}, on a {step_deg}° sphere. |
| 3 | `E_EMISSION_BAND` {f_lo_mhz, f_max_mhz} | The emission band from {f_lo_mhz} to {f_max_mhz} MHz holds no far-field frequency: f_lo is twice the carrier, and the band must run past it and hold a carrier harmonic or a point of the 100 MHz grid from 1 to 6 GHz. Give --f-max above {f_lo_mhz} MHz, or a --band that reaches 1 GHz. |
| 4 | `W_EMISSION_AIR_BOX` {gap_mm, quarter_mm, boundary} | The emission model's air box is outside the tested setting: an air gap of {gap_mm} mm to a {boundary} absorber, where gate P3-C tested pml_8 with a gap of λ/4 at f_lo ({quarter_mm} mm) or more. |
| 4 | `W_EMISSION_LIDS_LEFT_OUT` {ref, refs} | Shields {refs} get no lid: the emission model holds one lid, over {ref}, the shield over most of the board. |
| 6 | `I_EMISSION_RELATIVE` | Relative emission, not a compliance verdict: the field at 3 m per volt of the source's incident wave and per mA of its current, for comparing variants of one board under identical settings; it predicts no measured field. |
| 6 | `I_EMISSION_BAND` {count, f_lo_mhz, f_max_mhz, harmonics} | Far field at {count} frequencies from {f_lo_mhz} to {f_max_mhz} MHz; the carrier's harmonics among them: {harmonics}. |
| 6 | `I_EMISSION_HARMONIC` {n, f_mhz, e_v_db, e_ma_db, theta_deg, phi_deg, rad_pct, basis, eps, closure} | Harmonic {n} at {f_mhz} MHz: {e_v_db} dB re 1 (V/m)/V and {e_ma_db} dB re 1 (V/m)/mA at 3 m, the sphere's largest at θ {theta_deg}°, φ {phi_deg}°; P_rad is {rad_pct} % of the incident power ({basis}); energy closure ε {eps}: {closure}. |
| 6 | `I_EMISSION_CLOSURE` {judged, total, eps, f_mhz, limit} | Energy closure is judged at {judged} of {total} frequencies; the largest \|ε\| among them is {eps}, at {f_mhz} MHz, against {limit}. |
| 6 | `I_EMISSION_NOT_JUDGED` {total} | Energy closure is judged at none of the {total} frequencies: each is truncated by a ring, takes in under 1e-3 of the incident power, or meets a resistor in the grid. |
| 6 | `W_EMISSION_CLOSURE` {eps, f_mhz, limit} | Energy closure misses at {f_mhz} MHz: \|ε\| {eps} is over {limit}, so the power bookkeeping there is not to be trusted; a stricter preset or a wider air gap is the usual fix. |
| 6 | `W_EMISSION_RING` {f_mhz, t_ns, q, factor, width_mhz} | A resonance at {f_mhz} MHz still rings when the job ends at {t_ns} ns: fitted Q {q}, truncation factor {factor}. Frequencies within {width_mhz} MHz of it are reported as truncated and are not closure-judged. |
| 6 | `W_EMISSION_RING_HELD` {f_mhz, t_ns} | A resonance at {f_mhz} MHz does not decay by the job's end at {t_ns} ns, so no Q fits it and every frequency is reported as truncated. |
| 6 | `I_LIMIT_EMISSION` | Limits of the emission results: the board alone in free space, with no ground reflection, cables, enclosure or part bodies; copper a perfect conductor and the dielectric lossless, so a cavity's Q reads 5 to 40 times a real FR-4 board's; one lid, drawn walls only; the largest over a 5° sphere, not a turntable; peak phasors, which a per-V or per-mA ratio cancels; truncation as reported; the results compare variants under identical settings and predict no measured field. |
| 6 | `T_CLOSURE_JUDGED`, `T_CLOSURE_TRUNCATED`, `T_CLOSURE_P_ACC_LOW`, `T_CLOSURE_RESISTIVE`, `T_CLOSURE_BACKED`, `T_NF2FF_ONLY` | judged · not judged, a ring truncates it · not judged, under 1e-3 of the incident power is taken in · not judged, a resistor in the grid takes power no probe measures · closure-backed · from NF2FF only |
| 8 | `E_EMISSION_ONE_RUN` {path, command} | {path} is an emission project: its run puts every part in the grid at its value, so `{command}` does not apply. Change a value in project.json and run it again. |
| 8 | `I_EMISSION_NO_FAR_FIELD` | No far field is recorded for this run, so it has no emission levels; run it again. |
| 8 | `E_EMISSION_PART` {ref, value} | The emission run puts every chain part in the grid at its value, but {ref} ("{value}") is not a C, L or R whose value reads (a C above 0), or it is turned off a multiple of 90°. Set {ref}'s "value" in project.json, or rotate it in KiCad, and run again. |
| 9 | `W_EMISSION_LONG_RUN` {time} | The driven job may take {time} to T_max, over two hours: a lower --f-max, or a carrier's band instead of --band, cuts it. |
| 10 | `W_OVERRIDE_REFUSED` {from, x_mm, y_mm, reason} | An added via of finding {from} at ({x_mm}, {y_mm}) mm is left out: {reason}. |
| 10 | `T_OVERRIDE_COPPER`, `T_OVERRIDE_EDGE` | it would come within the 0.2 mm clearance of another net's track, pad, copper graphic or via · it would come within the 0.2 mm clearance of the board edge |
| 11 | `I_OVERRIDES` {fills, vias, finding} | The variant holds {fills} filled voids and {vias} added vias from finding {finding}; they are geometry in project.json, not in the board: draw them in KiCad to keep them. |
| 11 | `E_OVERRIDE_REVIEW` {path, finding, reason} | Cannot make a variant from finding {finding} of the review {path}: {reason}. |
| 11 | `E_OVERRIDE_NONE` {finding, reason} | Finding {finding} gives no variant: {reason}. |
| 11 | `T_REVIEW_SCHEMA`, `T_REVIEW_OTHER_BOARD`, `T_REVIEW_NO_FINDING` | it is not a review.json of schema 1 · it reviewed another board, or this one before its last save; review it again · it holds no finding of that id |
| 11 | `T_OVERRIDE_NOT_A_VOID`, `T_OVERRIDE_NO_PAIR`, `T_OVERRIDE_PITCH`, `T_OVERRIDE_NO_ROOM` | its run crosses no hole of its reference plane on that layer: a split between two nets, or the plane's edge, cannot be filled without a short; draw the fix in KiCad · its fence has fewer than two vias to space new ones between · the pitch is not under the gap, so no via fits in it · no added via clears the other nets' copper, the board edge and its plane |
| 12 | `T_OVERRIDE_TWO_NETS`, `T_OVERRIDE_OFF_PLANE` | its reference changes between two nets, which only a capacitor would join, and a capacitor variant is deferred; draw the fix in KiCad · its plane's net does not cover it on the reference layer |
| 18 (no-go only) | `W_EMISSION_UNVALIDATED` {record} | The emission kind failed its validation ({record}): its results are unvalidated, relative ones included. |

In all, 47 codes, and 48 on a no-go.

---

## File structure

```
tools/golden_s5.py, tests/fixtures/golden_s5.json; tests/test_golden_{v1,antenna,si}.py, tests/test_repo.py      # T1
core/model/csx.py (EMISSION_NF2FF_MAX), core/project.py, core/review/__init__.py, gui/control.py (open_project);
  tests/test_project.py, test_review.py, test_gui_control.py, test_sexpr.py                                     # T2
cli.py (new_emission, _HIDDEN, main, _new), core/model/spec.py (emission_pulse, emission_t_max);
  tests/test_cli_emission.py                                                                                     # T3
core/geometry/region.py, core/geometry/__init__.py, core/model/spec.py, core/model/csx.py, pipeline.py
  (build_model); tests/test_emission_model.py                                                                    # T4
stoprule.py (the branch, tail_fit, truncated); tests/test_stoprule_emission.py                                   # T5
core/post/farfield.py (port_dft, snapped), core/post/antenna.py, core/post/emission.py;
  tests/test_post_emission.py                                                                                    # T6
pipeline.py (fingerprint), core/post/emission.py (null_floor, floor_db); tests/test_post_emission.py,
  tests/test_emission_run.py                                                                                     # T7
pipeline.py (prepare, simulate, run_ports, far_field, _run, emission_parts, emission_of, emission_outputs,
  write_outputs, retune, verify); tests/test_emission_run.py                                                     # T8
pipeline.py (cost_seconds, cost_notes, cost); tests/test_emission_run.py                                         # T9
core/geometry/overrides.py (apply_overrides), pipeline.py (load); tests/test_overrides.py                        # T10
core/geometry/overrides.py (read_review, via_size, make_overrides: R1, R4), cli.py; tests/test_overrides.py,
  tests/test_cli_emission.py                                                                                     # T11
core/geometry/overrides.py (return_via; R2, R3); tests/test_overrides.py                                         # T12
tools/ea.py, tools/p3a.py (dipole's keywords), tools/p0.py (tools_id), tests/fixtures/ea/criteria.json;
  tests/test_ea.py                                                                                               # T13
docs/validation/<date>-e-a.md and .json                                                                          # T14 (run)
tools/make_fixtures.py (emc_probe), tests/fixtures/emc_probe*.kicad_pcb and .pads.json; tests/test_fixtures.py,
  tests/test_pads.py, tests/test_probe.py                                                                        # T15
tools/probe.py, tests/fixtures/probe/criteria.json; tests/test_probe.py                                          # T16
docs/validation/<date>-probe-freeze.json, <date>-probe.md and .json                                              # T17 (run)
core/project.py, cli.py, pipeline.py (W_EMISSION_UNVALIDATED), on a no-go only                                   # T18
the Stage 1 spec (A-78 to A-83)                                                                                  # T19 (doc)
```

Every task that adds codes also edits `core/messages.py`, `po/pt_BR.po`, `po/kicad_rf_studio.pot` and `src/kicad_rf_studio/locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo`.

---

### Task 1 [code]: The pins first

**The shared outputs this plan's edits reach,** at `a87bcc1`:

| Output | Edited by (task) | Hashed at `a87bcc1` | Task 1 adds |
| --- | --- | --- | --- |
| v1's, the antenna's and SI's model specs, spec hashes and model.json; lpf915's and ifa2g4_pi's verify specs; project.json as `new` writes it, `new`'s lines | `excitation`, `model_spec`, region, `build_geometry`, `build_model` (4); `core/project.py`, `cli` (2, 3) | yes: `models` | – |
| v1's and the antenna's results/ files and result lines from committed waves; the 2D readouts | `write_outputs`' dispatch, `farfield.py` (6, 8) | yes: `outputs` (env-gated) | – |
| `load()`'s notes | `pipeline.load` (10, 18) | no | `load` |
| the cost lines, at pool 1, and at pool 4 with a kept run (I_COST_PREDICTED, `small_speed(4)`, W_SI_LONG_RUN) | `cost_notes`, `cost_seconds` (9) | no | `cost` |
| every call `build_csx` makes | `csx.py` (4) | no | `csx`, `csx_verify` |
| the antenna and SI fingerprints | `fingerprint` (7) | no | `fingerprint` |
| the stop rule's verdicts on the committed traces | `stop_rule` (5) | no | `stop` |
| P3-A's hand-written specs | `p3a.dipole` (13) | no | `p3a` |
| a whole `cost`, `run` and v1 `verify` through the fake worker: exit codes, project.json's results and verify blocks, every event line, every job.json (setup, jobs, transform), and the results/ files, SI's included | `prepare`, `simulate`, `run_ports`, `far_field`, `_run`, `cost`, `verify`, `retune` (8, 9) | no | `run` (env-gated, as `outputs`) |
| review.json, compare's lines | – (the rules and compare are not edited; `resolve_f_max` gains a schema-4 branch only) | review: yes (`test_golden_review.py`) | – |

**Files:**
- Create `tools/golden_s5.py`. It writes `tests/fixtures/golden_s5.json` once.
- Modify `tests/test_golden_v1.py`, `test_golden_antenna.py` and `test_golden_si.py`: one module fixture and one test each.
- Modify `tests/test_repo.py`: `test_every_golden_pin_names_a_clean_product_tree`'s list gains `"golden_s5.json"`.
- `tools/golden_v1.py`, `golden_antenna.py`, `golden_si.py` and their JSONs stay byte for byte as they are.

**Interfaces.** Produces, in `tools/golden_s5.py`, which imports `fake_cli.patches` and `test_model_csx.Rec` from `tests` through `sys.path`, as `golden_si` imports `test_cli_si`:
- `GOLDEN = p0.FIX / "golden_s5.json"`;
- `SETUP = {"dt": 1e-13, "node": [0, 1, 1, 1]}`;
- `VOLATILE = ("folder", "run_dir", "path", "log", "wall")`: event params that hold a path or a measured time;
- `csx_calls(spec) -> str`: the sha256 of `json.dumps(log, default=lambda o: type(o).__name__)`, where `log` is every call `build_csx(spec, 1, spec["excitation"]["t_max"])` makes with `sys.modules`' `CSXCAD`, `CSXCAD.CSProperties` and `openEMS` standing in as `Rec`s (`mock.patch.dict`);
- `case(pj) -> dict`, of a project built by `new`:
  - `"load"`: the sha256 of `json.dumps(pipeline.load(pj)[3], sort_keys=True, default=str)`;
  - `"cost"`: the sha256 of `[cost_notes(model, project, SETUP, 4, 1, 100.0), cost_notes(model, {**project, "results": {"model_hash": spec_hash(spec), "jobs": [{"verdict": "converged", "t_stop": 5e-9}]}}, SETUP, 2, 4, 3.0)]`;
  - `"csx"`: `csx_calls(spec)`;
  - for an antenna or SI project, `"fingerprint"`: the sha256 of `json.dumps(fingerprint less "app" and "openems", sort_keys=True)`, with `runs.openems_versions` patched to `("0.37.0", "0.7.0")`;
- `fake_run(pj, verify=False) -> dict`, under `mock.patch.multiple(runs, **fake_cli.patches(<working folder>/data-<project folder name>), free_ram_mb=lambda: 1e6, run_jobs=<the real runs.run_jobs called with watch None>)`, with `secrets.token_hex` patched to `lambda n: "0" * (2 * n)`, a calibration saved as `tests/conftest.py`'s `calibrated` saves it, and, with `verify`, `spec.c_box` patched to `2e-14` as golden_v1 patches it:
  - it runs `pipeline.cost(pj, <a folder made first>)`, then `pipeline.run(pj)`, then with `verify` `pipeline.verify(pj)`. Unwatched, each fake job writes its whole trace, so verdicts, t_stop and waves are the same on every call;
  - it returns `{"cost": step, "run": step, ("verify": step,) "files": {name: sha256 of each results/ file at the end}}`, each `step` being `{"exit", "record": the sha256 of project.json's results block (verify's for verify; None for cost) less run_dir and wall_s, "events": the sha256 of [[kind, job, code, params less VOLATILE] for each event of its run folder, in file order], "jobs": {job folder name: sha256 of its job.json}}`;
- `shared_v1()`, `shared_antenna()`, `shared_si()` -> dict, each building its golden tool's projects in the working folder exactly as that tool builds them (golden_v1.CASES with `new` at 915 MHz; golden_antenna.BANDS with `new_antenna` on `_board(name)`; golden_si.CASES with `new_si` and `si_args`), each returning `{"cases": {case: case(pj)}, "run": {name: fake_run(pj)}}`, where:
  - v1's run is lpf915's, with `verify`; the antenna's is ifa2g4's, whose transform's job.json joins its run's `"jobs"`; SI's is usb2_hs's;
  - lpf915's and ifa2g4_pi's case adds `"csx_verify"`: `csx_calls` of the verify spec as golden_v1 and golden_antenna build it;
  - v1 adds `"stop"`: `{trace name: {preset: [kind, t, round(residual_db, 2)] or None}}` of `stop_rule(rec, k, preset, exc)` for each `tests/fixtures/traces/*.npz` (`rec, k, exc, _ = p0.load_trace(path)`) and each preset of `stoprule.PRESETS`, and `"p3a"`: `{sid: spec_hash(s) for sid, s in p3a.specs().items()}`;
- `digests() -> dict`: `{"v1": shared_v1(), "antenna": shared_antenna(), "si": shared_si()}`, each run in its own new subfolder of the working folder, so the three tools' case folders never meet (golden_antenna writes golden_v1's case folders too);
- `main() -> int`: `golden_v1.record(GOLDEN, digests)`, which records in a fresh temporary folder with `code` and `env`.

- [ ] **Step 1: The failing tests.** In each of the three modules, read `SHARED = json.loads(golden_s5.GOLDEN.read_text(encoding="utf-8"))`, and add a module fixture that runs its own `shared_<kind>()` in a fresh folder:

```python
@pytest.fixture(scope="module")
def shared(tmp_path_factory):
    home = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("shared"))  # relative paths only, as `now`
    try:
        return golden_s5.shared_v1()  # shared_antenna(), shared_si() in the other two modules
    finally:
        os.chdir(home)
```

  In `tests/test_golden_v1.py` (which also imports `p3a`):

```python
def test_v1s_shared_outputs_stand_as_they_were_at_a87bcc1(shared):  # Stage 5 design 8 risk 11; plan 3 ruling 2
    pins = SHARED["v1"]
    assert set(shared["cases"]) == set(golden_v1.CASES) and set(shared["run"]) == {"lpf915"}
    assert {"load", "cost", "csx", "csx_verify"} <= set(shared["cases"]["lpf915"])
    assert set(shared["run"]["lpf915"]) == {"cost", "run", "verify", "files"} and set(shared["p3a"]) == set(p3a.STEPS)
    assert len(shared["stop"]) == 8 and all(len(v) == 3 for v in shared["stop"].values())
    # a load note, a cost line, a CSX call, a stop verdict or a P3-A spec moved
    assert {k: v for k, v in shared.items() if k != "run"} == {k: v for k, v in pins.items() if k != "run"}
    if golden_v1.env() != SHARED["env"]:
        pytest.skip("the run pins compare only on the env that recorded them (golden_v1.env())")
    assert shared["run"] == pins["run"]  # an exit, a record, an event line, a job file or a results/ file moved
```

  In `tests/test_golden_antenna.py`:

```python
def test_the_antennas_shared_outputs_stand_as_they_were_at_a87bcc1(shared):  # plan 3 ruling 2
    pins = SHARED["antenna"]
    assert set(shared["cases"]) == set(golden_antenna.BANDS) and set(shared["run"]) == {"ifa2g4"}
    assert all({"load", "cost", "csx", "fingerprint"} <= set(c) for c in shared["cases"].values())
    assert "csx_verify" in shared["cases"]["ifa2g4_pi"]
    assert sum(name.startswith("job-0-nf2ff") for name in shared["run"]["ifa2g4"]["run"]["jobs"]) == 1  # the transform
    assert shared["cases"] == pins["cases"]
    if golden_v1.env() != SHARED["env"]:
        pytest.skip("the run pins compare only on the env that recorded them (golden_v1.env())")
    assert shared["run"] == pins["run"]
```

  In `tests/test_golden_si.py`:

```python
def test_the_si_fixtures_shared_outputs_stand_as_they_were_at_a87bcc1(shared):  # plan 3 ruling 2
    pins = SHARED["si"]
    assert set(shared["cases"]) == set(golden_si.CASES) and set(shared["run"]) == {"usb2_hs"}
    assert all({"load", "cost", "csx", "fingerprint"} <= set(c) for c in shared["cases"].values())
    assert shared["cases"] == pins["cases"]
    if golden_v1.env() != SHARED["env"]:
        pytest.skip("the run pins compare only on the env that recorded them (golden_v1.env())")
    assert shared["run"] == pins["run"]  # SI's results/ files and lines included
```

  In `tests/test_repo.py`, the expected list becomes `["golden_antenna.json", "golden_s5.json", "golden_si.json", "golden_v1.json"]`.
- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_repo.py -q -rs`. Expected: FAIL, with `ModuleNotFoundError: No module named 'golden_s5'`.
- [ ] **Step 3: `tools/golden_s5.py`,** as Interfaces gives it. Its docstring says what it pins, that it was recorded once at `a87bcc1` before plan 3's first shared edit, and that a new recording is a controller ruling, which deletes the file first.
- [ ] **Step 4: Record once.** Run `.venv/Scripts/python tools/golden_s5.py` (it records in English). Then run `git status --short tests/fixtures`. Expected: exactly `?? tests/fixtures/golden_s5.json`.
- [ ] **Step 5: Run them.** Use Step 2's command. Expected: PASS with nothing skipped, the existing models and outputs tests unchanged.
- [ ] **Step 6: Both suites, commit, graph.**

```bash
git add tools/golden_s5.py tests/fixtures/golden_s5.json tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_repo.py
git commit -m "test(golden): pin what plan 3's shared edits reach before any of them: load notes, cost lines at two pools, every CSX call, the antenna and SI fingerprints, the stop verdicts on the traces, P3-A's specs, and a whole fake cost, run and verify with their records, lines, job files and results, recorded at a87bcc1 (Stage 5 design 8 risk 11)"
graphify update .
```

---

### Task 2 [code]: Schema 4, the review's f_max order and the window's refusal

**The `antenna(` calls at `a87bcc1`, and their sides** (§5.6):

| Where | Side | Task |
| --- | --- | --- |
| region.py `f_max`, `band` (2) | an `emission()` branch first: the band's f_max; `emission_band` | 4 |
| geometry/__init__.py `build_geometry` (1) | `whole = ant or emission(project)` picks board_region, the lid's crop, `Geometry(..., antenna=whole)` (the mesh's pair exemption) and the air-gap and lids-left-out gates, the last two as W_EMISSION_ twins; sheet copper, join and W_STAIRCASED stay antenna-only | 4 |
| spec.py `excitation` (1) | emission tested before antenna (after SI) | 4 |
| spec.py `model_spec` sheet (1) | antenna-only | – |
| spec.py `model_spec` block (1) | "boundary": antenna or emission; sheet, nf2ff and join antenna-only | 4 |
| project.py `check_project` (2) | `emission()` first; the antenna's band and far-field checks stay antenna-only | 2 |
| review `resolve_f_max` (1) | an emission branch at step 3 | 2 |
| pipeline `load` (1) | check_antenna and adopt antenna-only; the overrides behind `emission()` | 10 |
| pipeline `build_model` (1) | air box: antenna or emission | 4 |
| pipeline `cost_notes` (1), `cost`'s prepare (1) | antenna or emission | 9 |
| pipeline `simulate`'s prepare (1), speed refresh (1), `_run` fp (1), `_run` results (1), `write_outputs` (1) | antenna or emission; emission dispatched first in write_outputs | 8 |
| pipeline `chain_results` (1), `assign` (1), `antenna_result` (1), `compare_projects` (1), `verify` (1), `_verify` (1) | antenna-only, not reached: retune and verify refuse the kind first (Task 8), compare's kind check refuses it (its third kind is plan 4's), and the window refuses it before `pipeline.load` (this task) | – |
| post/chain.py (1), post/waves.py `layout` (1) | antenna-only, not reached for the same reasons; an emission run reads no layout (AR-3) | – |
| gui/control.py (4), gui/window.py (2) | antenna-only, not reached: `open_project` refuses a schema-4 file first (G_KIND_LATER, this task); the GUI's emission kind is plan 5's | – |

That makes 32 calls.

**Files:**
- Modify `core/model/csx.py` (the constant only), `core/project.py`, `core/review/__init__.py`, `gui/control.py` (`open_project`), and the messages.
- Tests: `tests/test_project.py`, `tests/test_review.py`, `tests/test_gui_control.py`, `tests/test_sexpr.py`.

**Interfaces.** Produces:
- in `csx.py`: `EMISSION_NF2FF_MAX = 64`;
- in `core/project.py`:
  - `SCHEMA_EMISSION = 4` and `emission(data) -> bool`: `data.get("schema") == SCHEMA_EMISSION`;
  - `NEAR_FIELD_MAX = 11`;
  - `emission_band(data) -> tuple[float, float]`: `(pulse_band(f_lo, f_max)[0], f_max)` of `data["band"]`;
  - `harmonics_hz(f0, f_max) -> list[float]`: n·f0 for n = 2, 3, … while n·f0 ≤ f_max;
  - `emission_far_field_hz(f0: float | None, f_lo, f_max) -> list[float]`, ascending: the harmonics (none without f0), then the grid `1e9 + 1e8·k` (k 0..50) inside [f_lo, f_max], leaving out a point within 1 MHz of a harmonic; at most EMISSION_NF2FF_MAX, the lowest harmonics kept first, then the lowest grid points;
  - `make_emission_project(board_path, board_sha256, f0_hz, f_lo_hz, f_max_hz, stackup, classes, chain, others, ports, *, t_max_s, air_gap_mm, preset=DEFAULT_PRESET, lid_height_mm=None) -> dict`:
    - `make_project`'s dict less `harmonics` and `band_factor`;
    - schema SCHEMA_EMISSION, f0_hz (None without a carrier), t_max_s, region `{"expand_h": REACH_H}` and lid true, in their places;
    - then appended: `kind "emission"`, `band {"f_lo_hz", "f_max_hz"}`, `air_gap_mm`, boundary ANTENNA_BOUNDARY, `far_field {"f_hz": emission_far_field_hz(...), "step_deg": FAR_FIELD_STEP}` and `near_field false`;
    - no `overrides`;
  - `_override(entry) -> bool`: a dict with `"kind"` "fill" or "via", `"from"` and `"net"` text; a fill has `"layer"` text and `"polygon_mm"` {"exterior": ≥ 3 [x, y] number pairs, "holes": a list of such rings}; a via has `"at_mm"` [x, y], `"diameter_mm"` > 0, `"drill_mm"` > 0, `"layers"` two names and an optional `"pitch_mm"` > 0;
  - `_FIELDS_EMISSION`: `_FIELDS` less harmonics and band_factor, with:
    - `f0_hz` `_ABOVE_0_OR_NULL` and `lid` `_FLAG`;
    - ports with an optional `"R"` (`_OPTIONAL_ABOVE_0`);
    - kind, band (`f_lo_hz`, `f_max_hz` above 0), `air_gap_mm`, boundary (pml_8 or mur, as the antenna's), far_field (1 to EMISSION_NF2FF_MAX numbers, T_EXPECT_EMISSION_FAR_FIELD_HZ; step as the antenna's), `near_field` (`_FLAG`);
    - `overrides`: `(lambda v: v is _MISSING or isinstance(v, list) and all(map(_override, v)), "T_EXPECT_OVERRIDES")`;
  - `load_project`: accepts SCHEMA_EMISSION; E_PROJECT_SCHEMA's `expected` is SCHEMA_EMISSION;
  - `check_project`:
    - `_FIELDS_EMISSION` when `emission(data)`, tested first;
    - then, in order, `band.f_max_hz` (f_lo < f_max, T_EXPECT_EMISSION_BAND), `far_field.f_hz` (each in [f_lo, f_max]), `near_field` (true needs f0_hz, T_EXPECT_NEAR_FIELD) and `ports[0].R` (absent, T_EXPECT_DRIVEN_R);
    - outside schema 4, an `overrides` key is E_PROJECT_FIELD on `overrides`, T_EXPECT_NO_OVERRIDES;
- in `core/review/__init__.py`, `resolve_f_max`: an emission project's carrier is its `f0_hz` at step 2, as today; without one, `min(band.f_max_hz, F_MAX_CAP)`, source `"emission"`, at step 3. I_REVIEW_BASIS's source is then `T_FMAX_EMISSION`;
- in `gui/control.py`, `open_project`: before `pipeline.load`, `if emission(load_project(path)): raise KrsError("G_KIND_LATER", path=str(path))`, with `# ponytail: plan 5 opens the emission kind; until then the window's project line reads f0 and harmonics`, as Stage 4's G_SI_LATER did (7140e6f).

- [ ] **Step 1: The head check.** Run `git grep -n "antenna(" -- src | grep -v "def antenna(\|check_antenna(\|new_antenna(\|make_antenna_project(\|_verify_antenna(\|draw_antenna(\|retrace_antenna("`. Expected: the 32 lines of the table. A different list stops the task for a ruling.
- [ ] **Step 2: The failing tests.** In `tests/test_project.py`:
  - add `SCHEMA_EMISSION, emission, emission_band, emission_far_field_hz, harmonics_hz, make_emission_project` to the project import;
  - in `test_schema_mismatch_names_the_file_and_both_versions`, the expected schema becomes `SCHEMA_EMISSION` and `"schema 3"` becomes `"schema 4"`;
  - add:

```python
from kicad_rf_studio.core.model.csx import EMISSION_NF2FF_MAX

FILL = {"kind": "fill", "layer": "In1.Cu", "net": "GND", "from": "R1-0123abcd",
        "polygon_mm": {"exterior": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]], "holes": []}}
VIA = {"kind": "via", "at_mm": [1.0, 2.0], "diameter_mm": 0.6, "drill_mm": 0.3, "layers": ["F.Cu", "B.Cu"],
       "net": "GND", "from": "R4-0123abcd", "pitch_mm": 1.0}


def emission_dict(f0=915e6, f_lo=1.83e9, f_max=3e9):
    b, a = load_board(FIX / "ifa2g4.kicad_pcb"), antenna_dict()
    ports = [*a["ports"], {**a["ports"][0], "name": "P2", "signal": "AE1.1"}]
    return make_emission_project("ifa2g4.kicad_pcb", "0" * 64, f0, f_lo, f_max, b.stackup, classify(b), a["chain"],
                                 [], ports, t_max_s=31e-9, air_gap_mm=air_gap(f_lo))


def test_an_emission_project_is_schema_4_with_its_band_and_far_field():  # design 5.6, 5.8
    d = emission_dict()
    assert (d["schema"], d["kind"], d["f0_hz"], d["band"], d["t_max_s"]) == (
        4, "emission", 915e6, {"f_lo_hz": 1.83e9, "f_max_hz": 3e9}, 31e-9)
    assert "harmonics" not in d and "band_factor" not in d and "overrides" not in d
    assert (d["lid"], d["region"], d["boundary"], d["near_field"]) == (True, {"expand_h": 6.0}, "pml_8", False)
    assert d["far_field"] == {"f_hz": emission_far_field_hz(915e6, 1.83e9, 3e9), "step_deg": 5}
    assert emission(d) and not emission({**d, "schema": 2}) and check_project(d, Path("p.json")) is d
    assert emission_band(d) == (1.40e9, 3e9) and SCHEMA_EMISSION == 4


def test_the_far_field_list_is_the_harmonics_and_the_100_mhz_grid_in_the_band():  # design 5.8; BC3
    assert emission_far_field_hz(915e6, 1.83e9, 3e9) == [1.83e9, 1.9e9, 2.0e9, 2.1e9, 2.2e9, 2.3e9, 2.4e9, 2.5e9,
                                                        2.6e9, 2.7e9, 2.745e9, 2.8e9, 2.9e9, 3.0e9]  # the probe's 14
    assert emission_far_field_hz(None, 1e9, 6e9) == [1e9 + 1e8 * k for k in range(51)]  # no carrier: the grid
    assert emission_far_field_hz(1e9, 2e9, 3e9) == [2e9 + 1e8 * k for k in range(11)]  # 2·f0 on the grid, once
    assert emission_far_field_hz(50e6, 1e8, 6e9) == [n * 50e6 for n in range(2, 66)]  # capped: harmonics first
    assert len(emission_far_field_hz(50e6, 1e8, 6e9)) == EMISSION_NF2FF_MAX
    assert emission_far_field_hz(None, 3e8, 9e8) == []  # new refuses it (Review Focus 1)
    assert harmonics_hz(915e6, 4.575e9) == [1.83e9, 2.745e9, 3.66e9, 4.575e9]


@pytest.mark.parametrize(("change", "field", "expected"), [
    ({"kind": "antenna"}, "kind", "T_EXPECT_EMISSION"),
    ({"f0_hz": 0}, "f0_hz", "T_EXPECT_ABOVE_0_OR_NULL"),
    ({"band": {"f_lo_hz": 3e9, "f_max_hz": 3e9}}, "band.f_max_hz", "T_EXPECT_EMISSION_BAND"),
    ({"far_field": {"f_hz": [1.8e9], "step_deg": 5}}, "far_field.f_hz", "T_EXPECT_EMISSION_FAR_FIELD_HZ"),
    ({"far_field": {"f_hz": [2e9] * 65, "step_deg": 5}}, "far_field.f_hz", "T_EXPECT_EMISSION_FAR_FIELD_HZ"),
    ({"near_field": None}, "near_field", "T_EXPECT_FLAG"),
    ({"f0_hz": None, "near_field": True}, "near_field", "T_EXPECT_NEAR_FIELD"),
    ({"lid": None}, "lid", "T_EXPECT_FLAG"),
    ({"boundary": "MUR"}, "boundary", "T_EXPECT_BOUNDARY"),
    ({"overrides": [{"kind": "via", "at_mm": [1.0, 2.0]}]}, "overrides", "T_EXPECT_OVERRIDES")])
def test_a_schema_4_field_out_of_its_range_is_named(change, field, expected):  # design 5.6
    with pytest.raises(KrsError) as e:
        check_project({**emission_dict(), **change}, Path("p.json"))
    assert (e.value.code, e.value.params["field"], e.value.params["expected"]) == ("E_PROJECT_FIELD", field, expected)


def test_a_terminations_r_is_read_and_the_driven_ports_is_refused():  # design 5.6: the termination's R
    d = emission_dict()
    ok = {**d, "ports": [d["ports"][0], {**d["ports"][1], "R": 75.0}]}
    assert check_project(ok, Path("p.json")) is ok
    for ports, field, expected in (([d["ports"][0], {**d["ports"][1], "R": 0}], "ports[1].R", "T_EXPECT_ABOVE_0"),
                                   ([{**d["ports"][0], "R": 75.0}, d["ports"][1]], "ports[0].R", "T_EXPECT_DRIVEN_R")):
        with pytest.raises(KrsError) as e:
            check_project({**d, "ports": ports}, Path("p.json"))
        assert (e.value.params["field"], e.value.params["expected"]) == (field, expected)


def test_overrides_belong_to_schema_4_alone(tmp_path):  # design 5.6, 5.9; Review Focus 5
    d = {**emission_dict(), "overrides": [FILL, VIA]}
    assert check_project(d, Path("p.json")) is d
    _, v1 = run_new(tmp_path)
    for other in (load_project(v1), antenna_dict(), si_dict()):
        with pytest.raises(KrsError) as e:
            check_project({**other, "overrides": [FILL]}, Path("p.json"))
        assert (e.value.params["field"], e.value.params["expected"]) == ("overrides", "T_EXPECT_NO_OVERRIDES")
```

  In `tests/test_review.py` (importing `cli`, `render` and `FIX` as the module needs them):

```python
def test_an_emission_project_joins_the_review_f_max_order_with_its_own_source():  # design 5.1; AR-10
    from test_project import emission_dict
    assert resolve_f_max(None, None, emission_dict()) == (4.575e9, "carrier", 915e6)
    assert resolve_f_max(None, None, emission_dict(None, 1e9, 3e9)) == (3e9, "emission", None)
    assert resolve_f_max(None, None, emission_dict(None, 1e9, 8e9)) == (6e9, "emission", None)
    assert resolve_f_max(4e9, None, emission_dict()) == (4e9, "cli", 915e6)
    board, stack, zs, classes = cli._load(FIX / "ifa2g4.kicad_pcb", None)
    notes = dict(review_board(board, stack, zs, classes, project=emission_dict(None, 1e9, 3e9)).notes)
    assert notes["I_REVIEW_BASIS"]["source"] == "T_FMAX_EMISSION"
    assert "T_FMAX" not in render("I_REVIEW_BASIS", **notes["I_REVIEW_BASIS"])  # a catalog term, never a raw code
```

  In `tests/test_gui_control.py` (importing `gettext`, `messages` and `CATALOG` as needed):

```python
def test_an_emission_project_is_refused_by_the_window_and_named_by_no_kind(tmp_path, fake):  # Review Focus 2; AR-17
    from test_project import emission_dict
    p = tmp_path / "project.json"
    save_project(p, emission_dict())
    opened = control.open_project(p)
    assert opened.project is None and opened.problem == ("G_KIND_LATER", {"path": str(p)})
    assert opened.stored["schema"] == 4 and control.fields(opened.stored)  # Advanced still opens the file
    pt = gettext.translation("kicad_rf_studio", messages.LOCALE, ["pt_BR"]).gettext(CATALOG["G_KIND_LATER"])
    assert "emiss" not in CATALOG["G_KIND_LATER"].lower() and "emiss" not in pt.lower()
```

  In `tests/test_sexpr.py`, a module-level `PLANS_1_2`: the 56 codes `git diff d3b036f a87bcc1 -- src/kicad_rf_studio/core/messages.py` adds, as a sorted tuple; then:

```python
def test_no_stage5_line_names_a_limit_a_standard_or_a_verdict():  # design 5.8; ruling 5 as AR-1 applies it
    words = re.compile(r"\b(?:dBµV|dBuV|FCC|CISPR|margins?|pass(?:es|ed)?)\b", re.IGNORECASE)
    allowed = {"I_REVIEW_RELATIVE": "predicts a pass or a fail", "T_FMAX_DEFAULT": "FCC 15.33(b)(1)"}  # released
    ours = re.compile(r"EMISSION|OVERRIDE|CLOSURE|NF2FF|NEAR_FIELD|DRIVEN_R|T_REVIEW_|T_FMAX_|KIND_LATER")
    codes = {*PLANS_1_2, *(c for c in CATALOG if ours.search(c))}
    assert set(PLANS_1_2) <= set(CATALOG) and "T_FMAX_EMISSION" in codes
    found = []
    for code in sorted(codes):
        text = CATALOG[code]
        if code in allowed:
            assert allowed[code] in text
            text = text.replace(allowed[code], "")
        found += [(code, w) for w in words.findall(text)]
    assert found == []
```

- [ ] **Step 3: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_project.py tests/test_review.py tests/test_gui_control.py tests/test_sexpr.py -q`. Expected: FAIL, with `ImportError` on `SCHEMA_EMISSION`.
- [ ] **Step 4: The code** of Interfaces. Then run `tools/catalog.py` for the nine codes of Task 2 and their pt-BR.
- [ ] **Step 5: Run them.** Run Step 3's command, then `tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_golden_review.py -q -rs`. Expected: PASS, nothing skipped. A scan match in a released plan 1–2 msgid other than the two allowed phrases stops the task for a ruling.
- [ ] **Step 6: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/model/csx.py src/kicad_rf_studio/core/project.py src/kicad_rf_studio/core/review/__init__.py src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_project.py tests/test_review.py tests/test_gui_control.py tests/test_sexpr.py
git commit -m "feat(project): schema 4, the emission project: its band, its far-field list of the harmonics and the 100 MHz grid capped at 64, a termination's R, the near-field flag, overrides refused outside it, its place in the review's f_max order, the window's refusal naming no kind, and a scan for limit and verdict words (Stage 5 design 5.1, 5.6, 5.8)"
graphify update .
```

---

### Task 3 [code]: `new --emission`

**Files:**
- Modify `cli.py`: `new_emission`, `_HIDDEN`, `main` and `_new`.
- Modify `core/model/spec.py`: two new functions only.
- Messages.
- Create `tests/test_cli_emission.py`.

**Interfaces.**
- **Consumes** Task 2's project functions, and `F_MAX_CAP` and `CARRIER_HARMONICS` from `core.review`.
- **Produces, in `spec.py`:**
  - `emission_t_max(f_lo, f_max) -> float`: 2·t0 + 60/f_c of the pulse (pulse_band's f1, f_max), f_c the pulse's centre, rounded up to a whole ns, as `antenna_t_max` rounds;
  - `emission_pulse(f_lo, f_max, t_max=None) -> dict`: `{**pulse(f1, f_max, t_max or emission_t_max(f_lo, f_max)), "emission": True}`. That key is the spec's one emission marker.
- **Produces, in `cli.py`:**
  - `new_emission(board, start, end, *, f0=None, f_max=None, band=None, review=None, finding=None, pitch=None, preset=DEFAULT_PRESET, stackup=None, lid_height=None, output=None) -> tuple[Path, list[tuple[str, dict]]]`. Task 11 wires `review`, `finding` and `pitch`, which are accepted here. It works as `new_antenna` does, every refusal before anything is written:
    1. **The band:** (f_lo, f_max) is `band`, or `(2·f0, f_max or min(F_MAX_CAP, CARRIER_HARMONICS·f0))`. E_EMISSION_BAND when f_max ≤ f_lo or `emission_far_field_hz(f0, f_lo, f_max)` is empty, before the board is read.
    2. **The model's inputs:** `_load`, then `trace_chain(board, start, end, classes)`; ports P1 (the start, driven) and P2 (the end), by `_port`; `exc = emission_pulse(f_lo, f_max)`; `board_region(board, chain, ports, zs, f_max)`; `project_parts(..., exc["f1"], exc["f2"], antenna=True)`; `find_lid` over the crop with `{"lid": True, "lid_height_mm": lid_height}`.
    3. **The project:** `make_emission_project(..., t_max_s=exc["t_max"], air_gap_mm=air_gap(f_lo))`, written by `_write`.
    4. **The notes:** `_head_notes`, I_CHAIN, the part notes and the port notes; I_EMISSION_DEFAULTS, carrier `f"{f0 / 1e6:g} MHz"` or `"T_NONE"`; W_COPPER_WEIGHT, W_LID_HEIGHT_MISSING, the part notes, W_NO_REFERENCE; W_F0_RANGE for an f0 outside 1e6–1e11; W_ABSOLUTE_BOARD_PATH, then I_WROTE.
  - `_HIDDEN = argparse.ArgumentParser(add_help=False, allow_abbrev=False)` with `--emission` (store_true), `--review PATH`, `--finding ID` and `--pitch MM` (`_positive(float)`). These four are never added to `_parser()`, so they are off the usage line, and `--e` still reads as `--end` alone (AR-16).
  - `main(argv)`: `argv = sys.argv[1:] if argv is None else list(argv)`; when `argv[:1] == ["new"]`, `hidden, rest = _HIDDEN.parse_known_args(argv[1:])`, the main parser reads `["new", *rest]`, and `vars(args).update(vars(hidden))`. Every other command parses as today.
  - `_new`:
    - With `--emission`: refused, E_NEW_KIND, when `--antenna`, `--interface` or `--harmonics` is given, or any SI option but `--f-max`, or `--f-max` without `--f0`, or `--review` and `--finding` given apart, or `--pitch` without `--finding`.
    - Without `--emission`: the existing rules, plus a refusal of `--review`, `--finding` and `--pitch`.

- [ ] **Step 1: The failing tests,** in `tests/test_cli_emission.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import gettext

import pytest

from kicad_rf_studio import cli
from kicad_rf_studio.cli import main
from kicad_rf_studio.core import messages
from kicad_rf_studio.core.geometry.region import air_gap
from kicad_rf_studio.core.messages import CATALOG, KrsError, render
from kicad_rf_studio.core.model.spec import emission_pulse, emission_t_max
from kicad_rf_studio.core.project import emission_far_field_hz, read_project
from test_cli_new import FIX

LPF, COUPON = FIX / "lpf915.kicad_pcb", FIX / "coupon_gcpw_pads.kicad_pcb"
NEW = ["new", str(COUPON), "--start", "TP1.1", "--end", "TP2.1"]


def emission_project(folder, board=COUPON, start="TP1.1", end="TP2.1", **kw):
    """project.json of an emission project as new_emission writes it into `folder`, f0 915 MHz unless told."""
    return cli.new_emission(board, start, end, **({"f0": 915e6} | kw), output=folder)[0]


def test_the_emission_pulse_and_its_t_max():  # design 5.7
    exc = emission_pulse(1.83e9, 3e9)
    assert (exc["f1"], exc["f2"], exc["t_max"], exc["emission"]) == (1.40e9, 3e9, 31e-9, True)  # the probe's
    assert exc["t0"] == pytest.approx(1.7905e-9, rel=1e-4)
    assert [emission_t_max(*b) for b in ((1e9, 6e9), (1.83e9, 4.575e9), (1e9, 2.5e9), (5e8, 1.5e9))] == [
        19e-9, 22e-9, 41e-9, 69e-9]


def test_new_emission_writes_schema_4_on_the_whole_board(tmp_path):  # design 5.6, 5.7, 5.8
    d = read_project(emission_project(tmp_path / "e", LPF, "U1.1", "J1.1", lid_height=2.5))
    assert (d["schema"], d["kind"], d["f0_hz"], d["band"]) == (4, "emission", 915e6,
                                                                {"f_lo_hz": 1.83e9, "f_max_hz": 4.575e9})
    assert (d["t_max_s"], d["air_gap_mm"], d["lid"], d["near_field"]) == (22e-9, air_gap(1.83e9), True, False)
    assert d["far_field"]["f_hz"] == emission_far_field_hz(915e6, 1.83e9, 4.575e9) and "overrides" not in d
    assert [p["signal"] for p in d["ports"]] == ["U1.1", "J1.1"] and not any("R" in p for p in d["ports"])
    roles = {q["ref"]: q["role"] for q in (*d["chain"]["series"], *d["chain"]["shunt"], *d["others"])}
    assert {roles[r] for r in ("C2", "L1", "C3")} == {"port"} and roles["C4"] == "copper"  # A-27's bypass


def test_new_emission_with_a_band_has_no_carrier(tmp_path):  # design 5.6: --band F_LO:F_HI
    d = read_project(emission_project(tmp_path / "b", f0=None, band=(1e9, 6e9)))
    assert (d["f0_hz"], d["band"], d["t_max_s"]) == (None, {"f_lo_hz": 1e9, "f_max_hz": 6e9}, 19e-9)
    assert d["far_field"]["f_hz"] == [1e9 + 1e8 * k for k in range(51)]


@pytest.mark.parametrize("kw", [{"f0": 2.4e9, "f_max": 4.8e9}, {"f0": 3e9}, {"f0": None, "band": (3e8, 9e8)}])
def test_an_empty_emission_band_is_refused_before_anything_is_written(tmp_path, kw):  # Review Focus 1
    with pytest.raises(KrsError) as e:
        cli.new_emission(COUPON, "TP1.1", "TP2.1", **kw, output=tmp_path / "x")
    assert e.value.code == "E_EMISSION_BAND" and not (tmp_path / "x").exists()


@pytest.mark.parametrize("args", [
    ["--emission", "--band", "1GHz:6GHz", "--f-max", "3GHz"], ["--emission", "--interface", "se50"],
    ["--emission", "--f0", "915MHz", "--harmonics", "3"], ["--emission", "--f0", "915MHz", "--pair"],
    ["--emission", "--f0", "915MHz", "--target", "50"], ["--f0", "915MHz", "--review", "r.json", "--finding", "R1-0"],
    ["--emission", "--f0", "915MHz", "--review", "r.json"], ["--emission", "--f0", "915MHz", "--pitch", "1"]])
def test_new_refuses_an_emission_mix(tmp_path, capsys, args):  # design 5.6
    assert main([*NEW, *args, "-o", str(tmp_path / "x")]) == 2
    assert render("E_NEW_KIND") in capsys.readouterr().err and not (tmp_path / "x").exists()


def test_emission_with_an_antenna_is_refused(tmp_path, capsys):  # design 5.6
    assert main(["new", str(COUPON), "--start", "TP1.1", "--antenna", "TP2", "--band", "1GHz:2GHz", "--emission"]) == 2
    assert render("E_NEW_KIND") in capsys.readouterr().err


def test_the_emission_options_stay_off_the_usage_and_every_abbreviation_reads_as_before(tmp_path, capsys):  # B10
    with pytest.raises(SystemExit):
        main(["new", "--help"])
    out = capsys.readouterr().out
    assert "--band" in out and not any(o in out for o in ("--emission", "--review", "--finding", "--pitch"))
    pt = gettext.translation("kicad_rf_studio", messages.LOCALE, ["pt_BR"]).gettext(CATALOG["E_NEW_KIND"])
    assert "emiss" not in CATALOG["E_NEW_KIND"].lower() and "emiss" not in pt.lower()
    assert main(["new", str(COUPON), "--start", "TP1.1", "--e", "TP2.1", "--f0", "915MHz",
                 "-o", str(tmp_path / "v")]) == 0  # AR-16: --e is still --end alone
    assert read_project(tmp_path / "v" / "project.json")["schema"] == 1


def test_new_emission_through_main(tmp_path, capsys):  # design 5.6: --f-max with --f0
    assert main([*NEW, "--emission", "--f0", "915MHz", "--f-max", "3GHz", "-o", str(tmp_path / "e")]) == 0
    d = read_project(tmp_path / "e" / "project.json")
    assert (d["band"], d["t_max_s"]) == ({"f_lo_hz": 1.83e9, "f_max_hz": 3e9}, 31e-9)
    assert "not a compliance verdict" in capsys.readouterr().out  # I_EMISSION_DEFAULTS
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_cli_emission.py -q`. Expected: FAIL, with `ImportError` on `emission_pulse`.
- [ ] **Step 3: The code** of Interfaces, with I_EMISSION_DEFAULTS and E_EMISSION_BAND and their pt-BR.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_cli_new.py tests/test_cli_antenna.py tests/test_cli_si.py tests/test_cli_review.py tests/test_sexpr.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py -q -rs`. Expected: PASS, nothing skipped.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/cli.py src/kicad_rf_studio/core/model/spec.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_cli_emission.py
git commit -m "feat(cli): new --emission, hidden until the probe's go and read by its own parser: a carrier's harmonics band or --band, the emission pulse and its T_max, the whole board's parts as an antenna's, every refusal before anything is written (Stage 5 design 5.6, 5.7)"
graphify update .
```

---

### Task 4 [code]: The model

**Files:**
- Modify `core/geometry/region.py`, `core/geometry/__init__.py`, `core/model/spec.py`, `core/model/csx.py` and `pipeline.py` (`build_model`).
- Messages.
- Create `tests/test_emission_model.py`.

**Interfaces.** Each edit follows Task 2's table.
- **`region.f_max`** returns `band.f_max_hz` for an emission project. **`region.band`** returns `emission_band(project)`.
- **`build_geometry`:** `whole = ant or emission(project)` picks board_region, the lid's crop, `Geometry(..., antenna=whole)` and the two gates; an emission project's gates are W_EMISSION_AIR_BOX and W_EMISSION_LIDS_LEFT_OUT, with the antenna's params and tests.
- **`excitation`:** after SI, an emission project's is `emission_pulse(band f_lo, band f_max, project["t_max_s"])`.
- **`model_spec`:**
  - f0 is 0.0 for SI or emission, so every κ is 0;
  - `"boundary"` is written for antenna or emission when project.json's boundary is pml_8, before the antenna's sheet, nf2ff and join keys, so an antenna spec's key order is unchanged;
  - only `if emission(project) and project["near_field"]`: `spec["near_field"] = near_field_plane(project, board, geom, spec)`.
- **`near_field_plane(project, board, geom, spec) -> dict`**, in spec.py, with `NEAR_FIELD_MM = 1.5`:
  - `{"start": [x0, y0, z], "stop": [x1, y1, z], "f_hz": harmonics_hz(f0, f_max)[:NEAR_FIELD_MAX]}`;
  - x0 to y1 are the outline's bounds (else geom's crop's);
  - z is the highest z of spec's metal (copper solids, the lid's plate and walls, rods) + NEAR_FIELD_MM;
  - every coordinate to 1e-6 mm.
- **`build_model`:**
  - the air box applies to antenna or emission, with `air_cell(band(project)[1])`;
  - for an emission project only, a port whose project entry has `"R"` takes it as the placed entry's last key.
- **`build_csx`:**
  - `AddLumpedPort` and `AddCurvePort` take `port.get("R", 50)`;
  - the NF2FF check's cap is EMISSION_NF2FF_MAX when `pulse.get("emission")`, else NF2FF_MAX;
  - after the box, when the spec holds `"near_field"`: `dump = csx.AddDump("near_field", dump_type=11, file_type=1, frequency=nf["f_hz"], over_sampling=4); dump.AddBox(nf["start"], nf["stop"])`. Over-sampled 4 times as the NF2FF box is: at openEMS's default Nyquist rate a frequency aliases at 2·f2 − f, worst at f2, which the top harmonic often is.

- [ ] **Step 1: The failing tests,** in `tests/test_emission_model.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.geometry.region import air_gap
from kicad_rf_studio.core.model.csx import EMISSION_NF2FF_MAX, PML_CELLS, build_csx
from kicad_rf_studio.core.model.spec import emission_pulse, spec_hash
from kicad_rf_studio.core.project import harmonics_hz, load_project, save_project
from test_cli_antenna import antenna_project
from test_cli_emission import LPF, emission_project
from test_cli_new import run_new
from test_cli_si import si_project
from test_model_csx import TINY, fake_openems


def built(pj, **edits):
    if edits:
        save_project(pj, {**load_project(pj), **edits})
    project, board, geom, notes = pipeline.load(pj)
    return project, board, geom, notes, pipeline.build_model(project, board, geom)


def test_an_emission_model_is_the_whole_board_in_air_under_pml_lossless(tmp_path):  # design 5.6, 5.7; B3
    project, board, geom, notes, model = built(emission_project(tmp_path / "e"))
    s, gap = model.spec, project["air_gap_mm"]
    assert geom.antenna and not model.blocked and not [c for c, _ in notes if c.startswith("E_")]
    assert (s["boundary"], s["excitation"]) == ("pml_8", emission_pulse(1.83e9, 4.575e9, 22e-9))
    assert {"nf2ff", "copper", "join", "near_field"}.isdisjoint(s) and all(m["kappa"] == 0.0 for m in s["materials"])
    x0, _, x1, _ = board.outline.bounds
    assert s["mesh"]["x"][PML_CELLS] <= x0 - gap and s["mesh"]["x"][-1 - PML_CELLS] >= x1 + gap


def test_a_terminations_r_reaches_the_spec_and_the_csx(tmp_path, monkeypatch):  # design 5.6
    pj = emission_project(tmp_path / "e")
    base = built(pj)[4].spec
    d = load_project(pj)
    spec = built(pj, ports=[d["ports"][0], {**d["ports"][1], "R": 75.0}])[4].spec
    p1, p2 = spec["ports"]
    assert "R" not in p1 and p2["R"] == 75.0 and spec_hash(spec) != spec_hash(base)
    log = fake_openems(monkeypatch)
    build_csx(spec, 1, 1e-9)
    assert [a[:2] for n, a, _ in log if n == "AddLumpedPort"] == [(1, 50), (2, 75.0)]


@pytest.mark.parametrize("make", [lambda f: run_new(f)[1], antenna_project, si_project], ids=["v1", "antenna", "si"])
def test_no_other_kind_writes_an_r_or_a_near_field_plane(tmp_path, make):  # Review Focus 5; B11
    pj = make(tmp_path / "p")
    plain = spec_hash(built(pj)[4].spec)
    ports = [{**q, "R": 75.0} for q in load_project(pj)["ports"]]
    assert spec_hash(built(pj, ports=ports, near_field=True)[4].spec) == plain


def test_the_far_field_cap_is_64_for_an_emission_spec_and_stays_11_otherwise(monkeypatch):  # design 5.8; 3
    exc, grid = emission_pulse(1e9, 6e9), [1e9 + 1e8 * k for k in range(51)]
    spec = {**TINY, "excitation": exc, "nf2ff": {"f_hz": grid, "center": [2.0, 2.0, 2.0]}}
    log = fake_openems(monkeypatch)
    build_csx(spec, 1, 1e-9)
    assert any(n == "CreateNF2FFBox" for n, _, _ in log)
    with pytest.raises(ValueError):
        build_csx({**spec, "nf2ff": {"f_hz": [2e9] * (EMISSION_NF2FF_MAX + 1), "center": [0, 0, 0]}}, 1, 1e-9)
    plain = {k: v for k, v in exc.items() if k != "emission"}
    with pytest.raises(ValueError):
        build_csx({**spec, "excitation": plain, "nf2ff": {"f_hz": grid[:12], "center": [0, 0, 0]}}, 1, 1e-9)


def test_the_near_field_plane_sits_1_5_mm_over_the_lid_at_the_harmonics(tmp_path, monkeypatch):  # design 5.8
    pj = emission_project(tmp_path / "e", LPF, "U1.1", "J1.1", lid_height=2.5)
    s = built(pj, near_field=True)[4].spec
    near, plate = s["near_field"], s["metal"]["lid"]["plate"]["z"]
    assert near["start"][2] == near["stop"][2] == round(plate + 1.5, 6)
    assert near["f_hz"] == harmonics_hz(915e6, 4.575e9)
    log = fake_openems(monkeypatch)
    build_csx(s, 1, 1e-9)
    assert ("AddDump", ("near_field",), {"dump_type": 11, "file_type": 1, "frequency": near["f_hz"],
                                         "over_sampling": 4}) in log
    assert ("AddBox", (near["start"], near["stop"]), {}) in log


def test_an_emission_air_box_under_a_quarter_wave_is_flagged(tmp_path):  # design 5.6: the air gap
    notes = built(emission_project(tmp_path / "e"), air_gap_mm=20.0)[3]
    assert ("W_EMISSION_AIR_BOX", {"gap_mm": "20.0", "quarter_mm": f"{air_gap(1.83e9):.1f}",
                                   "boundary": "pml_8"}) in notes
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_emission_model.py -q`. Expected: FAIL, on the missing emission branches.
- [ ] **Step 3: The code** of Interfaces, with W_EMISSION_AIR_BOX and W_EMISSION_LIDS_LEFT_OUT and their pt-BR.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_model_csx.py tests/test_model_spec.py tests/test_antenna_model.py tests/test_si_model.py -q -rs`. Expected: PASS, nothing skipped, no golden digest moved.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/geometry/region.py src/kicad_rf_studio/core/geometry/__init__.py src/kicad_rf_studio/core/model/spec.py src/kicad_rf_studio/core/model/csx.py src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_emission_model.py
git commit -m "feat(model): the emission model, Stage 3's whole board in air under PML_8, lossless, the emission pulse its one spec marker, a termination's R, the NF2FF cap of 64 for it alone and the optional near-field plane, over-sampled as the box is (Stage 5 design 5.6, 5.8)"
graphify update .
```

---

### Task 5 [code]: The stop branch and the tail fit

**Files:**
- Modify `stoprule.py`.
- Create `tests/test_stoprule_emission.py` (its own module, so `tests/test_stoprule.py`'s module-level `EXC` stays as it is).

**Interfaces.** Produces, in `stoprule.py`:
- the constants: `TAIL_GAP_S = 2e-9` (the tail starts this long after 2·t0, the pulse's end); `TAIL_WINDOW_S = 2e-9`; `TAIL_CUT_DB = 20.0`; `RING_FACTOR = 0.01`; `RING_WIDTH = 50`;
- `stop_rule`: `"flat"` is `np.inf` when `exc.get("emission")`, else `_flat(...)` as now;
- `tail_fit(t: np.ndarray, u: np.ndarray, exc: dict, t_end: float) -> list[dict]`: the rings `{"f_hz", "q", "factor"}`, ascending in f, `q` None for an envelope that does not decay;
- `truncated(f: np.ndarray, rings: list[dict]) -> np.ndarray`: a bool per frequency, true when, for a ring with factor > RING_FACTOR, |f − f_r| ≤ RING_WIDTH·f_r/q, or for any ring whose q is None.

`tail_fit`'s algorithm. The design's §5.7 steps; the window shape and the estimator are the builder's (§6), marked:

```
t_s = 2·exc["t0"] + TAIL_GAP_S; span = t_end − t_s; K = floor(span / TAIL_WINDOW_S); K < 3 → []
grid = f1, f1 + δ, … ≤ f2 (exc's), δ = 1/(4·span)
for each port row x of u, its tail the samples with t_s ≤ t < t_end:
    X(f) = |Σ w·x·e^(−j2πft)| on grid, w = np.hanning(len(tail))     # Hann: a rectangle's −13 dB sidelobes would
                                                                       # read as peaks within 20 dB (builder's)
    X.max() == 0 → next port
    peaks = grid[scipy.signal.find_peaks(X)[0]] with X ≥ X.max()·10^(−TAIL_CUT_DB/20)   # this port's own peaks
    in each window k < K, t_s + k·W ≤ t < t_s + (k+1)·W:                               # back to back, rectangular
        c = np.linalg.lstsq(columns cos 2πft and sin 2πft of every f of peaks, x in the window)   # jointly (builder's):
        A_k(f) = hypot of f's two coefficients            # a lone DFT leaks a neighbour 0.6 GHz off into the envelope
    for each peak f_r: windows with A_k > 0; fewer than 3 → next peak
        slope = np.polyfit(window centres, 20·log10(A_k), 1)[0]                        # dB/s
        slope ≥ 0 → (f_r, None, 1.0); else Q = (20/ln 10)·π·f_r/|slope|, factor = e^(−π·f_r·t_end/Q)
merge over the ports, ascending in f: an entry within 2/span of a group's first joins it; each group keeps the entry
of its largest factor, q None counting as factor 1.0                                    # BC6: the worst over the ports
```

`# ponytail:` on the lstsq: 2·peaks columns must stay under a window's samples (about 48 at f2 3 GHz); a peak list that long would need fewer, stronger peaks.

- [ ] **Step 1: The failing tests,** in `tests/test_stoprule_emission.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest

from kicad_rf_studio.core.model.spec import emission_pulse
from kicad_rf_studio.stoprule import RING_FACTOR, Records, stop_rule, tail_fit, truncated

EXC = emission_pulse(1.83e9, 3e9)  # the probe's pulse: 1.40–3 GHz, t0 1.79 ns, T_max 31 ns
SPAN = 31e-9 - 2 * EXC["t0"] - 2e-9  # the tail past 2·t0 + 2 ns


def ringing(modes, ports=1, t_end=31e-9):
    """f1's synthetic record: port 0 the band pulse, and at each port each mode (f, Q, [its amplitude at each port],
    relative to the pulse's peak) as a·e^(−π·f·(t − 2·t0)/Q)·sin(2π·f·t) from 2·t0; i = u/50, the energy Σu²."""
    t, t0 = np.arange(0, t_end, 5e-12), EXC["t0"]
    fm, fw = (EXC["f1"] + EXC["f2"]) / 2, (EXC["f2"] - EXC["f1"]) / 2
    u = np.zeros((ports, t.size))
    u[0] = np.sin(2 * np.pi * fm * (t - t0)) * np.exp(-(2 * np.pi * fw * t / 3 - 3) ** 2) * (t < 2 * t0)
    for f, q, amps in modes:
        ring = np.exp(-np.pi * f * (t - 2 * t0) / q) * np.sin(2 * np.pi * f * t) * (t >= 2 * t0)
        for k, a in enumerate(amps):
            u[k] += a * ring
    return Records(t, u, t, u / 50, t, (u ** 2).sum(0) + 1e-30)


def fitted(rec, t_end=31e-9):
    return tail_fit(rec.t_u, rec.u, EXC, t_end)


def test_an_emission_job_that_rings_is_never_flat():  # design 5.7; f1
    rec = ringing([(1.413e9, 232, [0.1, 0.01])], ports=2)
    assert stop_rule(rec, 0, "normal", EXC) is None  # no verdict to T_max: the job ends there, "t_max"
    v = stop_rule(rec, 0, "normal", {k: x for k, x in EXC.items() if k != "emission"})
    assert v.kind == "flat" and 2 * EXC["t0"] + 5e-9 <= v.t <= 2 * EXC["t0"] + 9e-9  # today's rule, as f1 found


def test_the_tail_fit_reads_one_rings_q_and_its_truncation_factor():  # design 5.7; f1's single mode
    (r,) = fitted(ringing([(1.413e9, 232, [0.1, 0.01])], ports=2))
    assert abs(r["f_hz"] - 1.413e9) <= 1 / SPAN and r["q"] == pytest.approx(232, rel=0.05)
    assert r["factor"] == pytest.approx(np.exp(-np.pi * 1.413e9 * 31e-9 / 232), rel=0.05)  # 0.553


@pytest.mark.parametrize("modes", [[(1.413e9, 232), (1.999e9, 895)],  # risk 2: two modes 0.59 GHz apart
                                   [(1.413e9, 232), (1.999e9, 1789)]])  # f1's plane pair, its slowest TM11
def test_two_rings_at_one_port_are_both_fitted_and_neither_reads_as_held(modes):  # risk 2; AR-5
    rings = fitted(ringing([(f, q, [0.1]) for f, q in modes]))
    assert len(rings) == 2
    for r, (f, q) in zip(rings, modes):
        assert abs(r["f_hz"] - f) <= 2 / SPAN and r["q"] == pytest.approx(q, rel=0.10) and r["factor"] > RING_FACTOR


def test_three_rings_over_two_ports_are_the_union_and_a_ring_weak_at_the_source_is_seen():  # risk 2; BC6
    modes = [(1.413e9, 232, [0.1, 0.001]), (1.999e9, 895, [0.001, 0.1]), (2.826e9, 186, [0.05, 0.001])]
    rings = fitted(ringing(modes, ports=2))
    assert len(rings) == 3
    for r, (f, q, _) in zip(rings, modes):
        assert abs(r["f_hz"] - f) <= 2 / SPAN and r["q"] == pytest.approx(q, rel=0.10) and r["factor"] > RING_FACTOR


def test_a_held_ring_has_no_q_and_truncates_every_frequency_beside_decaying_ones():  # Review Focus 4; AR-5
    modes = [(1.413e9, 232, [0.1]), (1.999e9, -2000, [0.03]), (2.826e9, 186, [0.1])]  # the middle one grows a little
    a, held, c = fitted(ringing(modes))
    assert (held["q"], held["factor"]) == (None, 1.0) and abs(held["f_hz"] - 1.999e9) <= 2 / SPAN
    assert a["q"] == pytest.approx(232, rel=0.10) and c["q"] == pytest.approx(186, rel=0.10)
    assert truncated(np.array([1e9, 3e9]), [a, held, c]).all()


def test_a_damped_ring_converges_and_truncates_nothing():  # design 5.7: a factor under 0.01
    rec = ringing([(1.413e9, 10, [0.1])])
    v = stop_rule(rec, 0, "normal", EXC)
    assert v.kind == "converged" and v.t < 31e-9
    rings = fitted(rec, v.t)
    assert all(r["factor"] < RING_FACTOR for r in rings) and not truncated(np.array([1.413e9]), rings).any()


def test_a_quiet_tail_and_a_short_one_fit_nothing():  # Review Focus 4
    assert fitted(ringing([])) == []  # the pulse ends at 2·t0
    short = 2 * EXC["t0"] + 2e-9 + 5e-9  # two whole 2 ns windows only
    assert fitted(ringing([(1.413e9, 232, [0.1])], t_end=short), short) == []


def test_truncated_is_50_f_over_q_round_each_ring_over_0_01():  # design 5.7
    rings = [{"f_hz": 2e9, "q": 1000.0, "factor": 0.5}, {"f_hz": 2.5e9, "q": 100.0, "factor": 0.005}]
    f = np.array([1.89e9, 1.9e9, 2.1e9, 2.11e9, 2.5e9])
    assert truncated(f, rings).tolist() == [False, True, True, False, False]
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_stoprule_emission.py -q`. Expected: FAIL, with `ImportError` on `tail_fit`.
- [ ] **Step 3: The code** of Interfaces.
- [ ] **Step 4: Run them.** Use Step 2's command. Expected: PASS.
  - **Stop rule (risk 2):** a Q outside its stated tolerance, a ring missed, or a held ring read as decaying (or the converse) stops the task for a ruling, with the measured values. So does today's flat verdict outside its window in `test_an_emission_job_that_rings_is_never_flat`. Never widen a tolerance or a window, and never change the 2 ns windows, the 20 dB cut, the Hann peak search or the joint estimator to make one pass.
  - Then run `tests/test_stoprule.py tests/test_traces_real.py tests/test_p0.py tests/test_golden_v1.py -q -rs`. Expected: PASS, nothing skipped, the `stop` pins unchanged.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/stoprule.py tests/test_stoprule_emission.py
git commit -m "feat(stoprule): the emission branch, never flat, ending at T_max, and the tail fit: each port's ringing peaks, their envelopes fitted jointly in 2 ns windows, a Q and a truncation factor each, tested on one-, two- and three-mode records and a held ring first (Stage 5 design 5.7; risk 2)"
graphify update .
```

---

### Task 6 [code]: The far field at 3 m, normalisation and closure

**Files:**
- Modify `core/post/farfield.py`: `port_dft` and `snapped`. `port_powers` calls `port_dft`, so its bits are unchanged.
- Modify `core/post/antenna.py`: `far_field_of` calls `snapped`.
- Create `core/post/emission.py`.
- Messages.
- Tests: `tests/test_post_emission.py`.

**Interfaces.**
- **Produces, in `farfield.py`:**
  - `port_dft(t_u, u, t_i, i, f) -> tuple[np.ndarray, np.ndarray]`: U and I, port_powers' DFT;
  - `snapped(f, exact) -> np.ndarray`: far_field_of's snap, each value to the nearest of `exact` within a relative 1e-6.
- **Produces, in `core/post/emission.py`:**
  - the constants: `R_M = 3.0`, `P_ACC_MIN = 1e-3`, `BACKED = 3.0`, `EPS_LIMIT = round(ETA_LIMIT - 1, 6)`;
  - `EMISSION_OUTPUTS = re.compile(r"emission(_rings)?\.csv")` and `EMISSION_LIMITS = ("I_LIMIT_EMISSION",)`;
  - `EMISSION_COLUMNS = ("f_hz", "harmonic", "e_3m_db_per_v_relative", "e_3m_db_per_ma_relative", "theta_deg", "phi_deg", "p_inc_w", "p_acc_w", "p_rad_w")`;
  - `incident(t_u, u, t_i, i, f) -> np.ndarray`: (U + Z0·I)/2;
  - `emission_rows(sphere: FarField, t_u, u, t_i, i, rings, *, resistive: bool, f0: float | None) -> list[dict]`. One row per frequency of `sphere`, in its order. Row 0 of u and i is the source, every other row a termination. Each row holds:
    - `"f_hz"`;
    - `"harmonic"`: n when f0 is given, n = round(f/f0) ≥ 2 and |f − n·f0| ≤ 1e-6·n·f0, else None;
    - `"e_3m"`: max over (θ, φ) of √(|E_θ|² + |E_φ|²)/R_M, with that point's `"theta_deg"` and `"phi_deg"`;
    - `"e_v"` = e_3m/|U_inc| and `"e_ma"` = e_3m/(|I|·1e3), the source's U_inc and I;
    - `"p_inc"` and `"p_acc"`, port_powers' of the source; `"p_rad"`, the sphere's; `"p_term"`, the list of −½·Re(U_k·I_k*);
    - `"eps"` = (p_acc − p_rad − Σp_term)/p_inc, B8's; `"eps_acc"` = the same residual over p_acc, report-only (AR-20);
    - `"closure"`, the first that holds: "truncated" (`truncated`), "p_acc_low" (p_acc < P_ACC_MIN·p_inc), "resistive" (`resistive`), else "judged";
    - `"basis"`: "closure-backed" when judged and p_rad/p_inc ≥ BACKED·|eps|, else "nf2ff-only";
  - `emission_csv(rows, names) -> bytes`: EMISSION_COLUMNS, then `p_term_<name>_w` per termination, then `eps`, `closure`, `p_rad_basis`. The e columns are 20·log10 of e_v and e_ma, harmonic is empty for None, comma-separated with "\n" line ends and numbers as Python's repr, as `antenna._csv` writes;
  - `rings_csv(rings) -> bytes`: `f_hz,q,factor,truncating`;
  - `ring_lines(rings, t_end) -> list`: W_EMISSION_RING per ring with factor > RING_FACTOR and a q, and W_EMISSION_RING_HELD per ring with q None, in list order;
  - `emission_lines(project, rows) -> list`: I_EMISSION_BAND, its harmonics as `"1830, 2745 MHz"` or "T_NONE"; I_EMISSION_HARMONIC per harmonic row; I_EMISSION_CLOSURE (the worst |ε| over the judged rows) or I_EMISSION_NOT_JUDGED; then W_EMISSION_CLOSURE when that worst |ε| is over EPS_LIMIT.

  dB values are given to 2 decimals, |ε| and the factor to 4, and the angles as :g.

- [ ] **Step 1: The failing tests,** in `tests/test_post_emission.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io

import numpy as np
import pytest

from kicad_rf_studio.core.post.emission import (EMISSION_COLUMNS, R_M, emission_csv, emission_lines, emission_rows,
                                                incident, ring_lines, rings_csv)
from kicad_rf_studio.core.post.farfield import FarField, port_dft, port_powers, snapped

F = [1.83e9, 2.0e9, 2.745e9]
RINGS = [{"f_hz": 2.0e9, "q": 1000.0, "factor": 0.5}]  # truncates 1.9 to 2.1 GHz
PROJECT = {"f0_hz": 915e6, "band": {"f_lo_hz": 1.83e9, "f_max_hz": 3e9}}


def far(e_theta=3.0, p_rad=0.0099, f=F):
    theta, phi = np.arange(0, 181, 5.0), np.arange(0, 360, 5.0)
    shape = (len(f), theta.size, phi.size)
    et = np.zeros(shape, complex)
    et[:, 18, 0] = e_theta  # at θ 90°, φ 0°: 3 V/m at 1 m, 1 V/m at 3 m
    return FarField(np.array(f), theta, phi, np.full(len(f), p_rad), np.ones(len(f)), np.ones(shape), et,
                    np.zeros(shape, complex))


def waves(source=(2.0, 0.02), terms=((1.0, -0.02),)):
    """port_dft is 2·Δt·Σ x·e^(−j2πft): at Δt 0.5 s with one sample at t 0, U and I are those samples at every f."""
    t, ports = np.arange(4) * 0.5, [source, *terms]
    u, i = (np.array([[p[q], 0, 0, 0] for p in ports], float) for q in (0, 1))
    return t, u, t, i


def test_the_field_at_3_m_per_v_and_per_ma_and_the_closure():  # design 5.8; B4, B6, B8
    a, b, c = rows = emission_rows(far(), *waves(), RINGS, resistive=False, f0=915e6)
    # U 2, I 0.02: U_inc 1.5, P_acc 0.02, P_inc 3²/400 = 0.0225; the termination's ½·1·0.02 = 0.01
    assert (a["harmonic"], b["harmonic"], c["harmonic"]) == (2, None, 3)
    assert (a["e_3m"], a["e_v"], a["e_ma"]) == pytest.approx((1.0, 1 / 1.5, 0.05))
    assert (a["theta_deg"], a["phi_deg"]) == (90.0, 0.0)
    assert (a["p_inc"], a["p_acc"], a["p_term"]) == (pytest.approx(0.0225), pytest.approx(0.02), [pytest.approx(0.01)])
    assert a["eps"] == pytest.approx((0.02 - 0.0099 - 0.01) / 0.0225)
    assert a["eps_acc"] == pytest.approx((0.02 - 0.0099 - 0.01) / 0.02)  # report-only, on P_acc (AR-20)
    assert [r["closure"] for r in rows] == ["judged", "truncated", "judged"]
    assert [r["basis"] for r in rows] == ["closure-backed", "nf2ff-only", "closure-backed"]


def test_a_frequency_is_not_judged_with_little_power_taken_in_or_a_resistor_in_the_grid():  # design 5.8
    low = emission_rows(far(), *waves(source=(2.0, 1e-6)), [], resistive=False, f0=None)
    assert {r["closure"] for r in low} == {"p_acc_low"}
    rows = emission_rows(far(), *waves(), RINGS, resistive=True, f0=None)
    assert [r["closure"] for r in rows] == ["resistive", "truncated", "resistive"]


def test_incident_is_the_50_ohm_sources_forward_wave_on_port_powers_dft():  # design 5.8: P3-A's DFT
    t, u, _, i = waves()
    f = np.array(F)
    assert incident(t, u[0], t, i[0], f) == pytest.approx([1.5] * 3)
    U, I = port_dft(t, u[0], t, i[0], f)
    assert port_powers(t, u[0], t, i[0], f)[0] == pytest.approx(0.5 * (U * I.conj()).real)


def test_a_float32_frequency_snaps_to_its_listed_one_and_reads_as_its_harmonic():  # design 5.8
    stored = np.float32(2.745e9).item()
    assert stored != 2.745e9
    assert snapped(np.array([stored, 2.0e9 + 5000]), [2.745e9, 2.0e9]).tolist() == [2.745e9, 2.0e9 + 5000]
    rows = emission_rows(far(f=[1.83e9, 2.0e9, stored]), *waves(), [], resistive=False, f0=915e6)
    assert rows[2]["harmonic"] == 3


def test_the_csvs_hold_each_frequency_in_db_re_1_vm_per_v_and_per_ma_and_the_rings():  # design 5.8: units
    rows = emission_rows(far(), *waves(), RINGS, resistive=False, f0=915e6)
    table = list(csv.reader(io.StringIO(emission_csv(rows, ["P2"]).decode())))
    assert table[0] == [*EMISSION_COLUMNS, "p_term_P2_w", "eps", "closure", "p_rad_basis"] and len(table) == 4
    assert float(table[1][2]) == pytest.approx(20 * np.log10(1 / 1.5))
    assert float(table[1][3]) == pytest.approx(20 * np.log10(0.05))
    assert (table[1][1], table[2][1], table[2][-2]) == ("2", "", "truncated")
    assert rings_csv(RINGS).decode().splitlines() == ["f_hz,q,factor,truncating", "2000000000.0,1000.0,0.5,True"]


def test_the_lines_state_the_band_each_harmonic_the_closure_and_the_rings():  # design 5.7, 5.8
    rows = emission_rows(far(), *waves(), RINGS, resistive=False, f0=915e6)
    assert [c for c, _ in emission_lines(PROJECT, rows)] == [
        "I_EMISSION_BAND", "I_EMISSION_HARMONIC", "I_EMISSION_HARMONIC", "I_EMISSION_CLOSURE"]
    worse = emission_rows(far(p_rad=0.0), *waves(), [], resistive=False, f0=915e6)  # ε 0.444
    assert [c for c, _ in emission_lines(PROJECT, worse)][-1] == "W_EMISSION_CLOSURE"
    none = emission_rows(far(), *waves(), [], resistive=True, f0=915e6)
    assert "I_EMISSION_NOT_JUDGED" in [c for c, _ in emission_lines(PROJECT, none)]
    held = {"f_hz": 1.5e9, "q": None, "factor": 1.0}
    assert [c for c, _ in ring_lines([*RINGS, {"f_hz": 2.5e9, "q": 100.0, "factor": 0.005}, held], 31e-9)] == [
        "W_EMISSION_RING", "W_EMISSION_RING_HELD"]
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_post_emission.py -q`. Expected: FAIL, with `ModuleNotFoundError` on `core.post.emission`.
- [ ] **Step 3: The code** of Interfaces, with Task 6's fifteen codes and their pt-BR.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_post_farfield.py tests/test_post_antenna.py tests/test_sexpr.py tests/test_golden_antenna.py -q -rs`. Expected: PASS, nothing skipped, the antenna's outputs unchanged, and the scan clean on the new codes.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/post/farfield.py src/kicad_rf_studio/core/post/antenna.py src/kicad_rf_studio/core/post/emission.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_post_emission.py
git commit -m "feat(post): emission rows, the largest field over the sphere at 3 m per V of the incident wave and per mA, the powers, energy closure judged only where not truncated with power taken in and no grid resistor, its CSVs, lines and limit line (Stage 5 design 5.8)"
graphify update .
```

---

### Task 7 [code]: The emission fingerprint and n(f)

**Files:**
- Modify `pipeline.py` (`fingerprint`) and `core/post/emission.py`.
- Tests: `tests/test_post_emission.py`; create `tests/test_emission_run.py`.

**Interfaces.**
- **`pipeline.fingerprint`:** an emission branch first. It returns:
  - `preset`, `mesh`, `region`, `f0_hz`, `band`, `t_max_s`, `air_gap_mm`, `boundary`, `far_field`, `near_field`, `stackup` and `lid_height_mm`;
  - `"ends": [[q["signal"], q.get("R", 50.0)] for q in project["ports"]]`;
  - `"copper"`, `"app"` and `"openems"`, as the antenna branch has them.

  It leaves out `lid`, `overrides`, `results`, `verify` and `board`.
- **In `core/post/emission.py`:**
  - `FLOOR_STEP_DB = 0.05`;
  - `null_floor(a: FarField, b: FarField, u_a: np.ndarray, u_b: np.ndarray) -> np.ndarray`: n(f), the largest over the sphere of |E_b − E_a|, where E = (E_θ, E_φ)/R_M/U_inc. ValueError when the frequencies (relative 1e-6), θ or φ differ. The sphere is the finest grid that holds every frequency (the 1° cuts hold the first only);
  - `floor_db(n) -> np.ndarray`: `np.round(np.ceil(np.round(20·log10(3·n)/FLOOR_STEP_DB, 9))·FLOOR_STEP_DB, 2)`, and −inf where n is 0.
- **Consumers:** `tools/probe.py` calls both for criterion 2, and plan 4's compare will reuse them.

- [ ] **Step 1: The failing tests.** In `tests/test_post_emission.py`:

```python
from kicad_rf_studio.core.post.emission import floor_db, null_floor


def test_n_is_the_largest_vector_difference_over_the_sphere_per_v_at_3_m():  # design 5.10; f2
    u = np.full(3, 1.5)
    assert null_floor(far(3.0), far(3.0j), u, u) == pytest.approx([abs(3 - 3j) / R_M / 1.5] * 3)  # max|E| equal
    assert null_floor(far(3.0), far(3.3), u, u) == pytest.approx([0.3 / R_M / 1.5] * 3)
    with pytest.raises(ValueError):
        null_floor(far(), far(f=[1.83e9, 2.0e9, 2.8e9]), u, u)


def test_the_floor_is_r13s_form_rounded_up_to_0_05_db():  # design 5.10; R-13
    assert floor_db(np.array([10 ** (-47.28 / 20), 0.05, 0.0])).tolist() == [-37.7, -16.45, -np.inf]
```

  In `tests/test_emission_run.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.project import load_project
from test_cli_emission import emission_project
from test_project import VIA


def test_the_emission_fingerprint_leaves_out_the_lid_the_overrides_and_the_board(tmp_path, monkeypatch):  # 5.10
    monkeypatch.setattr(runs, "openems_versions", lambda: ("0.37.0", "0.7.0"))
    base = load_project(emission_project(tmp_path / "a"))
    fp = pipeline.fingerprint(base)
    assert fp["ends"] == [["TP1.1", 50.0], ["TP2.1", 50.0]] and {"lid", "overrides", "board", "results"}.isdisjoint(fp)
    for same in ({"lid": False}, {"overrides": [VIA]}, {"board": {"path": "b.kicad_pcb", "sha256": "0" * 64}}):
        assert pipeline.fingerprint({**base, **same}) == fp
    for other in ({"lid_height_mm": 2.0}, {"near_field": True}, {"t_max_s": 40e-9}, {"preset": "strict"},
                  {"ports": [base["ports"][0], {**base["ports"][1], "R": 75.0}]}):
        assert pipeline.fingerprint({**base, **other}) != fp
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_post_emission.py tests/test_emission_run.py -q`. Expected: FAIL, with `ImportError` on `null_floor`.
- [ ] **Step 3: The code** of Interfaces.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_golden_antenna.py tests/test_golden_si.py tests/test_compare.py tests/test_si_compare.py -q -rs`. Expected: PASS, nothing skipped, the `fingerprint` pins unchanged.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/core/post/emission.py tests/test_post_emission.py tests/test_emission_run.py
git commit -m "feat(emission): the fingerprint that leaves out the lid, the overrides and the board and keeps the ends with their R, and n(f), the largest vector difference over the sphere per V at 3 m, with R-13's floor (Stage 5 design 5.10)"
graphify update .
```

---

### Task 8 [code]: An emission run, end to end

**Files:**
- Modify `pipeline.py`.
- Messages.
- Tests: `tests/test_emission_run.py`.

**Interfaces.**
- **`prepare(..., jobs: int | None = None)`:** `pool = min(pool, jobs or len(model.spec["ports"]))`.
- **`run_ports(..., spec_file: str = "model.json")`:** passes `spec=f"../{spec_file}"` to `runs.write_job`, whose dict keeps `"spec"` first, so job.json's bytes are unchanged by default (the `run` pins).
- **`far_field(job, step_deg)`:** passes `spec=finished["spec"]` to `runs.write_job`, so the transform builds its box from the driven job's spec.
- **`emission_parts(project) -> None`:** E_EMISSION_PART {ref, value} for the first part port (role "port" or "curve_port") that is a curve port or whose value neither `values.bypass` nor `port_value` reads; verify_spec would otherwise refuse after the setup job, in words that send the user to `verify`, or crash on a curve port's `"dir": None`.
- **`simulate(model, project, run_dir, far_field: dict | None = None)`:**
  - for an emission project, prepare takes `small=True` and `jobs=1`;
  - after the cost lines, `model = replace(model, spec=verify_spec(model.spec, parts(project), runs.job_dir(run_dir, 0, "setup") / "operator_dump.vtr", setup["dt"], far_field=far_field))`, written to `run_dir / "driven.json"` as `runs.write_spec` writes model.json;
  - then `run_ports(..., [1], ..., spec_file="driven.json")`;
  - the speed refresh skips antenna and emission.
- **`_run`, for an emission project:**
  - `emission_parts(project)` first, before prepare and any job;
  - `loss` is None; `fp = fingerprint(project)`, taken before the jobs; `box = far_field_box(project, board, geom)`, passed to simulate;
  - after the kept check, `done[0]["rings"] = tail_fit(t_u, u, excitation(project), done[0]["t_stop"])` from the job's whole waves.npz;
  - results gain `"far_field": None` and `"fingerprint": fp`, as an antenna's do;
  - the pre-transform `write_outputs` stays the antenna's alone (`"nf2ff" in model.spec`): an emission run has no S files to keep;
  - the transform runs for `"nf2ff" in model.spec or emission(project)`.
- **`emission_of(results, project) -> tuple[list[dict], list[str]] | None`:**
  - None without `results["far_field"]`;
  - E_RESULTS_WAVES for the first missing of the sphere's .h5, the job's waves.npz and `driven.json`;
  - the sphere's f snapped to `project["far_field"]["f_hz"]`;
  - `emission_rows(sphere, <the whole waves.npz, the window the dumps accumulate over, as P3-A reads it>, rings, resistive=any(g.get("R") is not None for g in driven["grid"]), f0=project["f0_hz"])`;
  - the terminations' names are `driven.json`'s ports after the first.
- **`emission_outputs(path, project, command, *, errors_as_lines=False) -> list`:**
  - the lines, in order: I_EMISSION_RELATIVE, `basis_lines`, `ring_lines(rings, t_stop)`, then `emission_lines` or I_EMISSION_NO_FAR_FIELD;
  - the files `emission.csv` (with a far field) and `emission_rings.csv`, through `write(..., EMISSION_OUTPUTS, command)`;
  - then I_OUTPUTS, or E_RESULTS_WRITE in its place, then EMISSION_LIMITS;
  - errors are handled as `antenna_outputs` handles them.
- **`write_outputs`** dispatches an emission project to `emission_outputs` first.
- **`retune` and `verify`** raise E_EMISSION_ONE_RUN {path, command: "retune" or "verify"} for an emission project, right after their first `read_project`, before the lock.

- [ ] **Step 1: The failing tests,** added to `tests/test_emission_run.py`:

```python
import json
from pathlib import Path

import pytest

from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.emission import EMISSION_COLUMNS
from kicad_rf_studio.core.project import save_project
from test_cli_emission import LPF
from test_run_antenna import events


def test_an_emission_run_is_three_jobs_in_one_folder_and_writes_its_csvs(tmp_path, calibrated):  # 5.6, 5.8
    pj = emission_project(tmp_path / "e")
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    r, run_dir = d["results"], Path(d["results"]["run_dir"])
    project, board, geom, _ = pipeline.load(pj)
    spec = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    driven = json.loads((run_dir / "driven.json").read_text(encoding="utf-8"))
    assert r["model_hash"] == spec_hash(spec) == spec_hash(pipeline.build_model(project, board, geom).spec)
    assert "nf2ff" not in spec and driven["nf2ff"]["f_hz"] == d["far_field"]["f_hz"] and driven["excitation"]["emission"]
    spec_of = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))["spec"] for p in run_dir.glob("job-*/job.json")}
    assert (spec_of.pop("job-0-setup"), spec_of.pop("job-1-P1")) == ("../model.json", "../driven.json")
    assert list(spec_of.values()) == ["../driven.json"]  # the transform reads the driven job's spec
    assert [j["port"] for j in r["jobs"]] == ["P1"] and isinstance(r["jobs"][0]["rings"], list)
    assert set(r["far_field"]) == {"sphere", "elevation", "azimuth"} and r["loss_expected"] is None
    assert r["fingerprint"] == pipeline.fingerprint(d)
    results = pj.parent / "results"
    assert sorted(f.name for f in results.iterdir()) == ["emission.csv", "emission_rings.csv"]
    header = (results / "emission.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[:9] == list(EMISSION_COLUMNS) and "p_term_P2_w" in header
    ev = [json.loads(x) for x in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    start = next(e for e in ev if e["code"] == "I_RUN_START")
    assert (start["params"]["runs"], start["params"]["pool"]) == (1, 1)
    codes = events(run_dir)
    assert "I_GATES_PASSED_PML" in codes and codes.index("I_EMISSION_RELATIVE") < codes.index("I_OUTPUTS")
    assert codes[-1] == "I_LIMIT_EMISSION"


def test_a_failed_transform_keeps_the_job_and_says_so(tmp_path, calibrated, monkeypatch):  # as Stage 3 5.5
    def fail(*_, **__):
        raise KrsError("E_WORKER_FAILED", job="T_JOB_FAR_FIELD", exit_code=1, log="log.txt")

    monkeypatch.setattr(pipeline, "far_field", fail)
    pj = emission_project(tmp_path / "e")
    assert pipeline.run(pj) == 2
    r = load_project(pj)["results"]
    assert r["far_field"] is None and {"E_WORKER_FAILED", "I_EMISSION_NO_FAR_FIELD"} <= set(events(r["run_dir"]))


def test_a_part_the_grid_cannot_hold_is_refused_before_any_job(tmp_path, calibrated):  # AR-12
    pj = emission_project(tmp_path / "e", LPF, "U1.1", "J1.1", lid_height=2.5)
    d = load_project(pj)
    next(q for q in d["chain"]["shunt"] if q["ref"] == "C2")["value"] = "C_Small"
    save_project(pj, d)
    run_dir = tmp_path / "r"
    assert pipeline.run(pj, run_dir) == 2
    assert "E_EMISSION_PART" in events(run_dir) and not (run_dir / "job-0-setup").exists()


def test_retune_and_verify_refuse_an_emission_project_and_compare_stays_two_kinds(tmp_path):  # 5.6; plan 4
    pj = emission_project(tmp_path / "e")
    for call in (lambda: pipeline.retune(pj, []), lambda: pipeline.verify(pj)):
        with pytest.raises(KrsError) as e:
            call()
        assert e.value.code == "E_EMISSION_ONE_RUN"
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(pj, pj)
    assert e.value.code == "E_COMPARE_KIND"
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_emission_run.py -q`. Expected: FAIL: the run raises in the v1 outputs, or the assertions fail.
- [ ] **Step 3: The code** of Interfaces, with E_EMISSION_ONE_RUN, I_EMISSION_NO_FAR_FIELD and E_EMISSION_PART and their pt-BR.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_run.py tests/test_run_antenna.py tests/test_si_run.py tests/test_verify.py tests/test_retune.py tests/test_p0.py tests/test_p3a.py tests/test_ee.py -q -rs`. Expected: PASS, nothing skipped, the `run` pins unchanged.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_emission_run.py
git commit -m "feat(run): an emission run, three jobs in one folder: the setup on model.json, the one driven job on driven.json with every part in the grid, the transform on its spec, the tail fit in its record and the emission CSVs and lines; a part the grid cannot hold refused first; retune and verify refuse the kind (Stage 5 design 5.6 to 5.8)"
graphify update .
```

---

### Task 9 [code]: Cost

**Files:**
- Modify `pipeline.py`.
- Messages.
- Tests: `tests/test_emission_run.py`.

**Interfaces.**
- **`cost_seconds(model, project, dt, pool, per_job_mcs, t) -> float`:** cost_notes' inner `seconds`, moved out: ceil(runs/pool) × weighted × (t/dt) / (mcs·1e6). runs is 1 for an emission project, else `len(spec["ports"])`; weighted and mcs follow the antenna's branch for antenna or emission (`cell_split`, `PML_WEIGHT`, `small_speed(pool)`), and the Debye branch for SI. cost_notes calls it wherever it called `seconds`, so its lines are unchanged (the `cost` pins).
- **`cost_notes`:** the I_COST_SPLIT branch is antenna or emission; I_COST_TIME's runs count is 1 for an emission project; W_EMISSION_LONG_RUN {time} is added for an emission project whose `cost_seconds` to T_max exceeds LONG_RUN_S.
- **`cost()`:** `prepare(..., small=antenna(project) or emission(project), si=si(project), jobs=1 if emission(project) else None)`.
- **The reading of §5.6's "cost counts jobs 1 and 2"** (AR-18): `cost` runs the setup job, as it does for every kind, for its gates and dt, and predicts the one driven job; the transform is not predicted, and the probe records it apart.
- **Consumers:** `tools/probe.py` predicts with `cost_seconds`. `tools/ea.py` counts its hand-written specs itself on the same basis (Task 13).

- [ ] **Step 1: The failing tests,** added to `tests/test_emission_run.py`:

```python
from kicad_rf_studio.core.model.spec import cell_split


def test_cost_counts_the_driven_job_with_the_antennas_pml_weight(tmp_path, calibrated):  # design 5.11
    pj, run_dir = emission_project(tmp_path / "e"), tmp_path / "c"
    run_dir.mkdir()
    assert pipeline.cost(pj, run_dir) == 0
    ev = [json.loads(x) for x in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "I_COST_SPLIT" in [e["code"] for e in ev]
    assert next(e for e in ev if e["code"] == "I_COST_TIME")["params"]["runs"] == 1


def test_cost_seconds_and_the_long_run_line(tmp_path):  # design 5.11: past LONG_RUN_S
    project, board, geom, _ = pipeline.load(emission_project(tmp_path / "e"))
    model = pipeline.build_model(project, board, geom)
    cells = len(model.mesh.x) * len(model.mesh.y) * len(model.mesh.z)
    weighted = cells + (runs.PML_WEIGHT - 1) * cell_split(model.spec)[2]
    assert pipeline.cost_seconds(model, project, 1e-13, 1, 100.0, 1e-9) == pytest.approx(
        weighted * 1e4 / (100e6 * runs.small_speed(1)))
    setup = {"dt": 1e-13, "node": [0, 1, 1, 1]}
    assert "W_EMISSION_LONG_RUN" in [c for c, _ in pipeline.cost_notes(model, project, setup, 4, 1, 1e-3)]
    assert "W_EMISSION_LONG_RUN" not in [c for c, _ in pipeline.cost_notes(model, project, setup, 4, 1, 1e9)]
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_emission_run.py -q -k cost`. Expected: FAIL, with `AttributeError` on `cost_seconds`.
- [ ] **Step 3: The code** of Interfaces, with W_EMISSION_LONG_RUN and its pt-BR.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_cli_cost.py tests/test_cost_model.py tests/test_si_cost.py -q -rs`. Expected: PASS, nothing skipped, the `cost` and `run` pins unchanged.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_emission_run.py
git commit -m "feat(cost): the emission kind's cost, the antenna's PML weight and small-model speed on its one driven job after the setup cost runs, a warning past two hours, and cost_seconds for the probe tool (Stage 5 design 5.11)"
graphify update .
```

---

### Task 10 [code]: Overrides applied at load

**Files:**
- Create `core/geometry/overrides.py`.
- Modify `pipeline.py` (`load`).
- Messages.
- Create `tests/test_overrides.py`.

**Interfaces.** Produces, in `core/geometry/overrides.py`:
- `CLEARANCE = 0.2` (mm): KiCad's default netclass clearance, as f3's probes used it, for an added via and for a fill.
- `span(board, layers) -> list[str]`: the copper layers from `layers[0]` to `layers[1]` in `board.copper_layers` order.
- `blocker(board, at, radius, net, layers) -> str | None`:
  - "T_OVERRIDE_COPPER" when the disc of `radius` + CLEARANCE at `at` meets, on a layer of `span`, a track, a pad with copper there, or a CopperArea whose source is not "zone", of another net, or another net's via whose span shares a layer;
  - else "T_OVERRIDE_EDGE" when that disc is not within the outline;
  - else None.
- `apply_overrides(board, overrides) -> list[tuple[str, dict]]`, entry n's uuid being `f"override-{n}"`:
  1. **The vias first.** A via whose `blocker` is not None is left out with W_OVERRIDE_REFUSED {from, x_mm, y_mm (KiCad's frame, :.3f), reason}. Otherwise it is appended to `board.vias` as a `Via`, and every zone-sourced area of another net on its span loses the disc of diameter/2 + CLEARANCE.
  2. **Then the fills.** Each is Polygon(exterior, holes), less every other-net track, pad, area and via disc on its layer grown by CLEARANCE, appended as `CopperArea(layer, net, polygon, "override", uuid)` when not empty.
- `pipeline.load`: before `build_geometry`, `extra = apply_overrides(board, project["overrides"]) if emission(project) and project.get("overrides") else []`; then `notes += [*board.warnings, *extra, *geom.notes, ...]`, so the overrides' notes follow W_BOARD_CHANGED and the board's warnings, and `extra` is empty for every other kind (the `load` pins).

- [ ] **Step 1: The failing tests,** in `tests/test_overrides.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import shapely
from shapely.geometry import Point

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.geometry.overrides import CLEARANCE, apply_overrides
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_emission import emission_project
from test_cli_new import FIX

SLOT = {"kind": "fill", "layer": "In1.Cu", "net": "GND", "from": "R1-test",
        "polygon_mm": {"exterior": [[116, -103], [117, -103], [117, -97], [116, -97]], "holes": []}}


def via(x, y, net="GND"):
    return {"kind": "via", "at_mm": [x, y], "diameter_mm": 0.6, "drill_mm": 0.3, "layers": ["F.Cu", "B.Cu"],
            "net": net, "from": "R4-test"}


def plane(board, layer, net):
    return shapely.union_all([a.polygon for a in board.areas if (a.layer, a.net) == (layer, net)])


def test_a_fill_fills_the_void_as_the_twin_board_draws_it():  # design 5.9; f3's probe 1
    gap, twin = load_board(FIX / "usb2_hs_gap.kicad_pcb"), load_board(FIX / "usb2_hs.kicad_pcb")
    assert apply_overrides(gap, [SLOT]) == []
    assert [(a.layer, a.net, a.uuid) for a in gap.areas if a.source == "override"] == [("In1.Cu", "GND", "override-0")]
    assert plane(gap, "In1.Cu", "GND").symmetric_difference(plane(twin, "In1.Cu", "GND")).area < 1e-6


def test_an_added_via_cuts_an_antipad_in_other_net_fills_only():  # design 5.9; risk 12
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    assert apply_overrides(b, [via(110.0, -97.0)]) == []
    assert [(v.uuid, v.net) for v in b.vias if v.uuid.startswith("override")] == [("override-0", "GND")]
    r = 0.3 + CLEARANCE
    plus = plane(b, "In2.Cu", "+3V3")
    assert not plus.intersects(Point(110, -97).buffer(r - 1e-3)) and plus.covers(Point(110, -97 - r - 0.05))
    assert plane(b, "In1.Cu", "GND").covers(Point(110, -97).buffer(r))


def test_a_via_on_another_nets_copper_or_by_the_edge_is_left_out_with_a_w_line():  # design 5.9; risk 12
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    assert apply_overrides(b, [via(110.0, -100.275), via(110.0, -94.3)]) == [
        ("W_OVERRIDE_REFUSED", {"from": "R4-test", "x_mm": "110.000", "y_mm": "100.275", "reason": "T_OVERRIDE_COPPER"}),
        ("W_OVERRIDE_REFUSED", {"from": "R4-test", "x_mm": "110.000", "y_mm": "94.300", "reason": "T_OVERRIDE_EDGE"})]
    assert not any(v.uuid.startswith("override") for v in b.vias)


def test_load_applies_the_overrides_and_checks_them_again(tmp_path):  # design 5.9; Review Focus 3
    pj = emission_project(tmp_path / "e")  # coupon_gcpw_pads: LINE from (100, 100) to (120, 100)
    save_project(pj, {**load_project(pj), "overrides": [via(110.0, -100.0), via(110.0, -103.0)]})
    _, board, _, notes = pipeline.load(pj)
    assert ("W_OVERRIDE_REFUSED", {"from": "R4-test", "x_mm": "110.000", "y_mm": "100.000",
                                   "reason": "T_OVERRIDE_COPPER"}) in notes
    assert [v.uuid for v in board.vias if v.uuid.startswith("override")] == ["override-1"]
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_overrides.py -q`. Expected: FAIL, with `ModuleNotFoundError` on `core.geometry.overrides`.
- [ ] **Step 3: The code** of Interfaces, with W_OVERRIDE_REFUSED, T_OVERRIDE_COPPER and T_OVERRIDE_EDGE and their pt-BR.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py -q -rs`. Expected: PASS, nothing skipped, the `load` pins unchanged. A fixture fact that fails stops the task for a ruling with the measured geometry. Examples: a test point that misses the copper or the edge it names, or the twin's plane differing by more than the stated area. Never change an expected code or area to make it pass.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/geometry/overrides.py src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_overrides.py
git commit -m "feat(overrides): an emission project's fills and added vias applied at load before the geometry, antipads cut in other-net zone fills only, and every via checked again for clearance, one on other copper left out with a warning (Stage 5 design 5.9; risk 12)"
graphify update .
```

---

### Task 11 [code]: A variant from a finding: the review file, R1, R4 and the CLI

**Files:**
- Modify `core/geometry/overrides.py` and `cli.py` (`new_emission`'s `review`, `finding` and `pitch`).
- Messages.
- Tests: `tests/test_overrides.py`, `tests/test_cli_emission.py`.

**Interfaces.** Produces, in `core/geometry/overrides.py`:
- `read_review(path, finding) -> dict`: UTF-8 JSON of schema 1. Otherwise E_OVERRIDE_REVIEW {path, finding, reason}, with the read error's `reason()` or T_REVIEW_SCHEMA.
- `via_size(board, net) -> tuple[float, float, tuple[str, str]]`: the most common (diameter, drill, layers) of the net's vias, a tie going to the smaller diameter, and `(0.6, 0.3, (top, bottom))` with none.
- `make_overrides(board, review, finding, pitch, path) -> tuple[list[dict], list[tuple[str, dict]]]`, `path` the review file as given to `--review`:
  - **Refusals:** E_OVERRIDE_REVIEW {path, finding, reason}: T_REVIEW_OTHER_BOARD when `review["board"]["sha256"]` is not `board_hash(board.path)`, checked first, then T_REVIEW_NO_FINDING for an unknown id; E_OVERRIDE_NONE {finding, reason} when no entry results.
  - **The pitch** is `pitch or review["settings"]["l_mm"]`.
  - **The frame:** each point read from review.json is (x, −y). Each entry's `"from"` is the finding's id, and pitched vias (R3, R4) carry `"pitch_mm"`.
  - **The rules,** dispatched by the finding's rule (R2 and R3 are Task 12's):
    - **R1:** U is the union of the zone fills of (ref_layer, ref_net). The hole is the interior ring of U's polygons that contains the finding's at_mm, else T_OVERRIDE_NOT_A_VOID. The fill is that ring's polygon, less other-net copper on ref_layer grown by CLEARANCE, one entry per part.
    - **R4:** A and B are the vias of `kiids.vias` in that order; fewer than two gives T_OVERRIDE_NO_PAIR. n = ceil(gap/p) − 1, from `measured.gap_mm`; n ≤ 0 gives T_OVERRIDE_PITCH. The points are A + (B − A)·k/(n + 1), k = 1..n, each with A's diameter, drill, layers and net; one whose `blocker` is not None is left out with W_OVERRIDE_REFUSED; none kept gives T_OVERRIDE_NO_ROOM.
- `new_emission`: with `review`, `make_overrides(board, read_review(review, finding), finding, pitch, str(review))` runs before the write; its entries become `project["overrides"]`; its notes and I_OVERRIDES {fills, vias, finding} join the notes before W_ABSOLUTE_BOARD_PATH.

- [ ] **Step 1: The failing tests.** In `tests/test_overrides.py`:

```python
import json
import math

import pytest
from shapely.geometry import Polygon

from kicad_rf_studio import cli
from kicad_rf_studio.core.geometry.overrides import make_overrides
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import board_hash
from kicad_rf_studio.core.review import review_board
from kicad_rf_studio.core.review.outputs import review_json


def reviewed(name, edit=None, **kw):
    """The board `name` as cli._load reads it, edited in memory by `edit`, and its review.json as a dict."""
    path = FIX / f"{name}.kicad_pcb"
    board, stack, zs, classes = cli._load(path, None)
    if edit:
        edit(board)
    return board, json.loads(review_json(review_board(board, stack, zs, classes, **kw), str(path), board_hash(path)))


def first(review, rule, **match):
    return next(f for f in review["findings"] if f["rule"] == rule and all(f[k] == v for k, v in match.items()))


def test_r1s_fill_is_its_void_on_the_reference_layer(tmp_path):  # design 5.9; f3
    board, review = reviewed("usb2_hs_gap", nets=["USB_D*"])
    f = first(review, "R1")
    (fill,), notes = make_overrides(board, review, f["id"], None, str(tmp_path / "review.json"))
    assert (fill["kind"], fill["layer"], fill["net"], fill["from"], notes) == ("fill", "In1.Cu", "GND", f["id"], [])
    assert Polygon(fill["polygon_mm"]["exterior"]).area == pytest.approx(6.0)


def test_r4_densifies_a_gap_with_ceil_gap_over_p_minus_1_vias_like_its_first(tmp_path):  # design 5.9
    board, review = reviewed("emc_review", f_max=8e9)  # L 0.883 mm: SH1's 0.976 mm gaps fire
    path, f = str(tmp_path / "review.json"), first(review, "R4")
    a, b = (next(v for v in board.vias if v.uuid == u) for u in f["kiids"]["vias"])
    entries, _ = make_overrides(board, review, f["id"], 0.4, path)
    n = math.ceil(f["measured"]["gap_mm"] / 0.4) - 1
    assert len(entries) == n == 2
    for k, e in enumerate(entries, 1):
        assert e["at_mm"] == pytest.approx([a.at[q] + (b.at[q] - a.at[q]) * k / (n + 1) for q in (0, 1)])
        assert (e["diameter_mm"], e["drill_mm"], tuple(e["layers"]), e["net"], e["pitch_mm"]) == (
            a.diameter, a.drill, a.layers, a.net, 0.4)
    with pytest.raises(KrsError) as e:
        make_overrides(board, review, f["id"], 1.0, path)
    assert (e.value.code, e.value.params["reason"]) == ("E_OVERRIDE_NONE", "T_OVERRIDE_PITCH")


def test_a_review_of_another_board_or_without_the_finding_gives_no_variant(tmp_path):  # design 5.9
    board, review = reviewed("usb2_hs_gap", nets=["USB_D*"])
    path = str(tmp_path / "review.json")
    for data, reason in (({**review, "board": {**review["board"], "sha256": "0" * 64}}, "T_REVIEW_OTHER_BOARD"),
                         (review, "T_REVIEW_NO_FINDING")):
        with pytest.raises(KrsError) as e:
            make_overrides(board, data, "R9-00000000", None, path)
        assert (e.value.code, e.value.params["path"], e.value.params["reason"]) == ("E_OVERRIDE_REVIEW", path, reason)
```

  In `tests/test_cli_emission.py`:

```python
def test_new_emission_makes_a_variant_from_a_review_finding_and_a_pitch(tmp_path, capsys):  # design 5.9; 6
    import json, math
    from kicad_rf_studio.core.kicad import load_board
    from kicad_rf_studio.core.project import board_hash
    board = load_board(COUPON)
    a, b = sorted((v for v in board.vias if v.net == "GND" and abs(v.at[1] + 100.9) < 0.01), key=lambda v: v.at[0])[:2]
    review = {"schema": 1, "board": {"path": "coupon_gcpw_pads.kicad_pcb", "sha256": board_hash(COUPON)},
              "settings": {"l_mm": 1.413}, "findings": [{"id": "R4-test", "rule": "R4", "kiids": {
                  "vias": [a.uuid, b.uuid]}, "measured": {"gap_mm": round(math.dist(a.at, b.at), 3)}}]}
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    args = [*NEW, "--emission", "--f0", "915MHz", "--review", str(path), "--finding", "R4-test"]
    assert main([*args, "--pitch", "0.3", "-o", str(tmp_path / "v")]) == 0
    d = read_project(tmp_path / "v" / "project.json")
    assert [o["kind"] for o in d["overrides"]] == ["via"] * 3 and {o["from"] for o in d["overrides"]} == {"R4-test"}
    assert "R4-test" in capsys.readouterr().out  # I_OVERRIDES
    path.write_text(json.dumps({**review, "board": {**review["board"], "sha256": "0" * 64}}), encoding="utf-8")
    assert main([*args, "-o", str(tmp_path / "w")]) == 2 and not (tmp_path / "w").exists()
    err = capsys.readouterr().err
    assert render("T_REVIEW_OTHER_BOARD") in err and str(path) in err  # the review file, never the board
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_overrides.py tests/test_cli_emission.py -q`. Expected: FAIL, with `ImportError` on `make_overrides`.
- [ ] **Step 3: The code** of Interfaces, with Task 11's ten codes and their pt-BR.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_golden_review.py tests/test_sexpr.py -q`. Expected: PASS. A fixture fact that fails (an area, a count) stops the task for a ruling with the measured value.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/geometry/overrides.py src/kicad_rf_studio/cli.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_overrides.py tests/test_cli_emission.py
git commit -m "feat(overrides): a variant from one review finding and a pitch, hidden on new --emission: R1's same-net void filled and R4's gap densified as explicit geometry in the importer's frame, refused with the review file named where no in-app fix exists (Stage 5 design 5.9, 6)"
graphify update .
```

---

### Task 12 [code]: R2's return via and R3's edge fence

**Files:**
- Modify `core/geometry/overrides.py`.
- Messages.
- Tests: `tests/test_overrides.py`.

**Interfaces.** Produces, in `core/geometry/overrides.py`:
- `STEP_MM, ANGLE_DEG = 0.1, 15`: R2's search;
- `return_via(board, at, r_signal, d, size, net, planes) -> XY | None`: the first point at radius ρ = r_signal + size's radius + CLEARANCE, growing by STEP_MM while ρ ≤ d; at each ρ, the angles 0°, ANGLE_DEG, … < 360° from +x, counter-clockwise in the importer's frame. A point is kept when `blocker` is None and the zone fills of `net` on both `planes` layers cover the via's disc;
- in `make_overrides`:
  - **R2:** `params["from_net"] != params["to_net"]` is T_OVERRIDE_TWO_NETS. Else `plane = params["from_net"]`; the signal via is the finding's net's via at at_mm (1 µm); the entry is `return_via(board, at, r_signal, finding["limit"], via_size(board, plane), plane, (params["from_layer"], params["to_layer"]))`, a via of the plane's net, else T_OVERRIDE_NO_ROOM;
  - **R3:**
    - S is the finding's tracks' centre lines, merged, within limit + w/2 of the outline's boundary;
    - the points lie every pitch along S from its start;
    - each point Q moves toward its nearest boundary point B, to w/2 + (|QB| − w/2)/2 from Q: halfway across the gap between the track's copper and the edge (builder's choice, §6);
    - a via of `via_size(board, ref_net)` is kept when `blocker` is None and ref_net's fill on ref_layer covers its disc; otherwise W_OVERRIDE_REFUSED (T_OVERRIDE_OFF_PLANE for the plane);
    - no via kept gives T_OVERRIDE_NO_ROOM.

- [ ] **Step 1: The failing tests,** added to `tests/test_overrides.py` (with `from dataclasses import replace` and `from kicad_rf_studio.core.geometry.overrides import blocker`):

```python
def test_r2_between_two_nets_has_no_in_app_variant(tmp_path):  # design 5.9
    board, review = reviewed("qspi_clk", nets=["*CLK"])
    with pytest.raises(KrsError) as e:
        make_overrides(board, review, first(review, "R2")["id"], None, str(tmp_path / "review.json"))
    assert (e.value.code, e.value.params["reason"]) == ("E_OVERRIDE_NONE", "T_OVERRIDE_TWO_NETS")


def test_r2s_return_via_is_one_via_of_the_planes_net_within_d_on_both_planes(tmp_path):  # design 5.9
    def ground_in2(b):  # test_review_rules' same-net case: In2.Cu's +3V3 renamed GND
        b.areas = [replace(a, net="GND") if a.layer == "In2.Cu" else a for a in b.areas]

    board, review = reviewed("qspi_clk", ground_in2, nets=["*CLK"])
    f = first(review, "R2")
    assert (f["params"]["from_net"], f["params"]["to_net"]) == ("GND", "GND")
    (v,), notes = make_overrides(board, review, f["id"], None, str(tmp_path / "review.json"))
    signal = (f["at_mm"][0], -f["at_mm"][1])  # KiCad's frame to the importer's
    (x, y), r = v["at_mm"], v["diameter_mm"] / 2
    assert (v["kind"], v["net"], v["from"], notes) == ("via", "GND", f["id"], [])
    assert math.dist((x, y), signal) <= f["limit"] and blocker(board, (x, y), r, "GND", tuple(v["layers"])) is None
    assert all(plane(board, layer, "GND").covers(Point(x, y).buffer(r))
               for layer in (f["params"]["from_layer"], f["params"]["to_layer"]))


def test_r3s_fence_runs_between_the_track_and_the_edge_where_it_clears(tmp_path):  # design 5.9
    board, review = reviewed("usb2_hs", nets=["USB_D-"], edge_k=30.0)
    f = first(review, "R3", net="USB_D-")
    entries, _ = make_overrides(board, review, f["id"], 1.0, str(tmp_path / "review.json"))
    assert len(entries) >= 5 and {(e["kind"], e["net"], e["pitch_mm"]) for e in entries} == {("via", "GND", 1.0)}
    for e in entries:
        (x, y), r = e["at_mm"], e["diameter_mm"] / 2
        assert -99.725 < y < -94.0 and blocker(board, (x, y), r, "GND", tuple(e["layers"])) is None
        assert plane(board, f["ref_layer"], "GND").covers(Point(x, y).buffer(r))


def test_r3_with_no_room_by_the_edge_gives_no_variant(tmp_path):  # design 5.9: emc_review's CLK_EDGE, 0.35 mm in
    board, review = reviewed("emc_review")
    with pytest.raises(KrsError) as e:
        make_overrides(board, review, first(review, "R3")["id"], None, str(tmp_path / "review.json"))
    assert e.value.params["reason"] == "T_OVERRIDE_NO_ROOM"
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_overrides.py -q`. Expected: FAIL, the R2 and R3 cases unhandled.
- [ ] **Step 3: The code** of Interfaces, with T_OVERRIDE_TWO_NETS and T_OVERRIDE_OFF_PLANE and their pt-BR.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_golden_review.py tests/test_sexpr.py -q`. Expected: PASS. A fixture fact that fails (the y band, the via count) stops the task for a ruling with the measured value.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/geometry/overrides.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_overrides.py
git commit -m "feat(overrides): R2's return via of the planes' net, the first clear point within d on both planes, and R3's fence halfway between the track and the edge where it clears; a reference change between two nets has no in-app variant (Stage 5 design 5.9)"
graphify update .
```

---

### Task 13 [code]: Gate E-A's tool and its frozen criteria

**Files:**
- Create `tools/ea.py` and `tests/test_ea.py`.
- `tests/fixtures/ea/criteria.json` is written once by `--criteria`.
- Modify `tools/p3a.py`: `dipole` gains keywords whose defaults keep P3-A's spec byte for byte (the `p3a` pins).
- Modify `tools/p0.py`: `tools_id()` beside `code_id()`.

**Interfaces.**
- **`p0.tools_id() -> str`:** `git rev-parse HEAD:tools`, plus "+dirty" when a tracked file under tools differs from it, as `code_id` does for src.
- **`p3a.dipole(length_mm, *, f_hz=F_HZ, boundary="pml_8", box=None, gap_mm=GAP_MM, cmax_mm=CMAX_MM, excitation=None)`:** `excitation` stands in for `pulse(F1, F2, T_MAX)` when given.
- **`tools/ea.py`, the constants:**
  - `PRESET = "normal"`, `CASES = ("dipole", "loop")`; step ids `f"ea-{case}-a{attempt}"`;
  - `CRITERIA = p0.FIX / "ea" / "criteria.json"`;
  - `DIPOLE_F = [1e9 + 1e8 * k for k in range(16)]`: 1–2.5 GHz, past the antenna's cap of 11;
  - `LOOP_F = [5e8 + 1e8 * k for k in range(11)]` and `LOOP_JUDGED = [5e8, 1e9, 1.5e9]`;
  - `PASS = "<§5.12 E-A row's Pass column, verbatim>"`;
  - `EXPECTED_BLOCKS = {"dipole": [], "loop": ["E_PORT_SHORT"]}`: at DC a closed loop is one PEC piece, so the port gate's witnesses share a root (`pipeline.port_gates`); p0.run_model records it and runs on.
- **The specs:**
  - `dipole_spec()`: `p3a.dipole(p3a.SHORT_MM, f_hz=DIPOLE_F, gap_mm=air_gap(1e9), cmax_mm=air_cell(2.5e9), excitation=emission_pulse(1e9, 2.5e9))`;
  - `loop_spec()`: a hand-written spec: `"copper": "sheet"`, `"boundary": "pml_8"`, no materials; the excitation `emission_pulse(5e8, 1.5e9)`; the metal five sheet strips at z 0, the 0.1 mm strips centred on x, y = ±2.5, the bottom one split by the gap x ∈ [−0.05, 0.05]; port P1 lumped, dir x, start [−0.05, −2.55, 0.0], stop [0.05, −2.45, 0.0], nodes [[−0.05, −2.55, 0], [0.05, −2.55, 0], [−0.15, −2.55, 0], [0.15, −2.55, 0]]; the mesh x and y `round(-2.65 + 0.1·k, 6)` for k in range(54), z [−0.1, 0.0, 0.1], each graded at 1.3 to `air_cell(1.5e9)` out to `air_gap(5e8)` past the loop, then `with_pml`; `"nf2ff": {"f_hz": LOOP_F, "center": [0, 0, 0]}`;
  - `loop_area_mm2(spec) -> float`: the area inside the strips' centre lines, as the mesh-snapped strips give them.
- **`criteria() -> dict`:**
  - `{"gate": "E-A", "source": PASS, "eta_ohm": η0 (scipy.constants), "r_m": 3.0, "expected_blocks": EXPECTED_BLOCKS, ...}`;
  - `"dipole"`: `length_mm` 12.0, `f_hz` DIPOLE_F, `e_r_per_a` [η0·tan(kL/4)/(2π)], `e_tol_db` 0.5, `identity_tol_db` 0.05, `eta_rad` 1.0, `eta_tol` 0.02, `p_acc_min` 1e-3, `eta_judged_expected` 0 (the critics' estimate: P_acc/P_inc 6e-6 to 3e-4 on a 12 mm wire; open issue 2);
  - `"loop"`: `side_mm` 5.0, `area_mm2` (loop_area_mm2), `constant` 1.3169e-14, `f_hz` LOOP_JUDGED, `e_per_ma` [1.3169e-14·f²·A/3·1e-3], `e_tol_db` 0.5;
  - `"incomplete"`: "a case with no record, a verdict not in KEPT, a criteria frequency missing from its far field (a relative 1e-6), or a blocking setup gate other than expected_blocks': handled as a fail (Task 14)".
- **`predict(spec, mcs) -> dict`:** `"cells"`; `"pml"`: cells − Π(len − 2·(PML_CELLS + 1)), as p3a counts; `"dt"`: 1/(c·√Σ1/Δmin²), as ee.predict has it; `"to_t_max_s"`: (cells + (PML_WEIGHT − 1)·pml)·(t_max/dt)/(mcs·small_speed(1)·1e6), `mcs` being `pipeline.prepare(p0.model_of(spec), print, small=True)`'s: cost's emission basis (AR-14).
- **`_case(spec, sid) -> dict`**, a step's work: `run = p0.run_model(p0.model_of(spec), PRESET, sid, [1])`; for a kept job with waves: the rings from `tail_fit`, the sphere from `read_far_field(pipeline.far_field(job)["sphere"])` snapped to the spec's list, and `emission_rows(..., resistive=False, f0=None)`. It returns the run plus `"verdict"`, `"t_stop"`, `"rings"`, and `"f_hz"`, `"e_ma"`, `"e_3m"`, `"p_acc"`, `"p_inc"`, `"p_rad"` and `"d_max"` as lists aligned in f, empty without a far field; `"blocked"` holds the setup gate's codes.
- **`measure(out, attempt) -> dict`:** `{case: the step's result or None}` from the step records that exist (`p0.records` over those ids).
- **`decide(m, crit) -> dict`** → `{"verdict": "pass" | "fail" | "incomplete", "fails": [...], "eta_judged": count, "dipole": [...], "loop": [...]}`:
  - "incomplete" as `crit["incomplete"]` says;
  - the dipole, at each `f_hz`: `e_err_db` = 20·log10(e_ma·1e3·r_m/e_r_per_a); `identity_db` = 20·log10(e_3m·r_m/√(η0·d_max·p_rad/(2π))); `acc_ratio` = p_acc/p_inc; η = p_rad/p_acc, `eta_judged` where acc_ratio ≥ p_acc_min;
  - the loop, at each judged f: `e_err_db` = 20·log10(e_ma/e_per_ma);
  - the fails, in this order: "dipole_e", "dipole_identity", "dipole_eta", "loop_e".
- **`tables(result) -> str`:** EA-1 the dipole's rows, with P_acc/P_inc and whether η was judged at each frequency; EA-2 the loop's; EA-3 the runs (verdict, t_stop, rings, blocked, cells, dt, wall_s, predicted_s, MC/s).
- **`write(out, attempt) -> dict`:** `<out>/ea/ea-a<N>.json` through `p0.save`, with the keys `gate`, `versions`, `tools` (`p0.tools_id()`), `criteria` {"file": "tests/fixtures/ea/criteria.json", "sha256"}, `runs`, `decision` (decided against `json.loads(CRITERIA.read_text())`, never `criteria()`), `calibration` (no host key) and `machine`; `ea-a<N>.md` beside it.
- **`main(argv) -> int`:**
  - `--criteria` writes CRITERIA once through `p0.save`, and raises `SystemExit("… never regenerated …")` when it exists;
  - otherwise it calls `p0.enter` first;
  - `--out DIR --cost`: for each case, `predict` and its setup gate alone (`p0.run_model(p0.model_of(spec), PRESET, f"ea-{case}-setup", [])`, no time steps), printed as the last line, JSON `{case: {**predict, "blocked": codes}}`; returns 1 when a case's blocked codes hold one outside EXPECTED_BLOCKS;
  - `--out DIR [--attempt N]` (default 1): each case through `p0.step(out, f"ea-{case}-a{N}", f"{spec_hash(spec)}+{p0.tools_id()}", partial(_case, spec, sid))`, a step that raises printed and skipped; then `write` from the steps that exist; returns 1 when a step raised.

- [ ] **Step 1: The failing tests,** in `tests/test_ea.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import numpy as np
import pytest
from scipy.constants import physical_constants

import ea
import p0
from kicad_rf_studio.core.geometry.region import air_gap
from kicad_rf_studio.core.model.csx import EMISSION_NF2FF_MAX, NF2FF_MAX, PML_CELLS
from kicad_rf_studio.core.model.spec import emission_pulse


def test_the_dipole_is_p3as_12_mm_wire_with_the_emission_pulse_a_quarter_wave_of_1_ghz_off():  # 5.12 E-A (1)
    s = ea.dipole_spec()
    assert s["excitation"] == emission_pulse(1e9, 2.5e9) and s["excitation"]["t_max"] == 41e-9
    assert s["boundary"] == "pml_8" and [c["z"] for c in s["metal"]["curves"]] == [[0.5, 6.0], [-6.0, -0.5]]
    assert NF2FF_MAX < len(s["nf2ff"]["f_hz"]) <= EMISSION_NF2FF_MAX  # the emission cap runs
    assert s["mesh"]["z"][PML_CELLS] <= -6.0 - air_gap(1e9) and s["mesh"]["z"][-1 - PML_CELLS] >= 6.0 + air_gap(1e9)


def test_the_loop_is_four_one_cell_strips_and_a_one_cell_gap_port_on_the_mesh():  # 5.12 E-A (2)
    s = ea.loop_spec()
    assert s["copper"] == "sheet" and s["excitation"]["t_max"] == 69e-9 and s["excitation"]["emission"]
    assert len(s["metal"]["copper"]) == 5 and all(c["z"] == [0.0, 0.0] for c in s["metal"]["copper"])
    (p,) = s["ports"]
    assert (p["dir"], p["start"], p["stop"]) == ("x", [-0.05, -2.55, 0.0], [0.05, -2.45, 0.0])
    lines = {a: set(s["mesh"][a]) for a in "xyz"}
    assert all(n[0] in lines["x"] and n[1] in lines["y"] and n[2] in lines["z"] for n in p["nodes"])
    assert np.diff(sorted(v for v in lines["x"] if abs(v) <= 2.65)).max() <= 0.1 + 1e-9
    assert ea.loop_area_mm2(s) == pytest.approx(25.0)


def test_the_committed_criteria_are_the_design_s_closed_forms_and_never_regenerated():  # 5.12: frozen first
    crit = json.loads(ea.CRITERIA.read_text(encoding="utf-8"))
    assert crit == ea.criteria()
    eta, k = physical_constants["characteristic impedance of vacuum"][0], 2 * math.pi * 2.5e9 / 299792458
    assert crit["dipole"]["e_r_per_a"][-1] == pytest.approx(eta * math.tan(k * 0.012 / 4) / (2 * math.pi))
    assert crit["loop"]["e_per_ma"][1] == pytest.approx(1.3169e-14 * 1e18 * 25e-6 / 3 * 1e-3)  # 1.097e-4 (r3)
    assert crit["expected_blocks"] == {"dipole": [], "loop": ["E_PORT_SHORT"]}  # a closed loop is one PEC piece
    assert crit["dipole"]["eta_judged_expected"] == 0
    with pytest.raises(SystemExit, match="never regenerated"):
        ea.main(["--criteria"])


def measured(crit, de=0.0, di=0.0, eta=1.0, ratio=1e-2, dl=0.0, verdict="converged", blocked=((), ())):
    d, lo, r = crit["dipole"], crit["loop"], crit["r_m"]
    p_rad, d_max = np.full(len(d["f_hz"]), 1e-3), np.full(len(d["f_hz"]), 1.5)
    e_3m = np.sqrt(crit["eta_ohm"] * d_max * p_rad / (2 * np.pi)) / r * 10 ** (di / 20)
    dipole = {"verdict": verdict, "blocked": list(blocked[0]), "f_hz": d["f_hz"], "e_3m": e_3m.tolist(),
              "d_max": d_max.tolist(), "e_ma": (np.array(d["e_r_per_a"]) * 10 ** (de / 20) / (1e3 * r)).tolist(),
              "p_rad": p_rad.tolist(), "p_acc": (p_rad / eta).tolist(), "p_inc": (p_rad / eta / ratio).tolist()}
    loop = {"verdict": "converged", "blocked": list(blocked[1]), "f_hz": lo["f_hz"],
            "e_ma": (np.array(lo["e_per_ma"]) * 10 ** (dl / 20)).tolist()}
    return {"dipole": dipole, "loop": loop}


def test_e_a_passes_inside_its_tolerances_and_names_each_miss():  # design 5.12 E-A's Pass column
    crit = ea.criteria()
    d = ea.decide(measured(crit, de=0.45, di=0.04, eta=1.019, dl=-0.45), crit)
    assert (d["verdict"], d["eta_judged"]) == ("pass", len(crit["dipole"]["f_hz"]))
    for kw, fail in (({"de": 0.55}, "dipole_e"), ({"di": 0.06}, "dipole_identity"), ({"eta": 1.03}, "dipole_eta"),
                     ({"dl": -0.55}, "loop_e")):
        assert (lambda d: (d["verdict"], d["fails"]))(ea.decide(measured(crit, **kw), crit)) == ("fail", [fail])
    d = ea.decide(measured(crit, eta=1.5, ratio=1e-4), crit)
    assert (d["verdict"], d["eta_judged"]) == ("pass", 0)  # η judged only at P_acc/P_inc ≥ 1e-3, and the count says so


def test_a_case_not_kept_missing_or_blocked_by_an_unexpected_gate_is_incomplete():  # Task 14's third branch
    crit = ea.criteria()
    assert ea.decide(measured(crit, blocked=((), ("E_PORT_SHORT",))), crit)["verdict"] == "pass"  # pre-registered
    for m in (measured(crit, verdict="diverged"), measured(crit, blocked=((), ("E_PORT_OPEN",))),
              measured(crit, blocked=(("E_PORT_SHORT",), ())), {**measured(crit), "loop": None}):
        assert ea.decide(m, crit)["verdict"] == "incomplete"


def test_the_e_a_steps_run_through_the_harness_with_the_fake_worker(p0_out, monkeypatch, capsys):  # ruling 10
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    assert ea.main(["--out", str(p0_out), "--cost"]) == 0
    cost = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert set(cost) == {"dipole", "loop"}
    assert all({"cells", "pml", "dt", "to_t_max_s", "blocked"} <= set(c) for c in cost.values())
    assert ea.main(["--out", str(p0_out)]) == 0
    result = json.loads((p0_out / "ea" / "ea-a1.json").read_text(encoding="utf-8"))
    assert set(result) == {"gate", "versions", "tools", "criteria", "runs", "decision", "calibration", "machine"}
    assert result["criteria"]["file"] == "tests/fixtures/ea/criteria.json"
    assert result["decision"]["verdict"] in ("pass", "fail", "incomplete")  # the fake's far field is P3-A's 58 mm
    step = json.loads((p0_out / "steps" / "ea-dipole-a1.json").read_text(encoding="utf-8"))
    assert f"+{p0.tools_id()}@" in step["key"]  # a tools change runs the step again
    assert (p0_out / "ea" / "ea-a1.md").read_text(encoding="utf-8").startswith("## EA-1")
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_ea.py -q`. Expected: FAIL, with `ModuleNotFoundError: No module named 'ea'`.
- [ ] **Step 3: `tools/ea.py`, `p3a.dipole`'s keywords and `p0.tools_id`,** as Interfaces gives them. `ea.py`'s docstring reads: "Gate E-A, the emission closed forms (Stage 5 design 5.12), the controller's: P3-A's 12 mm dipole and a 5 × 5 mm loop as hand-written specs carrying the emission excitation key, through p0, judged by §5.8's post code against tests/fixtures/ea/criteria.json, frozen before the run. Run: python tools/ea.py --criteria | --out DIR [--cost] [--attempt N]."
- [ ] **Step 4: The criteria, once,** after open issue 2's ruling. Run `.venv/Scripts/python tools/ea.py --criteria`: seconds, in memory, no openEMS.
- [ ] **Step 5: Run them.** Run Step 2's command, then `tests/test_p3a.py tests/test_p0.py tests/test_model_spec.py tests/test_golden_v1.py -q -rs`. Expected: PASS, nothing skipped, the `p3a` pins unchanged.
- [ ] **Step 6: Both suites, commit, graph.**

```bash
git add tools/ea.py tools/p3a.py tools/p0.py tests/test_ea.py tests/fixtures/ea/criteria.json
git commit -m "feat(tools): ea.py, gate E-A: P3-A's 12 mm dipole and a 5 x 5 mm loop with the emission pulse, the cap of 64 and the post code run unchanged, judged per mA against the closed forms and the NF2FF identity frozen in criteria.json before the run, its setup gate checked first and its steps keyed by the tools tree (Stage 5 design 5.12)"
graphify update .
```

---

### Task 14 [run]: E-A (the controller's)

`<EMC_GATES>` is plan 2's gates folder, `$HOME\krs-gates-emc`, reused with its calibration. Each call starts with:

```powershell
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"; $g = Join-Path $HOME "krs-gates-emc"  # <EMC_GATES>
$env:LOCALAPPDATA = "$g\data"; $env:XDG_DATA_HOME = "$g\data"; $env:LANGUAGE = "en"; $env:PYTHONUTF8 = "1"
New-Item -ItemType Directory -Force "$g\logs" | Out-Null
```

**The rules:**
- One openEMS process at a time, and no pytest meanwhile.
- Each call runs in the background and is waited on.
- The machine time is the tool's own figure (`to_t_max_s`), which already weights the PML; no factor applies. Before a run predicted past 1 h, tell the owner in pt-BR (the memory reaper).
- At least 8 GB of RAM free for a run predicted under 2 h. Past 2 h, 14 GB, after a pt-BR warning.
- The criteria are Task 13's commit: `git log --format="%h %s" -1 -- tests/fixtures/ea/criteria.json` names it. They are never regenerated or edited after the run.
- **The attempt:** a run whose step stored no record and whose run folder holds no verdict event (killed by the memory reaper, a reboot) is not the attempt: the ledger and the record name the interruption and its cause, and a restart follows the standing rule for killed background runs, the owner asked first. A run that wrote its verdict event is the attempt.

- [ ] **Step 0: A whole-branch review before the run.** Request a review of `main..HEAD` (Tasks 1 to 13) against this plan and the design's plan 3 row (superpowers:requesting-code-review). Each fix is test-first, in its own commit, after both suites. Nothing E-A runs changes after this step but by Step 3's bug rule.
- [ ] **Step 1: The prediction and the setup check.** Run `& .venv\Scripts\python.exe -X utf8 tools\ea.py --out $g --cost *> "$g\logs\ea-cost.log"`, and record both cases' figures and blocked lists in the ledger. Expected: exit 0, the loop's blocked list E_PORT_SHORT or empty, the dipole's empty. Exit 1 (another gate blocks) stops before Step 2 for a ruling: a fix to a spec, and any change of criteria.json it brings, happens only now, by a ruled deletion and Task 13's `--criteria`, in its own commit, before E-A's run.
- [ ] **Step 2: The run.** Run `& .venv\Scripts\python.exe -X utf8 tools\ea.py --out $g *> "$g\logs\ea.log"`, and record the start, the end and the exit in `$g\logs\ledger.txt`. Expected: exit 0, with `$g\ea\ea-a1.json` and `ea-a1.md` written.
- [ ] **Step 3: The record.** Write `docs/validation/<date>-e-a.md`, with `<date>-e-a.json` a byte copy of `ea-a1.json`. Its sections:
  1. the verdict, as the tool decided it;
  2. the inputs: the commands, with `<EMC_GATES>` and `<openEMS folder>`; the versions and the tools id; each spec's hash and mesh; the criteria file, its sha256 and the commit that froze it;
  3. EA-1 and EA-2, verbatim, with the number of frequencies η was judged at (pre-registered 0);
  4. the runs, with the machine time predicted against measured;
  5. the outcome:
     - **pass:** go on to Task 15;
     - **fail or incomplete:** run superpowers:systematic-debugging on the record. A defect that a new test reproduces, in the pipeline (normalisation, radius, peak or RMS) or in ea.py's specs and code, is fixed in its owning task's file in its own `fix:` commit after both suites, and E-A runs once more with `--attempt 2`. That record is `<date>-e-a-rerun.md` and `.json`, and both records are kept. With no defect reproduced, the controller records part B's no-go: Tasks 15 to 17 are skipped, and Task 18's no-go branch names this record.

  The record holds no path and no host name. It is committed before any rerun. Then run:

  ```bash
  git add docs/validation/<date>-e-a.md docs/validation/<date>-e-a.json
  git commit -m "docs(validation): gate E-A, the dipole's E per mA against the feed-referenced form, the NF2FF identity and eta, and the loop's E per mA at 3 m, against the criteria frozen before the run (Stage 5 design 5.12; controller recommendation, owner unavailable)"
  graphify update .
  ```

---

### Task 15 [code]: The probe's fixtures (only after E-A passes)

**Files:**
- Modify `tools/make_fixtures.py`: `emc_probe` after `emc_review`, and three BOARDS entries. The `"emc_"` prefix already gives them four layers.
- Modify `tests/test_fixtures.py` (NAMES) and `tests/test_pads.py` (`test_pads_match_pcbnew`'s list, and one test).
- Create `tests/test_probe.py`.
- Written by the tool: `tests/fixtures/emc_probe.kicad_pcb`, `emc_probe_null.kicad_pcb` and `emc_probe_pp.kicad_pcb`, each with its `.pads.json`.

**Interfaces.** Produces the boards, in KiCad's frame (mm, y down):
- 50 × 50 mm at (100, 100)–(150, 150) on STACKUP_4L, 1 oz copper on every layer;
- U1.1, the source, then C2 (3.3 pF, shunt), L1 (15 nH, series) and C3 (3.3 pF, shunt), then J1.1, J1 being the edge SMA on the bottom edge;
- SH1, lpf915's 20 × 20 mm frame at (115, 115), whose right-side gap the line leaves by at y 121.25 (AR-13; §6 leaves the footprints to the builder);
- RF_B's straight segment from L1 to (131, 121.25), at least 5 mm of it outside the frame, then an arc of radius 4 mm to (135, 125.25), then a straight run to J1;
- In1.Cu, In2.Cu and B.Cu GND (In2.Cu +3V3 on `emc_probe_pp`).

The generator, as given:

```python
def emc_probe(b, null=False, pp=False):
    """The go/no-go probe's board (Stage 5 design 5.13): 50 x 50 mm on STACKUP_4L, In1.Cu, In2.Cu and B.Cu GND drawn to
    the outline (KiCad's 0.5 mm edge clearance stops the fills 0.5 mm in), F.Cu bare but the chain along y 121.25: U1,
    lpf915's QFN "RFIC", its pin 1 the source; C2 and C3, 3.3 pF shunts, and L1, 15 nH, lpf915's values; RF_B through
    SH1's right-side gap, straight to x 131, an arc of radius 4 mm down to (135, 125.25), and down to J1, lpf915's edge
    SMA turned onto the bottom edge. GND vias under U1's pad and beside C2's and C3's, on SH1's pad line every 1.025 mm
    but where RF_B leaves, 2 mm either side of RF_B every 2 mm, and a 3 mm stitching grid. `null`: the straight segment
    before the arc as two collinear tracks meeting at x 128 (N_on); `pp`: In2.Cu +3V3, and C1, 100 nF, to GND (P_pp)."""
    y, box = 121.25, (100, 100, 150, 150)
    rect(b, pcbnew.Edge_Cuts, *box)
    for layer in (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        square(b, layer, "+3V3" if pp and layer == pcbnew.In2_Cu else "GND", *box)
    u1 = place(b, QFN, "U1", "RFIC", (108, y - 0.75), 180, {"1": "RF_A", "2": "GND", "4": "GND", "17": "GND"})
    c2 = place(b, C0402, "C2", "3.3pF", (113, y + 0.48), 270, {"1": "RF_A", "2": "GND"})
    l1 = place(b, "Inductor_SMD:L_0402_1005Metric", "L1", "15nH", (114.5, y), 0, {"1": "RF_A", "2": "RF_B"})
    c3 = place(b, C0402, "C3", "3.3pF", (116, y + 0.48), 270, {"1": "RF_B", "2": "GND"})
    j1 = place(b, "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount", "J1", "SMA", (135, 147.46), 270,
               {"1": "RF_B", "2": "GND"})
    place(b, "RF_Shielding:Wuerth_36103205_20x20mm", "SH1", "SHIELD", (115, 115), 0, {"1": "GND"})
    track(b, "RF_A", 0.25, pad_at(u1, "1"), (110.3, y))
    track(b, "RF_A", 0.6, (110.3, y), pad_at(l1, "1"))
    track(b, "RF_B", 0.6, pad_at(l1, "2"), *([(128, y)] if null else []), (131, y))
    s = math.sqrt(0.5)
    arc(b, "RF_B", 0.6, (131, y), (131 + 4 * s, y + 4 - 4 * s), (135, y + 4))
    track(b, "RF_B", 0.6, (135, y + 4), pad_at(j1, "1"))
    track(b, "GND", 0.25, pad_at(u1, "2"), (108.6, y - 0.5))  # pin 2 into the exposed pad, as lpf915's
    for dx in (-0.45, 0.45):
        for dy in (-1.2, -0.3):
            via(b, (108 + dx, y + dy))
    to_gnd(b, pad_at(c2, "2"))
    to_gnd(b, pad_at(c3, "2"))
    lo, hi, n = 104.75, 125.25, 20  # SH1's pads' centre line
    frame = [p for k in range(n) for p in ((lo + 20.5 * k / n, lo), (hi, lo + 20.5 * k / n),
                                           (hi - 20.5 * k / n, hi), (lo, hi - 20.5 * k / n))
             if not (p[0] == hi and abs(p[1] - y) < 1.5)]
    for p in frame:
        via(b, p)
    rf = [("line", (110.3, y), (131, y)), ("arc", (131, y + 4), 4, -90, 0), ("line", (135, y + 4), (135, 147))]
    grid = [(102.5 + 3 * i, 102.5 + 3 * j) for i in range(16) for j in range(16)]
    fence(b, [p for p in (*fence_points(rf, 2.0, pitch=2.0), *grid) if all(math.dist(p, q) >= 0.8 for q in frame)],
          box, keep=0.5)
    if pp:
        decoupled(b, (143, 107))  # after the vias, so the boards share every via but C1's two
```

  BOARDS gains `"emc_probe": emc_probe`, `"emc_probe_null": lambda b: emc_probe(b, null=True)` and `"emc_probe_pp": lambda b: emc_probe(b, pp=True)`.

- [ ] **Step 1: The failing tests.** `tests/test_fixtures.py`'s NAMES and `test_pads_match_pcbnew`'s list gain the three names. Add to `tests/test_pads.py` (importing `math`, `shapely`, and `classify` and `trace_chain` from `kicad_rf_studio.core.kicad`):

```python
def test_the_emc_probe_fixtures():  # Stage 5 design 5.13, 5.14: the probe's base, null twin and plane pair
    base, null, pp = (load_board(FIX / f"{n}.kicad_pcb") for n in ("emc_probe", "emc_probe_null", "emc_probe_pp"))
    for b in (base, null, pp):
        assert b.copper_layers == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu") and b.outline.bounds == (100.0, -150.0, 150.0, -100.0)
        assert {x.thickness for x in b.stackup.layers if x.kind == "copper"} == {0.035}  # 1 oz everywhere
        c = classify(b)
        assert (c.shields, c.connectors) == ({"SH1"}, {"J1"})
        chain = trace_chain(b, "U1.1", "J1.1", c)
        assert ([p.ref for p in chain.series], sorted(p.ref for p in chain.shunt)) == (["L1"], ["C2", "C3"])
    zones = lambda b: sorted({(a.layer, a.net) for a in b.areas if a.source == "zone"})  # noqa: E731
    assert zones(base) == zones(null) == [("B.Cu", "GND"), ("In1.Cu", "GND"), ("In2.Cu", "GND")]
    assert zones(pp) == [("B.Cu", "GND"), ("In1.Cu", "GND"), ("In2.Cu", "+3V3")]
    rf = [t for t in base.tracks if t.net == "RF_B"]
    (arc,) = [t for t in rf if t.mid is not None]
    assert round(math.dist(arc.start, (131, -125.25)), 3) == 4.0  # an arc of radius 4 mm, at least 3
    (beside,) = [t for t in rf if t.mid is None and t.end == arc.start]
    assert beside.start[1] == beside.end[1] and beside.end[0] - beside.start[0] >= 5
    rf_null = [t for t in null.tracks if t.net == "RF_B"]
    assert len(rf_null) == len(rf) + 1  # the straight segment as two collinear pieces
    union = lambda ts: shapely.union_all([t.polygon() for t in ts])  # noqa: E731
    assert union(rf_null).symmetric_difference(union(rf)).area < 1e-9
    assert {v.at for v in null.vias} == {v.at for v in base.vias} and len(base.vias) >= 150
    added = {(v.at, v.net) for v in pp.vias} - {(v.at, v.net) for v in base.vias}
    assert len(added) == 2 and {net for _, net in added} == {"+3V3", "GND"}
```

  In `tests/test_probe.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from kicad_rf_studio import cli, pipeline, runs
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.project import load_project
from test_cli_new import FIX


def test_the_null_twin_moves_the_mesh_and_hash_but_not_the_fingerprint(tmp_path, monkeypatch):  # 5.13; BC5
    monkeypatch.setattr(runs, "openems_versions", lambda: ("0.37.0", "0.7.0"))
    made = {name: cli.new_emission(FIX / f"{name}.kicad_pcb", "U1.1", "J1.1", f0=915e6, f_max=3e9, lid_height=2.5,
                                   output=tmp_path / name)[0] for name in ("emc_probe", "emc_probe_null", "emc_probe_pp")}
    specs = []
    for name in ("emc_probe", "emc_probe_null"):  # the two models the guard compares
        project, board, geom, notes = pipeline.load(made[name])
        model = pipeline.build_model(project, board, geom)
        assert not model.blocked and not pipeline.stops(notes) and project["t_max_s"] == 31e-9
        specs.append(model.spec)
    a, b = specs
    assert spec_hash(a) != spec_hash(b) and a["mesh"] != b["mesh"]  # not a null at all otherwise (P4-E's R-4)
    fp = [pipeline.fingerprint(load_project(pj)) for pj in made.values()]
    assert fp[0] == fp[1] == fp[2]
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_fixtures.py tests/test_pads.py tests/test_probe.py -q -k "probe"`. Expected: FAIL, with KrsError E_BOARD_UNREADABLE on `emc_probe.kicad_pcb`.
- [ ] **Step 3: The generator,** as given.
- [ ] **Step 4: Generate only the three, under A-3's isolation,** in one PowerShell call, then compare every other board with git:

```powershell
$kp = Join-Path (Get-Location) 'build\kicad-profile'; New-Item -ItemType Directory -Force $kp | Out-Null
Get-ChildItem env: | Where-Object { $_.Name -like 'KICAD*' } | ForEach-Object { Remove-Item "env:$($_.Name)" }
if (Test-Path env:TMPDIR) { Remove-Item env:TMPDIR }
$env:APPDATA = $kp; $env:LOCALAPPDATA = $kp  # the script itself points KICAD_*_HOME, TEMP and TMP at $kp
& "<KiCad 9 bin folder>\python.exe" tools/make_fixtures.py tests/fixtures emc_probe emc_probe_null emc_probe_pp
"exit $LASTEXITCODE"; git status --short tests/fixtures
.venv/Scripts/python -c "import hashlib, pathlib, subprocess; run = lambda *a: subprocess.run(a, capture_output=True, check=True).stdout; files = run('git', 'ls-files', 'tests/fixtures/*.kicad_pcb', 'tests/fixtures/*.pads.json').decode().split(); bad = [f for f in files if hashlib.sha256(pathlib.Path(f).read_bytes().replace(b'\r\n', b'\n')).digest() != hashlib.sha256(run('git', 'show', 'HEAD:' + f)).digest()]; print(len(files), 'tracked boards and pad files,', len(bad), 'changed', bad)"
```

  Expected:
  - `exit 0`;
  - `git status` lists exactly the six new files;
  - the last line reads `92 tracked boards and pad files, 0 changed []`.

  Never start KiCad itself or kicad-cli. Then:
  - If another file changed, stop: the golden pins hash those boards.
  - If a fact of Step 1 fails on the real fills, report the measured value for a ruling and leave the design's numbers unmoved. Examples: a fill gap, a via the fence dropped near J1, or J1's pad off the line.
  - If the guard finds N_on's hash or mesh equal to P_on's, move the split along the same segment, trying x 129.3, 127.7 and 130.1 in that order. Regenerate `emc_probe_null` alone and report which split held (§5.13: "a split that leaves the hash equal moves to another point of that straight segment").
- [ ] **Step 5: Run them again.** Run Step 2's command, then `tests/test_board.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_golden_review.py tests/test_repo.py -q -rs`. Expected: PASS, nothing skipped, with `test_board.py`'s sweep reading the three boards with no warning.
- [ ] **Step 6: Both suites, commit, graph.**

```bash
git add tools/make_fixtures.py tests/test_fixtures.py tests/test_pads.py tests/test_probe.py tests/fixtures/emc_probe.* tests/fixtures/emc_probe_null.* tests/fixtures/emc_probe_pp.*
git commit -m "test(fixtures): the go/no-go probe's boards, a 50 x 50 mm four-layer LoRa-like front end with a pi filter, a shield frame and an arc bend, its collinear-split null twin and its GND/+3V3 plane-pair variant, the null's hash and mesh apart from the base's and its fingerprint equal (Stage 5 design 5.13, 5.14; BC5)"
graphify update .
```

---

### Task 16 [code]: The probe's tool and its frozen criteria

**Files:**
- Create `tools/probe.py`.
- `tests/fixtures/probe/criteria.json` is written once by `--criteria`.
- Tests: `tests/test_probe.py`.

**Interfaces.**
- **The constants:** `CRITERIA = p0.FIX / "probe" / "criteria.json"`, `RUNS = ("P_off", "P_on", "N_on", "P_pp")`, `RAM_POLL_S = 5.0`; step ids `f"probe-{name}-a{attempt}"`.
- **`criteria() -> dict`**, the frozen content:
  - `"probe"`: "Stage 5 design 5.13", and `"source"`: §5.13's three Go criteria and its incomplete rules, verbatim;
  - `"runs"`: `{"P_off": {"board": "emc_probe", "lid": false}, "P_on": {"board": "emc_probe", "lid": true}, "N_on": {"board": "emc_probe_null", "lid": true}, "P_pp": {"board": "emc_probe_pp", "lid": true}}`;
  - `"start"`: "U1.1", `"end"`: "J1.1", `"f0_hz"`: 915e6, `"f_lo_hz"`: 1.83e9, `"f_max_hz"`: 3e9, `"lid_height_mm"`: 2.5, `"preset"`: "normal";
  - `"harmonics_hz"`: [1.83e9, 2.745e9], `"t_max_s"`: 31e-9, `"budget_s"`: 7200, `"margin_db"`: 20.0, `"eps_limit"`: 0.02, `"floor_step_db"`: 0.05;
  - `"statistic"`: the n(f), floor and L_off definitions, in §5.13's words;
  - `"report"`: the report-only figures (AR-20): each judged row's P_acc/P_inc and its residual on the P_acc basis, and per run the count of judged rows with P_acc/P_inc > eps_limit (only those can fail B8's criterion), and the runs whose closure is judged at no frequency, with their rings;
  - `"incomplete"`: §5.13's list, plus: "a run whose driven job diverges or grows, whose mesh or setup gates block it (exit 3), or whose jobs are not kept (exit 4): criterion 1 for that run; a run whose transform fails or that records no far field: criteria 2 and 3 for that run; an exit 2 is recorded with its E_ codes and judged on its verdict and wall time";
  - `"attempt"`: "one; a rerun only for a pipeline bug a new test reproduces on the first record, both records kept; a run killed before its driven job's verdict event is not the attempt".
- **`load_criteria() -> dict`:** reads CRITERIA.
- **`dirty() -> str`:** `git status --porcelain --untracked-files=no -- src tools tests/fixtures`.
- **`project_of(out, name, crit, attempt) -> Path`:** makes `<out>/probe/a<N>/<name>/project.json` once, with `cli.new_emission` on the board copied LF to `<out>/probe/a<N>/boards/`, as golden_v1 copies; P_off's has `lid` false; SystemExit when `t_max_s` is not `crit["t_max_s"]` ("never raised").
- **`guard(out, crit, attempt) -> dict`:** `{"spec_hash": {run: hash}, "mesh_differs", "hash_differs", "fingerprints_equal"}` from the four projects, built in memory as Task 15's test builds them.
- **`freeze(out, crit, attempt) -> dict`:** SystemExit when `dirty()` is not empty or the guard fails; else writes `<out>/probe/freeze-a<N>.json`: `{"commit", "code" (p0.code_id), "tools" (p0.tools_id), "fixtures": {board: sha256 of its LF bytes}, "criteria": sha256 of CRITERIA's bytes, "guard"}`.
- **`check(out, crit, attempt)`:** SystemExit naming the freeze unless `code_id`, `tools_id`, the boards' sha256 and the criteria's sha256 all equal `freeze-a<N>.json`'s. `--cost`, `--run` and `--record` call it first.
- **`cost(out, name, crit, attempt) -> dict`:** `{"cells", "split", "dt", "mcs", "to_t_max_s"}`: the model, `prepare(..., small=True, jobs=1)`, `setup_gate`'s dt, and `cost_seconds` to T_max.
- **`run(out, name, crit, attempt) -> dict`**, the step's work: `pipeline.run(project_of(...))`, with a thread sampling `runs.free_ram_mb()` every RAM_POLL_S. The record holds:
  - `"exit"`, `"run_dir"` (the folder's name, never a path), `"codes"` (the run's E_ message codes);
  - `"verdict"`, `"t_cut"`, `"t_stop"`, `"rings"`;
  - `"wall_s"` (the driven job's, results' job-phase wall time), `"total_s"`;
  - `"setup_s"` and `"transform_s"`: each job folder's latest file time less its job.json's;
  - `"cells"`, `"split"` (cell_split of model.json), `"dt"`, `"steps"`;
  - `"measured_mcs"` (the driven job's openEMS_stats speed) and `"calibrated_mcs"` (prepare's, small, pool 1);
  - `"ratio"`: measured_mcs·weighted/cells over calibrated_mcs, against SMALL_SPEED[1], for plan 4's refit;
  - `"predicted_s"` and `"predicted_t_max_s"` (`cost_seconds` to t_stop and to T_max);
  - `"ram_drop_gb"`: the start's free RAM less the least sampled, with `# ponytail: a proxy, other processes count; a peak-RSS probe if plan 4's refit needs it`;
  - `"dumps_bytes"`, of `worker.DUMPS` in the driven job;
  - `"rows"`: `emission_of`'s, made plain; `"far_field"`: whether the run recorded one;
  - `"mesh_sha"`: of model.json's mesh;
  - `"harmonics_truncated"`.

  A run whose exit is not 0 records what it has.
- **`null(out, crit, attempt) -> dict | None`:** None when N_on's or P_on's record holds no far field; else `{"f_hz": the harmonics, "n": null_floor's at them (None where a sphere lacks one), "mesh_equal"}`, from their sphere files, snapped, and their waves (`incident`).
- **`decide(runs: dict[str, dict | None], nl: dict | None, crit) -> dict`** → `{"verdict": "go" | "no-go", "failed": [...], "1": {run: {...}}, "2": {harmonic MHz: {...}}, "3": {run: {...}}}`, each entry with `"result"` "pass", "fail" or "incomplete":
  1. per run: incomplete when missing, or its exit is 3 or 4, or its verdict is not "converged" or "t_max"; fail when `wall_s` > budget_s; else pass. An exit 2 is judged on its verdict and wall time.
  2. per harmonic: incomplete when `nl` is None, n is None or 0, `mesh_equal`, or P_off is missing or holds no row there; else L_off = 20·log10(e_v on P_off), floor = `floor_db(n)`, fail when L_off − floor < margin_db; L_on − floor reported.
  3. per run: incomplete when missing or holding no rows; fail when a judged row has |eps| > eps_limit; reported: the judged count, the worst |eps| and its f, the rows not judged by reason, `"can_fail"` (judged rows with P_acc/P_inc > eps_limit), the worst `eps_acc`, `"none_judged"` (the run's rings when no row is judged, else None), and P_pp's truncated harmonics.

  "go" when every entry of the three passes; `"failed"` lists, in order, the criteria ("1", "2", "3") with an entry that did not.
- **`tables(result) -> str`:** PR-1 to PR-3 for the criteria, PR-4 the report-only figures, then the run measures.
- **`write(out, crit, attempt) -> dict`:** `<out>/probe/probe-a<N>.json` and `.md` from the step records that exist (`p0.records` over those ids still refuses two codes), a missing run passed to decide as None; SystemExit unless every record's key holds the freeze's tools id and code id.
- **`main(argv) -> int`:** `--criteria` (once, "never regenerated"), or `--out DIR [--attempt N]` (default 1) with one of `--freeze`, `--cost NAME`, `--run NAME` (through `p0.step`, keyed `f"{spec_hash}+{p0.tools_id()}"`) and `--record`.

- [ ] **Step 1: The failing tests,** added to `tests/test_probe.py`:

```python
import json

import pytest

import p0
import probe


def test_the_probe_criteria_are_design_5_13s_committed_once():  # design 5.13: pre-registration
    crit = json.loads(probe.CRITERIA.read_text(encoding="utf-8"))
    assert crit == probe.criteria() and list(crit["runs"]) == list(probe.RUNS)
    assert (crit["harmonics_hz"], crit["t_max_s"], crit["budget_s"], crit["margin_db"], crit["eps_limit"]) == (
        [1.83e9, 2.745e9], 31e-9, 7200, 20.0, 0.02)
    assert {"statistic", "report", "incomplete", "attempt"} <= set(crit)
    with pytest.raises(SystemExit, match="never regenerated"):
        probe.main(["--criteria"])


def rec(wall=3600.0, verdict="t_max", eps=0.001, e_v=(1e-3, 1e-3), closure="judged", exit=0, far=True):
    rows = [{"f_hz": f, "harmonic": n, "e_v": e, "eps": eps, "eps_acc": eps, "p_acc": 1e-3, "p_inc": 1.0,
             "closure": closure} for f, n, e in zip((1.83e9, 2.745e9), (2, 3), e_v)] if far else []
    return {"exit": exit, "verdict": verdict, "wall_s": wall, "rows": rows, "far_field": far, "rings": [],
            "harmonics_truncated": []}


NULL = {"f_hz": [1.83e9, 2.745e9], "n": [1e-6, 1e-6], "mesh_equal": False}  # floor −110.45 dB


def test_go_needs_each_run_in_budget_a_20_db_floor_margin_and_closure():  # design 5.13's three criteria
    crit, runs = probe.criteria(), {name: rec() for name in probe.RUNS}
    assert probe.decide(runs, NULL, crit)["verdict"] == "go"
    assert probe.decide({**runs, "P_off": rec(e_v=(1e-3, 3.1e-5))}, NULL, crit)["verdict"] == "go"  # 20.28 dB
    cases = (({"P_pp": rec(wall=7201.0)}, NULL, ["1"]), ({"P_on": rec(verdict="diverged", exit=4)}, NULL, ["1"]),
             ({"P_off": rec(e_v=(1e-3, 3e-5))}, NULL, ["2"]),  # 19.99 dB over the floor at 2.745 GHz
             ({}, {**NULL, "n": [0.0, 1e-6]}, ["2"]), ({}, {**NULL, "mesh_equal": True}, ["2"]),
             ({"N_on": rec(eps=0.021)}, NULL, ["3"]), ({"P_off": None}, NULL, ["1", "2", "3"]),
             ({"P_on": rec(exit=2, far=False)}, None, ["2", "3"]))  # its transform failed: no far field, no null
    for change, nl, failed in cases:
        d = probe.decide({**runs, **change}, nl, crit)
        assert (d["verdict"], d["failed"]) == ("no-go", failed)
    truncated = {**rec(eps=0.5, closure="truncated"), "harmonics_truncated": [2.745e9]}
    d = probe.decide({**runs, "P_pp": truncated}, NULL, crit)
    assert d["verdict"] == "go" and d["3"]["P_pp"]["none_judged"] is not None  # B10; a vacuous criterion 3 shows


def test_the_probe_runs_one_board_a_call_and_records_what_exists_against_its_freeze(p0_out, monkeypatch):  # 11
    crit = {**probe.criteria(), "start": "TP1.1", "end": "TP2.1",
            "runs": {name: {"board": "coupon_gcpw_pads", "lid": name != "P_off"} for name in probe.RUNS}}
    monkeypatch.setattr(probe, "load_criteria", lambda: crit)
    monkeypatch.setattr(probe, "guard", lambda *a: {"hash_differs": True, "mesh_differs": True,
                                                     "fingerprints_equal": True, "spec_hash": {}})
    monkeypatch.setattr(probe, "dirty", lambda: "")  # a test runs on an edited tree
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    out = str(p0_out)
    assert probe.main(["--out", out, "--freeze"]) == 0
    for name in probe.RUNS[:2]:
        assert probe.main(["--out", out, "--cost", name]) == 0 and probe.main(["--out", out, "--run", name]) == 0
    assert probe.main(["--out", out, "--record"]) == 0  # a first record from the runs that exist
    first = json.loads((p0_out / "probe" / "probe-a1.json").read_text(encoding="utf-8"))
    assert first["decision"]["verdict"] == "no-go"
    assert {r for r, x in first["decision"]["1"].items() if x["result"] == "incomplete"} == {"N_on", "P_pp"}
    for name in probe.RUNS[2:]:
        assert probe.main(["--out", out, "--run", name]) == 0
    assert probe.main(["--out", out, "--record"]) == 0
    result = json.loads((p0_out / "probe" / "probe-a1.json").read_text(encoding="utf-8"))
    assert set(result["runs"]) == set(probe.RUNS) and result["decision"]["verdict"] in ("go", "no-go")
    assert all("/" not in r["run_dir"] and "\\" not in r["run_dir"] for r in result["runs"].values())
    monkeypatch.setattr(p0, "tools_id", lambda: "another tools tree")
    with pytest.raises(SystemExit, match="freeze"):
        probe.main(["--out", out, "--record"])  # a record never mixes code or tools with the freeze's
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_probe.py -q`. Expected: FAIL, with `ModuleNotFoundError: No module named 'probe'`.
- [ ] **Step 3: `tools/probe.py`,** as Interfaces gives it. Its docstring reads: "The go/no-go probe (Stage 5 design 5.13), the controller's: four runs of the emission kind, one a call, judged against tests/fixtures/probe/criteria.json, frozen with the boards, the product and the tools before the first run. Run: python tools/probe.py --criteria | --out DIR [--attempt N] (--freeze | --cost NAME | --run NAME | --record)."
- [ ] **Step 4: The criteria, once,** after open issue 3's ruling. Run `.venv/Scripts/python tools/probe.py --criteria`.
- [ ] **Step 5: Run them.** Use Step 2's command. Expected: PASS.
- [ ] **Step 6: Both suites, commit, graph.**

```bash
git add tools/probe.py tests/test_probe.py tests/fixtures/probe/criteria.json
git commit -m "feat(tools): probe.py, the go/no-go probe: its criteria frozen as JSON, its four projects and in-memory guard, a freeze of the boards, the product and the tools that every run and record checks, one run a call through the product with its machine record, and the three criteria's decision from whatever runs exist (Stage 5 design 5.13)"
graphify update .
```

---

### Task 17 [run]: The probe (the controller's)

The calls start as Task 14's do, and the same rules apply: one openEMS process at a time and no pytest meanwhile; the tool's own prediction against the 1 h warning and the RAM floors, with no factor; the attempt as Task 14 defines it. **Each run is its own call, alone at pool 1.**

- [ ] **Step 0: A whole-branch review before the freeze.** Request a review of the commits since Task 14 (Tasks 15 and 16, and any Step 0 fixes) against this plan and the design's plan 3 row. Each fix is test-first, in its own commit, after both suites.
- [ ] **Step 1: The freeze.**
  - Run `& .venv\Scripts\python.exe -X utf8 tools\probe.py --out $g --freeze *> "$g\logs\probe-freeze.log"`. Expected: exit 0 and `$g\probe\freeze-a1.json`.
  - Copy it byte for byte to `docs/validation/<date>-probe-freeze.json`, then run:

  ```bash
  git add docs/validation/<date>-probe-freeze.json
  git commit -m "docs(validation): the probe's freeze before its first run: the four boards' bytes, their spec hashes, the criteria file, the product tree and the tools tree under test (Stage 5 design 5.13; controller recommendation, owner unavailable)"
  ```

  From here on, no fixture, band, preset, T_max, criterion, product code or tool changes, except for a pipeline or tool bug that a new test reproduces on the first record.
- [ ] **Step 2: The four runs, in order: P_off, P_on, N_on, P_pp.** For each NAME:
  1. Run `--cost NAME` into `$g\logs\probe-NAME-cost.log`, and record the prediction.
  2. Check the RAM as the rules say. Tell the owner in pt-BR when the prediction passes 1 h.
  3. Run `& .venv\Scripts\python.exe -X utf8 tools\probe.py --out $g --run NAME *> "$g\logs\probe-NAME.log"`, and record the start, the end and the exit in the ledger.
  4. A failure gets superpowers:systematic-debugging, never a blind rerun:
     - first run `--record` and commit that first record as `<date>-probe.md` and `.json`, marked incomplete, with the runs that exist;
     - a pipeline or tool bug is reproduced by a new test and fixed in its own `fix:` commit after both suites; the probe then runs again with `--attempt 2` under a new freeze (`<date>-probe-rerun-freeze.json`), and its record is `<date>-probe-rerun.md` and `.json`; both records are kept;
     - a change that is not such a bug is a new probe, which can never overturn a recorded no-go inside Stage 5.
- [ ] **Step 3: The record.**
  - Run `--record` into `$g\logs\probe-record.log`.
  - Write `docs/validation/<date>-probe.md`, with `<date>-probe.json` a byte copy of `probe-a1.json`. Its sections:
    1. the verdict, go or no-go, and the criteria that failed;
    2. the inputs: the freeze's commit, code and tools ids, the fixtures' sha256, the spec hashes, the criteria sha256, the commands and the versions;
    3. criterion 1 per run: the verdict and its time, the driven job's wall time, the setup and the transform apart, every (f_r, Q, factor);
    4. criterion 2 per harmonic: L_off, n, the floor, the margin, and L_on − floor beside it;
    5. criterion 3 per run: the frequencies judged, the worst |ε|, the rest by reason; how many judged frequencies could have failed (P_acc/P_inc > 0.02) and the worst residual on the P_acc basis; each run whose closure is judged at no frequency, with the rings that caused it; P_pp's truncated harmonics, stated as §5.13 asks;
    6. what §5.13 lists for each run: the cells and their split, dt and the steps, MC/s and the measured ratio for the speed refit, peak RAM (the proxy), the dumps' bytes, the setup's and the transform's times, and cost's prediction against the measured run. The FD accumulation's share is not measured apart: it lies inside the measured speed ratio. The per-frequency rows are in the JSON;
    7. on a go, what plans 4 and 5 take from it; on a no-go, Task 18's branch.
  - The record holds no path and no host name. Then run:

  ```bash
  git add docs/validation/<date>-probe.md docs/validation/<date>-probe.json
  git commit -m "docs(validation): the go/no-go probe, four runs of the emission kind against its frozen criteria: each driven job's time to the stop branch, the floor from the collinear-split null and energy closure where the rings allow (Stage 5 design 5.13; controller recommendation, owner unavailable)"
  graphify update .
  ```

---

### Task 18 [code on a no-go]: The outcome

The controller picks the branch from the record of Task 14 (E-A) or Task 17 (the probe).

- **On a go:** no code.
  - The kind stays hidden: `--emission` stays off the usage line, E_NEW_KIND keeps its text, the window keeps G_KIND_LATER, and the GUI has no emission kind. Plan 5 releases it.
  - The controller copies into this plan's rulings file what plans 4 and 5 take from the probe's record: the measured speed ratio and the PML share, for plan 4's refit; the floor at both harmonics; P_pp's (f_r, Q) against f1's 232–1789; the peak RAM and the dumps' bytes; the transform's time.

**On a no-go** (E-A's or the probe's):

**Files:**
- Modify `core/project.py` (`EMISSION_UNVALIDATED`), `cli.py` and `pipeline.py`.
- Messages.
- Tests: `tests/test_cli_emission.py`.

**Interfaces:**
- `EMISSION_UNVALIDATED = "docs/validation/<date>-<e-a|probe>.md"`, the failing record's repo path;
- `new_emission` adds W_EMISSION_UNVALIDATED {record} before I_WROTE;
- `pipeline.load` adds it after W_BOARD_CHANGED for every `emission(project)`.

- [ ] **Step 1: The failing test:**

```python
def test_an_unvalidated_kind_says_so_at_new_and_at_every_load(tmp_path):  # design 5.13: the no-go branch
    from kicad_rf_studio import pipeline
    from kicad_rf_studio.core.project import EMISSION_UNVALIDATED
    from test_cli_new import run_new
    pj, notes = cli.new_emission(COUPON, "TP1.1", "TP2.1", f0=915e6, output=tmp_path / "e")
    line = ("W_EMISSION_UNVALIDATED", {"record": EMISSION_UNVALIDATED})
    assert line in notes and line in pipeline.load(pj)[3]
    _, v1 = run_new(tmp_path)
    assert line not in pipeline.load(v1)[3]
```

- [ ] **Step 2: Run it.** Command: `.venv/Scripts/python -m pytest tests/test_cli_emission.py -q -k unvalidated`. Expected: FAIL, with `ImportError`.
- [ ] **Step 3: The code,** with W_EMISSION_UNVALIDATED and its pt-BR.
- [ ] **Step 4: Run it,** then `tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_sexpr.py -q -rs`. Expected: PASS, nothing skipped, the `load` pins unchanged.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/project.py src/kicad_rf_studio/cli.py src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_cli_emission.py
git commit -m "feat(emission): part B's no-go, a warning at new --emission and at every load of a schema-4 project naming the record that failed, the kind kept hidden and unreleased (Stage 5 design 5.13; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 19 [doc]: Amendments A-78 to A-83

- [ ] **Step 1: The Stage 1 spec.** Tag each paragraph "(A-n, Stage 5 plan 3: unreleased until the probe's go; controller recommendation, owner unavailable.)". On a go, each tag adds "The probe's go: docs/validation/<date>-probe.md; plan 5 releases the kind." On a no-go, each adds "Dormant: <the failing record>."
  - **A-78, §5.1, §5.3 and §5.8:** the emission model: the whole board in air, PML_8, λ/4 at f_lo, λ/20 at f_max, solid copper, a lossless dielectric; the emission pulse, f1 = f_lo/1.3 rounded down and f2 = f_max, and its `"emission"` key; a termination's R; the near-field plane, over-sampled 4 times; the three jobs, model.json and driven.json.
  - **A-79, §6.3 and §6.4:** the emission stop branch: no flat, T_max = 2·t0 + 60/f_c rounded up to a whole ns, the tail fit with its per-port Hann peak search, its envelopes fitted jointly in back-to-back 2 ns windows, its merge, a truncation width of 50·f_r/Q, and q None for an envelope that does not decay; its cost lines: the antenna's weight and speed, the setup run and one driven job predicted, W_EMISSION_LONG_RUN.
  - **A-80, §7 (emission results):** the NF2FF list capped at 64; the 3 m field per V of U_inc and per mA; closure, its judged conditions and the closure-backed label; emission.csv and emission_rings.csv, and the lines; I_LIMIT_EMISSION; n(f) and its floor; the fingerprint; E_EMISSION_ONE_RUN and E_EMISSION_PART.
  - **A-81, §7.8:** schema 4, its fields and checks, written by `new BOARD --start --end --emission (--f0 F [--f-max F] | --band F_LO:F_HI)` with the variant options `--review PATH --finding ID [--pitch MM]`, all hidden from the usage line until the go, and E_EMISSION_BAND; the overrides: entries, frame, 0.2 mm clearance, applied at load, the re-check and the W_ refusal; `overrides` refused outside schema 4; the window's G_KIND_LATER; the review's f_max order gains a schema-4 project (its carrier at step 2, else its band's f_max, at most 6 GHz, as "emission").
  - **A-82, a new §9.12 entry, "E-A: emission closed forms (Stage 5)":** the two cases; the loop's pre-registered E_PORT_SHORT; the criteria frozen in `tests/fixtures/ea/criteria.json`; the results from Task 14's record(s), with the count of frequencies η was judged at.
  - **A-83, a new §9.13, "The go/no-go probe (Stage 5)":**
    - after E-A's pass: the boards, the four runs, the criteria frozen in `tests/fixtures/probe/criteria.json`, the freeze, and the result from Task 17's record(s);
    - after E-A's no-go: the probe as §5.13 fixes it, "not built and not run: E-A's no-go (docs/validation/<date>-e-a.md) closed part B", naming no fixture, criteria file or freeze.
  - **The Status line** gains: "On `<date>`, Stage 5's plan 3 amended §5.1, §5.3, §5.8, §6.3, §6.4, §7, §7.8, §9.12 and §9.13 (A-78 to A-83) the same way, each unreleased until the probe's go."
- [ ] **Step 2: Test, commit, graph.** `.venv/Scripts/python -m pytest tests/test_repo.py -q` passes. This task is docs only, so the previous task's suites stand. Then run:

```bash
git add docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs(spec): A-78 to A-83, the hidden emission kind, its model, stop branch, results, schema 4 and overrides, gate E-A and the go/no-go probe with their results, each unreleased until the probe's go (Stage 5 plan 3; controller recommendation, owner unavailable)"
graphify update .
```

---

## The close (the controller's)

1. **The tip.** Run the full suite and the GUI tests in pt-BR, each alone in the background, and record their counts.
2. **The release check,** in the background: `.venv\Scripts\python.exe tools/release_check.py *> "$env:TEMP\krs-s5p3-release.log"`. Expected: exit 0 and eight PASS lines (build, install, gui, antenna, si, review, plugin, privacy). A FAIL is fixed test-first in its own commit, after both suites.
3. **A whole-branch review** against this plan and the design's plan 3 row; Tasks 1 to 16 were reviewed before E-A's run and the probe's freeze, so this one weighs Tasks 18 and 19 and every fix since. A fix commit re-runs step 1. A fix that touches code E-A or the probe ran follows the bug rule: a new test that reproduces it, the one rerun, and both records kept.
4. **The merge.** Fast-forward merge into `main` locally, then delete the branch. Nothing is pushed.
5. **The rulings file:** `.superpowers/sdd/<date>-stage5-plan3-rulings-and-minors.md`.
6. **After the close:**
   - **On a no-go,** the controller writes the Stage 5 exit record. It names the gate that failed and lists A-78 to A-83 as dormant.
   - **On a go,** plan 4 is written next.
   - `<EMC_GATES>` stays. Its settings.json and steps folder are never opened.

## Not in this plan

- **Plan 4's:** compare's third kind and its thresholds, I_COMPARE_OVERRIDES, gates E-B to E-D, the cost refit (the probe records the ratio), and a lossy-default revisit.
- **Plan 5's:**
  - the GUI's emission kind (G_KIND_LATER's refusal removed), Advanced's emission defaults, Results' figure and Compare;
  - "simulate this" switched to the emission pair;
  - the README's emission tutorial, the release check's emission step, the acceptance and §10's amendment.
- **Deferred by the design:** Prony extrapolation, a stitching-capacitor override, a board-edge fence by default and overrides on the SI kind.
- **`waves.layout`'s band grid for emission** (AR-3), and W_AIR_BOX's and W_LIDS_LEFT_OUT's antenna texts, which stay as they are.

## Controller rulings (binding; as applied)

1. **Scope:** the plan 3 row only, Tasks 1 to 19. Three additions keep the row's own work safe: G_KIND_LATER (a hidden-kind file never reads as E_INTERNAL in the window), E_EMISSION_PART (an emission run's own refusal before any job), and `p0.tools_id` (the freeze holds the gate tools too).
2. **Pins:** Task 1, through a new `tools/golden_s5.py` and `golden_s5.json` (AR-2). The three golden tools and JSONs stay untouched, the three test files are extended, and test_repo's list gains the file.
3. **The model:** as given; `model.json` is `model_spec`'s spec, and the driven job and the transform read `driven.json` (AR-4).
4. **The band, T_max and the stop branch:** §5.7, with the envelope estimator read under §6's window latitude (AR-5), and risk 2's tests first, f1's plane pair among them.
5. **The far field, normalisation and closure:** §5.8. **Changed:** the word scan allows two released phrases, I_REVIEW_RELATIVE's "predicts a pass or a fail" and T_FMAX_DEFAULT's "FCC 15.33(b)(1)", which design §5.1 step 4 itself fixes (AR-1, open issue 1). Report-only figures join the probe's record without moving B8's criterion (AR-20).
6. **The overrides:** §5.9, with a 0.2 mm clearance and the CLI spelled `new … --emission … --review PATH --finding ID [--pitch MM]`, hidden.
7. **The fingerprint and n(f):** §5.10, in Task 7.
8. **Cost:** §5.11, in Task 9, with AR-18's reading of "counts jobs 1 and 2"; no refit; no factor on any prediction.
9. **Hidden:** a separate parser reads the hidden options (AR-16), E_NEW_KIND is unchanged, and the window refuses the kind naming none (AR-17).
10. **E-A:** Tasks 13 and 14. Its setup gate is checked before the run; an incomplete result is handled as a fail (AR-14).
11. **The probe:** Tasks 15 to 17, with the freeze holding the tools tree, numbered attempts, and criterion 1 read from the driven job (AR-19, AR-20).
12. **The close:** Task 18, both branches; Task 19, A-78 to A-83, with the CLI inside §7.8's amendment, so the list is ruling 12's exactly.
13. **Never a real KiCad.**
14. **Tests:** as given per task, with `-rs` and no golden skip on this PC.
15. **Execution:** subagent-driven, 19 tasks, with whole-branch reviews before E-A's run and before the probe's freeze as well as at the close.

## Architect's rulings (controller recommendations, owner unavailable)

- **AR-1, the word scan:** an explicit set (plans 1 and 2's 56 codes, frozen in the test, plus every code named like this plan's), whole words with "margins", "passes" and "passed", and two exact released phrases allowed, each asserted present in its code. The label "not a compliance verdict" holds none of the six words, so it needs no allowance.
- **AR-2, the pins:** `tools/golden_s5.py` builds each kind's cases in its own folder and records `golden_s5.json` once. The fake run is unwatched (`run_jobs` with no watch), so each fake job writes its whole trace and the run is deterministic; the run pins are env-gated, as the outputs pins are.
- **AR-3, `waves.layout`'s band grid** stays antenna-only. The window refuses the kind before `pipeline.load` (AR-17), and retune, verify and compare refuse it, so layout never sees one. This narrows §5.6's list.
- **AR-4, `driven.json`:** the setup reads `model.json`, the driven job and the transform read `driven.json`; `run_ports` and `far_field` carry the spec file, with job.json's bytes unchanged by default and pinned.
- **AR-5, the tail fit:** a Hann peak search per port within 20 dB of that port's largest; each port's peaks fitted jointly by least squares in back-to-back 2 ns windows (a lone DFT at f_r leaks a neighbour 0.6 GHz off into the envelope: +63 % and +179 % on two modes in the critics' probe, against within 4 % jointly); a peak fitted only at the ports where it stands within 20 dB, its factor the worst over them (BC6); merge within 2/span. A non-decaying envelope gets q None, factor 1.0 and truncates every frequency: it has no finite Q, so 50·f/Q gives no width, and its cut leaks across the band.
- **AR-6, one spec marker:** the excitation's `"emission": true`. A port's `"R"` and `"near_field"` are the other emission-only keys, written only under `emission(project)`.
- **AR-7, an `"R"`** is a termination's only; on the driven port it is refused (T_EXPECT_DRIVEN_R), since U_inc assumes a 50 Ω source.
- **AR-8, the NF2FF list** keeps the lowest harmonics first when the cap of 64 binds; a grid point within 1 MHz of a harmonic is left out.
- **AR-9, `near_field`** is a flag; on, it records the harmonics (at most 11) over the outline's bounds, 1.5 mm above the highest metal, over-sampled 4 times; it needs f0.
- **AR-10, the review's source** for a carrier-free emission project is `"emission"`, shown through T_FMAX_EMISSION.
- **AR-11, W_EMISSION_AIR_BOX and W_EMISSION_LIDS_LEFT_OUT** are twins of the antenna's warnings, whose texts name the antenna.
- **AR-12, retune and verify refuse** the kind (E_EMISSION_ONE_RUN); the ring list goes to `emission_rings.csv`; E_EMISSION_PART refuses a part the grid cannot hold before any job.
- **AR-13, the probe board:** SH1 is lpf915's 20 × 20 mm frame, its own right-side gap the opening (the design's "about 20 × 15" is r3's estimate; §6 leaves footprints to the builder); the RF fence 2 mm off the line every 2 mm; a 3 mm grid; C1 where no grid via moves.
- **AR-14, E-A:** the dipole is `p3a.dipole` with the gap at λ/4 of 1 GHz and 16 frequencies; the loop is sheet strips centred on ±2.5 mm, A 25.0 mm², a flat lumped port across a one-cell gap, its E_PORT_SHORT pre-registered; predictions on cost's emission basis; a blocking gate other than that one, a case not kept or a frequency missing is incomplete, handled as a fail; a setup block found by `--cost` stops before the run, where a ruled fix and re-freeze are still allowed.
- **AR-15, the probe's peak RAM** is the drop in free RAM over the run, a proxy.
- **AR-16, the hidden options** are read by `_HIDDEN` (`allow_abbrev=False`) before the main parser, so `--e` stays `--end` and no error message names a hidden flag.
- **AR-17, G_KIND_LATER:** the window refuses a schema-4 file before `pipeline.load`, as Stage 4's G_SI_LATER did, its text naming no kind.
- **AR-18, cost:** "counts jobs 1 and 2" reads as: cost runs the setup job, as for every kind, and predicts the one driven job; the transform is recorded by the probe, not predicted.
- **AR-19, the gate tools' identity:** every step keyed by the spec and the tools tree; the probe's freeze refuses a dirty tree and its runs and records refuse a changed product, tools tree, board or criteria file; attempts numbered; records written from the steps that exist and committed before any rerun.
- **AR-20, the probe's reading:** criterion 1 from the driven job's verdict and wall time (exits 3 and 4 incomplete, an exit 2 recorded); no far field leaves criteria 2 and 3 incomplete for that run; report-only P_acc/P_inc, the P_acc-basis residual, the rows that could fail, and the runs judged at no frequency.
- **AR-21, E_EMISSION_BAND** also refuses a band that holds no far-field frequency.
- **AR-22, Task 11 is split** (R1 and R4 with the CLI; R2 and R3 apart), so a reviewer can reject one geometry without the other.

## Open issues, ruled by the controller (2026-11-16; owner unavailable)

Each ruling is a controller recommendation made before Task 1.

1. **AR-1, the word scan.** The question: allow the two released phrases in the scan, or reword both lines so that the design's single allowed match holds literally. The phrases are I_REVIEW_RELATIVE's "predicts a pass or a fail" and T_FMAX_DEFAULT's "FCC 15.33(b)(1)", which §5.1 step 4 fixes. Rewording would touch EN, PT and their README quotes.
   - **Ruling: allow both, as Task 2 writes it.**
   - The first phrase is a disclaimer that denies a verdict. The second is the f_max default's source, which the design itself fixes. Neither is a result, and both lines are released.
   - Each allowance is exact and asserted present in its own code, so any other occurrence still fails.
   - Rewording would move released English and pt-BR text and two README quotes, and the user would gain nothing.
2. **E-A's η check.** §5.12's P_acc/P_inc ≥ 1e-3 judges none of the 16 dipole frequencies: the estimate is 6e-6 to 3e-4 on a 12 mm wire. So η passes vacuously.
   - **Ruling: keep 1e-3 verbatim**, with `eta_judged_expected` 0 pre-registered and the count stated in the record.
   - 1e-3 is the conditioning P3-A taught. Below it, P_acc is a small difference of large DFT terms, and a spurious η miss would close part B on a numerical artefact.
   - E-A still checks the 3 m scaling, the per-mA normalisation and the NF2FF identity.
   - The record names the vacuous η check as an owner item. A case that conditions η belongs to a later gate.
3. **The probe's criterion 3.** On B8's P_inc basis, a judged frequency can fail only where P_acc/P_inc > 0.02. Behind the π filter, that holds at the lowest frequencies only.
   - **Ruling: keep B8's criterion (the default).**
   - The P_acc-basis residual and the count of judged rows that could fail stay report-only, registered before the freeze. The record shows how much criterion 3 could decide.
   - The basis is an owner item.
4. **AR-5, q None for a non-decaying envelope** (every frequency truncated), against the design's |slope|. **Ruling: accepted.**
   - A non-decaying envelope has no finite Q.
   - The design's |slope| would read a growing envelope as a decaying Q, and its truncation width 50·f_r/Q would vanish.
   - Truncating every frequency is the conservative reading. The probe's record lists each run judged at no frequency, with its rings, so a vacuous criterion 3 shows.
5. **AR-5, the joint least-squares envelope and the per-port 20 dB fit.** **Ruling: accepted** as the builder's latitude under §6 (the window's shape within §5.7's 2 ns windows).
   - A one-frequency least-squares fit over a rectangular window is the short-time DFT itself. The joint fit removes the neighbour's leakage: +63 % and +179 % with lone DFTs, against within 4 %.
   - BC6's worst factor over the ports is taken over the ports where the peak stands within 20 dB.
6. **AR-3 and AR-17: G_KIND_LATER,** and §5.6's list narrowed so that waves' band grid stays antenna-only. **Ruling: accepted.**
   - G_KIND_LATER keeps the kind hidden, naming none, and keeps a CLI-made emission project from reading as E_INTERNAL in the window, as Stage 4's G_SI_LATER did.
   - One driven job holds no N-port, and every path to `layout` refuses the kind first.
7. **AR-14: E-A's incomplete result handled as a fail.** **Ruling: accepted.**
   - §5.12 ends E-A in a pass, or, when no pipeline bug is reproduced, in a no-go.
   - A reproduced defect in the pipeline or in ea.py gets the one rerun. A run killed before its verdict event is not the attempt (Task 14's rules).
   - A setup block is caught by `--cost` before the run, while a ruled fix is still allowed.
8. **AR-18: cost's reading of "counts jobs 1 and 2".** Cost runs the setup job, as for every kind, and predicts the one driven job. The probe records the transform apart. **Ruling: accepted.**
9. **AR-2: the run pins are env-gated,** bound to this PC as the existing outputs pins are. **Ruling: accepted.** A recording on another env is a ruling.

**The controller's own review** (writing-plans' self-review, 2026-11-16):
- **Coverage.** Every item of the design's plan 3 row (§5.6 to §5.13, §5.14's probe boards, §5.16's plan 3 amendments) maps to a task. Every blocking and important finding of the five critics is applied, or ruled above.
- **Names and numbers checked at `a87bcc1`:**
  - `p3a.specs`, `STEPS` and `SHORT_MM`;
  - `fake_cli.patches`; `test_model_csx.Rec`, `fake_openems` and `TINY`;
  - the golden tools' `record`, `env`, `CASES`, `BANDS` and `_board`;
  - `p0.load_trace`, `code_id`, `step`, `records` and `run_model`;
  - 8 traces and 3 presets;
  - 56 message codes added by plans 1 and 2, and both allowed phrases verbatim;
  - 92 tracked boards and pad files;
  - `open_project`'s try block, which turns G_KIND_LATER into `problem`.
- **Two stop rules made explicit:**
  - Task 5: today's flat window;
  - Task 10: a fixture fact.
- **Proportion.** The plan runs longer than plan 2's: 19 tasks, two gate tools, the tail fit and a fixture generator. Its long blocks are tests that carry the design's values, plus two algorithms that no signature determines. Kept.
