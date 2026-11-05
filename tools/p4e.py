# SPDX-License-Identifier: GPL-3.0-or-later
"""P4-E, the noise floor (Stage 4 design 5.8, 5.11; plan 4 rulings E-1, E-2). It runs P4-B's 90 Ω coupon at the decided
settings, its own base and against it the same run twice, the board shifted one fine cell and its gap moved ± d, and
the null edit when its spec hash is not the base's; and P4-B's terminated-victim coupon against itself shifted one fine
cell, for NEXT's and FEXT's noise. The noise per quantity and the thresholds compare then uses are judged against
`tests/fixtures/p4e/criteria.json` and `references.json`, and p4e.json and p4e.md are written in <out>/p4e. Run:
`python tools/p4e.py --out DIR [--steps base,repeat,shift,gapp,gapm,null,vbase,vshift] [--references]`."""
import argparse
import json
import math
import sys
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path

import p0
import p3
import p4
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.cs2d import Pair, pair
from kicad_rf_studio.core.geometry.sections import cross_section
from kicad_rf_studio.core.mesh.gates import fit2d
from kicad_rf_studio.core.post.si import db, mixed_mode
from p4a import even_odd_s
from p4b import COUPLED_MM, F
from p4c import ORDER

CRITERIA = json.loads((p0.FIX / "p4e" / "criteria.json").read_text(encoding="utf-8"))  # committed before any run
REFERENCES = p0.FIX / "p4e" / "references.json"  # written once by --references, committed before any run
BASE, NULL, VICTIM = "p4b_ms90", "p4e_null", "p4b_ms90_vic"  # P4-B's 90 Ω coupon, its split twin, its victim case
# by mesh n, each moved by that n's fine cell d (make_fixtures' D_SI, D_SI3): BASE shifted, its gap ± d, VICTIM shifted
BOARDS = {2: {"shift": "p4e_shift", "gapp": "p4e_gapp", "gapm": "p4e_gapm", "vshift": "p4e_vshift"},
          3: {"shift": "p4e_shift3", "gapp": "p4e_gapp3", "gapm": "p4e_gapm3", "vshift": "p4e_vshift3"}}
STEPS = ("base", "repeat", "shift", "gapp", "gapm", "null", "vbase", "vshift")
TARGET_OHM, MARKER = 90.0, 48  # usb2-hs's target and its 240 MHz marker on F, 5 MHz apart


def key(row: dict) -> str:
    """A si_deltas row's key: "sdd21@<its marker>" ("sdd21@marker", "sdd21@f_max"), else its quantity."""
    return f"sdd21@{row['marker']}" if row["quantity"] == "sdd21" else row["quantity"]


def noise(pairs: dict[str, list[dict]], model_even: dict) -> dict:
    """The noise (design 5.8; E-2) of si_deltas' rows `pairs` by step (repeat, shift, gapp, gapm, null and vshift, each
    when present), at the mesh model's even parts `model_even` by key:
    - per key, the largest |Δ| of repeat, shift, null and vshift, and, when the key is in model_even and both gap pairs
      hold it, |(Δ_gapp + Δ_gapm)/2 − model_even[key]|; a row without a delta, and a dB row (a key of CRITERIA's IL_DB
      or DB) whose base and variant both lie at or under floor_db, counts in no term;
    - per constant of CRITERIA's, the largest over its keys, 0.0 when none.
    Returns {constant: value, "parts": {key: {"repeat", "shift", "null", "vshift", "even", "model_even", "odd",
    "noise"}}}: each pair's Δ, the gap's even and odd parts (Δ_gapp ± Δ_gapm)/2, the model's even part and the key's
    noise, None where a pair, either gap pair or a model is absent."""
    c = CRITERIA
    dbs = {*c["constants"]["IL_DB"], *c["constants"]["DB"]}

    def counted(rows: list[dict]) -> dict:  # {key: Δ} of the rows that count
        return {key(r): r["delta"] for r in rows if r["delta"] is not None
                and not (key(r) in dbs and max(r["base"], r["variant"]) <= c["floor_db"])}

    d = {step: counted(rows) for step, rows in pairs.items()}
    parts = {}
    for k in dict.fromkeys(k for found in d.values() for k in found):  # each key once, in the rows' order
        part = {step: d.get(step, {}).get(k) for step in ("repeat", "shift", "null", "vshift")}
        plus, minus = (d.get(step, {}).get(k) for step in ("gapp", "gapm"))
        gap, model = None not in (plus, minus), model_even.get(k)
        even = (plus + minus) / 2 if gap else None
        terms = [abs(x) for x in part.values() if x is not None]
        if gap and model is not None:
            terms.append(abs(even - model))
        parts[k] = {**part, "even": even, "model_even": model, "odd": (plus - minus) / 2 if gap else None,
                    "noise": max(terms, default=0.0)}
    return {**{name: max((parts[k]["noise"] for k in keys if k in parts), default=0.0)
               for name, keys in c["constants"].items()}, "parts": parts}


