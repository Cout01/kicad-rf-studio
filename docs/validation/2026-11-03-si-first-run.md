# The first SI run: the USB 2.0 fixture (2026-11-03)

## 1. Purpose

Stage 4's plan 2 ends with its first real SI run. It is not a gate: gates P4-B to P4-F are plan 4's (Stage 4 design §5.11). The run was read against checks registered in the plan before it ran (plan 2, Task 11, Step 4).

- **It checks** that an SI project goes from `new` through `cost` to `run` on the USB 2.0 fixture and writes a valid layout N-port.
- **It records** the runtime and the 2D table for plans 3 and 4.

## 2. Inputs

- **Code:** branch `stage4-plan2` at `0db236b`, product code (`git rev-parse HEAD:src`) `77f74bc`. At `0db236b` the suite passed (2222 passed, 6 skipped, no warnings), and so did the GUI tests in pt-BR (42 passed, 3 skipped).
- **Versions:** Python 3.14.2, openEMS 0.37.0, CSXCAD 0.7.0, scikit-rf 2.2.0, numpy 2.5.4; Windows 11 (10.0.26200), 16 CPUs.
- **Isolation:** each PowerShell call set LOCALAPPDATA and XDG_DATA_HOME to `<RUN>\data`, an isolated data folder with its own calibration, and set CSXCAD_INSTALL_PATH to `<openEMS folder>`. `<RUN>` is a folder under the user's temp folder, outside every work tree.
- **Boards:** the committed fixtures `tests/fixtures/usb2_hs.kicad_pcb` and `tests/fixtures/qspi_clk.kicad_pcb`, copied into `<RUN>`.
- **Commands,** from the repo root, in this order:
  ```
  kicad-rf-studio new <RUN>\usb2_hs.kicad_pcb --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o <RUN>\proj
  kicad-rf-studio cost <RUN>\proj
  kicad-rf-studio new <RUN>\qspi_clk.kicad_pcb --start U1.11 --end U2.6 --interface se50 -o <RUN>\qspi
  kicad-rf-studio cost <RUN>\qspi
  kicad-rf-studio run <RUN>\proj
  kicad-rf-studio cost <RUN>\proj
  kicad-rf-studio cost <RUN>\dfill
  ```
  - The second `cost <RUN>\proj` is cost2, after the run.
  - `<RUN>\dfill` is the d fill's twin: `<RUN>\proj` copied, with `mesh.max_cell_mm` set to null and `results` removed.
  - Then came the plan's two `python -c` readouts: the layout file's checks (§6), and the 2D work's time with the long cut's legs (§3).
  - Every exit code was 0 (`codes.txt`: new 0, cost 0, qnew 0, qcost 0, run 0, cost2 0, dfill 0).
- **The language:** the CLI ran in the machine's pt-BR locale, so its logs are in Portuguese. A line quoted here is the English catalog's text with the run's values.
- **The fresh calibration:** the first `cost` measured the isolated folder's speed once, 4 jobs at once with 4 threads each: 764.4 MC/s in total, 191.1 MC/s a job. One job alone ran at 584.1 MC/s.
- **The preset: normal.** The plan switches to draft only when Step 2's worst case exceeds 4 h, and this one was 40 min.
- **What `new` wrote:**
  - the interface usb2-hs: 90 Ω differential ± 10 %, rise time 500 ps, marker 240 MHz, simulated to 10 GHz;
  - the pair USB_D+ with USB_D-, by KiCad's pair rule;
  - the chain J1.3 → U1.3 with series R1, and the chain J1.2 → U1.2 with series R2, 22 Ω each, both part ports;
  - C1 (100 nF) as copper;
  - the victim AUX from TP1.1 to TP2.1;
  - the ports:
    - P1 J1.3, P2 J1.2, P5 TP1.1 and P6 TP2.1, each vertical to the plane in In1.Cu;
    - P3 U1.3 and P4 U1.2, each referenced to U1.17 (the "ic" rule);
    - R1 and R2 as part ports;
  - T_max 9 ns, stop window 2 ns, mesh n 2 with cells up to 0.414 mm (λ/40 at f_max, 2D εeff 3.28), a lossless dielectric, dt floor 0.6, and a region and protected reach of 6 substrate heights (1.2 mm).

