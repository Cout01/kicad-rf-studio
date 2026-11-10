# SPDX-License-Identifier: GPL-3.0-or-later
"""The plane pairs' cavity modes (Stage 5 design 5.4; r2 2), in mm: a cell-centred finite-volume Laplacian with cut
cells on a raster anchored at the outline's minimum corner, which keeps mirror and rotation symmetry exact. Cell area
fractions are the mass and face open fractions the conductances; faces leaving the region carry no flux, so the edges
are Neumann (PMC), and via posts are Dirichlet. eigsh solves it in shift-invert with Weyl's mode count. numpy, scipy
and shapely only: the GUI process imports this module (Stage 1 3.1)."""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import shapely
from scipy.constants import c
from scipy.linalg import eigh
from scipy.sparse import coo_matrix, diags
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import eigsh
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.kicad.shapes import XY

H = 0.25  # mm, the raster's cell: slots of 2·H or more resolve (r2)
SLIVER = 1e-3  # a cut cell under this area fraction is dropped
ISLAND_MM2 = 1.0  # a component of the link graph under this area is dropped: it would be a spurious static mode
SIGMA = -1e-3  # mm⁻², eigsh's shift, just under the static mode, so that K − σM is positive definite
DC_HZ = 1e6  # gate E-E's "under 1 MHz": a mode below it is the static mode
C_MM = c * 1e3  # mm/s
PEACEMAN = 0.1985  # a lone node held at 0 is a post of radius PEACEMAN·h, Peaceman's well-block radius (r2 measured it)


@dataclass(frozen=True)
class Modes:
    """A region's modes up to f_max, its static modes first (one per component without a post)."""
    f: np.ndarray  # Hz, sorted, every eigenfrequency ≤ f_max; a static mode 0.0
    h: float  # the grid used, in mm
    v: np.ndarray  # the free cells × f's modes; a post's held cells are not free
    xy: np.ndarray  # the free cells' centres, mm


