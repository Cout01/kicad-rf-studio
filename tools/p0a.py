# SPDX-License-Identifier: GPL-3.0-or-later
"""P0-A, the coupon gate (spec 9.2; D-24, D-25; amendments A-1, A-2), part 1: the instrument. Each pad-less coupon is a
harness model (D-9): its project.json made by hand, the product's geometry, mesh and model spec, two vertical 50 Ω
lumped feeds at the line's ends, and a probe triplet at each section's cut (and a twin's midpoint); fit2d is computed,
never applied (D-29). The line constants come from the probe files by MSLPort's equations (A-1), the references from
KiCad's line formulas and cs2d in a 45 h box (D-25, A-2).

Dev-time only, like p0: the package never imports it."""
import math
import sys
from pathlib import Path

import numpy as np
import shapely
from scipy.constants import c as C0
from shapely.geometry import LineString, Point

import p0
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.cs2d import solve
from kicad_rf_studio.core.geometry import Geometry, build_geometry
from kicad_rf_studio.core.geometry.sections import cross_section
from kicad_rf_studio.core.geometry.zstack import substrate_h
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.mesh import Mesh, build_mesh
from kicad_rf_studio.core.mesh.gates import dt_floor_reference, edge_lint, fit2d, mesh_with_lint
from kicad_rf_studio.core.model.readers import read_probe
from kicad_rf_studio.core.model.spec import model_spec
from kicad_rf_studio.core.project import board_hash, make_project

sys.path.append(str(p0.ROOT / "tests"))  # kicad_lines: KiCad's line formulas, as the tests port them
from kicad_lines import cpwg, microstrip  # noqa: E402

COUPONS = ("coupon_ms", "coupon_ms_masked", "coupon_gcpw", "coupon_gcpw_masked", "coupon_dense", "coupon_gcpw_45",
           "coupon_gcpw_arc")
PAIRS = (("coupon_ms_masked", "coupon_ms"), ("coupon_gcpw_masked", "coupon_gcpw"))  # (masked, mask-free)
TWINS = ("coupon_gcpw_45", "coupon_gcpw_arc")  # against coupon_gcpw (D-27)
MIDPOINTS = {"coupon_gcpw_45": (107.071, 92.929), "coupon_gcpw_arc": (109.609, 101.464)}  # KiCad's frame; 45° there
BOX_REF = 45  # the 2D references' box, in substrate heights (D-14, D-25)
F0 = 915e6
BAND = (0.6e9, 2.8e9)  # the band of the report's min and max (D-25)
LIMITS = {"z0_pct": 5.0, "eeff_pct": 3.0, "shift_z0_pp": 0.5, "shift_eeff_pp": 1.0, "twin_pct": 5.0, "delta_pp": 1.0,
          "dt_ratio": 0.85}  # the floor itself is GATES["dt_floor"]


def _nearest(lines: np.ndarray, v: float) -> int:
    """The index of the line of `lines` nearest `v`."""
    return int(np.abs(lines - v).argmin())


def coupon_project(name: str, n: int) -> tuple[Board, dict]:
    """The board of the coupon `name` (tests/fixtures) and its project.json as `new` writes it, made by hand since `new`
    cannot trace a pad-less line (R-P2-8; tests/test_cli_cost.by_hand): the chain LINE alone, no part, no port, preset
    normal, mesh.n `n`."""
    path = p0.FIX / f"{name}.kicad_pcb"
    board = load_board(path)
    chain = {"start": "", "end": "", "nets": ["LINE"], "series": [], "shunt": []}
    project = make_project(path.as_posix(), board_hash(path), F0, board.stackup, classify(board), chain, [], [])
    project["mesh"]["n"] = n
    return board, project


