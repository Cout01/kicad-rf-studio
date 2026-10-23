# kicad-rf-studio — Stage 1 design: a validated simulation engine

- **Date:** 2026-10-16
- **Status:** design approved section by section in conversation, revised on 2026-10-19 after an independent review, and approved by the owner. On 2026-10-21 the owner confirmed one amendment to §5.4: the substrate height now counts in the cell size.
- **Scope:** Stage 1 of the project: the headless engine, the command-line orchestrator and the validation gates. The GUI and the KiCad toolbar button (Stage 2) get their own spec, written with Stage 1's results.

---

## 1. Purpose

kicad-rf-studio lets a hardware engineer simulate the RF parts of a KiCad board with openEMS without writing openEMS scripts.

The first workflow is **RF front-end matching**:
1. Pick an RF path on a KiCad board.
2. The app simulates the cropped layout once, with a port at every RF part.
3. L and C values are then retuned instantly, with no new field simulation.
4. The results are S11, S21, harmonic rejection and a Smith chart.

The simplest case is a single trace between two pads, with no parts. Two runs give its S11 and S21, and `cost` prints the 2D Z0 and εeff of each straight section with no 3D run at all.

The users are hardware engineers who use KiCad and are not FDTD experts. The project is public open source.

### 1.1 Decisions this design rests on

| Topic | Decision |
|---|---|
| Use cases, eventually | PCB antennas, line impedance, RF filters and matching, EMC/SI |
| First workflow (v1) | RF front-end matching. The line-impedance check stays as an internal regression test against KiCad's line calculator |
| Import | The app reads `.kicad_pcb` directly, and KiCad may be closed. In Stage 2, a KiCad toolbar button also sends the open board and the selection |
| Licence and hosting | GPL-3.0-or-later, on GitHub |
| Platforms | Windows 10/11 and Linux |
| UI language | English. Every user-facing string is translatable from day one, and a pt-BR translation follows right after v1 |
| openEMS | Used as-is: openEMS 0.37.0 and CSXCAD 0.7.0, installed separately, never bundled in v1 |
| Simulation domain | Always a selected region, never a whole board |
| Defaults | Safe automatic defaults. In Stage 1 every default is written to `project.json`, which serves as the advanced settings; Stage 2 adds an advanced panel |
| Stackup | From the board file, or a confirmed preset. The first preset uses JLCPCB's published data |
| Copper weight | Only 1 oz (35 µm) is validated |
| Part data | Users keep a local folder of vendor S2P files. The app never ships them |
| Hardware | None. Everything runs on the PC: no fabricated boards or coupons, no VNA, no lab measurements. All references are numerical |
| Architecture | Our own thin core, one CLI orchestrator and worker processes. In Stage 2, a PySide6 GUI client that never imports openEMS. No fork of an existing tool, and no GUI hosted inside KiCad |
| Order | Validate first (this spec), build the GUI afterwards |
| KiCad | Version 9 minimum; reads KiCad 9 and 10 files |
| Default v1 scope | The output chain: RF switch common port → DC block → pi low-pass → coaxial connector, under a shield lid. TX-side matching, which has rotated parts, joins only if the rotated-port test passes (§9.3) |
| Time policy | Whether Draft or Normal accuracy is the default is decided after the Stage 1 measurements |
| Fallback if the private-board gate fails | Keep the instant retune, labelled "relative / what-if", and offer a full verification run of the final value set (§7.6) |

### 1.2 What v1 must show, and what Stage 1 measures

- **Line Z0** of mask-free lines within 5 % of KiCad's line calculator, and εeff within 3 % of a 2D reference.
- **Physically valid S:** passivity, reciprocity and a loss budget.
- **Instant-retune results** consistent with full simulations, within the thresholds in §9.4.
- **Runtime:** "minutes, not hours" is a v1 success criterion. Runtime is shown before every run and measured afterwards. P0-C (§9.4) measures whether the promise holds, and the owner then sets the time policy.
- **A GUI that never freezes.** This is Stage 2, but this architecture is what makes it possible.

### 1.3 Terms

- **Chain:** the RF path from `--start` to `--end`, with its parts (§4.6). **P** is the number of external ports and **M** the number of part ports.
- **Measured nets:** the chain's signal nets.
- **ROI:** the region of interest around the chain (§5.1). **Margin:** the coarse-mesh region between the ROI and the walls.
- **Protected set:** the copper that the mesh rule protects (§5.4).
- **C_box:** the capacitance of a part port's box (§5.7).
- **f1, f2:** the edges of the simulated band (§5.8).
- **cs2d, fit2d:** the 2D cross-section reference, and the gate that checks the actual mesh against it (§5.5).
- **Chain-equivalent:** the machine time of one full set of P + M runs of the output chain.

---

## 2. Stages

| Stage | Content | Spec |
|---|---|---|
| 1 | Headless core, CLI orchestrator, worker, validation gates P0-0 to P0-D | This document |
| 2 (completes v1) | PySide6 GUI client, KiCad toolbar button, live import through kicad-python | Own spec, written with Stage 1's results |
| 3 | PCB antenna placement, with relative results (PML, NF2FF) | Later |
| Later | SI, EMC and differential pairs, a GPU engine, a bundled installer | — |

---

## 3. Architecture

### 3.1 Units

| Unit | Responsibility | Depends on | Interface |
|---|---|---|---|
| `core.kicad` | Reads `.kicad_pcb` text into a Board (copper, pads, vias, footprints, zones, board outline, stackup, mask) and traces the RF chain | stdlib, shapely | `load_board(path) -> Board`, `trace_chain(board, start, end) -> Chain` |
| `core.geometry` | Copper pipeline, region and walls, vias in the margin, shield lid | shapely, numpy | Polygons per (layer, net) inside the region |
| `core.mesh` | Mesh rule, edge lint, fit2d gate, timestep floor | numpy | Mesh lines in x, y and z, plus check results |
| `core.model` | Part roles and models, external ports and port boxes, excitation and band, CSX build | openEMS and CSXCAD, imported lazily | A serialisable model spec and `build_csx(spec)` |
| `core.post` | Co-simulation reduction, retune, validity indicators, exports | numpy, scikit-rf, matplotlib | Touchstone, PNG and CSV files |
| `core.project` | Project file and hashes | stdlib | `project.json` |
| `core.messages` | Message codes with parameters, and the gettext catalog | stdlib gettext | Used by every unit |
| Orchestrator (the CLI) | The only run controller: run folders, worker pool, stop rule, events, STOP/ABORT, cost, calibration | stdlib subprocess | `kicad-rf-studio <command>` and `events.jsonl` |
| Worker | One process per excitation: builds the CSX, calls `FDTD.Run` with an explicit thread count, writes the waves (the time-domain port voltages and currents) | openEMS, CSXCAD, numpy and h5py only | `job.json` in; `waves.npz` and a log out |

