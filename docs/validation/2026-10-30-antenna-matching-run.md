# The matching flow on the pi variant: run, retune, verify and compare (2026-10-30)

## 1. Purpose

Stage 3's plan 3 ends with one end-to-end run of the matching flow on the 2.4 GHz fixture's pi variant, `ifa2g4_pi`. The run went through these steps:

- `new --antenna`, `cost`, and `run`, with the three matching parts as part ports, then `cost` again;
- the instant retune, at values searched over E24, the values the GUI's snapping gives;
- `verify`, with the far field;
- the what-if retune;
- the same run with the network bypassed, and its own verify;
- `compare` of the two projects.

The plan registered the checks before the run. This is not a gate: gates P3-B to P3-E are plan 4's (Stage 3 design §5.11). The run shows that the matching flow works end to end on openEMS. It also measures two things: the co-simulation's consistency on an antenna, and the cost at a pool of 4 jobs.

## 2. Inputs

- **Commands.** Each block ran in one PowerShell call from the repo root. In each call, LOCALAPPDATA and XDG_DATA_HOME were set to `<RUN>\data` and `CSXCAD_INSTALL_PATH` to the openEMS folder. `<RUN>` is a folder under the user's temp folder, outside every work tree. The board was copied there from `tests/fixtures/ifa2g4_pi.kicad_pcb`.
  ```
  kicad-rf-studio new <RUN>\ifa2g4_pi.kicad_pcb --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o <RUN>\proj
  kicad-rf-studio cost <RUN>\proj
  kicad-rf-studio run <RUN>\proj
  kicad-rf-studio cost <RUN>\proj
  (copy <RUN>\proj to <RUN>\proj_b)
  kicad-rf-studio retune <RUN>\proj L1=0R C2=0.13pF C3=1pF
  kicad-rf-studio verify <RUN>\proj
  kicad-rf-studio retune <RUN>\proj
  kicad-rf-studio retune <RUN>\proj_b L1=0R C2=open C3=open
  kicad-rf-studio verify <RUN>\proj_b
  kicad-rf-studio compare <RUN>\proj <RUN>\proj_b -o <RUN>\compare
  ```
  - **Exit codes:** 0 for all ten commands.
  - **`proj_b`** was copied right after the run. It holds the same run, with no verify.
  - **The English lines** in §4 were made afterwards, with no openEMS run.
- **The search** ran in the controller's scratch, before the retune, and is not committed.
  - **Candidates:** L1 at `0R` and the 39 E24 values from 0.51 to 20 nH; C2 and C3 each at `open` and the 49 E24 values from 0.1 to 10 pF. That is 100,000 sets.
  - **How each set was closed:** as the retune closes it, on the run's layout. Each part used its 0402 preset (ESL 0.5 nH, ESR 0.1 Ω; Cp 30 fF on an L) across its port box's C_box (L1 5.57 fF; C2 and C3 5.42 fF). A bypass has no package model.
  - **The score:** the largest |S11| over the 32 layout points from f_lo to f_hi.
  - **Best set:** L1=0R C2=0.13pF C3=1pF, at −10.33 dB. The product's own `assign` and `chain_results` gave the same value, to 0.
  - **Next sets:** L1=560pH C2=0.24pF C3=1pF and L1=0R C2=0.15pF C3=1pF, both at −10.25 dB.
  - **For comparison:** the run's own values (2.7 nH, 1 pF, 1 pF) read −4.00 dB, and the network all bypassed reads −2.51 dB.
- **Versions:**
  - product code `bb6c363` on branch `stage3-plan3`;
  - Python 3.14.2, openEMS 0.37.0, CSXCAD 0.7.0, scikit-rf 2.2.0, NumPy 2.5.4, h5py 3.16.0;
  - Windows 11 (10.0.26200), 16 CPUs.
  - At `bb6c363` the suite passed (1964 passed, 5 skipped), and so did the GUI tests in pt-BR (36 passed, 2 skipped).
- **Calibration:** fresh, made by the first `cost` in the isolated data folder.
  - 822.3 MC/s in aggregate, at a pool of 4 jobs × 4 threads.
  - At 4 threads: one job alone ran at 586.6 MC/s, and four at once at 205.6 MC/s each.
  - Two at once, at 8 threads each, reached 678.4 MC/s in aggregate.
  - One job at 1, 2 and 16 threads: 184.7, 265.6 and 324.5 MC/s.
