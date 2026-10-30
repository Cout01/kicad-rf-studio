# Stage 3 Plan 2: The Antenna Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A user creates an antenna project from a KiCad board with `new BOARD --start REF.PAD --antenna REF --band F_LO:F_HI`. `cost` and `run` simulate the whole board in a PML_8 air box. A run with no part port writes S11, the resonance, the bandwidth, the efficiencies, the gains, the three cuts and their files, each labelled relative and stated with its limits.

**Architecture:**
- **Schema 2.** project.json schema 2 (`"kind": "antenna"`) reuses v1's chain, ports, parts and mesh shapes. It adds the band, the antenna (its reference and its feed-to-ground join pads), the air gap, the boundary and the far-field fields. Code branches on `core.project.antenna(data)`, which reads the schema, so no v1 path changes.
- **Import and geometry.** The importer records which footprint drew each copper graphic and which footprints hold a keep-out. `load` gives the antenna's netless copper the feed pad's net, so v1's region, protected set, connectivity, sections and mesh rule take the antenna as measured copper. One rule is added, for an antenna's geometry alone: an edge that another copper layer's opposite edge meets passes the lint's third test. `board_region` keeps the ROI as the measured region and sets the walls to the board's box.
- **Model.** `build_model` grades the mesh into an air box up to λ(f2)/20 and adds PML_8. `model_spec` writes `"boundary"`, `"nf2ff"` (only when there is no part port) and `"join"`. The setup worker cuts the join's mesh nodes out of the port-short check. `cost` weights the PML cells with gate P3-A's two corrections. `_run` saves S, then transforms the far field, and `write_outputs` writes the antenna's lines and files.

**Tech Stack:**
- Python ≥ 3.11 (dev venv 3.14.2), numpy, shapely, h5py, matplotlib and scikit-rf (its Smith chart), with the repo's `smooth_mesh_lines`. No new dependency.
- openEMS 0.37.0 and CSXCAD 0.7.0. Only workers import them; Task 12 runs them for real.
- KiCad 9's bundled Python with pcbnew, for `tools/make_fixtures.py` only (Task 1).
- pytest; `tools/catalog.py` (Babel, dev extra).

**Spec:**
- `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md` (binding): §5.12 item 2, with §1, §3, §4, §5.1–§5.6, §5.9, §5.10's CLI form, §5.11's fixtures paragraph and §5.13.
- The Stage 1 spec, `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`, where the design reuses it: §1.1, §3, §4.1–§4.6, §5.1–§5.8, §6.3, §6.4, §7, §9 and §10.
- Task 12 lands A-26 (§1.1), A-27 (§5.1), A-28 (§6.3), A-29 (§6.4), A-30 (§10), A-31 (§5.5) and A-32 (§3.2, §3.3, §7.4, §7.5), with their exact text.
- Binding for cost: gate P3-A's report, `docs/validation/2026-10-29-p3-a.md` and `.json`, §4.
- Research (git-ignored): `.superpowers/sdd/stage3-research/` r1, r2 and r3.

**Branch:** `stage3-plan2`, from `main` at `47aff31`. This plan is `docs/superpowers/plans/2026-10-29-stage3-plan2-antenna-project.md`. Commands run from the repo root with `.venv/Scripts/python`. Line references are `main`'s at `47aff31`; if an earlier task moved a line, find it by its quoted text.

**Before Task 1 (the controller):**
1. `git switch -c stage3-plan2 main`. Then `git diff --stat 47aff31 HEAD -- src tests tools po pyproject.toml` must print nothing.
2. Commit this plan on the branch.
3. After Task 12: the whole-branch review, a local fast-forward merge into `main`, and delete the branch. Nothing is pushed.

## Global Constraints

