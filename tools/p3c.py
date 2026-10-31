# SPDX-License-Identifier: GPL-3.0-or-later
"""P3-C, convergence and defaults (Stage 3 design 5.11) on both fixtures: mesh n 2/3/4, the air gap λ/4 against λ/2,
Normal against Strict, a free run to 3 × the stop time, solid against all-sheet copper, and MUR at λ/2 as report-only
evidence; each variant a project edit run through the product, each delta computed in-process (compare refuses
different settings); p3c.json and p3c.md in <out>/p3c, written from whatever steps are recorded. Run: python
tools/p3c.py --out DIR [--steps ...]."""
import argparse
import json
import math
import sys
from dataclasses import replace
from functools import partial
from pathlib import Path

import numpy as np

import p0
import p3
import p3a
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.mesh.gates import fit2d, mesh_with_lint
from kicad_rf_studio.core.model.ports import ends, nominal_boxes
from kicad_rf_studio.core.post.antenna import resonance
from kicad_rf_studio.core.project import load_project, mesh_n
from kicad_rf_studio.stoprule import KEPT, PRESETS

CRITERIA = json.loads((p0.FIX / "p3c" / "criteria.json").read_text(encoding="utf-8"))  # committed before any run
FIXTURES = ("ifa2g4", "meander915")
COPPERS = ("solid", "sheet")
SETTINGS = ("n2", "n3", "n4", "gap2", "strict")
FREE = {"free": "n2", "murfree": "mur"}  # each free step's project, by its setting
# each fixture's raised "t_max_s" and "flat_s", set only at a checkpoint (Task 10), a recorded deviation
RAISED: dict[str, dict] = {"ifa2g4": {}, "meander915": {}}
# the antenna defaults P3-C may raise, as kept; the copper is chosen, not raised: solid stays new's when sheet fails
DEFAULTS = {"mesh_n": 2, "gap_factor": 1, "preset": "normal", "boundary": "pml_8", "t_max": "kept", "flat": "kept"}


def names() -> list[str]:
    """Every step, fixture by fixture, copper by copper: <fixture>-<copper>-<setting> for each of SETTINGS, then mur
    (MUR at λ/2; the meander's runs only when its PML fails), then the free runs free, on the n2 project, and murfree,
    on the mur project."""
    return [f"{fixture}-{copper}-{setting}" for fixture in FIXTURES for copper in COPPERS
            for setting in (*SETTINGS, "mur", *FREE)]


def edits(name: str, base: dict) -> dict:
    """The project edits (p0.edit's dotted keys) of the run step `name` on its fixture's base project `base`: its
    copper; n3 and n4 their mesh n, ifa2g4's with the fit2d limit fit2d_raised (ruling 2); gap2 the air gap at λ/2,
    twice the base's; strict the stop rule's preset alone, mesh n kept at 2 (`new --preset strict` would write n 3);
    mur the MUR boundary at λ/2; then RAISED's edits of its fixture."""
    fixture, copper, setting = name.split("-")
    gap = {"air_gap_mm": round(2 * base["air_gap_mm"], 6)}
    fit2d = {"gates.fit2d_limit": CRITERIA["fit2d_raised"]} if fixture == "ifa2g4" else {}
    return {"copper": copper, **{"n2": {}, "n3": {"mesh.n": 3, **fit2d}, "n4": {"mesh.n": 4, **fit2d}, "gap2": gap,
                                 "strict": {"preset": "strict"}, "mur": {"boundary": "mur", **gap}}[setting],
            **RAISED[fixture]}


def _ran(out: Path, name: str) -> dict:
    """p3.measure of the project `name`'s run step; RuntimeError "run <name> first" when that step has no record."""
    if (m := p3.measure(out, name)) is None:
        raise RuntimeError(f"p3c: run {name} first")
    return m