def points(geom: Geometry, name: str) -> list[dict]:
    """The measured points of the coupon `name`, in the internal frame: each section's cut, on planes normal to its axis
    (label s<i>), then a twin's midpoint (MIDPOINTS) on x-normal planes across its line at 45° (label "mid")."""
    pts = [{"label": f"s{i}", "at": list(s.cut), "normal": s.axis, "theta": 0.0, "section": i}
           for i, s in enumerate(geom.sections)]
    if name in MIDPOINTS:
        x, y = MIDPOINTS[name]
        pts.append({"label": "mid", "at": [x, -y], "normal": "x", "theta": 45.0, "section": None})
    return pts


def probe_set(geom: Geometry, mesh: Mesh, point: dict) -> list[dict]:
    """The probe triplet at `point` (r7 §2.2, A-1), on planes normal to point["normal"] around its line k, the one
    nearest the point: voltage probes <label>_v0..2 (type 0) on the lines k−1, k and k+1, each on the line across
    nearest the strip's centre on its plane, from the strip's bottom face down to the top face of the copper under it;
    current probes <label>_i0..1 (type 1, norm_dir the normal's axis) on the duals between them, loops round the strip:
    across, from the dual outside its lowest line inside the strip to the dual outside its highest; in z, from the dual
    1.5 cells under its copper slab's bottom face to the dual 1.5 cells over its top. The strip on a plane is the
    plane's trace cut with the LINE piece holding the point. Every coordinate is a line or a dual, so that openEMS
    snaps each probe unambiguously."""
    a = "xy".index(point["normal"])
    b = 1 - a  # the in-plane axis across the normal
    along, across = (mesh.x, mesh.y)[a], (mesh.x, mesh.y)[b]
    k = _nearest(along, point["at"][a])
    line = next(pc.polygon for pc in geom.pieces if pc.net == "LINE" and pc.polygon.contains(Point(point["at"])))
    x0, y0, x1, y1 = geom.region.crop.bounds
    *_, under, cu = (s for s in geom.zs if s.kind == "copper")
    z, k0, k1 = mesh.z, _nearest(mesh.z, cu.z0), _nearest(mesh.z, cu.z1)
    z_lo, z_hi = (z[k0 - 2] + z[k0 - 1]) / 2, (z[k1 + 1] + z[k1 + 2]) / 2

    def at(u: float, v: float, w: float) -> list[float]:
        """The point `u` along the normal, `v` across it and at `w` in z, as [x, y, z]."""
        return [float(u), float(v), float(w)] if a == 0 else [float(v), float(u), float(w)]

    def strip(u: float) -> tuple[float, float]:
        """The strip's span across on the plane `u` along the normal."""
        # ponytail: one crossing per plane on the coupons; a line that folds back needs the crossing nearest the point
        bounds = line.intersection(LineString([(u, y0), (u, y1)] if a == 0 else [(x0, u), (x1, u)])).bounds
        return bounds[b], bounds[b + 2]

    probes = []
    for m, u in enumerate(along[k - 1:k + 2]):
        v = across[_nearest(across, sum(strip(u)) / 2)]
        probes.append({"name": f"{point['label']}_v{m}", "type": 0, "weight": 1, "start": at(u, v, cu.z0),
                       "stop": at(u, v, under.z1)})
    for m in range(2):
        u = (along[k - 1 + m] + along[k + m]) / 2
        lo, hi = strip(u)
        j = np.flatnonzero((across > lo) & (across < hi))  # the lines inside the strip
        probes.append({"name": f"{point['label']}_i{m}", "type": 1, "weight": 1, "norm_dir": a,
                       "start": at(u, (across[j[0] - 1] + across[j[0]]) / 2, z_lo),
                       "stop": at(u, (across[j[-1]] + across[j[-1] + 1]) / 2, z_hi)})
    return probes


