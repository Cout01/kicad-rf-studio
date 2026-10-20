# SPDX-License-Identifier: GPL-3.0-or-later
"""Every string a user can see is a code in CATALOG plus parameters. The English template is the
gettext msgid, so a translation is a catalog file under kicad_rf_studio/locale."""
import gettext
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
    "W_NETLESS_COPPER": "Copper shape {uuid} on {layer} has no net and is simulated as floating copper.",
    "W_PADSTACK": "Pad {pad} uses a per-layer padstack; its front shape is used on every layer.",
    "W_DUPLICATE_REF": "Footprints share the references {refs}; the copies were renamed with #2, #3 and so on. Annotate the board in KiCad to name them.",
    "E_BAD_FREQUENCY": 'Cannot read the frequency "{text}". Write it like 915MHz.',
    "E_UNKNOWN_PRESET": 'Unknown stackup preset "{name}". Known presets: {known}.',
    "E_DEFAULT_RULE_LAYERS": "Stackup presets are implemented for 2 copper layers, and this board has {count}. Add the stackup to the board in KiCad.",
    "W_COPPER_WEIGHT": "Copper layers {layers} are not 35 µm; the mesh rule is not validated for this copper weight.",
    "E_NO_STACKUP": "The board has no stackup. Give --stackup jlcpcb-2l, or --stackup kicad-default to accept KiCad's default rule.",
    "E_UNKNOWN_PAD": "Pad {name} does not exist. Closest pads: {candidates}.",
    "E_AMBIGUOUS_PAD": "Pads named {name} sit on different nets ({nets}). Name a pad with a unique number.",
    "E_START_ON_GND": 'Pad {name} is on net "{net}", which is GND, power or no net; a chain cannot start or end there.',
    "E_SAME_PADS": "The chain starts and ends at the same pad, {name}. Give two different pads.",
    "E_NO_CHAIN": "No chain from {start} to {end}: the walk stopped at nets {reached}. A DNP part, a connector, a shield, a GND or power net, or a part with three or more pads is in the way.",
    "E_PROJECT_SCHEMA": "{path} uses project schema {found}; this version reads schema {expected}.",
    "E_OUTPUT_PATH": "Cannot write {path}: {reason}. Choose another -o folder.",
    "E_PROJECT_EXISTS": "{path} already exists. Delete it, or give another -o folder.",
    "I_STACKUP": "Stackup: {source}, dielectric {thickness_mm} mm, εr {epsilon_r}; mask {mask_mm} mm, εr {mask_epsilon_r}.",
    "I_CLASSES": "GND nets: {gnd}. Power nets: {power}. Connectors: {connectors}. Shields: {shields}.",
    "I_CHAIN": "Chain {start} → {end}: series {series}; shunt {shunt}.",
    "I_PORT": "Port {name}: signal {signal}, reference {reference} ({rule}).",
    "I_F0": "f0 {f0_mhz} MHz, with {harmonics} harmonics.",
    "I_DEFAULTS": "Preset {preset} (provisional default), band factor {band_factor}, T_max {t_max_ns} ns, harmonics {harmonics}.",
    "W_FILLS_AS_SAVED": "Fills as saved — refill (B) in KiCad and save if you changed copper.",
    "W_LID_HEIGHT_MISSING": "Shield {refs} found but no --lid-height was given; `run` will refuse until project.json has lid_height_mm.",
    "W_VALUE_UNREADABLE": "Cannot read the value of {refs}. Write values like 4.7pF, 4p7 or 15nH.",
    "W_F0_RANGE": "f0 = {f0_hz} Hz is outside 1 MHz to 100 GHz. Did you forget the unit, as in 915MHz?",
    "W_NO_REFERENCE": "No reference found for {signal}; set it in project.json before `run`.",
    "W_ABSOLUTE_BOARD_PATH": "The board is on another drive, so project.json stores its absolute path.",
    "I_WROTE": "Wrote {path}.",
    "E_INTERNAL": "Internal error: {detail}. Please report it.",
}

_translation = gettext.translation(
    "kicad_rf_studio", localedir=Path(__file__).resolve().parents[1] / "locale", fallback=True)


def render(code: str, **params) -> str:
    """The message for `code` in the user's language; English when there is no translation."""
    return _translation.gettext(CATALOG[code]).format(**params)


# The `reason` of E_BOARD_UNREADABLE and E_OUTPUT_PATH, by the class of the error. Never the system's own message: it
# is long, in the system's language, and a UnicodeDecodeError's repr holds every byte of the file. NotADirectoryError
# is a file where a folder of the path should be.
_REASONS = ((FileNotFoundError, "file not found"), (IsADirectoryError, "not a file"),
            (PermissionError, "permission denied"), ((FileExistsError, NotADirectoryError), "already exists as a file"),
            (UnicodeError, "not UTF-8 text"))


def reason(error: Exception) -> str:
    """A short English phrase for an OSError or a UnicodeError met reading or writing a file."""
    return next((text for kind, text in _REASONS if isinstance(error, kind)), "cannot be read")


class KrsError(Exception):
    """An error the user is told about; `str(err)` is the rendered message."""

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params

    def __str__(self) -> str:
        return render(self.code, **self.params)
