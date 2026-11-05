# SPDX-License-Identifier: GPL-3.0-or-later
"""P4-F, the positive control (Stage 4 design 5.11; plan 4 rulings F-1 to F-3). It runs usb2_hs, its neck-down and its
plane gap at new's values and P4-B to P4-D's settings, under the ring rule, compared through their runs. The rows each
case is built to move are judged against `tests/fixtures/p4f/criteria.json` with P4-E's thresholds, and p4f.json and
p4f.md are written in <out>/p4f. Run: `python tools/p4f.py --out DIR [--steps usb2_hs,usb2_hs_neck,usb2_hs_gap]`."""
import argparse
import json
import sys
from functools import partial
from pathlib import Path

import p0
import p3
import p4
import p4d
import p4e
from kicad_rf_studio.core.messages import english
from kicad_rf_studio.core.post.si import si_delta_lines
from kicad_rf_studio.stoprule import RING_CEILING

CRITERIA = json.loads((p0.FIX / "p4f" / "criteria.json").read_text(encoding="utf-8"))  # committed before any run
REFERENCES = p0.FIX / "p4f" / "references.json"  # the ladder model's soft notes, written by hand before any run
CASES = ("usb2_hs", "usb2_hs_neck", "usb2_hs_gap")  # the base, its neck-down and its plane gap
JUDGED = {"neck": "tdr_highest", "gap": "scd21_worst"}  # the row each case is built to move (F-2)


def step(out: Path, name: str) -> dict:
    """The step `name` of CASES: p4's run step on its project at p4.N, p4.RULE and p4.DIELECTRIC; the base is P4-D's
    lossless usb2_hs step, the same project and record, while the dielectric is lossless. KeyError for another name."""
    if name not in CASES:
        raise KeyError(name)
    return p4.run_step(out, p4.project(out, name)[0])


def measure(out: Path) -> dict:
    """P4-F's measurements in <out>, in this process:
    - "thresholds": P4-E's, <out>/p4e/p4e.json's, with "floor_db" from p4e.CRITERIA (SystemExit "run P4-E's report
      first" without it);
    - "runs": p4.measure of each recorded case by its name, with "verdicts", its jobs' in port order, "t_max_s", its
      project's T_max, and "ceiling_s", the ring rule's RING_CEILING × T_max;
    - "neck" and "gap": p4.deltas of the base's run against the neck's and the gap's, each None while either reading
      is missing;
    - "neck_short", the neck reading's own highest level's mark, and "base_short", the base's two marks [lowest's,
      highest's], each None without levels;
    - "dc": {case: p4d.dc_check of its project's run against p4d's references' entry (D-2)}, None when its results are
      not its run's;
    - "invalid": the recorded cases whose run is not valid."""
    file = out / "p4e" / "p4e.json"
    if not file.is_file():
        raise SystemExit("run P4-E's report first")
    thresholds = {**json.loads(file.read_text(encoding="utf-8"))["thresholds"], "floor_db": p4e.CRITERIA["floor_db"]}
    runs = {}
    for case in CASES:
        if (x := p4.measure(out, p4.name(case))) is not None:
            t_max = x["project"]["t_max_s"]
            runs[case] = {**x, "verdicts": [job["verdict"] for job in x["jobs"]], "t_max_s": t_max,
                          "ceiling_s": RING_CEILING * t_max}
    base = runs.get(CASES[0])

    def deltas(case: str) -> list[dict] | None:
        x = runs.get(case)
        return p4.deltas(base, x) if base and x and base["reading"] and x["reading"] else None

    def marks(case: str) -> list[bool] | None:
        r = runs.get(case, {}).get("reading")
        return None if r is None or r.levels is None else [level[2] for level in r.levels]

    neck, refs = marks(CASES[1]), json.loads(p4d.REFERENCES.read_text(encoding="utf-8"))["dc"]
    return {"thresholds": thresholds, "runs": runs, "neck": deltas(CASES[1]), "gap": deltas(CASES[2]),
            "neck_short": None if neck is None else neck[1], "base_short": marks(CASES[0]),
            "dc": {case: None if x["fingerprint"] is None else p4d.dc_check(p3.project_path(out, p4.name(case)),
                                                                            refs[case]) for case, x in runs.items()},
            "invalid": [case for case, x in runs.items() if not x["valid"]]}


