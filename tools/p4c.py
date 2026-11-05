# SPDX-License-Identifier: GPL-3.0-or-later
"""P4-C, the SI mesh rule and the TDR (Stage 4 design 5.11; plan 4 rulings C-1 to C-4). The rule at λ/40 and its λ/80
arm run against the d fill on P4-B's straight 90 Ω pair and an L-shaped pair at P4-B's n; the step lines run at the
decided rule. They are judged against `tests/fixtures/p4c/criteria.json` and `references.json`, and p4c.json and
p4c.md are written in <out>/p4c. Run: `python tools/p4c.py --out DIR [--steps ...] [--references]`."""
import argparse
import json
import math
import sys
import tempfile
from functools import partial
from pathlib import Path

import numpy as np
from scipy.constants import c as C_0

import p0
import p3
import p4
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.mesh.gates import fit2d
from kicad_rf_studio.core.post.si import Reading, arrival, compare_verify
from kicad_rf_studio.core.project import INTERFACES

CRITERIA = json.loads((p0.FIX / "p4c" / "criteria.json").read_text(encoding="utf-8"))  # committed before any run
REFERENCES = p0.FIX / "p4c" / "references.json"  # written once by --references, committed before any run
PAIRS = ("p4b_ms90", "p4c_l90")  # P4-B's straight 90 Ω pair (its λ/40 run is P4-B's step) and the L-shaped one
STEP_LINES = ("p4c_step75", "p4c_step35")  # 50 → 75 → 50 Ω and 50 → 35 → 50 Ω, se50 nets
ORDER = ("l40", "l80", "dfill")  # the SI rules, the coarsest first
COUPLED_MM = {"p4b_ms90": 60.0, "p4c_l90": 40.0}  # each pair's coupled run, the L's two 20 mm legs
LEAD_MM, MID_MM = 38.0, 36.0  # a step line's lead, from its port to the step, and its middle (Task 3's step_line)
TARGET = INTERFACES["se50"]["target_ohm"]  # the step lines' target: their TDR's reference


def dispersion(cell_mm: float, eeff: float, length_mm: float, f: float) -> float:
    """The Yee grid's phase error (rad) over `length_mm` of a line at `eeff` with cells `cell_mm` along it, at `f` (Hz)
    (ruling C-2): β·L·(β·Δx)²/24, β = 2πf√eeff/c."""
    beta = 2 * math.pi * f * math.sqrt(eeff) / C_0
    return beta * length_mm * 1e-3 * (beta * cell_mm * 1e-3) ** 2 / 24


def route_limit_mm(cell_mm: float, d_mm: float, eeff: float, f: float, ds_max: float) -> float:
    """The route length (mm) up to which a rule's cells `cell_mm` meet `ds_max` against the d fill's `d_mm` (ruling
    C-2): ds_max over the per-mm difference of dispersion at the cell and at d."""
    return ds_max / (dispersion(cell_mm, eeff, 1.0, f) - dispersion(d_mm, eeff, 1.0, f))


def step_edges(r: Reading, rho_levels: tuple[float, float, float]) -> tuple[float | None, float | None]:
    """The two edges (s) of a step line's localising TDR `r` (ruling C-3), on its reflection ρ = (z − TARGET)/(z +
    TARGET) on r.t, between the levels `rho_levels` (lead, middle, after): the first where ρ first crosses (rho_lead +
    rho_mid)/2 from the lead's side to the middle's at t ≥ t_r = r.rise[0]; the second where it next crosses (rho_mid +
    rho_after)/2 from the middle's side to the after's, so the first edge's tail never reads as it. Each is interpolated
    linearly between the samples either side; None for an edge ρ never crosses (the second, too, without the first).
    The Gaussian edge is centred on its half height in ρ: on the ideal line the Ω half height read the delay 3.1 %
    short, the ρ half height 0.007 %."""
    rho, edges = (r.z - TARGET) / (r.z + TARGET), []
    k = int(np.searchsorted(r.t, r.rise[0]))  # the first sample at t ≥ t_r
    for a, b in zip(rho_levels, rho_levels[1:]):
        h = (a + b) / 2
        x = (rho[k:] - h) * np.sign(b - a)  # under 0 on a's side, from 0 on b's
        hits = np.flatnonzero((x[:-1] < 0) & (x[1:] >= 0))
        if not hits.size:
            break
        k += int(hits[0]) + 1  # the first sample on b's side
        edges.append(float(r.t[k - 1] + (h - rho[k - 1]) * (r.t[k] - r.t[k - 1]) / (rho[k] - rho[k - 1])))
    return (*edges, None, None)[:2]


