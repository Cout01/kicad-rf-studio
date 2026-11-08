# kicad-rf-studio — Stage 4 design: signal integrity of a net or a differential pair

Status: written on 2026-11-02 by the controller, right after Stage 3 closed (main at `f62fa65`). The owner is unavailable and asked not to be stopped for questions, so every decision below that the Stage 1 spec, the Stage 2 and Stage 3 designs and the pt-BR design did not already make is a controller recommendation, owner unavailable. The research behind it is in `.superpowers/sdd/stage4-research/` (git-ignored):
- r1, the physics, with five openEMS probes of a coupled microstrip pair run on this PC;
- r2, the user's workflow and the KiCad side;
- r3, the engine;
- r4, the references and the gates.

An independent builder read the design before the commit. Its four questions are settled in §5.1 (the TDR's two rise times, the presets' band and their marker frequency), §5.3 (the Debye default's rule) and §5.3 again (SI's timestep floor). Amended on 2026-11-08 by plan 4 with the gates' results (P4-B to P4-F, `docs/validation/2026-11-06-p4-b.md` to `2026-11-08-p4-f.md`).

References: "Stage 1 §x" names a section of the Stage 1 spec (`docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`), and so does every § in a list or heading that names that spec; "Stage 3 §x" names one of `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md`; a bare § names a section of this design.

## 1. Intent and why

The Stage 1 spec's stage table leaves "SI, EMC and differential pairs" for later, and the roadmap after the antennas is signal integrity. The users are the same hardware engineers, and the case is a fast net on their own board: a USB 2.0 high-speed pair from the connector through its ESD pads and series resistors to the MCU, a 100BASE-TX pair to the magnetics, a QSPI or SDIO clock with its series resistor. KiCad routes the pair at a width and gap from a calculator, but the calculator knows only the straight section. The connector's pads, the ESD array's pads, a 0402 resistor's pads, a via, a neck-down at the MCU, a gap in the plane under the pair and a neighbour net all change what the signal sees. Stage 4 shows where along the route the impedance leaves its target, how much of the differential signal turns into common mode, how much leaks into a neighbour, and what a series termination's value does, on the user's own board, before it is made.

The results are relative, as in Stage 3, because there is no hardware (Stage 1 §1.1) and because the model leaves things out: the copper is a perfect conductor, the region is cropped by absorbing walls, and the packages, dies and connector bodies are absent. A variant run against a baseline with identical settings cancels most of what the two share, so Stage 4's main outputs are the profile along the route and the comparison: this route against that one, with each difference marked resolved or not.

Success: from a KiCad board and two pads, the user gets the route's impedance profile (a TDR) against the target band, the mixed-mode S-parameters of a pair (differential insertion and return loss, mode conversion), the intra-pair skew, the crosstalk to a neighbour, a 2D table of every straight section's impedance in seconds, an instant retune of the series parts on the route, and a comparison that says which differences are resolved. Runtime is measured and shown by `cost` before every run, never promised. Up to 3 GHz, r1 estimates a USB 2.0 high-speed pair at about 2 minutes per job with §5.3's mesh rule, and about 7–24 minutes per job with Stage 1 §5.4's rule as it stands. At the presets' 10 GHz (§5.1), the controller estimates about 5–10 minutes per job with §5.3's rule.

## 2. What is already decided (binding)

- Stage 1 §1.1: openEMS 0.37.0 and CSXCAD 0.7.0 as they are; always a selected region, never a whole board; no hardware, every reference numerical; the what-if label on the instant retune; and, from Stage 1 §3.1, the CLI and GUI never import openEMS.
- Stage 1 §5.1: MUR on all six faces for a selected region, with copper running through the walls; boundary types never mixed per face.
- These Stage 1 sections are reused, with the changes below:
  - §5.3: solid copper;
  - §5.4: the mesh rule, the protected set and the mesh gates;
  - §5.6: the port box between a signal pad and its reference copper;
  - §6.3: the port-residual stop rule and its presets;
  - §6.4: the cost estimate;
  - §7.1: one job per port, and S = B·A⁻¹;
  - §7.2: the instant retune with snapping;
  - §7.6: verify;
  - §7.7: the explicit S-parameter definition.
- Stage 2: the GUI client, the KiCad button and its handoff, cost before every run, the run folders and events.
- Stage 3: the project kinds by schema, the settings fingerprint, `compare` with its resolved and not-resolved thresholds set by a noise-floor gate, and the golden pins that land before any shared change.
- The pt-BR translation: every new message code is a catalog code with its pt-BR msgstr, compiled into the committed `.mo`.

## 3. Goals, non-goals and anti-goals