def thresholds(noise: dict) -> dict:
    """The significance thresholds (design 5.8) from `noise`'s constants: each of CRITERIA's design values kept when its
    noise lies under a third of it, else factor × the noise rounded up to the constant's step, to 6 decimals; then
    SE_OHM = DIFF_OHM/2, unmeasured on a pair; "kept", per constant. It reads CRITERIA, never si.py, so a report written
    again after si.py takes the thresholds judges the same way."""
    c, out = CRITERIA, {}
    kept = {name: noise[name] < design / 3 for name, design in c["design"].items()}
    for name, design in c["design"].items():
        step = c["steps"][name]
        out[name] = design if kept[name] else round(math.ceil(round(c["factor"] * noise[name] / step, 9)) * step, 6)
    return {**out, "SE_OHM": out["DIFF_OHM"] / 2, "kept": kept}


def null_equal(out: Path) -> bool:
    """Whether the null edit's model is the base's (E-1): p0.model_key of NULL's project and of BASE's, each at the
    decided settings (p4.project, made when missing)."""
    return p0.model_key(p4.project(out, NULL)[1]) == p0.model_key(p4.project(out, BASE)[1])


def _coupled(folder: Path, board: str, n: int, rule: str) -> tuple[float, Pair, Callable]:
    """`board`'s 60 mm coupled section at mesh n `n` and the rule `rule`, lossless, loaded and built (pipeline.load,
    build_model) as its run builds it, read as P4-B's references read it: (fit2d's coupled z0_mesh on the model's mesh,
    cs2d's pair on the mesh lines, the smeared cut; the section's cross_section with the mask and its partner, for the
    exact cut)."""
    project, board_, geom, _ = pipeline.load(p4.project(folder, board, n=n, rule=rule, dielectric="lossless")[1])
    mesh = pipeline.build_model(project, board_, geom).mesh
    sec = next(s for s in geom.sections if round(s.length, 3) == COUPLED_MM)
    cut = partial(cross_section, sec, geom.pieces, geom.zs, geom.masks.get(sec.layer), partners=geom.partners(sec.net))
    _, fit = [x for x in fit2d(geom, mesh) if x.section == sec]  # the leg's own Fit, then the coupled one
    return fit.z0_mesh, pair(cut("smeared", mesh.dz0), mesh.y if sec.axis == "x" else mesh.x, mesh.z), cut


def _even(z_diff: list[float], modes: list[Pair]) -> dict:
    """The even parts (E-2), (X(s + d) + X(s − d))/2 − X(s), over the boards s, s + d and s − d in that order: the TDR
    rows' of their Zdiff `z_diff`, and "sdd21@marker"'s of db(Sdd21) at MARKER of the even/odd 4-port of their modes
    `modes` over COUPLED_MM at 50 Ω, mixed_mode's at TARGET_OHM."""
    def even(x: list[float]) -> float:
        return (x[1] + x[2]) / 2 - x[0]

    il = [float(db(mixed_mode(even_odd_s(p.z_even, p.eps_even, p.z_odd, p.eps_odd, COUPLED_MM, F), F, TARGET_OHM,
                              True)[MARKER, 1, 0])) for p in modes]
    return {"tdr_lowest": even(z_diff), "tdr_highest": even(z_diff), "sdd21@marker": even(il)}


