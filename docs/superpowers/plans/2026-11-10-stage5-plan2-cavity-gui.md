# Stage 5 Plan 2: Cavity Modes, Gate E-E and the GUI Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The review gains the plane pairs' cavity modes. Each mode comes from a 2D cut-cell eigen-solve and is marked when it sits near a carrier or clock harmonic. Gate E-E checks the solver in CI, and one recorded openEMS run measures the fringing bias. `review.json`'s `cavities` is filled. The GUI gains a Review tab that runs the review on the pool, plus Select in KiCad and "simulate this" into New's SI kind. The README gets a review tutorial, and the release check gets a review step.

**Architecture:**
- **The solver is one new module, `core/cavity.py`.** It imports numpy, scipy and shapely, and never openEMS or CSXCAD, because the GUI process imports it (Stage 1 §3.1). It holds:
  - `solve`: the cut-cell finite-volume operator with its via posts and guards;
  - `narrow_slot` and `marks`;
  - `cavities`: the pair finder.
- **The review:**
  - `core/review/__init__.py`'s `review_board` fills `Review.cavities` with JSON-ready entries, and `cavity_lines` words them;
  - `outputs.review_json` writes them;
  - `cli.review` prints them before I_REVIEW_FINDINGS.
- **The GUI:**
  - `gui/control.py` runs `cli.review` into `runs.data_dir()/review`, as `control.compare` runs `compare_projects`;
  - `gui/window.py`'s `ReviewView` shows the result;
  - `button.select` selects in KiCad;
  - "simulate this" reuses `control._si_handed` and `show_pads`, and reads the press from its handoff file.
- **The confirmation run:** `tools/ee.py` writes E-E's hand-written spec, as `tools/p3a.py` writes P3-A's, and drives it through `p0`. Its references are committed before the run, in `tests/fixtures/ee/references.json`, as P4-B's are. Only the controller runs openEMS with it.

**Tech Stack:**
- Python ≥ 3.11 (dev venv 3.14.2);
- numpy, scipy (`sparse`, `sparse.linalg.eigsh`, `sparse.csgraph`, `linalg`, `special`, `optimize`, `signal`), shapely, matplotlib and PySide6, all already dependencies;
- kicad-python 0.8 (`>=0.8,<0.9`);
- pytest, and `tools/catalog.py` (Babel, dev extra).

**Spec:**
- **The design, binding:** `docs/superpowers/specs/2026-11-09-stage5-emc-design.md`, its §5.15 plan 2 row. That row covers §5.4, §5.12's two E-E rows, §5.3's cavities, §5.5, §5.14 (emc_review as a GND/+3V3 cavity), §5.16's plan 2 amendments, §5.17 items 2 and 4, §6, §7, and §8 risks 7 and 8.
- **The controller's decisions:** `.superpowers/sdd/stage5-research/controller-decisions.md`, A11 to A13 and BC1/BC2 (git-ignored).
- **The research** (git-ignored), in `.superpowers/sdd/stage5-research/`:
  - `r2-cavity/findings.md`: the operator, the via post, E-E;
  - `r4-gui-button/findings.md`: the tab, Select, the fake KiCad, "simulate this";
  - `f1/findings.md`: the loaded Q of a port across a plane pair.
- **Plan 1, as merged:** `docs/superpowers/plans/2026-11-09-stage5-plan1-review-rules.md` and `.superpowers/sdd/2026-11-10-stage5-plan1-rulings-and-minors.md`. The latter carries emc_review's In2.Cu hole inside SH1's via ring, which Task 4 pins.
- **The Stage 1 spec:** A-1 to A-71. Task 15 adds A-72 to A-77.
- **The pt-BR design:** §5.1 (a whole message per grammar) and §6 (glossary, tone, quoted labels).

**Branch:**
- `stage5-plan2`, from `main` at `1f57b80`.
- Commands run from the repo root with `.venv/Scripts/python`.
- A path without a folder is under `src/kicad_rf_studio/`.
- Line references are main's at `1f57b80`. Find a moved line by its quoted text.

**Machine time:**
- Task 13's openEMS confirmation takes 0.5–2 h. Its `--cost` step predicts it first.
- Each task's suites take about 40 min.

**Before Task 1 (the controller):**
1. Run `git switch -c stage5-plan2 main`.
2. Commit this plan on the branch.
3. Record the baseline from plan 1's close at `1f57b80`: 2551 passed and 7 skipped; in pt-BR, 50 passed and 4 skipped.

## Global Constraints

**From the design (verbatim):**
- §3, anti-goals:
  - "Any change to v1's, the antenna's or SI's model specs, spec hashes or output bytes."
  - "A pass/fail verdict, a severity tier beyond the catalog's W_ and I_ prefixes, or an absolute emission claim."
  - "A new dependency."
  - "A fixture that is not synthetic."
  - "Pushing."
- §4:
  - "No new dependency. numpy, scipy (`scipy.sparse`, `scipy.sparse.linalg.eigsh`, `scipy.special`), shapely and matplotlib are already in. kicad-python stays pinned `>=0.8,<0.9`."
  - "Every new message has its pt-BR msgstr in the same commit. Every G_ text keeps the existing rule: no backtick, flag or terminal syntax."
  - "The review and the cavity solve run off the GUI thread (Stage 2's 50 ms rule)."
- §5.4: "The grid is anchored at the outline's minimum corner, which keeps mirror and rotation symmetry exact."
- §5.5:
  - "It never zooms, because `run_action` is documented as an unstable API."
  - "Nothing is written into the user's KiCad project."
- §5.12: "numerical references are committed as JSON before the gate's runs, and never regenerated during them".

**This plan's own:**
- **Pins** (ruling 2):
  - `tests/test_golden_v1.py`, `test_golden_antenna.py` and `test_golden_si.py` stay green and unchanged on every task.
  - Task 6 re-records the five review goldens, once, and no other task does. Any other golden move stops the task for a ruling.
- **Imports:**
  - `core/cavity.py` imports numpy, scipy and shapely only. It never imports openEMS, CSXCAD or matplotlib.
  - Qt is imported only under `gui/`.
- **Never a real KiCad** (ruling 7):
  - tests talk only to `tests/fake_kicad.py`;
  - no task starts KiCad, kicad-cli or KiCad's Python;
  - Qt runs offscreen only.
- **openEMS:**
  - Only Task 13, the controller's, runs it, outside pytest.
  - Implementer tasks test `tools/ee.py` with the fake worker and in-memory specs.
