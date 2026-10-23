# SPDX-License-Identifier: GPL-3.0-or-later
"""P0-B, the lpf915 gate (spec 9.3; D-30, D-32..D-40). The runs, each a resumable p0.step: B1 to B6 through the
product's own commands on fresh projects (D-9: `run` of lpf915, `verify` of it, `run` of lpf915-45, at mesh.n 3 and at
mesh.reach_h 6), the empty-box runs A and B and the K_MAX sweep as harness models. Then, from the run folders: the
live "converged" evidence, the twin, the common-cut reach, the bias at n = 3, the C_p fit, the sweep, the growth and
dt statistics; the pre-registered rules (D-33..D-39, D-30's final part, D-44); p0b.json and p0b.md.

Dev-time only, like p0: the package never imports it. Run: python tools/p0b/harness.py [--out DIR]
[--only B1,B2,B3,B4,B5,B6,kmax] [--report]."""
import argparse
import copy
import json
import math
import re
import shutil
import sys
import traceback
from functools import partial
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.mesh.gates import fit2d
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.chain import terminate, with_box
from kicad_rf_studio.core.post.checks import compare
from kicad_rf_studio.core.post.waves import grid, layout
from kicad_rf_studio.core.project import BAND_FACTOR, HARMONICS, load_project, parts, save_project
from kicad_rf_studio.stoprule import KEPT, growth_rise

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/, for p0 when this runs as a script
import p0  # noqa: E402

