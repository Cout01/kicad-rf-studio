# SPDX-License-Identifier: GPL-3.0-or-later
"""Every string a user can see is a code in CATALOG plus parameters. The English template is the
gettext msgid, so a translation is a catalog file under kicad_rf_studio/locale. The language is picked once, at
import (_languages)."""
import ctypes
import gettext
import json
import os
import sys
from pathlib import Path

LOCALE = Path(__file__).resolve().parents[1] / "locale"

CATALOG: dict[str, str] = {
    "E_PARSE_UNBALANCED": "The board file is damaged: unbalanced brackets near line {line}. Open it in KiCad and save it again.",
    "E_NOT_A_BOARD": "{path} is not a KiCad board file.",
    "E_BOARD_UNREADABLE": "Cannot read the board {path}: {reason}. Check the path, or open the board in KiCad and save it again.",
    "E_BOARD_VERSION": "This board was saved by a KiCad older than 9 (file version {version}). Open it in KiCad 9 or newer and save it.",
    "W_BOARD_NEWER": "This board was saved by a newer KiCad (file version {version}); reading it was not tested.",
    "W_REPAIRED_FILTER_RATIO": "Repaired {count} teardrop entries damaged by a KiCad 9 writer bug; the file on disk is unchanged.",
    "W_ZONE_NOT_FILLED": "Zone {uuid} on {layer} has no fill and is left out. Refill (B) in KiCad and save.",
    "W_NO_OUTLINE": "The board has no Edge.Cuts outline, so the substrate is not clipped.",
    "W_COPPER_DROPPED": "{kind} {uuid} on {layer} is left out of the simulation; convert it to a filled shape or a solid zone in KiCad if it carries current.",
    "W_NETLESS_COPPER": "Copper shape {uuid} on {layer} has no net and is simulated as floating copper.",
    "W_COPPER_EMPTIED": "Copper of net {net} on {layer} is smaller than the 10 µm simplification and was left out.",
    "E_OPEN_IN_ROI": "Net {net} is broken inside the simulated region. Check the copper in KiCad and refill zones (B).",
    "E_SHORT_IN_ROI": "Nets {nets} touch inside the simulated region. Check the copper in KiCad and refill zones (B).",
    "W_OPEN_IN_MARGIN": "Net {net} is broken in the margin of the simulated region, which may affect the result. Check the copper in KiCad and refill zones (B).",
    "W_SHORT_IN_MARGIN": "Nets {nets} touch in the margin of the simulated region, which may affect the result. Check the copper in KiCad and refill zones (B).",
    "W_STAIRCASED": "Net {net} has copper that is not axis-aligned (45° segments or arcs), which the mesh staircases. P0-A measured a staircased 45° line 4.6 % off its axis-aligned twin in Z0 at mesh n 2, within the 5 % budget, so the run goes on, but its accuracy is not validated. For a validated result, route the measured nets with horizontal and vertical tracks. A finer mesh lowers the error: set \"mesh\": {{\"n\": 3}} in project.json.",
    "E_LID_HEIGHT": "Shield {refs} covers the simulated region but project.json has no lid_height_mm. Set lid_height_mm in project.json, or set \"lid\": false to leave the lid out.",
    "E_CHAIN_OFF_OUTLINE": "The measured nets ({nets}) have copper outside the board outline, or no copper at all. Of several Edge.Cuts outlines in one file (a panel, a frame, a coupon beside the board), only the one that encloses the most is read: save the board in a file of its own, or delete the other outlines.",
    "E_EDGE_LINT": "A mesh line sits badly at the copper edge {edge_mm} mm ({axis}, {reason}) even after one re-mesh. Widen the gap at that edge in KiCad, or change mesh.n in project.json (now {n}).",
    "E_FIT2D": "The mesh misses the 2D reference on net {net} ({layer}) by {err_pct} % (limit {limit_pct} %) at mesh.n {n}. Set mesh.n to 3 in project.json.",
    "E_FIT2D_FINE": "The fine mesh (mesh.n {n}) still misses the 2D reference on net {net} ({layer}) by {err_pct} % (limit {limit_pct} %). Raising gates.fit2d_limit in project.json lets the run go on, at your own risk.",
    "E_FIT2D_SHORT": "Other copper touches net {net} on {layer} at its 2D cut, so fit2d cannot check it. Check the copper in KiCad and refill zones (B); copper with no net counts too.",
    "I_2D_HEADER": "2D estimate: bends, vias, pads and parts not included",
    "I_2D_SECTION": "{net} on {layer}: width {width_mm} mm, gap {gap_mm}, length {length_mm} mm — Z0 {z0} Ω, εeff {eeff} without mask; Z0 {z0_mask} Ω, εeff {eeff_mask} with mask",
    "W_NO_SECTIONS": "The measured nets have no straight, axis-aligned sections, so there is no 2D estimate.",
    "W_2D_SHORT": "{net} on {layer}: width {width_mm} mm, length {length_mm} mm — other copper touches this line, so there is no 2D estimate. Check the copper in KiCad and refill zones (B).",
    "W_PADSTACK": "Pad {pad} uses a per-layer padstack; its front shape is used on every layer.",
    "W_DUPLICATE_REF": "Footprints share the references {refs}; the copies were renamed with #2, #3 and so on. Annotate the board in KiCad to name them.",
    "E_BAD_FREQUENCY": 'Cannot read the frequency "{text}". Write it like 915MHz.',
    "E_UNKNOWN_PRESET": 'Unknown stackup preset "{name}". Known presets: {known}.',
    "E_DEFAULT_RULE_LAYERS": "Stackup presets are implemented for 2 copper layers, and this board has {count}. Add the stackup to the board in KiCad.",
    "W_COPPER_WEIGHT": "Copper layers {layers} are not 35 µm; the mesh rule is not validated for this copper weight.",
    "E_NO_STACKUP": "The board has no stackup. Give --stackup jlcpcb-2l, or --stackup kicad-default to accept KiCad's default rule.",
    "E_STACKUP_LAYERS": "The stackup has {stackup} copper layers but the board has {board}. Fix the board stackup in KiCad, or choose a matching --stackup.",
    "E_DIELECTRIC_THICKNESS": 'The stackup layer "{layer}" has no thickness. Set its thickness in KiCad (Board Setup → Physical Stackup), save the board and re-create the project.',
    "E_UNKNOWN_PAD": "Pad {name} does not exist. Closest pads: {candidates}.",
    "E_AMBIGUOUS_PAD": "Pads named {name} sit on different nets ({nets}). Name a pad with a unique number.",
    "E_START_ON_GND": 'Pad {name} is on net "{net}", which is GND, power or no net; a chain cannot start or end there.',
    "E_SAME_PADS": "The chain starts and ends at the same pad, {name}. Give two different pads.",
    "E_NO_CHAIN": "No chain from {start} to {end}: the walk stopped at nets {reached}. A DNP part, a connector, a shield, a GND or power net, or a part with three or more pads is in the way.",
    "E_PROJECT_SCHEMA": "{path} uses project schema {found}; this version reads schema {expected}.",
    "E_PROJECT_UNREADABLE": "Cannot read the project {path}: {reason}. Check the path, or fix project.json in a text editor.",
    "E_PROJECT_FIELD": "{path}: {field} is missing or is not {expected}. Fix it in a text editor, or re-create the project with `new`.",
    "E_OUTPUT_PATH": "Cannot write {path}: {reason}. Choose another -o folder.",
    "E_PROJECT_EXISTS": "{path} already exists. Delete it, or give another -o folder.",
    "I_STACKUP": "Stackup: {source}, dielectric {thickness_mm} mm, εr {epsilon_r}; mask {mask_mm} mm, εr {mask_epsilon_r}.",
    "I_STACKUP_NO_MASK": "Stackup: {source}, dielectric {thickness_mm} mm, εr {epsilon_r}; no mask.",
    "I_CLASSES": "GND nets: {gnd}. Power nets: {power}. Connectors: {connectors}. Shields: {shields}.",
    "I_CHAIN": "Chain {start} → {end}: series {series}; shunt {shunt}.",
    "I_PART": "Part {ref} {value}: {role}; package {package}, ESL {esl_nh} nH, ESR {esr_ohm} Ω.",
    "I_PART_NO_MODEL": "Part {ref} {value}: {role}; no package preset, so as a port a C, L or R takes its ideal value and any other part needs its S2P file (`retune PROJECT {ref}=file.s2p:series`, or :shunt).",
    "I_PORT": "Port {name}: signal {signal}, reference {reference} ({rule}).",
    "I_PORT_POINT": "Port {name}: signal {signal}, reference ({x}, {y}) on {layer} ({rule}).",
    "I_PORT_NO_REFERENCE": "Port {name}: signal {signal}, no reference.",
    "I_F0": "f0 {f0_mhz} MHz, with {harmonics} harmonics.",
    "I_DEFAULTS": "Preset {preset} (provisional default), band factor {band_factor}, T_max {t_max_ns} ns, harmonics {harmonics}, mesh n {mesh_n}, region {expand_h} substrate heights past the chain, margin scale {margin_scale}, protected reach {reach_h} substrate heights.",
    "I_LID_ON": "Shield lid on: \"lid\": null in project.json means on when harmonics > 1; true or false forces it.",
    "I_LID_OFF": "Shield lid off: \"lid\": null in project.json means on when harmonics > 1; true or false forces it.",
    "W_FILLS_AS_SAVED": "Fills as saved — refill (B) in KiCad and save if you changed copper.",
    "W_LID_HEIGHT_MISSING": "Shield {refs} covers the simulated region and no --lid-height was given; set lid_height_mm in project.json before `run`, or \"lid\": false to leave the lid out.",
    "W_VALUE_UNREADABLE": "Cannot read the value of {refs}. Write values like 4.7pF, 4p7 or 15nH.",
    "W_PART_OPEN": "Left open in the simulated region: {refs}. Their self-resonance from the package preset is below 3·f2, or they are chokes or not C, L or R; make one a port in project.json if it matters (each port adds a run).",
    "W_F0_RANGE": "f0 = {f0_hz} Hz is outside 1 MHz to 100 GHz. Did you forget the unit, as in 915MHz?",
    "W_NO_REFERENCE": "No reference found for {signal}; set it in project.json before `run`.",
    "W_ABSOLUTE_BOARD_PATH": "The board is on another drive, so project.json stores its absolute path.",
    "I_WROTE": "Wrote {path}.",
    "E_SETTINGS_UNREADABLE": "Cannot read {path}: {reason}. Delete it; setup-openems and calibrate write it again.",
    "E_OPENEMS_MISSING": "openEMS is not installed for {python}. Install it: {command}",
    "E_OPENEMS_OLD": "This Python has openEMS {openems} and CSXCAD {csxcad}; kicad-rf-studio needs openEMS 0.37 and CSXCAD 0.7 or newer. Install them: {command}",
    "W_OPENEMS_UNTESTED": "openEMS {openems} is not 0.37.x, the version kicad-rf-studio is tested with, so results may differ. Install 0.37 for validated results: {command}",
    "E_SETUP_OPENEMS_WINDOWS": "setup-openems is for Windows. On Linux, build openEMS with update_openEMS.sh <prefix> --python while this venv is active (see README).",
    "E_SETUP_OPENEMS_DIR": "{dir} is not an openEMS package for this Python: it needs openEMS.exe and the openems and csxcad wheels for {tag} in its python folder. Give the folder of the official Windows package of openEMS 0.37.",
    "E_SETUP_OPENEMS_PIP": "pip could not install the openEMS wheels (exit code {exit_code}). Read pip's output above, then run setup-openems again.",
    "I_OPENEMS_INSTALLED": "Installed openEMS {openems} and CSXCAD {csxcad} from {dir}; the folder is recorded in {settings}.",
    "E_NO_PORTS": "project.json has no ports, so there is nothing to excite. Create the project with `new` between two pads.",
    "E_NO_REFERENCE": "Port {signal} has no reference. Set its \"reference\" in project.json to a pad or a point before running.",
    "E_REFERENCE_POINT": "Port {name}: no copper on {layer} lies at its reference point {point} mm. Set its \"reference\" in project.json to a point on the ground copper, or to a pad.",
    "E_REFERENCE_LAYER": "Port {name}: its reference is on {reference_layer} and its signal pad on {signal_layer}; Stage 1 builds horizontal ports only. Choose a reference on {signal_layer} in project.json.",
    "E_ROTATED_PART": "Part {ref} is not at a multiple of 90°, so its port would be a CurvePort, which P0-B measured outside the consistency limits against its 0° twin (max |ΔS| 0.194). Rotate it in KiCad, or set \"allow_curve_port\": true in project.json at your own risk.",
    "E_PORT_SPANS": "Port {name}: its two pads face each other neither along x nor along y, so no box joins them. Choose a reference straight across from the signal pad in project.json.",
    "E_PORT_BOX": "Port {name}: its box finds no mesh line inside its pads, or no copper-free mesh line between them with each end on its own pad's copper. Change mesh.n in project.json (another value moves the mesh lines), use larger pads, or clear other copper from between the pads.",
    "E_PART_VALUE": "Part {ref} is in the grid but its value \"{value}\" cannot be read. Fix its value in project.json, or set its role to \"open\" or \"port\".",
    "E_GRID_KIND": "Part {ref} cannot sit in the grid: only a C or an R can. Set its role to \"port\" or \"open\" in project.json.",
    "E_LOCKED": "Another run of this project has been running since {started} in {run}. Wait for it, or create a file named STOP in that folder to stop it; if no run is going on, delete {lock}.",
    "E_RUN_DIR": "Cannot use {path} as the run folder: {reason}. Give another --run-dir.",
    "W_STALE_LOCK": "Reclaimed {lock}: the run in {run} ended without releasing it.",
    "E_OPENEMS_DLL": "openEMS could not load its libraries (CSXCAD_INSTALL_PATH is {value}). Install it again: {command}",
    "E_SETUP_FAILED": "openEMS could not set up the model; see {log}. Look at the model with `preview`.",
    "E_WORKER_FAILED": "The {job} worker ended with code {exit_code}; see {log}. Report it if the log shows no cause.",
    "I_CALIBRATING": "Measuring this machine's simulation speed, once (20–30 s)…",
    "I_CALIBRATED": "Calibrated: {pool} jobs at once with {threads} threads each, {speed} MC/s in all; `kicad-rf-studio calibrate` measures again.",
    "I_END": "The command ended with exit code {exit_code}.",
    "W_BOARD_CHANGED": "The board {path} changed since `new` wrote project.json; its chain, ports and parts may be stale. Re-create the project with `new` if you moved copper.",
    "W_OFF_TOP_LAYER": "Net {net} runs on {layer}, not on the top copper; the region, the cell size and dz0 use the top layer's substrate height (a Stage 1 limit). Check its fit2d result.",
    "E_PORT_OPEN": "Port {name}: its {end} end does not lie in its own pad's copper on the mesh. Check the port in project.json and look at it with `preview`.",
    "E_PORT_SHORT": "Port {name}: its signal and reference are one piece of copper on the mesh, a short. Check the copper between them in KiCad and with `preview`.",
    "I_COST_CELLS": "Cells: {nx} × {ny} × {nz} = {mcells} M (mesh n {n}, cell d {d_mm} mm).",
    "I_COST_SMALLEST": "Smallest cell: {size_um} µm across {axis}, at {axis} = {at_mm} mm.",
    "I_COST_DT": "dt {dt} s (floor {floor} × {ref} s), set by the {axis} edge at ({x}, {y}, {z}) mm.",
    "I_COST_TIME": "Worst case: {time} for {runs} runs to T_max {t_max_ns} ns, {pool} at once with {threads} threads each.",
    "I_COST_PREDICTED": "Predicted from the last run's stop times: {time}.",
    "I_COST_RAM": "RAM: about {gb} GB ({pool} jobs at once).",
    "I_COST_DRIVER_CELL": "Main cost: the {size_um} µm cell across {axis} at {at_mm} mm, under d/3, sets dt. Move or merge the copper edges there in KiCad.",
    "I_COST_DRIVER_RUNS": "Main cost: {runs} runs, one per port, {parts} of them part ports.",
    "I_COST_DRIVER_CELLS": "Main cost: the cell count. The cell d {d_mm} mm follows the narrowest width, gap or substrate height; a smaller region.expand_h shrinks it.",
    "W_NO_PORTS": "project.json has no ports, so cost stops after the 2D estimate. Create the project with `new` between two pads to simulate it.",
    "W_RAM": "One job needs about {need_gb} GB of RAM and {free_gb} GB is free, so jobs run one at a time and may still swap. Close other programs, or shrink the model (region.expand_h, mesh.n in project.json).",
    "E_DT_FLOOR": "openEMS's timestep {dt} s is below {floor} × the reference {ref} s, set by the {axis} edge at ({x}, {y}, {z}) mm. A tiny cell there makes the run slow; move or merge the copper edges near it in KiCad.",
    "E_UNUSED_PRIMITIVE": "openEMS left part of {property} out of the model ({type}). A primitive type such as Box touches no mesh edge, \"none\" means the property holds no primitive, and \"outside\" means it lies outside the simulated region. So that port or part is not in the model. Look at it with `preview`.",
    "W_UNUSED_PRIMITIVE": "openEMS left part of {property} out of the model ({type}). A primitive type such as LinPoly is a sliver smaller than a cell, \"none\" means the property holds no primitive, and \"outside\" means it lies outside the simulated region. Look at it with `preview` if it should carry current.",
    "W_GATE_LIMITS": "project.json sets gates.fit2d_limit {fit2d_limit} and gates.dt_floor {dt_floor}, not 0.03 and 0.8, so this verdict is outside the validated limits. Set them back to 0.03 and 0.8 for a validated result.",
    "I_GATES_PASSED": "Gates passed: edge lint, fit2d, timestep floor (dt {dt} s), port connectivity and unused primitives.",
    "I_RUN_START": "Running {runs} jobs, {pool} at once, in {folder}. Create a file named STOP there, or press Ctrl+C, to stop.",
    "I_PROGRESS": "{port}: {t_ns} ns, residual {residual_db} dB, {speed_mcs} MC/s.",
    "I_JOB_CONVERGED": "{port}: converged at {t_ns} ns (residual {residual_db} dB).",
    "W_JOB_FLAT": "{port}: not converged at {residual_db} dB; the residual stopped falling at {t_ns} ns. S is kept and flagged; look for a resonance or an open port with `preview`.",
    "W_JOB_T_MAX": "{port}: reached T_max ({t_ns} ns) at a residual of {residual_db} dB. S is kept and flagged; raise t_max_s in project.json for a converged result.",
    "E_JOB_DIVERGED": "{port}: diverged at {t_ns} ns (NaN or inf), so its S is not kept. Look for tiny cells with `cost` and at the model with `preview`.",
    "E_JOB_GROWTH": "{port}: the energy grew 20 dB after the pulse, at {t_ns} ns, so its S is not kept. Look at the model with `preview`.",
    "W_JOB_UNCLASSIFIED": "{port}: the worker ended before T_max without a verdict, so its S is not kept. See {log}.",
    "W_JOB_STOPPED": "{port}: stopped, so its S is not kept. Run `run` again for results.",
    "I_RESULTS": "{kept} of {runs} jobs kept S, in {wall}; results recorded in {path}.",
    "W_RUN_NOT_KEPT": "{kept} of {runs} jobs kept S, in {wall}, so project.json keeps its previous results and results/ is unchanged. The verdicts above, also in {folder}, say why; fix that and run `run` again.",
    "I_PREVIEW": "Opened {path} in AppCSXCAD.",
    "E_APPCSXCAD_MISSING": "AppCSXCAD was not found; open {path} in it by hand, or install openEMS with it: {command}",
    "E_S_SINGULAR": "The run's excitations are not independent at {f_mhz} MHz (condition number {kappa}, limit {limit}), so S cannot be computed: a job's waves are dead or duplicated. Run `run` again.",
    "E_RESULTS_JOB": "The last run's job {port} ended {verdict}, so its S was not kept and the layout cannot be reduced. Run `run` again.",
    "E_RESULTS_WAVES": "{path} is missing: the last run's folder was moved or deleted. Run `run` again.",
    "E_PART_NO_VALUE": "Part {ref} has no value that reads (\"{value}\") and no S2P file, so its port cannot be closed. Give its S2P file with `retune PROJECT {ref}=file.s2p:series` (or :shunt), or, for a C, L or R, a value with `retune PROJECT {ref}=VALUE`.",
    "E_S2P_MISSING": "Part {ref}: its S2P file {path} does not exist. Name an existing file with `retune PROJECT {ref}=file.s2p:series` (or :shunt), or, for a C, L or R, give a value with `retune PROJECT {ref}=VALUE`.",
    "E_S2P_UNREADABLE": "Part {ref}: {path} is not a Touchstone file that can be read. Check the file, or, for a C, L or R, give a value with `retune PROJECT {ref}=VALUE`.",
    "E_S2P_PORTS": "Part {ref}: {path} has {ports} ports, and a part needs a 2-port measured in a series or a shunt fixture. Give its .s2p file.",
    "E_S2P_BAND": "Part {ref}: {path} covers {f_lo}–{f_hi} MHz, not the simulated band {f1}–{f2} MHz, and it is never extrapolated. Give a file that covers the band, or, for a C, L or R, a value with `retune PROJECT {ref}=VALUE`.",
    "W_S2P_FIXTURE": "Part {ref}: {path} fits a {fits}-thru measurement better than the :{named} it was given. The suffix names the fixture the vendor measured the part in, not its place on the board; if the vendor used {fits}-thru, give it again as `retune PROJECT {ref}=file.s2p:{fits}`.",
    "E_CBOX": "The last run recorded no usable C_box for part {ref} ({value}), so its port cannot be closed. Run `run` again, and look at the part's port with `preview` if this repeats.",
    "I_PASSIVITY": "Passivity: σ_max {sigma} at worst, at {f_mhz} MHz (|a| {a_db} dB); flagged above {limit}.",
    "W_PASSIVITY": "Passivity flagged: σ_max {sigma} at {f_mhz} MHz (|a| {a_db} dB) is above {limit}, so this S makes power. Check the verdicts above: a flat or T_max job is the usual cause, and a stricter preset the fix.",
    "I_RECIPROCITY": "Reciprocity: |Sij − Sji| {err} at worst, at {f_mhz} MHz (|a| {a_db} dB); flagged above {limit}.",
    "W_RECIPROCITY": "Reciprocity flagged: |Sij − Sji| {err} at {f_mhz} MHz (|a| {a_db} dB) is above {limit}. Check the verdicts above: a flat or T_max job is the usual cause, and a stricter preset the fix.",
    "I_LOSS_BUDGET": "Loss budget: {layout_pct} % unaccounted with the part losses removed, against {expected_pct} % expected dielectric loss, at worst at {f_mhz} MHz (|a| {a_db} dB); flagged {limit_pct} points above.",
    "W_LOSS_BUDGET": "Loss budget flagged: {layout_pct} % unaccounted at {f_mhz} MHz (|a| {a_db} dB) is more than {limit_pct} points above the {expected_pct} % expected dielectric loss. Radiation or power coupled into cut nets is the usual cause; look at the model with `preview`.",
    "W_ETA_RAD": "Radiation efficiency flagged: η_rad {eta} at {f_mhz} MHz is above {limit}, so the far field radiates more power than the port accepts, and the efficiencies and gains at that frequency are not reliable. A stricter preset or a wider air gap is the usual fix.",
    "E_RESULTS_WRITE": "Cannot write {path}: {reason}. Close the program that holds it open (a spreadsheet, say), then run `{command}` to write it again.",
    "I_MARKER": "{marker} = {f_mhz} MHz (|a| {a_db} dB): IL {il_db} dB and RL {rl_db} dB with layout; IL {il_ideal_db} dB and RL {rl_ideal_db} dB ideal schematic.",
    "I_MARKER_TRACE": "{marker} = {f_mhz} MHz (|a| {a_db} dB): IL {il_db} dB and RL {rl_db} dB.",
    "I_HR": "Harmonic rejection at {marker}: {hr_db} dB with layout, {hr_ideal_db} dB ideal schematic.",
    "I_HR_TRACE": "Harmonic rejection at {marker}: {hr_db} dB.",
    "I_BASIS": "Results of the run in {run_dir} at preset {preset}: {converged} jobs converged, {flat} flat, {t_max} at T_max.",
    "W_NOT_TWO_PORT": "The project has {ports} external ports, not 2, so the 2-port summary (PNG, CSV, IL, RL, harmonic rejection, loss budget, ideal schematic) is skipped; the Touchstone files and the passivity and reciprocity checks are written. Keep two ports in project.json for the summary.",
    "I_WHAT_IF": "Relative / what-if: the instant retune is not yet validated against a full simulation of a real board (spec 7.6), so read these chain results as relative. Check the final values with `{command}`.",
    "I_OUTPUTS": "Wrote {files} in {folder}.",
    "I_PLOT_TITLE": "{name}: relative to a 50 Ω source and load",
    "I_PLOT_LAYOUT": "with layout",
    "I_PLOT_IDEAL": "ideal schematic",
    "I_PLOT_FREQUENCY": "Frequency (GHz)",
    "I_LIMIT_MAGNETIC": "Limit: no magnetic coupling between part bodies.",
    "I_LIMIT_LID": "Limit: no interaction between part bodies and the lid.",
    "I_LIMIT_S2P_PLANE": "Limit: vendor S2P reference planes differ from the pad-gap box.",
    "I_LIMIT_PEC": "Limit: copper is PEC, so there is no conductor loss.",
    "I_LIMIT_WALLS": "Limit: the through-crop walls absorb most of the power coupled into cut nets, and reflect the rest.",
    "I_LIMIT_ACCURACY": "Limit: accuracy is reported as |ΔS| or as a null shift, never in dB at a null.",
    "I_LIMIT_50_OHM": "Limit: insertion loss, return loss and harmonic rejection are relative to a 50 Ω source and load.",
    "I_LIMIT_IDEAL": "Limit: the ideal schematic is the same part models (preset or S2P) joined ideally: no layout, no C_box, no traces.",
    "I_LIMIT_LOSS": "Limit: the expected dielectric loss is a lower bound from the measured straight sections.",
    "E_RETUNE_NO_PARTS": "This project has no part ports (a single trace), so there is nothing to retune; `run` writes its outputs.",
    "E_RETUNE_ARG": "Cannot read \"{arg}\": write REF=VALUE, as in C1=4.7pF, or REF=file.s2p:series (or :shunt).",
    "E_RETUNE_TWICE": "{ref} is assigned twice; give each part once.",
    "E_RETUNE_UNKNOWN": "No part {ref} is a port of this project. The parts you can retune: {refs}.",
    "E_RETUNE_ROLE": "Part {ref} is {role} in the model, not a port, so retune cannot change it. To retune it, set its role to \"port\" in project.json and run `run` again (each port adds a run).",
    "E_RETUNE_VALUE": "Cannot read \"{value}\" as the value of {ref}: a C, L or R takes a value in its own unit (4.7pF, 4p7, 15nH, 50R; a C above 0), and any part takes an S2P file as {ref}=file.s2p:series (or :shunt).",
    "E_NO_RESULTS": "project.json has no results yet. Run `run` first.",
    "E_RESULTS_STALE": "The model changed since the last run (a board re-saved in KiCad can change it too), or that run is older than this version, so its results no longer apply. Run `run` again.",
    "E_VERIFY_VALUE": "verify puts each part in the grid at its value, but {ref} has \"{value}\": verify can place only a C, L or R whose value reads (a C above 0). Set {ref}'s \"value\" in project.json, which keeps its S2P file, then run verify again; `retune PROJECT {ref}=VALUE` sets it too but drops the S2P file.",
    "E_VERIFY_DUMP": "verify sizes each part's cell from the last run's operator dump {path}, which is missing. Run `run` again.",
    "E_VERIFY_K": "Part {ref}: its inductor in the grid resonates too fast for the time step (k {k}, limit {limit}), and the run would diverge. Check its value in project.json; a real inductor reads k near 0.01.",
    "E_VERIFY_NO_PARTS": "This project has no part ports (a single trace), so verify has nothing to put in the grid: `run` is already its full simulation.",
    "E_VERIFY_CURVE": "Part {ref} is rotated (a CurvePort), and verify cannot put a rotated part in the grid. Rotate it in KiCad to a multiple of 90° to verify this chain.",
    "E_VERIFY_PORTS": "verify compares S21 and S11, so it needs at least 2 external ports; this project has {ports}. Keep two ports in project.json.",
    "W_VERIFY_NOT_KEPT": "{kept} of {runs} verify jobs kept S, in {wall}, so nothing was compared or stored. The verdicts above, also in {folder}, say why; fix that and run `verify` again.",
    "I_VERIFY_RESULTS": "{runs} verify jobs kept S, in {wall}; the comparison is stored in {path}.",
    "I_VERIFY_COMPARE": "verify against the retune at the same ideal values: |ΔS21| {ds21_db} dB and |ΔS11| {ds11} at f0 = {f0_mhz} MHz (|a| {a_db} dB); max |ΔS| {ds_max} up to f2.",
    "I_VERIFY_NULL": "Null of |S21| at {f_mhz} MHz in verify (|a| {a_db} dB): null shift {shift_pct} % against the retune's.",
    "W_VERIFY_NULL_UNMATCHED": "Null of |S21| at {f_mhz} MHz in verify (|a| {a_db} dB) has no match within ±5 % in the retune at the same ideal values; the stated limits below say what that reduction leaves out.",
    "I_VERIFY_NO_NULLS": "No null of |S21| stands 20 dB out of the response, so there is no null shift to report.",
    "I_VERIFY_LOSS_BUDGET": "Loss budget: {layout_pct} % unaccounted with the parts in the grid (a resistor's loss counts here), against {expected_pct} % expected dielectric loss, at worst at {f_mhz} MHz (|a| {a_db} dB); flagged {limit_pct} points above.",
    "W_VERIFY_LOSS_BUDGET": "Loss budget flagged: {layout_pct} % unaccounted at {f_mhz} MHz (|a| {a_db} dB) is more than {limit_pct} points above the {expected_pct} % expected dielectric loss, with the parts in the grid. A resistor in the chain adds its own loss here; otherwise radiation or power coupled into cut nets is the usual cause; look at the model with `preview`.",
    "I_VERIFY_SCOPE": "verify checks the layout reduction, not the vendor part data: each part sat in the grid at its ideal value, against a retune at the same values. Its loss budget counts a resistor's loss in the grid as layout loss.",
    "E_INTERNAL": "Internal error: {detail}. Please report it.",
    "G_APP": "kicad-rf-studio",
    "G_RUNNING": "Running in {folder}…",
    "G_END_DONE": "Finished (exit code {exit_code}).",
    "G_END_REFUSED": "Refused (exit code {exit_code}): the message above says why and what to do.",
    "G_END_BLOCKED": "A gate blocked it (exit code {exit_code}): the verdicts above say which and what to change.",
    "G_END_NOT_KEPT": "Not every job kept S (exit code {exit_code}), so the previous results stay; the verdicts above say why.",
    "G_END_STOPPED": "Stopped (exit code {exit_code}).",
    "G_END_FAILED": "Failed (exit code {exit_code}): the message above says what happened. Please report it.",
    "G_END_EXITED": "The process in {folder} exited with code {exit_code} without recording how it ended: it was killed, or it failed at its start ({log} says why). Start it again; the next run reclaims any lock it left.",
    "G_END_LOST": "The process of {folder} ended without recording how (it was killed, or the PC restarted). Start it again; the next run reclaims any lock it left.",
    "G_ENDED": "The run in {folder}, started from another window or a terminal, has ended. Its verdicts are above, and the results it kept show in Results.",
    "G_LOCKED": "A run of this project, started at {started} from another window or a terminal, is going on in {run}. Stop stops it. If no run is going on (its process was killed and its number reused), delete {lock}.",
    "G_RUN_START": "Running {runs} jobs, {pool} at once, in {folder}. Stop stops them.",
    "G_WHAT_IF": "Relative / what-if: the instant retune is not yet validated against a full simulation of a real board (spec 7.6), so read these chain results as relative. Check the final values with Verify.",
    "G_NO_RESULTS": "No results yet: estimate the cost, then run.",
    "G_RESULTS_STALE": "The model changed since the last run (a board re-saved in KiCad can change it too), or that run is older than this version, so its results no longer apply. Estimate the cost and run again.",
    "G_TAB_PROJECT": "Project",
    "G_TAB_COST": "Cost",
    "G_TAB_RUN": "Run",
    "G_TAB_RESULTS": "Results and retune",
    "G_OPEN": "Open a project…",
    "G_OPEN_FILTER": "Projects (*.json)",
    "G_COST": "Estimate the cost",
    "G_RUN": "Run…",
    "G_STOP": "Stop",
    "G_LOADING": "Reading the project and building its model…",
    "G_PROJECT": "{path}: f0 {f0_mhz} MHz, {harmonics} harmonics, preset {preset}.",
    "G_NO_COST": "No cost of this model yet: estimate it, then Run… asks to start the run.",
    "G_COST_REUSED": "The cost in {folder} matches this model: Run… asks to start the run.",
    "G_CONFIRM_TITLE": "Start the run?",
    "G_CONFIRM_RUN": "Start the run? Its cost:",
    "G_START_FAILED": "Cannot start {program}: {reason}. Install kicad-rf-studio again.",
    "G_COL_PORT": "Port",
    "G_COL_TIME": "t (ns)",
    "G_COL_RESIDUAL": "Residual (dB)",
    "G_COL_SPEED": "MC/s",
    "G_COL_VERDICT": "Verdict",
    "G_NEW": "New from a board",
    "G_NEW_BOARD": "Board",
    "G_NEW_START": "Start pad (REF.PAD)",
    "G_NEW_END": "End pad (REF.PAD)",
    "G_NEW_F0": "f0 (for example 915MHz)",
    "G_NEW_HARMONICS": "Harmonics",
    "G_NEW_PRESET": "Preset",
    "G_NEW_STACKUP": "Stackup",
    "G_NEW_LID": "Shield lid height (mm)",
    "G_NEW_FOLDER": "Project folder",
    "G_NEW_NO_FOLDER": "Choose the project folder: New writes project.json into it.",
    "G_BROWSE": "Browse…",
    "G_BOARD_FILTER": "KiCad boards (*.kicad_pcb)",
    "G_STACKUP_BOARD": "The board's own",
    "G_CREATE": "Create the project",
    "G_CREATING": "Reading the board and writing project.json…",
    "G_PROJECT_EXISTS": "{path} already exists. Open it with Open a project…, or choose another project folder.",
    "G_OUTPUT_PATH": "Cannot write {path}: {reason}. Choose another project folder.",
    "G_NO_STACKUP": "The board has no stackup. Choose the stackup jlcpcb-2l, or kicad-default to accept KiCad's default rule.",
    "G_STACKUP_LAYERS": "The stackup has {stackup} copper layers but the board has {board}. Fix the board stackup in KiCad, or choose a matching stackup.",
    "G_LID_HEIGHT_MISSING": "Shield {refs} covers the simulated region and no lid height was given; set lid_height_mm in Advanced before you run, or set lid to false to leave the lid out.",
    "G_PART_NO_MODEL": "Part {ref} {value}: {role}; no package preset, so as a port a C, L or R takes its ideal value and any other part needs its S2P file, which its row in Results and retune takes.",
    "G_NO_REFERENCE": "No reference found for {signal}; set its port's reference (ports[].reference) in Advanced before you run.",
    "G_COL_PART": "Part",
    "G_COL_VALUE": "Value",
    "G_COL_SNAP": "Snapping",
    "G_COL_S2P": "S2P file",
    "G_COL_FIXTURE": "S2P fixture",
    "G_SNAP_OFF": "off",
    "G_SNAP_E12": "E12",
    "G_SNAP_E24": "E24",
    "G_FIXTURE_SERIES": "series",
    "G_FIXTURE_SHUNT": "shunt",
    "G_CHOOSE_S2P": "S2P file…",
    "G_S2P_FILTER": "Touchstone 2-ports (*.s2p)",
    "G_REVERT": "Revert",
    "G_DROPPED": "project.json or its board changed on disk: the values you had not applied to the parts it changed, or to results that no longer apply, were dropped, and those parts show their stored values.",
    "G_RETUNE_VALUE": "Cannot read \"{value}\" as the value of {ref}: a C, L or R takes a value in its own unit (4.7pF, 4p7, 15nH, 50R; a C above 0), and any part takes an S2P file in its row.",
    "G_PART_NO_VALUE": "Part {ref} has no value that reads (\"{value}\") and no S2P file, so its port cannot be closed. Give it an S2P file in its row, or, for a C, L or R, a value.",
    "G_S2P_MISSING": "Part {ref}: its S2P file {path} does not exist. Choose an existing file in its row, or, for a C, L or R, clear the file to use its value.",
    "G_S2P_UNREADABLE": "Part {ref}: {path} is not a Touchstone file that can be read. Check the file, or, for a C, L or R, clear the file to use its value.",
    "G_S2P_BAND": "Part {ref}: {path} covers {f_lo}–{f_hi} MHz, not the simulated band {f1}–{f2} MHz, and it is never extrapolated. Choose a file that covers the band, or, for a C, L or R, clear the file to use its value.",
    "G_S2P_FIXTURE": "Part {ref}: {path} fits a {fits}-thru measurement better than the {named} fixture it was given. The fixture names how the vendor measured the part, not its place on the board; if the vendor used {fits}-thru, set its fixture to {fits}.",
    "G_APPLY": "Apply",
    "G_APPLYING": "Applying: retune stores the changed values in project.json and writes results/…",
    "G_APPLIED": "Applied: project.json holds these values, and {folder} holds their outputs.",
    "G_VERIFY": "Verify",
    "G_VERIFY_NONE": "Not verified yet: Verify runs a full simulation of the stored values, with each part in the grid.",
    "G_VERIFY_STALE": "Verify is stale: the values or the model changed since the last verify.",
    "G_APPLY_FIRST": "Verify runs the values stored in project.json, and these are not applied yet. Apply them, then verify?",
    "G_VERIFY_VALUE": "Verify puts each part in the grid at its value, but {ref} has \"{value}\": Verify can place only a C, L or R whose value reads (a C above 0). Set {ref}'s value in Advanced (under chain.series, chain.shunt or others), which keeps its S2P file, or clear the file in its row in Results and retune and type the value there, which Apply stores without the file; then press Verify again.",
    "G_TAB_ADVANCED": "Advanced",
    "G_COL_FIELD": "Field",
    "G_COL_DEFAULT": "Default",
    "G_COL_UNIT": "Unit",
    "G_SAVE": "Save",
    "G_SAVE_FAILED": "Cannot save {path}: {reason}. Close the program that holds it open, then save again.",
    "G_PROJECT_FIELD": "{path}: {field} is missing or is not {expected}. Fix it in Advanced, or create the project again with New from a board.",
    "G_UNIT_HZ": "Hz",
    "G_UNIT_S": "s",
    "G_UNIT_MM": "mm",
    "G_UNIT_SUBSTRATE": "substrate heights",
    "G_UNIT_HENRY": "H",
    "G_UNIT_OHM": "Ω",
    "G_UNIT_FARAD": "F",
    "G_MENU_HELP": "Help",
    "G_ABOUT": "About kicad-rf-studio",
    "G_ABOUT_QT": "About Qt",
    "G_ABOUT_DEPENDENCY": "{name} {version}: {licence}",
    "G_NOT_INSTALLED": "not installed",
    "G_ABOUT_TEXT": "kicad-rf-studio {version}: simulates the RF parts of a KiCad board with openEMS.\n\nCopyright (C) 2026 the kicad-rf-studio contributors.\n\nThis program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program comes with ABSOLUTELY NO WARRANTY. It includes a copy of CSXCAD's SmoothMeshLines under the GNU Lesser General Public License, version 3 or later. Both licences are at https://www.gnu.org/licenses/.\n\nRuntime dependencies (installed by pip, or by you for openEMS and CSXCAD; not included):\n{dependencies}",
    "E_KICAD_UNREACHABLE": "Cannot reach KiCad: it was closed or restarted, or its API is off. In KiCad's PCB editor, with Preferences > Plugins > Enable KiCad API on, press the kicad-rf-studio button again.",
    "E_KICAD_BUSY": "KiCad stayed busy (a dialog, a tool or a zone fill is still open or running). Finish it in KiCad, then try again.",
    "E_KICAD_UNSUPPORTED": "This KiCad cannot answer a request the kicad-rf-studio button needs: the button needs KiCad 9.0.7 or later, or 10.x.",
    "E_KICAD_VERSION": "KiCad {version} is not supported: the kicad-rf-studio button needs KiCad 9.0.7 or later, or 10.x.",
    "E_KICAD_NO_BOARD": "KiCad's PCB editor has no saved board open. Open or save the board in KiCad's PCB editor, then press the kicad-rf-studio button again.",
    "E_HANDOFF_WRITE": "Cannot write {path}: {reason}. Check that this folder can be written, then press the kicad-rf-studio button again.",
    "E_GUI_START": "Cannot start {program}: {reason}. Install kicad-rf-studio again, then run kicad-rf-studio install-kicad-plugin.",
    "G_BUTTON_PLUGIN": "Simulates the RF parts of a KiCad board with openEMS.",
    "G_BUTTON_ACTION": "Opens kicad-rf-studio on this board, with the selected pads as the chain's start and end.",
    "I_PLUGIN_INSTALLED": "Installed the kicad-rf-studio button in {folder}.",
    "I_PLUGIN_NEXT": "One step is left, in KiCad: Preferences › Plugins › Enable KiCad API, then restart KiCad. The button then shows in the PCB editor's toolbar.",
    "I_PLUGIN_REMOVED": "Removed the kicad-rf-studio button from {folder}.",
    "I_PLUGIN_NONE": "There is no kicad-rf-studio button to remove under {folder}.",
    "E_NO_KICAD_FOLDER": "No KiCad 9.0 or 10.0 folder in {folder}: start KiCad once, so that it makes its folder there, or name the version with --kicad 9.0 or --kicad 10.0.",
    "E_PLUGIN_WRITE": "Cannot write or remove the kicad-rf-studio button in {path}: {reason}. Check that this folder can be written (Windows' Controlled folder access can block it), then run install-kicad-plugin again.",
    "E_PLUGIN_PYTHON": "This Python's path, {python}, has a character that launch.cmd cannot hold in the console's code page. Install kicad-rf-studio in a folder whose path has none, then run install-kicad-plugin again.",
    "G_SWAP": "Swap start and end",
    "G_HANDOFF_UNSAVED": "{board} as saved lacks a pad or a part selected in KiCad, which holds edits not yet saved: save the board in KiCad and press the button again.",
    "G_HANDOFF_PADS": "{count} pads are selected in KiCad. Select only the chain's two end pads and press the button again, or pick start and end here.",
    "G_REFILL": "Refill zones and save in KiCad",
    "G_REFILL_CONFIRM": "Refill every zone of {board} in KiCad, then save the board there? The save also writes every edit not yet saved in KiCad.",
    "G_REFILLING": "KiCad is refilling the zones and saving the board…",
    "G_REFILLED": "KiCad refilled the zones and saved {board}.",
    "E_KICAD_OTHER_BOARD": "KiCad has {open} open, not {board}, so nothing was refilled or saved. Open {board} in KiCad and press the kicad-rf-studio button again.",
    # T_: a word a message takes as a parameter, rendered with it (pt-BR design 5.1); no T_ template has a field
    "T_FILE_NOT_FOUND": "file not found",
    "T_NOT_A_FILE": "not a file",
    "T_PERMISSION_DENIED": "permission denied",
    "T_EXISTS_AS_FILE": "already exists as a file",
    "T_NOT_UTF8": "not UTF-8 text",
    "T_NOT_JSON": "not JSON",
    "T_CANNOT_READ": "cannot be read",
    "T_CANNOT_WRITE": "cannot be written",
    "T_CANNOT_START": "cannot be started",
    "T_CANNOT_MAKE": "cannot be made",
    "T_HOLDS_A_RUN": "already holds a run",
    "T_NOT_A_JSON_OBJECT": "not a JSON object",
    "T_JOB_SETUP": "setup",
    "T_JOB_XML": "xml",
    "T_JOB_CALIBRATION": "calibration",
    "T_JOB_FAR_FIELD": "far-field",
    "T_NONE": "none",
    "T_UNKNOWN": "unknown",
    "T_UNSET": "unset",
    "T_MISSING": "missing",
    "T_SOURCE_BOARD": "board",
    "T_HATCHED_ZONE": "hatched zone",
    "T_END_REFERENCE": "reference",
    "T_END_SIGNAL": "signal",
    "T_ON_EDGE": "on edge",
    "T_INSIDE_TOO_CLOSE": "inside too close",
    "T_OUTSIDE_CLOSER": "outside closer",
    "T_DIVERGED": "diverged",
    "T_GROWTH": "growth",
    "T_UNCLASSIFIED": "unclassified",
    "T_STOPPED": "stopped",
    "T_INSTALL_WINDOWS": "kicad-rf-studio setup-openems <openEMS folder>",
    "T_INSTALL_LINUX": "update_openEMS.sh <prefix> --python with this venv active (see README)",
    "T_EXPECT_TEXT": "text",
    "T_EXPECT_ABOVE_0": "a number above 0",
    "T_EXPECT_FLAG": "true or false",
    "T_EXPECT_TWO_NAMES": "two names",
    "T_EXPECT_CLASS": "a list of names, or null (computed from the board)",
    "T_EXPECT_ROLE": "port, copper, open, grid or curve_port",
    "T_EXPECT_MODEL": "null, or package (text) with esl_h, esr_ohm and cp_f (numbers of 0 or more)",
    "T_EXPECT_S2P": "null, or file (text) and connection (series or shunt)",
    "T_EXPECT_PARTS": "a list of parts",
    "T_EXPECT_WHOLE_ABOVE_0": "a whole number above 0",
    "T_EXPECT_PRESET": "draft, normal or strict",
    "T_EXPECT_MESH_N": "a whole number of 2 or more",
    "T_EXPECT_KIND": "mask, copper or dielectric",
    "T_EXPECT_0_OR_MORE": "a number of 0 or more",
    "T_EXPECT_ABOVE_0_OR_NULL": "a number above 0, or null",
    "T_EXPECT_0_OR_MORE_OR_NULL": "a number of 0 or more, or null",
    "T_EXPECT_LAYERS": "a list of layers",
    "T_EXPECT_LID_HEIGHT": 'a number above 0, or null ("lid": false leaves the lid out)',
    "T_EXPECT_LID": "true, false or null",
    "T_EXPECT_NAMES": "a list of names",
    "T_EXPECT_RULE": "connector, ic, copper or null",
    "T_EXPECT_REFERENCE": "a pad, a point or null",
    "T_EXPECT_PORTS": "a list of ports",
    "T_EXPECT_DT_FLOOR": "a number above 0 and at most 1",
    "T_EXPECT_OBJECT": "an object",
}


