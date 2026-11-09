# kicad-rf-studio — Stage 5 design: EMC, a first slice

Status: written on 2026-11-09 by the controller, right after Stage 4 closed (main at `d3b036f`), and revised the same day with four critics' findings (fidelity, builder, codebase and scope). The owner is unavailable and asked not to be stopped for questions. Every decision below that the Stage 1 spec, the Stage 2 to Stage 4 designs and the pt-BR design did not already make is therefore a controller recommendation, owner unavailable.

The binding input is the controller's decision record, A1 to A13 (part A) and B1 to B12 (part B), in `.superpowers/sdd/stage5-research/controller-decisions.md`. Where a decision says less than the research it adopts, that research's recommendation fills it in. Where this design goes past a decision, the text says so and calls it a controller ruling. The research behind the decisions is git-ignored:
- `.superpowers/sdd/stage5-scoping/` explains why Stage 5 is EMC, and what is deferred: the GPU engine and the installer.
- `.superpowers/sdd/stage5-research/` holds:
  - r1, the rules and the board geometry;
  - r2, the cavity modes;
  - r3, the emission engine and the probe;
  - r4, the GUI, the button and KiCad's selection API;
  - r5, the references and the gates;
  - the completeness critic;
  - the follow-ups: f1 (the stop rule and a plane pair's Q), f2 (the probe's floor), f3 ("simulate this" and the fingerprint) and f4. f4 measured the review's defaults on three public open-hardware boards, downloaded to a scratch folder and never committed: a two-layer sub-GHz LoRa module, a four-layer LoRa node with an RF shield frame, and a two-layer 2.4 GHz module carrier.

Where a follow-up measured what a first-round finding assumed, the follow-up wins. An independent builder reads this design before the commit.

References: "Stage 1 §x" names a section of the Stage 1 spec (`docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`). So does every § in a list or heading that names that spec. "Stage 3 §x" names a section of `docs/superpowers/specs/2026-10-29-stage3-antenna-placement-design.md`, and "Stage 4 §x" one of `docs/superpowers/specs/2026-11-02-stage4-signal-integrity-design.md`. A bare § names a section of this design.

## 1. Intent and why

EMC is the one use case the owner named first that is still undelivered. The Stage 1 spec's stage table leaves "EMC, a GPU engine, a bundled installer" for later, and Stage 4 §3 defers radiated emission to "a later EMC stage built on Stage 3's engine".

The users are the same hardware engineers, and their boards are sub-GHz radio front-ends and 2.4 GHz modules with PCB antennas. The structures Stage 5 looks for on those boards:
- a clock that crosses a gap in its plane;
- a reference change with no return via near it;
- a fast net along the board edge;
- a shield frame stitched too sparsely;
- a GND/power plane pair whose cavity resonates near a harmonic of the carrier.

Stage 5 is cut so that each part is worth having on its own.

**Part A** (plans 1 and 2) needs no solver.
- A `review` command, a GUI Review tab and KiCad's own selection show those structures on the user's board in seconds. Each finding shows its measured value against its threshold and the threshold's public source.
- A 2D eigen-solve lists the plane pairs' cavity modes.
- A broader rule checker already exists: kicad-happy (MIT), cited as prior art and never reused. Part A therefore differs by native integration, not by breadth: the app's own import of the board, the cavity solve, click-to-select in KiCad, and a "simulate this" handoff.

**Part B** (plan 3) is the core of a relative "emission" project kind on Stage 3's PML and NF2FF engine. It gives the far field at 3 m per volt of drive, for a variant against a base.
- Its two real risks are runtime and the numerical floor. A go/no-go probe measures them, against criteria that §5.13 fixes before the run.
- Plans 4 and 5 (the emission gates, compare, the GUI figure and the acceptance) run only on a go.

The results are relative, as in Stages 3 and 4:
- there is no hardware (Stage 1 §1.1);
- the model is the board alone in free space, with perfect copper and no cables;
- nothing is said about compliance.

A review finding is a measurement against a threshold, never a verdict. An emission number is a transfer function per V or per mA, never a field strength against a limit.

**Success for part A.** From a KiCad board, in seconds, the user gets:
- the tagged nets' gap crossings, reference changes, edge runs and shield-fence gaps, each located, measured and selectable in KiCad;
- the cavity modes near the carrier's harmonics.

**Success for part B, on a go.** The emission of the board's driven chain against a variant (lid off, a filled void, added stitching), with at least one difference resolved, as §5.17 requires.

## 2. What is already decided (binding)

- **Stage 1 §1.1:** openEMS 0.37.0 and CSXCAD 0.7.0 as they are. There is no hardware, and every reference is numerical. From Stage 1 §3.1: the CLI and GUI never import openEMS.
- **Stage 3:**
  - the antenna's whole board in air, with PML_8 on all six faces (Stage 3 §5.2);
  - the NF2FF box and its transform (Stage 3 §5.5);
  - energy accounting through `core/post/farfield.py` (`port_powers`, `efficiencies`, `ETA_LIMIT`);
  - the lid (`core/geometry/lid.py`);
  - the project kinds, told apart by schema;
  - the settings fingerprint;
  - `compare`, with its resolved and not-resolved thresholds set by a noise-floor gate (Stage 3 §5.8).
- **Stage 4:**
  - the golden pins of v1, the antenna and SI (`tests/test_golden_v1.py`, `tests/test_golden_antenna.py`, `tests/test_golden_si.py`);
  - the SI kind and its pre-fill of New (Stage 4 §5.10, as A-66 amends it);
  - net classes left unread;
  - the gate pattern of P4-E: a threshold is kept when its noise is under a third of it, and otherwise becomes three times the noise;
  - ruling R-13: a level floor of 20·log10(3·n).
- **Stage 2:** the GUI client, the KiCad button and its handoff, the one pool thread for slow work, the run folders and events.
- **The pt-BR translation:** every new message code is a catalog code with its pt-BR msgstr, compiled into the committed `.mo` through `tools/catalog.py`.
- **The controller's scoping choice** (`.superpowers/sdd/stage5-scoping/controller-decision.md`): Stage 5 is EMC as a cut-able first slice; the GPU engine and the installer are deferred; the probe decides plans 4 and 5.

## 3. Goals, non-goals and anti-goals

Goals:
- `kicad-rf-studio review BOARD`: rules R1 to R4 (§5.2) over tagged nets, in seconds, writing `review.json`, `review.csv` and `review.png` (A1, A9).
- Plane-pair cavity modes from a 2D eigen-solve, each marked when it lies near a carrier harmonic or a named clock harmonic, gated against the analytic rectangle (A11, A12).
- A GUI Review tab that runs the review on the pool, lists findings and modes beside the overlay, selects the flagged copper in KiCad, and pre-fills New from a finding (A13).
- An emission project kind, schema 4 (B1 to B8):
  - one pad driven, and every other chain end terminated;
  - the far field at 3 m, per V and per mA;
  - the energy balance;
  - a stop rule that reports what it truncates.
- Gate E-A and the go/no-go probe, both with criteria fixed here (B9, B10).
- On a go (B11, B12):
  - "simulate this" variants as explicit geometry overrides;
  - the emission compare, with thresholds from a measured floor;
  - the GUI figure, the tutorial and the acceptance.
- v1's, the antenna's and SI's projects, models and outputs unchanged, bit for bit.

Non-goals (Stage 5 does not do these):
- Compliance in any form: FCC or CISPR limit lines, masks, detectors (quasi-peak, average, peak), a 10 m distance, or a ground-reflection and height-scan model. The model has no ground plane under it. Its stated limit says "no ground reflection" and says nothing about test sites; r5's note on lined sites stays in the research.
- Cable common mode, conducted emission, IBIS or switching-node source spectra, and the enclosure and part bodies beyond the lid.
- Items deferred by a decision:
  - a lossy emission default (B3);
  - Prony tail extrapolation (B7);
  - a stitching-capacitor override (B11);
  - a board-edge fence by default (A7).
- An instant emission retune, and mode-shape images of the cavity. A9's three files are the outputs.
- R5, floating copper and pour fingers (A1). No simulable structure follows from it, KiCad's isolated-copper removal covers it, and r2's pair finder needs no island map.
- Net classes, as in Stage 4.
- The GPU engine and the installer (scoping).

Anti-goals:
- Any change to v1's, the antenna's or SI's model specs, spec hashes or output bytes. `NF2FF_MAX` stays 11 for the antenna.
- A pass/fail verdict, a severity tier beyond the catalog's W_ and I_ prefixes, or an absolute emission claim. Every number carries its relative label (§5.8 fixes the units).
- A rule without a public source, a positive fixture and a negative one.
- A new dependency.
- A fixture that is not synthetic. The public boards f4 measured stay evidence and are never committed. No owner board, file or setting is read.
- Pushing.

## 4. Constraints

