# kicad-rf-studio

kicad-rf-studio imports KiCad boards and simulates their RF parts with openEMS. It is free software, licensed under the GNU General Public License v3.0 or later (see `LICENSE`); its copy of CSXCAD's SmoothMeshLines is under the GNU Lesser General Public License v3.0 or later (see `COPYING.LESSER`).

## Install

kicad-rf-studio runs from a virtual environment of its own, `<venv>` below. pip installs it there with its Python dependencies, Qt among them (about 600 MB on disk); openEMS 0.37 comes apart. Until kicad-rf-studio is on PyPI, `<source>` is the source zip of a release on the project's GitHub page, once the project is published there, or a clone of this repository.

### Windows

In PowerShell, on Windows 10 or 11:

1. Install Python 3.14, 64-bit, for your user: with the Python install manager (`py install 3.14`), which needs no admin rights, or from python.org. The openEMS 0.37 wheels for Windows need Python 3.13 or 3.14.
2. Make the venv at `%LOCALAPPDATA%\kicad-rf-studio\venv` and install kicad-rf-studio into it. `$venv` names it in the commands below; a new PowerShell window needs that first line again.

   ```
   $venv = "$env:LOCALAPPDATA\kicad-rf-studio\venv"
   py -3.14 -m venv $venv
   & "$venv\Scripts\python" -m pip install <source>
   ```

3. Unpack the official Windows package of openEMS 0.37 and give its folder, the one that holds `openEMS.exe` and `python\`, to `setup-openems`. It installs the package's openEMS and CSXCAD wheels into the venv, offline, and records the folder.

   ```
   & "$venv\Scripts\kicad-rf-studio" setup-openems "<openEMS folder>"
   ```

4. Start KiCad once first, so that it makes its version's folder (or name the version with `--kicad 9.0` or `--kicad 10.0`). Install the KiCad button, for KiCad 9.0.7 or later, or 10.x. It writes into each KiCad version's plugins folder and never edits KiCad's settings. Then, in KiCad: Preferences › Plugins › Enable KiCad API, then restart KiCad.

   ```
   & "$venv\Scripts\kicad-rf-studio" install-kicad-plugin
   ```

5. Start the GUI with `& "$venv\Scripts\kicad-rf-studio-gui"`, or from KiCad's PCB editor: select the chain's two end pads, the antenna footprint (or one of its pads) and the radio pin, or a track, arc or via of a signal-integrity line, and press the kicad-rf-studio button. After updating kicad-rf-studio, run `install-kicad-plugin` again: the button's tooltip, which says what it takes, is written there.

### Linux

On Debian 12, Ubuntu 24.04 or Fedora (glibc 2.34 or newer), with the system Python (3.11 or newer):

1. Clone upstream's openEMS-Project at v0.37.0, with its submodules, and install its build dependencies. This is the one step that needs admin rights: the script asks, then installs your distribution's packages with sudo, `python3-venv` among them on Debian and Ubuntu.

   ```
   git clone --recursive --branch v0.37.0 https://github.com/thliebig/openEMS-Project.git
   cd openEMS-Project
   ./scripts/install_deps.sh --install --python
   ```

2. Make the venv at `~/.local/share/kicad-rf-studio/venv`, activate it and install kicad-rf-studio into it:

   ```
   python3 -m venv ~/.local/share/kicad-rf-studio/venv
   source ~/.local/share/kicad-rf-studio/venv/bin/activate
   pip install <source>
   ```

3. With the venv active, build openEMS in the openEMS-Project folder, without sudo, so that its Python bindings land in the venv: `./update_openEMS.sh ~/.local/share/kicad-rf-studio/openEMS --python`. Leave the GUI build on (no `--disable-GUI`): it builds AppCSXCAD.
4. Start KiCad once first, so that it makes its version's folder (or name the version with `--kicad 9.0` or `--kicad 10.0`). With the venv active, install the KiCad button: `kicad-rf-studio install-kicad-plugin`. Then, in KiCad: Preferences › Plugins › Enable KiCad API, then restart KiCad. A Flatpak KiCad cannot start the button: open the board in the GUI instead.
5. Start the GUI with `kicad-rf-studio-gui`. On a desktop, Qt needs the xcb cursor library: `libxcb-cursor0` on Debian and Ubuntu, `xcb-util-cursor` on Fedora.

### After installing

- **Moved the venv?** Its `kicad-rf-studio` programs and the button's launcher still name its old place. Reinstall kicad-rf-studio, then run `install-kicad-plugin` again, both through the Python of the venv where it now is: `& "<venv>\Scripts\python" -m pip install --force-reinstall --no-deps <source>`, then `& "<venv>\Scripts\python" -m kicad_rf_studio install-kicad-plugin` (Linux: `<venv>/bin/python` in both). Until then the button fails: KiCad 10 shows the shell's error, KiCad 9 nothing.
- **Remove the button:** `& "$venv\Scripts\kicad-rf-studio" install-kicad-plugin --remove` (Linux, with the venv active: `kicad-rf-studio install-kicad-plugin --remove`) deletes its folder from each KiCad version's plugins folder, and nothing else. Once the venv is gone, delete the `kicad-rf-studio` folder by hand from each `Documents\KiCad\<version>\plugins` (Windows) or `~/.local/share/kicad/<version>/plugins` (Linux).
- **Uninstall:** remove the button, then delete the venv; on Linux, also the openEMS folder `~/.local/share/kicad-rf-studio/openEMS` and the openEMS-Project clone. The folder that holds the venv, `%LOCALAPPDATA%\kicad-rf-studio` or `~/.local/share/kicad-rf-studio`, also holds the settings and the run folders your projects' results point to: delete it only when no project needs them.
- **English on a Portuguese Windows:** kicad-rf-studio speaks the language that `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` or `LANG` names when one is set, else Brazilian Portuguese when Windows' display language is Portuguese (Brazil), else English. To keep English, run `setx LANGUAGE en` once and restart KiCad; git and other programs that read `LANGUAGE` turn English too. On Linux, put `export LANGUAGE=en` in your profile.

## Tutorial

This takes `lpf915`, the synthetic 915 MHz low-pass filter in `tests/fixtures` (a series DC block and a C-L-C pi of 0402 parts on a 50 Ω GCPW, under a shield), through `new`, `cost`, `run`, `retune` and `verify`. Run the commands from the root of a clone, or of the unpacked source zip, with the venv from Install. In PowerShell, `<venv>\Scripts\kicad-rf-studio` is `& "$venv\Scripts\kicad-rf-studio"`; on Linux, with the venv active, type `kicad-rf-studio` alone.

The times were measured on the development PC (Windows 11, 16 CPUs, 4 jobs at once) at the Normal preset, `new`'s default: by P0-B (`docs/validation/2026-10-25-p0-b.md`), unless marked as measured while this tutorial was written. P0-B's run B6 is this project: lpf915 at the protected reach of 6 substrate heights that `new` now writes. The excerpts are real output, from P0-B's runs or from runs made while this tutorial was written; `<run folder>` stands for the run's folder in the per-user data folder, and `lpf915` for the project's folder.

**`new`** reads the board, traces the chain between the pads U1.1 and J1.1 and writes the project. `--lid-height` is the height of the shield's lid in mm.

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/lpf915.kicad_pcb --start U1.1 --end J1.1 --f0 915MHz --lid-height 2.5 -o lpf915
```

