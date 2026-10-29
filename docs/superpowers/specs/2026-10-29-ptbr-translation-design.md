# The pt-BR translation: design

Status: written on 2026-10-29 by the controller, right after Stage 2's exit. The owner is unavailable and asked not to be stopped for questions, so every decision below that the Stage 1 spec and the Stage 2 design did not already make is a controller recommendation, owner unavailable. The research behind it is in `.superpowers/sdd/ptbr-research/` (git-ignored). An independent builder read it before the commit; its one question, which pt-BR word stands for "gate" beside verify's, is settled in §6.1.

## 1. Intent

kicad-rf-studio's user interface is English. The Stage 1 spec (§1.1) promised that every user-facing string is translatable from day one and that a pt-BR translation follows right after v1. The Stage 2 design (§5.7, §5.9) made the pt-BR catalog the first plan after v1. This design is that plan's ground: a user whose Windows shows Portuguese (Brazil), the owner among them, gets the CLI's and the GUI's text in pt-BR with no setting to find, and everyone else keeps English.

## 2. What is already decided (binding)

- Stage 1 §3.5: stdlib gettext, one catalog shared by the core, the CLI and the GUI. A message is a code plus parameters, and the English template is the msgid. Babel is a dev-only tool for extracting and compiling the catalogs.
- Stage 1 §3.3: events carry codes, never text, so they stay language-neutral and are translated only when displayed.
- Stage 2 §5.7: GUI strings are `G_` codes in the same catalog, rendered with `render()`; no `.ts` or `.qm` files for our strings; Qt's own dialogs use the qtbase translations that the PySide6 wheel ships.
- `core/messages.py` holds CATALOG (316 codes at `29d0ec2`: 118 G, 91 E, 64 I, 43 W; every template distinct) and binds `gettext.translation("kicad_rf_studio", localedir=<package>/locale, fallback=True)` at import.

## 3. Goals, non-goals, anti-goals

Goals:
- Every catalog message in pt-BR, following §6's glossary and tone.
- The language picked with no setting: the gettext variables when one is set, else Windows' display language.
- No English word left inside a pt-BR sentence by a parameter.
- Qt's own words (Yes/No, context menus, About Qt) in pt-BR with the catalog.
- The window laid out cleanly in pt-BR, whose sentences run longer than English ones.
- The suite deterministic in English on any machine, and the GUI tests passing in pt-BR too.

Non-goals (stay English):
- argparse's own words (usage, "error:", "invalid choice"), which come from the stdlib's own gettext domain. The CLI has no help texts.
- `detail()`'s exception text, tracebacks, gui.log, cli.log's Python text, pip's output.
- Identifiers: commands (`run`, `retune`, `setup-openems`), options (`--stackup`, `-o`), preset and stackup names (draft, normal, strict), JSON keys and values, file and folder names, units, part values, refs, `REF.PAD`, `T_max`, symbols (Z0, εeff, f0, S21).
- Machine-read files: Touchstone files (their what-if comment line included), summary.csv's header, events.jsonl, project.json.
- The docs: README, specs, plans, validation records.
- Other languages, pt-PT included. A GUI language menu (owner item, §8).
- The button helper's own line in KiCad (§5.4).

Anti-goals:
- Numbers localized. A decimal comma would clash with project.json, the CLI's value parser and KiCad's own fields. Every number keeps its decimal point in both languages; the lid spin box already uses `QLocale.c()`.
- A translation that can crash. A msgstr whose format fields differ from its msgid's raises KeyError in `render()`; tests forbid it.
- Behaviour that depends on the language. Code never parses rendered text.

## 4. Choosing the language

Controller recommendation, owner unavailable.

- `core/messages.py` picks the language once, at import, before it binds `_translation`:
  1. When any of LANGUAGE, LC_ALL, LC_MESSAGES or LANG is set and non-empty, gettext reads them itself (`languages=None`), as today. A Linux desktop's `LANG=pt_BR.UTF-8` then picks pt_BR with no code. `LANGUAGE=en`, or `C`, gives English.
  2. Else, on Windows, the user's display language, from `GetUserDefaultUILanguage` through ctypes (stdlib, Qt-free): 0x0416, Portuguese (Brazil), gives `["pt_BR"]`; anything else gives English. The regional format (`locale.getlocale()`, `QLocale.system().name()`) is the wrong signal and is not read.
  3. Else, English.
- One function tells the rest of the app the resolved language (`"pt_BR"` or `"en"`), for Qt's translator and for tests.
- The environment carries the choice to every child process. The GUI starts the orchestrator CLI with its own environment (`control._env`), and the button helper starts the GUI with KiCad's. A user who wants English on a Portuguese Windows sets `LANGUAGE=en` in their user environment; the README says so in one line.
- The tests pin English by assigning `os.environ["LANGUAGE"] = "en"` at the very top of `tests/conftest.py`, before its first import. A fixture would be too late: test modules call `render()` at import, and every test's child process must inherit the pin. A developer whose Windows, or Git Bash's `LANG`, is Portuguese then still sees the suite pass. The pin takes `KRS_TEST_LANGUAGE` instead of `en` when it is set, which is how §7.3 runs the GUI tests in pt-BR.