## 3. The 2D table and the cost

**The 2D table** of the USB 2.0 fixture, in the order `cost` printed it before its estimate. Every row is on F.Cu, with the mask, against the target 90 Ω ± 10 % (a pair's Zdiff, a net's Z0). A coupled row's delay is its odd mode's.

| net | section | width (mm) | gap (mm) | length (mm) | Z (Ω) | εeff | delay (ps) | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USB_D+ | coupled | 0.300 | 0.253 | 2.038 | Zdiff 90.87 (Zodd 45.43, Zeven 59.15) | odd 3.053, even 3.490 | 11.9 | in band |
| USB_D+ | partner not alongside | 0.300 | – | 0.675 | Z0 52.51, so Zdiff 105.01 uncoupled | 3.312 | 4.1 | out of band |
| USB_D+ | coupled | 0.600 | 1.300 | 5.000 | Zdiff 65.30 (Zodd 32.65, Zeven 33.05) | odd 3.285, even 3.338 | 30.2 | out of band |
| USB_D+ | partner not alongside | 0.300 | – | 0.675 | Z0 52.59, so Zdiff 105.18 uncoupled | 3.311 | 4.1 | out of band |
| USB_D+ | coupled | 0.300 | 0.250 | 17.490 | Zdiff 90.20 (Zodd 45.10, Zeven 58.86) | odd 3.060, even 3.490 | 102.1 | in band |
| MCU_D+ | coupled | 0.300 | 0.250 | 4.527 | Zdiff 90.33 (Zodd 45.16, Zeven 58.99) | odd 3.061, even 3.497 | 26.4 | in band |
| USB_D- | coupled | 0.300 | 0.251 | 2.038 | Zdiff 90.31 (Zodd 45.15, Zeven 58.92) | odd 3.063, even 3.498 | 11.9 | in band |
| USB_D- | partner not alongside | 0.300 | – | 0.675 | Z0 52.51, so Zdiff 105.01 uncoupled | 3.312 | 4.1 | out of band |
| USB_D- | coupled | 0.600 | 1.300 | 5.000 | Zdiff 65.30 (Zodd 32.65, Zeven 33.05) | odd 3.285, even 3.338 | 30.2 | out of band |
| USB_D- | partner not alongside | 0.300 | – | 0.675 | Z0 52.59, so Zdiff 105.18 uncoupled | 3.311 | 4.1 | out of band |
| USB_D- | coupled | 0.300 | 0.250 | 17.490 | Zdiff 90.20 (Zodd 45.10, Zeven 58.87) | odd 3.060, even 3.491 | 102.1 | in band |
| MCU_D- | coupled | 0.300 | 0.250 | 4.527 | Zdiff 90.23 (Zodd 45.12, Zeven 58.95) | odd 3.062, even 3.498 | 26.4 | in band |
| AUX | victim | 0.200 | 0.625 | 12.000 | Z0 62.94 | 3.240 | 72.0 | no target |

- **The 17.49 mm run,** both legs coupled, width 0.300 mm, gap 0.250 mm, reads Zdiff 90.20 Ω on each leg, in band. Its legs differ only in the last digit: Zeven 58.86 and 58.87 Ω, εeff even 3.490 and 3.491.
- **In band:** the 2.038 mm coupled runs at the connector, Zdiff 90.87 Ω (USB_D+, gap 0.253 mm) and 90.31 Ω (USB_D-, gap 0.251 mm), and MCU_D+ and MCU_D- over 4.527 mm, Zdiff 90.33 and 90.23 Ω.
- **Out of band:**
  - two 0.675 mm jogs per leg, with the pair not alongside: Z0 52.51 and 52.59 Ω, so Zdiff 105.01 and 105.18 Ω uncoupled;
  - the 5.000 mm runs through U2, 0.600 mm wide with the legs 1.300 mm apart: Zdiff 65.30 Ω, which the 2D box reads low (§8).
