# SPDX-License-Identifier: GPL-3.0-or-later
"""The command line. `new` reads a board, traces the RF chain between two pads and writes project.json, which it never
replaces. `cost` prints the 2D Z0 and εeff of the measured nets' straight sections, then runs openEMS's setup-only
gate and prints the cost (pipeline.cost). `run` runs the gates and one job per port under the stop rule; only when
every job kept S does it replace the results in project.json and write the outputs to results/ (pipeline.run).
`retune` stores new part values or S2P files and writes results/ again from the last run's waves, with no new run
(pipeline.retune). `verify` runs once more with every part port in the grid at its ideal value, and compares that with
a retune at the same values (pipeline.verify). `preview` has a worker write the model's model.xml and opens it in
AppCSXCAD (pipeline.preview).
`new --antenna REF --band F_LO:F_HI` writes an antenna's project instead, schema 2, its chain from the start pad to the
antenna's feed (new_antenna, Stage 3).
`setup-openems` installs openEMS from the official Windows package into this Python, and `calibrate` measures this
machine's simulation speed. `install-kicad-plugin` writes the KiCad toolbar button (button.install) into KiCad's
plugin folders, or removes it. `cost`, `run` and `verify` take `--run-dir DIR`, the run folder to use instead of a new
one in the data folder (Stage 2's GUI gives it, design 5.2): made before the command, and refused with E_RUN_DIR when it
cannot be made or already holds a run. Their run folder, once it exists, ends with an end event (I_END) however the
command ends, after a message event for a refusal or an internal error that main caught (A-13). A command returns its
exit code, None for 0. There is no help= text: every string a user sees is a code in core.messages, and argparse
itself writes the usage line."""
import argparse
import contextlib
import math
import sys
from dataclasses import replace
from pathlib import Path

from kicad_rf_studio import runs
from kicad_rf_studio.core.kicad import choose_reference, classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.stackup import preset as stackup_preset
from kicad_rf_studio.core.kicad.tracer import adopt, check_antenna, feed_pad, signal_layer
from kicad_rf_studio.core.kicad.values import parse_band, parse_frequency
from kicad_rf_studio.core.messages import KrsError, detail, reason, render
from kicad_rf_studio.core.project import (BAND_FACTOR, DEFAULT_PRESET, EXPAND_H, HARMONICS, MARGIN_SCALE, MESH_N,
                                          REACH_H, T_MAX_S, board_hash, make_antenna_project, make_project, pulse_band,
                                          relative_path, save_project)

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
    return ", ".join(names) or "T_NONE"


def _stackup_note(stackup) -> tuple[str, dict]:
    """The stackup as `new` prints it: I_STACKUP, or I_STACKUP_NO_MASK without a mask; the board's own as
    T_SOURCE_BOARD (project.json keeps "board")."""
    dielectric = next(x for x in stackup.layers if x.kind == "dielectric")  # there is one: its thickness is above 0
    mask = next((x for x in stackup.layers if x.kind == "mask"), None)  # the top one; a stackup may have none
    shown = {"source": "T_SOURCE_BOARD" if stackup.source == "board" else stackup.source,
             "thickness_mm": f"{stackup.dielectric_thickness():g}", "epsilon_r": dielectric.epsilon_r}
    if mask is None:
        return "I_STACKUP_NO_MASK", shown
    return "I_STACKUP", {**shown, "mask_mm": f"{mask.thickness:g}", "mask_epsilon_r": mask.epsilon_r}


def _part_note(part: dict) -> tuple[str, dict]:
    """A part as I_PART prints it, or I_PART_NO_MODEL for one with no package preset."""
    named, model = {"ref": part["ref"], "value": part["value"], "role": part["role"]}, part["model"]
    if model is None:
        return "I_PART_NO_MODEL", named
    return "I_PART", {**named, "package": model["package"], "esl_nh": f"{model['esl_h'] * 1e9:g}",
                      "esr_ohm": f"{model['esr_ohm']:g}"}


