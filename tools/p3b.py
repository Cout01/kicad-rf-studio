# SPDX-License-Identifier: GPL-3.0-or-later
"""P3-B, the pipeline against a hand-built model (Stage 3 design 5.11): the free geometry pre-check, the hand runs in
their own process, the product's run (shared with P3-C as ifa2g4-solid-n2), the pre-registered checks and diagnoses of
tests/fixtures/p3b/criteria.json against the committed tests/fixtures/p3b/references.json, and p3b.json and p3b.md in
<out>/p3b. Run: python tools/p3b.py --out DIR [--steps ...]."""
import argparse
import json
import math
import subprocess
import sys
from functools import partial
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import Polygon

import p0
import p3
import p3a
import p3b_hand
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.post.antenna import resonance

CRITERIA = json.loads((p0.FIX / "p3b" / "criteria.json").read_text(encoding="utf-8"))  # committed before any run
REFERENCES = p0.FIX / "p3b" / "references.json"  # the hand run, committed before the product's side, never regenerated
PRODUCT, MUR = "ifa2g4-solid-n2", "ifa2g4-solid-mur"  # P3-C's ifa2g4 baseline and the project of its MUR step
EDITS = {PRODUCT: {"copper": "solid"}, MUR: {"copper": "solid", "boundary": "mur", "air_gap_mm": 62.456762}}
STEPS = ("geometry", "hand", "hand-f1", "product", "product-mur", "hand-030")
GEOMETRY = "p3b-geometry"  # the geometry step's id
# each hand run's settings: the reference's; λ/2 at f1 (81.465 mm), the one rerun r1 R2 allows; 0.30 mm on the antenna
HANDS = {"hand": {}, "hand-f1": {"wall_mm": round(299792458 / 1.84e9 / 2 * 1e3, 6)}, "hand-030": {"fine_mm": 0.3}}
LAYERS = {"F.Cu": [0.745, 0.78], "B.Cu": [0.0, 0.035]}  # each copper layer's z range in the product's model
RUNS = ("hand", "hand-f1", "hand-030", "product", "product-mur")  # P3B-2's rows, those recorded
HAND_S = 27 * 60.0  # r1's estimate of a hand run to 30 ns: 1.27 M nodes at the first run's 222.8 MC/s


def geometry(pj: Path) -> dict:
    """The free pre-check (r1 Q2) of the project `pj`: the product's model built in memory (pipeline.load,
    build_model), its copper solids unioned per layer by their z range (LAYERS), each against p3b_hand.copper().
    Returns {"xor_mm2": {layer: the area of their symmetric difference}, "port": {"hand": p3b_hand.port(), "product":
    P1's [start, stop]}}."""
    project, board, geom, _ = pipeline.load(pj)
    spec, hand_cu = pipeline.build_model(project, board, geom).spec, p3b_hand.copper()
    xor = {layer: float(shapely.symmetric_difference(shapely.union_all(
        [Polygon(zip(s["x"], s["y"])) for s in spec["metal"]["copper"] if s["z"] == z]), hand_cu[layer]).area)
        for layer, z in LAYERS.items()}
    p1 = next(q for q in spec["ports"] if q["name"] == "P1")
    return {"xor_mm2": xor, "port": {"hand": list(p3b_hand.port()), "product": [p1["start"], p1["stop"]]}}


def _kept(out: Path, name: str) -> dict | None:
    """The hand run `name`'s <out>/p3b/<name>/hand.json when it holds p3b_hand.script_sha(), else None."""
    path = out / "p3b" / name / "hand.json"
    run = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    return run if run and run.get("script_sha256") == p3b_hand.script_sha() else None


def hand(out: Path, name: str = "hand", fine_mm: float = p3b_hand.FINE_MM, wall_mm: float = p3b_hand.WALL_MM) -> dict:
    """The hand run `name`: <out>/p3b/<name>/hand.json as it is when it holds p3b_hand.script_sha(), as a hand run is
    keyed by the hand module alone, never by the product's code (r1), and so sits outside p0.step; else
    tools/p3b_hand.py run in a process of its own at `fine_mm` and `wall_mm`, with this process's environment, its
    output in <out>/p3b/<name>.log. RuntimeError on a non-zero exit. Returns the hand.json. The harness never imports
    openEMS."""
    if run := _kept(out, name):
        return run
    folder, log = out / "p3b" / name, out / "p3b" / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as f:
        code = subprocess.run([sys.executable, "-X", "utf8", str(p0.ROOT / "tools" / "p3b_hand.py"), "--out",
                               str(folder), "--fine-mm", str(fine_mm), "--wall-mm", str(wall_mm)],
                              stdout=f, stderr=subprocess.STDOUT).returncode
    if code:
        raise RuntimeError(f"p3b: the hand run {name} exited {code}; see {log}")
    return json.loads((folder / "hand.json").read_text(encoding="utf-8"))


