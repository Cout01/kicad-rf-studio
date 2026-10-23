# Stage 1 · Plan 5 — Validation gates and reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the Stage 1 gates this PC can run (P0-0, P0-A, P0-B and the KiCad button pre-check), build the P0-C tool and the P0-D / CI tier (b) workflow, make the product changes the gates need or pre-register, and end with a report per gate and the Stage 1 exit report with a bottom-up Stage 2 estimate.

**Architecture:**
- **Product changes, test-first:** the privacy gate's four gaps; port caps and witnesses inside the real pad copper; the optional fields `mesh.reach_h` and `region.margin_scale`; the "relative / what-if" label; the calibration's per-level speeds, run-folder hygiene and simulate's job loop as `pipeline.run_ports`; the reference chooser's next-best candidate; `stoprule.growth_rise`; optional probes in `build_csx`, `cross_section(box_h=)` and `layout(f=)`.
- **Dev-time harnesses under `tools/`**, never imported by the package: `p0.py` (the shared pieces), `p0a.py`, `p0b/harness.py`, the EMerge pair `p0b/emerge_app.py` (app venv) and `p0b/emerge_fem.py` (validation venv), `p0c.py`, `p0d.py`, and `.github/workflows/linux-openems.yml`. They drive the product through its own commands as subprocesses (D-9); the models the product cannot build (the P0-A coupons, the empty boxes, the K_MAX sweep, D-43's no-mask openEMS run) go through `pipeline.prepare`, `pipeline.setup_gate` and `pipeline.run_ports`. A step stores only what its run produced; every number of a gate JSON is computed from the run folders when the JSON is written.
- **Three phases (D-5):** code (Tasks 1–12); gate runs the controller starts in the background on an otherwise idle PC (Tasks 13–16); decision and report tasks that apply the rules the harnesses computed and return each report's text and JSON for `docs/validation/` (Tasks 17–22).

**Tech Stack:** Python ≥ 3.11 (the dev venv runs 3.14), numpy, scipy (`optimize.least_squares`), shapely, scikit-rf through `core.post`, stdlib `subprocess`/`json`/`hashlib`/`threading`/`contextlib`; openEMS 0.37.0 and CSXCAD 0.7.0 in workers only; EMerge 3.0.0b3 in a uv-made Python 3.13 venv inside the P0 folder; KiCad 9.0.7 (headless `kicad-cli` and its bundled Python) for the pre-check; GitHub Actions, written and not run; pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`. This plan covers §9 in full (9.1 P0-0, 9.2 P0-A, 9.3 P0-B, 9.4 P0-C as a tool, 9.5 P0-D as a workflow, 9.6 the button pre-check, 9.7 order, exit, timebox and reports), the decisions that §1.2, §5.3–5.7, §6.3, §7.4–7.6, §8 and §12 hand to P0, and the carry-overs plans 2–4 left to plan 5. The controller decisions D-1..D-55 and amendments A-1..A-5 (`.superpowers/sdd/plan5-research/controller-decisions.md`) bind every task. The research cited as rN is `.superpowers/sdd/plan5-research/rN-*/findings.md`.

**Before Task 1 (the controller):** commit A-1..A-4 beside this plan; copy the research scripts this plan ports from the session scratchpad into the git-ignored research folders: r6's `em_coupon.py`, `em_lpf.py`, `lpf_spec.py`, `compare_chain.py` and `coupon_refs.py` into `.superpowers/sdd/plan5-research/r6-emerge/scripts/`, r7's `e1_line.py` and `geo.py` into `.superpowers/sdd/plan5-research/r7-protocol/scripts/`.

**Stage 1 is split into five plans.** Each one ends in working, tested software:
1. Foundation and board import.
2. Geometry, mesh and the mesh gates, including the 2D Z0/εeff readout of `cost`.
3. Model, worker and run control: `cost`, `run`, `preview`, `calibrate` and `setup-openems`.
4. Co-simulation and results: `retune`, `verify`, the outputs and the validity indicators.
5. Validation gates P0-0 to P0-D, the KiCad button pre-check and the reports (this plan).

**Branch:** work on `stage1-plan5`, from `main`, in a workspace from `scripts/sdd-workspace`; this plan is `docs/superpowers/plans/2026-10-22-stage1-plan5-validation-gates.md`. Phase 1 commands assume the dev venv is active; every Phase 2 command and check names `.venv\Scripts\python.exe` (repo-relative), because each background command starts a fresh shell. `<P0>` stands for the P0 folder (default `%LOCALAPPDATA%\kicad-rf-studio-p0`).

## Global Constraints

- **Python and files:** Python ≥ 3.11 (CI floor); every new source file starts with `# SPDX-License-Identifier: GPL-3.0-or-later` (`.py`, `.yml`, `requirements.txt`); English. Dev tools print plain English; the product prints only CATALOG codes.
- **Dependencies:** the app's runtime dependencies do not change. EMerge (GPL-2.0-or-later, compatible with the repo's licence, never shipped) lives only in the validation venv: `emerge==3.0.0b3`, Python 3.13 from uv, inside `<P0>/emerge` with `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` there too; never a global Python, never an ESP-IDF environment; that venv never imports the app, and data passes through JSON, NPZ and Touchstone files only (D-41). No harness copies third-party code: the probe triplet uses MSLPort's equations, not its code, so NOTICE does not change.
- **Imports:** the package never imports `tools/`; the worker imports no `core.post`, skrf or matplotlib; `tools/p0b/emerge_fem.py` imports no `kicad_rf_studio` and no `p0`. Tools call `p0.cli`, `p0.enter`, `p0.command_lines` and `p0.code_id` through the module, so tests can patch them, and import `pipeline`, `core.post.chain` and `core.post.checks` by module or by the names they use, never under a name a tool defines. pytest gets `pythonpath = ["tools"]`; a script under `tools/p0b/` puts `tools/` on `sys.path` first.
- **Messages:** every new product string is a code in the one CATALOG of `core.messages`, with plain `{fields}` and pre-formatted numbers, and says what to do next; tests check `KrsError.code` and `.params` (or the rendered line), never `match=`.
- **Units and frames:** mm, Hz, s, F, H, Ω; `project.json` in KiCad's frame (y down); model specs, probes and harness points in the internal frame (y up).
- **Execution model (D-5..D-10):**
  - Phase 1 tasks are test-first. Phase 2 runs are started by the controller as background commands, one at a time, on an otherwise idle PC: never beside another gate run, a test suite or any other openEMS or EMerge process (the PC is memory-bound). Phase 3 starts after Task 16. From Task 13's start to Task 16's end, `src/` and `tools/` change only by a test-first commit made between runs to fix a step the harness reported failed (exit 1); nothing is committed while a run is in progress. Phase 3 tasks read the gate JSON and apply the pre-registered rules; the verdicts are computed by the harness code. A [decide] task whose gate pre-registers no rule (Tasks 21, 22) is report-only.
  - Harnesses are resumable (D-6): one record per finished step in `<P0>/steps/<step id>.json`, reused when it holds the same key: the step's model hash plus `p0.code_id()`, the id of the committed `src/` tree, so changed product code reruns its steps. A step stores only the raw outputs of its run (exit codes, run-folder names, the jobs as results record them); the gate JSON is computed from the run folders, never deleted (C-23), so an analysis fix needs no rerun, and a gate writer refuses records made by different code. A crash or a reboot loses at most the running step; a stopped job is never recorded; a step that raises is logged, the harness goes on with the next and exits 1 at the end.
  - Load (D-6): each step records the PC's load at its start and its end (`p0.busy()`: other workers, EMerge and pytest processes, and the calibration entry); a step is `"loaded"` when either reading saw one, or the check itself failed. A loaded step's S stays valid; only its times leave the report's section 6. Rerun a loaded step only when its own timing is needed.
  - Stop: graceful, a `<P0>/STOP` file, which `p0.step` checks before each step; immediate, `taskkill /T /F /PID <harness pid>`, then `p0.command_lines()` must hold no marker before a restart. Never put a STOP file inside a run folder. One harness per P0 folder: `p0.enter` holds `<P0>/harness.lock` for the life of the process.
  - The P0 folder holds every P0 artifact: projects, board copies, run folders, `settings.json` and its calibration, the step records, the gate JSON, rendered tables and the EMerge environment. Default `%LOCALAPPDATA%\kicad-rf-studio-p0`; `--out` overrides it. CLI children run with `LOCALAPPDATA` and `XDG_DATA_HOME` set to `<P0>/data`; the calibration runs first there; `p0.step` refuses a data folder outside the P0 folder, so the owner's per-user data folder is never touched (D-7).
  - Harness tests in tier (a) use the fake worker or plain unit data, and the `p0_out` fixture (`tests/conftest.py`): a P0 folder named with a space and an accent, the calibrated data folder inside it, the real `p0.enter`. A real openEMS check is `@pytest.mark.openems` and lasts about 2 min or less (D-8). Tier (a) never runs openEMS.
  - Gate runs drive the product (`new`, `cost`, `run`, `retune`, `verify`) as subprocesses; harness-only models exist only where the product cannot measure. P0 projects are always made fresh by the current `new` (F-9) and never get a reference set by hand (D-9, D-11).
  - Comparisons judged against dB limits run at the Normal stop level; Draft serves only for shakedowns and for the P0-D and tier (b) references (D-10).
- **Criterion-1 limits** (spec §9.3, §9.4): |ΔS21| ≤ 0.1 dB and |ΔS11| ≤ 0.02 at f0; |ΔS| ≤ 0.03 up to f2; every null shift ≤ 2 % and no unmatched null; "n/a" when there is no null (lpf915).
- **Timebox (D-4, Rec):** counted from 2026-10-22; target 2026-11-05 to 2026-11-12; ceiling 2026-11-19. Every run task checks the date first; at the ceiling every P0 run stops and the exit report is written with the data (Task 22). Every report and its JSON record elapsed days and machine hours.
- **Exit status (D-3):** "P0-A and P0-B decided on Windows; P0-D and tier (b) prepared, not run; P0-C tool ready and smoke-run on lpf915; Stage 1 exit pending the owner". No task claims the Stage 1 exit.
- **Reports (D-51, D-52):** `docs/validation/YYYY-MM-DD-p0-0.md`, `-p0-a.md`, `-p0-b.md`, `-precheck.md`, `-p0-c.md` (the procedure, no numbers), `-p0-d.md` (prepared) and `YYYY-MM-DD-stage1-exit.md`. English, one page where possible, these sections in order: 1. verdict; 2. inputs; 3. measured value against limit, pass or fail; 4. decisions, each marked; 5. stated limits and deviations; 6. machine time, predicted against measured; 7. next step. A JSON with generic names sits beside each: `p0a.json`, `p0b.json` and `precheck.json` as the tools write them; the P0-0, P0-C, P0-D and exit JSON returned by their task with the report text. Accuracy is |ΔS| or a null shift, never dB at a null. Harnesses render tables into `<P0>`; a Phase 3 subagent returns the report and its JSON as text; the controller saves them under `docs/validation/`, runs the privacy gate on them and commits them; a hit is fixed in the text or the JSON and re-staged, never bypassed; subagents never write report files.
- **Privacy:** synthetic fixtures only. Never open the owner's boards, KiCad profile or settings, network shares, KiCad recent-file lists or the private research archive; never print the file `KRS_PRIVATE_LIST` names, nor its path, nor any count or index derived from it. Committed reports, JSON and fixtures hold no absolute path, e-mail address, private name, or drive letter followed by a colon and a slash or backslash (this plan included). The gate JSON names run folders and projects by name, never by path, and holds no host name; event params are read into booleans and numbers, never copied. `.npz` member names are generic. No P0-C number is ever committed.
- **Recommendations:** each "Rec" decision applied by a commit (D-4, D-15, D-26, D-31, D-34, D-35, D-41, D-42, D-44, D-49) says "controller recommendation, owner unavailable" in its commit message and in its report.
- **Spec amendments**, committed by the controller beside this plan, each marked "controller recommendation, owner unavailable": **A-1** (§9.2 L546: the harness probe triplet with MSLPort's equations, D-24); **A-2** (§9.2 L547: masked absolute Z0 against KiCad × the 2D mask factor, and the mask shift against fit2d's on-mesh shift, D-25, D-26); **A-3** (§9.1 and §9.6: the isolated KiCad profile also sets TMP, clears TMPDIR and every KICAD* variable, and seeds kicad_common.json before any GUI start, D-50); **A-4** (§7.6 and §1.1: the label is on until P0-C passes, D-15). **A-5** (§1.1, §10, §12: the TX-side outcome, D-34) is written by Task 18.
- **No other product number changes** until a gate's pre-registered rule says so (D-22).
- **Workflow:** every implementer runs `graphify query "<question>"` (or `explain`/`path`) from the repo root before reading code, and `graphify update .` after changing it; commits carry no co-author line.

## Review Focus

