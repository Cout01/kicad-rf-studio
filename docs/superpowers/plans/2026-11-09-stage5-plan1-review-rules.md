# Stage 5 Plan 1: The Review's Rule Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `kicad-rf-studio review BOARD` reads a KiCad board and, with no solver, measures four things about the tagged nets, each against its threshold and the threshold's public source:
- gap crossings (R1);
- reference changes (R2);
- edge runs (R3);
- the shield fences' gaps (R4).

It writes `review.json`, `review.csv` and `review.png`.

**Architecture:**
- **One package, `core/review/`, one module per responsibility:**
  - `planes.py`: the plane map and a track's reference;
  - `tags.py`: the tagging;
  - `rules.py`: the four rules;
  - `outputs.py`: the three files;
  - `__init__.py`: composes them in `review_board`.

  `cli.review` loads the board with `new`'s `_load` and writes through `core.post.outputs.write`. Plan 2's GUI calls `cli.review` the way Compare calls `compare_projects`.
- **The review only reads.**
  - It builds no model, starts no worker, and never imports openEMS or CSXCAD.
  - It imports matplotlib only inside `review_png`, as `summary_png` does.
  - v1's, the antenna's and SI's specs, hashes and outputs are untouched: their three golden suites stay green on every task.
- **The fixtures.**
  - One new four-layer board, `emc_review`, comes from `tools/make_fixtures.py` under Stage 4's isolation. Its voids are literal cut-outs, as §5.14 draws them.
  - `usb2_hs`, `usb2_hs_gap`, `qspi_clk` and `lpf915` are reused untouched.
  - Five golden `review.json` files pin the whole output.

**Tech Stack:**
- Python ≥ 3.11 (dev venv 3.14.2);
- shapely, numpy and matplotlib, which are already dependencies (no new one);
- KiCad 9's bundled Python, for Task 1's generator only;
- pytest, and `tools/catalog.py` (Babel, dev extra).

**Spec:**
- **The design, binding:** `docs/superpowers/specs/2026-11-09-stage5-emc-design.md`, §5.15's plan 1 row:
  - §5.1 to §5.3 and §5.14;
  - §5.16's A-70 and A-71;
  - §1 to §4, §6 and §8, as they bear on part A.
- **The controller's decisions:** `.superpowers/sdd/stage5-research/controller-decisions.md`, A1 to A10, BC1 and BC2 (git-ignored).
- **The research behind them** (git-ignored), in `.superpowers/sdd/stage5-research/`: r1 (rules and geometry), f4 (the defaults on three public boards), r4 §4 (CLI and catalog), r5 §1 (sources) and critic.md.
- **The Stage 1 spec:** `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md` (§2, §3.2, §3.3; A-1 to A-69). Task 12 adds A-70 and A-71.
- **The pt-BR design:** `docs/superpowers/specs/2026-10-29-ptbr-translation-design.md` (§5.1: a message whose grammar changes around a word splits into whole messages).

**Branch:**
- `stage5-plan1`, from `main` at `2820803`.
- This plan is `docs/superpowers/plans/2026-11-09-stage5-plan1-review-rules.md`.
- Commands run from the repo root with `.venv/Scripts/python`.
- A path without a folder is under `src/kicad_rf_studio/`.
- Line references are main's at `2820803`; find a moved line by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage5-plan1 main`. Then `git diff --stat 2820803 HEAD -- src tests tools po pyproject.toml` must print nothing.
2. Rule on the three readings under "Deviations from the design" below (D-1 to D-3): confirm each or change it. Record the result in the ledger. Tasks 4, 5 and 7 build on them. Done: see "Open issues, ruled by the controller" at the end (D-1 and D-3 confirmed, D-2 changed for pads).
3. Commit this plan on the branch.
4. After Task 12, the close below.

## Global Constraints

**From the design (verbatim):**
- §3, anti-goals:
  - "Any change to v1's, the antenna's or SI's model specs, spec hashes or output bytes."
  - "A pass/fail verdict, a severity tier beyond the catalog's W_ and I_ prefixes, or an absolute emission claim."
  - "A rule without a public source, a positive fixture and a negative one."
  - "A new dependency."
  - "A fixture that is not synthetic. The public boards f4 measured stay evidence and are never committed. No owner board, file or setting is read."
  - "Pushing."
- §4:
  - "`OLDEST_SUPPORTED` in `core/kicad/board.py` stays as it is."
  - "No new dependency. … kicad-python stays pinned `>=0.8,<0.9`."
  - "Fixtures are synthetic boards built by `tools/make_fixtures.py` under KiCad 9's pcbnew, in the isolated profile of Stage 1 §9.1 (A-3's isolation), as Stage 4 built its own."
  - "Every new message has its pt-BR msgstr in the same commit. Every G_ text keeps the existing rule: no backtick, flag or terminal syntax."

**This plan's own:**
- **v1, the antenna and SI byte for byte** (ruling 2):
  - `tests/test_golden_v1.py`, `tests/test_golden_antenna.py` and `tests/test_golden_si.py` stay green and unchanged on every task.
  - `tracer.POWER`, `classify` and every shared function keep their behaviour.
  - A task that moves a pin is wrong: stop for a ruling, and never re-record.
- **The review only reads:**
  - no model, no worker, no `--run-dir`, nothing written outside `-o`;
  - openEMS and CSXCAD are never imported (Stage 1 §3.1);
  - matplotlib is imported inside `review_png` only.
- **Messages:**
  - Every user-facing line is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, added in the task that first emits it. The section "Messages" below gives each row.
  - The procedure in each such task:
    1. run `.venv/Scripts/python tools/catalog.py`;
    2. set each new msgstr;
    3. run it again.
  - Templates are unique, and no T_ template has a field.
  - Numbers and identifiers keep their spelling: `test_sexpr.py`'s KEEP rule.
  - A template with "(B)" says "Preencher todas as zonas (B)" in pt-BR.
  - No line holds a backtick, a `--flag` or `-o`, so plan 2 needs no G_ twin for them.
- **Tests:**
  - test-first; a test that already passes says so in its run step;
  - never openEMS, KiCad, kicad-cli or the network (Task 1's generator run is a step, not a test);
  - `KrsError` tests check `.code` and `.params`;
  - tests never write under `tests/fixtures`.
- **Full suite** before every commit that touches src, tests, tools, po or pyproject.toml:
  - The suite: `.venv/Scripts/python -m pytest -q`, about 38 minutes. The Stage 4 exit record's last count was 2477 passed and 7 skipped; the controller records the count at `2820803` before Task 1.
  - Then, in PowerShell, the GUI tests in pt-BR: `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q; Remove-Item Env:KRS_TEST_LANGUAGE` (50 passed, 4 skipped).
  - Each runs alone, in the background, waited on. **Never two pytest processes at once.**
- **Isolation:**
  - Task 1's generator runs under A-3's isolation (its Step 4), and never touches the owner's KiCad, its settings or the user's Documents.
  - Tests never touch a real KiCad folder, KiCad's settings or the real data folder.
- **Git:**
  - no push; the pre-commit privacy gate runs on every commit, and `--no-verify` is never used;
  - **no commit message carries a co-author line**; use the messages as given;
  - no committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name: write `<KiCad 9 bin folder>`.
- **Files:** every new `.py` starts with `# SPDX-License-Identifier: GPL-3.0-or-later`; code and docs are in English.
- **Python** runs only with a script, `-c` or `-m`: never a bare interactive `python`, least of all in a background shell.
- **Workflow:**
  - `graphify query "<question>"` before reading code, and `graphify update .` after each commit.
  - Ponytail: the smallest code that does what the design says, with a `ponytail:` comment on each corner cut that has a known ceiling.
  - Reuse what exists:
    - `cli._load`;
    - `tracer._walk`, `_links`, `partner_net`, `antenna_kind`, `_base` and `_prefix`;
    - `chain_of` and `zstack`;
    - `region.coarse_cell`;
    - `shapes.arc_points`;
    - `outputs.write`;
    - `pipeline.command_line` and `project_path`;
    - `golden_antenna._board`;
    - shapely.

## Deviations from the design (for the controller before Task 1)

- **D-1, R4's gap (AR-3; Task 7).**
  - §5.2: "The gaps between fence vias are measured along the line, over the stretches the frame pads cover, so the frame's own cut-out is excluded."
  - This plan's reading: between two consecutive fence vias, the gap is `min(covered, max(dist, along − dA − dB))`, where:
    - `along` is the ring length between their projections;
    - `covered` is the frame-covered part of it;
    - `dist` is their straight distance;
    - dA and dB are their distances to the ring.
  - Why:
    - Measured along the hull alone, vias on the pads' centre line read 2·inset + pitch at each corner: 1.976 mm at emc_review's 0.976 mm pitch, over L.
    - The straight distance alone lets two vias side by side silence an unstitched frame.
  - The formula reads the pitch at a corner and on a side, 0 across an opening, and the whole unstitched stretch for a cluster.
- **D-2, R1's antipad radius (AR-2; Task 4).**
  - §5.2: "within that hole's radius plus 0.6 mm".
  - This plan's reading: a via's diameter/2 (its pad, which KiCad keeps on the plane layers), and a `thru_hole` pad's copper half-extent, `shapely.hausdorff_distance(Point(pad.at), pad.polygon)`, at least its drill/2 (the controller's ruling: drill/2 would flag a THT crystal's or oscillator's own antipad, a 1.5 mm pad on a 0.8 mm drill with 0.25 mm clearance being a 1.0 mm run).
  - Task 4's lone-hole test pins the via's diameter and the pad's copper.
- **D-3, R3's connector negative (Task 5).**
  - §5.14's row is lpf915's SMA at k = 2. RF_SMA ends 2.24 mm from the edge, against 2h = 1.42 mm, so k = 2 is silent whatever the exclusion.
  - The test keeps k = 2, and adds k = 5 with and without the connector class, so that the exclusion itself is exercised.

## Review Focus

1. **A wrong reference.** Each of these is a bug:
   - the track's own layer taken;
   - a far plane taken before a near one;
   - a tie broken the wrong way (the layer below first; then GND; then the first name);
   - the minority net of a split layer taken.

   R1 to R3 all read this reference. Checks, all in Task 2:
   - `test_the_reference_is_the_nearest_layer_whose_planes_touch_the_centre_line`;
   - `test_a_stripline_takes_the_nearer_plane_and_the_span_between_both`;
   - `test_the_majority_net_wins_then_ties_go_below_then_to_ground_then_to_the_first_name`.
2. **R1 counting what is not a gap, or missing a split.**

   These must not count:
   - a cut-out with the reference net's plane under it (the look-through);
   - a lone antipad;
   - a run under 1 mm;
   - a run inside an excluded hull grown by 3h.

   These must count:
   - a void several mm wide;
   - another net's island on the reference layer.

   Checks, all in Task 4:
   - `test_r1_fires_on_each_usb_line_over_in1s_slot_at_exactly_1_mm`;
   - `test_r1_fires_on_a_void_and_looks_through_a_cut_out_to_ground_below`;
   - `test_r1_counts_another_nets_island_on_the_reference_layer_as_a_void`;
   - `test_a_lone_holes_void_is_its_antipad_and_any_other_void_counts`;
   - `test_exclusions_hold_connectors_keepout_footprints_and_printed_antennas`.
3. **Over-tagging,** f4's largest source of false positives. Each of these is a bug:
   - a deny-list name tagged by a pattern;
   - a ground or power net tagged, a dotted `+3.3V` included;
   - flags that add to the patterns instead of replacing them;
   - a wrong first source.

   Checks: Task 3's three tests.
4. **Coordinates and ids.** Each of these is a bug:
   - y not negated on the way out;
   - a `-0.0`;
   - an id that moves on a rerun;
   - two findings with one id;
   - a KIID listed twice.

   Checks:
   - Task 8's `test_a_findings_id_is_its_rule_and_a_hash_of_its_kiids_and_place_numbered_on_a_clash`;
   - Task 9's `test_review_json_holds_schema_1s_keys_in_kicads_frame`.
5. **The review reaching past reading.** Each of these is a bug:
   - importing openEMS, CSXCAD or matplotlib at import time;
   - writing outside `-o`;
   - a refused write that still exits 0, or that leaves a new review.json beside an old file.

   Checks:
   - Task 9's and Task 10's import probes;
   - Task 10's `test_review_writes_to_the_working_folder_and_a_held_file_is_an_e_line`;
   - the three golden suites on every task.
6. **The fixture rebuild touching another board** (the golden pins hash them). Check: Task 1 Step 4's sha256 comparison against git, and its `git status`.

R4's corners, openings and via clusters are pinned by Task 7's four tests. The whole output on five boards is pinned by Task 11's goldens.

---

## Messages

Each code below gives its English template, then its pt-BR msgstr.
- Insert the W_ and I_ rows before `"E_INTERNAL"`, and the T_ rows after `"T_EXPECT_SI_REFERENCE"`.
- Each task adds its own rows.
- There are 23 codes in all.

**Task 4:**
- `W_EMC_GAP_CROSSING`:
  - EN: "#{n} R1: {net} on {layer} runs {run_mm} mm over a void in its {ref_net} reference ({ref_layer}, h {h_mm} mm), {extent_mm} mm across, at ({x_mm}, {y_mm}) mm; λ/20 at f_max is {l_mm} mm. Crossing a split or void in the reference is a known return-path fault (LearnEMC; Ansys SIwave's Net Crossing Split; HyperLynx DRC); a run counts from 1 mm, a cut measured on three public boards."
  - PT: "#{n} R1: {net} em {layer} passa {run_mm} mm sobre um vazio na sua referência {ref_net} ({ref_layer}, h {h_mm} mm), com {extent_mm} mm de largura, em ({x_mm}, {y_mm}) mm; λ/20 em f_max é {l_mm} mm. Cruzar uma divisão ou um vazio da referência é uma falha conhecida do caminho de retorno (LearnEMC; Net Crossing Split do Ansys SIwave; HyperLynx DRC); um trecho conta a partir de 1 mm, um corte medido em três placas públicas."

**Task 5:**
- `W_EMC_EDGE`:
  - EN: "#{n} R3: {net} on {layer} runs {d_mm} mm from the board edge at ({x_mm}, {y_mm}) mm, under {k}·h = {kh_mm} mm (h {h_mm} mm to {ref_layer}): about {share_pct} % of its ideal return current would lie past the edge. Critical nets belong at least 2h from the board edge (LearnEMC)."
  - PT: "#{n} R3: {net} em {layer} passa a {d_mm} mm da borda da placa em ({x_mm}, {y_mm}) mm, abaixo de {k}·h = {kh_mm} mm (h {h_mm} mm até {ref_layer}): cerca de {share_pct} % da sua corrente de retorno ideal ficaria além da borda. Redes críticas ficam a pelo menos 2h da borda da placa (LearnEMC)."

