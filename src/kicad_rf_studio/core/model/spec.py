# SPDX-License-Identifier: GPL-3.0-or-later
"""The model spec (spec 3.3, C-19): the plain JSON from which a worker builds the openEMS model without shapely, its
hash, and verify's model (spec 7.6). Lengths are in mm, frequencies in Hz, times in s and conductivities in S/m."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from bisect import bisect_left, bisect_right
from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np
import scipy.constants
import shapely
from scipy.optimize import nnls
from shapely.geometry import GeometryCollection, MultiPolygon

from kicad_rf_studio.core.geometry.copper import clean, split_holes
from kicad_rf_studio.core.geometry.lid import snap_lid
from kicad_rf_studio.core.geometry.mask import smeared_epsilon
from kicad_rf_studio.core.geometry.region import band
from kicad_rf_studio.core.kicad.tracer import signal_layer
from kicad_rf_studio.core.kicad.values import bypass, part_kind, part_value, port_value
from kicad_rf_studio.core.mesh.rule import RATIO
from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.csx import PML_CELLS
from kicad_rf_studio.core.model.parts import COPPER
from kicad_rf_studio.core.model.ports import _pad
from kicad_rf_studio.core.model.readers import c_box
from kicad_rf_studio.core.project import antenna, copper_model, pulse_band
from kicad_rf_studio.stoprule import FLAT_S, WINDOW_S, flat_window, stop_window

if TYPE_CHECKING:
    from pathlib import Path

    from shapely.geometry import Polygon
    from shapely.geometry.base import BaseGeometry

    from kicad_rf_studio.core.geometry import Geometry
    from kicad_rf_studio.core.geometry.zstack import Slab
    from kicad_rf_studio.core.kicad.board import Board
    from kicad_rf_studio.core.mesh import Mesh

EPS0 = scipy.constants.epsilon_0  # F/m
# ponytail: stable through k 0.55 on lpf915's L1 cell at a rule mesh's dielectric interface, 10 ns at openEMS's own
# dt (P0-B, 2026-10-25)
K_MAX = 0.45  # verify's limit on k = dt/(2·√(L·C)) of an inductor's cell (C-37)


def pulse(f1: float, f2: float, t_max: float) -> dict:
    """The pulse of spec 5.8 over the band (f1, f2), in Hz: a sine at fm, the band's middle, under a Gaussian of fw,
    its half-width, centred on t0 = 9/(2π·fw) and cut at 2·t0. `expr` is the pulse in openEMS's syntax and `t_max`
    the run's T_max, in s (design 5.4)."""
    fm, fw = (f1 + f2) / 2, (f2 - f1) / 2
    t0 = 9 / (2 * math.pi * fw)
    return {"f1": f1, "f2": f2, "t0": t0, "t_max": t_max,
            "expr": f"sin(2*pi*{fm:.12g}*(t-{t0:.12g}))*exp(-(2*pi*{fw:.12g}*t/3-3)^2)*(t<{2 * t0:.12g})"}


def antenna_t_max(f_lo: float, f_hi: float) -> float:
    """An antenna's default T_max in s (Stage 3 design 5.4, A-28): 2·t0 + 60/f0 of its band's pulse (pulse_band,
    pulse), f0 the band's centre, rounded up to a whole ns."""
    return math.ceil((2 * pulse(*pulse_band(f_lo, f_hi), 0)["t0"] + 60 / ((f_lo + f_hi) / 2)) * 1e9) / 1e9


def dc_pulse(f_max: float, t_max: float, window_s: float) -> dict:
    """An SI project's pulse (Stage 4 design 5.4): openEMS's Gaussian with f0 = 0 and fc = f_max as a custom expression,
    exp(−(2π·f_max·t/3 − 3)²) cut at 2·t0, t0 = 9/(2π·f_max), which build_csx passes as v1's with f2 = f_max. f1 is 0:
    the DC point is measured. `window_s` is the residual's window (stop_window), and "flat_s" is FLAT_S + (window_s −
    WINDOW_S). A residual window W holds the residual at its last peak for W, so a flat window under W would call every
    SI run flat."""
    t0 = 9 / (2 * math.pi * f_max)
    return {"f1": 0.0, "f2": f_max, "t0": t0, "t_max": t_max, "window_s": window_s,
            "flat_s": FLAT_S + (window_s - WINDOW_S), "expr": f"exp(-(2*pi*{f_max:.12g}*t/3-3)^2)*(t<{2 * t0:.12g})"}


