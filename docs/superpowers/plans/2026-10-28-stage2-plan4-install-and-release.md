# Stage 2 · Plan 4 — Install and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make kicad-rf-studio installable and releasable (design §5.9 item 4): NOTICE's runtime dependencies, the README's install section for Windows and Linux, `tools/release_check.py` with its push-gated workflow, and §5.11's end-to-end check (one real run through the GUI, and the installed launcher replayed), closed by the Stage 2 exit record.

**Architecture:**
- **One stdlib script, `tools/release_check.py`** (Task 2), runs five steps, each printing one PASS, FAIL or SKIPPED line, inside one temporary folder named with a space and an accent: a wheel built by `pip wheel --no-deps` from `git archive` of HEAD (the tree a release's source zip holds) and inspected; a fresh venv with that wheel, `pip check`, kicad-python's import and both entry points; the GUI's own entry function offscreen in that venv; `install-kicad-plugin` run by that venv's console script, its plugin.json checked by kicad-python's packager, by KiCad's schema fetched at the tags 9.0.7 and 10.0.7 and by the identifier rules; the privacy gate's generic rules over the history and over the wheel's files, failing whenever the gate could not scan. Its pure parts and its privacy step get tier (a) tests; `.github/workflows/release-check.yml` (Task 3) runs it on a version tag or by hand, on Windows with Python 3.14 and on Linux at the declared floor, after the owner's push.
- **Docs with checks** (Tasks 1 and 5): NOTICE's list is pinned equal to `control.DEPENDENCIES`; the README's install section is pinned to the CLI's real subcommands and to `install-kicad-plugin`'s own KiCad step.
- **§5.11's end-to-end check** (Tasks 4 and 6): an opt-in test drives the real window, New on lpf915 at Draft to Verify, against a fresh data folder named by `KRS_E2E_DIR`; the controller runs it, follows the README's Windows steps in an isolated folder, replays that install's launcher from a console-less parent against `tests/fake_kicad.py`, and writes the Stage 2 exit record.

**Tech Stack:** Python ≥ 3.11 (the dev venv runs 3.14.2). From the stdlib: `zipfile`, `tempfile`, `subprocess`, `venv` (as `python -m venv`), `urllib.request`, `json`, `re`. jsonschema 4 (kicad-python brings it), imported only by the release check's plugin step. pip's `pip wheel --no-deps` (no `build`), git (`archive`, `ls-tree`), kicad-python 0.8.0's `kicad-python-packager`, PySide6-Essentials 6.12 offscreen, GitHub Actions (`actions/checkout@v4`, `actions/setup-python@v5`). pytest, with no pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-27-stage2-gui-and-button-design.md` (binding), its §5.9 item 4:
- §5.6's Licensing, Install and Release check, in full.
- §5.11 items 1 to 3; item 4, the owner's click-through, stays the owner's and does not block.
- §7's owner defaults: the install source before PyPI is a GitHub release's source zip after the push; no one-command installer in Stage 2; PySide6 stays a core dependency (unchanged).
- §3 (anti-goals) and §4 (constraints) bind every task. This is Stage 2's last plan: once it is merged, §5.11's items 1 to 3 hold.

The engine authority is `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, amended here in §3.6 (A-19, Task 1), §9.1 (A-20, Task 3), and §3.4 and §12 (A-21, Task 5); plan 1 took A-13 to A-15 and plan 3 A-16 to A-18. Plans 1 to 3 (`docs/superpowers/plans/2026-10-2*-stage2-plan{1,2,3}-*.md`) bind through their controller rulings where they still apply, and their records (`.superpowers/sdd/2026-10-28-stage2-plan{1,2,3}-rulings-and-minors.md`, git-ignored) carry four items here: kicad-python's import after `pip check` (Task 2), NOTICE from `control.DEPENDENCIES` and the packages it leaves out (Task 1), plugin.json against KiCad's tagged schemas (Task 2), and the README's moved venv (Task 5). The research is git-ignored: `.superpowers/sdd/stage2-research/r3-pack/findings.md` (packaging, licences, the release check), `r1-kicad/findings.md` (plugin.json's schema and the identifier rules) and `r2-gui/findings.md` (offscreen Qt on Linux). Stage 1's exit record, `docs/validation/2026-10-25-stage1-exit.md`, is the model for Task 6's.

**Branch:** `stage2-plan4`, from `main` at `06c2a81`. This plan is `docs/superpowers/plans/2026-10-28-stage2-plan4-install-and-release.md`. Commands run from the repo root with `.venv/Scripts/python`.

**Before Task 1 (the controller):**
1. Branch `stage2-plan4` from `main`. `git diff --stat 06c2a81 HEAD -- src tests tools pyproject.toml .github README.md NOTICE` must print nothing; otherwise re-check this plan's line references first.
2. Commit this plan on the branch. Its rulings are its last section, `## Controller rulings (2026-10-28; binding)`.
3. After Task 6: the whole-branch review, then a local fast-forward merge into `main` and the branch deleted. Nothing is pushed.

## Global Constraints

- **Python and platforms (design §4):** the declared floor stays `>=3.11` and ci.yml's matrix as it is; the Windows install uses Python 3.14, because the openEMS 0.37.0 wheels need 3.13 or 3.14; Windows 10/11, and Linux with glibc ≥ 2.34 (the PySide6 wheels' floor); KiCad 9.0.7 minimum, with 10.x supported.
- **Dependencies:** `pyproject.toml` does not change: no new runtime or dev dependency, PySide6-Essentials only (no QtCharts, no Addons), no pytest-qt, no PyYAML, no `build`. `tools/release_check.py` imports the standard library and `privacy_gate` at module level, and jsonschema (kicad-python's) only inside `plugin_problems`.
- **Import rules (design §4):** the core never imports Qt; the GUI never imports openEMS or CSXCAD; `cli` and `worker` import neither Qt nor kicad-python; the button helper never imports Qt. Plans 1 to 3's `QT_FREE` probe stays as it is.
- **Process model (design §5.1):** nothing in the GUI process reaches `runs.run_jobs`. The real run's test patches `runs.run_jobs` and `runs.ensure_calibrated` to fail in its own process, as `tests/test_gui.py`'s `window` fixture does, and asserts that openEMS and CSXCAD never loaded there.
- **Messages:** every user-facing string of the app is a code in the one `CATALOG` of `core.messages`; this plan adds none. `tools/release_check.py` prints plain English, as `tools/privacy_gate.py` does: a release tool's output, not the app's.
- **Qt only offscreen:** tests run under `QT_QPA_PLATFORM=offscreen`, which `tests/conftest.py` sets, and the real run's test asserts its QApplication's platform is offscreen; the release check sets it for the fresh venv's GUI. No visible window and no modal dialog: the real run's test replaces `ask` on its window.
- **No real KiCad, Documents, KiCad settings or data folder:** no test or tool touches a real KiCad plugin folder, the real Documents folder, KiCad's settings or the real data folder, and none starts KiCad. Tests keep conftest's autouse `no_kicad`; a subprocess that runs the app gets `LOCALAPPDATA` and `XDG_DATA_HOME` under `tmp_path`. The release check gives every process of its gui and plugin steps its temporary folder as `LOCALAPPDATA`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, `MPLCONFIGDIR`, `KICAD_DOCUMENTS_HOME` and `KICAD_CONFIG_HOME`, a `KICAD_API_SOCKET` nobody listens on, and no `KICAD_API_TOKEN` (its build and install steps run no app and keep pip's own cache). The real run's data folder is `KRS_E2E_DIR/data`, and `KRS_E2E_DIR` must lie outside the repository. Task 6 sets all of these in the same PowerShell call, or the same replay process, as each command it runs.
- **No push and no upload of any kind:** nothing is pushed, nothing goes to PyPI, no GitHub release is made, and the workflow is written, not run (design §4). Network use is limited to pip's downloads and KiCad's schema files at their tags, in the release check and in Task 6, never in a tier (a) test.
- **Tests:** test-first. Tier (a) tests never run openEMS, KiCad, the network or a build. The real run is opt-in: skipped unless `KRS_E2E_DIR` is set, and marked `openems`.
- **Full suite:** before every commit, `.venv/Scripts/python -m pytest -q` passes. It takes about 15 minutes, and the shell caps a foreground command at 10, so run it once in the background, with nothing beside it, and wait for its exit.
- **Privacy:** the pre-commit privacy gate runs on every commit (never `--no-verify`). Synthetic fixtures only. No committed file holds an absolute user path, a drive letter followed by a colon and a slash, a UNC share, an e-mail address or a private name: tests build an address at run time (`"t" + "@" + "t.test"`). Task 6's exit record names no path outside the repo: the real run prints `KRS_E2E_DIR` as `<KRS_E2E_DIR>`, the replay's folder is written `<iso>`, and the privacy gate's outcome is given without a count or a pattern index.
- **Licence and files:** GPL-3.0-or-later; English; `# SPDX-License-Identifier: GPL-3.0-or-later` heads every new `.py` and `.yml` file (`tests/test_repo.py` checks both).
- **Git:** no commit carries a co-author line. Nothing is pushed.
- **Workflow:** every implementer runs `graphify query "<question>"` (or `explain` or `path`) from the repo root before reading code, and `graphify update .` after each commit. Ponytail applies: the laziest solution that works, the repo's functions reused, the fewest files, the stdlib first, and a `ponytail:` comment, with its ceiling and its upgrade, on each corner cut.
- **Amendments:** each changed spec line ends with "(A-n, Stage 2 plan 4: controller recommendation, owner unavailable.)", and the spec's Status line gets one sentence, which later tasks widen.

## Review Focus

1. **A venv path with a space or an accent.** A Windows user name such as "João Silva" puts both into `%LOCALAPPDATA%\kicad-rf-studio\venv`. The build, pip, both entry points, the GUI and `install-kicad-plugin` must work there; a character the console's code page lacks is refused with E_PLUGIN_PYTHON (plan 3).
   - Checks: the release check's one temporary folder is named `krs release é …`, so its archive, wheel, venv, GUI and plugin steps all run under such a path, which `test_main_skips_what_a_failed_step_holds_up_fails_a_step_that_raises_and_removes_its_folder` pins (Task 2). Task 6 follows the README into `krs-plan4 readme é` and replays that install's launcher.
2. **pip resolving a protobuf that imports badly.** kicad-python 0.8.0's protos refuse a protobuf runtime older than their 5.29.6 gencode, which its `protobuf>=5.29,<6` pin allows. A shared venv holding 5.29.0 to 5.29.5 passes `pip check` and fails at the button's first import.
   - Checks: mitigated by the README's venv of the app's own (Task 5), where pip resolves the newest protobuf the pin allows; the release check's `python -I -c "import kipy.board_types"` after `pip check` (Task 2) guards a bad resolution at release time. Neither can see a user's shared venv (ruling).
3. **A wheel missing its package data, or carrying tests, tools, fixtures, docs or private text.**
   - Checks: `inspect_wheel` requires exactly HEAD's tracked `src/` files and the `.dist-info` files; `wheel_hits` runs the privacy gate's generic rules over the wheel's texts, with `tools/privacy_allow.txt` read as `src/` paths (every source file passed the pre-commit hook's private list). `test_the_wheel_holds_the_package_its_data_and_its_dist_info_and_nothing_else` and `test_the_wheels_texts_go_through_the_privacy_gates_generic_rules_its_allow_list_read_as_src_paths` (Task 2) pin both.
4. **A venv moved or deleted after `install-kicad-plugin`.** The launcher holds the old Python, so cmd or sh writes its own line and exits non-zero, which KiCad 10 shows, and KiCad 9 nothing. The README says to run `install-kicad-plugin` again, which rewrites the launcher.
   - Checks: `test_install_kicad_plugin_run_again_rewrites_the_launcher_for_the_venv_where_it_now_is` and the README test's "run `install-kicad-plugin` again" (Task 5); plan 3's launcher test pins that the launcher passes a failing helper's exit code.
5. **Offscreen Qt missing its Linux libraries on CI.** `release-check.yml` installs, on Linux, exactly the packages `ci.yml` installs for offscreen Qt; both are unverified until the first push.
   - Check: `test_the_release_check_workflow_runs_on_a_version_tag_or_by_hand_on_windows_and_at_the_linux_floor` (Task 3) requires `ci.yml`'s package line in both files.

---

## File structure

```
NOTICE                                         # T1 header line; "Runtime dependencies (not included)"
tests/test_gui_control.py                      # T1 NOTICE's list equals control.DEPENDENCIES
tools/release_check.py                         # T2 the release check
tests/test_release_check.py                    # T2 its pure parts, its privacy step and main
tests/test_button.py                           # T2 the identifier rules from release_check; T5 the launcher rewritten
.github/workflows/release-check.yml            # T3
tests/test_repo.py                             # T3 the workflow; T5 the README's install section
tests/test_gui.py                              # T4 dispose(); the opt-in real run through the window
README.md                                      # T5 Install; the Tutorial's first paragraph; Development setup 4 and 6
docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md   # T1 A-19; T3 A-20; T5 A-21
docs/validation/<date>-stage2-exit.md          # T6, by the controller
```

---

### Task 1 [code]: NOTICE's runtime dependencies

**Files:**
- Modify:
  - `NOTICE` (its second line, L2; a new last entry after L22);
  - `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (the Status line, L4; §3.6, after L177).
- Test: `tests/test_gui_control.py` (after `test_about_names_the_version_the_licence_notices_and_each_runtime_dependency`, the file's end, L432).

**Interfaces:**
- Consumes: plan 2's `control.DEPENDENCIES`, a tuple of 15 `(name, licence)` pairs in About's order: PySide6-Essentials, shiboken6, matplotlib, numpy, scipy, h5py, shapely, scikit-rf, pandas, kicad-python, protobuf, pynng, jsonschema, openEMS, CSXCAD. `tests/test_repo.py`'s `test_the_lgpl_text_ships_with_the_lgpl_code` splits NOTICE into entries at `"\n\n\n"`.
- Produces: NOTICE's last entry, headed `Runtime dependencies (not included)`, with one line `  - NAME (LICENCE)` per entry of `control.DEPENDENCIES`, in order; A-19.

- [ ] **Step 1: Write the failing test,** in `tests/test_gui_control.py` after the About test:

```python
def test_notice_names_each_runtime_dependency_with_its_licence_as_about_does():  # design 5.6 Licensing; A-19
    notice = (Path(__file__).resolve().parents[1] / "NOTICE").read_text(encoding="utf-8")
    entry = next(e for e in notice.split("\n\n\n") if e.startswith("Runtime dependencies (not included)\n"))
    assert re.findall(r"^  - (\S+) \((.+)\)$", entry, re.M) == list(control.DEPENDENCIES)  # one list for both
    assert "start only with a build that bundles them, which is deferred." in " ".join(entry.split())  # design 5.6
```

- [ ] **Step 2: Run it.** `.venv/Scripts/python -m pytest tests/test_gui_control.py -q -k notice`. Expected: FAIL with `StopIteration`: NOTICE has no such entry yet.
- [ ] **Step 3: NOTICE.** Its second line becomes `It includes the third-party pieces below, each under the licence given, but for the runtime dependencies listed last.` After its last line, append two empty lines and this entry, ending with a newline:

```
Runtime dependencies (not included)
  kicad-rf-studio includes none of these: pip installs them with it from PyPI, and its setup-openems command installs
  openEMS and CSXCAD from openEMS's official Windows package (on Linux, you build them). Each is under its own
  licence, as the GUI's About box lists them:
  - PySide6-Essentials (LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only)
  - shiboken6 (LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only)
  - matplotlib (Matplotlib License (PSF-based))
  - numpy (BSD-3-Clause)
  - scipy (BSD-3-Clause)
  - h5py (BSD-3-Clause)
  - shapely (BSD-3-Clause)
  - scikit-rf (BSD-3-Clause)
  - pandas (BSD-3-Clause)
  - kicad-python (MIT)
  - protobuf (BSD-3-Clause)
  - pynng (MIT)
  - jsonschema (MIT)
  - openEMS (GPL-3.0-or-later)
  - CSXCAD (LGPL-3.0-or-later)
  pip also installs the packages these depend on, each under its own licence, which pip show <name> names in the
  venv. kicad-rf-studio conveys none of them, Qt included, so the LGPL's conveying duties (its text, a way to replace
  the library, an offer of its source) start only with a build that bundles them, which is deferred.