Goals:
- An SI project from a KiCad board: one net between two pads, or a differential pair between two pads of each leg, plus up to two victim nets for crosstalk.
- The route's single-ended S-parameters as a Touchstone file; for a pair, the mixed-mode Sdd11, Sdd21, Scc11, Scc21, Scd11 and Scd21 at the target's reference impedance.
- A TDR impedance profile along the route against the target band, with its rise time and its resolution length shown, and the TDT.
- The intra-pair skew; NEXT and FEXT to each victim.
- In `cost`, a 2D table of every straight section's impedance (Z0, or Zdiff, Zodd and Zeven for a pair) against the target, in seconds, with no FDTD run.
- The series parts on the route (a series resistor, an AC-coupling capacitor, a 0R) as part ports: an instant retune with E12/E24 snapping under the what-if label, Apply and Verify, as in v1.
- A comparison of two projects with each difference marked resolved or not resolved.
- Every SI result labelled relative, with its stated limits.
- v1's and the antenna's projects, models and outputs unchanged, bit for bit.

Non-goals (Stage 4 does not do these):
- Eye diagrams, masks, jitter, BER; IBIS or IBIS-AMI drivers; an ideal-driver waveform. KiCad 9's own ngspice simulator loads IBIS models, and Stage 4's Touchstone files can be cascaded there.
- Power integrity and the PDN.
- Radiated emission (EMC). Stage 4 reports mode conversion and plane-gap crossings, with a "radiation risk, relative" note; the far field of a driven net belongs to a later EMC stage built on Stage 3's engine (r2 §5).
- A whole-board or whole-plane model. The plane-pair cavity resonances depend on the crop and are not predicted (§5.2).
- Parts with three or more pads on the route (an ESD array, a common-mode choke) as models: their pads are copper, their capacitance and coupling are absent, and a route cannot pass through a choke (§5.1).
- Back-drilled, blind and buried vias' details: KiCad 10's backdrill and post-machining tokens, inner via pads, and a blind via's layer-limited connectivity. Through vias are modelled as Stage 1 models them.
- Reading `.kicad_pro` net classes or KiCad 10's tuning profiles. KiCad 9 stores no impedance target; targets come from the interface presets or the user (§5.1).
- Absolute insertion-loss verdicts against a standard's limit, and standards' masks.
- Segmenting a long net and cascading its pieces; more than two ends on one line (a multi-drop net's other branches are stubs in the model).

Anti-goals:
- An SI number shown without the relative label and the stated limits.
- A TDR level shown as an impedance on a feature shorter than the TDR's resolution.
- A difference inside the model's noise shown as a real one.
- Any change to v1's or the antenna's projects, models or results.
- Copper as openEMS's conducting sheet: it read Zdiff 11 % high in r1's probe, and its thickness is in metres whatever the drawing unit.
- v1's constant-κ dielectric loss on an SI model: it gives a flat loss and a DC leakage that real FR-4 does not have (r1 measured 6–7 % of the power lost at DC on 50 mm).

## 4. Constraints

- openEMS 0.37.0 and CSXCAD 0.7.0 as installed, never bundled; Windows 10/11 and Linux; Python 3.14; KiCad 9 and 10 boards.
- No new runtime dependency. scikit-rf 2.2.0, numpy and scipy are already in; scikit-rf has `se2gmm`, `renormalize` and `extrapolate_to_dc` (r3, r4).
- Fixtures are synthetic boards built from KiCad's own library footprints with the repo's fixture generator, under Stage 1's A-3 isolation. No vendor file is shipped; application notes are cited.
- Every new message has its pt-BR msgstr in the same commit, through `tools/catalog.py`.
- v1 projects stay at schema 1 and antenna projects at schema 2, their model specs, hashes and output files byte for byte. The first plan adds golden pins for the antenna fixtures (v1's exist, the antenna's do not) before any shared change.

## 5. Decisions

### 5.1 The SI project

- **Inputs.** These are:
  - the board;
  - the start pad and the end pad of the measured net, for example the MCU's pin and the connector's pin;
  - an interface preset, which sets the band and the target;
  - for a pair, the partner net;
  - optionally, up to two victim nets, each by its two end pads;
  - v1's preset, stackup and lid height.

  The CLI form is `kicad-rf-studio new BOARD --start REF.PAD --end REF.PAD --interface NAME`, with the interface in place of `--f0` or `--band`, plus these options:
  - `--pair`, to take the partner by KiCad's rule, or `--pair-with REF.PAD:REF.PAD` to name its two ends;
  - `--victim REF.PAD:REF.PAD`, repeatable;
  - `--f-max F` and `--target OHMS`, for `--interface custom`.

  `cost`, `run`, `retune`, `verify`, `preview` and `compare` work on it as they do on the other kinds.
- **project.json.** An SI project is schema 3 with `"kind": "si"`; schemas 1 and 2 keep their meanings, and a build before Stage 4 refuses schema 3 with E_PROJECT_SCHEMA. Its fields:
  - the board;
  - the lines, each with its role (measured or victim) and its chain in v1's chain shape;
  - the pair;
  - the ports in v1's port shape, ordered [P start, N start, P end, N end, then each victim's start and end, then the part ports], so that `se2gmm` takes the pair's ports as they stand;
  - the interface, `f_max_hz`, the link's rise time, the marker frequency, the target impedance and its tolerance;
  - the dielectric model (§5.3);
  - `t_max_s` and the stop window (§5.4);
  - the preset, mesh and gates as in v1, and the lid.
