# Stage 4 Plan 2: The SI Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A user creates a signal-integrity project from a KiCad board with `new BOARD --start REF.PAD --end REF.PAD --interface NAME` (one net, or a differential pair found by KiCad's own rule, plus up to two victims); `cost` lists every straight section's 2D impedance against the interface's target before its estimate, and `run` simulates one job per port inside MUR walls with the DC pulse and writes the layout N-port as `layout.s{N}p`.

**Architecture:**
- **Schema 3.** An SI project.json is schema 3 (`"kind": "si"`): v1's board, preset, region, mesh, stackup, lid, classes, others, ports and gates, without f0, harmonics, band factor or chain, plus the interface and its band and target, the dielectric model, the stop window, `mesh.max_cell_mm`, the lines (each its role and its chain in v1's chain shape) and the pair. Every SI branch tests `core.project.si(data)`. `chain_of` and `parts` merge the lines, so v1's region, protected set, connectivity, sections, part ports and grid parts take every line as measured copper.
- **`new`.** The tracer walks each line from its start pad to its end pad; KiCad's `MatchDpSuffix`, ported, with a DP/DM alias, finds the partner; every two-pad part on a line is a part port but a pull-up; an end takes v1's same-layer reference when that lies within the reach across clear copper, else plan 1's vertical port. `new` then picks the parts and the lid from the region the model will build, its kept references included, and writes T_max, the stop window and max_cell from the longest route and the 2D εeff.
- **The engine.** `build_geometry` takes the lines' copper layers for d and the reach; `build_mesh` passes plan 1's SI rule (max_cell, and spans over every solid rod and over staircased copper); `model_spec` writes the DC pulse, κ-free materials (Debye on request) and the vertical ports; `cost` prints the 2D table, cs2d's pair on coupled sections, which fit2d also checks; `run` writes `layout.s{N}p` on the uniform grid from DC. Plans 3–5 add the SI results, the gates and the GUI.

**Tech Stack:**
- Python ≥ 3.11 (dev venv 3.14.2), numpy, scipy, shapely and scikit-rf (its Touchstone writer and reader), all already dependencies; plan 1's `cs2d.pair`, `core.post.si`, `substrate_h(zs, layers)`, `xy_lines(max_cell, spans)`, `si_max_cell`, `plane_under`, `vertical`, `dc_pulse`, `round_trip`, `si_t_max`, `stop_window` and `debye`. No new dependency.
- openEMS 0.37.0 and CSXCAD 0.7.0, only in the worker; Task 11 runs them for real.
- KiCad 9's bundled Python with pcbnew, for `tools/make_fixtures.py` only (Task 1).
- pytest, `tests/fake_worker.py`, `tests/networks.py`; `tools/catalog.py` (Babel, dev extra).

**Spec:**
- `docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md` (binding): §5.12 item 2, with §2–§4, §5.1–§5.5, §5.9, §5.11's fixtures paragraph and §5.13.
- The Stage 1 spec, `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, where the design reuses it: §3.1–§3.3, §4.4–§4.6, §5.1–§5.7, §6.3, §6.4, §7.1, §9.1 (A-3), §10; amendments A-1 to A-47.
- Plan 1, `docs/superpowers/plans/2026-11-02-stage4-plan1-pins-and-si-hooks.md`, merged at `8e758b3`, its "Open issues, ruled by the controller", and its carried items in `.superpowers/sdd/2026-11-03-stage4-plan1-rulings-and-minors.md` ("Carried to plan 2").
- Task 11 lands A-48 (§6.4), A-49 (§10), A-50 (§3.2, §3.3), A-51 (§5.1, §5.6, §5.7), A-52 (§6.3) and A-53 (§5.4, §5.5), with their exact text.
- Research (git-ignored): `.superpowers/sdd/stage4-research/` r1–r4.

**Branch:** `stage4-plan2`, from `main` at `8e758b3`. This plan is `docs/superpowers/plans/2026-11-03-stage4-plan2-si-project.md`. Commands run from the repo root with `.venv/Scripts/python`. Paths without a folder are under `src/kicad_rf_studio/`. Line references are `main`'s at `8e758b3`; if an earlier task moved a line, find it by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage4-plan2 main`. Then `git diff --stat 8e758b3 HEAD -- src tests tools po pyproject.toml` must print nothing.
2. Commit this plan on the branch.
3. After Task 11: the whole-branch review, a local fast-forward merge into `main`, and delete the branch. Nothing is pushed.

## Global Constraints

- **v1 and the antenna byte for byte** (design §3, §4): v1 projects stay schema 1 and antenna projects schema 2; `tests/test_golden_v1.py` and `tests/test_golden_antenna.py` stay green on every task. A task that moves a pin is wrong: stop and get a ruling, never re-record.
- **Schema 3 only for SI:** every SI branch tests `core.project.si(data)` (the schema), never `kind`. SI keys appear only in SI projects and specs: an excitation's `window_s` and `flat_s` with `f1` 0, a material's `"debye"`, a port's `"dir": "z"` and `{"plane": ...}` reference, `mesh.max_cell_mm`.
- **MUR on all six faces for SI:** an SI spec never holds `"boundary"`. Copper is solid, never openEMS's conducting sheet (an SI spec never holds `"copper"`), and every SI material's `kappa` is 0.0: v1's constant κ never enters an SI spec (design §3).
- **openEMS stays in the worker** (Stage 1 §3.1): the CLI, the orchestrator, `core.cs2d` and `core.post` never import openEMS or CSXCAD.
- **Messages:** every new user-facing string is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, in the same task, compiled with `.venv/Scripts/python tools/catalog.py` (run, set the msgstr, run again), by the pt-BR design's §6 glossary and this plan's glossary ruling. A word passed as a parameter is a `T_` code. Numbers keep the decimal point. A msgstr keeps every identifier, option, quoted text, backticked command and dotted number of its msgid (`tests/test_sexpr.py`'s KEEP).
- **Tests:** test-first. Tier (a) tests never run openEMS, KiCad, the network or a build; they use the fake worker and the committed fixtures. `KrsError` tests check `.code` and `.params`. A run command names its new tests by node id, never by a `-k` word.
- **Replica-checked numbers:** the fixtures' coordinates, and the bounds and values this plan derives from them, come from KiCad 9's footprint files and were checked on a text replica of the boards read by the repo's own importer (KiCad's pads, the planes as rectangles with square antipads), not through pcbnew. One the code misses stops the task: report both values and the formula that differs; the test changes only on a ruling.
- **Isolation:** tests never touch a real KiCad folder, the Documents folder, KiCad's settings or the real data folder. KiCad's Python runs only in Task 1, under A-3's isolation. Task 11's runs set LOCALAPPDATA and XDG_DATA_HOME to a folder under `$env:TEMP` in the same call, and type `CSXCAD_INSTALL_PATH` in the call, never in a file.
- **Full suite** before every commit: `.venv/Scripts/python -m pytest -q`, about 22 minutes (2123 passed, 6 skipped at `8e758b3`). Run it once, in the background, with nothing beside it, and wait for it to exit.
- **Git:** no push. The pre-commit privacy gate runs on every commit; never use `--no-verify`. No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name; write `<openEMS folder>`, `<KiCad 9 bin folder>` and `<RUN>`. No commit message carries a co-author line; use the messages as given.
- **Files:** every new `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`. Code and docs are in English.
- **Python** only with a script, `-c` or `-m`: never a bare interactive `python`, least of all in a background shell.
- **Workflow:** `graphify query "<question>"` before reading code, and `graphify update .` after each commit. Ponytail: the laziest solution that works, in the fewest files, with a `ponytail:` comment naming the ceiling on each corner cut. Reuse `new_antenna`'s shape and `_load`/`_port`/`_write`, the tracer, `build_region`, `project_parts`, `sections`, `cross_section`, cs2d's `solve` and `pair`, plan 1's hooks, `write`/`touchstone`/`port_map`, `make_fixtures`' helpers and `golden_v1.record`.

## Review Focus

1. **`new`'s region against the model's:** an end referenced to a QFN's exposed pad (qspi_clk's U1.11 to U1.17), which widens the ROI build_geometry builds, with a decoupling capacitor in that band (qspi_clk's C1, whose pads lie 1.7–2.4 mm off the line). Expected: `new` picks the parts and the lid from the ROI the model builds, so C1 is copper in the model and joins +3V3 to GND by the layer change. Checks: Task 5's `test_new_interface_on_the_qspi_clock` (`others` is C1 as copper) and Task 6's `test_an_si_line_on_two_layers_takes_both` (`parts` R1 and C1).
2. **An end whose nearest ground lies across another pad or past the reach** (a micro-B's D+ pin, its GND pin 5 behind the ID pin 4; a QFN pin's exposed pad is clear), and an end with no ground and no plane. Expected: v1's horizontal port only across clear copper within the reach, else the vertical port to the plane under the pad; with neither, E_SI_NO_REFERENCE, before anything is written; a port longer than λ/20 at f_max is W_SI_LONG_PORT. Checks: Task 4's `test_an_si_end_reaches_a_reference_only_across_clear_copper` and `test_an_si_ends_reference_is_v1s_or_the_plane_under_its_pad`; Task 5's `test_new_interface_writes_an_si_project` (J1's ports vertical, U1's to U1.17), `test_an_end_with_no_reference_and_no_plane_is_refused` and `test_a_long_port_is_warned`.
3. **Via rods under max_cell:** an exposed pad's thermal vias, a signal via's layer change, and a ground via whose ring lies within the reach while its centre lies past the protected extent on one axis. A rod with no span can fall between the graded lines and lose every node. Expected: every solid rod keeps lines across it at d or finer on each axis, a measured net's over ±1 mm and any other over its radius; with max_cell None the spans change nothing. Checks: Task 6's `test_every_solid_rod_keeps_its_lines`, `test_a_rod_past_the_extent_on_one_axis_keeps_its_lines` and `test_mesh_rule.py`'s `test_without_max_cell_spans_are_ignored`.
4. **A line on a layer whose dielectric differs from the top layer's** (a B.Cu return over a thinner prepreg, a stripline). Both fixtures have 0.2 mm under each outer layer, so nothing there shows it. Expected: d, the region's reach and the protected reach take the thinnest dielectric next to the lines' layers. Checks: Task 4's `test_an_si_region_grows_by_its_lines_substrate` and Task 6's `test_a_line_takes_its_own_dielectric_for_d_and_the_reach`.
5. **A route through a part of three or more pads** (a common-mode choke), beside an ESD array whose pads sit on the line. Expected: `E_SI_THROUGH_PART` naming the part and advising one project per side; the ESD array's pads are copper of the line, no refusal; a line with nothing on the way keeps v1's `E_NO_CHAIN`. Check: Task 3's `test_a_line_through_a_part_of_three_or_more_pads_is_refused`; the USB fixture's U2.

Ten more input classes are pinned in their own tasks: a pair named outside KiCad's rule and a partner with two pads on one footprint (Task 3), a pull-up and a DNP part on a line (Task 3), a short route whose held level must end flat before T_max (Task 4), a victim outside the measured lines' region and a line on a net another line holds (Task 5), a pair's legs that the 10 µm simplification leaves microns apart (Task 8), ports reordered by hand (Task 2), and an SI project opened by the GUI before plan 5 (Task 2).

---

## File structure

```
tools/make_fixtures.py; tests/fixtures/{usb2_hs,usb2_hs_neck,usb2_hs_gap,usb2_hs_45,qspi_clk}.*                       # T1
src/kicad_rf_studio/core/project.py (schema 3, interfaces); src/kicad_rf_studio/gui/control.py                         # T2
src/kicad_rf_studio/core/kicad/tracer.py (the pair, the lines); src/kicad_rf_studio/core/model/parts.py (SI roles)    # T3
src/kicad_rf_studio/core/geometry/region.py (layers), .../core/geometry/sections.py (line_layers, route_length,
  eps_eff_2d, cross_section's h), .../core/model/ports.py (_apart_axis, clear_between, si_reference),
  .../core/model/spec.py (si_t_max)                                                                                    # T4
src/kicad_rf_studio/cli.py (new_si, _head_notes)                                                                       # T5
src/kicad_rf_studio/core/project.py (parts), .../core/geometry/__init__.py, .../core/mesh/__init__.py, .../core/mesh/
  rule.py, .../core/mesh/gates.py, src/kicad_rf_studio/pipeline.py (load, build_model)                                 # T6
src/kicad_rf_studio/core/model/ports.py (ends, vertical), .../core/model/spec.py, .../core/model/csx.py,
  src/kicad_rf_studio/pipeline.py (last_sample)                                                                        # T7
src/kicad_rf_studio/core/geometry/sections.py (cross_section's partners), .../core/mesh/gates.py (fit2d),
  .../core/project.py (default_gates), src/kicad_rf_studio/pipeline.py (cost)                                          # T8
src/kicad_rf_studio/core/project.py (shown_reference), .../core/post/waves.py, src/kicad_rf_studio/pipeline.py
  (outputs, retune, verify), tests/networks.py                                                                         # T9
tools/golden_si.py, tests/test_golden_si.py, tests/fixtures/golden_si.json                                             # T10
src/kicad_rf_studio/core/messages.py, po/pt_BR.po and the .mo (T2–T9); new tests: tests/test_si_lines.py,
  tests/test_cli_si.py, tests/test_si_geometry.py, tests/test_si_model.py, tests/test_si_cost.py, tests/test_si_run.py;
  docs/validation/<date>-si-first-run.md and the Stage 1 spec (T11)
```

---

### Task 1 [code]: The fixtures

**Files:**
- Modify: `tools/make_fixtures.py` (`copper` L73-77, `track` L80-86, `via` L97-103, `zone` L106-116, `new_board` L430-445, `main` L478-492; the new boards after `pads_zoo`); `tests/test_fixtures.py` (NAMES), `tests/test_pads.py` (the parametrize list, one test), `tests/test_stackup.py` (`test_every_fixture_board_carries_the_default_two_layer_stackup`), `tests/test_gates.py` (one test).
- Written by the tool: `tests/fixtures/usb2_hs`, `usb2_hs_neck`, `usb2_hs_gap`, `usb2_hs_45` and `qspi_clk`, each `.kicad_pcb` with its `.pads.json`.

**Interfaces:**
- Produces, in `tools/make_fixtures.py`: `STACKUP_4L`, `W_PAIR = 0.3`, `GAP = 0.25`, `W_SE = 0.33`, `QFN`, `R0402`, `C0402`; `new_board(path, seed, rules=RULES, copper=2, thickness=0.8, stackup=STACKUP)`; `copper(b, item, name, width, layer=pcbnew.F_Cu)`; `track(b, name, width, *points, layer=pcbnew.F_Cu)`; `via(b, at, name="GND")`; `zone(b, layer, corners, clearance=0.15, name="GND")`; `square(b, layer, name, x0, y0, x1, y1)`; `planes(b, box, slot=None)`; `usb2_hs(b, neck=False, gap=False, bend=False)`; `qspi_clk(b)`; five BOARDS entries.
- Facts later tasks rely on (KiCad's frame, mm, y down; the importer negates y). Four copper layers, F.Cu (signal), In1.Cu (GND zone), In2.Cu (+3V3 zone), B.Cu (signal); 0.2 mm prepreg εr 4.3 under each outer copper, a 1.04 mm core εr 4.5, tan δ 0.02, 35 µm copper, 1.6 mm.
  - **usb2_hs** (outline 94, 94–134, 106): J1 micro-B at 270°, J1.2 USB_D- (98.4625, 99.675), J1.3 USB_D+ (98.4625, 100.325), J1.4 no net between J1.3 and J1.5 GND (98.4625, 101.625). U2 SOT-23-6 at (103, 100): pads 1 and 6 USB_D- at y 99.05, 3 and 4 USB_D+ at y 100.95, 2 GND with a via in it, 5 VBUS. The pair: 0.3 mm lines at y 99.725 and 100.275, a 0.25 mm gap, each line's inner edge on J1's and U1's inner pin edges (y 99.875, 100.125); from J1's pins to x 100.5, out to U2's rows, 0.6 mm wide (the pads' height) through U2's pads to x 105.5, back to the pair, then 17.49 mm to the resistors. R2 22 Ω (USB_D-, MCU_D-) at (123.5, 99.555) and R1 22 Ω (USB_D+, MCU_D+) at (123.5, 100.445), each entered at its line's own y. U1 QFN-16 at (130, 100): U1.2 MCU_D- (128.5375, 99.75), U1.3 MCU_D+ (128.5375, 100.25), U1.17 GND (the exposed pad), four GND vias in it. Victim AUX, 0.2 mm, from TP1.1 (108, 101.15) to TP2.1 (120, 101.15), 0.625 mm off the pair. C1 100nF (+3V3, GND) at (127, 102). Each line's route is 30.405 mm of track; no orthogonal jog is shorter than 0.675 mm.
  - **Variants:** `usb2_hs_neck` narrows each line to 0.2 mm on its inner side over x 112–117 (its outer edge kept, the gap 0.45 mm there); `usb2_hs_gap` leaves In1.Cu bare over x 116–117, y 97–103, off the long run's 2D cut at x 114; `usb2_hs_45` takes the pair up 1.5 mm over x 110–117 through four 45° bends a line at constant pitch.
  - **qspi_clk** (outline 94, 94–128, 106): U1 QFN-16 at (100, 100), U1.11 QSPI_CLK (101.4625, 99.75), U1.16 +3V3 (no track: a third netted pad, so the tracer never reads U1 as a two-pad part), U1.17 GND; R1 33 Ω (QSPI_CLK, FLASH_CLK) at (104.5, 99.75); the line 0.33 mm wide at y 99.79, its top edge on U1.11's: FLASH_CLK on F.Cu to a via at (107, 99.79), on B.Cu to a via at (117, 99.79), on F.Cu to U2.6 (119.525, 99.75), U2 a SOIC-8 at (122, 100.385) turned 180° (U2.4 GND, U2.8 +3V3); C1 100nF at (107, 102). The route is 17.0425 mm.
  - **Checked on the replica,** every line measured, at n 2: v1's d fill and the SI rule place no line the edge lint fails, fit2d reads at most 2.3 %, no copper of two nets lies closer than 0.15 mm, and cs2d with the mask reads the pair's Zdiff 90.2 Ω on the 17.49 mm run (95.4 bare), the neck's 117.4 Ω and the QSPI line's Z0 50.0 Ω. Edges of two features 15–25 µm apart (a 0.3 mm track into a 0.25 mm QFN pin) read fit2d 5.6–7 % off, 50 µm passed, and a line's edge on another feature's opposite edge failed the lint after its re-mesh: every line shares one set of lines per axis.

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_fixtures.py`'s NAMES and `tests/test_pads.py`'s `test_pads_match_pcbnew` list gain `"usb2_hs", "usb2_hs_neck", "usb2_hs_gap", "usb2_hs_45", "qspi_clk"`.
  - `tests/test_stackup.py`: `test_every_fixture_board_carries_the_default_two_layer_stackup` becomes `test_every_fixture_board_carries_its_generators_stackup`: for a stem starting with `("usb2_hs", "qspi_clk")` the kinds are `["mask", "copper", "dielectric", "copper", "dielectric", "copper", "dielectric", "copper", "mask"]` and `dielectric_thickness() == pytest.approx(b.thickness - 0.16)`; every other board as before.
  - In `tests/test_pads.py` (imports gain `from shapely.geometry import Point`):

```python
def test_the_si_fixtures():  # Stage 4 design 5.11: four layers, KiCad's own footprints, a USB 2.0 pair, a QSPI clock
    usb, qspi = (load_board(FIX / f"{n}.kicad_pcb") for n in ("usb2_hs", "qspi_clk"))
    for b in (usb, qspi):
        assert b.copper_layers == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu") and b.thickness == pytest.approx(1.6)
        assert [(x.thickness, x.epsilon_r) for x in b.stackup.layers if x.kind == "dielectric"] == [
            (0.2, 4.3), (1.04, 4.5), (0.2, 4.3)]
        assert {(a.layer, a.net) for a in b.areas if a.source == "zone"} == {("In1.Cu", "GND"), ("In2.Cu", "+3V3")}
        # three netted pads or more: the tracer never reads an IC as a two-pad part
        assert all(len([p for p in f.pads if p.net]) >= 3 for r, f in b.footprints.items() if r[0] == "U")
    fp = usb.footprints
    assert [fp[r].lib_id for r in ("J1", "U2", "U1")] == ["Connector_USB:USB_Micro-B_Molex-105017-0001",
                                                          "Package_TO_SOT_SMD:SOT-23-6", QFN]
    assert [(p.number, p.net) for p in fp["U2"].pads] == [("1", "USB_D-"), ("2", "GND"), ("3", "USB_D+"),
                                                         ("4", "USB_D+"), ("5", "VBUS"), ("6", "USB_D-")]
    assert {r: (fp[r].value, [p.net for p in fp[r].pads]) for r in ("R1", "R2", "C1")} == {
        "R1": ("22", ["USB_D+", "MCU_D+"]), "R2": ("22", ["USB_D-", "MCU_D-"]), "C1": ("100nF", ["+3V3", "GND"])}
    for name, (x, y) in {"J1.2": (98.4625, 99.675), "J1.3": (98.4625, 100.325), "J1.5": (98.4625, 101.625),
                         "U1.2": (128.5375, 99.75), "U1.3": (128.5375, 100.25), "R1.1": (122.99, 100.445),
                         "TP1.1": (108, 101.15), "TP2.1": (120, 101.15)}.items():
        assert math.dist(usb.pads(name)[0].center, (x, -y)) <= 1e-6, name
    assert usb.pads("J1.4")[0].net == "" and usb.outline.bounds == (94.0, -106.0, 134.0, -94.0)
    assert {t.width for t in usb.tracks if t.net in ("USB_D+", "USB_D-", "MCU_D+", "MCU_D-")} == {0.3, 0.6}
    assert {t.width for t in usb.tracks if t.net == "AUX"} == {0.2}
    assert {(t.layer, t.width) for t in qspi.tracks if t.net == "FLASH_CLK"} == {("F.Cu", 0.33), ("B.Cu", 0.33)}
    assert [v.net for v in qspi.vias].count("FLASH_CLK") == 2
    assert math.dist(qspi.pads("U2.6")[0].center, (119.525, -99.75)) <= 1e-6 and qspi.pads("U2.4")[0].net == "GND"
    neck, gap, bend = (load_board(FIX / f"usb2_hs_{n}.kicad_pcb") for n in ("neck", "gap", "45"))
    assert {t.width for t in neck.tracks if t.net == "USB_D+"} == {0.2, 0.3, 0.6}
    assert any(a.polygon.contains(Point(116.5, -100)) for a in usb.areas if a.layer == "In1.Cu")
    assert not any(a.polygon.contains(Point(116.5, -100)) for a in gap.areas if a.layer == "In1.Cu")
    assert sum(min(abs(t.end[0] - t.start[0]), abs(t.end[1] - t.start[1])) > 0.5 for t in bend.tracks) == 4
```

    with `QFN = "Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm"` at the module's top.
  - In `tests/test_gates.py` (imports gain `check_fit2d`, `fit2d` and `mesh_with_lint` from `core.mesh.gates`, where missing):

```python
@pytest.mark.parametrize("name", ["usb2_hs", "usb2_hs_neck", "usb2_hs_gap", "usb2_hs_45", "qspi_clk"])
def test_an_si_fixture_passes_the_edge_lint_and_fit2d_with_every_line_measured(name):  # design 5.11
    board = load_board(FIX / f"{name}.kicad_pcb")
    nets = sorted({t.net for t in board.tracks} - {"GND", "+3V3"})  # every line, as an SI project measures them
    geom = build_geometry(board, {"f0_hz": 10e9 / 3, "harmonics": 3, "band_factor": 1.0, "ports": [],
                                  "stackup": board.stackup.to_json(), "region": {"expand_h": 6.0, "margin_scale": 1.0},
                                  "mesh": {"n": 2, "reach_h": 6.0},
                                  "chain": {"start": "", "end": "", "nets": nets, "series": [], "shunt": []}})
    mesh = mesh_with_lint(geom, geom.protected, 2)  # E_EDGE_LINT would raise
    check_fit2d(fit2d(geom, mesh), 0.03, 2)  # E_FIT2D would raise
    assert mesh.d == pytest.approx(0.1)
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_fixtures.py tests/test_pads.py tests/test_stackup.py "tests/test_gates.py::test_an_si_fixture_passes_the_edge_lint_and_fit2d_with_every_line_measured" -q`. Expected: FAIL with `FileNotFoundError` on `usb2_hs.kicad_pcb`.
- [ ] **Step 3: `tools/make_fixtures.py`.**
  - **The helpers' new parameters:** `new_board(path, seed, rules=RULES, copper=2, thickness=0.8, stackup=STACKUP)` sets `b.SetCopperLayerCount(copper)` when `copper != 2`, the thickness and the stackup it splices; `copper()` and `track()` take `layer=pcbnew.F_Cu`; `via()` and `zone()` take the net `name`, "GND" by default. `main` passes `copper=4, thickness=1.6, stackup=STACKUP_4L` for a name starting with `("usb2_hs", "qspi_clk")`, and RULES. The docstrings say so.
  - **Add, as given:**

```python
# Stage 4's boards (design 5.11): signal, GND, +3V3, signal, 0.2 mm of prepreg under each outer copper, 1.6 mm
STACKUP_4L = """(stackup
 (layer "F.SilkS" (type "Top Silk Screen")) (layer "F.Paste" (type "Top Solder Paste"))
 (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01)) (layer "F.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 1" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.3) (loss_tangent 0.02))
 (layer "In1.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 2" (type "core") (thickness 1.04) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "In2.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 3" (type "prepreg") (thickness 0.2) (material "FR4") (epsilon_r 4.3) (loss_tangent 0.02))
 (layer "B.Cu" (type "copper") (thickness 0.035)) (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
 (layer "B.Paste" (type "Bottom Solder Paste")) (layer "B.SilkS" (type "Bottom Silk Screen"))
 (copper_finish "None") (dielectric_constraints no))
"""
# cs2d with the mask: a 90.3 Ω pair (95.4 bare) and a 50.0 Ω line on 0.2 mm of εr 4.3. Every line shares one set of mesh
# lines per axis, so the pair's inner edges sit on J1's and U1's inner pin edges and the QSPI line's top edge on U1.11's:
# edges 25 µm apart read fit2d 5.6-7 % off
W_PAIR, GAP, W_SE = 0.3, 0.25, 0.33
QFN = "Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm"
R0402, C0402 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric"


def square(b, layer, name, x0, y0, x1, y1):
    zone(b, layer, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], name=name)


