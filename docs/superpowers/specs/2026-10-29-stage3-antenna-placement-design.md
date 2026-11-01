# kicad-rf-studio — Stage 3 design: PCB antenna placement

Status: written on 2026-10-29 by the controller, right after the pt-BR translation (main at `dcad54e`). The owner is unavailable and asked not to be stopped for questions, so every decision below that the Stage 1 spec, the Stage 2 design and the pt-BR design did not already make is a controller recommendation, owner unavailable. The research behind it is in `.superpowers/sdd/stage3-research/` (git-ignored): r1 the physics, with two dipole probes run on this PC; r2 the user's workflow and the KiCad side; r3 the engine; r4 the references and gates. An independent builder read it before the commit; its three questions are settled in §5.1 (how one project gets both a retune and a far field) and §5.3 (what takes the ROI's place, the rest of the board's parts, and the copper model that sets the runtime). Amended on 2026-11-01 by Stage 3's plan 4 with the gates' results (P3-B to P3-E, `docs/validation/2026-10-31-p3-b.md` and `2026-11-01-p3-{c,d,e}.md`).

References: "Stage 1 §x" names a section of the Stage 1 spec (`docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`), and so does every § in a list or heading that names that spec; a bare § names a section of this design.

## 1. Intent and why

The Stage 1 spec's stage table names Stage 3: "PCB antenna placement, with relative results (PML, NF2FF)". The users are the same hardware engineers, and the case is an antenna printed on their own board: an inverted-F at 2.4 GHz, an inverted-F or a meander at 868/915 MHz. The vendor's application note gives a reference layout on the vendor's reference board. The user's board differs in its ground plane, its clearance, the copper and parts near the antenna, the shield lid and the matching network, and those differences move the resonance, the bandwidth and the efficiency. Stage 3 shows what they do, on the user's own board, before it is made.

The results are relative because there is no hardware (Stage 1 §1.1: every reference is numerical), and because the absolute numbers depend on things a board model does not hold: the enclosure, a hand, the battery, the cables. TI's AN043 measured a 5–10 MHz resonance shift from the coax cable's position alone. A variant run against a baseline with identical settings cancels most of the error the two share. So Stage 3's main output is the comparison: this placement against that one, this clearance against that one, and which differences are larger than the model's own noise.