- **The interface presets.** Each target is cited from a public application note. The link's rise time is the edge the link's driver makes: USB 2.0's is its specification's minimum and 100BASE-TX's is ANSI X3.263's (both cited by r1). se50's 1 ns is the controller's default for a fast MCU pin. The marker is the link's Nyquist frequency or its clock.

  | preset | target | the link's rise time | marker | f_max |
  | --- | --- | --- | --- | --- |
  | `usb2-hs` | 90 Ω differential ± 10 % (TI SPRAAR7J) | 500 ps | 240 MHz (480 Mb/s) | 10 GHz |
  | `100base-tx` | 100 Ω differential ± 10 % (TI SNLA387) | 3 ns | 62.5 MHz (125 Mbaud) | 10 GHz |
  | `se50` (QSPI, SDIO, SPI, a clock) | 50 Ω single-ended ± 10 % | 1 ns | 133 MHz | 10 GHz |
  | `custom` | the user's | the user's | the user's | the user's |

- **Two TDRs from one run.** The same S gives both (§5.6):
  - **The localising TDR** runs at the finest rise time the band supports, 1.25/f_max: §5.6's Gaussian filter is then near −40 dB at f_max, so the band's edge adds no ripple. At 10 GHz that is 125 ps, a resolution of about 12 mm on FR-4. The run's readings, compare's deltas and the gates read it.
  - **The link's TDR** runs at the link's rise time and is drawn beside it: what the link's own edge sees. At USB 2.0's 500 ps its resolution is about 45 mm, coarser than any pad on the route. That is why the band is set for the localising TDR, not for the link: r1's band for USB 2.0, 3 GHz, would have left a 417 ps TDR that resolves no pad, resistor or neck-down.
  - A link rise time faster than 1.25/f_max is refused.
- **The lines.** v1's tracer walks each line from its start pad to its end pad. The two-pad parts on the way are the line's parts:
  - Every one of them is a part port, whatever its value, as in Stage 3 §5.1, so a series termination can be retuned.
  - The exception is a shunt resistor of 1 kΩ or more to a supply or to ground, such as a pull-up. It is left open, the run spares its job, and `new`'s notes say so.
  - A line whose end can be reached only through a part with three or more pads (a common-mode choke) is refused, with a message that says to measure each side of it.
- **The pair.** The partner net is found by KiCad's own differential-pair rule (`BOARD::MatchDpSuffix`: from the end of the name, skip digits and underscores, then a `+`/`-` or an uppercase `P`/`N`), plus a `DP`/`DM` alias. The partner's ends are its pads on the start pad's and the end pad's footprints. A partner that is not found, or not exactly one pad on each footprint, is refused with a message naming `--pair-with`. `new`'s notes print the pairing.
- **The victims.** A victim's two ends become ports, so its coupled waves end in 50 Ω, not at a wall. A victim whose ends lie outside the region the measured lines set is refused: the region would have to grow to hold them, and v1's region rule does not grow for a victim.
- **The off-chain parts** keep v1's roles, plus Stage 3's capacitor rule (A-27, at f_max/2): a decoupling capacitor close to a short there is bridged as copper. A reference plane's return current crosses from one plane to another through those capacitors, and an open one would leave the planes unjoined. An ESD array's pads on the line are copper, and its capacitance is a stated limit.

### 5.2 The region and its walls

- **The selected region stays** (Stage 1 §1.1). It is the bounding box of every line's copper and parts, plus Stage 1 §5.4's reach, inside MUR walls on all six faces, with the planes and any cut copper running through them. A corridor along the route saves no cells on a tensor-product grid (r3). A PML is impossible, because the planes cross every wall (E_METAL_IN_PML).
- **Stated limits.**
  - The walls absorb most of what reaches them and reflect the rest (Stage 1 §7.5), which colours a cut neighbour's crosstalk.
  - The plane pair's cavity resonances depend on the crop, so their frequencies and depths are not predictions.
  - An open microstrip's radiation is absent.

### 5.3 Mesh, copper and dielectric