```

- [ ] **Step 4: The spec.**
  - §3.6 gains, after the line "  - the copy of CSXCAD's `SmoothMeshLines` (LGPL-3.0-or-later).": "- NOTICE also names the runtime dependencies, which kicad-rf-studio does not include (pip installs them; openEMS and CSXCAD come from `setup-openems` or the user's build), each with its licence, as the GUI's About box lists them. Since it conveys none of them, Qt included, the LGPL's conveying duties start only with a build that bundles them, which §10 defers. (A-19, Stage 2 plan 4: controller recommendation, owner unavailable.)"
  - The Status line gains, at its end: " On 2026-10-28, Stage 2's plan 4 amended §3.6 (A-19) the same way."
- [ ] **Step 5: Run them.** `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_repo.py -q`. Expected: PASS (the SmoothMeshLines entry still names COPYING.LESSER).
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add NOTICE tests/test_gui_control.py docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs: NOTICE names the runtime dependencies it does not include, as About lists them, and when LGPL duties would start; spec A-19 (Stage 2 design 5.6; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 2 [code]: `tools/release_check.py`

**Files:**
- Create: `tools/release_check.py`, `tests/test_release_check.py`.
- Modify: `tests/test_button.py` (`import re`, L9, goes; `import release_check` after `from test_gui_control import recorder, until`, L26; L242–245 become one line).

**Interfaces:**
- Consumes:
  - `tools/privacy_gate.py`: `_read_allow(root: Path) -> set[str]`, `_scan_file(where: str, path: str, data: bytes, deny: list[str], generic: bool) -> list[str]`, and the script itself, `privacy_gate.py --all --generic-only`, which prints one `<where>:<line>: <rule>` per hit and exits 1 when it found one, 0 when clean; it also exits 1, with nothing on stdout and its reason on stderr, when a git call fails (its `git()` calls `sys.exit`) or it crashes. With `--generic-only` it reads no private list, so commit headers, tags and refs never hit.
  - Plan 3: `button.plugin_json(entrypoint)`, `button.IDENTIFIER` (`org.kicadrfstudio.app`), `install-kicad-plugin --kicad 10.0`, which writes `<KICAD_DOCUMENTS_HOME>/<KiCad|kicad>/10.0/plugins/kicad-rf-studio`; kicad-python's console script `kicad-python-packager validate DIR` (exit 0 when valid; its requirements.txt warning concerns the python runtime only); `gui.main(argv)`.
- Produces, in `tools/release_check.py` (run as `python tools/release_check.py`; tests import it as `release_check`, `tools` being on pytest's `pythonpath`):
  - `ROOT = Path(__file__).resolve().parents[1]`, `WINDOWS = sys.platform == "win32"`.
  - `SCHEMA_TAGS = ("9.0.7", "10.0.7")`, `SCHEMA_URL = "https://gitlab.com/kicad/code/kicad/-/raw/{tag}/api/schemas/api.v1.schema.json"`.
  - `IDENTIFIER_RULES`, a tuple of `(name, match, pattern)`: `("KiCad 9.0.7", re.search, r"[\w\d]{2,}\.[\w\d]+\.[\w\d]+")` (its `IsValidIdentifier`, unanchored), `("KiCad 10.0.7", re.fullmatch, r"[a-zA-Z]{2,}(\.([a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]|[a-zA-Z0-9])){2,}")` (anchored) and `("design 5.5", re.fullmatch, r"[A-Za-z]+(\.[A-Za-z0-9]+){2,}")`; they move here from `tests/test_button.py`.
  - `DIST_INFO = ("METADATA", "WHEEL", "RECORD", "entry_points.txt", "top_level.txt", "licenses/LICENSE", "licenses/COPYING.LESSER", "licenses/NOTICE")`.
  - `SMOKE`, the GUI step's code, exactly: `"import sys; from PySide6.QtCore import QTimer; from PySide6.QtWidgets import QApplication; from kicad_rf_studio import gui; app = QApplication(sys.argv[:1]); QTimer.singleShot(0, lambda: [w.close() for w in app.topLevelWidgets() if type(w).__name__ == 'MainWindow' and w.isVisible()] or app.exit(3)); sys.exit(gui.main([]))"`: it exits 0 only when a visible main window was closed, which ends the event loop.
  - `NEEDS = {"install": "build", "gui": "install", "plugin": "install"}`; `STEPS = (build, install, gui, plugin, privacy)`.
  - `inspect_wheel(wheel: Path, sources: list[str]) -> list[str]`, `identifier_problems(identifier: str) -> list[str]`, `plugin_problems(plugin: dict, schemas: dict[str, dict]) -> list[str]`, `wheel_hits(wheel: Path, allow: set[str]) -> list[str]` (Step 3 says what each returns).
  - The steps `build`, `install`, `gui`, `plugin` and `privacy`, each `(tmp: Path) -> tuple[str, str]`, a status (`"PASS"`, `"FAIL"` or `"SKIPPED"`) and its detail; the helpers `run`, `failed`, `program` and `isolated`; `main() -> int`.

- [ ] **Step 1: Write the failing tests.** `tests/test_release_check.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""tools/release_check.py (Stage 2 design 5.6): its pure parts, its privacy step and its order of steps, with no
network and no build. The steps that build, install and fetch run in the controller's release check (plan 4, Task 6)."""
import json
import subprocess
import sys
import zipfile
from importlib.resources import files
from pathlib import Path

import pytest

import privacy_gate as gate
import release_check
from kicad_rf_studio import button

ROOT = Path(__file__).resolve().parents[1]
WHEEL = "kicad_rf_studio-0.1.0.dev0-py3-none-any.whl"  # as pip wheel names this repo's
INFO = "kicad_rf_studio-0.1.0.dev0.dist-info"
SOURCES = ["src/kicad_rf_studio/__init__.py", "src/kicad_rf_studio/data/stackups/jlcpcb-2l.json"]


def wheel(path, members=None):
    """A wheel at `path` holding SOURCES' package files and the dist-info files, changed by `members` (None drops one)."""
    content = {s.removeprefix("src/"): b"x\n" for s in SOURCES} | {
        f"{INFO}/{name}": b"x\n" for name in release_check.DIST_INFO} | (members or {})
    with zipfile.ZipFile(path, "w") as z:
        for name, data in content.items():
            if data is not None:
                z.writestr(name, data)
    return path


def test_the_wheel_holds_the_package_its_data_and_its_dist_info_and_nothing_else(tmp_path):  # design 5.6; RF 3
    assert release_check.inspect_wheel(wheel(tmp_path / WHEEL), SOURCES) == []
    bad = wheel(tmp_path / WHEEL, {"tests/conftest.py": b"x\n", "kicad_rf_studio/data/stackups/jlcpcb-2l.json": None,
                                   f"{INFO}/licenses/NOTICE": None})
    assert release_check.inspect_wheel(bad, SOURCES) == [
        "tests/conftest.py: not the package's", f"{INFO}/licenses/NOTICE: missing",
        "kicad_rf_studio/data/stackups/jlcpcb-2l.json: missing"]


@pytest.mark.parametrize(("identifier", "fails"), [
    ("org.kicadrfstudio.app", []),  # design 7's default
    ("io.github.owner.kicadrfstudio", []),  # r1's form for the owner's account
    ("org.kicad_rf.app", ["KiCad 10.0.7", "design 5.5"]),  # 9.0.7's \w takes the underscore
    ("org.kicad-rf.app", ["KiCad 9.0.7", "design 5.5"]),  # 10.0.7 takes the hyphen
    ("a.b.c", ["KiCad 9.0.7", "KiCad 10.0.7"]),  # a one-letter first segment
    ("org.app", ["KiCad 9.0.7", "KiCad 10.0.7", "design 5.5"])])  # two segments
def test_an_identifier_passes_kicad_9s_and_10s_rules_and_the_designs(identifier, fails):  # design 5.5; plan 3
    assert release_check.identifier_problems(identifier) == fails


def test_plugin_json_is_checked_against_each_schema_and_each_identifier_rule():  # design 5.6
    schema = json.loads(files("kipy.packaging.schemas").joinpath("api.v1.schema.json").read_text(encoding="utf-8"))
    plugin = button.plugin_json("launch.cmd")  # kipy's schema: KiCad 10.0.7's with one more scope (plan 3)
    assert release_check.plugin_problems(plugin, {"9.0.7": schema, "10.0.7": schema}) == []
    worse = {**plugin, "identifier": "1org.x.y", "runtime": {"type": "wasm"}}
    assert release_check.plugin_problems(worse, {"9.0.7": schema}) == [
        "KiCad 9.0.7's schema: '1org.x.y' does not match '^[a-zA-Z][-_a-zA-Z0-9.]{0,98}[a-zA-Z0-9]$'",
        "KiCad 9.0.7's schema: 'wasm' is not one of ['python', 'exec']",
        "identifier '1org.x.y': KiCad 10.0.7's rule", "identifier '1org.x.y': design 5.5's rule"]


def test_the_wheels_texts_go_through_the_privacy_gates_generic_rules_its_allow_list_read_as_src_paths(tmp_path):
    mail = "t" + "@" + "t.test"  # built at run time: the gate would flag a literal address in this file
    path = tmp_path / "w.whl"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("kicad_rf_studio/core/mesh/smooth.py", f"# {mail}\n")  # its src/ path is in privacy_allow.txt
        z.writestr("kicad_rf_studio/x.py", f"x = 1\n# {mail}\n")
    assert release_check.wheel_hits(path, gate._read_allow(ROOT)) == [
        "wheel:kicad_rf_studio/x.py:2: generic:email"]  # Review Focus 3


