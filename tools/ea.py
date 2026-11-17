# SPDX-License-Identifier: GPL-3.0-or-later
"""Gate E-A, the emission closed forms (Stage 5 design 5.12), the controller's: P3-A's 12 mm dipole and a 5 × 5 mm loop
as hand-written specs carrying the emission excitation key, through p0, judged by §5.8's post code against
tests/fixtures/ea/criteria.json, frozen before the run. Run: python tools/ea.py --criteria | --out DIR [--cost]
[--attempt N]."""
import argparse
import hashlib
import json
import math
import sys
import traceback
from dataclasses import replace
from functools import partial
from pathlib import Path

import numpy as np
from scipy import constants

import p0
import p3a
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.geometry.region import C0, air_cell, air_gap
from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines
from kicad_rf_studio.core.model.csx import PML_CELLS
from kicad_rf_studio.core.model.spec import emission_pulse, spec_hash, with_pml
from kicad_rf_studio.core.post.emission import emission_rows
from kicad_rf_studio.core.post.farfield import read_far_field, snapped
from kicad_rf_studio.stoprule import KEPT, tail_fit

PRESET = "normal"
CASES = ("dipole", "loop")
CRITERIA = p0.FIX / "ea" / "criteria.json"  # written once by --criteria, committed before any run
DIPOLE_F = [1e9 + 1e8 * k for k in range(16)]  # 1–2.5 GHz, past the antenna's cap of 11
LOOP_F = [5e8 + 1e8 * k for k in range(11)]
LOOP_JUDGED = [5e8, 1e9, 1.5e9]
PASS = ("(1) E_max·r/I_in within ±0.5 dB of η·tan(kL/4)/(2π), the sinusoidal current's feed-referenced form (the "
        "Hertzian form is about 6 dB off for a gap-fed wire, r5); the identity |E|·r = √(η·D·P_rad/(2π)) within ±0.05 "
        "dB; η_rad = 1 ± 0.02 where P_acc/P_inc ≥ 1e-3; (2) E_max(3 m)/I_port within ±0.5 dB of 1.3169e-14·f²·A/r, A "
        "from the mesh-snapped centre line; no η or closure on the loop: r5 computed P_acc/P_inc ≈ 3.2e-4 for a 10 mm "
        "loop at 1 GHz, and a smaller one is worse")  # design 5.12, the E-A row's Pass column
# at DC a closed loop is one PEC piece, so the port gate's witnesses share a root (pipeline.port_gates); p0.run_model
# records it and runs on
EXPECTED_BLOCKS = {"dipole": [], "loop": ["E_PORT_SHORT"]}
LISTS = ("f_hz", "e_ma", "e_3m", "p_acc", "p_inc", "p_rad")  # the emission_rows columns a step keeps, aligned in f


def dipole_spec() -> dict:
    """E-A's dipole (design 5.12 E-A (1); AR-14): P3-A's 12 mm wire (p3a.dipole) with the emission pulse over 1–2.5 GHz,
    its air gap λ/4 at 1 GHz and its air cell λ/20 at 2.5 GHz, recording the far field at DIPOLE_F."""
    return p3a.dipole(p3a.SHORT_MM, f_hz=DIPOLE_F, gap_mm=air_gap(1e9), cmax_mm=air_cell(2.5e9),
                      excitation=emission_pulse(1e9, 2.5e9))