**Rules**
- The core never imports Qt.
- `core.model` imports openEMS and CSXCAD only inside functions that the worker calls. `cost` runs the worker in setup-only mode and `preview` has it write the XML, so only worker processes ever import openEMS.
- `core.mesh` carries its own copy of CSXCAD's pure-Python `SmoothMeshLines`, because importing it from CSXCAD loads the compiled extension.
- The worker never imports scikit-rf, which pulls in pandas, nor matplotlib.
- In Stage 2, the GUI:
  - starts the orchestrator detached and tails `events.jsonl`;
  - never imports openEMS or CSXCAD;
  - can be closed without stopping a run, and re-attaches when it is reopened.

### 3.2 Command line

| Command | What it does |
|---|---|
| `kicad-rf-studio new BOARD --start REF.PAD --end REF.PAD --f0 915MHz [--harmonics 3] [--preset draft\|normal\|strict] [--stackup PRESET] [--lid-height MM] [-o PATH]` | Writes `project.json` with the traced chain, part roles and models, reference terminals and every default, and prints every value it assumed. The user may edit it. Default output: the current directory |
| `kicad-rf-studio cost PROJECT` | First prints the 2D Z0 and εeff of each straight, axis-aligned section of the measured nets, with and without mask, labelled "2D estimate: bends, vias, pads and parts not included". Then runs the worker in setup-only mode, without simulating, and reports cells, smallest cell, dt and the limiting node, the time (§6.4), RAM, and the dominant cost driver |
| `kicad-rf-studio run PROJECT` | Runs the gates and every excitation, records the results in the project, and writes the outputs of §7.3 at the current values |
| `kicad-rf-studio retune PROJECT REF=VALUE \| REF=file.s2p:series\|shunt ...` | Stores the values in `project.json` and writes the combined chain (Touchstone) and the summary. No new run. A vendor S2P is a 2-port measured in a series or a shunt fixture; the suffix says which, and so how the file becomes Z_part |
| `kicad-rf-studio verify PROJECT` | One full run with every part inside the grid as an ideal element at its current value (§7.6) |
| `kicad-rf-studio preview PROJECT` | Has the worker write `model.xml` without building the operator, then opens it in AppCSXCAD |
| `kicad-rf-studio setup-openems DIR` | Windows only: installs the openEMS and CSXCAD wheels from the official package into the app's environment and records CSXCAD_INSTALL_PATH |
| `kicad-rf-studio calibrate` | Re-runs the speed calibration. It also runs automatically before the first `cost` or `run` |

**Stage 1 never prompts.** Whatever this spec calls asked or confirmed comes from a `new` option or a `project.json` field, and `run` refuses while a required value is missing.

Stage 2's GUI calls the same functions, in the same order: `new`, then `cost`, then `run`, then `retune`. The GUI adds no run logic of its own.

### 3.3 Files and folders

- **`project.json`.** One file is both the project and the job spec. It holds:
  - a schema version;
  - the board path, relative to `project.json`, and the board hash;
  - the region definition and the stackup, including the mask;
  - f0, the harmonics, the preset, the band factor and T_max;
  - the chain and the parts (reference, value, role, model);
  - the external ports, each a (signal pad, reference pad) pair;
  - the mesh parameters;
  - one hash over the model spec handed to the worker: geometry, stackup, mask, mesh, ports, part roles, port boxes and excitation;
  - the results: the run folder, which holds the waves of each excitation, C_box for each part port, and the verdicts.
