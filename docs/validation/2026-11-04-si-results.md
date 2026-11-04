# The SI results: the USB 2.0 fixture and its plane-gap variant (2026-11-04)

## 1. Purpose

Stage 4's plan 3 ends with its end-to-end SI results on the USB 2.0 fixture and its plane-gap variant. It is not a gate: gates P4-B to P4-F are plan 4's (Stage 4 design §5.11). The runs were read against checks registered in the plan before they ran (plan 3, Task 8, Step 4).

- **It checks** that `run` writes an SI project's results (the layout N-port, the chain, the TDR, the mixed-mode S, the crosstalk and the loss lines), and that `retune` with snapping, `verify` and `compare` work on an SI project.
- **It records** the numbers for plans 4 and 5.
- **It previews** P4-F's positive control, Scd21's change with the plane gap, which is recorded here and not judged (§6).
- **The outcome:** every hard check passed, the plane-gap board's after ruling R8-1 (§7).

## 2. Inputs

- **Code:** branch `stage4-plan3` at `1bca9b1`, product code (`git rev-parse HEAD:src`) `421f27c`. At `1bca9b1` the suite passed (2256 passed, 6 skipped, no warnings), and so did the GUI tests in pt-BR (42 passed, 3 skipped).
- **Versions:** Python 3.14.2, openEMS 0.37.0, CSXCAD 0.7.0, scikit-rf 2.2.0, numpy 2.5.4, scipy 1.18.1, h5py 3.16.0; Windows 11 (10.0.26200), 16 CPUs; the app 0.1.0.dev0.
- **Isolation:** each PowerShell call set LOCALAPPDATA and XDG_DATA_HOME to `<RUN>\data`, an isolated data folder with its own calibration, and set CSXCAD_INSTALL_PATH to `<openEMS folder>`. `<RUN>` is a folder under the user's temp folder, outside every work tree.
- **Boards:** the committed fixtures `tests/fixtures/usb2_hs.kicad_pcb` (the solid board) and `tests/fixtures/usb2_hs_gap.kicad_pcb`, copied into `<RUN>`. The variant is the same board with In1.Cu's GND plane bare at x 116–117 mm, y 97–103 mm, across the pair's path.
- **Commands,** from the repo root. Step 2 ran, for each board `<name>` in usb2_hs and usb2_hs_gap, every exit code 0:
  ```
  kicad-rf-studio new <RUN>\<name>.kicad_pcb --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o <RUN>\<name>
  kicad-rf-studio cost <RUN>\<name>
  kicad-rf-studio run <RUN>\<name>
  ```
- **Step 3 ran,** with `$v` = 24:
  - `$v` is the GUI's E24 snapping of a typed 25 Ω, `snapped('R1', '25', 'E24')` from `kicad_rf_studio.gui.control`, so this is design §5.14's "retune of the series resistors with snapping"; `retune` stores it, which is the CLI's Apply.
  - the sweep: `<RUN>\usb2_hs` copied to `<RUN>\sweep`, then `retune <RUN>\sweep R1=<r> R2=<r>` for r = 0R, 10, 22, 33 and 47, each exit 0;
  - `retune <RUN>\usb2_hs R1=24 R2=24` (0), then `verify <RUN>\usb2_hs` (0);
  - `retune <RUN>\usb2_hs_gap R1=24 R2=24` (0, on the 9 ns run that R8-1 replaced). Its `verify` was stopped by a STOP file during setup, before any job (exit 130), once ruling R8-1 was made. `compare <RUN>\usb2_hs <RUN>\usb2_hs_gap -o <RUN>\compare` then refused with E_COMPARE_NO_RESULT (exit 2), as the gap had no verify.
- **Ruling R8-1's rerun of the gap board** (§7):
  - `t_max_s` was set to 3.2e-08 in `<RUN>\usb2_hs_gap\project.json` through `core.project`'s `load_project` and `save_project`, then `cost` ran (0).
  - A first attempt's `run` was stopped at 13:28. The agent tooling that drove it stopped its background shell on low system memory; this was no product failure. By then P1 to P6 had converged at 20.7–22.8 ns, and R1 and R2 had reached 3.6 ns. `run` keeps no partial run, so the run started over.
  - The second attempt ran `run <RUN>\usb2_hs_gap` (0), `retune <RUN>\usb2_hs_gap R1=24 R2=24` (0, `$v` again 24), `verify <RUN>\usb2_hs_gap` (0) and `compare <RUN>\usb2_hs <RUN>\usb2_hs_gap -o <RUN>\compare` (0), 359.2 min in all. Compare then ran once more with LANGUAGE=en into `<RUN>\compare_en` (0), for the English lines this record quotes.
