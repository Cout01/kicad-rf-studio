# SPDX-License-Identifier: GPL-3.0-or-later
"""cs2d, the 2D cross-section of a line (spec 5.5), in mm: x across the line, z up."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    """A rectangle of the cross-section: a conductor (`role` "signal" or "ground") or a dielectric of `eps_r` (role
    "")."""
    x0: float
    x1: float
    z0: float
    z1: float
    eps_r: float = 1.0
    role: str = ""


@dataclass(frozen=True)
class CrossSection:
    """Conductors and dielectrics in `box` (x0, x1, z0, z1), air elsewhere; a later dielectric overrides an earlier
    one. `sides` "open" makes the left and right faces of the box Neumann, "pec" keeps them conductors."""
    conductors: tuple[Rect, ...]
    dielectrics: tuple[Rect, ...]
    box: tuple[float, float, float, float]
    sides: str = "pec"