- **Run folders** live in the per-user data directory, never in the system temp directory:
  - Windows: `%LOCALAPPDATA%\kicad-rf-studio\runs\`;
  - Linux: `$XDG_DATA_HOME/kicad-rf-studio/runs/`.

  A run folder holds the model spec, `events.jsonl`, a `STOP` file when a stop is requested, and one folder per job, because openEMS runs inside its own folder. A job folder holds `job.json`, the log, openEMS's files and `waves.npz`.
- **Lock:** one per project, `project.json.lock` next to the project file, so two runs of one project never overlap.
- **Settings:** a per-user `settings.json` next to the run folders holds the openEMS folder and the speed calibration.
- **`events.jsonl`.** One JSON object per line: `{"t", "kind": progress|verdict|cost|result|message, "job", "code", "params"}`. The events carry message codes, never text, so they stay language-neutral and are translated only when displayed.
- The exact fields of `job.json`, the model spec and the events, the CLI exit codes and the run-folder names are fixed in the implementation plan.

### 3.4 Dependencies and install

- **Dependencies:** numpy, scipy, h5py, matplotlib, shapely and scikit-rf. Stage 2 adds PySide6-Essentials and kicad-python.
- **openEMS and CSXCAD** are not on PyPI, so they are never declared as dependencies.
- **Windows:**
  - The official openEMS wheels need Python 3.13 or 3.14.
  - Install steps:
    1. `py -3.14 -m venv <venv>`;
    2. `pip install <clone of the repository>` (publishing on PyPI is an open item, §12);
    3. `kicad-rf-studio setup-openems <openEMS dir>`.
  - Step 3 wraps `pip install --no-index --no-deps --find-links <dir>\python openEMS CSXCAD`. `--no-index` stays, because both names are unclaimed on PyPI and dropping it invites dependency confusion.
- **Linux** (tested only in CI containers):
  - Debian 12, Ubuntu 24.04 and Fedora, each with its system Python (≥ 3.11).
  - openEMS comes from upstream's `install_deps.sh` and `update_openEMS.sh <prefix> --python`. The script runs with the app's venv active, so that the bindings land in it; otherwise the script creates its own venv. The GUI build stays on, so that AppCSXCAD exists.
- **Version check:** before any command that starts a worker (`cost`, `run`, `verify`, `preview`), a subprocess checks that openEMS is at least 0.37, and the app warns outside 0.37.x.

### 3.5 Translations

- stdlib gettext, with one catalog shared by the core, the CLI and later the GUI.
- Messages carry a code plus parameters, and the English template is the msgid.
- Babel is a dev-only tool for extracting and compiling the catalogs, because the Windows Python ships no `Tools/i18n`.

### 3.6 Licence and notices

- GPL-3.0-or-later. openEMS is GPL-3.0-or-later and CSXCAD is LGPL-3.0-or-later.
- An SPDX header in every source file.
- A NOTICE file lists every third-party piece, with its licence:
  - RFsim (MIT): the package-parasitic presets, the outer-wall rule and the test-board pattern, if used;
  - formulas ported from KiCad's line calculator for the tests (GPL);
  - anything taken from gerber2ems (Apache-2.0);
  - the copy of CSXCAD's `SmoothMeshLines` (LGPL-3.0-or-later).
- Vendor S2P files are never committed.

---

## 4. Board import (`core.kicad`)

### 4.1 Reader

- A stdlib tokenizer: 0.21–0.35 s on a 6.4 MB panel.
- The `filter_ratio` repair and a bracket-balance check.
- Unknown tokens are tolerated.
- Nets are looked up by name, because KiCad 10 no longer writes net codes.
- Items are keyed by UUID, and coordinates map to (x, −y).
- Pad copper is placed with KiCad's ShapePos transform. In the research it matched pcbnew on every pad of one KiCad 9 board, which had no arc, custom or trapezoid pads; the fixtures cover those shapes.
- Reads KiCad 9 and 10 files.

### 4.2 Solder mask

From each pad's mask expansion, the board's `pad_to_mask_clearance`, the F.Mask/B.Mask graphics and zones, and the stackup's mask thickness and εr, the reader builds the mask-opening polygons.

### 4.3 Zone fills

- **Default:** the fills are used as saved.
  - A zone with no fill raises a warning.
  - A banner says: "Fills as saved — refill (B) in KiCad and save if you changed copper."
- **Live refill** through kicad-python is Stage 2.
- The product contains no pcbnew/SWIG code.

### 4.4 Stackup

- The stackup is parsed from the board.
- If the board has none, `new` refuses until `--stackup` names a preset, or `--stackup kicad-default` accepts KiCad's default rule. For a 0.8 mm 2-layer board, that rule gives a 0.71 mm dielectric and a 10 µm mask with εr 3.3.
- **First preset:** JLCPCB, transcribed from JLCPCB's published stackup data. The preset file records the source, the date, and the frequency at which εr and tanδ are specified.
- Copper other than 35 µm raises the warning "mesh rule not validated for this copper weight".

### 4.5 Components

Per footprint, the reader takes:
- the reference;
- the value. The value parser accepts `10uF/16V`, `0R` and `1meg`;
- the MPN field, if present;
- the footprint, the pad UUIDs, the orientation and the DNP flag.

### 4.6 Chain tracer (new code)

- A breadth-first walk from the start pad, over nets and through two-pad parts.
- It stops at:
  - GND and power nets;
  - parts with three or more pads;
  - connectors;
  - DNP parts.
- Nets are keyed by name.
- GND and power nets are recognised by name, connectors by reference prefix and shields by their frame-only pads. `new` prints each classification, and `project.json` can override it.
- Shunt parts that touch the chain's nets but sit off the walked path are tagged. They are RF-path parts (§5.7).
- The result is the ordered chain plus those shunt parts.
- Start and end on one net with no parts between them is a valid chain: a single trace, with P = 2 and M = 0.
- An RF switch is always a chain end, with the port on its pin.
- A self-check runs on the public `lpf915` board (§9.1).

---

## 5. Physics model (`core.geometry`, `core.mesh`, `core.model`)

### 5.1 Region and boundaries

- **The ROI** is the bounding box of the chain's nets, part pads and port pads, expanded by 3 substrate heights. The expansion can be changed in the project. The ROI is clipped to the board outline, where the substrate ends.
- **Walls** sit at ROI + 4 mm + 8 coarse cells, with MUR on all six faces.
- **Through-crop.** Copper, substrate and vias run through the walls. Nets are never cut at the ROI edge: an "island crop" was 2–80× worse in the research.
- **PML_8 on all six faces** is for antennas only (Stage 3), where no copper enters the absorber; Stage 1 always uses MUR. Boundary types are never mixed per face: the per-face mix and PML_8 grew after 15–21 ns, while MUR at the outer wall stayed stable.
- **Connectivity.** A short or an open inside the ROI is a gate; in the margin it is a warning.
- **Vias** in the protected set (§5.4) are solid PEC cylinders on the fine mesh. All other vias, in the ROI or the margin, become PEC curves snapped to the mesh; otherwise a 0.3 mm cylinder on 2.4 mm cells touches no mesh edge and vanishes.

### 5.2 Shield lid

- **Trigger:** a footprint with only frame pads whose outline overlaps the ROI, or a part the user tagged as a shield.
- The lid height is a project field, set with `new --lid-height`; `run` refuses while a detected lid has no height.
- The lid is a PEC plate plus walls on the frame outline, clipped at the walls like the copper.
- Its z position is snapped to existing mesh lines. Naive insertion created 8.3 µm slivers and halved dt.
- It is on by default whenever harmonics are shown.
- The opening over the coaxial connector is kept, and the shield is never used as the domain boundary.

### 5.3 Copper, solder mask and dielectric

- **Copper:** solid PEC of stackup thickness wherever any width or gap is below 30·t. Zero-thickness sheets are used only for structures that are wide everywhere. Evidence: sheet copper read Z0 8.7 % high on a 50 Ω GCPW, and an earlier sheet-and-mesh recipe was 20.7 % low.
- **Copper pipeline,** per (layer, net):
  1. `make_valid`;
  2. union;
  3. clip 1 mm past the walls;
  4. simplify at ≤ 10 µm, preserving topology;
  5. quantise to 1e-6 mm;
  6. vertical hole split;
  7. one `AddLinPoly` (solid) or `AddPolygon` (sheet) per piece.

  Never tile, and never use `.exterior` alone.
- **Solder mask:**
  - εr and thickness come from the stackup. The default is 10 µm and εr 3.3.
  - Inside the copper-thickness z-cell, the mask fills the gaps between conductors.
  - The coat above the copper is smeared over the first z-cell dz0 with ε_h = (t_m·ε_m + (dz0 − t_m))/dz0. The formula needs t_m ≤ dz0, which the mesh rule guarantees (§5.4).
  - Openings are honoured.

  In a 2D check on three lines, this model was within 0.07 % in Z0 and 0.13 % in εeff of the exact mask, with no extra z-line and no timestep cost. P0-A confirms it in FDTD. The mask moves a 50 Ω GCPW's Z0 by −2.8 to −7.8 %, up to more than the 5 % budget, so it cannot be ignored.
- **Dielectric loss:** a constant κ, set at f0. This is exact for the insertion loss at f0. At the harmonics it underestimates the loss, which is conservative for rejection. A Debye fit is deferred.

### 5.4 Mesh

- **Protected set:**
  - the measured nets;
  - their reference copper and vias within about 3 substrate heights (provisional; P0-B checks the reach);
  - the part pads;
  - the port boxes.
- **Rule for the protected set:**
  - one cell size d for the whole set: the smallest width or gap of the measured nets, or the substrate height h under them, divided by n, with n = 2 (standard) or 3 (fine), capped at 0.9·λ_min/20. The height counts because a strip's fringing field spreads over about h: a 3 mm microstrip on 0.71 mm meshed at d = w/2 read Z0 5.4 % low;
  - at solid-copper edges, lines sit d/4 inside and 3d/4 outside;
  - every feature is filled at d or finer.
- **Everything else:** vertex lines are clustered to a minimum cell, then graded with `SmoothMeshLines` at a ratio of 1.3 or less.
- **z:** exactly one cell across each copper thickness. Outside each copper face, dz0 = max(t_m, min(d/3, h/4)), graded ×1.3, where t_m is the mask thickness.
- **Collisions:** unprotected lines move first. If two protected patterns collide, they share one pattern, and fit2d checks it.
- **Merging:** in-plane only below d/3, in z only below dz0/3. Protected lines never move.
- **Quantisation:** every coordinate and mesh line goes to 1e-6 mm. The XML preview's 7 significant digits affect only the display.
- **Validity:** the rule is validated for 35 µm copper only.

### 5.5 Mesh gates

Only the edge lint first tries one automatic re-mesh; the other gates block directly. Every failure message says what to do next.

- **Edge lint**, on the protected set's in-plane copper edges. It fails when:
  - a line sits on the edge;
  - the nearest inside line is closer than d/8;
  - the first outside line is closer to the edge than the nearest inside line.

  Lines on edges measured −7 to −14 % in Z0. The pinned z faces of the copper are exempt. The lint's own tests include known-bad meshes: lines on the edge, and lines 1 µm inside the metal.
- **fit2d gate.** Each straight, axis-aligned section of a measured net is checked on the actual mesh against the 2D reference (cs2d), with the mask included in both. Above 3 % in Z0 the run is blocked; P0-A confirms the threshold. It takes about 0.1 s per section.
- **Timestep floor.** The reference is the vacuum Courant step of the smallest cell that the rule itself places in x, y and z. The run is blocked if openEMS's dt falls below 0.8 × that reference (P0-A confirms the factor), and the limiting node is reported (setup-only, verbose = 2). One stray 10 µm cell once made a run 5.5× longer.
- **Non-axis-aligned copper on measured nets** (45° segments, arcs). The user gets the warning "staircased, accuracy not validated" and an offer of local refinement. It is refused if P0-A shows errors above the budget.

### 5.6 External ports

- 50 Ω lumped ports between an explicit (signal pad, reference pad) pair.
- The reference is chosen automatically and always shown, in this order:
  1. a connector → its shell or GND pads;
  2. an IC pin → the nearest GND pad or exposed pad of the same footprint;
  3. otherwise → the nearest GND copper on the same layer;
  4. if there is none, `run` refuses until the reference pad is set in `project.json`.

  A reference on the opposite layer is never chosen automatically: on one layout, moving a reference from the adjacent pour to the bottom layer changed |S11| from −9.1 to −4.6 dB.
- **Port boxes on the mesh:**
  - the in-plane ends sit on the last mesh line inside each pad;
  - z spans the full copper thickness;
  - the width is snapped inward to lines inside the pad.
- **After setup** (setup-only plus a PEC dump), the PEC edges are grouped into connected pieces. Each port's two ends must lie in the pieces of its declared signal pad and reference pad, and those must be different pieces. The dump has no labels, and a lumped port's own end caps are PEC, so touching PEC alone proves nothing. Otherwise the run is blocked.
- An "unused primitive" on a port, excitation, probe or lumped part is an error.

### 5.7 Parts

Roles are assigned automatically and can be edited in `project.json`.

| Part | Role |
|---|---|
| Two-terminal part on the RF path, series or shunt | A port. Its model is the ideal value plus the package ESL/ESR preset, or a vendor S2P file that the user names (`retune`, §3.2) |
| `0R` | A copper rectangle, rotated if needed. Option: "as port" |
| DNP | Open |
| Other C or R in the ROI, not on the chain's nets | In the grid only if SRF > 3·f_max (SRF from the preset). Otherwise open, with a warning; the user can make it a port in `project.json`, and `cost` shows the extra run |
| Inductor | Never in the grid. A choke is open only if \|Z\| ≥ 200·Z0 across the band, SRF included. Otherwise it is a port |
| Rotated two-terminal part (not a multiple of 90°) | A CurvePort, only if P0-B's rotated case passes. Otherwise refused, with a message |

**Why every RF-path part is a port.** An ideal in-grid DC block of a few tens of pF is wrong above its self-resonance, which for such parts lies near 1.5 GHz: at 2·f0 the real part is already inductive. openEMS also has no stable series C + ESL element.

**C_box.** It is computed from the edge capacitances openEMS actually assigns to the port box (operator dump), with the mask between the pads included. The dumps are VTK XML files, read with a small stdlib reader. P0-B checks C_box against an empty-box run.

### 5.8 Excitation and band

- **Pulse:** a DC-free custom excitation, `sin(2π f_m (t − t0))·exp(−(2π f_w t/3 − 3)²)·(t < 2 t0)`, with f_m = (f1 + f2)/2, f_w = (f2 − f1)/2 and t0 = 9/(2π f_w). f_m and f_w are pulse parameters, not the operating f0. f2 is passed as the first frequency argument of `SetCustomExcite`: openEMS 0.37 takes the sampling rate from that argument and ignores the second.
- **Default band:** f1 = f_fund/2 and f2 = 1.1 × the highest harmonic shown; 1.25× is an option. For 915 MHz up to the third harmonic, that is 0.458–3.020 GHz:
  - the excitation magnitude |a| is −8.1 dB at f, −0.1 dB at 2f and −12.1 dB at 3f;
  - a plane-pair mode at 3.45 GHz sits at −34.9 dB.
- **Diagnostics:** |a(f)| is shown next to every reported frequency in the detailed output.
- **T_max:** a required project field, default 40 ns, set with `SetMaxTime`. The custom pulse allocates its samples before the run, so T_max must always be set.

---

## 6. Run control (orchestrator and worker)

### 6.1 Lifecycle

1. `run` takes the project lock and creates a fresh run folder.
2. It builds the model spec once and runs the gates: the mesh gates in the orchestrator, then one setup-only worker for the timestep floor, port connectivity and unused primitives, as `cost` does. A failed gate ends the run before any job starts.
3. It creates one job per excitation: P external ports plus M part ports.
4. A worker pool runs the jobs, each in its own job folder as `<venv python> -I -u -m kicad_rf_studio.worker job.json`, with an explicit thread count and OPENBLAS_NUM_THREADS=1.
5. Every event goes to `events.jsonl`, and stdout gets the same events as translated, readable lines.

**Stop.** A `STOP` file in the run folder, or Ctrl+C, makes the orchestrator write `ABORT` into each job folder. openEMS reacts at the next engine chunk: 0.6–1.1 s at 2 M cells, and 30.6 s in one measured case. During setup, only a hard kill works.

### 6.2 Engine settings

- EndCriteria = 1e-15, so openEMS's own criterion no longer stops runs on aliased energy dips. It cannot stop the NaN exit: a NaN energy still ends the engine loop as if converged, and the post-run checks (§6.3) then mark the run "diverged". The criterion's end messages also print only for the Gaussian excitation, so runs with the custom pulse end silently.
- `exact_endcriteria` keeps its default (off) and is never passed, because of the keyword quirk in §11.
- `SetMaxTime(T_max)` always.

### 6.3 Stop rule

The orchestrator polls each worker's port probe files at a fixed wall-clock rate. openEMS flushes every time-domain probe sample as it writes it; a partial last line is ignored. Only the log energy arrives at intervals of 4 s or more. The samples are taken in simulated time, so the rule does not depend on machine speed.

| Signal | Rule | Action |
|---|---|---|
| Log energy, or any probe sample, is NaN or inf | Immediately | ABORT; the run is marked "diverged" |
| Log-energy envelope, with its window widened until it holds ≥ 4 samples, armed only after the pulse ends (t > 2·t0) | ≥ its running minimum + 20 dB (provisional) | ABORT; S is invalid ("growth") |
| Port residual R(t) = max over the last 2 ns of Σ_p u_p² + (Z0·i_p)², in dB (10·log10) relative to its peak | ≤ the preset level, **and** the in-band monitor ≤ the preset tolerance. The monitor is the maximum, over ports j and frequencies f1–f2, of \|s_jk(t) − s_jk(t − 1 ns)\|, where s_jk = b_j/a_k comes from the job's records cut at t and k is the excited port | ABORT; "converged" |
| Port residual | Flat within 1 dB over 5 ns, above the level | ABORT; S kept and flagged "not converged at X dB" |
| Exit at T_max | — | S kept and flagged with the residual reached |
| Any other exit | — | "Unclassified, not converged" |

**After each run:**
- check that every probe sample is finite;
- check that the residual at the cut time is at or below the level;
- compute S from records **cut at the time the criterion was met**, so the results do not depend on the stop latency.

**Presets.** Provisional; P0 retunes them.

| Preset | Port residual level | S tolerance |
|---|---|---|
| Draft | −50 dB | 1e-2 |
| Normal | −60 dB | 2e-3 |
| Strict | −70 dB | 5e-4 |

**Evidence.** On a real-board crop, the port residual reached −60 dB at 13.1–13.6 ns, and S cut there differed by at most 5.7e-3 from the full record.

**Testing the rule.**
- Replay saved traces at decimations from 1 to 16. The rule this replaces flipped 11 of 14 verdicts at a decimation of 8.
- Run the "converged" branch live in P0-B and P0-C.

### 6.4 Cost model and calibration

- **Cost** = runs × cells × (T_stop / dt) / aggregate speed. The worst case uses T_stop = T_max. After a project's first run, `cost` also predicts the time from that run's stop time.
- **`cost` output:** cells, smallest cell, dt, the limiting node, predicted and worst-case time, RAM (about 170 MB per million cells per job) and the dominant cost driver.
- **Calibration,** 20–30 s on a small built-in model, before the first `cost` or `run`:
  - it measures MC/s at 1, 2, 4 and N threads, and one job against 2–4 parallel jobs;
  - the results are stored per machine and refreshed from every run's `Speed` lines.
- **Before calibration:** threads ≤ `os.cpu_count() // 2`, and the pool size follows from the cores and the RAM.
- The code holds no numeric constants for any particular PC.
- **The bracket for the output chain** on the development PC is 16 min to about 8 h for its 6 runs. Three unknowns set where it falls:
  - the cell count of the rule-compliant crop;
  - the co-simulation ring-down;
  - the parallel speed on an idle machine.

  Nothing is promised until P0-C has measured them.