def references() -> dict:
    """P4-E's references (E-2; G-1), computed in memory in a temporary folder, no openEMS: for n 2 and 3, BASE's and
    BOARDS[n]'s gapp's and gapm's coupled section (_coupled), each board's base by `new` with P4_NEW (p4.base):
    - "model_even"[f"{n}-{rule}"] at each rule of ORDER: _even of fit2d's coupled z0_mesh and of the mesh lines' modes,
      the run's own discretised cut, with "skew" and "scd21_worst" 0.0 by the pair's symmetry;
    - "exact"[str(n)]: _even of cs2d's pair on the exact cut with the mask, recorded.
    Then "code" (p0.code_id()) and "versions"."""
    model, exact = {}, {}
    with tempfile.TemporaryDirectory() as folder:
        for n, boards in BOARDS.items():
            for rule in ORDER:
                got = [_coupled(Path(folder), b, n, rule) for b in (BASE, boards["gapp"], boards["gapm"])]
                model[f"{n}-{rule}"] = {**_even([z for z, _, _ in got], [on for _, on, _ in got]), "skew": 0.0,
                                        "scd21_worst": 0.0}
            cuts = [pair(cut("exact")) for *_, cut in got]  # the exact cut holds no mesh line: the last rule's serves
            exact[str(n)] = _even([p.z_diff for p in cuts], cuts)
    return {"source": "tools/p4e.py --references, before any P4-E run: the even part (X(s + d) + X(s - d))/2 - X(s) of "
                      "p4b_ms90's 60 mm coupled section with its gap moved by d, one fine cell, at n 2 and 3, of Zdiff "
                      "and of Sdd21 at the marker (the even/odd 4-port of its modes at 90 ohm), on each n's and rule's "
                      "own mesh lines (fit2d's coupled cut and its modes) and on the exact cut",
            "model_even": model, "exact": exact, "code": p0.code_id(), "versions": p0.versions()}


def _board(step: str) -> tuple[str, str]:
    """The board and tag of the step `step`: BASE for "base" and, tagged "rep", "repeat"; NULL for "null"; VICTIM for
    "vbase"; BOARDS[p4.N]'s for shift, gapp, gapm and vshift. KeyError for another step."""
    fixed = {"base": (BASE, ""), "repeat": (BASE, "rep"), "null": (NULL, ""), "vbase": (VICTIM, "")}
    return fixed[step] if step in fixed else (BOARDS[p4.N][step], "")


def _name(step: str) -> str:
    """The project of the step `step` at p4.N, p4.RULE and p4.DIELECTRIC."""
    board, tag = _board(step)
    return p4.name(board, tag=tag)


def step(out: Path, name: str) -> dict | None:
    """The step `name` of STEPS: p4's run step on its board's project (_board) at p4.N, p4.RULE and p4.DIELECTRIC, so
    p0.step returns P4-B's or P4-C's record for "base", and P4-B's victim record for "vbase", when its key is the same.
    "null" returns None without a run when null_equal holds. KeyError for another name."""
    board, tag = _board(name)
    if name == "null" and null_equal(out):
        print("p4e: the null edit's spec hash is the base's, so it does not run", flush=True)
        return None
    return p4.run_step(out, p4.project(out, board, tag=tag)[0])