- **The language:** the CLI ran in the machine's pt-BR locale, so its logs are in Portuguese. A line quoted here is the English catalog's text with the run's values.
- **The fresh calibration:** the first `cost` (usb2_hs) measured the isolated folder's speed once. With 2 jobs at once of 8 threads each it ran 706.6 MC/s in total (the line prints 707), 353.3 MC/s a job; 4 at once measured 700.2 MC/s.
- **The preset: normal.** The plan switches to draft only when Step 2's worst case exceeds 4 h. The solid board's worst case was 43 min and the gap's first 1 h 21 min. The rerun's 5 h 15 min at T_max 32 ns raised W_SI_LONG_RUN; the preset stayed normal, as it is in the settings fingerprint that compare requires equal.
- **What `new` wrote,** both boards alike:
  - the interface usb2-hs: 90 Ω differential ± 10 %, the link's rise time 500 ps, marker 240 MHz, simulated to 10 GHz, where the localising TDR's rise time is 125 ps;
  - the stackup from the board (dielectric 1.44 mm; F.Cu, a 0.2 mm prepreg of εr 4.3, In1.Cu, a 1.04 mm core of εr 4.5, In2.Cu, a 0.2 mm prepreg, B.Cu; tan δ 0.02, which only the loss lines use; mask 0.01 mm of εr 3.3); GND net GND, power nets +3V3 and VBUS, connector J1;
  - the pair USB_D+ with USB_D-, by KiCad's pair rule;
  - the chain J1.3 → U1.3 with series R1, and the chain J1.2 → U1.2 with series R2, 22 Ω each in an 0402 (ESL 0.5 nH, ESR 0.1 Ω), as part ports; C1 (100 nF) is copper;
  - the victim AUX from TP1.1 to TP2.1, both ends ports, so the waves coupled into it end in 50 Ω;
  - the ports:
    - P1 J1.3, P2 J1.2, P5 TP1.1 and P6 TP2.1, each vertical to the plane in In1.Cu;
    - P3 U1.3 and P4 U1.2, each referenced to U1.17 (the "ic" rule);
    - R1 and R2 as part ports;
  - preset normal, T_max 9 ns, stop window 2 ns, mesh n 2 with cells up to 0.414 mm (λ/40 at f_max, 2D εeff 3.28), a lossless dielectric, dt floor 0.6, and a region and protected reach of 6 substrate heights (1.2 mm).
- **The 2D table,** both boards alike (a screening, which leaves out the plane gap):
  - the 17.490 mm coupled runs, width 0.300 mm, gap 0.250 mm: Zdiff 90.21 Ω (Zodd 45.10 Ω, Zeven 58.90 Ω), εeff odd 3.061 and even 3.493, 102.1 ps, in band;
  - the 2.038 mm runs at the connector: Zdiff 90.87 Ω (USB_D+) and 90.32 Ω (USB_D-), in band;
  - two 0.675 mm jogs per leg with the pair not alongside: Z0 52.51 and 52.59 Ω, so Zdiff 105.01 and 105.18 Ω uncoupled, out of band;
  - the 5.000 mm runs through U2, 0.600 mm wide with the legs 1.300 mm apart: Zdiff 70.25 Ω (Zodd 35.12 Ω, Zeven 35.73 Ω), out of band;
  - MCU_D+ and MCU_D- over 4.527 mm: Zdiff 90.34 and 90.24 Ω, in band;
  - the victim AUX, 0.200 mm wide, 0.625 mm off, 12.000 mm long: Z0 62.94 Ω, εeff 3.240, 72.0 ps, with no target.
- **The cells:** the solid board 230 × 117 × 77 = 2.07 M, the gap 242 × 117 × 77 = 2.18 M. Both have dt 8.0609e-14 s (floor 0.6 × 7.4439e-14 s), set by the z edge at (129.807, 100.139, 1.580) mm; the smallest cell is 33.3 µm in z, at z = −0.017 mm. Each run is 8 jobs: 4 for the measured lines' ends, 2 for the victim's ends and 2 for the part ports; RAM about 0.8 GB, 2 at once.

## 3. Each board's results

**The solid board (usb2_hs).** Every job converged at about a third of T_max (9 ns); the victim's ends stopped first. The run's events hold no E_ code, and their only verdict code is I_JOB_CONVERGED. "8 of 8 jobs kept S, in 26 min" (`results.wall_s` 1611.8 s).

| job | port | t_cut (ns) | last sample (ns) | residual (dB) | steps | wall (s) | MC/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 J1.3 | 3.074 | 3.099 | −60.8 | 38,440 | 410.4 | 194.1 |
| 2 | P2 J1.2 | 3.074 | 3.086 | −61.1 | 38,285 | 409.2 | 193.9 |
| 3 | P3 U1.3 | 3.036 | 3.049 | −60.8 | 37,820 | 401.2 | 195.3 |
| 4 | P4 U1.2 | 3.036 | 3.061 | −60.5 | 37,975 | 397.4 | 198.0 |
| 5 | P5 TP1.1 | 2.749 | 2.774 | −60.6 | 34,410 | 358.2 | 199.0 |
| 6 | P6 TP2.1 | 2.774 | 2.799 | −63.1 | 34,720 | 359.7 | 200.0 |
| 7 | R1 | 2.999 | 3.024 | −62.2 | 37,510 | 381.8 | 203.6 |
| 8 | R2 | 2.999 | 3.011 | −61.9 | 37,355 | 380.3 | 203.5 |