def test_the_privacy_step_passes_only_a_clean_scan_and_fails_when_the_gate_cannot_scan(tmp_path, monkeypatch):
    def gate_run(code, out="", err=""):  # the gate's script exits `code`, printing `out` and `err`
        done = subprocess.CompletedProcess([], code, out, err)
        monkeypatch.setattr(release_check, "run", lambda command, **kw: done)
        return release_check.privacy(tmp_path)  # no wheel in tmp_path: the history only

    assert gate_run(0) == ("PASS", "the history (no wheel): clean under the generic rules (the private list is the "
                                   "hooks')")
    assert gate_run(1, "abcd1234:docs/x.md:1: generic:drive\n") == (
        "FAIL", "the history (no wheel), under the generic rules:\n  abcd1234:docs/x.md:1: generic:drive")
    status, detail = gate_run(1, err="privacy_gate: git rev-list failed: x")  # exit 1 and no hit: it never scanned
    assert status == "FAIL" and detail.endswith(": exit code 1: privacy_gate: git rev-list failed: x")


def test_main_skips_what_a_failed_step_holds_up_fails_a_step_that_raises_and_removes_its_folder(monkeypatch, capsys):
    made = []

    def build(tmp):
        made.append(tmp)
        (tmp / "dist").mkdir()
        return "FAIL", "no wheel"

    def install(tmp):
        raise AssertionError("install needs build")

    def gui(tmp):
        raise AssertionError("gui needs install")

    def plugin(tmp):
        raise AssertionError("plugin needs install")

    def privacy(tmp):
        raise OSError("gone")  # a step that raises is its own FAIL, and the next steps still run

    monkeypatch.setattr(release_check, "STEPS", (build, install, gui, plugin, privacy))
    assert release_check.main() == 1
    assert capsys.readouterr().out.splitlines() == [
        "FAIL build: no wheel", "SKIPPED install: build did not pass", "SKIPPED gui: install did not pass",
        "SKIPPED plugin: install did not pass", "FAIL privacy: OSError: gone"]
    (tmp,) = made
    assert " " in tmp.name and "é" in tmp.name and not tmp.exists()  # Review Focus 1; one folder, removed


def test_the_release_check_loads_only_the_standard_library_until_its_plugin_step():  # the workflow adds jsonschema
    probe = (f"import sys; sys.path.insert(0, {str(ROOT / 'tools')!r}); import release_check; print(sorted("
             "{m.split('.')[0] for m in sys.modules} & {'kicad_rf_studio', 'jsonschema', 'kipy', 'PySide6', 'numpy'}))")
    out = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr
```

  In `tests/test_button.py`, `test_the_plugin_passes_kicads_schema_and_both_identifier_rules_and_its_icons_are_pngs`'s four lines from `nine = ...` to the design-rule assertion (L242–245) become `assert release_check.identifier_problems(button.IDENTIFIER) == []  # KiCad 9.0.7's, 10.0.7's and design 5.5's rules`; `import re` goes (nothing else uses it) and `import release_check` joins the imports after `from test_gui_control import recorder, until`.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_release_check.py tests/test_button.py -q`. Expected: FAIL at both files' collection with `ModuleNotFoundError: No module named 'release_check'`.
