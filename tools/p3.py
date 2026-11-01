# SPDX-License-Identifier: GPL-3.0-or-later
"""The gates P3-B to P3-E's shared runner (Stage 3 design 5.11, plan 4): the gates folder, the base project from `new`
and its variants, resumable run, verify and free steps through the product's CLI, the one-code check over a gate's
records, in-process measurements, the pair rule P3-B and P3-C share, and the cost refit from the gates' step records
(design 5.9). Dev-time only, like p0."""
import copy
import json
import math
import shutil
import traceback
from collections.abc import Callable
from functools import partial
from pathlib import Path
from statistics import median

import numpy as np

import p0
import p3a
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import CURVE_PORT, PORT
from kicad_rf_studio.core.model.readers import read_stats
from kicad_rf_studio.core.model.spec import cell_split, spec_hash
from kicad_rf_studio.core.post.antenna import dip_resonance, resonance
from kicad_rf_studio.core.project import load_project, parts, save_project
from kicad_rf_studio.stoprule import KEPT


def enter(out: Path) -> Path:
    """p0.enter of the gates folder `out` (<GATES>), which it returns resolved. SystemExit, with nothing made, when
    `out`, resolved, lies inside the per-user data folder (runs.data_dir(), read before entering) or inside a P0
    folder, one whose name starts with kicad-rf-studio-p0, itself included."""
    path = out.resolve()
    if path.is_relative_to(runs.data_dir().resolve()) or any(
            p.name.startswith("kicad-rf-studio-p0") for p in (path, *path.parents)):
        raise SystemExit(f"p3: {path} is inside the data folder or a P0 folder; choose another gates folder")
    return p0.enter(out)


def project_path(out: Path, name: str) -> Path:
    """The project.json of the project `name`, a board's base or a variant, in the gates folder `out`."""
    return out / "projects" / name / "project.json"


def base(out: Path, board: str) -> Path:
    """The base project of the fixture `board` (its file's stem), made when missing by `new` on its copy in out/boards,
    copied once: start U1.1, antenna AE1, the band 902–928 MHz for a meander, else 2400–2483.5 MHz. RuntimeError naming
    new's exit code and last line on a non-zero exit. Returns the project file."""
    kept, pj = out / "boards" / f"{board}.kicad_pcb", project_path(out, board)
    if not kept.is_file():
        kept.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p0.FIX / kept.name, kept)
    if not pj.is_file():
        band = "902MHz:928MHz" if board.startswith("meander") else "2400MHz:2483.5MHz"
        code, text = p0.cli("new", str(kept), "--start", "U1.1", "--antenna", "AE1", "--band", band,
                            "-o", str(pj.parent))
        if code:
            raise RuntimeError(f"p3: new exited {code}: {(text.strip().splitlines() or [''])[-1]}")
    return pj


def variant(out: Path, name: str, board: str, edits: dict) -> Path:
    """The project `name` (p0c's variant): made when missing as a copy of base(out, board) without results and verify,
    then `edits` (p0.edit) on every call, saved only when they change it, so that it keeps its own results until an
    edit changes it. Returns the project file."""
    pj = project_path(out, name)
    if not pj.is_file():
        pj.parent.mkdir(parents=True, exist_ok=True)
        save_project(pj, {k: v for k, v in load_project(base(out, board)).items() if k not in ("results", "verify")})
    data = load_project(pj)
    edited = p0.edit(copy.deepcopy(data), edits)
    if edited != data:
        save_project(pj, edited)
    return pj


def step_id(name: str, command: str) -> str:
    """The id of the step of `command` ("run", "verify" or "free") on the project `name`."""
    return f"p3-{name}-{command}"


def run_step(out: Path, name: str, command: str = "run") -> dict:
    """`command`, "run" or "verify", on the project `name` through the product's CLI (p0.cli_run), a p0.step keyed by
    its model's hash and its preset, which the spec does not hold, and for verify by the values of its part ports too,
    so that an edit that changes any of them runs it again. No `cost` runs: the run's own events carry the cost lines,
    and measure predicts from the formula. Returns the record."""
    pj = project_path(out, name)
    project = load_project(pj)
    key = f"{p0.model_key(pj)}|{project['preset']}"
    if command == "verify":
        values = {ref: q["value"] for ref, q in parts(project).items() if q["role"] in (PORT, CURVE_PORT)}
        key += "|" + ",".join(f"{ref}={value}" for ref, value in sorted(values.items()))
    return p0.step(out, step_id(name, command), key, lambda: p0.cli_run(pj, command))


