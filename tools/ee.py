# SPDX-License-Identifier: GPL-3.0-or-later
"""Gate E-E's openEMS confirmation (Stage 5 design 5.12), the controller's: a hand-written spec as p3a's, one run
through p0, Re Z_in's peaks against the eigen-solve on the Δ-buffered outline, frozen in
tests/fixtures/ee/references.json before the run. Run: python tools/ee.py --references | --out DIR [--cost]."""
import argparse
import hashlib
import json
import math
import sys
import traceback
from collections.abc import Iterable
from functools import partial
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks
from shapely.geometry import box

import p0
from kicad_rf_studio import runs
from kicad_rf_studio.core import cavity
from kicad_rf_studio.core.geometry.region import C0
from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines
from kicad_rf_studio.core.model.spec import dc_pulse, spec_hash, with_pml
from kicad_rf_studio.core.post import waves
from kicad_rf_studio.stoprule import KEPT, RING_CEILING, WINDOW_S

A_MM, B_MM, D_MM, EPS_R = 50.0, 30.0, 0.8, 4.4  # the plane pair, lossless (design 5.12)
FINE_MM, CELL_IN_MM, RATIO = 0.2, 0.5, 1.3  # the cells at the plate edges and the port, over the plates, the grading
PORT = (round(2 + FINE_MM / 3, 6),) * 2  # mm: the port's x and y, 2.066667, on the thirds grid
SLAB_MM = 5.0  # the laminate's margin past the plates
F_MAX = 6.5e9
# the architect's estimate: one corner port loads a Q of about 20 at f10, twice f1's two-port Q_L of 10.2, which gives
# about 25 ns to −60 dB; the ring rule may run on to RING_CEILING·T_MAX
T_MAX = 30e-9
AIR_MM, CMAX_MM = 15.0, C0 / F_MAX * 1e3 / 20  # the air from the plates to the PML, and its largest cell, λ/20
PRESET = "normal"
STEP = "ee-cavity"
F_GRID = np.arange(1e9, 6.5e9 + 1, 1e6)  # Hz: Re Z_in's grid
DELTA_MM = 0.412 * D_MM * (EPS_R + 0.3) / (EPS_R - 0.258)  # Hammerstad's Δ at W/d → ∞ (design 5.12)
TOL, PROMINENCE_DB, MIN_PEAK, NODAL = 0.02, 3.0, 0.01, 0.1  # the decision (design 5.12; AR-7)
REFERENCES = p0.FIX / "ee" / "references.json"  # written once by --references, committed before any run


def _air(lines: Iterable[float], lo: float, hi: float) -> list[float]:
    """`lines` (mm) graded at RATIO up to CMAX_MM out to `lo` and `hi`, then with_pml, on the 1e-6 mm grid."""
    return with_pml([round(float(v), 6) for v in smooth_mesh_lines(np.array([*lines, lo, hi]), CMAX_MM, RATIO)])


def _xy(lo: float, hi: float) -> list[float]:
    """An in-plane axis of plates from `lo` to `hi` mm: each edge e's window of FINE_MM lines, round(e + s·(FINE_MM/3 +
    k·FINE_MM), 6), s +1 at the low edge with k over range(−5, 15), so that the port's line is in it, and −1 at the high
    one with k over range(−5, 5). Each edge so sits a third of a cell from its inside line and two thirds from its
    outside one, with no line on it (the edge lint). Then the laminate's edges SLAB_MM past the plates, CELL_IN_MM
    cells graded at RATIO between them, and the air to AIR_MM past the plates (_air)."""
    fixed = [round(e + s * (FINE_MM / 3 + k * FINE_MM), 6)
             for e, s, ks in ((lo, 1, range(-5, 15)), (hi, -1, range(-5, 5))) for k in ks]
    board = smooth_mesh_lines(np.array([*fixed, lo - SLAB_MM, hi + SLAB_MM]), CELL_IN_MM, RATIO)
    return _air(board, lo - AIR_MM, hi + AIR_MM)


