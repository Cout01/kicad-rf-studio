# SPDX-License-Identifier: GPL-3.0-or-later
"""P4-B, the coupled coupons (Stage 4 design 5.11; plan 4 rulings B-1 to B-6): the 90 and 100 Ω microstrip pairs and
the coupled stripline at n 2 and n 3, the 45° twins at n 2 (n 3 for a twin that missed, with the owner's go), and the
terminated against the cut victim. Each is run through the product at the SI rule and lossless. Their Zdiff, NEXT and
FEXT are judged against the 2D solve of their own mesh lines in `tests/fixtures/p4b/references.json`, by
`criteria.json`, and p4b.json and p4b.md are written in <out>/p4b. Run: `python tools/p4b.py --out DIR
[--steps board-nK,...] [--references]`."""
import argparse
import json
import math
import sys
import tempfile
from functools import partial
from pathlib import Path

import numpy as np
import skrf as rf
from scipy.constants import c as C_0

import p0
import p3
import p4
from kicad_lines import coupled_microstrip  # tests/ is on sys.path through p4
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.cs2d import Pair, pair
from kicad_rf_studio.core.geometry.sections import cross_section
from kicad_rf_studio.core.mesh.gates import fit2d
from kicad_rf_studio.core.post.antenna import DELTA_COLUMNS
from kicad_rf_studio.core.post.si import Reading, arrival, compare_verify, db, si_deltas, uniform_grid
from p4a import cohn, even_odd_s

CRITERIA = json.loads((p0.FIX / "p4b" / "criteria.json").read_text(encoding="utf-8"))  # committed before any run
REFERENCES = p0.FIX / "p4b" / "references.json"  # written once by --references, committed before any run
COUPONS = ("p4b_ms90", "p4b_ms100", "p4b_sl90")
BENDS = {"p4b_ms90_45": "p4b_ms90", "p4b_ms100_45": "p4b_ms100"}  # each 45° twin and its straight twin
VICTIM = ("p4b_ms90_vic", "p4b_ms90_cut")  # p4b_ms90's pair with the victim terminated, and with it cut
REF_OF = {**{c: c for c in COUPONS}, **BENDS, **dict.fromkeys(VICTIM, "p4b_ms90")}  # each board's references' coupon
# ponytail: Task 3's legs (width, gap in mm) written again, as make_fixtures imports pcbnew; read them from the boards
# if a coupon changes
LEGS = {"p4b_ms90": (0.3, 0.25), "p4b_ms100": (0.25, 0.28), "p4b_sl90": (0.18, 0.25)}
COUPLED_MM = 60.0  # the coupled run's length
F = uniform_grid(10e9)  # the references' grid: the presets' band from DC


def next_peak(s: np.ndarray, f: np.ndarray, f_q: float, lobe: float = 2.0) -> tuple[float, float]:
    """NEXT on its first lobe (ruling B-3): the highest db(s[:, 1, 0]), P near to N near, over 0 < f ≤ lobe·f_q (Hz),
    and its f, as Python floats."""
    band = (f > 0) & (f <= lobe * f_q)
    d = db(s[band, 1, 0])
    k = int(np.argmax(d))
    return float(d[k]), float(f[band][k])


def fext_db(s: np.ndarray, f: np.ndarray, z: float, f_hi: float | None = None) -> float:
    """FEXT's peak in dB (ruling B-3): db of S[:, 3, 0], P near to N far, over 0 < f ≤ `f_hi` (Hz; the whole grid when
    None), after every port of a copy of `s` is renormalised from 50 Ω to `z` (scikit-rf's Network.renormalize)."""
    net = rf.Network(frequency=rf.Frequency.from_f(f, unit="Hz"), s=s.copy(), z0=50.0, s_def="power")
    net.renormalize(z)
    band = (f > 0) & (f <= (np.inf if f_hi is None else f_hi))
    return float(db(net.s[band, 3, 0]).max())


def victim(project: dict, vic: Reading, cut: Reading) -> dict:
    """The victim case (ruling B-5) of the terminated victim's reading `vic` (6 ports) against the cut one's `cut` (the
    pair's 4), on the victim's SI project dict `project`: {"rows": si_deltas(project, vic, cut), the pair's rows, as the
    cut has no victim; "ds_pair": the largest |vic.s − cut.s| above DC over the pair's own block; "next_db" and
    "fext_db": the victim's crosstalk peaks, from vic's own reading}. The two runs' fingerprints differ by design
    ("ends"), as compare refuses such runs, so it never goes through p4.deltas."""
    return {"rows": si_deltas(project, vic, cut), "ds_pair": float(np.abs(vic.s[1:, :4, :4] - cut.s[1:, :4, :4]).max()),
            "next_db": vic.xt[0][0], "fext_db": vic.xt[0][2]}