def free_step(out: Path, name: str, t_free: float) -> dict:
    """The free run of the project `name`'s model (pipeline.load, build_model) to `t_free` s with no stop rule
    (p3a._free), a p0.step keyed by its spec's hash and that length. Returns the record."""
    project, board, geom, _ = pipeline.load(project_path(out, name))
    spec, sid = pipeline.build_model(project, board, geom).spec, step_id(name, "free")
    return p0.step(out, sid, f"{spec_hash(spec)}@{t_free!r}", partial(p3a._free, spec, sid, t_free))


def records(out: Path, ids: list[str]) -> list[dict]:
    """The records of the steps among `ids` that ran (p0.records); SystemExit when they ran on two product codes. Every
    gate's write calls it over its product steps first."""
    return p0.records(out, [i for i in ids if (out / "steps" / f"{i}.json").is_file()])


def _entry() -> dict | None:
    """This machine's calibration entry in settings.json, as p3a reads it; None before one."""
    return runs.load_settings().get("machines", {}).get(runs.machine_key())


def measure(out: Path, name: str, command: str = "run") -> dict | None:
    """The measurements of the step of `command` on the project `name`, in this process; None when the step has no
    record. "free": its record's result plus "cells" and "split" (cell_split) of its run folder's model.json and
    "wall_s", the step's. "run" and "verify": p0.summary of the record with "predicted_s" and "worst_s" recomputed by
    predicted_s, as cost prints them before the run, to the longest t_stop of the jobs that kept S and to the spec's
    T_max; plus "split", cell_split of the run folder's model.json; "cal_mcs", the per-job MC/s that prepare(small=True)
    took at the run's pool from this machine's calibration entry; "speeds_mcs", the MC/s of each job that wrote its
    openEMS_stats.txt. Each of those None without model.json, the pool or such a job: exits 2, 3 and 4 are recorded.
    Then from pipeline.antenna_result of the project (a KrsError gives None to each): "f_hz" and "s11", the band grid
    and S11, kept in memory, which the gates drop from their JSON; "band", [f_lo, f_hi]; "f_res_hz" and "depth_db",
    resonance's and |S11| there in dB; "conditioned", whether dip_resonance finds a dip (the lowest |S11| inside the
    grid at or below −6 dB); "far_f_hz", "d_dbi" (D_max at the first recorded frequency, f0), "eta_rad" and "eta_tot",
    in the recorded order, each None without a far field. Python floats and bools, never numpy's."""
    path = out / "steps" / f"{step_id(name, command)}.json"
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    res = record["result"]
    folder = p0.run_path(res["run_dir"]) if res["run_dir"] else None
    file = folder and folder / "model.json"
    spec = json.loads(file.read_text(encoding="utf-8")) if file and file.is_file() else None
    if command == "free":
        return {**res, "cells": math.prod(len(spec["mesh"][a]) for a in "xyz"), "split": list(cell_split(spec)),
                "wall_s": record["wall_s"]}
    m, entry = p0.summary(record), _entry()
    pool, cal = m["pool"], None
    if entry and pool:  # mirrors pipeline.prepare(small=True)
        cal = runs.per_job_mcs(entry, pool)
        if pool == 1:
            cal = entry.get("single", {}).get(str(entry["threads"]), cal)
    kept = [job["t_stop"] for job in m["jobs"] if job["verdict"] in KEPT and job["t_stop"] is not None]

    def time_to(t: float | None) -> float | None:
        return None if None in (spec, m["dt"], t, cal) else predicted_s(spec, m["dt"], t, pool, len(spec["ports"]), cal)

    stats = sorted(folder.glob("job-[1-9]*/openEMS_stats.txt")) if folder else []
    speeds = [s["speed"] / 1e6 for p in stats if (s := read_stats(p.read_text(encoding="utf-8")))]
    try:
        r = pipeline.antenna_result(project_path(out, name))
    except KrsError:  # E_COMPARE_NO_RESULT (no results, stale ones, their files gone) or another refusal
        r = None
    far = r and r["far"]
    k, f_res = resonance(r["f"], r["s11"]) if r else (None, None)
    return {**m, "predicted_s": time_to(max(kept, default=None)),
            "worst_s": time_to(spec and spec["excitation"]["t_max"]), "split": spec and list(cell_split(spec)),
            "cal_mcs": cal, "speeds_mcs": speeds or None, "f_hz": r and r["f"], "s11": r and r["s11"],
            "band": r and [float(r["project"]["band"][key]) for key in ("f_lo_hz", "f_hi_hz")], "f_res_hz": f_res,
            "depth_db": r and float(20 * np.log10(abs(r["s11"][k]))),
            "conditioned": r and dip_resonance(r["f"], r["s11"]) is not None,
            "far_f_hz": far and far["sphere"].f.tolist(),
            "d_dbi": far and float(10 * np.log10(far["sphere"].d_max[0])),
            "eta_rad": far and far["eff"]["eta_rad"].tolist(), "eta_tot": far and far["eff"]["eta_tot"].tolist()}


