# SPDX-License-Identifier: GPL-3.0-or-later
"""P3-D, the noise floor, and P3-E, the positive control (Stage 3 design 5.11), on the pi variant ifa2g4_pi and its
variant boards, each run, retuned to plan 3's snapped values and verified, with P3-C's defaults applied: the pairs
through antenna_result and deltas, the thresholds that compare then uses, and p3d.json/p3d.md and p3e.json/p3e.md in
<out>. Run: python tools/p3d.py --out DIR [--steps ...]."""
import argparse
import json
import math
import sys
from functools import partial
from pathlib import Path

import numpy as np

import p0
import p3
import p3a
import p3c
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.antenna import deltas
from kicad_rf_studio.core.project import load_project, save_project

CRITERIA = json.loads((p0.FIX / "p3d" / "criteria.json").read_text(encoding="utf-8"))  # committed before any run
BOARDS = ("ifa2g4_pi", "ifa2g4_pi_shift", "ifa2g4_pi_dxp", "ifa2g4_pi_dxm")  # the base, the whole shift, ± d
POUR = "ifa2g4_pi_pour"  # P3-E's ground pour inside the antenna's clearance
# the re-searched values (Task 11 Step 2) and the refined mesh n (Task 11 Step 5), each set only on its pre-registered
# branch, a recorded deviation; None: criteria's values and P3-C's mesh n
VALUES: list[str] | None = None
REFINE: int | None = None
JUDGED = ("repeat", "shift", "dxp", "dxm")  # the pairs P3-D judges; dxp_dxm, +d against -d, is reported only
MARKERS = ("f_lo", "f0", "f_hi")  # the band's markers, in deltas' order
RUN_COLUMNS = ["step", "pool", "cells", "split", "speeds_mcs", "cal_mcs", "predicted_s", "worst_s", "wall_s"]


def project_name(board: str) -> str:
    """The project of the board `board`: d-<board>, r-<board> on the refined branch (REFINE)."""
    return f"{'r' if REFINE else 'd'}-{board}"


def _repeat() -> str:
    """The repeat's project: a copy of the base's (copy_project), verified a second time."""
    return project_name(BOARDS[0]) + "-rep"


def configure(out: Path, board: str) -> Path:
    """p3.variant of the board `board` (a moved board's regenerated <board>_r under REFINE) as project_name(board), with
    the edits_2g4 decisions of <out>/p3c/p3c.json (SystemExit "run P3-C first" without it) and, under REFINE, mesh.n
    REFINE with gates.fit2d_limit at ruling 2's raise (p3c's fit2d_raised). Returns the project file."""
    path = out / "p3c" / "p3c.json"
    if not path.is_file():
        raise SystemExit(f"p3d: no {path}; run P3-C first")
    edits = json.loads(path.read_text(encoding="utf-8"))["decisions"]["edits_2g4"]
    if REFINE:
        edits = {**edits, "mesh.n": REFINE, "gates.fit2d_limit": p3c.CRITERIA["fit2d_raised"]}
    return p3.variant(out, project_name(board), f"{board}_r" if REFINE and board in BOARDS[1:] else board, edits)


def copy_project(out: Path, source: str, name: str) -> Path:
    """The project `name`, made once as the project `source`'s project.json without its verify, results kept (both
    folders sit in <out>/projects, so its board path stands). Returns its project file."""
    pj = p3.project_path(out, name)
    if not pj.is_file():
        pj.parent.mkdir(parents=True, exist_ok=True)
        save_project(pj, {k: v for k, v in load_project(p3.project_path(out, source)).items() if k != "verify"})
    return pj


def _retune(pj: Path, values: list[str]) -> None:
    """`retune` of the project `pj` to `values` through the product's CLI; RuntimeError naming its exit code and last
    line on a non-zero exit."""
    code, text = p0.cli("retune", str(pj), *values)
    if code:
        raise RuntimeError(f"p3d: retune exited {code}: {(text.strip().splitlines() or [''])[-1]}")