It prints the stackup, the chain, each part and port, and every default it wrote:

```
Chain U1.1 → J1.1: series C1, L1, R1; shunt C2, C3, R2.
Port P1: signal U1.1, reference U1.2 (ic).
Port P2: signal J1.1, reference J1.2 (connector).
Preset normal (provisional default), band factor 1.1, T_max 40 ns, harmonics 3, mesh n 2, region 3 substrate heights past the chain, margin scale 1, protected reach 6 substrate heights.
Wrote lpf915\project.json.
```

**`cost`** prints the 2D Z0 and εeff of the chain's straight sections, then runs openEMS's setup-only gate and prints what a run will cost. On a machine with no calibration yet, it first measures the machine's speed, once. Measured while this tutorial was written, it took 40 s.

```
<venv>\Scripts\kicad-rf-studio cost lpf915
```

```
RF_B on F.Cu: width 0.600 mm, gap 0.150, length 2.035 mm — Z0 49.89 Ω, εeff 2.655 without mask; Z0 47.04 Ω, εeff 2.985 with mask
Cells: 332 × 195 × 69 = 4.47 M (mesh n 2, cell d 0.0751 mm).
Worst case: 13 h 16 min for 6 runs to T_max 40 ns, 4 at once with 4 threads each.
RAM: about 3.2 GB (4 jobs at once).
Main cost: 6 runs, one per port, 4 of them part ports.
```

Plan 6's mesh rule (spec §5.4, A-8) moved lpf915's lines after P0-B; the run times below are P0-B's.

That worst case comes from today's calibration, which each run refreshes. P0-B's B6 recorded a worst case of 46937 s (13.0 h) and, from its run's stop times, a prediction of 35801 s (9.9 h); after a `run`, `cost` prints that prediction too.

**`run`** runs the gates, then one job per port (P1 and P2, and the part ports C1, L1, C2 and C3) under the stop rule. When every job keeps S, it records the results in `project.json` and writes `layout.s6p`, `chain.s2p`, `summary.csv` and `summary.png` to `lpf915\results`. B6's six jobs took 19714 s (5.5 h), 0.55 of that prediction, and all six converged:

```
<venv>\Scripts\kicad-rf-studio run lpf915
```

```
Running 6 jobs, 4 at once, in <run folder>. Create a file named STOP there, or press Ctrl+C, to stop.
P1: converged at 13.79 ns (residual -67.2 dB).
P2: converged at 30.47 ns (residual -69.4 dB).
C1: converged at 13.95 ns (residual -66.7 dB).
L1: converged at 18.67 ns (residual -69.2 dB).
C2: converged at 13.83 ns (residual -70.0 dB).
C3: converged at 22.77 ns (residual -67.9 dB).
6 of 6 jobs kept S, in 5 h 28 min; results recorded in lpf915\project.json.
f0 = 915 MHz (|a| -8.1 dB): IL 2.54 dB and RL 3.70 dB with layout; IL 1.96 dB and RL 4.52 dB ideal schematic.
```

**`retune`** stores new part values and writes `lpf915\results` again from the last run's waves, with no new run. Measured while this tutorial was written, it took 2.3 to 2.4 s in four runs on a copy of B6:

```
<venv>\Scripts\kicad-rf-studio retune lpf915 C2=4.7pF
```

```
f0 = 915 MHz (|a| -8.1 dB): IL 3.91 dB and RL 2.40 dB with layout; IL 3.05 dB and RL 3.09 dB ideal schematic.
Relative / what-if: the instant retune is not yet validated against a full simulation of a real board (spec 7.6), so read these chain results as relative. Check the final values with `kicad-rf-studio verify lpf915\project.json`.
```

The retune stays labelled relative / what-if until P0-C passes: `run` and `retune` print that line, and `chain.s2p` and `summary.png` carry it. P0-B failed, so P0-C is recorded "do not start" and the label stays on.

**`verify`** runs once more with each part in the grid at its ideal value, only P1 and P2 as jobs, and compares that with a retune at the same values. It was not timed at reach 6. P0-B's B2, `verify` on lpf915 at the reach then in force (3 substrate heights), took 7077 s (2.0 h). Its P1 job converged and its P2 job reached T_max:

```
<venv>\Scripts\kicad-rf-studio verify lpf915
```

```
P1: converged at 30.18 ns (residual -71.4 dB).
P2: not converged where its S ends, at 39.99 ns with a residual of -69.7 dB: at T_max, or, for a signal-integrity job whose residual still fell fast enough there, past it, where that fall slowed or the ring rule's ceiling came. S is kept and flagged; raise t_max_s in project.json for a converged result.
```