def pair(a: dict, b: dict, limit: float, conditioned_db: float) -> dict:
    """Ruling 1's pair rule, as amended at commit, on the measures `a` and `b` (or dicts of their shape: "f_hz" and
    "s11" on one grid, "band", "d_dbi", "far_f_hz", "eta_rad"): "f_res" [f_a, f_b] and "depth_db", resonance's on each;
    "f_rel" |f_b − f_a|/f_a, but a pair with no resonance in its grid (either lowest |S11| at its first or last point)
    is judged by fit_shift's response shift when that fit is clean (its residual at most a quarter of ds11): the
    controller's ruling at P3-C's CP3, f_rel then |x|/(1 + x), b's resonance against a's; otherwise f_rel stays the
    argmins' (vacuous); "fit", fitted's {"shift", "residual", "clean"} there, None when both lowest |S11| lie inside
    the grid; "conditioned", both lowest |S11| inside the grid and at or below `conditioned_db`; "ds11",
    the largest |S_b − S_a| over a's band [f_lo, f_hi]; "ds11_shift", the largest |S_a(f·(1 + limit)) − S_a(f)| there,
    S_a interpolated in its real and imaginary parts: what a shift of `limit` does to a's S11; "pass" f_rel ≤ `limit`;
    "explained", a miss on no conditioned dip whose curves differ by no more than ds11_shift; "d_db" |D_b − D_a| at f0;
    "eta_db", the largest |10·log10(η_b/η_a)| over a's recorded frequencies, b's nearest to each; D and η None when
    either side lacks them. Python floats and bools."""
    f, sa, sb = np.asarray(a["f_hz"]), np.asarray(a["s11"]), np.asarray(b["s11"])
    (ka, fa), (kb, fb) = resonance(f, sa), resonance(f, sb)
    depth = [float(20 * np.log10(abs(s[k]))) for s, k in ((sa, ka), (sb, kb))]
    band = (f >= a["band"][0]) & (f <= a["band"][1])
    up = f[band] * (1 + limit)  # past the grid's end np.interp holds the last value: a stricter explanation only
    ds11 = float(np.abs(sb - sa)[band].max())
    ds11_shift = float(np.abs(np.interp(up, f, sa.real) + 1j * np.interp(up, f, sa.imag) - sa[band]).max())
    inside = all(0 < k < len(f) - 1 for k in (ka, kb))
    fit = None if inside else fitted(a, b)  # no resonance in the grid: the controller's ruling at P3-C's CP3
    f_rel = abs(fit["shift"]) / (1 + fit["shift"]) if fit and fit["clean"] else abs(fb - fa) / fa
    conditioned = inside and max(depth) <= conditioned_db
    ok = f_rel <= limit
    eta_db = None
    if a["eta_rad"] and b["eta_rad"]:
        near = [int(np.abs(np.asarray(b["far_f_hz"]) - fk).argmin()) for fk in a["far_f_hz"]]
        eta_db = float(max(abs(10 * np.log10(b["eta_rad"][j] / eta)) for j, eta in zip(near, a["eta_rad"])))
    return {"f_res": [fa, fb], "depth_db": depth, "f_rel": f_rel, "conditioned": conditioned, "ds11": ds11,
            "ds11_shift": ds11_shift, "pass": ok, "explained": not ok and not conditioned and ds11 <= ds11_shift,
            "d_db": None if None in (a["d_dbi"], b["d_dbi"]) else float(abs(b["d_dbi"] - a["d_dbi"])),
            "eta_db": eta_db, "fit": fit}


