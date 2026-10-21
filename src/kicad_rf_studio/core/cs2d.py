# SPDX-License-Identifier: GPL-3.0-or-later
"""cs2d, the 2D cross-section of a line and its quasi-static solver (spec 5.5), in mm: x across the line, z up. A
finite-volume Laplace solve on a rectilinear grid gives the capacitance per length with the dielectrics (C) and in
vacuum (C0): Z0 = 1/(c0·√(C·C0)) and εeff = C/C0. On its own grid it is the 2D reference; on the FDTD mesh lines it is
fit2d's estimate of what that mesh makes of the line."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
from scipy.constants import c as C_0
from scipy.constants import epsilon_0 as EPS_0
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

REF_H = 10  # reference_box: substrate heights past the line
FINE = 20  # the reference grid: cells next to conductor edges are at most min(feature)/FINE,
GRADE = 1.2  # grow away from them by at most this ratio,
COARSE = 40  # up to the box's side/COARSE
TOL = 1e-9  # mm, float noise on coordinates of the 1e-6 mm grid


class ShortError(ValueError):
    """A grid node lies on the signal and on another conductor, which the FDTD model shorts."""


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


@dataclass(frozen=True)
class Line:
    """A line's quasi-static characteristic impedance `z0` (Ω) and effective permittivity `eps_eff`."""
    z0: float
    eps_eff: float


def reference_box(conductors: tuple[Rect, ...], h: float) -> tuple[float, float, float, float]:
    """The box of a comparison with the line formulas: REF_H·h past the signal's sides and above the top copper; below,
    the bottom face of the bottom ground plane (the highest ground under the signal that spans the box), else REF_H·h
    under the lowest copper. On the 1e-6 mm grid."""
    sig = [r for r in conductors if r.role == "signal"]
    x0, x1 = min(r.x0 for r in sig) - REF_H * h, max(r.x1 for r in sig) + REF_H * h
    under = min(r.z0 for r in sig)
    planes = [r.z0 for r in conductors if r.role == "ground" and r.x0 <= x0 and r.x1 >= x1 and r.z1 <= under]
    z0 = max(planes, default=min(r.z0 for r in conductors) - REF_H * h)
    z1 = max(r.z1 for r in conductors) + REF_H * h
    return round(x0, 6), round(x1, 6), round(z0, 6), round(z1, 6)