def round_trip(length_mm: float, eps_eff: float) -> float:
    """A line's round trip in s, from its length and its 2D εeff (Stage 4 design 5.4)."""
    return 2 * length_mm * 1e-3 * math.sqrt(eps_eff) / scipy.constants.c


def si_t_max(f_max: float, round_trip_s: float) -> float:
    """An SI project's default T_max in s (Stage 4 design 5.4): the pulse's length 2·t0, plus 6 of the longest round
    trips, plus 2 ns, rounded up to a whole ns as antenna_t_max does (A-28); and at least the pulse plus the
    residual's window w = stop_window(round_trip_s), which holds the pulse's 0 dB peak, the flat window dc_pulse writes
    and 1 ns to settle, rounded up likewise, so that a level held on a short route ends flat, not at T_max (plan 1's
    open issue 4): 9 ns at 10 GHz with the 2 ns window, where plan 1's 10 ns (100 mm) and 25 ns (300 mm) stand."""
    t0, w = 9 / (2 * math.pi * f_max), stop_window(round_trip_s)
    return max(math.ceil((2 * t0 + 6 * round_trip_s + 2e-9) * 1e9),
               math.ceil((2 * t0 + w + FLAT_S + (w - WINDOW_S) + 1e-9) * 1e9)) / 1e9


def excitation(project: dict) -> dict:
    """pulse() over the band (f1, f2) of `project` (project.json), run to the project's T_max; an antenna's also holds
    its flat window "flat_s": project.json's flat_s when it sets one (gate P3-C's widened window), else flat_window() of
    its f0 (Stage 3 design 5.4)."""
    exc = pulse(*band(project), project["t_max_s"])
    return {**exc, "flat_s": project.get("flat_s") or flat_window(project["f0_hz"])} if antenna(project) else exc


def with_pml(lines: list[float]) -> list[float]:
    """`lines` (ascending, mm) with PML_CELLS lines added past each end at that end's outer cell, quantised to 1e-6 mm
    (design 5.2)."""
    lo, hi = lines[1] - lines[0], lines[-1] - lines[-2]
    return ([round(lines[0] - k * lo, 6) for k in range(PML_CELLS, 0, -1)] + list(lines)
            + [round(lines[-1] + k * hi, 6) for k in range(1, PML_CELLS + 1)])


def air_box(mesh: Mesh, gap: float, cell: float, pml: bool) -> Mesh:
    """`mesh` (an antenna's, wall to wall around the board) with each axis graded at RATIO up to `cell` through `gap` mm
    of air past both its ends, the PML's inner edge (Stage 3 design 5.2, 5.3), then with_pml when `pml`; on the 1e-6 mm
    grid. smooth_mesh_lines only adds lines, so the board's stay, and so do the Mesh's edges and exempt pairs."""
    def graded(old: np.ndarray) -> np.ndarray:
        lines = [round(float(v), 6) for v in smooth_mesh_lines(np.r_[old, old[0] - gap, old[-1] + gap], cell, RATIO)]
        return np.array(with_pml(lines) if pml else lines)

    return replace(mesh, x=graded(mesh.x), y=graded(mesh.y), z=graded(mesh.z))


PML_CLEAR = 2  # the cells just inside the PML's inner edge that hold no structure either (design 5.2)


def metal_in_pml(spec: dict) -> list[tuple[str, dict]]:
    """E_METAL_IN_PML (Stage 3 design 5.2), for each face of a `"boundary": "pml_8"` spec that metal, dielectric or a
    lumped element reaches within the PML or the PML_CLEAR cells just inside its inner edge. That band holds every
    coordinate below line PML_CELLS + PML_CLEAR, counted from either end of its axis; a coordinate on that line
    passes. Params: the axis, the farthest coordinate and that line, in mm. [] for any other spec."""
    if spec.get("boundary") != "pml_8":
        return []
    pec, k = spec["metal"], PML_CELLS + PML_CLEAR
    solids = (*(s for m in spec["materials"] for s in m["solids"]), *pec["copper"], *pec["lid"]["walls"])
    xyz = [(s["x"], s["y"], s["z"]) for s in solids]
    if (plate := pec["lid"]["plate"]) is not None:
        xyz.append((plate["x"], plate["y"], [plate["z"]]))
    for rod in (*pec["cylinders"], *pec["curves"]):  # a curve is a rod of radius 0
        (x, y), r = rod["at"], rod.get("r", 0.0)
        xyz.append(([x - r, x + r], [y - r, y + r], rod["z"]))
    xyz += [list(zip(e["start"], e["stop"])) for e in (*spec["ports"], *spec["grid"])]  # probes skipped: P0's own
    out = []
    for n, axis in enumerate("xyz"):
        lines, coords = spec["mesh"][axis], [c for e in xyz for c in e[n]]
        low, high = min(coords, default=math.inf), max(coords, default=-math.inf)
        for at, limit, past in ((low, lines[k], low < lines[k]), (high, lines[-1 - k], high > lines[-1 - k])):
            if past:
                out.append(("E_METAL_IN_PML", {"axis": axis, "at_mm": f"{at:.3f}", "limit_mm": f"{limit:.3f}"}))
    return out