def fit_shift(a: dict, b: dict) -> tuple[float, float]:
    """The relative shift x in [−0.1, 0.1] that best maps the measure `a`'s S11 onto `b`'s over a's band [f_lo, f_hi]
    on the grid both share: the x that minimizes r(x), the largest |S_a(f·(1 + x)) − S_b(f)| there, S_a interpolated in
    its real and imaginary parts as pair's ds11_shift; (x, r(x)) as Python floats. S_b(f) ≈ S_a(f·(1 + x)) means b's
    response sits at a's frequencies divided by (1 + x), so b's resonance is a's / (1 + x)."""
    # ponytail: a brute-force scan of 20001 shifts; a bracketed minimizer if it ever shows in a report's time
    f, sa, sb = np.asarray(a["f_hz"]), np.asarray(a["s11"]), np.asarray(b["s11"])
    band = (f >= a["band"][0]) & (f <= a["band"][1])
    shifts = np.linspace(-0.1, 0.1, 20001)  # a step of 1e-5
    up = np.outer(1 + shifts, f[band])  # past the grid's end np.interp holds the last value, as in pair
    r = np.abs(np.interp(up, f, sa.real) + 1j * np.interp(up, f, sa.imag) - sb[band]).max(axis=1)
    k = int(r.argmin())
    return float(shifts[k]), float(r[k])


def fitted(a: dict, b: dict) -> dict:
    """fit_shift(a, b) as pair reports it: {"shift", "residual", "clean"}, clean when the shift lies inside the scan
    and the residual is at most a quarter of ds11, the largest |S_b − S_a| over a's band, itself above 0 (the
    controller's ruling at P3-C's CP3)."""
    x, r = fit_shift(a, b)
    f = np.asarray(a["f_hz"])
    ds11 = float(np.abs(np.asarray(b["s11"]) - np.asarray(a["s11"]))[(f >= a["band"][0]) & (f <= a["band"][1])].max())
    return {"shift": x, "residual": r, "clean": abs(x) < 0.1 and ds11 > 0 and r <= 0.25 * ds11}


def predicted_s(spec: dict, dt: float, t: float, pool: int, jobs: int, mcs: float) -> float:
    """The machine time in s that cost predicts for `jobs` jobs of the antenna model `spec` at the timestep `dt` (s) to
    the simulated time `t` (s), `pool` at once at the calibration's `mcs` MC/s a job, with gate P3-A's corrections:
    each PML node (cell_split) counts as runs.PML_WEIGHT cells, at runs.SMALL_SPEED × `mcs`."""
    cells = math.prod(len(spec["mesh"][a]) for a in "xyz")
    # mirrors the time() in pipeline.cost_notes for an antenna
    return p0.predicted_s(jobs, pool, cells + (runs.PML_WEIGHT - 1) * cell_split(spec)[2], dt, t,
                          mcs * runs.SMALL_SPEED)


def calibration() -> dict:
    """This machine's calibration as a gate reports it: its entry's aggregate_mcs, pool, threads, single and levels,
    each None without one, never the entry's key, which holds a host name."""
    entry = _entry() or {}
    return {key: entry.get(key) for key in ("aggregate_mcs", "pool", "threads", "single", "levels")}


# ponytail: no keep-awake call: this PC's sleep timeout is 0; a reboot loses the running step, which reruns
def run_steps(names: list[str], work: Callable[[str], object]) -> int:
    """p3a's loop over a gate's steps: for each of `names`, prints "p3: <name>" and calls `work(name)`; one that raises
    an Exception has its traceback printed and the loop goes on, while SystemExit (a STOP file) and KeyboardInterrupt
    end it. Returns 1 when one raised, else 0."""
    failed = []
    for name in names:
        print(f"p3: {name}", flush=True)
        try:
            work(name)
        except Exception:  # logged and skipped
            failed.append(name)
            traceback.print_exc()
    if failed:
        print(f"p3: failed steps: {', '.join(failed)}", flush=True)
    return 1 if failed else 0


def rows(out: Path) -> list[dict]:
    """The cost refit's rows (ruling 6), one per record in out/steps of a run or verify step (p3-…-run, p3-…-verify)
    that was not loaded, through measure: {"step", "pool", "cells", "f_pml" (split[2]/cells), "node_mcs" (the median
    of speeds_mcs), "cal_mcs"}, a row lacking any of them left out. A step id has one record, so a step two gates share
    counts once; free runs, the hand runs (in out/p3b, not steps) and other steps are none of them."""
    # ponytail: measure reads each project's antenna result too, unused here; a cost-only reader at hundreds of steps
    found = []
    for path in sorted((out / "steps").glob("p3-*.json")):
        name, _, command = path.stem.removeprefix("p3-").rpartition("-")
        if command not in ("run", "verify") or json.loads(path.read_text(encoding="utf-8"))["loaded"]:
            continue
        m = measure(out, name, command)
        row = {"step": path.stem, "pool": m["pool"], "cells": m["cells"],
               "f_pml": m["split"] and m["cells"] and m["split"][2] / m["cells"],
               "node_mcs": m["speeds_mcs"] and median(m["speeds_mcs"]), "cal_mcs": m["cal_mcs"]}
        if None not in row.values():
            found.append(row)
    return found