def run(out: Path, name: str) -> None:
    """The step `name` of names() in <out> (<GATES>); KeyError for another name. A run step: p3.variant of its fixture's
    base with edits(name, the base project), then p3.run_step. A free step: p3.free_step of its project (FREE), as that
    project's run left it, to t_free: for free, and for the meander's murfree (its PML free run's length), max(n2's
    t_max_s, free_factor × n2's longest kept t_stop) (ruling 4; ValueError when n2 kept none); for ifa2g4's murfree,
    free_factor × the mur project's t_max_s (P3-A's 3 × T_max window, where its MUR twin rose 16 dB). RuntimeError "run
    <project> first" when its project's run, or n2's, which sets its length, has no record."""
    if name not in names():
        raise KeyError(name)
    fixture, copper, setting = name.split("-")
    if setting not in FREE:
        p3.variant(out, name, fixture, edits(name, load_project(p3.base(out, fixture))))
        p3.run_step(out, name)
        return
    project, n2 = f"{fixture}-{copper}-{FREE[setting]}", f"{fixture}-{copper}-n2"
    m = _ran(out, project)
    if (fixture, setting) == ("ifa2g4", "murfree"):
        t_free = CRITERIA["free_factor"] * load_project(p3.project_path(out, project))["t_max_s"]
    else:
        jobs = (m if project == n2 else _ran(out, n2))["jobs"]
        kept = [job["t_stop"] for job in jobs if job["verdict"] in KEPT and job["t_stop"] is not None]
        t_free = max(load_project(p3.project_path(out, n2))["t_max_s"], CRITERIA["free_factor"] * max(kept))
    p3.free_step(out, project, t_free)


def extrapolated(fs: list[float], p: float | None = None) -> tuple[float, str, float | None]:
    """f_res at the zero cell from `fs`, f_res at mesh n 2, 3 and 4, or n 2 and 3 (h ∝ 1/n): (f, kind, observed p).
    Three meshes, the steps d1 = f3 − f2 and d2 = f4 − f3: a sign change or a zero step is (f4, "oscillating", None);
    else R = d1/d2 at most R(0) = ln(3/2)/ln(4/3) is (f4, "not converging", None); else p solves R(p) = (2^−p − 3^−p)/
    (3^−p − 4^−p) = R by bisection on (0, 16], and f4 + d2/((4/3)^order − 1) at order min(p, 1), 1 exactly when R ≥ 2,
    is "monotone" with p. Two meshes: f3 + (f3 − f2)/(1.5^order − 1) at order min(`p`, 1), 1 without `p`, is
    "two meshes" with None."""
    # order 1 is the conservative end only at p ≥ 1 (R ≥ 2); at 0 < p < 1 the observed order gives the larger
    # correction (r2, Celik 2008); the two-mesh branch assumes the 2.4 GHz fixture's order
    if len(fs) == 2:
        f2, f3 = fs
        return f3 + (f3 - f2) / (1.5 ** (1.0 if p is None else min(p, 1.0)) - 1), "two meshes", None
    f2, f3, f4 = fs
    d1, d2 = f3 - f2, f4 - f3
    if d1 * d2 <= 0:
        return f4, "oscillating", None
    r = d1 / d2
    if r <= math.log(3 / 2) / math.log(4 / 3):
        return f4, "not converging", None
    lo, hi = 0.0, 16.0
    for _ in range(60):  # R(p) rises with p
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if (2 ** -mid - 3 ** -mid) / (3 ** -mid - 4 ** -mid) < r else (lo, mid)
    p_obs = (lo + hi) / 2
    return f4 + d2 / ((4 / 3) ** (1.0 if r >= 2 else min(p_obs, 1.0)) - 1), "monotone", p_obs