**Task 6:**
- `I_EMC_REF_CHANGE`:
  - EN: "#{n} R2: {net}'s via at ({x_mm}, {y_mm}) mm moves its reference from {from_net} on {from_layer} to {to_net} on {to_layer}; {path}: {nearest}, against {limit_mm} mm (TI SLLA656: within 200 mils, closer is better; Siemens: manage reference plane changes). For information."
  - PT: "#{n} R2: a via de {net} em ({x_mm}, {y_mm}) mm muda a referência de {from_net} em {from_layer} para {to_net} em {to_layer}; {path}: {nearest}, contra {limit_mm} mm (TI SLLA656: até 200 mils, quanto mais perto, melhor; Siemens: gerenciar trocas de plano de referência). Apenas informativo."
- The terms:

  | Code | EN | PT |
  | --- | --- | --- |
  | `T_EMC_RETURN_CAP` | "the nearest capacitor between the two nets" | "o capacitor mais próximo entre as duas redes" |
  | `T_EMC_RETURN_VIA` | "the nearest via joining the two layers" | "a via mais próxima que une as duas camadas" |

**Task 7:**
- `W_EMC_FENCE_PITCH`:
  - EN: "#{n} R4: the via fence ({fence}) leaves {gap_mm} mm of its line with no GND via, {lambdas} λ at f_max, at ({x_mm}, {y_mm}) mm, over λ/20 = {l_mm} mm (Bahl; Harper; Archambeault)."
  - PT: "#{n} R4: a cerca de vias ({fence}) deixa {gap_mm} mm da sua linha sem via de GND, {lambdas} λ em f_max, em ({x_mm}, {y_mm}) mm, acima de λ/20 = {l_mm} mm (Bahl; Harper; Archambeault)."
- The term:

  | Code | EN | PT |
  | --- | --- | --- |
  | `T_EMC_BOARD_EDGE` | "board edge" | "borda da placa" |

**Task 8:**
- `I_REVIEW_RELATIVE`:
  - EN: "Geometry rules, not a compliance verdict: each finding measures the board as saved against a published rule of thumb, named with its source; nothing here predicts a pass or a fail."
  - PT: "Regras de geometria, não um veredito de conformidade: cada achado mede a placa como foi salva contra uma regra prática publicada, citada com a sua fonte; nada aqui prevê aprovação ou reprovação."
- `I_REVIEW_BASIS`:
  - EN: "Review at f_max {f_max_ghz} GHz ({source}) and εr {eps_r}: λ/20 is {l_mm} mm; the edge rule's k is {edge_k}."
  - PT: "Revisão em f_max {f_max_ghz} GHz ({source}) e εr {eps_r}: λ/20 é {l_mm} mm; o k da regra da borda é {edge_k}."
- The tag lines, one whole message per source (pt-BR design §5.1):
  - `I_REVIEW_TAGS_FLAG`:
    - EN: "Nets you named: {nets}."
    - PT: "Redes que você indicou: {nets}."
  - `I_REVIEW_TAGS_PROJECT`:
    - EN: "Nets of the project's chain or lines: {nets}."
    - PT: "Redes da cadeia ou das linhas do projeto: {nets}."
  - `I_REVIEW_TAGS_PATTERN`:
    - EN: "Nets tagged by their names' patterns: {nets}."
    - PT: "Redes marcadas pelos padrões dos seus nomes: {nets}."
  - `I_REVIEW_TAGS_WALK`:
    - EN: "Nets reached through series parts and pair partners: {nets}."
    - PT: "Redes alcançadas pelos componentes em série e pelos pares diferenciais: {nets}."
- `I_REVIEW_NO_TAGS`:
  - EN: "No net is tagged, so R1 to R3 measure nothing; R4 still looks at the shields."
  - PT: "Nenhuma rede está marcada, então R1 a R3 não medem nada; R4 ainda examina as blindagens."
- `W_REVIEW_NET_UNMATCHED`:
  - EN: "No net the review can tag matches {pattern}; ground and power nets are never tagged."
  - PT: "Nenhuma rede que a revisão pode marcar corresponde a {pattern}; redes de terra e de alimentação nunca são marcadas."
- `W_EMC_LAYER_SKIPPED`:
  - EN: "A zone on {layer} is unfilled or hatched, so the layer would read as a void everywhere: R1 and R3 skip the tracks it would reference. Refill (B) in KiCad, save, and review again."
  - PT: "Uma zona em {layer} está sem preenchimento ou hachurada, então a camada pareceria um vazio em toda parte: R1 e R3 ignoram as trilhas que a teriam como referência. Use Preencher todas as zonas (B) no KiCad, salve e revise de novo."
- `I_EMC_NO_REFERENCE`:
  - EN: "No plane lies under {nets} on any layer, so R1 to R3 do not measure them."
  - PT: "Nenhum plano fica sob {nets} em nenhuma camada, então R1 a R3 não as medem."
- `I_LIMIT_REVIEW_KEEPOUT`:
  - EN: "Limit: board-level keep-out areas leave no geometry in the import, so the review sees only the fills they shape; a footprint's keep-out, a connector or a printed antenna takes its copper out of R1 and R3."
  - PT: "Limite: as áreas de exclusão da placa não deixam geometria na importação, então a revisão vê só os preenchimentos que elas moldam; a exclusão de um footprint, um conector ou uma antena impressa tira o seu cobre de R1 e R3."
- The terms:

  | Code | EN | PT |
  | --- | --- | --- |
  | `T_FMAX_CLI` | "the value given" | "o valor informado" |
  | `T_FMAX_CARRIER` | "5 times the carrier, at most 6 GHz" | "5 vezes a portadora, no máximo 6 GHz" |
  | `T_FMAX_SI` | "the signal-integrity project's f_max, at most 6 GHz" | "o f_max do projeto de integridade de sinal, no máximo 6 GHz" |
  | `T_FMAX_DEFAULT` | "the default: FCC 15.33(b)(1)'s upper measurement frequency for a device whose highest frequency is 500 to 1000 MHz" | "o padrão: a frequência máxima de medição da FCC 15.33(b)(1) para um dispositivo cuja frequência mais alta é de 500 a 1000 MHz" |

**Task 10:**
- `I_REVIEW_FINDINGS`:
  - EN: "Findings: {count}."
  - PT: "Achados: {count}."

The review also prints two existing codes: `W_FILLS_AS_SAVED` and `I_OUTPUTS` (`E_RESULTS_WRITE` in its place on a refused write). Neither needs a new row.

---

## File structure

```
tools/make_fixtures.py, tests/fixtures/emc_review.*; tests/test_fixtures.py, test_pads.py, test_stackup.py   # T1
core/review/__init__.py (docstring), core/review/planes.py; tests/test_review_planes.py                        # T2
core/review/tags.py; tests/test_review_tags.py                                                                 # T3
core/review/rules.py (constants, SOURCES, Finding, Group, exclusions, groups, r1), messages, po, .mo;
  tests/test_review_rules.py                                                                                   # T4
core/review/rules.py (return_share, r3), messages, po, .mo; tests/test_review_rules.py                         # T5
core/review/rules.py (r2), messages, po, .mo; tests/test_review_rules.py                                       # T6
core/review/rules.py (r4), messages, po, .mo; tests/test_review_rules.py                                       # T7
core/review/__init__.py (Review, REVIEW_LIMITS, resolve_f_max, finding_ids, review_board), messages, po, .mo;
  tests/test_review.py                                                                                         # T8
core/review/outputs.py; tests/test_review_outputs.py                                                           # T9
cli.py (review, _review, the parser), messages, po, .mo; tests/test_cli_review.py                              # T10
tools/golden_review.py, tests/fixtures/review/*.json, tests/test_golden_review.py                              # T11
the Stage 1 spec (A-70, A-71)                                                                                  # T12
```

---

### Task 1 [code]: The `emc_review` fixture

**Files:**
- Modify `tools/make_fixtures.py`:
  - `emc_review` goes after `line100`;
  - BOARDS gains `"emc_review": emc_review`;
  - `main`'s Stage 4 prefix tuple gains `"emc_"`, and its docstring names it.

  `zone`, `square` and `planes` are unchanged.
- Modify the tests:
  - `tests/test_fixtures.py` (NAMES);
  - `tests/test_pads.py` (the `test_pads_match_pcbnew` list, and one new test);
  - `tests/test_stackup.py` (the prefix tuple of `test_every_fixture_board_carries_its_generators_stackup`).
- Written by the tool: `tests/fixtures/emc_review.kicad_pcb` and `emc_review.pads.json`.

**Interfaces:**
- Produces `emc_review(b)`.
- Facts later tasks rely on. Coordinates are in KiCad's frame, in mm, y down; the importer negates y.
  - **The board:**
    - the outline is (100, 100)–(150, 150), on STACKUP_4L: F.Cu, 0.2 mm, In1.Cu, 1.04 mm, In2.Cu, 0.2 mm, B.Cu;
    - every zone is drawn to the outline with `square`, and KiCad's 0.5 mm copper-to-edge clearance stops its fill 0.5 mm in, as `coupon`'s comment and lpf915 show.
  - **In1.Cu:** GND, as five zones that leave two boxes bare, overlapping 0.5 mm as `planes(slot=)`'s do:
    - box 1, (110, 105)–(116, 115);
    - box 2, (110, 120)–(116, 130).
  - **In2.Cu:**
    - +3V3, as four zones around (107, 117)–(119, 133);
    - a GND island, (108, 118)–(118, 132), 1 mm clear of them inside that frame, tied to In1.Cu's GND by a via at (109, 119).
  - **CLK_EDGE:** a 0.5 mm F.Cu track from (103, 100.6) to (123, 100.6). Its edge is 0.35 mm from the outline, and GND covers its whole centre line.
  - **CLK_GAP:** a 0.33 mm F.Cu track from (103, 110) to (123, 110), across box 1, with +3V3 under the box on In2.Cu.
  - **CLK_LOOK:** the same at y 125, across box 2, with the GND island under it on In2.Cu.
  - **CLK_MID:** a 0.33 mm F.Cu track from (103, 140) to a CLK_MID via at (113, 140), then on B.Cu to (123, 140). `decoupled` puts C1 at (113, 140.75): its pads are 0.890 mm from the via.
  - **SH1:** lpf915's `RF_Shielding:Wuerth_36103205_20x20mm` at (137, 137), its pads GND, with TP1 (net RF) at its centre. 84 GND vias sit on its pads' centre line, the square 126.75–147.25, 20.5/21 = 0.976 mm apart.
  - **The vias:** 88 in all, 86 of them GND.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_fixtures.py`'s NAMES and `test_pads_match_pcbnew`'s list gain `"emc_review"`.
  - `test_stackup.py`'s tuple becomes `("usb2_hs", "qspi_clk", "p4", "si_", "emc_")`.
  - In `tests/test_pads.py`, the imports gain `import shapely`, `LineString` in the `shapely.geometry` import, and `classify` beside `load_board`. Then add:

```python
def test_the_emc_review_fixture():  # Stage 5 design 5.14: emc_review, a positive or negative for each rule
    b = load_board(FIX / "emc_review.kicad_pcb")
    assert b.copper_layers == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu") and b.outline.bounds == (100.0, -150.0, 150.0, -100.0)
    assert sorted({(a.layer, a.net) for a in b.areas if a.source == "zone"}) == [
        ("In1.Cu", "GND"), ("In2.Cu", "+3V3"), ("In2.Cu", "GND")]
    assert sorted((t.net, t.layer, t.width) for t in b.tracks if t.net.startswith("CLK")) == [
        ("CLK_EDGE", "F.Cu", 0.5), ("CLK_GAP", "F.Cu", 0.33), ("CLK_LOOK", "F.Cu", 0.33), ("CLK_MID", "B.Cu", 0.33),
        ("CLK_MID", "F.Cu", 0.33)]
    c = classify(b)
    assert (c.shields, c.connectors) == ({"SH1"}, frozenset())

    def on(layer, net):
        return shapely.union_all([a.polygon for a in b.areas if (a.layer, a.net, a.source) == (layer, net, "zone")])

    gnd1 = on("In1.Cu", "GND")
    assert gnd1.covers(LineString([(103, -100.6), (123, -100.6)]))  # CLK_EDGE over GND, its centre 0.6 mm in
    for y in (110, 125):  # CLK_GAP's and CLK_LOOK's cut-outs: bare over x 110 to 116 exactly
        assert gnd1.covers(LineString([(103, -y), (110, -y)])) and gnd1.covers(LineString([(116, -y), (123, -y)]))
        assert not gnd1.intersects(LineString([(110.001, -y), (115.999, -y)]))
    assert on("In2.Cu", "+3V3").covers(LineString([(103, -110), (123, -110)]))  # +3V3 under box 1
    assert on("In2.Cu", "GND").covers(LineString([(108.5, -125), (117.5, -125)]))  # GND under box 2 only
    assert not on("In2.Cu", "GND").intersects(LineString([(103, -110), (123, -110)]))
    assert (len(b.vias), len([v for v in b.vias if v.net == "GND"])) == (88, 86)
    assert round(min(math.dist(p.center, (113, -140)) for p in b.footprints["C1"].pads), 3) == 0.89
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_fixtures.py tests/test_pads.py tests/test_stackup.py -q -k "emc_review"`. Expected: FAIL with `FileNotFoundError` on `emc_review.kicad_pcb`.
- [ ] **Step 3: The generator,** `emc_review`, as given:

```python
def emc_review(b):
    """The review's board (Stage 5 design 5.14): 50 x 50 mm on STACKUP_4L, every zone drawn to the outline (KiCad's
    0.5 mm edge clearance stops the fills 0.5 mm in). In1.Cu is GND as five zones that leave two 6 x 10 mm boxes bare,
    overlapping 0.5 mm as planes(slot=)'s do; In2.Cu is +3V3 as four zones round a GND island under the second box, 1 mm
    clear of it, the island tied to In1.Cu by a GND via. CLK_EDGE, 0.5 mm wide, runs 0.35 mm from the top edge over GND
    (R3's positive); CLK_GAP crosses the first box, +3V3 under it (R1's positive, a void); CLK_LOOK crosses the second,
    GND under it (R1's look-through negative); CLK_MID goes from F.Cu to B.Cu at a via 0.89 mm from C1's pads, +3V3 and
    GND (R2's negative); SH1, lpf915's frame, with TP1 inside it and a GND via every 0.976 mm on its pads' centre line
    (R4's negative)."""
    rect(b, pcbnew.Edge_Cuts, 100, 100, 150, 150)
    for r in ((100, 100, 110, 150), (116, 100, 150, 150), (109.5, 100, 116.5, 105), (109.5, 115, 116.5, 120),
              (109.5, 130, 116.5, 150)):
        square(b, pcbnew.In1_Cu, "GND", *r)
    for r in ((100, 100, 107, 150), (119, 100, 150, 150), (106.5, 100, 119.5, 117), (106.5, 133, 119.5, 150)):
        square(b, pcbnew.In2_Cu, "+3V3", *r)
    square(b, pcbnew.In2_Cu, "GND", 108, 118, 118, 132)
    via(b, (109, 119))  # the island's tie to In1.Cu's GND, which keeps KiCad's island removal off it
    track(b, "CLK_EDGE", 0.5, (103, 100.6), (123, 100.6))
    track(b, "CLK_GAP", W_SE, (103, 110), (123, 110))
    track(b, "CLK_LOOK", W_SE, (103, 125), (123, 125))
    track(b, "CLK_MID", W_SE, (103, 140), (113, 140))
    via(b, (113, 140), "CLK_MID")
    track(b, "CLK_MID", W_SE, (113, 140), (123, 140), layer=pcbnew.B_Cu)
    decoupled(b, (113, 140.75))
    place(b, "RF_Shielding:Wuerth_36103205_20x20mm", "SH1", "SHIELD", (137, 137), 0, {"1": "GND"})
    place(b, TP1MM, "TP1", "TP", (137, 137), 0, {"1": "RF"})
    lo, hi, n = 126.75, 147.25, 21  # the frame's 1 mm pads' centre line
    for k in range(n):
        s = lo + (hi - lo) * k / n
        for at in ((s, lo), (hi, s), (lo + hi - s, hi), (lo, lo + hi - s)):
            via(b, at)
