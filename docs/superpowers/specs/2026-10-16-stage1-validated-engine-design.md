# kicad-rf-studio — Stage 1 design: a validated simulation engine

- **Date:** 2026-10-16
- **Status:** design approved section by section in conversation; this document awaits the owner's review.
- **Scope:** Stage 1 of the project: the headless engine, the command-line orchestrator and the validation gates. The GUI and the KiCad toolbar button (Stage 2) get their own spec, written with Stage 1's results.

---

## 1. Purpose

kicad-rf-studio lets a hardware engineer simulate the RF parts of a KiCad board with openEMS without writing openEMS scripts.

The first workflow is **RF front-end matching**:
1. Pick an RF path on a KiCad board.
2. The app simulates the cropped layout once, with a port at every RF part.
3. L and C values are then retuned instantly, with no new field simulation.
4. The results are S11, S21, harmonic rejection and a Smith chart.

The users are hardware engineers who use KiCad and are not FDTD experts. The project is public open source.

### 1.1 Decisions this design rests on

| Topic | Decision |
|---|---|
| Use cases, eventually | PCB antennas, line impedance, RF filters and matching, EMC/SI |
| First workflow (v1) | RF front-end matching. The line-impedance check stays as an internal regression test against KiCad's line calculator |
| Import | The app reads `.kicad_pcb` directly, and KiCad may be closed. In Stage 2, a KiCad toolbar button also sends the open board and the selection |
| Licence and hosting | GPL-3.0-or-later, on GitHub |
| Platforms | Windows 10/11 and Linux; macOS best effort |
| UI language | English. Every user-facing string is translatable from day one, and a pt-BR translation follows right after v1 |
| openEMS | Used as-is: openEMS 0.37.0 and CSXCAD 0.7.0, installed separately, never bundled in v1 |
| Simulation domain | Always a selected region, never a whole board |
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

- **Line Z0** within 5 % of KiCad's line calculator, and εeff within 3 % of a 2D reference.
- **Physically valid S:** passivity, reciprocity and a loss budget.
- **Instant-retune results** consistent with full simulations, within the thresholds in §9.4.
- **Runtime** shown before every run and measured afterwards. The "minutes, not hours" promise is set only after §9.4.
- **A GUI that never freezes.** This is Stage 2, but this architecture is what makes it possible.

---

## 2. Stages

| Stage | Content | Spec |
|---|---|---|
| 1 | Headless core, CLI orchestrator, worker, validation gates P0-0 to P0-D | This document |
| 2 (completes v1) | PySide6 GUI client, KiCad toolbar button, live import through kicad-python | Own spec, written with Stage 1's results |
| 3 | PCB antenna placement, with relative results (PML, NF2FF) | Later |
| Later | SI and differential pairs, a GPU engine, a bundled installer | — |

---

## 3. Architecture

### 3.1 Units

| Unit | Responsibility | Depends on | Interface |
|---|---|---|---|
| `core.kicad` | Reads `.kicad_pcb` text into a Board (copper, pads, footprints, zones, stackup, mask) and traces the RF chain | stdlib, shapely | `load_board(path) -> Board`, `trace_chain(board, start, end) -> Chain` |
| `core.geometry` | Copper pipeline, region and walls, vias in the margin, shield lid | shapely, numpy | Polygons per (layer, net) inside the region |
| `core.mesh` | Mesh rule, edge lint, fit2d gate, timestep floor | numpy | Mesh lines in x, y and z, plus check results |
| `core.model` | Part roles and models, external ports and port boxes, excitation and band, CSX build | openEMS and CSXCAD, imported lazily | A serialisable model spec and `build_csx(spec)` |
| `core.post` | Co-simulation reduction, retune, validity indicators, exports | numpy, scikit-rf, matplotlib | Touchstone, PNG and CSV files |
| `core.project` | Project file and hashes | stdlib | `project.json` |
| `core.messages` | Message codes with parameters, and the gettext catalog | stdlib gettext | Used by every unit |
| Orchestrator (the CLI) | The only run controller: run folders, worker pool, stop rule, events, STOP/ABORT, cost, calibration | stdlib subprocess | `kicad-rf-studio <command>` and `events.jsonl` |
| Worker | One process per excitation: builds the CSX, calls `FDTD.Run` with an explicit thread count, writes the waves | openEMS, CSXCAD, numpy and h5py only | `job.json` in; waves `.npz` and a log out |