Success: on a board with a printed antenna, the user gets the antenna's S11 at the radio pin against the band, its resonance and bandwidth, its radiation and total efficiency, its peak gain and three pattern cuts, a matching retune with E12/E24 snapping, and a comparison with a baseline that says which differences are resolved. Runtime is measured and recorded, not promised: with Stage 1 §5.3's solid copper, r1 estimates 9–18 min per job at 2.4 GHz (measured: one 2.4 GHz job 25 min, `docs/validation/2026-10-30-antenna-first-run.md`) and 45–90 min at 868/915 MHz on this PC, before a worst-case T_max; all-sheet copper would cut that about 1.9–2 times (its timestep 1.86–2.03 times larger than solid's), but gate P3-C did not offer it (§5.3). `cost` shows the estimate before every run, as in v1.

## 2. What is already decided (binding)

- Stage 1 §1.1: openEMS 0.37.0 and CSXCAD 0.7.0 as they are; no hardware, every reference numerical; the what-if label on the instant retune; and, from Stage 1 §3.1, the CLI and GUI never import openEMS.
- Stage 1 §5.1: PML_8 on all six faces is for antennas only, with no copper in the absorber; boundary types are never mixed per face (the per-face mix and a PML_8 with copper in it grew after 15–21 ns).
- The Stage 1 spec's §5.3 (the copper model), §5.4 (the mesh rule and the protected set), §5.6 (the port box between the signal pad and its reference copper), §5.8 (the DC-free pulse), §6.3 (the stop rule and its presets), §6.4 (the cost estimate), §7.2 (the instant retune with snapping) and §7.6 (verify): reused, with the changes below.
- Stage 2: the GUI client, the KiCad button and its handoff, cost before every run, the run folders and events.
- The pt-BR translation: every new message code is a catalog code with its pt-BR msgstr, compiled into the committed `.mo`; the catalog tests fail on a template without one.

## 3. Goals, non-goals and anti-goals

Goals:
- An antenna project from a KiCad board: the antenna footprint, the radio pin that feeds it, the band.
- The antenna's S11 and input impedance at the radio pin, its resonance and its −10 dB bandwidth against the band.
- Radiation efficiency, total efficiency, directivity, peak gain and realized gain, and the pattern in the board's three principal planes.
- The matching network retuned instantly with snapping, and verified.
- A comparison of two projects, with each difference marked resolved or not resolved.
- Every antenna result labelled relative, with its stated limits.
- v1's matching chain unchanged, its results bit for bit.

Non-goals (Stage 3 does not do these):
- Chip antennas and module antennas. Their radiator's copper is not in the board file: a chip antenna footprint has two pads, and an ESP32-WROOM footprint has pads and a keep-out. v1's matching chain still applies up to their pad.
- The enclosure, a hand or body, the battery, cables, screws and the parts' bodies (only their pads are in the file).
- Moving the antenna or searching placements automatically. Variants are board files the user edits in KiCad.
- An instant retune of the far field. Efficiency and pattern come from runs that hold the actual network (§5.7).
- Two bands in one run; two antennas and their coupling; external wire antennas.
- A 3D pattern view in the GUI. The full-sphere data is written to a file.
- Absolute performance claims.

Anti-goals:
- An antenna number shown without the relative label and the stated limits.
- A difference inside the model's noise shown as a real one.
- Any change to v1's projects, models or results.
- Copper or dielectric inside the absorber.
- A stale far-field file silently reused (openEMS's `read_cached` default).

## 4. Constraints

- openEMS 0.37.0 and CSXCAD 0.7.0 as installed (never bundled); Windows 10/11 and Linux; Python 3.14; KiCad 9 and 10 boards.
- No new runtime dependency: h5py, numpy and matplotlib are already in.
- Fixtures are synthetic boards built from KiCad's own library footprints. No vendor file (Gerber, DXF, app-note figure) is shipped; app notes are cited.
- Every new message has its pt-BR msgstr in the same commit, through `tools/catalog.py`.
- v1 projects stay at schema 1, and their model specs, hashes and output files stay byte for byte. The first plan pins that with golden tests before it changes any code.

## 5. Decisions

### 5.1 The antenna project

- **Inputs.** The board, the antenna footprint's reference, the start pad (the radio pin, or any pad upstream of the matching network, a test connector's included) and the band f_lo to f_hi, plus v1's preset, stackup and lid height. The CLI form is `kicad-rf-studio new BOARD --start REF.PAD --antenna REF --band F_LO:F_HI`, with `--antenna` in place of `--end` and the band in place of `--f0` (f0 is the band's centre; harmonics do not apply). `cost`, `run`, `retune`, `verify` and `preview` work on it as they do on a v1 project.
- **project.json.** An antenna project is schema 2 with `"kind": "antenna"`. v1 projects stay schema 1, and a build before Stage 3 refuses a schema 2 project with E_PROJECT_SCHEMA. Its fields: the board, the start port in v1's port shape, the antenna's reference, the band, the matching parts in v1's chain shape, the air gap, the boundary, the far-field frequencies and angle step, `t_max_s`, the preset, mesh and gates as in v1, the lid.
- **The chain.** v1's tracer walks from the start pad to the antenna footprint's feed pad; the parts on the way are the matching network. The antenna footprint ends the chain and is never a part. So P = 1.
- **Every chain part is a part port**, whatever its value: a 0R and a DNP placeholder included, since the network is what the user tunes (v1's roles still decide everything off the chain, §5.3). A 0R starts at 0 Ω and a DNP part starts open. So M is the number of parts on the chain, and a project whose antenna is fed straight from the start pad has M = 0.
- **One project, both results.** The run (1 + M jobs) gives S11 at the radio pin for any part values: the instant retune. The far field comes from the job that holds the network as applied (§5.5): the run's own job when M = 0, otherwise Verify. The retune accepts 0 Ω for a series position and open for a shunt position, so the antenna seen through its feed line (the network bypassed) is a retune, then Apply and Verify. A project with M = 0 has nothing to retune or verify (v1's E_RETUNE_NO_PARTS and E_VERIFY_NO_PARTS stand): its run is its far-field run.
- **Antenna footprints.** A footprint is offered as an antenna when its reference starts with AE, its library id starts with `RF_Antenna:`, or it has copper graphics. Two kinds are refused, each with its own message that points to v1's chain:
  - a module: a library id starting with `RF_Module:`, or a footprint keep-out with no copper graphics;
  - a chip antenna: an antenna footprint with pads and no copper graphics.