- **The files:** `results/` holds chain.s6p, layout.s8p, si_summary.csv, si_summary.png and si_tdr.csv. `results.route` and `results.fingerprint` are recorded: the route reads εeff 3.2777 over 30.405 mm, with the loss estimates below. C_box is 2.38e-15 F at R1 and 2.45e-15 F at R2.
- **The lines,** in order. They are the chain at the values `new` wrote, 22 Ω each:
  - "Passivity: σ_max 1.0011 at worst, at 9415.0 MHz (|a| -17.3 dB); flagged above 1.02."
  - "Reciprocity: |Sij − Sji| 9.90e-03 at worst, at 10000.0 MHz (|a| -19.6 dB); flagged above 0.02."
  - I_SI_RELATIVE: "Relative: these signal-integrity results compare variants of one board under identical settings; they do not predict measured performance."
  - "Sdd21 -1.913 dB at the marker (240 MHz) and -2.962 dB at f_max (10 GHz)."
  - "The worst Sdd11 up to f_max: -7.39 dB at 4805 MHz." and "The worst Scd21 up to f_max: -43.89 dB at 10000 MHz."
  - "Scc21, the common mode's transmission: -1.90 dB at the marker (240 MHz)."
  - "The differential TDR: the localising rise time 125 ps resolves 10.3 mm and the link's 500 ps 41.4 mm, at the route's 2D εeff 3.28; the first resolution length at each port is the port's own launch."
  - I_SI_TDR_SHORT twice: the lowest level "84.94 Ω at 131.2 ps (10.9 mm)" and the highest "96.00 Ω at 256.2 ps (21.2 mm)", each "lies on a feature shorter than two resolution lengths (20.7 mm), so it is not that feature's impedance."
  - "Intra-pair skew +0.08 ps: the N leg's TDT arrives at 200.0 ps and the P leg's at 199.9 ps, each at half its peak."
  - "Crosstalk into AUX from the pair driven differentially at its start: NEXT at TP1.1 peaks at -25.66 dB (9170 MHz) and FEXT at TP2.1 at -28.84 dB (9345 MHz)."
  - the loss lines: the copper's over the route's 30.4 mm by Hammerstad's formula, about 0.050 dB at the marker and 0.321 dB at f_max; the lossless dielectric's, about 0.022 and 0.907 dB;
  - I_WHAT_IF, I_OUTPUTS, then the six limits last (I_LIMIT_SI_CROP, I_LIMIT_PEC, I_LIMIT_SI_LOSSLESS, I_LIMIT_SI_BODIES, I_LIMIT_SI_PORTS and I_LIMIT_SI_RESOLUTION; §9 quotes them).
- **The order checks hold:** both indicators come before I_SI_RELATIVE, every other I_SI_ line after it, the six limits last, and I_WHAT_IF is present.

**The plane-gap board's first run, at T_max 9 ns,** is kept as R8-1's evidence; the rerun's results replaced it.

- Every job reached T_max (W_JOB_T_MAX), at residuals of −45.6, −45.6, −48.4, −48.3, −45.3 and −45.8 dB (P1 to P6) and −49.4 and −49.3 dB (R1, R2). "8 of 8 jobs kept S, in 1 h 26 min" (`results.wall_s` 5185.1 s). Each job ran the full 111,649 steps, in 1243–1300 s at 187.3–195.8 MC/s.
- W_PASSIVITY: "Passivity flagged: σ_max 1.1112 at 2350.0 MHz (|a| -1.1 dB) is above 1.02, so this S makes power. Check the verdicts above: a flat or T_max job is the usual cause, and a stricter preset the fix." Reciprocity read 7.83e-03 at 10000.0 MHz.
- Its lines, for the record only: Sdd21 −1.912 dB at the marker and −3.340 dB at f_max; the worst Sdd11 −7.21 dB at 10000 MHz; the worst Scd21 −27.29 dB at 9390 MHz; Scc21 −1.91 dB; the levels 85.27 Ω at 131.2 ps (10.9 mm) and 98.05 Ω at 256.2 ps (21.2 mm), both short; skew +0.44 ps (N 207.1 ps, P 206.7 ps); NEXT −19.20 dB (9495 MHz) and FEXT −21.05 dB (9485 MHz).

**The plane-gap board's rerun, at T_max 32 ns.** Every job converged, at 64–71 % of T_max; the part ports stopped first. The run's events hold no E_ code, and their only verdict code is I_JOB_CONVERGED. "8 of 8 jobs kept S, in 3 h 22 min" (`results.wall_s` 12142.9 s); I_BASIS reads "8 jobs converged, 0 flat, 0 at T_max."

| job | port | t_cut (ns) | last sample (ns) | residual (dB) | steps | wall (s) | MC/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 J1.3 | 22.777 | 22.802 | −60.7 | 282,875 | 3136.9 | 196.6 |
| 2 | P2 J1.2 | 22.777 | 22.790 | −60.6 | 282,720 | 3143.3 | 196.1 |
| 3 | P3 U1.3 | 20.716 | 20.728 | −62.3 | 257,145 | 2922.3 | 191.8 |
| 4 | P4 U1.2 | 20.891 | 20.916 | −62.1 | 259,470 | 2931.2 | 193.0 |
| 5 | P5 TP1.1 | 22.702 | 22.715 | −61.0 | 281,790 | 3197.3 | 192.1 |
| 6 | P6 TP2.1 | 22.078 | 22.090 | −61.1 | 274,040 | 3118.1 | 191.6 |
| 7 | R1 | 20.478 | 20.491 | −63.2 | 254,200 | 2842.0 | 195.0 |
| 8 | R2 | 20.516 | 20.528 | −63.0 | 254,665 | 2815.0 | 197.2 |

