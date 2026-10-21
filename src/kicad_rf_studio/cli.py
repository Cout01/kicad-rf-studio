# SPDX-License-Identifier: GPL-3.0-or-later
"""The command line. `new` reads a board, traces the RF chain between two pads and writes project.json, which it never
replaces. `cost` prints the 2D Z0 and εeff of the measured nets' straight sections (plan 3 adds the setup-only run
after them). `setup-openems` installs openEMS from the official Windows package into this Python. There is no help=
text: every string a user sees is a code in core.messages, and argparse itself writes the usage line."""
import argparse
import math
import os
import sys
from pathlib import Path

from kicad_rf_studio import runs
from kicad_rf_studio.core.kicad import choose_reference, classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.stackup import preset as stackup_preset
from kicad_rf_studio.core.kicad.tracer import signal_layer
from kicad_rf_studio.core.kicad.values import parse_frequency
from kicad_rf_studio.core.messages import KrsError, reason, render
from kicad_rf_studio.core.project import (BAND_FACTOR, DEFAULT_PRESET, EXPAND_H, HARMONICS, MESH_N, T_MAX_S,
                                          board_file, board_hash, load_project, make_project, save_project)

PRESETS = ("draft", "normal", "strict")  # the run presets; `--stackup` names a stackup preset, which is another thing


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


def _part_note(part: dict) -> tuple[str, dict]:
    """A part as I_PART prints it, or I_PART_NO_MODEL for one with no package preset."""
    named, model = {"ref": part["ref"], "value": part["value"], "role": part["role"]}, part["model"]
    if model is None:
        return "I_PART_NO_MODEL", named
    return "I_PART", {**named, "package": model["package"], "esl_nh": f"{model['esl_h'] * 1e9:g}",
                      "esr_ohm": f"{model['esr_ohm']:g}"}


def _reference(ref) -> dict | None:
    """A port's reference as project.json keeps it: a pad, a point on a layer, or None. The point is in KiCad's frame,
    y down, as project.py says."""
    if ref is None:
        return None
    if ref.rule == "copper":
        x, y = ref.point
        return {"point": [x, 0.0 - y], "layer": ref.layer}  # 0.0 - y keeps a zero from becoming -0.0
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
    """Board, stackup, z-stack, classes, chain, ports, region, parts and lid, then project.json and the summary: every
    refusal (E_STACKUP_LAYERS, E_DIELECTRIC_THICKNESS, E_CHAIN_OFF_OUTLINE among them) comes before anything is
    written (C-44)."""
    # imported here, as in `cost`: the CLI adds no work at import time
    from kicad_rf_studio.core.geometry.lid import find_lid
    from kicad_rf_studio.core.geometry.region import band, build_region
    from kicad_rf_studio.core.geometry.zstack import zstack
    from kicad_rf_studio.core.model.parts import project_parts

    board = load_board(a.board)
    named = a.stackup is not None  # an empty --stackup is a name too, and an unknown one
    stackup = stackup_preset(a.stackup, board.thickness, len(board.copper_layers)) if named else board.stackup
    if stackup is None or stackup.dielectric_thickness() <= 0:  # no stackup, or none that leaves a dielectric
        raise KrsError("E_NO_STACKUP")
    zs = zstack(stackup, board.copper_layers)
    classes = classify(board)
    chain = trace_chain(board, a.start, a.end, classes)
    ports = []
    for n, signal in enumerate((a.start, a.end), 1):
        ref = choose_reference(board, classes, signal)
        sig = next(p for p in board.pads(signal) if p.layers)  # the pad trace_chain resolved: the first with copper
        ports.append({"name": f"P{n}", "signal": signal, "signal_uuid": sig.uuid, "layer": signal_layer(board, sig),
                      "rule": ref and ref.rule, "reference": _reference(ref)})
    f1, f2 = band({"f0_hz": a.f0, "harmonics": a.harmonics, "band_factor": BAND_FACTOR})
    region = build_region(board, chain, ports, zs, f2, EXPAND_H)
    series, shunt, others, part_notes = project_parts(board, chain, classes, region.roi, f1, f2)
    _, gate = find_lid(board, classes, region, zs,
                       {"harmonics": a.harmonics, "lid": None, "lid_height_mm": a.lid_height})
    folder, other_drive = Path(a.output or "."), False
    try:
        board_path = Path(os.path.relpath(a.board, folder)).as_posix()
    except ValueError:  # relpath cannot cross drives
        board_path, other_drive = Path(a.board).absolute().as_posix(), True
    project = make_project(
        board_path, board_hash(a.board), a.f0, stackup, classes,
        {"start": chain.start, "end": chain.end, "nets": list(chain.nets), "series": series, "shunt": shunt}, others,
        ports, harmonics=a.harmonics, preset=a.preset, lid_height_mm=a.lid_height)
    target = folder / "project.json"
    try:
        if target.exists():  # it may hold the hand edits that W_NO_REFERENCE and W_LID_HEIGHT_MISSING ask for
            raise KrsError("E_PROJECT_EXISTS", path=str(target))
        folder.mkdir(parents=True, exist_ok=True)
        save_project(target, project)
    except OSError as e:  # the path the error names (the folder, a file in the way, the file written), else target
        raise KrsError("E_OUTPUT_PATH", path=str(e.filename or target), reason=reason(e)) from None

    c = project["classes"]
    dielectric = next(x for x in stackup.layers if x.kind == "dielectric")  # there is one: its thickness is above 0
    mask = next((x for x in stackup.layers if x.kind == "mask"), None)  # the top one; a stackup may have none
    notes = [*board.warnings, ("W_FILLS_AS_SAVED", {}),
             ("I_STACKUP", {"source": stackup.source, "thickness_mm": f"{stackup.dielectric_thickness():g}",
                            "epsilon_r": dielectric.epsilon_r, "mask_mm": f"{mask.thickness:g}" if mask else "none",
                            "mask_epsilon_r": mask.epsilon_r if mask else "none"}),
             ("I_CLASSES", {"gnd": _list(c["gnd_nets"]), "power": _list(c["power_nets"]),
                            "connectors": _list(c["connectors"]), "shields": _list(c["shields"])}),
             ("I_CHAIN", {"start": chain.start, "end": chain.end, "series": _list(p.ref for p in chain.series),
                          "shunt": _list(p.ref for p in chain.shunt)}),
             *map(_part_note, series + shunt + others),
             *(("I_PORT", {"name": p["name"], "signal": p["signal"], "reference": _shown(p["reference"]),
                           "rule": p["rule"] or "none"}) for p in ports),
             ("I_F0", {"f0_mhz": f"{a.f0 / 1e6:g}", "harmonics": a.harmonics}),
             ("I_DEFAULTS", {"preset": a.preset, "band_factor": BAND_FACTOR, "t_max_ns": f"{T_MAX_S * 1e9:g}",
                             "harmonics": a.harmonics, "mesh_n": MESH_N[a.preset], "expand_h": f"{EXPAND_H:g}"}),
             ("I_LID", {"state": "on" if a.harmonics > 1 else "off"})]
    if heavy := stackup.nonstandard_copper():
        notes.append(("W_COPPER_WEIGHT", {"layers": _list(heavy)}))
    # what `run` refuses (E_LID_HEIGHT) is a warning here: lid_height_mm can still be set in project.json
    notes += [("W_LID_HEIGHT_MISSING", params) for code, params in gate if code == "E_LID_HEIGHT"]
    notes += part_notes  # W_VALUE_UNREADABLE (DNP parts too), W_PART_OPEN
    notes += [("W_NO_REFERENCE", {"signal": p["signal"]}) for p in ports if p["reference"] is None]
    if not 1e6 <= a.f0 <= 1e11:  # a bare --f0 915 is 915 Hz
        notes.append(("W_F0_RANGE", {"f0_hz": f"{a.f0:g}"}))
    if other_drive:
        notes.append(("W_ABSOLUTE_BOARD_PATH", {}))
    notes.append(("I_WROTE", {"path": target}))
    for code, params in notes:
        print(render(code, **params))


