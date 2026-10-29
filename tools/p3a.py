# SPDX-License-Identifier: GPL-3.0-or-later
"""P3-A, the far-field sanity gate (Stage 3 design 5.11). Part 1, the dipoles. Part 2: the steps, each resumable through
p0.step and keyed by its spec's hash; the measurements; the pre-registered rules; p3a.json and p3a.md in <out>/p3a.

Dev-time only, like p0. Run: python tools/p3a.py --out DIR."""
import argparse
import contextlib
import json
import math
import sys
import traceback
from functools import partial
from pathlib import Path

import numpy as np

import p0
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.geometry.region import C0
from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.model.csx import PML_CELLS
from kicad_rf_studio.core.model.readers import read_stats
from kicad_rf_studio.core.model.spec import pulse, spec_hash, with_pml
from kicad_rf_studio.core.post.farfield import efficiencies, eta_lines, port_powers, read_far_field
from kicad_rf_studio.stoprule import growth_rise
from kicad_rf_studio.worker import DUMPS

F0, F_LO, F_HI = 2.45e9, 2.40e9, 2.50e9  # the dipoles' band, f0 its centre
F1, F2 = 1.85e9, 3.0e9  # the pulse: f_lo/1.3 and 1.2·f_hi, rounded (design 5.4)
F_HZ = [F0, F_LO, F_HI]  # the far-field frequencies, f0 first (design 5.5)
T_MAX = 30e-9  # 2·t0 + 60/f0 = 29.5 ns, rounded up (design 5.4)
GAP_MM = C0 / F_LO * 1e3 / 4  # the air gap: λ/4 at f_lo (design 5.2)
CMAX_MM = C0 / F2 * 1e3 / 20  # the air's largest cell, λ(f2)/20
CELL_MM, FEED_MM = 0.5, 1.0  # the wire's cell and the port's gap (r1's probes)
SHORT_MM, HALF_MM = 12.0, 58.0  # λ/10 at f0 (λ/20 read η_rad 0.971 in the architect's probe); r1's half-wave wire
REFS = json.loads((p0.FIX / "p3a" / "references.json").read_text(encoding="utf-8"))  # committed, never regenerated
PRESET = "normal"
STEPS = ("p3a-short", "p3a-half", "p3a-half-box2", "p3a-short-3x", "p3a-half-3x", "p3a-half-mur")  # in run order
WEIGHT_TOL, SPEED_BAND = 0.25, (0.67, 1.5)  # design 5.9's report-only decisions, pre-registered
T_FREE = REFS["growth_factor"] * T_MAX  # the free runs' end, 90 ns: Stage 1 6.4's worst-case stop time is T_max


def dipole(length_mm: float, *, f_hz: list[float] = F_HZ, boundary: str | None = "pml_8",
           box: list[list[float]] | None = None) -> dict:
    """A z-directed PEC wire dipole `length_mm` long, centred on the origin, in vacuum, as a model spec (design 5.11).
    Its arms are two curves on the x = y = 0 lines, and a 50 Ω lumped port P1 spans the FEED_MM gap, with witnesses one
    CELL_MM into each arm. The pulse runs over F1–F2 to T_MAX. Mesh lines fall every CELL_MM out to 1 mm past the wire's
    ends and to ±1 mm in x and y, then GAP_MM of air graded at 1.3 up to CMAX_MM, then with_pml. `boundary` is "pml_8"
    (None: MUR). The far field is recorded at `f_hz` about the origin, in `box` when given."""
    half, gap = length_mm / 2, FEED_MM / 2
    fine = {"x": [-1.0, -0.5, 0.0, 0.5, 1.0], "y": [-1.0, -0.5, 0.0, 0.5, 1.0],
            "z": np.arange(-half - 1.0, half + 1.0 + 1e-9, CELL_MM).tolist()}
    ends = {"x": (0.0, 0.0), "y": (0.0, 0.0), "z": (-half, half)}
    mesh = {a: with_pml([round(float(v), 6) for v in smooth_mesh_lines(
        np.array([*fine[a], ends[a][0] - GAP_MM, ends[a][1] + GAP_MM]), CMAX_MM, 1.3)]) for a in "xyz"}
    start, stop = [0.0, 0.0, -gap], [0.0, 0.0, gap]
    spec = {"mesh": mesh, "excitation": pulse(F1, F2, T_MAX), "materials": [],
            "metal": {"copper": [], "lid": {"plate": None, "walls": []}, "cylinders": [],
                      "curves": [{"at": [0.0, 0.0], "z": [gap, half]}, {"at": [0.0, 0.0], "z": [-half, -gap]}]},
            "ports": [{"name": "P1", "kind": "lumped", "dir": "z", "start": start, "stop": stop, "part": False,
                       "nodes": [start, stop, [0.0, 0.0, -gap - CELL_MM], [0.0, 0.0, gap + CELL_MM]]}],
            "grid": [], "nf2ff": {"f_hz": list(f_hz), "center": [0.0, 0.0, 0.0], **({"box": box} if box else {})}}
    return {**spec, "boundary": boundary} if boundary else spec