def step_row(r: Reading, ref: dict) -> dict:
    """A step line's readings of its Reading `r` (ruling C-3) at its references `ref` (references()' steps[board][n]),
    t_a and t_b ref's predicted edges ("t_edges_s"), t_r = r.rise[0]: "z_lead", p4.plateau from t_r to t_a − t_r;
    "z_mid", from t_a + t_r to t_b − t_r; "z_after", from t_b + t_r to t_b + (t_a − t_r); "gamma", (z_mid −
    z_lead)/(z_mid + z_lead); "edges_s", step_edges at those plateaus' ρ; "delay_s", half the time between them;
    "short", the levels' marks (r.levels: [lowest's, highest's]), the short-feature rule's true negative that P4-F's
    report cites. Each None without what it reads."""
    t_r, (t_a, t_b) = r.rise[0], ref["t_edges_s"]
    z = (p4.plateau(r, t_r, t_a - t_r), p4.plateau(r, t_a + t_r, t_b - t_r),
         p4.plateau(r, t_b + t_r, t_b + (t_a - t_r)))
    edges = (None, None) if None in z else step_edges(r, tuple((v - TARGET) / (v + TARGET) for v in z))
    z_lead, z_mid, z_after = z
    return {"z_lead": z_lead, "z_mid": z_mid, "z_after": z_after,
            "gamma": None if None in (z_lead, z_mid) else (z_mid - z_lead) / (z_mid + z_lead), "edges_s": list(edges),
            "delay_s": None if None in edges else (edges[1] - edges[0]) / 2,
            "short": None if r.levels is None else [level[2] for level in r.levels]}


def references() -> dict:
    """P4-C's references (G-1), computed in memory in a temporary folder, no openEMS: each board's base by `new` with
    P4_NEW (p4.base), then its project lossless at the SI rule (new's λ/40), loaded and built (pipeline.load,
    build_model) as its run builds it.
    - "steps", per step line and mesh n as a str (2 and 3): "z_lead" and "z_mid", fit2d's z0_mesh of its lead and its
      middle on that n's mesh; "gamma" from them; "eeff_lead" and "eeff_mid", the product's 2D table's
      (pipeline.si_readout: cs2d with the mask); "t_edges_s", the round trips to its two edges, 2·LEAD_MM·√eeff_lead/c
      and that plus 2·MID_MM·√eeff_mid/c; "delay_s", the middle's MID_MM·√eeff_mid/c.
    - "pairs", per pair at p4.N: "n"; "max_cell_mm" per rule, "l40" new's and "l80" p4.settings' half of it; "d_mm",
      the mesh's d, the d fill's cell; "length_mm", its coupled run's (COUPLED_MM); "eps_odd", the 2D table's odd εeff
      on its longest coupled section; "f_hz", its f_max_hz; "dispersion" at each rule's cell and at d ("dfill"); and
      "route_limit_mm" per rule, against d at CRITERIA's ds_max.
    Then "code" (p0.code_id()) and "versions"."""
    steps, pairs = {}, {}
    with tempfile.TemporaryDirectory() as folder:
        def built(board: str, n: int | None = None) -> tuple:
            """`board`'s project at mesh n `n` (None for p4.N): (the project, its geometry, its model's mesh, its 2D
            table, si_readout's rows)."""
            pj = p4.project(Path(folder), board, n=n, rule="l40", dielectric="lossless")[1]
            project, board_, geom, _ = pipeline.load(pj)
            mesh = pipeline.build_model(project, board_, geom).mesh
            return project, geom, mesh, pipeline.si_readout(board_, geom, project)

        for board in STEP_LINES:
            for n in (2, 3):
                _, geom, mesh, table = built(board, n)
                lead, mid, _ = fit2d(geom, mesh)  # the lead, the middle and the lead after, in place order
                e_lead, e_mid, _ = (float(p["eeff"]) for code, p in table if code == "I_SI_2D_LINE")
                t_a, delay = 2 * LEAD_MM * 1e-3 * math.sqrt(e_lead) / C_0, MID_MM * 1e-3 * math.sqrt(e_mid) / C_0
                steps.setdefault(board, {})[str(n)] = {
                    "z_lead": lead.z0_mesh, "z_mid": mid.z0_mesh,
                    "gamma": (mid.z0_mesh - lead.z0_mesh) / (mid.z0_mesh + lead.z0_mesh), "eeff_lead": e_lead,
                    "eeff_mid": e_mid, "t_edges_s": [t_a, t_a + 2 * delay], "delay_s": delay}
        for board, length in COUPLED_MM.items():
            project, _, mesh, table = built(board)
            coupled = max((p for code, p in table if code == "I_SI_2D_PAIR"), key=lambda p: float(p["length_mm"]))
            eps, f, d = float(coupled["eeff_odd"]), project["f_max_hz"], mesh.d
            cells = {rule: p4.settings(project, rule=rule)["mesh.max_cell_mm"] for rule in ("l40", "l80")}
            pairs[board] = {"n": p4.N, "max_cell_mm": cells, "d_mm": d, "length_mm": length, "eps_odd": eps, "f_hz": f,
                            "dispersion": {**{rule: dispersion(cell, eps, length, f) for rule, cell in cells.items()},
                                           "dfill": dispersion(d, eps, length, f)},
                            "route_limit_mm": {rule: route_limit_mm(cell, d, eps, f, CRITERIA["ds_max"])
                                               for rule, cell in cells.items()}}
    return {"source": "tools/p4c.py --references, before any P4-C run: fit2d's Z0 on each step line's own mesh at n 2 "
                      "and 3 with the 2D table's eeff and the predicted edges, and each pair's cells, d and the Yee "
                      "grid's phase error with each rule's route-length limit",
            "steps": steps, "pairs": pairs, "code": p0.code_id(), "versions": p0.versions()}