def _port_note(port: dict) -> tuple[str, dict]:
    """A port as `new` prints it: I_PORT with a pad reference, I_PORT_POINT with a point on a layer (KiCad's frame, as
    stored; x and y as f"{v:.3f}"), I_PORT_NO_REFERENCE with none (a port with no reference has no rule)."""
    named, ref = {"name": port["name"], "signal": port["signal"]}, port["reference"]
    if ref is None:
        return "I_PORT_NO_REFERENCE", named
    if "pad" in ref:
        return "I_PORT", {**named, "reference": ref["pad"], "rule": port["rule"]}
    x, y = ref["point"]
    return "I_PORT_POINT", {**named, "x": f"{x:.3f}", "y": f"{y:.3f}", "layer": ref["layer"], "rule": port["rule"]}


def _reference(ref) -> dict | None:
    """A port's reference as project.json keeps it: a pad, a point on a layer, or None. The point is in KiCad's frame,
    y down, as project.py says."""
    if ref is None:
        return None
    if ref.rule == "copper":
        x, y = ref.point
        return {"point": [x, 0.0 - y], "layer": ref.layer}  # 0.0 - y keeps a zero from becoming -0.0
    return {"pad": ref.pad, "uuid": ref.uuid}


def _load(board: str | Path, stackup: str | None) -> tuple:
    """`new`'s board, its stackup (preset `stackup`'s, None: the board's own), z-stack and classes, as (board, stackup,
    zs, classes). E_NO_STACKUP when there is no stackup, or none that leaves a dielectric."""
    from kicad_rf_studio.core.geometry.zstack import zstack  # here, as in `cost`: the CLI adds no work at import time

    board = load_board(board)
    named = stackup is not None  # an empty --stackup is a name too, and an unknown one
    stackup = stackup_preset(stackup, board.thickness, len(board.copper_layers)) if named else board.stackup
    if stackup is None or stackup.dielectric_thickness() <= 0:  # no stackup, or none that leaves a dielectric
        raise KrsError("E_NO_STACKUP")
    return board, stackup, zstack(stackup, board.copper_layers), classify(board)


def _port(board, classes, name: str, signal: str) -> dict:
    """Port `name` at pad `signal`, with its reference (choose_reference), as project.json keeps it."""
    ref = choose_reference(board, classes, signal)
    sig = next(p for p in board.pads(signal) if p.layers)  # the pad trace_chain resolved: the first with copper
    return {"name": name, "signal": signal, "signal_uuid": sig.uuid, "layer": signal_layer(board, sig),
            "rule": ref and ref.rule, "reference": _reference(ref)}


def _write(folder: Path, project: dict) -> Path:
    """Writes `project` to project.json in `folder`, which it makes, and returns its path. It never replaces one:
    E_PROJECT_EXISTS, then E_OUTPUT_PATH for a write that fails."""
    target = folder / "project.json"
    try:
        if target.exists():  # it may hold the hand edits that W_NO_REFERENCE and W_LID_HEIGHT_MISSING ask for
            raise KrsError("E_PROJECT_EXISTS", path=str(target))
        folder.mkdir(parents=True, exist_ok=True)
        save_project(target, project)
    except OSError as e:  # the path the error names (the folder, a file in the way, the file written), else target
        raise KrsError("E_OUTPUT_PATH", path=str(e.filename or target), reason=reason(e, "T_CANNOT_WRITE")) from None
    return target


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
    from kicad_rf_studio.core.model.parts import project_parts

    board, stackup, zs, classes = _load(board, stackup)
    chain = trace_chain(board, start, end, classes)
    ports = [_port(board, classes, f"P{n}", signal) for n, signal in enumerate((start, end), 1)]
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
    target = _write(folder, project)

    c = project["classes"]
    notes = [*board.warnings, ("W_FILLS_AS_SAVED", {}), _stackup_note(stackup),
             ("I_CLASSES", {"gnd": _list(c["gnd_nets"]), "power": _list(c["power_nets"]),
                            "connectors": _list(c["connectors"]), "shields": _list(c["shields"])}),
             ("I_CHAIN", {"start": chain.start, "end": chain.end, "series": _list(p.ref for p in chain.series),
                          "shunt": _list(p.ref for p in chain.shunt)}),
             *map(_part_note, series + shunt + others),
             *map(_port_note, ports),
             ("I_F0", {"f0_mhz": f"{f0 / 1e6:g}", "harmonics": harmonics}),
             ("I_DEFAULTS", {"preset": preset, "band_factor": BAND_FACTOR, "t_max_ns": f"{T_MAX_S * 1e9:g}",
                             "harmonics": harmonics, "mesh_n": MESH_N[preset], "expand_h": f"{EXPAND_H:g}",
                             "margin_scale": f"{MARGIN_SCALE:g}", "reach_h": f"{REACH_H:g}"}),
             ("I_LID_ON" if harmonics > 1 else "I_LID_OFF", {})]
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


