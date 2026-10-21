# SPDX-License-Identifier: GPL-3.0-or-later
"""The stackup as slabs in z, in mm: bottom to top, with z = 0 at the bottom face of the bottom copper layer."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import accumulate

from kicad_rf_studio.core.kicad.stackup import Stackup
from kicad_rf_studio.core.messages import KrsError


@dataclass(frozen=True)
class Slab:
    """One layer between z0 and z1. `copper` is the board's name of a copper layer, and None for the others."""
    kind: str  # "mask", "copper" or "dielectric"
    z0: float
    z1: float
    eps_r: float | None  # None for copper
    tan_d: float | None
    copper: str | None


def zstack(stackup: Stackup, copper_layers: tuple[str, ...]) -> tuple[Slab, ...]:
    """The stackup's layers bottom to top, quantised to 1e-6 mm. Its copper layers take the board's names (top to
    bottom, as `copper_layers` lists them) by position, since a stackup may repeat a name for copper sub-layers. The
    masks are the stackup's outer layers, so they sit outside the copper. Raises E_STACKUP_LAYERS when the stackup's
    copper count is not the board's, and E_DIELECTRIC_THICKNESS, naming the top one, when a dielectric has no
    thickness (the reader takes a missing one for 0): the copper on either side would touch, and the mesh's d be 0."""
    count = sum(layer.kind == "copper" for layer in stackup.layers)
    if count != len(copper_layers):
        raise KrsError("E_STACKUP_LAYERS", stackup=count, board=len(copper_layers))
    if thin := [layer.name for layer in stackup.layers if layer.kind == "dielectric" and layer.thickness <= 0]:
        raise KrsError("E_DIELECTRIC_THICKNESS", layer=thin[0])
    layers = stackup.layers[::-1]
    faces = list(accumulate((layer.thickness for layer in layers), initial=0.0))  # layer i spans faces[i], faces[i + 1]
    base = faces[next(i for i, layer in enumerate(layers) if layer.kind == "copper")]
    names = iter(copper_layers[::-1])
    return tuple(Slab(layer.kind, round(faces[i] - base, 6), round(faces[i + 1] - base, 6), layer.epsilon_r,
                      layer.loss_tangent, next(names) if layer.kind == "copper" else None)
                 for i, layer in enumerate(layers))


def substrate_h(zs: tuple[Slab, ...]) -> float:
    """The dielectric between the top copper, where the measured nets run, and the next copper down, in mm."""
    # ponytail: the measured nets are taken to run on the top copper, which on 2 layers is no assumption. A chain on
    # another layer of a board with 4 or more gets the top layer's h; pass the chain's layer in when one needs it.
    copper = [s for s in zs if s.kind == "copper"]
    return round(copper[-1].z0 - copper[-2].z1, 6)