- **The victim AUX,** 0.200 mm wide, 0.625 mm from USB_D+'s edge (the gap column: the nearest copper of another net) and 12.000 mm long, has no target.
- **The 2D work's time on this model:** `si_readout` (the 2D table) took 2.81 s, and `fit2d` on the mesh 3.86 s. Both are a few seconds, so plan 1's open issue 8, cs2d's (1, −1) path, is not needed.
- **The long cut's two legs alone,** as fit2d's per-leg reference reads them: USB_D+ 51.009 Ω and USB_D- 51.101 Ω. They are 0.09 Ω (0.18 %) apart. This is the asymmetry that the 2D table's mean-c11 modes accept.

**The cost**

| | value |
| --- | --- |
| runs | 8: 4 for the measured lines' ends, 2 for the victims' ends, 2 for the part ports |
| RAM | about 1.6 GB, 4 jobs at once |
| worst case before the run: 8 runs to T_max 9 ns, 4 at once with 4 threads each, at the fresh calibration's 191.1 MC/s a job | 40 min |
| worst case after the run (cost2), at the pool-4 level the run refreshed | 1 h 14 min (4471 s) |
| predicted from the run's stop times (cost2's I_COST_PREDICTED, printed "25 min") | 1533 s (25.6 min) |
| measured, the job phase (`results.wall_s`) | 1557.8 s (26.0 min) |
| **ratio predicted/measured** | **0.984** |

- **The run's own speed:** each job measured 101.3 to 107.3 MC/s, a mean of 103.5 (§5). That is 0.54 times the calibration's per-job speed: the calibration measured 1.85 times what this 2.07 M-cell model ran at.
- **cost2:** the run refreshed the pool-4 level, as v1's runs do (D-16), so the worst case rose from 40 min to 1 h 14 min. Its new line reads "Predicted from the last run's stop times: 25 min." No constant changed; the SI cost refit is plan 4's.

## 4. The runtime against the design's estimate

- **The plan's estimate:** about 2.2 M cells (239 × 120 × 77), dt near 7.3e-14 s, about 123,000 steps a job to the 9 ns T_max, 8 jobs.
- **Measured:**
  - **Cells:** 230 × 117 × 77 = 2,072,070 under the SI rule (mesh n 2, cell d 0.1000 mm). The d fill's twin has 402 × 121 × 77 = 3,745,434, so the SI rule holds 55 % of the d fill's cells. The twin's worst case, at the level cost2 used, is 2 h 14 min, and it raises W_SI_LONG_RUN: "The worst case is 2 h 14 min, over two hours: the draft preset, or a shorter route between nearer pads, cuts it."
  - **dt:** 8.0609e-14 s, above its floor of 0.6 × 7.4439e-14 s. It is set by the z edge at (129.807, 100.139, 1.580) mm, inside U1's footprint. The smallest cell is 33.3 µm in z, at z = −0.017 mm. The twin's dt is 8.0779e-14 s, set by the z edge at (96.588, 100.925, 1.580) mm.
  - **Steps:** 111,649 to T_max. The jobs stopped at 34,255 to 38,285 steps, 31 % to 34 % of T_max.
  - **Wall time:** 684 to 779 s a job at 101 to 107 MC/s. The job phase, all 8 jobs with 4 at once of 4 threads each, took 1557.8 s (26.0 min).