def decide(m: dict, t: dict) -> dict:
    """P4-F's checks (design 5.11; F-2) on the measures `m` (measure's shape) at P4-E's thresholds `t` ("DIFF_OHM",
    "DB", "floor_db"), a missing row or delta a fail:
    - "neck": the neck pair's tdr_highest row (its "quantity" alone without one) with its "limit", neck_factor ×
      DIFF_OHM, and "pass", its delta at least that;
    - "gap": the gap pair's scd21_worst row (likewise) with its "limit", DB, its "floor_db" and "pass", resolved:
      |delta| above DB and the higher of its two levels above floor_db;
    - "verdict": {"value": "fail" on a fail, else "pass"; "fails": "neck: tdr_highest", "gap: scd21_worst" and
      "<case>: valid"; "owner": "neck: short mark" when the neck run's own highest level is unmarked (neck_short
      False), the short-feature rule's true positive missed, an owner item}."""
    def row(case: str) -> dict:  # its judged row, {} without one
        return next((r for r in m[case] or [] if r["quantity"] == JUDGED[case]), {})

    neck, gap, limit = row("neck"), row("gap"), CRITERIA["neck_factor"] * t["DIFF_OHM"]
    passed = {"neck": neck.get("delta") is not None and neck["delta"] >= limit,
              "gap": gap.get("delta") is not None and abs(gap["delta"]) > t["DB"]
              and max(gap["base"], gap["variant"]) > t["floor_db"]}
    fails = [f"{case}: {JUDGED[case]}" for case, ok in passed.items() if not ok]
    fails += [f"{case}: valid" for case in m["invalid"]]
    return {"neck": {"quantity": JUDGED["neck"], **neck, "limit": limit, "pass": passed["neck"]},
            "gap": {"quantity": JUDGED["gap"], **gap, "limit": t["DB"], "floor_db": t["floor_db"],
                    "pass": passed["gap"]},
            "verdict": {"value": "fail" if fails else "pass", "fails": fails,
                        "owner": ["neck: short mark"] if m["neck_short"] is False else []}}


def tables(result: dict) -> str:
    """The Markdown of the gate JSON `result` (write's), by p0.table: P4F-1 the judged rows with their limits, the neck
    run's own mark against the base's, P4-E's thresholds and the verdict; P4F-2 every other row of both pairs, as
    compare words them; P4F-3 the runs: verdicts, t_stop against T_max and the ring rule's ceiling, the DC point, cells,
    predicted and wall times, valid; then the references' soft notes beside what was measured."""
    c, t, v, refs, rows = (result[k] for k in ("criteria", "thresholds", "verdict", "references", "rows"))
    items = [*({"item": k, "value": result[k]} for k in ("neck_short", "base_short")),
             *({"item": k, "value": t[k]} for k in ("DIFF_OHM", "DB", "floor_db")),
             {"item": "verdict", "value": v["value"]}, {"item": "fails", "value": ", ".join(v["fails"]) or "none"},
             {"item": "owner", "value": ", ".join(v["owner"]) or "none"}]

    def delta(case: str, quantity: str) -> float | None:  # the measured delta, None without
        return next((r["delta"] for r in rows[case] or [] if r["quantity"] == quantity), None)

    neck, gap = refs["neck"], refs["gap"]
    notes = [{"note": "neck tdr_highest delta (ohm)", "predicted": neck["tdr_highest_delta_ohm"],
              "measured": delta("neck", "tdr_highest")},
             {"note": "neck tdr_lowest delta (ohm)", "predicted": neck["tdr_lowest_delta_ohm"],
              "measured": delta("neck", "tdr_lowest")},
             {"note": "neck largest pointwise TDR difference (ohm)", "predicted": neck["pointwise_max_ohm"]},
             {"note": "gap tdr_highest delta (ohm)", "predicted": gap["tdr_highest_delta_ohm"],
              "plan3": gap["plan3_preview"]["tdr_highest_delta_ohm"], "measured": delta("gap", "tdr_highest")},
             {"note": "gap scd21_worst delta (dB)", "plan3": gap["plan3_preview"]["scd21_worst_delta_db"],
              "measured": delta("gap", "scd21_worst")}]
    recorded = [f"{case}:\n\n" + "\n".join(f"- {line}" for line in lines) for case, lines in result["recorded"].items()]
    return "\n\n".join([
        "## P4F-1 The judged rows",
        f"Each case's run against usb2_hs's at mesh n {result['n_now']}, the rule {result['rule_now']} and "
        f"{result['dielectric_now']}, compared through their runs' chains (no retune or verify). neck: the highest TDR "
        f"level's delta at least {c['neck_factor']:g} × DIFF_OHM; gap: the worst Scd21's change resolved, |delta| "
        "above DB and the higher of its two levels above floor_db; each run valid. DIFF_OHM, DB and floor_db are "
        "P4-E's. The neck run's own highest level should be marked short, the short-feature rule's true positive (the "
        "delta row's mark carries the base's levels, short already); a miss is an owner item.",
        p0.table([{"case": case, **result[case]} for case in JUDGED],
                 ["case", "quantity", "marker", "base", "variant", "delta", "limit", "pass"]),
        p0.table(items, ["item", "value"]),
        "## P4F-2 The other rows, recorded",
        "Every other row of both pairs, as compare words them (si_delta_lines on the base's project), resolved at "
        "si.py's registered thresholds.",
        *(recorded or ["Not run."]),
        "## P4F-3 Runs",
        "Each run's job verdicts in port order and its longest t_stop kept, against T_max and the ring rule's ceiling, "
        f"{RING_CEILING} × T_max; dc, the DC point's largest | |S_layout(0)| − |2P − I| | against P4-D's committed "
        "references, recorded (P4-D judges it on its lossless runs).",
        p0.table([{"step": case, **x, "verdicts": ", ".join(x["verdicts"]), "dc": result["dc"].get(case)}
                  for case, x in result["runs"].items()],
                 ["step", "verdicts", "t_stop_s", "t_max_s", "ceiling_s", "dc", "cells", "predicted_s", "worst_s",
                  "wall_s", "valid"]),
        "## Soft notes",
        f"{refs['source']}. plan3: plan 3's preview of the gap.",
        p0.table(notes, ["note", "predicted", "plan3", "measured"])]) + "\n"