def loop_spec() -> dict:
    """E-A's loop (design 5.12 E-A (2); AR-14) as a model spec, hand-written as p3a's dipole: five PEC sheet strips at z
    0, 0.1 mm wide and centred on x, y = ±2.5 mm, the bottom one split by the gap x ∈ [−0.05, 0.05]; in vacuum under
    PML_8, the emission pulse over 0.5–1.5 GHz; a lumped port P1 in x across the gap, flat on the bottom strip, its caps
    on the gap's edges and its witnesses one cell into each piece. The mesh: x and y every 0.1 mm from −2.65 to 2.65 mm,
    z at −0.1, 0 and 0.1 mm, each graded at 1.3 up to air_cell(1.5 GHz) out to air_gap(0.5 GHz) past the loop, then
    with_pml. The far field is recorded at LOOP_F about the origin."""
    gap, cell = air_gap(5e8), air_cell(1.5e9)

    def axis(lines: list[float], lo: float, hi: float) -> list[float]:
        return with_pml([round(float(v), 6) for v in smooth_mesh_lines(np.array([*lines, lo - gap, hi + gap]), cell,
                                                                       1.3)])

    def strip(x0: float, x1: float, y0: float, y1: float) -> dict:
        return {"x": [x0, x1, x1, x0], "y": [y0, y0, y1, y1], "z": [0.0, 0.0]}

    fine = [round(-2.65 + 0.1 * k, 6) for k in range(54)]
    return {"mesh": {"x": axis(fine, -2.55, 2.55), "y": axis(fine, -2.55, 2.55), "z": axis([-0.1, 0.0, 0.1], 0.0, 0.0)},
            "excitation": emission_pulse(5e8, 1.5e9), "materials": [],
            "metal": {"copper": [strip(-2.55, -0.05, -2.55, -2.45), strip(0.05, 2.55, -2.55, -2.45),
                                 strip(2.45, 2.55, -2.55, 2.55), strip(-2.55, 2.55, 2.45, 2.55),
                                 strip(-2.55, -2.45, -2.55, 2.55)],
                      "lid": {"plate": None, "walls": []}, "cylinders": [], "curves": []},
            "ports": [{"name": "P1", "kind": "lumped", "dir": "x", "start": [-0.05, -2.55, 0.0],
                       "stop": [0.05, -2.45, 0.0], "part": False,
                       "nodes": [[-0.05, -2.55, 0.0], [0.05, -2.55, 0.0], [-0.15, -2.55, 0.0], [0.15, -2.55, 0.0]]}],
            "grid": [], "nf2ff": {"f_hz": list(LOOP_F), "center": [0.0, 0.0, 0.0]}, "copper": "sheet",
            "boundary": "pml_8"}


def loop_area_mm2(spec: dict) -> float:
    """The area inside the centre lines of loop_spec's strips in `spec`, in mm², as the mesh-snapped strips give them
    (design 5.12 E-A (2)): each strip's edges snapped to their nearest mesh lines, a tall strip giving an x centre and a
    wide one a y centre; the span of the x centres times that of the y centres."""
    centres = {"x": [], "y": []}
    for s in spec["metal"]["copper"]:
        (x0, x1), (y0, y1) = ([min(spec["mesh"][a], key=lambda v: abs(v - e)) for e in (min(s[a]), max(s[a]))]
                              for a in "xy")
        if y1 - y0 > x1 - x0:
            centres["x"].append((x0 + x1) / 2)
        else:
            centres["y"].append((y0 + y1) / 2)
    return math.prod(max(c) - min(c) for c in centres.values())