- **The project, as `new` wrote it:**
  - **Band and time:** 2400–2483.5 MHz, f0 2441.75 MHz; the pulse over 1840–2990 MHz; T_max 30 ns; the Normal preset.
  - **Mesh and region:** mesh n 2, cell d 0.300 mm. The measured region is 6 substrate heights past the antenna and the chain.
  - **Absorber:** an air gap of 31.2 mm to a PML_8 absorber.
  - **Far field:** 11 frequencies on a 5° sphere.
  - **The chain:** U1.1 → AE1.1, with series L1 2.7 nH (RF_A–RF) and shunts C2 1 pF (RF_A–GND) and C3 1 pF (RF–GND). Each part is a part port with the 0402 preset.
  - **Other parts:** C1 (100 nF, VDD–GND) is copper.
  - **Port and join:** the port P1 is signal U1.1 with reference U1.2 (rule "ic"). The join is AE1.2.
- **The settings fingerprint**, recorded by the run and by both verifies:
  - preset normal; mesh n 2, reach 6 substrate heights; region 6;
  - the band, f0, T_max 30 ns, an air gap of 31.228 mm, the boundary pml_8, the 11 far-field frequencies at 5°;
  - the stackup from the board: masks 0.01 mm at εr 3.3, copper 0.035 mm, a dielectric of 0.71 mm at εr 4.5 and tan δ 0.02;
  - no lid height; start U1.1; solid copper;
  - app 0.1.0.dev0; openEMS 0.37.0.

## 3. The cost at a pool of 4

| | value |
| --- | --- |
| mesh | 135 × 143 × 71 = 1,370,655 nodes |
| split | board 106,502 (7.8 %), air 668,623 (48.8 %), PML 595,530 (43.4 %) |
| corrected work | N − N_PML + 6.38·N_PML = 4,574,606 cell equivalents (3.34 × N); the PML holds 83.1 % of it |
| corrected speed at a pool of 4 | 0.384 × 205.6 MC/s = 78.9 MC/s of cell equivalents a job, 23.7 MC/s of nodes |
| predicted, from the run's longest stop time (cost2's I_COST_PREDICTED, printed "1 h 36 min") | 5,792.6 s: C3's 99,962 timesteps (12.62 ns at dt 1.2625e-13 s), one round of 4 jobs |
| measured, the job phase (`results.wall_s`) | 3,760.0 s |
| openEMS's own, the 4 jobs at once | P1 3,475.8 s (88,377 timesteps, 34.85 MC/s); L1 3,647.6 s (94,997, 35.70 MC/s); C2 3,480.8 s (88,377, 34.80 MC/s); C3 3,743.5 s (99,962, 36.60 MC/s) |
| **ratio predicted/measured** | **1.541**, outside [0.67, 1.5] |
| worst case to T_max, as printed | 3 h 49 min (4 runs to 30 ns, 4 at once, 4 threads each) |

- **The ratio misses the range by 0.04.** This was SMALL_SPEED's first measurement at a pool of 4; the first run measured it at a pool of 1. As the plan states, PML_WEIGHT and SMALL_SPEED stay as they are, and plan 4's P3-C refits them.
- **What it shows.** The calibration slows down under concurrency more than this model does.
  - The calibration's 4-at-once level is 35.0 % of its one-job speed (205.6 against 586.6 MC/s).
  - This model ran at about 35 MC/s of nodes a job, 4 at once. That is 48 % of the 72.4–72.9 MC/s the same mesh reached alone in the two verify jobs.
- **At a pool of 1 the correction holds.**
  - The cost formula gives 1,902.3 s and 1,828.4 s for the two verify jobs at their stop times, against openEMS's 1,762.0 s and 1,704.7 s: ratios 1.080 and 1.073.
  - The first run's ratio was 1.128.
  - At this PML weight, a SMALL_SPEED of 0.59 would give a ratio of 1 at a pool of 4.
- **The times:**
  - **The run:** 4 jobs at once, the job phase 1 h 2 min 40 s. The whole `run` took 62 min 58 s. The jobs converged at 11.12, 11.95, 11.12 and 12.58 ns of 30 ns, near 40 % of T_max.
  - **verify of `proj`:** one job, 93,673 timesteps to 11.83 ns, in 1,762.0 s at 72.87 MC/s. The far-field transform took about 7 s: its folder was made at 16:52:15 and its three files were written by 16:52:22. The whole command took 30 min 0 s.
  - **verify of `proj_b`:** one job, 90,032 timesteps to 11.37 ns, in 1,704.7 s at 72.39 MC/s. The transform took about 8 s. The whole command took 29 min 5 s.
  - **The rest:** the three retunes, `compare` and the copy took about 9 s together. The plan had expected about an hour for this step, and it took 59 min 14 s.