- openEMS 0.37.0 and CSXCAD 0.7.0 as installed; Windows 10/11 and Linux; Python 3.14; KiCad 9 and 10 boards. `OLDEST_SUPPORTED` in `core/kicad/board.py` stays as it is.
- No new dependency. numpy, scipy (`scipy.sparse`, `scipy.sparse.linalg.eigsh`, `scipy.special`), shapely and matplotlib are already in. kicad-python stays pinned `>=0.8,<0.9`.
- Fixtures are synthetic boards built by `tools/make_fixtures.py` under KiCad 9's pcbnew, in the isolated profile of Stage 1 §9.1 (A-3's isolation), as Stage 4 built its own.
- Every new message has its pt-BR msgstr in the same commit. Every G_ text keeps the existing rule: no backtick, flag or terminal syntax.
- The review and the cavity solve run off the GUI thread (Stage 2's 50 ms rule).

## 5. Decisions

### 5.1 The review's inputs: tags, f_max and L

**The command:**

`kicad-rf-studio review BOARD [--net PATTERN]… [--project PROJECT] [--f0 F] [--clock F]… [--f-max F] [--edge-k K] [--edge-fence] [--stackup NAME] [-o PATH]`

- The board is read with `new`'s own loader, `cli._load`: the board, its stackup or `--stackup`'s preset, and E_NO_STACKUP without one.
- `-o` is the output folder. As for `compare`, it defaults to the working folder (A9).
- The exit code is 0 whether or not anything is found, and 2 on a refusal or a refused write.
- It starts no worker.

**Tags** (A8). Every finding of R1 to R3 is about a tagged net. The JSON records each tag's source as one of four kinds:
- `flag`: `--net`, a name or an fnmatch pattern, repeatable. In the GUI, it is the nets field.
- `project`: the chain or the lines of the project given with `--project`, or of the project open in the GUI (`core/geometry/__init__.py`'s `chain_of`).
- `pattern`: two conditions must both hold:
  - the name after its last "/" fullmatches r1's regular expression for one of A8's families: CLK, SCK, XTAL, SW, SPI, I2S or USB (r1 §3). SWDIO fails the switch regex, so it is not a switch node.
  - its last "_"-separated word, with trailing digits stripped, is not one of CTRL, NSS, DIO, BUSY, RST, IRQ, EN or CS. So SPI_CS is not tagged, and CLK_GEN is.

  Extending r1's RF deny list to every family is a controller reading of A8. A8 lists that deny list but not r1's rf family.
- `walk`: a net reached from a tagged net through two-pad series parts (`tracer._walk`), or as its differential partner (`tracer.partner_net`), as r1 recommends. The patterns miss MCU_D± behind a series resistor.

**Which sources apply** (controller ruling, builder check):
- `--net` flags, or the GUI's nets field when it is filled, replace the patterns. With no `--net` and an empty nets field, the patterns apply.
- The chain or the lines of a project, given with `--project` or open in the GUI, are always added.
- The walk applies to every tagged net.
- `review.json` records each tag's source as the first source that tagged it, in this order: flag, project, pattern, walk.

Further tagging rules:
- Ground and power nets (`tracer.classify`) are never tagged.
- A flag tags past the deny list.
- Net classes stay unread.

f4 measured that over-tagging is the largest source of false positives: five supply and RC-filtered control nets added 59 R1 segments and 6 R2 hits on one board.

**f_max** (A2) is resolved in this order, and `review.json` records the step that gave it as `f_max_source` (controller ruling, builder check):
1. `--f-max`, when given ("cli").
2. Otherwise a carrier f0, which is `--f0`, a v1 project's f0, or an antenna project's band centre (f_lo + f_hi)/2, gives min(6 GHz, 5·f0) ("carrier"); `--f0` wins over a project's. The cavity marks use that carrier's harmonics (§5.4).
3. Otherwise an SI project's interface `f_max_hz`, capped at 6 GHz ("si"). From plan 3, a schema-4 emission project joins this order: its carrier f0, when it names one, at step 2, and otherwise its band's f_max, capped at 6 GHz, at this step (controller ruling, builder check).
4. Otherwise the default, 5 GHz ("default"): FCC 15.33(b)(1)'s upper measurement frequency for a device whose highest frequency is 500–1000 MHz.

A project's own simulation f_max (`region.f_max`) is never the review's f_max: the review's band is EMC's, not the run's. The GUI resolves f_max the same way, with the open project as `--project` and its f0 field as `--f0` (controller ruling, builder check).

f4 measured that 6 GHz bought no true positive on three public boards. It flagged 59 % of the vias of a 50-mil grid, against 13 % at 5 GHz.

**εr** (A3) is the highest dielectric εr in the board's own stackup. A layer that names no material takes the app's `DEFAULT_EPSILON_R_DIELECTRIC`, 4.5 (`core/kicad/stackup.py`). There is no new constant.

**L** = λ_d/20 at f_max, from the existing `region.coarse_cell(f_max, eps_r_max)` (A2):
- 1.413 mm at 5 GHz and εr 4.5;
- 1.178 mm at 6 GHz;
- 1.545 mm at 5 × 915 MHz.

λ/20 is the structure size of concern for fences and stitching (Bahl and Harper, via the Via fence article; Archambeault 2002). Sources split between λ/20 and λ/10 because of the transmission figures: a single row of vias at λ/20 transmits about −20 dB, and at λ/10 about −10 dB (r5's wire-grid estimate).

**The plane map.**
- A plane is a zone fill (`CopperArea`, source "zone") of a net that `classify` calls ground or power, unioned per (layer, net).
- The review also counts as power a net named like KiCad's power symbols with a decimal point, such as `+3.3V` or `+1.8V`, which `tracer.POWER` misses (f4). `tracer.POWER` itself is unchanged, because v1, the antenna and SI classify with it and their hashes must not move.
- A layer whose zone the importer reported unfilled (W_ZONE_NOT_FILLED) or dropped as hatched (W_COPPER_DROPPED) would read as a void everywhere. R1 and R3 therefore skip the tracks that reference it, with a W_ line that names the layer and points at KiCad's refill.

**The exclusions.** R1 and R3 skip copper inside the hull of any of the following, each hull grown by 3h (r1, A4):
- a connector's pads;
- a footprint with a keep-out zone (`Footprint.keepout`);
- a printed antenna (`tracer.antenna_kind`).

Board-level keep-out rule areas leave no geometry in the import, and the review's output says so.

### 5.2 The rules

Each rule states what it measured, the threshold, the threshold's source and the tag's source. No rule says pass or fail.

**The reference**, shared by R1, R2 and R3:
- **The reference layer** of a tagged track is the copper layer nearest to it by dielectric distance, above or below, on which plane copper of any GND or power net covers at least one point of the track's centre line. For stripline it is the nearer of the two, and a tie goes to the layer below.
- **The reference net** is the net whose planes cover the most of the centre line's length on that layer. A tie goes to a GND net, and then to the first net name in sort order.
- **h** is the dielectric thickness between the track's copper and the reference layer, summed over the slabs between them.

**R1, a tagged net over a void or split in its reference** (A4; W_EMC_GAP_CROSSING).
- **Bare points.** A point of the centre line is bare when no plane of the reference net covers it on any copper layer. That includes the reference layer and any other layer, seen through cut-outs (f4's option (b)). A plane of another net does not cover it.
  - This narrows A4's "a plane on some other layer" to a plane of the reference's net. f4's R1′ accepted any GND or power plane. It is a controller ruling: under A4 as worded, `usb2_hs_gap`'s In2.Cu +3V3 would cover the In1 slot, and R1's positive fixture (A10, r1) would go silent. That slot is also Stage 4's measured positive control (P4-F).
  - A split between two nets on one layer is a void of the reference net, so it counts.
- **Runs that count.** Only contiguous bare runs of at least 1 mm count, compared on lengths rounded to 1 µm. A void that holds exactly one via or plated hole, within that hole's radius plus 0.6 mm, is the hole's antipad and does not count (r1).
- **What a finding reports:** the bare run's length, the void's extent across the track, and L.
- **Source:**
  - LearnEMC: "splitting/gapping a ground plane … is almost always a bad idea";
  - Ansys SIwave's "Net Crossing Split";
  - HyperLynx DRC's "signal traces crossing antipads and plane splits".

  The rule is binary. Only "what counts as a gap" has a number: f4's measured 1 mm.
- **Precision.** f4 measured 62 % (5 of 8) with the any-net look-through, against 25 % for the adjacent-layer form, on three public boards. Its false positives were runs over a deliberate cut-out with a same-net plane under it. The same-net form removes those same false positives, but its precision on those boards has not been re-measured.

**R2, a reference change** (A5; I_EMC_REF_CHANGE, info only).
- At each via of a tagged net, it compares the reference (as defined above) of the net's tracks on either side.
- **Different nets** (for example GND to +3V3): it fires unless a capacitor lies within d of the via whose two pads sit on exactly those two nets. Distance is measured from pad centre to via centre. A capacitor between two reference nets is their return path (r5; Olney's rule 15; TI SPRACP4).
- **The same net on two layers:** it fires when no via of that net joining the two layers lies within d.
- **d** = max(L, 2 mm) (A5, f4), which is 2 mm at the default f_max.
- **What a finding reports:** the nearest return path's distance and the plane pair. §5.4 lists that plane pair as a cavity excitation point.
- **Source:** TI SLLA656 ("within 200 mils, closer is better") and Siemens' "manage reference plane changes". No source derives a number, and the public boards gave R2 no true positive to calibrate against. That is why R2 is info only.

**R3, a tagged net near the board edge** (A6; W_EMC_EDGE).
- d is the distance from the track's edge to the board outline (`Board.outline`) only. Internal plane edges are R1's.
- It fires when 0 < d < k·h, with k = 2 by default (`--edge-k`).
- Each finding prints d, h, k and the share of the ideal return current past the edge:
  - microstrip: ½ − arctan(d/h)/π, which is 14.8 % at 2h (Johnson and Graham's 1/(1 + (x/h)²) distribution);
  - stripline between planes b apart: (2/π)·arctan(e^(−π·d/b)), which is 2.7 % at 2h with b = 2h (r5).

  A6's "(2/π)·atan(k)" is the two-sided share within ±k·h. The one-edge share is printed because it is the one that reads as "past the edge".
- **Source:** LearnEMC, "critical nets should be routed at least 2X from the board edge", the only expert source with a number (r5). f4 measured that k = 3 adds one debatable finding and one false positive over k = 2.

**R4, shield fences** (A7; W_EMC_FENCE_PITCH).
- For each shield in `classify`'s `shields`, the frame line is the hull of the shield's frame pads, taken as `find_lid` takes it.
- The fence is the GND vias within 1 mm of that line (A7, f4).
- The gaps between fence vias are measured along the line, over the stretches the frame pads cover, so the frame's own cut-out is excluded.
- It fires on a gap over L, and prints the pitch as a fraction of λ_d at f_max. It prints no attenuation figure.
- The board-edge fence is opt-in (`--edge-fence`). At every f_max it fired on all three public boards with no true positive, and two of its largest gaps were antenna keep-outs (f4).
- **Source:** λ/20 (Bahl; Harper; Archambeault). The wire-grid estimate (§5.1) stays in this design and the README, and never appears in a finding.

### 5.3 The review's outputs and codes

**`review.json`**, schema 1 (A9). Its keys, with every `*_mm` coordinate in KiCad's frame: mm, y down. The importer stores y up, so y is negated on the way out.

```
{"schema": 1,
 "board": {"path", "sha256"},
 "settings": {"f_max_hz", "f_max_source", "eps_r", "l_mm", "edge_k", "edge_fence",
              "tags": [{"net", "source"}]},            # source: flag | project | pattern:<family> | walk
 "notes": [{"code", "params"}],
 "findings": [{"id", "rule", "code", "params", "net", "layer",
               "ref_layer", "ref_net", "h_mm",
               "at_mm": [x, y], "bbox_mm": [x0, y0, x1, y1],
               "measured": {name: value}, "limit", "limit_source", "tag_source",
               "kiids": {"tracks", "vias", "zones", "pads", "footprints"}}],
 "cavities": [ … ]}                                    # §5.4
```

- **The board's path** is written as given on the command line. The GUI's review writes it as the press gave it.
- **The id** is the rule, "-", and the first 8 hex digits of a sha256 over the UTF-8 of `json.dumps([rule, sorted KIIDs of every kind, [round(x, 2), round(y, 2)]], separators=(",", ":"))`, where (x, y) is the finding's place in KiCad's frame.
  - When two findings share an id, they get "-2", "-3" and so on, in order of place (x, then y). This happens, for example, when one track crosses two voids of one zone.
  - The id survives a rerun while the copper and the settings are unchanged.
- **The KIIDs** come from `Track.uuid`, `Via.uuid`, `CopperArea.uuid`, `Pad.uuid` and `Footprint.uuid`. A zone's KIID covers all its fills.

**`review.csv`** is for the user only; the GUI reads `review.json`. Its format:
- UTF-8, comma-separated, with a header row;
- one row per finding, with the columns id, rule, code, net, layer, ref_layer, ref_net, x_mm, y_mm, measured, limit, kiids and message;
- `measured` holds name=value pairs joined by ";", for example `run_mm=1.000;extent_mm=1.200;l_mm=1.413`;
- `kiids` holds kind:KIID pairs joined by ";";
- the message is the catalog's English text;
- coordinates are mm in KiCad's frame.

**`review.png`** shows the outline, the planes' cover, the tagged tracks, and each finding's number at its place. It is drawn on a matplotlib Figure imported inside the function and saved at 100 dpi, as `outputs.summary_png` does.

**Writing** goes through `outputs.write`, with its own pattern for the three names.

**The codes** form one family, each with its pt-BR msgstr:
- W_EMC_GAP_CROSSING (R1);
- I_EMC_REF_CHANGE (R2);
- W_EMC_EDGE (R3);
- W_EMC_FENCE_PITCH (R4).

The review's other lines get new I_ and W_ codes: its basis, the tags, the skipped layers, the cavity lines, and the relative label "geometry rules, not a compliance verdict". No line advises terminal syntax that a G_ twin would then need.

### 5.4 Plane-pair cavity modes

**The pairs** (A11, r2's pair finder):
- For each pair of copper layers, the cavity outline is the facing area of every pour on one layer and every pour on the other, whatever their nets, minus the pours of the layers between them.
- The outline is split into connected cavities with `shapely.get_parts`. Cavities under 20 mm² are dropped.
- d is the dielectric between the two layers, and εr is the series value through the slabs.
- **Posts:**
  - a GND/power pair has no posts;
  - a same-net pair gets a post at each via or plated pad of its net whose span joins the two layers;
  - decoupling capacitors are excluded (A11), and the output says so. In reality each one is a series RLC post.

**The solve** (A11):
- the operator is a cell-centred finite-volume Laplacian with cut cells on a 0.25 mm raster. Face open fractions are the conductances, and cell area fractions are the mass.
- Edges are Neumann (PMC), and posts are Dirichlet.
- `scipy.sparse.linalg.eigsh` solves it in shift-invert, with the mode count from Weyl's law.
- **Guards:**
  - past about 1.5 M cells the grid coarsens, with a W_ line;
  - slots under 0.5 mm get a W_ line, because a slot under two cells is not resolved (r2 measured a 0.3 mm slot invisible at 0.5 mm);
  - components of the link graph under 1 mm² are dropped before the solve, because they give spurious zero modes.
- The grid is anchored at the outline's minimum corner, which keeps mirror and rotation symmetry exact.

**The via post** (A11, r2's option (c)):
- the nearest node is held at 0;
- its four links are scaled by α = ln(1/0.1985)/ln(h/r), for a barrel radius r under the cell size h;
- for r ≥ h, the cells inside the disc are held at 0.

r2 measured errors of +0.18 % to −0.48 % against the analytic shorted circle, for r/h from 0.1 to 0.8.

**No fringing correction** (A11). The frequencies read high by about 2Δ/a, with Δ ≈ 0.4–0.5 d (Hammerstad's edge extension). That is about 0.3 % for d = 0.2 mm on 50 mm, and about 2 % for d = 1 mm. The limit line states it.

**Near a harmonic** (A11):
- A mode at f is marked for a source s (the carrier, or a `--clock` frequency) when |f − n·f_s| ≤ 0.05·n·f_s for some integer n ≥ 1. The carrier's fundamental is included.
- The carrier is §5.1's carrier f0: `--f0`, a v1 project's f0, or an antenna project's band centre (controller ruling, builder check).
- The ±5 % window covers three error terms: εr's tolerance (±2.5 % in f), fringing (up to −2 %) and the solver (under 0.5 %).
- **Suppressing a clock's marks.** A clock's marks are suppressed for every n where its harmonics lie closer than twice the window's half-width (f_s < 0.1·n·f_s, so n > 10). That is where adjacent windows overlap. One I_ note per clock names the first suppressed n. For example, a 40 MHz crystal's harmonics are 2 % apart at 2 GHz.
- The carrier's marks are never suppressed.

**Outputs.** For each cavity, `review.json` and the CLI's lines give:
- its layers and nets, d, εr, area and post count;
- its modes up to f_max, each with its mark.

**The stated limits**, printed with them:
- lossless: the list says where a resonance may sit, never how high it rises;
- no decoupling capacitors;
- vias as posts only;
- TM0 modes only;
- no fringing;
- εr uniform;
- the fills as saved;
- slots under 0.5 mm unresolved, and posts snapped to the grid;
- cavities uncoupled across splits.

**Runtime.** r2 measured:
- 0.7 s on a clean 50 × 50 mm outline at 0.25 mm;
- 4.7 s with 60 antipads, a slot and 10 posts;
- about 20 s on 100 × 80 mm.

The solve runs inside the review, on the pool in the GUI.

### 5.5 The GUI's Review tab and Select in KiCad

**The tab** (A13, r4).
- It sits at index 1, after Project. The order becomes Project, Review, Cost, Run, Results, Compare, Advanced.
- **Fixed indices.** Inserting the tab moves Cost, Run, Results, Compare and Advanced up by one, so every fixed index changes to `self.tabs.indexOf(<widget>)` in the same commit that adds the tab:
  - in `window.py`, the cost/run switch, `1 if command == "cost" else 2`;
  - in `tests/test_gui.py`, every `currentIndex() ==`, `setCurrentIndex(n)` and `tabText(n)` on the tabs.

  `take_handoff` keeps index 0, which is Project.
- **Contents:**
  - the board field, the nets field (empty for the patterns), the f0 field and a Review button;
  - the status line;
  - the CLI's lines in GUI words, the relative label among them;
  - a findings table (number, rule, net, layer, place in KiCad's frame), with the cavity-mode table under it;
  - `review.png` in a scroll area, as Compare shows `compare.png`.

  The PNG's numbers cross-reference the table. There is no clickable canvas.

  The nets field stands for `--net`, and the open project for `--project`: a filled nets field replaces the patterns, and an open project's chain or lines are tagged either way (controller ruling, builder check). The f0 field stands for `--f0`, and f_max resolves in §5.1's order (controller ruling, builder check).
- **It reads `review.json`** for the findings, the cavities and the KIIDs.
- **It runs on the pool** (A13). The click submits the review. The tick takes the review's Future before its project guard, since a review needs no project. When the review ends, it fills the tables and the picture. A refusal empties the view and shows in GUI words.
- **Its folder** is a fixed `runs.data_dir()/review`, replaced on each review, as Compare's `compare/` folder is replaced on each compare. Nothing is written into the user's KiCad project (A9, r4).
- **A button press** keeps the Review tab current when it is open, and fills its board from the press. Otherwise the press goes to Project, as `take_handoff` does today (A13).

**Select in KiCad** (A13) is a new `button.select(socket, token, board, kiids)` beside `refill`, reusing `_kicad`, `_call` and `_board_path`.
- **Another board open:** it refuses with a new E_KICAD_SELECT_OTHER_BOARD {board, open} ("… so nothing was selected"), with its pt-BR msgstr. E_KICAD_OTHER_BOARD stays Refill's: its text says nothing was refilled or saved.
- **The call.** It clears KiCad's selection, then passes kipy 0.8's `Board.add_to_selection` objects that carry only `.id = KIID(value=…)`.
- **Unknown KIIDs.** KiCad 9.0.7 and 10.0.0 register AddToSelection and skip unknown KIIDs silently (r4, from their `api_handler_pcb.cpp`). A selected count under the number of KIIDs sent therefore means KiCad holds edits not yet saved, and the status line says so.
- **Tests.** `tests/fake_kicad.py`'s `FakeKiCad` gains ClearSelection, AddToSelection and a known-KIID set, and a test pins the duck typing.
- **Fallback.** Should a kipy bump change the method, the fallback is the public getters filtered by id.
- **No zoom.** It never zooms, because `run_action` is documented as an unstable API.
- **When it is enabled:** only while a press gave a KiCad socket and rows are selected. It uses the press's socket and token, never a guessed default.

**"Simulate this" in plan 2** (A13).
- For an R1, R2 or R3 finding, it pre-fills New's SI kind through the delivered Stage 4 code (`control._si_handed`, `si_candidates`, `show_pads`), then switches to Project.
- The Handed object it builds carries the last press's socket and token, so Refill and Select keep pointing at the real KiCad.
- **The status line after the handoff:**
  - it says that the SI run is one relative result, and that a comparison needs a twin board drawn in KiCad: the fixed copper, or the moved trace;
  - for an R3 finding, it adds that SI measures the line, not the radiation from the edge;
  - where SI's classification of the reference net differs from the review's (a dotted power name, §5.1), it names both.
- On a go, plan 5 switches "simulate this" to the emission kind, with the variant of §5.9.

**Tests:**
- the window still fits 1200 × 800 with the seventh tab, in English and in pt-BR;
- the review leaves the GUI thread in under 50 ms;
- Select's calls against the fake;
- "simulate this" lands on Project with Kind and the end pads set;
- `control`'s review against the CLI's `review.json` on a committed fixture.

### 5.6 The emission project

**project.json** (B1):
- It is schema 4, `SCHEMA_EMISSION = 4`, with `"kind": "emission"`. `antenna()` tests `schema == 2` alone, so the kind cannot be schema 2.
- A new `emission()` predicate joins `antenna()` and `si()`.
- **Loading.** `load_project` accepts schema 4, and E_PROJECT_SCHEMA's `expected` becomes SCHEMA_EMISSION. A build from before Stage 5 refuses schema 4 with E_PROJECT_SCHEMA.
- **Checking.** `check_project` tests `emission(data)` first and picks a `_FIELDS_EMISSION` beside `_FIELDS_ANTENNA` and `_FIELDS_SI`. In it, `lid` is a flag, as theirs is, and `overrides` is optional, since a base has none.
- **`overrides` outside schema 4.** `_check` never refuses an extra key, so a separate test after it raises E_PROJECT_FIELD on an `overrides` key in schemas 1 to 3.

**Its fields:**
- the board;
- the chain, in v1's shape, from the driven pad (start) to the terminated end;
- the ports, each with an optional `"R"`;
- the band (§5.7): `f0_hz` or none, `f_lo_hz` and `f_max_hz`;
- `t_max_s`;
- the far-field list (§5.8);
- the optional near-field plane (§5.8);
- the preset, the mesh and the gates;
- the lid and `lid_height_mm`;
- the stackup;
- the region, the air gap and the boundary `pml_8`;
- the variant's `overrides` (§5.9).

**The model** is Stage 3's: the whole board in air, with PML_8 on six faces, an air cell of λ/20 at f_max (`region.air_cell`), and solid copper. It is a verify-style job (r3):
- every part sits at its value as a grid element, as `verify_spec` places them;
- one port is driven;
- every other non-part port is a termination. `csx.build_csx` already makes a port that is not excited a 50 Ω lumped or curve port.
- **The termination's R.** A termination is 50 Ω unless the project's port carries an optional `"R"` (r3 item 3). The key is written only in emission specs (B11), so no other kind's hash moves. Advanced edits it, since AdvancedView edits any leaf (r4).
- **Decoupling capacitors.** A capacitor whose reactance is at most Z0/5 at the pulse's centre is copper (`core/model/parts.py`), as in the antenna and SI kinds (A-27: `role` with `place` board or far, the reactance net of ESL).

**Which kind checks an emission project joins.** `antenna()` stays `schema == 2`.
- These become `antenna(p) or emission(p)`:
  - `region.py`'s board region and air gap;
  - `build_geometry`'s whole-board ports;
  - `model_spec`'s "boundary";
  - `prepare`'s `small`;
  - `cost_notes`' split;
  - the speed refresh guard;
  - `waves`' band grid.
- These stay antenna-only: load's `check_antenna` and `adopt`; `join`; sheet copper; the flat window; and `check_project`'s band and far-field checks.
- `excitation()` tests `emission()` before `antenna()`.
- The far-field box comes from `verify_spec(far_field=…)`, since the parts are in the grid.
- Plan 3's first task lists every `antenna(` call at its head commit and assigns each to one side. The three golden suites run after each such edit.

**An emission run is three jobs in one run folder:**
1. a setup job on `model_spec`'s spec: the mesh gates, dt and the operator dump. A blocked gate exits 3, as `run`'s does.
2. the one driven job, on `verify_spec(spec, parts, dump, dt, far_field=…)`, with the source port excited and the emission stop branch;
3. the NF2FF transform.

`spec_hash`, the null check of §5.13 and the fingerprint all use `model.json`, which is `model_spec`'s spec before `verify_spec`. `cost` counts jobs 1 and 2. The probe records the setup's time and the transform's time apart.

**The dielectric is lossless** (B3): every κ is 0, as in an SI spec. Only a lossless model with no resistive grid part makes energy closure a check rather than a bound (r3). The probe's plane-pair run records its fitted Q values as evidence for revisiting this in plan 4.

**Every emission-only key** is written only in emission specs, so no other kind's spec hash moves (B11). These keys are the kind's marker in the spec, the far-field cap, the stop branch's key, a port's `"R"`, the near-field plane and the overrides.

**The CLI:**

`new BOARD --start REF.PAD --end REF.PAD --emission (--f0 F [--f-max F] | --band F_LO:F_HI)`

It writes through a new `cli.new_emission`. `_new` changes as follows:
- `--f-max` is an SI option, or an emission option alongside `--emission` and `--f0`;
- `--band` goes with `--antenna` or with `--emission`;
- `--emission` together with `--antenna` or `--interface` is E_NEW_KIND.

For an emission project, `--band F_LO:F_HI` is the carrier-free band: f_lo = F_LO, f_max = F_HI, and the air gap is λ/4 at F_LO. §5.7's default 1–6 GHz is `--band 1e9:6e9`, and the GUI pre-fills it.

Until a go:
- `--emission` is hidden from the usage line;
- E_NEW_KIND's text, with its pt-BR, does not name it;
- the GUI has no emission kind (B10).

### 5.7 The band, the excitation and the stop rule

**The band** (B2):
- **With a carrier f0:** the harmonics only. f_lo = 2·f0, and the air gap is λ/4 at 2·f0 (`region.air_gap`), about 41 mm for 915 MHz. The fundamental is the wanted signal, not emission, and P3-C validated λ/4 at f_lo. f_max is min(6 GHz, 5·f0), A2's rule capped at 6 GHz as scoping item 4 caps it, and `--f-max` overrides it.
- **Without a carrier:** `--band`. The default is 1–6 GHz, with a 75 mm gap (λ/4 at 1 GHz).
- **The pulse** is `spec.pulse(f1, f_max)`, with f1 = f_lo/1.3 rounded down to 3 significant digits, as `pulse_band` rounds it, and f2 = f_max unrounded (B2).
  - f2 is f_max itself, not the antenna's 1.2·f_hi, so the air cell and the NF2FF frequencies stay inside the pulse.
  - The emission band is [f_lo, f_max], the upper part of the pulse band [f1, f2]. The NF2FF list and closure use the emission band only, as §5.8 says (controller ruling, builder check).
  - The pulse's band edges sit about 19.5 dB under its centre in amplitude. §5.8's normalisation removes that.

**T_max** applies `antenna_t_max`'s rule to the emission pulse: 2·t0 + 60/f_c, where f_c is the pulse's centre, rounded up to a whole ns.
- It is 31 ns for the probe's 1.40–3 GHz pulse (t0 = 1.79 ns).
- `antenna_t_max` itself takes an antenna band, so the rule is applied to the emission pulse directly, not by calling that function.
- It is a project field, so a ringing structure's T_max can be raised by hand, as R8-1 did in Stage 4. The probe never raises it (§5.13).

**The stop rule** (B7) gains an emission branch, chosen by a key that only an emission excitation carries.
- **No flat verdict.** f1 fed synthetic records through `stoprule.stop_rule`. Under today's rule, a ringing plane pair ends "flat" at about 7.9 ns, keeping 12–29 % of its resonant amplitude. SI's ring rule never applies to a band pulse: `stoprule.ceiling` and `ring` act only on an excitation with `window_s`.
- **The other verdicts.** Diverged, growth and converged stay as they are. With none of them, the job ends at T_max as "t_max", which KEPT keeps, with W_JOB_T_MAX.
- **The tail fit at the end of the job** (f1's option (c), "a Q_fit per dominant mode") runs on every port's u, not only the excited port's, so that a cavity mode coupled weakly into the source but strongly into another port is still seen (controller ruling, builder check):
  1. Find the tail's spectral peaks: the DFT of each port's u over [2·t0 + 2 ns, T], keeping every local maximum in the pulse band within 20 dB of the largest. The peaks are the union over the ports.
  2. For each peak f_r,k, take a short-time DFT at f_r,k over successive 2 ns windows. This gives an amplitude envelope in dB.
  3. Fit a least-squares line to the envelope past 2·t0 + 2 ns. This gives Q_k = 8.686·π·f_r,k/|slope|, with the slope in dB/s.
  4. The truncation factor is factor_k = e^(−π·f_r,k·T/Q_k), with T the job's end time in simulated seconds. Each f_r,k takes the worst (largest) factor_k over the ports.
  5. Every (f_r,k, Q_k, factor_k) goes into the job's record. A W_ line is written for each factor over 0.01.

  The window lengths and the 20 dB peak cut are a controller construction of f1's option (c).
- Prony tail extrapolation is deferred (B7).

**What the factors gate.**
- A frequency is **truncated** when, for some k with factor_k > 0.01, |f − f_r,k| ≤ 50·f_r,k/Q_k. That is the ring's single-pole −40 dB width, a controller construction of f1's per-frequency exclusion.
- A frequency is **closure-judged** when it is not truncated and §5.8's other conditions hold. Truncated frequencies are reported as such and not judged.

f1 computed that closure within 0.02 needs T ≥ 9.2·Q/ω at a cavity mode: 241 ns for a 50 mm plane pair at Q 232, far past any 2 h run. Judging closure there would only measure the truncation.

### 5.8 The far field, normalisation and closure

**The NF2FF list** (B5) covers the emission band [f_lo, f_max] only (controller ruling, builder check):
- the harmonics n·f0 for n ≥ 2, up to f_max;
- plus every point of a 100 MHz grid from 1 to 6 GHz that lies inside [f_lo, f_max];
- at most 64 frequencies.

No point below f_lo is computed or closure-judged, because the PML's λ/4 distance is validated only at f_lo (P3-C, §5.7). For the probe, the list runs from 1.83 GHz to 3.0 GHz.

The cap is emission-only, beside `csx.NF2FF_MAX`, which stays 11 for antenna specs, and `_FIELDS_ANTENNA`'s check stays with it. r3 estimated the FD accumulation at about 2 % of the run at 64 frequencies, and 0.35–0.67 GB a job. The probe measures both.

**The optional near-field plane** (r3 item 7, scoping G4).
- It is one FD H dump (dump_type 11) on a z-plane 1.5 mm above the highest model metal, which is the lid plate when the lid is on.
- It covers the harmonic frequencies only, at most 11.
- It is off by default. It is a project key written only in emission specs and kept in the fingerprint (B11), and Advanced sets it (r4).
- It writes its file to the job's folder. No Stage 5 figure reads it, and the probe leaves it off.

**The 3 m field** (B6).
- It is the worker's 1 m transform multiplied by 1/3. `worker._far_field` passes no radius, so openEMS uses 1 m.
- The scaling is exact in the far field, because openEMS's field prefactor is j·k·e^(−jkr)/(4πr). The far field holds at 3 m: 2D²/λ is about 0.2 m at 6 GHz for a 70 mm diagonal.
- |E|max(f) is the maximum over the 5° sphere of √(|E_θ|² + |E_φ|²), with its θ and φ.

**Normalisation** (B4). Both forms come from `port_powers`' DFT, whose scale P3-A tied to the FD dumps (η_rad 1.0005).
- **Per V** of the source port's incident wave, U_inc = (U + 50·I)/2, the forward wave of a 50 Ω source. A variant that loads the source differently therefore compares fairly.
- **Per mA** of the port current I.

**Energy closure** (B8). P_in is B8's: P_in = P_inc = P_rad + ΣP_term + P_ref.
- ε(f) = 1 − (P_rad + ΣP_term + P_ref)/P_inc, where P_term,k = −½·Re(U_k·I_k*) at each terminated port, and P_ref is the source port's reflected power.
- The limit is |ε| ≤ 0.02 (ETA_LIMIT − 1, P3-A's η ± 0.02).
- A frequency is closure-judged only when all three conditions hold:
  - it is not truncated (§5.7);
  - P_acc ≥ 1e-3·P_inc (P3-A's conditioning lesson, r3);
  - the model has no resistive grid part, whose loss no probe measures (r3).
- **The "closure-backed" label.** P_rad/P_in is labelled closure-backed only where P_rad/P_inc ≥ 3·|ε|, and otherwise "from NF2FF only". This is r5's test, rewritten on B8's P_inc base. With 50 Ω loads, P_rad can be a thousandth of P_acc, and a 2 % residual then says nothing about it.

**What a run gives**, besides v1's run files:
- a CSV with, for each NF2FF frequency:
  - |E|max at 3 m per V and per mA, with its direction;
  - P_inc, P_acc, P_rad and each P_term;
  - ε, and whether the frequency was closure-judged or truncated;
- the job's (f_r, Q, factor) list;
- lines that print the band, the harmonics' levels and the closure.

The GUI's figure is plan 5's.

**Units.** The CSV's columns and the figure's axis are in dB re 1 (V/m)/V and dB re 1 (V/m)/mA at 3 m, each with the relative label. They are never in dBµV/m. There is never a horizontal limit or margin line, and never a standard's name on a result. A test scans the new emission and review msgids, and plan 5's figure labels, for "dBµV", "dBuV", "FCC", "CISPR", "margin" and "pass". The only allowed match is the label "not a compliance verdict".

**The relative label and the stated limits** go on every emission result:
- the board alone in free space: no ground reflection, cables, enclosure or part bodies;
- copper a perfect conductor and the dielectric lossless: a cavity's Q reads 5–40 times a real FR-4 board's (f1);
- one lid, drawn walls only;
- the maximum over a 5° sphere, not a turntable;
- peak phasors, which a per-V or per-mA ratio cancels;
- truncation as reported;
- results compare variants under identical settings, and predict no measured field.

### 5.9 "Simulate this": the base and its variant

On a go, plan 5's "simulate this" makes an emission pair from a finding (B11, f3). Plan 3 builds the overrides, as the plan table puts them there, so that the CLI and the gates can use them.

**The pair** is two project folders on the same board: base and variant.
- The variant's project.json holds an explicit `overrides` list of geometry, computed when the variant is made. The list holds polygons and via coordinates, never rules. The rule's parameters are kept only as metadata.
- The overrides' clearance is checked again at every load. W_BOARD_CHANGED already flags a board edited since.

**The override entries** are in the importer's frame (mm, y up). The conversion from `review.json`'s KiCad frame is done once, when the variant is made:

```
{"kind": "fill", "layer", "net", "polygon_mm": {"exterior": [[x, y], …], "holes": [[[x, y], …], …]}, "from": <finding id>}
{"kind": "via", "at_mm": [x, y], "diameter_mm", "drill_mm", "layers": [top, bottom], "net", "from": <finding id>}
```

**The variants:**
- **The lid:** the project's existing `lid` flag.
- **A filled void** (R1): the void the finding names, filled with the reference plane's net, minus every other-net copper on that layer grown by a clearance.
  - Only a same-net void can be filled. A split between two nets cannot be filled without a short.
  - f3 showed that filling `usb2_hs_gap`'s void reproduces `usb2_hs`'s copper pieces polygon for polygon, and its mesh line for line.
- **Stitching vias at pitch p.** p defaults to L. Three cases:
  - R2 (same-net references only): one via of the planes' net at the first clear point within d of the via;
  - R3: a fence along the edge between the net and the outline;
  - R4: ceil(gap/p) − 1 equally spaced vias in each gap, with their neighbours' diameter, drill, layers and net.

**Added vias** cut an antipad in other-net zone fills only, as KiCad's refill would. A via that would cross a track, a pad or a graphic of another net is refused with a W_ line. A rod spans every layer, and `connectivity` reports shorts only for chain nets: f3 found a naive via on `lpf915` landing on RF_B copper.

**What has no in-app variant:**
- R3's trace move. Its in-app variant is the edge fence, and moving the trace is named as "draw a copy in KiCad".
- Different-net splits (R1) and GND-to-power changes (R2).
- A stitching capacitor, which is deferred (B11).

**Where it applies:** in `pipeline.load`, behind `emission(project)`, before `build_geometry`, as `tracer.adopt` edits an antenna's board there.
- The board's `areas` take new `CopperArea` values with source "override".
- Its `vias` take new `Via` values whose uuid is "override-<n>". Via has no source field, and `board.py`'s dataclasses stay as they are.
- `copper_pieces`, `via_rods`, the mesh and `model_spec` read neither field and need no edit.
- Overrides apply to the emission kind only, so no v1, antenna or SI spec hash moves (B11).

### 5.10 The fingerprint and compare

**The emission fingerprint** (B11, f3). Plan 3 builds it, for the probe's null guard (§5.13).
- **It leaves out** `lid`, `overrides`, `results`, `verify`, and the board's path and sha256. The lid pair, the override pairs and two-board pairs (a moved trace, a different-net split) therefore compare.
- **It keeps:**
  - `lid_height_mm`;
  - `ends`: the driven pad and the terminations with their R, so a different source is refused, as SI's `ends` are;
  - the preset, the mesh and the region;
  - the band, with f0 and f_max;
  - `t_max_s`, the air gap and the boundary;
  - the far-field list and the near-field plane;
  - the stackup and the copper model;
  - the app's version and openEMS's.

**`compare_projects`' third kind** is plan 4's, as are its thresholds (B12). Plan 4's first task adds an antenna compare's printed lines and an SI compare's printed lines to the pins, before `compare_projects` is edited. Then:
- A mixed pair is refused with E_COMPARE_KIND.
- `I_COMPARE_BASIS` is unchanged. A new `I_COMPARE_OVERRIDES {role, count, kinds}` line is printed only for an emission pair, after each I_COMPARE_BASIS, so the output says what differs.
- E_COMPARE_KIND's and G_COMPARE_KIND's texts name the emission kind only when plan 5 releases it, each with its pt-BR msgstr.
- Both sides must have the same NF2FF frequency list and sphere grid, and are refused otherwise.

**The floor's data.** n(f) is the maximum over the 5° sphere of |E_b − E_a|.
- The complex E_θ and E_φ are read from each run's NF2FF `.h5` at the finest grid, scaled by 1/3, and divided by U_inc(f).
- floor(f) = 20·log10(3·n(f)), rounded up to 0.05 dB.
- In plan 3, one function computes this, and a probe tool in `tools/` (like `tools/p3a.py`) calls it for criterion 2. Plan 4's compare reuses the same function.

**The deltas** (plan 4):
- ΔE_max at 3 m per V, at each harmonic and at each NF2FF frequency;
- ΔP_rad/P_in, where closure-backed.

A delta resolves when it exceeds its threshold and the higher of the two levels lies above floor(f) (§5.12, E-B). A level under the floor reads "at or below the floor". A lid's effect then reads as at least the lid-off level minus the floor.

### 5.11 Cost

- `cost_notes` takes the antenna's branch for the emission kind:
  - the board, air and PML split (`cell_split`);
  - each PML cell weighted by `runs.PML_WEIGHT`;
  - the speed scaled by `runs.small_speed(pool)`.

  It counts the setup and the driven job (§5.6). It adds a W_ line past `LONG_RUN_S`, two hours, as W_SI_LONG_RUN does.
- The RAM line counts cells, not the FD dumps (its existing ponytail). The probe records peak RAM and the dumps' bytes, and plan 4's refit adds them if the line misleads.
- `SMALL_SPEED` and `PML_WEIGHT` were fitted on models of about 1.3 M nodes (`docs/validation/2026-11-01-p3-refit.md`). r3 estimated the emission models at 3.5–8 M nodes. The probe measures the ratio, and plan 4 refits it (B12).

### 5.12 Validation gates (amends Stage 1 §9)

Stage 5 is validated like Stages 1, 3 and 4:
- numerical references are committed as JSON before the gate's runs, and never regenerated during them;
- each gate has its case, metric, threshold, and what happens when it fails;
- a published measurement is a soft note, never a criterion;
- each gate gets a short report under `docs/validation/`, with its machine time predicted and measured.

| Gate | Plan | Case | Pass | If it fails |
| --- | --- | --- | --- | --- |
| E-E Cavity (CI, plus one recorded run) | 2 | (1) a 50 × 30 mm rectangle at εr 4.4, aligned and rotated 30°: all 11 non-DC modes up to 6 GHz against f_mn = c/(2√εr)·√((m/a)² + (n/b)²), and exactly one mode under 1 MHz with no posts; (2) a circle of radius 25 mm against Bessel's x′_mn, first six modes; (3) the circle with a centre post, r 0.1–0.2 mm, against the root of J0′(kR)·Y0(kr) − Y0′(kR)·J0(kr), and no DC mode; (4) symmetry: the mirror and the 90° rotation of an asymmetric outline with posts; (5) the via-post shift on 50 × 30 mm; (6) an L of three 25 mm squares, self-convergence only; (7) `usb2_hs` against `usb2_hs_gap`, and `lpf915`'s stitched pair | (1) and (2): each mode within 0.5 % at h 0.25 mm (r2 measured 0.016 % and 0.010 %); (3) within 1 %; (4) identical lists to 1e-9 relative; (5) a post on the (1,0) nodal line leaves f10 within 0.1 %, mirrored positions give identical lists, and a post moved toward the antinode strictly lowers the post mode; (6) the first eigenvalue's differences shrink at least 2× per halving of h, with no remembered reference; (7) the slot lowers the first non-DC mode by at least 5 %, `lpf915`'s pair has no DC mode, and the lists are pinned as golden | a solver bug: blocks plan 2 |
| E-E openEMS confirmation (recorded, the controller's run) | 2 | a 50 × 30 mm PEC plane pair, d 0.8 mm, lossless εr 4.4, in air with PML about 15 mm off; one 50 Ω port between the planes about (2, 2) mm in from a corner; SI's DC pulse to 6.5 GHz and its ring rule, which ends because a port across the pair damps it (f1 computed a loaded Q near 10 for such ports on a 50 mm pair); a hand-written spec, as `tools/p3a.py` writes P3-A's | Δ = 0.412·d·(εr + 0.3)/(εr − 0.258), Hammerstad's edge extension at W/d → ∞; the outline is buffered by Δ with mitred corners. Every peak of Re Z_in from 1 to 6.5 GHz that stands more than 3 dB above its neighbouring minima is matched to the nearest eigenfrequency of a mode that is not nodal at the port, and each matched pair agrees within 2 %. An unmatched peak or eigenfrequency is recorded, not failed. The unbuffered offset is recorded | not a blocker for part A: the offset is recorded as the measured fringing bias and named in the cavity's limit line; the solver is unchanged (A11) |
| E-A Emission closed forms (B9) | 3 | both cases are hand-written specs, as `tools/p3a.py` writes P3-A's, carrying the emission excitation key, so the emission stop branch, the NF2FF cap and §5.8's post code (3 m scaling, U_inc and I normalisation) run unchanged on them; only the board import and the mesh are bypassed. (1) P3-A's 12 mm z-dipole (`tools/p3a.py`'s `dipole`), a 1 mm gap port, vacuum, PML_8 at λ/4, judged over 1–2.5 GHz (l ≤ λ/10); (2) a 5 × 5 mm square PEC loop of one-cell strips at 0.1 mm cells, a 50 Ω port across a one-cell gap, judged at 0.5, 1.0 and 1.5 GHz (perimeter ≤ λ/10) | (1) E_max·r/I_in within ±0.5 dB of η·tan(kL/4)/(2π), the sinusoidal current's feed-referenced form (the Hertzian form is about 6 dB off for a gap-fed wire, r5); the identity \|E\|·r = √(η·D·P_rad/(2π)) within ±0.05 dB; η_rad = 1 ± 0.02 where P_acc/P_inc ≥ 1e-3; (2) E_max(3 m)/I_port within ±0.5 dB of 1.3169e-14·f²·A/r, A from the mesh-snapped centre line; no η or closure on the loop: r5 computed P_acc/P_inc ≈ 3.2e-4 for a 10 mm loop at 1 GHz, and a smaller one is worse | a pipeline bug (normalisation, radius, peak or RMS): blocks the probe until found. With no pipeline bug reproduced by a new test, the failure is a no-go for part B: Stage 5 closes after plan 3 through §5.13's no-go branch, and the probe is not run (controller ruling, builder check) |
| E-B Floor and thresholds | 4, on a go | on the probe's front-end fixture, no-op pairs: a repeat (expected bit-identical, a sanity check); the whole board shifted one fine cell in x and in y; the collinear-split null in each lid state; the NF2FF box two cells further in. The null's spec hash must differ from its base's, and its fingerprint must equal it | records the noise per key: ΔE_max per V at each frequency, and ΔP_rad/P_in; design values 0.5 dB each, kept when the noise lies under a third of them; floor(f) = 20·log10(3·n(f)), n(f) the largest vector difference over the pairs (§5.10), rounded up to 0.05 dB | a threshold widens to three times its noise, rounded up to 0.05 dB (P4-E's rule) |
| E-C Positive controls | 4, on a go | a 50 Ω microstrip, terminated in 50 Ω, over a solid plane, against the same board with a slot across its path (one board and its fill override); the same microstrip at 1h and at 10h from the board edge (two boards) | the variant's ΔE_max at a harmonic in band at least three times the ΔE threshold, the variant higher, its level above floor(f); every run valid; `review` flags the gap's board and the 1h board, and not their twins | the gap: the thresholds hide real effects, so refine and repeat E-B. The edge, pre-registered: R3 keeps its literature basis, its text says that a board-only model cannot show the cable mechanism behind it (r5), and Stage 5 does not fail on it |
| E-D Lid and fence pitch | 4, on a go | the front-end fixture with the lid off; with the lid on and the frame's fence at p = λ_d/5, λ_d/10 and λ_d/20 at the 3rd harmonic (the R4 densify override); r3's closed ring with the termination inside the can, labelled a physics datum, never a floor | lid on below lid off by a resolved Δ at every closure-judged harmonic where lid off stands above the floor (or lid on reads "at or below the floor"); E_max non-increasing as p shrinks, each step resolved or at or below the floor | refine and repeat E-B once; a second miss keeps that variant out of "simulate this" and records it |

E-A's criteria, its row's Pass column, are committed as JSON and frozen before its run, as the probe's are (§5.13). No tolerance or closed form changes after the run (controller ruling, builder check).

The soft references, never criteria:
- for E-D: the wire-grid fence slope (about −3, −10 and −20 dB at λ/5, λ/10 and λ/20), and Ye et al. 2001's FDTD stitching curves;
- Ansys's 5–10 dB for stitching capacitors across a split;
- for E-C: In Compliance's "more than 20 dB in some harmonics" for an edge net, and Leone 2007's trace closed form.

Machine time:
- E-E's run: 0.5–2 h;
- E-A: 1–2 h;
- the probe: about 5 h (§5.13);
- E-B to E-D: 25–50 h (the scoping estimate).

`cost` predicts each run first.

### 5.13 The probe and the cut points

The probe (B10) runs in plan 3, after E-A passes.

**Pre-registration.**
- The probe's criteria are fixed here, before any run, and committed as JSON beside the fixtures, as P4-E's were. The JSON holds the judged harmonics, T_max, the 2 h budget, the 20 dB margin, the statistic and the incomplete rules.
- Before the first run, the probe's fixtures, their spec hashes, the criteria JSON and the code under test are frozen at a recorded commit.
- There is one attempt. A rerun is allowed only for a pipeline bug that a new test reproduces on the first record, and both records are kept.
- After the first run, no fixture, band, preset, T_max or criterion changes. A changed probe is a new probe, with its own record, and it can never overturn a recorded no-go inside Stage 5.

**The fixture** (f1, f2, r3) is a 50 × 50 mm synthetic LoRa-like board on `STACKUP_4L`, with 1 oz copper on every layer. `stackup.COPPER` is the only weight the mesh rule is validated for.
- **F.Cu** holds:
  - a radio-like source pad;
  - a C–L–C π low-pass with `lpf915`'s values;
  - an edge connector, J1, terminated in 50 Ω.
- **The RF line** from the filter to J1 has one arc bend, a KiCad arc with a radius of at least 3 mm, and beside it a straight segment at least 5 mm long, which N_on splits (controller ruling, builder check).
- **Inner and bottom layers.** In1.Cu, In2.Cu and B.Cu are GND, stitched at about 3 mm (r3).
- **Vias along the RF line** (r3). Their pitch is left to the builder (§6).
- **The shield.** A shield frame of about 20 × 15 mm covers the source and the filter. Its opening is where the line leaves for J1, and its lid is 2.5 mm high.
- **No switch.** r3's switch is left out: a part with three or more pads has no chain path (Stage 4 §5.1).
- The carrier is 915 MHz.

**The band:**
- f0 is 915 MHz, f_lo is 1.83 GHz, and `--f-max` is 3 GHz.
- **The probe's harmonics** are the 2nd and 3rd, 1.83 and 2.745 GHz.
- The pulse runs 1.40–3 GHz, and T_max is 31 ns. T_max is written in the criteria JSON and never raised.
- The air gap is about 41 mm, and the preset is Normal.
- f2 estimated 1.25 h a structure in this band, against 2.75 h at 6 GHz.

**Four runs**, each alone at pool 1, so that each wall time is its own:
1. **P_off**, the lid off.
2. **P_on**, the lid on.
3. **N_on**, the null with the lid on, in P4-E's form: the straight segment of the RF route beside the arc bend is split into collinear pieces. The copper union is unchanged, only a line or two is added to the mesh, and the arc itself is never re-split (controller ruling, builder check). Before the run, in memory, its spec hash must differ from P_on's, and its fingerprint must equal P_on's. A split that leaves the hash equal moves to another point of that straight segment.
4. **P_pp**, the lid on (a controller choice; B10 and f1 leave the lid state open). In2.Cu becomes +3V3, and nothing else changes.
   - B.Cu stays GND, so the board holds two GND/+3V3 cavities with the same planar modes: In1/In2 at 1.04 mm, and In2/B.Cu at 0.2 mm. A 100 nF capacitor bridges +3V3 to GND, and the ports stay GND-referenced.
   - The modes, at about 1.41, 2.0 and 2.83 GHz, sit by the harmonics. f1 computed a lossless Q of 232–1789 for them.
   - A go measured without P_pp would be reversed by the owner's first four-layer board.

**Go, when all three criteria hold** (B10):
1. **Runtime.** Each run's driven job, at the fixed T_max, ends with the emission stop rule's verdict (§5.7) in at most 2 h of wall time, measured from the job's start to its end. The setup and the NF2FF transform are recorded apart, and every (f_r, Q, factor) is recorded. A controller addition to B10: a run that diverges or grows, or whose mesh gates block it, has no field to judge, and counts as incomplete, so no go.
2. **The floor.** At each of the probe's harmonics, whatever their truncation: L_off(f) − floor(f) ≥ 20 dB.
   - L_off = 20·log10 of the maximum over the sphere of |E| at 3 m per V on P_off.
   - n(f) is the maximum over the sphere of the vector difference |E_N_on − E_P_on| at 3 m per V (§5.10).
   - floor(f) = 20·log10(3·n(f)), rounded up to 0.05 dB (R-13's form).
   - The result is "incomplete", and so no go, when n(f) = 0 at a probe harmonic, when the null's mesh equals its base's, or when a run is missing.
   - L_on − floor is reported beside it.
3. **Closure.** |ε| ≤ 0.02 at every closure-judged frequency of every run (§5.7, §5.8). Every closure-judged frequency lies in the emission band, 1.83 GHz to 3.0 GHz: no point of the pulse below f_lo is computed or judged (controller ruling, builder check). A frequency that is not judged is listed as such.

**What P_pp can decide.**
- It fails the probe if its driven job overruns 2 h, or if closure fails at any frequency where its rings allow judging.
- Where its rings truncate a harmonic, B10 does not let that harmonic fail the probe. The record then states that a four-layer board with a power pair truncates that harmonic.

**What the probe records**, for each run:
- the cells, and their board, air and PML split;
- dt and the steps;
- the verdict and its time;
- every (f_r, Q, factor);
- the wall time and the MC/s, with the measured ratio for the speed refit;
- peak RAM, the dumps' bytes, and the setup's and the transform's times;
- per frequency: |E|max per V and per mA with its direction, P_inc, P_acc, P_rad, each P_term, ε, and whether the frequency was closure-judged;
- `cost`'s prediction against the measured run.

**On a go:** plans 4 and 5 run (B12). Plan 5 switches "simulate this" to the emission kind, and releases the kind in the GUI and the CLI help.

**On a no-go** (B10):
- Stage 5 closes after plan 3, and the record names the criterion that failed.
- The emission kind stays unreleased. It is off the GUI and the CLI help; its code, E-A and the probe's record are kept; and its gates wait for the GPU engine.
- Plan 3's closing task adds a W_EMISSION_UNVALIDATED line, which names the probe's record, to `new --emission` and to every load of a schema-4 project.
- "Simulate this" stays on the SI kind.
- Plan 3's amendments are listed as dormant in the exit record (§5.16).

**E-A's no-go** takes this same branch (controller ruling, builder check). When E-A fails and no new test reproduces a pipeline bug (§5.12), the probe is not run, the exit record names E-A as the gate that failed, and W_EMISSION_UNVALIDATED names E-A's record in place of the probe's.

**Whatever the outcome:**
- Part A, delivered by plans 1 and 2, stands whole.
- r3's closed-ring null moves to E-D as a shield datum labelled physics (B10). A sealed PEC enclosure passes no field in the Yee update. The app's lid, whose walls stand on the frame pads from the top copper up, leaks through the substrate between the fence vias. That leak is R4's physics, not a floor (f2).

### 5.14 Fixtures

The fixtures follow A10:
- they are synthetic, with a positive and a negative per rule;
- `tools/make_fixtures.py` makes them, in a task under Stage 4's isolation, where `git status` must show only the new files;
- the committed boards that serve are reused untouched, since the golden pins hash them.

| Rule | Positive | Negative |
| --- | --- | --- |
| R1 | `usb2_hs_gap` (USB_D± over In1's 1.000 mm slot, with In2's +3V3 under it); the new board's clock over a void several mm wide | `usb2_hs`; the new board's track over a deliberate In1 cut-out with GND under it on In2 (the look-through) |
| R2 | `qspi_clk` (FLASH_CLK from In1's GND to In2's +3V3, with the nearest bridge 2.26 mm and 9.77 mm away, over d = 2 mm) | the new board's via, bridged by a GND/+3V3 0402 within 0.9 mm; a same-net change with a GND via 0.8 mm away, as an in-memory `dataclasses.replace` |
| R3 | the new board's clock, with its edge within 2h of the outline and its plane under all of it, so that R1 stays silent | `usb2_hs` (the pair about 5 mm in, against 2h = 0.4 mm); `lpf915`'s edge-launch SMA (the connector exclusion) |
| R4 | `lpf915`'s SH1 (r1 found no GND via at its frame) | the new board's shield, with GND vias at 1.0 mm under its frame pads |

- **The new review board** is r1's `emc_review`: 50 × 50 mm on `STACKUP_4L`, with In1.Cu GND, In2.Cu +3V3, and the rows above.
  - Its R3 positive moves from r1's plane edge to the outline (A6). Its plane is therefore drawn to the outline with `square`, not inset 0.5 mm as `planes` draws it.
  - It doubles as a GND/+3V3 cavity for E-E's fixture goldens.
- **The probe's boards** (plan 3) are its base, its null twin and its plane-pair variant (§5.13). Plan 4 adds E-C's microstrip boards.
- **Four layers.** `main()` builds `emc_review` and the probe's boards with (4, 1.6, STACKUP_4L), through STACKS entries or by adding their prefixes to the Stage 4 tuple. Any other name would come out on KiCad's default two-layer stackup. Rebuilding by name leaves every other committed board's bytes unchanged.
- **Regression tests.** Each review fixture's findings, cavities and settings are pinned in a golden `review.json`. The golden stores the board as its file name and sha256 only, and the test compares everything else byte for byte.

### 5.15 Plans

Stage 5 runs as up to five plans. Each plan is subagent-driven, leaves the suite green in both languages, and merges into main by fast-forward before the next plan is written, as Stage 4's did.

| Plan | Content | Machine time |
| --- | --- | --- |
| 1 | The rule engine R1–R4 and the plane map (§5.1, §5.2); tagging; `review` in the CLI, with `review.json`, `review.csv` and `review.png` (§5.3); the W_/I_EMC codes with pt-BR; the fixtures and the goldens (§5.14) | none |
| 2 | The cavity modes, and gate E-E with its recorded openEMS run (§5.4, §5.12); the GUI Review tab, Select in KiCad and "simulate this" on the SI kind (§5.5); the README's review tutorial; `tools/release_check.py`'s review step | the openEMS confirmation, 0.5–2 h |
| 3 | First, the pins: the three suites stand, and the first task extends them to any shared output this plan's edits reach that they do not yet hash, before the first shared edit. Then: schema 4 and `new --emission` (§5.6), with the termination's R and the kind checks; the overrides (§5.9); the stop branch (§5.7); the NF2FF cap, the near-field plane, the 3 m field, the normalisation and closure (§5.8); the emission fingerprint and the n(f) function (§5.10); cost (§5.11); gate E-A, with its criteria frozen as JSON before its run, and on its no-go §5.13's closing branch without the probe (controller ruling, builder check); then the probe's fixtures, its frozen criteria and its four runs (§5.13) | E-A 1–2 h; the probe about 5 h |
| 4 | Only on a go: compare's third kind, with its pins first (§5.10); gates E-B, E-C and E-D and their reports; compare's thresholds and floor; the cost refit | 25–50 h |
| 5 | Only on a go: the emission kind in New and in Results, with its figure; Compare for it; "simulate this" switched to the emission pair; the README's emission tutorial; the release check's emission step; the acceptance through the window; the exit record | the acceptance's runs |

On a no-go, the exit record is written after plan 3.

### 5.16 Amendments to the Stage 1 spec

These are A-70 onward, each landing in the plan that implements it:
- §2's stage table: a row 5, "EMC, a first slice: geometry review, cavity modes and relative emission", naming this design. The Later row becomes "a GPU engine, a bundled installer" (plan 1).
- §3.2 and §3.3: `review`, its options, outputs and exit codes, and the GUI's `review` folder (plans 1 and 2).
- §4.6: the button's Select in KiCad, and the Review tab's handoff (plan 2).
- §5.1, §5.3 and §5.8: the emission kind's region, its lossless dielectric and its pulse (plan 3).
- §6.3 and §6.4: the emission stop branch, its T_max and its cost lines (plan 3).
- §7: the cavity modes and their stated limits (plan 2); the emission results, closure and their stated limits (plan 3).
- §7.8: schema 4 and its overrides (plan 3).
- §9.12 (new): E-E and E-A, with their results (plans 2 and 3).
- §9.13 (new): the probe and, on a go, E-B to E-D (plans 3 and 4).
- §9.1: the release check's review step (plan 2), and its emission step on a go (plan 5).
- §10: this design's non-goals join the deferred list. The review and the cavity modes leave it. The emission kind leaves it only on a go.

Each of plan 3's amendments is marked "unreleased until the probe's go". On a no-go, the exit record lists them as dormant.

### 5.17 Acceptance

Stage 5 is done when all of these hold:
1. Plans 1 to 3 are merged, and plans 4 and 5 too on a go. Each has the suite green in English and the GUI tests green in pt-BR.
2. `review` on every committed review fixture matches its golden output, and `tools/release_check.py` passes with its review step.
3. E-E has passed and its openEMS run is recorded. E-A has passed, and the probe's record states go or no-go against §5.13's criteria; or E-A's record states its no-go, with no pipeline bug reproduced, and the probe was not run (controller ruling, builder check). On a go, E-B to E-D have passed, or their fallbacks are in force and recorded.
4. One review has run end to end through the GUI's code paths, offscreen, on the new review board: Review, the findings and modes shown, Select in KiCad against the fake KiCad, and "simulate this" pre-filling New.
5. On a go, an emission compare of lid on against lid off has run on the probe's base board, through the window. In it, at least one closure-judged harmonic must either be resolved, or read "at or below the floor" with lid on while lid off stands above it, as E-D requires. If neither holds, the acceptance fails, and the exit record names the harmonic.
6. The Stage 5 exit record lists the owner's items.

## 6. Left to the builder

- Module, class, function, option, message code and file names, within §5's rules. Three things are fixed by this design: the four W_/I_EMC codes (A9), schema 4 with its override entries (§5.9), and `review.json`'s schema 1 keys (§5.3). For example, `core/review.py` and `core/cavity.py` could hold the review and the cavity solve.
- These numbers and lists, within the bounds given:
  - the pattern families' exact regular expressions, from r1's, tested on a name list that holds SWDIO, SPI_CS, CLK_GEN, LORA_DIO1 and MCU_D±;
  - the clearance of a fill override and of an added via, and which via an override adds when the board has several GND via sizes;
  - the short-time DFT's window shape within §5.7's 2 ns windows;
  - Weyl's mode-count margin, and the coarsening step past 1.5 M cells;
  - the pitch of the probe fixture's vias along the RF line.
- The CLI's spelling of the variant's inputs: a review file and a finding id, and the pitch p.
- How each plan is cut into tasks, and the fixtures' exact footprints, as long as each rule keeps its positive and negative, and each probe board keeps its §5.13 role.
- Whether `review.png` adds a cavity panel.

Where this design and the code disagree, the code's tests and the Stage 1 spec win, and the controller rules on it in the plan's ledger.

## 7. Owner items this work leaves open

Each item has the default this design applies:
- **The GPU engine**, either the openEMS dev package or the next release. Default: not adopted. It is the biggest lever for speed, and the next stage on the owner's go. On a no-go, releasing the emission kind waits on it.
- **The installer.** Default: deferred to the first push. Setup and doctor come first, then Shape A, an online bootstrap that conveys no binaries. Shape B waits on A-19.
- **EMerge as E-F.** Default: optional, in its own venv, the owner's, as P3-F and P4-G are.
- **A lossy emission default.** Default: lossless (B3), with the probe's fitted Q values as evidence.
- **Prony tail extrapolation.** Default: deferred, with truncation reported (B7).
- **A stitching-capacitor override.** Default: deferred (B11).
- **Overrides on the SI kind** (the filled void, stitching vias). Default: emission only (B11). On a no-go, the SI handoff stays a single run.
- **A board-edge fence by default.** Default: opt-in (A7).
- **A 10 m distance or a ground-reflection model.** Default: free space at 3 m.
- **FCC and CISPR limit lines.** Default: none, by design.
- **kicad-happy's broader checks.** Default: cited, not reused.
- **The review's thresholds and tag patterns:** f_max 5 GHz, the 1 mm run, R2's max(L, 2 mm), k = 2, the ±5 % window, the deny list and its scope, and R1's same-net look-through. Default: §5.1, §5.2 and §5.4, set from three public boards and one judge. Running the review on the owner's own boards is the calibration.
- **The probe's budget.** Default: 2 h a run and 20 dB, the controller's reading of "as fast as possible".
- **The native pt-BR review** of the new strings, among them the new EMC terms (plano, caminho de retorno, costura de vias, cerca de vias, modo de cavidade).
- **The click-through of Select in KiCad** on a real KiCad 9.0.7 and 10.x: are footprint-owned zones and graphics selected, and does the selection show while the GUI holds the foreground?
- **`tracer.POWER` and dotted power names** (`+3.3V`, `+1.8V`, f4). Default: recognised by the review only. Changing the shared pattern moves classification for every kind, so it waits for a plan that records the pins again.
- **The review of A-70 onward.** Default: each is a controller recommendation.
- **Every item of the Stage 4 exit record §8 stands unchanged.** Among them:
  - the first push and its identity rewrite;
  - the deny-list review;
  - P0-C;
  - the engine redesign (A-9, A-10);
  - RFsim and NOTICE;
  - the existing click-through on KiCad 9.0.7 and 10.x;
  - the plugin identifier;
  - the reviews of A-13 to A-40 and of A-41 to A-69;
  - the native review of `po/pt_BR.po`;
  - Linux and the workflows after the push;
  - the golden pins bound to this PC;
  - P3-F;
  - the rest of Stage 2's §7 table: PyPI, the one-command installer, the Windows Sandbox run and the others;
  - the 45° rule and its B3′ run;
  - the ties R-5, R-9 and R-12;
  - EMerge as P4-G.

## 8. Risks

1. **Lossless ringing shapes the probe.** A plane pair's lossless Q is 232–1789 (f1), so a 31 ns run truncates it whatever the rule. Mitigation:
   - the stop branch fits a Q and a truncation factor per tail peak;
   - closure is judged only where the record is complete;
   - P_pp is one of the four runs, so its runtime and its untruncated frequencies count toward the go.

   Its truncated harmonics cannot fail the probe under B10, and the record states them.
2. **The tail fit is unproven on a multi-mode residual.** It has been tested only on f1's synthetic single-mode records. Mitigation: unit tests on synthetic two- and three-mode records with known Q before the probe, and the probe's recorded (f_r, Q) against f1's computed band. The fit reads every port's u (§5.7), so a mode weak at the source port but strong at another is still seen (controller ruling, builder check).
3. **The probe band is not the default band.** The probe runs to 3 GHz, while a default emission project runs to 6 GHz, about 2.2 times the time a run (f2). A go says that the 2nd and 3rd harmonics fit in 2 h, not the 5th. Mitigation: `cost` before every run, the long-run warning, and plan 4's refit at the gates' sizes.
4. **The floor is one sample.** One null pair gives the floor, as R-13's did, and a fence change adds more mesh lines than a split. Mitigation: E-B's pairs on a go, and P4-E's widening rule.
5. **Review precision rests on three boards and one judge.** f4's 62 % for R1 was judged unblinded, on three KiCad 6 and 7 files loaded by lowering `OLDEST_SUPPORTED` in memory, and with the any-net look-through: R1's same-net form has not been re-measured. The app's own tagging also differs from the reviewer's hand pick. Mitigation:
   - each finding prints its measurement, threshold and source;
   - R2 is info;
   - the edge fence is opt-in;
   - tags show their source;
   - calibration on the owner's boards is an owner item.
6. **R1's positive control sits on its threshold.** `usb2_hs_gap`'s bare run is 1.000 mm, against the 1 mm cut. Mitigation: lengths are compared at 1 µm, and the new board adds a second positive with a wide void.
7. **The cavity list can be over-read.** It is lossless and leaves decoupling capacitors out, while the emission model shorts them as copper, so the two can disagree on modes. Mitigation: the stated limits on every list, and the list says where a mode is, never how high it rises.
8. **The Select handoff's duck typing.** It depends on kipy 0.8 reading only `.id`, and kicad-python's main branch has moved the method. Mitigation: the `<0.9` pin, the fake-KiCad test, and the getters as the named fallback.
9. **Review thresholds from weak sources.** R2's d and R3's k rest on single practitioner sources, and λ/20 traces to books the research did not read. Mitigation: sources printed with each finding, a user-settable k, and no pass/fail.
10. **The cost model's extrapolation.** `SMALL_SPEED` and `PML_WEIGHT` come from 1.3 M-node models, and the RAM line leaves out the FD dumps. Mitigation: the probe records both, and plan 4 refits.
11. **A silent v1, antenna or SI regression.** Mitigation:
    - the three pin suites, extended before the first shared edit;
    - an antenna and an SI compare's printed lines pinned before compare is edited;
    - every emission key written only in emission specs;
    - overrides applied only behind `emission(project)`;
    - the `antenna()` checks assigned one by one.
12. **Hidden shorts from added vias.** `connectivity` reports shorts only for chain nets. Mitigation: the override's own clearance check on every layer the rod spans, antipads only in zone fills, and a W_ refusal otherwise.
13. **A probe tuned after the fact.** Mitigation: the fixtures, hashes, criteria and code are frozen at a recorded commit, with one attempt (§5.13).