- **The files:** the run wrote the same five files into `results/`, replacing the 9 ns run's; `results.route` and C_box equal the solid board's.
- **The lines,** in order:
  - "Passivity: σ_max 1.0116 at worst, at 2350.0 MHz (|a| -1.1 dB); flagged above 1.02." This is I_PASSIVITY, not the 9 ns run's W_PASSIVITY.
  - "Reciprocity: |Sij − Sji| 8.71e-03 at worst, at 10000.0 MHz (|a| -19.7 dB); flagged above 0.02."
  - then I_SI_RELATIVE;
  - Sdd21 −2.066 dB at the marker and −3.538 dB at f_max;
  - the worst Sdd11, −7.04 dB at 10000 MHz, and the worst Scd21, −27.50 dB at 9425 MHz;
  - Scc21 −2.07 dB;
  - the TDR line, as the solid board's;
  - the levels 85.27 Ω at 131.2 ps (10.9 mm) and 98.32 Ω at 256.2 ps (21.2 mm), both I_SI_TDR_SHORT;
  - skew +0.45 ps (N 207.1 ps, P 206.6 ps);
  - NEXT −19.10 dB (9475 MHz) and FEXT −20.78 dB (9470 MHz);
  - the same loss lines;
  - then I_WHAT_IF, I_OUTPUTS and the six limits last.
- **The order checks hold,** as for the solid board.
- **Its lines are the chain at 24 Ω,** because project.json kept the first retune's values. So they stand beside the solid board's retune at 24 Ω (§5), not beside its run at 22 Ω:
  - Sdd21: −2.066 against −2.067 dB at the marker, and −3.538 against −3.154 dB at f_max;
  - the worst Scd21: −27.50 against −44.00 dB;
  - crosstalk: NEXT −19.10 against −25.62 dB, and FEXT −20.78 against −28.73 dB;
  - the highest level: 98.32 against 96.27 Ω;
  - skew: +0.45 against +0.08 ps.

## 4. The termination sweep

The sweep ran on the solid board's copy, both series resistors at each value. Each step redrew the chain from the one layout N-port and exited 0 in 7–10 s; project.json ends at 47.

| R1 = R2 | Sdd21 at 240 MHz (dB) | Sdd21 at 10 GHz (dB) | worst Sdd11 (dB, MHz) | worst Scd21 (dB, MHz) | Scc21 at 240 MHz (dB) | lowest level | highest level | skew (ps) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0R | −0.002 | −0.339 | −10.13 at 7865 | −46.56 at 8970 | −0.01 | 84.94 Ω at 131.2 ps, short | 89.82 Ω at 206.2 ps (17.1 mm), in band | +0.01 |
| 10 Ω | −0.922 | −1.711 | −9.14 at 4890 | −43.02 at 10000 | −0.92 | 84.93 Ω at 131.2 ps, short | 94.15 Ω at 256.2 ps, short | +0.05 |
| 22 Ω | −1.913 | −2.962 | −7.39 at 4805 | −43.89 at 10000 | −1.90 | 84.94 Ω at 131.2 ps, short | 96.00 Ω at 256.2 ps, short | +0.08 |
| 33 Ω | −2.731 | −3.969 | −6.29 at 4775 | −44.46 at 10000 | −2.71 | 84.94 Ω at 131.2 ps, short | 97.41 Ω at 256.2 ps, short | +0.09 |
| 47 Ω | −3.672 | −5.100 | −5.30 at 4755 | −45.03 at 10000 | −3.65 | 84.94 Ω at 131.2 ps, short | 98.91 Ω at 256.2 ps, short | +0.11 |

- **At the marker,** Sdd21 follows a series resistance R in each leg of a matched 90 Ω pair, 20·log10(90/(90 + R)): −0.915, −1.900, −2.713 and −3.650 dB for 10, 22, 33 and 47 Ω, within 0.023 dB of the sweep. Scc21 follows the same formula, as the common mode's R/2 against its 22.5 Ω target gives the same ratio.
- **The levels and the match:** the highest level rises with R, from 89.82 Ω (0R, in band, I_SI_TDR_LEVEL) to 98.91 Ω (47 Ω); the lowest stays at 84.93–84.94 Ω; the worst Sdd11 rises from −10.13 to −5.30 dB. The 22 Ω row equals the run's own lines, the chain at `new`'s values.

## 5. The retune with snapping, and verify

**The solid board's retune at `$v` = 24** (the applied values, with the 0402's ESL 0.5 nH and ESR 0.1 Ω) exited 0, and project.json holds R1 and R2 at '24'. Its lines: Sdd21 −2.067 dB at the marker and −3.154 dB at f_max; the worst Sdd11 −7.16 dB at 4800 MHz; the worst Scd21 −44.00 dB at 10000 MHz; Scc21 −2.06 dB; the levels 84.94 Ω at 131.2 ps and 96.27 Ω at 256.2 ps, both short; skew +0.08 ps (N 199.9 ps, P 199.8 ps); NEXT −25.62 dB (9160 MHz) and FEXT −28.73 dB (9325 MHz).