def _modes(p: Pair) -> dict:
    """The cs2d pair `p` as the references hold it: its z_even, eps_even, z_odd and eps_odd; "f_q_hz", the coupled run's
    quarter wave at their mean εeff; "next_db" and "next_hz", next_peak of their even/odd 4-port at 50 Ω on F;
    "z_ref", √(Ze·Zo)."""
    f_q = C_0 / (4 * COUPLED_MM * 1e-3 * math.sqrt((p.eps_even + p.eps_odd) / 2))
    s = even_odd_s(p.z_even, p.eps_even, p.z_odd, p.eps_odd, COUPLED_MM, F)
    next_db, next_hz = next_peak(s, F, f_q, CRITERIA["lobe"])
    return {"z_even": p.z_even, "eps_even": p.eps_even, "z_odd": p.z_odd, "eps_odd": p.eps_odd, "f_q_hz": f_q,
            "next_db": next_db, "next_hz": next_hz, "z_ref": math.sqrt(p.z_even * p.z_odd)}


def references() -> dict:
    """P4-B's references (G-1), computed in memory in a temporary folder, no openEMS: each coupon's base by `new` with
    P4_NEW (p4.base), then its project at mesh n 2 and 3, lossless at the SI rule (new's λ/40), loaded and built
    (pipeline.load, build_model) as its run builds it. Per coupon, its coupled run's first 60 mm section (the P leg's):
    - "fit2d", per n as a str: that section's coupled Fit from fit2d on the model's mesh ("z0_mesh", "z0_ref", "err"),
      with _modes of the pair fit2d solves on the mesh lines (the smeared cut);
    - "exact": _modes of cs2d's pair on the exact cut with the mask, its "z_diff", and "fext50_db", fext_db of its
      even/odd 4-port at 50 Ω over the whole grid;
    - recorded only: "kicad", the Zdiff of KiCad's calculator for a microstrip (B-2), "cohn", Cohn's zero-thickness
      modes for the stripline.
    Per bend, "t_mid_s": the round trip to its diagonal's centre, 2 + (1 − p) + 15 + 16.5 mm with p its twin's
    (w + s)/2, at its twin's exact εodd. Then "code" (p0.code_id()) and "versions"."""
    coupons = {}
    with tempfile.TemporaryDirectory() as folder:
        for c in COUPONS:
            fits = {}
            for n in (2, 3):
                pj = p4.project(Path(folder), c, n=n, rule="l40", dielectric="lossless")[1]
                project, board, geom, _ = pipeline.load(pj)
                mesh = pipeline.build_model(project, board, geom).mesh
                sec = next(s for s in geom.sections if round(s.length, 3) == COUPLED_MM)
                cut = partial(cross_section, sec, geom.pieces, geom.zs, geom.masks.get(sec.layer),
                              partners=geom.partners(sec.net))
                _, fit = [x for x in fit2d(geom, mesh) if x.section == sec]  # the leg's own Fit, then the coupled one
                on = pair(cut("smeared", mesh.dz0), mesh.y if sec.axis == "x" else mesh.x, mesh.z)
                fits[str(n)] = {"z0_mesh": fit.z0_mesh, "z0_ref": fit.z0_ref, "err": fit.err, **_modes(on)}
            exact = pair(cut("exact"))
            s = even_odd_s(exact.z_even, exact.eps_even, exact.z_odd, exact.eps_odd, COUPLED_MM, F)
            coupons[c] = {"fit2d": fits, "exact": {**_modes(exact), "z_diff": exact.z_diff,
                                                   "fext50_db": fext_db(s, F, 50.0)}}
            if c == "p4b_sl90":
                z_even, z_odd = cohn(*LEGS[c], 0.535, 4.3)
                coupons[c]["cohn"] = {"z_even": z_even, "z_odd": z_odd, "z_diff": 2 * z_odd}
            else:
                coupons[c]["kicad"] = {"z_diff": 2 * coupled_microstrip(*LEGS[c], 0.2, 0.035, 4.3)[2]}
    bends = {b: {"t_mid_s": 2 * (2 + (1 - sum(LEGS[t]) / 2) + 15 + 16.5) * 1e-3
                 * math.sqrt(coupons[t]["exact"]["eps_odd"]) / C_0} for b, t in BENDS.items()}
    return {"source": "tools/p4b.py --references, before any P4-B run: fit2d's coupled cut on each coupon's own mesh "
                      "at n 2 and 3, the exact cut, KiCad's calculator or Cohn, the bends' diagonal centres",
            "coupons": coupons, "bends": bends, "code": p0.code_id(), "versions": p0.versions()}


