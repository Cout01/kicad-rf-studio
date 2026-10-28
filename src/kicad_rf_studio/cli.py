# SPDX-License-Identifier: GPL-3.0-or-later
"""The command line. `new` reads a board, traces the RF chain between two pads and writes project.json, which it never
replaces. `cost` prints the 2D Z0 and εeff of the measured nets' straight sections, then runs openEMS's setup-only
gate and prints the cost (pipeline.cost). `run` runs the gates and one job per port under the stop rule; only when
every job kept S does it replace the results in project.json and write the outputs to results/ (pipeline.run).
`retune` stores new part values or S2P files and writes results/ again from the last run's waves, with no new run
(pipeline.retune). `verify` runs once more with every part port in the grid at its ideal value, and compares that with
a retune at the same values (pipeline.verify). `preview` has a worker write the model's model.xml and opens it in
AppCSXCAD (pipeline.preview).
`setup-openems` installs openEMS from the official Windows package into this Python, and `calibrate` measures this
machine's simulation speed. `cost`, `run` and `verify` take `--run-dir DIR`, the run folder to use instead of a new
one in the data folder (Stage 2's GUI gives it, design 5.2): made before the command, and refused with E_RUN_DIR when it
cannot be made or already holds a run. Their run folder, once it exists, ends with an end event (I_END) however the
command ends, after a message event for a refusal or an internal error that main caught (A-13). A command returns its
exit code, None for 0. There is no help= text: every string a user sees is a code in core.messages, and argparse
itself writes the usage line."""
import argparse
import contextlib
import math
import sys
from pathlib import Path

from kicad_rf_studio import runs
from kicad_rf_studio.core.kicad import choose_reference, classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.stackup import preset as stackup_preset
from kicad_rf_studio.core.kicad.tracer import signal_layer
from kicad_rf_studio.core.kicad.values import parse_frequency
from kicad_rf_studio.core.messages import KrsError, detail, reason, render
from kicad_rf_studio.core.project import (BAND_FACTOR, DEFAULT_PRESET, EXPAND_H, HARMONICS, MARGIN_SCALE, MESH_N,
                                          REACH_H, T_MAX_S, board_hash, make_project, relative_path, save_project,
                                          shown_reference)

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


