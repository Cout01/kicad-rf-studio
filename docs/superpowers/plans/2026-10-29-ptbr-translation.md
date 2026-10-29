# pt-BR Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A user whose Windows shows Portuguese (Brazil), or whose gettext variables name pt_BR, gets the CLI's and the GUI's text in pt-BR with no setting to find, with no English word left in a sentence by a parameter, while everyone else, the KiCad helper's line and the test suite keep English.

**Architecture:**
- **One catalog, one choice, at import** (Tasks 1–3): `core/messages.py` picks the language once (the gettext variables when one is set, else Windows' display language through ctypes, else English) and binds stdlib gettext to it. A parameter that is a word becomes a `T_` code of the same `CATALOG`, which `render()` renders with its message, so events and `project.json` keep codes and identifiers; grammar that a word cannot carry splits the message. Task 2 builds the mechanism with the words a call site writes literally (reasons, fallbacks, job names, "none", None); Task 3 does the rest.
- **Files from a dev tool** (Tasks 4–5): `tools/catalog.py` (Babel, dev extra only) writes `po/kicad_rf_studio.pot` and `po/pt_BR.po` from `CATALOG` and compiles the committed `.mo`; stdlib tests keep the `.mo` equal to the `.po`, complete, and true to each msgid's fields, line breaks, identifiers and numbers; Task 5's implementer fills the `.po` by §6's glossary, this plan's additions and §6.2's tone, and an independent reviewer reads every message and every term in each sentence it fills.
- **What stays English or follows Qt** (Tasks 6–7): `english()` renders the helper's line and chain.s2p's what-if line; `gui.main` installs PySide6's `qtbase_<lang>.qm` while its window runs; `tests/test_gui.py` reads the window's lines through `control.text`, so it passes in pt-BR too, which Task 8's grabs, release check and CLI read confirm.

**Tech Stack:** Python ≥ 3.11 (dev venv 3.14.2). Stdlib: `gettext` (`translation`, `GNUTranslations`, `NullTranslations`), `ctypes` (`windll.kernel32.GetUserDefaultUILanguage`), `string.Formatter`, `ast.literal_eval`, `re`, `tomllib`. Babel 2.18.0, pinned (`Catalog`, `read_po`, `write_po`, `write_mo`), in `tools/catalog.py` and the dev extra only. PySide6-Essentials 6.12 (`QTranslator`, `QLibraryInfo.LibraryPath.TranslationsPath`), offscreen in tests. pytest, no pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-29-ptbr-translation-design.md` (binding, all of it), with Stage 1 §3.3 (events carry codes) and §3.5 (stdlib gettext, msgid = the English template, Babel dev-only) and Stage 2 §5.7 (`G_` codes in the same catalog; qtbase translations). Task 5 amends the Stage 1 spec's §1.1 and §3.5 (A-22). The research is git-ignored: `.superpowers/sdd/ptbr-research/r1-strings/findings.md` (every word parameter with file:line but tracer.py's "none", which this plan adds), `r2-tests/findings.md` (literal-English asserts, the pin, the catalog tests), `r3-glossary/findings.md`, `r4-qt-pack/findings.md` (QTranslator, Windows language APIs, packaging, the privacy gate on Babel's header).

**Branch:** `ptbr-translation`, from `main` at `178edf9`. This plan is `docs/superpowers/plans/2026-10-29-ptbr-translation.md`. Commands run from the repo root with `.venv/Scripts/python`.

**Before Task 1 (the controller):**
1. Branch `ptbr-translation` from `main`. `git diff --stat 178edf9 HEAD -- src tests tools pyproject.toml README.md` must print nothing; otherwise re-check this plan's line references first.
2. Commit this plan on the branch. Its rulings are its last section, `## Controller rulings (2026-10-29; binding)`.
3. After Task 8: the whole-branch review, then a local fast-forward merge into `main` and the branch deleted. Nothing is pushed.

Line references are `main`'s at `178edf9`. Where an earlier step or task has added lines above one, the place is found by its quoted text.

## Global Constraints

- **msgid = the English template** (Stage 1 §3.5): every user-facing string, term included, is a code of the one `CATALOG` in `src/kicad_rf_studio/core/messages.py`; gettext keys a translation by its template, so every template stays distinct (tested from Task 2). No `ngettext`, no `pgettext`.
- **Numbers keep the decimal point** in both languages (design §3): nothing is formatted by locale; the lid spin box keeps `QLocale.c()`; a msgstr keeps every dotted number of its msgid (Task 5's test).
- **Identifiers stay untranslated** (design §3): commands (`run`, `retune`, `setup-openems`…), options (`--stackup`, `-o`), presets (`draft`, `normal`, `strict`), stackup names, JSON keys and values, file and folder names, units, part values, refs, `REF.PAD`, `T_max`, symbols (Z0, εeff, f0, S21); the CLI's `:series`/`:shunt` syntax; `project.json` keeps `"board"`, verdicts, roles and rules as they are.
- **Events stay codes** (Stage 1 §3.3): a word parameter is a `T_` code in `events.jsonl` and in `KrsError.params`, rendered only when shown.
- **Stays English:** the helper's stderr and button.log line, ASCII but for paths (design §5.4), and chain.s2p's what-if line (§5.3), both through `english()`; argparse's own words, `detail()`'s text, tracebacks, gui.log's and cli.log's Python text, pip's output (design §3).
- **The tests pinned to English:** `os.environ["LANGUAGE"] = os.environ.get("KRS_TEST_LANGUAGE") or "en"` on the line after `import os` at the top of `tests/conftest.py`; `KRS_TEST_LANGUAGE=pt_BR` is for `tests/test_gui.py` only (design §7.2–7.3); tests elsewhere that assert literal English stay as they are.
- **Stdlib first:** gettext, ctypes, `string.Formatter`, `ast`; Babel (`babel==2.18.0`) only in `tools/catalog.py` and the dev extra, never imported by `src/` or `tests/` (Task 4's import probe).
- **Qt only offscreen** in tests (conftest sets `QT_QPA_PLATFORM`); no test shows a modal dialog; the `QTranslator` that `gui.main` installs is removed when it returns.
- **No real KiCad, Documents, KiCad settings or data folder:** tests keep conftest's autouse `no_kicad` and the `fake` fixture's data folder; Task 8 sets an isolated `LOCALAPPDATA` and `XDG_DATA_HOME` in the same PowerShell call as each command that runs the app; nothing starts KiCad.
- **No push and no upload;** the merge is local.
- **Tests:** test-first; tier (a) tests never run openEMS, KiCad, the network or a build; `KrsError` tests check `.code` and `.params`.
- **Full suite:** before every commit, `.venv/Scripts/python -m pytest -q` passes. It takes about 15 minutes, past the shell's 10-minute foreground cap: run it once in the background, with nothing beside it, and wait for its exit.
- **Privacy:** the pre-commit privacy gate runs on every commit (never `--no-verify`). No committed file holds an absolute user path, a drive letter followed by a colon and a slash, a UNC share, an e-mail address (not even a placeholder, Babel's included) or a private name. Task 8's commands name `$env:TEMP` folders only; the openEMS folder is typed in the call, never written into a file.
- **Files:** GPL-3.0-or-later; English code and docs; `# SPDX-License-Identifier: GPL-3.0-or-later` heads `tools/catalog.py` (`tests/test_repo.py` checks it).
- **Git:** no commit carries a co-author line; commit messages as given.
- **Workflow:** every implementer runs `graphify query "<question>"` (or `explain`, `path`) from the repo root before reading code, and `graphify update .` after each commit. Ponytail: the laziest solution that works, the repo's functions reused, the fewest files, the stdlib first, and a `ponytail:` comment naming its ceiling and upgrade on each corner cut.
- **Amendments:** A-22's lines end with "(A-22, pt-BR translation plan: controller recommendation, owner unavailable.)", and the Stage 1 spec's Status line gets one sentence.

## Review Focus

1. **A msgstr that changes what must stay as it is:** a field, a line break, a decimal point, a command, an option, quoted JSON, a file-dialog filter or a dialog label's "…". A field the msgstr adds makes `render()` raise KeyError, so a CLI line dies or a GUI status goes blank in pt-BR only; a decimal comma (W_GATE_LIMITS's "0,03") has a user type a number that project.json keeps as text; a filter moved from the end leaves a file dialog empty.
   - Checks: `test_every_translation_keeps_its_fields_and_line_breaks_with_no_spec_or_conversion` (Task 4) and `test_every_translation_keeps_the_identifiers_numbers_filters_and_ellipses` (Task 5), over the shipped `.mo`, in every suite.
2. **A stale or missing compiled catalog:** the `.po` edited without the tool, a `CATALOG` change not translated, an uncommitted `.mo`, or one the wheel leaves out. The UI turns English or half English with no warning.
   - Checks: `test_the_compiled_catalog_is_its_po_translated_and_ships_in_the_wheel` (Task 4: the `.mo` equals the `.po`'s translated pairs, which a fuzzy or uncompiled entry fails; the `.po`'s msgids equal `CATALOG`'s templates; package-data names the `.mo`); `test_the_pt_br_catalog_translates_every_template_and_nothing_else` (Task 5); Task 8's release check (`inspect_wheel` requires every tracked `src/` file, the `.mo` among them).
3. **An English word reaching a pt-BR sentence through a parameter** ("Redes GND: none", "Ilhas mais próximas: none", "Tampa da blindagem on"). Under the English pin a rendered assert passes whether a site passes the term or the old word, so the checks read the parameter itself.
   - Checks: Tasks 2 and 3's tests at each site, which assert the parameter is a `T_` code (test_board, test_runs, test_post_outputs, test_gui_control, test_tracer, test_cli_cost's gapless section, test_gui's two start failures, test_gates, test_cost_model, test_post_waves, test_post_chain, test_pool, test_project, test_run_dir); `test_every_literal_reason_fallback_and_job_name_is_a_term` (Task 2), which scans `src/` for a reason, fallback or job name written as a word; `test_with_pt_br_active_new_leaves_no_english_word_parameter_in_its_lines` (Task 5); Task 8's reading of lpf915's `new` and `cost` in pt-BR.
4. **A Portuguese label that a widget cuts, or a quoted label that is not its widget's** ("O botão Stop…" beside a button that reads "Parar").
   - Checks: `test_a_label_quoted_in_a_message_is_its_widgets_label_and_kicads_labels_are_kicads` (Task 5); `test_the_window_fits_1200_by_800_and_its_tabs_need_no_scrolling` (Task 7), run in both languages; Task 8's thirteen grabs read at 1200 × 800.
5. **The wrong language picked:** an English Windows with a pt-BR regional format, `LANG=C` or `pt_PT` on Linux, a pt-BR Windows or Git Bash running the suite.
   - Checks: Task 1's `test_with_no_gettext_variable_windows_display_language_picks_the_language` (0x0409 with `locale.getlocale` faked to pt_BR gives English; 0x0816 English); Task 4's `test_the_package_catalog_follows_the_gettext_variables` (C, C.UTF-8 and pt_PT give English; `LANGUAGE=en` wins over `LANG=pt_BR.UTF-8`) and its pinned-language assertion.

---

## File structure

```
src/kicad_rf_studio/core/messages.py   # T1 LOCALE, _ui_language, _languages, language; T2 _render, reason, the first
                                       #   T_ terms; T3 the other terms and the splits; T6 english
tests/conftest.py                      # T1 the pin; T5 the pt_br fixture
README.md                              # T1 After installing: English on a Portuguese Windows; T4 Development step 7
src/kicad_rf_studio/{cli,runs,pipeline,button}.py, core/{post/outputs,kicad/tracer}.py, gui/window.py
                                       # T2 reasons, fallbacks, job names, "none"
src/kicad_rf_studio/{cli,runs,pipeline}.py, core/{project,mesh/gates,post/waves,kicad/board,model/parts}.py,
  gui/{control,window}.py              # T3 the other word parameters; T6 button.main, pipeline.write_outputs
tools/catalog.py                       # T4 (Babel)
po/kicad_rf_studio.pot, po/pt_BR.po    # T4 written by the tool; T5 translated
src/kicad_rf_studio/locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo   # T4 compiled, committed; T5 recompiled
pyproject.toml                         # T4 babel in the dev extra; the .mo in package-data
src/kicad_rf_studio/gui/__init__.py    # T6 qtbase, which main installs and removes
tests/test_sexpr.py                    # T1–T5 the catalog and language tests
tests/test_{board,runs,post_outputs,gui_control,pool,tracer,cli_cost,cli_new}.py   # T2
tests/test_{cli_new,project,gates,cost_model,post_waves,post_chain,board,pool,runs,run_dir,gui_control}.py  # T3
tests/test_gui_control.py, tests/test_cli_new.py   # T5
tests/test_button.py, tests/test_run.py   # T6
tests/test_gui.py                      # T2 two tests; T4 the import probe; T6; T7
docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md   # T5 A-22
```

---

### Task 1 [code]: The language choice and the English pin

**Files:**
- Modify: `src/kicad_rf_studio/core/messages.py` (imports, L4–6; module docstring, L2–3; the binding, L327–328), `tests/conftest.py` (L1–3), `README.md` (After installing: a bullet after "Uninstall", L64).
- Test: `tests/test_sexpr.py` (after `test_render_translates_the_template_and_then_fills_it_in`, the file's end).

**Interfaces:**
- Consumes: `gettext.translation(domain, localedir, languages, fallback=True)`, which reads LANGUAGE, LC_ALL, LC_MESSAGES and LANG itself when `languages` is None and stops at `C`.
- Produces, in `core/messages.py`: `LOCALE = Path(__file__).resolve().parents[1] / "locale"`; `_ui_language() -> int`; `_languages() -> list[str] | None`; `_translation`, bound with `_languages()`; `language() -> str`. In `tests/conftest.py`: the pin.

- [ ] **Step 1: Write the failing tests,** in `tests/test_sexpr.py` (imports gain `gettext`, `locale`, `os`, `sys`):

```python
GETTEXT_VARIABLES = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")


@pytest.fixture
def no_gettext_variable(monkeypatch):
    for name in GETTEXT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(("ui", "chosen"), [
    (0x0416, ["pt_BR"]),  # Portuguese (Brazil)
    (0x0816, ["en"]),  # Portuguese (Portugal) is not pt-BR (design 3)
    (0x0409, ["en"]),  # an English Windows, whatever its regional format (Review Focus 5)
    (0, ["en"])])  # not Windows
def test_with_no_gettext_variable_windows_display_language_picks_the_language(no_gettext_variable, monkeypatch, ui,
                                                                              chosen):  # pt-BR design 4
    monkeypatch.setattr(messages, "_ui_language", lambda: ui)
    monkeypatch.setattr(locale, "getlocale", lambda *a: ("pt_BR", "cp1252"))  # the regional format is never read
    assert messages._languages() == chosen


@pytest.mark.parametrize("name", GETTEXT_VARIABLES)
def test_a_gettext_variable_wins_over_windows_display_language(no_gettext_variable, monkeypatch, name):
    monkeypatch.setattr(messages, "_ui_language", lambda: 0x0416)
    monkeypatch.setenv(name, "")  # empty is unset, as gettext reads it
    assert messages._languages() == ["pt_BR"]
    monkeypatch.setenv(name, "C")
    assert messages._languages() is None  # gettext reads it itself (Task 4 runs C and pt_BR.UTF-8)


def test_language_names_the_catalog_that_loaded(monkeypatch):  # pt-BR design 4: for Qt's translator and the tests
    class PtBr(gettext.NullTranslations):
        def info(self):
            return {"language": "pt_BR"}

    monkeypatch.setattr(messages, "_translation", gettext.NullTranslations())
    assert messages.language() == "en"
    monkeypatch.setattr(messages, "_translation", PtBr())
    assert messages.language() == "pt_BR"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' display language")
def test_windows_display_language_is_read_through_ctypes():
    assert 0 < messages._ui_language() <= 0xFFFF  # a LANGID


def test_the_suite_pins_its_language_before_anything_reads_it():  # pt-BR design 4, 7.2
    assert os.environ["LANGUAGE"] == (os.environ.get("KRS_TEST_LANGUAGE") or "en")
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_sexpr.py -q`. Expected: FAIL: `AttributeError: ... has no attribute '_ui_language'` (monkeypatch), `... 'language'`, and `KeyError: 'LANGUAGE'`.
- [ ] **Step 3: Implement** in `core/messages.py`:
  - imports gain `ctypes`, `os`, `sys`; `LOCALE` as above, before `CATALOG`.
  - `_ui_language()`: "Windows' display language, a LANGID (0x0416: Portuguese (Brazil)); 0 elsewhere." `ctypes.windll.kernel32.GetUserDefaultUILanguage()` when `sys.platform == "win32"`, else 0.
  - `_languages()`: "gettext's languages (pt-BR design 4): None when LANGUAGE, LC_ALL, LC_MESSAGES or LANG is set and not empty, which gettext then reads itself; else ["pt_BR"] when Windows' display language is Portuguese (Brazil), and ["en"] for any other. Never the regional format, which is the wrong signal." One element only: a list such as ["en_US", "pt_BR"] makes gettext skip the missing English and load pt_BR (r4). It carries `# ponytail: one LANGID, Portuguese (Brazil)'s; another language adds its own here, or reads GetUserPreferredUILanguages' names ("-" to "_")`.
  - the binding: `_translation = gettext.translation("kicad_rf_studio", localedir=LOCALE, languages=_languages(), fallback=True)`.
  - `language()`: "The language the catalog speaks (pt-BR design 4), for Qt's translator and the tests: the loaded .mo's Language header, "en" without one." `_translation.info().get("language", "en")`, with `# ponytail: the .mo's Language header names it (tools/catalog.py writes it from the .po's name); a .mo without one reads as English`.
  - the module docstring gains: "The language is picked once, at import (_languages)."
- [ ] **Step 4: The pin.** `tests/conftest.py`'s first lines become:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import os

# pt-BR design 4: before conftest's imports, which load core.messages (it binds its language at import), and inherited
# by every process a test starts; KRS_TEST_LANGUAGE=pt_BR runs tests/test_gui.py in pt-BR (design 7.3)
os.environ["LANGUAGE"] = os.environ.get("KRS_TEST_LANGUAGE") or "en"

import json
```

  followed by its other imports as they are (`import os` leaves their list).
- [ ] **Step 5: The README.** After installing gains, after its "Uninstall" bullet: "- **English on a Portuguese Windows:** kicad-rf-studio speaks the language that `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` or `LANG` names when one is set, else Brazilian Portuguese when Windows' display language is Portuguese (Brazil), else English. To keep English, run `setx LANGUAGE en` once and restart KiCad; git and other programs that read `LANGUAGE` turn English too. On Linux, put `export LANGUAGE=en` in your profile."
- [ ] **Step 6: Run them again.** `.venv/Scripts/python -m pytest tests/test_sexpr.py tests/test_repo.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/messages.py tests/conftest.py tests/test_sexpr.py README.md
git commit -m "feat(i18n): the language comes from the gettext variables, else Windows' display language, and the tests pin English (pt-BR design 4)"
graphify update .
```

---

### Task 2 [code]: Reasons, fallbacks, job names, "none" and None become terms

**Files:**
- Modify: `src/kicad_rf_studio/core/messages.py` (G_NONE, L243; the `T_` group's first entries after E_KICAD_OTHER_BOARD, L324; `render`, L331–333; the comment, `_REASONS` and `reason`, L336–348), `cli.py` (`_list`, L49; L118, L274, L276), `runs.py` (L52; `check_job`, L343–356; L413), `pipeline.py` (L253, L283, L416, L900), `core/post/outputs.py` (L224), `core/kicad/tracer.py` (`unknown_pad`, L107–111), `button.py` (L104, L176, L266, L291), `gui/window.py` (L290, L609, L718, L756).
- Test: `tests/test_sexpr.py`, `test_board.py`, `test_runs.py`, `test_post_outputs.py`, `test_gui_control.py`, `test_pool.py`, `test_tracer.py`, `test_cli_cost.py`, `test_cli_new.py`, `test_gui.py`.

**Interfaces:**
- Consumes: Task 1's `messages` module; `reason`'s callers above; `cli._list`, `cli.new`, `cli.save_project`; `runs.check_job(job, result, name, settings)`; `tracer.unknown_pad(board, name)`; `pipeline.load(path) -> (project, board, geom, notes)` and `pipeline.readout_2d(geom)`; the window's `start`, `apply`, `applied` and New's lid box; `control.start`, `control.apply`; `test_cli_cost.new_project`.
- Produces: `_render(translation, code: str, params: dict) -> str` and `render(code: str, **params) -> str`; `reason(error: Exception, fallback: str = "T_CANNOT_READ") -> str`, a `T_` code; the 17 `T_` codes of Step 3 (CATALOG: 332 codes); in `tests/test_sexpr.py`, `ROOT`, for Task 4.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_sexpr.py` (imports gain `re`, `from pathlib import Path`): the reason test (L113–120) becomes:

```python
@pytest.mark.parametrize("error, code, text", [
    (FileNotFoundError(2, "x"), "T_FILE_NOT_FOUND", "file not found"),
    (IsADirectoryError(21, "x"), "T_NOT_A_FILE", "not a file"),
    (PermissionError(13, "x"), "T_PERMISSION_DENIED", "permission denied"),
    (FileExistsError(17, "x"), "T_EXISTS_AS_FILE", "already exists as a file"),
    (NotADirectoryError(20, "x"), "T_EXISTS_AS_FILE", "already exists as a file"),  # a folder on the way is a file
    (UnicodeDecodeError("utf-8", b"\xe9", 0, 1, "invalid continuation byte"), "T_NOT_UTF8", "not UTF-8 text"),
    (OSError(22, "x"), "T_CANNOT_READ", "cannot be read"), (OSError(), "T_CANNOT_READ", "cannot be read")])
def test_a_file_error_has_a_short_reason_by_its_class(error, code, text):  # a code, rendered when shown
    assert reason(error) == code and render(code) == text
```

  and gains, at the file's end:

```python
ROOT = Path(__file__).resolve().parents[1]


def test_every_template_is_its_own_msgid_and_a_term_takes_no_field():  # pt-BR design 5.1: gettext keys on it
    assert len(set(CATALOG.values())) == len(CATALOG)  # T_NONE takes G_NONE's "none"
    assert [code for code in CATALOG if code.startswith("T_") and "{" in CATALOG[code]] == []  # rendered bare


def test_a_term_parameter_renders_in_the_language_and_none_as_unknown(monkeypatch):  # pt-BR design 5.1
    assert render("E_UNKNOWN_PAD", name="X", candidates="T_NONE") == render("E_UNKNOWN_PAD", name="X",
                                                                            candidates="none")
    assert render("E_LOCKED", lock="L", run=None, started=None) == render("E_LOCKED", lock="L", run="unknown",
                                                                           started="unknown")
    assert render("I_WROTE", path="T_max") == "Wrote T_max."  # only a code of CATALOG is a term

    class Translation:
        def gettext(self, msgid):
            return {"none": "—"}.get(msgid, msgid)

    monkeypatch.setattr(messages, "_translation", Translation())
    assert render("E_UNKNOWN_PAD", name="X", candidates="T_NONE").endswith(": —.")


def test_every_literal_reason_fallback_and_job_name_is_a_term():  # pt-BR design 5.1; Review Focus 3
    text = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "src").rglob("*.py")))
    words = r'reason\(\w+, "(?!T_)[^"]*"|reason="(?!T_)[^"]*"|check_job\(.*?, "(?!T_)[^"]*"'
    assert re.findall(words, text) == []  # each found with its call: make the word a T_ code
```

  - `tests/test_board.py`: L120, L121, L124 and L139 compare with `"T_FILE_NOT_FOUND"`, `"T_NOT_A_FILE"`, `"T_NOT_UTF8"` and `"T_PERMISSION_DENIED"` (L125–127's `str(e.value)` keeps its English under the pin).
  - `tests/test_runs.py` L105: `[("{", "T_NOT_JSON"), ("[]", "T_NOT_A_JSON_OBJECT")]`. `tests/test_post_outputs.py` L169: `"reason": "T_PERMISSION_DENIED"`. `tests/test_gui_control.py` L168 and L205: `"T_FILE_NOT_FOUND"`.
  - `tests/test_pool.py`: L105's `"setup"` becomes `"T_JOB_SETUP"`, and L113 and L117 pass `"T_JOB_SETUP"` to `check_job`.
  - `tests/test_tracer.py` L264: `e.value.params["candidates"] == "T_NONE"` (its `str(e.value)` keeps "Closest pads: none." under the pin).
  - `tests/test_cli_cost.py` (imports gain `readout_2d` from `kicad_rf_studio.pipeline`): `test_a_microstrip_has_no_gap_and_its_mask_lowers_z0` (L132–136) names its project `pj = new_project(tmp_path, "coupon_ms_masked")`, runs `main(["cost", str(pj)])` as before, and ends with `assert [p["gap_mm"] for c, p in readout_2d(load(pj)[2]) if c == "I_2D_SECTION"] == ["T_NONE"]`.
  - `tests/test_cli_new.py` (imports gain `KrsError`), at the file's end:

```python
def test_a_project_folder_that_cannot_be_written_says_so(tmp_path, monkeypatch):  # pt-BR design 5.1: not "read"
    def refused(*args):
        raise OSError(22, "x")

    monkeypatch.setattr(cli, "save_project", refused)
    with pytest.raises(KrsError) as e:
        cli.new(LPF, "U1.1", "J1.1", 915e6, output=tmp_path / "p")
    assert (e.value.code, e.value.params["reason"]) == ("E_OUTPUT_PATH", "T_CANNOT_WRITE")
```

  - `tests/test_gui.py`: L477's `render("G_NONE")` becomes `render("T_NONE")`. Add, after `test_a_process_that_cannot_start_or_ends_without_its_end_event_says_so`:

```python
def test_a_program_that_cannot_start_for_another_reason_cannot_be_started(window, tmp_path, monkeypatch):
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()  # pt-BR design 5.1: not "read"
    w = window()
    w.open_project(pj)
    opened(w)
    failed = render("G_START_FAILED", program=w.prefix[0], reason="T_CANNOT_START")

    def refused(*args):
        raise OSError(22, "x")

    monkeypatch.setattr(control, "start", refused)
    w.cost_button.click()
    assert w.proc is None and w.cost_status.text() == failed
    monkeypatch.setattr(control, "apply", refused)  # Apply's retune, the window's other start
    w.apply()
    until(lambda: w.tick() or w.applying is None)  # apply()'s own tick may already have read its end
    assert w.results.retune_status.text() == failed
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_sexpr.py tests/test_board.py tests/test_runs.py tests/test_post_outputs.py tests/test_gui_control.py tests/test_pool.py tests/test_tracer.py tests/test_cli_cost.py tests/test_cli_new.py -q` and `.venv/Scripts/python -m pytest tests/test_gui.py -q -k "another_reason or new_from_a_board"`. Expected: FAIL: the reason test and the parameter compares with English words, "Closest pads: T_NONE." in the term test, the scan listing cli.py's, runs.py's, pipeline.py's, button.py's, outputs.py's and window.py's words, and `KeyError: 'T_NONE'` in the GUI test.
- [ ] **Step 3: CATALOG.** G_NONE goes. The `T_` group opens after E_KICAD_OTHER_BOARD with these entries, in this order (Task 3 closes it):

```python
    # T_: a word a message takes as a parameter, rendered with it (pt-BR design 5.1); no T_ template has a field
    "T_FILE_NOT_FOUND": "file not found",
    "T_NOT_A_FILE": "not a file",
    "T_PERMISSION_DENIED": "permission denied",
    "T_EXISTS_AS_FILE": "already exists as a file",
    "T_NOT_UTF8": "not UTF-8 text",
    "T_NOT_JSON": "not JSON",
    "T_CANNOT_READ": "cannot be read",
    "T_CANNOT_WRITE": "cannot be written",
    "T_CANNOT_START": "cannot be started",
    "T_CANNOT_MAKE": "cannot be made",
    "T_HOLDS_A_RUN": "already holds a run",
    "T_NOT_A_JSON_OBJECT": "not a JSON object",
    "T_JOB_SETUP": "setup",
    "T_JOB_XML": "xml",
    "T_JOB_CALIBRATION": "calibration",
    "T_NONE": "none",
    "T_UNKNOWN": "unknown",
```

- [ ] **Step 4: `render` and `reason`.**
  - `_render(translation, code, params)`: "`code`'s template from `translation`, filled with `params`; a parameter that is a T_ code of CATALOG is shown as that term from `translation`, and None as T_UNKNOWN's (pt-BR design 5.1)." A str starting with `"T_"` that is a key of CATALOG; `# ponytail: a parameter equal to a T_ code renders as that term (a net named T_NONE would): design 5.1's accepted limit`. `render(code, **params)` returns `_render(_translation, code, params)`; its docstring adds "its T_ parameters too".
  - `_REASONS` pairs each class with its code (`"T_FILE_NOT_FOUND"` … `"T_NOT_JSON"`); `reason`'s default fallback is `"T_CANNOT_READ"`; its docstring: "The T_ code of a short phrase for an OSError, …; `fallback`, a T_ code, for any other error." The comment above `_REASONS` names every user: "The `reason` of E_BOARD_UNREADABLE, E_PROJECT_UNREADABLE, E_SETTINGS_UNREADABLE, E_OUTPUT_PATH (and G_OUTPUT_PATH, its GUI wording), E_RESULTS_WRITE, E_RUN_DIR, E_HANDOFF_WRITE, E_GUI_START, E_PLUGIN_WRITE, G_START_FAILED and G_SAVE_FAILED".
- [ ] **Step 5: The call sites,** each passing a code where it passed a word:
  - `cli.py`: `_list` returns `", ".join(names) or "T_NONE"`; L118 `reason(e, "T_CANNOT_WRITE")` (a write error: design 5.1); L274 `reason(e, "T_CANNOT_MAKE")`; L276 `reason="T_HOLDS_A_RUN"`.
  - `runs.py`: L52 `reason="T_NOT_A_JSON_OBJECT"`; L413 `"T_JOB_CALIBRATION"`; `check_job`'s docstring says `name` is "a T_ code (a tool may pass its own word, shown as it is)", since `tools/make_waves.py` passes "setup", "P1" and "P2".
  - `pipeline.py`: L253 `"T_JOB_SETUP"`; L283 `"T_NONE" if s.gap is None`; L416 `reason(err, "T_CANNOT_WRITE")`; L900 `"T_JOB_XML"`.
  - `core/post/outputs.py` L224 `reason(err, "T_CANNOT_WRITE")`; `core/kicad/tracer.py` L111 `or "T_NONE"`, its docstring adding "(T_NONE when none is close)".
  - `button.py`: L104, L266 and L291 `reason(e, "T_CANNOT_WRITE")`; L176 `reason(e, "T_CANNOT_START")`.
  - `gui/window.py`: L290 `render("T_NONE")`; L609 and L718 `reason(e, "T_CANNOT_START")` (`reason(error, …)` at L718); L756 `reason(e, "T_CANNOT_WRITE")`.
- [ ] **Step 6: Run them again.** Step 2's commands. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(i18n): reasons, fallbacks, job names, \"none\" and None are T_ terms rendered with their message, and file errors fall back to their own verb (pt-BR design 5.1)"
graphify update .
```

---

### Task 3 [code]: The other word parameters, the splits and the fixture labels

**Files:**
- Modify: `src/kicad_rf_studio/core/messages.py` (CATALOG's I_STACKUP L54, I_PORT L59, I_LID L62; the rest of the `T_` group after Task 2's), `cli.py` (the import, L30–32; the notes, L120–138), `core/project.py` (`shown_reference`'s docstring, L68–70; the expectation texts, L164–203, L211, L230), `core/mesh/gates.py` (`mesh_with_lint`, L52–63), `core/post/waves.py` (L92), `pipeline.py` (L145), `runs.py` (`install_command`, L62–66; L351), `core/kicad/board.py` (L194), `core/model/parts.py` (L52), `gui/control.py` (after `GUI`, L36; `text`, L246–249), `gui/window.py` (L41).
- Test: `tests/test_cli_new.py`, `test_project.py`, `test_gates.py`, `test_cost_model.py`, `test_post_waves.py`, `test_post_chain.py`, `test_board.py`, `test_pool.py`, `test_runs.py`, `test_run_dir.py`, `test_gui_control.py`.

**Interfaces:**
- Consumes: Task 2's `_render`, `render` and `T_` codes; `pipeline.VERDICTS`, `stoprule.KEPT`; `gates.mesh_with_lint` (the reasons of `rule.lint_hits`); `pipeline.port_gates`; `waves.layout`; `parts.c_box_of`; `runs.install_command`, `runs.WINDOWS`, `runs.check_job`; `project._FIELDS`, `_check`, `check_project`, `shown_reference`; `cli._part_note`; `control.GUI`, `control.text`; `window.FIXTURES`.
- Produces: the 40 `T_` codes and 5 split codes of Step 3 (CATALOG: 376 codes); `runs.install_command() -> str`, `"T_INSTALL_WINDOWS"` or `"T_INSTALL_LINUX"`; `cli._stackup_note(stackup) -> tuple[str, dict]`, `cli._port_note(port: dict) -> tuple[str, dict]`; `control.FIXTURE_LABELS = {"series": "G_FIXTURE_SERIES", "shunt": "G_FIXTURE_SHUNT"}`; in `tests/test_run_dir.py`, `events(run_dir: Path, **match) -> list[dict]`, for Task 7.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_cli_new.py`: L284, L341 and L407's `render("I_LID", state="on")` become `render("I_LID_ON")`; L637's becomes `render("I_LID_OFF" if "1" in extra else "I_LID_ON")`; L315's line becomes `"Stackup: board, dielectric 0.73 mm, εr 4.4; no mask."` and its test is renamed `test_a_stackup_without_a_mask_says_so`; L403–404 become `"Port P1: signal TP1.1, no reference."` and `"Port P2: signal TP2.1, no reference."`.
  - `tests/test_project.py` (imports gain `render`): L109–110 become `assert (e.value.code, {**e.value.params, "expected": render(e.value.params["expected"])}) == ("E_PROJECT_FIELD", {"path": str(pj), "field": field, "expected": expected})`; L139 compares `render(e.value.params["expected"])` in place of `e.value.params["expected"]`; L190–192 as L109–110. `render` of a non-code raises KeyError, so each proves a `T_EXPECT_` code with that English.
  - `tests/test_gates.py`: `"on edge"` becomes `"T_ON_EDGE"` at L114 and L363 (L116's render keeps its text through the term).
  - `tests/test_cost_model.py`: every `"end": "reference"` and `"end": "signal"` (L40, L41, L43, L65–66) becomes `"end": "T_END_REFERENCE"` and `"end": "T_END_SIGNAL"`.
  - `tests/test_post_waves.py` (imports gain `CATALOG`, `from kicad_rf_studio.pipeline import VERDICTS`, `from kicad_rf_studio.stoprule import KEPT`): L114's verdict becomes `"T_DIVERGED"`; add `test_each_verdict_whose_s_is_not_kept_has_its_term`: `assert {"T_" + v.upper() for v in VERDICTS.keys() - KEPT} <= CATALOG.keys()`.
  - `tests/test_post_chain.py` L132: `(None, "T_MISSING")`. `tests/test_board.py` L509: `p["kind"] == "T_HATCHED_ZONE"`. `tests/test_pool.py` L104: `"unset"` becomes `"T_UNSET"`.
  - `tests/test_runs.py`:

```python
@pytest.mark.parametrize(("windows", "code", "text"), [
    (True, "T_INSTALL_WINDOWS", "kicad-rf-studio setup-openems <openEMS folder>"),
    (False, "T_INSTALL_LINUX", "update_openEMS.sh <prefix> --python with this venv active (see README)")])
def test_the_install_hint_is_a_term_and_reads_as_before(monkeypatch, windows, code, text):  # pt-BR design 5.1
    monkeypatch.setattr(runs, "WINDOWS", windows)
    assert runs.install_command() == code and render(code) == text
```

  - `tests/test_run_dir.py`: `events` (L19–20) takes a filter, which Task 7 reuses, and a test joins the file's end:

```python
def events(run_dir, **match):
    """The events of `run_dir` whose fields equal `match` (all of them without one), in order."""
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [e for e in map(json.loads, lines) if all(e[k] == v for k, v in match.items())]
```

```python
def test_a_word_parameter_stays_a_code_in_the_event_and_reads_as_its_term(tmp_path, capsys, fake, monkeypatch):
    # pt-BR design 5.1 and Stage 1 3.3: a fresh machine's calibration cannot load openEMS
    monkeypatch.setenv("KRS_FAKE_EXIT", "2")
    monkeypatch.delenv("CSXCAD_INSTALL_PATH", raising=False)
    pj, run_dir = new_project(tmp_path, "coupon_gcpw_pads", preset="draft"), tmp_path / "r"
    capsys.readouterr()
    assert main(["cost", str(pj), "--run-dir", str(run_dir)]) == 2
    (message,) = events(run_dir, code="E_OPENEMS_DLL")
    assert (message["kind"], message["params"]) == ("message", {"value": "T_UNSET",
                                                                "command": runs.install_command()})
    err = capsys.readouterr().err
    assert render("E_OPENEMS_DLL", **message["params"]) + "\n" in err and "T_" not in err
```

  - `tests/test_gui_control.py` (imports gain `from kicad_rf_studio.core import messages`):

```python
def test_the_gui_names_a_fixture_by_its_combo_label_not_the_cli_syntax(monkeypatch):  # pt-BR design 5.1
    class Translation:
        def gettext(self, msgid):
            return {"series": "SERIES-LABEL", "shunt": "SHUNT-LABEL"}.get(msgid, msgid)

    monkeypatch.setattr(messages, "_translation", Translation())
    line = control.text("W_S2P_FIXTURE", {"ref": "C3", "path": "p", "named": "series", "fits": "shunt"})
    assert line == render("G_S2P_FIXTURE", ref="C3", path="p", named="SERIES-LABEL", fits="SHUNT-LABEL")
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_cli_new.py tests/test_project.py tests/test_gates.py tests/test_cost_model.py tests/test_post_waves.py tests/test_post_chain.py tests/test_board.py tests/test_pool.py tests/test_runs.py tests/test_run_dir.py tests/test_gui_control.py -q`. Expected: FAIL, first with `KeyError: 'I_LID_ON'`, `KeyError: 'text'` (an expectation that is still a phrase) and parameters still English.
- [ ] **Step 3: CATALOG.** The five split entries below take their places: I_STACKUP_NO_MASK after I_STACKUP, I_PORT_POINT and I_PORT_NO_REFERENCE after I_PORT, I_LID_ON and I_LID_OFF in I_LID's place (L62). The other entries close the `T_` group after Task 2's T_UNKNOWN, in this order:

```python
    "I_STACKUP_NO_MASK": "Stackup: {source}, dielectric {thickness_mm} mm, εr {epsilon_r}; no mask.",
    "I_PORT_POINT": "Port {name}: signal {signal}, reference ({x}, {y}) on {layer} ({rule}).",
    "I_PORT_NO_REFERENCE": "Port {name}: signal {signal}, no reference.",
    "I_LID_ON": "Shield lid on: \"lid\": null in project.json means on when harmonics > 1; true or false forces it.",
    "I_LID_OFF": "Shield lid off: \"lid\": null in project.json means on when harmonics > 1; true or false forces it.",
    "T_UNSET": "unset",
    "T_MISSING": "missing",
    "T_SOURCE_BOARD": "board",
    "T_HATCHED_ZONE": "hatched zone",
    "T_END_REFERENCE": "reference",
    "T_END_SIGNAL": "signal",
    "T_ON_EDGE": "on edge",
    "T_INSIDE_TOO_CLOSE": "inside too close",
    "T_OUTSIDE_CLOSER": "outside closer",
    "T_DIVERGED": "diverged",
    "T_GROWTH": "growth",
    "T_UNCLASSIFIED": "unclassified",
    "T_STOPPED": "stopped",
    "T_INSTALL_WINDOWS": "kicad-rf-studio setup-openems <openEMS folder>",
    "T_INSTALL_LINUX": "update_openEMS.sh <prefix> --python with this venv active (see README)",
    "T_EXPECT_TEXT": "text",
    "T_EXPECT_ABOVE_0": "a number above 0",
    "T_EXPECT_FLAG": "true or false",
    "T_EXPECT_TWO_NAMES": "two names",
    "T_EXPECT_CLASS": "a list of names, or null (computed from the board)",
    "T_EXPECT_ROLE": "port, copper, open, grid or curve_port",
    "T_EXPECT_MODEL": "null, or package (text) with esl_h, esr_ohm and cp_f (numbers of 0 or more)",
    "T_EXPECT_S2P": "null, or file (text) and connection (series or shunt)",
    "T_EXPECT_PARTS": "a list of parts",
    "T_EXPECT_WHOLE_ABOVE_0": "a whole number above 0",
    "T_EXPECT_PRESET": "draft, normal or strict",
    "T_EXPECT_MESH_N": "a whole number of 2 or more",
    "T_EXPECT_KIND": "mask, copper or dielectric",
    "T_EXPECT_0_OR_MORE": "a number of 0 or more",
    "T_EXPECT_ABOVE_0_OR_NULL": "a number above 0, or null",
    "T_EXPECT_0_OR_MORE_OR_NULL": "a number of 0 or more, or null",
    "T_EXPECT_LAYERS": "a list of layers",
    "T_EXPECT_LID_HEIGHT": 'a number above 0, or null ("lid": false leaves the lid out)',
    "T_EXPECT_LID": "true, false or null",
    "T_EXPECT_NAMES": "a list of names",
    "T_EXPECT_RULE": "connector, ic, copper or null",
    "T_EXPECT_REFERENCE": "a pad, a point or null",
    "T_EXPECT_PORTS": "a list of ports",
    "T_EXPECT_DT_FLOOR": "a number above 0 and at most 1",
    "T_EXPECT_OBJECT": "an object",
```

- [ ] **Step 4: The call sites,** each passing a code where it passed a word:
  - `cli.py`: the notes' I_STACKUP entry becomes `_stackup_note(stackup)`, their I_PORT entries `*map(_port_note, ports)`, and I_LID `("I_LID_ON" if harmonics > 1 else "I_LID_OFF", {})`; `shown_reference` leaves the import.
    - `_stackup_note(stackup)`: "The stackup as `new` prints it: I_STACKUP, or I_STACKUP_NO_MASK without a mask; the board's own as T_SOURCE_BOARD (project.json keeps "board")." It takes over the dielectric and mask lookups (L121–122).
    - `_port_note(port)`, beside `_part_note`: "A port as `new` prints it: I_PORT with a pad reference, I_PORT_POINT with a point on a layer (KiCad's frame, as stored; x and y as f"{v:.3f}"), I_PORT_NO_REFERENCE with none (a port with no reference has no rule)."
  - `core/project.py`: each expectation text in `_TEXT` … `_FIELDS`, `_check` (L211) and `check_project` (L230) becomes the `T_EXPECT_` code whose template is that text; `shown_reference`'s docstring says "as the port map shows it" (it serves only `outputs.port_map`, an English file).
  - `core/mesh/gates.py` L63: `reason="T_" + hit.reason.upper()`, with `# ponytail: the term by name; a new reason in rule.lint_hits needs its T_ code`; its docstring's `("on edge")` becomes `(T_ON_EDGE)`.
  - `core/post/waves.py` L92: `verdict="T_" + job["verdict"].upper()`, with `# ponytail: the term by name; test_post_waves requires one for each verdict whose S is not kept`.
  - `pipeline.py`: L145's ends `("T_END_REFERENCE", rc, rw), ("T_END_SIGNAL", sc, sw)`.
  - `runs.py`: `install_command` returns `"T_INSTALL_WINDOWS" if WINDOWS else "T_INSTALL_LINUX"` (docstring: "The T_ code of how to give this Python openEMS, as the E_OPENEMS_* messages say it"); L351 `or "T_UNSET"`.
  - `core/kicad/board.py` L194 `"kind": "T_HATCHED_ZONE"` (KiCad's own tokens, gr_text and the like, stay); `core/model/parts.py` L52 `value="T_MISSING"`.
  - `gui/control.py`: `FIXTURE_LABELS` after `GUI`, with the comment "an S2P fixture combo's label code by its data"; `text` gains, before its return, `if code == "W_S2P_FIXTURE": params = {**params, "named": render(FIXTURE_LABELS[params["named"]]), "fits": render(FIXTURE_LABELS[params["fits"]])}`, and its docstring adds "W_S2P_FIXTURE's fixtures named by the combo's labels, not the CLI's syntax (pt-BR design 5.1)".
  - `gui/window.py`: L41 `FIXTURES = tuple(control.FIXTURE_LABELS.items())`.
- [ ] **Step 5: Run them again.** Step 2's command. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(i18n): every other word passed as a parameter is a T_ term, grammar splits I_LID, I_STACKUP and I_PORT, and the GUI names a fixture by its combo's label (pt-BR design 5.1)"
graphify update .
```

---

### Task 4 [code]: The catalog files and `tools/catalog.py`

**Files:**
- Create: `tools/catalog.py`; `po/kicad_rf_studio.pot`, `po/pt_BR.po` and `src/kicad_rf_studio/locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo`, all three written by the tool.
- Modify: `pyproject.toml` (the dev extra, L15; package-data, L27); `README.md` (Development setup: a step 7 after step 6, L157); `tests/test_gui.py` (the import probe, L63).
- Test: `tests/test_sexpr.py`.

**Interfaces:**
- Consumes: Task 1's `LOCALE`; Tasks 2–3's CATALOG (376 codes); Task 2's `ROOT`.
- Produces: `tools/catalog.py` (`main(argv: list[str]) -> int`, run as `python tools/catalog.py [LANG...]`; `write(path: Path, catalog: Catalog) -> None`); in `tests/test_sexpr.py`, for Task 5: `PT_PO`, `PT_MO`, `po_pairs(text: str) -> dict[str, str]`, `mo_pairs(path: Path = PT_MO) -> dict[str, str]`, `fields(text: str) -> set[tuple[str, str, str | None]] | None`.

- [ ] **Step 1: Write the failing tests,** in `tests/test_sexpr.py` (imports gain `ast`, `subprocess`, `tomllib`):

```python
PT_PO = ROOT / "po" / "pt_BR.po"
PT_MO = messages.LOCALE / "pt_BR" / "LC_MESSAGES" / "kicad_rf_studio.mo"


def po_pairs(text):
    """A .po's msgid → msgstr pairs, its header's ("") among them: each string's quoted lines joined (Babel escapes only
    the backslash, tab, CR, LF and double quote, which literal_eval reads alike)."""
    def join(block):
        return "".join(ast.literal_eval(line) for line in block.splitlines())
    return {join(i): join(s) for i, s in re.findall(r'^msgid ((?:".*"\n)+)msgstr ((?:".*"\n)+)', text, re.M)}


def mo_pairs(path=PT_MO):
    """A compiled catalog's msgid → msgstr pairs, its header left out."""
    with path.open("rb") as f:  # ponytail: GNUTranslations' private _catalog, stable since Python 2: no public list
        return {k: v for k, v in gettext.GNUTranslations(f)._catalog.items() if k}


def fields(text):
    """Each replacement field of `text` as (name, format spec, conversion); None for a brace str.format refuses."""
    try:
        return {(name, spec, conv) for _, name, spec, conv in string.Formatter().parse(text) if name is not None}
    except ValueError:  # an unbalanced brace: a mismatch, named by its msgid
        return None


def test_the_compiled_catalog_is_its_po_translated_and_ships_in_the_wheel():  # pt-BR design 7.1, 7.2; RF 2
    text = PT_PO.read_text(encoding="utf-8")
    assert set(po_pairs(text)) - {""} == set(CATALOG.values())  # after a change to CATALOG, run tools/catalog.py
    assert mo_pairs() == {i: s for i, s in po_pairs(text).items() if i and s}  # after a .po edit, the same
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]
    assert "locale/*/LC_MESSAGES/*.mo" in data["kicad_rf_studio"]  # the wheel compiles nothing (design 7.1)


def test_every_translation_keeps_its_fields_and_line_breaks_with_no_spec_or_conversion():  # design 3, 7.2; RF 1
    assert [m for m, s in mo_pairs().items() if (fields(s), s.count("\n")) != (fields(m), m.count("\n"))] == []


@pytest.mark.parametrize(("env", "shown"), [
    ({"LANG": "pt_BR.UTF-8"}, "pt_BR"),  # a Linux desktop's: no code (design 4)
    ({"LANGUAGE": "en", "LANG": "pt_BR.UTF-8"}, "en"),  # LANGUAGE first: the README's way to keep English
    ({"LANG": "C"}, "en"), ({"LC_ALL": "C.UTF-8"}, "en"),  # Review Focus 5
    ({"LANG": "pt_PT.UTF-8"}, "en")])  # pt-PT is not pt-BR (design 3)
def test_the_package_catalog_follows_the_gettext_variables(env, shown):  # pt-BR design 4, 7.1
    base = {k: v for k, v in os.environ.items() if k not in GETTEXT_VARIABLES}
    probe = "from kicad_rf_studio.core import messages; print(messages.language())"
    out = subprocess.run([sys.executable, "-I", "-c", probe], env={**base, **env}, capture_output=True, text=True)
    assert out.stdout.strip() == shown, out.stderr
```

  Task 1's `test_the_suite_pins_its_language_before_anything_reads_it` gains a last line, `assert messages.language() == os.environ["LANGUAGE"]  # a misplaced pin loads Windows' pt-BR here`. In `tests/test_gui.py`, the import probe's set (L63) gains `'babel'` (the line wraps), with the comment "babel: tools/catalog.py's alone (pt-BR design 7.1)".
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_sexpr.py -q`. Expected: FAIL with `FileNotFoundError` for `po/pt_BR.po` and the `.mo`, and `pt_BR` printed as `en`.
- [ ] **Step 3: pyproject.** `dev = ["pytest>=8", "babel==2.18.0"]`; `kicad_rf_studio = ["data/**/*.json", "locale/*/LC_MESSAGES/*.mo"]`. Install Babel into the dev venv: `.venv/Scripts/python -m pip install "babel==2.18.0"`.
- [ ] **Step 4: `tools/catalog.py`,** which no tier (a) test runs (tests never import Babel), written as given:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""The message catalog's files (pt-BR design 7.1), run from the repo root with the dev venv's Python after a change to
CATALOG or to a .po: `python tools/catalog.py [LANG...]`. It writes po/kicad_rf_studio.pot from core.messages.CATALOG,
each entry's code its extracted comment (`pybabel extract` cannot read a dict's values); updates each po/<lang>.po from
it, making one for each LANG named that has none (a new or changed template comes back with an empty msgstr, the old
pair kept at the file's end as an obsolete #~ entry; a line it cannot parse stops it with a PoFileError naming the
line); and compiles each .po's translated entries into src/kicad_rf_studio/locale/<lang>/LC_MESSAGES/kicad_rf_studio.mo,
which is committed: the wheel compiles nothing. No header it writes holds an address or a date: Babel's defaults hold
placeholder addresses, one of which the privacy gate's e-mail rule matches, and a date would change every file on every
run. Babel, pinned in the dev extra (each header names its version), does the work; the package and the tests never
import it."""
import datetime
import io
import re
import sys
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po

from kicad_rf_studio import __version__
from kicad_rf_studio.core.messages import CATALOG, LOCALE

PO = Path(__file__).resolve().parents[1] / "po"
DOMAIN = "kicad_rf_studio"
UNSHARED = re.compile(  # the header lines that hold an address or a date
    rb'^"(Report-Msgid-Bugs-To|POT-Creation-Date|PO-Revision-Date|Last-Translator|Language-Team):.*\n', re.M)
# ponytail: Babel always writes a .mo's POT-Creation-Date, so it holds the epoch: no real date, and the same bytes from
# the same .po
EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def write(path: Path, catalog: Catalog) -> None:
    """`catalog` as a .po (or .pot) at `path`: each string on one line but split after each \\n, no python-format flag
    (Babel's guess at "4.6 % off"), and none of the UNSHARED header lines."""
    for message in catalog:  # Babel sets the flag again on every read, so it goes here
        message.flags.discard("python-format")
    out = io.BytesIO()
    write_po(out, catalog, width=0)
    path.write_bytes(UNSHARED.sub(b"", out.getvalue()))


def main(argv: list[str]) -> int:
    template = Catalog(domain=DOMAIN, project="kicad-rf-studio", version=__version__, fuzzy=False,
                       header_comment="# kicad-rf-studio's messages: tools/catalog.py writes this template.")
    for code, text in CATALOG.items():
        template.add(text, auto_comments=[code])
    PO.mkdir(exist_ok=True)
    write(PO / f"{DOMAIN}.pot", template)
    for lang in sorted({p.stem for p in PO.glob("*.po")} | set(argv)):
        path = PO / f"{lang}.po"
        if path.exists():
            with path.open("rb") as f:
                catalog = read_po(f, abort_invalid=True)  # a damaged line stops it, never a msgstr cut short
        else:
            catalog = Catalog(locale=lang, domain=DOMAIN, project="kicad-rf-studio", version=__version__, fuzzy=False,
                              header_comment=f"# kicad-rf-studio's messages in {lang}: translate each msgstr here, "
                                             "then run tools/catalog.py.")
        catalog.update(template, no_fuzzy_matching=True)  # never a neighbour's msgstr guessed into a new msgid
        write(path, catalog)
        catalog.msgid_bugs_address = catalog.last_translator = catalog.language_team = ""
        catalog.creation_date = catalog.revision_date = EPOCH
        mo = LOCALE / lang / "LC_MESSAGES" / f"{DOMAIN}.mo"
        mo.parent.mkdir(parents=True, exist_ok=True)
        with mo.open("wb") as f:
            write_mo(f, catalog)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 5: Write the files.** `.venv/Scripts/python tools/catalog.py pt_BR`. Expected: `po/kicad_rf_studio.pot` and `po/pt_BR.po` with 376 entries each, every pt_BR msgstr empty, each entry headed by `#. <CODE>`, the 204 entries with a field flagged `#, python-brace-format` and none `python-format`, the `.po`'s header naming `Language: pt_BR` and `Generated-By: Babel 2.18.0` and no address or date; a header-only `.mo`. Run it again: `md5sum po/* src/kicad_rf_studio/locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo` prints the same sums before and after (probed).
- [ ] **Step 6: The README.** Development setup gains: "7. After a change to a message in `src/kicad_rf_studio/core/messages.py`, run `python tools/catalog.py` (Babel comes with the dev extras), translate each entry of `po/pt_BR.po` whose msgstr is empty (a changed message's old translation stays at the file's end as a `#~` entry), then run it again: the tests refuse a catalog that is not complete and compiled. They run in English whatever your system's language, and `KRS_TEST_LANGUAGE=pt_BR` runs `tests/test_gui.py` in Brazilian Portuguese."
- [ ] **Step 7: Run them again.** `.venv/Scripts/python -m pytest tests/test_sexpr.py tests/test_repo.py -q` and `.venv/Scripts/python -m pytest tests/test_gui.py -q -k load_no_qt`. Expected: PASS (the field test finds no translation yet; Task 5's do).
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add tools/catalog.py po src/kicad_rf_studio/locale pyproject.toml README.md tests/test_sexpr.py tests/test_gui.py
git commit -m "feat(i18n): tools/catalog.py writes po/ from CATALOG and compiles the committed .mo with Babel, a pinned dev extra; the wheel ships it (pt-BR design 7.1)"
graphify update .
```

---

### Task 5 [translate]: The pt-BR catalog

**Files:**
- Modify: `po/pt_BR.po` (every msgstr), `src/kicad_rf_studio/locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo` (compiled), `tests/conftest.py` (the `pt_br` fixture, after `qapp`), `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (the Status line, L4; §1.1's UI-language row, L32; §3.5, after L169).
- Test: `tests/test_sexpr.py`, `tests/test_gui_control.py`, `tests/test_cli_new.py`.

**Interfaces:**
- Consumes: Task 4's `po/pt_BR.po`, `tools/catalog.py`, `mo_pairs`, `PT_MO`; Task 2's `render`; `control.GUI`.
- Produces: the compiled pt_BR catalog; conftest's `pt_br` fixture, for Task 6.

**Roles:** Task 5's implementer is the translator: its brief is this task with design §3 and §6 whole. The controller dispatches Step 5's reviewer and sends the findings it accepts back to that implementer, or, if it has ended, to a fresh one with the same brief.

- [ ] **Step 1: Write the failing tests.**
  - `tests/conftest.py` (imports gain `gettext`):

```python
@pytest.fixture
def pt_br(monkeypatch):
    """The pt-BR catalog active in this process whatever the pin (pt-BR design 7.2), with no fallback, so a missing .mo
    fails; the processes a test starts keep the pinned language."""
    from kicad_rf_studio.core import messages
    monkeypatch.setattr(messages, "_translation", gettext.translation("kicad_rf_studio", messages.LOCALE, ["pt_BR"]))
```

  - `tests/test_sexpr.py`:

```python
QUOTED = {  # a G_ message that names a widget, and that widget's label codes (design 6.2 rule 4)
    "G_LOCKED": ("G_STOP",), "G_RUN_START": ("G_STOP",), "G_WHAT_IF": ("G_VERIFY",), "G_NO_COST": ("G_RUN",),
    "G_COST_REUSED": ("G_RUN",), "G_PROJECT_EXISTS": ("G_OPEN",), "G_LID_HEIGHT_MISSING": ("G_TAB_ADVANCED",),
    "G_NO_REFERENCE": ("G_TAB_ADVANCED",), "G_PART_NO_MODEL": ("G_TAB_RESULTS",), "G_VERIFY_NONE": ("G_VERIFY",),
    "G_VERIFY_STALE": ("G_VERIFY",), "G_APPLY_FIRST": ("G_VERIFY", "G_APPLY"),
    "G_VERIFY_VALUE": ("G_VERIFY", "G_TAB_ADVANCED", "G_TAB_RESULTS", "G_APPLY"),
    "G_PROJECT_FIELD": ("G_TAB_ADVANCED", "G_NEW")}
# what a msgstr keeps of its msgid (design 3, 6.2 rule 3): a command in backticks, quoted JSON, an option, a file-dialog
# filter and a dotted number
KEEP = re.compile(r'`[^`]+`|"[^"]*"|--[a-z][\w-]*|\(\*\.\w+\)|\d+(?:\.\d+)+')


def test_the_pt_br_catalog_translates_every_template_and_nothing_else():  # pt-BR design 7.2; Review Focus 2
    assert set(mo_pairs()) == set(CATALOG.values())


def test_a_label_quoted_in_a_message_is_its_widgets_label_and_kicads_labels_are_kicads():  # design 6.1, 6.2; RF 4
    pt = mo_pairs()
    for text in (CATALOG.get, lambda code: pt[CATALOG[code]]):  # English, then pt-BR
        assert [code for code, labels in QUOTED.items() if not all(text(label) in text(code) for label in labels)] == []
    for code in ("E_KICAD_UNREACHABLE", "I_PLUGIN_NEXT"):
        assert "Preferências › Plug-ins › Ativar a API do KiCad" in pt[CATALOG[code]], code
    assert "Configuração da placa › Empilhamento físico" in pt[CATALOG["E_DIELECTRIC_THICKNESS"]]
    assert [m for m in CATALOG.values() if "(B)" in m and "Preencher todas as zonas (B)" not in pt[m]] == []


def test_the_pt_br_catalog_keeps_the_glossarys_nevers():  # design 6.1 (preencher, executar, gate), 6.2 rule 1
    pt = mo_pairs()
    never = re.compile(r"\b(recarreg\w*|rod(ar|e|ando)|tu|favor|o usuário)\b", re.I)
    assert [msgid for msgid, msgstr in pt.items() if never.search(msgstr)] == []
    gates = [CATALOG[code] for code in ("I_GATES_PASSED", "G_END_BLOCKED") if CATALOG[code] in pt]  # a gate, in prose
    assert [m for m in gates if "checage" not in pt[m].lower() or "verifica" in pt[m].lower()] == []


def test_every_translation_keeps_the_identifiers_numbers_filters_and_ellipses():  # design 3, 6.2 rules 3, 6; RF 1
    pt = mo_pairs()
    assert [m for m, s in pt.items()
            if any(k not in s for k in KEEP.findall(m)) or m.endswith("…") != s.endswith("…")] == []
    filters = [CATALOG[code] for code in ("G_OPEN_FILTER", "G_BOARD_FILTER", "G_S2P_FILTER") if CATALOG[code] in pt]
    assert [m for m in filters if not pt[m].endswith(m.split()[-1])] == []  # Qt reads the filter at the end
```

  - `tests/test_gui_control.py` (imports gain `from test_sexpr import mo_pairs`): `test_every_gui_wording_keeps_its_cli_params_and_drops_terminal_syntax` checks both languages with one regex; its loop becomes:

```python
    pt = mo_pairs()
    for cli_code, gui_code in control.GUI.items():  # later tasks' entries too
        assert fields(gui_code) <= fields(cli_code), gui_code  # rendered with the CLI line's own params
        for text in (CATALOG[gui_code], pt[CATALOG[gui_code]]):  # English, then pt-BR (pt-BR design 7.2)
            assert not re.search(r"`|--[a-z]|(?<!\w)-o |PROJECT", text), gui_code  # "Abra-o" is no -o
```

  - `tests/test_cli_new.py`, after `test_ports_without_a_reference`:

```python
def test_with_pt_br_active_new_leaves_no_english_word_parameter_in_its_lines(tmp_path, capsys, mini_board_file,
                                                                             pt_br):  # design 3; Review Focus 3
    board = mini_board_file(footprint("TP1", pad(1, "SIG")) + footprint("TP2", pad(1, "SIG", x=5)), stackup=NO_MASK)
    code = main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    words = set(re.findall(r"\w+", capsys.readouterr().out))  # no mask, no ground: none, board, the lid
    assert code == 0 and not words & {"none", "on", "off", "board", "unknown", "reference", "Port", "Stackup"}
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_sexpr.py tests/test_gui_control.py tests/test_cli_new.py -q -k "pt_br or quoted or identifiers or terminal_syntax"`. Expected: of the six tests this step adds or changes, the nevers and identifiers tests pass on the header-only catalog and the other four FAIL: 376 templates missing from the `.mo`, then `KeyError` on the first msgstr looked up (the sexpr test that `-k quoted` also picks passes).
- [ ] **Step 3: Translate.** Fill every msgstr of `po/pt_BR.po` in file order, in batches of about 60 entries, the `T_` group (the file's last 57 entries) as a batch of its own. Each batch is one Edit of a contiguous block: its `#.`, `#,` and `msgid` lines copied unchanged, only its `msgstr ""` lines filled; touch nothing else (the header among it). After each batch, `.venv/Scripts/python tools/catalog.py`, then `.venv/Scripts/python -m pytest tests/test_sexpr.py -q -k "fields or identifiers or nevers or compiled"`, which read a partial catalog, so a broken placeholder fails in its own batch; after the `T_` batch, run Step 5's listing and read each term in its sentences. One line per msgstr, `\n` where its msgid has one (G_ABOUT_TEXT, which the tool then splits after each `\n`: edit it in that form afterwards), `\"` for a double quote; the `#, python-brace-format` flags are Babel's, and only `{fields}` and `{{ }}` are placeholders. §6.1's glossary, the plan glossary below and §6.2's tone bind, and:
  - every `{field}` of the msgid, and no other, spelled as in the msgid (a field may move), `{{` and `}}` kept (W_STAIRCASED);
  - a msgstr equal to its msgid is still written (G_APP, units, E12, E24, MC/s): an empty msgstr is untranslated;
  - §3's identifiers as they are, in backticks or not: commands, options, presets, stackup names, JSON keys and values (`"lid": false`, null, true, port, copper, open, grid, curve_port, series, shunt, mask, connector, ic), openEMS's own `"none"` and `"outside"` and its type names (Box, LinPoly, CurvePort) in E_UNUSED_PRIMITIVE and W_UNUSED_PRIMITIVE, file and folder names (project.json, results/, STOP, launch.cmd, log.txt), numbers with their decimal point (4.6 %, 0.03, 4.7pF, 9.0.7), refs, REF.PAD, REF=VALUE, PROJECT, T_max, Edge.Cuts, Z0, εeff, f0, S11, S21, IL, RL, |ΔS|, σ_max, C_box, Ctrl+C; a file-dialog filter ends its msgstr with its `(*.json)` part (G_OPEN_FILTER, G_BOARD_FILTER, G_S2P_FILTER), and a msgid that ends in "…" ends its msgstr so;
  - `{role}` (I_PART, I_PART_NO_MODEL, G_PART_NO_MODEL, E_RETUNE_ROLE) and `{rule}` (I_PORT, I_PORT_POINT) are JSON values: quote them (papel "{role}", regra "{rule}");
  - a count never changes the sentence (rule 5), so the count fields, where 1 is common, take the label form ("harmônicos: {harmonics}", "tarefas simultâneas: {pool}"): {harmonics}, {pool}, {threads}, {runs}, {kept}, {parts}, {ports}, {count}, and I_BASIS's {converged}, {flat} and {t_max};
  - the E_ and W_ messages keep the CLI's `:series`, `:shunt` and `{fits}-thru`; in G_S2P_FIXTURE, `{fits}` and `{named}` are the fixture combo's labels (série, shunt), so its pt-BR reads with them and drops "{fits}-thru";
  - a label a G_ message names is its widget's pt-BR msgstr, word for word (`QUOTED`); G_ENDED's "Results" and G_NEW_NO_FOLDER's "New" stand for the Results and retune tab and the Create the project button, so write those labels whole; advice that reuses a button's words without naming the button (G_NO_RESULTS, G_RESULTS_STALE: "estimate the cost", "run") is advice in the imperative (rule 1); KiCad's paths are §6.1's with `›` (E_KICAD_UNREACHABLE's `>` too), and every "(B)" refill reads "Preencher todas as zonas (B)";
  - G_ABOUT_TEXT's notice is translated; the licence names ("GNU General Public License", "GNU Lesser General Public License") and the URL stay.
  - The `T_` terms fill a slot in other messages, so each is translated for its slot and the whole sentence reads. A slot that takes terms of different genders, or both a term and a value (a path, a time, a KiCad token), stands after a colon or in parentheses, and its terms are gender-free: a noun, a "de …" phrase, a clause or "—", never an adjective or a participle that must agree. So:
    - T_FILE_NOT_FOUND to T_NOT_A_JSON_OBJECT follow "…: {reason}." after a file, folder or program named before them: clauses that agree with no noun ("arquivo não encontrado", "permissão negada", "não foi possível gravar");
    - T_EXPECT_* follow "{field} is missing or is not {expected}": noun phrases, JSON words kept, "or" as "ou";
    - T_NONE is "—", a lone value after a label, in a list or in the lid box (I_CLASSES, I_CHAIN, I_2D_SECTION's gap, E_UNKNOWN_PAD's candidates): its slots mix genders (redes, blindagens, ilhas, altura; conectores, componentes); T_UNKNOWN, what Python held as None, is "—" too, in labelled slots: E_LOCKED, G_LOCKED and W_STALE_LOCK name their run as "(início: {started}; pasta: {run})" or "(pasta: {run})", and E_PROJECT_SCHEMA its {found} after a colon;
    - T_UNSET is CSXCAD_INSTALL_PATH's value, "não definida", in E_OPENEMS_DLL's "(CSXCAD_INSTALL_PATH: {value})"; T_MISSING is E_CBOX's value in parentheses;
    - T_SOURCE_BOARD follows "Empilhamento: " where a preset's name can stand ("da placa"); W_COPPER_DROPPED opens "A simulação deixa de fora: {kind} {uuid} em {layer}", {kind} being T_HATCHED_ZONE ("zona hachurada") or a KiCad token such as gr_text, and its advice names the copper ("se esse cobre conduz corrente, converta-o…");
    - T_END_REFERENCE and T_END_SIGNAL fill E_PORT_OPEN's "its {end} end" ("de referência", "de sinal"); T_ON_EDGE, T_INSIDE_TOO_CLOSE and T_OUTSIDE_CLOSER E_EDGE_LINT's "({axis}, {reason})";
    - T_DIVERGED, T_GROWTH, T_UNCLASSIFIED and T_STOPPED are nouns after a colon in E_RESULTS_JOB ("terminou assim: {verdict}": divergência, crescimento de energia, sem veredito, interrupção); T_JOB_SETUP, T_JOB_XML and T_JOB_CALIBRATION are "de …" phrases after E_WORKER_FAILED's noun ("O processo {job}": de configuração, de XML, de calibração);
    - T_INSTALL_WINDOWS and T_INSTALL_LINUX are the command after "Install it: {command}": its command words kept, "<openEMS folder>" and the prose translated.

  The plan glossary (adds to §6.1, by §6.1's own principles; the reviewer applies it too):

  | English | pt-BR | Note |
  | --- | --- | --- |
  | gate names (I_GATES_PASSED) | edge lint, fit2d; piso do passo de tempo, conectividade das portas, primitivas não usadas | edge lint and fit2d are names and stay; the other three describe their gates |
  | snapping (G_COL_SNAP) / its off (G_SNAP_OFF) | Série E / nenhuma | never "ajuste", which is retune's in the same tab |
  | teardrop / padstack / annotate | reforço da junção / empilhamento de ilhas / reanotar | KiCad's words ("Reanote a placa no KiCad") |
  | gap | espaçamento | never KiCad's "lacuna" |
  | edge | borda (the copper's) / aresta (the mesh's `{axis}` edge in I_COST_DT and E_DT_FLOOR) | |
  | package / verdict / flagged / outline | encapsulamento / veredito / sinalizado / contorno | `Edge.Cuts` stays |
  | S2P file | arquivo S2P | |
  | Controlled folder access (E_PLUGIN_WRITE) | Acesso controlado a pastas | Windows' own label |

  Tone rule 2, exactly: tabs, column headers, box titles, field labels and the Help menu are nouns; buttons are infinitives, and About's two items read "Sobre …", as Qt's own "Sobre o Qt". So "Run" (G_TAB_RUN) and "Run…" (G_RUN), "Board" (G_NEW_BOARD) and "board" (T_SOURCE_BOARD), "S2P file" (G_COL_S2P) and "S2P file…" (G_CHOOSE_S2P) differ in pt-BR, the only msgids that differ by case or "…" (probed).
- [ ] **Step 4: Compile and check.** `.venv/Scripts/python tools/catalog.py`, then Step 2's command and `.venv/Scripts/python -m pytest tests/test_sexpr.py -q`. Expected: PASS. A failing check names its msgid: fix that msgstr, compile again; a `PoFileError` names the `.po` line the tool cannot read.
- [ ] **Step 5: The independent review.** The controller writes the listing below to `.superpowers/sdd/2026-10-29-ptbr-listing.txt` (git-ignored) with `.venv/Scripts/python -X utf8 - > .superpowers/sdd/2026-10-29-ptbr-listing.txt`, the script on stdin: every msgstr, then each slot a term fills with each of its terms, the other fields "X" (probed: 618 lines).

```python
import gettext
import string

from kicad_rf_studio.core import messages
from kicad_rf_studio.core.messages import CATALOG, render

messages._translation = gettext.translation("kicad_rf_studio", messages.LOCALE, ["pt_BR"])
for code, text in CATALOG.items():  # every msgstr, a term as it renders
    print(f"{code}: {render(code) if code.startswith('T_') else messages._translation.gettext(text)}")
REASONS = ("T_FILE_NOT_FOUND T_NOT_A_FILE T_PERMISSION_DENIED T_EXISTS_AS_FILE T_NOT_UTF8 T_NOT_JSON T_CANNOT_READ "
           "T_CANNOT_WRITE T_CANNOT_START T_CANNOT_MAKE T_HOLDS_A_RUN T_NOT_A_JSON_OBJECT")
SLOTS = [  # (the messages, the field, the terms, None standing for T_UNKNOWN): every slot a term fills
    ("E_BOARD_UNREADABLE E_PROJECT_UNREADABLE E_SETTINGS_UNREADABLE E_OUTPUT_PATH G_OUTPUT_PATH E_RESULTS_WRITE "
     "E_RUN_DIR E_HANDOFF_WRITE E_GUI_START E_PLUGIN_WRITE G_START_FAILED G_SAVE_FAILED", "reason", REASONS.split()),
    ("E_PROJECT_FIELD G_PROJECT_FIELD", "expected", [c for c in CATALOG if c.startswith("T_EXPECT_")]),
    ("E_RESULTS_JOB", "verdict", "T_DIVERGED T_GROWTH T_UNCLASSIFIED T_STOPPED".split()),
    ("E_WORKER_FAILED", "job", "T_JOB_SETUP T_JOB_XML T_JOB_CALIBRATION".split()),
    ("E_PORT_OPEN", "end", "T_END_REFERENCE T_END_SIGNAL".split()),
    ("E_EDGE_LINT", "reason", "T_ON_EDGE T_INSIDE_TOO_CLOSE T_OUTSIDE_CLOSER".split()),
    ("E_OPENEMS_DLL", "value", ["T_UNSET"]), ("E_CBOX", "value", ["T_MISSING"]),
    ("E_OPENEMS_MISSING E_OPENEMS_OLD W_OPENEMS_UNTESTED E_OPENEMS_DLL E_APPCSXCAD_MISSING", "command",
     ["T_INSTALL_WINDOWS", "T_INSTALL_LINUX"]),
    ("W_COPPER_DROPPED", "kind", ["T_HATCHED_ZONE"]), ("I_STACKUP I_STACKUP_NO_MASK", "source", ["T_SOURCE_BOARD"]),
    *(("I_CLASSES", field, ["T_NONE"]) for field in ("gnd", "power", "connectors", "shields")),
    ("I_CHAIN", "series", ["T_NONE"]), ("I_CHAIN", "shunt", ["T_NONE"]), ("I_2D_SECTION", "gap_mm", ["T_NONE"]),
    ("E_UNKNOWN_PAD", "candidates", ["T_NONE"]), ("E_LOCKED G_LOCKED", "started", [None]),
    ("E_LOCKED G_LOCKED W_STALE_LOCK", "run", [None]), ("E_PROJECT_SCHEMA", "found", [None])]
for codes, field, terms in SLOTS:
    for code in codes.split():
        names = {name for _, name, _, _ in string.Formatter().parse(CATALOG[code]) if name}
        for term in terms:
            print(f"{code} {field}={term}: {render(code, **{**dict.fromkeys(names, 'X'), field: term})}")
```

  It then dispatches a fresh reviewer subagent with design §3 and §6, Step 3 of this task (its rules and the plan glossary), `po/pt_BR.po` and that listing; never the translator's notes. It checks the whole catalog for: glossary drift (one English term rendered two ways, but Step 3's three pairs; a KiCad term not KiCad's; "verificação" for a gate, which §6.1 keeps for verify; "região" for a zone); meaning (each msgstr says what its msgid says: no number, limit, condition or advice dropped); placeholders and identifiers; tone (rules 1–6); quoted labels and KiCad paths; each `T_` term read inside every sentence the listing fills with it; the same English phrase translated the same way throughout. It returns one line per finding, `CODE: what is wrong → the msgstr it proposes`, or "no findings". The translator applies each finding the controller accepts (a disagreement is settled by §6 and the plan glossary, the controller deciding), then Step 4 runs again.
- [ ] **Step 6: The spec (A-22).**
  - §1.1's row "| UI language | English. Every user-facing string is translatable from day one, and a pt-BR translation follows right after v1 |" becomes "| UI language | English, or Brazilian Portuguese where Windows' display language is Portuguese (Brazil) or the gettext variables name it; every user-facing string is a catalog code (A-22, pt-BR translation plan: controller recommendation, owner unavailable.) |".
  - §3.5 gains, after its Babel bullet: "- The language is the gettext variables' when one is set, else Windows' display language (Portuguese (Brazil) gives pt-BR), else English. A word passed as a parameter is a `T_` code of the catalog, rendered with its message. The catalog's sources are `po/` at the repo's root, and the compiled `.mo` is committed under the package's `locale/`; `tools/catalog.py` writes both with Babel, pinned in the dev extra. (A-22, pt-BR translation plan: controller recommendation, owner unavailable.)"
  - The Status line gains, at its end: " On 2026-10-29, the pt-BR translation plan amended §1.1 and §3.5 (A-22) the same way."
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add po src/kicad_rf_studio/locale tests/conftest.py tests/test_sexpr.py tests/test_gui_control.py tests/test_cli_new.py docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "feat(i18n): the pt-BR catalog, every message and term by the design's glossary and tone, independently reviewed; spec A-22 (pt-BR design 6; controller recommendation, owner unavailable)"
graphify update .
```

---

### Task 6 [code]: English where it stays, and Qt's own words

**Files:**
- Modify: `src/kicad_rf_studio/core/messages.py` (after `render`), `button.py` (import, L22; `main`'s line, L179), `pipeline.py` (the messages import, L34; `write_outputs`, L479–505), `gui/__init__.py` (imports, L12; `qtbase` after `forward`; `main`, L81–86).
- Test: `tests/test_button.py` (after `test_a_handoff_that_cannot_be_written_or_a_gui_that_cannot_start_is_its_own_line`), `tests/test_run.py` (after `test_three_external_ports_and_a_part_port_get_the_label_after_w_not_two_port`), `tests/test_gui.py` (after `test_the_gui_entry_runs_offscreen_and_logs_without_a_console`; imports gain `QCoreApplication`).

**Interfaces:**
- Consumes: Task 2's `_render`; Task 5's `pt_br` fixture and catalog; Task 1's `language()`; plan 3's `kicad` fixture and `HELPER_CODES`; `test_run.star_project(tmp_path, n)`.
- Produces: `english(code: str, **params) -> str`; `gui.qtbase(language: str)`, a `QTranslator` or None.

- [ ] **Step 1: Write the failing tests.** `tests/test_button.py` (imports gain `english`):

```python
def test_with_pt_br_active_the_helpers_line_stays_english_and_ascii(fake, kicad, pt_br, tmp_path, monkeypatch,
                                                                    capsys):  # pt-BR design 5.4
    k = kicad(version=(8, 0, 9))
    monkeypatch.setenv("KICAD_API_SOCKET", k.url)
    monkeypatch.setenv("KICAD_API_TOKEN", k.token)
    assert button.main() == 1
    line = english("E_KICAD_VERSION", version="8.0.9")
    assert line != render("E_KICAD_VERSION", version="8.0.9")  # pt-BR is active
    assert capsys.readouterr() == ("", line + "\n") and line.isascii()
    assert (fake / "button.log").read_text(encoding="utf-8").splitlines()[-1].endswith(" " + line)
    k = kicad()  # a GUI that cannot start: its reason, a term, in English too
    monkeypatch.setenv("KICAD_API_SOCKET", k.url)
    monkeypatch.setenv("KICAD_API_TOKEN", k.token)
    missing = tmp_path / "no-gui"
    monkeypatch.setattr(button, "gui_command", lambda handoff: [str(missing), "--handoff", str(handoff)])
    assert button.main() == 1
    err = capsys.readouterr().err
    assert err == english("E_GUI_START", program=str(missing), reason="T_FILE_NOT_FOUND") + "\n"
    assert err.replace(str(missing), "").isascii()
```

  `tests/test_run.py` (imports gain `english`):

```python
def test_with_pt_br_active_chain_s2p_keeps_the_english_what_if_line(tmp_path, pt_br):  # pt-BR design 5.3
    pj, project = star_project(tmp_path, 2)
    write_outputs(pj, project, "c")
    what_if = {"command": command_line("kicad-rf-studio", "verify", str(pj))}
    assert render("I_WHAT_IF", **what_if) != english("I_WHAT_IF", **what_if)  # pt-BR is active
    assert ("! " + english("I_WHAT_IF", **what_if)).encode() in (pj.parent / "results" / "chain.s2p").read_bytes()
```

  `tests/test_gui.py`:

```python
def test_qts_own_words_come_from_pyside6s_qtbase_translation():  # pt-BR design 5.2
    assert gui.qtbase("en") is None and gui.qtbase("xx") is None  # PySide6 ships a qtbase_en.qm: never loaded
    translator = gui.qtbase("pt_BR")
    assert Path(translator.filePath()).name == "qtbase_pt_BR.qm"
    assert translator.translate("QPlatformTheme", "&Yes") == "&Sim"


def test_gui_main_speaks_qts_words_in_its_language_and_leaves_none_behind(qapp, fake, monkeypatch):  # design 5.2
    monkeypatch.setattr(gui, "language", lambda: "pt_BR")
    seen = []
    QTimer.singleShot(0, lambda: (seen.append(QCoreApplication.translate("QPlatformTheme", "&Yes")), qapp.quit()))
    assert gui.main([]) == 0 and seen == ["&Sim"]
    assert QCoreApplication.translate("QPlatformTheme", "&Yes") == "&Yes"  # removed: the session's app is English
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_button.py tests/test_run.py -q -k pt_br` and `.venv/Scripts/python -m pytest tests/test_gui.py -q -k qts`. Expected: FAIL: `ImportError: cannot import name 'english'` at collection, and `AttributeError: module 'kicad_rf_studio.gui' has no attribute 'qtbase'`.
- [ ] **Step 3: English.**
  - `english(code, **params)` in `core/messages.py`: "The message for `code` in English whatever the language, its T_ parameters too: the button helper's line, which KiCad 10 shows decoded in a code page nobody has checked (pt-BR design 5.4), and chain.s2p's what-if line, in an ASCII file (5.3)." `_render(gettext.NullTranslations(), code, params)`.
  - `button.main`: `line = english(e.code, **e.params) if isinstance(e, KrsError) else english("E_INTERNAL", detail=detail(e))`; its docstring says "one English stderr line".
  - `pipeline.write_outputs`: chain.s{P}p's comments end with `[english("I_WHAT_IF", **what_if)] if label else []`; summary.png keeps `label`, the process's language (design 5.3); the docstring says the chain file's label line is English.
- [ ] **Step 4: Qt's own words,** in `gui/__init__.py`: `from kicad_rf_studio.core.messages import language`; `qtbase(language)`: "A QTranslator holding PySide6's own qtbase_<language>.qm (pt-BR design 5.2): Yes/No, context menus, spin box steps, About Qt; None for English, or for a language PySide6 has no file for." Qt imported inside it (`QLibraryInfo`, `QTranslator`); a parentless `QTranslator`, returned when `language != "en"` and `load(f"qtbase_{language}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))` succeeds. In `main`, after the listen and before the window: `translator = qtbase(language())`, installed with `app.installTranslator(translator)` when it is not None; `return app.exec()` becomes `code = app.exec()`, then `app.removeTranslator(translator)` when one was installed, then `return code` (probed), with `# ponytail: an exception before exec leaves the translator on the app; a try/finally if a caller ever reuses its app after one`. `main`'s docstring adds "Qt's own words follow the catalog's language while the window runs (qtbase)".
- [ ] **Step 5: Run them again.** `.venv/Scripts/python -m pytest tests/test_button.py tests/test_run.py -q` and `.venv/Scripts/python -m pytest tests/test_gui.py -q -k "qts or gui_entry"`. Expected: PASS (the English tests too: under the pin, `english` and `render` agree).
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src/kicad_rf_studio/core/messages.py src/kicad_rf_studio/button.py src/kicad_rf_studio/pipeline.py src/kicad_rf_studio/gui/__init__.py tests/test_button.py tests/test_run.py tests/test_gui.py
git commit -m "feat(i18n): the KiCad helper's line and chain.s2p's what-if line stay English and ASCII, and Qt's own words follow the catalog's language through PySide6's qtbase translations (pt-BR design 5.2-5.4)"
graphify update .
```

---

### Task 7 [code]: `tests/test_gui.py` passes in pt-BR

**Files:**
- Test: `tests/test_gui.py`.
- Modify, only when Step 2's guard fails in pt-BR: `src/kicad_rf_studio/gui/window.py`.

**Interfaces:**
- Consumes: Task 5's catalog; Task 3's `test_run_dir.events(run_dir, **match)` (each event's `t`, `kind`, `job`, `code`, `params`); `control.text(code, params)`.
- Produces: nothing new.

- [ ] **Step 1: Run it in pt-BR, failing.** `KRS_TEST_LANGUAGE=pt_BR .venv/Scripts/python -m pytest tests/test_gui.py -q` (several minutes; in the background if it nears the 10-minute cap). Expected: FAIL in the tests that hold Step 3's literals (main's lines at `178edf9`, moved down by Tasks 2 and 6's tests): English beside pt-BR lines.
- [ ] **Step 2: Write the guard test,** after `test_every_list_of_sentences_wraps_at_its_width`:

```python
def test_the_window_fits_1200_by_800_and_its_tabs_need_no_scrolling(window):  # pt-BR design 3; Review Focus 4
    w = window()
    hint = w.minimumSizeHint()  # English probed: 830 × 518
    assert hint.width() <= 1200 and hint.height() <= 800
    # a tab never elides or narrows (scroll buttons appear instead), so every label is whole when the bar fits
    assert w.tabs.tabBar().sizeHint().width() <= w.tabs.width()
```

  Run it: `.venv/Scripts/python -m pytest tests/test_gui.py -q -k tabs_need_no_scrolling`. Expected: PASS in English (a tab bar of about 600 px in a 1200-px window, probed). If it fails under `KRS_TEST_LANGUAGE=pt_BR` in Step 4, that is a layout defect: fix `window.py` test-first as Task 8's Step 4 says, and commit it with this task.
- [ ] **Step 3: The literals,** each through the catalog (imports gain `from test_run_dir import events`):
  - L153: after `lines = items(w.cost_lines)`, `main_cost = events(w.run_dir, kind="cost")[-1]`; the assertion's `lines[-1].startswith("Main cost: ")` becomes `main_cost["code"].startswith("I_COST_DRIVER_") and lines[-1] == control.text(main_cost["code"], main_cost["params"])`.
  - L166: `(cost_time,) = events(w.run_dir, code="I_COST_TIME")`, then `"Worst case: " in asked[0]` becomes `control.text(cost_time["code"], cost_time["params"]) in asked[0]`.
  - L170: `(p1,) = events(w.run_dir, kind="verdict", job=1)`, then `assert p1["code"] == "I_JOB_CONVERGED" and w.jobs.item(0, 4).text() == control.text(p1["code"], p1["params"])`.
  - L172: `(start,) = events(w.run_dir, code="I_RUN_START")`, then `assert start["params"]["runs"] == 2 and render("G_RUN_START", **start["params"]) in log`.
  - L213–214 and L578: `reason="file not found"` becomes `reason="T_FILE_NOT_FOUND"`.
  - L266: `stopped = events(first.run_dir, code="W_JOB_STOPPED")`, then `assert stopped and all(control.text(e["code"], e["params"]) in items(second.log) for e in stopped)`.
  - L356: `last = events(cost, kind="cost")[-1]`, then `items(w.cost_lines)[-1] == control.text(last["code"], last["params"])`.
  - L386: `res.lines[0][0] == "I_BASIS"` (L385 already compares every line through `control.text`).
  - L762: `control.text("W_S2P_FIXTURE", {"ref": "C3", "path": str(c3.resolve()), "named": "series", "fits": "shunt"}) in items(r.lines)`.
  - L907: `(cost_time,) = events(w.run_dir, code="I_COST_TIME")`, then `control.text(cost_time["code"], cost_time["params"]) in items(w.log)`.
  - L979–980: `expected="T_EXPECT_WHOLE_ABOVE_0"`.
  - L1074, in the opt-in real run: `(cost_time,) = events(w.cost, code="I_COST_TIME")`, then `control.text(cost_time["code"], cost_time["params"]) in asked[0]`.
- [ ] **Step 4: Run it in both languages.** `KRS_TEST_LANGUAGE=pt_BR .venv/Scripts/python -m pytest tests/test_gui.py -q`, then `.venv/Scripts/python -m pytest tests/test_gui.py -q`. Expected: PASS both, the Linux-only test and the real run skipped. Another line that fails only in pt-BR is fixed the same way (`control.text` over its event, or `render` of its code); a guard failure in pt-BR is a layout defect, fixed as Step 2 says.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add tests/test_gui.py
git commit -m "test(gui): the window's tests read its lines through control.text and pass in pt-BR too; the window fits 1200 x 800 and its tabs need no scrolling (pt-BR design 7.2)"
graphify update .
```

  (`src/kicad_rf_studio/gui/window.py` joins the `git add` when Step 2's fix touched it.)

---

### Task 8 [run]: The controller's checks

This task commits only the fixes Steps 4 and 7 may need. Every other file it makes is under `$env:TEMP`. It never starts KiCad, and never touches a real KiCad folder, the real Documents folder, KiCad's settings or the real data folder. The PowerShell tool keeps no variable between calls, so every block sets what it uses; run each as one call. A cmdlet that fails, even under `-ErrorAction SilentlyContinue`, makes the tool report exit 1, so the blocks test before they remove and print each exit code.

- [ ] **Step 1: The full suite at the branch tip,** pinned to English, once, in the background, waited on. Expected: all pass. Record the counts.
- [ ] **Step 2: `tests/test_gui.py` in pt-BR with grabs.** If `$env:TEMP\krs-font\krs_font.py` is gone, write it again as plan 3's Task 7 Step 5 gives it whole. Then, in the background, waited on:

```powershell
$env:KRS_TEST_LANGUAGE = "pt_BR"; $env:PYTHONPATH = "$env:TEMP\krs-font"; $env:KRS_GRAB_DIR = "$env:TEMP\krs-grabs-ptbr"
if (Test-Path $env:KRS_GRAB_DIR) { Remove-Item -Recurse -Force $env:KRS_GRAB_DIR }
.venv\Scripts\python.exe -X utf8 -m pytest tests/test_gui.py -q -p krs_font *> "$env:TEMP\krs-ptbr-gui.log"
"exit $LASTEXITCODE" | Add-Content "$env:TEMP\krs-ptbr-gui.log"
```

  Expected: every test passes but the two skips, and `krs-grabs-ptbr` holds the thirteen PNGs: project, cost, run, run-attached, run-lost, results, results-stale, new, handoff, refill, retune, verify, advanced.
- [ ] **Step 3: Read each PNG** with the Read tool, at 1200 × 800: every word Portuguese but the identifiers, legible, unclipped, not overlapping, not elided ("…" only on labels that open a dialog); numbers with their decimal point; buttons, tabs, column headers, combo items and status lines whole. A word-wrapped label's old height in a grab is an artifact of `grab()` (plan 1).
- [ ] **Step 4: Fix each layout defect** in `src/kicad_rf_studio/gui/window.py` (design 7.3), test-first where a widget property shows it: a test in `tests/test_gui.py` beside Task 7's guard, true in both languages, that fails under `KRS_TEST_LANGUAGE=pt_BR` before the fix (a header section narrower than its text, a status label without word wrap, the window's minimum past 1200 × 800). A defect that is a wrong word is fixed in `po/pt_BR.po` and compiled (Task 5's rules). Each fix: the full suite, then `git commit -m "fix(gui): <what> so the pt-BR window shows it whole (pt-BR design 7.3)"`, then Steps 2–3 again.
- [ ] **Step 5: The release check,** with the default TEMP, in the background, waited on: `.venv\Scripts\python.exe -X utf8 tools\release_check.py *> "$env:TEMP\krs-ptbr-release.log"; "exit $LASTEXITCODE" | Add-Content "$env:TEMP\krs-ptbr-release.log"`. Expected: `PASS build` (its inspection requires every tracked `src/` file, the `.mo` among them), `PASS install`, `PASS gui` (the GUI in this machine's language: pt-BR on this Windows, with Qt's translator), `PASS plugin`, `PASS privacy` (the `.po` scanned, clean); `exit 0`.
- [ ] **Step 6: The CLI in pt-BR on lpf915,** with no gettext variable, so Windows' display language picks it end to end, in an isolated data folder (on a machine whose display language is not pt-BR, set `$env:LANGUAGE = "pt_BR"` after the `foreach` line instead):

```powershell
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$iso = Join-Path $env:TEMP 'krs-ptbr-cli'
if (Test-Path $iso) { Remove-Item -Recurse -Force $iso }
New-Item -ItemType Directory -Force "$iso\local" | Out-Null
foreach ($n in 'LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG') { if (Test-Path "Env:$n") { Remove-Item "Env:$n" } }
$env:LOCALAPPDATA = "$iso\local"; $env:XDG_DATA_HOME = "$iso\local"; $env:KICAD_API_SOCKET = "ipc://$iso\none.sock"
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"  # typed here, never committed: the isolated folder records none
if ($env:LOCALAPPDATA -ne "$iso\local") { throw 'not isolated' }
.venv\Scripts\python.exe -X utf8 -m kicad_rf_studio new tests\fixtures\lpf915.kicad_pcb --start U1.1 --end J1.1 --f0 915MHz --lid-height 2.5 -o "$iso\lpf915"
"new exit $LASTEXITCODE"
.venv\Scripts\python.exe -X utf8 -m kicad_rf_studio cost "$iso\lpf915"
"cost exit $LASTEXITCODE"
```

  The README Tutorial's two commands. Expected: `new`'s summary, then `cost`'s 2D readout, its calibration lines (a fresh data folder: about a minute) and its cost lines, every one in pt-BR; `new exit 0`, and `cost exit 0` (a gate's verdict, exit 3, is read the same way). Read each line for an English word left inside a sentence; identifiers, units and symbols are §3's. Then delete `$iso`.
- [ ] **Step 7: Fix what Step 6 shows:** a word left English becomes a `T_` code at its call site with its test, as in Tasks 2–3, its msgstr translated as in Task 5 (the tool gives the new entry an empty msgstr); the full suite; `git commit -m "fix(i18n): <the word> is a T_ term (pt-BR design 5.1)"`; Step 6 again.
- [ ] **Step 8: Record and close.** The controller writes the counts, the grabs' verdicts, the release check's five lines and Step 6's reading into `.superpowers/sdd/2026-10-29-ptbr-rulings-and-minors.md` (git-ignored), with the open owner items (Not in this plan). Then the whole-branch review; any later commit reruns Step 1, Steps 2–3 when it touches `src/kicad_rf_studio/gui` or `po/`, and Step 5 when it touches `src/` or `tools/`. Delete `$env:TEMP\krs-grabs-ptbr`, the two logs and `.superpowers/sdd/2026-10-29-ptbr-listing.txt`.

---

## Not in this plan

- **argparse's own words** (usage, "error:", "invalid choice"): the stdlib's own gettext domain (design §3).
- **`detail()`'s text, tracebacks, gui.log and cli.log's Python text, pip's output** (design §3); `detail()` cuts a long exception with "…", the one non-ASCII character the helper's English line can still print (pre-existing).
- **The helper's line in pt-BR:** the owner's, once the click-through shows how KiCad 10 decodes an action's stderr (design §8).
- **A language menu in the GUI:** the owner's; it needs a settings.json key written under a lock, and three writers rewrite that file with none today (design §8).
- **A native speaker's review of `po/pt_BR.po`,** the glossary and this plan's additions first ("—" for T_NONE and T_UNKNOWN, "Série E", "espaçamento", "Preencher todas as zonas (B)" among them): the owner's, not blocking (design §6.3, §8).
- **Other languages, pt-PT included** (design §3): a new language is `python tools/catalog.py <lang>` and its translation; the gettext variables pick it with no code change, Windows' display language once `_languages()` knows its LANGID (its ponytail note), and the catalog tests read pt_BR's files only, a glob of `po/*.po` being their upgrade.
- **Numbers in the locale's format** (design §3, an anti-goal); **plurals** (`ngettext`, design §6.2 rule 5); **`pgettext`/msgctxt:** every template stays distinct instead (ruling).
- **English templates reworded so a label is quoted whole** (G_ENDED's "Results", G_NEW_NO_FOLDER's "New"): the English stays; Task 5 Step 3 has the translator write those labels whole, which `QUOTED` cannot check.
- **Translated preset names in the New combo, machine-read files** (Touchstone, summary.csv, events.jsonl, project.json) **and the docs** (design §3).
- **The rest of the suite in pt-BR:** tests outside `tests/test_gui.py` assert literal English under the pin (design §7.2).
- **plugin.json and summary.png:** they already follow the language of the process that writes them (design §5.3).
- **E_SETUP_FAILED, E_WORKER_FAILED and W_JOB_UNCLASSIFIED naming log.txt while the traceback is in err.txt** (r1 §7): not a translation matter; a carry-over item.

## Controller rulings (2026-10-29; binding)

The architect's rulings, revised after the four reviews (coverage, feasibility checked in a scratch folder, i18n correctness, quality and ponytail). Each is a controller recommendation, owner unavailable.

- Ruling: eight tasks, in this order: the language choice (1); the mechanism with the words a call site writes literally, reasons, fallbacks, job names, "none" and None (2); the other word parameters, the grammar splits and the fixture labels (3); the catalog files and tool (4); the translation (5); English for the helper and chain.s2p, and Qt's own words (6); `tests/test_gui.py` in pt-BR (7); the controller's checks (8). The draft's one word-parameter task touched 14 source and 15 test files, too much for one implementer and one review, so it splits where each half leaves the suite green and changes English output only where its own tests say (the fallbacks and "unknown" in 2, the new summary's three lines in 3); the draft's helper and Qt tasks, one function and two tests each in other files, merge, keeping eight full-suite runs. The terms come before the first `.pot`, so nothing is translated twice; Tasks 6–7 come after the translation, whose `.mo` their pt-BR tests need; the pin lands first, before any `.mo` can make a pt-BR shell's suite Portuguese — cost if wrong: one more catalog update.
- Ruling: `_languages()` returns None when any of LANGUAGE, LC_ALL, LC_MESSAGES or LANG is non-empty, so gettext reads them as today; else `["pt_BR"]` for LANGID 0x0416 from `GetUserDefaultUILanguage` through ctypes (`_ui_language()`, 0 off Windows) and `["en"]` for any other; one-element lists, since a list like `["en_US", "pt_BR"]` makes gettext skip the missing English (r4); one LANGID, its ponytail note naming the upgrade. Nothing hands the language to a child process: the CLI the GUI starts (`control._env`) and the GUI the helper starts inherit the same environment, on the same Windows user, so they choose alike — design §4 — cost if wrong: none.
- Ruling: `language()` is the loaded `.mo`'s Language header, "en" without one: the catalog that actually loaded, so `LANG=pt_PT` or a missing `.mo` reads as English; `tools/catalog.py` writes the header from the `.po`'s name, and Task 4's subprocess test runs it — cost if wrong: a `.mo` without the header leaves Qt's words English.
- Ruling: the conftest pin is an assignment, never `setdefault`, on the line after `import os`, before the imports that load `core.messages` through `fake_cli` and `runs`; no `# noqa` (the repo runs no linter); `KRS_TEST_LANGUAGE` serves `tests/test_gui.py` alone — design §4, r2 — cost if wrong: none.
- Ruling: `render()` recognises a `T_` parameter as a str that starts with `T_` and is a key of `CATALOG`, renders it from the same translation with no parameters, and shows None as T_UNKNOWN; no `T_` template has a field (tested) — design §5.1 — cost if wrong: a net named like a `T_` code shows as its term, design §5.1's accepted limit.
- Ruling: T_NONE replaces G_NONE, since gettext keys on the template and both read "none"; its pt-BR is "—", which no slot's gender changes (redes, blindagens, ilhas and the lid's height are feminine, conectores and the chain's parts masculine), so §5.1's agreement holds with no split, where KiCad's "nenhum" would clash in five of its nine slots; T_UNKNOWN is "—" too, in the labelled slots Task 5 Step 3 gives E_LOCKED, G_LOCKED, W_STALE_LOCK and E_PROJECT_SCHEMA — r3, the i18n review — cost if wrong: a native speaker changes two msgstrs.
- Ruling: I_LID splits into I_LID_ON and I_LID_OFF (design §5.1's agreement; "off" is G_SNAP_OFF's template too); I_STACKUP gains I_STACKUP_NO_MASK and I_PORT gains I_PORT_POINT and I_PORT_NO_REFERENCE, a point needing its own words around x, y and the layer, and "none (none)" being no sentence. The English of the last two improves to "; no mask." and ", no reference.", three test lines; `shown_reference` stays for the port map, an English file — cost if wrong: none.
- Ruling: verdicts and edge-lint reasons map to their terms by name (`"T_" + value.upper()`): the verdicts are tested complete from `VERDICTS.keys() - KEPT`; the three lint reasons are `rule.lint_hits`' literals, test_gates proving the mapping and gates.py's ponytail note asking a new one for its term (a test restating the three would only copy them). Job names, port ends, "unset", "missing", "hatched zone", "board", tracer's "none", the install hints and the reason fallbacks are codes at their call sites, and one scan of `src/` refuses a reason, fallback or job name written as a word (Task 2), since under the English pin a rendered assert passes either way. `project.json`, events and KiCad's own tokens keep their identifiers — cost if wrong: a new lint reason shows as its code until test_gates names it.
- Ruling: the 25 E_PROJECT_FIELD expectations become `T_EXPECT_` codes in `project.py`'s tuples, and `test_project.py` compares `render(params["expected"])` with the English phrase, which proves a code with that English in three edited asserts instead of 28 rows — cost if wrong: none.
- Ruling: the GUI's fixture message gets the combo's labels in `control.text`, from `control.FIXTURE_LABELS`, from which `window.FIXTURES` derives (window's `FIXTURE` is a column index, hence the name); `render()` renders only `T_` codes — design §5.1 — cost if wrong: none.
- Ruling: Python's None renders as T_UNKNOWN inside `render()`, one line for E_PROJECT_SCHEMA, E_LOCKED, W_STALE_LOCK, G_LOCKED and any later None, rather than at each call site; English reads "unknown" where it read "None" — design §5.1 — cost if wrong: a msgstr.
- Ruling: E_OUTPUT_PATH falls back to T_CANNOT_WRITE and G_START_FAILED to T_CANNOT_START at both its sites, a run's start and Apply's retune, each with a test that raises a bare `OSError(22, "x")` — design §5.1 — cost if wrong: none.
- Ruling: `english()` renders through the same `_render` with `NullTranslations`, terms included; `button.main` and chain.s2p's label use it, summary.png keeps `render()` — design §5.3, §5.4 — cost if wrong: none.
- Ruling: `tools/catalog.py` uses Babel's `Catalog`, `read_po` with `abort_invalid=True` (by default a msgstr wrapped over two lines comes back cut to its first characters with only a warning: probed), `write_po` (`width=0`) and `write_mo`; `update(template, no_fuzzy_matching=True)`, so a new or changed template comes back with an empty msgstr, which the completeness test names, and its old pair stays as an obsolete `#~` entry, where Babel's default fills a new msgid with a neighbour's msgstr marked fuzzy (probed: "cannot be deleted" given "não pode ser lido"); the `python-format` flag, Babel's guess at "4.6 % off", is dropped before each write, so Poedit or `msgfmt -c` never flags a correct msgstr; one regex drops the address and date header lines from the `.pot` and `.po`; the `.mo`'s header has the address fields emptied and both dates at the epoch; plain imports, the dev venv's editable install serving `kicad_rf_studio`; probed on the 376-code catalog: idempotent, 204 brace-format flags and no python-format one, the privacy gate's generic rules clean — design §7.1 — cost if wrong: a Babel that adds an address header shows at the commit's privacy gate.
- Ruling: Babel joins the dev extra pinned as `babel==2.18.0`: Babel writes its version into every header (`Generated-By`), so another version would rewrite all three files; a contributor bumps it on purpose and runs the tool once (Babel 2.18.0 needs Python ≥ 3.8, so CI's `.[dev]` installs it on the 3.11 floor); the import probe in `tests/test_gui.py` refuses it in the package — design §7.1 — cost if wrong: none.
- Ruling: the stdlib `.po` reader is one regex plus `ast.literal_eval` of each quoted line, and the `.mo` is read through `GNUTranslations._catalog`, private but stable since Python 2; `fields()` gives None for a brace `str.format` refuses and the field check compares line breaks too, so each failure names its msgid; the catalog tests are design §7.2's (complete, same fields with no spec or conversion, `.mo` equal to `.po`, which a fuzzy entry fails, and the G_ syntax rule, now one loop over both languages with `(?<!\w)-o ` so Portuguese "Abra-o" passes) plus the `.po` following `CATALOG`, package-data, the identifiers check, quoted labels, the glossary's nevers with "gate" as "checagem prévia", and `new` in pt-BR — cost if wrong: a Python that renames `_catalog` fails them loudly.
- Ruling: a msgstr keeps every backticked command, quoted JSON key or value, option, file-dialog filter and dotted number of its msgid, a "…" ends both or neither, and each filter ends its msgstr — design §3's identifiers and anti-goal, §6.2 rules 3 and 6; probed: every such span in `CATALOG` is an identifier, a placeholder or a number, so a correct translation passes, and a decimal comma, a dropped "…" or a moved filter fails — cost if wrong: a translation that must drop one waits for an exception in the test.
- Ruling: a `pt_br` fixture swaps `messages._translation` for the real pt_BR catalog with no fallback; processes a test starts keep the pinned language (r2) — cost if wrong: none.
- Ruling: `gui.qtbase(language)` returns a parentless `QTranslator` holding `qtbase_<language>.qm` from QLibraryInfo's translations path, None for "en" (PySide6 ships `qtbase_en.qm`, probed) or a missing file; `gui.main` installs it after a start that did not forward and before the window, and removes it with `removeTranslator` once `exec` returns (probed), plainly rather than through the local's destructor, so the session's QApplication stays English with no `gc.collect()` — design §5.2, r2's watch item — cost if wrong: none.
- Ruling: `tests/test_gui.py`'s literals go through `control.text` over the run's events, read by test_run_dir's `events` with the match filter Task 3 gives it, and I_BASIS by its code; the reason, expectation and fixture literals move in Task 7 because they fail only in pt-BR; a language-agnostic guard pins the window's minimum within 1200 × 800 and the tab bar's size hint within the tabs' width, since a tab never elides or narrows (scroll buttons appear instead), so comparing a tab's rect with its text could never fail (probed) — r2, Review Focus 4 — cost if wrong: none.
- Ruling: one amendment, A-22, in Task 5 (§1.1's UI-language row, one §3.5 bullet), landing with the catalog that makes the UI bilingual — Stage 2 §5.10 — cost if wrong: none.
- Ruling: Task 5's implementer is the translator, briefed with the task and design §3 and §6 whole; it translates in batches of about 60 entries in file order (the `T_` group last, as its own batch), each one Edit of a contiguous block followed by the tool and the checks that read a partial catalog, so a broken placeholder fails in its batch; a fresh reviewer then reads the whole catalog with every msgstr and every term rendered in each sentence it fills (Step 5's listing); the controller accepts or settles each finding by §6 and the plan glossary and sends it to the implementer, or to a fresh one with the same brief; the native speaker's review stays the owner's — design §6.3 — cost if wrong: drift both miss waits for the owner.
- Ruling: Task 5 Step 3's plan glossary adds what §6.1 leaves open, by §6.1's own principles (KiCad's words for KiCad's terms; a word kept apart from one it would collide with): snapping "Série E", never retune's "ajuste"; teardrop, padstack and annotate as KiCad says them; gap "espaçamento", never KiCad's wrong "lacuna"; the copper's edge "borda" and the mesh's "aresta"; package, verdict, flagged, outline and S2P file; Windows' own "Acesso controlado a pastas"; edge lint and fit2d kept as the gates' names, the other three described. Tone rule 2 becomes exact (tabs, headers, box titles, field labels and the Help menu nouns; buttons infinitives; About's items "Sobre …", as Qt's own), which the drift check honours for the three pairs that differ by case or "…" — r3 — cost if wrong: one msgstr per term, which the native speaker may change.
- Ruling: `QUOTED` lists the G_ messages that name a widget by its label (r3's list), Apply among G_VERIFY_VALUE's and G_APPLY_FIRST's; advice that reuses a button's words without naming it (G_NO_RESULTS, G_RESULTS_STALE) is imperative advice by rule 1, not a quote; G_ENDED's "Results" and G_NEW_NO_FOLDER's "New" are short forms that Step 3 has the translator write as the Results and retune tab's and the Create the project button's labels, the English unchanged — design §6.2 rule 4 — cost if wrong: one msgstr each, which the substring check cannot pin.
- Ruling: design §6.1's "Preencher todas as zonas (B)" stays, though KiCad 9.0.7's kicad.mo reads "Preenche todas as zonas" (r3): the (B) hotkey names the item, the infinitive follows tone rule 2, and the design binds the text — cost if wrong: one letter in eight msgstrs and the test's string, the native speaker's call.
- Ruling: Task 8 runs `new` and `cost` on lpf915 with no gettext variable, so the Windows path is exercised as a user meets it, in an isolated data folder with `CSXCAD_INSTALL_PATH` set in the same call (cost calibrates there first), each exit code printed and every removal guarded by `Test-Path`, since a failed cmdlet makes the PowerShell tool report exit 1; its grabs come from `tests/test_gui.py` in pt-BR with plan 3's font plugin; layout fixes go into `window.py`, test-first where a widget property shows them — design §7.3 — cost if wrong: about a minute of calibration.
- Ruling (disclosure, the architect): read-only probes only. Babel 2.18.0 in a throwaway venv in the scratch folder, a prototype of `tools/catalog.py` run against the current `CATALOG` into that folder (a `.pot` and `.po` of 316 entries, a header-only `.mo` with `Language: pt_BR`; a second run byte-identical; a translated entry compiled; the privacy gate's generic rules clean on both texts, its e-mail rule matching Babel's default Language-Team); the stdlib `.po` reader and Task 4's checks over those files (every template, G_ABOUT_TEXT's lines, W_STAIRCASED's escapes; a msgstr with another field caught); gettext over that folder with LANG=pt_BR.UTF-8 (pt_BR), LANGUAGE=en beside it, LANG=C, LC_ALL=C.UTF-8 and LANG=pt_PT.UTF-8 (English); Tasks 2–3's CATALOG computed (376 codes, every template distinct, no field in a term, the 25 expectation phrases of `project.py` one-to-one with the `T_EXPECT_` codes); `QUOTED`'s English side; PySide6's `qtbase_pt_BR.qm` offscreen (loads; `&Yes` gives `&Sim`; `qtbase_en.qm` exists, `qtbase_xx` fails); KiCad 9.0.7's pt_BR `kicad.mo` ("none" is "nenhum"); the English main window offscreen with isolated data and KiCad folders (minimum 830 × 518). No suite, no openEMS, no KiCad, nothing written in the repo or its venv — cost if wrong: none.
- Ruling (disclosure, the reviser): read-only too, in its scratch folder: Babel 2.18.0 in a throwaway venv (Requires-Python ≥ 3.8; `Generated-By` carries its version); this revision's `tools/catalog.py` over the current `CATALOG` and over the planned 376-code one built in scratch (377 msgid lines, 204 brace-format flags and no python-format one, a second run byte-identical, the privacy gate's generic rules clean on the `.po`, the `.pot` and the tool); `read_po` on a msgstr wrapped over two lines (cut to "Ol" with a warning by default, a `PoFileError` with `abort_invalid=True`, unescaped inner quotes read either way); `update`'s fuzzy matching filling a new msgid and `no_fuzzy_matching` leaving it empty with the old pair obsolete; this plan's stdlib checks over an identity translation (all pass), a partial one (all batch checks pass) and damaged ones (a decimal comma, a dropped "…", a moved filter, a stray line break and an unbalanced brace, each named by its msgid); Step 5's listing (618 lines); `QUOTED`'s English side with Apply; the 25 expectation phrases; a `QTabWidget` offscreen at 1200 × 800 (no eliding, scroll buttons, every tab rect as wide as its text even with 7320 px of tabs, the minimum size hint blind to them, the tab bar's size hint 600, 684 and 7320 px, the width set at `show()`); `qtbase_pt_BR.qm` installed and removed explicitly (`&Sim`, then `&Yes`); the repo's tests read for every comparison of a raw reason, word or job name. No suite, no openEMS, no KiCad, nothing written in the repo or its venv — cost if wrong: none.