def criteria() -> dict:
    """E-A's criteria (design 5.12, its row's Pass column; AR-14), computed in memory, no openEMS: the dipole's
    feed-referenced closed form η·tan(kL/4)/(2π) per A at each of DIPOLE_F, its NF2FF identity and η tolerances, and
    the loop's 1.3169e-14·f²·A/r per mA at each of LOOP_JUDGED, A from loop_area_mm2; η and r are the criteria's own
    (scipy.constants, 3 m), never the product's; the setup gates expected to block; and what is incomplete."""
    eta, r = constants.physical_constants["characteristic impedance of vacuum"][0], 3.0
    area, length = loop_area_mm2(loop_spec()), p3a.SHORT_MM
    return {"gate": "E-A", "source": PASS, "eta_ohm": eta, "r_m": r, "expected_blocks": EXPECTED_BLOCKS,
            "dipole": {"length_mm": length, "f_hz": DIPOLE_F,
                       "e_r_per_a": [eta * math.tan(2 * math.pi * f / constants.c * length * 1e-3 / 4) / (2 * math.pi)
                                     for f in DIPOLE_F],
                       "e_tol_db": 0.5, "identity_tol_db": 0.05, "eta_rad": 1.0, "eta_tol": 0.02, "p_acc_min": 1e-3,
                       # the critics' estimate: P_acc/P_inc 6e-6 to 3e-4 on a 12 mm wire, so η is judged nowhere
                       # (open issue 2)
                       "eta_judged_expected": 0},
            "loop": {"side_mm": 5.0, "area_mm2": area, "constant": 1.3169e-14, "f_hz": LOOP_JUDGED,
                     "e_per_ma": [1.3169e-14 * f ** 2 * area * 1e-6 / r * 1e-3 for f in LOOP_JUDGED], "e_tol_db": 0.5},
            "incomplete": "a case with no record, a verdict not in KEPT, a criteria frequency missing from its far "
                          "field (a relative 1e-6), or a blocking setup gate other than expected_blocks': handled as a "
                          "fail (Task 14)"}


def predict(spec: dict, mcs: float) -> dict:
    """The one job of `spec` before the run, on cost's emission basis (AR-14): {"cells": Π lines; "pml": the cells
    openEMS's UPML updates, cells − Π(len − 2·(PML_CELLS + 1)), as p3a counts; "dt": the Courant step of each axis's
    smallest cell, 1/(c·√Σ 1/Δmin²), in s, as ee.predict has it; "to_t_max_s": its time to the spec's T_max, each PML
    cell weighted by runs.PML_WEIGHT, at `mcs` × runs.small_speed(1) MC/s}. `mcs` is pipeline.prepare's for a small
    model."""
    lines = [spec["mesh"][a] for a in "xyz"]
    cells = math.prod(map(len, lines))
    pml = cells - math.prod(len(v) - 2 * (PML_CELLS + 1) for v in lines)
    dt = 1 / (C0 * math.sqrt(sum(1 / (np.diff(v).min() * 1e-3) ** 2 for v in lines)))
    return {"cells": cells, "pml": pml, "dt": dt,
            "to_t_max_s": (cells + (runs.PML_WEIGHT - 1) * pml) * (spec["excitation"]["t_max"] / dt)
            / (mcs * runs.small_speed(1) * 1e6)}


def _case(spec: dict, sid: str) -> dict:
    """A step's work: run_model's job phase on `spec` at PRESET, port 1, then, for a kept job with waves, the rings
    tail_fit reads in its whole waves.npz, its sphere (pipeline.far_field) with the frequencies snapped to the spec's
    list, and emission_rows on them, with no resistor and no carrier. Returns the run plus "verdict", "t_stop",
    "blocked" (the setup gate's codes), "rings", and LISTS and "d_max", aligned in f, all empty without a far field."""
    run = p0.run_model(p0.model_of(spec), PRESET, sid, [1])
    (done,) = run["jobs"]
    far = {"rings": [], "d_max": [], **{key: [] for key in LISTS}}
    if done["verdict"] in KEPT and done["waves"]:
        folder = p0.run_path(run["run_dir"])
        with np.load(folder / done["waves"]) as w:
            t_u, u, t_i, i = w["t_u"], w["u"], w["t_i"], w["i"]
        rings = tail_fit(t_u, u, spec["excitation"], done["t_stop"])
        sphere = read_far_field(pipeline.far_field(folder / done["job"])["sphere"])
        sphere = replace(sphere, f=snapped(sphere.f, spec["nf2ff"]["f_hz"]))
        rows = emission_rows(sphere, t_u, u, t_i, i, rings, resistive=False, f0=None)
        far = {"rings": rings, "d_max": sphere.d_max.tolist(), **{key: [row[key] for row in rows] for key in LISTS}}
    return {**run, "verdict": done["verdict"], "t_stop": done["t_stop"],
            "blocked": [code for code, _ in run["blocked"]], **far}


