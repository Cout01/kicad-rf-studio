# Stage 3 Plan 4: The Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Run gates P3-B to P3-E on the synthetic fixtures with pre-registered criteria, write their reports with machine time predicted and measured, and land the antenna-only defaults, the cost refit and the significance thresholds the gates set.

**Architecture:**
- **One shared runner, thin gate tools.** `tools/p3.py` drives the product through its CLI (`p0.cli`, `p0.cli_run`) in one gates folder `<GATES>` entered by `p0.enter`: a base project from `new`, each variant a `project.json` edit in its own folder, resumable `p0.step`s keyed by model, preset and values, a free run built on `p3a._free`, in-process measurements through `pipeline.antenna_result`, the one pair rule that P3-B and P3-C share, and a one-code check over every gate's records. `tools/p3b.py` (with the hand-built openEMS model in `tools/p3b_hand.py`, always run in its own process), `tools/p3c.py` and `tools/p3d.py` (P3-D and P3-E) each hold their steps, a `decide()` against a criteria JSON committed before any run, and their tables.
- **Product changes before the runs, none during them:** an antenna-only `copper` field (`"solid"` or `"sheet"`), whose sheet branch builds each copper layer as a zero-thickness sheet at its dielectric face, and an optional antenna `flat_s` (the flat window in s), so that a run that ends flat reruns as a project edit. `src/` is then frozen through the runs; the defaults, the cost refit and the thresholds land after the last run as antenna-only constants with amendments A-35 to A-40.

**Tech Stack:**
- Python ≥ 3.11 (dev venv 3.14.2), numpy, shapely, scikit-rf, h5py. No new dependency.
- openEMS 0.37.0 and CSXCAD 0.7.0: in the product's workers and in the hand model's child process only.
- KiCad 9's bundled Python with its isolated profile, for the fixture variants only (Tasks 7 and 11).
- pytest (`openems` marker for the test that runs the hand mesh in a child process); `tools/catalog.py` (Babel, dev extra).

**Spec:**
- `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md` (binding): §5.12 item 4, with §1, §3, §4, §5.2, §5.3, §5.4, §5.8, §5.9, §5.11, §5.13 (§9: P3-A to P3-F), §5.14 item 2, §7 and §8.
- The Stage 1 spec `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`: §3.2, §5.1, §5.3, §5.4, §5.5, §6.3, §6.4 and §9. Task 14 lands A-35 to A-40 with their exact text.
- Plans 1 to 3 (`docs/superpowers/plans/2026-10-29-stage3-plan1-far-field-engine.md`, `2026-10-29-stage3-plan2-antenna-project.md`, `2026-10-30-stage3-plan3-matching-and-comparison.md`), the records `docs/validation/2026-10-29-p3-a.md`, `2026-10-30-antenna-first-run.md` and `2026-10-30-antenna-matching-run.md`.
- Research (git-ignored): `.superpowers/sdd/stage3-plan4-research/` r1 (P3-B), r2 (P3-C), r3 (P3-D, P3-E), r4 (machinery); `.superpowers/sdd/stage3-research/r4-references/`.

**Branch:** `stage3-plan4`, from `main` at `749c30e`. This plan is `docs/superpowers/plans/2026-10-30-stage3-plan4-the-gates.md`. Commands run from the repo root with `.venv/Scripts/python`. Line references are `main`'s at `749c30e`; find a moved line by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage3-plan4 main`; `git diff --stat 749c30e HEAD -- src tests tools po pyproject.toml` prints nothing.
2. Commit this plan on the branch.
3. After Task 14: the whole-branch review, a local fast-forward merge into `main`, delete the branch. Nothing is pushed.

## Global Constraints

