# SPDX-License-Identifier: GPL-3.0-or-later
"""The parts of the model (spec 5.7): each part's role and the parasitics of its chip package."""
import math
import re

import numpy as np
from shapely.geometry import MultiPolygon, Polygon

from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.tracer import Chain, Classes, _netted
from kicad_rf_studio.core.kicad.values import OPEN_VALUE, bypass, part_kind, part_value
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.project import ROLES

PORT, COPPER, OPEN, GRID, CURVE_PORT = ROLES
# ponytail: typical published magnitudes, provisional; plan 5 (P0) confirms them
PRESETS: dict[str, tuple[float, float, float]] = {  # by package: ESL (H), ESR (Ω) and the parallel Cp (F)
    "0201": (3e-10, 0.1, 2e-14), "0402": (5e-10, 0.1, 3e-14), "0603": (7e-10, 0.1, 5e-14),
    "0805": (9e-10, 0.1, 7e-14), "1206": (1.2e-9, 0.1, 1e-13)}
Z0 = 50.0  # Ω: a choke holds 200·Z0 across the band
SHUNT_OPEN_OHM = 1e3  # design 5.1: a pull-up of 1 kΩ or more barely loads a fast line, and each port costs a run
_PACKAGE = re.compile("|".join(PRESETS))


def model_of(lib_id: str) -> dict | None:
    """The preset of the first package size of PRESETS that the library id names, else None."""
    m = _PACKAGE.search(lib_id)
    if m is None:
        return None
    esl, esr, cp = PRESETS[m[0]]
    return {"package": m[0], "esl_h": esl, "esr_ohm": esr, "cp_f": cp}


def srf(kind: str, value: float, model: dict) -> float:
    """The self-resonance in Hz: of the ESL with the capacitance of a C, of the ESL with Cp for an R, and of the
    inductance of an L with Cp."""
    l, c = {"C": (model["esl_h"], value), "R": (model["esl_h"], model["cp_f"]), "L": (value, model["cp_f"])}[kind]
    return 1 / (2 * math.pi * math.sqrt(l * c))


def is_choke(value: float, model: dict, f1: float, f2: float) -> bool:
    """Whether an inductor of `value` H keeps |Z| ≥ 200·Z0 at each of 101 frequencies from f1 to f2, with Z =
    (ESR + jωL) ∥ 1/(jωCp), so that its self-resonance counts."""
    w = 2 * np.pi * np.linspace(f1, f2, 101)
    z = 1 / (1 / (model["esr_ohm"] + 1j * w * value) + 1j * w * model["cp_f"])
    return bool(np.all(np.abs(z) >= 200 * Z0))


def c_box_of(boxes: dict, ref: str) -> float:
    """The C_box (F) of the part port `ref` in `boxes`, a run's c_box by ref (C-16). E_CBOX when it is missing, not
    finite or not above 0: such a box cannot close the port."""
    if ref not in boxes:
        raise KrsError("E_CBOX", ref=ref, value="T_MISSING")
    if not (math.isfinite(c := boxes[ref]) and c > 0):
        raise KrsError("E_CBOX", ref=ref, value=f"{c:g}")
    return c


def role(kind: str | None, value: float | None, model: dict | None, dnp: bool, angle: float, place: str,
         f1: float, f2: float, *, bridge: bool = False) -> str:
    """The role of a part of `kind` (part_kind) and `value` (part_value) placed "series", "shunt" or "other" (off the
    chain), from the first rule that holds (spec 5.7, C-12, C-13): a DNP part is open; an R of 0 is copper; a C or R
    off the chain is in the grid when it has a value and a model, sits at a multiple of 90° and resonates above 3·f2,
    else open; any other part off the chain but an L is open; a part at another angle is a curve port; a shunt or
    other L that is a choke is open; the rest are ports. A value of 0 counts as none. A part of an antenna's board,
    `place` "board" in its measured region and "far" past it (Stage 3 design 5.3), is never a port: a C close to a
    short at the pulse's centre is copper, a C or R that v1 would put in the grid is in the grid on "board" and open on
    "far", and any other part is open. With `bridge`, an SI project's parts off its lines, "other" (Stage 4 design
    5.1), take that capacitor rule too: A-27's rule at the pulse's centre, f_max/2 with f1 0; the rest keep v1's
    roles."""
    square = angle % 90 == 0
    if dnp:
        return OPEN
    if kind == "R" and value == 0:
        return COPPER
    if (bridge or place in ("board", "far")) and kind == "C" and value:  # A-27 (Stage 3 design 5.3, Stage 4's 5.1)
        w = math.pi * (f1 + f2)  # 2π × the pulse's centre, near f0; the copper bridge stands for the package's ESL
        if 1 / (w * value) - w * (model or {}).get("esl_h", 0.0) <= Z0 / 5:
            # ponytail: past the measured region a bridge sits in coarse cells, which may resolve none of it
            # (I_LIMIT_PARTS_OFF_CHAIN says so); its pads as free coordinates if that matters
            return COPPER  # a decoupling capacitor is close to a short at RF
    if place in ("other", "board", "far") and kind in ("C", "R"):
        # ponytail: a grid part past the measured region is open; the whole board's fill would stretch to its pads
        return GRID if place != "far" and value and model and square and srf(kind, value, model) > 3 * f2 else OPEN
    if place in ("board", "far") or place == "other" and kind != "L":
        return OPEN
    if not square:
        return CURVE_PORT
    if kind == "L" and place in ("shunt", "other") and value and model and is_choke(value, model, f1, f2):
        return OPEN
    return PORT