def new(board: str | Path, start: str, end: str, f0: float, *, harmonics: int = HARMONICS,
        preset: str = DEFAULT_PRESET, stackup: str | None = None, lid_height: float | None = None,
        output: str | Path | None = None) -> tuple[Path, list[tuple[str, dict]]]:
    """Board, stackup, z-stack, classes, chain, ports, region, parts and lid, then project.json: every refusal
    (E_STACKUP_LAYERS, E_DIELECTRIC_THICKNESS, E_CHAIN_OFF_OUTLINE among them) comes before anything is written
    (C-44). Returns project.json's path and the summary as (code, params) notes, I_WROTE last, which the `new` command
    prints and Stage 2's GUI shows (design 5.2); prints nothing. `f0` is in Hz, `lid_height` in mm, `output`
    project.json's folder (the working one when None) and `stackup` a stackup preset's name (None: the board's own)."""
    # imported here, as in `cost`: the CLI adds no work at import time
    from kicad_rf_studio.core.geometry.lid import find_lid
    from kicad_rf_studio.core.geometry.region import band, build_region
    from kicad_rf_studio.core.geometry.zstack import zstack
    from kicad_rf_studio.core.model.parts import project_parts

    board = load_board(board)
    named = stackup is not None  # an empty --stackup is a name too, and an unknown one
    stackup = stackup_preset(stackup, board.thickness, len(board.copper_layers)) if named else board.stackup
    if stackup is None or stackup.dielectric_thickness() <= 0:  # no stackup, or none that leaves a dielectric
        raise KrsError("E_NO_STACKUP")
    zs = zstack(stackup, board.copper_layers)
    classes = classify(board)
    chain = trace_chain(board, start, end, classes)
    ports = []
    for n, signal in enumerate((start, end), 1):
        ref = choose_reference(board, classes, signal)
        sig = next(p for p in board.pads(signal) if p.layers)  # the pad trace_chain resolved: the first with copper
        ports.append({"name": f"P{n}", "signal": signal, "signal_uuid": sig.uuid, "layer": signal_layer(board, sig),
                      "rule": ref and ref.rule, "reference": _reference(ref)})
    f1, f2 = band({"f0_hz": f0, "harmonics": harmonics, "band_factor": BAND_FACTOR})
    region = build_region(board, chain, ports, zs, f2, EXPAND_H)
    series, shunt, others, part_notes = project_parts(board, chain, classes, region.roi, f1, f2)
    _, gate = find_lid(board, classes, region, zs,
                       {"harmonics": harmonics, "lid": None, "lid_height_mm": lid_height})
    folder = Path(output or ".")
    board_path, other_drive = relative_path(board.path, folder)
    project = make_project(
        board_path, board_hash(board.path), f0, stackup, classes,
        {"start": chain.start, "end": chain.end, "nets": list(chain.nets), "series": series, "shunt": shunt}, others,
        ports, harmonics=harmonics, preset=preset, lid_height_mm=lid_height)
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
             *(("I_PORT", {"name": p["name"], "signal": p["signal"], "reference": shown_reference(p["reference"]),
                           "rule": p["rule"] or "none"}) for p in ports),
             ("I_F0", {"f0_mhz": f"{f0 / 1e6:g}", "harmonics": harmonics}),
             ("I_DEFAULTS", {"preset": preset, "band_factor": BAND_FACTOR, "t_max_ns": f"{T_MAX_S * 1e9:g}",
                             "harmonics": harmonics, "mesh_n": MESH_N[preset], "expand_h": f"{EXPAND_H:g}",
                             "margin_scale": f"{MARGIN_SCALE:g}", "reach_h": f"{REACH_H:g}"}),
             ("I_LID", {"state": "on" if harmonics > 1 else "off"})]
    if heavy := stackup.nonstandard_copper():
        notes.append(("W_COPPER_WEIGHT", {"layers": _list(heavy)}))
    # what `run` refuses (E_LID_HEIGHT) is a warning here: lid_height_mm can still be set in project.json
    notes += [("W_LID_HEIGHT_MISSING", params) for code, params in gate if code == "E_LID_HEIGHT"]
    notes += part_notes  # W_VALUE_UNREADABLE (DNP parts too), W_PART_OPEN
    notes += [("W_NO_REFERENCE", {"signal": p["signal"]}) for p in ports if p["reference"] is None]
    if not 1e6 <= f0 <= 1e11:  # a bare --f0 915 is 915 Hz
        notes.append(("W_F0_RANGE", {"f0_hz": f"{f0:g}"}))
    if other_drive:
        notes.append(("W_ABSOLUTE_BOARD_PATH", {}))
    notes.append(("I_WROTE", {"path": target}))
    return target, notes


def _new(a: argparse.Namespace) -> None:
    _, notes = new(a.board, a.start, a.end, a.f0, harmonics=a.harmonics, preset=a.preset, stackup=a.stackup,
                   lid_height=a.lid_height, output=a.output)
    for code, params in notes:
        print(render(code, **params))


def _cost(a: argparse.Namespace) -> int:
    from kicad_rf_studio import pipeline  # here, as in `new`: the CLI adds no work at import time

    return pipeline.cost(pipeline.project_path(a.project), a.run_dir)


def _run(a: argparse.Namespace) -> int:
    from kicad_rf_studio import pipeline

    return pipeline.run(pipeline.project_path(a.project), a.run_dir)


def _retune(a: argparse.Namespace) -> int:
    from kicad_rf_studio import pipeline

    return pipeline.retune(pipeline.project_path(a.project), a.assignments)