- **Copper** is solid, as Stage 1 §5.3 has it, never a conducting sheet.
- **The SI mesh rule** applies to an SI project only:
  - Stage 1 §5.4's fine cell d fills only the copper edges' patterns, plus a margin around each via, as the builder sets it.
  - Between them, the cells grade at 1.3 up to `max_cell`, which defaults to λ_eff(f_max)/40.
  - A straight 100 mm run then needs about 230 lines along it where the d fill needs about 1,400 (r1).
  - Gate P4-C compares the rule with the d fill. If it fails, the d fill stays and SI runs at Stage 1's cost.
  - The edge lint and fit2d apply unchanged. fit2d also checks a pair's coupled sections (§5.9).
  - **The timestep floor** is 0.6 by default for an SI project (`gates.dt_floor`), not v1's 0.8:
    - Real pairs are rarely axis-aligned. A staircased 45° track at n 3 read its dt at 0.72 of the rule's reference in Stage 3 (A-35), and stopped on E_DT_FLOOR.
    - The floor guards the runtime: 0.6 costs a third more steps at worst, and still stops a mesh whose lines nearly coincide.
    - Stage 3's meander ran its n 3 and n 4 at 0.6.
    - v1's and the antenna's floors stay 0.8.
- **The dielectric under each layer.** For an SI project, d and the reach use the dielectric next to each copper layer the lines use, not the top layer's alone. Today `zstack` takes the top layer, which is wrong for a stripline (r3).
- **The dielectric model** is an SI project field with two values:
  - **lossless**: no conductivity;
  - **Debye**: a multi-pole Debye fit of the stackup's εr and tan δ, in the Djordjevic–Sarkar manner, through CSXCAD 0.7.0's `CSPropDebyeMaterial`, with about one pole per decade of the band and at least two.

  Gate P4-D checks the Debye model against scikit-rf's MLine with Djordjevic–Sarkar loss, and measures two numbers that are kept apart:
  - **The Debye cell's weight** w: what one Debye cell costs against a plain one, which `cost` counts as it counts a PML cell. r1 measured about 6.8 at five poles.
  - **The whole run's slowdown** on the USB 2.0 fixture: 1 + f·(w − 1), where f is the fixture's share of Debye cells. r1's five-pole line, with 20 % of its cells in the substrate, ran 2.35 times slower.

  The rule, registered here before the gate runs: if the accuracy check passes and that slowdown is 1.5 or less, Debye becomes the SI default. Otherwise lossless stays the default and Debye is an option. Lossless is the cheaper default because the presets' interfaces lose little on a board's route, and the impedance profile, the mode conversion and the crosstalk are right without loss (r1). v1's constant κ is never used for SI.
- **Diagonal and arc routing** keeps v1's W_STAIRCASED warning. Gate P4-B's 45° pair, against its axis-aligned twin, decides whether a staircased pair stays a warning or is raised to n 3 or refused.
- **Vias** are Stage 1's through vias: solid barrels, their end-layer rings and the antipads from the saved zone fills. Inner rings, back-drilling and blind or buried connectivity are deferred and stated.

### 5.4 Excitation and stop

- **The pulse** for an SI project is a Gaussian from DC to f_max: openEMS's `SetGaussExcite(0, f_max)`, or the same as a custom expression. The DC point is then measured: r1's probe read S11 = 0 and S31 = 1 at DC on a line with 50 Ω ports at both ends. Stage 1 §5.8's DC-free pulse stays for v1 and the antenna.
- **The stop** is Stage 1 §6.3's port residual alone.
  - With a DC pulse, openEMS's field energy never decays: r1 measured −1.43 dB for all of 30 ns, from the static charge a soft source leaves. The port signals reached −60 dB at 4.1 ns. v1's EndCriteria stays at 1e-15.
  - The residual's window scales with the longest line: `window_s` = max(2 ns, 1.5 × the longest port-to-port round trip). It is written only in SI specs, as Stage 3 wrote `flat_s`, so a pulse still travelling on a long line cannot read as converged.
  - T_max defaults to the pulse's length + 6 × the longest round trip + 2 ns. The round trip comes from the route's length and the 2D εeff.
  - The growth detector stays.
- **The fallback**, if gate P4-D finds a model whose port residual does not decay with the DC pulse, is Stage 1 §5.8's DC-free pulse. The DC point is then computed from the copper's connectivity (a resistive nodal solve with the ports as 50 Ω), and the gap up to the first trusted point is interpolated (r3).

### 5.5 Ports

- **One single-ended lumped port at each end of each line**, 50 Ω, in Stage 1 §5.6's port box. A pair has 4 ports and a victim 2. There is one job per port and one per part port (Stage 1 §7.1), and S = B·A⁻¹ as in v1.
- **The vertical port** is new, for SI only. When an end pad has no same-layer reference copper within the reach, its port runs from the pad to the nearest plane under it, across the pad: the natural port for a line over its plane. Today such a pad is refused (E_REFERENCE_LAYER). Gate P4-D compares it with the horizontal port on a pad coupon.
- **Mixed mode** comes from scikit-rf's `se2gmm` on the ordered ports, renormalised to the target with the S-parameter definition passed explicitly (Stage 1 §7.7). It is exact for the layout N-port, so no odd- or even-mode excitation is needed.
- **Deferred:** a two-run differential and common excitation (openEMS accepts signed port amplitudes) would halve a pair's jobs. It gives only the near-end columns, which a part-port reduction cannot use.

