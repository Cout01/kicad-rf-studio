# Stage 1 · Plan 1: Foundation and Board Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A tested package whose `kicad-rf-studio new` command:
- reads a `.kicad_pcb` file;
- traces the RF chain between two pads;
- writes `project.json`.

The plan also delivers the repository's privacy gate and the synthetic fixture boards.

**Architecture:**
- A stdlib S-expression reader feeds `core.kicad`, which builds a `Board` of shapely polygons in mm, y up.
- `core.kicad` classifies nets and footprints, then traces the chain as a breadth-first walk over nets through two-pad parts.
- `core.project` writes the project file, and `cli.py` is a thin argparse front end.
- Fixture boards are generated once with KiCad 9's own Python and committed. pcbnew's pad polygons are committed alongside them as ground truth.

**Tech Stack:**
- Python ≥ 3.11, shapely 2, pytest (dev only);
- git hooks and GitHub Actions;
- KiCad 9.0.7's bundled Python, for the dev-time fixture generator only.

**Spec:** `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`. This plan covers §1.3, §3.1–3.5 (the parts listed below), §4, §5.6's reference rule, §8 (import errors) and §9.1.

**Stage 1 is split into five plans.** Each one ends in working, tested software:
1. Foundation and board import (this plan).
2. Geometry, mesh and the mesh gates, including the 2D Z0/εeff readout of `cost`.
3. Model, worker and run control: `cost`, `run`, `preview`, `calibrate` and `setup-openems`.
4. Co-simulation and results: `retune`, `verify`, the outputs and the validity indicators.
5. Validation gates P0-A to P0-D, the KiCad button pre-check and the reports.

**Branch:** work on `stage1-plan1`. Commands assume the dev venv is active.

## Global Constraints

- **Python:** ≥ 3.11 everywhere. The Windows dev venv uses Python 3.14, or 3.13 if a dependency has no 3.14 wheel.
- **Licence:** GPL-3.0-or-later. Every `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`.
- **Dependencies:** the only runtime dependency in this plan is `shapely>=2.0`; the only dev dependency is `pytest>=8`.
- **Imports:** the product imports no pcbnew, Qt, openEMS or CSXCAD. `tools/make_fixtures.py` is dev-time only.
- **User-facing strings:** every one is a message code with parameters in `core.messages`, and the English template is the msgid.
- **Units:** mm, Hz and s.
- **Coordinates:** board coordinates map to (x, −y). Angles are degrees, counter-clockwise in that y-up frame.
- **KiCad versions:** KiCad 9 minimum (file version ≥ 20241229). KiCad 9 and 10 files are read, and nets are looked up by name.
- **Privacy:**
  - only synthetic data enters the repository: no private names, paths or board details;
  - vendor S2P files are never committed;
  - no drive paths or e-mail addresses appear in committed text.
- **Commits:** commit messages carry no co-author lines.
- **Language:** code, comments, docs and messages are in English.

## Review Focus

1. **KiCad 10 files.** A board saved by KiCad 10 references nets by name and has no net codes; it must load like its KiCad 9 twin. Test: `test_kicad10_net_syntax` (Task 6).
2. **KiCad 9's teardrop writer bug.** A board with a bare `)filter_ratio` must load, with one warning. Tests: `test_filter_ratio_repair` (Task 3) and `test_repair_warning` (Task 6).
3. **Bottom-side and rotated footprints.** Their pads must sit exactly where pcbnew puts them. Test: `test_pads_match_pcbnew` on `pads_zoo` (Task 7).
4. **Non-ASCII text.** Values and paths with spaces or accents must round-trip, and a cp1252 console must never crash the CLI. Tests: `test_parse_value` with "0Ω" (Task 4), then `test_project_path_with_spaces_and_accents` and `test_cli_survives_a_cp1252_console` (Task 11).
5. **Unfilled zones and boards without Edge.Cuts.** They must produce warnings, not crashes. Tests: `test_unfilled_zone_warns` and `test_missing_outline_warns` (Task 6).

---

## File structure

```
pyproject.toml  LICENSE  README.md  .gitignore
.githooks/pre-commit  .githooks/pre-push
.github/workflows/ci.yml
tools/privacy_gate.py  tools/privacy_allow.txt        # stdlib only
tools/make_fixtures.py                                # dev-time, KiCad 9 Python
src/kicad_rf_studio/__init__.py
src/kicad_rf_studio/cli.py                            # argparse front end
src/kicad_rf_studio/core/__init__.py
src/kicad_rf_studio/core/messages.py                  # CATALOG, KrsError, render()
src/kicad_rf_studio/core/project.py                   # project.json
src/kicad_rf_studio/core/kicad/__init__.py            # re-exports
src/kicad_rf_studio/core/kicad/sexpr.py               # tokenizer, repair, node helpers
src/kicad_rf_studio/core/kicad/values.py              # part values, frequencies
src/kicad_rf_studio/core/kicad/shapes.py              # arcs, pad outlines, ShapePos
src/kicad_rf_studio/core/kicad/board.py               # dataclasses, load_board()
src/kicad_rf_studio/core/kicad/mask.py                # solder-mask openings
src/kicad_rf_studio/core/kicad/stackup.py             # board stackup, default rule, presets
src/kicad_rf_studio/core/kicad/tracer.py              # classify, trace_chain, choose_reference
src/kicad_rf_studio/data/stackups/jlcpcb-2l.json
tests/conftest.py  tests/test_*.py
tests/fixtures/*.kicad_pcb  tests/fixtures/*.pads.json
```

---

### Task 1: Repository skeleton

**Files:**
- Create: `pyproject.toml`, `LICENSE`, `README.md`, `.gitignore`, `.github/workflows/ci.yml`, `src/kicad_rf_studio/__init__.py`, `src/kicad_rf_studio/core/__init__.py`
- Test: `tests/test_repo.py`

**Interfaces:**
- Produces: package `kicad_rf_studio` with `__version__ = "0.1.0.dev0"`, and the console script `kicad-rf-studio = kicad_rf_studio.cli:main`. `cli.py` arrives in Task 11.

- [ ] **Step 1: Write the failing test**

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import kicad_rf_studio

ROOT = Path(__file__).resolve().parents[1]
SPDX = "# SPDX-License-Identifier: GPL-3.0-or-later"

def test_version():
    assert kicad_rf_studio.__version__ == "0.1.0.dev0"

def test_every_python_file_has_spdx_header():
    files = [p for d in ("src", "tools", "tests") if (ROOT / d).is_dir() for p in (ROOT / d).rglob("*.py")]
    missing = [str(p.relative_to(ROOT)) for p in files
               if SPDX not in p.read_text(encoding="utf-8").splitlines()[:2]]
    assert missing == []
