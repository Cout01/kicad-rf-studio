# Stage 4 Plan 1: The Pins and the Engine's SI Hooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin every antenna fixture's models and outputs, and v1's 2D readouts, byte for byte, then add the engine's signal-integrity hooks (schema 3, cs2d's coupled pair, the TDR, the dielectric next to each layer, the SI mesh rule, the vertical port, the DC pulse with its stop window, the Debye dielectric), each a pure function that no v1 or antenna path calls, and prove them with gate P4-A in CI, whose tool holds the even/odd 4-port model.

**Architecture:** Task 1 records sha256 digests of what the seven antenna fixtures build and write at `037bc4b`, and of v1's 2D readouts, beside v1's pins, before any shared code changes; every later task keeps both pin sets green. Each SI hook is a new function, or an optional argument whose default is today's behaviour: cs2d's `pair` calls `solve` three times and changes nothing in it, `substrate_h(layers=())`, `xy_lines(max_cell=None)`, `End.ref_layer=None`, an excitation's optional `window_s`, a material's optional `"debye"`; plan 2 wires them into an SI project. Gate P4-A is `tools/p4a.py`, which holds Cohn's formula and the even/odd 4-port as reference models and checks cs2d's pair against Cohn and Kirschning–Jansen, the 4-port's identities and the TDR against references committed as JSON; `tests/test_p4a.py` runs it in CI, and Task 10 records it.

**Tech Stack:**
- Python ≥ 3.11 (dev venv 3.14.2), numpy, scipy (`optimize.nnls`, `special.ellipk`) and shapely, all already dependencies.
- openEMS 0.37.0 and CSXCAD 0.7.0, only in the worker: `CSXCAD.CSProperties.CSPropDebyeMaterial`, imported inside `build_csx`'s Debye branch.
- pytest, `tests/test_model_csx.fake_openems`, `tests/networks.py` and `tools/p0.py`.

**Spec:**
- `docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md` (binding): §5.12 item 1, with §2–§4, §5.1, §5.3–§5.6, §5.9, §5.11 and §5.13.
- The Stage 1 spec, `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, where the design reuses it: §3.1, §5.1, §5.3–§5.6 (C-14), §5.8, §6.3, §6.4, §9 and §10.
- Task 10 lands A-41 (§2), A-42 (§5.3, and §10's Debye line), A-43 (§5.4), A-44 (§5.6), A-45 (§5.8), A-46 (§6.3) and A-47 (§9.10), with their exact text.
- Research (git-ignored) is in `.superpowers/sdd/stage4-research/`: r1 (the probes), r3 (the engine) and r4 (the references). openEMS-Project's v0.37.0 sources show where a Debye pole sits on the Yee edges (`FDTD/extensions/operator_ext_debyematerial.cpp`), against the static ε's quarter-cell average (`FDTD/operator.cpp`, `AverageMatQuarterCell`).

**Branch:** `stage4-plan1`, from `main` at `037bc4b`. This plan is `docs/superpowers/plans/2026-11-02-stage4-plan1-pins-and-si-hooks.md`. Commands run from the repo root with `.venv/Scripts/python`. Line references are `main`'s at `037bc4b`; if an earlier task moved a line, find it by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage4-plan1 main`. Then `git diff --stat 037bc4b HEAD -- src tests tools po pyproject.toml` must print nothing.
2. Commit this plan on the branch.
3. After Task 10: the whole-branch review, a local fast-forward merge into `main`, and delete the branch. Nothing is pushed.

## Global Constraints

- **v1 and the antenna byte for byte** (design §3, §4): v1 projects stay at schema 1 and antenna projects at schema 2. Their model specs, `spec_hash`, `model.json` bytes, verify's model, `project.json`, `new`'s lines, the 2D readout and `results/` files stay as built at `037bc4b`. Task 1 pins the antenna fixtures, and v1's 2D readouts, which v1's Stage 3 pins lack, before any shared change. No task re-records a pin.
- **SI keys only in SI specs:** an excitation's `"window_s"` and `"flat_s"` with `f1` 0 (`dc_pulse`), a material's `"debye"` and a port with `"dir": "z"` (`vertical`) come only from this plan's SI functions, which no v1 or antenna path calls. A wiring slip in plan 2 that leaks one into a v1 or antenna spec moves its hash, which Task 1's pins, run by every later task, catch.
- **MUR on all six faces for SI** (Stage 1 §5.1): an SI spec never holds `"boundary"`. Copper is solid, never openEMS's conducting sheet. v1's constant κ never goes into an SI spec (design §3).
- **openEMS stays in the worker** (Stage 1 §3.1): the CLI, the orchestrator, `core.cs2d` and `core.post` never import openEMS or CSXCAD. `build_csx` imports `CSXCAD.CSProperties` inside its Debye branch only.
- **Messages:** every new user-facing string is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, compiled with `.venv/Scripts/python tools/catalog.py` in the same task, by the pt-BR design's §6.1 glossary. This plan adds none: its refusals are E_PORT_BOX and ValueErrors that plan 2 turns into messages. Numbers keep the decimal point.
- **Tests:** test-first. Tier (a) tests never run openEMS, KiCad, the network or a build. `KrsError` tests check `.code` and `.params`, and csx tests use `fake_openems`.
- **Isolation:** tests never touch a real KiCad folder, the Documents folder, KiCad's settings or the real data folder. Task 10's tool writes under `$env:TEMP`, outside every work tree.
- **Full suite** before every commit: `.venv/Scripts/python -m pytest -q`, about 21 minutes (2081 passed and 6 skipped at `037bc4b`). Run it once, in the background, with nothing beside it, and wait for it to exit.
- **Git:** no push. The pre-commit privacy gate runs on every commit; never use `--no-verify`. No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name. No commit message carries a co-author line; use the messages as given.
- **Files:** every new `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`. Code and docs are in English.
- **Python** only with a script, `-c` or `-m`: never a bare interactive `python`, least of all in a background shell.
- **Workflow:** `graphify query "<question>"` before reading code, and `graphify update .` after each commit. Ponytail: the laziest solution that works, in the fewest files, with a `ponytail:` comment naming the ceiling on each corner cut. Reuse cs2d's `solve`, golden_v1's `sha`, `env` and `record`, `networks.synth_records`, the stop rule, `p0`'s report helpers, `fake_openems` and `kicad_lines`.

## Review Focus