def cell_split(spec: dict) -> tuple[int, int, int]:
    """An antenna mesh's nodes as cost counts cells, (board, air, PML) (Stage 3 design 5.9): the PML's, the nodes
    openEMS's UPML updates, PML_CELLS + 1 lines in from each face, none without "boundary"; the board's, the nodes
    inside the box of every material solid (the dielectric, the masks included); the air's, the rest."""
    solids = [s for m in spec["materials"] for s in m["solids"]]
    total = inner = board = 1
    for axis in "xyz":
        lines, coords = spec["mesh"][axis], [c for s in solids for c in s[axis]]
        total *= len(lines)
        inner *= len(lines) - 2 * (PML_CELLS + 1)
        board *= bisect_right(lines, max(coords)) - bisect_left(lines, min(coords))  # the lines inside, inclusive
    pml = total - inner if "boundary" in spec else 0
    return board, total - board - pml, pml


def kappa(eps_r: float, tan_d: float | None, f0: float) -> float:
    """The conductivity that gives a dielectric of εr `eps_r` the loss tangent `tan_d` at `f0` (spec 5.3: a constant
    κ, set at f0); 0 when the stackup gives no loss tangent."""
    return 0.0 if tan_d is None else 2 * math.pi * f0 * EPS0 * eps_r * tan_d


DEBYE_F_REF = 1e9  # Hz: where a stackup's εr and tan δ are taken to hold
DEBYE_DECADES = 2  # the fit's band, f_max/100 to f_max: gate P4-D's 0.1 GHz to f_max at 10 GHz (Stage 4 design 5.11)


def debye(eps_r: float, tan_d: float, f_max: float) -> dict:
    """An SI dielectric's Debye model (Stage 4 design 5.3), a model spec material's "debye": ε(f) = ε∞ + Σ Δε/(1 +
    j·f/f_relax), one pole a decade at f_max/10^k, k = DEBYE_DECADES down to 0. It is fitted in the Djordjevic–Sarkar
    manner to `eps_r` and `tan_d` at DEBYE_F_REF, ε″ = εr·tan δ flat and ε′ = εr − (2/π)·ε″·ln(f/DEBYE_F_REF), on 61
    log-spaced points from the first pole to f_max, its ε″ rows weighted 1/tan δ, by non-negative least squares: every
    Δε ≥ 0, a pole that takes 0 dropped, and no κ, so no DC loss. ValueError ("Debye") for a tan δ of 0 or less, and for
    an ε∞ under 1, a fit below vacuum."""
    # ponytail: one pole a decade ripples tan δ by about 6 % on FR-4 (−4.7 to +4.8 % against Djordjevic–Sarkar's
    # ε″/√ε′); gate P4-D may ask for poles past the band's edges (4 from f_max/10^2.2 to f_max·10^0.2 read 3.9 %),
    # at a higher cell weight
    if tan_d <= 0:
        raise ValueError(f"a Debye fit needs a loss tangent above 0, not {tan_d}")
    poles = [f_max / 10 ** k for k in range(DEBYE_DECADES, -1, -1)]
    f = np.geomspace(poles[0], f_max, 61)
    cols = [1 / (1 + 1j * f / p) for p in poles]
    a = np.vstack([np.r_[np.ones_like(f), np.zeros_like(f)], *(np.r_[c.real, -c.imag / tan_d] for c in cols)]).T
    b = np.r_[eps_r - 2 / math.pi * eps_r * tan_d * np.log(f / DEBYE_F_REF), np.full(f.size, eps_r)]
    x, _ = nnls(a, b)
    if x[0] < 1:
        raise ValueError(f"a Debye fit below vacuum: ε∞ {x[0]:.3f} under 1 (εr {eps_r}, tan δ {tan_d})")
    keep = x[1:] > 0
    return {"eps_inf": float(x[0]), "delta": x[1:][keep].tolist(),
            "f_relax_hz": [p for p, k in zip(poles, keep) if k]}


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