```

- [ ] **Step 2: Run the test to verify it fails.** Run `python -m pytest tests/test_repo.py -q`. Expected: an import error for `kicad_rf_studio`.

- [ ] **Step 3: Create the skeleton**

`pyproject.toml`, exactly:

```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "kicad-rf-studio"
version = "0.1.0.dev0"
description = "Simulate the RF parts of a KiCad board with openEMS"
readme = "README.md"
license = "GPL-3.0-or-later"
requires-python = ">=3.11"
dependencies = ["shapely>=2.0"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
kicad-rf-studio = "kicad_rf_studio.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
kicad_rf_studio = ["data/**/*.json"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

The other files:
- **`LICENSE`:** the verbatim text of https://www.gnu.org/licenses/gpl-3.0.txt.
- **`README.md`:** a one-paragraph description, plus the dev setup: create a venv, then run `pip install -e .[dev]`.
- **`.gitignore`:**

```
.venv/
__pycache__/
*.egg-info/
build/
dist/
.pytest_cache/
# user projects, results and boards never enter the repository
project.json
project.json.lock
results/
*.s[0-9]p
*.s[0-9][0-9]p
*.kicad_pcb
*.kicad_pro
*.kicad_prl
*.lck
*-backups/
fp-info-cache
!tests/fixtures/*.kicad_pcb
graphify-out/
.claude/settings.local.json
```

- **`.github/workflows/ci.yml`:** job `tier-a`, on push and pull request. The matrix pairs `windows-latest` with Python 3.14 and `ubuntu-24.04` with 3.12. Steps:
  1. `actions/checkout@v4` with `fetch-depth: 0`;
  2. `actions/setup-python@v5`;
  3. `python -m pip install -e .[dev]`;
  4. `python -m pytest -q`.

- [ ] **Step 4: Create the venv and run the tests.** Run `py -3.14 -m venv .venv`, then `pip install -e .[dev]`, then `python -m pytest -q`. Expected: `2 passed`.

- [ ] **Step 5: Commit.** Run `git add -A`, then `git commit -m "build: add package skeleton, licence and CI tier (a)"`.

---

### Task 2: Privacy gate

**Files:**
- Create: `tools/privacy_gate.py`, `tools/privacy_allow.txt`, `.githooks/pre-commit`, `.githooks/pre-push`
- Modify: `.github/workflows/ci.yml`, `README.md`
- Test: `tests/test_privacy_gate.py`

**Interfaces:**
- **`scan_text(text: str, deny: list[str], generic: bool = True) -> list[tuple[int, str]]`.** Returns one `(line, rule)` pair per hit:
  - `line` is 1-based;
  - `rule` is `"deny#<n>"` (n is 1-based) or `"generic:drive|home|unc|email"`;
  - the matched text never appears.
- **`main(argv: list[str] | None = None) -> int`.**
  - It takes exactly one of `--staged`, `--pre-push REMOTE URL` or `--all`, plus an optional `--generic-only`.
  - It returns 0 when clean, 1 on hits, and 2 when the private list is missing and `--generic-only` is not set.
- **Private list:**
  - its path is in the env var `KRS_PRIVATE_LIST`;
  - it is UTF-8, one entry per line, and blank lines and `#` lines are ignored;
  - entries match as case-insensitive substrings.
- **`tools/privacy_allow.txt`:** each line `path:<repo-relative path>` exempts that path from the generic rules only.

The generic rules, exactly:

```python
GENERIC = {
    "drive": r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]",
    "home": r"/(?:home|Users)/[^/\s]+/",
    "unc": r"\\\\[A-Za-z0-9_.$-]+\\",
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
}
```

**What each mode scans:**
- **`--staged`:**
  - the paths come from `git diff --cached --name-only -z --diff-filter=ACMR`;
  - each path and its staged blob (`git show :<path>`) are scanned.
- **`--pre-push`:**
  - stdin carries lines of the form `<local ref> <local sha> <remote ref> <remote sha>`;
  - a line whose local sha is all zeros is skipped;
  - the commits are `git rev-list <local sha> --not --remotes` when the remote sha is all zeros, and `git rev-list <remote sha>..<local sha>` otherwise.
- **`--all`:** the commits are `git rev-list --all`.
- **What is scanned per commit:**
  - the header and message: `git cat-file commit <sha>`;
  - every path in `git ls-tree -r -z --full-tree <sha>`;
  - every blob once, by blob sha. A blob is scanned as UTF-8 text with `errors="replace"`, except `.npz` and `.zip` blobs, whose member names are scanned instead. Other binary blobs are skipped, meaning blobs with a NUL byte in their first 8 KiB.
  - the ref names.
- **Output:** one line per hit, `<where>:<line>: <rule>`.

- [ ] **Step 1: Write the failing tests.** The test file defines three helpers and imports the gate through `sys.path.insert(0, str(ROOT / "tools"))`:
  - **`repo` fixture:**
    - runs `git init` in `tmp_path`;
    - calls `monkeypatch.chdir`;
    - sets `KRS_PRIVATE_LIST` to a file containing `acme`.
  - **`commit(repo, path, text, author=None) -> str`:**
    - writes the file, then adds and commits it;
    - uses a dummy identity built at runtime, so no literal address sits in the source;
    - passes `--author` when given;
    - returns the sha.
  - **`commit_zip(repo, path, member) -> str`:** commits a zip with one member of that name.

```python
def test_generic_rules():
    text = "a " + "D" + ":" + "\\" + "data\nb " + "user" + "@" + "example.org\n"
    assert gate.scan_text(text, deny=[]) == [(1, "generic:drive"), (2, "generic:email")]

def test_deny_is_case_insensitive_and_never_echoed(repo, capsys):
    commit(repo, "notes.md", "Project ACME\n")
    assert gate.main(["--all"]) == 1
    out = capsys.readouterr().out
    assert "deny#1" in out and "acme" not in out.lower()

def test_missing_list_fails_closed(repo, monkeypatch):
    monkeypatch.delenv("KRS_PRIVATE_LIST")
    assert gate.main(["--all"]) == 2

def test_pre_push_scans_the_whole_range(repo, monkeypatch):
    commit(repo, "a.txt", "acme\n"); sha = commit(repo, "a.txt", "clean\n")
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"refs/heads/main {sha} refs/heads/main {'0' * 40}\n"))
    assert gate.main(["--pre-push", "origin", "url"]) == 1

def test_author_email_is_checked(repo):
    commit(repo, "a.txt", "clean\n", author="dev <dev" + "@" + "acme.test>")
    assert gate.main(["--all"]) == 1

def test_zip_member_names_are_checked(repo):
    commit_zip(repo, "w.npz", member="acme.npy")
    assert gate.main(["--all"]) == 1

def test_allow_file_exempts_generic_rules_only(repo):
    commit(repo, "tools/privacy_allow.txt", "path:docs/x.md\n")
    commit(repo, "docs/x.md", "D" + ":" + "/x\n")
    assert gate.main(["--all", "--generic-only"]) == 0
```

- [ ] **Step 2: Run the tests to verify they fail.** Run `python -m pytest tests/test_privacy_gate.py -q`. Expected: `ModuleNotFoundError: privacy_gate`.

- [ ] **Step 3: Implement `tools/privacy_gate.py`** (stdlib only) to the rules above, and add the hooks:
  - **`.githooks/pre-commit`:** `#!/bin/sh` followed by `exec python tools/privacy_gate.py --staged`.
  - **`.githooks/pre-push`:** `#!/bin/sh` followed by `exec python tools/privacy_gate.py --pre-push "$@"`.
  - Mark both executable with `git update-index --chmod=+x`.
  - Put `path:tests/test_privacy_gate.py` in `tools/privacy_allow.txt`.
  - **CI:** add the step `python tools/privacy_gate.py --all --generic-only` before pytest.
  - **README:** add a "Contributing" section: set `KRS_PRIVATE_LIST`, then run `git config core.hooksPath .githooks`.

- [ ] **Step 4: Run the tests.** Expected: `7 passed`.

- [ ] **Step 5: Owner step.**
  - Stop and ask the owner to create the private list outside the repository and set `KRS_PRIVATE_LIST`.
  - Then run `git config core.hooksPath .githooks`.
  - Then run `python tools/privacy_gate.py --all`. It reports the existing commits' author identity, which is expected until the owner's identity rewrite (spec §12).

- [ ] **Step 6: Commit.** Run `git add -A`, then `git commit -m "feat: add local privacy gate and git hooks"`.

---

### Task 3: S-expressions and message codes

**Files:**
- Create: `src/kicad_rf_studio/core/messages.py`, `src/kicad_rf_studio/core/kicad/__init__.py`, `src/kicad_rf_studio/core/kicad/sexpr.py`
- Test: `tests/test_sexpr.py`

**Interfaces:**
- **`messages.CATALOG: dict[str, str]`:** maps each code to its English `str.format` template. All codes of this plan are in the table below.
- **`messages.KrsError(Exception)`:**
  - constructed as `KrsError(code: str, **params)`;
  - attributes `.code` and `.params`;
  - `str(err)` returns `render(code, **params)`.
- **`messages.render(code: str, **params) -> str`:**
  - looks the template up with `gettext.translation("kicad_rf_studio", localedir=<package>/locale, fallback=True).gettext`;
  - then calls `.format(**params)`.
- **`sexpr.Quoted(str)`:** marks atoms that were quoted in the file.
- **`sexpr.repair(text: str) -> tuple[str, int]`:**
  - fixes KiCad 9's teardrop writer bug: `re.sub(r'\)(\s*)filter_ratio\b', r')\1(filter_ratio', text)`;
  - returns the text and the count.
- **`sexpr.parse(text: str) -> list`:**
  - returns the root node: a list whose first item is its head symbol;
  - atoms are `str`, or `Quoted` for quoted strings;
  - on unbalanced brackets it raises `KrsError("E_PARSE_UNBALANCED", line=N)`. N is the line of the last unclosed `(`, or the line where an extra `)` appears.
- **Helpers:**
  - `child(node, head) -> list | None`;
  - `children(node, head) -> list[list]`;
  - `atom(node, head, i=1, default=None) -> str | None`;
  - `num(node, head, i=1, default=None) -> float | None`.

**Message catalog (all of this plan):**

| Code | Template |
|---|---|
| E_PARSE_UNBALANCED | The board file is damaged: unbalanced brackets near line {line}. Open it in KiCad and save it again. |
| E_BOARD_VERSION | This board was saved by a KiCad older than 9 (file version {version}). Open it in KiCad 9 or newer and save it. |
| W_BOARD_NEWER | This board was saved by a newer KiCad (file version {version}); reading it was not tested. |
| W_REPAIRED_FILTER_RATIO | Repaired {count} teardrop entries damaged by a KiCad 9 writer bug; the file on disk is unchanged. |
| W_ZONE_NOT_FILLED | Zone {uuid} on {layer} has no fill and is left out. Refill (B) in KiCad and save. |
| W_NO_OUTLINE | The board has no Edge.Cuts outline, so the substrate is not clipped. |
| W_NETLESS_COPPER | Copper shape {uuid} on {layer} has no net and is simulated as floating copper. |
| W_PADSTACK | Pad {pad} uses a per-layer padstack; its front shape is used on every layer. |
| E_BAD_FREQUENCY | Cannot read the frequency "{text}". Write it like 915MHz. |
| E_UNKNOWN_PRESET | Unknown stackup preset "{name}". Known presets: {known}. |
| E_DEFAULT_RULE_LAYERS | Stackup presets are implemented for 2 copper layers, and this board has {count}. Add the stackup to the board in KiCad. |
| W_COPPER_WEIGHT | Copper layers {layers} are not 35 µm; the mesh rule is not validated for this copper weight. |
| E_NO_STACKUP | The board has no stackup. Give --stackup jlcpcb-2l, or --stackup kicad-default to accept KiCad's default rule. |
| E_UNKNOWN_PAD | Pad {name} does not exist. Closest pads: {candidates}. |
| E_AMBIGUOUS_PAD | Pads named {name} sit on different nets ({nets}). Name a pad with a unique number. |
| E_START_ON_GND | Pad {name} is on net "{net}", which is GND, power or no net; a chain cannot start or end there. |
| E_NO_CHAIN | No chain from {start} to {end}: the walk stopped at nets {reached}. A DNP part, a GND or power net, or a part with three or more pads is in the way. |
| E_PROJECT_SCHEMA | {path} uses project schema {found}; this version reads schema {expected}. |
| I_STACKUP | Stackup: {source}, dielectric {thickness_mm} mm, εr {epsilon_r}. |
| I_CLASSES | GND nets: {gnd}. Power nets: {power}. Connectors: {connectors}. Shields: {shields}. |
| I_CHAIN | Chain {start} → {end}: series {series}; shunt {shunt}. |
| I_PORT | Port {name}: signal {signal}, reference {reference} ({rule}). |
| I_DEFAULTS | Preset {preset} (provisional default), band factor {band_factor}, T_max {t_max_ns} ns, harmonics {harmonics}. |
| W_FILLS_AS_SAVED | Fills as saved — refill (B) in KiCad and save if you changed copper. |
| W_LID_HEIGHT_MISSING | Shield {refs} found but no --lid-height was given; `run` will refuse until project.json has lid_height_mm. |
| W_NO_REFERENCE | No reference found for {signal}; set it in project.json before `run`. |
| W_ABSOLUTE_BOARD_PATH | The board is on another drive, so project.json stores its absolute path. |
| I_WROTE | Wrote {path}. |
| E_INTERNAL | Internal error: {detail}. Please report it. |

- [ ] **Step 1: Write the failing tests**

```python
from kicad_rf_studio.core.kicad.sexpr import parse, repair, Quoted, child, atom, num
from kicad_rf_studio.core.messages import KrsError, CATALOG, render
import string, pytest

def test_parse_nested_quoted_and_escaped():
    root = parse('(a (b "x \\"y\\"") 1.5 sym)')
    assert root == ["a", ["b", 'x "y"'], "1.5", "sym"]
    assert isinstance(root[1][1], Quoted) and not isinstance(root[3], Quoted)

def test_helpers():
    root = parse('(pad "1" (at 1 -2 90) (size 0.5 0.6))')
    assert atom(root, "at") == "1" and num(root, "at", 3) == 90.0 and child(root, "drill") is None

def test_filter_ratio_repair():
    text, n = repair("(teardrop (curved_edges no)filter_ratio 0.9))")
    assert n == 1
    assert parse(text) == ["teardrop", ["curved_edges", "no"], ["filter_ratio", "0.9"]]

def test_unbalanced_reports_line():
    with pytest.raises(KrsError) as e:
        parse("(a\n (b\n")
    assert e.value.code == "E_PARSE_UNBALANCED" and e.value.params["line"] == 2

def test_every_template_formats():
    for code, template in CATALOG.items():
        fields = {f for _, f, _, _ in string.Formatter().parse(template) if f}
        assert render(code, **{f: "x" for f in fields})
```

- [ ] **Step 2: Run the tests to verify they fail.** Run `python -m pytest tests/test_sexpr.py -q`. Expected: an import error.

- [ ] **Step 3: Implement `messages.py` and `sexpr.py`.** Tokenize with one regex, `r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+'`, and a stack. Track line numbers by counting newlines between matches.

- [ ] **Step 4: Run the tests.** Expected: `5 passed`.

- [ ] **Step 5: Commit.** Message: `feat: add S-expression reader and message catalog`.

---

### Task 4: Part values and frequencies

**Files:**
- Create: `src/kicad_rf_studio/core/kicad/values.py`
- Test: `tests/test_values.py`

**Interfaces:**
- **`parse_value(text: str) -> tuple[float, str] | None`.**
  - It returns `(SI value, kind)`. The kind is `"F"`, `"H"` or `"R"`, or `""` when the text has no unit letter. It returns `None` when the text has no number.
  - Everything after the first `/` or whitespace is ignored.
  - It accepts the prefixes p, n, u, µ, m, k, K, M, G and `meg`, RKM notation (`4n7`, `4R7`, `2k2`, `0R`), and the units F, H, R, Ω and ohm.
- **`parse_frequency(text: str) -> float`.**
  - It accepts `915MHz`, `0.915 GHz`, `915e6` and `915mhz`, and returns Hz.
  - The k, M and G prefixes and the `Hz` unit are case-insensitive.
  - Any other text raises `KrsError("E_BAD_FREQUENCY", text=text)`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("text, expected", [
    ("10uF/16V", (10e-6, "F")), ("0R", (0.0, "R")), ("0Ω", (0.0, "R")), ("1meg", (1e6, "")),
    ("4n7", (4.7e-9, "")), ("4R7", (4.7, "R")), ("2k2", (2200.0, "")), ("3.3pF", (3.3e-12, "F")),
    ("15nH", (15e-9, "H")), ("100n", (100e-9, "")), ("47pF 50V", (47e-12, "F")), ("DNP", None), ("", None)])
def test_parse_value(text, expected):
    got = parse_value(text)
    if expected is None:
        assert got is None
    else:
        assert got[1] == expected[1] and got[0] == pytest.approx(expected[0])

@pytest.mark.parametrize("text", ["915MHz", "0.915 GHz", "915e6", "915mhz"])
def test_parse_frequency(text):
    assert parse_frequency(text) == pytest.approx(915e6)

def test_bad_frequency():
    with pytest.raises(KrsError) as e:
        parse_frequency("abc")
    assert e.value.code == "E_BAD_FREQUENCY"
```

- [ ] **Step 2: Run the tests to verify they fail.** Run `python -m pytest tests/test_values.py -q`.
- [ ] **Step 3: Implement both functions in `values.py`.**
- [ ] **Step 4: Run the tests.** Expected: all pass.
- [ ] **Step 5: Commit.** Message: `feat: parse part values and frequencies`.

---

### Task 5: Fixture boards

**Files:**
- Create: `tools/make_fixtures.py`
- Create: `tests/fixtures/<name>.kicad_pcb` and `tests/fixtures/<name>.pads.json` for every name below
- Test: `tests/test_fixtures.py`

**Interfaces:**
- **Produces:** the fixture files that later tasks test against.
- **`<name>.pads.json`:** `{"<pad uuid>": {"name": "REF.NUM", "center": [x, y], "polygons": [[[x, y], ...], ...]}}`.
  - Values are in mm, y up.
  - `center` comes from pcbnew's `ShapePos`.
  - `polygons` holds the outer rings of `GetEffectivePolygon(<pad's first copper layer>, ERROR_INSIDE)`.
  - A board with no pads gets `{}`.

**How the generator runs.** It is dev-time code and runs only under KiCad 9's bundled Python:
- The env var `KICAD_PYTHON` names KiCad's `python.exe`, in KiCad's `bin` folder.
- The isolated profile: before running, point `KICAD_CONFIG_HOME`, `KICAD_DOCUMENTS_HOME`, `KICAD_CACHE_HOME` and `TEMP` at an empty `build/kicad-profile`.
- The command is `"%KICAD_PYTHON%" tools/make_fixtures.py tests/fixtures`.
- Footprints are loaded by path from KiCad's footprint folder, given by `KICAD9_FOOTPRINT_DIR`, because the isolated profile has no library table.
- Zones are filled with `ZONE_FILLER`.
- Every board gets KiCad's default 2-layer stackup for its thickness.

**Fixture contents.** All boards are 0.8 mm thick with 2 layers.

| Fixture | Content |
|---|---|
| `coupon_ms` | 20 mm microstrip, 1.35 mm wide, net `LINE` on F.Cu; B.Cu GND zone; an F.Mask opening over the whole board; no footprints |
| `coupon_ms_masked` | `coupon_ms` without the mask opening |
| `coupon_gcpw` | 20 mm GCPW, 0.6 mm wide with 0.15 mm gaps; F.Cu and B.Cu GND zones; a GND via fence (0.3 mm drill, 0.6 mm pad, 1 mm pitch, 0.6 mm from each line edge); mask opening |
| `coupon_gcpw_masked` | `coupon_gcpw` without the mask opening |
| `coupon_gcpw_pads` | `coupon_gcpw` with `TestPoint:TestPoint_Pad_1.0x1.0mm` footprints TP1 and TP2 at the line ends, both on `LINE` |
| `coupon_dense` | `coupon_gcpw` plus a parallel 0.3 mm trace on net `AUX`, 0.2 mm outside the top ground's edge |
| `coupon_gcpw_45` | `coupon_gcpw` routed at 45° |
| `coupon_gcpw_arc` | `coupon_gcpw` with a 90° arc track of 5 mm radius in the middle |
| `lpf915` | Parts below on F.Cu; GCPW traces 0.6/0.15 mm; F.Cu and B.Cu GND zones; a via fence along the RF traces; default mask, with webs between the pads; `solder_mask_min_width` 0; an Edge.Cuts rectangle sized to fit, with J2 on the edge |
| `lpf915-45` | `lpf915` with L1 at 45° and its two traces re-routed to its pads |
| `pads_zoo` | Library footprints at 0°, 30°, 90° and 180°, one footprint on the bottom side, and a hand-built ZOO1. ZOO1 has circle, oval, trapezoid, chamfered round-rect, custom (a polygon primitive on a rect anchor) and thru-hole pads, one with a drill offset |

**`lpf915` parts:**

| Ref | Footprint | Value | Pads → nets |
|---|---|---|---|
| U1 | `Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm` | RFIC | 1 RF_A; 2, 4 and 17 (EP) GND; 8 VDD |
| C4 | `Capacitor_SMD:C_0603_1608Metric` | 10uF/16V | 1 VDD, 2 GND |
| C1 | `Capacitor_SMD:C_0402_1005Metric` | 100pF | 1 RF_A, 2 RF_B |
| C2 | `Capacitor_SMD:C_0402_1005Metric` | 3.3pF | 1 RF_B, 2 GND |
| L1 | `Inductor_SMD:L_0402_1005Metric` | 15nH | 1 RF_B, 2 RF_C |
| C3 | `Capacitor_SMD:C_0402_1005Metric` | 3.3pF | 1 RF_C, 2 GND |
| R1 | `Resistor_SMD:R_0402_1005Metric` | 0R | 1 RF_C, 2 RF_OUT |
| J1 | `Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical` | U.FL | 1 RF_OUT, the others GND |
| R2 | `Resistor_SMD:R_0402_1005Metric` | 0R, DNP | 1 RF_OUT, 2 RF_SMA |
| J2 | `Connector_Coaxial:SMA_Amphenol_132289_EdgeMount` | SMA | 1 RF_SMA, the others GND |
| SH1 | a frame footprint from KiCad's `RF_Shielding` library, enclosing U1 to J1 | SHIELD | all pads GND |

- [ ] **Step 1: Write the failing test**

```python
FIX = Path(__file__).parent / "fixtures"
NAMES = ["lpf915", "lpf915-45", "coupon_ms", "coupon_ms_masked", "coupon_gcpw", "coupon_gcpw_masked",
         "coupon_gcpw_pads", "coupon_dense", "coupon_gcpw_45", "coupon_gcpw_arc", "pads_zoo"]

@pytest.mark.parametrize("name", NAMES)
def test_fixture_parses_and_has_pad_truth(name):
    root = parse(repair((FIX / f"{name}.kicad_pcb").read_text(encoding="utf-8"))[0])
    assert root[0] == "kicad_pcb" and int(atom(root, "version")) >= 20241229
    truth = json.loads((FIX / f"{name}.pads.json").read_text(encoding="utf-8"))
    uuids = {atom(p, "uuid") for fp in children(root, "footprint") for p in children(fp, "pad")}
    assert set(truth) == uuids
```

- [ ] **Step 2: Run the test to verify it fails.** Run `python -m pytest tests/test_fixtures.py -q`. Expected: file-not-found failures.

- [ ] **Step 3: Write `tools/make_fixtures.py` and run it.**
  - Use `help(pcbnew.PAD)` and `help(pcbnew.FOOTPRINT)` inside KiCad's Python for the KiCad 9 API.
  - DNP is set with the footprint's DNP setter.
  - Open each board once in KiCad to confirm that it looks as described.

- [ ] **Step 4: Run the test.** Expected: `11 passed`.

- [ ] **Step 5: Commit.** The pre-commit privacy gate checks the generated files. Message: `test: add synthetic fixture boards and pcbnew pad truth`.

---

### Task 6: Board reader — header, nets, outline, tracks, vias, zones

**Files:**
- Create: `src/kicad_rf_studio/core/kicad/board.py`, `src/kicad_rf_studio/core/kicad/shapes.py`, `tests/conftest.py`
- Modify: `src/kicad_rf_studio/core/kicad/__init__.py`, to export `load_board`
- Test: `tests/test_board.py`

**Interfaces:**

```python
XY = tuple[float, float]

@dataclass(frozen=True)
class Track:            # segment, or arc when mid is set
    layer: str; net: str; width: float; start: XY; end: XY; mid: XY | None; uuid: str
    def polygon(self) -> Polygon: ...   # round-capped outline

@dataclass(frozen=True)
class Via:
    at: XY; diameter: float; drill: float; layers: tuple[str, str]; net: str; uuid: str

@dataclass(frozen=True)
class CopperArea:       # zone fill or copper graphic
    layer: str; net: str; polygon: Polygon; source: str; uuid: str     # source: "zone" | "graphic"

@dataclass
class Board:
    path: Path; version: int; thickness: float
    copper_layers: tuple[str, ...]          # top to bottom: F.Cu, In1.Cu, ..., B.Cu
    nets: tuple[str, ...]
    footprints: dict[str, "Footprint"]      # by reference; filled in Task 7
    tracks: list[Track]; vias: list[Via]; areas: list[CopperArea]
    outline: Polygon | None
    pad_to_mask_clearance: float; solder_mask_min_width: float
    mask_graphics: dict[str, list[Polygon]] # "F" / "B": shapes drawn on F.Mask / B.Mask
    stackup: "Stackup | None"               # filled in Task 9
    warnings: list[tuple[str, dict]]        # (message code, params)
    def pads(self, name: str) -> list["Pad"]: ...   # "REF.NUM"; Task 7

def load_board(path: str | Path) -> Board: ...
# shapes.py
def arc_points(start: XY, mid: XY, end: XY, max_err: float = 0.001) -> list[XY]: ...
def circle(center: XY, radius: float, max_err: float = 0.001) -> Polygon: ...
```

**Reading rules:**
- **Coordinates:** map every `at`, `start`, `mid`, `end`, `center` and `xy` to (x, −y).
- **Version:** `(version N)` with N < 20241229 raises `E_BOARD_VERSION`. N above `NEWEST_TESTED` adds `W_BOARD_NEWER`. `NEWEST_TESTED` is a module constant, 20241229 until CI tier (c) records the KiCad 10 version.
- **Repair:** when `repair()` fixed anything, add `W_REPAIRED_FILTER_RATIO(count)`.
- **Nets:**
  - the header table has entries `(net <code> "<name>")`;
  - an item's `(net …)` holding a `Quoted` atom gives the name directly (KiCad 10, and pads);
  - otherwise the integer code is looked up in the table;
  - `""` means no net.
- **Layers:** the copper layers are the `(layers …)` names ending in `.Cu`, ordered F.Cu, inner layers by number, then B.Cu.
- **Board-level items:**
  - the thickness comes from `(general (thickness T))`;
  - `pad_to_mask_clearance` and `solder_mask_min_width` come from `(setup …)`, defaulting to 0;
  - `segment` and `arc` become `Track`s;
  - `via` becomes a `Via`, with layers defaulting to F.Cu and B.Cu.
- **Zones:**
  - zones with `(keepout …)` are skipped;
  - each `filled_polygon` becomes a `CopperArea(source="zone")` on its layer when that layer is copper. On F.Mask or B.Mask it goes into `mask_graphics` instead;
  - a copper zone with no `filled_polygon` adds `W_ZONE_NOT_FILLED(uuid, layer)`.
- **Board graphics:** `gr_poly`, `gr_rect`, `gr_circle`, `gr_line` and `gr_arc`:
  - on copper layers they become `CopperArea(source="graphic")`. Filled shapes become polygons, and strokes are buffered by width/2. The net comes from `(net …)`, or is `""` with a `W_NETLESS_COPPER` warning;
  - on mask layers they go into `mask_graphics`;
  - on Edge.Cuts they go into the outline linework.
- **Outline:** run `shapely.ops.polygonize` on the Edge.Cuts linework. The largest polygon, minus the polygons inside it, is the outline. If there is none, the outline is `None` and `W_NO_OUTLINE` is added.
- **Track polygon:**
  - a segment is `LineString([start, end]).buffer(width / 2)`;
  - an arc is the `arc_points` polyline buffered the same way.

- [ ] **Step 1: Write `tests/conftest.py` and the failing tests**

```python
# conftest.py
MINI = ('(kicad_pcb (version {version}) (generator "test") (general (thickness 0.8)) '
        '(layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user) (39 "F.Mask" user)) '
        '(setup (pad_to_mask_clearance {clearance})) (net 0 "") {body})')

@pytest.fixture
def mini_board_file(tmp_path):
    def make(body="", version=20241229, clearance=0):
        p = tmp_path / "mini.kicad_pcb"
        p.write_text(MINI.format(version=version, clearance=clearance, body=body), encoding="utf-8")
        return p
    return make

@pytest.fixture
def mini_board(mini_board_file):
    return lambda body="", **kw: load_board(mini_board_file(body, **kw))
```

```python
# test_board.py
def codes(b): return [c for c, _ in b.warnings]

def test_lpf915_header():
    b = load_board(FIX / "lpf915.kicad_pcb")
    assert b.version >= 20241229 and b.thickness == pytest.approx(0.8)
    assert b.copper_layers == ("F.Cu", "B.Cu")
    assert {"GND", "VDD", "RF_A", "RF_B", "RF_C", "RF_OUT", "RF_SMA"} <= set(b.nets)

def test_coupon_copper():
    b = load_board(FIX / "coupon_gcpw.kicad_pcb")
    line = [t for t in b.tracks if t.net == "LINE"]
    assert line and all(t.width == pytest.approx(0.6) for t in line)
    assert len(b.vias) > 10 and {v.net for v in b.vias} == {"GND"}
    assert {a.layer for a in b.areas if a.net == "GND" and a.source == "zone"} == {"F.Cu", "B.Cu"}
    assert b.outline is not None and b.outline.area > 0

def test_track_polygons():
    seg = Track("F.Cu", "N", 0.2, (0, 0), (1, 0), None, "u")
    assert seg.polygon().area == pytest.approx(0.2 + math.pi * 0.01, rel=1e-3)
    arc = Track("F.Cu", "N", 0.1, (1, 0), (0, 1), (math.sqrt(0.5), math.sqrt(0.5)), "u")
    assert arc.polygon().area == pytest.approx(0.1 * math.pi / 2 + math.pi * 0.0025, rel=2e-3)

def test_kicad10_net_syntax(mini_board):
    k9 = '(net 1 "SIG") (segment (start 0 0) (end 1 0) (width 0.2) (layer "F.Cu") (net 1) (uuid "a"))'
    k10 = '(segment (start 0 0) (end 1 0) (width 0.2) (layer "F.Cu") (net "SIG") (uuid "a"))'
    assert mini_board(k9).tracks[0].net == "SIG"
    b10 = mini_board(k10, version=20250901)
    assert b10.tracks[0].net == "SIG" and "W_BOARD_NEWER" in codes(b10)

def test_repair_warning(mini_board):
    assert ("W_REPAIRED_FILTER_RATIO", {"count": 1}) in mini_board("(teardrops (curved_edges no)filter_ratio 0.9))").warnings

def test_unfilled_zone_warns(mini_board):
    zone = ('(zone (net 0) (net_name "") (layer "F.Cu") (uuid "z") '
            '(polygon (pts (xy 0 0) (xy 1 0) (xy 1 1))))')
    assert "W_ZONE_NOT_FILLED" in codes(mini_board(zone))

def test_missing_outline_warns(mini_board):
    b = mini_board("")
    assert b.outline is None and "W_NO_OUTLINE" in codes(b)

def test_old_version_refused(mini_board):
    with pytest.raises(KrsError) as e:
        mini_board("", version=20231120)
    assert e.value.code == "E_BOARD_VERSION"
```

- [ ] **Step 2: Run the tests to verify they fail.** Run `python -m pytest tests/test_board.py -q`.
- [ ] **Step 3: Implement `load_board`, `Track.polygon`, `arc_points` and `circle`** to the rules above. The arc segment count is `ceil(sweep / (2 * acos(1 - max_err / r)))`.
- [ ] **Step 4: Run the tests.** Expected: all pass.
- [ ] **Step 5: Add CI tier (c)** to `ci.yml`. It is a job in container `kicad/kicad:10.0`:
  - it downloads three demo boards from KiCad's repository at tag `9.0.7`, with their URLs pinned in the workflow, into `build/k9/`;
  - it copies `tests/fixtures/*.kicad_pcb` into `build/k9/` as well;
  - it runs `kicad-cli pcb upgrade` on each board into `build/k10/`;
  - it runs `pytest tests/test_kicad10.py` with `KRS_KICAD9_DIR=build/k9` and `KRS_KICAD10_DIR=build/k10`.

  Create `tests/test_kicad10.py`. For each board it compares `load_board` on the KiCad 9 file and on the upgraded copy: nets, track count, via count, footprint refs, and every pad centre within 1e-6 mm. It skips when either env var is unset.
- [ ] **Step 6: Commit.** Message: `feat: read board header, nets, outline, tracks, vias and zones`.

---

### Task 7: Footprints and pads

**Files:**
- Modify: `src/kicad_rf_studio/core/kicad/board.py`, `src/kicad_rf_studio/core/kicad/shapes.py`
- Test: `tests/test_pads.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class Pad:
    ref: str; number: str; uuid: str; net: str
    kind: str                      # "smd" | "thru_hole" | "np_thru_hole" | "connect"
    layers: tuple[str, ...]        # copper layers
    mask_sides: tuple[str, ...]    # subset of ("F", "B")
    center: XY                     # ShapePos
    polygon: Polygon
    mask_margin: float | None
    @property
    def name(self) -> str: ...     # f"{ref}.{number}"

@dataclass(frozen=True)
class Footprint:
    ref: str; value: str; mpn: str | None; lib_id: str; uuid: str
    layer: str; at: XY; angle: float; dnp: bool
    pads: tuple[Pad, ...]; mask_margin: float | None

def pad_shape(pad: list, fp_at: XY, fp_angle: float) -> tuple[XY, Polygon, list[tuple[str, dict]]]: ...   # shapes.py
```

**ShapePos.** The file stores a pad's angle `pa` already including the footprint's angle `fa`.

```python
def rot(p, deg):
    c, s = cos(radians(deg)), sin(radians(deg))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)
# footprint (at fx fy fa); pad (at px py pa); drill offset (offset ox oy), absent = 0
pos    = add((fx, -fy), rot((px, -py), fa))     # pad position
center = add(pos, rot((ox, -oy), pa))           # ShapePos
# the outline is built around (0, 0) in the pad frame (y up), rotated by pa, moved to center
```

Bottom-side footprints store already-mirrored local coordinates, so no extra mirroring is needed. If the zoo test fails, fix the transform, never the test.

**Outlines in the pad frame.** `(size w h)`. KiCad's local y points down, so negate y in every corner and primitive.
- **rect:** a box of w × h.
- **roundrect:** with r = `roundrect_rratio`·min(w, h), the box shrunk by r, then buffered by r.
- **chamfer:** with c = `chamfer_ratio`·min(w, h), cut the corners listed in `(chamfer …)`. "top" is +y after the flip.
- **circle:** radius w/2.
- **oval:** a stadium. That is a segment of length |w − h| along the long axis, buffered by min(w, h)/2.
- **trapezoid** (`rect_delta dx dy`): the corners, in KiCad's y-down frame, are `(-w/2-dy/2, h/2+dx/2)`, `(w/2+dy/2, h/2-dx/2)`, `(w/2-dy/2, -h/2+dx/2)` and `(-w/2+dy/2, -h/2-dx/2)`. The zoo test decides the signs.
- **custom:** the union of the anchor and each primitive.
  - The anchor is from `(options … (anchor rect|circle))`, sized w × h.
  - `gr_poly` is filled, and also buffered by width/2 when its width is above 0.
  - `gr_line` and `gr_arc` are strokes buffered by width/2.
  - `gr_circle` and `gr_rect` are filled, or a ring when not filled.
- **padstack:** a `(padstack (mode M))` with M other than `normal` adds `W_PADSTACK` and uses the main shape.

**Pad layers.** `*.Cu` means all copper layers, and `F&B.Cu` means F.Cu and B.Cu. The mask sides come from `F.Mask`, `B.Mask` and `*.Mask`.

**Footprint fields:**
- **ref and value:** `(property "Reference" …)` and `(property "Value" …)`.
- **mpn:** a property whose lower-cased name is `mpn`, `manufacturer part number` or `manufacturer_part_number`.
- **dnp:** `dnp` among the `(attr …)` atoms, or `(dnp yes)`.
- **mask margin:** `(solder_mask_margin m)` at footprint and at pad level.
- **graphics:** `fp_poly`, `fp_rect`, `fp_circle`, `fp_line` and `fp_arc` use the footprint transform `(fx, −fy) + rot((lx, −ly), fa)`. They then follow the board-graphic rules of Task 6, with net `""`.
- **duplicates:** pads that share a number keep separate `Pad` objects. `Board.pads("J1.2")` returns all of them.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("name", ["pads_zoo", "lpf915", "lpf915-45", "coupon_gcpw_pads"])
def test_pads_match_pcbnew(name):
    b = load_board(FIX / f"{name}.kicad_pcb")
    truth = json.loads((FIX / f"{name}.pads.json").read_text(encoding="utf-8"))
    pads = {p.uuid: p for fp in b.footprints.values() for p in fp.pads}
    assert set(pads) == set(truth)
    for uuid, t in truth.items():
        p = pads[uuid]
        assert p.name == t["name"] and math.dist(p.center, t["center"]) <= 1e-6, p.name
        ref = unary_union([Polygon(ring) for ring in t["polygons"]])
        assert p.polygon.hausdorff_distance(ref) <= 0.005, p.name
        assert p.polygon.symmetric_difference(ref).area <= 1e-3 * ref.area + 1e-6, p.name

def test_lpf915_footprints():
    b = load_board(FIX / "lpf915.kicad_pcb")
    assert b.footprints["C1"].value == "100pF" and b.footprints["R2"].dnp and not b.footprints["R1"].dnp
    assert b.footprints["L1"].lib_id == "Inductor_SMD:L_0402_1005Metric"
    assert [p.net for p in b.pads("C2.1")] == ["RF_B"] and b.pads("U1.17")[0].net == "GND"
```

- [ ] **Step 2: Run the tests to verify they fail.** Run `python -m pytest tests/test_pads.py -q`.
- [ ] **Step 3: Implement the footprint parsing, `pad_shape` and `Board.pads`.**
- [ ] **Step 4: Run the tests,** then `python -m pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit.** Message: `feat: read footprints and pad outlines at ShapePos`.

---

### Task 8: Solder-mask openings

**Files:**
- Create: `src/kicad_rf_studio/core/kicad/mask.py`
- Test: `tests/test_mask.py`

**Interfaces:**
- **Consumes:** `Board`, `Pad` and `Footprint` (Tasks 6–7).
- **Produces:** `mask_openings(board: Board, side: str) -> MultiPolygon`. `side` is `"F"` or `"B"`, and the result is empty when there are no openings.

**Rules:**
1. Every pad with `side` in `mask_sides` gets an opening, `pad.polygon.buffer(margin)`. The margin is the first value that is not `None` among `pad.mask_margin`, `footprint.mask_margin` and `board.pad_to_mask_clearance`. Negative margins shrink the opening.
2. Add `board.mask_graphics[side]` and take the union.
3. If `solder_mask_min_width` w > 0, apply `.buffer(w/2).buffer(-w/2)`. This removes mask webs narrower than w.

- [ ] **Step 1: Write the failing tests**

```python
def opening_hits(m, *polys): return [g for g in m.geoms if any(g.intersects(p) for p in polys)]

def test_web_between_0402_pads_is_kept():
    b = load_board(FIX / "lpf915.kicad_pcb")
    a, c = b.pads("C1.1")[0].polygon, b.pads("C1.2")[0].polygon
    hit = opening_hits(mask_openings(b, "F"), a)
    assert len(hit) == 1 and not hit[0].intersects(c)

def test_min_width_closes_narrow_webs():
    b = load_board(FIX / "lpf915.kicad_pcb")
    b.solder_mask_min_width = 0.6
    a, c = b.pads("C1.1")[0].polygon, b.pads("C1.2")[0].polygon
    assert any(g.intersects(a) and g.intersects(c) for g in mask_openings(b, "F").geoms)

def test_margin_precedence(mini_board):
    fp = ('(footprint "X:Y" (layer "F.Cu") (at 0 0) (property "Reference" "U9") (property "Value" "x") '
          '(solder_mask_margin 0.1) '
          '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Mask") (solder_mask_margin 0.05) (uuid "p1")) '
          '(pad "2" smd rect (at 5 0) (size 1 1) (layers "F.Cu" "F.Mask") (uuid "p2")))')
    m = mask_openings(mini_board(fp, clearance=0.2), "F")
    areas = sorted(g.area for g in m.geoms)
    assert areas == pytest.approx([1 + 4 * 0.05 + math.pi * 0.05**2, 1 + 4 * 0.1 + math.pi * 0.1**2], rel=1e-3)
```

- [ ] **Step 2: Run the tests to verify they fail.** Run `python -m pytest tests/test_mask.py -q`.
- [ ] **Step 3: Implement `mask_openings`.**
- [ ] **Step 4: Run the tests.** Expected: `3 passed`.
- [ ] **Step 5: Commit.** Message: `feat: build solder-mask openings`.

---

### Task 9: Stackup — board, KiCad default rule, JLCPCB preset

**Files:**
- Create: `src/kicad_rf_studio/core/kicad/stackup.py`, `src/kicad_rf_studio/data/stackups/jlcpcb-2l.json`
- Modify: `src/kicad_rf_studio/core/kicad/board.py`. `load_board` sets `stackup = from_board(root)`.
- Test: `tests/test_stackup.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class Layer:
    name: str; kind: str; thickness: float; epsilon_r: float | None; loss_tangent: float | None  # kind: "mask" | "copper" | "dielectric"

@dataclass(frozen=True)
class Stackup:
    source: str                       # "board" | preset name
    layers: tuple[Layer, ...]         # top to bottom; mask, copper and dielectric only
    def dielectric_thickness(self) -> float: ...
    def nonstandard_copper(self) -> list[str]: ...   # copper layers whose thickness differs from 0.035 mm by > 0.001 mm
    def to_json(self) -> dict: ...
    @staticmethod
    def from_json(d: dict) -> "Stackup": ...

def from_board(root: list) -> Stackup | None: ...      # (setup (stackup …)); None when absent
def kicad_default(thickness: float, copper_layers: int = 2) -> Stackup: ...
def preset(name: str, thickness: float, copper_layers: int = 2) -> Stackup: ...  # "kicad-default" | "jlcpcb-2l"
# both raise E_DEFAULT_RULE_LAYERS(count) when copper_layers != 2
```

**Rules:**
- **`from_board`:** maps each stackup `type` to a kind:
  - a type containing "Solder Mask" becomes `mask`;
  - `copper` stays `copper`;
  - `core` and `prepreg` become `dielectric`;
  - other types are dropped.

  Values come from `thickness`, `epsilon_r` and `loss_tangent`.
- **`kicad_default(t)`:** the layers, top to bottom, are:
  - mask: 0.01 mm, εr 3.3, tanδ 0;
  - copper: 0.035 mm;
  - dielectric: t − 0.09 mm, εr 4.5, tanδ 0.02;
  - copper: 0.035 mm;
  - mask: 0.01 mm, εr 3.3, tanδ 0.
- **`preset("jlcpcb-2l", t)`:** the same build. Its εr and tanδ come from the JSON file, and its dielectric is t minus the copper and mask.
- **`preset("kicad-default", t)`:** the same as `kicad_default(t)`.
- **Unknown name:** raises `E_UNKNOWN_PRESET(name, known)`.

**`jlcpcb-2l.json`:**
```json
{"name": "jlcpcb-2l", "source": "...", "retrieved": "YYYY-MM-DD", "spec_frequency_hz": ...,
 "copper_mm": 0.035,
 "mask": {"thickness_mm": ..., "epsilon_r": ..., "loss_tangent": ...},
 "dielectric": {"material": "FR-4", "epsilon_r": ..., "loss_tangent": ...},
 "notes": "..."}
```

- [ ] **Step 1: Write the failing tests**

```python
def test_kicad_default_rule():
    s = kicad_default(0.8)
    assert s.dielectric_thickness() == pytest.approx(0.71)
    assert (s.layers[0].kind, s.layers[0].thickness, s.layers[0].epsilon_r) == ("mask", 0.01, 3.3)

def test_board_stackup_is_read():
    s = load_board(FIX / "lpf915.kicad_pcb").stackup
    assert s.source == "board" and [l.kind for l in s.layers] == ["mask", "copper", "dielectric", "copper", "mask"]
    assert s.dielectric_thickness() == pytest.approx(0.71)

def test_board_without_stackup(mini_board):
    assert mini_board("").stackup is None

def test_jlcpcb_preset_records_its_source():
    d = json.loads(files("kicad_rf_studio").joinpath("data/stackups/jlcpcb-2l.json").read_text("utf-8"))
    assert d["source"].startswith("https://jlcpcb.com/") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["retrieved"])
    assert "spec_frequency_hz" in d and 3.5 <= d["dielectric"]["epsilon_r"] <= 5.0
    assert preset("jlcpcb-2l", 0.8).source == "jlcpcb-2l"

def test_unknown_preset():
    with pytest.raises(KrsError) as e:
        preset("nope", 0.8)
    assert e.value.code == "E_UNKNOWN_PRESET"

def test_presets_refuse_more_than_two_layers():
    with pytest.raises(KrsError) as e:
        preset("kicad-default", 1.6, copper_layers=4)
    assert e.value.code == "E_DEFAULT_RULE_LAYERS"

def test_nonstandard_copper_is_listed():
    s = kicad_default(0.8)
    heavy = Stackup("x", tuple(replace(l, thickness=0.07) if l.kind == "copper" else l for l in s.layers))
    assert s.nonstandard_copper() == [] and len(heavy.nonstandard_copper()) == 2
```

- [ ] **Step 2: Run the tests to verify they fail.** Run `python -m pytest tests/test_stackup.py -q`.
- [ ] **Step 3: Transcribe the JLCPCB preset.**
  - Read JLCPCB's public stackup or impedance page.
  - Record the URL, today's date, the frequency at which εr and tanδ are specified, and the 2-layer FR-4 and solder-mask values.
  - If the page cannot be read or does not state a value, stop and ask the owner. Never invent a value; a missing frequency is `null`, explained in `notes`.
- [ ] **Step 4: Implement `stackup.py` and wire it into `load_board`.**
- [ ] **Step 5: Run the tests.** Expected: `7 passed`.
- [ ] **Step 6: Commit.** Message: `feat: read board stackups and add KiCad-default and JLCPCB presets`.

---

### Task 10: Net classes, chain tracer and port references

**Files:**
- Create: `src/kicad_rf_studio/core/kicad/tracer.py`
- Modify: `src/kicad_rf_studio/core/kicad/__init__.py`, to export `classify`, `trace_chain` and `choose_reference`
- Test: `tests/test_tracer.py`

**Interfaces:**

```python
def is_gnd(net: str) -> bool: ...
def is_power(net: str) -> bool: ...

@dataclass(frozen=True)
class Classes:
    gnd: frozenset[str]; power: frozenset[str]; connectors: frozenset[str]; shields: frozenset[str]

def classify(board: Board, overrides: dict | None = None) -> Classes: ...

@dataclass(frozen=True)
class ChainPart:
    ref: str
    pads: tuple[str, str]   # series: (start side, end side); shunt: (chain side, other side)
    nets: tuple[str, str]

@dataclass(frozen=True)
class Chain:
    start: str; end: str; nets: tuple[str, ...]; series: tuple[ChainPart, ...]; shunt: tuple[ChainPart, ...]

def trace_chain(board: Board, start: str, end: str, classes: Classes | None = None) -> Chain: ...

@dataclass(frozen=True)
class Reference:
    rule: str               # "connector" | "ic" | "copper"
    pad: str | None; uuid: str | None; point: XY | None; layer: str

def choose_reference(board: Board, classes: Classes, signal: str) -> Reference | None: ...
```

**Classification** (spec §4.6). The patterns are matched with `fullmatch` on the base name, the text after the last `/`:

```python
GND = re.compile(r"(?i)[ADPSC]?GND\w*|\w*_GND|VSS\w*|0V|EARTH")
POWER = re.compile(r"(?i)\+\w+|\d+V\d*|V(CC|DD|BAT|IN|SYS|BUS|USB|IO|CORE)\w*")
CONNECTOR_PREFIXES = {"J", "P", "X", "CN"}    # letters before the reference's digits
```

- **Shield:** a footprint with ≥ 2 pads, all on GND nets, whose pads' bounding box contains the centre of a pad of another footprint.
- **Overrides:** any of the keys `gnd_nets`, `power_nets`, `connectors` and `shields` replaces the computed set.

**Tracer:**
1. **Resolve each name with `board.pads`:**
   - no match raises `E_UNKNOWN_PAD(name, candidates)`. The candidates are `", ".join(difflib.get_close_matches(name, all pad names, n=5))`;
   - matches on different nets raise `E_AMBIGUOUS_PAD(name, nets)`;
   - a start or end net that is GND, power or `""` raises `E_START_ON_GND(name, net)`.
2. **Build the graph.** The nodes are nets. The edges are footprints that meet all of these:
   - exactly two pads with a net;
   - not DNP, not a connector and not a shield;
   - neither net is GND or power.
3. **Search.** Run a breadth-first search from the start net, visiting footprints sorted by ref.
   - The series parts follow the path, with their pads oriented from start to end.
   - If the end net is not reached, raise `E_NO_CHAIN(start, end, reached)`, where `reached` lists the sorted nets that were reached.
4. **Shunt parts.** Every other two-pad footprint, DNP included, with a pad on a chain net is a shunt part. Its pads and nets are oriented as (chain side, other side), and the list is sorted by ref.

**Reference** (spec §5.6). Ties are broken by pad number, then uuid. The opposite layer is never used.
1. If the signal's footprint is a connector, take the nearest GND pad of that footprint (rule `connector`).
2. If the signal's footprint has ≥ 3 pads, take the nearest GND pad of that footprint (rule `ic`).
3. Otherwise, take the nearest point on GND copper on the signal pad's first layer, using `shapely.ops.nearest_points` over tracks, areas and pads (rule `copper`, with `pad=None`).
4. If none of these applies, return `None`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.fixture(scope="module")
def lpf(): return load_board(FIX / "lpf915.kicad_pcb")

def test_classify_lpf915(lpf):
    c = classify(lpf)
    assert "GND" in c.gnd and "VDD" in c.power and {"J1", "J2"} <= c.connectors and c.shields == {"SH1"}

@pytest.mark.parametrize("net, gnd, power", [
    ("/GND", True, False), ("GNDA", True, False), ("AGND", True, False), ("VSS", True, False),
    ("+3V3", False, True), ("3V3", False, True), ("VDD_RF", False, True), ("RF_OUT", False, False)])
def test_net_name_rules(net, gnd, power):
    assert (is_gnd(net), is_power(net)) == (gnd, power)

def test_output_chain(lpf):
    ch = trace_chain(lpf, "U1.1", "J1.1")
    assert ch.nets == ("RF_A", "RF_B", "RF_C", "RF_OUT")
    assert [p.ref for p in ch.series] == ["C1", "L1", "R1"] and ch.series[0].pads == ("C1.1", "C1.2")
    assert [p.ref for p in ch.shunt] == ["C2", "C3", "R2"]

def test_reverse_direction(lpf):
    assert [p.ref for p in trace_chain(lpf, "J1.1", "U1.1").series] == ["R1", "L1", "C1"]

def test_dnp_part_blocks_the_walk(lpf):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "U1.1", "J2.1")
    assert e.value.code == "E_NO_CHAIN"

def test_unknown_pad_lists_candidates(lpf):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "U1.99", "J1.1")
    assert e.value.code == "E_UNKNOWN_PAD" and e.value.params["candidates"].startswith("U1.")

