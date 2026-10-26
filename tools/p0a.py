# SPDX-License-Identifier: GPL-3.0-or-later
"""P0-A, the coupon gate (spec 9.2; D-24..D-30; amendments A-1, A-2). Part 1, the instrument: each pad-less coupon is
a harness model (D-9): its project.json made by hand, the product's geometry, mesh and model spec, two vertical 50 Ω
lumped feeds at the line's ends, and a probe triplet at each section's cut (and a twin's midpoint); fit2d is computed,
never applied (D-29). The line constants come from the probe files by MSLPort's equations (A-1), the references from
KiCad's line formulas and cs2d in a 45 h box (D-25, A-2). Part 2, the rules and the driver: the steps (the
calibration, the 14 coupon runs, the pad coupon through new, cost and run, the stray-cell setup), each resumable
through p0.step; the rows, pairs, twins, pad and stray assembled from the run folders; the pre-registered rules
(D-26..D-30); p0a.json and p0a.md.

Dev-time only, like p0: the package never imports it. Run: python tools/p0a.py [--out DIR] [--only ID[,ID…]]
[--report]."""
import argparse
import math
import shutil
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

import numpy as np
import shapely
from scipy.constants import c as C0
from shapely.geometry import LineString, Point

import p0
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.cs2d import solve
from kicad_rf_studio.core.geometry import Geometry, build_geometry
from kicad_rf_studio.core.geometry.sections import cross_section
from kicad_rf_studio.core.geometry.zstack import substrate_h
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.mesh import Mesh, build_mesh
from kicad_rf_studio.core.mesh.gates import dt_floor_reference, edge_lint, fit2d, mesh_with_lint
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.readers import read_probe
from kicad_rf_studio.core.model.spec import model_spec, spec_hash
from kicad_rf_studio.core.post.checks import LOSS_LIMIT, RECIP_LIMIT, SIGMA_LIMIT
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import BAND_FACTOR, HARMONICS, board_hash, load_project, make_project, save_project
from kicad_rf_studio.stoprule import KEPT, growth_rise

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
NS = (2, 3)  # the mesh.n of every coupon run (D-24)
COUPON_STEPS = {f"p0a-{name}-n{n}": (name, n) for name in COUPONS for n in NS}
STEPS = ("p0a-calibrate", *COUPON_STEPS, "p0a-pad", "p0a-stray")  # in the order main runs them
PAD_NEW = ("--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz")  # new's arguments for the pad coupon (D-28)
PIN = {"mesh.reach_h": 3.0}  # the P0 runs' reach, so that a later default (D-37) cannot change the models CI builds


def _nearest(lines: np.ndarray, v: float) -> int:
    """The index of the line of `lines` nearest `v`."""
    return int(np.abs(lines - v).argmin())


def coupon_project(name: str, n: int) -> tuple[Board, dict]:
    """The board of the coupon `name` (tests/fixtures) and its project.json as `new` writes it, made by hand since `new`
    cannot trace a pad-less line (R-P2-8; tests/test_cli_cost.by_hand): the chain LINE alone, no part, no port, preset
    normal, mesh.n `n`, mesh.reach_h pinned (PIN)."""
    path = p0.FIX / f"{name}.kicad_pcb"
    board = load_board(path)
    chain = {"start": "", "end": "", "nets": ["LINE"], "series": [], "shunt": []}
    project = make_project(path.as_posix(), board_hash(path), F0, board.stackup, classify(board), chain, [], [])
    return board, p0.edit(project, {"mesh.n": n, **PIN})


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


def _pct(a: float | None, b: float | None) -> float | None:
    """100·(a/b − 1), None when either is None."""
    return None if a is None or b is None else 100 * (a / b - 1)


def _same_model(record: dict, spec: dict) -> None:
    """SystemExit unless `spec`, the model this code builds, is the one the step `record` ran (its key's hash)."""
    if spec_hash(spec) != record["key"].split("@")[0]:
        raise SystemExit(f"p0a: {record['step']} ran another model than this code builds; run the harness again")