def planes(b, box, slot=None):
    """GND on In1.Cu and +3V3 on In2.Cu, 0.5 mm inside the outline `box` (x0, y0, x1, y1); with `slot`, In1.Cu's GND as
    four zones that leave that box bare."""
    x0, y0, x1, y1 = box[0] + 0.5, box[1] + 0.5, box[2] - 0.5, box[3] - 0.5
    if slot:
        sx0, sy0, sx1, sy1 = slot
        for r in ((x0, y0, sx0, y1), (sx1, y0, x1, y1), (sx0 - 0.5, y0, sx1 + 0.5, sy0), (sx0 - 0.5, sy1, sx1 + 0.5, y1)):
            square(b, pcbnew.In1_Cu, "GND", *r)
    else:
        square(b, pcbnew.In1_Cu, "GND", x0, y0, x1, y1)
    square(b, pcbnew.In2_Cu, "+3V3", x0, y0, x1, y1)


def decoupled(b, at):
    """C1, 100 nF, joining +3V3 to GND at `at`, each pad down a track to a via of its net."""
    place(b, C0402, "C1", "100nF", at, 0, {"1": "+3V3", "2": "GND"})
    for dx, name in ((-0.48, "+3V3"), (0.48, "GND")):
        track(b, name, 0.3, (at[0] + dx, at[1]), (at[0] + dx, at[1] + 1.2))
        via(b, (at[0] + dx, at[1] + 1.2), name)


def usb2_hs(b, neck=False, gap=False, bend=False):
    """A USB 2.0 high-speed pair along y = 100, left to right (Stage 4 design 5.11): J1, a micro-B (USB_D- J1.2, USB_D+
    J1.3); U2, a SOT-23-6 ESD array whose pads 1 and 6 (USB_D-) and 3 and 4 (USB_D+) the lines run straight through,
    0.6 mm wide; the pair at a 0.25 mm gap; the 22 Ω series resistors R2 and R1; U1, a QFN-16 "MCU" (MCU_D- U1.2,
    MCU_D+ U1.3, GND on its exposed pad U1.17). AUX, the victim, runs from TP1.1 to TP2.1 0.625 mm under the pair; C1,
    100 nF, joins +3V3 to GND by U1. `neck` narrows each line to 0.2 mm on its inner side over x 112-117, `gap` leaves
    In1.Cu bare over x 116-117, y 97-103, and `bend` takes the pair up 1.5 mm over x 110-117 through 45° bends at
    constant pitch."""
    rect(b, pcbnew.Edge_Cuts, 94, 94, 134, 106)
    planes(b, (94, 94, 134, 106), (116, 97, 117, 103) if gap else None)
    place(b, "Connector_USB:USB_Micro-B_Molex-105017-0001", "J1", "USB_B_Micro", (97, 100.325), 270,
          {"1": "VBUS", "2": "USB_D-", "3": "USB_D+", "5": "GND", "6": "GND"})  # pins at x 98.4625, y 99.025-101.625
    track(b, "GND", 0.3, (98.4625, 101.625), (98.4625, 102.825))  # J1.5 to its shield's plated hole
    place(b, "Package_TO_SOT_SMD:SOT-23-6", "U2", "USBLC6-2SC6", (103, 100), 0,
          {"1": "USB_D-", "2": "GND", "3": "USB_D+", "4": "USB_D+", "5": "VBUS", "6": "USB_D-"})
    via(b, (101.8625, 100))  # U2.2 to In1.Cu, in its pad
    place(b, R0402, "R2", "22", (123.5, 99.555), 0, {"1": "USB_D-", "2": "MCU_D-"})  # pad edges on the lines' inner
    place(b, R0402, "R1", "22", (123.5, 100.445), 0, {"1": "USB_D+", "2": "MCU_D+"})  # edges: no jog to them
    place(b, QFN, "U1", "MCU", (130, 100), 0, {"2": "MCU_D-", "3": "MCU_D+", "17": "GND"})
    for x in (129.55, 130.45):
        for y in (99.55, 100.45):
            via(b, (x, y))  # the exposed pad to In1.Cu
    p = (W_PAIR + GAP) / 2  # each line's centre off y = 100
    t = p * math.tan(math.pi / 8)  # a 45° bend moves each line's vertex this far along x, at constant pitch
    for usb, mcu, s in (("USB_D-", "MCU_D-", -1), ("USB_D+", "MCU_D+", 1)):  # s: the line's side of y = 100
        y_p, y_s = 100 + s * p, 100 + s * 0.95  # the pair; through U2's pads
        track(b, usb, W_PAIR, (98.4625, y_p), (100.5, y_p), (100.5, y_s))
        track(b, usb, 0.6, (100.5, y_s), (105.5, y_s))  # as tall as U2's pads: one pair of edges, not two
        mid = [(110 + s * t, y_p), (111.5 + s * t, y_p - 1.5), (115.5 - s * t, y_p - 1.5), (117 - s * t, y_p)] if bend else []
        if neck:
            track(b, usb, W_PAIR, (105.5, y_s), (105.5, y_p), (112, y_p))
            track(b, usb, 0.2, (112, y_p + s * 0.05), (117, y_p + s * 0.05))  # the outer edge kept
            track(b, usb, W_PAIR, (117, y_p), (122.99, y_p))
        else:
            track(b, usb, W_PAIR, (105.5, y_s), (105.5, y_p), *mid, (122.99, y_p))
        track(b, mcu, W_PAIR, (124.01, y_p), (128.5375, y_p))
    for ref, x in (("TP1", 108), ("TP2", 120)):
        place(b, "TestPoint:TestPoint_Pad_1.0x1.0mm", ref, "TP", (x, 101.15), 0, {"1": "AUX"})
    track(b, "AUX", 0.2, (108, 101.15), (120, 101.15))
    decoupled(b, (127, 102))


def qspi_clk(b):
    """A QSPI clock (Stage 4 design 5.11): QSPI_CLK from U1.11, a QFN-16 "MCU" pin (+3V3 on U1.16, GND on its exposed
    pad U1.17), through R1, 33 Ω, then FLASH_CLK down a via to 10 mm on B.Cu and up another to U2.6, the clock pin of
    U2, a SOIC-8 flash turned 180° (U2.4 GND, U2.8 +3V3). C1, 100 nF, joins +3V3 to GND by the first via, where the
    return current leaves In1.Cu's GND for In2.Cu's +3V3."""
    rect(b, pcbnew.Edge_Cuts, 94, 94, 128, 106)
    planes(b, (94, 94, 128, 106))
    place(b, QFN, "U1", "MCU", (100, 100), 0, {"11": "QSPI_CLK", "16": "+3V3", "17": "GND"})
    for x in (99.55, 100.45):
        for y in (99.55, 100.45):
            via(b, (x, y))
    place(b, R0402, "R1", "33", (104.5, 99.75), 0, {"1": "QSPI_CLK", "2": "FLASH_CLK"})
    place(b, "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "U2", "FLASH", (122, 100.385), 180,
          {"4": "GND", "6": "FLASH_CLK", "8": "+3V3"})  # U2.6 at (119.525, 99.75)
    y = 99.75 + (W_SE - 0.25) / 2  # the line's top edge on U1.11's, a 0.25 mm pin
    track(b, "QSPI_CLK", W_SE, (101.4625, y), (103.99, y))
    track(b, "FLASH_CLK", W_SE, (105.01, y), (107, y))
    via(b, (107, y), "FLASH_CLK")
    track(b, "FLASH_CLK", W_SE, (107, y), (117, y), layer=pcbnew.B_Cu)
    via(b, (117, y), "FLASH_CLK")
    track(b, "FLASH_CLK", W_SE, (117, y), (119.525, y))
    track(b, "GND", 0.3, (124.475, 98.48), (124.475, 97.3))
    via(b, (124.475, 97.3))
    track(b, "+3V3", 0.3, (119.525, 102.29), (119.525, 103.5))
    via(b, (119.525, 103.5), "+3V3")
    decoupled(b, (107, 102))