def test_single_trace():
    b = load_board(FIX / "coupon_gcpw_pads.kicad_pcb")
    ch = trace_chain(b, "TP1.1", "TP2.1")
    assert ch.nets == ("LINE",) and ch.series == () and ch.shunt == ()

def test_references(lpf):
    c = classify(lpf)
    r = choose_reference(lpf, c, "U1.1"); assert (r.rule, r.pad) == ("ic", "U1.2")
    r = choose_reference(lpf, c, "J1.1"); assert r.rule == "connector" and lpf.pads(r.pad)[0].net == "GND"
    t = load_board(FIX / "coupon_gcpw_pads.kicad_pcb")
    r = choose_reference(t, classify(t), "TP1.1")
    assert r.rule == "copper" and r.layer == "F.Cu" and r.point is not None
```

- [ ] **Step 2: Run the tests to verify they fail.** Run `python -m pytest tests/test_tracer.py -q`.
- [ ] **Step 3: Implement `tracer.py`.**
- [ ] **Step 4: Run the tests.** Expected: all pass.
- [ ] **Step 5: Commit.** Message: `feat: classify nets, trace the RF chain and choose port references`.

---

### Task 11: Project file and the `new` command

**Files:**
- Create: `src/kicad_rf_studio/core/project.py`, `src/kicad_rf_studio/cli.py`
- Test: `tests/test_project.py`, `tests/test_cli_new.py`

**Interfaces:**
- **`project.SCHEMA = 1`.**
- **`board_hash(path) -> str`:** the SHA-256 hex digest of the file's bytes.
- **`save_project(path: Path, data: dict) -> None`:** writes UTF-8 JSON with `indent=2` and `ensure_ascii=False`.
- **`load_project(path: Path) -> dict`:** raises `E_PROJECT_SCHEMA(path, found, expected)` on a schema mismatch.
- **`cli.main(argv: list[str] | None = None) -> int`:**
  - exits with 0 on success, 2 on `KrsError` (rendered to stderr) and 1 on any other exception (`E_INTERNAL`);
  - its first lines are `sys.stdout.reconfigure(errors="replace")` and `sys.stderr.reconfigure(errors="replace")`.

**`project.json`, schema 1:**

```json
{
  "schema": 1,
  "board": {"path": "<relative to project.json, forward slashes>", "sha256": "<hex>"},
  "f0_hz": 915000000.0, "harmonics": 3, "preset": "normal", "band_factor": 1.1, "t_max_s": 4e-08,
  "stackup": "<Stackup.to_json()>",
  "lid_height_mm": null,
  "classes": {"gnd_nets": [], "power_nets": [], "connectors": [], "shields": []},
  "chain": {"start": "U1.1", "end": "J1.1", "nets": [],
            "series": [{"ref": "C1", "pads": ["C1.1", "C1.2"], "nets": ["RF_A", "RF_B"], "value": "100pF"}],
            "shunt": []},
  "ports": [{"name": "P1", "signal": "U1.1", "rule": "ic",
             "reference": {"pad": "U1.2", "uuid": "<uuid>"}}]
}
```

- **Reference shapes:** a reference is `{"pad", "uuid"}`, or `{"point": [x, y], "layer": "F.Cu"}` for the copper rule, or `null`.
- **Board path:** when `os.path.relpath` fails across drives, store the absolute path and print `W_ABSOLUTE_BOARD_PATH`.
- **Defaults:**
  - `preset` defaults to `normal`. This is provisional: the owner sets the time policy after P0-C (spec §1.1);
  - band factor 1.1, T_max 40 ns, 3 harmonics.

**`new BOARD --start REF.PAD --end REF.PAD --f0 F [--harmonics N] [--preset draft|normal|strict] [--stackup NAME] [--lid-height MM] [-o PATH]`:**
1. Load the board.
2. **Stackup:**
   - `--stackup` takes a preset of the board's thickness, with `copper_layers=len(board.copper_layers)`;
   - otherwise the board's own stackup is used;
   - otherwise the command raises `E_NO_STACKUP`.
3. Classify the nets and footprints.
4. Trace the chain.
5. Choose the references for P1 (start) and P2 (end).
6. **Write `project.json`.** The output is `PATH/project.json`, or `./project.json` when `-o` is not given; the parent folders are created.
7. **Print one line for each of:**
   - every board warning;
   - `W_FILLS_AS_SAVED`;
   - `I_STACKUP`, `I_CLASSES`, `I_CHAIN`, `I_PORT` (once per port) and `I_DEFAULTS`;
   - `W_COPPER_WEIGHT`, when `stackup.nonstandard_copper()` is not empty;
   - `W_LID_HEIGHT_MISSING`, when shields exist and `--lid-height` is absent;
   - `W_NO_REFERENCE`, for each port without a reference;
   - `I_WROTE`.

- [ ] **Step 1: Write the failing tests**

```python
def run_new(tmp_path, *extra, board="lpf915.kicad_pcb", start="U1.1", end="J1.1", out=None):
    out = out or tmp_path / "proj"
    code = main(["new", str(FIX / board), "--start", start, "--end", end, "--f0", "915MHz", "-o", str(out), *extra])
    return code, out / "project.json"