- **Levers still available:** a tighter ROI, a smaller protected set and the Draft preset. Later: the reciprocity fit and the Linux/GCC or GPU engines.

---

## 7. Co-simulation and results (`core.post`)

### 7.1 Runs

All P + M excitations always run, because the matrix A must be square: S = B·A⁻¹. A least-squares fit using reciprocity, which would save one run, is deferred until it is validated.

### 7.2 Retune

- Each part is re-attached as Z_part ∥ C_box with scikit-rf's `Circuit`. That takes 3.7 ms per retune for a 6-port at 400 points.
- A plain numpy termination is the test oracle. The two agree to 1e-15–6e-15 (measured), and the tests assert 1e-12.
- Values are ideal or, per part, an S2P file, converted to Z_part with the series-thru or shunt-thru formula that the user named. Stage 2 adds E12/E24 snapping.

### 7.3 Outputs

- S21 and S11, with markers at f0 and at each harmonic shown.
- Insertion loss, return loss and harmonic rejection, labelled "relative to the chosen source impedance".
- "Ideal schematic" next to "with layout".
- **Exports:**
  - Touchstone for the layout N-port, with its port map, and for the combined chain;
  - a PNG summary with S11, S21 and a Smith chart of S11, and a CSV summary.
- The files go to a `results/` folder next to `project.json`, and each retune replaces the previous set.
- A single trace (M = 0) has no retune: its outputs are S11, S21 and its 2-port Touchstone.