- **v1 byte for byte** (design §3, §4): v1 projects, model specs, `spec_hash`, `model.json`, `project.json`, `new`'s lines and `results/` files stay as `tests/test_golden_v1.py` and the v1 suites pin them. A task that moves a pin is wrong: stop and get a ruling, never re-record.
- **Antenna only:** every new branch tests `core.project.antenna(data)`; the sheet branch reaches the model through `copper_model` and the spec key `"copper": "sheet"`, written only for an antenna. v1's `MESH_N`, `T_MAX_S`, `FLAT_S`, `PRESETS`, `GATES`, `BAND_FACTOR` never change; a gate's default lands as an antenna constant.
- **Criteria before runs:** `tests/fixtures/p3b/criteria.json`, `tests/fixtures/p3c/criteria.json` and `tests/fixtures/p3d/criteria.json` are committed (Tasks 4, 5, 8) before any gate run; nothing in them changes after a run. A branch they pre-register (a raised T_max or flat window, re-searched values, the refined mesh) is taken through a `tools/` constant (`p3c.RAISED`, `p3d.VALUES`, `p3d.REFINE`), recorded as a deviation.
- **References never regenerated:** P3-B's `tests/fixtures/p3b/references.json` is committed after the hand run and before the product's side (Task 9); `p3b.references()` refuses one whose `script_sha256` is not `tools/p3b_hand.py`'s.
- **src frozen** from the first gate run to the last (Tasks 9–11): `p0.step` keys every record `@code_id` (`git rev-parse HEAD:src`) and every gate's report goes through `p3.records`, which refuses records of two codes; P3-B's hand runs, keyed by the hand module alone, are outside it. Checkpoint decisions go into `tools/` constants or project edits, never `src/`. A fix between gates is a ruling; finished gates' reports stand only when `p0.model_key` of their variants is unchanged.
- **One openEMS command at a time** on an idle PC; each block one background PowerShell call from Task 9's template; codes and times appended to `<GATES>\logs\ledger.txt`; a controller checkpoint after each block, recorded in the plan's ledger. A commit made during Tasks 9–11 runs the full suite first, between blocks, never alongside one.
- **`<GATES>` = `$HOME\krs-gates`:** outside TEMP (Storage Sense) and every work tree, never the real data folder nor a `kicad-rf-studio-p0*` folder (`p3.enter` refuses those two). Every command sets `CSXCAD_INSTALL_PATH = "<openEMS folder>"` in the same call, never in a file.
- **openEMS stays in workers** (Stage 1 §3.1): the CLI, the orchestrator, `core.post`, the gate tools and pytest's own process never import openEMS or CSXCAD; `tools/p3b_hand.py` imports them only inside `mesh()` and `run()`, always in a child process.
- **Messages:** every new or changed product message is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, compiled by `.venv/Scripts/python tools/catalog.py` in the same task (run, set the msgstr, run again). A word passed as a parameter is a `T_` code; numbers keep the decimal point; a msgstr keeps every identifier, option, quoted text and dotted number. The gate tools print plain English, as `tools/p3a.py` does.
- **Tests:** test-first. Tier (a) never runs openEMS, KiCad, the network or a build: the fake worker through `p0_out`, `calibrated`, `fake` and `test_p0.in_process`. `KrsError` tests check `.code` and `.params`. Tests never touch a real KiCad folder, the Documents folder, KiCad's settings or the real data folder. A test that a later default would move names the field it needs (`copper`, `mesh.n`, `air_gap_mm`).
- **Prototype numbers:** a number this plan gives from the architect's or the reviser's in-memory probes (the sheet model's lines, materials and dt reference, the fit2d errors, the cell counts, the port box) that the code misses stops the task: report both values and the formula that differs. The pin changes only on a ruling.
- **Full suite** before every commit: `.venv/Scripts/python -m pytest -q`, about 20 minutes, alone, in the background, waited on.
- **Git:** no push; the pre-commit privacy gate runs on every commit, never `--no-verify`; no commit message carries a co-author line; use the messages as given. No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name: write `<openEMS folder>`, `<KiCad 9 bin folder>`, `<GATES>`, `<RUN>`.
- **Files:** every new `.py` starts with `# SPDX-License-Identifier: GPL-3.0-or-later`; code and docs in English.
- **Workflow:** `graphify query "<question>"` before reading code; `graphify update .` after each commit. Ponytail: reuse `p0` (enter, step, records, cli, cli_run, summary, edit, model_key, predicted_s, save, table, versions, machine), `p3a._free` and `p3a._cell`, `p0c`'s base/variant pattern, `pipeline.antenna_result`, `core.post.antenna` (`resonance`, `dip_resonance`, `deltas`), `cell_split`, `core.mesh.gates.fit2d`, the fake worker; a `ponytail:` comment on each corner cut with a known ceiling.

## Review Focus

1. **A gate tool resumed after a reboot or a kill mid-run.** The interrupted step leaves no record, runs again from scratch in a new run folder, and the dead run's project lock is reclaimed (W_STALE_LOCK). Check: Task 1's `test_an_interrupted_step_leaves_no_record_and_runs_again` (a dead pid's lock left behind); Task 10's checkpoints name any orphaned run folder in the report.
2. **A gate assembled from records of two product codes,** after a ruled src fix between runs. Every gate's report goes through `p3.records`, which refuses two codes; P3-B's hand runs, keyed by the hand module alone, neither block it nor rerun. Check: Task 1's `test_a_gate_is_never_assembled_from_two_product_codes`; Task 4's `test_a_hand_run_is_kept_by_the_hand_modules_hash_alone`.
3. **A pre-registered criterion read with the wrong unit or sign.** Every criteria key names its unit (`_rel` a fraction of f, `_db`, `_mm2`); every delta check is `abs()` against an inclusive limit, a level check is signed (the hand's `decay_db` ≤ −40), and `None` fails. Check: each gate's decide test puts a value just inside each limit, one just past it, a negative delta and, for P3-B, a hand run that grew 45 dB (Tasks 4, 6, 8).
4. **A run that ends at T_max or flat judged as converged.** Every comparison that reads it is not judged and the verdict stays "incomplete" until it reruns at the raised T_max or the widened flat window (`p3c.RAISED`, a project edit); P3-B's valid check needs the product's job converged. Check: Task 6's `test_a_run_at_t_max_or_flat_is_no_converged_comparison`; Task 4's T_max case; Task 2's `test_an_antennas_flat_window_may_be_set_in_project_json`.
5. **Sheet copper meeting verify's lumped parts or a real openEMS only after src is frozen.** Its zero-height port boxes, grid parts and fills must build and run before the first gate run. Check: Task 2's `test_sheet_copper_puts_verifys_network_in_the_sheets_plane`; Task 9 Step 1's real `cost` of the three fixtures and a short run, retune and verify of the sheet pi project.

---

## File structure

```
tools/p3.py, tests/test_p3.py, tools/p3a.py (_free's free length)                                   # T1
src/kicad_rf_studio/core/project.py, core/geometry/__init__.py, core/model/spec.py, core/model/csx.py,
  pipeline.py (fingerprint), core/messages.py, po/*, the .mo                                          # T2
tools/p3b_hand.py, tests/test_p3b.py (hand part)                                                    # T3
tools/p3b.py, tests/fixtures/p3b/criteria.json, tests/test_p3b.py (gate part)                       # T4
tools/p3c.py, tests/fixtures/p3c/criteria.json, tests/test_p3c.py (steps)                           # T5
tools/p3c.py, tests/test_p3c.py (rules, report)                                                     # T6
tools/make_fixtures.py, tests/fixtures/ifa2g4_pi_{shift,dxp,dxm,pour}.{kicad_pcb,pads.json},
  tests/test_antenna_geometry.py, tests/test_cli_antenna.py (BANDS), tests/test_board.py,
  tests/test_fixtures.py, tests/test_pads.py                                                         # T7
tools/p3d.py, tests/fixtures/p3d/criteria.json, tests/test_p3d.py                                   # T8
tests/fixtures/p3b/references.json, docs/validation/<date>-p3-b.{md,json}                           # T9
tools/p3c.py (RAISED, on its branch), docs/validation/<date>-p3-c.{md,json}                         # T10
tests/test_antenna_geometry.py (D, EDITS), tools/make_fixtures.py and the moved boards (n 3 or the
  refine branch), tools/p3d.py (VALUES, REFINE, on their branches), docs/validation/<date>-p3-{d,e}.* # T11
tools/p3.py (rows, refit), tests/test_p3.py, docs/validation/<date>-p3-refit.{md,json},
  src/kicad_rf_studio/runs.py, pipeline.py (cost_notes), messages, po, tests/test_cost_model.py     # T12
src/kicad_rf_studio/core/project.py, cli.py, pipeline.py (gate_lines, n 3 only), core/post/antenna.py,
  core/geometry/__init__.py, core/geometry/region.py, stoprule.py, core/mesh/rule.py (comment),
  messages, po                                                                                       # T13
docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md, the Stage 3 design             # T14
```

---

### Task 1 [code]: The gates' shared runner

**Files:**
- Create: `tools/p3.py`, `tests/test_p3.py`.
- Modify: `tools/p3a.py` (`_free` takes its free length).

**Interfaces:**
- Consumes: `p0.enter`, `p0.cli`, `p0.cli_run`, `p0.step`, `p0.records`, `p0.model_key`, `p0.edit`, `p0.summary`, `p0.predicted_s`, `p0.run_path`, `p0.FIX`; `p3a._free`; `pipeline.load`, `build_model`, `antenna_result`; `core.post.antenna.resonance`, `dip_resonance`; `core.model.spec.cell_split`, `spec_hash`; `core.model.readers.read_stats`; `runs.data_dir`, `load_settings`, `machine_key`, `per_job_mcs`, `PML_WEIGHT`, `SMALL_SPEED`; `core.project.load_project`, `save_project`, `parts`; `tests/test_p0.in_process`.
- Produces (in `tools/p3.py`):
  - `enter(out: Path) -> Path`; `project_path(out: Path, name: str) -> Path`; `base(out: Path, board: str) -> Path`; `variant(out: Path, name: str, board: str, edits: dict) -> Path`.
  - `step_id(name: str, command: str) -> str` (`f"p3-{name}-{command}"`, command `"run"`, `"verify"` or `"free"`).
  - `run_step(out: Path, name: str, command: str = "run") -> dict`; `free_step(out: Path, name: str, t_free: float) -> dict`; `records(out: Path, ids: list[str]) -> list[dict]`.
  - `measure(out: Path, name: str, command: str = "run") -> dict | None`; `pair(a: dict, b: dict, limit: float, conditioned_db: float) -> dict`; `predicted_s(spec: dict, dt: float, t: float, pool: int, jobs: int, mcs: float) -> float`; `calibration() -> dict`; `run_steps(names: list[str], work: Callable[[str], object]) -> int`.
  - `p3a._free(spec: dict, sid: str, t_free: float = T_FREE) -> dict`.

- [ ] **Step 1: Write the failing tests,** `tests/test_p3.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
import sys

import numpy as np
import pytest

import p0
import p3
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.model.spec import cell_split
from kicad_rf_studio.core.project import load_project
from test_p0 import in_process

F = np.linspace(2.3e9, 2.5e9, 201)


@pytest.fixture
def gates(p0_out, monkeypatch):
    """p0_out entered as <GATES>, the CLI in this process (the fake worker), no other process seen."""
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    return p3.enter(p0_out)


def test_a_run_step_runs_the_product_once_and_measures_it(gates, monkeypatch):  # design 5.11; r4 1
    pj = p3.variant(gates, "ifa2g4-solid-n2", "ifa2g4", {})
    assert pj == gates / "projects" / "ifa2g4-solid-n2" / "project.json" and load_project(pj)["band"]["f_lo_hz"] == 2.4e9
    record = p3.run_step(gates, "ifa2g4-solid-n2")
    assert record["step"] == "p3-ifa2g4-solid-n2-run" and record["result"]["exit"] == 0
    monkeypatch.setattr(p0, "cli_run", lambda *a: pytest.fail("a recorded step ran again"))
    assert p3.run_step(gates, "ifa2g4-solid-n2") == record
    m = p3.measure(gates, "ifa2g4-solid-n2")
    spec = json.loads((p0.run_path(m["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    assert m["split"] == list(cell_split(spec)) and m["pool"] == 1 and m["speeds_mcs"] == [100.0]  # the fake's
    assert m["jobs"][0]["verdict"] == "converged" and m["cal_mcs"] == 200.0  # calibrated: single {"2": 200.0}
    assert m["f_res_hz"] == pytest.approx(2506.4e6, abs=0.1e6) and m["depth_db"] == pytest.approx(-33.0, abs=0.1)
    assert m["conditioned"] is True and len(m["eta_rad"]) == len(m["far_f_hz"]) == 2  # the fake's sphere fixture
    assert m["band"] == [2.4e9, 2.4835e9]
    project, board, geom, _ = pipeline.load(pj)  # the product's own lines, from the same run
    setup = json.loads((p0.run_path(m["run_dir"]) / "job-0-setup" / "setup.json").read_text(encoding="utf-8"))
    notes = dict(pipeline.cost_notes(pipeline.build_model(project, board, geom), project, setup, 2, 1, 200.0))
    assert notes["I_COST_PREDICTED"]["time"] == pipeline.duration(m["predicted_s"])
    assert notes["I_COST_TIME"]["time"] == pipeline.duration(m["worst_s"])


def test_an_interrupted_step_leaves_no_record_and_runs_again(gates, monkeypatch):  # RF 1
    pj = p3.variant(gates, "ifa2g4-solid-n2", "ifa2g4", {})
    real = p0.cli_run

    def killed(*a):  # a reboot or taskkill mid-run: cli_run raises, so p0.step stores nothing
        raise RuntimeError("killed")

    monkeypatch.setattr(p0, "cli_run", killed)
    with pytest.raises(RuntimeError):
        p3.run_step(gates, "ifa2g4-solid-n2")
    assert not (gates / "steps" / "p3-ifa2g4-solid-n2-run.json").exists() and p3.measure(gates, "ifa2g4-solid-n2") is None
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()  # the killed run's project lock, its pid gone: runs.project_lock reclaims it (W_STALE_LOCK)
    lock = pj.with_name("project.json.lock")
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    monkeypatch.setattr(p0, "cli_run", real)
    assert p3.run_step(gates, "ifa2g4-solid-n2")["result"]["exit"] == 0 and not lock.exists()


def test_a_variant_keeps_its_own_results_and_an_edit_reruns_it(gates):  # design 5.11; r4 1
    p3.variant(gates, "n", "ifa2g4", {})
    p3.variant(gates, "s", "ifa2g4", {"preset": "strict"})
    normal, strict = p3.run_step(gates, "n"), p3.run_step(gates, "s")
    assert normal["key"].split("|")[0] == strict["key"].split("|")[0] and normal["key"] != strict["key"]
    assert load_project(p3.project_path(gates, "s"))["mesh"]["n"] == 2  # the preset alone: new --preset's n 3 trap
    p3.variant(gates, "n", "ifa2g4", {"t_max_s": 31e-9})  # T_max is in the model
    assert p3.measure(gates, "n")["f_res_hz"] is None  # stale results measure as none (antenna_result)
    assert p3.run_step(gates, "n")["key"] != normal["key"]  # and the step runs again
    assert p3.measure(gates, "n")["f_res_hz"] is not None


def test_a_free_step_runs_to_its_free_length(gates):  # design 5.11 P3-C; ruling 4
    p3.variant(gates, "ifa2g4-solid-n2", "ifa2g4", {})
    record = p3.free_step(gates, "ifa2g4-solid-n2", 33e-9)
    result = record["result"]
    assert record["step"] == "p3-ifa2g4-solid-n2-free" and result["t_max"] == 33e-9 and result["finite"]
    assert result["growth_db"] == 0.0 and result["run_dir"].startswith("p3-ifa2g4-solid-n2-free-")
    assert p3.measure(gates, "ifa2g4-solid-n2", "free")["t_max"] == 33e-9


def test_the_gates_folder_is_never_the_data_folder_nor_p0s(tmp_path, monkeypatch):  # ruling 7
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data" / "kicad-rf-studio")
    for out in (tmp_path / "data" / "kicad-rf-studio" / "gates", tmp_path / "kicad-rf-studio-p0-x"):
        with pytest.raises(SystemExit):
            p3.enter(out)
        assert not out.exists()


def test_a_gate_is_never_assembled_from_two_product_codes(gates):  # RF 2; p0.records
    for sid, code in (("p3-a-run", "x"), ("p3-b-run", "y")):
        p0.save(gates / "steps" / f"{sid}.json", {"step": sid, "code": code})
    assert [r["step"] for r in p3.records(gates, ["p3-a-run", "p3-c-run"])] == ["p3-a-run"]  # a step not run is left out
    with pytest.raises(SystemExit):
        p3.records(gates, ["p3-a-run", "p3-b-run"])


def test_a_blocked_run_is_recorded_and_measures_as_none(gates):  # p0.cli_run stores exits 2 to 4
    p3.variant(gates, "blocked", "ifa2g4", {"gates.fit2d_limit": 0.001})  # fit2d reads 0.99 % at n 2: exit 3
    assert p3.run_step(gates, "blocked")["result"]["exit"] == 3
    m = p3.measure(gates, "blocked")
    assert (m["jobs"], m["split"], m["predicted_s"], m["worst_s"], m["f_res_hz"]) == ([], None, None, None, None)


def meas(f_res, depth=-12.0, d=2.57, eta=0.81):  # a measure's shape: a dip of `depth` dB at f_res, a parabola in dB
    s11 = 10 ** ((depth + 8 * ((F - f_res) / 50e6) ** 2) / 20) + 0j
    return {"f_hz": F, "s11": s11, "band": [2.4e9, 2.4835e9], "d_dbi": d, "far_f_hz": [2.44175e9], "eta_rad": [eta]}


def test_a_pair_is_judged_by_its_resonance_and_explained_by_its_s11():  # ruling 1; RF 3
    p = p3.pair(meas(2.4e9), meas(2.43e9, d=2.77, eta=0.81 * 10 ** -0.01), 0.01, -6.0)
    assert p["f_res"] == pytest.approx([2.4e9, 2.43e9]) and p["f_rel"] == pytest.approx(0.0125)
    assert (p["conditioned"], p["pass"], p["explained"]) == (True, False, False)
    assert p["d_db"] == pytest.approx(0.2) and p["eta_db"] == pytest.approx(0.1) and p["ds11_shift"] > 0
    edge = p3.pair(meas(2.4e9), meas(2.52e9), 0.01, -6.0)  # its lowest |S11| at the grid's end: no dip
    assert edge["conditioned"] is False and edge["f_res"][1] == 2.5e9


def test_an_unconditioned_miss_is_explained_within_its_shift_equivalent():  # ruling 1, amended at commit
    x, turn = (F - 2.4e9) / 100e6, np.exp(-2j * np.pi * F * 1.7e-9)  # the first run's phase slope

    def broad(tilt_db):  # a broad -5.9 dB minimum at 2.4 GHz, tilted per 100 MHz
        return {**meas(2.4e9), "s11": 10 ** ((-5.9 + 0.5 * x ** 2 + tilt_db * x) / 20) * turn}

    near = p3.pair(broad(0.0), broad(-0.6), 0.01, -6.0)  # the argmins 60 MHz apart, the curves about 0.03 apart
    assert (near["conditioned"], near["pass"], near["explained"]) == (False, False, True)
    assert near["ds11"] < 0.05 < 0.1 < near["ds11_shift"] < 0.2  # a 1 % shift moves S11 by about 0.14 here
    far = p3.pair(broad(0.0), broad(-5.0), 0.01, -6.0)  # about 0.20 apart in band: more than a 1 % shift
    assert far["explained"] is False and far["ds11"] > far["ds11_shift"]
```

  `2506.4e6` and `−33.0 dB` are plan 3's probe of the default fake's M = 0 S11 (plan 3, Task 8 note); the fake's far field is `tests/fixtures/farfield/sphere.h5`, two frequencies (`test_match_antenna.py:142`). The 11 frequencies belong to the real runs.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_p3.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p3'`.
- [ ] **Step 3: `tools/p3a.py`.** `_free(spec, sid, t_free=T_FREE)`: every `T_FREE` in its body becomes `t_free`, its docstring says "to `t_free` (T_FREE by default)". `main` is unchanged, so P3-A's keys and `tests/test_p3a.py` stand.
- [ ] **Step 4: `tools/p3.py`.** Module docstring: "The gates P3-B to P3-E's shared runner (Stage 3 design 5.11, plan 4): the gates folder, the base project from `new` and its variants, resumable run, verify and free steps through the product's CLI, the one-code check over a gate's records, in-process measurements and the pair rule P3-B and P3-C share. Dev-time only, like p0."
  - **`enter(out)`:** SystemExit, with nothing made, when `out.resolve()` is inside `runs.data_dir().resolve()` (read before entering) or `out.name` starts with `"kicad-rf-studio-p0"`; else `p0.enter(out)`.
  - **`base(out, board)`:** copies `p0.FIX / f"{board}.kicad_pcb"` to `out / "boards"` once; when `project_path(out, board)` is missing, `p0.cli("new", str(<copy>), "--start", "U1.1", "--antenna", "AE1", "--band", "902MHz:928MHz" if board.startswith("meander") else "2400MHz:2483.5MHz", "-o", str(<its folder>))`, RuntimeError naming the exit code and the last line on a non-zero exit. Every CLI argument is a str (the tests' in-process CLI is argparse's). Returns the project file.
  - **`variant(out, name, board, edits)`:** `tools/p0c.py`'s `variant`: made once as a copy of `base(out, board)` without `results` and `verify`, then `p0.edit` with `edits` on every call, saved only when they change it. Returns the project file.
  - **`run_step(out, name, command)`:** `p0.step(out, step_id(name, command), key, lambda: p0.cli_run(pj, command))`, `pj = project_path(out, name)`, key `f"{p0.model_key(pj)}|{project['preset']}"`, plus `"|" + ",".join(f"{ref}={value}" for ref, value in sorted(values.items()))` for `verify`, the values of the parts whose role is port or curve_port. No `cost` runs: the run's own events carry the cost lines, and `measure` predicts from the formula.
  - **`free_step(out, name, t_free)`:** the spec of `name`'s model (`pipeline.load`, `build_model`), then `p0.step(out, step_id(name, "free"), f"{spec_hash(spec)}@{t_free!r}", partial(p3a._free, spec, step_id(name, "free"), t_free))`.
  - **`records(out, ids)`:** `p0.records(out, [i for i in ids if (out / "steps" / f"{i}.json").is_file()])`: the recorded ones, SystemExit when two codes. Every gate's `write` calls it over its product steps first.
  - **`measure(out, name, command)`:** None when the step has no record. For `"free"`: the record's result plus `"cells"`, `"split"` (from its run folder's model.json) and `"wall_s"` (the step's). Else `p0.summary(record)`'s dict with `"predicted_s"` and `"worst_s"` recomputed by `predicted_s` (to the longest kept t_stop and to the spec's T_max: what `cost` prints before the run), plus:
    - `"split"`: `list(cell_split(spec))` of the run folder's model.json; `"cal_mcs"`: the per-job MC/s that prepare(small=True) uses at the run's pool, from this machine's calibration entry (as p3a reads it): at a pool of 1 `entry["single"][str(entry["threads"])]` (else `runs.per_job_mcs(entry, 1)`), else `runs.per_job_mcs(entry, pool)`, commented `# mirrors pipeline.prepare(small=True)`; `"speeds_mcs"`: each job's openEMS_stats.txt speed in MC/s. Each None when model.json, the pool or a kept job is missing (exits 2, 3 and 4 are recorded).
    - From `pipeline.antenna_result(pj)` (a KrsError gives None to each): `"f_hz"` and `"s11"` (the band grid and S11, kept in memory; the gates drop them from their JSON), `"band"` (`[f_lo, f_hi]`), `"f_res_hz"` and `"depth_db"` (`resonance` and |S11| there in dB), `"conditioned"` (`dip_resonance` finds a dip: the lowest |S11| inside the grid at or below −6 dB), `"far_f_hz"`, `"d_dbi"` (10·log10 of `d_max` at the first recorded frequency, f0), `"eta_rad"` and `"eta_tot"` (lists, recorded order). Python floats and bools, never numpy's.
  - **`pair(a, b, limit, conditioned_db)`:** ruling 1's pair rule (as amended at commit) on two measures (or measure-shaped dicts: `"f_hz"` and `"s11"` on one grid, `"band"`, `"d_dbi"`, `"far_f_hz"`, `"eta_rad"`): `"f_res"` [f_a, f_b] and `"depth_db"` by `resonance` on each; `"f_rel"` |f_b − f_a|/f_a; `"conditioned"` both argmins inside the grid and both depths ≤ `conditioned_db`; `"ds11"` the largest |S_b − S_a| over [f_lo, f_hi] of a's band; `"ds11_shift"` the largest |S_a(f·(1 + limit)) − S_a(f)| there, S_a interpolated in its real and imaginary parts (what a shift of the limit does to S11; past the grid's end `np.interp` holds the last value, which can only make the explanation stricter); `"pass"` f_rel ≤ limit; `"explained"` not pass, not conditioned and ds11 ≤ ds11_shift (the curves differ by no more than a shift of the check's own limit moves a's); `"d_db"` |D_b − D_a| at f0; `"eta_db"` the largest |10·log10(η_b/η_a)| over a's recorded frequencies, b's matched by nearest; D and η None when either side lacks them. Python floats and bools.
  - **`predicted_s(spec, dt, t, pool, jobs, mcs)`:** `p0.predicted_s(jobs, pool, cells + (runs.PML_WEIGHT - 1) * pml, dt, t, mcs * runs.SMALL_SPEED)`, cells Π len(mesh lines), pml `cell_split(spec)[2]`: cost_notes' antenna formula. Comment `# mirrors the time() in pipeline.cost_notes for an antenna`.
  - **`calibration()`:** this machine's entry's `aggregate_mcs`, `pool`, `threads`, `single` and `levels`, never its key (a host name).
  - **`run_steps(names, work)`:** p3a's loop: prints `p3: <name>`, calls `work(name)`, on an Exception prints the traceback and goes on (SystemExit and KeyboardInterrupt end it); returns 1 when one raised, else 0.
  - `# ponytail: no keep-awake call: this PC's sleep timeout is 0; a reboot loses the running step, which reruns`.
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_p3a.py tests/test_p0.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/p3.py tools/p3a.py tests/test_p3.py
git commit -m "test(gates): the shared runner of gates P3-B to P3-E, variants, resumable steps, one-code records, measurements and the pair rule through the product's CLI (Stage 3 design 5.11)"
graphify update .
```

---

### Task 2 [code]: Sheet copper and the flat window for antennas

**Files:**
- Modify: `src/kicad_rf_studio/core/project.py` (`COPPER_MODELS`, `ANTENNA_COPPER`, `copper_model`, `_FIELDS_ANTENNA`, `make_antenna_project`); `core/geometry/__init__.py` (`build_geometry`); `core/model/spec.py` (`excitation`, `model_spec`); `core/model/csx.py` (`_prism`, `build_csx`); `pipeline.py` (`fingerprint`); `core/messages.py`; `po/*` and the `.mo`.
- Test: `tests/test_project.py`, `tests/test_antenna_model.py`, `tests/test_model_spec.py`, `tests/test_model_csx.py`, `tests/test_match_antenna.py`.

**Interfaces:**
- Consumes: `zstack`, `Stackup.from_json`, `model_spec`, `verify_spec`, `far_field_box`, `flat_window`, `fingerprint`; the tests' `antenna_project`, `model_of`, `antenna_dict`, `project_of`.
- Produces: `COPPER_MODELS = ("solid", "sheet")`, `ANTENNA_COPPER = "solid"`, `copper_model(data: dict) -> str` (`data.get("copper", "solid")`); project.json's optional antenna fields `copper` and `flat_s` (s); the antenna-only spec key `"copper": "sheet"`; `_prism(prop, solid: dict, priority: int, sheet: bool = False) -> None`; T_EXPECT_COPPER.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_project.py` (imports gain `copper_model`): `test_a_schema_2_field_out_of_its_range_is_named`'s list gains `({"copper": "foil"}, "copper", "T_EXPECT_COPPER")` and `({"flat_s": 0}, "flat_s", "T_EXPECT_ABOVE_0")`, and:

```python
def test_an_antennas_copper_is_solid_or_sheet_and_optional():  # design 5.3; ruling 3
    d = antenna_dict()
    assert d["copper"] == "solid" and copper_model(d) == "solid" and "flat_s" not in d
    assert check_project({**d, "copper": "sheet", "flat_s": 4.4e-8}, Path("p.json"))["copper"] == "sheet"
    old = {k: v for k, v in d.items() if k != "copper"}  # a project made before this version
    assert check_project(old, Path("p.json")) is old and copper_model(old) == "solid"
```

  - `tests/test_antenna_model.py` (imports gain `load_project`, `save_project`, `spec_hash`, `parts`, `verify_spec`, `far_field_box` and `spec_module` where missing):

```python
def test_sheet_copper_puts_each_copper_layer_at_its_dielectric_face(tmp_path):  # design 5.3; P3-C
    pj = antenna_project(tmp_path / "sheet")
    save_project(pj, {**load_project(pj), "copper": "sheet"})
    model, _, _ = model_of(pj)
    s = model.spec
    assert model.blocked == [] and [len(s["mesh"][a]) for a in "xyz"] == [135, 137, 69] and s["copper"] == "sheet"
    assert {tuple(c["z"]) for c in s["metal"]["copper"]} == {(0.0, 0.0), (0.71, 0.71)}
    assert [(m["name"], m["solids"][0]["z"]) for m in s["materials"]] == [
        ("substrate_0", [0.0, 0.71]), ("mask_F_coat", [0.71, 0.81]), ("mask_B_coat", [-0.1, 0.0])]  # no 0-thick fill
    assert [(q["start"][2], q["stop"][2]) for q in s["ports"]] == [(0.71, 0.71)]  # a port in the sheet's plane
    assert model.dt_ref == pytest.approx(2.3057e-13, rel=1e-4) and s["nf2ff"]["center"][2] == 0.355
    solid_pj = antenna_project(tmp_path / "solid")
    save_project(solid_pj, {**load_project(solid_pj), "copper": "solid"})  # named: a sheet default moves no pin here
    solid, _, _ = model_of(solid_pj)
    assert "copper" not in solid.spec and spec_hash(solid.spec) != spec_hash(s) and len(solid.spec["mesh"]["z"]) == 71


def test_sheet_copper_puts_verifys_network_in_the_sheets_plane(tmp_path, monkeypatch):  # design 5.3, 5.7; RF 5
    pj = antenna_project(tmp_path, FIX / "ifa2g4_pi.kicad_pcb")
    save_project(pj, {**load_project(pj), "copper": "sheet"})
    project, board, geom, _ = pipeline.load(pj)
    spec = pipeline.build_model(project, board, geom).spec
    by_ref = parts(project)
    by_ref["L1"]["value"], by_ref["C2"]["value"], by_ref["C3"]["value"] = "0R", "0.13pF", "1pF"  # plan 3's snapped set
    dump = tmp_path / "operator_dump.vtr"
    dump.write_bytes(b"")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    out = verify_spec(spec, by_ref, dump, 2.4e-13, far_field=far_field_box(project, board, geom))
    assert [(g["name"], g["start"][2], g["stop"][2]) for g in out["grid"]] == [("C2", 0.71, 0.71), ("C3", 0.71, 0.71)]
    added = out["metal"]["copper"][len(spec["metal"]["copper"]):]  # L1's 0 Ω box and the parts' PEC fill
    assert added and all(c["z"] == [0.71, 0.71] for c in added) and out["copper"] == "sheet"


def test_an_antennas_flat_window_may_be_set_in_project_json(tmp_path):  # design 5.4: P3-C revisits it; RF 4
    pj = antenna_project(tmp_path)
    default, _, _ = model_of(pj)
    save_project(pj, {**load_project(pj), "flat_s": 4.4e-8})
    widened, _, _ = model_of(pj)
    assert default.spec["excitation"]["flat_s"] == flat_window(2.44175e9)
    assert widened.spec["excitation"]["flat_s"] == 4.4e-8
```

  - `tests/test_model_spec.py` (imports gain `ends` and `nominal_boxes`):

```python
def test_a_v1_model_of_zero_thickness_copper_keeps_every_material():  # v1 byte for byte: a 0 mm copper builds today
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")
    p = {**p, "stackup": {**p["stackup"], "layers": [{**layer, "thickness_mm": 0.0} if layer["kind"] == "copper"
                                                      else layer for layer in p["stackup"]["layers"]]}}
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2)
    s = model_spec(p, board, g, m, [place(x, m, g.zs, g.pieces) for x in e], [])
    assert "copper" not in s and [x["name"] for x in s["materials"]] == [
        "substrate_0", "mask_F_fill", "mask_F_coat", "mask_B_fill", "mask_B_coat"]  # its 0-thick fills kept
```

  - `tests/test_model_csx.py`:

```python
def test_a_sheet_of_no_thickness_is_a_polygon_in_its_plane():  # design 5.3: sheet copper, antenna only
    calls = []

    class Prop:
        def AddLinPoly(self, *a, **k):
            calls.append(("linpoly", a, k))

        def AddPolygon(self, *a, **k):
            calls.append(("polygon", a, k))

    xy = {"x": [0.0, 1.0, 1.0], "y": [0.0, 0.0, 1.0]}
    _prism(Prop(), {**xy, "z": [0.71, 0.71]}, 1000, True)
    _prism(Prop(), {**xy, "z": [0.0, 0.035]}, 1000, True)
    _prism(Prop(), {**xy, "z": [0.71, 0.71]}, 1000)  # without the spec's key, as every v1 model: as before
    assert calls == [("polygon", ([xy["x"], xy["y"]], "z", 0.71), {"priority": 1000}),
                     ("linpoly", ([xy["x"], xy["y"]], "z", 0.0, 0.035), {"priority": 1000}),
                     ("linpoly", ([xy["x"], xy["y"]], "z", 0.71, 0.0), {"priority": 1000})]
```

  - `tests/test_match_antenna.py`, after the fingerprint test: `def test_the_fingerprint_reads_the_copper_model_and_a_flat_window(tmp_path, calibrated)`: `d = load_project(antenna_project(tmp_path / "p"))`, `fp = pipeline.fingerprint({**d, "copper": "sheet", "flat_s": 4.4e-8})`, `assert (fp["copper"], fp["flat_s"]) == ("sheet", 4.4e-8) and "flat_s" not in pipeline.fingerprint(d)`.
  - Probes (in memory on `main`, the stackup's copper set to 0 mm): ifa2g4 sheet 135 × 137 × 69, dt reference 2.3057e-13 s, nothing blocked, the materials and ports above; ifa2g4_pi sheet 135 × 143 × 69, 2.4599e-13 s, its verify grid and fills at z 0.71; meander915 sheet 216 × 153 × 77, 2.2642e-13 s (W_STAIRCASED as in solid); lpf915 with 0 mm copper builds today with its two zero-thickness mask fills.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_project.py tests/test_antenna_model.py tests/test_model_spec.py tests/test_model_csx.py tests/test_match_antenna.py -q`. Expected: FAIL (`cannot import name 'copper_model'`, `_prism` takes no `sheet`, no `"copper"` key, `flat_s` ignored).
- [ ] **Step 3: `core/project.py`.**
  - `COPPER_MODELS = ("solid", "sheet")` commented "an antenna's copper model (Stage 3 design 5.3): Stage 1 5.3's solid copper, or every copper layer a sheet, for the whole model"; `ANTENNA_COPPER = "solid"` commented "`new`'s; gate P3-C decides whether all-sheet replaces it".
  - `copper_model(data)`: "project.json's copper, else "solid": an antenna made before plan 4 has none."
  - `_FIELDS_ANTENNA["copper"] = (lambda v: v is _MISSING or v in COPPER_MODELS, "T_EXPECT_COPPER")` and `_FIELDS_ANTENNA["flat_s"] = _OPTIONAL_ABOVE_0`, after `far_field`.
  - `make_antenna_project` appends `copper=ANTENNA_COPPER` after `far_field` (its docstring adds "and copper ANTENNA_COPPER"); it writes no `flat_s`.
- [ ] **Step 4: The sheet branch and the flat window.**
  - `build_geometry`: `ant = antenna(project)` moves above the z-stack; for an antenna whose `copper_model` is `"sheet"`, `zstack` takes the stackup with each copper layer's `thickness_mm` 0.0, so each copper slab collapses onto its dielectric face and the masks rest on it; the mesh, fit2d's cross-sections (sheet against sheet) and the ports follow from `zs`. Docstring: "An antenna's sheet copper (Stage 3 design 5.3) is a stack whose copper layers have no thickness."
  - `spec.excitation`: an antenna's `"flat_s"` is `project.get("flat_s") or flat_window(project["f0_hz"])`; docstring "project.json's flat_s when it sets one (gate P3-C's widened window)".
  - `model_spec`: `sheet = antenna(project) and copper_model(project) == "sheet"`; the materials' generator leaves out a material whose solids have no thickness only when `sheet`, commented "an antenna's sheet copper leaves its slab and mask fill no thickness; v1's materials stay as they are, 0 mm copper included"; in the antenna block, `spec["copper"] = "sheet"` when `sheet`.
  - `csx._prism(prop, solid, priority, sheet=False)`: with `sheet` and z0 == z1, `prop.AddPolygon([solid["x"], solid["y"]], "z", z0, priority=priority)`; docstring "or, with `sheet` (the antenna-only spec key "copper": "sheet", Stage 3 design 5.3) and z0 == z1, a polygon in the plane z = z0". `build_csx` passes `spec.get("copper") == "sheet"` for the materials and the metal.
  - `pipeline.fingerprint`: `"copper": copper_model(project)`, and `"flat_s"` when project.json sets it (so pre-plan-4 records still compare); its ponytail comment removed. No cost line names the copper: the fingerprint and model.json's key record it.
- [ ] **Step 5: The message,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| T_EXPECT_COPPER | "solid" or "sheet" | "solid" ou "sheet" |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_sexpr.py tests/test_cli_antenna.py tests/test_antenna_geometry.py tests/test_cost_model.py -q`. Expected: PASS, the golden pins unchanged.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(antenna): a copper field, solid or sheet, whose sheet branch puts each copper layer at its dielectric face, and an optional flat window; the fingerprint reads both (Stage 3 design 5.3, 5.4)"
graphify update .
```

---

### Task 3 [code]: P3-B's hand-built model

**Files:**
- Create: `tools/p3b_hand.py`, `tests/test_p3b.py`.

**Interfaces:**
- Consumes: `tests/fixtures/ifa2g4.pads.json` (pcbnew's pads) and `tests/fixtures/ifa2g4.kicad_pcb` (its vias' text); numpy, shapely; CSXCAD and openEMS inside `mesh()` and `run()` only, in a child process.
- Produces (`tools/p3b_hand.py`):
  - Constants: `F_LO, F_HI, F0`; `F11` (f0 then 10 evenly from f_lo to f_hi, as `make_antenna_project`); `WALL_MM = 62.456762` (λ/2 at f_lo); `FINE_MM, BOARD_MM, AIR_MM, RATIO, MERGE_MM = 0.2, 2.36, 5.0, 1.4, 0.1`; `GAUSS = (2.415e9, 0.575e9)`; `END_CRITERIA, T_END_S, THREADS = 1e-5, 30e-9, 4`; `GRID_HZ` (1840 to 2990 MHz every 1 MHz); `CENTER = [107.0, -109.0, 0.39]` (mm).
  - `pads() -> dict[str, BaseGeometry]`, `rods() -> list[tuple[float, float]]`, `antenna() -> BaseGeometry` (AE1's 12 rectangles), `copper() -> dict[str, BaseGeometry]` ({"F.Cu", "B.Cu"}, mm, y up), `port() -> tuple[list[float], list[float]]`, `mesh(fine_mm: float = FINE_MM, wall_mm: float = WALL_MM) -> dict[str, list[float]]`, `run(out: Path, fine_mm: float = FINE_MM, wall_mm: float = WALL_MM) -> dict`, `script_sha() -> str`, `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing tests,** in `tests/test_p3b.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import json
import re
import subprocess
import sys

import pytest
import shapely
from shapely.geometry import Polygon

import p0
import p3b_hand
from test_cli_antenna import antenna_project
from kicad_rf_studio.core.project import load_project

BOARD = p0.FIX / "ifa2g4.kicad_pcb"


def modules(nodes) -> set[str]:
    """The top-level package of every import among `nodes`."""
    return {(a.name if isinstance(n, ast.Import) else n.module).split(".")[0]
            for n in nodes if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}


def test_the_hand_model_imports_none_of_the_product():  # ruling 7; design 5.11 P3-B: independent
    tree = ast.parse((p0.ROOT / "tools" / "p3b_hand.py").read_text(encoding="utf-8"))
    assert not modules(ast.walk(tree)) & {"kicad_rf_studio", "p0", "p3", "p3a", "p3b"}
    assert not modules(tree.body) & {"CSXCAD", "openEMS"}  # only inside mesh() and run(), in the child


def test_the_hand_antenna_is_the_footprints_polygon():  # r1 Q2: 12 rectangles, XOR the 0.3 mm drill's keyhole
    text = BOARD.read_text(encoding="utf-8")
    i = text.index("(fp_poly", text.index('(footprint "RF_Antenna:Texas_SWRA117D_2.4GHz_Left"'))
    xy = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", text[i:text.index("(stroke", i)])
    drawn = Polygon([(100 + float(x), -(100 + float(y))) for x, y in xy])  # AE1 at (100, 100), angle 0; y up
    assert len(xy) == 53 and shapely.area(shapely.symmetric_difference(drawn, p3b_hand.antenna())) <= 0.08
    assert p3b_hand.antenna().difference(p3b_hand.copper()["F.Cu"]).area <= 1e-9  # on the top copper


def test_the_hand_port_spans_the_pads_gap_on_the_top_copper():  # r1 Q3: exactly the gap, no snapping
    start, stop = p3b_hand.port()
    assert (start, stop) == ([99.03, -112.95, 0.745], [99.7, -111.0, 0.78])
    pads = p3b_hand.pads()
    assert pads["U1.2"].bounds[2] == pytest.approx(99.03) and pads["U1.1"].bounds[0] == pytest.approx(99.7)


def test_the_hand_settings_are_pre_registered(tmp_path):  # r1 R4: frozen before any run, its sha in the reference
    assert p3b_hand.WALL_MM == round(299792458 / 2.4e9 / 2 * 1e3, 6)
    assert p3b_hand.F11 == load_project(antenna_project(tmp_path))["far_field"]["f_hz"]  # the product's 11
    rods = p3b_hand.rods()  # the 35 vias and AE1.2's plated hole, the IFA's short (the product's 36 rods)
    assert len(rods) == 36 and (102.1, -100.0) in rods and BOARD.read_text(encoding="utf-8").count("thru_hole") == 1
    assert len(p3b_hand.script_sha()) == 64


@pytest.mark.openems
def test_the_hand_mesh_is_fine_on_the_antenna_and_its_walls_at_half_a_wavelength(tmp_path):  # r1 Q4
    out = tmp_path / "mesh.json"  # mesh() imports CSXCAD's smoother, so it runs in a child: pytest never loads it
    done = subprocess.run([sys.executable, "-X", "utf8", str(p0.ROOT / "tools" / "p3b_hand.py"), "--mesh", str(out)],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    m = json.loads(out.read_text(encoding="utf-8"))
    assert m["x"][0] == pytest.approx(87.0 - p3b_hand.WALL_MM) and m["y"][-1] == pytest.approx(-94.0 + p3b_hand.WALL_MM)
    start, stop = p3b_hand.port()
    for axis, v in [*zip("xyz", start), *zip("xyz", stop)]:  # the port's edges on mesh lines
        assert min(abs(v - line) for line in m[axis]) <= 1e-6
    fine = [b - a for a, b in zip(m["x"], m["x"][1:]) if 88.15 <= a and b <= 102.55]
    assert max(fine) <= 0.2 + 1e-6 and 1.0e6 <= len(m["x"]) * len(m["y"]) * len(m["z"]) <= 1.6e6
    assert "CSXCAD" not in sys.modules
```

  r1's probe built such a mesh at 159 × 156 × 51 = 1.27 M nodes; the bounds leave the seeds' exact count to the code. The architect checked the 12 rectangles against AE1's 53-point polygon: XOR 0.0687 mm². The board's text holds one plated hole, AE1.2 (pads.json centre (102.1, −100.0)), and 35 vias.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_p3b.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p3b_hand'`.
- [ ] **Step 3: `tools/p3b_hand.py`.** Module docstring: "P3-B's hand-built model of the 2.4 GHz fixture ifa2g4 (Stage 3 design 5.11), written by hand from tools/make_fixtures.py's numbers and KiCad's Texas_SWRA117D_2.4GHz_Left footprint, its pads from tests/fixtures/ifa2g4.pads.json (pcbnew's own) and its vias from the board's text: its own mesh, MUR on all six faces at λ/2 at f_lo, a 50 Ω lumped port across U1.1–U1.2's gap, a Gaussian pulse, a frequency-domain far-field box over-sampled 4 times read with read_cached=False. It imports nothing of the product, and openEMS and CSXCAD only inside mesh() and run(), always in a process of its own: `python tools/p3b_hand.py --out DIR [--fine-mm MM] [--wall-mm MM]`, or `--mesh FILE` for the mesh lines alone."
  - **Geometry** (mm, y up: KiCad's y negated), each piece citing its line in `tools/make_fixtures.py` or the footprint:
    - the outline (87, 94)–(127, 124); the GND zones' rectangle (87.5, 99.75)–(126.5, 123.5);
    - AE1 at (100, 100): the 12 rectangles of r1 Q2, local (x0, x1, y0, y1): (−11.85, −11.35, −5.15, −0.71), (−11.35, −9.15, −5.15, −4.65), (−9.65, −9.15, −4.65, −2.01), (−9.65, −6.65, −2.51, −2.01), (−7.15, −6.65, −5.15, −2.51), (−7.15, −4.45, −5.15, −4.65), (−4.95, −4.45, −4.65, −2.01), (−4.95, −1.95, −2.51, −2.01), (−2.45, −1.95, −5.15, −2.51), (−2.45, 2.55, −5.15, −4.65), (−0.25, 0.25, −4.65, 0.25), (1.65, 2.55, −4.65, 0.25), on F.Cu (`antenna()`);
    - the feed: (100, 100)–(100, 110) 1.35 mm and (100, 110)–(100, 111.975) 0.6 mm, round caps (`LineString.buffer(w/2)`); the VDD track 0.25 mm from (100, 116.925) to C1.1's centre; the GND track 0.3 mm from C1.2's centre to the via at (103.68, 116.925);
    - every pad of pads.json on its layers (AE1.2, through-hole, on both); C1 bridged as copper, the convex hull of its two pads;
    - **F.Cu** = (the zone rectangle − the 1.0 mm round buffer of the RF and VDD copper: AE1.1, the feed, U1.1, U1.8, the VDD track, C1.1) ∪ every piece above; **B.Cu** = the zone rectangle ∪ AE1.2; `# ponytail: the fill rebuilt by its rule, not KiCad's min-thickness rounding (r1: ≤ 1 mm² on F.Cu)`.
    - `rods()`: every `(via (at x y)` of the board's text, by one regex (`\(via\s+\(at ([-\d.]+) ([-\d.]+)\)`), y negated, then AE1.2's plated hole at its pads.json centre: the fixture's one thru_hole pad, the IFA's short, whose barrel the product builds too (`core/geometry/vias.py`).
  - **Stackup:** B.Cu z 0–0.035, the core 0.035–0.745 at εr 4.5 and κ = 2π·F0·ε0·4.5·0.02, F.Cu 0.745–0.78; the mask as two boxes over the outline, z 0.78–0.88 and −0.1–0, at εh = (0.01·3.3 + (0.1 − 0.01))/0.1, its own formula.
  - **`port()`:** start `[99.03, -112.95, 0.745]` (U1.2's edge), stop `[99.7, -111.0, 0.78]` (U1.1's), direction x, 50 Ω.
  - **`mesh(fine_mm, wall_mm)`** (CSXCAD's `SmoothMeshLines`, imported here): the seeds of an in-plane axis are the bounds of every piece the copper is built from (each AE1 rectangle, pad, track, rod and C1's hull), of each RF or VDD piece grown by the 1.0 mm clearance, of the zone and of the outline, never the fill's arc vertices; merged within MERGE_MM in ascending order, the port's edges always kept. Those inside the antenna-and-feed box (x 88.15–102.55, KiCad y 94.85–112.95) are smoothed at `fine_mm` (RATIO); then all of them at BOARD_MM; then the walls at the outline ± `wall_mm`, smoothed at AIR_MM. z: 0, 0.035, 0.745, 0.78, the mask boxes' faces −0.1 and 0.88, and 4 equal cells across the core, smoothed at BOARD_MM, then the walls at −0.1 − `wall_mm` and 0.88 + `wall_mm`, smoothed at AIR_MM. Every line to 1e-6 mm.
  - **`run(out, fine_mm, wall_mm)`:** `openEMS(EndCriteria=END_CRITERIA)`, `SetMaxTime(T_END_S)`, `SetGaussExcite(*GAUSS)`, `SetBoundaryCond(["MUR"] * 6)`; the grid in mm; the core and the masks at priority 1, the copper at priority 10 as 35 µm `AddLinPoly` extrusions (a polygon with holes, the fill's VDD pocket, cut into hole-free pieces by a 1 µm slit through each hole, `# ponytail: 1 µm slits for the holes AddLinPoly takes none of, 200 times under the mesh's finest cell; CSXCAD's polygons with holes if a slit ever shows`), each rod a PEC curve from z 0 to 0.78 on its mesh lines (its x and y are seeds); `AddLumpedPort(1, 50, start, stop, "x", 1.0, priority=5)`; `CreateNF2FFBox("nf2ff", start=mesh line 3, stop=mesh line −4 on each axis, frequency=F11, over_sampling=4)`; `Run(out / "sim", numThreads=THREADS)`. Then `port.CalcPort` on GRID_HZ (S11 = uf_ref/uf_inc) and on F11 (P_acc = ½·Re(uf_tot·if_tot*)); `CalcNF2FF(sim, F11, θ 0:5:180, φ −180:5:180, center=[c * 1e-3 for c in CENTER], read_cached=False, outfile=f"hand-{secrets.token_hex(4)}.h5")` (metres, as `worker._far_field` passes it; D_max, P_rad); η_rad = P_rad/P_acc. Writes and returns `out / "hand.json"`: `{"f_hz", "s11": [[re, im]], "far": {"f_hz", "d_max", "p_rad", "p_acc", "eta_rad"}, "cells": [nx, ny, nz], "t_end": the port voltage's last sample time, "criterion_hit": t_end < 0.99·T_END_S, "decay_db": 20·log10(max |u| over the last 2 ns / max |u|), "fine_mm", "wall_mm", "wall_s", "versions": {"openems", "csxcad" (importlib.metadata), "python", "os"}, "script_sha256": script_sha()}`, no path.
  - **`script_sha()`:** the sha256 of this file's bytes with CRLF read as LF.
  - **`main(argv)`:** `--mesh FILE` writes `mesh()`'s lines as JSON (`{"x", "y", "z"}`) and returns 0; else `--out DIR [--fine-mm MM] [--wall-mm MM]` runs.
- [ ] **Step 4: Run them again.** Step 2's command (the openems test runs where CSXCAD imports, as on this PC). Expected: PASS. A missed XOR or mesh number is a prototype number: stop with both values.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add tools/p3b_hand.py tests/test_p3b.py
git commit -m "test(p3b): the hand-built openEMS model of the 2.4 GHz fixture, transcribed independently of the product (Stage 3 design 5.11)"
graphify update .
```

---

### Task 4 [code]: P3-B's gate

**Files:**
- Create: `tools/p3b.py`, `tests/fixtures/p3b/criteria.json`.
- Test: `tests/test_p3b.py`.

**Interfaces:**
- Consumes: Task 1's `p3.*` and `test_p3.gates`; Task 3's `p3b_hand.copper`, `port`, `rods`, `script_sha`, `F11`, `F_LO`, `F_HI`, `FINE_MM`, `WALL_MM`; `pipeline.load`, `build_model`; `p3a._cell`.
- Produces: `CRITERIA`, `REFERENCES = p0.FIX / "p3b" / "references.json"`, `PRODUCT = "ifa2g4-solid-n2"`, `STEPS = ("geometry", "hand", "hand-f1", "product", "product-mur", "hand-030")`; `geometry(pj: Path) -> dict`; `hand(out: Path, name: str = "hand", fine_mm: float = p3b_hand.FINE_MM, wall_mm: float = p3b_hand.WALL_MM) -> dict`; `references() -> dict`; `measure(out: Path) -> dict`; `decide(m: dict) -> dict`; `tables(result: dict) -> str`; `write(out: Path) -> dict`; `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: The criteria,** `tests/fixtures/p3b/criteria.json`:

```json
{"source": "Stage 3 design 5.11, gate P3-B; plan 4 ruling 1 (r1): f_res is the refined lowest |S11| over the simulated band on each side, the hand's interpolated onto the product's grid; a miss on an unconditioned minimum (not both inside the grid at or below -6 dB) is explained when max |dS11| over [f_lo, f_hi] is within its shift-equivalent, the largest |dS11| that shifting the hand's S11 by f_res_rel makes there (the controller's amendment at commit); D at f0 and eta_rad at every recorded frequency stay binding; the hand run is valid when it hit its end criterion or its last 2 ns sit decay_db or more under its peak, and the product's job converged; a fail is diagnosed by the first of diagnoses whose two runs pass f_res, D and eta, else a product bug is presumed; a hand-f1 run that is not valid either stops for a ruling",
 "f_res_rel": 0.01, "d_db": 0.3, "eta_db": 0.3, "conditioned_db": -6.0, "decay_db": 40.0,
 "xor_f_cu_mm2": 1.0, "xor_b_cu_mm2": 0.2,
 "diagnoses": [["boundary", "hand", "product-mur"], ["mesh", "hand-030", "product"],
               ["boundary and mesh", "hand-030", "product-mur"]]}
```

- [ ] **Step 2: Write the failing tests,** in `tests/test_p3b.py` (its imports gain these):

```python
import numpy as np

import p3b
from kicad_rf_studio.core.project import save_project
from test_p3 import gates  # noqa: F401 (the fixture)

F = np.linspace(2.3e9, 2.5e9, 201)


def side(f_res=2.4e9, depth=-12.0, d=2.57, eta=0.81, verdict="converged"):  # a measure: a dip of `depth` dB at f_res
    s11 = 10 ** ((depth + 8 * ((F - f_res) / 50e6) ** 2) / 20) + 0j  # a parabola in dB: resonance() finds f_res
    return {"f_hz": F, "s11": s11, "band": [2.4e9, 2.4835e9], "d_dbi": d, "far_f_hz": [2.44175e9] * 11,
            "eta_rad": [eta] * 11, "jobs": [{"verdict": verdict}]}


def shallow(tilt_db=0.0, scale=1.0, tau=1.7e-9):  # a broad -5.9 dB minimum at 2.4 GHz (the fixture's, first run),
    f = F / scale  # tilted per 100 MHz, its frequency axis scaled, its phase turning over tau s (the first run's)
    x = (f - 2.4e9) / 100e6
    return {**side(), "s11": 10 ** ((-5.9 + 0.5 * x ** 2 + tilt_db * x) / 20) * np.exp(-2j * np.pi * f * tau)}


def m(hand=None, product=None, hit=True, decay=-45.0, xor=(0.5, 0.05), **diagnostics):
    return {"hand": {**(hand or side()), "criterion_hit": hit, "decay_db": decay}, "product": product or side(),
            "geometry": {"xor_mm2": {"F.Cu": xor[0], "B.Cu": xor[1]}}, **diagnostics}


def test_the_p3b_rules_inclusive_signed_and_conditioned():  # design 5.11; ruling 1; RF 3, 4
    assert p3b.decide(m())["verdict"] == {"value": "pass", "fails": [], "diagnosis": None}
    for change, fails in [({"product": side(f_res=2.4239e9)}, []), ({"product": side(f_res=2.4241e9)}, ["f_res"]),
                          ({"product": side(f_res=2.3761e9)}, []), ({"product": side(f_res=2.3759e9)}, ["f_res"]),
                          ({"product": side(d=2.272)}, []), ({"product": side(d=2.268)}, ["d"]),
                          ({"product": side(d=2.868)}, []), ({"product": side(d=None)}, ["d"]),
                          ({"product": side(eta=0.81 * 10 ** -0.0298)}, []),
                          ({"product": side(eta=0.81 * 10 ** -0.0302)}, ["eta"]),
                          ({"hit": False, "decay": -40.0}, []), ({"hit": False, "decay": -39.9}, ["valid"]),
                          ({"hit": False, "decay": 45.0}, ["valid"]),  # a grown run is no reference: signed
                          ({"product": side(verdict="t_max")}, ["valid"]),  # nor a product run cut at T_max
                          ({"xor": (1.01, 0.05)}, ["geometry"]), ({"xor": (0.99, 0.21)}, ["geometry"])]:
        assert p3b.decide(m(**change))["verdict"]["fails"] == fails
    explained = p3b.decide(m(hand=shallow(), product=shallow(-0.6)))  # the argmin 60 MHz away, |dS11| about 0.03
    e = explained["f_res"]  # a 1 % shift of the hand's S11 moves it by about 0.14 in band (the first run's slope)
    assert e["conditioned"] is False and e["ds11"] < 0.05 < 0.1 < e["ds11_shift"] < 0.2
    assert explained["verdict"] == {"value": "explained", "fails": [], "diagnosis": None}
    moved = p3b.decide(m(hand=shallow(), product=shallow(-5.0)))  # |dS11| about 0.20 in band: more than a 1 % shift
    assert moved["f_res"]["ds11"] > moved["f_res"]["ds11_shift"] and moved["verdict"]["fails"] == ["f_res"]
    turned = p3b.decide(m(hand=shallow(), product=shallow(scale=1.015)))  # a real 1.5 % shift
    assert turned["f_res"]["ds11"] > turned["f_res"]["ds11_shift"] and turned["verdict"]["fails"] == ["f_res"]
    edge = p3b.decide(m(product=side(f_res=2.52e9)))  # the product's lowest |S11| at the grid's end: no dip
    assert edge["f_res"]["conditioned"] is False and edge["verdict"]["fails"] == ["f_res"]


def test_a_p3b_fail_is_diagnosed_by_the_pre_registered_pairs():  # design 5.11: blocks until explained
    miss = m(product=side(f_res=2.43e9))  # a conditioned 1.25 % miss
    assert p3b.decide(miss)["verdict"] == {"value": "fail", "fails": ["f_res"], "diagnosis": None}  # none run yet
    assert p3b.decide({**miss, "product-mur": side(f_res=2.405e9)})["verdict"]["diagnosis"] == "boundary"
    assert p3b.decide({**miss, "product-mur": side(f_res=2.43e9), "hand-030": side(f_res=2.428e9)})[
        "verdict"]["diagnosis"] == "mesh"
    both = {**miss, "product-mur": side(f_res=2.43e9), "hand-030": side(f_res=2.4e9)}
    assert p3b.decide(both)["verdict"]["diagnosis"] == "product bug presumed"


def test_the_reference_is_refused_once_the_hand_model_changed(tmp_path, monkeypatch):  # design 5.11; ruling 7
    path = tmp_path / "references.json"
    monkeypatch.setattr(p3b, "REFERENCES", path)
    with pytest.raises(SystemExit):
        p3b.references()  # none committed yet: the product's side may not run
    path.write_text(json.dumps({"script_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(SystemExit):
        p3b.references()


def test_a_hand_run_is_kept_by_the_hand_modules_hash_alone(tmp_path, monkeypatch):  # RF 2; r1: not by the code's id
    p0.save(tmp_path / "p3b" / "hand" / "hand.json", {"script_sha256": p3b_hand.script_sha(), "wall_s": 1.0})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("a kept hand run ran again"))
    assert p3b.hand(tmp_path)["wall_s"] == 1.0


def test_the_hand_copper_matches_the_products_model(tmp_path):  # r1 Q2: the free pre-check, no openEMS
    pj = antenna_project(tmp_path)
    save_project(pj, {**load_project(pj), "copper": "solid"})  # P3-B's product side is solid copper (PRODUCT)
    g = p3b.geometry(pj)
    assert g["xor_mm2"]["F.Cu"] <= 1.0 and g["xor_mm2"]["B.Cu"] <= 0.2
    assert g["port"]["hand"] == [[99.03, -112.95, 0.745], [99.7, -111.0, 0.78]]
    assert g["port"]["product"] == [[98.98, -112.89812, 0.745], [99.787503, -111.07688, 0.78]]  # r1's probe


def test_p3b_runs_its_product_step_and_writes(gates, monkeypatch, tmp_path):  # design 5.11; the harness on the fake
    f = np.arange(1840, 2991) * 1e6
    monkeypatch.setattr(p3b, "REFERENCES", tmp_path / "references.json")
    p0.save(p3b.REFERENCES, {"script_sha256": p3b_hand.script_sha(), "f_hz": f.tolist(), "s11": [[0.5, 0.0]] * len(f),
                             "far": {"f_hz": [2.45e9, 2.4e9], "d_max": [1.8, 1.8], "p_rad": [1.0, 1.0],
                                     "p_acc": [1.25, 1.25], "eta_rad": [0.8, 0.8]},
                             "criterion_hit": True, "decay_db": -45.0, "cells": [1, 1, 1], "t_end": 1e-8, "wall_s": 1.0})
    assert p3b.main(["--out", str(gates), "--steps", "geometry,product"]) == 0
    assert p3b.main(["--out", str(gates)]) == 0
    text = (gates / "p3b" / "p3b.json").read_text(encoding="utf-8")
    assert '"s11"' not in text and '"f_hz"' not in text and json.loads(text)["decisions"]["verdict"]["value"]
    assert (gates / "p3b" / "p3b.md").read_text(encoding="utf-8").startswith("## P3B-1")
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_p3b.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p3b'`.
- [ ] **Step 4: `tools/p3b.py`.** Module docstring: "P3-B, the pipeline against a hand-built model (Stage 3 design 5.11): the free geometry pre-check, the hand runs in their own process, the product's run (shared with P3-C as ifa2g4-solid-n2), the pre-registered checks and diagnoses of tests/fixtures/p3b/criteria.json against the committed tests/fixtures/p3b/references.json, and p3b.json and p3b.md in <out>/p3b. Run: python tools/p3b.py --out DIR [--steps ...]."
  - **`geometry(pj)`:** the product's model built in memory (`pipeline.load`, `build_model`), its copper solids unioned per layer by their z range (F.Cu (0.745, 0.78), B.Cu (0.0, 0.035)); `{"xor_mm2": {layer: area of the symmetric difference with p3b_hand.copper()[layer]}, "port": {"hand": list(p3b_hand.port()), "product": [P1's start, stop]}}`.
  - **`hand(out, name, fine_mm, wall_mm)`:** `<out>/p3b/<name>/hand.json` as it is when it holds `p3b_hand.script_sha()`: a hand run is keyed by the hand module alone, never by the product's code (r1), so it sits outside `p0.step`; else runs `[sys.executable, "-X", "utf8", str(<tools/p3b_hand.py>), "--out", str(<that folder>), "--fine-mm", str(fine_mm), "--wall-mm", str(wall_mm)]` with this process's environment, its output to `<out>/p3b/<name>.log`; RuntimeError on a non-zero exit; returns the hand.json it wrote. The harness never imports openEMS.
  - **`references()`:** REFERENCES' JSON; SystemExit "P3-B's reference is committed after the hand run and never regenerated: run the hand step and commit it first" when missing, or "the hand model changed after its reference" when its `script_sha256` is not `p3b_hand.script_sha()`.
  - **Steps** (main's `--steps`): `geometry` → `p0.step(out, "p3b-geometry", f"{p3b_hand.script_sha()}|{p0.model_key(pj)}", lambda: geometry(pj))`, `pj = p3.variant(out, PRODUCT, "ifa2g4", {"copper": "solid"})`; `hand` → `hand(out)`; `hand-f1`, the one rerun r1 R2 allows when the hand run neither hit its criterion nor decayed 40 dB → `hand(out, "hand-f1", wall_mm=round(299792458 / 1.84e9 / 2 * 1e3, 6))` (λ/2 at f1, 81.465 mm); `product` → `references()` first, then that variant and `p3.run_step(out, PRODUCT)`; the diagnostics, run only on a fail: `product-mur` (the project `ifa2g4-solid-mur`, `{"copper": "solid", "boundary": "mur", "air_gap_mm": 62.456762}`, the project P3-C's MUR step runs when solid copper wins) and `hand-030` (`hand(out, "hand-030", 0.3)`).
  - **`measure(out)`:** `{"hand": the reference as a measure, "product": p3.measure(out, PRODUCT), "geometry": the geometry step's result (None without one)}`, plus `"product-mur"` (`p3.measure`) and `"hand-030"`, `"hand-f1"` (their hand.json as measures) when recorded. A hand run as a measure: its S11 interpolated in its real and imaginary parts onto the product's grid (its own without one), `"band"` [F_LO, F_HI], `"d_dbi"` (10·log10 of D_max at f0, the first), `"far_f_hz"`, `"eta_rad"`, and its `"criterion_hit"`, `"decay_db"`, `"cells"`, `"t_end"`, `"wall_s"`.
  - **`decide(m)`:** each limit inclusive, None a fail, in this order: `f_res` = `p3.pair(hand, product, f_res_rel, conditioned_db)`; `d` (its d_db ≤ `d_db`); `eta` (its eta_db ≤ `eta_db`); `valid` (the hand hit its criterion or its `decay_db` ≤ −`decay_db`, signed, and the product's job verdict is "converged"); `geometry` (both XORs within their limits). Returns `{"f_res": the pair with "pass", "d", "eta", "valid", "geometry": {"value", "pass"}, "verdict": {"value": "pass" | "explained" | "fail", "fails": [...], "diagnosis"}}`: "explained" when the only miss is an explained f_res; on a fail, "diagnosis" names the first entry of `diagnoses` whose two runs are recorded and pass f_res (explained counts), D and η by `p3.pair`, "product bug presumed" when every entry's runs are recorded and none passes, else None.
  - **`tables`** and **`write`** as `p3a`'s, cells by `p3a._cell`: P3B-1 the checks with limit, value and pass (f_res with its conditioning, |ΔS11| and its 1 % shift-equivalent `ds11_shift`), the verdict and the diagnosis; P3B-2 the runs (cells, t_end or verdict, D, η_rad range, f_res, depth, wall_s, predicted_s and worst_s: the product's by `p3.predicted_s`, the hand's r1 estimate of 27 min); P3B-3 the port boxes, the XORs and the hand's rods; `<out>/p3b/p3b.json` through `p0.save` (`versions`, `criteria`, the reference's scalars without `f_hz`, `s11` and `far`, `calibration` from `p3.calibration()`, the measurements without `f_hz` and `s11`, `decisions`, `machine` from `p0.machine` of `p3.records` over the product steps, and the hand runs' wall_s) and `p3b.md`.
  - **`main`:** `p3.enter`, then `--steps` through `p3.run_steps`; with no `--steps`, `write`. Returns 1 when a step raised.
- [ ] **Step 5: Run them again.** Step 3's command. Expected: PASS. The product's port box is r1's probe (the reviser's too): a miss stops the task.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/p3b.py tests/test_p3b.py tests/fixtures/p3b/criteria.json
git commit -m "test(p3b): gate P3-B's steps, pre-registered criteria, checks and diagnoses, the f_res conditioning rule and the free geometry pre-check (Stage 3 design 5.11)"
graphify update .
```

---

### Task 5 [code]: P3-C's steps

**Files:**
- Create: `tools/p3c.py`, `tests/fixtures/p3c/criteria.json`, `tests/test_p3c.py`.

**Interfaces:**
- Consumes: Task 1's `p3.*` and `test_p3.gates`; `core.project.load_project`.
- Produces: `CRITERIA`; `FIXTURES = ("ifa2g4", "meander915")`; `COPPERS = ("solid", "sheet")`; `SETTINGS = ("n2", "n3", "n4", "gap2", "strict")`; `RAISED: dict[str, dict] = {"ifa2g4": {}, "meander915": {}}`; `edits(name: str, base: dict) -> dict`; `names() -> list[str]`; `run(out: Path, name: str) -> None`; `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: The criteria,** `tests/fixtures/p3c/criteria.json`:

```json
{"source": "Stage 3 design 5.4, 5.9 and 5.11, gate P3-C; plan 4 rulings (r2, r4): f_res the refined lowest |S11|, conditioned when every compared minimum lies inside the grid at or below -6 dB; an unconditioned f_res miss is explained when max |dS11| over [f_lo, f_hi] is within its shift-equivalent, the largest |dS11| that shifting the reference's S11 by the check's limit makes there (the controller's amendment at commit), the mesh check's against the S11 extrapolated pointwise; eta is eta_rad at the worst of the 11 recorded frequencies, D at f0; n 2 judged against the f_res extrapolated at the observed order capped at 1, two meshes at the 2.4 GHz fixture's; a comparison that reads a run not converged is not judged; the PML free run to max(T_max, free_factor x the n 2 job's stop time); ifa2g4's MUR free run to free_factor x T_max; the meander's MUR at lambda/2, run only when its PML fails, to its PML free run's length; each free run judged as P3-A judges growth; T_max raised to the residual's decay over t_max_fit_s projected to the preset's level x t_max_margin, rounded up to a whole ns; the flat window widened to flat_periods_widened periods of f0; the refit keeps the PML weight unless it moves by more than refit_w_band",
 "conditioned_db": -6.0, "mesh_f_res_rel": 0.01,
 "gap_f_res_rel": 0.002, "gap_d_db": 0.2, "gap_eta_db": 0.1, "preset_f_res_rel": 0.001, "preset_eta_db": 0.05,
 "sheet_f_res_rel": 0.005, "sheet_eta_db": 0.1, "free_factor": 3, "free_reach": 0.99, "growth_db_max": 6.0,
 "fit2d_raised": 0.05, "t_max_margin": 1.5, "t_max_fit_s": 20e-9, "flat_periods_widened": 40, "refit_w_band": 0.25}
```

- [ ] **Step 2: Write the failing tests,** `tests/test_p3c.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import numpy as np
import pytest

import p3
import p3c
from kicad_rf_studio.core.project import load_project
from test_p3 import gates  # noqa: F401 (the fixture)


@pytest.fixture(autouse=True)
def nothing_raised(monkeypatch):  # the gates' own RAISED, set at a checkpoint, never reaches a test
    monkeypatch.setattr(p3c, "RAISED", {"ifa2g4": {}, "meander915": {}})


def test_the_variants_edits(monkeypatch):  # rulings 2, 3; r2 Q3; RAISED per fixture
    base = {"air_gap_mm": 31.228381, "mesh": {"n": 2}, "preset": "normal", "t_max_s": 3e-8}
    assert p3c.edits("ifa2g4-sheet-n3", base) == {"copper": "sheet", "mesh.n": 3, "gates.fit2d_limit": 0.05}
    assert p3c.edits("meander915-solid-n4", base) == {"copper": "solid", "mesh.n": 4}  # passes fit2d at every n
    assert p3c.edits("ifa2g4-solid-gap2", base) == {"copper": "solid", "air_gap_mm": 62.456762}
    assert p3c.edits("ifa2g4-solid-strict", base) == {"copper": "solid", "preset": "strict"}  # mesh.n stays 2
    assert p3c.edits("ifa2g4-solid-mur", base) == {"copper": "solid", "boundary": "mur", "air_gap_mm": 62.456762}
    monkeypatch.setattr(p3c, "RAISED", {"ifa2g4": {}, "meander915": {"t_max_s": 1.2e-7, "flat_s": 4.4e-8}})
    assert p3c.edits("meander915-sheet-gap2", base) == {"copper": "sheet", "air_gap_mm": 62.456762,
                                                         "t_max_s": 1.2e-7, "flat_s": 4.4e-8}


def test_p3c_runs_its_steps_through_the_product(gates):  # design 5.11; ruling 4
    assert p3c.main(["--out", str(gates), "--steps", "ifa2g4-solid-n2,ifa2g4-solid-strict,ifa2g4-solid-free"]) == 0
    n2, free = p3.measure(gates, "ifa2g4-solid-n2"), p3.measure(gates, "ifa2g4-solid-n2", "free")
    assert free["t_max"] == max(30e-9, 3 * max(j["t_stop"] for j in n2["jobs"]))
    strict = load_project(p3.project_path(gates, "ifa2g4-solid-strict"))
    assert (strict["preset"], strict["mesh"]["n"], strict["copper"]) == ("strict", 2, "solid")
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_p3c.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p3c'`.
- [ ] **Step 4: `tools/p3c.py`.** Module docstring: "P3-C, convergence and defaults (Stage 3 design 5.11) on both fixtures: mesh n 2/3/4, the air gap λ/4 against λ/2, Normal against Strict, a free run to 3 × the stop time, solid against all-sheet copper, and MUR at λ/2 as report-only evidence; each variant a project edit run through the product, each delta computed in-process (compare refuses different settings); p3c.json and p3c.md in <out>/p3c, written from whatever steps are recorded. Run: python tools/p3c.py --out DIR [--steps ...]."
  - **Names:** `f"{fixture}-{copper}-{setting}"` for each of SETTINGS, plus `mur` on both fixtures (the meander's run only when its PML fails, Task 10); free steps `f"{fixture}-{copper}-free"` (on the n2 project) and `f"{fixture}-{copper}-murfree"` (on the mur project). `names()` lists them fixture by fixture, copper by copper.
  - **`edits(name, base)`:** `{"copper": copper}` plus: n3/n4 `"mesh.n"`, with `"gates.fit2d_limit": CRITERIA["fit2d_raised"]` on ifa2g4 (ruling 2); gap2 `"air_gap_mm": round(2 * base["air_gap_mm"], 6)`; strict `"preset": "strict"` alone (the copy keeps n 2: `new --preset strict` would write n 3); mur `"boundary": "mur"` and the λ/2 gap; then `RAISED[fixture]`'s edits (`"t_max_s"`, `"flat_s"`), set only at a checkpoint (Task 10).
  - **`run(out, name)`:** a free name: `p3.free_step(out, <its project>, t_free)`, t_free for `free` max(project t_max_s, `free_factor` × the n2 step's longest kept t_stop), for ifa2g4's `murfree` `free_factor` × the mur project's t_max_s (P3-A's 3 × T_max window, where its MUR twin rose 16 dB), for the meander's `murfree` as its `free`; RuntimeError "run <its project> first" when the step it reads has no record. Else `p3.variant(out, name, fixture, edits(name, load_project(p3.base(out, fixture))))` then `p3.run_step(out, name)`.
  - **`main`:** `p3.enter`, then `--steps` (required here; Task 6 makes it optional) through `p3.run_steps(names, partial(run, out))`. Returns its code.
- [ ] **Step 5: Run them again.** Step 3's command. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/p3c.py tests/test_p3c.py tests/fixtures/p3c/criteria.json
git commit -m "test(p3c): gate P3-C's variants, edits and free runs through the product, with its pre-registered criteria (Stage 3 design 5.11)"
graphify update .
```

---

### Task 6 [code]: P3-C's rules and report

**Files:**
- Modify: `tools/p3c.py`, `tests/test_p3c.py`.

**Interfaces:**
- Consumes: Task 5's `p3c`; `p3.pair`, `p3.records`, `p3.measure`, `p3.calibration`; `p3a._cell`; `pipeline.load`; `core.mesh.gates.fit2d`, `mesh_with_lint`; `core.model.ports.ends`, `nominal_boxes`; `core.project.mesh_n`; `stoprule.PRESETS`.
- Produces: `extrapolated(fs: list[float], p: float | None = None) -> tuple[float, str, float | None]`; `projected_stop(run_dir: Path, level_db: float, window_s: float) -> float | None`; `fit2d_probe(pj: Path) -> list[dict]`; `decide(m: dict[str, dict | None]) -> dict`; `edits_2g4(decisions: dict, gap_mm: float) -> dict`; `tables(result: dict) -> str`; `write(out: Path) -> dict`; `main` with no `--steps` writes.

- [ ] **Step 1: Write the failing tests,** in `tests/test_p3c.py`:

```python
F = np.linspace(2.3e9, 2.5e9, 201)


def run(f_res=2.4e9, depth=-12.0, d=2.57, eta=0.81, verdict="converged"):
    s11 = 10 ** ((depth + 8 * ((F - f_res) / 50e6) ** 2) / 20) + 0j
    return {"f_hz": F, "s11": s11, "band": [2.4e9, 2.4835e9], "d_dbi": d, "far_f_hz": [2.44175e9] * 11,
            "eta_rad": [eta] * 11, "jobs": [{"verdict": verdict, "t_stop": 9.85e-9}]}


def shallow(tilt_db=0.0):  # a broad -5.9 dB minimum at 2.4 GHz (the fixture's, first run), tilted per 100 MHz,
    x = (F - 2.4e9) / 100e6  # its phase turning as the first run's (a 1 % shift moves S11 by about 0.14 in band)
    return {**run(), "s11": 10 ** ((-5.9 + 0.5 * x ** 2 + tilt_db * x) / 20) * np.exp(-2j * np.pi * F * 1.7e-9)}


def free(growth=0.1, t_stop=30e-9, finite=True):
    return {"growth_db": growth, "t_max": 30e-9, "t_stop": t_stop, "finite": finite}


def full(**over):  # every step of both fixtures, every default kept, sheet winning
    m = {}
    for fx in p3c.FIXTURES:
        for cu in p3c.COPPERS:
            m |= {f"{fx}-{cu}-{s}": run(f_res=2.4e9 * (1 + {"n2": 0, "n3": -0.001, "n4": -0.0015}.get(s, 0)))
                  for s in p3c.SETTINGS}
            m[f"{fx}-{cu}-free"] = free()
            if fx == "ifa2g4":
                m[f"ifa2g4-{cu}-mur"], m[f"ifa2g4-{cu}-murfree"] = run(), free(growth=16.0)  # P3-A's twin rose 16 dB
    return m | over


def test_the_extrapolation_takes_the_observed_order_capped_at_1():  # r2 Q3: order 1 is conservative only at p ≥ 1
    def f(n, p, f_inf=2.4e9, c=0.02):
        return f_inf * (1 + c / n ** p)
    assert p3c.extrapolated([f(n, 1) for n in (2, 3, 4)])[:2] == (pytest.approx(2.4e9), "monotone")
    assert p3c.extrapolated([f(n, 1) for n in (2, 3)]) == (pytest.approx(2.4e9), "two meshes", None)
    assert p3c.extrapolated([f(n, 0.5) for n in (2, 3, 4)]) == (
        pytest.approx(2.4e9), "monotone", pytest.approx(0.5, abs=1e-3))  # p < 1: the larger correction
    assert p3c.extrapolated([f(n, 0.5) for n in (2, 3)], p=0.5)[0] == pytest.approx(2.4e9)  # the 2.4 GHz fixture's order
    assert p3c.extrapolated([f(n, 2) for n in (2, 3, 4)])[0] == pytest.approx(f(4, 2) + 3 * (f(4, 2) - f(3, 2)))  # 1 binds
    assert p3c.extrapolated([2.400e9, 2.401e9, 2.403e9])[1] == "not converging"
    assert p3c.extrapolated([2.40e9, 2.39e9, 2.395e9]) == (2.395e9, "oscillating", None)


def test_the_p3c_rules_keep_every_default_on_good_runs():  # design 5.11
    d = p3c.decide(full())
    assert d["decisions"] == {"copper": "sheet", "mesh_n": 2, "gap_factor": 1, "preset": "normal",
                              "boundary": "pml_8", "t_max": "kept", "flat": "kept"}
    assert d["checks"]["mur"]["ifa2g4"]["report_only"] and d["verdict"] == {"value": "pass", "fails": []}
    mesh = d["checks"]["mesh"]["ifa2g4"]
    assert (mesh["kind"], mesh["p"], mesh["value"]) == ("monotone", pytest.approx(1.0, abs=1e-3), pytest.approx(0.003, abs=1e-4))


def test_each_failed_check_raises_its_default():  # design 5.11's fallbacks; RF 3
    late = full(**{f"ifa2g4-{cu}-n2": run(f_res=2.43e9) for cu in p3c.COPPERS})  # 1.6 % off the extrapolation
    assert p3c.decide(late)["decisions"]["mesh_n"] == 3
    assert p3c.decide(full(**{"meander915-sheet-gap2": run(d=2.36)}))["decisions"]["gap_factor"] == 2  # ΔD 0.21 dB
    assert p3c.decide(full(**{"meander915-sheet-gap2": run(d=2.38)}))["decisions"]["gap_factor"] == 1  # 0.19 dB
    assert p3c.decide(full(**{"meander915-sheet-gap2": run(f_res=2.3951e9)}))["decisions"]["gap_factor"] == 2  # -0.204 %
    assert p3c.decide(full(**{"ifa2g4-sheet-strict": run(eta=0.81 * 10 ** -0.006)}))["decisions"]["preset"] == "strict"
    assert p3c.decide(full(**{"meander915-sheet-n2": run(f_res=2.4121e9)}))["decisions"]["copper"] == "solid"  # 0.504 %
    assert p3c.decide(full(**{"meander915-sheet-n2": run(f_res=2.3881e9)}))["decisions"]["copper"] == "sheet"  # -0.496 %
    grew = p3c.decide(full(**{"ifa2g4-sheet-free": free(growth=6.1)}))
    assert grew["checks"]["pml"]["pass"] is False and grew["verdict"]["value"] == "blocked"  # MUR's own run grew too
    assert p3c.decide(full(**{"ifa2g4-sheet-free": free(growth=6.1), "ifa2g4-sheet-murfree": free()}))[
        "decisions"]["boundary"] == "mur"
    meander = {"meander915-sheet-free": free(growth=6.1), "ifa2g4-sheet-murfree": free()}
    assert p3c.decide(full(**meander))["verdict"]["value"] == "incomplete"  # the meander's own MUR run is needed
    assert p3c.decide(full(**meander, **{"meander915-sheet-mur": run(), "meander915-sheet-murfree": free()}))[
        "decisions"]["boundary"] == "mur"


def test_an_unconditioned_miss_within_its_shift_equivalent_is_explained():  # ruling 1, amended at commit
    d = p3c.decide(full(**{f"ifa2g4-{cu}-{s}": shallow() if s in ("n3", "n4") else shallow(-0.6)
                           for cu in p3c.COPPERS for s in p3c.SETTINGS}))
    mesh = d["checks"]["mesh"]["ifa2g4"]
    assert (mesh["pass"], mesh["explained"], mesh["kind"]) == (False, True, "oscillating")
    assert mesh["ds11"] < 0.05 < 0.1 < mesh["ds11_shift"]  # |dS11| about 0.03 against a 1 % shift's 0.14
    assert d["decisions"]["copper"] == "sheet" and d["decisions"]["mesh_n"] == 2
    copper = p3c.decide(full(**{"meander915-solid-n2": shallow(), "meander915-sheet-n2": shallow(-2.0)}))
    c = copper["checks"]["copper"]["meander915"]  # |dS11| about 0.09 against a 0.5 % shift's 0.07
    assert c["explained"] is False and c["ds11"] > c["ds11_shift"] and copper["decisions"]["copper"] == "solid"
    near = p3c.decide(full(**{"meander915-solid-n2": shallow(), "meander915-sheet-n2": shallow(-0.6)}))
    assert near["checks"]["copper"]["meander915"]["explained"] is True and near["decisions"]["copper"] == "sheet"


def test_a_run_at_t_max_or_flat_is_no_converged_comparison():  # RF 4; design 5.4
    d = p3c.decide(full(**{"meander915-sheet-n2": run(verdict="t_max")}))
    assert d["checks"]["copper"]["meander915"]["pass"] is None and d["checks"]["converged"]["pass"] is False
    assert d["decisions"]["t_max"] == "raised" and d["verdict"]["value"] == "incomplete"
    flat = p3c.decide(full(**{"ifa2g4-sheet-gap2": run(verdict="flat")}))
    assert flat["checks"]["gap"]["ifa2g4"]["pass"] is None and flat["decisions"]["flat"] == "widened"
    assert flat["verdict"]["value"] == "incomplete"


def test_a_raised_t_max_stays_a_decision_after_its_rerun(monkeypatch):  # design 5.4
    monkeypatch.setattr(p3c, "RAISED", {"ifa2g4": {}, "meander915": {"t_max_s": 1.2e-7}})
    d = p3c.decide(full())
    assert d["decisions"]["t_max"] == "raised" and d["verdict"] == {"value": "defaults raised", "fails": ["t_max"]}


def test_a_missing_step_is_not_run_never_a_pass():
    d = p3c.decide({"ifa2g4-solid-n2": run()})  # decide reads m.get(name)
    assert d["checks"]["copper"]["ifa2g4"]["pass"] is None and d["verdict"]["value"] == "incomplete"


def test_the_2g4_edits_p3d_applies():  # ruling 2; P3-D and P3-E take P3-C's defaults
    assert p3c.edits_2g4({"copper": "sheet", "mesh_n": 3, "gap_factor": 2, "preset": "normal", "boundary": "pml_8"},
                         31.228381) == {"copper": "sheet", "mesh.n": 3, "gates.fit2d_limit": 0.05,
                                        "air_gap_mm": 62.456762}


def test_the_projected_stop_from_the_residuals_decay(tmp_path):  # ruling 9: T_max raised from the decay
    events = [{"kind": "progress", "code": "I_PROGRESS", "job": 1,
               "params": {"t_ns": f"{t:.2f}", "residual_db": f"{-0.5 * t:.1f}"}} for t in range(40, 80)]
    (tmp_path / "events.jsonl").write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
    assert p3c.projected_stop(tmp_path, -60.0, 20e-9) == pytest.approx(120e-9, rel=1e-3)  # -0.5 dB/ns from -39.5 dB
    flat = [{**e, "params": {**e["params"], "residual_db": "-30.0"}} for e in events]
    (tmp_path / "events.jsonl").write_text("\n".join(map(json.dumps, flat)), encoding="utf-8")
    assert p3c.projected_stop(tmp_path, -60.0, 20e-9) is None


def test_p3c_writes_its_report_from_the_recorded_steps(gates):  # design 5.11; RF 2
    assert p3c.main(["--out", str(gates), "--steps", "ifa2g4-solid-n2,ifa2g4-solid-strict"]) == 0
    assert p3c.main(["--out", str(gates)]) == 0
    text = (gates / "p3c" / "p3c.json").read_text(encoding="utf-8")
    result = json.loads(text)
    assert result["verdict"]["value"] == "incomplete" and isinstance(result["checks"]["preset"]["ifa2g4"]["value"], float)
    assert '"s11"' not in text and '"f_hz"' not in text
    assert (gates / "p3c" / "p3c.md").read_text(encoding="utf-8").startswith("## P3C-1")
```

  The architect's probe of fit2d at the default 3 % limit (in memory): ifa2g4 solid n 3 E_FIT2D_FINE 4.13 %, n 4 4.76 %; sheet n 3 3.87 %, n 4 4.76 %; meander915 passes at n 3 and 4 in both coppers. The reviser's, per section on ifa2g4 solid: n 2 0.99 % (0.6 mm) and 0.31 % (1.35 mm), n 3 4.13 % and 0.75 %.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_p3c.py -q`. Expected: FAIL (`module 'p3c' has no attribute 'extrapolated'`, `main` refuses no `--steps`).
- [ ] **Step 3: `tools/p3c.py`.**
  - **`extrapolated(fs, p=None)`:** f_res at n 2, 3 (and 4), h ∝ 1/n. Three meshes: steps d1 = f3 − f2, d2 = f4 − f3; a sign change or a zero step gives `(f4, "oscillating", None)`, judged by max(|f2 − f4|, |f3 − f4|); else R = d1/d2 and R(p) = (2^−p − 3^−p)/(3^−p − 4^−p): R ≤ R(0) = ln(3/2)/ln(4/3) is `(f4, "not converging", None)`; else the observed p solves R(p) = R by bisection on (0, 16], and the order used is min(p, 1) (1 exactly when R ≥ 2): `f4 + d2 / ((4/3) ** order − 1)`, `"monotone"`, p. Two meshes: order min(p, 1) with `p` given (the 2.4 GHz fixture's observed order), else 1: `f3 + (f3 − f2) / (1.5 ** order − 1)`, `"two meshes"`, None. Comment `# order 1 is the conservative end only at p ≥ 1 (R ≥ 2); at 0 < p < 1 the observed order gives the larger correction (r2, Celik 2008); the two-mesh branch assumes the 2.4 GHz fixture's order`.
  - **`projected_stop(run_dir, level_db, window_s)`:** job 1's I_PROGRESS events in events.jsonl over the last `window_s` of simulated time, their finite residuals, a least-squares line of residual_db against t; where it meets `level_db`, in s; None when it does not fall. `# ponytail: a straight line in dB; a beating residual projects wrongly, and a None or beating projection stops for a ruling`.
  - **`fit2d_probe(pj)`:** every section's `{"net", "width", "err"}` from `fit2d(geom, mesh)` on the project's own mesh (`mesh_with_lint(geom, replace(geom.protected, boxes=nominal_boxes(ends(board, project, geom.pieces))), mesh_n(project))`, as `build_model` makes it): ruling 2's record, RF's 0.6 mm section within 5 % and the 1.35 mm section within 3 %.
  - **`decide(m)`:** `m` maps each name to its `p3.measure` (or `"free"` measure), read with `m.get(name)`. A check is `{"pass": None, "why": "missing" | "not converged"}` when a step it reads is missing or a compared run's job verdict is not "converged"; else, per fixture:
    - `copper`: `p3.pair(n2 solid, n2 sheet, sheet_f_res_rel, conditioned_db)` with η ≤ `sheet_eta_db` (D reported). The winning copper `c` is "sheet" when it passes (explained counts) on both fixtures, else "solid"; every later check reads `c`'s steps.
    - `mesh`: `extrapolated` of n2, n3, n4 (n2, n3 when n4 is missing, with ifa2g4's observed p for the meander); `"value"` |f2 − f_ext|/f_ext (for "oscillating" max(|f2 − f4|, |f3 − f4|)/f4), pass within `mesh_f_res_rel` unless "not converging"; `"conditioned"` all three; `"ds11"` against S11 extrapolated pointwise at the same order (`S4 + (S4 − S3)/((4/3)^order − 1)`, or from S2 and S3; S4 itself when oscillating), and `"ds11_shift"` the shift-equivalent of `mesh_f_res_rel` on that extrapolated S11, as `p3.pair` takes it, explained when not conditioned and ds11 ≤ ds11_shift; plus `"kind"`, `"p"`, `"ratio"`.
    - `gap`: pair(n2, gap2, `gap_f_res_rel`, `conditioned_db`) with D ≤ `gap_d_db`, η ≤ `gap_eta_db`; `preset`: pair(n2, strict, `preset_f_res_rel`, `conditioned_db`) with η ≤ `preset_eta_db`.
    - Across fixtures: `converged` `{"pass", fixture: {"t_max": [names], "flat": [names]}}`; `pml` `{"pass", fixture: {"growth_db", "finite", "reach", "pass"}}`: the free run finite, growth ≤ `growth_db_max`, t_stop ≥ `free_reach` × t_max; `mur` `{fixture: {"report_only": True, ...}}` for each fixture whose MUR steps are recorded: its pair against n2 (Δf, ΔD, Δη) and its free run's growth, never a cause of "incomplete" unless the boundary needs it.
    - **Decisions:** `copper` c; `mesh_n` 3 when mesh fails (not explained) on either fixture; `gap_factor` 2 when gap fails on either; `preset` "strict" when preset fails on either; `boundary` "mur" when pml fails on a fixture and ifa2g4's MUR free run, and that of every fixture whose PML failed, passes the same growth rule; `t_max` "raised" when a compared run ended at T_max or RAISED holds a t_max_s, `flat` "widened" likewise with flat_s. **Verdict:** "incomplete" when a check is not judged or a MUR free run the boundary needs is missing; "blocked" when pml fails and a needed MUR free run grew too; "pass" when every default is kept; else "defaults raised", the raised ones in `fails`.
  - **`edits_2g4(decisions, gap_mm)`:** the project edits P3-D and P3-E apply to the 2.4 GHz boards: `copper`; `mesh.n` 3 with `gates.fit2d_limit` 0.05 (the pi board reads 3.53 % at n 3, r3); `air_gap_mm` at `gap_factor` × `gap_mm`; `preset` when "strict"; `boundary` "mur" with the λ/2 gap. T_max and the flat window are left out: they do not move a converged run's S.
  - **`tables`**, **`write`** as `p3b`'s: P3C-1 the checks per fixture with limit, value, pass, explained, |ΔS11| beside its threshold `ds11_shift`, and the mesh check's kind, observed p and ratio; P3C-2 the runs (verdict, t_stop, cells, split, f_res, depth, D, η_rad range, wall_s, predicted_s, worst_s, MC/s, pool); P3C-3 the decisions and, for each fixture with a T_max verdict or a raised T_max, `projected_stop(<its run folder>, PRESETS[preset][0], t_max_fit_s)` × `t_max_margin`, rounded up to a whole ns, and K = ceil((that − 2·t0)·f0) at that fixture's f0, t0 from its model.json; `p3c.json` holds `decisions["edits_2g4"]` from `edits_2g4(decisions, load_project(p3.base(out, "ifa2g4"))["air_gap_mm"])`, the fit2d probes of ifa2g4's n3 and n4 variants, and `machine` from `p0.machine` of `p3.records` over the recorded steps.
  - **`main`:** `--steps` optional; without it, `write`.
- [ ] **Step 4: Run them again.** Step 2's command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add tools/p3c.py tests/test_p3c.py
git commit -m "test(p3c): gate P3-C's rules, the observed-order extrapolation and the report, each failed check raising its antenna default (Stage 3 design 5.11)"
graphify update .
```

---

### Task 7 [code]: The fixture variants

**Files:**
- Modify: `tools/make_fixtures.py`; `tests/test_antenna_geometry.py`; `tests/test_cli_antenna.py` (`BANDS`); `tests/test_board.py:446`; `tests/test_fixtures.py` (`NAMES`); `tests/test_pads.py` (`test_pads_match_pcbnew`'s parametrize).
- Create (generated): `tests/fixtures/ifa2g4_pi_shift`, `ifa2g4_pi_dxp`, `ifa2g4_pi_dxm`, `ifa2g4_pi_pour`, each `.kicad_pcb` and `.pads.json`.

**Interfaces:**
- Consumes: `antenna_board`, `IFA`, `fence`, `zone`, `save`, `main`; `p0.edit`.
- Produces: `D_MOVE = 0.3`; `POUR = [(89.65, 98.99), (98.3, 98.99), (98.3, 100.25), (89.65, 100.25)]`; `moved(ae_at, outline, ground_top, radio_y, dx, dy) -> tuple`; `antenna_board(..., dx: float = 0.0, pour: list | None = None)`; BOARDS `ifa2g4_pi_shift`, `ifa2g4_pi_dxp`, `ifa2g4_pi_dxm`, `ifa2g4_pi_pour`; in the test, `D` and `EDITS`.

- [ ] **Step 1: Write the failing tests,** in `tests/test_antenna_geometry.py` (the parametrize of `test_each_antenna_fixture_builds_its_model` gains the four boards):

```python
BAND = (2.4e9, 2.4835e9)
D = 0.3  # make_fixtures.D_MOVE: one fine cell of the pi board at P3-C's n (Task 11 Step 1 re-sets both)
EDITS: dict = {}  # P3-C's edits_2g4 for the 2.4 GHz boards (Task 11 Step 1 copies p3c.json's in)


def built(tmp_path, name):
    pj = antenna_project(tmp_path / name, FIX / f"{name}.kicad_pcb", BAND)
    save_project(pj, p0.edit(load_project(pj), EDITS))
    return model_of(pj)[0]


def centres(name):  # pcbnew's pad centres by name, y up (the uuids differ: each board's seed is its name)
    return {v["name"]: v["center"] for v in json.loads((FIX / f"{name}.pads.json").read_text(encoding="utf-8")).values()}


def test_one_fine_cell_is_the_pi_boards_d(tmp_path):  # ruling 8: d is the fine cell at the copper under P3-C's n
    assert D == round(built(tmp_path, "ifa2g4_pi").mesh.d, 6)


def test_the_shifted_board_is_the_base_translated(tmp_path):  # design 5.11 P3-D; ruling 8
    base, shift = built(tmp_path, "ifa2g4_pi"), built(tmp_path, "ifa2g4_pi_shift")
    for axis, d in (("x", D), ("y", -D), ("z", 0.0)):  # KiCad's +D in y is -D with y up
        a, b = getattr(base.mesh, axis), getattr(shift.mesh, axis)
        assert len(a) == len(b) and np.abs(b - (a + d)).max() <= 1e-6 + 1e-9  # one 1e-6 mm quantum, float slack
    c0, c1 = centres("ifa2g4_pi"), centres("ifa2g4_pi_shift")
    assert c0.keys() == c1.keys() and len(c0) == 18
    assert all(abs(c1[k][0] - c0[k][0] - D) <= 1e-6 and abs(c1[k][1] - c0[k][1] + D) <= 1e-6 for k in c0)
    assert shift.blocked == []


def test_the_moved_front_end_keeps_the_ground_the_fence_and_the_mesh_across(tmp_path):  # ruling 8; r3 Q3
    base = built(tmp_path, "ifa2g4_pi")
    vias = {name: {tuple(v.at) for v in load_board(FIX / f"{name}.kicad_pcb").vias}
            for name in ("ifa2g4_pi", "ifa2g4_pi_dxp", "ifa2g4_pi_dxm")}
    for name, d in (("ifa2g4_pi_dxp", D), ("ifa2g4_pi_dxm", -D)):
        m = built(tmp_path, name)
        assert m.blocked == [] and np.array_equal(m.mesh.y, base.mesh.y) and np.array_equal(m.mesh.z, base.mesh.z)
        assert {round(100 + d + v, 6) for v in LOCAL_X} <= {e for e, _ in m.mesh.edges["x"]}  # AE1 moved by d
        gone, new = vias["ifa2g4_pi"] - vias[name], vias[name] - vias["ifa2g4_pi"]
        assert len(gone) == 3 and sorted((round(x + d, 6), y) for x, y in gone) == sorted(new)  # the to_gnd vias
        assert m.dt_ref == pytest.approx(base.dt_ref, rel=0.01)


def test_the_pour_stays_a_millimetre_from_the_antenna(tmp_path):  # design 5.11 P3-E; r3 Q4
    def gnd(name, layer):  # the GND zone fills on `layer`
        return shapely.union_all([a.polygon for a in load_board(FIX / f"{name}.kicad_pcb").areas
                                  if a.source == "zone" and a.net == "GND" and a.layer == layer])
    b = load_board(FIX / "ifa2g4_pi_pour.kicad_pcb")
    antenna = shapely.union_all([a.polygon for a in b.areas if a.ref == "AE1"] + [p.polygon for p in b.pads("AE1.1")])
    for layer in ("F.Cu", "B.Cu"):
        pour = gnd("ifa2g4_pi_pour", layer).difference(gnd("ifa2g4_pi", layer))
        assert 6.4 <= pour.area <= 6.7 and pour.distance(antenna) >= 0.999  # 8.65 × 0.76 mm above the main zone
    assert built(tmp_path, "ifa2g4_pi_pour").blocked == []
```

  Imports gain `json`, `numpy as np`, `shapely`, `p0` and `load_board`. The pour's area is the architect's arithmetic (6.57 mm² less the fill's rounded corners), not a probe: a miss stops the task with the measured value.
  - `tests/test_cli_antenna.py`: `BANDS` gains the four boards at `(2.4e9, 2.4835e9)`, so `antenna_project` takes them.
  - `tests/test_board.py:446`: the exemption reads `path.stem.startswith(("ifa2g4", "meander915"))`, so the new boards take the antenna boards' W_NETLESS_COPPER rule (plan 2's deferred minor: the names written once).
  - `tests/test_fixtures.py`'s `NAMES` and `tests/test_pads.py`'s `test_pads_match_pcbnew` parametrize gain the four boards: their pads.json, which the shift test reads, is checked against the reader.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_antenna_geometry.py tests/test_board.py tests/test_fixtures.py tests/test_pads.py -q`. Expected: FAIL (the four boards do not exist).
- [ ] **Step 3: `tools/make_fixtures.py`.**
  - `D_MOVE = 0.3` commented "one fine cell at the antenna's copper at mesh n 2 (the 0.6 mm stub over n, r3); 0.2 at n 3, which Task 11 regenerates when P3-C sets n 3"; `POUR` commented "P3-E's ground pour, GND on both layers 1.0 mm from AE1's open end and meander bottoms, overlapping the main zone by 0.5 mm so the fills join (r3 Q4)".
  - `moved(ae_at, outline, ground_top, radio_y, dx, dy)`: each offset by (dx, dy), the fence grid derived from them follows.
  - `antenna_board(..., dx=0.0, pour=None)`: right before `fence(...)`, `front = [*b.GetFootprints(), *b.GetTracks()]` (AE1, U1, the parts, their tracks and to_gnd vias); `fence` runs at the base's positions (a +0.3 move would drop the via at (104.5, 116.25) 1.42 mm from C1, r3); then each item of `front` moves by `pcbnew.VECTOR2I(MM(dx), 0)`; with `pour`, `zone(b, layer, pour, clearance=1.0)` on F.Cu and B.Cu. `save()` refills the zones.
  - BOARDS: `"ifa2g4_pi_shift": lambda b: antenna_board(b, *IFA[:2], *moved(*IFA[2:], D_MOVE, D_MOVE), pi=True)`, `"ifa2g4_pi_dxp"` and `"ifa2g4_pi_dxm"` (`dx=±D_MOVE`, `pi=True`), `"ifa2g4_pi_pour"` (`pi=True, pour=POUR`).
  - `main`: `rules = ANTENNA_RULES if name.startswith(("ifa2g4", "meander915")) else RULES`.
- [ ] **Step 4: Generate the four boards** in one PowerShell call (plan 2's Task 1 did this; never run KiCad or kicad-cli otherwise):

```powershell
& "<KiCad 9 bin folder>\python.exe" tools/make_fixtures.py tests/fixtures ifa2g4_pi_shift ifa2g4_pi_dxp ifa2g4_pi_dxm ifa2g4_pi_pour
git status --short tests/fixtures
```

  Expected: four names printed, exit 0; `git status` lists the eight new files and no changed fixture (the golden pins' boards and plan 2's three untouched).
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/make_fixtures.py tests/fixtures/ifa2g4_pi_shift.* tests/fixtures/ifa2g4_pi_dxp.* tests/fixtures/ifa2g4_pi_dxm.* tests/fixtures/ifa2g4_pi_pour.* tests/test_antenna_geometry.py tests/test_cli_antenna.py tests/test_board.py tests/test_fixtures.py tests/test_pads.py
git commit -m "test(fixtures): the pi variant shifted whole, its front end moved by one fine cell either way, and a ground pour in its clearance, for gates P3-D and P3-E (Stage 3 design 5.11)"
graphify update .
```

---

### Task 8 [code]: P3-D and P3-E's gate

**Files:**
- Create: `tools/p3d.py`, `tests/fixtures/p3d/criteria.json`, `tests/test_p3d.py`.

**Interfaces:**
- Consumes: Task 1's `p3.*` and `test_p3.gates`; Task 6's `p3c.json` (`decisions.edits_2g4`); Task 7's boards; `pipeline.antenna_result`; `core.post.antenna.deltas`; `p3a._cell`.
- Produces: `CRITERIA`; `BOARDS = ("ifa2g4_pi", "ifa2g4_pi_shift", "ifa2g4_pi_dxp", "ifa2g4_pi_dxm")`; `POUR = "ifa2g4_pi_pour"`; `VALUES: list[str] | None = None`; `REFINE: int | None = None`; `project_name(board: str) -> str`; `configure(out: Path, board: str) -> Path`; `copy_project(out: Path, source: str, name: str) -> Path`; `run(out: Path, board: str) -> None`; `pair(base: Path, variant: Path) -> dict`; `thresholds(noise: dict) -> dict`; `decide_d(pairs: dict[str, dict | None]) -> dict`; `decide_e(p: dict | None, shift_rel: float, db: float) -> dict`; `write(out: Path) -> dict`; `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: The criteria,** `tests/fixtures/p3d/criteria.json`:

```json
{"source": "Stage 3 design 5.8 and 5.11, gates P3-D and P3-E; plan 4 rulings 1 and 10 (r3): the pi variant verified at plan 3's snapped values, re-searched once by plan 3 Task 9's search on the base's run (p3d.VALUES, one set on every board) only when the base's verify dips above -6 dB; noise the largest delta over the repeat, the whole shift and the front end moved by plus and minus d, each quantity reported with its odd and even parts; thresholds max(the design's default, 3 x the noise), rounded up; BW_LIMIT 3 x the bandwidth noise over f0, rounded up, only when above the frequency threshold; the -6 dB screen kept unless a compared dip lies within 3 x the depth noise of it; P3-E resolved under the thresholds, its dip conditioned, its sign negative (soft); if P3-E is not resolved, P3-D is refined once: the next mesh n with fit2d 0.05 and the moved boards at that n's d (p3d.REFINE), every pair and the pour run again, the thresholds by the same rule",
 "values": ["L1=0R", "C2=0.13pF", "C3=1pF"], "conditioned_db": -6.0, "move_f_res_rel": 0.002, "move_eta_db": 0.1,
 "default_shift_rel": 0.003, "default_db": 0.2, "factor": 3, "shift_step_rel": 0.0005, "db_step": 0.05, "pour_sign": -1}
```

- [ ] **Step 2: Write the failing tests,** `tests/test_p3d.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

import p0
import p3
import p3d
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.project import load_project
from test_p3 import gates  # noqa: F401 (the fixture)


@pytest.fixture(autouse=True)
def first_values(monkeypatch):  # the gates' own VALUES and REFINE, set on their branches, never reach a test
    monkeypatch.setattr(p3d, "VALUES", None)
    monkeypatch.setattr(p3d, "REFINE", None)


def p(df_rel=0.0, deta=0.0, dd=0.0, depth=(-12.5, -12.5), dbw=0.1, ds11=0.004):  # a pair's deltas, f0 2441.75 MHz
    return {"f0_hz": 2.44175e9, "df_rel": df_rel, "deta_tot_db": [deta] * 3, "deta_rad_db": [deta] * 3,
            "dgain_db": dd, "dd_db": dd, "dbw_mhz": dbw, "ds11_max": ds11, "depth_db": depth}


def test_the_thresholds_are_three_times_the_noise_never_below_the_defaults():  # ruling 10; BW_LIMIT's rule
    assert p3d.thresholds({"f_rel": 0.0004, "db": 0.03, "bw_rel": 0.0005}) == {"shift_rel": 0.003, "db": 0.2,
                                                                                 "bw_rel": None}
    t = p3d.thresholds({"f_rel": 0.0013, "db": 0.09, "bw_rel": 0.0005})
    assert (t["shift_rel"], t["db"]) == (pytest.approx(0.004), pytest.approx(0.3))  # 0.0039 and 0.27, rounded up
    assert p3d.thresholds({"f_rel": 0.001, "db": 0.2 / 3, "bw_rel": 0.0})["shift_rel"] == 0.003  # at the defaults
    assert p3d.thresholds({"f_rel": 0.0004, "db": 0.03, "bw_rel": 0.0011})["bw_rel"] == pytest.approx(0.0035)


def test_the_p3d_rules():  # design 5.11 P3-D; RF 3
    pairs = {"repeat": p(), "shift": p(0.0001, 0.01), "dxp": p(0.002, -0.1), "dxm": p(-0.0015, 0.05)}
    d = p3d.decide_d(pairs)
    assert d["verdict"]["value"] == "pass" and (d["noise"]["f_rel"], d["noise"]["db"], d["noise"]["ds11"]) == (
        0.002, 0.1, 0.004)
    assert (d["shift_rel"], d["db"], d["bw_rel"]) == (pytest.approx(0.006), pytest.approx(0.3), None)  # a pass widens
    assert d["odd_even"]["f_rel"] == (pytest.approx(0.00175), pytest.approx(0.00025)) and d["position_bound"] is True
    assert d["screen"]["kept"] is True  # every dip 6.5 dB under -6 dB, its depth noise 0
    assert p3d.decide_d({**pairs, "dxm": p(-0.00201)})["verdict"]["fails"] == ["dxm"]
    assert p3d.decide_d({**pairs, "dxp": p(deta=0.101)})["verdict"]["fails"] == ["dxp"]
    unconditioned = p3d.decide_d({**pairs, "shift": p(depth=(-12.5, -5.9))})
    assert unconditioned["verdict"] == {"value": "fail", "fails": ["shift"]} and unconditioned["shift_rel"] is None
    assert p3d.decide_d({**pairs, "repeat": None})["verdict"]["value"] == "incomplete"


def test_the_p3e_rule():  # design 5.11 P3-E
    e = p3d.decide_e(p(-0.0031), 0.003, 0.2)
    assert (e["resolved"], e["sign"], e["pass"], e["ratio"]) == (True, "as expected", True, pytest.approx(1.0333, abs=1e-4))
    assert p3d.decide_e(p(-0.003), 0.003, 0.2)["pass"] is False  # resolved means larger, strictly (deltas' rule)
    assert p3d.decide_e(p(0.01), 0.003, 0.2)["sign"] == "opposite"  # soft: reported, still a pass
    assert p3d.decide_e(p(-0.01, depth=(-12.5, -5.0)), 0.003, 0.2)["pass"] is False  # the pour lifted the dip


def test_p3d_runs_retunes_copies_and_verifies(gates, monkeypatch):  # design 5.11 P3-D; r3 Q1
    monkeypatch.setenv("KRS_FAKE", "network")  # as pi_run: the pi's 4 jobs on the known network
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)  # the fake's operator dump is empty
    p0.save(gates / "p3c" / "p3c.json", {"decisions": {"edits_2g4": {}}})
    assert p3d.main(["--out", str(gates), "--steps", "ifa2g4_pi"]) == 0
    assert all((gates / "steps" / f"p3-{s}.json").is_file()
               for s in ("d-ifa2g4_pi-run", "d-ifa2g4_pi-verify", "d-ifa2g4_pi-rep-verify"))
    base, rep = (p3.project_path(gates, n) for n in ("d-ifa2g4_pi", "d-ifa2g4_pi-rep"))
    assert load_project(rep)["verify"]["values"] == {"L1": "0R", "C2": "0.13pF", "C3": "1pF"}
    assert load_project(rep)["results"] == load_project(base)["results"]
    pr = p3d.pair(base, rep)  # one run, one verify model, one fake: the same S11
    assert pr["depth_db"][0] == pr["depth_db"][1] and pr["df_rel"] in (None, 0.0)
    v = p3.measure(gates, "d-ifa2g4_pi", "verify")
    assert (v["pool"], v["cal_mcs"]) == (1, 200.0) and v["cells"] > 0  # verify's one job: a row of the refit
    monkeypatch.setattr(p3d, "VALUES", ["L1=0R", "C2=0.1pF", "C3=1pF"])  # a re-searched set (Task 11 Step 2)
    assert p3d.main(["--out", str(gates), "--steps", "ifa2g4_pi"]) == 0  # every verify reruns: its key holds them
    assert load_project(rep)["verify"]["values"]["C2"] == "0.1pF" == load_project(base)["verify"]["values"]["C2"]
    monkeypatch.setattr(p3d, "REFINE", 3)  # P3-E's fallback: the next n, under its own names
    pj = p3d.configure(gates, "ifa2g4_pi")
    assert pj.parent.name == "r-ifa2g4_pi" and (load_project(pj)["mesh"]["n"],
                                                load_project(pj)["gates"]["fit2d_limit"]) == (3, 0.05)
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_p3d.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'p3d'`.
- [ ] **Step 4: `tools/p3d.py`.** Module docstring: "P3-D, the noise floor, and P3-E, the positive control (Stage 3 design 5.11), on the pi variant ifa2g4_pi and its variant boards, each run, retuned to plan 3's snapped values and verified, with P3-C's defaults applied: the pairs through antenna_result and deltas, the thresholds that compare then uses, and p3d.json/p3d.md and p3e.json/p3e.md in <out>. Run: python tools/p3d.py --out DIR [--steps ...]."
  - **`VALUES`** (None: criteria's `values`) and **`REFINE`** (None: P3-C's mesh n) are set only on their pre-registered branches (Task 11 Steps 2 and 5), each a recorded deviation. **`project_name(board)`:** `f"{'r' if REFINE else 'd'}-{board}"`; the repeat is `project_name("ifa2g4_pi") + "-rep"`.
  - **`configure(out, board)`:** `p3.variant(out, project_name(board), f"{board}_r" if REFINE and board in BOARDS[1:] else board, edits)`, edits the `decisions.edits_2g4` of `<out>/p3c/p3c.json` (SystemExit "run P3-C first" when it is missing), plus `mesh.n` REFINE and `gates.fit2d_limit` 0.05 under REFINE.
  - **`copy_project(out, source, name)`:** `name`'s project.json is `source`'s without `verify`, made once (same folder depth, so the board path stands). Returns it.
  - **`run(out, board)`:** `pj = configure(out, board)`; `p3.run_step(out, project_name(board))`; `p0.cli("retune", str(pj), *values)`, values `VALUES or CRITERIA["values"]`, RuntimeError on a non-zero exit; for `ifa2g4_pi`, the repeat `copy_project(out, <its name>, <repeat>)` once, right after its first retune, and `p0.cli("retune", str(<repeat>), *values)` every time, so the two always hold one set; then `p3.run_step(out, project_name(board), "verify")` and, for `ifa2g4_pi`, `p3.run_step(out, <repeat>, "verify")`. `--steps` takes the board names.
  - **`pair(base, variant)`:** both `pipeline.antenna_result`; `rows = deltas(b["project"], b["f"], (b["s11"], b["far"]), (v["s11"], v["far"]))`; `{"f0_hz", "df_rel": the resonance row's delta in MHz over f0 in MHz (None without a dip on either), "deta_tot_db": the three eta_tot rows' deltas, "deta_rad_db": 10·log10(η_rad,v/η_rad,b) at the recorded frequencies nearest f_lo, f0 and f_hi, "dgain_db": the peak_gain row's delta, "dd_db": ΔD in dB at f0, "dbw_mhz": the bandwidth row's delta, "ds11_max": the largest |ΔS11| over [f_lo, f_hi], "depth_db": (each lowest |S11| in dB)}`.
  - **`thresholds(noise)`:** `{"shift_rel", "db", "bw_rel"}`: `max(default, factor × noise)` for `f_rel` and `db`, each rounded up to `shift_step_rel` and `db_step` (`math.ceil(round(x / step, 9)) * step`, rounded to 6 decimals); `bw_rel` `factor × noise["bw_rel"]` rounded up to `shift_step_rel` when that exceeds `shift_rel`, else None. `# ponytail: two ±d moves are a thin sample; their maximum is the conservative statistic (r3 Q5)`.
  - **`decide_d(pairs)`:** pairs `repeat`, `shift`, `dxp`, `dxm` (the base against the repeat, the shift, `-dxp` and `-dxm`; `dxp` against `dxm` is reported only). A pair is conditioned when both depths are at or below `conditioned_db`; an unconditioned one fails and leaves the thresholds None (the controller rules). `noise`: `f_rel` the largest |df_rel|, `db` the largest |Δ| over η_tot, η_rad, the peak gain and D, `bw_rel` the largest |dbw_mhz| over f0 in MHz, `depth_db` the largest |Δdepth|, `ds11` the largest ds11_max. `odd_even`: for f_rel and each dB quantity, ((Δ+ − Δ−)/2, (Δ+ + Δ−)/2) of the ±d pairs, the odd part the position's slope × d, the even one discretization and curvature; `position_bound` |odd| > 2·|even| on f_rel. `screen`: `{"depth_noise_db", "margin_db": the smallest (−6 − depth) over every compared dip, "kept": margin > 3 × depth noise}`. `dxp` and `dxm` pass with |df_rel| ≤ `move_f_res_rel` and every |Δη_tot|, |Δη_rad| ≤ `move_eta_db`. Returns `{"pairs", "noise", "odd_even", "position_bound", "screen", "shift_rel", "db", "bw_rel", "verdict": {"value": "pass" | "fail" | "incomplete", "fails"}}`; the thresholds come from `thresholds` on a pass and on a fail alike (the design's fallback is the same rule).
  - **`decide_e(p, shift_rel, db)`:** resolved |df_rel| > shift_rel, strictly; `ratio` |df_rel|/shift_rel; `sign` "as expected" when df_rel has `pour_sign`'s sign, else "opposite" (soft); pass when resolved and both depths are conditioned.
  - **`write(out)`:** after `p3.records` over the recorded steps: p3d.json and p3d.md (P3D-1 the pairs' deltas with their odd and even parts, P3D-2 noise, thresholds, the BW need, the screen and the largest |ΔS11| against verify's 0.0076 at f0 and 0.0149 at most (plan 3), P3D-3 every run and verify step's `p3.measure` without `f_hz` and `s11`: pool, cells, split, speeds_mcs, cal_mcs, predicted_s, worst_s, wall_s); with the pour's verify recorded, p3e.json and p3e.md (its pair, `decide_e` at P3-D's thresholds, its runs likewise).
- [ ] **Step 5: Run them again.** Step 3's command. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/p3d.py tests/test_p3d.py tests/fixtures/p3d/criteria.json
git commit -m "test(p3d): gates P3-D and P3-E on the pi variant, the noise floor's pairs and the significance thresholds at three times it (Stage 3 design 5.11)"
graphify update .
```

---

### Task 9 [run]: P3-B

Each block is one PowerShell call, run in the background and waited on, from this template (each step names `<block>`, `<tool>` and `<steps>`):

```powershell
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"; $g = Join-Path $HOME "krs-gates"
New-Item -ItemType Directory -Force "$g\logs" | Out-Null; $t = Get-Date
& .venv\Scripts\python.exe -X utf8 tools\<tool>.py --out $g --steps <steps> *> "$g\logs\<block>.log"
"<block> $($t.ToString('s')) $((Get-Date).ToString('s')) exit $LASTEXITCODE" | Add-Content "$g\logs\ledger.txt"
```

A report is the template's first line, then `& .venv\Scripts\python.exe -X utf8 tools\<tool>.py --out $g`. A block that exits 1 names its failed step in its log: superpowers:systematic-debugging, never a blind rerun.

- [ ] **Step 1: The sheet check,** before src freezes: openEMS's real setup of all-sheet copper on the three fixtures, and one short run, retune and verify of the sheet pi project (T_max 3 ns, a smoke run), in the background:

```powershell
$s = Join-Path $env:TEMP 'krs-plan4-sheet'; Remove-Item -Recurse -Force $s -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $s | Out-Null
$env:LOCALAPPDATA = "$s\data"; $env:XDG_DATA_HOME = "$s\data"; $env:CSXCAD_INSTALL_PATH = "<openEMS folder>"
$krs = ".venv\Scripts\kicad-rf-studio.exe"
foreach ($c in @(@("ifa2g4", "2400MHz:2483.5MHz"), @("ifa2g4_pi", "2400MHz:2483.5MHz"), @("meander915", "902MHz:928MHz"))) {
  $b, $band = $c; Copy-Item "tests\fixtures\$b.kicad_pcb" $s
  & $krs new "$s\$b.kicad_pcb" --start U1.1 --antenna AE1 --band $band -o "$s\$b" *> "$s\$b-new.log"
  & .venv\Scripts\python.exe -c "import sys; from pathlib import Path; from kicad_rf_studio.core.project import load_project, save_project; p = Path(sys.argv[1]); save_project(p, {**load_project(p), 'copper': 'sheet', 't_max_s': 3e-9})" "$s\$b\project.json"
  & $krs cost "$s\$b" *> "$s\$b-cost.log"; "$b cost $LASTEXITCODE" | Add-Content "$s\codes.txt" }
& $krs run "$s\ifa2g4_pi" *> "$s\pi-run.log"; "pi run $LASTEXITCODE" | Add-Content "$s\codes.txt"
& $krs retune "$s\ifa2g4_pi" L1=0R C2=0.13pF C3=1pF *> "$s\pi-retune.log"; "pi retune $LASTEXITCODE" | Add-Content "$s\codes.txt"
& $krs verify "$s\ifa2g4_pi" *> "$s\pi-verify.log"; "pi verify $LASTEXITCODE" | Add-Content "$s\codes.txt"
```

  Expected: codes.txt holds `cost 0` three times, then `pi run 0`, `pi retune 0`, `pi verify 0`; each cost log's I_COST_DT at or above 0.8 × its reference (about 2.14e-13 s against 2.31e-13 s on ifa2g4 and 2.36e-13 s against 2.46e-13 s on the pi, the feasibility review's setup), and no E_PORT_SHORT, E_PORT_OPEN, E_PORT_BOX, E_DT_FLOOR or E_UNUSED_PRIMITIVE in any log; each run folder's model.json under `$s\data\kicad-rf-studio\runs` holds `"copper": "sheet"` with every copper z0 equal to its z1; the verify log has its far-field lines. About 15–20 min (a fresh calibration first). A failure is fixed test-first in Task 2's modules, its own commit, before Step 2.
- [ ] **Step 2: The tip.** The full suite in the background, then `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass; record the counts and `git rev-parse HEAD:src`: src is frozen from here to Task 11's last run.
- [ ] **Step 3: Block B0,** `<tool>` p3b, `<steps>` geometry: the free pre-check. Expected: exit 0 in seconds (with `new`); `<GATES>\steps\p3b-geometry.json` holds XORs within 1.0 mm² (F.Cu) and 0.2 mm² (B.Cu). Above them: stop, a transcription or import bug.
- [ ] **Step 4: Block B1,** `<steps>` hand. Expected: exit 0; about 11–14 min if openEMS's −50 dB criterion ends it at 12–15 ns, at most 27 min to 30 ns (1.27 M nodes at the first run's 222.8 MC/s, r1). Check `<GATES>\p3b\hand\hand.json`: `criterion_hit`, or `decay_db` ≤ −40; else Block B1′ (`<steps>` hand-f1, λ/2 at f1, 81.465 mm), a recorded deviation, whose `hand-f1\hand.json` Step 5 commits instead. A hand-f1 run that is not valid either: stop for a ruling.
- [ ] **Step 5: Commit the reference** before the product's side (the full suite first, between blocks):

```powershell
Copy-Item "$g\p3b\hand\hand.json" tests\fixtures\p3b\references.json
git add tests/fixtures/p3b/references.json
git commit -m "test(p3b): the hand-built model's reference, committed before the product's side runs (Stage 3 design 5.11)"
```

- [ ] **Step 6: Block B2,** `<steps>` product. Expected: exit 0; about 25 min (the first run: one job 25.0 min, predicted 28 min); the step `p3-ifa2g4-solid-n2-run` is P3-C's ifa2g4 baseline too.
- [ ] **Step 7: Judge.** The p3b report, then read `<GATES>\p3b\p3b.md`.
  - **pass** or **explained** (an f_res miss on an unconditioned minimum whose max |ΔS11| in band is within its 1 % shift-equivalent, D and η_rad within limits, the runs valid): go on.
  - **fail:** P3-B blocks until explained (design §5.11). The pre-registered diagnostics, in order, each a block and a report: (a) the XOR (done); (b) `<steps>` product-mur (MUR at 62.456762 mm, about 23 min); (c) `<steps>` hand-030 (the hand at 0.30 mm, about 17 min). The verdict's diagnosis decides: "boundary", "mesh" or "boundary and mesh" is "failed, explained: <diagnosis>", the default it touches named (the absorber for boundary, the mesh n for mesh); "product bug presumed" is superpowers:systematic-debugging, a fix test-first in its own commit, a ruling on the src freeze, and `<steps>` geometry,product again against the unchanged reference.
- [ ] **Step 8: The report,** `docs/validation/<date>-p3-b.md` with `<date>-p3-b.json` (a copy of `p3b.json`), r4's sections:
  1. Verdict, and the diagnosis on a fail.
  2. Inputs: the commands with `<GATES>` and `<openEMS folder>`, the versions, the calibration, the fixture, the hand model's settings.
  3. Measured against limit: P3B-1 to P3B-3, f_res with its |ΔS11| and its 1 % shift-equivalent.
  4. Decisions, each "controller recommendation, owner unavailable".
  5. Stated limits and deviations: the differences by design (MUR at λ/2, own mesh, exact port box, the mask smeared, the Gauss pulse); the explanation's threshold, the 1 % shift-equivalent on the hand's S11, with its value (ruling 1 as amended at commit); AN043 as a soft note only.
  6. Machine time: predicted (hand 27 min; the product by the formula, to t_stop and to T_max) against measured, per block.
  7. Next step.

  No path and no host name. Full suite, then `git commit -m "docs(validation): gate P3-B, the pipeline against a hand-built model of the 2.4 GHz fixture (Stage 3 design 5.11; controller recommendation, owner unavailable)"`, then `graphify update .`.

---

### Task 10 [run]: P3-C

Blocks from Task 9's template with `<tool>` p3c. After each block: the p3c report (an interim report from the recorded steps) and a checkpoint in the ledger: exit code, times, each step's verdict and t_stop, its predicted time (to t_stop and to T_max) against measured, any loaded step, and any orphaned run folder (a `runs` folder no step record names, left by an interrupted step) named for the report. A graceful stop is `New-Item "$g\STOP"`, which waits for the running step (never a STOP file in a run folder); delete `$g\STOP` before the next block. Times are r2's at a pool of 1, the sheet runs' scaled to openEMS's measured timestep ratio, 1.86 rather than 2.1.

- [ ] **Step 1: Block C1:** `<steps>` ifa2g4-sheet-n2 (`ifa2g4-solid-n2` is recorded). Expected: exit 0, about 13 min.
- [ ] **Step 2: Block C2:** `<steps>` meander915-solid-n2. Expected: exit 0; 2.2 h if it converges near a third of its 79 ns T_max, 6.9 h at T_max. **CP2:** its verdict and t_stop re-plan the rest, the remaining blocks re-estimated from its t_stop or its projection.
  - Converged: go on.
  - `t_max` (ruling 9's branch): the interim report's P3C-3 projection becomes `RAISED["meander915"]["t_max_s"]` in `tools/p3c.py` (a tools commit, the full suite first: `git commit -m "chore(p3c): the meander's T_max raised from its first run's decay (plan 4 ruling 9; controller recommendation, owner unavailable)"`); every meander step reruns at it (its key changes); its `n4` steps are dropped from Block C5 (the extrapolation takes the 2.4 GHz fixture's order); recorded as a deviation. A None projection: stop for a ruling.
  - `flat`: `RAISED["meander915"]["flat_s"] = round(40 / 915e6, 12)` likewise (`chore(p3c): the meander's flat window widened to 40 periods of f0 ...`). A run of ifa2g4 that ends at T_max or flat takes the same route through `RAISED["ifa2g4"]`.
- [ ] **Step 3: Block C3:** `<steps>` meander915-sheet-n2 (plus meander915-solid-n2 again on a RAISED branch). Expected: about 1.1–3.5 h. **CP3:** the interim report's `decisions.copper` is the winning copper `<c>` for every later step.
- [ ] **Step 4: Block C4,** ifa2g4 on `<c>`: `<steps>` ifa2g4-<c>-n3,ifa2g4-<c>-n4,ifa2g4-<c>-gap2,ifa2g4-<c>-strict,ifa2g4-<c>-free,ifa2g4-<c>-mur,ifa2g4-<c>-murfree. Expected: about 5.4 h solid, 3.5 h sheet (r2; MUR at λ/2 builds about 0.27 × the PML work, its free run to 3 × T_max, 90 ns). **CP4:** n, gap, preset and PML stability for the 2.4 GHz fixture; the fit2d probes of n3 and n4: RF's 0.6 mm section within 5 %, the 1.35 mm section within 3 % (ruling 2).
- [ ] **Step 5: Block C5,** the meander on `<c>`: `<steps>` meander915-<c>-n3,meander915-<c>-n4,meander915-<c>-gap2,meander915-<c>-strict,meander915-<c>-free. Expected: about 13 h (sheet, converging) to about 70 h (solid, on the RAISED branch), as CP2 re-estimated. When the interim report's pml check fails on the meander: Block C5′, `<steps>` meander915-<c>-mur,meander915-<c>-murfree (about 2 h), before the boundary is decided.
- [ ] **Step 6: The report.** The p3c report; verdict "pass" or "defaults raised" (each fallback in force and recorded); "blocked" (PML unstable and a needed MUR free run grew too) stops Stage 3 for a ruling; "incomplete" names its missing or unconverged steps. `docs/validation/<date>-p3-c.md` and `.json`, Task 9's sections; §4 decides each default (copper, n, gap, preset, boundary, T_max, flat window) with its rule, and records whether the cell d taken from the feed network alone stands (plan 2's open issue 2: it stands when n 2 passes); §5 states ruling 2's fit2d limit with r2's cause (a mesh-line conflict between AE1's 0.5 mm feed pad and the 0.6 mm stub, Z0 4–5 % high, at most 0.06 % on f_res), the observed orders (and the two-mesh branch's assumed one), the reading of "3 × the stop time", the MUR free run's 3 × T_max window, the RAISED branch if taken, the free runs' growth, that the copper comparison ran at mesh n 2, and sheet copper's scope (both fixtures' feeds keep their ground 1 mm away; Stage 1 §5.3's 8.7 % GCPW reading still holds for a coplanar gap under 30·t); §6 per block against this plan's estimates (ruling 9's about 20 h all-sheet, 33 h solid, up to 82 h; up to about 95 h on the RAISED branch). Full suite, then `git commit -m "docs(validation): gate P3-C, convergence and defaults on both fixtures (Stage 3 design 5.11; controller recommendation, owner unavailable)"`, `graphify update .`.

---

### Task 11 [run]: P3-D and P3-E

- [ ] **Step 1: d and the edits follow P3-C.** In `tests/test_antenna_geometry.py`, `EDITS` becomes p3c.json's `decisions.edits_2g4` (a literal); when `decisions.mesh_n` is 3, `D_MOVE = 0.2` in `tools/make_fixtures.py` and `D = 0.2` in the test, and Task 7's Step 4 runs again for `ifa2g4_pi_shift ifa2g4_pi_dxp ifa2g4_pi_dxm`. Task 7's tests (`test_one_fine_cell_is_the_pi_boards_d` among them), the full suite, then `git commit -m "test(fixtures): the pi variants at P3-C's settings (plan 4 ruling 8)"`. tests/ and tools/ are outside `code_id`, so no record moves.
- [ ] **Step 2: Block D1,** `<tool>` p3d, `<steps>` ifa2g4_pi: the base and its repeat. Expected: exit 0; about 2 h at n 2 solid (the run's 4 jobs at once 63 min, two verify jobs about 30 min each), about 1.66 times that at n 3, about half with sheet copper. Check: the base's verify dips to −6 dB or below inside the grid; else the pre-registered re-search: plan 3 Task 9 Step 3's search (E24 values and the bypasses, closed as the retune closes them, the smallest largest |S11| over [f_lo, f_hi]) on this run's layout, in scratch; its best set becomes `p3d.VALUES` (a tools commit, the full suite first, a recorded deviation) and D1 runs again (the run is kept; every verify reruns, its key holding the values).
- [ ] **Step 3: Block D2:** `<steps>` ifa2g4_pi_shift,ifa2g4_pi_dxp,ifa2g4_pi_dxm. Expected: about 4.7 h at n 2 solid (three run-retune-verify sequences of about 1 h 33 min); about 13.7 h for D1 to E1 at n 3. **CP-D:** the p3d report; P3-D's verdict, noise, thresholds, the ±d moves' odd and even parts, the −6 dB screen against the depth noise. An unconditioned pair: stop for a ruling.
- [ ] **Step 4: The P3-D report,** `docs/validation/<date>-p3-d.md` and `.json`: §3 the pairs (repeat, whole shift, ±d, and +d against −d reported only), whether the repeat was bit-identical in S11, that the whole shift checks translation invariance only, so the noise rests on the two ±d samples; each quantity's odd part (sensitivity to position) and even part (discretization) and, when |odd| > 2·|even| on f_res, that the thresholds are set by sensitivity to position rather than noise (an owner item: thresholds from max(|repeat|, |shift|, |even|), or a mesh-only probe); the largest |ΔS11| against verify's 0.0076 at f0 and 0.0149 at most (plan 3's matching run); the −6 dB screen against each dip's depth and the depth noise; §4 the thresholds `shift_rel`, `db` and BW_LIMIT's need, with the depth of the dip it was measured on; §6 the machine time (pool-4 runs predicted about 1.5 times high until Task 12's refit). Full suite, then commit `docs(validation): gate P3-D, the noise floor on the 2.4 GHz fixture's pi variant (Stage 3 design 5.11; controller recommendation, owner unavailable)`.
- [ ] **Step 5: Block E1:** `<steps>` ifa2g4_pi_pour. Expected: about 1 h 33 min. Then the p3d report writes p3e. **Not resolved:** first the pour's dip depth and the shift's sign, to tell a weak control from wide thresholds; then the pre-registered fallback (design §5.11: refine and repeat P3-D): REFINE = P3-C's n + 1 (fit2d 0.05 on the pi boards, 3.53 % at n 3); in `tools/make_fixtures.py`, `D_REFINE = round(0.6 / REFINE, 6)` and BOARDS `ifa2g4_pi_shift_r`, `ifa2g4_pi_dxp_r`, `ifa2g4_pi_dxm_r` at it, `BANDS` and a load-and-build test of each at REFINE, generated as Task 7 Step 4 does; `p3d.REFINE` set; a tools/tests commit, the full suite first; then D1, D2 and E1 again under the `r-` names (about 10 h at n 3, r3), the thresholds by the same rule, P3-E judged once more. A second miss goes to the controller.
- [ ] **Step 6: The P3-E report,** `docs/validation/<date>-p3-e.md` and `.json`: §3 its pair, |Δf| over the threshold, the pour's dip depth and the sign, and, in one call with `$env:LANGUAGE = "en"` and LOCALAPPDATA and XDG_DATA_HOME at `$g\data`, `.venv\Scripts\kicad-rf-studio.exe compare "$g\projects\d-ifa2g4_pi" "$g\projects\d-ifa2g4_pi_pour" -o "$g\compare-e"` (seconds, no openEMS; the `r-` projects on the refine branch), its lines (they still print the provisional wording until Task 13); §6 its machine time predicted (to t_stop and to T_max) against measured. Full suite, then commit `docs(validation): gate P3-E, the ground-pour positive control (Stage 3 design 5.11; controller recommendation, owner unavailable)`. `<GATES>` stays until the Stage 3 exit record (plan 5's acceptance may reuse its projects).

---

### Task 12 [decision]: The cost refit by pool level

**Files:**
- Modify: `tools/p3.py` (`rows`, `refit`, `refit_record`; `predicted_s` reads the level), `tests/test_p3.py`; `src/kicad_rf_studio/runs.py`; `pipeline.py` (`cost_notes`); `core/messages.py`; `po/*`, the `.mo`; `tests/test_cost_model.py`.
- Create: `docs/validation/<date>-p3-refit.md`, `.json`.

**Interfaces:**
- Produces: `p3.rows(out: Path) -> list[dict]`; `p3.refit(rows: list[dict], w: float, like: tuple[dict, dict] | None = None, band: float = 0.25) -> dict`; `p3.refit_record(out: Path, like: tuple[str, str], extra: list[dict], dest: Path) -> dict`; `runs.SMALL_SPEED: dict[int, float]`; `runs.small_speed(pool: int) -> float`.

- [ ] **Step 1: Write the failing tests,** in `tests/test_p3.py`:

```python
def test_the_refit_recovers_the_small_speed_by_level_and_judges_w_on_its_pair():  # design 5.9; ruling 6
    def row(pool, f, small, w=6.38, cal=580.0):
        return {"pool": pool, "f_pml": f, "cal_mcs": cal, "node_mcs": small * cal / (1 + (w - 1) * f)}
    rows = [row(1, f, 0.42) for f in (0.0, 0.31, 0.38, 0.44)] + [row(4, 0.434, 0.58, cal=205.6)]
    out = p3.refit(rows, 6.38, like=(rows[0], rows[3]))
    assert out["small"] == {1: pytest.approx(0.42), 4: pytest.approx(0.58)}
    assert (out["w_fit"], out["w_line"]) == (pytest.approx(6.38), pytest.approx(6.38)) and out["moved"] is False
    assert out["w"] == 6.38
    moved = [row(1, f, 0.42, w=9.0) for f in (0.0, 0.31, 0.44)]
    out = p3.refit(moved, 6.38, like=(moved[0], moved[2]))
    assert out["moved"] and out["w"] == pytest.approx(9.0) and out["small"][1] == pytest.approx(0.42)


def test_the_rows_are_each_recorded_run_and_verify_once(gates):  # free runs and hand runs left out
    p3.variant(gates, "a", "ifa2g4", {})
    p3.run_step(gates, "a")
    p3.free_step(gates, "a", 30e-9)
    (row,) = p3.rows(gates)
    m = p3.measure(gates, "a")
    assert row == {"step": "p3-a-run", "pool": 1, "cells": m["cells"], "f_pml": m["split"][2] / m["cells"],
                   "node_mcs": 100.0, "cal_mcs": 200.0}
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_p3.py -q`. Expected: FAIL (`module 'p3' has no attribute 'refit'`).
- [ ] **Step 3: `tools/p3.py`.**
  - `rows(out)`: every record in `out/steps` of a `p3-…-run` or `p3-…-verify` step, not loaded, through `measure`: `{"step", "pool", "cells", "f_pml": split[2]/cells, "node_mcs": the median of speeds_mcs, "cal_mcs"}`, a row lacking any of them left out. One record per step id, so the step P3-B and P3-C share counts once.
  - `refit(rows, w, like, band)`: each row's k = node_mcs·(1 + (w − 1)·f_pml)/cal_mcs; `small[pool]` the median of its pool's k, to 3 significant digits. `w_fit` from `like`, the f_PML-0 row and its twin of one fixture, mesh n and copper at a pool of 1 (P3-A's method): 1 + (r − 1)/f, r = (node_0/cal_0)/(node_f/cal_f); `w_line` from the pool-1 rows (two distinct f_pml at least), cal/node = a + b·f_pml by least squares, 1 + b/a, a cross-check; `moved` when |w_fit − w| > band·w; then `w = w_fit` and the k's again at it. Returns `{"small", "w_fit", "w_line", "w", "moved"}`.
  - `refit_record(out, like, extra, dest)`: `rows(out) + extra`, the `like` step ids' rows, `refit` at `runs.PML_WEIGHT` with `band` from `tests/fixtures/p3c/criteria.json`'s `refit_w_band`; writes `dest.json` (`rows`, `like`, `result`, the constants before) through `p0.save` and `dest.md` (the rows with their k against cells and f_PML, by `p0.table`, then the result). Returns the JSON.
- [ ] **Step 4: Run them again.** Step 2's command. Expected: PASS.
- [ ] **Step 5: The fit,** in one call (`<c>` P3-C's copper):

```powershell
$env:PYTHONPATH = "tools"; $g = Join-Path $HOME "krs-gates"
& .venv\Scripts\python.exe -X utf8 -c "import p3; from pathlib import Path; p3.refit_record(p3.enter(Path(r'$g')), ('p3-ifa2g4-<c>-mur-run', 'p3-ifa2g4-<c>-n2-run'), [{'step': 'matching run, 2026-10-30', 'pool': 4, 'cells': None, 'f_pml': 0.434, 'node_mcs': 35.5, 'cal_mcs': 205.6}], Path('docs/validation/<date>-p3-refit'))"
```

  The extra row is the matching run's pool-4 point (`docs/validation/2026-10-30-antenna-matching-run.md` §3). r2 expects about 0.42 at a pool of 1 and 0.58 at a pool of 4, w kept; the record gives `<a>`, `<b>` and `<w>`.
- [ ] **Step 6: Write the product's failing tests.** `tests/test_cost_model.py`: `def test_the_small_speed_is_its_pool_levels()`: `runs.small_speed(1) == runs.SMALL_SPEED[1] == <a>`, `runs.small_speed(4) == runs.SMALL_SPEED[4] == <b>`, `runs.small_speed(2) == runs.small_speed(3) == <a>` (the nearest lower measured level), `runs.small_speed(8) == <b>`; and `test_an_antennas_cost_splits_its_cells_and_weights_the_pml`'s `"ratio"` reads `f"{<a>:g}"`, its `"weight"` `f"{<w>:g}"`, and its `step` `(1728 + <w> * 25272) / (100.0 * <a> * 1e6)`.
- [ ] **Step 7: Run them.** `.venv/Scripts/python -m pytest tests/test_cost_model.py -q`. Expected: FAIL (`SMALL_SPEED` a float, no `small_speed`).
- [ ] **Step 8: The product.**
  - `runs.py`: `PML_WEIGHT` the record's w; `SMALL_SPEED = {1: <a>, 4: <b>}`, its comment citing gate P3-A and `docs/validation/<date>-p3-refit.md`, the old ponytail replaced by `# ponytail: unmeasured levels (2, 3) take the nearest lower measured one, which predicts longer`; `small_speed(pool)`: `SMALL_SPEED[max(k for k in SMALL_SPEED if k <= pool)]`.
  - `cost_notes`: `per_job_mcs * runs.small_speed(pool)`, and I_COST_SPLIT's `ratio` that value. `tools/p3.py`'s `predicted_s` reads `runs.small_speed(pool)`.
  - The message, through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_COST_SPLIT | Cells: {board} M in the board, {air} M of air and {pml} M of PML; the time counts a PML cell as {weight} cells and runs this model at {ratio} × the calibrated speed for that many jobs at once (gates P3-A and P3-C). | Células: {board} M na placa, {air} M de ar e {pml} M de PML; o tempo conta uma célula de PML como {weight} células e executa este modelo a {ratio} × a velocidade calibrada para esse número de tarefas simultâneas (checagens prévias P3-A e P3-C). |

- [ ] **Step 9: Run them again.** `.venv/Scripts/python -m pytest tests/test_cost_model.py tests/test_p3.py tests/test_golden_v1.py tests/test_sexpr.py tests/test_antenna_model.py -q`. Expected: PASS; v1's cost lines unchanged (the correction is antenna-only).
- [ ] **Step 10: Full suite, commit, graph.**

```bash
git add tools/p3.py tests src po docs/validation
git commit -m "feat(cost): an antenna's small-model speed by pool level, refitted from gates P3-B to P3-E (Stage 3 design 5.9)"
graphify update .
```

---

### Task 13 [decision]: The defaults P3-C set and the thresholds P3-D set

**Files:**
- Modify (by the reports' decisions): `src/kicad_rf_studio/core/post/antenna.py`; `core/project.py`; `cli.py`; `pipeline.py` (`gate_lines`, the n 3 branch only); `core/geometry/__init__.py` (W_AIR_BOX's rule); `core/geometry/region.py`; `stoprule.py`; `core/mesh/rule.py` (a comment); `core/messages.py`; `po/*`, the `.mo`; `tests/test_post_antenna.py`, `tests/test_project.py`, `tests/test_cli_antenna.py`, `tests/test_stoprule.py`, `tests/test_antenna_model.py`, `tests/test_antenna_geometry.py`, and on the n 3 branch `tests/test_cli_cost.py` and `tests/test_run.py`.

**Interfaces:**
- Produces: `ANTENNA_BOUNDARY` ("pml_8", or "mur" on that branch), and only where a gate changed the default `ANTENNA_MESH_N`, `ANTENNA_PRESET`, `ANTENNA_GATES` and `default_gates(data: dict) -> dict` (`core/project.py`), `T_MAX_PERIODS` (`cli.py`), `GAP_FRACTION` (`core/geometry/region.py`); `SHIFT_LIMIT`, `DB_LIMIT` (and `BW_LIMIT` only when P3-D needs it).

- [ ] **Step 1: Write the failing tests,** one per decision the reports took, before its change:
  - **Always:** `tests/test_post_antenna.py`: `SHIFT_LIMIT, DB_LIMIT == <P3-D's shift_rel, db>`; `delta_lines`' last line renders the new I_COMPARE_THRESHOLDS with `{"shift_pct": f"{100 * SHIFT_LIMIT:g}", "db": f"{DB_LIMIT:g}"}`; re-pin `test_the_deltas_and_whether_each_is_resolved`'s `7.32525` and `0.2` and `test_the_delta_lines_and_csv`'s `"0.3"` and `"0.2"` only when the values changed. `tests/test_antenna_geometry.py:80` pins W_AIR_BOX's params `{"gap_mm": "20.0", "boundary": "mur", "tested": "pml_8", "fraction": "λ/4", "default_mm": "31.2"}` (the tested setting on this branch); `tests/test_cli_antenna.py:36`'s I_ANTENNA_DEFAULTS renders the text without "(provisional default)".
  - **BW_LIMIT needed:** `deltas`' `bandwidth_10db` row's threshold is `BW_LIMIT * f0 / 1e6`, the resonance row's still `SHIFT_LIMIT`'s; `delta_lines` ends with I_COMPARE_BW_THRESHOLD after I_COMPARE_THRESHOLDS.
  - **mesh_n 3:** `new --antenna` writes `mesh.n` 3 and gates `{"fit2d_limit": 0.05, "dt_floor": 0.8}` at the Normal preset, and its `cost` prints no W_GATE_LIMITS, while an antenna at n 2 with 0.05 and a v1 project with 0.05 still do (`tests/test_cli_cost.py:296` and `tests/test_run.py:243` render it with `fit2d_default="0.03"` and `dt_floor_default="0.8"`); `new` of v1 still writes `MESH_N["normal"]` 2 and GATES (`tests/test_golden_v1.py` green); re-pin, where a test builds the default antenna, `model.mesh.d == 0.3` (0.2), the [135, 137, 71] line counts (n 3's) and I_ANTENNA_DEFAULTS' `mesh_n`.
  - **gap_factor 2:** `air_gap(2.4e9) == 62.456762`; W_AIR_BOX absent at λ/2 and present at λ/4 (`"fraction": "λ/2"`); re-pin `tests/test_antenna_model.py:28–29`'s 31.228381, `tests/test_project.py:225` and I_ANTENNA_DEFAULTS' `air_gap_mm` ("62.5").
  - **copper sheet:** `antenna_dict()["copper"] == "sheet"`; re-pin `tests/test_antenna_model.py:31`'s [135, 137, 71] (135 × 137 × 69), `:53`'s MUR [119, 121, 55] ([119, 121, 53]) and the pi's far-field centre z 0.39 (0.355).
  - **preset strict:** `new --antenna` writes preset "strict" and `ANTENNA_MESH_N` (2 unless n 3 is decided too), not `MESH_N["strict"]`.
  - **boundary mur:** `new --antenna` writes boundary "mur" and the λ/2 gap; W_AIR_BOX silent there, and present for a MUR λ/4 project and for a PML_8 one (`"tested": "mur"`).
  - **t_max raised to K periods:** `new --antenna` on ifa2g4 writes `t_max_s` = ceil to a whole ns of 2·t0 + K/f0, K from P3C-3; re-pin I_ANTENNA_DEFAULTS' `t_max_ns`.
  - **flat widened:** `flat_window(2.44175e9) == max(5e-9, 40 / 2.44175e9)`, re-pinning `tests/test_antenna_model.py:43`'s `8.19085e-9` and `tests/test_stoprule.py`'s `test_an_antennas_flat_window_counts_20_periods_of_f0` (renamed to 40).
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_antenna.py tests/test_project.py tests/test_cli_antenna.py tests/test_stoprule.py tests/test_antenna_model.py tests/test_antenna_geometry.py -q` (plus `tests/test_cli_cost.py tests/test_run.py` on the n 3 branch). Expected: FAIL on each decision's test.
- [ ] **Step 3: The changes,** each antenna-only, v1's constants untouched:
  - **Always:** `core/post/antenna.py`: `SHIFT_LIMIT, DB_LIMIT = <shift_rel>, <db>` commented "gate P3-D (`docs/validation/<date>-p3-d.md`): three times the model's measured noise floor, never below the design's 0.3 % and 0.2 dB", in place of the provisional ponytail; `dip_resonance`'s ponytail states P3-D's screen result ("P3-D: depth noise <x> dB, every compared dip at least <y> dB under −6 dB; still a depth screen, which a broad −7 dB minimum passes"). `core/project.py`: `ANTENNA_BOUNDARY = "pml_8"`, which `make_antenna_project` writes. `build_geometry`'s W_AIR_BOX: `project["boundary"] != ANTENNA_BOUNDARY or gap < air_gap(f_lo)`, params `gap_mm`, `boundary`, `tested` (ANTENNA_BOUNDARY), `fraction` (`f"λ/{GAP_FRACTION}"`, "λ/4" until a gap change) and `default_mm`. `tests/test_antenna_model.py:52`'s "provisional" comment states P3-C's result.
  - BW_LIMIT, only when P3-D's `bw_rel` is not None: `BW_LIMIT = <bw_rel>` beside the others, `deltas`' bandwidth row judged at `BW_LIMIT * f0`, and `delta_lines` appends I_COMPARE_BW_THRESHOLD; else its ponytail stays.
  - mesh_n 3: `ANTENNA_MESH_N = 3` and `ANTENNA_GATES = {"fit2d_limit": 0.05, "dt_floor": 0.8}` in `core/project.py`, with ruling 2's cause; `default_gates(data)`: ANTENNA_GATES for an antenna at mesh n ≥ 3, else GATES; `make_antenna_project` writes `mesh.n` ANTENNA_MESH_N and `gates` `dict(default_gates(...))`; `pipeline.gate_lines(gates, default)` at each of its six callers with `default_gates(project)`, and W_GATE_LIMITS names the default.
  - gap_factor 2: `GAP_FRACTION = 2` in `core/geometry/region.py`, `air_gap` is λ/GAP_FRACTION at f_lo.
  - copper sheet: `ANTENNA_COPPER = "sheet"`.
  - preset strict: `ANTENNA_PRESET = "strict"`, `new_antenna`'s default, and `ANTENNA_MESH_N` (2 unless n 3) in `make_antenna_project`'s `mesh.n`.
  - boundary mur: `ANTENNA_BOUNDARY = "mur"` with `GAP_FRACTION = 2`.
  - t_max: `T_MAX_PERIODS = <K>` in `cli.py` in place of the inline 60.
  - flat: `FLAT_PERIODS = 40` in `stoprule.py` (antenna-only already). Every antenna project without its own `flat_s` then reads stale (its spec's flat_s changes), `<GATES>`' included, so plan 5's acceptance reruns its pair.
  - `core/mesh/rule.py`, at `_patterns`' shared-cell rule, a comment only: `# ponytail: a narrow pad in line with a wider feed (an inverted-F's 0.5 mm feed pad on its 0.6 mm stub) shares one cell with the feed's edge 48 µm away, so the stub reads Z0 4-5 % high at mesh n 3 and 4 (gate P3-C, ruling 2: at most 0.06 % on f_res); E→W for sections under λg(f2)/20, or exempting the non-cut edge from the lint, if users meet it`.
- [ ] **Step 4: The messages,** through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_COMPARE_THRESHOLDS | Resolved means larger than the significance threshold: {shift_pct} % of f0 for a frequency and {db} dB for an efficiency or a gain, set by gate P3-D at three times the model's measured noise floor and never below 0.3 % and 0.2 dB. | Resolvido significa maior que o limiar de significância: {shift_pct} % de f0 para uma frequência e {db} dB para uma eficiência ou um ganho, definidos pela checagem prévia P3-D em três vezes o piso de ruído medido do modelo e nunca abaixo de 0.3 % e 0.2 dB. |
| W_AIR_BOX | The antenna's air box is outside the tested setting: an air gap of {gap_mm} mm to a {boundary} absorber, where gate P3-C tested {tested} with a gap of {fraction} at f_lo ({default_mm} mm) or more. | A caixa de ar da antena está fora da configuração testada: espaçamento de ar de {gap_mm} mm até um absorvedor {boundary}, enquanto a checagem prévia P3-C testou {tested} com um espaçamento de {fraction} em f_lo ({default_mm} mm) ou mais. |
| I_ANTENNA_DEFAULTS | Preset {preset}, T_max {t_max_ns} ns (2·t0 + 60/f0), mesh n {mesh_n}, measured region {expand_h} substrate heights past the antenna and the chain, protected reach {reach_h} substrate heights, air gap {air_gap_mm} mm (λ/4 at f_lo) to a {boundary} absorber, far-field frequencies: {count}, on a {step_deg}° sphere. | Predefinição {preset}, T_max {t_max_ns} ns (2·t0 + 60/f0), malha n {mesh_n}, região medida de {expand_h} alturas de substrato além da antena e da cadeia, alcance protegido de {reach_h} alturas de substrato, espaçamento de ar de {air_gap_mm} mm (λ/4 em f_lo) até um absorvedor {boundary}, frequências do campo distante: {count}, numa esfera de {step_deg}°. |
| I_COMPARE_BW_THRESHOLD (BW branch) | A change of the -10 dB bandwidth is resolved above {bw_pct} % of f0, set by gate P3-D at three times its measured noise on a minimum {depth_db} dB deep; the noise grows as a minimum gets shallower. | Uma mudança da largura de banda a -10 dB é resolvida acima de {bw_pct} % de f0, definida pela checagem prévia P3-D em três vezes o ruído medido dela num mínimo de {depth_db} dB; o ruído cresce quando o mínimo fica mais raso. |
| W_GATE_LIMITS (n 3 branch) | project.json sets gates.fit2d_limit {fit2d_limit} and gates.dt_floor {dt_floor}, not {fit2d_default} and {dt_floor_default}, so this verdict is outside the validated limits. Set them back to {fit2d_default} and {dt_floor_default} for a validated result. | O project.json define gates.fit2d_limit {fit2d_limit} e gates.dt_floor {dt_floor}, não {fit2d_default} e {dt_floor_default}, então este veredito está fora dos limites validados. Volte-os para {fit2d_default} e {dt_floor_default} para ter um resultado validado. |

  With gap_factor 2, I_ANTENNA_DEFAULTS' "(λ/4 at f_lo)" reads "(λ/2 at f_lo)" ("(λ/2 em f_lo)"); with T_MAX_PERIODS K, its "(2·t0 + 60/f0)" reads K in both. W_GATE_LIMITS' v1 rendering is unchanged (defaults "0.03" and "0.8").
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_sexpr.py tests/test_compare.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(antenna): the defaults gate P3-C set and the significance thresholds gate P3-D set, antenna-only (Stage 3 design 5.4, 5.8, 5.11)"
graphify update .
```

---

### Task 14 [decision]: The amendments, the design's wording and the close

- [ ] **Step 1: The amendments,** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, each bracketed choice the reports' decision:
  - **A-35, §5.3 and §5.4** (and §5.5 on the n 3 branch). §5.3, a bullet after "Dielectric loss": "- **Antennas** (Stage 3): an antenna project's `copper` is "solid", this section's copper, or "sheet": every copper layer a zero-thickness PEC sheet at its dielectric face, the masks resting on it, for the whole model. Gate P3-C compared them on both fixtures at mesh n 2: sheet [passed, within 0.5 % in resonance and 0.1 dB in radiation efficiency, and is the antenna default | failed and is not offered]; openEMS's timestep is <r> times solid's (<dt_sheet> against <dt_solid> s on the 2.4 GHz fixture), since the rule keeps a d/3 cell beside the sheet (`docs/validation/<date>-p3-c.md`). Both fixtures' feeds keep their ground 1 mm away; on a feed whose coplanar gap is under 30·t this section's evidence (a sheet read Z0 8.7 % high on a 50 Ω GCPW) still holds, and the owner decides whether such feeds keep solid copper. (A-35, Stage 3 plan 4: controller recommendation, owner unavailable.)" §5.4, a bullet: "- **Antennas** (Stage 3): the antenna's mesh n is [2, within 1 % of the resonance extrapolated at the observed order capped at 1 on both fixtures, so the cell d taken from the feed network alone stands | 3, as n 2 missed 1 % of the extrapolated resonance]; the copper models were compared at n 2. At n 3 and 4 the 2.4 GHz fixture's 0.6 mm stub reads 4–5 % high from a shared edge cell, at most 0.06 % on the resonance, [and its P3-C runs set gates.fit2d_limit 0.05 | so an antenna at mesh n 3 or more defaults to a fit2d limit of 5 % (§5.5)]. (A-35, …)" On the n 3 branch, §5.5's fit2d bullet gains: "An antenna at mesh n 3 or more defaults to a limit of 5 %, the shared edge cell of a narrow pad in line with a wider feed being the rule's own, and W_GATE_LIMITS measures its gates against that (gate P3-C, A-35)."
  - **A-36, §5.1,** after A-27's bullet: "- **The antenna's absorber** (Stage 3): gate P3-C ran PML_8 free to max(T_max, 3 × the stop time) on both fixtures with [no energy rise above 6 dB | a rise of <X> dB on <fixture>, so MUR at λ/2 is the antenna default]; MUR at λ/2 ran on the 2.4 GHz fixture free to 3 × T_max (90 ns) and rose <Z> dB [, and on the 915 MHz fixture to <t> ns, rising <W> dB]; the air gap is [λ/4: λ/2 moved the resonance by at most 0.2 %, D by 0.2 dB and the radiation efficiency by 0.1 dB | λ/2, as λ/4 missed those limits] (`docs/validation/<date>-p3-c.md`). (A-36, Stage 3 plan 4: controller recommendation, owner unavailable.)"
  - **A-37, §6.3,** A-28's paragraph gains: "Gate P3-C measured the stop times: [both kept: every compared run converged before T_max, and none ended flat | T_max is 2·t0 + <K>/f0, since the <fixture> rang to it, raised from its decay with a 1.5 margin | the flat window is 40 periods of f0]; an antenna's project.json may set `flat_s`, its flat window in s, which P3-C used to rerun a run that ended flat; the Normal preset matched Strict within 0.1 % and 0.05 dB [| failed it, so Strict is the antenna's preset, at the antenna's own mesh n] (`docs/validation/<date>-p3-c.md`). (A-37, Stage 3 plan 4: controller recommendation, owner unavailable.)"
  - **A-38, §6.4,** A-29's bullet: "0.384 times the calibration's own one-job speed" becomes "the small-model speed of its pool level, <a> at one job and <b> at four (an unmeasured level takes the nearest lower one), times the calibration's per-job speed at that level", and "they stay provisional until gate P3-C refits them" becomes "gates P3-B to P3-E's runs refitted them, the PML weight [kept | <w>] as its like-for-like MUR pair measured it, the pool-1 line a cross-check (`docs/validation/<date>-p3-refit.md`) (A-38, Stage 3 plan 4: controller recommendation, owner unavailable.)".
  - **A-39, §3.2,** A-34's paragraph: "each resolved above 0.3 % of f0 for a frequency or 0.2 dB for an efficiency or a gain, until gate P3-D sets them" becomes "each resolved above <shift> % of f0 for a frequency or <db> dB for an efficiency or a gain [, and the −10 dB bandwidth's change above <bw> % of f0, measured on a minimum <depth> dB deep], which gate P3-D set at three times the model's measured noise floor and never below 0.3 % and 0.2 dB (`docs/validation/<date>-p3-d.md`); gate P3-E's ground pour inside the antenna's clearance shifted the resonance by <Δ> %, [resolved | not resolved at the first thresholds, so P3-D was refined at mesh n <n>, and P3-E then <its result>] (A-39, Stage 3 plan 4: controller recommendation, owner unavailable.)".
  - **A-40, §9.9,** a new section after §9.8: "### 9.9 P3-B to P3-E (Stage 3)" with "Gates P3-B to P3-E (Stage 3 design §5.11), run by `tools/p3b.py`, `tools/p3c.py` and `tools/p3d.py` through the product's CLI in one gates folder, each against criteria committed before its runs (`tests/fixtures/p3b/criteria.json`, `tests/fixtures/p3c/criteria.json`, `tests/fixtures/p3d/criteria.json`). **P3-B** compares the 2.4 GHz fixture through `new` and `run` with an openEMS model of the same board written by hand (`tools/p3b_hand.py`: MUR at λ/2, its own mesh, a lumped port across the radio pads' gap), its reference `tests/fixtures/p3b/references.json` committed before the product's side ran: f_res within 1 % (a miss on a minimum shallower than −6 dB or at the grid's end is explained when |ΔS11| in band stays within what a 1 % shift of the hand's S11 makes there), D_max and η_rad within 0.3 dB, the hand run ended by its criterion or decayed 40 dB and the product's converged; a fail blocks until a pre-registered diagnosis (the product with MUR at λ/2, the hand at 0.30 mm) explains it; result <verdict>. **P3-C** runs both fixtures at mesh n 2/3/4, a λ/4 and a λ/2 air gap, Normal and Strict, free to max(T_max, 3 × the stop time), and solid against sheet copper: n 2 within 1 % of the extrapolated resonance, the gap within 0.2 %, 0.2 dB and 0.1 dB, Strict within 0.1 % and 0.05 dB, sheet within 0.5 % and 0.1 dB on both fixtures, the free runs' energy rising at most 6 dB; each failed check raises its antenna default, as A-35 to A-37 record; result <verdict>. **P3-D** measures the noise floor on the pi variant verified at <values>: the same verify twice, the board shifted by one fine cell and its front end moved by ± one fine cell, the ± moves within 0.2 % of f0 and 0.1 dB in η; the thresholds are three times the largest noise, never below the design's (A-39); result <verdict>. **P3-E** compares a ground pour inside the clearance against the base: its resonance shift resolved, else P3-D refined once and P3-E judged again; result <verdict>. **P3-F**, EMerge as a second solver, stays the owner's. The reports are `docs/validation/<date>-p3-{b,c,d,e}.md`, and the cost refit's `docs/validation/<date>-p3-refit.md`; machine time <h> h against this plan's 20–82 h (up to about 95 h on the T_max branch). (A-40, Stage 3 plan 4: controller recommendation, owner unavailable.)"
  - **The Status line** gains at its end: " On <date>, Stage 3's plan 4 amended §3.2, §5.1, §5.3, §5.4[, §5.5], §6.3, §6.4 and §9 (A-35 to A-40) the same way."
- [ ] **Step 2: The design's wording,** `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md`:
  - §1: "all-sheet copper, if gate P3-C allows it (§5.3), cuts that 5–6 times" becomes "all-sheet copper cuts the timestep about <r> times (gate P3-C: [adopted | not offered])"; the runtime sentence gains "measured: one 2.4 GHz job 25 min, `docs/validation/2026-10-30-antenna-first-run.md`".
  - §5.2: the air gap "is λ/4 at f_lo by default" becomes "is [λ/4 | λ/2] at f_lo by default (gate P3-C, A-36)"; "MUR on all six faces stays a project option, the fallback if a gate finds PML_8 unstable (§5.11)" becomes "[MUR on all six faces stays a project option: gate P3-C found PML_8 stable and measured MUR at λ/2 as evidence | MUR on all six faces at λ/2 is the antenna default: gate P3-C found PML_8 unstable] (A-36)".
  - §5.3's last copper bullet ends: "Gate P3-C [adopted all-sheet copper, validated on feeds whose ground keeps 1 mm away | kept solid copper] (A-35)."; §5.4's "Gate P3-C revisits both" becomes "Gate P3-C [kept both | <the change>] (A-37)."; §5.8's "until gate P3-D measures the noise floor and sets them at three times it" becomes "set by gate P3-D at <shift> % and <db> dB (A-39)"; §5.9's last sentence becomes "Gate P3-C refitted the small-model speed by pool level and [kept | refitted] the PML weight (A-38).".
  - §7: "Sheet copper for antennas", "The boundary" and "Runtime" carry the gates' results in place of "only if P3-C allows it" and "if a gate finds".
  - Its Status line: "Amended on <date> by Stage 3's plan 4 with the gates' results (P3-B to P3-E, `docs/validation/<date>-p3-*.md`)."
- [ ] **Step 3: Commit.** The full suite, `git add docs/superpowers/specs`, `git commit -m "docs(spec): Stage 1 spec A-35 to A-40 and the Stage 3 design's wording from gates P3-B to P3-E (Stage 3 design 5.13; controller recommendation, owner unavailable)"`, `graphify update .`.
- [ ] **Step 4: The suite in both languages:** the full suite in the background, then `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass; record the counts in the ledger.
- [ ] **Step 5: Close.** The whole-branch review; Step 4 again after any later commit; fast-forward `main` locally; delete the branch; delete `$env:TEMP\krs-plan4-sheet`. Nothing is pushed. `<GATES>` stays until the Stage 3 exit record (Task 11).

---

## Not in this plan

- **P3-F, EMerge as a second solver:** the owner's (design §5.11, §5.14 item 2), recorded in A-40.
- **Plan 5:** the GUI (New's antenna kind, Results, Advanced, Compare), the KiCad button, the README tutorial on the 2.4 GHz fixture, the release check, the acceptance run (design §5.14 item 3: a compare against the ground-pour variant verified at the same values, which Task 7's `ifa2g4_pi_pour` and Task 11's projects serve) and the Stage 3 exit record.
- **Deferred by the design:** the instant far-field retune by superposition (design §3, §7).
- **A matched M = 0 2.4 GHz fixture:** ruling 1; P3-D and P3-E run on the pi variant, whose verify dips to −12.5 dB.
- **A product fix for the pad-in-line fit2d conflict:** a comment in Task 13 and an owner item (r2 Q1); ruling 2's limit covers the gates. Plan 2's open issue 3, AE1 alone moved by 0.1, −0.1 or 0.37 mm reading E_FIT2D 3.9–4.8 % at n 2, is the same conflict: a user who meets it raises `gates.fit2d_limit`, as E_FIT2D's advice says, at their own risk.
- **Sheet copper on a narrow coplanar feed:** neither fixture has one, so P3-C cannot test it; A-35 states the scope, and an owner item asks for solid copper where a feed's gap is under 30·t, or a W_ line from a solid-copper fit2d solve.
- **The losing copper at mesh n 3:** if P3-C sets n 3, A-35 says the copper models were compared at n 2.
- **All threads for a lone job** (plan 2's item): this PC's calibration ran one job at 16 threads slower than at 4 (320.6 against 580.2 MC/s), so no calibration level is added.
- **A keep-awake call and `p0.machine`'s start date** (r4): the sleep timeout is 0 and a reboot loses one step either way; the reports state that `elapsed_days` counts from P0's start, as P3-A's did.
- **Pool-4 batching of single-job runs** (r2, r4): one openEMS command at a time keeps the timings clean.
- **Deleting `<GATES>`:** after the Stage 3 exit record, on the controller's go.

## Controller rulings (2026-10-30; binding)

The controller's eleven rulings stand as given; the architect's follow, revised after the four reviews. Each is a controller recommendation made while the owner is unavailable.

- Ruling 1 (the controller's): no new matched fixture. P3-B and P3-C run on ifa2g4 (M = 0); the gates' f_res is the refined lowest |S11| over the simulated band, with its depth and a "conditioned" flag; an f_res miss on an unconditioned minimum is explained by max |ΔS11| over [f_lo, f_hi] within its shift-equivalent (amended at commit from 0.05; D and η_rad binding); P3-D and P3-E run on ifa2g4_pi at L1=0R C2=0.13pF C3=1pF, each configuration run, retuned and verified — the shallow −5.9 dB minimum, r1, r3 — cost if wrong: about 9 h of reruns on a new fixture.
- Ruling 2 (the controller's): E_FIT2D_FINE at n 3 and 4 on ifa2g4 is r2's mesh-line conflict; those projects set `gates.fit2d_limit` 0.05, recorded in P3-C's report; no code change — r2 Q1 — cost if wrong: a product fix later.
- Ruling 3 (the controller's): the antenna-only `copper` field, "solid" by default or "sheet", validated, built and fingerprinted; adopted only by P3-C's criteria; about 2 times faster — r2 Q2 — cost if wrong: one field.
- Ruling 4 (the controller's): P3-C's free run goes to max(T_max, 3 × the measured stop time) on `p3a._free`, its growth judged as P3-A's — r4 — cost if wrong: about 13 h more on the meander.
- Ruling 5 (the controller's): MUR at λ/2 runs once on the 2.4 GHz fixture, report-only; the default only on PML instability — r4 — cost if wrong: about 0.5 h.
- Ruling 6 (the controller's): PML_WEIGHT stays 6.38 unless P3-C's data move it; SMALL_SPEED becomes one value per pool level, fitted after the runs (Task 12) — r2 Q5 — cost if wrong: cost lines off by their level's error.
- Ruling 7 (the controller's): the shared `tools/p3.py`, one tool per gate, the hand model in a module that imports none of the product (an AST test), decide() unit-tested, criteria before runs, P3-B's reference between the hand run and the product's side, reports with machine time, `<GATES>` by `--out`, src frozen during the runs — r4 — cost if wrong: harness rework.
- Ruling 8 (the controller's): the variants `ifa2g4_pi_dxp`, `_dxm`, `_shift` and `_pour` from `tools/make_fixtures.py` under KiCad 9's Python, only the named boards, each with a load-and-build test — r3 — cost if wrong: one regeneration.
- Ruling 9 (the controller's): the schedule in blocks with checkpoints, cheap and decisive runs first, one openEMS command at a time; about 20, 33 or up to 82 machine hours; the meander's T_max raised from its decay if it rings, its n 4 dropped, extrapolating with the 2.4 GHz fixture's order — r4 — cost if wrong: hours.
- Ruling 10 (the controller's): the thresholds after P3-D are max(the design's default, 3 × the largest measured noise); P3-E is judged with them; compare's lines lose "provisional" — r3 Q5 — cost if wrong: a threshold a reader trusts too much or too little.
- Ruling 11 (the controller's): each default a gate changes lands after the runs as an antenna-only constant with its amendment and the design's wording — design §5.13 — cost if wrong: a paragraph moved.
- Ruling: the task order — the runner, the copper field and flat window, the hand model, P3-B's gate, P3-C's steps, P3-C's rules, the fixtures, P3-D's gate, then the runs B, C, D and E, then the refit, the defaults and the amendments. Every [code] task lands before any run, so src freezes once; P3-B runs first because an import, mesh or port bug would void every later run — r1, r4 — cost if wrong: a reorder.
- Ruling: P3-C's steps and its rules are two tasks, each with its own commit, since a reviewer can approve the variants and reject the statistics — review — cost if wrong: one more review.
- Ruling: each gate's criteria JSON lands in its own tool's first task (Tasks 4, 5, 8), all before every run; a pre-registered branch is taken through a tools constant (`p3c.RAISED`, `p3d.VALUES`, `p3d.REFINE`), recorded as a deviation, never by editing the criteria — ponytail, criteria before runs — cost if wrong: none.
- Ruling: one pair rule (`p3.pair`) serves P3-B and P3-C: f_res and depth by `resonance` on each side's S11, conditioned when both argmins lie inside the grid at or below −6 dB (`dip_resonance`'s screen), ds11 over [f_lo, f_hi] against its shift-equivalent (amended at commit), D at f0, η_rad's worst over the recorded frequencies; Python floats and bools — review: two copies of one rule drift, and an edge minimum is no dip — cost if wrong: none.
- Ruling (amended at commit): ruling 1's explanation applies to every P3-C f_res comparison, each against its own shift-equivalent, the largest |ΔS11| that shifting the reference's S11 by the check's limit makes in band (1 % for P3-B and the mesh check, 0.5 % for copper, 0.2 % for the gap, 0.1 % for the preset); the mesh check's |ΔS11| is against the S11 extrapolated pointwise at the same order; each explained check is reported with its |ΔS11| and its threshold — the ill-conditioned minimum is the fixture's, and the draft's 0.05, scaled with each limit, explained only curves within about 0.36 times each check's limit on ifa2g4 (physics review) — cost if wrong: a default kept that a stricter reading would raise.
- Ruling: P3-C's "Δη" is η_rad at the worst of the 11 recorded frequencies, binding, with η_tot reported; D is judged at f0 — η_tot carries the mismatch, which any resonance shift moves; r2 Q3 and P3-A's precedent — cost if wrong: a mismatch change unjudged, which the f_res check covers.
- Ruling (replaces the architect's order-1 ruling): n 2 is judged against the f_res extrapolated at the observed order p, solved from R = (f3 − f2)/(f4 − f3), capped at 1 (order 1 exactly when R ≥ 2); R ≤ ln(3/2)/ln(4/3) with steps of one sign is "not converging", a fail; a sign change or a zero step is "oscillating", judged against the finest; with n 4 dropped, n 2 and n 3 at the 2.4 GHz fixture's observed order capped at 1, as ruling 9 words it — order 1 is the conservative end only at p ≥ 1, and at p = 0.5 it reads 62 % of n 2's error (physics review) — cost if wrong: n 3 adopted where order 2 would keep n 2, about 1.5 times the machine time of every antenna run.
- Ruling: "Normal against the Strict preset" is the stop rule's preset alone at mesh n 2 (`new --preset strict` would also write n 3, which the mesh check judges) — r2's trap — cost if wrong: one run.
- Ruling: a P3-C comparison that reads a run not converged is not judged and keeps the verdict "incomplete"; a run that ended at T_max or flat reruns with `p3c.RAISED[fixture]`'s `t_max_s` or `flat_s`, every step of that fixture with it, and the decision records the raise — design §5.4 ("P3-C revisits both"), RF 4 — cost if wrong: hours of reruns.
- Ruling: `flat_s` is an optional antenna field (seconds), absent meaning FLAT_PERIODS/f0, read by `excitation` and named in the fingerprint only when set, so that a flat run reruns as a project edit while src is frozen — the flat window was code, so P3-C could not finish on that branch (coverage review) — cost if wrong: one field.
- Ruling: T_max is raised from the residual's decay over `t_max_fit_s` of I_PROGRESS events, projected to the preset's level (`stoprule.PRESETS`), times `t_max_margin`, rounded up to a whole ns; the antenna's K = ceil((T_raised − 2·t0)·f0) at that fixture's f0, given in P3C-3 and used in Task 13; the flat window widens to 40 periods — design §5.4, ruling 9 — cost if wrong: worst-case time only, as a converged run stops at its verdict.
- Ruling: P3-C's steps are named `<fixture>-<copper>-<setting>`, both coppers defined, and the blocks after CP3 run the winning copper's, read from the interim report, so no run on the losing copper is mistaken for the winner's — ponytail — cost if wrong: none.
- Ruling: the fit2d raise is ifa2g4's at n ≥ 3 in both coppers, nowhere else: the architect's probe found the meander passing at n 2, 3 and 4 in both coppers; each raised variant's report carries every section's fit2d (`fit2d_probe`), RF's 0.6 mm section within 5 % and the 1.35 mm section within 3 % — ruling 2, the probe, r2 — cost if wrong: a blocked step (exit 3), visible at once.
- Ruling: ifa2g4's MUR free run goes to 3 × T_max (90 ns, P3-A's window, where its MUR twin rose 16 dB), since 30 ns cannot show that failure and a pass makes MUR the default on any PML failure; when the meander's PML fails, MUR becomes the default only after the meander's own MUR λ/2 run and free run (to its PML free run's length) pass, else "blocked" — ruling 4 binds the PML check, not this run (physics review) — cost if wrong: about 0.7 h, and 2 h on that branch.
- Ruling: sheet copper is a z-stack whose copper layers have no thickness; `model_spec` writes the antenna-only key `"copper": "sheet"` and, only then, leaves out materials of no thickness, and `csx._prism` draws a solid of no thickness as a polygon only with that key; the mesh, fit2d (sheet against a sheet reference) and the ports follow from the stack. v1 never reaches the branch: a v1 stackup with 0 mm copper, which builds today with zero-thickness mask fills, keeps them (a test) — the reviser's probe of lpf915 — cost if wrong: Task 9 Step 1's real cost, run, retune and verify catch a setup failure before any gate run.
- Ruling: `copper` is optional in schema 2 (absent reads solid) and `new` writes it; no cost line names it: the fingerprint and model.json's key record it, so a pre-plan-4 event still renders and no message changes twice (quality and feasibility reviews) — ponytail — cost if wrong: one parameter added later.
- Ruling: if all-sheet fails, "not offered" means `new` keeps writing solid and plan 5's GUI does not list sheet; the field and its branch stay — ponytail — cost if wrong: a refusal added later.
- Ruling: sheet copper's scope is the fixtures' feeds, whose ground keeps 1 mm away; on a coplanar gap under 30·t Stage 1 §5.3's 8.7 % GCPW reading still holds; A-35, §5.3 and §7 say so, and the owner decides whether such feeds keep solid copper — physics review — cost if wrong: a user's narrow-gap feed read a few % high in Z0.
- Ruling: P3-B's hand model is r1's, frozen before its run: the 12 rectangles and the tracks transcribed, the pads from pads.json, the F.Cu fill rebuilt by its rule, the 35 vias by one regex and AE1.2's plated hole (the IFA's short, whose barrel the product builds too), solid 35 µm copper, the mask smeared over 0.1 mm, MUR at 62.456762 mm, 0.2 mm on the antenna and feed, 2.36 mm in the board and 5 mm in air by CSXCAD's own smoother, a Gaussian over 1.84–2.99 GHz, EndCriteria 1e-5 to 30 ns, 4 threads, the far-field centre in metres; its mesh test runs it in a child, so pytest's process never imports CSXCAD; its f_res is taken by the product's `resonance` on both sides, one definition — r1; the physics and feasibility reviews — cost if wrong: one hand run (27 min).
- Ruling: the hand run is valid when it ended by its criterion or its last 2 ns sit 40 dB or more under its peak (signed: a run that grew is no reference); otherwise it reruns once at λ/2 at f1 (81.465 mm, `hand-f1`), a deviation, whose run is the committed reference; a hand-f1 run that is not valid either stops for a ruling; P3-B's valid check also needs the product's job converged — r1 R2, RF 3 and 4 — cost if wrong: 30 min.
- Ruling: a P3-B fail is diagnosed by pre-registered pairs, in order: "boundary" when the product with MUR at λ/2 matches the hand, "mesh" when the hand at 0.30 mm matches the product, "boundary and mesh" when those two match each other, else "product bug presumed"; P3B-1 reports |ΔS11| beside its 1 % shift-equivalent, the explanation's threshold since the amendment at commit — design §5.11 ("blocks until explained"), physics review — cost if wrong: a miss explained by the wrong difference.
- Ruling: the product's side of P3-B is P3-C's ifa2g4 solid n 2 baseline, one step; P3-B's MUR diagnostic is the project `ifa2g4-solid-mur`, which P3-C's MUR step runs when solid copper wins — ruling 9 — cost if wrong: none.
- Ruling: step keys — a run by its model's hash and its preset (the preset is not in the spec); a verify by those and the part ports' values; a free run by its spec's hash and its length; P3-B's geometry by the hand module's hash and the product's model hash; every such key `@code_id` through `p0.step`; P3-B's hand runs are kept in their folders by the hand module's hash alone, outside `p0.step` — r1 (never rerun after a product fix), r4 — cost if wrong: a step rerun or wrongly reused.
- Ruling: every gate's report goes through `p3.records`, which refuses records of two product codes among the recorded steps, as `p0.records` does for a whole gate — the Global Constraints relied on a check no gate made (quality review) — cost if wrong: none.
- Ruling: the harness runs no `cost`; the predicted time, to t_stop and to T_max, is cost_notes' antenna formula in `p3.predicted_s`, which a test pins equal to cost_notes' own I_COST_PREDICTED and I_COST_TIME — ponytail, design §5.11 ("cost predicts each run first") — cost if wrong: none.
- Ruling: `p3.enter` refuses the real data folder and `kicad-rf-studio-p0*`, not TEMP, where the tests' folders live; TEMP is the run tasks' rule (`$HOME\krs-gates`) — ruling 7 — cost if wrong: none.
- Ruling: P3-D and P3-E take P3-C's 2.4 GHz edits from `p3c.json` (`edits_2g4`): copper always, mesh n with fit2d 0.05 at n 3 (the pi board reads 3.53 % there, r3), gap, preset, boundary; T_max and the flat window are left out, as they do not move a converged run's S — ponytail — cost if wrong: none.
- Ruling: "the antenna alone moved" is the front end (AE1, U1, the parts, their tracks and to_gnd vias) moved along x by ± d against a fixed ground, outline and fence; along y the clearance would change, a physical change; P3-D reports each quantity's odd part (sensitivity to position) and even part (discretization), and when the odd part dominates the report says the thresholds rest on position rather than noise, an owner item — r3 Q3, ruling 8, physics review — cost if wrong: two boards.
- Ruling: P3-D's "same run twice" is a second verify of a copy made after the base's first retune and retuned with it every time, since compare reads verify: one 30-minute job, not a 63-minute run — r3 Q1 — cost if wrong: one run.
- Ruling: the values are criteria's; when the base's verify dips above −6 dB they are re-searched once by plan 3 Task 9's search on the base's run and set in `p3d.VALUES` for every board; every verify's key holds the values, so a change reruns them all — the re-search could not otherwise reach p3d without editing criteria after a run (coverage review) — cost if wrong: one re-search.
- Ruling: a P3-D pair whose dips are not both at or below −6 dB stops for a ruling instead of entering the noise; P3-E needs the pour's dip conditioned too — plan 3's resonance screen — cost if wrong: a stop.
- Ruling: the thresholds round up to 0.05 % of f0 and 0.05 dB; BW_LIMIT is three times the bandwidth noise over f0, rounded up likewise, only when it exceeds the frequency threshold, with its own line naming the depth it was measured on; the −6 dB screen is kept unless a compared dip lies within three times the depth noise of it — r3 Q5, plan 3's handoffs, physics review — cost if wrong: one constant.
- Ruling: P3-E's fallback is pre-registered: refine means the next mesh n on the pi boards with fit2d 0.05, the moved boards regenerated at that n's d under `_r` names, every P3-D pair and the pour run again under `r-` names (`p3d.REFINE`), the thresholds by the same rule and P3-E judged once more; a second miss goes to the controller — design §5.11 and §5.14 item 2 (coverage review) — cost if wrong: about 10 h.
- Ruling: the refit reads its rows from the step records (`p3.rows`: each run and verify once, the free runs, the hand runs and the loaded steps left out), plus the matching run's pool-4 point; the small speed is each level's median; w is judged on the like-for-like ifa2g4 n 2 and MUR pair, P3-A's method, the pool-1 line a cross-check; w moves only beyond 25 %; levels 2 and 3 take level 1's, the lower one, which predicts longer; `SMALL_SPEED` has int keys; the result is its own record, `docs/validation/<date>-p3-refit.md`, which runs.py and A-38 cite — r2 Q5, the physics, coverage and quality reviews — cost if wrong: a pool-2 prediction off by its level's difference.
- Ruling: on the n 3 branch, an antenna at mesh n ≥ 3 defaults to a fit2d limit of 5 % (`ANTENNA_GATES`, `default_gates`), `gate_lines` compares a project's gates with its own default and W_GATE_LIMITS names it, and A-35 amends Stage 1 §5.5 — the 3 % limit would block the 2.4 GHz fixtures at the default, and a 5 % default would otherwise print W_GATE_LIMITS on every antenna output (feasibility review); it extends ruling 2, open issue 3 — cost if wrong: a looser fit2d gate on antenna feeds at n 3.
- Ruling: W_AIR_BOX warns when the air box is not the antenna's tested default, its boundary (`ANTENNA_BOUNDARY`) with a gap of λ/GAP_FRACTION at f_lo or more, and names that default, so the MUR and gap branches need no second text — coverage review — cost if wrong: one message.
- Ruling: r4's options left out: a keep-awake call (the sleep timeout is 0, and a reboot loses one step either way), `p0.machine`'s start date (the reports say elapsed_days counts from P0's start, as P3-A's did), pool-4 batching (one openEMS command at a time keeps the timings clean) — ponytail — cost if wrong: one function argument.
- Ruling: no new pt-BR term: plan 3's stand (piso de ruído, limiar de significância, checagem prévia), and "jobs at once" keeps the catalog's "tarefas simultâneas" — pt-BR design §6 — cost if wrong: a native speaker changes a few msgstrs.
- Ruling (disclosure): the architect's probes ran in a scratch folder with the repo's venv, in memory, no openEMS, no KiCad: the zero-thickness stack on ifa2g4, ifa2g4_pi and meander915 at n 2 (135 × 137 × 69, 135 × 143 × 69 and 216 × 153 × 77 lines; dt references 2.3057e-13, 2.4599e-13 and 2.2642e-13 s; nothing blocked); fit2d at n 3 and 4 in both coppers (ifa2g4 4.13, 4.76, 3.87 and 4.76 %; the meander none); the 12 rectangles against AE1's polygon (XOR 0.0687 mm²); the fixture's 53 polygon points, 35 vias and the pi board's 18 pads. The reviser's, likewise: the sheet materials (substrate 0–0.71, coats 0.71–0.81 and −0.1–0 once the zero-thickness fills drop), ports and copper at z 0 and 0.71, the far-field centre z 0.355; verify_spec on the sheet pi project (grid parts and fills at z 0.71, finite values); lpf915 with 0 mm copper building today with its zero-thickness mask fills; the product's port box [98.98, −112.89812, 0.745]–[99.787503, −111.07688, 0.78]; fit2d per section on ifa2g4 solid (n 2 0.99 % and 0.31 %, n 3 4.13 % and 0.75 %); one thru_hole pad, AE1.2 at (102.1, −100.0). The feasibility review's real openEMS setup gave sheet dt 2.1426e-13 s (ifa2g4) and 2.35612e-13 s (pi), 1.86 times solid's. No suite ran — cost if wrong: none.

## Open issues, ruled by the controller (2026-10-30; owner unavailable)

The draft's six open issues, and two the reviews raised that the plan carries as owner items, are ruled here, each a controller recommendation. Those marked (owner) join the owner's list when this plan merges.

1. **The explanation's window stays [f_lo, f_hi]** (ruling 1). Since the amendment below, |ΔS11| and its threshold are taken over one window, and a real resonance shift turns the whole complex S11, phase first, so it shows in band even when both minima lie outside it (Task 4's "turned" case); ifa2g4's minimum sits 11.8 MHz below f_lo, well within the curve's smooth reach. — cost if wrong: an explanation a wider window would refuse, which D and η_rad still bound.
2. **P3-B's 0.05** gives way to each check's shift-equivalent (the amendment below).
3. **The n 3 branch is confirmed:** an antenna at mesh n ≥ 3 defaults to a 5 % fit2d limit (`ANTENNA_GATES`, `default_gates`, Stage 1 §5.5 amended by A-35), since a 3 % default would block both 2.4 GHz fixtures at the default and every antenna run test on them. (owner) The product fix for the pad-in-line conflict (E→W on sections under λg(f2)/20, or exempting the non-cut edge from the lint) stays the owner's; Task 13 leaves the comment. — cost if wrong: a looser fit2d gate on antenna feeds at n 3.
4. **The time budget** (up to about 95 h on the T_max branch, P3-E's fallback about 10 h more) is accepted. CP2 records its re-estimate of the rest; a re-estimate above 110 h drops the meander's n 4 steps, as the T_max branch does (two meshes at the 2.4 GHz fixture's observed order), a recorded deviation. — cost if wrong: one mesh level of evidence on the meander.
5. **The extrapolation at the observed order capped at 1 is confirmed.** A "not converging" mesh check on either fixture stops at its checkpoint for a controller ruling before P3-D takes the 2.4 GHz edits, since n 3 is then unvalidated too. — cost if wrong: a stop.
6. **The optional `flat_s` field is confirmed,** a product change before the freeze beside ruling 3's copper field: design §5.4 says P3-C revisits the flat window, which src's freeze would otherwise make impossible. — cost if wrong: one field.
7. (owner) **The ±d moves may measure sensitivity to position** rather than noise: the open-end leg sits 0.65 mm from the ground zone's corner. Ruling 10's maximum stays the statistic; when the odd part dominates on f_res, P3-D's report raises the owner item (thresholds from max(|repeat|, |shift|, |even|), or a mesh-only probe).
8. (owner) **Sheet copper on a narrow coplanar feed** (a gap under 30·t): neither fixture has one, so A-35 states the scope, and the owner decides between solid copper on such feeds and a W_ line from a solid-copper fit2d solve.

## Controller amendment at commit (2026-10-30; owner unavailable)

- **The explanation's threshold is each check's own shift-equivalent.** The draft explained an unconditioned f_res miss when max |ΔS11| in band was within 0.05 (P3-B and the mesh check), scaled by each check's limit elsewhere. On ifa2g4 the first run's phase slope makes a 1 % shift move S11 by about 0.14 in band (|dS11/df| about 0.0056 per MHz, the physics review; 0.1404 on the tests' curve in the controller's scratch emulation), so 0.05 explained only curves within about a 0.36 % shift: 2.8 times stricter than the 1 % check it explains, while r1's differences by design map to 0.055–0.14. A P3-B miss on the −5.9 dB minimum was then likelier to reach "product bug presumed" than to be explained, and no pre-registered diagnosis removes the port box, the smeared mask or the pulse. `p3.pair` now explains a miss when ds11 ≤ ds11_shift: the curves differ by no more than a shift of the check's own limit moves the reference's. `explained_ds11` leaves both criteria files and `pair`'s signature; Task 1 tests the rule directly, and Tasks 4 and 6 test it on phase-turning shallow curves (|ΔS11| 0.03 explained and 0.20 or a real 1.5 % shift not, at 1 %; 0.09 not and 0.03 explained at copper's 0.5 %); Task 9's judgement and report, A-40 and the rulings read the same. D and η_rad stay binding, a conditioned miss is never explained, and no run has started. — controller recommendation, owner unavailable — cost if wrong: an explanation a stricter reading would refuse, which D, η_rad and the diagnoses still bound.