## 5. What changes in the code

### 5.1 Words passed as parameters become codes

Some parameters are English words that land inside a sentence: `reason()`'s phrases ("file not found", "permission denied"…) and its callers' fallbacks ("cannot be written", "cannot be started", "cannot be made"…), "none", "on"/"off", E_PROJECT_FIELD's 25 expectation phrases, E_EDGE_LINT's reasons, E_PORT_OPEN's "reference"/"signal", E_RESULTS_JOB's verdicts, W_COPPER_DROPPED's "hatched zone", I_STACKUP's "board", E_WORKER_FAILED's job names, "unset", "missing", and the prose inside the setup-openems command hint. The research lists each with its file and line.

- Each becomes a catalog code with the prefix `T_`, a term, translated like any message.
- The parameter carries the code, so events stay language-neutral (Stage 1 §3.3). `render()` renders a parameter value that is a `T_` code of CATALOG before it formats the template. A user's net or part literally named like a `T_` code would be rendered as that term: an accepted limit.
- Where Portuguese grammar changes the sentence around the word (gender and agreement, as with I_LID's on/off), the message splits into whole messages instead of taking a word.
- Python's `None` reaching a sentence ("schema None", E_LOCKED's "since None in None" for a lock never written) is rendered as a `T_` term too.
- The same pass fixes the callers that pass the wrong fallback today: E_OUTPUT_PATH, a write error, and G_START_FAILED, a start error, fall back to "cannot be read".
- The GUI's fixture message names the fixture combo's own labels, not the CLI's `series`/`shunt` syntax.

### 5.2 Qt's own words

`gui.main` installs a `QTranslator` holding PySide6's `qtbase_<language>.qm`, from `QLibraryInfo.path(TranslationsPath)`, before it builds the window, when the language is pt_BR. Yes/No, the context menus, the spin boxes' steps and About Qt then read in Portuguese. Windows' native file dialogs already follow Windows' language.

### 5.3 Files the app writes

- chain.s2p's what-if comment line is written from the English template: the file is ASCII, and an accent would turn into an escape there.
- plugin.json's name and descriptions are rendered in the installer's language when `install-kicad-plugin` runs, as today.
- summary.png's labels follow the language of the process that draws it.

### 5.4 The button helper stays English

`button.main` prints one line to stderr, which KiCad 10 shows, and writes one line to button.log. Plan 3 kept that line ASCII (except for paths) because KiCad 10's decoding of an action's stderr is unverified. Until the owner's click-through settles it, the helper renders its line from the English templates whatever the language, and a test pins its ASCII form with pt-BR active. The GUI that the helper starts follows the language as everywhere else. `refill`'s messages show in the GUI, so they are translated.

## 6. The translation

### 6.1 Glossary

KiCad 9.0.7's own pt-BR words are used for KiCad's terms. Its electrical and RF terms are not used, since several are wrong ("Característica da impedância", "Perda da tangente").

| English | pt-BR | Note |
| --- | --- | --- |
| board / PCB | placa (f.) / PCI | KiCad's words |
| pad | ilha (f.) | KiCad's word; the `REF.PAD` syntax stays |
| footprint | footprint (m.) | KiCad keeps it |
| zone | zona (f.) | |
| fill / refill | preencher / preencher novamente | never "recarregar" |
| copper / layer | cobre / camada | |
| stackup | empilhamento (m.) | KiCad's word; `--stackup` and preset names stay |
| solder mask | máscara de solda | |
| via | via | |
| net | rede (f.) | |
| track, trace | trilha | both become one word |
| part | componente (m.) | |
| vendor | fabricante | |
| port | porta (f.) | |
| chain | cadeia (f.) | |
| series / shunt | série / shunt | the `:series` and `:shunt` syntax stays |
| fixture | fixture (m.) | |
| insertion / return loss | perda de inserção (IL) / perda de retorno (RL) | IL and RL stay |
| harmonic rejection | rejeição de harmônicos | |
| null | nulo | |
| passivity / reciprocity | passividade / reciprocidade | |
| loss budget | balanço de perdas | |
| mesh / grid | malha / grade | "in the grid" is "na grade", kept apart from the mesh |
| cell / timestep | célula / passo de tempo | |
| run | execução / executar | the `run` command stays; never "rodar" |
| job / worker | tarefa / processo | |
| cost | custo | |
| gate | checagem prévia | the gates' names stay; never "verificação", which is verify's: a verify runs the gates too, and "Verificações aprovadas" there would read as a passed verify |
| residual / converged / flat | resíduo / convergiu / estagnado | |
| what-if | hipotético | |
| retune | ajuste / ajustar | the `retune` command stays |
| verify | verificação / Verificar | the `verify` command stays |
| preset | predefinição | draft, normal and strict stay |
| shield / lid | blindagem / tampa | |
| calibration | calibração | `calibrate` stays |
| lock | trava | |
| project / results / outputs | projeto / resultados / saídas | |
| button | botão | |
| KiCad API | API do KiCad | |
| plugin | plug-in | KiCad's word |
| settings | configurações | |
| PCB editor / toolbar | editor de PCI / barra de ferramentas | |
| ideal schematic | esquemático ideal | |
| exit code | código de saída | |
| stale | desatualizado | |