## 4. The lines

Each command printed its lines in pt-BR, Windows' display language. Below are the English renders, with the same numbers:

- **The run's and both verifies' lines:** their result events, rendered under LANGUAGE=en.
- **retune2's lines:** `retune <RUN>\proj` with no values, run again under LANGUAGE=en. `proj` still held retune2's values and its verify.
- **compare's lines:** `compare` run again under LANGUAGE=en with `-o <RUN>\compare_en`.

Every block carries the relative label. Each block after the first ends with the same five Limit lines as the run's, which are left out below.

### 4.1 The run

```
4 of 4 jobs kept S, in 1 h 2 min; results recorded in <RUN>\proj\project.json.
Results of the run in <RUN>\data\kicad-rf-studio\runs\proj-20261030-151746-78e5 at preset normal: 4 jobs converged, 0 flat, 0 at T_max.
Passivity: σ_max 1.0015 at worst, at 2279.9 MHz (|a| -1.1 dB); flagged above 1.02.
Reciprocity: |Sij − Sji| 6.00e-03 at worst, at 2990.0 MHz (|a| -19.5 dB); flagged above 0.02.
Relative: these antenna results compare variants of one board under identical settings; they do not predict measured performance.
Resonance (lowest |S11|): 2325.8 MHz, |S11| -6.9 dB, Zin at U1.1 43.2 - j46.7 Ω.
f_lo = 2400.0 MHz: |S11| -5.6 dB, Zin at U1.1 17.5 - j16.0 Ω, mismatch efficiency 72.6 %.
f0 = 2441.8 MHz: |S11| -4.7 dB, Zin at U1.1 13.3 - j4.2 Ω, mismatch efficiency 66.2 %.
f_hi = 2483.5 MHz: |S11| -4.0 dB, Zin at U1.1 11.5 + j5.9 Ω, mismatch efficiency 60.2 %.
-10 dB bandwidth: none, as |S11| stays above -10 dB.
-6 dB bandwidth: 2274.2 to 2384.3 MHz (110.1 MHz).
No far field for this run: a run with part ports records none, as its jobs hold ports where the matching parts sit; `kicad-rf-studio verify <RUN>\proj\project.json` runs one job with each part in the grid at its value, as an ideal part, and records it.
Relative / what-if: the instant retune is not yet validated against a full simulation of a real board (spec 7.6), so read these chain results as relative. Check the final values with `kicad-rf-studio verify <RUN>\proj\project.json`.
Wrote antenna_summary.png, chain.s1p, layout.s4p in <RUN>\proj\results.
Limit: the board alone in free space.
Limit: copper is a perfect conductor, so the radiation efficiency reads high.
Limit: no enclosure, hand, battery or cable.
Limit: the parts' bodies are absent; only their pads are in the board file.
Limit: the parts off the chain are approximated: capacitors close to a short as copper, the rest open or in the grid, and past the measured region only as fine as its coarse mesh.
```

### 4.2 retune2: L1=0R C2=0.13pF C3=1pF, after verify