```

  `main`'s line becomes `stage4 = name.startswith(("usb2_hs", "qspi_clk", "p4", "si_", "emc_"))`, and its docstring lists `emc_*` with Stage 4's four-layer boards.
- [ ] **Step 4: Generate only `emc_review`, under A-3's isolation,** in one PowerShell call, then compare every other board with git:

```powershell
$kp = Join-Path (Get-Location) 'build\kicad-profile'; New-Item -ItemType Directory -Force $kp | Out-Null
Get-ChildItem env: | Where-Object { $_.Name -like 'KICAD*' } | ForEach-Object { Remove-Item "env:$($_.Name)" }
if (Test-Path env:TMPDIR) { Remove-Item env:TMPDIR }
$env:APPDATA = $kp; $env:LOCALAPPDATA = $kp  # the script itself points KICAD_*_HOME, TEMP and TMP at $kp
& "<KiCad 9 bin folder>\python.exe" tools/make_fixtures.py tests/fixtures emc_review
"exit $LASTEXITCODE"; git status --short tests/fixtures
.venv/Scripts/python -c "import hashlib, pathlib, subprocess; run = lambda *a: subprocess.run(a, capture_output=True, check=True).stdout; files = run('git', 'ls-files', 'tests/fixtures/*.kicad_pcb', 'tests/fixtures/*.pads.json').decode().split(); bad = [f for f in files if hashlib.sha256(pathlib.Path(f).read_bytes().replace(b'\r\n', b'\n')).digest() != hashlib.sha256(run('git', 'show', 'HEAD:' + f)).digest()]; print(len(files), 'tracked boards and pad files,', len(bad), 'changed', bad)"
```

  Expected:
  - `exit 0`;
  - `git status` lists exactly `?? tests/fixtures/emc_review.kicad_pcb` and `?? tests/fixtures/emc_review.pads.json`;
  - the last line reads `90 tracked boards and pad files, 0 changed []`.

  Never start KiCad itself or kicad-cli.
  - If any other file changed, stop: the goldens pin those boards by hash.
  - If a fact of Step 1 fails on the real fills, report the measured value for a ruling, and do not move the fixture's numbers. This covers an island removed, a fill gap between the overlapping zones, or a box edge off by more than 1 µm.
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_board.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py tests/test_repo.py -q`. Expected: PASS, and `test_board.py`'s sweep reads `emc_review` with no warning.
- [ ] **Step 6: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add tools/make_fixtures.py tests/test_fixtures.py tests/test_pads.py tests/test_stackup.py tests/fixtures/emc_review.*
git commit -m "test(fixtures): emc_review, a four-layer review board: a clock along the edge, a clock across an In1 cut-out over +3V3, one across a cut-out over a GND island, a bridged layer change and a stitched shield frame (Stage 5 design 5.14)"
graphify update .
```

---

### Task 2 [code]: The plane map and the reference

**Files:**
- Create:
  - `core/review/__init__.py`, holding only its docstring: "The geometry review (Stage 5 design 5.1 to 5.3): rules R1 to R4 over tagged nets, no solver.";
  - `core/review/planes.py`;
  - `tests/test_review_planes.py`.

**Interfaces:**
- Consumes `Board`, `CopperArea`, `Track`; `Classes`; `tracer._base`; `shapes.arc_points`; `zstack.Slab`.
- Produces, in `core/review/planes.py`:
  - `DOTTED_POWER = re.compile(r"\+\d+\.\d+V\w*")` (`+3.3V`, `+1.8V`; design §5.1, f4);
  - `Ref(layer: str, net: str, h: float, b: float | None)`, frozen:
    - h is the dielectric from the track's copper to `layer`, in mm;
    - b is the dielectric between the planes on both sides, for stripline; else None;
  - `PlaneMap(planes: dict[str, dict[str, BaseGeometry]], gnd: frozenset[str], layers: tuple[str, ...], skipped: tuple[str, ...], h: dict[tuple[str, str], float])`, frozen;
  - `centre_line(t: Track) -> LineString`;
  - `plane_nets(board, classes) -> frozenset[str]`;
  - `plane_map(board, classes, zs) -> PlaneMap`;
  - `cover(pm, net) -> BaseGeometry`;
  - `reference(pm, layer, line) -> Ref | None`.

- [ ] **Step 1: Write the failing tests,** `tests/test_review_planes.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path

from shapely.geometry import LineString, box

from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.kicad.board import CopperArea
from kicad_rf_studio.core.kicad.tracer import is_power
from kicad_rf_studio.core.review.planes import (DOTTED_POWER, PlaneMap, Ref, centre_line, plane_map, plane_nets,
                                                reference)

FIX = Path(__file__).parent / "fixtures"
LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def mapped(name, edit=lambda b: None):
    b = load_board(FIX / f"{name}.kicad_pcb")
    edit(b)
    c = classify(b)
    return b, c, plane_map(b, c, zstack(b.stackup, b.copper_layers))


def line_of(b, net, layer):
    return centre_line(next(t for t in b.tracks if (t.net, t.layer) == (net, layer)))


def dotted(b):  # usb2_hs's +3V3 named as KiCad's +3.3V power symbol names it
    b.areas = [replace(a, net="+3.3V") if a.net == "+3V3" else a for a in b.areas]
    b.nets = tuple("+3.3V" if n == "+3V3" else n for n in b.nets)


def test_the_plane_map_is_each_ground_or_power_nets_zone_fills_by_layer():  # design 5.1
    b, _, pm = mapped("usb2_hs_gap")
    assert {(layer, net) for layer, nets in pm.planes.items() for net in nets} == {("In1.Cu", "GND"), ("In2.Cu", "+3V3")}
    gnd = pm.planes["In1.Cu"]["GND"]
    assert gnd.covers(LineString([(110, -100), (115, -100)])) and not gnd.intersects(LineString([(116.2, -100),
                                                                                                 (116.8, -100)]))
    assert (pm.layers, pm.skipped, pm.gnd) == (LAYERS, (), frozenset({"GND"}))
    assert [pm.h[k] for k in (("F.Cu", "In1.Cu"), ("F.Cu", "In2.Cu"), ("F.Cu", "B.Cu"), ("B.Cu", "In1.Cu"))] == [
        0.2, 1.24, 1.44, 1.24]  # dielectric only, summed over the slabs between


def test_a_dotted_power_name_is_a_plane_net_though_tracer_power_misses_it():  # design 5.1; f4
    assert DOTTED_POWER.fullmatch("+3.3V") and DOTTED_POWER.fullmatch("+1.8V") and not is_power("+3.3V")
    b, c, pm = mapped("usb2_hs", dotted)
    assert "+3.3V" in plane_nets(b, c) and "+3.3V" not in c.power and set(pm.planes["In2.Cu"]) == {"+3.3V"}


def test_an_unfilled_or_hatched_zones_layer_is_skipped():  # design 5.1
    def warned(b):
        b.warnings = [("W_ZONE_NOT_FILLED", {"uuid": "z", "layer": "In2.Cu"}),
                      ("W_COPPER_DROPPED", {"kind": "T_HATCHED_ZONE", "layer": "In1.Cu", "uuid": "y"}),
                      ("W_COPPER_DROPPED", {"kind": "gr_text", "layer": "B.Cu", "uuid": "t"})]

    assert mapped("usb2_hs", warned)[2].skipped == ("In1.Cu", "In2.Cu")  # top to bottom; text is not a zone


def test_the_reference_is_the_nearest_layer_whose_planes_touch_the_centre_line():  # design 5.2
    b, _, pm = mapped("qspi_clk")
    assert reference(pm, "F.Cu", line_of(b, "FLASH_CLK", "F.Cu")) == Ref("In1.Cu", "GND", 0.2, None)
    assert reference(pm, "B.Cu", line_of(b, "FLASH_CLK", "B.Cu")) == Ref("In2.Cu", "+3V3", 0.2, None)
    own = PlaneMap({"F.Cu": {"GND": box(0, -1, 10, 1)}}, frozenset({"GND"}), LAYERS, (), pm.h)
    assert reference(own, "F.Cu", LineString([(1, 0), (9, 0)])) is None  # never the track's own layer


def test_a_stripline_takes_the_nearer_plane_and_the_span_between_both():  # design 5.2
    b, _, pm = mapped("qspi_clk", lambda b: b.areas.append(CopperArea("B.Cu", "GND", b.outline, "zone", "z")))
    assert reference(pm, "In2.Cu", line_of(b, "FLASH_CLK", "B.Cu")) == Ref("B.Cu", "GND", 0.2, 1.24)


def test_the_majority_net_wins_then_ties_go_below_then_to_ground_then_to_the_first_name():  # design 5.2
    h = {(x, y): 0.2 for x in LAYERS for y in LAYERS if x != y}
    line, plate = LineString([(1, 0), (9, 0)]), box(0, -1, 10, 1)
    pm = PlaneMap({"F.Cu": {"VDD": plate}, "B.Cu": {"VCC": plate}}, frozenset({"GND"}), LAYERS, (), h)
    assert reference(pm, "In1.Cu", line) == Ref("B.Cu", "VCC", 0.2, 0.4)

    def net_of(halves):
        return reference(PlaneMap({"In2.Cu": halves}, frozenset({"GND"}), LAYERS, (), h), "In1.Cu", line).net

    assert net_of({"VDD": box(0, -1, 7, 1), "GND": box(7, -1, 10, 1)}) == "VDD"  # 6 mm of VDD against 2 of GND
    assert net_of({"VDD": box(0, -1, 5, 1), "GND": box(5, -1, 10, 1)}) == "GND"
    assert net_of({"VDD": box(0, -1, 5, 1), "AVDD": box(5, -1, 10, 1)}) == "AVDD"
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_review_planes.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'kicad_rf_studio.core.review'`.
- [ ] **Step 3: `core/review/planes.py`:**
  - **`plane_nets`** is `classes.gnd | classes.power`, plus every net of `board.nets` whose `_base` fullmatches DOTTED_POWER.
  - **`plane_map`:**
    - `planes`: per (layer, net), the `shapely.union_all` of the `CopperArea` polygons with source "zone" of a plane net;
    - `gnd`: `classes.gnd`;
    - `layers`: `board.copper_layers`;
    - `skipped`: the layers, top to bottom, named by a board warning that is W_ZONE_NOT_FILLED, or W_COPPER_DROPPED with kind T_HATCHED_ZONE;
    - `h[(a, b)]`, for both orders: the sum of the thicknesses of `zs`' dielectric slabs between copper layers a and b, rounded to 1e-6.
  - **`cover(pm, net)`** is the union of `net`'s planes over every layer.
  - **`centre_line`** is `[t.start, t.end]`, or `arc_points(t.start, t.mid, t.end)` for an arc.
  - **`reference`:**
    1. Each side's candidate is the nearest other layer on that side, by `h`, whose planes intersect `line`.
    2. The reference layer is the nearer candidate; on a tie, the one below.
    3. Its net is the one whose planes there cover the most of `line`'s length, compared rounded to 1e-6. On a tie, a net in `gnd` wins, then the first in sort order.
    4. b is the sum of both sides' h when both sides have a candidate; else None.
    5. With no candidate, the result is None.
- [ ] **Step 4: Run them.** Step 2's command. Expected: PASS.
- [ ] **Step 5: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review tests/test_review_planes.py
git commit -m "feat(review): the plane map, ground and power fills by layer with dotted supply names, and a track's reference: the nearest plane under its centre line, its majority net and h (Stage 5 design 5.1, 5.2)"
graphify update .
```

---

### Task 3 [code]: Tags

**Files:** Create `core/review/tags.py` and `tests/test_review_tags.py`.

**Interfaces:**
- Consumes `tracer._walk`, `_links`, `partner_net` and `_base`.
- Produces, in `core/review/tags.py`:
  - `FAMILIES`, in order: r1's expressions cut to A8's seven, each fullmatched case-insensitively on `_base(net)`:
    - `CLK`: `.*(CLK|LRCK|OSC).*`;
    - `SCK`: `.*SCK.*`;
    - `XTAL`: `.*(XTAL|XIN|XOUT).*`;
    - `SW`: `(SW|LX|PH)\d*|.*_(SW|LX)\d*`;
    - `SPI`: `.*(SPI|SDIO|MOSI|MISO).*|.*(SDO|SDI)\d*`;
    - `I2S`: `.*I2S.*`;
    - `USB`: `.*USB.*`.
  - `DENY = frozenset({"CTRL", "NSS", "DIO", "BUSY", "RST", "IRQ", "EN", "CS"})`;
  - `family(net) -> str | None`: the first family that matches. It is None when none matches, or when the name's last "_" word, upper-cased with trailing digits stripped, is in DENY.
  - `tag(board, classes, never, flags=(), chain_nets=()) -> tuple[dict[str, str], list[str]]`: the tags (net → source, sorted by net), and the flags that match no net the review can tag.