def project_parts(board: Board, chain: Chain, classes: Classes, roi: Polygon | MultiPolygon, f1: float, f2: float,
                  *, antenna: bool = False, si: bool = False, emission: bool = False
                  ) -> tuple[list[dict], list[dict], list[dict], list[tuple[str, dict]]]:
    """The chain's series and shunt parts, the other parts and their notes, as project.json keeps them: a part is
    {"ref", "pads", "nets", "value", "dnp", "role", "model", "s2p"}, its value the footprint's text as written, its
    model the package preset of a C, L or R, else None, and its s2p None (no S2P file; C-18). The others are the
    two-pad parts (two netted copper pads on two nets, no connector or shield) with a pad in `roi` and neither pad on
    a chain net, in reference order; with `antenna` (Stage 3 design 5.3), every such part anywhere on the board, placed
    "board" when a pad meets `roi` (the measured region), else "far". With `antenna` (Stage 3 design 5.1), every chain
    part is a port, a curve port off a multiple of 90°, whatever its value (no 0R, DNP or choke rule), and a DNP one's
    value is OPEN_VALUE. With `si` (Stage 4 design 5.1), every chain part, a part of an SI project's lines, is a port as
    with `antenna`, but a pull-up, a shunt R of SHUNT_OPEN_OHM or more whose other net (its nets[1]) is a GND or power
    net, which is open, a DNP one's value OPEN_VALUE; the others keep v1's roles, placed "other", with role's `bridge`.
    W_VALUE_UNREADABLE names the C, L and R parts whose value does not read, DNP ones too, except an antenna's or an SI
    line's chain part whose value values.bypass reads (0 Ω or open); W_PART_OPEN (W_BOARD_PARTS_OPEN with `antenna`)
    the other parts left open that are not DNP; with `si`, I_SI_SHUNT_OPEN the pull-ups left open that are not DNP.
    `emission` is always given with `antenna` (Stage 5 design 5.6; the controller's ruling on Task 4): an emission run
    puts every part at its value as verify_spec places it, so a chain part whose value values.bypass reads is placed at
    that value here, as v1's roles place a 0R and a DNP part: copper at 0 Ω and open when open, at any angle. Every
    other chain part, the others and the notes stay as with `antenna`."""
    def part(ref: str, pads, nets, place: str) -> dict:
        fp, kind = board.footprints[ref], part_kind(ref)
        model = model_of(fp.lib_id) if kind else None  # spec 5.7: the ideal value plus the preset; a diode has none
        if (si and place == "shunt" and kind == "R" and nets[1] in classes.gnd | classes.power
                and (part_value(ref, fp.value) or 0) >= SHUNT_OPEN_OHM):
            value, part_role = OPEN_VALUE if fp.dnp else fp.value, OPEN  # a pull-up (Stage 4 design 5.1)
        elif (antenna or si) and place in ("series", "shunt"):
            # every part on an antenna's chain or an SI line is a port, whatever its value: a 0R, a DNP placeholder, a
            # choke (Stage 3 design 5.1, Stage 4 design 5.1)
            value, part_role = OPEN_VALUE if fp.dnp else fp.value, CURVE_PORT if fp.angle % 90 else PORT
            if emission and (z := bypass(ref, value)) is not None:  # placed at its value (Stage 5 design 5.6)
                part_role = COPPER if z == 0 else OPEN
        else:
            # ponytail: with f1 0 no inductor is a choke (|Z| at DC is its ESR), so an L off the lines in the region is
            # a part port and a run; a choke test from the marker up if real boards meet one
            value, part_role = fp.value, role(kind, part_value(ref, fp.value), model, fp.dnp, fp.angle, place, f1, f2,
                                              bridge=si)
        return {"ref": ref, "pads": list(pads), "nets": list(nets), "value": value, "dnp": fp.dnp, "role": part_role,
                "model": model, "s2p": None}

    series = [part(p.ref, p.pads, p.nets, "series") for p in chain.series]
    shunt = [part(p.ref, p.pads, p.nets, "shunt") for p in chain.shunt]
    others, not_parts = [], classes.connectors | classes.shields
    for ref in sorted(board.footprints):
        pads = _netted(board.footprints[ref])
        nets = [p.net for p in pads]
        if (len(pads) == 2 and nets[0] != nets[1] and ref not in not_parts and set(nets).isdisjoint(chain.nets)
                and ((inside := any(roi.intersects(p.polygon) for p in pads)) or antenna)):
            place = ("board" if inside else "far") if antenna else "other"
            others.append(part(ref, [p.name for p in pads], nets, place))
    notes = []
    # W_VALUE_UNREADABLE leaves out an antenna's or an SI line's chain part whose value bypass reads, 0 Ω or open
    # (Stage 3 design 5.7)
    bypassed = ({q["ref"] for q in series + shunt if bypass(q["ref"], q["value"]) is not None} if antenna or si
                else set())
    if refs := sorted(q["ref"] for q in series + shunt + others if q["ref"] not in bypassed
                      and part_kind(q["ref"]) and part_value(q["ref"], q["value"]) is None):
        notes.append(("W_VALUE_UNREADABLE", {"refs": ", ".join(refs)}))
    if refs := sorted(q["ref"] for q in others if q["role"] == OPEN and not q["dnp"]):
        notes.append(("W_BOARD_PARTS_OPEN" if antenna else "W_PART_OPEN", {"refs": ", ".join(refs)}))
    if si and (refs := sorted(q["ref"] for q in shunt if q["role"] == OPEN and not q["dnp"])):
        notes.append(("I_SI_SHUNT_OPEN", {"refs": ", ".join(refs)}))
    return series, shunt, others, notes
