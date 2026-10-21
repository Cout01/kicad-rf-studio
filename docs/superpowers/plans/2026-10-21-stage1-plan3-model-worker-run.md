# Stage 1 · Plan 3: Model, Worker and Run Control — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a project's geometry and mesh into an openEMS model that isolated worker processes build and run, so that `cost` adds the setup-only gates and the cost model, `run` runs every excitation under the stop rule and records the results in `project.json`, and `preview`, `calibrate` and `setup-openems` work.

**Architecture:**
- `core.model` turns the Geometry, the Mesh, the part roles and the ports into a plain, hashed JSON model spec. `build_csx(spec)` is the only code that imports CSXCAD and openEMS, and it runs inside the worker.
- `kicad_rf_studio.worker` is one process per job (`run`, `setup` or `xml`), started as `<python> -I -u -m kicad_rf_studio.worker job.json` in its own job folder; it writes `waves.npz`, `setup.json` or `model.xml`.
- The orchestrator: `runs.py` (data folder, settings, version check, run folders, lock, events, job pool with STOP/ABORT, calibration), `pipeline.py` (gates in spec order, `cost`, `run`, `preview`) and `stoprule.py` (a pure function of the probe records). `cli.py` stays a thin front end.

**Tech Stack:** Python ≥ 3.11, shapely 2, numpy, scipy, h5py (openEMS's wheels need it), openEMS 0.37.0 and CSXCAD 0.7.0 (installed separately), stdlib `subprocess`/`json`/`zlib`/`base64`/`xml.etree`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`. This plan covers §3.1–3.4 (core.model, orchestrator, worker; `cost`, `run`, `preview`, `setup-openems`, `calibrate`; the files of §3.3; install and version check), the model side of §5.1–5.3, §5.5's timestep floor, §5.6–5.8, §6.1–6.4, the model hash of §7.8 (reuse by hash is plan 4's), the plan-3 checks of §8, the openEMS quirks of §11 and the stop-rule replay of CI tier (a) in §9.1.

**Stage 1 is split into five plans.** Each one ends in working, tested software:
1. Foundation and board import.
2. Geometry, mesh and the mesh gates, including the 2D Z0/εeff readout of `cost`.
3. Model, worker and run control: `cost`, `run`, `preview`, `calibrate` and `setup-openems` (this plan).
4. Co-simulation and results: `retune`, `verify`, the outputs and the validity indicators.
5. Validation gates P0-A to P0-D, the KiCad button pre-check and the reports.

**Branch:** work on `stage1-plan3`, from `main`. Commands assume the dev venv is active.

## Global Constraints

- **Python:** ≥ 3.11 (CI floor); every new `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`.
- **Dependencies:** runtime `shapely>=2.0`, `numpy`, `scipy`, `h5py`, `matplotlib`; dev `pytest>=8`; openEMS and CSXCAD are never declared (`setup-openems` installs them); scikit-rf waits for plan 4.
- **openEMS:** 0.37.0 with CSXCAD 0.7.0; the version check refuses openEMS < 0.37 or CSXCAD < 0.7, warns outside 0.37.x, and runs before `cost`'s setup part and before `run`, `preview` and `calibrate`.
- **Imports:** only worker processes import openEMS or CSXCAD, only inside `core.model.csx.build_csx`; the worker imports the stdlib, numpy, h5py, openEMS and CSXCAD only; the core never imports Qt.
- **Messages:** every user-visible string is a code with parameters in `core.messages` (English template = msgid) and says what to do next; events carry codes and parameters, never text; tests check `KrsError.code` and `.params`, never `match=`. No message field is named `code`: `render()` and `KrsError()` take the code as their first argument.
- **Units and frames:** mm, Hz, s; CSX delta unit 1e-3 m; the model spec uses the internal frame (x, −y), y up; `project.json`, messages and events use KiCad's frame, y down; every coordinate and mesh line sits on the 1e-6 mm grid.
- **Engine settings:** MUR on all six faces; `openEMS(EndCriteria=1e-15)`; `SetMaxTime` always; `SetCustomExcite(expr, f2, f2)`; TimeStepMethod/TimeStep/TimeStepFactor never set (method 3 stays); `exact_endcriteria` never passed and no `Run` keyword is `False` or `0`; `numThreads` always explicit; every worker gets `OPENBLAS_NUM_THREADS=1`.
- **Band and pulse:** f1 = f0/2, f2 = 1.1 × harmonics × f0, f_m = (f1 + f2)/2, f_w = (f2 − f1)/2, t0 = 9/(2π f_w), pulse `sin(2π f_m (t − t0))·exp(−(2π f_w t/3 − 3)²)·(t < 2 t0)`; dielectric κ = 2π·f0·ε0·εr·tanδ.
- **Gates and stop rule** (provisional, P0 retunes them): fit2d 3 % (`gates.fit2d_limit` 0.03); dt ≥ 0.8 × floor reference (`gates.dt_floor` 0.8); growth +20 dB; Draft −50 dB / 1e-2, Normal −60 dB / 2e-3, Strict −70 dB / 5e-4; residual window 2 ns, monitor lag 1 ns, flat within 1 dB over 5 ns.
- **Files:** run folders under `%LOCALAPPDATA%\kicad-rf-studio\runs\` (Windows) or `$XDG_DATA_HOME/kicad-rf-studio/runs/` (`~/.local/share` when unset), never in the system temp folder; `settings.json` next to `runs/`; `project.json.lock` next to `project.json`.
- **Cost model:** cells = Nx·Ny·Nz mesh lines, as openEMS counts them; RAM ≈ 170 MB per million cells per job + 50 MB per worker; no numeric constant for any particular PC.
- **Privacy:** synthetic data only; no drive, home or UNC path, e-mail address or private name in a committed file (log samples leave out openEMS's banner); `.npz` member names are generic.
- **Commits:** no co-author lines. **Language:** English.
- **Tests:** tier (a) runs without openEMS, on fakes and committed samples; tests needing openEMS carry `@pytest.mark.openems` and are skipped where `python -I -c "import openEMS"` fails. `pipeline.py` and `cli.py` import `from kicad_rf_studio import runs` and call `runs.X(...)`; `runs.run_jobs` calls `subprocess.Popen` and `time.sleep` through the module objects. Tests patch those module attributes.

## Review Focus

1. **A fresh machine whose worker cannot load openEMS's libraries** (CSXCAD_INSTALL_PATH unset, as r5 reproduced). Calibration is the first worker `cost` or `run` starts; a worker exit 2 must give `E_OPENEMS_DLL` and exit 2 after the 2D readout, never E_INTERNAL. One helper, `runs.check_job`, maps every job exit (calibrate, setup gate, preview). Tests: `test_a_failed_job_maps_to_one_coded_error` (Task 13), `test_a_fresh_machine_that_cannot_load_openems_gets_a_coded_refusal` (Task 17).
2. **Non-ASCII paths** (a user name in %LOCALAPPDATA%, a project folder "projeto ação"): run and job folder names are ASCII, the worker calls `Run(".")` from its job folder, AppCSXCAD gets a relative `model.xml`. Tests: `test_run_and_job_folder_names_are_ascii` (Task 12), `test_setup_mode_reads_the_log_and_the_dumps` and the tier-b `test_the_worker_on_a_tiny_model` under a parent named "usuário ação" (Task 10), `test_the_viewer_opens_a_relative_file_from_the_job_folder` (Task 19).
3. **A `project.json` hand-edited between `new` and `run`** in ways the schema accepts: a reference by pad name with an empty uuid resolves; a grid part that is not a C or R, or whose value does not read, gets a coded refusal. Tests: `test_a_reference_by_pad_name_alone` (Task 6), `test_a_grid_part_must_be_a_c_or_r_with_a_readable_value` (Task 7).
4. **A worker that dies mid-run** (out of memory, a C++ abort) after its records already meet a criterion: that job is "unclassified" with its log named, the others finish, the results are written, `run` exits 4. Test: `test_a_crashed_job_is_unclassified_and_the_others_finish` (Task 18).
5. **Ctrl+C while a worker is still in setup:** the worker is killed at once, no process outlives the orchestrator, the lock is released; `cost` exits 130, and `run` exits 130 before its jobs start and 4 after. Tests: `test_ctrl_c_kills_a_job_in_setup_and_leaves_no_process` (Task 13), `test_ctrl_c_during_the_setup_job_exits_130_and_leaves_no_process` (Task 17), `test_ctrl_c_in_the_job_phase_stops_the_run_and_frees_the_lock` (Task 18).

---

## File structure

```
pyproject.toml                                   # + h5py, matplotlib; the openems marker
README.md                                        # install: Windows (setup-openems) and Linux
tools/make_dumps.py                              # dev-time: the two VTK dump fixtures (needs openEMS)
src/kicad_rf_studio/cli.py                       # + run, preview, calibrate, setup-openems; cost moves to pipeline
src/kicad_rf_studio/runs.py                      # data folder, settings, version check, folders, lock, events, pool, calibration
src/kicad_rf_studio/pipeline.py                  # load, build_model, cost model, setup gate, cost, run, preview
src/kicad_rf_studio/stoprule.py                  # the stop rule (pure)
src/kicad_rf_studio/worker.py                    # the worker process
src/kicad_rf_studio/core/project.py              # make_project / check_project / read_project, GATES, ROLES
src/kicad_rf_studio/core/messages.py             # + codes
src/kicad_rf_studio/core/kicad/values.py         # decimal comma, RKM bound, part_kind, part_value
src/kicad_rf_studio/core/kicad/board.py          # dropped footprint copper, Bézier outline
src/kicad_rf_studio/core/kicad/shapes.py         # bezier_points
src/kicad_rf_studio/core/kicad/tracer.py         # signal_layer
src/kicad_rf_studio/core/geometry/__init__.py    # Geometry.masks, Geometry.protected
src/kicad_rf_studio/core/geometry/region.py      # band
src/kicad_rf_studio/core/mesh/__init__.py        # t_m from both masks
src/kicad_rf_studio/core/mesh/protect.py         # part pads of off-chain ports and grid parts
src/kicad_rf_studio/core/mesh/gates.py           # fit2d per side, E_FIT2D_SHORT, check_fit2d(limit, n), E_EDGE_LINT frame
src/kicad_rf_studio/core/model/__init__.py       # docstring only
src/kicad_rf_studio/core/model/parts.py          # roles, package presets
src/kicad_rf_studio/core/model/ports.py          # port ends, nominal boxes, placed boxes
src/kicad_rf_studio/core/model/spec.py           # excitation, materials, model spec, hash
src/kicad_rf_studio/core/model/readers.py        # openEMS logs, probes, statistics, VTK dumps, PEC pieces, C_box
src/kicad_rf_studio/core/model/csx.py            # build_csx: the only openEMS/CSXCAD import, inside the function
tests/fake_worker.py  tests/traces.py  tests/fixtures/dumps/{PEC_dump.vtp,operator_dump.vtr}  tests/test_*.py
```

## Decisions this plan fixes (spec §3.3)

| Decision | Task |
|---|---|
| `job.json`, `setup.json`, `waves.npz` | 10 |
| The model spec (port entries: Task 6) | 7 |
| `events.jsonl`, run and job folder names, the lock | 12 |
| CLI exit codes: 0 done, 1 internal error, 2 refusal, 3 a gate blocked, 4 a job's S not kept, 130 Ctrl+C (any command before `run`'s jobs start) | 17, 18 |
| project.json keys / its `results` | 4 / 18 |
| settings.json | 1, 14 |

**For the owner to confirm:**
- **Port direction:** the axis along which a port's two ends lie apart while their spans across it overlap; C-14's "axis of the larger separation" refuses lpf915's own P2.
- **The curve-port switch** is a top-level `allow_curve_port`, because `ports` is a list.
- **The gate's dt** is read from the setup log (6 digits), not from `openEMS_stats.txt` (C-17), which exists only after a real run.
- **The package presets** (ESL, ESR, parallel Cp) are this plan's typical values, provisional.
- **An inductor off the chain in the ROI** follows §5.7's Inductor row: open when it is a choke, else a port (one more run each); C-12 names only shunt chokes among RF-path parts.
- **"1,000pF" and "4,700pF" stay unreadable:** a comma before exactly three digits is also a US thousands separator (1 nF, not 1 pF), so it reads only after a lone 0 ("0,047uF"). This applies C-2's "ambiguous stays refused" to the "1–3 digits" rule.
- **The stop-rule numbers** (presets, growth, windows, lag) stay code constants; only the preset name and the two gate limits are in `project.json` (spec §1.1 says every default is written there).
- **A project without ports:** `cost` prints its 2D readout and `W_NO_PORTS`, then exits 0 (3 with a geometry gate).
- **NOTICE:** whether plan 2's wall rule (ROI + 4 mm + 8 coarse cells) is RFsim's "outer-wall rule" (spec §3.6) is unchecked.

---

### Task 1: Dependencies, the `openems` marker, settings, the version check and `setup-openems`

**Files:**
- Create: `src/kicad_rf_studio/runs.py`, `tests/test_runs.py`
- Modify: `pyproject.toml`, `README.md`, `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`, `tests/conftest.py`

**Interfaces:**
- Produces:
  - `runs.WINDOWS: bool = sys.platform == "win32"` (tests patch it).
  - `runs.data_dir() -> Path`: `%LOCALAPPDATA%\kicad-rf-studio` on Windows (`~/AppData/Local` when unset); elsewhere `$XDG_DATA_HOME/kicad-rf-studio` (`~/.local/share` when unset).
  - `runs.load_settings() -> dict` (no file → `{}`; not JSON → `E_SETTINGS_UNREADABLE {path, reason}`) and `runs.save_settings(data: dict) -> None`, on `data_dir() / "settings.json"`; `save_settings` creates `data_dir()` (`mkdir(parents=True, exist_ok=True)`), then writes through `core.project.save_project`.
  - `runs.install_command() -> str`: `"kicad-rf-studio setup-openems <openEMS folder>"` on Windows, else `"update_openEMS.sh <prefix> --python with this venv active (see README)"`.
  - `runs.openems_versions() -> tuple[str, str]`: `subprocess.run([sys.executable, "-I", "-c", PROBE], capture_output=True, text=True, timeout=120)` with `PROBE = "import importlib.metadata as m; print(m.version('openEMS'), m.version('CSXCAD'))"` (metadata only, no DLL load; `-I` sees what the worker sees); a non-zero exit raises `E_OPENEMS_MISSING {python, command}`.
  - `runs.check_openems() -> list[tuple[str, dict]]`: compares major.minor read with `(\d+)\.(\d+)`; raises `E_OPENEMS_OLD {openems, csxcad, command}` below openEMS 0.37 or CSXCAD 0.7; returns `[("W_OPENEMS_UNTESTED", {"openems", "command"})]` outside 0.37.x, else `[]`.
  - `runs.setup_openems(folder: Path) -> list[tuple[str, dict]]` and the command `kicad-rf-studio setup-openems DIR`.

- [ ] **Step 1: Write the failing tests** in `tests/test_runs.py`

```python
TAG = f"cp{sys.version_info[0]}{sys.version_info[1]}"


def package(tmp_path, tag=TAG):
    """A folder laid out like the official Windows package: openEMS.exe, and python/ with the two wheels."""
    d = tmp_path / "openEMS"
    (d / "python").mkdir(parents=True)
    (d / "openEMS.exe").write_bytes(b"")
    for name in ("openems-0.37.0", "csxcad-0.7.0"):
        (d / "python" / f"{name}-{tag}-{tag}-win_amd64.whl").write_bytes(b"")
    return d


@pytest.fixture
def calls(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: seen.append(cmd) or
                        subprocess.CompletedProcess(cmd, 0, "0.37.0 0.7.0\n", ""))
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")  # not created: save_settings makes it
    monkeypatch.setattr(runs, "WINDOWS", True)
    return seen


def test_setup_openems_installs_both_wheels_offline_and_records_the_folder(tmp_path, calls, capsys):
    pkg = package(tmp_path)
    assert main(["setup-openems", str(pkg)]) == 0
    assert calls[0] == [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--find-links",
                        str(pkg / "python"), "openEMS", "CSXCAD"]
    assert runs.load_settings() == {"openems_dir": str(pkg.resolve())}
    assert capsys.readouterr().out.splitlines()[-1] == render(
        "I_OPENEMS_INSTALLED", openems="0.37.0", csxcad="0.7.0", dir=str(pkg.resolve()),
        settings=str(tmp_path / "data" / "settings.json"))


def test_setup_openems_is_for_windows_only(tmp_path, calls, monkeypatch):
    monkeypatch.setattr(runs, "WINDOWS", False)
    with pytest.raises(KrsError) as e:
        runs.setup_openems(package(tmp_path))
    assert (e.value.code, e.value.params, calls) == ("E_SETUP_OPENEMS_WINDOWS", {}, [])


def test_setup_openems_needs_the_wheels_of_this_python(tmp_path, calls):
    pkg = package(tmp_path, tag="cp39")
    with pytest.raises(KrsError) as e:
        runs.setup_openems(pkg)
    assert (e.value.code, e.value.params, calls) == ("E_SETUP_OPENEMS_DIR", {"dir": str(pkg), "tag": TAG}, [])


@pytest.mark.parametrize(("out", "rc", "code", "params"), [
    ("0.37.0 0.7.0\n", 0, None, {}),
    ("0.38.1 0.7.2\n", 0, "W_OPENEMS_UNTESTED", {"openems": "0.38.1"}),
    ("0.36.2 0.7.0\n", 0, "E_OPENEMS_OLD", {"openems": "0.36.2", "csxcad": "0.7.0"}),
    ("0.37.0 0.6.9\n", 0, "E_OPENEMS_OLD", {"openems": "0.37.0", "csxcad": "0.6.9"}),
    ("", 1, "E_OPENEMS_MISSING", {"python": sys.executable})])
def test_the_version_check_reads_metadata_in_an_isolated_subprocess(monkeypatch, out, rc, code, params):
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: seen.append(cmd) or
                        subprocess.CompletedProcess(cmd, rc, out, ""))
    if code and code.startswith("E_"):
        with pytest.raises(KrsError) as e:
            runs.check_openems()
        got = [(e.value.code, e.value.params)]
    else:
        got = runs.check_openems()
    assert got == ([(code, {**params, "command": runs.install_command()})] if code else [])
    assert seen[0][:3] == [sys.executable, "-I", "-c"] and "import openEMS" not in seen[0][3]  # no DLL load


@pytest.mark.parametrize(("windows", "env", "expected"), [
    (True, {"LOCALAPPDATA": "/x/Local"}, "/x/Local/kicad-rf-studio"),
    (False, {"XDG_DATA_HOME": "/x/share"}, "/x/share/kicad-rf-studio"),
    (False, {}, "~/.local/share/kicad-rf-studio")])
def test_the_data_folder_is_per_user_never_temp(monkeypatch, windows, env, expected):  # spec 3.3
    monkeypatch.setattr(runs, "WINDOWS", windows)
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert runs.data_dir() == Path(expected).expanduser()


@pytest.mark.openems
def test_openems_imports_in_this_python():  # tier b: the dev venv after setup-openems
    assert runs.check_openems() == []
```

- [ ] **Step 2: Run** `python -m pytest tests/test_runs.py -q`. Expected: FAIL (`kicad_rf_studio.runs` missing).
- [ ] **Step 3: Implement.**
  - `pyproject.toml`: `dependencies = ["shapely>=2.0", "numpy", "scipy", "h5py", "matplotlib"]` (C-33: `--no-deps` leaves the wheels' needs to the app); `[tool.pytest.ini_options] markers = ["openems: needs openEMS importable in this Python (CI tier b)"]`.
  - `tests/conftest.py`:

```python
def pytest_collection_modifyitems(config, items):
    """@pytest.mark.openems tests run only where the worker's own interpreter imports openEMS (CI tier b)."""
    marked = [item for item in items if "openems" in item.keywords]
    if marked and subprocess.run([sys.executable, "-I", "-c", "import openEMS"], capture_output=True).returncode:
        for item in marked:
            item.add_marker(pytest.mark.skip(reason="openEMS does not import in this Python"))
```

  - `setup_openems(folder)`: off Windows `E_SETUP_OPENEMS_WINDOWS`; `E_SETUP_OPENEMS_DIR {dir, tag}` unless `folder / "openEMS.exe"` exists and `folder / "python"` holds `openems-*-{tag}-*.whl` and `csxcad-*-{tag}-*.whl` (tag `cp{major}{minor}`); pip as the test pins (`--no-index` stays: both names are unclaimed on PyPI), a non-zero exit → `E_SETUP_OPENEMS_PIP {exit_code}`; `settings["openems_dir"] = str(folder.resolve())`; returns `[("I_OPENEMS_INSTALLED", {...})]` from `openems_versions()`. The subcommand prints the notes.
  - Messages:
    - `E_SETTINGS_UNREADABLE`: "Cannot read {path}: {reason}. Delete it; setup-openems and calibrate write it again."
    - `E_OPENEMS_MISSING`: "openEMS is not installed for {python}. Install it: {command}"
    - `E_OPENEMS_OLD`: "This Python has openEMS {openems} and CSXCAD {csxcad}; kicad-rf-studio needs openEMS 0.37 and CSXCAD 0.7 or newer. Install them: {command}"
    - `W_OPENEMS_UNTESTED`: "openEMS {openems} is not 0.37.x, the version kicad-rf-studio is tested with, so results may differ. Install 0.37 for validated results: {command}"
    - `E_SETUP_OPENEMS_WINDOWS`: "setup-openems is for Windows. On Linux, build openEMS with update_openEMS.sh <prefix> --python while this venv is active (see README)."
    - `E_SETUP_OPENEMS_DIR`: "{dir} is not an openEMS package for this Python: it needs openEMS.exe and the openems and csxcad wheels for {tag} in its python folder. Give the folder of the official Windows package of openEMS 0.37."
    - `E_SETUP_OPENEMS_PIP`: "pip could not install the openEMS wheels (exit code {exit_code}). Read pip's output above, then run setup-openems again."
    - `I_OPENEMS_INSTALLED`: "Installed openEMS {openems} and CSXCAD {csxcad} from {dir}; the folder is recorded in {settings}."
  - `README.md` "Install": Windows: `py -3.14 -m venv <venv>`; `<venv>\Scripts\python -m pip install <clone of this repository>`; `kicad-rf-studio setup-openems <openEMS folder>` (the official package's folder, holding `openEMS.exe` and `python\`). Linux (Debian 12, Ubuntu 24.04 or Fedora, system Python ≥ 3.11): activate a venv, `pip install <clone>`, then upstream's `install_deps.sh` and `update_openEMS.sh <prefix> --python` with the venv active and the GUI build on (it builds AppCSXCAD).
- [ ] **Step 4: Run** `python -m pytest -q`. Expected: all pass; the `openems` test is skipped.
- [ ] **Step 5: Give the dev venv openEMS.** In PowerShell: `python -m pip install -e .[dev]`; `kicad-rf-studio setup-openems "$env:CSXCAD_INSTALL_PATH"` (on the dev PC that variable holds the official package's folder); `python -m pytest -m openems -q`. Expected: 1 passed. Later tasks' `openems` tests run in this venv.
- [ ] **Step 6: Commit.** `feat: add setup-openems, the openEMS version check and the openems test marker`

---

### Task 2: core.kicad carry-overs: part values, dropped copper, Bézier outline

**Files:**
- Modify: `src/kicad_rf_studio/core/kicad/values.py`, `board.py`, `shapes.py`
- Test: `tests/test_values.py`, `tests/test_board.py`, `tests/test_cli_new.py`

**Interfaces:**
- Produces:
  - `parse_value(text)`: right after NFKC, a comma between digits followed by 1–3 digits and then a prefix or unit letter is a decimal point ("4,7uF", "2,2k", "1,5nH", "0,047uF"; C-2), except exactly 3 digits after an integer part other than "0", which could be a thousands separator ("1,000pF" is None); "1,000", "4,7" and "100,50V" stay None. The RKM pattern takes at most 3 trailing digits and no digit after them, so "1n4148" is None.
  - `part_kind(ref: str) -> str | None`: "C", "L" or "R" when the reference's leading letters are exactly that.
  - `part_value(ref: str, text: str) -> float | None`: `parse_value`'s value when `part_kind(ref)` is set and the text names that part's unit (F, H or R) or none; else None.
  - `shapes.bezier_points(p0: XY, p1: XY, p2: XY, p3: XY, n: int = 32) -> list[XY]`: the cubic at s = k/n, k = 0…n.
  - The board reader warns `W_COPPER_DROPPED` for a `gr_text_box` on copper and for a footprint's `fp_text`, `fp_text_box` or `fp_curve` on copper (L-5); a `gr_curve` on Edge.Cuts joins the outline as a polyline of `bezier_points` (L-6).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize(("text", "value"), [
    ("4,7uF", 4.7e-6), ("4,7µF", 4.7e-6), ("2,2k", 2200.0), ("1,5nH", 1.5e-9), ("0,047uF", 4.7e-8),
    ("4n7", 4.7e-9), ("2k21", 2210.0), ("4R7", 4.7), ("1u0", 1e-6)])  # µ: the micro sign NFKC folds
def test_a_decimal_comma_and_rkm_read(text, value):  # C-2
    assert parse_value(text)[0] == pytest.approx(value, rel=1e-12)


@pytest.mark.parametrize("text", ["1,000", "1,000pF", "4,700pF", "4,7", "100,50V", "1n4148", "3.3.3pF"])
def test_ambiguous_values_stay_unreadable(text):
    assert parse_value(text) is None


@pytest.mark.parametrize(("ref", "text", "value"), [
    ("C1", "100n", 1e-7), ("L1", "15n", 1.5e-8), ("R1", "0R", 0.0), ("R2", "4k7", 4700.0), ("C12", "4,7uF", 4.7e-6),
    ("C1", "15nH", None), ("D1", "1N4148", None), ("FB1", "BLM18", None), ("CN1", "100n", None)])
def test_a_part_value_takes_its_kind_from_the_designator(ref, text, value):  # C-2, M-5
    assert part_value(ref, text) == (None if value is None else pytest.approx(value, rel=1e-12))


def test_part_kind():
    assert [part_kind(r) for r in ("C1", "L2", "R10", "D1", "CN1", "RF1")] == ["C", "L", "R", None, None, None]


def test_dropped_footprint_copper_warns(mini_board):  # L-5
    b = mini_board('(footprint "L:X" (layer "F.Cu") (uuid "f1") (at 0 0) (property "Reference" "X1") '
                   '(fp_text user "RF" (at 1 1) (layer "F.Cu") (uuid "t1")) '
                   '(fp_curve (pts (xy 0 0) (xy 1 1) (xy 2 1) (xy 3 0)) (layer "F.Cu") (uuid "c1"))) '
                   '(gr_text_box "RF" (start 0 0) (end 2 1) (layer "F.Cu") (uuid "b1"))')
    assert {(p["kind"], p["uuid"]) for c, p in b.warnings if c == "W_COPPER_DROPPED"} == {
        ("fp_text", "t1"), ("fp_curve", "c1"), ("gr_text_box", "b1")}


def test_a_bezier_on_edge_cuts_closes_the_outline(mini_board):  # L-6
    sides = "".join(f'(gr_line (start {a}) (end {b}) (layer "Edge.Cuts"))'
                    for a, b in (("0 0", "10 0"), ("0 0", "0 10"), ("0 10", "10 10")))
    b = mini_board(sides + '(gr_curve (pts (xy 10 0) (xy 10 3) (xy 10 7) (xy 10 10)) (layer "Edge.Cuts"))')
    assert b.outline is not None and b.outline.area == pytest.approx(100, abs=1e-3)
```

  Revise on purpose: `test_values.py::test_text_that_is_not_a_value_gives_none` drops "4,7uF", "0,1uF" and "2,2k" (they read now; "100,50V" stays); `test_cli_new.py::test_a_part_value_that_cannot_be_read_is_warned` writes C2 = "3.3.3pF" and expects `["3.3.3pF", "3.3pF", "0R"]` as the stored shunt values.
- [ ] **Step 2: Run** `python -m pytest tests/test_values.py tests/test_board.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**, spelling µ and Ω with the module's `_MU` and `_OMEGA`:
  - `_COMMA = re.compile(rf"^(\d+),(\d{{1,3}})(?=(?i:meg|ohm|[fhr])|[pnu{_MU}mkKMG{_OMEGA}])")`: a match whose second group has 3 digits and whose first is not "0" returns None; otherwise `_COMMA.sub(r"\1.\2", s)`, before the RKM substitution;
  - `_RKM = re.compile(rf"^(\d+)([pnu{_MU}mkKMGRr])(\d{{1,3}})(?!\d)")`;
  - `bezier_points`: B(s) = (1−s)³p0 + 3(1−s)²s·p1 + 3(1−s)s²·p2 + s³p3.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: read decimal commas and part kinds, warn about dropped footprint copper, close Bézier outlines`

---

### Task 3: Part roles and models

**Files:**
- Create: `src/kicad_rf_studio/core/model/__init__.py` (docstring: "The model a worker builds; only csx.py imports openEMS, inside build_csx."), `src/kicad_rf_studio/core/model/parts.py`
- Modify: `src/kicad_rf_studio/core/geometry/region.py`, `src/kicad_rf_studio/core/project.py` (`ROLES`)
- Test: `tests/test_model_parts.py`

**Interfaces:**
- Consumes: `part_kind`, `part_value` (Task 2); `build_region`, `f_max`; `Chain`, `Classes`, `Board`.
- Produces:
  - `region.band(project: dict) -> tuple[float, float]` = `(project["f0_hz"] / 2, f_max(project))`.
  - `core.project.ROLES = ("port", "copper", "open", "grid", "curve_port")` (stdlib module; `parts.py` imports it from there).
  - `parts.PRESETS: dict[str, tuple[float, float, float]]` (ESL H, ESR Ω, Cp F): `{"0201": (3e-10, 0.1, 2e-14), "0402": (5e-10, 0.1, 3e-14), "0603": (7e-10, 0.1, 5e-14), "0805": (9e-10, 0.1, 7e-14), "1206": (1.2e-9, 0.1, 1e-13)}` with `# ponytail: typical published magnitudes, provisional; plan 4 and P0 refine them`; `parts.Z0 = 50.0`.
  - `parts.model_of(lib_id: str) -> dict | None`: `{"package", "esl_h", "esr_ohm", "cp_f"}` for the first `0201|0402|0603|0805|1206` in the library id, else None.
  - `parts.srf(kind, value, model) -> float` (Hz): 1/(2π√(ESL·C)) for a C, 1/(2π√(ESL·Cp)) for an R, 1/(2π√(L·Cp)) for an L.
  - `parts.is_choke(value, model, f1, f2) -> bool`: |Z| ≥ 200·Z0 at each of 101 frequencies f1…f2, Z = (ESR + jωL) ∥ 1/(jωCp).
  - `parts.role(kind, value, model, dnp, angle, place, f1, f2) -> str`, `place` ∈ "series", "shunt", "other"; the first rule that holds (C-12, C-13, spec §5.7):
    1. DNP → "open".
    2. An R of value 0 → "copper".
    3. `place == "other"` and a C or R → "grid" when it has a value and a model, an angle that is a multiple of 90° and srf > 3·f2; else "open".
    4. `place == "other"` and not an L → "open".
    5. An angle that is not a multiple of 90° → "curve_port".
    6. A shunt or other L with a value and a model, and `is_choke` → "open".
    7. Otherwise → "port".
  - `parts.project_parts(board, chain, classes, roi, f1, f2) -> tuple[list[dict], list[dict], list[dict], list[tuple[str, dict]]]`: series, shunt, others, notes; each part `{"ref", "pads", "nets", "value", "dnp", "role", "model"}`; `others` are the two-pad parts (two netted copper pads on two nets, no connector or shield) with a pad in `roi` and neither pad on a chain net, in reference order; notes `("W_VALUE_UNREADABLE", {"refs"})` for C, L or R parts (any place, DNP included) whose value does not read, and `("W_PART_OPEN", {"refs"})` for `others` left open that are not DNP (refs sorted, comma-joined).

- [ ] **Step 1: Write the failing tests**

```python
def lpf_parts():
    board, p = project_of("lpf915", "U1.1", "J1.1")  # tests/test_gates.py
    zs = zstack(Stackup.from_json(p["stackup"]), board.copper_layers)
    roi = build_region(board, chain_of(p), p["ports"], zs, f_max(p)).roi
    return project_parts(board, chain_of(p), classify(board, p["classes"]), roi, *band(p))


def test_lpf915_roles_and_models():  # spec 5.7
    series, shunt, others, notes = lpf_parts()
    assert {q["ref"]: q["role"] for q in series + shunt + others} == {
        "C1": "port", "L1": "port", "R1": "copper", "C2": "port", "C3": "port", "R2": "open", "C4": "open"}
    assert [q["ref"] for q in others] == ["C4"] and [q["dnp"] for q in shunt] == [False, False, True]
    assert series[0]["model"] == {"package": "0402", "esl_h": 5e-10, "esr_ohm": 0.1, "cp_f": 3e-14}
    assert others[0]["model"]["package"] == "0603" and notes == [("W_PART_OPEN", {"refs": "C4"})]


C0402 = model_of("Capacitor_SMD:C_0402_1005Metric")


@pytest.mark.parametrize(("kind", "value", "dnp", "angle", "place", "expected"), [
    ("C", 1e-10, True, 0, "series", "open"),            # DNP
    ("R", 0.0, False, 0, "series", "copper"),           # 0R
    ("R", 0.0, False, 45, "shunt", "copper"),           # a turned 0R is still copper
    ("L", 1.5e-8, False, 45, "series", "curve_port"),   # rotated
    ("L", 1.5e-8, False, 0, "series", "port"),          # a series inductor is always a port
    ("C", 0.4e-12, False, 90, "other", "grid"),         # SRF 11.3 GHz > 3·f2 = 9.06 GHz
    ("C", 1e-12, False, 0, "other", "open"),            # SRF 7.1 GHz
    ("R", 1e3, False, 0, "other", "grid"),              # SRF 41 GHz
    ("L", 1e-6, False, 0, "other", "port"),             # spec 5.7: no choke (3.8 kΩ at f1), so a port
    (None, None, False, 0, "series", "port")])          # a diode on the path: a port with no model
def test_role(kind, value, dnp, angle, place, expected):
    assert role(kind, value, C0402 if kind else None, dnp, angle, place, 457.5e6, 3.0195e9) == expected


def test_a_choke_is_open_only_while_it_holds_200_z0_over_the_band():  # C-12, spec 5.7
    m = model_of("Inductor_SMD:L_0402_1005Metric")
    assert role("L", 10e-3, m, False, 0, "shunt", 0.5e6, 3.3e6) == "open"      # ≥ 31 kΩ, SRF 9.2 MHz
    assert role("L", 1e-6, m, False, 0, "shunt", 457.5e6, 3.0195e9) == "port"  # 3.8 kΩ at f1
    assert role("L", 10e-6, m, False, 0, "shunt", 457.5e6, 3.0195e9) == "port" # SRF 290 MHz: 1.8 kΩ at f2
```

- [ ] **Step 2: Run** `python -m pytest tests/test_model_parts.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `band`, `ROLES` and `parts.py` (kind from `part_kind`, value from `part_value`, angle from `Footprint.angle`). Message `W_PART_OPEN`: "Left open in the simulated region: {refs}. Their self-resonance from the package preset is below 3·f2, or they are chokes or not C, L or R; make one a port in project.json if it matters (each port adds a run)."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: assign part roles and package models (spec 5.7)`

---

### Task 4: The project schema and `new`

**Files:**
- Modify: `src/kicad_rf_studio/core/project.py`, `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`, `src/kicad_rf_studio/core/kicad/tracer.py`
- Test: `tests/test_project.py`, `tests/test_cli_new.py`, `tests/test_cli_cost.py` (`by_hand` writes through `make_project` with the computed classes, `others=[]`, `ports=[]`)

**Interfaces:**
- Consumes: `project_parts`, `band` (Task 3); `zstack`, `build_region`, `find_lid`.
- Produces:
  - `project.DEFAULT_PRESET, HARMONICS, BAND_FACTOR, T_MAX_S` (moved from cli.py); `project.GATES = {"fit2d_limit": 0.03, "dt_floor": 0.8}` with `# ponytail: provisional until P0-A confirms them` (C-10).
  - `project.make_project(board_path, board_sha256, f0_hz, stackup, classes, chain, others, ports, *, harmonics=HARMONICS, preset=DEFAULT_PRESET, lid_height_mm=None) -> dict`: every key — schema, board, f0_hz, harmonics, preset, band_factor, t_max_s, region `{"expand_h": EXPAND_H}`, mesh `{"n": MESH_N[preset]}`, stackup, lid_height_mm, `lid` (None), classes, chain, others, ports, `gates` (a copy of GATES), `allow_curve_port` (False).
  - `project.check_project(data: dict, path: Path) -> dict`: `KrsError("E_PROJECT_FIELD", path=str(path), field=..., expected=...)` for the first missing or mistyped field (C-3, R42), named with dots and `[k]`; never E_INTERNAL, never a silent misread. `project.read_project(path) = check_project(load_project(path), path)`.
  - `save_project` writes atomically: a temporary file next to the target, then `os.replace` (it creates no folder).
  - `tracer.signal_layer(board, pad) -> str`: the first layer of the pad holding a track of its net that touches it, else `pad.layers[0]` (M-6); `choose_reference` and `new` use it.
  - `new` (C-44, C-46, C-12): board → stackup → `zstack` → classes → chain → ports → `build_region` → `project_parts` → `find_lid` → `make_project` → write → print. So E_STACKUP_LAYERS, E_DIELECTRIC_THICKNESS and E_CHAIN_OFF_OUTLINE are refused before anything is written. When `find_lid(board, classes, region, zs, {"harmonics": h, "lid": None, "lid_height_mm": height})` returns E_LID_HEIGHT, `new` warns `W_LID_HEIGHT_MISSING {refs}` instead. `new` still refuses an existing `project.json` (R38).
  - What `new` prints: board.warnings, W_FILLS_AS_SAVED, I_STACKUP, I_CLASSES, I_CHAIN; one `I_PART` or `I_PART_NO_MODEL` per part (series, shunt, others); I_PORT ×2, I_F0, I_DEFAULTS, `I_LID {state}` ("on" when harmonics > 1, else "off"); then W_COPPER_WEIGHT, W_LID_HEIGHT_MISSING, W_VALUE_UNREADABLE (project_parts' note, L-7), W_PART_OPEN, W_NO_REFERENCE, W_F0_RANGE, W_ABSOLUTE_BOARD_PATH; I_WROTE.

Validated fields (numbers finite, a bool never a number, a whole number an `int` so 3.0 is refused):

| Field | Expected text |
|---|---|
| board, region, mesh, gates, classes, chain, stackup | an object |
| board.path, board.sha256, chain.start, chain.end, stackup.source, a layer's name, a port's name/signal/signal_uuid/layer, a part's ref/value | text |
| f0_hz, band_factor, t_max_s, region.expand_h, gates.fit2d_limit | a number above 0 |
| gates.dt_floor | a number above 0 and at most 1 |
| harmonics | a whole number above 0 |
| mesh.n | a whole number of 2 or more |
| preset | draft, normal or strict |
| lid_height_mm | a number above 0, or null ("lid": false leaves the lid out) |
| lid | true, false or null |
| allow_curve_port, a part's dnp | true or false |
| classes.* | a list of names, or null (computed from the board) |
| chain.nets | a list of names |
| stackup.layers | a list of layers; kind: mask, copper or dielectric; thickness_mm: a number of 0 or more; epsilon_r: a number above 0, or null; loss_tangent: a number of 0 or more, or null |
| chain.series, chain.shunt, others | a list of parts; pads and nets: two names; role: port, copper, open, grid or curve_port; model: null, or package (text) with esl_h, esr_ohm and cp_f (numbers of 0 or more) |
| ports | a list of ports; rule: connector, ic, copper or null; reference: a pad, a point or null |
| results (optional) | an object |

- [ ] **Step 1: Write the failing tests**

```python
KEYS = {"schema", "board", "f0_hz", "harmonics", "preset", "band_factor", "t_max_s", "region", "mesh", "stackup",
        "lid_height_mm", "lid", "classes", "chain", "others", "ports", "gates", "allow_curve_port"}
DELETE = object()


def edit(data, where, value):
    *path, last = where
    for key in path:
        data = data[key]
    if value is DELETE:
        del data[last]
    else:
        data[last] = value


def test_new_writes_every_key_and_reads_it_back(tmp_path):  # C-3, C-10, C-13, C-46
    code, pj = run_new(tmp_path, "--lid-height", "2.5")
    d = read_project(pj)
    assert code == 0 and set(d) == KEYS
    assert (d["lid"], d["gates"], d["allow_curve_port"]) == (None, {"fit2d_limit": 0.03, "dt_floor": 0.8}, False)
    assert d["chain"]["series"][0] == {"ref": "C1", "pads": ["C1.1", "C1.2"], "nets": ["RF_A", "RF_B"],
                                       "value": "100pF", "dnp": False, "role": "port",
                                       "model": {"package": "0402", "esl_h": 5e-10, "esr_ohm": 0.1, "cp_f": 3e-14}}
    assert [(p["ref"], p["dnp"], p["role"]) for p in d["chain"]["shunt"]][-1] == ("R2", True, "open")
    assert [(p["ref"], p["role"]) for p in d["others"]] == [("C4", "open")]


@pytest.mark.parametrize(("where", "value", "field", "expected"), [
    (["lid_height_mm"], 0, "lid_height_mm", 'a number above 0, or null ("lid": false leaves the lid out)'),
    (["chain"], DELETE, "chain", "an object"),
    (["harmonics"], "3", "harmonics", "a whole number above 0"),
    (["preset"], "Strict", "preset", "draft, normal or strict"),
    (["mesh", "n"], 3.0, "mesh.n", "a whole number of 2 or more"),
    (["classes", "shields"], "SH1", "classes.shields", "a list of names, or null (computed from the board)"),
    (["ports", 0, "reference"], DELETE, "ports[0].reference", "a pad, a point or null"),
    (["stackup", "layers", 1, "thickness_mm"], DELETE, "stackup.layers[1].thickness_mm", "a number of 0 or more"),
    (["f0_hz"], -915e6, "f0_hz", "a number above 0"),
    (["t_max_s"], 0, "t_max_s", "a number above 0"),
    (["gates", "dt_floor"], 1.5, "gates.dt_floor", "a number above 0 and at most 1"),
    (["chain", "series", 0, "role"], "lumped", "chain.series[0].role", "port, copper, open, grid or curve_port"),
    (["lid"], "yes", "lid", "true, false or null"),
    (["allow_curve_port"], 1, "allow_curve_port", "true or false")])
def test_a_bad_field_is_named_never_internal(tmp_path, where, value, field, expected):  # S-1, S-7, L-2
    _, pj = run_new(tmp_path, "--lid-height", "2.5")
    d = load_project(pj)
    edit(d, where, value)
    save_project(pj, d)
    with pytest.raises(KrsError) as e:
        read_project(pj)
    assert (e.value.code, e.value.params) == ("E_PROJECT_FIELD", {"path": str(pj), "field": field,
                                                                  "expected": expected})


def test_new_refuses_a_dielectric_with_no_thickness_before_writing(tmp_path, capsys, mini_board_file):  # C-44
    board = four_layer(mini_board_file, "", top='(material "FR4") (epsilon_r 4.3) (loss_tangent 0.02)')
    out = tmp_path / "p"
    assert main(["new", str(board), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "-o", str(out)]) == 2
    assert capsys.readouterr().err == render("E_DIELECTRIC_THICKNESS", layer="dielectric 1") + "\n"
    assert not out.exists()


@pytest.mark.parametrize(("extra", "warned"), [((), True), (("--harmonics", "1"), False),
                                               (("--lid-height", "2.5"), False)])
def test_the_lid_warning_follows_find_lids_condition(tmp_path, capsys, extra, warned):  # C-46, L-2
    run_new(tmp_path, *extra)
    out = capsys.readouterr().out.splitlines()
    assert (render("W_LID_HEIGHT_MISSING", refs="SH1") in out) == warned
    assert render("I_LID", state="off" if "1" in extra else "on") in out


def test_a_through_hole_port_takes_the_layer_its_track_reaches(tmp_path, mini_board_file):  # M-6
    tht = '(pad "1" thru_hole circle (at 0 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask") (net "SIG"))'
    smd = '(pad "1" smd rect (at 0 0) (size 1 1) (layers "B.Cu") (net "SIG"))'
    board = mini_board_file(
        f'(footprint "L:J" (layer "F.Cu") (uuid "j") (at 5 10) (property "Reference" "J9") {tht}) '
        f'(footprint "L:T" (layer "B.Cu") (uuid "t") (at 25 10) (property "Reference" "TP2") {smd}) '
        + SEG.format(5, 10, 25, 10, 0.3, "B.Cu", "SIG", "s"))
    out = tmp_path / "p"
    assert main(["new", str(board), "--start", "J9.1", "--end", "TP2.1", "--f0", "915MHz", "--stackup", "jlcpcb-2l",
                 "-o", str(out)]) == 0
    assert [p["layer"] for p in load_project(out / "project.json")["ports"]] == ["B.Cu", "B.Cu"]
```

  Revise on purpose in `tests/test_cli_new.py`:
  - `test_project_layout`: the key set is `KEYS`; parts gain `dnp`, `role`, `model`; `others` is `[C4]`.
  - `test_the_printed_summary`: after the I_CHAIN line, the I_PART lines "Part C1 100pF: port; package 0402, ESL 0.5 nH, ESR 0.1 Ω." and the like for L1, R1 (copper), C2, C3, R2 (open) and C4 (open, package 0603, ESL 0.7 nH); after DEFAULTS, `render("I_LID", state="on")`; then `render("W_PART_OPEN", refs="C4")`.
  - `test_the_lid_warning_names_the_shield`: expects `render("W_LID_HEIGHT_MISSING", refs="SH1")`.
  - `test_heavy_copper_is_warned_between_the_defaults_and_the_lid`: `lines[n - 1]` is the I_LID line and `lines[n + 1]` the W_LID_HEIGHT_MISSING line.
  - `test_ports_without_a_reference`: the expected stdout gains `render("I_LID", state="on")` after DEFAULTS.
  - `test_unreadable_values_are_one_warning_for_series_shunt_and_dnp_parts`: C2 "3,3pF" reads now and C4 "??" is an `others` part, so `warned == ["Cannot read the value of C4, L1, R2. Write values like 4.7pF, 4p7 or 15nH."]`.
- [ ] **Step 2: Run** `python -m pytest tests/test_project.py tests/test_cli_new.py tests/test_cli_cost.py -q`. Expected: the new and revised tests FAIL.
- [ ] **Step 3: Implement** the writer and reader, the atomic write, `signal_layer` and `new`'s order. Messages:
  - `E_PROJECT_FIELD`: "{path}: {field} is missing or is not {expected}. Fix it in a text editor, or re-create the project with `new`."
  - `E_LID_HEIGHT` (C-4): "Shield {refs} covers the simulated region but project.json has no lid_height_mm. Set lid_height_mm in project.json, or set \"lid\": false to leave the lid out."
  - `W_LID_HEIGHT_MISSING`: "Shield {refs} covers the simulated region and no --lid-height was given; set lid_height_mm in project.json before `run`, or \"lid\": false to leave the lid out."
  - `I_LID`: "Shield lid {state}: \"lid\": null in project.json means on when harmonics > 1; true or false forces it."
  - `I_PART`: "Part {ref} {value}: {role}; package {package}, ESL {esl_nh} nH, ESR {esr_ohm} Ω." (`:g`)
  - `I_PART_NO_MODEL`: "Part {ref} {value}: {role}; no package preset, so `retune` uses its ideal value."
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: write and validate the complete project.json in new`

---

### Task 5: Geometry and gate carry-overs

**Files:**
- Modify: `src/kicad_rf_studio/core/geometry/__init__.py`, `src/kicad_rf_studio/core/mesh/__init__.py`, `src/kicad_rf_studio/core/mesh/protect.py`, `src/kicad_rf_studio/core/mesh/gates.py`, `src/kicad_rf_studio/core/messages.py`, `src/kicad_rf_studio/cli.py` (`_cost` takes `geom.masks`)
- Test: `tests/test_gates.py`; `tests/test_mesh_rule.py` (its hand-built Geometry; `geom.mask` read as `geom.masks.get(sec.layer)`)

**Interfaces:**
- Produces:
  - `Geometry.masks: dict[str, MaskModel]` replaces `Geometry.mask`: `{<top copper>: F mask, <bottom copper>: B mask}`, F first, a side with no mask absent (M-4, C-6).
  - `protected_set(..., pads: tuple[str, ...] = ())`: extra part pads protected like the chain's; `build_geometry` passes the pads of `project.get("others", ())` whose role is port, curve_port or grid (spec §5.4 "the part pads", R3-069), and keeps the result as `Geometry.protected` (C-41).
  - `build_mesh`: `t_m = max((m.t_m for m in geom.masks.values()), default=0.0)`.
  - `fit2d` uses `geom.masks.get(sec.layer)` (C-7); a `ShortError` in the reference solve raises `KrsError("E_FIT2D_SHORT", net=, layer=)` (C-42, O-2).
  - `check_fit2d(fits, limit: float, n: int) -> None`: the worst section above `limit` raises `E_FIT2D` when n < 3, else `E_FIT2D_FINE` (C-43), with `{net, layer, err_pct: round(100·err, 2), limit_pct: f"{100*limit:g}", n}`; `FIT2D_LIMIT` is deleted.
  - `mesh_with_lint(geom, prot, n)` raises `E_EDGE_LINT {axis, edge_mm, reason, n}`: `edge_mm` in KiCad's frame (`0.0 - edge` for y), `reason` the hit's token with "_" read as " " ("on edge") (C-43, L-4).

- [ ] **Step 1: Write the failing tests** in `tests/test_gates.py`

```python
def twin(mini_board_file, line):
    """test_cli_cost's 0.6 mm GCPW of SIG on `line`, the plane on the other outer layer."""
    plane = "B.Cu" if line == "F.Cu" else "F.Cu"
    path = mini_board_file(EDGE + SEG.format(5, 10, 35, 10, 0.6, line, "SIG", "s") + zone(line, "GND", 0, 0, 40, 9.55)
                           + zone(line, "GND", 0, 10.45, 40, 20) + zone(plane, "GND", 0, 0, 40, 20))
    return build_geometry(load_board(path), mini())


def test_geometry_keeps_both_masks_and_the_protected_set_it_built():  # C-41, M-4
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2")
    g = build_geometry(board, p)
    assert {k: m.side for k, m in g.masks.items()} == {"F.Cu": "F", "B.Cu": "B"}
    assert g.protected == protected_set(board, chain_of(p), classify(board, p["classes"]), g.pieces,
                                        substrate_h(g.zs))
    assert via_rods(board, g.region.crop, g.zs, g.protected) == g.rods


def test_an_off_chain_part_made_a_port_is_protected():  # spec 5.4, R3-069
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2")
    c4 = board.pads("C4.1")[0].polygon  # on VDD: neither measured nor ground copper
    for role, inside in (("open", False), ("port", True)):
        g = build_geometry(board, {**p, "others": [{**p["others"][0], "role": role}]})
        assert g.protected.area["F.Cu"].buffer(1e-6).contains(c4) == inside


def test_fit2d_reads_each_section_under_its_own_sides_mask(mini_board_file):  # C-7
    refs = []
    for line in ("F.Cu", "B.Cu"):
        g = twin(mini_board_file, line)
        refs.append(fit2d(g, mesh_with_lint(g, g.protected, 2))[0].z0_ref)
    assert refs[1] == pytest.approx(refs[0], rel=1e-3)


def test_copper_on_the_line_at_the_reference_cut_is_a_gate(mini_board_file):  # C-42: never E_INTERNAL
    rect = '(gr_rect (start 4 14.95) (end 36 15.05) (stroke (width 0)) (fill yes) (layer "F.Cu") (uuid "r1")) '
    g = build_geometry(load_board(mini_board_file(SEG.format(5, 15, 35, 15, 0.3, "F.Cu", "SIG", "s") + rect)), mini())
    with pytest.raises(KrsError) as e:
        fit2d(g, mesh_with_lint(g, g.protected, 2))
    assert (e.value.code, e.value.params) == ("E_FIT2D_SHORT", {"net": "SIG", "layer": "F.Cu"})


def fit(err):
    s = Section("RF_B", "F.Cu", "x", (0.0, 0.0), (1.0, 0.0), 0.6, 0.15, 1.0, (0.5, 0.0))
    return Fit(s, 50.0, 50.0 / (1 + err), err)


@pytest.mark.parametrize(("n", "code"), [(2, "E_FIT2D"), (3, "E_FIT2D_FINE")])
def test_the_fit2d_advice_follows_n_and_the_limit_is_a_project_field(n, code):  # C-43, C-10
    with pytest.raises(KrsError) as e:
        check_fit2d([fit(0.044)], 0.03, n)
    assert (e.value.code, e.value.params) == (code, {"net": "RF_B", "layer": "F.Cu", "err_pct": 4.4,
                                                     "limit_pct": "3", "n": n})
    check_fit2d([fit(0.044)], 0.05, n)  # a raised gates.fit2d_limit lets it pass


BAD_Y = Mesh(np.array([0.0, 1.0]), np.array([-100.6, -100.4505, -100.3]), np.array([0.0, 1.0]), D, 0.01, {},
             {"x": [], "y": [(-100.4505, -1)]})


def test_the_edge_lint_names_a_y_edge_in_kicads_frame(monkeypatch):  # C-43, L-4
    monkeypatch.setattr(gates, "build_mesh", lambda *a, **k: BAD_Y)
    with pytest.raises(KrsError) as e:
        mesh_with_lint(None, None, 2)
    assert (e.value.code, e.value.params) == ("E_EDGE_LINT", {"axis": "y", "edge_mm": 100.4505,
                                                              "reason": "on edge", "n": 2})
```

  Revise on purpose: `geom_of` returns `(g, g.protected)`; every `check_fit2d(fits)` becomes `check_fit2d(fits, 0.03, 2)`; `test_remesh_failure_blocks` expects `{"axis": "x", "edge_mm": edge, "reason": "on edge", "n": 2}` and `str(e.value) == render("E_EDGE_LINT", axis="x", edge_mm=edge, reason="on edge", n=2)`; `test_fit2d_blocks_on_coarse_mesh` expects `{"net": "LINE", "layer": "F.Cu", "err_pct": 100.0, "limit_pct": "3", "n": 2}`; `test_check_fit2d_names_the_worst_section_over_3_percent` expects `{"net": "B", "layer": "F.Cu", "err_pct": 5.0, "limit_pct": "3", "n": 2}` and the new E_FIT2D text.
- [ ] **Step 2: Run** `python -m pytest tests/test_gates.py tests/test_mesh_rule.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Messages:
  - `E_EDGE_LINT`: "A mesh line sits badly at the copper edge {edge_mm} mm ({axis}, {reason}) even after one re-mesh. Widen the gap at that edge in KiCad, or change mesh.n in project.json (now {n})."
  - `E_FIT2D`: "The mesh misses the 2D reference on net {net} ({layer}) by {err_pct} % (limit {limit_pct} %) at mesh.n {n}. Set mesh.n to 3 in project.json."
  - `E_FIT2D_FINE`: "The fine mesh (mesh.n {n}) still misses the 2D reference on net {net} ({layer}) by {err_pct} % (limit {limit_pct} %). Raising gates.fit2d_limit in project.json lets the run go on, at your own risk."
  - `E_FIT2D_SHORT`: "Other copper touches net {net} on {layer} at its 2D cut, so fit2d cannot check it. Check the copper in KiCad and refill zones (B); copper with no net counts too."
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: keep both masks and the protected set in Geometry; fit2d per side; gate messages in KiCad's frame`

---

### Task 6: Ports and port boxes

**Files:**
- Create: `src/kicad_rf_studio/core/model/ports.py`
- Modify: `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_model_ports.py`

**Interfaces:**
- Consumes: `Board`, `Piece`, `Mesh`, `Slab`, `SIMPLIFY`; the project's `ports`, `chain`, `others`, `allow_curve_port`.
- Produces:
  - `@dataclass(frozen=True) class End`: `name: str`, `signal: BaseGeometry`, `reference: BaseGeometry` (internal frame), `layer: str`, `role: str` ("external", "port", "curve_port" or "grid").
  - `ends(board, project, pieces) -> list[End]` in job order: the external ports in project order, then the parts with role port, curve_port or grid in project order (series, shunt, others); a part's signal is `pads[0]`, its reference `pads[1]`. A pad reference is found by its uuid, else by its name: the first pad of that name with copper on the port's layer (`# ponytail: a reference by pad name alone takes the first pad of that name`). A point reference resolves to the nearest piece on its layer within `SIMPLIFY` (pieces are simplified at 10 µm, the stored point lies on the raw copper), cut to the box over the signal pad's span across the direction from the signal centre to the point and over the signal pad's length beyond the point. Raises `E_NO_PORTS`; `E_NO_REFERENCE {signal}` for a null reference; `E_UNKNOWN_PAD {name, candidates}` (the tracer's own lookup) for a pad that is not on the board; `E_REFERENCE_POINT {name, point, layer}` for a point with no copper within `SIMPLIFY`; `E_REFERENCE_LAYER {name, signal_layer, reference_layer}` (C-14: no vertical ports); `E_ROTATED_PART {ref}` for a curve_port while `allow_curve_port` is false (C-12, C-37).
  - `nominal_boxes(ends) -> tuple[Polygon, ...]`: the convex hull of each pair, for `Protected.boxes` (they widen the protected extent; part pads get their edge lines from Task 5).
  - `place(end, mesh, zs) -> dict`: `{"name", "kind": "lumped", "dir": "x"|"y", "start": [x, y, z], "stop": [x, y, z], "nodes": [ref cap, sig cap, ref witness, sig witness], "part": bool}`, every coordinate a line of `mesh`, the box starting at the reference end so that openEMS's u is V_signal − V_reference; raises `E_PORT_SPANS {name}` and `E_PORT_BOX {name}`.

  `place` works on bounding boxes (`# ponytail: pads are taken as their bounding boxes; a round pad's corner can leave a cap edge in air, which the PEC check tolerates`):

```text
S, R = bounds of signal and reference. p = the in-plane axis along which S and R are apart (their spans along p do
not overlap) while their spans across p overlap; no such axis → E_PORT_SPANS. t = the other in-plane axis.
inside(lines, a, b) = the lines strictly between a and b.
sig = the line of inside(S along p) nearest R; ref = the line of inside(R along p) nearest S;
lo, hi = the first and last line of inside(the overlap of S and R across p); any one missing → E_PORT_BOX.
z0, z1 = the faces of end.layer's copper slab. tc = the line of [lo, hi] nearest (lo + hi)/2.
start = (ref, lo, z0); stop = (sig, hi, z1), on the axes (p, t, z).
nodes = [(ref, tc, z1), (sig, tc, z1), (line of inside(R) farthest from S, tc, z1), (line of inside(S) farthest from R, tc, z1)]
```

- [ ] **Step 1: Write the failing tests**

```python
@cache
def lpf_model():
    """lpf915 through `new` with a 2.5 mm lid: board, project, geometry, port ends, and the mesh with their boxes."""
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    return board, p, g, e, mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2)


def test_lpf915_ports_in_job_order():
    assert [(x.name, x.role) for x in lpf_model()[3]] == [
        ("P1", "external"), ("P2", "external"), ("C1", "port"), ("L1", "port"), ("C2", "port"), ("C3", "port")]


def test_port_boxes_sit_on_lines_inside_their_pads():  # spec 5.6, C-14
    board, p, g, e, m = lpf_model()
    p1, p2, c1, c2 = (place(x, m, g.zs) for x in (e[0], e[1], e[2], e[4]))
    assert (p1["dir"], p2["dir"], c1["dir"], c2["dir"]) == ("y", "y", "x", "y")
    assert -99.625 < p1["start"][1] < -99.375 and -100.125 < p1["stop"][1] < -99.875  # U1.2, then U1.1
    assert 101.05 < p1["start"][0] < p1["stop"][0] < 101.875
    assert 112.825 < p2["start"][0] < p2["stop"][0] < 112.925  # J1.1 and J1.2 overlap 0.1 mm in x
    assert 103.7 < c1["start"][0] < 104.26 and 102.74 < c1["stop"][0] < 103.3  # C1.2 (reference), then C1.1
    for q in (p1, p2, c1, c2):
        assert (q["start"][2], q["stop"][2]) == (0.745, 0.78)
        assert {q["start"][0], q["stop"][0]} <= set(m.x.tolist()) and {q["start"][1], q["stop"][1]} <= set(m.y.tolist())
    assert (p1["part"], c1["part"]) == (False, True)


def test_a_copper_rule_reference_takes_the_ground_under_the_point():  # S-3: the y flip of the stored point
    board, p = project_of("coupon_gcpw_pads", "TP1.1", "TP2.1")
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    q = place(e[0], mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2), g.zs)
    assert q["dir"] == "y" and q["start"][1] < -100.6505 < -100.5 < q["stop"][1] < -99.5
    assert 99.5 < q["start"][0] < q["stop"][0] < 100.5


def edited(name, start, end, where, value, *more):
    board, p = project_of(name, start, end, *more)
    p = copy.deepcopy(p)
    edit(p, where, value)  # tests/test_project.py
    return board, p


@pytest.mark.parametrize(("where", "value", "code", "params"), [
    (["ports", 0, "reference"], None, "E_NO_REFERENCE", {"signal": "TP1.1"}),
    (["ports", 0, "reference"], {"point": [100.0, 100.6505], "layer": "B.Cu"}, "E_REFERENCE_LAYER",
     {"name": "P1", "signal_layer": "F.Cu", "reference_layer": "B.Cu"}),
    (["ports", 0, "reference"], {"point": [100.0, 100.3], "layer": "F.Cu"}, "E_REFERENCE_POINT",  # in the gap
     {"name": "P1", "point": "(100.000, 100.300)", "layer": "F.Cu"}),
    (["ports"], [], "E_NO_PORTS", {})])
def test_refusals_on_the_coupon(where, value, code, params):
    board, p = edited("coupon_gcpw_pads", "TP1.1", "TP2.1", where, value)
    with pytest.raises(KrsError) as e:
        ends(board, p, build_geometry(board, p).pieces)
    assert (e.value.code, e.value.params) == (code, params)


def test_an_unknown_reference_pad_is_named():
    board, p = edited("lpf915", "U1.1", "J1.1", ["ports", 0, "reference"], {"pad": "U9.2", "uuid": ""})
    with pytest.raises(KrsError) as e:
        ends(board, p, build_geometry(board, p).pieces)
    assert (e.value.code, e.value.params["name"]) == ("E_UNKNOWN_PAD", "U9.2")


def test_a_reference_by_pad_name_alone():  # Review Focus 3
    board, p = edited("lpf915", "U1.1", "J1.1", ["ports", 0, "reference"], {"pad": "U1.2", "uuid": ""},
                      "--lid-height", "2.5")
    assert ends(board, p, build_geometry(board, p).pieces)[0].reference.equals(board.pads("U1.2")[0].polygon)


def test_pads_that_face_each_other_on_no_axis_are_refused():
    board, p, g, _, m = lpf_model()
    q = copy.deepcopy(p)
    q["ports"][0]["reference"] = {"pad": "C2.2", "uuid": board.pads("C2.2")[0].uuid}  # diagonal to U1.1
    with pytest.raises(KrsError) as e:
        place(ends(board, q, g.pieces)[0], m, g.zs)
    assert (e.value.code, e.value.params) == ("E_PORT_SPANS", {"name": "P1"})


def test_a_rotated_part_needs_the_switch():  # C-12, C-37
    board, p = project_of("lpf915-45", "U1.1", "J1.1", "--lid-height", "2.5")
    with pytest.raises(KrsError) as e:
        ends(board, p, build_geometry(board, p).pieces)
    assert (e.value.code, e.value.params) == ("E_ROTATED_PART", {"ref": "L1"})
```

- [ ] **Step 2: Run** `python -m pytest tests/test_model_ports.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** `point` is formatted `f"({x:.3f}, {y:.3f})"` in KiCad's frame. Messages:
  - `E_NO_PORTS`: "project.json has no ports, so there is nothing to excite. Create the project with `new` between two pads."
  - `E_NO_REFERENCE`: "Port {signal} has no reference. Set its \"reference\" in project.json to a pad or a point before running."
  - `E_REFERENCE_POINT`: "Port {name}: no copper on {layer} lies at its reference point {point} mm. Set its \"reference\" in project.json to a point on the ground copper, or to a pad."
  - `E_REFERENCE_LAYER`: "Port {name}: its reference is on {reference_layer} and its signal pad on {signal_layer}; Stage 1 builds horizontal ports only. Choose a reference on {signal_layer} in project.json."
  - `E_ROTATED_PART`: "Part {ref} is not at a multiple of 90°, so its port would be a CurvePort, which P0-B has not validated. Rotate it in KiCad, or set \"allow_curve_port\": true in project.json at your own risk."
  - `E_PORT_SPANS`: "Port {name}: its two pads face each other neither along x nor along y, so no box joins them. Choose a reference straight across from the signal pad in project.json."
  - `E_PORT_BOX`: "Port {name}: no mesh line lies inside its pads, so its box cannot sit on them. Set mesh.n to 3 in project.json, or use larger pads."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: place port boxes on mesh lines inside their pads (spec 5.6)`

---

### Task 7: The model spec and its hash

**Files:**
- Create: `src/kicad_rf_studio/core/model/spec.py`
- Modify: `src/kicad_rf_studio/core/geometry/copper.py` (a note on `Piece.solid`), `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_model_spec.py`

**Interfaces:**
- Consumes: `Geometry` (masks, lid, rods, pieces, zs, region), `Mesh` (x, y, z, dz0, snapped_rods), `place` (Task 6), `snap_lid`, `split_holes`, `clean`, `smeared_epsilon`, `part_kind`, `part_value`, `band`.
- Produces:
  - `EPS0 = scipy.constants.epsilon_0`.
  - `excitation(project) -> {"f1", "f2", "t0", "t_max", "expr"}`, `expr = f"sin(2*pi*{fm:.12g}*(t-{t0:.12g}))*exp(-(2*pi*{fw:.12g}*t/3-3)^2)*(t<{2*t0:.12g})"`, `t_max` the project's `t_max_s`.
  - `kappa(eps_r, tan_d, f0) -> float` = 2π·f0·EPS0·εr·tanδ; 0 when `tan_d` is None.
  - `grid_entry(placed, part) -> dict` = `{**placed, "R": value or None, "C": value or None}` by `part_kind`: a part whose kind is not C or R raises `E_GRID_KIND {ref}`; an unreadable value raises `E_PART_VALUE {ref, value}`.
  - `model_spec(project, board, geom, mesh, ports, grid) -> dict`:

```text
{"mesh": {"x": [...], "y": [...], "z": [...]},                     # the Mesh's own lines (X-6), Python floats
 "excitation": excitation(project),
 "materials": [{"name", "eps", "kappa", "priority", "solids": [{"x": [...], "y": [...], "z": [z0, z1]}]}],
 "metal": {"copper": [solid, ...], "lid": {"plate": {"x", "y", "z"} | None, "walls": [solid, ...]},
           "cylinders": [{"at": [x, y], "r": r, "z": [z0, z1]}], "curves": [{"at": [x, y], "z": [z0, z1]}]},
 "ports": ports,                 # place() entries, in job order
 "grid": grid}                   # grid_entry() entries
```

  - `spec_hash(spec) -> str` = sha256 of `json.dumps(spec, sort_keys=True, separators=(",", ":"))` (C-19); the excited port, threads and paths stay out; port parts' values stay out (a retune keeps the results), grid values are in.
  - How the spec is built:
    - **Materials**, in this order, each at priority 10 + its index in the final list (openEMS breaks priority ties arbitrarily); a material with no solids is left out (openEMS warns "No primitives found" for an empty property):
      - each dielectric slab `substrate_<i>`, bottom up: εr and κ at f0;
      - each copper slab between two dielectrics: a substrate entry at their mean εr and mean κ (C-8);
      - per mask (F first) `mask_<side>_fill` at ε_m and κ_m = `kappa(ε_m, tanδ of the stackup's mask slab, f0)` over `z_fill`, and `mask_<side>_coat` at ε_h = `smeared_epsilon(t_m, ε_m, dz0)` and κ_m·t_m/dz0 over [z_coat0, z_coat0 + dz0] on F, [z_coat0 − dz0, z_coat0] on B (C-6). The stackup's mask slabs never become materials (X-3).
    - **Footprints:** every polygon → solids through `split_holes` of each part (X-2, X-4); substrate solids from `clean(board.outline or region.crop, region.crop)`; mask solids from `gap_fill` and `coat`.
    - **Metal:** every piece a solid over its layer's slab (C-5); every part with role "copper" adds the convex hull of its two pads on their layer (spec §5.7); solid rods → cylinders, the snapped rods that are not solid → curves (C-40); `snap_lid(geom.lid, mesh.z)` gives the plate (a sheet at the snapped z1) and the walls (from z0 to the snapped z1) (C-39, X-5).
    - **Rings** are the exterior coordinates without the closing point.

  `copper.py`: `Piece.solid` gets `# ponytail: informational since plan 3: the CSX builds every piece solid (C-5); sheets come back only if P0 shows a gain`.

- [ ] **Step 1: Write the failing tests**

```python
P915 = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "t_max_s": 40e-9}


def test_the_pulse_for_915_mhz():  # spec 5.8
    e = excitation(P915)
    assert (e["f1"], e["f2"], e["t_max"]) == pytest.approx((457.5e6, 3.0195e9, 40e-9))
    assert e["t0"] == pytest.approx(9 / (2 * math.pi * 1.281e9), rel=1e-12)  # 1.1182 ns
    fm, fw, t0 = 1.7385e9, 1.281e9, e["t0"]
    form = lambda t: (math.sin(2 * math.pi * fm * (t - t0)) * math.exp(-(2 * math.pi * fw * t / 3 - 3) ** 2)
                      * (t < 2 * t0))
    for t in (0.3e-9, 1.1e-9, 2.0e-9, 2.3e-9):  # the last one is past the gate (t < 2 t0)
        got = eval(e["expr"].replace("^", "**"), {"sin": math.sin, "exp": math.exp, "pi": math.pi, "t": t})
        assert got == pytest.approx(form(t), abs=1e-9)


def test_kappa_is_set_at_f0():  # spec 5.3
    assert kappa(4.5, 0.02, 915e6) == pytest.approx(4.58134e-3, rel=1e-5) and kappa(3.3, None, 915e6) == 0.0


@cache
def lpf_spec():
    board, p, g, e, m = lpf_model()  # tests/test_model_ports.py
    return g, m, model_spec(p, board, g, m, [place(x, m, g.zs) for x in e], [])


def test_the_lpf915_spec():
    g, m, s = lpf_spec()
    assert json.loads(json.dumps(s)) == s
    assert s["mesh"]["z"] == m.z.tolist() and s["mesh"]["z"][-1] == pytest.approx(26.001447)  # X-6: over the 2.5 mm lid
    assert all(c["z"] in ([0.745, 0.78], [0.0, 0.035]) for c in s["metal"]["copper"])  # C-5: every piece solid
    assert len(s["metal"]["copper"]) == len(g.pieces) + 1  # + R1, a 0R rectangle; R2 is DNP
    names = [x["name"] for x in s["materials"]]
    assert names == ["substrate_0", "mask_F_fill", "mask_F_coat", "mask_B_fill", "mask_B_coat"]
    assert [x["priority"] for x in s["materials"]] == [10, 11, 12, 13, 14]
    sub, _, fcoat, _, bcoat = s["materials"]
    assert (sub["eps"], sub["kappa"], sub["solids"][0]["z"]) == (4.5, pytest.approx(4.58134e-3, rel=1e-5),
                                                                 [0.035, 0.745])
    assert fcoat["solids"][0]["z"] == [0.78, round(0.78 + m.dz0, 6)] and bcoat["solids"][0]["z"] == [round(-m.dz0, 6), 0.0]
    assert fcoat["eps"] == pytest.approx(smeared_epsilon(0.01, 3.3, m.dz0)) and fcoat["kappa"] == 0.0
    assert not any(q["z"] in ([0.78, 0.79], [-0.01, 0.0]) for x in s["materials"] for q in x["solids"])  # X-3
    area = sum(Polygon(zip(q["x"], q["y"])).area for q in fcoat["solids"])
    assert area == pytest.approx(g.masks["F.Cu"].coat.area, abs=1e-3)  # C-6: the 47 openings honoured
    assert len(s["metal"]["cylinders"]) == 21 and len(s["metal"]["curves"]) == 15  # C-40
    assert all(c["at"][0] in m.x and c["at"][1] in m.y for c in s["metal"]["curves"])
    assert s["metal"]["lid"]["plate"]["z"] == snap_lid(g.lid, m.z).z1 and s["metal"]["lid"]["plate"]["z"] in m.z  # C-39


def test_lid_walls_drawn_as_one_closed_ring_are_split():  # X-4
    board, p, g, _, m = lpf_model()
    frame = box(100, -105, 110, -95).difference(box(101, -104, 109, -96))
    s = model_spec(p, board, replace(g, lid=replace(g.lid, walls=MultiPolygon([frame]))), m, [], [])
    walls = [Polygon(zip(w["x"], w["y"])) for w in s["metal"]["lid"]["walls"]]
    assert sum(w.area for w in walls) == pytest.approx(frame.area, abs=1e-6)
    assert not any(w.contains(Point(105, -100)) for w in walls)  # never the frame's .exterior


def test_a_material_with_no_solids_is_left_out():  # openEMS warns on a property with no primitive
    board, p = project_of("coupon_gcpw_pads", "TP1.1", "TP2.1")
    g = build_geometry(board, p)
    s = model_spec(p, board, g, mesh_with_lint(g, g.protected, 2), [], [])
    assert [x["name"] for x in s["materials"]] == ["substrate_0", "mask_B_fill", "mask_B_coat"]  # F mask open everywhere


def test_inner_copper_slabs_are_filled_at_the_mean_of_their_neighbours(mini_board_file):  # C-8, X-1
    top = '(thickness 0.2) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.01)'
    board = load_board(four_layer(mini_board_file, SEG.format(5, 10, 35, 10, 0.3, "F.Cu", "SIG", "s")
                                  + plane("In1.Cu"), top=top))
    p = {**mini(), "f0_hz": 915e6, "t_max_s": 40e-9, "stackup": board.stackup.to_json(), "others": []}
    g = build_geometry(board, p)
    s = model_spec(p, board, g, mesh_with_lint(g, g.protected, 2), [], [])
    in1 = next(x for x in g.zs if x.copper == "In1.Cu")
    fill = next(x for x in s["materials"] if x["solids"][0]["z"] == [in1.z0, in1.z1])
    assert fill["eps"] == pytest.approx(4.4)
    assert fill["kappa"] == pytest.approx((kappa(4.5, 0.01, 915e6) + kappa(4.3, 0.02, 915e6)) / 2)
    assert fill["priority"] < 1000  # the metal (Task 9) wins where the copper lies


def test_the_hash_covers_the_model_but_not_the_port_values():  # C-19, spec 7.8
    g, m, s = lpf_spec()
    assert len(spec_hash(s)) == 64 and spec_hash(s) == spec_hash(json.loads(json.dumps(s)))
    grid = grid_entry(s["ports"][2], {"ref": "C4", "value": "0.4pF"})
    assert (grid["R"], grid["C"]) == (None, pytest.approx(0.4e-12))
    assert spec_hash({**s, "grid": [grid]}) != spec_hash({**s, "grid": [{**grid, "C": 0.5e-12}]})
    assert spec_hash({**s, "excitation": {**s["excitation"], "t_max": 20e-9}}) != spec_hash(s)
    assert '"value"' not in json.dumps(s)  # a retune keeps the results


@pytest.mark.parametrize(("ref", "value", "code"), [
    ("C4", "??", "E_PART_VALUE"), ("L9", "10nH", "E_GRID_KIND"), ("D1", "1N4148", "E_GRID_KIND")])
def test_a_grid_part_must_be_a_c_or_r_with_a_readable_value(ref, value, code):  # Review Focus 3
    with pytest.raises(KrsError) as e:
        grid_entry(lpf_spec()[2]["ports"][2], {"ref": ref, "value": value})
    assert (e.value.code, e.value.params["ref"]) == (code, ref)
```

- [ ] **Step 2: Run** `python -m pytest tests/test_model_spec.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Messages:
  - `E_PART_VALUE`: "Part {ref} is in the grid but its value \"{value}\" cannot be read. Fix its value in project.json, or set its role to \"open\" or \"port\"."
  - `E_GRID_KIND`: "Part {ref} cannot sit in the grid: only a C or an R can. Set its role to \"port\" or \"open\" in project.json."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: build the model spec and its hash (spec 3.3, 5.3, 5.8)`

---

### Task 8: Readers of openEMS's output

**Files:**
- Create: `src/kicad_rf_studio/core/model/readers.py`, `tools/make_dumps.py`, `tests/fixtures/dumps/PEC_dump.vtp`, `tests/fixtures/dumps/operator_dump.vtr`
- Test: `tests/test_readers.py`

**Interfaces:**
- Produces (stdlib and numpy only; the worker imports this module):
  - `read_probe(text) -> tuple[np.ndarray, np.ndarray]`: complete lines only (a partial last line is ignored), "%" lines skipped, CRLF or LF; a token `float()` refuses that contains "nan" or "inf" (MSVC's `-nan(ind)`) reads as NaN or ±inf.
  - `read_run_stats(text) -> tuple[np.ndarray, np.ndarray, np.ndarray]`: the timestep, speed (cells/s) and energy columns of `openEMS_run_stats.txt`, complete rows only.
  - `read_stats(text) -> dict`: `openEMS_stats.txt` as `{"cells", "dt", "iterations", "sim_time", "wall", "speed"}` (speed in cells/s).
  - `read_log(text) -> {"cells": [nx, ny, nz] | None, "dt": float | None, "node": [n, i, j, k] | None, "nrts": int | None, "iterations": int | None}` from `FDTD simulation size: (\d+)x(\d+)x(\d+) -->`, `FDTD timestep is: (\S+) s` (6 significant digits), `found at position: (\d+) : (\d+);(\d+);(\d+)` (verbose 2), `Max\. number of timesteps: (\d+)`, `Time for (\d+) iterations`.
  - `read_unused(text) -> list[list[str]]` from stderr: `Unused primitive (type: T) detected in property: P!` → `[T, P]`; `No primitives found in property: P!` → `["none", P]`; `Warning in P (...) : Box is outside the field domain!! Disabling` → `["outside", P]`.
  - `read_vtk(path) -> dict[str, np.ndarray]`: every DataArray by name; cell arrays as `Lines/connectivity`, `Lines/offsets`, …; `Coordinates` as `x`, `y`, `z` by position (their names are pointer addresses).
  - `pec_roots(path, lines, nodes) -> list[int]`: the union-find root of each node (mm, on lines) over `PEC_dump.vtp`'s edges; −1 for a node no PEC edge touches.
  - `c_box(path, lines, start, stop, axis, dt) -> float`: series-of-parallel over the box's p-edges in `operator_dump.vtr` (C-18).

```text
each array: base64(header) + base64(zlib blocks); header = UInt32 [nblocks, blocksize, lastblocksize, csize_1..n],
its base64 length 4·ceil(4·(3 + nblocks)/3); data = the decompressed blocks joined.
.vtp: format="appended", the arrays in <AppendedData encoding="base64"> after its "_", offsets in characters;
.vtr: format="binary", inline. Point (i, j, k) of an nx·ny grid is index i + nx·(j + ny·k); component n of a
3-vector array, at 3·index + n, belongs to the edge from (i, j, k) toward +n.
pec_roots: each dump point (metres, float32) takes the nearest line index per axis (lines × 1e-3); union-find over
the point indices of each 2-point line; a node's root is that of a point with its indices.
c_box: the box spans line indices a..b along `axis`, lo..hi on the other two (inclusive); per layer m in a..b−1,
C_layer = Σ over the layer's edges of C_e = dt·(1 + vv)/(2·vi), component `axis` (vi = 0 is PEC: skipped);
C_box = 1 / Σ (1 / C_layer).
```

  `# ponytail: pure-Python union-find, about 1 s per million PEC edges; numpy label propagation if it shows`

- [ ] **Step 1: Generate the dump fixtures** with `tools/make_dumps.py` (dev-time, SPDX header, needs Task 1's venv, runs openEMS directly), in mm (`SetDeltaUnit(1e-3)`): mesh x −8…8 step 0.25 (65 lines), y −4…4 step 0.25 (33), z `[-1, -0.5, 0, 0.125, 0.25, 0.375, 0.5, 0.535, 0.6, 0.75, 1, 1.5, 2, 2.5, 3, 3.5]` (16); material `FR4` (εr 4.3, κ = `kappa(4.3, 0.02, 915e6)`) box [−8, −4, 0]–[8, 4, 0.5] at priority 0; metal `PEC` boxes [−8, −4, 0]–[8, 4, 0] and [−5, −0.5, 0.5]–[5, 0.5, 0.535] at priority 10; `AddLumpedPort(1, 50, [-5, -0.5, 0], [-5, 0.5, 0.5], "z", excite=1)` and `(2, 50, [5, -0.5, 0], [5, 0.5, 0.5], "z", excite=0)`; `openEMS(EndCriteria=1e-15)`, MUR×6, `SetCustomExcite` with `excitation(P915)`'s pulse, `SetMaxTime(5e-9)`; `Run(".", setup_only=True, numThreads=1, debug_PEC=True, debug_operator=True)` with the working folder `tests/fixtures/dumps`; it deletes `et` and `ht`. Run `python tools/make_dumps.py`. Expected: two files of about 34 and 16 KB.
- [ ] **Step 2: Write the failing tests**

```python
SETUP_LOG = ("openEMS - verbose level 2\n"
             "Operator::CalcTimestep_Var3: Smallest timestep (1.73972e-13s) found at position: 2 : 0;0;6\n"
             "FDTD simulation size: 65x33x16 --> 34320 FDTD cells \r\n"
             "FDTD timestep is: 1.73972e-13 s; Nyquist rate: 951 timesteps @3.02211e+09 Hz\n"
             "Max. number of timesteps: 28740 ( --> 1 * Excitation signal length)\n")
STATS = ("34320\t% number of cells\n1.739719832710559e-13\t% timestep (s)\n28740\t% number of iterations\n"
         "4.999954799210147e-09\t% total numerical time (s)\n16.034181\t% simulation time (s)\n"
         "61515882.8505179\t% speed (cells/s)\n")
PROBE = ("% time-domain voltage integration by openEMS v0.37.0 @Wed Oct 21 08:38:31 2026\r\n"
         "% start-coordinates: (-0.005,0,0) m -> [12,16,2]\r\n% stop-coordinates: (-0.005,0,0.0005) m -> [12,16,6]\r\n"
         "% t/s\tvoltage\r\n0\t-0\r\n4.12313600352e-11\t2.93135258289e-07\r\n8.24627200704e-11\t-nan(ind)\r\n1.2369")
DUMPS = Path(__file__).parent / "fixtures" / "dumps"
LINES = (np.arange(-8, 8.001, 0.25), np.arange(-4, 4.001, 0.25),
         np.array([-1, -0.5, 0, .125, .25, .375, .5, .535, .6, .75, 1, 1.5, 2, 2.5, 3, 3.5]))


def test_the_setup_log():  # r5's real lines; the banner (it holds an e-mail address) is left out
    assert read_log(SETUP_LOG) == {"cells": [65, 33, 16], "dt": 1.73972e-13, "node": [2, 0, 0, 6], "nrts": 28740,
                                   "iterations": None}
    assert read_log("Time for 28740 iterations with 34320.00 cells : 16.03 sec\n")["iterations"] == 28740
    assert read_log("Time for 0 iterations with 34320 cells : 0.00011 sec\n")["iterations"] == 0  # a stale ABORT


def test_statistics_and_probes():
    assert read_stats(STATS) == {"cells": 34320, "dt": 1.739719832710559e-13, "iterations": 28740,
                                 "sim_time": 4.999954799210147e-09, "wall": 16.034181, "speed": 61515882.8505179}
    steps, speed, e = read_run_stats("%time\ttimestep\tspeed\tenergy\n4.12275\t8058\t6.70792e+07\t2.93607e-15\n"
                                     "8.21882\t15168\t5.95729e+07\t-nan(ind)\n12.304\t222")
    assert steps.tolist() == [8058, 15168] and speed[0] == 6.70792e+07 and e[0] == 2.93607e-15 and np.isnan(e[1])
    t, v = read_probe(PROBE)
    assert t.tolist() == [0.0, 4.12313600352e-11, 8.24627200704e-11] and v[1] == 2.93135258289e-07 and np.isnan(v[2])


def test_unused_primitives_from_stderr():  # C-16
    err = ("Warning: Unused primitive (type: Box) detected in property: port_resist_1!\n"
           "Warning: No primitives found in property: metal!\n"
           "Processing::DefineStartStopCoord: Warning in port_ut_2 (-1,0,0) : Box is outside the field domain!! Disabling\n")
    assert read_unused(err) == [["Box", "port_resist_1"], ["none", "metal"], ["outside", "port_ut_2"]]


def test_the_dumps_decode():  # r5: UInt32 headers, zlib, base64
    pec, op = read_vtk(DUMPS / "PEC_dump.vtp"), read_vtk(DUMPS / "operator_dump.vtr")
    assert len(pec["Points"]) == 3 * 2551 and len(pec["Lines/connectivity"]) == 2 * 4933
    assert [len(op[c]) for c in "xyz"] == [65, 33, 16]
    assert np.linalg.norm(op["vv"].reshape(-1, 3), axis=1).max() == pytest.approx(1.7320508075688772, rel=1e-6)


def test_pec_pieces_tell_the_strip_from_the_ground():  # C-15
    r = pec_roots(DUMPS / "PEC_dump.vtp", LINES, [[-5, 0, 0], [-5, 0, 0.5], [0, 2, 0], [0, 0, 0.535], [0, 3, 2]])
    assert r[0] == r[2] != r[1] == r[3] and min(r[:4]) >= 0 and r[4] == -1


def test_c_box_of_port_1():  # C-18: 4 layers of 5 z-edges in series
    c = c_box(DUMPS / "operator_dump.vtr", LINES, [-5, -0.5, 0], [-5, 0.5, 0.5], 2, 1.73972e-13)
    assert c == pytest.approx(2.3796e-14, rel=1e-3)
```

- [ ] **Step 3: Run** `python -m pytest tests/test_readers.py -q`. Expected: FAIL (module missing).
- [ ] **Step 4: Implement** `readers.py`.
- [ ] **Step 5: Run** the tests, then `git add tools/make_dumps.py tests/fixtures/dumps` and `python tools/privacy_gate.py --staged --generic-only` (`--all` scans only the committed history). Expected: PASS, and no hit.
- [ ] **Step 6: Commit.** `feat: read openEMS's logs, probes, statistics and VTK dumps; PEC pieces and C_box`

---

### Task 9: `build_csx`

**Files:**
- Create: `src/kicad_rf_studio/core/model/csx.py`
- Test: `tests/test_model_csx.py`

**Interfaces:**
- Consumes: the model spec (Task 7).
- Produces:
  - `METAL_PRIORITY = 1000`.
  - `build_csx(spec, excite: int, t_max: float) -> tuple[object, object]`: the `ContinuousStructure` and the `openEMS` object; CSXCAD and openEMS imported inside the function only; port `excite` (1-based) is excited.
  - The calls, exactly:
    - setup: `openEMS(EndCriteria=1e-15)`, `ContinuousStructure()`, `fdtd.SetCSX(csx)`; `GetGrid().SetDeltaUnit(1e-3)`, `SetLines("x" | "y" | "z", lines)`; `SetBoundaryCond(["MUR"] * 6)`; `SetCustomExcite(expr, f2, f2)`, `SetMaxTime(t_max)`. TimeStepMethod, TimeStep and TimeStepFactor are never set (W-1).
    - each material: `csx.AddMaterial(name, epsilon=eps, kappa=kappa)`, then one `AddLinPoly([x, y], "z", z0, z1 - z0, priority=p)` per solid.
    - one metal, `csx.AddMetal("metal")`: each copper solid and each lid wall `AddLinPoly(..., priority=METAL_PRIORITY)`; the plate `AddPolygon([x, y], "z", z, priority=METAL_PRIORITY)` (points as `[xs, ys]`: CSXCAD misreads an (N, 2) array silently); each cylinder `AddCylinder([x, y, z0], [x, y, z1], r, priority=METAL_PRIORITY)`; each curve `AddCurve([[x, x], [y, y], [z0, z1]])` with no priority.
    - each port k = 1…: `fdtd.AddLumpedPort(k, 50, start, stop, dir, excite=1 if k == excite else 0)`.
    - each grid part i: `csx.AddLumpedElement(f"lumped_{i}", ny="xyz".index(dir), caps=True, R=R)` or `C=C` (the one that is set), then `.AddBox(start, stop)`.

  Property names carry their role (C-16): `port_*` are openEMS's own port properties, `lumped_*` parts, and `metal`, `substrate_*`, `mask_*` the rest.

- [ ] **Step 1: Write the failing tests**

```python
class Rec:
    """Stands in for CSXCAD and openEMS: every call is logged as (name, args, kwargs); Run returns 0 (setup OK),
    any other call another Rec."""

    def __init__(self, log, name=""):
        self.log, self.name = log, name

    def __getattr__(self, name):
        return Rec(self.log, name)

    def __call__(self, *args, **kw):
        self.log.append((self.name, args, kw))
        return 0 if self.name == "Run" else Rec(self.log, self.name)


def fake_openems(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "CSXCAD", types.SimpleNamespace(ContinuousStructure=Rec(calls, "ContinuousStructure")))
    monkeypatch.setitem(sys.modules, "openEMS", types.SimpleNamespace(openEMS=Rec(calls, "openEMS")))
    return calls


SQUARE = {"x": [0.0, 4.0, 4.0, 0.0], "y": [0.0, 0.0, 4.0, 4.0]}
TINY = {  # a 5 × 5 × 5-line model: a substrate slab, a copper block, one port
    "mesh": {"x": [0.0, 1.0, 2.0, 3.0, 4.0], "y": [0.0, 1.0, 2.0, 3.0, 4.0], "z": [0.0, 1.0, 2.0, 3.0, 4.0]},
    "excitation": excitation({"f0_hz": 1e9, "harmonics": 1, "band_factor": 1.1, "t_max_s": 1e-9}),
    "materials": [{"name": "substrate_0", "eps": 4.5, "kappa": 0.0046, "priority": 10,
                   "solids": [{**SQUARE, "z": [0.0, 1.0]}]}],
    "metal": {"copper": [{"x": [1.0, 3.0, 3.0, 1.0], "y": [1.0, 1.0, 3.0, 3.0], "z": [1.0, 2.0]}],
              "lid": {"plate": None, "walls": []}, "cylinders": [], "curves": []},
    "ports": [{"name": "P1", "kind": "lumped", "dir": "z", "start": [2.0, 2.0, 0.0], "stop": [2.0, 2.0, 1.0],
               "nodes": [[2.0, 2.0, 0.0], [2.0, 2.0, 1.0], [0.0, 0.0, 0.0], [2.0, 2.0, 2.0]], "part": False}],
    "grid": []}


def test_build_csx_follows_the_spec_and_the_engine_settings(monkeypatch):  # spec 5.8, 6.2, W-1
    log = fake_openems(monkeypatch)
    build_csx(TINY, 1, 1e-9)
    names = [n for n, _, _ in log]
    assert log[0] == ("openEMS", (), {"EndCriteria": 1e-15})
    assert ("SetDeltaUnit", (1e-3,), {}) in log and ("SetBoundaryCond", (["MUR"] * 6,), {}) in log
    f2 = TINY["excitation"]["f2"]
    assert ("SetCustomExcite", (TINY["excitation"]["expr"], f2, f2), {}) in log and ("SetMaxTime", (1e-9,), {}) in log
    assert not {"SetTimeStepMethod", "SetTimeStep", "SetTimeStepFactor"} & set(names)
    assert ("AddMaterial", ("substrate_0",), {"epsilon": 4.5, "kappa": 0.0046}) in log
    assert [kw["priority"] for n, _, kw in log if n == "AddLinPoly"] == [10, METAL_PRIORITY]
    assert ("AddLumpedPort", (1, 50, [2.0, 2.0, 0.0], [2.0, 2.0, 1.0], "z"), {"excite": 1}) in log


def test_the_lid_and_the_vias_are_metal_primitives(monkeypatch):  # C-39, C-40, R3-057
    log = fake_openems(monkeypatch)
    lid = {"plate": {**SQUARE, "z": 3.0}, "walls": [{**SQUARE, "z": [2.0, 3.0]}]}
    build_csx({**TINY, "metal": {**TINY["metal"], "lid": lid, "cylinders": [{"at": [1.0, 1.0], "r": 0.15, "z": [0.0, 2.0]}],
                                 "curves": [{"at": [3.0, 3.0], "z": [0.0, 2.0]}]}}, 1, 1e-9)
    assert ("AddPolygon", ([SQUARE["x"], SQUARE["y"]], "z", 3.0), {"priority": METAL_PRIORITY}) in log
    assert ("AddLinPoly", ([SQUARE["x"], SQUARE["y"]], "z", 2.0, 1.0), {"priority": METAL_PRIORITY}) in log
    assert ("AddCylinder", ([1.0, 1.0, 0.0], [1.0, 1.0, 2.0], 0.15), {"priority": METAL_PRIORITY}) in log
    assert ("AddCurve", ([[3.0, 3.0], [3.0, 3.0], [0.0, 2.0]],), {}) in log


def test_grid_parts_are_lumped_elements_named_for_the_gate(monkeypatch):  # C-16
    log = fake_openems(monkeypatch)
    part = {**TINY["ports"][0], "name": "C4", "R": None, "C": 1e-12}
    build_csx({**TINY, "grid": [part]}, 1, 1e-9)
    assert ("AddLumpedElement", ("lumped_0",), {"ny": 2, "caps": True, "C": 1e-12}) in log
```

- [ ] **Step 2: Run** `python -m pytest tests/test_model_csx.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `csx.py` as the Interfaces fix it.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: build the CSX and the FDTD setup from the model spec`

---

### Task 10: The worker

**Files:**
- Create: `src/kicad_rf_studio/worker.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Consumes: `build_csx` (Task 9); `read_log`, `read_unused`, `read_probe`, `pec_roots`, `c_box` (Task 8).
- Produces:
  - `job.json`, exactly: `{"spec": "../model.json", "port": int, "mode": "run" | "setup" | "xml", "threads": int, "t_max": float}`, `port` the excited port, 1-based.
  - `LOG, ERR = "log.txt", "err.txt"`: the orchestrator sends stdout and stderr there.
  - `SETUP_FAILED = 10`.
  - `run_kwargs(mode, threads, parts) -> dict`: setup `{"setup_only": True, "verbose": 2, "numThreads": threads, "debug_PEC": True}` plus `"debug_operator": True` when `parts`; run `{"numThreads": threads, "dump_statistics": True}`. No value is ever False (spec §11), `exact_endcriteria` never passed.
  - `main(argv=None) -> int`: deletes a stale `ABORT` first (C-20, r5); wraps the `build_csx(...)` call in `try/except ImportError` → 2 (openEMS imports inside it); calls `fdtd.Run(".", **run_kwargs(...))` from inside the job folder, so no absolute path reaches openEMS; a non-zero return in setup mode → `SETUP_FAILED` (MSVC's `abort()` and openEMS's console handler exit 3, so 3 is a crash); any other code is a crash.
  - Outputs:
    - run: `waves.npz` = `{"t_u": (n,), "u": (ports, n), "t_i": (n,), "i": (ports, n)}` from `port_ut_k` and `port_it_k`, cut to the shortest file.
    - setup: `setup.json` = `{"dt", "cells", "node", "unused", "dumps", "pec", "c_box"}`: dt, cells, node from `read_log(log.txt)`; unused from `read_unused(err.txt)`; `dumps` the relative names of the dump files written; `pec[k]` = `pec_roots` of port k's `nodes`; `c_box` = `{name: farads}` for the ports with `"part"`, at the log's dt (C-18). A log with no dt line raises (a crash).
    - xml: `Write2XML("model.xml")` (C-34).

- [ ] **Step 1: Write the failing tests**

```python
def write_job(tmp_path, spec, mode, parent="run"):
    run = tmp_path / parent
    job = run / "job-1-P1"
    job.mkdir(parents=True)
    (run / "model.json").write_text(json.dumps(spec), encoding="utf-8")
    (job / "job.json").write_text(json.dumps({"spec": "../model.json", "port": 1, "mode": mode, "threads": 1,
                                              "t_max": spec["excitation"]["t_max"]}), encoding="utf-8")
    return job


SMOKE = {**TINY, "mesh": {a: LINES[k].tolist() for k, a in enumerate("xyz")}, "ports": [  # tests/test_readers.py
    {"name": f"P{k}", "kind": "lumped", "dir": "z", "start": [x, -0.5, 0.0], "stop": [x, 0.5, 0.5],
     "nodes": [[x, 0.0, 0.0], [x, 0.0, 0.5], [0.0, 2.0, 0.0], [0.0, 0.0, 0.535]], "part": k == 1}
    for k, x in ((1, -5.0), (2, 5.0))]}


@pytest.mark.parametrize(("mode", "parts", "kw"), [
    ("setup", False, {"setup_only": True, "verbose": 2, "numThreads": 3, "debug_PEC": True}),
    ("setup", True, {"setup_only": True, "verbose": 2, "numThreads": 3, "debug_PEC": True, "debug_operator": True}),
    ("run", False, {"numThreads": 3, "dump_statistics": True})])
def test_run_keywords_never_carry_false(mode, parts, kw):  # spec 11: False drops the options after it
    got = worker.run_kwargs(mode, 3, parts)
    assert got == kw and False not in got.values() and "exact_endcriteria" not in got


def test_setup_mode_reads_the_log_and_the_dumps(tmp_path, monkeypatch):  # C-15, C-17, C-18, Review Focus 2
    log = fake_openems(monkeypatch)
    job = write_job(tmp_path, SMOKE, "setup")
    (job / worker.LOG).write_text(SETUP_LOG, encoding="utf-8")
    (job / worker.ERR).write_text("", encoding="utf-8")
    for f in DUMPS.iterdir():
        shutil.copy(f, job)
    monkeypatch.chdir(job)
    assert worker.main(["job.json"]) == 0
    s = json.loads((job / "setup.json").read_text(encoding="utf-8"))
    assert (s["dt"], s["cells"], s["node"], s["unused"]) == (1.73972e-13, [65, 33, 16], [2, 0, 0, 6], [])
    assert s["pec"][0] == pec_roots(DUMPS / "PEC_dump.vtp", LINES, SMOKE["ports"][0]["nodes"])
    assert s["c_box"] == {"P1": pytest.approx(2.3796e-14, rel=1e-3)}
    assert ("Run", (".",), worker.run_kwargs("setup", 1, True)) in log


def test_run_mode_writes_the_waves_from_the_probe_files(tmp_path, monkeypatch):  # Review Focus 2
    log = fake_openems(monkeypatch)
    job = write_job(tmp_path, TINY, "run")
    for name in ("port_ut_1", "port_it_1"):
        (job / name).write_text(PROBE, encoding="utf-8")
    monkeypatch.chdir(job)
    assert worker.main(["job.json"]) == 0
    w = np.load(job / "waves.npz")
    assert set(w.files) == {"t_u", "u", "t_i", "i"} and w["u"].shape == (1, 3)
    assert ("Run", (".",), worker.run_kwargs("run", 1, False)) in log


def test_xml_mode_clears_a_stale_abort_and_writes_a_relative_file(tmp_path, monkeypatch):  # C-20
    log = fake_openems(monkeypatch)
    job = write_job(tmp_path, TINY, "xml")
    (job / "ABORT").write_text("")
    monkeypatch.chdir(job)
    assert worker.main(["job.json"]) == 0
    assert not (job / "ABORT").exists() and ("Write2XML", ("model.xml",), {}) in log


def test_openems_that_will_not_import_is_exit_2(tmp_path, monkeypatch):  # C-31: the orchestrator names the variable
    monkeypatch.setitem(sys.modules, "CSXCAD", None)
    monkeypatch.setitem(sys.modules, "openEMS", None)
    monkeypatch.chdir(write_job(tmp_path, TINY, "xml"))
    assert worker.main(["job.json"]) == 2


def test_the_worker_imports_no_geometry_stack():  # spec 3.1, R21
    out = subprocess.run([sys.executable, "-I", "-c", "import sys, kicad_rf_studio.worker; print(sorted(m for m in "
                          "('shapely', 'scipy', 'matplotlib', 'skrf', 'openEMS', 'CSXCAD') if m in sys.modules))"],
                         capture_output=True, text=True).stdout
    assert out.strip() == "[]"


@pytest.mark.openems
@pytest.mark.parametrize("parent", ["run", "usuário ação"])  # Review Focus 2: a non-ASCII parent never reaches openEMS
@pytest.mark.parametrize("mode", ["xml", "setup", "run"])
def test_the_worker_on_a_tiny_model(tmp_path, mode, parent):
    job = write_job(tmp_path, TINY, mode, parent)
    with open(job / worker.LOG, "wb") as out, open(job / worker.ERR, "wb") as err:
        code = subprocess.run([sys.executable, "-I", "-u", "-m", "kicad_rf_studio.worker", "job.json"], cwd=job,
                              stdout=out, stderr=err, env={**os.environ, "OPENBLAS_NUM_THREADS": "1"}).returncode
    assert code == 0
    if mode == "xml":
        assert (job / "model.xml").read_text(encoding="utf-8").startswith("<openEMS>")
    if mode == "setup":
        s = json.loads((job / "setup.json").read_text(encoding="utf-8"))
        assert s["cells"] == [5, 5, 5] and s["dt"] > 0 and s["unused"] == [] and len(s["pec"]) == 1
    if mode == "run":
        w = np.load(job / "waves.npz")
        assert w["u"].shape[0] == 1 and w["u"].shape[1] >= 2 and np.isfinite(w["u"]).all()
```

- [ ] **Step 2: Run** `python -m pytest tests/test_worker.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `worker.py`, with `if __name__ == "__main__": sys.exit(main())`.
- [ ] **Step 4: Run** `python -m pytest tests/test_worker.py -q`, then `python -m pytest -m openems tests/test_worker.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: add the worker process (run, setup and xml modes)`

---

### Task 11: The stop rule and its replays

**Files:**
- Create: `src/kicad_rf_studio/stoprule.py`, `tests/traces.py`
- Test: `tests/test_stoprule.py`

**Interfaces:**
- Produces:
  - Constants (provisional, P0 retunes them): `PRESETS = {"draft": (-50.0, 1e-2), "normal": (-60.0, 2e-3), "strict": (-70.0, 5e-4)}`; `GROWTH_DB = 20.0`; `FLAT_DB, FLAT_S = 1.0, 5e-9`; `WINDOW_S = 2e-9`; `LAG_S = 1e-9`; `N_FREQ = 101`; `Z0 = 50.0`; `KEPT = frozenset({"converged", "flat", "t_max"})`.
  - `@dataclass(frozen=True) class Records`: `t_u, u, t_i, i, te, e` (numpy; `u`, `i` of shape (ports, n)).
  - `@dataclass(frozen=True) class Verdict`: `kind` ("diverged", "growth", "converged" or "flat"), `t` (the cut time), `residual_db`.
  - `residual_db(rec) -> np.ndarray`.
  - `stop_rule(rec, k, preset, exc) -> Verdict | None`: `k` the 0-based row of the excited port, `exc` the spec's excitation; pure and causal — a verdict at t uses no sample after t, so the verdict on a prefix is the earliest verdict of the whole record; fewer than 2 samples → None.

```text
diverged: the first non-finite u, i or e → Verdict("diverged", its time, nan)
p[n] = Σ_ports u[n]² + (Z0·i[n])²; R[n] = max p over t_u in (t_u[n] − WINDOW_S, t_u[n]]; R_dB = 10·log10(R / running max of p)
growth: E_dB of the energy samples above 0 (others skipped); armed where te > 2·t0; env[m] = max E_dB over the samples
        in (te[m] − WINDOW_S, te[m]] and over the last 4 samples; growth at the first armed m whose env ≥ GROWTH_DB +
        the minimum env of the armed samples before m
converged: the first n with t_u[n] > 2·t0 + LAG_S, R_dB[n] ≤ level and monitor(n) ≤ tol. monitor(n) = max over ports j
        and N_FREQ frequencies from f1 to f2 of |s_j(n) − s_j(m)|, m the last sample with t_u ≤ t_u[n] − LAG_S,
        s_j = (U_j − Z0·I_j)/(U_k + Z0·I_k), U and I the DFTs of u on t_u and of i on t_i cut at that sample;
        one cumulative sum over the samples gives every cut at once
flat: the first n with t_u[n] ≥ 2·t0 + FLAT_S and R_dB[n] > level whose R_dB over (t_u[n] − FLAT_S, t_u[n]] spans ≤ FLAT_DB
the earliest of diverged, growth, converged and flat wins (a tie in that order); none → None
```

  `# ponytail: each poll recomputes the rule on the whole record; fine below about 1e4 samples, make it incremental if polls lag`

  `tests/traces.py`: `trace(kind, ports=2, k=0, f1=457.5e6, f2=3.0195e9, dt=4.1e-11, t_end=40e-9) -> Records`, with fm, fw, t0 from f1 and f2 (§5.8):
  - `pulse(t) = sin(2π fm (t − t0))·exp(−(2π fw t/3 − 3)²)·(t < 2 t0)`; `ring_j(t) = a_j·exp(−max(t − 2 t0, 0)/τ)·sin(2π (1.0 + 0.3 j)·1e9·t)·(t > t0)`, a_j = 0.3 for j = k else 0.2, τ = 6 ns for "tmax" else 1 ns;
  - `t_u = arange(0, t_end, dt)`, `t_i = t_u + dt/2`; `u_k = 0.5·pulse(t_u) + ring_k(t_u)`, `i_k = (0.5·pulse(t_i) − ring_k(t_i))/Z0`; other ports `u_j = ring_j(t_u)`, `i_j = −ring_j(t_i)/Z0`.
  - On the last port, each added term also goes into its current as −term/Z0: "flat" adds `1e-2·sin(2π·1.2e9·t)`; "growth" adds `g(t)·sin(2π·1.5e9·t)`, `g = 1e-4·exp(max(t − 8e-9, 0)/1.3e-9)·(t > 8e-9)`; "nan" sets `u[last][min(200, n − 1)] = nan`.
  - The energy is `te = t_u`, `e = Σ_ports u² + (Z0·i)²`.

- [ ] **Step 1: Write the failing tests**

```python
EXC = {"f1": 457.5e6, "f2": 3.0195e9, "t0": 9 / (2 * math.pi * 1.281e9)}


@pytest.mark.parametrize(("kind", "preset", "verdict", "t_ns"), [
    ("converge", "draft", "converged", 9.31), ("converge", "normal", "converged", 10.70),
    ("converge", "strict", "converged", 11.81), ("flat", "normal", "flat", 12.30),
    ("nan", "normal", "diverged", 8.20), ("growth", "normal", "growth", None), ("tmax", "normal", None, None)])
def test_replay_at_decimations_1_to_16(kind, preset, verdict, t_ns):  # spec 6.3; a faster PC logs energy sparser
    rec = trace(kind)
    got = [stop_rule(replace(rec, te=rec.te[::d], e=rec.e[::d]), 0, preset, EXC) for d in range(1, 17)]
    assert {v and v.kind for v in got} == {verdict}
    if t_ns:
        assert {v.t for v in got} == {got[0].t} and got[0].t == pytest.approx(t_ns * 1e-9, abs=0.05e-9)


def prefix(rec, n):
    seen = rec.te <= rec.t_u[n - 1]
    return Records(rec.t_u[:n], rec.u[:, :n], rec.t_i[:n], rec.i[:, :n], rec.te[seen], rec.e[seen])


@pytest.mark.parametrize("chunk", [4, 64])
def test_polls_find_the_cut_of_the_whole_record(chunk):  # S does not depend on the stop latency (spec 6.3)
    rec = trace("converge")
    first = next(v for n in range(chunk, len(rec.t_u) + chunk, chunk)
                 if (v := stop_rule(prefix(rec, min(n, len(rec.t_u))), 0, "normal", EXC)))
    assert first == stop_rule(rec, 0, "normal", EXC) and stop_rule(prefix(rec, 1), 0, "normal", EXC) is None


def test_no_growth_before_the_pulse_ends():  # armed only after 2·t0
    rec = trace("converge")
    early = rec.te < 2 * EXC["t0"]
    dip = np.where(early, np.geomspace(1e-9, 1.0, len(rec.e)), rec.e)  # a deep dip inside the pulse: an unarmed
    assert stop_rule(replace(rec, e=dip), 0, "normal", EXC).kind == "converged"  # running minimum flags growth at 2.26 ns
```

- [ ] **Step 2: Run** `python -m pytest tests/test_stoprule.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `stoprule.py` (a searchsorted window for R, a cumulative DFT for the monitor).
- [ ] **Step 4: Run** the tests. Expected: PASS, in seconds.
- [ ] **Step 5: Commit.** `feat: add the stop rule with its synthetic replays (spec 6.3)`

---

### Task 12: Run folders, the lock and events

**Files:**
- Modify: `src/kicad_rf_studio/runs.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_runs.py`

**Interfaces:**
- Consumes: `data_dir` (Task 1).
- Produces:
  - `ascii_name(text) -> str` = `re.sub(r"[^A-Za-z0-9_-]", "_", text) or "_"`.
  - `run_dir_for(stem: str) -> Path` (not created) = `data_dir() / "runs" / f"{ascii_name(stem)}-{YYYYMMDD-HHMMSS}-{secrets.token_hex(2)}"` (C-23); callers pass the project folder's name, or "calibrate". `# ponytail: run folders are never deleted (C-23)`.
  - `job_dir(run_dir, k, name) -> Path` = `run_dir / f"job-{k}-{ascii_name(name)}"`; k is 1-based for run jobs and 0 for `job-0-setup` / `job-0-xml`.
  - `write_spec(run_dir, spec) -> None`: `run_dir.mkdir(parents=True)` (runs/ may not exist yet), then `model.json`.
  - `write_job(job, port, mode, threads, t_max) -> Path`: creates `job`, writes `job.json` (Task 10's fields), returns `job`.
  - `project_lock(project_path, run_dir)`, a context manager (C-24): creates `<project>.lock` with `os.O_CREAT | os.O_EXCL`, holding `{"pid", "run_dir", "started"}` (ISO time); a live holder raises `E_LOCKED {lock, run, started}`; a dead one prints `W_STALE_LOCK {lock, run}` and is replaced; removed on exit, exceptions included. Liveness: on Windows `OpenProcess(0x1000)` then `GetExitCodeProcess == 259` (STILL_ACTIVE), never `os.kill` (it terminates the process); elsewhere `os.kill(pid, 0)`, `PermissionError` counting as alive. `# ponytail: one lock per project, so two projects share the CPU; a reused pid keeps a stale lock alive, and E_LOCKED says to delete it`.
  - `emit(run_dir, kind, code, params: dict, job: int | None = None) -> None` (C-21): appends `{"t": round(time.time(), 3), "kind", "job", "code", "params"}` to `events.jsonl` and prints `render(code, **params)`; kinds progress, verdict, cost, result, message; `job` k for a job, 0 for `job-0-*`, None for run-level events. The params travel as one dict, so a field named `kind` or `job` cannot collide.
  - `MB_PER_MCELL, MB_PER_WORKER = 170, 50` (`# ponytail: provisional (spec 6.4); P0-C measures RAM`); `free_ram_mb() -> float`: `GlobalMemoryStatusEx`'s ullAvailPhys through ctypes on Windows, `MemAvailable` from `/proc/meminfo` elsewhere; `pool_size(cells, threads, free_mb, cpus) -> int` = `max(1, min(cpus // threads, int(free_mb // (MB_PER_MCELL * cells / 1e6 + MB_PER_WORKER))))` (spec 6.4).

- [ ] **Step 1: Write the failing tests** in `tests/test_runs.py`

```python
def test_run_and_job_folder_names_are_ascii(tmp_path, monkeypatch):  # Review Focus 2, C-23
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    d = runs.run_dir_for("projeto ação")
    assert d.parent == tmp_path / "data" / "runs" and re.fullmatch(r"projeto_a__o-\d{8}-\d{6}-[0-9a-f]{4}", d.name)
    assert runs.job_dir(d, 3, "C1·Ω").name == "job-3-C1__"
    assert runs.write_job(d / "job-1-P1", 1, "run", 2, 1e-9) == d / "job-1-P1"


def test_a_live_lock_refuses_and_a_stale_one_is_reclaimed(tmp_path, capsys):  # C-24
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    with pytest.raises(KrsError) as e:
        with runs.project_lock(pj, tmp_path / "new"):
            pass
    assert (e.value.code, e.value.params) == ("E_LOCKED", {"lock": str(lock), "run": "R", "started": "S"})
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    with runs.project_lock(pj, tmp_path / "new"):
        assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == os.getpid()
    assert not lock.exists() and capsys.readouterr().out == render("W_STALE_LOCK", lock=str(lock), run="R") + "\n"


def test_events_are_json_lines_mirrored_on_stdout(tmp_path, capsys):  # spec 3.3, 6.1
    params = {"kind": "gr_text", "uuid": "u", "layer": "F.Cu"}  # W_COPPER_DROPPED has a field named kind
    runs.emit(tmp_path, "message", "W_COPPER_DROPPED", params, job=2)
    e = json.loads((tmp_path / "events.jsonl").read_text(encoding="utf-8"))
    assert set(e) == {"t", "kind", "job", "code", "params"}
    assert (e["kind"], e["job"], e["code"], e["params"]) == ("message", 2, "W_COPPER_DROPPED", params)
    assert capsys.readouterr().out == render("W_COPPER_DROPPED", **params) + "\n"


def test_pool_size_follows_cores_and_ram():  # C-25, spec 6.4
    assert runs.pool_size(2_000_000, 4, 32_000, 16) == 4
    assert runs.pool_size(2_000_000, 4, 1_000, 16) == 2  # 1000 // (340 + 50)
    assert runs.pool_size(20_000_000, 4, 1_000, 16) == 1  # never 0
```

- [ ] **Step 2: Run** `python -m pytest tests/test_runs.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** Messages:
  - `E_LOCKED`: "Another run of this project has been running since {started} in {run}. Wait for it, or create a file named STOP in that folder to stop it; if no run is going on, delete {lock}."
  - `W_STALE_LOCK`: "Reclaimed {lock}: the run in {run} ended without releasing it."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: run folders, the project lock and events`

---

### Task 13: The job pool with STOP and ABORT

**Files:**
- Modify: `src/kicad_rf_studio/runs.py`, `src/kicad_rf_studio/core/messages.py`, `tests/conftest.py`
- Create: `tests/fake_worker.py`
- Test: `tests/test_pool.py`

**Interfaces:**
- Consumes: Task 12; `worker.LOG`, `worker.ERR`, `worker.SETUP_FAILED` (Task 10); `traces.trace` (Task 11, for the fake).
- Produces:
  - `WORKER = ("-I", "-u", "-m", "kicad_rf_studio.worker")`, `POLL_S = 1.0`, `ABORT_WAIT_S = 60.0` (module globals read at call time; tests patch them).
  - `worker_env(settings) -> dict`: `os.environ` plus `OPENBLAS_NUM_THREADS=1`, plus `CSXCAD_INSTALL_PATH` from `settings["openems_dir"]` when set.
  - `run_jobs(jobs, pool, run_dir, settings, watch=None) -> dict[Path, dict]`: `{"code": int | None, "stopped": bool}` per job.
  - `check_job(job, result, name, settings) -> None`, the one map from a job's exit to an outcome, used by calibrate, the setup gate and preview: `result["stopped"]` → `KeyboardInterrupt`; code 2 → `E_OPENEMS_DLL {value}` (`worker_env(settings).get("CSXCAD_INSTALL_PATH") or "unset"`, C-31); `SETUP_FAILED` → `E_SETUP_FAILED {log}`; any other non-zero → `E_WORKER_FAILED {job: name, exit_code, log}`; `log` is `str(job / LOG)`.

```text
start: subprocess.Popen([sys.executable, *WORKER, "job.json"], cwd=job (a Path), env=worker_env(settings),
       stdout=job/LOG, stderr=job/ERR, creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW on Windows,
       start_new_session=True elsewhere) — Ctrl+C reaches only the orchestrator.
loop: keep up to `pool` jobs running, in list order; time.sleep(POLL_S) between polls:
  a STOP file in run_dir, or KeyboardInterrupt, stops the run: ABORT goes into every running job folder, jobs not
  started never start, a running job with no port_ut_1 yet (still in setup) is killed at once, the others are
  killed if still alive after ABORT_WAIT_S; every job of a stopped run is "stopped".
  Otherwise a running job with watch(job) true gets ABORT once.
finally: any live worker is killed, so no process outlives the orchestrator.
```

  `tests/fake_worker.py` stands in for the worker, run as `python -I -u tests/fake_worker.py job.json`; it puts its own folder on `sys.path` (to import `traces`). On start it writes `env.json` = `{"cwd": os.getcwd(), "isolated": sys.flags.isolated, "OPENBLAS_NUM_THREADS": ..., "CSXCAD_INSTALL_PATH": ...}`, appends `start|end <port> <time.time()>` to `$KRS_FAKE_LOG` when set, reads `job.json` and `../model.json`. Then:
  - `$KRS_FAKE_EXIT` set: exits with that code at once, in any mode (2 a DLL failure, 10 a setup error, 7 a crash);
  - `$KRS_FAKE == "hang"`: sleeps 600 s and writes nothing, in any mode;
  - setup: writes `setup.json` = `{"dt": 1e-13, "cells": [len x, len y, len z], "node": [2, 0, 0, 1], "unused": [], "dumps": [], "pec": [[1, 2, 1, 2] per lumped port, [1, 2] per curve port], "c_box": {name: 2e-14 per port with "part"}}` updated with `json.loads($KRS_FAKE_SETUP or "{}")`, exits 0;
  - xml: writes `model.xml` with `<openEMS/>`, exits 0;
  - run, by `$KRS_FAKE` (default "converge"): "slow" is "converge" at 0.2 s per sample; "crash" (when `$KRS_FAKE_JOB` is unset or equals `job["port"]`, else "converge") writes the converge samples up to 12 ns, ignoring ABORT, and exits 7 with no `waves.npz`; any other kind uses `traces.trace(kind, len(ports), port − 1, f1, f2, t_end=job["t_max"])`:
    1. prints `Max. number of timesteps: N`, N = round(t_max/1e-13);
    2. writes the headers of `port_ut_k` and `port_it_k`;
    3. per sample: one flushed line in each probe file and a row `<wall s>\t<round(t/1e-13)>\t5e+07\t<energy>` in `openEMS_run_stats.txt`, then sleeps 1 ms, until an `ABORT` file appears;
    4. prints `Time for <n> iterations with <cells> cells : 1.00 sec` (n = N when every sample was written);
    5. writes `openEMS_stats.txt` (cells, 1e-13, n, n·1e-13, 1.0 and 5e7 × threads, one value per line) and `waves.npz` (the written samples); exits 0.

  `tests/conftest.py` gains:

```python
FAKE = Path(__file__).parent / "fake_worker.py"


@pytest.fixture
def fake(tmp_path, monkeypatch):
    """Workers are tests/fake_worker.py (KRS_FAKE* pick its behaviour), the data folder is under tmp_path, polls are
    fast and the version check passes. Returns the data folder."""
    monkeypatch.setattr(runs, "WORKER", ("-I", "-u", str(FAKE)))
    monkeypatch.setattr(runs, "POLL_S", 0.02)
    monkeypatch.setattr(runs, "ABORT_WAIT_S", 5.0)
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(runs, "check_openems", lambda: [])
    return tmp_path / "data"
```

- [ ] **Step 1: Write the failing tests** in `tests/test_pool.py`

```python
def tiny_jobs(run_dir, n):
    runs.write_spec(run_dir, TINY)
    return [runs.write_job(runs.job_dir(run_dir, k, f"P{k}"), 1, "run", 1, TINY["excitation"]["t_max"])
            for k in range(1, n + 1)]


def most_at_once(log):
    marks = sorted((float(t), 1 if what == "start" else -1)
                   for what, _, t in (line.split() for line in log.read_text().splitlines()))
    return max(itertools.accumulate(d for _, d in marks))


def test_the_pool_runs_isolated_workers_at_most_pool_at_once(tmp_path, fake, monkeypatch):  # spec 6.1, C-25
    monkeypatch.setenv("KRS_FAKE_LOG", str(tmp_path / "times.txt"))
    run_dir = tmp_path / "run"
    js = tiny_jobs(run_dir, 3)
    out = runs.run_jobs(js, 2, run_dir, {"openems_dir": "/x/openEMS"})
    assert [out[j] for j in js] == [{"code": 0, "stopped": False}] * 3
    env = json.loads((js[0] / "env.json").read_text(encoding="utf-8"))
    assert Path(env.pop("cwd")).resolve() == js[0].resolve()
    assert env == {"isolated": 1, "OPENBLAS_NUM_THREADS": "1", "CSXCAD_INSTALL_PATH": "/x/openEMS"}
    assert most_at_once(tmp_path / "times.txt") <= 2


def test_a_stop_file_aborts_the_running_jobs(tmp_path, fake, monkeypatch):  # C-26
    monkeypatch.setenv("KRS_FAKE", "slow")
    run_dir = tmp_path / "run"
    js = tiny_jobs(run_dir, 3)
    threading.Timer(1.0, lambda: (run_dir / "STOP").write_text("")).start()
    out = runs.run_jobs(js, 2, run_dir, {})
    assert [out[j]["stopped"] for j in js] == [True, True, True]
    assert (js[0] / "ABORT").is_file() and not (js[2] / "log.txt").exists()  # the third never started


def test_ctrl_c_kills_a_job_in_setup_and_leaves_no_process(tmp_path, fake, monkeypatch):  # Review Focus 5
    monkeypatch.setenv("KRS_FAKE", "hang")
    started, real_popen, real_sleep, calls = [], subprocess.Popen, time.sleep, []

    def popen(*a, **kw):
        started.append(real_popen(*a, **kw))
        return started[-1]

    def sleep(s):
        calls.append(s)
        if len(calls) == 3:
            raise KeyboardInterrupt
        real_sleep(s)

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(time, "sleep", sleep)
    run_dir = tmp_path / "run"
    t = time.monotonic()
    out = runs.run_jobs(tiny_jobs(run_dir, 1), 1, run_dir, {})
    assert list(out.values())[0]["stopped"] and time.monotonic() - t < 3 and started[0].poll() is not None


def test_watch_aborts_only_the_job_it_names(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("KRS_FAKE", "slow")
    run_dir = tmp_path / "run"
    js = tiny_jobs(run_dir, 2)
    out = runs.run_jobs(js, 2, run_dir, {}, watch=lambda job: job == js[0] and (job / "port_ut_1").exists())
    assert (js[0] / "ABORT").exists() and not (js[1] / "ABORT").exists()
    assert out[js[0]] == {"code": 0, "stopped": False}


@pytest.mark.parametrize(("exit_code", "code", "params"), [
    (2, "E_OPENEMS_DLL", {"value": "unset"}), (10, "E_SETUP_FAILED", {}), (7, "E_WORKER_FAILED", {"job": "setup",
                                                                                                 "exit_code": 7})])
def test_a_failed_job_maps_to_one_coded_error(tmp_path, fake, monkeypatch, exit_code, code, params):  # Review Focus 1
    monkeypatch.setenv("KRS_FAKE_EXIT", str(exit_code))
    monkeypatch.delenv("CSXCAD_INSTALL_PATH", raising=False)
    run_dir = tmp_path / "run"
    (job,) = tiny_jobs(run_dir, 1)
    out = runs.run_jobs([job], 1, run_dir, {})
    with pytest.raises(KrsError) as e:
        runs.check_job(job, out[job], "setup", {})
    log = {} if code == "E_OPENEMS_DLL" else {"log": str(job / "log.txt")}
    assert (e.value.code, e.value.params) == (code, {**params, **log})
    with pytest.raises(KeyboardInterrupt):
        runs.check_job(job, {"code": None, "stopped": True}, "setup", {})
```

- [ ] **Step 2: Run** `python -m pytest tests/test_pool.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `worker_env`, `run_jobs`, `check_job` and `tests/fake_worker.py`. Messages:
  - `E_OPENEMS_DLL`: "openEMS could not load its libraries (CSXCAD_INSTALL_PATH is {value}). Run setup-openems again, or set CSXCAD_INSTALL_PATH to the openEMS folder."
  - `E_SETUP_FAILED`: "openEMS could not set up the model; see {log}. Look at the model with `preview`."
  - `E_WORKER_FAILED`: "The {job} worker ended with code {exit_code}; see {log}. Report it if the log shows no cause."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: the job pool with STOP and ABORT, and one map from a job's exit to its outcome`

---

### Task 14: `calibrate`

**Files:**
- Modify: `src/kicad_rf_studio/runs.py`, `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`, `tests/conftest.py`
- Test: `tests/test_calibrate.py`

**Interfaces:**
- Consumes: `run_jobs`, `check_job`, `write_spec`, `write_job`, `job_dir`, `run_dir_for` (Tasks 12–13); `read_stats` (Task 8); `excitation`, `kappa` (Task 7).
- Produces:
  - `machine_key() -> str` = `f"{socket.gethostname()}/{os.cpu_count()}"` (C-32; never `platform.*`, R21).
  - `CAL_STEPS = 300`; `calibration_spec() -> dict`: 100 lines per axis at 1 mm (about 1e6 cells), one `substrate_0` (εr 4.5, κ = `kappa(4.5, 0.02, 915e6)`) over z 0–49 mm, one lumped port `"z"` from [50, 50, 49] to [50, 50, 50], the 915 MHz band's `excitation` with `t_max = CAL_STEPS × 1.9258e-12` (the 1 mm Courant step). `# ponytail: a uniform model; real runs refresh the speed`.
  - `choose(single: dict[int, float], parallel: dict[int, float], cpus) -> tuple[int, int, float]` (threads, pool, aggregate MC/s): 1 job at `cpus` threads or k jobs at `cpus // k` threads for the k in `parallel`; the best aggregate wins, a tie goes to fewer jobs.
  - `calibrate(settings) -> dict`: with N = `os.cpu_count()`, single jobs at 1, 2, 4 and N threads (deduplicated, at most N), then k parallel jobs at N // k threads for k ∈ {2, 4} with k ≤ N, in `run_dir_for("calibrate")`; job folders `job_dir(run_dir, i, f"{t}t")` for singles and `f"{k}x{N // k}t"` for each parallel job, i counting from 1; every job passes `check_job(job, result, "calibration", settings)`; each job's speed from `openEMS_stats.txt`; stores `settings["machines"][machine_key()] = {"threads", "pool", "aggregate_mcs", "single": {str(t): mcs}, "parallel": {str(k): aggregate mcs}, "at"}` and saves; prints `I_CALIBRATING` and `I_CALIBRATED`; returns the entry.
  - `ensure_calibrated(settings) -> dict`: the stored entry, or `calibrate(settings)` on a machine with none (spec 6.4).
  - `sizing(entry, cells) -> tuple[int, int]` (threads, pool) = `(entry["threads"], min(entry["pool"], pool_size(cells, entry["threads"], free_ram_mb(), os.cpu_count())))`. Every caller has a calibration (`ensure_calibrated` runs first).
  - `kicad-rf-studio calibrate`: `check_openems()` first (C-31), then `calibrate(load_settings())`.
  - `tests/conftest.py` gains:

```python
@pytest.fixture
def calibrated(fake):
    """A stored calibration of this machine: 2 jobs of 2 threads, 400 MC/s in all. Returns the data folder."""
    runs.save_settings({"machines": {runs.machine_key(): {
        "threads": 2, "pool": 2, "aggregate_mcs": 400.0, "single": {"2": 200.0}, "parallel": {"2": 400.0},
        "at": "2026-10-21T00:00:00"}}})
    return fake
```

- [ ] **Step 1: Write the failing tests**

```python
def test_choose_takes_the_best_aggregate_and_fewer_jobs_on_a_tie():
    assert runs.choose({1: 50.0, 2: 100.0, 4: 200.0, 8: 400.0}, {2: 600.0, 4: 560.0}, 8) == (4, 2, 600.0)
    assert runs.choose({8: 400.0}, {2: 400.0, 4: 400.0}, 8) == (8, 1, 400.0)


@pytest.mark.parametrize(("cpus", "single", "parallel"), [
    (8, {"1": 50.0, "2": 100.0, "4": 200.0, "8": 400.0}, {"2": 400.0, "4": 400.0}),
    (2, {"1": 50.0, "2": 100.0}, {"2": 100.0})])  # never a parallel job at 0 threads
def test_calibrate_measures_and_stores_this_machine(fake, monkeypatch, capsys, cpus, single, parallel):  # C-35
    monkeypatch.setattr(os, "cpu_count", lambda: cpus)  # the fake reports 50 MC/s per thread
    entry = runs.calibrate({})
    assert (entry["threads"], entry["pool"], entry["aggregate_mcs"]) == (cpus, 1, 50.0 * cpus)
    assert (entry["single"], entry["parallel"]) == (single, parallel)
    assert runs.load_settings()["machines"][runs.machine_key()] == entry
    assert capsys.readouterr().out.splitlines() == [render("I_CALIBRATING"),
                                                    render("I_CALIBRATED", threads=cpus, pool=1, speed=f"{50 * cpus}")]


def test_a_stored_calibration_is_used_without_running(calibrated, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", fail)  # tests/test_cli_cost.py
    assert runs.ensure_calibrated(runs.load_settings())["threads"] == 2


def test_sizing_caps_the_pool_by_ram(monkeypatch):  # C-25
    monkeypatch.setattr(os, "cpu_count", lambda: 16)
    monkeypatch.setattr(runs, "free_ram_mb", lambda: 1000.0)
    assert runs.sizing({"threads": 2, "pool": 4}, 2_000_000) == (2, 2)


@pytest.mark.openems
def test_calibrate_with_openems(tmp_path, monkeypatch):  # tier b, about 20–30 s
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    entry = runs.calibrate(runs.load_settings())
    assert entry["aggregate_mcs"] > 0 and 1 <= entry["threads"] <= os.cpu_count() and entry["pool"] >= 1
```

- [ ] **Step 2: Run** `python -m pytest tests/test_calibrate.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Messages (`speed` formatted `:.0f`):
  - `I_CALIBRATING`: "Measuring this machine's simulation speed, once (20–30 s)…"
  - `I_CALIBRATED`: "Calibrated: {pool} jobs at once with {threads} threads each, {speed} MC/s in all; `kicad-rf-studio calibrate` measures again."
- [ ] **Step 4: Run** the tests, then `python -m pytest -m openems tests/test_calibrate.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: calibrate the machine's speed and size the worker pool from it`

---

### Task 15: The model pipeline: `load` and `build_model`

**Files:**
- Create: `src/kicad_rf_studio/pipeline.py`
- Modify: `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `read_project`, `board_file`, `board_hash`, `mesh_n`, `load_board`, `build_geometry`, `mesh_with_lint`, `fit2d`, `check_fit2d`, `dt_floor_reference`, `ends`, `nominal_boxes`, `place`, `model_spec`, `grid_entry`.
- Produces:
  - `project_path(arg: str) -> Path`: a folder stands for its `project.json` (O-5).
  - `GEOMETRY_GATES = ("E_OPEN_IN_ROI", "E_SHORT_IN_ROI")`; `stops(notes) -> int`: 2 when a note is `E_LID_HEIGHT` (a refusal), 3 when a note is a geometry gate, else 0.
  - `load(path) -> tuple[dict, Board, Geometry, list[tuple[str, dict]]]`: notes = `W_BOARD_CHANGED {path}` when the board's sha256 differs (C-30), the board's warnings, the geometry's notes (E_ entries included), then `W_OFF_TOP_LAYER {net, layer}` per measured section off the top copper (C-9).
  - `@dataclass class Model`: `mesh: Mesh | None`, `spec: dict | None`, `blocked: list[tuple[str, dict]]`, `dt_ref: float | None`; the port names are `[q["name"] for q in spec["ports"]]`.
  - `build_model(project, board, geom) -> Model` (spec 6.1 step 2, C-42): `e = ends(...)`; `mesh_with_lint(geom, replace(geom.protected, boxes=nominal_boxes(e)), mesh_n(project))` (on E_EDGE_LINT: mesh and spec None, blocked); `fit2d` and `check_fit2d(fits, project["gates"]["fit2d_limit"], n)` (E_FIT2D, E_FIT2D_FINE and E_FIT2D_SHORT are blocked, the model is still built); `dt_ref = dt_floor_reference(mesh)` before anything is added; `place` each end, grid ends through `grid_entry` with their part's dict; `model_spec`. The refusals of `ends`, `place` and `grid_entry` propagate; the caller handles `stops(notes)`.

- [ ] **Step 1: Write the failing tests**

```python
def lpf(tmp_path, **edits):
    _, pj = run_new(tmp_path, "--lid-height", "2.5")  # tests/test_cli_new.py
    save_project(pj, {**load_project(pj), **edits})
    return pj


def test_a_folder_stands_for_its_project_json(tmp_path):  # O-5
    assert project_path(str(tmp_path)) == tmp_path / "project.json"
    assert project_path(str(tmp_path / "p.json")) == tmp_path / "p.json"


def test_load_warns_when_the_board_changed_since_new(tmp_path):  # C-30
    board = tmp_path / "b.kicad_pcb"
    board.write_bytes((FIX / "coupon_gcpw_pads.kicad_pcb").read_bytes())
    main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    board.write_bytes(board.read_bytes() + b"\n")
    assert load(tmp_path / "p" / "project.json")[3][0] == ("W_BOARD_CHANGED", {"path": str(board.resolve())})


def test_a_section_off_the_top_copper_warns(tmp_path, mini_board_file):  # C-9
    path = mini_board_file(EDGE + SEG.format(5, 10, 35, 10, 0.6, "B.Cu", "SIG", "s") + zone("F.Cu", "GND", 0, 0, 40, 20))
    pj = by_hand(tmp_path / "p" / "project.json", path, nets=("SIG",), stackup=kicad_default(0.8).to_json())
    assert ("W_OFF_TOP_LAYER", {"net": "SIG", "layer": "B.Cu"}) in load(pj)[3]


def test_the_lpf915_model(tmp_path):
    p, board, g, notes = load(lpf(tmp_path))
    m = build_model(p, board, g)
    assert stops(notes) == 0 and m.blocked == []
    assert [(q["name"], q["part"]) for q in m.spec["ports"]] == [
        ("P1", False), ("P2", False), ("C1", True), ("L1", True), ("C2", True), ("C3", True)]
    assert m.dt_ref == dt_floor_reference(m.mesh)


def test_an_off_chain_part_made_a_port_adds_a_run_and_changes_the_hash(tmp_path):  # spec 5.7, S-4
    p, board, g, _ = load(lpf(tmp_path))
    q = {**p, "others": [{**p["others"][0], "role": "port"}]}
    m, n = build_model(p, board, g), build_model(q, board, build_geometry(board, q))
    assert [x["name"] for x in n.spec["ports"]] == [x["name"] for x in m.spec["ports"]] + ["C4"]
    assert spec_hash(n.spec) != spec_hash(m.spec)


def test_lpf915_at_mesh_n_3_stops_at_fit2d_but_keeps_its_model(tmp_path):  # O-3, R-P2-21
    p, board, g, _ = load(lpf(tmp_path, mesh={"n": 3}))
    m = build_model(p, board, g)
    (code, params), = m.blocked
    assert (code, params["net"], params["n"]) == ("E_FIT2D_FINE", "RF_B", 3) and m.spec is not None


def test_a_failed_edge_lint_leaves_no_model(tmp_path, monkeypatch):
    p, board, g, _ = load(lpf(tmp_path))
    monkeypatch.setattr(gates, "build_mesh", lambda *a, **k: BAD_Y)  # tests/test_gates.py
    m = build_model(p, board, g)
    assert (m.mesh, m.spec, [c for c, _ in m.blocked]) == (None, None, ["E_EDGE_LINT"])


def test_a_missing_lid_height_is_a_refusal(tmp_path):
    assert stops(load(lpf(tmp_path, lid_height_mm=None))[3]) == 2
```

- [ ] **Step 2: Run** `python -m pytest tests/test_pipeline.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Messages:
  - `W_BOARD_CHANGED`: "The board {path} changed since `new` wrote project.json; its chain, ports and parts may be stale. Re-create the project with `new` if you moved copper."
  - `W_OFF_TOP_LAYER`: "Net {net} runs on {layer}, not on the top copper; the region, the cell size and dz0 use the top layer's substrate height (a Stage 1 limit). Check its fit2d result."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: build the model through the mesh gates (spec 6.1)`

---

### Task 16: The cost model

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_cost_model.py`

**Interfaces:**
- Consumes: `Model` (Task 15), `KrsError`.
- Produces:
  - `port_gates(ports, roots) -> list[tuple[str, dict]]` (C-15): 4 roots [rc, sc, rw, sw] (lumped): `E_PORT_OPEN {name, end: "reference"}` unless rc == rw ≥ 0; `E_PORT_OPEN {name, end: "signal"}` unless sc == sw ≥ 0; `E_PORT_SHORT {name}` when rw == sw; 2 roots (CurvePort, no caps): `E_PORT_OPEN` for a −1, `E_PORT_SHORT` when equal.
  - `duration(seconds) -> str`, floored: under 60 s "N s", under 1 h "N min", else "H h M min".
  - `smallest_cell(mesh) -> tuple[float, str, float]`: size in mm, axis, the cell's middle in KiCad's frame; the first smallest wins, in x, y, z order.
  - `driver(mesh, runs, parts) -> tuple[str, dict]` (C-36): a cell under d/3 − 1e-6 mm → `I_COST_DRIVER_CELL {size_um, axis, at_mm}`; else more than 2 runs → `I_COST_DRIVER_RUNS {runs, parts}`; else `I_COST_DRIVER_CELLS {d_mm}`.
  - `cost_notes(model, project, setup, threads, pool, per_job_mcs) -> list[tuple[str, dict]]` (spec 6.4): `I_COST_CELLS {nx, ny, nz, mcells, n, d_mm}`; `I_COST_SMALLEST {size_um, axis, at_mm}`; `I_COST_DT {dt, floor, ref, axis, x, y, z}` (the node mapped through the mesh lines, KiCad's frame); `I_COST_TIME {time, runs, t_max_ns, pool, threads}` with time = ceil(runs/pool) × cells × (T_max/dt) / (per_job_mcs·1e6); `I_COST_PREDICTED {time}` with the longest `t_stop` of `project["results"]["jobs"]` for T_max, when there are results; `I_COST_RAM {gb, pool}`, gb = pool·(MB_PER_MCELL·cells/1e6 + MB_PER_WORKER)/1024; then the driver. Formats: dt and ref `:.4e`; coordinates `:.3f`; mcells `:.2f`; d_mm `:.4f`; size_um `:.1f`; gb `:.1f`; floor and t_max_ns `:g`.

- [ ] **Step 1: Write the failing tests**

```python
def test_cost_notes_follow_the_cost_model():  # spec 6.4
    lines = np.linspace(0.0, 9.0, 10)
    m = Model(Mesh(lines, lines, lines, 1.0, 0.4, {}, {}), {"ports": [{"part": False}, {"part": False},
              {"part": True}]}, [], 1.5e-12)
    p = {"t_max_s": 1e-9, "gates": GATES, "mesh": {"n": 2}}
    notes = cost_notes(m, p, {"dt": 1e-12, "node": [0, 1, 2, 3]}, 4, 2, 1.0)
    assert notes == [
        ("I_COST_CELLS", {"nx": 10, "ny": 10, "nz": 10, "mcells": "0.00", "n": 2, "d_mm": "1.0000"}),
        ("I_COST_SMALLEST", {"size_um": "1000.0", "axis": "x", "at_mm": "0.500"}),
        ("I_COST_DT", {"dt": "1.0000e-12", "floor": "0.8", "ref": "1.5000e-12", "axis": "x", "x": "1.000",
                       "y": "-2.000", "z": "3.000"}),
        ("I_COST_TIME", {"time": "2 s", "runs": 3, "t_max_ns": "1", "pool": 2, "threads": 4}),
        ("I_COST_RAM", {"gb": "0.1", "pool": 2}),
        ("I_COST_DRIVER_RUNS", {"runs": 3, "parts": 1})]
    later = cost_notes(m, {**p, "results": {"jobs": [{"t_stop": 5e-10}, {"t_stop": 2e-10}]}}, {"dt": 1e-12,
                       "node": [0, 1, 2, 3]}, 4, 2, 1.0)
    assert ("I_COST_PREDICTED", {"time": "1 s"}) in later
    assert (duration(5307.2), duration(840), duration(45.4)) == ("1 h 28 min", "14 min", "45 s")


@pytest.mark.parametrize(("roots", "notes"), [
    ([[1, 2, 1, 2]], []), ([[1, 1, 1, 1]], [("E_PORT_SHORT", {"name": "P1"})]),
    ([[1, 2, 3, 2]], [("E_PORT_OPEN", {"name": "P1", "end": "reference"})]),
    ([[1, -1, 1, 2]], [("E_PORT_OPEN", {"name": "P1", "end": "signal"})]),
    ([[4, 9]], []), ([[4, 4]], [("E_PORT_SHORT", {"name": "P1"})]),  # a CurvePort has no caps
    ([[-1, 9]], [("E_PORT_OPEN", {"name": "P1", "end": "reference"})])])
def test_port_gates(roots, notes):  # C-15
    assert port_gates([{"name": "P1"}], roots) == notes
```

- [ ] **Step 2: Run** `python -m pytest tests/test_cost_model.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Messages:
  - `E_PORT_OPEN`: "Port {name}: its {end} end does not lie in its own pad's copper on the mesh. Check the port in project.json and look at it with `preview`."
  - `E_PORT_SHORT`: "Port {name}: its signal and reference are one piece of copper on the mesh, a short. Check the copper between them in KiCad and with `preview`."
  - `I_COST_CELLS`: "Cells: {nx} × {ny} × {nz} = {mcells} M (mesh n {n}, cell d {d_mm} mm)."
  - `I_COST_SMALLEST`: "Smallest cell: {size_um} µm across {axis}, at {axis} = {at_mm} mm."
  - `I_COST_DT`: "dt {dt} s (floor {floor} × {ref} s), set by the {axis} edge at ({x}, {y}, {z}) mm."
  - `I_COST_TIME`: "Worst case: {time} for {runs} runs to T_max {t_max_ns} ns, {pool} at once with {threads} threads each."
  - `I_COST_PREDICTED`: "Predicted from the last run's stop times: {time}."
  - `I_COST_RAM`: "RAM: about {gb} GB ({pool} jobs at once)."
  - `I_COST_DRIVER_CELL`: "Main cost: the {size_um} µm cell across {axis} at {at_mm} mm, under d/3, sets dt. Move or merge the copper edges there in KiCad."
  - `I_COST_DRIVER_RUNS`: "Main cost: {runs} runs, one per port, {parts} of them part ports."
  - `I_COST_DRIVER_CELLS`: "Main cost: the cell count. The cell d {d_mm} mm follows the narrowest width, gap or substrate height; a smaller region.expand_h shrinks it."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: the cost model and the port connectivity gate (spec 6.4, 5.6)`

---

### Task 17: `cost`: the setup gate and the command

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py`, `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_cli_cost.py`, revised and extended

**Interfaces:**
- Consumes: Tasks 12–16 (`runs.check_openems`, `runs.ensure_calibrated`, `runs.sizing`, `runs.free_ram_mb`, `runs.run_dir_for`, `runs.write_spec`, `runs.job_dir`, `runs.write_job`, `runs.run_jobs`, `runs.check_job`, `runs.emit`, `runs.load_settings`).
- Produces:
  - `prepare(model, emit) -> tuple[int, int, float]` (threads, pool, per-job MC/s), shared by `cost` and `run`: emits `check_openems()`'s warnings; `entry = ensure_calibrated(load_settings())`; `(threads, pool) = sizing(entry, cells)`; `W_RAM {need_gb, free_gb}` (`:.1f`) when one job needs more than the free RAM; per-job MC/s = `entry["aggregate_mcs"] / entry["pool"]`.
  - `setup_gate(model, project, run_dir, settings, threads) -> tuple[dict, list, list]` (setup data, blocked gates, warnings): one job `job-0-setup`, port 1, mode "setup", `t_max = 2·t0` (nothing in setup depends on T_max; `et`/`ht` hold NrTS lines); `check_job(job, result, "setup", settings)`; gates: `E_DT_FLOOR {dt, floor, ref, axis, x, y, z}` when dt < `gates.dt_floor` × `model.dt_ref` (C-17, W-3; `# ponytail: dt from the setup log (6 digits); openEMS_stats.txt exists only after a run`); `port_gates`; an unused primitive of a `port_*` or `lumped_*` property → `E_UNUSED_PRIMITIVE {property, type}`, of any other → `W_UNUSED_PRIMITIVE` (C-16, X-8).
  - `cost(path) -> int`:
    1. `load`; print W_FILLS_AS_SAVED, the 2D readout (moved from cli.py, unchanged), the notes.
    2. `stops == 2` → return 2. No ports → print `W_NO_PORTS`, return `stops(notes)`.
    3. `build_model`; print the blocked gates.
    4. With a spec: `prepare`; a run folder `run_dir_for(path.parent.name)`; `setup_gate`, emitting blocked gates as verdict events and warnings as message events; `W_GATE_LIMITS` after the gate lines when `project["gates"] != GATES` (C-10); the cost notes as `cost` events.
    5. Return 3 if any gate blocked (geometry, mesh or setup), else 0 (C-22).
  - `cli.main` returns `args.func(args) or 0` and maps KeyboardInterrupt to 130; `cost`, `run`, `preview` take a project file or folder and import `pipeline` inside the command.

- [ ] **Step 1: Write the failing tests.**

  First revise the plan-2 tests on purpose (CO-1), with `FILLS = render("W_FILLS_AS_SAVED")` and `PORTLESS = render("W_NO_PORTS")`:
  - `test_cost_prints_2d_readout`: `out[0] == FILLS`, the header at `out[1]`, the row at `out[2]`.
  - `test_cost_on_45_degree_coupon`: `[FILLS, W_NO_SECTIONS, W_STAIRCASED, PORTLESS]`.
  - `test_a_microstrip_has_no_gap_and_its_mask_lowers_z0`: `[FILLS, HEADER, row, PORTLESS]`.
  - `test_rows_follow_the_chain_then_the_position_and_the_notes_come_last`: exit 2; `out[:2] == [FILLS, HEADER]`, rows `out[2:-1]`, `out[-1] == render("E_LID_HEIGHT", refs="SH1")`.
  - `test_a_short_at_the_cut_gets_a_note_in_place_of_its_row`: `(3, [FILLS, HEADER, SHORT, W_NO_OUTLINE, E_SHORT_IN_ROI, PORTLESS])`.
  - `test_copper_with_no_net_on_the_line_gets_a_note_in_place_of_its_row`: `(0, [FILLS, HEADER, SHORT, W_NETLESS_COPPER, W_NO_OUTLINE, PORTLESS])`.
  - `test_each_arm_of_a_hairpin_reads_as_the_line_it_is`: the rows are `out[2:5]`.
  - `test_a_line_on_the_bottom_copper_reads_under_the_bottom_mask`: the row is `out[2]`; the B.Cu case also prints `render("W_OFF_TOP_LAYER", net="SIG", layer="B.Cu")`.
  - `test_a_project_that_cannot_be_read_is_a_user_error[folder]`: the path is `pj / "project.json"`, reason "file not found".
  - `test_cost_starts_no_worker` keeps its Popen ban and its `sys.modules` check on `coupon_ms`.

  Then add:

```python
def test_cost_runs_one_setup_worker_and_prints_the_cost(tmp_path, capsys, calibrated, monkeypatch):  # spec 3.2
    started, real = [], subprocess.Popen
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: started.append((cmd, kw["cwd"])) or real(cmd, **kw))
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    capsys.readouterr()
    assert main(["cost", str(pj.parent)]) == 0  # a folder works too
    out = capsys.readouterr().out.splitlines()
    assert len(started) == 1 and started[0][0][-1] == "job.json" and started[0][1].name == "job-0-setup"
    assert out[:2] == [render("W_FILLS_AS_SAVED"), HEADER]
    assert [line.split(":")[0].split(" ")[0] for line in out[3:]] == ["Cells", "Smallest", "dt", "Worst", "RAM", "Main"]
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # spec 3.1


@pytest.mark.parametrize(("setup", "code", "line"), [
    ({"pec": [[1, 1, 1, 1], [1, 2, 1, 2]]}, 3, render("E_PORT_SHORT", name="P1")),
    ({"unused": [["Box", "port_resist_2"]]}, 3, render("E_UNUSED_PRIMITIVE", property="port_resist_2", type="Box")),
    ({"unused": [["LinPoly", "metal"]]}, 0, render("W_UNUSED_PRIMITIVE", property="metal", type="LinPoly"))])
def test_the_setup_gates(tmp_path, capsys, calibrated, monkeypatch, setup, code, line):  # C-15, C-16
    monkeypatch.setenv("KRS_FAKE_SETUP", json.dumps(setup))
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    assert main(["cost", str(pj)]) == code and line in capsys.readouterr().out.splitlines()


def test_the_timestep_floor_names_the_limiting_node_in_kicads_frame(tmp_path, capsys, calibrated, monkeypatch):
    monkeypatch.setenv("KRS_FAKE_SETUP", json.dumps({"dt": 1e-15, "node": [1, 3, 4, 5]}))  # C-17
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    p, board, g, _ = load(pj)
    m = build_model(p, board, g)
    assert main(["cost", str(pj)]) == 3
    assert render("E_DT_FLOOR", dt="1.0000e-15", floor="0.8", ref=f"{m.dt_ref:.4e}", axis="y",
                  x=f"{m.mesh.x[3]:.3f}", y=f"{0.0 - m.mesh.y[4]:.3f}", z=f"{m.mesh.z[5]:.3f}") in capsys.readouterr().out


def test_a_failed_fit2d_still_prints_the_cost_and_exits_3(tmp_path, capsys, calibrated):  # C-22, C-10
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    save_project(pj, {**load_project(pj), "gates": {"fit2d_limit": 0.02, "dt_floor": 0.8}})  # it reads 2.47 %
    assert main(["cost", str(pj)]) == 3
    out = capsys.readouterr().out
    assert "misses the 2D reference on net LINE" in out and "Worst case:" in out
    assert render("W_GATE_LIMITS", fit2d_limit="0.02", dt_floor="0.8") in out.splitlines()


@pytest.mark.parametrize(("exit_code", "err"), [
    ("2", render("E_OPENEMS_DLL", value="unset") + "\n"), ("7", "The calibration worker ended with code 7")])
def test_a_fresh_machine_that_cannot_load_openems_gets_a_coded_refusal(tmp_path, capsys, fake, monkeypatch,
                                                                       exit_code, err):  # Review Focus 1
    monkeypatch.setenv("KRS_FAKE_EXIT", exit_code)  # no calibration yet: calibrate starts the first worker
    monkeypatch.delenv("CSXCAD_INSTALL_PATH", raising=False)
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    capsys.readouterr()
    assert main(["cost", str(pj)]) == 2
    out, got = capsys.readouterr()
    assert out.splitlines()[:2] == [render("W_FILLS_AS_SAVED"), HEADER] and got.startswith(err)


def test_cost_prints_the_readout_before_it_needs_openems(tmp_path, capsys, fake, monkeypatch):  # C-31
    def missing():
        raise KrsError("E_OPENEMS_MISSING", python="py", command="cmd")

    monkeypatch.setattr(runs, "check_openems", missing)
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    capsys.readouterr()
    assert main(["cost", str(pj)]) == 2
    out, err = capsys.readouterr()
    assert out.splitlines()[:2] == [render("W_FILLS_AS_SAVED"), HEADER]
    assert err == render("E_OPENEMS_MISSING", python="py", command="cmd") + "\n"


def test_ctrl_c_during_the_setup_job_exits_130_and_leaves_no_process(tmp_path, calibrated, monkeypatch):  # RF 5
    monkeypatch.setenv("KRS_FAKE", "hang")
    started, real_popen, real_sleep, calls = [], subprocess.Popen, time.sleep, []

    def popen(*a, **kw):
        started.append(real_popen(*a, **kw))
        return started[-1]

    def sleep(s):
        calls.append(s)
        if len(calls) == 3:
            raise KeyboardInterrupt
        real_sleep(s)

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(time, "sleep", sleep)
    assert main(["cost", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 130
    assert len(started) == 1 and started[0].poll() is not None


@pytest.mark.openems
def test_cost_on_the_pad_coupon_with_openems(tmp_path, capsys, monkeypatch):  # tier b: setup-only at n = 2
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    runs.save_settings({"machines": {runs.machine_key(): {"threads": 2, "pool": 1, "aggregate_mcs": 200.0}}})
    assert main(["cost", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 0
    out = capsys.readouterr().out
    assert "Cells: " in out and "Main cost:" in out and "unused" not in out
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

- [ ] **Step 2: Run** `python -m pytest tests/test_cli_cost.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Messages:
  - `W_NO_PORTS`: "project.json has no ports, so cost stops after the 2D estimate. Create the project with `new` between two pads to simulate it."
  - `W_RAM`: "One job needs about {need_gb} GB of RAM and {free_gb} GB is free, so jobs run one at a time and may still swap. Close other programs, or shrink the model (region.expand_h, mesh.n in project.json)."
  - `E_DT_FLOOR`: "openEMS's timestep {dt} s is below {floor} × the reference {ref} s, set by the {axis} edge at ({x}, {y}, {z}) mm. A tiny cell there makes the run slow; move or merge the copper edges near it in KiCad."
  - `E_UNUSED_PRIMITIVE`: "openEMS left a {type} of {property} unused: it touches no mesh edge, so that port or part is not in the model. Look at it with `preview`."
  - `W_UNUSED_PRIMITIVE`: "openEMS left a {type} of {property} unused: a sliver smaller than a cell, left out of the model. Look at it with `preview` if it should carry current."
  - `W_GATE_LIMITS`: "project.json sets gates.fit2d_limit {fit2d_limit} and gates.dt_floor {dt_floor}, not 0.03 and 0.8, so this verdict is outside the validated limits. Set them back to 0.03 and 0.8 for a validated result." (`:g`)
- [ ] **Step 4: Run** the full suite, then `python -m pytest -m openems tests/test_cli_cost.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: run the setup-only gate in cost and print the cost model (spec 3.2, 6.4)`

---

### Task 18: `run`

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py`, `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: everything above; `stop_rule`, `Records`, `KEPT` (Task 11); `read_probe`, `read_run_stats`, `read_stats`, `read_log` (Task 8); `spec_hash` (Task 7).
- Produces:
  - `records(job, ports, dt) -> Records`: every port's probe files cut to the shortest, the energy from `openEMS_run_stats.txt` at te = timestep × dt; a missing file gives empty arrays (setup is still running, or the worker died).
  - `VERDICTS = {"converged": "I_JOB_CONVERGED", "flat": "W_JOB_FLAT", "t_max": "W_JOB_T_MAX", "diverged": "E_JOB_DIVERGED", "growth": "E_JOB_GROWTH", "unclassified": "W_JOB_UNCLASSIFIED", "stopped": "W_JOB_STOPPED"}`; every verdict event's params are `{"port", "t_ns", "residual_db", "log"}` (`:.2f`, `:.1f`, the job's log path).
  - `run(path) -> int` (spec 6.1, C-42):
    1. `read_project`; no ports → `E_NO_PORTS` (exit 2).
    2. Take `project_lock(path, run_dir_for(path.parent.name))`, create the run folder. From here a `KrsError` is emitted as a message event and `run` returns 2.
    3. Emit `W_FILLS_AS_SAVED` and the notes; `stops(notes)` → return 2 or 3.
    4. `build_model`; blocked → emit as verdicts (and `W_GATE_LIMITS` when the gates differ) and return 3.
    5. `prepare` (Task 17).
    6. `setup_gate`; blocked → return 3; else emit `I_GATES_PASSED {dt}` (`:.4e`), `W_GATE_LIMITS` when the gates differ, and the cost notes (runtime shown before every run). A STOP or Ctrl+C up to here propagates as KeyboardInterrupt: exit 130, the lock released, `results` untouched.
    7. One job per port: `job-k-<name>`, port k, mode "run", T_max. Emit `I_RUN_START`, then `run_jobs` with a `watch` that reads `records`, calls `stop_rule` with the project's preset, keeps the verdict, and emits `I_PROGRESS {port, t_ns, residual_db, speed_mcs}` (speed from `read_run_stats`, /1e6, `:.1f`) once per new energy row.
    8. Classify each job after it exits, the first match winning:
       1. a non-finite sample → "diverged";
       2. a non-zero exit or no `waves.npz` → "stopped" if the job was stopped, else "unclassified";
       3. the live verdict;
       4. `stop_rule` on the final records;
       5. the job was stopped → "stopped";
       6. iterations = NrTS in the log → "t_max";
       7. otherwise "unclassified" (spec 6.3: never silently done).

       Emit each verdict, followed by `W_GATE_LIMITS` when the gates differ from GATES (C-10).
    9. Write `results`, re-reading `project.json` under the lock and replacing only that key: `{"model_hash", "run_dir", "gates", "dt", "c_box", "wall_s", "jobs": [{"port", "verdict", "t_cut", "t_stop", "residual_db", "waves"}]}`; `waves` relative to `run_dir` or None; `t_stop` the last probe time (None without samples); `t_cut` the verdict's time or None.
    10. Refresh the calibration's `aggregate_mcs` with Σ cells·iterations / the wall time of the job phase.
    11. Emit `I_RESULTS {kept, runs, wall, path}` (`wall = duration(wall_s)`) as a `result` event; return 0 if every verdict is in KEPT, else 4 (C-22, C-29).

    A run that started jobs replaces `results` (a stopped one too); a gate-blocked run leaves them.

- [ ] **Step 1: Write the failing tests**

```python
def coupon(tmp_path, preset="draft"):
    return new_project(tmp_path, "coupon_gcpw_pads", preset=preset)  # tests/test_cli_cost.py


def verdict_codes(run_dir):
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return {e["job"]: e["code"] for e in events if e["kind"] == "verdict"}


def test_run_converges_and_records_its_results(tmp_path, calibrated):  # spec 6.1, 3.3, C-29
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    run_dir = Path(r["run_dir"])
    assert [(j["port"], j["verdict"]) for j in r["jobs"]] == [("P1", "converged"), ("P2", "converged")]
    assert r["jobs"][0]["t_cut"] == pytest.approx(9.31e-9, abs=0.1e-9) and r["jobs"][0]["residual_db"] <= -50
    assert all((run_dir / j["waves"]).is_file() for j in r["jobs"])
    assert r["model_hash"] == spec_hash(json.loads((run_dir / "model.json").read_text(encoding="utf-8")))
    assert (r["gates"], r["dt"], r["c_box"]) == ({"fit2d_limit": 0.03, "dt_floor": 0.8}, 1e-13, {})
    kinds = {json.loads(line)["kind"] for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()}
    assert kinds == {"message", "verdict", "cost", "progress", "result"}
    assert not (pj.parent / "project.json.lock").exists()
    assert runs.load_settings()["machines"][runs.machine_key()]["aggregate_mcs"] != 400.0  # refreshed


@pytest.mark.parametrize(("kind", "code", "verdict"), [
    ("nan", 4, "E_JOB_DIVERGED"), ("tmax", 0, "W_JOB_T_MAX"), ("flat", 0, "W_JOB_FLAT"), ("growth", 4, "E_JOB_GROWTH")])
def test_each_verdict_through_run(tmp_path, calibrated, monkeypatch, kind, code, verdict):  # spec 6.3, R3-107
    monkeypatch.setenv("KRS_FAKE", kind)
    pj = coupon(tmp_path, "normal")  # the replays pin these at Normal
    assert main(["run", str(pj)]) == code
    assert verdict_codes(Path(load_project(pj)["results"]["run_dir"]))[1] == verdict


def test_a_crashed_job_is_unclassified_and_the_others_finish(tmp_path, capsys, calibrated, monkeypatch):  # RF 4
    monkeypatch.setenv("KRS_FAKE", "crash")  # past the converge cut, then exit 7 with no waves
    monkeypatch.setenv("KRS_FAKE_JOB", "2")
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 4
    r = load_project(pj)["results"]
    assert [j["verdict"] for j in r["jobs"]] == ["converged", "unclassified"] and r["jobs"][1]["waves"] is None
    log = Path(r["run_dir"]) / "job-2-P2" / "log.txt"
    assert any(line.startswith("P2: the worker ended") and str(log) in line for line in capsys.readouterr().out.splitlines())


def test_a_stop_file_stops_the_run_found_from_the_lock(tmp_path, calibrated, monkeypatch):  # C-26, spec 3.1
    monkeypatch.setenv("KRS_FAKE", "slow")
    pj = coupon(tmp_path)

    def stopper():
        while True:
            try:
                run_dir = Path(json.loads((pj.parent / "project.json.lock").read_text(encoding="utf-8"))["run_dir"])
                break
            except (OSError, ValueError):
                time.sleep(0.01)
        while not any(run_dir.glob("job-1-*/port_ut_1")):
            time.sleep(0.01)
        (run_dir / "STOP").write_text("")

    threading.Thread(target=stopper, daemon=True).start()
    assert main(["run", str(pj)]) == 4
    assert {j["verdict"] for j in load_project(pj)["results"]["jobs"]} == {"stopped"}
    assert not (pj.parent / "project.json.lock").exists()


def test_ctrl_c_in_the_job_phase_stops_the_run_and_frees_the_lock(tmp_path, calibrated, monkeypatch):  # RF 5
    monkeypatch.setenv("KRS_FAKE", "slow")
    real_sleep, fired = time.sleep, []

    def sleep(s):
        if not fired and any(calibrated.glob("runs/*/job-1-*/port_ut_1")):
            fired.append(1)
            raise KeyboardInterrupt
        real_sleep(s)

    monkeypatch.setattr(time, "sleep", sleep)
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 4 and not (pj.parent / "project.json.lock").exists()
    assert {j["verdict"] for j in load_project(pj)["results"]["jobs"]} == {"stopped"}


@pytest.mark.parametrize(("edits", "code", "first"), [
    ({"lid_height_mm": None}, 2, render("E_LID_HEIGHT", refs="SH1")),
    ({"lid_height_mm": 2.5, "mesh": {"n": 3}}, 3, "The fine mesh (mesh.n 3) still misses the 2D reference on net RF_B")])
def test_run_stops_before_any_worker(tmp_path, capsys, calibrated, monkeypatch, edits, code, first):  # C-42
    pj = new_project(tmp_path, "lpf915")
    save_project(pj, {**load_project(pj), **edits})
    monkeypatch.setattr(subprocess, "Popen", fail)
    capsys.readouterr()
    assert main(["run", str(pj)]) == code
    assert any(line.startswith(first) for line in capsys.readouterr().out.splitlines())
    assert "results" not in load_project(pj)


def test_run_refuses_a_project_without_ports_or_a_reference(tmp_path, capsys, calibrated):  # O-6
    assert main(["run", str(new_project(tmp_path, "coupon_ms"))]) == 2
    assert capsys.readouterr().err == render("E_NO_PORTS") + "\n"
    pj = coupon(tmp_path)
    d = load_project(pj)
    d["ports"][0]["reference"] = None
    save_project(pj, d)
    assert main(["run", str(pj)]) == 2
    assert render("E_NO_REFERENCE", signal="TP1.1") in capsys.readouterr().out.splitlines()


def test_a_held_lock_refuses_the_run(tmp_path, capsys, calibrated):
    pj = coupon(tmp_path)
    (pj.parent / "project.json.lock").write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}))
    assert main(["run", str(pj)]) == 2 and "Another run of this project" in capsys.readouterr().err


def test_gate_limits_that_differ_are_recorded_and_said(tmp_path, capsys, calibrated):  # C-10
    pj = coupon(tmp_path)
    save_project(pj, {**load_project(pj), "gates": {"fit2d_limit": 0.05, "dt_floor": 0.8}})
    assert main(["run", str(pj)]) == 0
    out = capsys.readouterr().out.splitlines()
    limits = render("W_GATE_LIMITS", fit2d_limit="0.05", dt_floor="0.8")
    assert [out[i + 1] for i, line in enumerate(out) if line.startswith(("Gates passed", "P1: converged",
                                                                         "P2: converged"))] == [limits] * 3
    assert load_project(pj)["results"]["gates"] == {"fit2d_limit": 0.05, "dt_floor": 0.8}


def test_a_model_larger_than_free_ram_runs_one_job_at_a_time(tmp_path, capsys, calibrated, monkeypatch):  # spec 6.4
    monkeypatch.setattr(runs, "free_ram_mb", lambda: 100.0)
    assert main(["run", str(coupon(tmp_path))]) == 0
    out = capsys.readouterr().out.splitlines()
    ram = next(i for i, line in enumerate(out) if line.startswith("One job needs about"))
    assert ram < next(i for i, line in enumerate(out) if line.startswith("Running 2 jobs, 1 at once"))


def test_lpf915_runs_one_job_per_port_and_records_c_box(tmp_path, calibrated, monkeypatch):  # R3-095, C-18
    monkeypatch.setenv("KRS_FAKE", "tmax")
    pj = new_project(tmp_path, "lpf915")
    save_project(pj, {**load_project(pj), "lid_height_mm": 2.5})
    assert main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    assert sorted(d.name for d in Path(r["run_dir"]).glob("job-[1-9]*")) == [
        "job-1-P1", "job-2-P2", "job-3-C1", "job-4-L1", "job-5-C2", "job-6-C3"]
    assert set(r["c_box"]) == {"C1", "L1", "C2", "C3"}


@pytest.mark.openems
def test_new_cost_run_on_the_pad_coupon(tmp_path, monkeypatch):  # spec 9.2: P = 2, M = 0, Draft, short T_max
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")  # a fresh machine: cost calibrates first
    pj = coupon(tmp_path)
    save_project(pj, {**load_project(pj), "t_max_s": 3e-10})
    assert main(["cost", str(pj)]) == 0 and main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    assert [j["verdict"] for j in r["jobs"]] == ["t_max", "t_max"] and len(r["model_hash"]) == 64
    for j in r["jobs"]:
        w = np.load(Path(r["run_dir"]) / j["waves"])
        assert w["u"].shape[0] == 2 and np.isfinite(w["u"]).all()
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

- [ ] **Step 2: Run** `python -m pytest tests/test_run.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Messages:
  - `I_GATES_PASSED`: "Gates passed: edge lint, fit2d, timestep floor (dt {dt} s), port connectivity and unused primitives."
  - `I_RUN_START`: "Running {runs} jobs, {pool} at once, in {folder}. Create a file named STOP there, or press Ctrl+C, to stop."
  - `I_PROGRESS`: "{port}: {t_ns} ns, residual {residual_db} dB, {speed_mcs} MC/s."
  - `I_JOB_CONVERGED`: "{port}: converged at {t_ns} ns (residual {residual_db} dB)."
  - `W_JOB_FLAT`: "{port}: not converged at {residual_db} dB; the residual stopped falling at {t_ns} ns. S is kept and flagged; look for a resonance or an open port with `preview`."
  - `W_JOB_T_MAX`: "{port}: reached T_max ({t_ns} ns) at a residual of {residual_db} dB. S is kept and flagged; raise t_max_s in project.json for a converged result."
  - `E_JOB_DIVERGED`: "{port}: diverged at {t_ns} ns (NaN or inf), so its S is not kept. Look for tiny cells with `cost` and at the model with `preview`."
  - `E_JOB_GROWTH`: "{port}: the energy grew 20 dB after the pulse, at {t_ns} ns, so its S is not kept. Look at the model with `preview`."
  - `W_JOB_UNCLASSIFIED`: "{port}: the worker ended before T_max without a verdict, so its S is not kept. See {log}."
  - `W_JOB_STOPPED`: "{port}: stopped, so its S is not kept. Run `run` again for results."
  - `I_RESULTS`: "{kept} of {runs} jobs kept S, in {wall}; results recorded in {path}."
- [ ] **Step 4: Run** the full suite, then `python -m pytest -m openems tests/test_run.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: run every excitation under the stop rule and record the results (spec 6.1)`

---

### Task 19: `preview`

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py`, `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_preview.py`

**Interfaces:**
- Produces:
  - `appcsxcad(settings) -> str | None` = `shutil.which("AppCSXCAD", path=os.pathsep.join(filter(None, (settings.get("openems_dir"), os.environ.get("CSXCAD_INSTALL_PATH"), os.environ.get("PATH")))))`.
  - `open_viewer(exe, job) -> None`: `subprocess.Popen([exe, "model.xml"], cwd=job, ...)`, detached (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP on Windows, `start_new_session=True` elsewhere), not waited for; AppCSXCAD fails on non-ASCII paths, so it gets a relative name (spec 8).
  - `preview(path) -> int`: `load` (`stops == 2` → 2); `build_model`, print the blocked gates, return 3 when the spec is None (otherwise go on: preview is how one looks at a failing model); `check_openems()`; a run folder with `job-0-xml` (mode "xml", port 1) and `check_job(job, result, "xml", settings)`; no AppCSXCAD → `E_APPCSXCAD_MISSING {path}`; `open_viewer`; print `I_PREVIEW {path}`; return 0.
  - The command `kicad-rf-studio preview PROJECT`.

- [ ] **Step 1: Write the failing tests**

```python
def test_preview_writes_the_xml_in_a_job_folder_and_opens_it(tmp_path, capsys, fake, monkeypatch):  # C-34
    opened = []
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: opened.append((exe, job)))
    assert main(["preview", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 0
    (exe, job), = opened
    assert job.name == "job-0-xml" and (job / "model.xml").is_file()
    assert capsys.readouterr().out.splitlines()[-1] == render("I_PREVIEW", path=str(job / "model.xml"))


def test_the_viewer_opens_a_relative_file_from_the_job_folder(tmp_path, monkeypatch):  # Review Focus 2
    seen = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: seen.append((cmd, kw["cwd"])))
    pipeline.open_viewer("AppCSXCAD", tmp_path)
    assert seen == [(["AppCSXCAD", "model.xml"], tmp_path)]


def test_a_missing_appcsxcad_names_the_file(tmp_path, capsys, fake, monkeypatch):
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: None)
    assert main(["preview", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 2
    assert capsys.readouterr().err.startswith("AppCSXCAD was not found")


@pytest.mark.openems
def test_preview_writes_a_real_model_xml(tmp_path, monkeypatch):  # tier b: the XML write, no GUI
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    opened = []
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: opened.append(job))
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    assert main(["preview", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 0
    root = ET.parse(opened[0] / "model.xml").getroot()
    assert root.tag == "openEMS" and root.find("FDTD/BoundaryCond").get("xmin") == "MUR"
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
```

- [ ] **Step 2: Run** `python -m pytest tests/test_preview.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Messages:
  - `I_PREVIEW`: "Opened {path} in AppCSXCAD."
  - `E_APPCSXCAD_MISSING`: "AppCSXCAD was not found; open {path} in it by hand, or run setup-openems to record the openEMS folder."
- [ ] **Step 4: Run** the full suite, then `python -m pytest -m openems tests/test_preview.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: preview the model in AppCSXCAD`

---

### Task 20: The CurvePort behind `allow_curve_port`

**Files:**
- Modify: `src/kicad_rf_studio/core/model/ports.py`, `src/kicad_rf_studio/core/model/csx.py`, `src/kicad_rf_studio/core/model/readers.py`, `src/kicad_rf_studio/worker.py`
- Test: `tests/test_model_ports.py`, `tests/test_model_csx.py`, `tests/test_readers.py`, `tests/test_worker.py`

**Interfaces:**
- Produces:
  - `ends` accepts a curve_port when `project["allow_curve_port"]` is true (C-37).
  - `place` of a curve_port end: `{"name", "kind": "curve", "dir": None, "start", "stop", "nodes": [start, stop], "part": True}`; start the reference pad's centre, stop the signal pad's, each snapped to the nearest x and y lines, at the copper slab's z1 (`# ponytail: the top face for any layer; P0-B tests F.Cu only`).
  - `build_csx`: a "curve" port is `fdtd.AddCurvePort(k, 50, start, stop, excite=1 if k == excite else 0)` — openEMS's one-edge lumped port joined to both ends by PEC curves (r3).
  - `readers.curve_edge(lines, start, stop) -> tuple[int, tuple[int, int, int]]`: the axis and start index of the edge openEMS's CurvePort builds (ports.py v0.37.0): the axis is the dominant one of stop − start; ends snapped exactly one cell apart give their own edge; otherwise the line nearest the midpoint along the axis, and the lines nearest the midpoints across it.
  - Worker: the `c_box` of a curve port is `c_box` over its one edge (a box one cell long).

- [ ] **Step 1: Write the failing tests**

```python
def test_a_rotated_part_becomes_a_curve_port_behind_the_switch():  # C-37, spec 5.7
    board, p = project_of("lpf915-45", "U1.1", "J1.1", "--lid-height", "2.5")
    p = {**copy.deepcopy(p), "allow_curve_port": True}
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2)
    l1 = place(next(x for x in e if x.name == "L1"), m, g.zs)
    cx, cy = board.pads("L1.2")[0].center
    assert (l1["kind"], l1["start"][2], l1["stop"][2]) == ("curve", 0.78, 0.78)
    assert l1["start"][:2] == [min(m.x, key=lambda v: abs(v - cx)), min(m.y, key=lambda v: abs(v - cy))]
    assert l1["nodes"] == [l1["start"], l1["stop"]]


def test_build_csx_adds_a_curve_port(monkeypatch):
    log = fake_openems(monkeypatch)
    build_csx({**TINY, "ports": [{**TINY["ports"][0], "kind": "curve"}]}, 1, 1e-9)
    assert ("AddCurvePort", (1, 50, [2.0, 2.0, 0.0], [2.0, 2.0, 1.0]), {"excite": 1}) in log


def test_curve_edge_follows_openems():  # ports.py CurvePort, v0.37.0
    lines = ([0.0, 1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 2.0], [0.0, 1.0])
    assert curve_edge(lines, [0.2, 1.0, 1.0], [3.9, 1.0, 1.0]) == (0, (2, 1, 1))  # the edge at the midpoint
    assert curve_edge(lines, [1.1, 1.0, 1.0], [1.9, 1.0, 1.0]) == (0, (1, 1, 1))  # one cell apart: its own edge


def test_the_c_box_of_a_curve_port_is_its_one_edge(tmp_path, monkeypatch):  # C-18 for a CurvePort
    fake_openems(monkeypatch)
    curve = {"name": "L1", "kind": "curve", "dir": None, "start": [-5.0, 0.0, 0.0], "stop": [-5.0, 0.0, 0.5],
             "nodes": [[-5.0, 0.0, 0.0], [-5.0, 0.0, 0.5]], "part": True}
    job = write_job(tmp_path, {**SMOKE, "ports": [*SMOKE["ports"], curve]}, "setup")  # tests/test_worker.py
    (job / worker.LOG).write_text(SETUP_LOG, encoding="utf-8")
    (job / worker.ERR).write_text("", encoding="utf-8")
    for f in DUMPS.iterdir():
        shutil.copy(f, job)
    monkeypatch.chdir(job)
    assert worker.main(["job.json"]) == 0
    c = json.loads((job / "setup.json").read_text(encoding="utf-8"))["c_box"]["L1"]
    assert c == pytest.approx(1.9037e-14, rel=1e-3)  # the z-edge at (−5, 0, 0.25): one substrate edge
```

- [ ] **Step 2: Run** `python -m pytest tests/test_model_ports.py tests/test_model_csx.py tests/test_readers.py tests/test_worker.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the Interfaces. `port_gates` already handles two roots (Task 16).
- [ ] **Step 4: Run** the full suite, then `python -m pytest -m openems -q`. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: build a CurvePort for a rotated part behind allow_curve_port (P0-B)`

---

## Not in this plan

- **Plan 4:** the co-simulation S = B·A⁻¹ from `waves.npz` cut at `t_cut`; `retune` and `verify`, the §7.3 outputs, the §7.4 indicators and the §7.5 stated limits; reusing results while the model hash holds and refusing a stale retune (§7.8); showing |a(f)| next to each frequency (`excitation` gives f1, f2, t0); S2P parts and scikit-rf; in-grid inductors (`verify`'s LEtype 0 recipe) and the k ≤ 1 check.
- **Plan 5:** the P0 harnesses and the MSLPort/CPWPort coupons; replays of real traces and the live "converged" branch; CI tier (b), which reuses this plan's `@pytest.mark.openems` tests; confirming the provisional numbers (fit2d 3 %, the 0.8 floor, the 3 h reach, +20 dB, the stop presets, the package presets and their Cp, the RAM model); the lid's ±2.8 % snap and the local-refinement offer; flipping `allow_curve_port`'s default after P0-B and making the margin a project field (P0-C criterion 4); the Linux install (P0-D).
- **Deferred SHOULD carries:** normalising rings before the 10 µm simplify, so the hash is independent of the board file's order (M-8); warning about a second shield or a bottom-side shield (M-9); merging into an existing `project.json` in `new` (R38: `new` keeps refusing); a 0 mm copper layer, which zstack accepts and the CSX builds as a degenerate solid (rf:205); `test_no_csxcad_import`, which cannot fail (rf:178); a shunt across two chain nets, untested (plan 2's last note); the cost-loop mutation test (CO-3), lazy CLI imports (L-8) and `MAX_ROUNDS` (L-9).
- **Known limits:** the gate's dt has 6 significant digits; old run folders are never deleted (C-23); the lock is per project, so two projects running at once share the CPU; an unused primitive in a dielectric, a mask or the lid is a warning; port boxes take pads as their bounding boxes; the calibration model is uniform; a reference given by pad name alone takes the first pad of that name; each poll recomputes the stop rule on the whole record; `I_LID` is printed for boards without a shield too.