1. **A P0 run interrupted by a crash, a reboot, a STOP file, Ctrl+C, or a code change between nights:** finished steps are reused by their key; the interrupted step runs again from scratch in a fresh run folder; a step whose model or product code changed runs again; a stopped job is never recorded; nothing half-written is read back; a record holding numpy scalars, complex numbers or NaN is written as plain JSON. Tests: `test_a_step_runs_once_reruns_when_its_key_or_code_changes_and_a_crash_leaves_nothing` (Task 7a), `test_a_stopped_run_is_never_recorded` (Task 7b).
2. **A job that ends t_max or flat** (a lid cavity ringing, lpf915's slow 2.4–2.6 GHz tail): P0-A leaves its row out of the rules and names it among the fails; P0-B fails on it under D-33; a K_MAX sweep value that ends t_max still rising counts as unstable. Tests: `test_the_p0a_rules` (Task 8c), `test_the_p0b_rules` (Task 9).
3. **A privacy hit in a gate JSON or a report** (I_JOB_CONVERGED's params carry an absolute log path; a host name in a machine key): the gate JSON holds booleans, numbers and names only, round-trips with `allow_nan=False` and passes the generic scan. Test: `test_p0b_on_the_fake_worker_writes_a_plain_private_free_gate_json` (Task 9).
4. **P0-C pointed inside a git work tree, or at folders with spaces and accents:** an `--out` or `--board` inside any work tree (the repo itself, `tests/fixtures`, a folder not yet made under one, the `.git` folder) is refused before anything is written; folders outside named with spaces and accents run. Tests: `test_p0c_refuses_paths_inside_a_git_work_tree`, `test_p0c_on_lpf915_with_the_fake_worker` (Task 11).
5. **A project.json from plan 4 (no `mesh.reach_h`, no `region.margin_scale`) or one with a hand-typed wrong value:** it reads with the defaults and keeps its model hash, so its results stay valid; a wrong type refuses with E_PROJECT_FIELD naming the field. Tests: `test_reach_and_margin_are_optional_and_enter_the_model` and the new rows of `test_a_bad_field_is_named_never_internal` (Task 3).

---

## File structure

```
tools/privacy_gate.py                              # D-19: BOM, nested tags, cp1252 text, gitlinks
.gitignore  README.md  .github/workflows/ci.yml    # D-20; D-21's licence line; an SPDX first line
src/kicad_rf_studio/core/model/ports.py            # D-11: nodes inside the real copper
src/kicad_rf_studio/core/project.py                # D-12: REACH_H, MARGIN_SCALE, readers, optional fields
src/kicad_rf_studio/core/geometry/__init__.py      # D-12: passes the two fields
src/kicad_rf_studio/core/geometry/region.py        # D-12: build_region(margin_scale=)
src/kicad_rf_studio/cli.py  core/messages.py       # I_DEFAULTS, I_WHAT_IF
src/kicad_rf_studio/pipeline.py                    # D-15 label, D-16 levels, run_ports, D-17 et/ht
src/kicad_rf_studio/core/post/outputs.py           # summary_png(label=)
src/kicad_rf_studio/core/post/waves.py             # layout(f=)
src/kicad_rf_studio/runs.py                        # D-16: per_job_mcs, levels
src/kicad_rf_studio/stoprule.py                    # growth_rise, shared with _growth
src/kicad_rf_studio/core/kicad/tracer.py           # D-18: choose_reference(rank=)
src/kicad_rf_studio/core/model/csx.py              # D-13: probes
src/kicad_rf_studio/core/geometry/sections.py      # D-14: cross_section(box_h=)
tools/p0.py  tools/p0a.py  tools/p0c.py  tools/p0d.py
tools/p0b/harness.py  tools/p0b/emerge_app.py  tools/p0b/emerge_fem.py  tools/p0b/requirements.txt
.github/workflows/linux-openems.yml
tests/conftest.py                                  # p0_out (Task 7a)
tests/test_p0.py  tests/test_p0a.py  tests/test_p0b.py  tests/test_emerge_app.py  tests/test_p0c.py  tests/test_p0d.py
tests/test_traces_real.py  tests/test_p0d_refs.py  tests/fake_worker.py
tests/fixtures/traces/coupon_gcpw_pads-k{1,2}.npz  tests/fixtures/traces/lpf915-k{1..6}.npz   # Task 19
tests/fixtures/p0d/<model>.npz                                                             # Task 20
pyproject.toml                                     # [tool.pytest.ini_options] pythonpath = ["tools"]
```

## Decisions this plan fixes

| Decision | Task |
|---|---|
| Port nodes inside the copper shrunk by SIMPLIFY; the line across is the nearest width line where both ends keep such lines | 2 |
| `mesh.reach_h` (3.0), `region.margin_scale` (1.0), `I_DEFAULTS` | 3 |
| `I_WHAT_IF`, `pipeline.RETUNE_VALIDATED` | 4 |
| settings.json `levels`, `runs.per_job_mcs`, `pipeline.run_ports` | 5 |
| `choose_reference(..., rank=0)` | 6 |
| The P0 folder, `harness.lock`, `STOP`, `<P0>/steps/*.json` keyed by model hash and src tree, the `p0` interfaces of 7a | 7a |
| `stoprule.growth_rise`, `layout(f=)`, `run_model`, the trace format, `s_of`, `closed_chain`, `summary` | 7b |
| `spec["probes"]`, `cross_section(box_h=)` | 8a |
| The coupon instrument (feeds, triplets, references) | 8b |
| `<P0>/p0a/p0a.json`, the P0-A rules | 8c |
| `<P0>/p0b/p0b.json`, the B1–B6 projects, the P0-B rules | 9 |
| `<P0>/emerge/input.json`, `<P0>/p0b/emerge.json`, the validation venv and its requirements | 10 |
| `OUT/report/p0c.json`, `p0c.md`, `p0c-public.json` | 11 |
| `linux-openems.yml`'s jobs, `p0d.py`'s commands, the reference members, `p0d.PIN` | 12 |
| `tests/fixtures/traces/*.npz` | 19 |
| `tests/fixtures/p0d/*.npz` | 20 |

---

## Phase 1 — code

### Task 1 [code]: P0-0's fixes — the privacy gate's four gaps, .gitignore and the licence line

**Files:**
- Modify: `tools/privacy_gate.py`, `.gitignore`, `README.md` (its first paragraph), `.github/workflows/ci.yml` (a first line)
- Test: `tests/test_privacy_gate.py`, `tests/test_repo.py`

**Interfaces:**
- Consumes: `privacy_gate._scan_file`, `_scan_commit`, `_pushed`, `git`, `main`; the tests' `repo`, `commit`, `commit_bytes`, `stage`, `tag`, `hits`, `push`, `private_list`, `IDENT`, `NEVER`.
- Produces (D-19):
  - `_scan_file`: a blob that starts with a UTF-16 byte order mark (`FF FE` or `FE FF`) is scanned in three readings, UTF-16, UTF-8 and cp1252 (bad bytes replaced), each hit once, as the cp1252 branch already merges its two readings. Measured on this repo: a UTF-8-BOM blob already matches, and a blob that starts with a UTF-16 mark but holds UTF-8 text does not (the carry-over's "BOM-prefixed blob that is not UTF-16").
  - `_tags(shas: list[str]) -> list[str]`: each tag object of `shas`, then every tag object it reaches through nested tags (`git cat-file tag` says `type tag`), each once, in that order. `--all` and `--pre-push` scan `_tags(tags)`.
  - Commit and tag text: `_scan_file(f"{sha[:8]}:commit", "", git("cat-file", "commit", sha, raw=True), deny, False)` (and `:tag` for a tag), so cp1252 text is read as a blob is.
  - `--staged` leaves out gitlinks, the names whose index mode is `160000` in `git ls-files --stage -z`, and never runs `git show` on one.
  - `.gitignore` adds `runs/`, `\#auto_saved_files#` (escaped: a leading `#` starts a comment), `_autosave-*`, `*.kicad_sch`, `*.kicad_dru`, `fp-lib-table` and `sym-lib-table`; the `tests/fixtures` exception stays (D-20).
  - README's first paragraph (D-21): "… It is free software, licensed under the GNU General Public License v3.0 or later (see `LICENSE`); its copy of CSXCAD's SmoothMeshLines is under the GNU Lesser General Public License v3.0 or later (see `COPYING.LESSER`)."

- [ ] **Step 1: Write the failing tests** in `tests/test_privacy_gate.py`:

```python
@pytest.mark.parametrize("data", [b"\xff\xfeProject ACME\n", b"\xfe\xffProject ACME\n", b"\xef\xbb\xbfProject ACME\n"],
                         ids=["ff-fe", "fe-ff", "utf8-bom"])
def test_a_byte_order_mark_never_hides_the_utf8_reading(repo, capsys, data):  # D-19
    sha = commit_bytes(repo, "notes.txt", data)
    assert gate.main(["--all"]) == 1
    assert hits(capsys.readouterr().out) == [(f"{sha[:8]}:notes.txt", "1", "deny#1")]


def test_a_tag_of_a_tag_is_scanned_through_to_the_inner_tag(repo, monkeypatch, capsys):  # D-19
    commit(repo, "a.txt", "clean\n")
    inner = tag(repo, "inner", "Release ACME", "t")
    git(repo, "-c", "user.name=t", *IDENT[2:], "-c", "tag.gpgsign=false", "tag", "-a", "outer", "inner", "-m", "v1")
    git(repo, "tag", "-d", "inner")  # only the outer tag's ref is left
    outer = git(repo, "rev-parse", "outer")
    assert gate.main(["--all"]) == 1
    assert [where for where, _, _ in hits(capsys.readouterr().out)] == [f"{inner[:8]}:tag"]
    assert push(monkeypatch, f"refs/tags/outer {outer} refs/tags/outer {NEVER}") == 1


@pytest.mark.parametrize("what", ["commit", "tag"])
def test_commit_and_tag_text_in_cp1252_is_read(repo, monkeypatch, tmp_path_factory, what):  # D-19
    monkeypatch.setenv("KRS_PRIVATE_LIST", str(private_list(tmp_path_factory, "ação\n".encode())))
    message = tmp_path_factory.mktemp("msg") / "m.txt"
    message.write_bytes("Projeto ação\n".encode("cp1252"))
    if what == "commit":
        stage(repo, "a.txt", "clean\n")
        git(repo, *IDENT, "-c", "i18n.commitEncoding=cp1252", "commit", "-q", "-F", str(message))
    else:
        commit(repo, "a.txt", "clean\n")
        git(repo, "-c", "user.name=t", *IDENT[2:], "-c", "tag.gpgsign=false", "tag", "-a", "v1", "-F", str(message))
    assert gate.main(["--all"]) == 1


def test_a_staged_gitlink_is_skipped_without_a_git_error(repo, capsys):  # D-19: a submodule commit the repo lacks
    commit(repo, "a.txt", "clean\n")
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{'1' * 40},sub")
    stage(repo, "b.txt", "acme\n")  # the rest of the index is still scanned
    assert gate.main(["--staged"]) == 1
    out = capsys.readouterr()
    assert (out.out, out.err) == ("b.txt:1: deny#1\n", "")
```

  In `tests/test_repo.py`:

```python
def test_run_folders_and_kicad_side_files_are_ignored_and_the_p0_fixtures_are_not():  # D-20, spec 9.1
    ignored = ["runs/r/model.json", "p0/runs/job-1/waves.npz", "#auto_saved_files#", "_autosave-x", "a.kicad_sch",
               "a.kicad_dru", "fp-lib-table", "sym-lib-table"]
    kept = ["tests/fixtures/traces/lpf915-k1.npz", "tests/fixtures/p0d/lpf915.npz", "tests/fixtures/lpf915.kicad_pcb",
            "docs/validation/2026-11-05-p0-a.md", "docs/validation/2026-11-05-p0-a.json"]

    def by_git(path):
        return subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0

    assert [p for p in ignored if not by_git(p)] == [] and [p for p in kept if by_git(p)] == []


def test_the_readme_names_both_licence_texts():  # D-21
    first = (ROOT / "README.md").read_text(encoding="utf-8").split("\n\n")[1]
    assert "`LICENSE`" in first and "`COPYING.LESSER`" in first


def test_every_workflow_starts_with_an_spdx_header():  # D-55
    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert files and [p.name for p in files if p.read_text(encoding="utf-8").splitlines()[0] != SPDX] == []
```
- [ ] **Step 2: Run** `python -m pytest tests/test_privacy_gate.py tests/test_repo.py -q`. Expected: FAIL — `ff-fe` and `fe-ff` exit 0; the nested tag and both cp1252 cases exit 0; the gitlink case raises SystemExit (`git show :sub` fails on the absent commit and its stderr is echoed); the new .gitignore paths are not ignored; README names `LICENSE` only; ci.yml has no SPDX line. `utf8-bom` passes before and after.
- [ ] **Step 3: Implement** the four fixes as the Interfaces say, the .gitignore lines, the README sentence, and `# SPDX-License-Identifier: GPL-3.0-or-later` as ci.yml's first line.
- [ ] **Step 4: Run** the two files, then the full suite. Expected: all pass (the existing UTF-16 test still reports exactly one hit).
- [ ] **Step 5: Audit the history (D-23).** With `KRS_PRIVATE_LIST` set, from the repo root:

```
python tools/privacy_gate.py --all | python -c "import subprocess,sys; hits=[h for h in sys.stdin if h.strip()]; other=[h for h in hits if not (':commit:' in h and subprocess.run(['git','cat-file','commit',h.split(':')[0]],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout.splitlines()[int(h.split(':')[2])-1].startswith(('author ','committer ')))]; print('identity lines only' if not other else 'STOP: a hit off the author and committer lines')"
```
  Expected: `identity lines only` (expected until the owner's rewrite). It prints no count, index or text. A STOP line blocks plan 5: stop and report it to the controller. Then `python tools/privacy_gate.py --all --generic-only`. Expected: exit 0, no output. Keep both outcomes, never a count, for Task 21.
- [ ] **Step 6: Commit.** `fix: close the privacy gate's four gaps, ignore run folders and KiCad side files, name both licence texts (D-19..D-21)`

---

### Task 2 [code]: Port caps and witnesses inside the real pad copper (D-11)

**Files:**
- Modify: `src/kicad_rf_studio/core/model/ports.py`
- Test: `tests/test_model_ports.py`

**Interfaces:**
- Consumes: `End`, `place`, `ends`, `nominal_boxes`, `copper.SIMPLIFY`; `build_geometry`, `mesh_with_lint`; `Mesh`, `Slab`; `project_of` (tests/test_gates.py).
- Produces: `place(end: End, mesh: Mesh, zs: tuple[Slab, ...]) -> dict`, signature unchanged. For a lumped port, the width lines across come first, as today. The line across `tc` is then the first of them, nearest the middle of the bounds' overlap first (a tie to the lower line), at which each end keeps at least one line along p inside its bounds whose point at `tc` lies inside its copper shrunk by SIMPLIFY (`end.signal.buffer(-SIMPLIFY).contains(Point(...))`, and the same for `end.reference`): the copper solids are simplified by up to 10 µm. The caps and witnesses are chosen among the lines each end keeps at `tc`, as today. E_PORT_BOX (unchanged text) when the width keeps no line or no width line qualifies, so a facing span that vanishes once rounded corners count is a coded refusal, never E_INTERNAL. E_PORT_SPANS still reads the bounds. The ponytail at ports.py:141 becomes `# ponytail: the nodes sit inside the real copper (by SIMPLIFY); the box's other lines across may cross a rounded corner's air`.
  Measured effect of this rule on the fixtures (n = 2 / n = 3):
  - lpf915: P2 at both n (at n = 2 its line across moves from x 112.828, 3 µm inside J1.2's edge, to 112.9024; at n = 2 a filter at the old line would refuse with E_PORT_BOX); P1's reference cap at n = 2 (y −99.6237 → −99.5201); C1's signal cap (x 103.2914 → 103.2165 at n = 2, 103.2905 → 103.2404 at n = 3); C2's and C3's reference witnesses at n = 3 (y −101.2379 → −101.192).
  - lpf915-45: P2 at both n (x 112.8322 → 112.9029 at n = 2); C2's and C3's reference witnesses at n = 3.
  - coupon_gcpw_pads at n = 3: both ports' reference witnesses (y −101.6465 → −101.5973).
  So P1's and C1's boxes, C1's C_box and lpf915's model hash change too; no test pins them.

- [ ] **Step 1: Write the failing tests** in `tests/test_model_ports.py`:

```python
@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize(("name", "start", "end"), [("coupon_gcpw_pads", "TP1.1", "TP2.1"), ("lpf915", "U1.1", "J1.1"),
                                                   ("lpf915-45", "U1.1", "J1.1")])
def test_every_node_of_every_port_lies_inside_its_copper(name, start, end, n):  # D-11, r3 B-3
    more = ("--lid-height", "2.5") if name.startswith("lpf") else ()
    board, p = project_of(name, start, end, *more)
    p = {**p, "allow_curve_port": True}
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), n)
    outside = []
    for x in e:
        q = place(x, m, g.zs)
        owners = [x.reference, x.signal] if q["kind"] == "curve" else [x.reference, x.signal, x.reference, x.signal]
        outside += [(x.name, k) for k, (node, cu) in enumerate(zip(q["nodes"], owners))
                    if not cu.contains(Point(node[:2]))]
    assert outside == []


def test_lpf915s_p2_moves_to_the_width_line_where_both_pads_have_copper():  # D-11: n = 2 places it
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")
    g = build_geometry(board, p)
    e = ends(board, p, g.pieces)
    m = mesh_with_lint(g, replace(g.protected, boxes=nominal_boxes(e)), 2)
    p2 = place(next(x for x in e if x.name == "P2"), m, g.zs)
    assert [node[0] for node in p2["nodes"]] == pytest.approx([112.9024] * 4, abs=1e-4)


def test_a_round_pad_with_no_line_inside_its_copper_is_a_coded_refusal():  # D-11: never E_INTERNAL
    mesh = Mesh(np.array([-0.295, 0.295, 0.6, 0.9]), np.array([-0.2, 0.0, 0.2]), np.array([0.745, 0.78]), 0.1, 0.03,
                {}, {})
    end = End("P9", Point(0, 0).buffer(0.3), box(0.5, -0.05, 1.0, 0.05), "F.Cu", "external")
    with pytest.raises(KrsError) as e:
        place(end, mesh, (Slab("copper", 0.745, 0.78, None, None, "F.Cu"),))
    assert (e.value.code, e.value.params) == ("E_PORT_BOX", {"name": "P9"})


@pytest.mark.openems
def test_lpf915_at_n3_passes_the_port_gates(tmp_path, capsys, monkeypatch):  # D-11; about 1–2 min
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    runs.save_settings({"machines": {runs.machine_key(): {"threads": 4, "pool": 1, "aggregate_mcs": 200.0}}})
    pj = tmp_path / "lpf915" / "project.json"
    assert main(["new", str(FIX / "lpf915.kicad_pcb"), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz",
                 "--lid-height", "2.5", "-o", str(pj.parent)]) == 0
    d = load_project(pj)
    d["mesh"]["n"], d["gates"]["fit2d_limit"] = 3, 0.05  # E_FIT2D_FINE's own advice: RF_B reads +4.39 %
    save_project(pj, d)
    capsys.readouterr()
    assert main(["cost", str(pj)]) == 0
    assert render("E_PORT_OPEN", name="P2", end="signal") not in capsys.readouterr().out
```

  Test imports: `numpy as np`; `from shapely.geometry import Point, box`; `from kicad_rf_studio import runs`; `main`; `render`; `Mesh` from `core.mesh`; `Slab` from `core.geometry.zstack`; `End` from `core.model.ports`; `load_project`, `save_project`; `from test_cli_cost import FIX`.
- [ ] **Step 2: Run** `python -m pytest tests/test_model_ports.py -q`. Expected: FAIL — lpf915 and lpf915-45 list `[("P2", 0), ("P2", 1), ("P2", 2), ("P2", 3)]` at both n (r3 measured 26–95 µm outside); P2's line across at n = 2 is 112.828; the round pad places a box.
- [ ] **Step 3: Implement** the choice of `tc` and the filter in `place` as the Interfaces say.
- [ ] **Step 4: Run** the file, the full suite, then `python -m pytest -m openems tests/test_model_ports.py -q`. Expected: all pass. If a port outside the Interfaces' list moves, name it and its shift in the task report. If the openems test still finds E_PORT_OPEN, never loosen it: stop and report, because P0-B's B5 needs it.
- [ ] **Step 5: Commit.** `fix: place port caps and witnesses inside the real pad copper, so lpf915's P2 passes the port gates at n = 2 and 3 (D-11)`

---

### Task 3 [code]: The optional fields `mesh.reach_h` and `region.margin_scale` (D-12)

**Files:**
- Modify: `src/kicad_rf_studio/core/project.py`, `src/kicad_rf_studio/core/geometry/__init__.py`, `src/kicad_rf_studio/core/geometry/region.py`, `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_cli_cost.py`, `tests/test_cli_new.py`, `tests/test_project.py`, `tests/test_geometry_region.py`

**Interfaces:**
- Consumes: `region_expand_h`'s pattern; `_FIELDS`, `_check`, `_MISSING`; `protected_set(..., reach_h=)`; `build_region`; `WALL_MM`, `WALL_CELLS`.
- Produces:
  - `project.REACH_H = 3.0` (the protected-set reach in substrate heights) and `project.MARGIN_SCALE = 1.0` (the factor on the margin `WALL_MM + WALL_CELLS·coarse`).
  - `project.mesh_reach_h(data: dict) -> float` (`data.get("mesh", {}).get("reach_h", REACH_H)`) and `project.region_margin_scale(data: dict) -> float` (likewise from `region`).
  - `make_project` writes `"region": {"expand_h": EXPAND_H, "margin_scale": MARGIN_SCALE}` and `"mesh": {"n": MESH_N[preset], "reach_h": REACH_H}`.
  - `_FIELDS`: `"region": {"expand_h": _ABOVE_0, "margin_scale": _OPTIONAL_ABOVE_0}`, `"mesh": {"n": …, "reach_h": _OPTIONAL_ABOVE_0}` with `_OPTIONAL_ABOVE_0 = (lambda v: v is _MISSING or _number(v) and v > 0, "a number above 0")`; `_check` raises when `isinstance(test, dict) or not test(value)` (every existing test already refuses `_MISSING`, so only the optional ones accept a missing key).
  - `build_region(board, chain, ports, zs, f_max, expand_h=3.0, margin_scale=1.0) -> Region`: `m = margin_scale * (WALL_MM + WALL_CELLS * coarse)`.
  - `build_geometry` passes `region_margin_scale(project)` to `build_region` and `reach_h=mesh_reach_h(project)` to `protected_set`.
  - `I_DEFAULTS`: "Preset {preset} (provisional default), band factor {band_factor}, T_max {t_max_ns} ns, harmonics {harmonics}, mesh n {mesh_n}, region {expand_h} substrate heights past the chain, margin scale {margin_scale}, protected reach {reach_h} substrate heights." (`cli._new` adds `"margin_scale": f"{MARGIN_SCALE:g}"`, `"reach_h": f"{REACH_H:g}"`).
  - No key enters the model spec: both enter it through the walls and the mesh lines they move, so the hash follows any change that changes the model, and plan-4 projects keep their hash and their results.

- [ ] **Step 1: Write the failing tests.** In `tests/test_cli_new.py`:

```python
DEFAULTS = ("Preset normal (provisional default), band factor 1.1, T_max 40 ns, harmonics 3, mesh n 2, "
            "region 3 substrate heights past the chain, margin scale 1, protected reach 3 substrate heights.")


def test_reach_and_margin_are_optional_and_enter_the_model(tmp_path):  # D-12, Review Focus 5
    _, pj = run_new(tmp_path, "--lid-height", "2.5")

    def model_hash():
        project, board, geom, _ = load(pj)
        return spec_hash(build_model(project, board, geom).spec)

    base = model_hash()
    d = load_project(pj)
    del d["mesh"]["reach_h"], d["region"]["margin_scale"]
    save_project(pj, d)
    assert model_hash() == base  # a project.json from plan 4 reads the defaults and keeps its hash
    for group, key, value in (("mesh", "reach_h", 6.0), ("region", "margin_scale", 2.0)):
        d[group][key] = value
        save_project(pj, d)
        assert model_hash() != base
        del d[group][key]
```

  Revise on purpose: line 137's strict variant of DEFAULTS gains ", margin scale 1, protected reach 3 substrate heights." In `tests/test_cli_cost.py`: `test_new_writes_region_and_mesh_defaults` asserts `d["region"] == {"expand_h": 3.0, "margin_scale": 1.0} and d["mesh"] == {"n": n, "reach_h": 3.0}`; `test_a_project_without_region_or_mesh_reads_their_defaults` adds `assert (mesh_reach_h({}), region_margin_scale({}), mesh_reach_h({"mesh": {"reach_h": 6}})) == (3.0, 1.0, 6)`. In `tests/test_project.py`, `test_a_bad_field_is_named_never_internal` gains the rows `(["mesh", "reach_h"], 0, "mesh.reach_h", "a number above 0")` and `(["region", "margin_scale"], "2", "region.margin_scale", "a number above 0")`. In `tests/test_geometry_region.py`:

```python
def test_margin_scale_multiplies_the_wall_margin():  # D-12, spec 9.4 criterion 4
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")
    zs = zstack(Stackup.from_json(p["stackup"]), board.copper_layers)
    one, two = (build_region(board, chain_of(p), p["ports"], zs, 3.0195e9, 3.0, s) for s in (1.0, 2.0))
    margin = WALL_MM + WALL_CELLS * one.coarse
    assert one.walls[1] - one.roi.bounds[2] == pytest.approx(margin, abs=2e-6)
    assert two.walls[1] - two.roi.bounds[2] == pytest.approx(2 * margin, abs=2e-6)
```

  Test imports: `load`, `build_model` from `pipeline` and `spec_hash` (test_cli_new); `mesh_reach_h`, `region_margin_scale` (test_cli_cost); `WALL_MM`, `WALL_CELLS`, `chain_of`, `from test_gates import project_of` (test_geometry_region).
- [ ] **Step 2: Run** `python -m pytest tests/test_cli_new.py tests/test_cli_cost.py tests/test_project.py tests/test_geometry_region.py -q`. Expected: FAIL (the readers, the keys, the parameter and the I_DEFAULTS text are missing).
- [ ] **Step 3: Implement** as the Interfaces say.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: the optional project fields mesh.reach_h and region.margin_scale, written by new and printed by I_DEFAULTS (D-12)`

---

### Task 4 [code]: The "relative / what-if" label (D-15)

**Files:**
- Modify: `src/kicad_rf_studio/pipeline.py`, `src/kicad_rf_studio/core/post/outputs.py`, `src/kicad_rf_studio/core/messages.py`
- Test: `tests/test_run.py`, `tests/test_post_outputs.py`

**Interfaces:**
- Consumes: `write_outputs`, `command_line`, `port_map`, `touchstone`, `summary_png`, `render`.
- Produces:
  - `pipeline.RETUNE_VALIDATED = False` with `# spec 7.6 (amendment A-4): the instant retune is labelled relative / what-if until P0-C passes; the owner sets True after P0-C (controller recommendation, owner unavailable)`.
  - `I_WHAT_IF`: "Relative / what-if: the instant retune is not yet validated against a full simulation of a real board (spec 7.6), so read these chain results as relative. Check the final values with `{command}`."
  - `write_outputs`: when the project has part ports and not `RETUNE_VALIDATED`, with `label = render("I_WHAT_IF", command=command_line("kicad-rf-studio", "verify", str(path)))`: the label is the last comment line of `chain.s{P}p` (after `port_map`; `touchstone` escapes it to ASCII), the second line of `summary.png`'s title, and `("I_WHAT_IF", {"command": …})` follows the indicator lines, before `I_OUTPUTS` or the E_RESULTS_WRITE line in its place. That one line is the offer of `verify`. A single trace (no part port) has no label; `verify` writes none.
  - `outputs.summary_png(lay, chain, ideal, name, label: str | None = None) -> bytes`: `fig.suptitle(render("I_PLOT_TITLE", name=name) + ("\n" + label if label else ""))`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_run.py`:

```python
def test_the_retune_is_labelled_what_if_until_p0c_passes(tmp_path, calibrated, monkeypatch, capsys):  # D-15, A-4
    pj = lpf_run(tmp_path, monkeypatch)
    label = render("I_WHAT_IF", command=command_line("kicad-rf-studio", "verify", str(pj)))
    assert "I_WHAT_IF" in result_codes(load_project(pj)["results"]["run_dir"])
    assert b"! Relative / what-if: " in (pj.parent / "results" / "chain.s2p").read_bytes()
    monkeypatch.setattr(pipeline, "RETUNE_VALIDATED", True)
    capsys.readouterr()
    assert main(["retune", str(pj)]) == 0
    assert label not in capsys.readouterr().out
    assert b"Relative / what-if" not in (pj.parent / "results" / "chain.s2p").read_bytes()
```

  Revise on purpose: `test_run_writes_the_outputs_of_a_known_network`'s codes read `[…, "W_LOSS_BUDGET", "I_WHAT_IF", "I_OUTPUTS", *LIMITS]`, and `test_a_held_output_file_still_prints_the_results_and_the_limits`'s read `[…, "W_LOSS_BUDGET", "I_WHAT_IF", "E_RESULTS_WRITE", *LIMITS]`; the single-trace lists do not change. In `tests/test_post_outputs.py`:

```python
def test_the_png_title_carries_the_what_if_label(monkeypatch):  # D-15
    titles = []
    monkeypatch.setattr(Figure, "suptitle", lambda self, text, **kw: titles.append(text))
    chain = ideal_schematic(PI, PI_Z, F)
    summary_png(lay_of(EXT, chain), chain, chain, "lpf915", label="L")
    summary_png(lay_of(EXT, chain), chain, chain, "lpf915")
    assert titles == [render("I_PLOT_TITLE", name="lpf915") + "\nL", render("I_PLOT_TITLE", name="lpf915")]
```

  Test imports: `from kicad_rf_studio import pipeline` (test_run); `from matplotlib.figure import Figure` (test_post_outputs).
- [ ] **Step 2: Run** `python -m pytest tests/test_run.py tests/test_post_outputs.py -q`. Expected: FAIL (`I_WHAT_IF` unknown; `label` unexpected).
- [ ] **Step 3: Implement** the constant, the code, the label in `write_outputs` and the keyword.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: label the instant retune relative / what-if and offer verify until P0-C passes (D-15; controller recommendation, owner unavailable)`

---

### Task 5 [code]: The calibration's per-level speeds, run-folder hygiene and simulate's job loop (D-16, D-17)

**Files:**
- Modify: `src/kicad_rf_studio/runs.py`, `src/kicad_rf_studio/pipeline.py`, `tests/fake_worker.py`
- Test: `tests/test_calibrate.py`, `tests/test_cli_cost.py`, `tests/test_run.py`

**Interfaces:**
- Consumes: `runs.calibrate`, `choose`, `sizing`; `pipeline.prepare`, `simulate`, `classify_job`, `records`, `stop_rule`.
- Produces:
  - `runs.per_job_mcs(entry: dict, k: int) -> float`: `entry["levels"][str(k)]`, the per-job MC/s with k jobs at once, when present; else `entry["aggregate_mcs"] / entry["pool"]`, as before plan 5 (an old entry, or a level not measured yet). `# ponytail: a level never run reads the calibration's aggregate / pool, as before plan 5`.
  - `calibrate`'s entry gains `"levels"`: `{str(pool): aggregate / pool}`, plus `"1": single[threads]` only when one job at the chosen thread count was timed (`single` holds 1, 2, 4 and N threads only, while choose() returns N // pool: 8 threads for 2 jobs on 16 CPUs). The calibration model itself is unchanged (r4 §7.2).
  - `prepare` returns `(threads, pool, runs.per_job_mcs(entry, pool))`, `pool` = min(sizing's pool, the runs): `cost` predicts at the level the run will use.
  - `pipeline.run_ports(model: Model, run_dir: Path, setup: dict, threads: int, pool: int, preset: str, gates: dict, ports: list[int] | None = None, t_max: float | None = None) -> tuple[list[dict], list[float], float]`: simulate's job loop moved out unchanged: I_RUN_START; one job `job-{k}-{name}` per port number k in `ports` (1-based, default every port) to `t_max` (default the spec's), `pool` at once under the stop rule at `preset` (the live watch with I_PROGRESS); each job's verdict event (classify_job) followed by `gate_lines(gates)`; then each classified job's `et` and `ht` removed (`unlink(missing_ok=True)`, D-17). graphify and grep confirm no code reads them: `tools/make_dumps.py` only deletes them. Returns (the jobs as project.json's results record them, openEMS's speed in cells/s of each job that wrote its stats, the job phase's wall time in s). Run folders are never deleted (C-23).
  - `simulate`: prepare, the setup gate and its events, gate_lines, the cost lines, `run_ports(model, run_dir, setup, threads, pool, project["preset"], project["gates"])`, then the refresh writes `entry.setdefault("levels", {})[str(pool)] = mean(speeds) / 1e6` and never touches `aggregate_mcs` (T18-R1's drift).
  - `tests/fake_worker.py`: run mode writes empty `et` and `ht` files first, as openEMS does.

- [ ] **Step 1: Write the failing tests.** In `tests/test_calibrate.py`, `test_calibrate_measures_and_stores_this_machine` adds `assert entry["levels"] == {"1": 50.0 * cpus}`, and:

```python
def test_the_per_job_speed_is_the_levels_else_the_calibrations():  # D-16
    entry = {"pool": 4, "aggregate_mcs": 800.0, "levels": {"1": 450.0, "4": 120.0}}
    assert [runs.per_job_mcs(entry, k) for k in (1, 2, 4)] == [450.0, 200.0, 120.0]
    assert runs.per_job_mcs({"pool": 4, "aggregate_mcs": 800.0}, 2) == 200.0  # an entry from before plan 5


def test_calibrate_stores_only_the_levels_it_timed(calibrated, monkeypatch):  # D-16: 2 × 8 threads wins on 16 CPUs
    monkeypatch.setattr(os, "cpu_count", lambda: 16)
    monkeypatch.setattr(runs, "choose", lambda single, parallel, cpus: (8, 2, 742.2))
    entry = runs.calibrate(runs.load_settings())
    assert entry["levels"] == {"2": pytest.approx(371.1)}  # no "1": one job at 8 threads was never timed
```

  In `tests/test_cli_cost.py`:

```python
def test_cost_predicts_at_the_speed_of_its_own_level(tmp_path, capsys, calibrated, monkeypatch):  # D-16
    monkeypatch.setattr(runs, "sizing", lambda entry, cells: (2, 2))  # level 2 on any runner, 2 vCPUs too
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")  # 2 runs

    def worst(levels):
        runs.save_settings({"machines": {runs.machine_key(): {"threads": 2, "pool": 2, "aggregate_mcs": 400.0,
                                                              "levels": levels}}})
        assert main(["cost", str(pj)]) == 0
        return next(x for x in capsys.readouterr().out.splitlines() if x.startswith("Worst case:"))

    assert worst({}) == worst({"2": 200.0}) != worst({"2": 50.0})
```

  In `tests/test_run.py`, `test_run_converges_and_records_its_results` patches `runs.sizing` to `lambda entry, cells: (2, 2)` and ends with
  `entry = runs.load_settings()["machines"][runs.machine_key()]` and
  `assert (entry["aggregate_mcs"], entry["levels"]) == (400.0, {"2": pytest.approx(100.0)})  # the fake's 5e7 × 2 threads a job, at 2 jobs`; and:

```python
def test_a_classified_job_leaves_no_excitation_arrays(tmp_path, calibrated):  # D-17
    pj = coupon(tmp_path)
    assert main(["run", str(pj)]) == 0
    jobs = sorted(Path(load_project(pj)["results"]["run_dir"]).glob("job-[12]-*"))
    assert len(jobs) == 2 and all((j / "waves.npz").is_file() for j in jobs)
    assert [p for j in jobs for p in (j / "et", j / "ht") if p.exists()] == []
```

  Test imports: `os` (test_calibrate).
- [ ] **Step 2: Run** `python -m pytest tests/test_calibrate.py tests/test_cli_cost.py tests/test_run.py -q`. Expected: FAIL (no `levels`, no `per_job_mcs`, `aggregate_mcs` refreshed to 200.0, `et` and `ht` left).
- [ ] **Step 3: Implement** as the Interfaces say; `run_ports` is a move of simulate's loop, so `tests/test_run.py` and `tests/test_verify.py` guard it unchanged.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: refresh and use the calibration's speed per concurrency level, share simulate's job loop as run_ports, and drop each classified job's et and ht (D-16, D-17)`

---

### Task 6 [code]: The reference chooser's next-best candidate (D-18)

**Files:**
- Modify: `src/kicad_rf_studio/core/kicad/tracer.py`
- Test: `tests/test_tracer.py`

**Interfaces:**
- Consumes: `choose_reference`, `TIE_DECIMALS`, `signal_layer`, `_resolve`, `_copper`.
- Produces: `choose_reference(board: Board, classes: Classes, signal: str, rank: int = 0) -> Reference | None` (spec 9.4 criterion 3, O-3). Rank 0 is today's result, computed by today's code, so `new` and every output are unchanged. The order is the chooser's own: the connector's or IC's GND pads on the signal layer by (rounded distance, number, uuid), then the copper rule's candidates — rank 0 of the rule being today's nearest point, the later ranks the nearest points on the other distinct pieces of `shapely.union_all` of the layer's GND shapes, by (distance rounded to TIE_DECIMALS, x, y); a piece holds the rank-0 point, and is skipped, when its distance to that point is ≤ 1e-6 mm (the point lies on a boundary, where an exact `intersects` can miss by float noise). Never the opposite layer. None when the order has fewer than rank + 1 candidates.

- [ ] **Step 1: Write the failing test** in `tests/test_tracer.py`:

```python
def test_the_next_best_reference_is_the_second_of_the_choosers_own_order(lpf):  # D-18, spec 9.4 criterion 3
    c = classify(lpf)
    assert choose_reference(lpf, c, "U1.1", 0) == choose_reference(lpf, c, "U1.1")
    u = choose_reference(lpf, c, "U1.1", 1)
    assert (u.rule, u.pad, u.layer) == ("ic", "U1.4", "F.Cu")  # 1.5 mm off, after U1.2 at 0.5 mm
    j0, j1 = (choose_reference(lpf, c, "J1.1", k) for k in (0, 1))
    assert (j1.rule, j1.pad) == ("connector", "J1.2") and j1.uuid != j0.uuid  # the U.FL's other ground pad
    t = load_board(FIX / "coupon_gcpw_pads.kicad_pcb")
    ct = classify(t)
    r0, r1 = (choose_reference(t, ct, "TP1.1", k) for k in (0, 1))
    assert r0.point == pytest.approx((100.0, -100.6505), abs=1e-6) and (r1.rule, r1.layer) == ("copper", "F.Cu")
    assert r1.point == pytest.approx((100.0, -99.3495), abs=1e-6)  # the ground on the line's other side
    assert choose_reference(t, ct, "TP1.1", 2) is None
```
- [ ] **Step 2: Run** `python -m pytest tests/test_tracer.py -q`. Expected: FAIL (`rank` unexpected).
- [ ] **Step 3: Implement** the keyword as the Interfaces say.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: the reference chooser's next-best candidate, for P0-C's criterion 3 (D-18)`

---

### Task 7a [code]: The P0 folder and resumable steps (`tools/p0.py`, part 1)

**Files:**
- Create: `tools/p0.py`, `tests/test_p0.py`
- Modify: `pyproject.toml` (`pythonpath = ["tools"]` under `[tool.pytest.ini_options]`), `tests/conftest.py` (the `p0_out` fixture)

**Interfaces:**
- Consumes: `runs.data_dir`, `load_settings`, `machine_key`, `openems_versions`, `project_lock`; `project.save_project`; `KrsError`.
- Produces:
  - Constants: `p0.ROOT` (the repo), `p0.FIX = ROOT / "tests" / "fixtures"`, `p0.START = date(2026, 10, 22)` (D-4), `p0.MARKERS = ("kicad_rf_studio.worker", "emerge_fem", "pytest")`.
  - `default_out() -> Path`: `runs.data_dir().parent / "kicad-rf-studio-p0"`.
  - `inside_git(path: Path) -> bool`: whether `path` (resolved) or any of its parents holds a `.git` file or folder: no git process, so a missing git, a refused repo or a `GIT_DIR` cannot read as outside, and a worktree, a submodule, a file inside the repo and the `.git` folder itself all count as inside.
  - `enter(out: Path) -> Path`: `SystemExit` with a one-line reason, nothing made, for an `out` inside a git work tree; else makes `out/data`, sets `os.environ["LOCALAPPDATA"]` and `os.environ["XDG_DATA_HOME"]` to it, so this process's `runs.*` and every child use it (D-7), and holds `out/harness.lock` for the life of the process (`runs.project_lock(out / "harness", out)`, entered once per folder and kept in a module dict, so a second `enter` of the same folder in this process is a no-op); returns `out` resolved. Raises `E_LOCKED` while another live harness holds the folder.
  - `cli(*args: str) -> tuple[int, str]`: the product's CLI as a child: `[sys.executable, "-c", "import sys; from kicad_rf_studio.cli import main; sys.exit(main(sys.argv[1:]))", *args]` with `os.environ` plus `PYTHONIOENCODING=utf-8`, text decoded as UTF-8; returns (exit code, stdout then stderr).
  - `command_lines() -> list[str]`: every process's command line: `powershell -NoProfile -NonInteractive -Command "(Get-CimInstance Win32_Process).CommandLine"` on Windows, `/proc/*/cmdline` elsewhere; raises when the check cannot run.
  - `busy() -> dict`: `{"workers", "emerge", "pytest": the numbers of command lines holding each of MARKERS (each None when command_lines raised), "calibration": this machine's settings entry or None}`. `# ponytail: matched by substring, read at a step's start and end only; a process that starts and ends between them is not seen`.
  - `plain(o)`: the `json.dumps` default: a numpy scalar as its Python value, a complex number (Python or numpy) as `[re, im]`, an array as a list, a Path as its name, anything else as its `repr` (a long run's record is never lost to a TypeError).
  - `save(path: Path, data) -> dict`: `json.loads(json.dumps(data, default=plain), parse_constant=lambda _: None)` (NaN and ±inf become null), written by `save_project` (a temporary file then `os.replace`) after making the folder; returns it.
  - `code_id() -> str`: `git rev-parse HEAD:src` (the committed product tree), plus `"+dirty"` when `git status --porcelain --untracked-files=no -- src` prints anything.
  - `step(out: Path, step_id: str, key: str, work: Callable[[], dict]) -> dict`: `SystemExit` with a one-line reason when `out/STOP` exists, or when `runs.data_dir()` is not inside `out` (D-7, fail closed); the record in `out/steps/<step_id>.json` when it holds `f"{key}@{code_id()}"`; else `busy()`, `work()`, `busy()`, then `{"step", "key", "code": code_id(), "load", "load_end", "loaded", "started" (ISO time), "wall_s", "result"}` saved with `save`, so a crash leaves no record; `"loaded"` when either reading counts another process or is None. Returns the record as stored.
  - `records(out: Path, ids: list[str]) -> list[dict]`: each `out/steps/<id>.json`; `SystemExit` naming the missing ids, or the ids whose `"code"` differs from the first one's (a gate is never assembled from two codes).
  - `versions() -> dict`: `{"commit" (short HEAD), "code": code_id(), "python", "openems", "csxcad" (None when openEMS is missing), "os", "cpus"}` (no path, no host name).
  - `machine(records: list[dict]) -> dict`: `{"steps": n, "machine_hours": Σ wall_s / 3600, "loaded": [step ids], "elapsed_days": (today − START).days}`.
  - `table(rows: list[dict], cols: list[str]) -> str`: a Markdown table, floats as `:.4g`, None as "–".
  - `tests/conftest.py`:

```python
@pytest.fixture
def p0_out(tmp_path, monkeypatch, calibrated):
    """A P0 folder named with a space and an accent, with the fake worker and this machine's calibration in the
    data folder p0.enter makes inside it (D-7). Returns the folder; p0.enter stays the real one."""
    out = tmp_path / "p0 ação"
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, "unused")  # restored after the test; p0.enter sets both
    monkeypatch.setattr(runs, "data_dir", lambda: out / "data" / "kicad-rf-studio")
    runs.save_settings(json.loads((calibrated / "settings.json").read_text(encoding="utf-8")))
    return out
```

- [ ] **Step 1: Write the failing tests** in `tests/test_p0.py`:

```python
def test_enter_points_every_child_at_the_p0_data_folder(tmp_path, monkeypatch):  # D-7
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, "unused")  # restored after the test
    out = p0.enter(tmp_path / "p0 ação")
    assert (os.environ["LOCALAPPDATA"], os.environ["XDG_DATA_HOME"]) == (str(out / "data"),) * 2
    assert runs.data_dir() == out / "data" / "kicad-rf-studio" and (out / "harness.lock").is_file()
    code, text = p0.cli("new", str(p0.FIX / "coupon_gcpw_pads.kicad_pcb"), "--start", "TP1.1", "--end", "TP2.1",
                        "--f0", "915MHz", "-o", str(out / "proj"))
    assert code == 0 and "εr" in text  # a real child process, its UTF-8 text intact
    assert p0.enter(out) == out  # this process holds the lock already


def test_one_harness_per_p0_folder(tmp_path, monkeypatch):  # D-5
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, "unused")
    out = tmp_path / "p0"
    out.mkdir()
    (out / "harness.lock").write_text(json.dumps({"pid": os.getppid(), "run_dir": "x", "started": "y"}),
                                      encoding="utf-8")  # a live process that is not this one
    with pytest.raises(KrsError) as e:
        p0.enter(out)
    assert e.value.code == "E_LOCKED"


def test_a_p0_folder_inside_a_git_work_tree_is_refused(tmp_path):  # D-7, D-46
    inside = (p0.FIX, p0.FIX / "lpf915.kicad_pcb", p0.ROOT / "no-such-folder" / "x", p0.ROOT / ".git" / "x")
    assert all(map(p0.inside_git, inside)) and not p0.inside_git(tmp_path)
    with pytest.raises(SystemExit):
        p0.enter(p0.ROOT / "build" / "p0")
    assert not (p0.ROOT / "build" / "p0").exists()


def test_a_step_runs_once_reruns_when_its_key_or_code_changes_and_a_crash_leaves_nothing(tmp_path, fake,
                                                                                          monkeypatch):  # D-6; RF 1
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    calls = []

    def work():
        calls.append(1)
        return {"x": np.float64(1.5), "ok": np.bool_(True), "a": np.arange(3), "z": np.complex128(1 + 2j),
                "nan": math.nan, "p": Path("job-1-P1") / "waves.npz"}

    first, again = p0.step(tmp_path, "s1", "k1", work), p0.step(tmp_path, "s1", "k1", work)
    assert calls == [1] and first["result"] == again["result"] == {"x": 1.5, "ok": True, "a": [0, 1, 2],
                                                                   "z": [1.0, 2.0], "nan": None, "p": "waves.npz"}
    p0.step(tmp_path, "s1", "k2", work)
    monkeypatch.setattr(p0, "code_id", lambda: "other")
    p0.step(tmp_path, "s1", "k2", work)
    assert calls == [1, 1, 1]

    def dies():
        raise RuntimeError("reboot")

    with pytest.raises(RuntimeError):
        p0.step(tmp_path, "s2", "k1", dies)
    assert sorted(p.name for p in (tmp_path / "steps").iterdir()) == ["s1.json"]


def test_a_step_is_marked_loaded_beside_another_process_or_a_failed_check(tmp_path, fake, monkeypatch):  # D-6
    assert any("pytest" in c for c in p0.command_lines())  # the real check sees this test run
    monkeypatch.setattr(p0, "command_lines", lambda: ["python -I -u -m kicad_rf_studio.worker job.json", "x.exe"])
    rec = p0.step(tmp_path, "s", "k", lambda: {})
    assert rec["loaded"] and (rec["load"]["workers"], rec["load"]["emerge"], rec["load"]["pytest"]) == (1, 0, 0)
    monkeypatch.setattr(p0, "command_lines", lambda: ["x.exe"])
    assert not p0.step(tmp_path, "t", "k", lambda: {})["loaded"]

    def broken():
        raise OSError("no powershell")

    monkeypatch.setattr(p0, "command_lines", broken)
    rec = p0.step(tmp_path, "u", "k", lambda: {})
    assert rec["loaded"] and rec["load"]["workers"] is None


def test_a_step_refuses_a_stop_file_and_a_data_folder_outside_its_p0_folder(tmp_path, fake, monkeypatch):  # D-7
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    (tmp_path / "STOP").write_text("")
    with pytest.raises(SystemExit):
        p0.step(tmp_path, "s", "k", lambda: {})
    (tmp_path / "STOP").unlink()
    with pytest.raises(SystemExit):
        p0.step(tmp_path / "elsewhere", "s", "k", lambda: {})  # the fake's data folder is not inside it
    assert not (tmp_path / "steps").exists()


def test_records_refuse_a_missing_step_or_two_codes(tmp_path, fake, monkeypatch):  # D-51; Global Constraints
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    p0.step(tmp_path, "a", "k", lambda: {})
    p0.step(tmp_path, "b", "k", lambda: {})
    assert p0.machine(p0.records(tmp_path, ["a", "b"]))["steps"] == 2
    assert set(p0.versions()) == {"commit", "code", "python", "openems", "csxcad", "os", "cpus"}
    with pytest.raises(SystemExit):
        p0.records(tmp_path, ["a", "c"])
    monkeypatch.setattr(p0, "code_id", lambda: "other")
    p0.step(tmp_path, "b", "k2", lambda: {})
    with pytest.raises(SystemExit):
        p0.records(tmp_path, ["a", "b"])
    assert p0.table([{"a": 1.23456, "b": None}], ["a", "b"]).splitlines()[2] == "| 1.235 | – |"
```

  Test imports (`tests/test_p0.py`): `contextlib`, `io`, `json`, `math`, `os`, `Path`, `numpy as np`, `pytest`; `import p0`; `from kicad_rf_studio import runs`; `KrsError`. `tests/conftest.py` adds `import json`.
- [ ] **Step 2: Run** `python -m pytest tests/test_p0.py -q`. Expected: FAIL (no module `p0`).
- [ ] **Step 3: Implement** the pytest setting, the fixture and `tools/p0.py` as the Interfaces say (SPDX header; a docstring saying it is dev-time and never imported by the package).
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat(tools): the P0 folder, its lock and STOP file, resumable steps keyed by model and code, the load check and plain records (D-4..D-7; controller recommendation, owner unavailable)`

---

### Task 7b [code]: Runs, traces and chains (`tools/p0.py`, part 2), `growth_rise` and the layout at any frequencies

**Files:**
- Modify: `tools/p0.py`, `src/kicad_rf_studio/stoprule.py`, `src/kicad_rf_studio/core/post/waves.py` (`layout(f=)`)
- Test: `tests/test_p0.py`, `tests/test_stoprule.py`, `tests/test_post_waves.py`

**Interfaces:**
- Consumes: Task 7a; `runs.run_dir_for`, `job_dir`, `load_settings`, `per_job_mcs`; `pipeline.prepare`, `setup_gate`, `run_ports`, `records`, `load`, `build_model`, `Model`, `VERDICTS`; `stoprule.stop_rule`, `Records`, `KEPT`; `waves.layout`, `s_matrix`; `chain.part_impedances`, `loads`, `terminate`, `z_part`; `values.part_kind`, `port_value`; `project.load_project`, `parts`, `GATES`; `spec.spec_hash`; `gates.dt_floor_reference`; `Mesh`; `checks.compare`.
- Produces:
  - `stoprule.growth_rise(rec: Records, t0: float) -> float`: the largest rise, in dB, of the energy envelope over its running minimum after the pulse (te > 2·t0), 0.0 without one. `_growth` and it read one generator `_rises(rec, t0)` of (te, rise), so the statistic D-38 confirms exists once; `test_stoprule`'s growth tests guard the move.
  - `waves.layout(project: dict, results: dict, f: np.ndarray | None = None) -> Layout`: at `f` when given (EMerge's frequencies, another band's grid), its markers the indices of n·f0 found in `f`; the grid as today otherwise.
  - `LIMITS1 = {"ds21_db_f0": 0.1, "ds11_f0": 0.02, "ds_max": 0.03, "shift": 0.02}`; `criterion1(cmp: dict) -> dict`: `{"ds21_db_f0": bool, "ds11_f0": bool, "ds_max": bool, "nulls": "n/a" | bool, "pass": bool}` under LIMITS1; a null whose shift is None fails.
  - `model_of(spec: dict) -> Model`: `Model(Mesh(x, y, z of spec["mesh"] as arrays, 0.0, 0.0, {}, {}), spec, [], dt_floor_reference(that mesh))`.
  - `model_key(pj: Path) -> str`: `spec_hash` of the model `pipeline.load` and `build_model` give the project, or `"blocked"` when the edge lint left no spec.
  - `edit(project: dict, edits: dict) -> dict`: each dotted key (`"mesh.n"`) set in place, groups made as needed; returns `project`.
  - `run_path(name: str) -> Path`: `runs.data_dir() / "runs" / name` (every tool enters its P0 folder first, and `step` refuses a data folder outside it).
  - `run_model(model: Model, preset: str, stem: str, ports: list[int], t_max: float | None = None) -> dict`: the harness's job phase (D-9): `pipeline.prepare` (its lines printed), a fresh `runs.run_dir_for(stem)` on every call, `pipeline.setup_gate(model, {"gates": GATES}, run_dir, settings, threads)` — its blocking gates recorded, never applied — then, when `ports`, `pipeline.run_ports(model, run_dir, setup, threads, min(pool, len(ports)), preset, GATES, ports, t_max)`. Raises KeyboardInterrupt when any job was stopped, so a stopped run is never recorded. Returns `{"run_dir": its name, "setup": setup.json, "blocked": [[code, params]], "warnings": [[code, params]], "jobs": [the jobs as results record them, each plus "job": its folder name], "pool", "wall_s", "speeds_mcs"}`; `layout` reads the jobs.
  - `cli_run(pj: Path, command: str) -> dict`: `cli(command, str(pj))` for `run` or `verify`; RuntimeError (no record, the step reruns) on exit 1 or 130, or on exit 2 with `f"{pj}.lock"` in its output (E_LOCKED: an orphaned child holds the project); else `{"exit", "run_dir": the newest run folder named after the project's folder, "jobs": the jobs results (or verify) record for that folder, else None, "wall_s": likewise}`. An exit 4 is stored: its stopped verdicts could only come from a STOP file inside a run folder, which the stop procedure forbids.
  - `save_trace(job: Path, ports: int, dt: float, k: int, exc: dict, t_cut: float, out: Path) -> Path` and `load_trace(path: Path) -> tuple[Records, int, dict, float]`: `k` is the excited port, 1-based, stored as k − 1; `np.savez_compressed` of `pipeline.records(job, ports, dt)` as members `t_u, u, t_i, i, te, e`, plus `exc` ([f1, f2, t0]), `k` and `t_cut`. At most 50 kB (D-40): the energy rows are thinned by 2 while the file is larger; ValueError naming the job when the probe samples alone exceed it (never the probe samples thinned, never an endless loop). `load_trace` returns (Records, k − 1, {"f1", "f2", "t0"}, t_cut).
  - `s_of(traces: list[tuple[Records, int, dict, float | None]], f: np.ndarray, preset: str | None = None, rows: list[int] | None = None) -> tuple[np.ndarray, np.ndarray]`: each record replayed at `preset` (`stop_rule`, causal) and cut at its verdict, or cut at its own t_cut when `preset` is None; taken whole without one; u and i restricted to `rows` (default every port). One trace gives its column (F, N, 1), s_jk = (U_j − Z0·I_j)/(U_k + Z0·I_k); N traces give `s_matrix` (F, N, N). Returns (S, the cut times, NaN for a whole record). `# ponytail: one excitation gives a column that carries the feeds' port parasitics, the same on both sides of a comparison`. The one record-to-S reduction of the tools: the empty box, P0-C's per-preset replay and P0-D call it.
  - `closed_chain(pj: Path, *, f: np.ndarray | None = None, ideal: bool = False, cbox: dict | None = None, key: str = "results", cuts: list[float | None] | None = None) -> tuple[np.ndarray, np.ndarray, int]`: `layout(project, project[key], f=f)`, each job cut at `cuts[k]` in place of its t_cut when given, closed at each part port by Z_part ∥ C_box — the part models and S2P files as `run` writes chain.s{P}p, or the ideal values (`z_part(part_kind(ref), port_value(ref, value), None, f)`) when `ideal` — with `cbox` (by ref) in place of the run's `c_box` when given; returns (f, S (F, P, P), the index of f0). With `key="verify"` it is verify's own N-port, which has no part port.
  - `predicted_s(runs: int, pool: int, cells: int, dt: float, t: float, mcs: float) -> float`: `ceil(runs / pool) · cells · (t / dt) / (mcs · 1e6)`, cost_notes' formula (pipeline.py:197-198).
  - `summary(record: dict) -> dict`: a CLI run's numbers from its step record and its run folder (events.jsonl, model.json, setup.json): `{"exit", "cells" (I_COST_CELLS), "dt", "dt_ratio" (I_COST_DT's dt / ref), "pool" (I_RUN_START), "jobs": [{"port", "verdict", "t_cut", "t_stop", "residual_db", "growth_db"}] (the record's jobs, else the verdict events), "wall_s" (the run's job phase, else the step's), "predicted_s" (the run's longest kept t_stop) and "worst_s" (T_max), both with `runs.per_job_mcs` of the calibration the record's load saw at the step's start, "indicators": {"sigma", "recip", "loss_pct", "expected_pct"} (the result events, None when missing), "warnings" (the W_ codes among them), "lid_mm" (the lid plate's z in model.json minus the top copper face, None without a lid), "run_dir" (its name)}`; `growth_db` is `stoprule.growth_rise` on each job's records.

- [ ] **Step 1: Write the failing tests** in `tests/test_p0.py`:

```python
def in_process(*args):
    """p0.cli inside this process, so that the `fake` fixture's worker runs; other test files import it."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(list(args))
    return code, out.getvalue()


EXC40 = excitation({"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "t_max_s": 40e-9})
TWO = {**TINY, "excitation": EXC40,  # the fake's traces converge at about 10.7 ns at Normal; TINY's 1 ns never would
       "ports": [TINY["ports"][0], {**TINY["ports"][0], "name": "P2", "start": [3.0, 3.0, 0.0], "stop": [3.0, 3.0, 1.0],
                                    "nodes": [[3.0, 3.0, 0.0], [3.0, 3.0, 1.0], [3.0, 3.0, 0.0], [3.0, 3.0, 1.0]]}]}


def test_run_model_runs_only_the_excited_ports_and_records_its_gates(tmp_path, calibrated):  # D-9, D-17
    run = p0.run_model(p0.model_of(TWO), "normal", "two", [1])
    (job,) = run["jobs"]
    assert (job["port"], job["verdict"]) == ("P1", "converged")
    assert [code for code, _ in run["blocked"]] == ["E_DT_FLOOR"]  # the fake's dt on 1 mm cells: recorded, not applied
    folder = p0.run_path(run["run_dir"])
    assert (folder / job["waves"]).is_file() and not (folder / job["job"] / "et").exists()
    assert not list(folder.glob("job-2-*")) and run["run_dir"] != p0.run_model(p0.model_of(TWO), "normal", "two", [])["run_dir"]


def test_a_stopped_run_is_never_recorded(tmp_path, calibrated, ctrl_c_on_third_poll, monkeypatch):  # D-6; RF 1
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    with pytest.raises(KeyboardInterrupt):
        p0.step(tmp_path, "s", "k", lambda: p0.run_model(p0.model_of(TWO), "normal", "two", [1]))
    assert not (tmp_path / "steps" / "s.json").exists()


def test_a_trace_round_trips_and_replays_to_its_live_cut(tmp_path, calibrated):  # D-40
    run = p0.run_model(p0.model_of(TWO), "normal", "two", [1])
    job = run["jobs"][0]
    path = p0.save_trace(p0.run_path(run["run_dir"]) / job["job"], 2, run["setup"]["dt"], 1, TWO["excitation"],
                         job["t_cut"], tmp_path / "t.npz")
    rec, k, exc, t_cut = p0.load_trace(path)
    assert sorted(np.load(path).files) == ["e", "exc", "i", "k", "t_cut", "t_i", "t_u", "te", "u"]
    assert (k, t_cut) == (0, job["t_cut"]) and stop_rule(rec, k, "normal", exc).t == job["t_cut"]
    assert path.stat().st_size <= 50_000


def test_s_of_cuts_or_replays_each_record_and_reduces_it():  # D-35, D-48
    traces = [(network_trace(2, k, EXC40["f1"], EXC40["f2"], 1e-13, 40e-9), k, EXC40, None) for k in (0, 1)]
    s, t_cut = p0.s_of(traces, F, "draft")
    assert np.abs(s - star(F, 2)).max() <= 1e-5 and (t_cut < 40e-9).all()
    assert p0.s_of(traces[:1], F, "draft")[0].shape == (len(F), 2, 1)
    whole, cuts = p0.s_of(traces, F)  # no preset: each record's own t_cut, here none, so whole
    assert np.abs(whole - star(F, 2)).max() <= 1e-5 and np.isnan(cuts).all()
    three = [(network_trace(3, k, EXC40["f1"], EXC40["f2"], 1e-13, 40e-9), k, EXC40, None) for k in (0, 1)]
    assert np.abs(p0.s_of(three, F, rows=[0, 1])[0] - star(F, 3)[:, :2, :2]).max() <= 0.05  # port 3 stays loaded


def test_the_closed_chain_of_a_run_at_its_models_ideal_values_cuts_and_boxes(tmp_path, calibrated,
                                                                             monkeypatch):  # D-34, D-37, D-43
    pj = lpf_run(tmp_path, monkeypatch)  # tests/test_run.py: lpf915 on the network fake
    results = load_project(pj)["results"]
    assert p0.model_key(pj) == results["model_hash"]
    f, s, k0 = p0.closed_chain(pj)
    assert k0 == 71 and np.abs(s - terminate_np(star(F, 6), [0, 1], lpf_loads(M0402))).max() <= 1e-5
    f, s, _ = p0.closed_chain(pj, ideal=True, f=F[[71, 213]])
    assert np.abs(s - terminate_np(star(F, 6), [0, 1], lpf_loads(None))[[71, 213]]).max() <= 1e-5
    same = p0.closed_chain(pj, cuts=[j["t_cut"] for j in results["jobs"]], cbox=results["c_box"])[1]
    assert np.abs(same - p0.closed_chain(pj)[1]).max() == 0


def test_criterion_1_reads_the_spec_limits_and_no_null_as_na():  # spec 9.4 criterion 1
    ok = {"ds21_db_f0": 0.1, "ds11_f0": 0.02, "ds_max": 0.03, "nulls": []}
    assert p0.criterion1(ok) == {"ds21_db_f0": True, "ds11_f0": True, "ds_max": True, "nulls": "n/a", "pass": True}
    assert not p0.criterion1({**ok, "ds_max": 0.0301})["pass"]
    assert p0.criterion1({**ok, "nulls": [{"f_hz": 2.7e9, "shift": -0.021}]})["nulls"] is False
    assert p0.criterion1({**ok, "nulls": [{"f_hz": 2.7e9, "shift": None}]})["pass"] is False  # an unmatched null


def test_the_small_helpers():  # D-16; P0-B's dotted edits
    assert p0.predicted_s(6, 4, 2_694_450, 5.4043e-14, 17e-9, 120.0) == pytest.approx(
        2 * 2_694_450 * (17e-9 / 5.4043e-14) / 120e6)
    assert p0.edit({"mesh": {"n": 2}}, {"mesh.n": 3, "gates.fit2d_limit": 0.05}) == {
        "mesh": {"n": 3}, "gates": {"fit2d_limit": 0.05}}
```

  In `tests/test_stoprule.py`:

```python
def test_growth_rise_is_the_statistic_the_stop_rule_compares():  # D-38
    assert growth_rise(trace("growth"), EXC["t0"]) >= GROWTH_DB > 10 > growth_rise(trace("converge"), EXC["t0"])
```

  In `tests/test_post_waves.py`:

```python
def test_the_layout_at_other_frequencies_is_the_same_reduction(tmp_path):  # P0: EMerge's points, another band
    results = fake_run(tmp_path, synth_records(lambda f: star(f, 3), 3, F1, F2, DT, 10e-9),
                       [port("P1"), port("P2"), port("C1", True)])
    whole, some = layout(P915, results), layout(P915, results, f=F[[71, 213, 300]])
    assert np.array_equal(some.f, F[[71, 213, 300]]) and some.markers == [0, 1]
    assert np.abs(some.s - whole.s[[71, 213, 300]]).max() <= 1e-12
```

  Test imports (`tests/test_p0.py`, added): `main`; `stop_rule` from `stoprule`; `excitation` from `core.model.spec`; `grid` (`F, _ = grid(915e6, 3, 1.1)`); `from networks import network_trace, star, terminate_np`; `from test_model_csx import TINY`; `from test_post_chain import M0402`; `from test_run import lpf_loads, lpf_run`. `tests/test_stoprule.py` adds `GROWTH_DB`, `growth_rise`.
- [ ] **Step 2: Run** `python -m pytest tests/test_p0.py tests/test_stoprule.py tests/test_post_waves.py -q`. Expected: FAIL (`run_model`, `growth_rise` and the other names missing; `layout` takes no `f`).
- [ ] **Step 3: Implement** the stop rule's shared generator, `layout`'s keyword and the `p0` functions as the Interfaces say.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat(tools): run_model, cli_run, traces, s_of, closed chains and run summaries for the P0 harnesses, growth_rise in the stop rule, and layout at any frequencies (D-9, D-16, D-38, D-40)`

---

### Task 8a [code]: Probes in `build_csx` and the 2D box keyword (D-13, D-14)

**Files:**
- Modify: `src/kicad_rf_studio/core/model/csx.py`, `src/kicad_rf_studio/core/geometry/sections.py`
- Test: `tests/test_model_csx.py`, `tests/test_cs2d_coupons.py`

**Interfaces:**
- Produces:
  - `build_csx`: after the ports, each entry of an optional `spec["probes"]` — `{"name", "type" (0 voltage, 1 current), "weight", "norm_dir" (optional), "start", "stop"}` — becomes `csx.AddProbe(name, p_type=type, weight=weight[, norm_dir=…]).AddBox(start, stop)`. The product never writes the key; the worker leaves the probe files in the job folder (D-13).
  - `cross_section(sec, pieces, zs, mask, mode, dz0=None, box_h=BOX_H)`: the box runs `box_h` substrate heights past the line and past the stack (D-14); fit2d keeps BOX_H = 10.

- [ ] **Step 1: Write the failing tests.** In `tests/test_model_csx.py`:

```python
def test_probes_follow_the_ports(monkeypatch):  # D-13
    log = fake_openems(monkeypatch)
    volt = {"name": "s0_v1", "type": 0, "weight": 1, "start": [2.0, 2.0, 1.0], "stop": [2.0, 2.0, 0.0]}
    loop = {"name": "s0_i0", "type": 1, "weight": 1, "norm_dir": 0, "start": [2.5, 1.5, 0.5], "stop": [2.5, 2.5, 2.5]}
    build_csx({**TINY, "probes": [volt, loop]}, 1, 1e-9)
    names = [n for n, _, _ in log]
    assert ("AddProbe", ("s0_v1",), {"p_type": 0, "weight": 1}) in log
    assert ("AddProbe", ("s0_i0",), {"p_type": 1, "weight": 1, "norm_dir": 0}) in log
    assert ("AddBox", ([2.5, 1.5, 0.5], [2.5, 2.5, 2.5]), {}) in log and names.index("AddProbe") > names.index("AddLumpedPort")
```

  In `tests/test_cs2d_coupons.py`:

```python
@pytest.mark.parametrize(("name", "z0", "eeff"), [("coupon_ms", 48.863, 3.3576), ("coupon_ms_masked", 48.182, 3.4533),
                                                   ("coupon_gcpw", 50.197, 2.6516),
                                                   ("coupon_gcpw_masked", 47.308, 2.9853)])
def test_the_2d_box_can_grow_for_the_p0a_references(name, z0, eeff):  # D-14; r7 §2.1
    g, _ = geom_of(name)  # tests/test_gates.py
    s = g.sections[0]
    wide = solve(cross_section(s, g.pieces, g.zs, g.masks.get(s.layer), "exact", box_h=45))
    assert (wide.z0, wide.eps_eff) == (pytest.approx(z0, abs=2e-3), pytest.approx(eeff, abs=2e-4))
    assert solve(cross_section(s, g.pieces, g.zs, g.masks.get(s.layer), "exact")).z0 < wide.z0  # 10 h reads low
```
- [ ] **Step 2: Run** `python -m pytest tests/test_model_csx.py tests/test_cs2d_coupons.py -q`. Expected: FAIL (no probes; `box_h` unexpected).
- [ ] **Step 3: Implement** the four lines in `build_csx` and the keyword.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: optional probes in build_csx and the 2D cross-section's box height, for P0-A (D-13, D-14)`

---

### Task 8b [code]: The P0-A instrument (`tools/p0a.py`, part 1) (D-24, D-25)

**Files:**
- Create: `tools/p0a.py`, `tests/test_p0a.py`

**Interfaces:**
- Consumes: Tasks 7a–8a; `make_project`, `board_hash`, `classify`, `load_board`, `build_geometry`, `build_mesh`, `mesh_with_lint`, `edge_lint`, `fit2d`, `model_spec`, `cross_section`, `solve`, `substrate_h`, `grid`, `read_probe`; `kicad_lines.microstrip`, `cpwg` (p0a puts `tests/` on `sys.path`). r7's `e1_line.py` and `geo.py` (`.superpowers/sdd/plan5-research/r7-protocol/scripts/`) are the measured reference implementation of the triplet.
- Produces:
  - `p0a.COUPONS = ("coupon_ms", "coupon_ms_masked", "coupon_gcpw", "coupon_gcpw_masked", "coupon_dense", "coupon_gcpw_45", "coupon_gcpw_arc")`, `PAIRS = (("coupon_ms_masked", "coupon_ms"), ("coupon_gcpw_masked", "coupon_gcpw"))`, `TWINS = ("coupon_gcpw_45", "coupon_gcpw_arc")`, `MIDPOINTS = {"coupon_gcpw_45": (107.071, 92.929), "coupon_gcpw_arc": (109.609, 101.464)}` (KiCad frame; the line runs at 45° there), `BOX_REF = 45`, `F0 = 915e6`, `BAND = (0.6e9, 2.8e9)`, `LIMITS = {"z0_pct": 5.0, "eeff_pct": 3.0, "shift_z0_pp": 0.5, "shift_eeff_pp": 1.0, "twin_pct": 5.0, "delta_pp": 1.0, "dt_ratio": 0.85}` (the floor itself is `GATES["dt_floor"]`).
  - `coupon_project(name: str, n: int) -> tuple[Board, dict]`: `make_project` by hand (chain LINE alone, no part, no port, preset normal, `tests/test_cli_cost.by_hand`'s pattern) with `mesh.n` = n; the pad-less coupons cannot go through `new`.
  - `points(geom: Geometry, name: str) -> list[dict]`: `{"label", "at": [x, y] (internal frame), "normal": "x" | "y", "theta": degrees, "section": index | None}`: each section's cut, normal along its axis, theta 0, label `s<i>`; a twin also gets its midpoint (MIDPOINTS with y negated), normal "x", theta 45, label "mid".
  - `probe_set(geom: Geometry, mesh: Mesh, point: dict) -> list[dict]` (r7 §2.2, A-1): on the plane normal to `point["normal"]`, at the mesh line k nearest the point: voltage probes (type 0, weight 1) at lines k−1, k, k+1, each at the across line nearest the strip's centre on that plane, from the strip's bottom face to the top face of the copper under it (0.745 → 0.035 on the fixtures); current probes (type 1, weight 1, norm_dir of the normal axis) at the two duals between them, their sides across at the duals just outside the strip's span on that plane (between its outermost line inside and the next line out), in z from the dual 1.5 cells under its copper slab's bottom face to the dual 1.5 cells over its top. The strip's span on a plane comes from the plane's trace cut with the LINE piece holding the point. Names `<label>_v0..2`, `<label>_i0..1`.
  - `feeds(geom: Geometry, mesh: Mesh) -> list[dict]`: P1 and P2, vertical 50 Ω lumped ports at the mesh lines nearest the LINE track's two ends (the 45° coupon's too): `"kind": "lumped", "dir": "z"`, from the top face of the copper under the strip to the strip's bottom face, `"nodes": [start, stop, start, stop]`, `"part": False` (D-24).
  - `coupon_model(name: str, n: int, edits: dict | None = None) -> tuple[Model, Geometry, list[dict], int]`: the coupon's project with `p0.edit(project, edits)`, then the model (spec = `model_spec(project, board, geom, mesh, feeds, [])` plus `"probes"` of every point; `Model(mesh, spec, [], dt_floor_reference(mesh))`), its geometry, its points, and the first build's lint hits `len(edge_lint(build_mesh(geom, geom.protected, n)))`. fit2d is never applied (D-24, D-29). Raises E_EDGE_LINT as `mesh_with_lint` does.
  - `triplet(v: np.ndarray, i: np.ndarray, dv: tuple[float, float], di: float) -> tuple[np.ndarray, np.ndarray]`: MSLPort's equations (ports.py:436-447), spacings in m: Et = v[1], dEt = (v[2] − v[0])/(dv[0] + dv[1]), Ht = (i[0] + i[1])/2, dHt = (i[1] − i[0])/di; Z0 = √(Et·dEt/(Ht·dHt)); β = √(−dEt·dHt/(Ht·Et)), sign flipped where Re β < 0.
  - `eps_eff(beta: np.ndarray, f: np.ndarray, theta: float = 0.0) -> np.ndarray`: (Re β·cos θ·c0/(2πf))².
  - `line_constants(job: Path, probes: list[dict], f: np.ndarray, t_cut: float | None, theta: float) -> tuple[np.ndarray, np.ndarray]`: Z0 (complex) and εeff over `f` from one point's five probe files in `job`, each DFT'd on its own samples up to `t_cut` (whole when None); the spacings come from the probes' positions along the current probes' `norm_dir`.
  - `references(geom: Geometry, mesh: Mesh, point: dict) -> dict`: for a section point, `z0_ref` = KiCad's `microstrip(w, h, t, εr)` or `cpwg(w, gap, h, t, εr)` × cs2d's exact-mask over no-mask Z0 in the 45 h box (1 for a mask-free coupon; D-25, A-2), `eeff_ref` and `z0_2d` (cs2d, exact mask, `box_h=BOX_REF`), `z0_mesh` and `eeff_mesh` (cs2d on the mesh lines with the coat smeared over dz0, as fit2d's mesh side) and `e_fit` (fit2d's signed `z0_mesh/z0_ref − 1` of that section); `{}` for a midpoint.

- [ ] **Step 1: Write the failing tests** in `tests/test_p0a.py`:

```python
C0 = 299792458.0


def test_the_triplet_returns_the_lines_own_z0_and_the_discrete_beta():  # D-24, A-1; r7 §2.4
    f = np.array([0.6e9, 0.915e9, 2.8e9])
    beta, z0, d = 2 * np.pi * f * math.sqrt(3.41) / C0, 49.0, 75e-6
    x_v, x_i = np.array([-d, 0.0, d])[:, None], np.array([-d / 2, d / 2])[:, None]
    a, b = 1.0, 0.3 * np.exp(0.7j)  # a forward and a backward wave: exact for any mix
    v = a * np.exp(-1j * beta * x_v) + b * np.exp(1j * beta * x_v)
    i = (a * np.exp(-1j * beta * x_i) - b * np.exp(1j * beta * x_i)) / z0
    z, bt = p0a.triplet(v, i, (d, d), d)
    assert np.allclose(z, z0, rtol=1e-12, atol=0) and np.allclose(bt, 2 / d * np.sin(beta * d / 2), rtol=1e-9, atol=0)
    oblique = p0a.eps_eff(bt / math.cos(math.radians(45)), f, 45.0)  # x-normal planes across a 45° line
    assert np.allclose(oblique, (bt.real * C0 / (2 * np.pi * f)) ** 2, rtol=1e-12, atol=0)


def test_line_constants_read_the_probe_files_back(tmp_path):  # D-24: the files, their own sample times, the DFT
    z0, eeff, d = 49.0, 3.41, 75e-6
    v, t = C0 / math.sqrt(eeff), np.arange(0, 5e-9, 1e-11)
    probes = []
    for name, kind, x in (("p_v0", 0, -d), ("p_v1", 0, 0.0), ("p_v2", 0, d), ("p_i0", 1, -d / 2), ("p_i1", 1, d / 2)):
        tt = t + (5e-12 if kind else 0.0)  # currents half a step later, as openEMS writes them
        value = np.exp(-((tt - x / v - 1e-9) / 0.15e-9) ** 2) / (z0 if kind else 1.0)  # a forward pulse
        (tmp_path / name).write_text("% t/s\tvalue\n" + "".join(f"{p!r}\t{q!r}\n" for p, q in zip(tt, value)),
                                     encoding="utf-8")
        probes.append({"name": name, "type": kind, "weight": 1, **({"norm_dir": 0} if kind else {}),
                       "start": [110.0 + x * 1e3, -100.0, 0.745], "stop": [110.0 + x * 1e3, -100.0, 0.035]})
    z, e = p0a.line_constants(tmp_path, probes, np.array([915e6]), None, 0.0)
    assert z[0] == pytest.approx(z0, rel=1e-6) and e[0] == pytest.approx(eeff, rel=1e-4)


def test_a_coupon_model_has_two_vertical_feeds_and_a_triplet_at_the_cut():  # D-13, D-24
    model, geom, pts, lint = p0a.coupon_model("coupon_gcpw", 2)
    x = np.array(model.spec["mesh"]["x"])
    p1, p2 = model.spec["ports"]
    assert [(q["name"], q["dir"], q["start"][2], q["stop"][2], q["part"]) for q in (p1, p2)] == [
        ("P1", "z", 0.035, 0.745, False), ("P2", "z", 0.035, 0.745, False)]
    assert abs(p1["start"][0] - 100.0) < 0.08 and abs(p2["start"][0] - 120.0) < 0.08
    assert p1["start"][1] == p2["start"][1] == pytest.approx(-100.0, abs=0.04)
    assert [p["label"] for p in pts] == ["s0"] and lint == 0
    v0, v1, v2, i0, i1 = model.spec["probes"]
    assert [q["type"] for q in (v0, v1, v2, i0, i1)] == [0, 0, 0, 1, 1] and (i0["norm_dir"], i1["norm_dir"]) == (0, 0)
    k = int(np.flatnonzero(x == v1["start"][0])[0])
    assert (v0["start"][0], v2["start"][0]) == (x[k - 1], x[k + 1]) and abs(x[k] - 110.0) <= np.diff(x).max()
    assert (i0["start"][0], i1["start"][0]) == ((x[k - 1] + x[k]) / 2, (x[k] + x[k + 1]) / 2)
    assert (v1["start"][2], v1["stop"][2]) == (0.745, 0.035)
    lo, hi = sorted((i0["start"][1], i0["stop"][1]))
    assert -100.3 - 0.0752 < lo < -100.3 and -99.7 < hi < -99.7 + 0.0752  # just outside the 0.6 mm strip
    assert i0["start"][2] < 0.745 and i0["stop"][2] > 0.78


def test_the_twins_are_measured_at_their_midpoint_on_x_normal_planes():  # D-24
    assert p0a.points(build_geometry(*p0a.coupon_project("coupon_gcpw_45", 2)), "coupon_gcpw_45") == [
        {"label": "mid", "at": [107.071, -92.929], "normal": "x", "theta": 45.0, "section": None}]
    arc = p0a.points(build_geometry(*p0a.coupon_project("coupon_gcpw_arc", 2)), "coupon_gcpw_arc")
    assert [(p["label"], p["normal"], p["theta"]) for p in arc] == [("s0", "x", 0.0), ("s1", "y", 0.0),
                                                                    ("mid", "x", 45.0)]


@pytest.mark.parametrize(("name", "z0_ref", "eeff_ref"), [
    ("coupon_ms", 49.0393, 3.3576), ("coupon_ms_masked", 48.3558, 3.4533),
    ("coupon_gcpw", 51.7855, 2.6516), ("coupon_gcpw_masked", 48.8051, 2.9853)])
def test_the_references_are_kicad_and_the_45h_2d_line(name, z0_ref, eeff_ref):  # D-25, A-2
    model, geom, pts, _ = p0a.coupon_model(name, 2)
    ref = p0a.references(geom, model.mesh, pts[0])
    assert (ref["z0_ref"], ref["eeff_ref"]) == (pytest.approx(z0_ref, abs=2e-3), pytest.approx(eeff_ref, abs=2e-4))
    if name == "coupon_gcpw_masked":
        assert ref["e_fit"] == pytest.approx(0.0378, abs=2e-4)  # R-P2-20: the row the gate blocks at n = 2


@pytest.mark.openems
def test_the_triplet_reads_the_microstrip_coupon_in_real_openems(tmp_path, monkeypatch):  # D-24, A-1; about 1 min
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    runs.save_settings({"machines": {runs.machine_key(): {"threads": 4, "pool": 1, "aggregate_mcs": 400.0}}})
    model, geom, pts, _ = p0a.coupon_model("coupon_ms", 2)
    run = p0.run_model(model, "normal", "e1", [1], t_max=6e-9)
    (job,) = run["jobs"]
    z0, eeff = p0a.line_constants(p0.run_path(run["run_dir"]) / job["job"], model.spec["probes"],
                                  np.array([p0a.F0]), job["t_cut"], 0.0)
    assert job["verdict"] in KEPT  # r7 measured 49.117 Ω and 3.4099 at 6 ns
    assert z0[0].real == pytest.approx(49.117, abs=0.5) and eeff[0] == pytest.approx(3.410, abs=0.03)
```

  Test imports (`tests/test_p0a.py`): `json`, `math`, `numpy as np`, `pytest`; `import p0, p0a`; `from kicad_rf_studio import runs`; `build_geometry`; `KEPT` from `stoprule`; `from test_p0 import in_process`.
- [ ] **Step 2: Run** `python -m pytest tests/test_p0a.py -q`. Expected: FAIL (no module `p0a`).
- [ ] **Step 3: Implement** `tools/p0a.py`'s instrument as the Interfaces say (SPDX header; `tests/` put on `sys.path` at the top).
- [ ] **Step 4: Run** the full suite, then `python -m pytest -m openems tests/test_p0a.py -q`. Expected: all pass. If the openems test misses r7's numbers, never widen it: compare the probe geometry with r7 §2.2 and its `e1_line.py` first, then stop and report.
- [ ] **Step 5: Commit.** `feat(tools): the P0-A instrument — coupons with vertical feeds and probe triplets, MSLPort's equations and the KiCad and 45 h 2D references (D-24, D-25; A-1, A-2)`

---

### Task 8c [code]: The P0-A rules and driver (`tools/p0a.py`, part 2) (D-26..D-30)

**Files:**
- Modify: `tools/p0a.py`, `tests/test_p0a.py`

**Interfaces:**
- Consumes: Tasks 7a–8b; `p0.summary`, `p0.records`, `p0.step`, `p0.cli`, `p0.cli_run`, `p0.run_model`; `growth_rise`; `GATES`.
- Produces:
  - `rows(record: dict, name: str, n: int) -> list[dict]`: one coupon step's rows, computed at assembly: the model rebuilt by `coupon_model(name, n)` (its `spec_hash` must equal the step's key, else SystemExit), then per point `line_constants` and `references`. A step that recorded a lint failure gives the row `{"coupon", "n", "lint": "E_EDGE_LINT", "pass": False}`.
  - `measure(out: Path) -> dict`: `{"rows", "pairs", "twins", "pad", "stray"}` from the step records (`p0.records`):
    - a row: `coupon, n, point, theta, cells, dt, dt_ratio, lint, lint_first_hits, blocked, verdict, t_cut, growth_db, loaded, wall_s, predicted_s, z0 (Re Z0), z0_ref, dz0_pct, eeff, eeff_ref, deeff_pct, z0_band, eeff_band, e_fit_pct, delta_pp, z0_mesh, eeff_mesh, z0_2d, run_dir, pass` (read at f0 = grid index 71; the bands are min and max over BAND; `delta_pp` = e_FDTD − e_fit with e_FDTD = Re Z0/z0_2d − 1; `pass` = |dz0_pct| ≤ 5 and |deeff_pct| ≤ 3, None for a midpoint; `predicted_s` = `p0.predicted_s(1, 1, cells, dt, t_stop, runs.per_job_mcs(the step's calibration, 1))`; `growth_db` = `growth_rise` on the job's records);
    - a pair (masked, mask-free, same n): `pair, n, z0_fdtd_pct, z0_mesh_pct, z0_2d_pct, eeff_fdtd_pct, eeff_mesh_pct, eeff_2d_pct, miss_z0_pp, miss_eeff_pp, gap_z0_pp, gap_eeff_pp, pass` (miss = FDTD − on-mesh shift, judged at 0.5 pp and 1 pp; gap = FDTD − exact 2D shift, a stated limit; D-26);
    - a twin: `twin, n, z0_twin, z0_gcpw, dz0_pct, eeff_twin, eeff_gcpw, deeff_pct` (against coupon_gcpw's row at the same n; D-27), and for the arc `arc_mid_vs_straights` (its midpoint's |ΔZ0| in % against the mean of its own s0 and s1 in the same run; report only, r7 §2.5);
    - `pad`: `p0.summary` of the pad's run, plus `exit` ({"new", "cost", "run"}), `sigma`, `recip`, `loss_pct`, `loss_expected_pct` and `pass` (D-28: exits 0, both jobs converged, σ_max ≤ 1.02, reciprocity ≤ 0.02, loss_pct − loss_expected_pct ≤ 2, no W_ indicator);
    - `stray`: `dt_ratio` (setup dt over the rule mesh's dt_ref), `codes`, `trips` (E_DT_FLOOR among them).
  - `decide(m: dict) -> dict`, pure, on the rows that are axis-aligned section points whose job converged and whose model passed its lint ("counted rows"); every other row is left out of the rules and named among the fails:
    - `"fit2d"` (D-29): `{"rule": "D-29", "i_at_3": bool, "limit_pct": float, "max_delta_pp": float, "ii": bool, "branch": "keep" | "keep-state" | "lower" | "unpredicted"}`. (i) at L % holds when every counted row with |e_fit_pct| ≤ L passes D-25 (Z0 and εeff); L starts at 3 and drops by 0.5 while (i) fails, never below 1.5 (a pre-registered floor: below it no GCPW row is left to judge, and L 0 would block every model). (ii) is max |delta_pp| ≤ 1 over the counted rows. `keep` when (i) holds at 3 and (ii) holds; `keep-state` when only (ii) fails; `lower` when (i) holds at an L from 2.5 to 1.5; `unpredicted` when (i) still fails at 1.5: no limit change (`limit_pct` 3.0), the P0-A verdict fails, and the failing rows become stated limits and the Stage 2 calibration item (D-31).
    - `"dt_floor"` (D-30, P0-A's part): `{"rule": "D-30", "min_ratio": the smallest dt_ratio over the rows and the pad, "stray_ratio", "stray_trips"}`; P0-B adds its own meshes and decides (Task 9).
    - `"mask_shift"`: `{"rule": "D-26", "pass": bool}`.
    - `"twins"` (D-27): `{"rule": "D-27", "max_dz0_pct": float, "branch": "refuse" | "advice" | "keep"}`: `refuse` when max |dz0_pct| over both twins and both n is > 5; else `advice` when every twin's |dz0_pct| at n = 3 is below its n = 2 value; else `keep`.
    - `"pad"`: `{"rule": "D-28", "pass": bool}`.
    - `"verdict"`: `{"value": "pass" | "fail", "fails": [text]}`: pass when every counted row within the final limit passes, no row is left out, both pairs pass at both n, the pad passes, and fit2d is not `unpredicted`.
  - `tables(result: dict) -> str`: tables A1 (rows), A2 (pairs), A3 (twins), A4 (pad), A5 (decisions) with `p0.table`.
  - `write(out: Path) -> dict`: measure, decide and tables into `<out>/p0a/p0a.json` (`{"gate": "P0-A", "versions", "calibration", "rows", "pairs", "twins", "pad", "stray", "decisions", "machine"}`, through `p0.save`) and `p0a.md`; returns the JSON.
  - `main(argv=None) -> int`: `python tools/p0a.py [--out DIR] [--only ID[,ID…]] [--report]`; `p0.enter(out)` first; steps, each through `p0.step` and logged and skipped on an exception (exit 1 at the end): `p0a-calibrate` (key "once": `p0.cli("calibrate")`), `p0a-<coupon>-n<2|3>` (14, key the model's `spec_hash`: `p0.run_model(model, "normal", step id, [1])` plus `lint_first_hits`; a coupon whose `coupon_model` raises E_EDGE_LINT records `{"lint": [code, params]}` with key "E_EDGE_LINT"), `p0a-pad` (key the pad project's `p0.model_key`: `new` from the board copied into `<out>/boards`, `cost`, then `p0.cli_run(pj, "run")`, all at Normal, project in `<out>/p0a/projects/coupon_gcpw_pads`), `p0a-stray` (key the stray spec's `spec_hash`: coupon_gcpw at n = 2 with one x line added 10 µm from the line nearest the cut, `run_model(Model(model_of(stray spec).mesh, stray spec, [], the rule mesh's dt_ref), "normal", step id, [])`); then `write(out)` when every step's record exists. `--report` writes from the records and starts no step.

- [ ] **Step 1: Write the failing tests** in `tests/test_p0a.py`:

```python
def test_the_p0a_rules():  # D-26, D-27, D-29, D-30; RF 2
    def r(e_fit, dz0, deeff=0.0, delta=0.2, verdict="converged", dt=1.0):
        return {"coupon": "coupon_gcpw", "n": 2, "point": "s0", "section": 0, "e_fit_pct": e_fit, "dz0_pct": dz0,
                "deeff_pct": deeff, "delta_pp": delta, "verdict": verdict, "lint": None, "dt_ratio": dt,
                "pass": abs(dz0) <= 5 and abs(deeff) <= 3}

    def twin(d2, d3, name="coupon_gcpw_45"):
        return [{"twin": name, "n": 2, "dz0_pct": d2}, {"twin": name, "n": 3, "dz0_pct": d3}]

    m = {"rows": [r(2.55, 1.0, dt=0.95), r(3.78, 0.5), r(-3.5, 6.0)], "pairs": [{"pass": True}],
         "twins": twin(3.0, 2.0) + twin(2.5, 1.5, "coupon_gcpw_arc"), "pad": {"pass": True, "dt_ratio": 0.92},
         "stray": {"dt_ratio": 0.45, "trips": True}}
    d = p0a.decide(m)  # the −3.5 % row lies outside |e_fit| ≤ 3: the gate filters on the magnitude
    assert (d["fit2d"]["branch"], d["fit2d"]["i_at_3"], d["twins"]["branch"]) == ("keep", True, "advice")
    assert d["verdict"] == {"value": "pass", "fails": []}
    assert d["dt_floor"] == {"rule": "D-30", "min_ratio": 0.92, "stray_ratio": 0.45, "stray_trips": True}
    assert p0a.decide({**m, "rows": [r(2.9, 5.6), r(2.4, 1.0)]})["fit2d"] == {
        "rule": "D-29", "i_at_3": False, "limit_pct": 2.5, "max_delta_pp": 0.2, "ii": True, "branch": "lower"}
    assert p0a.decide({**m, "rows": [r(2.55, 1.0, deeff=3.2)]})["fit2d"]["branch"] == "lower"  # εeff counts in (i)
    assert p0a.decide({**m, "rows": [r(2.5, 1.0, delta=1.3)]})["fit2d"]["branch"] == "keep-state"
    low = p0a.decide({**m, "rows": [r(2.5, 1.0), r(0.3, 6.0)]})  # a row fit2d cannot explain: the floor holds
    assert (low["fit2d"]["branch"], low["fit2d"]["limit_pct"], low["verdict"]["value"]) == ("unpredicted", 3.0, "fail")
    flat = p0a.decide({**m, "rows": [r(2.5, 1.0), r(2.0, 9.0, verdict="t_max")]})  # left out, and named
    assert (flat["fit2d"]["branch"], flat["verdict"]["value"], len(flat["verdict"]["fails"])) == ("keep", "fail", 1)
    lint = {"coupon": "coupon_dense", "n": 3, "lint": "E_EDGE_LINT", "pass": False}
    assert p0a.decide({**m, "rows": [r(2.5, 1.0), lint]})["verdict"]["value"] == "fail"
    assert p0a.decide({**m, "twins": twin(-6.0, 4.0)})["twins"]["branch"] == "refuse"
    assert p0a.decide({**m, "twins": twin(3.0, 4.0) + twin(2.5, 1.5, "coupon_gcpw_arc")})["twins"]["branch"] == "keep"


def test_the_p0a_steps_run_through_the_harness_and_the_product(p0_out, monkeypatch):  # D-9, D-28, D-30
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    assert p0a.main(["--out", str(p0_out), "--only", "p0a-coupon_ms-n2,p0a-pad"]) == 0
    coupon, pad = (rec["result"] for rec in p0.records(p0_out, ["p0a-coupon_ms-n2", "p0a-pad"]))
    assert [j["verdict"] for j in coupon["jobs"]] == ["converged"] and coupon["blocked"] == []
    assert pad["exit"] == {"new": 0, "cost": 0, "run": 0}
    summary = p0.summary(p0.records(p0_out, ["p0a-pad"])[0])
    assert [j["verdict"] for j in summary["jobs"]] == ["converged"] * 2 and summary["warnings"] == ["W_LOSS_BUDGET"]
    monkeypatch.setenv("KRS_FAKE_SETUP", json.dumps({"dt": 5e-14}))  # under 0.8 × coupon_gcpw's 6.7e-14 s
    assert p0a.main(["--out", str(p0_out), "--only", "p0a-stray"]) == 0
    stray = p0.records(p0_out, ["p0a-stray"])[0]["result"]
    assert [code for code, _ in stray["blocked"]] == ["E_DT_FLOOR"] and stray["jobs"] == []
```
- [ ] **Step 2: Run** `python -m pytest tests/test_p0a.py -q`. Expected: FAIL (`decide` and `main` missing).
- [ ] **Step 3: Implement** the rules, the assembly and the driver as the Interfaces say.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat(tools): the P0-A rules and driver — rows assembled from the run folders, the fit2d floor, the dt floor's P0-A part, the mask shift and the twins (D-26..D-30; controller recommendation, owner unavailable)`

---

### Task 9 [code]: The P0-B harness (`tools/p0b/harness.py`) (D-30, D-32..D-40)

**Files:**
- Create: `tools/p0b/harness.py`, `tests/test_p0b.py`
- Modify: `tests/fake_worker.py` (setup mode writes an empty `operator_dump.vtr` when a port holds a part)

**Interfaces:**
- Consumes: Tasks 7a–8c; Task 3's `mesh.reach_h`; `pipeline.load`, `build_model`, `records`; `core.model.spec` as a module (`verify_spec`, `K_MAX`, `c_box`); `fit2d`; `terminate`, `with_box`, `loads`; `compare`; `grid`; `load_project`, `save_project`, `parts`; `growth_rise`, `KEPT`; `scipy.optimize.least_squares`.
- Produces:
  - `NEW = ("--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "--lid-height", "2.5")` (D-32: 2.5 mm, as r1, r3 and r7).
  - `VARIANTS = {"B1": ("lpf915", {}), "B4": ("lpf915-45", {"allow_curve_port": True}), "B5": ("lpf915", {"mesh.n": 3, "gates.fit2d_limit": 0.05}), "B6": ("lpf915", {"mesh.reach_h": 6.0})}`.
  - `K_SWEEP = (0.35, 0.40, 0.45, 0.48, 0.50, 0.55)`, `KMAX_T_MAX = 10e-9` (185,000 steps at lpf915's 5.4e-14 s: r3 B-6 saw k 0.49 diverge only after about 52,700 steps; about 18.5 min a value, 1.9 h in all, inside D-39's 2 h), `REACH = {"ds21_db_f0": 0.033, "ds11_f0": 0.0067, "ds_max": 0.01}` (a third of criterion 1, D-37), `GROWTH_LIMIT_DB = 10.0` (D-38).
  - `project(out: Path, run_id: str) -> Path`: `<out>/p0b/projects/<run_id>/project.json`, made by `p0.cli("new", <board copied into <out>/boards>, *NEW, "-o", folder)` when missing; then VARIANTS' edits through `p0.edit` on every call, saved only when something changed, so an interruption between `new` and the edits never leaves a wrong project behind.
  - `evidence(record: dict) -> dict` (D-40), from the run folder: `{"jobs": [{"port", "event": bool (an I_JOB_CONVERGED verdict event for that job), "abort": bool (an ABORT file in its folder), "order": bool (t_cut < t_stop < t_max_s), "ok"}], "cut_delta": max |S of the jobs cut at t_cut − S of their whole records| (stop-latency evidence only), "trunc_2ns": max |S cut at t_cut − S cut 2 ns earlier| (a truncation estimate), "ok": every job ok and cut_delta ≤ 2e-3}`. Event params are never copied: I_JOB_CONVERGED carries an absolute log path.
  - `fit_cp(s: np.ndarray, f: np.ndarray, c_box: dict, refs: list[str], measured: dict[str, np.ndarray], empty: dict[str, list[str]]) -> tuple[dict[str, float], float]`: C_p per part box, fitted jointly over both variants, every f and entry (real and imaginary parts), in fF from C_box: `terminate(s, [0, 1], zk(C_p))` against each measured 2-port, an emptied box closed by 1/(jωC_p) and a passive one by 50 Ω ∥ C_p (`with_box`); returns the C_p by ref and the condition number of the fit's Jacobian at the solution, which the report prints (a C_p of an ill-conditioned fit, cond > 1e3, is stated as not identified).
  - `empty_box(out: Path) -> dict` (D-35, r7 §3.5): from B1's run's `model.json`, variant A without the C1 and L1 ports and B without C2 and C3 (same mesh and materials), each run as steps `p0b-B3-A` and `p0b-B3-B` by `p0.run_model(p0.model_of(spec), "normal", step id, [1, 2])`; at assembly the FDTD 2-ports are `p0.s_of(each job's records with its own t_cut, f, rows=[0, 1])`, the co-sim side `terminate(B1's layout S, [0, 1], zk, f)` with 1/(jωC_box) at an emptied box and `with_box(50, f, C_box)` at a passive one. Returns `{"A": {"ds_max", "ds11_f0", "ds21_f0"}, "B": {…}, "c_box": {ref: F}, "c_p": {ref: F}, "dc_ff": {ref: fF}, "cond": float, "verify_ds_max": {"c_box": float, "c_p": float}}`, the last being B2's comparison with the retune closed by C_box and by C_p (`p0.closed_chain(B1, ideal=True, cbox=…)` against `p0.closed_chain(B1, key="verify")`). Report only.
  - `kmax_values(dt: float, c_cell: float) -> list[tuple[float, float]]`: (k, L) with L = (dt/(2k))²/c_cell for k in K_SWEEP.
  - `kmax_sweep(out: Path) -> None` (D-39): B1's model rebuilt (its hash checked against its results), the L1 cell's C read from `verify_spec`'s grid entry at the as-built values, then per k a step `p0b-kmax-<k>`: `verify_spec` with L1's value `f"{L * 1e12:.6g}pH"` and `spec.K_MAX` set to 1.0 while it is built (restored in `finally`; `# ponytail: patches the module's K_MAX for this process while verify_spec builds the sweep's spec`), run by `p0.run_model(p0.model_of(vspec), "strict", step id, [1], t_max=KMAX_T_MAX)`. Strict, because its −70 dB level cannot stop lpf915 before about 18 ns (r4 §2.5), so every value runs its 10 ns unless it grows.
  - Step keys: `p0b-B1`, `-B4`, `-B5`, `-B6`: the project's `p0.model_key`; `p0b-B2` (`verify` on B1's project), `p0b-B3-A`/`-B3-B` and `p0b-kmax-<k>`: their own model hash (B2: B1's) plus B1's record's `run_dir`, so they rerun when B1 does. The CLI steps are `p0.cli_run(pj, "run")` (or `"verify"`).
  - `measure(out: Path) -> dict`, from the step records, the projects, the run folders and `<out>/p0a/p0a.json` (SystemExit without it):
    - `"runs"`: {run: `p0.summary`} for B1, B2, B4, B5, B6; `"evidence"`: {"B1", "B2", "B4": evidence};
    - `"consistency"`: B2's stored `verify.compare`;
    - `"tx"`: `compare(a=B1's chain, b=B4's chain, f, k0, 0.02)`, each as `p0.closed_chain` writes it (own cuts, part models: D-34's measure); `"tx_ideal"`: the same at the ideal values (report, r7 §3.4);
    - `"reach"`: B6 against B1 with each job cut at the common time T_k = min(B1's t_cut, B6's t_cut) of job k (`closed_chain(cuts=…)`; whole only when both are None), so the plane-pair tail both share cancels and the reach effect remains (D-37's measure); `"reach_stored"`: the comparison as each run cut itself (report);
    - `"bias"`: `{"fit2d_n2", "fit2d_n3"` (% per section, from B1's and B5's models), `"compare"` (B5 against B1 as stored), `"compare_common"` (at common cuts), `"s21_db"` ({"f0", "2f0", "3f0"}: [n2, n3]), `"lid_mm"` ({"n2", "n3"})};
    - `"empty_box"`; `"kmax"`: `[{"k", "l_h", "verdict", "t_ns", "growth_db"}]`;
    - `"verdicts"`: {run: [kind]} for B1, B2, B3 (A and B jobs), B4, B5, B6, and "p0a" (every P0-A row's and the pad's job verdicts);
    - `"growth_db"`: the rise of every healthy job (B1–B6, B3, every P0-A row and the pad);
    - `"dt_ratios"`: {"p0a_min": p0a.json's decisions.dt_floor.min_ratio, "B1", "B2", "B4", "B5", "B6": each run's dt / dt_ref}; `"stray"`: p0a.json's stray;
    - `"emerge"`: `<out>/p0b/emerge.json`, or None.
  - `decide(m: dict) -> dict`, pure:
    - `"consistency"`: criterion1 of it, plus `"verify_converged"` (both B2 jobs converged);
    - `"tx"`: criterion1, `"all_converged"` over the 12 B1 and B4 jobs, `"pass"`;
    - `"reach"`: `{"confirmed"}` under REACH;
    - `"growth"`: `{"max_db", "healthy_growth" (the runs, "p0a" included, with a growth verdict), "sweep_caught", "confirmed"}`: a sweep value is unstable when it ended growth or diverged, or ended at t_max with growth_db ≥ GROWTH_LIMIT_DB; `sweep_caught` = at least one value is unstable and every unstable value ended growth or diverged; confirmed = max ≤ 10 dB, no healthy growth and the sweep caught (nothing unstable means D-38's diverging case was not exercised: not confirmed);
    - `"kmax"`: a value is stable when its verdict is in KEPT and it is not unstable; `{"stable_through", "confirmed": every k ≤ 0.48 stable, "k_max": 0.45, else 0.9 × the lowest k that is not stable}`;
    - `"dt_floor"` (D-30, final): `{"rule": "D-30", "min_ratio": the smallest of p0a_min and P0-B's ratios, "stray_ratio", "stray_trips", "confirmed": min ≥ 0.85 and the stray cell trips}`;
    - `"verdict"`: `{"value": "pass" | "fail" | "pending", "fails": [text], "emerge_accepted": bool}`: pass needs consistency and verify_converged, every B1, B2 and B4 job converged, and EMerge passed or inconclusive with an accepted cause — accepted only when every FDTD-internal criterion passed and every reason is an EMerge precondition (D-44); pending without emerge.json; the twin never decides the verdict (O-11).
  - `tables(result) -> str` (B-runs, B-consistency, B-twin, B-Cbox, B-n, B-EMerge, B-constants); `write(out: Path) -> dict`: `<out>/p0b/p0b.json` (`{"gate": "P0-B", "versions", "calibration", **measure, "decisions": decide, "machine"}`, through `p0.save`, over every P0-B record and the EMerge ones that exist) and `p0b.md`.
  - `main(argv=None) -> int`: `python tools/p0b/harness.py [--out DIR] [--only B1,B2,B3,B4,B5,B6,kmax] [--report]`; `p0.enter(out)` first; each step through `p0.step`, logged and skipped on an exception (exit 1 at the end); `write(out)` when every P0-B step's record exists, so night 3 ends with `p0b.json` pending and Task 15 rewrites it. `--report` writes from the records and starts no step.

- [ ] **Step 1: Write the failing tests** in `tests/test_p0b.py`:

```python
def skewed(f):
    """A passive, reciprocal 6-port whose ports differ (each its own line): networks.star is symmetric in its ports,
    so on it the A/B design only sees C1 + L1 and C2 + C3, and the four C_p cannot be told apart."""
    a, tau = np.array([0.95, 0.94, 0.96, 0.93, 0.97, 0.92]), np.array([0.20, 0.25, 0.10, 0.35, 0.15, 0.30]) * 1e-9
    g = a * np.exp(-2j * np.pi * np.asarray(f)[:, None] * tau)
    return g[:, :, None] * (2 / 6 * np.ones((6, 6)) - np.eye(6)) * g[:, None, :]


P0A = {"rows": [{"verdict": "converged", "growth_db": 0.0}], "pad": {"jobs": [{"verdict": "converged", "growth_db": 0.0}]},
       "stray": {"dt_ratio": 0.45, "trips": True},
       "decisions": {"dt_floor": {"min_ratio": 0.92, "stray_ratio": 0.45, "stray_trips": True}}}


def test_the_p0b_projects_are_fresh_projects_with_their_edits(p0_out, monkeypatch):  # D-32, D-9
    monkeypatch.setattr(p0, "cli", in_process)
    b5, b4, b6 = (load_project(harness.project(p0_out, r)) for r in ("B5", "B4", "B6"))
    assert (b5["mesh"], b5["gates"]["fit2d_limit"], b5["lid_height_mm"]) == ({"n": 3, "reach_h": 3.0}, 0.05, 2.5)
    assert b4["allow_curve_port"] is True and b6["mesh"] == {"n": 2, "reach_h": 6.0}
    assert (p0_out / "boards" / "lpf915-45.kicad_pcb").is_file()
    pj = harness.project(p0_out, "B5")
    d = load_project(pj)
    d["mesh"]["n"] = 2  # an interruption between new and the edits
    save_project(pj, d)
    assert load_project(harness.project(p0_out, "B5"))["mesh"]["n"] == 3


def test_the_empty_box_fit_recovers_the_box_capacitances():  # D-35; r7 §3.5
    refs, empty = ["C1", "L1", "C2", "C3"], {"A": ["C1", "L1"], "B": ["C2", "C3"]}
    c_box = {"C1": 2.388e-15, "L1": 2.735e-15, "C2": 1.397e-15, "C3": 1.390e-15}  # lpf915 at n = 2
    true = {"C1": 1.4e-15, "L1": 3.2e-15, "C2": 1.9e-15, "C3": 0.9e-15}
    w, s = 2 * np.pi * F, skewed(F)

    def closed(run):
        zk = np.stack([1 / (1j * w * true[r]) if r in empty[run] else with_box(np.full(len(F), 50.0 + 0j), F, true[r])
                       for r in refs], -1)
        return terminate(s, [0, 1], zk, F)

    fitted, cond = harness.fit_cp(s, F, c_box, refs, {run: closed(run) for run in empty}, empty)
    assert {r: round(v * 1e15, 3) for r, v in fitted.items()} == {r: round(v * 1e15, 3) for r, v in true.items()}
    assert 1 <= cond < 1e3


def test_the_k_sweep_inductances_give_back_their_k():  # D-39
    dt, c = 5.4043e-14, 2.0e-15
    assert [k for k, _ in harness.kmax_values(dt, c)] == [0.35, 0.40, 0.45, 0.48, 0.50, 0.55]
    for k, l in harness.kmax_values(dt, c):
        assert dt / (2 * math.sqrt(l * c)) == pytest.approx(k, rel=1e-12)


def test_the_p0b_rules():  # D-30, D-33, D-34, D-37..D-39, D-44; O-11; RF 2
    ok = {"ds21_db_f0": 0.05, "ds11_f0": 0.01, "ds_max": 0.02, "nulls": []}
    verdicts = {"B1": ["converged"] * 6, "B2": ["converged"] * 2, "B3": ["converged"] * 4, "B4": ["converged"] * 6,
                "B5": ["converged"] * 6, "B6": ["converged"] * 6, "p0a": ["converged"] * 16}
    sweep = [{"k": k, "verdict": "t_max", "growth_db": 0.0} for k in harness.K_SWEEP[:4]] + [
        {"k": 0.50, "verdict": "growth", "growth_db": 25.0}, {"k": 0.55, "verdict": "diverged", "growth_db": 40.0}]
    m = {"consistency": ok, "tx": ok, "reach": {"ds21_db_f0": 0.02, "ds11_f0": 0.005, "ds_max": 0.008, "nulls": []},
         "verdicts": verdicts, "growth_db": [0.0, 3.2], "kmax": sweep, "emerge": {"verdict": "pass", "reasons": []},
         "dt_ratios": {"p0a_min": 0.92, "B1": 1.05, "B5": 1.01}, "stray": {"dt_ratio": 0.45, "trips": True}}
    d = harness.decide(m)
    assert (d["verdict"]["value"], d["tx"]["pass"], d["reach"]["confirmed"], d["growth"]["confirmed"]) == (
        "pass", True, True, True)
    assert (d["kmax"]["confirmed"], d["kmax"]["k_max"], d["dt_floor"]["confirmed"]) == (True, 0.45, True)
    low = [{**s, "verdict": "growth"} if s["k"] == 0.45 else s for s in sweep]
    assert harness.decide({**m, "kmax": low})["kmax"]["k_max"] == pytest.approx(0.405)
    creeping = [{**s, "growth_db": 14.0} if s["k"] == 0.48 else s for s in sweep]  # t_max, still rising
    d = harness.decide({**m, "kmax": creeping})
    assert (d["kmax"]["confirmed"], d["kmax"]["k_max"], d["growth"]["sweep_caught"]) == (
        False, pytest.approx(0.432), False)
    calm = [{**s, "verdict": "t_max", "growth_db": 0.0} for s in sweep]  # nothing diverged: growth not exercised
    d = harness.decide({**m, "kmax": calm})
    assert (d["kmax"]["confirmed"], d["growth"]["confirmed"]) == (True, False)
    assert not harness.decide({**m, "reach": {**ok, "ds_max": 0.011}})["reach"]["confirmed"]
    assert not harness.decide({**m, "growth_db": [10.5]})["growth"]["confirmed"]
    assert not harness.decide({**m, "verdicts": {**verdicts, "p0a": ["growth"]}})["growth"]["confirmed"]
    assert not harness.decide({**m, "dt_ratios": {**m["dt_ratios"], "B5": 0.84}})["dt_floor"]["confirmed"]
    one_t_max = {**verdicts, "B1": ["converged"] * 5 + ["t_max"]}
    assert harness.decide({**m, "verdicts": one_t_max})["verdict"]["value"] == "fail"
    flat_b2 = {**verdicts, "B2": ["converged", "flat"]}
    assert harness.decide({**m, "verdicts": flat_b2})["consistency"]["verify_converged"] is False
    inconclusive = {"verdict": "inconclusive", "reasons": ["coupon_gcpw z0 -5.20 %"]}
    assert harness.decide({**m, "emerge": inconclusive})["verdict"] == {"value": "pass", "fails": [],
                                                                        "emerge_accepted": True}
    assert harness.decide({**m, "emerge": inconclusive, "consistency": {**ok, "ds_max": 0.05}})["verdict"]["value"] == "fail"
    assert harness.decide({**m, "emerge": None})["verdict"]["value"] == "pending"
    assert harness.decide({**m, "tx": {**ok, "ds_max": 0.04}})["verdict"]["value"] == "pass"  # the twin decides the TX side only


def test_p0b_on_the_fake_worker_writes_a_plain_private_free_gate_json(p0_out, monkeypatch):  # D-40, D-51; RF 3
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)  # verify's L cell: the fake's dump is empty
    p0.save(p0_out / "p0a" / "p0a.json", P0A)
    assert harness.main(["--out", str(p0_out)]) == 0  # every step, then p0b.json
    text = (p0_out / "p0b" / "p0b.json").read_text(encoding="utf-8")
    data = json.loads(text)
    json.dumps(data, allow_nan=False)
    assert gate.scan_text(text, [], generic=True) == []
    assert data["decisions"]["verdict"]["value"] == "pending"  # no emerge.json yet
    b1 = data["evidence"]["B1"]
    assert b1["ok"] and all(isinstance(j[key], bool) for j in b1["jobs"] for key in ("event", "abort", "order"))
    assert [s["k"] for s in data["kmax"]] == list(harness.K_SWEEP)
```

  Test imports: `json`, `math`, `numpy as np`, `pytest`; `import p0`; `import privacy_gate as gate`; `from p0b import harness`; `load_project`, `save_project`; `from kicad_rf_studio.core.model import spec as spec_module`; `grid` (`F, _ = grid(915e6, 3, 1.1)`); `terminate`, `with_box`; `from test_p0 import in_process`.
- [ ] **Step 2: Run** `python -m pytest tests/test_p0b.py -q`. Expected: FAIL (no module `p0b.harness`).
- [ ] **Step 3: Implement** `tools/p0b/harness.py` (SPDX header; `tools/` put on `sys.path` at the top) and the fake worker's empty dump as the Interfaces say.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat(tools): the P0-B harness — B1–B6 through the product, the empty-box A/B fit, the K_MAX sweep, the common-cut reach and the pre-registered rules (D-30, D-32..D-40; controller recommendation, owner unavailable)`

---

### Task 10 [code]: The EMerge cross-check harness (`tools/p0b/emerge_app.py`, `emerge_fem.py`) (D-41..D-44)

**Files:**
- Create: `tools/p0b/emerge_app.py`, `tools/p0b/emerge_fem.py`, `tools/p0b/requirements.txt`, `tests/test_emerge_app.py`

**Interfaces:**
- Consumes: `p0.*` (`closed_chain`, `run_model`, `model_of`, `step`, `enter`, `save`, `records`); `p0a.coupon_model`, `references`, `BOX_REF`; `harness.project`, `harness.write`; `pipeline.load`, `build_model`; `geom.rods`; `cross_section`; `terminate`, `z_part`; `checks.compare`; `spec_hash`; `runs.free_ram_mb`; `waves.layout`. r6's scripts in `.superpowers/sdd/plan5-research/r6-emerge/scripts/` (`lpf_spec.py` for the export, `em_coupon.py` and `em_lpf.py` for the FEM side, `compare_chain.py` for the recombination) are the measured reference.
- Produces:
  - `emerge_app.freqs(f0: float, f2: float) -> np.ndarray`: f0·j/8 for j = 4…26, then f2: 24 points (D-43).
  - `emerge_app.NPORT_FREE_MB = 22000` (r6: the 60 µm level peaks near 20 GB on this 31 GB PC).
  - `emerge_app.export(pj: Path, out: Path) -> dict`: writes and returns `<out>/emerge/input.json` (D-42, r6 §4):
    - `"coupons"`: for coupon_ms and coupon_gcpw, `{"cs": dataclasses.asdict of the section's cross-section, mode "none", in the BOX_REF (45 h) box, so EMerge's coupon and its 45 h reference share the box, "z0_ref": KiCad, "eeff_ref": the 45 h 2D εeff}` (from `p0a.coupon_model(name, 2)` and `p0a.references`);
    - `"lpf915"`: `{"spec": the project's model spec (when the project has results, its hash must equal theirs, else SystemExit), "labels": [{"net", "layer"}] per copper solid in spec order ("copper_part" for the 0R hulls), "chain_nets", "rods": [{"at", "radius", "z0", "z1"}] (every via, solid or not), "mask_clean": the mask materials opened by 5 µm (`buffer(-0.005).buffer(0.005)`, mitre joins) without slivers under 1e-6 mm², "faces": [per spec port in job order: {"name", "p" (0 along x, 1 along y), "z" (mid-copper), "gap_x", "gap_y" (the gap polygon between the model's own signal and reference copper within the port box's span across), "h_eff" (the harmonic mean of the gap over 21 cuts across the span), "line": [g0, g1, t] (the midline from the signal copper's edge to the reference copper's), "sign" (+1 when the reference lies at higher p), "lo", "hi"}], "freqs": freqs(f0, f2), "f0"}`.
  - `emerge_app.verdict(cmp: dict | None, coupons: list[dict], move: float | None, sigma: float | None, recip: float | None, unsolved: list[str] = ()) -> tuple[str, list[str]]` (D-43): the reasons, each a failed EMerge precondition: `f"EMerge {level} not solved"` per unsolved level (a missing or failed FEM output), `f"{name} z0 {dz0:.2f} %"` (|dz0_pct| > 5 against KiCad), `f"{name} eeff {deeff:.2f} %"` (> 3 against the 45 h 2D value), `f"chain moved {move:.4f} from 75 to 60 um"` (> 0.01), `f"sigma_max {sigma:.4f}"` (> 1.01), `f"reciprocity {recip:.4f}"` (> 0.01). Any reason → `"inconclusive"`; else `"pass"` when cmp's ds_max ≤ `p0.LIMITS1["ds_max"]` and ds21_db_f0 ≤ `p0.LIMITS1["ds21_db_f0"]`, else `"fail"`.
  - `emerge_app.fem(out: Path, mode: str, *args: str) -> dict`, a step's work: for `nport`, SystemExit (no record, rerun later) when `runs.free_ram_mb()` < NPORT_FREE_MB, saying to close other programs; then `<out>/emerge/venv` Python `-I tools/p0b/emerge_fem.py mode *args` with the working folder `<out>/emerge` and `TEMP`/`TMP` under it, waited for; returns `{"exit", "output": its output file's name}` (stderr's tail stays in the step record only).
  - `emerge_app.cross_check(out: Path) -> dict`: openEMS at EMerge's frequencies, `p0.closed_chain(B1, f=freqs, ideal=True)` (Z_ideal ∥ C_box, as retune closes it); EMerge's 60 µm 6-port, the finer level, closed by Z_ideal alone through `terminate` (and with C_box, as a sensitivity); `compare(a=EMerge's chain, b=openEMS's chain, f, k0, 0.02)`; `move` = max |chain(60) − chain(75)|; σ_max and reciprocity the larger of both levels'; the coupon rows from `coupon_*-50.json` against input.json's references; writes `<out>/p0b/emerge.json`: `{"coupons": [{"name", "edge_um", "z0", "z0_ref", "dz0_pct", "eeff", "eeff_ref", "deeff_pct"}], "nport": {"75": {...}, "60": {...}} (nodes, tets, t_s, peak_gb, sigma_max, recip), "move", "compare", "compare_75", "compare_cbox", "compare_n3" (B5's chain against EMerge's, D-36), "verdict", "reasons", "freeze" (the validation venv's `freeze.txt` lines)}`.
  - `emerge_app.nomask(out: Path) -> None`: the no-mask diagnostic pair (D-43), only after a `"fail"`: step `p0b-emerge-nport-75-nomask` (`fem(..., "--mask", "none")`) and step `p0b-emerge-nomask-openems` (B1's spec without its `mask_*` materials, `p0.run_model(..., "normal", step id, [1, …, 6])`, key its spec_hash plus B1's run_dir); `cross_check` then adds `"compare_nomask"`, closing the no-mask openEMS run by the C_box of its own setup.json.
  - `emerge_app.main(argv)`: `python tools/p0b/emerge_app.py run --out DIR`, one background command: `p0.enter(out)`; the validation venv made once by `uv venv --python 3.13 <out>/emerge/venv` and filled by `uv pip install --python <venv python> -r tools/p0b/requirements.txt`, both with an explicit environment (`UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` under `<out>/emerge`, `UV_PYTHON_PREFERENCE=only-managed`, `UV_NO_CONFIG=1`); `uv pip freeze` into `<out>/emerge/freeze.txt`; `export(B1, out)`; the FEM steps `p0b-emerge-coupon-coupon_ms-50`, `-coupon-coupon_gcpw-50`, `-nport-75`, `-nport-60` (key: input.json's sha256 plus the step's arguments); `cross_check`; `nomask` and `cross_check` again when the verdict is `"fail"`; then `harness.write(out)`.
  - `tools/p0b/emerge_fem.py` (validation venv only; numpy, emerge, psutil; no `kicad_rf_studio`, no `p0`; stdout and stderr reconfigured to UTF-8; `MKL_NUM_THREADS` defaulted to 8 before importing emerge), r6's em_coupon.py and em_lpf.py ported:
    - `coupon --input FILE --name NAME --edge-um UM --out FILE.json`: the coupon's cross-section extruded 4 mm (r6 §5.1's measured length) in its closed PEC box, grounds run out to the box walls, 35 µm solid copper, a TEM `ModalPort` on each end face with its voltage line from the ground's top to the strip's bottom, frequencies 0.4575 and 0.915 GHz, `run_sweep(parallel=False, frequency_groups=1)`; `{"name", "edge_um", "z0", "eeff", "freq_hz", "nodes", "tets", "t_s", "peak_gb", "emerge"}`, Z0 and εeff read at 0.4575 GHz.
    - `nport --input FILE --edge-um UM [--mask clean|none] --out FILE.npz`: an air box over the spec's mesh bounds with an order-2 `AbsorbingBoundary` on its outside; the spec's dielectrics at their priorities as `Material(er=eps, cond=kappa)` (the masks from `mask_clean`, or none); every copper solid a 35 µm PEC prism (priority 1000, `set_pec_domain`); every via an 8-sided PEC cylinder (`compensate_radius=True`); the lid plate a 50 µm PEC slab at its snapped z, and its walls; `gmsh.model.occ.remove_all_duplicates` replaced by a no-op before `commit_geometry`; `set_boundary_size` of the chain-net copper at `UM` µm, growth 2, resolution 0.33; one 50 Ω `LumpedPort` per face (width hi − lo, height h_eff, direction ±p, its midline as the voltage line); `mw_cap_sp_single = mw_cap_sp_col = size_check = False`; `run_sweep(parallel=False, frequency_groups=1)` at `freqs`; writes `f`, `s`, `names` to the npz and `{"nodes", "tets", "t_s", "peak_gb", "sigma_max", "recip", "emerge"}` beside it as `FILE.json`. These are D-42's workarounds, "the same layout" (Rec).
  - `tools/p0b/requirements.txt` (SPDX comment line first): `emerge==3.0.0b3`, `emsutil==1.1.4`, `gmsh==4.15.2`, `numpy==2.2.6`, `scipy==1.18.1`, `mkl==2026.2.0`, `pyvista==0.49.1`, `vtk==9.7.1` (r6's resolution on this PC; D-41, Rec). The run records the whole environment's freeze.

- [ ] **Step 1: Write the failing tests** in `tests/test_emerge_app.py`:

```python
def test_the_frequencies_hold_f0_its_harmonics_and_f2():  # D-43
    f = emerge_app.freqs(915e6, 3.0195e9)
    assert len(f) == 24 and {915e6, 1830e6, 2745e6} <= set(f.tolist()) and (f[0], f[-1]) == (457.5e6, 3.0195e9)


def test_the_export_cuts_each_port_face_from_the_models_own_copper(p0_out, monkeypatch):  # D-42; r6 §4.3
    monkeypatch.setattr(p0, "cli", in_process)
    data = emerge_app.export(harness.project(p0_out, "B1"), p0_out)
    lpf = data["lpf915"]
    assert [fc["name"] for fc in lpf["faces"]] == ["P1", "P2", "C1", "L1", "C2", "C3"]
    assert [("xy"[fc["p"]], fc["sign"]) for fc in lpf["faces"]] == [
        ("y", 1.0), ("y", 1.0), ("x", 1.0), ("x", 1.0), ("y", -1.0), ("y", -1.0)]
    assert lpf["faces"][0]["line"][1] == pytest.approx(-99.7218, abs=1e-3)  # P1's reference: the GND pour's edge
    assert len(lpf["labels"]) == len(lpf["spec"]["metal"]["copper"]) and len(lpf["rods"]) == 36
    assert set(data["coupons"]) == {"coupon_ms", "coupon_gcpw"} and (p0_out / "emerge" / "input.json").is_file()


def test_the_emerge_verdict_follows_d43():  # D-43, D-44
    ok = {"ds21_db_f0": 0.05, "ds11_f0": 0.01, "ds_max": 0.02, "nulls": []}
    coupons = [{"name": "coupon_ms", "dz0_pct": -1.08, "deeff_pct": 0.14},
               {"name": "coupon_gcpw", "dz0_pct": -4.03, "deeff_pct": 0.40}]  # r6 at 50 µm
    assert emerge_app.verdict(ok, coupons, 0.004, 1.0018, 0.008) == ("pass", [])
    assert emerge_app.verdict({**ok, "ds_max": 0.031}, coupons, 0.004, 1.0018, 0.008) == ("fail", [])
    miss = [coupons[0], {**coupons[1], "dz0_pct": -5.2}]
    assert emerge_app.verdict(ok, miss, 0.004, 1.0018, 0.008) == ("inconclusive", ["coupon_gcpw z0 -5.20 %"])
    assert emerge_app.verdict(ok, coupons, 0.012, 1.0018, 0.008) == ("inconclusive",
                                                                     ["chain moved 0.0120 from 75 to 60 um"])
    assert emerge_app.verdict(None, coupons, None, 1.0018, 0.008, ["60 um"]) == ("inconclusive",
                                                                                 ["EMerge 60 um not solved"])


def test_an_nport_solve_waits_for_free_ram(tmp_path, monkeypatch):  # r6 §6: the 60 µm level peaks near 20 GB
    monkeypatch.setattr(runs, "free_ram_mb", lambda: 15000.0)
    with pytest.raises(SystemExit):
        emerge_app.fem(tmp_path, "nport", "--edge-um", "60")


def test_the_fem_script_compiles_and_never_imports_the_app():  # D-41, D-55
    text = (p0.ROOT / "tools" / "p0b" / "emerge_fem.py").read_text(encoding="utf-8")
    compile(text, "emerge_fem.py", "exec")
    assert "kicad_rf_studio" not in text and "import p0" not in text
    requirements = (p0.ROOT / "tools" / "p0b" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert requirements[0] == "# SPDX-License-Identifier: GPL-3.0-or-later" and "emerge==3.0.0b3" in requirements


def test_the_cross_check_closes_both_sides_as_d43_says(p0_out, monkeypatch):  # D-43: the plumbing, on the fake
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    assert harness.main(["--out", str(p0_out), "--only", "B1"]) == 0
    pj = harness.project(p0_out, "B1")
    data, e = emerge_app.export(pj, p0_out), p0_out / "emerge"
    project = load_project(pj)
    f = np.array(data["lpf915"]["freqs"])
    s = layout(project, project["results"], f=f).s  # EMerge as openEMS's own layout N-port
    for um in (75, 60):
        np.savez(e / f"lpf915-{um}.npz", f=f, s=s, names=np.array(["P1", "P2", "C1", "L1", "C2", "C3"]))
        p0.save(e / f"lpf915-{um}.json", {"sigma_max": 1.0, "recip": 0.0, "nodes": 1, "tets": 1, "t_s": 1.0,
                                          "peak_gb": 1.0, "emerge": "3.0.0b3"})
    for name, ref in data["coupons"].items():
        p0.save(e / f"{name}-50.json", {"name": name, "edge_um": 50, "z0": ref["z0_ref"], "eeff": ref["eeff_ref"]})
    (e / "freeze.txt").write_text("emerge==3.0.0b3\n", encoding="utf-8")
    out = emerge_app.cross_check(p0_out)
    assert out["compare_cbox"]["ds_max"] <= 1e-9 and out["reasons"] == [] and out["move"] == 0
    assert (p0_out / "p0b" / "emerge.json").is_file()
```

  Test imports: `numpy as np`, `pytest`; `import p0`; `from kicad_rf_studio import runs`; `load_project`; `layout`; `from p0b import emerge_app, harness`; `from test_p0 import in_process`.
- [ ] **Step 2: Run** `python -m pytest tests/test_emerge_app.py -q`. Expected: FAIL (no module `p0b.emerge_app`).
- [ ] **Step 3: Implement** the three files as the Interfaces say. `emerge_fem.py` is never run in this task (no EMerge in the dev venv).
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat(tools): the EMerge cross-check — one-command run with resumable FEM steps, export and cross-check in the app venv, the FEM scripts and their pinned requirements (D-41..D-44; controller recommendation, owner unavailable)`

---

### Task 11 [code]: The P0-C tool (`tools/p0c.py`) (D-46)

**Files:**
- Create: `tools/p0c.py`, `tests/test_p0c.py`

**Interfaces:**
- Consumes: `p0.*`; Task 6's `choose_reference(rank=1)`; `cli._reference` (stores a Reference as `new` does); Task 3's `region.margin_scale`; `stop_rule`, `PRESETS`; `waves.grid`, `layout(f=)`; `chain.part_impedances`, `loads`; `sigma_max`, `recip_err`, `loss_budget`; `runs.free_ram_mb`.
- Produces:
  - `p0c.STEPS = ("C0", "C1", "C2", "C3", "C4a", "C4b", "C5", "C6", "S2P")`; `p0c.PUBLIC`, the allowlist below.
  - `main(argv=None) -> int`: `python tools/p0c.py --board PATH --start REF.PAD --end REF.PAD --f0 F [--harmonics N] [--lid-height MM] [--stackup NAME] --out DIR [--preset draft|normal|strict] [--steps C0,C1,…] [--s2p DIR]`.
    - Exit 2 with one line, nothing written, when `--out` or `--board` lies inside a git work tree (`p0.inside_git`) or `--board` is not a file.
    - `p0.enter(out)`; the board copied to `OUT/board/<its name>`, the original never touched; every CLI child through `p0.cli`, so `LOCALAPPDATA` is `OUT/data`.
    - The base project `OUT/projects/base/project.json` by `new` with the given options. A variant that runs is a copy of base without results in `OUT/projects/<step>/`; a variant that needs C1's results (C2, S2P) is a copy of C1's project with them, which `results_of` accepts, because the preset is not in the spec hash. Every step resumable (`p0.step`); the step stores the raw outputs (exit codes, run-folder names); the criteria are computed when the report is written.
    - | Step | What | Key | Computes |
      |---|---|---|---|
      | C0 | `cost` on base | base's model key | cells, smallest cell, dt and its node, worst-case and predicted times (I_COST_* events) |
      | C1 | base with `"preset"` = `--preset` (default strict), `run`; RAM sampled every 5 s by a thread meanwhile | base's model key + the preset | each job replayed at every preset up to it (`p0.s_of`, causal): stop times per preset; S per preset against the run's own (max \|ΔS\|); the 6-run wall time per preset from the I_PROGRESS times (`# ponytail: a round model: each round of pool jobs starts when its slowest job would have stopped`); per-job speeds; RAM in use, from `runs.free_ram_mb()` (start minus the lowest, per job and per Mcell; `# ponytail: system-wide free RAM`) |
      | C2 | C1's project copied with its results, `"preset"` normal, `verify` | C1's run folder | criterion 1: `p0.criterion1(verify.compare)` |
      | C3 | both ports' references → `choose_reference(…, rank=1)`, `run` at normal | the variant's model key | criterion 3: \|ΔS21(f0)\| in dB against the base at Normal ≤ 0.2 |
      | C4a | `mesh.n` 3, `run` at normal; after an exit 3 naming E_FIT2D_FINE, `gates.fit2d_limit` 0.05 and `run` again (W_GATE_LIMITS recorded) | likewise | criterion 4, n |
      | C4b | `region.margin_scale` 2.0, `run` at normal | likewise | criterion 4, margin |
      | C5 | `"lid": false`, `run` at normal | likewise | lid on and off: max \|ΔS\| at f0, 2f0, 3f0 |
      | C6 | `band_factor` 1.25, `run` at normal | likewise | its chain at the 1.1 grid's points (`p0.closed_chain(pj, f=…)`): max \|ΔS\| at f0, 2f0, 3f0; its cost |
      | S2P | with `--s2p DIR`: each `<REF>.series.s2p` or `<REF>.shunt.s2p`, `retune` on a copy of C1's project with its results | C1's run folder + the files' sha256 | the chain's change from the presets, per file (the owner's own preset check) |
    - The base at Normal: C1's records replayed at Normal, cut, reduced and closed as `run` closes them (`waves.layout` with the Normal cuts, `chain.loads` of `part_impedances`). Criterion 2 on that layout: `sigma_max ≤ 1.02`, `recip_err ≤ 0.02`, `loss_budget(…)[k0] − loss_expected ≤ 0.02` (spec L586). Criterion 4: both C4a and C4b within 0.1 dB of the base at f0. A variant whose command exits non-zero records its exit and codes, and its criterion reads None (not measured, so not passed).
    - Verdict (spec L599): `{"pass": c1 and c2 and c4, "refine_mesh": not c4, "fallback": not (c1 and c2), "prominent_reference": not c3}`.
    - Writes `OUT/report/p0c.json` and `p0c.md` (private: refs, nets, values, coordinates) and `OUT/report/p0c-public.json`: only PUBLIC's keys — `{"criteria": {"c1": {"ds21_db_f0", "ds11_f0", "ds_max", "pass"}, "c2": {"sigma_max", "recip", "loss_excess", "pass"}, "c3": {"ds21_db", "pass"}, "c4": {"n3_ds21_db", "margin_ds21_db", "pass"}}, "verdict": {"pass", "refine_mesh", "fallback", "prominent_reference"}, "measured": {"mcells", "dt", "stop_ns": {preset: [per job]}, "wall_s": {preset}, "speeds_mcs", "ram_mb_per_mcell", "lid_ds": {"f0", "2f0", "3f0"}, "band_ds": {…}, "s2p_ds_max"}, "machine": {"machine_hours", "elapsed_days", "loaded_steps"}}` — every leaf a number, a bool or null: no name, ref, net, value, coordinate, hash or path.

- [ ] **Step 1: Write the failing tests** in `tests/test_p0c.py`:

```python
ARGS = ["--start", "U1.1", "--end", "J1.1", "--f0", "915MHz"]


def test_p0c_refuses_paths_inside_a_git_work_tree(tmp_path):  # D-46; Review Focus 4
    board = tmp_path / "b.kicad_pcb"
    board.write_bytes((p0.FIX / "lpf915.kicad_pcb").read_bytes())
    for b, out in ((p0.FIX / "lpf915.kicad_pcb", tmp_path / "out"), (board, p0.ROOT / "build" / "p0c"),
                   (board, p0.ROOT / "not-yet" / "deeper")):
        assert p0c.main(["--board", str(b), "--out", str(out), *ARGS]) == 2
    assert not any(p.exists() for p in (tmp_path / "out", p0.ROOT / "build" / "p0c", p0.ROOT / "not-yet"))


def test_p0c_on_lpf915_with_the_fake_worker(tmp_path, p0_out, monkeypatch):  # D-46; Review Focus 4
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)  # verify's L cell: the fake's dump is empty
    board = tmp_path / "placa ação" / "lpf915.kicad_pcb"
    board.parent.mkdir()
    board.write_bytes((p0.FIX / "lpf915.kicad_pcb").read_bytes())
    s2p = tmp_path / "s2p"
    s2p.mkdir()
    write_s2p(s2p / "C2.shunt.s2p", 1 / (2j * np.pi * F * 3.3e-12), "shunt", F)
    assert p0c.main(["--board", str(board), *ARGS, "--lid-height", "2.5", "--out", str(p0_out), "--preset", "normal",
                     "--steps", "C0,C1,C2,C3,C4a,C4b,C5,C6,S2P", "--s2p", str(s2p)]) == 0
    private = json.loads((p0_out / "report" / "p0c.json").read_text(encoding="utf-8"))
    public = json.loads((p0_out / "report" / "p0c-public.json").read_text(encoding="utf-8"))
    assert set(private["criteria"]) == {"c1", "c2", "c3", "c4"} and (p0_out / "board" / "lpf915.kicad_pcb").is_file()
    assert "compare" in load_project(p0_out / "projects" / "C2" / "project.json")["verify"]

    def leaves(x):
        items = x.values() if isinstance(x, dict) else x if isinstance(x, list) else None
        return [x] if items is None else [v for y in items for v in leaves(y)]

    assert all(v is None or isinstance(v, (bool, int, float)) for v in leaves(public))
    measured = [public["criteria"][c][k] for c, k in (("c1", "ds21_db_f0"), ("c1", "ds_max"), ("c2", "sigma_max"),
                                                      ("c3", "ds21_db"), ("c4", "n3_ds21_db"), ("c4", "margin_ds21_db"))]
    measured += [public["measured"]["lid_ds"]["f0"], public["measured"]["band_ds"]["f0"], public["measured"]["s2p_ds_max"]]
    assert all(isinstance(v, float) for v in measured)  # every step ran and was measured, none read None
    c = {k: bool(v["pass"]) for k, v in public["criteria"].items()}
    assert public["verdict"] == {"pass": c["c1"] and c["c2"] and c["c4"], "refine_mesh": not c["c4"],
                                 "fallback": not (c["c1"] and c["c2"]), "prominent_reference": not c["c3"]}
```

  Test imports: `json`, `numpy as np`; `import p0, p0c`; `load_project`; `grid` (`F, _ = grid(915e6, 3, 1.1)`); `from networks import write_s2p`; `from kicad_rf_studio.core.model import spec as spec_module`; `from test_p0 import in_process`.
- [ ] **Step 2: Run** `python -m pytest tests/test_p0c.py -q`. Expected: FAIL (no module `p0c`).
- [ ] **Step 3: Implement** `tools/p0c.py` as the Interfaces say.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat(tools): the P0-C tool — variants C0–C6 and S2P, criteria 1–4 from the run folders, private and public reports, refusals inside a work tree (D-46)`

---

### Task 12 [code]: P0-D and CI tier (b) — `tools/p0d.py` and `.github/workflows/linux-openems.yml` (D-47, D-48)

**Files:**
- Create: `tools/p0d.py`, `.github/workflows/linux-openems.yml`, `tests/test_p0d.py`

**Interfaces:**
- Consumes: `p0.*` (`s_of`, `run_model`, `model_of`, `enter`, `edit`, `records`, `save_trace`, `run_path`, `criterion1`); `p0a.COUPONS`, `coupon_model`, `line_constants`; `stoprule.PRESETS`; `grid`; `compare`; `pipeline.load`, `build_model`, `records`; `main` (for `new`).
- Produces:
  - `p0d.MODELS = (*p0a.COUPONS, "coupon_gcpw_pads", "lpf915")`, `PADS = {"coupon_gcpw_pads": ("TP1.1", "TP2.1", ()), "lpf915": ("U1.1", "J1.1", ("--lid-height", "2.5"))}`, `PIN = {"mesh.reach_h": 3.0}` (the P0 runs' reach, so a later default from D-37 cannot change the models CI builds), `FLOOR = 10 * PRESETS["draft"][1]` (the null floor, as verify derives it), `ZE_LIMIT_PCT = 0.5` (Linux's Z0 and εeff against the Windows reference: both sides run one model at one stop level, which r7 expects to agree to well under 0.1 %).
  - `judge(ref: dict, s: np.ndarray, spec_hash: str) -> dict`: `{"compare": compare(a=ref["S"], b=s, ref["f"], 71, FLOOR), "criterion1": p0.criterion1(that), "spec_hash_equal": bool}` (a mismatch is reported, never fatal).
  - `models(out: Path, only: list[str] | None = None) -> list[dict]`: `out/<model>.json`, the model spec — a coupon: `p0a.coupon_model(name, 2, edits=PIN)`; the pad coupon and lpf915: `new` in-process into `out/<model>/`, `p0.edit(project, PIN)` saved, then `pipeline.load` and `build_model` — and `out/matrix.json` = the returned `[{"model", "port"}]`: port 1 for a coupon, 1–2 and 1–6 otherwise.
  - `excite(spec_path: Path, port: int, out: Path) -> dict`: `p0.enter(out)`, then `p0.run_model(p0.model_of(spec), "draft", f"{model}-k{port}", [port])`, also written as `out/result.json`.
  - `references(p0_dir: Path, out: Path, models: tuple[str, ...] = MODELS) -> list[Path]` (D-48): `p0.enter(p0_dir)` first (never `enter(out)`: `out` is `tests/fixtures/p0d`, inside the work tree); from the records of `p0a-<coupon>-n2`, `p0a-pad` and `p0b-B1`: each job's records (`pipeline.records`), `p0.s_of(…, the co-sim grid, "draft")`, written as `out/<model>.npz` with members `f`, `S`, `t_cut`, `spec_hash` and, for a coupon, `z0` (Re Z0) and `eeff` (points × f, `p0a.line_constants` at the Draft cut). By causality the Draft replay of a Normal record is exact.
  - `traces(p0_dir: Path, out: Path) -> list[Path]` (D-40): `p0.enter(p0_dir)` first; `p0.save_trace` of B1's six jobs and the pad coupon's two as `out/lpf915-k<1..6>.npz` and `out/coupon_gcpw_pads-k<1,2>.npz`; SystemExit naming a job whose live verdict is not `converged` (D-40's fixtures are the live converged branch), before any file is written.
  - `compare_runs(runs: Path, refs: Path, models_dir: Path) -> dict`: per reference, the Linux records from each `runs/<model>-k<port>/` (`result.json` and its job folder), `p0.s_of(…, "draft")` and `judge`; a model with a missing excitation fails, named; coupons also give max |ΔZ0| and |Δεeff| in % against the reference (the probes from `models_dir/<model>.json`), each within ZE_LIMIT_PCT; `{"models": {model: judge + {"dz0_pct", "deeff_pct", "pass"}}, "pass": bool}`. This is tier (b)'s permanent trace-impedance regression test (spec L541).
  - `main(argv)`: `python tools/p0d.py models --out DIR [--only M,…]` · `excite --spec FILE --port K --out DIR` · `compare --runs DIR --refs DIR --models DIR --out FILE` (exit 1 when a model fails) · `references --p0 DIR --out DIR` · `traces --p0 DIR --out DIR`.
  - `.github/workflows/linux-openems.yml`: first line the SPDX header; `permissions: contents: read`; `on:` a `schedule` (`cron: "17 3 * * *"`, tier b) and `workflow_dispatch` (P0-D). Three step groups recur in every job that needs openEMS, because each job is a fresh container: "base packages" (git, sudo, python3, python3-venv or its pip, through `apt-get` or `dnf`), "openEMS dependencies" (`git clone --depth 1 --branch v0.37.0` of upstream's openEMS-Project into `/tmp/oe`, then `./scripts/install_deps.sh --auto --python` there: the shared libraries openEMS and CSXCAD link against live in the container, not in the cache) and "cache key" (`py=<the system Python's major.minor>` into `$GITHUB_OUTPUT`, computed after python3 is installed). Jobs:
    - `models` (runs-on ubuntu-24.04, setup-python 3.12, `pip install -e .`, `python tools/p0d.py models --out models`, uploads `models`; outputs `entries` (matrix.json) and `distros`: `[{"image": "ubuntu:24.04", "slug": "ubuntu2404"}]` on a schedule, else that plus `{"image": "debian:12", "slug": "debian12"}` and `{"image": "fedora:44", "slug": "fedora44"}`); `timeout-minutes: 30`.
    - `build` (needs models; matrix `distro: ${{ fromJSON(needs.models.outputs.distros) }}`; container `matrix.distro.image`; the three groups; `actions/cache@v4` on `/opt/openEMS` and `/opt/krs`, key `openems-v0.37.0-${{ matrix.distro.slug }}-py${{ steps.key.outputs.py }}`; on a miss: `git -C /tmp/oe submodule update --init --recursive --depth 1`, `python3 -m venv /opt/krs`, then `. /opt/krs/bin/activate && pip install -e . && cd /tmp/oe && ./update_openEMS.sh /opt/openEMS --python` (the GUI build on); always the probe `. /opt/krs/bin/activate && python -c "import openEMS, CSXCAD, importlib.metadata as m; v = m.version('openEMS'); print(v); assert v.startswith('0.37.'), v"`, which fails the job loudly); `timeout-minutes: 350`.
    - `excite` (needs [models, build]; matrix `distro` × `entry: ${{ fromJSON(needs.models.outputs.entries) }}`, `fail-fast: false`; the same container and three groups; `actions/cache/restore@v4` with the same key and `fail-on-cache-miss: true`; downloads `models`; `. /opt/krs/bin/activate && pip install -e . && python tools/p0d.py excite --spec models/<model>.json --port <port> --out "$RUNNER_TEMP/runs/<model>-k<port>"` (outside the checkout, which `p0.enter` would refuse); uploads `runs-<slug>-<model>-k<port>`); `timeout-minutes: 350`.
    - `compare` (needs [models, excite]; `if: always()`, so a failed excitation is reported; matrix `distro`; ubuntu-24.04, setup-python 3.12, `pip install -e .`; downloads `models` and `runs-<slug>-*` merged into `runs/`; `python tools/p0d.py compare --runs runs --refs tests/fixtures/p0d --models models --out compare-<slug>.json`, uploaded); `timeout-minutes: 30`.
    - `openems-tests` (`if: github.event_name == 'schedule'`; `needs: build`; container `ubuntu:24.04`; the three groups; `actions/cache/restore@v4` with the ubuntu2404 key and `fail-on-cache-miss: true`; `. /opt/krs/bin/activate && pip install -e ".[dev]" && python -m pytest -m openems -q`); `timeout-minutes: 120`.

- [ ] **Step 1: Write the failing tests** in `tests/test_p0d.py`:

```python
F, _ = grid(915e6, 3, 1.1)


def test_judge_applies_criterion_1_against_the_windows_reference():  # D-47, D-48
    ref = {"f": F, "S": star(F, 6), "t_cut": np.full(6, 4e-9), "spec_hash": np.array("abc")}
    same = p0d.judge(ref, star(F, 6), "abc")
    assert same["criterion1"]["pass"] and same["spec_hash_equal"]
    bent = star(F, 6).copy()
    bent[100, 2, 3] += 0.05
    assert p0d.judge(ref, bent, "abd")["criterion1"]["ds_max"] is False


def test_models_writes_each_spec_and_the_matrix(tmp_path):  # D-47
    assert p0d.models(tmp_path, ["coupon_ms", "coupon_gcpw_pads"]) == [
        {"model": "coupon_ms", "port": 1}, {"model": "coupon_gcpw_pads", "port": 1}, {"model": "coupon_gcpw_pads", "port": 2}]
    assert json.loads((tmp_path / "coupon_ms.json").read_text(encoding="utf-8"))["probes"]
    assert load_project(tmp_path / "coupon_gcpw_pads" / "project.json")["mesh"]["reach_h"] == 3.0  # PIN


def test_excite_runs_one_port_at_draft_and_compare_judges_it(p0_out, tmp_path):  # D-47: one job per excitation
    spec = tmp_path / "two.json"
    spec.write_text(json.dumps(TWO), encoding="utf-8")
    run = p0d.excite(spec, 1, p0_out)
    assert [j["port"] for j in run["jobs"]] == ["P1"] and (p0_out / "result.json").is_file()
    job = p0.run_path(run["run_dir"]) / run["jobs"][0]["job"]
    s, cuts = p0.s_of([(records(job, 2, run["setup"]["dt"]), 0, TWO["excitation"], None)], F, "draft")
    refs, runs_dir = tmp_path / "refs", tmp_path / "runs"
    refs.mkdir()
    np.savez(refs / "two.npz", f=F, S=s, t_cut=cuts, spec_hash=np.array(spec_hash(TWO)))
    shutil.copytree(p0_out, runs_dir / "two-k1")
    assert p0d.compare_runs(runs_dir, refs, tmp_path)["pass"]
    np.savez(refs / "two.npz", f=F, S=s + 0.05, t_cut=cuts, spec_hash=np.array(spec_hash(TWO)))
    assert not p0d.compare_runs(runs_dir, refs, tmp_path)["pass"]


def test_references_and_traces_come_from_a_p0_folder(p0_out, tmp_path, monkeypatch):  # D-40, D-48
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    assert p0a.main(["--out", str(p0_out), "--only", "p0a-pad"]) == 0
    assert harness.main(["--out", str(p0_out), "--only", "B1"]) == 0
    refs = p0d.references(p0_out, tmp_path / "refs", models=("coupon_gcpw_pads", "lpf915"))
    assert [p.name for p in refs] == ["coupon_gcpw_pads.npz", "lpf915.npz"]
    with np.load(refs[1]) as z:
        assert set(z.files) == {"f", "S", "t_cut", "spec_hash"} and z["S"].shape == (len(F), 6, 6)
    traces = p0d.traces(p0_out, tmp_path / "traces")
    assert sorted(p.name for p in traces)[:3] == ["coupon_gcpw_pads-k1.npz", "coupon_gcpw_pads-k2.npz", "lpf915-k1.npz"]
    assert p0.load_trace(traces[0])[1] in (0, 1)


@pytest.mark.parametrize(("run", "argv", "folder"), [
    ("p0a", ["--out", "{p0}"], "p0"), ("harness", ["--out", "{p0}"], "p0"), ("emerge_app", ["run", "--out", "{p0}"], "p0"),
    ("p0c", ["--board", "{board}", "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "--out", "{p0}"], "p0"),
    ("p0d", ["references", "--p0", "{p0}", "--out", "{out}"], "p0"), ("p0d", ["traces", "--p0", "{p0}", "--out", "{out}"], "p0"),
    ("p0d", ["excite", "--spec", "{board}", "--port", "1", "--out", "{out}"], "out")])
def test_every_tool_enters_its_p0_folder_first(tmp_path, monkeypatch, run, argv, folder):  # D-7, D-46
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes((p0.FIX / "lpf915.kicad_pcb").read_bytes())
    seen = []

    def enter(out):
        seen.append(Path(out))
        raise RuntimeError("entered")

    monkeypatch.setattr(p0, "enter", enter)
    monkeypatch.setattr(runs, "data_dir", lambda: pytest.fail("runs used before p0.enter"))
    paths = {"p0": tmp_path / "p0", "out": tmp_path / "out", "board": board}
    main = {"p0a": p0a.main, "harness": harness.main, "emerge_app": emerge_app.main, "p0c": p0c.main,
            "p0d": p0d.main}[run]
    with pytest.raises(RuntimeError):
        main([a.format(**paths) for a in argv])
    assert seen == [paths[folder]]


def test_the_linux_workflow_is_prepared():  # D-47
    text = (p0.ROOT / ".github" / "workflows" / "linux-openems.yml").read_text(encoding="utf-8")
    assert text.splitlines()[0] == "# SPDX-License-Identifier: GPL-3.0-or-later"
    assert "\npermissions:\n  contents: read\n" in text
    for needle in ("schedule:", "workflow_dispatch:", "debian:12", "ubuntu:24.04", "fedora:44", "--branch v0.37.0",
                   "install_deps.sh --auto --python", "update_openEMS.sh /opt/openEMS --python", "startswith('0.37.')",
                   "import openEMS, CSXCAD", "fail-on-cache-miss: true", "if: always()", 'pip install -e ".[dev]"',
                   "tools/p0d.py excite", "tools/p0d.py compare", "pytest -m openems"):
        assert needle in text, needle
    assert "needs: build" in text.split("openems-tests:")[1]
    assert max(int(m) for m in re.findall(r"timeout-minutes: (\d+)", text)) <= 350
```

  Test imports: `json`, `re`, `shutil`, `Path`, `numpy as np`, `pytest`; `import p0, p0a, p0c, p0d`; `from p0b import emerge_app, harness`; `from kicad_rf_studio import runs`; `load_project`; `records` from `pipeline`; `spec_hash`; `grid`; `from networks import star`; `from test_p0 import TWO, in_process`.
- [ ] **Step 2: Run** `python -m pytest tests/test_p0d.py -q`. Expected: FAIL (no module `p0d`, no workflow).
- [ ] **Step 3: Implement** `tools/p0d.py` and the workflow as the Interfaces say.
- [ ] **Step 4: Run** the full suite. Expected: all pass. The workflow is never run here (no remote, no push: spec §12).
- [ ] **Step 5: Commit.** `feat(tools, ci): P0-D and CI tier (b) — the Linux workflow, the pinned models, the reference and trace writers, the compare script with its line-impedance limit (D-47, D-48)`

---

## Phase 2 — gate runs (the controller, background commands, an idle PC; nothing is committed)

### Task 13 [run]: The P0 folder, the calibration and P0-A

- **Before:** Tasks 1–12 committed on the branch; `git status --porcelain` empty; note `git rev-parse --short HEAD`; the date is before 2026-11-19 (D-4), else go to Task 22; no other openEMS, EMerge or pytest process: `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'tools'); import p0; print([sum(m in c for c in p0.command_lines()) for m in p0.MARKERS])"` prints `[0, 0, 0]` (it reads no settings). From here to Task 16's end, `src/` and `tools/` stay frozen but for a fix of a failed step (Global Constraints).
- **Command:** `.venv\Scripts\python.exe tools\p0a.py --out <P0>` (its first step is `calibrate` in `<P0>/data`).
- **Expected machine time:** about 3–4 h idle (r4 §2.7: the seven coupons at n = 2 ≈ 42 min, at n = 3 ≈ 2.0 h; the pad coupon ≈ 14 min; setups and the stray cell ≈ 10 min). r7's upper figure, if runs go to 10 ns: 9.4 h.
- **Outputs:** `<P0>/data/kicad-rf-studio/settings.json` (calibration with `levels`); `<P0>/steps/p0a-calibrate.json`, `p0a-<coupon>-n2.json` and `-n3.json` (14), `p0a-pad.json`, `p0a-stray.json`; `<P0>/p0a/p0a.json` (Task 8c's keys) and `p0a.md`; `<P0>/p0a/projects/coupon_gcpw_pads/`; run folders in `<P0>/data/kicad-rf-studio/runs/`.
- **Done when:** the harness exits 0 and `.venv\Scripts\python.exe -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print(d['decisions']['verdict'], d['machine']['loaded'])" <P0>\p0a\p0a.json` prints the verdict and the loaded steps; their times stay out of the report's section 6. Exit 1 names the failed steps in the log: fix them by a test-first commit (no run in progress) and run the same command again; finished steps are reused.

### Task 14 [run]: P0-B — B1 to B6 and the K_MAX sweep

- **Before:** as Task 13; Task 13 done.
- **Commands,** one night each:
  1. `.venv\Scripts\python.exe tools\p0b\harness.py --out <P0> --only B1,B2,B3` — about 5–6 h (B1 ≈ 3.0 h at Normal, t_stop ≈ 17 ns; B2 ≈ 1.0 h; B3's four jobs ≈ 1–1.6 h).
  2. `.venv\Scripts\python.exe tools\p0b\harness.py --out <P0> --only B4,B6` — about 6–7 h (B4 ≈ 3.2 h; B6 ≈ 3–4 h).
  3. `.venv\Scripts\python.exe tools\p0b\harness.py --out <P0> --only B5,kmax` — about 10 h (B5 at n = 3 ≈ 7.8 h; the sweep 6 × about 18.5 min ≈ 1.9 h, one 4-thread job at about 450 MC/s, r4 §2.6, D-39's budget 2 h).
- **Expected machine time:** about 22–24 h in all (r4 §2.7, r7 §3.2); worst case to T_max ≈ 43 h.
- **Outputs:** `<P0>/steps/p0b-B1.json`, `p0b-B2.json`, `p0b-B3-A.json`, `p0b-B3-B.json`, `p0b-B4.json`, `p0b-B5.json`, `p0b-B6.json`, `p0b-kmax-0.35.json` … `p0b-kmax-0.55.json`; projects in `<P0>/p0b/projects/B1|B4|B5|B6`; run folders in `<P0>/data/kicad-rf-studio/runs/`; after night 3, `<P0>/p0b/p0b.json` and `p0b.md` with the verdict pending (no emerge.json yet); Task 15 rewrites them.
- **Done when:** night 3 exits 0 and `.venv\Scripts\python.exe -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); print(d['decisions']['verdict']['value'], d['machine']['loaded'], d['evidence']['B1']['ok'])" <P0>\p0b\p0b.json` prints `pending`, the loaded steps (their times stay out of section 6) and B1's evidence.

### Task 15 [run]: The EMerge cross-check

- **Before:** Task 14 done; no openEMS process; the date is before 2026-11-19; at least 22 GB of free RAM (close other programs: the nport steps refuse below it).
- **Command:** `.venv\Scripts\python.exe tools\p0b\emerge_app.py run --out <P0>` — one background command: the validation venv, its freeze, the export, the FEM steps, the cross-check, the no-mask pair only after a `"fail"`, and `p0b.json` rewritten.
- **Expected machine time:** the venv about 1 min (about 430 MB the first time); the coupons about 5–10 min (r6 measured 5–9 GB in the 10 h box; the 45 h box is larger and unmeasured, mostly coarse air); the 75 µm 6-port about 15–17 min at up to 16 GB; the 60 µm about 20 min at about 20 GB (r6 §6); the no-mask pair, if needed, about 3 h (openEMS) plus 6 min.
- **Outputs:** `<P0>/emerge/{venv,freeze.txt,input.json,coupon_ms-50.json,coupon_gcpw-50.json,lpf915-75.npz/.json,lpf915-60.npz/.json}`; `<P0>/steps/p0b-emerge-*.json`; `<P0>/p0b/emerge.json` (Task 10's keys); `<P0>/p0b/p0b.json` and `p0b.md`.
- **Done when:** the command exits 0, `emerge.json` holds a `"verdict"`, and `p0b.json`'s `decisions.verdict.value` is `pass` or `fail`, not `pending`; the loaded FEM steps are listed in its `machine`.

### Task 16 [run]: The P0-C smoke run and the KiCad pre-check re-run

- **Before:** Task 15 done; no openEMS process; the date is before 2026-11-19; the owner's KiCad, profile and boards are never touched.
- **P0-C smoke (D-46):** `.venv\Scripts\python.exe tools\p0c.py --board tests/fixtures/lpf915.kicad_pcb --start U1.1 --end J1.1 --f0 915MHz --out <P0>\p0c-x` must exit 2 (a board inside the work tree). Then `.venv\Scripts\python.exe tools\p0c.py --board <P0>\boards\lpf915.kicad_pcb --start U1.1 --end J1.1 --f0 915MHz --lid-height 2.5 --out <P0>\p0c-smoke --preset draft --steps C0,C1` — about 45 min (C0 ≈ 1 min; C1 = six jobs at Draft ≈ 43 min, r4). Outputs: `<P0>/p0c-smoke/report/{p0c.json,p0c.md,p0c-public.json}` with C0 and C1 filled and the criteria not measured (None).
- **Pre-check re-run (D-49, A-3):** write `<P0>\precheck\precheck.py` with the text below (never committed), then run it once from the repo root, about 2 min: `.venv\Scripts\python.exe <P0>\precheck\precheck.py <P0>`. Every KiCad child gets the isolated environment explicitly, so no shell state is needed; `subprocess.run` waits for `pythonw.exe`.

```python
# spec 9.6's pre-check (D-49, A-3): KiCad 9.0.7's loader and its launch of a .cmd, in an isolated profile
import json, os, subprocess, sys, uuid
from pathlib import Path

R = Path(sys.argv[1]).resolve() / "precheck"
KC = Path(os.environ["ProgramFiles"]) / "KiCad" / "9.0" / "bin"
PL = R / "documents" / "KiCad" / "9.0" / "plugins" / "krs precheck"  # a space, so wx quotes the path
for sub in ("config", "cache", "temp", "appdata", "localappdata"):
    (R / sub).mkdir(parents=True, exist_ok=True)
PL.mkdir(parents=True, exist_ok=True)
env = {k: v for k, v in os.environ.items()
       if not k.upper().startswith("KICAD") and k.upper() not in ("TMPDIR", "KRS_PRIVATE_LIST")}
env |= {"KICAD_CONFIG_HOME": str(R / "config"), "KICAD_DOCUMENTS_HOME": str(R / "documents"),
        "KICAD_CACHE_HOME": str(R / "cache"), "TEMP": str(R / "temp"), "TMP": str(R / "temp"),
        "APPDATA": str(R / "appdata"), "LOCALAPPDATA": str(R / "localappdata")}  # r5 §1's isolation


def kicad(exe, *args, **extra):
    """A KiCad program, waited for, with the isolated environment only."""
    assert env["KICAD_CONFIG_HOME"].startswith(str(R)) and "TMPDIR" not in env
    return subprocess.run([str(KC / exe), *args], env=env | extra, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)


version = kicad("kicad-cli.exe", "version").stdout.strip()  # also seeds config/9.0/kicad_common.json
common = R / "config" / "9.0" / "kicad_common.json"
settings = json.loads(common.read_text(encoding="utf-8"))
settings.setdefault("api", {})["enable_server"] = True
settings.setdefault("system", {})["language"] = "English"
common.write_text(json.dumps(settings, indent=2), encoding="utf-8")
(PL / "plugin.json").write_text(json.dumps({
    "$schema": "https://go.kicad.org/api/schemas/v1", "identifier": "org.krsprecheck.cmd",
    "name": "KRS exec .cmd pre-check", "description": "kicad-rf-studio spec 9.6: an exec action whose entrypoint is a .cmd",
    "runtime": {"type": "exec"},
    "actions": [{"identifier": "marker", "name": "KRS .cmd pre-check", "description": "Runs launch.cmd, which writes a marker",
                 "show-button": True, "scopes": ["pcb"], "entrypoint": "launch.cmd", "args": ["--from-kicad", "two words"],
                 "icons-light": ["icon-24.png", "icon-48.png"], "icons-dark": ["icon-24.png", "icon-48.png"]}]},
    indent=2), encoding="utf-8")
from matplotlib.figure import Figure  # noqa: E402 (the dev venv's)
for size in (24, 48):
    Figure(figsize=(size / 100, size / 100)).savefig(PL / f"icon-{size}.png", dpi=100)
(PL / "launch.cmd").write_bytes(b"\r\n".join([
    b"@echo off", b"setlocal EnableDelayedExpansion", b'>>"%~dp0marker.txt" (', b"  echo marker=ok",
    b"  echo cwd=!CD!", b"  echo arg1=%~1", b"  echo arg2=%~2", b"  echo socket=!KICAD_API_SOCKET!",
    b"  echo token=!KICAD_API_TOKEN!", b")", b"exit /b 0", b""]))
loader = kicad("kicad-cli.exe", "version", KICAD_ENABLE_WXTRACE="1", WXTRACE="KICAD_API").stderr
(R / "loader.log").write_text(loader, encoding="utf-8")
token, replay = str(uuid.uuid4()), R / "wx_launch.py"
replay.write_text('''import json, os, sys, time
import wx
plugin, token = sys.argv[1], sys.argv[2]
args = (os.path.join(plugin, "launch.cmd"), "--from-kicad", "two words")
cmd = " ".join(f'"{a}"' if (" " in a or "\\t" in a or not a) else a for a in args)  # wxExecuteImpl's quoting
os.environ["KICAD_API_SOCKET"] = "ipc://" + os.path.join(os.environ["TMP"], "kicad", "api.sock")
os.environ["KICAD_API_TOKEN"] = token
os.chdir(plugin)
app = wx.App(False)
pid = wx.Execute(cmd, wx.EXEC_ASYNC | wx.EXEC_HIDE_CONSOLE)
marker = os.path.join(plugin, "marker.txt")
for _ in range(100):
    if os.path.exists(marker):
        break
    time.sleep(0.1)
time.sleep(0.5)
with open(os.path.join(plugin, "replay.json"), "w", encoding="utf-8") as f:
    json.dump({"pid": pid, "marker": os.path.exists(marker)}, f)
''', encoding="utf-8")
kicad("pythonw.exe", "-I", "-B", str(replay), str(PL), token)  # KiCad's own wx 3.2.8, console-less
r = json.loads((PL / "replay.json").read_text(encoding="utf-8"))
m = dict(line.split("=", 1) for line in (PL / "marker.txt").read_text(encoding="ascii", errors="replace").splitlines()
         if "=" in line)
checks = {"kicad_9_0_7": version == "9.0.7", "schema_valid": "schema validation successful" in loader,
          "action_loaded": "loaded action org.krsprecheck.cmd.marker" in loader,
          "exec_ready": "org.krsprecheck.cmd is not a Python plugin, all set" in loader,
          "launched": bool(r["pid"]) and r["marker"], "marker": m.get("marker") == "ok",
          "args": (m.get("arg1"), m.get("arg2")) == ("--from-kicad", "two words"),
          "socket": m.get("socket", "").startswith("ipc://") and m.get("socket", "").endswith("api.sock"),
          "token": m.get("token") == token, "cwd": Path(m.get("cwd", "")).resolve() == PL.resolve()}
checks["commit"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
(R / "precheck.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
print(json.dumps(checks))
sys.exit(0 if all(v for k, v in checks.items() if k != "commit") else 1)
```
- **Outputs:** `<P0>/precheck/{loader.log,precheck.json}`; the plugin folder's `marker.txt` and `replay.json`; the P0-C smoke reports.
- **Done when:** the smoke reports exist; the pre-check exits 0 with every check true. On exit 1 (`.cmd` refused, or a check false), stop: the fallback order (an `.exe` console script, then the `python` runtime) is the owner's call (D-49), and precheck.json goes into the report as it is.

---

## Phase 3 — decisions and reports

### Task 17 [decide]: P0-A

**Reads:** `<P0>/p0a/p0a.json`, `p0a.md`, and `<P0>/p0b/p0b.json`'s `decisions.dt_floor` (the controller gives `<P0>`).

**Rules, as computed in `decisions`; apply the branch that fired, all written out:**
- **D-29, `decisions.fit2d.branch`** (E_FIT2D_FINE stays unchanged in every branch: its text reads `{limit_pct}`):
  - `keep` or `keep-state`: `project.py`'s comment on `GATES` becomes `# P0-A confirmed the fit2d limit on <date> (docs/validation/<date>-p0-a.md)` (adding "and the floor" when D-30 confirmed). No test change. `keep-state`: the report states `max_delta_pp` as fit2d's model error.
  - `lower` to L %: `GATES["fit2d_limit"] = L / 100`; W_GATE_LIMITS's two literals `0.03` become L/100 written with `:g`. Search for `fit2d_limit` and `GATES`, not for `0.03` (criterion 1's ds_max is 0.03 too). Fixtures that then stop at the default mesh (r3 M1): at L = 2.5, lpf915 and lpf915-45 (n = 2: RF_A +2.58 %, RF_B +2.81 %), coupon_gcpw, coupon_dense and coupon_gcpw_arc (n = 2: +2.51…+2.55 %) and coupon_gcpw_masked at n = 3 (+2.79 %); at L = 2.0 also coupon_gcpw_pads at n = 2 (+2.47 %); at L = 1.5 every GCPW fixture at both n. The suite keeps running them at the 3 % gate through one autouse fixture in `tests/conftest.py`, `monkeypatch.setitem(project.GATES, "fit2d_limit", 0.03)` with `# ponytail: the fixtures were drawn under the 3 % gate; test_the_fit2d_limit_follows_p0a pins the new default`; new test `test_the_fit2d_limit_follows_p0a`: `monkeypatch.undo()` first, then `assert GATES["fit2d_limit"] == <L/100 literal> and f"not {<L/100>:g} and 0.8" in CATALOG["W_GATE_LIMITS"]`. Task 22's tutorial then sets `"gates": {"fit2d_limit": 0.03, "dt_floor": 0.8}` in lpf915's project.json and shows the W_GATE_LIMITS line it prints.
  - `unpredicted`: no change; the report names the failing rows as stated limits and as the Stage 2 calibration item (D-31).
- **D-30, `p0b.json`'s `decisions.dt_floor.confirmed`** (over P0-A's and P0-B's meshes): true → the comment says so; false → no change, the measured ratios go into the report as a stated limit (D-22), and the Stage 2 estimate gets the item.
- **D-26, `decisions.mask_shift`:** report only (A-2 is amended).
- **D-27, `decisions.twins.branch`:**
  - `refuse`: `sections()` emits `E_STAIRCASED {net}` where it emitted W_STAIRCASED; `pipeline.GEOMETRY_GATES = ("E_OPEN_IN_ROI", "E_SHORT_IN_ROI", "E_STAIRCASED")`; CATALOG gains `E_STAIRCASED`: "Net {net} has copper that is not axis-aligned (45° segments or arcs). P0-A measured such copper <max_dz0_pct, 1 decimal> % off its axis-aligned twin in Z0, above the 5 % budget, so the run is blocked. Route it with horizontal and vertical tracks." and loses W_STAIRCASED; every test that pins W_STAIRCASED or runs coupon_gcpw_45, coupon_gcpw_arc or lpf915-45 through `cost`, `run` or `verify` follows (`grep -rln "W_STAIRCASED\|coupon_gcpw_45\|coupon_gcpw_arc\|lpf915-45" tests`); new test `test_staircased_measured_copper_is_refused_after_p0a`: `cost` on lpf915-45 with `"allow_curve_port": true` exits 3 and prints `render("E_STAIRCASED", net="RF_B")`.
  - `advice`: W_STAIRCASED's template ends with " A finer mesh lowers the error: set \"mesh\": {\"n\": 3} in project.json."; test `test_the_staircase_warning_offers_the_fine_mesh`: `render("W_STAIRCASED", net="RF_B").endswith('set "mesh": {"n": 3} in project.json.')`.
  - `keep`: no change.
- **D-28:** report; its traces come in Task 19.
- **D-31 (Rec):** no mesh-rule change; R-P2-20, R-P2-21 and R-P2-27 stay stated limits, now with P0-A's FDTD evidence (the rows' `delta_pp`).
- **A P0-A verdict of `fail`:** its failing rows become stated limits, P0-B's decisions still apply (spec §9.7 orders P0-C after P0-B), and the exit report records it.

- [ ] **Step 1:** Write each fired branch's test; run it. Expected: FAIL.
- [ ] **Step 2:** Make the code and text change; run the full suite. Expected: all pass.
- [ ] **Step 3: Commit.** `feat: apply P0-A's decisions — fit2d <branch>, dt floor <confirmed|stated>, staircase <branch> (D-26..D-31; controller recommendation, owner unavailable)`.
- [ ] **Step 4: Return the report text** (`YYYY-MM-DD-p0-a.md`, the seven sections) and name `p0a.json` as its JSON: the verdict; inputs (commit, fixtures, Normal, n = 2 and 3, `versions`, the calibration); tables A1–A5 from `p0a.md`; the decisions, marked; stated limits (the A-1 and A-2 deviations, both MSLPort measurements of r7 §2.2 — 66–113 Ω on one-cell solid strips — and CPWPort's 0.09 % agreement; the mesh resolving about 80 % of the GCPW mask shift at n = 2; KiCad's CPWG +3.1 % bias; the 2D box's dielectric past the board edge; R-P2-20/21/27; R-P2-23's price: coupon_ms's x/y lines 92/55 at d = h/n against 58/37 at d = w/n at n = 2 (r3 A-3), with the microstrip rows as its FDTD confirmation); machine time, each row's `predicted_s` against `wall_s`, loaded steps left out; next step.

### Task 18 [decide]: P0-B and amendment A-5

**Reads:** `<P0>/p0b/p0b.json`, `p0b.md`, `emerge.json`.

**Rules:**
- **D-33, `decisions.verdict`:** `pass` → report. `fail` → no code change here; the report gives the diagnosis tables (the empty box's C_p, its cond and `verify_ds_max`; each job's `trunc_2ns` truncation estimate; verify's known differences: the L cell's C is not C_box, the PEC strips' few tenths of a nH, an in-grid R's loss). D-45: the controller decides whether our model is at fault; if it is, Task 18b; at the ceiling the §7.6 label stays on (D-15) and P0-C is recorded "do not start". A B1, B2 or B4 job that ended t_max or flat fails D-33 as it stands; whether the rerun raises that run's `t_max_s` while its residual still falls (O-13) is the controller's call under D-45, recorded in the report. With an accepted inconclusive EMerge result, the report states its cause and evidence, marked "controller recommendation, owner unavailable" (D-44).
- **D-34 (Rec), `decisions.tx.pass`:**
  - Pass: `make_project` writes `"allow_curve_port": True`; E_ROTATED_PART: "Part {ref} is not at a multiple of 90°, and project.json sets \"allow_curve_port\": false, so its port, a CurvePort, is refused. P0-B measured the CurvePort within the consistency limits against its 0° twin (max |ΔS| <tx ds_max, 3 decimals>); set \"allow_curve_port\": true, or rotate the part in KiCad."; tests: `test_new_writes_every_key_and_reads_it_back` expects `True`, `test_a_rotated_part_needs_the_switch` sets `False` itself, and any test relying on the old default follows (`grep -rn "allow_curve_port\|E_ROTATED_PART" tests`). A-5: §1.1 L43 "… TX-side matching, which has rotated parts, joins v1: P0-B's rotated-port case passed on <date> (§9.3)"; §10's first item "complex targets at IC pins: the TX side joined v1, so they go to the Stage 2 estimate (§7.7)"; §12's row "TX side in v1 | P0-B's rotated-port case: joined (<date>)".
  - Fail: the default stays false; E_ROTATED_PART: "Part {ref} is not at a multiple of 90°, so its port would be a CurvePort, which P0-B measured outside the consistency limits against its 0° twin (max |ΔS| <ds_max>). Rotate it in KiCad, or set \"allow_curve_port\": true in project.json at your own risk." A-5: §1.1 L43 "… TX-side matching stays out of v1: P0-B's rotated-port case failed on <date> (§9.3)"; §12's row "not joined (<date>)".
  - Either way, test `test_the_rotated_part_message_states_p0bs_result`: `"P0-B measured" in render("E_ROTATED_PART", ref="L1")`.
- **D-37, `decisions.reach.confirmed`** (judged at common cuts): true → protect.py's "(provisional: P0-B checks it)" becomes "(P0-B confirmed it on <date>)"; false → `project.REACH_H = 6.0`, DEFAULTS and the region/mesh defaults test read 6; run the suite and revise each failure whose only cause is the reach (lines, cells, times, fit2d values on the GCPW fixtures and lpf915), and stop and report any gate verdict that flips. Consequences, stated in the report: plan-4 projects without the field rebuild with the new reach and their results read stale; P0-D's models stay at 3.0 through `p0d.PIN`, so Task 20's references still match; Task 22's tutorial quotes B6's measured times (lpf915 at reach 6).
- **D-38, `decisions.growth.confirmed`:** true → stoprule's comment on GROWTH_DB says so; false → no change, the rises (and "not exercised" when nothing in the sweep diverged) are a stated limit (D-22).
- **D-39, `decisions.kmax`:** confirmed → spec.py's ponytail: "stable through k 0.48 on lpf915's L1 cell at a rule mesh's dielectric interface, 10 ns at openEMS's own dt (P0-B, <date>)"; else `K_MAX = <k_max>`, and `test_model_spec`'s `K_MAX == 0.45` and E_VERIFY_K's `"limit"` follow.
- **D-30:** applied by Task 17 from this file.
- **D-35, D-36, D-40:** report only (the traces come in Task 19).

- [ ] **Step 1:** Write each fired branch's test; run it. Expected: FAIL.
- [ ] **Step 2:** Make the code and text changes; run the full suite. Expected: all pass.
- [ ] **Step 3: Commit** the product changes: `feat: apply P0-B's decisions — TX side <joined|not joined>, reach, growth, K_MAX (D-34, D-37..D-39; controller recommendation, owner unavailable)`.
- [ ] **Step 4: Commit** A-5 alone: `docs(spec): A-5, the TX-side outcome after P0-B (controller recommendation, owner unavailable)`.
- [ ] **Step 5: Return the report text** (`YYYY-MM-DD-p0-b.md`) and name `p0b.json` as its JSON, which the controller saves beside it: the verdict; inputs (both projects' commands, Normal, the lid snapped to <lid_mm> at n = 2 and n = 3); the tables B-runs, B-consistency, B-twin (with `tx_ideal`), B-Cbox, B-n (as stored and at common cuts), B-EMerge (with `emerge==3.0.0b3`, the freeze, D-42's four workarounds and both levels), B-constants; the decisions, marked; stated limits (no in-band null: the null criterion reads n/a; F-R3; the lid snap's n dependence; the presets unconfirmed; `cut_delta` bounds the stop latency only, `trunc_2ns` estimates the truncation; the no-mask diagnostic is a harness-only model beyond D-9's list, run under D-43); machine time, each run's `predicted_s` and `worst_s` against `wall_s`, loaded steps left out; next step (P0-C "may start" or "do not start").

### Task 18b [run]: P0-B rerun after a D-45 fix (only when Task 18's D-45 branch fired)

- **Before:** the fix landed as its own test-first [code] commit, with no run in progress; the date is before 2026-11-19, else go to Task 22.
- **Commands:** Task 14's three commands, then Task 15's command, in that order. Every P0-B step reruns, because its key holds the `src/` tree's id; the writer refuses a mix of old and new records.
- **Expected machine time:** about 23–25 h (Task 14) plus about 1 h (Task 15).
- **Outputs and done when:** as Tasks 14 and 15; then Task 18 again, once (D-45: "rerun once").

### Task 19 [code]: The real stop-rule traces and their replay (D-40, spec 9.1)

**Files:**
- Create: `tests/fixtures/traces/coupon_gcpw_pads-k1.npz`, `-k2.npz`, `tests/fixtures/traces/lpf915-k1.npz` … `-k6.npz`, `tests/test_traces_real.py`

**Interfaces:**
- Consumes: `p0d.traces` (Task 12), `p0.load_trace` (Task 7b), `stop_rule`.
- Produces: the eight fixtures, members `t_u, u, t_i, i, te, e, exc, k, t_cut` (generic names), each ≤ 50 kB (D-40), every one a live converged job.

- [ ] **Step 1: Write the failing tests** in `tests/test_traces_real.py`:

```python
TRACES = sorted((Path(__file__).parent / "fixtures" / "traces").glob("*.npz"))


def test_real_traces_are_committed():  # spec 9.1, D-40
    assert [p.name for p in TRACES] == [*(f"coupon_gcpw_pads-k{k}.npz" for k in (1, 2)),
                                        *(f"lpf915-k{k}.npz" for k in range(1, 7))]
    assert all(p.stat().st_size <= 50_000 for p in TRACES)


@pytest.mark.parametrize("path", TRACES, ids=lambda p: p.stem)
def test_real_traces_replay_to_their_live_verdict_at_decimations_1_to_16(path):  # spec 6.3, D-40
    rec, k, exc, t_cut = p0.load_trace(path)
    step = float(np.diff(rec.te).max())
    for d in range(1, 17):  # a faster PC logs its energy sparser
        v = stop_rule(replace(rec, te=rec.te[::d], e=rec.e[::d]), k, "normal", exc)
        assert v.kind == "converged" and abs(v.t - t_cut) <= (d - 1) * step
```

  Test imports: `from dataclasses import replace`, `Path`, `numpy as np`, `pytest`; `import p0`; `stop_rule`.
- [ ] **Step 2: Run** `python -m pytest tests/test_traces_real.py -q`. Expected: FAIL (no fixtures).
- [ ] **Step 3: Write the fixtures:** `python tools/p0d.py traces --p0 <P0> --out tests/fixtures/traces`. If it refuses a job that did not converge live, or a trace above 50 kB, stop and report: D-40's fixtures are the live converged branch.
- [ ] **Step 4: Stage and check privacy:** `git add tests/fixtures/traces tests/test_traces_real.py`, then `python tools/privacy_gate.py --staged`. Expected: no hit (generic member names).
- [ ] **Step 5: Run** the file, then the full suite. Expected: all pass. If a replay misses its live cut, never loosen the bound: stop and report.
- [ ] **Step 6: Commit.** `test: real stop-rule traces from P0-A's pad coupon and P0-B's lpf915, replayed at decimations 1–16 (D-40)`

### Task 20 [code]: The P0-D references and the P0-D report (D-48)

**Files:**
- Create: `tests/fixtures/p0d/<model>.npz` for each of `p0d.MODELS`, `tests/test_p0d_refs.py`

**Interfaces:**
- Consumes: `p0d.references`, `p0d.models`, `p0d.MODELS`, `p0.s_of`, `p0a.COUPONS`, `p0.load_trace`; Task 19's traces.
- Produces: the nine references: members `f`, `S`, `t_cut`, `spec_hash`, plus `z0` and `eeff` for the seven harness coupons.

- [ ] **Step 1: Write the failing tests** in `tests/test_p0d_refs.py`:

```python
REFS = Path(__file__).parent / "fixtures" / "p0d"
TRACES = Path(__file__).parent / "fixtures" / "traces"


def test_the_windows_references_are_committed_with_generic_members():  # D-48
    for name in p0d.MODELS:
        with np.load(REFS / f"{name}.npz") as z:
            extra = {"z0", "eeff"} if name in p0a.COUPONS else set()
            assert set(z.files) == {"f", "S", "t_cut", "spec_hash"} | extra, name


def test_the_references_are_the_models_p0d_builds_here(tmp_path):  # D-47: CI compares the same models
    p0d.models(tmp_path)
    for name in p0d.MODELS:
        built = spec_hash(json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8")))
        with np.load(REFS / f"{name}.npz") as z:
            assert str(z["spec_hash"]) == built, name


@pytest.mark.parametrize("name", ["coupon_gcpw_pads", "lpf915"])
def test_the_draft_replay_of_the_committed_traces_reproduces_the_references(name):  # D-48: exact by causality
    traces = [p0.load_trace(p) for p in sorted(TRACES.glob(f"{name}-k*.npz"))]
    with np.load(REFS / f"{name}.npz") as ref:
        s, t_cut = p0.s_of(traces, ref["f"], "draft")
        assert np.array_equal(t_cut, ref["t_cut"]) and np.abs(s - ref["S"]).max() <= 1e-12
```

  Test imports: `json`, `Path`, `numpy as np`, `pytest`; `import p0, p0a, p0d`; `spec_hash`.
- [ ] **Step 2: Run** `python -m pytest tests/test_p0d_refs.py -q`. Expected: FAIL (no references).
- [ ] **Step 3: Write the references:** `python tools/p0d.py references --p0 <P0> --out tests/fixtures/p0d`.
- [ ] **Step 4: Stage and check privacy** as in Task 19.
- [ ] **Step 5: Run** the file and the full suite. Expected: all pass. If a hash differs, a Phase 3 change moved a model: stop and report (D-37's reach is pinned by `p0d.PIN`).
- [ ] **Step 6: Commit.** `test: the Windows P0-D references, P0-A's and P0-B's Normal records replayed at Draft (D-48)`
- [ ] **Step 7: Return the report text** (`YYYY-MM-DD-p0-d.md`, verdict "prepared, not run") and its JSON (`{"models", "jobs_per_distro", "distros", "references": [file names], "elapsed_days", "machine_hours": 0}` from `models`' matrix): the workflow and its jobs; the models and the 15 excitation jobs per distro; the references; r7's expected times on a 4-vCPU runner (lpf915 at Draft 1.1–1.7 h per excitation to 12 ns, 3.7–5.5 h to T_max; the coupons 0.3–1.0 h); the pass criteria (criterion 1 against the references, and the coupons' Z0 and εeff within 0.5 %; Linux never gets looser limits); stated limits (the build steps, the library path and the source build's version metadata are unverified until the first dispatch; fedora:44's image; F-R1 exercised by the excite jobs); next step: the owner's first push, then a manual dispatch.

### Task 21 [decide]: The pre-check, P0-0 and P0-C procedure reports (report-only)

**Reads:** Task 16's `<P0>/precheck/precheck.json` and `loader.log`; Task 1's audit outcomes; the repo.

- [ ] **Step 1: The pre-check report** (`YYYY-MM-DD-precheck.md`, D-49, Rec; its JSON is `precheck.json`): the verdict from precheck.json — "§9.6 passed; no fallback needed" only when every check is true, else "§9.6 not passed; the fallback (an `.exe` console script, then the `python` runtime) is the owner's call (D-49)"; the commit it ran at; evidence level "KiCad 9.0.7's real loader (kicad-cli with WXTRACE) loaded the exec action whose entrypoint is a .cmd; the launch, replayed with KiCad's own wx 3.2.8 from a console-less parent, ran it with the expected args, environment (KICAD_API_SOCKET, KICAD_API_TOKEN) and cwd; the toolbar click was not run"; the 2-minute GUI click listed as an owner confirmation that does not block; the identifier rule for Stage 2 (dot-separated segments of letters and digits, at least 3, the first letters only) and the plugin folder name with a space; A-3's isolation (TMP set, TMPDIR and KICAD* cleared, APPDATA and LOCALAPPDATA redirected, kicad_common.json seeded); an appendix with the procedure, `plugin.json` and `launch.cmd` as Task 16 writes them (no absolute path). Return the text.
- [ ] **Step 2: Audit and write the P0-0 report** (`YYYY-MM-DD-p0-0.md`, D-23), one row per item, and its JSON (`{"items": {item: "ok" | "owner" | "push-gated"}, "tests": {"tier_a": passed, "openems": passed}, "elapsed_days", "machine_hours": 0}`):
  - porting (plans 1–4 ported the research module by module, each with its test; no patched third-party code in the repo);
  - the hooks and the deny list (active, readable, never printed, its path included); the `--all` outcome (identity lines only, expected until the owner's rewrite; no count) and `--generic-only` (clean), rerun now with Task 1's command;
  - `.gitignore` (Task 1's test); the fixtures and how they were made (`tools/make_fixtures.py`, isolated profile); the lpf915 checklist (each §9.1 item against its fixture test);
  - tiers: (a) `python -m pytest -q` and `python -m pytest -m openems -q` counts on this PC (run them now, after every gate run); (b) and (c) written, never run;
  - SPDX, NOTICE, LICENSE and COPYING.LESSER (test_repo); the gate's four gaps fixed (Task 1);
  - the owner's items: the identity rewrite, c20f71b's text (the deny list does not cover it), the deny-list review, RFsim and NOTICE.
  Return the text and the JSON.
- [ ] **Step 3: The P0-C procedure** (`YYYY-MM-DD-p0-c.md`, D-46, no numbers) and its JSON (`{"steps": p0c.STEPS, "criteria": ["c1", "c2", "c3", "c4"], "smoke": {"steps": ["C0", "C1"], "ran": bool}}`, no number): what the owner runs (`tools/p0c.py` with a copy of the board outside any work tree), what each step and criterion computes, the verdict rule, where the outputs stay (OUT only), what may come back to the repo (decisions only, in non-identifying words: the time policy, `RETUNE_VALIDATED`, the default mesh), the expected machine time (about 8.5–9.5 chain-equivalents, r7 §4.2) and the smoke run's status (cost and base at Draft on lpf915 ran). Return the text and the JSON.

### Task 22 [decide]: The tutorial, the Stage 1 exit report and the Stage 2 estimate (report-only)

**Reads:** every report JSON in `docs/validation/`, the P0-C smoke's `p0c-public.json` (its `machine`), the step records' times, `git log`.

- [ ] **Step 1: Write the failing test** `test_the_readme_has_a_tutorial` in `tests/test_repo.py`: the README has a `## Tutorial` heading, and the section after it names each of `new`, `cost`, `run`, `retune` and `verify`. Run it. Expected: FAIL (no `## Tutorial`).
- [ ] **Step 2: Write README's "Tutorial" section** (D-21, after P0-B): `new tests/fixtures/lpf915.kicad_pcb --start U1.1 --end J1.1 --f0 915MHz --lid-height 2.5 -o lpf915`, then `cost lpf915`, `run lpf915`, `retune lpf915 C2=4.7pF`, `verify lpf915`, each with what it prints and P0-B's measured times on the development PC (B1's cost time and wall time at Normal — B6's when D-37 raised the reach — B2's wall time, a retune in seconds), the gates override of Task 17's `lower` branch when it fired, and a line that the retune is labelled relative / what-if until P0-C passes.
- [ ] **Step 3: Run** the test and the full suite. Expected: all pass.
- [ ] **Step 4: Commit.** `docs: a tutorial on lpf915 with P0-B's measured times (D-21)`
- [ ] **Step 5: Return the exit report text** (`YYYY-MM-DD-stage1-exit.md`) and its JSON (`{"gates": {gate: status}, "elapsed_days", "machine_hours": {gate: hours}, "stage2_hours"}`): the verdict, D-3's status in its exact words when P0-A and P0-B were decided, else, at the ceiling, "<the gates decided>; <the gates not decided by 2026-11-19>, with their data; P0-D and tier (b) prepared, not run; P0-C tool ready; Stage 1 exit pending the owner" (D-4); a table of the gates (P0-0, P0-A, P0-B, the pre-check: decided; P0-C: tool ready, smoke-run, owner; P0-D and tier (b): prepared, push-gated); the timebox (elapsed days against the target and the ceiling) and the machine hours summed from p0a.json, p0b.json (EMerge steps included), the smoke's p0c-public.json and the pre-check, predicted against measured; the P0-C procedure as one page (D-46), condensed from `-p0-c.md`; the owner's items (P0-C on the private board, the time policy, the identity rewrite and c20f71b, RFsim/NOTICE, the GUI click, the first push, PyPI, flipping `RETUNE_VALIDATED`); and the **Stage 2 estimate** (D-53): hours per task with its assumptions, for the PySide6 client tailing `events.jsonl` with detach and re-attach; the toolbar button with the pre-check's outcome; live import and refill through kicad-python and the 9.0.7 against 10.x API gaps; KiCad 10.x support for the button (its own plugin folder, the stricter identifier, output capture); the advanced panel; E12/E24 snapping; the reference made prominent if P0-C's criterion 3 asks; the what-if UI if the fallback stays; complex targets only if the TX side joined; packaging; the pt-BR catalog after v1; the mesh-rule calibration first (inside lines by edge role on plan 2's ratchet harness, fit2d as the objective, D-31); a C_box correction only if P0-C shows one is needed. Calibrate it by Stage 1's velocity: plan tasks done per working day from plans 1–5's task counts and `git log`'s first and last dates, each Stage 2 item sized in plan-task units with its assumption.

---

## Not in this plan

- **The owner's (spec §12, D-2):** running P0-C on the private board and its verdict; the v1 time policy; the band-factor default, a stop-preset retune and a RAM-model change (P0-C decides them); setting `RETUNE_VALIDATED` after P0-C; the identity rewrite, c20f71b's text and the deny-list review; the NOTICE/RFsim question (it gates publishing); the source of the private board files; the 2-minute GUI click of the pre-check; PyPI.
- **Push-gated:** running P0-D, tier (b) and tier (c); F-R1's Linux PR_SET_PDEATHSIG test; moving `board.py`'s NEWEST_TESTED after tier (c).
- **Deferred by ruling (D-2):** a mesh-rule recalibration (D-31: R-P2-20, R-P2-21 and R-P2-27 stay stated limits; the calibration is the Stage 2 estimate's first item); a C_box correction (D-35, report only); an F-R3 gate (O-35, a known limit); fitting package presets to vendor S2P files (only the owner's own check through `p0c.py --s2p`); Babel tooling (O-33); band-1.25 runs, a stop-preset retune and a RAM-model change on this PC; tightening σ_max, reciprocity and the loss limit (P0-C data); a committed pre-check tool (D-49); every §10 item.
- **Known limits:** the 2D reference's dielectric runs past the coupons' board edge (A-13); KiCad's 35 µm CPWG formula reads Z0 +3.1 % and εeff −10.2 % against cs2d; the mesh resolves about 80 % of a 0.15 mm GCPW gap's mask shift at n = 2; lpf915's 2.5 mm lid snaps +8.9 % at n = 2 and +3.6 % at n = 3, which enters B5 against B1; the lid on and off (R46) is measured by P0-C's step C5 on the owner's board, while P0-B reports only the snapped height (D-32); the load check reads command lines by substring at a step's start and end only; the empty-box fit assumes white residuals and one geometry; the K_MAX sweep runs one cell (lpf915's L1) for 10 ns at the Strict level; the reach is judged at common cuts, the twin and the bias also as stored; EMerge is a same-day beta with four workarounds (D-42) and only 8 pinned packages, and its coupons in the 45 h box are unmeasured in size; P0-C's wall time per preset is a round model and its RAM a system-wide reading; lpf915 has no in-band null, so the null criterion is untested until P0-C; the growth and K_MAX decisions rest on lpf915 and the coupons only; the workflow's build steps, library path and version metadata are unverified until the first dispatch.