```
Results of the run in <RUN>\data\kicad-rf-studio\runs\proj-20261030-151746-78e5 at preset normal: 4 jobs converged, 0 flat, 0 at T_max.
Passivity: σ_max 1.0015 at worst, at 2279.9 MHz (|a| -1.1 dB); flagged above 1.02.
Reciprocity: |Sij − Sji| 6.00e-03 at worst, at 2990.0 MHz (|a| -19.5 dB); flagged above 0.02.
Relative: these antenna results compare variants of one board under identical settings; they do not predict measured performance.
Resonance (lowest |S11|): 2443.4 MHz, |S11| -17.4 dB, Zin at U1.1 60.6 - j10.5 Ω.
f_lo = 2400.0 MHz: |S11| -10.3 dB, Zin at U1.1 65.8 + j33.1 Ω, mismatch efficiency 90.7 %.
f0 = 2441.8 MHz: |S11| -17.4 dB, Zin at U1.1 62.1 - j9.2 Ω, mismatch efficiency 98.2 %.
f_hi = 2483.5 MHz: |S11| -10.5 dB, Zin at U1.1 32.1 - j17.6 Ω, mismatch efficiency 91.1 %.
-10 dB bandwidth: 2397.7 to 2486.6 MHz (89.0 MHz).
-6 dB bandwidth: 2356.6 to 2521.5 MHz (164.9 MHz).
2400.0 MHz: total efficiency 73.6 % what-if: the last verify's radiation efficiency 81.3 % times the 90.6 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2409.3 MHz: total efficiency 75.8 % what-if: the last verify's radiation efficiency 81.3 % times the 93.2 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2418.6 MHz: total efficiency 77.5 % what-if: the last verify's radiation efficiency 81.3 % times the 95.3 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2427.8 MHz: total efficiency 78.7 % what-if: the last verify's radiation efficiency 81.3 % times the 96.8 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2437.1 MHz: total efficiency 79.4 % what-if: the last verify's radiation efficiency 81.3 % times the 97.7 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2441.8 MHz: total efficiency 79.5 % what-if: the last verify's radiation efficiency 81.3 % times the 97.8 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2446.4 MHz: total efficiency 79.4 % what-if: the last verify's radiation efficiency 81.3 % times the 97.7 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2455.7 MHz: total efficiency 78.8 % what-if: the last verify's radiation efficiency 81.2 % times the 97.0 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2464.9 MHz: total efficiency 77.5 % what-if: the last verify's radiation efficiency 81.1 % times the 95.6 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2474.2 MHz: total efficiency 75.6 % what-if: the last verify's radiation efficiency 81.0 % times the 93.3 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
2483.5 MHz: total efficiency 73.2 % what-if: the last verify's radiation efficiency 80.9 % times the 90.4 % of the incident power that this retune's network passes to the board (its mismatch efficiency less its parts' own loss); a lossless network that does not radiate leaves the radiation efficiency and the pattern as they are.
Relative / what-if: the instant retune is not yet validated against a full simulation of a real board (spec 7.6), so read these chain results as relative. Check the final values with `kicad-rf-studio verify <RUN>\proj\project.json`.
Wrote antenna_summary.png, chain.s1p, layout.s4p in <RUN>\proj\results.
```

### 4.3 verify of `proj`: L1=0R C2=0.13pF C3=1pF

```
1 verify jobs kept S, in 29 min; the comparison is stored in <RUN>\proj\project.json.
Relative: these antenna results compare variants of one board under identical settings; they do not predict measured performance.
Resonance (lowest |S11|): 2446.6 MHz, |S11| -12.5 dB, Zin at U1.1 74.7 - j16.5 Ω.
f_lo = 2400.0 MHz: |S11| -9.3 dB, Zin at U1.1 71.6 + j37.8 Ω, mismatch efficiency 88.3 %.
f0 = 2441.8 MHz: |S11| -12.5 dB, Zin at U1.1 78.3 - j11.6 Ω, mismatch efficiency 94.4 %.
f_hi = 2483.5 MHz: |S11| -10.1 dB, Zin at U1.1 43.0 - j29.7 Ω, mismatch efficiency 90.2 %.
-10 dB bandwidth: 2407.4 to 2484.6 MHz (77.1 MHz).
-6 dB bandwidth: 2354.5 to 2532.1 MHz (177.6 MHz).
verify against the retune at the same ideal values: |ΔS11| 0.0076 at f0 = 2441.75 MHz (|a| -0.1 dB) and 0.0149 at most up to f2.
Resonance at 2446.6 MHz in verify against 2446.8 MHz in the retune: a shift of -0.01 %.
2400.0 MHz: radiation efficiency 81.3 %, total efficiency 71.8 %, directivity 2.51 dBi, gain 1.61 dBi, realized gain 1.07 dBi.
2409.3 MHz: radiation efficiency 81.3 %, total efficiency 73.5 %, directivity 2.52 dBi, gain 1.62 dBi, realized gain 1.18 dBi.
2418.6 MHz: radiation efficiency 81.3 %, total efficiency 74.9 %, directivity 2.53 dBi, gain 1.63 dBi, realized gain 1.27 dBi.
2427.8 MHz: radiation efficiency 81.3 %, total efficiency 75.9 %, directivity 2.54 dBi, gain 1.64 dBi, realized gain 1.34 dBi.
2437.1 MHz: radiation efficiency 81.3 %, total efficiency 76.5 %, directivity 2.54 dBi, gain 1.65 dBi, realized gain 1.38 dBi.
2441.8 MHz: radiation efficiency 81.3 %, total efficiency 76.7 %, directivity 2.55 dBi, gain 1.65 dBi, realized gain 1.40 dBi.
2446.4 MHz: radiation efficiency 81.3 %, total efficiency 76.7 %, directivity 2.55 dBi, gain 1.65 dBi, realized gain 1.40 dBi.
2455.7 MHz: radiation efficiency 81.2 %, total efficiency 76.5 %, directivity 2.56 dBi, gain 1.66 dBi, realized gain 1.39 dBi.
2464.9 MHz: radiation efficiency 81.1 %, total efficiency 75.8 %, directivity 2.57 dBi, gain 1.66 dBi, realized gain 1.36 dBi.
2474.2 MHz: radiation efficiency 81.0 %, total efficiency 74.6 %, directivity 2.57 dBi, gain 1.66 dBi, realized gain 1.30 dBi.
2483.5 MHz: radiation efficiency 80.9 %, total efficiency 73.0 %, directivity 2.58 dBi, gain 1.66 dBi, realized gain 1.21 dBi.
Passivity: σ_max 0.9665 at worst, at 2990.0 MHz (|a| -19.4 dB); flagged above 1.02.
Reciprocity: |Sij − Sji| 0.00e+00 at worst, at 1840.0 MHz (|a| -19.6 dB); flagged above 0.02.
Wrote verify.s1p, verify_farfield.csv, verify_summary.csv, verify_summary.png in <RUN>\proj\results.
verify checks the layout reduction, not the vendor part data: each part sat in the grid at its value as an ideal part, without the package ESL, ESR and Cp or the S2P data the retune applies, a 0 Ω part as copper and an open part left out, against a retune at the same ideal values; its far field holds that ideal network.
```