KiCad menu paths use KiCad's pt-BR labels, with `›` as the separator: "Preferências › Plug-ins › Ativar a API do KiCad"; "Configuração da placa › Empilhamento físico"; Refill (B) as "Preencher todas as zonas (B)".

### 6.2 Tone

1. Advice uses the imperative in the você form ("Abra", "Salve", "Confira"), and "você" only where a subject is needed. Never "tu", "favor" or "o usuário".
2. Buttons, tabs, headers and titles use an infinitive or a noun, in sentence case ("Executar…", "Estimar o custo", "Parar"). Progress lines use the gerund ("Executando…"), outcomes the participle ("Concluído (código de saída 0).").
3. §3's identifiers, every `{placeholder}` (and `{{ }}`), units, numbers and symbols stay as they are. File-dialog filters keep their `(*.json)` parts, which Qt parses.
4. A label quoted inside a message is the translated widget's label, word for word ("Stop stops it" becomes "O botão Parar a interrompe").
5. There is no `ngettext`, so a count never changes the sentence ("Ilhas selecionadas no KiCad: {count}.").
6. A label that opens a dialog keeps its "…".

### 6.3 Who translates

The controller's subagents translate every msgid and every new `T_` term, following §6.1 and §6.2. Then an independent reviewer checks the whole catalog for glossary drift, broken placeholders, quoted labels that do not match their widgets, and tone. A native speaker's review is the owner's item (§8); it does not block the merge.

## 7. Files, tests and checks

### 7.1 Files

- `po/kicad_rf_studio.pot` and `po/pt_BR.po` at the repo's root, outside `src/`. The release check's `inspect_wheel` expects every tracked file under `src/` in the wheel, and these are not shipped.
- `src/kicad_rf_studio/locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo` is compiled and committed, and `pyproject.toml`'s package-data adds `locale/*/LC_MESSAGES/*.mo`. The wheel is built from `git archive` with plain setuptools, which compiles nothing, so an uncommitted `.mo` would ship an English-only wheel without a warning.
- A dev script, `tools/catalog.py`, writes the `.pot` from CATALOG (`pybabel extract` cannot find dictionary values), updates the `.po` and compiles the `.mo`, with Babel. Babel joins the dev extra; the tests do not import it. Its headers carry no e-mail address and no date: Babel's default Language-Team header holds a placeholder address, which matches the privacy gate's e-mail rule. Each entry carries its code as an extracted comment for the translator.
- The privacy gate skips binary files, so the `.mo` is never scanned. The `.po`, which is, holds the same text.

### 7.2 Tests

- The English pin at the top of conftest.py (§4).
- The catalog, with the stdlib only:
  - every CATALOG template is a key of the compiled `.mo`, and the `.mo` has no other key;
  - each msgstr has exactly its msgid's format fields, and none adds a format spec or a conversion;
  - the `.mo`'s pairs equal the `.po`'s (a few lines of `.po` parsing; modification times do not survive a checkout);
  - the `G_` rules that today check only the English templates (no backtick, `--flag`, `-o ` or `PROJECT` in GUI text) hold for the pt-BR ones too.
- The language choice: the gettext variables win over Windows' language; 0x0416 gives pt_BR and another language English (ctypes call faked); `C` gives English.
- `render()` renders `T_` parameters, and an event's parameters stay codes.
- The helper's line stays ASCII and English with pt-BR active.
- Qt's translator loads `qtbase_pt_BR.qm` for pt_BR and none for English.
- `tests/test_gui.py`'s eight asserts on literal English go through `render()` or `control.text()`, so the GUI tests pass with `KRS_TEST_LANGUAGE=pt_BR` too. Tests elsewhere that assert literal English stay as they are, under the pin.

### 7.3 The controller's checks

- The full suite, pinned to English.
- `tests/test_gui.py` run with `KRS_TEST_LANGUAGE=pt_BR`, the font plugin and `KRS_GRAB_DIR`: every test passes, and the thirteen grabs are read at 1200 × 800 for clipped, cut or overlapping Portuguese text. Each defect is fixed in the window's code, test-first where a widget property can show it.
- The release check: the wheel holds the `.mo`, and its GUI step runs in the machine's language.
- The CLI in pt-BR on lpf915's `new` and `cost` (no simulation), read for English words left inside sentences.

## 8. Owner items (not blocking)

- A native speaker's review of `po/pt_BR.po`, the glossary above all.
- A language menu in the GUI, if wanted. It would need a settings.json key written under a lock: today three writers rewrite that file with no lock.
- The helper's line in pt-BR, once the click-through shows how KiCad 10 decodes an action's stderr.
- Other languages: the files and tests take a new `.po` with no code change.

## 9. Left to the plan

The task split and order; the exact `T_` codes and their templates; how `render()` recognises a `T_` parameter; the splits that grammar needs; the conftest line; the window fixes that the pt-BR grabs show.
