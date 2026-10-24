# SPDX-License-Identifier: GPL-3.0-or-later
"""The model spec (spec 3.3, C-19): the plain JSON from which a worker builds the openEMS model without shapely, its
hash, and verify's model (spec 7.6). Lengths are in mm, frequencies in Hz, times in s and conductivities in S/m."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from bisect import bisect_left, bisect_right
from typing import TYPE_CHECKING

import scipy.constants
import shapely
from shapely.geometry import GeometryCollection, MultiPolygon

from kicad_rf_studio.core.geometry.copper import clean, split_holes
from kicad_rf_studio.core.geometry.lid import snap_lid
from kicad_rf_studio.core.geometry.mask import smeared_epsilon
from kicad_rf_studio.core.geometry.region import band
from kicad_rf_studio.core.kicad.tracer import signal_layer
from kicad_rf_studio.core.kicad.values import part_kind, part_value, port_value
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import COPPER
from kicad_rf_studio.core.model.ports import _pad
from kicad_rf_studio.core.model.readers import c_box

if TYPE_CHECKING:
    from pathlib import Path

    from shapely.geometry import Polygon
    from shapely.geometry.base import BaseGeometry

    from kicad_rf_studio.core.geometry import Geometry
    from kicad_rf_studio.core.geometry.zstack import Slab
    from kicad_rf_studio.core.kicad.board import Board
    from kicad_rf_studio.core.mesh import Mesh

EPS0 = scipy.constants.epsilon_0  # F/m
# ponytail: stable up to k 0.48 at openEMS's own dt on a uniform grid with equal edges (r3 3.6); plan 5 confirms it
K_MAX = 0.45  # verify's limit on k = dt/(2·√(L·C)) of an inductor's cell (C-37)


def excitation(project: dict) -> dict:
    """The pulse of spec 5.8 over the band (f1, f2) of `project` (project.json): a sine at fm, the band's middle,
    under a Gaussian of fw, its half-width, centred on t0 = 9/(2π·fw) and cut at 2·t0. `expr` is the pulse in
    openEMS's syntax and `t_max` the project's T_max."""
    f1, f2 = band(project)
    fm, fw = (f1 + f2) / 2, (f2 - f1) / 2
    t0 = 9 / (2 * math.pi * fw)
    return {"f1": f1, "f2": f2, "t0": t0, "t_max": project["t_max_s"],
            "expr": f"sin(2*pi*{fm:.12g}*(t-{t0:.12g}))*exp(-(2*pi*{fw:.12g}*t/3-3)^2)*(t<{2 * t0:.12g})"}


def kappa(eps_r: float, tan_d: float | None, f0: float) -> float:
    """The conductivity that gives a dielectric of εr `eps_r` the loss tangent `tan_d` at `f0` (spec 5.3: a constant
    κ, set at f0); 0 when the stackup gives no loss tangent."""
    return 0.0 if tan_d is None else 2 * math.pi * f0 * EPS0 * eps_r * tan_d


def grid_entry(placed: dict, part: dict) -> dict:
    """The grid element of `part`, as project.json holds it, on its port box `placed` (place()): its value as "R" or
    "C" by its kind, the other None. Raises E_GRID_KIND for a part that is not a C or an R, and E_PART_VALUE for a
    value that does not read."""
    ref, kind = part["ref"], part_kind(part["ref"])
    if kind not in ("C", "R"):
        raise KrsError("E_GRID_KIND", ref=ref)
    if (value := part_value(ref, part["value"])) is None:
        raise KrsError("E_PART_VALUE", ref=ref, value=part["value"])
    return {**placed, "R": None, "C": None, kind: value}


def _ring(p: Polygon) -> dict:
    """The exterior of `p` without its closing point, as {"x": [...], "y": [...]}."""
    x, y = shapely.get_coordinates(p.exterior)[:-1].T.tolist()
    return {"x": x, "y": y}


def _solids(g: BaseGeometry, z0: float, z1: float) -> list[dict]:
    """Every polygon of `g`, cut by split_holes (AddLinPoly takes no holes), as a solid from `z0` to `z1`."""
    return [{**_ring(q), "z": [z0, z1]} for p in shapely.get_parts(g) for q in split_holes(p)]


def model_spec(project: dict, board: Board, geom: Geometry, mesh: Mesh, ports: list[dict], grid: list[dict]) -> dict:
    """The model of `geom` on `mesh` as plain JSON (C-19): the mesh's own lines (X-6), the excitation, the materials,
    the metal, `ports` (the place() entries in job order) and `grid` (the grid_entry() entries).
    The materials, in this order: each dielectric slab, bottom up, at its εr and its κ at f0, and each copper slab
    between two dielectrics, at their mean εr and mean κ (C-8), all on the board (the crop cut to its outline) and
    named by their place in the list; then per mask, F first, its gap fill in the outer copper's slab and its coat
    smeared over the first z-cell dz0 outside it (C-6). The stackup's mask slabs are never materials (X-3). A material
    with no solids is left out, and each is at priority 10 + its place in the list: openEMS breaks ties arbitrarily.
    The metal: every copper piece, solid (C-5), and the convex hull of the two pads of each part whose role is copper
    (spec 5.7), cut back from other nets' copper on its layer to the pads' own clearance, each over its layer's slab;
    the solid rods as cylinders, the others as curves on the mesh lines (C-40); the lid's plate on the z line nearest
    its top, and its walls up to it (C-39, X-5). Every solid is cut by split_holes. Raises E_UNKNOWN_PAD for a copper
    part's pad that does not exist."""
    f0, zs, crop, dz = project["f0_hz"], geom.zs, geom.region.crop, mesh.dz0

    def k(s: Slab) -> float:
        return kappa(s.eps_r, s.tan_d, f0)

    area = clean(crop if board.outline is None else board.outline, crop)
    layers = [(s.eps_r, k(s), s) for s in zs if s.kind == "dielectric"]
    layers += [((a.eps_r + b.eps_r) / 2, (k(a) + k(b)) / 2, s)
               for a, s, b in zip(zs, zs[1:], zs[2:]) if s.kind == "copper" and a.kind == b.kind == "dielectric"]
    mats = [("substrate", eps, kap, _solids(area, s.z0, s.z1)) for eps, kap, s in layers]
    for m in geom.masks.values():
        km = kappa(m.eps_m, (zs[-1] if m.side == "F" else zs[0]).tan_d, f0)
        coat = (m.z_coat0, round(m.z_coat0 + dz, 6)) if m.side == "F" else (round(m.z_coat0 - dz, 6), m.z_coat0)
        mats += [(f"mask_{m.side}_fill", m.eps_m, km, _solids(m.gap_fill, *m.z_fill)),
                 (f"mask_{m.side}_coat", smeared_epsilon(m.t_m, m.eps_m, dz), km * m.t_m / dz, _solids(m.coat, *coat))]
    materials = [{"name": f"substrate_{i}" if name == "substrate" else name, "eps": eps, "kappa": kap,
                  "priority": 10 + i, "solids": solids}
                 for i, (name, eps, kap, solids) in enumerate(x for x in mats if x[3])]

    cu = {s.copper: (s.z0, s.z1) for s in zs if s.kind == "copper"}
    copper = [solid for pc in geom.pieces for solid in _solids(pc.polygon, *cu[pc.layer])]
    for part in (*project["chain"]["series"], *project["chain"]["shunt"], *project["others"]):
        if part["role"] == COPPER:
            pads = [_pad(board, name) for name in part["pads"]]
            layer, both = signal_layer(board, pads[0]), GeometryCollection([p.polygon for p in pads])
            # a pour can reach between the pads, under the part's body, where a copper hull would short it to them
            # ponytail: copper that runs right across between the pads cuts the hull in two, leaving the part open
            near = [pc.polygon for pc in geom.pieces if pc.layer == layer and pc.net not in {p.net for p in pads}]
            gap = min((q.distance(both) for q in near), default=0.0)
            copper += _solids(clean(both.convex_hull.difference(MultiPolygon(near).buffer(gap)), crop), *cu[layer])
    lid = {"plate": None, "walls": []}
    if geom.lid is not None:
        top = snap_lid(geom.lid, mesh.z)
        lid = {"plate": {**_ring(top.plate), "z": top.z1}, "walls": _solids(top.walls, top.z0, top.z1)}
    return {"mesh": {"x": mesh.x.tolist(), "y": mesh.y.tolist(), "z": mesh.z.tolist()},
            "excitation": excitation(project),
            "materials": materials,
            "metal": {"copper": copper, "lid": lid,
                      "cylinders": [{"at": list(r.at), "r": r.radius, "z": [r.z0, r.z1]} for r in geom.rods if r.solid],
                      "curves": [{"at": list(r.at), "z": [r.z0, r.z1]} for r in mesh.snapped_rods if not r.solid]},
            "ports": ports,
            "grid": grid}


