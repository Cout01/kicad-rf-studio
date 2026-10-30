# Stage 3 Plan 3: Matching and Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On an antenna project with a matching network, every chain part is a port that the instant retune sets (0 Ω and open included), `verify` runs the applied values as ideal parts in one job that records the far field, and `compare BASE VARIANT` reports two projects' deltas, each resolved or not, refusing projects simulated with different settings.

**Architecture:**
- **Bypass values.** An antenna chain part's value may be a bypass: 0 Ω (`0R`, any 0 in ohms, or 0 on an L or an R) or `open`. `values.bypass` reads it and `chain.z_value` makes it Z_part 0 or ∞; `with_box` closes an open port with its box's C alone. v1's retune (assign, part_impedances, loads, terminate, snapping, S2P parts) then runs as it is, and v1 never reads a bypass: every branch tests `core.project.antenna()`.
- **Verify.** `verify_spec` puts the parts in the grid as v1 does, ideal at their values, a bypass as copper over its port's box or absent, and adds the far-field box (`far_field_box`, factored out of `model_spec`). Verify's one job therefore records the far field. `_verify_antenna` compares S11 and, where both mark a dip, the resonance with the retune, and transforms the far field as `_run` does. The retune's what-if η_tot then takes η_rad from that verify while it is current (`current_verify`).
- **Compare.** Each antenna run and verify records a settings fingerprint. `compare` checks each project's results against its current model as retune does (`results_of`), then reads its full simulation: its run when no part is on its chain, else its current verify at the values project.json holds. It refuses differing fingerprints and writes the deltas and the overlays.

**Tech Stack:**
- Python ≥ 3.11 (dev venv 3.14.2), numpy, scikit-rf, matplotlib and h5py. No new dependency.
- openEMS 0.37.0 and CSXCAD 0.7.0, in workers only; Task 9 runs them for real.
- pytest; `tools/catalog.py` (Babel, dev extra).

**Spec:**
- `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md` (binding): §5.12 item 3, with §1, §3, §4, §5.1, §5.5–§5.8, §5.13 and §5.14 item 3.
- The Stage 1 spec, `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, where the design reuses it: §3.2, §3.3, §7.1–§7.6, §7.8, §9 and §10.
- Task 9 lands A-33 (§7.6) and A-34 (§3.2, §3.3), with their exact text.
- Plans 1 and 2 (`docs/superpowers/plans/2026-10-29-stage3-plan{1-far-field-engine,2-antenna-project}.md`) and the first run's record, `docs/validation/2026-10-30-antenna-first-run.md`.
- Research (git-ignored): `.superpowers/sdd/stage3-research/` r2 (Q3, Q4) and r3.

**Branch:** `stage3-plan3`, from `main` at `39a570f`. This plan is `docs/superpowers/plans/2026-10-30-stage3-plan3-matching-and-comparison.md`. Commands run from the repo root with `.venv/Scripts/python`. Line references are `main`'s at `39a570f`; if an earlier task moved a line, find it by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage3-plan3 main`. Then `git diff --stat 39a570f HEAD -- src tests tools po pyproject.toml` must print nothing.
2. Commit this plan on the branch.
3. After Task 9: the whole-branch review, a local fast-forward merge into `main`, and delete the branch. Nothing is pushed.

## Global Constraints