1. **A pair that is not a pair in cs2d:** unequal widths or z spans, a lone line, three lines, legs that share a mesh node, or a leg that given lines miss (plan 2's fit2d passes the mesh lines). Even and odd modes need mirror-image legs, a shared node is a short the FDTD model would make, and a missed leg would read a lone line as the pair's modes. Checks: Task 2's `test_a_pair_is_two_mirror_image_lines_that_never_share_a_node`; the stripline in `test_a_coupled_stripline_against_cohn_at_thin_copper`.
2. **A TDR from S on a grid that does not start at DC, or a sum started at t = 0.** The first reads garbage silently; the second reads half the step (55 Ω for 60, r1). Checks: Task 3's `test_the_tdr_needs_a_uniform_grid_from_dc` and `test_the_tdrs_sum_starts_before_t_0`.
3. **A via span that overlaps an edge's pattern or ends inside its cells.** Plan 2 puts a span on every via at a track's end or bend, where the edges' patterns already lie. A span end within d/3 of an edge's line must merge into it, and the edge lint, RATIO and the d/3 merge must still hold. Checks: Task 5's `test_the_si_rule_fills_a_via_margin_at_d_clear_of_or_over_an_edge`.
4. **A vertical port over the wrong plane:** no copper, an antipad or a split under the pad, copper of a signal net, or another net's copper on a layer between the pad and the plane. Two cases must still find their plane: a plane that the copper pipeline's hole cut (`split_holes`) left in abutting pieces, none of which covers the pad alone, and a plane behind a layer bare under the pad (design §5.5's nearest plane). Checks: Task 6's `test_the_plane_under_a_pad_is_the_nearest_one_nets_copper_that_covers_it`, `test_a_pad_with_no_plane_under_it_has_no_vertical_port` and `test_a_vertical_port_needs_a_mesh_line_inside_its_pad`.
5. **A DC pulse whose port residual cannot fall** (a floating piece's charge holding a port's level) **or that is still travelling on a long line.** The first must end flat, or at T_max where T_max comes first (a route under about 37 mm at εeff 3.3), never converged; the second must not converge before the far port has seen the pulse. Their test records hold the log energy, as openEMS's does under the DC pulse (r1): the ports' own power falls to 0 between the pulses, which the growth detector reads as growth. Checks: Task 7's `test_a_port_level_the_dc_pulse_leaves_behind_ends_flat_not_converged` and `test_a_pulse_still_travelling_on_a_long_line_never_reads_as_converged`.

Two more input classes are pinned in their own tasks: a stripline whose dielectrics above and below differ (Task 4), and a Debye fit with a negative pole or an ε∞ under 1 (Task 8).

---

## File structure

```
tools/golden_v1.py, tools/golden_antenna.py, tests/test_golden_antenna.py, tests/fixtures/golden_antenna.json  # T1
src/kicad_rf_studio/core/cs2d.py, tests/test_cs2d.py, tests/kicad_lines.py                                    # T2
tools/p4a.py                                      # T2 cohn and the cross-sections; T3 even_odd_s; T9 the gate
src/kicad_rf_studio/core/post/si.py, tests/test_post_si.py, core/post/__init__.py                             # T3
src/kicad_rf_studio/core/project.py, tests/test_project.py                                                    # T4
src/kicad_rf_studio/core/geometry/zstack.py, tests/test_geometry_region.py                                    # T4
src/kicad_rf_studio/core/geometry/region.py, src/kicad_rf_studio/core/mesh/rule.py, tests/test_mesh_rule.py    # T5
src/kicad_rf_studio/core/model/ports.py, tests/test_model_ports.py                                            # T6
src/kicad_rf_studio/core/model/spec.py                         # T7 dc_pulse, round_trip, si_t_max; T8 debye
src/kicad_rf_studio/stoprule.py, tests/test_stoprule.py                                                       # T7
tests/test_model_spec.py, tests/test_model_csx.py                                                             # T7, T8
src/kicad_rf_studio/core/model/csx.py                                                                         # T8
tests/test_p4a.py, tests/fixtures/p4a/references.json                                                         # T9
docs/validation/<date>-p4-a.md and .json; the Stage 1 spec                                                    # T10
```

---

### Task 1 [code]: Golden pins on the antenna fixtures and v1's 2D readouts

**Files:**
- Create: `tools/golden_antenna.py` and `tests/test_golden_antenna.py`.
- Modify: `tools/golden_v1.py`: `main`'s body becomes `record`.
- Written by the tool: `tests/fixtures/golden_antenna.json`.

**Interfaces:**
- Consumes:
  - `golden_v1.sha(data: bytes) -> str`, `golden_v1.env() -> list` and `golden_v1.CASES`; `p0.FIX`, `p0.ROOT` and `p0.code_id()`.
  - `cli.new_antenna` and `cli.new`; `pipeline.load`, `build_model`, `readout_2d(geom)`, `expected_loss(geom, f0)` and `write_outputs(path, project, command)`.
  - `runs.write_spec`, `spec_hash`, `verify_spec(spec, parts, dump, dt, *, far_field)`, `far_field_box`, `parts` and `GATES`.
  - `networks.star(f, n)` and `networks.synth_records(s_of, n, f1, f2, dt, t_rec)`.
- Produces:
  - `golden_v1.record(golden: Path, digests: Callable[[], dict]) -> int`, which `golden_v1.main()` now calls.
  - `golden_antenna.GOLDEN`, `BANDS` and `TRACED`; `golden_antenna.digests() -> dict`, called with an empty folder as the working directory; `golden_antenna.main() -> int`.

- [ ] **Step 1: Write the failing test,** `tests/test_golden_antenna.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os

import golden_antenna
import golden_v1
import pytest

GOLDEN = json.loads(golden_antenna.GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def now(tmp_path_factory):
    home = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("golden_antenna"))  # relative paths only, so no byte holds this machine's folders
    try:
        return golden_antenna.digests()
    finally:
        os.chdir(home)


def test_the_antennas_build_byte_for_byte_what_they_did_at_037bc4b(now):  # Stage 4 design 3, 4, 5.12 item 1
    assert set(now["models"]) == set(golden_antenna.BANDS) and "verify" in now["models"]["ifa2g4_pi"]
    # an antenna's model spec, its hash, the pi's verify model, project.json, new's lines or a blocking gate moved
    assert now["models"] == GOLDEN["models"]


def test_the_antennas_outputs_and_the_2d_readouts_are_byte_for_byte_what_they_were_at_037bc4b(now):  # design 3, 4
    assert set(now["outputs"]) == set(golden_antenna.BANDS) | set(golden_v1.CASES)
    assert set(now["outputs"]["ifa2g4"]) == {"readout", "layout.s1p", "farfield.csv", "antenna_summary.csv",
                                             "antenna_summary.png", "lines"}
    assert set(now["outputs"]["ifa2g4_pi"]) == {"readout", "layout.s4p", "chain.s1p", "antenna_summary.png", "lines"}
    assert all(set(now["outputs"][name]) == {"readout"} for name in golden_v1.CASES)  # v1's, which golden_v1 lacks
    # ponytail: the output bytes are the recording machine's (golden_v1.env), which leaves out Pillow, summary.png's
    # encoder; its version joins env() at the next ruled re-recording
    if golden_v1.env() != GOLDEN["env"]:
        pytest.skip("the antenna output pins compare only on the env that recorded them (golden_v1.env())")
    assert now["outputs"] == GOLDEN["outputs"]  # a results/ file, a result line or a 2D readout moved
```

- [ ] **Step 2: Run it.** `.venv/Scripts/python -m pytest tests/test_golden_antenna.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'golden_antenna'`.
- [ ] **Step 3: The tools.**
  - **`golden_v1.record(golden: Path, digests: Callable[[], dict]) -> int`** is `golden_v1.main`'s body as it stands, with `GOLDEN` and `digests()` now its arguments and its refusal's prefix `golden.stem`, so golden_v1's refusal reads as today. Its docstring: "Records digests(), run in a fresh temporary folder, in `golden` with the product tree's id (p0.code_id) and env(), and returns 0; refuses with 1 when `golden` exists. tools/golden_antenna.py records through it too." `main()` returns `record(GOLDEN, digests)`, and golden_v1 imports `Callable` from `collections.abc`.
  - **`tools/golden_antenna.py`,** as given:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""The antenna golden pins (Stage 4 design 3, 4, 5.12 item 1): sha256 digests of what the antenna fixtures build and
write, and of v1's 2D readouts, which golden_v1 does not pin, recorded once at 037bc4b, before Stage 4 changed any
code, in tests/fixtures/golden_antenna.json, with golden_v1.env(). tests/test_golden_antenna.py compares the models
everywhere and the outputs where env() matches. Dev-time only: run it once with `python tools/golden_antenna.py`,
which records in English through golden_v1.record. It refuses to overwrite the JSON; a new recording is a controller
ruling, which deletes the file first."""
import os

if __name__ == "__main__":
    os.environ["LANGUAGE"] = "en"  # the suite's language, set before core.messages binds one: the PNGs' labels

import json
import shutil
import sys
from pathlib import Path
from unittest import mock

import numpy as np

import golden_v1
import p0
from golden_v1 import sha
from kicad_rf_studio import cli, pipeline, runs
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.model.spec import far_field_box, spec_hash, verify_spec
from kicad_rf_studio.core.project import GATES, parts

sys.path.append(str(p0.ROOT / "tests"))  # networks: the known N-port the KRS_FAKE=network fake replays
from networks import star, synth_records  # noqa: E402

GOLDEN = p0.FIX / "golden_antenna.json"
WIFI, ISM = (2.4e9, 2.4835e9), (902e6, 928e6)
BANDS = {"ifa2g4": WIFI, "ifa2g4_pi": WIFI, "ifa2g4_pi_shift": WIFI, "ifa2g4_pi_dxp": WIFI, "ifa2g4_pi_dxm": WIFI,
         "ifa2g4_pi_pour": WIFI, "meander915": ISM}  # every antenna fixture, new_antenna from U1.1 to AE1, defaults
TRACED = ("ifa2g4", "ifa2g4_pi")  # the cases whose outputs the committed fixtures let the suite write


def _board(name: str) -> str:
    """The fixture `name`'s board, copied into the working folder with LF line ends, as git stores it."""
    Path(f"{name}.kicad_pcb").write_bytes((p0.FIX / f"{name}.kicad_pcb").read_bytes().replace(b"\r\n", b"\n"))
    return f"{name}.kicad_pcb"


def _readout(geom) -> str:
    return sha(json.dumps(pipeline.readout_2d(geom), sort_keys=True).encode())


def digests() -> dict:
    """{"models": {case: {"spec_hash", "model_json", "project", "notes", "blocked"}, the pi's with "verify"},
    "outputs": {case: {"readout"}, TRACED's with each results/ file and "lines", and each of golden_v1.CASES with its
    "readout"}}, each board copied into the working folder (_board) and built there by new_antenna, or by new at
    golden_v1's settings. The pi's verify model is golden_v1's lpf915 recipe with its far-field box. ifa2g4's run is
    the far-field fixture's 58 mm dipole job (M = 0); the pi's 4 jobs are synth_records' star(f, 4) to 10 ns under its
    pulse, every part port at C_box 2e-14 F."""
    models, outputs = {}, {}
    for name, band in BANDS.items():
        pj, notes = cli.new_antenna(_board(name), "U1.1", "AE1", band, output=Path(name))
        project, board, geom, _ = pipeline.load(pj)
        model = pipeline.build_model(project, board, geom)
        spec = model.spec
        models[name] = {"spec_hash": spec_hash(spec), "model_json": sha(json.dumps(spec).encode()),
                        "project": sha(pj.read_bytes()),
                        "notes": sha(json.dumps(notes[:-1], sort_keys=True, default=str).encode()),
                        "blocked": sha(json.dumps(model.blocked, sort_keys=True, default=str).encode())}
        outputs[name] = {"readout": _readout(geom)}
        if name == "ifa2g4_pi":
            dump = Path(name) / "operator_dump.vtr"
            dump.write_bytes(b"")
            with mock.patch.object(spec_module, "c_box", lambda *_: 2e-14):
                vspec = verify_spec(spec, parts(project), dump, 1e-13, far_field=far_field_box(project, board, geom))
            models[name]["verify"] = {"spec_hash": spec_hash(vspec), "model_json": sha(json.dumps(vspec).encode())}
        if name not in TRACED:
            continue
        run_dir, jobs, far = Path(name) / "run", [], None
        runs.write_spec(run_dir, spec)
        n, exc = len(spec["ports"]), spec["excitation"]
        if n == 1:  # no part port: the far-field fixture's job, waves and transforms
            (run_dir / "job-1").mkdir()
            for file in ("waves.npz", "sphere.h5", "elevation.h5", "azimuth.h5"):
                shutil.copyfile(p0.FIX / "farfield" / file, run_dir / "job-1" / file)
            far = {grid: f"job-1/{grid}.h5" for grid in ("sphere", "elevation", "azimuth")}
            jobs.append({"port": "P1", "verdict": "converged", "t_cut": None, "t_stop": 1e-8, "residual_db": -60.0,
                         "waves": "job-1/waves.npz"})
        else:
            for k, (t_u, u, t_i, i) in enumerate(synth_records(lambda f: star(f, n), n, exc["f1"], exc["f2"], 1e-13,
                                                               10e-9), 1):
                (run_dir / f"job-{k}").mkdir()
                np.savez(run_dir / f"job-{k}" / "waves.npz", t_u=t_u, u=u, t_i=t_i, i=i)
                jobs.append({"port": spec["ports"][k - 1]["name"], "verdict": "converged", "t_cut": None,
                             "t_stop": float(t_u[-1]), "residual_db": -60.0, "waves": f"job-{k}/waves.npz"})
        results = {"run_dir": str(run_dir), "preset": "normal", "gates": GATES, "jobs": jobs,
                   "loss_expected": pipeline.expected_loss(geom, project["f0_hz"]),
                   "c_box": {q["name"]: 2e-14 for q in spec["ports"] if q["part"]}, "far_field": far}
        lines = pipeline.write_outputs(pj, {**project, "results": results}, "c")
        outputs[name] |= {**{f.name: sha(f.read_bytes()) for f in sorted((pj.parent / "results").iterdir())},
                          "lines": sha(json.dumps(lines, sort_keys=True, default=str).encode())}
    for name, (start, end, lid) in golden_v1.CASES.items():  # v1's 2D readouts, which golden_v1 does not pin
        pj, _ = cli.new(_board(name), start, end, 915e6, lid_height=lid, output=Path(name))
        outputs[name] = {"readout": _readout(pipeline.load(pj)[2])}
    return {"models": models, "outputs": outputs}


def main() -> int:
    """Records digests() in GOLDEN through golden_v1.record; 1 when GOLDEN exists."""
    return golden_v1.record(GOLDEN, digests)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Record the pins from `037bc4b`'s product.**
  - `git diff --stat 037bc4b -- src` must print nothing.
  - Run `.venv/Scripts/python tools/golden_antenna.py`. Expected: exit 0 and the JSON, about 5 KB, in about 10 s. Its `"code"` equals `git rev-parse 037bc4b:src`, and its `"env"` starts with `"win32"` and ends with `"en"`.
  - Run it again, then `.venv/Scripts/python tools/golden_v1.py`. Expected: each refuses, naming its JSON, with exit 1.
  - The reviser's prototype, v1's readouts included, gave identical digests in two working folders, in 9.5–9.9 s, a 5.3 KB JSON, and no blocking gate on any fixture.
- [ ] **Step 5: Run it again.** `.venv/Scripts/python -m pytest tests/test_golden_antenna.py tests/test_golden_v1.py tests/test_repo.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/golden_v1.py tools/golden_antenna.py tests/test_golden_antenna.py tests/fixtures/golden_antenna.json
git commit -m "test(golden): pin the seven antenna fixtures' model specs, hashes, the pi's verify model, project.json, new's lines, the 2D readout and results/ bytes, and v1's 2D readouts, as built at 037bc4b, recorded through golden_v1.record (Stage 4 design 4, 5.12 item 1)"
graphify update .
```

---

### Task 2 [code]: cs2d's coupled pair, Cohn and Kirschning–Jansen

**Files:**
- Modify `src/kicad_rf_studio/core/cs2d.py`: the module docstring, and `Pair` and `pair` after `solve` (L154–178). `solve` and its helpers stay as they are.
- Modify `tests/kicad_lines.py`: its docstring, and `coupled_microstrip`.
- Create `tools/p4a.py`, part 1.
- Test: `tests/test_cs2d.py`, which takes `WIDE` from `p4a` in place of its own.

**Interfaces:**
- Consumes: `cs2d.solve`, `Line`, `TOL` and `reference_box`; `kicad_lines.microstrip` and `ZF0`.
- Produces:
  - `cs2d.Pair`, a frozen dataclass: `z_even`, `eps_even`, `z_odd`, `eps_odd` (float) and `c: tuple[tuple[float, float], tuple[float, float]]`, the pair's capacitance matrix with the dielectrics, in F/m. Its properties are `z_diff` (2·z_odd), `z_comm` (z_even/2) and `k` ((z_even − z_odd)/(z_even + z_odd)).
  - `cs2d.pair(cs: CrossSection, x: np.ndarray | None = None, z: np.ndarray | None = None) -> Pair`.
  - `kicad_lines.coupled_microstrip(w, s, h, t, er) -> tuple[float, float, float, float]`, which returns (Zeven, εeven, Zodd, εodd).
  - `p4a.WIDE = 1e3`, `p4a.cohn(w, s, b, er) -> tuple[float, float]` (Zeven, Zodd), `p4a.stripline_pair(w, s, b, t, er) -> CrossSection` and `p4a.ms_pair(w, s, h, t, er) -> CrossSection`, all in mm.
- `solve` and every v1 and antenna path are untouched: `pair` only calls `solve`.

- [ ] **Step 1: Write the failing tests,** in `tests/test_cs2d.py`. Its imports gain `math`, `C_0` from `scipy.constants`, `ShortError` and `pair`, and `from p4a import WIDE, cohn, ms_pair, stripline_pair`; its own `WIDE = 1e3` line goes.

```python
def test_cohns_and_kirschning_jansens_coupled_lines_as_ported():  # Stage 4 design 5.11; r4's worked example
    ze, zo = cohn(0.15, 0.15, 0.5, 4.3)
    assert (round(ze, 2), round(zo, 2), round(2 * zo, 1), round((ze - zo) / (ze + zo), 3)) == (71.98, 52.01, 104.0,
                                                                                               0.161)
    assert kicad_lines.coupled_microstrip(0.15, 0.15, 0.2, 0.001, 4.3) == pytest.approx(
        (97.1232802849029, 3.249327590191874, 65.3666499716574, 2.7706356176104663), rel=1e-9)  # KiCad 9.0's formulas
    z, _ = kicad_lines.microstrip(0.15, 0.2, 0.0, 4.3)
    far = kicad_lines.coupled_microstrip(0.15, 5.0, 0.2, 0.0, 4.3)  # 25 h apart: hardly coupled
    assert far[0] == pytest.approx(z, rel=1e-3) and far[2] == pytest.approx(z, rel=1e-3)


def test_a_coupled_stripline_against_cohn_at_thin_copper():  # Stage 4 design 5.9, 5.11: P4-A's 0.5 %
    p = pair(stripline_pair(0.15, 0.15, 0.5, 1e-4, 4.3))
    ze, zo = cohn(0.15, 0.15, 0.5, 4.3)
    assert p.z_even == pytest.approx(ze, rel=0.005) and p.z_odd == pytest.approx(zo, rel=0.005)  # -0.26 %, -0.34 %
    assert p.eps_even == pytest.approx(4.3, rel=1e-9) and p.eps_odd == pytest.approx(4.3, rel=1e-9)  # homogeneous
    assert (p.z_diff, p.z_comm, p.k) == (2 * p.z_odd, p.z_even / 2, (p.z_even - p.z_odd) / (p.z_even + p.z_odd))
    (c11, c12), (c21, c22) = p.c
    assert c12 == c21 < 0 < c11 == c22
    for z, c in ((p.z_even, c11 + c12), (p.z_odd, c11 - c12)):  # a homogeneous line: Z = √εr / (c0·C)
        assert z * c * C_0 / math.sqrt(4.3) == pytest.approx(1, rel=1e-9)


def test_a_coupled_microstrip_against_kirschning_jansen():  # Stage 4 design 5.11: P4-A's 3 % at 1 µm
    p = pair(ms_pair(0.15, 0.15, 0.2, 0.001, 4.3))
    assert (p.z_even, p.eps_even, p.z_odd, p.eps_odd) == pytest.approx(
        kicad_lines.coupled_microstrip(0.15, 0.15, 0.2, 0.001, 4.3), rel=0.03)  # -1.32, -0.75, -0.47, -0.89 %


def test_a_pair_is_two_mirror_image_lines_that_never_share_a_node():  # Review Focus 1
    cs = ms_pair(0.15, 0.15, 0.2, 0.035, 4.3)
    p_leg, n_leg, plane = cs.conductors
    for conductors, match in (((p_leg, replace(n_leg, x1=n_leg.x1 + 0.05), plane), "mirror"),
                              ((p_leg, replace(n_leg, z1=n_leg.z1 + 0.01), plane), "mirror"),
                              ((p_leg, plane), "two signal"),
                              ((p_leg, n_leg, replace(p_leg, x0=-1.0, x1=-0.9), plane), "two signal")):
        with pytest.raises(ValueError, match=match):
            pair(replace(cs, conductors=conductors))
    with pytest.raises(ShortError):  # lines every 0.2 mm: the node at x 0 holds an edge of each leg
        pair(cs, np.array([-0.4, -0.2, 0.0, 0.2, 0.4]))
    with pytest.raises(ValueError, match="no grid edge"):  # lines that miss the N leg: a lone line, not a pair
        pair(cs, np.array([-1.0, -0.15, 0.0, 1.0]))
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_cs2d.py -q`. Expected: FAIL with `ImportError: cannot import name 'pair' from 'kicad_rf_studio.core.cs2d'` (the cs2d import precedes p4a's).
- [ ] **Step 3: `tools/p4a.py`, part 1,** as given:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""P4-A, the 2D and formulas gate (Stage 4 design 5.11). Part 1: Cohn's exact coupled stripline and the cross-sections
cs2d solves for it and for Kirschning–Jansen's coupled microstrip, in mm. Task 3 adds the even/odd 4-port, and Task 9
the gate."""
import math

from scipy.special import ellipk

from kicad_rf_studio.core.cs2d import CrossSection, Rect, reference_box

WIDE = 1e3  # mm: planes run past any box; the solver keeps what lies in it


def cohn(w: float, s: float, b: float, er: float) -> tuple[float, float]:
    """Zeven and Zodd (Ω) of Cohn's exact zero-thickness edge-coupled stripline (S. B. Cohn, IRE Trans. MTT 3(5), 1955):
    two strips `w` wide and `s` apart, centred between ground planes `b` apart, in εr `er`."""
    def ratio(k: float) -> float:  # K(k')/K(k) of modulus k; scipy's ellipk takes the parameter m = k²
        return float(ellipk(1 - k * k) / ellipk(k * k))

    a, c = math.tanh(math.pi * w / (2 * b)), math.tanh(math.pi * (w + s) / (2 * b))
    return 30 * math.pi / math.sqrt(er) * ratio(a * c), 30 * math.pi / math.sqrt(er) * ratio(a / c)


def stripline_pair(w: float, s: float, b: float, t: float, er: float) -> CrossSection:
    """Two strips `w` wide, `s` apart and `t` thick, centred between 35 µm planes `b` apart in εr `er`, the P leg first;
    the box spans the planes and 10·b past the strips."""
    z = b / 2
    legs = (Rect(-s / 2 - w, -s / 2, z - t / 2, z + t / 2, role="signal"),
            Rect(s / 2, s / 2 + w, z - t / 2, z + t / 2, role="signal"))
    planes = (Rect(-WIDE, WIDE, -0.035, 0, role="ground"), Rect(-WIDE, WIDE, b, b + 0.035, role="ground"))
    box = (round(-s / 2 - w - 10 * b, 6), round(s / 2 + w + 10 * b, 6), -0.035, round(b + 0.035, 6))
    return CrossSection(legs + planes, (Rect(-WIDE, WIDE, 0, b, er),), box)


def ms_pair(w: float, s: float, h: float, t: float, er: float) -> CrossSection:
    """Two strips `w` wide, `s` apart and `t` thick on `h` of εr `er` over a plane `t` thick, the P leg first, in their
    reference box (cs2d.reference_box)."""
    conductors = (Rect(-s / 2 - w, -s / 2, h, h + t, role="signal"), Rect(s / 2, s / 2 + w, h, h + t, role="signal"),
                  Rect(-WIDE, WIDE, -t, 0, role="ground"))
    return CrossSection(conductors, (Rect(-WIDE, WIDE, 0, h, er),), reference_box(conductors, h))
```

- [ ] **Step 4: `kicad_lines.coupled_microstrip`.** The module docstring adds `pcb_calculator/transline/c_microstrip.cpp` (branch 9.0, read on 2026-11-02): `C_MICROSTRIP::delta_u_thickness`, `filling_factor_even`, `filling_factor_odd`, `er_eff_static` and `Z0_even_odd`, quasi-static and with no cover (every cover term vanishes past its range), with `compute_single_line`'s zero-thickness single line. The port, as given:

```python
def coupled_microstrip(w: float, s: float, h: float, t: float, er: float) -> tuple[float, float, float, float]:
    """Zeven (Ω), εeven, Zodd (Ω) and εodd of an edge-coupled microstrip with no cover: two strips `w` wide, `s` apart
    and `t` thick on `h` of εr `er` (Kirschning and Jansen, IEEE Trans. MTT 32(1), 1984, with Jansen's 1978 thickness
    terms), as KiCad 9's c_microstrip.cpp computes them at f → 0."""
    u, g, t_h = w / h, s / h, t / h
    du_e = du_o = 0.0
    if t_h > 0:  # delta_u_thickness
        du = 1.25 * t_h / math.pi * (1 + math.log(
            (2 + (4 * math.pi * u - 2) / (1 + math.exp(-100 * (u - 1 / (2 * math.pi))))) / t_h))
        dt = t_h / (g * er)
        du_e = du * (1 - 0.5 * math.exp(-0.69 * du / dt))
        du_o = du_e + dt
    ue, uo = u + du_e, u + du_o
    z1, e1 = microstrip(w, h, 0.0, er)  # compute_single_line: zero thickness, no cover
    q_t = 2 * math.log(2) / math.pi * t_h  # delta_q_thickness × √u
    v = ue * (20 + g * g) / (10 + g * g) + g * math.exp(-g)  # filling_factor_even
    a_e = 1 + math.log((v ** 4 + v * v / 2704) / (v ** 4 + 0.432)) / 49 + math.log(1 + v ** 3 / 5929.741) / 18.7
    b_e = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    e_e = 0.5 * (er + 1) + 0.5 * (er - 1) * ((1 + 10 / v) ** (-a_e * b_e) - q_t / math.sqrt(ue))
    b_o = 0.747 * er / (0.15 + er)  # filling_factor_odd
    c_o = b_o - (b_o - 0.207) * math.exp(-0.414 * uo)
    d_o = 0.593 + 0.694 * math.exp(-0.562 * uo)
    a_o = 0.7287 * (e1 - 0.5 * (er + 1)) * (1 - math.exp(-0.179 * uo))
    e_o = (0.5 * (er + 1) + a_o - e1) * (math.exp(-c_o * g ** d_o) - q_t / math.sqrt(uo)) + e1
    q1 = 0.8695 * ue ** 0.194  # Z0_even_odd
    q2 = 1 + 0.7519 * g + 0.189 * g ** 2.31
    q3 = 0.1975 + (16.6 + (8.4 / g) ** 6) ** -0.387 + math.log(g ** 10 / (1 + (g / 3.4) ** 10)) / 241
    q4 = 2 * q1 / (q2 * (math.exp(-g) * ue ** q3 + (2 - math.exp(-g)) * ue ** -q3))
    q5 = 1.794 + 1.14 * math.log(1 + 0.638 / (g + 0.517 * g ** 2.43))
    q6 = 0.2305 + math.log(g ** 10 / (1 + (g / 5.8) ** 10)) / 281.3 + math.log(1 + 0.598 * g ** 1.154) / 5.1
    q7 = (10 + 190 * g * g) / (1 + 82.3 * g ** 3)
    q8 = math.exp(-6.5 - 0.95 * math.log(g) - (g / 0.15) ** 5)
    q9 = math.log(q7) * (q8 + 1 / 16.5)
    q10 = (q2 * q4 - q5 * math.exp(math.log(uo) * q6 * uo ** -q9)) / q2
    z_e = z1 * math.sqrt(e1 / e_e) / (1 - math.sqrt(e1) * q4 * z1 / ZF0)
    z_o = z1 * math.sqrt(e1 / e_o) / (1 - math.sqrt(e1) * q10 * z1 / ZF0)
    return z_e, e_e, z_o, e_o
```

- [ ] **Step 5: cs2d.**
  - **`Pair`,** with the docstring "A coupled pair's quasi-static modes (Stage 4 design 5.9): the even (common) and odd (differential) impedances in Ω, their effective permittivities, and the capacitance matrix c with the dielectrics, in F/m."
  - **`pair`:**
    - **Docstring:** "The even and odd modes of the pair in `cs` (Stage 4 design 5.9): its two "signal" conductors, the P leg first, from three solve() calls on the lines given, or on solve's own grid, which does not depend on the roles, so the three share it: each leg alone at 1 V with the other a ground (C_P, C_N), then both at 1 V (C_PN, both lines' charge). Each Line gives C = √εeff/(c0·Z0) and C0 = 1/(c0·Z0·√εeff). Then Ce = C_PN/2 and Co = C_P + C_N − Ce, likewise in vacuum, Z = 1/(c0·√(C·C0)), εeff = C/C0, c11 = (Ce + Co)/2 and c12 = (Ce − Co)/2. Raises ValueError unless there are exactly two signal conductors with equal widths and z spans (within TOL), and solve's own errors: ValueError when a leg holds no grid edge, ShortError when a node holds both legs."
    - Check the legs before solving, with the messages "a pair needs exactly two signal conductors" and "a pair's two lines must mirror each other: equal widths and z spans".
    - Then `solve(cs_p, x, z)`, `solve(cs_n, x, z)` and `solve(cs, x, z)`, where `cs_p` is `replace(cs, conductors=...)` with the N leg's role `"ground"`, and `cs_n` likewise with the P leg's.
    - Mark it `# ponytail: mirror-image legs only, their surroundings' symmetry unchecked; an asymmetric pair's modes are not even and odd, and plan 2 decides what its 2D table does with one. Three solves where a (1, −1) excitation takes two: 1.5 times the time, and solve unchanged`.
  - **The module docstring** adds: "pair() gives a coupled pair's even and odd modes from three solves (Stage 4 design 5.9)."
- [ ] **Step 6: Run them again.** `.venv/Scripts/python -m pytest tests/test_cs2d.py tests/test_golden_antenna.py tests/test_golden_v1.py -q`. Expected: PASS. The reviser's prototype matched the (1, 1) and (1, −1) energies on solve's grid to 5e-16, in 1.5 s against 1.0 s on the 0.1 µm stripline.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/cs2d.py tests/kicad_lines.py tests/test_cs2d.py tools/p4a.py
git commit -m "feat(cs2d): a coupled pair's even and odd modes, Zdiff, Zcomm, k and its capacitance matrix from three solves, mirror-image legs only, with Cohn's coupled stripline and KiCad 9's Kirschning-Jansen coupled microstrip as references (Stage 4 design 5.9, 5.11)"
graphify update .
```

---

### Task 3 [code]: The TDR, and the even/odd 4-port as P4-A's reference

**Files:** Create `src/kicad_rf_studio/core/post/si.py` and `tests/test_post_si.py`. Modify `core/post/__init__.py`'s docstring, which adds "the TDR (si)", and `tools/p4a.py`: `even_odd_s`, numpy and scipy.constants' `c` among its imports, and its docstring's part 1.

**Interfaces:**
- Consumes: `p4a.cohn`.
- Produces:
  - in `tools/p4a.py`: `even_odd_s(z_even: float, eps_even: float, z_odd: float, eps_odd: float, length_mm: float, f: np.ndarray, z_ref: float = 50.0) -> np.ndarray`, of shape (F, 4, 4), its ports [P near, N near, P far, N far];
  - in `core/post/si.py`: `N_TDR = 2000`, `PAD = 8`, `LEAD = 4.0` and `LOCAL_RISE = 1.25`; `uniform_grid(f_max: float, n: int = N_TDR) -> np.ndarray` and `rise_filter(f: np.ndarray, t_r: float) -> np.ndarray`; `step_response(s, f, t_r) -> tuple[np.ndarray, np.ndarray]`, which returns (t in s, ρ); `tdr(s11, f, t_r, z_ref=50.0) -> tuple[np.ndarray, np.ndarray]`, which returns (t in s, Z in Ω).

- [ ] **Step 1: Write the failing tests,** `tests/test_post_si.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import math

import numpy as np
import pytest
from scipy.constants import c as C0

from kicad_rf_studio.core.post.si import (LEAD, LOCAL_RISE, N_TDR, rise_filter, step_response, tdr,
                                          uniform_grid)
from p4a import cohn, even_odd_s

F, TR = uniform_grid(10e9), LOCAL_RISE / 10e9  # the presets' band and its localising rise time, 125 ps
TAU = 50e-3 * 2.0 / C0  # one way along 50 mm at εeff 4: 0.334 ns
GAMMA = 10 / 110  # a 60 Ω line's step from 50 Ω


def test_a_homogeneous_striplines_4port_has_no_fext_and_its_next_peaks_at_k():  # design 5.11: P4-A, to 1e-9
    ze, zo = cohn(0.15, 0.15, 0.5, 4.3)
    fq = C0 / (4 * 50e-3 * math.sqrt(4.3))  # the quarter wave
    s = even_odd_s(ze, 4.3, zo, 4.3, 50.0, np.r_[np.linspace(0, 3 * fq, 301), fq], math.sqrt(ze * zo))
    k = (ze - zo) / (ze + zo)
    assert np.abs(s[:, 0, 3]).max() <= 1e-9 and np.abs(s[:, 0, 0]).max() <= 1e-9  # FEXT and S11
    assert abs(abs(s[-1, 0, 1]) - k) <= 1e-9 and np.abs(s[:, 0, 1]).max() <= k + 1e-9  # NEXT's peak
    assert np.abs(s - s.transpose(0, 2, 1)).max() <= 1e-15  # reciprocal
    assert np.abs(np.einsum("fij,fkj->fik", s, s.conj()) - np.eye(4)).max() <= 1e-9  # lossless


def test_a_lines_reflection_is_the_bounce_series_of_its_steps_gamma():  # design 5.11: P4-A, to 1e-9
    f = np.linspace(0, 10e9, 401)
    s = even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, f)  # no coupling: each leg a 60 Ω line between 50 Ω ports
    th = 2 * np.pi * f * TAU
    x = np.exp(-2j * th)
    assert np.abs(s[:, 0, 0] - GAMMA * (1 - x) / (1 - GAMMA ** 2 * x)).max() <= 1e-9
    assert np.abs(s[:, 0, 2] - (1 - GAMMA ** 2) * np.exp(-1j * th) / (1 - GAMMA ** 2 * x)).max() <= 1e-9
    assert np.abs(s[:, 0, 1]).max() == np.abs(s[:, 0, 3]).max() == 0.0


def test_the_tdr_reads_an_ideal_60_ohm_line_as_60_then_50():  # design 5.6, 5.11
    t, z = tdr(even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, F)[:, 0, 0], F, TR)
    assert round(float(np.interp(TAU, t, z)), 1) == 60.0  # mid-line: 59.999
    late = (t >= 4 * TAU + 4 * TR) & (t <= 20e-9)  # past the second round trip; until then 50.075 Ω, the line's Γ³
    assert set(np.round(z[late], 1).tolist()) == {50.0}


def test_the_tdrs_sum_starts_before_t_0():  # Review Focus 2: r1's first version read half the step, 55 Ω
    t, rho = step_response(even_odd_s(60.0, 4.0, 60.0, 4.0, 50.0, F)[:, 0, 0], F, TR)
    assert t[0] <= -LEAD * TR and abs(rho[0]) <= 1e-5  # quiet before the filter's impulse, centred on t = 0
    assert float(np.interp(TAU, t, rho)) == pytest.approx(GAMMA, rel=1e-3)  # the whole step, not half of it


def test_the_tdr_needs_a_uniform_grid_from_dc():  # Review Focus 2
    for f in (np.array([1e9, 2e9, 3e9]), np.array([0.0, 1e9, 3e9])):
        with pytest.raises(ValueError, match="uniform grid from DC"):
            step_response(np.zeros(3), f, TR)
    assert len(F) == N_TDR + 1 and F[[0, 1, -1]].tolist() == [0.0, 5e6, 10e9]
    assert 20 * math.log10(rise_filter(np.array([10e9]), TR)[0]) == pytest.approx(-40.78, abs=0.01)  # design 5.1
    assert rise_filter(np.array([0.0]), TR)[0] == 1.0
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_si.py -q`. Expected: FAIL with `No module named 'kicad_rf_studio.core.post.si'`.
- [ ] **Step 3: The 4-port and the TDR.**
  - **`even_odd_s`, in `tools/p4a.py`:** each mode m is a line of impedance Z_m and electrical length θ_m = 2π·f·length·√ε_m/c0 between `z_ref` ports.
    - With z = Z_m/z_ref and D = 2·cos θ + j·(z + 1/z)·sin θ: Γ_m = j·(z − 1/z)·sin θ/D and T_m = 2/D.
    - a = (Γe + Γo)/2, b = (Γe − Γo)/2 (NEXT), c = (Te + To)/2 (the thru) and d = (Te − To)/2 (FEXT).
    - S's rows are [a, b, c, d], [b, a, d, c], [c, d, a, b] and [d, c, b, a].
    - The docstring states the port order, that the model is exact for a lossless quasi-TEM pair (r4), and that it is P4-A's and P4-B's reference, which no product code reads. p4a's docstring's part 1 names it.
  - **`core/post/si.py`:**
    - **Docstring:** "Signal integrity's time-domain readings (Stage 4 design 5.1, 5.6): the uniform grid from DC, the Gaussian rise filter and the TDR's step response from S. Pure numpy: it never imports openEMS or scikit-rf." It imports math and numpy.
    - **Constants**, each commented:
      - `N_TDR`: "points above DC: 5 MHz apart at 10 GHz, a 200 ns record", with `# ponytail: a response longer than the 1/Δf record wraps, and Z = z_ref(1 + ρ)/(1 − ρ) has no bound as ρ → 1 (an open); plan 3 retunes N_TDR`;
      - `PAD`: "the inverse FFT's zero padding";
      - `LEAD`: "rise times before t = 0 where the step's sum starts";
      - `LOCAL_RISE`: "the localising TDR's rise time is LOCAL_RISE/f_max, where the filter is near −40 dB at f_max (design 5.1)".
    - **`uniform_grid`** returns `np.linspace(0.0, f_max, n + 1)`.
    - **`rise_filter`** is H(f) = exp(−2π²σ²f²), σ = t_r/2.563, a Gaussian whose step rises 10–90 % in t_r.
    - **`tdr`** returns `t, z_ref * (1 + rho) / (1 - rho)` of `step_response`.
    - **`step_response`,** as given:

```python
def step_response(s: np.ndarray, f: np.ndarray, t_r: float) -> tuple[np.ndarray, np.ndarray]:
    """The step response ρ(t) of S `s` (F,) on `f`, a uniform grid from DC (uniform_grid), through rise_filter at the
    10–90 % rise time `t_r` (s): the inverse FFT of the filtered S, zero-padded PAD times, summed from LEAD rise times
    before t = 0, since the filter's impulse is centred on t = 0 and a sum started there reads half the step (r1).
    ValueError for any other grid."""
    f = np.asarray(f, float)
    if f[0] != 0 or not np.allclose(np.diff(f), f[1] - f[0], rtol=1e-9, atol=0):
        raise ValueError("the TDR needs a uniform grid from DC")
    m = PAD * (len(f) - 1)
    spec = np.zeros(m + 1, complex)
    spec[:len(f)] = s * rise_filter(f, t_r)
    h = np.fft.irfft(spec)  # the filtered impulse response, a sample every dt
    dt = 1 / (2 * m * (f[1] - f[0]))
    k = math.ceil(LEAD * t_r / dt)
    return (np.arange(len(h)) - k) * dt, np.cumsum(np.roll(h, k))
```

- [ ] **Step 4: Run them again.** `.venv/Scripts/python -m pytest tests/test_post_si.py tests/test_cs2d.py -q`. Expected: PASS. The prototypes read:
  - FEXT 0.0, S11 3.5e-17, and NEXT's peak within 2.8e-17 of k = 0.16104;
  - the bounce series within 6.7e-16 and the thru within 3.7e-15;
  - 59.999 Ω mid-line, the late window within 0.0014 Ω of 50, and |ρ| 2.4e-7 at t = −0.5 ns.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/post/si.py src/kicad_rf_studio/core/post/__init__.py tests/test_post_si.py tools/p4a.py
git commit -m "feat(post): the TDR's step response from S on a uniform grid from DC, summed from before t = 0, and the even/odd 4-port of a uniform coupled pair as P4-A's reference in tools/p4a.py (Stage 4 design 5.6, 5.11)"
graphify update .
```

---

### Task 4 [code]: Schema 3, and the dielectric next to each layer

**Files:** Modify `src/kicad_rf_studio/core/project.py`: `SCHEMA_SI` after `SCHEMA_ANTENNA` (L32), and `si` after `antenna` (L52–54). Modify `src/kicad_rf_studio/core/geometry/zstack.py`: `substrate_h` (L43–48), and `Iterable` from `collections.abc` among its imports. Tests: `tests/test_project.py` and `tests/test_geometry_region.py`.

**Interfaces:**
- Produces: `project.SCHEMA_SI = 3` and `project.si(data: dict) -> bool`; `substrate_h(zs: tuple[Slab, ...], layers: Iterable[str] = ()) -> float`, in mm.
- `load_project` is unchanged and still refuses schema 3 with E_PROJECT_SCHEMA, `expected` SCHEMA_ANTENNA. Plan 2 accepts schema 3 in the task that adds `_FIELDS_SI`, and adds an SI project's gates (dt_floor 0.6, design §5.3), which nothing in plan 1 reads.
- Without `layers`, `substrate_h` returns today's value, so every current caller (all v1 or antenna) is unchanged. Plan 2 passes an SI project's line layers, for d and the reach.

- [ ] **Step 1: Write the failing tests.** In `tests/test_project.py` (imports gain `SCHEMA_SI` and `si`):

```python
def test_schema_3_is_an_si_project_which_this_build_still_refuses(tmp_path):  # Stage 4 design 5.1
    assert (SCHEMA_SI, si({"schema": 3}), si({"schema": 2}), si({}), antenna({"schema": 3})) == (
        3, True, False, False, False)
    p = tmp_path / "project.json"
    p.write_text('{"schema": 3, "kind": "si"}', encoding="utf-8")
    with pytest.raises(KrsError) as e:  # until plan 2 checks an SI project's fields
        load_project(p)
    assert (e.value.code, e.value.params) == ("E_PROJECT_SCHEMA", {"path": str(p), "found": 3,
                                                                   "expected": SCHEMA_ANTENNA})
```

  In `tests/test_geometry_region.py` (imports gain `Slab`):

```python
SIX = (Slab("copper", 0.0, 0.035, None, None, "B.Cu"), Slab("dielectric", 0.035, 0.235, 4.3, 0.02, None),
       Slab("copper", 0.235, 0.27, None, None, "In4.Cu"), Slab("dielectric", 0.27, 0.57, 4.5, 0.02, None),
       Slab("copper", 0.57, 0.605, None, None, "In3.Cu"), Slab("dielectric", 0.605, 0.755, 4.3, 0.02, None),
       Slab("copper", 0.755, 0.79, None, None, "In2.Cu"), Slab("dielectric", 0.79, 1.09, 4.5, 0.02, None),
       Slab("copper", 1.09, 1.125, None, None, "In1.Cu"), Slab("dielectric", 1.125, 1.325, 4.3, 0.02, None),
       Slab("copper", 1.325, 1.36, None, None, "F.Cu"))  # bottom up: 0.2, 0.3, 0.15, 0.3 and 0.2 mm between coppers


def test_an_si_lines_substrate_is_the_thinnest_dielectric_next_to_its_layers():  # Stage 4 design 5.3
    assert substrate_h(SIX) == substrate_h(SIX, ["F.Cu"]) == 0.2  # v1's and the antenna's: the top layer's
    assert substrate_h(SIX, ["B.Cu"]) == 0.2  # a bottom microstrip: the dielectric above it
    assert substrate_h(SIX, ["In3.Cu"]) == 0.15  # a stripline 0.3 mm over In4.Cu and 0.15 mm under In2.Cu
    assert substrate_h(SIX, ["In4.Cu"]) == 0.2 and substrate_h(SIX, ["F.Cu", "In3.Cu"]) == 0.15
    with pytest.raises(KeyError):
        substrate_h(SIX, ["In5.Cu"])
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_project.py tests/test_geometry_region.py -q -k "schema_3 or thinnest"`. Expected: `tests/test_project.py` errors at collection with `cannot import name 'SCHEMA_SI'`, and the substrate_h test fails with `TypeError: substrate_h() takes 1 positional argument but 2 were given`.
- [ ] **Step 3: The code.**
  - After `SCHEMA_ANTENNA`: `SCHEMA_SI = 3`, commented "an SI project (Stage 4 design 5.1): load_project refuses it until Stage 4 plan 2 checks its fields".
  - `si(data)`, with the docstring "Whether project.json `data` is an SI project's, schema SCHEMA_SI (Stage 4 design 5.1).", returns `data.get("schema") == SCHEMA_SI`.
  - **`substrate_h`:**
    - **Docstring:** "The dielectric next to the measured nets' copper, in mm. Without `layers`: between the top copper, where v1's and an antenna's measured nets run, and the next copper down. With `layers` (an SI project's line layers, Stage 4 design 5.3): the thinnest dielectric between any of them and a copper layer next to it, above or below, which sets the fringing field d resolves and the reach. KeyError for a name that is not a copper layer of `zs`."
    - Index the copper slabs bottom up by name. A layer's gaps are `cu[i].z0 − cu[i − 1].z1` and `cu[i + 1].z0 − cu[i].z1`, where they exist. Take the minimum over the layers, rounded to 6 decimals.
    - The ponytail comment now says that SI passes its lines' layers.
- [ ] **Step 4: Run them again.** `.venv/Scripts/python -m pytest tests/test_project.py tests/test_geometry_region.py tests/test_golden_antenna.py tests/test_golden_v1.py -q`. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/project.py src/kicad_rf_studio/core/geometry/zstack.py tests/test_project.py tests/test_geometry_region.py
git commit -m "feat(project, geometry): schema 3 and si(), which load_project still refuses until plan 2 checks an SI project's fields, and substrate_h over given copper layers, the thinnest dielectric next to any of them, for an SI project's d and reach (Stage 4 design 5.1, 5.3)"
graphify update .
```

---

### Task 5 [code]: The SI mesh rule

**Files:** Modify `src/kicad_rf_studio/core/geometry/region.py`: `SI_CELLS` and `si_max_cell` after `coarse_cell` (L46–48). Modify `src/kicad_rf_studio/core/mesh/rule.py`: `xy_lines` (L101–126) and `_axis` (L155–180). Test: `tests/test_mesh_rule.py`.

**Interfaces:**
- Consumes: `region.lambda_min(f_max, eps_r_max)` and `region.coarse_cell`.
- Produces:
  - `region.SI_CELLS = 40` and `region.si_max_cell(f_max: float, eps_eff: float) -> float` (mm).
  - `xy_lines(edges, extent, walls, free, d, coarse, prefer=(), force=(), h=math.inf, exempt=frozenset(), *, max_cell: float | None = None, spans: Collection[tuple[float, float]] = ()) -> tuple[np.ndarray, np.ndarray]`; `Collection` is already among rule.py's imports.
- With `max_cell` None the lines are today's, bit for bit, and `spans` is ignored. Plan 2 passes the max_cell of the 2D εeff, and the spans: the margins around vias, and staircased copper.

- [ ] **Step 1: Write the failing tests,** in `tests/test_mesh_rule.py` (its import from `core.geometry.region` gains `coarse_cell` and `si_max_cell`; `GRID_TOL` and `bad_pairs` are the file's own):

```python
SI_D, SI_H = 0.075, 0.2  # a 0.15 mm pair with a 0.15 mm gap on 0.2 mm, at n 2
SI_COARSE, SI_CELL = coarse_cell(10e9, 4.3), si_max_cell(10e9, 3.3)  # λ_min/20 and λ_eff/40 at 10 GHz
STRAIGHT = [(0.0, 1), (100.0, -1)]  # a 100 mm pair along x: its ends
ACROSS = [(-0.225, 1), (-0.075, -1), (0.075, 1), (0.225, -1)]  # its two legs, across it
L_X = [(0.0, 1), (49.775, 1), (49.925, -1), (50.075, 1), (50.225, -1)]  # an L: 50 mm along x, then down along y


def si_axis(edges, extent, **si):
    walls = (round(extent[0] - 4 - 8 * SI_COARSE, 6), round(extent[1] + 4 + 8 * SI_COARSE, 6))  # 4 mm + 8 cells
    return rule.xy_lines(edges, extent, walls, [e for e, _ in edges], SI_D, SI_COARSE, h=SI_H, **si)[0]


def around(lines, e, inside):
    """The lines nearest the edge at `e`, in its metal and out of it: its pattern's inside and outside lines."""
    off = np.round((lines - e) * inside, 9)
    return lines[off > 0][off[off > 0].argmin()], lines[off < 0][off[off < 0].argmax()]


@pytest.mark.parametrize(("edges", "extent", "fewer"), [(STRAIGHT, (-1.2, 101.2), 4), (ACROSS, (-1.425, 1.425), 1.5),
                                                        (L_X, (-1.2, 51.425), 4)])
def test_the_si_rule_fills_d_only_at_the_edges_and_grades_to_max_cell_between(edges, extent, fewer):  # design 5.3
    v1, si = si_axis(edges, extent), si_axis(edges, extent, max_cell=SI_CELL)
    held = lambda lines: lines[(lines >= extent[0]) & (lines <= extent[1])]  # noqa: E731
    assert fewer * len(held(si)) <= len(held(v1))  # 267 against 1,368; 22 against 42; 153 against 706
    assert [around(si, e, s) for e, s in edges] == [around(v1, e, s) for e, s in edges]  # the edge patterns kept
    assert lint_hits(si, edges, SI_D) == [] and bad_pairs(si, [e for e, _ in edges]) == []
    steps, mids = np.diff(si), (si[1:] + si[:-1]) / 2
    inside = (mids >= extent[0]) & (mids <= extent[1])
    assert steps[inside].max() <= SI_CELL + GRID_TOL and steps[~inside].max() <= SI_COARSE + GRID_TOL
    assert steps.min() >= SI_D / 3 - GRID_TOL  # the d/3 merge


@pytest.mark.parametrize(("edges", "extent", "span"), [(STRAIGHT, (-1.2, 101.2), (49.0, 51.0)),
                                                       (STRAIGHT, (-1.2, 101.2), (99.0, 101.0)),
                                                       (L_X, (-1.2, 51.425), (49.0, 51.0)),
                                                       (L_X, (-1.2, 51.425), (49.0, 49.8))])
def test_the_si_rule_fills_a_via_margin_at_d_clear_of_or_over_an_edge(edges, extent, span):  # 5.3; Review Focus 3
    si = si_axis(edges, extent, max_cell=SI_CELL, spans=[span])
    inner = si[(si >= span[0]) & (si <= span[1])]
    assert inner[0] == span[0] and np.diff(inner).max() <= SI_D + GRID_TOL  # 49.8 lies d/3 from an edge line: merged
    assert lint_hits(si, edges, SI_D) == [] and bad_pairs(si, [e for e, _ in edges]) == []
    assert np.diff(si).min() >= SI_D / 3 - GRID_TOL
    assert si_max_cell(10e9, 3.3) == pytest.approx(0.412576, abs=1e-6)  # 30 mm/√3.3/40
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_mesh_rule.py -q -k si_rule`. Expected: FAIL with `ImportError: cannot import name 'si_max_cell' from 'kicad_rf_studio.core.geometry.region'`.
- [ ] **Step 3: The rule.**
  - **region.py:** `SI_CELLS = 40`, commented "an SI mesh's largest cell along a line is λ_eff(f_max)/SI_CELLS (Stage 4 design 5.3); gate P4-C may move it". `si_max_cell(f_max, eps_eff)` returns `lambda_min(f_max, eps_eff) / SI_CELLS`, with the docstring "An SI mesh's max_cell, λ_eff(f_max)/SI_CELLS, in mm: f_max in Hz, eps_eff the lines' 2D εeff (Stage 4 design 5.3)."
  - **`xy_lines`** passes `max_cell` and `spans` to both `_axis` calls. Its docstring gains this bullet: "With `max_cell` (an SI project's, Stage 4 design 5.3), d fills only the `spans` (lo, hi) the caller gives on this axis: the margins around vias, and any copper its edges cannot pattern. Their ends are lines where clear. Elsewhere in the extent the cells grade at RATIO up to `max_cell`, and outside it up to `coarse` as before. The rule's own lines are then the walls, the edge lines, the extent's and the spans' ends, and the spans' fill. With None, as for v1 and the antenna, d fills the whole extent as before and `spans` is ignored."
  - **`_axis`** gains `max_cell` and `spans` and changes in four places. Everything else stays, `_smooth` at `coarse` too:
    1. With `max_cell` set, `base` also merges each span's two ends (rounded to 6 decimals) that are `clear`.
    2. `fill(m)` is `(m >= lo) & (m <= hi)` when `max_cell` is None, and otherwise whether any span (a, b) holds m, a ≤ m ≤ b (all False without spans). The fill's `_grade` waits on `mid[~fill(mid)]` instead of `mid[(mid < lo) | (mid > hi)]`.
    3. The second `_grade`'s cap is `np.where(fill(m), d, np.where((m >= lo) & (m <= hi), cap, coarse))`, `cap` being d with None and `max_cell` otherwise, so None gives today's cap.
    4. The pinned lines are `np.union1d(base, lines[fill(lines)])`.
  - Mark it `# ponytail: d fills only where the caller says; staircased (45°) copper has no axis edge, so plan 2 passes its spans too or keeps the d fill`.
- [ ] **Step 4: Run them again.** `.venv/Scripts/python -m pytest tests/test_mesh_rule.py tests/test_geometry_region.py tests/test_golden_antenna.py tests/test_golden_v1.py -q`. Expected: PASS. The reviser's prototype of this change gave the counts in the tests' comments, every edge's nearest lines equal to the d fill's, today's lines array-equal with `max_cell` None, and every span's cells at d or under (the clear via span's at 0.074 mm), with 298, 287, 169 and 161 lines in the four spans' extents.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/geometry/region.py src/kicad_rf_studio/core/mesh/rule.py tests/test_mesh_rule.py
git commit -m "feat(mesh): the SI mesh rule in xy_lines, d only at the edges' patterns and the given spans, graded at 1.3 up to max_cell = λ_eff(f_max)/40 inside the protected extent, with si_max_cell beside coarse_cell (Stage 4 design 5.3)"
graphify update .
```

---

### Task 6 [code]: The vertical port

**Files:** Modify `src/kicad_rf_studio/core/model/ports.py`: `End` (L29–40) gains `ref_layer`; `plane_under` and `vertical` go after `nominal_boxes`; `place` gains its first line; the `TYPE_CHECKING` block (L18–26) imports `Collection` from `collections.abc`. Test: `tests/test_model_ports.py`.

**Interfaces:**
- Consumes: `Slab`, `Piece`, `Mesh`, `SIMPLIFY` and `shapely.union_all`; `copper.split_holes` in the tests.
- Produces:
  - `End.ref_layer: str | None = None`, after `centers`.
  - `plane_under(pad: BaseGeometry, layer: str, zs: tuple[Slab, ...], pieces: list[Piece], nets: Collection[str]) -> str | None`.
  - `vertical(end: End, mesh: Mesh, zs: tuple[Slab, ...]) -> dict`, which `place()` returns when `end.ref_layer` is set.
- Plan 2 makes an SI end vertical when no same-layer reference lies within the reach: `End(name, pad, pad, layer, role, ref_layer=plane_under(...))`. Its reference is the pad's footprint, which the plane covers, so `nominal_boxes` stays the pad.

- [ ] **Step 1: Write the failing tests,** in `tests/test_model_ports.py` (imports gain `plane_under`, and `split_holes` beside `Piece`):

```python
FOUR = (Slab("copper", 0.0, 0.035, None, None, "B.Cu"), Slab("dielectric", 0.035, 0.235, 4.3, 0.02, None),
        Slab("copper", 0.235, 0.27, None, None, "In2.Cu"), Slab("dielectric", 0.27, 1.335, 4.5, 0.02, None),
        Slab("copper", 1.335, 1.37, None, None, "In1.Cu"), Slab("dielectric", 1.37, 1.57, 4.3, 0.02, None),
        Slab("copper", 1.57, 1.605, None, None, "F.Cu"))
GRID = np.round(np.arange(-10, 11) * 0.1, 6)  # lines every 0.1 mm
V_MESH = Mesh(GRID, GRID, np.array([0.0, 0.035, 0.235, 0.27, 1.335, 1.37, 1.57, 1.605]), 0.1, 0.03, {}, {})
PAD = box(-0.15, -0.3, 0.15, 0.3)  # 0.3 × 0.6 mm, longer along y


def plane(layer, net="GND", shape=box(-5, -5, 5, 5)):
    return Piece(layer, net, shape, True)


def cut(shape, layer="In1.Cu"):
    """A GND plane `shape` as the copper pipeline leaves it: pieces with no holes (split_holes)."""
    return [Piece(layer, "GND", g, True) for g in split_holes(shape)]


def test_a_vertical_port_runs_from_the_plane_under_a_pad_to_the_pad():  # Stage 4 design 5.5
    assert plane_under(PAD, "F.Cu", FOUR, [plane("In1.Cu")], {"GND"}) == "In1.Cu"
    q = place(End("P1", PAD, PAD, "F.Cu", "external", ref_layer="In1.Cu"), V_MESH, FOUR, [])
    assert q == {"name": "P1", "kind": "lumped", "dir": "z", "start": [0.0, -0.2, 1.37], "stop": [0.0, 0.2, 1.57],
                 "nodes": [[0.0, 0.0, 1.37], [0.0, 0.0, 1.57], [0.0, 0.0, 1.335], [0.0, 0.0, 1.605]], "part": False}
    assert plane_under(PAD, "B.Cu", FOUR, [plane("In2.Cu")], {"GND"}) == "In2.Cu"  # a bottom pad: the plane above
    q = place(End("P2", PAD, PAD, "B.Cu", "external", ref_layer="In2.Cu"), V_MESH, FOUR, [])
    assert (q["start"], q["stop"]) == ([0.0, -0.2, 0.235], [0.0, 0.2, 0.035])  # from the plane: u = V_pad − V_plane
    # the lumped port's order, plane cap, pad cap, then their far faces, which the PEC-roots gate reads
    assert q["nodes"] == [[0.0, 0.0, 0.235], [0.0, 0.0, 0.035], [0.0, 0.0, 0.27], [0.0, 0.0, 0.0]]
    disc = Point(0, 0).buffer(0.2)
    q = place(End("P3", disc, disc, "F.Cu", "external", ref_layer="In1.Cu"), V_MESH, FOUR, [])
    assert (q["start"], q["stop"]) == ([-0.1, 0.0, 1.37], [0.1, 0.0, 1.57])  # a round pad: across its centre


def test_the_plane_under_a_pad_is_the_nearest_one_nets_copper_that_covers_it():  # design 5.5; Review Focus 4
    halves = cut(box(-5, -5, 5, 5).difference(Point(0.05, 3.0).buffer(0.15)))  # an antipad 3 mm off, cut at x 0.05
    assert len(halves) == 2 and plane_under(PAD, "F.Cu", FOUR, halves, {"GND"}) == "In1.Cu"  # neither piece alone
    assert plane_under(PAD, "F.Cu", FOUR, [plane("In2.Cu")], {"GND"}) == "In2.Cu"  # past In1.Cu, bare under the pad
    away = plane("In1.Cu", "SIG", box(1, -1, 2, 1))  # In1.Cu's copper beside the pad, not over it
    assert plane_under(PAD, "F.Cu", FOUR, [away, plane("In2.Cu")], {"GND"}) == "In2.Cu"
    two = (FOUR[0], Slab("dielectric", 0.035, 1.535, 4.5, 0.02, None), Slab("copper", 1.535, 1.57, None, None, "F.Cu"))
    assert plane_under(PAD, "F.Cu", two, [plane("B.Cu")], {"GND"}) == "B.Cu"  # two layers: the bottom copper


@pytest.mark.parametrize("pieces", [
    [],  # no copper under the pad
    cut(box(-5, -5, 5, 5).difference(Point(0, 0).buffer(0.15))),  # an antipad under it, cut as the pipeline cuts it
    [plane("In1.Cu", shape=box(-5, -5, 0.0, 5)), plane("In1.Cu", shape=box(0.1, -5, 5, 5))],  # a split under it
    [plane("In1.Cu", "SIG")],  # copper of a signal net
    [plane("In1.Cu", "SIG", box(-1, -1, 1, 1)), plane("In2.Cu")]])  # another net's copper between the pad and plane
def test_a_pad_with_no_plane_under_it_has_no_vertical_port(pieces):  # Review Focus 4
    assert plane_under(PAD, "F.Cu", FOUR, pieces, {"GND"}) is None


def test_a_vertical_port_needs_a_mesh_line_inside_its_pad():  # D-11: a coded refusal, never E_INTERNAL
    tiny = box(0.02, 0.02, 0.08, 0.08)  # between the lines at 0 and 0.1
    with pytest.raises(KrsError) as e:
        place(End("P9", tiny, tiny, "F.Cu", "external", ref_layer="In1.Cu"), V_MESH, FOUR, [])
    assert (e.value.code, e.value.params) == ("E_PORT_BOX", {"name": "P9"})
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_model_ports.py -q -k "vertical or plane"`. Expected: FAIL with `cannot import name 'plane_under'`.
- [ ] **Step 3: The port.**
  - **`End`'s docstring** adds: "`ref_layer`, an SI end's only (Stage 4 design 5.5): the copper layer of the plane under its pad, which makes its port vertical; None keeps the port on `layer`."
  - **`plane_under`:**
    - **Docstring:** "The copper layer of the plane a vertical port on `pad`, on copper layer `layer`, takes as its reference (Stage 4 design 5.5): the nearest layer toward the board's middle (down from the top half, up from the bottom half, and on past the middle) on which the copper of one net of `nets` (the ground and power nets), its pieces' union, covers the pad, the 10 µm simplification allowed. None when a layer before it has any copper over the pad's footprint, or when no layer qualifies: no copper, an antipad or a split under the pad, or another net's copper on the way. The union, since the copper pipeline's hole cut splits a plane along any antipad's x into abutting pieces."
    - Index the copper layers bottom up, `i` the pad's. Walk `cu[i - 1::-1]` when `i >= len(cu) / 2`, else `cu[i + 1:]`. On each layer, return its name when, for a net of `nets`, `shapely.union_all` of that layer's pieces of that net, buffered by SIMPLIFY, covers the pad; else return None when any piece on the layer intersects the pad. Return None after the last layer.
    - Mark it `# ponytail: any copper over the pad's footprint on a layer on the way refuses the port, though the sheet crosses only the pad's centre line; a narrower check if real pads need it`.
  - **`vertical`:**
    - **Docstring:** "The vertical lumped port of `end`, an SI end over a plane (Stage 4 design 5.5): a sheet in z from the plane's face (end.ref_layer's slab) to the pad's (end.layer's), starting at the plane, the reference, so that openEMS's u is V_pad − V_plane. Across, the sheet runs along the longer side of the pad's copper shrunk by SIMPLIFY (x on a tie), on the lines inside that copper. It sits at the line across within the copper's bounds nearest their middle, a tie to the lower. Its `nodes` are the plane's cap, the pad's cap, then the plane's and the pad's far faces (the witnesses), the lumped port's order, all at the sheet's middle line (a tie to the lower). E_PORT_BOX when no line lies inside the pad either way."
    - With the plane below, the faces are (plane.z1, pad.z0) and the witnesses (plane.z0, pad.z1); with it above, (plane.z0, pad.z1) and (plane.z1, pad.z0). Every coordinate is a mesh line, as a Python float.
    - Mark it `# ponytail: a sheet across the pad's centre line; a box over the whole pad would need its corners inside a rounded pad's copper`.
  - **`place`** gains its first line, `if end.ref_layer is not None: return vertical(end, mesh, zs)`, and its docstring names the vertical port.
- [ ] **Step 4: Run them again.** `.venv/Scripts/python -m pytest tests/test_model_ports.py tests/test_golden_antenna.py tests/test_golden_v1.py -q`. Expected: PASS. The reviser's prototype of `plane_under` gave every case above, In2.Cu for an F.Cu pad over a bare In1.Cu on a six-layer S-S-G-P-S-S stack, and In3.Cu for its bottom pad.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/model/ports.py tests/test_model_ports.py
git commit -m "feat(ports): the vertical port, a 50 ohm lumped sheet in z from the nearest plane under a pad to the pad across its centre line, for SI ends only, and the plane it takes: one net's copper covering the pad, past layers bare over it (Stage 4 design 5.5)"
graphify update .
```

---

### Task 7 [code]: The SI pulse and its stop

**Files:**
- Modify `src/kicad_rf_studio/core/model/spec.py`: `dc_pulse`, `round_trip` and `si_t_max`, after `antenna_t_max` (L62–65); its import from `stoprule` gains `FLAT_S` and `WINDOW_S`.
- Modify `src/kicad_rf_studio/stoprule.py`: `stop_window` after `flat_window`; `residual_db` (L45–52); `stop_rule` (L60–83).
- Test: `tests/test_model_spec.py`, `tests/test_stoprule.py` and `tests/test_model_csx.py`.

**Interfaces:**
- Produces:
  - `spec.dc_pulse(f_max: float, t_max: float, window_s: float) -> dict`, with the keys `f1` (0.0), `f2`, `t0`, `t_max`, `window_s`, `flat_s` and `expr`.
  - `spec.round_trip(length_mm: float, eps_eff: float) -> float` and `spec.si_t_max(f_max: float, round_trip_s: float) -> float`, both in s.
  - `stoprule.stop_window(round_trip_s: float) -> float` and `stoprule.residual_db(rec: Records, window: float = WINDOW_S) -> np.ndarray`.
  - `stop_rule` reads `exc.get("window_s", WINDOW_S)`.
- `build_csx` is unchanged: `SetCustomExcite(expr, f2, f2)` takes the DC pulse as it takes v1's. `pipeline.last_sample` keeps the 2 ns window (plan 2). v1's and the antenna's excitations are Task 1's pins.

- [ ] **Step 1: Write the failing tests.** In `tests/test_model_spec.py` (imports gain `dc_pulse`, `round_trip`, `si_t_max`, and `stop_window` from `stoprule`):

```python
def test_the_si_pulse_is_openems_gaussian_from_dc_to_f_max():  # Stage 4 design 5.4
    p = dc_pulse(10e9, 10e-9, 2e-9)
    assert (p["f1"], p["f2"], p["t_max"], p["window_s"], p["flat_s"]) == (0.0, 10e9, 10e-9, 2e-9, 5e-9)
    assert p["t0"] == 9 / (2 * math.pi * 10e9)
    assert p["expr"] == "exp(-(2*pi*10000000000*t/3-3)^2)*(t<2.86478897565e-10)"  # openEMS's Gaussian at f0 = 0
    assert dc_pulse(10e9, 25e-9, 5.4e-9)["flat_s"] == pytest.approx(8.4e-9)  # the flat window past the residual's


def test_the_si_round_trip_t_max_and_stop_window():  # Stage 4 design 5.4
    rt = round_trip(100.0, 3.3)
    assert rt == pytest.approx(1.2119e-9, rel=1e-4)  # 2 × 100 mm at εeff 3.3
    assert (si_t_max(10e9, rt), stop_window(rt)) == (10e-9, 2e-9)  # 0.29 + 7.27 + 2 ns, up to a whole ns; 2 ns floor
    rt = round_trip(300.0, 3.3)
    assert (si_t_max(10e9, rt), stop_window(rt)) == (25e-9, pytest.approx(5.4535e-9, rel=1e-4))
```

  In `tests/test_model_csx.py` (imports gain `dc_pulse`):

```python
def test_the_si_pulse_goes_through_v1s_custom_excitation(monkeypatch):  # Stage 4 design 5.4
    log = fake_openems(monkeypatch)
    exc = dc_pulse(10e9, 10e-9, 2e-9)
    build_csx({**TINY, "excitation": exc}, 1, 10e-9)
    assert ("SetCustomExcite", (exc["expr"], 10e9, 10e9), {}) in log and ("SetMaxTime", (10e-9,), {}) in log
    assert log[0] == ("openEMS", (), {"EndCriteria": 1e-15})  # the port residual alone stops it (design 5.4)
```

  In `tests/test_stoprule.py` (imports gain `Z0` and `stop_window` from `stoprule`, and `dc_pulse` from `core.model.spec`):

```python
F_MAX = 10e9
SI = dc_pulse(F_MAX, 30e-9, 2e-9)  # f1 0, window_s 2 ns, flat_s 5 ns


def far_end(delay, offset=0.0, dt=2e-12, t_end=30e-9):
    """A 2-port record of SI's pulse sent into a matched line at port 1 and arriving at port 2 `delay` later, half its
    size; `offset` a level that stays on port 1 after the pulse, a charge its port cannot drain. Its log energy is held
    at 1, as openEMS's field energy under the DC pulse hardly decays (design 5.4; r1: −1.43 dB in 30 ns): the ports'
    own power falls to 0 between the pulses, which the growth detector would read as growth."""
    def pulse(t):
        return np.exp(-(2 * math.pi * F_MAX * t / 3 - 3) ** 2) * (t < 2 * SI["t0"])

    t_u = np.arange(0, t_end, dt)
    t_i = t_u + dt / 2
    u = np.array([pulse(t_u) + offset * (t_u > 2 * SI["t0"]), 0.5 * pulse(t_u - delay)])
    i = np.array([pulse(t_i), -0.5 * pulse(t_i - delay)]) / Z0
    return Records(t_u, u, t_i, i, t_u, np.ones_like(t_u))


def test_a_pulse_still_travelling_on_a_long_line_never_reads_as_converged():  # design 5.4; Review Focus 5
    rec = far_end(5e-9)  # 5 ns one way: a 10 ns round trip
    early = stop_rule(rec, 0, "normal", SI)  # the 2 ns window: converged at 2.27 ns, before port 2 sees anything
    assert early.kind == "converged" and early.t < 5e-9
    late = stop_rule(rec, 0, "normal", dc_pulse(F_MAX, 30e-9, stop_window(10e-9)))  # 15 ns, its flat window 18 ns
    assert late.kind == "converged" and 20e-9 < late.t < 21e-9  # 20.26 ns: the far end's pulse has left the window


def test_a_port_level_the_dc_pulse_leaves_behind_ends_flat_not_converged():  # design 5.4; Review Focus 5
    v = stop_rule(far_end(1e-9, offset=1e-2), 0, "normal", SI)  # a floating charge holding 1 % on port 1
    assert (v.kind, round(v.residual_db)) == ("flat", -43) and v.t < 10e-9  # 8.248 ns: S kept, flagged
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_model_spec.py tests/test_stoprule.py tests/test_model_csx.py -q`. Expected: FAIL with `cannot import name 'dc_pulse'`.
- [ ] **Step 3: `spec.py`.**
  - **`dc_pulse`:**
    - **Docstring:** "An SI project's pulse (Stage 4 design 5.4): openEMS's Gaussian with f0 = 0 and fc = f_max as a custom expression, exp(−(2π·f_max·t/3 − 3)²) cut at 2·t0, t0 = 9/(2π·f_max), which build_csx passes as v1's with f2 = f_max. f1 is 0: the DC point is measured. `window_s` is the residual's window (stop_window), and "flat_s" is FLAT_S + (window_s − WINDOW_S). A residual window W holds the residual at its last peak for W, so a flat window under W would call every SI run flat."
    - The expression is `f"exp(-(2*pi*{f_max:.12g}*t/3-3)^2)*(t<{2 * t0:.12g})"`, in pulse()'s number format.
  - **`round_trip`** returns `2 * length_mm * 1e-3 * math.sqrt(eps_eff) / scipy.constants.c`. Its docstring: "A line's round trip in s, from its length and its 2D εeff (Stage 4 design 5.4)."
  - **`si_t_max`** returns `math.ceil((9 / (math.pi * f_max) + 6 * round_trip_s + 2e-9) * 1e9) / 1e9`. Its docstring: "An SI project's default T_max in s (Stage 4 design 5.4): the pulse's length 2·t0, plus 6 of the longest round trips, plus 2 ns, rounded up to a whole ns as antenna_t_max does (A-28)."
- [ ] **Step 4: `stoprule.py`.**
  - **`stop_window`** returns `max(WINDOW_S, 1.5 * round_trip_s)`. Its docstring: "An SI run's residual window in s (Stage 4 design 5.4): 1.5 × the longest port-to-port round trip, at least WINDOW_S, so a pulse still travelling on a long line cannot read as converged."
  - **`residual_db(rec, window=WINDOW_S)`** uses its argument, and its docstring says so.
  - **`stop_rule`** computes `r_db = residual_db(rec, exc.get("window_s", WINDOW_S))`, and its docstring names "an SI pulse's "window_s"". `_rises` keeps WINDOW_S: the growth detector is v1's. At the growth call: `# ponytail: the growth detector keeps v1's 2 ns window under an SI pulse, whose field energy holds; an SI ruling if P4-D sees false growth`.
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_antenna.py tests/test_golden_v1.py tests/test_run.py -q`. Expected: PASS. The reviser's replay of these records under this rule gave the verdicts in the tests' comments.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/model/spec.py src/kicad_rf_studio/stoprule.py tests/test_model_spec.py tests/test_stoprule.py tests/test_model_csx.py
git commit -m "feat(model): the SI pulse, a Gaussian from DC to f_max through v1's custom excitation, its residual and flat windows, and T_max = pulse + 6 round trips + 2 ns; the stop rule reads window_s (Stage 4 design 5.4)"
graphify update .
```

---

### Task 8 [code]: The Debye dielectric

**Files:**
- Modify `src/kicad_rf_studio/core/model/spec.py`: `DEBYE_F_REF`, `DEBYE_DECADES` and `debye`, after `kappa` (L139–142), with `from scipy.optimize import nnls`.
- Modify `src/kicad_rf_studio/core/model/csx.py`: `import math`, the materials loop (L54–57) and `build_csx`'s docstring.
- Test: `tests/test_model_spec.py` and `tests/test_model_csx.py`.

**Interfaces:**
- Produces:
  - `spec.DEBYE_F_REF = 1e9` and `spec.DEBYE_DECADES = 2`.
  - `spec.debye(eps_r: float, tan_d: float, f_max: float) -> dict`, which returns `{"eps_inf": float, "delta": [float, ...], "f_relax_hz": [float, ...]}`.
  - A model spec material's optional `"debye"` key, in that shape, which `build_csx` reads. Plan 2 writes it for an SI dielectric with a loss tangent when the dielectric model is Debye.

- [ ] **Step 1: Write the failing tests.** In `tests/test_model_spec.py` (imports gain `numpy as np`, `DEBYE_F_REF` and `debye`):

```python
def debye_eps(d, f):
    """ε(f) of a debye() entry: ε∞ + Σ Δε/(1 + j·f/f_relax)."""
    return d["eps_inf"] + sum(de / (1 + 1j * f / fr) for de, fr in zip(d["delta"], d["f_relax_hz"]))


@pytest.mark.parametrize(("eps_r", "tan_d", "tol"), [(4.3, 0.02, 0.07), (3.66, 0.004, 0.06)])  # FR-4; a low-loss one
def test_a_debye_fit_holds_the_loss_tangent_across_the_band_and_none_at_dc(eps_r, tan_d, tol):  # design 5.3
    d = debye(eps_r, tan_d, 10e9)
    assert d["f_relax_hz"] == [1e8, 1e9, 1e10]  # one pole a decade, f_max/100 to f_max
    assert all(v > 0 for v in d["delta"]) and 1 <= d["eps_inf"] < eps_r  # no negative pole, nothing below vacuum
    e = debye_eps(d, np.geomspace(1e8, 1e10, 401))
    assert np.abs(-e.imag / e.real / tan_d - 1).max() <= tol  # measured 6.0 % and 4.9 %
    assert debye_eps(d, np.array([DEBYE_F_REF]))[0].real == pytest.approx(eps_r, rel=0.005)
    assert debye_eps(d, np.array([0.0]))[0].imag == 0.0  # no κ: no DC loss
    low = debye_eps(d, np.array([1e5]))[0]
    assert -low.imag / low.real <= 0.01 * tan_d


@pytest.mark.parametrize(("eps_r", "tan_d"), [(1.5, 0.3), (4.3, 0.0)])  # ε∞ would fall under 1; no loss to fit
def test_a_debye_fit_below_vacuum_or_without_loss_is_refused(eps_r, tan_d):  # design 5.3
    with pytest.raises(ValueError, match="Debye"):
        debye(eps_r, tan_d, 10e9)
```

  In `tests/test_model_csx.py` (imports gain `math`):

```python
def test_a_debye_material_is_csxcads_debye_property_and_a_plain_one_is_not(monkeypatch):  # 5.3; SI keys only in SI
    log = fake_openems(monkeypatch)
    monkeypatch.setitem(sys.modules, "CSXCAD.CSProperties",
                        types.SimpleNamespace(CSPropDebyeMaterial=Rec(log, "CSPropDebyeMaterial")))
    db = {"eps_inf": 4.0, "delta": [0.2, 0.1], "f_relax_hz": [1e9, 1e10]}
    build_csx({**TINY, "materials": [{**TINY["materials"][0], "kappa": 0.0, "debye": db}]}, 1, 1e-9)
    assert [kw for n, _, kw in log if n == "CSPropDebyeMaterial"] == [{"order": 2, "name": "substrate_0", "epsilon": 4.0}]
    assert [(a, kw) for n, a, kw in log if n == "SetDispersiveMaterialProperty"] == [
        ((0,), {"eps_delta": 0.2, "eps_relax": 1 / (2 * math.pi * 1e9)}),  # relaxation times, in s
        ((1,), {"eps_delta": 0.1, "eps_relax": 1 / (2 * math.pi * 1e10)})]
    names = [n for n, _, _ in log]
    assert "AddProperty" in names and "AddMaterial" not in names  # no κ
    assert [kw["priority"] for n, _, kw in log if n == "AddLinPoly"] == [10, METAL_PRIORITY]
    log.clear()
    build_csx(TINY, 1, 1e-9)  # a v1 spec: the plain material, as before
    assert ("AddMaterial", ("substrate_0",), {"epsilon": 4.5, "kappa": 0.0046}) in log
    assert "CSPropDebyeMaterial" not in [n for n, _, _ in log]
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_model_spec.py tests/test_model_csx.py -q -k debye`. Expected: FAIL with `cannot import name 'DEBYE_F_REF'`.
- [ ] **Step 3: `debye`,** as given (its points, weights and poles set the tolerances above):

```python
DEBYE_F_REF = 1e9  # Hz: where a stackup's εr and tan δ are taken to hold
DEBYE_DECADES = 2  # the fit's band, f_max/100 to f_max: gate P4-D's 0.1 GHz to f_max at 10 GHz (Stage 4 design 5.11)


def debye(eps_r: float, tan_d: float, f_max: float) -> dict:
    """An SI dielectric's Debye model (Stage 4 design 5.3), a model spec material's "debye": ε(f) = ε∞ + Σ Δε/(1 +
    j·f/f_relax), one pole a decade at f_max/10^k, k = DEBYE_DECADES down to 0. It is fitted in the Djordjevic–Sarkar
    manner to `eps_r` and `tan_d` at DEBYE_F_REF, ε″ = εr·tan δ flat and ε′ = εr − (2/π)·ε″·ln(f/DEBYE_F_REF), on 61
    log-spaced points from the first pole to f_max, its ε″ rows weighted 1/tan δ, by non-negative least squares: every
    Δε ≥ 0, a pole that takes 0 dropped, and no κ, so no DC loss. ValueError ("Debye") for a tan δ of 0 or less, and for
    an ε∞ under 1, a fit below vacuum."""
    # ponytail: one pole a decade ripples tan δ by about 6 % on FR-4 (−4.7 to +4.8 % against Djordjevic–Sarkar's
    # ε″/√ε′); gate P4-D may ask for poles past the band's edges (4 from f_max/10^2.2 to f_max·10^0.2 read 3.9 %),
    # at a higher cell weight
    if tan_d <= 0:
        raise ValueError(f"a Debye fit needs a loss tangent above 0, not {tan_d}")
    poles = [f_max / 10 ** k for k in range(DEBYE_DECADES, -1, -1)]
    f = np.geomspace(poles[0], f_max, 61)
    cols = [1 / (1 + 1j * f / p) for p in poles]
    a = np.vstack([np.r_[np.ones_like(f), np.zeros_like(f)], *(np.r_[c.real, -c.imag / tan_d] for c in cols)]).T
    b = np.r_[eps_r - 2 / math.pi * eps_r * tan_d * np.log(f / DEBYE_F_REF), np.full(f.size, eps_r)]
    x, _ = nnls(a, b)
    if x[0] < 1:
        raise ValueError(f"a Debye fit below vacuum: ε∞ {x[0]:.3f} under 1 (εr {eps_r}, tan δ {tan_d})")
    keep = x[1:] > 0
    return {"eps_inf": float(x[0]), "delta": x[1:][keep].tolist(),
            "f_relax_hz": [p for p, k in zip(poles, keep) if k]}
```

- [ ] **Step 4: `build_csx`.**
  - In the materials loop, a material with `"debye"` (`db`) becomes `CSPropDebyeMaterial(csx.GetParameterSet(), order=len(db["delta"]), name=m["name"], epsilon=db["eps_inf"])`, imported from `CSXCAD.CSProperties` inside that branch only, as openEMS is: a worker's import.
  - Each pole k gets `material.SetDispersiveMaterialProperty(k, eps_delta=Δε_k, eps_relax=1 / (2 * math.pi * f_relax_k))`, a relaxation time in s. Then `csx.AddProperty(material)` adds it.
  - A material without the key keeps `csx.AddMaterial(m["name"], epsilon=m["eps"], kappa=m["kappa"])`. Either goes to `_prism` with its solids, as now.
  - The docstring adds: "A material with the SI-only key "debye" ({"eps_inf", "delta", "f_relax_hz"}, Stage 4 design 5.3) is CSXCAD's CSPropDebyeMaterial, each pole's relaxation time 1/(2π·f_relax); its κ is ignored. openEMS 0.37 puts each pole on an edge at the edge's own point, over its whole area (operator_ext_debyematerial.cpp), where the static ε is averaged over the quarter cells, so the edges on a Debye substrate's top face carry its full Δε over dual cells half in air: a stated limit gate P4-D isolates."
- [ ] **Step 5: Run them again.** Step 2's command without `-k`, then `.venv/Scripts/python -m pytest tests/test_golden_antenna.py tests/test_golden_v1.py tests/test_worker.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/model/spec.py src/kicad_rf_studio/core/model/csx.py tests/test_model_spec.py tests/test_model_csx.py
git commit -m "feat(model): the Debye dielectric for SI specs, a one-pole-a-decade fit of er and tan d at 1 GHz in the Djordjevic-Sarkar manner, built as CSXCAD's CSPropDebyeMaterial with no kappa (Stage 4 design 5.3)"
graphify update .
```

---

### Task 9 [code]: Gate P4-A

**Files:**
- Create: `tests/fixtures/p4a/references.json` and `tests/test_p4a.py`.
- Modify: `tools/p4a.py`, part 2.

**Interfaces:**
- Consumes:
  - `cs2d.pair`, and `p4a.cohn`, `stripline_pair`, `ms_pair` and `even_odd_s`.
  - `si.uniform_grid`, `tdr` and `LOCAL_RISE`.
  - `p0.FIX`, `p0.save`, `p0.table` and `p0.versions`.
  - `kicad_lines.coupled_microstrip` in `tests/test_p4a.py` only: `measure()` reads the formulas' values from `REFS`.
- Produces: `p4a.REFS`, `p4a.measure() -> dict` (`{"rows": [...], "verdict": "pass" | "fail"}`) and `p4a.main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: The references,** `tests/fixtures/p4a/references.json`, committed before the gate's run and never regenerated (design §5.11). The values are the formulas' as of this plan; a case's own `t_mm` overrides its group's:

```json
{"source": "Stage 4 design 5.11, gate P4-A: Cohn's exact zero-thickness edge-coupled stripline (S. B. Cohn, IRE Trans. MTT 3(5), 1955; tools/p4a.py cohn); Kirschning and Jansen's coupled microstrip, quasi-static with no cover, as KiCad 9.0's calculator computes it (pcb_calculator/transline/c_microstrip.cpp; tests/kicad_lines.py coupled_microstrip); the even/odd 4-port of a uniform lossless pair (tools/p4a.py even_odd_s); an ideal 60 ohm line between 50 ohm ports. A case's own t_mm overrides its group's.",
 "cohn": {"t_mm": 0.0001, "limit": 0.005, "cases": [
  {"w": 0.15, "s": 0.15, "b": 0.5, "er": 4.3, "z_even": 71.98342405099247, "z_odd": 52.01461048031955},
  {"w": 0.2, "s": 0.2, "b": 0.6, "er": 4.3, "z_even": 67.40168654593361, "z_odd": 50.86779321065293},
  {"w": 0.3, "s": 0.1, "b": 0.5, "er": 4.3, "z_even": 50.23427299274296, "z_odd": 35.51848782321822},
  {"w": 0.1, "s": 0.3, "b": 0.4, "er": 4.3, "z_even": 70.20240112588493, "z_odd": 64.80026504967648}]},
 "kj_1um": {"t_mm": 0.001, "limit": 0.03, "cases": [
  {"w": 0.15, "s": 0.15, "h": 0.2, "er": 4.3, "z_even": 97.1232802849029, "eps_even": 3.249327590191874, "z_odd": 65.3666499716574, "eps_odd": 2.7706356176104663},
  {"w": 0.2, "s": 0.15, "h": 0.2, "er": 4.3, "z_even": 84.30662805401742, "eps_even": 3.3163721381158924, "z_odd": 57.98344450068376, "eps_odd": 2.806460633589963},
  {"w": 0.5, "s": 0.5, "h": 1.0, "er": 4.5, "z_even": 118.74442214862536, "eps_even": 3.29194691205046, "z_odd": 68.20906264670947, "eps_odd": 2.816993971162812},
  {"w": 1.0, "s": 0.3, "h": 1.5, "er": 4.5, "z_even": 113.05710843070086, "eps_even": 3.330009916997594, "z_odd": 49.67941809199963, "eps_odd": 2.8046458927388223}]},
 "kj_35um": {"t_mm": 0.035, "limit": 0.05, "cases": [
  {"w": 0.5, "s": 0.5, "h": 1.0, "er": 4.5, "z_even": 120.2953356947341, "eps_even": 3.288029518974082, "z_odd": 66.89353287968208, "eps_odd": 2.829986140855531},
  {"w": 1.0, "s": 0.3, "h": 1.5, "er": 4.5, "z_even": 113.8467971645535, "eps_even": 3.3289028663936624, "z_odd": 49.02436030751428, "eps_odd": 2.813901231029615},
  {"w": 0.6, "s": 0.6, "h": 1.5, "er": 4.5, "z_even": 134.4796342831145, "eps_even": 3.242019437992506, "z_odd": 68.24462487539876, "eps_odd": 2.805699126510386}]},
 "kj_recorded": {"t_mm": 0.035, "limit": null, "cases": [
  {"w": 0.15, "s": 0.15, "h": 0.2, "er": 4.3, "t_mm": 0.018, "z_even": 98.79154746313598, "eps_even": 3.236372605411727, "z_odd": 63.83106586042997, "eps_odd": 2.798536029747614},
  {"w": 0.15, "s": 0.15, "h": 0.2, "er": 4.3, "z_even": 100.11659603731445, "eps_even": 3.2167332716612065, "z_odd": 62.79235617601896, "eps_odd": 2.8201147786863157}]},
 "identity": {"limit": 1e-9, "length_mm": 50.0},
 "tdr": {"z_line": 60.0, "z_ref": 50.0, "eps": 4.0, "length_mm": 50.0, "f_max_hz": 1e10}}
```

- [ ] **Step 2: Write the failing tests,** `tests/test_p4a.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

import kicad_lines
import p4a


@pytest.fixture(scope="module")
def measured():
    return p4a.measure()  # about 12 s: thirteen cs2d pairs of three solves each


def test_p4a_passes(measured):  # Stage 4 design 5.11: P4-A in CI; a failure is a code bug, which blocks Stage 4
    rows = measured["rows"]
    assert [r for r in rows if r["pass"] is False] == [] and measured["verdict"] == "pass"
    assert {r["check"] for r in rows} == {"cohn", "kj_1um", "kj_35um", "kj_recorded", "identity", "tdr"}
    assert [r["check"] for r in rows].count("cohn") == 8 and len(rows) == 50  # 8 + 16 + 12 + 8 + 4 + 2
    assert all(r["pass"] is None for r in rows if r["check"] == "kj_recorded")  # recorded, never gated
    assert [r["quantity"] for r in rows if r["check"] == "kj_35um" and r["pass"] is None] == ["eps_even", "eps_odd"] * 3


def test_the_references_are_the_formulas_as_ported():  # design 5.11: committed before the gate, never regenerated
    for c in p4a.REFS["cohn"]["cases"]:
        assert p4a.cohn(c["w"], c["s"], c["b"], c["er"]) == pytest.approx((c["z_even"], c["z_odd"]), rel=1e-12)
    for key in ("kj_1um", "kj_35um", "kj_recorded"):
        for c in p4a.REFS[key]["cases"]:
            t = c.get("t_mm", p4a.REFS[key]["t_mm"])  # a case's own thickness, else its group's
            assert kicad_lines.coupled_microstrip(c["w"], c["s"], c["h"], t, c["er"]) == pytest.approx(
                (c["z_even"], c["eps_even"], c["z_odd"], c["eps_odd"]), rel=1e-9)


def test_p4a_writes_its_record(measured, tmp_path, monkeypatch):  # design 5.11: a short report under docs/validation
    monkeypatch.setattr(p4a, "measure", lambda: measured)
    assert p4a.main(["--out", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "p4a" / "p4a.json").read_text(encoding="utf-8"))
    assert (data["gate"], data["verdict"], len(data["rows"])) == ("P4-A", "pass", 50) and data["wall_s"] >= 0
    assert (tmp_path / "p4a" / "p4a.md").read_text(encoding="utf-8").startswith("## P4A-1 Checks")
```

- [ ] **Step 3: Run them.** `.venv/Scripts/python -m pytest tests/test_p4a.py -q`. Expected: FAIL with `AttributeError: module 'p4a' has no attribute 'measure'` (and `'REFS'`).
- [ ] **Step 4: The gate.**
  - **The docstring** adds: "Part 2: the gate. measure() checks cs2d's pair against REFS (Cohn at 0.1 µm; Kirschning–Jansen at 1 µm, and at 35 µm on 1.0 and 1.5 mm substrates; the fixtures' 0.2 mm stack recorded at 18 and 35 µm), the even/odd 4-port's identities and the TDR on an ideal line; tests/test_p4a.py runs it in CI. Dev-time: `python tools/p4a.py --out DIR` writes p4a.json and p4a.md in DIR/p4a for docs/validation/."
  - **`REFS`** is `json.loads((p0.FIX / "p4a" / "references.json").read_text(encoding="utf-8"))`.
  - **`measure()`** returns `{"rows": rows, "verdict": "fail" if any row's pass is False else "pass"}`. Each row is `{"check", "case", "quantity", "reference", "measured", "error", "limit", "pass"}`, with `case` a short text of its geometry, such as "w 0.15 s 0.15 b 0.5 er 4.3", plus "t 0.018" where the case sets its own `t_mm`. The rows, in order:
    - **`cohn`:** per case, `z_even` and `z_odd` of `pair(stripline_pair(w, s, b, t_mm, er))`. The error is measured/reference − 1, and a row passes at |error| ≤ limit.
    - **`kj_1um`:** per case, `z_even`, `eps_even`, `z_odd` and `eps_odd` of `pair(ms_pair(w, s, h, t, er))`, t the case's `t_mm`, else the group's, the same way.
    - **`kj_35um`:** the same four, the εeff rows with limit and pass None.
    - **`kj_recorded`:** the four per case, with limit and pass None.
    - **`identity`:** the error is |measured − reference|, and a row passes at ≤ 1e-9.
      - With the first Cohn case's reference Ze and Zo, both modes at its εr, over `identity.length_mm`, `even_odd_s` at z_ref √(Ze·Zo), on 301 points to three quarter waves plus the quarter wave f_q: `fext`, max |S41|, reference 0; `s11`, max |S11|, reference 0; `next_peak`, |S21(f_q)|, reference k.
      - `bounce`: REFS["tdr"]'s line, `z_line` in both modes at `eps` over its `length_mm`, at its `z_ref`, uncoupled: its largest |S11 − Γ(1 − x)/(1 − Γ²x)| on 401 points to `f_max_hz`, reference 0.
    - **`tdr`:** Task 3's ideal line, REFS["tdr"], on `uniform_grid(f_max_hz)` at `LOCAL_RISE / f_max_hz`, τ its one-way delay:
      - `plateau`: Z at τ, reference `z_line`;
      - `late`: for t from 4τ + 4·t_r up to 20 ns, as in Task 3's test, the Z farthest from `z_ref`, reference `z_ref`.

      The error is measured − reference, the limit 0.05 Ω, and a row passes at |error| < limit: the design's "60.0 then 50.0 Ω", to one decimal.
  - **`main(argv)`:**
    - argparse with `--out` alone, required.
    - `m = measure()`, timed with `time.perf_counter()`, then `p0.save(out / "p4a" / "p4a.json", {"gate": "P4-A", "versions": p0.versions(), "references": REFS, "wall_s": wall_s, **m})`.
    - Write `p4a.md` beside it: `"## P4A-1 Checks\n\n" + p0.table(m["rows"], ["check", "case", "quantity", "reference", "measured", "error", "limit", "pass"]) + "\n"`.
    - Return 0 for a pass, else 1. `if __name__ == "__main__": sys.exit(main())`.
- [ ] **Step 5: Run them again.** `.venv/Scripts/python -m pytest tests/test_p4a.py tests/test_cs2d.py tests/test_post_si.py tests/test_repo.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/p4a.py tests/test_p4a.py tests/fixtures/p4a/references.json
git commit -m "feat(tools): gate P4-A in CI, cs2d's pair against Cohn and Kirschning-Jansen, the even/odd 4-port's identities and the TDR on an ideal line, against references committed in tests/fixtures/p4a (Stage 4 design 5.11)"
graphify update .
```

---

### Task 10 [run]: P4-A's record and the amendments

This task commits the report, its JSON, the amendments and any fix a failure needs. Every other file it makes stays under `$env:TEMP`. Run each PowerShell block as one call.

- [ ] **Step 1: The suite at the branch tip.** Run the full suite in the background and wait for it. Then run the GUI tests in pt-BR, in one call: `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass. Record the counts.
- [ ] **Step 2: Run P4-A's tool:**

```powershell
$out = Join-Path $env:TEMP 'krs-p4a'
.venv\Scripts\python.exe -X utf8 tools\p4a.py --out $out
"exit $LASTEXITCODE"
```

  Expected: `exit 0` in about 15 s, with `$out\p4a\p4a.json` and `p4a.md`. The prototypes predict:
  - Cohn: −0.19 to −0.37 %;
  - Kirschning–Jansen: within 1.4 % at 1 µm, and within 3.93 % in Z at 35 µm;
  - the fixtures' 0.2 mm stack, recorded: Z −6.1 % and −5.5 % at 18 µm, −9.4 % and −9.3 % at 35 µm;
  - every identity under 1e-14;
  - the TDR at 59.999 Ω, then within 0.0014 Ω of 50.
- [ ] **Step 3: Read the gate.**
  - A failed row gets superpowers:systematic-debugging. A bug is fixed test-first in the module that owns it: a tier (a) test that fails first, the full suite, `git commit -m "fix(<area>): <what> (P4-A)"`, then Step 2 again.
  - A limit never changes (design §5.11). A miss that is not a bug stops the plan for a controller ruling, which the report records.
- [ ] **Step 4: The report,** `docs/validation/<the run's date, YYYY-MM-DD>-p4-a.md`, in the P3-A report's sections:
  1. **Verdict.**
  2. **Inputs:** the command, `versions`, `tests/fixtures/p4a/references.json`, and the cases with why each one.
  3. **Measured value against limit:** P4A-1, the tool's table.
  4. **Decisions:**
     - "thin copper" for Cohn is 0.1 µm;
     - Kirschning–Jansen at 35 µm is gated in Z on 1.0 and 1.5 mm substrates, where t/h ≤ 0.035; its εeff rows, and the fixtures' 0.2 mm stack at 18 and 35 µm, are recorded;
     - the identities are read at a reference of √(Ze·Zo), and "a step's Γ" as the bounce series of an uncoupled line;
     - "then 50.0 Ω" is read after the line's second round trip, from 4τ + 4·t_r.
  5. **Stated limits and deviations:**
     - At 0.1 µm cs2d reads −0.19 to −0.37 % against Cohn's zero thickness, of which −0.14 to −0.24 % is cs2d's own grid (its reading at 0.01 µm) and the rest the strips' thickness. At 1 µm it reads −0.63 to −1.36 %, outside 0.5 %. A later change to cs2d's GRADE or COARSE moves these rows by tenths of a percent with no bug involved.
     - The microstrip pairs sit in cs2d's reference box (REF_H 10, a grounded box 10 h past the strips): at 1 µm it holds about 0.5 % of Zeven's −1.32 % against Kirschning–Jansen, and nearly all of εeven's −0.75 % (−0.79 % and −0.03 % in a box 40 h out); the odd mode does not move. Plan 2's 2D table carries the same bias on Zeven and Zcomm.
     - KiCad's coupled microstrip builds on a zero-thickness single line (`compute_single_line`), so its thickness terms raise Zeven and εodd as the copper thickens, where both must fall. On the fixtures' stack its Zeven reads 96.99, 98.79 and 100.12 Ω at 0, 18 and 35 µm, and its εodd 2.768, 2.799 and 2.820, while cs2d's read 95.84 Ω and 2.746 at 1 µm, 92.72 Ω and 2.586 at 18 µm, and 90.73 Ω and 2.474 at 35 µm. So cs2d reads Zeven and Zodd 9.4 % and 9.3 % under KiCad's at 35 µm, where r1's openEMS probe read cs2d's Zdiff within 1.9 % (116.0 Ω against r1's cs2d 113.8 Ω). The 35 µm limit is met where t/h ≤ 0.035; εeff at 35 µm is recorded, cs2d's εodd 4.3–5.0 % under KiCad's on the gated cases. This is KiCad's coding of the formula, as `tests/test_cs2d.py`'s ruling found for Hammerstad–Jensen and KiCad's CPWG at 35 µm.
     - P4-B's "Zdiff within 5 % of KiCad's calculator" therefore cannot hold on that stack for a correct solver (KiCad 125.6 Ω, cs2d 113.9 Ω, r1's FDTD 116.0 Ω): plan 4 rules on it before P4-B runs.
     - Between 2τ and 4τ the TDR reads 50.075 Ω, the line's own Γ³.
  6. **Machine time:** predicted seconds against `p4a.json`'s `wall_s`.
  7. **Next step:** Stage 4's plan 2, the SI project.

  Copy `$out\p4a\p4a.json` to `docs/validation/<date>-p4-a.json`; it holds no path and no host name.
- [ ] **Step 5: The amendments,** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`:
  - **A-41, §2's table (L75):** before the `Later` row, add `| 4 | Signal integrity of a net or a differential pair: the TDR, mixed-mode S and crosstalk, with relative results | ` + "`docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md`" + ` (A-41, Stage 4 plan 1: controller recommendation, owner unavailable.) |`. The `Later` row's content becomes `EMC, a GPU engine, a bundled installer`.
  - **A-42, §5.3:** a bullet after the antennas' bullet (L294): "- **Signal integrity** (Stage 4): an SI project's copper is solid, never openEMS's conducting sheet, which read a coupled pair's Zdiff 11 % high in the Stage 4 research's probe and takes its thickness in metres whatever the drawing unit. Its dielectric is lossless, or a Debye fit of the stackup's εr and tan δ at 1 GHz in the Djordjevic–Sarkar manner: one pole a decade from f_max/100 to f_max, each Δε positive, ε∞ at least 1 and no DC loss, built as CSXCAD's CSPropDebyeMaterial. This section's constant κ is never used for SI: it gives a flat loss and a DC leakage. Gate P4-D sets the default. (A-42, Stage 4 plan 1: controller recommendation, owner unavailable.)" In §10, the line `- Debye dielectric loss;` (L673) becomes `- Debye dielectric loss, except for signal integrity (§5.3, A-42);`.
  - **A-43, §5.4:** a bullet after the antennas' bullet (L313): "- **Signal integrity** (Stage 4): an SI project's d and reach take the thinnest dielectric next to any copper layer its lines use, above or below, not the top layer's alone. Its mesh rule fills at d only the copper edges' patterns and a margin around each via. Between them, inside the protected extent, the cells grade at 1.3 up to max_cell, λ_eff(f_max)/40 by default, and outside the extent up to the coarse cell. On a synthetic 100 mm straight pair the rule placed about 270 lines along the run where the d fill placed about 1,370, and the edge lint passed. Gate P4-C compares it with the d fill, which stays if it fails. The edge lint and fit2d apply unchanged, and an SI project's gates.dt_floor defaults to 0.6, against v1's 0.8, since a staircased 45° track at n 3 read 0.72 of its reference (A-35). (A-43, Stage 4 plan 1: controller recommendation, owner unavailable.)"
  - **A-44, §5.6:** a bullet after "An "unused primitive"…" (L346): "- **The vertical port** (Stage 4): for an SI project only, an end pad with no same-layer reference within the reach gets a 50 Ω lumped port in z. It runs from the nearest plane toward the board's middle to the pad: the first copper layer on which one ground or power net's copper covers the pad, every layer before it bare over the pad's footprint. The port is a sheet across the pad's centre line, along its longer side. Its nodes are the plane's and the pad's faces and their far faces, which the PEC-roots gate checks as any port's. A pad with no such plane (none, an antipad, a split, or another net's copper on the way) has no vertical port. This lifts C-14's "no vertical ports" for SI alone; v1's reference order, and its refusal of a reference on another layer, stay. Gate P4-D compares it with the horizontal port on a pad coupon. (A-44, Stage 4 plan 1: controller recommendation, owner unavailable.)"
  - **A-45, §5.8:** a bullet after the T_max bullet (L372): "- **The SI pulse** (Stage 4): an SI project's pulse is openEMS's Gaussian with f0 = 0 as a custom expression, exp(−(2π·f_max·t/3 − 3)²)·(t < 2·t0) with t0 = 9/(2π·f_max), passed as v1's with f2 = f_max, so its DC point is measured. This section's DC-free pulse stays for v1 and the antennas. (A-45, Stage 4 plan 1: controller recommendation, owner unavailable.)"
  - **A-46, §6.3:** a paragraph after the antennas' paragraph (L420): "**Signal integrity** (Stage 4): with the DC pulse, openEMS's field energy never decays (a soft source leaves a static charge), so the port residual is the only stop and EndCriteria stays 1e-15. The residual's window is max(2 ns, 1.5 × the longest port-to-port round trip), written only in an SI model's excitation as `window_s`, so a pulse still travelling on a long line cannot read as converged. Its flat window is 5 ns plus that window's excess over 2 ns, since a window holds the residual at its last peak for its whole length. T_max defaults to the pulse's length plus 6 of the longest round trips plus 2 ns, rounded up to a whole ns, the round trip from the route's length and the 2D εeff. The growth detector and the other constants stay. (A-46, Stage 4 plan 1: controller recommendation, owner unavailable.)"
  - **A-47:** a new `### 9.10 P4-A: 2D and formulas (Stage 4)` after §9.9's last paragraph (L659), before the `---` above §10: "Stage 4's first gate (Stage 4 design §5.11), in CI: `tests/test_p4a.py` runs `tools/p4a.py`'s checks against `tests/fixtures/p4a/references.json`. cs2d's coupled pair is checked against Cohn's exact zero-thickness coupled stripline at 0.1 µm copper, within 0.5 %. It is checked against Kirschning–Jansen's coupled microstrip, as KiCad 9's calculator computes it, within 3 % in Z and εeff at 1 µm, and within 5 % in Z at 35 µm on 1.0 and 1.5 mm substrates, where t/h ≤ 0.035; εeff at 35 µm is recorded, not gated (cs2d's εodd reads 4.3–5.0 % under KiCad's there). The tool holds the even/odd 4-port of a uniform lossless pair, whose identities hold to 1e-9: a homogeneous stripline's FEXT and S11 are zero at a reference of √(Ze·Zo), NEXT peaks at k at the quarter wave, and a line's S11 is the bounce series of its step's Γ. The TDR routine reads an ideal 60 Ω line as 60.0 Ω, then 50.0 Ω after its second round trip. KiCad's coupled microstrip builds on a zero-thickness single line, so its thickness terms raise Zeven and εodd as the copper thickens, where both must fall: on the fixtures' 0.2 mm stack at 35 µm cs2d reads Zeven and Zodd about 9 % under KiCad's, while an openEMS probe read cs2d's Zdiff within 1.9 %, a stated limit of KiCad's formula, recorded in the report. A failure is a code bug, which blocks Stage 4. Result on <date>: <pass, or the ruling>, `docs/validation/<date>-p4-a.md`. (A-47, Stage 4 plan 1: controller recommendation, owner unavailable.)"
  - **The Status line (L4)** gains, at its end: " On <date>, Stage 4's plan 1 amended §2, §5.3, §5.4, §5.6, §5.8, §6.3, §9 and §10 (A-41 to A-47) the same way."
- [ ] **Step 6: Commit.**

```bash
git add docs/validation/<date>-p4-a.md docs/validation/<date>-p4-a.json docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs(validation): gate P4-A <passed> in CI, cs2d's coupled pair, the even/odd 4-port and the TDR against committed references; Stage 1 spec A-41 to A-47 (Stage 4 design 5.11, 5.13; controller recommendation, owner unavailable)"
graphify update .
```

- [ ] **Step 7: Close.** Run the whole-branch review, and Step 1 again after any later commit. Fast-forward `main` to the branch locally, delete the branch, and delete `$env:TEMP\krs-p4a`. Nothing is pushed.

---

## Not in this plan

- **Plan 2, the SI project:**
  - schema 3 accepted with `_FIELDS_SI` (E_PROJECT_SCHEMA's `expected` becomes 3), and an SI project's gates (`GATES_SI`, dt_floor 0.6, design §5.3), which nothing in plan 1 reads; `new --interface` and its presets (`LOCAL_RISE` refuses a faster link rise time);
  - the lines, the pair, the victims and the ends;
  - when an end is vertical, its project.json shape, and the user-facing refusals with their messages (no plane under a pad, a Debye fit below vacuum), and whether a vertical port's height is capped;
  - the part ports, the shunt-R rule and A-27's capacitors;
  - the SI branches of `build_geometry`, `build_mesh` and `model_spec`, which wire this plan's hooks:
    - `substrate_h` over the lines' layers;
    - `xy_lines` with `si_max_cell` of the 2D εeff and spans over the vias (r1 suggests a 1 mm margin) and staircased copper;
    - `dc_pulse` with `stop_window` and `si_t_max`, and whether T_max's default covers the flat window on a short route;
    - lossless or `debye` materials;
    - MUR and the SI gates;
  - fit2d on coupled sections (`pair` on the mesh lines); cost's 2D table, its reference box (REF_H 10 reads Zeven about 0.5 % low), the job breakdown, the Debye weight and the short-route note;
  - a run that writes the layout Touchstone file, and the fixtures;
  - `pipeline.last_sample` with `window_s`;
  - the amendments to §6.4 and §10 (SI and differential pairs leave the deferred list, design §5.13).
- **Plan 3, the SI results:** the grid from the waves, the two TDRs and the TDT, mixed mode, skew, NEXT and FEXT, the loss lines, the outputs, the SI retune and verify, `compare`, and §7's amendment.
- **Plan 4, the gates:**
  - P4-B to P4-F and the defaults they set (n, the mesh rule, the dielectric model and its pole count, the thresholds, the 45° rule), the cost refit, and §9's P4-B to P4-G. P4-G stays the owner's.
  - §5.4's fallback, if P4-D finds a model whose port residual does not decay with the DC pulse: Stage 1 §5.8's DC-free pulse, with the DC point from the copper's resistive nodal solve with the ports as 50 Ω, and the gap to the first trusted point interpolated (r3).
  - P4-B's "5 % of KiCad's calculator" on the 0.2 mm/35 µm stack, which needs a ruling before P4-B runs (the Kirschning–Jansen ruling below).
  - P4-D's isolation of the Debye edges on a substrate's top face, and its coupon's vertical port height (the Debye and vertical-port rulings).
- **Plan 5:** the GUI, the button, the README tutorial, the acceptance run and the exit record.
- **KiCad 10's coupled stripline** (Cohn with a thickness term): P4-A uses Cohn's zero-thickness form at 0.1 µm.
- **A (1, −1) excitation in cs2d:** `pair` calls `solve` three times; plan 2 adds the faster path only if fit2d on coupled sections needs the 1.5 times.
- **Output pins in another environment:** as v1's, the antenna's outputs and the 2D readouts compare only where `golden_v1.env()` matches the recording; elsewhere, only the models.

## Controller rulings (2026-11-02; binding)

These are the architect's rulings, revised after four reviews. Each is a controller recommendation made while the owner is unavailable.

- Ruling: the order is the pins, the pair, the TDR with the 4-port, schema 3 with the dielectric next to each layer, the mesh rule, the vertical port, the pulse and stop, Debye, the gate tool, then the run. The TDR's test reads the 4-port's ideal line, so they share a task. Schema 3 and `si()` have no reader in plan 1 and ride with `substrate_h`, the smallest task, which saves a 21-minute suite run. The gate tool is code, test-first, apart from the run that records it — design §4, §5.12 item 1 — cost if wrong: a reorder.
- Ruling: the antenna pins cover all seven fixtures at new_antenna's defaults, each board copied in with LF ends, and add v1's three 2D readouts, which golden_v1 does not pin, as new keys, not a re-recording.
  - **Pinned everywhere:** the spec hash, model.json, project.json, new's lines without I_WROTE, and the blocking gates (none today); and the pi's verify model at dt 1e-13 s and C_box 2e-14 F, with its far-field box.
  - **Pinned where `env()` matches:** every antenna and v1 case's 2D readout; and the results/ and lines of ifa2g4 (the far-field fixture's real dipole job, M = 0) and of the pi (`synth_records` of star(f, 4)).
  - `golden_v1.main`'s body becomes `golden_v1.record(golden, digests)`, which both tools call: tools/ lies outside `code_id`'s src, and test_golden_v1 never calls main.
  - The reviser's prototype was deterministic across two folders, in about 10 s, with a 5.3 KB JSON.

  — design §3, §4 — cost if wrong: a re-recording ruling.
- Ruling: plan 1 adds `SCHEMA_SI` and `si()`, and `load_project` keeps refusing schema 3 (`expected` 2). Accepting it before plan 2 checks its fields would let a hand-made schema 3 file reach code that reads it as v1's. `GATES_SI` (dt_floor 0.6) has no reader in plan 1 and moves to plan 2, which writes an SI project's gates; A-43 states the default — design §5.1 ("a build before Stage 4 refuses schema 3"), §5.3 — cost if wrong: a constant moves back.
- Ruling: cs2d's pair is three `solve()` calls on one grid: each leg alone at 1 V with the other a ground (C_P, C_N), then both at 1 V (C_PN). Then Ce = C_PN/2 and Co = C_P + C_N − Ce, likewise in vacuum, and c11 = (Ce + Co)/2, c12 = (Ce − Co)/2: solve's grid is not mirror-symmetric, so C_P and C_N differ by about 1e-4, and c11 is their mean.
  - `solve`, `_dirichlet` and every v1 and antenna 2D path stay as they are, so no pin needs to prove them; solve's own errors refuse legs that share a node (ShortError) and a leg the lines miss (ValueError).
  - It refuses anything but two mirror-image legs (ValueError); the surroundings' symmetry goes unchecked, marked `ponytail:`.
  - It costs 1.5 times the Laplace solves of a (1, −1) excitation: 1.5 s against 1.0 s on the 0.1 µm stripline, the two agreeing to 5e-16.

  — design §5.9, r4 — cost if wrong: plan 2 adds the two-excitation path if fit2d on coupled sections needs the speed.
- Ruling: "thin copper" for Cohn is 0.1 µm. There cs2d reads −0.19 to −0.37 % on four cases, of which −0.14 to −0.24 % is cs2d's own grid (its reading at 0.01 µm) and the rest the strips' thickness. At 1 µm it reads −0.63 to −1.36 %, outside 0.5 %. The worst row's margin is 0.13 %, so a later change to cs2d's GRADE or COARSE (plan 2's fit2d speed, say) moves these rows by tenths of a percent with no bug involved — design §5.11 — cost if wrong: one constant in the references.
- Ruling: Kirschning–Jansen (ported from KiCad 9.0's c_microstrip.cpp into tests/kicad_lines.py) is gated at 1 µm on Z and εeff within 3 %, and at 35 µm on Z only, on 1.0 and 1.5 mm substrates, where t/h ≤ 0.035.
  - **Measured:** within 1.4 % at 1 µm, of which about 0.5 % of Zeven's −1.32 % is cs2d's reference box (REF_H 10; −0.79 % in a box 40 h out), and within 3.93 % in Z at 35 µm. εeff at 35 µm is recorded: cs2d's εodd reads 4.3–5.0 % under KiCad's there.
  - **Why the 0.2 mm stack is recorded:** KiCad builds the coupled lines on a zero-thickness single line (`compute_single_line`), so its thickness terms raise Zeven and εodd as the copper thickens (Zeven 96.99, 98.79 and 100.12 Ω at 0, 18 and 35 µm), where both must fall, as cs2d's do (95.84 Ω at 1 µm, 92.72 and 90.73 Ω). On the fixtures' stack cs2d reads Zeven and Zodd 9.4 % and 9.3 % under KiCad's at 35 µm, where r1's FDTD read cs2d's Zdiff within 1.9 %. The stack is recorded at 18 and 35 µm, the slope as evidence; cs2d at zero thickness is a sheet, which its own note puts 1.2 % low, so KiCad's zero-thickness values are quoted in the report.
  - **The consequence:** P4-B's "Zdiff within 5 % of KiCad's calculator" cannot hold on that stack for a correct solver (KiCad 125.6 Ω, cs2d 113.9 Ω, r1's FDTD 116.0 Ω), and plan 4 rules on it before P4-B runs.

  — design §5.11, and `tests/test_cs2d.py`'s ruling on formula thickness terms — cost if wrong: one gated case set.
- Ruling: the even/odd 4-port lives in `tools/p4a.py` beside Cohn, the other reference model: no product code reads it in plans 1–5 (results come from the run's S through se2gmm), and P4-A's identities and plan 4's P4-B (NEXT's peak) import it there. Its ports are [P near, N near, P far, N far], z_ref 50 Ω by default. The identities hold at z_ref = √(Ze·Zo), where a homogeneous pair's FEXT and S11 vanish. "A step's Γ" is the bounce series of an uncoupled line, S11 = Γ(1 − x)/(1 − Γ²x). The prototypes held them to 4e-15 — design §5.11, r4 — cost if wrong: one function moves into core/post.
- Ruling: the TDR, alone in `core/post/si.py`, uses N_TDR 2000 (a 200 ns record at 10 GHz, which a longer response wraps, marked `ponytail:`), PAD 8, a sum started 4 rise times before t = 0, and σ = t_r/2.563.
  - The ideal line is read at τ (59.999 Ω), and from 4τ + 4·t_r to 20 ns within 0.0014 Ω of 50; between 2τ and 4τ it reads 50.075 Ω, its own Γ³.
  - P4-A's tdr rows pass at |error| < 0.05 Ω, one rule: the design's "60.0 then 50.0 Ω", to one decimal.
  - A grid not uniform from DC is a ValueError.

  — design §5.6, r1, r3 — cost if wrong: plan 3 retunes N_TDR.
- Ruling: `substrate_h(zs, layers)` takes the thinnest dielectric next to any given layer, above or below, so an asymmetric stripline takes its nearer plane. One h serves d and the reach, as in v1, and no layers keeps the top layer's — design §5.3, r3 — cost if wrong: one function grows a second value.
- Ruling: the SI mesh rule is `xy_lines(max_cell=…, spans=…)`, with `si_max_cell` = `lambda_min(f_max, εeff)/40` beside `coarse_cell` in region.py.
  - **Where:** d fills only the spans, whose ends are lines where clear. max_cell caps the rest of the extent, and the coarse cell the outside; `_smooth` is unchanged; with None the lines are today's and the spans are ignored.
  - **Plan 2's:** the via margin, the εeff from the 2D table, and spans over staircased copper, which has no axis edge to pattern.
  - **Measured:** 267 lines against 1,368 on a 100 mm pair and 153 against 706 on an L, each edge's nearest lines the d fill's, and today's lines array-equal with None. Spans clear of and over an edge's pattern (49–51 and 99–101 mm on the straight pair, 49–51 and 49–49.8 mm on the L) keep the lint, RATIO, the d/3 merge and cells at d or under; a span end within d/3 of an edge's line merges into it.

  — design §5.3, §6 — cost if wrong: a 45° pair with no span reads coarse, which P4-B would catch.
- Ruling: the vertical port.
  - **The plane:** `plane_under` walks the copper layers from the pad's toward the board's middle and on, and takes the first on which one ground or power net's copper, its pieces' union, covers the pad, the 10 µm simplification allowed. Any copper over the pad's footprint on a layer before it gives None, as do no copper, an antipad and a split. This is design §5.5's "nearest plane under it"; the adjacent layer alone would refuse a pad over a bare signal layer. The union matters because the copper pipeline's hole cut (Stage 1 §5.3 step 6, `split_holes`) splits a plane along any antipad's x, and a cut through the pad's span leaves abutting pieces, none of which covers the pad.
  - **The port:** a sheet in z across the pad's centre line along its longer side, from the plane's face to the pad's, starting at the plane, as r1's probe used. Its nodes keep the lumped port's order, [plane cap, pad cap, plane far face, pad far face], which the PEC-roots gate reads. A box over the whole pad would need its corners inside a rounded pad's copper.
  - **Refusals:** E_PORT_BOX when no line lies inside the pad. Plan 2 raises the user-facing refusal at `new`.
  - **Its height:** a two-layer board's port is 1.5 mm tall, and a walk past bare layers makes ports taller, against the 0.2 mm the design's launch estimate (j6–19 Ω at 10 GHz) assumes: plan 2 caps the height, or plan 4's P4-D coupon includes the tallest port the product builds.

  — design §5.5, Stage 1 §5.6 — cost if wrong: one function.
- Ruling: the DC pulse is openEMS's Gaussian at f0 = 0, written as `SetCustomExcite`'s expression, so `build_csx` and the worker keep one code path: f1 0, f2 f_max, t0 = 9/(2π·f_max) — design §5.4 — cost if wrong: none.
- Ruling: `window_s` = max(2 ns, 1.5 × the round trip), and `dc_pulse` also writes "flat_s" = FLAT_S + (window_s − WINDOW_S).
  - **Why:** in the replay, with the log energy held as openEMS's is under the DC pulse (r1: −1.43 dB over 30 ns) and the growth detector at WINDOW_S, a pulse reaching the far port 5 ns later converged falsely at 2.27 ns under the 2 ns window. With a 15 ns window and v1's 5 ns flat window it read flat at 5.29 ns with a 0 dB residual. With the 18 ns flat window it converged at 20.26 ns. A test record whose energy is the ports' own power falls to 0 between the pulses, and the growth detector read it as growth at 4.23 ns, so Task 7's records hold the energy.
  - **Kept:** the growth detector keeps WINDOW_S (marked `ponytail:`), LAG_S stays, and `last_sample` waits for plan 2. `si_t_max` rounds up to a whole ns, as `antenna_t_max` does (A-28).
  - **Short routes:** under about 37 mm at εeff 3.3, T_max (5 ns or less) comes before the 5.29 ns a flat verdict needs, so a held level ends at T_max, flagged, never converged.

  — design §5.4 — cost if wrong: one key.
- Ruling: the Debye fit takes f_ref 1 GHz (KiCad stores none) and one pole a decade at f_max/100, f_max/10 and f_max, the band P4-D judges. It is NNLS on 61 log points with the ε″ rows weighted 1/tan δ, and zero poles are dropped.
  - **Refused (ValueError):** a tan δ of 0 or less, and an ε∞ under 1.
  - **Measured:** tan δ within 6.0 % of a constant on FR-4 (4.3, 0.02; ε∞ 4.09), 4.9 % at 3.66/0.004 and 8.3 % at 4.5/0.035. Against Djordjevic–Sarkar's attenuation ε″/√ε′, which P4-D's MLine reference uses, the FR-4 fit reads −4.7 to +4.8 % over 0.1–10 GHz and −1.8 to +3.6 % over 4.5–10 GHz, where P4-D's 5 % binds on a 100 mm line.
  - **Plan 4's lever:** poles past the band's edges. Four from f_max/10^2.2 to f_max·10^0.2 read 3.9 % (−2.8 to +1.9 % against D-S); four inside the band, 2/3 of a decade apart, read 7.4 %, worse than three.
  - `build_csx` builds a "debye" material as CSXCAD's CSPropDebyeMaterial (r1's binding), relaxation times 1/(2π·f_relax), with no κ.
  - **Stated limit:** openEMS 0.37's Debye extension takes each pole at an edge's own point over the edge's whole area (`operator_ext_debyematerial.cpp`), where the static ε is averaged over the quarter cells (`operator.cpp`), so the edges on a Debye substrate's top face carry the full Δε over dual cells half in air. P4-D isolates it, with a substrate-filled stripline twin, before retuning the fit; r1's unexplained insertion loss at 5 GHz may hold some of it.

  — design §5.3, r1 — cost if wrong: one constant.
- Ruling: P4-A is `tools/p4a.py`: the references JSON, `measure()`'s 50 rows (Cohn 8, Kirschning–Jansen 16 at 1 µm, 12 at 35 µm and 8 recorded, identities 4, TDR 2) and `main()`'s record with its `wall_s`, run in CI by `tests/test_p4a.py`. The cross-sections, Cohn's formula and the 4-port live in the tool from Tasks 2 and 3, where the tests import them; KiCad's formula sits beside its single-line port in `tests/kicad_lines.py`, which only the tests read, since `measure()` reads the formulas' values from REFS — design §5.11 — cost if wrong: none.
- Ruling: one place per number and check. test_cs2d takes `WIDE` from p4a. Task 7 drops v1's and the antenna's excitation-key assertions, which Task 1's pins make on every fixture. An SI key leaking into a v1 or antenna spec has no failure path in plan 1, so it moves from the Review Focus to the Global Constraints, the pins its check; its place goes to a via span over an edge's pattern. test_cs2d keeps its Kirschning–Jansen worked example and its two accuracy tests: they are Task 2's failing tests, written before the references exist, and they check what P4-A does not (the C matrix, the homogeneous εeff, the mode relations) — ponytail — cost if wrong: none.
- Ruling: A-41 (§2), A-42 (§5.3, and §10's Debye line, which would otherwise contradict it), A-43 (§5.4), A-44 (§5.6), A-45 (§5.8), A-46 (§6.3) and A-47 (§9.10, P4-A) land in Task 10, after the gate. §10's "SI and differential pairs" leaves with plan 2's SI project, which the line names, as do §6.4 and the rest of §10; §7 is plan 3's, and §9's P4-B to P4-G plan 4's — design §5.13 — cost if wrong: a paragraph moved.
- Ruling: this plan adds no catalog message, so no pt-BR msgstr. Its refusals are E_PORT_BOX and ValueErrors that plan 2 maps — pt-BR design §6 — cost if wrong: none.
- Ruling (disclosure): the architect's and the reviser's checks ran only in a scratch folder, with the repo's venv, an isolated data folder and no openEMS run:
  - the antenna digests, v1's readouts included, twice;
  - cs2d's pair by three solves against the (1, 1) and (1, −1) energies, Cohn at 1, 0.1 and 0.01 µm, and the KJ port on 16 geometries, its references reproduced exactly;
  - the 4-port, the TDR, the SI mesh rule with its spans, the vertical port's plane on split and layered planes, the Debye fit against a constant tan δ and against Djordjevic–Sarkar, and the stop rule's replays with both energy records.

  KiCad 9.0's `c_microstrip.cpp` and `microstrip.cpp` were downloaded, read-only, from KiCad's GitLab into that folder, and openEMS-Project's v0.37.0 Debye extension and material averaging were read in a local clone. No suite ran, and nothing was written in the repo or its venv — cost if wrong: none.

## Open issues, ruled by the controller (2026-11-02; owner unavailable)

The reviser's nine open issues are ruled here, each a controller recommendation.

1. **P4-B against KiCad's calculator** judges only where t/h ≤ 0.035, as P4-A does. On the fixtures' 0.2 mm/35 µm stack, P4-B records KiCad's Zdiff and the difference, and judges against fit2d alone (1.5 %). KiCad's thickness terms move the wrong way there: KiCad 125.6 Ω, cs2d 113.9 Ω, r1's FDTD 116.0 Ω. Plan 4 lands this as the design's amended P4-B row, with P4-B. — cost if wrong: one comparison.
2. **A tall vertical port** gives a warning, not a refusal. When its height exceeds λ_eff(f_max)/20, plan 2 adds a W_ code with its pt-BR msgstr, advising a lower f_max; the TDR already marks each port's launch (design §5.6). P4-D's pad coupon adds the tallest port the product builds: 1.5 mm, a two-layer board's. — cost if wrong: the warning becomes a refusal.
3. **The Debye edges on a substrate's top face** stay as the plan rules: P4-D isolates them with a substrate-filled stripline twin before any retuning of the fit. If they cause a miss, the fit is not bent to hide it: the limit is stated, or plan 4 rules on the model. — cost if wrong: a stated limit.
4. **A short route's T_max** covers the flat verdict: plan 2 writes T_max = max(si_t_max, 2·t0 + flat_s + 1 ns). A held level then ends flat, not flagged at T_max. That costs a few ns per job on routes under about 37 mm. — cost if wrong: a few ns per job.
5. **cs2d's reference box** stays at REF_H 10. Zeven's 0.5 % low bias is far inside the presets' ±10 % target bands. Plan 2's 2D table states it as a screening, as the design calls it. — cost if wrong: one constant.
6. **P4-A's Cohn margin** (0.13 % on the worst row) is the regression guard it should be. A later change to cs2d's GRADE or COARSE that moves those rows is reviewed as a cs2d change, re-measured against the same references, never by moving the references. — cost if wrong: none.
7. **The Debye fit's pole count** stays at three in plan 1. P4-D may move to four poles past the band's edges (3.9 % against a constant tan δ) if its 5 % binds. The higher cell weight then goes through design §5.3's 1.5× rule. — cost if wrong: one constant.
8. **cs2d's pair keeps three solves.** Plan 2 adds the (1, −1) path only if fit2d on coupled sections, or the 2D table, takes more than a few seconds on the fixtures. — cost if wrong: one function.
9. **The owner's review.** A-41 to A-47 and P4-A's deviations from the design's table are controller recommendations: thin copper at 0.1 µm; Kirschning–Jansen at 35 µm gated in Z only where t/h ≤ 0.035; εeff at 35 µm and the fixtures' stack recorded; the 4-port in tools/; the vertical port's nearest plane past bare layers. P4-A's record states each, and the Stage 4 exit record carries them as owner items. — cost if wrong: none.