def inset_box(spec: dict, cells: int) -> list[list[float]]:
    """The far-field box of `spec` moved `cells` mesh lines inward from openEMS's own under PML_8, whose corners sit on
    line PML_CELLS + 1 from either end of each axis (probed): [start, stop] in mm."""
    return [[spec["mesh"][a][PML_CELLS + 1 + cells] for a in "xyz"],
            [spec["mesh"][a][-PML_CELLS - 2 - cells] for a in "xyz"]]


def specs() -> dict[str, dict]:
    """The model spec of each of STEPS: the short and the half-wave dipole; the half-wave with its box moved
    REFS["box_cells"] lines inward; both again for their free runs; and the half-wave's MUR twin, on the same mesh with
    the box where openEMS places it under PML_8."""
    short, half = dipole(SHORT_MM), dipole(HALF_MM)
    return {"p3a-short": short, "p3a-half": half,
            "p3a-half-box2": dipole(HALF_MM, box=inset_box(half, REFS["box_cells"])),
            "p3a-short-3x": short, "p3a-half-3x": half,
            "p3a-half-mur": dipole(HALF_MM, boundary=None, box=inset_box(half, 0))}


def decide(m: dict) -> dict:
    """The P3-A row's checks (design 5.11) against REFS, each limit inclusive (|v − ref| ≤ tol) and a None value a
    fail, in this order: short_d and half_d, D in dBi at f0; eta, η_rad within REFS's band at every recorded frequency
    of both dipoles (m holds the value farthest from 1); box, the half-wave's D with its box moved REFS["box_cells"]
    lines against its own; growth, both 3× runs finite with growth_db at most REFS["growth_db_max"];
    dumps_after_abort, the three base runs converged by the stop rule's ABORT, each with its 12 dumps and a far field
    read; setup, no base run's setup gate blocked. Then design 5.9's two decisions, report-only here (plan 2 applies
    them): a correction when |w_pml − 1| > WEIGHT_TOL, or when the small-model speed ratio leaves SPEED_BAND, neither
    for a None. Returns {check: {"pass"}, "pml_weight": {"value", "correction"}, "small_speed": {"ratio",
    "correction"}, "verdict": {"value": "pass" or "fail", "fails": the failed checks in order}}."""
    def near(v: float | None, ref: float | None, tol: float) -> bool:
        return v is not None and ref is not None and abs(v - ref) <= tol

    r, base, free = REFS, [m[k] for k in ("short", "half", "box2")], [m[k] for k in ("short_3x", "half_3x")]
    checks = {"short_d": near(m["short"]["d_dbi"], r["short_d_dbi"], r["short_tol_db"]),
              "half_d": near(m["half"]["d_dbi"], r["half_d_dbi"], r["half_tol_db"]),
              "eta": all(near(m[k]["eta_rad"], r["eta_rad"], r["eta_tol"]) for k in ("short", "half")),
              "box": near(m["box2"]["d_dbi"], m["half"]["d_dbi"], r["box_db"]),
              "growth": all(x["finite"] and x["growth_db"] is not None and x["growth_db"] <= r["growth_db_max"]
                            for x in free),
              "dumps_after_abort": all(x["verdict"] == "converged" and x["aborted"] and x["dumps"]
                                       and x["d_dbi"] is not None for x in base),
              "setup": not any(x["blocked"] for x in base)}
    w, ratio = m["pml"]["weight"], m["speed"]["ratio"]
    fails = [name for name, ok in checks.items() if not ok]
    return {**{name: {"pass": ok} for name, ok in checks.items()},
            "pml_weight": {"value": w, "correction": w is not None and abs(w - 1) > WEIGHT_TOL},
            "small_speed": {"ratio": ratio,
                            "correction": ratio is not None and not SPEED_BAND[0] <= ratio <= SPEED_BAND[1]},
            "verdict": {"value": "fail" if fails else "pass", "fails": fails}}


