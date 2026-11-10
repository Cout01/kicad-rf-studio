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
antenna's feed (new_antenna, Stage 3). `compare BASE VARIANT` compares two antenna projects' or two signal-integrity
projects' full simulations (pipeline.compare_projects, Stage 3 and Stage 4). `new --interface NAME` writes a
signal-integrity project, schema 3: the line from the start pad to the end pad, a differential pair's partner and up to
two victims (new_si, Stage 4). `review BOARD` measures the board's tagged nets and shield fences against four geometry
rules, with no solver, and writes review.json, review.csv and review.png (review, Stage 5); like `compare`, it starts
no worker.
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
from kicad_rf_studio.core.kicad.tracer import (Chain, adopt, check_antenna, feed_pad, partner_ends, signal_layer,
                                               trace_line)
from kicad_rf_studio.core.kicad.values import parse_band, parse_frequency
from kicad_rf_studio.core.messages import KrsError, detail, reason, render
from kicad_rf_studio.core.project import (BAND_FACTOR, DEFAULT_PRESET, EXPAND_H, HARMONICS, INTERFACES, MARGIN_SCALE,
                                          MESH_N, REACH_H, T_MAX_S, board_hash, make_antenna_project, make_project,
                                          make_si_project, pulse_band, relative_path, save_project, si_interface)

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


def _ends(text: str) -> tuple[str, str]:
    """An argparse type: REF.PAD:REF.PAD as two pad names."""
    ends = tuple(text.split(":"))
    if len(ends) != 2 or not all(ends):
        raise ValueError(text)
    return ends


