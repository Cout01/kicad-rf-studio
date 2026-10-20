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
# What KiCad assumes for a mask or dielectric whose file gives no epsilon_r or loss_tangent: it writes them only for a
# layer with a material, and a default stackup's mask has none. DEFAULT_EPSILON_R_SOLDERMASK is KiCad's own macro
# (stackup_predefined_prms.h); the others are the values its BOARD_STACKUP_ITEM and DIELECTRIC_PRMS start from
# (board_stackup.cpp, board_stackup.h): FR4 for a dielectric, no loss for a mask. The one place they are written.
DEFAULT_EPSILON_R_SOLDERMASK = 3.3
DEFAULT_LOSS_TANGENT_SOLDERMASK = 0.0
DEFAULT_EPSILON_R_DIELECTRIC = 4.5
DEFAULT_LOSS_TANGENT_DIELECTRIC = 0.02
_DEFAULTS = {"mask": (DEFAULT_EPSILON_R_SOLDERMASK, DEFAULT_LOSS_TANGENT_SOLDERMASK),
             "dielectric": (DEFAULT_EPSILON_R_DIELECTRIC, DEFAULT_LOSS_TANGENT_DIELECTRIC)}
PRESETS = ("kicad-default", "jlcpcb-2l")  # the second is data/stackups/jlcpcb-2l.json
# KiCad's default rule for 2 copper layers, shaped like a preset file
_KICAD_DEFAULT = {"copper_mm": COPPER,
                  "mask": {"thickness_mm": 0.01, "epsilon_r": DEFAULT_EPSILON_R_SOLDERMASK,
                           "loss_tangent": DEFAULT_LOSS_TANGENT_SOLDERMASK},
                  "dielectric": {"epsilon_r": DEFAULT_EPSILON_R_DIELECTRIC,
                                 "loss_tangent": DEFAULT_LOSS_TANGENT_DIELECTRIC}}
_KINDS = {"copper": "copper", "core": "dielectric", "prepreg": "dielectric"}  # KiCad's (type ...) to a kind


@dataclass(frozen=True)
class Layer:
    """One layer, in mm. A mask or dielectric with no epsilon_r or loss_tangent (None) takes KiCad's default for its
    kind, the DEFAULT_* constants above, however the layer is made: only copper keeps None."""
    name: str
    kind: str  # "mask", "copper" or "dielectric"
    thickness: float
    epsilon_r: float | None
    loss_tangent: float | None

    def __post_init__(self):
        epsilon_r, loss_tangent = _DEFAULTS.get(self.kind, (None, None))
        if self.epsilon_r is None:
            object.__setattr__(self, "epsilon_r", epsilon_r)
        if self.loss_tangent is None:
            object.__setattr__(self, "loss_tangent", loss_tangent)


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
        """Reads what `to_json` wrote. A layer may leave out `epsilon_r` and `loss_tangent`; a mask or dielectric that
        does gets KiCad's default, as in `from_board`."""
        return Stackup(d["source"], tuple(
            Layer(x["name"], x["kind"], x["thickness_mm"], x.get("epsilon_r"), x.get("loss_tangent"))
            for x in d["layers"]))


def from_board(root: list) -> Stackup | None:
    """The stackup in `(setup (stackup ...))`, or None when the board has none. Silkscreen and paste layers are
    left out. KiCad writes the sub-layers of a dielectric after a bare `addsublayer`; each becomes a layer. A mask or
    dielectric the file gives no epsilon_r or loss_tangent (KiCad writes them only for a layer with a material) gets
    KiCad's default (DEFAULT_*, applied by `Layer`)."""
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
    """Mask, copper, dielectric, copper, mask, where the dielectric is what is left of `thickness`. A null in `spec`
    (a value the vendor does not publish) gets KiCad's default (DEFAULT_*, applied by `Layer`); the preset file keeps
    the null, because it records what the vendor publishes."""
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
    """The named rule for a board of `thickness`. A null in the preset file takes KiCad's default (DEFAULT_*), as in
    `from_board`. Raises E_UNKNOWN_PRESET, and E_DEFAULT_RULE_LAYERS for any copper count but 2."""
    if name not in PRESETS:
        raise KrsError("E_UNKNOWN_PRESET", name=name, known=", ".join(PRESETS))
    if name == "kicad-default":
        return kicad_default(thickness, copper_layers)
    spec = json.loads(files("kicad_rf_studio").joinpath(f"data/stackups/{name}.json").read_text("utf-8"))
    return _two_layer(name, spec, thickness, copper_layers)