def _far(spec: dict, sid: str) -> dict:
    """A base step's work: run_model's job phase on `spec` at PRESET, port 1 only, so the stop rule ends the job, plus
    "dumps" (every name of DUMPS in its folder), "aborted" (an ABORT file there, which only the stop rule's live watch
    writes) and "far": when the dumps are there and the job kept waves, pipeline.far_field's sphere read back,
    port_powers over the job's whole waves.npz at its frequencies, and {"f_hz", "d_max", "p_rad", "p_acc", "p_inc", the
    four efficiencies, "eta_lines"}; else None."""
    run = p0.run_model(p0.model_of(spec), PRESET, sid, [1])
    (done,) = run["jobs"]
    job = p0.run_path(run["run_dir"]) / done["job"]
    dumps, far = all((job / name).is_file() for name in DUMPS), None
    if dumps and done["waves"]:
        sphere = read_far_field(pipeline.far_field(job)["sphere"])
        with np.load(job / "waves.npz") as w:
            p_acc, p_inc = port_powers(w["t_u"], w["u"][0], w["t_i"], w["i"][0], sphere.f)
        eff = efficiencies(sphere, p_acc, p_inc)
        far = {"f_hz": sphere.f, "d_max": sphere.d_max, "p_rad": sphere.p_rad, "p_acc": p_acc, "p_inc": p_inc, **eff,
               "eta_lines": eta_lines(sphere.f, eff["eta_rad"])}
    return {**run, "dumps": dumps, "aborted": (job / "ABORT").is_file(), "far": far}


def _free(spec: dict, sid: str) -> dict:
    """A free step's work, the worker's own path with no stop rule, to T_FREE: pipeline.prepare for the threads; a
    fresh run folder with model.json and one job of port P1, run unwatched and checked under the tool's own word "run";
    its et and ht removed; openEMS_stats.txt, which openEMS and the fake both write, read; then its records at that dt.
    Returns {"run_dir": the folder's name, never a path (the privacy gate refuses one), "t_max", "t_stop", "dt",
    "speed_mcs", "finite": every u, i and energy sample finite, "growth_db": growth_rise}."""
    threads = pipeline.prepare(p0.model_of(spec), lambda code, params: print(render(code, **params)))[0]
    run_dir, settings = runs.run_dir_for(sid), runs.load_settings()
    runs.write_spec(run_dir, spec)
    job = runs.write_job(runs.job_dir(run_dir, 1, "P1"), 1, "run", threads, T_FREE)
    runs.check_job(job, runs.run_jobs([job], 1, run_dir, settings)[job], "run", settings)
    for array in ("et", "ht"):  # as run_ports removes them (D-17)
        with contextlib.suppress(OSError):  # Windows: an antivirus or the indexer may still hold it; it stays
            (job / array).unlink(missing_ok=True)
    stats = read_stats((job / "openEMS_stats.txt").read_text(encoding="utf-8"))
    rec = pipeline.records(job, 1, stats["dt"])
    return {"run_dir": run_dir.name, "t_max": T_FREE, "t_stop": pipeline.last_sample(rec)[0], "dt": stats["dt"],
            "speed_mcs": stats["speed"] / 1e6, "finite": all(np.isfinite(x).all() for x in (rec.u, rec.i, rec.e)),
            "growth_db": growth_rise(rec, spec["excitation"]["t0"])}