**The solid board's verify:** 6 of 6 jobs converged ("6 verify jobs kept S, in 21 min"; the command took 1307 s). There is no E_ code, verify.s6p was written, and `verify.fingerprint` equals `results.fingerprint`.

| job | port | t_cut (ns) | last sample (ns) | residual (dB) | steps | wall (s) | MC/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 J1.3 | 3.036 | 3.061 | −60.8 | 37,975 | 422.3 | 186.3 |
| 2 | P2 J1.2 | 3.036 | 3.061 | −60.7 | 37,975 | 421.7 | 186.6 |
| 3 | P3 U1.3 | 3.024 | 3.036 | −60.2 | 37,665 | 428.9 | 182.0 |
| 4 | P4 U1.2 | 3.024 | 3.036 | −60.1 | 37,665 | 427.8 | 182.4 |
| 5 | P5 TP1.1 | 2.736 | 2.749 | −63.0 | 34,100 | 393.1 | 179.7 |
| 6 | P6 TP2.1 | 2.724 | 2.736 | −60.8 | 33,945 | 391.4 | 179.7 |

- **Its lines,** with every part an ideal 24 Ω in the grid: Sdd21 −2.068 dB at the marker and −2.829 dB at f_max; the worst Sdd11 −6.98 dB at 4600 MHz; the worst Scd21 −45.26 dB at 9680 MHz; Scc21 −2.05 dB; the levels 84.94 Ω at 131.2 ps (10.9 mm) and 92.80 Ω at 250.0 ps (20.7 mm), both short; skew +0.09 ps (N 195.8 ps, P 195.8 ps); NEXT −25.82 dB (8965 MHz) and FEXT −29.36 dB (9055 MHz); the same loss lines.
- I_VERIFY_COMPARE_SI: "verify against the retune at the same ideal values: max |ΔS| 0.0165 from the first point above DC to f_max, at 9900 MHz (|a| -19.1 dB)."
- I_VERIFY_LEVEL_SHORT twice: the lowest level "84.94 Ω against 84.94 Ω" and the highest "92.80 Ω against 93.00 Ω", each "one of them lies on a feature shorter than two resolution lengths, so it is not that feature's impedance."
- Then come passivity, σ_max 1.0000 at 10000.0 MHz, and reciprocity, 1.11e-02 at 10000.0 MHz, then I_OUTPUTS (verify.s6p), I_VERIFY_SCOPE_SI and the six limits last.
- **The package model's share:** the ideal-value retune that verify compares with reads 93.00 Ω; the applied retune, with the 0402's ESL and ESR, reads 96.27 Ω and −3.154 dB at f_max, where verify's ideal parts read −2.829 dB. That difference is the package model's, which I_VERIFY_SCOPE_SI names.

**The plane-gap board's retune at 24,** on the rerun's results, exited 0 in 10 s. R1 and R2 stay at '24'. Its lines equal the rerun's own (§3), the chain at the same applied values.

**The plane-gap board's verify:** 6 of 6 jobs converged, at 71–73 % of T_max ("6 verify jobs kept S, in 2 h 35 min"; the command took 9368 s). There is no E_ code, verify.s6p was written, and `verify.fingerprint` equals `results.fingerprint`.

| job | port | t_cut (ns) | last sample (ns) | residual (dB) | steps | wall (s) | MC/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P1 J1.3 | 23.402 | 23.415 | −61.4 | 290,470 | 3107.5 | 203.8 |
| 2 | P2 J1.2 | 23.415 | 23.427 | −61.3 | 290,625 | 3108.1 | 203.9 |
| 3 | P3 U1.3 | 22.715 | 22.727 | −62.3 | 281,945 | 3057.7 | 201.0 |
| 4 | P4 U1.2 | 22.727 | 22.752 | −62.1 | 282,255 | 3049.1 | 201.8 |
| 5 | P5 TP1.1 | 23.477 | 23.490 | −61.1 | 291,400 | 3140.9 | 202.3 |
| 6 | P6 TP2.1 | 23.340 | 23.352 | −61.8 | 289,695 | 3136.3 | 201.4 |

- **Its lines,** with every part an ideal 24 Ω in the grid:
  - Sdd21 −2.067 dB at the marker and −3.052 dB at f_max;
  - the worst Sdd11, −7.25 dB at 4550 MHz, and the worst Scd21, −27.61 dB at 9410 MHz;
  - Scc21 −2.06 dB;
  - the levels 85.28 Ω at 131.2 ps (10.9 mm) and 95.01 Ω at 250.0 ps (20.7 mm), both short;
  - skew +0.46 ps (N 203.2 ps, P 202.7 ps);
  - NEXT −20.41 dB (8555 MHz) and FEXT −23.03 dB (9470 MHz);
  - the same loss lines.
