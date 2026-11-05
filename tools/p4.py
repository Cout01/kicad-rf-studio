# SPDX-License-Identifier: GPL-3.0-or-later
"""The gates P4-B to P4-F's shared runner (Stage 4 design 5.11, plan 4 ruling G-1), on p0's and p3's machinery:
- the gates folder;
- a base project per board from `new --interface` (test_p4_fixtures.P4_NEW);
- its variants at a mesh n, a mesh rule and a dielectric;
- resumable run steps keyed by model, preset and code;
- the one-code check;
- in-process measurements of a run's chain, with cost's own SI time and the product's validity flags;
- the deltas compare would read;
- the SI cost refit's rows.

Checkpoint decisions are this module's constants N, RULE, DIELECTRIC, EDITS and BENDS_N3, never src. Dev-time only,
like p0."""
import json
import math
import shutil
import sys
from pathlib import Path
from statistics import median

import numpy as np

import p0
import p3
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.readers import read_stats
from kicad_rf_studio.core.model.spec import debye_cells
from kicad_rf_studio.core.post.checks import RECIP_LIMIT, SIGMA_LIMIT
from kicad_rf_studio.core.post.si import Reading, read, si_deltas
from kicad_rf_studio.core.project import load_project
from kicad_rf_studio.stoprule import KEPT

sys.path.append(str(p0.ROOT / "tests"))  # test_p4_fixtures: P4_NEW, each board's new arguments written once
from test_p4_fixtures import P4_NEW  # noqa: E402

N = 2  # mesh n, P4-B's checkpoint (B-6)
# the SI rule, "l40" (new's λ/40), "l80" (λ/80) or "dfill" (max_cell_mm null), P4-C's checkpoint (C-2, C-3)
RULE = "l40"
DIELECTRIC = "lossless"  # P4-D's checkpoint (§5.3's rule)
EDITS: dict[str, dict] = {}  # project edits by board, Task 3's recorded fit2d blocks (Stage 3 ruling 2's limit)
# the owner's answer on a 45° twin's n 3 run (B-4): "pending", or "declined" when no go comes by P4-F's report
BENDS_N3 = "pending"

enter, records, run_steps = p3.enter, p3.records, p3.run_steps  # the gates folder, the one-code check, the step loop


def base(out: Path, board: str) -> Path:
    """The base project of the fixture `board` (its file's stem), made when missing by `new` with P4_NEW's arguments
    on its copy in out/boards, copied once. RuntimeError naming new's exit code and last line on a non-zero exit.
    Returns the project file."""
    kept, pj = out / "boards" / f"{board}.kicad_pcb", p3.project_path(out, board)
    if not kept.is_file():
        kept.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p0.FIX / kept.name, kept)
    if not pj.is_file():
        code, text = p0.cli("new", str(kept), *P4_NEW[board], "-o", str(pj.parent))
        if code:
            raise RuntimeError(f"p4: new exited {code}: {(text.strip().splitlines() or [''])[-1]}")
    return pj


def name(board: str, n: int | None = None, rule: str | None = None, dielectric: str | None = None,
         tag: str = "") -> str:
    """The name of `board`'s project at mesh n `n`, the rule `rule` and the dielectric `dielectric`, each None for its
    checkpoint constant: <board>-n<n>-<rule>, then -debye for a Debye dielectric, then -<tag> when given."""
    debye = "-debye" if (dielectric or DIELECTRIC) == "debye" else ""
    return f"{board}-n{n or N}-{rule or RULE}{debye}" + (f"-{tag}" if tag else "")


def settings(base: dict, n: int | None = None, rule: str | None = None, dielectric: str | None = None) -> dict:
    """The edits (p0.edit's dotted keys) that set the base project `base` to mesh n `n`, the rule `rule` and the
    dielectric `dielectric`, each None for its checkpoint constant: "mesh.n"; "mesh.max_cell_mm", the base's (new's
    λ/40) for "l40", half of it to 1e-6 mm for "l80", None for "dfill"; "dielectric"."""
    cell = base["mesh"]["max_cell_mm"]
    return {"mesh.n": n or N, "mesh.max_cell_mm": {"l40": cell, "l80": round(cell / 2, 6), "dfill": None}[rule or RULE],
            "dielectric": dielectric or DIELECTRIC}


def project(out: Path, board: str, n: int | None = None, rule: str | None = None, dielectric: str | None = None,
            tag: str = "", extra: dict | None = None) -> tuple[str, Path]:
    """`board`'s project named by name(), p3's variant of base(out, board) under settings, then EDITS' edits of the
    board, then `extra`. Returns (its name, its project file)."""
    edits = settings(load_project(base(out, board)), n, rule, dielectric) | EDITS.get(board, {}) | (extra or {})
    title = name(board, n, rule, dielectric, tag)
    return title, p3.variant(out, title, board, edits, make=base)