### 5.2 The domain and its walls (amends Stage 1 §1.1 and §5.1 for antennas)

- **The whole board.** An antenna's ground plane is half the antenna (TI's AN043: the ground's size took the bandwidth from about 250 to about 100 MHz). So an antenna project simulates the whole board outline, every copper layer, the substrate, the mask and the lid, in an air box. The selected-region rule stays for the matching chain.
- **PML_8 on all six faces**, as Stage 1 §5.1 already reserved for antennas. r1's probes ran it stable to 30 and 40 ns with nothing in the absorber.
- **The air gap** from the board to the PML's inner edge is λ/4 at f_lo by default (gate P3-C, A-36) (openEMS's documentation: "Radiating structures must be kept at a distance of λ/4 from PML"). The 8 PML lines are added outside the gap at the outer cell size. The gap is a project field.
- **A setup gate**, E_METAL_IN_PML, refuses a model with metal or dielectric within the PML plus 2 cells.
- **The far-field box** sits one line inside the PML on every face and encloses the whole board. Its centre for the transform is the board's centre.
- **MUR on all six faces** stays a project option: gate P3-C found PML_8 stable and measured MUR at λ/2 rising 21 dB within 90 ns, so it is no fallback (A-36).

### 5.3 Mesh and copper

- **The antenna group** is the antenna footprint's own copper: its pads and its copper graphics. It joins the measured copper, so Stage 1 §5.4's rule meshes it fine, with the feed network, the matching parts' pads and the ground edge within the rule's reach. Netless antenna copper takes the feed pad's net, and W_NETLESS_COPPER is not raised for it.
- **The feed-to-ground join.** An inverted-F joins its feed to ground through its own copper by design (KiCad's `Texas_SWRA117D_2.4GHz_*` declares the net tie). The connectivity gate and the port-short check accept that join for the antenna group and nowhere else, and project.json records it.
- **The measured region takes the ROI's place.** The antenna group, the chain from the start pad to the antenna, and their reference copper within Stage 1 §5.4's reach form the measured region. The fine mesh and the connectivity gates apply there as they apply in v1's ROI; a short or an open elsewhere on the board is a warning, as in v1's margin.
- **The rest of the board** is meshed coarse: λ_eff(f2)/20 in the dielectric, graded at 1.3 into the air up to λ(f2)/20.
- **The rest of the board's parts are never ports.** v1's roles apply to them with two changes, since a part far from the chain still sits in the antenna's field:
  - a capacitor whose self-resonance is below 3·f2 is bridged as copper, not left open: a decoupling capacitor is close to a short at RF, and an open one would leave its pour floating next to the antenna;
  - an inductor or a ferrite bead, or a part whose value does not parse, is left open rather than made a port.

  Resistors, and capacitors resonating above 3·f2, go in the grid as in v1. Every shield frame on the board gets its lid at the project's lid height. The stated limits (§5.6) say these parts are approximations.
- **Placement repeatability.** The antenna group's mesh lines are placed in the antenna footprint's own frame and move with it, so a variant that moves the antenna keeps the antenna's own discretization. Gate P3-D measures the noise that remains.
- **The copper model is a whole-model choice.** openEMS runs one timestep for the whole model, and the mesh rule puts both faces of every copper layer across the whole domain, so a single solid feed line keeps the 35 µm cell, and its small timestep, everywhere. Stage 1 §5.3's solid copper is the default. Gate P3-C compares it with all-sheet copper (every copper layer a sheet) on both fixtures: if all-sheet passes, it becomes the antenna default (r1: 5–6 times cheaper); if it fails, it is not offered. Gate P3-C kept solid copper (A-35).
- **Diagonal antenna copper** (KiCad's `Texas_SWRA416_868MHz_915MHz` has 18 diagonal segments) keeps v1's W_STAIRCASED warning; it is never refused.
- **fit2d** runs on the feed network's sections only: a radiator has no reference under it.

### 5.4 Excitation and stop

- **The pulse** is Stage 1 §5.8's DC-free pulse over f1 ≈ f_lo/1.3 to f2 ≈ 1.2·f_hi (r1: 1.9–2.9 GHz for 2.4 GHz, about 0.7–1.1 GHz for 902–928 MHz). The builder rounds them.
- **The stop rule** is Stage 1 §6.3's port residual with v1's presets. Only two constants scale with f0 for antennas:
  - T_max defaults to 2·t0 + 60/f0: about 30 ns at 2.45 GHz, about 75 ns at 915 MHz;
  - the flat window is max(5 ns, 20/f0).

  Gate P3-C kept both (A-37). v1's constants do not change.
- **The growth detector** (Stage 1 §6.3) is the PML's guard: a run whose energy grows is classified as v1 classifies it.

### 5.5 The far field

- **Recording.** The worker adds openEMS's far-field box with frequency-domain recording at no more than 11 frequencies, all inside [f1, f2]: f0, f_lo, f_hi and the rest spread across the band. r1 measured 12 MB of dumps against 368 MB for time-domain recording, and a 0.55 s transform against 7.8 s.
- **When.** The far field is recorded in a job only when that job holds the actual antenna network: the run of a project with M = 0 (no part on the chain), and verify, which holds every part in the grid at its applied value (Stage 1 §7.6), a 0 Ω or an open one included. A part-port run records none.
- **The transform** runs in a worker mode, since the orchestrator never imports openEMS. It always passes `read_cached=False` and an output file unique to the call; a test asserts both. The full sphere is sampled at 5°, and the three principal cuts at 1° at f0: XY (θ = 90°), XZ (φ = 0°) and YZ (φ = 90°).
- **Quantities.** P_rad is openEMS's surface integral. P_acc and P_inc come from the port's record over the same time window as the far-field recording. Then η_rad = P_rad/P_acc, η_tot = P_rad/P_inc = η_rad·(1 − |S11|²), gain = D·η_rad and realized gain = D·η_tot. openEMS's own tutorials mix the two efficiencies; every output here names which it is. An η_rad above 1.02 raises a validity warning.

### 5.6 Results

- **What a run gives**, besides v1's run files:
  - S11 at the start port with the band shaded, a Smith chart and the input impedance;
  - the resonance (the minimum of |S11|), the −10 dB bandwidth with a −6 dB marker, and the mismatch efficiency 1 − |S11|²;
  - from a far-field job: η_rad, η_tot, D, peak gain and realized gain across the recorded frequencies, and the three cuts at f0;
  - files: a one-port Touchstone file, the full-sphere far field as CSV, a per-frequency summary CSV and a summary PNG.
- **The relative label and the stated limits** go on every antenna result: the CLI's lines, the summary PNG, the GUI's antenna pages. The limits: the board alone in free space; copper as a perfect conductor, so η_rad reads high; no enclosure, hand, battery or cable; parts' bodies absent; parts off the chain approximated (§5.3); results compare variants under identical settings and do not predict measured performance.
- **The loss budget** (Stage 1 §7.4) does not apply to an antenna: radiation is its "loss".

### 5.7 Matching, retune and verify (one-port)

- **The run** is v1's: P + M jobs, here 1 + M. Terminating the part ports with their models gives S11 at the radio pin for any part values, so the instant retune, the E12/E24 snapping (E24 by default) and S2P parts work as in v1. Setting the series parts to 0 Ω and opening the shunts shows the antenna through its feed line.
- **The instant retune** shows S11 and the mismatch efficiency, under Stage 1 §7.6's what-if label. Where the project has a far-field result, it also shows η_tot = η_rad·(1 − |S11|²) with η_rad from that result, labelled what-if: a lossless network leaves the radiated power and the pattern as they are.
- **Verify** is v1's, one-port: every part in the grid at the applied values, one job, with the far field recorded. It compares |ΔS11| at f0, the largest |ΔS11| up to f2 and the resonance shift with the instant retune.

### 5.8 Compare and significance

- **`kicad-rf-studio compare BASE VARIANT`** overlays the two projects' S11 and, where both have one, their efficiencies and cuts. It writes a deltas table: the resonance shift in MHz and %, the −10 dB bandwidth's change, Δη_tot in dB at f0 and at the band's edges, and the change in peak gain.
- **Same settings or nothing.** `compare` refuses when the two projects' settings fingerprints differ (preset, mesh, band, air gap, boundary, stackup, copper model, app and openEMS versions).
- **Resolved or not.** Each delta is marked resolved when it exceeds the significance threshold, and "not resolved" otherwise. The thresholds default to 0.3 % of f0 for a resonance shift and 0.2 dB for an efficiency or gain change, kept by gate P3-D, whose measured noise floor lies under a third of them (A-39).

### 5.9 Cost

Stage 1 §6.4's estimate stays: jobs × cells × T_max/dt over the calibrated speed, with T_max the worst case. For an antenna, the cost lines split the cells into board, air and PML. Gates P3-B to P3-E's runs refitted the small-model speed by pool level (0.559 at one job, 0.718 at four) and the PML weight (8.92) (A-38).

### 5.10 GUI and button

- **New** gains a kind: matching chain or antenna. For an antenna it lists the candidate footprints (modules and chip antennas listed but disabled, with the reason), the start pad, and the band with presets: 868 MHz (863–870), 915 MHz (902–928), 2.4 GHz (2400–2483.5) and custom.
- **Cost and Run** are unchanged.
- **Results** for an antenna: S11 with the band shaded, the Smith chart, the result lines, and the three polar cuts at f0 from matplotlib. Retune works as in v1, on S11 and the mismatch efficiency; efficiency and pattern say which run they come from.
- **Compare** opens a second project and shows the overlays and the deltas table.
- **Advanced** shows the antenna fields: the air gap, the boundary, the far-field frequencies and angle step.
- **The button.** A selected antenna footprint pre-fills New with the antenna kind, and a selected pad pre-fills the start pad; a selected module or chip antenna shows the refusal.

### 5.11 Validation gates (amends Stage 1 §9)

Stage 3 is validated like Stage 1: numerical references, each gate with its case, its metric, its threshold and what happens when it fails. A published measurement (an app note's S11 or gain) is a soft plausibility note in the gate's report, never a pass criterion: AN043 states its own scatter. References are committed as JSON and never regenerated during a gate. Each gate gets a short report under `docs/validation/`, with its machine time predicted and measured.

| Gate | Case | Pass | If it fails |
|---|---|---|---|
| P3-A Far-field sanity | Synthetic dipoles in air under PML_8, no board: a short dipole and a half-wave dipole | short dipole D = 1.76 ± 0.10 dBi; half-wave D = 2.15 ± 0.15 dBi; η_rad = 1 ± 0.02 (PEC in vacuum); the far-field box moved 2 cells changes D by ≤ 0.05 dB; no energy growth out to 3 × the stop time; an aborted run still writes its far-field dumps | a pipeline bug: blocks Stage 3 until fixed |
| P3-B The pipeline against a hand-built model | The 2.4 GHz fixture through `new` and `run`, against an openEMS script of the same geometry written by hand (MUR at λ/2, its own mesh, as openEMS's inverted-F example does) | f_res within 1 %, Dmax within 0.3 dB, η_rad within 0.3 dB | import, mesh or port bug: blocks until explained |
| P3-C Convergence and defaults | Both fixtures: mesh n 2/3/4, air gap λ/4 against λ/2, the Normal against the Strict preset, a run to 3 × its stop time, solid against all-sheet copper | n = 2 within 1 % of the extrapolated f_res (else n = 3 becomes the antenna default); gap: Δf_res ≤ 0.2 %, ΔD ≤ 0.2 dB, Δη ≤ 0.1 dB; preset: Δf_res ≤ 0.1 %, Δη ≤ 0.05 dB; all-sheet becomes the antenna default if Δf_res ≤ 0.5 % and Δη ≤ 0.1 dB on both | a default is raised (n, gap, T_max); PML unstable: MUR at λ/2 becomes the antenna default; all-sheet not offered |
| P3-D Noise floor | The 2.4 GHz fixture (the cheaper one): the same run twice; the whole model shifted by one fine cell; the antenna alone moved by ± one fine cell | records the noise; passes if the antenna's ± move gives ≤ 0.2 % of f0 and ≤ 0.1 dB in η | the significance thresholds widen to three times the measured noise |
| P3-E Positive control | A fixture variant with a ground pour inside the antenna's clearance | its resonance shift is resolved | the thresholds hide real effects: refine and repeat P3-D |
| P3-F Second solver (optional, the owner's) | EMerge in its own Python 3.13 venv, on a printed dipole or the 2.4 GHz fixture, as P0-B ran it | f_res within 1.5 %, Dmax within 0.5 dB; "inconclusive" is allowed with its cause written | cannot fail Stage 3 alone |

r4 estimates 15–35 machine hours in all, mostly overnight. `cost` predicts each run first.

**Fixtures.** Two synthetic boards built with the repo's fixture generator from KiCad's library footprints: `Texas_SWRA117D_2.4GHz_Left` on a stated rectangular ground (2.4 GHz), and `Texas_SWRA416_868MHz_915MHz` on its ground (868/915 MHz), each with a radio pad. The gates run each fixture with the antenna fed straight from the radio pad through a 50 Ω line (M = 0: one job per run, the far field in it), plus the variants P3-D and P3-E need. The 2.4 GHz fixture also has a variant with a pi network (M = 3), for the tutorial and the acceptance run. They are the regression tests too.

### 5.12 Plans

Stage 3 runs as five plans. Each is subagent-driven, leaves the suite green in both languages, and is merged to main before the next is written.

1. **The far-field engine.** Golden pins on v1 (model specs, hashes and output bytes for every v1 fixture); the boundary and far-field keys in the model spec, written only for antennas; the worker's far-field box and transform mode; the far-field reader and the efficiencies; E_METAL_IN_PML; the PML cost weight; gate P3-A on synthetic dipoles.
2. **The antenna project.** Schema 2; `new --antenna`; the footprint classes and refusals; the antenna group, its net and its join; the whole-board domain, the air box and its mesh; the measured region and the rest of the board's parts; the antenna's T_max and flat window; fit2d on the feed network; cost's cell split; the two fixtures; a run with M = 0 that writes §5.6's files.
3. **Matching and comparison.** Every chain part a port; the one-port branch of the run's results, the retune (with 0 Ω and open) and verify; the far field in verify; `compare` with the fingerprint and the thresholds.
4. **The gates.** P3-B to P3-E on the fixtures, their reports and the defaults they set; P3-F left to the owner.
5. **The GUI, the button and the docs.** §5.10; the README's antenna tutorial on the 2.4 GHz fixture; the release check; the Stage 3 exit record.

### 5.13 Amendments to the Stage 1 spec

These are A-23 onward, each landing in the plan that implements it:
- §1.1's simulation domain: the whole board for an antenna project;
- §2's stage table: Stage 3's design;
- §5.1: the antenna boundary, the air gap and E_METAL_IN_PML;
- §6.3 and §6.4: the antenna's T_max and flat window, and the cost's cell split;
- §7: the one-port retune and verify, and no loss budget for antennas;
- §9: gates P3-A to P3-F;
- §10: antennas and NF2FF leave the deferred list, and this design's non-goals join it.

### 5.14 Acceptance

Stage 3 is done when all of these hold:
1. The five plans are merged, the suite green in English and the GUI tests in pt-BR.
2. P3-A to P3-E have passed, or their fallbacks are in force and recorded; P3-F has run or is recorded as the owner's.
3. One antenna project has run end to end through the GUI's code paths offscreen, on the 2.4 GHz fixture with its pi network: New, Cost, Run (S11 for any values), a retune with snapping, Apply, Verify (the far field at the applied values), and a compare against the ground-pour variant verified at the same values.
4. The Stage 3 exit record lists the owner's items.

## 6. Left to the builder

- Module, class, function and message code names, within §5's rules.
- The exact pulse band, the far-field frequencies within the limit, the cuts' layout and the summary PNG's panels.
- The settings fingerprint's exact fields.
- How each plan is cut into tasks, and the fixtures' exact ground planes, matching footprints and variants.
- Whether the PML weight and the small-model speed need a calibration change (§5.9).

Where this design and the code disagree, the code's tests and the Stage 1 spec win, and the controller rules on it in the plan's ledger.

## 7. Owner items this work leaves open

Each item has the default this design applies:
- **The whole board for antennas** (amending Stage 1 §1.1). Default: yes; the selected region stays for the matching chain.
- **Chip and module antennas.** Default: refused, with the message pointing to v1's chain.
- **Band presets.** Default: 868 (863–870), 915 (902–928, which covers Brazil's 902–907.5 and 915–928 MHz) and 2.4 GHz (2400–2483.5), plus custom.
- **The bandwidth threshold.** Default: −10 dB, with a −6 dB marker.
- **Absolute numbers.** Default: shown, always with the relative label and the stated limits; deltas marked resolved or not.
- **The boundary.** Default: PML_8 with a λ/4 gap at f_lo; MUR on all six faces stays a project option: gate P3-C found PML_8 stable and measured MUR at λ/2 rising 21 dB within 90 ns, so it is no fallback (A-36).
- **Sheet copper for antennas.** Default: solid, as Stage 1 §5.3; all-sheet copper, for the whole model, is not offered: gate P3-C kept solid copper (A-35).
- **Runtime.** Default: measured and recorded, shown by `cost` before every run; no runtime is promised (measured: one 2.4 GHz job 25 min, `docs/validation/2026-10-30-antenna-first-run.md`). Gates P3-B to P3-E's runs refitted the small-model speed by pool level (0.559 at one job, 0.718 at four) and the PML weight (8.92) (A-38).
- **Matching placeholders.** Default: every part on an antenna's chain is a part port, a 0R or DNP placeholder included.
- **Parts off the chain.** Default: never ports; decoupling capacitors past their self-resonance bridged as copper; inductors, beads and unparsed values left open.
- **Matching in the far field.** Default: efficiency and pattern from the jobs that hold the network (M = 0, or verify); an instant far-field retune by superposition is deferred.
- **A dielectric enclosure shell** (εr, thickness, gap). Default: deferred, a stated limit.
- **EMerge as P3-F.** Default: optional, in its own venv, "inconclusive" accepted.
- **Unchanged owner items:** the first push and its identity rewrite, the deny-list review, P0-C, the engine redesign (A-9, A-10), RFsim/NOTICE, the click-through, the plugin identifier, the native review of `po/pt_BR.po`.

## 8. Risks

1. **PML late growth.** Stage 1 saw it with copper in the absorber; r1's probes saw none without. Mitigation: P3-A and P3-C's runs to 3 × the stop time, the growth detector, the MUR fallback.
2. **Runtime at 868/915 MHz.** A high-Q antenna rings long, and solid copper sets a small timestep. Mitigation: T_max scaled by f0 with its flag, cost before every run, P3-C's sheet-copper check.
3. **Deltas inside the noise read as design guidance.** Mitigation: P3-D's measured floor and "not resolved".
4. **A silent v1 regression.** Mitigation: the golden pins land first.
5. **The far-field dumps after an abort** are not yet confirmed on 0.37.0. Mitigation: P3-A checks it; until then a run's far field comes from a run that ended by its own criterion.
6. **Weak published references.** The tutorials publish plots, not numbers, and the app notes leave out ground planes. Stage 3's confidence rests on theory (P3-A), internal consistency (P3-B to P3-E) and the optional second solver.
7. **Users over-reading absolute efficiency or gain.** Mitigation: the label and limits on every result.
8. **The owner's ESP32 work mostly uses modules**, which Stage 3 refuses. Mitigation: the refusal says why and what still applies; the module's own pad stays a v1 chain end.