### 7.4 Validity indicators

- **Passivity:** σ_max ≤ 1.02. P0 may tighten it.
- **Reciprocity:** error ≤ 0.02.
- **Loss budget:** the unaccounted power 1 − |S11|² − |S21|² of the combined chain, less the power the part models absorb themselves (ESR and S2P data, from the waves into each part port), against the expected dielectric loss: the quasi-TEM loss from εeff, εr and tanδ over each section's length. An excess above 2 % is flagged. `verify` keeps its parts in the grid, so its loss budget counts an in-grid resistor's loss as layout loss.

### 7.5 Stated limits

These are printed with every result:
- no magnetic coupling between part bodies;
- no interaction between part bodies and the lid;
- vendor S2P reference planes differ from the pad-gap box;
- copper is PEC, so there is no conductor loss;
- the through-crop walls absorb most of the power coupled into cut nets, and reflect the rest.

Accuracy is reported as |ΔS| or as a null shift, never in dB at a null.

### 7.6 Verification run and fallback

- **`verify`** runs once with every part in the grid as an ideal element at its current value. S2P and ESL/ESR models are replaced by that value. Each part sits in the box of the port it replaces:
  - capacitors are classic C of C_part + C_box. A classic C replaces the box's own capacitance instead of adding to it (measured), so the box's C_box is added back to match the retune's Z_part ∥ C_box;
  - inductors use LEtype=0 in a one-cell box, joined to both pads by PEC strips, with an explicit C equal to the cell's own capacitance. Without it, openEMS 0.37's Z_FACT rule lowers that capacitance, using the excitation's cut-off frequency, which the custom pulse never sets (it reads uninitialised memory: the cell's C fell to zero in 4 of 22 runs), and the run can diverge;
  - the k check, k = dt/(2·√(L·C)) ≤ 0.45, makes sure the time step resolves each inductor cell's resonance. An isolated cell is stable up to k = 1, but in the grid, at openEMS's own dt, runs diverged from k ≥ 0.49. Real parts read k ≈ 0.003–0.03. If a part fails it, `verify` refuses and names the part;
  - LEtype=1 is never used, because it is unstable in 0.37.