### 4.4 verify of `proj_b`: L1=0R C2=open C3=open

```
1 verify jobs kept S, in 28 min; the comparison is stored in <RUN>\proj_b\project.json.
Relative: these antenna results compare variants of one board under identical settings; they do not predict measured performance.
Resonance (lowest |S11|): 2262.9 MHz, |S11| -7.7 dB, Zin at U1.1 22.7 + j13.5 Ω.
f_lo = 2400.0 MHz: |S11| -3.9 dB, Zin at U1.1 64.8 + j93.3 Ω, mismatch efficiency 59.2 %.
f0 = 2441.8 MHz: |S11| -3.1 dB, Zin at U1.1 106.6 + j131.8 Ω, mismatch efficiency 50.9 %.
f_hi = 2483.5 MHz: |S11| -2.5 dB, Zin at U1.1 196.6 + j168.7 Ω, mismatch efficiency 44.0 %.
-10 dB bandwidth: none, as |S11| stays above -10 dB.
-6 dB bandwidth: 2202.3 to 2329.7 MHz (127.4 MHz).
verify against the retune at the same ideal values: |ΔS11| 0.0020 at f0 = 2441.75 MHz (|a| -0.0 dB) and 0.0041 at most up to f2.
Resonance at 2262.9 MHz in verify against 2262.7 MHz in the retune: a shift of +0.01 %.
2400.0 MHz: radiation efficiency 80.6 %, total efficiency 47.8 %, directivity 2.53 dBi, gain 1.59 dBi, realized gain -0.68 dBi.
2409.3 MHz: radiation efficiency 80.6 %, total efficiency 46.1 %, directivity 2.53 dBi, gain 1.60 dBi, realized gain -0.83 dBi.
2418.6 MHz: radiation efficiency 80.5 %, total efficiency 44.6 %, directivity 2.54 dBi, gain 1.60 dBi, realized gain -0.97 dBi.
2427.8 MHz: radiation efficiency 80.4 %, total efficiency 43.0 %, directivity 2.55 dBi, gain 1.60 dBi, realized gain -1.11 dBi.
2437.1 MHz: radiation efficiency 80.3 %, total efficiency 41.6 %, directivity 2.56 dBi, gain 1.60 dBi, realized gain -1.26 dBi.
2441.8 MHz: radiation efficiency 80.2 %, total efficiency 40.8 %, directivity 2.56 dBi, gain 1.60 dBi, realized gain -1.33 dBi.
2446.4 MHz: radiation efficiency 80.2 %, total efficiency 40.1 %, directivity 2.56 dBi, gain 1.60 dBi, realized gain -1.40 dBi.
2455.7 MHz: radiation efficiency 80.0 %, total efficiency 38.7 %, directivity 2.57 dBi, gain 1.60 dBi, realized gain -1.55 dBi.
2464.9 MHz: radiation efficiency 79.8 %, total efficiency 37.4 %, directivity 2.58 dBi, gain 1.60 dBi, realized gain -1.69 dBi.
2474.2 MHz: radiation efficiency 79.6 %, total efficiency 36.2 %, directivity 2.59 dBi, gain 1.59 dBi, realized gain -1.83 dBi.
2483.5 MHz: radiation efficiency 79.3 %, total efficiency 34.9 %, directivity 2.59 dBi, gain 1.59 dBi, realized gain -1.97 dBi.
Passivity: σ_max 0.9352 at worst, at 1840.0 MHz (|a| -19.6 dB); flagged above 1.02.
Reciprocity: |Sij − Sji| 0.00e+00 at worst, at 1840.0 MHz (|a| -19.6 dB); flagged above 0.02.
Wrote verify.s1p, verify_farfield.csv, verify_summary.csv, verify_summary.png in <RUN>\proj_b\results.
verify checks the layout reduction, not the vendor part data: each part sat in the grid at its value as an ideal part, without the package ESL, ESR and Cp or the S2P data the retune applies, a 0 Ω part as copper and an open part left out, against a retune at the same ideal values; its far field holds that ideal network.
```

