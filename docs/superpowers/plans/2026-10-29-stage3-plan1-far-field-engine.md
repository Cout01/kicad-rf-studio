# Stage 3 Plan 1: The Far-Field Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The engine records, transforms and reads an antenna's far field, computes its efficiencies and applies the E_METAL_IN_PML gate, and gate P3-A proves it on synthetic dipoles; first, golden digests pin every v1 model, hash and output byte for byte.

**Architecture:** A model spec may hold two antenna-only keys: `"boundary": "pml_8"` (PML_8 on all six faces) and `"nf2ff"` (frequencies, a centre and an optional box for openEMS's frequency-domain far-field box). The box is over-sampled 4 times, so it samples at the port probes' rate. `build_csx` reads both keys, and every v1 spec holds neither, so it builds exactly as Task 1's digests pin it. The transform is a worker mode run beside the finished job, so the orchestrator never imports openEMS. It makes three `CalcNF2FF` calls with `read_cached=False`, each writing a file named for the call, and `core.post.farfield` reads them with h5py. P_acc and P_inc come from the job's waves with openEMS's DFT convention. `tools/p3a.py` runs a 12 mm and a 58 mm wire dipole through the product's job phase and transform on P0's harness, and Task 7 runs it, reports it and lands A-23 to A-25.

**Tech Stack:**
- Python ≥ 3.11 (dev venv 3.14.2), numpy, h5py 3.16 (already a dependency) and the repo's `smooth_mesh_lines`.
- openEMS 0.37.0 and CSXCAD 0.7.0. They are imported only in workers and in the dev tools `tools/make_farfield.py` and `tools/p3a.py`: `CreateNF2FFBox` (with CSXCAD's per-dump `over_sampling`), `nf2ff.CalcNF2FF`, `utilities.DFT_time2freq` and `nf2ff.nf2ff_results`.
- pytest.
- `tools/catalog.py` (Babel 2.18.0, dev extra).

**Spec:**
- `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md` (binding): §5.12 item 1, with §2–§4, §5.2, §5.5, §5.9, §5.11 and §5.13.
- The Stage 1 spec, `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, where the design reuses it: §3.1, §3.3, §5.1, §5.8, §6.3, §6.4, §9 and §11.
- Task 7 lands A-23 (§2), A-24 (§5.1) and A-25 (§9.8), with their exact text.
- Research (git-ignored) is in `.superpowers/sdd/stage3-research/`: r1 (the probes, the API, `read_cached`), r3 (the engine) and r4 (P3-A's references). openEMS-Project's v0.37.0 sources show the dumps' sampling (`openems.cpp`, `Common/processing.cpp`) and the PML's lines (`FDTD/extensions/operator_ext_upml.cpp`).

**Branch:** `stage3-plan1`, from `main` at `4e5edda`. This plan is `docs/superpowers/plans/2026-10-29-stage3-plan1-far-field-engine.md`. Commands run from the repo root with `.venv/Scripts/python`. Line references are `main`'s at `4e5edda`; if an earlier task moved a line, find it by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage3-plan1 main`. Then `git diff --stat 4e5edda HEAD -- src tests tools po pyproject.toml` must print nothing.
2. Commit this plan on the branch.
3. After Task 7: the whole-branch review, a local fast-forward merge into `main`, and delete the branch. Nothing is pushed.

## Global Constraints

- **v1 byte for byte** (design §3, §4): v1 projects stay at schema 1. These stay exactly as built at `4e5edda`: their model specs, `spec_hash`, `model.json` bytes, verify's model spec, `project.json`, `new`'s lines and `results/` files. Task 1 pins them before any code changes, and no later task re-records the pins.
- **Antenna keys only in antenna specs:** only P3-A's dipoles (and plan 2's antennas later) write `"boundary"` and `"nf2ff"`. They never go into a v1 project's specs (`model_spec`'s, or `verify_spec`'s copies of them) or into `calibration_spec`.
- **PML_8 on all six faces, never mixed** (Stage 1 §5.1): `"pml_8"` sets all six faces, and the key's absence sets MUR on all six.
- **Nothing in the absorber** (design §3, §5.2): E_METAL_IN_PML refuses metal, dielectric or a lumped port within the PML or the 2 cells just inside its inner edge. The 8 PML lines go outside, at the outer cell size.
- **Far field in the frequency domain only** (design §5.5): `CreateNF2FFBox` always gets `frequency=` and `over_sampling=4`, with 1 to 11 frequencies, f0 first, each satisfying f1 ≤ f ≤ f2.
- **Every transform** passes `read_cached=False`, writes a file no earlier call used, and first checks all 12 dumps (design §3: no stale far-field file).
- **openEMS stays in the worker** (Stage 1 §3.1): the CLI, the orchestrator and `core.post` never import openEMS or CSXCAD.
- **Messages:** every new user-facing string is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`. The same task compiles it with `.venv/Scripts/python tools/catalog.py` (pt-BR design §6 and this plan's glossary). A word passed as a parameter is a `T_` code. Numbers keep the decimal point.
- **Tests:** test-first.
  - Tier (a) tests never run openEMS, KiCad, the network or a build. They use `test_model_csx.fake_openems`, `tests/fake_worker.py` (through the `fake`, `calibrated` and `p0_out` fixtures) and committed fixtures.
  - `KrsError` tests check `.code` and `.params`, and gate-line tests check (code, params).
  - Real openEMS runs only in the dev tools of Tasks 4 and 7 and in Task 4's tier (b) test. That test is skipped wherever the worker's Python cannot import openEMS, so only CI's Linux tier b runs it.
- **Isolation:** tests never touch a real KiCad folder, Documents, KiCad's settings or the real data folder. The tools in Tasks 4 and 7 run through `p0.enter`, in a folder under `$env:TEMP` outside every work tree. `CSXCAD_INSTALL_PATH` is typed in the call and never written to a file.
- **Full suite** before every commit: `.venv/Scripts/python -m pytest -q`. It takes about 17 minutes, so run it once, in the background, with nothing beside it, and wait for it to exit.
- **Git:** no push. The pre-commit privacy gate runs on every commit, so never use `--no-verify`. No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name. No commit message carries a co-author line; use the messages as given.
- **Files:** every new `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`. Code and docs are in English.
- **Workflow:**
  - Run `graphify query "<question>"` before reading code, and `graphify update .` after each commit.
  - Ponytail: choose the laziest solution that works, and touch the fewest files.
  - Reuse the repo's pieces: the worker's modes, `runs.run_jobs`, `p0.run_model`, `p0.step`, the stop rule and the fake worker.
  - Reach for the stdlib, numpy and h5py first.
  - Put a `ponytail:` comment naming the ceiling on each corner cut.

## Review Focus

1. **A far-field frequency outside the band, more than 11 of them, or one near f2 recorded at openEMS's default rate.**
   - By default openEMS accumulates a frequency-domain dump only every 1/(2·f2·dt) steps, so each frequency picks up an alias at 2·f2 − f, worse toward f2.
   - On the 12 mm dipole, against a 3.0 GHz f2: η_rad 0.952 and D 0.30 dB low at 2.9 GHz, and η_rad 1.35 at 2.99 GHz. The architect's probe read 3.3 at f2 itself. W_ETA_RAD flags only values above 1.02, so it misses the 0.952.
   - `over_sampling=4` accumulates at the port probes' rate and removes the alias, so the design's f1 ≤ f ≤ f2 holds. Refuse anything else before any run.
   - Checks: Task 2's `test_the_far_field_box_records_the_frequencies_in_the_frequency_domain` and `test_far_field_frequencies_outside_the_band_or_more_than_11_are_refused`.
2. **A transform called twice for one job.** openEMS's defaults (`read_cached=True`, one `nf2ff.h5`) silently return the first call's result. Checks: Task 3's `test_nf2ff_mode_transforms_each_grid_afresh_into_a_file_of_its_own` and `test_far_field_transforms_in_a_folder_of_its_own_and_never_reuses_a_file`.
3. **A job that ended before its far field was recorded**: killed, crashed before PostProcess, or missing a face file. `CalcNF2FF` skips a face whose files are missing and integrates the rest, so it returns a wrong Prad with no error. Checks: Task 3's `test_nf2ff_mode_refuses_a_job_whose_far_field_was_never_recorded`, and P3-A's `dumps_after_abort`, which also asks for the stop rule's ABORT in the job's folder.
4. **A v1 pin that moves with the machine, not the code.**
   - summary.png's labels are drawn in the process's language. This PC's default is pt-BR, while the suite pins English.
   - The Touchstone files carry scikit-rf's version, summary.png carries matplotlib's, and the floats carry this CPU's BLAS bits.
   - A board on another drive than the working folder adds W_ABSOLUTE_BOARD_PATH to `new`'s lines, as on CI's Windows runner.
   - Checks: Task 1's tool records in English with `env()`; its test compares outputs only where `env()` matches; and `digests()` copies each board into the working folder.
5. **A structure reaching the absorber**: a wire, a slab, a copper piece, the lid, a lumped port, a grid part, or a via whose radius crosses into the PML or the 2 cells just inside its inner edge. A coordinate exactly on the limit's line passes. A face gives one line, at its farthest intruder. Checks: Task 5's `test_metal_dielectric_or_a_port_within_the_pml_and_2_cells_is_refused` (one case per kind) and `test_the_setup_gate_blocks_metal_within_the_pml`; P3-A's `setup` check.

---

## File structure

```
tools/golden_v1.py, tests/test_golden_v1.py, tests/fixtures/golden_v1.json            # T1
src/kicad_rf_studio/core/model/csx.py      # T2 PML_CELLS, BOUNDARY, NF2FF_MAX; build_csx's boundary, box, return
src/kicad_rf_studio/core/model/spec.py     # T2 pulse, with_pml; T5 PML_CLEAR, metal_in_pml
src/kicad_rf_studio/worker.py              # T2 the unpacking; T3 DUMPS, GRIDS, mode "nf2ff"
tools/p3a.py, tests/test_p3a.py            # T2 the dipoles; T6 the gate; tests/fixtures/p3a/references.json T6
src/kicad_rf_studio/runs.py                # T3 write_job's extra keys, job_dir's docstring
src/kicad_rf_studio/pipeline.py            # T3 far_field; T5 setup_gate's E_METAL_IN_PML
src/kicad_rf_studio/core/messages.py, po/*, locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo
                                           # T3 T_JOB_FAR_FIELD; T4 W_ETA_RAD; T5 E_METAL_IN_PML
tests/fake_worker.py                       # T3 the dumps and mode "nf2ff"; T6 copies the far-field fixture
tools/make_farfield.py, tests/fixtures/farfield/   # T4 the probe step and its fixture
src/kicad_rf_studio/core/post/farfield.py, tests/test_post_farfield.py               # T4
tests/test_model_csx.py, test_model_spec.py, test_worker.py, test_run.py             # T2, T3, T5
docs/validation/<date>-p3-a.md, .json; the Stage 1 spec                               # T7
```

---

### Task 1 [code]: Golden pins on v1

**Files:**
- Create: `tools/golden_v1.py` and `tests/test_golden_v1.py`.
- Written by the tool: `tests/fixtures/golden_v1.json`.

**Interfaces:**
- Consumes:
  - `cli.new(board, start, end, f0, *, lid_height, output) -> (Path, notes)`.
  - `pipeline.load`, `build_model`, `expected_loss(geom, f0)` and `write_outputs(path, project, command) -> lines`.
  - `runs.write_spec` and `runs.calibration_spec()`.
  - `spec_hash` and `verify_spec(spec, parts, dump, dt)`, with `core.model.spec.c_box` stood in for as `tests/fake_cli.py` does.
  - `parts(project)` and `messages.language()`.
  - `p0.load_trace(path) -> (Records, k, exc, t_cut)`, `p0.FIX` and `p0.code_id()`.
  - `GATES`, `load_project` and `save_project`.
- Produces:
  - `golden_v1.GOLDEN`, `CASES` and `TRACED`.
  - `golden_v1.env() -> list`.
  - `golden_v1.digests() -> dict`, to be called with an empty folder as the working directory.
  - `golden_v1.main() -> int`.

- [ ] **Step 1: Write the failing test,** `tests/test_golden_v1.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import golden_v1


def test_v1_builds_and_writes_byte_for_byte_what_it_did_at_4e5edda(tmp_path, monkeypatch):  # Stage 3 design 3, 4; RF 4
    monkeypatch.chdir(tmp_path)  # digests() works in relative paths, so no byte holds this machine's folders
    golden = json.loads(golden_v1.GOLDEN.read_text(encoding="utf-8"))
    now = golden_v1.digests()
    assert set(now["models"]) == {"lpf915", "lpf915-45", "coupon_gcpw_pads", "calibration"}
    assert "verify" in now["models"]["lpf915"]
    assert now["models"] == golden["models"]  # a v1 model spec, its hash, verify's model, project.json or new's lines moved
    assert set(now["outputs"]) == {"lpf915", "coupon_gcpw_pads"}
    if golden_v1.env() == golden["env"]:  # ponytail: the output bytes are the recording machine's (golden_v1.env)
        assert now["outputs"] == golden["outputs"]  # a v1 results/ file or result line moved
```

- [ ] **Step 2: Run it.** `.venv/Scripts/python -m pytest tests/test_golden_v1.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'golden_v1'`.
- [ ] **Step 3: Write `tools/golden_v1.py`.**
  - **Docstring:** "The v1 golden pins (Stage 3 design 3, 4, 5.12 item 1): sha256 digests of what v1 builds and writes from the committed fixtures, recorded once, before Stage 3 changed any code, in tests/fixtures/golden_v1.json, with env(), what the output bytes depend on besides the code. tests/test_golden_v1.py compares the models everywhere and the outputs where env() matches. Every path is relative to the working folder. Dev-time only: run it once with `python tools/golden_v1.py`, which records in English, the suite's language. It refuses to overwrite the JSON; a new recording is a controller ruling, which deletes the file first."
  - **Imports, in this order:**
    1. `os`.
    2. `if __name__ == "__main__": os.environ["LANGUAGE"] = "en"`, commented "the suite's language (tests/conftest.py), set before core.messages binds one at import: summary.png's labels are drawn in it".
    3. The rest: `hashlib`, `json`, `platform`, `shutil`, `sys`, `tempfile`, `Path`, `unittest.mock`, `matplotlib`, `numpy as np`, `scipy`, `skrf`, `p0`, `cli`, `pipeline`, `runs`, `messages`, the `kicad_rf_studio.core.model.spec` module as `spec_module`, `spec_hash`, `verify_spec`, `GATES`, `load_project`, `parts` and `save_project`.
  - **`main()`:**
    - When `GOLDEN` exists, it prints the refusal to stderr and returns 1.
    - Otherwise it runs `digests()` inside a `tempfile.TemporaryDirectory()`, entered with `os.chdir` and left in a `finally`.
    - It writes `json.dumps({"code": p0.code_id(), "env": env(), **pins}, indent=1, sort_keys=True) + "\n"` and returns 0.
    - `__main__` calls `sys.exit(main())`.
  - **The pins, as given:**

```python
GOLDEN = p0.FIX / "golden_v1.json"
CASES = {"lpf915": ("U1.1", "J1.1", 2.5), "lpf915-45": ("U1.1", "J1.1", 2.5),
         "coupon_gcpw_pads": ("TP1.1", "TP2.1", None)}  # new's start, end and lid height, at f0 915 MHz
TRACED = ("lpf915", "coupon_gcpw_pads")  # the cases whose every job tests/fixtures/traces holds


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def env() -> list:
    """What the output bytes depend on besides the code, with no host name: the platform, the CPU, the numpy, scipy,
    matplotlib and scikit-rf versions, and the catalog's language."""
    # ponytail: the output bytes carry scikit-rf's and matplotlib's versions, summary.png's language and this CPU's
    # BLAS bits; on any other env() only the model digests are compared
    return [sys.platform, platform.processor(), np.__version__, scipy.__version__, matplotlib.__version__,
            skrf.__version__, messages.language()]


def digests() -> dict:
    """{"models": {case: {"spec_hash", "model_json", "project", "notes"}, lpf915's with "verify", "calibration":
    {"spec_hash", "model_json"}}, "outputs": {case of TRACED: {each results/ file: its sha256, "lines"}}}. Each case's
    board is copied into the working folder and built there by `new` at v1's defaults (lpf915-45 with
    allow_curve_port, else E_ROTATED_PART), so project.json's relative board path and new's lines are the same on
    every machine. The model spec is pinned by its hash and by model.json's bytes as runs.write_spec writes them,
    project.json by its bytes, and new's lines without I_WROTE. verify's model of lpf915 (verify refuses lpf915-45,
    E_VERIFY_CURVE, and the coupon, E_VERIFY_NO_PARTS) is verify_spec's at the fake's dt, 1e-13 s, with the dump's
    reader stood in for as tests/fake_cli.py does: 2e-14 F a cell. A traced case's <case>/run holds its model.json and
    its jobs' waves from the traces: every job converged at its trace's cut, C_box 2e-14 F per part port, the expected
    loss of its geometry."""
    models, outputs = {}, {}
    for name, (start, end, lid) in CASES.items():
        shutil.copyfile(p0.FIX / f"{name}.kicad_pcb", f"{name}.kicad_pcb")
        pj, notes = cli.new(f"{name}.kicad_pcb", start, end, 915e6, lid_height=lid, output=Path(name))
        if name == "lpf915-45":
            save_project(pj, {**load_project(pj), "allow_curve_port": True})
        project, board, geom, _ = pipeline.load(pj)
        spec = pipeline.build_model(project, board, geom).spec
        models[name] = {"spec_hash": spec_hash(spec), "model_json": sha(json.dumps(spec).encode()),
                        "project": sha(pj.read_bytes()),
                        "notes": sha(json.dumps(notes[:-1], sort_keys=True, default=str).encode())}
        if name == "lpf915":
            dump = Path(name) / "operator_dump.vtr"
            dump.write_bytes(b"")
            with mock.patch.object(spec_module, "c_box", lambda *_: 2e-14):
                vspec = verify_spec(spec, parts(project), dump, 1e-13)
            models[name]["verify"] = {"spec_hash": spec_hash(vspec), "model_json": sha(json.dumps(vspec).encode())}
        if name not in TRACED:
            continue
        run_dir, jobs = Path(name) / "run", []
        runs.write_spec(run_dir, spec)
        for k, port in enumerate(spec["ports"], 1):
            rec, _, _, t_cut = p0.load_trace(p0.FIX / "traces" / f"{name}-k{k}.npz")
            (run_dir / f"job-{k}").mkdir()
            np.savez(run_dir / f"job-{k}" / "waves.npz", t_u=rec.t_u, u=rec.u, t_i=rec.t_i, i=rec.i)
            jobs.append({"port": port["name"], "verdict": "converged", "t_cut": t_cut, "t_stop": float(rec.t_u[-1]),
                         "residual_db": -60.0, "waves": f"job-{k}/waves.npz"})
        results = {"run_dir": str(run_dir), "preset": "normal", "gates": GATES, "jobs": jobs,
                   "loss_expected": pipeline.expected_loss(geom, 915e6),
                   "c_box": {q["name"]: 2e-14 for q in spec["ports"] if q["part"]}}
        lines = pipeline.write_outputs(pj, {**project, "results": results}, "c")
        outputs[name] = {**{f.name: sha(f.read_bytes()) for f in sorted((pj.parent / "results").iterdir())},
                         "lines": sha(json.dumps(lines, sort_keys=True, default=str).encode())}
    calibration = runs.calibration_spec()
    models["calibration"] = {"spec_hash": spec_hash(calibration), "model_json": sha(json.dumps(calibration).encode())}
    return {"models": models, "outputs": outputs}
```

- [ ] **Step 4: Record the pins from `4e5edda`'s product.**
  - `git diff --stat 4e5edda -- src` must print nothing.
  - Run `.venv/Scripts/python tools/golden_v1.py`. Expected: exit 0, and `tests/fixtures/golden_v1.json` (about 2 KB). Its `"code"` equals `git rev-parse 4e5edda:src`, and its `"env"` starts with `"win32"` and ends with `"en"`.
  - Run it a second time. Expected: the refusal, and exit 1.
  - This revision's prototype gave identical digests in two working folders, in 4.1 s. Its English summary.png digests are the ones the suite computes. A pt_BR process draws other summary.png bytes and nothing else.
- [ ] **Step 5: Run it again.** `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_repo.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/golden_v1.py tests/test_golden_v1.py tests/fixtures/golden_v1.json
git commit -m "test(golden): pin v1's model specs, hashes, verify's model, project.json, new's lines and results/ bytes as built at 4e5edda (Stage 3 design 4, 5.12 item 1)"
graphify update .
```

---

### Task 2 [code]: The antenna keys, the boundary, the pulse and P3-A's dipoles

**Files:**
- Modify:
  - `core/model/csx.py`: constants after L7, the docstring at L16–25, L36, and the box and the return at L72.
  - `core/model/spec.py`: `excitation`, L45–53.
  - `worker.py`: L75.
  - `tests/test_worker.py`: L89.
- Create: `tools/p3a.py`.
- Test: `tests/test_model_csx.py`, `tests/test_model_spec.py` and a new `tests/test_p3a.py`.

**Interfaces:**
- Consumes: `smooth_mesh_lines(lines, max_res, ratio)`; `band(project)` and `C0` (`core/geometry/region.py`).
- Produces:
  - `csx.PML_CELLS = 8`, `csx.BOUNDARY = {None: "MUR", "pml_8": "PML_8"}` and `csx.NF2FF_MAX = 11`.
  - `build_csx(spec, excite, t_max) -> tuple[object, object, object | None]`, the third value being the far-field box or None.
  - `spec.pulse(f1: float, f2: float, t_max: float) -> dict` and `spec.with_pml(lines: list[float]) -> list[float]`.
  - The keys `"boundary": "pml_8"` and `"nf2ff": {"f_hz": [f0, …], "center": [x, y, z] mm, "box": [start, stop] mm, optional}`.
  - `p3a.F0`, `F_LO`, `F_HI`, `F1`, `F2`, `F_HZ`, `T_MAX`, `GAP_MM`, `CMAX_MM`, `CELL_MM`, `FEED_MM`, `SHORT_MM` and `HALF_MM`.
  - `p3a.dipole(length_mm: float, *, f_hz: list[float] = F_HZ, boundary: str | None = "pml_8", box: list[list[float]] | None = None) -> dict`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_model_csx.py` (imports gain `pytest`):

```python
def test_the_boundary_is_mur_without_the_key_and_pml_8_on_all_six_faces_with_it(monkeypatch):  # design 5.2; S1 5.1
    log = fake_openems(monkeypatch)
    assert build_csx(TINY, 1, 1e-9)[2] is None  # a v1 spec: MUR (the test above) and no far-field box
    build_csx({**TINY, "boundary": "pml_8"}, 1, 1e-9)
    assert ("SetBoundaryCond", (["PML_8"] * 6,), {}) in log
    with pytest.raises(KeyError):  # MUR is the key's absence, never a value
        build_csx({**TINY, "boundary": "mur"}, 1, 1e-9)


FAR = {"f_hz": [1e9, 0.5e9, 1.1e9], "center": [2.0, 2.0, 2.0]}  # TINY's band, f1 0.5 GHz to f2 1.1 GHz, both ends in


def test_the_far_field_box_records_the_frequencies_in_the_frequency_domain(monkeypatch):  # design 5.5; RF 1
    log = fake_openems(monkeypatch)
    assert build_csx({**TINY, "nf2ff": FAR}, 1, 1e-9)[2] is not None
    names = [n for n, _, _ in log]
    # openEMS's own placement under PML_8, accumulated every Nyquist/4 steps, as the port probes sample
    assert ("CreateNF2FFBox", ("nf2ff",), {"frequency": FAR["f_hz"], "over_sampling": 4}) in log
    assert names.index("CreateNF2FFBox") > names.index("SetBoundaryCond")  # it reads the grid and the boundary
    build_csx({**TINY, "nf2ff": {**FAR, "box": [[1.0, 1.0, 1.0], [3.0, 3.0, 3.0]]}}, 1, 1e-9)
    assert ("CreateNF2FFBox", ("nf2ff",), {"frequency": FAR["f_hz"], "over_sampling": 4, "start": [1.0, 1.0, 1.0],
                                           "stop": [3.0, 3.0, 3.0]}) in log


@pytest.mark.parametrize("f_hz", [[1.2e9], [0.4e9], [], [0.6e9] * 12])  # RF 1
def test_far_field_frequencies_outside_the_band_or_more_than_11_are_refused(monkeypatch, f_hz):  # design 5.5
    log = fake_openems(monkeypatch)
    with pytest.raises(ValueError, match="far-field frequencies"):
        build_csx({**TINY, "nf2ff": {**FAR, "f_hz": f_hz}}, 1, 1e-9)
    assert "CreateNF2FFBox" not in [n for n, _, _ in log]
```

  In `tests/test_model_spec.py` (imports gain `pulse`, `with_pml`, and `band` from `core.geometry.region`; `math` and `pytest` are already imported):

```python
def test_the_pulse_is_spec_5_8s_over_any_band_and_excitation_is_it_over_the_projects():  # design 5.4
    p = pulse(1.85e9, 3.0e9, 30e-9)
    assert (p["f1"], p["f2"], p["t_max"]) == (1.85e9, 3.0e9, 30e-9)
    assert p["t0"] == pytest.approx(9 / (2 * math.pi * 0.575e9)) and p["expr"].startswith("sin(2*pi*2425000000*(t-")
    project = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "t_max_s": 40e-9}
    assert excitation(project) == pulse(*band(project), 40e-9)


def test_with_pml_adds_8_lines_past_each_end_at_its_outer_cell():  # design 5.2
    assert with_pml([0.0, 1.0, 3.0]) == [-8.0, -7.0, -6.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 3.0,
                                         5.0, 7.0, 9.0, 11.0, 13.0, 15.0, 17.0, 19.0]
    assert with_pml([0.1, 0.4, 0.5])[:2] == [-2.3, -2.0]  # quantised to 1e-6 mm
```

  `tests/test_p3a.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest

import p3a
from kicad_rf_studio.core.model.csx import PML_CELLS


@pytest.mark.parametrize("length", [p3a.SHORT_MM, p3a.HALF_MM])
def test_p3as_dipoles_are_wires_on_the_mesh_in_vacuum_under_pml_8(length):  # design 5.2, 5.11
    s, half, gap = p3a.dipole(length), length / 2, p3a.FEED_MM / 2
    assert (s["boundary"], s["materials"], s["grid"], s["metal"]["copper"]) == ("pml_8", [], [], [])
    assert s["metal"]["curves"] == [{"at": [0.0, 0.0], "z": [gap, half]}, {"at": [0.0, 0.0], "z": [-half, -gap]}]
    (port,) = s["ports"]
    assert (port["kind"], port["dir"], port["start"], port["stop"], port["part"]) == (
        "lumped", "z", [0.0, 0.0, -gap], [0.0, 0.0, gap], False)
    assert s["nf2ff"] == {"f_hz": [2.45e9, 2.4e9, 2.5e9], "center": [0.0, 0.0, 0.0]}
    assert (s["excitation"]["f1"], s["excitation"]["f2"], s["excitation"]["t_max"]) == (1.85e9, 3.0e9, 30e-9)
    for axis in "xyz":
        steps = np.diff(s["mesh"][axis])
        assert np.allclose(steps[:PML_CELLS], steps[0]) and np.allclose(steps[-PML_CELLS:], steps[-1])
        assert steps.max() <= p3a.CMAX_MM and steps.min() == pytest.approx(p3a.CELL_MM)
    z = s["mesh"]["z"]
    assert z[PML_CELLS] == round(-half - p3a.GAP_MM, 6) and {-half, -gap, gap, half} <= set(z)
    assert 0.0 in s["mesh"]["x"] and 0.0 in s["mesh"]["y"]


def test_a_dipole_drops_the_pml_or_places_its_box_on_the_same_mesh():  # P3-A's MUR twin and moved box
    box = [[-9.0, -9.0, -40.0], [9.0, 9.0, 40.0]]
    mur = p3a.dipole(p3a.HALF_MM, boundary=None, box=box)
    assert "boundary" not in mur and mur["nf2ff"]["box"] == box and mur["mesh"] == p3a.dipole(p3a.HALF_MM)["mesh"]
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_model_csx.py tests/test_model_spec.py tests/test_p3a.py -q`. Expected: FAIL.
  - Collection fails with `No module named 'p3a'` and `cannot import name 'pulse'`.
  - The csx tests fail because `build_csx` returns two values and never calls `CreateNF2FFBox`.
- [ ] **Step 3: `csx.py`.**
  - Add three constants:
    - `PML_CELLS = 8`, commented "PML_8's 8 outermost cells on each face (design 5.2)".
    - `BOUNDARY = {None: "MUR", "pml_8": f"PML_{PML_CELLS}"}`, commented "the spec's "boundary"; absent in every v1 spec".
    - `NF2FF_MAX = 11`.
  - L36 becomes `fdtd.SetBoundaryCond([BOUNDARY[spec.get("boundary")]] * 6)`.
  - Before the return, when `nf = spec.get("nf2ff")` holds a value:
    - Take f1 and f2 from the excitation. Raise `ValueError(f"far-field frequencies {f_hz}: 1 to {NF2FF_MAX}, each from f1 {f1:g} to f2 {f2:g} Hz")` unless `0 < len(f_hz) <= NF2FF_MAX and all(f1 <= f <= f2 for f in f_hz)`. Mark it `# ponytail: a crash (E_WORKER_FAILED); far-field frequencies come from code until plan 2's project field, which gets its own refusal`.
    - Then `box = fdtd.CreateNF2FFBox("nf2ff", frequency=f_hz, over_sampling=4, **({"start": nf["box"][0], "stop": nf["box"][1]} if "box" in nf else {}))`, commented "accumulated every Nyquist/4 steps, the port probes' rate: at openEMS's default Nyquist rate a frequency aliases at 2·f2 − f, worse toward f2 (design 5.5)".
  - Return `csx, fdtd, box`, with `box` None when the key is absent.
  - The docstring names both keys and the return. The box records in the frequency domain, over-sampled 4 times, on all six faces, with no mirror, at openEMS's own placement (one line inside the PML) or at `box`.
- [ ] **Step 4: `spec.py`.**
  - `pulse(f1, f2, t_max)` takes over `excitation`'s body, applied to the band (f1, f2).
  - `excitation(project)` becomes `return pulse(*band(project), project["t_max_s"])`.
  - Add `with_pml(lines)`, with the docstring "`lines` (ascending, mm) with PML_CELLS lines added past each end at that end's outer cell, quantised to 1e-6 mm (design 5.2)". It imports `PML_CELLS` from `csx`.
- [ ] **Step 5: The worker and its test.** In `worker.py`, L75 becomes `_, fdtd, _ = build_csx(spec, job["port"], job["t_max"])`. In `tests/test_worker.py`, L89's lambda returns `(None, types.SimpleNamespace(Run=lambda *_, **__: 1), None)`.
- [ ] **Step 6: `tools/p3a.py`.** Its docstring is "P3-A, the far-field sanity gate (Stage 3 design 5.11). Part 1, the dipoles. Dev-time only, like p0."; Task 6 completes it. It imports `numpy`, `C0`, `smooth_mesh_lines`, `pulse` and `with_pml`, and holds, as given:

```python
F0, F_LO, F_HI = 2.45e9, 2.40e9, 2.50e9  # the dipoles' band, f0 its centre
F1, F2 = 1.85e9, 3.0e9  # the pulse: f_lo/1.3 and 1.2·f_hi, rounded (design 5.4)
F_HZ = [F0, F_LO, F_HI]  # the far-field frequencies, f0 first (design 5.5)
T_MAX = 30e-9  # 2·t0 + 60/f0 = 29.5 ns, rounded up (design 5.4)
GAP_MM = C0 / F_LO * 1e3 / 4  # the air gap: λ/4 at f_lo (design 5.2)
CMAX_MM = C0 / F2 * 1e3 / 20  # the air's largest cell, λ(f2)/20
CELL_MM, FEED_MM = 0.5, 1.0  # the wire's cell and the port's gap (r1's probes)
SHORT_MM, HALF_MM = 12.0, 58.0  # λ/10 at f0 (λ/20 read η_rad 0.971 in the architect's probe); r1's half-wave wire


def dipole(length_mm: float, *, f_hz: list[float] = F_HZ, boundary: str | None = "pml_8",
           box: list[list[float]] | None = None) -> dict:
    """A z-directed PEC wire dipole `length_mm` long, centred on the origin, in vacuum, as a model spec (design 5.11).
    Its arms are two curves on the x = y = 0 lines, and a 50 Ω lumped port P1 spans the FEED_MM gap, with witnesses one
    CELL_MM into each arm. The pulse runs over F1–F2 to T_MAX. Mesh lines fall every CELL_MM out to 1 mm past the wire's
    ends and to ±1 mm in x and y, then GAP_MM of air graded at 1.3 up to CMAX_MM, then with_pml. `boundary` is "pml_8"
    (None: MUR). The far field is recorded at `f_hz` about the origin, in `box` when given."""
    half, gap = length_mm / 2, FEED_MM / 2
    fine = {"x": [-1.0, -0.5, 0.0, 0.5, 1.0], "y": [-1.0, -0.5, 0.0, 0.5, 1.0],
            "z": np.arange(-half - 1.0, half + 1.0 + 1e-9, CELL_MM).tolist()}
    ends = {"x": (0.0, 0.0), "y": (0.0, 0.0), "z": (-half, half)}
    mesh = {a: with_pml([round(float(v), 6) for v in smooth_mesh_lines(
        np.array([*fine[a], ends[a][0] - GAP_MM, ends[a][1] + GAP_MM]), CMAX_MM, 1.3)]) for a in "xyz"}
    start, stop = [0.0, 0.0, -gap], [0.0, 0.0, gap]
    spec = {"mesh": mesh, "excitation": pulse(F1, F2, T_MAX), "materials": [],
            "metal": {"copper": [], "lid": {"plate": None, "walls": []}, "cylinders": [],
                      "curves": [{"at": [0.0, 0.0], "z": [gap, half]}, {"at": [0.0, 0.0], "z": [-half, -gap]}]},
            "ports": [{"name": "P1", "kind": "lumped", "dir": "z", "start": start, "stop": stop, "part": False,
                       "nodes": [start, stop, [0.0, 0.0, -gap - CELL_MM], [0.0, 0.0, gap + CELL_MM]]}],
            "grid": [], "nf2ff": {"f_hz": list(f_hz), "center": [0.0, 0.0, 0.0], **({"box": box} if box else {})}}
    return {**spec, "boundary": boundary} if boundary else spec
```

  The architect's prototype of this mesh gave 45 × 45 × 161 lines for the 58 mm dipole and 45 × 45 × 69 for the 12 mm one. The 58 mm mesh has 326,025 cells, and openEMS's UPML updates 68 % of them (9 lines per face).
- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_worker.py tests/test_golden_v1.py -q`. Expected: PASS. The pins hold because no v1 spec holds a new key.
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/model/csx.py src/kicad_rf_studio/core/model/spec.py src/kicad_rf_studio/worker.py tools/p3a.py tests/test_model_csx.py tests/test_model_spec.py tests/test_worker.py tests/test_p3a.py
git commit -m "feat(model): the antenna-only spec keys, PML_8 on all six faces and the over-sampled frequency-domain far-field box, the pulse over any band, and P3-A's wire dipoles (Stage 3 design 5.2, 5.5, 5.11)"
graphify update .
```

---

### Task 3 [code]: The far-field transform in a worker mode

**Files:**
- Modify:
  - `worker.py`: the docstring (L2–6), `DUMPS` and `GRIDS` after L19, `_far_field` after `_setup`, and `main`'s modes (L78–88).
  - `runs.py`: `job_dir`'s docstring (L122) and `write_job` (L132–137).
  - `pipeline.py`: the imports (`secrets`, `GRIDS`), and `far_field` after `run_ports` (L688).
  - `core/messages.py`: after `T_JOB_CALIBRATION` (L349).
  - `po/*` and the `.mo`.
  - `tests/fake_worker.py`.
- Test: `tests/test_worker.py`.

**Interfaces:**
- Consumes: Task 2's `build_csx -> (csx, fdtd, box)` and the `"nf2ff"` key; `runs.job_dir`, `run_jobs`, `check_job` and `load_settings`; `fake_openems`, `TINY` and `test_worker.write_job`.
- Produces:
  - `worker.DUMPS`: the 12 names, `nf2ff_E_0.h5` … `nf2ff_H_5.h5`.
  - `worker.GRIDS: dict[str, tuple[np.ndarray, np.ndarray, bool]]` (θ in degrees, φ in degrees, f0 only).
  - Worker mode `"nf2ff"`, whose job.json adds `"dumps"` (the finished job's folder, relative) and `"out"` (the outputs' stem).
  - `runs.write_job(job, port, mode, threads, t_max, **extra) -> Path`.
  - `pipeline.far_field(job: Path) -> dict[str, Path]`.
  - `T_JOB_FAR_FIELD`.

- [ ] **Step 1: Write the failing tests,** in `tests/test_worker.py` (imports gain `KrsError` and `pipeline`):

```python
NF = {"f_hz": [1e9, 0.9e9], "center": [2.0, 2.0, 2.0]}  # TINY's band: 0.5–1.1 GHz


def finished_job(tmp_path, dumps=worker.DUMPS):
    """A run job of TINY with a far field, as openEMS leaves it: model.json above it, its job.json and `dumps`."""
    job = write_job(tmp_path, {**TINY, "nf2ff": NF}, "run")
    for name in dumps:
        (job / name).write_bytes(b"")
    return job


def transform_job(job):
    """The transform's own folder beside `job`, as far_field makes it, with the token ab12."""
    folder = job.parent / "job-0-nf2ff-ab12"
    folder.mkdir()
    (folder / "job.json").write_text(json.dumps({"spec": "../model.json", "port": 1, "mode": "nf2ff", "threads": 1,
                                                 "t_max": 1e-9, "dumps": f"../{job.name}", "out": "nf2ff-ab12"}),
                                     encoding="utf-8")
    return folder


def test_nf2ff_mode_transforms_each_grid_afresh_into_a_file_of_its_own(tmp_path, monkeypatch):  # design 5.5; RF 2
    log = fake_openems(monkeypatch)
    monkeypatch.chdir(transform_job(finished_job(tmp_path)))
    assert worker.main(["job.json"]) == 0
    calls = [(args, kw) for name, args, kw in log if name == "CalcNF2FF"]
    assert list(worker.GRIDS) == ["sphere", "elevation", "azimuth"]
    assert [kw["outfile"] for _, kw in calls] == [f"nf2ff-ab12-{grid}.h5" for grid in worker.GRIDS]
    assert all(kw["read_cached"] is False and args[0] == "../job-1-P1" for args, kw in calls)
    assert all(kw["center"] == pytest.approx([2e-3] * 3) for _, kw in calls)  # metres: the spec's 2 mm
    assert [args[1] for args, _ in calls] == [NF["f_hz"], NF["f_hz"][:1], NF["f_hz"][:1]]  # recorded ones only
    assert [(len(args[2]), len(args[3])) for args, _ in calls] == [(37, 72), (360, 2), (1, 360)]
    assert (calls[1][0][2][0], list(calls[1][0][3]), list(calls[2][0][2])) == (-180, [0, 90], [90])
    assert "Run" not in [name for name, _, _ in log]  # no FDTD


def test_nf2ff_mode_refuses_a_job_whose_far_field_was_never_recorded(tmp_path, monkeypatch):  # RF 3
    log = fake_openems(monkeypatch)
    monkeypatch.chdir(transform_job(finished_job(tmp_path, worker.DUMPS[:-1])))
    with pytest.raises(FileNotFoundError, match="nf2ff_H_5.h5"):
        worker.main(["job.json"])
    assert "CalcNF2FF" not in [name for name, _, _ in log]


def test_far_field_transforms_in_a_folder_of_its_own_and_never_reuses_a_file(tmp_path, fake):  # 5.5; RF 2
    job = finished_job(tmp_path)
    first, second = pipeline.far_field(job), pipeline.far_field(job)
    assert list(first) == list(second) == list(worker.GRIDS)
    assert all(p.parent == job and p.is_file() for p in (*first.values(), *second.values()))
    assert not set(first.values()) & set(second.values())
    folders = sorted(job.parent.glob("job-0-nf2ff-*"))
    assert len(folders) == 2 and {json.loads((f / "job.json").read_text(encoding="utf-8"))["dumps"]
                                  for f in folders} == {"../job-1-P1"}
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # Stage 1 3.1: a worker transformed it


def test_a_transform_that_fails_names_the_far_field_job(tmp_path, fake, monkeypatch):  # pt-BR design 5.1
    job = finished_job(tmp_path)
    monkeypatch.setenv("KRS_FAKE_EXIT", "1")
    with pytest.raises(KrsError) as e:
        pipeline.far_field(job)
    assert (e.value.code, e.value.params["job"], e.value.params["exit_code"]) == (
        "E_WORKER_FAILED", "T_JOB_FAR_FIELD", 1)
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_worker.py -q`. Expected: FAIL with `module 'kicad_rf_studio.worker' has no attribute 'DUMPS'`.
- [ ] **Step 3: The worker.**
  - Add `DUMPS = tuple(f"nf2ff_{q}_{n}.h5" for q in "EH" for n in range(6))`, commented "the far-field box's E and H on each face".
  - Add `GRIDS`, in this order:
    - `"sphere": (np.arange(0, 181, 5), np.arange(0, 360, 5), False)`;
    - `"elevation": (np.arange(-180, 180, 1), np.array([0, 90]), True)`;
    - `"azimuth": (np.array([90]), np.arange(0, 360, 1), True)`.

    Comment it "design 5.5: the full sphere at 5° at every recorded frequency; the XZ (φ 0°) and YZ (φ 90°) cuts as one θ sweep and the XY cut (θ 90°) as a φ sweep, at 1° at f0", with `# ponytail: fixed steps; plan 2's angle-step field passes its own`.
  - In `main`, unpack `_, fdtd, box = build_csx(...)`. Before the xml branch, add `if job["mode"] == "nf2ff": _far_field(job, spec, box); return 0`, marked `# ponytail: the whole CSX rebuilt for openEMS's box; on a board, build only the box from model.json's lines if plan 2 measures it slow`. The module docstring names the mode, its keys and its outputs.
  - `_far_field(job: dict, spec: dict, box: object) -> None` is the contract with openEMS. Its docstring:

    "Mode "nf2ff" (Stage 3 design 5.5): the far field of the finished job in job["dumps"] (relative), one CalcNF2FF per grid of GRIDS, always read_cached=False, written to <dumps>/<job["out"]>-<grid>.h5, a name no other call uses: the sphere at every recorded frequency, the cuts at f0 (the first), about spec["nf2ff"]["center"] (mm; CalcNF2FF takes metres). FileNotFoundError naming the first missing dump, before any transform: CalcNF2FF skips a face whose files are missing and integrates the rest."

    The two mode tests above fix every call, its arguments and its order; write the body to them.
- [ ] **Step 4: `runs.py`.**
  - `write_job` gains `**extra`, merged into job.json after the five keys. Its docstring adds "and `extra`'s keys (the far-field transform's dumps and out)".
  - `job_dir`'s docstring names `job-0-nf2ff-<token>` beside job-0-setup and job-0-xml.
- [ ] **Step 5: `pipeline.far_field(job)`.**
  - **Docstring:** "The far-field transform (Stage 3 design 5.5) of the finished job in folder `job`, whose model spec records a far field. One worker in mode "nf2ff", in a folder of its own beside the job (job-0-nf2ff-<token>, a new `secrets.token_hex(4)` at each call), reads the job's dumps and writes <job>/nf2ff-<token>-<grid>.h5 for each of worker.GRIDS, so a second transform never reads or overwrites the first's. Returns those paths by grid. Raises what check_job raises, naming the job T_JOB_FAR_FIELD."
  - **Body:**
    1. Read the job's job.json for `port` and `t_max`.
    2. Call `runs.write_job(runs.job_dir(job.parent, 0, f"nf2ff-{token}"), port, "nf2ff", 1, t_max, dumps=f"../{job.name}", out=f"nf2ff-{token}")`.
    3. Run it with one `runs.run_jobs([work], 1, job.parent, settings)`, with `settings = runs.load_settings()`.
    4. Call `runs.check_job(work, …, "T_JOB_FAR_FIELD", settings)`.
- [ ] **Step 6: The fake worker.** It imports `DUMPS` and `GRIDS` from `kicad_rf_studio.worker`.
  - When `"nf2ff" in spec`, `run` writes `b""` to each of `DUMPS`, beside `et` and `ht`. A job stopped by ABORT then keeps them, as openEMS 0.37.0 does (probed).
  - Before its `return run(job, spec)`, `act` handles mode `"nf2ff"`: it writes `b""` to `<dumps>/<out>-<grid>.h5` for each grid and returns 0. Task 6 makes these copies of the far-field fixture.
  - The docstring says so.
- [ ] **Step 7: The term.**
  1. Add `"T_JOB_FAR_FIELD": "far-field"` after T_JOB_CALIBRATION.
  2. Run `.venv/Scripts/python tools/catalog.py`.
  3. Set the msgstr to `"de campo distante"`, so that E_WORKER_FAILED reads "O processo de campo distante terminou com o código …".
  4. Run the tool again.
- [ ] **Step 8: Run them again.** `.venv/Scripts/python -m pytest tests/test_worker.py tests/test_sexpr.py tests/test_pool.py tests/test_run.py -q`. Expected: PASS. `test_sexpr`'s scan finds no job name written as a word.
- [ ] **Step 9: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(worker): the far-field transform in a worker mode beside the finished job, read_cached off and outputs named for the call, refused without all 12 dumps (Stage 3 design 5.5)"
graphify update .
```

---

### Task 4 [code]: The far-field reader and the efficiencies

**Files:**
- Create:
  - `tools/make_farfield.py`.
  - `src/kicad_rf_studio/core/post/farfield.py`.
  - `tests/test_post_farfield.py`.
  - `tests/fixtures/farfield/`, written by the tool: `sphere.h5`, `elevation.h5`, `azimuth.h5`, `waves.npz` and `reference.json`.
- Modify: `core/post/__init__.py`'s docstring; `core/messages.py`, after `W_LOSS_BUDGET` (L155); `po/*` and the `.mo`.

**Interfaces:**
- Consumes:
  - `p3a.dipole`, `p3a.HALF_MM` and `p3a.SHORT_MM`.
  - `pipeline.far_field`.
  - `p0.enter`, `run_model`, `model_of` and `run_path`.
  - `core.model.parts.Z0`.
  - For the tier (b) test: `runs.write_spec`, `write_job`, `job_dir`, `run_jobs` and `check_job`, and `worker.DUMPS`.
- Produces, in `core/post/farfield.py`:
  - `FarField`, a frozen dataclass of numpy arrays: `f` (F,) in Hz; `theta` (T,) and `phi` (P,) in degrees; `p_rad` (F,) in W; `d_max` (F,); and `d` (F, T, P), linear.
  - `read_far_field(path: Path) -> FarField`.
  - `port_powers(t_u, u, t_i, i, f) -> tuple[np.ndarray, np.ndarray]`, giving (P_acc, P_inc) of one port's 1-D records.
  - `efficiencies(sphere: FarField, p_acc, p_inc) -> dict[str, np.ndarray]`, with the keys `eta_rad`, `eta_tot`, `gain` and `realized_gain`, all linear.
  - `ETA_LIMIT = 1.02` and `eta_lines(f, eta_rad) -> list[tuple[str, dict]]`.
  - `W_ETA_RAD`.

- [ ] **Step 1: The probe step's tool, `tools/make_farfield.py`.** Its docstring: "Build tests/fixtures/farfield: the far field of a real run of tools/p3a.py's 58 mm dipole, recorded at 2.45 and 2.40 GHz. The run goes through the product's job phase (p0.run_model at Normal; its stop rule ends it with ABORT) and its transform (pipeline.far_field). The reader's tests use the fixture without openEMS. Dev-time only: it imports openEMS, so it runs with CSXCAD_INSTALL_PATH set, and the product never imports it. Run: python tools/make_farfield.py --out DIR, where DIR is a P0 folder outside every repository." It imports `argparse`, `json`, `shutil`, `Path`, `numpy as np`, `p0`, `p3a` and `pipeline`, and holds, as given (no test runs it, and its reference pins the reader):

```python
FAR = p0.FIX / "farfield"


def main(argv: list[str] | None = None) -> int:
    """Runs the 58 mm dipole in the P0 folder --out and writes FAR; 0 when done."""
    from openEMS.nf2ff import nf2ff_results  # here only: the product never imports openEMS
    from openEMS.utilities import DFT_time2freq

    parser = argparse.ArgumentParser(prog="make_farfield")
    parser.add_argument("--out", required=True, help="a P0 folder outside every repository")
    p0.enter(Path(parser.parse_args(argv).out))
    spec = p3a.dipole(p3a.HALF_MM, f_hz=[2.45e9, 2.4e9])
    run = p0.run_model(p0.model_of(spec), "normal", "farfield", [1])
    job = p0.run_path(run["run_dir"]) / run["jobs"][0]["job"]
    far = pipeline.far_field(job)
    FAR.mkdir(exist_ok=True)
    for grid, path in far.items():
        shutil.copyfile(path, FAR / f"{grid}.h5")
    shutil.copyfile(job / "waves.npz", FAR / "waves.npz")
    f = np.array(spec["nf2ff"]["f_hz"])  # the spec's float64 frequencies; the files store them as float32
    with np.load(job / "waves.npz") as w:
        u, i = DFT_time2freq(w["t_u"], w["u"][0], f), DFT_time2freq(w["t_i"], w["i"][0], f)
    u_inc, i_inc = (u + 50 * i) / 2, (i + u / 50) / 2  # ports.Port.CalcPort's, at its 50 Ω
    ref = {"f_hz": f.tolist(), "verdict": run["jobs"][0]["verdict"], "aborted": (job / "ABORT").is_file(),
           "blocked": [code for code, _ in run["blocked"]], "p_acc": (0.5 * np.real(u * np.conj(i))).tolist(),
           "p_inc": (0.5 * np.real(u_inc * np.conj(i_inc))).tolist()}
    for grid in far:
        res = nf2ff_results(str(FAR / f"{grid}.h5"))
        ref[grid] = {"d_max": np.asarray(res.Dmax).tolist(), "p_rad": np.asarray(res.Prad).tolist()}
    (FAR / "reference.json").write_text(json.dumps(ref, indent=1) + "\n", encoding="utf-8")
    return 0
```

- [ ] **Step 2: Make the fixture,** in one PowerShell call:

```powershell
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"  # typed here, never written into a file
.venv\Scripts\python.exe -X utf8 tools\make_farfield.py --out "$env:TEMP\krs-farfield"
"exit $LASTEXITCODE"
```

  Expected: `exit 0` after about 2 minutes, most of it the fresh folder's calibration. Then check:
  - `reference.json` reads `"verdict": "converged"`, `"aborted": true` and `"blocked": []`: ABORT ended the run, its dumps were there, and the setup gate blocked nothing.
  - The sphere's `p_rad[0] / p_acc[0]` is within 1 ± 0.02. The plan-mesh probe read 1.0004.
  - The folder holds about 310 KB.

  If η is outside 1 ± 0.02, stop the task for superpowers:systematic-debugging and a controller ruling, and delete `tests/fixtures/farfield` instead of committing it. Any other verdict, or a missing ABORT, is a finding for Task 7's report, and the fixture is still written. Delete `$env:TEMP\krs-farfield` afterwards.
- [ ] **Step 3: Write the failing tests,** `tests/test_post_farfield.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import shutil
import subprocess
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

import p3a
from kicad_rf_studio import pipeline, runs, worker
from kicad_rf_studio.core.post.farfield import efficiencies, eta_lines, port_powers, read_far_field

FAR = Path(__file__).parent / "fixtures" / "farfield"  # tools/make_farfield.py: a real 58 mm dipole, ended by ABORT
REF = json.loads((FAR / "reference.json").read_text(encoding="utf-8"))


def test_the_reader_reads_openems_0370s_far_field_layout():  # design 5.5; r3: the layout pinned by a real run
    s = read_far_field(FAR / "sphere.h5")
    assert np.allclose(s.f, REF["f_hz"], rtol=1e-6, atol=0)  # stored as float32
    assert np.allclose(s.theta, np.arange(0, 181, 5)) and np.allclose(s.phi, np.arange(0, 360, 5))  # degrees
    assert s.d.shape == (2, 37, 72)
    assert np.allclose(s.d_max, REF["sphere"]["d_max"], rtol=1e-12, atol=0)
    assert np.allclose(s.p_rad, REF["sphere"]["p_rad"], rtol=1e-12, atol=0)
    assert np.allclose(s.d.max(axis=(1, 2)), s.d_max, rtol=1e-6, atol=0)  # D = 4π·r²·P_rad(θ, φ)/Prad, openEMS's Dmax
    assert (s.d[:, [0, -1]] < 0.01 * s.d_max[:, None, None]).all()  # a z dipole's nulls on the z axis
    assert (s.d[:, 18].min(axis=1) > 0.99 * s.d_max).all()  # and its peak all round the θ = 90° ring


def test_the_cuts_are_the_three_principal_planes_at_f0():  # design 5.5: XZ and YZ as a θ sweep, XY as a φ sweep
    s, el, az = (read_far_field(FAR / f"{grid}.h5") for grid in ("sphere", "elevation", "azimuth"))
    assert np.allclose(el.f, s.f[:1], rtol=1e-6) and np.allclose(az.f, s.f[:1], rtol=1e-6)
    assert np.allclose(el.theta, np.arange(-180, 180)) and np.allclose(el.phi, [0, 90]) and el.d.shape == (1, 360, 2)
    assert np.allclose(az.theta, [90]) and np.allclose(az.phi, np.arange(360)) and az.d.shape == (1, 1, 360)
    assert np.allclose(el.p_rad, s.p_rad[:1], rtol=1e-9, atol=0)  # one surface integral, whatever the angles
    ring = az.d[0, 0]
    assert ring.min() > 0.99 * ring.max()  # round in XY
    assert np.allclose(el.d[0, [90, 270]], ring.max(), rtol=0.01) and (el.d[0, 180] < 0.01 * ring.max()).all()


def test_the_port_powers_are_openems_dft_over_the_whole_record():  # design 5.5: openEMS's convention, one window
    with np.load(FAR / "waves.npz") as w:
        p_acc, p_inc = port_powers(w["t_u"], w["u"][0], w["t_i"], w["i"][0], np.array(REF["f_hz"]))
    assert np.allclose(p_acc, REF["p_acc"], rtol=1e-12, atol=0) and np.allclose(p_inc, REF["p_inc"], rtol=1e-12, atol=0)


def test_a_half_wave_dipole_in_vacuum_radiates_what_its_port_accepts():  # design 5.5, 5.11
    s = read_far_field(FAR / "sphere.h5")
    with np.load(FAR / "waves.npz") as w:
        p_acc, p_inc = port_powers(w["t_u"], w["u"][0], w["t_i"], w["i"][0], s.f)
    e = efficiencies(s, p_acc, p_inc)
    assert np.allclose(e["eta_rad"], 1.0, atol=0.02) and np.allclose(e["eta_tot"], e["eta_rad"] * p_acc / p_inc)
    assert np.allclose(e["gain"], s.d_max * e["eta_rad"]) and np.allclose(e["realized_gain"], s.d_max * e["eta_tot"])
    assert eta_lines(s.f, e["eta_rad"]) == []


def test_eta_rad_above_1_02_is_flagged_at_its_worst_frequency():  # design 5.5
    f = np.array([2.45e9, 2.4e9, 2.5e9])
    assert eta_lines(f, np.array([1.0, 1.03, 1.025])) == [
        ("W_ETA_RAD", {"eta": "1.030", "f_mhz": "2400.0", "limit": "1.02"})]
    assert eta_lines(f, np.array([1.0, 1.02, 0.5])) == []


def test_a_far_field_file_in_another_layout_is_refused(tmp_path):  # r3: openEMS's legacy layout, or transposed
    legacy, transposed = tmp_path / "legacy.h5", tmp_path / "transposed.h5"
    for path in (legacy, transposed):
        shutil.copyfile(FAR / "elevation.h5", path)
    with h5py.File(legacy, "r+") as h5:  # openEMS's legacy layout: real and imaginary apart, stored (φ, θ)
        for name in ("E_theta", "E_phi"):
            fd = h5[f"/nf2ff/{name}/FD"]
            data = fd["f0"][()]
            del fd["f0"]
            fd["f0_real"], fd["f0_imag"] = data.real.T, data.imag.T
    with h5py.File(transposed, "r+") as h5:
        p = h5["/nf2ff/P_rad/FD/f0"][()]
        del h5["/nf2ff/P_rad/FD/f0"]
        h5["/nf2ff/P_rad/FD/f0"] = p.T
    for path in (legacy, transposed):
        with pytest.raises(ValueError, match="layout"):
            read_far_field(path)


def test_the_far_field_reader_loads_no_openems():  # Stage 1 3.1: only a worker imports it
    probe = "import sys, kicad_rf_studio.core.post.farfield; print(sorted({'openEMS', 'CSXCAD'} & set(sys.modules)))"
    assert subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True).stdout.strip() == "[]"


@pytest.mark.openems
def test_a_real_short_dipole_writes_its_dumps_and_its_far_field(tmp_path, monkeypatch):  # CI tier b; about 40 s
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    run = tmp_path / "run"
    runs.write_spec(run, p3a.dipole(p3a.SHORT_MM))
    job = runs.write_job(runs.job_dir(run, 1, "P1"), 1, "run", 2, 8e-9)  # past the pulse's end, 2·t0 = 5 ns
    runs.check_job(job, runs.run_jobs([job], 1, run, {})[job], "run", {})
    assert all((job / name).is_file() for name in worker.DUMPS)  # PML_8 and the box, under real openEMS
    s = read_far_field(pipeline.far_field(job)["sphere"])
    assert s.d.shape == (3, 37, 72) and np.isfinite(s.d).all() and (s.p_rad > 0).all()
```

- [ ] **Step 4: Run them.** `.venv/Scripts/python -m pytest tests/test_post_farfield.py -q`. Expected: FAIL with `No module named 'kicad_rf_studio.core.post.farfield'`.
- [ ] **Step 5: `core/post/farfield.py`.** Its docstring: "The far field (Stage 3 design 5.5): openEMS's transform files read with h5py; the port's powers over the recording's window; the efficiencies and gains; and their validity flag. Never imports openEMS."
  - **`read_far_field(path)`:** its docstring states the layout it reads:
    - `/Mesh/theta` and `/Mesh/phi`, in radians as float32 (returned in degrees, rounded to 1e-4), and `/Mesh/r`;
    - `/nf2ff`'s attributes `Frequency`, `Prad` and `Dmax`;
    - per frequency n, the real (θ, φ) dataset `P_rad/FD/f{n}`;
    - `d = 4π·r²·P_rad/Prad`.

    It raises `ValueError("… far-field layout …")`, naming the file, when `f0_real` is in `E_theta/FD` (the legacy layout) or a `P_rad` dataset is not (len θ, len φ). It reads no E dataset; plan 2 adds E_θ and E_φ with the far-field CSV. Comment it `# ponytail: openEMS 0.37.0's layout only; W_OPENEMS_UNTESTED warns outside 0.37.x`.
  - **`port_powers(t_u, u, t_i, i, f)`:**
    - It uses openEMS's `DFT_time2freq` for a pulse, each record on its own time axis: `X(f) = 2·Δt·Σ x·exp(−j2πft)`, with Δt = t[1] − t[0].
    - `P_acc = ½·Re(U·I*)`, and `P_inc = |U + Z0·I|²/(8·Z0)`, which is CalcPort's ½·Re(uf_inc·if_inc*) for a real Z0.
    - It covers the whole record, at the probes' rate. The frequency-domain dumps accumulate to the engine's last step, not to the cut, and at that same rate (over-sampling 4).
    - Probed: equal to CalcPort within 2e-16.
  - **`efficiencies`:** `eta_rad = p_rad/p_acc`, `eta_tot = p_rad/p_inc`, `gain = d_max·eta_rad` and `realized_gain = d_max·eta_tot`.
  - **`eta_lines(f, eta_rad)`:** one `W_ETA_RAD` line at the largest η_rad, when it is above ETA_LIMIT, with params `{"eta": f"{v:.3f}", "f_mhz": f"{f/1e6:.1f}", "limit": f"{ETA_LIMIT:g}"}`.
  - `core/post/__init__.py`'s docstring adds "the far field and the efficiencies (farfield)".
- [ ] **Step 6: The message.**
  1. Add `"W_ETA_RAD": "Radiation efficiency flagged: η_rad {eta} at {f_mhz} MHz is above {limit}, so the far field radiates more power than the port accepts, and the efficiencies and gains at that frequency are not reliable. A stricter preset or a wider air gap is the usual fix.",` after W_LOSS_BUDGET.
  2. Run the tool.
  3. Set the msgstr to "Eficiência de radiação sinalizada: η_rad {eta} em {f_mhz} MHz está acima de {limit}, então o campo distante irradia mais potência do que a porta aceita, e as eficiências e os ganhos nessa frequência não são confiáveis. Uma predefinição mais rigorosa ou um espaçamento de ar maior é a correção comum."
  4. Run the tool again.
- [ ] **Step 7: Run them again.** `.venv/Scripts/python -m pytest tests/test_post_farfield.py tests/test_worker.py tests/test_sexpr.py tests/test_repo.py -q`. Expected: PASS, with the tier (b) test skipped (no openEMS in the worker's Python without `CSXCAD_INSTALL_PATH`).
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add tools/make_farfield.py src tests po
git commit -m "feat(post): the far-field reader, P_acc and P_inc by openEMS's DFT over the recording's window, the efficiencies and W_ETA_RAD, on a fixture from a real dipole run (Stage 3 design 5.5)"
graphify update .
```

---

### Task 5 [code]: E_METAL_IN_PML

**Files:**
- Modify:
  - `core/model/spec.py`: `PML_CLEAR` and `metal_in_pml`, after `with_pml`.
  - `pipeline.py`: `setup_gate` after L260, and its docstring.
  - `core/messages.py`: after `W_UNUSED_PRIMITIVE` (L124).
  - `po/*` and the `.mo`.
- Test: `tests/test_model_spec.py` and `tests/test_run.py`.

**Interfaces:**
- Consumes: `PML_CELLS`, `p3a.dipole`, `p3a.SHORT_MM` and `p3a.HALF_MM`; `p0.model_of`; `pipeline.setup_gate(model, project, run_dir, settings, threads)`.
- Produces: `spec.PML_CLEAR = 2`; `spec.metal_in_pml(spec: dict) -> list[tuple[str, dict]]`; E_METAL_IN_PML among `setup_gate`'s blocking gates.

- [ ] **Step 1: Write the failing tests.** In `tests/test_model_spec.py` (imports gain `p3a`, `PML_CELLS`, `PML_CLEAR` and `metal_in_pml`):

```python
def test_metal_dielectric_or_a_port_within_the_pml_and_2_cells_is_refused():  # design 5.2; RF 5
    s = p3a.dipole(p3a.SHORT_MM)
    (x, y, z), k = (s["mesh"][a] for a in "xyz"), PML_CELLS + PML_CLEAR
    assert metal_in_pml(s) == [] and metal_in_pml(p3a.dipole(p3a.HALF_MM)) == []
    assert metal_in_pml({key: v for key, v in s.items() if key != "boundary"}) == []  # MUR: no absorber

    def line(axis, at, limit):
        return ("E_METAL_IN_PML", {"axis": axis, "at_mm": f"{at:.3f}", "limit_mm": f"{limit:.3f}"})

    def box(x0, x1, y0, y1, z0, z1):
        return {"x": [x0, x1, x1, x0], "y": [y0, y0, y1, y1], "z": [z0, z1]}

    def metal(**kw):
        return {**s, "metal": {**s["metal"], **kw}}

    def wire(z0):
        return metal(curves=[*s["metal"]["curves"], {"at": [0.0, 0.0], "z": [z0, -6.0]}])

    slab = {"name": "substrate_0", "eps": 4.3, "kappa": 0.0, "priority": 10,
            "solids": [box(x[2], 5.0, -5.0, 5.0, -1.0, 1.0)]}
    copper = box(0.0, x[-2], -1.0, 1.0, -1.0, 1.0)  # into the x-high absorber
    lid = {"plate": {**box(-1.0, 1.0, -1.0, 1.0, 0.0, 0.0), "z": z[-3]},
           "walls": [box(-1.0, 1.0, y[3], 0.0, -1.0, 1.0)]}
    part = {**s["ports"][0], "name": "C1", "dir": "x", "start": [x[1], 0.0, 0.0], "stop": [0.0, 0.0, 0.0],
            "R": None, "C": 1e-12}
    cases = [
        (wire(z[k]), []),  # on the limit's own line
        (wire(z[k - 1]), [line("z", z[k - 1], z[k])]),
        ({**s, "materials": [slab]}, [line("x", x[2], x[k])]),
        ({**s, "ports": [{**s["ports"][0], "stop": [0.0, 0.0, z[-2]]}]}, [line("z", z[-2], z[-1 - k])]),
        (metal(cylinders=[{"at": [x[k] + 0.1, 0.0], "r": 0.2, "z": [-1.0, 1.0]}]), [line("x", x[k] - 0.1, x[k])]),
        (metal(copper=[copper]), [line("x", x[-2], x[-1 - k])]),
        ({**s, "grid": [part]}, [line("x", x[1], x[k])]),
        ({**metal(curves=[{"at": [x[5], 0.0], "z": [-1.0, 1.0]}]), "materials": [slab]}, [line("x", x[2], x[k])]),
        (metal(copper=[copper], lid=lid),
         [line("x", x[-2], x[-1 - k]), line("y", y[3], y[k]), line("z", z[-3], z[-1 - k])]),
    ]
    for spec, lines in cases:  # each kind; one line per face, at its farthest intruder, x low to z high
        assert metal_in_pml(spec) == lines
```

  In `tests/test_run.py` (imports gain `p0` and `p3a`):

```python
def test_the_setup_gate_blocks_metal_within_the_pml(tmp_path, calibrated):  # design 5.2: a setup gate; RF 5
    def blocked(spec, name):
        model = p0.model_of(spec)
        return [code for code, _ in pipeline.setup_gate(model, {"gates": GATES}, tmp_path / name,
                                                          runs.load_settings(), 2)[1]]

    s = p3a.dipole(p3a.SHORT_MM)
    assert "E_METAL_IN_PML" not in blocked(s, "clear")
    s["metal"]["curves"].append({"at": [0.0, 0.0], "z": [s["mesh"]["z"][0], -6.0]})
    assert blocked(s, "deep").count("E_METAL_IN_PML") == 1
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_model_spec.py tests/test_run.py -q -k pml`. Expected: FAIL with `cannot import name 'PML_CLEAR'`.
- [ ] **Step 3: `metal_in_pml(spec)`.**
  - **Docstring:** "E_METAL_IN_PML (Stage 3 design 5.2), for each face of a `"boundary": "pml_8"` spec that metal, dielectric or a lumped element reaches within the PML or the PML_CLEAR cells just inside its inner edge. That band holds every coordinate below line PML_CELLS + PML_CLEAR, counted from either end of its axis; a coordinate on that line passes. Params: the axis, the farthest coordinate and that line, in mm. [] for any other spec."
  - **It reads:**
    - every material solid's x, y and z;
    - the same for `metal.copper` and `lid.walls`;
    - `lid.plate`'s x, y and z;
    - each cylinder's at ± r in x and y, and its z;
    - each curve's at and z;
    - each port's and grid part's start and stop.

    It skips probes, which are the P0 harnesses'.
  - **It returns** at most one line per face, at the farthest intruder, in the order x low, x high, y low, y high, z low, z high.
  - **`setup_gate`** gains `blocked += metal_in_pml(model.spec)`, and its docstring names the gate.
- [ ] **Step 4: The message.**
  1. Add `"E_METAL_IN_PML": "The model has metal, dielectric or a port within the PML or the 2 cells just inside its inner edge: along {axis} it reaches {at_mm} mm, past {limit_mm} mm. Copper or dielectric in the absorber makes the run unstable; widen the air gap around the board.",` after W_UNUSED_PRIMITIVE.
  2. Run the tool.
  3. Set the msgstr to "O modelo tem metal, dielétrico ou uma porta dentro da PML ou das 2 células logo depois dela: ao longo de {axis}, ele chega a {at_mm} mm, além de {limit_mm} mm. Cobre ou dielétrico no absorvedor deixa a execução instável; aumente o espaçamento de ar em volta da placa."
  4. Run the tool again.
- [ ] **Step 5: Run them again.** Step 2's command without `-k`, then `.venv/Scripts/python -m pytest tests/test_sexpr.py tests/test_cli_cost.py tests/test_golden_v1.py -q`. Expected: PASS. A v1 spec has no boundary key, so v1's gates and lines are unchanged.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(gates): E_METAL_IN_PML refuses metal, dielectric or a port within the PML and the 2 cells inside it (Stage 3 design 5.2)"
graphify update .
```

---

### Task 6 [code]: The P3-A gate tool

**Files:**
- Modify: `tools/p3a.py`; `tests/fake_worker.py`.
- Create: `tests/fixtures/p3a/references.json`.
- Test: `tests/test_p3a.py`.

**Interfaces:**
- Consumes:
  - From Tasks 2–5: `dipole`, `T_MAX`, `pipeline.far_field`, `worker.DUMPS`, `read_far_field`, `port_powers`, `efficiencies`, `eta_lines` and `PML_CELLS`.
  - From `p0`: `enter`, `step`, `records`, `run_model`, `model_of`, `run_path`, `save`, `table`, `versions`, `machine`, `predicted_s` and `FIX`.
  - From `pipeline`: `prepare`, `records` and `last_sample`.
  - From `runs`: `write_spec`, `write_job`, `job_dir`, `run_jobs`, `check_job`, `run_dir_for`, `load_settings`, `machine_key` and `per_job_mcs`.
  - `read_stats`, `growth_rise` and `spec_hash`.
- Produces:
  - `p3a.REFS`, `PRESET = "normal"`, `STEPS`, `WEIGHT_TOL = 0.25` and `SPEED_BAND = (0.67, 1.5)`.
  - `inset_box(spec, cells) -> list[list[float]]` and `specs() -> dict[str, dict]`.
  - `decide(m: dict) -> dict`, `measure(out: Path) -> dict`, `tables(result: dict) -> str` and `write(out: Path) -> dict`.
  - `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: The references,** `tests/fixtures/p3a/references.json`. Design §5.11 has them committed and never regenerated:

```json
{"source": "Stage 3 design 5.11, gate P3-A: a short dipole's D is 1.5 (1.76 dBi) and a half-wave dipole's 1.64 (2.15 dBi) (Balanis, ch. 4); PEC in vacuum radiates every watt its port accepts; the box moves 2 cells; no energy growth out to 3 × the stop time, T_max (Stage 1 6.4), read as a rise of at most 6 dB, well below the growth detector's 20 dB",
 "short_d_dbi": 1.76, "short_tol_db": 0.10, "half_d_dbi": 2.15, "half_tol_db": 0.15,
 "eta_rad": 1.0, "eta_tol": 0.02, "box_cells": 2, "box_db": 0.05, "growth_factor": 3, "growth_db_max": 6.0}
```

- [ ] **Step 2: Write the failing tests,** in `tests/test_p3a.py` (imports gain `json`, `math`, `p0` and `read_far_field`):

```python
def run(d, eta=1.0, verdict="converged", dumps=True, aborted=True, blocked=()):
    return {"verdict": verdict, "aborted": aborted, "dumps": dumps, "blocked": list(blocked), "d_dbi": d,
            "eta_rad": eta}


def free(growth=0.0, finite=True):
    return {"finite": finite, "growth_db": growth}


M = {"short": run(1.79), "half": run(2.16), "box2": run(2.14), "short_3x": free(), "half_3x": free(3.0),
     "pml": {"weight": 3.1}, "speed": {"ratio": 0.3}}  # near what the plan-mesh probes predict


def test_the_p3a_rules():  # design 5.11's P3-A row and 5.9's decisions, pre-registered
    d = p3a.decide(M)
    assert d["verdict"] == {"value": "pass", "fails": []}
    assert d["pml_weight"] == {"value": 3.1, "correction": True}
    assert d["small_speed"] == {"ratio": 0.3, "correction": True}
    calm = p3a.decide({**M, "pml": {"weight": 1.2}, "speed": {"ratio": 0.7}})
    assert not calm["pml_weight"]["correction"] and not calm["small_speed"]["correction"]
    for change, fails in [({"short": run(1.87)}, ["short_d"]), ({"half": run(1.99), "box2": run(2.0)}, ["half_d"]),
                          ({"half": run(2.16, eta=1.021)}, ["eta"]), ({"short": run(1.79, eta=0.979)}, ["eta"]),
                          ({"box2": run(2.22)}, ["box"]), ({"half_3x": free(6.5)}, ["growth"]),
                          ({"short_3x": free(finite=False)}, ["growth"]),
                          ({"box2": run(2.14, verdict="t_max")}, ["dumps_after_abort"]),
                          ({"half": run(2.16, aborted=False)}, ["dumps_after_abort"]),
                          ({"short": run(1.79, blocked=["E_METAL_IN_PML"])}, ["setup"]),
                          ({"short": run(None, eta=None, dumps=False)}, ["short_d", "eta", "dumps_after_abort"])]:
        assert p3a.decide({**M, **change})["verdict"] == {"value": "fail", "fails": fails}


def test_the_moved_box_sits_its_cells_inside_openems_own_placement():  # design 5.11: the box moved 2 cells
    s, k = p3a.dipole(p3a.HALF_MM), PML_CELLS + 1  # openEMS's placement under PML_8: line 9 (probed)
    assert p3a.inset_box(s, 0) == [[s["mesh"][a][k] for a in "xyz"], [s["mesh"][a][-1 - k] for a in "xyz"]]
    assert p3a.inset_box(s, 2) == [[s["mesh"][a][k + 2] for a in "xyz"], [s["mesh"][a][-3 - k] for a in "xyz"]]


def test_the_p3a_steps_run_through_the_harness_and_the_product(p0_out, monkeypatch):  # P0's harness, the fake worker
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    assert p3a.main(["--out", str(p0_out)]) == 0
    result = json.loads((p0_out / "p3a" / "p3a.json").read_text(encoding="utf-8"))
    sphere = read_far_field(p0.FIX / "farfield" / "sphere.h5")  # the fake's transform copies it
    assert result["half"]["d_dbi"] == pytest.approx(10 * math.log10(sphere.d_max[0]))
    assert (result["half"]["verdict"], result["half"]["aborted"], result["half"]["dumps"]) == ("converged", True, True)
    mur, again = p0.records(p0_out, ["p3a-half-mur", "p3a-half-3x"])
    assert mur["result"]["t_max"] == again["result"]["t_max"] == pytest.approx(3 * p3a.T_MAX)  # 3 × T_max, both twins
    assert (result["half_3x"]["finite"], result["half_3x"]["growth_db"]) == (True, 0.0)
    assert result["half_3x"]["run_dir"].startswith("p3a-half-3x-")  # a folder's name, never a path (privacy gate)
    d = result["decisions"]
    assert d["pml_weight"] == {"value": 1.0, "correction": False}  # the fake runs every job at 100 MC/s
    assert d["small_speed"] == {"ratio": 0.5, "correction": True}  # against the calibration's 400 MC/s / 2 jobs
    # every far field is the 58 mm fixture's, and the fake's dt (1e-13 s) trips E_DT_FLOOR on 0.5 mm cells
    assert d["verdict"] == {"value": "fail", "fails": ["short_d", "eta", "setup"]}
    assert (p0_out / "p3a" / "p3a.md").read_text(encoding="utf-8").startswith("## P3A-1")
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_p3a.py -q`. Expected: FAIL with `module 'p3a' has no attribute 'decide'`.
- [ ] **Step 4: The rules.**
  - **Constants:**
    - `REFS = json.loads((p0.FIX / "p3a" / "references.json").read_text(encoding="utf-8"))`;
    - `PRESET = "normal"`;
    - `STEPS = ("p3a-short", "p3a-half", "p3a-half-box2", "p3a-short-3x", "p3a-half-3x", "p3a-half-mur")`, in run order;
    - `WEIGHT_TOL, SPEED_BAND = 0.25, (0.67, 1.5)`, design 5.9's report-only decisions, pre-registered.
  - **`inset_box(spec, cells)`:** returns `[[spec["mesh"][a][PML_CELLS + 1 + cells] for a in "xyz"], [spec["mesh"][a][-PML_CELLS - 2 - cells] for a in "xyz"]]`, which is openEMS's own box under PML_8 moved `cells` lines inward.
  - **`specs()`:** keyed by step id:
    - p3a-short: `dipole(SHORT_MM)`;
    - p3a-half: `dipole(HALF_MM)`;
    - p3a-half-box2: half with `box=inset_box(half, REFS["box_cells"])`;
    - p3a-short-3x and p3a-half-3x: short's and half's specs;
    - p3a-half-mur: half with `boundary=None, box=inset_box(half, 0)`, the same mesh and box under MUR.
  - **`decide(m: dict) -> dict`**, pure. Its docstring is the rule; `test_the_p3a_rules` fixes the rest:

    "The P3-A row's checks (design 5.11) against REFS, each limit inclusive (|v − ref| ≤ tol) and a None value a fail, in this order: short_d and half_d, D in dBi at f0; eta, η_rad within REFS's band at every recorded frequency of both dipoles (m holds the value farthest from 1); box, the half-wave's D with its box moved REFS["box_cells"] lines against its own; growth, both 3× runs finite with growth_db at most REFS["growth_db_max"]; dumps_after_abort, the three base runs converged by the stop rule's ABORT, each with its 12 dumps and a far field read; setup, no base run's setup gate blocked. Then design 5.9's two decisions, report-only here (plan 2 applies them): a correction when |w_pml − 1| > WEIGHT_TOL, or when the small-model speed ratio leaves SPEED_BAND, neither for a None. Returns {check: {"pass"}, "pml_weight": {"value", "correction"}, "small_speed": {"ratio", "correction"}, "verdict": {"value": "pass" or "fail", "fails": the failed checks in order}}."

  Run `.venv/Scripts/python -m pytest tests/test_p3a.py -q -k "rules or moved_box"`. Expected: those two pass; the harness test still fails.
- [ ] **Step 5: The fake's transform.** In `tests/fake_worker.py`, mode `"nf2ff"` copies `tests/fixtures/farfield/<grid>.h5` to each output with `shutil.copyfile`, in place of the empty bytes. Its docstring says so.
- [ ] **Step 6: The harness.**
  - **Docstring:** add "Part 2: the steps, each resumable through p0.step and keyed by its spec's hash; the measurements; the pre-registered rules; p3a.json and p3a.md in <out>/p3a. Run: python tools/p3a.py --out DIR."
  - **A base step's work, `_far(spec, sid)`:**
    1. Run `run = p0.run_model(p0.model_of(spec), PRESET, sid, [1])`. Its one job's folder is `job`.
    2. Add `"dumps"`: whether every name in `DUMPS` is in `job`.
    3. Add `"aborted"`: whether an ABORT file is there, which only the stop rule's live watch writes.
    4. Add `"far"`. When the dumps are there and the job kept waves:
       - call `pipeline.far_field(job)` and read the sphere;
       - take `port_powers` over the job's whole waves.npz at `sphere.f`;
       - `"far"` holds `f_hz`, `d_max`, `p_rad`, `p_acc`, `p_inc`, the four `efficiencies` and `eta_lines`' lines.

       Otherwise `"far"` is None.
  - **A free step's work, `_free(spec, sid)`:** the worker's own path, with no stop rule, to `t_max = REFS["growth_factor"] * T_MAX` (90 ns: Stage 1 §6.4's worst-case stop time is T_max).
    1. `pipeline.prepare` for the threads.
    2. A fresh `runs.run_dir_for(sid)`, then `write_spec`.
    3. One `write_job(job_dir(run_dir, 1, "P1"), 1, "run", threads, t_max)`.
    4. `run_jobs` with no watch, then `check_job` named `"run"`, a tool's own word.
    5. Remove `et` and `ht`. Read the stats (`read_stats` of `openEMS_stats.txt`, which openEMS and the fake both write), then the records (`pipeline.records` at the stats' dt).
    6. Return `{"run_dir": run_dir.name, "t_max", "t_stop", "dt", "speed_mcs", "finite", "growth_db": growth_rise(rec, t0)}`.

    `run_dir` is a name, as run_model stores it, because the privacy gate refuses a path. `"finite"` is whether every u, i and energy sample is finite. Its key is `f"{spec_hash(spec)}@{t_max!r}"`.
  - **`measure(out)`** builds `m` from `p0.records(out, list(STEPS))` and one calibration entry, read as p0c does: this machine's in `runs.load_settings()`. The first step's prepare stored it, and run_model never refreshes it.
    - For `short`, `half` and `box2`, it keeps `{"verdict", "aborted", "dumps", "blocked", "d_dbi", "eta_rad", "warnings", "cells", "dt", "t_stop", "wall_s", "speed_mcs", "predicted_s"}`:

      | Key | What it holds |
      |---|---|
      | `blocked` | the setup gate's codes |
      | `d_dbi` | at f0, the first frequency |
      | `eta_rad` | the value of `efficiencies`' η_rad farthest from 1 |
      | `warnings` | run_model's codes and eta_lines' |
      | `cells` | Π len(mesh lines), as cost counts |
      | `dt` | the setup's |
      | `wall_s` | run_model's, the job phase |
      | `speed_mcs` | `run["speeds_mcs"][0]` |

      Without a far field, `d_dbi` and `eta_rad` are None.
    - `short_3x`, `half_3x` and `mur` keep their step's result, plus `"cells"`, `"wall_s"` (the step's) and `"predicted_s"`.
    - `predicted_s` is `p0.predicted_s(1, 1, cells, dt, t_stop, runs.per_job_mcs(entry, 1))`.
    - `"pml": {"cells", "pml_cells", "weight"}`:
      - `pml_cells = cells − Π(n − 2·(PML_CELLS + 1))`: the nodes openEMS's UPML updates, PML_CELLS + 1 lines per face (`operator_ext_upml.cpp`).
      - `weight = 1 + (mur's MC/s / half_3x's MC/s − 1)·cells/pml_cells`, from two free runs over the same steps.
    - `"speed": {"measured_mcs": mur's MC/s, "predicted_mcs": per_job_mcs(entry, 1), "ratio"}`: the MUR twin, so the PML's own cost is counted once, in w.
  - **`tables(result)`:** `p0.table` in three sections:
    - `## P3A-1 Checks`: each check, its limit and its value.
    - `## P3A-2 Runs`: each step's verdict, cells, D in dBi, η_rad, growth_db, wall_s, predicted_s and MC/s.
    - `## P3A-3 Decisions`.
  - **`write(out)`:** like `p0a.write`. It saves `<out>/p3a/p3a.json` through `p0.save` with `{"gate": "P3-A", "versions": p0.versions(), "references": REFS, "calibration", **m, "decisions": decide(m), "machine": p0.machine(...)}`, and writes `p3a.md` beside it. `"calibration"` holds only aggregate_mcs, pool, threads and levels, so no host name.
  - **`main(argv)`:** like `p0a.main`, with `--out` alone (required) and `p0.enter` first.
    - Each of STEPS goes through `p0.step` with its key and work: `_far` for the three base steps, `_free` for the other three.
    - A step that raises is printed, and the loop goes on.
    - It returns 1 when a step raised. Otherwise it calls `write(out)` and returns 0.
- [ ] **Step 7: Run them again.** `.venv/Scripts/python -m pytest tests/test_p3a.py tests/test_worker.py tests/test_p0.py tests/test_repo.py -q`. Expected: PASS. The fake run of all six steps takes about 30 s.
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add tools/p3a.py tests/test_p3a.py tests/fixtures/p3a/references.json tests/fake_worker.py
git commit -m "feat(tools): gate P3-A on synthetic dipoles through the product's job phase and transform, with the PML cell weight and the small single-job speed from free twins (Stage 3 design 5.9, 5.11)"
graphify update .
```

---

### Task 7 [run]: P3-A, its report and the amendments

This task commits the report, its JSON, the amendments and any fix a failure needs. Every other file it makes stays under `$env:TEMP`. Run each PowerShell block as one call.

- [ ] **Step 1: The suite at the branch tip.** Run the full suite in the background and wait for it. Then run the GUI tests in pt-BR (design §5.12, §5.14) in one call: `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass. Record the counts.
- [ ] **Step 2: Run P3-A,** in the background, waited on:

```powershell
$out = Join-Path $env:TEMP 'krs-p3a'
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"  # typed here, never written into a file
.venv\Scripts\python.exe -X utf8 tools\p3a.py --out $out *> "$env:TEMP\krs-p3a.log"
"exit $LASTEXITCODE" | Add-Content "$env:TEMP\krs-p3a.log"
```

  Expected: `exit 0` after about 30 minutes, most of it the three 90 ns free runs, with `$out\p3a\p3a.json` and `p3a.md`. The plan-mesh probes predict:
  - D 1.79 dBi (short) and 2.16 dBi (half-wave);
  - η_rad within 1 ± 0.001 at every recorded frequency;
  - ΔD about 0.02 dB for the moved box;
  - the dumps present after ABORT, and no setup gate blocking;
  - growth_db well under 6 dB on both 90 ns runs;
  - w about 3.1, and a small-speed ratio near 0.3.
- [ ] **Step 3: Read the gate:** `decisions`, every check, `machine` and every W_ line.
  - A failed check gets superpowers:systematic-debugging. A bug is fixed test-first in the module that owns it:
    1. a tier (a) test that fails first;
    2. the full suite;
    3. `git commit -m "fix(<area>): <what> (P3-A)"`;
    4. Step 2 again. `p0.step` reruns every step on the new code.
  - A threshold never changes (design §5.11). A miss that is not a bug stops the plan for a controller ruling, recorded in the report. For example: the short dipole's D just past 1.86 dBi while everything else passes, or a growth_db past 6 dB that is wander at the energy's floor rather than a sustained rise.
- [ ] **Step 4: The report,** `docs/validation/<the run's date, YYYY-MM-DD>-p3-a.md`, in the P0 reports' sections:
  1. Verdict.
  2. Inputs:
     - the command;
     - `versions`;
     - the calibration;
     - the dipoles: 12 and 58 mm, a 1 mm feed, a 0.5 mm cell, a 31.23 mm gap, the pulse over 1.85–3.0 GHz, and f_hz 2.45, 2.40 and 2.50 GHz over-sampled 4 times;
     - `<P3A>` for the folder.
  3. Measured value against limit (P3A-1, P3A-2).
  4. Decisions:
     - the PML weight: two free runs over the same 90 ns, with N_PML as openEMS's UPML counts it;
     - the small single-job speed, from the MUR twin;
     - whether plan 2 adds a correction.
  5. Stated limits and deviations:
     - the λ/10 short dipole, and why not λ/20;
     - f1 ≤ f ≤ f2 with over-sampling 4, and why the default rate aliases toward f2;
     - D judged at f0 and η at every recorded frequency;
     - the moved box on the half-wave only, and its margin;
     - the finite-length theory values, 1.775 dBi (12 mm) and 2.108 dBi (58 mm, 0.474 λ), beside the references, so the measured offsets are not read as pipeline error;
     - "3 × the stop time" read as 3 × T_max, and the 6 dB growth limit.
  6. Machine time: predicted against measured, per run and in total.
  7. Next step: plan 2.

  Copy `$out\p3a\p3a.json` to `docs/validation/<date>-p3-a.json`; it holds no path and no host name.
- [ ] **Step 5: The amendments,** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`:
  - **A-23, §2's table (L74):** stage 3's last cell, `Later`, becomes `` `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md` (A-23, Stage 3 plan 1: controller recommendation, owner unavailable.) ``.
  - **A-24, §5.1:** a bullet after the PML_8 bullet (L250): "- **The antenna boundary** (Stage 3): a model spec written for an antenna holds `"boundary": "pml_8"`: PML_8 on all six faces, its 8 cells added outside the air box at the outer cell size. A spec without the key, as every v1 spec is, keeps MUR on all six faces, so the two are never mixed. A setup gate, E_METAL_IN_PML, refuses a model with metal, dielectric or a lumped port within the PML or the 2 cells just inside its inner edge. (A-24, Stage 3 plan 1: controller recommendation, owner unavailable.)"
  - **A-25:** a new `### 9.8 P3-A: far-field sanity (Stage 3)` after §9.7's last bullet (L625), before the `---` above §10:

    "Stage 3's first gate (Stage 3 design §5.11), run by `tools/p3a.py`. Synthetic z-directed PEC wire dipoles in vacuum under PML_8, with no board, each fed by a 50 Ω lumped port across a 1 mm gap, run through the product's job phase at Normal and its far-field transform. The pulse spans 1.85–3.0 GHz, the far field is recorded at 2.45, 2.40 and 2.50 GHz with an over-sampling of 4, and the air gap is λ/4 at 2.40 GHz. The cases are a short dipole of 12 mm (λ/10 at f0 = 2.45 GHz) and a half-wave dipole of 58 mm. Pass: at f0, the short dipole's D within 1.76 ± 0.10 dBi and the half-wave's within 2.15 ± 0.15 dBi; at every recorded frequency, η_rad within 1 ± 0.02 on both; the half-wave's far-field box moved 2 lines inward changes D by no more than 0.05 dB; each dipole run free to 3 × T_max (90 ns) with every sample finite and its energy's rise over its running minimum at most 6 dB; every base run the stop rule ended with ABORT still writes its 12 far-field dumps, which the transform reads; and no base run's setup gate blocks. The references are `tests/fixtures/p3a/references.json`. A failure is a pipeline bug, which blocks Stage 3 until it is fixed. The gate also measures a PML cell's cost against an ordinary cell's, from a MUR twin on the same mesh run free over the same steps, and a small single-job model's speed against the calibration (Stage 3 design §5.9). Result on <date>: <pass, or the ruling>, `docs/validation/<date>-p3-a.md`. (A-25, Stage 3 plan 1: controller recommendation, owner unavailable.)"
  - **The Status line (L4)** gains, at its end: " On <date>, Stage 3's plan 1 amended §2, §5.1 and §9 (A-23 to A-25) the same way."
- [ ] **Step 6: Commit.**

```bash
git add docs/validation/<date>-p3-a.md docs/validation/<date>-p3-a.json docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs(validation): gate P3-A <passed> on synthetic dipoles under PML_8; Stage 1 spec A-23 to A-25 (Stage 3 design 5.11; controller recommendation, owner unavailable)"
graphify update .
```

- [ ] **Step 7: Close.**
  1. Run the whole-branch review.
  2. Run Step 1 again after any later commit.
  3. Fast-forward `main` to the branch locally, then delete the branch.
  4. Delete `$env:TEMP\krs-p3a` and its log.

  Nothing is pushed.

---

## Not in this plan

- **Plan 2, the antenna project:**
  - schema 2 and `new --antenna`;
  - the footprint classes, the antenna group, its net and its join;
  - the whole-board domain, the air box and its mesh, with the air gap as a project field;
  - the measured region and the parts off the chain;
  - the antenna's T_max and flat window;
  - fit2d on the feed network;
  - cost's cell split, carrying P3-A's PML-weight and small-speed decisions and counting PML nodes as openEMS does (design §5.9; plan 1 has no antenna cost line to correct);
  - the two fixtures;
  - an M = 0 run that calls `far_field` and writes §5.6's files with W_ETA_RAD, and the far-field CSV with E_θ and E_φ, which the reader then adds;
  - the far-field frequencies and angle step as project fields, with a user-facing refusal;
  - the amendments to §1.1, §6.3, §6.4 and §10.
- **Plan 3:** every chain part a port; the one-port retune and verify; the far field in verify; `compare`.
- **Plan 4:** gates P3-B to P3-E; P3-F stays the owner's.
- **Plan 5:** the GUI, the button, the README tutorial and the exit record.
- **verify.s{P}p's bytes among the pins:** no committed run holds verify's waves. verify's model spec is pinned (lpf915) with a stand-in C_box.
- **Two far-field boxes in one run:** the moved box is a second run on the same mesh.
- **Output pins in another environment:** they are compared only where `golden_v1.env()` matches the recording: this PC's platform, CPU and numeric stack, in English. Everywhere else, CI's Windows and Linux jobs included, only the model digests are compared.

## Controller rulings (2026-10-29; binding)

These are the architect's rulings, revised after four reviews. Each is a controller recommendation made while the owner is unavailable.

- Ruling: the tasks run in this order:
  1. the golden pins, before any code change;
  2. the spec keys, the boundary, `pulse`, `with_pml` and the dipoles;
  3. the transform;
  4. the reader, on a fixture made through Tasks 2–3's real path, so that the first real far-field run comes before the gate;
  5. E_METAL_IN_PML;
  6. the gate tool;
  7. the run.

  — design §5.12 item 1 and §4 — cost if wrong: a reorder.
- Ruling: the golden pins.
  - **The cases:** the three fixtures `new` traces at v1's defaults: lpf915 and lpf915-45 at a 2.5 mm lid (lpf915-45 with `allow_curve_port`), and coupon_gcpw_pads. Each board is copied into the working folder, so project.json's relative path and `new`'s lines are the same everywhere. That keeps W_ABSOLUTE_BOARD_PATH out on CI's Windows runner, whose checkout and temp folder sit on two drives.
  - **Pinned for each case:** `spec_hash`, `model.json`'s bytes, project.json's bytes, and `new`'s lines but I_WROTE.
  - **Also pinned:**
    - verify's model spec of lpf915, by `verify_spec` at dt 1e-13 s, with the dump's reader stood in for at 2e-14 F as `tests/fake_cli.py` does, since plan 3 rewrites verify. lpf915-45 is E_VERIFY_CURVE and the coupon E_VERIFY_NO_PARTS.
    - `calibration_spec`.
    - `write_outputs`' files and lines for lpf915 and coupon_gcpw_pads, built from the committed traces with every job converged at its trace's cut and C_box 2e-14 F.
  - **Language:** the tool records in English, the suite's language. summary.png's labels are rendered, and a pt_BR process (this PC's default) draws other bytes.
  - **Where outputs compare:** only where `golden_v1.env()` matches: platform, CPU, the numpy, scipy, matplotlib and scikit-rf versions, and the language. The Touchstone files carry scikit-rf's version, summary.png matplotlib's, and the floats this CPU's BLAS bits.
  - **Where models compare:** everywhere, as `test_p0d_refs` already compares model hashes on every CI job (D-47). `test_p0d_refs` keeps pinning the P0 coupon models.
  - The revised prototype gave identical digests in two folders, in 4.1 s.

  — design §3 and §4 — cost if wrong: a CI job whose shapely or numpy builds another model fails here and in `test_p0d_refs` until a ruling, and any dependency upgrade on this PC turns the output comparison off.
- Ruling: the spec keys.
  - `"boundary": "pml_8"`. Its absence means MUR, and any other value raises a KeyError.
  - `"nf2ff": {"f_hz", "center", "box"?}`. The centre is in mm and is converted to metres for `CalcNF2FF`, as openEMS's tutorials pass it. `"box"` exists only for P3-A's moved box and MUR twin.
  - The default placement is openEMS's own: line 9 under PML_8, probed.

  — design §5.2 and §5.5 — cost if wrong: one key renamed in plan 2.
- Ruling: `build_csx` records the far field with `over_sampling=4`. It refuses far-field frequencies outside f1 ≤ f ≤ f2, or more than 11 of them, with a ValueError: a crash, reported as E_WORKER_FAILED.
  - **Why:** openEMS 0.37.0 accumulates a frequency-domain dump at the plain Nyquist rate of f2 unless a per-dump over-sampling is set (`openems.cpp` L667–682, `processing.cpp` L172). So each frequency picks up its alias at 2·f2 − f, worse toward f2. On the plan's 12 mm dipole, all inside the old f < f2 guard:

    | Frequency (f2 = 3.0 GHz) | η_rad | D |
    |---|---|---|
    | 2.9 GHz | 0.952 | 0.30 dB low |
    | 2.99 GHz | 1.351 | 0.97 dB low |
    | f2 itself (architect's probe) | 3.3 | |

    W_ETA_RAD flags only values above 1.02, so it misses the 0.952.
  - **The fix:** CSXCAD 0.7.0's dump box takes `over_sampling`, and `CreateNF2FFBox` forwards it. openEMS then accumulates every Nyquist/4 steps, the port probes' own rate. On the same run and box, from 2.45 to 2.99 GHz, η_rad stayed within 1 ± 0.0013 and D within 0.03 dB of each other. The design's [f1, f2] then holds as written.

  — design §5.5 — cost if wrong: one keyword and one comparison.
- Ruling: the transform is the worker mode "nf2ff".
  - It runs in its own folder beside the job, job-0-nf2ff-<token>, and reads the dumps through `"../<job>"`.
  - It makes three `CalcNF2FF` calls, all with `read_cached=False`, writing `<job>/nf2ff-<token>-<grid>.h5`:
    - the sphere at 5° over every recorded frequency;
    - the elevation, θ −180…179 at φ 0 and 90;
    - the azimuth, φ 0…359 at θ 90.

    Both cuts are at 1° and at f0.
  - `build_csx` returns the box, and the worker checks all 12 dumps first. It rebuilds the whole CSX for openEMS's box; a `ponytail:` comment marks that for plan 2's whole board.
  - The fake's transform writes empty files (Task 3) and copies the reader's fixture once it exists (Task 6).
  - Probed:
    - a separate-process transform in this layout works;
    - negative θ works;
    - an unrecorded frequency raises "CalcNF2FF:: Unable to analyse files!";
    - FD dumps are written after ABORT on 0.37.0.

  — design §3 and §5.5 — cost if wrong: none.
- Ruling: the transform's job name is a term, T_JOB_FAR_FIELD ("de campo distante"), because `test_sexpr`'s scan refuses a word there — pt-BR design §5.1 — cost if wrong: none.
- Ruling: `pulse(f1, f2, t_max)` is factored out of `excitation`, because plan 2's band needs it. `with_pml` adds 8 lines at each end's outer cell, quantised to 1e-6 mm. The pins prove v1 unchanged — design §5.2 and §5.4 — cost if wrong: none.
- Ruling: P3-A's dipoles are z wires made of the spec's existing PEC `curves`.
  - **Geometry:** a 1 mm lumped port, a 0.5 mm cell, and air graded up to λ(f2)/20.
  - **Band and pulse:** the band is 2.40–2.50 GHz with f0 at 2.45 GHz, and the pulse runs over 1.85–3.0 GHz. The far field is recorded at [2.45, 2.40, 2.50] GHz, T_max is 30 ns, and the gap is λ/4 at f_lo.
  - **Lengths:** the short dipole is 12 mm (λ/10) and the half-wave 58 mm. At λ/20 the architect's probe read η_rad 0.971, with P_acc/P_inc at 3e-5, an ill-conditioned power balance.
  - **The plan's own mesh, probed through Tasks 2–3's path:**

    | Case | Result |
    |---|---|
    | 12 mm | D 1.789 dBi, η_rad 0.9999 |
    | 58 mm | D 2.157 dBi, η_rad 1.0004 |
    | Box moved 2 lines | ΔD 0.023 dB (half-wave), 0.018 dB (short) |
    | Normal cuts | 6.67 ns and 8.82 ns |

  - **Theory:** sinusoidal-current theory at f0 gives 1.775 dBi for 12 mm and 2.108 dBi for 58 mm (0.474 λ). The report states these beside the L → 0 and λ/2 references.

  — design §5.11, r1, r4 — cost if wrong: the short dipole's D has a 0.071 dB margin.
- Ruling: the checks are judged as follows.
  - **D:** at f0, on both dipoles.
  - **η_rad:** at every recorded frequency of both, by the value farthest from 1.
  - **Box:** moved 2 lines inward, on the half-wave only.
  - **Growth:** each dipole runs free through `runs.run_jobs` to 3 × T_max (90 ns). This reads the design's "3 × the stop time" with Stage 1 §6.4's worst-case stop time, since 3 × the Normal cuts (20 and 26.5 ns) would end before a product run may. It passes when every sample is finite and `growth_rise` is at most 6 dB. That limit is pre-registered as "no energy growth", well below the detector's provisional 20 dB (D-38).
  - **Dumps:** all three base runs ended converged, with the stop rule's ABORT in their folders, each with 12 dumps and a far field read.
  - **Setup:** no base run's setup gate blocked, since `run_model` records the gates and never applies them.

  — design §5.11, r4 — cost if wrong: one step, or about 15 minutes of machine time.
- Ruling: the PML cell weight and the small single-job speed.
  - **The weight:** `w = 1 + (s_MUR/s_PML − 1)·N/N_PML`, from two free runs over the same 90 ns: the half-wave under PML_8 (its growth run) and a MUR twin on the same mesh and box. Neither run's start-up then weighs more.
  - **N_PML** counts the nodes openEMS's UPML updates, PML_CELLS + 1 lines per face (`operator_ext_upml.cpp`). Plan 2's cell split must count the same way.
  - **The small single-job speed** is the MUR twin's against `per_job_mcs(entry, 1)`. The MUR twin ran 2.46× the PML run's speed on the 58 mm mesh, so this keeps the PML's own cost counted once, in w.
  - **Thresholds:** a correction is pre-registered as needed when |w − 1| > 0.25, or when the ratio leaves [0.67, 1.5]. Plan 2 applies it with the cost's cell split: plan 1 has no antenna cost line, and a change to v1's calibration would move v1's cost lines.

  — design §5.9 — cost if wrong: one constant in plan 2.
- Ruling: P3-A's harness.
  - It reads one calibration entry, as p0c does: this machine's in settings.json once the first step's prepare stored it (run_model never refreshes it). That entry serves every prediction.
  - A base run's wall_s is run_model's job phase, and a free run's is its step's.
  - `main` takes `--out` alone, since `p0.step`'s records already turn a rerun into an assembly.

  — design §5.11 and p0a's pattern — cost if wrong: a calibrate step added.
- Ruling: the reader.
  - It reads openEMS 0.37.0's layout only, and refuses the legacy split and transposed datasets.
  - It computes D from P_rad, returns angles in degrees to 1e-4, and returns the frequencies as stored (float32). It leaves E_θ and E_φ for plan 2's CSV.
  - P_acc and P_inc use openEMS's `DFT_time2freq` over the whole waves record. With over-sampling 4, that is the same window and the same sampling as the FD dumps. Checked against CalcPort to 2e-16.

  — design §5.5, r3 — cost if wrong: none.
- Ruling: the reader's fixture is a real 58 mm run through the product's path, made by `tools/make_farfield.py` (the `make_waves.py` pattern): 2 frequencies, about 310 KB.
  - `reference.json` comes from openEMS's own DFT, CalcPort's formulas and openEMS's reader, at the spec's float64 frequencies.
  - It records the verdict, the ABORT and the setup's blocked codes.
  - An η_rad outside 1 ± 0.02 stops the task, and no fixture is committed.

  — r3 — cost if wrong: one fixture regenerated.
- Ruling: W_ETA_RAD names the worst frequency once, as W_PASSIVITY does. Plan 1 records it in P3-A; plan 2 prints it — design §5.5 — cost if wrong: none.
- Ruling: E_METAL_IN_PML joins `setup_gate`'s blocking list. It is pure geometry on the spec.
  - It covers materials, copper, the lid's walls and plate, vias with their radius, curves, ports and grid parts.
  - It reports one line per face, at the farthest intruder.
  - Its band lies below line 10 from either end, so line 10 itself passes.
  - Its test has one case per kind.

  — design §5.2 — cost if wrong: none.
- Ruling: the references are committed as `tests/fixtures/p3a/references.json` and never regenerated. They hold the design's P3-A row (D, η, the box's 2 cells and 0.05 dB, the factor 3) and the pre-registered 6 dB growth limit. Design §5.9's report-only thresholds stay in `p3a.py` — design §5.11 — cost if wrong: none.
- Ruling: one tier (b) test, `@pytest.mark.openems`, runs the short dipole to 8 ns through the real worker, the transform and the reader. CI's Linux tier b then exercises PML_8, the box and mode "nf2ff" (design §4). It is skipped wherever the worker's Python cannot import openEMS, this PC's suite included — Stage 1 §9.1's tier (b) — cost if wrong: about 40 s a night.
- Ruling: Task 7 also runs the GUI tests in pt-BR, since each plan leaves the suite green in both languages — design §5.12, §5.14 — cost if wrong: a minute.
- Ruling: the amendments. A-23 (§2's row), A-24 (§5.1's antenna boundary and E_METAL_IN_PML) and A-25 (§9.8, P3-A) land in Task 7, after the gate. §5.1's air-gap text, §1.1, §6.3, §6.4 and §10 are plan 2's — design §5.13 — cost if wrong: a paragraph moved.
- Ruling: this plan's pt-BR glossary, by §6.1's principles:

  | English | pt-BR |
  |---|---|
  | far field | "campo distante" |
  | radiation efficiency | "eficiência de radiação" |
  | total efficiency | "eficiência total" |
  | directivity | "diretividade" |
  | gain | "ganho" |
  | realized gain | "ganho realizado" |
  | absorber | "absorvedor" |
  | air gap | "espaçamento de ar" |
  | PML | stays "a PML" |

  — pt-BR design §6 — cost if wrong: a native speaker changes three msgstrs.
- Ruling (disclosure): the architect's probes ran only in a scratch folder, with the repo's venv and `CSXCAD_INSTALL_PATH`, one at a time, each under 5 minutes:
  - wire dipoles under PML_8 with FD NF2FF, each stopped by an ABORT file as the pool writes one: 12 mm on 1.9–2.9 GHz, then 6, 12 and 58 mm on 1.85–3.0 GHz;
  - a separate-process transform of the 58 mm run's dumps;
  - openEMS's P_acc against this plan's formula;
  - `golden_v1.digests()` run twice, and the dipole mesh.

  No suite ran, and nothing was written in the repo or its venv — cost if wrong: none.
- Ruling (disclosure): this revision's own checks also ran only in a scratch folder:
  - the revised `digests()` twice, in two folders: identical, 4.1 s, with English digests equal to the suite's;
  - openEMS-Project's v0.37.0 sources and the installed CSXCAD 0.7.0 binding, for `over_sampling` and the UPML's lines;
  - the reviewers' probe outputs: the plan-mesh spheres (D 1.7886, 2.1574 and 2.1346 dBi) and the over-sampling and MUR-twin runs.

  No suite ran, and nothing was written in the repo or its venv — cost if wrong: none.