def measure(out: Path) -> dict:
    """The P3-A measurements of the P0 folder `out`, from its step records (p0.records: every step, one code) and one
    calibration entry, read as p0c does: this machine's in settings.json, which the first step's prepare stored and
    run_model never refreshes. "short", "half" and "box2", the base runs: their job's "verdict", "aborted", "dumps",
    "blocked" (the setup gate's codes), "d_dbi" (D at f0, the first frequency) and "eta_rad" (η_rad farthest from 1),
    both None without a far field, "warnings" (run_model's codes and eta_lines'), "cells" (Π len(mesh lines), as cost
    counts), "dt" (the setup's), "t_stop", "wall_s" (run_model's, the job phase), "speed_mcs" and "predicted_s".
    "short_3x", "half_3x" and "mur", the free runs: their step's result plus "cells", "wall_s" (the step's) and
    "predicted_s". predicted_s is p0.predicted_s of one job to t_stop at runs.per_job_mcs(entry, 1), None without one.
    "pml": {"cells", "pml_cells", "weight"}: pml_cells counts the nodes openEMS's UPML updates, PML_CELLS + 1 lines per
    face (operator_ext_upml.cpp), and the weight w = 1 + (s_MUR/s_PML − 1)·cells/pml_cells comes from the two free runs
    of the half-wave over the same steps. "speed": {"measured_mcs", "predicted_mcs", "ratio"}, the MUR twin's MC/s
    against the entry's single-job MC/s, so the PML's own cost is counted once, in w."""
    recs, spec = dict(zip(STEPS, p0.records(out, list(STEPS)))), specs()
    entry = runs.load_settings().get("machines", {}).get(runs.machine_key())
    mcs = runs.per_job_mcs(entry, 1) if entry else None

    def cells(sid: str) -> int:
        return math.prod(len(spec[sid]["mesh"][a]) for a in "xyz")  # as cost counts

    def predicted(n: int, dt: float, t: float | None) -> float | None:
        return None if None in (mcs, t) else p0.predicted_s(1, 1, n, dt, t, mcs)

    m = {}
    for name, sid in zip(("short", "half", "box2"), STEPS[:3]):
        res, n = recs[sid]["result"], cells(sid)
        (job,), far, dt = res["jobs"], res["far"], res["setup"]["dt"]
        d0, etas = (None, [None]) if far is None else (far["d_max"][0], far["eta_rad"])  # JSON: a NaN reads None
        m[name] = {"verdict": job["verdict"], "aborted": res["aborted"], "dumps": res["dumps"],
                   "blocked": [code for code, _ in res["blocked"]],
                   "d_dbi": None if d0 is None else 10 * math.log10(d0),
                   "eta_rad": None if None in etas else max(etas, key=lambda v: abs(v - 1)),
                   "warnings": [code for code, _ in res["warnings"] + (far["eta_lines"] if far else [])],
                   "cells": n, "dt": dt, "t_stop": job["t_stop"], "wall_s": res["wall_s"],
                   "speed_mcs": next(iter(res["speeds_mcs"]), None), "predicted_s": predicted(n, dt, job["t_stop"])}
    for name, sid in zip(("short_3x", "half_3x", "mur"), STEPS[3:]):
        res, n = recs[sid]["result"], cells(sid)
        m[name] = {**res, "cells": n, "wall_s": recs[sid]["wall_s"],
                   "predicted_s": predicted(n, res["dt"], res["t_stop"])}
    lines = [len(spec["p3a-half-mur"]["mesh"][a]) for a in "xyz"]  # half_3x's mesh too
    n = math.prod(lines)
    pml = n - math.prod(k - 2 * (PML_CELLS + 1) for k in lines)
    s_mur, s_pml = m["mur"]["speed_mcs"], m["half_3x"]["speed_mcs"]
    m["pml"] = {"cells": n, "pml_cells": pml, "weight": 1 + (s_mur / s_pml - 1) * n / pml}
    m["speed"] = {"measured_mcs": s_mur, "predicted_mcs": mcs, "ratio": None if mcs is None else s_mur / mcs}
    return m