- **Messages:**
  - Every user-facing line is a `CATALOG` code with its pt-BR msgstr. The task that first emits a code adds it (see the Messages section).
  - Run `.venv/Scripts/python tools/catalog.py`, set each new msgstr, then run it again.
  - Where new rows go:
    - W_/I_ rows before `"E_INTERNAL"`;
    - G_ rows after `"G_COL_UNIT"`;
    - E_KICAD_SELECT_OTHER_BOARD after `"E_KICAD_OTHER_BOARD"`.
  - Numbers and identifiers keep their spelling in pt-BR, under `test_sexpr.py`'s KEEP rule: "0.25", "0.5" and "f_max" stay as they are.
  - A G_ text that names a widget quotes that widget's label word for word. Its codes join `test_sexpr.py`'s QUOTED in the same task (pt-BR design §6.2 rule 4).
  - Gate prose in pt-BR says "checagem", never "verificação".
  - No new line holds "dBµV", "FCC", "CISPR", "margin" or "pass" (§5.8's later scan).
- **Tests:**
  - Write them first. `KrsError` tests check `.code` and `.params`.
  - Tests never write under `tests/fixtures`. The exceptions are Task 6's re-recording and Task 7's `--references` step.
  - E-E's analytic references are computed in the tests from `scipy.special` or the closed form, never remembered (ruling 4).
- **Suites,** before every commit that touches src, tests, tools, po or pyproject.toml:
  - `.venv/Scripts/python -m pytest -q`;
  - then, in PowerShell: `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q; Remove-Item Env:KRS_TEST_LANGUAGE`.
  - Each runs alone, in the background, and is waited on. **Never run two pytest processes at once.**
- **Git:**
  - No push. The privacy gate runs on every commit, and `--no-verify` is never used.
  - **No commit message carries a co-author line.** Use the messages as given.
  - No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address, a host name or a private name. Write `<openEMS folder>`, `<KiCad 9 bin folder>` and `<EMC_GATES>`.
- **Files:** every new `.py` starts with `# SPDX-License-Identifier: GPL-3.0-or-later`.
- **Python** runs only with a script, `-c` or `-m`. Never run a bare interactive `python`, least of all in a background shell.
- **Workflow:**
  - Run `graphify query "<question>"` before reading code, and `graphify update .` after each commit.
  - Ponytail: write the smallest code that does what the design says. Add a `ponytail:` comment on each corner cut that has a known ceiling.
  - Reuse what exists:
    - `copper.clean`, `zstack`, `review._kicad` and `outputs.write`;
    - `control._si_handed`, `_names`, `_antennas`, `text` and `message`;
    - `button._kicad`, `_call` and `_board_path`;
    - the window's `page`, `beside` and `sentences`, and its CompareView pattern;
    - `p0.enter`, `step`, `records`, `run_model`, `save`, `table` and `predicted_s`;
    - `waves.s_matrix`, `rule.lint_hits`, `smooth_mesh_lines`, `with_pml`, `dc_pulse` and `stoprule.RING_CEILING`.

## Review Focus

Each line names the test that checks it and the task that owns that test.

1. **A wrong operator.** Each of these is a bug:
   - a cut cell's mass or face fraction taken as 1;
   - a slot narrower than a cell leaking;
   - an island left in as a spurious zero mode;
   - a mode lost to too small a mode count;
   - a post held only at its node, without α;
   - a DC mode carrying round-off instead of exactly 0.0.

   Checks:
   - Task 1: `test_e_e1_…`, `test_e_e2_…`, `test_e_e6_…`, `test_a_slot_between_two_cell_centres_cuts_their_link`, `test_islands_under_1_mm2_are_dropped`;
   - Task 2: `test_e_e3_…`, `test_e_e4_…`, `test_e_e5_…`, `test_a_post_of_r_at_or_over_h_is_its_discs_cells_within_7_percent`.
2. **Guards that let the GUI process die.**
   - The grid must coarsen past 1.5 M cells.
   - It must also coarsen when the Lanczos vectors would pass MEM_MAX: memory grows as cells × modes.

   Check: Task 3's `test_past_cells_max_or_mem_max_the_grid_coarsens`.
3. **A post where there is none, or none where there is one.**
   - A GND/power pair has no post.
   - A via or plated pad is a post only where both layers' pours under it are its own net.
   - After `get_parts`, fills of different nets never touch, so each cavity has one net per side. emc_review's fence vias cross its GND/+3V3 cavity through antipads and are no posts. Its In2.Cu GND island makes its own GND/GND rim cavity, whose tie via is its one post.
   - No cavity forms inside SH1's ring, where In2.Cu has no copper.

   Check: Task 4's `test_emc_reviews_in1_in2_pair_is_a_postless_gnd_3v3_cavity_and_a_gnd_rim_with_one_post`.
4. **Marks:**
   - the ±5 % window holds, and the carrier's fundamental is included;
   - a clock past its 10th harmonic is never marked, and the carrier is never suppressed;
   - a DC mode is never marked;
   - the clock note is printed only where suppression can act.

   Checks: Task 3's `test_marks_…`, and Task 5's `test_cavity_lines_…`.
5. **The goldens moving beyond `cavities`.** Check: Task 6's `test_the_re_recorded_goldens_differ_from_plan_1s_only_in_cavities`, which compares every byte before `"cavities"`.
6. **E-E's run measuring something other than the design's case:**
   - a mesh line on a plate edge;
   - references computed after the run instead of committed before it;
   - a peak list polluted by DFT ripple;
   - buffered and plain modes paired by sorted index.

   Checks: Task 7's `test_the_spec_is_…`, `test_z_in_reads_…`, `test_the_committed_references_…` and `test_eigen_labels_…`.
7. **The GUI:**
   - the GUI thread blocked by a review;
   - a fixed tab index left pointing at the wrong tab;
   - "simulate this" carrying a stale or empty socket, so that Refill or Select reach the wrong KiCad or are enabled with no press;
   - §5.5's status lines lost after the handoff;
   - Select sent to another board.

   Checks:
   - Task 10's `test_the_review_leaves_the_gui_thread_in_under_50_ms_and_fills_its_tables_and_picture`;
   - Task 11's `test_simulate_this_pre_fills_new_and_keeps_the_presss_kicad` and `test_one_review_through_the_window_on_emc_review_select_and_simulate_this`;
   - Task 8's `test_select_refuses_another_board_and_sends_nothing_else`.
8. **The release step failing on a CRLF checkout.** Check: Task 12's `test_the_review_step_…`.

---

## Messages

Each code gives the English text, then the pt-BR text. The English text is the msgid.

**Task 5,** the CLI's cavity lines (params are text):
- `I_CAVITY` {k, layers, nets, x_mm, y_mm, d_mm, eps_r, area_mm2, posts}:
  - EN: "Cavity {k}: {layers}, nets {nets}, at ({x_mm}, {y_mm}) mm: d {d_mm} mm, εr {eps_r}, area {area_mm2} mm², via posts {posts}."
  - PT: "Cavidade {k}: {layers}, redes {nets}, em ({x_mm}, {y_mm}) mm: d {d_mm} mm, εr {eps_r}, área {area_mm2} mm², postes de via {posts}."
- `I_CAVITY_MODES` {k, modes}:
  - EN: "Cavity {k}'s modes up to f_max, in MHz: {modes}."
  - PT: "Modos da cavidade {k} até f_max, em MHz: {modes}."
- `I_CAVITY_NONE` {k}:
  - EN: "Cavity {k} has no mode up to f_max."
  - PT: "A cavidade {k} não tem modo até f_max."
- `I_CAVITY_NEAR_CARRIER` {k, f_mhz, n, of_mhz}:
  - EN: "Cavity {k}'s mode at {f_mhz} MHz lies within ±5 % of {n} × the carrier, {of_mhz} MHz."
  - PT: "O modo da cavidade {k} em {f_mhz} MHz fica a até ±5 % de {n} × a portadora, {of_mhz} MHz."
- `I_CAVITY_NEAR_CLOCK` {k, f_mhz, n, of_mhz}:
  - EN: "Cavity {k}'s mode at {f_mhz} MHz lies within ±5 % of {n} × the {of_mhz} MHz clock."
  - PT: "O modo da cavidade {k} em {f_mhz} MHz fica a até ±5 % de {n} × o clock de {of_mhz} MHz."
- `I_CAVITY_CLOCK_STOP` {clock_mhz, n}:
  - EN: "Marks near the {clock_mhz} MHz clock stop before its harmonic {n}: from there its harmonics lie closer than twice the ±5 % window, so every mode would be near one."
  - PT: "As marcas perto do clock de {clock_mhz} MHz param antes do seu harmônico {n}: dali em diante os harmônicos ficam mais próximos que o dobro da janela de ±5 %, então todo modo ficaria perto de um."
- `W_CAVITY_COARSE` {k, h_mm}:
  - EN: "Cavity {k} is too large for the 0.25 mm grid: it was solved at {h_mm} mm, so slots narrower than twice that are not resolved."
  - PT: "A cavidade {k} é grande demais para a grade de 0.25 mm: foi resolvida em {h_mm} mm, então fendas mais estreitas que o dobro disso não são resolvidas."
- `W_CAVITY_SLOT` {k}:
  - EN: "Cavity {k} has a slot or gap narrower than 0.5 mm, which the grid may not see at all: a mode the slot brings can be missing from the list."
  - PT: "A cavidade {k} tem uma fenda ou folga mais estreita que 0.5 mm, que a grade pode não enxergar: um modo que a fenda traz pode faltar na lista."
- `I_CAVITY_NO_PAIRS`:
  - EN: "No two copper layers have pours facing each other over 20 mm² or more, so there is no plane-pair cavity to solve."
  - PT: "Nenhum par de camadas de cobre tem preenchimentos frente a frente em 20 mm² ou mais, então não há cavidade de par de planos para resolver."
- `I_LIMIT_CAVITY`:
  - EN: "Limits of the cavity modes: lossless, so the list says where a resonance may sit, never how high it rises; decoupling capacitors excluded; vias as posts only, snapped to the grid, and a post of drill 0.5 mm or more, a disc of held cells, puts the mode it makes up to about 6 % low; TM0 modes only; no fringing, so frequencies read high by about 2Δ/a, Δ about 0.4 to 0.5 d (about 0.3 % for d 0.2 mm on 50 mm, 2 % for 1 mm); εr uniform; the fills as saved; slots under 0.5 mm unresolved; cavities uncoupled across splits."
  - PT: "Limites dos modos de cavidade: sem perdas, então a lista diz onde uma ressonância pode ficar, nunca quão alta ela sobe; capacitores de desacoplamento excluídos; vias apenas como postes, ajustados à grade, e um poste de furo de 0.5 mm ou mais, um disco de células fixadas, deixa o modo que ele cria até cerca de 6 % baixo; apenas modos TM0; sem efeito de borda, então as frequências saem altas em cerca de 2Δ/a, Δ cerca de 0.4 a 0.5 d (cerca de 0.3 % para d 0.2 mm em 50 mm, 2 % para 1 mm); εr uniforme; os preenchimentos como foram salvos; fendas abaixo de 0.5 mm não resolvidas; cavidades sem acoplamento entre divisões."

**Task 8:**
- `E_KICAD_SELECT_OTHER_BOARD` {board, open}:
  - EN: "KiCad has {open} open, not {board}, so nothing was selected. Open {board} in KiCad and press the kicad-rf-studio button again."
  - PT: "O KiCad está com {open} aberto, não {board}, então nada foi selecionado. Abra {board} no KiCad e pressione o botão do kicad-rf-studio de novo."

**Task 9:** QUOTED gains `"G_SIMULATE_SI": ("G_NEW", "G_KIND_SI")`.

| Code | EN | PT |
| --- | --- | --- |
| `G_NEAR_CARRIER` {n, f_mhz} | "{n} × carrier ({f_mhz} MHz)" | "{n} × portadora ({f_mhz} MHz)" |
| `G_NEAR_CLOCK` {n, f_mhz} | "{n} × clock ({f_mhz} MHz)" | "{n} × clock ({f_mhz} MHz)" |
| `G_SIMULATE_SI` {net} | "New from a board is set to the kind Signal integrity on {net}: one relative result. A comparison needs a twin board drawn in KiCad, with the copper fixed or the trace moved, and a project of each." | "Novo projeto a partir de uma placa está preparado com o tipo Integridade de sinal em {net}: um resultado relativo. Uma comparação precisa de uma placa gêmea desenhada no KiCad, com o cobre corrigido ou a trilha movida, e um projeto de cada uma." |
| `G_SIMULATE_EDGE` | "Signal integrity measures the line, not the radiation from the board edge." | "A integridade de sinal mede a linha, não a radiação da borda da placa." |
| `G_SIMULATE_REFERENCE` {net} | "The review counts {net} as a power plane by its name; the signal-integrity project does not, so its reference may differ." | "A revisão conta {net} como plano de alimentação pelo nome; o projeto de integridade de sinal não, então a sua referência pode ser outra." |

**Task 10:**

| Code | EN | PT |
| --- | --- | --- |
| `G_TAB_REVIEW` | "Review" | "Revisão" |
| `G_REVIEW` | "Review the board" | "Revisar a placa" |
| `G_REVIEWING` | "Reviewing…" | "Revisando…" |
| `G_REVIEW_NETS` | "Tagged nets" | "Redes marcadas" |
| `G_REVIEW_NETS_HINT` | "names or patterns, comma-separated; empty: the name patterns" | "nomes ou padrões, separados por vírgula; vazio: os padrões de nome" |
| `G_COL_NUMBER` | "No." | "Nº" |
| `G_COL_RULE` | "Rule" | "Regra" |
| `G_COL_NET` | "Net" | "Rede" |
| `G_COL_LAYER` | "Layer" | "Camada" |
| `G_COL_PLACE` | "Place (mm)" | "Local (mm)" |
| `G_COL_CAVITY` | "Cavity" | "Cavidade" |
| `G_COL_NEAR` | "Near" | "Perto de" |

The board row reuses `G_NEW_BOARD`, `G_BROWSE` and `G_BOARD_FILTER`. The f0 row reuses `G_NEW_F0`, and the modes table reuses `G_COL_F_MHZ`.

**Task 11:** QUOTED gains `"G_SELECT_MISSING": ("G_REVIEW",)`.

| Code | EN | PT |
| --- | --- | --- |
| `G_REVIEW_SELECT` | "Select in KiCad" | "Selecionar no KiCad" |
| `G_SELECTING` | "Selecting in KiCad…" | "Selecionando no KiCad…" |
| `G_SELECTED` {count} | "Items selected in KiCad: {count}." | "Itens selecionados no KiCad: {count}." |
| `G_SELECT_MISSING` {count, total} | "KiCad selected {count} of {total} items: the board it has open holds edits not yet saved. Save the board in KiCad and press Review the board again." | "O KiCad selecionou {count} de {total} itens: a placa aberta nele tem edições ainda não salvas. Salve a placa no KiCad e pressione Revisar a placa de novo." |
| `G_REVIEW_SIMULATE` | "Simulate this" | "Simular isto" |

**Task 14:** when the run measured a bias, I_LIMIT_CAVITY's text gains it (that task gives the text).

In all, 33 new codes: 10 in Task 5, 1 in Task 8, 5 in Task 9, 12 in Task 10 and 5 in Task 11. Task 14 changes one existing code.

---

## File structure

```
core/cavity.py (H…, Modes, solve); tests/test_cavity.py                                                # T1
core/cavity.py (posts in solve); tests/test_cavity.py                                                  # T2
core/cavity.py (CELLS_MAX/MEM_MAX coarsening, narrow_slot, marks); tests/test_cavity.py                # T3
core/cavity.py (Cavity, cavities); tests/test_cavity.py                                                # T4
core/review/__init__.py (Review.cavities, cavity_lines), cli.py (review's lines), messages, po, .mo;
  tests/test_review.py, tests/test_cli_review.py                                                       # T5
core/review/outputs.py (review_json), tests/fixtures/review/*.json, tests/test_golden_review.py         # T6
tools/ee.py, tests/fixtures/ee/references.json; tests/test_ee.py                                       # T7
button.py (select), messages, po, .mo; tests/fake_kicad.py, tests/test_button.py                       # T8
gui/control.py (REVIEW_FOLDER, Reviewed, review, finding_cells, mode_cells, kiids, simulate_notes,
  simulated, Handed.notes), messages, po, .mo; tests/test_gui_control.py, tests/test_sexpr.py           # T9
gui/window.py (ReviewView, the pages, indexOf, start_review, show_review), messages, po, .mo;
  tests/test_gui.py                                                                                    # T10
gui/window.py (Select, Simulate, the press rule, show_pads' notes, Refill's enable), messages, po, .mo;
  tests/test_gui.py, tests/test_sexpr.py                                                               # T11
README.md, tools/release_check.py; tests/test_repo.py, tests/test_release_check.py                     # T12
docs/validation/<date>-e-e-cavity.md and .json                                                         # T13 (run)
messages (I_LIMIT_CAVITY), po, .mo, README.md; tests/test_repo.py                                      # T14
the Stage 1 spec (A-72 to A-77)                                                                        # T15 (doc)
```

---

### Task 1 [code]: The cut-cell operator and the solve

**Files:** Create `core/cavity.py` and `tests/test_cavity.py`.

**Interfaces.** `core/cavity.py` produces:
- `H = 0.25` (mm), `SLIVER = 1e-3`, `ISLAND_MM2 = 1.0` and `SIGMA = -1e-3` (mm⁻²);
- `DC_HZ = 1e6`, gate E-E's "under 1 MHz": a mode below it is the static mode, stored as exactly 0.0;
- `C_MM = scipy.constants.c * 1e3`;
- `@dataclass(frozen=True) class Modes`:
  - `f: np.ndarray`: Hz, sorted, every eigenfrequency ≤ f_max, the DC mode 0.0;
  - `h: float`: the grid used, in mm;
  - `v: np.ndarray`: the free cells × f's modes;
  - `xy: np.ndarray`: the free cells' centres, mm;
- `solve(region: BaseGeometry, eps_r: float, f_max: float, posts: Sequence[tuple[XY, float]] = (), h: float = H) -> Modes`. Task 1 accepts `posts` and ignores it; Task 2 adds the posts.

- [ ] **Step 1: The failing tests,** in `tests/test_cavity.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import math

import numpy as np
import pytest
import shapely
from scipy.constants import c
from scipy.special import jnp_zeros
from shapely.geometry import Point, Polygon, box

from kicad_rf_studio.core.cavity import solve

EPS = 4.4
UNIT = c / (2 * math.sqrt(EPS))  # Hz·m: f_mn = UNIT·√((m/a)² + (n/b)²)


def rectangle_modes(a_mm, b_mm, f_max):
    a, b = a_mm / 1e3, b_mm / 1e3
    return sorted(f for m in range(20) for n in range(20)
                  if (m, n) != (0, 0) and (f := UNIT * math.hypot(m / a, n / b)) <= f_max)


@pytest.mark.parametrize("angle", [0, 30])
def test_e_e1_the_rectangle_matches_f_mn_aligned_and_rotated(angle):  # design 5.12 E-E (1)
    f = solve(shapely.affinity.rotate(box(0, 0, 50, 30), angle, origin=(0, 0)), EPS, 6e9).f
    exact = rectangle_modes(50, 30, 6e9)
    assert len(exact) == 11 and len(f) == 12 and (f < 1e6).sum() == 1  # every mode to 6 GHz, one DC mode
    assert f[0] == 0.0  # the static mode carries no round-off into the goldens
    assert np.allclose(f[1:], exact, rtol=5e-3, atol=0)


def test_e_e2_the_circle_matches_bessels_x_prime_over_its_first_six_modes():  # design 5.12 E-E (2)
    r_m, f_max = 25e-3, 5e9
    roots = [(x, 1 if m == 0 else 2) for m in range(8) for x in jnp_zeros(m, 3)]  # J_m'(x) = 0, m > 0 twice
    exact = sorted(f for x, k in roots for f in [x * c / (2 * math.pi * r_m * math.sqrt(EPS))] * k if f <= f_max)
    assert len(set(np.round(exact))) == 6  # the first six distinct modes
    f = solve(Point(0, 0).buffer(25, quad_segs=256), EPS, f_max).f
    assert f[0] == 0.0 and (f < 1e6).sum() == 1 and np.allclose(f[1:], exact, rtol=5e-3, atol=0)


def test_e_e6_the_l_shapes_first_mode_differences_shrink_at_least_2x_per_halving():  # design 5.12 E-E (6)
    ell = Polygon([(0, 0), (50, 0), (50, 25), (25, 25), (25, 50), (0, 50)])
    d = np.abs(np.diff([solve(ell, EPS, 2e9, h=h).f[1] for h in (1.0, 0.5, 0.25, 0.125)]))
    assert d[1] <= d[0] / 2 and d[2] <= d[1] / 2  # self-convergence only: no remembered value


def test_a_slot_between_two_cell_centres_cuts_their_link():  # r2 §2 detail 2
    plane = box(0, 0, 50, 50)
    slotted = plane.difference(box(24.3, -1, 24.45, 40))  # 0.15 mm wide, between the centres 24.25 and 24.75
    assert solve(slotted, EPS, 3e9, h=0.5).f[1] < 0.6 * solve(plane, EPS, 3e9, h=0.5).f[1]  # the slot mode


@pytest.mark.parametrize(("side", "dc"), [(0.8, 1), (2.0, 2)])
def test_islands_under_1_mm2_are_dropped(side, dc):  # design 5.4 guards
    f = solve(box(0, 0, 50, 30).union(box(60, 0, 60 + side, side)), EPS, 3e9).f
    assert (f < 1e6).sum() == dc and (f[:dc] == 0.0).all()


def test_two_solves_give_the_same_bits():  # ARPACK's start vector is fixed
    assert np.array_equal(solve(box(0, 0, 50, 30), EPS, 6e9).f, solve(box(0, 0, 50, 30), EPS, 6e9).f)
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_cavity.py -q`. Expected: FAIL, with `ModuleNotFoundError: No module named 'kicad_rf_studio.core.cavity'`.
- [ ] **Step 3: `solve`** (r2 §2; design §5.4). All lengths are in mm. The algorithm:
  1. **The raster.**
     - (x0, y0) = `region.bounds[:2]`.
     - `nx = ceil((x1 − x0)/h − 1e-9)`, and `ny` likewise.
     - Cell (i, j) is `[x0 + i·h, x0 + (i+1)·h] × [y0 + j·h, …]`. Its centre sits half a cell in.
  2. **The mass.**
     - Call `shapely.prepare(region)`.
     - A cell that `contains_properly` keeps A = 1, and one that does not intersect keeps A = 0. Any other cell takes A = area(cell ∩ region)/h².
     - Cells with A < SLIVER are dropped.
     - Vectorise with `shapely.box` arrays. Only boundary cells are clipped, which is r2's speed-up.
  3. **The links** between 4-neighbour kept cells:
     - The conductance is ℓ = length(face ∩ region)/h, or 1 when both cells have A ≥ 1 − 1e-9.
     - Any other link is cut (ℓ = 0) when the segment between the two centres meets `region.boundary` in two or more parts: `len(shapely.get_parts(seg.intersection(boundary))) >= 2`.
  4. **The islands.** `scipy.sparse.csgraph.connected_components` runs on the links with ℓ > 0. A component whose Σ A·h² < ISLAND_MM2 is dropped.
  5. **The system.**
     - K = Σ over links of (ℓ/h²)·(e_a − e_b)(e_a − e_b)ᵀ, as a csr matrix, and M = diag(A).
     - Task 2's posts act here.
  6. **The mode count** (Weyl): kk = 2π·f_max·√εr / C_MM, and N = A_Ω·kk²/(4π) + P_Ω·kk/(4π), where A_Ω = `region.area` and P_Ω = `region.length`. Then k = ceil(1.3·N) + 8.
  7. **The eigen-solve.**
     - Call `eigsh(K, k, M=M, sigma=SIGMA, which="LM", v0=np.ones(n))`.
     - While the largest eigenvalue is < kk² and k < n − 2, double k (at most n − 2) and solve again.
     - When k ≥ n − 1, use `scipy.linalg.eigh(K.toarray(), M.toarray())` instead.
     - With no free cell left, return empty arrays.
  8. **The frequencies.** f = C_MM·√max(λ, 0)/(2π·√εr), then `f[f < DC_HZ] = 0.0`. The docstring says that the static mode's eigenvalue is round-off, about 1e-15 mm⁻² or about 1 kHz, and is stored as 0.0 so that no golden pins BLAS noise. Sort, keep the f ≤ f_max with their vectors, and return `Modes(f, h, v, xy)`.
- [ ] **Step 4: Run them.** Use Step 2's command. Expected: PASS in under a minute (h = 0.125 on the L is 160 k cells).
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/cavity.py tests/test_cavity.py
git commit -m "feat(cavity): a cut-cell finite-volume Laplacian on a raster anchored at the outline's corner, Neumann edges, its link cut across sub-cell slots, islands under 1 mm2 dropped, eigsh in shift-invert with Weyl's count and the static mode stored as 0 (Stage 5 design 5.4; gate E-E 1, 2, 6)"
graphify update .
```

---

### Task 2 [code]: The via posts

**Files:** Modify `core/cavity.py` (`PEACEMAN`, `solve`'s step 5). Test: `tests/test_cavity.py`.

**Interfaces:**
- Produces `PEACEMAN = 0.1985`.
- A post is `((x, y), r)`, where r is the barrel radius (drill/2).

- [ ] **Step 1: The failing tests,** appended. Also import `brentq` from `scipy.optimize`, and `j0`, `j1`, `y0` and `y1` from `scipy.special`.

```python
def shorted_circle(r, big=25.0):  # Hz: the root of J0'(kR)·Y0(kr) − Y0'(kR)·J0(kr), k in 1/mm
    def g(k):
        return -j1(k * big) * y0(k * r) + y1(k * big) * j0(k * r)

    k = brentq(g, 1e-6 / big, jnp_zeros(0, 1)[0] / big)  # the post mode lies under the first m = 0 Neumann root
    return k * 1e3 * c / (2 * math.pi * math.sqrt(EPS))


@pytest.mark.parametrize("r", [0.1, 0.15, 0.2])
def test_e_e3_a_centre_post_matches_the_shorted_circle_and_leaves_no_dc_mode(r):  # design 5.12 E-E (3)
    # (0.125, 0.125) is a cell centre: (0, 0) is a cell corner, four cells tied; 0.18 mm off the axis moves the
    # post mode by O((k·0.18)²), far under the tolerance
    f = solve(Point(0, 0).buffer(25.0, quad_segs=256), EPS, 2e9, posts=[((0.125, 0.125), r)]).f
    assert f[0] > 1e6 and f[0] == pytest.approx(shorted_circle(r), rel=1e-2)


@pytest.mark.parametrize("at", [(0.125, 0.125), (0.0, 0.0)])  # a cell centre; a cell corner
@pytest.mark.parametrize("r", [0.25, 0.3, 0.5, 1.0])
def test_a_post_of_r_at_or_over_h_is_its_discs_cells_within_7_percent(r, at):  # design 5.4: r >= h, the disc
    f = solve(Point(0, 0).buffer(25.0, quad_segs=256), EPS, 2e9, posts=[(at, r)]).f
    assert f[0] > 1e6 and abs(f[0] / shorted_circle(r) - 1) <= 0.07  # probed down to -6.2 %: I_LIMIT_CAVITY states it


SHAPE = Polygon([(0, 0), (40, 0), (40, 10), (25, 10), (25, 30), (0, 30)])  # vertices on the grid's lines
POSTS = [((5.1, 4.3), 0.15), ((30.2, 5.6), 0.15), ((12.7, 22.1), 0.2)]  # no centre tie


@pytest.mark.parametrize("move", [lambda xy: xy * (-1, 1), lambda xy: xy[:, ::-1] * (-1, 1)])  # mirror; quarter turn
def test_e_e4_the_mirror_and_the_quarter_turn_give_identical_lists(move):  # design 5.12 E-E (4), with posts
    f = solve(SHAPE, EPS, 6e9, posts=POSTS).f
    moved = [(tuple(move(np.array([xy]))[0]), r) for xy, r in POSTS]
    g = solve(shapely.transform(SHAPE, move), EPS, 6e9, posts=moved).f
    assert f[0] > 1e6  # the posts hold: no DC mode
    assert len(g) == len(f) and np.allclose(g, f, rtol=1e-9, atol=0)


H5 = 50 / 201  # x = 25 is a cell centre, so (1,0)'s nodal line holds the post


def post_at(x):
    return solve(box(0, 0, 50, 30), EPS, 3e9, posts=[((x, 15.0), 0.15)], h=H5).f


def test_e_e5_the_post_on_the_nodal_line_mirrored_posts_and_the_post_mode_toward_the_antinode():  # E-E (5)
    assert np.min(np.abs(post_at(25.0) / (UNIT / 0.05) - 1)) <= 1e-3  # f10 kept within 0.1 %
    for x in (20.0, 12.5):
        assert np.allclose(post_at(50 - x), post_at(x), rtol=1e-9, atol=0)
    assert post_at(25.0)[0] > post_at(20.0)[0] > post_at(12.5)[0]  # strictly lower toward x = 0
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_cavity.py -q`. Expected: E-E3, the disc test, E-E4 and E-E5 FAIL, with a DC mode present and no post effect.
- [ ] **Step 3: The posts in `solve`** (r2's option (c); design §5.4). They act after step 4's islands and before the system is cut down.
  - **r < h:**
    - The post's node is the kept cell whose centre is nearest (x, y), the first index on a tie.
    - Multiply its links' ℓ by α = ln(1/PEACEMAN)/ln(h/r), and hold the node at 0.
  - **r ≥ h:**
    - Hold at 0 the kept cells whose centres lie within r of (x, y).
    - When no centre does, hold the nearest cell instead.
    - No α.
  - A node already held takes nothing more from a later post.
  - Remove the held nodes from K and M after assembly. Their scaled links stay on their neighbours' diagonals.
  - `xy` and `v` list the free cells only.
- [ ] **Step 4: Run them.** Use Step 2's command. Expected: PASS.
  - A miss on E-E3 to E-E5 is a solver bug. Debug it with superpowers:systematic-debugging, and never widen a tolerance (§5.12: "a solver bug: blocks plan 2").
  - A miss on the disc test's 7 % stops the task for a ruling, with the measured errors.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/cavity.py tests/test_cavity.py
git commit -m "feat(cavity): via posts, the nearest node held at 0 with its links scaled by ln(1/0.1985)/ln(h/r), or the disc's cells for r >= h within 7 % (Stage 5 design 5.4, r2's option (c); gate E-E 3, 4, 5)"
graphify update .
```

---

### Task 3 [code]: The guards and the marks

**Files:** Modify `core/cavity.py`. Test: `tests/test_cavity.py`.

**Interfaces.** Produces:
- `CELLS_MAX = 1_500_000`, `MEM_MAX = 1e9` (bytes), `SLOT_MIN = 0.5` (mm), `SLOT_AREA = 0.01` (mm²), `WINDOW = 0.05` and `CLOCK_N_MAX = 10`;
- `narrow_slot(region: BaseGeometry) -> bool`;
- `marks(f: float, carrier: float | None, clocks: Sequence[float]) -> list[dict]`. Each mark is `{"of": "carrier" | "clock", "f_hz": float, "n": int}`: the carrier first, then the clocks in their order.

`solve` doubles h while nx·ny > CELLS_MAX or nx·ny·(2k + 1)·8 > MEM_MAX, with k from step 6's Weyl count. `Modes.h` reports the h used.

- [ ] **Step 1: The failing tests,** appended. Also import `cavity`, `marks` and `narrow_slot`.

```python
def test_past_cells_max_or_mem_max_the_grid_coarsens(monkeypatch):  # design 5.4: past about 1.5 M cells
    monkeypatch.setattr(cavity, "CELLS_MAX", 10_000)  # 50 × 30 mm: 24 000 cells at 0.25 mm, 6 000 at 0.5 mm
    assert solve(box(0, 0, 50, 30), EPS, 3e9).h == 0.5 and solve(box(0, 0, 20, 20), EPS, 3e9).h == 0.25
    monkeypatch.setattr(cavity, "CELLS_MAX", 1_500_000)
    monkeypatch.setattr(cavity, "MEM_MAX", 2e6)  # 24 000 cells × (2k + 1) Lanczos vectors × 8 B; k about 13
    assert solve(box(0, 0, 50, 30), EPS, 3e9).h == 0.5


def test_a_slot_under_0_5_mm_is_named_and_holes_and_corners_are_not():  # design 5.4 guards
    plane = box(0, 0, 50, 30)
    assert narrow_slot(plane.difference(box(20, 10, 30, 10.3)))
    assert not narrow_slot(plane.difference(box(20, 10, 30, 10.6)))
    assert not narrow_slot(plane.difference(box(5, 5, 7, 7)).difference(Point(20, 20).buffer(0.4)))
    assert not narrow_slot(Polygon([(0, 0), (50, 0), (50, 25), (25, 25), (25, 50), (0, 50)]))


def test_marks_hold_the_window_the_fundamental_a_clocks_tenth_harmonic_and_never_dc():  # design 5.4
    assert marks(1.83e9 * 1.04, 915e6, ()) == [{"of": "carrier", "f_hz": 915e6, "n": 2}]
    assert marks(1.83e9 * 1.06, 915e6, ()) == []
    assert marks(950e6, 915e6, ()) == [{"of": "carrier", "f_hz": 915e6, "n": 1}]
    assert marks(30e9, 1e9, ()) == [{"of": "carrier", "f_hz": 1e9, "n": 30}]  # the carrier is never suppressed
    assert marks(400e6, None, (40e6,)) == [{"of": "clock", "f_hz": 40e6, "n": 10}]
    assert marks(440e6, None, (40e6,)) == []  # n 11: adjacent windows overlap
    assert marks(0.0, 915e6, (40e6,)) == []
    assert marks(1.83e9, 915e6, (61e6,)) == [{"of": "carrier", "f_hz": 915e6, "n": 2}]  # 61 MHz: n 30, suppressed
```

- [ ] **Step 2: Run them.** Expected: FAIL, with `AttributeError` or `ImportError`.
- [ ] **Step 3: The code.**
  - **`narrow_slot`** returns True when any polygon part of `region.buffer(SLOT_MIN/2, join_style="mitre").buffer(-SLOT_MIN/2, join_style="mitre").difference(region)` has an area ≥ SLOT_AREA. Mitred joins restore polygonal holes and corners exactly, so only gaps narrower than SLOT_MIN are filled.
  - **`marks`:**
    - For each source s that is not None, take n = max(1, round(f/s)).
    - The mode is marked when f > 0 and |f − n·s| ≤ WINDOW·n·s, and, for a clock, when n ≤ CLOCK_N_MAX.
    - Each source gives at most one mark, at the nearest n.
  - **The coarsening in `solve`**, before step 2:
    - Compute k from step 6 first.
    - Then double h with `while nx * ny > CELLS_MAX or nx * ny * (2 * k + 1) * 8 > MEM_MAX: h *= 2`, recomputing nx and ny each time.
    - Add a `ponytail:` comment. Doubling is the coarsening step (§6 leaves it to the builder). MEM_MAX bounds ARPACK's 2k + 1 Lanczos vectors, but not the shift-invert LU, nor a k that step 7 doubles later. Without it, a 300 × 300 mm plane at 5 GHz needs about 12 GB while under CELLS_MAX.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/cavity.py tests/test_cavity.py
git commit -m "feat(cavity): the grid doubled past 1.5 M cells or 1 GB of Lanczos vectors, slots under 0.5 mm found by a mitred closing, and the +/-5 % marks, a clock's past its 10th harmonic suppressed, the carrier's never (Stage 5 design 5.4)"
graphify update .
```

---

### Task 4 [code]: The pair finder

**Files:** Modify `core/cavity.py`. Test: `tests/test_cavity.py`.

**Interfaces:**
- Consumes `copper.clean`, `zstack.Slab` and `Board`.
- Produces:
  - `CAVITY_MM2 = 20.0`;
  - `@dataclass(frozen=True) class Cavity`:
    - `layers: tuple[str, str]`: the top layer first;
    - `nets: tuple[tuple[str, ...], tuple[str, ...]]`: each side's nets facing it, sorted. A side holds one net unless two pours of different nets touch;
    - `region: Polygon`: in the importer's frame;
    - `d: float`: mm;
    - `eps_r: float`;
    - `posts: tuple[tuple[XY, float], ...]`;
  - `cavities(board: Board, zs: tuple[Slab, ...]) -> list[Cavity]`. They are sorted by the layers' indices, then by area descending, then by `region.representative_point()`'s x and y.

- [ ] **Step 1: The failing tests** (appended):

```python
from dataclasses import replace
from pathlib import Path

from kicad_rf_studio.core.cavity import cavities
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.board import CopperArea

FIX = Path(__file__).parent / "fixtures"


def board(name):
    return load_board(FIX / f"{name}.kicad_pcb")


def pairs(b):
    return cavities(b, zstack(b.stackup, b.copper_layers))


def test_usb2_hs_holds_one_gnd_3v3_cavity_between_in1_and_in2_with_no_post():  # design 5.4; r2 §3's table
    (cav,) = pairs(board("usb2_hs"))
    assert (cav.layers, cav.nets, cav.posts) == (("In1.Cu", "In2.Cu"), (("GND",), ("+3V3",)), ())
    assert (cav.d, cav.eps_r) == (pytest.approx(1.04), pytest.approx(4.5))
    assert cav.region.area == pytest.approx(413.5, rel=0.02)


def test_lpf915s_stitched_gnd_pair_gets_a_post_at_each_via_and_plated_pad_joining_its_layers():  # design 5.4
    cav = max((c for c in pairs(board("lpf915")) if c.layers == ("F.Cu", "B.Cu")), key=lambda c: c.region.area)
    assert cav.nets == (("GND",), ("GND",)) and len(cav.posts) == 36
    assert cav.region.area == pytest.approx(582.7, rel=0.02)


def test_emc_reviews_in1_in2_pair_is_a_postless_gnd_3v3_cavity_and_a_gnd_rim_with_one_post():  # ruling 3
    b = board("emc_review")
    inner = [c for c in pairs(b) if c.layers == ("In1.Cu", "In2.Cu")]
    assert [c.nets for c in inner] == [(("GND",), ("+3V3",)), (("GND",), ("GND",))]  # nothing else: no third region
    main, rim = inner
    assert main.posts == () and main.region.area == pytest.approx(1697.5, rel=0.02)  # fence vias pass antipads
    assert not main.region.contains(Point(137, -137))  # SH1's ring: In2.Cu bare inside it (plan 1's carried minor)
    tie = next(v for v in b.vias if v.at == (109.0, -119.0))  # the island's tie (make_fixtures.emc_review)
    assert rim.posts == ((tie.at, tie.drill / 2),) and rim.region.area == pytest.approx(80.0, rel=0.02)


def test_a_pair_faces_only_where_no_layer_between_has_copper_and_takes_the_series_eps():  # design 5.4
    b = board("usb2_hs")
    full = [CopperArea(layer, "GND", b.outline, "zone", layer) for layer in ("F.Cu", "B.Cu")]
    found = pairs(replace(b, areas=b.areas + full))
    assert [c.layers for c in found] == [("F.Cu", "In1.Cu"), ("F.Cu", "B.Cu"), ("In1.Cu", "In2.Cu"),
                                         ("In2.Cu", "B.Cu")]
    between = shapely.union_all([a.polygon for a in b.areas if a.layer in ("In1.Cu", "In2.Cu")])
    ring = b.outline.area - between.intersection(b.outline).area  # F faces B only where In1 and In2 stop short
    assert found[1].region.area == pytest.approx(ring, rel=0.02)  # about 51 mm²
    (outer,) = pairs(replace(b, areas=full))  # In1 and In2 bare: F.Cu faces B.Cu through both dielectrics
    slabs = [s for s in zstack(b.stackup, b.copper_layers) if s.kind == "dielectric"]
    d = sum(s.z1 - s.z0 for s in slabs)
    assert outer.d == pytest.approx(d) and outer.eps_r == pytest.approx(d / sum((s.z1 - s.z0) / s.eps_r for s in slabs))


@pytest.mark.parametrize(("side", "count"), [(4.0, 0), (5.0, 1)])  # 16 and 25 mm²
def test_cavities_under_20_mm2_are_dropped(side, count):  # design 5.4
    b = board("usb2_hs")
    x, y = b.outline.centroid.coords[0]
    patch = CopperArea("F.Cu", "GND", box(x, y, x + side, y + side), "zone", "p")
    assert sum(c.layers == ("F.Cu", "In1.Cu") for c in pairs(replace(b, areas=b.areas + [patch]))) == count
```

- [ ] **Step 2: Run them.** Expected: FAIL, with `ImportError`.
- [ ] **Step 3: `cavities`** (r2 §3, design §5.4, ruling 3):
  1. **The pours.** Take each (layer, net) of the zone fills (`source == "zone"`, any net, netless included), and compute `clean(MultiPolygon(polygons), crop)`. The crop is `board.outline`, or the fills' bounding box when there is no outline. Copper graphics and tracks are not pours.
  2. **The facing area.** For each layer pair i < j of `board.copper_layers`, take the union of i's pours ∩ the union of j's pours, minus the union of every pour on the layers strictly between. Its `shapely.get_parts` polygons of area ≥ CAVITY_MM2 are the cavities.
  3. **d and εr.** d is the sum of the dielectric slabs' thicknesses between the two copper slabs of `zs`, and εr = d/Σ(t/εr) over those slabs.
  4. **The nets.** A side's nets are those whose pour on that layer meets the cavity over an area of more than 1e-6 mm².
  5. **The posts.** The candidates are:
     - a via of net n whose layer span (the indices of `via.layers`) covers i and j, with its copper `Point(via.at).buffer(via.diameter/2)`;
     - a `thru_hole` pad with `drill > 0` that holds both layers, with its copper `pad.polygon`.

     A candidate is a post, `(at, drill/2)`, when its copper intersects n's pour on layer i, n's pour on layer j, and the cavity. A GND/power cavity therefore gets none. Where a side holds several nets, only a via or pad of a net on both sides counts.
- [ ] **Step 4: Run them.** Expected: PASS.
  - **The stop rule.** The critics' probe of this rule measured 413.5 mm², 582.7 mm² with 36 posts, and emc_review's 1697.5 mm² and 80.0 mm² with its one tie post. A mismatch is reported with the measured value for a ruling. An expectation is never edited.
  - The emc_review test closes plan 1's carried minor: no cavity forms inside SH1's ring.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/cavity.py tests/test_cavity.py
git commit -m "feat(cavity): the pair finder, every zone fill facing every other less the layers between, split into cavities of 20 mm2 or more, with the series eps and posts where both layers' pours are the via's own net (Stage 5 design 5.4; ruling 3)"
graphify update .
```

---

### Task 5 [code]: The review solves its cavities and prints them

**Files:**
- Modify `core/review/__init__.py`:
  - `Review` gains `cavities: list[dict] = field(default_factory=list)` as its last field;
  - `review_board` fills it;
  - add `cavity_lines`.
- Modify `cli.py`: `review`'s `lines`.
- Messages: Task 5's ten rows.
- Tests: `tests/test_review.py`, `tests/test_cli_review.py`.

**Interfaces:**
- Consumes `cavities`, `solve`, `narrow_slot`, `marks`, `H` and `CLOCK_N_MAX`.
- Produces `Review.cavities`. Each entry is:
  - `"layers": [a, b]`;
  - `"nets": [[…], […]]`;
  - `"at_mm": [x, y]`: in KiCad's frame, `_kicad(c.region.representative_point().coords[0])`, each rounded to 1e-3 with `+ 0.0`;
  - `"d_mm"` and `"eps_r"`, rounded to 1e-3, and `"area_mm2"`, rounded to 1e-2;
  - `"posts": int`, `"h_mm": float` and `"narrow_slot": bool`;
  - `"modes": [{"f_hz": round(f, -3), "marks": marks(f, carrier, clocks)}]`, with the static mode kept as 0.0.
- Produces `cavity_lines(r: Review) -> list[tuple[str, dict]]`.

- [ ] **Step 1: The failing tests.**
  - In `tests/test_review.py`, whose import line becomes `from kicad_rf_studio.core.review import cavity_lines, finding_ids, resolve_f_max, review_board`:

```python
def test_the_review_of_emc_review_lists_its_cavities_with_their_marks():  # design 5.3, 5.4
    plain = run().cavities
    main = next(c for c in plain if c["nets"] == [["GND"], ["+3V3"]])
    assert (main["layers"], main["posts"], main["d_mm"], main["eps_r"], main["h_mm"]) == (
        ["In1.Cu", "In2.Cu"], 0, 1.04, 4.5, 0.25)
    assert main["modes"][0] == {"f_hz": 0.0, "marks": []} and main["modes"][-1]["f_hz"] <= 5e9
    first = main["modes"][1]["f_hz"]
    carried = next(c for c in run(f0=first / 2 * 1.02).cavities if c["nets"] == main["nets"])
    assert {"of": "carrier", "f_hz": first / 2 * 1.02, "n": 2} in carried["modes"][1]["marks"]


def test_cavity_lines_word_each_cavity_its_modes_marks_warnings_clocks_and_the_limit():  # design 5.4 outputs
    r = run(clocks=(40e6,))
    lines = cavity_lines(r)
    k1 = r.cavities[0]
    assert lines[0] == ("I_CAVITY", {"k": "1", "layers": "/".join(k1["layers"]),
                                     "nets": " / ".join(", ".join(side) for side in k1["nets"]),
                                     "x_mm": f"{k1['at_mm'][0]:.3f}", "y_mm": f"{k1['at_mm'][1]:.3f}",
                                     "d_mm": f"{k1['d_mm']:.3f}", "eps_r": f"{k1['eps_r']:g}",
                                     "area_mm2": f"{k1['area_mm2']:.1f}", "posts": str(k1["posts"])})
    assert lines[1] == ("I_CAVITY_MODES", {"k": "1", "modes": ", ".join(f"{m['f_hz'] / 1e6:.1f}"
                                                                          for m in k1["modes"] if m["f_hz"] > 0)})
    assert lines[-2:] == [("I_CAVITY_CLOCK_STOP", {"clock_mhz": "40", "n": "11"}), ("I_LIMIT_CAVITY", {})]
    assert cavity_lines(replace(r, cavities=[])) == [("I_CAVITY_NO_PAIRS", {}), ("I_LIMIT_CAVITY", {})]
    assert all(code != "I_CAVITY_CLOCK_STOP" for code, _ in cavity_lines(run(clocks=(1e9,))))  # 11 GHz > f_max
```

  - In `tests/test_cli_review.py`, the import probe's module list gains `kicad_rf_studio.core.cavity`. Add:

```python
def test_review_prints_its_cavity_lines_before_the_count(tmp_path, capsys):  # design 5.4
    assert main(["review", str(EMC), "-o", str(tmp_path)]) == 0
    out = capsys.readouterr().out.splitlines()
    k = out.index(render("I_REVIEW_FINDINGS", count=2))
    assert out[k - 1] == render("I_LIMIT_CAVITY")
    assert any(line.startswith(render("I_CAVITY_MODES", k="1", modes="")[:12]) for line in out[:k])
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_review.py tests/test_cli_review.py -q`. Expected: FAIL, with `ImportError: cannot import name 'cavity_lines'`.
- [ ] **Step 3: The code.**
  - **`review_board`**, after the findings, for each `Cavity` of `cavities(board, zs)`:
    - `m = solve(c.region, c.eps_r, f_hz, c.posts)`;
    - its entry, with `narrow_slot(c.region)`, and `marks` on the review's `carrier` and `clocks`;
    - the entries keep `cavities`' order.
  - **`cavity_lines(r)`.** For each entry k = 1, 2, …:
    - I_CAVITY, with the params as in the test;
    - I_CAVITY_MODES over the modes with f_hz > 0, or I_CAVITY_NONE {k} when there is none;
    - an I_CAVITY_NEAR_CARRIER or I_CAVITY_NEAR_CLOCK per mark, with {k, f_mhz: f"{f/1e6:.1f}", n, of_mhz: f"{s/1e6:g}"};
    - W_CAVITY_COARSE {k, h_mm: f"{h:g}"} when h_mm > H;
    - W_CAVITY_SLOT {k} when narrow_slot is set.

    After the entries:
    - I_CAVITY_NO_PAIRS when there is no entry;
    - else I_CAVITY_CLOCK_STOP {clock_mhz: f"{clock/1e6:g}", n: str(CLOCK_N_MAX + 1)} for each clock where (CLOCK_N_MAX + 1)·clock ≤ `r.settings["f_max_hz"]`, the only place where suppression can act;
    - I_LIMIT_CAVITY last.
  - **`cli.review`:** `lines = [*r.notes, *findings, *cavity_lines(r), ("I_REVIEW_FINDINGS", …)]`, so that `out[-3:]` in `test_review_writes_its_three_files_…` stands.
  - **Messages:** Task 5's rows, through `tools/catalog.py`.
  - `review_json` still writes `"cavities": []`. Task 6 changes it, so no golden moves here.
- [ ] **Step 4: Run them.** Run Step 2's command, then `tests/test_golden_review.py tests/test_sexpr.py -q`. Expected: PASS, with the goldens unchanged.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review/__init__.py src/kicad_rf_studio/cli.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_review.py tests/test_cli_review.py
git commit -m "feat(review): each plane-pair cavity solved to the review's f_max, its modes marked near the carrier's or a clock's harmonics, and printed with the stated limits before the count (Stage 5 design 5.4)"
graphify update .
```

---

### Task 6 [code]: `review.json`'s cavities and the goldens re-recorded

**Files:**
- Modify `core/review/outputs.py`: `review_json` writes `"cavities": r.cavities`, and its docstring says so.
- Re-record `tests/fixtures/review/*.json`.
- Modify `tests/test_golden_review.py`.

**Interfaces:** none new. `tools/golden_review.py` is unchanged.

- [ ] **Step 1: The failing tests,** in `tests/test_golden_review.py`:
  - In `test_the_goldens_name_their_board_…`, the assertion `d["cavities"] == []` becomes `isinstance(d["cavities"], list)`.
  - Add these (and import `subprocess`):

```python
PLAN1 = "1f57b80"  # plan 1's close: the goldens as plan 1 recorded them


@pytest.mark.parametrize("name", golden_review.CASES)
def test_the_re_recorded_goldens_differ_from_plan_1s_only_in_cavities(name):  # ruling 2
    shown = subprocess.run(["git", "show", f"{PLAN1}:tests/fixtures/review/{name}.json"], capture_output=True,
                           cwd=golden_review.GOLDEN.parents[2])
    if shown.returncode:
        pytest.skip("plan 1's commit is not in this clone")
    old_b = shown.stdout.replace(b"\r\n", b"\n")
    new_b = (golden_review.GOLDEN / f"{name}.json").read_bytes().replace(b"\r\n", b"\n")  # a CRLF checkout
    assert new_b[:new_b.index(b'"cavities"')] == old_b[:old_b.index(b'"cavities"')]  # every byte before, findings too
    old, new = json.loads(old_b), json.loads(new_b)
    assert old["cavities"] == [] and new.keys() == old.keys()


def golden(name):
    return json.loads((golden_review.GOLDEN / f"{name}.json").read_text(encoding="utf-8"))


def pair(name, nets):
    return max((c for c in golden(name)["cavities"] if c["nets"] == nets), key=lambda c: c["area_mm2"])


def test_e_e7_the_slot_lowers_the_first_mode_and_lpf915s_stitched_pair_has_no_dc_mode():  # design 5.12 E-E (7)
    whole, slotted = (pair(n, [["GND"], ["+3V3"]])["modes"][1]["f_hz"] for n in ("usb2_hs", "usb2_hs_gap"))
    assert slotted <= 0.95 * whole  # r2 measured 1.865 -> 1.676 GHz, -10.1 %
    lpf = pair("lpf915", [["GND"], ["GND"]])
    assert lpf["posts"] > 0 and min(m["f_hz"] for m in lpf["modes"]) >= 1e6
    rim = pair("emc_review", [["GND"], ["GND"]])
    assert rim["posts"] == 1 and min(m["f_hz"] for m in rim["modes"]) >= 1e6
    assert pair("emc_review", [["GND"], ["+3V3"]])["modes"][0]["f_hz"] == 0.0
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_golden_review.py -q`. Expected: the byte-for-byte and the plan 1 comparison tests PASS, and E-E7 FAILS on the empty cavities.
- [ ] **Step 3: `review_json`** writes `r.cavities`.
- [ ] **Step 4: Re-record once,** as `tools/golden_review.py`'s docstring rules.
  - In PowerShell: `Remove-Item -Recurse tests/fixtures/review; .venv\Scripts\python.exe tools/golden_review.py`.
  - Expected: exit 0, and `git status --short tests/fixtures` lists exactly the five modified files.
  - Read each file. Its findings are as before and its cavities are filled; emc_review holds the two In1/In2 cavities of Task 4.
  - Any other key that moved stops the task for a ruling. Never edit a golden by hand.
- [ ] **Step 5: Run them.** Run Step 2's command, then `tests/test_review_outputs.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py -q`. Expected: PASS.
- [ ] **Step 6: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review/outputs.py tests/fixtures/review tests/test_golden_review.py
git commit -m "test(review): review.json writes the cavities, and the five goldens re-recorded once, byte-identical to plan 1's up to cavities (Stage 5 design 5.3; ruling 2; gate E-E 7)"
graphify update .
```

---

### Task 7 [code]: The E-E confirmation tool and its frozen references

**Files:** Create `tools/ee.py`, `tests/test_ee.py` and `tests/fixtures/ee/references.json` (written by the tool's `--references`, in memory, with no openEMS).

**Interfaces:**
- **Consumes:**
  - `p0.enter`, `step`, `records`, `run_model`, `model_of`, `run_path`, `save`, `table`, `versions`, `machine` and `predicted_s`;
  - `runs.ensure_calibrated`, `load_settings` and `per_job_mcs`;
  - `spec.dc_pulse`, `with_pml` and `spec_hash`;
  - `stoprule.WINDOW_S`, `KEPT` and `RING_CEILING`;
  - `smooth_mesh_lines` and `waves.s_matrix`;
  - `cavity.solve`.
- **Produces, in `tools/ee.py`.** The constants:
  - the case: `A_MM, B_MM, D_MM, EPS_R = 50.0, 30.0, 0.8, 4.4`;
  - the mesh: `FINE_MM, CELL_IN_MM, RATIO = 0.2, 0.5, 1.3`;
  - `PORT = (round(2 + FINE_MM / 3, 6),) * 2`: 2.066667, on the thirds grid;
  - `SLAB_MM = 5.0`: the laminate's margin past the plates;
  - `F_MAX = 6.5e9`;
  - `T_MAX = 30e-9`. This is the architect's estimate. One corner port loads a Q of about 20 at f10, twice f1's two-port Q_L of 10.2, which gives about 25 ns to −60 dB. The ring rule may run on to `RING_CEILING`·T_MAX;
  - `AIR_MM = 15.0` and `CMAX_MM = C0 / F_MAX * 1e3 / 20`;
  - `PRESET = "normal"` and `STEP = "ee-cavity"`;
  - `F_GRID = np.arange(1e9, 6.5e9 + 1, 1e6)`;
  - `DELTA_MM = 0.412 * D_MM * (EPS_R + 0.3) / (EPS_R - 0.258)` (§5.12: Hammerstad's Δ at W/d → ∞);
  - the decision: `TOL = 0.02`, `PROMINENCE_DB = 3.0`, `MIN_PEAK = 0.01` and `NODAL = 0.1`;
  - `REFERENCES = p0.FIX / "ee" / "references.json"`, written once by `--references` and committed before any run.

  The functions:
  - `spec() -> dict`;
  - `z_in(t_u, u, t_i, i, f) -> np.ndarray`;
  - `peaks(f, re_z) -> list[float]`;
  - `eigen() -> list[dict]`, each `{"mn": [m, n], "f_hz", "plain_hz", "nodal"}`;
  - `references() -> dict`;
  - `decide(peaks_hz: list[float], modes: list[dict], tol: float = TOL) -> dict`;
  - `predict(s: dict, mcs: float) -> dict`;
  - `measure(out) -> dict`, `tables(result) -> str`, `write(out) -> dict` and `main(argv) -> int`.
- **`ee.json`'s top-level keys** are fixed here: `"gate"` ("E-E"), `"versions"`, `"spec_hash"`, `"references"` (`{"file": "tests/fixtures/ee/references.json", "sha256"}`), `"run"`, `"decision"` and `"calibration"`. `"decision"` is `decide()`'s result: `"verdict"`, `"matched"`, `"unmatched_peaks_hz"`, `"unmatched_modes_hz"` and `"offset_pct"`, the last None when nothing matched.

- [ ] **Step 1: The failing tests,** in `tests/test_ee.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import numpy as np
import pytest

import ee
import p0
from kicad_rf_studio import stoprule
from kicad_rf_studio.core.mesh.rule import lint_hits
from kicad_rf_studio.core.model.csx import PML_CELLS


def test_the_spec_is_design_5_12s_plane_pair_with_a_corner_port_in_air_under_pml():  # design 5.12 E-E run
    s = ee.spec()
    assert (s["boundary"], s["copper"], s["grid"]) == ("pml_8", "sheet", [])
    plate = {"x": [0.0, 50.0, 50.0, 0.0], "y": [0.0, 0.0, 30.0, 30.0]}
    assert s["metal"]["copper"] == [{**plate, "z": [0.0, 0.0]}, {**plate, "z": [0.8, 0.8]}]
    (m,) = s["materials"]
    slab = {"x": [-5.0, 55.0, 55.0, -5.0], "y": [-5.0, -5.0, 35.0, 35.0], "z": [0.0, 0.8]}  # laminate past the plates
    assert (m["eps"], m["kappa"], m["solids"]) == (4.4, 0.0, [slab])
    (p,) = s["ports"]
    assert ee.PORT[0] == pytest.approx(2.0, abs=0.1)
    assert (p["kind"], p["dir"], p["start"], p["stop"], p["part"]) == ("lumped", "z", [*ee.PORT, 0.0],
                                                                       [*ee.PORT, 0.8], False)
    exc = s["excitation"]
    assert (exc["f1"], exc["f2"], exc["t_max"], exc["window_s"]) == (0.0, 6.5e9, 30e-9, 2e-9)  # SI's DC pulse
    for axis, lo, hi in (("x", 0.0, 50.0), ("y", 0.0, 30.0)):
        lines = s["mesh"][axis]
        inner = lines[PML_CELLS:-PML_CELLS]
        assert ee.PORT[0] in lines and inner[0] <= lo - 15 and inner[-1] >= hi + 15
        assert lint_hits(np.array(lines), [(lo, 1), (hi, -1)], ee.FINE_MM) == []  # no line on a plate edge: thirds
        assert np.diff([v for v in lines if lo <= v <= hi]).max() <= 0.5 + 1e-9
        assert np.diff(lines).max() <= ee.CMAX_MM + 1e-9
    z = s["mesh"]["z"]
    assert {0.0, 0.8} <= set(z) and np.diff([v for v in z if 0 <= v <= 0.8]).max() <= 0.2 + 1e-9


def test_z_in_reads_a_resistor_and_peaks_refine_two_resonances_and_skip_bumps_and_ripple():  # the run's reading
    t = np.arange(4000) * 5e-12
    i = np.exp(-((t - 2e-9) / 2e-10) ** 2)
    assert np.allclose(ee.z_in(t, 50 * i, t, i, np.array([1e9, 3e9])), 50)
    f = ee.F_GRID
    lorentz = lambda f0, q: 1 / (1 + (2 * q * (f / f0 - 1)) ** 2)  # noqa: E731
    re_z = 1 + 40 * lorentz(1.5004e9, 30) + 30 * lorentz(3.0e9, 30) + 0.2 * lorentz(4.5e9, 5)  # 4.5 GHz: under 3 dB
    two = [pytest.approx(1.5004e9, abs=0.05e6), pytest.approx(3.0e9, abs=0.05e6)]
    assert ee.peaks(f, re_z) == two
    noisy = re_z - 1 + 1e-3 * (-1.0) ** np.arange(len(f))  # a lossless pair's troughs near 0, the DFT's ripple on them
    assert ee.peaks(f, noisy) == two  # the bump and the ripple stay under 1 % of the largest peak


def test_eigen_labels_both_solves_by_mn_and_flags_none_nodal_at_the_corner_port():  # design 5.12
    assert ee.DELTA_MM == pytest.approx(0.412 * 0.8 * 4.7 / 4.142)
    modes = ee.eigen()
    a, b = 50 + 2 * ee.DELTA_MM, 30 + 2 * ee.DELTA_MM
    assert len(modes) == 13 and len({tuple(m["mn"]) for m in modes}) == 13  # the non-DC modes from 1 to 6.5 GHz
    for m in modes:
        p, q = m["mn"]
        exact = 299792458 / (2 * np.sqrt(4.4)) * np.hypot(p / a, q / b) * 1e3
        assert m["f_hz"] == pytest.approx(exact, rel=5e-3) and m["f_hz"] < m["plain_hz"] and not m["nodal"]


def test_the_committed_references_are_the_solvers_and_are_never_regenerated():  # design 5.12: frozen before the run
    refs = json.loads(ee.REFERENCES.read_text(encoding="utf-8"))
    now = ee.references()
    assert {k: v for k, v in refs.items() if k != "modes"} == {k: v for k, v in now.items() if k != "modes"}
    assert [m["mn"] for m in refs["modes"]] == [m["mn"] for m in now["modes"]]
    for key in ("f_hz", "plain_hz"):
        assert np.allclose([m[key] for m in refs["modes"]], [m[key] for m in now["modes"]], rtol=1e-9, atol=0)
    with pytest.raises(SystemExit, match="never regenerated"):
        ee.main(["--references"])


EIG = [{"mn": [1, 0], "f_hz": 1.4e9, "plain_hz": 1.42e9, "nodal": False},
       {"mn": [0, 1], "f_hz": 2.4e9, "plain_hz": 2.43e9, "nodal": False},
       {"mn": [2, 0], "f_hz": 3.0e9, "plain_hz": 3.03e9, "nodal": True}]


def test_the_e_e_rule_matches_each_peak_to_its_nearest_non_nodal_mode_within_2_percent():  # design 5.12
    d = ee.decide([1.39e9, 2.44e9, 5.0e9], EIG)  # 5 GHz claims 2.4 GHz too; 2.44 GHz is nearer and keeps it
    assert d["verdict"] == "pass" and [m["peak_hz"] for m in d["matched"]] == [1.39e9, 2.44e9]
    assert d["unmatched_peaks_hz"] == [5.0e9] and d["unmatched_modes_hz"] == []
    assert d["offset_pct"] == pytest.approx(100 * np.mean([1.39 / 1.42 - 1, 2.44 / 2.43 - 1]))
    late = ee.decide([2.45e9], EIG)  # 2.08 % from 2.4 GHz
    assert (late["verdict"], late["unmatched_modes_hz"]) == ("fail", [1.4e9])
    none = ee.decide([], EIG)
    assert (none["verdict"], none["matched"], none["offset_pct"]) == ("incomplete", [], None)


def test_predict_counts_cells_and_prices_t_max_and_the_ring_ceiling():  # cost first (ruling 5)
    s = ee.spec()
    p = ee.predict(s, 100.0)
    cells = int(np.prod([len(s["mesh"][a]) for a in "xyz"]))
    assert p["cells"] == cells and 0.5e6 < cells < 2.5e6  # the critics' probe: about 1.15 M
    assert p["to_ceiling_s"] == pytest.approx(stoprule.RING_CEILING * p["to_t_max_s"])


def test_the_ee_step_runs_through_the_harness_with_the_fake_worker(p0_out, monkeypatch, capsys):  # ruling 5: fakes
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    assert ee.main(["--out", str(p0_out), "--cost"]) == 0
    assert {"cells", "dt", "to_t_max_s", "to_ceiling_s"} <= json.loads(capsys.readouterr().out).keys()
    assert ee.main(["--out", str(p0_out)]) == 0
    result = json.loads((p0_out / "ee" / "ee.json").read_text(encoding="utf-8"))
    assert set(result) == {"gate", "versions", "spec_hash", "references", "run", "decision", "calibration"}
    assert result["references"]["file"] == "tests/fixtures/ee/references.json"
    d = result["decision"]
    assert set(d) == {"verdict", "matched", "unmatched_peaks_hz", "unmatched_modes_hz", "offset_pct"}
    assert d["verdict"] in ("pass", "fail", "incomplete")
    assert "/" not in result["run"]["run_dir"] and "\\" not in result["run"]["run_dir"]  # a name, never a path
    assert (p0_out / "ee" / "ee.md").read_text(encoding="utf-8").startswith("## EE-1")
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_ee.py -q`. Expected: FAIL, with `ModuleNotFoundError: No module named 'ee'`.
- [ ] **Step 3: `tools/ee.py`.** Its docstring: "Gate E-E's openEMS confirmation (Stage 5 design 5.12), the controller's: a hand-written spec as p3a's, one run through p0, Re Z_in's peaks against the eigen-solve on the Δ-buffered outline, frozen in tests/fixtures/ee/references.json before the run. Run: python tools/ee.py --references | --out DIR [--cost]."
  - **`spec()`** is a full model spec, as `runs.calibration_spec` is. Its docstring says that the laminate runs SLAB_MM past the plates, as on a PCB pair, which is Hammerstad's Δ's assumption.
    - **The mesh, x and y:**
      - The fixed lines are each plate edge e's window of FINE_MM lines, `round(e + s·(FINE_MM/3 + k·FINE_MM), 6)`. Here s is +1 at the low edge, k runs over range(−5, 15), so the window holds the port's line, and s is −1 at the high edge, k over range(−5, 5). Each edge therefore sits a third of a cell from its inside line and two thirds from its outside line, with no line on it (the edge lint).
      - The fixed lines also hold the laminate's edges, lo − SLAB_MM and hi + SLAB_MM.
      - Then `board = smooth_mesh_lines(np.array(fixed), CELL_IN_MM, RATIO)`, and `with_pml([round(float(v), 6) for v in smooth_mesh_lines(np.array([*board, lo - AIR_MM, hi + AIR_MM]), CMAX_MM, RATIO)])`.
    - **The mesh, z:** `round(v, 6)` over `np.arange(-1, 1.81, 0.2)`, graded out to ±AIR_MM in the same way. The z faces at 0 and 0.8 are exempt from the edge lint.
    - **The excitation:** `dc_pulse(F_MAX, T_MAX, WINDOW_S)`.
    - **The materials:** one `substrate_0`, priority 10, eps 4.4, kappa 0.0, its solid the laminate box from z 0 to 0.8.
    - **The metal:** the two sheet plates; the lid `{"plate": None, "walls": []}`; no cylinders or curves.
    - **Port P1:** lumped at PORT from z 0 to 0.8, with `nodes [start, stop, start, stop]`.
    - **The keys:** `"grid": []`, `"copper": "sheet"` and `"boundary": "pml_8"`.
  - **`z_in`:** `S, _ = waves.s_matrix([(t_u, u[None], t_i, i[None])], f)`, then Z = Z0·(1 + S)/(1 − S), using s_matrix's own Z0 (the port DFT that already exists).
  - **`peaks`:**
    - Run `scipy.signal.find_peaks(20·log10(np.maximum(re_z, 1e-4 · re_z.max())), prominence=PROMINENCE_DB)`. The prominence is the design's "more than 3 dB above its neighbouring minima", and the floor keeps a trough's small negative values from making −240 dB dips.
    - Keep the peaks whose `re_z` is at least MIN_PEAK · `re_z.max()`.
    - Refine each by the parabola through its three points on re_z: f_k + Δf·(y₋ − y₊)/(2(y₋ − 2y_k + y₊)).
    - Return a list of floats.
  - **`eigen()`:**
    - `cavity.solve` at εr 4.4 on `box(0, 0, 50, 30).buffer(DELTA_MM, join_style="mitre")` to F_MAX, and on the plain box to 1.05·F_MAX (so that every buffered mode has its plain partner). Keep the non-DC modes from 1 GHz.
    - Label each list's modes by the nearest closed-form f_mn of its own rectangle (a + 2Δ by b + 2Δ for the buffered one; A12: the 50 × 30 box has no degenerate modes), and pair them by label.
    - "nodal" means |cos(mπ(x + Δ)/(a + 2Δ))·cos(nπ(y + Δ)/(b + 2Δ))| < NODAL at PORT.
    - Return the buffered modes under F_MAX in order: `{"mn", "f_hz", "plain_hz", "nodal"}`.
  - **`references()`:** `{"source": "tools/ee.py --references, before any E-E run: cavity.solve on the outline buffered by Hammerstad's delta and on the plain one", "delta_mm", "tol", "prominence_db", "min_peak", "nodal", "rule": "each peak takes its nearest non-nodal mode; a mode two peaks claim keeps the nearer, the other peak is recorded unmatched", "modes": eigen()}`.
  - **`decide`:**
    - Each peak takes its nearest non-nodal mode. When several peaks claim one mode, the nearest keeps it and the others go to `unmatched_peaks_hz`.
    - `matched` is a list of `{"peak_hz", "mode_hz", "plain_hz", "mn", "error_pct"}`.
    - `unmatched_modes_hz` lists the non-nodal modes that no peak kept.
    - `"verdict"`:
      - "incomplete" with no match;
      - "pass" when every matched |peak/mode − 1| ≤ tol;
      - else "fail".
    - `"offset_pct"` is the mean of 100·(peak/plain − 1) over the matched pairs, each against its own mode's plain value, or None with no match. This is the fringing bias.
  - **`predict`:**
    - cells = Π lines;
    - dt = 1/(c·√Σ 1/Δmin²), where Δmin is each axis's smallest step, in m;
    - `to_t_max_s = p0.predicted_s(1, 1, cells, dt, T_MAX, mcs)`, and `to_ceiling_s` the same at `stoprule.RING_CEILING * T_MAX`.
  - **`_run(s)`,** the step's work:
    - `run = p0.run_model(p0.model_of(s), PRESET, STEP, [1])`;
    - read the job's `waves.npz` (`p0.run_path(run["run_dir"]) / run["jobs"][0]["job"]`);
    - return `{**run, "peaks_hz": peaks(F_GRID, z_in(...).real)}`.
  - **`measure`:**
    - It reads the step's record: the verdict, t_stop, wall_s, cells, dt, MC/s, predicted_s and the peaks.
    - It reads REFERENCES, never `eigen()`, and calls `decide(peaks, refs["modes"], refs["tol"])`.
    - A job whose verdict is not in `KEPT` gives the decision "incomplete", with offset_pct None.
  - **`tables`:** EE-1, every peak and mode, matched or not; EE-2, the run.
  - **`write`:** `<out>/ee/ee.json` through `p0.save`, with the keys above. The calibration loses its host key, as in p3a's. `ee.md` goes beside it.
  - **`main`:**
    - `--references` writes REFERENCES through `p0.save`, and raises `SystemExit("… never regenerated …")` when the file exists.
    - Else it calls `p0.enter`.
    - With `--cost`, it prints `predict(spec(), runs.per_job_mcs(runs.ensure_calibrated(runs.load_settings()), 1))` as JSON and returns 0.
    - Else it runs `p0.step(out, STEP, spec_hash(spec()), partial(_run, spec()))`, then `write`, and returns 0, or 1 when the step raised.
- [ ] **Step 4: The references, once.** Run `.venv/Scripts/python tools/ee.py --references`: seconds, in memory, no openEMS. Expected: `tests/fixtures/ee/references.json` holds 13 modes, none nodal.
- [ ] **Step 5: Run them.** Use Step 2's command. Expected: PASS. No openEMS runs: the harness test uses the fake worker.
- [ ] **Step 6: Both suites, commit, graph.**

```bash
git add tools/ee.py tests/test_ee.py tests/fixtures/ee/references.json
git commit -m "feat(tools): ee.py, gate E-E's openEMS confirmation: the 50 x 30 mm plane pair's hand-written spec on a laminate, Re Z_in's peaks matched to the delta-buffered eigen-solve frozen before the run, within 2 %, the unbuffered offset recorded (Stage 5 design 5.12)"
graphify update .
```

---

### Task 8 [code]: `button.select` and the fake KiCad's selection

**Files:**
- Modify `button.py`: add `select` after `refill`.
- Modify `tests/fake_kicad.py`.
- Messages: E_KICAD_SELECT_OTHER_BOARD.
- Test: `tests/test_button.py`.

**Interfaces:**
- Produces `select(socket: str, token: str, board: Path, kiids: Sequence[str]) -> int`, which returns the count KiCad reports selected.
- `FakeKiCad(…, known: set[str] | None = None)`. Its `chosen: list[str]` holds what ClearSelection and AddToSelection left. `known` None means every KIID exists.

- [ ] **Step 1: The failing tests,** in `tests/test_button.py`:

```python
EMC = Path(__file__).parent / "fixtures" / "emc_review.kicad_pcb"


def test_select_clears_then_adds_objects_carrying_only_their_kiid_and_counts_kiCads_answer(kicad):  # 5.5; A13
    k = kicad(EMC, known={"a", "b"})  # kipy 0.8's add_to_selection reads only .id: this pins the duck typing
    assert button.select(k.url, k.token, EMC, ["a", "b", "c"]) == 2  # KiCad skips an unknown KIID
    assert k.seen == ["GetOpenDocuments", "ClearSelection", "AddToSelection"] and k.chosen == ["a", "b"]
    assert k.tokens == [k.token] * 3


def test_select_refuses_another_board_and_sends_nothing_else(kicad, tmp_path):  # design 5.5 Select
    other = kicad(tmp_path / "other.kicad_pcb")
    with pytest.raises(KrsError) as e:
        button.select(other.url, other.token, EMC, ["a"])
    assert (e.value.code, e.value.params) == ("E_KICAD_SELECT_OTHER_BOARD", {
        "board": str(EMC), "open": str(tmp_path / "other.kicad_pcb")})
    assert other.seen == ["GetOpenDocuments"]
    busy = kicad(EMC, errors={"AddToSelection": ["AS_BUSY"] * 9})
    with pytest.raises(KrsError) as e:
        button.select(busy.url, busy.token, EMC, ["a"])
    assert e.value.code == "E_KICAD_BUSY"
```

- [ ] **Step 2: Run them.** Expected: FAIL, with `AttributeError: … 'select'`.
- [ ] **Step 3: The code.**
  - **`select`** starts as `refill` does: `_kicad(socket, token)`, `until = time.monotonic() + BUSY_S`, and `get_board`, with E_KICAD_UNSUPPORTED read as E_KICAD_NO_BOARD. Then:
    - another board raises E_KICAD_SELECT_OTHER_BOARD {board, open};
    - `_call(pcb.clear_selection, until)`;
    - `len(_call(lambda: pcb.add_to_selection([SimpleNamespace(id=KIID(value=k)) for k in dict.fromkeys(kiids)]), until))`, with `KIID` from `kipy.proto.common.types.base_types_pb2`;
    - no zoom.

    Add a `ponytail:` comment: should a kipy bump move the method, the fallback is the public getters filtered by id (design §5.5).
  - **The fake's `response`:**
    - `"ClearSelection"` empties `chosen` and answers Empty.
    - `"AddToSelection"` unpacks `editor_commands_pb2.AddToSelection` and appends each id that is in `known` (all of them when `known` is None). It answers `SelectionResponse(items=[pack_any(board_types_pb2.Track(id=base_types_pb2.KIID(value=v))) for v in self.chosen])`.
  - **Messages:** the Task 8 row.
- [ ] **Step 4: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_button.py -q`. Expected: PASS.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/button.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/fake_kicad.py tests/test_button.py
git commit -m "feat(button): select, KiCad's selection cleared then the KIIDs added as objects carrying only their id, refused on another board with nothing selected, no zoom (Stage 5 design 5.5; A13)"
graphify update .
```

---

### Task 9 [code]: `control`'s review, its cells and "simulate this"

**Files:**
- Modify `gui/control.py`: `Handed` gains `notes`; the new code goes after `compare`.
- Messages: Task 9's rows, and QUOTED's `G_SIMULATE_SI` entry in `tests/test_sexpr.py`.
- Test: `tests/test_gui_control.py`.

**Interfaces.** Produces:
- `Handed.notes: tuple[tuple[str, dict], ...] = ()`, as its last field: New's status lines after a "simulate this" handoff;
- `REVIEW_FOLDER = "review"`;
- `@dataclass(frozen=True) class Reviewed`, with the fields `code: int`, `lines: list[tuple[str, dict]]`, `findings: list[dict]`, `cavities: list[dict]`, `board: Path` and `png: Path | None`;
- `review(board: Path, nets: list[str], f0: float | None, project: Path | None) -> Reviewed`;
- `finding_cells(findings) -> list[list[str]]`: the number, the rule, the net ("" for None), the layer ("" for None), and "(x, y)" to 3 decimals;
- `mode_cells(cavities) -> list[list[str]]`: one row per mode with f_hz > 0, holding `"{k}: {a}/{b} ({nets})"` (k the 1-based cavity index, the nets as I_CAVITY joins them), f in MHz to 1 decimal, and its marks as G_NEAR_* texts joined by "; ";
- `kiids(findings, rows) -> list[str]`: the selected rows' KIIDs of every kind, without repeats;
- `simulate_notes(finding: dict) -> list[tuple[str, dict]]`;
- `simulated(board: Path, net: str, handoff: Path | None, notes: Sequence[tuple[str, dict]]) -> Handed`.

- [ ] **Step 1: The failing tests,** in `tests/test_gui_control.py`:

```python
EMC, QSPI = FIX / "emc_review.kicad_pcb", FIX / "qspi_clk.kicad_pcb"


def test_control_reviews_into_the_data_folder_as_the_cli_writes_and_reads_it_back(fake):  # design 5.5; A9
    r = control.review(EMC, [], None, None)
    folder = runs.data_dir() / control.REVIEW_FOLDER
    data = json.loads((folder / "review.json").read_text(encoding="utf-8"))
    golden = json.loads((FIX / "review" / "emc_review.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in data.items() if k != "board"} == {k: v for k, v in golden.items() if k != "board"}
    assert (r.code, r.findings, r.cavities, r.png) == (0, data["findings"], data["cavities"], folder / "review.png")
    assert control.finding_cells(r.findings)[0] == ["1", "R1", "CLK_GAP", "F.Cu",
                                                   "({:.3f}, {:.3f})".format(*data["findings"][0]["at_mm"])]
    cells = control.mode_cells(r.cavities)
    assert len(cells) == sum(m["f_hz"] > 0 for c in r.cavities for m in c["modes"])  # the static mode is no row
    assert cells[0][0] == "1: In1.Cu/In2.Cu (GND / +3V3)"
    assert control.kiids(r.findings, [0]) == list(dict.fromkeys(k for ids in r.findings[0]["kiids"].values()
                                                                 for k in ids))
    lpf = control.review(FIX / "lpf915.kicad_pcb", ["RF_*"], 915e6, None)  # the folder is replaced
    marked = [m for c in lpf.cavities for m in c["modes"] if m["marks"]]
    near = [row[2] for row in control.mode_cells(lpf.cavities) if row[2]]
    assert near == ["; ".join(render("G_NEAR_CARRIER", n=k["n"], f_mhz=f"{k['f_hz'] / 1e6:g}") for k in m["marks"])
                    for m in marked]
    with pytest.raises(KrsError) as e:
        control.review(FIX / "missing.kicad_pcb", [], None, None)
    assert e.value.code == "E_BOARD_UNREADABLE"


def test_simulate_this_pre_fills_the_si_kind_with_the_presss_kicad_and_its_notes(fake):  # design 5.5
    si = [("G_SIMULATE_SI", {"net": "FLASH_CLK"})]
    h = control.simulated(QSPI, "FLASH_CLK", press(QSPI), si)  # the press's socket and token, read from its file
    assert (h.kind, h.net, h.socket, h.token, h.problem, {h.start, h.end}, h.notes) == (
        "si", "FLASH_CLK", "ipc://s", "T", None, {"U1.11", "U2.6"}, tuple(si))
    gap = control.simulated(EMC, "CLK_GAP", None, [])
    assert gap.problem == ("G_HANDOFF_SI_ENDS", {"net": "CLK_GAP", "count": 0, "pads": "T_NONE"})
    assert (gap.socket, gap.token) == ("", "")  # no press: no KiCad
    assert control.simulate_notes({"rule": "R3", "net": "CLK_EDGE", "ref_net": "+3.3V"}) == [
        ("G_SIMULATE_SI", {"net": "CLK_EDGE"}), ("G_SIMULATE_EDGE", {}), ("G_SIMULATE_REFERENCE", {"net": "+3.3V"})]
    assert control.simulate_notes({"rule": "R1", "net": "CLK_GAP", "ref_net": "+3V3"}) == [
        ("G_SIMULATE_SI", {"net": "CLK_GAP"})]  # +3V3 is power for both
```

- [ ] **Step 2: Run them.** Expected: FAIL, with `AttributeError`.
- [ ] **Step 3: The code.**
  - **`review`:**
    - `cli.review(str(board), nets=nets, project=None if project is None else str(project), f0=f0, output=runs.data_dir() / REVIEW_FOLDER, emit=…)` collects the lines.
    - On a non-zero exit, return no findings and no png. Else read `review.json` back.
    - It raises `cli.review`'s refusals.
    - Add three `ponytail:` comments:
      - the folder is replaced on each review, as compare/ is;
      - the pool's one thread waits for the review, seconds and about 20 s at 100 × 80 mm (§5.4), so a press's read queued meanwhile waits too;
      - review_png draws on this pool thread, as compare's note says.
  - **`simulate_notes`:**
    - G_SIMULATE_SI {net};
    - then G_SIMULATE_EDGE for R3;
    - then G_SIMULATE_REFERENCE {net: ref_net} when ref_net is a dotted power name that SI's classifier does not take as power: `ref_net is not None and DOTTED_POWER.fullmatch(_base(ref_net)) and not is_power(ref_net)`.
  - **`simulated`:**
    - `data = json.loads(handoff.read_text(encoding="utf-8")) if handoff else {}`, then socket and token = `data.get("socket", "")` and `data.get("token", "")`. These belong to the last press, read on the pool. A press's read still in flight therefore never leaves a stale socket.
    - `b = load_board(board)`, then `net, partner, ends, problem = _si_handed(b, [net], [])`.
    - Return `Handed(board, socket, token, _names(b.all_pads()), *(ends or ["", ""]), problem, "si", kinds=_antennas(b), net=net, partner=partner, notes=tuple(notes))`.
  - **Messages:** Task 9's rows, and QUOTED's `"G_SIMULATE_SI": ("G_NEW", "G_KIND_SI")`.
- [ ] **Step 4: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_gui_control.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/control.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_gui_control.py tests/test_sexpr.py
git commit -m "feat(gui): control.review runs the CLI's review into the data folder's review/ and reads review.json back, its findings' and modes' cells, and simulated, the SI pre-fill of a finding's net with the last press's KiCad and its status notes (Stage 5 design 5.5)"
graphify update .
```

---

### Task 10 [code]: The Review tab

**Files:**
- Modify `gui/window.py`:
  - `FINDING_COLUMNS` and `MODE_COLUMNS`;
  - `class ReviewView(QWidget)`, after `CompareView`;
  - in `MainWindow`: `project_page`, `cost_page` and `run_page` kept, the tab inserted, `watch`'s index, `start_review`, `pick_review_board`, `show_review`, and `tick`.
- Modify `tests/test_gui.py`.
- Messages: Task 10's rows.

**Interfaces:**
- Consumes Task 9's `control.review`, `finding_cells`, `mode_cells` and `Reviewed`.
- Produces:
  - `FINDING_COLUMNS = ("G_COL_NUMBER", "G_COL_RULE", "G_COL_NET", "G_COL_LAYER", "G_COL_PLACE")`;
  - `MODE_COLUMNS = ("G_COL_CAVITY", "G_COL_F_MHZ", "G_COL_NEAR")`;
  - `ReviewView`, which holds:
    - `board` (a QLineEdit), `browse`, `nets` (with the placeholder G_REVIEW_NETS_HINT), `f0`, `review_button`, `status` and `lines` (sentences);
    - `findings` (NoEditTriggers, SelectRows, ExtendedSelection), with `modes` under it, and `picture` (a QLabel in a resizable QScrollArea);
    - a horizontal QSplitter, with the two tables on the left and the picture on the right;
    - `display(lines, findings, modes, picture)`, and `rows() -> list[int]`, the selected rows sorted;
  - `MainWindow.review`, `reviewing`, `reviewed`, `project_page`, `cost_page` and `run_page`.

- [ ] **Step 1: The failing tests,** in `tests/test_gui.py`:
  - **The fixed indices change in this commit** (§5.5):
    - line 366's `again.tabs.currentIndex() == 1` becomes `== again.tabs.indexOf(again.cost_page)`;
    - line 754's `setCurrentIndex(3)` becomes `setCurrentIndex(w.tabs.indexOf(w.results))`;
    - line 758's `(w.tabs.currentIndex(), w.handoff, f.status.text()) == (0, handoff, "")` becomes `(w.tabs.currentWidget(), w.handoff, f.status.text()) == (w.project_page, handoff, "")`;
    - line 884's `currentIndex() == 0` becomes `currentWidget() is w.project_page`;
    - line 981's `tabText(3)` becomes `tabText(w.tabs.indexOf(w.results))`;
    - line 1512's `tabText(4)` becomes `tabText(w.tabs.indexOf(w.comparison))`.
  - In `test_the_window_fits_1200_by_800_…`, add before the kind loop: `assert w.tabs.count() == 7 and w.tabs.indexOf(w.review) == 1 and w.tabs.tabText(1) == render("G_TAB_REVIEW")`. The suite runs it in English, and the pt-BR run runs it in pt-BR.
  - Add:

```python
def test_the_review_leaves_the_gui_thread_in_under_50_ms_and_fills_its_tables_and_picture(window):  # 5.5; A13
    w = window()
    v = w.review
    v.board.setText(str(FIX / "emc_review.kicad_pcb"))
    start = time.perf_counter()
    v.review_button.click()
    assert time.perf_counter() - start < 0.05 and isinstance(w.reviewing, Future)
    assert v.status.text() == render("G_REVIEWING") and not v.review_button.isEnabled()
    w.reviewing.result(timeout=120)
    w.tick()
    r = w.reviewed
    assert v.findings.rowCount() == 2 and v.findings.item(0, 1).text() == "R1"
    assert v.modes.rowCount() == len(control.mode_cells(r.cavities)) > 0 and not v.picture.pixmap().isNull()
    assert v.lines.item(0).text() == control.text(*r.lines[0]) and v.status.text() == ""
    grab(w, "review")


def test_a_refused_review_empties_the_view_and_says_why(window, tmp_path):  # design 5.5
    w = window()
    w.review.board.setText(str(FIX / "emc_review.kicad_pcb"))
    w.review.review_button.click()
    w.reviewing.result(timeout=120)
    w.tick()
    w.review.board.setText(str(tmp_path / "missing.kicad_pcb"))
    w.review.review_button.click()
    w.reviewing.exception(timeout=60)
    w.tick()
    assert w.review.findings.rowCount() == w.review.modes.rowCount() == 0 and w.reviewed is None
    assert w.review.status.text().startswith(render("E_BOARD_UNREADABLE", path=str(tmp_path / "missing.kicad_pcb"),
                                                    reason="T_FILE_NOT_FOUND")[:20])
    w.review.f0.setText("lots")
    w.review.review_button.click()  # f0 is read on the GUI thread
    assert w.reviewing is None and w.review.status.text() != render("G_REVIEWING")
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_gui.py -q -k "review or fits or press or cost or retune or compare"`. Expected: FAIL, with `AttributeError: … 'review'`.
- [ ] **Step 3: The code.**
  - **The pages.** Keep the three `page(...)` calls as `self.project_page`, `self.cost_page` and `self.run_page`. After the tabs are added: `self.tabs.insertTab(1, self.review, render("G_TAB_REVIEW"))`.
  - **`watch`:** `self.tabs.setCurrentIndex(self.tabs.indexOf(self.cost_page if command == "cost" else self.run_page))`. `take_handoff`'s index 0 stays Project.
  - **`start_review`:**
    - f0 is read here, with `parse_frequency`, when the field is not blank. A refusal goes to the status line through `control.message`, and nothing starts.
    - The nets are the comma-separated names, stripped, with empty ones dropped.
    - `self.reviewing = self.pool.submit(control.review, Path(text), nets, f0, self.path)`.
    - Show G_REVIEWING, then call `self.tick()`.
  - **`pick_review_board`** works as `pick_board` does, into `review.board`.
  - **`show_review(done)`:**
    - An exception goes through `control.message` to the status line, with an empty view and `reviewed = None`. It is taken and never raised again, as `show_pads` takes it.
    - Else the status is cleared, the lines go in through `control.text`, the cells go in, and the png is shown when code is 0.
    - `reviewed` is the result when code is 0, else None.
  - **`tick`,** before `if self.path is None: return`: take the `reviewing` Future when it is done (show_review), then enable `review_button` while `reviewing is None`. The docstring names it.
  - **`closeEvent`'s docstring** names the review among the dropped work.
  - **Messages:** Task 10's rows.
- [ ] **Step 4: Run them.** Run Step 2's command, then the whole `tests/test_gui.py -q`. Expected: PASS.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_gui.py
git commit -m "feat(gui): the Review tab at index 1, the review on the pool with its findings, cavity modes and review.png, every fixed tab index now indexOf (Stage 5 design 5.5; A13)"
graphify update .
```

---

### Task 11 [code]: Select in KiCad, "simulate this" and the press rule

**Files:**
- Modify `gui/window.py`:
  - ReviewView's `select_button` and `simulate_button`, in a row under the findings;
  - `MainWindow.selecting`, `select_total`, `select_in_kicad`, `selected` and `simulate_this`;
  - `tick`'s enables;
  - `take_handoff`;
  - `show_pads`.
- Modify `tests/test_gui.py`.
- Messages: Task 11's rows, and QUOTED's `G_SELECT_MISSING` entry in `tests/test_sexpr.py`.

**Interfaces:** Consumes `button.select` and `control.kiids`, `simulate_notes` and `simulated`.

- [ ] **Step 1: The failing tests,** in `tests/test_gui.py`:

```python
def joined(*codes):
    return " ".join(control.text(code, params) for code, params in codes)


def test_simulate_this_pre_fills_new_and_keeps_the_presss_kicad(window):  # design 5.5 "simulate this"
    w = window()
    w.review.board.setText(str(FIX / "qspi_clk.kicad_pcb"))
    w.review.review_button.click()
    w.reviewing.result(timeout=120)
    w.tick()
    v, f = w.review, w.new_form
    assert not v.select_button.isEnabled() and not v.simulate_button.isEnabled()  # no press, no row
    v.findings.selectRow(0)  # R2 on FLASH_CLK
    w.tick()
    assert v.simulate_button.isEnabled() and not v.select_button.isEnabled()  # Select: only after a press
    v.simulate_button.click()
    note = joined(("G_SIMULATE_SI", {"net": "FLASH_CLK"}))
    assert w.tabs.currentWidget() is w.project_page and f.status.text() == note
    w.pads_read.result(timeout=60)
    w.tick()
    assert (f.kind.currentData(), {f.start.currentText(), f.end.currentText()}) == ("si", {"U1.11", "U2.6"})
    assert w.handed.socket == "" and not f.refill_button.isEnabled()  # no press: no KiCad to ask
    assert f.status.text() == note  # the note outlives the handoff (design 5.5)


def test_one_review_through_the_window_on_emc_review_select_and_simulate_this(window, kicad, tmp_path):  # 5.17 item 4
    board = tmp_path / "emc_review.kicad_pcb"
    board.write_bytes((FIX / "emc_review.kicad_pcb").read_bytes())
    k = kicad(board)
    w = window()
    v, f = w.review, w.new_form
    w.tabs.setCurrentWidget(v)
    w.take_handoff(press(board, socket=k.url, token=k.token))  # Review open: the press keeps it and fills its board
    assert w.tabs.currentWidget() is v
    w.pads_read.result(timeout=60)
    w.tick()
    assert v.board.text() == str(board) and f.refill_button.isEnabled()
    v.review_button.click()
    w.reviewing.result(timeout=120)
    w.tick()
    assert v.findings.rowCount() == 2 and v.modes.rowCount() > 0 and not v.picture.pixmap().isNull()
    v.findings.selectRow(0)
    w.tick()
    v.select_button.click()
    assert v.status.text() == render("G_SELECTING") and not v.select_button.isEnabled()
    w.selecting.result(timeout=60)
    w.tick()
    sent = control.kiids(w.reviewed.findings, [0])
    assert k.seen[-3:] == ["GetOpenDocuments", "ClearSelection", "AddToSelection"] and k.chosen == sent
    assert v.status.text() == render("G_SELECTED", count=len(sent))
    k.known = set()  # KiCad holds edits not yet saved: none of them is in its board
    v.select_button.click()
    w.selecting.result(timeout=60)
    w.tick()
    assert v.status.text() == render("G_SELECT_MISSING", count=0, total=len(sent))
    w.take_handoff(press(board, socket=k.url, token=k.token))  # a press read maybe in flight when Simulate is clicked
    v.findings.selectRow(1)  # R3 on CLK_EDGE
    w.tick()
    v.simulate_button.click()
    notes = [("G_SIMULATE_SI", {"net": "CLK_EDGE"}), ("G_SIMULATE_EDGE", {})]
    assert f.status.text() == joined(*notes)
    w.pads_read.result(timeout=60)
    w.tick()
    assert w.tabs.currentWidget() is w.project_page and f.kind.currentData() == "si" and w.handed.socket == k.url
    assert f.status.text() == joined(("G_HANDOFF_SI_ENDS", {"net": "CLK_EDGE", "count": 0, "pads": "T_NONE"}), *notes)
    w.tabs.setCurrentWidget(w.results)
    w.take_handoff(press(board, socket=k.url, token=k.token))  # Review not open: the press goes to Project
    assert w.tabs.currentWidget() is w.project_page
    w.pads_read.result(timeout=60)
    grab(w, "review-select")
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_gui.py -q -k "simulate or emc_review or refill or press"`. Expected: FAIL, with `AttributeError: … 'select_button'`.
- [ ] **Step 3: The code.**
  - **`tick`'s enables,** before the path guard, with `h = self.handed`:
    - Select while `h is not None and h.socket and self.reviewed is not None and v.rows() and self.selecting is None`;
    - Simulate while `self.reviewed is not None`, exactly one row is selected, and its finding's rule is R1, R2 or R3;
    - Refill while `h is not None and h.socket and self.refilling is None`. Only a press gives a KiCad, and a press's handoff always holds a socket;
    - the `selecting` Future is taken when it is done (`selected`).

    The docstring says all this.
  - **`select_in_kicad`:**
    - `kiids = control.kiids(self.reviewed.findings, v.rows())`, and `self.select_total = len(kiids)`;
    - `self.selecting = self.pool.submit(button.select, h.socket, h.token, self.reviewed.board, kiids)`;
    - show G_SELECTING, then call `self.tick()`.
  - **`selected(done)`:**
    - A refusal goes through `control.message`, with the exception taken as `show_pads` takes it.
    - Else show G_SELECTED {count} when count ≥ `select_total`, or G_SELECT_MISSING {count, total}.
  - **`simulate_this`:**
    - `finding = self.reviewed.findings[row]`, and `notes = control.simulate_notes(finding)`;
    - New's status = the notes' texts joined by a space;
    - `self.pads_read = self.pool.submit(control.simulated, self.reviewed.board, finding["net"], self.handoff, notes)`;
    - then `self.tabs.setCurrentIndex(self.tabs.indexOf(self.project_page))`.
  - **`take_handoff`:** `if self.tabs.currentWidget() is not self.review: self.tabs.setCurrentIndex(0)`.
  - **`show_pads`,** for a `Handed`:
    - also `self.review.board.setText(str(read.board))`;
    - its status becomes the problem's text and then the notes' texts, joined by a space, whenever either exists (`if read.problem: …` becomes that join);
    - a press's Handed has no notes, so its behaviour is unchanged.
  - **Messages:** Task 11's rows, and QUOTED's `"G_SELECT_MISSING": ("G_REVIEW",)`.
- [ ] **Step 4: Run them.** Run Step 2's command, then the whole `tests/test_gui.py` and `tests/test_sexpr.py`. Expected: PASS, the refill tests included.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/gui/window.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_gui.py tests/test_sexpr.py
git commit -m "feat(gui): Select in KiCad through the press's KiCad, simulate this into New's SI kind with its status lines kept through the handoff, a press keeping the Review tab current, and Refill only with a press's socket (Stage 5 design 5.5, 5.17 item 4; A13)"
graphify update .
```

---

### Task 12 [code]: The README's review tutorial and the release check's review step

**Files:**
- Modify `README.md`: a new `## Review tutorial` after the signal-integrity tutorial and before `## Development setup`.
- Modify `tools/release_check.py`: its docstring, `review`, `NEEDS` and `STEPS`.
- Tests: `tests/test_repo.py`, `tests/test_release_check.py`.

**Interfaces:**
- Produces `release_check.review(tmp: Path) -> tuple[str, str]`.
- `NEEDS["review"] = "install"`.
- `STEPS = (build, install, gui, antenna, si, review, plugin, privacy)`.

- [ ] **Step 1: The failing tests.**
  - In `tests/test_repo.py`:

```python
def test_the_readme_has_a_review_tutorial():  # design 5.15 plan 2; ruling 8
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.index("\n## Signal-integrity tutorial\n") < readme.index("\n## Review tutorial\n") < readme.index(
        "\n## Development setup\n")
    tutorial = readme.split("\n## Review tutorial\n", 1)[1].split("\n## ", 1)[0]
    for command in ("review tests/fixtures/emc_review.kicad_pcb -o review",
                    'review tests/fixtures/lpf915.kicad_pcb --net "RF_*" --f0 915MHz -o review'):
        assert f"kicad-rf-studio {command}\n" in tutorial, command
    assert "\n### What these results do not tell you\n" in tutorial
    for code in ("I_REVIEW_RELATIVE", "I_LIMIT_CAVITY", "I_LIMIT_REVIEW_KEEPOUT"):
        assert CATALOG[code] in tutorial, code
    assert all(CATALOG[c] in tutorial for c in ("G_TAB_REVIEW", "G_REVIEW_SELECT", "G_REVIEW_SIMULATE"))
```

  - In `tests/test_release_check.py`, the two STEPS assertions become `[…, "si", "review", "plugin", "privacy"]`. Add:

```python
def test_the_review_step_runs_review_on_the_releases_fixture_and_names_what_differs(tmp_path, monkeypatch):  # 5.17
    fixture, golden = ROOT / "tests" / "fixtures" / "emc_review.kicad_pcb", ROOT / "tests/fixtures/review/emc_review.json"
    lf = fixture.read_bytes().replace(b"\r\n", b"\n")
    with zipfile.ZipFile(tmp_path / "source.zip", "w") as z:  # git archive on a core.autocrlf checkout: CRLF
        z.writestr("tests/fixtures/emc_review.kicad_pcb", lf.replace(b"\n", b"\r\n"))
        z.write(golden, "tests/fixtures/review/emc_review.json")
    seen, data = [], json.loads(golden.read_text(encoding="utf-8"))

    def run(command, **kw):  # the fresh venv's review: it writes review.json where -o says
        seen.append((command, kw, (Path(kw["cwd"]) / command[2]).read_bytes()))
        out = Path(command[command.index("-o") + 1])
        out.mkdir(parents=True, exist_ok=True)
        (out / "review.json").write_text(json.dumps(data), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(release_check, "run", run)
    assert release_check.review(tmp_path)[0] == "PASS"
    (command, kw, board), = seen
    assert command[:3] == [release_check.program(tmp_path, "kicad-rf-studio"), "review", "emc_review.kicad_pcb"]
    assert board == lf  # LF, as the golden's sha256 hashes it (golden_antenna._board)
    assert kw["env"]["QT_QPA_PLATFORM"] == "offscreen"
    data = {**data, "cavities": []}
    assert release_check.review(tmp_path) == ("FAIL", "…/review/review.json differs from "
                                              "tests/fixtures/review/emc_review.json in: cavities")
    assert release_check.NEEDS["review"] == "install"
```

- [ ] **Step 2: Run them.** Command: `.venv/Scripts/python -m pytest tests/test_repo.py tests/test_release_check.py -q`. Expected: FAIL.
- [ ] **Step 3: `review(tmp)`.**
  - It writes the board from `tmp/source.zip` to `tmp/source/tests/fixtures/` as `z.read(name).replace(b"\r\n", b"\n")`, the rule of `golden_antenna._board`, and extracts the golden there too.
  - It runs `[program(tmp, "kicad-rf-studio"), "review", "emc_review.kicad_pcb", "-o", str(tmp / "review")]` through `run(command, timeout=300, cwd=<the board's folder>, env=isolated(tmp))`, so that the golden's board path, the file name, matches.
  - A non-zero exit gives `failed(...)`.
  - It compares the written JSON with the golden key by key, sorted. A difference gives the FAIL above. Else it returns `("PASS", "review wrote tests/fixtures/review/emc_review.json's review.json from tests/fixtures/emc_review.kicad_pcb in the fresh venv")`.
  - The module docstring says eight steps, with (f) review, (g) plugin and (h) privacy. Its "Every process of the gui, antenna, si and plugin steps" sentence names review too.
- [ ] **Step 4: The tutorial.**
  - **Capture the runs.** Run both commands from the repo root, each with `-o` into a fresh folder under TEMP: `.venv\Scripts\kicad-rf-studio review tests/fixtures/emc_review.kicad_pcb -o $env:TEMP\krs-review`, and the lpf915 one.
  - **Quote them.**
    - Quote each command with `-o review`. The output folder is replaced by `review`, a placeholder that the text names. No path and no host name appear.
    - For emc_review, quote the output whole. For lpf915, quote the R4 finding, the cavity lines and the limits.
  - **The prose covers:**
    - what each rule measures;
    - the tags and their sources;
    - f_max and L;
    - the cavity list and its marks, and why the static mode is not listed;
    - the GUI's Review tab, with its words as the catalog's English: Review, Select in KiCad, Simulate this;
    - that Select needs a press of the KiCad button.
  - **"### What these results do not tell you"** quotes I_REVIEW_RELATIVE, I_LIMIT_REVIEW_KEEPOUT and I_LIMIT_CAVITY as printed, and adds:
    - the thresholds' sources, and their calibration on three public boards only;
    - that R2 is for information;
    - the wire-grid estimate (about −20 dB at λ/20 and −10 dB at λ/10), which no finding prints (§5.2 R4).
- [ ] **Step 5: Run them.** Use Step 2's command. Expected: PASS.
- [ ] **Step 6: Both suites, commit, graph.**

```bash
git add README.md tools/release_check.py tests/test_repo.py tests/test_release_check.py
git commit -m "docs(readme): the review tutorial, quoting real review runs on emc_review and lpf915; release_check's review step, review.json against its golden in the fresh venv on the LF board (Stage 5 design 5.15, 5.17 item 2)"
graphify update .
```

---

### Task 13 [run]: E-E's openEMS confirmation (the controller's)

`<EMC_GATES>` is `$HOME\krs-gates-emc`: a gates folder outside TEMP and every work tree, apart from Stage 3's and Stage 4's. Each call starts with:

```powershell
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"; $g = Join-Path $HOME "krs-gates-emc"
$env:LOCALAPPDATA = "$g\data"; $env:XDG_DATA_HOME = "$g\data"
New-Item -ItemType Directory -Force "$g\logs" | Out-Null
```

**The rules:**
- One openEMS process at a time, and no pytest meanwhile.
- Each call runs in the background and is waited on.
- Before a run predicted to pass 1 h, tell the owner (the memory reaper).
- A failure gets superpowers:systematic-debugging, never a blind rerun.
- The references are Task 7's committed `tests/fixtures/ee/references.json`. Check that `git log --format="%h %s" -1 -- tests/fixtures/ee/references.json` names Task 7's commit before Step 2. They are never regenerated here.

- [ ] **Step 1: The prediction.** Run `& .venv\Scripts\python.exe -X utf8 tools\ee.py --out $g --cost *> "$g\logs\cost.log"`.
  - This first run calibrates the gates' data folder, a few minutes of openEMS.
  - Expected: about 1–1.5 M cells, with its time to T_max and to the ring ceiling.
  - Record both in the ledger.
- [ ] **Step 2: The run.**
  - Check the RAM as the controller's ruling 10 says: at least 8 GB free for a run predicted under 2 h, 14 GB past it after a pt-BR memory warning; else wait.
  - Run `& .venv\Scripts\python.exe -X utf8 tools\ee.py --out $g *> "$g\logs\ee.log"`.
  - Record the start, the end and the exit in `$g\logs\ledger.txt`, as Stage 4's template does.
  - Expected:
    - exit 0;
    - the job ends by the ring rule, its verdict in KEPT;
    - `$g\ee\ee.json` and `ee.md` written.
- [ ] **Step 3: The record.** Write `docs/validation/<date>-e-e-cavity.md`, with `<date>-e-e-cavity.json` a byte copy of `ee.json`. Its sections:
  1. The verdict: pass, fail or incomplete, any of which is recorded as it came.
  2. The inputs:
     - the commands, with `<EMC_GATES>` and `<openEMS folder>`;
     - the versions, the spec's hash and the mesh;
     - the laminate's margin past the plates;
     - the references file, its sha256 and the commit that froze it.
  3. EE-1: every peak and mode, matched or not, with each error against the Δ-buffered solve, and the unbuffered offset, which is the measured fringing bias, or "no peak matched".
  4. The machine time, predicted against measured.
  5. "Not a blocker for part A" (§5.12).

  The record holds no path and no host name. Then run:

  ```bash
  git commit -m "docs(validation): gate E-E's openEMS confirmation, the 50 x 30 mm plane pair's Re Z_in peaks against the delta-buffered eigen-solve frozen before the run and the measured fringing bias (Stage 5 design 5.12; controller recommendation, owner unavailable)"
  graphify update .
  ```

---

### Task 14 [code]: The cavity limit line names the measured bias

**Files:**
- Messages: I_LIMIT_CAVITY's EN and PT.
- `README.md`: the tutorial's quoted limit line.
- Test: `tests/test_repo.py`.

- [ ] **Step 1: The failing test:**

```python
def test_the_cavity_limit_names_e_es_measured_fringing_bias():  # design 5.12: named in the cavity's limit line
    (record,) = (ROOT / "docs" / "validation").glob("*-e-e-cavity.json")
    offset = json.loads(record.read_text(encoding="utf-8"))["decision"]["offset_pct"]
    text = CATALOG["I_LIMIT_CAVITY"]
    assert "(about 0.3 % for d 0.2 mm on 50 mm, 2 % for 1 mm" in text  # the scaling with d and a stays
    if offset is None:  # no peak matched: the estimate stands alone (not a blocker)
        assert "gate E-E" not in text
    else:
        assert f"; gate E-E's openEMS run measured {-offset:.1f} % on a 50 × 30 mm pair at d 0.8 mm)" in text
```

- [ ] **Step 2: Run it.** Expected: FAIL when the record holds an offset. With offset None, it passes as it stands: commit the test alone and skip Step 3. The record already says that no bias was measured.
- [ ] **Step 3: The text,** appended, never replacing anything:
  - EN: "…, 2 % for 1 mm)" becomes "…, 2 % for 1 mm; gate E-E's openEMS run measured {bias} % on a 50 × 30 mm pair at d 0.8 mm)", with the number written in to 1 decimal.
  - PT: "…, 2 % para 1 mm)" becomes "…, 2 % para 1 mm; a execução no openEMS da checagem E-E mediu {bias} % num par de 50 × 30 mm com d 0.8 mm)".
  - Then run `tools/catalog.py`, and update the README's quoted line to what `review` now prints.
- [ ] **Step 4: Run it,** then `tests/test_repo.py tests/test_sexpr.py tests/test_gui_control.py -q`. Expected: PASS.
- [ ] **Step 5: Both suites, commit, graph.**

```bash
git add src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale README.md tests/test_repo.py
git commit -m "feat(review): the cavity limit line names the fringing bias gate E-E's openEMS run measured, beside the d scaling (Stage 5 design 5.12)"
graphify update .
```

---

### Task 15 [doc]: Amendments A-72 to A-77

- [ ] **Step 1: The Stage 1 spec.** Tag each paragraph "(A-n, Stage 5 plan 2: controller recommendation, owner unavailable.)".
  - **A-72, §3.2 and §3.3:**
    - the GUI's review writes into a fixed `review` folder of the per-user data folder, replaced on each review, never into the user's KiCad project;
    - per cavity, `review.json`'s `cavities` holds:
      - the layers and the nets per side;
      - a place, d, εr, the area and the post count;
      - the grid and the narrow-slot flag;
      - the modes up to f_max with their marks, the static mode as 0.0;
    - the CLI prints each cavity, its modes (the static mode left out) and marks, and the cavity limits, before the findings' count.
  - **A-73, §4.6:**
    - the button's Select in KiCad clears KiCad's selection and adds the selected findings' KIIDs through the press's socket and token;
    - it refuses another board with E_KICAD_SELECT_OTHER_BOARD, and never zooms;
    - a press keeps the Review tab current and fills its board;
    - "simulate this" pre-fills New's SI kind for R1 to R3 with the last press's KiCad, and its status lines outlive the handoff;
    - Refill and Select need a press's socket.
  - **A-74, a new §7.9, "Plane-pair cavity modes (Stage 5)":**
    - the pair finder;
    - the cut-cell solve on 0.25 mm, with its posts;
    - the guards: 1.5 M cells, 1 GB of Lanczos vectors, slots under 0.5 mm, islands under 1 mm², cavities under 20 mm²;
    - the ±5 % marks and the clock suppression;
    - §5.4's stated limits verbatim, plus the disc post's up to 6 % and E-E's measured bias.
  - **A-75, §9.1 (d):** the release check's review step.
  - **A-76, a new §9.12, "E-E: cavity modes (Stage 5)":**
    - the CI cases (1) to (7), with their tolerances and the disc post's 7 % envelope;
    - the openEMS confirmation's reading of "matched": each peak takes its nearest non-nodal mode, and a mode two peaks claim keeps the nearer;
    - the references, frozen in `tests/fixtures/ee/references.json` before the run;
    - the laminate past the plates;
    - the results from Task 13's record: the verdict, the matched peaks' worst error, and the bias or "none measured".
  - **A-77, §10:**
    - the Stage 5 design's non-goals (its §3) join the deferred list;
    - the review and the cavity modes leave it: a note after Stage 4's "a whole-board or whole-plane model" names §7.9.
  - **The Status line** gains: "On `<date>`, Stage 5's plan 2 amended §3.2, §3.3, §4.6, §7, §9.1, §9.12 and §10 (A-72 to A-77) the same way."
- [ ] **Step 2: Test, commit, graph.** `.venv/Scripts/python -m pytest tests/test_repo.py -q` passes. This task is docs only, so Task 14's suites stand. Then:

```bash
git add docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs(spec): A-72 to A-77, the GUI's review folder and cavities, Select in KiCad, the cavity modes and their limits, the release check's review step, gate E-E with its results and the deferred list (Stage 5 plan 2; controller recommendation, owner unavailable)"
graphify update .
```

---

## The close (the controller's)

1. **The tip.** Run the full suite and the GUI tests in pt-BR, each alone in the background. Record their counts.
2. **The grabs, in both languages.** If `$env:TEMP\krs-font\krs_font.py` is gone, write it again as Stage 2 plan 3's Task 7 Step 5 gives it. Then:

   ```powershell
   $env:PYTHONPATH = "$env:TEMP\krs-font"
   foreach ($lang in @("en", "pt_BR")) {
     $env:KRS_TEST_LANGUAGE = $lang; $env:KRS_GRAB_DIR = "$env:TEMP\krs-grabs-s5p2-$lang"
     .venv\Scripts\python.exe -m pytest tests/test_gui.py -q -p krs_font -k "review or emc_review or simulate or fits_1200" }
   Remove-Item Env:KRS_GRAB_DIR, Env:KRS_TEST_LANGUAGE, Env:PYTHONPATH
   ```

   Read `review` and `review-select` in each folder with the Read tool. At 1200 × 800:
   - every word is the catalog's and unclipped;
   - both tables, the Select and Simulate row, and review.png are legible;
   - the seven tabs show without scroll buttons.

   A defect is fixed test-first in its owning task's file, in its own `fix(gui): …` commit, after both suites.
3. **The release check,** in the background: `.venv\Scripts\python.exe tools/release_check.py *> "$env:TEMP\krs-s5p2-release.log"`.
   - Expected: exit 0 and eight PASS lines (build, install, gui, antenna, si, review, plugin, privacy).
   - A review FAIL that names only `cavities` is a scipy or BLAS drift in the fresh venv. It goes to a ruling (a re-recording), never a code fix.
4. **A whole-branch review** against this plan and the design's plan 2 row. A fix commit re-runs step 1.
5. **The merge.** Fast-forward merge into `main` locally, then delete the branch. Nothing is pushed.

## Not in this plan

- **Plan 3's items** (ruling 1): the emission kind, schema 4, `new --emission`, the overrides, the stop branch and E-A.
- **The cavity extras:** a cavity panel in review.png, mode-shape images, the via-amplitude indicator and a fringing correction (§3, §6, A11).
- **Decoupling capacitors as posts** (A11: excluded, and stated).
- **Zoom in KiCad** (`run_action` is unstable), and GetSelection answering the fake's `chosen`.
- **The click-through of Select on a real KiCad 9.0.7 and 10.x:** the owner's (§7).
- **The native pt-BR review of the new terms:** cavidade, postes de via, portadora, marcas and clock. The owner's.
- **A test that a 0.5 mm slot resolves at h 0.25 within 0.5 %:** declined, since no probe measured it. The W_CAVITY_SLOT text no longer claims a resolution.

## Controller rulings (binding; as applied)

1. **Scope:** the plan 2 row only (Tasks 1 to 15).
2. **Pins:** the three suites run on every task. Task 6 alone re-records the review goldens, and its test proves byte for byte that only `cavities` moved.
3. **The solver** is in `core/cavity.py`, with §5.4's operator, post, Weyl count, guards, marks and limits. Ruling 3's mixed-cavity posts are Task 4's rule and test. One addition, with its reason: a memory guard, MEM_MAX, beside CELLS_MAX (AR-8).
4. **E-E (1) to (7)** are unit tests with §5.12's tolerances. Their references are computed from `scipy.special` or the closed form, and (7) is checked on the goldens.
5. **The confirmation run** is Task 13, the controller's:
   - in `<EMC_GATES>`, with the data variables set in the same call;
   - the cost predicted first, and one openEMS process at a time;
   - judged against references that Task 7 froze and committed before it;
   - recorded in `<date>-e-e-cavity.md`;
   - its bias named in the limit line by Task 14, or the estimate kept when nothing matched.
6. **The GUI** (Tasks 10 and 11):
   - index 1, with indexOf in the same commit (line 758 included);
   - the pool and the 50 ms test;
   - the data folder's review/;
   - the press rule;
   - Select's contract, with E_KICAD_SELECT_OTHER_BOARD;
   - "simulate this" through `_si_handed` and `show_pads`, with the press read from its handoff file;
   - every string a catalog code with its pt-BR msgstr, and quoted labels in QUOTED;
   - 1200 × 800 with seven tabs in both languages.
7. **Never a real KiCad:** the fake only.
8. **The README and the release check:** Task 12. The close runs the check.
9. **The amendments** are Task 15, the last, after the run.
10. **Tests:** as listed per task. §5.17 item 4 is Task 11's emc_review test.
11. **The close:** the controller's, with the grabs and the release check added.
12. **Fifteen tasks.** Task 13 is the controller's run, and Task 15 is docs only.

## Architect's rulings (controller recommendations, owner unavailable)

- **AR-1, the pours:** zone fills of any net. Copper graphics and tracks are not pours.
- **AR-2, `review.json`'s notes are untouched.** The cavity warnings and limits are CLI lines only, before I_REVIEW_FINDINGS. The JSON carries `h_mm` and `narrow_slot` per cavity.
- **AR-3, the marks:** at most one per source, at its nearest n = max(1, round(f/s)). The clock note is printed once per clock, with n = 11, and only when a cavity exists and 11·clock ≤ f_max.
- **AR-4, the frequencies** are stored in Hz, rounded to 1 kHz. A mode under 1 MHz is the static mode, stored as 0.0, and ARPACK starts from a vector of ones, so that a rerun gives the same bits. The static mode stays in review.json, where E-E7 reads it, but not in the CLI's lines or the GUI's table.
- **AR-5, "simulate this"'s status lines** are set at the click and carried on the Handed (`notes`). show_pads shows a pre-fill problem first, then the notes. The note outlives the handoff, as §5.5 asks.
- **AR-6, Refill and Select** are enabled only with a Handed whose socket is not empty. `simulated` reads the socket and token from the last press's handoff file on the pool, or "" with no press. A press's read in flight therefore never leaves a stale socket.
- **AR-7, E-E's run settings:**
  - the mesh: 0.2 mm cells around the plate edges and the port, each edge a third of a cell from its inside line; at most 0.5 mm over the plates; graded at 1.3 to λ/20 at 6.5 GHz in air;
  - T_MAX = 30 ns;
  - NODAL = 0.1 on the closed-form mode shape;
  - MIN_PEAK = 1 % of the largest Re Z;
  - the prominence as "3 dB above its neighbouring minima".
- **AR-8, the memory guard:** h also doubles while nx·ny·(2k + 1)·8 bytes > MEM_MAX = 1e9, with the same W_CAVITY_COARSE line.
- **AR-9, the disc post** (r ≥ h) is §5.4's rule, pinned within 7 % against the shorted circle. Its up to about 6 % low error is stated in I_LIMIT_CAVITY and §7.9.
- **AR-10, "matched" in E-E:** each peak takes its nearest non-nodal mode, as §5.12 words it. A mode that two peaks claim keeps the nearer peak, and the other peak is recorded unmatched. Buffered and plain modes are paired by their (m, n) label, never by sorted index.
- **AR-11, the laminate** runs 5 mm past the plates in E-E's run. That is a PCB plane pair, which is Hammerstad's Δ's assumption. The plates sit in air under PML about 15 mm off them.

## Open issues, ruled by the controller (2026-11-10; owner unavailable)

Each ruling is a controller recommendation.

1. **E-E's laminate (AR-11): confirmed.** The laminate runs 5 mm past the plates. A PCB plane pair sits on its laminate, and Hammerstad's edge extension assumes the dielectric goes on past the edge; "in air" (§5.12) is the surroundings under the PML. The record and the limit line say so.
2. **The matching reading (AR-10): confirmed** before Task 7 freezes it. Each peak takes its nearest non-nodal mode; a mode two peaks claim keeps the nearer, and the other peak is recorded unmatched. A lone peak far from every mode is matched to its nearest and fails the 2 % check: the run is not a blocker for part A, and the record names it.
3. **The disc post (AR-9): confirmed as §5.4 words it,** pinned within 7 % and stated in I_LIMIT_CAVITY and §7.9. An equivalent-radius α up to 2h joins the owner's items. A miss over 7 % in Task 2 stops for a ruling.
4. **The memory guard (AR-8): confirmed,** MEM_MAX = 1 GB of Lanczos vectors beside CELLS_MAX, with the same W_CAVITY_COARSE line.
5. **E-E's run settings (AR-7): confirmed** as the architect set them: T_MAX 30 ns, NODAL 0.1, MIN_PEAK 1 %, the 3 dB prominence and the thirds mesh. Task 13's `--cost` prints the prediction first.
6. **Eigenfrequencies in the goldens and the release step,** rounded to 1 kHz with ARPACK's fixed start and the static mode at 0.0: accepted. A FAIL that names only `cavities` in the fresh venv is a ruled re-recording, never a code fix.
7. **narrow_slot's reach** (a lone hole under 0.5 mm is flagged too): accepted. Its noise on dense boards is the owner's calibration item.
8. **The pt-BR terms:** 'clock' is kept, as the existing CLK wording has it. cavidade, postes de via, portadora, marcas and clock join the owner's native glossary review.
9. **Task 4's pinned areas** (413.5 mm², 582.7 mm² with 36 posts, and emc_review's 1697.5 and 80.0 mm² with its one tie post): the stop rule stands. A different measured value stops the task for a ruling, with the value.
10. **Task 13's memory rule** (amending its Step 2): a run predicted under 2 h starts with at least 8 GB of RAM free; a longer one with at least 14 GB, after a pt-BR memory warning to the owner. One openEMS process at a time, and no pytest meanwhile.
