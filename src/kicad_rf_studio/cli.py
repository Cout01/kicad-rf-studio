# SPDX-License-Identifier: GPL-3.0-or-later
"""The command line. `new` reads a board, traces the RF chain between two pads and writes project.json. There is no
help= text: every string a user sees is a code in core.messages, and argparse itself writes the usage line."""
import argparse
import math
import os
import sys
from pathlib import Path

from kicad_rf_studio.core.kicad import choose_reference, classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.stackup import preset as stackup_preset
from kicad_rf_studio.core.kicad.values import parse_frequency
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.project import SCHEMA, board_hash, save_project

PRESETS = ("draft", "normal", "strict")  # the run presets; `--stackup` names a stackup preset, which is another thing
# ponytail: provisional constants, the same for every preset; the owner sets the time policy (spec 1.1) after P0-C.
DEFAULT_PRESET, HARMONICS, BAND_FACTOR, T_MAX_S = "normal", 3, 1.1, 40e-9


def _positive(kind):
    """An argparse type: a `kind` above zero and finite (NaN fails the comparison too)."""
    def convert(text):
        value = kind(text)
        if not 0 < value < math.inf:
            raise ValueError(text)
        return value
    convert.__name__ = f"positive {kind.__name__}"  # argparse says: invalid positive int value: '0'
    return convert


def _list(names) -> str:
    return ", ".join(names) or "none"


def _part(board, part) -> dict:
    value = board.footprints[part.ref].value
    return {"ref": part.ref, "pads": list(part.pads), "nets": list(part.nets), "value": value}


def _reference(ref) -> dict | None:
    """A port's reference as project.json keeps it: a pad, a point on a layer, or None."""
    if ref is None:
        return None
    if ref.rule == "copper":
        return {"point": list(ref.point), "layer": ref.layer}
    return {"pad": ref.pad, "uuid": ref.uuid}


def _shown(ref: dict | None) -> str:
    """A stored reference as I_PORT prints it."""
    if ref is None:
        return "none"
    if "pad" in ref:
        return ref["pad"]
    x, y = ref["point"]
    return f"({x:.3f}, {y:.3f}) on {ref['layer']}"


def _new(a: argparse.Namespace) -> None:
    if not Path(a.board).is_file():
        raise KrsError("E_NOT_A_BOARD", path=a.board)
    board = load_board(a.board)
    named = a.stackup is not None  # an empty --stackup is a name too, and an unknown one
    stackup = stackup_preset(a.stackup, board.thickness, len(board.copper_layers)) if named else board.stackup
    if stackup is None or stackup.dielectric_thickness() <= 0:  # no stackup, or none that leaves a dielectric
        raise KrsError("E_NO_STACKUP")
    classes = classify(board)
    chain = trace_chain(board, a.start, a.end, classes)
    ports = []
    for n, signal in enumerate((a.start, a.end), 1):
        ref = choose_reference(board, classes, signal)
        ports.append({"name": f"P{n}", "signal": signal, "rule": ref and ref.rule, "reference": _reference(ref)})
    folder, other_drive = Path(a.output or "."), False
    try:
        board_path = Path(os.path.relpath(a.board, folder)).as_posix()
    except ValueError:  # relpath cannot cross drives
        board_path, other_drive = Path(a.board).absolute().as_posix(), True
    project = {
        "schema": SCHEMA,
        "board": {"path": board_path, "sha256": board_hash(a.board)},
        "f0_hz": a.f0, "harmonics": a.harmonics, "preset": a.preset, "band_factor": BAND_FACTOR, "t_max_s": T_MAX_S,
        "stackup": stackup.to_json(),
        "lid_height_mm": a.lid_height,
        # the sets as computed: classify() reads back any list that is present, even an empty one, as a replacement
        "classes": {"gnd_nets": sorted(classes.gnd), "power_nets": sorted(classes.power),
                    "connectors": sorted(classes.connectors), "shields": sorted(classes.shields)},
        "chain": {"start": chain.start, "end": chain.end, "nets": list(chain.nets),
                  "series": [_part(board, p) for p in chain.series], "shunt": [_part(board, p) for p in chain.shunt]},
        "ports": ports}
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "project.json"
    # ponytail: replaces a project.json that is already there, hand edits and all; refuse, or add --force, if that bites
    save_project(target, project)

    c = project["classes"]
    dielectric = next(x for x in stackup.layers if x.kind == "dielectric")  # there is one: its thickness is above 0
    notes = [*board.warnings, ("W_FILLS_AS_SAVED", {}),
             ("I_STACKUP", {"source": stackup.source, "thickness_mm": f"{stackup.dielectric_thickness():g}",
                            "epsilon_r": dielectric.epsilon_r}),
             ("I_CLASSES", {"gnd": _list(c["gnd_nets"]), "power": _list(c["power_nets"]),
                            "connectors": _list(c["connectors"]), "shields": _list(c["shields"])}),
             ("I_CHAIN", {"start": chain.start, "end": chain.end, "series": _list(p.ref for p in chain.series),
                          "shunt": _list(p.ref for p in chain.shunt)}),
             *(("I_PORT", {"name": p["name"], "signal": p["signal"], "reference": _shown(p["reference"]),
                           "rule": p["rule"] or "none"}) for p in ports),
             ("I_DEFAULTS", {"preset": a.preset, "band_factor": BAND_FACTOR, "t_max_ns": f"{T_MAX_S * 1e9:g}",
                             "harmonics": a.harmonics})]
    if heavy := stackup.nonstandard_copper():
        notes.append(("W_COPPER_WEIGHT", {"layers": _list(heavy)}))
    if c["shields"] and a.lid_height is None:
        notes.append(("W_LID_HEIGHT_MISSING", {"refs": _list(c["shields"])}))
    notes += [("W_NO_REFERENCE", {"signal": p["signal"]}) for p in ports if p["reference"] is None]
    if other_drive:
        notes.append(("W_ABSOLUTE_BOARD_PATH", {}))
    notes.append(("I_WROTE", {"path": target}))
    for code, params in notes:
        print(render(code, **params))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kicad-rf-studio")
    new = parser.add_subparsers(dest="command", required=True).add_parser("new")
    new.add_argument("board")
    new.add_argument("--start", required=True, metavar="REF.PAD")
    new.add_argument("--end", required=True, metavar="REF.PAD")
    new.add_argument("--f0", required=True, type=parse_frequency, metavar="F")
    new.add_argument("--harmonics", type=_positive(int), default=HARMONICS, metavar="N")
    new.add_argument("--preset", choices=PRESETS, default=DEFAULT_PRESET)
    new.add_argument("--stackup", metavar="NAME")
    new.add_argument("--lid-height", type=_positive(float), metavar="MM")
    new.add_argument("-o", dest="output", metavar="PATH")
    new.set_defaults(func=_new)
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(errors="replace")  # I_STACKUP's ε and I_CHAIN's → are not in cp1252
    sys.stderr.reconfigure(errors="replace")
    try:
        args = _parser().parse_args(argv)
        args.func(args)
    except KrsError as e:
        print(e, file=sys.stderr)
        return 2
    except Exception as e:
        print(render("E_INTERNAL", detail=" ".join(repr(e).split())), file=sys.stderr)  # the repr, on one line
        return 1
    return 0
