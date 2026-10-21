# SPDX-License-Identifier: GPL-3.0-or-later
"""The parts of the model (spec 5.7): each part's role and the parasitics of its chip package."""
import math
import re

import numpy as np
from shapely.geometry import MultiPolygon, Polygon

from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.tracer import Chain, Classes, _netted
from kicad_rf_studio.core.kicad.values import part_kind, part_value
from kicad_rf_studio.core.project import ROLES

PORT, COPPER, OPEN, GRID, CURVE_PORT = ROLES
# ponytail: typical published magnitudes, provisional; plan 4 and P0 refine them
PRESETS: dict[str, tuple[float, float, float]] = {  # by package: ESL (H), ESR (Ω) and the parallel Cp (F)
    "0201": (3e-10, 0.1, 2e-14), "0402": (5e-10, 0.1, 3e-14), "0603": (7e-10, 0.1, 5e-14),
    "0805": (9e-10, 0.1, 7e-14), "1206": (1.2e-9, 0.1, 1e-13)}
Z0 = 50.0  # Ω: a choke holds 200·Z0 across the band
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


def role(kind: str | None, value: float | None, model: dict | None, dnp: bool, angle: float, place: str,
         f1: float, f2: float) -> str:
    """The role of a part of `kind` (part_kind) and `value` (part_value) placed "series", "shunt" or "other" (off the
    chain), from the first rule that holds (spec 5.7, C-12, C-13): a DNP part is open; an R of 0 is copper; a C or R
    off the chain is in the grid when it has a value and a model, sits at a multiple of 90° and resonates above 3·f2,
    else open; any other part off the chain but an L is open; a part at another angle is a curve port; a shunt or
    other L that is a choke is open; the rest are ports. A value of 0 counts as none."""
    square = angle % 90 == 0
    if dnp:
        return OPEN
    if kind == "R" and value == 0:
        return COPPER
    if place == "other" and kind in ("C", "R"):
        return GRID if value and model and square and srf(kind, value, model) > 3 * f2 else OPEN
    if place == "other" and kind != "L":
        return OPEN
    if not square:
        return CURVE_PORT
    if kind == "L" and place in ("shunt", "other") and value and model and is_choke(value, model, f1, f2):
        return OPEN
    return PORT


def project_parts(board: Board, chain: Chain, classes: Classes, roi: Polygon | MultiPolygon, f1: float, f2: float
                  ) -> tuple[list[dict], list[dict], list[dict], list[tuple[str, dict]]]:
    """The chain's series and shunt parts, the other parts and their notes, as project.json keeps them: a part is
    {"ref", "pads", "nets", "value", "dnp", "role", "model"}, its value the footprint's text as written and its model
    the package preset of a C, L or R, else None. The others are the two-pad parts (two netted copper pads on two
    nets, no connector or shield) with a pad in `roi` and neither pad on a chain net, in reference order.
    W_VALUE_UNREADABLE names the C, L and R parts whose value does not read, DNP ones too; W_PART_OPEN the other parts
    left open that are not DNP."""
    def part(ref: str, pads, nets, place: str) -> dict:
        fp, kind = board.footprints[ref], part_kind(ref)
        model = model_of(fp.lib_id) if kind else None  # spec 5.7: the ideal value plus the preset; a diode has none
        return {"ref": ref, "pads": list(pads), "nets": list(nets), "value": fp.value, "dnp": fp.dnp,
                "role": role(kind, part_value(ref, fp.value), model, fp.dnp, fp.angle, place, f1, f2),
                "model": model}

    series = [part(p.ref, p.pads, p.nets, "series") for p in chain.series]
    shunt = [part(p.ref, p.pads, p.nets, "shunt") for p in chain.shunt]
    others, not_parts = [], classes.connectors | classes.shields
    for ref in sorted(board.footprints):
        pads = _netted(board.footprints[ref])
        nets = [p.net for p in pads]
        if (len(pads) == 2 and nets[0] != nets[1] and ref not in not_parts and set(nets).isdisjoint(chain.nets)
                and any(roi.intersects(p.polygon) for p in pads)):
            others.append(part(ref, [p.name for p in pads], nets, "other"))
    notes = []
    if refs := sorted(q["ref"] for q in series + shunt + others
                      if part_kind(q["ref"]) and part_value(q["ref"], q["value"]) is None):
        notes.append(("W_VALUE_UNREADABLE", {"refs": ", ".join(refs)}))
    if refs := sorted(q["ref"] for q in others if q["role"] == OPEN and not q["dnp"]):
        notes.append(("W_PART_OPEN", {"refs": ", ".join(refs)}))
    return series, shunt, others, notes