### 4.5 compare `proj` `proj_b`

```
Relative: these antenna results compare variants of one board under identical settings; they do not predict measured performance.
Base: <RUN>\proj\project.json, compared by its verify in <RUN>\data\kicad-rf-studio\runs\proj-20261030-162225-d21e.
Variant: <RUN>\proj_b\project.json, compared by its verify in <RUN>\data\kicad-rf-studio\runs\proj_b-20261030-165229-2e94.
Resonance: 2446.6 MHz to 2262.9 MHz, a shift of -183.7 MHz (-7.53 % of f0): resolved.
-10 dB bandwidth: not compared, as one of the two has none bounded inside the simulated band.
Total efficiency at f_lo = 2400.0 MHz: 71.8 % to 47.8 %, -1.77 dB: resolved.
Total efficiency at f0 = 2441.8 MHz: 76.7 % to 40.8 %, -2.74 dB: resolved.
Total efficiency at f_hi = 2483.5 MHz: 73.0 % to 34.9 %, -3.20 dB: resolved.
Peak gain at f0 = 2441.8 MHz: 1.65 dBi to 1.60 dBi, -0.04 dB: not resolved.
Resolved means larger than the significance threshold: 0.3 % of f0 for a frequency and 0.2 dB for an efficiency or a gain, both provisional until gate P3-D measures the model's noise floor and sets them at three times it.
Wrote compare.csv, compare.png in <RUN>\compare_en.
```

## 5. The checks of Step 4