def step(out: Path, name: str) -> dict:
    """The step `name`: a step line of STEP_LINES at p4.RULE, or <pair>-<rule> for a pair of PAIRS and a rule of ORDER
    at that rule (p4b_ms90-l40 is P4-B's step, the same project and record); each p4's run step at p4.N and lossless.
    KeyError for another name."""
    board, _, rule = name.rpartition("-")
    if name in STEP_LINES:
        board, rule = name, None
    elif board not in PAIRS or rule not in ORDER:
        raise KeyError(name)
    return p4.run_step(out, p4.project(out, board, rule=rule, dielectric="lossless")[0])


def measure(out: Path) -> dict:
    """P4-C's measurements in <out>, in this process, at p4.N and lossless. "pairs": per pair, per rule of ORDER whose
    step is recorded, p4.measure of its project with "delay_s", arrival(r.t, r.tdt) of its reading (None without one),
    and "ds", {rule: compare_verify's largest |ΔS| of the rule's reading against the d fill's} for each rule whose
    reading and the d fill's both read. "steps": per recorded step line (at p4.RULE), p4.measure of its project with
    step_row of its reading at the references for p4.N (each None without a reading). "rule_now": p4.RULE; "n_now":
    p4.N."""
    refs, pairs, steps = json.loads(REFERENCES.read_text(encoding="utf-8")), {}, {}
    for p in PAIRS:
        runs = {rule: x for rule in ORDER if (x := p4.measure(out, p4.name(p, p4.N, rule, "lossless"))) is not None}
        pairs[p] = {rule: {**x, "delay_s": x["reading"] and arrival(x["reading"].t, x["reading"].tdt)}
                    for rule, x in runs.items()}
        fill = runs.get("dfill", {}).get("reading")
        pairs[p]["ds"] = {rule: compare_verify(x["reading"], fill)["ds_max"] for rule, x in runs.items()
                          if rule != "dfill" and x["reading"] and fill}
    for s in STEP_LINES:
        if (x := p4.measure(out, p4.name(s, dielectric="lossless"))) is not None:
            r = x["reading"]
            steps[s] = {**x, **(step_row(r, refs["steps"][s][str(p4.N)]) if r else
                                dict.fromkeys(("z_lead", "z_mid", "z_after", "gamma", "edges_s", "delay_s", "short")))}
    return {"pairs": pairs, "steps": steps, "rule_now": p4.RULE, "n_now": p4.N}