def stray_model() -> pipeline.Model:
    """The stray-cell variant (D-30, PF-23): coupon_gcpw at n = 2 with one x line added 10 µm from the pinned x line
    nearest its cut, on the rule mesh's dt_ref, for a setup-only run whose dt the floor must catch."""
    model, _, pts, _ = coupon_model("coupon_gcpw", 2)
    pinned = model.mesh.pinned["x"]
    x = float(pinned[_nearest(pinned, pts[0]["at"][0])]) + 0.010
    spec = {**model.spec, "mesh": {**model.spec["mesh"], "x": sorted([*model.spec["mesh"]["x"], x])}}
    return pipeline.Model(p0.model_of(spec).mesh, spec, [], model.dt_ref)


def rows(record: dict, name: str, n: int) -> list[dict]:
    """The rows of the step `record` of the coupon `name` at mesh.n `n`, computed at assembly (D-24, D-25): its model
    rebuilt (coupon_model, _same_model), then per point its line constants, read at f0 (grid index 71) and as [min,
    max] over BAND, and its references; a job whose verdict kept no S (KEPT) gives no line constants. One row
    {"coupon", "n", "lint", "pass"} when the step recorded a lint failure."""
    res = record["result"]
    if "lint" in res:
        return [{"coupon": name, "n": n, "lint": res["lint"][0], "pass": False}]
    model, geom, pts, _ = coupon_model(name, n)
    _same_model(record, model.spec)
    (job,), dt, entry, mesh = res["jobs"], res["setup"]["dt"], record["load"]["calibration"], model.mesh
    folder, cells = p0.run_path(res["run_dir"]) / job["job"], len(mesh.x) * len(mesh.y) * len(mesh.z)  # as cost counts
    run = {"cells": cells, "dt": dt, "dt_ratio": dt / model.dt_ref, "lint": None,
           "lint_first_hits": res["lint_first_hits"], "blocked": [code for code, _ in res["blocked"]],
           "verdict": job["verdict"], "t_cut": job["t_cut"],
           "growth_db": growth_rise(pipeline.records(folder, len(model.spec["ports"]), dt),
                                    model.spec["excitation"]["t0"]),
           "loaded": record["loaded"], "wall_s": res["wall_s"],
           "predicted_s": None if entry is None or job["t_stop"] is None else
           p0.predicted_s(1, 1, cells, dt, job["t_stop"], runs.per_job_mcs(entry, 1))}
    f = grid(F0, HARMONICS, BAND_FACTOR)[0]
    k0, band = _nearest(f, F0), (f >= BAND[0]) & (f <= BAND[1])
    out = []
    for pt in pts:
        ref, section = references(geom, mesh, pt), pt["section"] is not None
        z0 = eeff = z0_band = eeff_band = None
        if job["verdict"] in KEPT:
            probes = [p for p in model.spec["probes"] if p["name"].rsplit("_", 1)[0] == pt["label"]]
            z, e = line_constants(folder, probes, f, job["t_cut"], pt["theta"])
            z0, eeff = float(z[k0].real), float(e[k0])
            z0_band, eeff_band = ([float(v[band].min()), float(v[band].max())] for v in (z.real, e))
        dz0, deeff = _pct(z0, ref.get("z0_ref")), _pct(eeff, ref.get("eeff_ref"))
        # δ = e_FDTD − e_fit, e_FDTD = Re Z0 / Z0_2D(45 h) − 1 (D-29)
        delta = 100 * (z0 / ref["z0_2d"] - 1 - ref["e_fit"]) if section and z0 is not None else None
        out.append({
            "coupon": name, "n": n, "point": pt["label"], "section": pt["section"], "theta": pt["theta"], **run,
            "z0": z0, "z0_ref": ref.get("z0_ref"), "dz0_pct": dz0, "eeff": eeff, "eeff_ref": ref.get("eeff_ref"),
            "deeff_pct": deeff, "z0_band": z0_band, "eeff_band": eeff_band,
            "e_fit_pct": 100 * ref["e_fit"] if section else None, "delta_pp": delta,
            "z0_mesh": ref.get("z0_mesh"), "eeff_mesh": ref.get("eeff_mesh"), "z0_2d": ref.get("z0_2d"),
            "run_dir": res["run_dir"],
            "pass": (dz0 is not None and abs(dz0) <= LIMITS["z0_pct"] and abs(deeff) <= LIMITS["eeff_pct"]) if section
            else None})
    return out