### 5.6 Results

- **The TDR and TDT** are computed from S on a uniform grid from DC to f_max, once at each of §5.1's two rise times:
  - a Gaussian rise-time filter at that rise time;
  - an inverse FFT;
  - a cumulative sum started before t = 0. r1's first version read half the step when it started at t = 0, because the filter's impulse is centred there.
  - then Z = Z_ref·(1 + ρ)/(1 − ρ).

  The routine is the repo's own, a few lines of numpy, with a unit test on an ideal 60 Ω line that must read 60.0 Ω, then 50.0 Ω.

  The profiles are plotted against time and against distance (the 2D εeff), with the target band, each rise time and its resolution length t_r·v/2.
  - **Short features.** A level on a feature shorter than two resolution lengths is marked as not the feature's impedance: a 5 mm neck-down from 90 to 110 Ω reads about 8 Ω high at 125 ps, not 20 Ω.
  - **Deltas still compare.** Two projects at the same settings filter the same way (the fingerprint holds f_max), so a difference between them is still compared against §5.8's thresholds.
  - **The launch.** The first resolution length at each port is marked as the port's own launch: the lumped port's parasitic, j6–19 Ω at 10 GHz from r1's estimate of 0.1–0.3 nH.
- **What a run gives**, besides v1's run files:
  - the single-ended layout Touchstone file and, after the part ports are closed, the chain's;
  - for a pair: Sdd21, Sdd11, Scc21 and Scd21 (insertion loss, return loss, common-mode transmission and mode conversion);
  - the differential (pair) or single-ended (net) TDRs, with the localising one's lowest and highest impedance along the route, outside the launches, and their positions against the target band;
  - the skew between the legs' TDTs, in ps;
  - NEXT and FEXT to each victim, with their peaks;
  - a CSV of the mixed-mode S and the TDR, and a summary PNG.
- **Loss** is labelled by what holds it. The copper is a perfect conductor. Each run prints formula estimates at the marker frequency and at f_max, over the route's length:
  - the conductor loss (Hammerstad, smooth copper);
  - with a lossless dielectric, the dielectric loss too.

  These are not folded into the S-parameters. Without loss, r1 found these results right: the impedance profile, the return loss's features, the mode conversion, the crosstalk and the resonance frequencies. Insertion loss magnitudes, and the depth of resonances, need the loss.
- **The relative label and the stated limits** go on every SI result: the CLI's lines, the summary PNG and the GUI's SI pages. The limits:
  - the region's crop and its walls (§5.2);
  - copper as a perfect conductor;
  - the dielectric model in force;
  - packages, dies and connector bodies absent;
  - three-or-more-pad parts as pads alone;
  - lumped ports at the pads;
  - the TDR's resolution;
  - results compare variants under identical settings and do not predict measured performance.
- **Validity.** v1's passivity and reciprocity indicators apply. v1's loss budget (Stage 1 §7.4) does not: a lossless model's missing power is the walls' and radiation's.

### 5.7 Retune and verify

- **The retune** closes the part ports with their models (Stage 1 §7.2): E12/E24 snapping (E24 by default), S2P parts, the what-if label while `RETUNE_VALIDATED` is False. It redraws the TDR, the mixed-mode S and the crosstalk from the closed N-port, so a series termination's value is swept without a run.
- **Verify** is v1's: every part in the grid at its applied value, one job per external port. It compares |ΔS| over the band, and the TDR's lowest and highest levels, against the retune at the same values.

### 5.8 Compare and significance

- **`compare BASE VARIANT`** on two SI projects:
  - overlays their TDR profiles and mixed-mode S;
  - writes a deltas table: the localising TDR's lowest and highest impedance (Ω), Sdd21 at the marker frequency and at f_max (dB), the worst Sdd11 and Scd21 up to f_max (dB), the skew (ps) and each victim's NEXT and FEXT peaks (dB).
- **Same settings or nothing.** The fingerprint holds the preset, mesh, interface, f_max, the link's rise time, the marker, the reference impedance, the stackup, the dielectric model, the app version and the openEMS version.
- **Resolved or not.** The thresholds are registered here, before any gate runs:
  - 1 Ω on a differential TDR level and 0.5 Ω on a single-ended one;
  - 0.05 dB on Sdd21;
  - 0.5 dB on Sdd11, Scd21, NEXT and FEXT where the level is above −50 dB ("not resolved" below it);
  - 1 ps on the skew.

  Gate P4-E kept IL_DB (0.05 dB) and SKEW_PS (1.0 ps), and DB (0.5 dB) by ruling R-13 with Scd21's own floor (−37.7 dB), and set DIFF_OHM at three times the measured noise, 2.2 Ω, with SE_OHM its half (`docs/validation/2026-11-07-p4-e.md`, A-63); P4-F resolved its positive control at them.

