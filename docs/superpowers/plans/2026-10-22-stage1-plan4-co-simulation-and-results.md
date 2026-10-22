# Stage 1 · Plan 4 — Co-simulation and results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce a run's waves to the layout N-port and its chain, so that `run` and a new `retune` write the §7.3 outputs with the §7.4 indicators and the §7.5 stated limits, and a new `verify` runs every part in the grid and compares.

**Architecture:**
- `core.post`, a new package of four modules, the only code that imports scikit-rf: `waves` (the grid, S = B·A⁻¹ from a run's waves, the condition guard, |a(f)|, the CurvePort polarity: a `Layout`), `chain` (Z_part per kind, S2P parts, the C_box loads, the termination with scikit-rf's `Circuit`, the ideal schematic by nodal analysis), `checks` (passivity, reciprocity, the loss budget, the comparison measures) and `outputs` (Touchstone, CSV, PNG, the `results/` writer, the stated limits).
- `pipeline.py` gains the output step that `run` and `retune` share (`write_outputs`), `retune`, `verify` and `simulate` (run's job phase, shared with verify); `core.model` learns verify's in-grid inductor (`verify_spec`, an L in `build_csx`); `cli.py` gains thin `retune` and `verify`.
- Tests get a physically consistent fake (`KRS_FAKE=network`, a star of lossy lines whose S is known) and a committed real-openEMS waves fixture.

**Tech Stack:** Python ≥ 3.11, numpy ≥ 2, scipy (`signal.find_peaks`, `constants`), scikit-rf ≥ 2.2 (`Circuit`, Touchstone 1.1), matplotlib (a `Figure` drawn by the Agg canvas), stdlib `csv`/`io`/`json`/`os`/`re`/`shlex`/`subprocess`; openEMS 0.37.0 and CSXCAD 0.7.0 in workers only; pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`. This plan covers §7 (7.1–7.6 and 7.8; 7.7 stays deferred), the `retune` and `verify` rows of §3.2 and `run`'s "writes the outputs of §7.3", §5.8's |a(f)| diagnostics, §8's missing-S2P error and every refusal plan 4's commands imply (§8's last rule), and the plan-4 parts of §9.1: tier (a)'s co-sim reduction, the synthetic S2P files built from ideal RLC, and the openems-marked tests of verify's elements.

**Stage 1 is split into five plans.** Each one ends in working, tested software:
1. Foundation and board import.
2. Geometry, mesh and the mesh gates, including the 2D Z0/εeff readout of `cost`.
3. Model, worker and run control: `cost`, `run`, `preview`, `calibrate` and `setup-openems`.
4. Co-simulation and results: `retune`, `verify`, the outputs and the validity indicators (this plan).
5. Validation gates P0-A to P0-D, the KiCad button pre-check and the reports.

**Branch:** work on `stage1-plan4`, from `main`. Commands assume the dev venv is active.

## Global Constraints

- **Python and files:** Python ≥ 3.11 (CI floor); every new `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`; English.
- **Dependencies:** runtime becomes `["shapely>=2.0", "numpy>=2", "scipy", "h5py", "matplotlib", "scikit-rf>=2.2"]` (numpy 2 for `.mT`; scikit-rf 2.2.0 is tested on Python 3.14.2 with numpy 2.5.4 and pulls pandas, accepted by spec §3.4). Install into the dev `.venv` with `python -m pip install -e .[dev]`, never into a global Python or an ESP-IDF environment. openEMS and CSXCAD stay undeclared.
- **scikit-rf 2.x API:** `from skrf.circuit import Circuit` and `rf.network.connect` (there is no `rf.Circuit` or `rf.connect`); read a user's file with `n = rf.Network(); n.read_touchstone(path)`, never `rf.Network(path)`, which unpickles; frequencies through `rf.Frequency.from_f(f, unit="Hz")`; every Network gets a `name` (`Circuit` and `write_touchstone` refuse an unnamed one).
- **Imports:** only `core.post` imports skrf, at the top of its modules; matplotlib is imported inside `outputs.summary_png` only, on a `matplotlib.figure.Figure`, never a pyplot figure (Stage 2 brings Qt, which the core never imports); `core.post` takes `from kicad_rf_studio.core.model.parts import Z0`, never the module as `parts` (that name is `project.parts`); the worker never imports `core.post`, skrf, pandas or matplotlib (`tests/test_worker.py` pins it).
- **Reference impedance:** `Z0` = 50 Ω at every port, external and part, in the waves, S, Γ and every Touchstone file; no renormalisation (C-7).
- **|a(f)| (C-12):** `level_db` (Task 1) is shown next to every reported frequency: the marker, indicator and null lines and the CSV's `a_db`; no warning code.
- **Outputs (C-27..C-32):** in `<project dir>/results/`: `layout.s{N}p`, `chain.s{P}p` (M > 0), `summary.png`, `summary.csv`, and `verify.s{P}p` from `verify`; Touchstone 1.1 as scikit-rf writes it (`# Hz S RI R 50.0`), ASCII only; the CSV comma-separated, "." decimal, UTF-8 with ASCII content, numbers as Python's repr; the nine stated limits after every result of `run`, `retune` and `verify`.
- **Exit codes:** only 0, 1, 2, 3, 4 and 130. `retune`: 0, 2 for a refusal, 1 internal; `run`: plan 3's, plus 2 when the output step refuses after the results are saved (C-26); `verify`: as `run`. The validity indicators (σ_max 1.02, reciprocity 0.02, loss budget 0.02; C-35) are flags, never gates: they change no exit code.
- **Messages:** every user-visible string, the PNG's words too, is a code in the one CATALOG of `core.messages`, with plain `{fields}` and pre-formatted numbers, and says what to do next; an advice that holds only for some parts says for which ("or, for a C, L or R, …"); math notation stays literal; CSV column names and Touchstone comments are English data, not codes; tests check `KrsError.code` and `.params` (or the rendered line), never `match=`; no field is named `code`; the existing `E_OUTPUT_PATH` is not reused for `results/`.
- **Units and frames:** mm, Hz, s, F, H, Ω; `project.json` in KiCad's frame (y down); the model spec in the internal frame.
- **Spec amendments the owner confirmed on 2026-10-22** (committed to the spec beside this plan; the spec's §7.2, §7.6, §7.8, §9.1, §11.9 and §12 now read so):
  - the termination oracle agrees to 1e-12, not §7.2's "2e-16" (measured 1e-15 to 6e-15; C-6);
  - a run replaces `results` and `results/` only when every job kept S; a run whose jobs do not all keep S leaves both as they were (C-24);
  - verify puts a capacitor in the grid as C_part + C_box, not C_part: a grid C replaces the box's own capacitance (C-36);
  - verify's inductor limit is k ≤ K_MAX = 0.45, not §7.6's k ≤ 1: runs diverged from k ≥ 0.49 (C-37);
  - §7.6 and §11.9: openEMS 0.37 never enlarges an inductor cell's capacitance; without an explicit C its Z_FACT rule lowers it (to zero in 4 of 22 custom-pulse runs), which is why every in-grid L gets one (r3 §3.5);
  - §9.1's synthetic S2P files built from ideal RLC are generated inside the tests, in `tmp_path`, and never committed; `.gitignore` does not change (C-41).
- **Workflow:** every implementer runs `graphify query "<question>"` (or `explain`/`path`) from the repo root before reading code; synthetic boards and fixtures only; no private names, absolute user paths, e-mail addresses, or a drive letter followed by a colon and a slash or backslash in any committed file, this plan included (the privacy gate's generic rules); commits carry no co-author line.
- **Tests:** tier (a) runs without openEMS, on fakes and committed samples; tests needing openEMS carry `@pytest.mark.openems`; tests patch module attributes (`os.replace`, `os.remove`, `subprocess.Popen`, `runs.*`, `spec.c_box`), so code calls them through their modules.

## Review Focus

1. **A spreadsheet holds `results/summary.csv` open while `retune` rewrites it** (Windows refuses to replace or delete a file another program holds): `E_RESULTS_WRITE` names the file and the command to rerun, assignments included; the summaries are replaced first, so `results/` and `project.json` stay as they were. Tests: `test_a_file_another_program_holds_is_a_coded_refusal` (Task 7), `test_a_csv_held_open_refuses_and_stores_nothing` (Task 10).
2. **A vendor S2P named by the part's place on the board instead of the vendor's fixture** (a series-thru file given `:shunt` because C2 sits in shunt): Z_part is then off by a factor of up to 2.4e5, silently; `W_S2P_FIXTURE` says which fixture the file fits. Test: `test_an_s2p_named_by_the_parts_place_is_warned` (Task 3).
3. **A vendor S2P measured over a narrower band than f1–f2** (many start at 1 GHz while f1 = f0/2): `E_S2P_BAND` names both bands; the run keeps its results, writes `layout.s{N}p`, prints the limits and exits 2. Test: `test_a_narrow_band_s2p_leaves_the_layout_n_port` (Task 9).
4. **An S2P path typed the Windows way, with a drive letter, spaces and accents, next to a decimal-comma value:** the drive's colon survives `rsplit`, the path is stored relative to `project.json`, the value verbatim, and the Touchstone header stays ASCII. Test: `test_a_windows_path_with_spaces_and_accents` (Task 10).
5. **The run folder deleted** (users clean `%LOCALAPPDATA%`): `retune` refuses with `E_RESULTS_WAVES` naming the missing file and writes nothing. Test: `test_a_deleted_run_folder_refuses_the_retune` (Task 10).

---

## File structure

```
pyproject.toml                                  # + numpy>=2, scikit-rf>=2.2
tools/make_waves.py                             # dev-time: the real-data waves fixture (starts the worker; imports no openEMS)
tests/fixtures/microstrip/{job-1.npz,job-2.npz,meta.json}
src/kicad_rf_studio/core/post/__init__.py       # docstring only
src/kicad_rf_studio/core/post/waves.py          # grid, S from the waves, κ_eq, |a(f)|, polarity: Layout
src/kicad_rf_studio/core/post/chain.py          # Z_part, S2P, C_box loads, the termination, the ideal schematic
src/kicad_rf_studio/core/post/checks.py         # passivity, reciprocity, loss budget, comparison measures
src/kicad_rf_studio/core/post/outputs.py        # Touchstone, CSV, PNG, the results/ writer, LIMITS
src/kicad_rf_studio/core/project.py             # parts(), the s2p key, relative_path, shown_reference
src/kicad_rf_studio/core/kicad/values.py        # port_value: a C of 0 is no value
src/kicad_rf_studio/core/model/parts.py         # project_parts writes s2p null; the presets' comment says plan 5
src/kicad_rf_studio/core/model/spec.py          # K_MAX, verify_spec
src/kicad_rf_studio/core/model/csx.py           # an L grid element
src/kicad_rf_studio/core/messages.py            # + codes; reason(error, fallback)
src/kicad_rf_studio/pipeline.py                 # expected_loss, command_line, gate_lines, write_outputs, results_of,
                                                #   assign, retune, simulate, verify; build_model uses parts()
src/kicad_rf_studio/cli.py                      # retune, verify; relative_path and shown_reference moved out
tests/networks.py tests/fake_worker.py tests/test_post_{waves,chain,checks,outputs,real}.py tests/test_retune.py
tests/test_verify.py (and revisions in test_run.py, test_cli_new.py, test_project.py, test_model_spec.py,
test_model_csx.py, test_worker.py)
```

## Decisions this plan fixes

| Decision | Task |
|---|---|
| A part's `s2p` key: null, or {"file", "connection": "series" or "shunt"}; a C of 0 is no value | 3 |
| `results` gains `preset` and `loss_expected`; it is replaced only when every job kept S | 6 |
| The files of `results/`, the Touchstone port map, the CSV columns, the writer's order | 7 |
| `KRS_FAKE=network` | 8 |
| `run`'s output step and its exit code 2 | 9 |
| `retune`'s syntax, storage, refusals and exit codes | 10 |
| verify's model spec: grid entries with an "L" key, the one-cell box, PEC strips | 11 |
| `project.json`'s `verify` key, verify's exit codes | 12 |
| The real-data fixture | 13 |

**Confirmed by the owner (2026-10-22):** the six spec amendments of Global Constraints.

---

### Task 1: scikit-rf, the co-simulation grid and S from the waves

**Files:**
- Create: `src/kicad_rf_studio/core/post/__init__.py` (docstring: "Co-simulation and results (spec 7): S from a run's waves (waves), the parts and the chain (chain), the validity indicators and comparisons (checks), the files of results/ (outputs). Only this package imports scikit-rf; the worker never imports it."), `src/kicad_rf_studio/core/post/waves.py`, `tests/networks.py`, `tests/test_post_waves.py`
- Modify: `pyproject.toml`, `src/kicad_rf_studio/core/messages.py`, `tests/test_worker.py`

**Interfaces:**
- Consumes: `parts.Z0`.
- Produces:
  - `waves.N_GRID = 400`, `waves.KAPPA_LIMIT = 10.0`.
  - `grid(f0: float, harmonics: int, band_factor: float) -> tuple[np.ndarray, int]` (C-11): (f, q) with f = f0·m/q for m = q//2 … floor(band_factor·harmonics·q·(1 + 1e-12)), q = 2·round(N_GRID/(2·(band_factor·harmonics − 0.5))); n·f0 sits exactly at index n·q − q//2 (915 MHz, 3 harmonics, ×1.1: 398 points, f0, 2f0, 3f0 at 71, 213, 355). The stop rule keeps its own 101 points.
  - `s_matrix(records: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]], f: np.ndarray) -> tuple[np.ndarray, np.ndarray]` (spec 7.1, C-8): (S, A), each (F, N, N), from N jobs' records (t_u, u, t_i, i), u and i of shape (N, n_j) already cut, job j exciting port j: the direct DFT Σ x·exp(−j2πf·t) of u on t_u and of i on t_i (no window, no Δt, no division by E(f): they cancel); a = (U + Z0·I)/(2√Z0), b = (U − Z0·I)/(2√Z0); S = B·A⁻¹ as solve(Aᵀ, Bᵀ)ᵀ, never the diagonal b/a. Raises `E_S_SINGULAR {kappa, f_mhz}` (C-9).
  - `kappa_eq(a: np.ndarray) -> np.ndarray` (F,): the 2-norm condition number of A after scaling each column to unit norm (a zero column stays zero).
  - `level_db(a: np.ndarray) -> np.ndarray` (F,): min over j of 20·log10(|A_jj(f)|/max over f of |A_jj|).
  - `tests/networks.py`: `Z0 = 50.0`, `C_BOX = 2e-14`, `star(f, n, a=0.95, tau=0.2e-9)`, `synth_records(s_of, n, f1, f2, dt, t_rec, smooth=False)`.

- [ ] **Step 1: Add scikit-rf and install it.** `pyproject.toml`: `dependencies = ["shapely>=2.0", "numpy>=2", "scipy", "h5py", "matplotlib", "scikit-rf>=2.2"]`. Then, in the dev `.venv`: `python -m pip install -e .[dev]`. Expected: `python -c "import skrf; from skrf.circuit import Circuit; print(skrf.__version__)"` prints `2.2.0` or later.

- [ ] **Step 2: Write the test helper and the failing tests.** `tests/networks.py` (r6's generator, the oracle of every co-simulation test):

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""Known networks and the waves openEMS would record from them (r6-math), for the co-simulation tests and the
KRS_FAKE=network fake: S = B·A⁻¹ must give back the network the waves came from."""
import numpy as np

Z0, C_BOX = 50.0, 2e-14  # Ω at every port; F, the fake worker's C_box of a part port


def star(f, n, a=0.95, tau=0.2e-9):
    """The S (F, n, n) of n 50 Ω lines of amplitude a and delay tau joined at one node: passive (σ_max = a²),
    reciprocal and causal."""
    g = a * np.exp(-2j * np.pi * np.asarray(f, float) * tau)
    return (g ** 2)[:, None, None] * (2 / n * np.ones((n, n)) - np.eye(n))


def synth_records(s_of, n, f1, f2, dt, t_rec, smooth=False):
    """[(t_u, u, t_i, i)] of n jobs on the n-port s_of(f) (reference Z0), every port closed by Z0 ∥ C_BOX as an
    openEMS lumped port is, job j driving port j through it with spec 5.8's pulse (smooth: one with no exp(−9)
    steps): u at openEMS's probe instants k·Δ, Δ = (floor(1/(2·f2·dt)) // 4)·dt, i at k·Δ + dt/2, k·Δ < t_rec.
    Band-limited exact samples, synthesised on an FFT grid 8 times longer than the record (r6 §2)."""
    fm, fw = (f1 + f2) / 2, (f2 - f1) / 2
    t0 = 9 / (2 * np.pi * fw)
    if smooth:
        e = lambda t: np.sin(2 * np.pi * fm * (t - 2 * t0)) * np.exp(-(2 * np.pi * fw * (t - t0) / 3 - 3) ** 2)
    else:
        e = lambda t: np.sin(2 * np.pi * fm * (t - t0)) * np.exp(-(2 * np.pi * fw * t / 3 - 3) ** 2) * (t < 2 * t0)
    step = (int(np.floor(1 / (2 * f2 * dt))) // 4) * dt
    k = int(t_rec / step)
    m = 8 * k | 1  # odd: irfft keeps every bin
    fb = np.fft.rfftfreq(m, step)
    fb[0] = fb[1] * 1e-6
    E = np.fft.rfft(e(np.arange(m) * step))
    zt = Z0 / (1 + 2j * np.pi * fb * C_BOX * Z0)
    g = ((zt - Z0) / (zt + Z0))[:, None, None]
    S = s_of(fb)
    a = np.linalg.solve(np.eye(n) - g * S, np.eye(n) * (np.sqrt(Z0) / (Z0 + zt))[:, None, None])
    b = S @ a
    V, I = np.sqrt(Z0) * (a + b), (a - b) / np.sqrt(Z0)
    shift = np.exp(2j * np.pi * fb * dt / 2)[:, None, None]
    u, i = (np.fft.irfft(X * E[:, None, None], m, axis=0)[:k] for X in (V, I * shift))
    t_u = np.arange(k) * step
    return [(t_u, u[:, :, j].T.copy(), t_u + dt / 2, i[:, :, j].T.copy()) for j in range(n)]
```

  `tests/test_post_waves.py`:

```python
F0, F1, F2 = 915e6, 457.5e6, 3.0195e9
DT = 1.73972e-13  # the dumps model's dt (tests/test_readers.py)
F, Q = grid(F0, 3, 1.1)


def test_the_grid_puts_f0_and_its_harmonics_on_exact_points():  # C-11
    assert (len(F), Q, F[0]) == (398, 142, F1)
    assert (F[71], F[213], F[355]) == (F0, 2 * F0, 3 * F0)  # bit-exact
    assert F[-1] <= F2 and np.allclose(np.diff(F), F0 / Q, rtol=1e-12, atol=0)


@pytest.mark.parametrize("n", [2, 3, 6])
def test_s_is_the_network_the_waves_came_from(n):  # spec 7.1, C-8; r6 §12: ≤ 1e-5, ≤ 1e-13 smooth
    S, A = s_matrix(synth_records(lambda f: star(f, n), n, F1, F2, DT, 10e-9), F)
    assert np.abs(S - star(F, n)).max() <= 1e-5 and kappa_eq(A).max() <= 1.02
    smooth = s_matrix(synth_records(lambda f: star(f, n), n, F1, F2, DT, 15e-9, smooth=True), F)[0]
    assert np.abs(smooth - star(F, n)).max() <= 1e-13


def test_job_scale_and_order_cancel_and_the_half_step_counts():  # C-8
    rec = synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)
    S = s_matrix(rec, F)[0]
    scaled = [(t, u * k, ti, i * k) for (t, u, ti, i), k in zip(rec, (0.1, 3.0, 10.0))]
    assert np.abs(s_matrix(scaled, F)[0] - S).max() <= 1e-13
    assert np.abs(s_matrix(rec[::-1], F)[0] - S).max() == 0
    cut = [(t[:n], u[:, :n], ti[:n], i[:, :n]) for (t, u, ti, i), n in zip(rec, (120, 200, 242))]
    assert np.abs(s_matrix(cut, F)[0] - star(F, 3)).max() <= 1e-5  # jobs of different lengths
    no_half_step = [(t, u, t, i) for t, u, _, i in rec]
    assert np.abs(s_matrix(no_half_step, F)[0] - star(F, 3)).max() > 1e-4


def test_the_excitation_level_is_the_pulse_spectrum():  # spec 5.8, C-12
    _, A = s_matrix(synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9), F)
    assert level_db(A)[[0, 71, 213, 355]] == pytest.approx([-19.65, -8.08, -0.10, -12.06], abs=0.05)


@pytest.mark.parametrize("bad", ["dead", "duplicated"])
def test_a_dead_or_duplicated_job_is_a_coded_refusal_without_a_warning(bad):  # C-9
    rec = synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)
    t, u, ti, i = rec[1]
    rec[1] = (t, 0 * u, ti, 0 * i) if bad == "dead" else rec[0]
    with warnings.catch_warnings(), pytest.raises(KrsError) as e:
        warnings.simplefilter("error")
        s_matrix(rec, F)
    assert (e.value.code, e.value.params["f_mhz"]) == ("E_S_SINGULAR", "457.5")
```

  Test imports: `json`, `shutil`, `warnings`, `Path`, `numpy as np`, `pytest`; `KrsError`; `grid`, `kappa_eq`, `level_db`, `s_matrix` (Task 2 adds `flipped`, `layout`) from `kicad_rf_studio.core.post.waves`; `from networks import star, synth_records` (Task 2 adds `terminate_np`).

  Revise on purpose: `tests/test_worker.py::test_the_worker_imports_no_geometry_stack` checks the tuple `('shapely', 'scipy', 'matplotlib', 'skrf', 'pandas', 'openEMS', 'CSXCAD', 'kicad_rf_studio.core.post')` (C-5).
- [ ] **Step 3: Run** `python -m pytest tests/test_post_waves.py tests/test_worker.py -q`. Expected: FAIL (`kicad_rf_studio.core.post` missing).
- [ ] **Step 4: Implement** `waves.py` and the message. `s_matrix`: one kernel exp(−j2π·outer(t, f)) for the voltages on t_u and one for the currents on t_i, built once on the record with the most samples and sliced to each job's n_j (every job samples the same instants from t = 0); `U[:, :, j] = (u_j @ Ku[:n_j]).T`, `I` likewise, giving (F, port, job); at the first f where not κ_eq ≤ KAPPA_LIMIT (NaN included) raise `E_S_SINGULAR {kappa: f"{κ:.3g}", f_mhz: f"{f/1e6:.1f}"}`, before any solve and with no numpy warning; then `S = np.linalg.solve(A.mT, B.mT).mT`.
  `# ponytail: one DFT kernel on the longest job's times; jobs sampled at other instants would each need their own`
  - `E_S_SINGULAR`: "The run's excitations are not independent at {f_mhz} MHz (condition number {kappa}, limit 10), so S cannot be computed: a job's waves are dead or duplicated. Run `run` again."
- [ ] **Step 5: Run** the two test files. Expected: PASS.
- [ ] **Step 6: Commit.** `feat: add scikit-rf and compute S = B·A⁻¹ from the waves on the co-simulation grid (spec 7.1)`

---

### Task 2: The layout N-port of a run

**Files:**
- Modify: `src/kicad_rf_studio/core/post/waves.py`, `src/kicad_rf_studio/core/messages.py`, `tests/networks.py`
- Test: `tests/test_post_waves.py`

**Interfaces:**
- Consumes: `grid`, `s_matrix`, `level_db` (Task 1); `stoprule.KEPT`; plan 3's `results` and run folder (`model.json`, `job-k-<name>/waves.npz`).
- Produces:
  - `@dataclass(frozen=True) class Layout`: `f: np.ndarray` (the grid), `markers: list[int]` (the grid indices of f0, 2f0, … up to the harmonics shown, those on the grid), `s: np.ndarray` (F, N, N, ports in job order, every port V_signal − V_reference), `a_db: np.ndarray` (F,), `ports: list[dict]` (model.json's port entries), `flipped: list[bool]`.
  - `flipped(port: dict) -> bool`: True for a CurvePort (`kind` "curve") whose start, its reference end, lies higher than its stop along the axis of the largest |stop − start| component: openEMS orders a CurvePort's ends along that axis, so it measured V_reference − V_signal (ports.py v0.37.0). A lumped port is never flipped: openEMS keeps a lumped box's given order (Task 13's openems test checks it on a reversed box).
  - `layout(project: dict, results: dict) -> Layout`: the grid from project's f0_hz, harmonics and band_factor; `results` holds `run_dir` and `jobs` (project.json's results, or verify's own). Refusals, in this order: `E_RESULTS_JOB {port, verdict}` for a job whose verdict is not in KEPT; `E_RESULTS_WAVES {path}` for a missing `run_dir/model.json`, then for each job's missing `run_dir/<waves>` (run_dir itself when `waves` is None). Each job is cut at searchsorted(t_u, t_cut, "right") for u and i alike, the whole record when t_cut is None (t_max); S from `s_matrix`, then D·S·D with D = −1 at each flipped port (C-10).
  - `tests/networks.py`: `terminate_np(s, ext, zk)`.

- [ ] **Step 1: Write the failing tests.** `tests/networks.py` gains the termination oracle (spec 7.2):

```python
def terminate_np(s, ext, zk):
    """S' = S_ee + S_ei·Γ·(I − S_ii·Γ)⁻¹·S_ie, Γ_k = (Z_k − Z0)/(Z_k + Z0) for the ports not in ext (index order),
    zk (F, M): the numpy oracle of the termination."""
    i = [k for k in range(s.shape[-1]) if k not in ext]
    g = (zk - Z0) / (zk + Z0)
    see, sei, sie, sii = (s[:, r][:, :, c] for r, c in ((ext, ext), (ext, i), (i, ext), (i, i)))
    return see + (sei * g[:, None, :]) @ np.linalg.solve(np.eye(len(i)) - sii * g[:, None, :], sie)
```

  `tests/test_post_waves.py`:

```python
P915 = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1}


def port(name, part=False):
    return {"name": name, "kind": "lumped", "dir": "x", "start": [0.0, 0.0, 0.0], "stop": [1.0, 0.0, 0.0],
            "nodes": [], "part": part}


def fake_run(tmp_path, rec, ports, t_cut=None):
    """A run folder with model.json (`ports`) and one waves.npz per job of `rec`, and its results."""
    run = tmp_path / "run"
    run.mkdir()
    (run / "model.json").write_text(json.dumps({"ports": ports}), encoding="utf-8")
    jobs = []
    for k, ((t_u, u, t_i, i), q) in enumerate(zip(rec, ports), 1):
        (run / f"job-{k}").mkdir()
        np.savez(run / f"job-{k}" / "waves.npz", t_u=t_u, u=u, t_i=t_i, i=i)
        jobs.append({"port": q["name"], "verdict": "converged", "t_cut": t_cut, "t_stop": float(t_u[-1]),
                     "residual_db": -61.0, "waves": f"job-{k}/waves.npz"})
    return {"run_dir": str(run), "jobs": jobs}


def test_the_layout_is_reduced_from_the_run_folder(tmp_path):  # spec 7.1, 6.3, C-8
    rec = synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)
    t, u, ti, i = rec[0]
    late = 1e-2 * np.sin(2 * np.pi * 1e9 * t) * (t > 5e-9)  # after t_cut: a reduction that ignores the cut fails
    rec[0] = (t, u + late, ti, i + late / 50)
    lay = layout(P915, fake_run(tmp_path, rec, [port("P1"), port("P2"), port("C1", True)], t_cut=4e-9))
    assert (lay.markers, lay.flipped, [q["name"] for q in lay.ports]) == ([71, 213, 355], [False] * 3,
                                                                          ["P1", "P2", "C1"])
    assert np.array_equal(lay.f, F) and np.abs(lay.s - star(F, 3)).max() <= 1e-5
    assert lay.a_db[71] == pytest.approx(-8.08, abs=0.05)


def test_a_reversed_curve_port_is_normalised_and_the_chain_does_not_change(tmp_path):  # C-10, X-7
    flip = np.array([[1.0], [1.0], [-1.0]])
    rec = [(t, u * flip, ti, i * flip) for t, u, ti, i in synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9)]
    curve = {"name": "L1", "kind": "curve", "dir": None, "start": [2.0, 5.0, 0.78], "stop": [2.0, 4.0, 0.78],
             "nodes": [], "part": True}
    lay = layout(P915, fake_run(tmp_path, rec, [port("P1"), port("P2"), curve]))
    assert lay.flipped == [False, False, True] and np.abs(lay.s - star(F, 3)).max() <= 1e-5
    zk = np.full((len(F), 1), 30 + 20j)
    raw = s_matrix(rec, F)[0]
    assert np.abs(terminate_np(lay.s, [0, 1], zk) - terminate_np(raw, [0, 1], zk)).max() <= 1e-12
    assert not flipped({**curve, "start": [2.0, 4.0, 0.78], "stop": [2.0, 5.0, 0.78]}) and not flipped(port("P1"))


@pytest.mark.parametrize("what", ["verdict", "waves", "folder"])
def test_results_that_cannot_be_reduced_name_the_fix(tmp_path, what):  # C-22, X-5, P-8
    results = fake_run(tmp_path, synth_records(lambda f: star(f, 2), 2, F1, F2, DT, 10e-9), [port("P1"), port("P2")])
    run = Path(results["run_dir"])
    if what == "verdict":
        results["jobs"][1]["verdict"] = "diverged"
        expected = ("E_RESULTS_JOB", {"port": "P2", "verdict": "diverged"})
    elif what == "waves":
        (run / "job-2" / "waves.npz").unlink()
        expected = ("E_RESULTS_WAVES", {"path": str(run / "job-2" / "waves.npz")})
    else:
        shutil.rmtree(run)
        expected = ("E_RESULTS_WAVES", {"path": str(run / "model.json")})
    with pytest.raises(KrsError) as e:
        layout(P915, results)
    assert (e.value.code, e.value.params) == expected
```
- [ ] **Step 2: Run** `python -m pytest tests/test_post_waves.py -q`. Expected: the new tests FAIL (`layout` missing).
- [ ] **Step 3: Implement** `Layout`, `flipped` and `layout` as the Interfaces fix them. Messages:
  - `E_RESULTS_JOB`: "The last run's job {port} ended {verdict}, so its S was not kept and the layout cannot be reduced. Run `run` again."
  - `E_RESULTS_WAVES`: "{path} is missing: the last run's folder was moved or deleted. Run `run` again."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: reduce a run's waves to the layout N-port, with the CurvePort polarity normalised`

---

### Task 3: Part models and S2P parts

**Files:**
- Create: `src/kicad_rf_studio/core/post/chain.py`, `tests/test_post_chain.py`
- Modify: `src/kicad_rf_studio/core/project.py`, `src/kicad_rf_studio/core/kicad/values.py`, `src/kicad_rf_studio/core/model/parts.py`, `src/kicad_rf_studio/pipeline.py` (`build_model` uses `parts()`), `src/kicad_rf_studio/core/messages.py`, `tests/networks.py`, `tests/test_project.py`, `tests/test_cli_new.py`

**Interfaces:**
- Consumes: `part_kind`, `part_value`; `Z0`; `grid` (Task 1).
- Produces:
  - `project.parts(data: dict) -> dict[str, dict]`: project.json's parts by ref, chain.series, chain.shunt then others — the dicts held in `data`, not copies (tests edit through it); `pipeline.build_model` uses it in place of its own dict.
  - Every part gains the required key `s2p`: None, or `{"file": text, "connection": "series" | "shunt"}` (C-18). `project_parts` writes None; `_PARTS` checks it with the text "null, or file (text) and connection (series or shunt)"; `SCHEMA` stays 1, so an older project gets `E_PROJECT_FIELD` naming the key.
  - `values.port_value(ref: str, text: str) -> float | None`: `part_value`, but None for a C of 0 (an open: its infinite impedance would make every output NaN).
  - `parts.py:15` reads `# ponytail: typical published magnitudes, provisional; plan 5 (P0) confirms them` (C-13).
  - `chain.z_part(kind: str, value: float, model: dict | None, f: np.ndarray) -> np.ndarray` (C-13, spec 5.7), with the preset's (esl_h, esr_ohm, cp_f), all 0 for None: C: ESR + jωESL + 1/(jωC); L: (ESR + jωL) ∥ 1/(jωCp); R: (R + jωESL) ∥ 1/(jωCp); each ∥ as zs/(1 + jωCp·zs), finite at zs = 0.
  - `chain.s2p_impedance(file: Path, connection: str, ref: str, f: np.ndarray) -> tuple[np.ndarray, str | None]` (C-14): Z_part on the grid — series-thru 2·Z0·(1 − S21)/S21, shunt-thru Z0·S21/(2·(1 − S21)), with S21 := (S21 + S12)/2 interpolated by `np.interp` on its real and imaginary parts onto f (never Z, never extrapolated), Z0 the file's R, noise data ignored — and the other connection when the file's own points from f[0] to f[-1] fit its identity better (series: max|S11 + S21 − 1|, shunt: max|S21 − S11 − 1|), else None. Refusals with `{ref, path: str(file)}`: `E_S2P_MISSING` (no file), `E_S2P_UNREADABLE` (any reader error, or no data), `E_S2P_PORTS` (+ `ports`), `E_S2P_BAND` (+ `f_lo`, `f_hi`, `f1`, `f2`, MHz `:.1f`; the file must span f[0] … f[-1]).
  - `chain.part_impedances(project: dict, folder: Path, refs: list[str], f: np.ndarray) -> tuple[dict[str, np.ndarray], list[tuple[str, dict]]]`: Z_part of each ref — its `s2p` file read at `(folder / file).resolve()` (folder: project.json's) when set, else `z_part(part_kind(ref), port_value(ref, value), model, f)` — and a `W_S2P_FIXTURE {ref, path, named, fits}` note for each file that fits the other fixture. Raises `E_PART_NO_VALUE {ref, value}` (C-15) and `s2p_impedance`'s refusals.
  - `tests/networks.py`: `write_s2p(path, z, connection, f, z0=50.0) -> Path` and `read_s(path) -> np.ndarray`, both importing skrf inside the function (the fake worker imports this module).

- [ ] **Step 1: Write the failing tests.** `tests/networks.py` gains:

```python
def write_s2p(path, z, connection, f, z0=50.0):
    """A Touchstone 2-port at `path` (a .s2p name) of the impedance z (one per f, Hz) measured in a series or shunt
    fixture of z0 Ω (spec 9.1's synthetic S2P files from ideal RLC)."""
    import skrf as rf

    s21 = 2 * z0 / (2 * z0 + z) if connection == "series" else 2 * z / (2 * z + z0)
    s11 = z / (2 * z0 + z) if connection == "series" else -z0 / (2 * z + z0)
    s = np.stack([np.stack([s11, s21], -1), np.stack([s21, s11], -1)], -2)
    rf.Network(frequency=rf.Frequency.from_f(f, unit="Hz"), s=s, z0=z0, name="part").write_touchstone(
        str(path.with_suffix("")))
    return path


def read_s(path):
    """The S of a Touchstone file, read the safe way."""
    import skrf as rf

    n = rf.Network()
    n.read_touchstone(str(path))
    return n.s
```

  `tests/test_post_chain.py`:

```python
F0 = 915e6
F, _ = grid(F0, 3, 1.1)
M0402 = model_of("0402")  # {"package": "0402", "esl_h": 5e-10, "esr_ohm": 0.1, "cp_f": 3e-14}
LPF = (("C1", "C", 100e-12), ("L1", "L", 15e-9), ("C2", "C", 3.3e-12), ("C3", "C", 3.3e-12))  # lpf915's part ports
FB1 = {"ref": "FB1", "pads": ["FB1.1", "FB1.2"], "nets": ["RF_C", "RF_OUT"], "value": "x", "dnp": False,
       "role": "port", "model": None, "s2p": None}  # a ferrite bead: no kind, so no ideal value (M-5)


def lpf():
    return copy.deepcopy(project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")[1])  # tests/test_gates.py


def test_the_part_models_follow_the_presets():  # C-13, spec 5.7; r6 §4
    f = F[[71, 213, 355]]
    assert z_part("C", 100e-12, M0402, f) == pytest.approx([0.1 + 1.135j, 0.1 + 4.879j, 0.1 + 8.044j], abs=1e-3)
    assert z_part("C", 3.3e-12, M0402, f) == pytest.approx([0.1 - 49.834j, 0.1 - 20.605j, 0.1 - 8.946j], abs=1e-3)
    assert z_part("L", 15e-9, M0402, f) == pytest.approx([0.103 + 87.539j, 0.113 + 183.384j, 0.133 + 298.694j],
                                                          abs=1e-3)
    assert z_part("R", 0.0, M0402, f[:1]) == pytest.approx([2.876j], abs=1e-3)  # a 0R made a port
    assert z_part("L", 15e-9, None, f) == pytest.approx(2j * np.pi * f * 15e-9, rel=1e-15)  # no preset: ideal
    w = 2 * np.pi * F
    assert z_part("L", 1e-6, M0402, F) == pytest.approx(1 / (1 / (0.1 + 1j * w * 1e-6) + 1j * w * 3e-14), rel=1e-12)
    srf_c = srf("C", 100e-12, M0402)
    assert abs(z_part("C", 100e-12, M0402, np.array([srf_c]))[0].imag) < 1e-9  # parts.srf's resonance


@pytest.mark.parametrize(("kind", "value", "connection", "z0"), [
    ("C", 3.3e-12, "series", 50.0), ("C", 3.3e-12, "shunt", 50.0), ("L", 15e-9, "series", 75.0),
    ("L", 15e-9, "shunt", 50.0), ("C", 100e-12, "series", 50.0)])
def test_an_s2p_gives_back_the_impedance_it_was_built_from(tmp_path, kind, value, connection, z0):  # C-14
    z = z_part(kind, value, None, F)
    got, fits = s2p_impedance(write_s2p(tmp_path / "part.s2p", z, connection, F, z0), connection, "C9", F)
    assert np.abs(got / z - 1).max() <= 1e-12 and fits is None


def test_an_s2p_takes_the_mean_of_s21_and_s12(tmp_path):  # C-14
    import skrf as rf

    n = rf.Network()
    n.read_touchstone(str(write_s2p(tmp_path / "l.s2p", z_part("L", 15e-9, None, F), "series", F)))
    s = n.s.copy()
    s[:, 0, 1] *= 1.01
    n.s = s
    n.write_touchstone(str(tmp_path / "skew"))
    m = (s[:, 1, 0] + s[:, 0, 1]) / 2
    assert s2p_impedance(tmp_path / "skew.s2p", "series", "L1", F)[0] == pytest.approx(100 * (1 - m) / m, rel=1e-12)


@pytest.mark.parametrize(("name", "text", "code"), [
    ("gone.s2p", None, "E_S2P_MISSING"), ("bad.s2p", "hello\n", "E_S2P_UNREADABLE"),
    ("empty.s2p", "# Hz S RI R 50\n", "E_S2P_UNREADABLE"),
    ("one.s1p", "# Hz S RI R 50\n1e8 0.5 0\n4e9 0.5 0\n", "E_S2P_PORTS")])
def test_an_s2p_that_cannot_serve_is_refused_by_name(tmp_path, name, text, code):  # spec 8, C-14
    file = tmp_path / name
    if text:
        file.write_text(text, encoding="ascii")
    with pytest.raises(KrsError) as e:
        s2p_impedance(file, "series", "C1", F)
    named = {"ref": "C1", "path": str(file)}
    assert (e.value.code, e.value.params) == (code, {**named, "ports": 1} if code == "E_S2P_PORTS" else named)


def test_an_s2p_that_misses_the_band_is_never_extrapolated(tmp_path):  # C-14
    f = np.linspace(1e9, 3e9, 21)
    file = write_s2p(tmp_path / "c.s2p", z_part("C", 3.3e-12, None, f), "series", f)
    with pytest.raises(KrsError) as e:
        s2p_impedance(file, "series", "C1", F)
    assert (e.value.code, e.value.params) == ("E_S2P_BAND", {"ref": "C1", "path": str(file), "f_lo": "1000.0",
                                                             "f_hi": "3000.0", "f1": "457.5", "f2": "3015.6"})


def test_an_s2p_named_by_the_parts_place_is_warned(tmp_path):  # Review Focus 2: C2 sits in shunt, its file is series
    file = write_s2p(tmp_path / "c2.s2p", z_part("C", 3.3e-12, None, F), "series", F)
    assert s2p_impedance(file, "shunt", "C2", F)[1] == "series"
    p = lpf()
    parts(p)["C2"]["s2p"] = {"file": "c2.s2p", "connection": "shunt"}
    assert part_impedances(p, tmp_path, ["C2"], F)[1] == [
        ("W_S2P_FIXTURE", {"ref": "C2", "path": str(file), "named": "shunt", "fits": "series"})]


def test_each_part_port_gets_its_model_or_its_file(tmp_path):  # C-13..C-15, spec 7.2
    p = lpf()
    p["chain"]["series"].append(dict(FB1))
    write_s2p(tmp_path / "c2.s2p", z_part("C", 4.7e-12, None, F), "shunt", F)
    write_s2p(tmp_path / "fb1.s2p", np.full(len(F), 30 + 40j), "series", F)
    parts(p)["C2"]["s2p"] = {"file": "c2.s2p", "connection": "shunt"}
    parts(p)["FB1"]["s2p"] = {"file": "fb1.s2p", "connection": "series"}  # no kind: an S2P is its only model
    z, notes = part_impedances(p, tmp_path, ["C1", "L1", "C2", "FB1"], F)
    assert np.allclose(z["C1"], z_part("C", 100e-12, M0402, F), rtol=1e-15) and notes == []
    assert np.abs(z["C2"] / z_part("C", 4.7e-12, None, F) - 1).max() <= 1e-12
    assert np.abs(z["FB1"] / (30 + 40j) - 1).max() <= 1e-12
    for ref, value in (("C3", "x"), ("C3", "0pF"), ("FB1", "x")):  # unreadable; a C of 0, an open; FB1 with no file
        parts(p)[ref].update(value=value, s2p=None)
        with pytest.raises(KrsError) as e:
            part_impedances(p, tmp_path, [ref], F)
        assert (e.value.code, e.value.params) == ("E_PART_NO_VALUE", {"ref": ref, "value": value})
```

  Test imports: `copy`, `math`, `numpy as np`, `pytest`; `KrsError`; `model_of`, `srf` from `core.model.parts`; `parts` from `core.project`; `grid` from `core.post.waves`; `part_impedances`, `s2p_impedance`, `z_part` (Task 4 adds `ideal_schematic`, `loads`, `terminate`, `with_box`) from `core.post.chain`; `from networks import C_BOX, star, terminate_np, write_s2p`; `from test_gates import project_of`.

  `tests/test_project.py`:

```python
@pytest.mark.parametrize(("value", "ok"), [
    (None, True), ({"file": "../parts/l1.s2p", "connection": "series"}, True),
    ({"file": "l1.s2p", "connection": "Series"}, False), ({"file": 3, "connection": "shunt"}, False), (DELETE, False)])
def test_a_parts_s2p_is_null_or_a_file_and_its_fixture(tmp_path, value, ok):  # C-18
    _, pj = run_new(tmp_path, "--lid-height", "2.5")  # tests/test_cli_new.py
    d = load_project(pj)
    edit(d, ["chain", "series", 0, "s2p"], value)
    save_project(pj, d)
    if ok:
        assert read_project(pj)["chain"]["series"][0]["s2p"] == value
        return
    with pytest.raises(KrsError) as e:
        read_project(pj)
    assert (e.value.code, e.value.params) == ("E_PROJECT_FIELD", {
        "path": str(pj), "field": "chain.series[0].s2p",
        "expected": "null, or file (text) and connection (series or shunt)"})
```

  Revise on purpose in `tests/test_cli_new.py`: `test_project_layout`'s every part dict (series, shunt, others) and `test_new_writes_every_key_and_reads_it_back`'s `series[0]` gain `"s2p": None`; the comment of `test_a_part_that_is_no_c_l_or_r_has_no_package_preset` reads `# FB1, a ferrite bead in series: no kind, so only an S2P file closes its port (M-5)`.
- [ ] **Step 2: Run** `python -m pytest tests/test_post_chain.py tests/test_project.py tests/test_cli_new.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `parts()`, the `s2p` key, `port_value`, the comment, `build_model`'s use of `parts()` and `chain.py`'s three functions. `s2p_impedance`: missing file first; read with `n = rf.Network(); n.read_touchstone(str(file))` inside `try/except Exception` (a parser of user input); no frequencies → unreadable; `n.nports != 2` → ports; band; then Z as the Interfaces say, and the fixture check. Messages (`I_PART_NO_MODEL`, plan 3's, is reworded: its promise held only for a C, L or R):
  - `E_PART_NO_VALUE`: "Part {ref} has no value that reads (\"{value}\") and no S2P file, so its port cannot be closed. Give its S2P file with `retune PROJECT {ref}=file.s2p:series` (or :shunt), or, for a C, L or R, a value with `retune PROJECT {ref}=VALUE`."
  - `E_S2P_MISSING`: "Part {ref}: its S2P file {path} does not exist. Name an existing file with `retune PROJECT {ref}=file.s2p:series` (or :shunt), or, for a C, L or R, give a value with `retune PROJECT {ref}=VALUE`."
  - `E_S2P_UNREADABLE`: "Part {ref}: {path} is not a Touchstone file that can be read. Check the file, or, for a C, L or R, give a value with `retune PROJECT {ref}=VALUE`."
  - `E_S2P_PORTS`: "Part {ref}: {path} has {ports} ports, and a part needs a 2-port measured in a series or a shunt fixture. Give its .s2p file."
  - `E_S2P_BAND`: "Part {ref}: {path} covers {f_lo}–{f_hi} MHz, not the simulated band {f1}–{f2} MHz, and it is never extrapolated. Give a file that covers the band, or, for a C, L or R, a value with `retune PROJECT {ref}=VALUE`."
  - `W_S2P_FIXTURE`: "Part {ref}: {path} fits a {fits}-thru measurement better than the :{named} it was given. The suffix names the fixture the vendor measured the part in, not its place on the board; if the vendor used {fits}-thru, give it again as `retune PROJECT {ref}=file.s2p:{fits}`."
  - `I_PART_NO_MODEL`: "Part {ref} {value}: {role}; no package preset, so as a port a C, L or R takes its ideal value and any other part needs its S2P file (`retune PROJECT {ref}=file.s2p:series`, or :shunt)."
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: part models and S2P parts, with the s2p key in project.json (spec 5.7, 7.2)`

---

### Task 4: The C_box loads, the termination and the ideal schematic

**Files:**
- Modify: `src/kicad_rf_studio/core/post/chain.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_post_chain.py`

**Interfaces:**
- Consumes: `z_part` (Task 3); project.json's `chain` and `classes`; parts' `ref`, `nets`, `role`; `is_gnd`, `is_power` (`core.kicad.tracer`); `Z0`.
- Produces:
  - `chain.with_box(z: np.ndarray, f: np.ndarray, c_box: float) -> np.ndarray` = z/(1 + jω·c_box·z), finite at z = 0.
  - `chain.loads(zparts: dict[str, np.ndarray], refs: list[str], c_box: dict, f: np.ndarray) -> np.ndarray` (F, M): `with_box` of each ref with `c_box[ref]`; `E_CBOX {ref, value}` when it is missing, not finite or not above 0 (`value` "missing" or `:g`) (C-16).
  - `chain.terminate(s: np.ndarray, ext: list[int], zk: np.ndarray, f: np.ndarray) -> np.ndarray` (F, P, P), scikit-rf's `Circuit` (spec 7.2): the layout `rf.Network(frequency=…, s=s, z0=Z0, name="layout")`, `Circuit.Port(frequency, f"port{n}", z0=Z0)` for the n-th port of `ext` in its order, each other port k closed by `rf.Network(frequency=…, z=zk[:, m].reshape(-1, 1, 1), z0=Z0, name=f"load{k}")`; `Circuit(cnx).s_external`; M = 0 works.
  - `chain.ideal_schematic(project: dict, zparts: dict[str, np.ndarray], f: np.ndarray) -> np.ndarray` (F, 2, 2): the chain's parts at their Z_part with no layout, no C_box and no traces (C-30). `others` are excluded; P1 sits on `chain.nets[0]` and P2 on `chain.nets[-1]`, each a 50 Ω port.

  The nodal solve:

```text
union-find over chain.nets and every net of the series and shunt parts; one ground group "" joins each of those nets
that is off the chain and a GND or power net (in classes.gnd_nets or classes.power_nets; is_gnd or is_power by name
where the list is null), staying the root of any group it joins; a copper part, and a port or curve_port part whose
zparts[ref] is 0 at every f, joins its two nets' groups; an open part is left out; the nodes are the groups other than
ground that hold a chain net or an end of a port or curve_port part, chain.nets' groups first; Y (F, n, n) gets
y = 1/zparts[ref] of every other port or curve_port part between its two nets' nodes (a ground end stamps the
diagonal only); Q (n, 2) holds 1 at P1's node and at P2's (a column stays 0 for a grounded net);
S = 2·Qᵀ·(Y + Q·Qᵀ/Z0)⁻¹·Q/Z0 − I
```

- [ ] **Step 1: Write the failing tests** in `tests/test_post_chain.py`:

```python
CLASSES = {"gnd_nets": ["GND"], "power_nets": []}


def part(ref, a, b, role="port"):
    return {"ref": ref, "nets": [a, b], "role": role}


def schematic(series=(), shunt=(), nets=("A", "B")):
    return {"chain": {"nets": list(nets), "series": list(series), "shunt": list(shunt)}, "others": [],
            "classes": CLASSES}


BW_C, BW_L = 1 / (2 * np.pi * F0 * 50), 2 * 50 / (2 * np.pi * F0)  # Butterworth n = 3 pi at f0: 3.4788 pF, 17.394 nH
PI = schematic([part("L1", "A", "B")], [part("C1", "A", "GND"), part("C2", "B", "GND")])
W = 2 * np.pi * F
PI_Z = {"L1": 1j * W * BW_L, "C1": 1 / (1j * W * BW_C), "C2": 1 / (1j * W * BW_C)}


@pytest.mark.parametrize(("c", "shown"), [(None, "missing"), (0.0, "0"), (math.inf, "inf")])
def test_a_part_port_needs_a_usable_c_box(c, shown):  # C-16
    with pytest.raises(KrsError) as e:
        loads({"C1": z_part("C", 1e-12, None, F)}, ["C1"], {} if c is None else {"C1": c}, F)
    assert (e.value.code, e.value.params) == ("E_CBOX", {"ref": "C1", "value": shown})


def test_the_termination_is_scikit_rf_circuit_and_agrees_with_numpy():  # spec 7.2, C-6 (owner-confirmed: 1e-12)
    zk = loads({r: z_part(k, v, M0402, F) for r, k, v in LPF}, [r for r, _, _ in LPF],
               dict.fromkeys([r for r, _, _ in LPF], C_BOX), F)
    assert np.abs(zk[:, 1] - 1 / (1 / z_part("L", 15e-9, M0402, F) + 2j * np.pi * F * C_BOX)).max() <= 1e-9
    assert np.abs(terminate(star(F, 6), [0, 1], zk, F) - terminate_np(star(F, 6), [0, 1], zk)).max() <= 1e-12
    assert np.abs(terminate(star(F, 2), [0, 1], np.zeros((len(F), 0)), F) - star(F, 2)).max() <= 1e-15  # M = 0


def test_the_ideal_schematic_of_a_butterworth_pi():  # C-30: the ABCD oracle in closed form; r6 §6
    s = ideal_schematic(PI, PI_Z, F)
    assert np.abs(np.abs(s[:, 1, 0]) ** 2 - 1 / (1 + (F / F0) ** 6)).max() <= 1e-13
    assert 20 * np.log10(abs(s[71, 1, 0])) == pytest.approx(-3.0103, abs=1e-4)
    assert np.abs((np.abs(s) ** 2).sum(1) - 1).max() <= 1e-13  # lossless


@pytest.mark.parametrize(("model", "s21_db"), [(None, [-1.735, -15.80, -26.36]),
                                               (M0402, [-1.958, -19.971, -39.063])])
def test_lpf915s_ideal_schematic(model, s21_db):  # C-30: R1 (0R) a short, R2 (DNP) left out, C4 (others) excluded
    s = ideal_schematic(lpf(), {r: z_part(k, v, model, F) for r, k, v in LPF}, F)
    assert 20 * np.log10(np.abs(s[[71, 213, 355], 1, 0])) == pytest.approx(s21_db, abs=5e-3)


def test_one_net_a_bridging_shunt_and_the_nets_off_the_chain():  # C-30
    assert np.abs(ideal_schematic(schematic(nets=["LINE"]), {}, F) - np.array([[0, 1], [1, 0]])).max() <= 1e-15
    zl, zx = 1j * W * 15e-9, 1 / (1j * W * 1e-12)
    zs = zl * zx / (zl + zx)
    bridge = ideal_schematic(schematic([part("L1", "A", "B")], [part("X1", "A", "B")]), {"L1": zl, "X1": zx}, F)
    assert np.abs(bridge[:, 1, 0] - 100 / (100 + zs)).max() <= 1e-13
    s = ideal_schematic(schematic([part("L1", "A", "B")], [part("R9", "B", "GND", "copper")]), {"L1": zl}, F)
    assert np.abs(s[:, 1, 0]).max() <= 1e-15 and np.abs(s[:, 1, 1] + 1).max() <= 1e-15  # a grounded port reads −1
    stub = schematic([part("L1", "A", "B")], [part("R2", "B", "SMA", "copper"), part("C9", "B", "SMA")])
    assert np.abs(ideal_schematic(stub, {"L1": zl, "C9": zx}, F)[:, 1, 0] - 100 / (100 + zl)).max() <= 1e-13  # floats
    short = ideal_schematic(schematic([part("R5", "A", "B")]), {"R5": np.zeros(len(F), complex)}, F)  # 0R port, no preset
    assert np.abs(short - np.array([[0, 1], [1, 0]])).max() <= 1e-15
```
- [ ] **Step 2: Run** `python -m pytest tests/test_post_chain.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** `with_box`, `loads`, `terminate` and `ideal_schematic` as the Interfaces and the block say. Message:
  - `E_CBOX`: "The last run recorded no usable C_box for part {ref} ({value}), so its port cannot be closed. Run `run` again, and look at the part's port with `preview` if this repeats."
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: the C_box loads, the termination with scikit-rf's Circuit and the ideal schematic (spec 7.2, 7.3)`

---

### Task 5: The validity indicators and the comparison measures

**Files:**
- Create: `src/kicad_rf_studio/core/post/checks.py`, `tests/test_post_checks.py`
- Modify: `src/kicad_rf_studio/core/messages.py`

**Interfaces:**
- Consumes: `Z0`; `scipy.signal.find_peaks`; `scipy.constants.c`.
- Produces:
  - `SIGMA_LIMIT, RECIP_LIMIT, LOSS_LIMIT = 1.02, 0.02, 0.02` (C-35) with `# ponytail: the spec's provisional limits; plan 5 (P0) tightens them`; `NULL_PROMINENCE_DB, NULL_WINDOW, NULL_HALF = 20.0, 0.05, 4`.
  - `sigma_max(s) -> np.ndarray` (F,) = `np.linalg.norm(s, 2, axis=(-2, -1))` (never skrf's `passivity`); `recip_err(s) -> np.ndarray` (F,) = max over i, j of |S_ij − S_ji| (C-33).
  - `loss_budget(s: np.ndarray, ext: list[int], zk: np.ndarray) -> np.ndarray` (F,): P_layout for a unit wave into port ext[0], the other external ports matched (C-34): b_i = (I − S_ii·Γ)⁻¹·S_ie[:, :, 0], S'_e1 = S_ee[:, :, 0] + S_ei·Γ·b_i, P_u = 1 − Σ_e |S'_e1|², P_parts = Σ_k |b_k|²·(1 − |Γ_k|²), P_layout = P_u − P_parts (M = 0: P_parts = 0).
  - `loss_expected(sections: list[tuple[float, float, float, float]], f0: float) -> float`: 1 − exp(−2·Σ α_d·ℓ) over (εr, εeff, tanδ, length in mm), α_d = (π·f0/c)·εr·(εeff − 1)/(√εeff·(εr − 1))·tanδ in Np/m: the model's constant κ makes the effective tanδ = tanδ·f0/f, so the loss is flat in f (C-25).
  - `indicator_lines(f, a_db, s, p_layout: np.ndarray | None, expected: float) -> list[tuple[str, dict]]`: `I_PASSIVITY` or `W_PASSIVITY {sigma (:.4f), limit (:g), f_mhz (:.1f), a_db (:.1f)}` at the worst f of `s`; `I_RECIPROCITY` or `W_RECIPROCITY {err (:.2e), limit, f_mhz, a_db}`; with `p_layout`, `I_LOSS_BUDGET` or `W_LOSS_BUDGET {layout_pct, expected_pct (100·x :.2f), limit_pct (100·LOSS_LIMIT :g), f_mhz, a_db}` at the worst excess. The W_ form above its limit.
  - `nulls(f, s21, floor) -> np.ndarray`: the null frequencies of |S21| (C-39): `find_peaks` on x = −dB with prominence NULL_PROMINENCE_DB; a null is kept when the smaller of its two shoulder |S21|, 10^(−max(x[left_bases], x[right_bases])/20), is at least `floor` (both shoulders stand above the noise); each refined by a complex quadratic least-squares fit of S21 over the grid index k ± NULL_HALF (`np.polyfit` on (f − f_k)/Δf), its |p| minimised over 4001 points across the fit window.
  - `match_null(f, s21, fn) -> float | None`: the minimum of |S21| within fn·(1 ± NULL_WINDOW) refined the same way; None when it sits on the window's edge.
  - `compare(a: np.ndarray, b: np.ndarray, f: np.ndarray, k0: int, floor: float) -> dict`: a the reference (verify's), b the other (C-38, C-39): `{"ds21_db_f0": |20·log10|a21| − 20·log10|b21|| at k0, "ds11_f0": |a11 − b11| at k0 (complex), "ds_max": max over f and every entry of |a − b|, "nulls": [{"f_hz": the reference null, "shift": (f_a − f_b)/f_b or None}]}`, every value a plain float.

- [ ] **Step 1: Write the failing tests**

```python
F0 = 915e6
F, _ = grid(F0, 3, 1.1)


def db(x):
    return 20 * np.log10(np.abs(x))


def shunt_thru(z):
    """The 2-port of a shunt impedance z (F,) on a 50 Ω thru."""
    s11, s21 = -50 / (2 * z + 50), 2 * z / (2 * z + 50)
    return np.stack([np.stack([s11, s21], -1), np.stack([s21, s11], -1)], -2)


def lpf_zk():
    return np.stack([with_box(z_part(k, v, M0402, F), F, C_BOX) for _, k, v in LPF], -1)


def test_passivity_is_sigma_max_and_reciprocity_the_largest_asymmetry():  # spec 7.4, C-33, C-35
    assert (SIGMA_LIMIT, RECIP_LIMIT, LOSS_LIMIT) == (1.02, 0.02, 0.02)
    assert np.abs(sigma_max(star(F, 3, a=1.0)) - 1).max() <= 1e-14
    assert sigma_max(star(F, 6)).max() == pytest.approx(0.95 ** 2, abs=1e-12)
    s = star(F, 3).copy()
    s[:, 0, 2] += 0.01
    assert recip_err(s) == pytest.approx(np.full(len(F), 0.01), abs=1e-15)


def test_the_loss_budget_removes_the_part_losses_exactly():  # C-34; r6 §7
    assert np.abs(loss_budget(star(F, 6, a=1.0), [0, 1], lpf_zk())).max() <= 1e-14  # lossless layout, ESR parts
    expected = loss_expected([(4.5, 2.984, 0.02, 20.0)], F0)
    assert expected == pytest.approx(0.0112634, abs=1e-7)  # a 20 mm line under mask
    g = np.sqrt(1 - expected) * np.exp(-2j * np.pi * F * 0.1e-9)
    line = np.zeros((len(F), 2, 2), complex)
    line[:, 0, 1] = line[:, 1, 0] = g
    assert np.abs(loss_budget(line, [0, 1], np.zeros((len(F), 0))) - expected).max() <= 1e-14  # M = 0, flat


def test_the_indicators_name_their_worst_frequency_and_flag_above_their_limits():  # spec 7.4, C-12, C-33..C-35
    a_db = np.full(len(F), -3.0)
    calm = indicator_lines(F, a_db, star(F, 3), np.full(len(F), 0.01), 0.005)
    assert [code for code, _ in calm] == ["I_PASSIVITY", "I_RECIPROCITY", "I_LOSS_BUDGET"]
    s = star(F, 3).copy()
    s[100] *= 1.2
    s[200, 0, 1] += 0.05
    lines = indicator_lines(F, a_db, s, np.full(len(F), 0.05), 0.02)
    assert lines[0] == ("W_PASSIVITY", {"sigma": "1.0830", "limit": "1.02", "f_mhz": f"{F[100] / 1e6:.1f}",
                                        "a_db": "-3.0"})
    assert lines[1] == ("W_RECIPROCITY", {"err": "5.00e-02", "limit": "0.02", "f_mhz": f"{F[200] / 1e6:.1f}",
                                          "a_db": "-3.0"})
    assert lines[2] == ("W_LOSS_BUDGET", {"layout_pct": "5.00", "expected_pct": "2.00", "limit_pct": "2",
                                          "f_mhz": "457.5", "a_db": "-3.0"})
    assert [code for code, _ in indicator_lines(F, a_db, star(F, 3), None, 0.0)] == ["I_PASSIVITY", "I_RECIPROCITY"]


def test_compare_reports_delta_s_and_the_null_shift():  # spec 7.5, 7.6, C-38, C-39; r6 §8: −1.9419 % within 1e-5
    a = shunt_thru(z_part("C", 6.8e-12, {**M0402, "esl_h": 5.2e-10}, F))  # verify's: a −48 dB trap
    b = shunt_thru(z_part("C", 6.8e-12, M0402, F))
    c = compare(a, b, F, 71, 0.02)
    assert c["ds21_db_f0"] == pytest.approx(abs(db(a[71, 1, 0]) - db(b[71, 1, 0])), rel=1e-12)
    assert c["ds11_f0"] == pytest.approx(abs(a[71, 0, 0] - b[71, 0, 0]), rel=1e-12)
    assert c["ds_max"] == pytest.approx(np.abs(a - b).max(), rel=1e-12)
    (null,) = c["nulls"]
    assert null["f_hz"] == pytest.approx(2676.48e6, abs=0.05e6)
    assert null["shift"] == pytest.approx(1 / np.sqrt(1.04) - 1, abs=1e-5)
    flat = shunt_thru(np.full(len(F), 1e9 + 0j))
    assert compare(a, flat, F, 71, 0.02)["nulls"] == [{"f_hz": pytest.approx(null["f_hz"]), "shift": None}]
    assert compare(a, b, F, 71, 0.5)["nulls"] == []  # shoulders 0.892 at f1 and 0.083 at f2: the smaller one rules
```

  Test imports: `numpy as np`, `pytest`; `LOSS_LIMIT`, `RECIP_LIMIT`, `SIGMA_LIMIT`, `compare`, `indicator_lines`, `loss_budget`, `loss_expected`, `recip_err`, `sigma_max` from `core.post.checks`; `grid` from `core.post.waves`; `with_box`, `z_part` from `core.post.chain`; `from networks import C_BOX, star`; `from test_post_chain import LPF, M0402`.
- [ ] **Step 2: Run** `python -m pytest tests/test_post_checks.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `checks.py` as the Interfaces fix it. Messages:
  - `I_PASSIVITY`: "Passivity: σ_max {sigma} at worst, at {f_mhz} MHz (|a| {a_db} dB); flagged above {limit}."
  - `W_PASSIVITY`: "Passivity flagged: σ_max {sigma} at {f_mhz} MHz (|a| {a_db} dB) is above {limit}, so this S makes power. Check the verdicts above: a flat or T_max job is the usual cause, and a stricter preset the fix."
  - `I_RECIPROCITY`: "Reciprocity: |Sij − Sji| {err} at worst, at {f_mhz} MHz (|a| {a_db} dB); flagged above {limit}."
  - `W_RECIPROCITY`: "Reciprocity flagged: |Sij − Sji| {err} at {f_mhz} MHz (|a| {a_db} dB) is above {limit}. Check the verdicts above: a flat or T_max job is the usual cause, and a stricter preset the fix."
  - `I_LOSS_BUDGET`: "Loss budget: {layout_pct} % unaccounted with the part losses removed, against {expected_pct} % expected dielectric loss, at worst at {f_mhz} MHz (|a| {a_db} dB); flagged {limit_pct} points above."
  - `W_LOSS_BUDGET`: "Loss budget flagged: {layout_pct} % unaccounted at {f_mhz} MHz (|a| {a_db} dB) is more than {limit_pct} points above the {expected_pct} % expected dielectric loss. Radiation or power coupled into cut nets is the usual cause; look at the model with `preview`."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: passivity, reciprocity, the loss budget and the comparison measures (spec 7.4, 7.6)`

---

### Task 6: What `run` records: the preset, the expected loss, and only kept S

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: `loss_expected` (Task 5); `geom.sections`, `cross_section(..., "exact")`, `cs2d.solve`, `ShortError`, `geom.zs`.
- Produces:
  - `pipeline.expected_loss(geom: Geometry, f0: float) -> float` (C-25): `checks.loss_expected` over `geom.sections`, each with its with-mask εeff (`solve(cross_section(s, geom.pieces, geom.zs, geom.masks.get(s.layer), "exact")).eps_eff`, the solve `cost`'s readout prints), the εr and tanδ (None → 0) of the dielectric slab next to its copper slab in `geom.zs` (the one below, else the one above), and `s.length`; a section that raises `ShortError` adds nothing. `# ponytail: straight, axis-aligned sections only, a lower bound; bends, pads and vias add nothing`.
  - `_run` computes it right after `build_model` passes its gates, before `prepare`, so that an error there costs no job; `results` gains `"preset"` (the project's stop preset) and `"loss_expected"` (that float) between `gates` and `dt`.
  - `run` writes `results` only when every job's verdict is in KEPT (C-24, owner-confirmed); otherwise it emits `W_RUN_NOT_KEPT {kept, runs, wall, folder}` as a `result` event instead of `I_RESULTS` and returns 4, leaving `results` (and, from Task 9, `results/`) untouched. `run`'s docstring says so.

- [ ] **Step 1: Write the failing tests.** In `tests/test_run.py`:

```python
def only_run(data):
    """The one run folder a test's run made under the data folder `data`."""
    return next((data / "runs").iterdir())


def test_results_record_the_preset_and_the_expected_loss(tmp_path, calibrated):  # C-25
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    assert (r["preset"], r["loss_expected"]) == ("draft", pytest.approx(0.00995, abs=3e-5))  # 20 mm, εeff 2.650


def test_a_run_that_keeps_no_s_leaves_the_previous_results(tmp_path, calibrated, monkeypatch, capsys):  # C-24
    monkeypatch.setenv("KRS_FAKE", "nan")
    pj = coupon(tmp_path, "normal")
    save_project(pj, {**load_project(pj), "results": {"jobs": []}})
    assert main(["run", str(pj)]) == 4
    assert load_project(pj)["results"] == {"jobs": []}
    assert any(line.startswith("0 of 2 jobs kept S, in ") for line in capsys.readouterr().out.splitlines())
```

  Revise on purpose in `tests/test_run.py` (C-24: a run that keeps no S writes no results):
  - `test_each_verdict_through_run`: its last line is `assert verdict_codes(only_run(calibrated))[1] == verdict`.
  - `test_a_crashed_job_is_unclassified_and_the_others_finish`: `run = only_run(calibrated)`; `assert verdict_codes(run) == {1: "I_JOB_CONVERGED", 2: "W_JOB_UNCLASSIFIED"} and "results" not in load_project(pj)`; `log = run / "job-2-P2" / "log.txt"`.
  - `test_a_stop_file_stops_the_run_found_from_the_lock`, `test_ctrl_c_in_the_job_phase_stops_the_run_and_frees_the_lock` and `test_a_second_ctrl_c_kills_at_once_and_the_jobs_are_recorded`: `assert set(verdict_codes(only_run(calibrated)).values()) == {"W_JOB_STOPPED"} and "results" not in load_project(pj)` in place of the results checks.
  - `test_a_job_stopped_before_it_started_has_no_time_or_residual`: the `r["jobs"][1] == …` assertion goes; its events come from `only_run(calibrated) / "events.jsonl"`.
  - `test_lpf915_runs_one_job_per_port_and_records_c_box` adds `assert (r["preset"], r["loss_expected"]) == ("normal", pytest.approx(0.00451, abs=3e-5))` (r6 §7: 7.99 mm of sections).
- [ ] **Step 2: Run** `python -m pytest tests/test_run.py -q`. Expected: FAIL for the two new tests, `test_lpf915_runs_one_job_per_port_and_records_c_box` and the revised tests that assert `"results" not in load_project(pj)`; the other revisions (`test_each_verdict_through_run`, `test_a_job_stopped_before_it_started_has_no_time_or_residual`) pass before and after.
- [ ] **Step 3: Implement** `expected_loss` and the changes in `_run`. Message:
  - `W_RUN_NOT_KEPT`: "{kept} of {runs} jobs kept S, in {wall}, so project.json keeps its previous results and results/ is unchanged. The verdicts above, also in {folder}, say why; fix that and run `run` again."
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: record the preset and the expected loss; replace results only when every job kept S`

---

### Task 7: The outputs: Touchstone, CSV, PNG and the `results/` writer

**Files:**
- Create: `src/kicad_rf_studio/core/post/outputs.py`, `tests/test_post_outputs.py`
- Modify: `src/kicad_rf_studio/core/project.py` (`shown_reference`), `src/kicad_rf_studio/cli.py` (`_shown` moves there), `src/kicad_rf_studio/core/messages.py` (codes; `reason(error, fallback)`)

**Interfaces:**
- Consumes: `Layout` (Task 2); `sigma_max`, `recip_err` (Task 5); `parts` (Task 3); `messages.reason`, `render`.
- Produces:
  - `project.shown_reference(ref: dict | None) -> str`: cli's `_shown`, moved (a pad's name, `({x:.3f}, {y:.3f}) on {layer}` for a point, "none").
  - `messages.reason(error: Exception, fallback: str = "cannot be read") -> str`: plan 1's phrases, `fallback` for any other error.
  - `OUTPUTS = re.compile(r"(layout|chain)\.s\d+p|summary\.(png|csv)")`, `VERIFY_OUTPUT = re.compile(r"verify\.s\d+p")` (matched with `fullmatch`).
  - `COLUMNS = ("f_hz", "marker", "a_db", "s11_db", "s11_deg", "s21_db", "s21_deg", "ideal_s11_db", "ideal_s11_deg", "ideal_s21_db", "ideal_s21_deg", "sigma_max", "recip_err", "loss", "loss_expected")` (C-29).
  - `LIMITS = ("I_LIMIT_MAGNETIC", "I_LIMIT_LID", "I_LIMIT_S2P_PLANE", "I_LIMIT_PEC", "I_LIMIT_WALLS", "I_LIMIT_ACCURACY", "I_LIMIT_50_OHM", "I_LIMIT_IDEAL", "I_LIMIT_LOSS")` (C-32).
  - `touchstone(s: np.ndarray, f: np.ndarray, names: list[str], comments: list[str]) -> bytes`: `rf.Network(frequency=rf.Frequency.from_f(f, unit="Hz"), s=s, z0=Z0, name="out")` with `port_names` and `comments = "\n".join(" " + line for line in comments)`, `write_touchstone(return_string=True, form="ri")` encoded ASCII; every name and comment line made ASCII first with `.encode("ascii", "backslashreplace").decode()` (µ becomes `\xb5`).
  - `port_map(project: dict, results: dict, lay: Layout, idx: list[int]) -> list[str]` (C-28): first the basis, `run {run folder's name}, preset {preset}: ` and each job as `{port} {verdict}`, plus ` at {residual_db:.1f} dB` for flat and t_max; then per port index k in `idx`, numbered n = 1, 2, …: `port {n} {name}: external, signal {signal}, reference {shown_reference(reference)}` for an external port, `port {n} {ref}: part {value}` or `part s2p {file}:{connection}`, `, signal {pads[0]}, reference {pads[1]}, C_box {c_box[ref]:.6g} F` for a part, each ending `, as built` or `, row and column negated` (lay.flipped); then each part port of `lay` not in `idx` as `terminated {ref}: part {value}` or `part s2p {file}:{connection}`, `, C_box {c_box[ref]:.6g} F` (the chain file records what it was closed with).
  - `marker_lines(lay: Layout, chain: np.ndarray, ideal: np.ndarray | None) -> list[tuple[str, dict]]` (C-30): per marker k = lay.markers[n − 1], marker "f0" for n = 1 else `f"{n}f0"`, f_mhz `f"{f/1e6:g}"`, a_db `:.1f`, IL = −20·log10|S21|, RL = −20·log10|S11| (`:.2f`): `I_MARKER {marker, f_mhz, a_db, il_db, rl_db, il_ideal_db, rl_ideal_db}`, or `I_MARKER_TRACE {marker, f_mhz, a_db, il_db, rl_db}` without ideal; for n ≥ 2 right after it `I_HR {marker, hr_db, hr_ideal_db}` or `I_HR_TRACE {marker, hr_db}`, HR_n = IL(n·f0) − IL(f0) (`:.1f`).
  - `summary_csv(lay: Layout, chain: np.ndarray, ideal: np.ndarray | None, p_layout: np.ndarray, expected: float) -> bytes`: `csv.writer`, "\n" line ends, COLUMNS then one row per grid point; floats as written by `csv` (repr); the ideal columns "" without ideal; sigma_max and recip_err of lay.s; loss = p_layout; loss_expected = expected.
  - `summary_png(lay: Layout, chain: np.ndarray, ideal: np.ndarray | None, name: str) -> bytes` (C-30): imports matplotlib here only; `Figure(figsize=(15, 4.5))` with three axes: |S21| dB and |S11| dB against GHz (`render("I_PLOT_FREQUENCY")`; y labels "|S21| (dB)" and "|S11| (dB)" stay literal), "with layout" solid and "ideal schematic" dashed (`I_PLOT_LAYOUT`, `I_PLOT_IDEAL`), a thin vertical line at each marker; `skrf.plotting.smith(ax=…, draw_labels=True)` under S11's locus, with the markers as dots; `suptitle(render("I_PLOT_TITLE", name=name))`; `savefig` to bytes, PNG, 100 dpi.
  - `write(folder: Path, files: dict[str, bytes], own: re.Pattern, command: str) -> None` (C-27): `folder.mkdir(parents=True, exist_ok=True)`; every file written to `.{name}.tmp` first; then each `os.replace`d onto its name, `summary.*` first (the files a person keeps open, so a held one refuses before anything changes); then `os.remove` of each file whose whole name `own` matches and that is not in `files` (a stale N); `os` calls go through the `os` module. Any OSError on the way removes the temporary files left and raises `E_RESULTS_WRITE {path: the file in hand, reason: reason(err, "cannot be written"), command}`. No other file is touched. `# ponytail: files replaced before a refused one keep their new contents; the advised command rewrites them all`.

- [ ] **Step 1: Write the failing tests**

```python
F0 = 915e6
F, _ = grid(F0, 3, 1.1)
EXT = [{"name": "P1", "part": False}, {"name": "P2", "part": False}]


def lay_of(ports, s, flipped=None):
    return Layout(F, [71, 213, 355], s, np.full(len(F), -3.0), ports, flipped or [False] * len(ports))


def test_touchstone_is_1_1_ascii_with_the_port_map_before_the_option_line(tmp_path):  # C-28
    data = touchstone(star(F, 6), F, ["P1", "P2", "C1", "L1", "C2", "C3"], ["port 3 C1: part 4,7µF", "two"])
    assert data.decode("ascii").splitlines()[:4] == [
        "! port 3 C1: part 4,7\\xb5F", "! two", f"! Created with skrf {skrf.__version__} (http://scikit-rf.org).",
        "# Hz S RI R 50.0 "]
    (tmp_path / "layout.s6p").write_bytes(data)
    assert np.abs(read_s(tmp_path / "layout.s6p") - star(F, 6)).max() == 0


def test_the_port_map_names_every_port_its_pads_c_box_polarity_and_the_terminated_parts():  # C-28, spec 6.3 flags
    p = copy.deepcopy(project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")[1])
    parts(p)["L1"]["s2p"] = {"file": "../parts/l1.s2p", "connection": "series"}
    results = {"run_dir": "/x/runs/lpf915-20261022-120000-ab12", "preset": "normal",
               "c_box": {"C1": 2.4e-15, "L1": 2.7e-15, "C2": 1.4e-15, "C3": 1.4e-15},
               "jobs": [{"port": "P1", "verdict": "converged", "residual_db": -61.0},
                        {"port": "P2", "verdict": "flat", "residual_db": -45.2}]}
    ports = [{"name": n, "part": n[0] != "P"} for n in ("P1", "P2", "C1", "L1", "C2", "C3")]
    lay = lay_of(ports, star(F, 6), [False, False, False, True, False, False])
    layout_map, chain_map = port_map(p, results, lay, range(6)), port_map(p, results, lay, [0, 1])
    assert layout_map[0] == chain_map[0] == (
        "run lpf915-20261022-120000-ab12, preset normal: P1 converged, P2 flat at -45.2 dB")
    assert len(layout_map) == 7 and layout_map[1:5] == [
        "port 1 P1: external, signal U1.1, reference U1.2, as built",
        "port 2 P2: external, signal J1.1, reference J1.2, as built",
        "port 3 C1: part 100pF, signal C1.1, reference C1.2, C_box 2.4e-15 F, as built",
        "port 4 L1: part s2p ../parts/l1.s2p:series, signal L1.1, reference L1.2, C_box 2.7e-15 F, "
        "row and column negated"]
    assert chain_map[3:] == [
        "terminated C1: part 100pF, C_box 2.4e-15 F", "terminated L1: part s2p ../parts/l1.s2p:series, C_box 2.7e-15 F",
        "terminated C2: part 3.3pF, C_box 1.4e-15 F", "terminated C3: part 3.3pF, C_box 1.4e-15 F"]


def test_markers_give_il_rl_and_harmonic_rejection_with_the_excitation_level():  # C-30, spec 5.8
    chain = ideal_schematic(PI, PI_Z, F)  # the Butterworth pi of tests/test_post_chain.py
    lay = lay_of(EXT, chain)
    assert marker_lines(lay, chain, None) == [
        ("I_MARKER_TRACE", {"marker": "f0", "f_mhz": "915", "a_db": "-3.0", "il_db": "3.01", "rl_db": "3.01"}),
        ("I_MARKER_TRACE", {"marker": "2f0", "f_mhz": "1830", "a_db": "-3.0", "il_db": "18.13", "rl_db": "0.07"}),
        ("I_HR_TRACE", {"marker": "2f0", "hr_db": "15.1"}),
        ("I_MARKER_TRACE", {"marker": "3f0", "f_mhz": "2745", "a_db": "-3.0", "il_db": "28.63", "rl_db": "0.01"}),
        ("I_HR_TRACE", {"marker": "3f0", "hr_db": "25.6"})]
    assert marker_lines(lay, chain, chain)[0] == ("I_MARKER", {
        "marker": "f0", "f_mhz": "915", "a_db": "-3.0", "il_db": "3.01", "rl_db": "3.01", "il_ideal_db": "3.01",
        "rl_ideal_db": "3.01"})


def test_the_csv_is_one_row_per_grid_point():  # C-29
    chain = ideal_schematic(PI, PI_Z, F)
    lay = lay_of(EXT, chain)
    rows = list(csv.reader(io.StringIO(summary_csv(lay, chain, None, np.full(len(F), 0.01), 0.0045).decode("utf-8"))))
    assert rows[0] == list(COLUMNS) and len(rows) == len(F) + 1
    assert [rows[1 + k][1] for k in (70, 71, 213, 355)] == ["", "f0", "2f0", "3f0"]
    assert float(rows[72][0]) == F0 and float(rows[72][5]) == pytest.approx(-3.0103, abs=1e-4)
    assert rows[72][7:11] == ["", "", "", ""] and (float(rows[72][13]), float(rows[72][14])) == (0.01, 0.0045)
    both = list(csv.reader(io.StringIO(summary_csv(lay, chain, chain, np.zeros(len(F)), 0.0).decode("utf-8"))))
    assert both[72][9] == both[72][5]


def test_the_png_draws_on_agg_and_leaves_no_pyplot_figure():  # C-30, spec 3.1
    chain = ideal_schematic(PI, PI_Z, F)
    assert summary_png(lay_of(EXT, chain), chain, chain, "lpf915")[:8] == b"\x89PNG\r\n\x1a\n"
    import matplotlib.pyplot
    assert matplotlib.pyplot.get_fignums() == []


def test_only_the_png_writer_imports_matplotlib():  # C-5
    out = subprocess.run([sys.executable, "-I", "-c", "import sys, kicad_rf_studio.core.post.outputs; print(sorted("
                          "m for m in ('matplotlib', 'pandas') if m in sys.modules))"], capture_output=True, text=True)
    assert out.stdout.strip() == "[]"


def test_the_writer_replaces_only_its_own_files(tmp_path):  # C-27: a changed N leaves no stale file
    out = tmp_path / "p" / "results"
    out.mkdir(parents=True)
    for name in ("layout.s6p", "chain.s2p", "summary.csv", "notes.txt", "verify.s2p", "my.s2p"):
        (out / name).write_text("old")
    write(out, {"layout.s7p": b"7", "summary.csv": b"csv"}, OUTPUTS, "kicad-rf-studio retune p")
    assert {p.name: p.read_text() for p in out.iterdir()} == {
        "layout.s7p": "7", "summary.csv": "csv", "notes.txt": "old", "verify.s2p": "old", "my.s2p": "old"}
    write(tmp_path / "q" / "results", {"layout.s2p": b"2"}, OUTPUTS, "c")  # a folder that does not exist yet
    assert (tmp_path / "q" / "results" / "layout.s2p").read_bytes() == b"2"


@pytest.mark.parametrize(("fails", "held", "left"), [
    ("replace", "summary.csv", {"layout.s6p": "old", "summary.csv": "old"}),  # summaries first: nothing changed
    ("remove", "layout.s6p", {"layout.s6p": "old", "layout.s7p": "7", "summary.csv": "new"})])
def test_a_file_another_program_holds_is_a_coded_refusal(tmp_path, monkeypatch, fails, held, left):  # C-27, RF 1
    out = tmp_path / "results"
    out.mkdir()
    for name in ("layout.s6p", "summary.csv"):
        (out / name).write_text("old")
    real = getattr(os, fails)

    def refuse(*args):  # Windows refuses to replace or delete a file another program holds open
        if Path(args[-1]).name == held:
            raise PermissionError(13, "in use")
        real(*args)

    monkeypatch.setattr(os, fails, refuse)
    with pytest.raises(KrsError) as e:
        write(out, {"layout.s7p": b"7", "summary.csv": b"new"}, OUTPUTS, "kicad-rf-studio retune p")
    assert (e.value.code, e.value.params) == ("E_RESULTS_WRITE", {
        "path": str(out / held), "reason": "permission denied", "command": "kicad-rf-studio retune p"})
    assert {p.name: p.read_text() for p in out.iterdir()} == left  # no temporary file left


def test_the_stated_limits_are_nine_lines():  # spec 7.5, C-32
    assert len(LIMITS) == 9 and render(LIMITS[0]) == "Limit: no magnetic coupling between part bodies."
```

  Test imports: `copy`, `csv`, `io`, `os`, `subprocess`, `sys`, `Path`, `numpy as np`, `pytest`, `skrf`; `KrsError`, `render`; `parts` from `core.project`; `Layout`, `grid` from `core.post.waves`; `ideal_schematic` from `core.post.chain`; `COLUMNS`, `LIMITS`, `OUTPUTS`, `marker_lines`, `port_map`, `summary_csv`, `summary_png`, `touchstone`, `write` from `core.post.outputs`; `from networks import read_s, star`; `from test_gates import project_of`; `from test_post_chain import PI, PI_Z`.
- [ ] **Step 2: Run** `python -m pytest tests/test_post_outputs.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `outputs.py`, `shown_reference`, cli's use of it and `reason`'s fallback. Messages:
  - `E_RESULTS_WRITE`: "Cannot write {path}: {reason}. Close the program that holds it open (a spreadsheet, say), then run `{command}` to write it again."
  - `I_MARKER`: "{marker} = {f_mhz} MHz (|a| {a_db} dB): IL {il_db} dB and RL {rl_db} dB with layout; IL {il_ideal_db} dB and RL {rl_ideal_db} dB ideal schematic."
  - `I_MARKER_TRACE`: "{marker} = {f_mhz} MHz (|a| {a_db} dB): IL {il_db} dB and RL {rl_db} dB."
  - `I_HR`: "Harmonic rejection at {marker}: {hr_db} dB with layout, {hr_ideal_db} dB ideal schematic."
  - `I_HR_TRACE`: "Harmonic rejection at {marker}: {hr_db} dB."
  - `I_PLOT_TITLE`: "{name}: relative to a 50 Ω source and load"; `I_PLOT_LAYOUT`: "with layout"; `I_PLOT_IDEAL`: "ideal schematic"; `I_PLOT_FREQUENCY`: "Frequency (GHz)".
  - `I_LIMIT_MAGNETIC`: "Limit: no magnetic coupling between part bodies."
  - `I_LIMIT_LID`: "Limit: no interaction between part bodies and the lid."
  - `I_LIMIT_S2P_PLANE`: "Limit: vendor S2P reference planes differ from the pad-gap box."
  - `I_LIMIT_PEC`: "Limit: copper is PEC, so there is no conductor loss."
  - `I_LIMIT_WALLS`: "Limit: the through-crop walls absorb most of the power coupled into cut nets, and reflect the rest."
  - `I_LIMIT_ACCURACY`: "Limit: accuracy is reported as |ΔS| or as a null shift, never in dB at a null."
  - `I_LIMIT_50_OHM`: "Limit: insertion loss, return loss and harmonic rejection are relative to a 50 Ω source and load."
  - `I_LIMIT_IDEAL`: "Limit: the ideal schematic is the same part models (preset or S2P) joined ideally: no layout, no C_box, no traces."
  - `I_LIMIT_LOSS`: "Limit: the expected dielectric loss is a lower bound from the measured straight sections."
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: write Touchstone, CSV and PNG outputs to results/ with the port map and the stated limits`

---

### Task 8: `KRS_FAKE=network`, a fake worker with a known S

**Files:**
- Modify: `tests/networks.py`, `tests/fake_worker.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: `star`, `synth_records` (Task 1); `layout` (Task 2); `stoprule.Records`.
- Produces:
  - `networks.network_trace(ports: int, k: int, f1: float, f2: float, dt: float, t_end: float) -> Records`: job k's (0-based) records of `star(f, ports)` from `synth_records`, the energy Σ u² + (Z0·i)² at te = t_u.
  - `tests/fake_worker.py`: `KRS_FAKE=network` writes `network_trace(len(ports), job["port"] − 1, f1, f2, DT, job["t_max"])` sample by sample, exactly as the other kinds (C-41); its docstring names the kind. The existing kinds do not change.

- [ ] **Step 1: Write the failing test**

```python
def test_the_network_fake_records_the_waves_of_a_known_network(tmp_path, calibrated, monkeypatch):  # C-41, X-12
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = coupon(tmp_path, "normal")
    assert main(["run", str(pj)]) == 0
    p = load_project(pj)
    jobs = p["results"]["jobs"]
    assert [j["verdict"] for j in jobs] == ["converged"] * 2
    assert jobs[0]["t_cut"] == pytest.approx(4.5e-9, abs=0.1e-9)  # measured: 4.502 ns at Normal
    assert np.abs(layout(p, p["results"]).s - star(F, 2)).max() <= 1e-5
```

  Test imports: `tests/test_run.py` gains `F, _ = grid(915e6, 3, 1.1)`, `grid` and `layout` from `core.post.waves` and `from networks import star`.
- [ ] **Step 2: Run** `python -m pytest tests/test_run.py -q -k network`. Expected: FAIL (the fake converges on its ring traces, whose S is arbitrary).
- [ ] **Step 3: Implement** `network_trace` and the fake's branch (`from networks import network_trace`, next to `from traces import trace`).
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `test: a KRS_FAKE=network worker that records the waves of a known N-port`

---

### Task 9: `run` writes the outputs of §7.3

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: Tasks 2–7 (`layout`, `part_impedances`, `loads`, `terminate`, `ideal_schematic`, `loss_budget`, `indicator_lines`, `touchstone`, `port_map`, `marker_lines`, `summary_csv`, `summary_png`, `write`, `OUTPUTS`, `LIMITS`); `VERDICTS`, `GATES`, `runs.WINDOWS`.
- Produces:
  - `pipeline.command_line(*args: str) -> str`: the command a user types again: `subprocess.list2cmdline(args)` when `runs.WINDOWS`, else `shlex.join(args)` (a path with spaces stays one argument).
  - `pipeline.gate_lines(gates: dict) -> list[tuple[str, dict]]`: `[("W_GATE_LIMITS", {"fit2d_limit": f"{gates['fit2d_limit']:g}", "dt_floor": f"{gates['dt_floor']:g}"})]` when `gates != GATES`, else `[]` (C-10); `cost` and `_run`'s `limits()` use it.
  - `pipeline.write_outputs(path: Path, project: dict, command: str, *, layout_on_part_error: bool = False) -> list[tuple[str, dict]]`, the step `run` and `retune` share (spec 3.2, 7.3, C-26..C-32); `command` is `E_RESULTS_WRITE`'s advice:
    1. `results = project["results"]`; `lay = layout(project, results)` (its refusals and `E_S_SINGULAR` propagate); ext = the indices of `lay.ports` with `part` False, refs = the names of the others; `folder = path.parent / "results"`.
    2. `files = {f"layout.s{N}p": touchstone(lay.s, lay.f, [q["name"] for q in lay.ports], port_map(project, results, lay, range(N)))}`.
    3. The basis lines: `I_BASIS {run_dir, preset, converged, flat, t_max}` (counts), then for each flat job `W_JOB_FLAT {port, t_ns: t_cut, residual_db}` and each t_max job `W_JOB_T_MAX {port, t_ns: t_stop, residual_db}` (`:.2f`, `:.1f`), then `gate_lines(results["gates"])`.
    4. `zparts, notes = part_impedances(project, path.parent, refs, lay.f)` (the notes join the lines), `zk = loads(zparts, refs, results["c_box"], lay.f)`. A KrsError here is re-raised, unless `layout_on_part_error`: then `write(folder, files, OUTPUTS, command)` and return the lines so far + `(err.code, err.params)` + `I_OUTPUTS` + LIMITS (C-26: the layout N-port, the refusal with its fix, the limits).
    5. `chain = terminate(lay.s, ext, zk, lay.f)`; with refs, `files[f"chain.s{P}p"] = touchstone(chain, lay.f, [lay.ports[k]["name"] for k in ext], port_map(project, results, lay, ext))`.
    6. P = 2: `ideal = ideal_schematic(project, zparts, lay.f)` when there are refs, else None; `p_layout = loss_budget(lay.s, ext, zk)`; lines += `marker_lines(lay, chain, ideal)` + `indicator_lines(lay.f, lay.a_db, lay.s, p_layout, results["loss_expected"])`; `files["summary.csv"]` and `files["summary.png"]` (name `path.parent.name`). P ≠ 2: lines += `indicator_lines(…, None, …)` + `W_NOT_TWO_PORT {ports: P}` (C-31).
    7. `write(folder, files, OUTPUTS, command)`; return lines + `I_OUTPUTS {files: ", ".join(sorted(files)), folder}` + `(code, {})` for each code of LIMITS.

  `_run`, after saving `results` and emitting `I_RESULTS`, emits each line of `write_outputs(path, data, command_line("kicad-rf-studio", "retune", str(path)), layout_on_part_error=True)` as a `result` event (an `E_` line as a `message` event) and returns 2 when an `E_` line is among them, else 0; `E_S_SINGULAR` reaches `run`'s handler: a message event and exit 2, nothing written.

- [ ] **Step 1: Write the failing tests** in `tests/test_run.py`:

```python
def lpf_project(tmp_path):
    """lpf915's project.json, from a copy of the board (a test may re-save it), with a 2.5 mm lid."""
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes((FIX / "lpf915.kicad_pcb").read_bytes())
    assert main(["new", str(board), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "--lid-height", "2.5",
                 "-o", str(tmp_path / "lpf915")]) == 0
    return tmp_path / "lpf915" / "project.json"


def lpf_run(tmp_path, monkeypatch):
    """lpf915 run on the network fake: its project.json."""
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = lpf_project(tmp_path)
    assert main(["run", str(pj)]) == 0
    return pj


def lpf_loads(model, **values):
    """Z_part ∥ C_BOX of lpf915's part ports in job order, at `values` (F or H) or the board's."""
    v = {**{ref: value for ref, _, value in LPF}, **values}
    return np.stack([with_box(z_part(ref[0], v[ref], model, F), F, C_BOX) for ref in v], -1)


def result_codes(run_dir):
    events = [json.loads(line) for line in (Path(run_dir) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return [e["code"] for e in events if e["kind"] == "result"]


def test_run_writes_the_outputs_of_a_known_network(tmp_path, calibrated, monkeypatch):  # spec 3.2, 7.3, C-26..C-30
    pj = lpf_run(tmp_path, monkeypatch)
    out = pj.parent / "results"
    assert sorted(p.name for p in out.iterdir()) == ["chain.s2p", "layout.s6p", "summary.csv", "summary.png"]
    assert np.abs(read_s(out / "layout.s6p") - star(F, 6)).max() <= 1e-5
    assert np.abs(read_s(out / "chain.s2p") - terminate_np(star(F, 6), [0, 1], lpf_loads(M0402))).max() <= 1e-5
    assert result_codes(load_project(pj)["results"]["run_dir"]) == [
        "I_RESULTS", "I_BASIS", "I_MARKER", "I_MARKER", "I_HR", "I_MARKER", "I_HR", "I_PASSIVITY", "I_RECIPROCITY",
        "W_LOSS_BUDGET", "I_OUTPUTS", *LIMITS]  # the star's lines lose 19 % or more


def test_a_single_trace_writes_its_two_port_and_summary(tmp_path, calibrated, monkeypatch):  # spec 7.3, C-31, C-24
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 0
    out = pj.parent / "results"
    assert sorted(p.name for p in out.iterdir()) == ["layout.s2p", "summary.csv", "summary.png"]
    assert np.abs(read_s(out / "layout.s2p") - star(F, 2)).max() <= 1e-5
    rows = list(csv.reader(io.StringIO((out / "summary.csv").read_text(encoding="utf-8"))))
    assert rows[0] == list(COLUMNS) and rows[72][1] == "f0" and rows[72][7:11] == ["", "", "", ""]
    assert result_codes(load_project(pj)["results"]["run_dir"]) == [
        "I_RESULTS", "I_BASIS", "I_MARKER_TRACE", "I_MARKER_TRACE", "I_HR_TRACE", "I_MARKER_TRACE", "I_HR_TRACE",
        "I_PASSIVITY", "I_RECIPROCITY", "W_LOSS_BUDGET", "I_OUTPUTS", *LIMITS]
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    monkeypatch.setenv("KRS_FAKE", "nan")
    assert main(["run", str(pj)]) == 4  # a run that keeps no S leaves results/ as it was
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_t_max_jobs_are_reduced_whole_and_flagged(tmp_path, calibrated, monkeypatch):  # R-4, X-2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = coupon(tmp_path)
    save_project(pj, {**load_project(pj), "t_max_s": 3e-9})  # T_max before 2·t0 + 1 ns: the rule cannot converge
    assert main(["run", str(pj)]) == 0
    r = load_project(pj)["results"]
    assert [(j["verdict"], j["t_cut"]) for j in r["jobs"]] == [("t_max", None)] * 2
    assert result_codes(r["run_dir"])[:4] == ["I_RESULTS", "I_BASIS", "W_JOB_T_MAX", "W_JOB_T_MAX"]
    head = (pj.parent / "results" / "layout.s2p").read_text(encoding="ascii").split("#")[0]
    assert ", preset draft: P1 t_max at " in head and ", P2 t_max at " in head


def test_three_external_ports_get_their_touchstone_and_no_two_port_summary(tmp_path):  # C-31
    rec = synth_records(lambda f: star(f, 3), 3, 457.5e6, 3.0195e9, 1.73972e-13, 10e-9)
    results = {**fake_run(tmp_path, rec, [port("P1"), port("P2"), port("P3")]), "preset": "normal", "gates": GATES,
               "c_box": {}, "loss_expected": 0.0}
    ports = [{"name": f"P{k}", "signal": f"J{k}.1", "reference": {"pad": f"J{k}.2", "uuid": ""}} for k in (1, 2, 3)]
    project = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "ports": ports, "others": [],
               "chain": {"nets": ["A"], "series": [], "shunt": []}, "results": results}
    lines = write_outputs(tmp_path / "p" / "project.json", project, "c")
    assert sorted(p.name for p in (tmp_path / "p" / "results").iterdir()) == ["layout.s3p"]
    assert [c for c, _ in lines] == ["I_BASIS", "I_PASSIVITY", "I_RECIPROCITY", "W_NOT_TWO_PORT", "I_OUTPUTS", *LIMITS]
    assert lines[3] == ("W_NOT_TWO_PORT", {"ports": 3})


def test_a_narrow_band_s2p_leaves_the_layout_n_port(tmp_path, calibrated, monkeypatch, capsys):  # Review Focus 3
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = lpf_project(tmp_path)
    f = np.linspace(1e9, 3e9, 41)
    write_s2p(pj.parent / "c1.s2p", z_part("C", 100e-12, None, f), "series", f)
    d = load_project(pj)
    parts(d)["C1"]["s2p"] = {"file": "c1.s2p", "connection": "series"}
    save_project(pj, d)
    assert main(["run", str(pj)]) == 2
    assert "results" in load_project(pj)
    assert sorted(p.name for p in (pj.parent / "results").iterdir()) == ["layout.s6p"]
    out = capsys.readouterr().out.splitlines()
    assert render("E_S2P_BAND", ref="C1", path=str(pj.parent / "c1.s2p"), f_lo="1000.0", f_hi="3000.0", f1="457.5",
                  f2="3015.6") in out
    assert out[-len(LIMITS):] == [render(code) for code in LIMITS]  # spec 7.5: printed with every result
```

  Test imports (`tests/test_run.py`): `csv`, `io`; `GATES`, `parts` from `core.project`; `COLUMNS`, `LIMITS` from `core.post.outputs`; `with_box`, `z_part` from `core.post.chain`; `write_outputs` from `pipeline`; `from networks import C_BOX, read_s, star, synth_records, terminate_np, write_s2p`; `from test_post_waves import fake_run, port`; `from test_post_chain import LPF, M0402`; `FIX` from `test_cli_cost`.
- [ ] **Step 2: Run** `python -m pytest tests/test_run.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** `command_line`, `gate_lines`, `write_outputs` and `_run`'s output step. Messages:
  - `I_BASIS`: "Results of the run in {run_dir} at preset {preset}: {converged} jobs converged, {flat} flat, {t_max} at T_max."
  - `W_NOT_TWO_PORT`: "The project has {ports} external ports, not 2, so the 2-port summary (PNG, CSV, IL, RL, harmonic rejection, loss budget, ideal schematic) is skipped; the Touchstone files and the passivity and reciprocity checks are written. Keep two ports in project.json for the summary."
  - `I_OUTPUTS`: "Wrote {files} in {folder}."
- [ ] **Step 4: Run** the full suite, then `python -m pytest -m openems tests/test_run.py -q` (the 0.3 ns coupon run now writes its outputs too). Expected: all pass.
- [ ] **Step 5: Commit.** `feat: run writes the outputs of spec 7.3`

---

### Task 10: `retune`

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py`, `src/kicad_rf_studio/core/project.py` (`relative_path`), `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`
- Create: `tests/test_retune.py`

**Interfaces:**
- Consumes: `write_outputs`, `command_line` (Task 9); `load`, `build_model`, `Model`, `spec_hash`; `runs.project_lock`; `parts` (Task 3); `port_value` (Task 3).
- Produces:
  - `project.relative_path(file: str | Path, folder: Path) -> tuple[str, bool]`: `os.path.relpath(file, folder)` with forward slashes, False; on another drive (ValueError) the absolute path, True. `cli._new` uses it for the board (behaviour unchanged).
  - `pipeline.results_of(project: dict, model: Model) -> dict` (spec 7.8, C-22, C-23): `E_NO_RESULTS` without `results`; `E_RESULTS_STALE` when `model.spec` is None, its `spec_hash` is not `results["model_hash"]`, or the results lack `loss_expected` (a run before this plan). `# ponytail: rebuilds the model (1.2–3.2 s on lpf915) to compare hashes; Stage 2 may cache it`.
  - `pipeline.assign(project: dict, assignments: list[str], folder: Path) -> dict` (C-17, C-18): a deep copy with each "REF=RIGHT" stored, split at the first "="; a RIGHT that ends in ":series" or ":shunt" (`rsplit(":", 1)`) sets `s2p = {"file": relative_path(path, folder)[0], "connection"}` — a relative path is read from the working directory, as `new` reads BOARD — and leaves `value` and `model`; any other RIGHT must read (`port_value(ref, RIGHT)`, so a C of 0 is refused), is stored verbatim as `value` and sets `s2p` to None. Refusals, the first in argument order: `E_RETUNE_ARG {arg}` (no "="), `E_RETUNE_TWICE {ref}`, `E_RETUNE_UNKNOWN {ref, refs}` (refs: the retunable refs, project order, ", "), `E_RETUNE_ROLE {ref, role}` (copper, open or grid), `E_RETUNE_VALUE {ref, value}`. `# ponytail: a file on another drive is stored absolute without a warning; a moved project then meets E_S2P_MISSING`.
  - `pipeline.retune(path: Path, assignments: list[str], emit: Callable[[str, dict], None] | None = None) -> int`: under `runs.project_lock(path, path.parent / "results")`: `read_project`; `E_RETUNE_NO_PARTS` when no part has role port or curve_port (C-21); `assign`; `load` and `build_model`, `results_of`; `lines = write_outputs(path, new, command_line("kicad-rf-studio", "retune", str(path), *assignments))`; `save_project(path, new)` when there were assignments (none: the outputs only, C-19); then `emit(code, params)` for each line — the default prints the rendered line; Stage 2's GUI passes its own (C-4) — and returns 0. It starts no worker and needs no openEMS; any refusal stores nothing (C-20).
  - The command `kicad-rf-studio retune PROJECT [ASSIGNMENT ...]` (`assignments`, `nargs="*"`), `pipeline.retune(pipeline.project_path(a.project), a.assignments)` with pipeline imported inside, no help text; cli's docstring names `retune`.

- [ ] **Step 1: Write the failing tests** in `tests/test_retune.py`:

```python
F, _ = grid(915e6, 3, 1.1)


def chain_of(pj):
    return read_s(pj.parent / "results" / "chain.s2p")


def test_retune_stores_a_value_and_rewrites_the_outputs_without_a_worker(tmp_path, calibrated, monkeypatch,
                                                                          capsys):  # spec 3.2, 7.2, C-17..C-19
    pj = lpf_run(tmp_path, monkeypatch)  # tests/test_run.py
    monkeypatch.setattr(subprocess, "Popen", fail)  # tests/test_cli_cost.py
    capsys.readouterr()
    assert main(["retune", str(pj), "C2=4.7pF"]) == 0
    assert (parts(load_project(pj))["C2"]["value"], parts(load_project(pj))["C2"]["s2p"]) == ("4.7pF", None)
    oracle = terminate_np(star(F, 6), [0, 1], lpf_loads(M0402, C2=4.7e-12))
    assert np.abs(chain_of(pj) - oracle).max() <= 1e-5
    assert b"! terminated C2: part 4.7pF, C_box 2e-14 F" in (pj.parent / "results" / "chain.s2p").read_bytes()
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("Results of the run in ") and out[-len(LIMITS):] == [render(c) for c in LIMITS]
    assert "openEMS" not in sys.modules
    board = pj.parent.parent / "lpf915.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n")  # re-saved in KiCad, its model unchanged: still not stale
    (pj.parent / "results" / "chain.s2p").unlink()
    assert main(["retune", str(pj)]) == 0 and np.abs(chain_of(pj) - oracle).max() <= 1e-5  # C-19: no assignment


def test_an_s2p_assignment_keeps_the_value_and_a_value_clears_it(tmp_path, calibrated, monkeypatch):  # C-17, C-18
    pj = lpf_run(tmp_path, monkeypatch)
    (tmp_path / "parts").mkdir()
    s2p = write_s2p(tmp_path / "parts" / "l1.s2p", z_part("L", 18e-9, None, F), "series", F)
    assert main(["retune", str(pj), f"L1={s2p}:series"]) == 0
    l1 = parts(load_project(pj))["L1"]
    assert (l1["value"], l1["s2p"]) == ("15nH", {"file": "../parts/l1.s2p", "connection": "series"})
    zk = lpf_loads(M0402)
    zk[:, 1] = with_box(z_part("L", 18e-9, None, F), F, C_BOX)
    assert np.abs(chain_of(pj) - terminate_np(star(F, 6), [0, 1], zk)).max() <= 1e-5
    assert main(["retune", str(pj), "L1=12nH"]) == 0
    assert (parts(load_project(pj))["L1"]["value"], parts(load_project(pj))["L1"]["s2p"]) == ("12nH", None)


def test_bad_assignments_are_refused_and_store_nothing(tmp_path, calibrated, monkeypatch, capsys):  # C-17, C-20, spec 8
    pj = lpf_run(tmp_path, monkeypatch)  # one run serves every case: a refusal stores nothing
    before, stamp = pj.read_bytes(), (pj.parent / "results" / "chain.s2p").stat().st_mtime_ns
    missing = pj.parent / "missing.s2p"
    for args, code, params in [
            (["C1"], "E_RETUNE_ARG", {"arg": "C1"}),
            (["C1=1pF", "C1=2pF"], "E_RETUNE_TWICE", {"ref": "C1"}),
            (["X9=1pF"], "E_RETUNE_UNKNOWN", {"ref": "X9", "refs": "C1, L1, C2, C3"}),
            (["R1=0R"], "E_RETUNE_ROLE", {"ref": "R1", "role": "copper"}),
            (["C4=1pF"], "E_RETUNE_ROLE", {"ref": "C4", "role": "open"}),
            (["C1=15nH"], "E_RETUNE_VALUE", {"ref": "C1", "value": "15nH"}),
            (["C1=part.s2p"], "E_RETUNE_VALUE", {"ref": "C1", "value": "part.s2p"}),
            (["C2=0"], "E_RETUNE_VALUE", {"ref": "C2", "value": "0"}),  # a C of 0 is an open: every output NaN
            ([f"C1={missing}:series"], "E_S2P_MISSING", {"ref": "C1", "path": str(missing)})]:
        capsys.readouterr()
        assert main(["retune", str(pj), *args]) == 2
        assert capsys.readouterr().err == render(code, **params) + "\n"
    assert pj.read_bytes() == before and (pj.parent / "results" / "chain.s2p").stat().st_mtime_ns == stamp


def test_a_part_with_no_kind_takes_only_an_s2p(tmp_path):  # C-15, M-5: FB1, a ferrite bead, has no ideal value
    p = copy.deepcopy(project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")[1])
    p["chain"]["series"].append(dict(FB1))
    with pytest.raises(KrsError) as e:
        assign(p, ["FB1=4.7pF"], tmp_path)
    assert (e.value.code, e.value.params) == ("E_RETUNE_VALUE", {"ref": "FB1", "value": "4.7pF"})
    file = write_s2p(tmp_path / "fb1.s2p", np.full(len(F), 30 + 40j), "series", F)
    assert parts(assign(p, [f"FB1={file}:series"], tmp_path))["FB1"]["s2p"] == {"file": "fb1.s2p",
                                                                                "connection": "series"}


def test_a_single_trace_has_no_retune(tmp_path, calibrated, capsys):  # spec 7.3, C-21
    assert main(["retune", str(coupon(tmp_path)), "C1=1pF"]) == 2
    assert capsys.readouterr().err == render("E_RETUNE_NO_PARTS") + "\n"


def test_retune_needs_results_of_this_model(tmp_path, calibrated, monkeypatch, capsys):  # spec 7.8, C-22, C-23
    assert main(["retune", str(lpf_project(tmp_path))]) == 2
    assert capsys.readouterr().err == render("E_NO_RESULTS") + "\n"
    pj = lpf_run(tmp_path / "b", monkeypatch)
    save_project(pj, {**load_project(pj), "t_max_s": 30e-9})  # the excitation is in the model hash
    assert main(["retune", str(pj)]) == 2 and capsys.readouterr().err == render("E_RESULTS_STALE") + "\n"
    d = load_project(pj)
    d["t_max_s"] = 40e-9
    del d["results"]["loss_expected"]  # a run before this plan
    save_project(pj, d)
    assert main(["retune", str(pj)]) == 2 and capsys.readouterr().err == render("E_RESULTS_STALE") + "\n"


def test_a_csv_held_open_refuses_and_stores_nothing(tmp_path, calibrated, monkeypatch, capsys):  # Review Focus 1
    pj = lpf_run(tmp_path, monkeypatch)
    csv_file = pj.parent / "results" / "summary.csv"
    before, held, real = pj.read_bytes(), csv_file.read_bytes(), os.replace

    def replace(src, dst):
        if Path(dst).name == "summary.csv":
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    capsys.readouterr()
    assert main(["retune", str(pj), "C2=4.7pF"]) == 2
    command = command_line("kicad-rf-studio", "retune", str(pj), "C2=4.7pF")  # the rerun keeps the assignment
    assert capsys.readouterr().err == render("E_RESULTS_WRITE", path=str(csv_file), reason="permission denied",
                                             command=command) + "\n"
    assert "C2=4.7pF" in command and pj.read_bytes() == before and csv_file.read_bytes() == held


def test_a_windows_path_with_spaces_and_accents(tmp_path, calibrated, monkeypatch):  # Review Focus 4
    pj = lpf_run(tmp_path, monkeypatch)
    (tmp_path / "peça 1").mkdir()
    s2p = write_s2p(tmp_path / "peça 1" / "bobina ç.s2p", z_part("L", 18e-9, None, F), "series", F)
    assert main(["retune", str(pj), f"L1={s2p}:series", "C2=3,9pF"]) == 0  # on Windows the path has a drive letter
    d = load_project(pj)
    assert parts(d)["L1"]["s2p"] == {"file": "../peça 1/bobina ç.s2p", "connection": "series"}
    assert parts(d)["C2"]["value"] == "3,9pF"
    head = (pj.parent / "results" / "layout.s6p").read_bytes().split(b"#")[0]
    assert max(head) < 128 and b"part s2p ../pe\\xe7a 1/bobina \\xe7.s2p:series" in head


def test_a_deleted_run_folder_refuses_the_retune(tmp_path, calibrated, monkeypatch, capsys):  # Review Focus 5
    pj = lpf_run(tmp_path, monkeypatch)
    run_dir = Path(load_project(pj)["results"]["run_dir"])
    shutil.rmtree(run_dir)
    before = sorted(p.name for p in (pj.parent / "results").iterdir())
    capsys.readouterr()
    assert main(["retune", str(pj)]) == 2
    assert capsys.readouterr().err == render("E_RESULTS_WAVES", path=str(run_dir / "model.json")) + "\n"
    assert sorted(p.name for p in (pj.parent / "results").iterdir()) == before


def test_retune_refuses_while_a_run_holds_the_lock(tmp_path, calibrated, monkeypatch, capsys):  # C-20
    pj = lpf_run(tmp_path, monkeypatch)
    before, lock = pj.read_bytes(), pj.parent / "project.json.lock"
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    capsys.readouterr()
    assert main(["retune", str(pj), "C2=4.7pF"]) == 2
    assert capsys.readouterr().err == render("E_LOCKED", lock=str(lock), run="R", started="S") + "\n"
    assert pj.read_bytes() == before
```

  Test imports: `copy`, `json`, `os`, `shutil`, `subprocess`, `sys`, `Path`, `numpy as np`, `pytest`; `main`; `KrsError`, `render`; `load_project`, `parts`, `save_project` from `core.project`; `grid` from `core.post.waves`; `with_box`, `z_part` from `core.post.chain`; `LIMITS` from `core.post.outputs`; `assign`, `command_line` from `pipeline`; `from networks import C_BOX, read_s, star, terminate_np, write_s2p`; `from test_cli_cost import fail`; `from test_gates import project_of`; `from test_post_chain import FB1, M0402`; `from test_run import coupon, lpf_loads, lpf_project, lpf_run`.
- [ ] **Step 2: Run** `python -m pytest tests/test_retune.py -q`. Expected: FAIL (`invalid choice: 'retune'`).
- [ ] **Step 3: Implement** `relative_path`, `results_of`, `assign`, `retune` and the command. Messages:
  - `E_RETUNE_NO_PARTS`: "This project has no part ports (a single trace), so there is nothing to retune; `run` writes its outputs."
  - `E_RETUNE_ARG`: "Cannot read \"{arg}\": write REF=VALUE, as in C1=4.7pF, or REF=file.s2p:series (or :shunt)."
  - `E_RETUNE_TWICE`: "{ref} is assigned twice; give each part once."
  - `E_RETUNE_UNKNOWN`: "No part {ref} is a port of this project. The parts you can retune: {refs}."
  - `E_RETUNE_ROLE`: "Part {ref} is {role} in the model, not a port, so retune cannot change it. To retune it, set its role to \"port\" in project.json and run `run` again (each port adds a run)."
  - `E_RETUNE_VALUE`: "Cannot read \"{value}\" as the value of {ref}: a C, L or R takes a value in its own unit (4.7pF, 4p7, 15nH, 50R; a C above 0), and any part takes an S2P file as {ref}=file.s2p:series (or :shunt)."
  - `E_NO_RESULTS`: "project.json has no results yet. Run `run` first."
  - `E_RESULTS_STALE`: "The model changed since the last run (a board re-saved in KiCad can change it too), or that run is older than this version, so its results no longer apply. Run `run` again."
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: retune values and S2P files without a new run (spec 3.2, 7.2, 7.8)`

---

### Task 11: verify's model: every part port in the grid, the inductor and the k check

**Files:**
- Modify: `src/kicad_rf_studio/core/model/spec.py`, `src/kicad_rf_studio/core/model/csx.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_model_spec.py`, `tests/test_model_csx.py`

**Interfaces:**
- Consumes: `readers.c_box` (imported into spec.py as `c_box` and looked up at call time, so a test can patch `spec.c_box`); `part_kind`, `port_value` (Task 3).
- Produces:
  - `spec.K_MAX = 0.45` with `# ponytail: stable up to k 0.48 at openEMS's own dt on a uniform grid with equal edges (r3 3.6); plan 5 confirms it` (C-37, owner-confirmed).
  - `spec.verify_spec(spec: dict, parts: dict[str, dict], boxes: dict, dump: Path, dt: float) -> dict` (spec 7.6, C-36): a deep copy of the run's (rebuilt) `spec` whose part ports leave `ports` for `grid`, appended after the run's own grid parts, on the same mesh lines; `boxes` is the run's C_box by ref. Each entry is the port's dict plus "R", "C" and, for an L, "L":
    - a C: the port's box, `C = value + boxes[ref]`, R None (a grid C replaces the box's own capacitance);
    - an R: the port's box, `R = value`, C None (it keeps the natural C);
    - an L: the one-cell box — per axis, lo and hi the smaller and larger of the box's two ends (a box can start at its higher end: lpf915's L1 runs from x 106.711 to 106.288); per in-plane axis the cell `[lines[i], lines[i + 1]]` with `lines[i]` the last mesh line at or below the box's centre, moved inside [lo, hi]; in z the box's copper slab, one cell; start and stop ascending — with `L = value`, R None and `C = c_box(dump, lines, cell start, cell stop, axis, dt)`, the explicit natural capacitance of that cell (every L gets one; `LEtype` is never written, so 0, never 1); and two PEC strips added to `metal.copper` as `{"x": [x0, x1, x1, x0], "y": [y0, y0, y1, y1], "z": [z0, z1]}`: along `dir` from lo to the cell and from the cell to hi, the cell's width across, the slab thick, each left out when its length is 0.
    - Refusals, in port order, per part: `E_VERIFY_VALUE {ref, value}` when the part is not a C, L or R whose value reads (`port_value`); `E_CBOX {ref, value}` for a C whose C_box is missing, not finite or not above 0; for an L, `E_VERIFY_DUMP {path}` when `dump` is missing, then `E_VERIFY_K {ref, k (:.3g), limit (:g)}` when k = dt/(2·√(L·C)) exceeds K_MAX (a C ≤ 0 reads as k inf).
  - `build_csx`: a grid entry's element takes every one of R, C and L that is set (`part.get(key) is not None`): `AddLumpedElement(f"lumped_{i}", ny=…, caps=True, **value)`. `grid_entry` keeps refusing an L for `run` (E_GRID_KIND), so `run`'s roles never put one in the grid (spec 5.7).

- [ ] **Step 1: Write the failing tests** in `tests/test_model_spec.py`:

```python
DT = 1.73972e-13  # the dumps model's dt
VPORTS = [  # on the dumps model's lines: P1 its own port; three part ports in the strip's copper slab, off the strip
    {"name": "P1", "kind": "lumped", "dir": "z", "start": [-5.0, -0.5, 0.0], "stop": [-5.0, 0.5, 0.5], "nodes": [],
     "part": False},
    {"name": "C1", "kind": "lumped", "dir": "y", "start": [2.0, 2.0, 0.5], "stop": [3.0, 1.0, 0.535], "nodes": [],
     "part": True},
    {"name": "L1", "kind": "lumped", "dir": "x", "start": [-1.0, 0.5, 0.5], "stop": [1.0, 1.5, 0.535], "nodes": [],
     "part": True},
    {"name": "R3", "kind": "lumped", "dir": "x", "start": [-3.0, 1.0, 0.5], "stop": [-2.0, 2.0, 0.535], "nodes": [],
     "part": True}]
VSPEC = {**TINY, "mesh": {a: LINES[k].tolist() for k, a in enumerate("xyz")}, "ports": VPORTS, "grid": []}
VPARTS = {"C1": {"ref": "C1", "value": "100pF"}, "L1": {"ref": "L1", "value": "15nH"}, "R3": {"ref": "R3", "value": "50R"}}
CBOX = {"C1": 2.4e-15, "L1": 2.7e-15, "R3": 1.4e-15}
STRIPS = [{"x": [-1.0, 0.0, 0.0, -1.0], "y": [1.0, 1.0, 1.25, 1.25], "z": [0.5, 0.535]},
          {"x": [0.25, 1.0, 1.0, 0.25], "y": [1.0, 1.0, 1.25, 1.25], "z": [0.5, 0.535]}]


def test_verify_moves_every_part_port_into_the_grid():  # spec 7.6, C-36 (owner-confirmed: C_part + C_box)
    v = verify_spec(VSPEC, VPARTS, CBOX, DUMPS / "operator_dump.vtr", DT)
    c1, l1, r3 = v["grid"]
    cell = c_box(DUMPS / "operator_dump.vtr", LINES, [0.0, 1.0, 0.5], [0.25, 1.25, 0.535], 0, DT)
    assert [q["name"] for q in v["ports"]] == ["P1"] and VSPEC["grid"] == [] and len(VSPEC["ports"]) == 4
    assert (c1["start"], c1["stop"], c1["R"], c1["C"]) == ([2.0, 2.0, 0.5], [3.0, 1.0, 0.535], None,
                                                           pytest.approx(100e-12 + 2.4e-15))
    assert (r3["R"], r3["C"]) == (50.0, None) and "L" not in c1 and "L" not in r3
    assert (l1["dir"], l1["start"], l1["stop"], l1["R"], l1["L"]) == ("x", [0.0, 1.0, 0.5], [0.25, 1.25, 0.535], None,
                                                                      15e-9)
    assert l1["C"] == pytest.approx(cell, rel=1e-12) and cell == pytest.approx(5.954e-15, rel=1e-3)
    assert v["metal"]["copper"][-2:] == STRIPS
    turned = {**VSPEC, "ports": [*VPORTS[:2], {**VPORTS[2], "start": [1.0, 0.5, 0.5], "stop": [-1.0, 1.5, 0.535]},
                                 VPORTS[3]]}  # the box starts at its higher end, as lpf915's L1 does
    t = verify_spec(turned, VPARTS, CBOX, DUMPS / "operator_dump.vtr", DT)
    assert (t["grid"][1]["start"], t["grid"][1]["stop"], t["metal"]["copper"][-2:]) == (
        [0.0, 1.0, 0.5], [0.25, 1.25, 0.535], STRIPS)


def test_verify_refuses_what_it_cannot_put_in_the_grid(tmp_path):  # C-36, C-37 (owner-confirmed: K_MAX 0.45)
    dump = DUMPS / "operator_dump.vtr"
    cases = [((VSPEC, {**VPARTS, "L1": {"ref": "L1", "value": "1pH"}}, CBOX, dump),
              ("E_VERIFY_K", {"ref": "L1", "k": "1.13", "limit": "0.45"})),
             ((VSPEC, {**VPARTS, "R3": {"ref": "R3", "value": "x"}}, CBOX, dump),
              ("E_VERIFY_VALUE", {"ref": "R3", "value": "x"})),
             ((VSPEC, {**VPARTS, "C1": {"ref": "C1", "value": "0pF"}}, CBOX, dump),
              ("E_VERIFY_VALUE", {"ref": "C1", "value": "0pF"})),
             ((VSPEC, VPARTS, {"L1": 2.7e-15, "R3": 1.4e-15}, dump), ("E_CBOX", {"ref": "C1", "value": "missing"})),
             ((VSPEC, VPARTS, CBOX, tmp_path / "none.vtr"), ("E_VERIFY_DUMP", {"path": str(tmp_path / "none.vtr")}))]
    for args, expected in cases:
        with pytest.raises(KrsError) as e:
            verify_spec(*args, DT)
        assert (e.value.code, e.value.params) == expected
    no_l = {**VSPEC, "ports": [q for q in VPORTS if q["name"] != "L1"]}
    assert K_MAX == 0.45 and len(verify_spec(no_l, VPARTS, CBOX, tmp_path / "none.vtr", DT)["grid"]) == 2
```

  `tests/test_model_csx.py`:

```python
def test_an_inductor_in_the_grid_is_letype_0_with_its_explicit_c(monkeypatch):  # spec 7.6, 11: never LEtype 1
    log = fake_openems(monkeypatch)
    build_csx({**TINY, "grid": [{**TINY["ports"][0], "name": "L1", "R": None, "C": 6e-16, "L": 1.5e-8}]}, 1, 1e-9)
    assert ("AddLumpedElement", ("lumped_0",), {"ny": 2, "caps": True, "C": 6e-16, "L": 1.5e-8}) in log
    assert not any("LEtype" in kw for _, _, kw in log)
```

  Test imports in `tests/test_model_spec.py`: `from kicad_rf_studio.core.model.readers import c_box`, `K_MAX` and `verify_spec` from `core.model.spec`, `from test_model_csx import TINY`, `from test_readers import DUMPS, LINES`.
- [ ] **Step 2: Run** `python -m pytest tests/test_model_spec.py tests/test_model_csx.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** `K_MAX`, `verify_spec` and build_csx's L. Messages:
  - `E_VERIFY_VALUE`: "verify puts each part in the grid at its value, but {ref} has \"{value}\": verify can place only a C, L or R whose value reads (a C above 0). For a C, L or R, set one with `retune PROJECT {ref}=VALUE`, then run verify again."
  - `E_VERIFY_DUMP`: "verify sizes each inductor's cell from the last run's operator dump {path}, which is missing. Run `run` again."
  - `E_VERIFY_K`: "Part {ref}: its inductor in the grid resonates too fast for the time step (k {k}, limit {limit}), and the run would diverge. Check its value in project.json; a real inductor reads k near 0.01."
- [ ] **Step 4: Run** the full suite. Expected: all pass (`test_a_grid_part_must_be_a_c_or_r_with_a_readable_value` still refuses the L).
- [ ] **Step 5: Commit.** `feat: verify's model: every part port in the grid, inductors as LEtype 0 with an explicit C and the k check`

---

### Task 12: `verify`

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py`, `src/kicad_rf_studio/core/post/outputs.py` (`grid_lines`), `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`
- Create: `tests/test_verify.py`

**Interfaces:**
- Consumes: `verify_spec` (Task 11); `results_of` (Task 10); `gate_lines`, `command_line` (Task 9); `layout`, `loads`, `terminate`, `z_part`, `compare`, `loss_budget`, `indicator_lines`, `touchstone`, `port_map`, `write`, `VERIFY_OUTPUT`, `LIMITS`; `port_value`, `part_kind`; `stoprule.PRESETS`; plan 3's `prepare`, `setup_gate`, `cost_notes`, `classify_job`, `records`.
- Produces:
  - `pipeline.simulate(model: Model, project: dict, run_dir: Path) -> tuple[list[dict], dict, float] | None`: `_run`'s job phase, moved in Step 1: prepare; the setup gate with its blocking gates, its warnings and `gate_lines`, then None when it blocks; else `I_GATES_PASSED`, `gate_lines`, the cost lines, the jobs under the stop rule at the project's preset, each verdict event followed by `gate_lines`, and the calibration's speed refreshed; returns (the jobs as `results` records them, setup.json, the job phase's wall time). `_run` keeps everything before `prepare`, then the results save (now after the speed refresh), `I_RESULTS` or `W_RUN_NOT_KEPT` and the output step.
  - `outputs.grid_lines(grid: list[dict], values: dict[str, str]) -> list[str]`: one port-map line per grid entry named in `values`: `in grid: {ref} {value} as C {C:.6g} F (value + C_box)`, `… as R {R:g} ohm`, `… as L {L:.6g} H with the cell's C {C:.6g} F`.
  - `pipeline.verify(path: Path) -> int` (spec 3.2, 7.6, C-36..C-38): before the lock (`read_project`), `E_VERIFY_NO_PARTS` when no part is a port or curve_port, `E_VERIFY_CURVE {ref}` for the first curve_port, `E_NO_RESULTS`; then as `run`: `run_dir_for`, the project lock, the run folder, a `KrsError` inside a message event and 2:
    1. `W_FILLS_AS_SAVED` and `load`'s notes, `stops`; `build_model`, a blocked mesh gate → 3; `results = results_of(project, model)`; `lay = layout(project, results)`.
    2. `ps = parts(project)`; `vspec = verify_spec(model.spec, ps, results["c_box"], Path(results["run_dir"]) / "job-0-setup" / "operator_dump.vtr", results["dt"])`; refs and ext as in `write_outputs`; `zk = loads({r: z_part(part_kind(r), port_value(r, ps[r]["value"]), None, lay.f) for r in refs}, refs, results["c_box"], lay.f)` (the ideal values, model and s2p ignored, C-38) — every refusal before any job.
    3. `out = simulate(replace(model, spec=vspec), project, run_dir)`: None → 3; `done, _, wall = out`; a job outside KEPT → `W_VERIFY_NOT_KEPT {kept, runs, wall: duration(wall), folder}` and 4, nothing stored.
    4. `own = layout(project, {"run_dir": str(run_dir), "jobs": done})`; `retuned = terminate(lay.s, ext, zk, lay.f)`; k0 = `lay.markers[0]`; `cmp = compare(own.s, retuned, lay.f, k0, 10 * max(PRESETS[results["preset"]][1], PRESETS[project["preset"]][1]))` (the noisier of the run's and verify's own preset sets the floor).
    5. `write(path.parent / "results", {f"verify.s{P}p": touchstone(own.s, own.f, [q["name"] for q in own.ports], port_map(project, {**results, "run_dir": str(run_dir), "jobs": done, "preset": project["preset"]}, own, list(range(P))) + grid_lines(vspec["grid"], values))}, VERIFY_OUTPUT, command_line("kicad-rf-studio", "verify", str(path)))`, then `project.json`'s `verify = {"model_hash": spec_hash(vspec), "base_hash": results["model_hash"], "values": {ref: value text}, "run_dir": str(run_dir), "jobs": done, "compare": cmp}` (reloaded under the lock; `results` untouched).
    6. Result events: `I_VERIFY_RESULTS {runs, wall, path}`; `I_VERIFY_COMPARE {f0_mhz (:g), a_db (own.a_db[k0], :.1f), ds21_db (:.3f), ds11 (:.4f), ds_max (:.4f)}`; per null `I_VERIFY_NULL {f_mhz (:.1f), a_db (own.a_db at the grid point nearest the null, :.1f), shift_pct (100·shift :+.2f)}` or `W_VERIFY_NULL_UNMATCHED {f_mhz, a_db}`, or `I_VERIFY_NO_NULLS`; `indicator_lines(own.f, own.a_db, own.s, loss_budget(own.s, ext_own, empty) if P == 2 else None, results["loss_expected"])` with `ext_own = list(range(P))` and `empty = np.zeros((len(own.f), 0))` (P_parts = 0, C-38); `I_OUTPUTS`; `I_VERIFY_SCOPE`; LIMITS. Returns 0.
  - The command `kicad-rf-studio verify PROJECT`, `pipeline.verify(pipeline.project_path(a.project))`; cli's docstring names `verify`.

- [ ] **Step 1: Move run's job phase into `simulate`.** As the Interfaces say; `limits()` becomes `gate_lines(gates)` emitted where it stood. Run `python -m pytest tests/test_run.py tests/test_cli_cost.py -q`. Expected: PASS, the tests unchanged. Commit: `refactor: share run's job phase as pipeline.simulate`.
- [ ] **Step 2: Write the failing tests** in `tests/test_verify.py`:

```python
F, _ = grid(915e6, 3, 1.1)


def verified(tmp_path, monkeypatch):
    """lpf915 run on the network fake, its run's operator dump stood in for (the fake writes none) and the cell C
    read as 6e-16 F: the project file."""
    pj = lpf_run(tmp_path, monkeypatch)  # tests/test_run.py
    (Path(load_project(pj)["results"]["run_dir"]) / "job-0-setup" / "operator_dump.vtr").write_bytes(b"")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    return pj


def test_verify_runs_the_parts_in_the_grid_and_compares(tmp_path, calibrated, monkeypatch, capsys):  # spec 7.6
    pj = verified(tmp_path, monkeypatch)
    before = load_project(pj)["results"]
    assert main(["verify", str(pj)]) == 0
    d = load_project(pj)
    v = d["verify"]
    assert d["results"] == before and v["base_hash"] == before["model_hash"] != v["model_hash"]
    assert set(v) == {"model_hash", "base_hash", "values", "run_dir", "jobs", "compare"}
    assert v["values"] == {"C1": "100pF", "L1": "15nH", "C2": "3.3pF", "C3": "3.3pF"}
    assert [(j["port"], j["verdict"]) for j in v["jobs"]] == [("P1", "converged"), ("P2", "converged")]  # C-38: P jobs
    model = json.loads((Path(v["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    assert [g["name"] for g in model["grid"]] == ["C1", "L1", "C2", "C3"] and [q["name"] for q in model["ports"]] == [
        "P1", "P2"]
    assert (model["grid"][0]["C"], model["grid"][1]["L"], model["grid"][1]["C"]) == (
        pytest.approx(100e-12 + C_BOX), 15e-9, 6e-16)
    retuned = terminate_np(star(F, 6), [0, 1], lpf_loads(None))  # ideal values ∥ C_box (C-38)
    assert v["compare"]["ds_max"] == pytest.approx(np.abs(star(F, 2) - retuned).max(), abs=1e-4)
    file = pj.parent / "results" / "verify.s2p"
    assert np.abs(read_s(file) - star(F, 2)).max() <= 1e-5
    assert b"in grid: L1 15nH as L 1.5e-08 H with the cell's C 6e-16 F" in file.read_bytes()
    assert result_codes(v["run_dir"]) == ["I_VERIFY_RESULTS", "I_VERIFY_COMPARE", "I_VERIFY_NO_NULLS", "I_PASSIVITY",
                                          "I_RECIPROCITY", "W_LOSS_BUDGET", "I_OUTPUTS", "I_VERIFY_SCOPE", *LIMITS]
    assert (pj.parent / "results" / "chain.s2p").is_file()  # retune's files stay


def test_verify_stores_nothing_when_a_job_keeps_no_s(tmp_path, calibrated, monkeypatch):  # C-38
    pj = verified(tmp_path, monkeypatch)
    monkeypatch.setenv("KRS_FAKE", "nan")
    assert main(["verify", str(pj)]) == 4 and "verify" not in load_project(pj)


@pytest.mark.parametrize("case", ["no results", "single trace", "rotated"])
def test_verify_refuses_before_any_run(tmp_path, calibrated, capsys, case):  # C-36
    if case == "no results":
        pj, line = lpf_project(tmp_path), render("E_NO_RESULTS")
    elif case == "single trace":
        pj, line = coupon(tmp_path), render("E_VERIFY_NO_PARTS")
    else:
        out = tmp_path / "lpf915-45"
        assert main(["new", str(FIX / "lpf915-45.kicad_pcb"), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz",
                     "-o", str(out)]) == 0
        pj = out / "project.json"
        save_project(pj, {**load_project(pj), "allow_curve_port": True, "lid_height_mm": 2.5})
        line = render("E_VERIFY_CURVE", ref="L1")
    capsys.readouterr()
    assert main(["verify", str(pj)]) == 2 and capsys.readouterr().err == line + "\n"
    assert not (calibrated / "runs").exists()


@pytest.mark.parametrize(("edit", "line"), [
    ({"t_max_s": 30e-9}, render("E_RESULTS_STALE")),
    ("value", render("E_VERIFY_VALUE", ref="C2", value="x"))])
def test_verify_refuses_stale_results_and_unreadable_values(tmp_path, calibrated, monkeypatch, capsys, edit, line):
    pj = verified(tmp_path, monkeypatch)
    d = load_project(pj)
    if edit == "value":
        parts(d)["C2"]["value"] = "x"  # not in the model hash
    else:
        d.update(edit)
    save_project(pj, d)
    capsys.readouterr()
    assert main(["verify", str(pj)]) == 2 and line in capsys.readouterr().out.splitlines()
    assert "verify" not in load_project(pj)
```

  Test imports: `json`, `Path`, `numpy as np`, `pytest`; `main`; `render`; `from kicad_rf_studio.core.model import spec as spec_module`; `load_project`, `parts`, `save_project` from `core.project`; `grid` from `core.post.waves`; `LIMITS` from `core.post.outputs`; `from networks import C_BOX, read_s, star, terminate_np`; `from test_cli_cost import FIX`; `from test_run import coupon, lpf_loads, lpf_project, lpf_run, result_codes`.
- [ ] **Step 3: Run** `python -m pytest tests/test_verify.py -q`. Expected: FAIL (`invalid choice: 'verify'`).
- [ ] **Step 4: Implement** `grid_lines`, `verify` and the command. Messages:
  - `E_VERIFY_NO_PARTS`: "This project has no part ports (a single trace), so verify has nothing to put in the grid: `run` is already its full simulation."
  - `E_VERIFY_CURVE`: "Part {ref} is rotated (a CurvePort), and verify cannot put a rotated part in the grid. Rotate it in KiCad to a multiple of 90° to verify this chain."
  - `W_VERIFY_NOT_KEPT`: "{kept} of {runs} verify jobs kept S, in {wall}, so nothing was compared or stored. The verdicts above, also in {folder}, say why; fix that and run `verify` again."
  - `I_VERIFY_RESULTS`: "{runs} verify jobs kept S, in {wall}; the comparison is stored in {path}."
  - `I_VERIFY_COMPARE`: "verify against the retune at the same ideal values: |ΔS21| {ds21_db} dB and |ΔS11| {ds11} at f0 = {f0_mhz} MHz (|a| {a_db} dB); max |ΔS| {ds_max} up to f2."
  - `I_VERIFY_NULL`: "Null of |S21| at {f_mhz} MHz in verify (|a| {a_db} dB): null shift {shift_pct} % against the retune's."
  - `W_VERIFY_NULL_UNMATCHED`: "Null of |S21| at {f_mhz} MHz in verify (|a| {a_db} dB) has no match within ±5 % in the retune. Compare the verify and chain Touchstone files in results/."
  - `I_VERIFY_NO_NULLS`: "No null of |S21| stands 20 dB out of the response, so there is no null shift to report."
  - `I_VERIFY_SCOPE`: "verify checks the layout reduction, not the vendor part data: each part sat in the grid at its ideal value, against a retune at the same values. Its loss budget counts a resistor's loss in the grid as layout loss."
- [ ] **Step 5: Run** the full suite. Expected: all pass.
- [ ] **Step 6: Commit.** `feat: verify: one full run with the parts in the grid, compared with a retune (spec 7.6)`

---

### Task 13: Real openEMS waves: the fixture and the openems tests

**Files:**
- Create: `tests/test_post_real.py`, `tools/make_waves.py`, `tests/fixtures/microstrip/job-1.npz`, `tests/fixtures/microstrip/job-2.npz`, `tests/fixtures/microstrip/meta.json`

**Interfaces:**
- Consumes: `runs.run_dir_for`, `write_spec`, `job_dir`, `write_job`, `run_jobs`, `check_job`, `load_settings`; `excitation`, `kappa`; `read_stats`; `s_matrix`, `kappa_eq`, `grid` (Task 1); `sigma_max`, `recip_err` (Task 5); `verify_spec` (Task 11); `tests/test_worker.write_job`.
- Produces: `tools/make_waves.py` (dev-time, SPDX header; it imports nothing from `tests/` and no openEMS or CSXCAD: it writes a model spec and starts the worker as a subprocess, which needs openEMS):
  - `rect(x0, x1, y0, y1, z0, z1) -> dict` = `{"x": [x0, x1, x1, x0], "y": [y0, y0, y1, y1], "z": [z0, z1]}`.
  - `microstrip(t_max: float) -> dict`: tools/make_dumps.py's microstrip as a model spec: lines x `np.arange(-8, 8.001, 0.25)`, y `np.arange(-4, 4.001, 0.25)` (rounded to 1e-6), z `[-1, -0.5, 0, 0.125, 0.25, 0.375, 0.5, 0.535, 0.6, 0.75, 1, 1.5, 2, 2.5, 3, 3.5]`; `excitation({"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "t_max_s": t_max})`; one material `substrate_0` (eps 4.3, `kappa(4.3, 0.02, 915e6)`, priority 10, `rect(-8, 8, -4, 4, 0.0, 0.5)`); metal copper `rect(-8, 8, -4, 4, -0.5, 0.0)` (a ground slab: a model spec has no zero-thickness sheet) and `rect(-5, 5, -0.5, 0.5, 0.5, 0.535)`, no lid, cylinders or curves; ports P1 at x = −5 and P2 at x = 5, each `{"kind": "lumped", "dir": "z", "start": [x, -0.5, 0.0], "stop": [x, 0.5, 0.5], "nodes": [[x, 0, 0], [x, 0, 0.5], [x, 2, 0], [0, 0, 0.535]], "part": True}` (so the setup job dumps the operator); `grid` [].
  - `main(out: Path = <repo>/tests/fixtures/microstrip, t_max: float = 15e-9) -> None`: a run folder `runs.run_dir_for("make_waves")` (never the system temp), `write_spec`, jobs `job-0-setup` (port 1, "setup") and `job-1-P1`, `job-2-P2` ("run"), 4 threads, `run_jobs(jobs, 3, …)`, `check_job` on each; copies each run job's `waves.npz` to `out/job-{k}.npz`; writes `out/meta.json` = `{"dt": openEMS_stats.txt's exact dt of job 1, "c_box": setup.json's c_box["P1"], "f0_hz": 915e6, "band": [f1, f2]}`. `python tools/make_waves.py [OUT] [T_MAX]`.

- [ ] **Step 1: Write the failing tests** in `tests/test_post_real.py`:

```python
REAL = Path(__file__).parent / "fixtures" / "microstrip"
F, _ = grid(915e6, 3, 1.1)


def make_waves():
    """tools/make_waves.py's functions, loaded by the openems tests only (main does not run)."""
    return runpy.run_path(str(Path(__file__).parents[1] / "tools" / "make_waves.py"))


def real_records(folder=REAL):
    return [tuple(np.load(folder / f"job-{k}.npz")[x] for x in ("t_u", "u", "t_i", "i")) for k in (1, 2)]


def run_worker(job):
    with open(job / LOG, "wb") as out, open(job / ERR, "wb") as err:
        return subprocess.run([sys.executable, "-I", "-u", "-m", "kicad_rf_studio.worker", "job.json"], cwd=job,
                              stdout=out, stderr=err, env={**os.environ, "OPENBLAS_NUM_THREADS": "1"}).returncode


def test_the_reduction_on_real_openems_waves():  # C-41, spec 9.1 tier (a); r6 §11
    meta = json.loads((REAL / "meta.json").read_text(encoding="utf-8"))
    rec = real_records()
    S, A = s_matrix(rec, F)
    assert meta["band"] == pytest.approx([457.5e6, 3.0195e9]) and meta["c_box"] == pytest.approx(2.3796e-14, rel=1e-3)
    assert np.abs((rec[0][2] - rec[0][0]) / meta["dt"] - 0.5).max() <= 1e-5  # currents half a timestep late
    assert recip_err(S).max() <= 1e-5 and sigma_max(S).max() <= 1.0 and kappa_eq(A).max() <= 1.05
    assert np.degrees(np.angle(S[71, 1, 0])) == pytest.approx(-21.12, abs=3.0)
    assert S[0, 1, 0].real > 0  # X-6: the lumped ports' sign, a thru reads positive near f1
    assert np.abs(s_matrix([(t, u, t, i) for t, u, _, i in rec], F)[0] - S).max() > 1e-4  # the half step counts
    shortcut = (S @ A) / np.diagonal(A, axis1=1, axis2=2)[:, None, :]  # b/a, the stop-rule monitor's form
    assert np.abs(shortcut - S).max() > 1e-3


@pytest.mark.openems
def test_the_waves_tool_and_the_lumped_port_order_on_real_openems(tmp_path, monkeypatch):  # C-41, X-6; about 70 s
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    tool = make_waves()
    tool["main"](tmp_path / "out", 5e-9)
    rec = real_records(tmp_path / "out")
    S = s_matrix(rec, F)[0]
    assert S[0, 1, 0].real > 0 and recip_err(S).max() <= 1e-5
    spec = tool["microstrip"](5e-9)
    p2 = spec["ports"][1]
    spec["ports"][1] = {**p2, "start": p2["stop"], "stop": p2["start"]}  # P2's box from its signal end down
    job = write_job(tmp_path, spec, "run")  # port 1 excited, as job-1.npz
    assert run_worker(job) == 0
    rev, (_, u, _, i) = np.load(job / "waves.npz"), rec[0]
    n = min(u.shape[1], rev["u"].shape[1])
    # openEMS keeps a lumped box's given order, so P2 now reads −u and −i (Task 2's flipped() relies on it)
    assert np.abs(rev["u"][1, :n] + u[1, :n]).max() <= 1e-6 * np.abs(u[1]).max()
    assert np.abs(rev["i"][1, :n] + i[1, :n]).max() <= 1e-6 * np.abs(i[1]).max()


@pytest.mark.openems
def test_verifys_grid_elements_run_stable(tmp_path):  # spec 7.6, C-36, C-37, C-41; about 45 s
    spec = make_waves()["microstrip"](5e-9)
    spec["ports"] = [{**q, "part": False} for q in spec["ports"]] + VPORTS[1:]  # tests/test_model_spec.py
    v = verify_spec(spec, VPARTS, CBOX, DUMPS / "operator_dump.vtr", DT)  # the L cell sits on the substrate's top
    assert [g["name"] for g in v["grid"]] == ["C1", "L1", "R3"] and [q["name"] for q in v["ports"]] == ["P1", "P2"]
    job = write_job(tmp_path, v, "run")
    assert run_worker(job) == 0
    u = np.load(job / "waves.npz")["u"]
    assert np.isfinite(u).all() and np.abs(u[:, 3 * u.shape[1] // 4:]).max() < 0.5 * np.abs(u).max()  # no growth
```

  Test imports: `json`, `os`, `runpy`, `subprocess`, `sys`, `Path`, `numpy as np`, `pytest`; `from kicad_rf_studio import runs`; `from kicad_rf_studio.worker import ERR, LOG`; `verify_spec` from `core.model.spec`; `recip_err`, `sigma_max` from `core.post.checks`; `grid`, `kappa_eq`, `s_matrix` from `core.post.waves`; `from test_model_spec import CBOX, DT, VPARTS, VPORTS`; `from test_readers import DUMPS`; `from test_worker import write_job`.
- [ ] **Step 2: Run** `python -m pytest tests/test_post_real.py -q`. Expected: FAIL (`tests/fixtures/microstrip/meta.json` missing; the openems tests, where openEMS imports, fail on the missing `tools/make_waves.py`).
- [ ] **Step 3: Write the tool and generate the fixture.** Write `tools/make_waves.py` as the Interfaces fix it, then run `python tools/make_waves.py` (about 1–2 minutes). Expected: `tests/fixtures/microstrip/` holds `job-1.npz` and `job-2.npz` (about 18 KB each, members t_u, u, t_i, i) and `meta.json`.
- [ ] **Step 4: Stage and check privacy.** `git add tools/make_waves.py tests/fixtures/microstrip tests/test_post_real.py`, then `python tools/privacy_gate.py --staged --generic-only`. Expected: no hit, and `git status` shows the three fixture files staged (`.gitignore` ignores none of them).
- [ ] **Step 5: Run** `python -m pytest tests/test_post_real.py -q`, then `python -m pytest -m openems tests/test_post_real.py -q`. Expected: PASS. If the tier (a) test fails on a regenerated fixture, compare with the research run (∠S21 at f0 −21.12°, reciprocity 3.9e-7, σ_max ≤ 0.99993, κ_eq ≤ 1.0196, half step 1.52e-3, b/a shortcut 1.02e-2) before touching a tolerance. If P2's reversed waves are not negated, or the in-grid run grows or goes non-finite, never loosen the assertion: stop and report it, because Task 2's `flipped()` (reversed lumped boxes) or C-36's explicit C (the uneven C/Npar split of an L cell on a dielectric interface) then needs an owner decision.
- [ ] **Step 6: Run** the full suite and `python -m pytest -m openems -q`. Expected: all pass.
- [ ] **Step 7: Commit.** `test: a real openEMS waves fixture and the openems-tier checks of the reduction, the port order and the in-grid elements`

---

## Not in this plan

- **Plan 5:** the "relative / what-if" label and the P0 harnesses, limits and reports: verify against retune in P0-B and P0-C, the 45° twin, n = 2 against n = 3, the EMerge cross-check (its N-port recombined through `chain.terminate`), P0-D; the empty-box C_box check (R-62), which closes the open part with zk = 1/(jω·C_box) through `terminate` as it stands; tightening σ_max, reciprocity and the loss limit; confirming the package presets, K_MAX and C_box against an empty box, which also sizes r6's port-measurement offset beyond C_box (−7 fF and −13 pH on the test box) and verify's own differences from the retune (below); CI tier (b) nightly, which reuses this plan's openems tests; the stopped-run hygiene of run folders (et and ht files, up to 32 MB a job).
- **Neither plan (spec §10):** E12/E24 snapping (Stage 2); §7.7 complex targets; the pt-BR catalog; 3-port switch-state assembly; the reciprocity least-squares fit.
- **Deferred (C-43):** board-order hash stability, so a re-saved board that only reorders elements reads as stale (P-3; it errs safe, and E_RESULTS_STALE names a re-save); lazy CLI imports; verify's reuse by its own hash (verify always runs); summaries for P ≠ 2 (W_NOT_TWO_PORT; verify compares the first two ports' S21 and S11 and skips the loss budget); a cache of the stale check for Stage 2 (1.2–3.2 s per retune on lpf915); run-folder size.
- **Deferred SHOULDs:** validating `results` field by field (P-7; `results_of` checks presence, the hash and `loss_expected`); two parts sharing a ref in a hand-edited project.json (R-16; the last wins); `W_BOARD_CHANGED` in retune (P-11; a change that alters the model is refused as stale); MPLCONFIGDIR (matplotlib writes its font cache under the user's home on the first PNG); an S2P reciprocity warning (YAGNI, C-14); a warning for an S2P path stored absolute across drives; a finiteness check of S before writing (only a C of 0 could make it NaN, and it is refused).
- **Known limits:** the expected dielectric loss is a lower bound (straight, axis-aligned sections only: staircased tracks, pads and vias add nothing); the null shift carries about 1 % of noise at Normal on a −48 dB notch (r6) and lpf915 has no in-band null; one DFT kernel assumes every job samples the same instants; K_MAX was measured on a uniform grid with equal edges at openEMS's own dt, while an L cell on a dielectric interface gets C/Npar on edges whose natural C differs (59 % of it on the substrate side of the test microstrip's cell, which Task 13's openems test runs); verify's inductor cell capacitance is not the port's C_box, and its PEC strips add series inductance across the pad gap (a few tenths of a nH by estimate on lpf915's L1) that the retune has not; verify's loss budget counts an in-grid R's loss as layout loss (P_parts = 0, C-38); a refused write leaves the files replaced before it with their new contents (the summaries go first); the ideal schematic grounds the GND and power nets only and floats any other net off the chain; the flat and t_max flags reach the Touchstone files as comments and the console as lines, not the CSV or PNG.