def measure(out: Path) -> dict:
    """The P0-A measurements of the P0 folder `out`, from its step records (p0.records: every step, one code) and its
    run folders: {"rows" (rows of each coupon step), "pairs" (D-26: masked against mask-free at the same n; miss = FDTD
    − on-mesh shift, judged; gap = FDTD − exact 2D shift, a stated limit), "twins" (D-27: each midpoint against
    coupon_gcpw's s0 at the same n; the arc's midpoint also against the mean of its own s0 and s1, report only), "pad"
    (D-28: p0.summary of its run and the pass), "stray" (D-30: its setup dt over the rule mesh's dt_ref and its codes)}.
    """
    recs = dict(zip(STEPS, p0.records(out, list(STEPS))))
    found = [row for sid, (name, n) in COUPON_STEPS.items() for row in rows(recs[sid], name, n)]
    at = {(row["coupon"], row["n"], row.get("point")): row for row in found}

    def get(name: str, n: int, point: str, key: str) -> float | None:
        return at.get((name, n, point), {}).get(key)

    pairs = []
    for (masked, free), n in ((pair, n) for pair in PAIRS for n in NS):
        z0, eeff = ([_pct(get(masked, n, "s0", key), get(free, n, "s0", key)) for key in keys]
                    for keys in (("z0", "z0_mesh", "z0_2d"), ("eeff", "eeff_mesh", "eeff_ref")))  # FDTD, mesh, 2D
        miss, gap = ([None if None in (q[0], q[i]) else q[0] - q[i] for q in (z0, eeff)] for i in (1, 2))
        pairs.append({"pair": f"{masked}/{free}", "n": n, "z0_fdtd_pct": z0[0], "z0_mesh_pct": z0[1],
                      "z0_2d_pct": z0[2], "eeff_fdtd_pct": eeff[0], "eeff_mesh_pct": eeff[1], "eeff_2d_pct": eeff[2],
                      "miss_z0_pp": miss[0], "miss_eeff_pp": miss[1], "gap_z0_pp": gap[0], "gap_eeff_pp": gap[1],
                      "pass": None not in miss and abs(miss[0]) <= LIMITS["shift_z0_pp"]
                      and abs(miss[1]) <= LIMITS["shift_eeff_pp"]})
    twins = []
    for name, n in ((name, n) for name in TWINS for n in NS):
        (z0, eeff), (z0_gcpw, eeff_gcpw) = ([get(coupon, n, point, key) for key in ("z0", "eeff")]
                                            for coupon, point in ((name, "mid"), ("coupon_gcpw", "s0")))
        twin = {"twin": name, "n": n, "z0_twin": z0, "z0_gcpw": z0_gcpw, "dz0_pct": _pct(z0, z0_gcpw),
                "eeff_twin": eeff, "eeff_gcpw": eeff_gcpw, "deeff_pct": _pct(eeff, eeff_gcpw)}
        if name == "coupon_gcpw_arc":
            ends = [get(name, n, point, "z0") for point in ("s0", "s1")]
            shift = _pct(z0, None if None in ends else sum(ends) / 2)
            twin["arc_mid_vs_straights"] = None if shift is None else abs(shift)
        twins.append(twin)
    summary = p0.summary(recs["p0a-pad"])
    ind = summary["indicators"]
    sigma, recip, loss, expected = ind["sigma"], ind["recip"], ind["loss_pct"], ind["expected_pct"]
    pad ={**summary, "sigma": sigma, "recip": recip, "loss_pct": loss, "loss_expected_pct": expected,
           "pass": (all(code == 0 for code in summary["exit"].values())
                    and [job["verdict"] for job in summary["jobs"]] == ["converged"] * 2
                    and None not in (sigma, recip, loss, expected) and sigma <= SIGMA_LIMIT and recip <= RECIP_LIMIT
                    and loss - expected <= 100 * LOSS_LIMIT and not summary["warnings"])}
    stray, res = stray_model(), recs["p0a-stray"]["result"]
    _same_model(recs["p0a-stray"], stray.spec)
    codes = [code for code, _ in res["blocked"] + res["warnings"]]
    return {"rows": found, "pairs": pairs, "twins": twins, "pad": pad,
            "stray": {"dt_ratio": res["setup"]["dt"] / stray.dt_ref, "codes": codes, "trips": "E_DT_FLOOR" in codes}}