- **For plan 4's 10–60 machine hours** (r4's 10–25 and r3's up to 60, Stage 4 design §5.11): at this machine's measured speed, an 8-port project of about 2 M cells costs 26 min when its jobs converge near 3 ns, and 75 min when every job runs to T_max.
  - 10 h holds about 23 converged runs of this size, and 60 h about 140.
  - At T_max, that is about 8 and 48.
  - A cost made from a fresh calibration alone would under-read such a run by about 1.85 times until a run refreshes its level.

## 5. The stop

The stop ran under the DC pulse and `window_s`, at the normal preset: −60 dB with an S tolerance of 2e-3. Every job converged; none was flat and none reached T_max (9 ns). Each stopped at about a third of T_max, between 2.75 and 3.07 ns, and the victims' ends stopped first.

| job | port | t_cut (ns) | last sample (ns) | residual (dB) | steps | wall (s) | MC/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 J1.3 | 3.074 | 3.086 | −60.8 | 38,285 | 776.5 | 102.2 |
| 2 | P2 J1.2 | 3.074 | 3.086 | −61.1 | 38,285 | 778.5 | 101.9 |
| 3 | P3 U1.3 | 3.036 | 3.049 | −60.8 | 37,820 | 768.0 | 102.0 |
| 4 | P4 U1.2 | 3.036 | 3.049 | −60.5 | 37,820 | 773.5 | 101.3 |
| 5 | P5 TP1.1 | 2.749 | 2.761 | −60.6 | 34,255 | 684.3 | 103.7 |
| 6 | P6 TP2.1 | 2.774 | 2.786 | −63.1 | 34,565 | 696.7 | 102.8 |
| 7 | R1 | 2.999 | 3.011 | −62.2 | 37,355 | 725.8 | 106.6 |
| 8 | R2 | 2.999 | 3.024 | −61.9 | 37,510 | 724.2 | 107.3 |

- **No E_ code:** the run's events hold none, and their only verdict code is I_JOB_CONVERGED. Their only W_ code is W_FILLS_AS_SAVED, the reminder that the zones' fills are read as saved.
- **The setup gate passed:** edge lint, fit2d, the dt floor, the ports' connectivity and unused primitives. Its line, I_GATES_PASSED, reads "Gates passed: edge lint, fit2d, timestep floor (dt 8.0609e-14 s), port connectivity and unused primitives."
- **The ports set up:** none of E_DT_FLOOR, E_FIT2D*, E_EDGE_LINT, E_PORT_OPEN, E_PORT_SHORT, E_PORT_BOX, E_PORT_VERTICAL_BOX or E_PORT_PLANE appeared. J1's and the victim's vertical ports and U1's horizontal ones all set up.

## 6. The layout N-port's validity

- **The file:** `results/` holds `layout.s8p` alone. It has 8 ports and 2001 points from 0 to 10 GHz in 5 MHz steps, all at 50 Ω.
- **Ports:** P1 to P6 are external. R1 and R2 are part ports with C_box 2.38e-15 F and 2.45e-15 F. The header names each port's signal and reference: J1's and the TPs' references are the plane in In1.Cu, U1's are U1.17.
- **Passivity:** σ_max is at most 1.0011, at 9.415 GHz. Its excess over 1 is 3.7e-5 at DC, 2.1e-4 at the median and 1.0e-3 at the 90th percentile. The smallest singular value runs from 0.9775 to 1, with a median of 0.9931. The network is nearly lossless, as PEC copper and a lossless dielectric inside MUR walls make it, so σ_max sits at 1 within numerical error.
- **Reciprocity:** the error is at most 0.0099, at 10 GHz, with a median of 0.0024.
- **Verdict:** both are within the plan's σ_max ≤ 1.02 and error ≤ 0.02.

## 7. qspi_clk's cost and short-route note

`new` and `cost` only; the clock was not run.

- **What `new` wrote:**
  - the interface se50: 50 Ω single-ended ± 10 %, rise time 1000 ps, marker 133 MHz, to 10 GHz;
  - the chain U1.11 → U2.6 with series R1, 33 Ω, a part port; C1 (100 nF) is copper;
  - P1 U1.11 referenced to U1.17 (the "ic" rule), and P2 U2.6 vertical to the plane in In1.Cu;
  - cells up to 0.427 mm (λ/40, 2D εeff 3.08).

