# kicad-rf-studio — Stage 1 design: a validated simulation engine

- **Date:** 2026-10-16
- **Status:** design approved section by section in conversation, revised on 2026-10-19 after an independent review, and approved by the owner. On 2026-10-21 the owner confirmed one amendment to §5.4: the substrate height now counts in the cell size. On 2026-10-22, plan 5 amended §1.1, §7.6, §9.1, §9.2 and §9.6 (A-1 to A-4) as controller recommendations while the owner was unavailable; the owner reviews them. On 2026-10-24, D-45's fix amended §5.6 (A-6) and §7.6 (A-7) the same way. On 2026-10-25, P0-B's TX-side outcome amended §1.1 and §12 (A-5) the same way. On 2026-10-26, plan 6's mesh-rule calibration amended §5.4 and §12 (A-8) the same way. On 2026-10-27, Stage 2's plan 1 amended §3.2, §3.3, §3.4 and §6.1 (A-13 to A-15) the same way. On 2026-10-28, Stage 2's plan 3 amended §3.2, §3.4, §4.3 and §10 (A-16 to A-18) the same way. On 2026-10-28, Stage 2's plan 4 amended §3.4, §3.6, §9.1 and §12 (A-19 to A-21) the same way. On 2026-10-29, the pt-BR translation plan amended §1.1 and §3.5 (A-22) the same way. On 2026-10-29, Stage 3's plan 1 amended §2, §5.1 and §9 (A-23 to A-25) the same way. On 2026-10-30, Stage 3's plan 2 amended §1.1, §3.2, §3.3, §5.1, §5.5, §6.3, §6.4, §7.4, §7.5 and §10 (A-26 to A-32) the same way. On 2026-10-30, Stage 3's plan 3 amended §3.2, §3.3 and §7.6 (A-33 and A-34) the same way. On 2026-11-01, Stage 3's plan 4 amended §3.2, §5.1, §5.3, §5.4, §6.3, §6.4 and §9 (A-35 to A-40) the same way. On 2026-11-03, Stage 4's plan 1 amended §2, §5.3, §5.4, §5.6, §5.8, §6.3, §9 and §10 (A-41 to A-47) the same way. On 2026-11-03, Stage 4's plan 2 amended §3.2, §3.3, §5.1, §5.4, §5.5, §5.6, §5.7, §6.3, §6.4 and §10 (A-48 to A-53) the same way. On 2026-11-04, Stage 4's plan 3 amended §3.2, §3.3, §7.2, §7.3, §7.4, §7.5 and §7.6 (A-54 to A-57) the same way. On 2026-11-08, Stage 4's plan 4 amended §3.2, §5.3, §5.4, §5.6, §5.8, §6.3, §6.4 and §9 (A-58 to A-64) the same way.
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
| UI language | English, or Brazilian Portuguese where Windows' display language is Portuguese (Brazil) or the gettext variables name it; every user-facing string is a catalog code (A-22, pt-BR translation plan: controller recommendation, owner unavailable.) |
| openEMS | Used as-is: openEMS 0.37.0 and CSXCAD 0.7.0, installed separately, never bundled in v1 |
| Simulation domain | Always a selected region, never a whole board, for the matching chain. An antenna project (Stage 3) simulates the whole board, every copper layer, the substrate, the mask and the lid, in an air box (A-26, Stage 3 plan 2: controller recommendation, owner unavailable.) |
| Defaults | Safe automatic defaults. In Stage 1 every default is written to `project.json`, which serves as the advanced settings; Stage 2 adds an advanced panel |
| Stackup | From the board file, or a confirmed preset. The first preset uses JLCPCB's published data |
| Copper weight | Only 1 oz (35 µm) is validated |
| Part data | Users keep a local folder of vendor S2P files. The app never ships them |
| Hardware | None. Everything runs on the PC: no fabricated boards or coupons, no VNA, no lab measurements. All references are numerical |
| Architecture | Our own thin core, one CLI orchestrator and worker processes. In Stage 2, a PySide6 GUI client that never imports openEMS. No fork of an existing tool, and no GUI hosted inside KiCad |
| Order | Validate first (this spec), build the GUI afterwards |
| KiCad | Version 9 minimum; reads KiCad 9 and 10 files |
| Default v1 scope | The output chain: RF switch common port → DC block → pi low-pass → coaxial connector, under a shield lid. TX-side matching stays out of v1: P0-B's rotated-port case failed on 2026-10-25 (§9.3) |
| Time policy | Whether Draft or Normal accuracy is the default is decided after the Stage 1 measurements |
| Fallback if the private-board gate fails | Keep the instant retune, labelled "relative / what-if", and offer a full verification run of the final value set (§7.6). The label is shown from the start, until the gate passes (A-4) |

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
| 3 | PCB antenna placement, with relative results (PML, NF2FF) | `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md` (A-23, Stage 3 plan 1: controller recommendation, owner unavailable.) |
| 4 | Signal integrity of a net or a differential pair: the TDR, mixed-mode S and crosstalk, with relative results | `docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md` (A-41, Stage 4 plan 1: controller recommendation, owner unavailable.) |
| Later | EMC, a GPU engine, a bundled installer | — |

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
| `kicad-rf-studio compare BASE VARIANT [-o PATH]` | Compares two antenna projects' or two signal-integrity projects' full simulations: writes compare.csv and compare.png, prints the deltas, each resolved or not, and refuses two projects whose settings fingerprints differ (A-34, A-57) |
| `kicad-rf-studio preview PROJECT` | Has the worker write `model.xml` without building the operator, then opens it in AppCSXCAD |
| `kicad-rf-studio setup-openems DIR` | Windows only: installs the openEMS and CSXCAD wheels from the official package into the app's environment and records CSXCAD_INSTALL_PATH |
| `kicad-rf-studio calibrate` | Re-runs the speed calibration. It also runs automatically before the first `cost` or `run` |
| `kicad-rf-studio install-kicad-plugin [--kicad 9.0\|10.0] [--remove]` | Writes the KiCad toolbar button, an exec plugin (`plugin.json`, a launcher holding this environment's Python, and its icons), into `plugins/kicad-rf-studio` of each KiCad 9.0 and 10.0 documents folder that exists, honouring KICAD_DOCUMENTS_HOME, or of the one named; `--remove` deletes it. It never edits KiCad's settings, and prints the one step left: turn on the KiCad API under Preferences › Plugins, then restart KiCad. (A-17, Stage 2 plan 3: controller recommendation, owner unavailable.) |

**Antennas** (Stage 3): `new BOARD --start REF.PAD --antenna REF --band F_LO:F_HI` writes an antenna project, with `--antenna` in place of `--end` and the band in place of `--f0` and `--harmonics`; `cost`, `run`, `retune` and `preview` work on it as on a v1 project. (A-32, Stage 3 plan 2: controller recommendation, owner unavailable.)

**Antenna comparison** (Stage 3): `verify` works on an antenna project with part ports (§7.6, A-33), and `compare BASE VARIANT [-o PATH]` compares two antenna projects' full simulations, each project's run when no part is on its chain, else its verify of the last run at the values project.json holds; like `retune`, it uses a project's results only while its model-spec hash is unchanged (§7.8). compare.png overlays their S11 and, where both have one, their efficiencies and cuts; the lines and compare.csv give the resonance shift in MHz and in % of f0 where both have their lowest |S11| at or below −6 dB inside the band, the −10 dB bandwidth's change, Δη_tot in dB at f_lo, f0 and f_hi and the peak gain's change at f0, each resolved above 0.3 % of f0 for a frequency or 0.2 dB for an efficiency or a gain, which gate P3-D kept. It refuses two projects whose settings fingerprints differ. (A-34, Stage 3 plan 3: controller recommendation, owner unavailable.) Three times the model's measured noise floor (the same verify twice, the board shifted by one fine cell, and the even parts of the antenna moved by ± one fine cell: 0.029 % and 0.029 dB) lies under those thresholds. The moves' odd part, the antenna's sensitivity to its position (0.56 % of f0 per 0.3 mm on the 2.4 GHz fixture's pi variant), is physics that compare resolves, not noise (`docs/validation/2026-11-01-p3-d.md`). Gate P3-E's ground pour inside the antenna's clearance shifted the resonance by −3.62 %, resolved at 12 times the threshold (`docs/validation/2026-11-01-p3-e.md`). (A-39, Stage 3 plan 4: controller recommendation, owner unavailable.)

**Signal integrity** (Stage 4): `new BOARD --start REF.PAD --end REF.PAD --interface NAME` writes an SI project, the interface (usb2-hs, 100base-tx, se50, or custom with `--f-max F` and `--target OHMS`) in place of `--f0`, with `--pair` (the partner by KiCad's pair rule or a DP/DM alias) or `--pair-with REF.PAD:REF.PAD`, and `--victim REF.PAD:REF.PAD` up to twice, each line on nets of its own; `cost`, `run` and `preview` work on it as on a v1 project, `retune` without values rewrites its layout file, and `verify`, `compare` and the retune of part values come with its results. (A-50, Stage 4 plan 2: controller recommendation, owner unavailable.)

**Signal-integrity results** (Stage 4): `retune`, `verify` and `compare` work on an SI project as on an antenna project. compare reads each project's run when no part is on its lines, else its verify of the last run at the values project.json holds; compare.png overlays their TDRs, every curve's levels marked, and their mixed-mode S, and its lines and compare.csv give the TDR's lowest and highest levels between the launches (marked "short" when either lies on a feature shorter than two resolution lengths), Sdd21 (S21) at the marker and at f_max, the worst Sdd11 (S11) and Scd21 up to f_max, the skew and each victim's NEXT and FEXT peaks, each resolved above 2.2 Ω on a differential TDR level and 1.1 Ω on a single-ended one, 0.05 dB on Sdd21, 0.5 dB on the rest where the higher of the two levels stands above −50 dB, Scd21's above its own floor of −37.7 dB, and 1 ps on the skew: the design's values where gate P4-E's measured noise lay under a third of them, the differential and single-ended TDR thresholds three times that noise (`docs/validation/2026-11-07-p4-e.md`); by ruling R-13, DB stays 0.5 dB and Scd21, zero by symmetry on a symmetric pair, takes a floor of its own at three times the null edit's Scd21 noise amplitude, as P4-E's computed 85.7 dB came from that noise alone. Gate P4-F resolved the neck-down's highest TDR level by 7.14 Ω, at least three times the differential threshold, the neck run's own level marked short, and the plane gap's Scd21 by 17.67 dB (`docs/validation/2026-11-08-p4-f.md`). (A-63, Stage 4 plan 4: controller recommendation, owner unavailable.) compare refuses an antenna project against an SI one. (A-57, Stage 4 plan 3: controller recommendation, owner unavailable.)

**Stage 1 never prompts.** Whatever this spec calls asked or confirmed comes from a `new` option or a `project.json` field, and `run` refuses while a required value is missing.

**Run folders given by the caller.** `cost`, `run` and `verify` take `--run-dir DIR`: the run folder to use instead of a new one in the data folder, made at the start (a relative DIR is read from the working folder; one that cannot be made or already holds a run is refused). With it, `cost` writes every line as an event there from its first. The first-use calibration runs inside the command's run folder, in `calibrate/`, and that folder's `STOP` stops it. Stage 2's GUI starts these commands detached, with a new folder each time. (A-14, Stage 2 plan 1: controller recommendation, owner unavailable.)

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
  - the results: the run folder, which holds the waves of each excitation, C_box for each part port, and the verdicts;
  - an antenna project (Stage 3) is schema 2 with `"kind": "antenna"`, without the harmonics and the band factor, and with the band, the antenna and its join pads, the air gap, the boundary and the far-field frequencies and angle step; v1 projects stay schema 1 (A-32).
  - an antenna's results and verify record a settings fingerprint, which `compare` requires to be equal: the preset, mesh, region, band and f0, T_max, air gap, boundary, far field, stackup, lid height, start pad, copper model and the versions of the app and of openEMS (A-34).
  - an SI project (Stage 4) is schema 3 with `"kind": "si"`, without f0, the harmonics, the band factor and the chain, and with the interface, `f_max_hz`, the link's rise time `rise_s`, the marker `marker_hz`, the target `target_ohm` and its tolerance, the dielectric model (lossless or debye), the stop window `window_s`, `mesh.max_cell_mm`, the lines (each its role, measured or victim, and its chain in the chain's shape) and the pair; its ports run P start, N start, P end, N end, then each victim's start and end, the part ports after them (A-50).
  - an SI project's results record its route (the 2D εeff of its distance axis, the measured route's length and its loss estimates) and, with its verify, a settings fingerprint, which `compare` requires to be equal: the preset, the mesh's n and reach (not max_cell_mm, which follows the lines' 2D εeff), the region, interface, f_max, the link's rise time, the marker, the target, the stackup, the dielectric model, the lid and its height, the external ports' signal pads and the versions of the app and of openEMS (A-57).