NEW = ("--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "--lid-height", "2.5")  # D-32: 2.5 mm, as r1, r3 and r7
VARIANTS = {"B1": ("lpf915", {}), "B4": ("lpf915-45", {"allow_curve_port": True}),
            "B5": ("lpf915", {"mesh.n": 3, "gates.fit2d_limit": 0.05}), "B6": ("lpf915", {"mesh.reach_h": 6.0})}
K_SWEEP = (0.35, 0.40, 0.45, 0.48, 0.50, 0.55)  # D-39
# 185,000 steps at lpf915's 5.4e-14 s: r3 B-6 saw k 0.49 diverge only after about 52,700 steps; about 18.5 min a
# value, 1.9 h in all, inside D-39's 2 h
KMAX_T_MAX = 10e-9
REACH = {"ds21_db_f0": 0.033, "ds11_f0": 0.0067, "ds_max": 0.01}  # a third of criterion 1 (D-37)
GROWTH_LIMIT_DB = 10.0  # D-38
EMPTY = {"A": ("C1", "L1"), "B": ("C2", "C3")}  # the boxes each empty-box run empties (D-35, r7 §3.5)
F0 = 915e6  # NEW's f0
FLOOR = 0.02  # the null floor of the harness's comparisons (r7 §3.4)
RUNS = ("B1", "B2", "B3", "B4", "B5", "B6", "kmax")  # --only's names, in the order main runs them
KMAX_STEPS = {k: f"p0b-kmax-{k:.2f}" for k in K_SWEEP}
STEPS = ("p0b-B1", "p0b-B2", "p0b-B3-A", "p0b-B3-B", "p0b-B4", "p0b-B5", "p0b-B6", *KMAX_STEPS.values())
AFTER_B1 = ("p0b-B2", "p0b-B3-A", "p0b-B3-B", *KMAX_STEPS.values())  # the steps keyed by B1's run as well
# D-43's preconditions, as emerge_app words its reasons
PRECONDITION = re.compile(r"\S+ (z0|eeff) \S+ %|(chain moved|sigma_max|reciprocity) .+")
UNSOLVED = re.compile(r"EMerge .+ not solved")  # a missing FEM output (PF-26)


def _read(path: Path):
    """The JSON at `path`."""
    return json.loads(path.read_text(encoding="utf-8"))


def _path(out: Path, run: str) -> Path:
    """The project.json of the run `run` (VARIANTS) in the P0 folder `out`."""
    return out / "p0b" / "projects" / run / "project.json"


def project(out: Path, run_id: str) -> Path:
    """The project of the run `run_id` (VARIANTS), <out>/p0b/projects/<run_id>/project.json (D-32, D-9): made by `new`
    with NEW from its board copied into <out>/boards when it is missing (RuntimeError on a non-zero exit; new writes
    project.json only once every refusal check passed); then VARIANTS' edits through p0.edit on every call, saved only
    when they change it, so an interruption between `new` and the edits never leaves a wrong project behind."""
    board, edits = VARIANTS[run_id]
    pj = _path(out, run_id)
    if not pj.is_file():
        (out / "boards").mkdir(parents=True, exist_ok=True)
        board_copy = shutil.copy2(p0.FIX / f"{board}.kicad_pcb", out / "boards")
        code, text = p0.cli("new", str(board_copy), *NEW, "-o", str(pj.parent))
        if code:
            raise RuntimeError(f"p0b: new exited {code}: {(text.strip().splitlines() or [''])[-1]}")
    data = load_project(pj)
    edited = p0.edit(copy.deepcopy(data), edits)
    if edited != data:
        save_project(pj, edited)
    return pj


def _traces(run_dir: str, jobs: list[dict]) -> list[tuple]:
    """p0.s_of's traces of `jobs` (each with "port" and "t_cut") in the run folder named `run_dir`: each job's records
    from its folder job-<k>-<port>, k its port's number in model.json, then its port's row, the excitation and its
    t_cut."""
    folder = p0.run_path(run_dir)
    spec, dt = _read(folder / "model.json"), _read(folder / "job-0-setup" / "setup.json")["dt"]
    names = [q["name"] for q in spec["ports"]]
    rows = [names.index(job["port"]) for job in jobs]
    return [(pipeline.records(runs.job_dir(folder, k + 1, names[k]), len(names), dt), k, spec["excitation"],
             job["t_cut"]) for k, job in zip(rows, jobs)]


def evidence(record: dict) -> dict:
    """The live "converged" evidence of the CLI run of the step `record` (D-40), from its run folder: per job
    (p0.summary's), "event" (an I_JOB_CONVERGED verdict event for it), "abort" (an ABORT file in its folder), "order"
    (t_cut < t_stop < the spec's t_max) and "ok" (all three); "cut_delta", the largest |S of the jobs cut at t_cut − S
    of their whole records| on the grid, evidence of the stop latency only; "trunc_2ns", the largest |S cut at t_cut −
    S cut 2 ns earlier|, a truncation estimate (both None unless every job kept S); "ok", every job ok and cut_delta ≤
    2e-3. Event params are never copied: I_JOB_CONVERGED's carry an absolute log path."""
    res = record["result"]
    folder, jobs = p0.run_path(res["run_dir"]), p0.summary(record)["jobs"]
    traces = _traces(res["run_dir"], jobs)
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    converged = {e["job"] for e in events if e["kind"] == "verdict" and e["code"] == "I_JOB_CONVERGED"}
    rows = []
    for (_, k, exc, t_cut), job in zip(traces, jobs):
        flags = {"event": k + 1 in converged, "abort": (runs.job_dir(folder, k + 1, job["port"]) / "ABORT").is_file(),
                 "order": None not in (t_cut, job["t_stop"]) and t_cut < job["t_stop"] < exc["t_max"]}
        rows.append({"port": job["port"], **flags, "ok": all(flags.values())})
    cut_delta = trunc = None
    if all(job["verdict"] in KEPT for job in jobs):
        f = grid(F0, HARMONICS, BAND_FACTOR)[0]
        cut = p0.s_of(traces, f)[0]
        whole = p0.s_of([(rec, k, exc, None) for rec, k, exc, _ in traces], f)[0]
        earlier = p0.s_of([(rec, k, exc, (job["t_stop"] if t is None else t) - 2e-9)
                           for (rec, k, exc, t), job in zip(traces, jobs)], f)[0]
        cut_delta, trunc = float(np.abs(cut - whole).max()), float(np.abs(cut - earlier).max())
    return {"jobs": rows, "cut_delta": cut_delta, "trunc_2ns": trunc,
            "ok": all(row["ok"] for row in rows) and cut_delta is not None and cut_delta <= 2e-3}


def _closures(f: np.ndarray, c: dict, refs: list[str], emptied) -> np.ndarray:
    """The loads (F, M) of the part ports `refs` in an empty-box run: 1/(jωC) at a box it empties (`emptied`),
    50 Ω ∥ C (with_box) at a passive one, C = c[ref] (F)."""
    w = 2 * np.pi * f
    return np.stack([1 / (1j * w * c[r]) if r in emptied else with_box(50.0, f, c[r]) for r in refs], -1)


def fit_cp(s: np.ndarray, f: np.ndarray, c_box: dict, refs: list[str], measured: dict[str, np.ndarray],
           empty: dict[str, list[str]]) -> tuple[dict[str, float], float]:
    """C_p (F) of each part box `refs` of the layout N-port `s` (F, N, N; ports 0 and 1 external, then refs in order)
    on `f` (D-35, r7 §3.5): least squares over both runs of `measured` (run: its 2-port), every f and entry, real and
    imaginary parts, of terminate(s, [0, 1], C_p's loads) against it, a box the run empties (empty[run]) closed by
    1/(jωC_p) and a passive one by 50 Ω ∥ C_p; in fF, from `c_box` (F, by ref). Returns the C_p by ref and the
    condition number of the fit's Jacobian at the solution (above 1e3 the report states a C_p as not identified)."""
    def residual(x: np.ndarray) -> np.ndarray:
        c = dict(zip(refs, x * 1e-15))
        r = np.concatenate([(terminate(s, [0, 1], _closures(f, c, refs, empty[run]), f) - measured[run]).ravel()
                            for run in measured])
        return np.concatenate([r.real, r.imag])

    fit = least_squares(residual, np.array([c_box[r] for r in refs]) * 1e15)
    return dict(zip(refs, (fit.x * 1e-15).tolist())), float(np.linalg.cond(fit.jac))


def empty_box(out: Path) -> dict:
    """The empty-box report (D-35, r7 §3.5), from the records of p0b-B1, p0b-B3-A and p0b-B3-B (p0.records: SystemExit
    when one is missing, so it never starts a run, PF-30). B1's layout S and C_box (its project's results), and per
    run (EMPTY): the FDTD 2-port, p0.s_of of its jobs' records cut at their own t_cut on rows 0 and 1, against the
    co-simulation terminate(B1's S, [0, 1]) closed by 1/(jωC_box) at an emptied box and 50 Ω ∥ C_box at a passive
    one: {"ds_max", "ds11_f0", "ds21_f0"}, complex |ΔS| (in run A, S21 ≈ 0). Then fit_cp on both runs, and B2's
    comparison redone, verify's own 2-port against the ideal-value chain closed by C_box and by C_p ("verify_ds_max",
    None for C_p when one is not above 0). Report only (D-35)."""
    _, a, b = p0.records(out, ["p0b-B1", "p0b-B3-A", "p0b-B3-B"])
    pj = _path(out, "B1")
    data = load_project(pj)
    results = data["results"]
    lay = layout(data, results)
    refs, c_box, k0 = [q["name"] for q in lay.ports if q["part"]], results["c_box"], lay.markers[0]
    measured, report = {}, {}
    for (run, emptied), rec in zip(EMPTY.items(), (a, b)):
        res = rec["result"]
        measured[run] = p0.s_of(_traces(res["run_dir"], res["jobs"]), lay.f, rows=[0, 1])[0]
        d = np.abs(measured[run] - terminate(lay.s, [0, 1], _closures(lay.f, c_box, refs, emptied), lay.f))
        report[run] = {"ds_max": float(d.max()), "ds11_f0": float(d[k0, 0, 0]), "ds21_f0": float(d[k0, 1, 0])}
    c_p, cond = fit_cp(lay.s, lay.f, c_box, refs, measured, EMPTY)
    verify = p0.closed_chain(pj, key="verify")[1]

    def ds_max(cbox: dict | None) -> float:
        return float(np.abs(p0.closed_chain(pj, ideal=True, cbox=cbox)[1] - verify).max())

    return {**report, "c_box": {r: c_box[r] for r in refs}, "c_p": c_p,
            "dc_ff": {r: (c_p[r] - c_box[r]) * 1e15 for r in refs}, "cond": cond,
            "verify_ds_max": {"c_box": ds_max(None),
                              "c_p": ds_max(c_p) if all(0 < v < math.inf for v in c_p.values()) else None}}


def kmax_values(dt: float, c_cell: float) -> list[tuple[float, float]]:
    """(k, L) for each k of K_SWEEP: L = (dt/(2k))²/c_cell (H), so that k = dt/(2·√(L·C)) (C-37) on a cell of
    capacitance c_cell (F) at the timestep dt (s)."""
    return [(k, (dt / (2 * k)) ** 2 / c_cell) for k in K_SWEEP]


def _b1_run(out: Path) -> str:
    """The name of B1's run folder, from its step record; SystemExit when B1 has none yet."""
    return p0.records(out, ["p0b-B1"])[0]["result"]["run_dir"]


def kmax_sweep(out: Path) -> None:
    """The K_MAX sweep (D-39): B1's model rebuilt from its project, SystemExit unless its hash is its results'; the L1
    cell's C read from verify_spec's grid entry at the as-built values; then per k of K_SWEEP the step p0b-kmax-<k>:
    verify's model with L1 at kmax_values' L, built with spec.K_MAX lifted to 1.0, run on P1 alone at Strict to
    KMAX_T_MAX, keyed by its spec_hash and B1's run. Strict, because its −70 dB level cannot stop lpf915 before about
    18 ns (r4 §2.5), so every value runs its 10 ns unless it grows."""
    run, pj = _b1_run(out), project(out, "B1")
    data, board, geom, _ = pipeline.load(pj)
    spec, results = pipeline.build_model(data, board, geom).spec, data["results"]
    if spec is None or spec_hash(spec) != results["model_hash"]:
        raise SystemExit("p0b: B1's project no longer builds the model of its results; run B1 again")
    by_ref, dt = parts(data), results["dt"]
    dump = runs.job_dir(p0.run_path(run), 0, "setup") / "operator_dump.vtr"
    built = spec_module.verify_spec(spec, by_ref, results["c_box"], dump, dt)
    for k, inductance in kmax_values(dt, next(g["C"] for g in built["grid"] if g["name"] == "L1")):
        swept = {**by_ref, "L1": {**by_ref["L1"], "value": f"{inductance * 1e12:.6g}pH"}}
        # ponytail: patches the module's K_MAX for this process while verify_spec builds the sweep's spec
        k_max, spec_module.K_MAX = spec_module.K_MAX, 1.0
        try:
            vspec = spec_module.verify_spec(spec, swept, results["c_box"], dump, dt)
        finally:
            spec_module.K_MAX = k_max
        sid = KMAX_STEPS[k]
        p0.step(out, sid, f"{spec_hash(vspec)}|{run}",
                partial(p0.run_model, p0.model_of(vspec), "strict", sid, [1], t_max=KMAX_T_MAX))


def _fit2d(pj: Path) -> list[dict]:
    """fit2d of each section of the model the project `pj` builds: {"net", "width_mm", "pct"}, pct 100·(z0_mesh/z0_ref
    − 1)."""
    data, board, geom, _ = pipeline.load(pj)
    mesh = pipeline.build_model(data, board, geom).mesh
    return [{"net": fit.section.net, "width_mm": fit.section.width, "pct": 100 * (fit.z0_mesh / fit.z0_ref - 1)}
            for fit in fit2d(geom, mesh)]


def measure(out: Path) -> dict:
    """The P0-B measurements of the P0 folder `out`, from its step records (p0.records: every step, one code), the
    projects, the run folders and <out>/p0a/p0a.json (SystemExit without it). SystemExit, too, when a project does not
    hold its step's run, or a step keyed by B1's run ran on another one. {"runs": p0.summary of B1, B2, B4, B5 and B6;
    "evidence" of B1, B2 and B4; "consistency": B2's stored verify.compare; "tx" (D-34): B1's chain against B4's, each
    as p0.closed_chain writes it, and "tx_ideal" at the ideal values (r7 §3.4); "reach" (D-37): B6 against B1, each job
    cut at the earlier of their t_cuts (whole only when both are None), so the tail both share cancels, and
    "reach_stored" as each run cut itself; "bias" (D-36): fit2d per section of B1's and B5's models, B5 against B1 as
    stored and at common cuts, |S21| in dB at f0, 2f0 and 3f0 ([n2, n3]) and the lid at each n; "empty_box"; "kmax":
    each sweep value's k, L, verdict, end time (t_cut, else t_stop) and growth; "verdicts": the job verdicts of B1, B2,
    B3 (A and B), B4, B5, B6 and "p0a" (its rows that hold one, PF-27, and the pad's jobs); "growth_db": the rise of
    each of those jobs; "dt_ratios": P0-A's smallest and each CLI run's dt / dt_ref; "stray": P0-A's; "emerge":
    <out>/p0b/emerge.json, or None}."""
    path = out / "p0a" / "p0a.json"
    if not path.is_file():
        raise SystemExit(f"p0b: no {path}; run P0-A first")
    p0a = _read(path)
    recs = dict(zip(STEPS, p0.records(out, list(STEPS))))
    pj = {run: _path(out, run) for run in VARIANTS}
    projects = {run: load_project(p) for run, p in pj.items()}
    held = {"p0b-B2": projects["B1"].get("verify", {}),
            **{f"p0b-{run}": data.get("results", {}) for run, data in projects.items()}}
    b1_run = recs["p0b-B1"]["result"]["run_dir"]
    stale = [sid for sid, held_run in held.items()
             if Path(held_run.get("run_dir", "")).name != recs[sid]["result"]["run_dir"]]
    stale += [sid for sid in AFTER_B1 if f"|{b1_run}@" not in recs[sid]["key"]]
    if stale:
        raise SystemExit(f"p0b: {', '.join(stale)}: the project holds another run, or B1 ran again since; run the "
                         "harness again")
    summaries = {run: p0.summary(recs[f"p0b-{run}"]) for run in ("B1", "B2", "B4", "B5", "B6")}

    def closed(run: str, **kw) -> np.ndarray:
        return p0.closed_chain(pj[run], **kw)[1]

    def common(run: str) -> list[float | None]:
        """Each job's common cut of B1 and `run`: the earlier t_cut, None only when both are None."""
        pairs = zip(projects["B1"]["results"]["jobs"], projects[run]["results"]["jobs"], strict=True)
        return [min((t for t in (a["t_cut"], b["t_cut"]) if t is not None), default=None) for a, b in pairs]

    f, b1, k0 = p0.closed_chain(pj["B1"])
    stored, cuts = {run: closed(run) for run in ("B4", "B5", "B6")}, {run: common(run) for run in ("B5", "B6")}
    marks = {"f0": k0, "2f0": int(np.abs(f - 2 * F0).argmin()), "3f0": int(np.abs(f - 3 * F0).argmin())}
    b3 = [_traces(recs[sid]["result"]["run_dir"], recs[sid]["result"]["jobs"]) for sid in ("p0b-B3-A", "p0b-B3-B")]
    kmax = []
    for k, sid in KMAX_STEPS.items():
        res = recs[sid]["result"]
        (job,), ((rec, _, exc, _),) = res["jobs"], _traces(res["run_dir"], res["jobs"])
        end = job["t_stop"] if job["t_cut"] is None else job["t_cut"]
        kmax.append({"k": k, "l_h": next(g["L"] for g in _read(p0.run_path(res["run_dir"]) / "model.json")["grid"]
                                          if g["name"] == "L1"),
                     "verdict": job["verdict"], "t_ns": None if end is None else end * 1e9,
                     "growth_db": growth_rise(rec, exc["t0"])})
    p0a_jobs = [row for row in p0a["rows"] if "verdict" in row] + p0a["pad"]["jobs"]  # PF-27: a lint row had no job
    verdicts = {run: [job["verdict"] for job in s["jobs"]] for run, s in summaries.items()}
    emerge = out / "p0b" / "emerge.json"
    return {
        "runs": summaries, "evidence": {run: evidence(recs[f"p0b-{run}"]) for run in ("B1", "B2", "B4")},
        "consistency": projects["B1"]["verify"]["compare"],
        "tx": compare(b1, stored["B4"], f, k0, FLOOR),
        "tx_ideal": compare(closed("B1", ideal=True), closed("B4", ideal=True), f, k0, FLOOR),
        "reach": compare(closed("B1", cuts=cuts["B6"]), closed("B6", cuts=cuts["B6"]), f, k0, FLOOR),
        "reach_stored": compare(b1, stored["B6"], f, k0, FLOOR),
        "bias": {"fit2d_n2": _fit2d(pj["B1"]), "fit2d_n3": _fit2d(pj["B5"]),
                 "compare": compare(b1, stored["B5"], f, k0, FLOOR),
                 "compare_common": compare(closed("B1", cuts=cuts["B5"]), closed("B5", cuts=cuts["B5"]), f, k0, FLOOR),
                 "s21_db": {name: [float(20 * np.log10(abs(s[k, 1, 0]))) for s in (b1, stored["B5"])]
                            for name, k in marks.items()},
                 "lid_mm": {"n2": summaries["B1"]["lid_mm"], "n3": summaries["B5"]["lid_mm"]}},
        "empty_box": empty_box(out), "kmax": kmax,
        "verdicts": {"B1": verdicts["B1"], "B2": verdicts["B2"],
                     "B3": [job["verdict"] for sid in ("p0b-B3-A", "p0b-B3-B") for job in recs[sid]["result"]["jobs"]],
                     "B4": verdicts["B4"], "B5": verdicts["B5"], "B6": verdicts["B6"],
                     "p0a": [job["verdict"] for job in p0a_jobs]},
        "growth_db": [job["growth_db"] for s in summaries.values() for job in s["jobs"]]
        + [growth_rise(rec, exc["t0"]) for traces in b3 for rec, _, exc, _ in traces]
        + [job["growth_db"] for job in p0a_jobs],
        "dt_ratios": {"p0a_min": p0a["decisions"]["dt_floor"]["min_ratio"],
                      **{run: s["dt_ratio"] for run, s in summaries.items()}},
        "stray": p0a["stray"], "emerge": _read(emerge) if emerge.is_file() else None}


def decide(m: dict) -> dict:
    """The P0-B rules on the measurements `m` (measure's), pure (D-30, D-33..D-39, D-44; O-11). "consistency":
    criterion 1 and both B2 jobs converged; "tx" (D-34): criterion 1 and the 12 B1 and B4 jobs converged; "reach"
    (D-37); "growth" (D-38): a sweep value is unstable when it ended growth or diverged, or t_max still rising by
    GROWTH_LIMIT_DB, and the sweep caught when one is and every one ended growth or diverged; "kmax" (D-39): a value
    is stable when its verdict kept S and it is not unstable; "dt_floor" (D-30, final). "verdict" (D-33, D-44, PF-26,
    PF-31): "fail" on any failed FDTD-internal criterion (consistency, every B1, B2 and B4 job converged) or EMerge's
    failure; else "pending" without emerge.json or with an EMerge level not solved; else "pass" when EMerge passed, or
    was inconclusive for D-43's preconditions only ("emerge_accepted"). The twin never decides it (O-11)."""
    v, emerge = m["verdicts"], m["emerge"]
    consistency = {**p0.criterion1(m["consistency"]), "verify_converged": v["B2"] == ["converged"] * 2}
    twelve, tx = v["B1"] + v["B4"] == ["converged"] * 12, p0.criterion1(m["tx"])

    def unstable(s: dict) -> bool:
        return s["verdict"] in ("growth", "diverged") or s["verdict"] == "t_max" and s["growth_db"] >= GROWTH_LIMIT_DB

    shaky = [s for s in m["kmax"] if unstable(s)]
    caught = bool(shaky) and all(s["verdict"] in ("growth", "diverged") for s in shaky)
    max_db, healthy = max(m["growth_db"], default=0.0), [run for run, kinds in v.items() if "growth" in kinds]
    stable = [s["k"] for s in m["kmax"] if s["verdict"] in KEPT and not unstable(s)]
    lowest = min((s["k"] for s in m["kmax"] if s["k"] not in stable), default=math.inf)
    ratios = [r for r in m["dt_ratios"].values() if r is not None]
    low, stray = min(ratios, default=None), m["stray"]
    fails = [] if consistency["pass"] else ["consistency: the co-simulation against verify fails criterion 1 (D-33)"]
    fails += [f"{run}: its jobs ended {', '.join(v[run]) or 'nothing'}, not every one converged (D-33)"
              for run, n in (("B1", 6), ("B2", 2), ("B4", 6)) if v[run] != ["converged"] * n]
    reasons = emerge["reasons"] if emerge else []
    unsolved = emerge is None or any(UNSOLVED.fullmatch(r) for r in reasons)
    accepted = (not fails and not unsolved and emerge["verdict"] == "inconclusive"
                and all(PRECONDITION.fullmatch(r) for r in reasons))  # D-44
    if not unsolved and emerge["verdict"] != "pass" and not accepted:
        fails.append(f"EMerge: {emerge['verdict']}" + "".join(f"; {r}" for r in reasons) + " (D-33, D-44)")
    return {"consistency": consistency, "tx": {**tx, "all_converged": twelve, "pass": tx["pass"] and twelve},
            "reach": {"confirmed": all(m["reach"][key] <= limit for key, limit in REACH.items())},
            "growth": {"max_db": max_db, "healthy_growth": healthy, "sweep_caught": caught,
                       "confirmed": max_db <= GROWTH_LIMIT_DB and not healthy and caught},
            "kmax": {"stable_through": max((k for k in stable if k < lowest), default=None),
                     "confirmed": lowest > 0.48,  # D-39: stable through k = 0.48, so K_MAX stays 0.45
                     "k_max": 0.45 if lowest > 0.48 else 0.9 * lowest},
            "dt_floor": {"rule": "D-30", "min_ratio": low, "stray_ratio": stray["dt_ratio"],
                         "stray_trips": stray["trips"],
                         "confirmed": low is not None and low >= 0.85 and stray["trips"]},  # dt/dt_ref ≥ 0.85
            "verdict": {"value": "fail" if fails else "pending" if unsolved else "pass", "fails": fails,
                        "emerge_accepted": accepted}}


def _cell(v) -> str:
    """`v` as the P0-B tables show it: None and an empty list as "–", a float as :.4g, a list's items and a dict's
    "key value" pairs joined by ", "."""
    if isinstance(v, dict):
        return ", ".join(f"{key} {_cell(x)}" for key, x in v.items())
    if isinstance(v, list):
        return ", ".join(map(_cell, v)) or "–"
    return "–" if v is None else f"{v:.4g}" if isinstance(v, float) else str(v)


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), with p0.table: B-runs (the runs, their jobs with B1's,
    B2's and B4's evidence, the evidence's S checks, every run's verdicts), B-consistency, B-twin, B-Cbox, B-n,
    B-EMerge, B-constants (reach, the K_MAX sweep, the dt ratios and the stray cell) and the decisions."""
    def table(title: str, items: list[dict]) -> str:
        cols = list(dict.fromkeys(key for item in items for key in item))
        return f"## {title}\n\n" + p0.table([{col: _cell(item.get(col)) for col in cols} for item in items], cols)

    def rows(limits: dict, **cmps: dict) -> list[dict]:
        """checks.compare results `cmps` by name, after a row of their `limits`."""
        return [{"vs": "limit", **limits}] + [
            {"vs": name, **{key: c[key] for key in limits}, "nulls": c["nulls"] or "n/a"} for name, c in cmps.items()]

    ev, box, bias, emerge = result["evidence"], result["empty_box"], result["bias"], result["emerge"]
    limits1 = {key: p0.LIMITS1[key] for key in ("ds21_db_f0", "ds11_f0", "ds_max")}
    marked = {(run, e["port"]): e for run, x in ev.items() for e in x["jobs"]}
    blocks = [table("B-runs", [{"run": run, **{k: x for k, x in s.items() if k != "jobs"}}
                               for run, s in result["runs"].items()]),
              table("B-runs jobs", [{"run": run, **job, **marked.get((run, job["port"]), {})}
                                    for run, s in result["runs"].items() for job in s["jobs"]]),
              table("B-runs evidence", [{"run": run, **{k: x[k] for k in ("cut_delta", "trunc_2ns", "ok")}}
                                        for run, x in ev.items()]),
              table("B-runs verdicts", [{"run": run, "verdicts": kinds} for run, kinds in result["verdicts"].items()]),
              table("B-consistency", rows(limits1, verify=result["consistency"])),
              table("B-twin", rows(limits1, twin=result["tx"], twin_ideal=result["tx_ideal"])),
              table("B-Cbox", [{"box": r, "c_box_ff": box["c_box"][r] * 1e15, "c_p_ff": box["c_p"][r] * 1e15,
                                "dc_ff": box["dc_ff"][r]} for r in box["c_box"]]
                    + [{"box": f"run {run}", **box[run]} for run in EMPTY]
                    + [{"box": "fit", "cond": box["cond"], "verify_ds_max": box["verify_ds_max"]}]),
              table("B-n", [{"net": a["net"], "width_mm": a["width_mm"], "fit2d_n2_pct": a["pct"],
                             "fit2d_n3_pct": b["pct"]} for a, b in zip(bias["fit2d_n2"], bias["fit2d_n3"])]
                    + [{"net": f"S21 dB at {at}", "n2": n2, "n3": n3} for at, (n2, n3) in bias["s21_db"].items()]
                    + [{"net": "lid mm", **bias["lid_mm"]}]),
              table("B-n chains", rows(limits1, stored=bias["compare"], common_cuts=bias["compare_common"])),
              "## B-EMerge\n\npending: no emerge.json yet" if emerge is None else
              table("B-EMerge", [{"verdict": emerge["verdict"], "reasons": emerge["reasons"]}]
                    + [{"compare": name, **c} for name, c in emerge.items() if name.startswith("compare") and c]
                    + emerge.get("coupons", [])),
              table("B-constants reach", rows(REACH, common_cuts=result["reach"], stored=result["reach_stored"])),
              table("B-constants K_MAX", result["kmax"]),
              table("B-constants dt", [{"run": run, "dt_ratio": r} for run, r in result["dt_ratios"].items()]
                    + [{"run": "stray", **result["stray"]}]),
              table("Decisions", [{"decision": name, "result": d} for name, d in result["decisions"].items()])]
    return "\n\n".join(blocks) + "\n"


def write(out: Path) -> dict:
    """measure, decide and tables of the P0 folder `out`: <out>/p0b/p0b.json through p0.save, whose "calibration" is
    the value of this machine's settings entry, never its key, which holds a host name (PF-29), and whose "machine"
    counts every P0-B step and the EMerge steps that exist; p0b.md beside it. Returns the JSON as saved."""
    m = measure(out)
    fem = sorted(path.stem for path in (out / "steps").glob("p0b-emerge-*.json"))
    result = p0.save(out / "p0b" / "p0b.json", {
        "gate": "P0-B", "versions": p0.versions(),
        "calibration": runs.load_settings().get("machines", {}).get(runs.machine_key()), **m,
        "decisions": decide(m), "machine": p0.machine(p0.records(out, [*STEPS, *fem]))})
    (out / "p0b" / "p0b.md").write_text(tables(result), encoding="utf-8")
    return result


def _run(out: Path, name: str) -> None:
    """The steps of `name` (RUNS), each through p0.step (D-6). B1, B4, B5 and B6 `run` their projects, keyed by
    p0.model_key; B2 `verify`s B1's, keyed by that plus B1's run, and B3 (PF-30) and the sweep are keyed by their own
    model's hash plus B1's run, so they all run again when B1 does. B3's runs A and B are B1's model.json less the
    ports EMPTY names (same mesh and materials), P1 and P2 excited."""
    if name == "kmax":
        return kmax_sweep(out)
    if name == "B3":
        run = _b1_run(out)
        spec = _read(p0.run_path(run) / "model.json")
        for variant, emptied in EMPTY.items():
            sid, vspec = f"p0b-B3-{variant}", {**spec, "ports": [q for q in spec["ports"] if q["name"] not in emptied]}
            p0.step(out, sid, f"{spec_hash(vspec)}|{run}",
                    partial(p0.run_model, p0.model_of(vspec), "normal", sid, [1, 2]))
        return None
    pj = project(out, "B1" if name == "B2" else name)
    key = p0.model_key(pj) + (f"|{_b1_run(out)}" if name == "B2" else "")
    p0.step(out, f"p0b-{name}", key, partial(p0.cli_run, pj, "verify" if name == "B2" else "run"))
    return None


def main(argv: list[str] | None = None) -> int:
    """python tools/p0b/harness.py [--out DIR] [--only B1,B2,B3,B4,B5,B6,kmax] [--report] (D-5, D-6): enters the P0
    folder first, then runs the steps of each of RUNS (or of --only), printing a step that raises and going on with the
    next, then writes the gate when every P0-B step has its record and none raised; --report writes from the records
    and starts no run. Returns 1 when a step raised, else 0."""
    parser = argparse.ArgumentParser(prog="p0b", description="P0-B, the lpf915 gate (spec 9.3).")
    parser.add_argument("--out", help="the P0 folder (default: kicad-rf-studio-p0 beside the per-user data folder)")
    parser.add_argument("--only", help=f"the runs to run, comma-separated, among {','.join(RUNS)}")
    parser.add_argument("--report", action="store_true", help="write p0b.json and p0b.md from the records only")
    a = parser.parse_args(argv)
    only = a.only.split(",") if a.only else RUNS
    if unknown := sorted(set(only) - set(RUNS)):
        parser.error(f"unknown run: {', '.join(unknown)}")
    out = p0.enter(Path(a.out) if a.out else p0.default_out())  # PF-32
    if a.report:
        write(out)
        return 0
    failed = []
    for name in [run for run in RUNS if run in only]:
        print(f"p0b: {name}", flush=True)
        try:
            _run(out, name)
        except Exception:  # logged and skipped; SystemExit (STOP) and KeyboardInterrupt end the harness
            failed.append(name)
            traceback.print_exc()
    if failed:
        print(f"p0b: failed: {', '.join(failed)}", flush=True)
        return 1
    if all((out / "steps" / f"{sid}.json").is_file() for sid in STEPS):
        write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