def far_field_box(project: dict, board: Board, geom: Geometry) -> dict:
    """An antenna's far-field box as the model spec's "nf2ff" holds it (Stage 3 design 5.5): project.json's
    far_field.f_hz about the board's centre, its outline's bounds' (else geom's crop's) centre at the stack's
    mid-height, to 1e-6 mm. model_spec writes it when no port is a part; verify, whose one job holds the network as
    applied, always (verify_spec)."""
    x0, y0, x1, y1 = (geom.region.crop if board.outline is None else board.outline).bounds
    centre = ((x0 + x1) / 2, (y0 + y1) / 2, (geom.zs[0].z0 + geom.zs[-1].z1) / 2)
    return {"f_hz": project["far_field"]["f_hz"], "center": [round(v, 6) for v in centre]}


def model_spec(project: dict, board: Board, geom: Geometry, mesh: Mesh, ports: list[dict], grid: list[dict]) -> dict:
    """The model of `geom` on `mesh` as plain JSON (C-19): the mesh's own lines (X-6), the excitation, the materials,
    the metal, `ports` (the place() entries in job order) and `grid` (the grid_entry() entries); then the antenna keys,
    only for an antenna (Stage 3 design 5.2–5.5): "boundary", "pml_8" when project.json's boundary is; "copper",
    "sheet" when its copper is (copper_model, design 5.3); "nf2ff" when no port is a part, far_field_box(); and "join"
    when the antenna has join pads, a box per pad: its bounds grown by d in x and y, from the lowest copper slab's z0 to
    the highest's z1, to 1e-6 mm.
    The materials, in this order: each dielectric slab, bottom up, at its εr and its κ at f0, and each copper slab
    between two dielectrics, at their mean εr and mean κ (C-8), all on the board (the crop cut to its outline) and
    named by their place in the list; then per mask, F first, its gap fill in the outer copper's slab and its coat
    smeared over the first z-cell dz0 outside it (C-6). The stackup's mask slabs are never materials (X-3). A material
    with no solids is left out, as is one of no thickness under sheet copper, and each is at priority 10 + its place
    in the list: openEMS breaks ties arbitrarily.
    The metal: every copper piece, solid (C-5) or, under sheet copper, a sheet, and the convex hull of the two pads of
    each part whose role is copper (spec 5.7), cut back from other nets' copper on its layer to the pads' own
    clearance, each over its layer's slab; the solid rods as cylinders, the others as curves on the mesh lines (C-40);
    the lid's plate on the z line nearest its top, and its walls up to it (C-39, X-5). Every solid is cut by
    split_holes. Raises E_UNKNOWN_PAD for a copper part's pad that does not exist."""
    f0, zs, crop, dz = project["f0_hz"], geom.zs, geom.region.crop, mesh.dz0
    sheet = antenna(project) and copper_model(project) == "sheet"

    def k(s: Slab) -> float:
        return kappa(s.eps_r, s.tan_d, f0)

    outline = crop if board.outline is None else board.outline
    area = clean(outline, crop)
    layers = [(s.eps_r, k(s), s) for s in zs if s.kind == "dielectric"]
    layers += [((a.eps_r + b.eps_r) / 2, (k(a) + k(b)) / 2, s)
               for a, s, b in zip(zs, zs[1:], zs[2:]) if s.kind == "copper" and a.kind == b.kind == "dielectric"]
    mats = [("substrate", eps, kap, _solids(area, s.z0, s.z1)) for eps, kap, s in layers]
    for m in geom.masks.values():
        km = kappa(m.eps_m, (zs[-1] if m.side == "F" else zs[0]).tan_d, f0)
        coat = (m.z_coat0, round(m.z_coat0 + dz, 6)) if m.side == "F" else (round(m.z_coat0 - dz, 6), m.z_coat0)
        mats += [(f"mask_{m.side}_fill", m.eps_m, km, _solids(m.gap_fill, *m.z_fill)),
                 (f"mask_{m.side}_coat", smeared_epsilon(m.t_m, m.eps_m, dz), km * m.t_m / dz, _solids(m.coat, *coat))]
    # an antenna's sheet copper leaves its slab and mask fill no thickness; v1's materials stay as they are, 0 mm copper
    # included
    materials = [{"name": f"substrate_{i}" if name == "substrate" else name, "eps": eps, "kappa": kap,
                  "priority": 10 + i, "solids": solids}
                 for i, (name, eps, kap, solids) in enumerate(
                     x for x in mats if x[3] and not (sheet and x[3][0]["z"][0] == x[3][0]["z"][1]))]

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
    spec = {"mesh": {"x": mesh.x.tolist(), "y": mesh.y.tolist(), "z": mesh.z.tolist()},
            "excitation": excitation(project),
            "materials": materials,
            "metal": {"copper": copper, "lid": lid,
                      "cylinders": [{"at": list(r.at), "r": r.radius, "z": [r.z0, r.z1]} for r in geom.rods if r.solid],
                      "curves": [{"at": list(r.at), "z": [r.z0, r.z1]} for r in mesh.snapped_rods if not r.solid]},
            "ports": ports,
            "grid": grid}
    if antenna(project):
        if project["boundary"] == "pml_8":
            spec["boundary"] = "pml_8"
        if sheet:
            spec["copper"] = "sheet"
        if not any(q["part"] for q in ports):
            spec["nf2ff"] = far_field_box(project, board, geom)
        if boxes := [_pad(board, name).polygon.bounds for name in project["antenna"]["join"]]:
            d, z0, z1 = mesh.d, min(z for z, _ in cu.values()), max(z for _, z in cu.values())
            spec["join"] = [[[round(v, 6) for v in (x0 - d, y0 - d, z0)], [round(v, 6) for v in (x1 + d, y1 + d, z1)]]
                            for x0, y0, x1, y1 in boxes]
    return spec


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