_ends.__name__ = "REF.PAD:REF.PAD"  # argparse names a type in its error: invalid REF.PAD:REF.PAD value


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
    stored; x and y as f"{v:.3f}"), I_PORT_PLANE with an SI end's plane (vertical, Stage 4 design 5.5),
    I_PORT_NO_REFERENCE with none (a port with no reference has no rule)."""
    named, ref = {"name": port["name"], "signal": port["signal"]}, port["reference"]
    if ref is None:
        return "I_PORT_NO_REFERENCE", named
    if "plane" in ref:
        return "I_PORT_PLANE", {**named, "layer": ref["plane"]}
    if "pad" in ref:
        return "I_PORT", {**named, "reference": ref["pad"], "rule": port["rule"]}
    x, y = ref["point"]
    return "I_PORT_POINT", {**named, "x": f"{x:.3f}", "y": f"{y:.3f}", "layer": ref["layer"], "rule": port["rule"]}


def _head_notes(board, stackup, classes: dict) -> list[tuple[str, dict]]:
    """The notes every `new` starts with: the board's warnings, W_FILLS_AS_SAVED, the stackup (_stackup_note) and
    I_CLASSES, from project.json's `classes`."""
    return [*board.warnings, ("W_FILLS_AS_SAVED", {}), _stackup_note(stackup),
            ("I_CLASSES", {"gnd": _list(classes["gnd_nets"]), "power": _list(classes["power_nets"]),
                           "connectors": _list(classes["connectors"]), "shields": _list(classes["shields"])})]


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

    notes = [*_head_notes(board, stackup, project["classes"]),
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
    from kicad_rf_studio.core.model.spec import antenna_t_max

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
    t_max = antenna_t_max(f_lo, f_hi)
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

    far = project["far_field"]
    notes = [*_head_notes(board, stackup, project["classes"]),
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


def _merged(lines: list[Chain]) -> Chain:
    """SI lines as one chain (Stage 4 design 5.1, the lines ruling): the first line's start and end, every line's nets
    in order, every series part, and every shunt part once, as the first line that has it holds it."""
    shunt = {}
    for p in (p for line in lines for p in line.shunt):
        shunt.setdefault(p.ref, p)
    return Chain(lines[0].start, lines[0].end, tuple(n for line in lines for n in line.nets),
                 tuple(p for line in lines for p in line.series), tuple(shunt.values()))


def _port_length(board, pieces, zs, port: dict) -> float:
    """An SI port's length in mm (W_SI_LONG_PORT): a vertical one's plane-to-pad height, between the facing faces of
    their copper slabs; a horizontal one's distance from its pad to its reference copper."""
    from kicad_rf_studio.core.model.ports import _pad, _reference as reference_copper  # here, as in `new`

    ref = port["reference"]
    if "plane" in ref:
        a, b = (next(s for s in zs if s.copper == layer) for layer in (port["layer"], ref["plane"]))
        return max(a.z0, b.z0) - min(a.z1, b.z1)
    sig = _pad(board, port["signal"], port["signal_uuid"], port["layer"])
    return sig.polygon.distance(reference_copper(board, pieces, port["name"], sig, port["layer"], ref))


def new_si(board: str | Path, start: str, end: str, interface: str, *, pair: bool = False,
           pair_with: tuple[str, str] | None = None, victims=(), f_max: float | None = None,
           target: float | None = None, preset: str = DEFAULT_PRESET, stackup: str | None = None,
           lid_height: float | None = None, output: str | Path | None = None) -> tuple[Path, list[tuple[str, dict]]]:
    """`new` for signal integrity (Stage 4 design 5.1): every refusal before anything is written; returns as `new`."""
    from kicad_rf_studio.core.geometry.copper import copper_pieces  # here, as in `new`
    from kicad_rf_studio.core.geometry.lid import find_lid
    from kicad_rf_studio.core.geometry.region import build_region, lambda_min
    from kicad_rf_studio.core.geometry.sections import eps_eff_2d, line_layers, route_length
    from kicad_rf_studio.core.geometry.zstack import substrate_h
    from kicad_rf_studio.core.model.parts import project_parts
    from kicad_rf_studio.core.model.ports import si_reference
    from kicad_rf_studio.core.model.spec import round_trip, si_t_max
    from kicad_rf_studio.core.post.si import LOCAL_RISE
    from kicad_rf_studio.stoprule import stop_window

    paired = pair or pair_with is not None
    interface = si_interface(interface, f_max, target, paired)
    if len(victims) > 2:
        raise KrsError("E_SI_VICTIMS", count=len(victims))
    f_max = interface["f_max_hz"]
    board, stackup, zs, classes = _load(board, stackup)
    lines = [trace_line(board, classes, start, end)]
    if paired:
        n_start, n_end, how = partner_ends(board, classes, start, end) if pair_with is None else (*pair_with, "given")
        lines.append(trace_line(board, classes, n_start, n_end))
    m = len(lines)  # the measured lines, then the victims
    lines += [trace_line(board, classes, a, b) for a, b in victims]
    held = set()
    for line in lines:
        if shared := [n for n in line.nets if n in held]:
            raise KrsError("E_SI_LINE_SHARED", start=line.start, end=line.end, net=shared[0])
        held.update(line.nets)
    merged = _merged(lines)
    # [P start, N start, P end, N end, each victim's start and end] (design 5.1: se2gmm's order)
    ends = [x.start for x in lines[:m]] + [x.end for x in lines[:m]] + [e for x in lines[m:] for e in (x.start, x.end)]
    ports = [_port(board, classes, f"P{k}", signal) for k, signal in enumerate(ends, 1)]
    bare = [{**p, "reference": None} for p in ports]  # so a far v1 reference stretches no region
    layers = line_layers(board, merged.nets)
    reach = REACH_H * substrate_h(zs, layers)
    roi = build_region(board, _merged(lines[:m]), bare[:2 * m], zs, f_max, REACH_H, layers=layers).roi
    for x in lines[m:]:  # a victim cannot grow the region (design 5.1)
        for name in (x.start, x.end):
            if not roi.covers(next(p for p in board.pads(name) if p.layers).polygon):  # _port's signal pad
                raise KrsError("E_SI_VICTIM_OUTSIDE", victim=f"{x.start}:{x.end}", pad=name, reach_mm=f"{reach:g}")
    first = build_region(board, merged, bare, zs, f_max, REACH_H, layers=layers)
    pieces, _ = copper_pieces(board, first.crop, {s.copper: round(s.z1 - s.z0, 6) for s in zs if s.kind == "copper"})
    for p in ports:
        p["reference"] = si_reference(board, classes, pieces, zs, p["name"], p["signal"], p["reference"], reach)
        if "plane" in p["reference"]:
            p["rule"] = "plane"
    # build_geometry's region, its kept references within the reach: the parts and the lid come from the model's ROI
    region = build_region(board, merged, ports, zs, f_max, REACH_H, layers=layers)
    series, shunt, others, part_notes = project_parts(board, merged, classes, region.roi, 0.0, f_max, si=True)
    chains, taken = [], set()
    for x in lines:  # each line's own parts in v1's chain shape, a part on two lines kept by the first
        own = {q.ref for q in x.series + x.shunt} - taken
        taken |= own
        chains.append({"start": x.start, "end": x.end, "nets": list(x.nets),
                       "series": [q for q in series if q["ref"] in own],
                       "shunt": [q for q in shunt if q["ref"] in own]})
    _, gate = find_lid(board, classes, region, zs, {"lid": True, "lid_height_mm": lid_height})
    eps = eps_eff_2d(board, merged.nets, pieces, zs) or max(s.eps_r for s in zs if s.kind == "dielectric")
    rt = round_trip(max(route_length(board, x.nets) for x in lines), eps)
    window_s, t_max_s = stop_window(rt), si_t_max(f_max, rt)
    limit = lambda_min(f_max, max(s.eps_r for s in zs if s.eps_r is not None)) / 20  # λ/20 in the highest εr
    long_ports = [("W_SI_LONG_PORT", {"name": p["name"], "length_mm": f"{length:.3f}", "limit_mm": f"{limit:.3f}"})
                  for p in ports if (length := _port_length(board, pieces, zs, p)) > limit]
    folder = Path(output or ".")
    board_path, other_drive = relative_path(board.path, folder)
    pair_of = {"p": lines[0].nets[0], "n": lines[1].nets[0], "by": how} if paired else None
    project = make_si_project(  # max_cell_mm null: the d fill, gate P4-C's (docs/validation/2026-11-07-p4-c.md)
        board_path, board_hash(board.path), stackup, classes,
        [{"role": "measured" if k < m else "victim", "chain": c} for k, c in enumerate(chains)], pair_of, others,
        ports, interface, t_max_s=t_max_s, window_s=window_s, max_cell_mm=None, preset=preset,
        lid_height_mm=lid_height)
    path = _write(folder, project)

    notes = [*_head_notes(board, stackup, project["classes"]),
             ("I_SI_INTERFACE", {"interface": interface["interface"], "target": f"{interface['target_ohm']:g}",
                                 "kind": "T_DIFFERENTIAL" if paired else "T_SINGLE_ENDED",
                                 "tolerance_pct": f"{100 * interface['tolerance']:g}",
                                 "rise_ps": f"{interface['rise_s'] * 1e12:g}",
                                 "marker_mhz": f"{interface['marker_hz'] / 1e6:g}", "f_max_ghz": f"{f_max / 1e9:g}",
                                 "local_ps": f"{LOCAL_RISE / f_max * 1e12:g}"})]
    if paired:
        terms = {"rule": "T_PAIR_RULE", "alias": "T_PAIR_ALIAS", "given": "T_PAIR_WITH"}
        notes.append(("I_SI_PAIR", {"p": pair_of["p"], "n": pair_of["n"], "how": terms[how]}))
    notes += [*(("I_CHAIN", {"start": x.start, "end": x.end, "series": _list(q.ref for q in x.series),
                             "shunt": _list(q.ref for q in x.shunt)}) for x in lines[:m]),  # a line's own, as traced
              *(("I_SI_VICTIM", {"start": c["start"], "end": c["end"], "net": c["nets"][0]}) for c in chains[m:]),
              *map(_part_note, series + shunt + others),
              *map(_port_note, ports),
              ("I_SI_DEFAULTS", {"preset": preset, "t_max_ns": f"{t_max_s * 1e9:g}", "window_ns": f"{window_s * 1e9:g}",
                                 "mesh_n": project["mesh"]["n"], "dielectric": project["dielectric"],
                                 "dt_floor": f"{project['gates']['dt_floor']:g}",
                                 "reach_h": f"{project['mesh']['reach_h']:g}", "reach_mm": f"{reach:g}"})]
    if heavy := stackup.nonstandard_copper():
        notes.append(("W_COPPER_WEIGHT", {"layers": _list(heavy)}))
    notes += [("W_LID_HEIGHT_MISSING", params) for code, params in gate if code == "E_LID_HEIGHT"]
    notes += part_notes  # W_VALUE_UNREADABLE (DNP parts too), W_PART_OPEN, I_SI_SHUNT_OPEN
    notes += long_ports
    if other_drive:
        notes.append(("W_ABSOLUTE_BOARD_PATH", {}))
    notes.append(("I_WROTE", {"path": path}))
    return path, notes


def review(board: str | Path, *, nets=(), project: str | None = None, f0=None, clocks=(), f_max=None, edge_k=None,
           edge_fence=False, stackup=None, output=None, emit=None) -> int:
    """`review BOARD` (Stage 5 design 5.1, 5.3), returning its exit code: the board as `new` loads it (_load: its
    E_NO_STACKUP and the stackup's refusals raise, before anything is written), the project at `project` when given
    (read_project), review_board, then review.csv, review.png and review.json written to `output`, the working folder
    when None (write, REVIEW_OUTPUTS, E_RESULTS_WRITE advising this command with -o). Then `emit(code, params)` for
    each line, which prints it by default, in AR-12's order: the review's notes, the findings, I_REVIEW_FINDINGS,
    I_OUTPUTS (a refused write's E_ line in its place, the other lines still printed) and REVIEW_LIMITS. 2 when a line
    is an E_ line, else 0, with findings or without. Frequencies are in Hz and `stackup` names a stackup preset (None:
    the board's own). It reads only: no model, no worker, nothing written outside the folder."""
    # imported here, as in `cost`: the CLI adds no work at import time
    from kicad_rf_studio import pipeline
    from kicad_rf_studio.core.post.outputs import write
    from kicad_rf_studio.core.project import read_project
    from kicad_rf_studio.core.review import REVIEW_LIMITS, review_board
    from kicad_rf_studio.core.review.outputs import REVIEW_OUTPUTS, review_csv, review_json, review_png

    board = str(board)  # the path as given (design 5.3), whether the GUI passes a Path or not
    loaded, stack, zs, classes = _load(board, stackup)
    data = None if project is None else read_project(pipeline.project_path(project))
    r = review_board(loaded, stack, zs, classes, nets=nets, project=data, f0=f0, clocks=clocks, f_max=f_max,
                     edge_k=edge_k, edge_fence=edge_fence)
    folder = Path(output) if output else Path.cwd()
    # review.json, the file the GUI reads, goes last: a held file refuses before it changes
    files = {"review.csv": review_csv(r), "review.png": review_png(r, loaded),
             "review.json": review_json(r, board, board_hash(board))}
    given = [x for net in nets for x in ("--net", net)]  # each given option again, in the parser's order
    given += ["--project", str(project)] if project is not None else []
    given += ["--f0", str(f0)] if f0 is not None else []
    given += [x for clock in clocks for x in ("--clock", str(clock))]
    given += ["--f-max", str(f_max)] if f_max is not None else []
    given += ["--edge-k", str(edge_k)] if edge_k is not None else []
    given += ["--edge-fence"] if edge_fence else []
    given += ["--stackup", stackup] if stackup is not None else []
    lines = [*r.notes, *((f.code, f.params) for f in r.findings), ("I_REVIEW_FINDINGS", {"count": len(r.findings)})]
    try:
        write(folder, files, REVIEW_OUTPUTS,
              pipeline.command_line("kicad-rf-studio", "review", board, *given, "-o", str(folder)))
    except KrsError as err:  # E_RESULTS_WRITE: a viewer holds review.png, say
        lines.append((err.code, err.params))
    else:
        lines.append(("I_OUTPUTS", {"files": ", ".join(sorted(files)), "folder": str(folder)}))
    emit = emit or (lambda code, params: print(render(code, **params)))
    for code, params in [*lines, *((code, {}) for code in REVIEW_LIMITS)]:
        emit(code, params)
    return 2 if any(code.startswith("E_") for code, _ in lines) else 0


def _new(a: argparse.Namespace) -> None:
    """`new` with --end and --f0, new_antenna with --antenna and --band, or new_si with --end and --interface;
    E_NEW_KIND for any other mix, --harmonics without --f0 and an SI option without --interface too."""
    si_option = a.pair or a.pair_with is not None or a.victim or a.f_max is not None or a.target is not None
    if ((a.antenna is None) != (a.band is None) or a.harmonics is not None and a.f0 is None
            or si_option and a.interface is None):
        raise KrsError("E_NEW_KIND")
    if a.interface is not None:
        _, notes = new_si(a.board, a.start, a.end, a.interface, pair=a.pair, pair_with=a.pair_with, victims=a.victim,
                          f_max=a.f_max, target=a.target, preset=a.preset, stackup=a.stackup,
                          lid_height=a.lid_height, output=a.output)
    elif a.antenna is None:
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


def _compare(a: argparse.Namespace) -> int:
    from kicad_rf_studio import pipeline

    return pipeline.compare_projects(pipeline.project_path(a.base), pipeline.project_path(a.variant),
                                     a.output and Path(a.output))


def _review(a: argparse.Namespace) -> int:
    return review(a.board, nets=a.net, project=a.project, f0=a.f0, clocks=a.clock, f_max=a.f_max, edge_k=a.edge_k,
                  edge_fence=a.edge_fence, stackup=a.stackup, output=a.output)


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
    end = new.add_mutually_exclusive_group(required=True)  # a chain's or a line's end, or an antenna (_new pairs them)
    end.add_argument("--end", metavar="REF.PAD")
    end.add_argument("--antenna", metavar="REF")
    frequency = new.add_mutually_exclusive_group(required=True)
    frequency.add_argument("--f0", type=parse_frequency, metavar="F")
    frequency.add_argument("--band", type=parse_band, metavar="F_LO:F_HI")
    frequency.add_argument("--interface", choices=(*INTERFACES, "custom"), metavar="NAME")
    pairing = new.add_mutually_exclusive_group()  # the SI options: _new refuses them without --interface
    pairing.add_argument("--pair", action="store_true")
    pairing.add_argument("--pair-with", type=_ends, metavar="REF.PAD:REF.PAD")
    new.add_argument("--victim", type=_ends, action="append", default=[], metavar="REF.PAD:REF.PAD")
    new.add_argument("--f-max", type=parse_frequency, metavar="F")
    new.add_argument("--target", type=_positive(float), metavar="OHMS")
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
    compare = commands.add_parser("compare")  # no --run-dir: it starts no worker, so main writes it no end event
    compare.add_argument("base")
    compare.add_argument("variant")
    compare.add_argument("-o", dest="output", metavar="PATH")
    compare.set_defaults(func=_compare)
    review = commands.add_parser("review")  # no --run-dir either: it starts no worker, so main writes it no end event
    review.add_argument("board")
    review.add_argument("--net", action="append", default=[], metavar="PATTERN")
    review.add_argument("--project", metavar="PROJECT")
    review.add_argument("--f0", type=parse_frequency, metavar="F")
    review.add_argument("--clock", type=parse_frequency, action="append", default=[], metavar="F")
    review.add_argument("--f-max", type=parse_frequency, metavar="F")
    review.add_argument("--edge-k", type=_positive(float), metavar="K")  # None: EDGE_K
    review.add_argument("--edge-fence", action="store_true")
    review.add_argument("--stackup", metavar="NAME")
    review.add_argument("-o", dest="output", metavar="PATH")
    review.set_defaults(func=_review)
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