def _cost(a: argparse.Namespace) -> None:
    """The 2D readout (spec 3.2): each measured section solved on cs2d's own grid without and with the exact mask of
    its own side (none on inner copper), in chain-net order and then by place, or W_2D_SHORT in its place where other
    copper touches the line at its cut; then the board's warnings and the geometry's notes, gate entries included,
    which `run` blocks on. No mesh and no worker."""
    # imported here, as in `new`: the CLI adds no work at import time
    from kicad_rf_studio.core.cs2d import ShortError, solve
    from kicad_rf_studio.core.geometry import build_geometry
    from kicad_rf_studio.core.geometry.sections import cross_section

    path = Path(a.project)
    project = load_project(path)
    board = load_board(board_file(path, project))
    geom = build_geometry(board, project)
    print(render("I_2D_HEADER" if geom.sections else "W_NO_SECTIONS"))
    for s in geom.sections:
        named = {"net": s.net, "layer": s.layer, "width_mm": f"{s.width:.3f}", "length_mm": f"{s.length:.3f}"}
        try:
            bare, coated = [solve(cross_section(s, geom.pieces, geom.zs, geom.masks.get(s.layer), m))
                            for m in ("none", "exact")]
        except ShortError:  # another net's copper (E_SHORT_IN_ROI) or copper with none, which no check reports
            print(render("W_2D_SHORT", **named))
            continue
        print(render("I_2D_SECTION", **named, gap_mm="none" if s.gap is None else f"{s.gap:.3f}", z0=f"{bare.z0:.2f}",
                     eeff=f"{bare.eps_eff:.3f}", z0_mask=f"{coated.z0:.2f}", eeff_mask=f"{coated.eps_eff:.3f}"))
    for code, params in [*board.warnings, *geom.notes]:
        print(render(code, **params))


def _setup_openems(a: argparse.Namespace) -> None:
    for code, params in runs.setup_openems(a.folder):
        print(render(code, **params))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kicad-rf-studio")
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new")
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
    cost = commands.add_parser("cost")
    cost.add_argument("project")
    cost.set_defaults(func=_cost)
    setup = commands.add_parser("setup-openems")
    setup.add_argument("folder", type=Path, metavar="DIR")
    setup.set_defaults(func=_setup_openems)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # I_STACKUP's ε and I_CHAIN's → are not in cp1252
        if hasattr(stream, "reconfigure"):  # a StringIO, say, has none and needs none
            stream.reconfigure(errors="replace")
    try:
        args = _parser().parse_args(argv)
        args.func(args)
    except KrsError as e:
        print(e, file=sys.stderr)
        return 2
    except Exception as e:
        detail = " ".join(f"{type(e).__name__}: {e}".split())  # on one line, and never the repr, which can hold a file
        print(render("E_INTERNAL", detail=detail if len(detail) <= 200 else detail[:199] + "…"), file=sys.stderr)
        return 1
    return 0
