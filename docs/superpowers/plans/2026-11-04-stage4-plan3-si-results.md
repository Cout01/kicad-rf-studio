# Stage 4 Plan 3: The SI Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An SI project's run, retune and verify print and write its signal-integrity results (the mixed-mode S at the target, the localising and the link's TDR with their levels between the launches, the TDT and the skew, NEXT and FEXT, and the loss lines) under the relative label and the stated limits, and `compare BASE VARIANT` reports two SI projects' deltas, each resolved or not, refusing projects simulated with different settings.

**Architecture:**
- **One reading.** `core/post/si.py` turns the chain's S into a `Reading`. The chain is the layout N-port with its part ports closed, each load held at DC at its value at the first point above it. The reading holds the mixed mode (scikit-rf's `se2gmm` at the target), the TDRs and TDTs at the localising and the link's rise times on one time axis, the TDT's arrival, the levels between the launches with the short-feature mark, the skew and the crosstalk peaks. The lines, the CSVs, the PNG, verify's comparison and compare's deltas all read it, and each carries the short-feature mark.
- **v1's skeleton.** `chain_results` and `write_outputs` carry an SI project as they carry v1's; plan 2's `si_outputs` copy goes. A run records the route (its 2D εeff, length and loss estimates) and the settings fingerprint before its jobs. `retune` takes the antenna's bypasses, `verify` is v1's with SI's comparison, and `compare` reads each project's run or current verify as it reads an antenna's.

**Tech Stack:**
- Python ≥ 3.11 (dev venv 3.14.2), numpy, scipy (`constants`, `signal.peak_prominences` and `peak_widths`), scikit-rf 2.2 (`se2gmm`, `renormalize`, `Circuit`, the Touchstone writer) and matplotlib, all dependencies already. No new dependency.
- Plan 1's `uniform_grid`, `step_response`, `tdr`, `LOCAL_RISE` and `tools/p4a.py`'s `even_odd_s`; plan 2's `layout`, `si_project`, `si_dict`, `basis_lines` and the fixtures.
- openEMS 0.37.0 and CSXCAD 0.7.0, only in the worker; Task 8 runs them for real.
- pytest, `tests/fake_worker.py` (`KRS_FAKE=network`), `tests/networks.py`; `tools/catalog.py` (Babel, dev extra).

**Spec:**
- `docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md` (binding): §5.12 item 3, with §2–§4, §5.1, §5.5–§5.8, §5.13 and §5.14.
- The Stage 1 spec, `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, where the design reuses it: §3.2, §3.3, §7.1–§7.8; amendments A-1 to A-53.
- Plans 1 and 2 (`docs/superpowers/plans/2026-11-02-stage4-plan1-pins-and-si-hooks.md`, `docs/superpowers/plans/2026-11-03-stage4-plan2-si-project.md`), merged at `3a5a610`; their records `docs/validation/2026-11-03-p4-a.md` and `docs/validation/2026-11-03-si-first-run.md`; their carried items in `.superpowers/sdd/2026-11-03-stage4-plan{1,2}-rulings-and-minors.md`.
- Task 8 lands A-54 (§7.3), A-55 (§7.2, §7.6), A-56 (§7.4, §7.5) and A-57 (§3.2, §3.3), with their exact text.
- Research (git-ignored): `.superpowers/sdd/stage4-research/` r1–r4.

**Branch:** `stage4-plan3`, from `main` at `3a5a610`. This plan is `docs/superpowers/plans/2026-11-04-stage4-plan3-si-results.md`. Commands run from the repo root with `.venv/Scripts/python`. Paths without a folder are under `src/kicad_rf_studio/`. Line references are `main`'s at `3a5a610`; if an earlier task moved a line, find it by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage4-plan3 main`. Then `git diff --stat 3a5a610 HEAD -- src tests tools po pyproject.toml` must print nothing.
2. Commit this plan on the branch.
3. After Task 8: the whole-branch review, a local fast-forward merge into `main`, and delete the branch. Nothing is pushed.

## Global Constraints