def new_antenna(board: str | Path, start: str, antenna: str, band: tuple[float, float], *,
                preset: str = DEFAULT_PRESET, stackup: str | None = None, lid_height: float | None = None,
                output: str | Path | None = None) -> tuple[Path, list[tuple[str, dict]]]:
    """`new` for an antenna (Stage 3 design 5.1): every refusal before anything is written; returns as `new`."""
    from kicad_rf_studio.core.geometry.lid import find_lid  # here, as in `new`
    from kicad_rf_studio.core.geometry.region import air_gap, board_region
    from kicad_rf_studio.core.model.parts import project_parts
    from kicad_rf_studio.core.model.spec import pulse

    f_lo, f_hi = band
    if f_hi > 2 * f_lo:
        raise KrsError("E_BAND_WIDE", f_lo_mhz=f"{f_lo / 1e6:g}", f_hi_mhz=f"{f_hi / 1e6:g}")
    board, stackup, zs, classes = _load(board, stackup)
    check_antenna(board, antenna)
    feed = feed_pad(board, classes, antenna)
    adopt(board, antenna, feed.net)
    # ponytail: every GND pad of the footprint, also a mounting pad; the footprint's net-tie group if one hides a short
    join = list(dict.fromkeys(p.name for p in board.footprints[antenna].pads if p.layers and p.net in classes.gnd))
    chain = trace_chain(board, start, feed.name, classes, antenna=antenna)
    ports = [_port(board, classes, "P1", start)]
    f1, f2 = pulse_band(f_lo, f_hi)
    f0 = (f_lo + f_hi) / 2
    # design 5.4: 2·t0 + 60/f0, rounded up to a whole ns
    t_max = math.ceil((2 * pulse(f1, f2, 0)["t0"] + 60 / f0) * 1e9) / 1e9
    region = board_region(board, chain, ports, zs, f2)
    series, shunt, others, part_notes = project_parts(board, chain, classes, region.roi, f1, f2, antenna=True)
    # every shield on the board is a candidate
    _, gate = find_lid(board, classes, replace(region, roi=region.crop), zs, {"lid": True, "lid_height_mm": lid_height})
    folder = Path(output or ".")
    board_path, other_drive = relative_path(board.path, folder)
    project = make_antenna_project(
        board_path, board_hash(board.path), f_lo, f_hi, stackup, classes,
        {"start": chain.start, "end": chain.end, "nets": list(chain.nets), "series": series, "shunt": shunt}, others,
        ports, antenna, join, t_max_s=t_max, air_gap_mm=air_gap(f_lo), preset=preset, lid_height_mm=lid_height)
    target = _write(folder, project)

    c, far = project["classes"], project["far_field"]
    notes = [*board.warnings, ("W_FILLS_AS_SAVED", {}), _stackup_note(stackup),
             ("I_CLASSES", {"gnd": _list(c["gnd_nets"]), "power": _list(c["power_nets"]),
                            "connectors": _list(c["connectors"]), "shields": _list(c["shields"])}),
             ("I_ANTENNA", {"ref": antenna, "feed": feed.name, "net": feed.net})]
    if join:
        notes.append(("I_ANTENNA_JOIN", {"ref": antenna, "pads": ", ".join(join)}))
    notes += [("I_CHAIN", {"start": chain.start, "end": chain.end, "series": _list(p.ref for p in chain.series),
                           "shunt": _list(p.ref for p in chain.shunt)}),
              *map(_part_note, series + shunt + others),
              *map(_port_note, ports),
              ("I_BAND", {"f_lo_mhz": f"{f_lo / 1e6:g}", "f_hi_mhz": f"{f_hi / 1e6:g}", "f0_mhz": f"{f0 / 1e6:g}",
                          "f1_mhz": f"{f1 / 1e6:g}", "f2_mhz": f"{f2 / 1e6:g}"}),
              ("I_ANTENNA_DEFAULTS", {"preset": preset, "t_max_ns": f"{t_max * 1e9:g}", "mesh_n": project["mesh"]["n"],
                                      "expand_h": f"{project['region']['expand_h']:g}",
                                      "reach_h": f"{project['mesh']['reach_h']:g}",
                                      "air_gap_mm": f"{project['air_gap_mm']:.1f}", "boundary": project["boundary"],
                                      "count": len(far["f_hz"]), "step_deg": far["step_deg"]})]
    if heavy := stackup.nonstandard_copper():
        notes.append(("W_COPPER_WEIGHT", {"layers": _list(heavy)}))
    notes += [("W_LID_HEIGHT_MISSING", params) for code, params in gate if code == "E_LID_HEIGHT"]
    notes += part_notes  # W_VALUE_UNREADABLE (DNP parts too), W_BOARD_PARTS_OPEN
    notes += [("W_NO_REFERENCE", {"signal": p["signal"]}) for p in ports if p["reference"] is None]
    if not 1e6 <= f0 <= 1e11:  # a bare --band 2400:2483.5 is in Hz
        notes.append(("W_F0_RANGE", {"f0_hz": f"{f0:g}"}))
    if other_drive:
        notes.append(("W_ABSOLUTE_BOARD_PATH", {}))
    notes.append(("I_WROTE", {"path": target}))
    return target, notes