- [ ] **Step 1: Write the failing tests,** `tests/test_review_tags.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.review.planes import plane_nets
from kicad_rf_studio.core.review.tags import family, tag
from test_review_planes import dotted

FIX = Path(__file__).parent / "fixtures"


def test_the_name_patterns_tag_a8s_families_past_the_deny_list():  # design 5.1, 6
    names = ["SWDIO", "SPI_CS", "CLK_GEN", "LORA_DIO1", "MCU_D+", "MCU_D-", "USB_D+", "QSPI_CLK", "SPI1_SCK",
             "XTAL_IN", "BUCK_SW", "I2S_BCLK", "SPI_MOSI", "/MCU/SCK", "CLK_EN", "SW1", "spi_cs2"]
    assert {n: family(n) for n in names} == {
        "SWDIO": None, "SPI_CS": None, "CLK_GEN": "CLK", "LORA_DIO1": None, "MCU_D+": None, "MCU_D-": None,
        "USB_D+": "USB", "QSPI_CLK": "CLK", "SPI1_SCK": "SCK", "XTAL_IN": "XTAL", "BUCK_SW": "SW",
        "I2S_BCLK": "CLK", "SPI_MOSI": "SPI", "/MCU/SCK": "SCK", "CLK_EN": None, "SW1": "SW", "spi_cs2": None}


def usb(edit=lambda b: None):
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    edit(b)
    c = classify(b)
    return b, c, plane_nets(b, c)


def test_patterns_tag_a_board_with_no_flag_and_the_walk_reaches_behind_its_resistors():  # design 5.1; BC2
    assert tag(*usb()) == ({"MCU_D+": "walk", "MCU_D-": "walk", "USB_D+": "pattern:USB", "USB_D-": "pattern:USB"}, [])
    b = load_board(FIX / "qspi_clk.kicad_pcb")
    c = classify(b)
    assert tag(b, c, plane_nets(b, c))[0] == {"FLASH_CLK": "pattern:CLK", "QSPI_CLK": "pattern:CLK"}


def test_flags_replace_the_patterns_a_project_adds_and_ground_and_power_are_never_tagged():  # design 5.1; BC2
    b, c, never = usb()
    assert tag(b, c, never, ["AUX"]) == ({"AUX": "flag"}, [])
    assert tag(b, c, never, ["USB_D*", "NOPE"]) == (
        {"MCU_D+": "walk", "MCU_D-": "walk", "USB_D+": "flag", "USB_D-": "flag"}, ["NOPE"])
    assert set(tag(b, c, never, ["*"])[0]) == {"AUX", "MCU_D+", "MCU_D-", "USB_D+", "USB_D-"}  # no GND, +3V3, VBUS
    assert tag(b, c, never, ["GND"]) == ({}, ["GND"])  # a flag of ground or power names nothing the review tags
    assert "+3.3V" not in tag(*usb(dotted), ["*"])[0]  # a dotted supply is a plane net, so never tagged
    assert tag(b, c, never, chain_nets=["AUX", "USB_D+"])[0] == {
        "AUX": "project", "MCU_D+": "walk", "MCU_D-": "walk", "USB_D+": "project", "USB_D-": "pattern:USB"}
    assert tag(b, c, never, ["AUX"], ["USB_D+"])[0] == {
        "AUX": "flag", "MCU_D+": "walk", "MCU_D-": "walk", "USB_D+": "project", "USB_D-": "walk"}
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_review_tags.py -q`. Expected: FAIL with `ModuleNotFoundError` for `kicad_rf_studio.core.review.tags`.
- [ ] **Step 3: `core/review/tags.py`.** `tag` works in this order, and a net takes the first source that tags it:
  1. **Flags:** the board's nets that `fnmatch.fnmatchcase` matches, by full name or by `_base`, against any flag. A flag passes the deny list.
  2. **Project:** the chain nets that are nets of the board.
  3. **Patterns** (only with no flag): `pattern:<family>`.
  4. **Walk:** breadth first from every net tagged so far, through `_walk(_links(board, classes), net)` and `partner_net(net, board.nets)`.

  Further rules:
  - A net in `never`, or the empty net, is never tagged, and the walk never passes through one.
  - A flag is unmatched when it matches no net outside `never` and the empty net.