- I_VERIFY_COMPARE_SI: "verify against the retune at the same ideal values: max |ΔS| 0.0170 from the first point above DC to f_max, at 8260 MHz (|a| -13.4 dB)."
- I_VERIFY_LEVEL_SHORT twice: the lowest level "85.28 Ω against 85.28 Ω" and the highest "95.01 Ω against 95.22 Ω".
- Then come passivity, σ_max 1.0092 at 2315.0 MHz (|a| -1.1 dB), and reciprocity, 9.53e-03 at 9465.0 MHz, then I_OUTPUTS (verify.s6p), I_VERIFY_SCOPE_SI and the six limits last.
- **The package model's share** is the same as on the solid board:
  - the applied retune reads 98.32 Ω and −3.538 dB at f_max;
  - verify's ideal parts read 95.01 Ω and −3.052 dB;
  - the ideal-value retune that verify compares with reads 95.22 Ω.

## 6. Compare's deltas

`compare <RUN>\usb2_hs <RUN>\usb2_hs_gap -o <RUN>\compare` exited 0 in 11 s. Its English rerun into `<RUN>\compare_en`, also 0 in 11 s, gives the lines quoted here. There was no E_COMPARE_SETTINGS: the two settings fingerprints are equal, as `t_max_s` lies outside them.

- **The two I_COMPARE_BASIS lines:**
  - "Base: `<RUN>\usb2_hs\project.json`, compared by its verify in `<its verify folder>`." and "Variant: `<RUN>\usb2_hs_gap\project.json`, compared by its verify in `<its verify folder>`."
  - Each names its own board's verify folder (source T_VERIFY).
- **The lines:** I_SI_RELATIVE comes first, then the deltas, base against variant:
  - "The lowest TDR level between the launches: 84.94 Ω against 85.28 Ω, +0.34 Ω: not resolved; one of them lies on a feature shorter than two resolution lengths, so it is not that feature's impedance, and the delta compares two levels filtered alike."
  - "The highest TDR level between the launches: 92.80 Ω against 95.01 Ω, +2.21 Ω: resolved; …", with the same tail.
  - "Sdd21 at 240 MHz: -2.068 dB against -2.067 dB, +0.001 dB: not resolved."
  - "Sdd21 at 10000 MHz: -2.829 dB against -3.052 dB, -0.223 dB: resolved."
  - "The worst Sdd11 up to f_max: -6.98 dB against -7.25 dB, -0.27 dB: not resolved."
  - "The worst Scd21 up to f_max: -45.26 dB against -27.61 dB, +17.65 dB: resolved."
  - "The intra-pair skew: +0.09 ps against +0.46 ps, +0.37 ps: not resolved."
  - "NEXT into AUX, its peak: -25.82 dB against -20.41 dB, +5.42 dB: resolved."
  - "FEXT into AUX, its peak: -29.36 dB against -23.03 dB, +6.34 dB: resolved."
  - I_SI_COMPARE_THRESHOLDS: "Resolved means larger than the significance threshold: 1 Ω on a TDR level, 0.05 dB on Sdd21 or S21, 0.5 dB on Sdd11, S11, Scd21, NEXT and FEXT where the higher of the two levels stands above -50 dB, and 1 ps on the skew: the design's registered values until gate P4-E measures the model's noise."
  - Then I_OUTPUTS ("Wrote compare.csv, compare.png in `<RUN>\compare_en`.") and the six limits last.
- **compare.csv** has nine rows, under the columns quantity, marker, f_hz, base, variant, unit, delta, delta_unit, threshold and resolved. Rounded:

| quantity | marker | base | variant | delta | threshold | resolved |
| --- | --- | --- | --- | --- | --- | --- |
| tdr_lowest | short | 84.940 Ω | 85.277 Ω | +0.337 Ω | 1.0 | False |
| tdr_highest | short | 92.798 Ω | 95.011 Ω | +2.213 Ω | 1.0 | True |
| sdd21 | marker (240 MHz) | −2.0678 dB | −2.0669 dB | +0.0009 dB | 0.05 | False |
| sdd21 | f_max (10 GHz) | −2.8294 dB | −3.0525 dB | −0.2231 dB | 0.05 | True |
| sdd11_worst | | −6.979 dB | −7.247 dB | −0.267 dB | 0.5 | False |
| scd21_worst | | −45.259 dB | −27.613 dB | +17.646 dB | 0.5 | True |
| skew | | +0.088 ps | +0.462 ps | +0.374 ps | 1.0 | False |
| next | AUX | −25.822 dB | −20.405 dB | +5.417 dB | 0.5 | True |
| fext | AUX | −29.365 dB | −23.027 dB | +6.338 dB | 0.5 | True |

- **compare.png** is written beside it.
- **What compare resolves:**
  - Five deltas are resolved: the highest level, Sdd21 at f_max, Scd21, NEXT and FEXT. Four are not: the lowest level, Sdd21 at the marker, Sdd11 and the skew.
  - The plane gap raises Scd21, the differential-to-common conversion, by 17.65 dB. This is P4-F's expected positive control, previewed here and not judged.
  - It also raises the crosstalk into AUX by 5.4–6.3 dB and lowers Sdd21 at f_max by 0.22 dB. At the marker the two boards agree within 0.001 dB.

## 7. Validity