def decide(m: dict) -> dict:
    """The P0-A rules on the measurements `m` (measure's), pure (D-26..D-30). The counted rows are the section points
    (PF-21) whose job converged and whose model passed its lint; every other row is left out of the rules and named
    among the fails, but a converged midpoint, which feeds only the twins (PF-19). Returns {"fit2d", "dt_floor",
    "mask_shift", "twins", "pad", "verdict"}."""
    ok = [row.get("verdict") == "converged" and not row.get("lint") for row in m["rows"]]
    left = [row for row, good in zip(m["rows"], ok) if not good]
    counted = [row for row, good in zip(m["rows"], ok) if good and row.get("section") is not None]

    def holds(limit: float) -> bool:
        """D-29 (i) at `limit` %: every counted row with |e_fit| ≤ limit passes D-25, in Z0 and in εeff (OI-1)."""
        return all(row["pass"] for row in counted if abs(row["e_fit_pct"]) <= limit)

    limit = 3.0  # D-29: down by 0.5 pp while (i) fails, never below the pre-registered 1.5 % floor (OI-2)
    while not holds(limit) and limit > 1.5:
        limit -= 0.5
    max_delta = max((abs(row["delta_pp"]) for row in counted), default=0.0)
    ii = max_delta <= LIMITS["delta_pp"]
    if holds(limit):
        branch = "lower" if limit < 3.0 else "keep" if ii else "keep-state"
    else:  # no limit change: the failing rows become stated limits and the Stage 2 calibration item (D-31)
        branch, limit = "unpredicted", 3.0
    dz0 = {(twin["twin"], twin["n"]): abs(twin["dz0_pct"]) for twin in m["twins"] if twin["dz0_pct"] is not None}
    worst = max(dz0.values(), default=None)
    smaller = all((name, 2) in dz0 and (name, 3) in dz0 and dz0[name, 3] < dz0[name, 2]
                  for name in {twin["twin"] for twin in m["twins"]})
    ratios = [row["dt_ratio"] for row in (*m["rows"], m["pad"]) if row.get("dt_ratio") is not None]  # PF-22

    def label(row: dict) -> str:
        return f"{row['coupon']} n={row['n']}" + (f" {row['point']}" if row.get("point") else "")

    fails = [f"{label(row)}: left out of the rules ({row.get('lint') or 'its job ended ' + str(row.get('verdict'))})"
             for row in left]
    fails += [f"{label(row)}: fails D-25 within the {limit:g} % limit (ΔZ0 {row['dz0_pct']:+.2f} %, Δεeff "
              f"{row['deeff_pct']:+.2f} %)" for row in counted if abs(row["e_fit_pct"]) <= limit and not row["pass"]]
    fails += [f"mask shift {pair.get('pair')} n={pair.get('n')}: fails D-26" for pair in m["pairs"] if not pair["pass"]]
    fails += [] if m["pad"]["pass"] else ["pad coupon: fails D-28"]
    fails += ["fit2d: D-29 (i) still fails at the 1.5 % floor (unpredicted)"] if branch == "unpredicted" else []
    return {"fit2d": {"rule": "D-29", "i_at_3": holds(3.0), "limit_pct": limit, "max_delta_pp": max_delta, "ii": ii,
                      "branch": branch},
            "dt_floor": {"rule": "D-30", "min_ratio": min(ratios, default=None), "stray_ratio": m["stray"]["dt_ratio"],
                         "stray_trips": m["stray"]["trips"]},
            "mask_shift": {"rule": "D-26", "pass": all(pair["pass"] for pair in m["pairs"])},
            "twins": {"rule": "D-27", "max_dz0_pct": worst,
                      "branch": "refuse" if worst is not None and worst > LIMITS["twin_pct"] else
                      "advice" if smaller else "keep"},
            "pad": {"rule": "D-28", "pass": m["pad"]["pass"]},
            "verdict": {"value": "fail" if fails else "pass", "fails": fails}}