# ponytail: no keep-awake call (the sleep timeout is 0); a reaped or rebooted step reruns
def run_step(out: Path, name: str) -> dict:
    """p3's run step on the project `name`, its id p4-<name>-run. Returns the record."""
    return p3.run_step(out, name, "run", prefix="p4")


def plateau(r: Reading, t0: float, t1: float) -> float | None:
    """The median of r.z over t0 ≤ t ≤ t1 (s); None when (t1 − t0)/r.rise[0] < 1 − 1e-9 (one rise time, to rounding)
    or no sample falls there."""
    z = r.z[(r.t >= t0) & (r.t <= t1)]
    return float(np.median(z)) if len(z) and (t1 - t0) / r.rise[0] >= 1 - 1e-9 else None


def reading(pj: Path, project: dict) -> tuple[Reading | None, str | None]:
    """The SI reading of the run in `project`'s results (project.json at `pj`), as write_outputs takes it: the chain of
    chain_results (a coupon's chain is its layout), read at the run's route's εeff. (the Reading, None); (None, the
    KrsError's code) when chain_results refuses; (None, None) with no chain."""
    try:
        res = pipeline.chain_results(pj, project)
    except KrsError as err:
        return None, err.code
    if res.chain is None:
        return None, None
    return read(res.chain, res.lay.f, project, project["results"]["route"]["eeff"]), None


def measure(out: Path, name: str) -> dict | None:
    """The measurements of the run step on the project `name`, in this process; None when the step has no record.
    p0.summary of the record, with "predicted_s" (to the longest t_stop of the jobs that kept S) and "worst_s" (to
    the spec's T_max) by predicted_s, as cost printed them: on the run folder's model.json and the calibration the
    step's load saw at its start. Then "speeds_mcs", the MC/s of each job that wrote its openEMS_stats.txt, and
    "node_mcs", their median; "cal_mcs", runs.calibrated_mcs at the run's pool; "debye_cells"; "converged", every
    job converged, a run with none not; "valid", converged with the summary's sigma and recip within
    checks.SIGMA_LIMIT and RECIP_LIMIT (the product's flags); "blocked", exit 3; "t_stop_s", the longest t_stop kept;
    "fingerprint", the results'; and "project", project.json as loaded. Each None without model.json, the pool, the
    calibration or such a job; the fingerprint None, too, when project.json's results are not this run's (run_dir
    names differ). "reading" and "reading_error": reading's when the step exited 0 and the results are its run's,
    else (None, None)."""
    path = out / "steps" / f"{p3.step_id(name, 'run', 'p4')}.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    m, entry = p0.summary(record), record["load"]["calibration"]
    folder = p0.run_path(m["run_dir"]) if m["run_dir"] else None
    file = folder and folder / "model.json"
    spec = json.loads(file.read_text(encoding="utf-8")) if file and file.is_file() else None
    pool, dt = m["pool"], m["dt"]
    t_stop = max((job["t_stop"] for job in m["jobs"] if job["verdict"] in KEPT and job["t_stop"] is not None),
                 default=None)

    def time_to(t: float | None) -> float | None:
        return None if None in (spec, dt, t, pool, entry) else predicted_s(spec, dt, t, pool, len(spec["ports"]), entry)

    stats = sorted(folder.glob("job-[1-9]*/openEMS_stats.txt")) if folder else []
    speeds = [s["speed"] / 1e6 for p in stats if (s := read_stats(p.read_text(encoding="utf-8")))]
    pj = p3.project_path(out, name)
    project = load_project(pj)
    results = project.get("results") or {}
    ours = m["run_dir"] is not None and Path(results.get("run_dir", "")).name == m["run_dir"]
    converged = bool(m["jobs"]) and all(job["verdict"] == "converged" for job in m["jobs"])
    sigma, recip = m["indicators"]["sigma"], m["indicators"]["recip"]
    r, error = reading(pj, project) if ours and m["exit"] == 0 else (None, None)
    return {**m, "predicted_s": time_to(t_stop), "worst_s": time_to(spec and spec["excitation"]["t_max"]),
            "speeds_mcs": speeds or None, "node_mcs": median(speeds) if speeds else None,
            "cal_mcs": entry and pool and runs.calibrated_mcs(entry, pool), "debye_cells": spec and debye_cells(spec),
            "converged": converged,
            "valid": converged and None not in (sigma, recip) and sigma <= SIGMA_LIMIT and recip <= RECIP_LIMIT,
            "blocked": m["exit"] == 3, "t_stop_s": t_stop, "fingerprint": results.get("fingerprint") if ours else None,
            "project": project, "reading": r, "reading_error": error}


def plain(m: dict) -> dict:
    """The measure `m` without "reading" and "project", as a gate's JSON holds it."""
    return {key: value for key, value in m.items() if key not in ("reading", "project")}