def measure(out: Path) -> dict:
    """P4-E's measurements in <out>, in this process: "key", f"{p4.N}-{p4.RULE}", the references' model_even entry;
    "runs", p4.measure of each recorded step of STEPS by its name; "pairs", {step: p4.deltas of the base's run against
    its run} for repeat, shift, gapp, gapm and null, and "vshift", p4.deltas(vbase, vshift) (both hold the victim, so
    their fingerprints agree and the rows include next and fext), each only when both readings are there;
    "null_equal"; "invalid", the recorded steps whose run is not valid."""
    runs = {s: x for s in STEPS if (x := p4.measure(out, _name(s))) is not None}

    def deltas(a: str, b: str) -> list[dict] | None:
        x, y = runs.get(a), runs.get(b)
        return p4.deltas(x, y) if x and y and x["reading"] and y["reading"] else None

    pairs = {s: deltas("base", s) for s in ("repeat", "shift", "gapp", "gapm", "null")} | {
        "vshift": deltas("vbase", "vshift")}
    return {"key": f"{p4.N}-{p4.RULE}", "runs": runs, "pairs": {s: r for s, r in pairs.items() if r is not None},
            "null_equal": null_equal(out), "invalid": [s for s, x in runs.items() if not x["valid"]]}


def decide(m: dict, refs: dict) -> dict:
    """P4-E's thresholds and verdict (design 5.8; E-1, E-2) on the measures `m` (measure's shape) against `refs` (the
    references' shape): noise of m's pairs at refs' model_even for m's key, then thresholds. The verdict: "fail" on an
    invalid run, each "<step>: valid"; else "incomplete" while a pair of repeat, shift, gapp, gapm and vshift is
    missing, or the null's when its spec hash is not the base's; else "pass" when every constant is kept, else
    "widened", the design's fallback being that rule itself. Returns {"noise", "thresholds", "verdict": {"value",
    "fails"}}."""
    n = noise(m["pairs"], refs["model_even"][m["key"]])
    t = thresholds(n)
    fails = [f"{s}: valid" for s in m["invalid"]]
    needed = ("repeat", "shift", "gapp", "gapm", "vshift") + (() if m["null_equal"] else ("null",))
    if fails:
        value = "fail"
    elif any(s not in m["pairs"] for s in needed):
        value = "incomplete"
    else:
        value = "pass" if all(t["kept"].values()) else "widened"
    return {"noise": n, "thresholds": t, "verdict": {"value": value, "fails": fails}}


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), by p0.table: P4E-1 the noise per key (each pair's Δ, the
    gap's even and odd parts, the mesh model's and the exact cut's even parts, the key's noise); P4E-2 the thresholds
    per constant (its design value, noise, kept and threshold, with SE_OHM), then the verdict; P4E-3 the runs: cells,
    pool, t_stop, predicted to t_stop and to T_max, wall, valid."""
    c, n, t, verdict = result["criteria"], result["noise"], result["thresholds"], result["verdict"]
    exact = result["references"]["exact"][str(result["n_now"])]
    parts = [{"key": k, **x, "exact_even": exact.get(k)} for k, x in n["parts"].items()]
    constants = [{"constant": k, "design": d, "noise": n[k], "kept": t["kept"][k], "threshold": t[k]}
                 for k, d in c["design"].items()] + [{"constant": "SE_OHM", "threshold": t["SE_OHM"]}]
    items = [*({"item": k, "value": result[k]} for k in ("key", "null_equal")),
             {"item": "verdict", "value": verdict["value"]},
             {"item": "fails", "value": ", ".join(verdict["fails"]) or "none"}]
    keys = "; ".join(f"{k}: {', '.join(v)}" for k, v in c["constants"].items())
    steps = ", ".join(f"{k} {v:g}" for k, v in c["steps"].items())
    return "\n\n".join([
        "## P4E-1 The noise",
        f"At mesh n {result['n_now']}, the rule {result['rule_now']} and {result['dielectric_now']}, each pair's "
        "deltas (variant − base, as compare reads them) by key: repeat, the same run twice; shift, the whole board "
        "moved one fine cell along x and y; null, its track split into collinear pieces, run only when its spec hash "
        "is not the base's "
        "(null_equal); vshift, the terminated-victim coupon moved one fine cell against its own base, which alone "
        "holds next and fext; even and odd, (Δ+d ± Δ−d)/2 of the gap moved ± d. model_even, the mesh model's even "
        "part: fit2d's coupled Zdiff and the even/odd 4-port of its modes on the run's own mesh lines, the skew and "
        "Scd21 0 by the pair's symmetry; exact_even, the exact cut's, recorded. A key's noise is the largest |Δ| of "
        "repeat, shift, null and vshift and |even − model_even| where a model holds; a dB row whose two levels both "
        f"lie at or under {c['floor_db']:g} dB counts in no term.",
        p0.table(parts, ["key", "repeat", "shift", "null", "vshift", "even", "model_even", "exact_even", "odd",
                         "noise"]),
        "## P4E-2 The thresholds",
        f"A constant's noise is the largest of its keys' ({keys}). Its design value is kept when that noise lies under "
        f"a third of it; else it becomes {c['factor']:g} times the noise, rounded up to its step ({steps}). SE_OHM = "
        "DIFF_OHM/2, unmeasured on a pair. pass: every constant kept; widened: one is not; incomplete: a pair is "
        "missing; fail: a run is not valid.",
        p0.table(constants, ["constant", "design", "noise", "kept", "threshold"]),
        p0.table(items, ["item", "value"]),
        "## P4E-3 Runs",
        p0.table([{"step": k, **x} for k, x in result["runs"].items()],
                 ["step", "cells", "pool", "t_stop_s", "predicted_s", "worst_s", "wall_s", "valid"])]) + "\n"


def write(out: Path) -> dict:
    """p4.records over the recorded steps first (SystemExit on two product codes), then measure and decide of <out>:
    <out>/p4e/p4e.json through p0.save, with the versions, CRITERIA, the references, the calibration
    (p3.calibration), n_now, rule_now and dielectric_now, measure's key, null_equal, pairs and invalid, "runs", each
    recorded step's p4.plain, decide's noise, thresholds (which P4-F reads) and verdict, and the steps' machine time
    (p0.machine); p4e.md beside it (tables). Returns the JSON as saved."""
    recs = p4.records(out, [p3.step_id(_name(s), "run", "p4") for s in STEPS])
    refs, m = json.loads(REFERENCES.read_text(encoding="utf-8")), measure(out)
    result = p0.save(out / "p4e" / "p4e.json", {
        "gate": "P4-E", "versions": p0.versions(), "criteria": CRITERIA, "references": refs,
        "calibration": p3.calibration(), "n_now": p4.N, "rule_now": p4.RULE, "dielectric_now": p4.DIELECTRIC,
        "key": m["key"], "null_equal": m["null_equal"], "pairs": m["pairs"], "invalid": m["invalid"],
        "runs": {s: p4.plain(x) for s, x in m["runs"].items()}, **decide(m, refs), "machine": p0.machine(recs)})
    (out / "p4e" / "p4e.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p4e.py --references: writes REFERENCES through p0.save, SystemExit when it exists. python
    tools/p4e.py --out DIR [--steps a,b]: enters <GATES> (p4.enter); with --steps, runs each of them in order
    (p4.run_steps) and returns 1 when one raised, else 0; without, writes the report and returns 0."""
    parser = argparse.ArgumentParser(prog="p4e", description="P4-E, the noise floor (Stage 4 design 5.8, 5.11).")
    parser.add_argument("--out", help="<GATES>, outside every git work tree")
    parser.add_argument("--steps", help=f"comma-separated steps of {', '.join(STEPS)}; without it, the report")
    parser.add_argument("--references", action="store_true", help="write the references once, before any run")
    args = parser.parse_args(argv)
    if args.references:
        if REFERENCES.exists():
            raise SystemExit("P4-E's references are committed once, before its runs, and never regenerated")
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