def _cell(v) -> str:
    """`v` as the P0-A tables show it: None as "–", a float as :.4g, a list's items and a dict's "key value" pairs
    joined by ", "."""
    if isinstance(v, dict):
        return ", ".join(f"{key} {_cell(x)}" for key, x in v.items())
    if isinstance(v, list):
        return ", ".join(map(_cell, v))
    return "–" if v is None else f"{v:.4g}" if isinstance(v, float) else str(v)


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), with p0.table: A1 the rows, A2 the mask-shift pairs, A3
    the twins (every key each holds), A4 the pad coupon and its jobs, A5 the decisions."""
    def table(title: str, items: list[dict], cols: list[str] | None = None) -> str:
        cols = cols or list(dict.fromkeys(key for item in items for key in item))
        return f"## {title}\n\n" + p0.table([{col: _cell(item.get(col)) for col in cols} for item in items], cols)

    pad = result["pad"]
    return "\n\n".join([
        table("A1 Rows", result["rows"]), table("A2 Mask-shift pairs", result["pairs"]),
        table("A3 Twins", result["twins"]),
        table("A4 Pad coupon", [pad], ["exit", "cells", "dt", "dt_ratio", "sigma", "recip", "loss_pct",
                                       "loss_expected_pct", "warnings", "lid_mm", "wall_s", "predicted_s", "pass"]),
        table("A4 Pad coupon jobs", pad["jobs"]),
        table("A5 Decisions", [{"decision": name, "rule": d.get("rule"),
                                "result": {key: v for key, v in d.items() if key != "rule"}}
                               for name, d in result["decisions"].items()])]) + "\n"


def write(out: Path) -> dict:
    """measure, decide and tables of the P0 folder `out`: <out>/p0a/p0a.json through p0.save, whose "calibration" is
    this machine's settings entry without its key, which holds a host name (PF-25), and p0a.md beside it. Returns the
    JSON as saved."""
    m = measure(out)
    entry = runs.load_settings().get("machines", {}).get(runs.machine_key()) or {}
    result = p0.save(out / "p0a" / "p0a.json", {
        "gate": "P0-A", "versions": p0.versions(),
        "calibration": {key: entry.get(key) for key in ("aggregate_mcs", "pool", "threads", "levels")}, **m,
        "decisions": decide(m), "machine": p0.machine(p0.records(out, list(STEPS)))})
    (out / "p0a" / "p0a.md").write_text(tables(result), encoding="utf-8")
    return result


def _calibrate() -> dict:
    """`calibrate` in the P0 data folder; RuntimeError, so that nothing is recorded, on a non-zero exit."""
    code, text = p0.cli("calibrate")
    if code:
        raise RuntimeError(f"p0a: calibrate exited {code}: {text.strip()}")
    return {"exit": code}


def _pad(out: Path) -> tuple[str, Callable[[], dict]]:
    """The key and work of the pad coupon's step (D-28, PF-20): its project <out>/p0a/projects/coupon_gcpw_pads, made
    by `new` from the board copied into <out>/boards when it is missing (RuntimeError on a non-zero exit; new writes
    project.json only once every refusal check passed), PIN saved, keyed by p0.model_key; the work runs cost, then
    run (p0.cli_run), at the project's preset, Normal."""
    pj = out / "p0a" / "projects" / "coupon_gcpw_pads" / "project.json"
    if not pj.is_file():
        (out / "boards").mkdir(parents=True, exist_ok=True)
        board = shutil.copy2(p0.FIX / "coupon_gcpw_pads.kicad_pcb", out / "boards")
        code, text = p0.cli("new", str(board), *PAD_NEW, "-o", str(pj.parent))
        if code:
            raise RuntimeError(f"p0a: new exited {code}: {(text.strip().splitlines() or [''])[-1]}")
    save_project(pj, p0.edit(load_project(pj), PIN))

    def work() -> dict:
        code, _ = p0.cli("cost", str(pj))
        run = p0.cli_run(pj, "run")
        return {**run, "exit": {"new": 0, "cost": code, "run": run["exit"]}}

    return p0.model_key(pj), work