def deltas(a: dict, b: dict) -> list[dict]:
    """si_deltas of the measure `b` against the measure `a` (the base), on a's project, as compare reads them.
    ValueError naming the differing keys, sorted, when their fingerprints differ, as compare refuses."""
    keys = a["fingerprint"].keys() | b["fingerprint"].keys()
    if fields := sorted(key for key in keys if a["fingerprint"].get(key) != b["fingerprint"].get(key)):
        raise ValueError(f"p4: the fingerprints differ in {', '.join(fields)}")
    return si_deltas(a["project"], a["reading"], b["reading"])


def predicted_s(spec: dict, dt: float, t: float, pool: int, jobs: int, entry: dict) -> float:
    """The machine time in s that cost predicts for `jobs` jobs of the SI model `spec` at the timestep `dt` (s) to the
    simulated time `t` (s), `pool` at once, on the calibration `entry`: each cell of a Debye dielectric (debye_cells)
    counts as runs.DEBYE_WEIGHT cells, at runs.per_job_mcs at that pool, taken at runs.SI_SPEED of it while it is the
    calibration's own (runs.calibrated_mcs)."""
    # mirrors pipeline.cost_notes and prepare(si=True)
    mcs = runs.per_job_mcs(entry, pool)
    if mcs == runs.calibrated_mcs(entry, pool):
        mcs *= runs.SI_SPEED
    cells = math.prod(len(spec["mesh"][a]) for a in "xyz")
    return p0.predicted_s(jobs, pool, cells + (runs.DEBYE_WEIGHT - 1) * debye_cells(spec), dt, t, mcs)


def rows(out: Path) -> list[dict]:
    """The SI cost refit's rows (ruling K-1), one per record in out/steps of a run step (p4-…-run) that was not
    loaded, through measure: {"step", "pool", "cells", "debye_cells", "node_mcs", "cal_mcs"}, a row lacking any of
    them left out."""
    # ponytail: measure reads each run's Reading too, unused here; a cost-only reader at hundreds of steps
    found = []
    for path in sorted((out / "steps").glob("p4-*-run.json")):
        if json.loads(path.read_text(encoding="utf-8"))["loaded"]:
            continue
        m = measure(out, path.stem.removeprefix("p4-").removesuffix("-run"))
        row = {"step": path.stem, **{key: m[key] for key in ("pool", "cells", "debye_cells", "node_mcs", "cal_mcs")}}
        if None not in row.values():
            found.append(row)
    return found


def refit(rows: list[dict]) -> dict:
    """The SI speed refit (ruling K-1) of `rows` (rows()'s) with no Debye cell, each row's ratio node_mcs/cal_mcs, its
    speed over the calibration's own per-job speed at its pool: "si_speed", their median to 3 significant digits;
    "range", [min, max]; "by_pool", {pool: their median}; "rows", their count."""
    lossless = [row for row in rows if not row["debye_cells"]]
    ratios = [row["node_mcs"] / row["cal_mcs"] for row in lossless]
    pools = sorted({row["pool"] for row in lossless})
    return {"si_speed": float(f"{median(ratios):.3g}"), "range": [min(ratios), max(ratios)],
            "by_pool": {pool: median(k for row, k in zip(lossless, ratios) if row["pool"] == pool) for pool in pools},
            "rows": len(ratios)}


def refit_record(out: Path, w: float, dest: Path) -> dict:
    """The SI cost refit's record (ruling K-1): refit of rows(out), beside `w`, the Debye weight gate P4-D measured.
    Writes <dest>.json through p0.save, {"rows", "result", "w", "before": runs.SI_SPEED and runs.DEBYE_WEIGHT as they
    stood}, and <dest>.md: the rows with each ratio, then the result, as p0.table's. Returns the JSON as saved."""
    every = rows(out)
    result = refit(every)
    before = {"SI_SPEED": runs.SI_SPEED, "DEBYE_WEIGHT": runs.DEBYE_WEIGHT}
    data = p0.save(Path(f"{dest}.json"), {"rows": every, "result": result, "w": w, "before": before})
    items = [{"item": "si_speed", "value": result["si_speed"]},
             {"item": "range", "value": "–".join(f"{k:.4g}" for k in result["range"])},
             *({"item": f"pool {pool}", "value": k} for pool, k in result["by_pool"].items()),
             {"item": "rows", "value": result["rows"]}]
    Path(f"{dest}.md").write_text("\n\n".join([
        "# The SI cost refit (Stage 4 design 5.9)",
        f"Each row's ratio = node_mcs/cal_mcs, its speed over the calibration's own per-job speed at its pool; the SI "
        f"speed is their median over the rows with no Debye cell. w, gate P4-D's Debye weight: {w}. Before: SI_SPEED "
        f"{before['SI_SPEED']}, DEBYE_WEIGHT {before['DEBYE_WEIGHT']}.",
        p0.table([{**row, "ratio": row["node_mcs"] / row["cal_mcs"]} for row in every],
                 ["step", "pool", "cells", "debye_cells", "node_mcs", "cal_mcs", "ratio"]),
        p0.table(items, ["item", "value"])]) + "\n", encoding="utf-8")
    return data
