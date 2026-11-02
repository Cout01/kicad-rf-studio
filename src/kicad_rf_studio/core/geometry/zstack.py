# SPDX-License-Identifier: GPL-3.0-or-later
"""The stackup as slabs in z, in mm: bottom to top, with z = 0 at the bottom face of the bottom copper layer."""
from __future__ import annotations

from collections.abc import Iterable
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


def substrate_h(zs: tuple[Slab, ...], layers: Iterable[str] = ()) -> float:
    """The dielectric next to the measured nets' copper, in mm. Without `layers`: between the top copper, where v1's
    and an antenna's measured nets run, and the next copper down. With `layers` (an SI project's line layers, Stage 4
    design 5.3): the thinnest dielectric between any of them and a copper layer next to it, above or below, which sets
    the fringing field d resolves and the reach. KeyError for a name that is not a copper layer of `zs`."""
    # ponytail: without `layers` the measured nets are taken to run on the top copper, which on 2 layers is no
    # assumption: on 4 or more, a chain on another layer gets the top layer's h. SI passes its lines' layers.
    cu = [s for s in zs if s.kind == "copper"]  # bottom up
    at = {s.copper: i for i, s in enumerate(cu)}
    gaps = []
    for i in [at[layer] for layer in layers] or [len(cu) - 1]:  # no layers: the top copper
        if i > 0:
            gaps.append(cu[i].z0 - cu[i - 1].z1)  # the dielectric below it
        if i < len(cu) - 1:
            gaps.append(cu[i + 1].z0 - cu[i].z1)  # and above it
    return round(min(gaps), 6)