def _verify(a: argparse.Namespace) -> int:
    from kicad_rf_studio import pipeline

    return pipeline.verify(pipeline.project_path(a.project), a.run_dir)


def _preview(a: argparse.Namespace) -> int:
    from kicad_rf_studio import pipeline

    return pipeline.preview(pipeline.project_path(a.project))


def _setup_openems(a: argparse.Namespace) -> None:
    for code, params in runs.setup_openems(a.folder):
        print(render(code, **params))


def _calibrate(a: argparse.Namespace) -> None:
    """Measures and stores this machine's speed after the openEMS check (C-31): E_OPENEMS_* come before any worker."""
    for code, params in runs.check_openems():
        print(render(code, **params))
    runs.calibrate(runs.load_settings())


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
    cost.add_argument("--run-dir", type=Path, metavar="DIR")
    cost.set_defaults(func=_cost)
    run = commands.add_parser("run")
    run.add_argument("project")
    run.add_argument("--run-dir", type=Path, metavar="DIR")
    run.set_defaults(func=_run)
    retune = commands.add_parser("retune")
    retune.add_argument("project")
    retune.add_argument("assignments", nargs="*")
    retune.set_defaults(func=_retune)
    verify = commands.add_parser("verify")
    verify.add_argument("project")
    verify.add_argument("--run-dir", type=Path, metavar="DIR")
    verify.set_defaults(func=_verify)
    preview = commands.add_parser("preview")
    preview.add_argument("project")
    preview.set_defaults(func=_preview)
    setup = commands.add_parser("setup-openems")
    setup.add_argument("folder", type=Path, metavar="DIR")
    setup.set_defaults(func=_setup_openems)
    commands.add_parser("calibrate").set_defaults(func=_calibrate)
    return parser


def _event(run_dir: Path | None, kind: str, code: str, params: dict) -> None:
    """An event of main's own, never printed, written only when `run_dir` is a folder by then; a write that fails
    leaves the exit code as it is."""
    with contextlib.suppress(OSError):
        if run_dir is not None and run_dir.is_dir():
            runs.emit(run_dir, kind, code, params, show=False)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # I_STACKUP's ε and I_CHAIN's → are not in cp1252
        if hasattr(stream, "reconfigure"):  # a StringIO, say, has none and needs none
            stream.reconfigure(errors="replace")
    run_dir = command = project = None  # the end event's folder and params, once known
    code = 1
    try:
        args = _parser().parse_args(argv)
        if getattr(args, "run_dir", None) is not None:  # cost, run and verify: made before the command
            args.run_dir = args.run_dir.absolute()  # a relative DIR is read from the working folder
            try:
                args.run_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise KrsError("E_RUN_DIR", path=str(args.run_dir), reason=reason(e, "cannot be made")) from None
            if (args.run_dir / "events.jsonl").exists():  # another run's folder: nothing is added to it
                raise KrsError("E_RUN_DIR", path=str(args.run_dir), reason="already holds a run")
        if hasattr(args, "run_dir"):  # cost, run and verify
            from kicad_rf_studio.pipeline import project_path  # here: the three commands load pipeline anyway

            path = project_path(args.project)
            command, project = args.command, str(path.resolve())
            # made by the command, as before; absolute: `run .` names it after the project's folder too
            args.run_dir = args.run_dir or runs.run_dir_for(path.absolute().parent.name)
            run_dir = args.run_dir
        code = args.func(args) or 0
    except KrsError as e:
        print(e, file=sys.stderr)
        _event(run_dir, "message", e.code, e.params)
        code = 2
    except KeyboardInterrupt:  # Ctrl+C, or a STOP file in the run folder (C-26)
        code = 130
    except Exception as e:
        print(render("E_INTERNAL", detail=detail(e)), file=sys.stderr)
        _event(run_dir, "message", "E_INTERNAL", {"detail": detail(e)})
        code = 1
    finally:
        _event(run_dir, "end", "I_END", {"exit_code": code, "command": command, "project": project})
    return code