def _ends(geom: Geometry) -> list[tuple[float, float]]:
    """The LINE track's two ends, sorted (the lower x first): the centres of its round caps, each fitted
    (x² + y² = 2ax + 2by + c) to the LINE copper's vertices within a track width of one of its two farthest vertices,
    which all lie on that cap. The copper's simplification only drops vertices, so a cap that lost its tip still gives
    its centre exactly, where the farthest vertex moved back by half a width misses it by 64 µm across (coupon_ms)."""
    v = shapely.get_coordinates(next(pc.polygon for pc in geom.pieces if pc.net == "LINE"))[:-1]
    d = np.linalg.norm(v[:, None] - v[None], axis=-1)
    ends = []
    for k in np.unravel_index(d.argmax(), d.shape):
        cap = v[d[k] <= geom.track_width]
        cx, cy, _ = np.linalg.lstsq(np.c_[2 * cap, np.ones(len(cap))], (cap ** 2).sum(1), rcond=None)[0]
        ends.append((float(cx), float(cy)))
    return sorted(ends)


def feeds(geom: Geometry, mesh: Mesh) -> list[dict]:
    """P1 and P2 (D-24): vertical 50 Ω lumped ports on the x and y lines nearest the LINE track's two ends (the 45°
    coupon's too), from the top face of the copper under the strip to the strip's bottom face, `nodes` [start, stop,
    start, stop] as in runs.calibration_spec; feeds, never parts."""
    *_, under, cu = (s for s in geom.zs if s.kind == "copper")
    ports = []
    for name, (x, y) in zip(("P1", "P2"), _ends(geom)):
        xy = [float(mesh.x[_nearest(mesh.x, x)]), float(mesh.y[_nearest(mesh.y, y)])]
        start, stop = [*xy, under.z1], [*xy, cu.z0]
        ports.append({"name": name, "kind": "lumped", "dir": "z", "start": start, "stop": stop,
                      "nodes": [start, stop, start, stop], "part": False})
    return ports


def coupon_model(name: str, n: int, edits: dict | None = None) -> tuple[pipeline.Model, Geometry, list[dict], int]:
    """The harness model of the coupon `name` at mesh.n `n` (D-24): its project (coupon_project) with p0.edit's
    `edits`, its geometry, the mesh with the edge lint (raising E_EDGE_LINT as mesh_with_lint does), the model spec of
    the two feeds plus "probes", every point's probe_set, and the timestep floor's reference of the mesh, with no
    blocking gate: fit2d is never applied (D-24, D-29). Returns the model, the geometry, the points and the first
    build's lint hits."""
    board, project = coupon_project(name, n)
    geom = build_geometry(board, p0.edit(project, edits or {}))
    hits = len(edge_lint(build_mesh(geom, geom.protected, n)))
    mesh = mesh_with_lint(geom, geom.protected, n)
    pts = points(geom, name)
    spec = {**model_spec(project, board, geom, mesh, feeds(geom, mesh), []),
            "probes": [probe for point in pts for probe in probe_set(geom, mesh, point)]}
    return pipeline.Model(mesh, spec, [], dt_floor_reference(mesh)), geom, pts, hits


def triplet(v: np.ndarray, i: np.ndarray, dv: tuple[float, float], di: float) -> tuple[np.ndarray, np.ndarray]:
    """Z0 and β (rad/m) of a probe triplet by MSLPort's equations (openEMS ports.py:436-447; A-1): `v` (3, F) the
    voltages on three planes along the line, dv[0] and dv[1] m apart, `i` (2, F) the currents on the two planes between
    them, `di` m apart. Z0 is exact for any mix of forward and backward waves; β is the discrete 2/Δ·sin(βΔ/2), its
    sign flipped where its real part is negative."""
    et, det = v[1], (v[2] - v[0]) / (dv[0] + dv[1])
    ht, dht = (i[0] + i[1]) / 2, (i[1] - i[0]) / di
    beta = np.sqrt(-det * dht / (ht * et))
    return np.sqrt(et * det / (ht * dht)), np.where(beta.real < 0, -beta, beta)