def step(out: Path, name: str) -> dict:
    """The step `name`, <board>-n<k> for a board of COUPONS, BENDS or VICTIM and k 2 or 3: p4's run step on the board's
    project at mesh n k, the SI rule ("l40") and lossless. KeyError for another name."""
    board, _, n = name.rpartition("-n")
    if board not in REF_OF or n not in ("2", "3"):
        raise KeyError(name)
    return p4.run_step(out, p4.project(out, board, n=int(n), rule="l40", dielectric="lossless")[0])


def _readings(r: Reading | None, ref: dict, t_mid: float | None) -> dict:
    """The readings of a step's Reading `r` at its coupon's fit2d references `ref` at its n, t_r = r.rise[0], each None
    without `r`: "plateau_ohm", p4.plateau from 2·t_r to t_far − 2·t_r (None without t_far); "level_ohm" for a bend,
    p4.plateau over t_r about its diagonal's centre `t_mid` (None for another board); "next_db", next_peak's dB on the
    first lobe; "fext_db", fext_db on that lobe at the modes' √(Ze·Zo); "fext_full_db", the same over the whole grid;
    "fext50_db", over the whole grid at 50 Ω; "launch_db", the largest db(S11)."""
    if r is None:
        return dict.fromkeys(("plateau_ohm", "level_ohm", "next_db", "fext_db", "fext_full_db", "fext50_db",
                              "launch_db"))
    t_r, f_q, lobe = r.rise[0], ref["f_q_hz"], CRITERIA["lobe"]
    return {"plateau_ohm": r.t_far and p4.plateau(r, 2 * t_r, r.t_far - 2 * t_r),
            "level_ohm": t_mid and p4.plateau(r, t_mid - t_r / 2, t_mid + t_r / 2),
            "next_db": next_peak(r.s, r.f, f_q, lobe)[0], "fext_db": fext_db(r.s, r.f, ref["z_ref"], lobe * f_q),
            "fext_full_db": fext_db(r.s, r.f, ref["z_ref"]), "fext50_db": fext_db(r.s, r.f, 50.0),
            "launch_db": float(db(r.s[:, 0, 0]).max())}


def measure(out: Path) -> dict:
    """P4-B's measurements in <out>, in this process. Per recorded step "<board>-n<k>" (step's), p4.measure of its
    project with "sigma" and "recip" from its indicators and _readings of its reading at REF_OF's coupon's
    fit2d[str(k)] references. On each coupon's n 3 row when both its runs read, recorded: "n_ds", compare_verify's
    largest |ΔS| of n 3 against n 2, and "n_delay_rel", |arrival₃/arrival₂ − 1| of their TDTs (None without both).
    Then "victim": victim() of the victim pair at p4.N when both its runs read, else None; "bends_n3": p4.BENDS_N3."""
    refs, m = json.loads(REFERENCES.read_text(encoding="utf-8")), {}
    for board, coupon in REF_OF.items():
        for n in (2, 3):
            row = p4.measure(out, p4.name(board, n, "l40", "lossless"))
            if row is not None:
                ref, t_mid = refs["coupons"][coupon]["fit2d"][str(n)], refs["bends"].get(board, {}).get("t_mid_s")
                m[f"{board}-n{n}"] = {**row, "sigma": row["indicators"]["sigma"], "recip": row["indicators"]["recip"],
                                      **_readings(row["reading"], ref, t_mid)}
    for c in COUPONS:
        a, b = (m.get(f"{c}-n{n}", {}).get("reading") for n in (2, 3))
        if a and b:
            t2, t3 = arrival(a.t, a.tdt), arrival(b.t, b.tdt)
            m[f"{c}-n3"] |= {"n_ds": compare_verify(a, b)["ds_max"],
                             "n_delay_rel": None if None in (t2, t3) else abs(t3 / t2 - 1)}
    vic, cut = (m.get(f"{b}-n{p4.N}", {}) for b in VICTIM)
    both = vic.get("reading") and cut.get("reading")
    return {**m, "victim": victim(vic["project"], vic["reading"], cut["reading"]) if both else None,
            "bends_n3": p4.BENDS_N3}