def verify_spec(spec: dict, parts: dict[str, dict], dump: Path, dt: float, *, far_field: dict | None = None) -> dict:
    """verify's model (spec 7.6, C-36, C-37, D-45): a copy of the run's `spec` whose part ports, all lumped, leave
    `ports` for `grid`, after the run's own grid parts, each at its value in `parts` (project.json's parts by ref), on
    the same lines: in one cell of its box along the box's axis, at its middle and in its copper slab, a C or an R
    across the box's whole width and an L one cell wide, joined to the box's two ends by PEC fill of the cell's width
    in `metal.copper`. The cell's own capacitance, from the operator dump `dump` at the time step `dt` (s), is added to
    a C (a grid C replaces it) and is an L's explicit C (without one, openEMS 0.37 lowers it); an R keeps it. Raises,
    part by part in port order, E_VERIFY_VALUE for a part that is not a C, L or R whose value reads, E_VERIFY_DUMP
    when `dump` is missing, then for an L E_VERIFY_K when k = dt/(2·√(L·C)) is above K_MAX.
    For an antenna (Stage 3 design 5.5, 5.7), `far_field` is its far-field box (far_field_box), which the copy records
    as "nf2ff", and a part whose value is a bypass (values.bypass) and that has no S2P file leaves the grid: at 0 Ω it
    is copper over its whole port box, open it is left out. A placeholder given an S2P file is a fitted part, refused
    as any value verify cannot place."""
    out = copy.deepcopy(spec)
    lines, copper = [out["mesh"][a] for a in "xyz"], out["metal"]["copper"]
    moved, out["ports"] = [q for q in out["ports"] if q["part"]], [q for q in out["ports"] if not q["part"]]
    for port in moved:
        ref = port["name"]
        kind, text = part_kind(ref), parts[ref]["value"]
        # per axis, the smaller and the larger end: a box can start at its higher end
        lo, hi = ([f(a, b) for a, b in zip(port["start"], port["stop"])] for f in (min, max))
        if far_field is not None and parts[ref]["s2p"] is None and (z := bypass(ref, text)) is not None:
            if z == 0:  # shorted: copper over the whole port box
                copper.append({"x": [lo[0], hi[0], hi[0], lo[0]], "y": [lo[1], lo[1], hi[1], hi[1]],
                               "z": [lo[2], hi[2]]})
            continue  # an open part leaves nothing, and neither reads the dump
        if (value := port_value(ref, text)) is None:
            raise KrsError("E_VERIFY_VALUE", ref=ref, value=text)
        if not dump.is_file():
            raise KrsError("E_VERIFY_DUMP", path=str(dump))
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
    if far_field is not None:
        out["nf2ff"] = far_field
    return out