def run(out: Path, board: str) -> None:
    """The board `board`'s steps in <out> (<GATES>): configure, its run (p3.run_step), retune to VALUES or criteria's
    values, then its verify. For the base, ifa2g4_pi, the repeat is copied once right after its first retune
    (copy_project) and retuned to the same values every time, so the two always hold one set, and verified after the
    base: r3 Q1's same run twice, one verify job, not a second run."""
    pj, name, values = configure(out, board), project_name(board), VALUES or CRITERIA["values"]
    p3.run_step(out, name)
    _retune(pj, values)
    if board == BOARDS[0]:
        _retune(copy_project(out, name, _repeat()), values)
    p3.run_step(out, name, "verify")
    if board == BOARDS[0]:
        p3.run_step(out, _repeat(), "verify")


def pair(base: Path, variant: Path) -> dict:
    """The deltas of the project `variant` against `base`, each pipeline.antenna_result (KrsError when either has no
    current result), through deltas on the base's band grid: {"f0_hz"; "df_rel", the resonance row's shift in MHz over
    f0 in MHz (None without a dip on either); "deta_tot_db", the three eta_tot rows' (f_lo, f0, f_hi); "deta_rad_db",
    10·log10(η_rad,v/η_rad,b) at the recorded frequencies nearest those; "dgain_db", the peak_gain row's; "dd_db", ΔD
    in dB at f0; "dbw_mhz", the -10 dB bandwidth row's; "ds11_max", the largest |ΔS11| over [f_lo, f_hi]; "depth_db",
    each lowest |S11| in dB}. The far-field ones None without both far fields. Python floats."""
    b, v = pipeline.antenna_result(base), pipeline.antenna_result(variant)
    project, f = b["project"], b["f"]
    f0, lo, hi = project["f0_hz"], project["band"]["f_lo_hz"], project["band"]["f_hi_hz"]
    rows = {}
    for r in deltas(project, f, (b["s11"], b["far"]), (v["s11"], v["far"])):
        rows.setdefault(r["quantity"], []).append(r["delta"])

    def at(x: dict, hz: float) -> int:  # x's recorded frequency nearest hz, as deltas reads η_tot
        return int(np.abs(x["far"]["sphere"].f - hz).argmin())

    eta_rad = d_db = None
    if b["far"] and v["far"]:
        eta_rad = [float(10 * np.log10(v["far"]["eff"]["eta_rad"][at(v, hz)] / b["far"]["eff"]["eta_rad"][at(b, hz)]))
                   for hz in (lo, f0, hi)]
        d_db = float(10 * np.log10(v["far"]["sphere"].d_max[at(v, f0)] / b["far"]["sphere"].d_max[at(b, f0)]))
    (res,), (bw,) = rows["resonance"], rows["bandwidth_10db"]
    return {"f0_hz": f0, "df_rel": None if res is None else res / (f0 / 1e6), "deta_tot_db": rows.get("eta_tot"),
            "deta_rad_db": eta_rad, "dgain_db": rows.get("peak_gain", [None])[0], "dd_db": d_db, "dbw_mhz": bw,
            "ds11_max": float(np.abs(v["s11"] - b["s11"])[(f >= lo) & (f <= hi)].max()),
            "depth_db": [float(20 * np.log10(np.abs(s).min())) for s in (b["s11"], v["s11"])]}


def thresholds(noise: dict) -> dict:
    """Ruling 10's thresholds from decide_d's `noise`: "shift_rel" and "db", max(the design's default, factor × the
    f_rel and db noise), each rounded up to shift_step_rel and db_step; "bw_rel" (BW_LIMIT), factor × the bw_rel
    noise rounded up to shift_step_rel when that exceeds shift_rel, else None (the bandwidth judged by shift_rel). A
    None noise gives a None threshold."""
    c = CRITERIA

    def up(x: float | None, floor: float, step: float) -> float | None:  # round(): float noise costs no step
        return None if x is None else round(math.ceil(round(max(floor, c["factor"] * x) / step, 9)) * step, 6)

    # ponytail: two ±d moves are a thin sample; their maximum is the conservative statistic (r3 Q5)
    shift = up(noise["f_rel"], c["default_shift_rel"], c["shift_step_rel"])
    bw = up(noise["bw_rel"], 0.0, c["shift_step_rel"])
    return {"shift_rel": shift, "db": up(noise["db"], c["default_db"], c["db_step"]),
            "bw_rel": bw if None not in (bw, shift) and bw > shift else None}