def _step(out: Path, sid: str) -> tuple[str, Callable[[], dict]]:
    """The key and the work of the step `sid` (STEPS): a coupon's key is its model's spec_hash, or "E_EDGE_LINT" when
    coupon_model raises it, whose step records {"lint": [code, params]}."""
    if sid == "p0a-calibrate":
        return "once", _calibrate
    if sid == "p0a-pad":
        return _pad(out)
    if sid == "p0a-stray":
        model = stray_model()
        return spec_hash(model.spec), lambda: p0.run_model(model, "normal", sid, [])
    name, n = COUPON_STEPS[sid]
    try:
        model, _, _, hits = coupon_model(name, n)
    except KrsError as e:
        if e.code != "E_EDGE_LINT":
            raise
        lint = [e.code, e.params]  # e is unbound once the except block ends
        return "E_EDGE_LINT", lambda: {"lint": lint}
    return spec_hash(model.spec), lambda: {**p0.run_model(model, "normal", sid, [1]), "lint_first_hits": hits}


def main(argv: list[str] | None = None) -> int:
    """python tools/p0a.py [--out DIR] [--only ID[,ID…]] [--report] (D-5, D-6): enters the P0 folder first, then runs
    each of STEPS (or of --only) through p0.step, printing a step that raises and going on with the next, then writes
    the gate when every step has its record and none raised; --report writes from the records and runs no step.
    Returns 1 when a step raised, else 0."""
    parser = argparse.ArgumentParser(prog="p0a", description="P0-A, the coupon gate (spec 9.2).")
    parser.add_argument("--out", help="the P0 folder (default: kicad-rf-studio-p0 beside the per-user data folder)")
    parser.add_argument("--only", help="the ids of the steps to run, comma-separated")
    parser.add_argument("--report", action="store_true", help="write p0a.json and p0a.md from the records only")
    a = parser.parse_args(argv)
    only = a.only.split(",") if a.only else STEPS
    if unknown := sorted(set(only) - set(STEPS)):
        parser.error(f"unknown step: {', '.join(unknown)}")
    out = p0.enter(Path(a.out) if a.out else p0.default_out())  # PF-24
    if a.report:
        write(out)
        return 0
    failed = []
    for sid in [step for step in STEPS if step in only]:
        print(f"p0a: {sid}", flush=True)
        try:
            p0.step(out, sid, *_step(out, sid))
        except Exception:  # logged and skipped; SystemExit (STOP) and KeyboardInterrupt end the harness
            failed.append(sid)
            traceback.print_exc()
    if failed:
        print(f"p0a: failed steps: {', '.join(failed)}", flush=True)
        return 1
    if all((out / "steps" / f"{sid}.json").is_file() for sid in STEPS):
        write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