- **Run folders** live in the per-user data directory, never in the system temp directory:
  - Windows: `%LOCALAPPDATA%\kicad-rf-studio\runs\`;
  - Linux: `$XDG_DATA_HOME/kicad-rf-studio/runs/`.

  A run folder holds the model spec, `events.jsonl`, a `STOP` file when a stop is requested, and one folder per job, because openEMS runs inside its own folder. A job folder holds `job.json`, the log, openEMS's files and `waves.npz`.
- **Lock:** one per project, `project.json.lock` next to the project file, so two runs of one project never overlap.
- **Settings:** a per-user `settings.json` next to the run folders holds the openEMS folder and the speed calibration.
- **`events.jsonl`.** One JSON object per line: `{"t", "kind": progress|verdict|cost|result|message|end, "job", "code", "params"}`. The events carry message codes, never text, so they stay language-neutral and are translated only when displayed. A `cost`, `run` or `verify` that has a run folder by its end, the one given with `--run-dir` (§3.2) or one it made, ends it with an `end` event however it ends, short of a hard kill: code `I_END`, with `exit_code`, `command` and `project` (the project file's resolved path), after a `message` event for any refusal or internal error it printed on stderr. So a refusal before the lock and a stop during setup leave a trace in a given folder, and a restarted GUI finds a project's last cost and runs. (A-13, Stage 2 plan 1: controller recommendation, owner unavailable.)
- The exact fields of `job.json`, the model spec and the events, the CLI exit codes and the run-folder names are fixed in the implementation plan.

### 3.4 Dependencies and install

- **Dependencies:** numpy, scipy, h5py, matplotlib, shapely and scikit-rf. Stage 2 adds `PySide6-Essentials>=6.10.1,<7` (6.10.1 is the first with Python 3.14 wheels; Essentials only, so no QtCharts or Addons) and `kicad-python>=0.8,<0.9` (0.8 is the first line that installs on Python 3.14; only the KiCad button's helper and the GUI's refill import it, never the command line or the worker), as core dependencies with no extra. (A-15, Stage 2 plan 1; A-16, Stage 2 plan 3: controller recommendations, owner unavailable.)
- **openEMS and CSXCAD** are not on PyPI, so they are never declared as dependencies.
- **Windows:**
  - The official openEMS wheels need Python 3.13 or 3.14.
  - Install steps, as the README gives them:
    1. `py -3.14 -m venv "%LOCALAPPDATA%\kicad-rf-studio\venv"`: a venv of the app's own, in its per-user data folder (§3.3);
    2. `pip install <source>`: a tagged release's source zip on GitHub once the repository is published, or a clone until then (publishing on PyPI is an open item, §12);
    3. `kicad-rf-studio setup-openems <openEMS dir>`;
    4. `kicad-rf-studio install-kicad-plugin` (§3.2), then, in KiCad, Preferences › Plugins › Enable KiCad API and a restart. No installer script wraps these steps in Stage 2. (A-21, Stage 2 plan 4: controller recommendation, owner unavailable.)
  - Step 3 wraps `pip install --no-index --no-deps --find-links <dir>\python openEMS CSXCAD`. `--no-index` stays, because both names are unclaimed on PyPI and dropping it invites dependency confusion.
- **Linux** (tested only in CI containers):
  - Debian 12, Ubuntu 24.04 and Fedora, each with its system Python (≥ 3.11).
  - openEMS comes from upstream's `install_deps.sh` and `update_openEMS.sh <prefix> --python`. The script runs with the app's venv active, so that the bindings land in it; otherwise the script creates its own venv. The GUI build stays on, so that AppCSXCAD exists.
  - The README's steps clone upstream's openEMS-Project at v0.37.0 and run its `install_deps.sh` first, the one step that needs admin rights; then they make the venv at `~/.local/share/kicad-rf-studio/venv`, build openEMS into `~/.local/share/kicad-rf-studio/openEMS` with that venv active and without sudo, and end with `kicad-rf-studio install-kicad-plugin`, as on Windows. (A-21, Stage 2 plan 4: controller recommendation, owner unavailable.)
- **Version check:** before any command that starts a worker (`cost`, `run`, `verify`, `preview`), a subprocess checks that openEMS is at least 0.37, and the app warns outside 0.37.x.

### 3.5 Translations

- stdlib gettext, with one catalog shared by the core, the CLI and later the GUI.
- Messages carry a code plus parameters, and the English template is the msgid.
- Babel is a dev-only tool for extracting and compiling the catalogs, because the Windows Python ships no `Tools/i18n`.
- The language is the gettext variables' when one is set, else Windows' display language (Portuguese (Brazil) gives pt-BR), else English. A word passed as a parameter is a `T_` code of the catalog, rendered with its message. The catalog's sources are `po/` at the repo's root, and the compiled `.mo` is committed under the package's `locale/`; `tools/catalog.py` writes both with Babel, pinned in the dev extra. (A-22, pt-BR translation plan: controller recommendation, owner unavailable.)

### 3.6 Licence and notices

- GPL-3.0-or-later. openEMS is GPL-3.0-or-later and CSXCAD is LGPL-3.0-or-later.
- An SPDX header in every source file.
- A NOTICE file lists every third-party piece, with its licence:
  - RFsim (MIT): the package-parasitic presets, the outer-wall rule and the test-board pattern, if used;
  - formulas ported from KiCad's line calculator for the tests (GPL);
  - anything taken from gerber2ems (Apache-2.0);
  - the copy of CSXCAD's `SmoothMeshLines` (LGPL-3.0-or-later).
- NOTICE also names the runtime dependencies, which kicad-rf-studio does not include (pip installs them; openEMS and CSXCAD come from `setup-openems` or the user's build), each with its licence, as the GUI's About box lists them. Since it conveys none of them, Qt included, the LGPL's conveying duties start only with a build that bundles them, which §10 defers. (A-19, Stage 2 plan 4: controller recommendation, owner unavailable.)
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
- **Live refill** is the KiCad button's action "Refill zones and save in KiCad" (Stage 2): after a confirmation, since the save also writes every unsaved edit, it refills every zone and saves the board through kicad-python, and the board is read again. (A-18, Stage 2 plan 3: controller recommendation, owner unavailable.)
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
- **The antenna boundary** (Stage 3): a model spec written for an antenna holds `"boundary": "pml_8"`: PML_8 on all six faces, its 8 cells added outside the air box at the outer cell size. A spec without the key, as every v1 spec is, keeps MUR on all six faces, so the two are never mixed. A setup gate, E_METAL_IN_PML, refuses a model with metal, dielectric or a lumped port within the PML or the 2 cells just inside its inner edge. (A-24, Stage 3 plan 1: controller recommendation, owner unavailable.)
- **The antenna's region** (Stage 3): the measured region takes the ROI's place: the bounding box of the antenna footprint's copper (its netless copper takes the feed pad's net), of the chain from the start pad to the antenna's feed pad and of the port, grown by `region.expand_h` substrate heights, 6 by default, the protected set's reach. The cell d comes from the feed network's tracks and sections, as in v1; the antenna's copper gets the rule's edge lines. A short or an open inside the measured region is a gate and elsewhere on the board a warning, except the antenna's own feed-to-ground join through the pads `antenna.join`, which `new` records and which the port-short check also accepts by cutting the PEC edges at the mesh nodes within one cell of those pads. The walls are the board's box, its outline and copper, grown by one coarse cell; the air gap `air_gap_mm`, λ/4 at f_lo by default, runs from them to the PML's inner edge, graded at 1.3 up to λ(f2)/20 in air; nothing reaches a crop. The shield over most of the board gets its lid at the project's lid height, and a warning names any other. The rest of the board's parts are never ports: a capacitor whose capacitive reactance, less its package's inductive one, is at most Z0/5 at the pulse's centre is copper; a resistor or capacitor that v1 puts in the grid is in the grid inside the measured region and open outside it; any other part is open. (A-27, Stage 3 plan 2: controller recommendation, owner unavailable.)
- **The antenna's absorber** (Stage 3): gate P3-C ran PML_8 free to max(T_max, 3 × the stop time) on both fixtures (30 and 79 ns) with no energy rise (0.00 dB), so PML_8 stays. MUR at λ/2 ran on the 2.4 GHz fixture free to 3 × T_max (90 ns) and rose 21.2 dB, as P3-A's MUR twin rose 16 dB, so it is no fallback for a PML failure. The air gap stays λ/4: λ/2 moved the 2.4 GHz fixture's resonance by at most 0.0034 % and its radiation efficiency by 0.007 dB, and D by at most 0.042 dB on either fixture (`docs/validation/2026-11-01-p3-c.md`). (A-36, Stage 3 plan 4: controller recommendation, owner unavailable.)
- **The SI region** (Stage 4): the ROI is the bounding box of every line's copper, its parts' pads, its ports' pads and their kept reference pads, grown by the protected set's reach, 6 substrate heights of the thinnest dielectric next to the lines' copper layers, inside MUR walls on all six faces as v1's; `new` picks the parts and the lid from that ROI. A victim whose end pads the ROI of the measured lines alone, their references left out, does not cover is refused. (A-51, Stage 4 plan 2: controller recommendation, owner unavailable.)
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
- **Antennas** (Stage 3): an antenna project's `copper` is "solid", this section's copper, or "sheet": every copper layer a zero-thickness PEC sheet at its dielectric face, the masks resting on it, for the whole model. Gate P3-C compared them on both fixtures at mesh n 2, and sheet failed and is not offered. It moved the 2.4 GHz fixture's resonance by 0.27 %, within the 0.5 % limit, but shifted the 915 MHz meander's response by 0.87 % in band, as this section's narrow-gap evidence predicts for the meander's closely spaced turns. With sheet copper openEMS's timestep was 1.86 times solid's (2.143e-13 against 1.150e-13 s on the 2.4 GHz fixture), the copper's thickness no longer resolved (`docs/validation/2026-11-01-p3-c.md`). A project may still set "sheet", at its own risk, where every gap stays wide: on a coplanar gap under 30·t this section's evidence (a sheet read Z0 8.7 % high on a 50 Ω GCPW) holds. (A-35, Stage 3 plan 4: controller recommendation, owner unavailable.)
- **Signal integrity** (Stage 4): an SI project's copper is solid, never openEMS's conducting sheet, which read a coupled pair's Zdiff 11 % high in the Stage 4 research's probe and takes its thickness in metres whatever the drawing unit. Its dielectric is lossless, or a Debye fit of the stackup's εr and tan δ at 1 GHz in the Djordjevic–Sarkar manner: four poles 0.8 decade apart, from f_max·10^−2.2 to f_max·10^0.2, fitted from f_max/100 to f_max (tan δ within 3.2 % of the stackup's on FR-4), each Δε positive, ε∞ at least 1 and no DC loss, built as CSXCAD's CSPropDebyeMaterial. This section's constant κ is never used for SI: it gives a flat loss and a DC leakage. (A-42, Stage 4 plan 1: controller recommendation, owner unavailable.) A Debye request on a dielectric whose loss tangent is 0 runs it lossless and says so (W_SI_DEBYE_NO_LOSS); a loss tangent the board leaves out reads KiCad's 0.02. Gate P4-D ran a 100 mm line lossless and with Debye: the Debye run's insertion loss less its lossless twin's, which holds the walls' and radiation's, left max(0.05 dB, 5 %) of scikit-rf's MLine dielectric loss with Djordjevic–Sarkar from 0.1 GHz to f_max (worst 4.865 of the limit at 9.985 GHz), with no DC loss above 0.00123, its slowest pole's tail included; a Debye cell weighs 108.8 plain cells at 4 threads, since openEMS 0.37 updates Debye materials on one thread, so the USB 2.0 fixture would run 32.95 times slower (predicted): the default is lossless, Debye an option. A run with Debye refreshes no calibration level (`docs/validation/2026-11-07-p4-d.md`). (A-59, Stage 4 plan 4: controller recommendation, owner unavailable.)

### 5.4 Mesh

- **Protected set:**
  - the measured nets;
  - their reference copper and vias within 6 substrate heights (P0-B raised the reach from 3 on 2026-10-25, D-37) (A-8, plan 6: controller recommendation, owner unavailable);
  - the part pads;
  - the port boxes.
- **Rule for the protected set:**
  - one cell size d for the whole set: the smallest width or gap of the measured nets, or the substrate height h under them, divided by n, with n = 2 (standard) or 3 (fine), capped at 0.9·λ_min/20. The height counts because a strip's fringing field spreads over about h: a 3 mm microstrip on 0.71 mm meshed at d = w/2 read Z0 5.4 % low;
  - at solid-copper edges, lines sit d/4 inside and 3d/4 outside. A slot edge, one that faces metal across a gap of at most 4d, has its inside line d/6 deep instead of d/4, in every cell it serves where the rule puts d/4, and keeps its outside line 3d/4 out. Its axis keeps the d/4 lines wherever the slot line would fail the edge lint or the d/3 merge. One pre-registered search chose these values over 48 candidates, against plan 2's ratchet of 2142 board rows and 246,064 synthetic axes, and P0-A's FDTD re-check passed on 2026-10-26 (A-8, plan 6: controller recommendation, owner unavailable);
  - every feature is filled at d or finer.
- **Everything else:** vertex lines are clustered to a minimum cell, then graded with `SmoothMeshLines` at a ratio of 1.3 or less.
- **z:** exactly one cell across each copper thickness. Outside each copper face, dz0 = max(t_m, min(d/3, h/4)), graded ×1.3, where t_m is the mask thickness.
- **Collisions:** unprotected lines move first. If two protected patterns collide, they share one pattern, and fit2d checks it.
- **Merging:** in-plane only below d/3, in z only below dz0/3. Protected lines never move.
- **Quantisation:** every coordinate and mesh line goes to 1e-6 mm. The XML preview's 7 significant digits affect only the display.
- **Validity:** the rule is validated for 35 µm copper only.
- **Antennas** (Stage 3): the antenna's mesh n is 2. On both fixtures n 2 lies within 1 % of the finest mesh's resonance: the 2.4 GHz fixture's sequence oscillates within 0.58 % of n 4, and the 915 MHz meander, whose resonance lies above its simulated grid, sits within 0.52 % of n 4 by its fitted response shift. So the cell d taken from the feed network alone stands, and the copper models were compared at n 2. At n 3 and 4 the 2.4 GHz fixture's 0.6 mm stub reads 4–5 % high from a shared edge cell, at most 0.06 % on the resonance, and its P3-C runs set gates.fit2d_limit 0.05. A staircased 45° track at n 3 or more takes openEMS's timestep under the dt floor (the meander's read 0.72 and 0.63 of its reference at n 3 and 4), so such a project lowers gates.dt_floor to refine its mesh (`docs/validation/2026-11-01-p3-c.md`). (A-35, Stage 3 plan 4: controller recommendation, owner unavailable.)
- **Signal integrity** (Stage 4): an SI project's d and reach take the thinnest dielectric next to any copper layer its lines use, above or below, not the top layer's alone. Its mesh rule fills at d only the copper edges' patterns and a margin around each via. Between them, inside the protected extent, the cells grade at 1.3 up to max_cell, λ_eff(f_max)/40 by default, and outside the extent up to the coarse cell. On a synthetic 100 mm straight pair the rule placed about 270 lines along the run where the d fill placed about 1,370, and the edge lint passed. Gate P4-C compares it with the d fill, which stays if it fails. The edge lint and fit2d apply unchanged, and an SI project's gates.dt_floor defaults to 0.6, against v1's 0.8, since a staircased 45° track at n 3 read 0.72 of its reference (A-35). (A-43, Stage 4 plan 1: controller recommendation, owner unavailable.)
- **The SI mesh rule's margins** (Stage 4): d fills ±1 mm around a measured net's via and a rod's own radius around any other solid rod, on each axis by the rod's own coordinate, and the copper bounds of every staircased track. max_cell is λ/40 at f_max in the largest εeff of the lines' straight sections, solved without the mask; `mesh.max_cell_mm` null keeps this section's d fill. On 2026-11-03 the USB 2.0 fixture's mesh held 2.07 M cells (230 × 117 × 77) against 3.75 M (402 × 121 × 77) with the d fill (`docs/validation/2026-11-03-si-first-run.md`). (A-53, Stage 4 plan 2: controller recommendation, owner unavailable.)
- **The SI mesh after the gates** (Stage 4): gate P4-B ran its 90 Ω and 100 Ω microstrip pairs and its coupled stripline at mesh n 2 and 3. Each Zdiff plateau read within 0.0244 % of fit2d's coupled value on the run's own mesh, and the FDTD's own move from n 2 to n 3, net of fit2d's, was at most 0.0027 %, so n 2 stayed; fit2d's own move and each n's error against the exact cut are recorded. Gate P4-C compared the SI rule with the d fill on a straight and an L-shaped pair: the d fill stays, `mesh.max_cell_mm` null by default. λ/40 read |ΔS| 0.0130 and 0.0326 and λ/80 0.0181 and 0.0389 against the d fill; the Yee phase error alone would allow 27.9 mm of route at λ/40 and 134.9 mm at λ/80 at 10 GHz, but the launches and the corner add a term no λ rule removes. Its step lines read their plateaus within 1.04 % and the reflection within 0.0024. A staircased 45° pair, a 33 mm diagonal between straight runs, read −2.27 % (90 Ω) and +5.35 % (100 Ω) from its axis-aligned twin at n 2: the 45° rule stays the owner's, W_STAIRCASED a warning (B3′, its n 3 run, needed the owner's go, which did not come). Shared mesh lines change no code: p4e_gapp's run edge lies 25 µm from its pads' and fit2d read it at 0.78 % on the d fill (0.67 % on the λ/40 mesh), and fit2d and the edge lint block what such edges spoil; a merge or an exemption is the owner's. VIA_MARGIN_MM stays unvalidated against the d fill: no gate pair crosses a via (`docs/validation/2026-11-06-p4-b.md`, `2026-11-07-p4-c.md`). (A-58, Stage 4 plan 4: controller recommendation, owner unavailable.)

### 5.5 Mesh gates

Only the edge lint first tries one automatic re-mesh; the other gates block directly. Every failure message says what to do next.

- **Edge lint**, on the protected set's in-plane copper edges. It fails when:
  - a line sits on the edge;
  - the nearest inside line is closer than d/8;
  - the first outside line is closer to the edge than the nearest inside line.

  Lines on edges measured −7 to −14 % in Z0. The pinned z faces of the copper are exempt. The lint's own tests include known-bad meshes: lines on the edge, and lines 1 µm inside the metal. In an antenna project (Stage 3), an edge that another copper layer's opposite edge meets within 20 µm, the metal on its other side, as on a two-layer helical antenna, is exempt from the third test, which no line can pass for both edges. The exemption is computed only for an antenna, so every v1 model is built as before. (A-31, Stage 3 plan 2: controller recommendation, owner unavailable.)
- **fit2d gate.** Each straight, axis-aligned section of a measured net is checked on the actual mesh against the 2D reference (cs2d), with the mask included in both. Above 3 % in Z0 the run is blocked; P0-A confirms the threshold. It takes about 0.1 s per section.
- **fit2d on a pair** (Stage 4): each section of a pair's line whose partner runs alongside at the cut is also checked coupled, Zdiff on the mesh against cs2d's pair, its error the larger of the odd and even modes', against the same 3 %; a partner cs2d cannot pair there leaves the line's own check alone. (A-53)
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
- **Port boxes on the mesh** (A-6, plan 5: controller recommendation, owner unavailable):
  - along the box, the ends sit on the last mesh line in the reference's copper and the first in the signal's, counting all the copper on that layer, not the pads only: the box spans the copper-free gap between them;
  - z spans the full copper thickness;
  - the width is snapped inward to lines inside both pads, less an outer line whose edge outward, at a line between the ends, has its midpoint in copper;
  - each end must touch, across the box's width, only the piece of copper that holds its own pad's witness, else the port is refused (E_PORT_BOX); this covers a part in the grid too, which the setup gate does not check;
  - so no copper lies in a box: openEMS keeps PEC on every edge whose midpoint lies in metal, except a lumped element's own edges along its axis. On `lpf915`, boxes from pad to pad had 2 to 8 shorted cells each: `verify`'s C2 and C3 acted as 8.8 pF instead of 3.3 pF, C1 gained 57–72 pF to ground, and the co-simulation's six-port was non-reciprocal by 0.16 (P0-B, D-45).
- **After setup** (setup-only plus a PEC dump), the PEC edges are grouped into connected pieces. Each port's two ends must lie in the pieces of its declared signal pad and reference pad, and those must be different pieces. The dump has no labels, and a lumped port's own end caps are PEC, so touching PEC alone proves nothing. Otherwise the run is blocked.
- An "unused primitive" on a port, excitation, probe or lumped part is an error.
- **The vertical port** (Stage 4): for an SI project only, an end pad with no same-layer reference within the reach gets a 50 Ω lumped port in z. It runs from the nearest plane toward the board's middle to the pad: the first copper layer on which one ground or power net's copper covers the pad, every layer before it bare over the pad's footprint. The port is a sheet across the pad's centre line, along its longer side. Its nodes are the plane's and the pad's faces and their far faces, which the PEC-roots gate checks as any port's. A pad with no such plane (none, an antipad, a split, or another net's copper on the way) has no vertical port. This lifts C-14's "no vertical ports" for SI alone; v1's reference order, and its refusal of a reference on another layer, stay. Gate P4-D compares it with the horizontal port on a pad coupon. (A-44, Stage 4 plan 1: controller recommendation, owner unavailable.)
- **An SI end's reference** (Stage 4): this section's same-layer reference is taken when its copper lies within the reach of the pad and the port box between them would hold no copper of another net, an unconnected pad's included; else the end gets the vertical port to the plane under its pad; with neither, `new` refuses. A micro-B connector's D+ pad, whose ground pin lies past the ID pin, gets the vertical port. A port longer than λ/20 at f_max in the stack's highest εr, pad to reference, is warned. (A-51) Gate P4-D compared the vertical port with the horizontal one on a QFN pad coupon (0.2 mm) and a two-layer 1.6 mm coupon (1.51 mm): both within 1.5 % in the TDR's plateau (1.000 and 0.9983 of the horizontal's), so the vertical port keeps the line's impedance scale at both heights; the plateau does not see the launch, which is recorded (worst |S11| −2.84 dB against −0.66 dB, the launch's TDR peak 3.09 Ω against 10.38 Ω on the tall coupon), and W_SI_LONG_PORT still warns past λ/20. The tall coupon's horizontal run reads invalid by reciprocity from a current-probe tie in openEMS's lumped port (ruling R-12), which leaves its plateau alone (A-60).

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

**Signal integrity** (Stage 4): every two-pad part on a line is a part port, whatever its value, as on an antenna's chain, but a shunt resistor of 1 kΩ or more to a supply or to ground (a pull-up), which is open and named by `new`. The parts off the lines keep this table's roles, and a capacitor whose capacitive reactance, less its package's inductive one, is at most Z0/5 at f_max/2 is copper (A-27's rule), so a decoupling capacitor joins the planes. (A-51)

**Why every RF-path part is a port.** An ideal in-grid DC block of a few tens of pF is wrong above its self-resonance, which for such parts lies near 1.5 GHz: at 2·f0 the real part is already inductive. openEMS also has no stable series C + ESL element.

**C_box.** It is computed from the edge capacitances openEMS actually assigns to the port box (operator dump), with the mask between the pads included. The dumps are VTK XML files, read with a small stdlib reader. P0-B checks C_box against an empty-box run.

### 5.8 Excitation and band

- **Pulse:** a DC-free custom excitation, `sin(2π f_m (t − t0))·exp(−(2π f_w t/3 − 3)²)·(t < 2 t0)`, with f_m = (f1 + f2)/2, f_w = (f2 − f1)/2 and t0 = 9/(2π f_w). f_m and f_w are pulse parameters, not the operating f0. f2 is passed as the first frequency argument of `SetCustomExcite`: openEMS 0.37 takes the sampling rate from that argument and ignores the second.
- **Default band:** f1 = f_fund/2 and f2 = 1.1 × the highest harmonic shown; 1.25× is an option. For 915 MHz up to the third harmonic, that is 0.458–3.020 GHz:
  - the excitation magnitude |a| is −8.1 dB at f, −0.1 dB at 2f and −12.1 dB at 3f;
  - a plane-pair mode at 3.45 GHz sits at −34.9 dB.
- **Diagnostics:** |a(f)| is shown next to every reported frequency in the detailed output.
- **T_max:** a required project field, default 40 ns, set with `SetMaxTime`. The custom pulse allocates its samples before the run, so T_max must always be set.
- **The SI pulse** (Stage 4): an SI project's pulse is openEMS's Gaussian with f0 = 0 as a custom expression, exp(−(2π·f_max·t/3 − 3)²)·(t < 2·t0) with t0 = 9/(2π·f_max), passed as v1's with f2 = f_max, so its DC point is measured. This section's DC-free pulse stays for v1 and the antennas. (A-45, Stage 4 plan 1: controller recommendation, owner unavailable.) The DC point matched the ports' copper connectivity, S = 2P − I with P the projector onto the cut space of the node-by-port incidence, within 2.1e-4 (usb2_hs_gap's; P4-D's own lossless projects at most 2.8e-5) on every lossless P4-D project and the USB 2.0 fixtures' layouts (a Debye run's DC point carries its slowest pole's tail and is judged by its DC loss), so this section's DC-free fallback is not needed (`docs/validation/2026-11-07-p4-d.md`). (A-60, Stage 4 plan 4: controller recommendation, owner unavailable.)

---

## 6. Run control (orchestrator and worker)

### 6.1 Lifecycle

1. `run` takes the project lock and creates a fresh run folder.
2. It builds the model spec once and runs the gates: the mesh gates in the orchestrator, then one setup-only worker for the timestep floor, port connectivity and unused primitives, as `cost` does. A failed gate ends the run before any job starts.
3. It creates one job per excitation: P external ports plus M part ports.
4. A worker pool runs the jobs, each in its own job folder as `<venv python> -I -u -m kicad_rf_studio.worker job.json`, with an explicit thread count and OPENBLAS_NUM_THREADS=1.
5. Every event goes to `events.jsonl`, and stdout gets the same events as translated, readable lines, except the end event, which is never printed, and the `message` event of a refusal or internal error that the command line caught, whose line goes to stderr (§3.3). (A-13, Stage 2 plan 1: controller recommendation, owner unavailable.)

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

**Antennas** (Stage 3): T_max defaults to 2·t0 + 60/f0, rounded up to a whole ns, f0 being the band's centre, and the flat window is max(5 ns, 20/f0); every other constant is v1's. (A-28, Stage 3 plan 2: controller recommendation, owner unavailable.) Gate P3-C measured the stop times and kept both. Every compared run converged before T_max (the 2.4 GHz fixture at 9.6–10.5 ns of 30, the 915 MHz meander at 14.8–15.4 ns of 79), and none ended flat. An antenna's project.json may set `flat_s`, its flat window in s, for a run that ends flat. The Normal preset matched Strict within 0.0008 % in resonance and 0.001 dB in radiation efficiency (`docs/validation/2026-11-01-p3-c.md`). (A-37, Stage 3 plan 4: controller recommendation, owner unavailable.)

**Signal integrity** (Stage 4): with the DC pulse, openEMS's field energy never decays (a soft source leaves a static charge), so the port residual is the only stop and EndCriteria stays 1e-15. The residual's window is max(2 ns, 1.5 × the longest port-to-port round trip), written only in an SI model's excitation as `window_s`, so a pulse still travelling on a long line cannot read as converged. Its flat window is 5 ns plus that window's excess over 2 ns, since a window holds the residual at its last peak for its whole length. T_max defaults to the pulse's length plus 6 of the longest round trips plus 2 ns, rounded up to a whole ns, the round trip from the route's length and the 2D εeff. The growth detector and the other constants stay. (A-46, Stage 4 plan 1: controller recommendation, owner unavailable.)

An SI project's T_max is also at least the pulse, the residual's window, the flat window and 1 ns, rounded up to a whole ns (9 ns at 10 GHz with the 2 ns window), so that a level held on a short route ends flat rather than at T_max: a 1 % level on 17–37 mm routes reads flat at 7.35–7.47 ns. (A-52, Stage 4 plan 2: controller recommendation, owner unavailable.)

**SI runs whose planes ring** (Stage 4): an SI job's openEMS runs to four times T_max; past T_max the stop rule fits a line to the port residual over its last 3 ns at every sample and lets the job run on while that line falls at least 0.3 dB/ns and reaches the preset's level by four times T_max, ending it otherwise as before (a residual flat, rising, falling slower or reaching the level later), its W_JOB_T_MAX line at the time its S ends. On Stage 4 plan 3's plane-gap variant, which rang past its 9 ns T_max, the rule let the 14 jobs of its 32 ns run and verify run to where they converged (20.5–23.5 ns), the latest projection 23.9 ns and the slopes −0.68 to −2.09 dB/ns (the 9 ns run's 8 jobs never passed T_max); gate P4-F's plane-gap run converged at 22.48 ns with no hand edit of T_max (its eight jobs at 19.79–22.48 ns). `cost` names the ceiling and its time (I_SI_COST_RING); W_SI_LONG_RUN still reads the worst case to T_max, since only planes that ring run past it. The ceiling is not in the model spec, so no model hash moves. (A-61, Stage 4 plan 4: controller recommendation, owner unavailable.)

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
- **Antennas** (Stage 3): `cost` splits the cells into board (inside the dielectric's box), air and PML (the nodes openEMS's UPML updates, 9 lines a face) and counts N − N_PML + 8.92·N_PML cells at the small-model speed of its pool level, 0.559 at one job and 0.718 at four (an unmeasured level takes the nearest lower one), times the calibration's per-job speed at that level at its threads, the cost refit's two corrections, by gate P3-A's method (`docs/validation/2026-11-01-p3-refit.md`). These two ratios are the one exception to "no numeric constants for any particular PC": P3-A measured them on the development PC, and gates P3-B to P3-E's runs refitted them: the PML weight 8.92, as the 2.4 GHz fixture's like-for-like MUR pair measured it (the pool-1 line 8.02, a cross-check), outside 6.38's 25 % band. Each level's small speed is the median of its runs' k, so the cost's prediction of openEMS's stepping time reads 0.95–1.01 of the measured at one job (the MUR run 1.01) and 0.99–1.07 at four, where it read 1.06–1.11 at one job (the MUR run 1.47) and 1.40–1.50 at four, all from the record's k and its constants before (`docs/validation/2026-11-01-p3-refit.md`). (A-38, Stage 3 plan 4: controller recommendation, owner unavailable.) An antenna run does not refresh the calibration. On 2026-10-30 the 2.4 GHz fixture's run took 25.0 min (1,502 s) against 28.2 min (1,695 s) predicted and the Stage 3 design's hope of 9–18 min; the PML held 43.8 % of the nodes, and the 35 µm copper cell set dt (`docs/validation/2026-10-30-antenna-first-run.md`). (A-29, Stage 3 plan 2: controller recommendation, owner unavailable.)
- **Signal integrity** (Stage 4): `cost` first lists the 2D table, every straight section of every line against the interface's target band with the mask: a net's Z0; a pair's Zdiff, Zodd and Zeven from cs2d's coupled pair where its partner runs alongside at the cut (a partner within 20 µm of the line's width taken at it, the 10 µm simplification's), else 2·Z0 uncoupled; with εeff, length and delay, and a victim's Z0 with no target. When the longest measured route's delay is under a sixth of the link's rise time, it says a run may not be needed. The cost lines count v1's cells at the calibration's speed, which an SI run refreshes as v1's does; an SI model runs at 0.663 times the calibration's own per-job speed until a run at its pool level measures that level (I_SI_COST_SPEED), the ratio gates P4-B to P4-F's runs refitted from the plan's provisional 0.55 (32 lossless runs, 0.506–1.279; 0.65 at pool 4 and 1.23 at pool 2, as the calibration's per-job speed is its aggregate over its pool at every pool above one); a run with Debye refreshes no level. The cost lines add the runs broken down into the measured lines' ends, the victims' ends and the part ports, and a warning past two hours that advises Draft or a shorter route. A Debye cell counts as 108.8 plain cells, the weight gate P4-D measured at 4 threads (I_SI_COST_DEBYE) (`docs/validation/2026-11-08-p4-refit.md`). (A-62, Stage 4 plan 4: controller recommendation, owner unavailable.) On 2026-11-03 the USB 2.0 fixture's 8 jobs took 26.0 min against 25.6 min predicted, on 2.07 M cells against 3.75 M with Stage 1's fill (`docs/validation/2026-11-03-si-first-run.md`). (A-48, Stage 4 plan 2: controller recommendation, owner unavailable.)
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
- **Signal integrity** (Stage 4): an SI project's retune takes an antenna's bypass syntax and refusals (§7.6, A-33) on every part of its lines, a 0R and a DNP part (`open`) included, and redraws the TDR, the mixed-mode S and the crosstalk from the closed N-port, each part port's load held at DC at its value at the grid's first point above DC (§7.3), so an S2P file must reach that point; a pull-up left open is no port, and a DNP one is stored `open`. (A-55)

### 7.3 Outputs

- S21 and S11, with markers at f0 and at each harmonic shown.
- Insertion loss, return loss and harmonic rejection, labelled "relative to the chosen source impedance".
- "Ideal schematic" next to "with layout".
- **Exports:**
  - Touchstone for the layout N-port, with its port map, and for the combined chain;
  - a PNG summary with S11, S21 and a Smith chart of S11, and a CSV summary.
- The files go to a `results/` folder next to `project.json`, and each retune replaces the previous set.
- A single trace (M = 0) has no retune: its outputs are S11, S21 and its 2-port Touchstone.

**Signal integrity** (Stage 4): an SI run's layout N-port lies on the uniform grid from DC to f_max, its DC point measured, and its chain closes the part ports as §7.2's retune does, each load held at DC at its value at the grid's first point above DC (a series capacitor's time constant lies beyond the TDR's record; an open part has no impedance at DC). Its S is renormalised to the target with s_def "power" passed explicitly (§7.7): a pair's ports through scikit-rf's se2gmm to mixed mode, the target differential and a quarter of it common; a net's ends to the target; a victim's ends stay at 50 Ω. The TDR is the step response of Sdd11 (a net's S11) through a Gaussian rise filter at the localising rise time 1.25/f_max and at the link's, summed from before t = 0, Z = Z_ref(1 + ρ)/(1 − ρ), the link's TDR and both TDTs read on the localising TDR's time axis; the far port's launch lies at twice the arrival of the measured line's TDT, where it reaches half its peak, and the first resolution length t_r·v/2 at each port is the port's own launch. The lowest and highest levels between the launches are read, each marked as no feature's impedance when it lies more than 1 Ω (0.5 Ω single-ended) off the target and its width at half its height, from the target or from its own base, is under two rise times: a feature shorter than two resolution lengths, which the lines, both plots, verify and compare mark wherever they show it. A pair's skew is its legs' TDT arrivals' difference; NEXT and FEXT are the peaks up to f_max from the measured line's start, a pair driven differentially, at each victim's first and second end. results/ holds layout.s{N}p, chain.s{P}p, si_summary.csv (the S at the target by frequency), si_tdr.csv (both TDRs and both TDTs by time, with the distance at the route's 2D εeff, its sections' length-weighted εeff with the mask) and si_summary.png; the lines give Sdd21 (S21) at the marker and at f_max, the worst Sdd11 (S11) and Scd21 up to f_max, Scc21 at the marker, the levels, the skew, the crosstalk peaks and, not in S, the copper's loss over the route's length by Hammerstad's formula for smooth copper and, with a lossless dielectric, the dielectric's, at the marker frequency and at f_max. On 2026-11-04 the USB 2.0 fixture and its plane-gap variant ran it (`docs/validation/2026-11-04-si-results.md`). (A-54, Stage 4 plan 3: controller recommendation, owner unavailable.)

### 7.4 Validity indicators

- **Passivity:** σ_max ≤ 1.02. P0 may tighten it.
- **Reciprocity:** error ≤ 0.02.
- **Loss budget:** the unaccounted power 1 − |S11|² − |S21|² of the combined chain, less the power the part models absorb themselves (ESR and S2P data, from the waves into each part port), against the expected dielectric loss: the quasi-TEM loss from εeff, εr and tanδ over each section's length. An excess above 2 % is flagged. `verify` keeps its parts in the grid, so its loss budget counts an in-grid resistor's loss as layout loss.
- **Antennas** (Stage 3) have no loss budget: radiation is their "loss" (A-32).
- **Signal integrity** (Stage 4) has no loss budget: a lossless model's missing power is the walls' and radiation's. Passivity and reciprocity apply. (A-56)

### 7.5 Stated limits

These are printed with every result:
- no magnetic coupling between part bodies;
- no interaction between part bodies and the lid;
- vendor S2P reference planes differ from the pad-gap box;
- copper is PEC, so there is no conductor loss;
- the through-crop walls absorb most of the power coupled into cut nets, and reflect the rest.

An antenna's results (Stage 3) state their own limits instead, after the label that they are relative: the board alone in free space; copper as a perfect conductor, so the radiation efficiency reads high; no enclosure, hand, battery or cable; the parts' bodies absent; the parts off the chain approximated (A-32).

An SI result (Stage 4) states its own limits after the label that it is relative: the region's crop inside its walls, with the planes' cavity resonances and no radiation of an open line; copper as a perfect conductor; the dielectric model in force, lossless, whose loss the loss lines estimate, or Debye's fit; packages, dies and connector bodies absent, a part of three or more pads its pads alone; lumped 50 Ω ports at the pads, whose launch fills the first resolution length; and the TDR's resolution, a feature shorter than two resolution lengths read as no impedance. (A-56, Stage 4 plan 3: controller recommendation, owner unavailable.)

Accuracy is reported as |ΔS| or as a null shift, never in dB at a null.

### 7.6 Verification run and fallback

- **`verify`** runs once with every part in the grid as an ideal element at its current value. S2P and ESL/ESR models are replaced by that value. Each part sits in the box of the port it replaces:
  - capacitors and resistors sit in one cell along the box's axis, at its middle, across the box's whole width, joined to its two ends by PEC fill of that width (A-7, plan 5: controller recommendation, owner unavailable; D-45: spread over the whole box, lpf915's grid capacitors kept in-band lines with Q above 200 even clear of copper). A capacitor is a classic C of C_part + the cell's own capacitance from the operator dump: a classic C replaces that capacitance instead of adding to it (measured). A resistor is R_part and keeps the cell's capacitance. The fill pieces, one cell apart, add a fringe capacitance across the part that the retune's Z_part ∥ C_box does not hold: on lpf915 about 11 fF across C1 and 6 fF across C2 and C3 (max |ΔS| about 0.003), a known difference in P0-B's report;
  - inductors use LEtype=0 in a one-cell box, joined to both pads by PEC strips, with an explicit C equal to the cell's own capacitance. Without it, openEMS 0.37's Z_FACT rule lowers that capacitance, using the excitation's cut-off frequency, which the custom pulse never sets (it reads uninitialised memory: the cell's C fell to zero in 4 of 22 runs), and the run can diverge;
  - the k check, k = dt/(2·√(L·C)) ≤ 0.45, makes sure the time step resolves each inductor cell's resonance. An isolated cell is stable up to k = 1, but in the grid, at openEMS's own dt, runs diverged from k ≥ 0.49. Real parts read k ≈ 0.003–0.03. If a part fails it, `verify` refuses and names the part;
  - LEtype=1 is never used, because it is unstable in 0.37.
- Its result is compared with a retune at the same ideal values: |ΔS| at f0 and up to f2. It checks the layout reduction, not the vendor part data, and the output says so.
- It is the consistency reference for P0-B and P0-C.
- **Until P0-C passes** (§9.4), v1 labels the instant retune "relative / what-if" and offers `verify` for the final value set; if P0-C fails, the label stays. (A-4, plan 5: controller recommendation, owner unavailable.)
- **Antennas** (Stage 3): every part on an antenna's chain is a part port, a 0R and a DNP placeholder too, a 0R starting at 0 Ω and a DNP part open (project.json's value `open`). The instant retune gives S11 at the start pad; it takes 0 Ω for a series part (`REF=0R`, any 0 in ohms, or 0 on an L or an R) and `open` for a shunt part, each with no package model, refuses 0 Ω on a part to a net off the chain, `open` on a series part and a C of 0 F, which could mean either. Where the last verify of the run's model recorded a far field, the retune adds the what-if total efficiency η_rad·P, η_rad from that verify and P the power the retune's network passes to the board: 1 − |S11|² less the parts' own loss (§7.4's terms), 1 − |S11|² for a lossless network. A run with part ports records no far field and says so. `verify` is one-port: every part in the grid at its value as an ideal part, without the package model or the S2P data, a 0 Ω part as copper over its port's box and an open part left out, in one job that records the far field, transformed as a run's is; it compares |ΔS11| at f0, the largest |ΔS11| up to f2 and, where both have their lowest |S11| at or below −6 dB inside the band, the resonance shift with the retune at the same ideal values, and writes verify.s1p, verify_farfield.csv, verify_summary.csv and verify_summary.png. On 2026-10-30 the 2.4 GHz fixture's pi variant ran it end to end (`docs/validation/2026-10-30-antenna-matching-run.md`). (A-33, Stage 3 plan 3: controller recommendation, owner unavailable.)
- **Signal integrity** (Stage 4): `verify` is v1's, every part in the grid at its value as an ideal part, a 0 Ω part as copper over its port's box and an open part left out, one job per external port; it compares the largest |ΔS| from the grid's first point above DC up to f_max and the TDR's lowest and highest levels between the launches, each marked when either lies on a feature shorter than two resolution lengths, with the retune at the same ideal values, whose loads hold at DC as the retune's, writes verify.s{P}p and records its settings fingerprint. (A-55, Stage 4 plan 3: controller recommendation, owner unavailable.)

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
  - (d) the release check, `tools/release_check.py`, by hand before a release and through `release-check.yml` on a version tag or by hand, on Windows with Python 3.14 and on ubuntu-24.04 at the declared floor: a wheel built from `git archive` of HEAD and inspected, a fresh venv's install with `pip check`, kicad-python's import and both entry points, the offscreen GUI smoke test, `plugin.json` against KiCad 9.0.7's and 10.0.7's schemas and the identifier rules, and the privacy gate's generic rules over the history and the wheel. Like tiers (b) and (c), its workflow first runs after the owner's push. (A-20, Stage 2 plan 4: controller recommendation, owner unavailable.)

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

### 9.8 P3-A: far-field sanity (Stage 3)

Stage 3's first gate (Stage 3 design §5.11), run by `tools/p3a.py`. Synthetic z-directed PEC wire dipoles in vacuum under PML_8, with no board, each fed by a 50 Ω lumped port across a 1 mm gap, run through the product's job phase at Normal and its far-field transform. The pulse spans 1.85–3.0 GHz, the far field is recorded at 2.45, 2.40 and 2.50 GHz with an over-sampling of 4, and the air gap is λ/4 at 2.40 GHz. The cases are a short dipole of 12 mm (λ/10 at f0 = 2.45 GHz) and a half-wave dipole of 58 mm. Pass: at f0, the short dipole's D within 1.76 ± 0.10 dBi and the half-wave's within 2.15 ± 0.15 dBi; at every recorded frequency, η_rad within 1 ± 0.02 on both; the half-wave's far-field box moved 2 lines inward changes D by no more than 0.05 dB; each dipole run free to 3 × T_max (90 ns) with every sample finite and its energy's rise over its running minimum at most 6 dB; every base run the stop rule ended with ABORT still writes its 12 far-field dumps, which the transform reads; and no base run's setup gate blocks. The references are `tests/fixtures/p3a/references.json`. A failure is a pipeline bug, which blocks Stage 3 until it is fixed. The gate also measures a PML cell's cost against an ordinary cell's, from a MUR twin on the same mesh run free over the same steps, and a small single-job model's speed against the calibration (Stage 3 design §5.9). Result on 2026-10-29: pass, `docs/validation/2026-10-29-p3-a.md`. (A-25, Stage 3 plan 1: controller recommendation, owner unavailable.)

### 9.9 P3-B to P3-E (Stage 3)

Gates P3-B to P3-E (Stage 3 design §5.11) ran by `tools/p3b.py`, `tools/p3c.py` and `tools/p3d.py` through the product's CLI in one gates folder, each against criteria committed before its runs (`tests/fixtures/p3b/criteria.json`, `tests/fixtures/p3c/criteria.json`, `tests/fixtures/p3d/criteria.json`), with the product's code frozen from the first run to the last.
- **P3-B, pass:** the 2.4 GHz fixture through `new` and `run` against an openEMS model of the same board written by hand (`tools/p3b_hand.py`: MUR at λ/2, its own mesh, a lumped port across the radio pads' gap). Its reference, `tests/fixtures/p3b/references.json`, was committed before the product's side ran. The resonance sat 0.070 % apart (limit 1 %), D 0.17 dB and η_rad 0.013 dB (limits 0.3 dB).
- **P3-C, pass:** both fixtures at mesh n 2, 3 and 4, a λ/4 and a λ/2 air gap, Normal and Strict, PML_8 free to max(T_max, 3 × the stop time), MUR at λ/2 on the 2.4 GHz fixture, and solid against sheet copper. Every default stands and sheet copper is not offered (A-35 to A-37). The 915 MHz meander's resonance lies above its simulated grid, so its resonance comparisons read the fitted response shift (the controller's ruling at its checkpoint).
- **P3-D, fail on its move criterion, explained:** the pi variant was verified at L1=0R, C2=0.13pF, C3=1pF. The same verify twice was bit-identical, and the board shifted by one fine cell moved under 3e-6 dB. The front end moved by ±0.3 mm moved the resonance 0.53–0.59 %, outside the moves' 0.2 % limit. Its odd part is the antenna's position (0.56 %) and its even part 0.029 %, so the thresholds stay 0.3 % and 0.2 dB (A-39).
- **P3-E, pass:** a ground pour inside the clearance moved the resonance by −3.62 %, resolved at 12 times the threshold.
- **P3-F**, EMerge as a second solver, stays the owner's.

The reports are `docs/validation/2026-10-31-p3-b.md`, `2026-11-01-p3-c.md`, `2026-11-01-p3-d.md` and `2026-11-01-p3-e.md`, and the cost refit's is `2026-11-01-p3-refit.md`. The machine time was about 33 h, within this plan's estimate of 20–82 h. (A-40, Stage 3 plan 4: controller recommendation, owner unavailable.)

### 9.10 P4-A: 2D and formulas (Stage 4)

Stage 4's first gate (Stage 4 design §5.11), in CI: `tests/test_p4a.py` runs `tools/p4a.py`'s checks against `tests/fixtures/p4a/references.json`. cs2d's coupled pair is checked against Cohn's exact zero-thickness coupled stripline at 0.1 µm copper, within 0.5 %. It is checked against Kirschning–Jansen's coupled microstrip, as KiCad 9's calculator computes it, within 3 % in Z and εeff at 1 µm, and within 5 % in Z at 35 µm on 1.0 and 1.5 mm substrates, where t/h ≤ 0.035; εeff at 35 µm is recorded, not gated (cs2d's εodd reads 4.3–5.0 % under KiCad's there). The tool holds the even/odd 4-port of a uniform lossless pair, whose identities hold to 1e-9: a homogeneous stripline's FEXT and S11 are zero at a reference of √(Ze·Zo), NEXT peaks at k at the quarter wave, and a line's S11 is the bounce series of its step's Γ. The TDR routine reads an ideal 60 Ω line as 60.0 Ω, then 50.0 Ω after its second round trip. KiCad's coupled microstrip builds on a zero-thickness single line, so its thickness terms raise Zeven and εodd as the copper thickens, where both must fall: on the fixtures' 0.2 mm stack at 35 µm cs2d reads Zeven and Zodd about 9 % under KiCad's, while an openEMS probe read cs2d's Zdiff within 1.9 %, a stated limit of KiCad's formula, recorded in the report. A failure is a code bug, which blocks Stage 4. Result on 2026-11-03: passed, `docs/validation/2026-11-03-p4-a.md`. (A-47, Stage 4 plan 1: controller recommendation, owner unavailable.)

### 9.11 P4-B to P4-G (Stage 4)

Gates P4-B to P4-F (Stage 4 design §5.11) run through `tools/p4.py` and `tools/p4b.py` to `p4f.py` by the product's CLI in one gates folder, against criteria and references committed before their runs (`tests/fixtures/p4b` to `p4f`), each referred to the 2D solve of the run's own mesh where the design names fit2d. **P4-B** runs coupled microstrip pairs of 90 and 100 Ω and a homogeneous coupled stripline at mesh n 2 and 3, their 45° twins at n 2 and a victim terminated against one cut by the walls: Zdiff within 1.5 % of fit2d's value on the run's mesh, the FDTD's own n 2 to n 3 move within 1 %, NEXT within 0.5 dB of the even/odd model of the mesh's modes on its first lobe, the stripline's FEXT at √(Ze·Zo) on its first lobe at most −40 dB, the 45° twin within 5 %; result fallback (all 20 checks pass; n 2; the 45° rule the owner's; the cut victim's refusal kept). **P4-C** compares the SI rule and its λ/80 arm with the d fill on a straight and an L-shaped pair (|ΔS| ≤ 0.01, delay within 0.5 %), and reads 50→75→50 and 50→35→50 step lines (plateaus within 1.5 % of fit2d, Γ within 0.01, delay within 2 %); result fallback (the d fill; the step lines pass; the short rule's true negative). **P4-D** compares the vertical port with the horizontal on two pad coupons, the DC point with the copper's projector 2P − I (within 0.01), and a 100 mm Debye line's loss over its lossless twin with scikit-rf's MLine (max(0.05 dB, 5 %)), and measures the Debye cell weight and the USB 2.0 fixture's slowdown; result fail on one invalid run, the tall coupon's horizontal port, by a current-probe tie (R-12; the port kept, the DC point passes, lossless stays, the Debye accuracy missed). **P4-E** measures the noise floor on the 90 Ω coupon: the same run twice, the board shifted by one fine cell and the gap moved ± d, its even part less the mesh model's where a model holds, the null edit by its spec hash, and its terminated-victim twin shifted by one fine cell for NEXT and FEXT; result widened (DIFF_OHM 2.2 Ω and SE_OHM 1.1 Ω; DB 0.5 dB and Scd21's floor by R-13). **P4-F** resolves the neck-down's highest TDR level and the plane gap's Scd21 against the USB 2.0 fixture; result pass. **P4-G**, EMerge as a second solver, stays the owner's. The reports are `docs/validation/2026-11-06-p4-b.md`, `2026-11-07-p4-c.md`, `2026-11-07-p4-d.md`, `2026-11-07-p4-e.md` and `2026-11-08-p4-f.md`, and the refit's `2026-11-08-p4-refit.md`; machine time about 46 h (P4-B about 18.2 h, P4-C 4.52 h, P4-D 11.59 h, P4-E 6.00 h, P4-F 5.78 h, each report's §6) against this plan's estimate of about 20 h expected and 42 h worst on its likely path, before its conditional runs. (A-64, Stage 4 plan 4: controller recommendation, owner unavailable.)

---

## 10. Deferred (YAGNI)

These are not in Stage 1 or v1:
- complex targets at IC pins, unless the TX side joins v1 (§7.7);
- automatic matching of vendor S2P files by MPN or value;
- an RF switch inside the chain (in Stage 1 a switch is always a chain end);
- zone refill through `kicad-cli`: the KiCad button's "Refill zones and save in KiCad" action (§4.3) takes its place (Stage 1 shows the banner); (A-18, Stage 2 plan 3: controller recommendation, owner unavailable.)
- live attach to Flatpak KiCad (Flatpak users import the file);
- a weekly canary build against openEMS master;
- 3-port switch-state assembly;
- Debye dielectric loss, except for signal integrity (§5.3, A-42);
- the reciprocity least-squares fit;
- automatic refinement driven by fit2d;
- Linux/GCC or GPU engine backends;
- a bundled openEMS or PyInstaller build;
- macOS;
- the Stage 3 design's non-goals (its §3): chip and module antennas; the enclosure, a hand or body, the battery, cables, screws and the parts' bodies; automatic placement; an instant far-field retune; two bands, two antennas or external wire antennas in one run; a 3D pattern view; absolute performance claims (A-30, Stage 3 plan 2: controller recommendation, owner unavailable);
- the Stage 4 design's non-goals (its §3): eye diagrams, masks, jitter and BER; IBIS or IBIS-AMI drivers and an ideal-driver waveform; power integrity and the PDN; radiated emission; a whole-board or whole-plane model; parts of three or more pads on the route as models; back-drilled, blind and buried vias' details; `.kicad_pro` net classes and KiCad 10's tuning profiles; absolute insertion-loss verdicts and standards' masks; segmenting a long net, and more than two ends on one line (A-49, Stage 4 plan 2: controller recommendation, owner unavailable.)

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
| Protected-set reach, growth threshold (+20 dB) and the k ≤ 0.45 check | P0-B on 2026-10-25: reach 3 h not confirmed, raised to 6 h (D-37; 6 h unchecked against a larger reach, a stated limit); growth not confirmed, a stated limit (D-38); k ≤ 0.45 confirmed (D-39) (A-8, plan 6: controller recommendation, owner unavailable) |
| TX side in v1 | P0-B's rotated-port case: not joined (2026-10-25) |
| v1 time policy | The owner, after P0-C |
| Commit author identity for the public repository | The owner, before the first push. Every existing commit is then rewritten to that identity, so neither the old identity nor earlier text is published. Until then, commits stay local, and Linux CI (P0-D) waits |
| Publishing on PyPI, and under which account | The owner, after the first push. Until then, install from a tagged release's source zip on GitHub, once the repository is published, or from a clone (A-21, Stage 2 plan 4: controller recommendation, owner unavailable) |
| Where the private board files are copied from | Asked at the start of P0-C |