def _new(a: argparse.Namespace) -> None:
    """`new` with --end and --f0, or new_antenna with --antenna and --band; E_NEW_KIND for any other mix, --harmonics
    with --antenna too."""
    if (a.antenna is None) != (a.band is None) or (a.antenna is not None and a.harmonics is not None):
        raise KrsError("E_NEW_KIND")
    if a.antenna is None:
        _, notes = new(a.board, a.start, a.end, a.f0, harmonics=a.harmonics or HARMONICS, preset=a.preset,
                       stackup=a.stackup, lid_height=a.lid_height, output=a.output)
    else:
        _, notes = new_antenna(a.board, a.start, a.antenna, a.band, preset=a.preset, stackup=a.stackup,
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


def _install_kicad_plugin(a: argparse.Namespace) -> None:
    from kicad_rf_studio import button  # here, as in `cost`: the CLI adds no work at import time

    for code, params in button.install(a.kicad, a.remove):
        print(render(code, **params))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kicad-rf-studio")
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new")
    new.add_argument("board")
    new.add_argument("--start", required=True, metavar="REF.PAD")
    end = new.add_mutually_exclusive_group(required=True)  # a matching chain's end, or an antenna (_new pairs them)
    end.add_argument("--end", metavar="REF.PAD")
    end.add_argument("--antenna", metavar="REF")
    frequency = new.add_mutually_exclusive_group(required=True)
    frequency.add_argument("--f0", type=parse_frequency, metavar="F")
    frequency.add_argument("--band", type=parse_band, metavar="F_LO:F_HI")
    new.add_argument("--harmonics", type=_positive(int), metavar="N")  # None: HARMONICS, for a matching chain only
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
    plugin = commands.add_parser("install-kicad-plugin")
    plugin.add_argument("--kicad", choices=("9.0", "10.0"))
    plugin.add_argument("--remove", action="store_true")
    plugin.set_defaults(func=_install_kicad_plugin)
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
                raise KrsError("E_RUN_DIR", path=str(args.run_dir), reason=reason(e, "T_CANNOT_MAKE")) from None
            if (args.run_dir / "events.jsonl").exists():  # another run's folder: nothing is added to it
                raise KrsError("E_RUN_DIR", path=str(args.run_dir), reason="T_HOLDS_A_RUN")
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