- [ ] **Step 3: Implement** `tools/release_check.py`.
  - Its docstring: "The release check (Stage 2 design 5.6): run by hand before a release, from the repo root (`python tools/release_check.py`, with the dev venv's Python, which has jsonschema), and by .github/workflows/release-check.yml on a version tag or by hand. Five steps, each printing one PASS, FAIL or SKIPPED line: build (a wheel from git archive of HEAD, the tree a release's source zip holds, inspected), install (a fresh venv: the wheel, pip check, kicad-python's import and both entry points), gui (the main window built, shown offscreen and closed, in that venv), plugin (install-kicad-plugin in that venv, its plugin.json checked against KiCad's schemas at SCHEMA_TAGS and the identifier rules) and privacy (the privacy gate's generic rules over the history and the wheel; the private list stays the hooks'). Every file it makes is under one temporary folder, removed at the end and named with a space and an accent, but for pip's own cache and build folders; a folder it cannot remove is named on a last line. Every process of the gui and plugin steps gets that folder for its data, caches and KiCad folders. Exits 1 when a step fails. The standard library only, but for jsonschema, which kicad-python brings, imported by the plugin step. Its lines are plain English: a release tool's output, like privacy_gate's, not the app's."
  - The pure parts, which the tests determine:
    - `inspect_wheel`: `[]` when `wheel` holds exactly the package (`sources`, HEAD's tracked paths under `src/`, without `src/`) and `<name>-<version>.dist-info/` plus each of `DIST_INFO`, that prefix read from the wheel's own file name (its first two `-`-separated fields); else `"NAME: not the package's"` for each member it should not hold, sorted, then `"NAME: missing"` for each it lacks, sorted.
    - `identifier_problems`: the names of `IDENTIFIER_RULES` that `identifier` fails, in their order.
    - `plugin_problems`: `f"KiCad {tag}'s schema: {error.message}"` for each error of `jsonschema.Draft7Validator(schema).iter_errors(plugin)`, for each `tag, schema` of `schemas`, sorted within a schema by `[str(p) for p in error.path]`; then `f"identifier {plugin['identifier']!r}: {name}'s rule"` for each name `identifier_problems` gives. `from jsonschema import Draft7Validator` sits inside it.
    - `wheel_hits`: one comprehension over the wheel's members, reusing `privacy_gate._scan_file(f"wheel:{name}", name, data, [], "src/" + name not in allow)`: the gate's generic rules over each member's text, as `--generic-only` reads a blob, off for a path `tools/privacy_allow.txt` lists.
  - The steps, the helpers and `main`, which no tier (a) test fixes whole, are written as given:

```python
def run(command: list[str], timeout: float = 1800, **kw) -> subprocess.CompletedProcess:
    """`command` run to its end, its output captured as UTF-8 text with errors replaced."""
    return subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout, **kw)


def failed(command: list[str], done: subprocess.CompletedProcess) -> tuple[str, str]:
    """A FAIL naming `command` (its program's file name and its next three arguments), its exit code and the last
    line of its stderr, else of its stdout."""
    lines = (done.stderr.strip() or done.stdout.strip()).splitlines()
    return "FAIL", f"{' '.join([Path(command[0]).name, *command[1:4]])}: exit code {done.returncode}: " + (
        lines[-1] if lines else "")


def program(tmp: Path, name: str) -> str:
    """The fresh venv's program `name`."""
    return str(tmp / "venv" / ("Scripts" if WINDOWS else "bin") / (name + (".exe" if WINDOWS else "")))


def isolated(tmp: Path) -> dict:
    """This environment for the fresh venv's app: its data, caches and settings, and KiCad's documents and settings
    folders under `tmp`, a KiCad API socket nobody listens on, no KiCad token, and Qt offscreen."""
    home = str(tmp / "home")
    names = ("LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "MPLCONFIGDIR")
    return {**{k: v for k, v in os.environ.items() if k != "KICAD_API_TOKEN"}, **dict.fromkeys(names, home),
            "KICAD_DOCUMENTS_HOME": str(tmp / "documents"), "KICAD_CONFIG_HOME": str(tmp / "config"),
            "KICAD_API_SOCKET": f"ipc://{tmp / 'no-kicad.sock'}", "QT_QPA_PLATFORM": "offscreen"}


def build(tmp: Path) -> tuple[str, str]:
    """(a) A wheel that pip wheel --no-deps builds from git archive of HEAD, the tree a release's source zip holds,
    into tmp/dist, inspected."""
    head = run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    for command in (["git", "archive", "--format=zip", "-o", str(tmp / "source.zip"), head],
                    [sys.executable, "-m", "pip", "wheel", "--no-deps", "--quiet", "--disable-pip-version-check",
                     "--wheel-dir", str(tmp / "dist"), str(tmp / "source.zip")]):
        if (done := run(command, cwd=ROOT)).returncode:
            return failed(command, done)
    wheel = next((tmp / "dist").glob("*.whl"))
    sources = run(["git", "ls-tree", "-r", "-z", "--name-only", head, "src"], cwd=ROOT).stdout.split("\0")
    if problems := inspect_wheel(wheel, [s for s in sources if s]):
        return "FAIL", "\n  ".join([wheel.name, *problems])
    return "PASS", f"{wheel.name}, from git archive of {head[:8]}: the package, its data and its dist-info, nothing else"


def install(tmp: Path) -> tuple[str, str]:
    """(b) A fresh venv, the wheel installed, pip check, then kicad-python's protos imported (pip check passes on a
    protobuf of 5.29.0 to 5.29.5, which they refuse: plan 3) and the gui-scripts entry there (the plugin step runs the
    console script). pip keeps its own cache."""
    wheel, python = next((tmp / "dist").glob("*.whl")), program(tmp, "python")
    for command in ([sys.executable, "-m", "venv", str(tmp / "venv")],
                    [python, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", str(wheel)],
                    [python, "-m", "pip", "check", "--disable-pip-version-check"],
                    [python, "-I", "-c", "import kipy.board_types"]):
        if (done := run(command)).returncode:
            return failed(command, done)
    if not Path(program(tmp, "kicad-rf-studio-gui")).exists():
        return "FAIL", "the fresh venv has no kicad-rf-studio-gui: the wheel lacks its gui-scripts entry"
    return "PASS", (f"{wheel.name} installs in a fresh venv with both entry points, pip check finds nothing broken, "
                    "kicad-python's protos import")


def gui(tmp: Path) -> tuple[str, str]:
    """(c) The GUI entry's own function in the fresh venv, offscreen and isolated (SMOKE)."""
    command = [program(tmp, "python"), "-I", "-c", SMOKE]
    if (done := run(command, timeout=300, env=isolated(tmp))).returncode:
        return failed(command, done)
    return "PASS", "the main window was built, shown offscreen and closed, in the fresh venv"


def plugin(tmp: Path) -> tuple[str, str]:
    """(d) install-kicad-plugin by the fresh venv's console script into tmp's KiCad 10.0 folder (9.0's files are the
    same), checked by kicad-python-packager, against KiCad's schema at each of SCHEMA_TAGS and the identifier rules
    (plugin_problems), and its entrypoint executable, as KiCad checks it at the click."""
    folder = tmp / "documents" / ("KiCad" if WINDOWS else "kicad") / "10.0" / "plugins" / "kicad-rf-studio"
    for command in ([program(tmp, "kicad-rf-studio"), "install-kicad-plugin", "--kicad", "10.0"],
                    [program(tmp, "kicad-python-packager"), "validate", str(folder)]):
        if (done := run(command, timeout=300, env=isolated(tmp))).returncode:
            return failed(command, done)
    data = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
    schemas = {tag: json.load(urllib.request.urlopen(SCHEMA_URL.format(tag=tag), timeout=60)) for tag in SCHEMA_TAGS}
    problems = plugin_problems(data, schemas) + [f"{a['entrypoint']}: not executable" for a in data["actions"]
                                                 if not os.access(folder / a["entrypoint"], os.X_OK)]
    if problems:
        return "FAIL", "\n  ".join(problems)
    return "PASS", (f"plugin.json passes kicad-python's validator, KiCad {' and '.join(SCHEMA_TAGS)}'s schemas and "
                    "the identifier rules, and its launcher is executable")


def privacy(tmp: Path) -> tuple[str, str]:
    """(e) The privacy gate's generic rules, as ci.yml runs them: over the history (its script, --all --generic-only)
    and over the wheel's texts (wheel_hits). The private list stays the hooks' (spec 9.1): pre-commit and pre-push run
    it on every commit and push."""
    command = [sys.executable, "-X", "utf8", str(ROOT / "tools" / "privacy_gate.py"), "--all", "--generic-only"]
    done = run(command, cwd=ROOT)
    hits = done.stdout.splitlines()
    if done.returncode != (1 if hits else 0):  # the gate also exits 1, with nothing on stdout, when git fails
        return failed(command, done)
    wheel = next((tmp / "dist").glob("*.whl"), None)
    hits += wheel_hits(wheel, privacy_gate._read_allow(ROOT)) if wheel else []
    scanned = f"the history and {wheel.name}" if wheel else "the history (no wheel)"
    if hits:
        return "FAIL", "\n  ".join([f"{scanned}, under the generic rules:", *hits])
    return "PASS", f"{scanned}: clean under the generic rules (the private list is the hooks')"


NEEDS = {"install": "build", "gui": "install", "plugin": "install"}
STEPS = (build, install, gui, plugin, privacy)


def main() -> int:
    """Runs STEPS in order in one temporary folder and prints each one's line; a step whose NEEDS did not pass is
    SKIPPED, and a step that raises is its own FAIL. Returns 1 when a step failed, else 0."""
    sys.stdout.reconfigure(errors="replace")
    status = {}
    # ponytail: a file a process still holds (Windows) stays in TEMP, named on the last line; a TEMP deeper than about
    # 120 characters overflows Windows' 260-character paths in the venv, which the failing step names: run it with a
    # shorter TEMP then
    with tempfile.TemporaryDirectory(prefix="krs release é ", ignore_cleanup_errors=True) as name:
        tmp = Path(name).resolve()  # TEMP may be an 8.3 short path, which venv warns about
        for step in STEPS:
            need = NEEDS.get(step.__name__)
            if need and status[need] != "PASS":
                result = ("SKIPPED", f"{need} did not pass")
            else:
                try:
                    result = step(tmp)
                except Exception as e:  # its own FAIL; the next steps still run
                    result = ("FAIL", f"{type(e).__name__}: {e}")
            status[step.__name__] = result[0]
            print(f"{result[0]} {step.__name__}: {result[1]}", flush=True)
    if Path(name).exists():
        print(f"NOTE: {Path(name).name} is left in TEMP: delete it by hand", flush=True)
    return 1 if "FAIL" in status.values() else 0


if __name__ == "__main__":
    sys.exit(main())
```

  - Its imports: `json`, `os`, `re`, `subprocess`, `sys`, `tempfile`, `urllib.request`, `zipfile`, `from pathlib import Path` and `import privacy_gate` (beside it in `tools/`; the script's folder is on `sys.path` when it runs, and pytest's `pythonpath` holds `tools`). The constants and the pure parts come first, in Interfaces' order; `NEEDS` and `STEPS` sit after `privacy`, before `main`.
  - Its other ponytail notes: on `SCHEMA_TAGS`, "# ponytail: KiCad's floor and the newest 10.0 release, fetched at run time; their schemas are identical (probed with 9.0.9.1 and 10.0.8-rc1). An offline or rate-limited run fails the plugin step: vendor both files then, with a NOTICE entry. Add a tag when KiCad ships a newer schema"; on `DIST_INFO`, "# ponytail: exact: a setuptools that writes another dist-info file fails the build step until it is named here"; on `SMOKE`, "# ponytail: gui.main, the gui-scripts entry's own function: its .exe launcher cannot be told to close, so only a launcher replay (design 5.11 item 3) starts the .exe itself".
- [ ] **Step 4: Run them again.** Same command. Expected: PASS.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add tools/release_check.py tests/test_release_check.py tests/test_button.py
git commit -m "feat(tools): release_check.py builds a wheel from git archive of HEAD and checks it, its install, the GUI offscreen, plugin.json against KiCad's schemas and the privacy gate's generic rules (Stage 2 design 5.6)"
graphify update .
```

---

### Task 3 [code]: The release-check workflow

**Files:**
- Create: `.github/workflows/release-check.yml`.
- Modify: `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (the Status line, L4; §9.1's CI tiers, after the tier (c) bullet, L547).
- Test: `tests/test_repo.py` (after `test_every_workflow_starts_with_an_spdx_header`, the file's end).

**Interfaces:**
- Consumes: Task 2's `tools/release_check.py` (exit 1 on a FAIL; jsonschema needed by its plugin step); `ci.yml`'s offscreen Qt line: `        run: sudo apt-get update && sudo apt-get install -y --no-install-recommends libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3`; `pyproject.toml`'s `requires-python`, as `test_ci_tests_the_declared_python_floor_with_read_only_permissions` reads it.
- Produces: `.github/workflows/release-check.yml`; A-20.

- [ ] **Step 1: Write the failing test,** in `tests/test_repo.py`:

```python
def test_the_release_check_workflow_runs_on_a_version_tag_or_by_hand_on_windows_and_at_the_linux_floor():  # A-20
    flow = (ROOT / ".github" / "workflows" / "release-check.yml").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    floor = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["requires-python"]
    assert '\non:\n  push:\n    tags: ["v*"]\n  workflow_dispatch:\n' in flow  # never a branch push (design 4)
    assert "\npermissions:\n  contents: read\n" in flow and "persist-credentials: false" in flow  # no token kept
    assert "fetch-depth: 0" in flow  # a shallow clone would leave the privacy gate one commit to scan
    assert f'python-version: "{floor[2:]}"' in flow and 'python-version: "3.14"' in flow  # Linux's floor, Windows'
    assert next(line for line in ci.splitlines() if "libegl1" in line) in flow.splitlines()  # Review Focus 5
    assert flow.splitlines()[-1] == "      - run: python tools/release_check.py"
```

- [ ] **Step 2: Run it.** `.venv/Scripts/python -m pytest tests/test_repo.py -q`. Expected: FAIL with `FileNotFoundError` for `release-check.yml`.
- [ ] **Step 3: The workflow,** `.github/workflows/release-check.yml`, given whole:

```yaml
# SPDX-License-Identifier: GPL-3.0-or-later
# The release check (Stage 2 design 5.6; spec 9.1 (d), A-20): tools/release_check.py on a version tag or by hand, on
# Windows with Python 3.14 and on Linux at the Python floor pyproject.toml declares. Prepared, not run: nothing is
# pushed before the owner says so (design 4).
name: release-check

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  release-check:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            python-version: "3.14"  # the README's Windows Python: openEMS 0.37's wheels need 3.13 or 3.14
          - os: ubuntu-24.04
            python-version: "3.11"  # the declared floor, Debian 12's system Python
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # the whole history, which the privacy gate scans
          persist-credentials: false  # nothing after this step needs the job's token
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      # Qt's offscreen platform still loads these (ci.yml's list); unverified until the first push
      - if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y --no-install-recommends libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3
      - run: python -m pip install "jsonschema>=4.23,<5"  # the plugin step's schema check, at kicad-python's pin
      - run: python tools/release_check.py
```

- [ ] **Step 4: The spec.**
  - §9.1's CI tiers gain, after the tier (c) bullet: "  - (d) the release check, `tools/release_check.py`, by hand before a release and through `release-check.yml` on a version tag or by hand, on Windows with Python 3.14 and on ubuntu-24.04 at the declared floor: a wheel built from `git archive` of HEAD and inspected, a fresh venv's install with `pip check`, kicad-python's import and both entry points, the offscreen GUI smoke test, `plugin.json` against KiCad 9.0.7's and 10.0.7's schemas and the identifier rules, and the privacy gate's generic rules over the history and the wheel. Like tiers (b) and (c), its workflow first runs after the owner's push. (A-20, Stage 2 plan 4: controller recommendation, owner unavailable.)"
  - The Status sentence of Task 1 becomes " On 2026-10-28, Stage 2's plan 4 amended §3.6 and §9.1 (A-19 and A-20) the same way."
- [ ] **Step 5: Run it again.** Same command. Expected: PASS, the SPDX test included.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add .github/workflows/release-check.yml tests/test_repo.py docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "ci: release-check.yml runs the release check on a version tag or by hand, on Windows and at the Linux floor; spec A-20 (Stage 2 design 5.6; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 4 [code]: One real run through the window, opt-in

**Files:**
- Test: `tests/test_gui.py` (`dispose`, the `window` fixture's teardown made a function, just before the fixture, L100; a new last test, after `test_the_help_menu_shows_about_and_qts_about`, L997).

**Interfaces:**
- Consumes: `MainWindow()` with its default prefix, `control.orchestrator()`; its state as plans 1 to 3 left it: `new_form` (`board`, `start`, `end`, `f0`, `preset`, `lid`, `create_button`), `board_chosen`, `pads_read`, `creating`, `cost_button`, `cost_status`, `cost_lines`, `cost`, `run_dir`, `run_button`, `ask`, `command`, `proc`, `end` (the watched end event), `run_status`, `jobs`, `log`, `results` (`parts`, `what_if`, `canvas`, `apply_button`, `retune_status`, `verify_button`, `verify_lines`, `stale`), `applying`, `opened.verified`, `tabs`, `started`, `pool`, `tick`; test_gui's `ROOT`, `opened`, `items`, `column`, `grab`, `PART` and `VALUE`; `test_gui_control.until`; `test_cli_cost`'s `FIX` and `fail`; conftest's `qapp`.
- Produces: `dispose(windows)`, which the `window` fixture's teardown and the real run share; `test_one_real_run_through_the_window_new_cost_run_retune_apply_verify`, selected by `-k real_run`, skipped unless `KRS_E2E_DIR` is set, and marked `openems`. Task 6 runs it; it prints one `e2e STEP: SECONDS s: ...` line per step, `KRS_E2E_DIR`'s path shown as `<KRS_E2E_DIR>`.

- [ ] **Step 1: Write the test.** Just before the `window` fixture, the fixture's teardown becomes a function, which the fixture then calls (`yield make`, then `dispose(made)` and `made.clear()`):

```python
def dispose(windows):
    """What `windows` started killed, their pools awaited and the windows closed: a test leaves no run going."""
    for w in windows:
        for proc in w.started:  # every process it started, not only the watched one
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        w.close()
        w.pool.shutdown(wait=True)  # a read still going would outlive the fake data folder
```

  At the end of `tests/test_gui.py`:

```python
# ponytail: run by hand only, so it can lag the window's API until it next runs; the fake-backed tests above pin each
# step's widgets meanwhile
@pytest.mark.openems
@pytest.mark.skipif(not os.environ.get("KRS_E2E_DIR"), reason="one real run through the window (design 5.11 item 2): "
                    "set KRS_E2E_DIR to an empty folder outside the repository")
def test_one_real_run_through_the_window_new_cost_run_retune_apply_verify(qapp, monkeypatch):
    out = Path(os.environ["KRS_E2E_DIR"]).resolve()  # design 5.11 item 2: opt-in, never in the suite's runs
    assert not out.is_relative_to(ROOT), "KRS_E2E_DIR must be outside the repository"  # its settings name this host
    out.mkdir(parents=True, exist_ok=True)
    assert not any(out.iterdir()), "KRS_E2E_DIR must be empty: a fresh data folder, as on a new install"
    assert qapp.platformName() == "offscreen"  # hours of a window, never a visible one
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.setenv(name, str(out / "data"))  # runs.data_dir(), here and in every process the window starts
    for name in ("run_jobs", "ensure_calibrated"):
        monkeypatch.setattr(runs, name, fail)  # design 5.1: no run in the GUI process
    board, pj = out / "board" / "lpf915.kicad_pcb", out / "board" / "lpf915" / "project.json"  # New's default folder
    board.parent.mkdir()
    board.write_bytes((FIX / "lpf915.kicad_pcb").read_bytes())

    def ended(timeout):  # the watched process to its exit, then the tick that reads its end event
        until(lambda: w.tick() or w.proc.poll() is not None, timeout=timeout)
        w.tick()

    def say(step, begin, line):  # the exit record quotes these lines: KRS_E2E_DIR's path never shows in them
        print(f"e2e {step}: {time.monotonic() - begin:.0f} s: {line.replace(str(out), '<KRS_E2E_DIR>')}", flush=True)

    w = MainWindow()  # the real orchestrator (control.orchestrator)
    w.show()
    try:
        begin, f = time.monotonic(), w.new_form
        f.board.setText(str(board))
        w.board_chosen()
        w.pads_read.result(timeout=60)
        w.tick()
        f.start.setCurrentText("U1.1")
        f.end.setCurrentText("J1.1")
        f.f0.setText("915MHz")
        f.preset.setCurrentText("draft")
        f.lid.setValue(2.5)  # the shield's lid, as the README's tutorial gives it
        f.create_button.click()
        assert w.creating.result(timeout=120)[0] == pj
        w.tick()
        opened(w)
        assert w.project_status.text() == render("G_PROJECT", path=str(pj), f0_mhz="915", harmonics=3, preset="draft")
        say("new", begin, w.project_status.text())
        begin = time.monotonic()
        w.cost_button.click()  # a fresh data folder: it calibrates this machine first
        ended(3600)
        assert w.cost_status.text() == render("G_END_DONE", exit_code=0), w.cost_status.text()
        say("cost", begin, " | ".join(items(w.cost_lines)))  # the estimate, before any run
        opened(w)  # the cost's end read the project again, which found it as this model's cost
        assert w.cost == w.run_dir and w.run_button.isEnabled()
        grab(w, "e2e-cost")
        asked = []
        monkeypatch.setattr(w, "ask", lambda text: asked.append(text) or True)
        begin = time.monotonic()
        w.run_button.click()
        assert w.command == "run" and "Worst case: " in asked[0]  # Run asked on the cost it shows
        ended(12 * 3600)
        assert (w.end["params"]["exit_code"], w.run_status.text()) == (0, render("G_END_DONE", exit_code=0)), \
            w.run_status.text()
        say("run", begin, " | ".join([*column(w.jobs, 4), items(w.log)[-1]]))
        grab(w, "e2e-run")
        opened(w)
        r = w.results
        assert column(r.parts, PART) == ["C1", "L1", "C2", "C3"] and not r.what_if.isHidden()
        r.parts.item(2, VALUE).setText("5pF")  # C2, snapped to E24 (design 7's default)
        assert r.parts.item(2, VALUE).text() == "5.1pF"
        assert r.canvas.figure.get_suptitle().endswith("\n" + render("G_WHAT_IF"))  # retuned, under the label
        w.tabs.setCurrentWidget(r)
        grab(w, "e2e-retune")
        r.apply_button.click()
        w.applying.result(timeout=300)
        w.tick()
        assert r.retune_status.text() == render("G_APPLIED", folder=str(pj.parent / "results"))
        assert parts(load_project(pj))["C2"]["value"] == "5.1pF"
        opened(w)
        begin = time.monotonic()
        r.verify_button.click()  # the values are applied: verify starts at once
        assert w.command == "verify"
        ended(12 * 3600)
        assert (w.end["params"]["exit_code"], w.run_status.text()) == (0, render("G_END_DONE", exit_code=0)), \
            w.run_status.text()
        opened(w)
        assert [c for c, _ in w.opened.verified][:2] == ["I_VERIFY_RESULTS", "I_VERIFY_COMPARE"] and r.stale.isHidden()
        assert load_project(pj)["verify"]["values"]["C2"] == "5.1pF"
        say("verify", begin, " | ".join(items(r.verify_lines)))
        w.tabs.setCurrentWidget(r)
        grab(w, "e2e-verify")
        assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # design 4: the GUI process
    finally:
        dispose([w])  # a failed step leaves no run going
```

- [ ] **Step 2: Run it, gated.** `.venv/Scripts/python -m pytest tests/test_gui.py -q -k "real_run or costs_then_runs"`. Expected: `1 passed, 1 skipped` (the fixture's teardown through `dispose`; no `KRS_E2E_DIR`). Then, as one PowerShell call, with a folder that holds a file and one inside the repo: `$d = Join-Path $env:TEMP 'krs-plan4-gate'; New-Item -ItemType Directory -Force $d | Out-Null; Set-Content "$d\x" 'x'; foreach ($e2e in $d, "$PWD\krs-plan4-gate") { $env:KRS_E2E_DIR = $e2e; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q -k real_run }; Remove-Item Env:KRS_E2E_DIR; Remove-Item -Recurse -Force $d`. Expected: `1 failed` twice, with `KRS_E2E_DIR must be empty` and then `KRS_E2E_DIR must be outside the repository`; nothing started, and no `krs-plan4-gate` folder in the repo (`1 skipped` instead means openEMS does not import in the dev venv: on Windows, `CSXCAD_INSTALL_PATH` names its folder). The real run is Task 6's.
- [ ] **Step 3: Full suite, commit, graph.** The suite gains one skip.

```bash
git add tests/test_gui.py
git commit -m "test(gui): an opt-in real run through the window, lpf915 at Draft from New to Verify, sharing the window fixture's teardown as dispose() (Stage 2 design 5.11 item 2)"
graphify update .
```

---

### Task 5 [code]: The README's install section

**Files:**
- Modify:
  - `README.md` (`## Install`, L5–19; the Tutorial's first paragraph, L23; `## Development setup`, its step 4, L110, and a step 6 after its step 5, L111);
  - `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (the Status line, L4; §3.4's Windows install steps, L153–156, and its Linux bullet, after L160; §12's PyPI row, L680).
- Test: `tests/test_repo.py` (gains `import re`, `import pytest`, `from kicad_rf_studio.cli import main` and `from kicad_rf_studio.core.messages import CATALOG`); `tests/test_button.py` (after `test_the_installed_launcher_runs_the_helper_and_passes_its_line_and_exit_code`, L300).

**Interfaces:**
- Consumes: the CLI's subcommands (`kicad-rf-studio COMMAND --help` exits 0 for a real one, 2 for any other); `CATALOG["I_PLUGIN_NEXT"]`, which holds "Preferences › Plugins › Enable KiCad API, then restart KiCad"; plan 3's `button.install(version)`, which writes the launcher for `os.path.abspath(sys.executable)` every time, and test_button's `SEGMENT` and `LAUNCHER`; upstream's openEMS-Project v0.37.0 scripts (`install_deps.sh --install` asks, then installs the distribution's packages with sudo, `python3-venv` among them on apt; `update_openEMS.sh <prefix> --python` installs the bindings into the active venv, else makes its own); Task 2's `tools/release_check.py` and Task 4's real-run test, which the README names.
- Produces: the README's Install section (Windows, Linux, After installing), the Tutorial's first paragraph and Development setup's steps 4 and 6; A-21.

- [ ] **Step 1: Write the failing tests.** In `tests/test_repo.py`:

```python
def test_the_readme_installs_the_app_openems_and_the_button_with_real_commands(capsys):  # design 5.6, 7; RF 4
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = readme.split("\n## Install\n", 1)[1].split("\n## ", 1)[0]
    step = "Preferences › Plugins › Enable KiCad API, then restart KiCad"
    assert step in CATALOG["I_PLUGIN_NEXT"] and step in install  # the README quotes the command's own words
    assert r"%LOCALAPPDATA%\kicad-rf-studio\venv" in install  # design 5.6's concrete venv
    assert "run `install-kicad-plugin` again" in install  # Review Focus 4: a moved venv
    # ponytail: code spans and fences only; a command named in prose goes unchecked
    code = "\n".join(re.findall(r"```[^\n]*\n(.*?)```", readme, re.S) + re.findall(r"`([^`\n]+)`", readme))
    named = set(re.findall(r"kicad-rf-studio[\"']? ([a-z][a-z-]*)", code))
    assert {"setup-openems", "install-kicad-plugin"} <= named
    for command in sorted(named):  # each a real subcommand: argparse shows its help and exits 0, else 2
        with pytest.raises(SystemExit) as e:
            main([command, "--help"])
        assert e.value.code == 0, command
    capsys.readouterr()
```

  In `tests/test_button.py`:

```python
def test_install_kicad_plugin_run_again_rewrites_the_launcher_for_the_venv_where_it_now_is(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path))  # the README's "Moved the venv?"; Review Focus 4
    launcher = tmp_path / SEGMENT / "10.0" / "plugins" / "kicad-rf-studio" / LAUNCHER
    for venv in ("old venv", "new venv"):  # where install-kicad-plugin ran, then where the venv is now
        monkeypatch.setattr(sys, "executable", str(tmp_path / venv / "python"))
        button.install("10.0")
    assert b"new venv" in launcher.read_bytes() and b"old venv" not in launcher.read_bytes()
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_repo.py tests/test_button.py -q -k "readme or run_again"`. Expected: the README test FAILs: today's Install section lacks KiCad's step; the rewrite test passes at once: it pins plan 3's installer, which the README's line relies on (it fails if `install` ever stops rewriting an existing launcher).
- [ ] **Step 3: The README.** Everything between the `## Install` line (L5) and the `## Tutorial` line (L21), today's `### Windows` and `### Linux`, becomes this text, with one empty line before and after it; its fenced blocks are the README's own:

````markdown
kicad-rf-studio runs from a virtual environment of its own, `<venv>` below. pip installs it there with its Python dependencies, Qt among them (about 600 MB on disk); openEMS 0.37 comes apart. Until kicad-rf-studio is on PyPI, `<source>` is the source zip of a release on the project's GitHub page, once the project is published there, or a clone of this repository.

### Windows

In PowerShell, on Windows 10 or 11:

1. Install Python 3.14, 64-bit, for your user: with the Python install manager (`py install 3.14`), which needs no admin rights, or from python.org. The openEMS 0.37 wheels for Windows need Python 3.13 or 3.14.
2. Make the venv at `%LOCALAPPDATA%\kicad-rf-studio\venv` and install kicad-rf-studio into it. `$venv` names it in the commands below; a new PowerShell window needs that first line again.

   ```
   $venv = "$env:LOCALAPPDATA\kicad-rf-studio\venv"
   py -3.14 -m venv $venv
   & "$venv\Scripts\python" -m pip install <source>
   ```

3. Unpack the official Windows package of openEMS 0.37 and give its folder, the one that holds `openEMS.exe` and `python\`, to `setup-openems`. It installs the package's openEMS and CSXCAD wheels into the venv, offline, and records the folder.

   ```
   & "$venv\Scripts\kicad-rf-studio" setup-openems "<openEMS folder>"
   ```

4. Install the KiCad button, for KiCad 9.0.7 or later, or 10.x. It writes into each KiCad version's plugins folder and never edits KiCad's settings. Then, in KiCad: Preferences › Plugins › Enable KiCad API, then restart KiCad.

   ```
   & "$venv\Scripts\kicad-rf-studio" install-kicad-plugin
   ```

5. Start the GUI with `& "$venv\Scripts\kicad-rf-studio-gui"`, or from KiCad's PCB editor: select the chain's two end pads and press the kicad-rf-studio button.

### Linux

On Debian 12, Ubuntu 24.04 or Fedora (glibc 2.34 or newer), with the system Python (3.11 or newer):

1. Clone upstream's openEMS-Project at v0.37.0, with its submodules, and install its build dependencies. This is the one step that needs admin rights: the script asks, then installs your distribution's packages with sudo, `python3-venv` among them on Debian and Ubuntu.

   ```
   git clone --recursive --branch v0.37.0 https://github.com/thliebig/openEMS-Project.git
   cd openEMS-Project
   ./scripts/install_deps.sh --install --python
   ```

2. Make the venv at `~/.local/share/kicad-rf-studio/venv`, activate it and install kicad-rf-studio into it:

   ```
   python3 -m venv ~/.local/share/kicad-rf-studio/venv
   source ~/.local/share/kicad-rf-studio/venv/bin/activate
   pip install <source>
   ```

3. With the venv active, build openEMS in the openEMS-Project folder, without sudo, so that its Python bindings land in the venv: `./update_openEMS.sh ~/.local/share/kicad-rf-studio/openEMS --python`. Leave the GUI build on (no `--disable-GUI`): it builds AppCSXCAD.
4. With the venv active, install the KiCad button: `kicad-rf-studio install-kicad-plugin`. Then, in KiCad: Preferences › Plugins › Enable KiCad API, then restart KiCad. A Flatpak KiCad cannot start the button: open the board in the GUI instead.
5. Start the GUI with `kicad-rf-studio-gui`. On a desktop, Qt needs the xcb cursor library: `libxcb-cursor0` on Debian and Ubuntu, `xcb-util-cursor` on Fedora.

### After installing

- **Moved the venv?** The button's launcher holds the path of the venv's Python, written by `install-kicad-plugin`: run `install-kicad-plugin` again from the venv where it now is. Until then the button fails: KiCad 10 shows the shell's error, KiCad 9 nothing.
- **Remove the button:** `kicad-rf-studio install-kicad-plugin --remove` deletes its folder from each KiCad version's plugins folder, and nothing else. Once the venv is gone, delete the `kicad-rf-studio` folder by hand from each `Documents\KiCad\<version>\plugins` (Windows) or `~/.local/share/kicad/<version>/plugins` (Linux).
- **Uninstall:** remove the button, then delete the venv; on Linux, also the openEMS folder `~/.local/share/kicad-rf-studio/openEMS` and the openEMS-Project clone. The folder that holds the venv, `%LOCALAPPDATA%\kicad-rf-studio` or `~/.local/share/kicad-rf-studio`, also holds the settings and the run folders your projects' results point to: delete it only when no project needs them.
````

  In the Tutorial's first paragraph, "Run the commands from the root of the clone with the venv from Install; on Linux, with the venv active, type `kicad-rf-studio` alone." becomes "Run the commands from the root of a clone, or of the unpacked source zip, with the venv from Install. In PowerShell, `<venv>\Scripts\kicad-rf-studio` is `& "$venv\Scripts\kicad-rf-studio"`; on Linux, with the venv active, type `kicad-rf-studio` alone." (the five commands keep their `<venv>\Scripts\kicad-rf-studio CMD ` form, which `test_the_readme_has_a_tutorial` reads).

  Development setup's step 4 becomes "4. Give the venv openEMS as Install says (on Windows, `kicad-rf-studio setup-openems <openEMS folder>`, and `CSXCAD_INSTALL_PATH` set to that folder: the tests import openEMS in this Python, which reads it to find openEMS's DLLs). Without it, the tests marked `openems` are skipped.", and after its step 5 comes: "6. Before a release, run `python tools/release_check.py`: it builds a wheel from git archive of HEAD and checks it, installs it in a fresh venv, starts the GUI there offscreen, checks the KiCad button's plugin.json against KiCad's schemas, and runs the privacy gate's generic rules over the history and the wheel. One real run through the GUI, lpf915 at Draft then its verify, runs with `KRS_E2E_DIR` set to an empty folder outside the repository and openEMS importable (step 4): `python -m pytest tests/test_gui.py -k real_run -s`. It takes about lpf915's Draft run plus its verify, and its cost line prints the estimate first; a file named STOP in its newest run folder stops it."
- [ ] **Step 4: The spec.**
  - In §3.4's Windows bullet, the lead line "  - Install steps:" becomes "  - Install steps, as the README gives them:", and its three numbered lines become these four:

```
    1. `py -3.14 -m venv "%LOCALAPPDATA%\kicad-rf-studio\venv"`: a venv of the app's own, in its per-user data folder (§3.3);
    2. `pip install <source>`: a tagged release's source zip on GitHub once the repository is published, or a clone until then (publishing on PyPI is an open item, §12);
    3. `kicad-rf-studio setup-openems <openEMS dir>`;
    4. `kicad-rf-studio install-kicad-plugin` (§3.2), then, in KiCad, Preferences › Plugins › Enable KiCad API and a restart. No installer script wraps these steps in Stage 2. (A-21, Stage 2 plan 4: controller recommendation, owner unavailable.)
```

  - §3.4's Linux bullet gains, after its openEMS line: "  - The README's steps clone upstream's openEMS-Project at v0.37.0 and run its `install_deps.sh` first, the one step that needs admin rights; then they make the venv at `~/.local/share/kicad-rf-studio/venv`, build openEMS into `~/.local/share/kicad-rf-studio/openEMS` with that venv active and without sudo, and end with `kicad-rf-studio install-kicad-plugin`, as on Windows. (A-21, Stage 2 plan 4: controller recommendation, owner unavailable.)"
  - §12's row "| Publishing on PyPI, and under which account | The owner, after the first push. Until then, install from a clone |" becomes "| Publishing on PyPI, and under which account | The owner, after the first push. Until then, install from a tagged release's source zip on GitHub, once the repository is published, or from a clone (A-21, Stage 2 plan 4: controller recommendation, owner unavailable) |".
  - The Status sentence becomes " On 2026-10-28, Stage 2's plan 4 amended §3.4, §3.6, §9.1 and §12 (A-19 to A-21) the same way."
- [ ] **Step 5: Run them again.** `.venv/Scripts/python -m pytest tests/test_repo.py tests/test_button.py -q`. Expected: PASS (the Tutorial and licence tests included).
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add README.md tests/test_repo.py tests/test_button.py docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs: the README installs the app, openEMS and the KiCad button on Windows and Linux, checked against the CLI; spec A-21 (Stage 2 design 5.6, 7; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 6 [run]: The controller's checks and the Stage 2 exit record

This task commits only the exit record (Step 9), its follow-up, and the fixes Step 8 may need. Every other file it makes is under `$env:TEMP`, outside the repo. It never starts KiCad, and never touches a real KiCad folder, the real Documents folder, KiCad's settings or the real data folder. The PowerShell tool keeps no variable between calls, so every block below sets what it uses; run each as one call. The openEMS package folder of Steps 3 and 6 is the openEMS 0.37 folder the dev venv was set up from: the controller types it in each call that needs it, and it is never written into a committed file.

- [ ] **Step 1: The full suite at the branch tip,** once, in the background, waited on. Expected: all pass (about 1730 passed and 5 skipped). Record the counts for §5.11 item 1.
- [ ] **Step 2: The release check, locally,** with the default TEMP (a deeper one overflows Windows' 260-character paths: Task 2's ponytail note), in the background, waited on; it takes a few minutes: `.venv\Scripts\python.exe -X utf8 tools\release_check.py *> "$env:TEMP\krs-plan4-release.log"; "exit $LASTEXITCODE" | Add-Content "$env:TEMP\krs-plan4-release.log"`. Expected, in the log: `PASS build`, `PASS install`, `PASS gui`, `PASS plugin`, then `PASS privacy` naming the history and the wheel, clean under the generic rules; no `NOTE` line; `exit 0`. A privacy FAIL is a leak to fix before anything else (its hit lines name a commit, a file and a generic rule, never the matched text).
- [ ] **Step 3: The README's Windows steps, as written, isolated.** One call; it takes a few minutes:

```powershell
$iso = Join-Path $env:TEMP 'krs-plan4 readme é'
Remove-Item -Recurse -Force $iso -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$iso\local", "$iso\docs\KiCad\9.0", "$iso\docs\KiCad\10.0", "$iso\board" | Out-Null
Copy-Item tests\fixtures\lpf915.kicad_pcb "$iso\board\"
git archive --format=zip --prefix=kicad-rf-studio/ -o "$iso\source.zip" HEAD  # what GitHub serves as a release's source zip
$env:LOCALAPPDATA = "$iso\local"; $env:XDG_DATA_HOME = "$iso\local"; $env:KICAD_DOCUMENTS_HOME = "$iso\docs"
$env:KICAD_CONFIG_HOME = "$iso\config"; $env:KICAD_API_SOCKET = "ipc://$env:TEMP\krs-plan4-none.sock"
Remove-Item Env:KICAD_API_TOKEN -ErrorAction SilentlyContinue
if ($env:LOCALAPPDATA -ne "$iso\local" -or $env:KICAD_DOCUMENTS_HOME -ne "$iso\docs") { throw 'not isolated' }
$venv = "$env:LOCALAPPDATA\kicad-rf-studio\venv"
py -3.14 -m venv $venv
& "$venv\Scripts\python" -m pip install "$iso\source.zip"
& "$venv\Scripts\kicad-rf-studio" setup-openems "<openEMS folder>"
& "$venv\Scripts\kicad-rf-studio" install-kicad-plugin
```

  Expected: pip's install ends without an error; `Installed openEMS 0.37.… and CSXCAD 0.7.… from …; the folder is recorded in …\krs-plan4 readme é\local\kicad-rf-studio\settings.json.`; two `Installed the kicad-rf-studio button in …` lines (9.0 and 10.0) and the `One step is left, in KiCad: …` line. Lines 10–14 are the README's step 2, 3 and 4 commands, with `<source>` the archive; a README command that does not run as written is a Task 5 defect (Step 8). Line 11's `py` runs after LOCALAPPDATA moved: here it is the legacy launcher, which finds Python 3.14 through the registry (probed); with the Python install manager's `py`, whose runtimes sit under the real LOCALAPPDATA, read `$py = py -3.14 -c "import sys; print(sys.executable)"` before line 6 and run line 11 as `& $py -m venv $venv`.
- [ ] **Step 4: Replay that install's launcher** (§5.11 item 3, as plan 3's Task 7 did, now with the venv the README makes). Write `replay.py` into `$env:TEMP\krs-plan4-replay` (made with `New-Item -ItemType Directory -Force`). It is plan 3's Task 7 script but for three changes: the socket's path as a third argument, the launcher's text recorded, and KiCad's folders and matplotlib's isolated too (plan 3's ruling "agents and the owner's KiCad"):

```python
# replay.py: the controller's replay of the README-installed launcher (Stage 2 plan 4, Task 6), never committed. Run
# with the dev venv's pythonw.exe, which has no console, as KiCad starts an action: KiCad 10 with pipes, KiCad 9
# without.
import json, os, subprocess, sys, time
from pathlib import Path

repo, iso, sock = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(repo / "tests"))
from fake_kicad import FakeKiCad  # noqa: E402
from kicad_rf_studio.core.kicad import load_board  # noqa: E402

board = iso / "board" / "lpf915.kicad_pcb"
kiid = {p.name: p.uuid for p in load_board(board).all_pads()}
plugin = iso / "docs" / "KiCad" / "10.0" / "plugins" / "kicad-rf-studio"
k = FakeKiCad(f"ipc://{sock}", board, pads=[kiid["U1.1"], kiid["J1.1"]], version=(10, 0, 7))
env = {**os.environ, "KICAD_API_SOCKET": k.url, "KICAD_API_TOKEN": k.token, "LOCALAPPDATA": str(iso / "local"),
       "XDG_DATA_HOME": str(iso / "local"), "MPLCONFIGDIR": str(iso / "local"),
       "KICAD_DOCUMENTS_HOME": str(iso / "docs"), "KICAD_CONFIG_HOME": str(iso / "config"), "QT_QPA_PLATFORM": "offscreen"}
hide = subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0)  # wxEXEC_HIDE_CONSOLE
result = {"launcher": (plugin / "launch.cmd").read_bytes().decode("oem")}
for press, pipes in (("kicad10", True), ("kicad9", False)):
    begin = time.monotonic()
    p = subprocess.Popen([str(plugin / "launch.cmd")], cwd=plugin, env=env, startupinfo=hide,
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if pipes else None,
                         stderr=subprocess.PIPE if pipes else None)
    try:
        out, err = p.communicate(timeout=30)  # KiCad 10 reads both pipes only once the action ends
    except subprocess.TimeoutExpired:  # a launcher that hangs: its whole tree goes, and its press says so
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        out, err = p.communicate()
    result[press] = {"code": p.returncode, "seconds": round(time.monotonic() - begin, 2),
                     "stdout": (out or b"").decode("utf-8", "replace"),
                     "stderr": (err or b"").decode("utf-8", "replace")}
    time.sleep(8)  # the first press's GUI starts and listens before the second press comes
result["seen"] = k.seen
k.close()
(iso / "replay.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
```

  Then, as one call (`Start-Process -Wait` would wait for the GUI the replay starts, so the replay is waited on by its own process):

```powershell
$iso = Join-Path $env:TEMP 'krs-plan4 readme é'
$script = Join-Path $env:TEMP 'krs-plan4-replay\replay.py'
$p = Start-Process -PassThru -FilePath .venv\Scripts\pythonw.exe -ArgumentList @("-I", "`"$script`"", "`"$PWD`"", "`"$iso`"", "`"$env:TEMP\krs-plan4-api.sock`"")
$p.WaitForExit(180000) | Out-Null
Get-Content "$iso\replay.json"
Get-Content "$iso\local\kicad-rf-studio\handoff.json"
$gui = Get-CimInstance Win32_Process -Filter "Name = 'kicad-rf-studio-gui.exe'" | Where-Object { $_.ExecutablePath -like '*\krs-plan4 readme é\*' }
"gui processes: $(@($gui).Count)"
"button.log: $(Test-Path "$iso\local\kicad-rf-studio\button.log")"
Get-Content "$iso\local\kicad-rf-studio\gui.log" -ErrorAction SilentlyContinue
```

  A missing `replay.json` means the script failed: run it again with `.venv\Scripts\python.exe` in place of `pythonw.exe` to see its traceback. Then check:
  - `replay.json`: `launcher` names the README venv's `python.exe` under `krs-plan4 readme é`; both presses `code` 0; `kicad10`'s `stdout` and `stderr` empty and `seconds` under 2; `seen` is `GetVersion`, `GetOpenDocuments`, `GetSelection`, twice.
  - `handoff.json`: the board under `krs-plan4 readme é\board`, the KIIDs of U1.1 and J1.1, `"kicad": "10.0.7"`, the socket and the token `"K"`.
  - `gui processes: 1`: the README venv's GUI started detached and outlived both launchers; the second press forwarded to it.
  - `button.log: False`, and `gui.log` empty or missing.
- [ ] **Step 5: Close it and clean up,** as one call. Only programs that live in this task's folder are stopped, each with its tree (the README venv's GUI launcher and the interpreters under it); this shell and every other process stay:

```powershell
$iso = Join-Path $env:TEMP 'krs-plan4 readme é'
Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*\krs-plan4 readme é\*' } | ForEach-Object { taskkill /T /F /PID $_.ProcessId 2>$null | Out-Null }
Remove-Item -Recurse -Force $iso, (Join-Path $env:TEMP 'krs-plan4-replay')
```

- [ ] **Step 6: The real run through the window** (§5.11 item 2). If `$env:TEMP\krs-font\krs_font.py` is gone, write it again as plan 3's Task 7 Step 5 gives it whole. Then, in the background, waited on (it takes about lpf915's Draft run plus its verify):

```powershell
$e2e = Join-Path $env:TEMP 'krs-plan4-e2e'
Remove-Item -Recurse -Force $e2e -ErrorAction SilentlyContinue
$env:KRS_E2E_DIR = $e2e; $env:KRS_GRAB_DIR = "$env:TEMP\krs-grabs-plan4"; $env:PYTHONPATH = "$env:TEMP\krs-font"
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"  # where this Python and its workers load openEMS's DLLs from
"src $(git rev-parse HEAD:src)" > "$env:TEMP\krs-plan4-e2e.log"
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_gui.py -k real_run -s -q -p krs_font *>> "$env:TEMP\krs-plan4-e2e.log"
```

  Read the log's `e2e cost:` line as soon as it appears: its `Worst case:` (and a prediction, when there is one) is the estimate the record compares with the measured times. Expected at the end: `1 passed`, with the lines `e2e new`, `e2e cost`, `e2e run` (the jobs' verdicts and the run's last log line), `e2e verify` (I_VERIFY_RESULTS and I_VERIFY_COMPARE's lines), each with `<KRS_E2E_DIR>` for the folder. `1 skipped` means openEMS did not import in the dev venv: check `CSXCAD_INSTALL_PATH`. A run or a verify that ends with another exit code is a finding for the record, with its run folder's events; it is not retried at another preset. To stop it early, only the app's own Stop is used: `New-Item -ItemType File (Join-Path (Get-ChildItem "$env:TEMP\krs-plan4-e2e\data\kicad-rf-studio\runs" -Directory | Sort-Object Name | Select-Object -Last 1).FullName STOP)`, which aborts the jobs within `ABORT_WAIT_S` (60 s) and writes the run's end event; the test then fails on that end, and its `finally` cleans up. Never kill python.exe or openEMS by name: they may be the owner's.
- [ ] **Step 7: Look at the four PNGs** in `$env:TEMP\krs-grabs-plan4` with the Read tool: `e2e-cost` (the 2D readout, the setup cost, Worst case, Run… enabled), `e2e-run` (one row per job with its verdict, the end state), `e2e-retune` (C2 at 5.1pF on E24, the curves under the what-if label), `e2e-verify` (verify's comparison beside the retuned result, the stale indicator hidden). Every word is the catalog's, legible and unclipped; a word-wrapped label's old height in a grab is an artifact of `grab()` (plan 1).
- [ ] **Step 8: Fix what fails.** Each defect becomes a [code] fix in the owning task's file, test-first where a test can see it, committed as `fix(...)` after the full suite; then the failing step runs again.
- [ ] **Step 9: The Stage 2 exit record,** `docs/validation/<date>-stage2-exit.md`, `<date>` the day it is written, modelled on Stage 1's (`docs/validation/2026-10-25-stage1-exit.md`), Markdown only. No line names a path outside the repo: the e2e lines are quoted as printed, and Step 4's facts are written with the replay's folder as `<iso>` (its launcher's Python as `<iso>\local\kicad-rf-studio\venv\Scripts\python.exe`), never pasted from `replay.json` or `handoff.json`.
  1. **Verdict:** one bold line first, as Stage 1's: Stage 2 done or not by §5.11's items 1 to 3, item 4 the owner's and not blocking. Then one table, one row per §5.11 item: 1 plans merged and the suite green (the counts of the last full-suite run; the merge is fast-forward, so they hold for main); 2 the real run (holds or not, with its `e2e` lines and the product code id at the head of its log); 3 the launcher replayed (Step 4's facts); 4 the owner's click-through (the owner's, not blocking).
  2. **Inputs:** the branch, its HEAD, the product code id (`git rev-parse HEAD:src`), plans 1 to 3 and their merge commits (`d0b4582`, `a6bf7e7`, `06c2a81`), plan 4's base `06c2a81` and the record's parent commit (plan 4's own merge follows the record), the design.
  3. **The release check, run locally:** its five lines as printed.
  4. **The README, followed:** the Windows steps as Step 3 ran them, from the source zip, with setup-openems and install-kicad-plugin; the Linux steps not followed by any agent: after the push, release-check.yml covers the wheel, its install, the GUI and the plugin on Linux at the floor, and the README's Linux steps themselves (install_deps, the openEMS build, the venv in `~/.local/share`) stay the owner's, or P0-D's containers'.
  5. **Stated limits and deviations:** push-gated and never run (release-check.yml, ci.yml's tier (a) on GitHub, tiers (b) and (c), P0-D); the Linux-only tests; `RETUNE_VALIDATED` False, so the what-if label stays (§7.6); the run at Draft; what only the click-through shows (plan 3's list); the release check reads no private list (the hooks do); the known limits in plans 1 to 3's records ("Deferred minors and known limits"), one line each.
  6. **Machine time:** cost (its calibration included), the run and the verify, measured against cost's estimate; the release check's wall time.
  7. **Next step, the owner's items,** one table as Stage 1's §7, each with the default this work applied: the plugin identifier and folder name (`org.kicadrfstudio.app`); the GUI saving the board through the API (only the confirmed refill-and-save); cost before every run (always shown, a matching cost reused); the snapping series (E24 for L and C, per part); PySide6 as a core dependency (yes); the what-if wording (§7.6's text, pointing to Verify); the install source before PyPI (a GitHub release's source zip after the push) and the README's release link once a release exists; a one-command installer (none in Stage 2); the review of A-13 to A-21, each a controller recommendation; the identity rewrite and the deny-list review; the first push, then the workflows; PyPI; the click-through on KiCad 9.0.7 and 10.x; the once-per-release clean-machine run of the Windows steps (Windows Sandbox); the README's Linux steps on a real distribution; P0-C; the engine redesign (A-9, A-10, r3's X-A run); RFsim/NOTICE; the v1 time policy; a tag-equals-version check with the first tag; a protobuf floor if a shared venv is ever met (ruling).

```bash
git add docs/validation/<date>-stage2-exit.md
git commit -m "docs(validation): the Stage 2 exit record: what holds of design 5.11, with its evidence, and the owner's items"
graphify update .
```

  Then delete `$env:TEMP\krs-plan4-e2e`, `krs-grabs-plan4` and the two logs. Any commit after the record, the whole-branch review's included, runs Step 1 again, and Steps 2 and 4 too when it changes anything under `src` or `tools`; a follow-up commit brings the record's sections 1 to 3 up to date before the merge. Step 6 is not run again for it: item 2 names the product code id the real run ran at.

---

## Not in this plan

- **The owner's click-through** on a real KiCad 9.0.7 and 10.x (design §5.11 item 4), with everything plan 3 lists that only it shows; it does not block.
- **The first push, PyPI and a GitHub release** (design §4, §7): `release-check.yml`, ci.yml's tiers and P0-D first run after the push; until a release exists the README's `<source>` is a clone or a source zip.
- **An installer script, a bundled or PyInstaller build, a Start-menu shortcut** (design §3, §7): none in Stage 2. LGPL's conveying duties would start with the bundled build (A-19).
- **An sdist:** it waits for PyPI (r3); the release check builds the wheel only, from `git archive` of HEAD, which is what a GitHub source zip holds and what the history scan covers.
- **A tag-equals-version check** (r3 item 7): the version scheme of a release is the owner's; add it with the first tag. The wheel's inspection reads no version either: setuptools writes pyproject's.
- **The private list in the release check:** the pre-commit and pre-push hooks run it on every commit and push (Stage 1 §9.1); the release check runs the gate's generic rules, as CI does (ruling).
- **A `protobuf>=5.29.6` floor in `pyproject.toml`:** a ruling; the README's venv of its own and the release check's import cover the install it describes.
- **Every transitive package in NOTICE and About:** a ruling; one sentence covers them.
- **A clean-machine run of the Windows steps** (Windows Sandbox: the openEMS package's VC++ runtimes, r3 item 8): the owner's, once per release.
- **KiCad's real plugin loader in tier (c)** (`kicad-cli` with KICAD_API tracing, r3's option): plugin.json is checked against the tagged schemas and kicad-python's validator here, and loaded by a real KiCad in the click-through.
- **Offscreen fonts in the release check:** its GUI step takes no grab. Review grabs keep plan 3's scratch font plugin (plan 1 and plan 2 named fonts for this plan).
- **The README's Linux steps run by an agent:** no Linux machine here. After the push, release-check.yml runs the wheel, its install, the GUI and the plugin on Linux at the floor; the steps themselves stay the owner's, or P0-D's containers'.
- **macOS, Flatpak KiCad's button, the pt-BR catalog:** design §3 and §5.7.

## Controller rulings (2026-10-28; binding)

The architect's rulings, revised after the four reviews (coverage, feasibility checked by running the build, the fresh venv and the schema fetch, safety and privacy, quality). Each is a controller recommendation, owner unavailable.

- Ruling: six tasks: NOTICE (1), the release check (2), its workflow (3), the opt-in real run (4), the README (5) and the controller's run with the exit record (6). The README comes last so that it names the release check and the real-run test once both exist; the workflow is its own task, a reviewer being able to pass the script and reject the CI file — cost if wrong: one more review gate.
- Ruling: NOTICE's runtime list is `control.DEPENDENCIES`, the same 15 names and licence strings in the same order, pinned by a test beside About's in `tests/test_gui_control.py`, which also pins the LGPL sentence and nothing else of the text — one list for About and NOTICE (r3, plan 3's carry-over); NOTICE stays hand-written text — cost if wrong: a row in both, which the test keeps together.
- Ruling: the deeper packages (attrs, cffi, pycparser, referencing, rpds-py, jsonschema-specifications and sniffio, which kicad-python's dependencies bring, like matplotlib's and pandas' own) are not listed: NOTICE says pip installs what these depend on, each under its own licence, which `pip show <name>` names — plan 2's About lists the packages the app or its direct dependencies name, the transitive set changes with pip's resolution and the platform, none is conveyed, and every one named is permissive — cost if wrong: rows in `DEPENDENCIES`, and NOTICE follows through its test.
- Ruling: LGPL's conveying duties are stated in NOTICE and in Stage 1 §3.6 (A-19) as starting only with a build that bundles Qt, which §10 defers — design §5.6 and r3 R-6 — cost if wrong: none.
- Ruling: `tools/release_check.py` is one script of the standard library, `privacy_gate` and, inside `plugin_problems` only, jsonschema (kicad-python brings it, so the dev venv has it, and the workflow installs it at kicad-python's pin). It prints plain English, as `privacy_gate.py` does: a release tool's lines are not the app's, so no catalog code — cost if wrong: its lines are not translatable, which no user reads.
- Ruling: five steps, each a function `(tmp) -> (status, detail)` that `main` prints as one line; a step whose `NEEDS` did not pass is SKIPPED, a step that raises is its own FAIL, `main` exits 1 on any FAIL; steps share files in the one temporary folder, not state. Privacy needs nothing, so it scans the history even when the build fails. `main` is given whole, since its test leaves its stdout handling, the folder's resolve and its cleanup open — cost if wrong: none.
- Ruling: the temporary folder is one `TemporaryDirectory(prefix="krs release é ", ignore_cleanup_errors=True)`, resolved because TEMP may be an 8.3 short path, which `venv` warns about (probed); a folder it cannot remove (a file a process still holds) is named on a last `NOTE` line, by its name only; the space and the accent put every step under the path a Windows user name gives (Review Focus 1). Everything is inside it but pip's own cache and build folders, which pip manages. No long-path handling: under the default TEMP the deepest paths stay well inside Windows' 260 characters, and a TEMP deeper than about 120 characters fails visibly in the venv (probed from a deep scratch folder) — cost if wrong: a user with a deep TEMP sets a shorter one for the run, as the ponytail note says.
- Ruling: the build runs `git archive --format=zip` of HEAD and `pip wheel --no-deps` from that zip (build isolation fetches `setuptools>=77`), and takes the sources from `git ls-tree` of HEAD — design §5.6's "build from a clean clone" is HEAD's tracked tree, never the working tree with its ignored `build/` (r3), and the archive is that tree as GitHub serves a release's source zip, §7's install source; it leaves no read-only git packs in TEMP, and a HEAD on no branch builds too. Probed under an accented path: 4 to 19 s, 48 package files and the 8 dist-info files, nothing else — cost if wrong: the archive's text files follow `core.autocrlf` (CRLF on this machine), which the wheel keeps and Python and JSON read alike.
- Ruling: the wheel's inspection is its member set: exactly HEAD's tracked `src/` files and `DIST_INFO` in the `.dist-info` named from the wheel's own file name. METADATA, `entry_points.txt` and the licence files' bytes are setuptools' translation of `pyproject.toml`, which the install step exercises (pip resolves `Requires-Dist`, both entry points must exist, the plugin step runs the console script), so they are not compared again; no version is read (the tag-equals-version check is the owner's, with the first tag) — r3 §4 item 3 asks for the members and both entry points — cost if wrong: a setuptools that adds a dist-info file fails the build step until `DIST_INFO` names it (ponytail note); a METADATA field the install does not exercise goes unchecked.
- Ruling: the fresh venv is `python -m venv` from the Python running the check; pip installs the wheel with its own cache (pip's, not this check's, so a second run downloads little), then `pip check`, then `python -I -c "import kipy.board_types"`, then the gui-scripts entry must exist — plan 3's carry-over: pip check passes on a protobuf its protos refuse; probed: about 45 s, 582 MB, protobuf 5.29.6. This guards a bad resolution at release time; a user's shared venv is the README's to avoid (Review Focus 2) — cost if wrong: none.
- Ruling: the GUI step runs `gui.main([])`, the gui-scripts entry's own function, in the fresh venv under `isolated(tmp)`, with a zero-delay timer that closes a visible main window, or exits 3 when none showed; its data folder, and so its `gui.lock` and its local server's name, are the temporary folder's, so it can never forward to a window the owner has open. The `.exe` itself cannot be told to close — probed: exit 0 in about 9 s, the main window shown, then closed — cost if wrong: the launcher `.exe` itself is exercised only by Task 6's replay (ponytail note).
- Ruling: the plugin step runs the fresh venv's `kicad-rf-studio install-kicad-plugin --kicad 10.0` into the temporary folder's documents (9.0's files are the same), then `kicad-python-packager validate`, KiCad's schema at each tag, the identifier rules and the launcher's executable bit (KiCad's click-time `IsFileExecutable`) — the wheel as a user gets it, end to end; probed in a throwaway venv — cost if wrong: none.
- Ruling: KiCad's schemas are fetched at run time from gitlab's raw files at `SCHEMA_TAGS = ("9.0.7", "10.0.7")`, KiCad's floor and its newest 10.0 release, never vendored: a vendored KiCad file would need its own NOTICE entry, and tier (c) fetches KiCad's demo boards the same way (r3). Probed: 9.0.7, 9.0.9.1, 10.0.7 and 10.0.8-rc1 are byte-identical; master adds `args` and the `footprint_wizard` scope (so `go.kicad.org`'s redirect to master is never used); kipy's bundled copy is 10.0.7's plus that scope. A failed fetch is the step's FAIL — cost if wrong: an offline or rate-limited run, a GitHub runner's included, fails its plugin step until the files are vendored with a NOTICE entry (ponytail note).
- Ruling: the identifier rules move from `tests/test_button.py` into `release_check.IDENTIFIER_RULES` (KiCad 9.0.7's unanchored regex, 10.0.7's anchored one, and design §5.5's own), and test_button's test calls `identifier_problems` — one copy, which the release check and the owner's final identifier share — cost if wrong: test_button imports a tool, as `test_privacy_gate` already does.
- Ruling: the privacy step runs the gate's own script as `ci.yml` does, `--all --generic-only` under `-X utf8`, and its `_scan_file` over each wheel member with no private list, `tools/privacy_allow.txt` read as `src/` plus the member's name (probed: without that, `smooth.py`'s licence header would hit). The gate's exit code must agree with its output: exit 1 with no hit line is a gate that never scanned (a git call that failed, or a crash), so that FAILs with the gate's own stderr line, as any other exit code does, and a tier (a) test pins all three outcomes. Stage 1 §9.1 keeps the private list with the hooks, which run it on every commit (pre-commit, never `--no-verify`) and every push, and CI repeats only the generic rules; a check that read the list would flag the owner's identity in commit headers until the rewrite, and the classifier that excused it (with its `deny#<n>` lines, a set-but-unusable list read as none, and a root file named `commit` read as a header) was what the reviews found fragile. Probed: the history is clean under the generic rules (35 s), and the built wheel is clean — cost if wrong: a private name that slipped past both hooks reaches a local release check unseen; the pre-push hook still refuses it (open issue for the owner: r3's literal form, the list and any hit failing, is the upgrade).
- Ruling: `release-check.yml` runs on a pushed `v*` tag and by hand, never on a branch push, on windows-latest with Python 3.14 (the README's) and on ubuntu-24.04 at the declared floor, 3.11 (Debian 12's Python, which the README's Linux steps allow; kicad-python adds typing_extensions below 3.13), the whole history checked out with no token kept in it, `ci.yml`'s offscreen Qt packages on Linux (a test keeps the two lines equal), jsonschema at kicad-python's pin, then the script — design §4: push-gated, written now; too slow for the pre-push hook (r3) — cost if wrong: the first tag's run finds what Linux needs.
- Ruling: §5.11 item 2's real run is a committed opt-in test, `test_one_real_run_through_the_window_new_cost_run_retune_apply_verify` in `tests/test_gui.py`, skipped unless `KRS_E2E_DIR` names a folder and marked `openems`, never run by the suite (skipped) or the release check (it never calls pytest). The owner can run it again before a release, and it is reviewed code beside the helpers it uses, where a scratch script would be lost with the session. Its steps mirror the fake-backed tests' assertions, which run in every suite; no fake dry run of the sequence is added — cost if wrong: one more skip in the suite; a test that only runs by hand can lag the window's API until it is next run (ponytail note), and a wrong assertion after the run costs the run again.
- Ruling: the real run uses the real orchestrator and a fresh data folder, `KRS_E2E_DIR/data`, so cost calibrates as on a new install. `KRS_E2E_DIR` must lie outside the repository (its `settings.json` names this host and is not git-ignored) and be empty, and the QApplication must be offscreen; it patches `run_jobs` and `ensure_calibrated` to fail in its own process, waits on the watched process (`proc.poll()`) and then the tick that reads its end event, never on a status text, so a failing run ends the test at once. It prints one line per step with its time, cost's lines first, with `KRS_E2E_DIR` shown as `<KRS_E2E_DIR>`, grabs four PNGs when `KRS_GRAB_DIR` is set (cost's after the re-read that enables Run…), and cleans up through `dispose()`, which the `window` fixture's teardown shares. openEMS's DLLs come from `CSXCAD_INSTALL_PATH`, which Task 6 sets in the same call (a README install records the folder in `settings.json`, which a fresh data folder lacks); it is stopped early only by a STOP file in its newest run folder, the app's own Stop. Its retune is C2 typed 5pF and snapped to 5.1pF (E24, design §7's default), then Apply, then Verify on the applied values, as the fake-backed tests do — cost if wrong: none.
- Ruling: the README's Windows steps are PowerShell with full paths, `$venv` set once, and no `Activate.ps1`, which Windows' default execution policy blocks; Python 3.14 64-bit for the user, the Python install manager named first, which needs no admin rights (r3: the README does not lean on the classic installer's options); `<source>` is the GitHub release's source zip once published, else a clone (design §7); KiCad's step is `I_PLUGIN_NEXT`'s own words; the Tutorial says what `<venv>\Scripts\kicad-rf-studio` is in PowerShell. "Moved the venv?", "Remove the button" (by hand once the venv is gone) and "Uninstall" close the section, the last naming the run folders that sit beside the venv in the data folder — design §5.6, r3 §3 — cost if wrong: a cmd user retypes `$venv` as `%venv%`.
- Ruling: the README's Linux steps clone upstream's openEMS-Project at v0.37.0 with `--recursive` (upstream's own documented clone), run `install_deps.sh --install --python` first, the one step that needs admin rights (it asks, then installs the distribution's packages with sudo, `python3-venv` among them on Debian and Ubuntu, which the venv then needs), make the venv at `~/.local/share/kicad-rf-studio/venv` with `source …/activate`, and build openEMS into `~/.local/share/kicad-rf-studio/openEMS` with the venv active and never with sudo (sudo drops the active venv, so upstream's script would make its own and the bindings would miss the app's) — read from upstream's v0.37.0 scripts — cost if wrong: unverified on Linux until the owner or P0-D's containers follow them.
- Ruling: the README's drift check reads every `kicad-rf-studio <command>` in the README's code, fenced or inline, and requires `kicad-rf-studio <command> --help` to exit 0 — public argparse behaviour, not its private actions — and pins only what guards something: KiCad's step quoted from `I_PLUGIN_NEXT`, design §5.6's concrete Windows venv, the moved-venv line (Review Focus 4), and `setup-openems` and `install-kicad-plugin` among the commands; the rest of the README's text is not copied into the test. Probed: the README's seven commands; an unknown one exits 2 — cost if wrong: prose outside code is unchecked (ponytail note).
- Ruling: Task 6 follows the README's Windows steps into an isolated `LOCALAPPDATA` and `KICAD_DOCUMENTS_HOME`, installing from `git archive` of HEAD, which is what GitHub serves as a release's source zip (probed: pip installs it), with setup-openems from the owner's openEMS package recording it in the isolated data folder; `py -3.14` there finds Python through the registry after LOCALAPPDATA moved (probed). It replays that venv's own launcher with KiCad's folders, the data folder and matplotlib's isolated (plan 3's ruling "agents and the owner's KiCad"), so §5.11 item 3 runs on the install a user gets, under a path with a space and an accent; the fake KiCad's socket sits outside that path, so nng's pipe name is not what gets tested. Its cleanup stops only programs that live in that folder, each with its tree — cost if wrong: none.
- Ruling: the exit record is Markdown only (nothing reads a JSON beside it), written and committed by the controller on the branch before the whole-branch review, with a one-line verdict first, as Stage 1's. Any later commit reruns the suite (and the release check and the replay for a change under `src` or `tools`), and a follow-up commit brings sections 1 to 3 up to date; the real run is not rerun for it, its product code id being recorded. Its inputs name plan 4's base and the record's parent, since plan 4's merge follows it; the merge is fast-forward, so its suite counts hold for main. It names no path outside the repo (the e2e lines print `<KRS_E2E_DIR>`, the replay's folder is `<iso>`), gives the privacy gate's outcome without a count or a pattern index, and lists every open owner item with the default this work applied — design §5.11, §7, Stage 1's model — cost if wrong: a record a commit older than the merge.
- Ruling: no `protobuf>=5.29.6` floor — the README's venv of its own and the release check's import cover the install it describes, and a direct pin would amend §3.4's dependencies — cost if wrong: a user who installs into a shared venv holding protobuf 5.29.0 to 5.29.5 gets E_INTERNAL naming the protobuf error at the button; the floor is one line then.
- Ruling: amendments A-19 (§3.6, Task 1), A-20 (§9.1's tier (d), Task 3) and A-21 (§3.4's install steps and Linux bullet, and §12's PyPI row, Task 5), numbered in commit order from A-19 (plan 1 took A-13 to A-15, plan 3 A-16 to A-18), with one Status sentence that later tasks widen — design §5.10 — cost if wrong: none.
- Ruling (disclosure, the architect): the architect ran only read-only probes, in a scratch folder: a clean clone at `06c2a81`, its wheel built with `pip wheel --no-deps` and inspected; a throwaway venv under a path with a space and an accent, the wheel installed there, `pip check`, the kipy import, the exact `SMOKE` code offscreen with isolated data and cache folders, `install-kicad-plugin --kicad 10.0` into an isolated documents folder, `kicad-python-packager validate`, both tagged schemas through jsonschema and a `git archive` zip installed by pip; KiCad's schema at 9.0.7, 9.0.9.1, 10.0.7, 10.0.8-rc1 and master; gitlab's tag list; the identifier rules on six identifiers; jsonschema 4.26's messages; the privacy gate over the history and the wheel, reported only as clean or not apart from the identity; a launcher whose Python is gone (cmd exits 1 with its own line); `TemporaryDirectory` removing a clone; argparse's `--help` exit codes. It then applied the draft's Tasks 1 to 5 to a scratch clone and ran their tests there, and ran that clone's `release_check.py` whole: five PASS lines and exit 0 in about 107 s, once its folder was given in 8.3 form. No full suite, no openEMS, no KiCad, no visible window, nothing written in the repo or its venv — cost if wrong: none.
- Ruling (disclosure, the reviser): the reviser, read-only too, in a scratch clone at `06c2a81`: a wheel from `git archive` of HEAD under a path with a space and an accent (about 4 s; 48 package files and 8 dist-info files; the revised `inspect_wheel` empty, `wheel_hits` clean); the revised `build` and `privacy` steps run whole on the clone (both PASS, the folder removed); the gate's generic rules over the repo's history (exit 0, 35 s); `py -3.14` with LOCALAPPDATA moved; upstream's v0.37.0 `install_deps.sh`, `update_openEMS.sh` and `build_python.sh` read; the CSXCAD package's DLL lookup (`CSXCAD_INSTALL_PATH`, else `OPENEMS_INSTALL_PATH`); this revision's Tasks 1 to 5 applied to the clone and their tests run there with the dev venv's Python (test_repo, test_gui_control, test_release_check and test_button: 92 passed, 1 skipped; test_gui: 31 passed, 2 skipped, the real run among the skips); the changed files clean under the gate's generic rules. No install-kicad-plugin, launcher or GUI outside pytest, no openEMS run, no KiCad, no full suite — cost if wrong: none.
- Ruling (the reviser's open issue 1): the release check keeps the privacy gate's generic rules only, as ruled above; the private list stays with the pre-commit and pre-push hooks (Stage 1 §9.1). r3's literal form, the list read and any hit failing, is the owner's upgrade, and the exit record lists it among the owner's items — cost if wrong: a private name that slipped past the pre-commit hook is caught by the pre-push hook, not by a local release check.
- Ruling (open issues 2 and 3): what is push-gated or needs Linux stays unverified until the owner's first push or a real distribution: `release-check.yml` on both runners, `ci.yml`'s apt line there, the schema fetch from a GitHub runner, the fresh venv at 3.11, and the README's Linux steps. The exit record states each as a limit and lists it as an owner item; vendoring both schema files with a NOTICE entry stays the fallback the ponytail note names — cost if wrong: the first tag's run finds it.
- Ruling (open issue 4): no fake dry run of the real run's sequence. Its assertions mirror the fake-backed tests, which run in every suite, and cost's estimate, read first, says how long the run and its verify take; a wrong assertion after the run costs that machine time once more, not the owner's time: Step 8 fixes it test-first where a fake-backed test can see it, `KRS_E2E_DIR` is emptied, and Step 6 runs again — cost if wrong: one more Draft run and verify.
- Ruling (open issue 5): the README's Windows step 1 stands as written. Only Task 6 moves LOCALAPPDATA, and its Step 3 gives the fallback for the install manager's `py` — cost if wrong: none for a user, whose LOCALAPPDATA does not move.
- Ruling (open issue 6): Development setup's step 4 names `CSXCAD_INSTALL_PATH` for the dev venv, and Task 6 Step 6 sets it in the same call as the run; a README install's workers keep reading the folder `setup-openems` recorded — cost if wrong: none.
- Ruling (agents, the real run and the release check): no agent but the controller runs the real-run test with an empty `KRS_E2E_DIR`. Task 4's gated checks use a folder that holds a file and one inside the repository, as its Step 2 gives them, and both fail before anything starts. The Task 2 implementer may run `tools/release_check.py` whole once, after its tests pass, since `isolated()` gives every app process it starts a temporary data folder, KiCad folders and an unused KiCad socket; Task 6 runs it as the record's evidence. Plan 3's ruling "agents and the owner's KiCad" binds every task. An agent that runs the privacy gate reports only whether it was clean, with no count and no pattern index — cost if wrong: none.