- **v1 byte for byte** (design §3, §4). v1 projects stay at schema 1. Their model specs, `spec_hash`, `model.json`, verify's model, `project.json`, `new`'s lines, retune's and verify's behaviour and `results/` files stay as `tests/test_golden_v1.py` and the v1 suites pin them. A task that moves a pin is wrong: stop and get a ruling, never re-record.
- **Antenna only.** Every antenna branch tests `core.project.antenna(data)`. No v1 dict gains a key: v1's results gain no `fingerprint`, and v1's verify block gains no `far_field` or `fingerprint`. A bypass value is read only for an antenna (`bypasses=antenna(project)`, `far_field=` given only for an antenna). The GUI keeps refusing antenna projects until plan 5 (`control.open_project`'s guard).
- **Far field** only from a job that holds the network as applied: a run with no part port, or verify. No part-port job records one. Every transform goes through `pipeline.far_field`, so `read_cached=False` and a file of its own (plan 1's worker).
- **openEMS stays in the worker** (Stage 1 §3.1): the CLI, the orchestrator and `core.post` never import openEMS or CSXCAD. `runs.openems_versions` reads the installed versions' metadata in an isolated subprocess and imports nothing.
- **Messages:**
  - Every new user-facing string is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, in the same task. Compile it with `.venv/Scripts/python tools/catalog.py` (run, set the msgstr, run again), by the pt-BR design's §6 glossary and this plan's glossary ruling.
  - A word passed as a parameter is a `T_` code.
  - Numbers keep the decimal point.
  - A msgstr keeps every identifier, option, quoted text, backticked command and dotted number of its msgid (`test_sexpr.py`'s KEEP). A table below writes `\|` for a pipe inside a cell: the msgid and msgstr hold `|S11|`, with no backslash.
- **Tests:** test-first.
  - Tier (a) tests never run openEMS, KiCad, the network or a build. They use `tests/fake_worker.py` through the `fake` and `calibrated` fixtures (`KRS_FAKE=network` for a known S), and committed fixtures.
  - `KrsError` tests check `.code` and `.params`.
  - **Prototype numbers.** A number this plan gives from the architect's or the reviser's probes that the code misses stops the task: report both values and the formula that differs. That covers the snapped values, the exact resonances on the band grid, the bandwidths, the far-field box's centre, the network fake's convergence and the oracle tolerances. The pin changes only on a ruling.
  - **Isolation:** tests never touch a real KiCad folder, the Documents folder, KiCad's settings or the real data folder. A test that calls `compare` passes `-o` into `tmp_path`, or first moves the working folder under `tmp_path` (`monkeypatch.chdir`), never the real working folder. Task 9 sets LOCALAPPDATA and XDG_DATA_HOME to a folder under `$env:TEMP` in the same call and types `CSXCAD_INSTALL_PATH` in the call, never in a file.
- **Full suite** before every commit: `.venv/Scripts/python -m pytest -q`, about 18 minutes. Run it once, in the background, with nothing beside it, and wait for it to exit.
- **Git:**
  - No push. The pre-commit privacy gate runs on every commit, so never use `--no-verify`.
  - No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name. Write `<openEMS folder>` and `<RUN>`.
  - No commit message carries a co-author line. Use the messages as given.
- **Files:** every new `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`. Code and docs are in English.
- **Workflow:**
  - Run `graphify query "<question>"` before reading code, and `graphify update .` after each commit.
  - Ponytail: the laziest solution that works, in the fewest files. Reuse v1's retune (`assign`, `part_impedances`, `loads`, `terminate`), verify (`verify_spec`, `_verify`'s phases), snapping (`gui.control.snapped`), S2P parts, `loss_budget` and `results_of`; `chain_results` and `layout`; plan 1's `far_field`, `far_field_of` and `efficiencies`; plan 2's `antenna_outputs`, `s11_lines`, `far_field_lines`, `resonance`, `bandwidth`, the CSVs and `draw_antenna`; and the fake worker.
  - Put a `ponytail:` comment naming the ceiling on each corner cut, in the step that writes the code.

## Review Focus

1. **A bypass the parser reads otherwise.**
   - `C2=0` is 0 F, an open, which v1's retune refuses (every output would be NaN). It must stay refused, never read as 0 Ω; on an antenna the refusal, E_RETUNE_ANTENNA_VALUE, names `C2=open` and `C2=0R`.
   - On an antenna, `L1=0R`, `C2=0 ohm`, `L1=0nH` (0 Ω) and `C3=OPEN` (open) are bypasses; `L1=0pF` (0 in a unit not an L's) is none.
   - On a v1 project, `L1=0R` and `C2=open` stay E_RETUNE_VALUE.
   - Snapping leaves a bypass as typed.
   - Checks: Task 1's `test_a_bypass_reads_0_ohm_or_open`, `test_an_antennas_retune_takes_0r_on_a_series_part_and_open_on_a_shunt_one` and `test_snapping_leaves_a_bypass_as_typed`.
2. **The network bypassed at once, and a placeholder there and back.**
   - The series part at 0 Ω and both shunts open: the antenna seen through its feed line.
   - A DNP placeholder fitted at 1 pF and then opened again must give back the first chain.s1p byte for byte.
   - Verify of the bypassed network: one copper box, nothing in the grid, no cell C read.
   - Checks: Task 1's `test_the_antenna_seen_through_its_feed_line`; Task 2's `test_a_placeholder_board_runs_its_placeholders_as_ports_there_and_back`; Task 5's `test_verify_of_the_antenna_through_its_feed_line`.
3. **A verify whose transform fails or is stopped, or whose file is held.**
   - On a failure: the comparison is stored with `far_field` null, verify.s1p and verify_summary.png are written, there is an E_ line, and the exit code is 2.
   - On a stop: KeyboardInterrupt (exit 130), with the comparison, I_VERIFY_RESULTS and verify.s1p kept.
   - A held verify_summary.png costs only verify's files; a held project.json costs the store and the transform, and verify.s1p and the PNG are still written.
   - Checks: Task 5's `test_a_verify_whose_transform_fails_keeps_its_comparison`, `test_a_stopped_verify_transform_keeps_the_comparison` and `test_a_held_file_costs_an_antennas_verify_only_that_file`.
4. **Values or the model changed between a verify and its use.** Cases: a project applied to other values after its verify, a verify of another run, a verify whose run folder was deleted, and results that an edited project.json or a re-saved board made stale.
   - `compare` refuses such a project with E_COMPARE_NO_RESULT, naming it.
   - The retune's what-if uses verify's η_rad only while that verify is current (`current_verify`).
   - Checks: Task 8's `test_compare_reads_a_part_port_projects_verify_at_its_values` and `test_compare_refuses_other_settings_another_kind_and_no_result`; Task 6's `test_after_verify_the_retune_shows_the_what_if_total_efficiency`.
5. **Two projects that are not comparable, or only half comparable.**
   - Refusals: fingerprints that differ (preset, air gap, openEMS version), a v1 project, a project with no results, a plan-2 result with no fingerprint. Each refusal names the fields or the project.
   - A project with no far field (a failed transform) leaves S11's deltas alone.
   - A lowest |S11| above −6 dB, or at the band's edge, is no resonance to judge (I_RESONANCE_NOT_COMPARED): the argmin of a shallow minimum moves with noise.
   - Checks: Task 8's `test_compare_refuses_other_settings_another_kind_and_no_result` and `test_compare_without_a_far_field_on_one_side_compares_s11_alone`; Task 7's `test_far_field_deltas_need_both_far_fields`; Task 5's `test_verify_compares_s11_and_the_resonance_with_the_retune`.

---

## File structure

```
src/kicad_rf_studio/core/kicad/values.py, core/post/chain.py, pipeline.py (assign)                          # T1
src/kicad_rf_studio/core/model/parts.py (project_parts)                                                      # T2
src/kicad_rf_studio/pipeline.py (fingerprint, _run, antenna_outputs), core/post/antenna.py (draw_antenna)     # T3
src/kicad_rf_studio/core/model/spec.py (far_field_box, model_spec, verify_spec)                             # T4
src/kicad_rf_studio/pipeline.py (verify, _model_phase, _verify, _verify_antenna, far_of), core/post/antenna.py # T5
src/kicad_rf_studio/pipeline.py (chain_results, s11_at, current_verify, antenna_outputs), core/post/antenna.py # T6
src/kicad_rf_studio/core/post/antenna.py (deltas, delta_lines, deltas_csv)                                   # T7
src/kicad_rf_studio/pipeline.py (antenna_result, compare_projects), core/post/antenna.py, cli.py            # T8
src/kicad_rf_studio/core/messages.py, po/*, locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo                      # T1, T3, T5-T8
tests/test_match_antenna.py (T1), tests/test_compare.py (T8) new; tests/fake_cli.py (T3); test_values.py,
  test_post_chain.py, test_retune.py, test_model_parts.py, test_cli_antenna.py, test_post_antenna.py, test_run.py,
  test_antenna_model.py
docs/validation/<date>-antenna-matching-run.md, the Stage 1 spec                                             # T9
```

---

### Task 1 [code]: Bypass values in the retune

**Files:**
- Modify:
  - `src/kicad_rf_studio/core/kicad/values.py`: `OPEN_VALUE` and `bypass` after `port_value`;
  - `src/kicad_rf_studio/core/post/chain.py`: `z_value` after `z_part`, `part_impedances` and `with_box`;
  - `src/kicad_rf_studio/pipeline.py`: `assign`;
  - `src/kicad_rf_studio/core/messages.py`: after E_RETUNE_VALUE;
  - `po/*` and the `.mo`.
- Create: `tests/test_match_antenna.py`.
- Test: `tests/test_values.py`, `tests/test_post_chain.py` and `tests/test_retune.py`.

**Interfaces:**
- Consumes: `parse_value`, `part_kind`, `part_value` and `port_value`; `z_part`; `core.project.antenna`; `assign`'s refusals; `gui.control.snapped` and `default_series` (Qt-free); the network fake.
- Produces:
  - `values.OPEN_VALUE = "open"` and `values.bypass(ref: str, text: str) -> float | None`, which gives 0.0, `math.inf` or None.
  - `chain.z_value(ref: str, text: str, model: dict | None, f: np.ndarray, *, bypasses: bool = False) -> np.ndarray | None`.
  - `chain.with_box(z, f, c_box)` takes an infinite z, an open part, and gives 1/(jω·c_box).
  - `part_impedances(project, folder, refs, f)` reads bypasses for an antenna.
  - `pipeline.assign`, for an antenna: a RIGHT that `bypass` reads is stored as typed. E_RETUNE_SHORT_SHUNT `{ref, net}` refuses 0 Ω on a shunt part whose other net is off the chain, E_RETUNE_OPEN_SERIES `{ref}` refuses open on a series part, and E_RETUNE_ANTENNA_VALUE `{ref, value}` takes E_RETUNE_VALUE's place.
  - In `tests/test_match_antenna.py`: `pi_run(tmp_path, monkeypatch, board=...) -> Path`, `OPEN`, `oracle(f, *z) -> np.ndarray` and `chain_s11(pj)`, which Tasks 2, 3, 5, 6 and 8 use.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_values.py` (imports gain `math` and `bypass`):

```python
@pytest.mark.parametrize(("ref", "text", "z"), [
    ("L1", "0R", 0.0), ("C2", "0Ω", 0.0), ("C2", "0 ohm", 0.0), ("R1", "0", 0.0), ("L1", "0nH", 0.0),
    ("C2", "open", math.inf), ("L1", " OPEN ", math.inf),
    ("C2", "0", None), ("C2", "0pF", None), ("L1", "0pF", None), ("L1", "2.7nH", None), ("R1", "50R", None),
    ("C2", "opened", None)])
def test_a_bypass_reads_0_ohm_or_open(ref, text, z):  # Stage 3 design 5.7; RF 1: a C of 0 F stays port_value's open
    assert bypass(ref, text) == z
```

  - In `tests/test_post_chain.py` (imports gain `with_box` and `z_value`):

```python
def test_an_antennas_bypass_closes_its_port_with_a_short_or_the_box_alone():  # Stage 3 design 5.7
    f = np.linspace(1.84e9, 2.99e9, 5)
    z = np.array([10 + 5j, 3 - 40j, 0, 1e3j, 50])
    assert np.array_equal(with_box(z, f, C_BOX), z / (1 + 2j * np.pi * f * C_BOX * z))  # v1's, bit for bit
    assert np.array_equal(with_box(np.full(5, np.inf + 0j), f, C_BOX), 1 / (2j * np.pi * f * C_BOX))
    assert np.array_equal(z_value("L1", "0R", M0402, f, bypasses=True), np.zeros(5, complex))
    assert np.isposinf(z_value("C2", "open", M0402, f, bypasses=True).real).all()
    assert z_value("L1", "0R", M0402, f) is None and z_value("C2", "open", M0402, f) is None  # v1 reads no bypass
    assert np.array_equal(z_value("C3", "1pF", M0402, f, bypasses=True), z_part("C", 1e-12, M0402, f))
    zk = np.stack([with_box(z_value(ref, text, M0402, f, bypasses=True), f, C_BOX)
                   for ref, text in (("L1", "0R"), ("C2", "open"), ("C3", "1pF"))], -1)
    assert np.abs(terminate(star(f, 4), [0], zk, f) - terminate_np(star(f, 4), [0], zk)).max() <= 1e-12
```

  - In `tests/test_retune.py`:

```python
def test_an_antennas_retune_takes_0r_on_a_series_part_and_open_on_a_shunt_one(tmp_path):  # Stage 3 design 5.7; RF 1
    from test_cli_antenna import FIX as ANTENNAS, antenna_project
    p = load_project(antenna_project(tmp_path / "pi", ANTENNAS / "ifa2g4_pi.kicad_pcb"))
    new = assign(p, ["L1=0R", "C2=open", "C3=OPEN"], tmp_path)
    assert [(q["ref"], q["value"], q["s2p"]) for q in (*new["chain"]["series"], *new["chain"]["shunt"])] == [
        ("L1", "0R", None), ("C2", "open", None), ("C3", "OPEN", None)]
    for arg, code, params in [("C2=0R", "E_RETUNE_SHORT_SHUNT", {"ref": "C2", "net": "GND"}),
                              ("L1=open", "E_RETUNE_OPEN_SERIES", {"ref": "L1"}),
                              ("C2=0", "E_RETUNE_ANTENNA_VALUE", {"ref": "C2", "value": "0"})]:  # 0 F stays refused
        with pytest.raises(KrsError) as e:
            assign(p, [arg], tmp_path)
        assert (e.value.code, e.value.params) == (code, params)
    s2p = write_s2p(tmp_path / "c3.s2p", z_part("C", 1.2e-12, None, F), "shunt", F)  # S2P parts as in v1
    assert parts(assign(p, [f"C3={s2p}:shunt"], tmp_path))["C3"]["s2p"] == {"file": "c3.s2p", "connection": "shunt"}
    v1 = copy.deepcopy(project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")[1])
    for arg in ("L1=0R", "C2=open"):  # v1's retune reads no bypass
        with pytest.raises(KrsError) as e:
            assign(v1, [arg], tmp_path)
        assert (e.value.code, e.value.params) == ("E_RETUNE_VALUE", {"ref": arg[:2], "value": arg[3:]})
```

  - `tests/test_match_antenna.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.post.chain import with_box
from kicad_rf_studio.core.post.waves import band_grid
from kicad_rf_studio.core.project import load_project
from kicad_rf_studio.gui.control import default_series, snapped
from networks import C_BOX, read_s, star, terminate_np
from test_cli_antenna import FIX, antenna_project

BAND = (2.4e9, 2.4835e9)
OPEN = None  # a part port closed by its box's C alone


def pi_run(tmp_path, monkeypatch, board=FIX / "ifa2g4_pi.kicad_pcb"):
    """`board`, the pi variant by default, run on the network fake (its layout is star(f, 4)), with the cell C that
    verify reads stood in for at 6e-16 F, as test_verify.verified does: the project file."""
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    pj = antenna_project(tmp_path / board.stem, board, BAND)
    assert pipeline.run(pj) == 0
    return pj


def oracle(f, *z):
    """S11 of star(f, 4) at port 1, its three part ports closed in job order by `z`: each a Z_part on f across C_BOX,
    or OPEN."""
    zk = [1 / (2j * np.pi * f * C_BOX) if v is OPEN else with_box(v, f, C_BOX) for v in z]
    return terminate_np(star(f, 4), [0], np.stack(zk, -1))[:, 0, 0]


def chain_s11(pj):
    return read_s(pj.parent / "results" / "chain.s1p")[:, 0, 0]


def test_the_antenna_seen_through_its_feed_line(tmp_path, calibrated, monkeypatch):  # design 5.7; RF 2
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.retune(pj, ["L1=0R", "C2=open", "C3=open"]) == 0  # the series part shorted, both shunts removed
    f = band_grid(load_project(pj))
    assert np.abs(chain_s11(pj) - oracle(f, np.zeros(len(f)), OPEN, OPEN)).max() <= 1e-5


def test_snapping_leaves_a_bypass_as_typed():  # design 5.7: E24 snapping as in v1, the GUI's (Stage 2 design 5.3)
    typed = {"L1": "3.1nH", "C2": "0.95pF", "C3": "1.25pF", "R1": "0R", "C4": "open", "L2": "0R"}
    assert {ref: snapped(ref, text, default_series(ref)) for ref, text in typed.items()} == {
        "L1": "3nH", "C2": "0.91pF", "C3": "1.3pF", "R1": "0R", "C4": "open", "L2": "0R"}
```

  Probe (reviser): on the network fake's pi run, the layout closed by a short and two open boxes matched this oracle within 9.1e-7.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_values.py tests/test_post_chain.py tests/test_retune.py tests/test_match_antenna.py -q`. Expected: FAIL. `test_values.py` stops at `cannot import name 'bypass'` and `test_post_chain.py` at `cannot import name 'z_value'`; the two retune tests raise E_RETUNE_VALUE for `L1=0R` (probed on `main`). `test_snapping_leaves_a_bypass_as_typed` passes at once: it pins `gui.control.snapped` (port_value reads `open` and an L's `0R` as None, and an R snaps off), which plan 5's retune table runs on bypass texts.
- [ ] **Step 3: `values.py`.**
  - `OPEN_VALUE = "open"`, commented "an antenna chain part's value that removes it (Stage 3 design 5.7)".
  - `bypass(ref, text)`:
    - Docstring: "The impedance in Ω that an antenna chain part's value text stands for when it bypasses or removes the part (Stage 3 design 5.7): math.inf for OPEN_VALUE, in any case and with spaces around it; 0.0 for a 0 in ohms on any part (parse_value gives (0.0, "R"): 0R, 0Ω, 0ohm) or a value that part_value reads as 0 for an L or an R (0, 0nH); else None, for port_value. A C of 0 is no bypass: it stays port_value's open, which the retune refuses; nor is a 0 in a unit not the part's (0pF on an L)."
    - The checks run in the docstring's order, and the tests fix them.
- [ ] **Step 4: `chain.py`.**
  - **`z_value`:**
    - Docstring: "Z_part (F,) on f of the part `ref` from its value text `text` (spec 5.7, 7.2): with `bypasses` (an antenna's part, Stage 3 design 5.7), a bypass first, 0 or inf at every f with no package model; else z_part of its kind, port_value and `model`; None when the text reads as neither."
    - The bypass case is `np.full(len(f), z, complex)`.
  - **`part_impedances`** sets `z[ref] = z_value(ref, part["value"], part["model"], f, bypasses=antenna(project))` and raises E_PART_NO_VALUE when that is None. Its docstring adds "an antenna's bypasses (z_value)".
  - **`with_box`** keeps v1's expression bit for bit for a finite z (the golden pins hash lpf915's chain.s2p):

```python
    y = 2j * np.pi * f * c_box
    with np.errstate(invalid="ignore"):  # inf·0j in the unused branch
        return np.where(np.isinf(z), 1 / y, z / (1 + y * z))
```

    Its docstring adds "an open part's (z inf, Stage 3 design 5.7) is the box's capacitance alone, 1/(jω·c_box)".
- [ ] **Step 5: `assign`'s antenna branch,** between the S2P branch and the `port_value` branch, whose refusal it also names for an antenna:

```python
        elif antenna(new) and (z := bypass(ref, right)) is not None:
            if z == 0 and part in new["chain"]["shunt"] and not set(part["nets"]) <= set(new["chain"]["nets"]):
                raise KrsError("E_RETUNE_SHORT_SHUNT", ref=ref, net=part["nets"][1])
            if z == math.inf and part in new["chain"]["series"]:
                raise KrsError("E_RETUNE_OPEN_SERIES", ref=ref)
            part["value"], part["s2p"] = right, None
        elif port_value(ref, right) is None:
            raise KrsError("E_RETUNE_ANTENNA_VALUE" if antenna(new) else "E_RETUNE_VALUE", ref=ref, value=right)
```

  - A shunt part's nets are (chain side, other side), as the tracer stores them.
  - The docstring adds "for an antenna (Stage 3 design 5.7), a RIGHT that values.bypass reads is stored as typed too: 0 Ω on a series part or on a part across two chain nets, open on a shunt part; E_RETUNE_SHORT_SHUNT (0 Ω to a net off the chain) and E_RETUNE_OPEN_SERIES refuse the converse, and E_RETUNE_ANTENNA_VALUE, which names the bypass syntax, stands for E_RETUNE_VALUE".
  - Comment the branch `# ponytail: the tracer's shunt list decides: a series part beside a parallel one is still refused open; a shunt 0R the board itself holds keeps its 0 Ω, so verify then meets E_PORT_SHORT; start it open in new if a board ships one`.
- [ ] **Step 6: The messages,** after E_RETUNE_VALUE, each run through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| E_RETUNE_SHORT_SHUNT | {ref} joins the antenna's chain to {net}: 0 Ω there would short the chain to {net}. \`{ref}=0R\` replaces a series part with a short; \`{ref}=open\` removes a part like this one. | {ref} liga a cadeia da antena a {net}: 0 Ω ali poria a cadeia em curto com {net}. \`{ref}=0R\` troca um componente em série por um curto; \`{ref}=open\` retira um componente como este. |
| E_RETUNE_OPEN_SERIES | {ref} is a series part of the antenna's chain: open there would cut the antenna off its feed. \`{ref}=0R\` replaces it with a short; \`open\` removes a shunt part. | {ref} é um componente em série da cadeia da antena: em aberto ali, ele separaria a antena da alimentação. \`{ref}=0R\` o troca por um curto; \`open\` retira um componente shunt. |
| E_RETUNE_ANTENNA_VALUE | Cannot read "{value}" as the value of {ref}: on an antenna's chain a C, L or R takes a value in its own unit (4.7pF, 4p7, 15nH, 50R), \`{ref}=0R\` replaces a series part with a short and \`{ref}=open\` removes a shunt part (a C of 0 F could mean either, so it is refused), and any part takes an S2P file as {ref}=file.s2p:series (or :shunt). | Não foi possível ler "{value}" como o valor de {ref}: na cadeia de uma antena, um C, L ou R recebe um valor na própria unidade (4.7pF, 4p7, 15nH, 50R), \`{ref}=0R\` troca um componente em série por um curto e \`{ref}=open\` retira um componente shunt (um C de 0 F poderia ser qualquer um dos dois, então é recusado), e qualquer componente recebe um arquivo S2P como {ref}=file.s2p:series (ou :shunt). |

- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_gui.py tests/test_p0b.py tests/test_post_checks.py tests/test_sexpr.py -q`. Expected: PASS. `with_box`'s v1 bits and the GUI's retune session are unchanged.
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(retune): an antenna's chain parts take 0 Ω and open, a series part shorted and a shunt part removed, the converse refused (Stage 3 design 5.7)"
graphify update .
```

---

### Task 2 [code]: Every chain part a port

**Files:**
- Modify: `src/kicad_rf_studio/core/model/parts.py`: `project_parts`.
- Test: `tests/test_model_parts.py`, `tests/test_cli_antenna.py` and `tests/test_match_antenna.py`.

**Interfaces:**
- Consumes: Task 1's `OPEN_VALUE`, `bypass`, `pi_run`, `oracle` and `chain_s11`; `role`'s v1 rules.
- Produces:
  - `project_parts(..., antenna=True)`: every chain part is "port", or "curve_port" off a multiple of 90°, and a DNP chain part's value is `OPEN_VALUE`. The choke rule does not apply. W_VALUE_UNREADABLE leaves out an antenna's chain part whose value `bypass` reads. v1's roles still decide everything off the chain.
  - `tests/test_cli_antenna.placeholders(folder: Path) -> Path`, which later tasks import.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_model_parts.py`:

```python
def test_every_part_on_an_antennas_chain_is_a_port(mini_board):  # Stage 3 design 5.1: whatever its value
    from shapely.geometry import box
    from test_antenna_kicad import fp
    from test_tracer import smd
    from kicad_rf_studio.core.kicad.tracer import Chain, ChainPart
    lib = {k: f"{n}_SMD:{k}_0402_1005Metric" for k, n in (("R", "Resistor"), ("C", "Capacitor"), ("L", "Inductor"))}
    b = mini_board(fp("R9", lib["R"], smd(1, "RF"), smd(2, "RF2", x=2), value="0R")
                   + fp("C9", lib["C"], smd(1, "RF2"), smd(2, "GND", x=2), "(attr smd dnp)", at="5 0", value="1pF")
                   + fp("L8", lib["L"], smd(1, "RF2"), smd(2, "GND", x=2), at="10 0", value="22uH")  # a choke
                   + fp("L9", lib["L"], smd(1, "RF2"), smd(2, "GND", x=2), at="15 0 45", value="2.7nH")
                   + fp("C10", lib["C"], smd(1, "RF2"), smd(2, "GND", x=2), at="20 0", value="open"))  # typed as one

    def on(ref, nets):
        return ChainPart(ref, (f"{ref}.1", f"{ref}.2"), nets)

    chain = Chain("U1.1", "AE1.1", ("RF", "RF2"), (on("R9", ("RF", "RF2")),),
                  tuple(on(ref, ("RF2", "GND")) for ref in ("C9", "L8", "L9", "C10")))
    for antenna, expected, unreadable in (
            (True, [("R9", "port", "0R"), ("C9", "port", "open"), ("L8", "port", "22uH"), ("L9", "curve_port", "2.7nH"),
                    ("C10", "port", "open")], []),
            (False, [("R9", "copper", "0R"), ("C9", "open", "1pF"), ("L8", "open", "22uH"),  # v1's roles and notes
                     ("L9", "curve_port", "2.7nH"), ("C10", "port", "open")], [("W_VALUE_UNREADABLE", {"refs": "C10"})])):
        series, shunt, _, notes = project_parts(b, chain, classify(b), box(-5, -5, 25, 5), 70e6, 100e6, antenna=antenna)
        assert [(q["ref"], q["role"], q["value"]) for q in series + shunt] == expected
        assert [note for note in notes if note[0] == "W_VALUE_UNREADABLE"] == unreadable
```

    The band is 70–100 MHz so that 22 µH is a choke by v1's rule (probed: `is_choke` True there, False at 1.84–2.99 GHz).
  - In `tests/test_cli_antenna.py`:

```python
def placeholders(folder: Path) -> Path:
    """ifa2g4_pi with L1 made R1, a 0R, and C2 made DNP: a chain with both placeholders (Stage 3 design 5.1)."""
    text = (FIX / "ifa2g4_pi.kicad_pcb").read_text(encoding="utf-8")
    text = text.replace('(property "Reference" "L1"', '(property "Reference" "R1"', 1).replace(
        '(property "Value" "2.7nH"', '(property "Value" "0R"', 1)
    i = text.index("(attr smd)", text.index('(property "Reference" "C2"'))
    board = folder / "pi_placeholders.kicad_pcb"
    board.write_text(text[:i] + "(attr smd dnp)" + text[i + len("(attr smd)"):], encoding="utf-8")
    return board


def test_new_makes_every_chain_part_a_port(tmp_path):  # Stage 3 design 5.1
    pj, notes = cli.new_antenna(placeholders(tmp_path), "U1.1", "AE1", (2.4e9, 2.4835e9), output=tmp_path / "p")
    d = load_project(pj)
    assert [(q["ref"], q["role"], q["value"], q["dnp"]) for q in d["chain"]["series"] + d["chain"]["shunt"]] == [
        ("R1", "port", "0R", False), ("C2", "port", "open", True), ("C3", "port", "1pF", False)]
    assert [(p["ref"], p["value"], p["role"]) for code, p in notes if code == "I_PART"][:3] == [
        ("R1", "0R", "port"), ("C2", "open", "port"), ("C3", "1pF", "port")]  # new says so, part by part
    assert "W_VALUE_UNREADABLE" not in [code for code, _ in notes]
```

  - In `tests/test_match_antenna.py` (imports gain `z_part`, `M0402` from `test_post_chain` and `placeholders`):

```python
def test_a_placeholder_board_runs_its_placeholders_as_ports_there_and_back(tmp_path, calibrated, monkeypatch):  # RF 2
    pj = pi_run(tmp_path, monkeypatch, placeholders(tmp_path))
    f, chain = band_grid(load_project(pj)), pj.parent / "results" / "chain.s1p"
    short, c1, before = np.zeros(len(f)), z_part("C", 1e-12, M0402, f), chain.read_bytes()
    assert np.abs(chain_s11(pj) - oracle(f, short, OPEN, c1)).max() <= 1e-5  # R1 at 0 Ω, C2 open, C3 1 pF
    assert pipeline.retune(pj, ["C2=1pF"]) == 0  # the DNP placeholder fitted
    assert np.abs(chain_s11(pj) - oracle(f, short, c1, c1)).max() <= 1e-5
    assert pipeline.retune(pj, ["C2=open"]) == 0 and chain.read_bytes() == before  # and removed again
```

  The architect's probe of `placeholders` traced series [R1] and shunt [C2, C3]; today's code gives R1 copper and C2 open with value "1pF". With the chain parts set to ports by hand, the network fake ran the four jobs, converged at 6.90 ns, in 3.1 s: layout.s4p matched star(f, 4) within 1.2e-7 and chain.s1p its oracle within 7.3e-7. The reviser's probe found chain.s1p equal byte for byte across two identical writes.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_model_parts.py tests/test_cli_antenna.py tests/test_match_antenna.py -q`. Expected: FAIL: R9 reads as copper and C9 as open, new's project holds R1 as copper, and the placeholders' run has two ports, so its chain.s1p misses the four-port oracle.
- [ ] **Step 3: `project_parts`.**
  - Inside its `part()` helper, for `antenna` and a place of "series" or "shunt":
    - the role is CURVE_PORT when `fp.angle % 90`, else PORT;
    - the value is OPEN_VALUE when `fp.dnp`, else the footprint's text.
  - Comment it "every part on an antenna's chain is a port, whatever its value: a 0R, a DNP placeholder, a choke (Stage 3 design 5.1)".
  - W_VALUE_UNREADABLE leaves out an antenna's chain part whose value `bypass` reads; v1's notes stay as they are.
  - The docstring adds both.
- [ ] **Step 4: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_cli_new.py tests/test_run_antenna.py tests/test_antenna_geometry.py -q`. Expected: PASS. v1's roles are unchanged, and the pi variant's L1, C2 and C3 were ports already. `new` needs no new line: its I_PART lines print each chain part's role and value.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(project): every part on an antenna's chain is a part port, a 0R starting at 0 Ω and a DNP part open (Stage 3 design 5.1)"
graphify update .
```

---

### Task 3 [code]: A part-port run's results and the settings fingerprint

**Files:**
- Modify:
  - `src/kicad_rf_studio/pipeline.py`: `fingerprint` after `results_of`, `_run`, and `antenna_outputs`;
  - `src/kicad_rf_studio/core/post/antenna.py`: `draw_antenna` and `antenna_png`;
  - `src/kicad_rf_studio/core/messages.py`: I_ANTENNA_NO_FAR_FIELD after I_ANTENNA_FAR_FIELD;
  - `po/*` and the `.mo`;
  - `tests/fake_cli.py`: `patches()`;
  - `tests/test_run.py` L292.
- Test: `tests/test_match_antenna.py` and `tests/test_post_antenna.py`.

**Interfaces:**
- Consumes: Tasks 1–2; `antenna_outputs`' `what_if`; `runs.openems_versions`.
- Produces:
  - `pipeline.fingerprint(project: dict) -> dict`, and an antenna's `results["fingerprint"]`.
  - `draw_antenna(fig, f, s11, project, far, name, label=None)` and `antenna_png(f, s11, project, far, name, label=None)`.
  - I_ANTENNA_NO_FAR_FIELD `{command}`.
  - `fake_cli.patches()`'s `openems_versions`, openEMS 0.37.0 and CSXCAD 0.7.0 under the fake.
  - In `tests/test_match_antenna.py`: `result_lines(run_dir) -> list[tuple[str, dict]]`, which Tasks 5 and 6 use.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/fake_cli.py`, `patches()` gains `"openems_versions": lambda: ("0.37.0", "0.7.0")`, and its docstring "and openEMS 0.37.0 as the installed version". `check_openems` is patched there already; without this, a tier (a) machine with no openEMS would meet E_OPENEMS_MISSING in `fingerprint`.
  - In `tests/test_match_antenna.py` (imports gain `json`, `Path`, `__version__` and `render`):

```python
def result_lines(run_dir):
    events = (Path(run_dir) / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [(e["code"], e["params"]) for e in map(json.loads, events) if e["kind"] == "result"]


def test_a_part_port_run_says_where_its_far_field_comes_from(tmp_path, calibrated, monkeypatch):  # design 5.5, 5.7
    pj = pi_run(tmp_path, monkeypatch)
    d = load_project(pj)
    lines, verify = result_lines(d["results"]["run_dir"]), pipeline.command_line("kicad-rf-studio", "verify", str(pj))
    codes = [code for code, _ in lines]
    assert ("I_ANTENNA_NO_FAR_FIELD", {"command": verify}) in lines and d["results"]["far_field"] is None
    assert codes.index("I_ANTENNA_RELATIVE") < codes.index("I_ANTENNA_NO_FAR_FIELD") < codes.index("I_WHAT_IF")
    seen = []
    monkeypatch.setattr(pipeline, "antenna_png", lambda f, s11, project, far, name, label=None: seen.append(label) or b"")
    assert pipeline.retune(pj, []) == 0 and seen == [render("I_WHAT_IF", command=verify)]  # the PNG's label


def test_an_antenna_run_records_its_settings_fingerprint(tmp_path, calibrated):  # design 5.8
    pj = antenna_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    keys = ("preset", "mesh", "region", "band", "f0_hz", "t_max_s", "air_gap_mm", "boundary", "far_field", "stackup",
            "lid_height_mm")
    assert d["results"]["fingerprint"] == {**{key: d[key] for key in keys}, "start": "U1.1", "copper": "solid",
                                           "app": __version__, "openems": "0.37.0"}  # fake_cli's openems_versions
```

  - In `tests/test_post_antenna.py`:

```python
def test_the_summary_png_carries_the_what_if_label():  # design 5.7: under Stage 1 7.6's label, as summary.png
    d = antenna_dict()
    f = band_grid(d)
    fig = Figure()
    draw_antenna(fig, f, dip(f).astype(complex), d, None, "proj", "label")
    assert fig.get_suptitle() == (render("I_PLOT_ANTENNA_TITLE", name="proj") + "\n" + render("I_ANTENNA_RELATIVE")
                                  + "\nlabel")
```

  - In `tests/test_run.py`, L292 becomes `assert not {"far_field", "fingerprint"} & set(load_project(pj)["results"])  # a v1 run's results gain no key`.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_match_antenna.py tests/test_post_antenna.py tests/test_run.py -q`. Expected: FAIL: the run's lines hold no I_ANTENNA_NO_FAR_FIELD, its results hold no `fingerprint`, and `draw_antenna` takes no `label`.
- [ ] **Step 3: `fingerprint`.**
  - It returns project.json's preset, mesh, region, band, f0_hz, t_max_s, air_gap_mm, boundary, far_field, stackup and lid_height_mm under their own names, then "start" (the chain's start pad), "copper" "solid", "app" `__version__` and "openems" `runs.openems_versions()[0]`. `pipeline.py` imports `__version__` from `kicad_rf_studio`.
  - Docstring: "An antenna's settings fingerprint (Stage 3 design 5.8), recorded with each run's and verify's results: project.json's fields that set the model or the far field but no part value, the lid height and the start pad among them (typed per project, not in the board); the copper model; and the versions of this app and of openEMS as a worker sees it (runs.openems_versions: metadata in an isolated subprocess, nothing imported)."
  - Comment the copper `# ponytail: Stage 1 5.3's solid copper is the only model; plan 4's P3-C adds all-sheet copper as a project field, read here`.
- [ ] **Step 4: `_run`** adds `data["results"]["fingerprint"] = fingerprint(project)` beside `far_field` for an antenna. Its docstring says so.
- [ ] **Step 5: `antenna_outputs`.**
  - `label = render("I_WHAT_IF", **what_if) if res.what_if else None` goes to `antenna_png` as its `label`.
  - After `s11_lines`, when there is no `results["far_field"]` but there are part ports (`res.refs`), the line `("I_ANTENNA_NO_FAR_FIELD", what_if)` follows.
  - The docstring adds both.
- [ ] **Step 6: `draw_antenna` and `antenna_png`** take `label=None`. The suptitle gains `"\n" + label` when it is given (the what-if label, D-15, as `draw_summary`'s), and `antenna_png` passes `label` through. Both docstrings say so.
- [ ] **Step 7: The message,** after I_ANTENNA_FAR_FIELD, through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_ANTENNA_NO_FAR_FIELD | No far field for this run: a run with part ports records none, as its jobs hold ports where the matching parts sit; \`{command}\` runs one job with each part in the grid at its value, as an ideal part, and records it. | Sem campo distante para esta execução: uma execução com portas de componentes não registra nenhum, pois as tarefas dela têm portas onde ficam os componentes de casamento; \`{command}\` executa uma tarefa com cada componente na grade com o valor dele, como componente ideal, e o registra. |

- [ ] **Step 8: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_run_antenna.py tests/test_golden_v1.py tests/test_p0.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 9: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(run): a part-port antenna run says where its far field comes from, puts the what-if label on its summary and records the settings fingerprint (Stage 3 design 5.5, 5.7, 5.8)"
graphify update .
```

---

### Task 4 [code]: Verify's model of an antenna

**Files:**
- Modify: `src/kicad_rf_studio/core/model/spec.py`: `far_field_box` before `model_spec`, `model_spec`'s antenna block and `verify_spec`.
- Test: `tests/test_antenna_model.py`.

**Interfaces:**
- Consumes: Task 1's `bypass`; `model_spec`'s "nf2ff" block; `verify_spec`'s cell and fill.
- Produces:
  - `far_field_box(project: dict, board: Board, geom: Geometry) -> dict`.
  - `verify_spec(spec, parts, dump, dt, *, far_field: dict | None = None) -> dict`.

- [ ] **Step 1: Write the failing test,** in `tests/test_antenna_model.py` (imports gain `KrsError`, `parts`, `far_field_box`, `verify_spec`, and `spec` as `spec_module` from `core.model`):

```python
def test_verify_puts_an_antennas_network_in_the_grid_and_records_its_far_field(tmp_path, monkeypatch):  # 5.5, 5.7
    project, board, geom, _ = pipeline.load(antenna_project(tmp_path, FIX / "ifa2g4_pi.kicad_pcb"))
    spec = pipeline.build_model(project, board, geom).spec
    box = far_field_box(project, board, geom)
    assert box == {"f_hz": project["far_field"]["f_hz"], "center": [107.0, -109.0, 0.39]}  # the board's centre
    m0, b0, g0, _ = pipeline.load(antenna_project(tmp_path / "m0"))
    assert far_field_box(m0, b0, g0) == pipeline.build_model(m0, b0, g0).spec["nf2ff"]  # model_spec's, factored out
    by_ref = parts(project)
    by_ref["L1"]["value"], by_ref["C2"]["value"] = "0R", "open"  # the series part shorted, a shunt removed
    dump = tmp_path / "operator_dump.vtr"
    dump.write_bytes(b"")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    out = verify_spec(spec, by_ref, dump, 1e-13, far_field=box)
    assert [q["name"] for q in out["ports"]] == ["P1"] and [g["name"] for g in out["grid"]] == ["C3"]
    assert (out["nf2ff"], out["boundary"], out["join"]) == (box, "pml_8", spec["join"])
    l1 = next(q for q in spec["ports"] if q["name"] == "L1")
    lo, hi = ([f(a, b) for a, b in zip(l1["start"], l1["stop"])] for f in (min, max))
    assert out["metal"]["copper"][len(spec["metal"]["copper"])] == {  # L1 at 0 Ω: copper over its whole box
        "x": [lo[0], hi[0], hi[0], lo[0]], "y": [lo[1], lo[1], hi[1], hi[1]], "z": [lo[2], hi[2]]}
    with pytest.raises(KrsError) as e:  # a bypass is an antenna's: without the far-field box, v1's refusal
        verify_spec(spec, by_ref, dump, 1e-13)
    assert (e.value.code, e.value.params) == ("E_VERIFY_VALUE", {"ref": "L1", "value": "0R"})
    by_ref["C2"]["s2p"] = {"file": "c2.s2p", "connection": "shunt"}  # a placeholder given an S2P file is fitted
    with pytest.raises(KrsError) as e:  # and has no value verify can place, as v1 refuses one
        verify_spec(spec, by_ref, dump, 1e-13, far_field=box)
    assert (e.value.code, e.value.params) == ("E_VERIFY_VALUE", {"ref": "C2", "value": "open"})
    by_ref["C2"]["s2p"], by_ref["C3"]["value"] = None, "open"
    dump.unlink()  # nothing left in the grid, so no cell C to read
    assert verify_spec(spec, by_ref, dump, 1e-13, far_field=box)["grid"] == []
```

  Probe: the pi's outline is (87, −124, 127, −94) and its stack runs from −0.01 to 0.79 mm, so the centre is [107.0, −109.0, 0.39]. The run's model has the ports P1, L1, C2 and C3, no grid, and L1's box lies in the top copper slab, z 0.745–0.78 mm.
- [ ] **Step 2: Run it.** `.venv/Scripts/python -m pytest tests/test_antenna_model.py -q`. Expected: FAIL with `cannot import name 'far_field_box'`.
- [ ] **Step 3: `far_field_box`.**
  - Docstring: "An antenna's far-field box as the model spec's "nf2ff" holds it (Stage 3 design 5.5): project.json's far_field.f_hz about the board's centre, its outline's bounds' (else geom's crop's) centre at the stack's mid-height, to 1e-6 mm. model_spec writes it when no port is a part; verify, whose one job holds the network as applied, always (verify_spec)."
  - Its body is `model_spec`'s present centre code, which now calls it.
- [ ] **Step 4: `verify_spec`'s `far_field`.**
  - The `lo, hi` line moves up to just after `kind, text`. It is pure arithmetic, so v1's refusals keep their order.
  - Then, when `far_field is not None`, `parts[ref]["s2p"] is None` and `(z := bypass(ref, text)) is not None`:
    - at 0 Ω, append `{"x": [lo0, hi0, hi0, lo0], "y": [lo1, lo1, hi1, hi1], "z": [lo2, hi2]}` to `metal.copper`;
    - in either case, `continue`. An open part leaves nothing, and neither case reads the dump.
  - A part with an S2P file falls through to `port_value`, whose E_VERIFY_VALUE already tells the user to set its value in project.json.
  - `out["nf2ff"] = far_field` when it is given.
  - Docstring addition: "For an antenna (Stage 3 design 5.5, 5.7), `far_field` is its far-field box (far_field_box), which the copy records as "nf2ff", and a part whose value is a bypass (values.bypass) and that has no S2P file leaves the grid: at 0 Ω it is copper over its whole port box, open it is left out. A placeholder given an S2P file is a fitted part, refused as any value verify cannot place."
- [ ] **Step 5: Run it again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_model_spec.py tests/test_verify.py tests/test_post_real.py tests/test_p0b.py -q`. Expected: PASS. lpf915's verify model is pinned and unchanged.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(model): verify's model of an antenna holds the far-field box, a part at 0 Ω as copper over its box and an open part left out (Stage 3 design 5.5, 5.7)"
graphify update .
```

---

### Task 5 [code]: Verify's run, comparison and far field

**Files:**
- Modify:
  - `src/kicad_rf_studio/pipeline.py`: `verify`, `_model_phase`, `_run`'s unpacking, `_verify`, `_verify_antenna` after it, and `far_of` after `far_field`;
  - `src/kicad_rf_studio/core/post/antenna.py`: `ANTENNA_VERIFY_OUTPUTS`, `dip_resonance` and `compare_s11`;
  - `src/kicad_rf_studio/core/messages.py`: after I_VERIFY_SCOPE;
  - `po/*` and the `.mo`.
- Test: `tests/test_match_antenna.py` and `tests/test_post_antenna.py`.

**Interfaces:**
- Consumes: Task 1's `z_value`; Task 3's `fingerprint` and `result_lines`; Task 4's `far_field_box` and `verify_spec(..., far_field=)`; `far_field`, `far_field_of`, `resonance`, `LEVELS_DB`, `s11_lines`, `far_field_lines`, `antenna_png`, `farfield_csv`, `antenna_csv`, `indicator_lines`, `port_map` and `grid_lines`.
- Produces:
  - `post.antenna.ANTENNA_VERIFY_OUTPUTS = re.compile(r"verify\.s1p|verify_(farfield\.csv|summary\.(png|csv))")`.
  - `post.antenna.dip_resonance(f: np.ndarray, s11: np.ndarray) -> float | None`.
  - `post.antenna.compare_s11(a: np.ndarray, b: np.ndarray, f: np.ndarray, k0: int) -> dict`, with the keys `ds11_f0`, `ds11_max`, `f_res_hz`, `f_res_retune_hz` and `shift`, the last three None where `dip_resonance` gives none.
  - `pipeline.far_of(record: dict) -> dict | None`, which Tasks 6 and 8 reuse.
  - `_model_phase` returns `(project, board, geom, model)`.
  - An antenna's verify block: `{"model_hash", "base_hash", "values", "run_dir", "jobs", "compare", "far_field", "fingerprint"}`. `far_field` is `{grid: path relative to run_dir}`, or None. Tasks 6 and 8 read it.
  - The messages I_VERIFY_COMPARE_S11, I_VERIFY_SHIFT, I_RESONANCE_NOT_COMPARED and I_VERIFY_SCOPE_ANTENNA.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_post_antenna.py` (imports gain `compare_s11` and `dip_resonance`):

```python
def test_verify_compares_s11_and_the_resonance_with_the_retune():  # design 5.7; RF 5: a shallow minimum is no dip
    f = band_grid(antenna_dict())
    a, b = dip(f, 2.4495e9).astype(complex), dip(f, 2.438e9).astype(complex)  # each resonance on a grid point
    k0 = int(np.flatnonzero(f == 2.44175e9)[0])
    assert compare_s11(a, b, f, k0) == {
        "ds11_f0": pytest.approx(abs(a[k0] - b[k0])), "ds11_max": pytest.approx(np.abs(a - b).max()),
        "f_res_hz": pytest.approx(2.4495e9, abs=1), "f_res_retune_hz": pytest.approx(2.438e9, abs=1),
        "shift": pytest.approx(11.5e6 / 2.438e9, rel=1e-6)}
    flat = (0.9 - 0.3 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)).astype(complex)  # lowest |S11| -4.4 dB
    assert dip_resonance(f, flat) is None and dip_resonance(f, dip(f, 1.0e9, 0.3e9)) is None  # shallow; band's edge
    cmp = compare_s11(a, flat, f, k0)
    assert (cmp["f_res_hz"], cmp["f_res_retune_hz"], cmp["shift"]) == (pytest.approx(2.4495e9, abs=1), None, None)
```

    Probe: 2.438 and 2.4495 GHz are band-grid points with symmetric neighbours 2.875 MHz away, where the parabola finds a symmetric dip exactly (0.0 Hz off). The flat curve has no −6 dB point (reviser's probe).
  - In `tests/test_match_antenna.py` (imports gain `os`, `pytest`, `KrsError`, `ANTENNA_LIMITS` and `z_part`):

```python
def test_verify_runs_an_antennas_network_in_one_job_and_records_its_far_field(tmp_path, calibrated, monkeypatch):
    pj = pi_run(tmp_path, monkeypatch)  # design 5.1, 5.5, 5.7
    m0 = antenna_project(tmp_path / "m0")
    with pytest.raises(KrsError) as e:  # no part on the chain: its run is its far-field run
        pipeline.verify(m0)
    assert e.value.code == "E_VERIFY_NO_PARTS"
    with pytest.raises(KrsError) as e:  # nor anything to retune: v1's refusals stand (design 5.1)
        pipeline.retune(m0, ["C1=1pF"])
    assert e.value.code == "E_RETUNE_NO_PARTS"
    before = load_project(pj)["results"]
    assert pipeline.verify(pj) == 0  # one external port: no E_VERIFY_PORTS for an antenna
    d = load_project(pj)
    v, run_dir = d["verify"], Path(d["verify"]["run_dir"])
    assert d["results"] == before and set(v) == {"model_hash", "base_hash", "values", "run_dir", "jobs", "compare",
                                                 "far_field", "fingerprint"}
    assert v["values"] == {"L1": "2.7nH", "C2": "1pF", "C3": "1pF"} and v["fingerprint"] == before["fingerprint"]
    assert [(j["port"], j["verdict"]) for j in v["jobs"]] == [("P1", "converged")]
    model = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    assert [q["name"] for q in model["ports"]] == ["P1"] and [g["name"] for g in model["grid"]] == ["L1", "C2", "C3"]
    assert model["nf2ff"]["f_hz"] == d["far_field"]["f_hz"] and list(v["far_field"]) == ["sphere", "elevation", "azimuth"]
    assert all((run_dir / p).is_file() for p in v["far_field"].values())
    f = band_grid(d)
    retuned = oracle(f, *(z_part(k, x, None, f) for k, x in (("L", 2.7e-9), ("C", 1e-12), ("C", 1e-12))))  # ideal
    assert v["compare"]["ds11_max"] == pytest.approx(np.abs(star(f, 1)[:, 0, 0] - retuned).max(), abs=1e-4)
    assert v["compare"]["shift"] is None  # star(f, 1) has no dip: its |S11| is 0.9025 at every f
    assert sorted(p.name for p in (pj.parent / "results").iterdir()) == [
        "antenna_summary.png", "chain.s1p", "layout.s4p", "verify.s1p", "verify_farfield.csv", "verify_summary.csv",
        "verify_summary.png"]
    codes = [code for code, _ in result_lines(run_dir)]
    assert codes[0] == "I_VERIFY_RESULTS" and codes.index("I_ANTENNA_RELATIVE") < codes.index("I_VERIFY_COMPARE_S11")
    assert codes[codes.index("I_VERIFY_COMPARE_S11") + 1] == "I_RESONANCE_NOT_COMPARED"
    assert codes.count("I_ANTENNA_FAR_FIELD") == 2  # the fixture's 2 f
    assert not {"I_VERIFY_LOSS_BUDGET", "W_VERIFY_LOSS_BUDGET"} & set(codes)
    assert codes[-7:] == ["I_OUTPUTS", "I_VERIFY_SCOPE_ANTENNA", *ANTENNA_LIMITS]


def test_verify_of_the_antenna_through_its_feed_line(tmp_path, calibrated, monkeypatch):  # design 5.7; RF 2
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.retune(pj, ["L1=0R", "C2=open", "C3=open"]) == 0
    monkeypatch.setattr(spec_module, "c_box", None)  # nothing in the grid: verify reads no cell C
    assert pipeline.verify(pj) == 0
    d = load_project(pj)
    run = json.loads((Path(d["results"]["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    model = json.loads((Path(d["verify"]["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    assert model["grid"] == [] and len(model["metal"]["copper"]) == len(run["metal"]["copper"]) + 1  # L1's box
    assert d["verify"]["values"] == {"L1": "0R", "C2": "open", "C3": "open"}


@pytest.mark.parametrize(("held", "stored", "written"), [
    ("verify_summary.png", True, None),  # stored with its far field; the second write refused, so no I_OUTPUTS
    ("project.json", False, "verify.s1p, verify_summary.png")])  # nothing stored, so no transform; the first write's
def test_a_held_file_costs_an_antennas_verify_only_that_file(tmp_path, calibrated, monkeypatch, held, stored, written):
    pj = pi_run(tmp_path, monkeypatch)  # RF 3; as test_verify's HELD
    real = os.replace

    def replace(src, dst):  # another program holds the file: an image viewer, an indexer
        if Path(dst).name == held:
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    assert pipeline.verify(pj) == 2
    d = load_project(pj)
    assert ("verify" in d) is stored
    assert not stored or list(d["verify"]["far_field"]) == ["sphere", "elevation", "azimuth"]
    (own,) = [p for p in (calibrated / "runs").iterdir() if str(p) != d["results"]["run_dir"]]  # verify's run folder
    events = [json.loads(line) for line in (own / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["kind"] for e in events if e["code"] == "E_RESULTS_WRITE"] == ["message"]  # one, the write that stands
    lines = result_lines(own)
    assert ("I_VERIFY_RESULTS" in [code for code, _ in lines]) is stored
    assert [p["files"] for code, p in lines if code == "I_OUTPUTS"] == ([written] if written else [])
    assert [code for code, _ in lines][-6:] == ["I_VERIFY_SCOPE_ANTENNA", *ANTENNA_LIMITS]


def test_a_verify_whose_transform_fails_keeps_its_comparison(tmp_path, calibrated, monkeypatch):  # RF 3
    pj = pi_run(tmp_path, monkeypatch)

    def fail(*_, **__):
        raise KrsError("E_WORKER_FAILED", job="T_JOB_FAR_FIELD", exit_code=1, log="log.txt")

    monkeypatch.setattr(pipeline, "far_field", fail)
    assert pipeline.verify(pj) == 2
    v = load_project(pj)["verify"]
    events = [json.loads(line) for line in (Path(v["run_dir"]) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert v["far_field"] is None and "ds11_f0" in v["compare"]
    assert [e["kind"] for e in events if e["code"] == "E_WORKER_FAILED"] == ["message"]
    written = sorted(p.name for p in (pj.parent / "results").iterdir())
    assert {"verify.s1p", "verify_summary.png"} <= set(written) and "verify_farfield.csv" not in written
    assert [p["files"] for c, p in result_lines(v["run_dir"]) if c == "I_OUTPUTS"] == ["verify.s1p, verify_summary.png"]


def test_a_stopped_verify_transform_keeps_the_comparison(tmp_path, calibrated, monkeypatch):  # RF 3; Stage 1 7.8
    pj = pi_run(tmp_path, monkeypatch)

    def stop(*_, **__):
        raise KeyboardInterrupt  # STOP or Ctrl+C during the transform

    monkeypatch.setattr(pipeline, "far_field", stop)
    with pytest.raises(KeyboardInterrupt):
        pipeline.verify(pj)
    v = load_project(pj)["verify"]
    assert v["far_field"] is None and [j["verdict"] for j in v["jobs"]] == ["converged"]
    assert [code for code, _ in result_lines(v["run_dir"])] == ["I_VERIFY_RESULTS"]  # said before the transform
    assert (pj.parent / "results" / "verify.s1p").is_file()
    assert not (pj.parent / "results" / "verify_farfield.csv").exists()
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_match_antenna.py tests/test_post_antenna.py -q`. Expected: FAIL with `cannot import name 'compare_s11'`.
- [ ] **Step 3: `post/antenna.py`.**
  - `ANTENNA_VERIFY_OUTPUTS` as given, commented "verify's files for an antenna (Stage 3 design 5.6, 5.7), which ANTENNA_OUTPUTS never matches, so a retune leaves them".
  - **`dip_resonance(f, s11)`:** "The refined resonance (resonance) of `s11` on `f` when its lowest |S11| marks a dip: at or below the −6 dB marker (LEVELS_DB) at a point inside the grid; else None, as the argmin of a shallow minimum, or one at the grid's edge, moves with the model's noise (Stage 3 plan 3)." Comment it `# ponytail: a depth screen; a broad -7 dB minimum still passes it, and P3-D's noise floor decides`.
  - **`compare_s11(a, b, f, k0)`:** its docstring is "How the retune's S11 `b` differs from verify's `a`, each (F,) on f (Stage 3 design 5.7), as checks.compare does for v1: |ΔS11| at the grid index k0 (f0), the largest |ΔS11| over f (up to f2), each one's dip_resonance and, only when both have one, the shift (f_a − f_b)/f_b; plain floats, None for a resonance or a shift there is not."
- [ ] **Step 4: `verify` and `_model_phase`.**
  - In `verify`, E_VERIFY_PORTS becomes `len(project["ports"]) < 2 and not antenna(project)`. Its docstring adds "an antenna's one external port excepted (Stage 3 design 5.7)".
  - `_model_phase` returns `project, board, geom, model`, and its docstring says so. `_run` unpacks `project, _, geom, model = built`.
- [ ] **Step 5: `_verify` and `far_of`.**
  - **`_verify`**, with `ant = antenna(project)`:
    - `project, board, geom, model = built`;
    - `vspec = verify_spec(model.spec, by_ref, dump, results["dt"], far_field=far_field_box(project, board, geom) if ant else None)`;
    - the loads are `zk = loads({ref: z_value(ref, values[ref], None, lay.f, bypasses=ant) for ref in refs}, ...)`, which is v1's own expression when `ant` is False;
    - after `own = layout(...)`, for an antenna: `return _verify_antenna(path, run_dir, project, vspec, values, own, terminate(lay.s, ext, zk, lay.f)[:, 0, 0], done, wall_s)`.

    v1's code below it is unchanged.
  - **`far_of(record)`:** "far_field_of of the run `record` holds, project.json's results or its verify (Stage 3 design 5.5): its far_field files and its first job's waves, in its run_dir; None when it records no far field. Raises far_field_of's E_RESULTS_WAVES."
- [ ] **Step 6: `_verify_antenna(path, run_dir, project, vspec, values, own, retuned, done, wall_s) -> int`.**
  - **Docstring:** "_verify's end for an antenna (Stage 3 design 5.5–5.7), with `own` verify's one-port layout and `retuned` the retune's S11 at the same ideal values; `results` is project["results"], as results_of checked it. The comparison (compare_s11, k0 own's f0 marker) is stored in project.json's verify with far_field null and fingerprint(project), and I_VERIFY_RESULTS emitted at once, as _run emits I_RESULTS before its transform. Then verify.s1p (port_map and grid_lines, as v1's) and verify_summary.png without a far field are written (ANTENNA_VERIFY_OUTPUTS), so that a stopped transform leaves them, as it leaves a run's S. Only when the comparison was stored, the far field is transformed from verify's job (far_field, the project's step), stored and read back (far_of), and all four files written again with it, S11 at the far field's frequencies from verify's own layout there (no part port: layout gives it in any order). That second write supersedes the first, whose refusal is said only when no second write follows. A refusal of a store, a write or the transform is an E_ line; a stopped transform propagates, the comparison stored and verify's S file kept. The lines after I_VERIFY_RESULTS: s11_lines of verify's S11, I_VERIFY_COMPARE_S11, I_VERIFY_SHIFT or I_RESONANCE_NOT_COMPARED, far_field_lines, indicator_lines with no loss budget, the E_ lines, I_OUTPUTS naming the files of the write that stands when it succeeded, I_VERIFY_SCOPE_ANTENNA and ANTENNA_LIMITS; each emitted as v1's are; 0, or 2 after an E_ line."
  - **The files:** verify_summary.png is `antenna_png(own.f, own.s[:, 0, 0], project, far, path.absolute().parent.name)`, with no label: verify is the full simulation, not a what-if. verify_summary.csv is `antenna_csv(far, layout(project, basis, far["sphere"].f).s[:, 0, 0])`, `basis` as v1's.
  - Comment the grid lines `# ponytail: verify.s1p's grid lines name the grid parts only; a bypassed part is in project.json's verify.values`.
  - **I_VERIFY_COMPARE_S11's params:**
    - `f0_mhz`: `f"{own.f[k0] / 1e6:g}"`;
    - `a_db`: `f"{own.a_db[k0]:.1f}"`;
    - `ds11` and `ds11_max`: `:.4f`.
  - **I_VERIFY_SHIFT's params:** `f_res_mhz` and `f_res_retune_mhz`, `:.1f` of each in MHz, and `shift_pct`, `f"{100 * shift:+.2f}"`.
  - **The verify block:** `{"model_hash": spec_hash(vspec), "base_hash": results["model_hash"], "values", "run_dir", "jobs": done, "compare", "far_field", "fingerprint"}`. `far_field` holds `{grid: p.relative_to(run_dir).as_posix()}`, as `_run`'s does.
- [ ] **Step 7: The messages,** after I_VERIFY_SCOPE, each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_VERIFY_COMPARE_S11 | verify against the retune at the same ideal values: \|ΔS11\| {ds11} at f0 = {f0_mhz} MHz (\|a\| {a_db} dB) and {ds11_max} at most up to f2. | Verificação contra o ajuste com os mesmos valores ideais: \|ΔS11\| {ds11} em f0 = {f0_mhz} MHz (\|a\| {a_db} dB) e no máximo {ds11_max} até f2. |
| I_VERIFY_SHIFT | Resonance at {f_res_mhz} MHz in verify against {f_res_retune_mhz} MHz in the retune: a shift of {shift_pct} %. | Ressonância em {f_res_mhz} MHz na verificação contra {f_res_retune_mhz} MHz no ajuste: um deslocamento de {shift_pct} %. |
| I_RESONANCE_NOT_COMPARED | Resonance: not compared, as the lowest \|S11\| of one of the two stays above -6 dB or sits at the edge of the simulated band, where it would move with the model's noise. | Ressonância: não comparada, pois o \|S11\| mínimo de uma das duas fica acima de -6 dB ou na borda da banda simulada, onde mudaria com o ruído do modelo. |
| I_VERIFY_SCOPE_ANTENNA | verify checks the layout reduction, not the vendor part data: each part sat in the grid at its value as an ideal part, without the package ESL, ESR and Cp or the S2P data the retune applies, a 0 Ω part as copper and an open part left out, against a retune at the same ideal values; its far field holds that ideal network. | A verificação confere a redução do layout, não os dados de componente do fabricante: cada componente ficou na grade com o valor dele como componente ideal, sem o ESL, o ESR e o Cp do encapsulamento nem os dados S2P que o ajuste aplica, um componente de 0 Ω como cobre e um em aberto deixado de fora, contra um ajuste com os mesmos valores ideais; o campo distante dela contém essa rede ideal. |

- [ ] **Step 8: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_verify.py tests/test_run_antenna.py tests/test_golden_v1.py tests/test_gui.py tests/test_sexpr.py -q`. Expected: PASS. v1's verify keeps its lines, files and refusals, E_VERIFY_PORTS among them.
- [ ] **Step 9: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(verify): an antenna's verify runs its network in one job, compares S11 and the resonance with the retune and records the far field (Stage 3 design 5.5, 5.7)"
graphify update .
```

---

### Task 6 [code]: The retune's what-if total efficiency

**Files:**
- Modify:
  - `src/kicad_rf_studio/pipeline.py`: `chain_results`, `s11_at` and `current_verify` before `antenna_outputs`, and `antenna_outputs`;
  - `src/kicad_rf_studio/core/post/antenna.py`: `eta_what_if_lines` after `far_field_lines`;
  - `src/kicad_rf_studio/core/messages.py`: I_ANTENNA_ETA_WHAT_IF after I_ANTENNA_NO_FAR_FIELD;
  - `po/*` and the `.mo`.
- Test: `tests/test_post_antenna.py` and `tests/test_match_antenna.py`.

**Interfaces:**
- Consumes: Task 5's verify block and `far_of`; Task 3's I_ANTENNA_NO_FAR_FIELD branch; `loss_budget`.
- Produces:
  - `eta_what_if_lines(far: dict, p: np.ndarray) -> list[tuple[str, dict]]`.
  - `ChainResults.p_layout` for an antenna: loss_budget's P_layout, which no line reports.
  - `pipeline.s11_at(path: Path, project: dict, f: np.ndarray) -> tuple[np.ndarray, np.ndarray]`, public for plan 5's retune session.
  - `pipeline.current_verify(project: dict) -> dict | None`, which Task 8 and plan 5 reuse.
  - I_ANTENNA_ETA_WHAT_IF `{f_mhz, eta_tot_pct, eta_rad_pct, delivered_pct}`.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_post_antenna.py` (imports gain `from types import SimpleNamespace` and `eta_what_if_lines`):

```python
def test_the_what_if_total_efficiency_takes_eta_rad_from_the_far_field():  # design 5.7
    far = {"sphere": SimpleNamespace(f=np.array([2.45e9, 2.4e9])), "eff": {"eta_rad": np.array([0.8, 0.9])}}
    assert eta_what_if_lines(far, np.array([0.99, 0.75])) == [
        ("I_ANTENNA_ETA_WHAT_IF", {"f_mhz": "2400.0", "eta_tot_pct": "67.5", "eta_rad_pct": "90.0",
                                   "delivered_pct": "75.0"}),
        ("I_ANTENNA_ETA_WHAT_IF", {"f_mhz": "2450.0", "eta_tot_pct": "79.2", "eta_rad_pct": "80.0",
                                   "delivered_pct": "99.0"})]
```

  - In `tests/test_match_antenna.py` (imports gain `shutil`, `save_project`, `loss_budget` and `eta_what_if_lines`):

```python
def test_after_verify_the_retune_shows_the_what_if_total_efficiency(tmp_path, calibrated, monkeypatch):  # 5.7; RF 4
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.verify(pj) == 0

    def retune(*assignments):
        lines = []
        assert pipeline.retune(pj, list(assignments), lambda code, params: lines.append((code, params))) == 0
        return lines

    lines = retune("C3=1.2pF")
    d = load_project(pj)
    v = d["verify"]
    assert pipeline.current_verify(d) == v and {"verify.s1p", "verify_farfield.csv", "verify_summary.csv",
                                                "verify_summary.png"} <= {p.name for p in (pj.parent / "results").iterdir()}
    far = pipeline.far_of(v)
    ff, up = far["sphere"].f, np.argsort(far["sphere"].f)  # the lines run by ascending frequency
    zk = np.stack([with_box(z_part(k, x, M0402, ff), ff, C_BOX)
                   for k, x in (("L", 2.7e-9), ("C", 1e-12), ("C", 1.2e-12))], -1)  # the retune's presets
    p = loss_budget(star(ff, 4), [0], zk)  # the fake's layout is star(f, 4) at any f
    got = [params for code, params in lines if code == "I_ANTENNA_ETA_WHAT_IF"]
    assert [float(g["delivered_pct"]) for g in got] == pytest.approx(100 * p[up], abs=0.06)
    assert [g["eta_rad_pct"] for g in got] == [f"{100 * x:.1f}" for x in far["eff"]["eta_rad"][up]]
    assert "I_ANTENNA_NO_FAR_FIELD" not in [code for code, _ in lines]
    for verify in ({**v, "far_field": None}, {**v, "base_hash": "0" * 64}):  # its transform failed; another run's
        save_project(pj, {**d, "verify": verify})
        assert (pipeline.current_verify(load_project(pj)) is None) is (verify["base_hash"] != v["base_hash"])
        assert "I_ANTENNA_NO_FAR_FIELD" in [code for code, _ in retune()]
    save_project(pj, {**d, "verify": v})
    shutil.rmtree(v["run_dir"])  # verify's folder deleted
    codes = [code for code, _ in retune()]
    assert pipeline.current_verify(load_project(pj)) is None
    assert "I_ANTENNA_NO_FAR_FIELD" in codes and "I_ANTENNA_ETA_WHAT_IF" not in codes
```

  Probe (reviser): at the far-field fixture's two frequencies, the loss budget of the fake's layout matched star(f, 4)'s within 5.7e-8, so the tolerance covers only the display's rounding.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_antenna.py tests/test_match_antenna.py -q`. Expected: FAIL with `cannot import name 'eta_what_if_lines'`.
- [ ] **Step 3: `eta_what_if_lines`.** Its docstring is "The instant retune's total efficiency where the project has a current verify with a far field (Stage 3 design 5.7): one I_ANTENNA_ETA_WHAT_IF per frequency of far_field_of's `far`, ascending, η_tot = η_rad·p, with η_rad from `far` and `p` (in far's order) the share of the incident power this retune's network passes to the board, loss_budget's P_layout: the design's 1 − |S11|² for a lossless network, less the parts' own loss otherwise; labelled what-if, as a lossless network that does not radiate leaves η_rad and the pattern as they are." The percentages use `:.1f`, and `f_mhz` uses `:.1f` of MHz.
- [ ] **Step 4: `chain_results`.** In its branch for P other than 2, an antenna's `p_layout = loss_budget(lay.s, ext, zk)`, commented "the power the board takes, for the what-if η_tot; no line reports it (design 5.6)"; v1 keeps W_NOT_TWO_PORT and `p_layout` None. The ChainResults docstring says so.
- [ ] **Step 5: `s11_at`, `current_verify` and `antenna_outputs`.**
  - **`s11_at`:** its docstring is "S11 and the loss budget's P_layout (each (F,), in f's order) of the chain at the frequencies `f` (Hz): the run's layout there, every part port closed as chain_results closes it (scikit-rf takes f ascending)". Its body is plan 2's three lines in `antenna_outputs` (`up`, `at`, `s11`), which now call it.
  - **`current_verify`:** its docstring is "project.json's verify block while it is of the model its results hold and its run folder still holds it (Stage 3 design 5.7, 5.8): its base_hash the results' model_hash, and its model.json, its jobs' waves and, when it records a far field, its far-field files present; else None (none, another run's, or its folder moved or deleted). The what-if η_tot and compare read verify through it."
  - **`antenna_outputs`:** the M = 0 branch reads the run's far field with `far_of(results)` and S11 there with `s11_at`. When the run has no far field and there are part ports (`res.refs`): with a current verify whose `far_of` gives a far field, `eta_what_if_lines(that far field, s11_at(path, project, its frequencies)[1])`; else Task 3's I_ANTENNA_NO_FAR_FIELD. Verify's far field goes into no file of the run's. The docstring adds the branch.
  - Comment it `# ponytail: η_rad from verify's ideal network (no package model), the network assumed not to radiate nor to change the board's own loss; the line says what-if`.
- [ ] **Step 6: The message,** after I_ANTENNA_NO_FAR_FIELD, through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_ANTENNA_ETA_WHAT_IF | {f_mhz} MHz: total efficiency {eta_tot_pct} % what-if: the last verify's radiation efficiency {eta_rad_pct} % times the {delivered_pct} % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are. | {f_mhz} MHz: eficiência total hipotética de {eta_tot_pct} %: a eficiência de radiação da última verificação, {eta_rad_pct} %, vezes os {delivered_pct} % da potência incidente que a rede deste ajuste entrega à placa (a eficiência de descasamento menos a perda dos próprios componentes); uma rede sem perdas que não irradia mantém a eficiência de radiação e o diagrama como estão. |

- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_run_antenna.py tests/test_retune.py tests/test_gui_control.py tests/test_golden_v1.py tests/test_sexpr.py -q`. Expected: PASS. An M = 0 run's far-field files and lines are unchanged.
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(retune): after verify, the retune shows the what-if total efficiency from verify's radiation efficiency and the power its network passes to the board (Stage 3 design 5.7)"
graphify update .
```

---

### Task 7 [code]: The deltas and their significance

**Files:**
- Modify:
  - `src/kicad_rf_studio/core/post/antenna.py`: the constants and the three functions, after `eta_what_if_lines`;
  - `src/kicad_rf_studio/core/messages.py`: the compare lines after I_ANTENNA_ETA_WHAT_IF, and the terms after T_STOPPED;
  - `po/*` and the `.mo`.
- Test: `tests/test_post_antenna.py`.

**Interfaces:**
- Consumes: Task 5's `dip_resonance` and I_RESONANCE_NOT_COMPARED; `bandwidth` and `_markers`; `far_field_of`'s shape (`sphere.f`, `eff`).
- Produces:
  - `SHIFT_LIMIT = 0.003` and `DB_LIMIT = 0.2`.
  - `DELTA_COLUMNS = ("quantity", "marker", "f_hz", "base", "variant", "unit", "delta", "delta_unit", "threshold", "resolved")`.
  - `deltas(project: dict, f: np.ndarray, base: tuple[np.ndarray, dict | None], variant: tuple[np.ndarray, dict | None]) -> list[dict]`.
  - `delta_lines(project: dict, rows: list[dict]) -> list[tuple[str, dict]]` and `deltas_csv(rows: list[dict]) -> bytes`.
  - Messages: I_COMPARE_RESONANCE, I_COMPARE_BANDWIDTH, I_COMPARE_NO_BANDWIDTH, I_COMPARE_ETA, I_COMPARE_GAIN, I_COMPARE_NO_FAR_FIELD and I_COMPARE_THRESHOLDS; the terms T_RESOLVED and T_NOT_RESOLVED.

- [ ] **Step 1: Write the failing tests,** in `tests/test_post_antenna.py` (imports gain `DELTA_COLUMNS`, `deltas`, `delta_lines` and `deltas_csv`):

```python
def far(eta, gain):  # far_field_of's shape for the deltas: f0, f_lo and f_hi recorded, in that order
    return {"sphere": SimpleNamespace(f=np.array([2.44175e9, 2.4e9, 2.4835e9])),
            "eff": {"eta_tot": np.array(eta), "gain": np.array(gain)}}


def up(db):  # 0.5 raised by db
    return 0.5 * 10 ** (db / 10)


def pair(f):  # a resonance 11.5 MHz up with a wider dip, η_tot +0.1, +0.3 and 0 dB at f_lo, f0 and f_hi, gain -0.25 dB
    return ((dip(f, 2.438e9), far([0.5, 0.5, 0.5], [1.5, 1.0, 1.0])),
            (dip(f, 2.4495e9, 0.12e9), far([up(0.3), up(0.1), 0.5], [1.5 * 10 ** -0.025, 1.0, 1.0])))


def test_the_deltas_and_whether_each_is_resolved():  # design 5.8
    d = antenna_dict()
    f = band_grid(d)
    rows = deltas(d, f, *pair(f))
    assert [(r["quantity"], r["marker"], r["unit"], r["delta_unit"], r["resolved"]) for r in rows] == [
        ("resonance", "", "MHz", "MHz", True), ("bandwidth_10db", "", "MHz", "MHz", True),
        ("eta_tot", "f_lo", "%", "dB", False), ("eta_tot", "f0", "%", "dB", True), ("eta_tot", "f_hi", "%", "dB", False),
        ("peak_gain", "f0", "dBi", "dB", True)]
    assert (rows[0]["base"], rows[0]["variant"], rows[0]["delta"]) == pytest.approx((2438.0, 2449.5, 11.5), abs=1e-6)
    assert rows[0]["threshold"] == pytest.approx(7.32525) and rows[2]["threshold"] == 0.2  # 0.3 % of f0; 0.2 dB
    assert rows[1]["delta"] == pytest.approx(24.52, abs=0.05)  # 122.63 to 147.14 MHz, interpolated in dB
    assert (rows[3]["f_hz"], rows[3]["base"], rows[3]["delta"]) == pytest.approx((2.44175e9, 50.0, 0.3))
    assert rows[5]["delta"] == pytest.approx(-0.25) and rows[5]["base"] == pytest.approx(10 * np.log10(1.5))


def test_far_field_deltas_need_both_far_fields():  # design 5.8; RF 5
    d = antenna_dict()
    f = band_grid(d)
    rows = deltas(d, f, (dip(f, 2.438e9), far([0.5] * 3, [1.0] * 3)), (dip(f, 2.435125e9), None))
    assert [r["quantity"] for r in rows] == ["resonance", "bandwidth_10db"]
    assert rows[0]["delta"] == pytest.approx(-2.875, abs=1e-6) and rows[0]["resolved"] is False  # 0.12 % of f0
    shallow = 0.9 - 0.5 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)  # lowest |S11| -8 dB: no -10 dB bandwidth
    bw = deltas(d, f, (dip(f, 2.438e9), None), (shallow, None))[1]
    assert bw["base"] == pytest.approx(122.63, abs=0.05) and (bw["variant"], bw["delta"], bw["resolved"]) == (
        None, None, None)
    flat = 0.9 - 0.3 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)  # lowest |S11| -4.4 dB: no resonance to judge
    res = deltas(d, f, (dip(f, 2.438e9), None), (flat, None))[0]
    assert (res["base"], res["variant"], res["delta"], res["resolved"]) == (pytest.approx(2438.0), None, None, None)


def test_the_delta_lines_and_csv():  # design 5.8
    d = antenna_dict()
    f = band_grid(d)
    rows = deltas(d, f, *pair(f))
    lines = delta_lines(d, rows)
    assert [code for code, _ in lines] == ["I_COMPARE_RESONANCE", "I_COMPARE_BANDWIDTH", "I_COMPARE_ETA",
                                           "I_COMPARE_ETA", "I_COMPARE_ETA", "I_COMPARE_GAIN", "I_COMPARE_THRESHOLDS"]
    assert lines[0][1] == {"base_mhz": "2438.0", "variant_mhz": "2449.5", "shift_mhz": "+11.5", "shift_pct": "+0.47",
                           "verdict": "T_RESOLVED"}
    assert lines[3][1] == {"marker": "f0", "f_mhz": "2441.8", "base_pct": "50.0", "variant_pct": "53.6",
                           "delta_db": "+0.30", "verdict": "T_RESOLVED"}
    assert lines[-1][1] == {"shift_pct": "0.3", "db": "0.2"}
    shallow = 0.9 - 0.5 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)
    flat = 0.9 - 0.3 * np.exp(-((f - 2.438e9) / 0.1e9) ** 2)
    assert [code for code, _ in delta_lines(d, deltas(d, f, (dip(f, 2.438e9), None), (shallow, None)))] == [
        "I_COMPARE_RESONANCE", "I_COMPARE_NO_BANDWIDTH", "I_COMPARE_NO_FAR_FIELD", "I_COMPARE_THRESHOLDS"]
    assert [code for code, _ in delta_lines(d, deltas(d, f, (dip(f, 2.438e9), None), (flat, None)))][0] == (
        "I_RESONANCE_NOT_COMPARED")
    table = list(csv.reader(io.StringIO(deltas_csv(rows).decode())))
    assert table[0] == list(DELTA_COLUMNS) and len(table) == 7 and table[1][-1] == "True"
```

  Probe: the bandwidths are 122.63 and 147.14 MHz (theory 122.59 and 147.11). 2.435125 GHz is a symmetric grid point; the shallow dip reaches −8 dB, under the −6 dB screen, and has no −10 dB crossing; the flat one reaches −4.4 dB.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_antenna.py -q`. Expected: FAIL with `cannot import name 'DELTA_COLUMNS'`.
- [ ] **Step 3: The constants.** `SHIFT_LIMIT, DB_LIMIT = 0.003, 0.2`, commented "design 5.8: a delta is resolved above 0.3 % of f0 for a frequency and 0.2 dB for an efficiency or a gain", plus `# ponytail: the design's provisional defaults; plan 4's P3-D sets them at three times its measured noise floor`.
- [ ] **Step 4: `deltas`.**
  - **Docstring:** "The deltas of `variant` against `base` (Stage 3 design 5.8), each (S11 (F,) on f, far_field_of's dict or None), as rows of DELTA_COLUMNS (None for no value): `unit` is base's and variant's, `delta_unit` the delta's and the threshold's."
  - **Rows, in order:**
    - "resonance": each one's dip_resonance in MHz, None without a dip; delta variant − base, only when both have one; unit and delta_unit MHz; threshold SHIFT_LIMIT·f0 in MHz.
    - "bandwidth_10db": each −10 dB bandwidth in MHz, or None when it is not bounded on both sides (bandwidth at the index of the lowest |S11|); delta and resolved only when both are bounded; the same units and threshold. `# ponytail: the bandwidth's change is judged by the frequency threshold; P3-D may give it its own`.
  - **Rows only when both have a far field:**
    - "eta_tot" at f_lo, f0 and f_hi (`marker`): each at the recorded frequency nearest the marker (f_hz the base's); base and variant 100·η_tot, unit "%"; delta 10·log10(η_v/η_b), delta_unit "dB".
    - "peak_gain" at f0: base and variant 10·log10(gain), unit "dBi"; delta in dB, delta_unit "dB".
    - Both take the threshold DB_LIMIT.
  - **Resolved** is `abs(delta) > threshold`, None without a delta.
- [ ] **Step 5: `delta_lines` and `deltas_csv`.**
  - **`delta_lines`:** "compare's lines of `deltas`' rows (Stage 3 design 5.8)", the verdict T_RESOLVED or T_NOT_RESOLVED:
    - I_COMPARE_RESONANCE `{base_mhz, variant_mhz (:.1f), shift_mhz (:+.1f), shift_pct (:+.2f of 100·Δ/f0), verdict}`, or I_RESONANCE_NOT_COMPARED `{}` when its delta is None;
    - I_COMPARE_BANDWIDTH `{base_mhz, variant_mhz (:.1f), change_mhz (:+.1f), verdict}`, or I_COMPARE_NO_BANDWIDTH `{}` when its delta is None;
    - I_COMPARE_ETA `{marker, f_mhz (:.1f), base_pct, variant_pct (:.1f), delta_db (:+.2f), verdict}` per row;
    - I_COMPARE_GAIN `{f_mhz, base_dbi, variant_dbi (:.2f), delta_db (:+.2f), verdict}`;
    - I_COMPARE_NO_FAR_FIELD `{}` in place of those two when there are no far-field rows;
    - last, I_COMPARE_THRESHOLDS `{shift_pct: f"{100 * SHIFT_LIMIT:g}", db: f"{DB_LIMIT:g}"}`.
  - **`deltas_csv`:** "compare.csv: DELTA_COLUMNS, then the rows, None as empty, as plan 2's CSVs are written" (`csv.writer`, "\n" line ends).
- [ ] **Step 6: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_COMPARE_RESONANCE | Resonance: {base_mhz} MHz to {variant_mhz} MHz, a shift of {shift_mhz} MHz ({shift_pct} % of f0): {verdict}. | Ressonância: de {base_mhz} MHz para {variant_mhz} MHz, um deslocamento de {shift_mhz} MHz ({shift_pct} % de f0): {verdict}. |
| I_COMPARE_BANDWIDTH | -10 dB bandwidth: {base_mhz} MHz to {variant_mhz} MHz, a change of {change_mhz} MHz: {verdict}. | Largura de banda a -10 dB: de {base_mhz} MHz para {variant_mhz} MHz, uma mudança de {change_mhz} MHz: {verdict}. |
| I_COMPARE_NO_BANDWIDTH | -10 dB bandwidth: not compared, as one of the two has none bounded inside the simulated band. | Largura de banda a -10 dB: não comparada, pois uma das duas não tem nenhuma delimitada dentro da banda simulada. |
| I_COMPARE_ETA | Total efficiency at {marker} = {f_mhz} MHz: {base_pct} % to {variant_pct} %, {delta_db} dB: {verdict}. | Eficiência total em {marker} = {f_mhz} MHz: de {base_pct} % para {variant_pct} %, {delta_db} dB: {verdict}. |
| I_COMPARE_GAIN | Peak gain at f0 = {f_mhz} MHz: {base_dbi} dBi to {variant_dbi} dBi, {delta_db} dB: {verdict}. | Ganho de pico em f0 = {f_mhz} MHz: de {base_dbi} dBi para {variant_dbi} dBi, {delta_db} dB: {verdict}. |
| I_COMPARE_NO_FAR_FIELD | The efficiencies and the gain are not compared: they need a far field in both projects (a run with no part on the chain, or a verify), and one of them has none. | As eficiências e o ganho não são comparados: eles precisam de um campo distante nos dois projetos (uma execução sem componente na cadeia, ou uma verificação), e um deles não tem nenhum. |
| I_COMPARE_THRESHOLDS | Resolved means larger than the significance threshold: {shift_pct} % of f0 for a frequency and {db} dB for an efficiency or a gain, both provisional until gate P3-D measures the model's noise floor and sets them at three times it. | Resolvido significa maior que o limiar de significância: {shift_pct} % de f0 para uma frequência e {db} dB para uma eficiência ou um ganho, ambos provisórios até a checagem prévia P3-D medir o piso de ruído do modelo e defini-los em três vezes ele. |
| T_RESOLVED | resolved | resolvido |
| T_NOT_RESOLVED | not resolved | não resolvido |

- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(post): the deltas of two antenna results, each resolved or not by the significance thresholds (Stage 3 design 5.8)"
graphify update .
```

---

### Task 8 [code]: `compare BASE VARIANT`

**Files:**
- Modify:
  - `src/kicad_rf_studio/core/post/antenna.py`: `COMPARE_OUTPUTS`, `_panels` (draw_antenna's body), `draw_compare` and `compare_png`;
  - `src/kicad_rf_studio/pipeline.py`: `antenna_result` and `compare_projects` after `retune`, and the module docstring;
  - `src/kicad_rf_studio/cli.py`: `_compare`, the parser and the module docstring;
  - `src/kicad_rf_studio/core/messages.py`: the refusals after E_RESULTS_STALE, I_COMPARE_BASIS before I_COMPARE_RESONANCE, I_PLOT_COMPARE_TITLE after I_PLOT_ANTENNA_TITLE, and the terms after T_NOT_RESOLVED;
  - `po/*` and the `.mo`.
- Create: `tests/test_compare.py`.
- Test: `tests/test_post_antenna.py`.

**Interfaces:**
- Consumes:
  - Task 3's fingerprint and `pi_run`; Task 5's `far_of`; Task 6's `current_verify`; Task 7's `deltas`, `delta_lines`, `deltas_csv` and `DELTA_COLUMNS`;
  - `read_project`, `load`, `build_model`, `results_of`, `layout`, `write`, `command_line`, `parts`, PORT and CURVE_PORT.
- Produces:
  - `COMPARE_OUTPUTS = re.compile(r"compare\.(png|csv)")`.
  - `draw_compare(fig, f, curves: list[tuple[str, np.ndarray, dict | None]], project: dict) -> None` and `compare_png(f, curves, project) -> bytes`.
  - `pipeline.antenna_result(path: Path) -> dict`, with the keys `path`, `project`, `f`, `s11`, `far`, `fingerprint`, `source` ("T_RUN" or "T_VERIFY") and `run_dir`.
  - `pipeline.compare_projects(base: Path, variant: Path, output: Path | None = None, emit=None) -> int`.
  - CLI `compare BASE VARIANT [-o PATH]`.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_post_antenna.py` (imports gain `compare_png` and `draw_compare`):

```python
def test_the_compare_png_overlays_both_with_the_label_and_the_limits():  # design 5.8; anti-goal 1
    d = antenna_dict()
    f = band_grid(d)
    for far_field in (far_of(), None):
        fig = Figure()
        draw_compare(fig, f, [("a", dip(f).astype(complex), far_field), ("b", dip(f, 2.45e9).astype(complex), far_field)], d)
        assert fig.get_suptitle() == render("I_PLOT_COMPARE_TITLE", base="a", variant="b") + "\n" + render(
            "I_ANTENNA_RELATIVE")
        assert all(render(code) in fig.texts[-1].get_text() for code in ANTENNA_LIMITS)
        assert len(fig.axes) == (6 if far_field else 2)  # S11, Smith; η and the three cuts where both have a far field
        assert [line.get_label() for line in fig.axes[0].lines if not line.get_label().startswith("_")] == ["a", "b"]
    assert compare_png(f, [("a", dip(f).astype(complex), None), ("b", dip(f).astype(complex), None)], d).startswith(
        b"\x89PNG")
```

  - `tests/test_compare.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import os
import shutil
from pathlib import Path

import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.post.antenna import ANTENNA_LIMITS, DELTA_COLUMNS
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_antenna import antenna_project
from test_match_antenna import pi_run
from test_run import lpf_project


def twin(pj, folder):
    """A copy of the project folder of `pj` at `folder`: the same results and run folder, its own project.json."""
    shutil.copytree(pj.parent, folder)
    return folder / "project.json"


def compared(base, variant, out):
    lines = []
    assert pipeline.compare_projects(base, variant, out, lambda code, params: lines.append((code, params))) == 0
    return lines


def edited(pj, **results):
    d = load_project(pj)
    save_project(pj, {**d, "results": {**d["results"], **results}})


def test_compare_two_runs_with_the_same_settings(tmp_path, calibrated, capsys):  # design 5.8
    a = antenna_project(tmp_path / "a")
    assert pipeline.run(a) == 0
    b, run_dir = twin(a, tmp_path / "b"), load_project(a)["results"]["run_dir"]
    lines = compared(a, b, tmp_path / "out")
    codes = [code for code, _ in lines]
    assert lines[:3] == [("I_ANTENNA_RELATIVE", {}),
                         ("I_COMPARE_BASIS", {"role": "T_BASE", "path": str(a), "source": "T_RUN", "run_dir": run_dir}),
                         ("I_COMPARE_BASIS", {"role": "T_VARIANT", "path": str(b), "source": "T_RUN", "run_dir": run_dir})]
    assert lines[3] == ("I_COMPARE_RESONANCE", {**lines[3][1], "shift_mhz": "+0.0", "verdict": "T_NOT_RESOLVED"})
    assert codes.count("I_COMPARE_ETA") == 3 and "I_COMPARE_GAIN" in codes
    assert {p["verdict"] for _, p in lines if "verdict" in p} == {"T_NOT_RESOLVED"}  # a project against its copy
    assert codes[-6:] == ["I_OUTPUTS", *ANTENNA_LIMITS]
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["compare.csv", "compare.png"]
    rows = list(csv.reader(io.StringIO((tmp_path / "out" / "compare.csv").read_text(encoding="utf-8"))))
    assert rows[0] == list(DELTA_COLUMNS) and len(rows) == 7
    capsys.readouterr()
    assert main(["compare", str(a), str(b), "-o", str(tmp_path / "cli")]) == 0
    assert render("I_ANTENNA_RELATIVE") in capsys.readouterr().out.splitlines()


def test_compare_refuses_other_settings_another_kind_and_no_result(tmp_path, calibrated, capsys):  # 5.8; RF 4, 5
    a = antenna_project(tmp_path / "a")
    assert pipeline.run(a) == 0
    b, old, stale = twin(a, tmp_path / "b"), twin(a, tmp_path / "old"), twin(a, tmp_path / "stale")
    edited(b, fingerprint={**load_project(b)["results"]["fingerprint"], "preset": "strict", "air_gap_mm": 62.5,
                           "openems": "0.36.0"})
    d = load_project(old)
    del d["results"]["fingerprint"]  # a result made before this version
    save_project(old, d)
    save_project(stale, {**load_project(stale), "t_max_s": 31e-9})  # T_max is in the model: its results are stale
    lpf, fresh = lpf_project(tmp_path), antenna_project(tmp_path / "fresh")
    for variant, code, params in [(b, "E_COMPARE_SETTINGS", {"fields": "air_gap_mm, openems, preset"}),
                                  (lpf, "E_COMPARE_KIND", {"path": str(lpf)}),
                                  (fresh, "E_COMPARE_NO_RESULT", {"path": str(fresh)}),
                                  (old, "E_COMPARE_NO_RESULT", {"path": str(old)}),
                                  (stale, "E_COMPARE_NO_RESULT", {"path": str(stale)})]:
        with pytest.raises(KrsError) as e:
            pipeline.compare_projects(a, variant, tmp_path / "out")
        assert (e.value.code, e.value.params) == (code, params)
    assert not (tmp_path / "out").exists()  # a refusal writes nothing
    capsys.readouterr()
    assert main(["compare", str(a), str(b), "-o", str(tmp_path / "cli")]) == 2
    assert capsys.readouterr().err == render("E_COMPARE_SETTINGS", fields="air_gap_mm, openems, preset") + "\n"


def test_compare_reads_a_part_port_projects_verify_at_its_values(tmp_path, calibrated, monkeypatch):  # 5.8; RF 4
    a = pi_run(tmp_path, monkeypatch)
    with pytest.raises(KrsError) as e:  # part ports and no verify: the retune alone is what-if
        pipeline.compare_projects(a, a, tmp_path / "out")
    assert (e.value.code, e.value.params) == ("E_COMPARE_NO_RESULT", {"path": str(a)})
    assert pipeline.verify(a) == 0
    b, other, verify_dir = twin(a, tmp_path / "b"), twin(a, tmp_path / "other"), load_project(a)["verify"]["run_dir"]
    lines = compared(a, b, tmp_path / "out")
    assert [(p["source"], p["run_dir"]) for c, p in lines if c == "I_COMPARE_BASIS"] == [("T_VERIFY", verify_dir)] * 2
    assert pipeline.retune(b, ["C3=1.2pF"]) == 0  # applied after its verify, which no longer holds b's values
    d = load_project(other)
    save_project(other, {**d, "verify": {**d["verify"], "base_hash": "0" * 64}})  # a verify of another run
    for project in (b, other):
        with pytest.raises(KrsError) as e:
            pipeline.compare_projects(a, project, tmp_path / "out")
        assert (e.value.code, e.value.params) == ("E_COMPARE_NO_RESULT", {"path": str(project)})
    shutil.rmtree(verify_dir)  # verify's folder deleted: the base, read first, has nothing to compare either
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(a, b, tmp_path / "out")
    assert (e.value.code, e.value.params) == ("E_COMPARE_NO_RESULT", {"path": str(a)})


def test_compare_without_a_far_field_on_one_side_compares_s11_alone(tmp_path, calibrated):  # design 5.8; RF 5
    a = antenna_project(tmp_path / "a")
    assert pipeline.run(a) == 0
    b = twin(a, tmp_path / "b")
    edited(b, far_field=None)  # its transform failed
    codes = [code for code, _ in compared(a, b, tmp_path / "out")]
    assert "I_COMPARE_NO_FAR_FIELD" in codes and not {"I_COMPARE_ETA", "I_COMPARE_GAIN"} & set(codes)


def test_compare_writes_to_the_working_folder_by_default_and_a_held_file_is_an_e_line(
        tmp_path, calibrated, monkeypatch):  # r2 Q4; Stage 1 7.5
    a = antenna_project(tmp_path / "a")
    assert pipeline.run(a) == 0
    b = twin(a, tmp_path / "b")
    (tmp_path / "cwd").mkdir()
    monkeypatch.chdir(tmp_path / "cwd")
    assert main(["compare", str(a), str(b)]) == 0
    assert sorted(p.name for p in (tmp_path / "cwd").iterdir()) == ["compare.csv", "compare.png"]
    real = os.replace

    def replace(src, dst):  # a viewer holds compare.png
        if Path(dst).name == "compare.png":
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    lines = []
    assert pipeline.compare_projects(a, b, tmp_path / "out", lambda code, params: lines.append((code, params))) == 2
    (err,) = [params for code, params in lines if code == "E_RESULTS_WRITE"]
    assert (err["path"], err["command"]) == (str(tmp_path / "out" / "compare.png"), pipeline.command_line(
        "kicad-rf-studio", "compare", str(a), str(b), "-o", str(tmp_path / "out")))
    codes = [code for code, _ in lines]
    assert "I_OUTPUTS" not in codes and codes[-5:] == list(ANTENNA_LIMITS)  # the lines still printed
```

  Probe (reviser): load and build_model took 0.32–0.34 s for ifa2g4 and its pi variant, so the model check costs compare under a second a project. The default fake's M = 0 S11 dips to −33.0 dB at 2506.4 MHz, inside the band, so its resonance row stands.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_compare.py tests/test_post_antenna.py -q`. Expected: FAIL with `cannot import name 'compare_png'`.
- [ ] **Step 3: `post/antenna.py`.**
  - **`_panels(fig, f, curves, project)`** is `draw_antenna`'s plotting body, drawn once per curve `(name, s11, far)`:
    - |S11| with the band shaded and the level lines, each curve labelled with its name;
    - the Smith chart with the marker dots;
    - only when every curve has a far field, η_tot and η_rad against GHz and the three cuts, on a common radial range.
    - With two curves, every panel gets a legend, and the η lines' labels start with the curve's name.
  - **`draw_antenna`** becomes `_panels(fig, f, [(name, s11, far)], project)` followed by its title, label and limits as they are, so plan 2's tests stand.
  - **`draw_compare(fig, f, curves, project)`:** "compare.png's overlays (Stage 3 design 5.8) on the Figure `fig`: _panels of both curves, under I_PLOT_COMPARE_TITLE {base, variant} (the curves' names) with I_ANTENNA_RELATIVE as its second line, and the rendered ANTENNA_LIMITS at the foot, as draw_antenna."
  - **`compare_png`:** `draw_compare` on an Agg Figure at 100 dpi, sized as `antenna_png` sizes it.
- [ ] **Step 4: `antenna_result(path)`.**
  - **Docstring:** "The full simulation `compare` reads of the project at `path` (Stage 3 design 5.8): E_COMPARE_KIND {path} for a project that is not an antenna's (read_project, before any board is read); then its results checked against its current model as retune checks them (load, build_model, results_of: Stage 1 7.8); with no part port on its chain, its run (results); with part ports, its current verify (current_verify) when that verify's values are, as text, the part ports' values project.json holds. Its S11 on the band grid (that record's one-port layout), its far field (far_of, None without one), its fingerprint, its source (T_RUN or T_VERIFY) and its run folder. E_COMPARE_NO_RESULT {path} for no results or stale ones (results_of's E_NO_RESULTS and E_RESULTS_STALE, the model built outside that catch), no such record, or one with no fingerprint (made before this version). It starts no worker."
  - Comment it `# ponytail: values compared as text, so 4p7 and 4.7pF read as different; port_value equality if users trip on it` and `# ponytail: verify's parts are ideal at their stored values (C-38), so an S2P file applied to a part is not what compare compares, and a chain part off 90° (E_VERIFY_CURVE) leaves its project nothing to compare`.
- [ ] **Step 5: `compare_projects(base, variant, output=None, emit=None)`.**
  - **Docstring:** "`compare BASE VARIANT` (Stage 3 design 5.8), returning its exit code: each project's result (antenna_result, the base's first); E_COMPARE_SETTINGS {fields}, the differing fingerprint keys sorted and joined by ", ", when their fingerprints differ; then compare.csv (deltas_csv) and compare.png (compare_png, each curve named by its project's folder, path.absolute().parent.name) written to `output`, the working folder (Path.cwd()) when None (write, COMPARE_OUTPUTS, E_RESULTS_WRITE advising this command with -o); then `emit(code, params)` for each line, which prints it by default, as retune's: I_ANTENNA_RELATIVE, I_COMPARE_BASIS {role, path, source, run_dir} for the base then the variant, delta_lines, I_OUTPUTS, ANTENNA_LIMITS; and 0. A refused write is an E_ line in I_OUTPUTS' place, the other lines still printed (Stage 1 7.5), and 2. It starts no worker; a refusal before the write writes nothing."
  - The deltas take the base's project, whose band, f0 and far field the variant shares by the fingerprint.
- [ ] **Step 6: The CLI.**
  - A `compare` subparser with the positionals `base` and `variant`, and `-o` (dest `output`, metavar PATH), whose func is `_compare`.
  - `_compare(a)` returns `pipeline.compare_projects(pipeline.project_path(a.base), pipeline.project_path(a.variant), a.output and Path(a.output))`.
  - `compare` takes no `--run-dir`, so `main` writes it no end event.
  - The module docstrings of `cli.py` and `pipeline.py` add "`compare BASE VARIANT` compares two antenna projects' full simulations (pipeline.compare_projects, Stage 3)".
- [ ] **Step 7: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| E_COMPARE_KIND | {path} is not an antenna project: \`compare\` compares two antenna projects, made with \`new --antenna\`. | {path} não é um projeto de antena: \`compare\` compara dois projetos de antena, criados com \`new --antenna\`. |
| E_COMPARE_NO_RESULT | {path} has no result that \`compare\` can use: a run of its current model, made by this version, with no part on the chain, or, with part ports, a verify of that run at the values project.json holds. Run \`run\` (a board re-saved since its run needs one), then \`verify\` for a project with part ports. | {path} não tem resultado que \`compare\` possa usar: uma execução do modelo atual dele, feita por esta versão, sem componente na cadeia ou, com portas de componentes, uma verificação dessa execução com os valores que o project.json guarda. Execute \`run\` (uma placa salva de novo desde a execução precisa de uma) e depois \`verify\` para um projeto com portas de componentes. |
| E_COMPARE_SETTINGS | The two projects were simulated with different settings ({fields}), so their differences would mix the boards' with the settings'. Make those settings the same in both, run both with the same versions of this app and of openEMS, and compare again. | Os dois projetos foram simulados com configurações diferentes ({fields}), então as diferenças deles misturariam as das placas com as das configurações. Deixe essas configurações iguais nos dois, execute os dois com as mesmas versões deste aplicativo e do openEMS e compare de novo. |
| I_COMPARE_BASIS | {role}: {path}, compared by its {source} in {run_dir}. | {role}: {path}, comparado pela {source} em {run_dir}. |
| I_PLOT_COMPARE_TITLE | {base} against {variant}: antenna, relative results | {base} contra {variant}: antena, resultados relativos |
| T_BASE | Base | Base |
| T_VARIANT | Variant | Variante |
| T_RUN | run | execução |
| T_VERIFY | verify | verificação |

- [ ] **Step 8: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_cli_new.py tests/test_run_antenna.py tests/test_golden_v1.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 9: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(cli): compare BASE VARIANT overlays two antenna projects' full simulations and marks each delta resolved or not, refusing two projects simulated with different settings (Stage 3 design 5.8)"
graphify update .
```

---

### Task 9 [run]: The pi variant end to end, its record and the amendments

This task commits the record, the amendments and any fix a failure needs. Everything else it makes stays under `$env:TEMP`. Run each PowerShell block as one call.

- [ ] **Step 1: The suite at the branch tip.** Run the full suite in the background and wait for it. Then run, in one call: `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass. Record the counts.
- [ ] **Step 2: New, cost, run and cost again on the pi variant,** in the background, waited on:

```powershell
$out = Join-Path $env:TEMP 'krs-plan3-run'; New-Item -ItemType Directory -Force $out | Out-Null
$env:LOCALAPPDATA = "$out\data"; $env:XDG_DATA_HOME = "$out\data"  # an isolated data folder: its own calibration
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"  # typed here, never written into a file
Copy-Item tests\fixtures\ifa2g4_pi.kicad_pcb $out
$krs = ".venv\Scripts\kicad-rf-studio.exe"
& $krs new "$out\ifa2g4_pi.kicad_pcb" --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o "$out\proj" *> "$out\new.log"; "new $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs cost "$out\proj" *> "$out\cost.log"; "cost $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs run "$out\proj" *> "$out\run.log"; "run $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs cost "$out\proj" *> "$out\cost2.log"; "cost2 $LASTEXITCODE" | Add-Content "$out\codes.txt"
```

  - **Expected codes:** `new 0`, `cost 0`, `run 0`, `cost2 0`.
  - **Expected time:** 1–2 hours. The first run's record costed this variant's worst case at 4 h 14 min: 4 runs to 30 ns, 4 at once. Its jobs converge near a third of T_max if they behave as the plain fixture's did, at 9.81 of 30 ns.
- [ ] **Step 3: The bypassed copy, the retune with snapping, verify, the second value set and compare,** in the background, waited on. Step 2's `$out`, environment and `$krs` lines come first, without its `Copy-Item`:

```powershell
Remove-Item -Recurse -Force "$out\proj_b" -ErrorAction SilentlyContinue; Copy-Item -Recurse "$out\proj" "$out\proj_b"
& $krs retune "$out\proj" L1=<searched> C2=<searched> C3=<searched> *> "$out\retune.log"; "retune $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs verify "$out\proj" *> "$out\verify.log"; "verify $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs retune "$out\proj" *> "$out\retune2.log"; "retune2 $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs retune "$out\proj_b" L1=0R C2=open C3=open *> "$out\retune_b.log"; "retune_b $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs verify "$out\proj_b" *> "$out\verify_b.log"; "verify_b $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs compare "$out\proj" "$out\proj_b" -o "$out\compare" *> "$out\compare.log"; "compare $LASTEXITCODE" | Add-Content "$out\codes.txt"
```

  - `proj_b` is copied right after the run, so it inherits the run and no verify: the same run with the network bypassed, the antenna seen through its feed line. The Remove-Item keeps a rerun from nesting the copy.
  - The first retune's values come from the controller's search on the run's layout, in scratch, before this step: each part over E24 values (L1 0.5–20 nH, C2 and C3 0.1–10 pF) and its bypass (L1 `0R`, C2 and C3 `open`), closed as the retune closes them (the 0402 presets and the cell C), for the smallest largest |S11| over [f_lo, f_hi]. E24 values are what the GUI's snapping gives (`gui.control.snapped`, pinned by Task 1's `test_snapping_leaves_a_bypass_as_typed`), so this is design §5.14 item 3's "retune with snapping", tuned to a match as a user would. The record gives the search, its best set and its largest in-band |S11|. Apply is the CLI's `retune` with them.
  - **Expected codes:** all 0.
  - **Expected time:** about an hour: two verify jobs alone of about 25 minutes each plus their transforms. The worst case is about 2.5 h, up to about 75 min a verify job to T_max (the record's 76 min, scaled by the pi model's nodes and dt).
- [ ] **Step 4: Read it, against these pre-registered checks.**
  - **Hard:** a failure gets superpowers:systematic-debugging, and a bug is fixed test-first in its module, then the step again.
    - **The run:**
      - its 4 jobs kept, with no E_ line;
      - I_GATES_PASSED_PML, with no E_PORT_SHORT, E_PORT_OPEN or E_PORT_BOX;
      - `results.far_field` null, with I_ANTENNA_NO_FAR_FIELD among its lines;
      - `results.fingerprint` present;
      - `results/` holds antenna_summary.png, chain.s1p and layout.s4p.
    - **The retune:** project.json holds the searched values, and its chain.s1p gives the search's largest in-band |S11| within 0.05 dB (a miss is the search's error, fixed in scratch, not the product's).
    - **retune_b:** proj_b's project.json holds L1 0R, C2 open and C3 open, and its lines hold I_ANTENNA_NO_FAR_FIELD.
    - **Each verify:**
      - its one job kept, with no E_ line and I_GATES_PASSED_PML;
      - `verify.far_field` names three files;
      - its `results/` gains verify.s1p, verify_farfield.csv, verify_summary.csv and verify_summary.png;
      - no W_ETA_RAD.
    - **proj_b's verify:** `verify.values` is {L1: 0R, C2: open, C3: open} and its `run_dir` is not proj's; its model has an empty grid and one copper box more than the run's model.
    - **retune2:** 11 I_ANTENNA_ETA_WHAT_IF lines and no I_ANTENNA_NO_FAR_FIELD.
    - **compare:** two I_COMPARE_BASIS lines with T_VERIFY, each naming its own project's verify folder; compare.csv and compare.png written.
  - **Cost:** cost2's I_COST_PREDICTED against the run's `results.wall_s`, as a ratio predicted/measured.
    - Within [0.67, 1.5] it passes.
    - It is SMALL_SPEED's first measurement at a pool of 4: the first run measured it at 1.
    - Outside the range, the record says so. PML_WEIGHT and SMALL_SPEED stay as they are, and plan 4's P3-C refits them.
  - **Soft, report-only:**
    - **Each verify's comparison:** |ΔS11| at f0, the largest |ΔS11|, and the resonance shift where both mark a dip (else that they did not). They are the co-simulation's consistency on an antenna, where P0-B's lpf915 read |ΔS| near 0.003.
    - **The ideal network's gap:** retune2's resonance and what-if η_tot at f0 against verify's own resonance and η_tot at f0, at the same values. Verify's parts are ideal; the retune's carry the 0402 presets, which at f0 read a C about 12–18 % and an L about 2 % above its value (the reviser's figures for 0.91 pF, 1.3 pF and 3 nH).
    - **proj_b's verify resonance** against the first run's 2388.2 MHz. That was the plain fixture's antenna through its 12 mm feed; the pi variant's 0.6 mm line with three pad pairs differs.
    - **Physics:** η_rad between 0.5 and 1.0; D at f0 between 1.5 and 4.5 dBi.
    - **compare's deltas,** which are resolved, and whether the resonance was compared at all.
    - **The times:** the run's 4 jobs at 4 at once, each verify job, each transform.
- [ ] **Step 5: The record,** `docs/validation/<the run's date>-antenna-matching-run.md`.
  - **Language:** write the lines in English. The run, each verify and compare printed in the process language, pt-BR on this PC.
    - Render the run's and each verify's events in one call: `$env:LANGUAGE = "en"; .venv\Scripts\python.exe -c "import json, sys; from kicad_rf_studio.core.messages import render; [print(render(e['code'], **e['params'])) for e in map(json.loads, open(sys.argv[1], encoding='utf-8')) if e['kind'] == 'result']" <events.jsonl>`.
    - retune2's lines: `retune "$out\proj"` with no assignments under `$env:LANGUAGE = "en"`, since proj still holds retune2's values and verify.
    - compare's lines: compare has no run folder, so run it again in one call under `$env:LANGUAGE = "en"` with `-o "$out\compare_en"`. It takes seconds and gives the same numbers.
  - **Sections:**
    1. Purpose: plan 3's end-to-end run of the matching flow, not a gate.
    2. Inputs: the commands with `<RUN>`, the versions and the fresh calibration.
    3. The cost at a pool of 4: predicted against measured.
    4. The lines: the run's, retune2's, both verifies' and compare's, under the relative label.
    5. The checks of Step 4.
    6. Verify's consistency, the ideal network's gap and the far field at the applied values.
    7. Compare's deltas.
    8. The stated limits.
    9. Next: plan 4 and plan 5.
  - It holds no path and no host name.
- [ ] **Step 6: The amendments,** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`:
  - **A-33, §7.6:** a bullet after A-4's "Until P0-C passes" bullet:
    > "- **Antennas** (Stage 3): every part on an antenna's chain is a part port, a 0R and a DNP placeholder too, a 0R starting at 0 Ω and a DNP part open (project.json's value `open`). The instant retune gives S11 at the start pad; it takes 0 Ω for a series part (`REF=0R`, any 0 in ohms, or 0 on an L or an R) and `open` for a shunt part, each with no package model, refuses 0 Ω on a part to a net off the chain, `open` on a series part and a C of 0 F, which could mean either. Where the last verify of the run's model recorded a far field, the retune adds the what-if total efficiency η_rad·P, η_rad from that verify and P the power the retune's network passes to the board: 1 − |S11|² less the parts' own loss (§7.4's terms), 1 − |S11|² for a lossless network. A run with part ports records no far field and says so. `verify` is one-port: every part in the grid at its value as an ideal part, without the package model or the S2P data, a 0 Ω part as copper over its port's box and an open part left out, in one job that records the far field, transformed as a run's is; it compares |ΔS11| at f0, the largest |ΔS11| up to f2 and, where both have their lowest |S11| at or below −6 dB inside the band, the resonance shift with the retune at the same ideal values, and writes verify.s1p, verify_farfield.csv, verify_summary.csv and verify_summary.png. On <date> the 2.4 GHz fixture's pi variant ran it end to end (`docs/validation/<date>-antenna-matching-run.md`). (A-33, Stage 3 plan 3: controller recommendation, owner unavailable.)"
  - **A-34, §3.2 and §3.3:**
    - §3.2's table, a row after `verify`'s:
      > "| `kicad-rf-studio compare BASE VARIANT [-o PATH]` | Compares two antenna projects' full simulations: writes compare.csv and compare.png, prints the deltas, each resolved or not, and refuses two projects whose settings fingerprints differ (A-34) |"
    - §3.2, after A-32's antennas paragraph:
      > "**Antenna comparison** (Stage 3): `verify` works on an antenna project with part ports (§7.6, A-33), and `compare BASE VARIANT [-o PATH]` compares two antenna projects' full simulations, each project's run when no part is on its chain, else its verify of the last run at the values project.json holds; like `retune`, it uses a project's results only while its model-spec hash is unchanged (§7.8). compare.png overlays their S11 and, where both have one, their efficiencies and cuts; the lines and compare.csv give the resonance shift in MHz and in % of f0 where both have their lowest |S11| at or below −6 dB inside the band, the −10 dB bandwidth's change, Δη_tot in dB at f_lo, f0 and f_hi and the peak gain's change at f0, each resolved above 0.3 % of f0 for a frequency or 0.2 dB for an efficiency or a gain, until gate P3-D sets them. It refuses two projects whose settings fingerprints differ. (A-34, Stage 3 plan 3: controller recommendation, owner unavailable.)"
    - §3.3, a last bullet of project.json's list: "an antenna's results and verify record a settings fingerprint, which `compare` requires to be equal: the preset, mesh, region, band and f0, T_max, air gap, boundary, far field, stackup, lid height, start pad, copper model and the versions of the app and of openEMS (A-34)."
  - **The Status line** gains, at its end: " On <date>, Stage 3's plan 3 amended §3.2, §3.3 and §7.6 (A-33 and A-34) the same way."
- [ ] **Step 7: Commit.**

```bash
git add docs/validation/<date>-antenna-matching-run.md docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs(validation): the matching flow on the 2.4 GHz fixture's pi variant, run, retune, verify and compare; Stage 1 spec A-33 and A-34 (Stage 3 design 5.13; controller recommendation, owner unavailable)"
graphify update .
```

- [ ] **Step 8: Close.**
  1. Run the whole-branch review.
  2. Run Step 1 again after any later commit.
  3. Fast-forward `main` to the branch locally, then delete the branch.
  4. Delete `$env:TEMP\krs-plan3-run`.

  Nothing is pushed. There are no screenshots: plan 3 has no GUI.

---

## Not in this plan

- **Plan 4, the gates P3-B to P3-E:**
  - their fixture variants, among them the ground-pour variant of the pi board for the acceptance compare (design §5.14 item 3); Task 9 compares two value sets of one project instead;
  - the significance thresholds from P3-D's noise floor (SHIFT_LIMIT, DB_LIMIT), a threshold of the bandwidth's own if P3-D measures one, and the −6 dB resonance screen checked against that noise;
  - all-sheet copper as a project field, which then replaces the fingerprint's constant "solid";
  - refitting PML_WEIGHT and SMALL_SPEED, with Task 9's first measurement at a pool of 4.
- **Plan 5, the GUI, the button and the docs:**
  - opening antenna projects, so that `control.open_project`'s guard goes;
  - the Results page with verify's far field, cuts and the what-if η_tot: the retune session shows `eta_what_if_lines(far_of(v), s11_at(path, project, f)[1])` for `v = current_verify(project)`, the CLI's own functions, so the GUI adds no run logic (Stage 1 §3.2);
  - the retune table taking 0R and open; `control.verify_stale` must read bypasses, since `port_value` reads `open` and a C's `0R` as None;
  - G_ wordings in `control.GUI`, with pt-BR, for the new lines that advise terminal syntax: E_RETUNE_SHORT_SHUNT, E_RETUNE_OPEN_SERIES, E_RETUNE_ANTENNA_VALUE, I_ANTENNA_NO_FAR_FIELD and E_COMPARE_NO_RESULT;
  - the Compare page on `compare_projects(..., emit=)`;
  - the README tutorial, the release check and the exit record.
- **Deferred by the design:**
  - the instant far-field retune by superposition (design §3 and §7);
  - de-embedding the feed line (r2 Q3).
- **Ceilings, each a ponytail comment:**
  - compare compares verify's values with project.json's as text;
  - compare reads verify, whose parts are ideal at their stored values (C-38), so an S2P file applied to a part is not what compare compares;
  - a chain part off a multiple of 90° makes verify refuse (E_VERIFY_CURVE), so compare cannot use that project;
  - verify.s1p's grid lines name the grid parts only;
  - the tracer's shunt list decides the converse refusals: a series part beside a parallel one is still refused open, and a shunt 0R that the board itself holds keeps its 0 Ω and verifies as copper, which can meet E_PORT_SHORT;
  - the what-if η_tot takes η_rad from verify's ideal network and assumes the matching network neither radiates nor changes the board's own loss;
  - the resonance screen is a depth screen (−6 dB, inside the band), which a broad −7 dB minimum still passes.

## Controller rulings (2026-10-30; binding)

These are the architect's rulings, revised after four reviews (coverage, feasibility, physics and network math, quality). Each is a controller recommendation made while the owner is unavailable.

- Ruling: the tasks run in this order:
  1. the bypass values;
  2. the ports;
  3. a part-port run's results and the fingerprint;
  4. verify's model;
  5. verify's run;
  6. the what-if;
  7. the deltas;
  8. the command;
  9. the run.

  Each task's tests are red in that task: Task 1 owns the feed-line retune end to end and Task 2 the placeholders' run, so no later task inherits a test that is green on arrival; the snapping pin, which passes on `main`, says so. Verify's spec code, shared with v1's verify and pinned by the golden digests, gets a gate apart from its pipeline wiring, and the deltas' numbers one apart from the command — design §5.12 item 3 and the quality review — cost if wrong: a reorder.
- Ruling: the bypass syntax. 0 Ω is a 0 in ohms on any part (`0R`, `0Ω`, `0ohm`, any case) or a value that reads as 0 for an L or an R (`0`, `0nH`); open is the text `open`, in any case.
  - A C of 0 (`C2=0`, `0pF`) stays refused, since it reads as 0 F, an open, and would be ambiguous with 0 Ω: a board's "0" on a C footprint often means a jumper. On an antenna the refusal is E_RETUNE_ANTENNA_VALUE, E_RETUNE_VALUE's text with the bypass syntax.
  - A bypass is read only for an antenna, so v1's `L1=0R` and `C2=open` stay E_RETUNE_VALUE.

  — design §5.7 ("accepts 0 Ω for a series position and open for a shunt position") — cost if wrong: one function.
- Ruling: the converse is refused. E_RETUNE_SHORT_SHUNT {ref, net} refuses 0 Ω on a shunt part whose other net is off the chain, which would short the chain to that net (GND, or a supply through a feed choke); E_RETUNE_OPEN_SERIES refuses open on a series part, which cuts the antenna off. Neither bypasses a network, and verify would then meet E_PORT_SHORT or radiate nothing. A part across two chain nets may take 0 Ω: it bridges a series part. A shunt 0R the board itself holds keeps its starting 0 Ω, which is no assignment (a ceiling) — design §5.7 and the feasibility review — cost if wrong: two codes removed.
- Ruling: the starting values.
  - A 0R keeps its own value text, which reads 0 Ω.
  - A DNP chain part's value becomes `open` in project.json, and its `dnp` flag stays, so every reader reads one value field.
  - A DNP series part never reaches a chain, since the tracer's walk stops at it (E_NO_CHAIN). So the placeholders that start open are shunts.

  — design §5.1 — cost if wrong: one field.
- Ruling: every chain part is PORT, or CURVE_PORT off a multiple of 90° (v1's angle rule, which verify refuses as v1 does), and v1's choke rule does not apply to it. W_VALUE_UNREADABLE leaves out an antenna's chain part whose value `bypass` reads, and a test pins v1's side of that note. v1's roles still decide everything off the chain and every v1 chain — design §5.1 ("whatever its value") — cost if wrong: one branch.
- Ruling: a bypass is ideal.
  - Z_part is 0 or ∞, with no package model.
  - The retune closes an open port with its box's C alone, the limit of Z ∥ C_box, which p0b's harness already uses for an emptied part.
  - Verify puts a 0 Ω part as copper over its port's box and leaves an open one out, so both sides of verify's comparison hold the same network. It does so only while the part has no S2P file: a placeholder given one is a fitted part, refused with E_VERIFY_VALUE as v1 refuses any value it cannot place.

  — design §5.7, Stage 1 §7.6 ("each part sits in the box of the port it replaces") and the physics review — cost if wrong: one expression each.
- Ruling: verify's far field. The box is factored out of `model_spec` as `far_field_box`, which `verify_spec` adds, and `_model_phase` returns the board for it. No part-port job records one; verify always does, under MUR too, as `model_spec` does at M = 0 — design §5.5 — cost if wrong: one key.
- Ruling: verify's files and their order. The files are verify.s1p, verify_farfield.csv, verify_summary.csv and verify_summary.png, names that retune's `write` never deletes (ANTENNA_OUTPUTS does not match them).
  - The comparison is stored first and I_VERIFY_RESULTS emitted at once, as `_run` emits I_RESULTS before its transform.
  - verify.s1p and the PNG are written before the transform, so a stopped transform leaves verify's S file, as a run's.
  - The transform runs only after a stored comparison: with project.json held, it could not be recorded.
  - All four files are written after it; that second write supersedes the first, whose refusal is said only when no second write follows.

  — design §5.6, Stage 1 §7.6 and §7.8, and the coverage and quality reviews — cost if wrong: file names in plan 5.
- Ruling: verify's comparison holds:
  - |ΔS11| at f0;
  - the largest |ΔS11| over the band grid, which runs to f2;
  - each resonance (plan 2's refined one) where it marks a dip: its lowest |S11| at or below the −6 dB marker, at a point inside the grid;
  - the shift (f_verify − f_retune)/f_retune, as v1's null shift, only when both do.

  There is no loss budget. Its texts say that verify's parts are ideal, without the package ESL, ESR and Cp or the S2P data the retune applies, never "as applied" — design §5.7 and the physics review — cost if wrong: one formula.
- Ruling: the what-if η_tot comes from the current verify (`current_verify`: its `base_hash` equal to `results.model_hash`, its model.json, waves and far-field files present). It is given at each recorded frequency, η_rad from verify times this retune's P_layout from `loss_budget`: the power the network passes to the board, which is the design's 1 − |S11|² for a lossless network and leaves out the parts' own loss otherwise (the presets' ESR cost 0.2–1.3 % of the incident power on the fake's pi, an S2P part more). No line reports P_layout as a loss budget, as design §5.6 says. There is none at M = 0, whose run's own far field holds η_tot, and an older, missing or far-field-less verify reads as none — design §5.7 and the physics review — cost if wrong: one condition.
- Ruling: the fingerprint.
  - **Fields:** the design's list made concrete: preset, mesh (n and reach), region (expand_h), band and f0, T_max, air gap, boundary, far field (frequencies and step, which the deltas at f_lo, f0 and f_hi need), stackup, lid height and the chain's start pad (each typed per project, not in the board, and each moves S11 or the far field), copper model ("solid", the only one), and the versions of this app (`__version__`) and of openEMS (`runs.openems_versions`, what a worker sees).
  - It is recorded in an antenna's results and verify blocks only.

  — design §5.8 and §6 (the builder's), and the quality and physics reviews — cost if wrong: one field added in plan 4.
- Ruling: `compare` compares full simulations only.
  - **Sources:** a project with no part port on its chain gives its run; one with part ports gives its verify, when `current_verify` returns it and its values are project.json's (text equality).
  - **Refusals:** anything else is E_COMPARE_NO_RESULT, naming the project, a deleted verify folder among them. A plan-2 result with no fingerprint is too.
  - Comparing two instant retunes would compare what-ifs, the anti-goal's unvalidated numbers.

  — design §5.8 and §5.14 item 3 — cost if wrong: a what-if source added.
- Ruling: `compare` checks each project's results against its current model as `retune` does (load, build_model, results_of: about 0.3 s a project, probed), so a board re-saved or a project.json edited after its run is refused, as Stage 1 §7.8 asks. It reads the recorded waves and starts no worker — Stage 1 §7.8 and the coverage review — cost if wrong: one results_of per project removed.
- Ruling: the deltas.
  - **Resonance:** the shift in MHz and in % of f0, only when both mark a dip (verify's rule).
  - **Bandwidth:** the −10 dB bandwidth's change, compared only when both are bounded and judged by the frequency threshold.
  - **Efficiency:** Δη_tot in dB at the recorded frequencies nearest f_lo, f0 and f_hi.
  - **Gain:** the peak gain D_max·η_rad at f0.
  - **Resolved:** above 0.3 % of f0 or 0.2 dB, strictly.
  - **compare.csv** gives the values' unit and the delta's unit apart (%, dBi against dB).

  — design §5.8 and the physics review — cost if wrong: one threshold.
- Ruling: compare writes compare.csv and compare.png into `-o PATH`, by default the working folder, as `new` does. A refused write is an E_ line in I_OUTPUTS' place, the other lines still printed, and exit 2, as Stage 1 §7.5 keeps the lines — r2 Q4 — cost if wrong: a default folder.
- Ruling: one drawing body, `_panels`, serves `draw_antenna` and `draw_compare`, so plan 5's GUI reuses both; compare.png names its curves by the projects' folders. verify_summary.png carries no label: its file name says verify, and verify is no what-if — ponytail and the coverage review — cost if wrong: none.
- Ruling: `new` prints no summary line of the chain's ports. Its I_PART lines already print each chain part's role and value, and E_RETUNE_ANTENNA_VALUE and the converse refusals teach `REF=0R` and `REF=open` where a user errs — ponytail, the quality review — cost if wrong: one info line.
- Ruling: this plan's pt-BR glossary, by the pt-BR design's §6.1. Plan 1's and plan 2's terms stand (campo distante, eficiência de radiação, ressonância, largura de banda, eficiência de descasamento, cadeia de casamento), and so do v1's (série, shunt, ajuste, verificação, hipotético, grade, checagem prévia).

  | English | pt-BR |
  |---|---|
  | part port | porta de componente |
  | replace with a short (0 Ω) | trocar por um curto |
  | open, remove | em aberto, retirar |
  | feed | alimentação |
  | matching network | rede de casamento |
  | ideal part | componente ideal |
  | pass to the board | entregar à placa |
  | shift | deslocamento |
  | resolved / not resolved | resolvido / não resolvido |
  | significance threshold | limiar de significância |
  | noise floor | piso de ruído |
  | peak gain | ganho de pico |
  | base / variant | base / variante |
  | pattern | diagrama |

  — pt-BR design §6 — cost if wrong: a native speaker changes a few msgstrs.
- Ruling: the amendments land in Task 9 with the run's numbers: A-33 (§7.6, the one-port retune and verify) and A-34 (§3.2's table row and paragraph for `compare` and verify, §3.3's fingerprint). Design §5.13's §7 item is thereby complete; its "no loss budget" half was A-32 — design §5.13 and the coverage review — cost if wrong: a paragraph moved.
- Ruling: Task 9 runs two value sets of one project, the snapped set and the network bypassed, copying the project folder right after its run, so the copy inherits no verify. The ground-pour variant the acceptance names is plan 4's fixture. Task 9's checks are pre-registered:
  - **Hard:** every job and verify kept; no E_ line; the far-field files; the what-if lines; compare's basis; proj_b's own verify.
  - **Cost:** the ratio within [0.67, 1.5], SMALL_SPEED's first measurement at a pool of 4.
  - **Soft:** the physics and the ideal network's gap, report-only.

  — design §5.11's spirit and §5.14 item 3, and the feasibility review — cost if wrong: one rerun.
- Ruling (disclosure): the probes ran only in a scratch folder, with the repo's venv.
  - **The architect's:** the placeholders board edit and its trace, roles and model; a network-fake run of the placeholders project with its chain parts set to ports by hand (4 jobs converged at 6.90 ns in 3.1 s; layout.s4p against star(f, 4) 1.2e-7; chain.s1p against its oracle 7.3e-7; `terminate` against numpy with a short and an open box load 9.7e-16); `with_box`'s `np.where` form, bit-equal to v1's; `bypass`'s parses, the snapped values, the choke at 70–100 MHz, the band-grid resonances and bandwidths, and openEMS's metadata version 0.37.0.
  - **The reviser's,** with LOCALAPPDATA and XDG_DATA_HOME in scratch: snapping on `main` (Task 1's pin passes there); the pi's chain nets (C2 on RF_A–GND, C3 on RF–GND); load and build_model at 0.32–0.34 s a project; the −6 dB screen on the test curves and on both fakes' M = 0 S11 (the default fake dips to −33.0 dB at 2506.4 MHz with its −6 dB region running past the band's top; the network fake's one-port has no dip); a network-fake pi run: chain.s1p equal byte for byte across identical writes, `main`'s assign refusing `L1=0R`, `C2=open` and `C2=0` with E_RETUNE_VALUE, chain.s1p against the preset oracle 5.2e-7, the feed-line termination against its oracle 9.1e-7, the presets' part loss 0.2–1.3 % of the incident power, the loss budget layout against star(f, 4) 5.7e-8, and verify refusing the antenna with E_VERIFY_PORTS; the new messages against test_sexpr's KEEP and field rules.

  No suite ran and no openEMS ran. The fake worker's isolated subprocesses and the probes refreshed git-ignored bytecode caches under `src/` and `tests/`; `git status` stayed clean — cost if wrong: none.

## Open issues, ruled by the controller (2026-10-30; owner unavailable)

The draft left its open issues outside the document, and the reviews added some. Each is ruled here as a controller recommendation. Those marked (owner) join the owner's list when this plan merges.

1. (owner) **The converse refusals.** Design §5.7's "0 Ω for a series position and open for a shunt position" is read as exclusive (the converse ruling). The owner confirms.
2. (owner) **The acceptance's compare** against the ground-pour variant (design §5.14 item 3) is plan 4's fixture and plan 5's offscreen run; Task 9 compares two value sets of one board.
3. (owner) **Verify's ideal network.** Verify places ideal values (C-38), so its S11, resonance and far field describe the network without the 0402 presets the retune applies: at f0 the snapped set reads C2 +12 %, C3 +18 % and L1 +2 % in the retune, enough to move a resonance by more than the thresholds. The texts now say so, and Task 9 measures the gap. An antenna's verify could place each part at its preset reactance at f0 (C_eff = −1/(ω0·X), L_eff = X/ω0): one number per part, v1 untouched.
4. **The thresholds and the resonance screen are provisional.** 0.3 % of f0 and 0.2 dB until P3-D; the bandwidth is judged by the frequency threshold; the −6 dB depth screen rejects the fixture's −5.9 dB minimum, where 0.01 dB of noise moved the argmin by σ 4.3 MHz in the physics review's model, but a broad −7 dB minimum still passes it. P3-D notes that a resonance's noise scales with 1/curvature of its dip, so a % of f0 measured on the fixture's broad minimum does not carry over to a matched dip. The draft's issue that the parabola's vertex "can land far off the grid" is withdrawn: the vertex stays within half a grid step of the argmin (20,000 random curves, physics review); the argmin is the risk.
5. **The what-if η_tot** generalises the design's formula with the loss budget (the what-if ruling). It still takes η_rad from verify's ideal network and assumes the matching network neither radiates nor changes the board's own loss; the line says what-if.
6. **Compare's ceilings:** text equality of values, S2P parts compared at their stored values, and curve ports, which verify refuses. Each is a ponytail comment; port_value equality, or a refusal for a part with an S2P file, if users meet them.
7. **The fingerprint's false refusals.** A variant board that renames its radio (another start pad) is refused until renamed back; a lid-height study is refused by design, the lid height being a setting.
8. (owner) **Machine time.** Task 9 expects 2–3 h; its worst case is about 6.5 h: the run's 4 h 14 min as printed (about 3 h 45 min at the first run's ratio of 1.128) and two verify jobs up to about 75 min each to T_max.
9. (owner) **The native review** of `po/pt_BR.po` stays an owner item; this plan's msgstrs follow its glossary ruling.
10. **Prototype numbers.** A missed prototype number stops its task for a ruling (Global Constraints). The controller rules from the measured value and the formula that differs, never by loosening a test without that reason.
11. **The GUI** refuses antenna projects until plan 5, whose items now name `current_verify`, `s11_at`, the G_ wordings and `verify_stale`'s bypasses.
12. **The fake's verify has no dip** (star(f, 1) holds |S11| 0.9025 at every f), so the integration tests check I_RESONANCE_NOT_COMPARED there and the unit tests check the shift.

## Controller amendment at commit (2026-10-30; owner unavailable)

- **Task 9's first value set is searched, not typed.** The draft's typed 3.1 nH, 0.95 pF and 1.25 pF were not tuned to the run's layout, and the plain fixture's lowest |S11| was −5.9 dB, above the −6 dB screen: such a set would likely give verify and compare no dip to judge. Step 3 now takes the E24 set (or bypass) that the retune's own closing makes best matched over the band, found in scratch from the run's layout, so verify's resonance comparison and compare's deltas meet a real match, and the ideal network's gap is measured where it matters. Step 4's retune check reads the searched values. No committed code changes — controller recommendation, owner unavailable — cost if wrong: one retune.