def _rel(a: float | None, b: float | None) -> float | None:
    """a/b − 1, None when either is None."""
    return None if a is None or b is None else a / b - 1


def decide(m: dict, refs: dict) -> dict:
    """P4-B's checks and decisions (design 5.11; B-1 to B-6) on the measures `m` against `refs` (the references' shape)
    by CRITERIA, each limit inclusive and a None value a fail:
    - "checks", per recorded coupon step at its n's fit2d references, {"step", "check", "value", "limit", "pass"}:
      zdiff, plateau/z0_mesh − 1 within zdiff_rel; next, next_db − the model's within next_db; fext, for the
      stripline, fext_db at most its limit; valid, the run's flag;
    - "decisions": "mesh_n", with e_k the plateau over its own mesh's z0_mesh, 3 when any coupon's |e₃/e₂ − 1|
      exceeds n_rel, 2 when every coupon's is within it, else None (one lacks either run or plateau); "staircase",
      each bend's level within bend_rel of its twin's plateau at the same n, a missing twin run (or plateau) leaving
      it undecided: "warn" when every bend passes at n 2; else, over the bends that missed, "refuse" when one fails or
      is blocked at n 3, "warn" or "n3" when all pass there and mesh_n is 3 or 2, "owner" when one lacks its n 3 run
      and bends_n3 is "declined", else None; "cut_victim", "refusal kept" when m["victim"] is not None, else None;
    - "verdict": {"value": "blocked" on a zdiff fail (a pipeline bug, design 5.11), else "fail" on another, else
      "incomplete" while a decision is None or a coupon step is missing, else "fallback" when mesh_n is 3 or staircase
      is "n3", "refuse" or "owner", else "pass"; "fails": "<step>: <check>", a zdiff fail with no plateau as
      "<step>: no reading"}."""
    c, checks = CRITERIA, []

    def ratio(board: str, n: int) -> float | None:  # the plateau over its own mesh's fit2d Zdiff
        p = m.get(f"{board}-n{n}", {}).get("plateau_ohm")
        return None if p is None else p / refs["coupons"][board]["fit2d"][str(n)]["z0_mesh"]

    for board in COUPONS:
        for n in (2, 3):
            if (row := m.get(step := f"{board}-n{n}")) is None:
                continue
            ref = refs["coupons"][board]["fit2d"][str(n)]
            e = _rel(row["plateau_ohm"], ref["z0_mesh"])
            dn = None if row["next_db"] is None else row["next_db"] - ref["next_db"]
            found = [("zdiff", e, c["zdiff_rel"], e is not None and abs(e) <= c["zdiff_rel"]),
                     ("next", dn, c["next_db"], dn is not None and abs(dn) <= c["next_db"])]
            if board == "p4b_sl90":
                x = row["fext_db"]
                found.append(("fext", x, c["fext_db"], x is not None and x <= c["fext_db"]))
            found.append(("valid", row["valid"], None, bool(row["valid"])))
            checks += [dict(zip(("step", "check", "value", "limit", "pass"), (step, *x))) for x in found]
    fails = [f"{x['step']}: " + ("no reading" if x["check"] == "zdiff" and x["value"] is None else x["check"])
             for x in checks if not x["pass"]]
    moves = [abs(e3 / e2 - 1) for e2, e3 in ((ratio(b, 2), ratio(b, 3)) for b in COUPONS) if None not in (e2, e3)]
    mesh_n = 3 if any(x > c["n_rel"] for x in moves) else 2 if len(moves) == len(COUPONS) else None

    def bend(b: str, n: int) -> bool | None:  # its level against its twin's plateau at n; None undecided
        row, twin = m.get(f"{b}-n{n}"), m.get(f"{BENDS[b]}-n{n}")
        if row is None or twin is None or twin["plateau_ohm"] is None:
            return None
        level = row["level_ohm"]
        return not row["blocked"] and level is not None and abs(level / twin["plateau_ohm"] - 1) <= c["bend_rel"]

    at2 = {b: bend(b, 2) for b in BENDS}
    at3 = [bend(b, 3) for b, ok in at2.items() if ok is False]  # the bends that missed at n 2
    if None in at2.values():
        staircase = None
    elif not at3:
        staircase = "warn"
    elif False in at3:
        staircase = "refuse"
    elif None not in at3:
        staircase = {3: "warn", 2: "n3"}.get(mesh_n)
    else:
        staircase = "owner" if m.get("bends_n3") == "declined" else None
    decisions = {"mesh_n": mesh_n, "staircase": staircase,
                 "cut_victim": None if m.get("victim") is None else "refusal kept"}
    if any(x["check"] == "zdiff" and not x["pass"] for x in checks):
        value = "blocked"
    elif fails:
        value = "fail"
    elif None in decisions.values() or any(f"{b}-n{n}" not in m for b in COUPONS for n in (2, 3)):
        value = "incomplete"
    elif mesh_n == 3 or staircase in ("n3", "refuse", "owner"):
        value = "fallback"
    else:
        value = "pass"
    return {"checks": checks, "decisions": decisions, "verdict": {"value": value, "fails": fails}}


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), by p0.table: P4B-1 the checks with their limit, value
    and pass; each coupon's n 2 against n 3 (its plateaus net of fit2d, the move judged, the raw move, fit2d's own
    move, each n against the exact cut, |ΔS| and the arrival); the readings recorded beside them (the exact cut, KiCad's
    calculator or Cohn, FEXT's full band and 50 Ω peak, the launch, a bend's level); the decisions and the verdict.
    P4B-2 the runs: cells, pool, t_stop, predicted to t_stop and to T_max, wall. P4B-3 the victim case, its two runs'
    fingerprints differing by design."""
    c, refs, rows, v = result["criteria"], result["references"]["coupons"], result["rows"], result["victim"]
    moves = []
    for k in COUPONS:
        r2, r3 = rows.get(f"{k}-n2", {}), rows.get(f"{k}-n3", {})
        a, b = r2.get("plateau_ohm"), r3.get("plateau_ohm")
        z2, z3, exact = refs[k]["fit2d"]["2"]["z0_mesh"], refs[k]["fit2d"]["3"]["z0_mesh"], refs[k]["exact"]["z_diff"]
        e2, e3 = _rel(a, z2), _rel(b, z3)
        moves.append({"coupon": k, "e_n2": e2, "e_n3": e3,
                      "move": None if None in (e2, e3) else abs(_rel(1 + e3, 1 + e2)), "raw": _rel(b, a),
                      "fit2d": _rel(z3, z2), "exact_n2": _rel(a, exact), "exact_n3": _rel(b, exact),
                      "ds_max": r3.get("n_ds"), "arrival": r3.get("n_delay_rel")})
    recorded = []
    for k, x in rows.items():
        ref = refs[REF_OF[k.rpartition("-n")[0]]]
        recorded.append({"step": k, "plateau_ohm": x["plateau_ohm"],
                         "exact": _rel(x["plateau_ohm"], ref["exact"]["z_diff"]),
                         "calculator_ohm": (ref.get("kicad") or ref["cohn"])["z_diff"],
                         **{q: x[q] for q in ("fext_full_db", "fext50_db", "launch_db", "level_ohm", "sigma",
                                              "recip")}})
    d, verdict = result["decisions"], result["verdict"]
    items = [*({"item": key, "value": value} for key, value in d.items()),
             {"item": "verdict", "value": verdict["value"]},
             {"item": "fails", "value": ", ".join(verdict["fails"]) or "none"}]
    victim_md = "Not run." if v is None else "\n\n".join([
        p0.table(v["rows"], list(DELTA_COLUMNS)),
        p0.table([{"item": key, "value": v[key]} for key in ("ds_pair", "next_db", "fext_db")], ["item", "value"])])
    return "\n\n".join([
        "## P4B-1 Checks",
        "zdiff: the plateau (the median of the localising differential TDR from 2 t_r to t_far − 2 t_r) over fit2d's "
        f"coupled Zdiff on the run's own mesh, less 1, within {c['zdiff_rel']:g}; a miss blocks, as a pipeline bug. "
        f"next: NEXT's peak over 0 < f ≤ {c['lobe']:g} f_q less the mesh modes' even/odd model's, within "
        f"{c['next_db']:g} dB. fext, the stripline: FEXT's peak over that band at the modes' √(Ze·Zo), at most "
        f"{c['fext_db']:g} dB. valid: every job converged, passivity and reciprocity within the product's flags. "
        "A None value fails.",
        p0.table(result["checks"], ["step", "check", "value", "limit", "pass"]),
        f"n 2 against n 3: e, each plateau over its own mesh's fit2d Zdiff, less 1; move, |(1 + e_n3)/(1 + e_n2) − 1|, "
        f"n 3 when a coupon's exceeds {c['n_rel']:g}; raw, the plateaus' own move; fit2d, fit2d's own move; exact, "
        "each n against the exact cut; ds_max, the largest |ΔS| above DC; arrival, |arrival_n3/arrival_n2 − 1| of "
        "the TDTs.",
        p0.table(moves, ["coupon", "e_n2", "e_n3", "move", "raw", "fit2d", "exact_n2", "exact_n3", "ds_max",
                         "arrival"]),
        "Recorded: each plateau against the exact cut, KiCad's calculator (Cohn's for the stripline), FEXT over the "
        "whole grid at √(Ze·Zo) and at 50 Ω, the launch's worst |S11|, and each 45° twin's level at its diagonal's "
        f"centre (the median over t_r), within {c['bend_rel']:g} of its twin's plateau at the same n.",
        p0.table(recorded, ["step", "plateau_ohm", "exact", "calculator_ohm", "fext_full_db", "fext50_db", "launch_db",
                            "level_ohm", "sigma", "recip"]),
        p0.table(items, ["item", "value"]),
        "## P4B-2 Runs",
        p0.table([{"step": k, **x} for k, x in rows.items()],
                 ["step", "cells", "pool", "t_stop_s", "predicted_s", "worst_s", "wall_s"]),
        "## P4B-3 The victim case",
        f"{VICTIM[0]} (the victim terminated, 6 ports) against {VICTIM[1]} (the victim cut, the pair's 4) at mesh n "
        f"{p4.N}: their fingerprints differ by design (\"ends\"), as compare refuses such runs, so the case reads the "
        "pair's own 4-port block and calls si_deltas directly; the cut victim's refusal is kept.",
        victim_md]) + "\n"


def write(out: Path) -> dict:
    """p4.records over the recorded steps first (SystemExit on two product codes), then measure and decide of <out>:
    <out>/p4b/p4b.json through p0.save, with the versions, CRITERIA, the references, the calibration
    (p3.calibration), the measures' rows by p4.plain, the victim case, bends_n3, decide's checks, decisions and
    verdict, and the steps' machine time (p0.machine); p4b.md beside it (tables). Returns the JSON as saved."""
    recs = p4.records(out, [p3.step_id(p4.name(b, n, "l40", "lossless"), "run", "p4") for b in REF_OF for n in (2, 3)])
    refs, m = json.loads(REFERENCES.read_text(encoding="utf-8")), measure(out)
    result = p0.save(out / "p4b" / "p4b.json", {
        "gate": "P4-B", "versions": p0.versions(), "criteria": CRITERIA, "references": refs,
        "calibration": p3.calibration(),
        "rows": {k: p4.plain(x) for k, x in m.items() if k not in ("victim", "bends_n3")},
        "victim": m["victim"], "bends_n3": m["bends_n3"], **decide(m, refs), "machine": p0.machine(recs)})
    (out / "p4b" / "p4b.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p4b.py --references: writes REFERENCES through p0.save, SystemExit when it exists. python
    tools/p4b.py --out DIR [--steps a,b]: enters <GATES> (p4.enter); with --steps, runs each of them in order
    (p4.run_steps) and returns 1 when one raised, else 0; without, writes the report and returns 0."""
    parser = argparse.ArgumentParser(prog="p4b", description="P4-B, the coupled coupons (Stage 4 design 5.11).")
    parser.add_argument("--out", help="<GATES>, outside every git work tree")
    parser.add_argument("--steps", help=f"comma-separated <board>-n<k>, k 2 or 3, of {', '.join(REF_OF)}; without "
                                        "it, the report")
    parser.add_argument("--references", action="store_true", help="write the references once, before any run")
    args = parser.parse_args(argv)
    if args.references:
        if REFERENCES.exists():
            raise SystemExit("P4-B's references are committed once, before its runs, and never regenerated")
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