| check | pre-registered | measured | verdict |
| --- | --- | --- | --- |
| run: the jobs | its 4 jobs kept, with no E_ line | 4 of 4 converged, residuals −60.2 to −60.7 dB; no E_ code; W_FILLS_AS_SAVED is its only W_ code, a message | pass |
| run: the setup gate | I_GATES_PASSED_PML, with no E_PORT_SHORT, E_PORT_OPEN or E_PORT_BOX | I_GATES_PASSED_PML; none of the three | pass |
| run: no far field | `results.far_field` null, with I_ANTENNA_NO_FAR_FIELD | null; the line printed | pass |
| run: the fingerprint | `results.fingerprint` present | present (§2) | pass |
| run: `results/` | antenna_summary.png, chain.s1p, layout.s4p | those three | pass |
| retune | the searched values in project.json; chain.s1p's largest in-band \|S11\| within 0.05 dB of the search's | L1 0R, C2 0.13pF, C3 1pF; −10.3277 dB against the search's −10.3277 dB | pass |
| retune_b | L1 0R, C2 open, C3 open in proj_b's project.json; I_ANTENNA_NO_FAR_FIELD among its lines | both | pass |
| each verify: the job | its one job kept, with no E_ line and I_GATES_PASSED_PML | `proj`: converged at 11.78 ns, residual −61.0 dB; `proj_b`: at 11.32 ns, −60.4 dB; no E_ code; I_GATES_PASSED_PML in both | pass |
| each verify: the far field | `verify.far_field` names three files | sphere, elevation and azimuth in both (`nf2ff-cc4e5fa0-*.h5`, `nf2ff-fe9176bc-*.h5`) | pass |
| each verify: `results/` | gains verify.s1p, verify_farfield.csv, verify_summary.csv and verify_summary.png | all four in both | pass |
| each verify: η_rad | no W_ETA_RAD | none; η_rad 80.9–81.3 % and 79.3–80.6 % | pass |
| proj_b's verify: values and folder | `verify.values` {L1: 0R, C2: open, C3: open}; its `run_dir` not proj's | as stated; `proj_b-20261030-165229-2e94` against `proj-20261030-162225-d21e` | pass |
| proj_b's verify: the model | an empty grid and one copper box more than the run's model | grid empty (proj's verify: C2 and C3); 9 copper boxes against the run's 8, the added one over L1's port box | pass |
| retune2 | 11 I_ANTENNA_ETA_WHAT_IF lines, no I_ANTENNA_NO_FAR_FIELD | 11; none | pass |
| compare | two I_COMPARE_BASIS lines with T_VERIFY, each naming its own project's verify folder; compare.csv and compare.png | Base by its verify in `proj-20261030-162225-d21e`, Variant by its verify in `proj_b-20261030-165229-2e94`; both files written | pass |
| cost | predicted/measured within [0.67, 1.5] | 1.541 | outside, recorded (§3); PML_WEIGHT and SMALL_SPEED stay, P3-C refits them |
| verify's comparison (soft) | reported | §6 | reported |
| the ideal network's gap (soft) | reported | §6 | reported |
| proj_b's verify resonance (soft) | against the first run's 2388.2 MHz | 2262.9 MHz | reported (§6) |
| η_rad (soft) | 0.5 to 1.0 | 0.793 to 0.813 | inside |
| D at f0 (soft) | 1.5 to 4.5 dBi | 2.55 and 2.56 dBi | inside |
| compare's deltas (soft) | which are resolved; whether the resonance was compared | §7 | reported |
| the times (soft) | reported | §3 | reported |

## 6. Verify's consistency, the ideal network's gap and the far field at the applied values

**Verify's consistency.** Each verify was compared with the retune at the same ideal values. This is the co-simulation's consistency on an antenna:

| | `proj`: L1 0R, C2 0.13 pF, C3 1 pF | `proj_b`: all bypassed |
| --- | --- | --- |
| \|ΔS11\| at f0 | 0.0076 | 0.0020 |
| largest \|ΔS11\| up to f2 | 0.0149 | 0.0041 |
| resonance, verify against the retune | 2446.6 against 2446.8 MHz: −0.16 MHz (−0.01 %) | 2262.9 against 2262.7 MHz: +0.19 MHz (+0.01 %) |
| both dip to −6 dB or below in the band | yes (verify −12.5 dB) | yes (verify −7.7 dB) |

- **Against P0-B.** P0-B's lpf915 read \|ΔS\| near 0.003.
  - `proj_b`, whose grid is empty (only L1's copper), sits at that level.
  - `proj`, with C2 and C3 as lumped parts in the grid, reads 2.5 times that at f0 and 5 times at most.
  - Both shifts are more than 35 times under compare's 0.3 % threshold.

**The ideal network's gap.** At the applied values, the retune carries the 0402 presets, and verify holds ideal parts:

| | retune2 (presets) | retune at ideal values (verify's comparison) | verify (ideal, full simulation) |
| --- | --- | --- | --- |
| resonance | 2443.4 MHz, −17.4 dB | 2446.8 MHz | 2446.6 MHz, −12.5 dB |
| \|S11\| at f_lo, f0, f_hi | −10.3, −17.4, −10.5 dB | | −9.3, −12.5, −10.1 dB |
| −10 dB bandwidth | 2397.7–2486.6 MHz (89.0 MHz) | | 2407.4–2484.6 MHz (77.1 MHz) |
| η_tot at f0 | 79.5 %, what-if (81.3 % × 97.8 %) | | 76.7 % (81.3 % × 94.4 % mismatch) |

- **The gap is the package model.**
  - With 0.5 nH of ESL, C3's 1 pF reads as 1.13 pF at f0 (+13 %), and C2's 0.13 pF as +1.6 %. L1 is a bypass, so it has no package model.
  - The presets' network therefore resonates 3.4 MHz below the ideal network and matches deeper at f0: −17.4 against −12.5 dB.
  - The plan's figure of 12–18 % for a C covers C3.
- **The search tuned the presets' network.** So the retune's −10 dB over the whole band is not the ideal network's: verify's −10 dB band misses f_lo by 7.4 MHz. A built board follows its real parts, which neither model holds. The retune's S2P route (C-14) brings real parts in.

**The far field at the applied values** (verify of `proj`):

- **Across the band:** η_rad 80.9–81.3 %, D 2.51–2.58 dBi, gain 1.61–1.66 dBi, realized gain 1.07–1.40 dBi.
- **At f0:** η_rad 81.3 %, η_tot 76.7 %, D 2.55 dBi.
- **Against the bypassed network** (verify of `proj_b`): η_rad there is 79.3–80.6 % and D 2.53–2.59 dBi.
  - The matching network changes η_rad by 0.7 to 1.6 points and D by 0.02 dB at most. η_tot at f0 rises from 40.8 % to 76.7 %.
  - This supports the what-if's premise: a lossless network that does not radiate leaves η_rad and the pattern as they are.
- **A cross-check the plan did not register:** `proj`'s verify η_rad at f0 (81.3 %) times retune_b's mismatch efficiency at f0 (50.8 %) gives 41.3 %. `proj_b`'s own verify reads 40.8 %, a difference of 0.05 dB.

**proj_b's verify resonance** is 2262.9 MHz (−7.7 dB), against the first run's 2388.2 MHz (−5.9 dB). The two resonances do not compare one antenna, because the start pad sees the antenna through a different feed:

- the plain fixture's 12 mm feed: 1.975 mm of 72 Ω, then 10 mm of 47 Ω;
- the pi variant's 0.6 mm line: RF_A 5.49 mm and RF 5.52 mm, 69.7–71.5 Ω by cost's 2D estimate, with L1's pad pair bridged as copper and C2's and C3's pad pairs left open.

## 7. Compare's deltas

| quantity | base, `proj`'s verify | variant, `proj_b`'s verify | delta | threshold | verdict |
| --- | --- | --- | --- | --- | --- |
| resonance | 2446.6 MHz | 2262.9 MHz | −183.7 MHz (−7.53 % of f0) | 7.33 MHz (0.3 % of f0) | resolved |
| −10 dB bandwidth | 77.1 MHz | none | | | not compared |
| η_tot at f_lo | 71.8 % | 47.8 % | −1.77 dB | 0.2 dB | resolved |
| η_tot at f0 | 76.7 % | 40.8 % | −2.74 dB | 0.2 dB | resolved |
| η_tot at f_hi | 73.0 % | 34.9 % | −3.20 dB | 0.2 dB | resolved |
| peak gain at f0 | 1.65 dBi | 1.60 dBi | −0.04 dB | 0.2 dB | not resolved |

- **The resonance was compared:** both projects have their lowest \|S11\| at −6 dB or below inside the simulated band (−12.5 and −7.7 dB).
- **The bandwidth was not compared:** the bypassed network has no −10 dB bandwidth. In compare.csv, that row leaves the variant and the delta empty.
- **The deltas read as a network's would:**
  - The match lifts η_tot by 1.8 to 3.2 dB across the band.
  - It leaves the peak gain (D·η_rad) within 0.04 dB, under the threshold.
- **The recorded far-field frequencies are openEMS's float32 values.** compare.csv's `f_hz` column and verify_summary.csv print them, for example 2441750016 Hz for f0's 2441750000 Hz.
  - compare reads the recorded frequency nearest each marker, as designed. The 16 Hz offset is far under the 9.3 MHz spacing.
  - The print is noted for plan 5's outputs.

## 8. The stated limits

- **The printed limits.** The five limits that each command printed (§4.1) apply. So does verify's scope line: verify checks the layout reduction, not the vendor part data.
- **One run.** This is one run of one synthetic fixture variant, on one PC with 16 CPUs, at the defaults: mesh n 2, the Normal preset, a λ/4 air gap and solid copper.
  - Convergence is P3-C's, and the noise floor is P3-D's.
  - Compare's thresholds (0.3 % of f0 and 0.2 dB) stay provisional until P3-D sets them.
  - No number here is a validated antenna figure.
- **The search.** It is the controller's, over E24 at fixed ranges plus the bypasses. It tuned the retune's network with the 0402 presets on the run's layout, not the ideal network and not a real part's S2P (§6).
- **The retune's label.** The instant retune stays labeled "relative / what-if" until P0-C passes (A-4).
- **The what-if premise.** The what-if η_tot assumes a network that neither radiates nor changes the pattern. Here, the matched and the bypassed networks' η_rad differ by 1.1 points at f0.
- **The cost at a pool of 4** was measured once, on this model (§3).

## 9. Next

- **Plan 4: gates P3-B to P3-E** on the fixtures, as the first run's record planned them:
  - E_FIT2D_FINE at mesh n 3 and 4 explained before the mesh study;
  - the meander's first job measured before its other runs are scheduled;
  - PML_WEIGHT and SMALL_SPEED refitted, by pool level: this run's 1.54 at a pool of 4, and 1.07–1.13 at a pool of 1;
  - P3-D's noise floor setting compare's thresholds;
  - the fixture's ground plane and the ground-pour variant decided.
- **Plan 5: the GUI, the KiCad button, the docs and Stage 3's exit:**
  - the GUI's matching and comparison: the retune table's bypasses, `control.verify_stale` and the Compare page;
  - the KiCad button and the docs;
  - Stage 3's exit record.
