# The first antenna run: the 2.4 GHz fixture (2026-10-30)

## 1. Purpose

Stage 3's plan 2 ends with its first real antenna run: the 2.4 GHz inverted-F fixture through `new --antenna`, `cost`, `run` and `cost` again, against checks registered in the plan before the run. It is not a gate. Gates P3-B to P3-E are plan 4's (Stage 3 design §5.11). It shows that the antenna project runs end to end on openEMS, and it measures what an antenna job costs on this PC, so plan 4 can be planned on measured time.

## 2. Inputs

- **Commands**, each in one PowerShell call from the repo root, with LOCALAPPDATA and XDG_DATA_HOME set to `<RUN>\data` and `CSXCAD_INSTALL_PATH` set to the openEMS folder in the same call. `<RUN>` is a folder under the user's temp folder, outside every work tree; the board is copied there from `tests/fixtures/ifa2g4.kicad_pcb`.
  ```
  kicad-rf-studio new <RUN>\ifa2g4.kicad_pcb --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o <RUN>\proj
  kicad-rf-studio cost <RUN>\proj
  kicad-rf-studio run <RUN>\proj
  kicad-rf-studio cost <RUN>\proj
  ```
  Exit codes: 0, 0, 0, 0. Afterwards, `retune <RUN>\proj` with no values and LANGUAGE=en printed the result lines again in English (§5), from the stored results and transform, with no openEMS run. §7's two setups ran `new` and `cost` the same way.
- **Versions:** product code `b9d6e9b` on branch `stage3-plan2`; Python 3.14.2; openEMS 0.37.0; CSXCAD 0.7.0; Windows 11 (10.0.26200), 16 CPUs. At `b9d6e9b` the suite passed (1919 passed, 5 skipped) and so did the GUI tests in pt-BR (36 passed, 2 skipped).
- **Calibration**, fresh, made by the first `cost` in the isolated data folder: 741.1 MC/s in aggregate, a pool of 4 jobs × 4 threads; one job alone at 4 threads 580.2 MC/s, four at once 185.3 MC/s each (one job at 1, 2 and 16 threads: 180.6, 257.9 and 320.6 MC/s).
- **The project**, as `new` wrote it:
  - Band 2400–2483.5 MHz, f0 2441.75 MHz; the pulse over 1840–2990 MHz; T_max 30 ns (2·t0 + 60/f0); the Normal preset.
  - Mesh n 2, cell d 0.300 mm. The measured region is 6 substrate heights past the antenna and the chain.
  - An air gap of 31.2 mm (λ/4 at f_lo) to a PML_8 absorber.
  - Far field at 11 frequencies on a 5° sphere.
  - The chain is U1.1 → AE1.1 with no parts. The port P1 is signal U1.1 with reference U1.2 (rule "ic").
  - The join is AE1.2. C1 (100 nF) is copper.

## 3. The cost