def write(out: Path) -> dict:
    """p4.records over the recorded cases first (SystemExit on two product codes), then measure and decide of <out> at
    measure's thresholds: <out>/p4f/p4f.json through p0.save, with the versions, CRITERIA, the references, the
    calibration (p3.calibration), n_now, rule_now and dielectric_now, the thresholds, "rows" {"neck", "gap"}, the
    marks, "recorded" {case: every other row of its pair rendered by english from si_delta_lines on the base's
    project}, "runs", each recorded case's p4.plain, dc and invalid, decide's neck, gap and verdict, and the steps'
    machine time (p0.machine); p4f.md beside it (tables). Returns the JSON as saved."""
    recs = p4.records(out, [p3.step_id(p4.name(case), "run", "p4") for case in CASES])
    m = measure(out)
    base = m["runs"].get(CASES[0], {}).get("project")
    recorded = {case: [english(code, **params) for code, params in
                       si_delta_lines(base, [r for r in m[case] if r["quantity"] != judged])]
                for case, judged in JUDGED.items() if m[case] is not None}
    result = p0.save(out / "p4f" / "p4f.json", {
        "gate": "P4-F", "versions": p0.versions(), "criteria": CRITERIA,
        "references": json.loads(REFERENCES.read_text(encoding="utf-8")), "calibration": p3.calibration(),
        "n_now": p4.N, "rule_now": p4.RULE, "dielectric_now": p4.DIELECTRIC, "thresholds": m["thresholds"],
        "rows": {case: m[case] for case in JUDGED}, "neck_short": m["neck_short"], "base_short": m["base_short"],
        "recorded": recorded, "runs": {case: p4.plain(x) for case, x in m["runs"].items()}, "dc": m["dc"],
        "invalid": m["invalid"], **decide(m, m["thresholds"]), "machine": p0.machine(recs)})
    (out / "p4f" / "p4f.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p4f.py --out DIR [--steps a,b]: enters <GATES> (p4.enter); with --steps, runs each of them in order
    (p4.run_steps) and returns 1 when one raised, else 0; without, writes the report, P4-E's first, and returns 0. Its
    references are written by hand, committed before any run."""
    parser = argparse.ArgumentParser(prog="p4f", description="P4-F, the positive control (Stage 4 design 5.11).")
    parser.add_argument("--out", required=True, help="<GATES>, outside every git work tree")
    parser.add_argument("--steps", help=f"comma-separated cases of {', '.join(CASES)}; without it, the report")
    args = parser.parse_args(argv)
    out = p4.enter(Path(args.out))
    if args.steps:
        return p4.run_steps(args.steps.split(","), partial(step, out))
    write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