def _cell(v) -> str:
    """`v` as the P3-A tables show it: None as "–", a float as :.4g, a list's items joined by ", " ("none" when it is
    empty) and a dict's "key value" pairs by "; "."""
    if isinstance(v, dict):
        return "; ".join(f"{key} {_cell(x)}" for key, x in v.items())
    if isinstance(v, list):
        return ", ".join(map(_cell, v)) or "none"
    return "–" if v is None else f"{v:.4g}" if isinstance(v, float) else str(v)


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), with p0.table: P3A-1 each check with its limit, its
    value and its pass; P3A-2 each step's verdict, cells, D in dBi, η_rad, growth_db, wall_s, predicted_s and MC/s;
    P3A-3 the two decisions with what they measured and their rule, and the verdict."""
    r, d = result["references"], result["decisions"]
    base = {k: result[k] for k in ("short", "half", "box2")}
    half, box2 = base["half"]["d_dbi"], base["box2"]["d_dbi"]
    checks = {
        "short_d": (f"{r['short_d_dbi']:g} ± {r['short_tol_db']:g} dBi at f0", base["short"]["d_dbi"]),
        "half_d": (f"{r['half_d_dbi']:g} ± {r['half_tol_db']:g} dBi at f0", half),
        "eta": (f"{r['eta_rad']:g} ± {r['eta_tol']:g} at every frequency (the value farthest from 1)",
                {k: base[k]["eta_rad"] for k in ("short", "half")}),
        "box": (f"ΔD within ± {r['box_db']:g} dB, the box {r['box_cells']} cells in",
                None if None in (half, box2) else box2 - half),
        "growth": (f"finite, a rise of at most {r['growth_db_max']:g} dB to {r['growth_factor']} × T_max",
                   {k: result[k]["growth_db"] if result[k]["finite"] else "not finite"
                    for k in ("short_3x", "half_3x")}),
        "dumps_after_abort": ("converged by the stop rule's ABORT, the 12 dumps, a far field read",
                              {k: f"{x['verdict']}, aborted {x['aborted']}, dumps {x['dumps']}, far field "
                                  f"{x['d_dbi'] is not None}" for k, x in base.items()}),
        "setup": ("no setup gate blocked", {k: x["blocked"] for k, x in base.items()})}
    rules = {"pml_weight": (result["pml"], f"a correction when w leaves 1 ± {WEIGHT_TOL:g}"),  # no "|": a table cell
             "small_speed": (result["speed"],
                             f"a correction when the ratio leaves [{SPEED_BAND[0]:g}, {SPEED_BAND[1]:g}]"),
             "verdict": (None, "pass when every check passes")}
    return "\n\n".join([
        "## P3A-1 Checks\n\n" + p0.table([{"check": k, "limit": limit, "value": _cell(v), "pass": d[k]["pass"]}
                                         for k, (limit, v) in checks.items()], ["check", "limit", "value", "pass"]),
        "## P3A-2 Runs\n\n" + p0.table([{"run": k, **result[k]} for k in ("short", "half", "box2", "short_3x",
                                                                         "half_3x", "mur")],
                                       ["run", "verdict", "cells", "d_dbi", "eta_rad", "growth_db", "wall_s",
                                        "predicted_s", "speed_mcs"]),
        "## P3A-3 Decisions\n\n" + p0.table([{"decision": k, "measured": _cell(v), "rule": rule, "result": _cell(d[k])}
                                            for k, (v, rule) in rules.items()],
                                           ["decision", "measured", "rule", "result"])]) + "\n"


def write(out: Path) -> dict:
    """measure, decide and tables of the P0 folder `out`: <out>/p3a/p3a.json through p0.save, whose "calibration" is
    this machine's settings entry without its key, which holds a host name, and p3a.md beside it. Returns the JSON as
    saved."""
    m = measure(out)
    entry = runs.load_settings().get("machines", {}).get(runs.machine_key()) or {}
    result = p0.save(out / "p3a" / "p3a.json", {
        "gate": "P3-A", "versions": p0.versions(), "references": REFS,
        "calibration": {key: entry.get(key) for key in ("aggregate_mcs", "pool", "threads", "levels")}, **m,
        "decisions": decide(m), "machine": p0.machine(p0.records(out, list(STEPS)))})
    (out / "p3a" / "p3a.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p3a.py --out DIR: enters the P0 folder first, then runs each of STEPS through p0.step, keyed by its
    spec's hash (a free run's also by T_FREE), _far for the three base steps and _free for the others, printing a step
    that raises and going on with the next. Returns 1 when a step raised; else writes the gate and returns 0. A rerun
    finds every record stored, so it only assembles."""
    parser = argparse.ArgumentParser(prog="p3a", description="P3-A, the far-field sanity gate (Stage 3 design 5.11).")
    parser.add_argument("--out", required=True, help="the P0 folder, outside every git work tree")
    out, spec, failed = p0.enter(Path(parser.parse_args(argv).out)), specs(), []
    for sid in STEPS:
        print(f"p3a: {sid}", flush=True)
        base = sid in STEPS[:3]
        key = spec_hash(spec[sid]) if base else f"{spec_hash(spec[sid])}@{T_FREE!r}"
        try:
            p0.step(out, sid, key, partial(_far if base else _free, spec[sid], sid))
        except Exception:  # logged and skipped; SystemExit (STOP) and KeyboardInterrupt end the harness
            failed.append(sid)
            traceback.print_exc()
    if failed:
        print(f"p3a: failed steps: {', '.join(failed)}", flush=True)
        return 1
    write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