def _steps(out: Path, attempt: int) -> dict[str, dict]:
    """The step records of `attempt` that the P0 folder `out` holds, by case (p0.records: one code)."""
    ids = {case: f"ea-{case}-a{attempt}" for case in CASES}
    there = {case: i for case, i in ids.items() if (out / "steps" / f"{i}.json").is_file()}
    return dict(zip(there, p0.records(out, list(there.values()))))


def measure(out: Path, attempt: int) -> dict:
    """E-A's measurements of `attempt` in the P0 folder `out`: {case: its step's result (_case's), None when the step
    stored no record}."""
    steps = _steps(out, attempt)
    return {case: steps[case]["result"] if case in steps else None for case in CASES}


def decide(m: dict, crit: dict) -> dict:
    """E-A's rule (design 5.12; AR-14) on measure's `m` against the criteria `crit`: "incomplete" for what
    crit["incomplete"] names, its reasons in "incomplete", with no rows; else, at each of the dipole's frequencies,
    e_err_db = 20·log10(e_ma·1e3·r/e_r_per_a), identity_db = 20·log10(e_3m·r/√(η·d_max·p_rad/(2π))), acc_ratio =
    p_acc/p_inc and eta = p_rad/p_acc, judged where acc_ratio ≥ p_acc_min, and at each of the loop's judged ones,
    e_err_db = 20·log10(e_ma/e_per_ma). "fails" in order dipole_e, dipole_identity, dipole_eta and loop_e, each a value
    past its tolerance or not finite (JSON's null, a NaN, fails); "pass" with none. "eta_judged" counts the
    frequencies η is judged at."""
    why, at = [], {}
    for case in CASES:
        c = m.get(case)
        if c is None:
            why.append(f"{case}: no record")
            continue
        if c["verdict"] not in KEPT:
            why.append(f"{case}: verdict {c['verdict']}")
        why += [f"{case}: {code} blocks" for code in c["blocked"] if code not in crit["expected_blocks"][case]]
        f = np.array(c["f_hz"], dtype=float)
        at[case] = [np.flatnonzero(np.isclose(f, x, rtol=1e-6, atol=0))[:1] for x in crit[case]["f_hz"]]
        if missing := [x for x, k in zip(crit[case]["f_hz"], at[case]) if not k.size]:
            why.append(f"{case}: no far field at {', '.join(f'{x / 1e6:g}' for x in missing)} MHz")
    if why:
        return {"verdict": "incomplete", "fails": [], "eta_judged": 0, "dipole": [], "loop": [], "incomplete": why}

    def v(case: str, key: str) -> np.ndarray:
        """`key` of `case` at its criteria frequencies, a null as NaN."""
        return np.array([m[case][key][k[0]] for k in at[case]], dtype=float)

    d, lo, r = crit["dipole"], crit["loop"], crit["r_m"]
    with np.errstate(divide="ignore", invalid="ignore"):  # a zero or a NaN reads as −inf or NaN, which fails
        e_err = 20 * np.log10(v("dipole", "e_ma") * 1e3 * r / np.array(d["e_r_per_a"]))
        identity = 20 * np.log10(v("dipole", "e_3m") * r / np.sqrt(
            crit["eta_ohm"] * v("dipole", "d_max") * v("dipole", "p_rad") / (2 * np.pi)))
        ratio, eta = v("dipole", "p_acc") / v("dipole", "p_inc"), v("dipole", "p_rad") / v("dipole", "p_acc")
        judged = ratio >= d["p_acc_min"]
        loop = 20 * np.log10(v("loop", "e_ma") / np.array(lo["e_per_ma"]))
    held = {"dipole_e": np.abs(e_err) <= d["e_tol_db"], "dipole_identity": np.abs(identity) <= d["identity_tol_db"],
            "dipole_eta": ~judged | (np.abs(eta - d["eta_rad"]) <= d["eta_tol"]),
            "loop_e": np.abs(loop) <= lo["e_tol_db"]}
    fails = [name for name, ok in held.items() if not ok.all()]
    return {"verdict": "fail" if fails else "pass", "fails": fails, "eta_judged": int(judged.sum()),
            "dipole": [{"f_hz": f, "e_err_db": a, "identity_db": b, "acc_ratio": q, "eta": e, "eta_judged": j}
                       for f, a, b, q, e, j in zip(d["f_hz"], *(x.tolist() for x in (e_err, identity, ratio, eta,
                                                                                    judged)))],
            "loop": [{"f_hz": f, "e_err_db": a} for f, a in zip(lo["f_hz"], loop.tolist())]}