- **The solid board:** layout.s8p has 8 ports and 2001 points from 0 to 10 GHz in 5 MHz steps, all at 50 Ω, with σ_max 1.00113 at 9.415 GHz and reciprocity 0.00990 at 10 GHz. chain.s6p reads σ_max 1.00003 at DC and reciprocity 0.01079 at 10 GHz; verify.s6p reads 1.00005 and 0.01114, both at 10 GHz. All are within the plan's σ_max ≤ 1.02 and error ≤ 0.02.
- **The gap's first run failed this check:** layout.s8p σ_max 1.11124 and chain.s6p 1.08495, both at 2.350 GHz; reciprocity, 0.00783 and 0.00885, stayed within. With every job at T_max, this was the hard-check failure that ruling R8-1 answers.
- **Ruling R8-1** (a controller recommendation, owner unavailable):
  - **The diagnosis:** no code defect. The slot in In1.Cu (x 116–117 mm, y 97–103 mm) couples the pair's return current into the In1–In2 plane cavity, which rings in the lossless model after the pulse leaves. From 3 to 9 ns each job's residual fell 1.2–2.4 dB/ns. si_t_max follows the route's round trips (9 ns here), and W_JOB_T_MAX and the flagged passivity are the designed responses.
  - **The fix,** by Stage 3's ruling 9 (P3-C): each job's residual from 6 to 9 ns was fitted with a least-squares line and projected to the normal preset's −60 dB. The latest projection was 20.71 ns (job 6); × 1.5, rounded up to a whole ns, gives 32 ns. The gap's `t_max_s` was raised to 32 ns by hand, as W_JOB_T_MAX says ("raise t_max_s in project.json for a converged result"). A fit from 4 ns gave 17.48 ns and 27 ns; the later, slower decay was taken.
  - **The solid board's results stand:** `t_max_s` is outside the SI settings fingerprint (Stage 4 design §5.8), and the solid board converges near 3 ns.
  - **The rerun's evidence:**
    - The second attempt converged 8 of 8 (I_JOB_CONVERGED), at 20.48–22.78 ns and −60.6 to −63.2 dB. Its P1 to P6 stopped within the stopped first attempt's 20.7–22.8 ns.
    - Per job, the projections from 6 to 9 ns were 16.74, 16.38, 16.23, 16.34, 19.52 and 20.71 ns (P1 to P6), and 15.67 and 15.77 ns (R1, R2). The stops were 22.78, 22.78, 20.72, 20.89, 22.70, 22.08, 20.48 and 20.52 ns.
    - So each job stopped at 1.07–1.39 times its own projection, 1.4–6.4 ns later: the decay slowed after 9 ns.
    - The latest stop, 22.78 ns (P1, P2), is 1.10 times the latest projection, inside the 1.5 margin, and 71 % of T_max. The margin was needed, as per job the stops reached 1.39 times their projections.
    - The gap's verify converged 6 of 6 at 22.71–23.48 ns, 73 % of T_max at most.
  - **Carried to plan 4:** an SI T_max for planes that ring (from the residual's decay, as ruling 9, or a note at cost), and P4-D's loss, which damps the ring.
- **The gap's rerun:**
  - layout.s8p (8 ports, 2001 points from 0 to 10 GHz, 50 Ω) reads σ_max 1.01155 at 2.350 GHz and reciprocity 0.00871 at 10 GHz.
  - chain.s6p reads 1.00715 at 2.350 GHz and 0.01031 at 9.480 GHz.
  - verify.s6p reads 1.00923 at 2.315 GHz and 0.00953 at 9.465 GHz.
  - All are within σ_max ≤ 1.02 and error ≤ 0.02. The run's and the verify's lines carry I_PASSIVITY, not W_PASSIVITY.
  - At 2.35 GHz, where the 9 ns run's excess was, σ_max fell from 1.111 to 1.012 once the ring had run out, consistent with R8-1's diagnosis. It is still the largest of the boards' (the solid board's is 1.00113).

## 8. Times against cost

- **The fresh calibration over-read the per-job speed:** 353.3 MC/s a job, against the solid run's 193.9–203.6 MC/s (mean 198.4). That is 1.74–1.82 times, 1.78 at the mean; plan 2 found 1.85.
- **The solid run:** cost said 43 min worst case (8 runs to T_max 9 ns, 2 at once with 8 threads each). The run took 1611.8 s (26.9 min; the line prints "26 min"), its jobs converging at 31–34 % of T_max. At the measured speed the worst case would have been about 1 h 18 min.
- **The gap's first run:** its cost came after the solid run had refreshed the pool-2 level (D-16) and said 1 h 21 min worst case. Every job ran to T_max, in 5185.1 s (1 h 26 min). Predicted/measured is about 0.94.
- **The solid board's verify:** its cost line read 1 h 0 min worst case for 6 runs to T_max. It took 21 min, with its jobs at 179.7–186.6 MC/s converging near 3 ns.
- **The gap's rerun:** cost said 5 h 15 min worst case (8 runs to T_max 32 ns), with W_SI_LONG_RUN. In the stopped first attempt, the pairs P1–P2, P3–P4 and P5–P6 took 58, 48 and 54 min to converge.
  - The second attempt took 12142.9 s (3 h 22 min; the command took 12166 s), 64 % of the prediction.
  - Its jobs ran at 191.6–197.2 MC/s (mean 194.2) and took 2815–3197 s each, converging at 64–71 % of T_max.
  - At that speed the worst case would have been about 4 h 57 min (2.18 M cells × 396,976 steps a job, 8 jobs 2 at once), so the cost read 1.06 times it.