def _speed_ratio(row: dict, w: float) -> float:
    """A refit row's k at the PML weight `w`: node_mcs·(1 + (w − 1)·f_pml)/cal_mcs, its speed in cells, each PML node
    counted as w, over its calibration's per-job speed."""
    return row["node_mcs"] * (1 + (w - 1) * row["f_pml"]) / row["cal_mcs"]


def refit(rows: list[dict], w: float, like: tuple[dict, dict] | None = None, band: float = 0.25) -> dict:
    """The cost refit (Stage 3 design 5.9, ruling 6) of `rows` (rows()'s, "step" and "cells" unread) at the PML weight
    `w`: "w_fit" from `like`, the f_PML-0 row and its twin of one fixture, mesh n and copper at a pool of 1, by P3-A's
    method, 1 + (r − 1)/f, r = (node_0/cal_0)/(node_f/cal_f) and f the twin's f_pml, None without `like`; "w_line",
    1 + b/a of the least-squares line cal/node = a + b·f_pml through the pool-1 rows, a cross-check, None without two
    distinct f_pml among them; "moved", |w_fit − w| > `band`·w; "w", w_fit when moved, else `w`; "small", {pool: the
    median of its rows' k (_speed_ratio) at that w, to 3 significant digits}. Python floats and bools."""
    w_fit = None
    if like:
        zero, twin = like
        r = (zero["node_mcs"] / zero["cal_mcs"]) / (twin["node_mcs"] / twin["cal_mcs"])
        w_fit = 1 + (r - 1) / twin["f_pml"]
    single, w_line = [row for row in rows if row["pool"] == 1], None
    if len({row["f_pml"] for row in single}) > 1:
        b, a = np.polyfit([row["f_pml"] for row in single], [row["cal_mcs"] / row["node_mcs"] for row in single], 1)
        w_line = float(1 + b / a)
    moved = w_fit is not None and abs(w_fit - w) > band * w
    w = w_fit if moved else w
    small = {pool: float(f"{median(_speed_ratio(row, w) for row in rows if row['pool'] == pool):.3g}")
             for pool in sorted({row["pool"] for row in rows})}
    return {"small": small, "w_fit": w_fit, "w_line": w_line, "w": w, "moved": moved}


def refit_record(out: Path, like: tuple[str, str], extra: list[dict], dest: Path) -> dict:
    """The cost refit's record (ruling 6): refit of rows(out) followed by `extra` (rows of runs outside out/steps) at
    runs.PML_WEIGHT, w judged on the rows of the step ids `like` (the f_PML-0 run, then its twin) with the band
    refit_w_band of tests/fixtures/p3c/criteria.json. Writes <dest>.json through p0.save, {"rows", "like", "result",
    "before": runs.PML_WEIGHT and runs.SMALL_SPEED as they stood}, and <dest>.md: the rows with their k at the result's
    w, then the result, as p0.table's. KeyError for a step id of `like` with no row. Returns the JSON as saved."""
    every = rows(out) + extra
    by_step = {row["step"]: row for row in every}
    band = json.loads((p0.FIX / "p3c" / "criteria.json").read_text(encoding="utf-8"))["refit_w_band"]
    result = refit(every, runs.PML_WEIGHT, (by_step[like[0]], by_step[like[1]]), band)
    before = {"PML_WEIGHT": runs.PML_WEIGHT, "SMALL_SPEED": runs.SMALL_SPEED}
    data = p0.save(Path(f"{dest}.json"), {"rows": every, "like": list(like), "result": result, "before": before})
    w = result["w"]
    items = [*({"item": f"small, pool {pool}", "value": s} for pool, s in result["small"].items()),
             *({"item": key, "value": result[key]} for key in ("w_fit", "w_line", "w", "moved"))]
    Path(f"{dest}.md").write_text("\n\n".join([
        "# The cost refit (Stage 3 design 5.9)",
        f"Each row's k = node_mcs·(1 + (w − 1)·f_pml)/cal_mcs at w = {w:g}. w is judged on {like[0]} (f_PML 0) "
        f"against {like[1]} by P3-A's method and moves beyond {band:g}·w; the pool-1 line is a cross-check. Before: "
        f"PML_WEIGHT {before['PML_WEIGHT']}, SMALL_SPEED {before['SMALL_SPEED']}.",
        p0.table([{**row, "k": _speed_ratio(row, w)} for row in every],
                 ["step", "pool", "cells", "f_pml", "node_mcs", "cal_mcs", "k"]),
        p0.table(items, ["item", "value"])]) + "\n", encoding="utf-8")
    return data