- Its result is compared with a retune at the same ideal values: |ΔS| at f0 and up to f2. It checks the layout reduction, not the vendor part data, and the output says so.
- It is the consistency reference for P0-B and P0-C.
- **If P0-C fails** (§9.4), v1 labels the instant retune "relative / what-if" and offers `verify` for the final value set.

### 7.7 Complex targets at IC pins

Deferred until the TX side is in; the output chain is 50 Ω at both ends. When they are added, every renormalisation passes s_def explicitly ('pseudo' to Z_t, 'power' to conj(Z_t)), with a unit test on a known complex load.

### 7.8 Project file

- Reopening a project allows retuning with no new runs.
- Results are reused while the model-spec hash (§3.3) is unchanged. Any change to the model spec, from a re-import or from an edit of `project.json`, asks for a new run.
- A run replaces the stored results, and the files in `results/`, only when every job kept S. A run that does not, because a job diverged or was stopped, leaves the previous results as they were.

---

## 8. Errors and checks

| Check | Type |
|---|---|
| Board parse: bracket imbalance, unsupported version | Error, with the line number |
| Unknown REF.PAD, or no chain found between the endpoints | Error, with the nearest candidates listed |
| Missing S2P file named in the project | Error |
| Required value missing: stackup, lid height or port reference | Error, naming the `new` option or the `project.json` field |
| openEMS missing, or older than 0.37 | Error, with the install command |
| Copper connectivity inside the ROI | Gate |
| Connectivity in the coarse margin | Warning |
| Port connectivity after setup | Gate |
| Edge lint on the protected set | Gate, after one automatic re-mesh |
| fit2d on straight sections | Gate above the threshold |
| Timestep floor | Gate |
| Unused primitive on a port, excitation, probe or lumped part | Gate; on a copper sliver, a warning |
| Non-axis-aligned measured copper | Warning; refusal if P0-A says so |
| Zone fills possibly stale | Banner |
| Copper weight other than 35 µm | Warning |
| Passivity, reciprocity, loss budget | Indicators |
| Run exit | Always classified (§6.3); never silently "done" |

- Every message is a code with parameters, and says what to do next. Every refusal stated elsewhere in this spec is also a coded error, even if it is not in this table.
- AppCSXCAD fails on non-ASCII paths, so `preview` launches it with the job folder as the working directory and a relative file name.

---

## 9. Verification plan (Stage 1 gates)

### 9.1 P0-0: repository and safety

- **Porting.** The public repository starts empty. The research prototypes, kept in a private archive outside the repository, are ported one module at a time, each with its test. Harnesses that depend on other projects' patched code stay private.
- **Privacy gate,** on the PC, before anything leaves it:
  - One stdlib script, run by git pre-commit and pre-push hooks. The pre-push hook scans every commit being pushed: file contents and names, author and committer fields, messages, and the member names inside `.npz` and `.zip` files. Any hit refuses the push.
  - The private list stays on the owner's PC, outside the repository. The hooks read its path from an environment variable and fail closed when it is missing. Nothing derived from it is ever committed, and the gate's own tests use a list of dummy words.
  - Generic regexes catch absolute drive and home paths, UNC shares and e-mail addresses in file contents. CI repeats only these, as a backstop.
  - Before the first push, the whole history is scanned and rewritten to the chosen identity (§12).