### 5.9 Cost and the 2D table

- **The estimate** is Stage 1 §6.4's: jobs × cells × T_max/dt over the calibrated speed. It adds:
  - the jobs broken down into lines, victims and parts;
  - the Debye cell weight when Debye is on, measured by P4-D;
  - a warning past two hours, which advises Draft or a shorter route.

  The gates refit the speed for SI models, as A-38 did for antennas.
- **The 2D table.** Gate P4-A extends the repo's 2D solver `cs2d` to two signal conductors: the C matrix, the odd and even modes, Zdiff = 2·Zodd, Zcomm = Zeven/2 and the coupling k.
  - `cost` lists every straight section of every line with its Z0, or its Zdiff, Zodd and Zeven, its εeff, length and delay, against the target band. That takes seconds, before any run.
  - fit2d checks a pair's coupled sections with the same 3 % rule as v1's single lines.
- **Electrically short routes.** When a route's delay is under a sixth of the link's rise time, `cost` says so: the 2D table and a lumped estimate may answer the question without a run.

### 5.10 GUI and button

- **New** gains the SI kind:
  - the start and end pads;
  - the partner, found by the rule or picked;
  - up to two victims;
  - the interface preset.
- **Cost** shows the 2D table before the estimate. **Run** is unchanged.
- **Results** for SI: the TDR with the target band, the mixed-mode S (or S21 and S11 for a single net) and the crosstalk. The retune works on the route's parts as in v1.
- **Compare** opens a second project and shows the overlays and the deltas table, as in Stage 3.
- **Advanced** shows f_max, the link's rise time, the marker, the target, the dielectric model and the stop window.
- **The button.** A selected track, arc or via pre-fills New with the SI kind, its net and partner, and the net's two pads when it has exactly two IC or connector pads. kipy 0.8.0's `KOT_PCB_TRACE`, `KOT_PCB_ARC` and `KOT_PCB_VIA` give the selection. A selected pair of pads keeps v1's pre-fill.

### 5.11 Validation gates (amends Stage 1 §9)

Stage 4 is validated like Stages 1 and 3: numerical references committed as JSON before the gate's runs and never regenerated during them, each gate with its case, its metric, its threshold and what happens when it fails. A published measurement is a soft note, never a criterion. Each gate gets a short report under `docs/validation/`, with its machine time predicted and measured.