def references() -> dict:
    """REFERENCES, the hand run committed as P3-B's reference. SystemExit when it is missing, so that the product's
    side never runs before it, or when its script_sha256 is not p3b_hand.script_sha()."""
    if not REFERENCES.is_file():
        raise SystemExit("p3b: P3-B's reference is committed after the hand run and never regenerated: run the hand "
                         "step and commit it first")
    ref = json.loads(REFERENCES.read_text(encoding="utf-8"))
    if ref.get("script_sha256") != p3b_hand.script_sha():
        raise SystemExit("p3b: the hand model changed after its reference")
    return ref


def step(out: Path, name: str) -> dict:
    """The step `name` of STEPS in <out> (<GATES>): geometry, the pre-check as a p0.step keyed by the hand module's
    hash and the product's model; a hand run of HANDS: hand, the reference's; hand-f1, the one rerun r1 R2 allows when
    the hand run neither hit its criterion nor decayed decay_db; hand-030, a diagnostic; product, PRODUCT's run once
    references() holds; product-mur, MUR's run, a diagnostic. The controller runs hand-f1 and the diagnostics only when
    they are called for (plan 4 Task 9): no step checks it. KeyError for another name."""
    if name == "geometry":
        pj = p3.variant(out, PRODUCT, "ifa2g4", EDITS[PRODUCT])
        return p0.step(out, GEOMETRY, f"{p3b_hand.script_sha()}|{p0.model_key(pj)}", lambda: geometry(pj))
    if name in HANDS:
        return hand(out, name, **HANDS[name])
    if name == "product":
        references()
    project = {"product": PRODUCT, "product-mur": MUR}[name]
    p3.variant(out, project, "ifa2g4", EDITS[project])
    return p3.run_step(out, project)


def _as_measure(run: dict, f: np.ndarray | None) -> dict:
    """The hand run `run` (a hand.json, or the reference) as a measure: its S11 interpolated in its real and imaginary
    parts onto the grid `f` (its own when None); "band" [F_LO, F_HI]; "f_res_hz" and "depth_db" as p3.measure takes
    them; "d_dbi", D_max at f0, the first recorded frequency, in dBi; "far_f_hz" and "eta_rad"; and its
    "criterion_hit", "decay_db", "cells", "t_end" and "wall_s"."""
    own, s, far = np.asarray(run["f_hz"]), np.asarray(run["s11"]), run["far"]
    f = own if f is None else np.asarray(f)
    s11 = np.interp(f, own, s[:, 0]) + 1j * np.interp(f, own, s[:, 1])
    k, f_res = resonance(f, s11)
    return {"f_hz": f, "s11": s11, "band": [p3b_hand.F_LO, p3b_hand.F_HI], "f_res_hz": f_res,
            "depth_db": float(20 * np.log10(abs(s11[k]))), "d_dbi": float(10 * np.log10(far["d_max"][0])),
            "far_f_hz": far["f_hz"], "eta_rad": far["eta_rad"],
            **{key: run[key] for key in ("criterion_hit", "decay_db", "cells", "t_end", "wall_s")}}


def measure(out: Path) -> dict:
    """P3-B's measurements in <out>: "hand", the reference as a measure; "product", p3.measure of PRODUCT; "geometry",
    the geometry step's result, None without one; then, when recorded, "product-mur" (p3.measure of MUR), "hand-030"
    and "hand-f1" (their hand.json as measures). A hand run's S11 lies on the product's grid: PRODUCT's, else MUR's
    (both the band's), else its own."""
    product, mur = p3.measure(out, PRODUCT), p3.measure(out, MUR)
    grid = next((x["f_hz"] for x in (product, mur) if x and x["f_hz"] is not None), None)
    path = out / "steps" / f"{GEOMETRY}.json"
    m = {"hand": _as_measure(references(), grid), "product": product,
         "geometry": json.loads(path.read_text(encoding="utf-8"))["result"] if path.is_file() else None}
    if mur is not None:
        m["product-mur"] = mur
    for name in ("hand-030", "hand-f1"):
        if run := _kept(out, name):
            m[name] = _as_measure(run, grid)
    return m


def _pair(a: dict | None, b: dict | None) -> dict | None:
    """p3.pair of the measures `a`, a hand run's, and `b` at CRITERIA's f_res_rel and conditioned_db; None when either
    is missing or has no S11."""
    if any(x is None or x["s11"] is None for x in (a, b)):
        return None
    return p3.pair(a, b, CRITERIA["f_res_rel"], CRITERIA["conditioned_db"])