- **`.gitignore`** excludes project files, Touchstone files, run and result folders, and KiCad side files, except under `tests/fixtures`.
- **Fixtures** are generated once, at dev time, with KiCad 9's pcbnew in an isolated KiCad profile, and committed. The profile's KICAD_CONFIG_HOME, KICAD_DOCUMENTS_HOME, KICAD_CACHE_HOME, TEMP and TMP point at a scratch folder, APPDATA and LOCALAPPDATA are redirected into it, and TMPDIR and every other KICAD* variable are cleared, so KiCad's API pipe and instance locks never share the owner's temp folder. (A-3, plan 5: controller recommendation, owner unavailable.) The fixtures are:
  - 50 Ω GCPW and microstrip coupons, mask-free by construction, plus masked variants and one GCPW coupon with pads at both ends;
  - a dense-neighbour coupon, a 45° GCPW and an arc coupon;
  - `lpf915` and its twin `lpf915-45`;
  - the pad polygons that pcbnew exports for each fixture board, so that CI checks pad placement without KiCad;
  - probe traces for replaying the stop rule: synthetic ones first, then traces from the coupon and `lpf915` runs. Traces from a private board are never committed;
  - synthetic S2P files built from ideal RLC, generated inside the tests and never committed.
- **`lpf915`,** a public synthetic board that also serves as the tutorial. It has:
  - a 0.8 mm 2-layer stackup and a 50 Ω GCPW;
  - 0402 footprints for a series DC block and a C-L-C pi, with values in the Value fields, including `0R` and `10uF/16V`;
  - all parts at multiples of 90°. The twin `lpf915-45` has one of them at 45°, for P0-B's rotated case;
  - an IC-like pad group with a GND exposed pad;
  - U.FL and edge-SMA footprints;
  - a GND pour, a via fence and a mask web between the pads.
- **CI tiers** (GitHub Actions):
  - (a) every push, on Windows and ubuntu-24.04, in seconds and without openEMS: parser, geometry, mesh, lint, connectivity, co-sim reduction, stop-rule replay, the 2D reference against the ported KiCad line formulas, and the generic privacy checks;
  - (b) nightly: the coupons and `lpf915` at Draft through the real worker, on one Linux distribution, with openEMS built by upstream's scripts and cached by tag. It must fit GitHub's 6 h job limit. The coupon runs are also the permanent trace-impedance regression test;
  - (c) a `kicad/kicad:10.0` container runs `kicad-cli pcb upgrade` on the fixtures and on pinned KiCad demo boards. The parse must equal the KiCad 9 parse.

### 9.2 P0-A: coupons (35 µm)

- Z0 within 5 % of KiCad's line calculator, εeff within 3 % of the 2D reference, and a clean edge lint. Each coupon is fed by lumped ports at its line ends and measured by a voltage and current probe triplet at a section cut, which gives Z0 and β by `MSLPort`'s own equations, with no port parasitics. `MSLPort` itself is not used: its current probe cuts through the one-cell solid strips and read 66–113 Ω on a 49 Ω line; `CPWPort` agrees with the triplet within 0.1 %. The 2D εeff reference uses a box 45 substrate heights tall. (A-1, plan 5: controller recommendation, owner unavailable.)
- The masked variants: the shift the mask causes (masked minus mask-free) in FDTD against fit2d's 2D shift on the same mesh lines, within 0.5 % for Z0 and 1 % for εeff (proposed; P0-A may adjust them). This validates §5.3 in FDTD. The shift against the exact mask is reported as a stated mesh limit, which fit2d bounds. The 5 % and 3 % absolute checks also apply; for masked Z0, the reference is KiCad's value scaled by the 2D mask factor (masked over mask-free Z0). (A-2, plan 5: controller recommendation, owner unavailable.)
- The dense-neighbour coupon, with the same thresholds.
- The 45° and arc coupons against their axis-aligned twins: a Z0 difference above 5 % makes §5.5 refuse; otherwise it warns.
- The coupon with pads also runs as a single-trace project through `new`, `cost` and `run` (P = 2, M = 0), and must pass the validity indicators.
- It also confirms the fit2d threshold and the timestep-floor factor.

### 9.3 P0-B: `lpf915` end to end

**The run** takes `lpf915` through the whole production pipeline:
1. parser and tracer;
2. solid copper;
3. the mesh rule;
4. horizontal ports;
5. MUR×6, κ-lossy FR-4, the DC-free pulse and the new stop rule;
6. co-simulation and retune.

**Measured:**
- C_box against an empty-box run;
- the bias at n = 2 and at n = 3;
- co-simulation against `verify` at the same values (consistency), with `verify` finite and decaying under the DC-free pulse;
- the 45° CurvePort case (`lpf915-45`) against its 0° twin (`lpf915`), which decides whether the TX side joins v1;
- the "converged" branch, live.

**Pass criteria** (the P0-C criterion-1 limits, accepted by the owner for P0-B too). Co-simulation against `verify`, and the 45° case against its 0° twin, each stay within |ΔS21| ≤ 0.1 dB and |ΔS11| ≤ 0.02 at f0, |ΔS| ≤ 0.03 up to f2, and a notch shift ≤ 2 %. Every run ends "converged". The other items are reported.

**External reference.** An EMerge FEM cross-check of the layout N-port (copper, substrate and mask, no parts). Both N-ports are recombined into the chain with the same ideal part values before they are compared.
- It runs on the Windows PC only, in a separate, validation-only Python 3.13 environment, because EMerge needs Python < 3.14. EMerge is not an app dependency.
- It passes if max |ΔS| ≤ 0.03 over the band and |ΔS21| ≤ 0.1 dB at f0.
- If EMerge's own coupon results miss the P0-A references (Z0 5 %, εeff 3 %), the cross-check is "inconclusive". P0-B then passes only with a written cause that the owner accepts.

### 9.4 P0-C: the private board crop

This runs locally only. The board copy, project files, results and the P0-C report stay in a folder outside the repository.