def _rel(a: float | None, b: float | None) -> float | None:
    """a/b − 1, None when either is None."""
    return None if a is None or b is None else a / b - 1


def decide(m: dict, refs: dict) -> dict:
    """P4-C's checks and decisions (design 5.11; C-1 to C-3) on the measures `m` (measure's shape) against `refs` (the
    references' shape) by CRITERIA, each limit inclusive and a None value a fail:
    - "pairs", per pair and rule (l40, l80) with that run and its d fill both measured, {"pair", "rule", "ds",
      "delay_s", "dfill_delay_s", "delay_rel" (the run's arrival over the d fill's, less 1), "cells", "dfill_cells",
      "fewer_cells", "valid", "dfill_valid", "pass"}: it passes when the run and its d fill are valid (the criteria's
      "every run valid"), ds ≤ ds_max and |delay_rel| ≤ delay_rel;
    - "pairs_rule": "l40" when both pairs pass at λ/40; else "l80" when both pass at λ/80, each with fewer cells than
      its d fill; else "dfill"; None while a run it needs is missing. "rule": the more refined (ORDER) of it and
      m["rule_now"], None with it;
    - "checks", per measured step line at refs' steps for m["n_now"], {"step", "check", "value", "limit", "pass"}:
      z_lead and z_mid, each plateau over fit2d's less 1, within plateau_rel; gamma, less fit2d's, within gamma_abs;
      delay, over the reference's less 1, within step_delay_rel; valid, the run's flag;
    - "refine", on a delay miss: "l80" while rule_now is "l40", else "n3" while n_now is 2, else "controller"; None
      without one;
    - "short_rule": "true negative" when every step line's levels are unmarked ([False, False]), else "owner" (an owner
      item, not a fail); None while a step line is missing;
    - "verdict": {"value": "blocked" on a plateau or gamma miss (a pipeline discrepancy that no cell along the line
      moves), else "fail" on another, else "incomplete" while the rule is None or a step line is missing, else
      "fallback" when the rule is "l80" or "dfill", else "pass"; "fails": "<step>: <check>"}."""
    c, pairs, checks = CRITERIA, [], []
    for p in PAIRS:
        x = m["pairs"].get(p, {})
        for rule in ("l40", "l80"):
            if (run := x.get(rule)) is None or (fill := x.get("dfill")) is None:
                continue
            ds, rel = x.get("ds", {}).get(rule), _rel(run["delay_s"], fill["delay_s"])
            pairs.append({"pair": p, "rule": rule, "ds": ds, "delay_s": run["delay_s"],
                          "dfill_delay_s": fill["delay_s"], "delay_rel": rel, "cells": run["cells"],
                          "dfill_cells": fill["cells"],
                          "fewer_cells": None not in (run["cells"], fill["cells"]) and run["cells"] < fill["cells"],
                          "valid": run["valid"], "dfill_valid": fill["valid"],
                          "pass": bool(run["valid"] and fill["valid"]) and ds is not None and ds <= c["ds_max"]
                          and rel is not None and abs(rel) <= c["delay_rel"]})

    def at(rule: str) -> bool | None:  # both pairs pass at `rule`, at l80 with fewer cells; None while one is unrun
        got = [row["pass"] and (rule == "l40" or row["fewer_cells"]) for row in pairs if row["rule"] == rule]
        return False if False in got else None if len(got) < len(PAIRS) else True

    at40 = at("l40")
    pairs_rule = "l40" if at40 else None if at40 is None else {True: "l80", False: "dfill", None: None}[at("l80")]
    rule = None if pairs_rule is None else max(pairs_rule, m["rule_now"], key=ORDER.index)

    def check(step: str, name: str, value: float | None, limit: float) -> dict:
        return {"step": step, "check": name, "value": value, "limit": limit,
                "pass": value is not None and abs(value) <= limit}

    for s in STEP_LINES:
        if (row := m["steps"].get(s)) is None:
            continue
        ref = refs["steps"][s][str(m["n_now"])]
        checks += [check(s, "z_lead", _rel(row["z_lead"], ref["z_lead"]), c["plateau_rel"]),
                   check(s, "z_mid", _rel(row["z_mid"], ref["z_mid"]), c["plateau_rel"]),
                   check(s, "gamma", None if row["gamma"] is None else row["gamma"] - ref["gamma"], c["gamma_abs"]),
                   check(s, "delay", _rel(row["delay_s"], ref["delay_s"]), c["step_delay_rel"]),
                   {"step": s, "check": "valid", "value": row["valid"], "limit": None, "pass": bool(row["valid"])}]
    fails = [f"{x['step']}: {x['check']}" for x in checks if not x["pass"]]
    missed = {x["check"] for x in checks if not x["pass"]}
    refine = None
    if "delay" in missed:
        refine = "l80" if m["rule_now"] == "l40" else "n3" if m["n_now"] == 2 else "controller"
    unrun = any(s not in m["steps"] for s in STEP_LINES)
    unmarked = not unrun and all(m["steps"][s]["short"] == [False, False] for s in STEP_LINES)
    short_rule = None if unrun else "true negative" if unmarked else "owner"
    if missed & {"z_lead", "z_mid", "gamma"}:
        value = "blocked"
    elif fails:
        value = "fail"
    elif rule is None or unrun:
        value = "incomplete"
    elif rule != "l40":
        value = "fallback"
    else:
        value = "pass"
    return {"pairs": pairs, "pairs_rule": pairs_rule, "rule": rule, "checks": checks, "refine": refine,
            "short_rule": short_rule, "verdict": {"value": value, "fails": fails}}


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), by p0.table: P4C-1 the pairs (each rule against its d
    fill: |ΔS|, the arrivals and their difference, cells, valid and pass; then each pair's dispersion estimate at each
    rule's cell and at d, with each rule's route-length limit; then the decisions and the verdict). P4C-2 the step lines
    (their checks, then their readings beside their references at n_now, with the levels' short marks). P4C-3 the runs:
    cells, pool, t_stop, predicted to t_stop and to T_max, wall."""
    c, refs, runs, verdict = result["criteria"], result["references"], result["runs"], result["verdict"]
    phase = [{"pair": p, **{k: x[k] for k in ("n", "length_mm", "eps_odd", "d_mm")},
              **{f"phase_{rule}": x["dispersion"][rule] for rule in ORDER},
              **{f"limit_{rule}_mm": x["route_limit_mm"][rule] for rule in ("l40", "l80")}}
             for p, x in refs["pairs"].items()]
    n = str(result["n_now"])
    readings = [{"step": s, **{k: runs[s][k] for k in ("z_lead", "z_mid", "z_after", "gamma", "delay_s", "short")},
                 **{f"ref_{k}": refs["steps"][s][n][k] for k in ("z_lead", "z_mid", "gamma", "delay_s")}}
                for s in STEP_LINES if s in runs]
    items = [*({"item": key, "value": result[key]} for key in ("pairs_rule", "rule_now", "rule", "n_now", "refine",
                                                                "short_rule")),
             {"item": "verdict", "value": verdict["value"]},
             {"item": "fails", "value": ", ".join(verdict["fails"]) or "none"}]
    return "\n\n".join([
        "## P4C-1 The pairs",
        f"Each rule's run against its d fill (max_cell_mm null) at mesh n {result['n_now']}, lossless: ds, the largest "
        f"|ΔS| over every entry and 0 < f ≤ f_max, at most {c['ds_max']:g}; delay_rel, the TDT's arrival over the d "
        f"fill's less 1, within {c['delay_rel']:g}; both runs valid. λ/40 stays when both pairs pass; else λ/80 when "
        "both pass at it, each with fewer cells than its d fill; else the d fill stays. The rule is the more refined "
        "of the pairs' and the steps' (rule_now).",
        p0.table(result["pairs"], ["pair", "rule", "ds", "delay_s", "dfill_delay_s", "delay_rel", "cells",
                                   "dfill_cells", "valid", "dfill_valid", "pass"]),
        "Recorded: the Yee grid's phase error β·L·(β·Δx)²/24 at f_max on each pair's coupled run, at each rule's cell "
        "and at d, and each rule's route-length limit, up to which it meets ds_max against the d fill.",
        p0.table(phase, ["pair", "n", "length_mm", "eps_odd", "d_mm", "phase_l40", "phase_l80", "phase_dfill",
                         "limit_l40_mm", "limit_l80_mm"]),
        p0.table(items, ["item", "value"]),
        "## P4C-2 The step lines",
        f"At the rule {result['rule_now']} and mesh n {n}: z_lead, the plateau from t_r to the predicted first edge − "
        f"t_r, and z_mid, between the predicted edges ± t_r, over fit2d's Z0 on the run's own mesh less 1, within "
        f"{c['plateau_rel']:g}; gamma, (z_mid − z_lead)/(z_mid + z_lead) less fit2d's, within {c['gamma_abs']:g}; a "
        "miss blocks, a pipeline discrepancy that no cell along the line moves. delay, half the time between the two "
        "edges, each the half height of the reflection coefficient between the plateaus either side, over "
        f"L·√eeff/c less 1, within {c['step_delay_rel']:g}; a miss is refined, λ/80 under λ/40, then n 3. short, the "
        "levels' marks [lowest, highest]: both unmarked is the short-feature rule's true negative, a mark an owner "
        "item.",
        p0.table(result["checks"], ["step", "check", "value", "limit", "pass"]),
        p0.table(readings, ["step", "z_lead", "ref_z_lead", "z_mid", "ref_z_mid", "z_after", "gamma", "ref_gamma",
                            "delay_s", "ref_delay_s", "short"]),
        "## P4C-3 Runs",
        p0.table([{"step": k, **x} for k, x in runs.items()],
                 ["step", "cells", "pool", "t_stop_s", "predicted_s", "worst_s", "wall_s"])]) + "\n"


def write(out: Path) -> dict:
    """p4.records over the recorded steps first (SystemExit on two product codes), then measure and decide of <out>:
    <out>/p4c/p4c.json through p0.save, with the versions, CRITERIA, the references, the calibration (p3.calibration),
    rule_now and n_now, "runs", each measured step's p4.plain by its --steps name (<pair>-<rule>, a step line), decide's
    pairs, rules, checks, refine, short_rule and verdict, and the steps' machine time (p0.machine); p4c.md beside it
    (tables). Returns the JSON as saved."""
    names = [p4.name(p, p4.N, rule, "lossless") for p in PAIRS for rule in ORDER]
    names += [p4.name(s, dielectric="lossless") for s in STEP_LINES]
    recs = p4.records(out, [p3.step_id(name, "run", "p4") for name in names])
    refs, m = json.loads(REFERENCES.read_text(encoding="utf-8")), measure(out)
    runs = {f"{p}-{rule}": p4.plain(x) for p, xs in m["pairs"].items() for rule, x in xs.items() if rule != "ds"}
    result = p0.save(out / "p4c" / "p4c.json", {
        "gate": "P4-C", "versions": p0.versions(), "criteria": CRITERIA, "references": refs,
        "calibration": p3.calibration(), "rule_now": m["rule_now"], "n_now": m["n_now"],
        "runs": runs | {s: p4.plain(x) for s, x in m["steps"].items()}, **decide(m, refs),
        "machine": p0.machine(recs)})
    (out / "p4c" / "p4c.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p4c.py --references: writes REFERENCES through p0.save, SystemExit when it exists. python
    tools/p4c.py --out DIR [--steps a,b]: enters <GATES> (p4.enter); with --steps, runs each of them in order
    (p4.run_steps) and returns 1 when one raised, else 0; without, writes the report and returns 0."""
    parser = argparse.ArgumentParser(prog="p4c",
                                     description="P4-C, the SI mesh rule and the TDR (Stage 4 design 5.11).")
    parser.add_argument("--out", help="<GATES>, outside every git work tree")
    parser.add_argument("--steps", help=f"comma-separated <pair>-<rule> ({', '.join(PAIRS)}; {', '.join(ORDER)}) or "
                                        f"step lines ({', '.join(STEP_LINES)}); without it, the report")
    parser.add_argument("--references", action="store_true", help="write the references once, before any run")
    args = parser.parse_args(argv)
    if args.references:
        if REFERENCES.exists():
            raise SystemExit("P4-C's references are committed once, before its runs, and never regenerated")
        p0.save(REFERENCES, references())
        return 0
    if args.out is None:
        parser.error("--out is required without --references")
    out = p4.enter(Path(args.out))
    if args.steps:
        return p4.run_steps(args.steps.split(","), partial(step, out))
    write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