| Gate | Case | Pass | If it fails |
| --- | --- | --- | --- |
| P4-A 2D and formulas (CI) | `cs2d` with two signals against Cohn's exact coupled stripline and Kirschning–Jansen's coupled microstrip (KiCad 9's calculator); the even/odd 4-port's identities; the TDR routine on an ideal line | against Cohn ≤ 0.5 % at thin copper; against Kirschning–Jansen ≤ 3 % at 1 µm and ≤ 5 % at 35 µm; homogeneous stripline FEXT = 0, NEXT's peak = k and a step's Γ exact, to 1e-9; the ideal line read 60.0 then 50.0 Ω | a code bug: blocks Stage 4 |
| P4-B Coupled coupons | a 90 Ω and a 100 Ω microstrip pair on about 0.2 mm, and a homogeneous coupled stripline, at n 2 and n 3 (with SI's timestep floor, §5.3); each also with a 45° bend; a victim cut by the wall against the same victim extended and terminated | Zdiff within 1.5 % of fit2d and 5 % of KiCad's calculator; n 2 against n 3 ≤ 1 %; NEXT's peak within 0.5 dB of the even/odd model; stripline FEXT ≤ −40 dB; the 45° pair within 5 % of its axis-aligned twin; passivity and reciprocity under their flags; the cut victim recorded | against fit2d: a pipeline bug, blocks; n 2 against n 3: n 3 becomes the SI default; the 45° pair: a staircased pair is raised to n 3 or refused; the cut victim: refusal kept |
| P4-C The SI mesh and the TDR | §5.3's rule against the d fill on a straight and an L-shaped pair; a 50→75→50 and a 50→35→50 step line | the rule: \|ΔS\| ≤ 0.01 up to f_max, delay within 0.5 %; the steps: each plateau within 1.5 % of fit2d, Γ within 0.01, delay within 2 % | the rule: the d fill stays; the TDR: refine and repeat |
| P4-D Ports, pulse and loss | the vertical port against the horizontal on a pad coupon; the DC point against the copper's resistive network; a 100 mm lossy line with Debye against scikit-rf's MLine (Djordjevic–Sarkar) | the plateau within 1.5 %, the launch's \|S11\| recorded; DC S within 0.01; Debye: insertion loss within max(0.05 dB, 5 %) over 0.1 GHz–f_max, no DC loss above 0.005, its cell weight and the USB 2.0 fixture's slowdown measured, and §5.3's default rule applied | vertical port not offered (refused as now); DC: §5.4's fallback; Debye: lossless stays the default |
| P4-E Noise floor | one P4-B pair: the same run twice; the whole model shifted by one fine cell; a null edit (a track split into collinear pieces); the gap moved ± d, its odd and even parts registered here | records the noise; passes when the noise proper lies under a third of each §5.8 threshold | the thresholds widen to three times the noise proper |
| P4-F Positive control | the 90 Ω pair with a 5 mm neck-down, and the pair crossing a plane gap | each TDR delta resolved at three times its threshold or more; the plane gap's Scd21 change resolved | the thresholds hide real effects: refine and repeat P4-E |
| P4-G Second solver (optional, the owner's) | EMerge in its own venv, on P4-B's 90 Ω pair | Zdiff within 3 %, Sdd21 within 0.1 dB; "inconclusive" allowed with its cause written | cannot fail Stage 4 alone |

r4 estimates 10–25 machine hours and r3 up to 60; `cost` predicts each run first.

**Fixtures.** Synthetic four-layer boards (signal, ground, power, signal; about 0.2 mm under each outer layer) built with the repo's fixture generator from KiCad's library footprints:
- **USB 2.0 high-speed.** A USB connector, the pads of a six-pin ESD array on the pair, a 22 Ω 0402 series resistor on each leg, and an MCU-like pad pair at the far end. A neighbour single-ended net runs alongside part of the route, with both of its ends inside the region.
- **Its variants:** the neck-down, the plane gap and a 45° bend.
- **A QSPI clock:** single-ended, from a QFN-like pad through a 33 Ω 0402 resistor to a flash's SOIC-8 pad.
- **The gates' coupons,** including a thick synthetic stack for a via coupon if the plan keeps one.

They are the regression tests too.

### 5.12 Plans

Stage 4 runs as five plans. Each is subagent-driven, leaves the suite green in both languages, and is merged to main before the next is written.

1. **The pins and the engine's SI hooks.**
   - Golden pins on the antenna fixtures: model specs, hashes and output bytes.
   - Schema 3 and the `si()` predicate.
   - `cs2d`'s coupled lines and the even/odd 4-port model.
   - The dielectric under each layer, the vertical port, the SI mesh rule, the DC pulse, the Debye dielectric and `window_s`, each written only in SI specs and tested as a pure function.
   - Gate P4-A, in CI.
2. **The SI project.**
   - `new --interface` with the lines, the pair by KiCad's rule, the victims and the ends.
   - The parts as part ports, with the shunt-R rule and the off-chain capacitors per A-27.
   - Cost's 2D table, job breakdown and short-route note.
   - A run that writes the layout Touchstone file.
   - The fixtures.
3. **The SI results.**
   - The uniform grid, the TDR and TDT, the mixed mode, the skew, NEXT and FEXT, and the loss lines.
   - The Touchstone, CSV and PNG outputs.
   - The SI retune and verify.
   - `compare` with the fingerprint and the thresholds.
4. **The gates.**
   - P4-B to P4-F on the fixtures and their reports.
   - The defaults they set: n, the mesh rule, the dielectric model, the thresholds and the 45° rule.
   - The cost refit.
   - P4-G is left to the owner.
5. **The GUI, the button and the docs.**
   - §5.10.
   - The README's SI tutorial on the USB 2.0 fixture.
   - The release check.
   - The acceptance run through the window.
   - The Stage 4 exit record.

### 5.13 Amendments to the Stage 1 spec

These are A-41 onward, each landing in the plan that implements it:
- §2's stage table: Stage 4's design;
- §5.3: the SI dielectric (lossless or Debye, never κ) and no conducting sheet;
- §5.4: the SI mesh rule and the dielectric under each layer;
- §5.6: the vertical port;
- §5.8: the SI pulse;
- §6.3 and §6.4: SI's stop window, T_max and cost lines;
- §7: mixed mode, the TDR and the SI retune;
- §9: gates P4-A to P4-G;
- §10: SI and differential pairs leave the deferred list, and this design's non-goals join it.

### 5.14 Acceptance

Stage 4 is done when all of these hold:
1. The five plans are merged, with the suite green in English and the GUI tests green in pt-BR.
2. P4-A to P4-F have passed, or their fallbacks are in force and recorded; P4-G has run or is recorded as the owner's.
3. One SI project has run end to end through the GUI's code paths offscreen, on the USB 2.0 high-speed fixture:
   - New, with the pair from the button's selection or the pickers;
   - Cost, with its 2D table;
   - Run;
   - a retune of the series resistors with snapping;
   - Apply;
   - Verify;
   - a compare against the plane-gap variant at the same settings.
4. The Stage 4 exit record lists the owner's items.

## 6. Left to the builder

- Module, class, function, option and message code names, within §5's rules.
- These numbers and lists:
  - the grid's size and the TDR's trust floor;
  - the via margin of the SI mesh rule and `max_cell`'s factor within the gate's bounds;
  - the Debye fit's pole count and placement;
  - the shunt-R threshold's exact value;
  - the `DP`/`DM` alias list;
  - the fingerprint's exact fields.
- Whether the skew comes from the TDTs' 50 % crossings or from a phase delay.
- How each plan is cut into tasks, and the fixtures' exact footprints and variants. Each gate coupon's sections must be at least three of the localising TDR's resolution lengths long (about 36 mm at 10 GHz).
- Whether a via coupon joins the gates (via stubs resonate near 24 GHz or above on boards up to 1.6 mm thick, r2), and the summary PNG's panels.

Where this design and the code disagree, the code's tests and the Stage 1 spec win, and the controller rules on it in the plan's ledger.

## 7. Owner items this work leaves open

Each item has the default this design applies:
- **The first interfaces.** Default: a USB 2.0 high-speed pair from the connector through the ESD pads and the series resistors to the MCU, and a single-ended QSPI clock with its series resistor.
- **The interface presets.** Default: `usb2-hs`, `100base-tx`, `se50` and `custom` (§5.1), each simulated to 10 GHz for the localising TDR, with its link rise time and marker. 1 Gb/s and 5 Gb/s links are custom.
- **The TDR's rise times.** Default: the localising 125 ps at 10 GHz, which the readings, the deltas and the gates read, plus the link's own rise time drawn beside it.
- **The dielectric loss.** Default: set by P4-D under §5.3's rule. Debye if it passes and the USB 2.0 fixture's whole run slows down by 1.5 times or less; otherwise lossless, with the formula lines.
- **SI's timestep floor.** Default: 0.6, against v1's 0.8 (§5.3).
- **Conductor loss.** Default: a perfect conductor, with a formula estimate printed beside the results.
- **The selected region for return-path studies.** Default: kept. Plane resonances are not predicted, and a plane-gap crossing is a relative result.
- **Standards' masks and limit lines.** Default: not shipped. Only impedance targets with public sources are shipped.
- **The ideal-driver waveform and IBIS.** Default: deferred.
- **Radiated emission.** Default: a later EMC stage.
- **ESD arrays and common-mode chokes.** Default: their pads are copper and their capacitance is a stated limit; a route ends before a choke. An N-terminal part model is deferred.
- **Net classes and KiCad 10's tuning profiles.** Default: not read.
- **Runtime.** Default: measured and shown by `cost` before every run, with a warning past two hours; none promised.
- **45° and arc pairs.** Default: warned, as W_STAIRCASED; P4-B decides any refusal.
- **Stripline.** Default: validated as a reference in P4-A and P4-B; the GUI's first concern is microstrip pairs.
- **The significance thresholds.** Default: §5.8's values, widened by P4-E.
- **EMerge as P4-G.** Default: optional, in its own venv, with "inconclusive" accepted.
- **Unchanged owner items,** as the Stage 3 exit record §8 lists them:
  - the first push and its identity rewrite;
  - the deny-list review;
  - P0-C;
  - the engine redesign (A-9, A-10);
  - RFsim and NOTICE;
  - the click-through;
  - the plugin identifier;
  - the review of A-13 to A-40;
  - the native review of `po/pt_BR.po`;
  - Linux and the workflows after the push.

## 8. Risks

1. **Runtime on long routes with fine gaps.** With Stage 1 §5.4's rule, r3 estimated a 40 × 15 mm USB pair at about 13 M cells, 2–4 hours per job and 4–8 hours per pair. Mitigation: the SI mesh rule and its gate P4-C, cost before every run, and the warning.
2. **Staircased 45° and arc pairs,** the common real routing, are not validated: mesh calibration read lpf915-45 at 2.77 % in fit2d at n 2 and refused it at n 3. Mitigation: P4-B, and the W_STAIRCASED warning until then.
3. **Loss.** Insertion loss reads optimistic with perfect copper and a lossless dielectric. Mitigation: P4-D's Debye model, the formula lines and the relative label.
4. **The DC pulse on an unusual net.** A model whose port residual does not decay would stop only at T_max. Mitigation: P4-D's check and §5.4's fallback.
5. **The crop's walls** colour a cut neighbour's crosstalk and invent plane resonances. Mitigation: victims inside the region, P4-B's cut-victim case and the stated limit.
6. **TDR levels on short features read as impedances.** Mitigation: the resolution length shown, and short features marked.
7. **A silent v1 or antenna regression.** Mitigation: the antenna's golden pins land first, beside v1's.
8. **Electrically short nets** gain little from a run. Mitigation: `cost`'s 2D table and its short-route note.
9. **KiCad 10's new via tokens** (backdrill, post-machining, buried) are not modelled. Mitigation: they are stated, and the boards still load.