def solve(region: BaseGeometry, eps_r: float, f_max: float, posts: Sequence[tuple[XY, float]] = (),
          h: float = H) -> Modes:
    """The modes of `region` between two plates with `eps_r` between them, up to `f_max` (Hz), on a raster of `h` mm.
    `posts` are vias, each its centre and barrel radius r in mm, held at 0 (design 5.4, r2's option (c)): for r < h
    the nearest cell, its links scaled by α = ln(1/PEACEMAN)/ln(h/r); for r ≥ h the cells whose centres lie within r,
    or the nearest when none does. The static mode's eigenvalue is round-off, about 1e-15 mm⁻² or about 1 kHz: every
    mode under DC_HZ is stored as 0.0, so that no golden pins BLAS noise."""
    x0, y0, x1, y1 = region.bounds
    nx, ny = math.ceil((x1 - x0) / h - 1e-9), math.ceil((y1 - y0) / h - 1e-9)
    i, j = np.divmod(np.arange(nx * ny), ny)  # cell i·ny + j is [x0 + i·h, x0 + (i+1)·h] × [y0 + j·h, …]
    corner = np.column_stack([x0 + i * h, y0 + j * h])
    cells = shapely.box(corner[:, 0], corner[:, 1], corner[:, 0] + h, corner[:, 1] + h)
    shapely.prepare(region)
    a = shapely.contains_properly(region, cells).astype(float)  # the mass: only the boundary's cells are clipped
    cut = (a == 0) & shapely.intersects(region, cells)
    a[cut] = shapely.area(shapely.intersection(cells[cut], region)) / h**2
    keep = a >= SLIVER

    idx = np.arange(nx * ny).reshape(nx, ny)  # the links: x-neighbours, then y-neighbours
    p, q = np.r_[idx[:-1].ravel(), idx[:, :-1].ravel()], np.r_[idx[1:].ravel(), idx[:, 1:].ravel()]
    step = np.repeat([[0.0, h], [h, 0.0]], [(nx - 1) * ny, nx * (ny - 1)], axis=0)  # a face runs on from q's corner
    both = keep[p] & keep[q]
    p, q, step = p[both], q[both], step[both]
    ell = np.ones(len(p))  # the conductances, 1 between two whole cells
    part = (a[p] < 1 - 1e-9) | (a[q] < 1 - 1e-9)
    face = shapely.linestrings(np.stack([corner[q[part]], corner[q[part]] + step[part]], axis=1))
    seg = shapely.linestrings(np.stack([corner[p[part]], corner[q[part]]], axis=1) + h / 2)
    slot = shapely.get_num_geometries(shapely.intersection(seg, region.boundary)) >= 2  # out and back between centres
    ell[part] = np.where(slot, 0.0, shapely.length(shapely.intersection(face, region)) / h)
    linked = ell > 0
    p, q, ell = p[linked], q[linked], ell[linked]

    _, comp = connected_components(coo_matrix((ell, (p, q)), shape=(nx * ny,) * 2), directed=False)
    free = keep & (np.bincount(comp, weights=a)[comp] * h * h >= ISLAND_MM2)  # islands give spurious static modes
    n = int(free.sum())
    if n == 0:
        return Modes(np.zeros(0), h, np.zeros((0, 0)), np.zeros((0, 2)))

    centre = corner + h / 2
    held = np.zeros(nx * ny, bool)  # the posts' cells, at 0
    # ponytail: each post scans every cell, about 23 ms a post at 1.5 M cells; a ±r/h window if stitched boards drag
    for xy, r in posts:
        d2 = np.where(free, ((centre - xy) ** 2).sum(axis=1), np.inf)
        disc = (d2 <= r * r) & (r >= h)  # r ≥ h: the cells whose centres lie within r, and no α
        if not disc.any():
            disc[np.argmin(d2)] = True  # the nearest cell, the first index on a tie
        disc &= ~held  # a node already held takes nothing more
        if r < h:  # alone the node is a post of radius PEACEMAN·h: α makes it r
            ell[disc[p] | disc[q]] *= math.log(1 / PEACEMAN) / math.log(h / r)
        held |= disc

    row = np.cumsum(free) - 1  # a free cell's row in K
    inside = free[p]  # a link's two cells share their component
    pa, qa, w = row[p[inside]], row[q[inside]], ell[inside] / h**2
    K = coo_matrix((np.r_[w, w, -w, -w], (np.r_[pa, qa, pa, qa], np.r_[pa, qa, qa, pa])), shape=(n, n)).tocsr()
    out = ~held[free]  # the held nodes leave K and M: their links stay on their neighbours' diagonals
    K = K[out][:, out]
    free &= ~held
    n = int(free.sum())
    M = diags(a[free], format="csr")

    kk = 2 * math.pi * f_max * math.sqrt(eps_r) / C_MM  # mm⁻¹
    k = math.ceil(1.3 * (region.area * kk**2 + region.length * kk) / (4 * math.pi)) + 8  # Weyl, with the edges' term
    if k >= n - 1:
        lam, v = eigh(K.toarray(), M.toarray())
    else:
        # ponytail: the fixed start gives a rerun the same bits while ARPACK asks for no random restart, which scipy
        # 1.17+ draws unseeded; none of gate E-E's solves asks. rng=0 pins it once pyproject requires scipy >= 1.17.
        lam, v = eigsh(K, k, M=M, sigma=SIGMA, which="LM", v0=np.ones(n))
        while lam.max() < kk**2 and k < n - 2:
            k = min(2 * k, n - 2)
            lam, v = eigsh(K, k, M=M, sigma=SIGMA, which="LM", v0=np.ones(n))
    order = np.argsort(lam)
    f = C_MM * np.sqrt(np.maximum(lam[order], 0)) / (2 * math.pi * math.sqrt(eps_r))
    f[f < DC_HZ] = 0.0
    up_to = f <= f_max
    return Modes(f[up_to], h, v[:, order[up_to]], centre[free])