def eps_eff(beta: np.ndarray, f: np.ndarray, theta: float = 0.0) -> np.ndarray:
    """εeff = (Re β·cos θ·c0/(2πf))² of β (rad/m) at `f` (Hz), read on planes whose normal is `theta` degrees off the
    line, where β along the normal is the line's β/cos θ (r7 §2.4)."""
    return (beta.real * math.cos(math.radians(theta)) * C0 / (2 * np.pi * f)) ** 2


def line_constants(job: Path, probes: list[dict], f: np.ndarray, t_cut: float | None,
                   theta: float) -> tuple[np.ndarray, np.ndarray]:
    """Z0 (complex, Ω) and εeff over `f` (Hz) of one point, from its five probe files in the job folder `job` (`probes`
    as probe_set gives them): each file's samples up to `t_cut` (s; the whole record for None), DFT'd on its own times,
    which takes the half step between E and H; then triplet, the spacings the probes' places along the current probes'
    norm_dir, and eps_eff at `theta` degrees."""
    def spectrum(probe: dict) -> np.ndarray:
        t, x = read_probe((job / probe["name"]).read_text(encoding="utf-8"))
        n = len(t) if t_cut is None else np.searchsorted(t, t_cut, "right")
        return x[:n] @ np.exp(-2j * np.pi * np.outer(t[:n], f))

    axis = next(p["norm_dir"] for p in probes if p["type"] == 1)
    volts, amps = ([p for p in probes if p["type"] == kind] for kind in (0, 1))
    (at_v0, at_v1, at_v2), (at_i0, at_i1) = ([p["start"][axis] * 1e-3 for p in group] for group in (volts, amps))  # m
    z0, beta = triplet(np.array([spectrum(p) for p in volts]), np.array([spectrum(p) for p in amps]),
                       (at_v1 - at_v0, at_v2 - at_v1), at_i1 - at_i0)
    return z0, eps_eff(beta, f, theta)


def references(geom: Geometry, mesh: Mesh, point: dict) -> dict:
    """The references of a section point (D-25, A-2), {} for a midpoint: "z0_ref", KiCad's microstrip or cpwg Z0 of the
    section (its width and gap on the stackup's h, t and εr) times cs2d's exact-mask over no-mask Z0 in the BOX_REF box,
    since KiCad has no mask (1 without one); "eeff_ref" and "z0_2d", cs2d's with the exact mask in that box;
    "z0_mesh" and "eeff_mesh", cs2d's on the mesh lines with the coat smeared over dz0, as fit2d's mesh side; "e_fit",
    fit2d's signed z0_mesh/z0_ref − 1 of that section."""
    if point["section"] is None:
        return {}
    sec, zs = geom.sections[point["section"]], geom.zs
    mask = geom.masks.get(sec.layer)
    cu = [s for s in zs if s.kind == "copper"][-1]
    h, t = substrate_h(zs), round(cu.z1 - cu.z0, 6)
    er = next(s.eps_r for s in zs if s.kind == "dielectric" and s.z1 == cu.z0)
    kicad = (microstrip(sec.width, h, t, er) if sec.gap is None else cpwg(sec.width, sec.gap, h, t, er))[0]
    exact, bare = (solve(cross_section(sec, geom.pieces, zs, mask, mode, box_h=BOX_REF)) for mode in ("exact", "none"))
    on_mesh = solve(cross_section(sec, geom.pieces, zs, mask, "smeared", mesh.dz0),
                    mesh.y if sec.axis == "x" else mesh.x, mesh.z)
    fit = fit2d(geom, mesh)[point["section"]]
    return {"z0_ref": kicad * exact.z0 / bare.z0, "eeff_ref": exact.eps_eff, "z0_2d": exact.z0,
            "z0_mesh": on_mesh.z0, "eeff_mesh": on_mesh.eps_eff, "e_fit": fit.z0_mesh / fit.z0_ref - 1}