| | value |
| --- | --- |
| mesh | 135 × 137 × 71 = 1,313,145 nodes |
| split | board 100,298 (7.6 %), air 637,621 (48.6 %), PML 575,226 (43.8 %) |
| corrected work | N − N_PML + 6.38·N_PML = 4,407,861 cell equivalents (3.36 × N); the PML holds 83.3 % of it |
| corrected speed | 0.384 × 580.2 MC/s = 222.8 MC/s of cell equivalents, 66.4 MC/s of nodes |
| predicted, from the run's stop time (cost2's I_COST_PREDICTED, printed "28 min") | 1,694.9 s |
| measured, the job phase (`results.wall_s`) | 1,502.1 s (openEMS's own: 1,489.6 s for 85,668 timesteps at 75.52 MC/s) |
| **ratio predicted/measured** | **1.128**, inside [0.67, 1.5]: pass |
| worst case to T_max, as printed | 1 h 26 min (5,160.6 s) |

PML_WEIGHT and SMALL_SPEED stay as gate P3-A set them; plan 4's P3-C refits them. Without them, v1's model would have predicted 193.9 s, 7.7 times under the measured time. The plan's probe of the draft model had measured 76.4 MC/s and a ratio of 1.13.

## 4. The runtime against the design's hope

- **Measured:** 25.0 minutes for the job, which converged at 9.81 ns and stopped at 9.85 ns of its 30 ns T_max. The whole `run` took 25 min 25 s: the setup gate 11 s, the job, the far-field transform 7 s and the outputs 2 s.
- **Against the design's hope:** design §1 hoped for 9–18 min per job at 2.4 GHz. The measured job is 1.4 times that range's top. A job that ran to T_max would take about 76 minutes at the measured speed.
- **Why it is slower:**
  - **The PML.** It is 43.8 % of the nodes, and at 6.38 cells each it is 83 % of the corrected work.
  - **The copper cell.** The smallest cell is the copper's 35.0 µm along z, at z = 0.018 mm. It sets dt at 1.1501e-13 s (floor 0.8 × 1.0964e-13 s), on the z edge at (99.100, 93.865, 0.000) mm, so a 30 ns T_max is 260,843 timesteps.
- **The machine hours for P3-B to P3-E.** Research note r4's estimate of 15–35 machine hours needs re-estimating. The estimate below rests on four inputs:
  - this run's 25 minutes;
  - §7's cost of the meander;
  - node counts built in memory with the product's own `load` and `build_model`, with no openEMS: mesh n 3 and n 4 give 1.49 and 2.26 times n 2's corrected work on the 2.4 GHz fixture and 1.47 and 2.13 times on the meander, and an air gap of λ/2 gives 1.31 and 1.23 times;
  - the run counts of the design §5.11 table.
- **The 2.4 GHz fixture's runs, about 9 hours:**
  - P3-B, about 1 h;
  - P3-C, its seven runs, about 4.5 h;
  - P3-D, four to five runs, about 2 h;
  - P3-E, about 1 h.
- **The meander's seven P3-C runs** decide the total. A meander job to its 79 ns T_max takes about 6.7 h: §7's cost prediction, 7 h 35 min, divided by this run's measured ratio, 1.128.
  - **About 24 h** if its job converges at the same third of its T_max as this one did, about 2.2 h a job.
  - **About 70 h** if a job rings to its T_max. Its run to 3 × the stop time alone would then take about 20 h.
- **The plan 4 re-estimate:** 30 to 80 machine hours, 70–90 % of it the meander's P3-C. r4's range holds only in the first case, near its top.
- **Two levers for plan 4:**
  - Measure the meander's first job before scheduling the rest.
  - Run P3-C's all-sheet comparison first. If all-sheet copper passes, every later run is 5–6 times cheaper (design §1).

## 5. The results' lines

The run printed these lines in pt-BR, Windows' display language. Below is `retune`'s English re-print, with the same numbers. Before them, the run's job line read "P1: converged at 9.81 ns (residual -62.5 dB)", and its results line read "Jobs that kept S: 1 of 1, in 25 min".

```
Results of the run in <RUN>\data\kicad-rf-studio\runs\proj-20261030-061310-c285 at preset normal: 1 jobs converged, 0 flat, 0 at T_max.
Passivity: σ_max 0.9127 at worst, at 1840.0 MHz (|a| -19.6 dB); flagged above 1.02.
Reciprocity: |Sij − Sji| 0.00e+00 at worst, at 1840.0 MHz (|a| -19.6 dB); flagged above 0.02.
Relative: these antenna results compare variants of one board under identical settings; they do not predict measured performance.
Resonance (lowest |S11|): 2388.2 MHz, |S11| -5.9 dB, Zin at U1.1 35.8 + j47.9 Ω.
f_lo = 2400.0 MHz: |S11| -5.9 dB, Zin at U1.1 40.7 + j52.6 Ω, mismatch efficiency 74.0 %.
f0 = 2441.8 MHz: |S11| -5.5 dB, Zin at U1.1 71.2 + j71.2 Ω, mismatch efficiency 72.1 %.
f_hi = 2483.5 MHz: |S11| -5.0 dB, Zin at U1.1 134.6 + j73.4 Ω, mismatch efficiency 68.2 %.
-10 dB bandwidth: none, as |S11| stays above -10 dB.
-6 dB bandwidth: none, as |S11| stays above -6 dB.
2400.0 MHz: radiation efficiency 81.0 %, total efficiency 60.0 %, directivity 2.53 dBi, gain 1.62 dBi, realized gain 0.31 dBi.
2409.3 MHz: radiation efficiency 81.0 %, total efficiency 59.8 %, directivity 2.54 dBi, gain 1.63 dBi, realized gain 0.31 dBi.
2418.6 MHz: radiation efficiency 81.0 %, total efficiency 59.5 %, directivity 2.55 dBi, gain 1.64 dBi, realized gain 0.30 dBi.
2427.8 MHz: radiation efficiency 81.0 %, total efficiency 59.1 %, directivity 2.56 dBi, gain 1.64 dBi, realized gain 0.27 dBi.
2437.1 MHz: radiation efficiency 80.9 %, total efficiency 58.6 %, directivity 2.57 dBi, gain 1.65 dBi, realized gain 0.24 dBi.
2441.8 MHz: radiation efficiency 80.9 %, total efficiency 58.3 %, directivity 2.57 dBi, gain 1.65 dBi, realized gain 0.22 dBi.
2446.4 MHz: radiation efficiency 80.8 %, total efficiency 57.9 %, directivity 2.57 dBi, gain 1.65 dBi, realized gain 0.20 dBi.
2455.7 MHz: radiation efficiency 80.7 %, total efficiency 57.2 %, directivity 2.58 dBi, gain 1.65 dBi, realized gain 0.16 dBi.
2464.9 MHz: radiation efficiency 80.5 %, total efficiency 56.5 %, directivity 2.59 dBi, gain 1.65 dBi, realized gain 0.10 dBi.
2474.2 MHz: radiation efficiency 80.4 %, total efficiency 55.6 %, directivity 2.59 dBi, gain 1.64 dBi, realized gain 0.04 dBi.
2483.5 MHz: radiation efficiency 80.2 %, total efficiency 54.7 %, directivity 2.60 dBi, gain 1.64 dBi, realized gain -0.02 dBi.
Wrote antenna_summary.csv, antenna_summary.png, farfield.csv, layout.s1p in <RUN>\proj\results.
Limit: the board alone in free space.
Limit: copper is a perfect conductor, so the radiation efficiency reads high.
Limit: no enclosure, hand, battery or cable.
Limit: the parts' bodies are absent; only their pads are in the board file.
Limit: the parts off the chain are approximated: capacitors close to a short as copper, the rest open or in the grid, and past the measured region only as fine as its coarse mesh.
```

## 6. The checks of Step 3

| check | pre-registered | measured | verdict |
| --- | --- | --- | --- |
| the job kept | converged, flat or t_max | converged at 9.81 ns, residual −62.5 dB | pass |
| no E_ line | none in the run | none; W_FILLS_AS_SAVED was the run's only W_ or E_ code | pass |
| the setup gate | no E_METAL_IN_PML, no E_PORT_SHORT (the join cut) | I_GATES_PASSED_PML: the absorber, the ports' connectivity and the unused primitives passed | pass |
| the air box and the lid | no W_AIR_BOX, no W_LIDS_LEFT_OUT | neither, in `new`'s notes or the run's events | pass |
| `results.far_field` | three files | sphere, elevation and azimuth, `nf2ff-32fa2baf-*.h5` in the job's folder | pass |
| `results/` | Task 11's four files | antenna_summary.csv, antenna_summary.png, farfield.csv, layout.s1p | pass |
| η_rad | ≤ 1.02 at every recorded frequency (no W_ETA_RAD) | 0.802 to 0.810 | pass |
| cost | predicted/measured within [0.67, 1.5] | 1.128 | pass |
| η_rad (soft) | 0.5 to 1.0 | 0.802 to 0.810 | inside |
| D at f0 (soft) | 1.5 to 4.5 dBi | 2.57 dBi | inside |
| resonance and bandwidth (soft) | reported | lowest \|S11\| at 2388.2 MHz, 11.8 MHz below f_lo; no −10 dB bandwidth | reported |
| the transform's time | above 60 s is a ruling | about 7 s (its folder made at 06:38:26, its three files written by 06:38:33; its log is empty) | below |

- **The fixture's match is a finding about the fixture, not a failure.**
  - |S11| stays between −5.9 and −5.0 dB across the band, and the lowest |S11| over the whole pulse is −5.9 dB, at 2388.2 MHz.
  - Zin at the radio pad runs from 40.7 + j52.6 Ω at f_lo to 134.6 + j73.4 Ω at f_hi. That is seen through the 12 mm feed: 1.975 mm of 72 Ω, then 10 mm of 47 Ω.
  - The inverted-F is TI's, but the ground plane is the fixture generator's own, not TI's board.
  - Plan 4's fixture variants decide whether the fixture keeps this ground plane.
- **The far-field transform** took about 7 s for 11 frequencies on the 5° sphere and the two 1° cuts. Plan 1's ponytail stands: the transform rebuilds the whole CSX.

## 7. The pi variant's setup and the 915 MHz cost

| | the pi variant (`ifa2g4_pi`) | the 915 MHz meander (`meander915`) |
| --- | --- | --- |
| band | 2400–2483.5 MHz | 902–928 MHz (pulse 693–1120 MHz, T_max 79 ns, air gap 83.1 mm) |
| chain | series L1 2.7 nH; shunts C2 and C3, 1 pF; all three ports; C1 copper | no parts; no join |
| mesh | 135 × 143 × 71 = 1,370,655 nodes | 216 × 153 × 79 = 2,610,792 nodes |
| split | board 106,502, air 668,623, PML 595,530 (43.4 %) | board 206,228, air 1,424,302, PML 980,262 (37.5 %) |
| dt | 1.2625e-13 s | 1.0220e-13 s |
| worst case, as printed | 4 h 14 min: 4 runs to 30 ns, 4 at once, 4 threads each | 7 h 35 min: 1 run to 79 ns, 4 threads |
| RAM | about 1.1 GB | about 0.5 GB |
| exit codes | `new` 0, `cost` 0 | `new` 0, `cost` 0 |

- **The pi variant's four ports** (P1, L1, C2 and C3) passed `cost`'s setup gate, which blocks on E_PORT_SHORT, E_PORT_OPEN and E_PORT_BOX.
  - Its shunt port C3 stands on RF and GND, which the antenna's join ties, so it relies on the join cut, and the cut holds. The setup gate's PEC roots keep C3's two ends apart, as they keep L1's RF end apart from its RF_A end.
  - C2 stands on RF_A and GND, across L1 from the join, so it does not rely on the cut. Task 12's brief had named both shunts.
  - Its worst case takes SMALL_SPEED at the calibration's 4-job level, 185.3 MC/s, but no run has measured that correction at a pool above 1.
  - With part ports it has no far field: the one-port branch and the what-if retune are plan 3's.
- **The meander** matches the plan's prototype: 2.61 M nodes, 38 % PML, T_max 79 ns, and a worst case near 7 h.
  - At this run's measured ratio, its worst case would be about 6 h 44 min.
  - `cost` warned W_STAIRCASED for RF, whose meander has 45° copper.
  - It warned W_UNUSED_PRIMITIVE nine times: openEMS left out LinPoly slivers of the front (4) and back (5) mask fills, sub-cell pieces of the 10 µm mask, not copper.

## 8. The stated limits

- The five limits the run printed (§5) apply.
- This is one run of one synthetic fixture on one PC (16 CPUs), at the defaults: mesh n 2, the Normal preset, a λ/4 air gap and solid copper.
- Convergence in the mesh, the gap and the preset is P3-C's, and the noise floor is P3-D's. No number here is a validated antenna figure.
- The two cost corrections are gate P3-A's, from wire dipoles in vacuum. This run checks them on a board at a pool of 1, within 13 %. SMALL_SPEED is unmeasured at a pool above 1.
- **The fit2d gate blocks the 2.4 GHz fixture at mesh n 3 and n 4.** These node counts were built in memory and run nowhere.
  - The failing section is RF's 0.6 mm feed section. On the mesh its Z0 is 73.33 Ω at n 3 and 73.76 Ω at n 4, against the 2D reference's 70.42 Ω, which misses the 3 % limit by 4.13 % and 4.76 % (E_FIT2D_FINE).
  - At n 2 the same section passes at 0.99 %. The meander's 0.6 mm section passes at n 2, 3 and 4, within 1.02 %.
  - P3-C's mesh study needs this explained first.

## 9. Next

- **Plan 3, matching and comparison** (design §5.12 item 3):
  - every chain part a port;
  - the one-port branch of the results, the retune and verify;
  - the far field in verify;
  - `compare`.
- **Plan 4, the gates P3-B to P3-E** on the fixtures, planned on §4's re-estimate:
  - E_FIT2D_FINE at mesh n 3 and 4 explained before the mesh study;
  - the meander's first job measured before its other runs are scheduled;
  - PML_WEIGHT and SMALL_SPEED refitted;
  - the fixture's ground plane decided.
