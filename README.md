# kicad-rf-studio

kicad-rf-studio imports KiCad boards and simulates their RF parts with openEMS. It is free software, licensed under the GNU General Public License v3.0 or later (see `LICENSE`); its copy of CSXCAD's SmoothMeshLines is under the GNU Lesser General Public License v3.0 or later (see `COPYING.LESSER`).

## Install

### Windows

1. Create a virtual environment with Python 3.14: `py -3.14 -m venv <venv>`
2. Install kicad-rf-studio into it: `<venv>\Scripts\python -m pip install <clone of this repository>`
3. Unpack the official Windows package of openEMS 0.37 and give its folder, the one that holds `openEMS.exe` and `python\`, to `<venv>\Scripts\kicad-rf-studio setup-openems <openEMS folder>`. It installs the package's openEMS and CSXCAD wheels into the venv, offline, and records the folder.

### Linux

On Debian 12, Ubuntu 24.04 or Fedora, with the system Python (3.11 or newer):

1. Create a virtual environment and activate it: `python3 -m venv <venv>`, then `source <venv>/bin/activate`
2. Install kicad-rf-studio into it: `pip install <clone of this repository>`
3. In a clone of upstream's openEMS-Project, install the build dependencies with `./scripts/install_deps.sh --install --python`, then build with `./update_openEMS.sh <prefix> --python` while the venv is active. Leave the GUI build on (no `--disable-GUI`): it builds AppCSXCAD.

## Tutorial

This takes `lpf915`, the synthetic 915 MHz low-pass filter in `tests/fixtures` (a series DC block and a C-L-C pi of 0402 parts on a 50 Ω GCPW, under a shield), through `new`, `cost`, `run`, `retune` and `verify`. Run the commands from the root of the clone with the venv from Install; on Linux, with the venv active, type `kicad-rf-studio` alone.

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
P2: reached T_max (39.99 ns) at a residual of -69.7 dB. S is kept and flagged; raise t_max_s in project.json for a converged result.
```

P0-B's consistency criterion, `verify` against the co-simulation, failed (|ΔS21| at f0 0.1019 dB against 0.1 dB, max |ΔS| 0.0926 against 0.03), and P0-B was decided fail at the ceiling. Read P0-B's report before you take `verify`'s comparison as agreement.

## Development setup

1. Create a virtual environment: `python -m venv .venv`
2. Activate it: `.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere.
3. Install the package in editable mode with the development extras: `python -m pip install -e .[dev]`
4. Give the venv openEMS as Install says (on Windows, `kicad-rf-studio setup-openems <openEMS folder>`). Without it, the tests marked `openems` are skipped.
5. Run the tests: `python -m pytest -q`

## Contributing

Set up the local privacy gate before you commit or push. It refuses private names, absolute drive and home paths, network shares and e-mail addresses. CI repeats only the generic checks.

1. Write the words that must never leave your machine in a UTF-8 text file kept outside the repository, one per line. Blank lines and lines starting with `#` are ignored, and matching ignores case.
2. Point `KRS_PRIVATE_LIST` at that file. In PowerShell: `$env:KRS_PRIVATE_LIST = "<path to the file>"`. In a POSIX shell: `export KRS_PRIVATE_LIST=<path to the file>`.
3. Enable the hooks: `git config core.hooksPath .githooks`

The hooks run `tools/privacy_gate.py` with the Python found on your `PATH`; it needs only the standard library. Without a usable list they refuse the commit or push. `python tools/privacy_gate.py --all` scans the whole history by hand.

A hit prints as `<where>:<line>: <rule>`. `deny#N` is the N-th entry of your list, counting entries only, and `generic:...` is one of the built-in rules. The gate never prints matched text; a file whose name matched shows as `path#N`.