def _ui_language() -> int:
    """Windows' display language, a 16-bit LANGID (0x0416: Portuguese (Brazil)) masked out of ctypes' int result; 0
    elsewhere."""
    return ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0xFFFF if sys.platform == "win32" else 0


def _languages() -> list[str] | None:
    """gettext's languages (pt-BR design 4): None when LANGUAGE, LC_ALL, LC_MESSAGES or LANG is set and not empty,
    which gettext then reads itself; else ["pt_BR"] when Windows' display language is Portuguese (Brazil), and ["en"]
    for any other. Never the regional format, which is the wrong signal. One element only: a list such as
    ["en_US", "pt_BR"] makes gettext skip the missing English and load pt_BR."""
    if any(os.environ.get(name) for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")):
        return None
    # ponytail: one LANGID, Portuguese (Brazil)'s; another language adds its own here, or reads
    # GetUserPreferredUILanguages' names ("-" to "_")
    return ["pt_BR"] if _ui_language() == 0x0416 else ["en"]


_translation = gettext.translation("kicad_rf_studio", localedir=LOCALE, languages=_languages(), fallback=True)


def language() -> str:
    """The language the catalog speaks (pt-BR design 4), for Qt's translator and the tests: the loaded .mo's Language
    header, "en" without one."""
    # ponytail: the .mo's Language header names it (tools/catalog.py writes it from the .po's name); a .mo without one
    # reads as English
    return _translation.info().get("language", "en")


def _render(translation, code: str, params: dict) -> str:
    """`code`'s template from `translation`, filled with `params`; a parameter that is a T_ code of CATALOG is shown as
    that term from `translation`, and None as T_UNKNOWN's (pt-BR design 5.1)."""
    # ponytail: a parameter equal to a T_ code renders as that term (a net named T_NONE would): design 5.1's accepted
    # limit
    def shown(value):
        value = "T_UNKNOWN" if value is None else value
        term = isinstance(value, str) and value.startswith("T_") and value in CATALOG
        return translation.gettext(CATALOG[value]) if term else value

    return translation.gettext(CATALOG[code]).format(**{name: shown(value) for name, value in params.items()})


def render(code: str, **params) -> str:
    """The message for `code` in the user's language, its T_ parameters too; English when there is no translation."""
    return _render(_translation, code, params)


def english(code: str, **params) -> str:
    """The message for `code` in English whatever the language, its T_ parameters too: the button helper's line, which
    KiCad 10 shows decoded in a code page nobody has checked (pt-BR design 5.4), and chain.s2p's what-if line, in an
    ASCII file (5.3)."""
    return _render(gettext.NullTranslations(), code, params)


# The `reason` of E_BOARD_UNREADABLE, E_PROJECT_UNREADABLE, E_SETTINGS_UNREADABLE, E_OUTPUT_PATH (and G_OUTPUT_PATH, its
# GUI wording), E_RESULTS_WRITE, E_RUN_DIR, E_HANDOFF_WRITE, E_GUI_START, E_PLUGIN_WRITE, G_START_FAILED and
# G_SAVE_FAILED, by the class of the error. Never the system's own message: it is long, in the system's language, and a
# UnicodeDecodeError's repr holds every byte of the file. NotADirectoryError is a file where a folder of the path
# should be.
_REASONS = ((FileNotFoundError, "T_FILE_NOT_FOUND"), (IsADirectoryError, "T_NOT_A_FILE"),
            (PermissionError, "T_PERMISSION_DENIED"), ((FileExistsError, NotADirectoryError), "T_EXISTS_AS_FILE"),
            (UnicodeError, "T_NOT_UTF8"), (json.JSONDecodeError, "T_NOT_JSON"))


def reason(error: Exception, fallback: str = "T_CANNOT_READ") -> str:
    """The T_ code of a short phrase for an OSError, a UnicodeError or a JSON error met reading or writing a file;
    `fallback`, a T_ code, for any other error."""
    return next((code for kind, code in _REASONS if isinstance(error, kind)), fallback)


def detail(error: Exception) -> str:
    """E_INTERNAL's detail: the class and message of `error` on one line, never its repr, which can hold a file, cut
    to 200 characters."""
    text = " ".join(f"{type(error).__name__}: {error}".split())
    return text if len(text) <= 200 else text[:199] + "…"


class KrsError(Exception):
    """An error the user is told about; `str(err)` is the rendered message."""

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params

    def __str__(self) -> str:
        return render(self.code, **self.params)