def _quantities(p: dict) -> dict:
    """The pair `p`'s compared quantities by name: f_rel, η_tot and η_rad at each marker in dB, the peak gain and D in
    dB; None where it lacks one."""
    tot, rad = p["deta_tot_db"] or [None] * 3, p["deta_rad_db"] or [None] * 3
    return {"f_rel": p["df_rel"], **{f"eta_tot_{m}_db": x for m, x in zip(MARKERS, tot)},
            **{f"eta_rad_{m}_db": x for m, x in zip(MARKERS, rad)}, "gain_db": p["dgain_db"], "d_db": p["dd_db"]}


def _largest(values) -> float | None:
    """The largest |x| among `values`, None left out; None when none is left."""
    return max((abs(x) for x in values if x is not None), default=None)


def _within(x: float | None, limit: float) -> bool:
    """|x| at most `limit`; None fails."""
    return x is not None and abs(x) <= limit


def _conditioned(p: dict) -> bool:
    """The pair `p`'s dips are both conditioned: each lowest |S11| at or below conditioned_db and inside the grid
    (deltas' dip_resonance, which df_rel needs on both sides)."""
    return p["df_rel"] is not None and max(p["depth_db"]) <= CRITERIA["conditioned_db"]


def _moved(p: dict) -> bool:
    """A ±d pair within P3-D's move limits: |df_rel| within move_f_res_rel and every |Δη_tot|, |Δη_rad| within
    move_eta_db."""
    q = _quantities(p)
    return _within(q["f_rel"], CRITERIA["move_f_res_rel"]) and all(
        _within(x, CRITERIA["move_eta_db"]) for k, x in q.items() if k.startswith("eta_"))


def decide_d(pairs: dict[str, dict | None]) -> dict:
    """P3-D (design 5.11) on `pairs`, pair's dicts by name, None for one not verified yet: JUDGED's repeat, shift, dxp
    and dxm (the base against the repeat, the shift, +d and -d); any other, dxp_dxm (+d against -d), is reported only.
    "noise" over the judged pairs present: "f_rel" the largest |df_rel|, "db" the largest |Δ| over η_tot, η_rad, the
    peak gain and D, "bw_rel" the largest |dbw_mhz| over f0 in MHz, "depth_db" the largest |Δdepth|, "ds11" the largest
    ds11_max. "odd_even", given dxp and dxm, for f_rel and each dB quantity (_quantities): ((Δ+ − Δ−)/2, (Δ+ + Δ−)/2),
    the odd part the position's slope × d, the even one discretization and curvature; "position_bound" |odd| >
    2·|even| on f_rel. "screen": "depth_noise_db", "margin_db" the smallest (conditioned_db − depth) over every
    compared dip, "kept" margin > factor × the depth noise. A pair fails unconditioned (_conditioned), and dxp and dxm
    outside the move limits (_moved). "shift_rel", "db" and "bw_rel" from thresholds once every judged pair is present
    and conditioned, on a pass and a fail alike, else None (an unconditioned pair stops for a ruling). "verdict":
    {"value": "fail" when a pair fails, else "incomplete" while one is missing, else "pass"; "fails", those failed}."""
    c = CRITERIA
    ps = {name: pairs.get(name) for name in JUDGED}
    there = [p for p in ps.values() if p is not None]
    qs = [_quantities(p) for p in there]
    noise = {"f_rel": _largest(q["f_rel"] for q in qs),
             "db": _largest(x for q in qs for k, x in q.items() if k != "f_rel"),
             "bw_rel": _largest(None if p["dbw_mhz"] is None else p["dbw_mhz"] / (p["f0_hz"] / 1e6) for p in there),
             "depth_db": _largest(p["depth_db"][1] - p["depth_db"][0] for p in there),
             "ds11": _largest(p["ds11_max"] for p in there)}
    plus, minus = (ps[k] and _quantities(ps[k]) for k in ("dxp", "dxm"))
    odd_even = plus and minus and {k: None if None in (a, minus[k]) else ((a - minus[k]) / 2, (a + minus[k]) / 2)
                                   for k, a in plus.items()}
    f = odd_even and odd_even["f_rel"]
    margin = min((c["conditioned_db"] - x for p in there for x in p["depth_db"]), default=None)
    fails = [k for k, p in ps.items()
             if p is not None and not (_conditioned(p) and (k in ("repeat", "shift") or _moved(p)))]
    judged = None not in ps.values() and all(map(_conditioned, there))
    return {"pairs": pairs, "noise": noise, "odd_even": odd_even, "position_bound": f and abs(f[0]) > 2 * abs(f[1]),
            "screen": {"depth_noise_db": noise["depth_db"], "margin_db": margin,
                       "kept": None if margin is None else margin > c["factor"] * noise["depth_db"]},
            **(thresholds(noise) if judged else dict.fromkeys(("shift_rel", "db", "bw_rel"))),
            "verdict": {"value": "fail" if fails else "pass" if judged else "incomplete", "fails": fails}}