def decide(m: dict) -> dict:
    """P3-B's checks (design 5.11) on the measures `m` against CRITERIA, each limit inclusive and None a fail, in this
    order: f_res, p3.pair of the hand and the product (ruling 1 as amended at commit: a miss on no conditioned dip is
    explained when ds11 is within ds11_shift); d, its ΔD at f0 within d_db; eta, its Δη_rad within eta_db; valid, the
    hand hit its end criterion or its decay_db is at most −decay_db (signed: a run that grew is no reference), and the
    product's job converged; geometry, both XORs within their limits. Returns {"f_res": the pair, with "pass"; "d",
    "eta", "valid", "geometry": {"value", "pass"}; "verdict": {"value": "pass", "explained" when the only miss is an
    explained f_res, else "fail"; "fails", the failed checks in order, an explained f_res not among them; "diagnosis":
    on a fail, the first of CRITERIA's diagnoses whose two runs are recorded and pass f_res (explained counts), D and
    η, "product bug presumed" when every entry's runs are recorded and none passes, else None}}."""
    c, hand_m, product, g = CRITERIA, m["hand"], m["product"], m["geometry"]

    def within(v: float | None, limit: float) -> bool:
        return v is not None and v <= limit

    def matches(p: dict | None) -> bool:
        return (p is not None and (p["pass"] or p["explained"]) and within(p["d_db"], c["d_db"])
                and within(p["eta_db"], c["eta_db"]))

    p = _pair(hand_m, product)
    d, eta, xor = p and p["d_db"], p and p["eta_db"], g and g["xor_mm2"]
    verdicts = [job["verdict"] for job in product["jobs"]] if product else []
    checks = {"f_res": p or {"pass": False, "explained": False},
              "d": {"value": d, "pass": within(d, c["d_db"])},
              "eta": {"value": eta, "pass": within(eta, c["eta_db"])},
              "valid": {"value": {"criterion_hit": hand_m["criterion_hit"], "decay_db": hand_m["decay_db"],
                                  "product": verdicts},
                        "pass": (hand_m["criterion_hit"] or within(hand_m["decay_db"], -c["decay_db"]))
                        and set(verdicts) == {"converged"}},
              "geometry": {"value": xor, "pass": xor is not None and xor["F.Cu"] <= c["xor_f_cu_mm2"]
                           and xor["B.Cu"] <= c["xor_b_cu_mm2"]}}
    fails = [k for k, x in checks.items() if not (x["pass"] or k == "f_res" and x["explained"])]
    diagnosis = None
    if fails:
        ran = [(name, a, b) for name, a, b in c["diagnoses"] if m.get(a) is not None and m.get(b) is not None]
        diagnosis = next((name for name, a, b in ran if matches(_pair(m[a], m[b]))),
                         "product bug presumed" if len(ran) == len(c["diagnoses"]) else None)
    value = "fail" if fails else "pass" if checks["f_res"]["pass"] else "explained"
    return {**checks, "verdict": {"value": value, "fails": fails, "diagnosis": diagnosis}}


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), with p0.table, cells by p3a._cell: P3B-1 each check
    with its limit, its value and its pass, f_res with its conditioning, ds11 (the largest ΔS11 in band) and its
    shift-equivalent ds11_shift, then the verdict and the diagnosis; P3B-2 each recorded run's cells, end (t_end, or
    its jobs' verdicts), D in dBi, η_rad range, f_res, depth, wall_s, predicted_s and worst_s (the product's by
    p3.predicted_s, a hand run's r1's estimate, HAND_S); P3B-3 the port boxes, the XORs and the hand's rods."""
    c, d, g = result["criteria"], result["decisions"], result["geometry"]
    v, f, cell = d["verdict"], d["f_res"], p3a._cell
    limits = {  # no "|": a table cell
        "f_res": f"f_rel within {c['f_res_rel']:g}; a miss on no conditioned dip (both inside the grid at or below "
                 f"{c['conditioned_db']:g} dB) is explained when ds11, the largest ΔS11 over [f_lo, f_hi], is within "
                 f"ds11_shift, the largest that a {c['f_res_rel']:.0%} shift of the hand's S11 makes there",
        "d": f"ΔD within {c['d_db']:g} dB at f0",
        "eta": f"Δη_rad within {c['eta_db']:g} dB at every recorded frequency",
        "valid": f"the hand hit its end criterion or its last 2 ns sit {c['decay_db']:g} dB or more under its peak; "
                 "the product's job converged",
        "geometry": f"XOR within {c['xor_f_cu_mm2']:g} mm² on F.Cu and {c['xor_b_cu_mm2']:g} mm² on B.Cu"}
    values = {"f_res": {k: f.get(k) for k in ("f_res", "f_rel", "depth_db", "conditioned", "ds11", "ds11_shift",
                                              "explained")},
              **{k: d[k]["value"] for k in ("d", "eta", "valid", "geometry")}}
    checks = [{"check": k, "limit": limit, "value": cell(values[k]), "pass": d[k]["pass"]}
              for k, limit in limits.items()]
    checks += [{"check": "verdict", "limit": "pass when every check passes; explained when the only miss is an "
                "explained f_res", "value": f"{v['value']}; fails {cell(v['fails'])}", "pass": v["value"] != "fail"},
               {"check": "diagnosis", "limit": "on a fail, the first whose two runs pass f_res, D and η: " + "; ".join(
                   f"{name}, {a} against {b}" for name, a, b in c["diagnoses"])
                + "; product bug presumed when all of them ran and none passes", "value": v["diagnosis"]}]

    def row(name: str, x: dict) -> dict:
        by_hand, eta = name.startswith("hand"), x["eta_rad"]
        return {"run": name, "cells": math.prod(x["cells"]) if by_hand else x["cells"],
                "end": x["t_end"] if by_hand else cell([job["verdict"] for job in x["jobs"]]), "d_dbi": x["d_dbi"],
                "eta_rad": cell(eta and [min(eta), max(eta)]), "f_res_mhz": x["f_res_hz"] and x["f_res_hz"] / 1e6,
                "depth_db": x["depth_db"], "wall_s": x["wall_s"],
                "predicted_s": HAND_S if by_hand else x["predicted_s"], "worst_s": HAND_S if by_hand else x["worst_s"]}

    port, rods = g and g["port"], p3b_hand.rods()
    geo = [("port box, the hand's", port and " to ".join(map(str, port["hand"]))),
           ("port box, the product's", port and " to ".join(map(str, port["product"]))),
           *((f"XOR {layer}, mm²", g and g["xor_mm2"][layer]) for layer in LAYERS),
           ("the hand's rods", f"{len(rods)}: " + "; ".join(f"({x:g}, {y:g})" for x, y in rods))]
    return "\n\n".join([
        "## P3B-1 Checks\n\n" + p0.table(checks, ["check", "limit", "value", "pass"]),
        "## P3B-2 Runs\n\n" + p0.table([row(k, result[k]) for k in RUNS if result.get(k) is not None],
                                       ["run", "cells", "end", "d_dbi", "eta_rad", "f_res_mhz", "depth_db", "wall_s",
                                        "predicted_s", "worst_s"]),
        "## P3B-3 Geometry\n\n" + p0.table([{"item": k, "value": cell(x)} for k, x in geo], ["item", "value"])]) + "\n"