P0-B's consistency criterion, `verify` against the co-simulation, failed (|ΔS21| at f0 0.1019 dB against 0.1 dB, max |ΔS| 0.0926 against 0.03), and P0-B was decided fail at the ceiling. Read P0-B's report before you take `verify`'s comparison as agreement.

## Antenna tutorial

This takes `ifa2g4_pi`, the synthetic 2.4 GHz board in `tests/fixtures` (KiCad's `Texas_SWRA117D_2.4GHz_Left` inverted-F, after TI's application note SWRA117D, fed from the radio's pad U1.1 through a pi network of 0402 parts: series L1, shunts C2 and C3), through `new --antenna`, `cost`, `run`, `retune` and `verify`, then compares it with `ifa2g4_pi_pour`, the same board with a ground pour inside the antenna's clearance. Run the commands as in the Tutorial above.

The times were measured on the development PC (Windows 11, 16 CPUs) at the Normal preset, `new`'s default, by the run through the GUI that closed Stage 3 (`docs/validation/2026-11-02-stage3-exit.md`); that run compared with the pour that gate P3-E had verified, so the pour's run and verify times are P3-E's (`docs/validation/2026-11-01-p3-e.md`). `cost` prints your own machine's estimate before every run, and no runtime is promised. The excerpts are real output of that run; `ifa2g4_pi`, `ifa2g4_pi_pour` and `compare` stand for the projects' and the compare's folders.

**`new --antenna`** finds the antenna footprint AE1 and its feed pad, traces the chain from the radio's pin U1.1 to it, and writes an antenna project for the band: `--antenna` takes the place of `--end` and `--band F_LO:F_HI` that of `--f0`. The whole board is simulated, in an air box with a PML absorber, and every part on the chain is a part port, so the network can be retuned.

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/ifa2g4_pi.kicad_pcb --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o ifa2g4_pi
```

It took under a second. It prints the stackup, the nets, the antenna and its join, the chain, each part and port, the band and every default it wrote:

```
Antenna AE1, fed at pad AE1.1 on net RF: its copper drawn without a net takes that net.
Antenna AE1 joins its feed to ground through AE1.2 by design, as an inverted-F does; the connectivity and port checks accept that join and no other.
Chain U1.1 → AE1.1: series L1; shunt C2, C3.
Port P1: signal U1.1, reference U1.2 (ic).
Band 2400 to 2483.5 MHz, f0 2441.75 MHz; the pulse spans 1840 to 2990 MHz.
Preset normal, T_max 30 ns (2·t0 + 60/f0), mesh n 2, measured region 6 substrate heights past the antenna and the chain, protected reach 6 substrate heights, air gap 31.2 mm (λ/4 at f_lo) to a pml_8 absorber, far-field frequencies: 11, on a 5° sphere.
Wrote ifa2g4_pi\project.json.
```

**`cost`** splits the cells into board, air and PML, and prints the worst case before any run.

```
<venv>\Scripts\kicad-rf-studio cost ifa2g4_pi
```

It took 37 s, 26 s of it measuring the machine's speed, which `cost` does once on a machine with no calibration yet:

```
Cells: 135 × 143 × 71 = 1.37 M (mesh n 2, cell d 0.3000 mm).
Cells: 0.11 M in the board, 0.67 M of air and 0.60 M of PML; the time counts a PML cell as 8.92 cells and runs this model at 0.559 × the calibrated speed for that many jobs at once (gate P3-A's method, refitted by gates P3-B to P3-E).
dt 1.2625e-13 s (floor 0.8 × 1.1118e-13 s), set by the z edge at (98.642, 93.865, 0.000) mm.
Worst case: 3 h 48 min for 4 runs to T_max 30 ns, 2 at once with 8 threads each.
RAM: about 0.6 GB (2 jobs at once).
```

**`run`** runs one job per port, P1 at the radio's pin and the part ports L1, C2 and C3, as many at once as the machine's calibration chose (two here). It gives S11 at the radio's pin for any part values, and no far field: a part port is not a part.

```
<venv>\Scripts\kicad-rf-studio run ifa2g4_pi
```

It took 3833 s (1.1 h), 0.28 of that worst case, and all four jobs converged. These results are at the board's own values, L1 2.7nH and C2 and C3 1pF:

```
P1: converged at 11.12 ns (residual -60.2 dB).
L1: converged at 11.95 ns (residual -60.7 dB).
C2: converged at 11.12 ns (residual -60.4 dB).
C3: converged at 12.58 ns (residual -60.6 dB).
4 of 4 jobs kept S, in 1 h 3 min; results recorded in ifa2g4_pi\project.json.
Resonance (lowest |S11|): 2325.8 MHz, |S11| -6.9 dB, Zin at U1.1 43.2 - j46.7 Ω.
f_lo = 2400.0 MHz: |S11| -5.6 dB, Zin at U1.1 17.5 - j16.0 Ω, mismatch efficiency 72.6 %.
f0 = 2441.8 MHz: |S11| -4.7 dB, Zin at U1.1 13.3 - j4.2 Ω, mismatch efficiency 66.2 %.
f_hi = 2483.5 MHz: |S11| -4.0 dB, Zin at U1.1 11.5 + j5.9 Ω, mismatch efficiency 60.2 %.
-10 dB bandwidth: none, as |S11| stays above -10 dB.
-6 dB bandwidth: 2274.2 to 2384.3 MHz (110.1 MHz).
No far field for this run: a run with part ports records none, as its jobs hold ports where the matching parts sit; `kicad-rf-studio verify ifa2g4_pi\project.json` runs one job with each part in the grid at its value, as an ideal part, and records it.
```

**`retune`** closes the part ports at new values, with no new run. These came from an E24 search over the run's layout, the values the GUI's snapping gives (C2 typed as 0.127pF snaps to 0.13pF). `0R` replaces a series part with a short and `open` removes a shunt part: `retune ifa2g4_pi L1=0R C2=open C3=open` shows the antenna through its feed line.

```
<venv>\Scripts\kicad-rf-studio retune ifa2g4_pi L1=0R C2=0.13pF C3=1pF
```

It took 2 s:

```
Resonance (lowest |S11|): 2443.4 MHz, |S11| -17.4 dB, Zin at U1.1 60.6 - j10.5 Ω.
f_lo = 2400.0 MHz: |S11| -10.3 dB, Zin at U1.1 65.8 + j33.1 Ω, mismatch efficiency 90.7 %.
f0 = 2441.8 MHz: |S11| -17.4 dB, Zin at U1.1 62.1 - j9.2 Ω, mismatch efficiency 98.2 %.
f_hi = 2483.5 MHz: |S11| -10.5 dB, Zin at U1.1 32.1 - j17.6 Ω, mismatch efficiency 91.1 %.
-10 dB bandwidth: 2397.7 to 2486.6 MHz (89.0 MHz).
-6 dB bandwidth: 2356.6 to 2521.5 MHz (164.9 MHz).
Relative / what-if: the instant retune is not yet validated against a full simulation of a real board (spec 7.6), so read these chain results as relative. Check the final values with `kicad-rf-studio verify ifa2g4_pi\project.json`.
```

**`verify`** runs one job with every part in the grid at its applied value, as an ideal part, and records the far field: the radiation and total efficiency, the directivity, gain and realized gain, and the three cuts at f0 in `verify_summary.png`. After it, `retune` also prints the what-if total efficiency of each new set of values.

```
<venv>\Scripts\kicad-rf-studio verify ifa2g4_pi
```

It took 1161 s (19 min). It prints a far-field line for each of the eleven far-field frequencies; this excerpt keeps f0's:

```
1 verify jobs kept S, in 19 min; the comparison is stored in ifa2g4_pi\project.json.
Resonance (lowest |S11|): 2446.6 MHz, |S11| -12.5 dB, Zin at U1.1 74.7 - j16.5 Ω.
f_lo = 2400.0 MHz: |S11| -9.3 dB, Zin at U1.1 71.6 + j37.8 Ω, mismatch efficiency 88.3 %.
f0 = 2441.8 MHz: |S11| -12.5 dB, Zin at U1.1 78.3 - j11.6 Ω, mismatch efficiency 94.4 %.
f_hi = 2483.5 MHz: |S11| -10.1 dB, Zin at U1.1 43.0 - j29.7 Ω, mismatch efficiency 90.2 %.
verify against the retune at the same ideal values: |ΔS11| 0.0076 at f0 = 2441.75 MHz (|a| -0.1 dB) and 0.0149 at most up to f2.
Resonance at 2446.6 MHz in verify against 2446.8 MHz in the retune: a shift of -0.01 %.
2441.8 MHz: radiation efficiency 81.3 %, total efficiency 76.7 %, directivity 2.55 dBi, gain 1.65 dBi, realized gain 1.40 dBi.
verify checks the layout reduction, not the vendor part data: each part sat in the grid at its value as an ideal part, without the package ESL, ESR and Cp or the S2P data the retune applies, a 0 Ω part as copper and an open part left out, against a retune at the same ideal values; its far field holds that ideal network.
```

**`compare`** reads both projects' verified results, which must share every setting, and marks each difference resolved or not. First the same steps on the pour board, then the compare, which writes `compare.csv` and `compare.png` into `compare`:

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/ifa2g4_pi_pour.kicad_pcb --start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz -o ifa2g4_pi_pour
<venv>\Scripts\kicad-rf-studio run ifa2g4_pi_pour
<venv>\Scripts\kicad-rf-studio retune ifa2g4_pi_pour L1=0R C2=0.13pF C3=1pF
<venv>\Scripts\kicad-rf-studio verify ifa2g4_pi_pour
<venv>\Scripts\kicad-rf-studio compare ifa2g4_pi ifa2g4_pi_pour -o compare
```

On the pour, `new` and `retune` take seconds, and `run` and `verify` took 1 h 4 min and 27 min in gate P3-E (`docs/validation/2026-11-01-p3-e.md`). The compare took 1 s:

```
Resonance: 2446.6 MHz to 2358.2 MHz, a shift of -88.5 MHz (-3.62 % of f0): resolved.
-10 dB bandwidth: not compared, as one of the two has none bounded inside the simulated band.
Total efficiency at f_lo = 2400.0 MHz: 71.8 % to 56.1 %, -1.07 dB: resolved.
Total efficiency at f0 = 2441.8 MHz: 76.7 % to 48.4 %, -2.00 dB: resolved.
Total efficiency at f_hi = 2483.5 MHz: 73.0 % to 39.0 %, -2.73 dB: resolved.
Peak gain at f0 = 2441.8 MHz: 1.65 dBi to 1.21 dBi, -0.44 dB: resolved.
Resolved means larger than the significance threshold: 0.3 % of f0 for a frequency and 0.2 dB for an efficiency or a gain, set by gate P3-D at three times the model's measured noise floor and never below 0.3 % and 0.2 dB.
Wrote compare.csv, compare.png in compare.
```

In the GUI, New's kind Antenna takes the antenna footprint, the start pad and a band preset; Results shows S11 with the band shaded, the Smith chart and, from the run that holds the network, the efficiencies and the three cuts, its title naming that run; the Compare tab compares the open project with a variant. The KiCad button pre-fills New with the antenna kind when the antenna footprint, or one of its pads, is selected with the radio's pin.

### What these results do not tell you

- Every antenna result carries this line: "Relative: these antenna results compare variants of one board under identical settings; they do not predict measured performance."
- The board is alone in free space: no enclosure, hand, battery or cable. TI's AN043 measured a 5–10 MHz shift from a cable's position alone.
- Copper is a perfect conductor, so the radiation efficiency reads high; the parts' bodies are absent, and the parts off the chain are approximated.
- A difference is resolved only above 0.3 % of f0 for a frequency and 0.2 dB for an efficiency or a gain, at least three times the model's measured noise floor (gate P3-D, `docs/validation/2026-11-01-p3-d.md`). This antenna's resonance moves about 1.9 % per mm of its position near the ground's corner, which compare resolves.
- The retune stays what-if until P0-C: `verify` checks the layout reduction with ideal parts, not the vendor parts, and here its ideal network reads −12.5 dB at f0 where the retune's 0402 presets read −17.4 dB.
- Chip antennas and modules are refused, the matching chain up to their pad still runs as in the Tutorial, and sheet copper is not offered.
- A radio pin, feed and antenna pad in one line can be refused by the fit2d gate; raising `gates.fit2d_limit` in project.json is at your own risk.
- `meander915` is no 915 MHz example: on its synthetic board it resonates above its band.

## Signal-integrity tutorial

This takes `usb2_hs`, the synthetic four-layer USB 2.0 high-speed board in `tests/fixtures`: a micro-B connector J1, the pads of a six-pin ESD array U2 on the pair, a 22 Ω 0402 series resistor on each leg (R1 and R2) and an MCU-like QFN U1 at the far end, with a neighbour net, AUX, running beside part of the route between the test points TP1 and TP2. It goes through `new --interface`, `cost`, `run`, `retune` and `verify`, then compares it with `usb2_hs_gap`, the same board with a slot in the plane under the pair. Run the commands as in the Tutorial above.

The times were measured on the development PC (Windows 11, 16 CPUs) at the Normal preset, `new`'s default, by the run through the GUI that closed Stage 4 (`docs/validation/2026-11-09-stage4-exit.md`). That run compared with the plane-gap board that gate P4-F had run (`docs/validation/2026-11-08-p4-f.md`), retuned and verified for it, so the gap's run time is P4-F's and its verify time that preparation's. `cost` prints your own machine's estimate before every run, and no runtime is promised. The excerpts are real output of that run; `<run folder>` stands for a run's folder in the per-user data folder, and `usb2_hs`, `usb2_hs_gap` and `compare` for the projects' and the compare's folders.

**`new --interface`** traces the measured line from the connector's pin J1.3 through R1 to the MCU's pin U1.3, takes its partner by KiCad's pair rule (`--pair`: USB_D+ with USB_D-, ending at J1.2 and U1.2) and AUX between TP1.1 and TP2.1 as a victim, and writes a signal-integrity project for the `usb2-hs` interface: 90 Ω differential ± 10 %, the link's 500 ps edge and a 240 MHz marker, simulated to 10 GHz. R1 and R2 are part ports, so their values can be retuned.

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/usb2_hs.kicad_pcb --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o usb2_hs
```

It took 10 s. It prints the stackup, the nets, the interface, the pair, both chains, the victim, each port and every default it wrote:

```
Stackup: board, dielectric 1.44 mm, εr 4.3; mask 0.01 mm, εr 3.3.
GND nets: GND. Power nets: +3V3, VBUS. Connectors: J1. Shields: none.
Interface usb2-hs: target 90 Ω differential ± 10 %, the link's rise time 500 ps, marker 240 MHz, simulated to 10 GHz, where the localising TDR's rise time is 125 ps.
Pair: USB_D+ with USB_D-, by KiCad's pair rule.
Chain J1.3 → U1.3: series R1; shunt none.
Chain J1.2 → U1.2: series R2; shunt none.
Victim TP1.1 → TP2.1 on net AUX: its two ends are ports, so the waves coupled into it end in 50 Ω.
Port P1: signal J1.3, vertical to the plane on In1.Cu.
Port P2: signal J1.2, vertical to the plane on In1.Cu.
Port P3: signal U1.3, reference U1.17 (ic).
Port P4: signal U1.2, reference U1.17 (ic).
Port P5: signal TP1.1, vertical to the plane on In1.Cu.
Port P6: signal TP2.1, vertical to the plane on In1.Cu.
Preset normal (provisional default), T_max 9 ns, stop window 2 ns, mesh n 2 with the cell d throughout the protected extent (gate P4-C), dielectric lossless, timestep floor 0.6, region and protected reach 6 substrate heights (1.2 mm).
Wrote usb2_hs\project.json.
```

**`cost`** first lists the 2D table, every straight section's impedance against the target band, in seconds and before any run; then the cells, the runs broken down into the lines' ends, the victim's and the part ports, the worst case, and the time a job whose planes ring may take past T_max.

```
<venv>\Scripts\kicad-rf-studio cost usb2_hs
```

It took 72 s, including the measurement of the machine's speed that `cost` makes once on a machine with no calibration yet:

```
2D table against the target 90 Ω ± 10 % (a pair's Zdiff, a net's Z0), mask included; bends, vias, pads and parts not included: a screening before the run, not its result.
USB_D+ on F.Cu, coupled: width 0.300 mm, gap 0.253 mm, length 2.038 mm — Zdiff 90.87 Ω (Zodd 45.44 Ω, Zeven 59.18 Ω), εeff odd 3.054, even 3.493, delay 11.9 ps: in the target band.
USB_D+ on F.Cu: width 0.300 mm, length 0.675 mm, its partner not alongside — Z0 52.51 Ω, so Zdiff 105.01 Ω uncoupled, εeff 3.312, delay 4.1 ps: outside the target band.
USB_D+ on F.Cu, coupled: width 0.600 mm, gap 1.300 mm, length 5.000 mm — Zdiff 70.25 Ω (Zodd 35.12 Ω, Zeven 35.73 Ω), εeff odd 3.419, even 3.496, delay 30.8 ps: outside the target band.
USB_D+ on F.Cu: width 0.300 mm, length 0.675 mm, its partner not alongside — Z0 52.59 Ω, so Zdiff 105.18 Ω uncoupled, εeff 3.311, delay 4.1 ps: outside the target band.
USB_D+ on F.Cu, coupled: width 0.300 mm, gap 0.250 mm, length 17.490 mm — Zdiff 90.21 Ω (Zodd 45.10 Ω, Zeven 58.90 Ω), εeff odd 3.061, even 3.493, delay 102.1 ps: in the target band.
MCU_D+ on F.Cu, coupled: width 0.300 mm, gap 0.250 mm, length 4.527 mm — Zdiff 90.34 Ω (Zodd 45.17 Ω, Zeven 59.03 Ω), εeff odd 3.061, even 3.500, delay 26.4 ps: in the target band.
USB_D- on F.Cu, coupled: width 0.300 mm, gap 0.251 mm, length 2.038 mm — Zdiff 90.32 Ω (Zodd 45.16 Ω, Zeven 58.96 Ω), εeff odd 3.063, even 3.501, delay 11.9 ps: in the target band.
USB_D- on F.Cu: width 0.300 mm, length 0.675 mm, its partner not alongside — Z0 52.51 Ω, so Zdiff 105.01 Ω uncoupled, εeff 3.312, delay 4.1 ps: outside the target band.
USB_D- on F.Cu, coupled: width 0.600 mm, gap 1.300 mm, length 5.000 mm — Zdiff 70.25 Ω (Zodd 35.12 Ω, Zeven 35.73 Ω), εeff odd 3.419, even 3.496, delay 30.8 ps: outside the target band.
USB_D- on F.Cu: width 0.300 mm, length 0.675 mm, its partner not alongside — Z0 52.59 Ω, so Zdiff 105.18 Ω uncoupled, εeff 3.311, delay 4.1 ps: outside the target band.
USB_D- on F.Cu, coupled: width 0.300 mm, gap 0.250 mm, length 17.490 mm — Zdiff 90.21 Ω (Zodd 45.10 Ω, Zeven 58.90 Ω), εeff odd 3.061, even 3.493, delay 102.1 ps: in the target band.
MCU_D- on F.Cu, coupled: width 0.300 mm, gap 0.250 mm, length 4.527 mm — Zdiff 90.24 Ω (Zodd 45.12 Ω, Zeven 58.99 Ω), εeff odd 3.063, even 3.502, delay 26.4 ps: in the target band.
AUX on F.Cu: width 0.200 mm, gap 0.625, length 12.000 mm — Z0 62.94 Ω, εeff 3.240, delay 72.0 ps: a victim, no target.
Cells: 402 × 121 × 77 = 3.75 M (mesh n 2, cell d 0.1000 mm).
dt 8.0779e-14 s (floor 0.6 × 7.4439e-14 s), set by the z edge at (96.588, 100.925, 1.580) mm.
Worst case: 1 h 51 min for 8 runs to T_max 9 ns, 4 at once with 4 threads each.
Runs: 4 for the measured lines' ends, 2 for the victims' ends, 2 for the part ports.
A job whose port residual still falls by 0.3 dB/ns or more at T_max, fast enough over its last 3 ns to reach the preset's level by 36 ns, runs on while it keeps doing so, until it converges: up to 7 h 24 min.
RAM: about 2.7 GB (4 jobs at once).
Main cost: 8 runs, one per port, 2 of them part ports.
```

**`run`** runs one job per port: the pair's four ends, the victim's two and the part ports R1 and R2. It gives the TDR along the route against the target band, the mixed-mode S (Sdd21, Sdd11, Scc21 and Scd21), the skew and the crosstalk into AUX, for any values of R1 and R2.

```
<venv>\Scripts\kicad-rf-studio run usb2_hs
```

It took 2351 s (39 min), 0.35 of that worst case, and all eight jobs converged. These results are at the board's own values, 22 Ω on R1 and R2:

```
P1: converged at 3.06 ns (residual -60.9 dB).
P2: converged at 3.06 ns (residual -60.7 dB).
P3: converged at 3.04 ns (residual -62.5 dB).
P4: converged at 3.04 ns (residual -62.4 dB).
P5: converged at 2.74 ns (residual -60.4 dB).
P6: converged at 2.76 ns (residual -62.1 dB).
R1: converged at 2.99 ns (residual -61.4 dB).
R2: converged at 2.99 ns (residual -61.2 dB).
8 of 8 jobs kept S, in 38 min; results recorded in usb2_hs\project.json.
Results of the run in <run folder> at preset normal: 8 jobs converged, 0 flat, 0 at T_max.
Passivity: σ_max 1.0083 at worst, at 10000.0 MHz (|a| -19.6 dB); flagged above 1.02.
Reciprocity: |Sij − Sji| 1.53e-02 at worst, at 10000.0 MHz (|a| -19.6 dB); flagged above 0.02.
Relative: these signal-integrity results compare variants of one board under identical settings; they do not predict measured performance.
Sdd21 -1.912 dB at the marker (240 MHz) and -2.900 dB at f_max (10 GHz).
The worst Sdd11 up to f_max: -7.43 dB at 4815 MHz.
The worst Scd21 up to f_max: -45.56 dB at 10000 MHz.
Scc21, the common mode's transmission: -1.90 dB at the marker (240 MHz).
The differential TDR: the localising rise time 125 ps resolves 10.3 mm and the link's 500 ps 41.4 mm, at the route's 2D εeff 3.28; the first resolution length at each port is the port's own launch.
The lowest TDR level between the launches, 84.97 Ω at 131.2 ps (10.9 mm), lies on a feature shorter than two resolution lengths (20.7 mm), so it is not that feature's impedance.
The highest TDR level between the launches, 96.10 Ω at 256.2 ps (21.2 mm), lies on a feature shorter than two resolution lengths (20.7 mm), so it is not that feature's impedance.
Intra-pair skew -0.01 ps: the N leg's TDT arrives at 199.9 ps and the P leg's at 199.9 ps, each at half its peak.
Crosstalk into AUX from the pair driven differentially at its start: NEXT at TP1.1 peaks at -25.72 dB (9170 MHz) and FEXT at TP2.1 at -28.92 dB (9360 MHz).
Not in S: the copper's loss over the route's 30.4 mm, by Hammerstad's formula for smooth copper, about 0.050 dB at the marker (240 MHz) and 0.321 dB at f_max (10 GHz).
Not in S either, the dielectric being lossless: its loss over the same length, about 0.022 dB at the marker and 0.907 dB at f_max.
```

**`retune`** closes the part ports at new values, with no new run: 24 Ω, the value the GUI's E24 snapping gives a typed 25 Ω. `0R` replaces a series part with a short.

```
<venv>\Scripts\kicad-rf-studio retune usb2_hs R1=24 R2=24
```

It took 7 s:

```
Relative: these signal-integrity results compare variants of one board under identical settings; they do not predict measured performance.
Sdd21 -2.067 dB at the marker (240 MHz) and -3.092 dB at f_max (10 GHz).
The worst Sdd11 up to f_max: -7.20 dB at 4805 MHz.
The worst Scd21 up to f_max: -45.70 dB at 10000 MHz.
Scc21, the common mode's transmission: -2.06 dB at the marker (240 MHz).
The differential TDR: the localising rise time 125 ps resolves 10.3 mm and the link's 500 ps 41.4 mm, at the route's 2D εeff 3.28; the first resolution length at each port is the port's own launch.
The lowest TDR level between the launches, 84.97 Ω at 131.2 ps (10.9 mm), lies on a feature shorter than two resolution lengths (20.7 mm), so it is not that feature's impedance.
The highest TDR level between the launches, 96.38 Ω at 256.2 ps (21.2 mm), lies on a feature shorter than two resolution lengths (20.7 mm), so it is not that feature's impedance.
Intra-pair skew -0.01 ps: the N leg's TDT arrives at 199.8 ps and the P leg's at 199.9 ps, each at half its peak.
Crosstalk into AUX from the pair driven differentially at its start: NEXT at TP1.1 peaks at -25.67 dB (9160 MHz) and FEXT at TP2.1 at -28.80 dB (9340 MHz).
Not in S: the copper's loss over the route's 30.4 mm, by Hammerstad's formula for smooth copper, about 0.050 dB at the marker (240 MHz) and 0.321 dB at f_max (10 GHz).
Not in S either, the dielectric being lossless: its loss over the same length, about 0.022 dB at the marker and 0.907 dB at f_max.
Relative / what-if: the instant retune is not yet validated against a full simulation of a real board (spec 7.6), so read these chain results as relative. Check the final values with `kicad-rf-studio verify usb2_hs\project.json`.
```

**`verify`** runs one job per external port with R1 and R2 in the grid at their values, as ideal parts, and compares the result with the retune's.

```
<venv>\Scripts\kicad-rf-studio verify usb2_hs
```

It took 1815 s (30 min), and all six jobs converged. This excerpt keeps the comparison with the retune:

```
6 verify jobs kept S, in 29 min; the comparison is stored in usb2_hs\project.json.
verify against the retune at the same ideal values: max |ΔS| 0.0292 from the first point above DC to f_max, at 9920 MHz (|a| -19.2 dB).
The lowest TDR level between the launches, verify against the retune: 84.97 Ω against 84.97 Ω; one of them lies on a feature shorter than two resolution lengths, so it is not that feature's impedance.
The highest TDR level between the launches, verify against the retune: 92.67 Ω against 93.06 Ω; one of them lies on a feature shorter than two resolution lengths, so it is not that feature's impedance.
verify checks the layout reduction, not the vendor part data: each part sat in the grid at its value as an ideal part, without the package ESL, ESR and Cp or the S2P data the retune applies, a 0 Ω part as copper and an open part left out, against a retune at the same ideal values, whose loads hold at DC their value at the grid's first point above DC.
```

**`compare`** reads both projects' verified results, which must share every setting, and marks each difference resolved or not. First the same steps on the plane-gap board, then the compare, which writes `compare.csv` and `compare.png` into `compare`:

```
<venv>\Scripts\kicad-rf-studio new tests/fixtures/usb2_hs_gap.kicad_pcb --start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1 -o usb2_hs_gap
<venv>\Scripts\kicad-rf-studio run usb2_hs_gap
<venv>\Scripts\kicad-rf-studio retune usb2_hs_gap R1=24 R2=24
<venv>\Scripts\kicad-rf-studio verify usb2_hs_gap
<venv>\Scripts\kicad-rf-studio compare usb2_hs usb2_hs_gap -o compare
```

On the plane-gap board, `new` and `retune` take seconds, `run` took 4 h 25 min in gate P4-F (`docs/validation/2026-11-08-p4-f.md`), and `verify` 3 h 35 min in the preparation for the run through the GUI. The compare took 9 s:

```
The lowest TDR level between the launches: 84.97 Ω against 85.31 Ω, +0.34 Ω: not resolved; one of them lies on a feature shorter than two resolution lengths, so it is not that feature's impedance, and the delta compares two levels filtered alike.
The highest TDR level between the launches: 92.67 Ω against 94.89 Ω, +2.22 Ω: resolved; one of them lies on a feature shorter than two resolution lengths, so it is not that feature's impedance, and the delta compares two levels filtered alike.
Sdd21 at 240 MHz: -2.068 dB against -2.067 dB, +0.001 dB: not resolved.
Sdd21 at 10000 MHz: -2.829 dB against -3.051 dB, -0.222 dB: resolved.
The worst Sdd11 up to f_max: -6.97 dB against -7.23 dB, -0.26 dB: not resolved.
The worst Scd21 up to f_max: -47.18 dB against -28.19 dB, +19.00 dB: resolved.
The intra-pair skew: -0.00 ps against +0.40 ps, +0.40 ps: not resolved.
NEXT into AUX, its peak: -25.87 dB against -20.98 dB, +4.89 dB: resolved.
FEXT into AUX, its peak: -29.42 dB against -23.58 dB, +5.84 dB: resolved.
Resolved means larger than the significance threshold: 2.2 Ω on a TDR level, 0.05 dB on Sdd21 or S21, 0.5 dB on Sdd11, S11, NEXT and FEXT where the higher of the two levels stands above -50 dB and on Scd21 where it stands above -37.7 dB, and 1 ps on the skew: the values gate P4-E set from the model's measured noise.
Wrote compare.csv, compare.png in compare.
```

In the GUI, New's kind Signal integrity takes the start and end pads, the interface, the pair (none, KiCad's rule or its two end pads picked) and up to two victims; the Cost tab lists the 2D table before the estimate; Results shows the TDR with the target band, the mixed-mode S and the crosstalk, and retunes R1 and R2 with E24 snapping; the Compare tab compares the open project with a variant. The KiCad button pre-fills New with the signal-integrity kind, the pair and an interface that fits it from a selected track, arc or via, and with the line's two end pads, the connector's first, when it has exactly two IC or connector pads: on `usb2_hs` the ESD array's pads make four, so pick J1.3 and U1.3, or select them in KiCad with a track of the pair.

### What these results do not tell you

- Every signal-integrity result carries this line: "Relative: these signal-integrity results compare variants of one board under identical settings; they do not predict measured performance."
- A TDR level marked short lies on a feature shorter than two resolution lengths, so it is not that feature's impedance; on this route about 1.1 resolution lengths lie between the launches, and the 2D table gives a straight section's impedance. A level within 2.2 Ω of a pair's target (1.1 Ω of a single net's) marks no feature, and the same values are compare's thresholds on a TDR level, three times the model's measured noise (gate P4-E, `docs/validation/2026-11-07-p4-e.md`).
- Copper staircased at 45° or along arcs is only warned about: gate P4-B measured a 45° pair 2.27 % (90 Ω) and 5.35 % (100 Ω) off its axis-aligned twin at mesh n 2, and whether such a pair is refused or run at a finer mesh is not decided yet (`docs/validation/2026-11-06-p4-b.md`).
- The dielectric is lossless by default, so S holds no dielectric loss, and the loss lines estimate it with the copper's. `"dielectric": "debye"` in project.json is the option, at a cost: a Debye cell weighs about 109 plain cells, so this board would run about 33 times slower (gate P4-D, `docs/validation/2026-11-07-p4-d.md`).
- A job whose port residual still falls fast enough at T_max runs on, up to four times T_max: the planes' cavity resonances ring in a lossless model, and they depend on the crop, so their frequencies and depths are no predictions. `cost` prints the time to that ceiling.
- `cost` prices a run of two jobs at once about 1.9 times too long, on the safe side, until a run with that many jobs at once measures the speed (`docs/validation/2026-11-08-p4-refit.md`).
- Copper is a perfect conductor; packages, dies and the connector's body are absent, and the ESD array is its pads alone; the ports are lumped at the pads.
- The retune stays what-if: `verify` checks the layout reduction with ideal parts, not the vendor parts.

## Development setup

1. Create a virtual environment: `python -m venv .venv`
2. Activate it: `.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere.
3. Install the package in editable mode with the development extras: `python -m pip install -e .[dev]`
4. Give the venv openEMS as Install says (on Windows, `kicad-rf-studio setup-openems <openEMS folder>`, and `CSXCAD_INSTALL_PATH` set to that folder: the tests import openEMS in this Python, which reads it to find openEMS's DLLs). Without it, the tests marked `openems` are skipped.
5. Run the tests: `python -m pytest -q`
6. Before a release, run `python tools/release_check.py`: it builds a wheel from git archive of HEAD and checks it, installs it in a fresh venv, starts the GUI there offscreen, runs `new --antenna` there on `tests/fixtures/ifa2g4_pi.kicad_pcb` and `new --interface` on `tests/fixtures/usb2_hs.kicad_pcb`, checks the KiCad button's plugin.json against KiCad's schemas, and runs the privacy gate's generic rules over the history and the wheel. One real run through the GUI, lpf915 at Draft then its verify, runs with `KRS_E2E_DIR` set to an empty folder outside the repository and openEMS importable (step 4): `python -X utf8 -m pytest tests/test_gui.py -k real_run -s`. It takes about lpf915's Draft run plus its verify, and its cost line prints the estimate first; a file named STOP in its newest run folder stops it. One antenna project through the GUI, `ifa2g4_pi` at Normal run, retuned, verified and compared with a verified ground-pour project, runs with `KRS_E2E_DIR` set to an empty folder outside the repository and `KRS_E2E_VARIANT` to that project's `project.json`, or to `window` to make the pour through the GUI first: `python -X utf8 -m pytest tests/test_gui.py -k antenna_project_through -s`. It takes about the pi project's run plus its verify, 1.4 h on the development PC (about 2.9 h with `window`, which also runs and verifies the pour). One signal-integrity project through the GUI, `usb2_hs` at Normal run, retuned, verified and compared with a verified plane-gap project, runs with `KRS_E2E_DIR` set to an empty folder outside the repository and `KRS_E2E_SI_VARIANT` to that project's `project.json`: `python -X utf8 -m pytest tests/test_gui.py -k si_project_through -s`. It takes about usb2_hs's run plus its verify, about 1.5 h on the development PC, after the variant's own run, retune and verify by the command line.
7. After a change to a message in `src/kicad_rf_studio/core/messages.py`, run `python tools/catalog.py` (Babel comes with the dev extras), translate each entry of `po/pt_BR.po` whose msgstr is empty (a changed message's old translation stays at the file's end as a `#~` entry), then run it again: the tests refuse a catalog that is not complete and compiled. They run in English whatever your system's language, and `KRS_TEST_LANGUAGE=pt_BR` runs `tests/test_gui.py` in Brazilian Portuguese.

## Contributing

Set up the local privacy gate before you commit or push. It refuses private names, absolute drive and home paths, network shares and e-mail addresses. CI repeats only the generic checks.

1. Write the words that must never leave your machine in a UTF-8 text file kept outside the repository, one per line. Blank lines and lines starting with `#` are ignored, and matching ignores case.
2. Point `KRS_PRIVATE_LIST` at that file. In PowerShell: `$env:KRS_PRIVATE_LIST = "<path to the file>"`. In a POSIX shell: `export KRS_PRIVATE_LIST=<path to the file>`.
3. Enable the hooks: `git config core.hooksPath .githooks`

The hooks run `tools/privacy_gate.py` with the Python found on your `PATH`; it needs only the standard library. Without a usable list they refuse the commit or push. `python tools/privacy_gate.py --all` scans the whole history by hand.

A hit prints as `<where>:<line>: <rule>`. `deny#N` is the N-th entry of your list, counting entries only, and `generic:...` is one of the built-in rules. The gate never prints matched text; a file whose name matched shows as `path#N`.