def decide_e(p: dict | None, shift_rel: float | None, db: float | None) -> dict:
    """P3-E (design 5.11) on the pour's pair `p` at P3-D's thresholds `shift_rel` and `db`: "resolved" |df_rel| >
    shift_rel, strictly, as deltas resolves; "ratio" |df_rel|/shift_rel; "sign" "as expected" when df_rel has
    pour_sign's sign, else "opposite" (soft: reported, never a fail); "conditioned" (_conditioned); "resolved_db"
    whether each dB quantity's |Δ| exceeds `db`, reported; "pass" resolved and conditioned. Each None, not judged,
    without the pair or P3-D's shift_rel."""
    if p is None or shift_rel is None:
        return {"pair": p, **dict.fromkeys(("resolved", "ratio", "sign", "conditioned", "resolved_db", "pass"))}
    f, conditioned = p["df_rel"], _conditioned(p)
    resolved = f is not None and abs(f) > shift_rel
    return {"pair": p, "resolved": resolved, "ratio": None if f is None else abs(f) / shift_rel,
            "sign": None if f is None else "as expected" if f * CRITERIA["pour_sign"] > 0 else "opposite",
            "conditioned": conditioned,
            "resolved_db": {k: None if None in (x, db) else abs(x) > db for k, x in _quantities(p).items()
                            if k != "f_rel"},
            "pass": resolved and conditioned}


def _steps() -> list[tuple[str, str]]:
    """The gate's steps as (project, command): the base's run and verify, the repeat's verify, then each other
    board's and the pour's run and verify."""
    first = project_name(BOARDS[0])
    return [(first, "run"), (first, "verify"), (_repeat(), "verify"),
            *((project_name(board), command) for board in (*BOARDS[1:], POUR) for command in ("run", "verify"))]


def _run_rows(runs: dict) -> list[dict]:
    """The rows of RUN_COLUMNS of `runs`, each step's measurements by its id."""
    return [{**{k: p3a._cell(x.get(k)) for k in RUN_COLUMNS}, "step": sid} for sid, x in runs.items()]