def write(out: Path) -> dict:
    """p3.records over the product steps first (SystemExit on two product codes), then measure, decide and tables of
    <out>: <out>/p3b/p3b.json through p0.save, with the versions, CRITERIA, the reference's scalars (no f_hz, s11 or
    far), this machine's calibration (p3.calibration), the measurements without f_hz and s11, the decisions, the
    product steps' machine time (p0.machine) and each recorded hand run's wall_s; p3b.md beside it. Returns the JSON as
    saved."""
    recs = p3.records(out, [GEOMETRY, *(p3.step_id(name, "run") for name in (PRODUCT, MUR))])
    m, ref = measure(out), references()
    result = p0.save(out / "p3b" / "p3b.json", {
        "gate": "P3-B", "versions": p0.versions(), "criteria": CRITERIA,
        "reference": {k: v for k, v in ref.items() if k not in ("f_hz", "s11", "far")},
        "calibration": p3.calibration(),
        **{k: x and {key: v for key, v in x.items() if key not in ("f_hz", "s11")} for k, x in m.items()},
        "decisions": decide(m), "machine": p0.machine(recs),
        "hand_wall_s": {name: run["wall_s"] for name in HANDS if (run := _kept(out, name))}})
    (out / "p3b" / "p3b.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p3b.py --out DIR [--steps a,b]: enters <GATES> (p3.enter) first; with --steps, runs each of them
    in order (p3.run_steps) and returns 1 when one raised, else 0; without, writes the gate and returns 0."""
    parser = argparse.ArgumentParser(prog="p3b", description="P3-B, the pipeline against a hand-built model (Stage 3 "
                                                             "design 5.11).")
    parser.add_argument("--out", required=True, help="<GATES>, outside every git work tree")
    parser.add_argument("--steps", help=f"comma-separated, among {', '.join(STEPS)}; without it, the report")
    args = parser.parse_args(argv)
    out = p3.enter(Path(args.out))
    if args.steps:
        return p3.run_steps(args.steps.split(","), partial(step, out))
    write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