```

  - **BOARDS gains** `"usb2_hs": usb2_hs`, `"usb2_hs_neck": lambda b: usb2_hs(b, neck=True)`, `"usb2_hs_gap": lambda b: usb2_hs(b, gap=True)`, `"usb2_hs_45": lambda b: usb2_hs(b, bend=True)` and `"qspi_clk": qspi_clk`.
- [ ] **Step 4: Generate only the new boards, under A-3's isolation,** in one PowerShell call:

```powershell
$kp = Join-Path (Get-Location) 'build\kicad-profile'; New-Item -ItemType Directory -Force $kp | Out-Null
Get-ChildItem env: | Where-Object { $_.Name -like 'KICAD*' } | ForEach-Object { Remove-Item "env:$($_.Name)" }
if (Test-Path env:TMPDIR) { Remove-Item env:TMPDIR }
$env:APPDATA = $kp; $env:LOCALAPPDATA = $kp  # the script itself points KICAD_*_HOME, TEMP and TMP at $kp
& "<KiCad 9 bin folder>\python.exe" tools/make_fixtures.py tests/fixtures usb2_hs usb2_hs_neck usb2_hs_gap usb2_hs_45 qspi_clk
"exit $LASTEXITCODE"; git status --short tests/fixtures
```

  Expected: `exit 0`, and `git status` lists exactly the ten new files. If any other file changes, stop: the golden pins hash the existing boards. Never start KiCad itself or kicad-cli.
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_board.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_repo.py -q`. Expected: PASS; `test_board.py`'s sweep reads the new boards with no warning. A lint or fit2d failure on a real board (KiCad's round antipads, its fills) stops the task: report the hit and the board for a ruling.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/make_fixtures.py tests/test_fixtures.py tests/test_pads.py tests/test_stackup.py tests/test_gates.py tests/fixtures/usb2_hs* tests/fixtures/qspi_clk.*
git commit -m "test(fixtures): a four-layer USB 2.0 high-speed pair from a micro-B through an ESD array and 22 ohm resistors to a QFN, its neck-down, plane-gap and 45 degree variants, and a QSPI clock through 33 ohms and a layer change, from KiCad's own footprints, each passing the edge lint and fit2d at n 2 (Stage 4 design 5.11)"
graphify update .
```

---

### Task 2 [code]: Schema 3, the interfaces and the GUI's refusal

**Files:**
- Modify: `core/project.py` (the docstring; the names after GATES; `make_si_project` after `make_antenna_project` L144; `_FIELDS_SI` after `_FIELDS_ANTENNA`; `check_project` L298; `load_project` L181); `gui/control.py` (`open_project` L219, `fields` L627-656); `core/messages.py`; `po/*` and the `.mo`.
- Test: `tests/test_project.py` (L28–L35 and L284–L292 change deliberately), `tests/test_gui_control.py`.

**Interfaces:**
- Consumes: `make_project`, `_check`, `_FIELDS`, `_PARTS`, `_reference`; `core.post.si.LOCAL_RISE`.
- Produces, in `core/project.py`:
  - `GATES_SI = {"fit2d_limit": 0.03, "dt_floor": 0.6}`, `SI_F_MAX = 10e9`, `SI_TOLERANCE = 0.1`, `DIELECTRICS = ("lossless", "debye")`, `SI_DIELECTRIC = "lossless"`, `LINE_ROLES = ("measured", "victim")`.
  - `INTERFACES: dict[str, dict]`, each `{"target_ohm", "rise_s", "marker_hz", "pair"}`.
  - `si_interface(name: str, f_max: float | None, target: float | None, paired: bool) -> dict`, returning `{"interface", "f_max_hz", "rise_s", "marker_hz", "target_ohm", "tolerance"}`.
  - `make_si_project(board_path, board_sha256, stackup, classes, lines, pair, others, ports, interface, *, t_max_s, window_s, max_cell_mm, preset=DEFAULT_PRESET, lid_height_mm=None) -> dict`.
  - `check_project` and `load_project` for schema 3; `E_PROJECT_SCHEMA`'s `expected` is `SCHEMA_SI`, the newest it reads.
- `control.open_project` reads an SI project as the problem `("G_SI_LATER", {"path"})` until plan 5; `control.fields` gives an SI project's own defaults.

- [ ] **Step 1: Write the failing tests.** In `tests/test_project.py` (imports gain `INTERFACES`, `make_si_project`, `read_project` and `si_interface`, where missing):
  - `test_schema_mismatch_names_the_file_and_both_versions` takes `"expected": SCHEMA_SI` and `"schema 3" in str(e.value)`; its last two lines load `{"schema": 3}`.
  - `test_schema_3_is_an_si_project_which_this_build_still_refuses` becomes:

```python
def test_schema_3_is_an_si_project_whose_fields_are_checked(tmp_path):  # Stage 4 design 5.1
    assert (SCHEMA_SI, si({"schema": 3}), si({"schema": 2}), antenna({"schema": 3})) == (3, True, False, False)
    p = tmp_path / "project.json"
    p.write_text('{"schema": 3, "kind": "si"}', encoding="utf-8")
    assert load_project(p) == {"schema": 3, "kind": "si"}
    with pytest.raises(KrsError) as e:
        read_project(p)
    assert (e.value.code, e.value.params["field"]) == ("E_PROJECT_FIELD", "board")
```

  - Add:

```python
def si_dict():
    """A schema 3 dict for usb2_hs's pair and victim, as new_si writes it, its parts left out."""
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    lines = [{"role": role, "chain": {"start": s, "end": e, "nets": nets, "series": [], "shunt": []}} for role, s, e, nets in (
        ("measured", "J1.3", "U1.3", ["USB_D+", "MCU_D+"]), ("measured", "J1.2", "U1.2", ["USB_D-", "MCU_D-"]),
        ("victim", "TP1.1", "TP2.1", ["AUX"]))]
    ports = [{"name": f"P{k}", "signal": s, "signal_uuid": "", "layer": "F.Cu", "rule": "plane",
              "reference": {"plane": "In1.Cu"}} for k, s in enumerate(("J1.3", "J1.2", "U1.3", "U1.2", "TP1.1", "TP2.1"), 1)]
    return make_si_project("usb2_hs.kicad_pcb", "0" * 64, b.stackup, classify(b), lines,
                           {"p": "USB_D+", "n": "USB_D-", "by": "rule"}, [], ports,
                           si_interface("usb2-hs", None, None, True), t_max_s=9e-9, window_s=2e-9, max_cell_mm=0.414)


def test_an_si_project_holds_the_design_fields():  # Stage 4 design 5.1, 5.3, 5.4
    d = si_dict()
    assert (d["schema"], d["kind"], d["interface"], d["f_max_hz"], d["rise_s"], d["marker_hz"], d["target_ohm"],
            d["tolerance"]) == (3, "si", "usb2-hs", 10e9, 5e-10, 2.4e8, 90.0, 0.1)
    assert (d["dielectric"], d["t_max_s"], d["window_s"], d["lid"]) == ("lossless", 9e-9, 2e-9, True)
    assert d["gates"] == {"fit2d_limit": 0.03, "dt_floor": 0.6}  # SI's floor (design 5.3, A-43)
    assert d["mesh"] == {"n": 2, "reach_h": 6.0, "max_cell_mm": 0.414} and d["region"] == {"expand_h": 6.0,
                                                                                            "margin_scale": 1.0}
    assert not {"f0_hz", "harmonics", "band_factor", "chain"} & set(d) and check_project(d, Path("p.json")) is d
    assert {k: (v["target_ohm"], v["rise_s"], v["marker_hz"], v["pair"]) for k, v in INTERFACES.items()} == {
        "usb2-hs": (90.0, 5e-10, 2.4e8, True), "100base-tx": (100.0, 3e-9, 62.5e6, True), "se50": (50.0, 1e-9, 133e6, False)}


def test_the_custom_interface_and_the_presets_refusals():  # design 5.1
    c = si_interface("custom", 5e9, 85.0, True)
    assert (c["interface"], c["f_max_hz"], c["target_ohm"], c["tolerance"]) == ("custom", 5e9, 85.0, 0.1)
    assert c["rise_s"] == pytest.approx(2.5e-10) and c["marker_hz"] == pytest.approx(1.4e9)  # 1.25/f_max, 0.35/rise
    for args, code, params in [(("usb2-hs", None, None, False), "E_SI_NEEDS_PAIR", {"interface": "usb2-hs"}),
                               (("se50", None, None, True), "E_SI_NOT_PAIR", {"interface": "se50"}),
                               (("custom", None, 85.0, True), "E_SI_CUSTOM", {}),
                               (("se50", 5e9, None, False), "E_SI_CUSTOM", {})]:
        with pytest.raises(KrsError) as e:
            si_interface(*args)
        assert (e.value.code, e.value.params) == (code, params)


@pytest.mark.parametrize(("change", "field", "expected"), [
    ({"kind": "antenna"}, "kind", "T_EXPECT_SI"),
    ({"interface": "usb3"}, "interface", "T_EXPECT_INTERFACE"),
    ({"rise_s": 1e-10}, "rise_s", "T_EXPECT_RISE"),  # faster than 1.25/f_max, the localising TDR's 125 ps
    ({"dielectric": "kappa"}, "dielectric", "T_EXPECT_DIELECTRIC"),  # never v1's κ (design 3)
    ({"mesh": {"n": 2, "reach_h": 6.0, "max_cell_mm": 0}}, "mesh.max_cell_mm", "T_EXPECT_ABOVE_0_OR_NULL"),
    ({"pair": None}, "pair", "T_EXPECT_SI_PAIR"),  # two measured lines are a pair
    (lambda d: {"lines": d["lines"][::-1]}, "lines", "T_EXPECT_SI_LINES"),  # the measured lines come first
    (lambda d: {"lines": [{**d["lines"][0], "role": "aggressor"}, *d["lines"][1:]]}, "lines[0].role",
     "T_EXPECT_LINE_ROLE"),
    (lambda d: {"ports": d["ports"][1:] + d["ports"][:1]}, "ports", "T_EXPECT_SI_PORTS"),  # se2gmm reads this order
    (lambda d: {"ports": [{**d["ports"][0], "rule": "vertical"}, *d["ports"][1:]]}, "ports[0].rule",
     "T_EXPECT_SI_RULE"),
    (lambda d: {"ports": [{**d["ports"][0], "reference": {"plane": 3}}, *d["ports"][1:]]}, "ports[0].reference",
     "T_EXPECT_SI_REFERENCE")])
def test_an_si_field_out_of_its_range_is_named(change, field, expected):  # design 5.1; Review Focus (ports by hand)
    d = si_dict()
    with pytest.raises(KrsError) as e:
        check_project({**d, **(change(d) if callable(change) else change)}, Path("p.json"))
    assert (e.value.code, e.value.params["field"], e.value.params["expected"]) == ("E_PROJECT_FIELD", field, expected)
```

  In `tests/test_gui_control.py`:

```python
def test_an_si_project_is_refused_until_plan_5(tmp_path):  # Stage 4 plan 2: the window reads f0 and harmonics
    from test_project import si_dict
    p = tmp_path / "project.json"
    save_project(p, si_dict())
    opened = control.open_project(p)
    assert opened.project is None and opened.problem == ("G_SI_LATER", {"path": str(p)})
    assert opened.stored["schema"] == 3  # Advanced still opens it, with an SI project's own defaults
    shown = {f.name: f.default for f in control.fields(opened.stored)}
    assert "kind" not in shown and (shown["gates.dt_floor"], shown["region.expand_h"], shown["lid"],
                                    shown["t_max_s"]) == ("0.6", "6.0", "true", "")
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_project.py tests/test_gui_control.py -q`. Expected: FAIL: the new names (`INTERFACES`, `make_si_project`, `si_interface`) cannot be imported.
- [ ] **Step 3: `core/project.py`.**
  - **The docstring** names schema 3 for an SI project (Stage 4 design 5.1). `SCHEMA_SI`'s comment drops "until Stage 4 plan 2".
  - **The constants,** after GATES, each commented: GATES_SI ("an SI project's: SI's timestep floor 0.6, Stage 4 design 5.3, A-43"), SI_F_MAX ("the presets' band, for the localising TDR, design 5.1"), SI_TOLERANCE, DIELECTRICS, SI_DIELECTRIC ("lossless until gate P4-D sets the default, design 5.3"), LINE_ROLES and:

```python
# Stage 4 design 5.1: each target from a public application note; rise_s the edge the link's driver makes, marker_hz the
# link's Nyquist frequency or its clock; every preset runs to SI_F_MAX
INTERFACES = {
    "usb2-hs": {"target_ohm": 90.0, "rise_s": 500e-12, "marker_hz": 240e6, "pair": True},  # TI SPRAAR7J Table A-1
    "100base-tx": {"target_ohm": 100.0, "rise_s": 3e-9, "marker_hz": 62.5e6, "pair": True},  # TI SNLA387, ANSI X3.263
    "se50": {"target_ohm": 50.0, "rise_s": 1e-9, "marker_hz": 133e6, "pair": False}}  # QSPI, SDIO, SPI, a clock
```

  - **`si_interface`:** docstring "An SI project's interface fields (Stage 4 design 5.1): a preset's at SI_F_MAX, or custom's from `f_max` (Hz) and `target` (Ω), its rise time LOCAL_RISE/f_max, the localising TDR's, and its marker 0.35/that, the rise time's bandwidth; tolerance SI_TOLERANCE. E_SI_CUSTOM unless custom has both `f_max` and `target` and a preset neither; E_SI_NEEDS_PAIR for a pair's preset without `paired`, E_SI_NOT_PAIR for a net's with it." Mark `# ponytail: custom's rise time and marker are derived; project.json holds them for an edit`.
  - **`make_si_project`:** docstring "project.json of an SI project (schema 3, Stage 4 design 5.1) as `new --interface` writes it: make_project's dict without f0_hz, harmonics, band_factor and chain, with schema SCHEMA_SI, `t_max_s`, region {"expand_h": REACH_H, "margin_scale": MARGIN_SCALE} (the protected set's reach, design 5.2), mesh {"n", "reach_h", "max_cell_mm"}, lid true and gates GATES_SI in their places; then kind, the `interface` fields, dielectric SI_DIELECTRIC, `window_s`, `lines` and `pair`." Body as `make_antenna_project`'s: `make_project(..., 0.0, ..., {}, ...)`, the four keys deleted, the overrides set in place, the SI keys appended.
  - **`_FIELDS_SI`:** `_FIELDS` in its order without f0_hz, harmonics, band_factor and chain, with `"mesh"` `{**_FIELDS["mesh"], "max_cell_mm": (None or above 0, "T_EXPECT_ABOVE_0_OR_NULL")}`, `"lid"` `_FLAG`, and `"ports"` v1's with `"rule"` in `(None, "connector", "ic", "copper", "plane")` (T_EXPECT_SI_RULE) and `"reference"` `_reference(v)` or a dict whose only key is `"plane"`, a text (T_EXPECT_SI_REFERENCE); then `"kind"` == "si" (T_EXPECT_SI), `"interface"` in `(*INTERFACES, "custom")` (T_EXPECT_INTERFACE), `"f_max_hz"`, `"rise_s"`, `"marker_hz"`, `"target_ohm"`, `"tolerance"` and `"window_s"` `_ABOVE_0`, `"dielectric"` in DIELECTRICS (T_EXPECT_DIELECTRIC), `"lines"` a list of `{"role": in LINE_ROLES (T_EXPECT_LINE_ROLE), "chain": _FIELDS["chain"]}` (T_EXPECT_SI_LINES), and `"pair"` None or `{"p": text, "n": text, "by": in ("rule", "alias", "given")}` (T_EXPECT_SI_PAIR).
  - **`check_project`:** an SI project checks `_FIELDS_SI`, then raises E_PROJECT_FIELD, in this order: `rise_s` / T_EXPECT_RISE unless `rise_s ≥ LOCAL_RISE / f_max_hz · (1 − 1e-9)`; `lines` / T_EXPECT_SI_LINES unless the roles are 1 or 2 "measured" then 0 to 2 "victim"; `pair` / T_EXPECT_SI_PAIR unless it is None with one measured line, else `[p, n]` is the measured lines' first nets; `ports` / T_EXPECT_SI_PORTS unless the signals are, in order, each measured line's start, each one's end, then each victim's start and end. The docstring says so.
  - **`load_project`:** accepts SCHEMA_SI; its refusal's `expected` is SCHEMA_SI, the newest it reads.
- [ ] **Step 4: `gui/control.py`.**
  - **`open_project`:** inside its `try`, before `pipeline.load`: `if si(load_project(path)): raise KrsError("G_SI_LATER", path=str(path))`, marked `# ponytail: plan 5 opens SI projects; until then the window's project line reads f0 and harmonics`.
  - **`fields`:** for `si(data)`, as for an antenna, "kind" is hidden and the defaults are an SI project's: lid true, region.expand_h REACH_H, gates.dt_floor GATES_SI's; t_max_s and mesh.max_cell_mm have none (`new` derives them from the route). The docstring says so.
- [ ] **Step 5: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| T_EXPECT_SI | the text "si" | o texto "si" |
| T_EXPECT_INTERFACE | usb2-hs, 100base-tx, se50 or custom | usb2-hs, 100base-tx, se50 ou custom |
| T_EXPECT_RISE | a time in s of at least 1.25/f_max_hz, the localising TDR's rise time | um tempo em s de pelo menos 1.25/f_max_hz, o tempo de subida do TDR de localização |
| T_EXPECT_DIELECTRIC | "lossless" or "debye" | "lossless" ou "debye" |
| T_EXPECT_SI_LINES | a list of lines, each with its role and chain: the measured line, or a pair's two, first, then up to two victims | uma lista de linhas, cada uma com seu role e sua chain: a linha medida, ou as duas de um par, primeiro, depois até duas vítimas |
| T_EXPECT_LINE_ROLE | measured or victim | measured ou victim |
| T_EXPECT_SI_PAIR | null for one measured line, or p and n, the first nets of the two measured lines, with by "rule", "alias" or "given" | null para uma linha medida, ou p e n, as primeiras redes das duas linhas medidas, com by "rule", "alias" ou "given" |
| T_EXPECT_SI_PORTS | a list of ports whose signals are the lines' ends in order: each measured line's start, then each one's end, then each victim's start and end | uma lista de portas cujos sinais são as pontas das linhas em ordem: o início de cada linha medida, depois o fim de cada uma, depois o início e o fim de cada vítima |
| T_EXPECT_SI_RULE | connector, ic, copper, plane or null | connector, ic, copper, plane ou null |
| T_EXPECT_SI_REFERENCE | a pad, a point, a plane (its copper layer's name) or null | uma ilha, um ponto, um plano (o nome da camada de cobre dele) ou null |
| E_SI_NEEDS_PAIR | Interface {interface} is a differential pair's: add --pair, or --pair-with REF.PAD:REF.PAD. | A interface {interface} é de um par diferencial: acrescente --pair, ou --pair-with REF.PAD:REF.PAD. |
| E_SI_NOT_PAIR | Interface {interface} is a single-ended net's: leave out --pair and --pair-with, or choose --interface custom. | A interface {interface} é de uma rede single-ended: retire --pair e --pair-with, ou escolha --interface custom. |
| E_SI_CUSTOM | --f-max and --target set the band and the target of --interface custom, which needs both; a preset interface takes neither. | --f-max e --target definem a banda e o alvo de --interface custom, que precisa dos dois; uma interface predefinida não recebe nenhum deles. |
| G_SI_LATER | {path} is a signal-integrity project (schema 3), which this window does not open yet: use the command line, `kicad-rf-studio cost` and `kicad-rf-studio run`. | {path} é um projeto de integridade de sinal (schema 3), que esta janela ainda não abre: use a linha de comando, `kicad-rf-studio cost` e `kicad-rf-studio run`. |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_sexpr.py tests/test_gui.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(project): schema 3 for SI projects, the interface presets with their cited targets, check_project for the lines, the pair and the port order, and the GUI's refusal until Stage 4 plan 5 with Advanced's SI defaults (Stage 4 design 5.1, 5.3)"
graphify update .
```

---

### Task 3 [code]: The pair, the lines and their parts

**Files:** Modify `core/kicad/tracer.py` (`partner_net` and `partner_ends` after `choose_reference`; `trace_chain` L129-175's walk into `_links` and `_walk`; `trace_line` after it), `core/model/parts.py` (`SHUNT_OPEN_OHM`, `role` L58-88, `project_parts` L91-133), `core/messages.py`, `po/*` and the `.mo`. Create `tests/test_si_lines.py`. Test: `tests/test_model_parts.py`.

**Interfaces:**
- Consumes: `_resolve`, `_copper`, `Board.nets`; `values.bypass`, `OPEN_VALUE`.
- Produces:
  - `tracer.partner_net(net: str, nets: Collection[str]) -> tuple[str, str] | None`, the partner and how ("rule" or "alias"); `tracer.partner_ends(board: Board, classes: Classes, start: str, end: str) -> tuple[str, str, str]`, the partner's start pad, end pad and how.
  - `tracer._links(board, classes, antenna=None) -> dict[str, list[tuple[str, Pad, Pad]]]` and `tracer._walk(links, net) -> dict`, `trace_chain`'s own steps, which it now calls; `tracer.trace_line(board: Board, classes: Classes, start: str, end: str) -> Chain`.
  - `parts.SHUNT_OPEN_OHM = 1e3`; `role(kind, value, model, dnp, angle, place, f1, f2, *, bridge: bool = False)`; `project_parts(board, chain, classes, roi, f1, f2, *, antenna=False, si=False)`.

- [ ] **Step 1: Write the failing tests,** `tests/test_si_lines.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from shapely.geometry import box

from kicad_rf_studio.core.kicad import classify
from kicad_rf_studio.core.kicad.tracer import partner_ends, partner_net, trace_line
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import project_parts
from test_antenna_kicad import fp
from test_tracer import part, smd, two

NETS = {"USB_D+", "USB_D-", "D_P_1", "D_N_1", "USB_DP", "USB_DM", "CLKP", "CLKN", "/eth/TX+", "/eth/TX-", "+3V3",
        "VBUS", "A_DP", "A_DN", "A_DM", "usb_dp", "usb_dm"}


def test_kicads_pair_rule_and_the_dp_dm_alias():  # Stage 4 design 5.1; KiCad 10 pcbnew/board.cpp MatchDpSuffix
    assert partner_net("USB_D+", NETS) == ("USB_D-", "rule") and partner_net("USB_D-", NETS) == ("USB_D+", "rule")
    assert partner_net("D_P_1", NETS) == ("D_N_1", "rule")  # the digits and underscores after the P stay
    assert partner_net("/eth/TX+", NETS) == ("/eth/TX-", "rule") and partner_net("CLKN", NETS) == ("CLKP", "rule")
    assert partner_net("USB_DP", NETS) == ("USB_DM", "alias") and partner_net("USB_DM", NETS) == ("USB_DP", "alias")
    assert partner_net("A_DP", NETS) == ("A_DN", "rule")  # KiCad's complement first, when it is a net of the board
    assert [partner_net(n, NETS) for n in ("+3V3", "VBUS", "usb_dp")] == [None] * 3  # KiCad's P and N are upper case
    assert partner_net("USB_D+", {"USB_D+"}) is None  # no complement on the board


def board_of(mini_board, *extra):
    return mini_board(part("J1", smd(1, "USB_D+"), smd(2, "USB_D-", x=2), smd(3, "GND", x=4)) +
                      part("U1", smd(1, "MCU_D+"), smd(2, "MCU_D-", x=2), smd(3, "GND", x=4), at="20 0") + "".join(extra))


def test_the_partner_is_the_complements_one_pad_on_each_end_footprint(mini_board):  # design 5.1
    b = board_of(mini_board)
    assert partner_ends(b, classify(b), "J1.1", "U1.1") == ("J1.2", "U1.2", "rule")


def test_a_partner_with_two_pads_or_none_is_refused(mini_board):  # design 5.1
    b = mini_board(part("J2", smd("A6", "USB_D+"), smd("B6", "USB_D+", x=1), smd("A7", "USB_D-", x=2),
                        smd("B7", "USB_D-", x=3)) + part("U1", smd(1, "MCU_D+"), smd(2, "MCU_D-", x=2), at="20 0"))
    with pytest.raises(KrsError) as e:  # a USB-C receptacle's two D- pads
        partner_ends(b, classify(b), "J2.A6", "U1.1")
    assert (e.value.code, e.value.params) == ("E_SI_PARTNER", {"net": "USB_D+", "pad": "J2.A6", "ref": "J2",
                                                               "partner": "USB_D-", "pads": "J2.A7, J2.B7"})
    b = mini_board(part("J3", smd(1, "SIG")) + part("U3", smd(1, "SIG"), at="20 0"))
    with pytest.raises(KrsError) as e:
        partner_ends(b, classify(b), "J3.1", "U3.1")
    assert (e.value.code, e.value.params) == ("E_SI_PARTNER", {"net": "SIG", "pad": "J3.1", "ref": "J3",
                                                               "partner": "T_NONE", "pads": "T_NONE"})


def test_a_line_through_a_part_of_three_or_more_pads_is_refused(mini_board):  # design 5.1; Review Focus 5
    cmc = part("L1", smd(1, "A"), smd(2, "B", x=2), smd(3, "A2", y=2), smd(4, "B2", x=2, y=2), at="10 0")
    b = mini_board(part("J1", smd(1, "A")) + cmc + part("U1", smd(1, "B"), at="20 0"))
    with pytest.raises(KrsError) as e:
        trace_line(b, classify(b), "J1.1", "U1.1")
    assert (e.value.code, e.value.params) == ("E_SI_THROUGH_PART", {"start": "J1.1", "end": "U1.1", "refs": "L1"})
    b = mini_board(part("J1", smd(1, "A")) + part("U1", smd(1, "B"), at="20 0"))
    with pytest.raises(KrsError) as e:
        trace_line(b, classify(b), "J1.1", "U1.1")
    assert e.value.code == "E_NO_CHAIN"  # nothing on the way: v1's refusal
    esd = part("U2", smd(1, "A"), smd(2, "GND", x=1), smd(3, "A2", x=2))  # pads on the line: copper, no refusal
    b = mini_board(part("J1", smd(1, "A")) + esd + two("R1", "A", "B") + part("U1", smd(1, "B"), at="20 0"))
    assert [p.ref for p in trace_line(b, classify(b), "J1.1", "U1.1").series] == ["R1"]


def test_an_si_lines_parts_are_ports_but_its_pull_ups(mini_board):  # design 5.1, 5.3 (A-27); Review Focus (pull-up)
    r = "Resistor_SMD:R_0402_1005Metric"
    b = mini_board(part("J1", smd(1, "A")) + part("U1", smd(1, "B"), at="20 0") +
                   "".join(fp(ref, r, smd(1, n1), smd(2, n2, x=2), value=v) for ref, n1, n2, v in (
                       ("R1", "A", "B", "22"), ("R5", "A", "+3V3", "1.5k"), ("R6", "B", "GND", "100"),
                       ("R7", "A", "C", "10k"))) +
                   part("R8", smd(1, "A"), smd(2, "GND", x=2), dnp=True) +  # a DNP placeholder: a port, value open
                   fp("C9", "Capacitor_SMD:C_0402_1005Metric", smd(1, "+3V3"), smd(2, "GND", x=2), value="100nF"))
    c = classify(b)
    series, shunt, others, notes = project_parts(b, trace_line(b, c, "J1.1", "U1.1"), c, box(-50, -50, 50, 50),
                                                 0.0, 10e9, si=True)
    assert [(q["ref"], q["role"]) for q in series] == [("R1", "port")]
    assert [(q["ref"], q["role"], q["value"]) for q in shunt] == [("R5", "open", "1.5k"), ("R6", "port", "100"),
                                                                  ("R7", "port", "10k"), ("R8", "port", "open")]
    assert [(q["ref"], q["role"]) for q in others] == [("C9", "copper")]  # A-27's rule at f_max/2
    assert ("I_SI_SHUNT_OPEN", {"refs": "R5"}) in notes and "W_VALUE_UNREADABLE" not in dict(notes)
```

  In `tests/test_model_parts.py`:

```python
@pytest.mark.parametrize(("kind", "value", "expected"), [
    ("C", 100e-9, "copper"),   # a decoupling C: 0.32 mΩ less 15.7 Ω of ESL at 5 GHz, f_max/2
    ("C", 1.5e-12, "copper"),  # 21.2 − 15.7 = 5.5 Ω ≤ Z0/5
    ("C", 1e-12, "open"),      # 16.1 Ω, and its SRF of 7.1 GHz under 3·f_max
    ("R", 1e3, "grid"),        # v1's: SRF 41 GHz
    ("L", 10e-9, "port")])     # v1's: an inductor in the region is a port (no choke from DC)
def test_an_si_projects_other_parts_keep_v1s_roles_and_bridge_a_decoupling_c(kind, value, expected):  # design 5.1
    assert role(kind, value, C0402, False, 0, "other", 0.0, 10e9, bridge=True) == expected
    assert role("C", 100e-9, C0402, False, 0, "other", 0.0, 10e9) == "open"  # v1's, without the bridge
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_si_lines.py "tests/test_model_parts.py::test_an_si_projects_other_parts_keep_v1s_roles_and_bridge_a_decoupling_c" -q`. Expected: FAIL with `cannot import name 'partner_ends'`.
- [ ] **Step 3: The pair.**
  - **`partner_net`:** docstring "The partner of `net` among the board's `nets` (Stage 4 design 5.1), and how: KiCad's own rule (BOARD::MatchDpSuffix, KiCad 10 pcbnew/board.cpp): from the name's end, past digits and underscores, a + or -, or an upper-case P or N, swapped ("rule"); else the DP/DM alias of a name whose last letters there are DP or DM ("alias"); None when neither complement is a net of the board." The alias is `_ALIAS = re.compile(r"(.*D)([PM])([0-9_]*)")` (fullmatch), commented "D+ and D- as DP and DM, which KiCad's rule pairs with DN". The test pins every branch; import `Collection` from `collections.abc`.
  - **`partner_ends`:** docstring "The partner's two ends (Stage 4 design 5.1): for each of pads `start` and `end`, its net's partner (partner_net, among board.nets) and that net's one copper pad on the same footprint; and how, "alias" when either end took the alias, else "rule". E_SI_PARTNER {net, pad, ref, partner, pads}, naming --pair-with, when a net has no partner (partner and pads T_NONE) or its footprint holds not exactly one pad of it (pads joined by ", ", T_NONE for none)." Each end through `_resolve`, so its refusals stand.
- [ ] **Step 4: The lines.**
  - **A refactor first:** `trace_chain`'s parts-and-links block becomes `_links(board, classes, antenna=None)` and its breadth-first walk `_walk(links, net) -> dict` (net → (from net, ref, near pad, far pad), the start net → None); `trace_chain` calls both, unchanged otherwise. Run `.venv/Scripts/python -m pytest tests/test_tracer.py tests/test_golden_v1.py tests/test_golden_antenna.py -q`: PASS before the SI path exists.
  - **`trace_line`:** docstring "An SI line from pad `start` to pad `end` (Stage 4 design 5.1): trace_chain's chain. Where it raises E_NO_CHAIN and a footprint of three or more copper pads with a net, no connector or shield, has a pad on a net the walk reaches from `start` and another on one it reaches from `end`, E_SI_THROUGH_PART {start, end, refs} names those footprints instead: the line runs through a part the model cannot hold." Mark `# ponytail: a part of three or more pads is found by the nets it bridges, not by geometry; a choke whose other side the walk cannot reach (a GND net) still reads E_NO_CHAIN`.
- [ ] **Step 5: The parts.**
  - **`role`'s `bridge`:** the antenna's capacitor rule applies when `bridge or place in ("board", "far")`; the docstring names the SI parts off a line, "other" with `bridge` (Stage 4 design 5.1: A-27's rule at the pulse's centre, f_max/2 with f1 0).
  - **`project_parts`'s `si`:** every chain part is a port as with `antenna` (a curve port off a multiple of 90°, a DNP one's value OPEN_VALUE), but a shunt R whose part_value is SHUNT_OPEN_OHM or more and whose other net (its `nets[1]`) is a GND or power net, which is OPEN; the others are v1's "other" with `bridge=True`. W_VALUE_UNREADABLE's `bypassed` exemption holds `if antenna or si`. The notes add `I_SI_SHUNT_OPEN {refs}` for the shunts left open, after W_PART_OPEN. `SHUNT_OPEN_OHM` is commented "design 5.1: a pull-up of 1 kΩ or more barely loads a fast line, and each port costs a run". Mark `# ponytail: with f1 0 no inductor is a choke (|Z| at DC is its ESR), so an L off the lines in the region is a part port and a run; a choke test from the marker up if real boards meet one`.
- [ ] **Step 6: The messages:**

| Code | English | pt-BR |
|---|---|---|
| E_SI_PARTNER | The partner of net {net} (pad {pad}) on {ref} is {partner} by KiCad's pair rule or the DP/DM alias, with pads {pads} on {ref}, where one is needed. Name the partner's two ends with --pair-with REF.PAD:REF.PAD. | O par da rede {net} (ilha {pad}) em {ref} é {partner} pela regra de pares do KiCad ou pelo apelido DP/DM, com ilhas {pads} em {ref}, onde uma é necessária. Indique as duas pontas do par com --pair-with REF.PAD:REF.PAD. |
| E_SI_THROUGH_PART | The line from {start} to {end} runs through {refs}, a part with three or more pads (a common-mode choke, say), which this simulation cannot hold: measure each side of it as a project of its own, ending at its pads. | A linha de {start} a {end} passa por {refs}, um componente com três ou mais ilhas (um choke de modo comum, por exemplo), que esta simulação não comporta: meça cada lado dele como um projeto próprio, terminando nas ilhas dele. |
| I_SI_SHUNT_OPEN | Left open: {refs}, shunt resistors of 1 kΩ or more to a supply or to ground (pull-ups), which barely load a fast line; each would cost a run as a part port. Make one a port in project.json if it matters. | Deixados em aberto: {refs}, resistores shunt de 1 kΩ ou mais para uma alimentação ou para o GND (pull-ups), que quase não carregam uma linha rápida; cada um custaria uma execução como porta de componente. Faça de um deles uma porta em project.json se isso importar. |

- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_tracer.py tests/test_model_parts.py tests/test_cli_new.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(tracer, parts): a differential pair's partner by KiCad's MatchDpSuffix, ported, with a DP/DM alias, and an SI line traced from pad to pad, refused through a part of three or more pads, its parts all ports but a pull-up of 1 kohm or more, and the parts off it bridged by A-27's capacitor rule at f_max/2 (Stage 4 design 5.1)"
graphify update .
```

---

### Task 4 [code]: The SI end and the route

**Files:**
- Modify: `core/geometry/region.py` (`build_region` L69-104's `layers`); `core/geometry/sections.py` (`cross_section` L201-232's `h`; `line_layers`, `route_length`, `eps_eff_2d` after it); `core/model/ports.py` (`_apart_axis`, which `place` L184-287 uses; `clear_between` and `si_reference` after `plane_under`); `core/model/spec.py` (`si_t_max` L85-88); `core/messages.py`, `po/*` and the `.mo`.
- Test: `tests/test_geometry_region.py`, `tests/test_geometry_sections.py`, `tests/test_model_ports.py`, `tests/test_model_spec.py`.

**Interfaces:**
- Consumes: `copper_pieces`, `sections`, `cs2d.solve`, `plane_under`, `_reference` (ports), `round_trip`, `stop_window`, `FLAT_S`, `WINDOW_S`.
- Produces:
  - `build_region(board, chain, ports, zs, f_max, expand_h=3.0, margin_scale=1.0, layers: Iterable[str] = ())`: the ROI grows by `expand_h · substrate_h(zs, layers)`.
  - `cross_section(sec, pieces, zs, mask, mode, dz0=None, box_h=BOX_H, h: float | None = None)`: the box is `box_h · h` past the line and the stack, `h` None for `substrate_h(zs)`.
  - `sections.line_layers(board, nets) -> tuple[str, ...]`, `route_length(board, nets) -> float` (mm) and `eps_eff_2d(board, nets, pieces, zs) -> float | None`.
  - `ports._apart_axis(s: tuple, r: tuple) -> int | None`; `ports.clear_between(sig: BaseGeometry, ref: BaseGeometry, pieces: list[Piece], layer: str, nets: Collection[str]) -> bool`; `ports.si_reference(board, classes, pieces, zs, name: str, signal: str, ref: dict | None, reach: float) -> dict`.
  - `spec.si_t_max(f_max, round_trip_s)`: at least `2·t0 + window_s + flat_s + 1 ns`, rounded up to a whole ns.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_geometry_region.py`:

```python
def test_an_si_region_grows_by_its_lines_substrate():  # Stage 4 design 5.3; Review Focus 4
    b, p = load_fixture_project("coupon_ms")
    top, line = (build_region(b, chain_of(p), p["ports"], SIX, f_max(p), 6.0, layers=layers).roi.bounds
                 for layers in ((), ("In3.Cu",)))
    assert line[1] - top[1] == pytest.approx(6 * (0.2 - 0.15))  # 6 × the stripline's 0.15 mm, not the top's 0.2 mm
```

  - In `tests/test_geometry_sections.py` (imports gain `line_layers`, `route_length` and `eps_eff_2d`):

```python
def test_an_si_lines_layers_route_length_and_2d_eps_eff():  # Stage 4 design 5.3, 5.4; replica-checked numbers
    usb, qspi = (load_board(FIX / f"{n}.kicad_pcb") for n in ("usb2_hs", "qspi_clk"))
    legs, clock = ("USB_D+", "MCU_D+"), ("QSPI_CLK", "FLASH_CLK")
    assert (line_layers(usb, legs), line_layers(qspi, clock), line_layers(usb, ("NONE",))) == (
        ("F.Cu",), ("F.Cu", "B.Cu"), ())
    assert (route_length(usb, legs), route_length(qspi, clock)) == (pytest.approx(30.405), pytest.approx(17.0425))
    zs = zstack(usb.stackup, usb.copper_layers)
    pieces, _ = copper_pieces(usb, box(94, -106, 134, -94), {s.copper: round(s.z1 - s.z0, 6) for s in zs if s.copper})
    nets = ("USB_D+", "MCU_D+", "USB_D-", "MCU_D-", "AUX")
    assert eps_eff_2d(usb, nets, pieces, zs) == pytest.approx(3.276, abs=1e-3)  # the 0.6 mm run through U2's pads
    assert eps_eff_2d(usb, ("NONE",), pieces, zs) is None
    sec = sections(usb, ("AUX",), pieces)[0][0]
    wide, narrow = (cross_section(sec, pieces, zs, None, "none", h=h).box for h in (None, 0.1))
    assert (wide[1] - wide[0], narrow[1] - narrow[0]) == (pytest.approx(0.2 + 4.0), pytest.approx(0.2 + 2.0))
```

  - In `tests/test_model_ports.py` (imports gain `clear_between`, `si_reference`, `classify` and `load_board` from core.kicad, `copper_pieces` and `zstack`):

```python
def test_an_si_end_reaches_a_reference_only_across_clear_copper():  # Stage 4 design 5.5; Review Focus 2
    sig, gnd, mid = box(0, 0, 0.4, 1.35), box(1.3, 0, 1.7, 1.35), box(0.65, 0, 1.05, 1.35)  # micro-B D+, GND, ID
    pieces = [Piece("F.Cu", "D+", sig, True), Piece("F.Cu", "GND", gnd, True)]
    assert clear_between(sig, gnd, pieces, "F.Cu", {"D+", "GND"})
    assert not clear_between(sig, gnd, [*pieces, Piece("F.Cu", "", mid, True)], "F.Cu", {"D+", "GND"})  # the ID pad
    assert clear_between(sig, gnd, [*pieces, Piece("In1.Cu", "", mid, True)], "F.Cu", {"D+", "GND"})  # another layer
    assert not clear_between(sig, box(1, 2, 2, 3), pieces, "F.Cu", {"D+", "GND"})  # apart both ways: no box


def test_an_si_ends_reference_is_v1s_or_the_plane_under_its_pad():  # Stage 4 design 5.5; Review Focus 2
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    c, zs = classify(b), zstack(b.stackup, b.copper_layers)
    pieces, _ = copper_pieces(b, box(94, -106, 134, -94), {s.copper: round(s.z1 - s.z0, 6) for s in zs if s.copper})
    pad = {n: next(p for p in b.pads(n) if p.layers) for n in ("J1.5", "U1.17")}
    j15, u17 = ({"pad": n, "uuid": pad[n].uuid} for n in ("J1.5", "U1.17"))
    assert si_reference(b, c, pieces, zs, "P1", "J1.3", j15, 1.2) == {"plane": "In1.Cu"}  # J1.4 lies between
    assert si_reference(b, c, pieces, zs, "P3", "U1.3", u17, 1.2) == u17  # 0.2 mm across clear copper
    far = {"point": [102.521, 100.183], "layer": "F.Cu"}  # TP1.1's nearest ground copper, 5 mm off
    assert si_reference(b, c, pieces, zs, "P5", "TP1.1", far, 1.2) == {"plane": "In1.Cu"}  # never E_REFERENCE_POINT
    with pytest.raises(KrsError) as e:
        si_reference(b, c, [pc for pc in pieces if pc.layer == "F.Cu"], zs, "P5", "TP1.1", far, 1.2)  # no plane
    assert (e.value.code, e.value.params) == ("E_SI_NO_REFERENCE", {"pad": "TP1.1", "layer": "F.Cu", "reach_mm": "1.2"})
```

  - In `tests/test_model_spec.py` (imports gain `stop_rule` from stoprule and `far_end` from `test_stoprule`):

```python
def test_a_short_routes_t_max_lets_a_held_level_end_flat():  # plan 1's open issue 4; Review Focus (short route)
    for length in (17.0, 31.0):  # the fixtures' routes; a 1 % level the DC pulse leaves held on port 1
        rt = round_trip(length, 3.3)
        t_max = si_t_max(10e9, rt)
        v = stop_rule(far_end(rt / 2, offset=1e-2, t_end=t_max), 0, "normal", dc_pulse(10e9, t_max, stop_window(rt)))
        assert (t_max, v.kind) == (9e-9, "flat")  # flat near 7.4 ns: the 2 ns window, then 5 ns flat, then settled
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest "tests/test_geometry_region.py::test_an_si_region_grows_by_its_lines_substrate" "tests/test_geometry_sections.py::test_an_si_lines_layers_route_length_and_2d_eps_eff" "tests/test_model_ports.py::test_an_si_end_reaches_a_reference_only_across_clear_copper" "tests/test_model_ports.py::test_an_si_ends_reference_is_v1s_or_the_plane_under_its_pad" "tests/test_model_spec.py::test_a_short_routes_t_max_lets_a_held_level_end_flat" -q`. Expected: FAIL: `build_region` takes no `layers`, the new names cannot be imported, and `si_t_max` gives 4 or 5 ns for these routes, which end with no verdict.
- [ ] **Step 3: The region and the sections.**
  - **`build_region`'s `layers`:** `grow = expand_h * substrate_h(zs, layers)`; with none, today's top layer. The docstring says so.
  - **`cross_section`'s `h`:** `m = box_h * (substrate_h(zs) if h is None else h)`; the docstring adds "an SI section's own layer's substrate (`substrate_h(zs, (sec.layer,))`), which a B.Cu or inner line needs; fit2d keeps the default, its two solves sharing the box".
  - **`line_layers(board, nets)`:** the copper layers of `nets`' tracks, in `board.copper_layers`' order; `()` with none, so substrate_h keeps the top layer's.
  - **`route_length(board, nets)`:** the centre-line length, in mm, of `nets`' tracks (an arc by `arc_points`), stubs included. Mark `# ponytail: every track of the line's nets, a stub too, and no via barrel: a longer route, a longer T_max`.
  - **`eps_eff_2d(board, nets, pieces, zs)`:** the largest εeff of `sections(board, nets, pieces)[0]`, each `solve(cross_section(s, pieces, zs, None, "none", h=substrate_h(zs, (s.layer,))))` on cs2d's own grid, a ShortError skipped; None with none. Mark `# ponytail: without the mask, which raises a 0.3 mm line's εeff by about 8 %: max_cell about 4 % coarser than λ/40 on the coated line and the round trip about 4 % short; the widest section sets it (the 0.6 mm run through an ESD array's pads)`.
- [ ] **Step 4: The SI end, in `core/model/ports.py`.**
  - **`_apart_axis(s, r)`:** "The in-plane axis (0 for x, 1 for y) along which the bounds `s` and `r` are apart while their spans across it overlap; None when they are apart on both axes or neither." `place` takes its axis from it (its E_PORT_SPANS on None), so the two can never disagree; v1's ports are unchanged.
  - **`clear_between`:** docstring "Whether a horizontal port's box between `sig` and `ref` (place's: along _apart_axis, across their spans' overlap) holds no copper of `layer` but of `nets`, an SI end's test (Stage 4 design 5.5): a pad between them, an unconnected one too, would leave the box no copper-free run (E_PORT_BOX). False when _apart_axis is None." A piece blocks when its intersection with the box has an area.
  - **`si_reference`:** docstring "An SI end's reference as project.json keeps it (Stage 4 design 5.5): `ref`, v1's choice (a pad or a point), when its copper (_reference, for port `name`) lies within `reach` mm of pad `signal` and clear_between holds for them with the signal's and the ground nets; else {"plane": layer}, plane_under the pad with the ground and power nets; E_SI_NO_REFERENCE {pad, layer, reach_mm (:g)} when neither." The distance is checked first, on the pad's or the point's raw copper, so a far point never meets `_reference`'s E_REFERENCE_POINT. Mark `# ponytail: v1's first choice only; a blocked ground pad does not fall back to the next one (choose_reference's rank), and a pair's two ends on one footprint may take different kinds`.
- [ ] **Step 5: `si_t_max`.** Also at least `math.ceil((2·t0 + w + FLAT_S + (w − WINDOW_S) + 1e-9) · 1e9) / 1e9`, t0 = 9/(2π·f_max) and w = stop_window(round_trip_s): the pulse, the residual's window, which holds the pulse's 0 dB peak, the flat window dc_pulse writes, and 1 ns to settle. Its docstring adds "and at least that, so that a level held on a short route ends flat, not at T_max (plan 1's open issue 4): 9 ns at 10 GHz with the 2 ns window, where plan 1's 10 ns (100 mm) and 25 ns (300 mm) stand". `stop_window`, `FLAT_S` and `WINDOW_S` join spec.py's import from stoprule.
- [ ] **Step 6: The message:**

| Code | English | pt-BR |
|---|---|---|
| E_SI_NO_REFERENCE | Pad {pad} has no ground copper on {layer} within {reach_mm} mm that a port can reach across clear copper, and no ground or power plane under it, so its port has no reference. Add ground copper beside the pad or a plane under it in KiCad, or end the line at another pad. | A ilha {pad} não tem cobre de GND em {layer} a até {reach_mm} mm que uma porta alcance sem cruzar outro cobre, nem um plano de GND ou de alimentação abaixo dela, então a porta dela não tem referência. Acrescente cobre de GND ao lado da ilha ou um plano abaixo dela no KiCad, ou termine a linha em outra ilha. |

- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_geometry_region.py tests/test_geometry_sections.py tests/test_model_ports.py tests/test_model_spec.py tests/test_stoprule.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_sexpr.py -q`. Expected: PASS; plan 1's `si_t_max` asserts (10 and 25 ns) unchanged.
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(geometry, ports, spec): an SI line's layers, route length and 2D eps_eff, the region by its own dielectric, an SI end's reference across clear copper or the plane under it, and a T_max that lets a short route's held level end flat (Stage 4 design 5.3-5.5)"
graphify update .
```

---

### Task 5 [code]: `new --interface`

**Files:**
- Modify: `cli.py` (`_head_notes`, which `new` L135-188 and `new_antenna` L191-254 now call; `_ends`; `_port_note`; `new_si` after `new_antenna`; `_new` L257-268; `_parser` L328); `core/messages.py` (new codes; E_NEW_KIND's text); `po/*` and the `.mo`.
- Create: `tests/test_cli_si.py`. Test: `tests/test_cli_new.py` and `tests/test_cli_antenna.py` (usage cases).

**Interfaces:**
- Consumes: Tasks 2–4; `_load`, `_port`, `_write`, `_stackup_note`, `_part_note`; `copper_pieces`, `find_lid`, `si_max_cell`, `round_trip`, `stop_window`, `LOCAL_RISE`.
- Produces:
  - `cli.new_si(board, start, end, interface, *, pair=False, pair_with=None, victims=(), f_max=None, target=None, preset=DEFAULT_PRESET, stackup=None, lid_height=None, output=None) -> tuple[Path, list[tuple[str, dict]]]`.
  - `tests/test_cli_si.py`: `FIX`, `USB`, `QSPI`, `si_args(board: Path) -> tuple[tuple, dict]` and `si_project(folder: Path, board: Path = USB, **kw) -> Path`, which later tasks and `tools/golden_si.py` import.

- [ ] **Step 1: Write the failing tests,** `tests/test_cli_si.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pytest

from kicad_rf_studio import cli
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.project import parts, read_project
from test_tracer import part, smd, track

FIX = Path(__file__).parent / "fixtures"
USB, QSPI = FIX / "usb2_hs.kicad_pcb", FIX / "qspi_clk.kicad_pcb"


def si_args(board: Path) -> tuple[tuple, dict]:
    """new_si's arguments for a fixture: a usb2_hs board's pair from J1.3 to U1.3 with the victim TP1.1:TP2.1, at
    usb2-hs; qspi_clk's net from U1.11 to U2.6, at se50."""
    if board.stem.startswith("usb2_hs"):
        return ("J1.3", "U1.3", "usb2-hs"), {"pair": True, "victims": [("TP1.1", "TP2.1")]}
    return ("U1.11", "U2.6", "se50"), {}


def si_project(folder: Path, board: Path = USB, **kw) -> Path:
    """project.json of a fixture as new_si writes it into `folder` (si_args)."""
    args, given = si_args(board)
    return cli.new_si(board, *args, **{**given, **kw}, output=folder)[0]


def test_new_interface_writes_an_si_project(tmp_path, capsys):  # design 5.1, 5.4, 5.5; Review Focus 2
    assert main(["new", str(USB), "--start", "J1.3", "--end", "U1.3", "--interface", "usb2-hs", "--pair",
                 "--victim", "TP1.1:TP2.1", "-o", str(tmp_path / "p")]) == 0
    d = read_project(tmp_path / "p" / "project.json")
    assert (d["schema"], d["kind"], d["interface"], d["dielectric"]) == (3, "si", "usb2-hs", "lossless")
    assert [(x["role"], x["chain"]["start"], x["chain"]["end"], x["chain"]["nets"]) for x in d["lines"]] == [
        ("measured", "J1.3", "U1.3", ["USB_D+", "MCU_D+"]), ("measured", "J1.2", "U1.2", ["USB_D-", "MCU_D-"]),
        ("victim", "TP1.1", "TP2.1", ["AUX"])]
    assert d["pair"] == {"p": "USB_D+", "n": "USB_D-", "by": "rule"}
    assert [(p["name"], p["signal"], p["rule"]) for p in d["ports"]] == [
        ("P1", "J1.3", "plane"), ("P2", "J1.2", "plane"), ("P3", "U1.3", "ic"), ("P4", "U1.2", "ic"),
        ("P5", "TP1.1", "plane"), ("P6", "TP2.1", "plane")]  # J1's ground pin lies past its ID pin: vertical
    assert d["ports"][0]["reference"] == {"plane": "In1.Cu"} and d["ports"][2]["reference"]["pad"] == "U1.17"
    assert [(q["ref"], q["role"]) for x in d["lines"] for q in x["chain"]["series"]] == [("R1", "port"), ("R2", "port")]
    assert [(q["ref"], q["role"]) for q in d["others"]] == [("C1", "copper")]
    assert (d["t_max_s"], d["window_s"], d["region"]["expand_h"]) == (9e-9, 2e-9, 6.0)  # 30.405 mm: the T_max floor
    assert d["mesh"]["max_cell_mm"] == pytest.approx(0.4141, abs=5e-4)  # λ/40 at 10 GHz, the 2D εeff 3.28
    out = capsys.readouterr().out
    for line in (render("I_SI_PAIR", p="USB_D+", n="USB_D-", how="T_PAIR_RULE"),
                 render("I_SI_INTERFACE", interface="usb2-hs", target="90", kind="T_DIFFERENTIAL", tolerance_pct="10",
                        rise_ps="500", marker_mhz="240", f_max_ghz="10", local_ps="125"),
                 render("I_PORT_PLANE", name="P1", signal="J1.3", layer="In1.Cu"),
                 render("I_SI_VICTIM", start="TP1.1", end="TP2.1", net="AUX"),
                 render("I_SI_DEFAULTS", preset="normal", t_max_ns="9", window_ns="2", mesh_n=2, max_cell_mm="0.414",
                        eeff="3.28", dielectric="lossless", dt_floor="0.6", reach_h="6", reach_mm="1.2")):
        assert line in out


def test_new_interface_on_the_qspi_clock(tmp_path):  # design 5.1, 5.11; Review Focus 1
    pj, notes = cli.new_si(QSPI, "U1.11", "U2.6", "se50", output=tmp_path / "q")
    d = read_project(pj)
    assert (d["pair"], [x["role"] for x in d["lines"]], d["target_ohm"], d["t_max_s"]) == (None, ["measured"], 50.0, 9e-9)
    assert [(p["signal"], p["rule"]) for p in d["ports"]] == [("U1.11", "ic"), ("U2.6", "plane")]
    assert d["lines"][0]["chain"]["shunt"] == []  # U1 has three netted pads: no part across P1's own pads
    assert [(q["ref"], q["role"]) for q in d["others"]] == [("C1", "copper")]  # in the ROI U1.17's reference widens
    assert "W_SI_LONG_PORT" not in [c for c, _ in notes]


def test_the_partner_given_by_pair_with(tmp_path):  # design 5.1
    d = read_project(cli.new_si(USB, "J1.3", "U1.3", "usb2-hs", pair_with=("J1.2", "U1.2"), output=tmp_path / "w")[0])
    assert d["pair"]["by"] == "given" and [p["signal"] for p in d["ports"]] == ["J1.3", "J1.2", "U1.3", "U1.2"]


def test_a_line_on_a_net_another_line_holds_is_refused(tmp_path):  # the lines ruling: no third end on a line
    for kw in ({"pair_with": ("J1.3", "U1.3")}, {"pair": True, "victims": [("J1.2", "U1.2")]}):
        with pytest.raises(KrsError) as e:
            cli.new_si(USB, "J1.3", "U1.3", "usb2-hs", output=tmp_path / "s", **kw)
        assert e.value.code == "E_SI_LINE_SHARED" and not (tmp_path / "s").exists()
    assert e.value.params == {"start": "J1.2", "end": "U1.2", "net": "USB_D-"}


def test_a_part_on_both_legs_is_stored_once(mini_board_file, tmp_path):  # the lines ruling: kept by the first
    def ends(ref, at):  # D+, D- and a ground pad each side of them, nothing between a pad and its ground
        return part(ref, smd(1, "D+"), smd(2, "D-", y=2), smd(3, "GND", y=-2), smd(4, "GND", y=4), at=at)
    board = mini_board_file(ends("J1", "0 0") + ends("U1", "20 0") + part("R9", smd(1, "D+"), smd(2, "D-", y=2),
                                                                         at="10 0") +
                            track("F.Cu", "D+", 0, 0, 20, 0) + track("F.Cu", "D-", 0, 2, 20, 2))
    d = read_project(cli.new_si(board, "J1.1", "U1.1", "custom", pair=True, f_max=5e9, target=100.0,
                                stackup="kicad-default", output=tmp_path / "r")[0])
    assert [[q["ref"] for q in x["chain"]["shunt"]] for x in d["lines"]] == [["R9"], []] and list(parts(d)) == ["R9"]


def test_a_long_port_is_warned(tmp_path):  # plan 1's open issue 2; Review Focus 2
    _, notes = cli.new_si(QSPI, "U1.11", "U2.6", "custom", f_max=100e9, target=50.0, output=tmp_path / "t")
    assert [(p["name"], p["length_mm"], p["limit_mm"]) for c, p in notes if c == "W_SI_LONG_PORT"] == [
        ("P1", "0.200", "0.071"), ("P2", "0.200", "0.071")]  # U1.11 to U1.17 across, U2.6 down to In1.Cu


def mini(mini_board_file, victim=""):
    line = part("A1", smd(1, "SIG")) + part("A2", smd(1, "SIG"), at="10 0") + track("F.Cu", "SIG", 0, 0, 10, 0)
    return mini_board_file(line + victim)


def test_an_end_with_no_reference_and_no_plane_is_refused(mini_board_file, tmp_path):  # design 5.5; RF 2
    with pytest.raises(KrsError) as e:
        cli.new_si(mini(mini_board_file), "A1.1", "A2.1", "se50", stackup="kicad-default", output=tmp_path / "p")
    assert (e.value.code, e.value.params) == ("E_SI_NO_REFERENCE", {"pad": "A1.1", "layer": "F.Cu", "reach_mm": "4.26"})
    assert not (tmp_path / "p").exists()


def test_a_victim_outside_the_measured_lines_region_is_refused(mini_board_file, tmp_path):  # design 5.1
    victim = part("B1", smd(1, "V"), at="0 30") + part("B2", smd(1, "V"), at="10 30") + track("F.Cu", "V", 0, 30, 10, 30)
    with pytest.raises(KrsError) as e:
        cli.new_si(mini(mini_board_file, victim), "A1.1", "A2.1", "se50", victims=[("B1.1", "B2.1")],
                   stackup="kicad-default", output=tmp_path / "p")
    assert (e.value.code, e.value.params) == ("E_SI_VICTIM_OUTSIDE", {"victim": "B1.1:B2.1", "pad": "B1.1",
                                                                      "reach_mm": "4.26"})
    with pytest.raises(KrsError) as e:
        cli.new_si(USB, "J1.3", "U1.3", "usb2-hs", pair=True, victims=[("TP1.1", "TP2.1")] * 3, output=tmp_path / "v")
    assert (e.value.code, e.value.params) == ("E_SI_VICTIMS", {"count": 3})
```

  In `tests/test_cli_new.py`, `test_a_usage_error_exits_2`'s list gains `["new", "b.kicad_pcb", "--start", "U1.1", "--end", "J1.1", "--interface", "usb2-hs", "--pair", "--pair-with", "J1.2:U1.2"]` (both pairings), `["new", "b.kicad_pcb", "--start", "U1.1", "--end", "J1.1", "--interface", "usb3"]`, `["new", "b.kicad_pcb", "--start", "U1.1", "--end", "J1.1", "--interface", "se50", "--victim", "TP1.1"]` (one side) and `["new", "b.kicad_pcb", "--start", "U1.1", "--end", "J1.1", "--interface", "custom", "--f-max", "5GHz", "--target", "0"]`. In `tests/test_cli_antenna.py`, `test_end_goes_with_f0_and_antenna_with_band`'s argv tuple gains `["--end", "AE1.1", "--f0", "915MHz", "--pair"]` and `["--antenna", "AE1", "--interface", "se50"]`, each E_NEW_KIND with exit 2.

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_cli_si.py -q`. Expected: FAIL with `AttributeError: module 'kicad_rf_studio.cli' has no attribute 'new_si'`.
- [ ] **Step 3: `cli.new_si`,** docstring "`new` for signal integrity (Stage 4 design 5.1): every refusal before anything is written; returns as `new`." In this order:
  1. `interface = si_interface(interface, f_max, target, pair or pair_with is not None)`; E_SI_VICTIMS `{count}` for more than two victims.
  2. `_load`; the measured line `trace_line(start, end)`; with a pair, the partner's ends from `pair_with` (how "given") or `partner_ends` and its line; each victim's line. E_SI_LINE_SHARED `{start, end, net}` for the first line whose nets meet an earlier line's (its first such net). The merged chain: the first line's start and end, every line's nets in order, every series part, every shunt part once.
  3. The ports, `_port(board, classes, f"P{k}", signal)` (v1's reference) in order [P start, N start, P end, N end, each victim's start and end].
  4. `layers = line_layers(board, merged nets)`, `h = substrate_h(zs, layers)`, `reach = REACH_H · h`; the measured lines' region, `build_region(board, measured chain, measured ports, zs, f_max, REACH_H, layers=layers)`, its ports' references None, so a far v1 reference never stretches it: E_SI_VICTIM_OUTSIDE `{victim "A:B", pad, reach_mm (:g)}` for the first victim end pad its ROI does not cover.
  5. `first = build_region(board, merged, ports with "reference": None, zs, f_max, REACH_H, layers=layers)`; `pieces, _ = copper_pieces(board, first.crop, thickness)` as build_geometry makes them; each port's reference replaced by `si_reference(board, classes, pieces, zs, name, signal, port["reference"], reach)`, and its rule by "plane" for a plane.
  6. `region = build_region(board, merged, ports, zs, f_max, REACH_H, layers=layers)` with the references kept: the call build_geometry makes, so the parts and the lid come from the ROI the model builds (a kept reference lies within the reach, so it stretches nothing far). `project_parts(board, merged, classes, region.roi, 0.0, f_max, si=True)`; each line's chain dict in v1's shape takes its own series and shunt part dicts, a part on two lines kept by the first.
  7. `find_lid(board, classes, region, zs, {"lid": True, "lid_height_mm": lid_height})`.
  8. `eps = eps_eff_2d(board, merged nets, pieces, zs)`, else the largest εr of zs's dielectrics; `rt = round_trip(max(route_length(board, line nets) for each line), eps)`; `window_s = stop_window(rt)`, `t_max_s = si_t_max(f_max, rt)`, `max_cell_mm = round(si_max_cell(f_max, eps), 6)`.
  9. W_SI_LONG_PORT `{name, length_mm (:.3f), limit_mm (:.3f)}` for each port longer than λ/20 at f_max in the stack's highest εr, `C0·1e3/(f_max·√εr_max)/20` mm: a vertical port's plane-to-pad height (between the facing slab faces), a horizontal one's distance from its pad to its reference copper.
  10. `make_si_project(...)` with pair `{"p", "n", "by"}` or None, then `_write`.
  - **Notes, in order:** `_head_notes(board, stackup, project["classes"])` (the board's warnings, W_FILLS_AS_SAVED, the stackup, I_CLASSES: the four lines `new` and `new_antenna` repeat today, which they now call); I_SI_INTERFACE `{interface, target, kind T_DIFFERENTIAL or T_SINGLE_ENDED, tolerance_pct (100·tolerance), rise_ps, marker_mhz, f_max_ghz, local_ps (LOCAL_RISE/f_max in ps)}`, every number `:g`; I_SI_PAIR `{p, n, how}` (T_PAIR_RULE, T_PAIR_ALIAS, T_PAIR_WITH); I_CHAIN for each measured line, I_SI_VICTIM `{start, end, net}` for each victim; the parts; the ports (`_port_note` gives I_PORT_PLANE `{name, signal, layer}` for a plane); I_SI_DEFAULTS `{preset, t_max_ns (:g), window_ns (:g), mesh_n, max_cell_mm (:.3f), eeff (:.2f), dielectric, dt_floor (:g), reach_h (:g), reach_mm (:g)}`; W_COPPER_WEIGHT, W_LID_HEIGHT_MISSING, the part notes, W_SI_LONG_PORT; W_ABSOLUTE_BOARD_PATH, I_WROTE.
  - **The parser:** the frequency group gains `--interface` (choices `(*INTERFACES, "custom")`, metavar NAME); `--pair` (store_true) and `--pair-with` (type `_ends`, metavar REF.PAD:REF.PAD) form a mutually exclusive group; `--victim` (type `_ends`, append, default `[]`), `--f-max` (type `parse_frequency`, metavar F) and `--target` (type `_positive(float)`, metavar OHMS). `_ends(text)` is "an argparse type: REF.PAD:REF.PAD as two pad names", ValueError unless exactly two non-empty sides. `_new` calls `new_si` with `--interface`, E_NEW_KIND with `--antenna` or `--harmonics`; any SI option without `--interface` is E_NEW_KIND.
- [ ] **Step 4: The messages,** each through the catalog tool; E_NEW_KIND's msgid changes deliberately (its old pair becomes obsolete):

| Code | English | pt-BR |
|---|---|---|
| E_NEW_KIND | \`new\` takes --end with --f0 (and --harmonics) for a matching chain, --antenna with --band for an antenna, or --end with --interface (and --pair, --pair-with, --victim, --f-max, --target) for signal integrity. | \`new\` recebe --end com --f0 (e --harmonics) para uma cadeia de casamento, --antenna com --band para uma antena, ou --end com --interface (e --pair, --pair-with, --victim, --f-max, --target) para integridade de sinal. |
| E_SI_VICTIMS | {count} victims given; a project takes up to two. | {count} vítimas indicadas; um projeto recebe até duas. |
| E_SI_VICTIM_OUTSIDE | Victim {victim}: its end {pad} lies outside the region the measured lines set, their copper and parts and {reach_mm} mm past them, which a victim cannot grow. Pick a victim whose ends lie near the route, or leave it out. | Vítima {victim}: a ponta {pad} fica fora da região que as linhas medidas definem, o cobre e os componentes delas e {reach_mm} mm além, que uma vítima não pode aumentar. Escolha uma vítima com as pontas perto da rota, ou deixe-a de fora. |
| E_SI_LINE_SHARED | The line from {start} to {end} runs on net {net}, which an earlier line of this project holds: each line needs nets of its own. Name the partner's two ends with --pair-with, or a victim's with --victim, on another net. | A linha de {start} a {end} passa pela rede {net}, que uma linha anterior deste projeto já tem: cada linha precisa de redes próprias. Indique as duas pontas do par com --pair-with, ou as de uma vítima com --victim, em outra rede. |
| I_SI_INTERFACE | Interface {interface}: target {target} Ω {kind} ± {tolerance_pct} %, the link's rise time {rise_ps} ps, marker {marker_mhz} MHz, simulated to {f_max_ghz} GHz, where the localising TDR's rise time is {local_ps} ps. | Interface {interface}: alvo de {target} Ω {kind} ± {tolerance_pct} %, tempo de subida do enlace de {rise_ps} ps, marcador em {marker_mhz} MHz, simulada até {f_max_ghz} GHz, onde o tempo de subida do TDR de localização é de {local_ps} ps. |
| T_DIFFERENTIAL | differential | diferencial |
| T_SINGLE_ENDED | single-ended | single-ended |
| I_SI_PAIR | Pair: {p} with {n}, by {how}. | Par: {p} com {n}, por {how}. |
| T_PAIR_RULE | KiCad's pair rule | regra de pares do KiCad |
| T_PAIR_ALIAS | the DP/DM alias | apelido DP/DM |
| T_PAIR_WITH | --pair-with | --pair-with |
| I_SI_VICTIM | Victim {start} → {end} on net {net}: its two ends are ports, so the waves coupled into it end in 50 Ω. | Vítima {start} → {end} na rede {net}: as duas pontas dela são portas, então as ondas acopladas nela terminam em 50 Ω. |
| I_PORT_PLANE | Port {name}: signal {signal}, vertical to the plane on {layer}. | Porta {name}: sinal {signal}, vertical até o plano em {layer}. |
| I_SI_DEFAULTS | Preset {preset} (provisional default), T_max {t_max_ns} ns, stop window {window_ns} ns, mesh n {mesh_n} with cells up to {max_cell_mm} mm between the copper edges (λ/40 at f_max, the 2D εeff {eeff}), dielectric {dielectric}, timestep floor {dt_floor}, region and protected reach {reach_h} substrate heights ({reach_mm} mm). | Predefinição {preset} (padrão provisório), T_max {t_max_ns} ns, janela de parada de {window_ns} ns, malha n {mesh_n} com células de até {max_cell_mm} mm entre as bordas do cobre (λ/40 em f_max, εeff 2D de {eeff}), dielétrico {dielectric}, piso do passo de tempo {dt_floor}, região e alcance protegido de {reach_h} alturas de substrato ({reach_mm} mm). |
| W_SI_LONG_PORT | Port {name} spans {length_mm} mm from its pad to its reference, more than λ/20 at f_max ({limit_mm} mm): its launch reads as an inductive bump, which the TDR marks as the port's own. A lower --f-max shortens it in wavelengths. | A porta {name} se estende por {length_mm} mm da ilha até a referência, mais que λ/20 em f_max ({limit_mm} mm): a entrada dela aparece como um degrau indutivo, que o TDR marca como da própria porta. Um --f-max menor a encurta em comprimentos de onda. |

- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_cli_new.py tests/test_cli_antenna.py tests/test_geometry_region.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_sexpr.py -q`. Expected: PASS; v1's and the antenna's `new` lines are unchanged (`_head_notes`), as the pins prove.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(cli): new --interface writes an SI project, its lines, the pair by KiCad's rule or --pair-with, up to two victims inside the measured lines' region, each end's reference across clear copper or vertical to the plane under it, the parts and lid from the region the model builds, and T_max, the stop window and max_cell from the route and the 2D eps_eff (Stage 4 design 5.1, 5.4, 5.5)"
graphify update .
```

---

### Task 6 [code]: The SI geometry and mesh

**Files:**
- Modify: `core/project.py` (`parts` L98-101); `core/geometry/__init__.py` (`Geometry` L29-48, `chain_of` L51-56, `build_geometry` L59-131); `core/geometry/region.py` (`f_max` L25-30); `core/geometry/sections.py` (`off_axis`, which `staircase_gap` L171 uses); `core/mesh/__init__.py` (`VIA_MARGIN_MM`, `build_mesh` L51-90, `_spans`); `core/mesh/rule.py` (`xy_lines`' docstring); `core/mesh/gates.py` (`mesh_with_lint` L54-67); `pipeline.py` (`load` L87-117, `build_model` L120-149).
- Create: `tests/test_si_geometry.py`. Test: `tests/test_mesh_rule.py`.

**Interfaces:**
- Consumes: Task 5's `si_project`; Task 4's `line_layers` and `build_region(layers=)`; plan 1's `xy_lines(max_cell, spans)`.
- Produces:
  - `parts(data)` and `chain_of(project)` merge an SI project's lines: the first line's start and end, every line's nets in order (once), every series part, then every shunt part.
  - `Geometry.layers: tuple[str, ...] = ()`, `legs: tuple[frozenset[str], frozenset[str]] | None = None`, `stairs: tuple[tuple[float, float, float, float], ...] = ()` and `Geometry.partners(net: str) -> frozenset[str]`.
  - `f_max(project)` is `project["f_max_hz"]` for an SI project; `sections.off_axis(t: Track) -> bool`.
  - `VIA_MARGIN_MM = 1.0`; `build_mesh(geom, prot, n, extra_edges=None, *, max_cell=None)`; `mesh_with_lint(geom, prot, n, *, max_cell=None)`.

- [ ] **Step 1: Write the failing tests,** `tests/test_si_geometry.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace

import numpy as np
import pytest
import shapely

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.geometry import chain_of
from kicad_rf_studio.core.geometry.vias import Rod
from kicad_rf_studio.core.mesh import VIA_MARGIN_MM, build_mesh
from kicad_rf_studio.core.mesh.gates import mesh_with_lint
from kicad_rf_studio.core.project import load_project, parts, save_project
from test_cli_si import FIX, QSPI, si_project

LEGS = (frozenset({"USB_D+", "MCU_D+"}), frozenset({"USB_D-", "MCU_D-"}))


@pytest.fixture(scope="module")
def usb(tmp_path_factory):
    return pipeline.load(si_project(tmp_path_factory.mktemp("usb")))


@pytest.fixture(scope="module")
def qspi(tmp_path_factory):
    return pipeline.load(si_project(tmp_path_factory.mktemp("qspi"), QSPI))


def extent(geom):
    return shapely.total_bounds(list(geom.protected.area.values()))


def test_an_si_projects_lines_are_one_chain_of_measured_copper(usb):  # design 5.1, 5.2
    project, board, geom, notes = usb
    c = chain_of(project)
    assert (c.start, c.end, c.nets) == ("J1.3", "U1.3", ("USB_D+", "MCU_D+", "USB_D-", "MCU_D-", "AUX"))
    assert [p.ref for p in c.series] == ["R1", "R2"] and list(parts(project)) == ["R1", "R2", "C1"]
    assert (geom.layers, geom.legs, geom.stairs) == (("F.Cu",), LEGS, ())
    assert geom.partners("MCU_D-") == LEGS[0] and geom.partners("AUX") == frozenset()
    assert geom.protected.nets == frozenset(c.nets)
    assert not {"E_OPEN_IN_ROI", "E_SHORT_IN_ROI", "W_STAIRCASED", "W_OFF_TOP_LAYER"} & {code for code, _ in notes}
    # every line's copper and parts, J1's pins to U1's exposed pad and the test points, 6 × 0.2 mm past them
    assert geom.region.roi.bounds == pytest.approx((96.5875, -102.85, 132.05, -97.55), abs=1e-6)


def test_an_si_line_on_two_layers_takes_both(qspi):  # design 5.3: the dielectric next to each layer; Review Focus 1
    project, board, geom, notes = qspi
    assert (geom.layers, geom.legs, list(parts(project))) == (("F.Cu", "B.Cu"), None, ["R1", "C1"])
    assert "W_OFF_TOP_LAYER" not in {code for code, _ in notes}  # v1's warning: the region took the top layer's h
    assert geom.region.roi.bounds == pytest.approx((97.95, -102.05, 121.7, -97.95), abs=1e-6)  # U1.17 within it


def test_a_line_takes_its_own_dielectric_for_d_and_the_reach(tmp_path):  # design 5.3; Review Focus 4
    pj = si_project(tmp_path, QSPI)
    data = load_project(pj)
    data["stackup"]["layers"] = [{**x, "thickness_mm": {"dielectric 1": 0.3, "dielectric 3": 0.1}.get(
        x["name"], x["thickness_mm"])} for x in data["stackup"]["layers"]]  # 0.1 mm over B.Cu, the total unchanged
    save_project(pj, data)
    project, board, geom, _ = pipeline.load(pj)
    assert geom.region.roi.bounds == pytest.approx((98.55, -101.45, 121.1, -98.55), abs=1e-6)  # 6 × 0.1, not × 0.3
    assert build_mesh(geom, geom.protected, 2).d == pytest.approx(0.05)  # h/n
    assert geom.protected.area["In1.Cu"].bounds[2] == pytest.approx(121.096, abs=0.005)  # U2.6's edge + 0.6 mm


def test_the_si_mesh_fills_d_at_the_edges_and_grades_to_max_cell_between(usb):  # design 5.3
    project, board, geom, _ = usb
    cap = project["mesh"]["max_cell_mm"]
    si = mesh_with_lint(geom, geom.protected, 2, max_cell=cap)  # E_EDGE_LINT would raise
    full = build_mesh(geom, geom.protected, 2)  # Stage 1's d fill
    box = extent(geom)
    mids = (si.x[1:] + si.x[:-1]) / 2
    steps = np.diff(si.x)[(mids > box[0]) & (mids < box[2])]
    assert len(si.x) < len(full.x) and 2 * si.d < steps.max() <= cap + 1e-6


@pytest.mark.parametrize("name", ["usb2_hs", "qspi_clk"])
def test_every_solid_rod_keeps_its_lines(name, tmp_path):  # plan 1's carried item; Review Focus 3
    project, board, geom, _ = pipeline.load(si_project(tmp_path, FIX / f"{name}.kicad_pcb"))
    m = build_mesh(geom, geom.protected, 2, max_cell=project["mesh"]["max_cell_mm"])
    solid = [r for r in geom.rods if r.solid]
    assert len(solid) >= 5  # the exposed pad's four vias with U2.2's, or with qspi_clk's two signal vias
    for r in solid:
        margin = VIA_MARGIN_MM if r.net in geom.protected.nets else r.radius
        for k, lines in enumerate((m.x, m.y)):
            held = lines[(lines >= r.at[k] - margin - 1e-6) & (lines <= r.at[k] + margin + 1e-6)]
            assert held.size >= 2 and np.diff(held).max() <= m.d + 1e-6, (r, k)


def test_a_rod_past_the_extent_on_one_axis_keeps_its_lines(usb):  # Review Focus 3: a fence via beside the route
    project, board, geom, _ = usb
    first = geom.rods[0]
    rod = Rod("GND", (114.0, round(extent(geom)[3] + 0.2, 6)), 0.15, first.z0, first.z1, True)  # x inside, y past
    m = build_mesh(replace(geom, rods=[*geom.rods, rod]), geom.protected, 2, max_cell=project["mesh"]["max_cell_mm"])
    held = m.x[(m.x >= 114.0 - 0.15 - 1e-6) & (m.x <= 114.0 + 0.15 + 1e-6)]
    assert held.size >= 2 and np.diff(held).max() <= m.d + 1e-6  # graded to max_cell there, it would lose its nodes


def test_staircased_copper_is_filled_at_d(tmp_path):  # design 5.3; plan 1's ponytail on 45° copper
    project, board, geom, notes = pipeline.load(si_project(tmp_path, FIX / "usb2_hs_45.kicad_pcb"))
    assert ("W_STAIRCASED", {"net": "USB_D+"}) in notes and len(geom.stairs) == 4  # two 45° segments a line
    m = build_mesh(geom, geom.protected, 2, max_cell=project["mesh"]["max_cell_mm"])
    for x0, y0, x1, y1 in geom.stairs:  # each segment's copper, its round ends too
        for lines, lo, hi in ((m.x, x0, x1), (m.y, y0, y1)):
            assert np.diff(lines[(lines >= lo) & (lines <= hi)]).max() <= m.d + 1e-6
```

  In `tests/test_mesh_rule.py` (it passes at once: the span contract plan 1's review asked to pin):

```python
def test_without_max_cell_spans_are_ignored():  # plan 1's span contract
    assert np.array_equal(si_axis(STRAIGHT, (-1.2, 101.2)),
                          si_axis(STRAIGHT, (-1.2, 101.2), spans=[(49.0, 51.0), (99.0, 101.0)]))
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_si_geometry.py "tests/test_mesh_rule.py::test_without_max_cell_spans_are_ignored" -q`. Expected: FAIL with `cannot import name 'VIA_MARGIN_MM'`; the mesh-rule test passes.
- [ ] **Step 3: The project and the geometry.**
  - **`parts`:** for an SI project, every line's chain series and shunt parts, then the others, by ref; the docstring says so.
  - **`chain_of`:** its docstring adds "an SI project's lines merged (Stage 4 design 5.1)"; the parts are stored once, so no dedupe here.
  - **`Geometry`:** the three fields with their defaults, and `partners(net)`, "the nets of an SI pair's other line for a net of one of its lines (`legs`), else none".
  - **`f_max`:** `project["f_max_hz"]` for `si(project)`, a branch first.
  - **`off_axis(t)`:** "a track the mesh staircases: an arc, or a segment whose ends share neither x nor y within ALIGN"; `staircase_gap` uses it.
  - **`build_geometry`:** for an SI project, `layers = line_layers(board, chain.nets)`, passed to `build_region` and, through `substrate_h(zs, layers)`, to `protected_set`; `legs` the two measured lines' nets when `project["pair"]`; `stairs` the copper bounds (`t.polygon().bounds`) of each `off_axis` track of the chain's nets, so the d fill covers its round ends too. The docstring adds an SI paragraph.
  - **`load`:** W_OFF_TOP_LAYER only when `not si(project)`: an SI geometry takes its lines' layers (design 5.3).
- [ ] **Step 4: The mesh.**
  - **`VIA_MARGIN_MM = 1.0`,** commented "an SI mesh fills d this far either side of a measured net's via (r1: 1 mm); gate P4-C may move it".
  - **`build_mesh`:** `h = substrate_h(zs, geom.layers)`. With `max_cell`, each in-plane axis's `xy_lines` gets `max_cell` and `_spans(geom, prot, k)`: every solid rod, on axis k by its own coordinate there whatever its other one (xy_lines lines a coordinate only d or more past the extent, so a rod whose centre lies just past it on one axis would otherwise keep no line on the other), at ± VIA_MARGIN_MM for a measured net's (`prot.nets`) and ± its radius for any other (a stitching or thermal via); and every staircased track's copper bounds along axis k; on the 1e-6 mm grid. A rod that is not solid is snapped to the lines (`snapped_rods`) and needs no span. Mark `# ponytail: another rod keeps d over its barrel only; its ring and the planes' antipads grade, which P4-C's twin measures`. The docstring says so.
  - **`mesh_with_lint`** passes `max_cell` to both builds.
  - **`xy_lines`' docstring** adds the span contract: "Each span is (lo, hi) with lo ≤ hi, in mm (a backwards one raises ValueError), clipped to the walls and dropped outside them; overlapping spans fill as their union."
  - **`build_model`** passes `max_cell=project["mesh"]["max_cell_mm"] if si(project) else None`.
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_geometry_region.py tests/test_gates.py tests/test_mesh_rule.py tests/test_golden_v1.py tests/test_golden_antenna.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(geometry, mesh): an SI project's lines as one chain, d and the reach from the lines' layers, and the SI mesh rule with a span over every solid rod and over staircased copper (Stage 4 design 5.2, 5.3)"
graphify update .
```

---

### Task 7 [code]: The SI model spec

**Files:**
- Modify: `core/model/ports.py` (`ends` L91-122, `vertical` L147-181); `core/model/spec.py` (`excitation` L91-96, `debye` L172, `model_spec` L230-307); `core/model/csx.py` (the pole loop); `pipeline.py` (`last_sample` L413-415, `run_ports` L815-868); `core/messages.py`, `po/*` and the `.mo`.
- Create: `tests/test_si_model.py`. Test: `tests/test_model_ports.py` (L305–L309 change deliberately: vertical()'s own code), `tests/test_model_spec.py`, `tests/test_model_csx.py`, `tests/test_run.py`.

**Interfaces:**
- Consumes: Task 6's `parts`; plan 1's `dc_pulse`, `debye`, `vertical`.
- Produces:
  - `ends()` reads `{"plane": layer}` as `End(name, pad, pad, layer, "external", ref_layer=layer)` and the parts through `parts(project).values()`, as `model_spec`'s copper parts do.
  - `excitation(project)` is `dc_pulse(f_max_hz, t_max_s, window_s)` for an SI project.
  - An SI spec's materials have `kappa` 0.0, and with `"dielectric": "debye"` each substrate material of tan δ above 0 has `"debye": debye(εr, tan δ, f_max_hz)`.
  - `vertical()` raises E_PORT_PLANE and E_PORT_VERTICAL_BOX; `pipeline.last_sample(rec: Records, window: float = WINDOW_S)`.

- [ ] **Step 1: Write the failing tests,** `tests/test_si_model.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest
import shapely

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.spec import dc_pulse, debye
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_si import si_project


@pytest.fixture(scope="module")
def usb(tmp_path_factory):
    project, board, geom, _ = pipeline.load(pj := si_project(tmp_path_factory.mktemp("usb")))
    return pj, geom, pipeline.build_model(project, board, geom)


def test_an_si_model_is_mur_lossless_and_pulsed_from_dc(usb):  # design 5.2-5.5; Global Constraints
    _, geom, model = usb
    spec = model.spec
    assert spec["excitation"] == dc_pulse(10e9, 9e-9, 2e-9) and not {"boundary", "nf2ff", "join", "copper"} & set(spec)
    assert all(m["kappa"] == 0.0 and "debye" not in m for m in spec["materials"])  # never v1's κ (design 3)
    assert [(q["name"], q["dir"], q["part"]) for q in spec["ports"]] == [
        ("P1", "z", False), ("P2", "z", False), ("P3", "x", False), ("P4", "x", False), ("P5", "z", False),
        ("P6", "z", False), ("R1", "x", True), ("R2", "x", True)]
    assert model.blocked == []
    x, box = model.mesh.x, shapely.total_bounds(list(geom.protected.area.values()))
    mids = (x[1:] + x[:-1]) / 2
    assert np.diff(x)[(mids > box[0]) & (mids < box[2])].max() > 2 * model.mesh.d  # the SI rule, not the d fill


def test_a_debye_si_model_fits_each_lossy_substrate(tmp_path):  # design 5.3
    pj = si_project(tmp_path / "d")
    save_project(pj, {**load_project(pj), "dielectric": "debye"})
    project, board, geom, _ = pipeline.load(pj)
    materials = pipeline.build_model(project, board, geom).spec["materials"]
    subs = [m for m in materials if m["name"].startswith("substrate")]
    assert subs and [m["debye"] for m in subs] == [debye(m["eps"], 0.02, 10e9) for m in subs]
    assert all(m["kappa"] == 0.0 for m in materials) and not [m for m in materials if "debye" in m and
                                                              m["name"].startswith("mask")]
    data = load_project(pj)
    data["stackup"]["layers"] = [{**x, "epsilon_r": 1.5, "loss_tangent": 0.3} if x["name"] == "dielectric 3" else x
                                 for x in data["stackup"]["layers"]]  # the bottom prepreg: the first material
    save_project(pj, data)
    project, board, geom, _ = pipeline.load(pj)
    with pytest.raises(KrsError) as e:  # its ValueError's text never reaches the user (plan 1's carried item)
        pipeline.build_model(project, board, geom)
    assert (e.value.code, e.value.params) == ("E_DEBYE_FIT", {"eps_r": "1.5", "tan_d": "0.3"})
```

  In `tests/test_model_ports.py`, `test_a_vertical_port_needs_a_mesh_line_inside_its_pad` now expects `("E_PORT_VERTICAL_BOX", {"name": "P9"})`, and:

```python
@pytest.mark.parametrize("plane", ["F.Cu", "In9.Cu"])
def test_a_vertical_port_needs_another_copper_layer_as_its_plane(plane):  # plan 1's carried item
    with pytest.raises(KrsError) as e:
        place(End("P1", PAD, PAD, "F.Cu", "external", ref_layer=plane), V_MESH, FOUR, [])
    assert (e.value.code, e.value.params) == ("E_PORT_PLANE", {"name": "P1", "layer": plane, "signal_layer": "F.Cu"})
```

  In `tests/test_model_spec.py` (imports gain `from kicad_rf_studio.core.model import spec as spec_module`):

```python
def test_a_debye_fit_that_keeps_no_pole_is_refused(monkeypatch):  # plan 1's carried item: no order-0 material
    monkeypatch.setattr(spec_module, "nnls", lambda a, b: (np.r_[4.0, 0.0, 0.0, 0.0], 0.0))
    with pytest.raises(ValueError, match="no pole"):
        debye(4.3, 0.02, 10e9)
```

  In `tests/test_model_csx.py`:

```python
def test_a_debye_entry_whose_lists_differ_is_refused(monkeypatch):  # plan 1's carried item: zip(strict=True)
    log = fake_openems(monkeypatch)
    monkeypatch.setitem(sys.modules, "CSXCAD.CSProperties",
                        types.SimpleNamespace(CSPropDebyeMaterial=Rec(log, "CSPropDebyeMaterial")))
    db = {"eps_inf": 4.0, "delta": [0.2], "f_relax_hz": [1e9, 1e10]}
    with pytest.raises(ValueError):
        build_csx({**TINY, "materials": [{**TINY["materials"][0], "kappa": 0.0, "debye": db}]}, 1, 1e-9)
```

  In `tests/test_run.py` (imports gain `residual_db`, and `far_end` from `test_stoprule`):

```python
def test_the_last_sample_reads_an_si_pulses_window():  # plan 1's carried item
    rec = far_end(5e-9, t_end=12e-9)  # the first pulse's peak inside a 15 ns window at the last sample, not a 2 ns one
    assert pipeline.last_sample(rec, 15e-9)[1] == residual_db(rec, 15e-9)[-1] == 0.0
    assert pipeline.last_sample(rec)[1] == -np.inf
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_si_model.py "tests/test_model_ports.py::test_a_vertical_port_needs_another_copper_layer_as_its_plane" "tests/test_model_ports.py::test_a_vertical_port_needs_a_mesh_line_inside_its_pad" "tests/test_model_spec.py::test_a_debye_fit_that_keeps_no_pole_is_refused" "tests/test_model_csx.py::test_a_debye_entry_whose_lists_differ_is_refused" "tests/test_run.py::test_the_last_sample_reads_an_si_pulses_window" -q`. Expected: FAIL (`KeyError: 'f0_hz'` in `model_spec`; vertical()'s codes, the two ValueErrors and `last_sample`'s argument missing).
- [ ] **Step 3: Ports.**
  - **`ends`:** a port whose reference holds `"plane"` gives `End(name, sig.polygon, sig.polygon, layer, "external", ref_layer=ref["plane"])`; the parts come from `parts(project).values()`. The docstring names the vertical end (Stage 4 design 5.5).
  - **`vertical`:** first, E_PORT_PLANE `{name, layer: end.ref_layer, signal_layer: end.layer}` when `end.ref_layer` is `end.layer` or no copper slab of `zs`; its no-line refusals become E_PORT_VERTICAL_BOX `{name}`, whose advice is a vertical port's (E_PORT_BOX's names the copper between two pads).
- [ ] **Step 4: The spec.**
  - **`excitation`:** `dc_pulse(project["f_max_hz"], project["t_max_s"], project["window_s"])` for `si(project)`, a branch first.
  - **`debye`:** after `keep`, `if not keep.any(): raise ValueError("a Debye fit keeps no pole")`; the docstring adds it.
  - **`model_spec`:** for an SI project, `f0` is not read; every material's κ is 0.0. With `project["dielectric"] == "debye"`, each substrate material (a dielectric slab, or a copper slab's fill at its two neighbours' mean εr and mean tan δ, a None tan δ read as 0) whose tan δ is above 0 gets `"debye"`, through a helper that turns debye's ValueError into E_DEBYE_FIT `{eps_r (:g), tan_d (:g)}`; the masks stay κ-free and Debye-free (`# ponytail: a 10 µm mask's loss is left out under Debye; a mask fit if P4-D needs it`). The copper parts come from `parts(project).values()`. The docstring adds an SI paragraph.
  - **`csx`:** the pole loop zips with `strict=True`.
- [ ] **Step 5: `last_sample`.** `last_sample(rec, window=WINDOW_S)` reads `residual_db(rec, window)`; `run_ports` passes `exc.get("window_s", WINDOW_S)` in `watch` and in its verdict loop. The docstring says so.
- [ ] **Step 6: The messages:**

| Code | English | pt-BR |
|---|---|---|
| E_DEBYE_FIT | A Debye fit of a dielectric with εr {eps_r} and tan δ {tan_d} has no valid poles: it falls below vacuum or keeps none. Set "dielectric": "lossless" in project.json, or check that layer's εr and loss tangent in KiCad. | Um ajuste de Debye de um dielétrico com εr {eps_r} e tan δ {tan_d} não tem polos válidos: fica abaixo do vácuo ou não mantém nenhum. Defina "dielectric": "lossless" em project.json, ou confira o εr e a tangente de perdas dessa camada no KiCad. |
| E_PORT_PLANE | Port {name} cannot take {layer} as its reference plane: it must be a copper layer of the board other than its pad's, {signal_layer}. Run \`new\` again, or set ports[].reference.plane in project.json. | A porta {name} não pode tomar {layer} como plano de referência: ele precisa ser uma camada de cobre da placa diferente da camada da ilha, {signal_layer}. Execute \`new\` de novo, ou defina ports[].reference.plane em project.json. |
| E_PORT_VERTICAL_BOX | Port {name}: no mesh line lies inside its pad's copper, so its vertical port has no sheet. Change mesh.n in project.json (another value moves the mesh lines), or end the line at a larger pad. | Porta {name}: nenhuma linha da malha fica dentro do cobre da ilha dela, então a porta vertical não tem folha. Mude mesh.n em project.json (outro valor move as linhas da malha), ou termine a linha em uma ilha maior. |

- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_model_ports.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_worker.py tests/test_stoprule.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(model): an SI model spec, MUR walls, the DC pulse with its stop window, kappa-free materials or Debye with its refusal as a catalog code, vertical ports to their planes with their own refusals, and last_sample on the SI window (Stage 4 design 5.2-5.5)"
graphify update .
```

---

### Task 8 [code]: `cost` for an SI project

**Files:**
- Modify: `core/geometry/sections.py` (`cross_section`'s `partners`); `core/mesh/gates.py` (`fit2d` L70-90); `core/project.py` (`default_gates`); `pipeline.py` (`gate_lines` L346-350, `si_readout` after `readout_2d` L308-325, `cost` L353-393, `cost_notes` L208-249, `_model_phase` L757-774, `simulate` L777-812, `run_ports` L815-868, `LONG_RUN_S`); `core/messages.py`, `po/*` and the `.mo`.
- Create: `tests/test_si_cost.py`.

**Interfaces:**
- Consumes: Tasks 4–7; `cs2d.pair`, `solve`, `ShortError`; `route_length`; `SIMPLIFY`.
- Produces:
  - `cross_section(sec, pieces, zs, mask, mode, dz0=None, box_h=BOX_H, h=None, partners: Collection[str] = ())`: among the cut's strips on `sec.layer` inside the box whose net is in `partners`, the one whose middle lies nearest the signal's centre line is a second signal, for `cs2d.pair`.
  - `fit2d` adds, for each section with `geom.partners(sec.net)` whose pair solves on its own grid, a Fit of its Zdiff on the mesh against cs2d's grid, `err` the larger of its odd and even modes' errors.
  - `project.default_gates(data) -> dict`: GATES_SI for an SI project, else GATES; `pipeline.gate_lines(gates: dict, defaults: dict = GATES)`: W_GATE_LIMITS_SI against GATES_SI; `run_ports(..., defaults=GATES)`.
  - `pipeline.si_readout(board: Board, geom: Geometry, project: dict) -> list[tuple[str, dict]]`; `LONG_RUN_S = 7200`.

- [ ] **Step 1: Write the failing tests,** `tests/test_si_cost.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from dataclasses import replace

import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.mesh.gates import check_fit2d, fit2d
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import GATES, GATES_SI
from test_cli_si import FIX, QSPI, si_project


def events(run_dir):
    return [(e["code"], e["params"]) for e in map(json.loads, (run_dir / "events.jsonl").read_text("utf-8").splitlines())]


def readout(tmp_path, board):
    project, board, geom, _ = pipeline.load(si_project(tmp_path, board))
    return pipeline.si_readout(board, geom, project)


def test_the_si_cost_lists_the_2d_table_and_the_runs(tmp_path, calibrated):  # design 5.9
    (tmp_path / "cost").mkdir()
    assert pipeline.cost(si_project(tmp_path / "p"), tmp_path / "cost") == 0
    ev = events(tmp_path / "cost")
    codes = {c for c, _ in ev}
    assert "I_SI_2D_HEADER" in codes and not {"I_2D_HEADER", "W_GATE_LIMITS", "W_GATE_LIMITS_SI",
                                              "I_SI_SHORT_ROUTE"} & codes
    long = [p for c, p in ev if c == "I_SI_2D_PAIR" and p["length_mm"] == "17.490"]  # the long run, a 0.25 mm gap
    assert {p["net"] for p in long} == {"USB_D+", "USB_D-"}
    assert all(p["verdict"] == "T_IN_BAND" and 81 <= float(p["z_diff"]) <= 99 for p in long)
    assert {p["net"] for c, p in ev if c == "I_SI_2D_PAIR"} >= {"MCU_D+", "MCU_D-"}  # legs microns apart still pair
    legs = [p for c, p in ev if c == "I_SI_2D_LEG"]  # the four jogs to and from U2's rows, each partner elsewhere
    assert len(legs) == 4 and all(float(p["z_diff"]) == pytest.approx(2 * float(p["z0"]), abs=0.011) for p in legs)
    assert dict(ev)["I_SI_COST_JOBS"] == {"lines": 4, "victims": 2, "parts": 2}
    assert [p["verdict"] for c, p in ev if c == "I_SI_2D_LINE"] == ["T_VICTIM"]  # AUX, the victim's one section


def test_the_neck_down_reads_out_of_the_band(tmp_path):  # design 5.9; P4-F's fixture
    neck = [p for c, p in readout(tmp_path, FIX / "usb2_hs_neck.kicad_pcb") if c == "I_SI_2D_PAIR"
            and p["width_mm"] == "0.200"]
    assert len(neck) == 2 and all(p["verdict"] == "T_OUT_OF_BAND" and float(p["z_diff"]) > 99 for p in neck)


def test_a_short_route_is_said_so_and_the_clock_reads_in_band(tmp_path):  # design 5.9: under a sixth of 1 ns
    rows = readout(tmp_path, QSPI)
    lines = dict(rows)
    assert lines["I_SI_SHORT_ROUTE"]["net"] == "QSPI_CLK" and float(lines["I_SI_SHORT_ROUTE"]["delay_ps"]) < 1000 / 6
    assert {p["verdict"] for c, p in rows if c == "I_SI_2D_LINE"} == {"T_IN_BAND"}  # 50.0 Ω, its B.Cu run too


def test_fit2d_checks_a_pairs_coupled_sections(tmp_path):  # design 5.3, 5.9
    project, board, geom, _ = pipeline.load(si_project(tmp_path))
    mesh = pipeline.build_model(project, board, geom).mesh
    coupled = [f for f in fit2d(geom, mesh) if f.z0_ref > 70]  # a Zdiff of about 90 Ω, beside each leg's own 51 Ω
    table = {p["net"]: float(p["z_diff"]) for c, p in pipeline.si_readout(board, geom, project)
             if c == "I_SI_2D_PAIR" and p["length_mm"] == "17.490"}
    long = [f for f in coupled if f.section.length == 17.49]
    assert {f.section.net for f in long} == {"USB_D+", "USB_D-"} and max(f.err for f in coupled) <= 0.03
    assert all(f.z0_ref == pytest.approx(table[f.section.net], abs=0.006) for f in long)  # cs2d's pair, not the mesh
    fits = fit2d(geom, replace(mesh, y=mesh.y[(mesh.y <= -100.125) | (mesh.y >= -99.875)]))  # no line in the gap
    assert max(f.err for f in fits if f.z0_ref > 70) > 0.03
    with pytest.raises(KrsError) as e:
        check_fit2d(fits, 0.03, 2)
    assert e.value.code == "E_FIT2D"


def test_an_si_cost_past_two_hours_is_warned_and_its_gates_are_its_own(tmp_path):  # design 5.9; A-43
    project, board, geom, _ = pipeline.load(si_project(tmp_path))
    model, setup = pipeline.build_model(project, board, geom), {"dt": 1e-13, "node": [0, 1, 2, 3]}
    assert "W_SI_LONG_RUN" in dict(pipeline.cost_notes(model, project, setup, 4, 1, 1.0))  # 1 MC/s: days
    assert "W_SI_LONG_RUN" not in dict(pipeline.cost_notes(model, project, setup, 4, 8, 1e9))
    assert pipeline.gate_lines(GATES_SI, GATES_SI) == [] and pipeline.gate_lines(GATES) == []
    assert pipeline.gate_lines(GATES, GATES_SI) == [("W_GATE_LIMITS_SI", {"fit2d_limit": "0.03", "dt_floor": "0.8"})]
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_si_cost.py -q`. Expected: FAIL: `pipeline.si_readout` does not exist, `cost` prints v1's 2D readout, and `gate_lines` takes one argument.
- [ ] **Step 3: The coupled cross-section and fit2d.**
  - **`cross_section`'s `partners`:** among the cut's strips on `sec.layer` inside the box whose net is in `partners`, the one whose middle lies nearest the signal's centre line takes the role "signal" too. When its width differs from the signal strip's by at most 2·SIMPLIFY, it takes the signal strip's width about its own middle: cs2d's pair needs mirror images to 1e-9 mm, and the 10 µm simplification leaves real legs 0.3–3 µm apart (usb2_hs's MCU run, every cut of usb2_hs_45). Mark `# ponytail: a partner within 20 µm takes the signal's width; wider legs read as a leg alone (I_SI_2D_LEG)`. The docstring says so; with no partner, today's cross-section.
  - **`fit2d`:** after a section's Fit, when `partners := geom.partners(sec.net)`: the exact cross-section with them through `pair` on cs2d's grid (a ValueError, ShortError included, means no coupled check: the leg's own Fit stands), then the smeared one on the mesh lines (a ValueError there: z 0, err 1, as v1's); the coupled Fit's z0 fields hold Zdiff. The docstring adds it, and `# ponytail: both legs' sections check the same coupled cut, twice`.
- [ ] **Step 4: The gates' defaults.** `default_gates(data)`; `gate_lines(gates, defaults=GATES)` returns `[]` when `gates == defaults`, else W_GATE_LIMITS, or W_GATE_LIMITS_SI when `defaults` is GATES_SI's value; `cost`, `_model_phase` and `simulate` pass `default_gates(project)`, and `simulate` passes it to `run_ports(..., defaults=...)`, which hands it to each verdict's `gate_lines`. `chain_results` keeps GATES.
- [ ] **Step 5: `si_readout`.**
  - **Docstring:** "The 2D table of an SI project (Stage 4 design 5.9), no file written: I_SI_2D_HEADER (W_NO_SECTIONS without a section), then each section of `geom` in order, its cut solved on cs2d's own grid with the exact mask of its side, in a box of its own layer's substrate (cross_section's `h`): a pair's line whose partner runs alongside at the cut as I_SI_2D_PAIR (cs2d.pair: Zdiff, Zodd, Zeven, the odd and even εeff, the delay at the odd mode's); a pair's line alone there as I_SI_2D_LEG (Z0, Zdiff 2·Z0 uncoupled); a single net's as I_SI_2D_LINE; each against the target band, |Z − target| ≤ tolerance·target, a victim's as T_VICTIM; W_2D_SHORT where other copper touches the line at its cut. Then I_SI_SHORT_ROUTE for the longest measured route (route_length) when its delay, at the largest εeff its rows read, is under rise_s/6."
  - The numbers are formatted as I_2D_SECTION's: widths, gaps and lengths `:.3f`, impedances `:.2f`, εeff `:.3f`, delays in ps `:.1f`. A pair whose legs differ at the cut by more than 2·SIMPLIFY (pair's ValueError) reads as I_SI_2D_LEG, marked `# ponytail: such a pair reads 2·Z0 with its partner grounded, which overstates Zdiff by the coupling; cs2d's asymmetric modes if real boards need it`. A pair whose surroundings differ per leg (a victim beside one) reads cs2d.pair's modes from the legs' mean c11, marked `# ponytail: mean-c11 modes as a screening; on usb2_hs's long cut the legs alone read 51.01 and 51.10 Ω`. A section shorter than its width (a jog into a pad) has no bare cut and reads the strip it joins, marked `# ponytail: no skip rule for a cut that is no line's until plan 4's P4-C sets one; the fixtures have none`.
  - **`cost`** prints `si_readout(board, geom, project)` in place of `readout_2d(geom)` for an SI project.
- [ ] **Step 6: `cost_notes`.** `time()` becomes `seconds()`, formatted by `duration` where used. For an SI project, after I_COST_TIME: I_SI_COST_JOBS `{lines: 2 × the measured lines, victims: 2 × the victims, parts: the part ports}`, then W_SI_LONG_RUN `{time}` when the worst case exceeds LONG_RUN_S (`LONG_RUN_S = 7200  # design 5.9: a warning past two hours`). Mark `# ponytail: a Debye cell counts as a plain one until gate P4-D measures its weight (design 5.9)`.
- [ ] **Step 7: The messages:**

| Code | English | pt-BR |
|---|---|---|
| I_SI_2D_HEADER | 2D table against the target {target} Ω ± {tolerance_pct} % (a pair's Zdiff, a net's Z0), mask included; bends, vias, pads and parts not included: a screening before the run, not its result. | Tabela 2D contra o alvo de {target} Ω ± {tolerance_pct} % (Zdiff de um par, Z0 de uma rede), com a máscara; curvas, vias, ilhas e componentes não incluídos: uma triagem antes da execução, não o resultado dela. |
| I_SI_2D_LINE | {net} on {layer}: width {width_mm} mm, gap {gap_mm}, length {length_mm} mm — Z0 {z0} Ω, εeff {eeff}, delay {delay_ps} ps: {verdict}. | {net} em {layer}: largura {width_mm} mm, espaçamento {gap_mm}, comprimento {length_mm} mm — Z0 {z0} Ω, εeff {eeff}, atraso de {delay_ps} ps: {verdict}. |
| I_SI_2D_LEG | {net} on {layer}: width {width_mm} mm, length {length_mm} mm, its partner not alongside — Z0 {z0} Ω, so Zdiff {z_diff} Ω uncoupled, εeff {eeff}, delay {delay_ps} ps: {verdict}. | {net} em {layer}: largura {width_mm} mm, comprimento {length_mm} mm, sem o par ao lado — Z0 {z0} Ω, logo Zdiff {z_diff} Ω sem acoplamento, εeff {eeff}, atraso de {delay_ps} ps: {verdict}. |
| I_SI_2D_PAIR | {net} on {layer}, coupled: width {width_mm} mm, gap {gap_mm} mm, length {length_mm} mm — Zdiff {z_diff} Ω (Zodd {z_odd} Ω, Zeven {z_even} Ω), εeff odd {eeff_odd}, even {eeff_even}, delay {delay_ps} ps: {verdict}. | {net} em {layer}, acoplada: largura {width_mm} mm, espaçamento {gap_mm} mm, comprimento {length_mm} mm — Zdiff {z_diff} Ω (Zodd {z_odd} Ω, Zeven {z_even} Ω), εeff ímpar {eeff_odd}, par {eeff_even}, atraso de {delay_ps} ps: {verdict}. |
| T_IN_BAND | in the target band | dentro da faixa alvo |
| T_OUT_OF_BAND | outside the target band | fora da faixa alvo |
| T_VICTIM | a victim, no target | uma vítima, sem alvo |
| I_SI_SHORT_ROUTE | The route {net} is {delay_ps} ps long, under a sixth of the link's {rise_ps} ps rise time: it is electrically short, and the 2D table above, with a lumped estimate, may answer the question without a run. | A rota {net} tem {delay_ps} ps, menos de um sexto do tempo de subida de {rise_ps} ps do enlace: é eletricamente curta, e a tabela 2D acima, com uma estimativa concentrada, pode responder à questão sem uma execução. |
| I_SI_COST_JOBS | Runs: {lines} for the measured lines' ends, {victims} for the victims' ends, {parts} for the part ports. | Execuções: {lines} para as pontas das linhas medidas, {victims} para as pontas das vítimas, {parts} para as portas de componentes. |
| W_SI_LONG_RUN | The worst case is {time}, over two hours: the draft preset, or a shorter route between nearer pads, cuts it. | O pior caso é {time}, mais de duas horas: a predefinição draft, ou uma rota mais curta entre ilhas mais próximas, o reduz. |
| W_GATE_LIMITS_SI | project.json sets gates.fit2d_limit {fit2d_limit} and gates.dt_floor {dt_floor}, not a signal-integrity project's 0.03 and 0.6, so this verdict is outside the limits it was built for. Set them back to 0.03 and 0.6. | project.json define gates.fit2d_limit {fit2d_limit} e gates.dt_floor {dt_floor}, não os 0.03 e 0.6 de um projeto de integridade de sinal, então este veredito está fora dos limites para os quais foi construído. Volte-os para 0.03 e 0.6. |

- [ ] **Step 8: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_cli_cost.py tests/test_cost_model.py tests/test_gates.py tests/test_run.py tests/test_p0.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_sexpr.py -q`. Expected: PASS; v1's cost lines are unchanged.
- [ ] **Step 9: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(cost): an SI project's 2D table, Zdiff, Zodd and Zeven from cs2d's pair on coupled sections against the target band, fit2d on them, the runs by lines, victims and parts, a warning past two hours and the short-route note (Stage 4 design 5.9)"
graphify update .
```

---

### Task 9 [code]: An SI run writes the layout N-port

**Files:**
- Modify: `core/project.py` (`shown_reference` L104-112); `core/post/waves.py` (`layout` L90-122); `pipeline.py` (`basis_lines` from `chain_results` L476-520; `si_outputs` after `antenna_outputs`; `write_outputs` L523-562; `_run` L709-754; `retune` L968-994; `verify` L1074-1102); `tests/networks.py` (`synth_records`); `core/messages.py`, `po/*` and the `.mo`.
- Create: `tests/test_si_run.py`. Test: `tests/test_post_waves.py`.

**Interfaces:**
- Consumes: Tasks 5–8; `core.post.si.uniform_grid`; `touchstone`, `port_map`, `write`, `OUTPUTS`.
- Produces:
  - `shown_reference({"plane": layer}) == f"plane {layer}"`.
  - `layout()`'s default grid for an SI project is `uniform_grid(project["f_max_hz"])`, its marker the grid point nearest `marker_hz`.
  - `pipeline.basis_lines(results: dict, defaults: dict = GATES) -> list`: I_BASIS, each flagged job and gate_lines, which `chain_results` now calls.
  - `pipeline.si_outputs(path, project, command, *, errors_as_lines=False) -> list[tuple[str, dict]]`, which `write_outputs` returns for an SI project.
  - `synth_records(..., f1=0.0, ...)` drives the SI pulse, `dc_pulse`'s Gaussian from DC.

- [ ] **Step 1: Write the failing tests,** `tests/test_si_run.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path

import numpy as np
import pytest
import skrf

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.si import uniform_grid
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import load_project
from kicad_rf_studio.stoprule import KEPT
from networks import star
from test_cli_si import QSPI, si_project
from test_run import result_codes


def test_an_si_run_writes_its_layout_on_the_grid_from_dc(tmp_path, calibrated, monkeypatch):  # design 5.12 item 2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    results = p["results"]
    assert [j["port"] for j in results["jobs"]] == ["P1", "P2", "P3", "P4", "P5", "P6", "R1", "R2"]  # Stage 1 7.1
    assert {j["verdict"] for j in results["jobs"]} <= KEPT and results["loss_expected"] is None  # no loss budget (5.6)
    out = pj.parent / "results"
    assert sorted(f.name for f in out.iterdir()) == ["layout.s8p"]
    n = skrf.Network(str(out / "layout.s8p"))
    assert (n.f[0], n.f[-1], len(n.f)) == (0.0, 10e9, 2001) and np.abs(n.s - star(n.f, 8)).max() <= 1e-5
    assert "port 1 P1: external, signal J1.3, reference plane In1.Cu, as built" in (out / "layout.s8p").read_text()
    assert result_codes(results["run_dir"]) == ["I_RESULTS", "I_BASIS", "I_OUTPUTS"]  # the SI results are plan 3's
    codes = {e["code"] for e in map(json.loads, (Path(results["run_dir"]) / "events.jsonl").read_text("utf-8").splitlines())}
    assert not {"W_GATE_LIMITS", "W_GATE_LIMITS_SI"} & codes  # every verdict judged against GATES_SI
    lay = layout(p, results)
    assert lay.f.tolist() == uniform_grid(10e9).tolist() and lay.markers == [48]  # 240 MHz on the 5 MHz grid
    assert pipeline.retune(pj, []) == 0 and sorted(f.name for f in out.iterdir()) == ["layout.s8p"]
    with pytest.raises(KrsError) as e:  # a part value would be stored and change nothing until plan 3
        pipeline.retune(pj, ["R1=33"])
    assert (e.value.code, e.value.params) == ("E_RETUNE_SI", {}) and load_project(pj) == p


def test_a_marker_off_the_grid_takes_its_nearest_point(tmp_path, calibrated, monkeypatch):  # se50's 133 MHz
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    assert layout(p, p["results"]).markers == [27]  # 135 MHz: round(133/5)


def test_verify_waits_for_the_si_results_and_preview_takes_an_si_project(tmp_path, calibrated, monkeypatch):
    pj = si_project(tmp_path / "p")
    with pytest.raises(KrsError) as e:
        pipeline.verify(pj)
    assert (e.value.code, e.value.params) == ("E_VERIFY_SI", {})
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(pj, pj)
    assert e.value.code == "E_COMPARE_KIND"  # compare comes with the SI results (plan 3)
    opened = []
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: opened.append(job))
    assert pipeline.preview(pj) == 0
    assert json.loads((Path(opened[0]).parent / "model.json").read_text(encoding="utf-8"))["excitation"]["f1"] == 0.0
```

  In `tests/test_post_waves.py` (imports gain `uniform_grid`):

```python
def test_the_si_pulse_from_dc_gives_back_the_network_and_its_dc_point():  # Stage 4 design 5.4
    f = uniform_grid(10e9)
    S, A = s_matrix(synth_records(lambda f: star(f, 4), 4, 0.0, 10e9, 1e-13, 9e-9), f)
    assert np.abs(S - star(f, 4)).max() <= 1e-5 and level_db(A)[0] == pytest.approx(0.0, abs=1e-9)
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_si_run.py "tests/test_post_waves.py::test_the_si_pulse_from_dc_gives_back_the_network_and_its_dc_point" -q`. Expected: FAIL: the waves test misses its 1e-5 bound and its DC level (the fake's v1 pulse from f1 0: S off by about 6e-3, DC about −106 dB), and the runs fail with `KeyError: 'f0_hz'`.
- [ ] **Step 3: The fake's pulse.** `synth_records`, with `f1 == 0`, drives `exp(−(2π·f2·t/3 − 3)²)·(t < 2·t0)`, t0 = 9/(2π·f2), dc_pulse's; its docstring says so. The fake worker passes the spec's f1 already.
- [ ] **Step 4: The run.**
  - **`shown_reference`:** a `{"plane": layer}` reads `f"plane {layer}"`; the docstring says so.
  - **`layout`:** for `si(project)`, f0 is `marker_hz`, the default grid `uniform_grid(project["f_max_hz"])`, and the marker the grid index nearest it, `round(marker_hz / (f[1] − f[0]))` (240 MHz is index 48; se50's 133 MHz reads at 135 MHz and 100base-tx's 62.5 MHz at 60 MHz, within half the 5 MHz step); the docstring names it (Stage 4 design 5.6: the TDR's grid).
  - **`basis_lines`:** `chain_results`' I_BASIS, flagged jobs and gate lines, moved, with `defaults`.
  - **`si_outputs`:** docstring "An SI run's outputs (Stage 4 design 5.12 item 2), which write_outputs writes for it, in run and retune alike: layout.s{N}p on layout()'s grid, with its port map, to results/ (write, OUTPUTS, `command` as E_RESULTS_WRITE's advice). Returns basis_lines at GATES_SI, then I_OUTPUTS; E_RESULTS_WRITE as write_outputs takes it. The SI results, the label and the limits are Stage 4 plan 3's." Mark `# ponytail: write_outputs' layout and write tail, copied; plan 3 rewrites this with the TDRs and the chain file`.
  - **`write_outputs`:** `if si(project): return si_outputs(...)`, a branch first.
  - **`_run`:** `loss = None if si(project) else expected_loss(geom, project["f0_hz"])`, commented "design 5.6: v1's loss budget does not apply to SI".
  - **`retune`:** under the lock, before `assign`: `if si(project) and assignments: raise KrsError("E_RETUNE_SI")`, marked `# ponytail: plan 3's SI retune closes the part ports; until then a value changes no output`; `retune` with none rewrites layout.s{N}p.
  - **`verify`:** first, `if si(project): raise KrsError("E_VERIFY_SI")`, marked `# ponytail: plan 3 verifies an SI project`.
- [ ] **Step 5: The messages:**

| Code | English | pt-BR |
|---|---|---|
| E_VERIFY_SI | \`verify\` does not take a signal-integrity project yet; \`cost\` and \`run\` do. | \`verify\` ainda não recebe um projeto de integridade de sinal; \`cost\` e \`run\` recebem. |
| E_RETUNE_SI | \`retune\` takes no part values for a signal-integrity project yet, since its retune comes with the SI results; without values it rewrites the layout Touchstone file. | \`retune\` ainda não recebe valores de componentes para um projeto de integridade de sinal, pois o retune dele vem com os resultados de SI; sem valores, ele reescreve o arquivo Touchstone do layout. |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_run.py tests/test_run_antenna.py tests/test_retune.py tests/test_verify.py tests/test_post_outputs.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(run): an SI run, one job per port, writes the layout N-port on the uniform grid from DC with its port map and its marker on the grid; verify and a retune of part values wait for the SI results (Stage 4 design 5.5, 5.12 item 2)"
graphify update .
```

---

### Task 10 [code]: The SI golden pins

**Files:** Create `tools/golden_si.py` and `tests/test_golden_si.py`; written by the tool: `tests/fixtures/golden_si.json`.

**Interfaces:**
- Consumes: `golden_v1.record`, `golden_v1.env`, `sha`; `golden_antenna._board`; Task 5's `si_args`; `cli.new_si`; `pipeline.load`, `build_model`, `si_readout`; `spec_hash`.
- Produces: `golden_si.GOLDEN`, `CASES` and `digests() -> dict` (`{"models": {case: {"spec_hash", "model_json", "project", "notes", "blocked"}}, "outputs": {case: {"readout"}}}`), `main() -> int`.

- [ ] **Step 1: Write the failing test,** `tests/test_golden_si.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os

import golden_si
import golden_v1
import pytest

GOLDEN = json.loads(golden_si.GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def now(tmp_path_factory):
    home = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("golden_si"))  # relative paths only, as golden_v1's
    try:
        return golden_si.digests()
    finally:
        os.chdir(home)


def test_the_si_fixtures_build_byte_for_byte_what_they_did_at_plan_2(now):  # Stage 4 design 5.11
    assert set(now["models"]) == set(golden_si.CASES)
    assert now["models"] == GOLDEN["models"]  # an SI project, its new lines, model spec, hash or a blocking gate moved


def test_the_si_2d_tables_are_byte_for_byte_what_they_were_at_plan_2(now):  # cost's output before plan 3's
    assert set(now["outputs"]) == set(golden_si.CASES)
    if golden_v1.env() != GOLDEN["env"]:
        pytest.skip("the 2D table pins compare only on the env that recorded them (golden_v1.env())")
    assert now["outputs"] == GOLDEN["outputs"]
```

- [ ] **Step 2: Run it.** `.venv/Scripts/python -m pytest tests/test_golden_si.py -q`. Expected: FAIL with `ModuleNotFoundError: No module named 'golden_si'`.
- [ ] **Step 3: `tools/golden_si.py`,** golden_antenna's shape: the docstring "The SI golden pins (Stage 4 plan 2): sha256 digests of what `new --interface` writes and the model it builds for each SI fixture, everywhere, and of its 2D table where golden_v1.env() matches, recorded once at plan 2's end in tests/fixtures/golden_si.json through golden_v1.record. Plans 3 to 5 keep them; a deliberate change (plan 4's defaults) is a ruled re-recording." It adds tests/ to `sys.path` as golden_antenna does for `networks`, and imports `si_args` from `test_cli_si`, so the five commands are written once. `CASES = ("usb2_hs", "usb2_hs_neck", "usb2_hs_gap", "usb2_hs_45", "qspi_clk")`; `digests()` builds each board copied in by `_board`, with `cli.new_si(board, *args, **kw, output=Path(name))` from `si_args`, then `pipeline.load` and `build_model`, pinning `spec_hash`, model.json's `sha(json.dumps(spec).encode())`, project.json's bytes, new's notes without I_WROTE and `model.blocked`, as golden_antenna does, and under "outputs" the sha of `json.dumps(si_readout(...), sort_keys=True)`. `main()` returns `golden_v1.record(GOLDEN, digests)`.
- [ ] **Step 4: Record the pins from this branch's code:** `git status --short src` prints nothing, then `.venv/Scripts/python tools/golden_si.py`. Expected: exit 0 and the JSON, about 3 KB, every case's `blocked` the digest of `[]`. Run it again: it refuses with exit 1.
- [ ] **Step 5: Run it again.** `.venv/Scripts/python -m pytest tests/test_golden_si.py tests/test_golden_v1.py tests/test_golden_antenna.py tests/test_repo.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add tools/golden_si.py tests/test_golden_si.py tests/fixtures/golden_si.json
git commit -m "test(golden): pin the five SI fixtures' projects, new's lines, model specs, hashes and blocking gates as plan 2 builds them, and their 2D tables where the env matches, recorded through golden_v1.record (Stage 4 design 5.11)"
graphify update .
```

---

### Task 11 [run]: The first SI run, its record and the amendments

This task commits the record, the amendments and any fix a failure needs. Everything else it makes stays under `$env:TEMP`. Run each PowerShell block as one call; each starts by naming `$out` and the isolated data folder.

- [ ] **Step 1: The suite at the branch tip.** Run the full suite in the background and wait for it. Then, in one call: `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass. Record the counts.
- [ ] **Step 2: New and cost on both fixtures,** in one call:

```powershell
$out = Join-Path $env:TEMP 'krs-si-run'; New-Item -ItemType Directory -Force $out | Out-Null
$env:LOCALAPPDATA = "$out\data"; $env:XDG_DATA_HOME = "$out\data"  # an isolated data folder: its own calibration
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"  # typed here, never written into a file
Copy-Item tests\fixtures\usb2_hs.kicad_pcb, tests\fixtures\qspi_clk.kicad_pcb $out
$krs = ".venv\Scripts\kicad-rf-studio.exe"
& $krs new "$out\usb2_hs.kicad_pcb" --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o "$out\proj" *> "$out\new.log"; "new $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs cost "$out\proj" *> "$out\cost.log"; "cost $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs new "$out\qspi_clk.kicad_pcb" --start U1.11 --end U2.6 --interface se50 -o "$out\qspi" *> "$out\qnew.log"; "qnew $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs cost "$out\qspi" *> "$out\qcost.log"; "qcost $LASTEXITCODE" | Add-Content "$out\codes.txt"
```

  Expected codes: `new 0`, `cost 0`, `qnew 0`, `qcost 0` (the first cost calibrates the isolated folder). Read cost.log's I_COST_TIME.
- [ ] **Step 3: The preset, then run,** in the background, waited on. The preset stays normal, or becomes draft in `$out\proj\project.json` when Step 2's worst case exceeds 4 h; either way the record says which and why. Budget several hours: the replica's SI mesh holds about 2.2 M cells (239 × 120 × 77), and dt near 7.3e-14 s makes about 123,000 steps a job to the 9 ns T_max, 8 jobs.

```powershell
$out = Join-Path $env:TEMP 'krs-si-run'
$env:LOCALAPPDATA = "$out\data"; $env:XDG_DATA_HOME = "$out\data"; $env:CSXCAD_INSTALL_PATH = "<openEMS folder>"
$krs = ".venv\Scripts\kicad-rf-studio.exe"
& $krs run "$out\proj" *> "$out\run.log"; "run $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs cost "$out\proj" *> "$out\cost2.log"; "cost2 $LASTEXITCODE" | Add-Content "$out\codes.txt"
```

  Expected codes: `run 0`, `cost2 0`.
- [ ] **Step 4: Read it, against these pre-registered checks.**
  - **Hard:** a failure gets superpowers:systematic-debugging, and a bug is fixed test-first in its module, then Steps 2 and 3 again.
    - every one of the 8 jobs kept (converged, flat or t_max), and no E_ line;
    - no E_DT_FLOOR, E_FIT2D*, E_EDGE_LINT, E_PORT_OPEN, E_PORT_SHORT, E_PORT_BOX, E_PORT_VERTICAL_BOX or E_PORT_PLANE: J1's and the victim's vertical ports and U1's horizontal ones set up;
    - `results/` holds `layout.s8p` alone, 2001 points from 0 to 10 GHz;
    - passivity and reciprocity at every point, in one call:

```powershell
$out = Join-Path $env:TEMP 'krs-si-run'
.venv\Scripts\python.exe -c "import skrf; from kicad_rf_studio.core.post.checks import sigma_max, recip_err; n = skrf.Network(r'$out\proj\results\layout.s8p'); print(sigma_max(n.s).max(), recip_err(n.s).max())"
```

      σ_max ≤ 1.02 and the error ≤ 0.02.
  - **The stop:** each job's verdict, t_cut and residual against the stop window (2 ns) and T_max (9 ns), recorded; a job at t_max is recorded as such, not a failure (design §5.4: P4-D owns a residual that does not decay).
  - **Cost:** cost2's I_COST_PREDICTED against `results.wall_s`, a ratio predicted/measured, recorded; no constant changes (the SI cost refit is plan 4's).
  - **The d fill's twin,** cost only, in one call:

```powershell
$out = Join-Path $env:TEMP 'krs-si-run'
$env:LOCALAPPDATA = "$out\data"; $env:XDG_DATA_HOME = "$out\data"; $env:CSXCAD_INSTALL_PATH = "<openEMS folder>"
Copy-Item -Recurse "$out\proj" "$out\dfill"
.venv\Scripts\python.exe -c "import pathlib; from kicad_rf_studio.core.project import load_project, save_project; p = pathlib.Path(r'$out\dfill\project.json'); d = load_project(p); d['mesh']['max_cell_mm'] = None; d.pop('results', None); save_project(p, d)"
& .venv\Scripts\kicad-rf-studio.exe cost "$out\dfill" *> "$out\dfill.log"; "dfill $LASTEXITCODE" | Add-Content "$out\codes.txt"
```

  - **The 2D work's time and the long cut's two legs,** in one call:

```powershell
$out = Join-Path $env:TEMP 'krs-si-run'
.venv\Scripts\python.exe -c "import time, pathlib; from kicad_rf_studio import pipeline; from kicad_rf_studio.core.mesh.gates import fit2d; project, board, geom, _ = pipeline.load(pathlib.Path(r'$out\proj\project.json')); t = time.perf_counter(); pipeline.si_readout(board, geom, project); a = time.perf_counter() - t; m = pipeline.build_model(project, board, geom); t = time.perf_counter(); fits = fit2d(geom, m.mesh); print(a, time.perf_counter() - t, [(f.section.net, round(f.z0_ref, 3)) for f in fits if f.section.length == 17.49 and f.z0_ref < 70])"
```

  - **Recorded:** the cells (nx × ny × nz) under the SI rule and under the d fill's twin, dt and the cell that sets it, the steps to the stop, the wall time per job, the 2D table's Zdiff on the 17.49 mm run, the 2D table's and fit2d's seconds (plan 1's open issue 8: cs2d's (1, −1) path only if they take more than a few seconds), the long cut's two legs alone (the asymmetry the 2D table's mean-c11 modes accept), and qspi_clk's cells, worst case and short-route note.
- [ ] **Step 5: The record,** `docs/validation/<the run's date, YYYY-MM-DD>-si-first-run.md`, with these sections:
  1. Purpose: plan 2's first real SI run, not a gate.
  2. Inputs: the commands with `<RUN>` for the folder, the versions, the preset and why, and the fresh calibration.
  3. The 2D table and the cost: the rows of the 17.49 mm run, the jobs' breakdown, predicted against measured, the 2D work's time.
  4. The runtime against the design's estimate: cells (SI rule against d fill), dt, steps, per-job wall time; what this means for plan 4's 10–60 machine hours.
  5. The stop: the verdicts under the DC pulse and window_s.
  6. The layout N-port's validity: σ_max and the reciprocity error.
  7. qspi_clk's cost and short-route note.
  8. The stated limits: no SI result yet (plan 3), copper PEC, a lossless dielectric, the region's MUR walls, the ports at the pads, the 2D table a screening.
  9. Next: plan 3 and plan 4.

  It holds no path and no host name.
- [ ] **Step 6: The amendments,** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`:
  - **A-48, §6.4:** a bullet after A-38's:
    > "- **Signal integrity** (Stage 4): `cost` first lists the 2D table, every straight section of every line against the interface's target band with the mask: a net's Z0; a pair's Zdiff, Zodd and Zeven from cs2d's coupled pair where its partner runs alongside at the cut (a partner within 20 µm of the line's width taken at it, the 10 µm simplification's), else 2·Z0 uncoupled; with εeff, length and delay, and a victim's Z0 with no target. When the longest measured route's delay is under a sixth of the link's rise time, it says a run may not be needed. The cost lines count v1's cells at the calibration's speed, which an SI run refreshes as v1's does, and add the runs broken down into the measured lines' ends, the victims' ends and the part ports, and a warning past two hours that advises Draft or a shorter route. A Debye cell counts as a plain one until gate P4-D measures its weight. On <date> the USB 2.0 fixture's 8 jobs took <measured> against <predicted> predicted, on <cells> cells against <d-fill cells> with Stage 1's fill (`docs/validation/<date>-si-first-run.md`). (A-48, Stage 4 plan 2: controller recommendation, owner unavailable.)"
  - **A-49, §10:** the bullet "SI and differential pairs;" is deleted, and the list ends with:
    > "- the Stage 4 design's non-goals (its §3): eye diagrams, masks, jitter and BER; IBIS or IBIS-AMI drivers and an ideal-driver waveform; power integrity and the PDN; radiated emission; a whole-board or whole-plane model; parts of three or more pads on the route as models; back-drilled, blind and buried vias' details; `.kicad_pro` net classes and KiCad 10's tuning profiles; absolute insertion-loss verdicts and standards' masks; segmenting a long net, and more than two ends on one line (A-49, Stage 4 plan 2: controller recommendation, owner unavailable.)"
  - **A-50, §3.2 and §3.3:**
    - §3.2, after the antenna comparison's paragraph: "**Signal integrity** (Stage 4): `new BOARD --start REF.PAD --end REF.PAD --interface NAME` writes an SI project, the interface (usb2-hs, 100base-tx, se50, or custom with `--f-max F` and `--target OHMS`) in place of `--f0`, with `--pair` (the partner by KiCad's pair rule or a DP/DM alias) or `--pair-with REF.PAD:REF.PAD`, and `--victim REF.PAD:REF.PAD` up to twice, each line on nets of its own; `cost`, `run` and `preview` work on it as on a v1 project, `retune` without values rewrites its layout file, and `verify`, `compare` and the retune of part values come with its results. (A-50, Stage 4 plan 2: controller recommendation, owner unavailable.)"
    - §3.3, a last bullet of project.json's list: "an SI project (Stage 4) is schema 3 with `"kind": "si"`, without f0, the harmonics, the band factor and the chain, and with the interface, `f_max_hz`, the link's rise time `rise_s`, the marker `marker_hz`, the target `target_ohm` and its tolerance, the dielectric model (lossless or debye), the stop window `window_s`, `mesh.max_cell_mm`, the lines (each its role, measured or victim, and its chain in the chain's shape) and the pair; its ports run P start, N start, P end, N end, then each victim's start and end, the part ports after them (A-50)."
  - **A-51, §5.1, §5.6 and §5.7:**
    - §5.1, a bullet after A-36's: "- **The SI region** (Stage 4): the ROI is the bounding box of every line's copper, its parts' pads, its ports' pads and their kept reference pads, grown by the protected set's reach, 6 substrate heights of the thinnest dielectric next to the lines' copper layers, inside MUR walls on all six faces as v1's; `new` picks the parts and the lid from that ROI. A victim whose end pads the ROI of the measured lines alone, their references left out, does not cover is refused. (A-51, Stage 4 plan 2: controller recommendation, owner unavailable.)"
    - §5.6, a bullet after A-44's: "- **An SI end's reference** (Stage 4): this section's same-layer reference is taken when its copper lies within the reach of the pad and the port box between them would hold no copper of another net, an unconnected pad's included; else the end gets the vertical port to the plane under its pad; with neither, `new` refuses. A micro-B connector's D+ pad, whose ground pin lies past the ID pin, gets the vertical port. A port longer than λ/20 at f_max in the stack's highest εr, pad to reference, is warned. (A-51)"
    - §5.7, a paragraph after the table: "**Signal integrity** (Stage 4): every two-pad part on a line is a part port, whatever its value, as on an antenna's chain, but a shunt resistor of 1 kΩ or more to a supply or to ground (a pull-up), which is open and named by `new`. The parts off the lines keep this table's roles, and a capacitor whose capacitive reactance, less its package's inductive one, is at most Z0/5 at f_max/2 is copper (A-27's rule), so a decoupling capacitor joins the planes. (A-51)"
  - **A-52, §6.3:** after A-46's paragraph: "An SI project's T_max is also at least the pulse, the residual's window, the flat window and 1 ns, rounded up to a whole ns (9 ns at 10 GHz with the 2 ns window), so that a level held on a short route ends flat rather than at T_max: a 1 % level on 17–37 mm routes reads flat at 7.35–7.47 ns. (A-52, Stage 4 plan 2: controller recommendation, owner unavailable.)"
  - **A-53, §5.4 and §5.5:**
    - §5.4, a bullet after A-43's: "- **The SI mesh rule's margins** (Stage 4): d fills ±1 mm around a measured net's via and a rod's own radius around any other solid rod, on each axis by the rod's own coordinate, and the copper bounds of every staircased track. max_cell is λ/40 at f_max in the largest εeff of the lines' straight sections, solved without the mask; `mesh.max_cell_mm` null keeps this section's d fill. On <date> the USB 2.0 fixture's mesh held <cells> cells against <d-fill cells> with the d fill (`docs/validation/<date>-si-first-run.md`). (A-53, Stage 4 plan 2: controller recommendation, owner unavailable.)"
    - §5.5, a bullet after the fit2d gate's: "- **fit2d on a pair** (Stage 4): each section of a pair's line whose partner runs alongside at the cut is also checked coupled, Zdiff on the mesh against cs2d's pair, its error the larger of the odd and even modes', against the same 3 %; a partner cs2d cannot pair there leaves the line's own check alone. (A-53)"
  - **The Status line** gains, at its end: " On <date>, Stage 4's plan 2 amended §3.2, §3.3, §5.1, §5.4, §5.5, §5.6, §5.7, §6.3, §6.4 and §10 (A-48 to A-53) the same way."
- [ ] **Step 7: Commit.**

```bash
git add docs/validation/<date>-si-first-run.md docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs(validation): the first SI run on the USB 2.0 fixture; Stage 1 spec A-48 to A-53 (Stage 4 design 5.12 item 2, 5.13; controller recommendation, owner unavailable)"
graphify update .
```

- [ ] **Step 8: Close.** Run the whole-branch review, and Step 1 again after any later commit. Fast-forward `main` to the branch locally, delete the branch, and delete `$env:TEMP\krs-si-run`. Nothing is pushed.

---

## Not in this plan

- **Plan 3, the SI results:** S beyond `layout.s{N}p` (the chain file with the part ports closed), the two TDRs and the TDT, mixed mode through `se2gmm` at the target, the skew, NEXT and FEXT, the loss lines, the passivity and reciprocity lines, the relative label and the stated limits on every SI line, the CSV and the summary PNG; the SI retune (E_RETUNE_SI lifted, with a bypass for an SI part's 0R and open values) and verify (E_VERIFY_SI lifted); `compare` with the SI fingerprint and the §5.8 thresholds; §7's amendment.
- **Plan 4, the gates:** P4-B to P4-F with their coupons (each section at least three localising resolution lengths, about 36 mm); the defaults they set (n, max_cell's factor and VIA_MARGIN_MM, the dielectric default and the Debye pole count, the thresholds, the 45° rule); the Debye cell weight in `cost` and the SI cost refit; §5.4's DC-free fallback if P4-D needs it; P4-B against KiCad's calculator only where t/h ≤ 0.035 (plan 1's open issue 1). P4-C also rules on what this plan leaves graded or unskipped (open issues 1–3). P4-G stays the owner's.
- **Plan 5:** the GUI's SI kind (G_SI_LATER lifted), the button's tracks, arcs and vias, the README tutorial, the release check, the acceptance and the exit record.
- **cs2d's (1, −1) path:** `pair` keeps three solves; plan 1's open issue 8 adds the faster path only if Task 11's 2D table or fit2d takes more than a few seconds on the fixtures.
- **Deferred, with their ceilings (ponytail comments):** a pair whose legs differ at a cut by more than 20 µm reads 2·Z0 in the 2D table, and an asymmetric pair's modes come from its legs' mean; a section shorter than its width reads the strip it joins; a pair's two ends on one footprint may take different port kinds, and a blocked first ground pad does not fall back to the next; another rod keeps d over its barrel only; masks stay lossless under Debye; the route length counts every track of the line's nets and no via barrel; a part of three or more pads is found by the nets it bridges; with f1 0 an inductor off the lines is a part port; `si_outputs` copies write_outputs' tail until plan 3.
- **An ESD array joined only inside its package:** a line that enters a flow-through array at pad 1 and leaves at pad 6 with no copper between them is two copper islands of one net, which the connectivity gate reads as E_OPEN_IN_ROI; the fixture's lines run through both pads. Bridging a multi-pad part's same-net pads is an owner item (open issue 9), not this plan's.

## Controller rulings (2026-11-03; binding)

These are the architect's rulings, revised after four reviews. Each is a controller recommendation made while the owner is unavailable.

- Ruling: the order is the fixtures, schema 3, the pair and the lines with their parts, the SI end and the route, `new`, the geometry and mesh, the model spec, cost, run, the pins, the run. The fixtures come first, as in Stage 3's plan 2: every later test builds on them, Task 1 alone runs KiCad's Python, and its gate test stops a layout the lint or fit2d refuses there, not in Task 6. The pair and the lines share one task (one module, one test file); the SI end's helpers get a task of their own, each with a direct test, before `new`, which builds its regions and pieces from the existing primitives. Task 8 stays whole: its coupled cut, fit2d, the table and the cost lines are one gate. The pins come last, once the code they hash is done — design §5.12 item 2, ponytail — cost if wrong: a reorder.
- Ruling: the fixtures' geometry, from KiCad 9's footprint files, checked on a text replica read by the repo's importer, every line measured, at n 2: no edge-lint hit under v1's d fill or the SI rule, fit2d at most 2.3 %, no copper of two nets closer than 0.15 mm. The first draft's layout failed the lint at about a dozen y edges, read its pair's fit2d 6–9 % off, kept 0.092 mm between a jog and U2.2, read qspi_clk's QFN as a part across a port and cut 2D rows through 0.25 mm jogs. Every line shares one set of mesh lines per axis, and edges of two features 15–25 µm apart read fit2d 5.6–7 % off (50 µm passed), so: the pair 0.3 mm at a 0.25 mm gap (90.3 Ω with the mask, 95.4 bare), its inner edges on J1's and U1's inner pin edges; 0.6 mm through U2's 0.6 mm pads, U2.2's via in its pad; jogs of 0.675 mm only; the resistors entered at the lines' own y; AUX 0.2 mm, 0.625 mm off; the neck 0.2 mm on each line's inner side (117.4 Ω); the slot at x 116–117, off the long run's cut at 114; the 45° rise 1.5 mm (1 mm read 4.1 %); the QSPI line 0.33 mm (50.0 Ω), its top edge on U1.11's; U1.16 on +3V3; C1's tracks on its pads (±0.48 mm) — design §5.11 and §6 (the builder's) — cost if wrong: the fixtures are regenerated, and the tests' coordinates move with them.
- Ruling: project.json keeps each line's chain in v1's shape, as the design says, and no top-level chain. `chain_of` and `parts` merge the lines, and `ends` and `model_spec` iterate `parts(project).values()`, v1's order for v1 (the pins prove it). A part on two lines is stored once, in the first line's chain; a line whose nets meet an earlier line's (a `--pair-with` on the measured pads, a victim on a measured net) is E_SI_LINE_SHARED, so no line has a third end — design §5.1, §3 — cost if wrong: four readers move to a top-level chain.
- Ruling: the pair is `{"p", "n", "by"}` (the measured lines' first nets and "rule", "alias" or "given"), and P is the start pad's net whatever its suffix; the partner's ends are, at each end's footprint, the one pad of that end's own net's partner, so a series resistor between the ends still pairs — design §5.1 — cost if wrong: one field.
- Ruling: KiCad's rule first, the alias only when KiCad's complement is no net of the board, both case-sensitive as KiCad's is; the plan gives `partner_net`'s docstring and the alias's pattern, and the test drives the body — design §6 (the alias list) — cost if wrong: one regular expression.
- Ruling: an SI end takes v1's same-layer reference only within the reach (6 × the lines' substrate height) and across a box that holds no other copper, by one `_apart_axis` that place() and clear_between share; else the vertical port; else E_SI_NO_REFERENCE at `new`. A micro-B's D+ and D- go vertical, a QFN pin to its exposed pad stays horizontal, a far test point goes vertical. "No reference within the reach" is read as "none a port can use": a blocked box is E_PORT_BOX at `cost`. Any SI port longer than λ/20 at f_max in the stack's highest εr, pad to reference, is W_SI_LONG_PORT — design §5.5, Stage 1 §5.6 (A-6), plan 1's open issue 2 — cost if wrong: a connector end reads E_PORT_BOX until edited by hand.
- Ruling: `new` picks the parts and the lid from the region build_geometry builds (its kept references and the lines' layers): a QFN end's exposed-pad reference widens the ROI, and qspi_clk's C1 lies only in that band, 0.42 mm past the references-None ROI. That region serves the victim check alone — design §5.1, §5.2 — cost if wrong: one call.
- Ruling: `mesh.max_cell_mm` is a project field, λ_eff(f_max)/40 from `new` and null for Stage 1's d fill, so P4-C's twin is a field edit. Its εeff, and the round trip's, is the largest single-line εeff of the lines' sections without the mask, each in its own layer's box (usb2_hs: 3.28 from the 0.6 mm run through U2, max_cell 0.414 mm; qspi_clk: 3.08, 0.427 mm), else the largest εr. The mask would raise it about 8 %: max_cell about 4 % coarser and the round trip about 4 % short, harmless while the window and T_max sit on their floors — design §5.3, §5.4 — cost if wrong: a few % on max_cell and T_max.
- Ruling: T_max = max(plan 1's si_t_max, 2·t0 + window_s + flat_s + 1 ns), rounded up to a whole ns, in `spec.si_t_max`. The residual's window holds the pulse's 0 dB peak, so no held level reads flat before t0 + window_s + flat_s (7.14 ns at 10 GHz); the draft's 7 ns came first. Replayed, a 1 % held level reads flat at 7.35–7.47 ns on 17–37 mm routes. Both fixtures sit on the 9 ns floor, plan 1's 10 ns (100 mm) and 25 ns (300 mm) stand, and a converging job stops earlier: only the worst case grows — plan 1's open issue 4 — cost if wrong: a few ns a job.
- Ruling: VIA_MARGIN_MM 1.0 around a measured net's via (r1's), and a rod's own radius around any other solid rod, every solid rod spanned on each axis by its own coordinate (one centred just past the extent keeps its lines); staircased tracks' copper bounds are spans on both axes; a rod that is not solid is snapped to the lines; with max_cell None nothing changes — plan 1's carried item, design §5.3 — cost if wrong: one constant in plan 4.
- Ruling: the region's reach is REACH_H (6) substrate heights of the lines' thinnest dielectric (`region.expand_h` 6, as the antenna's measured region), and a victim end must lie wholly in the ROI the measured lines set, references left out, checked before any reference is chosen — design §5.1, §5.2 — cost if wrong: one comparison.
- Ruling: an SI project's materials are κ-free; Debye goes on each substrate material with a tan δ, the copper slabs' fills at their neighbours' means, and the masks stay plain. The default is lossless until P4-D. debye()'s ValueErrors (below vacuum, and now no pole kept) become E_DEBYE_FIT at model_spec, so their non-ASCII text never reaches a console — plan 1's carried items, design §5.3 — cost if wrong: one material rule.
- Ruling: the 2D table lists every section of every line, a coupled section once per leg, each in its own layer's box. A partner strip within 2·SIMPLIFY of the signal's width takes it (cs2d's pair needs mirror images to 1e-9 mm, and the simplification leaves real legs 0.3–3 µm apart: usb2_hs's MCU run, every cut of usb2_hs_45); wider legs read Zdiff = 2·Z0 as a leg alone against the same band; an asymmetric pair's modes are cs2d's from the legs' mean c11, a screening (usb2_hs's long cut: the legs alone 51.01 and 51.10 Ω); coupled delays are the odd mode's. The short-route note takes the longest measured route at its rows' largest εeff, so "short" is never claimed early. fit2d checks a coupled section's Zdiff, the worse of its odd and even errors, against v1's 3 %, beside each leg's own check; a pair cs2d cannot solve keeps the leg's check alone. A section shorter than its width gets no skip rule before P4-C — design §5.3, §5.9 — cost if wrong: one table's rows, one Fit per coupled section.
- Ruling: the SI run's grid is plan 1's uniform grid from DC (2001 points at 10 GHz), so `layout.s{N}p` holds the measured DC point plan 3's TDR reads; its marker is the grid point nearest the marker frequency (240 MHz exactly, 133 MHz at 135, 62.5 MHz at 60), never dropped. Its lines are I_BASIS, flagged jobs, the gate lines at GATES_SI and I_OUTPUTS: no SI number before plan 3's label and limits; `results.loss_expected` is null. The fake's `synth_records` drives dc_pulse's Gaussian when f1 is 0 (star(f, 8) back within 1.2e-6, DC at 0 dB; v1's pulse there leaves S 6.3e-3 off and DC at −106 dB) — design §5.4, §5.6, §5.12 — cost if wrong: one grid.
- Ruling: `verify` refuses an SI project (E_VERIFY_SI) and so does a `retune` with part values (E_RETUNE_SI), until plan 3: the layout file a retune writes does not depend on them; `retune` alone rewrites it, and `compare` already refuses (E_COMPARE_KIND) — design §5.7, §5.12 — cost if wrong: two guards.
- Ruling: W_GATE_LIMITS_SI is a code of its own (W_GATE_LIMITS names 0.03 and 0.8); E_PORT_VERTICAL_BOX is vertical()'s own refusal, since E_PORT_BOX's advice names the copper between two pads (plan 1's test of it changes deliberately); E_NEW_KIND's text changes to name the SI form, the one deliberate msgid change; Advanced gives an SI project its own defaults, so a reset writes no v1 value into it — design §5.3, pt-BR design §6 — cost if wrong: a few msgstrs.
- Ruling: the SI golden pins cover the five fixtures' new-time projects, notes, model specs and blocking gates everywhere, as golden_antenna's models, and their 2D tables where golden_v1.env() matches, as its readouts; `golden_si` takes the commands from test_cli_si's `si_args`; no run-output pins before plan 3 — design §5.11 ("they are the regression tests too") — cost if wrong: one JSON re-recorded by ruling.
- Ruling: this plan's pt-BR glossary, by the pt-BR design's §6.1: signal integrity — integridade de sinal; differential pair — par diferencial; line — linha; measured line — linha medida; victim — vítima; interface — interface; target (impedance) — alvo; target band — faixa alvo; rise time — tempo de subida; marker — marcador; localising TDR — TDR de localização; plane — plano; vertical port — porta vertical; sheet (a vertical port's) — folha; stop window — janela de parada; dielectric — dielétrico; route — rota; delay — atraso; coupled — acoplada; odd/even (mode) — ímpar/par; electrically short — eletricamente curta; single-ended — single-ended; pull-up — pull-up; common-mode choke — choke de modo comum; link — enlace — cost if wrong: a native speaker changes a few msgstrs.
- Ruling: A-48 (§6.4), A-49 (§10), A-50 (§3.2, §3.3), A-51 (§5.1, §5.6, §5.7), A-52 (§6.3) and A-53 (§5.4, §5.5) land in Task 11 with the run's numbers; design §5.13 names §6.4 and §10, and the others join them because the code and the Stage 1 spec must agree, as A-32 did for the antennas: A-43 states the SI mesh rule, A-53 its margins and fit2d's coupled check — design §5.13 and §6 — cost if wrong: a paragraph moved.
- Ruling (disclosure): the architect's and the reviser's checks ran only in a scratch folder with the repo's venv: cs2d's pair and single line on the fixtures' cross-sections; dc_pulse-driven records through `s_matrix` on `uniform_grid(10e9)`; a text replica of the five boards from KiCad 9's footprint files (planes as rectangles with square antipads) through the repo's importer, build_geometry, both mesh rules with the edge lint, fit2d, cs2d's pair at every coupled cut, a clearance sweep and an emulation of `new`'s regions, references and parts; and the stop rule replayed with a held level. KiCad's footprint files were read, read-only; no KiCad binary, no openEMS run, no suite; nothing was written in the repo or its venv — cost if wrong: none.

## Open issues, ruled by the controller (2026-11-03; owner unavailable)

The reviser's open issues, each with the ruling it recommends. On 2026-11-03 the controller confirmed all nine as written, each a controller recommendation while the owner is unavailable. Issue 4's stop also covers Task 6 and Task 8 when a generated board, not the replica, fails the lint or fit2d there: the implementer reports BLOCKED with the board, the hit and its coordinates, and the controller rules on the layout; no limit and no assertion loosens to pass.

1. **Real boards' shared mesh lines.** Every line shares one set of lines per axis, so the edges of two features 15–25 µm apart (a 0.3 mm track into a 0.25 mm QFN pin, a micro-B's 0.65 mm pitch beside a 0.5 mm pair) fail the edge lint after its re-mesh or read fit2d 5–7 % off, as the first fixture layout did; real boards will meet it before plan 4. Recommendation: the fixtures stay clear of it (Task 1's gate test) and Task 11's record says so; P4-C measures it on such a board and rules between merging near-coincident edges of different features and a per-feature exemption. — cost if wrong: real SI boards read E_EDGE_LINT or E_FIT2D until plan 4.
2. **Sections that are no line's.** A section shorter than its width (the first draft's 0.25 mm jogs) has no bare cut, and its cut reads the strips it joins: Z0 of 2–3 Ω in the table, fit2d errors above 200 %. Recommendation: no skip rule in plan 2 (fit2d applies unchanged, design §5.3, and the fixtures have none); P4-C sets one for the table and fit2d alike. — cost if wrong: a real board's jog blocks on E_FIT2D.
3. **What the SI rule grades.** Another solid rod keeps d over its barrel only, so its ring and the planes' antipads grade, and unprotected pads inside the extent (a micro-B's VBUS and ID pins, a QFN's unconnected pins) get no lines of their own, where v1's d fill resolved both. Recommendation: P4-C's twin measures them; wider spans now would turn a via fence into a d fill along the route. — cost if wrong: a fixture's TDR moves by tenths of an ohm.
4. **The replica against pcbnew.** The checks read KiCad's own pads but square antipads where pcbnew fills round ones. Recommendation: Task 1's gate test on the generated boards is the check; a failure stops Task 1 for a ruling, never a test edit. — cost if wrong: one layout iteration.
5. **The first run's time.** About 2.2 M cells and 123,000 steps a job to 9 ns: 8 jobs may take several hours. Recommendation: Task 11's preset rule (normal, or draft past 4 h of worst case), recorded. — cost if wrong: an afternoon.
6. **The 9 ns floor's cost.** The worst case of a short route grows about 29 % over the draft's 7 ns, while a held level now stops flat near 7.4 ns and a converging job earlier. Recommendation: keep it, as plan 1's open issue 4 asked for a flat verdict. — cost if wrong: two ns a job.
7. **Asymmetric pairs in the 2D table.** cs2d's pair reads its modes from the legs' mean c11; a victim or a pour beside one leg makes them differ. Recommendation: a screening, the asymmetry recorded on usb2_hs in Task 11; P4-B's victim case checks it against the run. — cost if wrong: the table's Zdiff off by the asymmetry.
8. **The fixtures' impedances.** The pair reads 90.3 Ω with the mask at a 0.25 mm gap (the draft's 0.2 mm gap read 86.4 Ω, not the 89 Ω its ruling gave), the QSPI line 50.0 Ω. Recommendation: Task 1's facts; P4-B's coupons stay "a 90 Ω and a 100 Ω pair on about 0.2 mm". — cost if wrong: none.
9. **The owner's review.** The fixtures' redesign, A-48 to A-53, the 9 ns floor, E_SI_LINE_SHARED and E_RETUNE_SI are controller recommendations; an ESD array joined only inside its package, and bridging a multi-pad part's same-net pads, stay owner items. The Stage 4 exit record carries them. — cost if wrong: none.