def spec_hash(spec: dict) -> str:
    """The model hash (C-19, spec 7.8): the sha256 of `spec` as JSON with sorted keys and no spaces. The spec holds
    neither the excited port, nor the threads, nor any path, nor a port part's value, so a retune keeps the results;
    the grid's values are in it."""
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _cell(lines: list[float], lo: float, hi: float) -> tuple[float, float]:
    """The cell (lines[i], lines[i + 1]) of `lines` (ascending) whose lines[i] is the last line at or below the middle
    of `lo`–`hi`, moved inside `lo`–`hi`."""
    i = bisect_right(lines, (lo + hi) / 2) - 1
    i = min(max(i, bisect_left(lines, lo)), bisect_right(lines, hi) - 2)
    return lines[i], lines[i + 1]


def verify_spec(spec: dict, parts: dict[str, dict], dump: Path, dt: float) -> dict:
    """verify's model (spec 7.6, C-36, C-37, D-45): a copy of the run's `spec` whose part ports, all lumped, leave
    `ports` for `grid`, after the run's own grid parts, each at its value in `parts` (project.json's parts by ref), on
    the same lines: in one cell of its box along the box's axis, at its middle and in its copper slab, a C or an R
    across the box's whole width and an L one cell wide, joined to the box's two ends by PEC fill of the cell's width
    in `metal.copper`. The cell's own capacitance, from the operator dump `dump` at the time step `dt` (s), is added to
    a C (a grid C replaces it) and is an L's explicit C (without one, openEMS 0.37 lowers it); an R keeps it. Raises,
    part by part in port order, E_VERIFY_VALUE for a part that is not a C, L or R whose value reads, E_VERIFY_DUMP
    when `dump` is missing, then for an L E_VERIFY_K when k = dt/(2·√(L·C)) is above K_MAX."""
    out = copy.deepcopy(spec)
    lines, copper = [out["mesh"][a] for a in "xyz"], out["metal"]["copper"]
    moved, out["ports"] = [q for q in out["ports"] if q["part"]], [q for q in out["ports"] if not q["part"]]
    for port in moved:
        ref = port["name"]
        kind, text = part_kind(ref), parts[ref]["value"]
        if (value := port_value(ref, text)) is None:
            raise KrsError("E_VERIFY_VALUE", ref=ref, value=text)
        if not dump.is_file():
            raise KrsError("E_VERIFY_DUMP", path=str(dump))
        # per axis, the smaller and the larger end: a box can start at its higher end
        lo, hi = ([f(a, b) for a, b in zip(port["start"], port["stop"])] for f in (min, max))
        p = "xyz".index(port["dir"])
        cell = [(lo[n], hi[n]) for n in range(3)]
        for n in (0, 1) if kind == "L" else (p,):  # D-45: a C or an R spans its box's width, an L one cell
            cell[n] = _cell(lines[n], lo[n], hi[n])
        start, stop = [e[0] for e in cell], [e[1] for e in cell]
        c = c_box(dump, lines, start, stop, p, dt)
        k = dt / (2 * math.sqrt(value * c)) if value * c > 0 else math.inf  # a C (or an L) of 0 reads as k inf
        if kind == "L" and k > K_MAX:
            raise KrsError("E_VERIFY_K", ref=ref, k=f"{k:.3g}", limit=f"{K_MAX:g}")
        values = {"C": {"R": None, "C": value + c}, "R": {"R": value, "C": None}, "L": {"R": None, "C": c, "L": value}}
        out["grid"].append({**port, "start": start, "stop": stop, **values[kind]})
        for span in ((lo[p], start[p]), (stop[p], hi[p])):  # along dir: from lo to the cell, from the cell to hi
            if span[0] < span[1]:
                (x0, x1), (y0, y1), z = (span if n == p else cell[n] for n in range(3))
                copper.append({"x": [x0, x1, x1, x0], "y": [y0, y0, y1, y1], "z": list(z)})
    return out