- **v1, the antenna and plan 2 byte for byte** (design §3, §4): `tests/test_golden_v1.py`, `tests/test_golden_antenna.py` and `tests/test_golden_si.py` stay green on every task. No v1 or antenna dict gains a key: v1's and an antenna's results gain no `route`, v1's results and verify block no `fingerprint`. A task that moves a pin is wrong: stop and get a ruling, never re-record.
- **SI only behind the schema:** every SI branch tests `core.project.si(data)`, never `kind`.
- **openEMS stays in the worker** (Stage 1 §3.1): the CLI, the orchestrator and `core.post` never import openEMS or CSXCAD.
- **`core/post/si.py`'s imports** (C-5): at module level only the stdlib, numpy and `core.messages`; scipy, scikit-rf, matplotlib, `core.model.parts` (Z0) and `core.post.antenna` only inside the functions that use them. `core.project` imports the module for `LOCAL_RISE` before it defines ROLES, and `parts` and `antenna` import `core.project`: a module-level import of either is a circular import that stops every CLI entry (probed), and `scipy.constants` alone adds 0.17 s to `core.project`'s 0.09 s.
- **The anti-goals** (design §3): every SI result carries the relative label (I_SI_RELATIVE) and the stated limits (`si_limits`): the lines of run, retune, verify and compare, and both PNGs. A TDR level on a feature shorter than two resolution lengths is never shown as an impedance: I_SI_TDR_SHORT in the lines, I_VERIFY_LEVEL_SHORT in verify's, I_SI_COMPARE_LEVEL_SHORT and "short" in compare.csv's marker cell in compare's, and a cross on every curve of both PNGs. A difference is resolved only past its registered threshold.
- **Messages:** every new user-facing string is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, in the same task, compiled with `.venv/Scripts/python tools/catalog.py` (run, set the msgstr, run again), by the pt-BR design's §6 glossary and this plan's glossary ruling. A word passed as a parameter is a `T_` code; a symbol (Sdd21, NEXT) is not a word. Numbers keep the decimal point. A msgstr keeps every identifier, option, quoted text, backticked command and dotted number of its msgid (`tests/test_sexpr.py`'s KEEP). A table writes `\|` for a pipe inside a cell: the msgid and msgstr hold `|ΔS|`, with no backslash.
- **Tests:** test-first. Tier (a) tests never run openEMS, KiCad, the network or a build; they use the fake worker through the `fake` and `calibrated` fixtures (`KRS_FAKE=network`: the layout is `networks.star(f, N)`) and the committed fixtures. `KrsError` tests check `.code` and `.params`. A run command names its new tests by node id, never by a `-k` word. A guard that passes on `main` (an import probe, a key that must stay absent) says so in its Step 2.
- **Prototype numbers:** a number this plan gives from the architect's or the reviser's probes that the code misses stops the task: report both values and the formula that differs; the test changes only on a ruling. That covers the mixed-mode identities' bounds, the levels and their times, the short-feature marks, the neck's 98.45 Ω, the off-target neck's 102.02 Ω and pad's 44.64 Ω, usb2_hs's uniform route's 361.08 ps, the NEXT peak's 6.245 GHz, the 13.70 ps skew, the short route's 60.47 ps, `si_route`'s numbers, the fake QSPI chain's 26.87 Ω, verify's |ΔS| 0.12326, `compare_verify`'s 0.0169 at 8.705 GHz, the deltas' verdicts and the formatted line parameters.
- **Isolation:** tests never touch a real KiCad folder, the Documents folder, KiCad's settings or the real data folder. Task 8's runs set LOCALAPPDATA and XDG_DATA_HOME to a folder under `$env:TEMP` in the same call, and type `CSXCAD_INSTALL_PATH` in the call, never in a file.
- **Full suite** before every commit: `.venv/Scripts/python -m pytest -q`, about 23 minutes (2223 passed, 6 skipped at `3a5a610`; this plan's network-fake runs add about two). Run it once, in the background, with nothing beside it, and wait for it to exit.
- **Git:** no push. The pre-commit privacy gate runs on every commit; never use `--no-verify`. No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name; write `<openEMS folder>` and `<RUN>`. No commit message carries a co-author line; use the messages as given.
- **Files:** every new `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`. Code and docs are in English.
- **Python** only with a script, `-c` or `-m`: never a bare interactive `python`, least of all in a background shell.
- **Workflow:** `graphify query "<question>"` before reading code, and `graphify update .` after each commit. Ponytail: the laziest solution that works, in the fewest files, with a `ponytail:` comment naming the ceiling on each corner cut. Reuse plan 1's `tdr`, `step_response` and `uniform_grid`; scikit-rf's `se2gmm` and `renormalize`; scipy's `peak_prominences` and `peak_widths`; `chain_results`, `part_impedances`, `loads`, `terminate`, `s2p_impedance`, `touchstone`, `port_map`, `write`, `indicator_lines`, `loss_expected`, `assign`, `verify_spec`, `results_of`, `current_verify`, `fingerprint`, `basis_lines`, `deltas_csv`, `DELTA_COLUMNS` and antenna's `_csv`; the antenna's bypass rules; the fake worker; the tests' `result_lines`, `twin` and `compared`.

## Review Focus

1. **A part port's load at DC.** `with_box` divides by ω·C_box (its `np.where` computes both branches), and `z_part` divides by ω·C, so f = 0 gives a RuntimeWarning for every part port and an infinite load for a capacitor or an open (DNP) part; Circuit then writes NaN into S, and the TDR reads garbage. The architect's probe met this on the USB fixture's own resistors in v1's verify path. An S2P file reaches no DC either. Expected: each load is evaluated on `chain.above_dc(f)`, the grid with its DC point replaced by its first point above DC, in the run, the retune and verify's comparison alike; S stays finite and no warning is raised; an S2P file from 1 MHz retunes, one from 10 MHz is refused with E_S2P_BAND naming 5.0 MHz; a grid off DC (v1's, an antenna's) is unchanged. Checks: Task 4's `test_a_nets_run_reads_its_levels_and_holds_each_load_at_dc` (R1 open, warnings as errors), Task 5's `test_an_si_retune_takes_an_s2p_file_from_the_first_point_above_dc` and Task 6's `test_verify_puts_an_si_lines_parts_in_the_grid_and_compares` (warnings as errors).
2. **A measured line that reads no level.** Two cases: a route shorter than its two launches (a 5 mm net), and a line through which no step passes (the network fake's star, whose differential mode never reaches the far end). Expected: no level read, a line that says which case it is, verify's and compare's levels not compared. Checks: Task 1's `test_the_levels_between_the_launches_and_the_short_features`; Task 3's `test_a_route_with_no_level_says_why`; Task 4's `test_an_si_run_writes_its_results` (I_SI_TDR_NO_ARRIVAL); Task 6's `test_verify_puts_an_si_lines_parts_in_the_grid_and_compares` (I_VERIFY_NO_LEVELS); Task 7's `test_the_si_deltas_and_their_significance` (None rows).
3. **A level on a short feature, wherever a level is shown.** Three shapes the first rule missed: a short feature on a route that is itself off the target (its half height from the target falls on the route's own plateau), a uniformly mistuned route under four resolution lengths long (usb2_hs: about 0.9 resolution lengths between the launches), and a short level that verify or compare prints in Ω. Expected: the feature is marked against its own base and the uniform route is a level; verify's and compare's level lines and compare.csv carry the mark; both PNGs cross every curve's short level. Checks: Task 1's `test_the_levels_between_the_launches_and_the_short_features`; Task 4's `test_the_summary_png_holds_the_label_the_limits_and_marks_a_short_feature`; Task 6's `test_verifys_comparison_keeps_the_short_mark`; Task 7's `test_the_deltas_of_a_net`.
4. **The fingerprint's fields.** Two SI projects compare cannot use (other line ends or victims, another target or interface, an antenna project against an SI one, a plan-2 result with no route) and one it must take: a geometry variant whose `mesh.max_cell_mm` differs only because its lines' 2D εeff does (usb2_hs_45: 0.413997 against 0.414074 mm). Expected: E_COMPARE_SETTINGS naming the fields, E_COMPARE_KIND naming the odd project before any board is read (`pipeline.load` raising proves it), E_COMPARE_NO_RESULT; nothing written; the 45° variant's fingerprint equal to usb2_hs's. Checks: Task 2's `test_an_si_run_records_its_route_and_fingerprint_before_its_jobs` (the keys written out) and `test_an_si_fingerprint_leaves_out_what_the_lines_set`; Task 7's `test_compare_refuses_si_projects_it_cannot_compare`.
5. **A single-ended net with no victim (qspi_clk), and parts that are not ports.** Expected: S11 and S21 at the target, no mode conversion, no skew, and no crosstalk line, CSV column, delta row or PNG panel; a pull-up left open, a DNP pull-up and a part set to copper are no ports: retune refuses (E_RETUNE_ROLE, E_RETUNE_NO_PARTS), verify refuses (E_VERIFY_NO_PARTS), and compare reads the run. A route of 45° tracks alone has no section and no loss estimate. Checks: Task 1's `test_read_holds_what_the_lines_and_the_deltas_need`; Task 2's `test_a_route_with_no_section_has_no_loss_estimate`; Task 3's `test_the_lines_of_a_net_with_a_short_feature`; Task 4's `test_the_si_csvs`; Task 5's `test_an_si_retune_takes_the_bypasses_and_their_refusals` and `test_a_dnp_pull_up_is_open_at_open_and_not_listed`; Task 7's `test_the_deltas_of_a_net` and `test_compare_reads_a_partless_si_projects_run`.

---

## File structure

```
src/kicad_rf_studio/core/post/si.py (DIFF_OHM, SE_OHM, ARRIVAL_FLOOR, FLOOR_DB, Level, db, mixed_mode, arrival,
  distance_mm, levels, Reading, read; the N_TDR mark); tests/test_post_si.py                                          # T1
core/post/si.py (COPPER_RHO, hammerstad); pipeline.py (si_route, fingerprint, _run, run, results_of);
  tests/test_post_si.py, tests/test_si_run.py, tests/test_run.py, tests/test_match_antenna.py                          # T2
core/post/si.py (si_limits, si_lines); core/messages.py, po/pt_BR.po and the .mo; tests/test_post_si.py               # T3
core/post/si.py (SI_OUTPUTS, TDR_COLUMNS, si_csv, tdr_csv, draw_si, si_png); core/post/chain.py (above_dc,
  part_impedances); core/post/waves.py (layout's marker); core/mesh/rule.py (a comment); pipeline.py (chain_results,
  write_outputs, run's docstring; si_outputs removed); messages, po, .mo; tests/test_post_si.py, tests/test_si_run.py,
  tests/test_post_outputs.py                                                                                          # T4
pipeline.py (retune, assign); core/model/parts.py (a DNP pull-up); cli.py (I_CHAIN); messages, po, .mo;
  tests/test_si_run.py, tests/test_si_lines.py, tests/test_cli_si.py                                                  # T5
core/post/si.py (compare_verify); core/model/spec.py (verify_spec); pipeline.py (verify, _verify); messages, po, .mo;
  tests/test_post_si.py, tests/test_si_run.py                                                                         # T6
core/post/si.py (IL_DB, DB, LEVEL_FLOOR_DB, SKEW_PS, si_deltas, si_delta_lines); pipeline.py (_full_record,
  antenna_result, si_result, compare_projects, the module docstring); cli.py (the module docstring); messages, po,
  .mo; tests/test_si_compare.py (new), tests/test_si_run.py                                                           # T7
docs/validation/<date>-si-results.md and the Stage 1 spec                                                              # T8
```

---

### Task 1 [code]: The mixed mode and the TDR readings

**Files:** Modify `core/post/si.py` (its docstring; the N_TDR mark at L8-9; the names below after `tdr`). Test: `tests/test_post_si.py`.

**Interfaces:**
- Consumes: `step_response`, `tdr`, `LOCAL_RISE`, `uniform_grid`; `p4a.even_odd_s`; `test_project.si_dict`.
- Produces, in `core/post/si.py`:
  - `DIFF_OHM, SE_OHM = 1.0, 0.5`; `ARRIVAL_FLOOR = 1e-3`; `FLOOR_DB = -300.0`; `Level = tuple[float, float, bool]`, (t in s, Z in Ω, short).
  - `db(x: np.ndarray) -> np.ndarray`; `distance_mm(t, eeff: float)`.
  - `mixed_mode(s: np.ndarray, f: np.ndarray, target: float, paired: bool) -> np.ndarray`.
  - `arrival(t: np.ndarray, step: np.ndarray) -> float | None`.
  - `levels(t: np.ndarray, z: np.ndarray, t_r: float, t_far: float | None, target: float, ohm: float) -> tuple[Level, Level] | None`.
  - `@dataclass(frozen=True) class Reading` with the fields `f, s, m, marker, rise, t, z, z_link, tdt, tdt_link, t_far, levels, skew, xt, eeff`; `read(s: np.ndarray, f: np.ndarray, project: dict, eeff: float) -> Reading`.
  - In `tests/test_post_si.py`: `SE`, `P100`, `P2V`, `ROUTE1`, `NECK`, `line_s(sections, f, z0=50.0)`, `pair6(next_a=0.0, fext_a=0.0, tau_n=0.2e-9)` and `pair8(next2=0.01, fext2=0.005)`, which Tasks 3, 4, 6 and 7 import.

- [ ] **Step 1: Write the failing tests,** in `tests/test_post_si.py`. Its imports gain `subprocess`, `sys`, `from kicad_rf_studio.core.post.si import (ARRIVAL_FLOOR, FLOOR_DB, SE_OHM, Reading, arrival, distance_mm, levels, mixed_mode, read)` and `from test_project import si_dict`. Add:

```python
SE = {"target_ohm": 50.0, "tolerance": 0.1, "f_max_hz": 10e9, "rise_s": 1e-9, "marker_hz": 133e6, "pair": None,
      "dielectric": "lossless",
      "lines": [{"role": "measured", "chain": {"start": "A1.1", "end": "A2.1", "nets": ["SIG"], "series": [],
                                                "shunt": []}}]}  # a se50 net, as si_lines reads one
P100 = {**si_dict(), "target_ohm": 100.0}  # usb2_hs's pair and victim at 100 Ω: 50 Ω a leg, nothing renormalised
P2V = {**P100, "lines": [*P100["lines"], {"role": "victim", "chain": {"start": "TP3.1", "end": "TP4.1",
                                                                         "nets": ["AUX2"], "series": [],
                                                                         "shunt": []}}]}  # design 3: a second victim
ROUTE1 = [(50.0, 4.0, 15.0), (60.0, 4.0, 30.0), (50.0, 4.0, 15.0), (40.0, 4.0, 3.0), (50.0, 4.0, 15.0)]  # Z, εeff, mm
NECK = [(90.0, 3.0, 30.0), (110.0, 3.0, 5.0), (90.0, 3.0, 30.0)]  # design 5.6: a 5 mm neck-down from 90 to 110 Ω


def line_s(sections, f, z0=50.0):
    """S (F, 2, 2) at z0 of lossless lines in cascade, each (Z in Ω, εeff, length in mm), from their ABCD matrices."""
    a, b, c, d = (np.ones(len(f), complex), np.zeros(len(f), complex), np.zeros(len(f), complex),
                  np.ones(len(f), complex))
    for z, eps, length in sections:
        th = 2 * np.pi * f * length * 1e-3 * math.sqrt(eps) / C0
        a, b, c, d = (a * np.cos(th) + b * 1j * np.sin(th) / z, a * 1j * z * np.sin(th) + b * np.cos(th),
                      c * np.cos(th) + d * 1j * np.sin(th) / z, c * 1j * z * np.sin(th) + d * np.cos(th))
    den = a + b / z0 + c * z0 + d
    s11, s21, s22 = (a + b / z0 - c * z0 - d) / den, 2 / den, (-a + b / z0 - c * z0 + d) / den
    return np.stack([np.stack([s11, s21], -1), np.stack([s21, s22], -1)], -2)


def pair6(next_a=0.0, fext_a=0.0, tau_n=0.2e-9):
    """S (F, 6, 6) at 50 Ω of a pair's two matched legs (P 0.2 ns, N tau_n) and a matched victim, in SI's port order,
    the victim's start coupled to P's start by next_a and its end by fext_a."""
    s = np.zeros((len(F), 6, 6), complex)
    for (i, j), tau in (((0, 2), 0.2e-9), ((1, 3), tau_n), ((4, 5), 0.2e-9)):
        s[:, i, j] = s[:, j, i] = np.exp(-2j * np.pi * F * tau)
    s[:, 4, 0] = s[:, 0, 4] = next_a
    s[:, 5, 0] = s[:, 0, 5] = fext_a
    return s


def pair8(next2=0.01, fext2=0.005):
    """pair6(0.05, 0.02) with a second matched victim on ports 7 and 8, coupled to P's start by next2 and its end by
    fext2: P2V's ports."""
    s = np.zeros((len(F), 8, 8), complex)
    s[:, :6, :6] = pair6(0.05, 0.02)
    s[:, 6, 7] = s[:, 7, 6] = np.exp(-2j * np.pi * F * 0.2e-9)
    s[:, 6, 0] = s[:, 0, 6] = next2
    s[:, 7, 0] = s[:, 0, 7] = fext2
    return s


def test_mixed_mode_of_an_ideal_coupled_pair_is_matched_in_its_modes():  # design 5.5: se2gmm at the target
    ze, ee, zo, eo, length = 60.0, 3.3, 45.0, 2.9, 30.0  # a 90 Ω pair, its common mode at 30 Ω
    m = mixed_mode(even_odd_s(ze, ee, zo, eo, length, F), F, 90.0, True)  # the 4-port at 50 Ω a port
    leg = even_odd_s(ze, ee, zo, eo, length, F, 45.0)  # each leg at 45 Ω: 90 Ω differential, 22.5 Ω common
    th = 2 * np.pi * F * length * 1e-3 * math.sqrt(eo) / C0
    assert np.abs(m[:, 0, 0]).max() <= 1e-12 and np.abs(m[:, 1, 0] - np.exp(-1j * th)).max() <= 1e-12  # Sdd
    assert np.abs(m[:, 2, 2] - leg[:, 0, 0] - leg[:, 0, 1]).max() <= 1e-12  # Scc11: the even mode's Γ at 45 Ω
    assert np.abs(m[:, 3, 2] - leg[:, 0, 2] - leg[:, 0, 3]).max() <= 1e-12  # Scc21
    assert np.abs(m[:, 2:, :2]).max() <= 1e-12 and np.abs(m[:, :2, 2:]).max() <= 1e-12  # a symmetric pair converts none
    o = [0, 2, 1, 3]  # a 60 Ω line and an uncoupled victim in a net's order: start, end, the victim's start and end
    s4 = even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, F)[:, o][:, :, o]
    net = mixed_mode(s4, F, 60.0, False)
    th = 2 * np.pi * F * 50e-3 * 2.0 / C0
    assert np.abs(net[:, 0, 0]).max() <= 1e-6 and np.abs(net[:, 1, 0] - np.exp(-1j * th)).max() <= 1e-6
    assert np.abs(net[:, 2:, :2]).max() == 0.0  # no coupling made
    assert np.abs(net[:, 2:, 2:] - s4[:, 2:, 2:]).max() <= 1e-6  # the victim's ends stay at 50 Ω (renormalize: 3.6e-8)


def test_the_crosstalk_peaks_follow_the_even_odd_4port():  # design 5.6; P4-A's identities
    ze, zo = 62.5, 40.0  # √(Ze·Zo) = 50 Ω: a homogeneous stripline's 4-port at 50 Ω has no S11 and no FEXT
    o = [0, 2, 1, 3]
    (next_db, next_hz, fext_db, _), = read(even_odd_s(ze, 4.0, zo, 4.0, 30.0, F)[:, o][:, :, o], F, SE, 4.0).xt
    assert next_db == pytest.approx(20 * math.log10((ze - zo) / (ze + zo)), abs=1e-5) and next_hz == 6.245e9
    assert fext_db == FLOOR_DB  # exactly none: the floor, never -inf with a warning
    xt = read(pair6(next_a=0.05), F, P100, 3.0).xt
    assert xt[0][0] == pytest.approx(20 * math.log10(0.05 / math.sqrt(2)), abs=1e-9)  # driven differentially: half
    two = read(pair8(), F, P2V, 3.0).xt  # the second victim at m's ports 6 and 7
    assert [(round(x[0], 4), round(x[2], 4)) for x in two] == [(-29.0309, -36.9897), (-43.0103, -49.0309)]


def test_the_tdt_arrives_at_half_its_peak_and_the_skew_is_the_legs_difference():  # design 5.6, 6
    t, step = step_response(even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, F, 60.0)[:, 2, 0], F, TR)  # a matched line
    assert arrival(t, step) == pytest.approx(TAU - (t[1] - t[0]) / 2, abs=0.05e-12)  # the sum's half sample
    assert arrival(t, 0.9 * ARRIVAL_FLOOR * step) is None  # nothing passes
    p, n = read(pair6(tau_n=0.2137e-9)[:, :4, :4], F, P100, 3.0).skew
    assert n - p == pytest.approx(13.7e-12, abs=0.01e-12)


def test_the_levels_between_the_launches_and_the_short_features():  # design 5.6; anti-goal 2; Review Focus 2, 3
    s = line_s(ROUTE1, F)
    t, z = tdr(s[:, 0, 0], F, TR)
    t_far = 2 * arrival(t, step_response(s[:, 1, 0], F, TR)[1])
    low, high = levels(t, z, TR, t_far, 50.0, SE_OHM)
    assert (low[0], round(low[1], 2), low[2]) == (pytest.approx(818.75e-12), 46.68, True)  # 3 mm of 40 Ω: no level
    assert (high[0], round(high[1], 2), high[2]) == (pytest.approx(431.25e-12), 60.0, False)  # 30 mm of 60 Ω
    neck = read(line_s(NECK, F), F, {**SE, "target_ohm": 90.0}, 3.0).levels
    assert (round(neck[1][1], 2), neck[1][2], neck[0][2]) == (98.45, True, False)  # about 8 Ω high, not 20; marked
    off = read(line_s([(96.0, 3.0, 30.0), (110.0, 3.0, 5.0), (96.0, 3.0, 30.0)], F), F, {**SE, "target_ohm": 90.0},
               3.0).levels[1]  # the neck on a route 6 Ω high, inside the band
    pad = read(line_s([(47.0, 4.0, 30.0), (40.0, 4.0, 3.0), (47.0, 4.0, 30.0)], F), F, SE, 4.0).levels[0]
    assert (round(off[1], 2), off[2], round(pad[1], 2), pad[2]) == (102.02, True, 44.64, True)  # each against its base
    flat = read(line_s([(95.0, 3.2777, 30.405)], F), F, {**SE, "target_ohm": 90.0}, 3.2777)  # usb2_hs's route, 95 Ω
    assert flat.t_far == pytest.approx(361.08e-12, abs=0.01e-12) and [x[2] for x in flat.levels] == [False, False]
    assert levels(t, z, TR, None, 50.0, SE_OHM) is None
    short = read(line_s([(50.0, 4.0, 5.0)], F), F, SE, 4.0)  # a 5 mm route: its round trip under its two launches
    assert short.t_far == pytest.approx(60.47e-12, abs=0.01e-12) and short.levels is None
    assert distance_mm(TR, 4.0) == pytest.approx(9.3685, abs=1e-4)  # t_r·v/2, the resolution length


def test_read_holds_what_the_lines_and_the_deltas_need():  # design 5.6; Review Focus 5
    r = read(pair6(0.05, 0.02), F, P100, 3.0)
    assert isinstance(r, Reading) and (r.marker, r.rise, r.eeff) == (48, (LOCAL_RISE / 10e9, 5e-10), 3.0)
    assert r.m.shape == (len(F), 6, 6) and r.t.shape == r.z.shape == r.z_link.shape == r.tdt.shape == r.tdt_link.shape
    assert r.t_far == pytest.approx(0.4e-9 - (r.t[1] - r.t[0]), abs=0.1e-12)  # twice the thru's arrival
    assert len(r.xt) == 1 and r.skew[0] == r.skew[1]
    n = read(line_s(ROUTE1, F), F, SE, 4.0)
    assert (n.marker, n.skew, n.xt) == (27, None, [])  # 133 MHz on the 5 MHz grid reads at 135 MHz; a net: no skew
    long = read(line_s([(50.0, 4.0, 15.0), (60.0, 4.0, 200.0)], F), F, SE, 4.0)  # the link's on the localising t
    assert abs(long.t[np.argmax(long.z_link > 55)] - long.t[np.argmax(long.z > 55)]) < long.rise[1]  # 25 ps, not 3.5 ns
    assert abs(long.t[np.argmax(long.tdt_link > 0.5)] - long.t[np.argmax(long.tdt > 0.5)]) < long.rise[1]


def test_the_project_and_the_cli_import_neither_scipy_nor_scikit_rf():  # C-5: core.project imports this module
    out = subprocess.run([sys.executable, "-I", "-c", "import sys, kicad_rf_studio.core.project, kicad_rf_studio.cli; "
                          "print(sorted(m for m in ('scipy', 'skrf') if m in sys.modules))"],
                         capture_output=True, text=True)
    assert out.stdout.strip() == "[]"
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_si.py -q`. Expected: FAIL with `cannot import name 'ARRIVAL_FLOOR'` (the whole file at collection; its import guard is green on `main`, a guard Step 3 keeps).
- [ ] **Step 3: `core/post/si.py`.**
  - **The docstring** becomes: "Signal integrity's readings (Stage 4 design 5.1, 5.5, 5.6): the uniform grid from DC, the Gaussian rise filter and the TDR's step response from S; mixed mode at the target; the TDT's arrival, the levels between the launches and the skew; and, from later tasks, the lines, files, verify's comparison and compare's deltas. At module level it imports only the stdlib, numpy and core.messages: core.project imports it for LOCAL_RISE, so scipy, scikit-rf, matplotlib, core.model.parts and core.post.antenna are imported inside the functions that use them (C-5)."
  - **The N_TDR mark** (L8-9) becomes `# ponytail: a response longer than the 200 ns record wraps (an SI load holds its first point above DC at DC, so a series C's time constant never enters it), and Z = z_ref(1 + ρ)/(1 − ρ) has no bound as ρ → 1 (an open; draw_si clips its axis); P4-C or P4-D sets another N_TDR if a coupon needs one`.
  - **The constants,** each commented: `DIFF_OHM, SE_OHM = 1.0, 0.5` ("design 5.8: the significance of a differential and a single-ended TDR level; a level that close to the target marks no feature"); `ARRIVAL_FLOOR = 1e-3` ("a TDT whose peak stays under this has no arrival: nothing passes the line"); `FLOOR_DB = -300.0` ("the level in dB an exact zero reads as: an ideal pair's Scd21, crosstalk at DC").
  - **`db(x)`:** "|x| in dB, floored at FLOOR_DB, so an exact zero reads as that, never −inf with a warning."
  - **`distance_mm(t, eeff)`:** "The distance along the route, in mm, of the round-trip time `t` (s) at `eeff`: t·c/(2·√eeff); of a rise time, its resolution length t_r·v/2 (design 5.6)." It imports `c` from scipy.constants inside. Mark `# ponytail: one 2D εeff for the whole route, the measured line's length-weighted one: a pad, a via or a neck of another εeff, or a pair's odd mode a few % faster, sits a few % off along this axis; a per-section axis if a gate needs it`.
  - **`mixed_mode(s, f, target, paired)`:** "S (F, N, N) at Z0 on every port, ports in project.json's order, renormalised to the target (Stage 4 design 5.5; Stage 1 7.7: s_def "power" passed explicitly, the impedances real, so every definition agrees): a pair's [P start, N start, P end, N end] through scikit-rf's Network.se2gmm(p=2) to [d0, d1, c0, c1], `target` the differential reference and target/4 the common one; a net's start and end renormalised to `target` (Network.renormalize, one impedance a port); a victim's ends stay at Z0." It imports skrf and `core.model.parts`' Z0 inside; builds `rf.Network(frequency=rf.Frequency.from_f(f, unit="Hz"), s=s, z0=Z0, s_def="power")` on a copy of `s`; returns its `.s`. Mark `# ponytail: the common reference is target/4, the uncoupled pair's; a measured Zcomm if P4-B needs it`.
  - **`arrival(t, step)`:** docstring "The time (s) `step`, a TDT on step_response's `t`, first reaches half its peak, interpolated linearly between that sample and the one before (design 5.6); None when its peak is under ARRIVAL_FLOOR: nothing passes." Mark `# ponytail: step_response's sample at t sums the impulse up to t + dt/2, so an arrival reads half a sample (3.1 ps at 10 GHz) early; a skew, a difference, does not`.
  - **`levels(...)`,** as given (its rule's prototype numbers are pinned to 0.01 Ω, so the body is the one reasonable implementation, its edge cases included; si.py gains `import warnings` and `from dataclasses import dataclass`):

```python
def levels(t: np.ndarray, z: np.ndarray, t_r: float, t_far: float | None, target: float,
           ohm: float) -> tuple[Level, Level] | None:
    """The TDR `z` on `t`'s lowest and highest levels between the launches (design 5.6), each (t, Z, short), searched
    where t_r < t < t_far − t_r, the far port's launch at t_far; None without t_far, or with that span empty (a route
    no longer than its two launches). A level is short, on a feature under two resolution lengths and so not its
    impedance, when it lies more than `ohm` off `target` and either of two widths is under 2·t_r: its run past half
    its height from `target`, within 0 ≤ t ≤ t_far (the route between the ports, so a short route clips no level), or,
    when it stands more than `ohm` above its own base in the span (scipy.signal.peak_prominences), its width at half
    that prominence (peak_widths): a short feature on a route that is itself off the target."""
    from scipy.signal import peak_prominences, peak_widths  # here only (C-5)

    # ponytail: half-height widths from the target and from the level's own base, tuned on synthetic lines (the neck
    # and a pad, each on and off the target, a uniform mistuned route, launches of 0.3 nH); P4-F checks it on the
    # neck and the gap
    if t_far is None:
        return None
    span = np.flatnonzero((t > t_r) & (t < t_far - t_r))
    if not span.size:
        return None
    route = np.flatnonzero((t >= 0) & (t <= t_far))
    out = []
    for k in (span[np.argmin(z[span])], span[np.argmax(z[span])]):
        half, side = (z[k] + target) / 2, np.sign(z[k] - target) or 1.0
        i = j = k
        while i > route[0] and (z[i - 1] - half) * side > 0:
            i -= 1
        while j < route[-1] and (z[j + 1] - half) * side > 0:
            j += 1
        x, at = side * z[span], [k - span[0]]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # scipy's PeakPropertyWarning: an extreme at an edge
            prominence = peak_prominences(x, at)
        local = peak_widths(x, at, 0.5, prominence)[0][0] * (t[1] - t[0]) if prominence[0][0] > ohm else math.inf
        out.append((float(t[k]), float(z[k]), bool(abs(z[k] - target) > ohm and min(t[j] - t[i], local) < 2 * t_r)))
    return out[0], out[1]
```

  - **`Reading` and `read`:** `Reading`'s docstring names each field: `f` (Hz, the uniform grid from DC); `s` (F, P, P), the chain at Z0; `m`, mixed_mode's; `marker`, the grid index nearest marker_hz; `rise`, (LOCAL_RISE/f_max_hz, rise_s); `t` and `z`, the localising TDR of m[:, 0, 0] at the target; `z_link`, the link's, on the same `t`; `tdt` and `tdt_link`, the step of m[:, 1, 0] at each rise time, on the same `t`; `t_far`, twice arrival(t, tdt), None without one; `levels`; `skew`, a pair's legs' arrivals (P, N), None for a net or when either has none; `xt`, per victim in port order, (NEXT's peak dB, its Hz, FEXT's peak dB, its Hz); `eeff`, the distance axis's 2D εeff. `read(s, f, project, eeff)` fills them: paired is `project["pair"] is not None` and `target = project["target_ohm"]`; `t, z = tdr(m[:, 0, 0], f, rise[0], target)`; the link's TDR and both TDTs onto `t`, since step_response starts its axis LEAD rise times before t = 0 and the two axes differ by 1.5 to 11.5 ns: `t_l, z_l = tdr(m[:, 0, 0], f, rise[1], target)` then `z_link = np.interp(t, t_l, z_l)`, `tdt = step_response(m[:, 1, 0], f, rise[0])[1]` and `tdt_link` likewise interpolated from rise[1]'s; levels with DIFF_OHM for a pair, else SE_OHM; the skew from `step_response` of `s[:, 2, 0]` and `s[:, 3, 1]` at the localising rise; a victim's ports in `m` are 4 and 5 onward for a pair, 2 and 3 onward for a net, NEXT `db(m[:, v, 0])` and FEXT `db(m[:, v + 1, 0])`, each's peak and its grid point. The docstring says read takes the chain, never the layout, so the part ports are closed (Stage 4 design 5.6). Mark `# ponytail: NEXT at a victim's first-named end and FEXT at its second, so --victim names the end nearer the measured line's start first; a pick by geometry if users swap them`.
- [ ] **Step 4: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_p4a.py tests/test_golden_si.py -q`. Expected: PASS. The prototypes read Sdd11 7e-17, Scc11 2.2e-16, the net 3.3e-8 and its victim block 3.6e-8; the NEXT peak −13.170830 dB against 20·log10(k) −13.170827; the arrival 3.12 ps before τ; the skew 13.697 ps; the neck 98.4467 Ω; the link's 55 Ω crossing 25 ps after the localising one's (3.525 ns uninterpolated).
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/post/si.py tests/test_post_si.py
git commit -m "feat(post): an SI reading of a chain: mixed mode through se2gmm at the target, the localising and the link's TDR and TDT on one time axis, the TDT's arrival, the levels between the launches with a short feature marked against the target and its own base, the skew and the crosstalk peaks (Stage 4 design 5.5, 5.6)"
graphify update .
```

---

### Task 2 [code]: An SI run's route and fingerprint

**Files:** Modify `core/post/si.py` (`COPPER_RHO`, `hammerstad`); `pipeline.py` (`si_route` after `expected_loss` L410; `fingerprint` L1036-1046; `_run` L830-876 and `run`'s docstring L793-810; `results_of` L1023-1033). Test: `tests/test_post_si.py`, `tests/test_si_run.py`, `tests/test_run.py` (L294), `tests/test_match_antenna.py` (`test_an_antenna_run_records_its_settings_fingerprint`).

**Interfaces:**
- Consumes: `cross_section`, `solve`, `ShortError`, `substrate_h`, `route_length`, `loss_expected`; `test_cli_si.si_project`, `FIX`, `USB`, `QSPI`; `test_tracer.part`, `smd`, `track`.
- Produces:
  - `si.COPPER_RHO = 1.72e-8`; `si.hammerstad(f: float, w_mm: float, z0: float) -> float`, in Np/m.
  - `pipeline.si_route(board: Board, geom: Geometry, project: dict) -> dict`, `{"eeff": float, "length_mm": float, "loss_db": {"conductor": [at marker_hz, at f_max], "dielectric": [at marker_hz, at f_max]} | None}`.
  - `fingerprint(project)` of an SI project: its `preset`, `region`, `interface`, `f_max_hz`, `rise_s`, `marker_hz`, `target_ohm`, `stackup`, `dielectric`, `lid` and `lid_height_mm`; `"mesh"`, project.json's mesh without `max_cell_mm`; `"ends"` (the external ports' signal pads in order); `"app"` and `"openems"`.
  - An SI run's results hold `"route"` and `"fingerprint"`, both taken before the jobs; `results_of` reads SI results without `"route"` as stale.

- [ ] **Step 1: Write the failing tests.** In `tests/test_post_si.py` (imports gain `COPPER_RHO`, `hammerstad`):

```python
def test_hammerstads_conductor_loss_is_scikit_rfs():  # design 5.6: Hammerstad, smooth copper
    from skrf.media import MLine
    f = np.array([240e6, 10e9])
    for w, z0 in ((0.3, 51.0), (0.6, 35.0)):  # analyse_loss reads nothing of its instance
        mline = MLine.analyse_loss(None, 4.3, 3.2, 0.0, COPPER_RHO, 1.0, z0, z0, f, w * 1e-3, 35e-6, 0.0)[0]
        assert [hammerstad(x, w, z0) for x in f] == pytest.approx(mline, rel=1e-12)
```

  In `tests/test_si_run.py` (imports gain `__version__` and `cli` from kicad_rf_studio, `save_project`, `FIX` and `USB` from test_cli_si, and `part`, `smd`, `track` from test_tracer):

```python
def test_an_si_route_records_its_2d_eps_eff_length_and_loss(tmp_path):  # design 5.6: the loss lines' numbers
    for board, eeff, length, conductor, dielectric in [(USB, 3.2777, 30.405, [0.0497, 0.3210], [0.0218, 0.9072]),
                                                       (QSPI, 3.3294, 17.0425, [0.0202, 0.1748], [0.0069, 0.5161])]:
        project, b, geom, _ = pipeline.load(si_project(tmp_path / board.stem, board))
        assert pipeline.si_route(b, geom, project) == {
            "eeff": pytest.approx(eeff, abs=1e-4), "length_mm": pytest.approx(length),
            "loss_db": {"conductor": pytest.approx(conductor, abs=1e-4),
                        "dielectric": pytest.approx(dielectric, abs=1e-4)}}


def test_a_route_with_no_section_has_no_loss_estimate(mini_board_file, tmp_path):  # design 5.6; Review Focus 5
    def end(ref, at):  # a signal pad with a ground pad beside it
        return part(ref, smd(1, "SIG"), smd(2, "GND", y=-2), at=at)

    board = mini_board_file(end("A1", "0 0") + end("A2", "10 10") + track("F.Cu", "SIG", 0, 0, 10, 10))  # 45° alone
    project, b, geom, _ = pipeline.load(cli.new_si(board, "A1.1", "A2.1", "custom", f_max=5e9, target=50.0,
                                                   stackup="kicad-default", output=tmp_path / "d")[0])
    assert pipeline.si_route(b, geom, project) == {"eeff": 4.5, "length_mm": pytest.approx(14.1421, abs=1e-4),
                                                   "loss_db": None}  # the stack's largest εr, as new's


def test_an_si_run_records_its_route_and_fingerprint_before_its_jobs(tmp_path, calibrated, monkeypatch):  # 5.6, 5.8
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    project, board, geom, _ = pipeline.load(pj)
    assert d["results"]["route"] == pipeline.si_route(board, geom, project)
    keys = ("preset", "region", "interface", "f_max_hz", "rise_s", "marker_hz", "target_ohm", "stackup", "dielectric",
            "lid", "lid_height_mm")  # design 5.8's fields; t_max_s, window_s, tolerance and gates stay out
    assert d["results"]["fingerprint"] == {**{key: d[key] for key in keys}, "mesh": {"n": 2, "reach_h": 6.0},
                                           "ends": ["U1.11", "U2.6"], "app": __version__,
                                           "openems": "0.37.0"}  # fake_cli's openems_versions
    calls = []
    monkeypatch.setattr(pipeline, "si_route", lambda *a: calls.append("route") or {})
    monkeypatch.setattr(pipeline, "fingerprint", lambda p: calls.append("fingerprint") or {})
    monkeypatch.setattr(pipeline, "simulate", lambda *a, **k: calls.append("simulate"))  # None: the run ends at 3
    assert pipeline.run(pj) == 3 and calls == ["route", "fingerprint", "simulate"]  # a failed probe costs no job
    del d["results"]["route"]  # plan 2's results
    save_project(pj, d)
    with pytest.raises(KrsError) as e:
        pipeline.retune(pj, [])
    assert (e.value.code, e.value.params) == ("E_RESULTS_STALE", {})


def test_an_si_fingerprint_leaves_out_what_the_lines_set(tmp_path, fake):  # design 5.8; Review Focus 4
    a, b = (load_project(si_project(tmp_path / n, FIX / f"{n}.kicad_pcb")) for n in ("usb2_hs", "usb2_hs_45"))
    assert a["mesh"]["max_cell_mm"] != b["mesh"]["max_cell_mm"]  # λ/40 at each board's largest 2D εeff
    assert pipeline.fingerprint(a) == pipeline.fingerprint(b)  # a 45° bend is a variant compare takes
```

  In `tests/test_run.py`, `test_run_writes_the_outputs_of_a_known_network`'s last line reads `assert not {"far_field", "fingerprint", "route"} & set(load_project(pj)["results"])`; in `tests/test_match_antenna.py`, `test_an_antenna_run_records_its_settings_fingerprint` adds `assert "route" not in d["results"]` (an antenna's results gain no route).
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_si.py::test_hammerstads_conductor_loss_is_scikit_rfs tests/test_si_run.py::test_an_si_route_records_its_2d_eps_eff_length_and_loss tests/test_si_run.py::test_a_route_with_no_section_has_no_loss_estimate tests/test_si_run.py::test_an_si_run_records_its_route_and_fingerprint_before_its_jobs tests/test_si_run.py::test_an_si_fingerprint_leaves_out_what_the_lines_set tests/test_run.py::test_run_writes_the_outputs_of_a_known_network tests/test_match_antenna.py::test_an_antenna_run_records_its_settings_fingerprint -q`. Expected: FAIL with `cannot import name 'COPPER_RHO'` and `AttributeError: ... 'si_route'`, and the SI fingerprint's `KeyError: 'band'`; the v1 and antenna tests pass (guards: no route on `main`).
- [ ] **Step 3: `hammerstad`.** `COPPER_RHO = 1.72e-8` commented "Ω·m, KiCad's calculator's 5.8e7 S/m"; docstring "Hammerstad and Jensen's conductor attenuation in Np/m of a microstrip `w_mm` wide of impedance `z0` (Ω) at `f` (Hz), smooth copper (roughness factor 1), as scikit-rf's MLine.analyse_loss: R_s/(z0·w)·K_i, R_s = √(π·f·μ0·COPPER_RHO), K_i = exp(−1.2·(z0/η0)^0.7), μ0 and η0 = √(μ0/ε0) from scipy.constants, imported inside (C-5)." Mark `# ponytail: a microstrip formula, valid where the copper is 3 skin depths thick or more (25 µm at 62.5 MHz); an inner-layer section's conductor loss is a microstrip estimate, and a thinner copper or a lower marker reads it low`.
- [ ] **Step 4: `si_route`,** after `expected_loss`, docstring "An SI run's route (Stage 4 design 5.6), from its geometry, as expected_loss is v1's, recorded with its results: the measured line whose route_length is the longest (a pair's P leg on a tie); each section of that line cut as si_readout cuts a line alone, `cross_section(s, geom.pieces, geom.zs, geom.masks.get(s.layer), "exact", h=substrate_h(geom.zs, (s.layer,)))` (a cut that other copper touches adds nothing), on the slab expected_loss takes (the one below the copper, else above); "eeff", their εeff weighted by length, the distance axis's 2D εeff; "length_mm", that route_length; "loss_db", at marker_hz and at f_max_hz, the copper's 20·log10(e)·Σ hammerstad(f, s.width, z0)·ℓ and the dielectric's −10·log10(1 − loss_expected(terms, f)), each over the sections' Σℓ and times length_mm, in dB. With no section solved (a route of 45° tracks or arcs alone, or every cut touched), "eeff" is the stack's largest εr, as new's, and "loss_db" None." Mark `# ponytail: one line's loss for a pair, the P leg's (the odd mode's runs a little higher); the straight sections' mean per mm stands for the bends and pads`.
- [ ] **Step 5: The record.**
  - **`fingerprint`:** an SI branch first, its keys a local tuple as the antenna's are, its docstring adding "An SI project's (Stage 4 design 5.8): its preset, region, interface, f_max_hz, rise_s, marker_hz, target_ohm, stackup, dielectric, lid and lid_height_mm, its mesh without max_cell_mm, "ends" (its external ports' signal pads, in order, so two projects of other lines or victims never compare) and the versions; max_cell_mm, t_max_s, window_s and the stop window stay out, as they follow the lines' 2D εeff and length, which a variant may change." Mark `# ponytail: max_cell_mm out, so a hand-edited coarser cell compares too; a recorded factor if users edit it`.
  - **`_run`:** `project, board, geom, model = built`; before `simulate`, `route = si_route(board, geom, project) if si(project) else None` and `fp = fingerprint(project) if antenna(project) or si(project) else None`; an SI run's results gain `"route": route` and `"fingerprint": fp`, v1's and an antenna's no route. The docstrings of `run` and `_run` say so.
  - **`results_of`:** E_RESULTS_STALE also when `si(project) and "route" not in results` (a run before this version); the docstring says so.
- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_si_run.py tests/test_run.py tests/test_match_antenna.py tests/test_compare.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(run): an SI run records its route, the 2D eps_eff of its distance axis, its length and Hammerstad's and the dielectric's loss at the marker and f_max, and its settings fingerprint, before its jobs; older SI results read as stale (Stage 4 design 5.6, 5.8)"
graphify update .
```

---

### Task 3 [code]: The SI result lines

**Files:** Modify `core/post/si.py` (`si_limits`, `si_lines`), `core/messages.py`, `po/pt_BR.po` and the `.mo`. Test: `tests/test_post_si.py`.

**Interfaces:**
- Consumes: Task 1's `Reading`, `read`, `db`, `distance_mm`, `ARRIVAL_FLOOR`; Task 2's route dict (its loss_db None with no section); T_DIFFERENTIAL, T_SINGLE_ENDED, T_IN_BAND, T_OUT_OF_BAND (plan 2); W_NO_SECTIONS (v1's).
- Produces: `si_limits(project: dict) -> tuple[str, ...]`; `si_lines(project: dict, r: Reading, route: dict) -> list[tuple[str, dict]]`; in the tests, `ROUTE`.

- [ ] **Step 1: Write the failing tests,** in `tests/test_post_si.py` (imports gain `db`, `si_limits`, `si_lines`, and `render` from core.messages):

```python
ROUTE = {"eeff": 4.0, "length_mm": 63.0, "loss_db": {"conductor": [0.0497, 0.321], "dielectric": [0.0218, 0.9072]}}


def test_the_lines_of_a_net_with_a_short_feature():  # design 5.6; anti-goals 1, 2; Review Focus 3, 5
    r = read(line_s(ROUTE1, F), F, SE, 4.0)
    lines = si_lines(SE, r, ROUTE)
    assert [code for code, _ in lines] == ["I_SI_RELATIVE", "I_SI_INSERTION", "I_SI_WORST", "I_SI_TDR",
                                           "I_SI_TDR_SHORT", "I_SI_TDR_LEVEL", "I_SI_LOSS_CONDUCTOR",
                                           "I_SI_LOSS_DIELECTRIC"]
    assert lines[1][1] == {"mode": "S21", "marker_mhz": "135", "at_marker_db": f"{db(r.m[27, 1, 0]):.3f}",
                           "f_max_ghz": "10", "at_f_max_db": f"{db(r.m[-1, 1, 0]):.3f}"}
    assert lines[2][1] == {"mode": "S11", "worst_db": "-9.88", "f_mhz": "9290"}
    assert lines[3][1] == {"kind": "T_SINGLE_ENDED", "rise_ps": "125", "res_mm": "9.4", "link_ps": "1000",
                           "link_res_mm": "74.9", "eeff": "4.00"}
    assert lines[4][1] == {"level": "T_LOWEST", "z": "46.68", "t_ps": "818.8", "d_mm": "61.4", "two_res_mm": "18.7"}
    assert lines[5][1] == {"level": "T_HIGHEST", "z": "60.00", "t_ps": "431.3", "d_mm": "32.3",
                           "verdict": "T_OUT_OF_BAND"}
    assert lines[6][1] == {"length_mm": "63.0", "marker_mhz": "133", "at_marker_db": "0.050", "f_max_ghz": "10",
                           "at_f_max_db": "0.321"}  # the formula at the marker itself, not its grid point
    assert lines[7][1] == {"at_marker_db": "0.022", "at_f_max_db": "0.907"}
    assert all(render(code, **params) for code, params in lines)


def test_the_lines_of_a_pair_with_a_victim():  # design 5.6
    r = read(pair6(10 ** (-60 / 20) * math.sqrt(2), 10 ** (-70 / 20) * math.sqrt(2)), F, P100, 3.0)
    lines = si_lines(P100, r, ROUTE)
    assert [code for code, _ in lines] == [
        "I_SI_RELATIVE", "I_SI_INSERTION", "I_SI_WORST", "I_SI_WORST", "I_SI_COMMON", "I_SI_TDR", "I_SI_TDR_LEVEL",
        "I_SI_TDR_LEVEL", "I_SI_SKEW", "I_SI_CROSSTALK", "I_SI_LOSS_CONDUCTOR", "I_SI_LOSS_DIELECTRIC"]
    assert [p["mode"] for code, p in lines if "mode" in p] == ["Sdd21", "Sdd11", "Scd21"]
    assert lines[5][1]["kind"] == "T_DIFFERENTIAL" and lines[6][1]["verdict"] == "T_IN_BAND"  # 100 Ω flat
    assert lines[8][1] == {"skew_ps": "+0.00", "p_ps": "196.9", "n_ps": "196.9"}
    assert {k: lines[9][1][k] for k in ("net", "source", "start", "end", "next_db", "fext_db")} == {
        "net": "AUX", "source": "T_PAIR_DRIVE", "start": "TP1.1", "end": "TP2.1", "next_db": "-60.00",
        "fext_db": "-70.00"}


def test_a_route_with_no_level_says_why():  # design 5.6; Review Focus 2, 5
    short = read(line_s([(50.0, 4.0, 5.0)], F), F, SE, 4.0)
    assert ("I_SI_TDR_SHORT_ROUTE", {"t_far_ps": "60.5", "two_rise_ps": "250"}) in si_lines(SE, short, ROUTE)
    cut = read(np.zeros((len(F), 2, 2), complex), F, SE, 4.0)  # nothing passes the line
    assert ("I_SI_TDR_NO_ARRIVAL", {"floor": "0.001"}) in si_lines(SE, cut, ROUTE)
    none = si_lines(SE, short, {**ROUTE, "loss_db": None})  # no section solved: no loss estimate
    assert none[-1] == ("W_NO_SECTIONS", {}) and "I_SI_LOSS_CONDUCTOR" not in dict(none)


def test_the_limits_follow_the_dielectric():  # design 5.6
    assert si_limits(SE) == ("I_LIMIT_SI_CROP", "I_LIMIT_PEC", "I_LIMIT_SI_LOSSLESS", "I_LIMIT_SI_BODIES",
                             "I_LIMIT_SI_PORTS", "I_LIMIT_SI_RESOLUTION")
    debye = {**SE, "dielectric": "debye"}
    assert si_limits(debye)[2] == "I_LIMIT_SI_DEBYE"
    assert "I_SI_LOSS_DIELECTRIC" not in dict(si_lines(debye, read(line_s(ROUTE1, F), F, debye, 4.0), ROUTE))
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_si.py::test_the_lines_of_a_net_with_a_short_feature tests/test_post_si.py::test_the_lines_of_a_pair_with_a_victim tests/test_post_si.py::test_a_route_with_no_level_says_why tests/test_post_si.py::test_the_limits_follow_the_dielectric -q`. Expected: FAIL with `cannot import name 'si_limits'`.
- [ ] **Step 3: `si_limits` and `si_lines`.**
  - **`si_limits(project)`:** "The stated limits of an SI result (design 5.6), in this order: I_LIMIT_SI_CROP, I_LIMIT_PEC (v1's), I_LIMIT_SI_DEBYE or I_LIMIT_SI_LOSSLESS by project["dielectric"], I_LIMIT_SI_BODIES, I_LIMIT_SI_PORTS, I_LIMIT_SI_RESOLUTION."
  - **`si_lines(project, r, route)`:** docstring "An SI result's lines (Stage 4 design 5.6) of the reading `r` and the run's `route`, which follow chain_results' (I_BASIS up to the indicators): I_SI_RELATIVE; I_SI_INSERTION (Sdd21, a net's S21, at the marker and at f_max); I_SI_WORST of Sdd11 (S11), then for a pair of Scd21, and I_SI_COMMON (Scc21 at the marker); I_SI_TDR; the lowest then the highest level as I_SI_TDR_LEVEL, or I_SI_TDR_SHORT on a short feature, else I_SI_TDR_SHORT_ROUTE with t_far, else I_SI_TDR_NO_ARRIVAL {floor: ARRIVAL_FLOOR}; I_SI_SKEW for a pair with both arrivals; I_SI_CROSSTALK per victim (project's victim lines in order, its first net, start and end; source T_PAIR_DRIVE or T_LINE_DRIVE); I_SI_LOSS_CONDUCTOR at the project's marker_hz (the formula's own frequency, not the grid point's), then I_SI_LOSS_DIELECTRIC with a lossless dielectric; W_NO_SECTIONS in their place when the route has no loss estimate."
  - **Indices in `r.m`:** Sdd21/S21 `[:, 1, 0]`, Sdd11/S11 `[:, 0, 0]`, Scd21 `[:, 3, 0]`, Scc21 `[:, 3, 2]`; a worst is the largest `db` over f with its grid point.
  - **Formats:** a frequency in MHz or GHz `:g` of the grid point (`r.f[r.marker]`, `r.f[-1]`), but the loss line's marker `project["marker_hz"]`; insertion dB `:.3f`, other dB `:.2f`, a loss estimate `:.3f`; Ω `:.2f`; a time in ps `f"{t * 1e12:.1f}"` (a level's time lies on the 6.25 ps grid, half of them on a .x5 tie, which this form settles as the pins do), but a rise time `:g`; mm and the length `:.1f`; εeff `:.2f`; the skew `:+.2f` of N − P; `two_res_mm` twice the localising resolution length; `floor` `:g`; `verdict` T_IN_BAND when |Z − target| ≤ tolerance·target, else T_OUT_OF_BAND.
- [ ] **Step 4: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_SI_RELATIVE | Relative: these signal-integrity results compare variants of one board under identical settings; they do not predict measured performance. | Relativo: estes resultados de integridade de sinal comparam variantes de uma placa com configurações idênticas; eles não preveem o desempenho medido. |
| I_SI_INSERTION | {mode} {at_marker_db} dB at the marker ({marker_mhz} MHz) and {at_f_max_db} dB at f_max ({f_max_ghz} GHz). | {mode} de {at_marker_db} dB no marcador ({marker_mhz} MHz) e de {at_f_max_db} dB em f_max ({f_max_ghz} GHz). |
| I_SI_WORST | The worst {mode} up to f_max: {worst_db} dB at {f_mhz} MHz. | O pior {mode} até f_max: {worst_db} dB em {f_mhz} MHz. |
| I_SI_COMMON | Scc21, the common mode's transmission: {scc21_db} dB at the marker ({marker_mhz} MHz). | Scc21, a transmissão do modo comum: {scc21_db} dB no marcador ({marker_mhz} MHz). |
| I_SI_TDR | The {kind} TDR: the localising rise time {rise_ps} ps resolves {res_mm} mm and the link's {link_ps} ps {link_res_mm} mm, at the route's 2D εeff {eeff}; the first resolution length at each port is the port's own launch. | O TDR {kind}: o tempo de subida de localização de {rise_ps} ps resolve {res_mm} mm e o do enlace, de {link_ps} ps, {link_res_mm} mm, com o εeff 2D da rota de {eeff}; o primeiro comprimento de resolução em cada porta é a entrada da própria porta. |
| I_SI_TDR_LEVEL | The {level} TDR level between the launches: {z} Ω at {t_ps} ps ({d_mm} mm), {verdict}. | O nível {level} do TDR entre as entradas: {z} Ω em {t_ps} ps ({d_mm} mm), {verdict}. |
| I_SI_TDR_SHORT | The {level} TDR level between the launches, {z} Ω at {t_ps} ps ({d_mm} mm), lies on a feature shorter than two resolution lengths ({two_res_mm} mm), so it is not that feature's impedance. | O nível {level} do TDR entre as entradas, {z} Ω em {t_ps} ps ({d_mm} mm), fica num trecho mais curto que dois comprimentos de resolução ({two_res_mm} mm), então não é a impedância desse trecho. |
| I_SI_TDR_SHORT_ROUTE | No TDR level is read between the launches: the route's round trip, {t_far_ps} ps, is no longer than its two launches, {two_rise_ps} ps. | Nenhum nível do TDR é lido entre as entradas: a ida e volta da rota, {t_far_ps} ps, não é mais longa que as duas entradas, {two_rise_ps} ps. |
| I_SI_TDR_NO_ARRIVAL | No TDR level is read between the launches: no step reaches the measured line's far end (its TDT stays under {floor}), so the route's end is not found. | Nenhum nível do TDR é lido entre as entradas: nenhum degrau chega à ponta distante da linha medida (o TDT dela fica abaixo de {floor}), então o fim da rota não é encontrado. |
| I_SI_SKEW | Intra-pair skew {skew_ps} ps: the N leg's TDT arrives at {n_ps} ps and the P leg's at {p_ps} ps, each at half its peak. | Skew intrapar de {skew_ps} ps: o TDT da perna N chega em {n_ps} ps e o da perna P em {p_ps} ps, cada um na metade do próprio pico. |
| I_SI_CROSSTALK | Crosstalk into {net} from {source}: NEXT at {start} peaks at {next_db} dB ({next_mhz} MHz) and FEXT at {end} at {fext_db} dB ({fext_mhz} MHz). | Diafonia em {net} a partir {source}: o NEXT em {start} tem pico de {next_db} dB ({next_mhz} MHz) e o FEXT em {end}, de {fext_db} dB ({fext_mhz} MHz). |
| I_SI_LOSS_CONDUCTOR | Not in S: the copper's loss over the route's {length_mm} mm, by Hammerstad's formula for smooth copper, about {at_marker_db} dB at the marker ({marker_mhz} MHz) and {at_f_max_db} dB at f_max ({f_max_ghz} GHz). | Fora de S: a perda no cobre ao longo dos {length_mm} mm da rota, pela fórmula de Hammerstad para cobre liso, cerca de {at_marker_db} dB no marcador ({marker_mhz} MHz) e {at_f_max_db} dB em f_max ({f_max_ghz} GHz). |
| I_SI_LOSS_DIELECTRIC | Not in S either, the dielectric being lossless: its loss over the same length, about {at_marker_db} dB at the marker and {at_f_max_db} dB at f_max. | Também fora de S, pois o dielétrico é sem perdas: a perda nele ao longo do mesmo comprimento, cerca de {at_marker_db} dB no marcador e {at_f_max_db} dB em f_max. |
| T_LOWEST | lowest | mais baixo |
| T_HIGHEST | highest | mais alto |
| T_PAIR_DRIVE | the pair driven differentially at its start | do par excitado em modo diferencial no início |
| T_LINE_DRIVE | the measured line's start | do início da linha medida |
| I_LIMIT_SI_CROP | Limit: the region is cropped inside walls that absorb most of what reaches them and reflect the rest; the planes' cavity resonances depend on the crop, and an open line's radiation is absent. | Limite: a região é recortada dentro de paredes que absorvem a maior parte do que as atinge e refletem o resto; as ressonâncias de cavidade dos planos dependem do recorte, e a radiação de uma linha aberta não está presente. |
| I_LIMIT_SI_LOSSLESS | Limit: the dielectric is lossless, so S holds no dielectric loss; the loss lines estimate it. | Limite: o dielétrico é sem perdas, então S não contém perda no dielétrico; as linhas de perda a estimam. |
| I_LIMIT_SI_DEBYE | Limit: the dielectric is a Debye fit of the stackup's εr and tan δ, a model of its loss, not a measurement. | Limite: o dielétrico é um ajuste de Debye do εr e da tan δ do empilhamento, um modelo da perda dele, não uma medição. |
| I_LIMIT_SI_BODIES | Limit: packages, dies and connector bodies are absent, and a part of three or more pads is its pads alone. | Limite: encapsulamentos, chips e corpos de conectores não estão presentes, e um componente de três ou mais ilhas é só as ilhas dele. |
| I_LIMIT_SI_PORTS | Limit: the ports are lumped 50 Ω ports at the pads, whose own launch fills the first resolution length at each. | Limite: as portas são portas concentradas de 50 Ω nas ilhas, cuja própria entrada ocupa o primeiro comprimento de resolução de cada uma. |
| I_LIMIT_SI_RESOLUTION | Limit: the TDR resolves no feature shorter than two resolution lengths: such a feature's level is not its impedance. | Limite: o TDR não resolve trecho mais curto que dois comprimentos de resolução: o nível de um trecho assim não é a impedância dele. |

  T_PAIR_DRIVE and T_LINE_DRIVE carry pt-BR's contraction (de + o): I_SI_CROSSTALK's msgstr reads "a partir {source}", never "a partir de o".
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_post_si.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(post): an SI result's lines under the relative label, Sdd21 and the worst Sdd11 and Scd21, the TDR's levels with a short feature marked or the reason none is read, the skew, the crosstalk peaks and the loss lines, and the stated limits by the dielectric in force (Stage 4 design 5.6)"
graphify update .
```

---

### Task 4 [code]: The SI outputs of a run and a retune

**Files:**
- Modify: `core/post/si.py` (`SI_OUTPUTS`, `TDR_COLUMNS`, `si_csv`, `tdr_csv`, `draw_si`, `si_png`); `core/post/chain.py` (`above_dc` after `z_value`; `part_impedances` L73-92); `core/post/waves.py` (`layout` L116-129); `core/mesh/rule.py` (the comment at L184-185); `pipeline.py` (`chain_results` L575-613, `write_outputs` L616-658, `run`'s docstring; `si_outputs` L769-790 deleted); `core/messages.py`, `po/pt_BR.po` and the `.mo`.
- Test: `tests/test_post_si.py`, `tests/test_si_run.py` (its plan-2 test `test_an_si_run_writes_its_layout_on_the_grid_from_dc` changes deliberately: see Step 1), `tests/test_post_outputs.py` (`test_only_the_png_writer_imports_matplotlib`).

**Interfaces:**
- Consumes: Tasks 1–3; `touchstone`, `port_map`, `write`, `indicator_lines`, `with_box`, `antenna._csv`, `networks.terminate_np`, `networks.read_s`, `test_match_antenna.result_lines`.
- Produces:
  - `si.SI_OUTPUTS = re.compile(r"(layout|chain)\.s\d+p|si_summary\.(png|csv)|si_tdr\.csv")`, `si.TDR_COLUMNS = ("t_s", "distance_mm", "z_ohm", "z_link_ohm", "tdt", "tdt_link")`.
  - `si_csv(project: dict, r: Reading) -> bytes`; `tdr_csv(r: Reading) -> bytes`; `draw_si(fig, curves: list[tuple[str, Reading]], project: dict, title: str, label: str | None = None) -> list`; `si_png(curves, project, title, label=None) -> bytes`.
  - `chain.above_dc(f: np.ndarray) -> np.ndarray`.
  - `chain_results` for an SI project: basis_lines at GATES_SI, the part ports' loads on `above_dc(lay.f)`, then the indicator lines alone; `write_outputs` writes and reports an SI project's results; `layout()`'s marker is the point of `f` nearest the marker on any grid.

- [ ] **Step 1: Write the failing tests.** In `tests/test_post_si.py` (imports gain `csv`, `io`, `from matplotlib.figure import Figure`, `SI_OUTPUTS`, `TDR_COLUMNS`, `draw_si`, `si_csv`, `si_png`, `tdr_csv`):

```python
def test_the_si_csvs():  # design 5.6; Review Focus 5
    r = read(pair6(0.05, 0.02), F, P100, 3.0)
    rows = list(csv.reader(io.StringIO(si_csv(P100, r).decode())))
    assert rows[0] == ["f_hz", "marker", "sdd11_db", "sdd11_deg", "sdd21_db", "sdd21_deg", "scc11_db", "scc21_db",
                       "scd11_db", "scd21_db", "next1_db", "fext1_db"]
    assert len(rows) == 2002 and rows[49][:2] == ["240000000.0", "marker"] and rows[50][1] == ""
    assert next(csv.reader(io.StringIO(si_csv(P2V, read(pair8(), F, P2V, 3.0)).decode())))[-4:] == [
        "next1_db", "fext1_db", "next2_db", "fext2_db"]  # each victim its columns
    n = read(line_s(ROUTE1, F), F, SE, 4.0)
    assert next(csv.reader(io.StringIO(si_csv(SE, n).decode()))) == ["f_hz", "marker", "s11_db", "s11_deg", "s21_db",
                                                                     "s21_deg"]
    rows = list(csv.reader(io.StringIO(tdr_csv(n).decode())))
    t = np.array([float(row[0]) for row in rows[1:]])
    assert rows[0] == list(TDR_COLUMNS) and t[0] >= -2 * TR and t[-1] <= n.t_far + 2e-9  # the plot's span
    assert [float(x) for x in rows[1][1:3]] == [pytest.approx(distance_mm(t[0], 4.0)), pytest.approx(50.0, abs=1e-3)]
    assert SI_OUTPUTS.fullmatch("si_tdr.csv") and not SI_OUTPUTS.fullmatch("verify.s6p")


def test_the_summary_png_holds_the_label_the_limits_and_marks_a_short_feature():  # 5.6; anti-goals 1, 2; RF 3, 5
    n = read(line_s(ROUTE1, F), F, SE, 4.0)
    fig = Figure()
    axes = draw_si(fig, [("proj", n)], SE, "Title", "label")
    assert fig.get_suptitle() == "Title\n" + render("I_SI_RELATIVE") + "\nlabel"
    assert all(render(code) in fig.texts[-1].get_text() for code in si_limits(SE))
    assert len(axes) == 2  # a net with no victim: the TDR and |S|, no crosstalk
    assert [line.get_label() for line in axes[0].lines if not line.get_label().startswith("_")] == [
        "125 ps, 9.4 mm", "1000 ps, 74.9 mm"]  # each rise time and its resolution length (design 5.6)
    assert sorted(line.get_marker() for line in axes[0].lines if line.get_marker() in ("o", "x")) == ["o", "x"]
    assert len(axes[0].patches) == 3 and axes[0].get_ylim() == (0.0, 150.0)  # the band, both launches; an open clipped
    pair = read(pair6(0.05, 0.02), F, P100, 3.0)
    two = draw_si(Figure(), [("a", pair), ("b", pair)], P100, "T")
    assert len(two) == 3 and [line.get_marker() for line in two[0].lines].count("o") == 4  # every curve's levels
    assert si_png([("proj", n)], SE, "Title")[:8] == b"\x89PNG\r\n\x1a\n"
```

  In `tests/test_post_outputs.py`, `test_only_the_png_writer_imports_matplotlib`'s import line adds `kicad_rf_studio.core.post.si`.

  In `tests/test_si_run.py` (imports gain `warnings`, `from kicad_rf_studio.core.post.chain import above_dc, with_box`, `from kicad_rf_studio.core.post.si import read, si_limits, si_lines`, `read_s` and `terminate_np` from networks, and `result_lines` from test_match_antenna):
  - `test_an_si_run_writes_its_layout_on_the_grid_from_dc` changes deliberately: both `sorted(f.name for f in out.iterdir())` assertions expect `["chain.s6p", "layout.s8p", "si_summary.csv", "si_summary.png", "si_tdr.csv"]`, and the `result_codes(...) == ["I_RESULTS", "I_BASIS", "I_OUTPUTS"]` assertion goes (the next test pins the lines).
  - Add:

```python
def test_an_si_run_writes_its_results(tmp_path, calibrated, monkeypatch):  # design 5.6, 5.12 item 3; Review Focus 2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    res = pipeline.chain_results(pj, p)
    block = si_lines(p, read(res.chain, res.lay.f, p, p["results"]["route"]["eeff"]), p["results"]["route"])
    lines = result_lines(p["results"]["run_dir"])
    codes, k = [code for code, _ in lines], [code for code, _ in lines].index("I_SI_RELATIVE")
    assert codes[:k] == ["I_RESULTS", "I_BASIS", "I_PASSIVITY", "I_RECIPROCITY"] and lines[k:k + len(block)] == block
    assert codes[k + len(block):] == ["I_WHAT_IF", "I_OUTPUTS", *si_limits(p)]
    assert ("I_SI_TDR_NO_ARRIVAL", {"floor": "0.001"}) in block  # the fake's star passes no differential step
    assert np.abs(read_s(pj.parent / "results" / "chain.s6p") - res.chain).max() <= 1e-12
    assert layout(p, p["results"], np.array([0.0, 2e8, 2.5e8, 1e9])).markers == [2]  # the nearest point, on any grid


def test_a_nets_run_reads_its_levels_and_holds_each_load_at_dc(tmp_path, calibrated, monkeypatch):  # RF 1, 5
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    lines = result_lines(p["results"]["run_dir"])
    low = next(params for code, params in lines if code == "I_SI_TDR_LEVEL" and params["level"] == "T_LOWEST")
    assert (low["z"], low["verdict"]) == ("26.87", "T_OUT_OF_BAND") and "I_SI_CROSSTALK" not in dict(lines)
    assert sorted(f.name for f in (pj.parent / "results").iterdir()) == [
        "chain.s2p", "layout.s3p", "si_summary.csv", "si_summary.png", "si_tdr.csv"]
    p["lines"][0]["chain"]["series"][0]["value"] = "open"  # R1 as a DNP placeholder: no impedance at any f, DC too
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)  # with_box divided by zero at DC
        res = pipeline.chain_results(pj, p)
    z = with_box(np.full(2000, np.inf), res.lay.f[1:], p["results"]["c_box"]["R1"])
    held = terminate_np(res.lay.s, [0, 1], np.r_[z[:1], z][:, None])  # the load at 5 MHz, held to DC
    assert np.isfinite(res.chain).all() and np.abs(res.chain - held).max() <= 1e-12
    assert above_dc(np.array([1e9, 2e9])).tolist() == [1e9, 2e9]  # a grid off DC (v1's, an antenna's) as it is
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_si.py::test_the_si_csvs tests/test_post_si.py::test_the_summary_png_holds_the_label_the_limits_and_marks_a_short_feature tests/test_post_outputs.py::test_only_the_png_writer_imports_matplotlib tests/test_si_run.py -q`. Expected: FAIL: the new si.py and chain.py names cannot be imported, the run writes layout.s8p alone, and `layout`'s marker on the 4-point grid is 1. The import probe passes at once (si.py imports matplotlib only inside its PNG functions: a guard Step 3 keeps).
- [ ] **Step 3: The files, in `core/post/si.py`.**
  - **`si_csv(project, r)`:** "si_summary.csv (design 5.6): one row per grid point, f_hz, marker ("marker" at r.marker, else ""), then a pair's sdd11_db, sdd11_deg, sdd21_db, sdd21_deg, scc11_db, scc21_db, scd11_db, scd21_db, or a net's s11_db, s11_deg, s21_db, s21_deg, then next{k}_db and fext{k}_db for victim k from 1; dB by db, degrees by np.angle; comma-separated, "\n" line ends, numbers as Python's repr (csv.writer, as summary_csv)." Indices as si_lines'; Scc11 `[:, 2, 2]`, Scd11 `[:, 2, 0]`.
  - **`tdr_csv(r)`:** "si_tdr.csv (design 5.6): antenna._csv (imported inside) of TDR_COLUMNS, one row per sample of r.t from −2·r.rise[0] to (r.t_far or 0) + 2·r.rise[1], the plot's span: t_s, distance_mm (distance_mm at r.eeff), z_ohm (the localising TDR), z_link_ohm, tdt and tdt_link." The span is a private `_span(r)` mask that draw_si uses too, marked `# ponytail: with no arrival the plot ends 2 link rise times past t = 0 (1 to 6 ns at the presets), so a long line's open beyond that is cut; results.route's round trip if that matters`.
  - **`draw_si(fig, curves, project, title, label=None)`:** docstring "si_summary.png's and compare.png's plots (design 5.6, 5.8) on the matplotlib Figure `fig`, each curve (name, Reading) on every panel: the TDR, the localising rise solid and the link's dashed, against the distance along the route on _span, with the round-trip time on a secondary axis on top (distance_mm at the first curve's εeff), the target band shaded (target ± tolerance), the first curve's launches shaded (its first resolution length at 0 and before t_far), every curve's levels a dot ("o") or, on a short feature, a cross ("x"), and the Ω axis from 0 to 3·target (an open's Z, unbounded as ρ → 1, clipped); |S| in dB against GHz (a pair's Sdd21, Sdd11, Scc21 and Scd21, a net's S21 and S11) with a line at the marker; and, when the first curve holds crosstalk (its xt), each victim's NEXT and FEXT, named by the project's victim lines. A TDR curve is labelled by its rise time and its resolution length ("125 ps, 9.4 mm"), an |S| curve by its symbol, after the curve's name when there are two curves. Under `title`, then I_SI_RELATIVE, then `label` when given; the rendered si_limits, one a line, at the foot (fig.supxlabel, as draw_antenna). Returns the axes, the TDR's first." Axis labels: I_PLOT_DISTANCE, I_PLOT_TIME, I_PLOT_IMPEDANCE, I_PLOT_FREQUENCY (v1's); the band's legend I_PLOT_TARGET; the |S| axis "|S| (dB)".
  - **`si_png(curves, project, title, label=None)`:** draw_si on `Figure(figsize=(15, 4.5), layout="constrained")` (matplotlib imported here only, C-5), PNG at 100 dpi, as summary_png.
- [ ] **Step 4: The run's outputs.**
  - **`above_dc(f)`,** in `core/post/chain.py`: docstring "The grid `f` (Hz) a part port's load is evaluated on (Stage 4 design 5.6): an SI run's uniform grid with its DC point replaced by its first point above DC, so that each load holds that value at DC; `f` itself on a grid that does not start at DC, v1's and an antenna's." Body `return np.r_[f[1], f[1:]] if f[0] == 0 else f`. Mark `# ponytail: a load holds at DC its value at the first point above DC: a series capacitor's time constant lies beyond the TDR's 200 ns record and an open part has no impedance at DC; a DC error δ moves a TDR level only by a ramp of δ·(t + 4·t_r)/200 ns, and verify's |ΔS| starts above DC; an S2P file must reach that point (5 MHz), E_S2P_BAND naming it`.
  - **`part_impedances`:** `bypasses=antenna(project) or si(project)` (an SI part's `open` and 0R, Stage 4 design 5.1); `chain.py` imports `si`; the docstring says so.
  - **`layout`:** the SI marker is `int(np.abs(f - f0).argmin())`, the point of `f` nearest the marker on any grid (240 MHz is index 48, 133 MHz index 27 and 62.5 MHz index 12 on the uniform grid, as before); the docstring says so. This closes plan 2's carried item on the marker.
  - **`rule.py`:** the comment `# ponytail: d fills only where the caller says; staircased (45°) copper has no axis edge, so plan 2 passes its spans too or keeps the d fill` becomes `# ponytail: d fills only where the caller says; build_mesh spans an SI project's solid rods and staircased copper, so a pad off the lines and its antipad grade to max_cell` (plan 2's carried item).
  - **`chain_results`:** `basis_lines(results, default_gates(project))`; `fz = above_dc(lay.f)`, which `part_impedances` and `loads` take in place of `lay.f` (on v1's and an antenna's grids `fz` is `lay.f`); after `terminate`, an SI project adds `indicator_lines(lay.f, lay.a_db, lay.s, None, None)` alone, before the P = 2 branch (no ideal schematic, loss budget or W_NOT_TWO_PORT); v1's and the antenna's branches as they are. The docstring says so.
  - **`write_outputs`:** the `si_outputs` branch and `si_outputs` itself go. After `res`, the layout file, the label and the chain file as today, `lines = [*res.lines]`; then, for an SI project with a chain, `reading = read(res.chain, lay.f, project, results["route"]["eeff"])`, `lines += si_lines(project, reading, results["route"])` and the files `si_summary.csv` (si_csv), `si_tdr.csv` (tdr_csv) and `si_summary.png` (si_png of `[(path.absolute().parent.name, reading)]` under `render("I_PLOT_SI_TITLE", name=...)`, with `label`); v1's summary.csv and summary.png only when `not si(project)` and P = 2; then the label's line, `write` with SI_OUTPUTS for an SI project, else OUTPUTS, I_OUTPUTS, and `si_limits(project)` in LIMITS' place; pipeline imports read, si_lines, si_limits, si_csv, tdr_csv, si_png and SI_OUTPUTS from core.post.si, and `above_dc` from core.post.chain. The docstrings of `write_outputs` and `run` name the SI branch (Stage 4 design 5.6) in place of si_outputs; v1's lines and files are unchanged, as the golden pins prove.
- [ ] **Step 5: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_PLOT_SI_TITLE | {name}: signal integrity, relative results | {name}: integridade de sinal, resultados relativos |
| I_PLOT_DISTANCE | Distance along the route (mm) | Distância ao longo da rota (mm) |
| I_PLOT_TIME | Round-trip time (ps) | Tempo de ida e volta (ps) |
| I_PLOT_IMPEDANCE | Impedance (Ω) | Impedância (Ω) |
| I_PLOT_TARGET | target band | faixa alvo |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_run.py tests/test_retune.py tests/test_post_chain.py tests/test_match_antenna.py tests/test_post_outputs.py tests/test_post_waves.py tests/test_mesh_rule.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(outputs): an SI run and retune write layout and chain Touchstone files, the S at the target and the TDRs as CSVs and a summary PNG with the relative label and the limits, each part port's load held at DC from the first point above it; write_outputs carries SI as it carries v1 (Stage 4 design 5.6, 5.12 item 3)"
graphify update .
```

---

### Task 5 [code]: The SI retune

**Files:** Modify `pipeline.py` (`retune` L1094-1124, `assign` L1049-1091, its imports); `core/model/parts.py` (`project_parts` L113-115 and L148-149); `cli.py` (`new_si`'s I_CHAIN notes at L384, `notes += [*(("I_CHAIN"`); `core/messages.py`, `po/pt_BR.po` and the `.mo`. Test: `tests/test_si_run.py` (`test_an_si_run_writes_its_layout_on_the_grid_from_dc`'s E_RETUNE_SI block goes, deliberately), `tests/test_si_lines.py`, `tests/test_cli_si.py`.

**Interfaces:**
- Consumes: Task 4's outputs and `above_dc`; `chain_of`, `bypass`, `with_box`, `z_part`, `s2p_impedance`, `networks.write_s2p`.
- Produces: `retune` takes part values and S2P files on an SI project; `assign` reads an SI project's bypasses with the antenna's refusals; a DNP pull-up is stored `open` and left out of I_SI_SHUNT_OPEN; `new_si`'s I_CHAIN lists each measured line's traced parts.

- [ ] **Step 1: Write the failing tests.** In `tests/test_si_run.py` (imports gain `from kicad_rf_studio.core.post.chain import s2p_impedance, z_part`, `from kicad_rf_studio.core.project import parts`, `render` from core.messages, `C_BOX` and `write_s2p` from networks, and `si_dict` from test_project). The plan-2 test's lines from `with pytest.raises(KrsError) as e:  # a part value would be stored` to its assertion on E_RETUNE_SI go. Add:

```python
def test_an_si_retune_closes_the_part_ports_at_their_new_values(tmp_path, calibrated, monkeypatch):  # design 5.7
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    lines, seen = [], []
    monkeypatch.setattr(pipeline, "si_png", lambda curves, project, title, label=None: seen.append(label) or b"")
    assert pipeline.retune(pj, ["R1=33", "R2=33"], lambda code, params: lines.append((code, params))) == 0
    p = load_project(pj)
    assert [(ref, q["value"]) for ref, q in parts(p).items() if ref[0] == "R"] == [("R1", "33"), ("R2", "33")]
    f, model = uniform_grid(10e9), parts(p)["R1"]["model"]
    z = with_box(z_part("R", 33.0, model, f[1:]), f[1:], C_BOX)
    oracle = terminate_np(star(f, 8), list(range(6)), np.stack([np.r_[z[:1], z]] * 2, -1))
    assert np.abs(read_s(pj.parent / "results" / "chain.s6p") - oracle).max() <= 1e-5
    verify = {"command": pipeline.command_line("kicad-rf-studio", "verify", str(pj))}
    assert ("I_WHAT_IF", verify) in lines and seen == [render("I_WHAT_IF", **verify)]  # the PNG's label too
    assert [code for code, _ in lines][-6:] == list(si_limits(p))


def test_an_si_retune_takes_an_s2p_file_from_the_first_point_above_dc(tmp_path, calibrated, monkeypatch):  # 5.7; RF 1
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    fs, late = np.linspace(1e6, 20e9, 2000), np.linspace(10e6, 20e9, 2000)
    c = write_s2p(tmp_path / "c.s2p", 1 / (2j * np.pi * fs * 100e-9), "series", fs)  # an AC-coupling capacitor's data
    write_s2p(tmp_path / "late.s2p", 1 / (2j * np.pi * late * 100e-9), "series", late)
    assert pipeline.retune(pj, [f"R1={c}:series"]) == 0
    f = uniform_grid(10e9)
    zk = np.stack([with_box(z, f[1:], C_BOX) for z in (s2p_impedance(c, "series", "R1", f[1:])[0],
                                                        z_part("R", 22.0, parts(load_project(pj))["R2"]["model"],
                                                               f[1:]))], -1)
    oracle = terminate_np(star(f, 8), list(range(6)), np.vstack([zk[:1], zk]))  # the file's 5 MHz point held to DC
    assert np.abs(read_s(pj.parent / "results" / "chain.s6p") - oracle).max() <= 1e-5
    with pytest.raises(KrsError) as e:  # a file must reach the grid's first point above DC
        pipeline.retune(pj, [f"R1={tmp_path / 'late.s2p'}:series"])
    assert (e.value.code, e.value.params["f1"], e.value.params["f_lo"]) == ("E_S2P_BAND", "5.0", "10.0")


def test_an_si_retune_takes_the_bypasses_and_their_refusals(tmp_path):  # design 5.7, A-33's rules; Review Focus 5
    def port(ref, nets, **kw):
        return {"ref": ref, "pads": [f"{ref}.1", f"{ref}.2"], "nets": nets, "value": "22", "dnp": False,
                "role": "port", "model": None, "s2p": None, **kw}

    d = si_dict()
    d["lines"][0]["chain"]["series"] = [port("R1", ["USB_D+", "MCU_D+"])]
    d["lines"][0]["chain"]["shunt"] = [port("R7", ["USB_D+", "GND"]),
                                       port("R5", ["USB_D+", "+3V3"], value="1.5k", role="open")]  # a pull-up
    d["lines"][1]["chain"]["shunt"] = [port("R9", ["USB_D-", "USB_D+"])]  # across the pair: both nets measured
    new = pipeline.assign(d, ["R1=0R", "R7=open", "R9=0R"], tmp_path)
    assert {ref: q["value"] for ref, q in parts(new).items()} == {"R1": "0R", "R7": "open", "R5": "1.5k", "R9": "0R"}
    for arg, code, params in [("R1=open", "E_RETUNE_OPEN_SERIES", {"ref": "R1"}),
                              ("R7=0R", "E_RETUNE_SHORT_SHUNT", {"ref": "R7", "net": "GND"}),
                              ("R1=abc", "E_RETUNE_ANTENNA_VALUE", {"ref": "R1", "value": "abc"}),
                              ("R5=2.2k", "E_RETUNE_ROLE", {"ref": "R5", "role": "open"})]:
        with pytest.raises(KrsError) as e:
            pipeline.assign(d, [arg], tmp_path)
        assert (e.value.code, e.value.params) == (code, params)
```

  In `tests/test_si_lines.py`:

```python
def test_a_dnp_pull_up_is_open_at_open_and_not_listed(mini_board):  # Stage 4 plan 2's minor; Review Focus 5
    r = "Resistor_SMD:R_0402_1005Metric"
    b = mini_board(part("J1", smd(1, "A")) + part("U1", smd(1, "B"), at="20 0") + two("R1", "A", "B") +
                   fp("R5", r, smd(1, "A"), smd(2, "+3V3", x=2), value="1.5k") +
                   fp("R8", r, "(attr smd dnp) ", smd(1, "A"), smd(2, "+3V3", x=2), value="10k"))
    c = classify(b)
    _, shunt, _, notes = project_parts(b, trace_line(b, c, "J1.1", "U1.1"), c, box(-50, -50, 50, 50), 0.0, 10e9,
                                       si=True)
    assert [(q["ref"], q["role"], q["value"]) for q in shunt] == [("R5", "open", "1.5k"), ("R8", "open", "open")]
    assert ("I_SI_SHUNT_OPEN", {"refs": "R5"}) in notes  # a DNP part is open as any DNP part is, not as a pull-up
```

  In `tests/test_cli_si.py`, `test_a_part_on_both_legs_is_stored_once` keeps `notes` (`pj, notes = cli.new_si(...)`) and adds `assert [p["shunt"] for code, p in notes if code == "I_CHAIN"] == ["R9", "R9"]` (plan 2's minor: each line lists its own parts).
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_si_run.py::test_an_si_retune_closes_the_part_ports_at_their_new_values tests/test_si_run.py::test_an_si_retune_takes_an_s2p_file_from_the_first_point_above_dc tests/test_si_run.py::test_an_si_retune_takes_the_bypasses_and_their_refusals tests/test_si_lines.py::test_a_dnp_pull_up_is_open_at_open_and_not_listed tests/test_cli_si.py::test_a_part_on_both_legs_is_stored_once -q`. Expected: FAIL: E_RETUNE_SI for both retunes, E_RETUNE_VALUE on `R7=open`, R8's value `10k`, and one I_CHAIN with R9.
- [ ] **Step 3: The retune.**
  - **`retune`:** the `if si(project) and assignments:` guard goes; the docstring drops E_RETUNE_SI and says an SI project's retune redraws its TDRs, mixed-mode S and crosstalk from the closed N-port, an S2P file read from the grid's first point above DC (Stage 4 design 5.7).
  - **`assign`:** the bypass branch reads `(antenna(new) or si(new))`, and its two refusals read the lines merged: `chain = chain_of(new)`; E_RETUNE_SHORT_SHUNT when `z == 0`, `ref in {q.ref for q in chain.shunt}` and `not set(part["nets"]) <= set(chain.nets)`; E_RETUNE_OPEN_SERIES when `z == math.inf` and `ref in {q.ref for q in chain.series}`. E_RETUNE_ANTENNA_VALUE stands for E_RETUNE_VALUE on an SI project too. `pipeline` imports `chain_of` from core.geometry. The docstring adds the SI project (Stage 4 design 5.7). The antenna's behaviour is unchanged: `chain_of` of an antenna project is its chain.
  - **`project_parts`:** a pull-up's value is `OPEN_VALUE if fp.dnp else fp.value`, and I_SI_SHUNT_OPEN lists the open shunts that are not DNP; the docstring says so.
  - **`new_si`:** I_CHAIN of each measured line lists that line's traced parts (`x.series`, `x.shunt` of its `trace_line` Chain), so a part on both legs is listed under both, stored once.
- [ ] **Step 4: The messages.** E_RETUNE_SI leaves CATALOG (its pair goes obsolete). Three msgids change deliberately, each through the catalog tool, their old pairs obsolete:

| Code | English | pt-BR |
|---|---|---|
| E_RETUNE_SHORT_SHUNT | {ref} joins the chain to {net}: 0 Ω there would short the chain to {net}. \`{ref}=0R\` replaces a series part with a short; \`{ref}=open\` removes a part like this one. | {ref} liga a cadeia a {net}: 0 Ω ali poria a cadeia em curto com {net}. \`{ref}=0R\` troca um componente em série por um curto; \`{ref}=open\` retira um componente como este. |
| E_RETUNE_OPEN_SERIES | {ref} is a series part of the chain: open there would cut it, an antenna off its feed or a line in two. \`{ref}=0R\` replaces it with a short; \`open\` removes a shunt part. | {ref} é um componente em série da cadeia: em aberto ali, ele a cortaria, separando uma antena da alimentação ou uma linha em duas. \`{ref}=0R\` o troca por um curto; \`open\` retira um componente shunt. |
| E_RETUNE_ANTENNA_VALUE | Cannot read "{value}" as the value of {ref}: on an antenna's chain or a signal-integrity line, a C, L or R takes a value in its own unit (4.7pF, 4p7, 15nH, 50R), \`{ref}=0R\` replaces a series part with a short and \`{ref}=open\` removes a shunt part (a C of 0 F could mean either, so it is refused), and any part takes an S2P file as {ref}=file.s2p:series (or :shunt). | Não foi possível ler "{value}" como o valor de {ref}: na cadeia de uma antena ou numa linha de integridade de sinal, um C, L ou R recebe um valor na própria unidade (4.7pF, 4p7, 15nH, 50R), \`{ref}=0R\` troca um componente em série por um curto e \`{ref}=open\` retira um componente shunt (um C de 0 F poderia ser qualquer um dos dois, então é recusado), e qualquer componente recebe um arquivo S2P como {ref}=file.s2p:series (ou :shunt). |

- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_retune.py tests/test_match_antenna.py tests/test_si_lines.py tests/test_cli_si.py tests/test_gui_control.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(retune): an SI project's retune closes its part ports at new values or S2P files, 0R and open with the antenna's refusals on the lines merged, a DNP pull-up stored open, and new lists each line's own parts (Stage 4 design 5.7)"
graphify update .
```

---

### Task 6 [code]: The SI verify

**Files:** Modify `core/post/si.py` (`compare_verify`); `core/model/spec.py` (`verify_spec` L356-403); `pipeline.py` (`verify` L1204-1235, `_verify` L1238-1312); `core/messages.py`, `po/pt_BR.po` and the `.mo`. Test: `tests/test_post_si.py`, `tests/test_si_run.py` (`test_verify_waits_for_the_si_results_and_preview_takes_an_si_project` changes deliberately: see Step 1).

**Interfaces:**
- Consumes: Tasks 1–5; `test_verify`'s recipe (the dump stood in for, the cell C at 6e-16 F).
- Produces:
  - `si.compare_verify(own: Reading, retuned: Reading) -> dict`, `{"ds_max": float, "f_hz": float, "levels": [[own lowest Z, retuned's, short], [own highest Z, retuned's, short]] | None}`, short when either reading marks that level short.
  - `verify_spec(spec, parts, dump, dt, *, far_field=None, bypasses=False)`: a bypass leaves the grid with `bypasses` or a far-field box.
  - `verify` on an SI project; an SI project's verify block adds `"fingerprint"`.
  - In `tests/test_si_run.py`: `verified_si(tmp_path, monkeypatch, board=USB) -> Path`, which Task 7 imports.

- [ ] **Step 1: Write the failing tests.** In `tests/test_post_si.py` (imports gain `compare_verify`):

```python
def test_verifys_comparison_keeps_the_short_mark():  # design 5.7; anti-goal 2; Review Focus 3
    n = read(line_s(ROUTE1, F), F, SE, 4.0)
    m = read(line_s([(50.0, 4.0, 15.0), (61.0, 4.0, 30.0), (50.0, 4.0, 15.0), (40.0, 4.0, 3.0), (50.0, 4.0, 15.0)], F),
             F, SE, 4.0)  # the 60 Ω section at 61 Ω
    cmp = compare_verify(n, m)
    assert (round(cmp["ds_max"], 4), cmp["f_hz"]) == (0.0169, 8.705e9)  # from the first point above DC
    assert [(round(a, 2), round(b, 2), short) for a, b, short in cmp["levels"]] == [(46.68, 46.71, True),
                                                                                  (60.0, 61.0, False)]
    assert compare_verify(n, read(np.zeros((len(F), 2, 2), complex), F, SE, 4.0))["levels"] is None
```

  In `tests/test_si_run.py` (imports gain `from kicad_rf_studio.core.model import spec as spec_module`, `from kicad_rf_studio.core.model.spec import verify_spec`). `test_verify_waits_for_the_si_results_and_preview_takes_an_si_project`'s first refusal expects `("E_NO_RESULTS", {})` (no run yet), not E_VERIFY_SI. Add:

```python
def verified_si(tmp_path, monkeypatch, board=USB):
    """An SI fixture run on the network fake, its run's operator dump stood in for and the cell C read as 6e-16 F
    (test_verify.verified's), so that verify runs: the project file."""
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / board.stem, board)
    assert pipeline.run(pj) == 0
    (Path(load_project(pj)["results"]["run_dir"]) / "job-0-setup" / "operator_dump.vtr").write_bytes(b"")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    return pj


def test_verify_puts_an_si_lines_parts_in_the_grid_and_compares(tmp_path, calibrated, monkeypatch):  # 5.7; RF 1, 2
    pj = verified_si(tmp_path, monkeypatch)
    before = load_project(pj)["results"]
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)  # no division by zero at DC
        assert pipeline.verify(pj) == 0
    d = load_project(pj)
    v = d["verify"]
    assert d["results"] == before and set(v) == {"model_hash", "base_hash", "values", "run_dir", "jobs", "compare",
                                                 "fingerprint"}
    assert v["values"] == {"R1": "22", "R2": "22"} and v["fingerprint"] == before["fingerprint"]
    assert [j["port"] for j in v["jobs"]] == ["P1", "P2", "P3", "P4", "P5", "P6"]
    # star(f, 6) against star(f, 8) closed by 22 Ω ∥ C_BOX; the star's pair passes no differential step
    assert v["compare"] == {"ds_max": pytest.approx(0.12326, abs=1e-4), "f_hz": 10e9, "levels": None}
    model = json.loads((Path(v["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    assert [g["name"] for g in model["grid"]] == ["R1", "R2"]
    assert "verify.s6p" in {f.name for f in (pj.parent / "results").iterdir()}
    codes = result_codes(v["run_dir"])
    k = codes.index("I_VERIFY_COMPARE_SI")
    assert codes[:2] == ["I_VERIFY_RESULTS", "I_SI_RELATIVE"] and codes[k + 1] == "I_VERIFY_NO_LEVELS"
    assert codes[-7:] == ["I_VERIFY_SCOPE_SI", *si_limits(d)]


def test_verify_of_a_net_compares_its_tdr_levels(tmp_path, calibrated, monkeypatch):  # design 5.7
    pj = verified_si(tmp_path, monkeypatch, QSPI)
    assert pipeline.verify(pj) == 0
    d = load_project(pj)
    (low_v, low_r, low_s), (high_v, high_r, high_s) = d["verify"]["compare"]["levels"]
    # verify's own S is star(f, 2) back from the fake's waves, within 2e-6: matched, its levels 50 Ω to 1.6e-6
    assert (low_v, high_v) == (pytest.approx(50.0, abs=1e-4), pytest.approx(50.0, abs=1e-4))
    assert not (low_s or high_s)
    assert [p for c, p in result_lines(d["verify"]["run_dir"]) if c == "I_VERIFY_LEVEL"] == [
        {"level": "T_LOWEST", "verify": f"{low_v:.2f}", "retune": f"{low_r:.2f}"},
        {"level": "T_HIGHEST", "verify": f"{high_v:.2f}", "retune": f"{high_r:.2f}"}]


def test_verify_spec_puts_an_si_bypass_as_copper_or_leaves_it_out(tmp_path, monkeypatch):  # 5.7, A-33's rule
    project, board, geom, _ = pipeline.load(si_project(tmp_path))
    spec = pipeline.build_model(project, board, geom).spec
    by_ref = parts(project)
    by_ref["R1"]["value"], by_ref["R2"]["value"] = "0R", "open"
    dump = tmp_path / "operator_dump.vtr"
    dump.write_bytes(b"")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    out = verify_spec(spec, by_ref, dump, 1e-13, bypasses=True)
    assert out["grid"] == [] and len(out["metal"]["copper"]) == len(spec["metal"]["copper"]) + 1
    with pytest.raises(KrsError) as e:  # without it, v1's: R1 an R of 0 Ω, then R2's open refused
        verify_spec(spec, by_ref, dump, 1e-13)
    assert (e.value.code, e.value.params) == ("E_VERIFY_VALUE", {"ref": "R2", "value": "open"})
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_si.py::test_verifys_comparison_keeps_the_short_mark tests/test_si_run.py::test_verify_puts_an_si_lines_parts_in_the_grid_and_compares tests/test_si_run.py::test_verify_of_a_net_compares_its_tdr_levels tests/test_si_run.py::test_verify_spec_puts_an_si_bypass_as_copper_or_leaves_it_out tests/test_si_run.py::test_verify_waits_for_the_si_results_and_preview_takes_an_si_project -q`. Expected: FAIL with `cannot import name 'compare_verify'`, E_VERIFY_SI and `TypeError: ... 'bypasses'`.
- [ ] **Step 3: `compare_verify` and `verify_spec`.**
  - **`compare_verify(own, retuned)`:** "verify's comparison of an SI project (Stage 4 design 5.7), in plain floats: the largest |ΔS| of own.s against retuned.s over every entry and over f from the first point above DC (the retune's DC point is its 5 MHz load held there, verify's the FDTD's own), and the f where it lies; and the TDR's levels, [[own lowest Z, retuned's, short], [own highest Z, retuned's, short]], short when either marks that level short, None when either reads none."
  - **`verify_spec`:** keyword `bypasses: bool = False`; the bypass branch runs `if (bypasses or far_field is not None) and ...`; the docstring adds "and an SI project's (`bypasses`, Stage 4 design 5.7)". The antenna's and v1's calls are unchanged, so their verify models are, as golden_antenna's pi verify pin proves.
- [ ] **Step 4: `verify` and `_verify`.**
  - **`verify`:** the E_VERIFY_SI guard goes; the docstring says an SI project's verify is v1's with SI's comparison (Stage 4 design 5.7).
  - **`_verify`,** for an SI project:
    1. the ideal loads as chain_results' (Task 4): `fz = above_dc(lay.f)`, `z_value(..., fz, bypasses=ant or si(project))` and `loads(..., fz)` (v1's `fz` is `lay.f`);
    2. `verify_spec(..., bypasses=si(project))`; `fp = fingerprint(project) if ant or si(project) else None`;
    3. after the jobs, `retuned = terminate(lay.s, ext, zk, lay.f)`; `mine = read(own.s, own.f, project, results["route"]["eeff"])`; `cmp = compare_verify(mine, read(retuned, lay.f, project, results["route"]["eeff"]))` in place of v1's `compare`;
    4. an SI project's verify block gains `"fingerprint": fp`; v1's keeps its six keys (`tests/test_verify.py` pins them);
    5. the lines, in place of v1's I_VERIFY_COMPARE and nulls: `si_lines(project, mine, results["route"])`, then I_VERIFY_COMPARE_SI `{ds_max (:.4f), f_mhz (:g of f_hz in MHz), a_db (:.1f, own.a_db at the grid point of f_hz)}`, then per level I_VERIFY_LEVEL `{level (T_LOWEST, T_HIGHEST), verify, retune}` (each `:.2f`), or I_VERIFY_LEVEL_SHORT with the same parameters when that level is short, or one I_VERIFY_NO_LEVELS; the indicator lines with no loss budget; the E_ lines; I_OUTPUTS; I_VERIFY_SCOPE_SI and `si_limits(project)` in I_VERIFY_SCOPE's and LIMITS' place.
  - v1's lines and files are unchanged; the docstring names the SI branch.
- [ ] **Step 5: The messages,** each through the catalog tool; E_VERIFY_SI leaves CATALOG (its pair goes obsolete):

| Code | English | pt-BR |
|---|---|---|
| I_VERIFY_COMPARE_SI | verify against the retune at the same ideal values: max \|ΔS\| {ds_max} from the first point above DC to f_max, at {f_mhz} MHz (\|a\| {a_db} dB). | Verificação contra o ajuste com os mesmos valores ideais: \|ΔS\| máximo de {ds_max} do primeiro ponto acima de DC até f_max, em {f_mhz} MHz (\|a\| {a_db} dB). |
| I_VERIFY_LEVEL | The {level} TDR level between the launches, verify against the retune: {verify} Ω against {retune} Ω. | O nível {level} do TDR entre as entradas, verificação contra o ajuste: {verify} Ω contra {retune} Ω. |
| I_VERIFY_LEVEL_SHORT | The {level} TDR level between the launches, verify against the retune: {verify} Ω against {retune} Ω; one of them lies on a feature shorter than two resolution lengths, so it is not that feature's impedance. | O nível {level} do TDR entre as entradas, verificação contra o ajuste: {verify} Ω contra {retune} Ω; um deles fica num trecho mais curto que dois comprimentos de resolução, então não é a impedância desse trecho. |
| I_VERIFY_NO_LEVELS | The TDR's levels are not compared: verify or the retune reads none between the launches. | Os níveis do TDR não são comparados: a verificação ou o ajuste não lê nenhum entre as entradas. |
| I_VERIFY_SCOPE_SI | verify checks the layout reduction, not the vendor part data: each part sat in the grid at its value as an ideal part, without the package ESL, ESR and Cp or the S2P data the retune applies, a 0 Ω part as copper and an open part left out, against a retune at the same ideal values, whose loads hold at DC their value at the grid's first point above DC. | A verificação confere a redução do layout, não os dados de componente do fabricante: cada componente ficou na grade com o valor dele como componente ideal, sem o ESL, o ESR e o Cp do encapsulamento nem os dados S2P que o ajuste aplica, um componente de 0 Ω como cobre e um em aberto deixado de fora, contra um ajuste com os mesmos valores ideais, cujas cargas mantêm em DC o valor do primeiro ponto da grade acima de DC. |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_verify.py tests/test_antenna_model.py tests/test_match_antenna.py tests/test_model_spec.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(verify): an SI project's verify puts its line parts in the grid at their ideal values, a bypass as copper or left out, and compares the largest |dS| above DC and the TDR's levels, short ones marked, with the retune at the same values, recording its settings fingerprint (Stage 4 design 5.7)"
graphify update .
```

---

### Task 7 [code]: `compare` for two SI projects

**Files:** Modify `core/post/si.py` (the thresholds, `si_deltas`, `si_delta_lines`); `pipeline.py` (`_full_record` and `si_result` beside `antenna_result` L1127-1164, which builds on `_full_record`; `compare_projects` L1167-1201; the module docstring L6-7); `cli.py` (the module docstring L11); `core/messages.py`, `po/pt_BR.po` and the `.mo`. Create `tests/test_si_compare.py`. Test: `tests/test_si_run.py` (`test_verify_waits_for_the_si_results_and_preview_takes_an_si_project`'s compare refusal changes deliberately).

**Interfaces:**
- Consumes: Tasks 1–6; `antenna.DELTA_COLUMNS`, `antenna.deltas_csv`; `test_compare.twin`, `test_compare.compared`, `test_cli_antenna.antenna_project`; `test_si_run.verified_si`.
- Produces:
  - In `core/post/si.py`: `IL_DB, DB, LEVEL_FLOOR_DB, SKEW_PS = 0.05, 0.5, -50.0, 1.0`; `si_deltas(project: dict, base: Reading, variant: Reading) -> list[dict]`, rows of DELTA_COLUMNS; `si_delta_lines(project: dict, rows: list[dict]) -> list[tuple[str, dict]]`.
  - In `pipeline.py`: `_full_record(path: Path) -> tuple[dict, dict, Layout, str]`; `si_result(path: Path) -> dict`, `{"path", "project", "reading", "fingerprint", "source", "run_dir"}`; `compare_projects` on two SI projects.

- [ ] **Step 1: Write the failing tests,** `tests/test_si_compare.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import math

import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.antenna import DELTA_COLUMNS, deltas_csv
from kicad_rf_studio.core.post.si import read, si_delta_lines, si_deltas, si_limits
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_antenna import antenna_project
from test_cli_si import si_project
from test_compare import compared, twin
from test_post_si import F, P100, P2V, ROUTE1, SE, line_s, pair6, pair8
from test_si_run import verified_si

A = math.sqrt(2)  # pair6's coupling to P alone reads 3 dB down, driven differentially


def test_the_si_deltas_and_their_significance():  # design 5.8; Review Focus 2
    b = read(pair6(A * 10 ** (-60 / 20), A * 10 ** (-70 / 20)), F, P100, 3.0)
    v = read(pair6(A * 10 ** (-45 / 20), A * 10 ** (-60 / 20), 0.2e-9 + 1.5e-12), F, P100, 3.0)
    rows = si_deltas(P100, b, v)
    assert [(r["quantity"], r["marker"], r["threshold"], r["resolved"]) for r in rows] == [
        ("tdr_lowest", "", 1.0, False), ("tdr_highest", "", 1.0, False), ("sdd21", "marker", 0.05, False),
        ("sdd21", "f_max", 0.05, False), ("sdd11_worst", "", 0.5, False), ("scd21_worst", "", 0.5, True),
        ("skew", "", 1.0, True), ("next", "AUX", 0.5, True), ("fext", "AUX", 0.5, False)]  # FEXT: both under -50 dB
    assert rows[6]["delta"] == pytest.approx(1.498, abs=0.005) and rows[8]["delta"] == pytest.approx(10.0)
    assert (rows[2]["f_hz"], rows[3]["f_hz"], rows[2]["unit"], rows[6]["unit"]) == (240e6, 10e9, "dB", "ps")
    short = read(line_s([(50.0, 4.0, 5.0)], F), F, SE, 4.0)  # no level: the TDR rows hold none
    assert [r["resolved"] for r in si_deltas(SE, short, short)[:2]] == [None, None]
    two = read(pair8(), F, P2V, 3.0)  # each victim its rows, by its first net
    assert [(r["quantity"], r["marker"]) for r in si_deltas(P2V, two, two)[-4:]] == [
        ("next", "AUX"), ("fext", "AUX"), ("next", "AUX2"), ("fext", "AUX2")]


def test_the_deltas_of_a_net():  # design 5.8; anti-goal 2; Review Focus 3, 5
    n = read(line_s(ROUTE1, F), F, SE, 4.0)
    rows = si_deltas(SE, n, n)
    assert [(r["quantity"], r["marker"], r["threshold"]) for r in rows] == [
        ("tdr_lowest", "short", 0.5), ("tdr_highest", "", 0.5), ("s21", "marker", 0.05), ("s21", "f_max", 0.05),
        ("s11_worst", "", 0.5)]  # the 3 mm bump's level: marked in compare.csv
    assert {r["resolved"] for r in rows} == {False}
    assert [code for code, _ in si_delta_lines(SE, rows)][:2] == ["I_SI_COMPARE_LEVEL_SHORT", "I_SI_COMPARE_LEVEL"]


def test_the_si_delta_lines_and_csv():  # design 5.8
    b = read(pair6(A * 10 ** (-60 / 20), A * 10 ** (-70 / 20)), F, P100, 3.0)
    v = read(pair6(A * 10 ** (-45 / 20), A * 10 ** (-60 / 20), 0.2e-9 + 1.5e-12), F, P100, 3.0)
    rows = si_deltas(P100, b, v)
    lines = si_delta_lines(P100, rows)
    assert [code for code, _ in lines] == [
        "I_SI_COMPARE_LEVEL", "I_SI_COMPARE_LEVEL", "I_SI_COMPARE_INSERTION", "I_SI_COMPARE_INSERTION",
        "I_SI_COMPARE_WORST", "I_SI_COMPARE_WORST", "I_SI_COMPARE_SKEW", "I_SI_COMPARE_XT", "I_SI_COMPARE_XT",
        "I_SI_COMPARE_THRESHOLDS"]
    assert lines[6][1] == {"base": "+0.00", "variant": "+1.50", "delta": "+1.50", "verdict": "T_RESOLVED"}
    assert lines[7][1] == {"kind": "NEXT", "net": "AUX", "base": "-60.00", "variant": "-45.00", "delta": "+15.00",
                           "verdict": "T_RESOLVED"}
    assert lines[-1][1] == {"ohm": "1", "il_db": "0.05", "db": "0.5", "floor_db": "-50", "ps": "1"}
    short = read(line_s([(50.0, 4.0, 5.0)], F), F, SE, 4.0)
    assert [code for code, _ in si_delta_lines(SE, si_deltas(SE, short, short))][0] == "I_SI_COMPARE_NO_LEVELS"
    table = list(csv.reader(io.StringIO(deltas_csv(rows).decode())))
    assert table[0] == list(DELTA_COLUMNS) and len(table) == 10


def test_compare_two_si_projects_through_their_verifies(tmp_path, calibrated, monkeypatch):  # 5.8, 5.14
    a = verified_si(tmp_path, monkeypatch)
    assert pipeline.verify(a) == 0
    b, run_dir = twin(a, tmp_path / "b"), load_project(a)["verify"]["run_dir"]
    lines = compared(a, b, tmp_path / "out")
    codes = [code for code, _ in lines]
    assert lines[:3] == [("I_SI_RELATIVE", {}),
                         ("I_COMPARE_BASIS", {"role": "T_BASE", "path": str(a), "source": "T_VERIFY",
                                              "run_dir": run_dir}),
                         ("I_COMPARE_BASIS", {"role": "T_VARIANT", "path": str(b), "source": "T_VERIFY",
                                              "run_dir": run_dir})]
    assert "I_SI_COMPARE_NO_LEVELS" in codes
    assert {p["verdict"] for _, p in lines if "verdict" in p} == {"T_NOT_RESOLVED"}
    assert codes[-7:] == ["I_OUTPUTS", *si_limits(load_project(a))]
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["compare.csv", "compare.png"]


def test_compare_refuses_si_projects_it_cannot_compare(tmp_path, calibrated, monkeypatch):  # 5.8; Review Focus 4
    a = verified_si(tmp_path, monkeypatch)
    assert pipeline.verify(a) == 0
    b, old = twin(a, tmp_path / "b"), twin(a, tmp_path / "old")
    d = load_project(b)
    d["verify"]["fingerprint"] = {**d["verify"]["fingerprint"], "ends": ["J1.3", "J1.2", "U1.3", "U1.2"],
                                  "target_ohm": 85.0}  # no victim, another target
    save_project(b, d)
    d = load_project(old)
    del d["results"]["route"]  # plan 2's results
    save_project(old, d)
    for variant, code, params in [(b, "E_COMPARE_SETTINGS", {"fields": "ends, target_ohm"}),
                                  (old, "E_COMPARE_NO_RESULT", {"path": str(old)})]:
        with pytest.raises(KrsError) as e:
            pipeline.compare_projects(a, variant, tmp_path / "out")
        assert (e.value.code, e.value.params) == (code, params)
    ant = antenna_project(tmp_path / "ant")

    def board_read(*_):
        raise AssertionError("a board was read")

    with monkeypatch.context() as m:  # each project's kind, before any board is read
        m.setattr(pipeline, "load", board_read)
        for base, variant in ((a, ant), (ant, a)):
            with pytest.raises(KrsError) as e:
                pipeline.compare_projects(base, variant, tmp_path / "out")
            assert (e.value.code, e.value.params) == ("E_COMPARE_KIND", {"path": str(variant)})
    assert not (tmp_path / "out").exists()


def test_compare_reads_a_partless_si_projects_run(tmp_path, calibrated, monkeypatch):  # 5.7, 5.8; Review Focus 5
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    d = load_project(pj)
    for line in d["lines"]:
        for q in line["chain"]["series"]:
            q["role"] = "copper"  # R1 and R2 copper: no part port
    save_project(pj, d)
    assert pipeline.run(pj) == 0
    for call, code in ((lambda: pipeline.retune(pj, ["R1=33"]), "E_RETUNE_NO_PARTS"),
                       (lambda: pipeline.verify(pj), "E_VERIFY_NO_PARTS")):
        with pytest.raises(KrsError) as e:
            call()
        assert (e.value.code, e.value.params) == (code, {})
    lines = compared(pj, twin(pj, tmp_path / "b"), tmp_path / "out")
    assert [p["source"] for code, p in lines if code == "I_COMPARE_BASIS"] == ["T_RUN", "T_RUN"]
```

  In `tests/test_si_run.py`, `test_verify_waits_for_the_si_results_and_preview_takes_an_si_project`'s compare refusal expects `("E_COMPARE_NO_RESULT", {"path": str(pj)})` (no run), not E_COMPARE_KIND.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_si_compare.py "tests/test_si_run.py::test_verify_waits_for_the_si_results_and_preview_takes_an_si_project" -q`. Expected: FAIL with `cannot import name 'si_delta_lines'`.
- [ ] **Step 3: The deltas, in `core/post/si.py`.**
  - **The constants,** commented "design 5.8: the significance thresholds registered before any gate runs; gate P4-E keeps or widens each (plan 4)": `IL_DB, DB, LEVEL_FLOOR_DB, SKEW_PS = 0.05, 0.5, -50.0, 1.0` (DIFF_OHM and SE_OHM are Task 1's).
  - **`si_deltas(project, base, variant)`:** docstring "The deltas of `variant` against `base` (Stage 4 design 5.8), rows of antenna.DELTA_COLUMNS (imported inside) in plain floats (None for no value), delta = variant − base: tdr_lowest and tdr_highest (Ω, DIFF_OHM for a pair, SE_OHM for a net; None when either has no levels; `marker` "short" when either level is short, so compare.csv keeps the mark); sdd21 (a net's s21) at "marker" and at "f_max", with its f_hz (dB, IL_DB); sdd11_worst (s11_worst), and for a pair scd21_worst (dB, DB); for a pair skew (ps, N − P, SKEW_PS; None without both arrivals); and for each victim next and fext, the victim's first net in `marker` (dB, DB). Resolved when |delta| > threshold, and for the DB rows only when the higher of the two levels stands above LEVEL_FLOOR_DB; None when the delta is None." Short features compare too (design 5.6: the same settings filter alike). Mark `# ponytail: antenna.deltas' row, with the floor; one shared helper if a third kind compares`.
  - **`si_delta_lines(project, rows)`:** docstring "compare's lines of si_deltas' rows (design 5.8), each with its verdict, T_RESOLVED or T_NOT_RESOLVED: I_SI_COMPARE_LEVEL per TDR row (level T_LOWEST, T_HIGHEST), I_SI_COMPARE_LEVEL_SHORT when its marker is "short", or one I_SI_COMPARE_NO_LEVELS for both when they hold none; I_SI_COMPARE_INSERTION per sdd21 row (mode Sdd21 or S21, f_mhz); I_SI_COMPARE_WORST (mode Sdd11, S11, Scd21); I_SI_COMPARE_SKEW, or I_SI_COMPARE_NO_SKEW; I_SI_COMPARE_XT (kind NEXT or FEXT, net); then I_SI_COMPARE_THRESHOLDS {ohm, il_db, db, floor_db, ps} (:g, ohm by the project's kind)." Formats: Ω and dB `:.2f`, insertion dB `:.3f`, ps `:+.2f`, each delta signed (`:+`).
- [ ] **Step 4: `compare`.**
  - **`_full_record(path)`:** antenna_result's shared body, moved: load, build_model and results_of (E_COMPARE_NO_RESULT for none or stale); with no part port the run, else current_verify at project.json's values; E_COMPARE_NO_RESULT without one or without a fingerprint; `lay = layout(project, record)`, its E_RESULTS_WAVES as E_COMPARE_NO_RESULT. Returns `(project, record, lay, source)`.
  - **`antenna_result`:** its kind check, `_full_record`, then far_of in its own try (E_RESULTS_WAVES as E_COMPARE_NO_RESULT); its dict and docstring as today.
  - **`si_result(path)`:** `_full_record`; `{"path", "project", "reading": read(lay.s, lay.f, project, project["results"]["route"]["eeff"]), "fingerprint": record["fingerprint"], "source", "run_dir"}`. No kind check of its own: compare_projects, its one caller, checks both kinds first. Its docstring says so, and that verify's layout is its external ports alone, the run's at M = 0 its chain.
  - **`compare_projects`:** first, before any board is read, each project's kind: E_COMPARE_KIND {path} for the first, base then variant, that is not of the base's kind, an antenna or an SI project (the base's own kind checked as the antenna's is today). Then `si_result` or `antenna_result` for both; the fingerprint check as today; for SI, `si_deltas`, compare.png by `si_png` of both readings named by their folders under `render("I_PLOT_SI_COMPARE_TITLE", base=..., variant=...)`, lines I_SI_RELATIVE, the two I_COMPARE_BASIS and `si_delta_lines`, and `si_limits(b["project"])` in ANTENNA_LIMITS' place; compare.csv by `deltas_csv` for both kinds. The docstring names both kinds.
  - **The module docstrings** of `pipeline.py` and `cli.py` say `compare BASE VARIANT` compares two antenna projects' or two signal-integrity projects' full simulations.
- [ ] **Step 5: The messages,** each through the catalog tool; E_COMPARE_KIND's msgid changes deliberately (its old pair obsolete):

| Code | English | pt-BR |
|---|---|---|
| E_COMPARE_KIND | {path} is not of the kind \`compare\` takes here: two antenna projects, made with \`new --antenna\`, or two signal-integrity projects, made with \`new --interface\`. | {path} não é do tipo que \`compare\` recebe aqui: dois projetos de antena, criados com \`new --antenna\`, ou dois projetos de integridade de sinal, criados com \`new --interface\`. |
| I_PLOT_SI_COMPARE_TITLE | {base} against {variant}: signal integrity, relative results | {base} contra {variant}: integridade de sinal, resultados relativos |
| I_SI_COMPARE_LEVEL | The {level} TDR level between the launches: {base} Ω against {variant} Ω, {delta} Ω: {verdict}. | O nível {level} do TDR entre as entradas: {base} Ω contra {variant} Ω, {delta} Ω: {verdict}. |
| I_SI_COMPARE_LEVEL_SHORT | The {level} TDR level between the launches: {base} Ω against {variant} Ω, {delta} Ω: {verdict}; one of them lies on a feature shorter than two resolution lengths, so it is not that feature's impedance, and the delta compares two levels filtered alike. | O nível {level} do TDR entre as entradas: {base} Ω contra {variant} Ω, {delta} Ω: {verdict}; um deles fica num trecho mais curto que dois comprimentos de resolução, então não é a impedância desse trecho, e a diferença compara dois níveis filtrados do mesmo modo. |
| I_SI_COMPARE_NO_LEVELS | The TDR's levels are not compared: one of the projects reads none between the launches. | Os níveis do TDR não são comparados: um dos projetos não lê nenhum entre as entradas. |
| I_SI_COMPARE_INSERTION | {mode} at {f_mhz} MHz: {base} dB against {variant} dB, {delta} dB: {verdict}. | {mode} em {f_mhz} MHz: {base} dB contra {variant} dB, {delta} dB: {verdict}. |
| I_SI_COMPARE_WORST | The worst {mode} up to f_max: {base} dB against {variant} dB, {delta} dB: {verdict}. | O pior {mode} até f_max: {base} dB contra {variant} dB, {delta} dB: {verdict}. |
| I_SI_COMPARE_SKEW | The intra-pair skew: {base} ps against {variant} ps, {delta} ps: {verdict}. | O skew intrapar: {base} ps contra {variant} ps, {delta} ps: {verdict}. |
| I_SI_COMPARE_NO_SKEW | The intra-pair skew is not compared: one of the projects has a leg whose TDT does not arrive. | O skew intrapar não é comparado: um dos projetos tem uma perna cujo TDT não chega. |
| I_SI_COMPARE_XT | {kind} into {net}, its peak: {base} dB against {variant} dB, {delta} dB: {verdict}. | {kind} em {net}, o pico: {base} dB contra {variant} dB, {delta} dB: {verdict}. |
| I_SI_COMPARE_THRESHOLDS | Resolved means larger than the significance threshold: {ohm} Ω on a TDR level, {il_db} dB on Sdd21 or S21, {db} dB on Sdd11, S11, Scd21, NEXT and FEXT where the higher of the two levels stands above {floor_db} dB, and {ps} ps on the skew: the design's registered values until gate P4-E measures the model's noise. | Resolvido significa maior que o limiar de significância: {ohm} Ω num nível do TDR, {il_db} dB em Sdd21 ou S21, {db} dB em Sdd11, S11, Scd21, NEXT e FEXT onde o maior dos dois níveis fica acima de {floor_db} dB, e {ps} ps no skew: os valores registrados no design até a checagem prévia P4-E medir o ruído do modelo. |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_compare.py tests/test_antenna_lines.py tests/test_p3.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_sexpr.py -q`. Expected: PASS; the antenna's compare is unchanged.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(compare): compare BASE VARIANT on two SI projects, each project's run or current verify, the TDRs and mixed-mode S overlaid, the deltas against the design's registered thresholds with -50 dB as the floor and a short level marked, refusing other settings and an antenna against an SI project (Stage 4 design 5.8)"
graphify update .
```

---

### Task 8 [run]: The SI results on the USB 2.0 fixture and its plane-gap variant, the record and the amendments

This task commits the record, the amendments and any fix a failure needs. Everything else it makes stays under `$env:TEMP`. Run each PowerShell block as one call; each starts by naming `$out` and the isolated data folder.

- [ ] **Step 1: The suite at the branch tip.** Run the full suite in the background and wait for it. Then, in one call: `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass. Record the counts.
- [ ] **Step 2: New, cost and run on both boards at the same settings,** in the background, waited on:

```powershell
$out = Join-Path $env:TEMP 'krs-si-results'; New-Item -ItemType Directory -Force $out | Out-Null
$env:LOCALAPPDATA = "$out\data"; $env:XDG_DATA_HOME = "$out\data"  # an isolated data folder: its own calibration
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"  # typed here, never written into a file
Copy-Item tests\fixtures\usb2_hs.kicad_pcb, tests\fixtures\usb2_hs_gap.kicad_pcb $out
$krs = ".venv\Scripts\kicad-rf-studio.exe"
foreach ($n in "usb2_hs", "usb2_hs_gap") {
  & $krs new "$out\$n.kicad_pcb" --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o "$out\$n" *> "$out\$n-new.log"; "$n new $LASTEXITCODE" | Add-Content "$out\codes.txt"
  & $krs cost "$out\$n" *> "$out\$n-cost.log"; "$n cost $LASTEXITCODE" | Add-Content "$out\codes.txt"
  & $krs run "$out\$n" *> "$out\$n-run.log"; "$n run $LASTEXITCODE" | Add-Content "$out\codes.txt"
}
```

  Expected codes: all 0. Expected time: about an hour, two runs of 8 jobs (plan 2's first run took 26 min).
- [ ] **Step 3: The termination sweep, the retune with snapping, Apply, verify and compare,** in the background, waited on. Step 2's `$out`, environment and `$krs` lines come first, without its `Copy-Item`:

```powershell
$v = & .venv\Scripts\python.exe -c "from kicad_rf_studio.gui.control import snapped; print(snapped('R1', '25', 'E24'))"
Remove-Item -Recurse -Force "$out\sweep" -ErrorAction SilentlyContinue; Copy-Item -Recurse "$out\usb2_hs" "$out\sweep"
foreach ($r in "0R", "10", "22", "33", "47") { & $krs retune "$out\sweep" R1=$r R2=$r *> "$out\sweep-$r.log"; "sweep $r $LASTEXITCODE" | Add-Content "$out\codes.txt" }
foreach ($n in "usb2_hs", "usb2_hs_gap") {
  & $krs retune "$out\$n" R1=$v R2=$v *> "$out\$n-retune.log"; "$n retune $LASTEXITCODE" | Add-Content "$out\codes.txt"
  & $krs verify "$out\$n" *> "$out\$n-verify.log"; "$n verify $LASTEXITCODE" | Add-Content "$out\codes.txt"
}
& $krs compare "$out\usb2_hs" "$out\usb2_hs_gap" -o "$out\compare" *> "$out\compare.log"; "compare $LASTEXITCODE" | Add-Content "$out\codes.txt"
```

  - `$v` is the GUI's E24 snapping of a typed 25 Ω (`gui.control.snapped`, which this plan leaves as it is: `24` on `main`), so this is design §5.14's "retune of the series resistors with snapping"; `retune` stores it, the CLI's Apply. The record states `$v`. The sweep runs on a copy, so the applied project keeps one value set.
  - Expected codes: all 0. Expected time: about 40 minutes, two verifies of 6 jobs.
- [ ] **Step 4: Read it, against these pre-registered checks.**
  - **Hard:** a failure gets superpowers:systematic-debugging, and a bug is fixed test-first in its module, then the step again.
    - each run: 8 jobs kept, no E_ line; `results/` holds chain.s6p, layout.s8p, si_summary.csv, si_summary.png and si_tdr.csv; `results.route` and `results.fingerprint` present; I_SI_RELATIVE comes before every I_SI_ line (after the passivity and reciprocity lines, as the antenna's I_ANTENNA_RELATIVE follows its indicators) and the six limits end the lines; I_WHAT_IF present;
    - passivity and reciprocity under their flags (σ_max ≤ 1.02, error ≤ 0.02) for both layouts and both verifies;
    - each retune and sweep step: exit 0, project.json holding R1 and R2 at `$v` (the sweep at its last value);
    - each verify: 6 jobs kept, no E_ line, verify.s6p written, `verify.fingerprint` equal to `results.fingerprint`;
    - compare: two I_COMPARE_BASIS lines with T_VERIFY, each naming its own verify folder; compare.csv and compare.png written; no E_COMPARE_SETTINGS.
  - **Soft, recorded:**
    - each board's lines: Sdd21 at 240 MHz and at 10 GHz, the worst Sdd11 and Scd21, Scc21, the TDR's levels with their positions and marks, the skew, NEXT and FEXT into AUX, the loss lines;
    - what lies between the launches: at 125 ps and the route's 2D εeff 3.28 the resolution length is 10.35 mm, so the 30.4 mm route keeps about 0.9 resolution lengths (about 110 ps) between them; U2's run and the resistors read inside the launches, and the plane gap's x 116–117 mm (about 17.5 mm along the route) lies between them. Expected, not judged: each board's two levels read the route's middle blurred by both launches; a level more than 1 Ω off the target across the whole route is a level (I_SI_TDR_LEVEL), and the gap, a feature well under two resolution lengths, reads I_SI_TDR_SHORT where its excursion stands out from its base;
    - the sweep: the TDR's levels, the worst Sdd11 and Sdd21 at the marker for each value;
    - each verify's |ΔS| and level deltas, and their short marks;
    - compare's deltas and which are resolved: Scd21's change is P4-F's expected positive control, previewed here, not judged;
    - the times against cost's predictions.
- [ ] **Step 5: The record,** `docs/validation/<the run's date, YYYY-MM-DD>-si-results.md`.
  - **Language:** the lines in English. Render a run's or verify's events in one call: `$env:LANGUAGE = "en"; .venv\Scripts\python.exe -c "import json, sys; from kicad_rf_studio.core.messages import render; [print(render(e['code'], **e['params'])) for e in map(json.loads, open(sys.argv[1], encoding='utf-8')) if e['kind'] == 'result']" <events.jsonl>`; compare's lines by running it again under `$env:LANGUAGE = "en"` with `-o "$out\compare_en"`.
  - **Sections:** 1. Purpose: plan 3's end-to-end SI results, not a gate. 2. Inputs: the commands with `<RUN>`, the versions, the preset, `$v` and the fresh calibration. 3. Each board's results. 4. The termination sweep. 5. The retune with snapping and verify. 6. Compare's deltas. 7. Validity. 8. Times against cost. 9. The stated limits and what the window between the launches holds on this route. 10. Next: plan 4 and plan 5.
  - It holds no path and no host name.
- [ ] **Step 6: The amendments,** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`:
  - **A-54, §7.3:** a paragraph at the section's end:
    > "**Signal integrity** (Stage 4): an SI run's layout N-port lies on the uniform grid from DC to f_max, its DC point measured, and its chain closes the part ports as §7.2's retune does, each load held at DC at its value at the grid's first point above DC (a series capacitor's time constant lies beyond the TDR's record; an open part has no impedance at DC). Its S is renormalised to the target with s_def "power" passed explicitly (§7.7): a pair's ports through scikit-rf's se2gmm to mixed mode, the target differential and a quarter of it common; a net's ends to the target; a victim's ends stay at 50 Ω. The TDR is the step response of Sdd11 (a net's S11) through a Gaussian rise filter at the localising rise time 1.25/f_max and at the link's, summed from before t = 0, Z = Z_ref(1 + ρ)/(1 − ρ), the link's TDR and both TDTs read on the localising TDR's time axis; the far port's launch lies at twice the arrival of the measured line's TDT, where it reaches half its peak, and the first resolution length t_r·v/2 at each port is the port's own launch. The lowest and highest levels between the launches are read, each marked as no feature's impedance when it lies more than 1 Ω (0.5 Ω single-ended) off the target and its width at half its height, from the target or from its own base, is under two rise times: a feature shorter than two resolution lengths, which the lines, both plots, verify and compare mark wherever they show it. A pair's skew is its legs' TDT arrivals' difference; NEXT and FEXT are the peaks up to f_max from the measured line's start, a pair driven differentially, at each victim's first and second end. results/ holds layout.s{N}p, chain.s{P}p, si_summary.csv (the S at the target by frequency), si_tdr.csv (both TDRs and both TDTs by time, with the distance at the route's 2D εeff, its sections' length-weighted εeff with the mask) and si_summary.png; the lines give Sdd21 (S21) at the marker and at f_max, the worst Sdd11 (S11) and Scd21 up to f_max, Scc21 at the marker, the levels, the skew, the crosstalk peaks and, not in S, the copper's loss over the route's length by Hammerstad's formula for smooth copper and, with a lossless dielectric, the dielectric's, at the marker frequency and at f_max. On <date> the USB 2.0 fixture and its plane-gap variant ran it (`docs/validation/<date>-si-results.md`). (A-54, Stage 4 plan 3: controller recommendation, owner unavailable.)"
  - **A-55, §7.2 and §7.6:**
    - §7.2, a bullet at its end: "- **Signal integrity** (Stage 4): an SI project's retune takes an antenna's bypass syntax and refusals (§7.6, A-33) on every part of its lines, a 0R and a DNP part (`open`) included, and redraws the TDR, the mixed-mode S and the crosstalk from the closed N-port, each part port's load held at DC at its value at the grid's first point above DC (§7.3), so an S2P file must reach that point; a pull-up left open is no port, and a DNP one is stored `open`. (A-55)"
    - §7.6, a bullet after A-33's: "- **Signal integrity** (Stage 4): `verify` is v1's, every part in the grid at its value as an ideal part, a 0 Ω part as copper over its port's box and an open part left out, one job per external port; it compares the largest |ΔS| from the grid's first point above DC up to f_max and the TDR's lowest and highest levels between the launches, each marked when either lies on a feature shorter than two resolution lengths, with the retune at the same ideal values, whose loads hold at DC as the retune's, writes verify.s{P}p and records its settings fingerprint. (A-55, Stage 4 plan 3: controller recommendation, owner unavailable.)"
  - **A-56, §7.4 and §7.5:**
    - §7.4, a bullet after the antennas': "- **Signal integrity** (Stage 4) has no loss budget: a lossless model's missing power is the walls' and radiation's. Passivity and reciprocity apply. (A-56)"
    - §7.5, a paragraph after the antennas': "An SI result (Stage 4) states its own limits after the label that it is relative: the region's crop inside its walls, with the planes' cavity resonances and no radiation of an open line; copper as a perfect conductor; the dielectric model in force, lossless, whose loss the loss lines estimate, or Debye's fit; packages, dies and connector bodies absent, a part of three or more pads its pads alone; lumped 50 Ω ports at the pads, whose launch fills the first resolution length; and the TDR's resolution, a feature shorter than two resolution lengths read as no impedance. (A-56, Stage 4 plan 3: controller recommendation, owner unavailable.)"
  - **A-57, §3.2 and §3.3:**
    - §3.2's table, `compare`'s row reads: "| `kicad-rf-studio compare BASE VARIANT [-o PATH]` | Compares two antenna projects' or two signal-integrity projects' full simulations: writes compare.csv and compare.png, prints the deltas, each resolved or not, and refuses two projects whose settings fingerprints differ (A-34, A-57) |"
    - §3.2, a paragraph after A-50's: "**Signal-integrity results** (Stage 4): `retune`, `verify` and `compare` work on an SI project as on an antenna project. compare reads each project's run when no part is on its lines, else its verify of the last run at the values project.json holds; compare.png overlays their TDRs, every curve's levels marked, and their mixed-mode S, and its lines and compare.csv give the TDR's lowest and highest levels between the launches (marked "short" when either lies on a feature shorter than two resolution lengths), Sdd21 (S21) at the marker and at f_max, the worst Sdd11 (S11) and Scd21 up to f_max, the skew and each victim's NEXT and FEXT peaks, each resolved above 1 Ω on a differential TDR level and 0.5 Ω on a single-ended one, 0.05 dB on Sdd21, 0.5 dB on the rest where the higher of the two levels stands above −50 dB, and 1 ps on the skew: the design's registered values until gate P4-E sets them. It refuses an antenna project against an SI one. (A-57, Stage 4 plan 3: controller recommendation, owner unavailable.)"
    - §3.3, a last bullet of project.json's list: "an SI project's results record its route (the 2D εeff of its distance axis, the measured route's length and its loss estimates) and, with its verify, a settings fingerprint, which `compare` requires to be equal: the preset, the mesh's n and reach (not max_cell_mm, which follows the lines' 2D εeff), the region, interface, f_max, the link's rise time, the marker, the target, the stackup, the dielectric model, the lid and its height, the external ports' signal pads and the versions of the app and of openEMS (A-57)."
  - **The Status line** gains, at its end: " On <date>, Stage 4's plan 3 amended §3.2, §3.3, §7.2, §7.3, §7.4, §7.5 and §7.6 (A-54 to A-57) the same way."
- [ ] **Step 7: Commit.**

```bash
git add docs/validation/<date>-si-results.md docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs(validation): the SI results on the USB 2.0 fixture and its plane-gap variant, a termination sweep, a retune with snapping, verify and compare; Stage 1 spec A-54 to A-57 (Stage 4 design 5.12 item 3, 5.13; controller recommendation, owner unavailable)"
graphify update .
```

- [ ] **Step 8: Close.** Run the whole-branch review, and Step 1 again after any later commit. Fast-forward `main` to the branch locally, delete the branch, and delete `$env:TEMP\krs-si-results`. Nothing is pushed.

---

## Not in this plan

- **Plan 4, the gates:** P4-B to P4-F with their coupons (each section at least three localising resolution lengths, about 36 mm) and their reports; the defaults they set: n, max_cell's factor and VIA_MARGIN_MM, the dielectric default and the Debye pole count, the 45° rule, and this plan's thresholds (DIFF_OHM, SE_OHM, IL_DB, DB, LEVEL_FLOOR_DB, SKEW_PS), which P4-E keeps or widens; P4-F's positive control on the neck and the gap, which Task 8 only previews, and its check of the short-feature rule; P4-C's or P4-D's N_TDR and a trust floor, if a coupon needs either; the SI cost refit (plan 2's 1.85 times over-reading); §5.4's DC-free fallback if P4-D needs it; P4-G stays the owner's.
- **Plan 5, the GUI, the button and the docs:** opening an SI project (G_SI_LATER lifted); the Results page on `draw_si` with a retrace for the instant retune; the retune rows with E24 as an SI project's default series for every part port, an R included (design §5.7; `control.default_series("R1")` is "off" today), with the R rows (25 to 24 in E24, 27 in E12; 0R and open kept) added to `test_gui_control`'s snapping parametrize then; G_ wordings for E_RETUNE_SHORT_SHUNT, E_RETUNE_OPEN_SERIES, E_RETUNE_ANTENNA_VALUE and an SI E_S2P_BAND on an SI line, and G_COMPARE_KIND's text for SI; the Compare page on two SI projects; the README's SI tutorial on the USB 2.0 fixture; the release check; the acceptance run through the window (design §5.14 item 3); the Stage 4 exit record.
- **SI output golden pins:** none. Plan 4's defaults re-record golden_si by ruling, and the fake-run tests pin the outputs' structure and numbers; golden_si's model and 2D-table pins stay as plan 2 recorded them.
- **Deferred, with their ceilings (ponytail comments):** the DC rule (a series capacitor reads its 5 MHz value at DC; an S2P file must reach 5 MHz, E_S2P_BAND otherwise); N_TDR's 200 ns record and Z unbounded at an open; the TDT's half-sample offset; one 2D εeff for the distance axis; the short-feature rule's two widths, tuned on synthetic lines; the common reference at target/4; NEXT at a victim's first-named end; the loss estimate from one measured line's sections, scaled to its route; Hammerstad's microstrip formula on an inner-layer section and its skin-depth validity; the plot's span with no arrival; the SI fingerprint without max_cell_mm; the copy of antenna.deltas' row.
- **Plan 2's other carried items:** the SI cost refit and the shared mesh lines (plan 4); `check_project` refusing two lines that share a net (plan 5); `si_reference`'s within-reach point test (plan 4).

## Controller rulings (2026-11-04; binding)

These are the architect's rulings as revised after the four reviews. Each is a controller recommendation made while the owner is unavailable.

- Ruling: eight tasks, in this order: the reading, the run's record, the lines, the outputs, the retune, verify, compare, the run. The suggested shape's third item splits in two, the lines (a pure function and 23 messages) apart from the files and the pipeline that write them, so a reviewer can pass one and refuse the other; the crosstalk rides in the reading, its peaks being three lines of it; the fingerprint rides with the route in the run's record, since `_run` takes both before the jobs and verify (Task 6) stores it. Task 4 keeps the chain's DC hold with the writers: about ten lines whose one consumer in this plan is write_outputs' SI branch. Each task's tests are red in that task but its guards (the import probes, the keys that must stay absent), which pass on `main` and say so — design §5.12 item 3, ponytail — cost if wrong: a reorder.
- Ruling: every SI result lives in `core/post/si.py`, as the antenna's in `core/post/antenna.py`: one module, one `Reading` that the lines, CSVs, PNG, verify and compare read. At module level it imports only the stdlib, numpy and core.messages; scipy, scikit-rf, matplotlib, `core.model.parts`' Z0 and `core.post.antenna` (DELTA_COLUMNS, `_csv`) inside the functions that use them, since `core.project` imports it for `LOCAL_RISE` (parts and antenna import core.project back: a circular import, probed) and the CLI adds no work at import time (C-5; scipy.constants alone costs 0.17 s) — ponytail — cost if wrong: a module split.
- Ruling: mixed mode is scikit-rf's `se2gmm(p=2)` on the chain's first four ports, renormalised to the target differential and target/4 common, s_def "power" passed explicitly; a net's two ends are renormalised to the target, one impedance a port, and a victim's stay at 50 Ω, which the net test pins (a scalar renormalise moves the victim's S by 0.18). On an ideal coupled pair the modes come out matched to 1e-15 at those references (the architect's probe), so the unit test reads the even/odd 4-port of plan 1. The common reference at a quarter of the target is the uncoupled pair's (se2gmm's own 2·Z0 and Z0/2) — design §5.5, Stage 1 §7.7 — cost if wrong: one reference value and the Scc and Scd numbers with it.
- Ruling: the DC rule. Each part port's load is evaluated on `chain.above_dc(f)`, the grid with its DC point replaced by its first point above DC, in the run, the retune and verify's ideal loads alike; one helper that both chain_results and _verify call, `f` itself on a grid off DC, so v1's and the antenna's chains are unchanged. `with_box` divides by ω·C_box and `z_part` by ω·C, so DC gave a RuntimeWarning on the USB fixture's own resistors (the architect's probe of v1's verify path) and NaN for a capacitor or an open part. A series capacitor's time constant (10 µs for 100 nF in 100 Ω) lies far beyond the TDR's 200 ns record, so its true DC open would wrap into the TDR as a ramp; its 5 MHz value is the short-time view the TDR shows. An S2P file must reach 5 MHz (from 1 MHz it retunes within 2.4e-6 of the oracle; from 10 MHz E_S2P_BAND names 5.0, the reviser's probe) — design §5.6, §5.7 — cost if wrong: an AC-coupled line's DC point read as a short.
- Ruling: the TDT's arrival is where its step first reaches half its peak, interpolated between samples, none under ARRIVAL_FLOOR 1e-3; the far launch lies at twice the measured line's arrival (Sdd21's or S21's at the localising rise), and the skew is N's leg arrival less P's on the chain at 50 Ω. step_response sums each sample up to t + dt/2, so an arrival reads 3.1 ps early at 10 GHz; plan 1's time axis stays (its test pins t[0] ≤ −LEAD·t_r), and a skew, a difference, is exact to 0.003 ps. Since that axis starts LEAD rise times before t = 0, the link's TDR and both TDTs are interpolated onto the localising `t` (uninterpolated, the link's curve sat 1.5 to 11.5 ns late in every file and plot). The 50 % crossing is the design's left choice (§6) — design §5.6, §6 — cost if wrong: one function.
- Ruling: the levels are the localising TDR's lowest and highest where t_r < t < t_far − t_r. A level is marked short when it lies more than DIFF_OHM (a pair) or SE_OHM (a net) off the target and either width is under 2·t_r: its run past half its height from the target, searched over the whole route 0 ≤ t ≤ t_far, or, when it stands more than that threshold above its own base in the span, its width at half that prominence (scipy's peak_prominences and peak_widths, imported inside). On the design's own 5 mm neck from 90 to 110 Ω between 30 mm flanks it reads 98.45 Ω and is marked; the same neck on a 96 Ω route reads 102.02 Ω and a 3 mm 40 Ω pad on a 47 Ω route 44.64 Ω, both marked; a 3 mm 40 Ω bump reads 46.68 Ω and is marked, a 30 mm 60 Ω section reads 60.00 Ω and is not; a uniform 95 Ω route of usb2_hs's 30.405 mm (about 0.9 resolution lengths between the launches) is a level, and 15 and 20 mm sections fall either side of two resolution lengths (the physics review's 13 cases and the reviser's probe). Half-height from the target alone failed on a route itself off the target and, clipped to the span, marked every level of a route under four resolution lengths; half-height from the window's median stretched a bump over its neighbours. A level near the target is no feature, so a flat line never reads short. Deltas compare short levels too (design §5.6) — design §5.6, anti-goal 2 — cost if wrong: one rule, plan 4's P4-F checks it on the neck and the gap.
- Ruling: a level on a short feature carries its mark wherever a level is shown: I_SI_TDR_SHORT in the lines, a cross on every curve of both PNGs, `compare_verify`'s third element and I_VERIFY_LEVEL_SHORT in verify, the tdr rows' "short" in compare.csv's marker cell (DELTA_COLUMNS kept) and I_SI_COMPARE_LEVEL_SHORT in compare. "Deltas still compare" allows the delta, not an unmarked level: on the neck, compare would otherwise print 98.45 Ω in Ω with nothing saying it is no impedance — design §3 anti-goal 2, §5.6 — cost if wrong: two messages and one cell.
- Ruling: the run records `route` in its results, as v1 records `loss_expected`: the distance axis's 2D εeff, the length-weighted εeff with the mask of the measured line's sections, each cut as si_readout cuts a line alone, its own layer's substrate as `h` (usb2_hs 3.2777, qspi_clk 3.3294); its route_length; and the loss estimates over that length at marker_hz and at f_max, Hammerstad's α_c for smooth copper (scikit-rf MLine.analyse_loss's formula, matched to 1e-12 with scipy's μ0 and ε0, at KiCad's 5.8e7 S/m) and loss_expected's dielectric loss, −10·log10(1 − loss_expected), from the sections' mean per mm. With no section solved (45° tracks alone), its εeff is the stack's largest εr, as new's, its loss None and the lines say W_NO_SECTIONS. The loss lines print the marker's own frequency (133 MHz), the S lines its grid point (135 MHz). new's 2D εeff (the lines' largest, no mask) stays the mesh's and T_max's. Results without a route read as stale. The εeff and the loss need the board and its cuts (1.7 s on usb2_hs), which retune and the GUI's instant retune should not pay again. The cut and slab loop is si_readout's and expected_loss's, written once more and marked rather than hoisted, since expected_loss is v1's — design §5.6 — cost if wrong: one dict and a few % on a distance.
- Ruling: an SI fingerprint holds the design's fields made concrete, its keys a local tuple in `fingerprint` as the antenna's are and written out in its test: preset, region, interface, f_max_hz, rise_s, marker_hz, target_ohm, stackup, dielectric, lid and lid_height_mm (the lid sets the model where a shield covers the region, as its height does), the mesh without max_cell_mm, "ends" (the external ports' signal pads, so other lines or victims never compare and the deltas' victim rows line up), and the versions. max_cell_mm, t_max_s, window_s, tolerance and gates stay out: the first three follow the lines' 2D εeff and length, which a variant may change (usb2_hs_45 differs from usb2_hs in max_cell_mm alone, 0.413997 against 0.414074 mm, the reviser's probe), and the others change no S — design §5.8, §6 — cost if wrong: one key.
- Ruling: `write_outputs` and `chain_results` carry an SI project and plan 2's `si_outputs` copy goes (its carried item): basis_lines at GATES_SI, the DC rule, the indicator lines alone (no ideal schematic, loss budget or W_NOT_TWO_PORT), then the SI lines, the what-if label, I_OUTPUTS and `si_limits`; v1's lines and files are unchanged, as the golden pins prove. The files are layout.s{N}p, chain.s{P}p, si_summary.csv by frequency, si_tdr.csv by time over the plot's span (both TDRs and both TDTs, since design §5.6 computes each at both rise times) and si_summary.png, its TDR curves labelled with each rise time and its resolution length, every curve's levels marked and the Ω axis from 0 to 3·target: "a CSV of the mixed-mode S and the TDR" becomes one CSV per axis, since one file would pad 2001 frequency rows against 32,000 TDR samples — design §5.6, ponytail — cost if wrong: one file name.
- Ruling: N_TDR stays 2000: its 200 ns record is far past the longest T_max (25 ns at 300 mm), and the markers 48, 27 and 12 and the 5 MHz S2P floor rest on it. No trust floor: dc_pulse's spectrum stays above about −20 dB up to f_max (exp(−9/4) there), and §5.4's DC-free fallback (plan 4) would bring one back with its own pulse. si.py's mark says so in place of plan 1's "plan 3 retunes N_TDR" — design §6 — cost if wrong: one constant and the pins on its grid.
- Ruling: the lines' formats: insertion dB to 3 decimals (its threshold is 0.05 dB), other dB and Ω to 2, times in ps (`t * 1e12`, which settles the 6.25 ps grid's .x5 ties as the pins do) and distances in mm to 1, rise times `:g`, εeff to 2, the skew signed to 2, loss estimates to 3; a frequency is its grid point's (se50's 133 MHz reads 135), the loss lines' the marker's own; ARRIVAL_FLOOR a parameter of I_SI_TDR_NO_ARRIVAL, never a number in its text. A symbol (Sdd21, NEXT) is a literal parameter, a word a `T_` code — pt-BR design §5.1 — cost if wrong: a few format strings.
- Ruling: the SI limits are the design's list as six codes, v1's I_LIMIT_PEC reused, the dielectric's by the model in force; the design's last limit ("results compare variants under identical settings and do not predict measured performance") is I_SI_RELATIVE itself, which opens every SI result's own lines, after the passivity and reciprocity indicators as the antenna's label follows its indicators — design §5.6 — cost if wrong: one code.
- Ruling: the SI retune is the antenna's: bypass values on every line part, the converse refusals on the lines merged (`chain_of`), E_RETUNE_ANTENNA_VALUE for an unreadable value; an S2P file read from the grid's first point above DC. Three msgids generalise to "the chain" and name a signal-integrity line, the antenna's codes and params unchanged. A DNP pull-up is stored `open` and left out of I_SI_SHUNT_OPEN (plan 2's minor): its E_RETUNE_ROLE stands, and if a user promotes it to a port its value reads open, as a DNP part's does. Snapping stays the GUI's `snapped`, unchanged and unpinned here, as Stage 1 §7.2 and Stage 3's plan 3 had it; Task 8 reads it at run time; plan 5 makes E24 an SI part's default and adds the R rows to its snapping test — design §5.7 — cost if wrong: three msgstrs and one default in plan 5.
- Ruling: verify is v1's `_verify` with SI branches, not a function of its own as the antenna's: the same jobs, store and verify.s{P}p, its comparison (`compare_verify`: the largest |ΔS| over every entry and over f from the first point above DC, where the retune's held load and verify's own DC estimate need not agree, and both readings' levels with the short mark) and lines (verify's own SI lines, then the comparison, I_VERIFY_LEVEL or I_VERIFY_LEVEL_SHORT per level or I_VERIFY_NO_LEVELS, I_VERIFY_SCOPE_SI and the SI limits) in v1's place, and the fingerprint recorded in an SI project's verify block alone (v1's keeps its six keys). `verify_spec` takes `bypasses` beside `far_field`, so an SI 0 Ω part is copper and an open one is left out while every antenna caller and its tests stay as they are — design §5.7, ponytail — cost if wrong: a function split.
- Ruling: compare checks both projects' kinds before reading any board (a raising `pipeline.load` proves it), then reads each project's run when no part is on its lines, else its current verify at its values, through `_full_record`, which antenna_result now shares (its tools and tests keep its name and its own kind check; `si_result`, whose one caller checks, has none). The deltas are DELTA_COLUMNS rows, written by the antenna's `deltas_csv`, a short level's row marked in its marker cell; the −50 dB floor reads "the higher of the two levels", so a crosstalk rising from −60 to −40 dB is resolved and one from −70 to −60 dB is not — design §5.8 — cost if wrong: one condition.
- Ruling: `layout`'s SI marker is the point of `f` nearest the marker on any grid, `argmin`, which equals plan 2's `round` on the presets' uniform grid (62.5 MHz's tie included) — plan 2's carried item — cost if wrong: none.
- Ruling: Task 8 runs usb2_hs and usb2_hs_gap at the normal preset, sweeps R1 = R2 over 0R, 10, 22, 33 and 47 Ω on a copy, applies `snapped('R1', '25', 'E24')` (24 Ω on `main`, the GUI's snapping of a typed 25 Ω) to both, verifies both and compares them: design §5.14 item 3's flow through the CLI, the window's being plan 5's. Its checks are pre-registered: hard on what the code guarantees (I_SI_RELATIVE before every I_SI_ line, after the indicators), soft on the physics (about 0.9 resolution lengths between the launches at εeff 3.28), the gap's deltas a preview of P4-F — design §5.14 — cost if wrong: one rerun.
- Ruling: A-54 (§7.3), A-55 (§7.2, §7.6), A-56 (§7.4, §7.5) and A-57 (§3.2, §3.3) land in Task 8 with the run's numbers; design §5.13 names §7 (mixed mode, the TDR and the SI retune), and §3.2 and §3.3 join it because compare and the fingerprint change the commands and the record, as A-34 did for the antennas. A-54's chain closes the part ports "as §7.2's retune does" (§7.3 closes none), and A-55's §7.2 bullet repeats the DC hold — design §5.13 — cost if wrong: a paragraph moved.
- Ruling: no SI output golden pins in this plan: plan 4's defaults re-record golden_si by ruling anyway, and the fake-run tests pin the outputs' structure and numbers — design §5.12 — cost if wrong: a later ruled recording.
- Ruling: this plan's pt-BR glossary, by the pt-BR design's §6.1, plan 2's terms standing: mixed mode — modo misto; common mode — modo comum; mode conversion — conversão de modo; crosstalk — diafonia (NEXT and FEXT stay); launch — entrada (plan 2's W_SI_LONG_PORT); resolution length — comprimento de resolução; feature (of a route) — trecho; level — nível; lowest, highest — mais baixo, mais alto; round trip — ida e volta; skew — skew intrapar; leg — perna; conductor loss — perda no cobre; smooth copper — cobre liso; lossless — sem perdas; lumped port — porta concentrada; package — encapsulamento; die — chip; crop — recorte; cavity resonance — ressonância de cavidade; distance — distância; significance threshold — limiar de significância (Stage 3's). A `T_` word after a preposition carries pt-BR's contraction in its msgstr (T_PAIR_DRIVE "do par…", after "a partir") — cost if wrong: a native speaker changes a few msgstrs.
- Ruling (disclosure): the architect's checks ran only in a scratch folder with the repo's venv, an isolated data folder and the fake worker: two network-fake SI runs (usb2_hs and qspi_clk) and v1's verify path on the USB one; se2gmm and renormalize on plan 1's even/odd 4-port; the levels, arrivals and widths on ABCD-cascaded lines; si_route's numbers on both fixtures; Hammerstad against MLine.analyse_loss; the snapping of SI values; and the formatted lines and deltas of a reference implementation. The four reviews probed the circular import, the link TDR's axis, the fake verify's levels, the fingerprint on the five fixtures and the short-feature rule on 13 synthetic cases. The reviser re-ran this plan's 17 pure unit tests (Tasks 1, 2's Hammerstad, 3, 4's CSVs and PNG, 6's compare_verify and 7's deltas, plus the import guard) against a revised reference with RuntimeWarnings as errors, two network-fake runs and verifies (the QSPI chain's 26.87 Ω unmarked, verify's levels 1.6e-6 off 50 Ω, the USB |ΔS| 0.123264 at 10 GHz above DC), an S2P part held at DC, si_route's no-section case on a mini board and new_si's fingerprints on the four usb2_hs fixtures. No openEMS, no KiCad binary, no suite; nothing was written in the repo or its venv — cost if wrong: none.

## Open issues, ruled by the controller (2026-11-04; owner unavailable)

The reviser's open issues, each with the controller's ruling. On 2026-11-04 the controller confirmed all twelve as below, each a controller recommendation while the owner is unavailable.

1. The new short-feature rule is the physics review's and the reviser's. It was tuned on 13 synthetic ABCD lines, with and without 0.3 nH launches, and on the network fake, but never on FDTD data. P4-F checks it on the neck and the plane gap. The owner may prefer a different rule; that choice is open.
   **Ruling:** the rule stands as Task 1 writes it; plan 4's P4-F checks it on FDTD data; another rule is the owner's choice (an owner item).
2. The SI fingerprint leaves out max_cell_mm, so a project whose max_cell_mm was hand-edited coarser still compares. It also adds 'lid', which design 5.8's list does not name. Both are controller recommendations that need the owner's review of the field list (A-57).
   **Ruling:** both stand; A-57 lists the fields for the owner's review, and the ponytail mark names the hand-edited mesh as the ceiling.
3. The loss lines print the marker frequency itself (se50 133 MHz, 100base-tx 62.5 MHz), while the S lines print its grid point (135 MHz, 60 MHz). One result block therefore shows two 'marker' frequencies. The alternative is open: compute the loss at the grid point and re-pin QSPI's marker numbers to about 0.0203 and 0.0070.
   **Ruling:** as written. Each line names the frequency it holds: the loss lines are a closed-form estimate at the project's own marker, the S lines a reading at the grid point nearest it. usb2-hs's 240 MHz lies on the grid, so the USB block shows one frequency. Plan 5's Results page may unify them.
4. W_NO_SECTIONS is reused in place of the loss lines when no section was solved. Its text ('no straight, axis-aligned sections, so there is no 2D estimate') is accurate but generic, and slightly off when sections exist but every cut is touched by other copper. A dedicated wording could follow if users find it unclear.
   **Ruling:** reused; plan 5's wording review may add a dedicated message.
5. On an SI project, E_S2P_BAND names the simulated band as 5.0 to 10000.0 MHz, while the run's grid starts at DC. Only a ponytail comment explains the 5 MHz floor. An SI-specific wording is left to plan 5's G_ messages.
   **Ruling:** as written; plan 5's G_ wording (Not in this plan).
6. Task 4 remains the largest task (writers, PNG, CSVs, the chain's DC hold, marker, rule comment). The split was rejected; the controller may still split it if a per-task review asks to pass the chain change apart from the writers.
   **Ruling:** eight tasks stand. If Task 4's review loops on the chain change apart from the writers, the controller splits it then.
7. When no step arrives, the TDR plots end two link rise times past t = 0 (1 to 6 ns). A long line opened by a DNP part beyond that point is cut from the plot; this is marked as a ceiling.
   **Ruling:** the ceiling stands, marked; the route's round trip is the upgrade.
8. The link-rise TDT is written to si_tdr.csv but drawn on no PNG panel.
   **Ruling:** as written; plan 5's Results page decides its panel.
9. verify_spec keeps two switches (bypasses or far_field), which preserves every antenna caller. The quality review's single-switch alternative is recorded as rejected.
   **Ruling:** two switches stand.
10. Task 8's soft expectations rest on about 0.9 resolution lengths between the launches on usb2_hs, so the real levels and their marks on both boards are recorded, not judged. $v depends on gui.control.snapped at run time (24 on main), which no test pins any longer.
    **Ruling:** as written; the record states `$v` and the call that produced it.
11. The new pt-BR msgstrs, including the de+o contractions, await the owner's native review of po/pt_BR.po.
    **Ruling:** an owner item, with the native review of po/pt_BR.po.
12. Plan 2's carried items (the SI cost refit, the shared mesh lines, check_project's shared-net refusal, si_reference's point test) stay with plans 4 and 5.
    **Ruling:** they stay there.

**Owner items this plan adds**, each a controller recommendation until the owner reviews it: A-54 to A-57; the registered thresholds (DIFF_OHM, SE_OHM, IL_DB, DB, LEVEL_FLOOR_DB, SKEW_PS) until P4-E; the four deliberate msgid changes (E_RETUNE_SHORT_SHUNT, E_RETUNE_OPEN_SERIES, E_RETUNE_ANTENNA_VALUE, E_COMPARE_KIND); the native review of the new msgstrs (perna, diafonia, skew intrapar among them).

**A stop in any task:** a prototype number the code misses, a pin that moves or a fixture that refuses is reported BLOCKED with both values and the formula that differs, and the controller rules. No limit and no assertion loosens to pass.
