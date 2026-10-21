# SPDX-License-Identifier: GPL-3.0-or-later
"""Every string a user can see is a code in CATALOG plus parameters. The English template is the
gettext msgid, so a translation is a catalog file under kicad_rf_studio/locale."""
import gettext
import json
from pathlib import Path

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
    "W_STAIRCASED": "Net {net} has copper that is not axis-aligned (45° segments or arcs); it is staircased and its accuracy is not validated. For a validated result, route it with horizontal and vertical tracks.",
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
    "I_CLASSES": "GND nets: {gnd}. Power nets: {power}. Connectors: {connectors}. Shields: {shields}.",
    "I_CHAIN": "Chain {start} → {end}: series {series}; shunt {shunt}.",
    "I_PART": "Part {ref} {value}: {role}; package {package}, ESL {esl_nh} nH, ESR {esr_ohm} Ω.",
    "I_PART_NO_MODEL": "Part {ref} {value}: {role}; no package preset, so `retune` uses its ideal value.",
    "I_PORT": "Port {name}: signal {signal}, reference {reference} ({rule}).",
    "I_F0": "f0 {f0_mhz} MHz, with {harmonics} harmonics.",
    "I_DEFAULTS": "Preset {preset} (provisional default), band factor {band_factor}, T_max {t_max_ns} ns, harmonics {harmonics}, mesh n {mesh_n}, region {expand_h} substrate heights past the chain.",
    "I_LID": "Shield lid {state}: \"lid\": null in project.json means on when harmonics > 1; true or false forces it.",
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
    "E_ROTATED_PART": "Part {ref} is not at a multiple of 90°, so its port would be a CurvePort, which P0-B has not validated. Rotate it in KiCad, or set \"allow_curve_port\": true in project.json at your own risk.",
    "E_PORT_SPANS": "Port {name}: its two pads face each other neither along x nor along y, so no box joins them. Choose a reference straight across from the signal pad in project.json.",
    "E_PORT_BOX": "Port {name}: no mesh line lies inside its pads, so its box cannot sit on them. Set mesh.n to 3 in project.json, or use larger pads.",
    "E_PART_VALUE": "Part {ref} is in the grid but its value \"{value}\" cannot be read. Fix its value in project.json, or set its role to \"open\" or \"port\".",
    "E_GRID_KIND": "Part {ref} cannot sit in the grid: only a C or an R can. Set its role to \"port\" or \"open\" in project.json.",
    "E_LOCKED": "Another run of this project has been running since {started} in {run}. Wait for it, or create a file named STOP in that folder to stop it; if no run is going on, delete {lock}.",
    "W_STALE_LOCK": "Reclaimed {lock}: the run in {run} ended without releasing it.",
    "E_OPENEMS_DLL": "openEMS could not load its libraries (CSXCAD_INSTALL_PATH is {value}). Run setup-openems again, or set CSXCAD_INSTALL_PATH to the openEMS folder.",
    "E_SETUP_FAILED": "openEMS could not set up the model; see {log}. Look at the model with `preview`.",
    "E_WORKER_FAILED": "The {job} worker ended with code {exit_code}; see {log}. Report it if the log shows no cause.",
    "I_CALIBRATING": "Measuring this machine's simulation speed, once (20–30 s)…",
    "I_CALIBRATED": "Calibrated: {pool} jobs at once with {threads} threads each, {speed} MC/s in all; `kicad-rf-studio calibrate` measures again.",
    "E_INTERNAL": "Internal error: {detail}. Please report it.",
}

_translation = gettext.translation(
    "kicad_rf_studio", localedir=Path(__file__).resolve().parents[1] / "locale", fallback=True)


def render(code: str, **params) -> str:
    """The message for `code` in the user's language; English when there is no translation."""
    return _translation.gettext(CATALOG[code]).format(**params)


# The `reason` of E_BOARD_UNREADABLE, E_PROJECT_UNREADABLE, E_SETTINGS_UNREADABLE and E_OUTPUT_PATH, by the class of
# the error. Never the system's own message: it is long, in the system's language, and a UnicodeDecodeError's repr
# holds every byte of the file. NotADirectoryError is a file where a folder of the path should be.
_REASONS = ((FileNotFoundError, "file not found"), (IsADirectoryError, "not a file"),
            (PermissionError, "permission denied"), ((FileExistsError, NotADirectoryError), "already exists as a file"),
            (UnicodeError, "not UTF-8 text"), (json.JSONDecodeError, "not JSON"))


def reason(error: Exception) -> str:
    """A short English phrase for an OSError, a UnicodeError or a JSON error met reading or writing a file."""
    return next((text for kind, text in _REASONS if isinstance(error, kind)), "cannot be read")


class KrsError(Exception):
    """An error the user is told about; `str(err)` is the rendered message."""

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params

    def __str__(self) -> str:
        return render(self.code, **self.params)