def _within(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return (v >= lo - TOL) & (v <= hi + TOL)


def _fine(rects: list[Rect]) -> float:
    """min(feature)/FINE: the smallest width, thickness or gap of the conductors `rects`."""
    # ponytail: a sheet (zero thickness) has a sharper edge field than FINE resolves, and reads Z0 about 1.2 % low; a
    # cross-section gives every conductor its layer's thickness (Task 6). Upgrade: cells of feature/320 at sheet edges
    # (0.1 %).
    f = []
    for i, p in enumerate(rects):
        f += [p.x1 - p.x0, p.z1 - p.z0]
        for q in rects[i + 1:]:
            if p.z0 <= q.z1 and q.z0 <= p.z1:  # side by side (sheets too): the gap across x
                f.append(max(q.x0 - p.x1, p.x0 - q.x1))
            if p.x0 <= q.x1 and q.x0 <= p.x1:  # one over the other: the gap across z
                f.append(max(q.z0 - p.z1, p.z0 - q.z1))
    return min((v for v in f if v > TOL), default=math.inf) / FINE


def _axis(lo: float, hi: float, fixed: list[float], edges: list[float], fine: float) -> np.ndarray:
    """Reference lines from `lo` to `hi` through each of `fixed` between them: cells next to `edges` at most `fine`,
    growing away from them by at most GRADE up to (hi − lo)/COARSE. Each step is the size limit where it starts over
    GRADE, which keeps it under the limit across the cell; a run between two fixed lines is then shrunk to end on the
    second."""
    stops = np.unique(np.round([lo, hi, *(v for v in fixed if lo + TOL < v < hi - TOL)], 9))
    e, coarse = np.array([v for v in edges if lo + TOL < v < hi - TOL]), (hi - lo) / COARSE
    out = [stops[0]]
    for p, q in zip(stops[:-1], stops[1:]):
        v = [p]
        while v[-1] < q:
            v.append(v[-1] + min(coarse, fine + (GRADE - 1) * np.min(np.abs(e - v[-1]), initial=np.inf)) / GRADE)
        out += [p + (u - p) * (q - p) / (v[-1] - p) for u in v[1:-1]] + [q]
    return np.array(out)


def _bounded(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """The given lines `v` inside (lo, hi), and lo and hi."""
    v = np.asarray(v, dtype=float)
    return np.unique(np.concatenate([[lo, hi], v[(v > lo + TOL) & (v < hi - TOL)]]))


def _dirichlet(cs: CrossSection, x: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The fixed nodes and their potentials: the box's faces at 0 V (its left and right ones only when `sides` is
    "pec"), then each conductor, the signal at 1 V and any other at 0 V, on both ends of every grid edge whose middle
    lies in it. That is openEMS's rule for metal on a Yee edge, so a conductor that holds no edge's middle is lost, as
    in the FDTD model, and a node held by the signal and another conductor joins them: ShortError."""
    fixed = np.zeros((len(x), len(z)), bool)
    fixed[:, [0, -1]] = True
    if cs.sides == "pec":
        fixed[[0, -1]] = True
    sig, other = np.zeros(fixed.shape, bool), np.zeros(fixed.shape, bool)
    xm, zm = (x[:-1] + x[1:]) / 2, (z[:-1] + z[1:]) / 2
    for r in cs.conductors:
        across = _within(xm, r.x0, r.x1)[:, None] & _within(z, r.z0, r.z1)  # edges along x, by their left node
        up = _within(x, r.x0, r.x1)[:, None] & _within(zm, r.z0, r.z1)  # edges along z, by their lower node
        on = sig if r.role == "signal" else other
        on[:-1] |= across
        on[1:] |= across
        on[:, :-1] |= up
        on[:, 1:] |= up
    if (sig & other).any():
        raise ShortError("a grid node lies on the signal and on another conductor: the FDTD model shorts them")
    return fixed | sig | other, sig.astype(float)


def _capacitance(x: np.ndarray, z: np.ndarray, eps: np.ndarray, fixed: np.ndarray, phi: np.ndarray) -> float:
    """C/ε0 between the potentials `phi` on the `fixed` nodes, the cells of εr `eps`: the energy Σ g·Δφ² of the
    5-point system, which equals the signal's charge. An edge's g sums, over the (up to) two cells that share it, the
    cell's εr times its side across the edge over twice its side along it: the area-weighted mean permittivity."""
    dx, dz = np.diff(x), np.diff(z)
    ex, ez = np.pad(eps * dz, ((0, 0), (1, 1))), np.pad(eps * dx[:, None], ((1, 1), (0, 0)))
    node = np.arange(fixed.size).reshape(fixed.shape)
    a = np.concatenate([node[:-1].ravel(), node[:, :-1].ravel()])
    b = np.concatenate([node[1:].ravel(), node[:, 1:].ravel()])
    g = np.concatenate([((ex[:, :-1] + ex[:, 1:]) / (2 * dx[:, None])).ravel(),
                        ((ez[:-1] + ez[1:]) / (2 * dz)).ravel()])
    k = coo_matrix((np.concatenate([g, g, -g, -g]), (np.concatenate([a, b, a, b]), np.concatenate([a, b, b, a]))),
                   shape=(fixed.size, fixed.size)).tocsr()
    free, p = ~fixed.ravel(), phi.ravel().copy()
    p[free] = spsolve(k[free][:, free].tocsc(), -(k[free][:, ~free] @ p[~free]))
    return float(np.sum(g * (p[a] - p[b]) ** 2))


def solve(cs: CrossSection, x: np.ndarray | None = None, z: np.ndarray | None = None) -> Line:
    """Z0 and εeff of the signal of `cs` against its other conductors and its box. Without `x`/`z` it meshes that axis
    itself: lines at every rect edge, cells at most min(feature)/FINE next to conductor edges, graded by GRADE up to
    the box/COARSE. Given lines are used as they are, inside the box; its faces bound the solve either way. A cell takes
    the εr of the last dielectric that holds its centre. Raises ValueError when the signal holds no grid edge, and
    ShortError, a ValueError, when a grid node joins it to another conductor (a short in the FDTD model)."""
    x0, x1, z0, z1 = cs.box
    inside = [replace(r, x0=max(r.x0, x0), x1=min(r.x1, x1), z0=max(r.z0, z0), z1=min(r.z1, z1)) for r in cs.conductors]
    inside = [r for r in inside if r.x0 <= r.x1 and r.z0 <= r.z1]
    if x is None or z is None:
        fine, rects = _fine(inside), (*cs.conductors, *cs.dielectrics)
    if x is None:
        x = _axis(x0, x1, [v for r in rects for v in (r.x0, r.x1)], [v for r in inside for v in (r.x0, r.x1)], fine)
    if z is None:
        z = _axis(z0, z1, [v for r in rects for v in (r.z0, r.z1)], [v for r in inside for v in (r.z0, r.z1)], fine)
    x, z = _bounded(x, x0, x1), _bounded(z, z0, z1)
    fixed, phi = _dirichlet(cs, x, z)
    if not phi.any():
        raise ValueError("no grid edge lies in the signal conductor")
    eps = np.ones((len(x) - 1, len(z) - 1))
    xm, zm = (x[:-1] + x[1:]) / 2, (z[:-1] + z[1:]) / 2
    for r in cs.dielectrics:
        eps[np.ix_((xm > r.x0) & (xm < r.x1), (zm > r.z0) & (zm < r.z1))] = r.eps_r
    cap, cap0 = (_capacitance(x, z, e, fixed, phi) for e in (eps, np.ones_like(eps)))
    return Line(1 / (C_0 * EPS_0 * math.sqrt(cap * cap0)), cap / cap0)