def spec() -> dict:
    """E-E's run (design 5.12) as a full model spec, as runs.calibration_spec is: two sheet plates of A_MM × B_MM, D_MM
    apart, on a laminate of EPS_R, lossless, that runs SLAB_MM past the plates, as on a PCB pair, which is Hammerstad's
    Δ's assumption (AR-11); in air under PML_8, AIR_MM off the plates; SI's DC pulse to F_MAX and T_MAX; one lumped
    port P1 between the plates at PORT. The mesh: _xy in x and y; in z, 0.2 mm lines from −1 to 1.8 mm, the plates'
    faces among them (exempt from the edge lint), graded out to ±AIR_MM."""
    plate = {"x": [0.0, A_MM, A_MM, 0.0], "y": [0.0, 0.0, B_MM, B_MM]}
    x0, y0, x1, y1 = -SLAB_MM, -SLAB_MM, A_MM + SLAB_MM, B_MM + SLAB_MM
    start, stop = [*PORT, 0.0], [*PORT, D_MM]
    return {"mesh": {"x": _xy(0.0, A_MM), "y": _xy(0.0, B_MM),
                     "z": _air([round(v, 6) for v in np.arange(-1, 1.81, 0.2)], -AIR_MM, AIR_MM)},
            "excitation": dc_pulse(F_MAX, T_MAX, WINDOW_S),
            "materials": [{"name": "substrate_0", "eps": EPS_R, "kappa": 0.0, "priority": 10,
                           "solids": [{"x": [x0, x1, x1, x0], "y": [y0, y0, y1, y1], "z": [0.0, D_MM]}]}],
            "metal": {"copper": [{**plate, "z": [0.0, 0.0]}, {**plate, "z": [D_MM, D_MM]}],
                      "lid": {"plate": None, "walls": []}, "cylinders": [], "curves": []},
            "ports": [{"name": "P1", "kind": "lumped", "dir": "z", "start": start, "stop": stop, "part": False,
                       "nodes": [start, stop, start, stop]}],
            "grid": [], "copper": "sheet", "boundary": "pml_8"}