def _rings(rings: list[dict]) -> str:
    """tail_fit's `rings` in a table cell: each one's f and Q ("–" for a ring that does not decay), or "none"."""
    return ", ".join(f"{g['f_hz'] / 1e6:.1f} MHz Q {'–' if g['q'] is None else format(g['q'], '.0f')}"
                     for g in rings) or "none"


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), with p0.table: EA-1 the dipole's rows, with P_acc/P_inc
    and whether η was judged at each frequency, then the count; EA-2 the loop's, then the verdict; EA-3 the runs."""
    d = result["decision"]

    def mhz(rows: list[dict]) -> list[dict]:
        return [{**row, "f_mhz": row["f_hz"] / 1e6} for row in rows]

    ran = [{"case": case, "verdict": "no record"} if r is None else
           {"case": case, **r, "rings": _rings(r["rings"]), "blocked": ", ".join(r["blocked"]) or "none"}
           for case, r in result["runs"].items()]
    verdict = (f"Verdict: {d['verdict']}. Fails: {', '.join(d['fails']) or 'none'}."
               + (f" Incomplete: {'; '.join(d['incomplete'])}." if "incomplete" in d else ""))
    return "\n\n".join([
        "## EA-1 The dipole",
        p0.table(mhz(d["dipole"]), ["f_mhz", "e_err_db", "identity_db", "acc_ratio", "eta", "eta_judged"]),
        f"η is judged at {d['eta_judged']} frequencies, where P_acc/P_inc reaches the criteria's p_acc_min "
        "(pre-registered: 0).",
        "## EA-2 The loop",
        p0.table(mhz(d["loop"]), ["f_mhz", "e_err_db"]),
        verdict,
        "## EA-3 The runs",
        p0.table(ran, ["case", "verdict", "t_stop", "rings", "blocked", "cells", "dt", "wall_s", "predicted_s",
                       "speed_mcs"])]) + "\n"


def specs() -> dict[str, dict]:
    """Each of CASES' model spec."""
    return {"dipole": dipole_spec(), "loop": loop_spec()}