- **Input:** a local copy of the owner's private board files.
- **Pass criteria** (accepted by the owner):
  1. **Consistency.** Co-simulation against `verify` at the as-built ideal values:
     - |ΔS21| ≤ 0.1 dB and |ΔS11| ≤ 0.02 at f0;
     - |ΔS| ≤ 0.03 up to f2;
     - null or notch shift ≤ 2 %.
  2. **Validity.** σ_max ≤ 1.02, reciprocity error ≤ 0.02, and unaccounted power at f0, less the part models' own losses (§7.4), no more than the FR-4 loss estimate + 2 %.
  3. **Sensitivity.** S21 at f0 moves ≤ 0.2 dB between the automatic reference and the next-best one. Otherwise, Stage 2 makes that choice prominent.
  4. **Convergence.** n = 2 against n = 3, and the margin doubled: ≤ 0.1 dB at f0.
- **Also:**
  - the lid on and off;
  - the research's real-board case re-run to the −60 dB port residual, with B·A⁻¹ and C_box.
- **Measured:**
  - cells, dt and the limiting node;
  - the stop time per preset;
  - the wall time of the 6-run chain at Draft and at Normal;
  - parallel throughput on an idle machine;
  - band factor 1.1× against 1.25×.
- **Verdict.** P0-C passes when criteria 1, 2 and 4 pass. If criterion 4 fails, the default mesh is refined and P0-C repeats. If criterion 1 or 2 fails, v1 takes the fallback in §7.6. Criterion 3 only decides whether Stage 2 makes the reference choice prominent.

### 9.5 P0-D: Linux

P0-A and the `lpf915` run go through CI containers (Debian 12, Ubuntu 24.04, Fedora) with upstream's build scripts, at Draft, on manual dispatch, with one job per excitation. They pass when their S matches the Windows results within the P0-C criterion-1 limits. EMerge stays on the Windows PC. Nothing is installed locally.

### 9.6 KiCad button pre-check

In an isolated KiCad 9.0.7 profile (§9.1), check that the `exec` plugin runtime accepts a `.cmd` launcher. The profile's `kicad_common.json` is seeded before any GUI start, with the API server on, so no first-run dialog appears. (A-3, plan 5: controller recommendation, owner unavailable.) If it does not, the owner chooses the fallback, for example the `python` runtime. The owner's KiCad settings are not touched.

### 9.7 Order, exit, timebox and reports

- **Order:** P0-A needs the mesh rule and the worker. P0-B needs the whole pipeline. P0-C starts only after P0-B passes.
- **Exit:** P0-A and P0-B pass on Windows, P0-D passes in Linux CI, and P0-C yields a verdict and measured wall times. The owner then sets the v1 time policy.
- **Timebox:** target 2–3 weeks, ceiling 4 weeks. At the ceiling, stop and decide with the data.
- **Reports:** a short report after each gate, P0-0 to P0-D, and after the button pre-check. Stage 1 ends with a bottom-up estimate for Stage 2.
- **Machine time** (an estimate): about 4 h to 100 h for all gates, mostly overnight. P0-C dominates it, with about 8 chain-equivalents.

---

## 10. Deferred (YAGNI)

These are not in Stage 1 or v1:
- complex targets at IC pins, unless the TX side joins v1 (§7.7);
- automatic matching of vendor S2P files by MPN or value;
- an RF switch inside the chain (in Stage 1 a switch is always a chain end);
- zone refill through `kicad-cli` (Stage 1 shows the banner);
- live attach to Flatpak KiCad (Flatpak users import the file);
- a weekly canary build against openEMS master;
- 3-port switch-state assembly;
- Debye dielectric loss;
- the reciprocity least-squares fit;
- automatic refinement driven by fit2d;
- Linux/GCC or GPU engine backends;
- a bundled openEMS or PyInstaller build;
- macOS;
- antennas and NF2FF (Stage 3);
- SI and differential pairs.

---

## 11. Risks, ranked

1. **Co-simulation accuracy on a real board is unproven.** So far there is only FDTD-internal consistency. *Mitigation:* the external reference in P0-B, the thresholds in P0-C and the written fallback.
2. **Runtime.** The 6-run chain brackets at 16 min to about 8 h. *Mitigation:* the P0-C measurements, the cost gate, the Draft preset and the owner's decision.
3. **The external reference is numerical only,** by design: there are no measurements.
4. **The stop rule is new.** Its thresholds come from two crops. *Mitigation:* replay at several decimations, and live runs.
5. **Model correctness beyond straight, axis-aligned lines:** diagonal copper, CurvePort, and the mask model, which has been checked in 2D only.
6. **Part data:** S2P availability, and the reference-plane mismatch.
7. **KiCad churn:**
   - whether `exec` accepts a `.cmd` launcher is unverified;
   - API gaps between 9.0.7 and 10.x;
   - KiCad 11 drops SWIG, which only the dev-time fixture generator uses.
8. **Linux** is exercised only in CI.
9. **openEMS 0.37.0 quirks:**
   - a keyword passed as `False` drops the options after it;
   - NaN exits as converged;
   - the custom pulse leaves the cut-off frequency unset. In-grid inductors read it unless they get an explicit C, and it then lowers their cell's capacitance;
   - runs with a custom pulse end silently;
   - the NF2FF cache (`read_cached=False`);
   - stale ABORT files and abort latency;
   - LEtype=1 instability.
10. **Licensing and privacy:** GPL notices, RFsim's MIT notices, vendor S2P files never committed, and the privacy gate.

---

## 12. Open items, resolved during Stage 1

| Item | Resolved by |
|---|---|
| Band factor default (1.1× or 1.25×) and the stop presets | P0-C |
| Timestep-floor factor (0.8), fit2d threshold (3 %) and the mask-shift tolerances | P0-A confirms them |
| Protected-set reach (3 h), growth threshold (+20 dB) and the k ≤ 0.45 check | P0-B confirms them |
| TX side in v1 | P0-B's rotated-port case |
| v1 time policy | The owner, after P0-C |
| Commit author identity for the public repository | The owner, before the first push. Every existing commit is then rewritten to that identity, so neither the old identity nor earlier text is published. Until then, commits stay local, and Linux CI (P0-D) waits |
| Publishing on PyPI, and under which account | The owner, after the first push. Until then, install from a clone |
| Where the private board files are copied from | Asked at the start of P0-C |