- [ ] **Step 4: Run them.** Step 2's command. Expected: PASS.
- [ ] **Step 5: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review/tags.py tests/test_review_tags.py
git commit -m "feat(review): tags from the nets named, the project's chain, A8's name patterns past the deny list, and a walk through series parts and pair partners, each with its first source (Stage 5 design 5.1, BC2)"
graphify update .
```

---

### Task 4 [code]: R1 and the exclusions

**Files:**
- Create `core/review/rules.py` and `tests/test_review_rules.py`.
- Modify `core/messages.py`, `po/pt_BR.po` and the `.mo`: Task 4's row of "Messages".

**Interfaces:**
- Consumes Task 2's and Task 3's APIs, `tracer.antenna_kind`, and `classes.connectors`.
- Produces, in `core/review/rules.py`:
  - `RUN_MIN = 1.0` (mm, f4);
  - `ANTIPAD = 0.6` (mm, r1);
  - `EXCLUDE_H = 3.0` (r1, A4);
  - `EDGE_K = 2.0` (A6);
  - `SOURCES: dict[str, str]`, each rule's English source, which `review.json` holds as `limit_source`:
    - R1: "LearnEMC: splitting or gapping a ground plane is almost always a bad idea; Ansys SIwave's Net Crossing Split; HyperLynx DRC's signal traces crossing plane splits; a run of 1 mm or more, measured on three public boards";
    - R2: "TI SLLA656: stitching vias within 200 mils, closer is better; Siemens: manage reference plane changes";
    - R3: "LearnEMC: route critical nets at least 2X from the board edge";
    - R4: "lambda/20 at f_max: Bahl; Harper; Archambeault".
  - `Finding`, a dataclass with these fields:
    - `rule`, `code`;
    - `params`: the message's; review_board adds n, x_mm and y_mm;
    - `net`, `layer`;
    - `ref: Ref | None`;
    - `at: XY` and `bounds`: in the importer's frame;
    - `measured: dict`;
    - `limit: float`;
    - `kiids`: the keys tracks, vias, zones, pads and footprints, each a sorted list of distinct KIIDs (`sorted(set(...))`; a zone's KIID covers all its fills);
    - `id: str = ""`, `n: int = 0`, `tag_source: str | None = None`.
  - `Group(net, layer, ref, tracks, lines)`, frozen: a net's tagged tracks on one layer with one reference. `lines[i]` is `tracks[i]`'s centre line less the exclusions grown by `EXCLUDE_H·ref.h`, possibly empty.
  - `exclusions(board, classes) -> list[BaseGeometry]`, in reference order: the convex hulls of the copper pads of each connector and of each footprint with `keepout`, and of each printed antenna (`antenna_kind == "printed"`) with its copper graphics. A footprint gives one hull.
  - `groups(board, pm, tags, hulls) -> tuple[list[Group], list[str]]`: the groups, and the sorted nets with a track that has no reference;
  - `r1(board, pm, groups, l_mm) -> list[Finding]`.

- [ ] **Step 1: Write the failing tests,** `tests/test_review_rules.py` (Tasks 5 to 7 add to it):

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path

import pytest
import shapely
from shapely.geometry import Point, box

from kicad_rf_studio.core.geometry.region import coarse_cell
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.kicad.board import CopperArea, Footprint, Pad, Via
from kicad_rf_studio.core.kicad.tracer import antenna_kind
from kicad_rf_studio.core.review.planes import Ref, plane_map, plane_nets
from kicad_rf_studio.core.review.rules import exclusions, groups, r1
from kicad_rf_studio.core.review.tags import tag

FIX = Path(__file__).parent / "fixtures"
L5 = coarse_cell(5e9, 4.5)  # 1.4132 mm: λ/20 at the default f_max and εr 4.5


def setup(name, edit=lambda b: None, flags=(), connectors=None):
    b = load_board(FIX / f"{name}.kicad_pcb")
    edit(b)
    c = classify(b, None if connectors is None else {"connectors": connectors})
    pm = plane_map(b, c, zstack(b.stackup, b.copper_layers))
    tags, _ = tag(b, c, plane_nets(b, c), flags)
    return b, c, pm, tags, groups(b, pm, tags, exclusions(b, c))[0]


def test_r1_fires_on_each_usb_line_over_in1s_slot_at_exactly_1_mm():  # design 5.14 R1 positive; risk 6
    b, c, pm, tags, gs = setup("usb2_hs_gap")
    found = r1(b, pm, gs, L5)
    assert sorted((f.net, f.layer, f.ref, f.measured["run_mm"], f.measured["extent_mm"]) for f in found) == [
        ("USB_D+", "F.Cu", Ref("In1.Cu", "GND", 0.2, None), 1.0, 6.0),
        ("USB_D-", "F.Cu", Ref("In1.Cu", "GND", 0.2, None), 1.0, 6.0)]
    assert {(f.code, f.limit, f.measured["l_mm"]) for f in found} == {("W_EMC_GAP_CROSSING", 1.0, 1.413)}
    assert all(len(set(ids)) == len(ids) for f in found for ids in f.kiids.values())  # one KIID per zone
    b, c, pm, tags, gs = setup("usb2_hs")
    assert r1(b, pm, gs, L5) == []  # design 5.14 R1 negative


def test_r1_fires_on_a_void_and_looks_through_a_cut_out_to_ground_below():  # design 5.2 R1, 5.14
    b, c, pm, tags, gs = setup("emc_review")
    (f,) = r1(b, pm, gs, L5)  # CLK_LOOK has GND under its cut-out; CLK_MID's antipads are 0.45 mm runs
    assert (f.net, f.ref, f.measured["run_mm"], f.measured["extent_mm"]) == (
        "CLK_GAP", Ref("In1.Cu", "GND", 0.2, None), 6.0, 10.0)


def test_r1_counts_another_nets_island_on_the_reference_layer_as_a_void():  # design 5.2 R1: a split
    island = box(111.0, -103.0, 114.0, -97.0)

    def split(b):
        b.areas = [replace(a, polygon=a.polygon.difference(island)) if a.layer == "In1.Cu" else a for a in b.areas]
        b.areas.append(CopperArea("In1.Cu", "+3V3", island, "zone", "s"))

    b, c, pm, tags, gs = setup("usb2_hs", split)
    assert sorted((f.net, f.ref.net, f.measured["run_mm"], f.measured["extent_mm"]) for f in r1(b, pm, gs, L5)) == [
        ("USB_D+", "GND", 3.0, 6.0), ("USB_D-", "GND", 3.0, 6.0)]


def test_a_lone_holes_void_is_its_antipad_and_any_other_void_counts():  # design 5.2 R1; D-2
    hole = Point(112.0, -100.475).buffer(0.8)  # 0.2 mm off USB_D+, 0.75 mm off USB_D- (a 0.56 mm chord)

    def holed(b):
        b.areas = [replace(a, polygon=a.polygon.difference(hole)) if a.layer == "In1.Cu" else a for a in b.areas]

    b, c, pm, tags, gs = setup("usb2_hs", holed)
    (f,) = r1(b, pm, gs, L5)
    assert f.net == "USB_D+" and 1.5 < f.measured["run_mm"] < 1.6
    b.vias.append(Via((112.0, -100.475), 0.6, 0.3, ("F.Cu", "B.Cu"), "AUX", "v"))  # diameter/2 + 0.6 = 0.9 >= 0.8
    assert r1(b, pm, gs, L5) == []  # its drill/2 + 0.6 = 0.75 would not reach the hole's edge
    b.vias.pop()
    at = (112.0, -100.475)
    pad = Pad("X1", "1", "p", "AUX", "thru_hole", b.copper_layers, ("F", "B"), at, Point(at).buffer(0.3), None, at, 0.3)
    b.footprints["X1"] = Footprint("X1", "", None, "", "f", "F.Cu", at, 0.0, False, (pad,), None)
    assert r1(b, pm, gs, L5) == []  # D-2: its copper's 0.3 + 0.6 = 0.9 >= 0.8; its drill/2 + 0.6 = 0.75 would not


def test_exclusions_hold_connectors_keepout_footprints_and_printed_antennas():  # design 5.1; A4
    b = load_board(FIX / "lpf915.kicad_pcb")
    hulls = exclusions(b, classify(b))  # J1, a U.FL with a keep-out, and J2, the edge SMA
    assert len(hulls) == 2 and all(any(h.covers(Point(p.center)) for h in hulls)
                                   for ref in ("J1", "J2") for p in b.footprints[ref].pads if p.layers)
    b.footprints["C4"] = replace(b.footprints["C4"], keepout=True)
    assert len(exclusions(b, classify(b))) == 3
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    graphics = shapely.union_all([a.polygon for a in b.areas if a.ref == "AE1"])
    assert antenna_kind(b, "AE1") == "printed" and [h.covers(graphics) for h in exclusions(b, classify(b))] == [True]
    b, c, pm, tags, gs = setup("usb2_hs_gap")
    kept = groups(b, pm, tags, [Point(116.5, -100.0).buffer(0.1)])[0]  # grown by 3h = 0.6 mm, it spans the slot
    assert r1(b, pm, kept, L5) == []
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_review_rules.py -q`. Expected: FAIL with `ModuleNotFoundError` for `kicad_rf_studio.core.review.rules`.
- [ ] **Step 3: `core/review/rules.py`,** and the message (Task 4's row, by the procedure in Global Constraints).

  **Rounding,** for every rule:
  - every mm value is rounded to 1e-3 before it is compared or stored, `limit` included;
  - a share is rounded to 0.1 %, and a fraction of λ to 0.01;
  - k is kept as given.

  **Message params** are text:
  - mm as `f"{v:.3f}"`;
  - k as `f"{k:g}"`;
  - the share as `f"{v:.1f}"`;
  - a fraction of λ as `f"{v:.2f}"`.

  - **`exclusions`,** as in Interfaces.
  - **`groups`:**
    1. Skip each tagged track of zero length.
    2. Take each track's reference from its whole centre line.
    3. Leave out a track with no reference, and name its net.
    4. Leave out a track whose reference has a layer of `pm.skipped` at most `ref.h` away. With no reference, any skipped layer leaves the track out.
    5. Group the rest by (net, layer, ref). A group's `lines` are each track's centre line less `union(hulls).buffer(EXCLUDE_H·ref.h)`.
  - **`r1`,** for each group:
    1. `bare` = the merged `lines` (`line_merge(union_all)`) less `cover(pm, ref.net)`.
    2. For each part of `bare` of length ≥ RUN_MIN, its void is the connected part of `board.outline − cover` that holds the part's midpoint. With no outline, the cover's bounding box stands in for it.
    3. The run is the hole's antipad, and is dropped, when both hold (D-2):
       - the void holds exactly one via centre or `thru_hole` pad hole (`Pad.at`);
       - every vertex of the void lies within that hole's radius + ANTIPAD (+1 µm) of it. The radius is a via's diameter/2, or a pad's `max(drill/2, shapely.hausdorff_distance(Point(pad.at), pad.polygon))`.
    4. The extent is the void's spread along the unit normal of the run's chord (end − start).

    A finding has:
    - `at`: the run's midpoint; `bounds`: the run's;
    - `measured`: `{"run_mm", "extent_mm", "l_mm"}`; `limit`: RUN_MIN;
    - `kiids`: the tracks whose line meets the run, and the distinct zones of `ref.net` on `ref.layer` within `l_mm` of it;
    - `params`: `{net, layer, run_mm, ref_net, ref_layer, h_mm, extent_mm, l_mm}`.
- [ ] **Step 4: Run them.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_sexpr.py tests/test_gui_control.py -q`. Expected: PASS.
- [ ] **Step 5: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review/rules.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_review_rules.py
git commit -m "feat(review): R1, a tagged run of 1 mm or more over a void of its reference net on every layer, lone antipads and the connectors', keep-outs' and printed antennas' hulls grown by 3h left out (Stage 5 design 5.1, 5.2)"
graphify update .
```

---

### Task 5 [code]: R3

**Files:**
- Modify `core/review/rules.py` and `tests/test_review_rules.py`.
- Modify `core/messages.py`, `po/pt_BR.po` and the `.mo`: Task 5's row.

**Interfaces:**
- Produces, in `core/review/rules.py`:
  - `return_share(d, h, b) -> float`: ½ − atan(d/h)/π for microstrip (b None), else (2/π)·atan(e^(−π·d/b));
  - `r3(board, groups, edge_k) -> list[Finding]`.

- [ ] **Step 1: Write the failing tests,** appended to `tests/test_review_rules.py` (imports gain `r3, return_share`):

```python
def test_r3_fires_on_a_track_within_2h_of_the_outline_with_its_share_past_the_edge():  # design 5.2 R3, 5.14
    b, c, pm, tags, gs = setup("emc_review")
    (f,) = r3(b, gs, 2.0)
    assert (f.net, f.layer, f.ref, f.code, f.limit) == ("CLK_EDGE", "F.Cu", Ref("In1.Cu", "GND", 0.2, None),
                                                        "W_EMC_EDGE", 0.4)
    assert f.measured == {"d_mm": 0.35, "h_mm": 0.2, "k": 2.0, "share_pct": 16.5}
    b, c, pm, tags, gs = setup("usb2_hs")
    assert r3(b, gs, 2.0) == []  # the pair about 5 mm in


def test_r3_leaves_out_a_connectors_launch():  # design 5.14 R3 negative; 5.1's exclusions; D-3
    b, c, pm, tags, gs = setup("lpf915", flags=["RF_*"])
    assert r3(b, gs, 2.0) == r3(b, gs, 5.0) == []  # RF_SMA ends 2.24 mm in; J2's hull grown by 3h leaves it 5.7
    b, c, pm, tags, gs = setup("lpf915", flags=["RF_*"], connectors=[])
    assert [(f.net, f.measured["d_mm"]) for f in r3(b, gs, 5.0)] == [("RF_SMA", 2.24)]


def test_the_share_of_return_current_past_the_edge():  # design 5.2 R3: Johnson and Graham; r5
    assert round(100 * return_share(0.4, 0.2, None), 1) == 14.8  # microstrip at 2h
    assert round(100 * return_share(0.4, 0.2, 0.4), 1) == 2.7  # stripline at 2h, b = 2h
    assert return_share(0.0, 0.2, None) == pytest.approx(0.5)
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_review_rules.py -q`. Expected: FAIL with `ImportError` on `r3`.
- [ ] **Step 3: `r3`,** and the message (Task 5's row). Rounding is as in Task 4. With no `board.outline`, r3 finds nothing. For each group:
  1. Each track's d is the distance from its entry in the group's `lines` to the outline's boundary, less half its width. A track whose entry is empty is not measured, so the exclusions apply.
  2. Tracks with 0 < d < k·h are flagged. Their entries merge into contiguous parts, and each part is a finding, with d the least of its tracks'.
  3. `at` is the midpoint of the part's stretch within k·h + w/2 of the boundary; `bounds` are the part's tracks' copper (`Track.polygon`).
  4. `measured`: `{"d_mm", "h_mm", "k", "share_pct": 100·return_share(d, h, ref.b)}`; `limit`: k·h.
  5. `kiids`: the part's tracks; `params`: `{net, layer, d_mm, k, kh_mm, h_mm, ref_layer, share_pct}`.
- [ ] **Step 4: Run them.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_sexpr.py tests/test_gui_control.py -q`. Expected: PASS.
- [ ] **Step 5: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review/rules.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_review_rules.py
git commit -m "feat(review): R3, a tagged track within k·h of the outline outside the exclusions, with its share of return current past the edge (Stage 5 design 5.2)"
graphify update .
```

---

### Task 6 [code]: R2

**Files:**
- Modify `core/review/rules.py` and `tests/test_review_rules.py`.
- Modify `core/messages.py`, `po/pt_BR.po` and the `.mo`: Task 6's rows.

**Interfaces:**
- Produces, in `core/review/rules.py`:
  - `R2_FLOOR = 2.0`: mm, with d = max(L, 2 mm) (A5, f4);
  - `r2(board, classes, pm, tags, l_mm) -> list[Finding]`, in `board.vias` order.

- [ ] **Step 1: Write the failing tests,** appended to `tests/test_review_rules.py` (imports gain `r2`):

```python
def test_r2_fires_on_flash_clks_vias_from_in1s_ground_to_in2s_supply():  # design 5.14 R2 positive
    b, c, pm, tags, gs = setup("qspi_clk")
    found = r2(b, c, pm, tags, L5)
    assert [(f.net, f.layer, f.ref, f.params["to_layer"], f.params["to_net"], f.measured["return_mm"])
            for f in found] == [
        ("FLASH_CLK", "F.Cu", Ref("In1.Cu", "GND", 0.2, None), "In2.Cu", "+3V3", 2.262),
        ("FLASH_CLK", "F.Cu", Ref("In1.Cu", "GND", 0.2, None), "In2.Cu", "+3V3", 9.773)]
    assert {(f.code, f.limit, f.params["path"]) for f in found} == {("I_EMC_REF_CHANGE", 2.0, "T_EMC_RETURN_CAP")}
    assert found[0].params["nearest"] == "2.262 mm"


def test_r2_is_silent_on_a_bridged_change_and_on_a_same_net_change_with_a_via_near():  # design 5.14 R2 negatives
    b, c, pm, tags, gs = setup("emc_review")
    assert r2(b, c, pm, tags, L5) == []  # C1's pads 0.890 mm from CLK_MID's via

    def ground_in2(b):
        b.areas = [replace(a, net="GND") if a.layer == "In2.Cu" else a for a in b.areas]

    b, c, pm, tags, gs = setup("qspi_clk", ground_in2)
    assert [(f.params["path"], f.measured["return_mm"]) for f in r2(b, c, pm, tags, L5)] == [
        ("T_EMC_RETURN_VIA", 3.444), ("T_EMC_RETURN_VIA", 7.879)]
    b.vias.append(Via((107.0, -98.99), 0.6, 0.3, ("F.Cu", "B.Cu"), "GND", "v"))  # 0.8 mm from the first
    assert [f.measured["return_mm"] for f in r2(b, c, pm, tags, L5)] == [7.879]
```

- [ ] **Step 2: Run them.** Step 2 of Task 5's command. Expected: FAIL with `ImportError` on `r2`.
- [ ] **Step 3: `r2`,** and the messages (Task 6's rows). Rounding is as in Task 4. At each via of a tagged net:
  1. Its tracks are the net's tracks with an end within the via's radius (+1 µm), each with its reference. A track with no reference is dropped.
  2. Order them by layer, top to bottom. `from` is the first one's reference, and `to` the last one's.
  3. **Different nets:**
     - the returns are the footprints whose letters (`_prefix`) are "C" and whose two copper pads with a net sit on exactly {from.net, to.net};
     - each is as far as its nearer pad centre from the via centre;
     - the path is T_EMC_RETURN_CAP.
  4. **The same net on two layers:**
     - the returns are the vias of that net whose span holds both reference layers (the span is the copper layers between the via's two `layers`);
     - the path is T_EMC_RETURN_VIA.
  5. **The same layer and net:** nothing.
  6. It fires when no return lies within d = max(l_mm, R2_FLOOR).

  A finding has:
  - `layer`: the first track's; `ref`: `from`; `at`: the via's centre; `bounds`: its disc;
  - `measured`: `{"return_mm"}`, None with no return; `limit`: d;
  - `kiids`: the via and its tracks, plus the nearest capacitor's footprint or the nearest via;
  - `params`: `{net, from_net, from_layer, to_net, to_layer, path, nearest, limit_mm}`, with `nearest` as "T_NONE" or `f"{d:.3f} mm"`.
- [ ] **Step 4: Run them.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_sexpr.py tests/test_gui_control.py -q`. Expected: PASS.
- [ ] **Step 5: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review/rules.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_review_rules.py
git commit -m "feat(review): R2, a tagged via changing reference with no capacitor or stitching via within max(L, 2 mm), for information (Stage 5 design 5.2)"
graphify update .
```

---

### Task 7 [code]: R4

**Files:**
- Modify `core/review/rules.py` and `tests/test_review_rules.py`.
- Modify `core/messages.py`, `po/pt_BR.po` and the `.mo`: Task 7's rows.

**Interfaces:**
- Produces, in `core/review/rules.py`:
  - `FENCE_REACH = 1.0` (mm, A7 and f4);
  - `r4(board, classes, l_mm, edge_fence) -> list[Finding]`: the shields in sorted order, then the edge.

- [ ] **Step 1: Write the failing tests,** appended to `tests/test_review_rules.py` (imports gain `r4`):

```python
def frame(b, ref="SH1"):  # the shield's ring and its pad-covered stretches, longest first, as Step 3 takes them
    pads = shapely.union_all([p.polygon for p in b.footprints[ref].pads if b.footprints[ref].layer in p.layers])
    ring = pads.convex_hull.exterior
    return sorted(shapely.get_parts(shapely.line_merge(ring.intersection(pads.buffer(1e-6)))), key=lambda g: -g.length)


def gnd_vias(points, tag="s"):
    return [Via((p.x, p.y), 0.6, 0.3, ("F.Cu", "B.Cu"), "GND", f"{tag}{k}") for k, p in enumerate(points)]


def test_r4_fires_on_lpf915s_unstitched_frame_and_on_the_edge_only_when_asked():  # design 5.14 R4 positive; A7
    b, c, *_ = setup("lpf915")
    (f,) = r4(b, c, L5, False)
    assert (f.rule, f.code, f.net, f.layer, f.params["fence"], f.limit) == ("R4", "W_EMC_FENCE_PITCH", None, "F.Cu",
                                                                            "SH1", 1.413)
    assert f.measured == {"gap_mm": 47.2, "lambdas": 1.67}  # no GND via within 1 mm: the frame pads' whole cover
    assert f.kiids["footprints"] == [b.footprints["SH1"].uuid] and f.params["lambdas"] == "1.67"
    edge = [f for f in r4(b, c, L5, True) if f.params["fence"] == "T_EMC_BOARD_EDGE"]
    assert [(f.layer, f.measured["gap_mm"]) for f in edge] == [(None, 104.43)]  # the outline's whole length


def test_r4_is_silent_on_a_frame_stitched_every_0976_mm_around_its_corners():  # design 5.14 R4 negative; D-1
    b, c, *_ = setup("emc_review")
    assert r4(b, c, L5, False) == []


def test_r4_leaves_the_frames_openings_out_and_fires_on_a_missing_via():  # design 5.2 R4; A7; D-1
    b, c, *_ = setup("lpf915")
    parts = frame(b)
    vias = gnd_vias([p.interpolate(float(k)) for p in parts for k in range(int(p.length) + 1)])  # 1 mm, no opening
    b.vias += vias
    assert r4(b, c, L5, False) == []
    mid = int(parts[0].length) // 2  # the longest stretch's middle via
    b.vias.remove(vias[mid])
    (f,) = r4(b, c, L5, False)
    assert f.measured["gap_mm"] == 2.0 and sorted(f.kiids["vias"]) == sorted([vias[mid - 1].uuid, vias[mid + 1].uuid])


def test_r4_two_vias_side_by_side_leave_the_rest_of_the_frame_open():  # design 5.2 R4; D-1
    b, c, *_ = setup("lpf915")
    longest = frame(b)[0]
    b.vias += gnd_vias([longest.interpolate(0.0), longest.interpolate(1.0)])
    (f,) = r4(b, c, L5, False)
    assert f.measured["gap_mm"] > 40
```

- [ ] **Step 2: Run them.** Task 5's Step 2 command. Expected: FAIL with `ImportError` on `r4`.
- [ ] **Step 3: `r4`,** and the messages (Task 7's rows). Rounding is as in Task 4.
  - **A shield's fence:**
    - For each shield, the ring is the exterior of the convex hull of its copper pads on its side's layer (`Footprint.layer`), as `find_lid` takes it.
    - The covered stretch is the ring ∩ the pads' union buffered by 1e-6.
    - The fence is the vias of a `classes.gnd` net within FENCE_REACH of the ring, ordered by `ring.project`.
  - **The board-edge fence** (with `edge_fence` and an outline): the ring is `outline.exterior`, and it covers itself.
  - **The gaps** (D-1; design §5.2: "measured along the line, over the stretches the frame pads cover, so the frame's own cut-out is excluded"):
    - Between consecutive fence vias A and B, cyclic, the gap is `min(covered, max(dist, along − dA − dB))`, where:
      - `along` is the ring length from A's projection to B's;
      - `covered` is its frame-covered part;
      - `dist` is |AB|;
      - dA and dB are the vias' distances to the ring.
    - With fewer than two vias, the whole covered length is one gap.
    - Each gap over `l_mm` fires.

  A finding has:
  - `net`: None; `layer`: the shield's side, or None for the edge;
  - `at`: the midpoint of the ring's stretch from A to B (`ring.interpolate`, cyclic), or `ring.interpolate(ring.length / 2)` with fewer than two vias; `bounds`: the stretch's;
  - `measured`: `{"gap_mm", "lambdas": gap/(20·l_mm)}`; `limit`: `l_mm`;
  - `kiids`: the shield's footprint and the gap's two vias;
  - `params`: `{fence, gap_mm, lambdas, l_mm}`, with `fence` the shield's ref or T_EMC_BOARD_EDGE.
- [ ] **Step 4: Run them.** Task 5's Step 2 command, then `.venv/Scripts/python -m pytest tests/test_sexpr.py tests/test_gui_control.py -q`. Expected: PASS. If the missing via's gap reads other than 2.0 because the longest stretch turns a corner at its middle, report the measured value for a ruling.
- [ ] **Step 5: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review/rules.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_review_rules.py
git commit -m "feat(review): R4, a shield fence's gaps between ground vias over L, measured over the frame-covered line with the corners at the pitch, the board edge opt-in (Stage 5 design 5.2)"
graphify update .
```

---

### Task 8 [code]: The review

**Files:**
- Modify `core/review/__init__.py`.
- Modify `core/messages.py`, `po/pt_BR.po` and the `.mo`: Task 8's rows.
- Create `tests/test_review.py`.

**Interfaces:**
- Consumes Tasks 2 to 7, `chain_of`, `core.project.antenna` and `si`, and `region.coarse_cell`.
- Produces, in `core/review/__init__.py`:
  - `F_MAX_DEFAULT = 5e9`, `F_MAX_CAP = 6e9` and `CARRIER_HARMONICS = 5` (A2, BC1);
  - `REVIEW_LIMITS = ("I_LIMIT_REVIEW_KEEPOUT",)`: the limits printed last and written at the end of `review.json`'s notes (design §5.1);
  - `resolve_f_max(f_max, f0, project) -> tuple[float, str, float | None]`: (f_max, its source, the carrier);
  - `Review(settings: dict, notes: list[tuple[str, dict]], findings: list[Finding], cover: BaseGeometry, carrier: float | None, clocks: tuple[float, ...])`, a dataclass:
    - `cover` is the union of every plane of the plane map, which review.png draws;
    - the carrier and the clocks are kept for plan 2's cavity marks, and plan 1 writes them nowhere;
  - `finding_ids(findings) -> list[str]`;
  - `review_board(board, stackup, zs, classes, *, nets=(), project=None, f0=None, clocks=(), f_max=None, edge_k=None, edge_fence=False) -> Review`.

- [ ] **Step 1: Write the failing tests,** `tests/test_review.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.review import finding_ids, resolve_f_max, review_board

FIX = Path(__file__).parent / "fixtures"
CLKS = ("CLK_EDGE", "CLK_GAP", "CLK_LOOK", "CLK_MID")


def run(name="emc_review", edit=lambda b: None, **kw):
    b = load_board(FIX / f"{name}.kicad_pcb")
    edit(b)
    return review_board(b, b.stackup, zstack(b.stackup, b.copper_layers), classify(b), **kw)


def digest(rule, kiids, at):
    return hashlib.sha256(json.dumps([rule, kiids, at], separators=(",", ":")).encode()).hexdigest()[:8]


@pytest.mark.parametrize(("f_max", "f0", "project", "expected"), [
    (7e9, 915e6, None, (7e9, "cli", 915e6)),
    (None, 915e6, None, (4.575e9, "carrier", 915e6)),
    (None, 2.44e9, None, (6e9, "carrier", 2.44e9)),
    (None, None, {"schema": 1, "f0_hz": 868e6}, (4.34e9, "carrier", 868e6)),
    (None, None, {"schema": 2, "f0_hz": 870e6, "band": {"f_lo_hz": 840e6, "f_hi_hz": 880e6}},
     (4.3e9, "carrier", 860e6)),  # an antenna's band centre, never its f0_hz
    (None, None, {"schema": 3, "f_max_hz": 10e9}, (6e9, "si", None)),
    (None, None, {"schema": 3, "f_max_hz": 2e9}, (2e9, "si", None)),
    (None, 915e6, {"schema": 3, "f_max_hz": 10e9}, (4.575e9, "carrier", 915e6)),  # --f0 wins over a project's
    (None, None, None, (5e9, "default", None))])
def test_f_max_resolves_in_bc1s_order(f_max, f0, project, expected):  # design 5.1; BC1
    f, source, carrier = resolve_f_max(f_max, f0, project)
    assert f == pytest.approx(expected[0]) and source == expected[1] and carrier == pytest.approx(expected[2])


def test_the_review_of_emc_review_states_its_basis_and_tags_and_numbers_its_two_findings():  # design 5.1 to 5.3
    r = run()
    assert r.settings == {"f_max_hz": 5e9, "f_max_source": "default", "eps_r": 4.5, "l_mm": 1.413, "edge_k": 2.0,
                          "edge_fence": False, "tags": [{"net": n, "source": "pattern:CLK"} for n in CLKS]}
    assert r.notes == [("W_FILLS_AS_SAVED", {}), ("I_REVIEW_RELATIVE", {}),
                       ("I_REVIEW_BASIS", {"f_max_ghz": "5", "source": "T_FMAX_DEFAULT", "eps_r": "4.5",
                                           "l_mm": "1.413", "edge_k": "2"}),
                       ("I_REVIEW_TAGS_PATTERN", {"nets": ", ".join(CLKS)})]
    assert [(f.n, f.rule, f.net, f.tag_source) for f in r.findings] == [(1, "R1", "CLK_GAP", "pattern:CLK"),
                                                                       (2, "R3", "CLK_EDGE", "pattern:CLK")]
    gap, edge = r.findings
    assert (edge.params["n"], edge.params["x_mm"], edge.params["y_mm"]) == ("2", "113.000", "100.600")  # KiCad's frame
    assert float(gap.params["x_mm"]) == pytest.approx(113, abs=1e-3) and gap.params["y_mm"] == "110.000"
    assert r.cover.area > 0 and r.carrier is None and r.clocks == ()


def test_a_findings_id_is_its_rule_and_a_hash_of_its_kiids_and_place_numbered_on_a_clash():  # design 5.3
    f = run().findings[1]
    kiids = sorted(k for ids in f.kiids.values() for k in ids)
    assert f.id == f"R3-{digest('R3', kiids, [113.0, 100.6])}" == run().findings[1].id  # same copper, same id
    assert finding_ids([f, f]) == [f.id, f.id + "-2"]
    assert finding_ids([replace(f, at=(5.0, 0.0))]) == [f"R3-{digest('R3', kiids, [5.0, 0.0])}"]  # never -0.0


def test_the_notes_name_unmatched_flags_skipped_layers_and_nets_with_no_plane():  # design 5.1, 5.3
    assert run(nets=["NOPE"]).notes[3:] == [("I_REVIEW_NO_TAGS", {}), ("W_REVIEW_NET_UNMATCHED", {"pattern": "NOPE"})]

    def unfilled(b):
        b.warnings = [("W_ZONE_NOT_FILLED", {"uuid": "z", "layer": "In1.Cu"})]

    r = run(edit=unfilled)
    assert r.notes[:2] == [("W_ZONE_NOT_FILLED", {"uuid": "z", "layer": "In1.Cu"}), ("W_FILLS_AS_SAVED", {})]
    assert ("W_EMC_LAYER_SKIPPED", {"layer": "In1.Cu"}) in r.notes and r.findings == []  # F.Cu's tracks skipped

    def bare(b):
        b.areas = []

    r = run("usb2_hs", bare)
    assert ("I_REVIEW_TAGS_WALK", {"nets": "MCU_D+, MCU_D-"}) in r.notes
    assert r.notes[-1] == ("I_EMC_NO_REFERENCE", {"nets": "MCU_D+, MCU_D-, USB_D+, USB_D-"})
```

  `pytest.approx(None)` compares as equality (pytest 9.1.1), so the None carriers pass.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_review.py -q`. Expected: FAIL with `ImportError` on `finding_ids`.
- [ ] **Step 3: `core/review/__init__.py`,** and the messages (Task 8's rows).
  - **`resolve_f_max`** follows BC1:
    1. `f_max` given: "cli".
    2. Else the carrier is the first of these:
       - `f0`;
       - an antenna project's band centre, `(f_lo_hz + f_hi_hz)/2`, checked first with `core.project.antenna`;
       - a v1 project's `f0_hz` (neither `antenna` nor `si`).

       With a carrier, f_max is min(F_MAX_CAP, CARRIER_HARMONICS·carrier): "carrier".
    3. Else an SI project's `min(f_max_hz, F_MAX_CAP)`: "si".
    4. Else F_MAX_DEFAULT: "default".

    A project's own simulation f_max (`region.f_max`) is never read (design §5.1); the SI step reads the interface's top-level `f_max_hz`.
  - **`finding_ids`:**
    - Each id is "R<k>-" plus the first 8 hex digits of the SHA-256 of `json.dumps([rule, sorted KIIDs of every kind, [round(x, 2), round(y, 2)]], separators=(",", ":"))`, encoded as UTF-8.
    - (x, y) is the place in KiCad's frame, `(x + 0.0, 0.0 - y + 0.0)`, so no `-0.0` appears.
    - A repeated id takes "-2", "-3" and so on, in list order.
  - **`review_board`:**
    1. `never = plane_nets`; `pm = plane_map`.
    2. f_max, its source and the carrier come from `resolve_f_max`.
    3. εr is the highest `epsilon_r` of the stackup's dielectric layers.
    4. L is `coarse_cell(f_max, εr)`; k is `edge_k`, or EDGE_K.
    5. `tag(board, classes, never, nets, chain_of(project).nets if project else ())`.
    6. The groups, from `exclusions`.
    7. The findings: R1 + R2 + R3 + R4, sorted by (rule, KiCad x, KiCad y).
    8. Each finding takes `n` (from 1), its id, its `tag_source` (`tags.get(net)`), and the params n, x_mm and y_mm (`f"{v:.3f}"`, KiCad's frame).
    9. `cover` is the union of every geometry in `pm.planes`.

    Settings:
    - `f_max_hz`, `f_max_source`, `eps_r`;
    - `l_mm`: L rounded to 1e-3; `edge_k`: k as a float; `edge_fence`;
    - `tags`: `[{"net", "source"}]`, by net.

    Notes (AR-12):
    1. `board.warnings`;
    2. W_FILLS_AS_SAVED, as `new` prints it;
    3. I_REVIEW_RELATIVE;
    4. I_REVIEW_BASIS:
       - `f_max_ghz` as `f"{f/1e9:g}"`;
       - the source as T_FMAX_<SOURCE>;
       - `eps_r` as `f"{εr:g}"`;
       - `l_mm` as `f"{L:.3f}"`;
       - `edge_k` as `f"{k:g}"`;
    5. one I_REVIEW_TAGS_<SOURCE> line per source present, in BC2's order (FLAG, PROJECT, PATTERN, WALK), its nets joined by ", ". Every family goes under one pattern line. With no tag, I_REVIEW_NO_TAGS instead;
    6. W_REVIEW_NET_UNMATCHED, per unmatched flag;
    7. W_EMC_LAYER_SKIPPED, per skipped layer;
    8. I_EMC_NO_REFERENCE, when `groups` named nets.
- [ ] **Step 4: Run them.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_review_rules.py tests/test_sexpr.py tests/test_gui_control.py -q`. Expected: PASS.
- [ ] **Step 5: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review/__init__.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_review.py
git commit -m "feat(review): review_board: f_max in BC1's order, the stackup's highest permittivity and L, the tags, the four rules, ids stable across reruns, numbering, the planes' cover and the review's notes (Stage 5 design 5.1 to 5.3)"
graphify update .
```

---

### Task 9 [code]: The three files

**Files:** Create `core/review/outputs.py` and `tests/test_review_outputs.py`.

**Interfaces:**
- Produces, in `core/review/outputs.py`:
  - `REVIEW_OUTPUTS = re.compile(r"review\.(json|csv|png)")`;
  - `CSV_COLUMNS = ("id", "rule", "code", "net", "layer", "ref_layer", "ref_net", "x_mm", "y_mm", "measured", "limit", "kiids", "message")`;
  - `review_json(r, path: str, sha256: str) -> bytes`;
  - `review_csv(r) -> bytes`;
  - `draw_review(fig, r, board) -> None`;
  - `review_png(r, board) -> bytes`.

- [ ] **Step 1: Write the failing tests,** `tests/test_review_outputs.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import json
import subprocess
import sys
from dataclasses import replace

from matplotlib.figure import Figure

from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.messages import english
from kicad_rf_studio.core.review.outputs import CSV_COLUMNS, draw_review, review_csv, review_json, review_png
from kicad_rf_studio.core.review.rules import SOURCES
from test_review import FIX, run

SHA, PNG = "ab" * 32, b"\x89PNG\r\n\x1a\n"


def test_review_json_holds_schema_1s_keys_in_kicads_frame():  # design 5.3; ruling 1
    r = run()
    text = review_json(r, "b.kicad_pcb", SHA)
    data = json.loads(text)
    assert text.endswith(b"}\n") and list(data) == ["schema", "board", "settings", "notes", "findings", "cavities"]
    assert (data["schema"], data["board"], data["cavities"]) == (1, {"path": "b.kicad_pcb", "sha256": SHA}, [])
    assert data["settings"] == r.settings and data["notes"][1] == {"code": "I_REVIEW_RELATIVE", "params": {}}
    assert data["notes"][-1] == {"code": "I_LIMIT_REVIEW_KEEPOUT", "params": {}}  # design 5.1: the output says so
    f = data["findings"][1]
    assert list(f) == ["id", "rule", "code", "params", "net", "layer", "ref_layer", "ref_net", "h_mm", "at_mm",
                       "bbox_mm", "measured", "limit", "limit_source", "tag_source", "kiids"]
    assert (f["rule"], f["at_mm"], f["bbox_mm"], f["ref_layer"], f["ref_net"], f["h_mm"], f["limit"]) == (
        "R3", [113.0, 100.6], [102.75, 100.35, 123.25, 100.85], "In1.Cu", "GND", 0.2, 0.4)  # y down
    assert (f["limit_source"], f["tag_source"], f["id"]) == (SOURCES["R3"], "pattern:CLK", r.findings[1].id)
    assert list(f["kiids"]) == ["tracks", "vias", "zones", "pads", "footprints"] and len(f["kiids"]["tracks"]) == 1


def test_review_csv_has_a_row_per_finding_with_its_measures_kiids_and_english_message():  # design 5.3
    r = run()
    rows = list(csv.reader(io.StringIO(review_csv(r).decode("utf-8"))))
    assert rows[0] == list(CSV_COLUMNS) and len(rows) == 3
    row = dict(zip(rows[0], rows[2]))
    edge = r.findings[1]
    assert (row["id"], row["rule"], row["x_mm"], row["y_mm"], row["limit"]) == (edge.id, "R3", "113.000", "100.600",
                                                                                "0.400")
    assert row["measured"] == "d_mm=0.350;h_mm=0.200;k=2.000;share_pct=16.500"
    assert row["kiids"] == f"tracks:{edge.kiids['tracks'][0]}" and row["message"] == english("W_EMC_EDGE", **edge.params)


def test_review_png_numbers_each_finding_and_draws_the_reviews_cover_whatever_the_stackup(mini_board):  # design 5.3
    board = load_board(FIX / "emc_review.kicad_pcb")
    board.stackup = None  # as under --stackup: the review's own cover is drawn, never rebuilt
    r = run()
    fig = Figure()
    draw_review(fig, r, board)
    ax = fig.axes[0]
    assert [t.get_text() for t in ax.texts] == ["1", "2"] and len(ax.patches) >= 1
    assert review_png(r, board)[:8] == PNG
    assert review_png(replace(r, findings=[]), mini_board())[:8] == PNG  # a board with no outline


def test_the_review_imports_neither_openems_nor_matplotlib():  # Stage 1 3.1; ruling 5
    probe = ("import sys, kicad_rf_studio.core.review, kicad_rf_studio.core.review.outputs; "
             "print(sorted(m for m in ('openEMS', 'CSXCAD', 'matplotlib') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_review_outputs.py -q`. Expected: FAIL with `ModuleNotFoundError` for `kicad_rf_studio.core.review.outputs`.
- [ ] **Step 3: `core/review/outputs.py`.** Every coordinate goes out in KiCad's frame: y negated, rounded to 1e-3, with `+ 0.0`.
  - **`review_json`** is `json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"`:
    - `data` has §5.3's keys, in Step 1's order, with `cavities: []`. Its docstring says plan 2 fills the cavities.
    - `notes` are `r.notes`, then each of REVIEW_LIMITS with `{}`.
    - `bbox_mm` is `[x0, y0, x1, y1]` in KiCad's frame.
    - `ref_layer`, `ref_net` and `h_mm` come from `ref` (None without one).
    - `limit` is rounded to 1e-3.
    - `limit_source` is `SOURCES[rule]`. It is an English record for the file's readers; the docstring says a GUI shows the finding's message, which names the source in the user's language, never `limit_source`.
  - **`review_csv`** writes `csv.writer(out, lineterminator="\n")`, in UTF-8:
    - `measured` is `name=value` joined by ";", each value `f"{v:.3f}"`, or empty for None;
    - `limit` is `f"{v:.3f}"`;
    - `kiids` is `kind:KIID` joined by ";", in the key order;
    - `message` is `english(code, **params)`.
  - **`draw_review`** draws on one axes, equal aspect, y inverted, in mm:
    - the outline, when there is one;
    - `r.cover`, each polygon filled light grey with its holes left open (a matplotlib Path with its interiors);
    - the tagged tracks' centre lines (`r.settings["tags"]`' nets);
    - each finding's `n` as text at its place.

    It never rebuilds the plane map, the classes or the z-stack.
  - **`review_png`** is as `outputs.summary_png`:
    - `from matplotlib.figure import Figure` inside the function only (C-5);
    - `Figure(figsize=(8, 8), layout="constrained")`;
    - `draw_review`;
    - `savefig(format="png", dpi=100)`.
- [ ] **Step 4: Run them.** Step 2's command. Expected: PASS.
- [ ] **Step 5: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add src/kicad_rf_studio/core/review/outputs.py tests/test_review_outputs.py
git commit -m "feat(review): review.json schema 1 in KiCad's frame with the keep-out limit and an empty cavities list for plan 2, review.csv a row per finding, and review.png with the review's cover and each finding's number (Stage 5 design 5.3)"
graphify update .
```

---

### Task 10 [code]: The `review` command

**Files:**
- Modify:
  - `cli.py`: the module docstring names `review`; `review`, `_review`, and the parser after `compare`;
  - `core/messages.py`, `po/pt_BR.po` and the `.mo`: Task 10's row.
- Create `tests/test_cli_review.py`.

**Interfaces:**
- Consumes:
  - `_load`;
  - `core.project.read_project` and `board_hash`;
  - `pipeline.project_path` and `command_line`;
  - `core.post.outputs.write`;
  - Tasks 8 and 9.
- Produces in `cli.py`: `review(board: str | Path, *, nets=(), project: str | None = None, f0=None, clocks=(), f_max=None, edge_k=None, edge_fence=False, stackup=None, output=None, emit=None) -> int`.

- [ ] **Step 1: Write the failing tests,** `tests/test_cli_review.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from kicad_rf_studio import cli, pipeline
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import render

FIX = Path(__file__).parent / "fixtures"
EMC, LPF = FIX / "emc_review.kicad_pcb", FIX / "lpf915.kicad_pcb"


def settings(folder):
    return json.loads((folder / "review.json").read_text(encoding="utf-8"))["settings"]


def test_review_writes_its_three_files_and_prints_its_lines_in_seconds(tmp_path, capsys):  # design 5.1, 5.3; ruling 8
    start = time.perf_counter()
    assert main(["review", str(EMC), "-o", str(tmp_path)]) == 0
    assert time.perf_counter() - start < 30  # generous: r1 measured the rules in milliseconds; the PNG included
    assert sorted(p.name for p in tmp_path.iterdir()) == ["review.csv", "review.json", "review.png"]
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == [render("W_FILLS_AS_SAVED"), render("I_REVIEW_RELATIVE")]
    assert out[-3:] == [render("I_REVIEW_FINDINGS", count=2),
                        render("I_OUTPUTS", files="review.csv, review.json, review.png", folder=str(tmp_path)),
                        render("I_LIMIT_REVIEW_KEEPOUT")]
    assert json.loads((tmp_path / "review.json").read_text(encoding="utf-8"))["board"]["path"] == str(EMC)
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules


def test_review_writes_to_the_working_folder_and_a_held_file_is_an_e_line(tmp_path, monkeypatch):  # design 5.1
    monkeypatch.chdir(tmp_path)
    assert main(["review", str(EMC)]) == 0 and (tmp_path / "review.json").is_file()
    real = os.replace

    def replace(src, dst):  # a viewer holds review.png
        if Path(dst).name == "review.png":
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    lines, out = [], tmp_path / "out"
    assert cli.review(EMC, nets=["CLK_*"], edge_fence=True, output=out,  # a Path, as the GUI gives it
                      emit=lambda code, params: lines.append((code, params))) == 2
    (err,) = [params for code, params in lines if code == "E_RESULTS_WRITE"]
    assert err["command"] == pipeline.command_line("kicad-rf-studio", "review", str(EMC), "--net", "CLK_*",
                                                   "--edge-fence", "-o", str(out))
    assert "I_OUTPUTS" not in [code for code, _ in lines] and lines[-1] == ("I_LIMIT_REVIEW_KEEPOUT", {})
    assert not (out / "review.json").exists()  # review.json goes last: a held file refuses before it changes


def test_review_tags_a_projects_chain_takes_its_carrier_and_the_flags_win(tmp_path):  # design 5.1; BC1, BC2
    project, _ = cli.new(LPF, "U1.1", "J1.1", 915e6, output=tmp_path / "p")
    assert main(["review", str(LPF), "--project", str(tmp_path / "p"), "-o", str(tmp_path / "a")]) == 0
    s = settings(tmp_path / "a")
    assert (s["f_max_hz"], s["f_max_source"], s["l_mm"]) == (4.575e9, "carrier", 1.545)
    assert s["tags"] == [{"net": n, "source": "project"} for n in ("RF_A", "RF_B", "RF_C", "RF_OUT")]
    assert main(["review", str(LPF), "--project", str(project), "--f0", "868MHz", "--clock", "32MHz",
                 "-o", str(tmp_path / "b")]) == 0
    assert (settings(tmp_path / "b")["f_max_hz"], settings(tmp_path / "b")["f_max_source"]) == (4.34e9, "carrier")
    assert main(["review", str(LPF), "--f-max", "3GHz", "--edge-k", "3", "-o", str(tmp_path / "c")]) == 0
    assert (settings(tmp_path / "c")["f_max_hz"], settings(tmp_path / "c")["edge_k"]) == (3e9, 3.0)


def test_a_board_with_no_stackup_is_refused_and_a_preset_reviews_it(mini_board_file, tmp_path, capsys):  # design 5.1
    board = mini_board_file()
    assert main(["review", str(board), "-o", str(tmp_path / "o")]) == 2
    assert render("E_NO_STACKUP") in capsys.readouterr().err and not (tmp_path / "o").exists()
    assert main(["review", str(board), "--stackup", "kicad-default", "-o", str(tmp_path / "o")]) == 0


def test_the_parser_holds_the_designs_synopsis_and_no_run_dir():  # design 5.1; ruling 6
    a = cli._parser().parse_args(["review", "b.kicad_pcb"])
    assert (a.net, a.project, a.f0, a.clock, a.f_max, a.edge_k, a.edge_fence, a.stackup, a.output) == (
        [], None, None, [], None, None, False, None, None)
    assert not hasattr(a, "run_dir")


def test_the_cli_with_the_review_imports_neither_openems_nor_matplotlib():  # Stage 1 3.1; ruling 5
    probe = ("import sys, kicad_rf_studio.cli, kicad_rf_studio.core.review, kicad_rf_studio.core.review.outputs; "
             "print(sorted(m for m in ('openEMS', 'CSXCAD', 'matplotlib') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_cli_review.py -q`. Expected: FAIL, because argparse exits 2 on `invalid choice: 'review'`. The last test passes already, as it should: Tasks 2 to 9 left `core.review` importable, and the guard holds before the command.
- [ ] **Step 3: The command,** and the message (Task 10's row).
  - **The parser,** after `compare`. It has no `--run-dir`, so main writes it no end event:
    - `board`;
    - `--net` (append, default [], metavar PATTERN);
    - `--project` (PROJECT);
    - `--f0` (parse_frequency, F);
    - `--clock` (parse_frequency, append, default [], F);
    - `--f-max` (parse_frequency, F);
    - `--edge-k` (`_positive(float)`, default None, K);
    - `--edge-fence` (store_true);
    - `--stackup` (NAME);
    - `-o` (dest output, PATH);
    - `set_defaults(func=_review)`.

    `_review(a)` returns `review(a.board, nets=a.net, project=a.project, f0=a.f0, clocks=a.clock, f_max=a.f_max, edge_k=a.edge_k, edge_fence=a.edge_fence, stackup=a.stackup, output=a.output)`.
  - **`review`:**
    1. It starts with `board = str(board)`, which keeps the path as given (design §5.3) whether the GUI passes a Path or not. Its imports are inside it, as `cost`'s are.
    2. `_load(board, stackup)`. E_NO_STACKUP and the stackup refusals propagate, so main exits 2.
    3. The project is `read_project(pipeline.project_path(project))` when given.
    4. `review_board(...)`.
    5. The files are written into `Path(output) if output else Path.cwd()`, by `write(folder, files, REVIEW_OUTPUTS, command)`:
       - `files` is `{"review.csv": review_csv(r), "review.png": review_png(r, board), "review.json": review_json(r, board, board_hash(board))}`;
       - its comment says review.json, the file the GUI reads, goes last, so a held file refuses before it changes.
    6. The advised `command` is `pipeline.command_line("kicad-rf-studio", "review", board, ...)`: each given option in the parser's order, frequencies as `str(hz)` and k as `str(k)`, then `-o` with the folder.
  - **The lines,** in AR-12's order:
    1. `r.notes`;
    2. the findings' `(code, params)`;
    3. I_REVIEW_FINDINGS {count};
    4. I_OUTPUTS {files sorted and joined by ", ", folder}, or the E_RESULTS_WRITE line in its place;
    5. each of REVIEW_LIMITS with `{}`.

    Each line goes to `emit`, which prints `render` by default. `review` returns 2 when a line is an E_ line, else 0.
- [ ] **Step 4: Run them.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_cli_new.py tests/test_compare.py tests/test_sexpr.py tests/test_gui_control.py -q`. Expected: PASS.
- [ ] **Step 5: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add src/kicad_rf_studio/cli.py src/kicad_rf_studio/core/messages.py po src/kicad_rf_studio/locale tests/test_cli_review.py
git commit -m "feat(cli): review BOARD, with the design's options, its three files written to -o or the working folder with review.json last, exit 0 with findings or without and 2 on a refusal or a refused write (Stage 5 design 5.1, 5.3)"
graphify update .
```

---

### Task 11 [code]: The goldens

**Files:**
- Create `tools/golden_review.py` and `tests/test_golden_review.py`.
- Written by the tool: `tests/fixtures/review/emc_review.json`, `usb2_hs.json`, `usb2_hs_gap.json`, `qspi_clk.json` and `lpf915.json`. They sit in a folder of their own, because `test_repo.py`'s stamp test globs `tests/fixtures/golden_*.json`.

**Interfaces:**
- Produces in `tools/golden_review.py`:
  - `GOLDEN = p0.FIX / "review"`;
  - `CASES = {"emc_review": [], "usb2_hs": [], "usb2_hs_gap": [], "qspi_clk": [], "lpf915": ["--net", "RF_*", "--f0", "915MHz"]}`. lpf915's RF nets match no pattern;
  - `golden_bytes(name) -> bytes`, run in an empty working folder;
  - `main() -> int`.

- [ ] **Step 1: Write the failing tests,** `tests/test_golden_review.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json

import golden_review
import pytest


@pytest.mark.parametrize("name", golden_review.CASES)
def test_the_review_writes_its_golden_review_json_byte_for_byte(name, tmp_path, monkeypatch):  # design 5.14; 5.17 item 2
    monkeypatch.chdir(tmp_path)
    golden = (golden_review.GOLDEN / f"{name}.json").read_bytes().replace(b"\r\n", b"\n")  # a CRLF checkout
    assert golden_review.golden_bytes(name) == golden


def test_the_goldens_name_their_board_by_file_and_hash_and_hold_each_rules_positive():  # design 5.14's table
    data = {n: json.loads((golden_review.GOLDEN / f"{n}.json").read_text(encoding="utf-8")) for n in golden_review.CASES}
    assert {n: d["board"]["path"] for n, d in data.items()} == {n: f"{n}.kicad_pcb" for n in data}
    assert all(len(d["board"]["sha256"]) == 64 and d["cavities"] == [] for d in data.values())
    assert {n: [f["rule"] for f in d["findings"]] for n, d in data.items()} == {
        "emc_review": ["R1", "R3"], "usb2_hs": [], "usb2_hs_gap": ["R1", "R1"], "qspi_clk": ["R2", "R2"],
        "lpf915": ["R4"]}
    assert data["lpf915"]["settings"]["l_mm"] == 1.545 and data["lpf915"]["settings"]["f_max_source"] == "carrier"
    assert data["usb2_hs_gap"]["findings"][0]["measured"]["run_mm"] == 1.0
    assert data["emc_review"]["findings"][0]["measured"] == {"run_mm": 6.0, "extent_mm": 10.0, "l_mm": 1.413}
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_golden_review.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'golden_review'`.
- [ ] **Step 3: `tools/golden_review.py`.**
  - Its docstring: "The review's golden outputs (Stage 5 design 5.14; plan 1 ruling 4): each review fixture's review.json as `review` writes it on the board copied into the working folder (golden_antenna._board, LF line ends as git stores it), so the golden names the board by its file name and its sha256 only. Plan 1's Task 11 records them once; a deliberate change is a ruled re-recording: delete tests/fixtures/review and run this again from the repo root."
  - `golden_bytes(name)`:
    1. copies the board with `_board(name)`;
    2. asserts that `cli.main(["review", f"{name}.kicad_pcb", *CASES[name], "-o", name]) == 0`;
    3. returns `Path(name, "review.json").read_bytes()`.
  - `main()` returns 1 when GOLDEN exists. Otherwise:
    1. it makes GOLDEN;
    2. it writes each case's bytes there, from a `tempfile.TemporaryDirectory()` working folder, restoring the folder it started in;
    3. it returns 0.
- [ ] **Step 4: Record them, once:** `.venv/Scripts/python tools/golden_review.py`.
  - Expected: exit 0, and `git status --short tests/fixtures` lists exactly `?? tests/fixtures/review/`.
  - Read each file: the counts must match Step 1's table.
  - If a finding differs from the design's table (§5.14), stop and report it for a ruling. Never edit a golden by hand.
- [ ] **Step 5: Run them.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_repo.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_golden_si.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite and pt-BR GUI tests, commit, graph.**

```bash
git add tools/golden_review.py tests/test_golden_review.py tests/fixtures/review
git commit -m "test(review): golden review.json of emc_review, usb2_hs, usb2_hs_gap, qspi_clk and lpf915, the board by file name and sha256, compared byte for byte (Stage 5 design 5.14)"
graphify update .
```

---

### Task 12 [doc]: Amendments A-70 and A-71

- [ ] **Step 1: The Stage 1 spec,** with each paragraph tagged as given:
  - **A-70, §2's stage table:**
    - after row 4: "| 5 | EMC, a first slice: geometry review, cavity modes and relative emission | `docs/superpowers/specs/2026-11-09-stage5-emc-design.md` (A-70, Stage 5 plan 1: controller recommendation, owner unavailable.) |";
    - the Later row becomes "| Later | A GPU engine, a bundled installer | — |".
  - **A-71, §3.2,** a table row after `compare`'s:

    "| `kicad-rf-studio review BOARD [--net PATTERN]… [--project PROJECT] [--f0 F] [--clock F]… [--f-max F] [--edge-k K] [--edge-fence] [--stackup NAME] [-o PATH]` | Reviews the board's geometry with no solver: measures the tagged nets' gap crossings (R1), reference changes (R2, for information), edge runs (R3) and the shields' via fences (R4) against λ/20 at f_max and the rules' public sources, writes review.json, review.csv and review.png in PATH (default: the current directory), prints each finding, and exits 0 with findings or without, 2 on a refusal or a refused write (A-71) |"
  - **A-71, §3.2,** after the "Signal-integrity results" paragraph:

    "**Geometry review** (Stage 5): `review` reads the board as `new` does (its stackup, or `--stackup`'s preset). It tags nets from `--net` (names or fnmatch patterns, which replace the name patterns), from the chain or lines of `--project`, which are always added, from the name patterns of the CLK, SCK, XTAL, SW, SPI, I2S and USB families past a deny list when no `--net` is given, and from a walk through two-pad series parts and differential partners; ground and power nets are never tagged. f_max is `--f-max`; else 5 times a carrier (`--f0`, a v1 project's f0 or an antenna project's band centre), at most 6 GHz; else an SI project's interface f_max, at most 6 GHz; else 5 GHz; never a project's simulation f_max (`region.f_max`). L is λ/20 at f_max in the stackup's highest εr. The review builds no model, starts no worker and never imports openEMS; a finding is a measurement against a published rule of thumb, never a pass or a fail. (A-71, Stage 5 plan 1: controller recommendation, owner unavailable.)"
  - **A-71, §3.3,** a bullet after the run folders':

    "**`review.json`** (Stage 5), schema 1, KiCad's frame (mm, y down):
    - the board's path as given and its sha256;
    - the settings: f_max and its source, εr, L, k, the edge fence, and the tags with their sources;
    - the notes, the keep-out limit last;
    - the findings: id, rule, code and params, net, layer, reference layer, net and h, place and box, the measured values, the threshold and its source, the tag's source and the KIIDs;
    - the cavities, which the review's cavity modes fill.

    `review.csv` holds one row per finding. `review` writes both, and `review.png`, only into its `-o` folder, the working folder by default; never into a run folder or the user's KiCad project. (A-71)"
  - **The Status line** gains at its end: "On `<date>`, Stage 5's plan 1 amended §2, §3.2 and §3.3 (A-70 and A-71) the same way." Here `<date>` is the day it is written.
- [ ] **Step 2: Test, commit, graph.** `.venv/Scripts/python -m pytest tests/test_repo.py -q` passes. This task is docs only, so reuse Task 11's green suite and name it in the ledger. Then:

```bash
git add docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs(spec): A-70 and A-71, Stage 5 in the stage table and the review command with its options, files and exit codes (Stage 5 plan 1; controller recommendation, owner unavailable)"
graphify update .
```

---

## The close (the controller's)

1. At the tip, run the full suite and the GUI tests in pt-BR, each alone, as in Global Constraints. Record their counts.
2. The whole-branch review, against this plan and the design's plan 1 row. A fix commit re-runs step 1.
3. Fast-forward merge into `main` locally, then delete the branch. Nothing is pushed.

## Not in this plan

- **Plan 2's items** (ruling 1):
  - the cavity modes and gate E-E. `review.json`'s `cavities` stays `[]`, and `Review.carrier` and `Review.clocks` are kept for their marks. emc_review's In1/In2 pair holds the GND island under box 2 that §5.14's look-through needs, so plan 2's cavity golden on it is a GND/+3V3 pair with that GND/GND region inside;
  - the GUI's Review tab and its `runs.data_dir()/review` folder. The tab shows each finding's rendered message, never `limit_source`, an English record;
  - Select in KiCad;
  - "simulate this";
  - the README's review tutorial;
  - the release check's review step;
  - A-72 onward: §4.6, the GUI's review folder (§3.2, §3.3) and the cavity limits (§7).
- **G_ wordings for the review's lines:** none is needed, since no line holds terminal syntax. Plan 2 adds the tab's labels.
- **R5, net classes and a default board-edge fence:** design §3, A1, A7.
- **`tracer.POWER` learning dotted names:** only the review reads them (design §7). Changing the shared pattern moves every kind's pins.
- **Calibrating the thresholds on the owner's boards:** the owner's (design §7), as is the native review of the new pt-BR terms (plano, caminho de retorno, cerca de vias, achado, marcadas).
- **A PNG golden and a CSV golden:** only review.json is pinned (ruling 4). The PNG's bytes follow matplotlib's version.

## Controller rulings (2026-11-09; binding)

These are the controller's ten rulings, as applied. One is changed, number 10, with its reason given. Each is a controller recommendation made while the owner is unavailable.

1. **Scope** is the design's plan 1 row. Plan 2's items are under Not in this plan. `cavities` is written `[]` and documented as plan 2's (Task 9's docstring; A-71).
2. **No pin moves.** The three golden suites run in every task's suite. Task 1's sha256 comparison and Task 11's goldens add the review's own pins.
3. **The fixtures:**
   - `emc_review` comes from Task 1, under A-3's isolation, with Stage 4 plan 2's commands;
   - it is checked by sha256 against git and by `git status`;
   - the four reused boards are untouched.
4. **The goldens** are five `review.json` files, each naming its board by file name and sha256, compared byte for byte. `tools/golden_review.py` writes them, and only Task 11 runs it.
5. **One module per responsibility:** `core/review/planes.py`, `tags.py`, `rules.py`, `outputs.py` and `__init__.py`, plus `cli.review`. Nothing imports openEMS, and matplotlib is imported inside `review_png` only (Task 9's and Task 10's import probes).
6. **The CLI** is the design's synopsis, defaults and exit codes, with BC1's f_max order and BC2's tag sources. Each line is a catalog code with its pt-BR msgstr, in the task that adds it (the Messages section; 23 new codes).
7. **A-70 and A-71** land in Task 12, docs only.
8. **Tests:**
   - each rule has a positive and a negative test, on §5.14's table (Tasks 4 to 7);
   - the runtime bound is 30 s (Task 10);
   - both suites run on every task.
9. **The close** is the controller's (above).
10. **Execution** is subagent-driven, in **twelve** tasks, not ten. Each rule has its own task, so a reviewer can reject one rule without the others. This is within the ruling's 8 to 12.

## Architect's rulings (this plan's constructions; controller recommendations, owner unavailable)

- **AR-1, R2's sides:**
  - A via's touching tracks are ordered top to bottom, and the first and the last references are compared (r1's "first and last").
  - A return capacitor is a footprint whose reference letters are "C" and whose two copper pads with a net sit on exactly the two nets. Its distance is that of its nearer pad centre.
  - A return via is a via of the net (not a plated pad) whose layer span holds both reference layers, as §5.2 says "via".
- **AR-2, R1's run and void:**
  - one finding per contiguous bare run of a (net, layer, reference) group's merged centre lines;
  - the void is the connected part of the outline, less the reference net's planes on every layer, that holds the run's midpoint;
  - the extent is the void's spread along the normal of the run's chord;
  - the antipad test is every vertex within the lone hole's radius + 0.6 mm (+1 µm): a via's diameter/2, or a THT pad's copper half-extent, at least its drill/2 (D-2, as the controller ruled it).
- **AR-3, R4's gap** is `min(covered, max(dist, along − dA − dB))` between consecutive fence vias (D-1):
  - along a side, it reads the pitch;
  - at a corner, it reads the pitch, not 2·inset + pitch;
  - across a frame opening, it reads 0;
  - for a cluster, it reads the whole unstitched stretch.
- **AR-4, R3's aggregation:**
  - d is measured from the track's centre line less the grown exclusion hulls;
  - flagged tracks merge into contiguous parts per group, with d the least;
  - the place is the midpoint of the part's stretch within k·h + w/2 of the outline;
  - it is stripline when both sides have a covered layer, with b the sum of their h.
- **AR-5, no reference:** a track with no reference is not measured, and I_EMC_NO_REFERENCE names its net. A skipped layer as near as the reference, or any skipped layer when there is no reference, skips the track.
- **AR-6, the classes:** `classify(board)`, as `_load` gives it. A project adds tags and f_max, not its class overrides.
- **AR-7, the patterns:**
  - FAMILIES are r1's expressions cut to A8's seven, dropping ETH and RMII;
  - the deny list applies to every family (the design's reading of A8);
  - flags use `fnmatchcase` on the full name or its base;
  - only nets of the board are tagged;
  - a flag that matches only ground or power nets is unmatched, and its line says why.
- **AR-8, ordering:** findings by rule, then KiCad x and y, numbered from 1; a clash's suffix follows that order.
- **AR-9, `--clock`** is parsed and kept in `Review.clocks` for plan 2's marks. Plan 1 writes it nowhere, and the advised command repeats it.
- **AR-10, `emc_review` follows §5.14 literally:**
  - **Its voids are cut-outs.** In1.Cu's GND is five zones that leave two boxes bare, as `planes(slot=)` leaves usb2_hs_gap's slot. The look-through's GND under box 2 is an In2.Cu island 1 mm clear of the +3V3 zones, tied by a via. No zone priority is used.
  - **CLK_EDGE.** Every zone is drawn to the outline with `square`, and KiCad's 0.5 mm edge clearance stops every fill 0.5 mm in. So CLK_EDGE is 0.5 mm wide with its centre 0.6 mm in: covered by GND, its edge 0.35 mm from the outline, R1 silent on it.
- **AR-11, R4's fence vias** are of `classes.gnd` nets only. A finding's `limit` is, by rule:
  - R1: the 1 mm cut;
  - R2: d;
  - R3: k·h;
  - R4: L, rounded to 1e-3.
- **AR-12, the lines' order:**
  1. the board's warnings;
  2. W_FILLS_AS_SAVED;
  3. the relative label;
  4. the basis;
  5. the tags;
  6. the notes;
  7. the findings;
  8. the count;
  9. I_OUTPUTS;
  10. the keep-out limit.

  `review.json`'s `notes` are lines 1 to 6, then the limit.
- **AR-13, the goldens** live in `tests/fixtures/review/`, outside `test_repo`'s `golden_*.json` stamp glob. They are not gated on `golden_v1.env()`: review.json holds rounded geometry, codes and English source names, and no plotting or Touchstone bytes.
- **AR-14, the tag lines** are four whole messages, one per source. Under the pt-BR design §5.1, "por" plus an article would have to contract, so they are not one template with a term.

## Open issues, ruled by the controller (2026-11-09; owner unavailable)

1. **D-1, R4's gap:** confirmed, `min(covered, max(dist, along − dA − dB))`. It reads the pitch on a side and at a corner, nothing across a frame opening, and the whole unstitched stretch for a cluster: §5.2's "measured along the line, over the stretches the frame pads cover".
2. **D-2, R1's antipad radius:** changed for pads. A via's radius stays its diameter/2. A `thru_hole` pad's is its copper half-extent, at least its drill/2, so a THT crystal's or oscillator's own antipad is not a gap. Task 4's lone-hole test gains the pad case.
3. **D-3, R3's connector negative:** confirmed. k = 2 is kept, and k = 5 with and without the connector class exercises the exclusion itself.
4. **emc_review's In1/In2 pair:** accepted as built, since §5.14 asks for both the look-through and the cavity. Carried to plan 2: its E-E fixture golden either models the GND/GND region over box 2 or uses a cavity board of its own, as plan 2's own plan rules.
5. **Task 1's unrun fill facts:** the stop rule stands. A fact that fails on the real fills is reported with its measured value, and the fixture's numbers do not move without a ruling.
6. **The inferred goldens and Task 7's 2.0 mm gap:** the stop rules of Tasks 7 and 11 stand.
7. **W_FILLS_AS_SAVED among the review's lines:** kept. The review reads the fills as saved, which is what that line says, and it costs no new code.
8. **The golden bytes with no env gate:** accepted. A shapely or GEOS change that moves a rounded value is a ruled re-recording, never a code fix.
9. **Owner items:** R1's look-through precision on public boards, the thresholds' calibration and the native pt-BR review of the new EMC terms stay the owner's (design §7). The close's record lists them.
10. **Two corrections by the controller:**
    - Task 8's parametrized f_max test now asserts f, the source and the carrier plainly. The draft's `or` let a wrong f pass.
    - `resolve_f_max` and A-71 name `region.f_max` as the simulation f_max that is never read, beside the SI interface's `f_max_hz`, which is.
11. **The baseline count:** 2820803's src, tests, tools, po and pyproject.toml equal 61fd0a9's, whose suites read 2477 passed and 7 skipped (37:40), and 50 passed and 4 skipped in pt-BR (6:04). Task 1's suite compares against that.