- **The gap's verify:** its cost line read 3 h 42 min worst case for 6 runs to T_max 32 ns, with W_SI_LONG_RUN.
  - It took 2 h 35 min (the command took 9368 s), its jobs at 201.0–203.9 MC/s (mean 202.4), converging at 71–73 % of T_max.
  - At that speed the worst case would have been about 3 h 34 min, so the cost read 1.04 times it.
- **Each prediction matches the per-job speed of the latest run or verify (D-16).** Worked from the cells, the steps and 2 at once:
  - the rerun's 5 h 15 min matches 182.8 MC/s, the mean of the solid board's verify;
  - its verify's 3 h 42 min matches 194.2 MC/s, the mean of the rerun;
  - each to the minute.
- **The retunes:** the sweep's steps took 7–10 s each, and the solid board's retune 7 s and the gap's 10 s, both times. Compare's refusal took 14 s, and both of its runs on the two verifies took 11 s.
- **No constant changed.** The SI cost refit is plan 4's.

## 9. The stated limits, and what the window between the launches holds on this route

- **The six limit lines** end every run's, verify's and compare's lines. In English:
  - I_LIMIT_SI_CROP: "Limit: the region is cropped inside walls that absorb most of what reaches them and reflect the rest; the planes' cavity resonances depend on the crop, and an open line's radiation is absent."
  - I_LIMIT_PEC: "Limit: copper is PEC, so there is no conductor loss."
  - I_LIMIT_SI_LOSSLESS: "Limit: the dielectric is lossless, so S holds no dielectric loss; the loss lines estimate it."
  - I_LIMIT_SI_BODIES: "Limit: packages, dies and connector bodies are absent, and a part of three or more pads is its pads alone."
  - I_LIMIT_SI_PORTS: "Limit: the ports are lumped 50 Ω ports at the pads, whose own launch fills the first resolution length at each."
  - I_LIMIT_SI_RESOLUTION: "Limit: the TDR resolves no feature shorter than two resolution lengths: such a feature's level is not its impedance."
  - The design's last limit, that the results compare variants under identical settings and do not predict measured performance, is I_SI_RELATIVE itself, which opens each result's own lines (§3).
- **The window:**
  - At 125 ps and the route's 2D εeff 3.28, the resolution length is 10.35 mm; the line prints 10.3 mm.
  - So the 30.4 mm route keeps about 0.9 resolution lengths, about 110 ps, between the launches.
  - U2's run and the resistors read inside the launches. The plane gap's x 116–117 mm, about 17.5 mm along the route, lies between them.
  - As the plan expected, not judged: each board's two levels read the route's middle, blurred by both launches. They sit near the window's edges (131.2 ps or 10.9 mm, and 256.2 ps or 21.2 mm), and each is marked I_SI_TDR_SHORT. The one level not marked is the 0R sweep's highest, 89.82 Ω at 206.2 ps (17.1 mm): within 1 Ω of the target, it reads I_SI_TDR_LEVEL, in the target band.
- **The gap on the TDR:**
  - **The 9 ns run** (22 Ω): the highest level read 98.05 Ω against the solid board's 96.00 Ω, at the same 256.2 ps, and was marked short.
  - **The rerun's chain at 24 Ω** reads 85.27 and 98.32 Ω, against 84.94 and 96.27 Ω in the solid board's retune at 24 Ω. So at 24 Ω the gap adds 2.05 Ω to the highest level, as the truncated 9 ns run's did at 22 Ω.
  - **The verifies** read 85.28 and 95.01 Ω, against 84.94 and 92.80 Ω.
  - **The marks:** every level is marked short (I_SI_TDR_SHORT, I_VERIFY_LEVEL_SHORT), and compare marks both deltas short (I_SI_COMPARE_LEVEL_SHORT).
  - **What it means:** the highest level's +2.21 Ω is resolved. But as the line says, neither level is that feature's impedance, and the delta compares two levels filtered alike.
- **The ring:** the lossless model's In1–In2 cavity rings after the pulse. I_LIMIT_SI_CROP names the planes' cavity resonances, and R8-1 is how this run met them.

## 10. Next

- **Plan 4, the gates** (Stage 4 design §5.12 item 4):
  - the SI cost refit, with this run's 1.78 times over-reading and its times (§8);
  - shared mesh lines (P4-C);
  - P4-D's Debye fit, which damps the ring;
  - P4-E's thresholds;
  - P4-F's check of the short-feature rule on FDTD data, with the gap as the positive control previewed here (§6);
  - an SI T_max for planes that ring (R8-1, §7).
- **Plan 5, the GUI, the button and the docs** (§5.12 item 5): the GUI's Results page on draw_si, the Compare page on two SI projects, the README's SI tutorial, the release check, the acceptance run through the window and the Stage 4 exit record.

The Stage 1 spec's amendments A-54 to A-57 land with this record. They are controller recommendations, made while the owner was unavailable, and the Stage 4 exit record carries them as owner items.