**Rules**
- The core never imports Qt.
- `core.model` imports openEMS and CSXCAD only inside functions that the worker calls. `cost` and `preview` run the worker in setup-only mode, so only worker processes ever import openEMS.
- The worker never imports scikit-rf, which pulls in pandas, nor matplotlib.
- In Stage 2, the GUI:
  - starts the orchestrator detached and tails `events.jsonl`;
  - never imports openEMS or CSXCAD;
  - can be closed without stopping a run, and re-attaches when it is reopened.

### 3.2 Command line

| Command | What it does |
|---|---|
| `kicad-rf-studio new BOARD --start REF.PAD --end REF.PAD --f0 915MHz [--harmonics 3] [--preset normal] [--stackup PRESET] [-o PATH]` | Writes `project.json` with the traced chain, part roles and models, reference terminals and every default. The user may edit it. Default output: the current directory |
| `kicad-rf-studio cost PROJECT` | Runs the worker in setup-only mode, without simulating. Reports cells, smallest cell, dt and the limiting node, predicted and worst-case time, RAM, and the dominant cost driver |
| `kicad-rf-studio run PROJECT` | Runs every excitation and writes the results into the project |
| `kicad-rf-studio retune PROJECT REF=VALUE \| REF=file.s2p ...` | Writes the combined chain (Touchstone) and the summary. No new run |
| `kicad-rf-studio verify PROJECT` | One full run with the parts inside the grid at the current values (§7.6) |
| `kicad-rf-studio preview PROJECT` | Runs the worker in setup-only mode to write `model.xml`, then opens it in AppCSXCAD |
| `kicad-rf-studio setup-openems DIR` | Windows only: installs the openEMS and CSXCAD wheels from the official package into the app's environment and records CSXCAD_INSTALL_PATH |
| `kicad-rf-studio calibrate` | Re-runs the speed calibration. It also runs automatically before the first run |

Stage 2's GUI calls the same functions, in the same order: `new`, then `cost`, then `run`, then `retune`. The GUI adds no run logic of its own.

### 3.3 Files and folders

- **`project.json`.** One file is both the project and the job spec. It holds:
  - a schema version;
  - the board path and board hash;
  - the region definition and the stackup, including the mask;
  - f0, the harmonics, the preset, the band factor and T_max;
  - the chain and the parts (reference, value, role, model);
  - the external ports, each a (signal pad, reference pad) pair;
  - the mesh parameters;
  - one hash over the ROI copper, stackup, mask and mesh parameters;
  - the results: the run folder, the waves of each excitation, C_box for each part port, and the verdicts.