**The 2D table,** against the target 50 Ω ± 10 %, with the mask. Every row is 0.330 mm wide and in band.

| net | layer | length (mm) | Z0 (Ω) | εeff | delay (ps) |
| --- | --- | --- | --- | --- | --- |
| QSPI_CLK | F.Cu | 2.527 | 49.99 | 3.329 | 15.4 |
| FLASH_CLK | F.Cu | 1.990 | 49.96 | 3.330 | 12.1 |
| FLASH_CLK | B.Cu | 10.000 | 49.96 | 3.329 | 60.9 |
| FLASH_CLK | F.Cu | 2.525 | 49.96 | 3.330 | 15.4 |

- **The short-route note:** "The route QSPI_CLK is 103.7 ps long, under a sixth of the link's 1000 ps rise time: it is electrically short, and the 2D table above, with a lumped estimate, may answer the question without a run."
- **The cost:**
  - Cells: 168 × 86 × 77 = 1.11 M, the smallest cell 33.3 µm in z.
  - dt 7.9033e-14 s (floor 0.6 × 7.7611e-14 s), set by the z edge at (100.600, 100.257, 1.580) mm.
  - Worst case 11 min: 3 runs at once with 4 threads each, at the fresh calibration's speed for that level. The run did not measure that level.
  - The runs are 2 for the measured line's ends, 0 for victims and 1 for the part port; RAM is about 0.7 GB.

## 8. The stated limits

- **No SI result yet:** this run makes no claim on the channel. Its results (the TDR, mixed-mode S and the views) are plan 3's.
- **The model:** copper is PEC, the dielectric is lossless (Debye only on request), the region is closed by MUR walls, and the ports sit at the pads.
- **The 2D table is a screening.** It leaves out bends, vias, pads and parts. Its 65.30 Ω on the 0.6 mm runs through U2 read 7.2 % low. The coupled cut's box ran 10 substrate heights past the signal leg alone, so the partner leg sat 0.1 mm inside its PEC side. The branch's final review found it after this run, and its fix wave runs a pair's box 10 heights past both legs. Those runs now read Zdiff 70.25 Ω (Zodd 35.12 Ω, Zeven 35.73 Ω), within 0.2 % of a 40-height box, and the 0.3 mm runs move by at most 0.01 Ω. Either way the verdict is out of band.
- **Shared mesh lines** (the plan's open issue 1): every line shares one set of mesh lines per axis, so the edges of two features 15–25 µm apart, such as a 0.3 mm track into a 0.25 mm QFN pin or a micro-B's 0.65 mm pitch beside a 0.5 mm pair, fail the edge lint after its re-mesh or read fit2d 5–7 % off. The fixtures were laid out clear of it, as Task 1's gate test checks, so this run does not show it. Real boards will meet it before plan 4, and P4-C rules on it.
- **One run** of one synthetic fixture on one PC (16 CPUs), at the defaults: mesh n 2, the SI mesh rule, a lossless dielectric and the normal preset. Gates P4-B to P4-D set the first three (Stage 4 design §5.11).

## 9. Next

- **Plan 3, the SI results** (Stage 4 design §5.12 item 3), builds them on this layout file: the TDR and TDT, the mixed mode, the skew, NEXT and FEXT, and the loss lines.
- **Plan 4, the gates** (§5.12 item 4):
  - P4-B to P4-F take this run's runtime figures (§4);
  - the SI cost refit takes the calibration's 1.85 times over-reading of the per-job speed on a 2 M-cell model.

The Stage 1 spec's amendments A-48 to A-53 land with this record. They are controller recommendations, made while the owner was unavailable, and the Stage 4 exit record carries them as owner items (the plan's open issue 9).