def projected_stop(run_dir: Path, level_db: float, window_s: float) -> float | None:
    """When job 1's residual meets `level_db` (ruling 9), in s: a least-squares line of residual_db against t through
    the finite residuals of its I_PROGRESS events in <run_dir>/events.jsonl over the last `window_s` s of simulated
    time; None when it does not fall."""
    # ponytail: a straight line in dB; a beating residual projects wrongly, and a None or beating projection stops for
    # a ruling
    events = map(json.loads, (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
    progress = [e["params"] for e in events if e["code"] == "I_PROGRESS" and e["job"] == 1]
    t, r = (np.array([float(q[key]) for q in progress]) for key in ("t_ns", "residual_db"))
    keep = np.isfinite(r) & (t >= t.max(initial=-np.inf) - window_s * 1e9)
    t, r = t[keep], r[keep]
    if len(t) < 2:
        return None
    dt = t - t.mean()
    slope = (dt * (r - r.mean())).sum() / (dt * dt).sum()  # exactly 0 on a flat residual, where polyfit leaves noise
    return float(t.mean() + (level_db - r.mean()) / slope) * 1e-9 if slope < 0 else None


def fit2d_probe(pj: Path) -> list[dict]:
    """Every section's fit2d on the project `pj`'s own mesh as build_model makes it (its port ends' nominal boxes, its
    mesh n, the edge lint), whatever its fit2d limit: ruling 2's record, [{"net", "width" (mm), "err"}]."""
    project, board, geom, _ = pipeline.load(pj)
    boxes = nominal_boxes(ends(board, project, geom.pieces))
    mesh = mesh_with_lint(geom, replace(geom.protected, boxes=boxes), mesh_n(project))
    return [{"net": fit.section.net, "width": fit.section.width, "err": float(fit.err)} for fit in fit2d(geom, mesh)]


def _res(x: dict) -> tuple[float, bool]:
    """The run measure `x`'s f_res (resonance) and whether its minimum is conditioned, as p3.pair judges each side:
    inside the grid at or below conditioned_db."""
    f, s = np.asarray(x["f_hz"]), np.asarray(x["s11"])
    k, f_res = resonance(f, s)
    return f_res, bool(0 < k < len(f) - 1 and 20 * np.log10(abs(s[k])) <= CRITERIA["conditioned_db"])


def _within(v: float | None, limit: float) -> bool:
    return v is not None and v <= limit


def _pair(a: dict, b: dict, f_rel: float, eta_db: float, d_db: float | None = None) -> dict:
    """p3.pair of the runs `a` and `b` at the limit `f_rel`, with "value" its f_rel; "pass" and "explained" also need
    Δη_rad within `eta_db` and, given `d_db`, ΔD within it: both stay binding (ruling 1)."""
    p = p3.pair(a, b, f_rel, CRITERIA["conditioned_db"])
    binding = _within(p["eta_db"], eta_db) and (d_db is None or _within(p["d_db"], d_db))
    return {**p, "value": p["f_rel"], "pass": p["pass"] and binding, "explained": p["explained"] and binding}


def _mesh(xs: list[dict], p: float | None) -> dict:
    """The mesh check of the runs `xs` at n 2, 3 (and 4): extrapolated's "f_ext", "kind" and observed "p", at `p` on
    two meshes; "f_res" each run's; "ratio" (f3 − f2)/(f4 − f3); "value" n 2's |f2 − f_ext|/f_ext, oscillating
    max(|f2 − f4|, |f3 − f4|)/f4; "pass" within mesh_f_res_rel unless not converging; "conditioned" all of them; "ds11"
    and "ds11_shift" as p3.pair takes them, n 2 against the S11 extrapolated pointwise at f_ext's own order (S4 itself
    when oscillating); "explained" a miss on no conditioned dip whose ds11 is within ds11_shift (ruling 1, amended)."""
    res = [_res(x) for x in xs]
    fs = [f for f, _ in res]
    f_ext, kind, p_obs = extrapolated(fs, p)
    fine, coarse = fs[-1], fs[-2]
    value = max(abs(fs[0] - fine), abs(fs[1] - fine)) / fine if kind == "oscillating" else abs(fs[0] - f_ext) / f_ext
    w = (f_ext - fine) / (fine - coarse) if fine != coarse else 0.0  # extrapolated's own weight, 0 at f4 itself
    s_fine, s_coarse = np.asarray(xs[-1]["s11"]), np.asarray(xs[-2]["s11"])
    ext = {"f_hz": xs[0]["f_hz"], "s11": s_fine + w * (s_fine - s_coarse), "band": xs[0]["band"], "d_dbi": None,
           "eta_rad": None}
    shift = p3.pair(ext, xs[0], CRITERIA["mesh_f_res_rel"], CRITERIA["conditioned_db"])
    conditioned = all(c for _, c in res)
    ok = kind != "not converging" and value <= CRITERIA["mesh_f_res_rel"]
    return {"kind": kind, "p": p_obs, "ratio": (fs[1] - fs[0]) / (fs[2] - fs[1]) if len(fs) == 3 and fs[2] != fs[1]
            else None, "f_res": fs, "f_ext": f_ext, "value": value, "conditioned": conditioned, "ds11": shift["ds11"],
            "ds11_shift": shift["ds11_shift"], "pass": ok,
            "explained": not ok and not conditioned and shift["ds11"] <= shift["ds11_shift"]}


def _growth(x: dict | None) -> dict:
    """The free run measure `x` by P3-A's growth rule (ruling 4): "pass" when finite, its growth_db within
    growth_db_max and its "reach", t_stop/t_max, at least free_reach; not judged when missing."""
    if x is None:
        return {"pass": None, "why": "missing"}
    reach = None if x["t_stop"] is None else x["t_stop"] / x["t_max"]
    return {"growth_db": x["growth_db"], "finite": x["finite"], "reach": reach,
            "pass": bool(x["finite"]) and _within(x["growth_db"], CRITERIA["growth_db_max"])
            and reach is not None and reach >= CRITERIA["free_reach"]}


def decide(m: dict[str, dict | None]) -> dict:
    """P3-C's checks (design 5.11) on `m`, each step name's p3.measure (a free step's, its "free" measure), read with
    m.get(name), against CRITERIA, each limit inclusive and None a fail. A check is {"pass": None, "why": "missing"}
    when a run it reads has no record or no S11, {"pass": None, "why": "not converged"} when one's jobs did not all
    converge. Per fixture: copper, _pair of solid and sheet at n 2 (sheet_f_res_rel, Δη_rad within sheet_eta_db, ΔD
    reported); the winning copper c, sheet when copper passes (explained counts) on both fixtures, else solid, whose
    steps every later check reads; mesh, _mesh of n 2, 3 and 4, or n 2 and 3 without n 4 (the meander's at ifa2g4's
    observed p); gap, n 2 against gap2 (gap_f_res_rel, ΔD within gap_d_db, Δη_rad within gap_eta_db); preset, n 2
    against strict (preset_f_res_rel, Δη_rad within preset_eta_db). Across them: converged, {"pass": every recorded
    compared run converged, fixture: {"t_max": [names], "flat": [names]}, the compared runs that ended so}; pml,
    {"pass", fixture: c's free run by _growth}; mur, report only, for each fixture with c's mur or murfree recorded:
    {"report_only": True, "f_res", "f_rel", "d_db", "eta_db" of p3.pair of n 2 and mur, "free": murfree by _growth}.
    Decisions: copper c; mesh_n 3, gap_factor 2, preset "strict" when that check fails, not explained, on either
    fixture; boundary "mur" when pml fails on a fixture and ifa2g4's murfree, and that of every fixture whose PML
    failed, pass _growth; t_max "raised" (flat "widened") when a compared run ended at T_max (flat) or RAISED holds a
    t_max_s (flat_s). Verdict: "blocked" when such a needed murfree failed; else "incomplete" when a check is not
    judged or a needed murfree is missing; else "pass" when every DEFAULTS holds, else "defaults raised"; "fails" the
    raised ones. Returns {"checks", "decisions", "verdict"}."""
    c = CRITERIA

    def judged(names: list[str], judge) -> dict:
        xs = [m.get(name) for name in names]
        if any(x is None or x["s11"] is None for x in xs):
            return {"pass": None, "why": "missing"}
        if not all(job["verdict"] == "converged" for x in xs for job in x["jobs"]):
            return {"pass": None, "why": "not converged"}
        return judge(*xs)

    checks = {"copper": {fx: judged([f"{fx}-solid-n2", f"{fx}-sheet-n2"],
                                    lambda a, b: _pair(a, b, c["sheet_f_res_rel"], c["sheet_eta_db"]))
                         for fx in FIXTURES}, "mesh": {}}
    cu = "sheet" if all(x["pass"] or x.get("explained") for x in checks["copper"].values()) else "solid"
    for fx in FIXTURES:  # ifa2g4 first: its observed p is the meander's on two meshes
        n, p = [f"{fx}-{cu}-{s}" for s in SETTINGS[:3]], checks["mesh"].get("ifa2g4", {}).get("p")
        checks["mesh"][fx] = judged(n if m.get(n[2]) is not None else n[:2], lambda *xs: _mesh(list(xs), p))
    checks["gap"] = {fx: judged([f"{fx}-{cu}-n2", f"{fx}-{cu}-gap2"],
                                lambda a, b: _pair(a, b, c["gap_f_res_rel"], c["gap_eta_db"], c["gap_d_db"]))
                     for fx in FIXTURES}
    checks["preset"] = {fx: judged([f"{fx}-{cu}-n2", f"{fx}-{cu}-strict"],
                                   lambda a, b: _pair(a, b, c["preset_f_res_rel"], c["preset_eta_db"]))
                        for fx in FIXTURES}
    compared = {fx: [name for name in (f"{fx}-solid-n2", f"{fx}-sheet-n2", *(f"{fx}-{cu}-{s}" for s in SETTINGS[1:]))
                     if m.get(name) is not None] for fx in FIXTURES}
    checks["converged"] = {
        "pass": all(job["verdict"] == "converged" for names in compared.values() for name in names
                    for job in m[name]["jobs"]),
        **{fx: {v: [name for name in names if any(job["verdict"] == v for job in m[name]["jobs"])]
                for v in ("t_max", "flat")} for fx, names in compared.items()}}
    pml = {fx: _growth(m.get(f"{fx}-{cu}-free")) for fx in FIXTURES}
    passes = [x["pass"] for x in pml.values()]
    checks["pml"] = {"pass": False if False in passes else None if None in passes else True, **pml}
    checks["mur"] = {}
    for fx in FIXTURES:
        n2, mur, free = (m.get(f"{fx}-{cu}-{s}") for s in ("n2", "mur", "murfree"))
        if mur is None and free is None:
            continue
        both = all(x is not None and x["s11"] is not None for x in (n2, mur))
        p = p3.pair(n2, mur, 0.0, c["conditioned_db"]) if both else {}  # report only: no limit, so no pass is kept
        checks["mur"][fx] = {"report_only": True, **{k: p.get(k) for k in ("f_res", "f_rel", "d_db", "eta_db")},
                             "free": free and _growth(free)}
    failed = [fx for fx in FIXTURES if pml[fx]["pass"] is False]
    needs = dict.fromkeys(["ifa2g4", *failed]) if failed else {}  # whose MUR free run the boundary needs
    needed = [_growth(m.get(f"{fx}-{cu}-murfree"))["pass"] for fx in needs]

    def raised(check: str) -> bool:
        return any(x["pass"] is False and not x["explained"] for x in checks[check].values())

    def ended(verdict: str, key: str) -> bool:
        return any(checks["converged"][fx][verdict] or key in RAISED[fx] for fx in FIXTURES)

    decisions = {"copper": cu, "mesh_n": 3 if raised("mesh") else 2, "gap_factor": 2 if raised("gap") else 1,
                 "preset": "strict" if raised("preset") else "normal",
                 "boundary": "mur" if needed and all(needed) else "pml_8",
                 "t_max": "raised" if ended("t_max", "t_max_s") else "kept",
                 "flat": "widened" if ended("flat", "flat_s") else "kept"}
    fails = [k for k, v in DEFAULTS.items() if decisions[k] != v]
    unjudged = any(checks[k][fx]["pass"] is None for k in ("copper", "mesh", "gap", "preset", "pml") for fx in FIXTURES)
    value = ("blocked" if False in needed else "incomplete" if unjudged or None in needed
             else "defaults raised" if fails else "pass")
    return {"checks": checks, "decisions": decisions, "verdict": {"value": value, "fails": fails}}


def edits_2g4(decisions: dict, gap_mm: float) -> dict:
    """The project edits (p0.edit's dotted keys) that P3-D and P3-E apply to the 2.4 GHz boards from P3-C's
    `decisions` (ruling 2; P3-D and P3-E take P3-C's defaults): the copper always; mesh.n 3 with gates.fit2d_limit
    fit2d_raised (the pi board reads 3.53 % at n 3, r3); air_gap_mm at gap_factor × `gap_mm` (ifa2g4's base's), λ/2
    with MUR; preset "strict"; boundary "mur". A kept default is left out, as are T_max and the flat window: they do not
    move a converged run's S."""
    edits = {"copper": decisions["copper"]}
    if decisions["mesh_n"] == 3:
        edits |= {"mesh.n": 3, "gates.fit2d_limit": CRITERIA["fit2d_raised"]}
    factor = 2 if decisions["boundary"] == "mur" else decisions["gap_factor"]  # MUR runs at λ/2
    if factor != 1:
        edits["air_gap_mm"] = round(factor * gap_mm, 6)
    if decisions["preset"] == "strict":
        edits["preset"] = "strict"
    if decisions["boundary"] == "mur":
        edits["boundary"] = "mur"
    return edits


def _step(name: str) -> tuple[str, str]:
    """The project and command of the step `name`: a free step's project (FREE) and "free", else `name` and "run"."""
    fixture, copper, setting = name.split("-")
    return (f"{fixture}-{copper}-{FREE[setting]}", "free") if setting in FREE else (name, "run")


def measure(out: Path) -> dict[str, dict]:
    """p3.measure of each recorded step of names() in <out>, by its name."""
    return {name: x for name in names() if (x := p3.measure(out, *_step(name))) is not None}


def _t_max_projection(out: Path, m: dict, d: dict) -> dict:
    """Ruling 9's raise for each fixture with a compared run at T_max or a t_max_s in RAISED, read from its first such
    run, else from the winning copper's n2: {"run"; "projected_s", projected_stop of its run folder to the decided
    preset's level over t_max_fit_s; "t_max_s", that × t_max_margin rounded up to a whole ns; "k", ceil((t_max_s −
    2·t0)·f0) at its project's f0, t0 from its model.json}, each None without a run folder or a projection."""
    level, proj = PRESETS[d["decisions"]["preset"]][0], {}
    for fx in FIXTURES:
        at_t_max = d["checks"]["converged"][fx]["t_max"]
        if not at_t_max and "t_max_s" not in RAISED[fx]:
            continue
        name = (at_t_max or [f"{fx}-{d['decisions']['copper']}-n2"])[0]
        x = m.get(name)
        folder = x and x["run_dir"] and p0.run_path(x["run_dir"])
        stop = folder and projected_stop(folder, level, CRITERIA["t_max_fit_s"])
        # round() first: float noise in the product must not cost a whole ns or a whole period
        t_max = stop and math.ceil(round(stop * CRITERIA["t_max_margin"] * 1e9, 6)) / 1e9
        k = None
        if t_max:
            t0 = json.loads((folder / "model.json").read_text(encoding="utf-8"))["excitation"]["t0"]
            k = math.ceil(round((t_max - 2 * t0) * load_project(p3.project_path(out, name))["f0_hz"], 6))
        proj[fx] = {"run": name, "projected_s": stop, "t_max_s": t_max, "k": k}
    return proj


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), with p0.table, cells by p3a._cell: P3C-1 each check per
    fixture with its limit, its value (or why it is not judged), D and η where judged, its conditioning, pass and
    explained, |ΔS11| (ds11) beside its threshold ds11_shift, and the mesh check's kind, observed p and ratio; then pml,
    converged, mur and the verdict; P3C-2 each recorded step's verdict, t_stop, cells, split, f_res, depth, D, η_rad
    range, wall_s, predicted_s, worst_s, MC/s and pool; P3C-3 the decisions with their rules, then the T_max
    projections with K."""
    c, ch, d, v, cell = result["criteria"], result["checks"], result["decisions"], result["verdict"], p3a._cell
    why = "an unconditioned miss is explained when ds11 is within ds11_shift"  # no "|": a table cell
    limits = {
        "copper": f"sheet against solid at n 2: f_rel within {c['sheet_f_res_rel']:g}, Δη_rad within "
                  f"{c['sheet_eta_db']:g} dB, ΔD reported; {why}",
        "mesh": f"n 2 against the f_res extrapolated at the observed order capped at 1: within "
                f"{c['mesh_f_res_rel']:g}, not converging a fail; {why}, against the S11 extrapolated pointwise",
        "gap": f"λ/2 against λ/4: f_rel within {c['gap_f_res_rel']:g}, ΔD within {c['gap_d_db']:g} dB, Δη_rad within "
               f"{c['gap_eta_db']:g} dB; {why}",
        "preset": f"strict against normal at n 2: f_rel within {c['preset_f_res_rel']:g}, Δη_rad within "
                  f"{c['preset_eta_db']:g} dB; {why}",
        "pml": f"the free run finite, a rise of at most {c['growth_db_max']:g} dB, t_stop at least "
               f"{c['free_reach']:g} × its length"}
    rows = []
    for k in limits:
        for fx in FIXTURES:
            x = ch[k][fx]
            value = {key: x.get(key) for key in ("growth_db", "finite", "reach")} if k == "pml" else x.get("value")
            rows.append({**x, "check": k, "fixture": fx, "limit": limits[k], "value": x.get("why") or cell(value)})
    rows.append({"check": "converged", "fixture": "both", "pass": ch["converged"]["pass"],
                 "limit": "every compared run converged; a comparison that reads one at T_max or flat is not judged",
                 "value": cell({fx: ch["converged"][fx] for fx in FIXTURES})})
    rows += [{"check": "mur", "fixture": fx, "limit": "report only: MUR at λ/2 against n 2, and its free run by the "
              "PML's rule", "pass": "report only", "value": cell({k: y for k, y in x.items() if k != "report_only"})}
             for fx, x in ch["mur"].items()]
    rows.append({"check": "verdict", "fixture": "both", "value": f"{v['value']}; fails {cell(v['fails'])}",
                 "limit": "pass when every default is kept, else defaults raised; incomplete when a check is not "
                          "judged; blocked when the PML fails and a needed MUR free run grew too"})

    def run_row(name: str, x: dict) -> dict:
        jobs, eta = x.get("jobs"), x.get("eta_rad")
        stops = [x["t_stop"]] if jobs is None else [job["t_stop"] for job in jobs]
        return {"run": name, "verdict": "free" if jobs is None else cell([job["verdict"] for job in jobs]),
                "t_stop_ns": cell([t and t * 1e9 for t in stops]), "cells": x["cells"], "split": cell(x["split"]),
                "f_res_mhz": x.get("f_res_hz") and x["f_res_hz"] / 1e6, "depth_db": x.get("depth_db"),
                "d_dbi": x.get("d_dbi"), "eta_rad": cell(eta and [min(eta), max(eta)]), "wall_s": x["wall_s"],
                "predicted_s": x.get("predicted_s"), "worst_s": x.get("worst_s"),
                "mcs": cell(x.get("speeds_mcs", x.get("speed_mcs"))), "pool": x.get("pool")}

    rules = {"copper": "sheet when the copper check passes (explained counts) on both fixtures, else solid",
             "mesh_n": "3 when the mesh check fails, not explained, on either fixture",
             "gap_factor": "2 (λ/2) when the gap check fails, not explained, on either fixture",
             "preset": "strict when the preset check fails, not explained, on either fixture",
             "boundary": "mur when the PML fails on a fixture and ifa2g4's MUR free run, and that of each fixture "
                         "whose PML failed, passes the PML's rule",
             "t_max": "raised when a compared run ended at T_max or RAISED holds a t_max_s",
             "flat": "widened when a compared run ended flat or RAISED holds a flat_s",
             "edits_2g4": "the project edits P3-D and P3-E apply to the 2.4 GHz boards"}
    raise_rows = [{"fixture": fx, "run": x["run"], "projected_ns": x["projected_s"] and x["projected_s"] * 1e9,
                   "t_max_ns": x["t_max_s"] and x["t_max_s"] * 1e9, "k": x["k"]}
                  for fx, x in result["t_max_projection"].items()]
    return "\n\n".join([
        "## P3C-1 Checks\n\n" + p0.table(rows, ["check", "fixture", "limit", "value", "d_db", "eta_db", "conditioned",
                                               "pass", "explained", "ds11", "ds11_shift", "kind", "p", "ratio"]),
        "## P3C-2 Runs\n\n" + p0.table([run_row(k, x) for k, x in result["runs"].items()],
                                       ["run", "verdict", "t_stop_ns", "cells", "split", "f_res_mhz", "depth_db",
                                        "d_dbi", "eta_rad", "wall_s", "predicted_s", "worst_s", "mcs", "pool"]),
        "## P3C-3 Decisions\n\n" + p0.table([{"decision": k, "value": cell(d[k]), "rule": rule}
                                            for k, rule in rules.items()], ["decision", "value", "rule"])
        + f"\n\nT_max raised (ruling 9): the residual's decay over the last {c['t_max_fit_s'] * 1e9:g} ns projected to "
          f"the {d['preset']} preset's level × {c['t_max_margin']:g}, rounded up to a whole ns; K = ceil((T_max − "
          "2·t0)·f0).\n\n" + p0.table(raise_rows, ["fixture", "run", "projected_ns", "t_max_ns", "k"])]) + "\n"


def write(out: Path) -> dict:
    """p3.records over the recorded steps first (SystemExit on two product codes), then measure, decide and tables of
    <out>: <out>/p3c/p3c.json through p0.save, with the versions, CRITERIA, RAISED, this machine's calibration
    (p3.calibration), "runs" (each recorded step's measurements without f_hz and s11), decide's checks, decisions (with
    "edits_2g4", edits_2g4 at ifa2g4's base's air gap) and verdict, "t_max_projection", "fit2d" (fit2d_probe of each of
    ifa2g4's n3 and n4 variants made) and the steps' machine time (p0.machine); p3c.md beside it. Returns the JSON as
    saved."""
    recs = p3.records(out, [p3.step_id(*_step(name)) for name in names()])
    m = measure(out)
    d = decide(m)
    d["decisions"]["edits_2g4"] = edits_2g4(d["decisions"], load_project(p3.base(out, "ifa2g4"))["air_gap_mm"])
    variants = (f"ifa2g4-{copper}-{setting}" for copper in COPPERS for setting in ("n3", "n4"))
    result = p0.save(out / "p3c" / "p3c.json", {
        "gate": "P3-C", "versions": p0.versions(), "criteria": CRITERIA, "raised": RAISED,
        "calibration": p3.calibration(),
        "runs": {name: {key: v for key, v in x.items() if key not in ("f_hz", "s11")} for name, x in m.items()}, **d,
        "t_max_projection": _t_max_projection(out, m, d),
        "fit2d": {name: fit2d_probe(pj) for name in variants if (pj := p3.project_path(out, name)).is_file()},
        "machine": p0.machine(recs)})
    (out / "p3c" / "p3c.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p3c.py --out DIR [--steps a,b]: enters <GATES> (p3.enter) first; with --steps, runs each of them in
    order (p3.run_steps) and returns 1 when one raised, else 0; without, writes the gate and returns 0."""
    parser = argparse.ArgumentParser(prog="p3c", description="P3-C, convergence and defaults (Stage 3 design 5.11).")
    parser.add_argument("--out", required=True, help="<GATES>, outside every git work tree")
    parser.add_argument("--steps", help=f"comma-separated <fixture>-<copper>-<setting>, of {'/'.join(FIXTURES)}, "
                        f"{'/'.join(COPPERS)} and {'/'.join((*SETTINGS, 'mur', *FREE))}; without it, the report")
    args = parser.parse_args(argv)
    out = p3.enter(Path(args.out))
    if args.steps:
        return p3.run_steps(args.steps.split(","), partial(run, out))
    write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