def test_new_writes_project(tmp_path, capsys):
    code, pj = run_new(tmp_path, "--lid-height", "2.5")
    assert code == 0
    d = load_project(pj)
    assert (d["schema"], d["f0_hz"], d["harmonics"], d["preset"], d["band_factor"]) == (1, 915e6, 3, "normal", 1.1)
    assert d["t_max_s"] == pytest.approx(40e-9) and d["lid_height_mm"] == 2.5
    assert [p["ref"] for p in d["chain"]["series"]] == ["C1", "L1", "R1"]
    assert [p["signal"] for p in d["ports"]] == ["U1.1", "J1.1"] and d["stackup"]["source"] == "board"
    assert not Path(d["board"]["path"]).is_absolute() and len(d["board"]["sha256"]) == 64
    out = capsys.readouterr().out
    assert "Fills as saved" in out and "U1.2" in out

def test_new_warns_about_missing_lid_height(tmp_path, capsys):
    code, _ = run_new(tmp_path)
    assert code == 0 and "--lid-height" in capsys.readouterr().out

def test_new_refuses_board_without_stackup(tmp_path, capsys, mini_board_file):
    code = main(["new", str(mini_board_file("")), "--start", "A.1", "--end", "B.1", "--f0", "915MHz",
                 "-o", str(tmp_path / "p")])
    assert code == 2 and "--stackup" in capsys.readouterr().err