def tables_d(result: dict) -> str:
    """The Markdown tables of P3-D's JSON `result` (write's), with p0.table, cells by p3a._cell: P3D-1 each pair's
    deltas with its verdict, then the odd and even parts of the ±d pairs; P3D-2 the noise, the thresholds with their
    rules, BW_LIMIT's need with the depth it was measured on, the -6 dB screen, the largest |ΔS11| against verify's,
    the position bound and the verdict; P3D-3 each step's machine time."""
    c, cell, v, pairs = result["criteria"], p3a._cell, result["verdict"], result["pairs"]
    rows = [{**{k: cell(x) for k, x in (p or {}).items()}, "pair": name,
             "verdict": "report only" if name not in JUDGED else "missing" if p is None
             else "fail" if name in v["fails"] else "pass"} for name, p in pairs.items()]
    parts = [{"quantity": k, "odd": x and x[0], "even": x and x[1]} for k, x in (result["odd_even"] or {}).items()]
    depth = next((p["depth_db"][0] for name, p in pairs.items() if name in JUDGED and p), None)  # the base's dip
    rules = [
        ("noise", cell(result["noise"]), "the largest delta magnitude over repeat, shift, dxp and dxm: f_rel a "
                                         "fraction of f0; db over η_tot, η_rad, the peak gain and D; bw_rel the -10 dB "
                                         "bandwidth's over f0; depth_db the dips'; ds11 the largest ΔS11 in band"),
        ("shift_rel", cell(result["shift_rel"]), f"max({c['default_shift_rel']:g}, {c['factor']:g} × the f_rel noise), "
                                                 f"rounded up to {c['shift_step_rel']:g}"),
        ("db", cell(result["db"]), f"max({c['default_db']:g} dB, {c['factor']:g} × the db noise), rounded up to "
                                   f"{c['db_step']:g} dB"),
        ("bw_rel", cell(result["bw_rel"]), f"BW_LIMIT: {c['factor']:g} × the bw_rel noise, rounded up to "
                                           f"{c['shift_step_rel']:g}, only when above shift_rel, else the bandwidth "
                                           f"is judged by shift_rel; measured on the base's dip at {cell(depth)} dB"),
        ("screen", cell(result["screen"]), f"the {c['conditioned_db']:g} dB screen is kept unless a compared dip lies "
                                           f"within {c['factor']:g} × the depth noise of it"),
        ("ds11", cell(result["noise"]["ds11"]), "the largest ΔS11 magnitude in band against verify's 0.0076 at f0 and "
                                                "0.0149 at most (plan 3's matching run)"),
        ("position_bound", cell(result["position_bound"]),
         "the odd part over twice the even part on f_rel: then the thresholds rest on sensitivity to position rather "
         "than noise, an owner item (thresholds from the repeat, the shift and the even parts, or a mesh-only probe)"),
        ("verdict", f"{v['value']}; fails {cell(v['fails'])}",
         f"dxp and dxm within {c['move_f_res_rel']:g} of f0 and {c['move_eta_db']:g} dB in η_tot and η_rad; every "
         f"pair conditioned at {c['conditioned_db']:g} dB, else a fail that stops for a ruling")]
    return "\n\n".join([
        "## P3D-1 Pairs\n\n" + p0.table(rows, ["pair", "df_rel", "deta_tot_db", "deta_rad_db", "dgain_db", "dd_db",
                                                "dbw_mhz", "ds11_max", "depth_db", "verdict"])
        + "\n\nThe ±d pairs' odd part (Δ+ − Δ−)/2, the position's slope × d, and even part (Δ+ + Δ−)/2, "
          "discretization and curvature:\n\n" + p0.table(parts, ["quantity", "odd", "even"]),
        "## P3D-2 Noise and thresholds\n\n" + p0.table([dict(zip(("item", "value", "rule"), r)) for r in rules],
                                                       ["item", "value", "rule"])
        + f"\n\nDeviations: p3d.VALUES {cell(result['values'])}, p3d.REFINE {cell(result['refine'])} (– is the "
          "pre-registered: criteria's values, P3-C's mesh n).",
        "## P3D-3 Runs\n\n" + p0.table(_run_rows(result["runs"]), RUN_COLUMNS)]) + "\n"


def tables_e(result: dict) -> str:
    """The Markdown tables of P3-E's JSON `result` (write's): P3E-1 its pair and decide_e at P3-D's thresholds, each
    with its rule; P3E-2 its steps' machine time."""
    c, cell, t = result["criteria"], p3a._cell, result["thresholds"]
    rules = [("pair", cell(result["pair"]), "the pour against the base, both verified at the same values"),
             ("resolved", cell(result["resolved"]), f"the shift's magnitude over shift_rel {cell(t['shift_rel'])}, "
                                                    f"strictly; ratio {cell(result['ratio'])}"),
             ("sign", cell(result["sign"]), f"as expected when df_rel has the sign of {c['pour_sign']:+d} (soft: "
                                            "reported, never a fail)"),
             ("conditioned", cell(result["conditioned"]), f"both dips at or below {c['conditioned_db']:g} dB inside "
                                                          "the grid"),
             ("resolved_db", cell(result["resolved_db"]), f"each dB delta over db {cell(t['db'])}, reported"),
             ("pass", cell(result["pass"]), "resolved and conditioned; – while P3-D sets no thresholds or the pour "
                                            "is not verified")]
    return "\n\n".join([
        "## P3E-1 The ground pour\n\n" + p0.table([dict(zip(("item", "value", "rule"), r)) for r in rules],
                                                  ["item", "value", "rule"]),
        "## P3E-2 Runs\n\n" + p0.table(_run_rows(result["runs"]), RUN_COLUMNS)]) + "\n"


