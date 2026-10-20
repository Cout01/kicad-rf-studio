# SPDX-License-Identifier: GPL-3.0-or-later
"""The board's layer stack, in mm: the one in the board file, KiCad's default rule or a named preset. The rules
are for 2 copper layers; a board with more brings its own stackup."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from importlib.resources import files

from kicad_rf_studio.core.kicad.sexpr import atom, child, children, num
from kicad_rf_studio.core.messages import KrsError

COPPER = 0.035  # mm, 1 oz: the only copper weight the mesh rule is validated for
COPPER_TOLERANCE = 0.001  # mm
PRESETS = ("kicad-default", "jlcpcb-2l")  # the second is data/stackups/jlcpcb-2l.json
# KiCad's default rule for 2 copper layers, shaped like a preset file
_KICAD_DEFAULT = {"copper_mm": COPPER, "mask": {"thickness_mm": 0.01, "epsilon_r": 3.3, "loss_tangent": 0.0},
                  "dielectric": {"epsilon_r": 4.5, "loss_tangent": 0.02}}
_KINDS = {"copper": "copper", "core": "dielectric", "prepreg": "dielectric"}  # KiCad's (type ...) to a kind


@dataclass(frozen=True)
class Layer:
    name: str
    kind: str  # "mask", "copper" or "dielectric"
    thickness: float
    epsilon_r: float | None  # None: not given (copper has none, and KiCad leaves out a mask's)
    loss_tangent: float | None


@dataclass(frozen=True)
class Stackup:
    source: str  # "board" or the preset's name
    layers: tuple[Layer, ...]  # top to bottom; mask, copper and dielectric only

    def dielectric_thickness(self) -> float:
        return sum(layer.thickness for layer in self.layers if layer.kind == "dielectric")

    def nonstandard_copper(self) -> list[str]:
        """The names of the copper layers that are not 35 um thick, to within a micron."""
        return [layer.name for layer in self.layers
                if layer.kind == "copper" and abs(layer.thickness - COPPER) > COPPER_TOLERANCE]

    def to_json(self) -> dict:
        """The form project.json keeps: the thickness of a layer is `thickness_mm`."""
        return {"source": self.source, "layers": [
            {"name": layer.name, "kind": layer.kind, "thickness_mm": layer.thickness, "epsilon_r": layer.epsilon_r,
             "loss_tangent": layer.loss_tangent} for layer in self.layers]}

    @staticmethod
    def from_json(d: dict) -> Stackup:
        """Reads what `to_json` wrote; a layer may leave out `epsilon_r` and `loss_tangent`."""
        return Stackup(d["source"], tuple(
            Layer(x["name"], x["kind"], x["thickness_mm"], x.get("epsilon_r"), x.get("loss_tangent"))
            for x in d["layers"]))


def from_board(root: list) -> Stackup | None:
    """The stackup in `(setup (stackup ...))`, or None when the board has none. Silkscreen and paste layers are
    left out. KiCad writes the sub-layers of a dielectric after a bare `addsublayer`; each becomes a layer."""
    layers = []
    for item in children(child(child(root, "setup") or [], "stackup") or [], "layer"):
        type_ = str(atom(item, "type", default="")).lower()
        kind = "mask" if "solder mask" in type_ else _KINDS.get(type_)
        if kind is None:
            continue
        parts: list[list] = [[]]  # the item's properties, one list per sub-layer
        for c in item[2:]:
            if c == "addsublayer":
                parts.append([])
            else:
                parts[-1].append(c)
        layers += [Layer(str(item[1]), kind, num(p, "thickness", 1, 0.0), num(p, "epsilon_r"), num(p, "loss_tangent"))
                   for p in parts]
    return Stackup("board", tuple(layers)) if layers else None


def _two_layer(source: str, spec: dict, thickness: float, copper_layers: int) -> Stackup:
    """Mask, copper, dielectric, copper, mask, where the dielectric is what is left of `thickness`."""
    if copper_layers != 2:
        raise KrsError("E_DEFAULT_RULE_LAYERS", count=copper_layers)
    mask, core, copper = spec["mask"], spec["dielectric"], spec["copper_mm"]
    top = Layer("F.Mask", "mask", mask["thickness_mm"], mask["epsilon_r"], mask["loss_tangent"])
    cu = Layer("F.Cu", "copper", copper, None, None)
    dielectric = Layer("dielectric 1", "dielectric", thickness - 2 * (copper + mask["thickness_mm"]),
                       core["epsilon_r"], core["loss_tangent"])
    return Stackup(source, (top, cu, dielectric, replace(cu, name="B.Cu"), replace(top, name="B.Mask")))


def kicad_default(thickness: float, copper_layers: int = 2) -> Stackup:
    """KiCad's default rule for a board of `thickness`: 10 um of mask (epsilon_r 3.3) and 35 um of copper on each
    side of an FR-4 core (epsilon_r 4.5, tan d 0.02). Raises E_DEFAULT_RULE_LAYERS for any other copper count."""
    return _two_layer("kicad-default", _KICAD_DEFAULT, thickness, copper_layers)


def preset(name: str, thickness: float, copper_layers: int = 2) -> Stackup:
    """The named rule for a board of `thickness`. Raises E_UNKNOWN_PRESET, and E_DEFAULT_RULE_LAYERS for any
    copper count but 2."""
    if name not in PRESETS:
        raise KrsError("E_UNKNOWN_PRESET", name=name, known=", ".join(PRESETS))
    if name == "kicad-default":
        return kicad_default(thickness, copper_layers)
    spec = json.loads(files("kicad_rf_studio").joinpath(f"data/stackups/{name}.json").read_text("utf-8"))
    return _two_layer(name, spec, thickness, copper_layers)