def test_single_trace_project(tmp_path):
    code, pj = run_new(tmp_path, board="coupon_gcpw_pads.kicad_pcb", start="TP1.1", end="TP2.1")
    d = load_project(pj)
    assert code == 0 and d["chain"]["series"] == [] and d["ports"][1]["rule"] == "copper"

def test_project_path_with_spaces_and_accents(tmp_path):
    out = tmp_path / "pasta com espaço" / "projeto ação"
    code, pj = run_new(tmp_path, out=out)
    d = load_project(pj)
    assert code == 0 and (out / d["board"]["path"]).resolve() == (FIX / "lpf915.kicad_pcb").resolve()

def test_unknown_pad_exit_code(tmp_path, capsys):
    code, _ = run_new(tmp_path, start="U1.99")
    assert code == 2 and "U1." in capsys.readouterr().err

def test_cli_survives_a_cp1252_console(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    code, _ = run_new(tmp_path, "--lid-height", "2.5")
    assert code == 0

def test_schema_mismatch(tmp_path):
    p = tmp_path / "project.json"; p.write_text('{"schema": 99}', encoding="utf-8")
    with pytest.raises(KrsError) as e:
        load_project(p)
    assert e.value.code == "E_PROJECT_SCHEMA"
```

- [ ] **Step 2: Run the tests to verify they fail.** Run `python -m pytest tests/test_cli_new.py tests/test_project.py -q`.
- [ ] **Step 3: Implement `project.py` and `cli.py`** (argparse with a `new` subcommand).
- [ ] **Step 4: Run the whole suite and the real command.**
  - Run `python -m pytest -q`. Expected: all pass.
  - Run `kicad-rf-studio new tests/fixtures/lpf915.kicad_pcb --start U1.1 --end J1.1 --f0 915MHz --lid-height 2.5 -o build/demo`. Expected: the printed summary, and `build/demo/project.json`.
- [ ] **Step 5: Commit.** Message: `feat: add project file and the new command`.