- **Run folders** live in the per-user data directory, never in the system temp directory:
  - Windows: `%LOCALAPPDATA%\kicad-rf-studio\runs\`;
  - Linux: `$XDG_DATA_HOME/kicad-rf-studio/runs/`.

  A run folder holds the model spec, `job-NN.json`, the logs, `waves-NN.npz`, `events.jsonl`, a lock file and, when a stop is requested, a `STOP` file.
- **`events.jsonl`.** One JSON object per line: `{"t", "kind": progress|verdict|cost|result|message, "job", "code", "params"}`. The events carry message codes, never text, so they stay language-neutral and are translated only when displayed.

### 3.4 Dependencies and install

- **Dependencies:** numpy, scipy, h5py, matplotlib, shapely and scikit-rf. Stage 2 adds PySide6-Essentials and kicad-python.
- **openEMS and CSXCAD** are not on PyPI, so they are never declared as dependencies.
- **Windows:**
  - The official openEMS wheels need Python 3.13 or 3.14.
  - Install steps:
    1. `py -3.14 -m venv <venv>`;
    2. `pip install kicad-rf-studio`;
    3. `kicad-rf-studio setup-openems <openEMS dir>`.
  - Step 3 wraps `pip install --no-index --no-deps --find-links <dir>\python openEMS CSXCAD`. `--no-index` stays, because both names are unclaimed on PyPI and dropping it invites dependency confusion.
- **Linux:**
  - Python ≥ 3.11 and glibc ≥ 2.34 (Debian 12+, Ubuntu 22.04+, Fedora, EL9+).
  - openEMS comes from upstream's `install_deps.sh` and `update_openEMS.sh <prefix> --python`, with the GUI build on so that AppCSXCAD exists.
- **Version check:** at startup a subprocess checks that openEMS is at least 0.37, and the app warns outside 0.37.x.

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
  - anything taken from gerber2ems (Apache-2.0).
- Vendor S2P files are never committed.

---

## 4. Board import (`core.kicad`)

### 4.1 Reader

- A stdlib tokenizer: 0.21–0.35 s on a 6.4 MB panel.
- The `filter_ratio` repair and a bracket-balance check.
- Unknown tokens are tolerated.
- Nets are looked up by name, because KiCad 10 no longer writes net codes.
- Items are keyed by UUID, and coordinates map to (x, −y).
- Pad copper is placed with KiCad's ShapePos transform. This was verified at 0 nm on 1,244 pads against pcbnew.
- Reads KiCad 9 and 10 files.

### 4.2 Solder mask

From each pad's mask expansion, the board's `pad_to_mask_clearance`, the F.Mask/B.Mask graphics and zones, and the stackup's mask thickness and εr, the reader builds the mask-opening polygons.

### 4.3 Zone fills

- **Default:** the fills are used as saved.
  - A zone with no fill raises a warning.
  - A banner says: "Fills as saved — refill (B) in KiCad and save if you changed copper."
- **KiCad ≥ 10 installed:** optionally, `kicad-cli pcb drc --refill-zones --save-board` runs on a temporary copy, and the app reports the XOR-area difference. With Flatpak KiCad, it runs `flatpak run --command=kicad-cli org.kicad.KiCad …` on a copy under `$HOME`.
- **Live refill** through kicad-python is Stage 2.
- The product contains no pcbnew/SWIG code.

### 4.4 Stackup

- The stackup is parsed from the board.
- If the board has none, KiCad's default rule is pre-filled and confirmed once per board. For a 0.8 mm 2-layer board, that gives a 0.71 mm dielectric and a 10 µm mask with εr 3.3.
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
- Shunt parts that touch the chain but sit off the path are tagged.
- The result is the ordered chain plus those shunt parts.
- A self-check runs on the public `lpf915` board (§9.1).

---

## 5. Physics model (`core.geometry`, `core.mesh`, `core.model`)

### 5.1 Region and boundaries

- **The ROI** is the bounding box of the chain's nets, part pads and port pads, expanded by 3 substrate heights. The expansion can be changed in the project. On a small module the ROI may cover the whole board.
- **Walls** sit at ROI + 4 mm + 8 coarse cells, with MUR on all six faces.
- **Through-crop.** Copper, substrate and vias run through the walls. Nets are never cut at the ROI edge: an "island crop" was 2–80× worse in the research.
- **PML_8 on all six faces** is used only when no copper enters the absorber, which means antennas (Stage 3). Boundary types are never mixed per face: the per-face mix and PML_8 grew after 15–21 ns, while MUR at the outer wall stayed stable.
- **Connectivity.** A short or an open inside the fine-mesh ROI is a gate; in the coarse margin it is a warning.
- **Vias in the margin** become PEC curves snapped to the mesh. Otherwise a 0.3 mm cylinder on 2.4 mm cells touches no mesh edge and vanishes.

### 5.2 Shield lid

- **Trigger:** a footprint in the ROI that has only frame pads, or a part the user tagged as a shield.
- The lid height is asked once and stored in the project.
- The lid is a PEC plate plus walls on the frame outline.
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
  - εr and thickness come from the stackup. The default is 10 µm and εr 3.3, confirmed by the user.
  - Inside the copper-thickness z-cell, the mask fills the gaps between conductors.
  - The coat above the copper is smeared over the first z-cell dz0 with ε_h = (t_m·ε_m + (dz0 − t_m))/dz0.
  - Openings are honoured.

  In a 2D check on three lines, this model was within 0.07 % in Z0 and 0.13 % in εeff of the exact mask, with no extra z-line and no timestep cost. P0-A confirms it in FDTD. The mask moves a 50 Ω GCPW's Z0 by −2.8 to −7.8 %, more than the error budget, so it cannot be ignored.
- **Dielectric loss:** a constant κ, set at f0. This is exact for the insertion loss at f0. At the harmonics it underestimates the loss, which is conservative for rejection. A Debye fit is deferred.

### 5.4 Mesh

- **Protected set:**
  - the measured nets;
  - their reference copper within about 3 substrate heights;
  - the part pads;
  - the port boxes.
- **Rule for the protected set:**
  - cell d = min(width, gap)/n, with n = 2 (standard) or 3 (fine), capped at 0.9·λ_min/20;
  - at solid-copper edges, lines sit d/4 inside and 3d/4 outside;
  - every feature is filled at d or finer.
- **Everything else:** vertex lines are clustered to a minimum cell, then graded with `SmoothMeshLines` at a ratio of 1.3 or less.
- **z:** exactly one cell across each copper thickness. Outside each copper face, dz0 = min(d/3, h/4), graded ×1.3.
- **Collisions:** unprotected lines move first. If two protected patterns collide, they share one pattern, and fit2d checks it.
- **Merging:** in-plane only below d/3, in z only below dz0/3. Protected lines never move.
- **Quantisation:** every coordinate and mesh line goes to 1e-6 mm. The XML preview's 7 significant digits affect only the display.
- **Validity:** the rule is validated for 35 µm copper only.

### 5.5 Mesh gates

Each gate first tries one automatic re-mesh, and every failure message says what to do next.

- **Edge lint**, on the protected set's in-plane copper edges. It fails when:
  - a line sits on the edge;
  - the nearest inside line is closer than d/8;
  - the first outside line is closer than the last inside line.

  Lines on edges measured −7 to −14 % in Z0. The pinned z faces of the copper are exempt. The lint's own tests include known-bad meshes: lines on the edge, and lines 1 µm inside the metal.
- **fit2d gate.** Each straight, axis-aligned section of a measured net is checked on the actual mesh against the 2D reference (cs2d), with the mask included in both. Above 3 % in Z0 the run is blocked; P0-A confirms the threshold. It takes about 0.1 s per section.
- **Timestep floor.** The run is blocked if dt falls below 0.8 × the dt the rule predicts (P0-A confirms the factor), and the limiting node is reported (setup-only, verbose = 2). One stray 10 µm cell once made a run 5.5× longer.
- **Non-axis-aligned copper on measured nets** (45° segments, arcs). The user gets the warning "staircased, accuracy not validated" and an offer of local refinement. It is refused if P0-A shows errors above the budget.

### 5.6 External ports

- 50 Ω lumped ports between an explicit (signal pad, reference pad) pair.
- The reference is chosen automatically and always shown, in this order:
  1. a connector → its shell or GND pads;
  2. an IC pin → the nearest GND pad or exposed pad of the same footprint;
  3. otherwise → the nearest GND copper on the same layer;
  4. the opposite layer, only if nothing else exists.

  On one layout, moving a reference from the adjacent pour to the bottom layer changed |S11| from −9.1 to −4.6 dB.
- **Port boxes on the mesh:**
  - the in-plane ends sit on the last mesh line inside each pad;
  - z spans the full copper thickness;
  - the width is snapped inward to lines inside the pad.
- **After setup** (setup-only plus a PEC dump), each port's resistor edges must touch the PEC of the declared signal pad on one side and the declared reference pad on the other. Otherwise the run is blocked.
- An "unused primitive" on a port, excitation, probe or lumped part is an error.

### 5.7 Parts

Roles are assigned automatically and can be edited in `project.json`.

| Part | Role |
|---|---|
| Two-terminal part on the RF path, series or shunt | A port. Its model is the vendor S2P from the user's folder, matched by MPN, then by value and package. Otherwise, the ideal value plus the package ESL/ESR preset |
| `0R` | A copper rectangle, rotated if needed. Option: "as port" |
| DNP | Open |
| Off-path C or R in the ROI | In the grid only if SRF > 3·f_max (SRF from the S2P or the preset). Otherwise a port, or open with a warning |
| Inductor | Never in the grid. A choke is open only if \|Z\| ≥ 200·Z0 across the band, SRF included. Otherwise it is a port |
| RF switch on the path | A 2-port S2P of the selected path, between two pin ports. The unselected pin's isolation is treated as infinite, and this is stated as a limit |
| Rotated two-terminal part (not a multiple of 90°) | A CurvePort, only if P0-B's rotated case passes. Otherwise refused, with a message |

**Why every RF-path part is a port.** An ideal in-grid DC block of a few tens of pF is wrong above its self-resonance, which for such parts lies near 1.5 GHz: at 2·f0 the real part is already inductive. openEMS also has no stable series C + ESL element.

**C_box.** It is computed from the edge capacitances openEMS actually assigns to the port box (operator or PEC dump), with the mask between the pads included. It is checked once per box geometry against an empty-box run.

### 5.8 Excitation and band

- **Pulse:** a DC-free custom excitation, `sin(2π f0 (t − t0))·exp(−(2π fc t/3 − 3)²)·(t < 2 t0)`, with f0 + fc passed as the maximum frequency.
- **Default band:** f1 = f_fund/2 and f2 = 1.1 × the highest harmonic shown; 1.25× is an option. For 915 MHz up to the third harmonic, that is 0.458–3.020 GHz:
  - the excitation magnitude |a| is −8.1 dB at f, −0.1 dB at 2f and −12.1 dB at 3f;
  - a plane-pair mode at 3.45 GHz sits at −34.9 dB.
- **Diagnostics:** |a(f)| is shown next to every reported frequency in the detailed output.
- **T_max:** a required project field, default 40 ns, set with `SetMaxTime`. The custom pulse allocates its samples before the run, so T_max must always be set.

---

## 6. Run control (orchestrator and worker)

### 6.1 Lifecycle

1. `run` takes the lock, creates a fresh run folder and deletes any stale `ABORT`.
2. It builds the model spec once.
3. It creates one job per excitation: P external ports plus M part ports.
4. A worker pool runs the jobs, each as `<venv python> -I -u -m kicad_rf_studio.worker job.json` with an explicit thread count.
5. Every event goes to `events.jsonl`, and the same lines go to stdout.

**Stop.** A `STOP` file in the run folder makes the orchestrator write `ABORT` into each worker's folder. openEMS reacts at the next engine chunk: 0.6–1.1 s at 2 M cells, and 30.6 s in one measured case. During setup, only a hard kill works.

### 6.2 Engine settings

- EndCriteria = 1e-15, which switches openEMS's own criterion off. That criterion exits on NaN as if converged, and it stops on aliased energy dips. Its end messages also print only for the Gaussian excitation, so runs with the custom pulse end silently.
- `exact_endcriteria` off.
- `SetMaxTime(T_max)` always.

### 6.3 Stop rule

The orchestrator reads each worker's port probe files at every flush. Flushes come at least 4 s apart in wall-clock time, but the samples themselves are taken in simulated time, so the rule does not depend on machine speed.

| Signal | Rule | Action |
|---|---|---|
| Log energy, or any probe sample, is NaN or inf | Immediately | ABORT; the run is marked "diverged" |
| Log-energy envelope, with its window widened until it holds ≥ 4 samples | ≥ its running minimum + 20 dB | ABORT; S is invalid ("growth") |
| Port residual R(t) = max over the last 2 ns of Σ_p u_p² + (Z0·i_p)², in dB relative to its peak | ≤ the preset level, **and** the in-band S monitor max\|S(t) − S(t − 1 ns)\| ≤ the preset tolerance | ABORT; "converged" |
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

- **Cost** = runs × cells × (T_stop / dt) / aggregate speed.
- **`cost` output:** cells, smallest cell, dt, the limiting node, predicted and worst-case time, RAM (about 170 MB per million cells per job) and the dominant cost driver.
- **First-run calibration,** 20–30 s on a small built-in model:
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
- A plain numpy termination is the test oracle; the two agree to 2e-16.
- Values are ideal or, per part, an S2P file. Stage 2 adds E12/E24 snapping.

### 7.3 Outputs

- S21 and S11, with markers at f0, 2f0 and 3f0.
- Insertion loss, return loss and harmonic rejection, labelled "relative to the chosen source impedance".
- "Ideal schematic" next to "with layout".
- **Exports:**
  - Touchstone for the layout N-port, with its port map, and for the combined chain;
  - a PNG and CSV summary.

### 7.4 Validity indicators

- **Passivity:** σ_max ≤ 1.02. P0 may tighten it.
- **Reciprocity:** error ≤ 0.02.
- **Loss budget:** 1 − |S11|² − |S21|² against the expected dielectric loss plus a radiation allowance. An excess above 2 % is flagged.

### 7.5 Stated limits

These are printed with every result:
- no magnetic coupling between part bodies;
- no interaction between part bodies and the lid;
- vendor S2P reference planes differ from the pad-gap box;
- copper is PEC, so there is no conductor loss;
- the through-crop walls absorb any power coupled into cut nets.

Accuracy is reported as |ΔS| or as a null shift, never in dB at a null.

### 7.6 Verification run and fallback

- **`verify`** runs once with the parts in the grid at the current values:
  - capacitors are classic C;
  - inductors use LEtype=0 in a one-cell box, after the k ≤ 1 check;
  - LEtype=1 is never used, because it is unstable in 0.37.
- It is the consistency reference for P0-C.
- In-grid parts are ideal, so parts modelled by an S2P file cannot be verified this way. The output says so.
- **If P0-C fails** criteria 1–3 (§9.4), v1 labels the instant retune "relative / what-if" and offers `verify` for the final value set.

### 7.7 Complex targets at IC pins

Deferred until the TX side is in; the output chain is 50 Ω at both ends. When they are added, every renormalisation passes s_def explicitly ('pseudo' to Z_t, 'power' to conj(Z_t)), with a unit test on a known complex load.

### 7.8 Project file

- Reopening a project allows retuning with no new runs.
- A re-import runs again only if the ROI hash (ROI copper, stackup, mask, mesh parameters) has changed.

---

## 8. Errors and checks

| Check | Type |
|---|---|
| Board parse: bracket imbalance, unsupported version | Error, with the line number |
| Unknown REF.PAD, or no chain found between the endpoints | Error, with the nearest candidates listed |
| Missing S2P file named in the project | Error |
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

- Every message is a code with parameters, and says what to do next.
- AppCSXCAD fails on non-ASCII paths, so `preview` launches it with the job folder as the working directory and a relative file name.

---

## 9. Verification plan (Stage 1 gates)

### 9.1 P0-0: repository and safety

- **Porting.** The public repository starts empty. The research prototypes, kept in a private archive outside the repository, are ported one module at a time, each with its test. Harnesses that depend on other projects' patched code stay private.
- **Privacy gate,** in CI on every push:
  - The deny-list is stored as SHA-256 hashes of normalised tokens: company, project, user and host names, and server shares.
  - Generic regexes catch absolute drive and home paths and UNC shares.
  - The plain-text list lives only in a git-ignored local file, used to regenerate the hashes.
  - It covers code, boards and docs.
- **Fixtures** are generated once, at dev time, with KiCad 9's pcbnew in an isolated KiCad profile, and committed. The profile's KICAD_CONFIG_HOME, KICAD_DOCUMENTS_HOME, KICAD_CACHE_HOME and TEMP point at a scratch folder. The fixtures are:
  - 50 Ω GCPW and microstrip coupons, mask-free by construction, plus masked variants;
  - a dense-neighbour coupon, a 45° GCPW and an arc coupon;
  - `lpf915`;
  - sanitised probe traces for replaying the stop rule;
  - synthetic S2P files built from ideal RLC;
  - one job folder with a non-ASCII path.
- **`lpf915`,** a public synthetic board that also serves as the tutorial. It has:
  - a 0.8 mm 2-layer stackup and a 50 Ω GCPW;
  - 0402 footprints for a series DC block and a C-L-C pi, with values in the Value fields, including `0R` and `10uF/16V`;
  - one part at 45°;
  - an IC-like pad group with a GND exposed pad;
  - U.FL and edge-SMA footprints;
  - a GND pour, a via fence and a mask web between the pads.
- **CI tiers** (GitHub Actions):
  - (a) every push, on Windows and ubuntu-24.04, in seconds and without openEMS: parser, geometry, mesh, lint, connectivity, co-sim reduction, stop-rule replay and the privacy gate;
  - (b) nightly: the coupons and `lpf915` through the real worker, with openEMS built on Linux by upstream's scripts and cached by tag. The coupon runs are also the permanent trace-impedance regression test;
  - (c) a `kicad/kicad:10.0` container runs `kicad-cli pcb upgrade` on the fixtures and on pinned KiCad demo boards. The parse must equal the KiCad 9 parse.

### 9.2 P0-A: coupons (35 µm)

- Z0 within 5 % of KiCad's line calculator, εeff within 3 % of the 2D reference, and a clean edge lint.
- The masked variants against masked 2D references, with the same thresholds. This validates §5.3 in FDTD.
- The dense-neighbour coupon.
- The 45° and arc coupons, quantified against their axis-aligned twins. This decides whether §5.5 warns or refuses.
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
- co-simulation against `verify` at the same values (consistency);
- the 45° CurvePort case against its 0° twin, which decides whether the TX side joins v1;
- the "converged" branch, live.

**External reference.** An EMerge FEM cross-check of the bare-copper N-port.
- It runs in a separate, validation-only Python 3.13 environment, because EMerge needs Python < 3.14. EMerge is not an app dependency.
- It passes if max |ΔS| ≤ 0.03 over the band and |ΔS21| ≤ 0.1 dB at f0.
- If EMerge itself misses the P0-A coupon references by more than that budget, the cross-check is reported as "inconclusive" instead of pass or fail.

### 9.4 P0-C: the private board crop

This runs locally only. The board files and all results stay outside the repository.

- **Input:** a local copy of the owner's private board files.
- **Pass criteria** (accepted by the owner):
  1. **Consistency.** Co-simulation against `verify` at the as-built ideal values:
     - |ΔS21| ≤ 0.1 dB and |ΔS11| ≤ 0.02 at f0;
     - |ΔS| ≤ 0.03 up to f2;
     - null or notch shift ≤ 2 %.
  2. **Validity.** σ_max ≤ 1.02, reciprocity error ≤ 0.02, and unaccounted power at f0 no more than the FR-4 loss estimate + 2 %.
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
- **Diagnostic:** the SOL self-check, if criterion 1 fails.
- **If criteria 1–3 fail:** the fallback in §7.6.

### 9.5 P0-D: Linux

P0-A and P0-B run in CI containers (Debian 12, Ubuntu 24.04, Fedora), with upstream's build scripts. Nothing is installed locally.

### 9.6 KiCad button pre-check

In an isolated KiCad 9.0.7 profile, check that the `exec` plugin runtime accepts a `.cmd` launcher. The fallback is the `python` runtime. The owner's KiCad settings are not touched.

### 9.7 Order, exit, timebox and reports

- **Order:** P0-A needs the mesh rule and the worker. P0-B needs the whole pipeline. P0-C starts only after P0-B passes.
- **Exit:** P0-A and P0-B pass on Windows and in Linux CI, and P0-C yields a pass/fail result and measured wall times. The owner then sets the v1 time policy.
- **Timebox:** target 2–3 weeks, ceiling 4 weeks. At the ceiling, stop and decide with the data.
- **Reports:** a short report after each gate (A, B, C). Stage 1 ends with a bottom-up estimate for Stage 2.
- **Machine time:** about 4 h to 100 h for all gates, mostly overnight. P0-C dominates it, with about 8 chain-equivalents.

---

## 10. Deferred (YAGNI)

These are not in Stage 1 or v1:
- complex targets at IC pins (they come with the TX side);
- live attach to Flatpak KiCad (Flatpak users import the file);
- a weekly canary build against openEMS master;
- 3-port switch-state assembly;
- Debye dielectric loss;
- the reciprocity least-squares fit;
- automatic refinement driven by fit2d;
- Linux/GCC or GPU engine backends;
- a bundled openEMS or PyInstaller build;
- macOS beyond best effort;
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
| Timestep-floor factor (0.8) and fit2d threshold (3 %) | P0-A confirms them |
| TX side in v1 | P0-B's rotated-port case |
| v1 time policy | The owner, after P0-C |
| Commit author identity for the public repository | The owner, before the first push. Until then, commits stay local |
| Where the private board files are copied from | Asked at the start of P0-C |