def z_in(t_u: np.ndarray, u: np.ndarray, t_i: np.ndarray, i: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Z_in (F,) in Ω on `f` (Hz) of one port's voltage `u` at `t_u` and current `i` at `t_i`: its S from s_matrix's
    port DFT, then Z0·(1 + S)/(1 − S) at s_matrix's own Z0."""
    s = waves.s_matrix([(t_u, u[None], t_i, i[None])], f)[0][:, 0, 0]
    return waves.Z0 * (1 + s) / (1 - s)


def peaks(f: np.ndarray, re_z: np.ndarray) -> list[float]:
    """The resonances of Re Z_in `re_z` on the uniform grid `f` (Hz): find_peaks on 20·log10 of it floored at 1e-4 of
    its largest value, so that a trough's small negative values make no −240 dB dips, at PROMINENCE_DB, the design's
    "more than 3 dB above its neighbouring minima"; those of at least MIN_PEAK of the largest value, each refined by
    the parabola through its three points on re_z. Ascending, as floats."""
    top = re_z.max()
    k = find_peaks(20 * np.log10(np.maximum(re_z, 1e-4 * top)), prominence=PROMINENCE_DB)[0]
    k = k[re_z[k] >= MIN_PEAK * top]
    y0, y1, y2 = re_z[k - 1], re_z[k], re_z[k + 1]
    return (f[k] + (f[1] - f[0]) * (y0 - y2) / (2 * (y0 - 2 * y1 + y2))).tolist()


def _labels(f: np.ndarray, a: float, b: float) -> list[tuple[int, int]]:
    """Each of `f` (Hz) labelled (m, n) by the nearest closed-form mode of an `a` × `b` mm rectangle at EPS_R,
    c/(2√εr)·√((m/a)² + (n/b)²)."""
    # ponytail: the nearest label holds while no two modes lie closer than the solver's error (A12); a box with
    # degenerate modes would need its pairs by eigenvector overlap
    v = C0 * 1e3 / (2 * math.sqrt(EPS_R))  # mm/s
    mn = [(m, n) for m in range(int(f.max() * a / v) + 2) for n in range(int(f.max() * b / v) + 2) if m or n]
    f_mn = np.array([v * math.hypot(m / a, n / b) for m, n in mn])
    return [mn[j] for j in np.abs(f[:, None] - f_mn).argmin(axis=1)]


def eigen() -> list[dict]:
    """cavity.solve at EPS_R on the plates' outline buffered by DELTA_MM with mitred corners, to F_MAX, and on the plain
    outline to 1.05·F_MAX, so that every buffered mode has its plain partner; the non-DC modes from F_GRID's 1 GHz.
    Each list's modes are labelled by the nearest closed-form mode of their own rectangle (_labels; A12: the 50 × 30
    box has no degenerate mode) and paired by that label, never by sorted index. A mode is "nodal" where its
    closed-form shape |cos(mπ(x + Δ)/(a + 2Δ))·cos(nπ(y + Δ)/(b + 2Δ))| is under NODAL at PORT. Returns the buffered
    modes in order, each {"mn": [m, n], "f_hz", "plain_hz", "nodal"}."""
    a, b = A_MM + 2 * DELTA_MM, B_MM + 2 * DELTA_MM
    buffered = cavity.solve(box(0, 0, A_MM, B_MM).buffer(DELTA_MM, join_style="mitre"), EPS_R, F_MAX).f
    plain = cavity.solve(box(0, 0, A_MM, B_MM), EPS_R, 1.05 * F_MAX).f
    buffered, plain = buffered[buffered >= F_GRID[0]], plain[plain >= F_GRID[0]]
    partner = dict(zip(_labels(plain, A_MM, B_MM), plain))
    x, y = PORT
    return [{"mn": [m, n], "f_hz": float(f), "plain_hz": float(partner[m, n]),
             "nodal": abs(math.cos(m * math.pi * (x + DELTA_MM) / a) * math.cos(n * math.pi * (y + DELTA_MM) / b))
             < NODAL} for (m, n), f in zip(_labels(buffered, a, b), buffered)]


def references() -> dict:
    """E-E's references, computed in memory, no openEMS: the decision's constants and eigen()'s modes."""
    return {"source": "tools/ee.py --references, before any E-E run: cavity.solve on the outline buffered by "
                      "Hammerstad's delta and on the plain one",
            "delta_mm": DELTA_MM, "tol": TOL, "prominence_db": PROMINENCE_DB, "min_peak": MIN_PEAK, "nodal": NODAL,
            "rule": "each peak takes its nearest non-nodal mode; a mode two peaks claim keeps the nearer, the other "
                    "peak is recorded unmatched",
            "modes": eigen()}


def decide(peaks_hz: list[float], modes: list[dict], tol: float = TOL) -> dict:
    """E-E's rule (design 5.12; AR-10): each peak takes its nearest non-nodal mode of `modes` (eigen()'s); a mode that
    several peaks claim keeps the nearest, and the others are recorded unmatched. Returns {"verdict": "incomplete"
    with no match, "pass" when every matched |peak/mode − 1| ≤ `tol`, else "fail"; "matched", in the modes' order, each
    {"peak_hz", "mode_hz", "plain_hz", "mn", "error_pct": 100·(peak/mode − 1)}; "unmatched_peaks_hz";
    "unmatched_modes_hz", the non-nodal modes no peak kept; "offset_pct", the fringing bias: the mean of
    100·(peak/plain − 1) over the matched pairs, None with no match}."""
    live = [m for m in modes if not m["nodal"]]
    kept = {}  # a mode's index in live: the nearest peak that claims it
    for p in peaks_hz:
        j = min(range(len(live)), key=lambda j: abs(p - live[j]["f_hz"]), default=None)
        if j is not None and (j not in kept or abs(p - live[j]["f_hz"]) < abs(kept[j] - live[j]["f_hz"])):
            kept[j] = p
    matched = [{"peak_hz": kept[j], "mode_hz": m["f_hz"], "plain_hz": m["plain_hz"], "mn": m["mn"],
                "error_pct": 100 * (kept[j] / m["f_hz"] - 1)} for j, m in enumerate(live) if j in kept]
    verdict = ("incomplete" if not matched
               else "pass" if all(abs(x["peak_hz"] / x["mode_hz"] - 1) <= tol for x in matched) else "fail")
    return {"verdict": verdict, "matched": matched,
            "unmatched_peaks_hz": [p for p in peaks_hz if p not in kept.values()],
            "unmatched_modes_hz": [m["f_hz"] for j, m in enumerate(live) if j not in kept],
            "offset_pct": float(np.mean([100 * (x["peak_hz"] / x["plain_hz"] - 1) for x in matched]))
            if matched else None}


def predict(s: dict, mcs: float) -> dict:
    """The cost of the one job of the spec `s` at `mcs` MC/s, before the run: {"cells": Π lines; "dt": the Courant
    step of each axis's smallest cell, 1/(c·√Σ 1/Δmin²), in s; "to_t_max_s" and "to_ceiling_s": p0.predicted_s to
    T_MAX and to RING_CEILING·T_MAX, where the ring rule may run on}."""
    lines = [s["mesh"][a] for a in "xyz"]
    cells = math.prod(map(len, lines))
    dt = 1 / (C0 * math.sqrt(sum(1 / (np.diff(v).min() * 1e-3) ** 2 for v in lines)))
    return {"cells": cells, "dt": dt, "to_t_max_s": p0.predicted_s(1, 1, cells, dt, T_MAX, mcs),
            "to_ceiling_s": p0.predicted_s(1, 1, cells, dt, RING_CEILING * T_MAX, mcs)}


def _run(s: dict) -> dict:
    """The step's work: run_model's job phase on the spec `s` at PRESET, port 1, plus "peaks_hz": peaks of Re z_in on
    F_GRID from the job's whole waves.npz."""
    run = p0.run_model(p0.model_of(s), PRESET, STEP, [1])
    with np.load(p0.run_path(run["run_dir"]) / run["jobs"][0]["job"] / "waves.npz") as w:
        z = z_in(w["t_u"], w["u"][0], w["t_i"], w["i"][0], F_GRID)
    return {**run, "peaks_hz": peaks(F_GRID, z.real)}


def measure(out: Path) -> dict:
    """E-E's measurements of the P0 folder `out`, from its step's record: {"run": {"run_dir" (a name), "verdict",
    "t_stop", "wall_s" (run_model's, the job phase), "cells" (Π lines, as cost counts), "dt" (the setup's),
    "speed_mcs", "predicted_s" (p0.predicted_s of the job to t_stop at runs.per_job_mcs(entry, 1) of this machine's
    calibration entry, None without one), "peaks_hz", "machine" (p0.machine: whether another process loaded the
    step)}, "decision": decide of the peaks against REFERENCES' modes at its tol, never eigen()}. A job whose verdict
    is not in KEPT is judged on no peak: "incomplete", offset_pct None."""
    (rec,) = p0.records(out, [STEP])
    res, refs = rec["result"], json.loads(REFERENCES.read_text(encoding="utf-8"))
    (job,) = res["jobs"]
    entry = runs.load_settings().get("machines", {}).get(runs.machine_key())
    cells, dt, t_stop = math.prod(len(v) for v in spec()["mesh"].values()), res["setup"]["dt"], job["t_stop"]
    run = {"run_dir": res["run_dir"], "verdict": job["verdict"], "t_stop": t_stop, "wall_s": res["wall_s"],
           "cells": cells, "dt": dt, "speed_mcs": next(iter(res["speeds_mcs"]), None),
           "predicted_s": None if entry is None or t_stop is None
           else p0.predicted_s(1, 1, cells, dt, t_stop, runs.per_job_mcs(entry, 1)),
           "peaks_hz": res["peaks_hz"], "machine": p0.machine([rec])}
    return {"run": run, "decision": decide(res["peaks_hz"] if job["verdict"] in KEPT else [], refs["modes"],
                                           refs["tol"])}


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), with p0.table: EE-1 every mode of REFERENCES with the
    peak that kept it, then every unmatched peak, the verdict and the offset; EE-2 the run."""
    refs, d = json.loads(REFERENCES.read_text(encoding="utf-8")), result["decision"]
    kept = {tuple(x["mn"]): x for x in d["matched"]}

    def mhz(v: float | None) -> str | None:
        return None if v is None else f"{v / 1e6:.1f}"

    rows = [{"mn": f"({m['mn'][0]}, {m['mn'][1]})", "mode_mhz": mhz(m["f_hz"]), "plain_mhz": mhz(m["plain_hz"]),
             "nodal": m["nodal"], "peak_mhz": mhz(x and x["peak_hz"]), "error_pct": x and f"{x['error_pct']:+.2f}"}
            for m in refs["modes"] for x in [kept.get(tuple(m["mn"]))]]
    rows += [{"peak_mhz": mhz(p)} for p in d["unmatched_peaks_hz"]]
    offset = "–" if d["offset_pct"] is None else f"{d['offset_pct']:+.2f} %"
    return "\n\n".join([
        "## EE-1 Peaks and modes",
        f"Each peak of Re Z_in, {refs['prominence_db']:g} dB above its neighbouring minima and at least "
        f"{100 * refs['min_peak']:g} % of the largest, takes its nearest mode not nodal at the port of the solve on "
        f"the outline buffered by Δ = {refs['delta_mm']:.4f} mm; a mode two peaks claim keeps the nearer. The verdict "
        f"is pass when every matched pair agrees within {100 * refs['tol']:g} %; an unmatched peak or mode is "
        "recorded, not failed.",
        p0.table(rows, ["mn", "mode_mhz", "plain_mhz", "nodal", "peak_mhz", "error_pct"]),
        f"Verdict: {d['verdict']}. The offset of the peaks from the plain outline's modes, the fringing bias: "
        f"{offset}.",
        "## EE-2 The run",
        p0.table([result["run"]], ["run_dir", "verdict", "t_stop", "wall_s", "cells", "dt", "speed_mcs",
                                   "predicted_s"])]) + "\n"


def write(out: Path) -> dict:
    """measure of the P0 folder `out`: <out>/ee/ee.json through p0.save, {"gate": "E-E", "versions", "spec_hash",
    "references": {"file", "sha256" of its text, read with universal newlines so that a CRLF checkout hashes alike},
    "run", "decision", "calibration": this machine's settings entry without its key, which holds a host name, as
    p3a's}, and ee.md beside it. Returns the JSON as saved."""
    m, entry = measure(out), runs.load_settings().get("machines", {}).get(runs.machine_key()) or {}
    result = p0.save(out / "ee" / "ee.json", {
        "gate": "E-E", "versions": p0.versions(), "spec_hash": spec_hash(spec()),
        "references": {"file": REFERENCES.relative_to(p0.ROOT).as_posix(),
                       "sha256": hashlib.sha256(REFERENCES.read_text(encoding="utf-8").encode()).hexdigest()},
        **m, "calibration": {key: entry.get(key) for key in ("aggregate_mcs", "pool", "threads", "levels")}})
    (out / "ee" / "ee.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/ee.py --references: writes REFERENCES through p0.save; SystemExit when it exists. python
    tools/ee.py --out DIR [--cost]: enters the P0 folder DIR (p0.enter); with --cost, prints predict of spec() at
    runs.per_job_mcs(·, 1) of this machine's calibration, measured first on a machine that has none, as JSON, and
    returns 0; else runs the step through p0.step, keyed by the spec's hash, printing its traceback and returning 1
    when it raises, then writes the gate and returns 0. A rerun finds the record stored, so it only assembles."""
    parser = argparse.ArgumentParser(prog="ee", description="Gate E-E's openEMS confirmation (Stage 5 design 5.12).")
    parser.add_argument("--out", help="<EMC_GATES>, outside every git work tree")
    parser.add_argument("--cost", action="store_true",
                        help="print the run's predicted cost as JSON instead of running it; a machine with no "
                             "calibration is calibrated first")
    parser.add_argument("--references", action="store_true", help="write the references once, before any run")
    args = parser.parse_args(argv)
    if args.references:
        if REFERENCES.exists():
            raise SystemExit("E-E's references are committed once, before its run, and never regenerated")
        p0.save(REFERENCES, references())
        return 0
    if args.out is None:
        parser.error("--out is required without --references")
    out, s = p0.enter(Path(args.out)), spec()
    if args.cost:
        print(json.dumps(predict(s, runs.per_job_mcs(runs.ensure_calibrated(runs.load_settings()), 1))))
        return 0
    try:
        p0.step(out, STEP, spec_hash(s), partial(_run, s))
    except Exception:  # printed; SystemExit (STOP) and KeyboardInterrupt end the harness
        traceback.print_exc()
        return 1
    write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