- **v1 byte for byte** (design §3, §4). v1 projects stay at schema 1. Their model specs, `spec_hash`, `model.json`, verify's model, `project.json`, `new`'s lines and `results/` files stay as `tests/test_golden_v1.py` pins them. A task that moves a pin is wrong: stop and get a ruling, never re-record.
- **Schema 2 only for antennas.** Every antenna branch tests `core.project.antenna(data)` (the schema). No v1 dict gains a key: not `kind`, `far_field`, `flat_s`, `join`, `boundary`, `nf2ff` or `results.far_field`. The lint's two-layer exemption is computed only for an antenna's geometry (`Geometry.antenna`), so every v1 mesh runs v1's code.
- **The whole board in an air box** under PML_8 on all six faces, with nothing in the absorber. E_METAL_IN_PML (plan 1) gates it. The gap defaults to λ/4 at f_lo, and the 8 PML lines lie outside it.
- **Far field.** Frequency-domain only, at 1 to 11 frequencies inside [f1, f2], f0 first. Every transform passes `read_cached=False` with a file of its own (plan 1's worker).
- **openEMS stays in the worker** (Stage 1 §3.1): the CLI, the orchestrator and `core.post` never import openEMS or CSXCAD.
- **Messages:**
  - Every new user-facing string is a `CATALOG` code with its pt-BR msgstr in `po/pt_BR.po`, in the same task. The task compiles it with `.venv/Scripts/python tools/catalog.py` (run, set the msgstr, run again), by the pt-BR design's §6 glossary and this plan's glossary ruling.
  - A word passed as a parameter is a `T_` code.
  - Numbers keep the decimal point.
  - A msgstr keeps every identifier, option, quoted text, backticked command and dotted number of its msgid (`test_sexpr.py`'s KEEP).
  - A table below writes `\|` for a pipe inside a cell: the msgid and msgstr hold `|S11|`, with no backslash.
- **Tests:** test-first.
  - Tier (a) tests never run openEMS, KiCad, the network or a build. They use `tests/fake_worker.py` (through the `fake` and `calibrated` fixtures) and committed fixtures.
  - `KrsError` tests check `.code` and `.params`.
  - **Prototype numbers.** A number this plan gives as a prototype's (the ROI bounds, the sections, LOCAL_X, the line counts, the join box, the stop-rule times) that the code misses stops the task: report both values and the formula that differs. The pin changes only on a ruling.
  - **Isolation:** tests never touch a real KiCad folder, the Documents folder, KiCad's settings or the real data folder. Task 12's runs set LOCALAPPDATA and XDG_DATA_HOME to a folder under `$env:TEMP` in the same call, and type `CSXCAD_INSTALL_PATH` in the call, never in a file.
- **Full suite** before every commit: `.venv/Scripts/python -m pytest -q`, about 18 minutes. Run it once, in the background, with nothing beside it, and wait for it to exit.
- **Git:**
  - No push. The pre-commit privacy gate runs on every commit, so never use `--no-verify`.
  - No committed file holds an absolute user path, a drive letter followed by a colon and a slash, an e-mail address or a private name. Write `<openEMS folder>`, `<KiCad 9 bin folder>` and `<RUN>`.
  - No commit message carries a co-author line. Use the messages as given.
- **Files:** every new `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`. Code and docs are in English.
- **Workflow:**
  - Run `graphify query "<question>"` before reading code, and `graphify update .` after each commit.
  - Ponytail: choose the laziest solution that works, in the fewest files. Reuse the importer, the tracer, `build_region`, `make_project`, the protected set, `smooth_mesh_lines`, `with_pml`, `metal_in_pml`, plan 1's keys, worker modes and reader, the fake worker and `make_fixtures.py`.
  - Put a `ponytail:` comment naming the ceiling on each corner cut, in the step that writes the code.

## Review Focus

1. **A module or a chip antenna picked as `--antenna`.** The owner's ESP32 work uses modules (design risk 8).
   - KiCad 9's own library has the traps: six chip antennas carry keep-outs (Pulse_W3000, AVX_M620720, …), and Antenova_SR4G013_GPS draws a 0.8 mm² net-tie stub between its pads.
   - Expected: refused before anything is written. E_ANTENNA_MODULE is raised for an `RF_Module:` footprint, or for another footprint with a keep-out and no radiator drawn. E_ANTENNA_CHIP is raised for an AE or `RF_Antenna:` footprint whose copper graphics, if any, are no larger than its pads.
   - Each message points to v1's chain up to the pad.
   - Checks: Task 2's `test_modules_chip_antennas_and_other_footprints_are_refused` (with a keep-out chip antenna and a stub); Task 4's `test_new_refuses_a_module_before_writing`.
2. **An inverted-F whose own copper shorts its feed to ground** (KiCad's `Texas_SWRA117D_*`, pads on RF and GND).
   - v1's tracer reads such a footprint as a shunt part. Connectivity reads E_SHORT_IN_ROI, and the post-setup check reads E_PORT_SHORT.
   - Expected: the antenna ends the chain and is never a part. The join through its own GND pad is accepted by both checks, and nowhere else. The port-short cut is decided on mesh nodes, never on the dump's float32 metres.
   - Checks: Task 2's `test_the_antenna_ends_the_chain_and_is_never_a_part`; Task 6's `test_the_inverted_f_join_is_accepted_and_tied_to_its_pads` and `test_a_join_accepts_touches_within_it_and_no_other`; Task 8's `test_a_cut_join_separates_the_copper_it_held`. Task 12's real setups (ifa2g4's run and the pi variant's cost, whose shunt ports also need the cut) check no E_PORT_SHORT.
3. **A two-layer antenna whose top and bottom traces' edges coincide** (KiCad's `Texas_SWRA416_868MHz_915MHz`), with diagonal copper, and v1's models left as they were.
   - Coincident opposite edges can never pass v1's edge lint, so E_EDGE_LINT would block every such antenna. Diagonal footprint copper is no track, so v1 would never warn it as staircased.
   - The exemption must tell layers apart and reach `xy_lines`' slot fallback (`_faults`): by position alone it broke v1's `test_an_axis_the_slot_depth_would_break_keeps_its_as_built_lines[lint]`.
   - Expected: the antenna's model builds, with W_STAIRCASED; the same geometry without `antenna` still reads E_EDGE_LINT, so v1 is unchanged by construction.
   - Checks: Task 5's `test_only_opposite_edges_of_two_layers_within_20_um_are_paired` and `test_an_exempt_edge_passes_the_third_test_alone`; Task 6's `test_the_two_layer_exemption_is_the_antennas_alone` and `test_each_antenna_fixture_builds_its_model[meander915]`; `tests/test_golden_v1.py`.
4. **Parts off the chain on the antenna's board**: a decoupling capacitor beside the radio, a small RF capacitor, a resistor across the board, a bead.
   - v1 would leave them open, make an inductor a port, or mesh a far grid part's pads fine across the whole board. Design §5.3's wording, a self-resonance below 3·f2, would short every 0402 capacitor of 0.63 pF or more at 2.4 GHz, though a 1 pF one is −58 Ω there.
   - Expected: never a port. A capacitor close to a short at the pulse's centre (its capacitive reactance, less its package's inductive one, at most Z0/5: 3.75 pF and up in 0402 at 2.4 GHz, 13.7 pF at 915 MHz) is copper. A grid part is in the grid only in the measured region and open past it. An inductor, a bead, an unread value or any other capacitor is open.
   - Checks: Task 3's `test_the_rest_of_an_antennas_board_is_never_a_port` and `test_an_antennas_parts_are_every_two_pad_part_off_the_chain`; Task 4's ifa2g4 C1.
5. **A band typed wrong or a project edited by hand** (`--band 868MHz:2483.5MHz` for two bands, `2400MHz:24835MHz` for a lost point, `2400:2483.5` with no unit; a band, f0 or far field edited in project.json).
   - Expected: refused before the air mesh explodes, or warned:
     - E_BAD_BAND for text that does not read, or F_LO ≥ F_HI;
     - E_BAND_WIDE above an octave in `new`, and E_PROJECT_FIELD for the same in project.json, or for f0 outside the band, or a far field not led by f0;
     - W_F0_RANGE for a centre outside 1 MHz–100 GHz;
     - W_AIR_BOX for MUR or a gap under λ/4.
   - Checks: Task 4's `test_a_band_that_does_not_read_is_refused`, `test_a_band_wider_than_an_octave_is_refused` and `test_a_band_with_no_unit_is_warned`; Task 3's `test_a_schema_2_field_out_of_its_range_is_named`; Task 6's `test_an_air_box_outside_the_tested_setting_is_warned`.

---

## File structure

```
tools/make_fixtures.py, NOTICE, tests/fixtures/{ifa2g4,ifa2g4_pi,meander915}.{kicad_pcb,pads.json}   # T1
src/kicad_rf_studio/core/kicad/board.py, tracer.py                       # T2 CopperArea.ref, Footprint.keepout; kinds, feed, adopt
src/kicad_rf_studio/core/project.py, core/geometry/region.py, core/model/parts.py, gui/control.py
                                                                         # T3 schema 2, pulse_band, board_region, roles, GUI guard
src/kicad_rf_studio/cli.py, core/kicad/values.py                         # T4 _load/_port/_write, new --antenna, parse_band
src/kicad_rf_studio/core/geometry/__init__.py (Geometry.antenna), core/mesh/__init__.py, rule.py, gates.py
                                                                         # T5 the two-layer exemption, antenna only
src/kicad_rf_studio/pipeline.py (load), core/geometry/__init__.py, copper.py, sections.py, lid.py
                                                                         # T6 adopt in load, join, staircase, lid, air box warning
src/kicad_rf_studio/core/model/spec.py, csx.py, stoprule.py, pipeline.py (build_model)                        # T7
src/kicad_rf_studio/core/model/readers.py, worker.py, pipeline.py (far_field)                                 # T8
src/kicad_rf_studio/runs.py, core/model/spec.py (cell_split), pipeline.py (cost_notes, prepare, cost, simulate)  # T9
src/kicad_rf_studio/core/post/farfield.py, waves.py, outputs.py (write), antenna.py (new)                     # T10
src/kicad_rf_studio/pipeline.py (_run, write_outputs, chain_results, antenna_outputs)                         # T11
src/kicad_rf_studio/core/messages.py, po/*, locale/pt_BR/LC_MESSAGES/kicad_rf_studio.mo                       # T2-T4, T6, T9, T10
tests/test_antenna_kicad.py, test_cli_antenna.py, test_antenna_geometry.py, test_antenna_model.py,
  test_post_antenna.py, test_run_antenna.py (new); test_fixtures.py, test_pads.py, test_project.py,
  test_model_parts.py, test_geometry_region.py, test_gui_control.py, test_cli_new.py, test_mesh_rule.py, test_gates.py,
  test_geometry_copper.py, test_stoprule.py, test_readers.py, test_worker.py, test_cost_model.py,
  test_post_farfield.py, test_post_outputs.py, test_run.py, test_sexpr.py
docs/validation/<date>-antenna-first-run.md, the Stage 1 spec            # T12
```

---

### Task 1 [code]: The fixtures

**Files:**
- Modify: `tools/make_fixtures.py`, `NOTICE`, `tests/test_fixtures.py` (NAMES) and `tests/test_pads.py`.
- Written by the tool: `tests/fixtures/ifa2g4.kicad_pcb`, `ifa2g4_pi.kicad_pcb` and `meander915.kicad_pcb`, each with its `.pads.json`.

**Interfaces:**
- Produces:
  - The three boards, described below.
  - `make_fixtures.main(out, names=())`, which builds only `names` (all of BOARDS when empty).
  - `new_board(path, seed, rules=RULES)`, `zone(b, layer, corners, clearance=0.15)` and `fence(b, points, box, keep=0.5)`.
  - `ANTENNA_RULES`, `radio`, `to_gnd` and `antenna_board`.
- Facts later tasks rely on (KiCad's frame, mm; the importer's y is negated):
  - **ifa2g4:**
    - AE1, `RF_Antenna:Texas_SWRA117D_2.4GHz_Left`, sits at (100, 100). AE1.1 is on RF and AE1.2 (thru_hole) on GND.
    - U1 is a `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` "RFIC" turned 270°. U1.1 is RF at (100, 111.975) and U1.2 is GND at (98.73, 111.975).
    - A 1.35 mm RF track runs from (100, 100) to (100, 110), then a 0.6 mm track to U1.1.
    - C1 is 100nF 0402, VDD–GND, at (102, 116.925).
    - Both GND zones run from y = 99.75, 0.5 mm inside the outline (87, 94)–(127, 124), with a 1 mm rule clearance.
  - **ifa2g4_pi:** as ifa2g4, with U1.1 on RF_A, and:
    - C3 1pF (RF, GND) at (100.48, 104);
    - L1 2.7nH at 90° (pad 1 RF_A, pad 2 RF) at (100, 106);
    - C2 1pF (RF_A, GND) at (100.48, 108);
    - 0.6 mm RF and RF_A tracks.
  - **meander915:** AE1, `RF_Antenna:Texas_SWRA416_868MHz_915MHz`, at (110, 100), with AE1.1 on RF at (101, 105.9) and 19 unnamed holes. U1.1 is at (101, 111.975), with the same tracks as ifa2g4 from (101, 105.9). There is no C1. The ground runs from y = 106.5, with outline (89, 92.5)–(129, 146.5).

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_fixtures.py`, NAMES gains `"ifa2g4", "ifa2g4_pi", "meander915"`.
  - In `tests/test_pads.py`, `test_pads_match_pcbnew`'s parametrize list gains the same three, and imports gain `Counter`. Add:

```python
def test_the_antenna_fixtures():  # Stage 3 design 5.11: KiCad's own RF_Antenna footprints on a stated ground
    ifa, pi, mea = (load_board(FIX / f"{n}.kicad_pcb") for n in ("ifa2g4", "ifa2g4_pi", "meander915"))
    assert ifa.footprints["AE1"].lib_id == pi.footprints["AE1"].lib_id == "RF_Antenna:Texas_SWRA117D_2.4GHz_Left"
    assert mea.footprints["AE1"].lib_id == "RF_Antenna:Texas_SWRA416_868MHz_915MHz"
    assert (ifa.outline.bounds, mea.outline.bounds) == ((87.0, -124.0, 127.0, -94.0), (89.0, -146.5, 129.0, -92.5))
    for b in (ifa, pi):
        assert [(p.net, p.kind) for p in b.footprints["AE1"].pads] == [("RF", "connect"), ("GND", "thru_hole")]
    assert [(a.layer, a.net) for a in ifa.areas if a.source == "graphic"] == [("F.Cu", "")]
    assert Counter(a.layer for a in mea.areas if a.source == "graphic") == {"F.Cu": 10, "B.Cu": 27}
    assert [p.number for p in mea.footprints["AE1"].pads].count("") == 19
    for b, x in ((ifa, 100.0), (pi, 100.0), (mea, 101.0)):
        assert b.pads("U1.1")[0].center == pytest.approx((x, -111.975)) and b.pads("U1.2")[0].net == "GND"
    assert {r: (fp.value, [p.net for p in fp.pads]) for r, fp in pi.footprints.items() if r in ("C2", "L1", "C3")} == {
        "C2": ("1pF", ["RF_A", "GND"]), "L1": ("2.7nH", ["RF_A", "RF"]), "C3": ("1pF", ["RF", "GND"])}
    assert ifa.footprints["C1"].value == "100nF" and "C1" not in mea.footprints
    for b in (ifa, pi, mea):
        assert {(a.layer, a.net) for a in b.areas if a.source == "zone"} == {("F.Cu", "GND"), ("B.Cu", "GND")}
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_fixtures.py tests/test_pads.py -q`. Expected: FAIL with `FileNotFoundError` on `ifa2g4.kicad_pcb`.
- [ ] **Step 3: `tools/make_fixtures.py`.**
  - **Parameters:**
    - `new_board` gains `rules=RULES`, written to the `.kicad_dru` in place of `RULES`.
    - `zone` gains `clearance=0.15`, its local clearance.
    - `fence` gains `keep=0.5`, the HitTest distance to blockers.
    - `main(out, names=())` builds `names or BOARDS`. `__main__` calls `main(sys.argv[1], sys.argv[2:])`.
    - The module docstring adds the names argument: "a rerun of named boards rewrites only those".
  - **Add, as given:**

```python
# an antenna board's 50 Ω microstrip keeps its top ground 1 mm off: the fill's clearance, and the gap fit2d reads
ANTENNA_RULES = '(version 1)\n(rule "microstrip gap" (constraint clearance (min 1mm)))\n'


def radio(b, at, rf="RF"):
    """U1, a SOIC-8 "RFIC" turned 270 degrees at `at`: pin 1 (`rf`) on top, 8 VDD, the rest GND."""
    nets = {str(k): "GND" for k in range(2, 8)} | {"1": rf, "8": "VDD"}
    return place(b, "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "U1", "RFIC", at, 270, nets)


def to_gnd(b, pad):
    """A GND via 1.2 mm right of `pad` (x, y), and a 0.3 mm GND track to it."""
    via(b, (pad[0] + 1.2, pad[1]))
    track(b, "GND", 0.3, pad, (pad[0] + 1.2, pad[1]))


def antenna_board(b, lib, ae_nets, ae_at, outline, ground_top, radio_y, pi=False, decap=True, pitch=5.0):
    """A printed antenna on a rectangular ground (Stage 3 design 5.11): AE1 from `lib` at `ae_at`, the board `outline`
    (x0, y0, x1, y1), GND zones on both layers from y = `ground_top` down, 0.5 mm inside the outline, 1 mm clear of
    other nets; U1 straight below AE1's feed pad, pin 1's top end at `radio_y`, fed by a 1.35 mm microstrip and a 0.6
    mm stub into pin 1, or with `pi` C3 (shunt), L1 (series) and C2 (shunt) on a 0.6 mm line; `decap` a 100 nF C1
    beside pin 8; GND stitching vias every `pitch` mm over the ground."""
    ae = place(b, lib, "AE1", lib.split(":")[1], ae_at, 0, ae_nets)
    fx, fy = pad_at(ae, "1")
    radio(b, (fx - 1.905, radio_y + 3.45), "RF_A" if pi else "RF")  # pin 1 at (fx, radio_y + 0.975)
    x0, y0, x1, y1 = outline
    rect(b, pcbnew.Edge_Cuts, *outline)
    if pi:
        c3 = place(b, "Capacitor_SMD:C_0402_1005Metric", "C3", "1pF", (fx + 0.48, fy + 4.0), 0, {"1": "RF", "2": "GND"})
        l1 = place(b, "Inductor_SMD:L_0402_1005Metric", "L1", "2.7nH", (fx, fy + 6.0), 90, {"1": "RF_A", "2": "RF"})
        c2 = place(b, "Capacitor_SMD:C_0402_1005Metric", "C2", "1pF", (fx + 0.48, fy + 8.0), 0,
                   {"1": "RF_A", "2": "GND"})
        track(b, "RF", 0.6, (fx, fy), pad_at(l1, "2"))
        track(b, "RF_A", 0.6, pad_at(l1, "1"), (fx, radio_y + 0.975))
        to_gnd(b, pad_at(c3, "2"))
        to_gnd(b, pad_at(c2, "2"))
    else:
        track(b, "RF", 1.35, (fx, fy), (fx, radio_y - 1.0))
        track(b, "RF", 0.6, (fx, radio_y - 1.0), (fx, radio_y + 0.975))
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone(b, layer, [(x0 + 0.5, ground_top), (x1 - 0.5, ground_top), (x1 - 0.5, y1 - 0.5), (x0 + 0.5, y1 - 0.5)],
             clearance=1.0)
    if decap:
        c1 = place(b, "Capacitor_SMD:C_0402_1005Metric", "C1", "100nF", (fx + 2.0, radio_y + 5.925), 0,
                   {"1": "VDD", "2": "GND"})
        track(b, "VDD", 0.25, (fx, radio_y + 5.925), pad_at(c1, "1"))  # from pin 8
        to_gnd(b, pad_at(c1, "2"))
    fence(b, [(x0 + 2.5 + i * pitch, ground_top + 1.5 + j * pitch) for i in range(int((x1 - x0 - 4) / pitch) + 1)
              for j in range(int((y1 - ground_top - 3) / pitch) + 1)], outline, keep=1.5)


IFA = ("RF_Antenna:Texas_SWRA117D_2.4GHz_Left", {"1": "RF", "2": "GND"}, (100, 100), (87, 94, 127, 124), 99.75, 111.0)
```

  - **BOARDS gains:**
    - `"ifa2g4": lambda b: antenna_board(b, *IFA)`;
    - `"ifa2g4_pi": lambda b: antenna_board(b, *IFA, pi=True)`;
    - `"meander915": lambda b: antenna_board(b, "RF_Antenna:Texas_SWRA416_868MHz_915MHz", {"1": "RF"}, (110, 100), (89, 92.5, 129, 146.5), 106.5, 111.0, decap=False)`.
  - **`main`** passes `rules=ANTENNA_RULES` to `new_board` for a name in `("ifa2g4", "ifa2g4_pi", "meander915")`.
- [ ] **Step 4: Generate only the new boards,** in one PowerShell call with KiCad 9's Python (`make_fixtures.py` points its profile at `build/kicad-profile`):

```powershell
& "<KiCad 9 bin folder>\python.exe" tools/make_fixtures.py tests/fixtures ifa2g4 ifa2g4_pi meander915
"exit $LASTEXITCODE"; git status --short tests/fixtures
```

  Expected: `exit 0`, and `git status` lists exactly the six new files. Each board is about 30–40 KB, LF only. If any other file changes, stop: `main(names)` wrote outside its names, and the golden pins hash the existing boards.
- [ ] **Step 5: NOTICE** gains this entry, before "Runtime dependencies". Its licence text was checked against https://www.kicad.org/libraries/license/ on 2026-10-29: the licence (CC-BY-SA 4.0) and the exception's words match.

```
KiCad footprint library
  Upstream:  the footprint library installed with KiCad 9.0 (https://gitlab.com/kicad/libraries/kicad-footprints)
  Licence:   Creative Commons Attribution-ShareAlike 4.0 (CC-BY-SA-4.0), with KiCad's exception for designs: "To the
             extent that the creation of electronic designs that use 'Licensed Material' can be considered to be
             'Adapted Material', then the copyright holder waives article 3 of the license with respect to these
             designs and any generated files which use data provided as part of the 'Licensed Material'."
             (https://www.kicad.org/libraries/license/)
  Here:      the synthetic fixture boards tests/fixtures/*.kicad_pcb, which tools/make_fixtures.py builds from the
             library's footprints, among them RF_Antenna's Texas_SWRA117D_2.4GHz_Left and Texas_SWRA416_868MHz_915MHz,
             TI's antennas from its application notes SWRA117D and SWRA416, which are cited, not shipped
```

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_repo.py -q`. Expected: PASS. The architect's prototype of these boards matched pcbnew's pad truth on all 58 pads.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add tools/make_fixtures.py NOTICE tests/test_fixtures.py tests/test_pads.py tests/fixtures/ifa2g4.* tests/fixtures/ifa2g4_pi.* tests/fixtures/meander915.*
git commit -m "test(fixtures): the 2.4 GHz inverted-F, its pi-network variant and the 868/915 MHz meander, synthetic boards from KiCad's own RF_Antenna footprints (Stage 3 design 5.11)"
graphify update .
```

---

### Task 2 [code]: Antenna footprints in the importer

**Files:**
- Modify:
  - `core/kicad/board.py`: `CopperArea`, `Footprint`, `_graphic` and `_footprint`.
  - `core/kicad/tracer.py`: `trace_chain`, plus the new functions after `choose_reference`.
  - `core/messages.py`: after E_NO_CHAIN.
  - `po/*` and the `.mo`.
- Create: `tests/test_antenna_kicad.py`.

**Interfaces:**
- Consumes: `load_board`, `classify` and `Classes`; `test_tracer.smd`; the Task 1 fixtures.
- Produces:
  - `CopperArea.ref: str = ""`: the footprint whose copper graphic it is, "" for a board item.
  - `Footprint.keepout: bool = False`: whether one of its zones is a keep-out.
  - `antenna_kind(board, ref) -> str | None`, giving "printed", "module" or "chip".
  - `antenna_kinds(board) -> dict[str, str]`.
  - `check_antenna(board, ref) -> None`.
  - `feed_pad(board, classes, ref) -> Pad`.
  - `adopt(board, ref, net) -> None`.
  - `trace_chain(board, start, end, classes=None, antenna: str | None = None) -> Chain`.
  - Messages: E_ANTENNA_UNKNOWN, E_ANTENNA_MODULE, E_ANTENNA_CHIP, E_NOT_AN_ANTENNA and E_ANTENNA_FEED.

- [ ] **Step 1: Write the failing tests,** `tests/test_antenna_kicad.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pytest

from kicad_rf_studio.core.kicad import classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.tracer import adopt, antenna_kind, antenna_kinds, check_antenna, feed_pad
from kicad_rf_studio.core.messages import KrsError
from test_tracer import smd

FIX = Path(__file__).parent / "fixtures"
POLY = ('(fp_poly (pts (xy 0 -2) (xy 4 -2) (xy 4 -1.5) (xy 0 -1.5)) (stroke (width 0) (type solid)) (fill yes) '
        '(layer "F.Cu") (uuid "{}"))')  # 2 mm² of copper against a 1 mm² pad: a radiator
STUB = '(fp_line (start 0 0) (end 2 0) (stroke (width 0.5) (type solid)) (layer "F.Cu") (uuid "{}"))'  # a net-tie stub
KEEPOUT = ('(zone (net 0) (net_name "") (layer "F.Cu") (uuid "k{}") (hatch full 0.5) (keepout (tracks not_allowed) '
           '(vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints not_allowed)) '
           '(polygon (pts (xy 0 -5) (xy 5 -5) (xy 5 -10) (xy 0 -10))))')


def fp(ref, lib, *items, at="0 0", value="x"):
    return (f'(footprint "{lib}" (layer "F.Cu") (uuid "f-{ref}") (at {at}) (property "Reference" "{ref}") '
            f'(property "Value" "{value}") {"".join(items)})')


KINDS = "".join([
    fp("AE1", "Lib:IFA", smd(1, "RF"), POLY.format("g1")),                              # a radiator drawn: printed
    fp("AE2", "RF_Antenna:Johanson_2450AT18x100", smd(1, "RF2"), smd(2, x=3), at="10 0"),  # pads only: chip
    fp("AE3", "Lib:Chip", smd(1, "RF3"), at="20 0"),                                     # AE, pads only: chip
    fp("U2", "RF_Module:ESP32-WROOM-32", smd(1, "GND"), POLY.format("g2"), at="30 0"),   # a module, whatever it draws
    fp("U3", "Lib:Module", smd(1, "RF4"), KEEPOUT.format(3), at="40 0"),                 # keep-out, no copper: module
    fp("U4", "Lib:Ant", smd(1, "RF5"), POLY.format("g3"), KEEPOUT.format(4), at="50 0"),  # keep-out and radiator: printed
    fp("R1", "Lib:R", smd(1, "RF"), smd(2, "GND", x=2), at="60 0"),                       # none
    fp("AE4", "RF_Antenna:Antenova_SR4G013_GPS", smd(1, "RF6"), *(smd(k, "GND", x=2 * (k - 1)) for k in (2, 3, 4)),
       STUB.format("g4"), at="70 0"),                                                    # a stub under its pads: chip
    fp("AE5", "RF_Antenna:Pulse_W3000", smd(1, "RF7"), smd(2, "GND", x=2), KEEPOUT.format(5), at="80 0")])  # chip


def test_antenna_kinds(mini_board):  # design 5.1
    b = mini_board(KINDS)
    assert antenna_kinds(b) == {"AE1": "printed", "AE2": "chip", "AE3": "chip", "AE4": "chip", "AE5": "chip",
                                "U2": "module", "U3": "module", "U4": "printed"}
    assert antenna_kind(b, "R1") is None and b.footprints["U3"].keepout and not b.footprints["AE1"].keepout
    assert [a.ref for a in b.areas] == ["AE1", "U2", "U4", "AE4"]


@pytest.mark.parametrize(("ref", "code"), [("AE2", "E_ANTENNA_CHIP"), ("AE3", "E_ANTENNA_CHIP"),
                                           ("AE4", "E_ANTENNA_CHIP"), ("AE5", "E_ANTENNA_CHIP"),
                                           ("U2", "E_ANTENNA_MODULE"), ("U3", "E_ANTENNA_MODULE")])
def test_modules_chip_antennas_and_other_footprints_are_refused(mini_board, ref, code):  # design 5.1; RF 1
    with pytest.raises(KrsError) as e:
        check_antenna(mini_board(KINDS), ref)
    assert (e.value.code, e.value.params) == (code, {"ref": ref})


def test_a_footprint_that_is_no_antenna_names_the_printed_ones(mini_board):
    b = mini_board(KINDS)
    for ref, code in (("R1", "E_NOT_AN_ANTENNA"), ("AE9", "E_ANTENNA_UNKNOWN")):
        with pytest.raises(KrsError) as e:
            check_antenna(b, ref)
        assert (e.value.code, e.value.params) == (code, {"ref": ref, "candidates": "AE1, U4"})
    check_antenna(b, "AE1")  # a printed antenna: no refusal


def test_the_feed_pad_and_adopted_copper_of_an_inverted_f():  # design 5.1, 5.3; RF 2
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    assert feed_pad(b, classify(b), "AE1").name == "AE1.1"
    adopt(b, "AE1", "RF")
    assert [(a.net, a.ref) for a in b.areas if a.source == "graphic"] == [("RF", "AE1")]
    assert [p.net for p in b.footprints["AE1"].pads] == ["RF", "GND"]  # the join pad keeps its GND
    assert [code for code, _ in b.warnings if code == "W_NETLESS_COPPER"] == []


def test_a_two_layer_meander_adopts_its_unnamed_holes():  # design 5.3
    b = load_board(FIX / "meander915.kicad_pcb")
    adopt(b, "AE1", feed_pad(b, classify(b), "AE1").net)
    assert {p.net for p in b.footprints["AE1"].pads} == {a.net for a in b.areas if a.source == "graphic"} == {"RF"}


def test_other_netless_copper_keeps_its_warning(mini_board):
    loose = '(gr_poly (pts (xy 0 20) (xy 2 20) (xy 2 22)) (stroke (width 0)) (fill yes) (layer "F.Cu") (uuid "loose"))'
    b = mini_board(KINDS + loose)
    adopt(b, "AE1", "RF")
    assert [p["uuid"] for code, p in b.warnings if code == "W_NETLESS_COPPER"] == ["g2", "g3", "g4", "loose"]


@pytest.mark.parametrize(("pads", "nets"), [((smd(1, "GND"),), "T_NONE"), ((smd(1, "RF"), smd(2, "RF2", x=2)), "RF, RF2")])
def test_an_antenna_needs_one_feed_net(mini_board, pads, nets):  # design 5.1
    b = mini_board(fp("AE1", "RF_Antenna:X", *pads, POLY.format("g1")))
    with pytest.raises(KrsError) as e:
        feed_pad(b, classify(b), "AE1")
    assert (e.value.code, e.value.params) == ("E_ANTENNA_FEED", {"ref": "AE1", "nets": nets})


def test_the_antenna_ends_the_chain_and_is_never_a_part():  # design 5.1; RF 2
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    assert [p.ref for p in trace_chain(b, "U1.1", "AE1.1").shunt] == ["AE1"]  # v1's tracer: a shunt part
    chain = trace_chain(b, "U1.1", "AE1.1", antenna="AE1")
    assert (chain.nets, chain.series, chain.shunt) == (("RF",), (), ())
    pi = load_board(FIX / "ifa2g4_pi.kicad_pcb")
    chain = trace_chain(pi, "U1.1", "AE1.1", antenna="AE1")
    assert (chain.nets, [p.ref for p in chain.series], [p.ref for p in chain.shunt]) == (
        ("RF_A", "RF"), ["L1"], ["C2", "C3"])
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_antenna_kicad.py -q`. Expected: FAIL with `cannot import name 'adopt'`.
- [ ] **Step 3: `board.py`.**
  - `CopperArea` gains `ref: str = ""` last.
  - `Footprint` gains `keepout: bool = False` last.
  - `_graphic` gains `ref: str = ""`, passed into each `CopperArea`. `_footprint` passes its final ref (after the #n renaming).
  - `_footprint` sets `keepout` when a zone child holds `(keepout …)`. The zone still goes to `_zone`, which skips it.
  - Both docstrings say so.
- [ ] **Step 4: `tracer.py`.**
  - **`antenna_kind`,** the first that holds:
    1. "module" for a library id starting `RF_Module:`;
    2. "printed" when the areas whose `ref` is this footprint cover more than its copper pads do (the sum of their polygons' areas against the sum of its `_copper` pads' areas): a radiator, never a net-tie stub. KiCad's SWRA117D draws 21.2 mm² against 0.7 mm² of pads, SWRA416 137 mm² against 15.2 mm², Antenova_SR4G013_GPS 0.8 mm² against 15.4 mm²;
    3. "chip" for an AE prefix (`_prefix`) or an `RF_Antenna:` library id, keep-outs or not;
    4. "module" for any other footprint with a keep-out;
    5. otherwise None.

    Comment it `# ponytail: a custom-library module that draws more copper than its pads reads printed, and a connector or converter with a keep-out reads module in antenna_kinds (check_antenna's candidates list only printed ones); a class test if plan 5's list shows them`.
  - **`antenna_kinds`:** every footprint whose kind is not None, in reference order.
  - **`check_antenna`:** raises, in this order:
    - E_ANTENNA_UNKNOWN for a ref not on the board;
    - E_ANTENNA_MODULE or E_ANTENNA_CHIP by kind (params `{"ref"}`);
    - E_NOT_AN_ANTENNA for None.

    The two "named" refusals carry `candidates`: the printed refs joined by ", ", or T_NONE.
  - **`feed_pad`:** the first by number of the antenna's copper pads on the one net that is neither empty, GND nor power. E_ANTENNA_FEED, with `nets` sorted and joined or T_NONE, when there is not exactly one such net.
  - **`adopt`:**
    - Docstring: "Gives the antenna footprint `ref`'s netless copper, its copper graphics and its pads with no net, the net `net`, in place (Stage 3 design 5.3), and drops those graphics' W_NETLESS_COPPER. E_ANTENNA_UNKNOWN for a ref not on the board."
    - It replaces `board.areas` and `board.footprints[ref]` through `dataclasses.replace`.
    - Comment it `# ponytail: every netless piece of the footprint takes the feed net; a floating parasitic element would then read as an open of it (E_OPEN_IN_ROI); adopt only the copper the feed pad reaches if one appears`.
  - **`trace_chain`'s `antenna`:** joins `not_parts`. Its docstring: "the antenna footprint (Stage 3 design 5.1) ends the chain and is never a part".
- [ ] **Step 5: The messages,** after E_NO_CHAIN, each run through the catalog tool (run, set the msgstr, run again):

| Code | English | pt-BR |
|---|---|---|
| E_ANTENNA_UNKNOWN | Footprint {ref} is not on the board. Antenna footprints on it: {candidates}. | O footprint {ref} não está na placa. Footprints de antena nela: {candidates}. |
| E_ANTENNA_MODULE | {ref} is a module (an RF_Module: footprint, or one with a keep-out and no radiator drawn): its antenna's copper is inside the module, not in the board file, so it cannot be simulated as an antenna. The matching chain up to the module's pad still can: \`new BOARD --start REF.PAD --end {ref}.PAD --f0 F\`. | {ref} é um módulo (um footprint RF_Module:, ou um com área de exclusão e sem radiador desenhado): o cobre da antena dele fica dentro do módulo, não no arquivo da placa, então ela não pode ser simulada como antena. A cadeia de casamento até a ilha do módulo ainda pode: \`new BOARD --start REF.PAD --end {ref}.PAD --f0 F\`. |
| E_ANTENNA_CHIP | {ref} is a chip antenna: its radiator is inside the part's body and the board file holds only its pads, at most with a stub between them, so it cannot be simulated as an antenna. The matching chain up to its pad still can: \`new BOARD --start REF.PAD --end {ref}.PAD --f0 F\`. | {ref} é uma antena chip: o radiador fica dentro do corpo do componente e o arquivo da placa só tem as ilhas dela, no máximo com um trecho curto entre elas, então ela não pode ser simulada como antena. A cadeia de casamento até a ilha dela ainda pode: \`new BOARD --start REF.PAD --end {ref}.PAD --f0 F\`. |
| E_NOT_AN_ANTENNA | {ref} is not an antenna footprint: its reference does not start with AE, its library is not RF_Antenna and it draws no radiator, copper graphics larger than its pads. Antenna footprints on this board: {candidates}. | {ref} não é um footprint de antena: a referência dele não começa com AE, a biblioteca dele não é RF_Antenna e ele não desenha radiador, gráficos de cobre maiores que as ilhas dele. Footprints de antena nesta placa: {candidates}. |
| E_ANTENNA_FEED | Antenna {ref} needs one pad on a signal net, its feed, and has {nets}. Connect its feed pad to the RF net in the schematic, update the PCB from it in KiCad and save the board. | A antena {ref} precisa de uma ilha numa rede de sinal, a de alimentação, e tem: {nets}. Ligue a ilha de alimentação dela à rede de RF no esquemático, atualize a PCI a partir dele no KiCad e salve a placa. |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_tracer.py tests/test_pads.py tests/test_board.py tests/test_sexpr.py tests/test_golden_v1.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(kicad): antenna footprints by kind, their feed pad, their netless copper adopted and the antenna never a chain part (Stage 3 design 5.1, 5.3)"
graphify update .
```

---

### Task 3 [code]: Schema 2, the band, the whole-board region and the rest of the board's parts

**Files:**
- Modify:
  - `core/project.py`: the module docstring, the new names after SCHEMA, `check_project` and `load_project`;
  - `core/geometry/region.py`: `band`, `f_max`, and `air_cell`, `air_gap` and `board_region` after `build_region`;
  - `core/model/parts.py`: `role` and `project_parts`;
  - `gui/control.py`: `open_project`;
  - `core/messages.py`: the `T_EXPECT_` codes after T_EXPECT_OBJECT, and W_BOARD_PARTS_OPEN after W_PART_OPEN;
  - `po/*` and the `.mo`.
- Test: `tests/test_project.py` (and its L26–L27), `tests/test_geometry_region.py`, `tests/test_model_parts.py` and `tests/test_gui_control.py`.

**Interfaces:**
- Consumes: Task 2's `adopt` and `trace_chain(..., antenna=)`; `make_project`; `NF2FF_MAX` (`core/model/csx.py`); `coarse_cell` and `C0` (`region.py`); `Z0` and `srf` (`parts.py`).
- Produces:
  - In `core/project.py`:
    - `SCHEMA_ANTENNA = 2`, `FAR_FIELD_STEP = 5`, `antenna(data: dict) -> bool` and `pulse_band(f_lo: float, f_hi: float) -> tuple[float, float]`.
    - `make_antenna_project(board_path, board_sha256, f_lo_hz, f_hi_hz, stackup, classes, chain, others, ports, ref, join, *, t_max_s, air_gap_mm, preset=DEFAULT_PRESET, lid_height_mm=None) -> dict`.
    - `check_project` and `load_project` for schema 2.
  - In `core/geometry/region.py`: `band(project)` and `f_max(project) == band(project)[1]` for both kinds; `air_cell(f_max) -> float`, λ(f_max)/20 in mm; `air_gap(f_lo) -> float`, λ/4 at f_lo in mm; `board_region(board, chain, ports, zs, f_max, expand_h=REACH_H) -> Region`.
  - In `core/model/parts.py`: `role(..., place, ...)` takes "board" and "far"; `project_parts(board, chain, classes, roi, f1, f2, *, antenna=False)`.
  - `control.open_project` refuses an antenna project with E_PROJECT_SCHEMA until plan 5.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_project.py`:
    - Imports gain `from pathlib import Path`; `SCHEMA_ANTENNA`, `antenna`, `check_project`, `make_antenna_project` and `pulse_band` from `core.project`; `classify` and `load_board` from `core.kicad`; `air_gap` from `core.geometry.region`; and `FIX` beside `run_new` from `test_cli_new`.
    - `test_schema_mismatch_names_the_file_and_both_versions` changes deliberately, since E_PROJECT_SCHEMA now names the newest schema it reads. L26–L27 become:

```python
    assert e.value.params == {"path": str(p), "found": 99, "expected": SCHEMA_ANTENNA}  # the newest it reads (Stage 3)
    assert "schema 99" in str(e.value) and "schema 2" in str(e.value)
    p.write_text('{"schema": 2}', encoding="utf-8")
    assert load_project(p) == {"schema": 2}  # an antenna project (Stage 3 design 5.1); check_project reads its fields
```

    - Add:

```python
@pytest.mark.parametrize(("f_lo", "f_hi", "f1", "f2"), [(2.4e9, 2.4835e9, 1.84e9, 2.99e9), (902e6, 928e6, 693e6, 1.12e9),
                                                        (863e6, 870e6, 663e6, 1.05e9), (2.4e9, 2.5e9, 1.84e9, 3.0e9)])
def test_the_pulse_band_rounds_out_to_3_significant_digits(f_lo, f_hi, f1, f2):  # design 5.4
    assert pulse_band(f_lo, f_hi) == (f1, f2) and all(type(v) is float for v in pulse_band(f_lo, f_hi))


def antenna_dict():
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    chain = {"start": "U1.1", "end": "AE1.1", "nets": ["RF"], "series": [], "shunt": []}
    port = {"name": "P1", "signal": "U1.1", "signal_uuid": "u", "layer": "F.Cu", "rule": "ic",
            "reference": {"pad": "U1.2", "uuid": ""}}
    return make_antenna_project("ifa2g4.kicad_pcb", "0" * 64, 2.4e9, 2.4835e9, b.stackup, classify(b), chain, [],
                                [port], "AE1", ["AE1.2"], t_max_s=30e-9, air_gap_mm=air_gap(2.4e9))


def test_an_antenna_project_holds_the_design_fields():  # design 5.1, 5.2, 5.5
    d = antenna_dict()
    assert (d["schema"], d["kind"], d["band"], d["f0_hz"], d["t_max_s"]) == (
        2, "antenna", {"f_lo_hz": 2.4e9, "f_hi_hz": 2.4835e9}, 2.44175e9, 30e-9)
    assert "harmonics" not in d and "band_factor" not in d and d["lid"] is True and d["region"] == {"expand_h": 6.0}
    assert (d["antenna"], d["boundary"], d["air_gap_mm"]) == ({"ref": "AE1", "join": ["AE1.2"]}, "pml_8", 31.228381)
    f = d["far_field"]["f_hz"]
    assert (len(f), f[0], f[1], f[-1], d["far_field"]["step_deg"]) == (11, 2.44175e9, 2.4e9, 2.4835e9, 5)
    assert antenna(d) and not antenna({**d, "schema": 1}) and check_project(d, Path("p.json")) is d


@pytest.mark.parametrize(("change", "field", "expected"), [
    ({"kind": "chain"}, "kind", "T_EXPECT_ANTENNA"),
    ({"band": {"f_lo_hz": 2.4e9, "f_hi_hz": 2.3e9}}, "band.f_hi_hz", "T_EXPECT_BAND"),
    ({"band": {"f_lo_hz": 868e6, "f_hi_hz": 2.4835e9}}, "band.f_hi_hz", "T_EXPECT_BAND"),  # two bands: one a run
    ({"f0_hz": 2.5e9}, "f0_hz", "T_EXPECT_F0_BAND"),
    ({"boundary": "MUR"}, "boundary", "T_EXPECT_BOUNDARY"),
    ({"far_field": {"f_hz": [3.1e9], "step_deg": 5}}, "far_field.f_hz", "T_EXPECT_FAR_FIELD_HZ"),
    ({"far_field": {"f_hz": [2.44e9] * 12, "step_deg": 5}}, "far_field.f_hz", "T_EXPECT_FAR_FIELD_HZ"),
    ({"far_field": {"f_hz": [2.4e9, 2.44175e9], "step_deg": 5}}, "far_field.f_hz", "T_EXPECT_FAR_FIELD_HZ"),  # f0 first
    ({"far_field": {"f_hz": [2.44e9], "step_deg": 7}}, "far_field.step_deg", "T_EXPECT_STEP"),
    ({"air_gap_mm": 0}, "air_gap_mm", "T_EXPECT_ABOVE_0"),
    ({"antenna": {"ref": "AE1"}}, "antenna.join", "T_EXPECT_NAMES")])
def test_a_schema_2_field_out_of_its_range_is_named(change, field, expected):  # design 5.1; RF 5
    with pytest.raises(KrsError) as e:
        check_project({**antenna_dict(), **change}, Path("p.json"))
    assert (e.value.code, e.value.params["field"], e.value.params["expected"]) == ("E_PROJECT_FIELD", field, expected)
```

  - In `tests/test_geometry_region.py` (imports gain `air_cell`, `air_gap`, `band` and `board_region` beside the region names already imported, `trace_chain` from `core.kicad`, `adopt` from `core.kicad.tracer`, and `antenna_dict` from `test_project`):

```python
def test_the_band_of_an_antenna_is_its_pulse_band():  # design 5.2, 5.4
    d = antenna_dict()
    assert band(d) == (1.84e9, 2.99e9) and f_max(d) == 2.99e9 and air_cell(2.99e9) == pytest.approx(5.01325, abs=1e-5)
    assert air_gap(2.4e9) == 31.228381  # λ/4 at f_lo, to 1e-6 mm
    v1 = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1}
    assert band(v1) == (457.5e6, pytest.approx(3.0195e9)) and f_max(v1) == band(v1)[1]


def test_an_antennas_region_is_the_whole_board_with_the_measured_region_as_its_roi():  # design 5.2, 5.3
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    adopt(b, "AE1", "RF")
    zs = zstack(b.stackup, b.copper_layers)
    r = board_region(b, trace_chain(b, "U1.1", "AE1.1", antenna="AE1"),
                     [{"signal": "U1.1", "reference": {"pad": "U1.2", "uuid": ""}}], zs, 2.99e9)
    c = coarse_cell(2.99e9, 4.5)
    assert r.coarse == c and r.walls == tuple(round(v, 6) for v in (87 - c, 127 + c, -124 - c, -94 + c,
                                                                     zs[0].z0 - c, zs[-1].z1 + c))
    assert r.crop.bounds == (r.walls[0], r.walls[2], r.walls[1], r.walls[3])
    # the antenna, the feed and U1's pins 1-2, 6 substrate heights past them, cut at the outline (the prototype's)
    assert r.roi.bounds == pytest.approx((87.0, -117.21, 106.81, -94.0), abs=1e-6)
```

  - In `tests/test_model_parts.py`:

```python
G24, M915 = (1.84e9, 2.99e9), (693e6, 1.12e9)  # the pulse bands of 2400-2483.5 and 902-928 MHz


@pytest.mark.parametrize(("kind", "value", "dnp", "angle", "place", "pulse", "expected"), [
    ("C", 100e-9, False, 0, "board", G24, "copper"),   # a decoupling C: close to a short at RF
    ("C", 10e-12, False, 45, "far", G24, "copper"),    # at any angle, anywhere on the board
    ("C", 4.7e-12, False, 0, "board", G24, "copper"),  # 14.0 Ω − 7.6 Ω of ESL at 2.415 GHz: 6.4 Ω ≤ Z0/5
    ("C", 2.2e-12, False, 0, "board", G24, "open"),    # 22.4 Ω, and its SRF of 4.8 GHz is under 3·f2
    ("C", 1e-12, False, 0, "board", G24, "open"),      # 58 Ω: design 5.3's SRF wording would have shorted it
    ("C", 0.4e-12, False, 90, "board", G24, "grid"),   # SRF 11.3 GHz: in the grid in the measured region
    ("C", 0.4e-12, False, 90, "far", G24, "open"),     # but open past it
    ("C", 22e-12, False, 0, "board", M915, "copper"),  # 5.1 Ω at 906.5 MHz
    ("C", 4.7e-12, False, 0, "board", M915, "open"),   # 34.5 Ω, its SRF of 3.28 GHz under 3·f2 = 3.36 GHz
    ("R", 1e3, False, 0, "board", G24, "grid"), ("R", 1e3, False, 0, "far", G24, "open"),
    ("R", 0.0, False, 0, "far", G24, "copper"),        # a 0R
    ("L", 1e-6, False, 0, "board", G24, "open"),       # an inductor is never a port here
    ("C", None, False, 0, "board", G24, "open"),       # a value that does not read
    (None, None, False, 0, "board", G24, "open"),      # a bead, a diode
    ("C", 100e-9, True, 0, "board", G24, "open")])     # DNP
def test_the_rest_of_an_antennas_board_is_never_a_port(kind, value, dnp, angle, place, pulse, expected):  # 5.3; RF 4
    assert role(kind, value, C0402 if kind else None, dnp, angle, place, *pulse) == expected


def test_an_antennas_parts_are_every_two_pad_part_off_the_chain(mini_board):  # design 5.3; RF 4
    from shapely.geometry import box
    from test_antenna_kicad import fp
    from test_tracer import smd
    from kicad_rf_studio.core.kicad.tracer import Chain
    lib = "Resistor_SMD:R_0402_1005Metric"
    b = mini_board(fp("R1", lib, smd(1, "N1"), smd(2, "GND", x=2), value="1k") +
                   fp("R2", lib, smd(1, "N2"), smd(2, "GND", x=2), at="50 0", value="1k"))
    _, _, others, notes = project_parts(b, Chain("A.1", "B.1", ("RF",), (), ()), classify(b), box(-5, -5, 5, 5),
                                        1.84e9, 2.99e9, antenna=True)
    assert [(q["ref"], q["role"]) for q in others] == [("R1", "grid"), ("R2", "open")]
    assert notes == [("W_BOARD_PARTS_OPEN", {"refs": "R2"})]
```

  - In `tests/test_gui_control.py`:

```python
def test_an_antenna_project_is_refused_until_plan_5(tmp_path):  # Stage 3 plan 2: window.show_project reads harmonics
    from test_project import antenna_dict
    p = tmp_path / "project.json"
    save_project(p, antenna_dict())
    opened = control.open_project(p)
    assert opened.project is None and opened.problem == ("E_PROJECT_SCHEMA", {"path": str(p), "found": 2, "expected": 1})
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_project.py tests/test_geometry_region.py tests/test_model_parts.py tests/test_gui_control.py -q`. Expected: FAIL with `cannot import name 'SCHEMA_ANTENNA'`.
- [ ] **Step 3: `core/project.py`.**
  - **The module docstring** says "project.json, schema 1 for a matching chain and schema 2 for an antenna (Stage 3 design 5.1)".
  - **`SCHEMA_ANTENNA` and `antenna`:** `SCHEMA_ANTENNA = 2`, commented "an antenna project (Stage 3 design 5.1); v1's stay SCHEMA". `antenna(data)` is `data.get("schema") == SCHEMA_ANTENNA`.
  - **`pulse_band`:**
    - Docstring: "The pulse's band (f1, f2) of an antenna's band, in Hz (Stage 3 design 5.4): f_lo/1.3 rounded down and 1.2·f_hi rounded up, each to 3 significant digits, as floats."
    - It rounds `v / 10 ** (floor(log10 v) - 2)` to 6 decimals before floor or ceil, so float noise cannot bump 300.0 to 301.
  - **`make_antenna_project`:**
    - Docstring: "project.json of an antenna (schema 2, Stage 3 design 5.1) as `new --antenna` writes it: make_project's dict but harmonics and band_factor, with schema SCHEMA_ANTENNA, f0_hz the band's centre, `t_max_s`, region {"expand_h": REACH_H} (the measured region reaches as far as the protected set) and lid true (every shield gets its lid, 5.3); then kind, band, antenna {"ref", "join"}, `air_gap_mm`, boundary "pml_8" and far_field {"f_hz": f0 then 10 frequencies evenly from f_lo to f_hi, "step_deg": FAR_FIELD_STEP}."
    - Body: `make_project(...)` with `f0_hz` the centre, its harmonics and band_factor keys dropped, the overrides set in place and the antenna keys appended, so the key order is make_project's then kind, band, antenna, air_gap_mm, boundary and far_field.
  - **`_FIELDS_ANTENNA`:** `_FIELDS` without harmonics and band_factor, then:
    - `"kind"`: `== "antenna"`, T_EXPECT_ANTENNA;
    - `"band"`: `{"f_lo_hz": _ABOVE_0, "f_hi_hz": _ABOVE_0}`;
    - `"antenna"`: `{"ref": _TEXT, "join": (_names, "T_EXPECT_NAMES")}`;
    - `"air_gap_mm"`: `_ABOVE_0`;
    - `"boundary"`: in `("pml_8", "mur")`, T_EXPECT_BOUNDARY;
    - `"far_field"`: `{"f_hz"`: a list of 1 to NF2FF_MAX finite numbers, T_EXPECT_FAR_FIELD_HZ; `"step_deg"`: `type(v) is int and v > 0 and 180 % v == 0`, T_EXPECT_STEP`}`.
  - **`check_project`:** for an antenna it checks `_FIELDS_ANTENNA`, then raises E_PROJECT_FIELD, in this order:
    - `band.f_hi_hz` / T_EXPECT_BAND unless f_lo < f_hi ≤ 2·f_lo (design §3: one band a run);
    - `f0_hz` / T_EXPECT_F0_BAND unless f_lo ≤ f0 ≤ f_hi;
    - `far_field.f_hz` / T_EXPECT_FAR_FIELD_HZ unless its first frequency is f0_hz (the worker draws the cuts at the first) and every one lies within `pulse_band`.
  - **`load_project`:** accepts SCHEMA and SCHEMA_ANTENNA. Its refusal's `expected` is SCHEMA_ANTENNA, the newest it reads.
- [ ] **Step 4: `region.py`.**
  - **`band`:** for an antenna, `pulse_band(project["band"]["f_lo_hz"], project["band"]["f_hi_hz"])`, as a branch first; v1's lines stay as they are.
  - **`f_max`:** `band(project)[1]` for an antenna, as a branch first; v1's expression stays.
  - **`air_cell(f_max)`:** `C0 * 1e3 / f_max / 20`, documented as "an antenna's air cell, λ(f_max)/20, in mm (Stage 3 design 5.3)".
  - **`air_gap(f_lo)`:** `round(C0 * 1e3 / f_lo / 4, 6)`, documented as "an antenna's default air gap, λ/4 at f_lo, in mm (Stage 3 design 5.2)". `new` writes it, and the antenna geometry warns below it (Task 6).
  - **`board_region`:**
    - Docstring: "An antenna's region (Stage 3 design 5.2, 5.3): build_region's ROI at `expand_h`, which is the measured region (the antenna's copper takes the feed net, a chain net); the walls are the board's box, its outline's and every piece of its copper's bounds, grown by one coarse cell in x and y, and the stack's faces grown by one in z, so no copper edge sits on a wall; the crop is the walls' box, which every piece of copper lies inside, so nothing is clipped. Every coordinate goes to 1e-6 mm."
    - The copper is the tracks', areas' and copper pads' polygons.
- [ ] **Step 5: `parts.py`.**
  - **`role`** extends v1's rules rather than adding a block. Its docstring gains "a part of an antenna's board, `place` "board" in its measured region and "far" past it (Stage 3 design 5.3), is never a port: a C close to a short at the pulse's centre is copper, a C or R that v1 would put in the grid is in the grid on "board" and open on "far", and any other part is open". After the 0R rule:

```python
    if place in ("board", "far") and kind == "C" and value:  # the rest of an antenna's board (Stage 3 design 5.3)
        w = math.pi * (f1 + f2)  # 2π × the pulse's centre, near f0; the copper bridge stands for the package's ESL
        if 1 / (w * value) - w * (model or {}).get("esl_h", 0.0) <= Z0 / 5:
            return COPPER  # a decoupling capacitor is close to a short at RF
    if place in ("other", "board", "far") and kind in ("C", "R"):
        return GRID if place != "far" and value and model and square and srf(kind, value, model) > 3 * f2 else OPEN
    if place in ("board", "far") or place == "other" and kind != "L":
        return OPEN
```

    The grid line is v1's own `place == "other"` line, widened: the grid needs the measured region's fine lines at its pads (`# ponytail: a grid part past the measured region is open; the whole board's fill would stretch to its pads`). The COPPER return is marked `# ponytail: past the measured region a bridge sits in coarse cells, which may resolve none of it (I_LIMIT_PARTS_OFF_CHAIN says so); its pads as free coordinates if that matters`.
  - **`project_parts`:**
    - With `antenna`, the others are every two-pad part off the chain anywhere on the board. Each is "board" when a pad meets `roi` (the measured region), else "far".
    - The open, non-DNP ones are W_BOARD_PARTS_OPEN in place of W_PART_OPEN.
- [ ] **Step 6: `control.open_project`.** Inside its `try`, before `pipeline.load`, `if antenna(load_project(path))` raises E_PROJECT_SCHEMA `{"path": str(path), "found": SCHEMA_ANTENNA, "expected": SCHEMA}`, so the GUI shows the refusal it showed before this plan. Mark it `# ponytail: plan 5 opens antenna projects; until then window.show_project would read their harmonics`.
- [ ] **Step 7: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| T_EXPECT_ANTENNA | the text "antenna" | o texto "antenna" |
| T_EXPECT_BAND | a number above f_lo_hz and at most twice it, one band a run | um número acima de f_lo_hz e no máximo o dobro dele, uma banda por execução |
| T_EXPECT_F0_BAND | a frequency in Hz from band.f_lo_hz to band.f_hi_hz | uma frequência em Hz de band.f_lo_hz a band.f_hi_hz |
| T_EXPECT_BOUNDARY | "pml_8" or "mur" | "pml_8" ou "mur" |
| T_EXPECT_FAR_FIELD_HZ | a list of 1 to 11 frequencies in Hz, f0_hz first, each inside the pulse's band, f_lo_hz/1.3 to 1.2·f_hi_hz | uma lista de 1 a 11 frequências em Hz, f0_hz primeiro, cada uma dentro da banda do pulso, de f_lo_hz/1.3 a 1.2·f_hi_hz |
| T_EXPECT_STEP | a whole number of degrees that divides 180 | um número inteiro de graus que divide 180 |
| W_BOARD_PARTS_OPEN | Left open on the antenna's board: {refs}: inductors, beads, parts whose value does not read, capacitors neither close to a short nor fit for the grid, and resistors or capacitors past the measured region that would sit in the grid. The stated limits count them as approximations. | Deixados em aberto na placa da antena: {refs}: indutores, ferrites, componentes cujo valor não pode ser lido, capacitores que nem ficam perto de um curto nem cabem na grade, e resistores ou capacitores fora da região medida que ficariam na grade. Os limites declarados os contam como aproximações. |

- [ ] **Step 8: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_sexpr.py tests/test_cli_new.py tests/test_gui.py -q`. Expected: PASS. The pins hold because v1's band and roles are unchanged.
- [ ] **Step 9: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(project): schema 2 for antennas, the pulse band, the whole-board region and the rest of the board's parts never ports; the GUI refuses antenna projects until plan 5 (Stage 3 design 5.1-5.4)"
graphify update .
```

---

### Task 4 [code]: `new --antenna`

**Files:**
- Modify:
  - `cli.py`: `new`'s prelude, port and write into `_load`, `_port` and `_write`; `new_antenna`, `_new` and `_parser`;
  - `core/kicad/values.py`: `parse_band` after `parse_frequency`;
  - `core/messages.py`: after I_DEFAULTS;
  - `po/*` and the `.mo`;
  - `tests/test_cli_new.py`: two usage cases.
- Create: `tests/test_cli_antenna.py`.

**Interfaces:**
- Consumes: Task 2's `check_antenna`, `feed_pad`, `adopt` and `trace_chain(..., antenna=)`; Task 3's `make_antenna_project`, `pulse_band`, `air_gap`, `board_region` and `project_parts(..., antenna=True)`; `core.model.spec.pulse`.
- Produces:
  - `parse_band(text: str) -> tuple[float, float]`;
  - `cli._load(board, stackup) -> (Board, Stackup, zs, Classes)`, `cli._port(board, classes, name, signal) -> dict` and `cli._write(folder, project) -> Path`;
  - `cli.new_antenna(board, start, antenna, band, *, preset=DEFAULT_PRESET, stackup=None, lid_height=None, output=None) -> tuple[Path, list[tuple[str, dict]]]`;
  - `tests/test_cli_antenna.antenna_project(folder, board=IFA, band=None) -> Path`, which later tasks import;
  - messages E_BAD_BAND, E_BAND_WIDE, E_NEW_KIND, I_ANTENNA, I_ANTENNA_JOIN, I_BAND and I_ANTENNA_DEFAULTS.

- [ ] **Step 1: Write the failing tests,** `tests/test_cli_antenna.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pytest

from kicad_rf_studio import cli
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.kicad.values import parse_band
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.project import load_project, read_project
from test_antenna_kicad import fp
from test_tracer import smd

FIX = Path(__file__).parent / "fixtures"
IFA = FIX / "ifa2g4.kicad_pcb"
BANDS = {"ifa2g4": (2.4e9, 2.4835e9), "ifa2g4_pi": (2.4e9, 2.4835e9), "meander915": (902e6, 928e6)}


def antenna_project(folder: Path, board: Path = IFA, band=None) -> Path:
    """project.json of `board`'s AE1 fed from U1.1, as new_antenna writes it into `folder`."""
    return cli.new_antenna(board, "U1.1", "AE1", band or BANDS[board.stem], output=folder)[0]


def test_new_antenna_writes_schema_2(tmp_path, capsys):  # design 5.1
    code = main(["new", str(IFA), "--start", "U1.1", "--antenna", "AE1", "--band", "2400MHz:2483.5MHz",
                 "-o", str(tmp_path / "p")])
    d = read_project(tmp_path / "p" / "project.json")
    assert code == 0 and (d["schema"], d["kind"], d["band"]) == (2, "antenna", {"f_lo_hz": 2.4e9, "f_hi_hz": 2.4835e9})
    assert d["chain"] == {"start": "U1.1", "end": "AE1.1", "nets": ["RF"], "series": [], "shunt": []}
    assert [p["signal"] for p in d["ports"]] == ["U1.1"] and d["ports"][0]["reference"]["pad"] == "U1.2"
    assert (d["antenna"], d["t_max_s"]) == ({"ref": "AE1", "join": ["AE1.2"]}, 30e-9)
    assert [(q["ref"], q["role"]) for q in d["others"]] == [("C1", "copper")]  # a decoupling C, bridged (RF 4)
    out = capsys.readouterr().out
    for line in (render("I_ANTENNA", ref="AE1", feed="AE1.1", net="RF"), render("I_ANTENNA_JOIN", ref="AE1", pads="AE1.2"),
                 render("I_BAND", f_lo_mhz="2400", f_hi_mhz="2483.5", f0_mhz="2441.75", f1_mhz="1840", f2_mhz="2990"),
                 render("I_ANTENNA_DEFAULTS", preset="normal", t_max_ns="30", mesh_n=2, expand_h="6", reach_h="6",
                        air_gap_mm="31.2", boundary="pml_8", count=11, step_deg=5)):
        assert line in out
    assert "no net and is simulated as floating copper" not in out  # the antenna's copper took RF


def test_new_antenna_on_the_915_meander_and_the_pi_variant(tmp_path):  # design 5.1, 5.11
    _, notes = cli.new_antenna(FIX / "meander915.kicad_pcb", "U1.1", "AE1", (902e6, 928e6), output=tmp_path / "m")
    d = load_project(tmp_path / "m" / "project.json")
    assert (d["antenna"], d["t_max_s"], d["chain"]["nets"]) == ({"ref": "AE1", "join": []}, 79e-9, ["RF"])
    assert "I_ANTENNA_JOIN" not in [c for c, _ in notes] and notes[-1][0] == "I_WROTE"
    d = load_project(antenna_project(tmp_path / "pi", FIX / "ifa2g4_pi.kicad_pcb"))
    assert ([q["ref"] for q in d["chain"]["series"]], [q["ref"] for q in d["chain"]["shunt"]]) == (["L1"], ["C2", "C3"])


def test_new_refuses_a_module_before_writing(tmp_path, mini_board_file):  # design 5.1; RF 1
    board = mini_board_file(fp("U2", "RF_Module:ESP32-WROOM-32", smd(1, "RF")))
    with pytest.raises(KrsError) as e:
        cli.new_antenna(board, "U2.1", "U2", (2.4e9, 2.4835e9), stackup="jlcpcb-2l", output=tmp_path / "p")
    assert (e.value.code, e.value.params) == ("E_ANTENNA_MODULE", {"ref": "U2"}) and not (tmp_path / "p").exists()


@pytest.mark.parametrize(("text", "code"), [("2400MHz", "E_BAD_BAND"), ("2483.5MHz:2400MHz", "E_BAD_BAND"),
                                            ("2.4GHz:2.4GHz", "E_BAD_BAND"), ("x:2.4GHz", "E_BAD_FREQUENCY")])
def test_a_band_that_does_not_read_is_refused(text, code):  # RF 5
    with pytest.raises(KrsError) as e:
        parse_band(text)
    assert e.value.code == code
    assert parse_band(" 2400MHz : 2483.5MHz ") == (2.4e9, 2.4835e9)


def test_a_band_wider_than_an_octave_is_refused(tmp_path):  # design 3: one band a run; RF 5
    with pytest.raises(KrsError) as e:
        cli.new_antenna(IFA, "U1.1", "AE1", (868e6, 2.4835e9), output=tmp_path / "p")
    assert (e.value.code, e.value.params) == ("E_BAND_WIDE", {"f_lo_mhz": "868", "f_hi_mhz": "2483.5"})


def test_a_band_with_no_unit_is_warned(tmp_path):  # RF 5: "2400:2483.5" reads as Hz
    _, notes = cli.new_antenna(IFA, "U1.1", "AE1", (2400.0, 2483.5), output=tmp_path / "hz")
    assert ("W_F0_RANGE", {"f0_hz": "2441.75"}) in notes


def test_end_goes_with_f0_and_antenna_with_band(tmp_path, capsys):  # design 5.1
    for argv in (["--end", "AE1.1", "--band", "2.4GHz:2.5GHz"],
                 ["--antenna", "AE1", "--band", "2.4GHz:2.5GHz", "--harmonics", "3"]):  # harmonics do not apply
        assert main(["new", str(IFA), "--start", "U1.1", *argv, "-o", str(tmp_path)]) == 2
        assert render("E_NEW_KIND") in capsys.readouterr().err
```

  In `tests/test_cli_new.py`, `test_a_usage_error_exits_2`'s list gains two cases:
  - `["new", "b.kicad_pcb", "--start", "U1.1", "--antenna", "AE1"]`, with no frequency or band;
  - `["new", "b.kicad_pcb", "--start", "U1.1", "--end", "J1.1", "--antenna", "AE1", "--f0", "915MHz"]`, both ends.

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_cli_antenna.py -q`. Expected: FAIL with `cannot import name 'parse_band'`.
- [ ] **Step 3: `parse_band(text)`.**
  - "F_LO:F_HI": each side is read by `parse_frequency` (whose E_BAD_FREQUENCY stands).
  - E_BAD_BAND `{"text"}` without exactly one ":" or unless F_LO < F_HI.
- [ ] **Step 4: The shared helpers, a refactor on its own.** `new`'s first five steps become `_load(board, stackup)`, its port dict `_port(board, classes, name, signal)` and its write `_write(folder, project)` (E_PROJECT_EXISTS, then E_OUTPUT_PATH, as `new` raises them today). `new` calls all three. Run `.venv/Scripts/python -m pytest tests/test_cli_new.py tests/test_golden_v1.py -q`: PASS, so `new`'s output is unchanged before the antenna path exists.
- [ ] **Step 5: `cli.py`'s antenna path.**
  - **`new_antenna`,** with the docstring "`new` for an antenna (Stage 3 design 5.1): every refusal before anything is written; returns as `new`". In this order:
    1. E_BAND_WIDE when f_hi > 2·f_lo (params `f"{v / 1e6:g}"`).
    2. `_load`, then `check_antenna`.
    3. `feed = feed_pad(...)`, then `adopt(board, antenna, feed.net)`.
    4. `join` = the antenna's copper pads on a GND net (`# ponytail: every GND pad of the footprint, also a mounting pad; the footprint's net-tie group if one hides a short`).
    5. `trace_chain(board, start, feed.name, classes, antenna=antenna)`, then `ports = [_port(board, classes, "P1", start)]`.
    6. `f1, f2 = pulse_band(...)`, with f0 the band's centre.
    7. `t_max = math.ceil((2 * pulse(f1, f2, 0)["t0"] + 60 / f0) * 1e9) / 1e9`, commented "design 5.4: 2·t0 + 60/f0, rounded up to a whole ns".
    8. `region = board_region(board, chain, ports, zs, f2)`, then `project_parts(board, chain, classes, region.roi, f1, f2, antenna=True)`.
    9. `find_lid(board, classes, replace(region, roi=region.crop), zs, {"lid": True, "lid_height_mm": lid_height})`, since every shield on the board is a candidate.
    10. `make_antenna_project(..., air_gap_mm=air_gap(f_lo))`, then `_write`.
  - **Notes, in order:**
    1. the board's warnings (after `adopt`), W_FILLS_AS_SAVED, the stackup, I_CLASSES;
    2. I_ANTENNA `{ref, feed, net}`, then I_ANTENNA_JOIN `{ref, pads}` when there is a join;
    3. I_CHAIN, the parts, the port;
    4. I_BAND `{f_lo_mhz, f_hi_mhz, f0_mhz, f1_mhz, f2_mhz}` (`:g` of MHz);
    5. I_ANTENNA_DEFAULTS `{preset, t_max_ns (:g of ns), mesh_n, expand_h (:g), reach_h (:g), air_gap_mm (:.1f), boundary, count, step_deg}`;
    6. W_COPPER_WEIGHT, W_LID_HEIGHT_MISSING, the part notes, W_NO_REFERENCE, then W_F0_RANGE when f0 is outside 1 MHz–100 GHz;
    7. W_ABSOLUTE_BOARD_PATH, I_WROTE.
  - **The parser:**
    - `--end` and `--antenna` (metavar REF) form one required mutually exclusive group, and `--f0` and `--band` (type `parse_band`, metavar F_LO:F_HI) another.
    - `--harmonics` defaults to None.
    - `_new` raises E_NEW_KIND when `(a.antenna is None) != (a.band is None)`, or when `--harmonics` comes with `--antenna`. Else it calls `new_antenna`, or `new` with `harmonics=a.harmonics or HARMONICS`.
- [ ] **Step 6: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| E_BAD_BAND | Cannot read the band "{text}". Write it as F_LO:F_HI with F_LO below F_HI, like 2400MHz:2483.5MHz. | Não é possível ler a banda "{text}". Escreva-a como F_LO:F_HI com F_LO abaixo de F_HI, como 2400MHz:2483.5MHz. |
| E_BAND_WIDE | The band {f_lo_mhz} to {f_hi_mhz} MHz spans more than an octave. An antenna project simulates one band: make one project per band, such as one for 868 MHz and one for 2.4 GHz. | A banda de {f_lo_mhz} a {f_hi_mhz} MHz passa de uma oitava. Um projeto de antena simula uma banda: crie um projeto por banda, como um para 868 MHz e outro para 2.4 GHz. |
| E_NEW_KIND | \`new\` takes --end with --f0 (and --harmonics) for a matching chain, or --antenna with --band for an antenna. | \`new\` recebe --end com --f0 (e --harmonics) para uma cadeia de casamento, ou --antenna com --band para uma antena. |
| I_ANTENNA | Antenna {ref}, fed at pad {feed} on net {net}: its copper drawn without a net takes that net. | Antena {ref}, alimentada na ilha {feed} da rede {net}: o cobre dela desenhado sem rede recebe essa rede. |
| I_ANTENNA_JOIN | Antenna {ref} joins its feed to ground through {pads} by design, as an inverted-F does; the connectivity and port checks accept that join and no other. | A antena {ref} liga a alimentação ao GND por {pads} por projeto, como um F invertido; as checagens de conectividade e de porta aceitam essa ligação e nenhuma outra. |
| I_BAND | Band {f_lo_mhz} to {f_hi_mhz} MHz, f0 {f0_mhz} MHz; the pulse spans {f1_mhz} to {f2_mhz} MHz. | Banda de {f_lo_mhz} a {f_hi_mhz} MHz, f0 {f0_mhz} MHz; o pulso cobre de {f1_mhz} a {f2_mhz} MHz. |
| I_ANTENNA_DEFAULTS | Preset {preset} (provisional default), T_max {t_max_ns} ns (2·t0 + 60/f0), mesh n {mesh_n}, measured region {expand_h} substrate heights past the antenna and the chain, protected reach {reach_h} substrate heights, air gap {air_gap_mm} mm (λ/4 at f_lo) to a {boundary} absorber, far-field frequencies: {count}, on a {step_deg}° sphere. | Predefinição {preset} (padrão provisório), T_max {t_max_ns} ns (2·t0 + 60/f0), malha n {mesh_n}, região medida de {expand_h} alturas de substrato além da antena e da cadeia, alcance protegido de {reach_h} alturas de substrato, espaçamento de ar de {air_gap_mm} mm (λ/4 em f_lo) até um absorvedor {boundary}, frequências do campo distante: {count}, numa esfera de {step_deg}°. |

- [ ] **Step 7: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_cli_new.py tests/test_golden_v1.py tests/test_sexpr.py -q`. Expected: PASS.
- [ ] **Step 8: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(cli): new --antenna --band writes an antenna project, refusing modules, chip antennas and bands wider than an octave (Stage 3 design 5.1)"
graphify update .
```

---

### Task 5 [code]: The lint's two-layer exemption, for an antenna's geometry alone

**Files:**
- Modify:
  - `core/geometry/__init__.py`: `Geometry`;
  - `core/mesh/__init__.py`: `Mesh`, `build_mesh` and `_pairs` after `_edges`;
  - `core/mesh/rule.py`: `xy_lines`, `lint_hits` and `_faults`;
  - `core/mesh/gates.py`: `edge_lint`.
- Test: `tests/test_mesh_rule.py` and `tests/test_gates.py`.

**Interfaces:**
- Consumes: `_edges`, `SIMPLIFY`, `Protected`, `Piece`.
- Produces:
  - `Geometry.antenna: bool = False`, last.
  - `_pairs(pieces, prot) -> dict[str, set[Edge]]`.
  - `Mesh.exempt: dict[str, frozenset[Edge]] = field(default_factory=dict)`, last.
  - `xy_lines(..., exempt=frozenset())`, `lint_hits(lines, edges, d, exempt=())` and `_faults(lines, edges, d, exempt=())`.
  - Task 6 sets `Geometry.antenna` and proves the rule on the meander.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/test_mesh_rule.py` (imports gain `_pairs` beside `_edges`, `lint_hits` from `core.mesh.rule`, `Piece` from `core.geometry.copper`, `Protected` from `core.mesh.protect` and `box` from `shapely.geometry`):

```python
def test_only_opposite_edges_of_two_layers_within_20_um_are_paired():  # Stage 3 design 5.3: a two-layer helix; RF 3
    prot = Protected(frozenset({"RF"}), {layer: box(-1, -1, 10, 2) for layer in ("F.Cu", "B.Cu")}, frozenset(), ())
    top = Piece("F.Cu", "RF", box(0, 0, 5.5, 1), True)
    assert _pairs([top, Piece("B.Cu", "RF", box(5.5, 0, 9, 1), True)], prot) == {"x": {(5.5, -1), (5.5, 1)}, "y": set()}
    assert _pairs([top, Piece("B.Cu", "RF", box(5.53, 0, 9, 1), True)], prot) == {"x": set(), "y": set()}  # 30 µm
    assert _pairs([top, Piece("F.Cu", "GND", box(5.5, 0, 9, 1), True)], prot) == {"x": set(), "y": set()}  # one layer


def test_an_exempt_edge_passes_the_third_test_alone():  # Stage 3 design 5.3; RF 3
    lines, edges = np.array([5.425, 5.575]), [(5.5, -1), (5.5, 1)]  # each edge's inside line is the other's outside
    assert lint_hits(lines, edges, 0.3) == [(5.5, "outside_closer"), (5.5, "outside_closer")]
    assert lint_hits(lines, edges, 0.3, exempt={(5.5, -1), (5.5, 1)}) == []
    assert lint_hits(np.array([5.5, 5.6]), edges, 0.3, exempt=set(edges)) == [(5.5, "on_edge"), (5.5, "on_edge")]
```

  - In `tests/test_gates.py` (imports gain `replace` from `dataclasses` when it is missing):

```python
def test_edge_lint_reads_the_meshs_exempt_edges():  # Stage 3 design 5.3
    m = lint_mesh([0.97, 1.02], [(1.0, -1)])
    assert edge_lint(m)[0].reason == "outside_closer" and m.exempt == {}  # v1's Mesh exempts nothing
    assert edge_lint(replace(m, exempt={"x": frozenset({(1.0, -1)})})) == []
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_mesh_rule.py tests/test_gates.py -q`. Expected: FAIL with `cannot import name '_pairs'`.
- [ ] **Step 3: The exemption.**
  - **`Geometry.antenna`:** its docstring gains "`antenna`: an antenna's geometry (Stage 3 design 5.3), whose mesh exempts its two-layer pairs (core.mesh._pairs) from the edge lint's third test".
  - **`_pairs(pieces, prot)`:** each layer's protected edges, `_edges` of that layer's pieces, and per axis the edges that an edge of another copper layer with the opposite sign meets within `2 * SIMPLIFY`, both of each pair. Docstring: "The protected edges, per axis, that another copper layer's opposite edge meets, the metal on its other side, as on a two-layer helix (Stage 3 design 5.3): no line passes the lint's third test for both." Comment: `# ponytail: pairs by position across layers only, so two unrelated edges that happen to coincide are exempt too; computed for an antenna's geometry alone`.
  - **`lint_hits`'s `exempt`:** "outside_closer" is not raised for an edge in `exempt`. Docstring addition: "an edge of `exempt` (an antenna's two-layer pairs) is spared the third test, which no line can pass for both edges of a pair".
  - **`_faults` and `xy_lines`:** `xy_lines` passes its `exempt` to `_faults`, which passes it to `lint_hits`, so the slot depth's fallback judges the axis as the lint does.
  - **`build_mesh`:** `exempt = _pairs(geom.pieces, prot) if geom.antenna else {}`; each axis's `xy_lines` gets `frozenset(exempt.get(axis, ()))`, and the Mesh holds them in `exempt`. The docstring says so.
  - **`edge_lint`** passes `mesh.exempt.get(axis, ())`. `mesh_with_lint`'s re-mesh calls `build_mesh` again, which pairs again.
- [ ] **Step 4: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_meshcal.py tests/test_geometry_lid.py tests/test_golden_v1.py -q`. Expected: PASS. No v1 geometry sets `antenna`, so every v1 mesh is built by v1's code; the pins prove it.
- [ ] **Step 5: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(mesh): opposite edges of two copper layers that meet pass the edge lint's third test, for an antenna's geometry alone (Stage 3 design 5.3)"
graphify update .
```

---

### Task 6 [code]: The antenna's geometry

**Files:**
- Modify:
  - `pipeline.py`: `load` (L84–92);
  - `core/geometry/__init__.py`: `build_geometry`;
  - `core/geometry/copper.py`: `connectivity`;
  - `core/geometry/sections.py`: `STAIR_MM` and `staircased`;
  - `core/geometry/lid.py`: `find_lid`'s ponytail comment;
  - `core/messages.py`: W_LIDS_LEFT_OUT and W_AIR_BOX after W_STAIRCASED;
  - `po/*` and the `.mo`.
- Create: `tests/test_antenna_geometry.py`.
- Test: `tests/test_geometry_copper.py`.

**Interfaces:**
- Consumes: Task 2's `adopt`; Task 3's `antenna`, `board_region`, `air_gap` and `REACH_H`; Task 4's `antenna_project`; Task 5's `Geometry.antenna`.
- Produces:
  - `load(path)` adopts an antenna's copper before the geometry.
  - `connectivity(pieces, rods, roi, nets, crop, join=None)`.
  - `STAIR_MM = 0.5` and `staircased(polygons) -> bool`.
  - For an antenna, `build_geometry` gives the measured region as the ROI, the whole board's copper, the join accepted, W_STAIRCASED for diagonal antenna copper, a lid over the whole board with W_LIDS_LEFT_OUT for the other shields, W_AIR_BOX outside the tested air box, and `antenna=True`.

- [ ] **Step 1: Write the failing tests.** `tests/test_antenna_geometry.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path

import pytest

from kicad_rf_studio import cli, pipeline
from kicad_rf_studio.core.project import load_project, save_project
from test_antenna_kicad import fp
from test_cli_antenna import FIX, IFA, antenna_project
from test_tracer import smd

LOCAL_X = (-11.85, -11.35, -9.65, -9.15, -7.15, -6.65, -4.95, -4.45, -2.45, -1.95, -0.25, 0.25, 1.65, 2.55)  # SWRA117D


def model_of(pj: Path):
    project, board, geom, notes = pipeline.load(pj)
    return pipeline.build_model(project, board, geom), geom, notes


@pytest.mark.parametrize("name", ["ifa2g4", "ifa2g4_pi", "meander915"])
def test_each_antenna_fixture_builds_its_model(tmp_path, name):  # design 5.3; RF 3
    model, geom, notes = model_of(antenna_project(tmp_path, FIX / f"{name}.kicad_pcb"))
    assert model.blocked == [] and model.mesh.d == 0.3 and pipeline.stops(notes) == 0 and geom.antenna
    staircased = [p for code, p in notes if code == "W_STAIRCASED"]
    assert staircased == ([{"net": "RF"}] if name == "meander915" else [])  # SWRA416's 18 diagonals: a warning


def test_the_two_layer_exemption_is_the_antennas_alone(tmp_path):  # design 5.3; v1 byte for byte; RF 3
    project, board, geom, _ = pipeline.load(antenna_project(tmp_path, FIX / "meander915.kicad_pcb"))
    blocked = pipeline.build_model(project, board, replace(geom, antenna=False)).blocked  # v1's lint, as before
    assert [code for code, _ in blocked] == ["E_EDGE_LINT"] and pipeline.build_model(project, board, geom).blocked == []


def test_the_inverted_f_join_is_accepted_and_tied_to_its_pads(tmp_path):  # design 5.3; RF 2
    pj = antenna_project(tmp_path)
    assert pipeline.load(pj)[3] == []  # no W_NETLESS_COPPER, no short, no W_AIR_BOX
    data = load_project(pj)
    data["antenna"]["join"] = []
    save_project(pj, data)
    assert ("E_SHORT_IN_ROI", {"nets": "GND, RF"}) in pipeline.load(pj)[3]


def test_fit2d_measures_the_feed_line_and_never_the_radiator(tmp_path):  # design 5.3
    _, geom, _ = model_of(antenna_project(tmp_path))
    assert [(s.net, s.width, s.length) for s in geom.sections] == [("RF", 0.6, 1.975), ("RF", 1.35, 10.0)]


def test_the_antenna_is_in_the_fine_set_and_its_edges_move_with_it(tmp_path):  # design 5.3: placement
    moved = tmp_path / "moved.kicad_pcb"
    text = IFA.read_text(encoding="utf-8")
    i = text.index("(at 100 100)", text.index('(footprint "RF_Antenna:'))
    moved.write_text(text[:i] + "(at 100.3 100)" + text[i + len("(at 100 100)"):], encoding="utf-8")  # AE1 one d along x
    for board, x in ((IFA, 100.0), (moved, 100.3)):
        model, _, _ = model_of(antenna_project(tmp_path / board.stem, board, (2.4e9, 2.4835e9)))
        assert {round(x + v, 6) for v in LOCAL_X} <= {e for e, _ in model.mesh.edges["x"]}


def test_every_shield_is_a_lid_candidate_and_one_gets_it(tmp_path):  # design 5.3; the "one lid" ruling
    def frame(ref, x, y, s):  # a shield: GND pads at the corners of an s mm square
        pads = (smd(k, "GND", x=dx, y=dy) for k, (dx, dy) in enumerate(((0, 0), (s, 0), (0, s), (s, s)), 1))
        return fp(ref, "Lib:Shield", *pads, at=f"{x} {y}")

    lib = "Resistor_SMD:R_0402_1005Metric"
    shields = (frame("SH1", 108, 104, 8) + fp("R9", lib, smd(1, "N9"), smd(2, "GND", x=1), at="112 108", value="1k")
               + frame("SH2", 116, 116, 4) + fp("R8", lib, smd(1, "N8"), smd(2, "GND", x=1), at="117.5 118", value="1k"))
    board = tmp_path / "shields.kicad_pcb"
    board.write_text(IFA.read_text(encoding="utf-8").rstrip()[:-1] + shields + ")\n", encoding="utf-8")
    pj, notes = cli.new_antenna(board, "U1.1", "AE1", (2.4e9, 2.4835e9), output=tmp_path / "p")
    assert ("W_LID_HEIGHT_MISSING", {"refs": "SH1, SH2"}) in notes  # both, far outside the measured region
    save_project(pj, {**load_project(pj), "lid_height_mm": 1.5})
    _, _, geom, notes = pipeline.load(pj)
    assert geom.lid.ref == "SH1" and ("W_LIDS_LEFT_OUT", {"ref": "SH1", "refs": "SH2"}) in notes


def test_an_air_box_outside_the_tested_setting_is_warned(tmp_path):  # design 5.2; P3-A's MUR twin; RF 5
    pj = antenna_project(tmp_path)
    save_project(pj, {**load_project(pj), "boundary": "mur", "air_gap_mm": 20.0})
    assert ("W_AIR_BOX", {"gap_mm": "20.0", "quarter_mm": "31.2", "boundary": "mur"}) in pipeline.load(pj)[3]
```

  - In `tests/test_geometry_copper.py` (imports gain `Piece` and `connectivity` from `core.geometry.copper`):

```python
def test_a_join_accepts_touches_within_it_and_no_other():  # Stage 3 design 5.3; RF 2
    rf, gnd = Piece("F.Cu", "RF", box(0, 0, 4, 1), True), Piece("F.Cu", "GND", box(3.5, 0, 6, 1), True)
    roi, crop, join = box(-10, -10, 10, 10), box(-20, -20, 20, 20), box(3.4, -0.1, 4.1, 1.1)
    assert connectivity([rf, gnd], [], roi, ["RF"], crop) == [("E_SHORT_IN_ROI", {"nets": "GND, RF"})]
    assert connectivity([rf, gnd], [], roi, ["RF"], crop, join=join) == []
    other = Piece("F.Cu", "GND", box(-1, 0, 0.2, 1), True)  # a second touch, outside the join
    assert connectivity([rf, gnd, other], [], roi, ["RF"], crop, join=join) == [("E_SHORT_IN_ROI", {"nets": "GND, RF"})]
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_antenna_geometry.py tests/test_geometry_copper.py -q`. Expected: FAIL, with `join` an unexpected keyword and the meander's model blocked by E_EDGE_LINT (its geometry is not yet an antenna's).
- [ ] **Step 3: `pipeline.load`.** For an antenna, `adopt(board, project["antenna"]["ref"], project["chain"]["nets"][-1])` right after `load_board`. The docstring says so.
- [ ] **Step 4: `connectivity`'s `join`.**
  - The geometry where an antenna's own copper joins its feed to ground (Stage 3 design 5.3). A short whose touch lies within it is no short.
  - Docstring addition: "`join` (None: none) …"; the check is `geoms[i].intersection(geoms[j]).within(join)`.
- [ ] **Step 5: `staircased(polygons)`.**
  - True when an edge at least `STAIR_MM` long runs along neither axis, by the mesh's ALONG test (each of |dx| and |dy| above the other's 1/50). The other's 1/50 is restated, not imported, since core.mesh is built on core.geometry.
  - Comment: `# ponytail: long straight off-axis edges only; an arc or a circle whose chords are all under STAIR_MM is not flagged`.
- [ ] **Step 6: `build_geometry`,** for an antenna (`antenna(project)`):
  - **Region:** `board_region(board, chain, ports, zs, f_max(project), region_expand_h(project))` replaces `build_region`.
  - **Join:** `join = union of the join pads' polygons (project["antenna"]["join"]) buffered by 2 * SIMPLIFY` (None when empty), passed to `connectivity`.
  - **Staircase:** `W_STAIRCASED {"net": chain.nets[-1]}` is appended, unless the sections already raised it for that net, when `staircased` holds for the areas whose `ref` is the antenna's.
  - **Lid:** `find_lid` gets `replace(region, roi=region.crop)`, so every top-side shield on the board is a candidate. With a lid, W_LIDS_LEFT_OUT `{"ref": lid.ref, "refs"}` names the other top-side shields of `classes.shields`, when there are any. `find_lid` itself is unchanged, so v1's lines keep their bytes; its existing ponytail comment becomes "one lid, the shield over most of the ROI, or of the board for an antenna (Geometry holds one Lid); an antenna's other shields are named in W_LIDS_LEFT_OUT".
  - **Air box:** W_AIR_BOX `{"gap_mm" (:.1f), "quarter_mm" (:.1f of air_gap(f_lo)), "boundary"}` when the boundary is not "pml_8" or `air_gap_mm` is below `air_gap(f_lo)`: only PML_8 at λ/4 has passed a gate.
  - **Antenna:** the Geometry is built with `antenna=True`.
  - **Ceiling:** comment the branch `# ponytail: the antenna group is the footprint's own copper; a radiator drawn as tracks on the feed net (fit2d would measure it as feed line) or as board graphics or zones outside the footprint is not in it`.
- [ ] **Step 7: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| W_LIDS_LEFT_OUT | Shields {refs} on the antenna's board get no lid: one lid is modelled, over {ref}, the shield over most of the board. | As blindagens {refs} na placa da antena ficam sem tampa: uma só tampa é modelada, sobre {ref}, a blindagem sobre a maior parte da placa. |
| W_AIR_BOX | The antenna's air box is outside the tested setting: an air gap of {gap_mm} mm (λ/4 at f_lo is {quarter_mm} mm) to a {boundary} absorber. Only PML_8 at λ/4 or more has passed a gate (P3-A); a MUR twin's energy rose 16 dB at 0.53 λ, and gate P3-C tests the rest. | A caixa de ar da antena está fora da configuração testada: espaçamento de ar de {gap_mm} mm (λ/4 em f_lo é {quarter_mm} mm) até um absorvedor {boundary}. Só a PML_8 a λ/4 ou mais passou numa checagem prévia (P3-A); a energia de uma gêmea com MUR subiu 16 dB a 0.53 λ, e a checagem prévia P3-C testa o resto. |

- [ ] **Step 8: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_geometry_lid.py tests/test_gates.py tests/test_sexpr.py -q`. Expected: PASS. A missed prototype number (the sections, LOCAL_X) stops the task (Global Constraints).
- [ ] **Step 9: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(geometry): the antenna's copper in the measured region, its feed-to-ground join accepted alone, every shield a lid candidate and the untested air box warned (Stage 3 design 5.2, 5.3)"
graphify update .
```

---

### Task 7 [code]: The antenna's model spec

**Files:**
- Modify:
  - `core/model/spec.py`: `air_box`, `excitation` and `model_spec`;
  - `core/model/csx.py`: the ponytail comment at the far-field frequency check;
  - `stoprule.py`: `FLAT_PERIODS`, `flat_window`, `stop_rule` and `_flat`;
  - `pipeline.py`: `build_model`.
- Create: `tests/test_antenna_model.py`.
- Test: `tests/test_stoprule.py`.

**Interfaces:**
- Consumes: Task 3's `air_cell` and `band`; Task 6's `model_of` (from `test_antenna_geometry`); plan 1's `with_pml`, `metal_in_pml`, `PML_CELLS` and `NF2FF_MAX`.
- Produces:
  - `air_box(mesh: Mesh, gap: float, cell: float, pml: bool) -> Mesh`.
  - The antenna spec keys: `"boundary"` (pml_8 only), `"nf2ff"` `{"f_hz", "center"}` (no part port only), `"join"` `[[[x0, y0, z0], [x1, y1, z1]], …]` mm, and the excitation's `"flat_s"`.
  - `flat_window(f0: float) -> float`.

- [ ] **Step 1: Write the failing tests,** `tests/test_antenna_model.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest

from kicad_rf_studio.core.geometry.region import air_cell
from kicad_rf_studio.core.mesh.gates import edge_lint
from kicad_rf_studio.core.model.csx import PML_CELLS
from kicad_rf_studio.core.model.spec import metal_in_pml
from kicad_rf_studio.core.project import load_project, save_project
from kicad_rf_studio.stoprule import flat_window
from test_antenna_geometry import model_of
from test_cli_antenna import FIX, antenna_project


def test_an_antennas_model_sits_in_an_air_box_under_pml_8(tmp_path):  # design 5.2, 5.3
    model, geom, _ = model_of(antenna_project(tmp_path))
    s, w = model.spec, geom.region.walls
    assert s["boundary"] == "pml_8" and metal_in_pml(s) == [] and edge_lint(model.mesh) == []  # the board's lines kept
    for k, a in enumerate("xyz"):
        v = np.array(s["mesh"][a])
        steps = np.diff(v)
        assert np.allclose(steps[:PML_CELLS], steps[0]) and np.allclose(steps[-PML_CELLS:], steps[-1])
        assert v[PML_CELLS] == pytest.approx(w[2 * k] - 31.228381, abs=2e-6)  # the gap past the walls
        assert v[-1 - PML_CELLS] == pytest.approx(w[2 * k + 1] + 31.228381, abs=2e-6)
        assert steps.max() <= air_cell(2.99e9) + 1e-6
    assert [len(s["mesh"][a]) for a in "xyz"] == [135, 137, 71]  # the prototype's


def test_the_far_field_box_join_and_flat_window_are_the_antennas(tmp_path):  # design 5.3-5.5
    model, geom, _ = model_of(pj := antenna_project(tmp_path))
    s, zs = model.spec, geom.zs
    assert s["nf2ff"] == {"f_hz": load_project(pj)["far_field"]["f_hz"],
                          "center": [107.0, -109.0, round((zs[0].z0 + zs[-1].z1) / 2, 6)]}  # the board's centre
    cu = [z for z in zs if z.kind == "copper"]
    assert s["join"] == [[[101.35, -100.55, cu[0].z0], [102.85, -99.45, cu[-1].z1]]]  # AE1.2 grown by d = 0.3
    exc = s["excitation"]
    assert (exc["f1"], exc["f2"], exc["t_max"]) == (1.84e9, 2.99e9, 30e-9)
    assert exc["flat_s"] == flat_window(2.44175e9) == pytest.approx(8.19085e-9, rel=1e-5)


def test_part_ports_record_no_far_field_and_mur_adds_no_pml(tmp_path):  # design 5.5, 5.2
    model, _, _ = model_of(antenna_project(tmp_path / "pi", FIX / "ifa2g4_pi.kicad_pcb"))
    assert "nf2ff" not in model.spec and model.spec["boundary"] == "pml_8"  # 1 + 3 jobs: a part-port run
    pj = antenna_project(tmp_path / "mur")
    save_project(pj, {**load_project(pj), "boundary": "mur"})
    model, _, _ = model_of(pj)
    # provisional: MUR is the untested fallback (W_AIR_BOX), which plan 4's P3-C tests and may re-pin
    assert "boundary" not in model.spec and [len(model.spec["mesh"][a]) for a in "xyz"] == [119, 121, 55]
```

  In `tests/test_stoprule.py`, with `math` and `flat_window` imported:

```python
def test_an_antennas_flat_window_counts_20_periods_of_f0():  # design 5.4
    exc = {"f1": 1.84e9, "f2": 2.99e9, "t0": 9 / (math.pi * 1.15e9)}
    rec = trace("flat", 1, 0, 1.84e9, 2.99e9)
    assert round(stop_rule(rec, 0, "normal", exc).t * 1e9, 3) == 17.179  # v1's 5 ns
    v = stop_rule(rec, 0, "normal", {**exc, "flat_s": flat_window(2.44175e9)})
    assert (v.kind, round(v.t * 1e9, 3)) == ("flat", 20.377)
    assert (flat_window(5e9), flat_window(915e6)) == (5e-9, pytest.approx(21.858e-9, rel=1e-4))
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_antenna_model.py tests/test_stoprule.py -q`. Expected: FAIL with `cannot import name 'flat_window'`.
- [ ] **Step 3: `stoprule.py`.**
  - `FLAT_PERIODS = 20`, commented "an antenna's flat window, in periods of f0 (Stage 3 design 5.4)".
  - `flat_window(f0) = max(FLAT_S, FLAT_PERIODS / f0)`.
  - `_flat` takes `window=FLAT_S` in place of FLAT_S, and `stop_rule` passes `exc.get("flat_s", FLAT_S)`.
- [ ] **Step 4: `spec.py` and `csx.py`.**
  - **`air_box`:**
    - Docstring: "`mesh` (an antenna's, wall to wall around the board) with each axis graded at RATIO up to `cell` through `gap` mm of air past both its ends, the PML's inner edge (Stage 3 design 5.2, 5.3), then with_pml when `pml`; on the 1e-6 mm grid. smooth_mesh_lines only adds lines, so the board's stay, and so do the Mesh's edges and exempt pairs."
    - Body: per axis, `lines = [round(float(v), 6) for v in smooth_mesh_lines(np.r_[old, old[0] - gap, old[-1] + gap], cell, RATIO)]`, then `replace(mesh, x=…, y=…, z=…)`.
  - **`excitation`** adds `"flat_s": flat_window(project["f0_hz"])` for an antenna.
  - **`model_spec`,** for an antenna (docstring: "the antenna keys, only for an antenna (Stage 3 design 5.2–5.5)"):
    - `"boundary": "pml_8"` when `project["boundary"] == "pml_8"`.
    - `"nf2ff"` when no port is a part: `{"f_hz": project["far_field"]["f_hz"], "center": [the outline's bounds' centre x and y, (zs[0].z0 + zs[-1].z1)/2]}`, each to 1e-6. The outline falls back to the crop.
    - `"join"` for each pad name in `project["antenna"]["join"]`, through `ports._pad`: its polygon's bounds grown by `mesh.d` in x and y, and z from the lowest copper slab's z0 to the highest's z1, each to 1e-6. The key is absent when there is no join.
  - **`csx.py`'s comment** at the far-field frequency check becomes `# ponytail: a crash (E_WORKER_FAILED); an antenna's frequencies come from project.json's far_field.f_hz, which check_project refuses outside the pulse band first`.
- [ ] **Step 5: `pipeline.build_model`.** After `dt_floor_reference`, for an antenna:

```python
        mesh = air_box(mesh, project["air_gap_mm"], air_cell(band(project)[1]), project["boundary"] == "pml_8")
```

  The docstring adds "an antenna's mesh in its air box (Stage 3 design 5.2)".
- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_model_spec.py tests/test_model_csx.py tests/test_p3a.py tests/test_antenna_geometry.py -q`. Expected: PASS. No v1 spec holds `"join"`, and every v1 excitation lacks `"flat_s"`. A missed prototype number (the line counts, the join box) stops the task.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(model): the air box graded to lambda(f2)/20 under PML_8, the far-field box at the board's centre, the join's boxes and the antenna's flat window (Stage 3 design 5.2-5.5)"
graphify update .
```

---

### Task 8 [code]: The worker's join cut and angle step

**Files:**
- Modify:
  - `core/model/readers.py`: `pec_roots`;
  - `worker.py`: `_setup`, `_far_field` and the comment at GRIDS;
  - `pipeline.py`: `far_field`.
- Test: `tests/test_readers.py` and `tests/test_worker.py`.

**Interfaces:**
- Consumes: Task 7's `"join"` spec key; plan 1's mode "nf2ff", GRIDS and `runs.write_job`'s extra keys.
- Produces:
  - `pec_roots(path, lines, nodes, cut=())`.
  - job.json's `"step_deg"` and `pipeline.far_field(job, step_deg=5)`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_readers.py`:

```python
def test_a_cut_join_separates_the_copper_it_held():  # Stage 3 design 5.3: the port-short check; RF 2
    nodes = [[-5, 0, 0.5], [3, 0, 0.535], [-5, 0, 0]]  # the strip at both ends, the ground
    whole = pec_roots(DUMPS / "PEC_dump.vtp", LINES, nodes)
    cut = pec_roots(DUMPS / "PEC_dump.vtp", LINES, nodes, [[[-0.3, -1.0, 0.4], [0.3, 1.0, 0.6]]])
    assert whole[0] == whole[1] != whole[2] and cut[0] != cut[1] and cut[2] == whole[2]
```

  In `tests/test_worker.py`:
  - The setup test that compares `s["pec"][0]` with `pec_roots(...)` gains a twin. Its spec holds `"join": [[[-0.3, -1.0, 0.4], [0.3, 1.0, 0.6]]]`, and the test asserts `s["pec"][0] == pec_roots(DUMPS / "PEC_dump.vtp", LINES, nodes, spec["join"])`.
  - `test_nf2ff_mode_transforms_each_grid_afresh_into_a_file_of_its_own` gains a second run whose job.json adds `"step_deg": 10`. It asserts the sphere call's θ and φ lengths are `(19, 36)`, and that the two cuts' calls are unchanged.

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_readers.py tests/test_worker.py -q`. Expected: FAIL with `pec_roots() takes 3 positional arguments but 4 were given`.
- [ ] **Step 3: `pec_roots`'s `cut`.**
  - Boxes `[[x0, y0, z0], [x1, y1, z1]]` in mm. `pec_roots` already maps each dump point to its nearest mesh node (`_nearest` per axis); an edge with an end whose node lies inside a box, bounds included, is skipped.
  - The test reads the node's own line coordinates in mm, never the dump's float32 metres. At x, y ≈ 100 mm half a float32 step (3.7 nm) is larger than any tolerance a box could take, and the top copper face sits 2 pm off its line in the dump: on ifa2g4's real setup an exact metre test let the short through, and a 1 nm one held only by that rounding.
  - Docstring: "an antenna's feed-to-ground join, cut at its mesh nodes so that the port-short check sees any other short (Stage 3 design 5.3)". Comment: `# ponytail: a real short inside the join's box is cut too; the box is the join pads' bounds grown by d`.
- [ ] **Step 4: The worker and the step.**
  - **`worker._setup`** passes `spec.get("join", ())` to each port's `pec_roots`.
  - **`worker._far_field`:** GRIDS keeps all three keys, which `pipeline.far_field`, the fake worker and `test_worker` iterate. `_far_field` replaces only the sphere's θ and φ, with `np.arange(0, 181, step)` and `np.arange(0, 360, step)` for `step = job.get("step_deg", 5)`. The ponytail comment at GRIDS becomes "the sphere's step comes from job.json; the cuts stay at 1°".
  - **`pipeline.far_field(job, step_deg=5)`** writes `step_deg=step_deg` into the transform's job.json.
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_golden_v1.py tests/test_model_csx.py tests/test_p3a.py tests/test_post_farfield.py tests/test_run.py -q`. Expected: PASS: a v1 spec has no `"join"`, so its cut is empty.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(worker): the port-short check cuts an antenna's join at its mesh nodes, and the far field's sphere takes the project's angle step (Stage 3 design 5.3, 5.5)"
graphify update .
```

---

### Task 9 [code]: Cost's cell split and the gates line

**Files:**
- Modify:
  - `runs.py`: the constants after MB_PER_MCELL;
  - `core/model/spec.py`: `cell_split` after `metal_in_pml`;
  - `pipeline.py`: `cost_notes`, `prepare`, `cost` and `simulate`;
  - `core/messages.py`: I_COST_SPLIT after I_COST_CELLS, and I_GATES_PASSED_PML after I_GATES_PASSED;
  - `po/*` and the `.mo`;
  - `tests/test_sexpr.py`: the gates tuple.
- Test: `tests/test_cost_model.py` and `tests/test_antenna_model.py`.

**Interfaces:**
- Consumes: Task 7's antenna spec; `per_job_mcs` and `duration`.
- Produces:
  - `runs.PML_WEIGHT = 6.38` and `runs.SMALL_SPEED = 0.384`.
  - `cell_split(spec) -> tuple[int, int, int]` (board, air, PML).
  - `prepare(model, emit, run_dir=None, *, small=False)`.
  - The corrected time in I_COST_TIME and I_COST_PREDICTED for an antenna.
  - I_COST_SPLIT and I_GATES_PASSED_PML.
  - No calibration refresh from an antenna run.

- [ ] **Step 1: Write the failing tests.** In `tests/test_cost_model.py` (imports gain `cell_split`):

```python
def test_an_antennas_cost_splits_its_cells_and_weights_the_pml():  # design 5.9; P3-A's decisions
    lines = np.arange(30.0)  # 30 lines per axis: 27000 nodes, 12³ inside the PML's 9 lines a face
    spec = {"boundary": "pml_8", "mesh": {a: lines.tolist() for a in "xyz"}, "ports": [{"part": False}],
            "materials": [{"solids": [{"x": [10.0, 19.0, 19.0, 10.0], "y": [10.0, 10.0, 19.0, 19.0], "z": [12.0, 14.0]}]}]}
    assert cell_split(spec) == (300, 1428, 25272)
    m = Model(Mesh(lines, lines, lines, 1.0, 0.4, {}, {}), spec, [], 1.5e-12)
    project = {"schema": 2, "t_max_s": 1e-9, "gates": GATES, "mesh": {"n": 2},
               "results": {"model_hash": spec_hash(spec), "jobs": [{"verdict": "converged", "t_stop": 5e-10}]}}
    notes = dict(cost_notes(m, project, {"dt": 1e-12, "node": [0, 1, 2, 3]}, 4, 1, 100.0))
    assert notes["I_COST_SPLIT"] == {"board": "0.00", "air": "0.00", "pml": "0.03", "weight": "6.38", "ratio": "0.384"}
    step = (1728 + 6.38 * 25272) / (100.0 * 0.384 * 1e6)  # s per 1 ps step
    assert (notes["I_COST_TIME"]["time"], notes["I_COST_PREDICTED"]["time"]) == (duration(1000 * step), duration(500 * step))
    v1 = {**project, "schema": 1}
    assert "I_COST_SPLIT" not in dict(cost_notes(m, v1, {"dt": 1e-12, "node": [0, 1, 2, 3]}, 4, 1, 100.0))
```

  In `tests/test_antenna_model.py` (imports gain `json`, `pipeline` and `runs`):

```python
def codes(run_dir):
    return [json.loads(line)["code"] for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_an_antenna_runs_its_gates_with_the_absorber_and_leaves_the_calibration(tmp_path, calibrated):  # P3-A
    project, board, geom, _ = pipeline.load(antenna_project(tmp_path / "p"))
    model = pipeline.build_model(project, board, geom)
    before = runs.load_settings()
    done, _, _ = pipeline.simulate(model, project, tmp_path / "run")
    seen = codes(tmp_path / "run")
    assert "I_GATES_PASSED_PML" in seen and "I_GATES_PASSED" not in seen and "I_COST_SPLIT" in seen
    assert [j["verdict"] for j in done] == ["converged"] and runs.load_settings() == before


def test_cost_and_preview_take_an_antenna_project(tmp_path, calibrated, monkeypatch):  # design 5.1
    pj = antenna_project(tmp_path / "p")
    assert pipeline.cost(pj, tmp_path / "cost") == 0 and "I_COST_SPLIT" in codes(tmp_path / "cost")
    opened = []
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: opened.append(job))
    assert pipeline.preview(pj) == 0
    assert "boundary" in json.loads((opened[0].parent / "model.json").read_text(encoding="utf-8"))
```

  In `tests/test_sexpr.py`, `test_the_pt_br_catalog_keeps_the_glossarys_nevers`'s gates tuple gains `"I_GATES_PASSED_PML"`.
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_cost_model.py tests/test_antenna_model.py -q`. Expected: FAIL with `cannot import name 'cell_split'`.
- [ ] **Step 3: The constants.**
  - `PML_WEIGHT, SMALL_SPEED = 6.38, 0.384`, commented "gate P3-A (docs/validation/2026-10-29-p3-a.md §4): a PML cell costs 6.38 ordinary cells, and a small antenna model runs at 0.384 times the calibration's own one-job speed at its threads. They compose as (N − N_PML + w·N_PML)/N over the ratio, never w on every cell (Stage 3 design 5.9)".
  - Plus `# ponytail: one PC's gate (16 CPUs), one job alone; 0.384 at a pool above 1 is unmeasured, and a calibration that never timed one job at its threads (12 CPUs at 4 × 3) falls back to aggregate/pool and over-predicts about 3 times; plan 4's P3-C refits them`.
- [ ] **Step 4: `cell_split(spec)`.**
  - Docstring: "An antenna mesh's nodes as cost counts cells, (board, air, PML) (Stage 3 design 5.9): the PML's, the nodes openEMS's UPML updates, PML_CELLS + 1 lines in from each face, none without "boundary"; the board's, the nodes inside the box of every material solid (the dielectric, the masks included); the air's, the rest."
  - The board's count is the product over axes of the lines inside that box, inclusive.
- [ ] **Step 5: `cost_notes`.**
  - For an antenna, I_COST_SPLIT follows I_COST_CELLS, in M with 2 decimals, with `weight` `f"{runs.PML_WEIGHT:g}"` and `ratio` `f"{runs.SMALL_SPEED:g}"`.
  - `time()` counts `cells + (runs.PML_WEIGHT - 1) * pml` cells at `per_job_mcs * runs.SMALL_SPEED`. RAM keeps the raw cells: `# ponytail: RAM counts the cells, not the far-field dumps (12 MB at 2.4 GHz, r1); add them if W_RAM misleads`.
  - The docstring names the antenna's split and corrections.
- [ ] **Step 6: `prepare`'s `small`.**
  - With `small` and a pool of 1, the per-job MC/s is the calibration's own one-job speed at its threads, `entry["single"][str(threads)]`, when the entry holds it, else `per_job_mcs(entry, 1)`. P3-A measured SMALL_SPEED against that speed, which no run refreshes; a v1 run at pool 1 refreshes `levels["1"]`.
  - The docstring says so. `cost` and `simulate` pass `small=antenna(project)`; `p0` and `p3a` leave it False.
- [ ] **Step 7: `simulate`.**
  - It emits `"I_GATES_PASSED_PML" if "boundary" in model.spec else "I_GATES_PASSED"`.
  - It refreshes the calibration only when `not antenna(project)`, commented "an antenna's speed holds the PML and the small model, which cost applies to the calibration's own (Stage 3 design 5.9)".
- [ ] **Step 8: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_COST_SPLIT | Cells: {board} M in the board, {air} M of air and {pml} M of PML; the time counts a PML cell as {weight} cells and runs this model at {ratio} × the calibrated speed (gate P3-A). | Células: {board} M na placa, {air} M de ar e {pml} M de PML; o tempo conta uma célula de PML como {weight} células e executa este modelo a {ratio} × a velocidade calibrada (checagem prévia P3-A). |
| I_GATES_PASSED_PML | Gates passed: edge lint, fit2d, timestep floor (dt {dt} s), the absorber (nothing within the PML or the 2 cells inside it), port connectivity and unused primitives. | Checagens prévias aprovadas: edge lint, fit2d, piso do passo de tempo (dt {dt} s), o absorvedor (nada dentro da PML ou nas 2 células junto à sua borda interna), conectividade das portas e primitivas não usadas. |

- [ ] **Step 9: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_cli_cost.py tests/test_run.py tests/test_preview.py tests/test_p3a.py tests/test_sexpr.py tests/test_golden_v1.py -q`. Expected: PASS. v1's cost lines and gates line are unchanged.
- [ ] **Step 10: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(cost): an antenna's cells split into board, air and PML with gate P3-A's PML weight and small-model speed (Stage 3 design 5.9)"
graphify update .
```

---

### Task 10 [code]: The antenna's numbers, lines and files

**Files:**
- Modify:
  - `core/post/farfield.py`: `FarField` and `read_far_field`;
  - `core/post/waves.py`: `band_grid` and `layout`'s default grid and markers;
  - `core/post/outputs.py`: `write`'s order;
  - `core/messages.py`: the antenna's lines after I_VERIFY_SCOPE, and the limits after I_LIMIT_LOSS;
  - `po/*` and the `.mo`.
- Create: `core/post/antenna.py` and `tests/test_post_antenna.py`.
- Test: `tests/test_post_farfield.py` and `tests/test_post_outputs.py`.

**Interfaces:**
- Consumes: plan 1's `read_far_field`, `port_powers`, `efficiencies` and `eta_lines`; Task 3's `pulse_band`; outputs' `write` and `rf.plotting.smith`.
- Produces:
  - `FarField.e_theta` and `e_phi`, each (F, T, P) complex.
  - In `waves.py`: `band_grid(project) -> np.ndarray`, and `layout(project, results)` on that grid for an antenna, with markers [f0].
  - `write` replaces any `*summary.csv`, then any `*summary.png`, before the rest.
  - In `core/post/antenna.py`:
    - `ANTENNA_OUTPUTS` (a regex), `ANTENNA_LIMITS` (a tuple of codes) and `LEVELS_DB = (-10.0, -6.0)`.
    - `zin(s11) -> np.ndarray` and `shown_zin(z: complex) -> str`.
    - `resonance(f, s11) -> tuple[int, float]` and `bandwidth(f, s11, k, level_db) -> tuple[float | None, float | None] | None`.
    - `s11_lines(project, f, s11) -> list[tuple[str, dict]]`.
    - `far_field_of(paths: dict[str, Path], waves: Path) -> dict` (sphere, elevation, azimuth, p_acc, p_inc, eff).
    - `far_field_lines(far) -> list[tuple[str, dict]]`.
    - `farfield_csv(far) -> bytes` and `antenna_csv(far, s11_far) -> bytes`.
    - `draw_antenna(fig, f, s11, project, far, name) -> None` and `antenna_png(f, s11, project, far, name) -> bytes`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_post_farfield.py`:

```python
def test_e_theta_and_e_phi_are_the_transforms_and_agree_with_d():  # design 5.6: the far-field CSV
    s = read_far_field(FAR / "sphere.h5")
    assert s.e_theta.shape == s.e_phi.shape == s.d.shape and s.e_theta.dtype == complex
    power = (abs(s.e_theta) ** 2 + abs(s.e_phi) ** 2) / (2 * 376.730313668)  # W/sr at r = 1 m
    assert np.allclose(power, s.d * s.p_rad[:, None, None] / (4 * np.pi), rtol=1e-6)
```

  Its `test_a_far_field_file_in_another_layout_is_refused` stays as it is: E is read after the layout check, so the legacy file still raises ValueError.

  In `tests/test_post_outputs.py` (imports gain `os`, `write` and `ANTENNA_OUTPUTS` where missing):

```python
def test_the_summaries_are_replaced_first(tmp_path, monkeypatch):  # spec C-27: a held summary refuses before anything
    seen, real = [], os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: seen.append(Path(b).name) or real(a, b))
    write(tmp_path, dict.fromkeys(("layout.s1p", "antenna_summary.png", "antenna_summary.csv"), b"x"), ANTENNA_OUTPUTS, "c")
    assert seen == ["antenna_summary.csv", "antenna_summary.png", "layout.s1p"]
```

  `tests/test_post_antenna.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import math
from pathlib import Path

import numpy as np
import pytest
from matplotlib.figure import Figure

from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.post.antenna import (ANTENNA_LIMITS, antenna_csv, antenna_png, bandwidth, draw_antenna,
                                                far_field_lines, far_field_of, farfield_csv, resonance, s11_lines,
                                                shown_zin, zin)
from kicad_rf_studio.core.post.waves import band_grid
from test_project import antenna_dict

FAR = Path(__file__).parent / "fixtures" / "farfield"
F = np.linspace(1.84e9, 2.99e9, 2301)


def dip(f, at=2.44e9, width=0.1e9):  # a resonance at `at`, |S11| 0.05
    return 0.9 - 0.85 * np.exp(-((f - at) / width) ** 2)


def edges(level_db):  # the exact crossings of dip()
    g = (0.9 - 10 ** (level_db / 20)) / 0.85
    return 2.44e9 - 0.1e9 * math.sqrt(-math.log(g)), 2.44e9 + 0.1e9 * math.sqrt(-math.log(g))


def far_of():
    return far_field_of({g: FAR / f"{g}.h5" for g in ("sphere", "elevation", "azimuth")}, FAR / "waves.npz")


def test_resonance_and_bandwidth():  # design 5.6
    k, f_res = resonance(F, dip(F))
    assert f_res == pytest.approx(2.44e9, abs=1e5)
    for level in (-10.0, -6.0):
        assert bandwidth(F, dip(F), k, level) == pytest.approx(edges(level), abs=2e4)
    assert bandwidth(F, dip(F), k, -30.0) is None
    f = band_grid(antenna_dict())  # 2.875 MHz steps: a dip between two points is found within 0.01 % of f0
    for at in (2.44e9, 2.4401e9, 2.4428e9):
        assert resonance(f, dip(f, at))[1] == pytest.approx(at, abs=1e-4 * 2.44175e9)
    low = dip(F, 1.95e9, 0.3e9)  # its -10 dB region runs off the band's low end
    assert bandwidth(F, low, resonance(F, low)[0], -10.0)[0] is None
    assert shown_zin(complex(48.24, -3.06)) == "48.2 - j3.1" and zin(np.array([0.0]))[0] == 50.0


def test_the_s11_lines():  # design 5.6
    d = antenna_dict()
    f = band_grid(d)
    assert (f[0], f[-1]) == (1.84e9, 2.99e9) and {2.4e9, 2.44175e9, 2.4835e9} <= set(f)
    lines = s11_lines(d, f, dip(f))
    assert [c for c, _ in lines] == ["I_ANTENNA_RELATIVE", "I_ANTENNA_RESONANCE", "I_ANTENNA_POINT", "I_ANTENNA_POINT",
                                     "I_ANTENNA_POINT", "I_ANTENNA_BANDWIDTH", "I_ANTENNA_BANDWIDTH"]
    assert (lines[1][1]["f_mhz"], lines[1][1]["port"]) == ("2440.0", "U1.1")  # refined; Zin at the radio pin
    assert [p["marker"] for c, p in lines if c == "I_ANTENNA_POINT"] == ["f_lo", "f0", "f_hi"]
    assert lines[-2][1]["level_db"] == "-10" and lines[-1][1]["level_db"] == "-6"
    edge = s11_lines(d, f, dip(f, 1.0e9, 0.3e9))
    assert ("W_RESONANCE_EDGE", {"f_mhz": "1840.0"}) in edge and ("I_ANTENNA_NO_BANDWIDTH", {"level_db": "-10"}) in edge
    low = s11_lines(d, f, dip(f, 1.95e9, 0.3e9))
    assert [(p["level_db"], p["f_lo_mhz"]) for c, p in low if c == "W_BANDWIDTH_EDGE"][0] == ("-10", "1840.0")


def test_the_far_field_files_and_lines():  # design 5.5, 5.6
    far = far_of()
    lines = far_field_lines(far)
    assert [c for c, _ in lines] == ["I_ANTENNA_FAR_FIELD"] * 2  # the fixture's 2 frequencies, ascending
    assert lines[0][1]["f_mhz"] == "2400.0" and float(lines[0][1]["d_dbi"]) == pytest.approx(2.157, abs=0.05)
    bad = {**far, "eff": {**far["eff"], "eta_rad": far["eff"]["eta_rad"] * 1.05}}  # plan 1's W_ETA_RAD, printed here
    assert [c for c, _ in far_field_lines(bad)] == ["I_ANTENNA_FAR_FIELD"] * 2 + ["W_ETA_RAD"]
    rows = list(csv.reader(io.StringIO(farfield_csv(far).decode())))
    assert rows[0] == ["f_hz", "theta_deg", "phi_deg", "e_theta_re", "e_theta_im", "e_phi_re", "e_phi_im", "d_dbi",
                       "gain_dbi", "realized_gain_dbi"] and len(rows) == 1 + 2 * 37 * 72
    rows = list(csv.reader(io.StringIO(antenna_csv(far, np.array([0.1, 0.2])).decode())))
    assert rows[0] == ["f_hz", "s11_db", "s11_deg", "zin_re", "zin_im", "mismatch", "p_acc_w", "p_inc_w", "p_rad_w",
                       "eta_rad", "eta_tot", "d_max_dbi", "gain_dbi", "realized_gain_dbi"] and len(rows) == 3


def test_the_summary_png_holds_the_label_and_the_limits():  # design 5.6; anti-goal 1: no number without them
    d = antenna_dict()
    f = band_grid(d)
    for far in (far_of(), None):  # a part-port run has no far field: S11 and the Smith chart only
        fig = Figure()
        draw_antenna(fig, f, dip(f).astype(complex), d, far, "proj")
        assert fig.get_suptitle() == render("I_PLOT_ANTENNA_TITLE", name="proj") + "\n" + render("I_ANTENNA_RELATIVE")
        assert all(render(code) in fig.texts[-1].get_text() for code in ANTENNA_LIMITS)
        assert antenna_png(f, dip(f).astype(complex), d, far, "proj").startswith(b"\x89PNG")
```

- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_post_antenna.py tests/test_post_farfield.py tests/test_post_outputs.py -q`. Expected: FAIL with `No module named 'kicad_rf_studio.core.post.antenna'`.
- [ ] **Step 3: The reader, the grid and the writer.**
  - `read_far_field` reads `/nf2ff/E_theta/FD/f{n}` and `E_phi` (complex, (θ, φ)) into `e_theta` and `e_phi`, which are added last to `FarField`, only after its legacy-layout and shape checks. Its docstring loses "It reads no E dataset".
  - **`band_grid`:** `np.unique(np.r_[np.linspace(f1, f2, N_GRID + 1), f_lo, f0, f_hi])` from `pulse_band`, with the docstring "an antenna's grid (Stage 3 design 5.6): the pulse's band, with f_lo, f0 and f_hi on it".
  - **`layout`:** its default `f` is `band_grid(project)` for an antenna. Its markers read `project.get("harmonics", 1)`.
  - **`write`'s order:** `name.endswith("summary.csv")` first, then `name.endswith("summary.png")`, then the rest, so an antenna's held summary also refuses before anything changes. v1's order is unchanged.
- [ ] **Step 4: `core/post/antenna.py`.**
  - **Docstring:** "An antenna's results (Stage 3 design 5.5, 5.6): S11's resonance, bandwidth and mismatch at the band's markers, the far field's efficiencies and gains, and the files of results/, each labelled relative with its stated limits; no loss budget, radiation being the "loss". matplotlib is imported inside antenna_png only (C-5)."
  - **Constants:**
    - `ANTENNA_OUTPUTS = re.compile(r"(layout|chain)\.s\d+p|farfield\.csv|antenna_summary\.(png|csv)")`;
    - `ANTENNA_LIMITS = ("I_LIMIT_FREE_SPACE", "I_LIMIT_PEC_ETA", "I_LIMIT_SURROUNDINGS", "I_LIMIT_BODIES", "I_LIMIT_PARTS_OFF_CHAIN")`;
    - `LEVELS_DB = (-10.0, -6.0)`.
  - **S11 functions:**
    - `zin = Z0·(1 + s)/(1 − s)`. `shown_zin(z)` is `f"{z.real:.1f} {'+' if z.imag >= 0 else '-'} j{abs(z.imag):.1f}"`.
    - `resonance` is the argmin k of |S11| and the frequency there refined by a parabola through |S11| in dB at k − 1, k and k + 1 (`np.polyfit` on f − f[k]); at the grid's first or last point, f[k] itself. The 401-point grid's step is 0.12 % of f0, against plan 3's 0.3 % significance threshold; the parabola found the synthetic dip within 3e-5 % of f0.
    - `bandwidth` gives the crossings of `level_db` on either side of index `k`, interpolated linearly in dB between grid points. A side with no crossing is None: |S11| stays below the level to the grid's end. It is None when |S11[k]| is above the level.
  - **`s11_lines`,** in the order the test fixes; `port` is `project["chain"]["start"]`, where Zin is seen:
    1. I_ANTENNA_RELATIVE;
    2. I_ANTENNA_RESONANCE `{f_mhz (:.1f of the refined frequency), s11_db (:.1f), zin, port}`, |S11| and Zin at k; then W_RESONANCE_EDGE `{f_mhz}` when k is the grid's first or last point;
    3. I_ANTENNA_POINT for f_lo, f0 and f_hi `{marker, f_mhz, s11_db, zin, port, mismatch_pct (:.1f of 100·(1 − |S11|²))}`;
    4. per level, I_ANTENNA_BANDWIDTH `{level_db (:g), f_lo_mhz, f_hi_mhz, bw_mhz}` (:.1f); W_BANDWIDTH_EDGE `{level_db, f_lo_mhz, f_hi_mhz}`, the grid's end in place of a missing crossing; or I_ANTENNA_NO_BANDWIDTH `{level_db}`.
  - **`far_field_of`:**
    - It reads the three grids and the job's waves (port 1's `u[0]`, `i[0]` over the whole record), and returns sphere, elevation, azimuth, `p_acc`, `p_inc` and `eff` (`efficiencies` at `sphere.f`).
    - A missing file raises E_RESULTS_WAVES `{path}`.
  - **`far_field_lines`:**
    - One I_ANTENNA_FAR_FIELD per recorded frequency, ascending: `{f_mhz (:.1f), eta_rad_pct, eta_tot_pct (:.1f), d_dbi, gain_dbi, realized_dbi (:.2f)}`.
    - Then `eta_lines` (W_ETA_RAD, plan 1's flag).
  - **The CSVs,** as the test fixes their columns, with Python's repr numbers and "\n" line ends:
    - `farfield.csv`: one row per frequency, θ and φ of the sphere; dBi columns are 10·log10 of D, D·η_rad and D·η_tot.
    - `antenna_summary.csv`: one row per far-field frequency, with S11 at those frequencies given.
  - **`draw_antenna` and `antenna_png`:**
    - `draw_antenna` draws on a matplotlib Figure, as `draw_summary` does, so plan 5's GUI reuses it. Panels:
      - |S11| in dB against GHz, with [f_lo, f_hi] shaded (`axvspan`) and −10/−6 dB lines;
      - S11 on a Smith chart (`rf.plotting.smith(ax=…, draw_labels=True)`, as `draw_summary` calls it), with dots at f_lo, f0 and f_hi;
      - with a far field, η_rad and η_tot in % against GHz, and the three polar cuts of D in dBi at f0: XY (azimuth, θ 90°), XZ (elevation, φ 0°) and YZ (elevation, φ 90°), titled with those literal plane names.
    - The suptitle is `render("I_PLOT_ANTENNA_TITLE", name=…)` + "\n" + `render("I_ANTENNA_RELATIVE")`, and the last `fig.text`, at the foot, holds the rendered ANTENNA_LIMITS, one a line.
    - `antenna_png` is `draw_antenna` on an Agg Figure at 100 dpi, as `summary_png` builds it.
- [ ] **Step 5: The messages,** each through the catalog tool:

| Code | English | pt-BR |
|---|---|---|
| I_ANTENNA_RELATIVE | Relative: these antenna results compare variants of one board under identical settings; they do not predict measured performance. | Relativo: estes resultados de antena comparam variantes de uma placa com configurações idênticas; eles não preveem o desempenho medido. |
| I_ANTENNA_RESONANCE | Resonance (lowest \|S11\|): {f_mhz} MHz, \|S11\| {s11_db} dB, Zin at {port} {zin} Ω. | Ressonância (menor \|S11\|): {f_mhz} MHz, \|S11\| {s11_db} dB, Zin em {port} {zin} Ω. |
| W_RESONANCE_EDGE | \|S11\| is lowest at {f_mhz} MHz, the edge of the simulated band, so the antenna resonates outside it, far off tune for this band. | \|S11\| é menor em {f_mhz} MHz, a borda da banda simulada, então a antena ressoa fora dela, muito fora de sintonia para esta banda. |
| I_ANTENNA_POINT | {marker} = {f_mhz} MHz: \|S11\| {s11_db} dB, Zin at {port} {zin} Ω, mismatch efficiency {mismatch_pct} %. | {marker} = {f_mhz} MHz: \|S11\| {s11_db} dB, Zin em {port} {zin} Ω, eficiência de descasamento {mismatch_pct} %. |
| I_ANTENNA_BANDWIDTH | {level_db} dB bandwidth: {f_lo_mhz} to {f_hi_mhz} MHz ({bw_mhz} MHz). | Largura de banda a {level_db} dB: de {f_lo_mhz} a {f_hi_mhz} MHz ({bw_mhz} MHz). |
| W_BANDWIDTH_EDGE | {level_db} dB bandwidth: at least {f_lo_mhz} to {f_hi_mhz} MHz: \|S11\| stays below {level_db} dB to the edge of the simulated band, so its true edge lies outside it. | Largura de banda a {level_db} dB: pelo menos de {f_lo_mhz} a {f_hi_mhz} MHz: \|S11\| fica abaixo de {level_db} dB até a borda da banda simulada, então a borda verdadeira fica fora dela. |
| I_ANTENNA_NO_BANDWIDTH | {level_db} dB bandwidth: none, as \|S11\| stays above {level_db} dB. | Largura de banda a {level_db} dB: nenhuma, pois \|S11\| fica acima de {level_db} dB. |
| I_ANTENNA_FAR_FIELD | {f_mhz} MHz: radiation efficiency {eta_rad_pct} %, total efficiency {eta_tot_pct} %, directivity {d_dbi} dBi, gain {gain_dbi} dBi, realized gain {realized_dbi} dBi. | {f_mhz} MHz: eficiência de radiação {eta_rad_pct} %, eficiência total {eta_tot_pct} %, diretividade {d_dbi} dBi, ganho {gain_dbi} dBi, ganho realizado {realized_dbi} dBi. |
| I_LIMIT_FREE_SPACE | Limit: the board alone in free space. | Limite: a placa sozinha no espaço livre. |
| I_LIMIT_PEC_ETA | Limit: copper is a perfect conductor, so the radiation efficiency reads high. | Limite: o cobre é um condutor perfeito, então a eficiência de radiação fica alta demais. |
| I_LIMIT_SURROUNDINGS | Limit: no enclosure, hand, battery or cable. | Limite: sem gabinete, mão, bateria ou cabo. |
| I_LIMIT_BODIES | Limit: the parts' bodies are absent; only their pads are in the board file. | Limite: os corpos dos componentes não estão no modelo; só as ilhas deles estão no arquivo da placa. |
| I_LIMIT_PARTS_OFF_CHAIN | Limit: the parts off the chain are approximated: capacitors close to a short as copper, the rest open or in the grid, and past the measured region only as fine as its coarse mesh. | Limite: os componentes fora da cadeia são aproximados: capacitores perto de um curto como cobre, os demais em aberto ou na grade, e fora da região medida só tão finos quanto a malha grossa dela. |
| I_PLOT_ANTENNA_TITLE | {name}: antenna, relative results | {name}: antena, resultados relativos |

- [ ] **Step 6: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_post_waves.py tests/test_run.py tests/test_sexpr.py tests/test_golden_v1.py tests/test_p3a.py -q`. Expected: PASS.
- [ ] **Step 7: Full suite, commit, graph.**

```bash
git add src tests po
git commit -m "feat(post): an antenna's resonance, bandwidth, efficiencies, gains and cuts, with its files, label and limits (Stage 3 design 5.5, 5.6)"
graphify update .
```

---

### Task 11 [code]: An antenna run writes its results

**Files:**
- Modify: `pipeline.py`:
  - `_run`;
  - `chain_results` (its `else` branch);
  - `write_outputs`;
  - `antenna_outputs`, after `write_outputs`.
- Create: `tests/test_run_antenna.py`.
- Test: `tests/test_run.py`.

**Interfaces:**
- Consumes: Task 8's `far_field(job, step_deg)`; Task 10's `core.post.antenna` and `layout`.
- Produces:
  - `results["far_field"]`, an antenna's only: `{grid: "job-1-P1/nf2ff-<token>-<grid>.h5"}` relative to the run folder, or None.
  - `antenna_outputs(path, project, command, *, errors_as_lines=False) -> list[tuple[str, dict]]`, which `write_outputs` returns for an antenna, `run` and `retune` alike.

- [ ] **Step 1: Write the failing tests,** `tests/test_run_antenna.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path

import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.antenna import ANTENNA_LIMITS
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_antenna import FIX, antenna_project

FOUR = ["antenna_summary.csv", "antenna_summary.png", "farfield.csv", "layout.s1p"]


def events(run_dir):
    return [json.loads(line)["code"] for line in (Path(run_dir) / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def files(pj):
    return sorted(f.name for f in (pj.parent / "results").iterdir())


def test_an_antenna_run_records_its_far_field_and_writes_its_files(tmp_path, calibrated):  # design 5.5, 5.6
    pj = antenna_project(tmp_path / "p")
    data = load_project(pj)
    save_project(pj, {**data, "far_field": {**data["far_field"], "step_deg": 10}})
    assert pipeline.run(pj) == 0
    results = load_project(pj)["results"]
    assert list(results["far_field"]) == ["sphere", "elevation", "azimuth"]
    assert all((Path(results["run_dir"]) / v).is_file() for v in results["far_field"].values())
    job, = Path(results["run_dir"]).glob("job-0-nf2ff-*/job.json")
    assert json.loads(job.read_text(encoding="utf-8"))["step_deg"] == 10  # the project's step reaches the transform
    assert files(pj) == FOUR
    codes = events(results["run_dir"])
    assert "W_NOT_TWO_PORT" not in codes and "I_LOSS_BUDGET" not in codes  # no loss budget (design 5.6)
    assert codes.index("I_ANTENNA_RELATIVE") < codes.index("I_ANTENNA_FAR_FIELD") and codes[-5:] == list(ANTENNA_LIMITS)
    assert pipeline.retune(pj, []) == 0 and files(pj) == FOUR  # retune rewrites them from the stored transform


def test_a_failed_transform_keeps_s_and_says_so(tmp_path, calibrated, monkeypatch):  # design 5.5
    def fail(*_, **__):
        raise KrsError("E_WORKER_FAILED", job="T_JOB_FAR_FIELD", exit_code=1, log="log.txt")

    monkeypatch.setattr(pipeline, "far_field", fail)
    pj = antenna_project(tmp_path / "p")
    assert pipeline.run(pj) == 2
    results = load_project(pj)["results"]
    assert results["far_field"] is None and "E_WORKER_FAILED" in events(results["run_dir"])
    assert files(pj) == ["antenna_summary.png", "layout.s1p"]


def test_a_stopped_transform_keeps_the_runs_s(tmp_path, calibrated, monkeypatch):  # Stage 1 7.8: a kept run is saved
    def stop(*_, **__):
        raise KeyboardInterrupt  # STOP or Ctrl+C during the transform

    monkeypatch.setattr(pipeline, "far_field", stop)
    pj = antenna_project(tmp_path / "p")
    with pytest.raises(KeyboardInterrupt):
        pipeline.run(pj)
    results = load_project(pj)["results"]
    assert [j["verdict"] for j in results["jobs"]] == ["converged"] and results["far_field"] is None
    assert files(pj) == ["antenna_summary.png", "layout.s1p"]


def test_a_part_port_antenna_run_has_s11_and_no_far_field(tmp_path, calibrated):  # design 5.5; plan 3's branch
    pj = antenna_project(tmp_path / "pi", FIX / "ifa2g4_pi.kicad_pcb")
    assert pipeline.run(pj) == 0
    assert load_project(pj)["results"]["far_field"] is None
    assert files(pj) == ["antenna_summary.png", "chain.s1p", "layout.s4p"]
```

  In `tests/test_run.py`, `test_run_writes_the_outputs_of_a_known_network` gains `assert "far_field" not in load_project(pj)["results"]` (a v1 run's results gain no key).
- [ ] **Step 2: Run them.** `.venv/Scripts/python -m pytest tests/test_run_antenna.py tests/test_run.py -q`. Expected: FAIL with KeyError `'far_field'`: `run` records v1's results and writes v1's files.
- [ ] **Step 3: `_run`.**
  - An antenna's results add `"far_field": None`; v1's results dict is unchanged. They are saved, and I_RESULTS emitted, as soon as every job kept S, as v1 does (Stage 1 §7.8).
  - Then, when `"nf2ff" in model.spec`:
    1. `write_outputs(path, data, command, errors_as_lines=True)` first, its lines not emitted: the S files, so that a stopped transform keeps them.
    2. `paths = far_field(run_dir / Path(done[0]["waves"]).parent, project["far_field"]["step_deg"])`.
    3. `data["results"]["far_field"] = {grid: p.relative_to(run_dir).as_posix() for grid, p in paths.items()}`, saved again.
    4. On a KrsError: `far_field` stays None, the error is emitted as a message event, and the return code is 2. A KeyboardInterrupt propagates (exit 130) with S already kept.
  - Then `write_outputs`' lines, as v1 emits them.
  - The docstring adds "an antenna run saves its S as v1 does, then, with no part port, transforms its far field after its job and saves again; a transform that fails is an E_ line, and one stopped leaves S kept (Stage 3 design 5.5)".
- [ ] **Step 4: The outputs.**
  - **`chain_results`:** W_NOT_TWO_PORT is not added for an antenna.
  - **`write_outputs`:** for an antenna it returns `antenna_outputs(...)`. `retune` calls it too, so a retune rewrites an antenna's files from the stored `results.far_field`.
  - **`antenna_outputs`:**
    - Its files:
      - v1's Touchstone files (`layout.s{N}p`, plus `chain.s1p` when part ports are closed);
      - with `results["far_field"]`, `farfield.csv` and `antenna_summary.csv`, from `far_field_of` with the job's waves and S11 at `sphere.f` (the S11 from `layout(project, results, f=sphere.f)`, terminated as `res.chain` is);
      - `antenna_summary.png` whenever `res.chain` exists.
    - Its lines: `res.lines` (I_BASIS up to the indicators), `s11_lines` on `res.chain[:, 0, 0]`, then `far_field_lines`, the what-if label as v1's, I_OUTPUTS, then ANTENNA_LIMITS.
    - It writes through `write(folder, files, ANTENNA_OUTPUTS, command)`. The `errors_as_lines` handling is v1's, and E_RESULTS_WAVES from `far_field_of` is one more such line.
- [ ] **Step 5: Run them again.** Step 2's command, then `.venv/Scripts/python -m pytest tests/test_retune.py tests/test_verify.py tests/test_post_outputs.py tests/test_golden_v1.py tests/test_gui_control.py -q`. Expected: PASS.
- [ ] **Step 6: Full suite, commit, graph.**

```bash
git add src tests
git commit -m "feat(run): an antenna run saves its S, then with no part port transforms its far field and writes its results (Stage 3 design 5.5, 5.6)"
graphify update .
```

---

### Task 12 [run]: The first antenna run, its record and the amendments

This task commits the record, the amendments and any fix a failure needs. Everything else it makes stays under `$env:TEMP`. Run each PowerShell block as one call.

- [ ] **Step 1: The suite at the branch tip.** Run the full suite in the background and wait for it. Then run, in one call: `$env:KRS_TEST_LANGUAGE = "pt_BR"; .venv\Scripts\python.exe -m pytest tests/test_gui.py -q`. Expected: all pass. Record the counts.
- [ ] **Step 2: New, cost and run the 2.4 GHz fixture,** in the background, waited on:

```powershell
$out = Join-Path $env:TEMP 'krs-plan2-run'; New-Item -ItemType Directory -Force $out | Out-Null
$env:LOCALAPPDATA = "$out\data"; $env:XDG_DATA_HOME = "$out\data"  # an isolated data folder: its own calibration
$env:CSXCAD_INSTALL_PATH = "<openEMS folder>"  # typed here, never written into a file
Copy-Item tests\fixtures\ifa2g4.kicad_pcb $out
$krs = ".venv\Scripts\kicad-rf-studio.exe"
& $krs new "$out\ifa2g4.kicad_pcb" --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o "$out\proj" *> "$out\new.log"; "new $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs cost "$out\proj" *> "$out\cost.log"; "cost $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs run "$out\proj" *> "$out\run.log"; "run $LASTEXITCODE" | Add-Content "$out\codes.txt"
& $krs cost "$out\proj" *> "$out\cost2.log"; "cost2 $LASTEXITCODE" | Add-Content "$out\codes.txt"
```

  - **Expected codes:** `new 0`, `cost 0`, `run 0`, `cost2 0`.
  - **Expected time:** the run takes 20–90 minutes.
  - **The architect's probe** of the draft's model on this PC: 135 × 138 × 71 = 1.32 M nodes, 44 % PML, dt 1.15e-13 s and 76.4 MC/s on 4 threads. The worst case to 30 ns is then about 75 minutes. The corrected cost model predicts about 67.5 MC/s, so its time is 1.13 times the measured. The revised mesh is 135 × 137 × 71 = 1.31 M nodes, with the same PML share.
- [ ] **Step 3: Read it, against these pre-registered checks:**
  - **Hard:** a failure gets superpowers:systematic-debugging, and a bug is fixed test-first in its module, then Step 2 again.
    - the run's one job is kept (converged, flat or t_max);
    - no E_ line;
    - no E_METAL_IN_PML and no E_PORT_SHORT (the join cut);
    - no W_AIR_BOX and no W_LIDS_LEFT_OUT;
    - `results.far_field` holds three files;
    - `results/` holds the four files of Task 11's first test;
    - η_rad ≤ 1.02 at every recorded frequency (no W_ETA_RAD).
  - **Cost:** `cost2`'s I_COST_PREDICTED against the run's `results.wall_s` (the job phase), as a ratio predicted/measured.
    - Within [0.67, 1.5] it passes.
    - Outside it, the record says so. `PML_WEIGHT` and `SMALL_SPEED` stay as they are, and plan 4's P3-C refits them.
  - **Physics, soft, report-only** (P3-A's dipoles read D 1.79 and 2.16 dBi and η_rad 1.000):
    - η_rad between 0.5 and 1.0 (FR-4 at tanδ 0.02 and PEC copper);
    - D at f0 between 1.5 and 4.5 dBi;
    - the resonance and its distance from the band, and the −10 dB bandwidth.

    The fixture's ground plane is the generator's own, not TI's. A resonance off the band is a finding about the fixture, for plan 4, not a failure.
  - **Also recorded:** the transform's wall time (its job folder's log). A time above 60 s is a ruling on plan 1's ponytail that the transform rebuilds the whole CSX.
- [ ] **Step 4: Two more setups, cost only,** in the same isolated folder:
  - **The pi variant:** `new` on a copy of `ifa2g4_pi.kicad_pcb` with `--band 2400MHz:2483.5MHz`, then `cost`. Expected: `cost 0`, and none of E_PORT_SHORT, E_PORT_OPEN or E_PORT_BOX on its four ports: its shunt ports C2 and C3 stand on RF and GND, which the antenna's own join ties, so they too rely on the cut. Record its cells, split and worst case (4 runs, SMALL_SPEED unmeasured at a pool above 1).
  - **The 915 MHz meander:** `new` on a copy of `meander915.kicad_pcb` with `--band 902MHz:928MHz`, then `cost`. Record its cells, split and worst case. The prototype gave 216 × 153 × 79 = 2.61 M nodes, 38 % PML, T_max 79 ns and a corrected worst case near 7 h, which is likely high for a 2.6 M-node model. This is plan 4's budget.
- [ ] **Step 5: The record,** `docs/validation/<the run's date>-antenna-first-run.md`. It has these sections:
  1. Purpose: plan 2's first real antenna run, not a gate.
  2. Inputs: the commands with `<RUN>` for the folder, the versions, and the fresh calibration (aggregate, pool, threads, levels, the one-job speed at its threads).
  3. The cost: the split, predicted against measured, and the ratio.
  4. The runtime against the design's hope: the measured time against design §1's 9–18 min per job at 2.4 GHz; the PML's share of the nodes and of the corrected work; dt and the 35 µm copper cell that sets it; and that r4's 15–35 machine hours for P3-B to P3-E need re-estimating from these numbers and Step 4's.
  5. The results' lines, as printed, under the relative label.
  6. The checks of Step 3.
  7. The pi variant's setup and the 915 MHz cost.
  8. The stated limits.
  9. Next: plan 3 and plan 4.

  It holds no path and no host name.
- [ ] **Step 6: The amendments,** in `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`:
  - **A-26, §1.1's "Simulation domain" row:** the decision becomes "Always a selected region, never a whole board, for the matching chain. An antenna project (Stage 3) simulates the whole board, every copper layer, the substrate, the mask and the lid, in an air box (A-26, Stage 3 plan 2: controller recommendation, owner unavailable.)"
  - **A-27, §5.1:** a bullet after A-24's:
    > "- **The antenna's region** (Stage 3): the measured region takes the ROI's place: the bounding box of the antenna footprint's copper (its netless copper takes the feed pad's net), of the chain from the start pad to the antenna's feed pad and of the port, grown by `region.expand_h` substrate heights, 6 by default, the protected set's reach. The cell d comes from the feed network's tracks and sections, as in v1; the antenna's copper gets the rule's edge lines. A short or an open inside the measured region is a gate and elsewhere on the board a warning, but the antenna's own feed-to-ground join through the pads `antenna.join`, which `new` records and which the port-short check also accepts by cutting the PEC edges at the mesh nodes within one cell of those pads. The walls are the board's box, its outline and copper, grown by one coarse cell; the air gap `air_gap_mm`, λ/4 at f_lo by default, runs from them to the PML's inner edge, graded at 1.3 up to λ(f2)/20 in air; nothing reaches a crop. The shield over most of the board gets its lid at the project's lid height, and a warning names any other. The rest of the board's parts are never ports: a capacitor whose capacitive reactance, less its package's inductive one, is at most Z0/5 at the pulse's centre is copper; a resistor or capacitor that v1 puts in the grid is in the grid inside the measured region and open outside it; any other part is open. (A-27, Stage 3 plan 2: controller recommendation, owner unavailable.)"
  - **A-28, §6.3:** after the presets table:
    > "**Antennas** (Stage 3): T_max defaults to 2·t0 + 60/f0, rounded up to a whole ns, f0 being the band's centre, and the flat window is max(5 ns, 20/f0); every other constant is v1's. (A-28, Stage 3 plan 2: controller recommendation, owner unavailable.)"
  - **A-29, §6.4:** a bullet after the calibration's:
    > "- **Antennas** (Stage 3): `cost` splits the cells into board (inside the dielectric's box), air and PML (the nodes openEMS's UPML updates, 9 lines a face) and counts N − N_PML + 6.38·N_PML cells at 0.384 times the calibration's own one-job speed at its threads, gate P3-A's two corrections (`docs/validation/2026-10-29-p3-a.md`). These two ratios are the one exception to "no numeric constants for any particular PC": P3-A measured them on the development PC, and they stay provisional until gate P3-C refits them. An antenna run does not refresh the calibration. On <date> the 2.4 GHz fixture's run took <measured> against <predicted> predicted and the Stage 3 design's hope of 9–18 min; the PML held <share> of the nodes, and the 35 µm copper cell set dt (`docs/validation/<date>-antenna-first-run.md`). (A-29, Stage 3 plan 2: controller recommendation, owner unavailable.)"
  - **A-30, §10:**
    - The bullet "antennas and NF2FF (Stage 3);" is deleted.
    - The list ends with:
      > "- the Stage 3 design's non-goals (its §3): chip and module antennas; the enclosure, a hand or body, the battery, cables, screws and the parts' bodies; automatic placement; an instant far-field retune; two bands, two antennas or external wire antennas in one run; a 3D pattern view; absolute performance claims (A-30, Stage 3 plan 2: controller recommendation, owner unavailable.)"
  - **A-31, §5.5's edge lint:** after its known-bad-meshes sentence:
    > "In an antenna project (Stage 3), an edge that another copper layer's opposite edge meets within 20 µm, the metal on its other side, as on a two-layer helical antenna, is exempt from the third test, which no line can pass for both edges. The exemption is computed only for an antenna, so every v1 model is built as before. (A-31, Stage 3 plan 2: controller recommendation, owner unavailable.)"
  - **A-32, §3.2, §3.3, §7.4 and §7.5:**
    - §3.2, after the command table: "**Antennas** (Stage 3): `new BOARD --start REF.PAD --antenna REF --band F_LO:F_HI` writes an antenna project, with `--antenna` in place of `--end` and the band in place of `--f0` and `--harmonics`; `cost`, `run`, `retune` and `preview` work on it as on a v1 project. (A-32, Stage 3 plan 2: controller recommendation, owner unavailable.)"
    - §3.3, a last bullet of project.json's list: "an antenna project (Stage 3) is schema 2 with `"kind": "antenna"`, without the harmonics and the band factor, and with the band, the antenna and its join pads, the air gap, the boundary and the far-field frequencies and angle step; v1 projects stay schema 1 (A-32)."
    - §7.4, a last bullet: "**Antennas** (Stage 3) have no loss budget: radiation is their "loss" (A-32)."
    - §7.5, after the list: "An antenna's results (Stage 3) state their own limits instead, after the label that they are relative: the board alone in free space; copper as a perfect conductor, so the radiation efficiency reads high; no enclosure, hand, battery or cable; the parts' bodies absent; the parts off the chain approximated (A-32)."
  - **The Status line** gains, at its end: " On <date>, Stage 3's plan 2 amended §1.1, §3.2, §3.3, §5.1, §5.5, §6.3, §6.4, §7.4, §7.5 and §10 (A-26 to A-32) the same way."
- [ ] **Step 7: Commit.**

```bash
git add docs/validation/<date>-antenna-first-run.md docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md
git commit -m "docs(validation): the first antenna run on the 2.4 GHz fixture; Stage 1 spec A-26 to A-32 (Stage 3 design 5.13; controller recommendation, owner unavailable)"
graphify update .
```

- [ ] **Step 8: Close.**
  1. Run the whole-branch review.
  2. Run Step 1 again after any later commit.
  3. Fast-forward `main` to the branch locally, then delete the branch.
  4. Delete `$env:TEMP\krs-plan2-run`.

  Nothing is pushed. There are no screenshots: plan 2 has no GUI.

---

## Not in this plan

- **Plan 3, matching and comparison:**
  - every chain part a port (a 0R starting at 0 Ω, a DNP part open);
  - the one-port retune with 0 Ω and open, and verify's one-port path with its far field (verify still refuses an antenna project, E_VERIFY_PORTS);
  - a line saying why a part-port run has no far field;
  - `compare` with the settings fingerprint and the thresholds, on Task 10's refined resonance.

  Plan 2 runs the pi variant with v1's roles, gives S11 with no far field, and pins only that.
- **Plan 4, the gates P3-B to P3-E:**
  - their fixture variants: the whole board shifted by d, the antenna moved by ±d, and the ground pour in the clearance, the pi board's too for the acceptance compare. Each is one BOARDS entry of Task 1's generator, once P3-D's d and its moves are decided;
  - the MUR-at-λ/2 fallback (P3-A's MUR twin rose 16 dB at 0.53 λ; W_AIR_BOX warns until then), the sheet-copper check, n 2/3/4 (which also measures d taken from the feed network alone), the gap, the presets and the 915 MHz runs;
  - the fit2d sensitivity this revision found: AE1 moved by 0.1, −0.1 or 0.37 mm reads E_FIT2D 3.9–4.8 % on the 0.6 mm stub at n 2 (n 3 passes), while the ±d moves pass;
  - refitting PML_WEIGHT and SMALL_SPEED, SMALL_SPEED at a pool above 1 among them;
  - all threads for a lone job, which needs a calibration level of its own.

  P3-F stays the owner's.
- **Plan 5, the GUI:**
  - New's antenna kind, its band presets and candidate list;
  - the Results, Advanced and Compare pages, with `draw_antenna`;
  - the button's pre-fill, including how the GUI reads schema 2, which removes Task 3's guard in `control.open_project`;
  - the README tutorial, the release check and the exit record.
- **Deferred, with their ceilings (ponytail comments):**
  - several shield lids: the model holds one, and W_LIDS_LEFT_OUT names the others;
  - the far-field dumps' RAM in the cost;
  - the transform rebuilding the whole CSX, measured in Task 12;
  - arcs of antenna copper not flagged as staircased;
  - a radiator drawn as tracks on the feed net (fit2d would read it as feed line) or as board graphics or zones outside the footprint, which is not the antenna group;
  - the join taken from the footprint's GND pads, not its net-tie group, and every netless piece of the footprint adopted, a floating parasitic element included;
  - a custom-library module drawing more copper than its pads read as printed, and a connector or converter with a keep-out listed as a module by `antenna_kinds`;
  - a copper bridge past the measured region only as fine as the coarse mesh, which the limits state.

## Controller rulings (2026-10-29; binding)

These are the architect's rulings, revised after four reviews. Each is a controller recommendation made while the owner is unavailable.

- Ruling: the tasks run in this order:
  1. the fixtures;
  2. the importer;
  3. schema 2, the band, the region and the roles;
  4. `new`;
  5. the lint's two-layer exemption;
  6. the antenna's geometry;
  7. the model spec;
  8. the worker's join cut and angle step;
  9. cost;
  10. the outputs' pieces;
  11. the wiring;
  12. the run.

  The shared mesh code (5) and the worker (8) each get a task and a gate of their own, so neither hides among antenna-only code. Each task's tests use the fixtures and `new` of the tasks before it — design §5.12 item 2 and the quality review — cost if wrong: a reorder.
- Ruling: the fixtures' geometry.
  - **The feed:** a 1.35 mm microstrip (50 Ω on the 0.71 mm core) with the top ground kept 1 mm off by a `.kicad_dru` rule, and a 0.6 mm stub into pin 1. d is then 0.3 mm at n 2. lpf915's 0.15 mm GCPW gaps would make it 0.075 mm, about 10 times the cells.
  - **The radio:** a SOIC-8 "RFIC" turned 270°. Its 0.67 mm gap to the GND pin is meshed by d 0.3, while a QFN's 0.25 mm gaps need d ≤ 0.1.
  - **The pi line:** 0.6 mm wide. The prototype's 3 mm 1.35 mm piece read fit2d 4.47 %.
  - **The grounds:** 40 × 24.25 mm (2.4 GHz) and 40 × 40 mm (868/915 MHz), the generator's own, stated and not TI's.
  - **The 915 board** has no decoupling C.
  - **Only the named boards are generated,** because the golden pins hash the existing boards' bytes; any other change stops the task.

  The prototype built all three in scratch with KiCad 9's Python: pads equal to pcbnew's (58 of 58), the three models with no blocked gate, fit2d at most 1.81 % — design §5.11 and §6 (the builder's) — cost if wrong: the fixtures are regenerated, and the tests' coordinates move with them.
- Ruling: the P3-D and P3-E variants are plan 4's. They need P3-D's d and its moves, and the acceptance's ground-pour pi board — design §5.11 ("if they cost nothing more now": they do) — cost if wrong: three BOARDS entries in plan 4.
- Ruling: the importer records the drawing footprint on each copper graphic (`CopperArea.ref`) and a footprint keep-out (`Footprint.keepout`). Both have defaults, so no constructor changes — r2 Q1 — cost if wrong: none.
- Ruling: the antenna kinds, the first that holds:
  1. "module": an `RF_Module:` library id;
  2. "printed": copper graphics larger in area than the footprint's copper pads, a radiator;
  3. "chip": an AE reference or an `RF_Antenna:` library id with pads only, a net-tie stub or keep-outs;
  4. "module": any other footprint with a keep-out.

  Any other footprint is E_NOT_AN_ANTENNA, and the refusals that cannot name a kind list the printed antennas on the board. On KiCad 9's 18 RF_Antenna footprints the draft's order (keep-out before copper) made six chip antennas with keep-outs modules and Antenova_SR4G013_GPS, a 0.8 mm² net-tie stub against 15.4 mm² of pads, printed; this order leaves three printed (SWRA117D Left and Right at 21.2 mm² against 0.7 mm², SWRA416 at 137 mm² against 15.2 mm²) and fifteen chip. Ceilings: a custom module drawing more copper than its pads reads printed, and a connector or converter with a keep-out reads module in `antenna_kinds` — design §5.1 — cost if wrong: a refusal's wording.
- Ruling: the feed pad is the antenna's pad on its one signal net, and anything else is E_ANTENNA_FEED. The netless copper graphics and netless pads of that footprint take that net, in `new` and in `load`, and their W_NETLESS_COPPER is dropped. Other netless copper keeps its warning. A floating parasitic element of the footprint would also take the net and read as an open (ceiling) — design §5.3 — cost if wrong: one function.
- Ruling: the feed-to-ground join.
  - It is the antenna's pads on a GND net, recorded in `antenna.join`, not the footprint's net-tie group: on KiCad's printed antennas they are the same pads (SWRA117D ties 1 and 2; SWRA416 has no GND pad). A GND mounting pad would be accepted too (ceiling).
  - **Connectivity** accepts a GND/feed touch that lies within those pads, buffered by 2·SIMPLIFY.
  - **The port-short check** cuts every PEC edge with an end whose nearest mesh node lies within those pads' bounds grown by d, through every copper layer, compared on the lines' own mm values. The draft's 1 nm metre tolerance held only because it covered the top face's 2 pm float32 rounding, and half a float32 step at x, y ≈ 100 mm is 3.7 nm.
  - **Probed:** on openEMS 0.37.0's real setup of ifa2g4, the port's four nodes were one piece without the cut, and the reference and signal ends apart with it, at a growth of 0, 0.3 and 0.6 mm (the architect); the node test on the feasibility review's real setup dump gave no E_PORT_SHORT and no E_PORT_OPEN at the same three growths, and Task 8's readers test holds on the committed dump (this revision).

  — design §5.3 — cost if wrong: a box's growth.
- Ruling: schema 2.
  - **Shape:** v1's chain, ports, parts, mesh, gates and stackup shapes, without harmonics or band_factor. Added: f0_hz (the band's centre), kind, band, antenna, air_gap_mm, boundary ("pml_8" or "mur") and far_field. `make_antenna_project` is `make_project`'s dict with those two keys dropped, schema, t_max_s, region and lid overridden and the antenna keys appended.
  - **Checks:** `check_project` refuses what `new` would: f_hi above 2·f_lo, f0_hz outside the band, and far-field frequencies not led by f0_hz (the worker draws the cuts at the first) or outside the pulse band.
  - **Branching:** code branches on the schema (`antenna()`), never on a `kind` that a hand-edited v1 file could hold.
  - **E_PROJECT_SCHEMA** now names 2 as the newest it reads. The GUI refuses an antenna project with it until plan 5, since `window.show_project` reads harmonics.

  — design §5.1 — cost if wrong: one field renamed in plan 5.
- Ruling: the pulse band is f_lo/1.3 rounded down and 1.2·f_hi rounded up, to 3 significant digits, derived and not stored:

  | Band | Pulse band |
  |---|---|
  | 2400–2483.5 MHz | 1.84–2.99 GHz |
  | 902–928 MHz | 693–1120 MHz |
  | 863–870 MHz | 663–1050 MHz |

  — design §5.4 ("the builder rounds them") — cost if wrong: one function.
- Ruling: T_max and the flat window.
  - T_max is 2·t0 + 60/f0, rounded up to a whole ns and stored in t_max_s: 30 ns (2.4 GHz), 79 ns (915 MHz) and 85 ns (868 MHz).
  - The flat window max(5 ns, 20/f0) travels in the excitation as `"flat_s"`: 8.19 ns at 2.44 GHz, 21.9 ns at 915 MHz. On the synthetic flat trace, the verdict moves from 17.18 to 20.38 ns (rechecked in this revision).

  — design §5.4 — cost if wrong: one constant.
- Ruling: the far-field defaults are f0, then 10 frequencies evenly from f_lo to f_hi (11, all inside [f1, f2]), with a 5° sphere. The step travels in job.json, not the spec, so a new step needs a transform but no run; until a command re-transforms, a changed step applies at the next run, and `retune` rewrites farfield.csv from the stored transform — design §5.5 — cost if wrong: one key moved.
- Ruling: the CLI.
  - `--end`/`--antenna` and `--f0`/`--band` are argparse's mutually exclusive required groups, so a missing one stays a usage error as in v1. A crossed pair is E_NEW_KIND, and so is `--harmonics` with `--antenna`, which harmonics do not apply to.
  - A band wider than an octave is E_BAND_WIDE (Review Focus 5). A centre outside 1 MHz–100 GHz reuses W_F0_RANGE.
  - A start pad on the antenna's own feed stays E_SAME_PADS, "The chain starts and ends at the same pad", which is true of it.
  - `new`'s prelude, port and write become `_load`, `_port` and `_write`, a refactor proved by the golden pins before the antenna path is added.

  — design §5.1 and §3 (one band a run) — cost if wrong: one refusal.
- Ruling: the region.
  - **The measured region** is build_region's ROI at expand_h 6, the protected set's reach.
  - **The walls** are the board's box (outline and copper) ± one coarse cell, and the crop is that box.
  - **The air gap** runs from those walls, so the air is one coarse cell deeper than "from the board" (2.4 mm at 2.4 GHz), on the safe side. A wall on the outermost copper edge would fail the lint on an edge-launch connector. Its default, λ/4 at f_lo, is `region.air_gap`, beside C0, which `new` writes and W_AIR_BOX compares with.
  - **The air** is graded at 1.3 up to λ(f2)/20, then 8 PML lines. This is P3-A's dipole recipe, smooth_mesh_lines on the board's own lines.

  — design §5.2 and §5.3 — cost if wrong: one subtraction.
- Ruling: the cell d comes from the feed network alone: `cell_size` reads tracks and sections, as v1's rule does, so SWRA117D's 0.5 mm arms (d 0.25 by Stage 1 §5.4's words) leave d at 0.3; the antenna's copper gets the rule's edge lines and the fine fill. A-27 says so, and P3-C's n 2/3/4 measures it — design §5.3 ("Stage 1 §5.4's rule meshes it fine"), as the code reads the rule — cost if wrong: d from the antenna's narrowest width or gap, and the line counts re-pinned.
- Ruling: the rest of the board's parts.
  - A "board" part has a pad in the measured region; a "far" part has none.
  - A C whose capacitive reactance, less its package's inductive one, is at most Z0/5 at the pulse's centre (f1 + f2)/2 is copper anywhere: close to a short, or past its self-resonance, where the copper bridge stands for its inductance. In 0402 that is 3.75 pF and up at 2.4 GHz, 13.7 pF at 915 MHz and 14.6 pF at 868 MHz; 100 nF in 1206 stays copper.
  - A grid C or R (v1's rule, SRF above 3·f2) is in the grid on "board" and open on "far": the grid needs fine lines at its pads, which across the whole board would stretch the fine fill over it. Anything else is open, with W_BOARD_PARTS_OPEN in place of W_PART_OPEN's "make one a port".
  - This corrects design §5.3's wording to its own reason ("a decoupling capacitor is close to a short at RF"): read as written, a self-resonance below 3·f2 bridges every 0402 C of 0.63 pF or more at 2.4 GHz, though 1 pF is −58 Ω there and 2.2 pF −22 Ω. The physics review proposed |X(f0)| ≤ Z0/5 with the ESL; that would leave a 100 nF 0603 open at 2.4 GHz (its ESL alone is 10.7 Ω), so the bridge counts the capacitance only, less the ESL.

  — design §5.3 — cost if wrong: one rule, and the owner rules on the wording.
- Ruling: one lid. The shield over most of the board gets it, with lid true for antennas; Geometry holds one Lid, and W_LIDS_LEFT_OUT names any other top-side shield, so the ceiling is never silent. `find_lid` itself is unchanged, so v1's lines keep their bytes. Several lids need the spec's lid to hold several plates — design §5.3 — cost if wrong: a spec key in plan 4 or 5.
- Ruling: one mesh rule, the two-layer exemption.
  - **Coincident opposite edges on two copper layers (within 2·SIMPLIFY) are exempt from "outside closer".** SWRA416's helix puts the top trace's right edge on the bottom trace's left edge. No line arrangement passes both, and it failed at x 115.494 (local 5.494).
  - **For an antenna's geometry alone, and by layer:** `_pairs` reads each layer's edges, `Mesh.exempt` carries them, and `xy_lines`' slot fallback (`_faults`) and `edge_lint` both honour them. The draft's position-only exemption inside `lint_hits` broke v1's `test_an_axis_the_slot_depth_would_break_keeps_its_as_built_lines[lint]` (a same-layer pair 9 µm apart), and applied in the gate alone it left the meander's x axis on its as-built lines and E_FIT2D 3.96 %. This version builds all three fixtures with nothing blocked, the meander at 216 × 153 × 79 with fit2d 1.02 and 1.39 % and 18 pairs exempt; without `antenna`, the meander still reads E_EDGE_LINT, so v1 is unchanged by construction.
  - **The draft's other rule is dropped** ("an edge inside another net's copper is no edge"). No fixture needs it: ifa2g4's first lint is clean under v1's rules at its own placement and at 14 more AE1 positions. On v1's path it would have changed any board whose netless copper or margin short overlaps protected copper.

  — design §5.3 and §5.4 — cost if wrong: an antenna's edge resolution, which P3-C's n 2/3/4 measures.
- Ruling: W_STAIRCASED is raised for antenna copper with an edge ≥ 0.5 mm off both axes. That catches SWRA416's 36 diagonal edges and none of SWRA117D's: its drill-hole chords are 0.03 mm — design §5.3 — cost if wrong: an arc antenna unflagged.
- Ruling: the antenna's lines "in its own frame" need no code.
  - The rule places each edge's lines from that edge and fills between edges from those lines alone, on the 1e-6 mm grid on which KiCad's nanometres sit, so the antenna's own lines move with it. They do not where they meet the board's lines: a d/3 merge, a free vertex line, the grading.
  - The prototype moved AE1 by d: all 14 SWRA117D edges stayed protected edges, and 7 of the 10 isolated ones kept their nearest lines exactly.
  - Task 6 pins the first, and P3-D measures the rest. Some other moves trip the stub's fit2d at n 2: 0.1, −0.1 and 0.37 mm of the 14 tried in this revision (open issue for plan 4).

  — design §5.3 ("Gate P3-D measures the noise that remains") — cost if wrong: an anchored-lattice mesh in plan 4.
- Ruling: fit2d on the feed network needs no code. Sections come from tracks, and footprint copper is no track, so only the feed line is measured: 0.99 % and 0.31 % on ifa2g4. Task 6 pins it — design §5.3 — cost if wrong: none.
- Ruling: W_AIR_BOX warns, never refuses, an antenna project whose boundary is MUR or whose gap is under λ/4 at f_lo: design §5.2 keeps MUR a project option, and only PML_8 at λ/4 has passed a gate (P3-A's MUR twin rose 16 dB at 0.53 λ) — design §5.2 and P3-A §5 — cost if wrong: one warning.
- Ruling: cost.
  - `PML_WEIGHT` 6.38 and `SMALL_SPEED` 0.384 compose as P3-A's §4 says.
  - **Board** is the nodes inside the dielectric's box.
  - **The speed's basis:** for an antenna's lone job, the calibration's own one-job speed at its threads (`single[threads]`), which P3-A measured the ratio against and which no run refreshes; a v1 run at pool 1 refreshes `levels["1"]`. At a pool above 1 the ratio is unmeasured, and a calibration that never timed one job at its threads (12 CPUs at 4 × 3) falls back to aggregate/pool and over-predicts about 3 times: ponytail ceilings for P3-C.
  - An antenna run does not refresh the calibration: its speed already holds both corrections, and counting them again would over-predict 12 times.
  - **Probed:** the 1.32 M-node ifa2g4 model ran at 76.4 MC/s on 4 threads for 1.5 ns. The corrected model predicts 67.5 MC/s (predicted 1.13 × measured), and the uncorrected one 7.7 times too fast.

  — design §5.9 and P3-A §4 — cost if wrong: two constants.
- Ruling: I_GATES_PASSED_PML replaces I_GATES_PASSED wherever the spec holds "boundary", so v1's line keeps its bytes — P3-A's final-review deferral — cost if wrong: none.
- Ruling: an antenna run saves its S as v1 does, as soon as every job kept S, and writes its S files; with no part port it then transforms its far field and saves again. A failed transform is an E_ line and exit 2; a stopped one propagates (exit 130) with S kept. `results.far_field` holds the three files relative to the run folder, for an antenna only — design §5.5 and Stage 1 §7.8 — cost if wrong: one key, or one more write.
- Ruling: the outputs.
  - **Touchstone:** v1's `layout.s{N}p`, plus `chain.s1p` when part ports close.
  - **Antenna files:** `farfield.csv` (E_θ and E_φ at r = 1 m, D, G and realized G in dBi) and `antenna_summary.csv` per far-field frequency, both only with a far field; `antenna_summary.png` always, drawn by `draw_antenna`, which plan 5 reuses. `write` replaces the summaries first.
  - **Grid and lines:** S11 on the pulse band's grid, with f_lo, f0 and f_hi on it. The resonance is the |S11| minimum refined by a 3-point parabola in dB (the grid's step is 0.12 % of f0, plan 3's threshold 0.3 %), with W_RESONANCE_EDGE at the grid's end. The bandwidth is interpolated in dB at −10 and −6 dB, and a side that never crosses is W_BANDWIDTH_EDGE, never a bounded number. Zin is printed at the start pad it is seen from.
  - **Label and limits:** the relative label first and the five limits last, on the CLI and in the PNG. No loss budget, and no W_NOT_TWO_PORT.

  — design §5.5 and §5.6 — cost if wrong: file names in plan 5.
- Ruling: this plan's pt-BR glossary, by the pt-BR design's §6.1. Plan 1's terms stand (campo distante, eficiência de radiação, diretividade, absorvedor, espaçamento de ar, a PML), and so do v1's (blindagem, tampa, checagem prévia).

  | English | pt-BR |
  |---|---|
  | antenna | antena |
  | module | módulo |
  | chip antenna | antena chip |
  | feed pad | ilha de alimentação |
  | matching chain | cadeia de casamento |
  | band | banda |
  | resonance | ressonância |
  | bandwidth | largura de banda |
  | input impedance | impedância de entrada |
  | mismatch efficiency | eficiência de descasamento |
  | keep-out | área de exclusão |
  | measured region | região medida |
  | octave | oitava |
  | free space | espaço livre |
  | enclosure | gabinete |
  | feed-to-ground join | ligação da alimentação ao GND |
  | radiator | radiador |
  | air box | caixa de ar |

  — pt-BR design §6 — cost if wrong: a native speaker changes a few msgstrs.
- Ruling: the amendments A-26 to A-32 land in Task 12 with the run's numbers. §5.5's lint (A-31) and §3.2, §3.3, §7.4 and §7.5 (A-32) join design §5.13's list, because the code and the Stage 1 spec must agree; §7's one-port retune and verify stay plan 3's. A-29 also records the two cost ratios as the one exception to §6.4's "no numeric constants for any particular PC" — design §5.13 and §6 — cost if wrong: a paragraph moved.
- Ruling: Task 12's pre-registered checks.
  - **Hard:** the job kept, no E_ line, no E_METAL_IN_PML or E_PORT_SHORT, no W_AIR_BOX or W_LIDS_LEFT_OUT, three far-field files, four results files, η_rad ≤ 1.02 everywhere; the pi variant's setup with no port gate blocked.
  - **Cost:** the ratio predicted/measured within [0.67, 1.5] passes; outside it is recorded and plan 4 refits.
  - **Physics, soft:** η_rad 0.5–1.0, D at f0 1.5–4.5 dBi, the resonance and bandwidth reported; an off-band resonance is a fixture finding. The record compares the runtime with design §1's 9–18 min.

  — design §5.11's spirit and P3-A — cost if wrong: one rerun.
- Ruling (disclosure): the architect's probes ran only in a scratch folder, one at a time:
  - the generator under KiCad 9's Python, with its profile in scratch;
  - model builds of the three boards with the repo's venv (read-only), patched in-process;
  - the v1 golden spec hashes under both mesh rules;
  - one openEMS 0.37.0 setup-only run (11 s) and one 1.5 ns run (236 s) of ifa2g4, with `CSXCAD_INSTALL_PATH` typed in the call.

  No suite ran, and nothing was written in the repo or its venv — cost if wrong: none.
- Ruling (disclosure): this revision's own checks also ran only in scratch, on the reviews' scratch fixtures (byte-equal to the architect's) and their in-process prototype:
  - `test_mesh_rule.py` and `test_gates.py` with the draft's rules patched in: the slot-depth test fails, as the feasibility review found (1 failed, 534 passed over seven files);
  - ifa2g4 under v1's rules at 15 AE1 positions (a clean first lint at all), the cross-layer pairing on the three fixtures and the revised line counts (135 × 137 × 71, MUR 119 × 121 × 55, the pi 135 × 143 × 71, the meander 216 × 153 × 79);
  - the node-snapped cut on a real setup dump and on the committed one; the stop-rule times; the refined resonance on the band grid;
  - KiCad 9's RF_Antenna library through the repo's parser, and the licence page.

  No suite ran, no openEMS ran, and nothing was written in the repo or its venv — cost if wrong: none.

## Open issues, ruled by the controller (2026-10-29; owner unavailable)

The plan's last revision left twelve open issues. Each is ruled here as a controller recommendation. Those marked (owner) join the owner's list when this plan merges.

1. (owner) **The capacitor rule.** Design §5.3's capacitor rule is read by its reason, not its wording, as the "rest of the board's parts" ruling says; A-27 records it, and the owner confirms the wording. Plan 4 may add a board with small RF capacitors off the chain to measure it.
2. **The cell d** comes from the feed network alone, as the cell-d ruling says. P3-C's n 2/3/4 decides whether the antenna's own widths must set it.
3. **Arbitrary antenna moves.** Their fit2d sensitivity at n 2 is plan 4's (Not in this plan), which weighs n 3 or the gate for antenna variants.
4. **SMALL_SPEED** stays one PC's measurement until P3-C refits it (Task 9's ponytail).
5. (owner) **Runtime.** The 2.4 GHz worst case is near 75 min a job against design §1's 9–18 min, and the meander's near 7 h. Task 12 records the measured numbers and re-estimates r4's 15–35 machine hours for P3-B to P3-E; plan 4 is planned on them.
6. (owner) **One lid,** with W_LIDS_LEFT_OUT, as the one-lid ruling says.
7. **MUR** stays a project option, warned by W_AIR_BOX, until P3-C.
8. **The join and adopt.** The join taken from the GND pads, and every netless piece of the footprint adopted, stand as ponytail ceilings.
9. **Hand edits.** check_project refuses what it can; a band edited by hand needs `new` again, and an edited step applies at the next run.
10. **The GUI** refuses antenna projects until plan 5 (Task 3's guard).
11. **Prototype numbers.** A missed prototype number stops its task for a ruling (Global Constraints). The controller rules from the measured value and the formula that differs, never by loosening a test without that reason.
12. **The Review Focus** keeps five items; the interrupted transform is Task 11's test.