def write(out: Path, attempt: int) -> dict:
    """measure and decide of `attempt` in the P0 folder `out`: <out>/ea/ea-a<N>.json through p0.save, {"gate": "E-A",
    "versions", "tools" (p0.tools_id), "criteria": {"file", "sha256" of its text, read with universal newlines so that
    a CRLF checkout hashes alike, as ee's}, "runs": each case's step result, None without one, plus its "spec_hash",
    "cells", "pml", "dt" (the setup's), "speed_mcs" and "predicted_s", predict's figure scaled to the job's t_stop at
    that dt; "decision", decided against the committed criteria file, never criteria(); "calibration", this machine's
    settings entry without its key, which holds a host name, as p3a's, plus "single", the one-job speed a small
    model's prediction starts from; "machine" (p0.machine)}, and ea-a<N>.md beside it. Returns the JSON as saved."""
    m, text = measure(out, attempt), CRITERIA.read_text(encoding="utf-8")
    ran = {}
    for case, spec in specs().items():
        if (res := m[case]) is None:
            ran[case] = None
            continue
        p = predict(spec, pipeline.prepare(p0.model_of(spec), print, small=True)[2])
        dt, t_stop = res["setup"]["dt"], res["t_stop"]
        ran[case] = {**res, "spec_hash": spec_hash(spec), "cells": p["cells"], "pml": p["pml"], "dt": dt,
                     "speed_mcs": next(iter(res["speeds_mcs"]), None),
                     "predicted_s": None if t_stop is None
                     else p["to_t_max_s"] * t_stop / spec["excitation"]["t_max"] * p["dt"] / dt}
    entry = runs.load_settings().get("machines", {}).get(runs.machine_key()) or {}
    result = p0.save(out / "ea" / f"ea-a{attempt}.json", {
        "gate": "E-A", "versions": p0.versions(), "tools": p0.tools_id(),
        "criteria": {"file": CRITERIA.relative_to(p0.ROOT).as_posix(),
                     "sha256": hashlib.sha256(text.encode()).hexdigest()},
        "runs": ran, "decision": decide(m, json.loads(text)),
        "calibration": {key: entry.get(key) for key in ("aggregate_mcs", "pool", "threads", "single", "levels")},
        "machine": p0.machine(list(_steps(out, attempt).values()))})
    (out / "ea" / f"ea-a{attempt}.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/ea.py --criteria: writes CRITERIA through p0.save; SystemExit when it exists. Otherwise enters the
    P0 folder --out (p0.enter) first. With --cost: for each case, predict at pipeline.prepare's small-model MC/s and its
    setup gate alone (run_model with no port, no time step), printed as the last line, JSON {case: {**predict,
    "blocked": the gate's codes}}; returns 1 when a case's codes hold one outside EXPECTED_BLOCKS, else 0. Else runs
    each case's step ea-<case>-a<N> (--attempt N, default 1) through p0.step, keyed by its spec's hash and
    p0.tools_id(), printing a step that raises and going on; then writes the gate from the steps that exist, and
    returns 1 when a step raised, else 0. A rerun finds every record stored, so it only assembles."""
    parser = argparse.ArgumentParser(prog="ea",
                                     description="Gate E-A, the emission closed forms (Stage 5 design 5.12).")
    parser.add_argument("--out", help="<EMC_GATES>, outside every git work tree")
    parser.add_argument("--cost", action="store_true",
                        help="print each case's predicted cost and setup gate as JSON instead of running it")
    parser.add_argument("--attempt", type=int, default=1, help="the attempt's number, 1 unless a ruled rerun")
    parser.add_argument("--criteria", action="store_true", help="write the criteria once, before any run")
    args = parser.parse_args(argv)
    if args.criteria:
        if CRITERIA.exists():
            raise SystemExit("E-A's criteria are committed once, before its run, and never regenerated")
        p0.save(CRITERIA, criteria())
        return 0
    if args.out is None:
        parser.error("--out is required without --criteria")
    out, cases = p0.enter(Path(args.out)), specs()
    if args.cost:
        cost = {}
        for case, spec in cases.items():
            mcs = pipeline.prepare(p0.model_of(spec), print, small=True)[2]
            setup = p0.run_model(p0.model_of(spec), PRESET, f"ea-{case}-setup", [])
            cost[case] = {**predict(spec, mcs), "blocked": [code for code, _ in setup["blocked"]]}
        print(json.dumps(cost))
        return int(any(set(c["blocked"]) - set(EXPECTED_BLOCKS[case]) for case, c in cost.items()))
    failed = False
    for case, spec in cases.items():
        sid = f"ea-{case}-a{args.attempt}"
        print(f"ea: {sid}", flush=True)
        try:
            p0.step(out, sid, f"{spec_hash(spec)}+{p0.tools_id()}", partial(_case, spec, sid))
        except Exception:  # printed and skipped; SystemExit (STOP) and KeyboardInterrupt end the harness
            failed = True
            traceback.print_exc()
    write(out, args.attempt)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