def write(out: Path) -> dict:
    """p3.records over the recorded steps first (SystemExit on two product codes), then the pairs (pair; None while
    either side has no current verify) and decide_d of <out>: <out>/p3d/p3d.json through p0.save, with the versions,
    CRITERIA, VALUES and REFINE (the deviations), this machine's calibration (p3.calibration), decide_d's result, "runs"
    (each recorded step's p3.measure but the pour's, without f_hz and s11) and their machine time (p0.machine); p3d.md
    beside it. With the pour's verify recorded, <out>/p3e/p3e.json likewise, with P3-D's "thresholds", decide_e of the
    base against the pour at them and the pour's runs; p3e.md beside it. Returns P3-D's JSON as saved."""
    ids = {p3.step_id(*s): s for s in _steps()}
    recs = p3.records(out, list(ids))
    runs = {sid: {k: x for k, x in m.items() if k not in ("f_hz", "s11")}
            for sid, s in ids.items() if (m := p3.measure(out, *s)) is not None}

    def paired(a: str, b: str) -> dict | None:
        try:
            return pair(p3.project_path(out, a), p3.project_path(out, b))
        except KrsError:  # E_COMPARE_NO_RESULT: not verified at its current values yet, or its project not made
            return None

    base, (shift, dxp, dxm), pour = project_name(BOARDS[0]), map(project_name, BOARDS[1:]), project_name(POUR)
    d = decide_d({"repeat": paired(base, _repeat()), "shift": paired(base, shift), "dxp": paired(base, dxp),
                  "dxm": paired(base, dxm), "dxp_dxm": paired(dxp, dxm)})
    head = {"versions": p0.versions(), "criteria": CRITERIA, "values": VALUES, "refine": REFINE,
            "calibration": p3.calibration()}
    e_ids = [p3.step_id(pour, command) for command in ("run", "verify")]
    result = p0.save(out / "p3d" / "p3d.json", {
        "gate": "P3-D", **head, **d, "runs": {k: x for k, x in runs.items() if k not in e_ids},
        "machine": p0.machine([r for r in recs if r["step"] not in e_ids])})
    (out / "p3d" / "p3d.md").write_text(tables_d(result), encoding="utf-8")
    if e_ids[1] in runs:
        e = p0.save(out / "p3e" / "p3e.json", {
            "gate": "P3-E", **head, "thresholds": {k: d[k] for k in ("shift_rel", "db")},
            **decide_e(paired(base, pour), d["shift_rel"], d["db"]), "runs": {k: runs[k] for k in e_ids if k in runs},
            "machine": p0.machine([r for r in recs if r["step"] in e_ids])})
        (out / "p3e" / "p3e.md").write_text(tables_e(e), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p3d.py --out DIR [--steps a,b]: enters <GATES> (p3.enter) first; with --steps, runs each board's
    steps in order (p3.run_steps) and returns 1 when one raised, else 0; without, writes the gates and returns 0."""
    parser = argparse.ArgumentParser(prog="p3d", description="P3-D, the noise floor, and P3-E, the positive control "
                                                             "(Stage 3 design 5.11).")
    parser.add_argument("--out", required=True, help="<GATES>, outside every git work tree")
    parser.add_argument("--steps", help=f"comma-separated boards, of {', '.join((*BOARDS, POUR))}; without it, the "
                                        "reports")
    args = parser.parse_args(argv)
    out = p3.enter(Path(args.out))
    if args.steps:
        return p3.run_steps(args.steps.split(","), partial(run, out))
    write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
