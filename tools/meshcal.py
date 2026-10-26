# SPDX-License-Identifier: GPL-3.0-or-later
"""Plan 6's mesh-rule calibration (design 2026-10-26 §5.1): the one search over 48 candidates for a slot edge's own
inside depth, and its acceptance, fixed before the search. A candidate is a copy of the repo's src, out/tree, whose
rule.py ends with one line that sets SLOT_IN, SLOT_GATE and SLOT_SERVED. r1's harness, pinned by sha256, measures it:
hrun.py (plan 2's ratchet) gives the board rows at mesh n 2 and 3, ax/launch.py the synthetic axes with h unset, 2d and
5d. Each evaluation is a resumable p0 step keyed by its candidate and p0.code_id(): the baseline (the role off), which
must reproduce r1's frozen rows and axes; the shakedown candidate, which must break no axis the baseline keeps; then
the candidates. accept() holds conditions 1 to 4 and choose() condition 5; meshcal.json and meshcal.md record them, and
once meshcal.json exists the search is spent.

Dev-time only: the package never imports it.
# ponytail: single-use, plan 6's one search; the harness and its boards stay outside the repo
Run: python tools/meshcal.py --harness DIR --boards DIR --out DIR."""
import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from functools import partial
from pathlib import Path

import p0

CANDIDATES = [{"id": f"{depth}_{gate}_{scope}", "slot_in": d, "gate": g, "served": scope == "served"}
              for depth, d in (("1-8", 1 / 8), ("9-64", 9 / 64), ("5-32", 5 / 32), ("1-6", 1 / 6), ("3-16", 3 / 16),
                               ("5-24", 5 / 24))
              for gate, g in (("none", 0.0), ("2", 2.0), ("3", 3.0), ("4.2", 4.2))
              for scope in ("lone", "served")]  # depth × gate × scope (design §5.1); depths and gates are ×d
BASE = {"id": "off", "slot_in": None, "gate": 0.0, "served": False}  # the role off: the rule as built
SHAKE = "1-6_none_served"  # r1's ungated served d/6, which broke 3168 axes before the guard (Task 2)
H = {"unset": "", "2d": "2", "5d": "5"}  # the axes runs' KRS_AXIS_H: no h, then h = 2d and h = 5d
GCPW = ("coupon_gcpw", "coupon_gcpw_masked", "coupon_gcpw_pads", "coupon_dense", "coupon_gcpw_arc")  # condition 4
MS = ("coupon_ms", "coupon_ms_masked")  # the microstrip fixtures, whose fit2d condition 4 keeps unchanged
N3_EXEMPT = ("lpf915", "lpf915-45")  # the fixtures condition 1 reads at n 2 only
MAX_REGS = 5  # condition 3: the most board rows the baseline passes that a candidate may fail
GCPW_PCT = 1.5  # condition 4: the GCPW coupons' fit2d limit, ±%
PINNED = {  # the sha256 of each file run reads from r1's harness
    "hrun.py": "4b36b980ae74efb2e4183ccda03a1def424031083060e522a59b96bea3f301c0",
    "all_r6.jsonl": "e94da21b6f8364b928961eb3e799565d0d722c39a4281d4a0e7d557e9a9f15c9",
    "ax/launch.py": "c27c50e31a16b7682e2171879004173de092656f9377ae77448f0536a58efce6",
    "ax/axrun.py": "ff6628b8e9599c559f379e7468e13076479bfce9aedc663af663859abfe3e5a1",
    "ax/common.py": "c5f36a957d2f5906bd0badbb6fb2851a5a31fa91e44a57afe2fcfefb11d8d2b3",
    "ax/axes.py": "61e5aa7ddf30fcd0762d3e2c88682d9176992de9b1f6fd813566882502f2ea46",
    "ax/axes2.py": "ab105323f4b167bc7cc42c8e60ca7ea28440e9593adda8ac65e705ad66012807",
    "ax/caxes.py": "7cfec228037cdb25b2a7d45f86ddb5378aaa3c922703d45b4bcb65bf278562d2",
    "ax/a_head.json": "9b04f55655d058f6a27a076c22ea3187257c63afa5c7115df8a9d732ed84dafd",
    "ax/a_head_h5.json": "9b04f55655d058f6a27a076c22ea3187257c63afa5c7115df8a9d732ed84dafd",
    "ax/a_head_h2.json": "b108a7fcbdd7298828ff256c80c20fdf0faa865f9294bcf3ce3b8b0eb73669ff",
}
# each output of the baseline, in out, and the file of r1's harness it must equal
FROZEN = {"rows/off.jsonl": "all_r6.jsonl", "axes/off-unset.json": "ax/a_head.json",
          "axes/off-2d.json": "ax/a_head_h2.json", "axes/off-5d.json": "ax/a_head_h5.json"}


def patch(text: str, cand: dict) -> str:
    """`text`, a rule.py, plus one line that sets its slot role to `cand`'s values."""
    line = f"SLOT_IN, SLOT_GATE, SLOT_SERVED = {cand['slot_in']!r}, {cand['gate']!r}, {cand['served']!r}"
    return f"{text.rstrip()}\n{line}\n"


def ok(row: dict) -> bool:
    """A board row that passes every gate (plan 2's ratchet): built, no lint hit after the one re-mesh, no ratio fault,
    no cell under d/3, every section's fit2d a number under 3 % (D-22)."""
    return "err" not in row and row["lint"] == row["ratio"] == row["d3"] == 0 and all(
        isinstance(v, float) and abs(v) < 3 for v in row["fit2d"])


def passes(rows: dict, family: str | None = None) -> int:
    return sum(ok(r) for (f, _, _), r in rows.items() if family in (None, f))


def axis_regressions(base: dict, axes: dict) -> int:
    """The axes clean in `base` that fail in `axes` (lint after the re-mesh, ratio, d/3 or an error); one `axes`
    lacks counts as failed."""
    return sum(not any(v[1:]) and any(axes.get(key, [1] * 5)[1:]) for key, v in base.items())


def accept(base_rows: dict, base_axes: dict, rows: dict, axes: dict) -> dict:
    """The design's acceptance (§5.1, fixed before the search) of one candidate's rows and axes against the
    baseline's; a row or axis the candidate lacks counts as failed."""
    def get(key):
        return rows.get(key, {"err": "missing"})
    fixtures = [get(k) for k in base_rows if k[0] == "fixtures" and (k[2] == 2 or k[1] not in N3_EXEMPT)]
    regs = [k for k in base_rows if ok(base_rows[k]) and not ok(get(k))]
    below = sorted({f for f, _, _ in base_rows if passes(rows, f) < passes(base_rows, f)})
    axes_regs = {h: axis_regressions(base_axes[h], axes[h]) for h in H}
    gcpw = [v for k in base_rows if k[0] == "fixtures" and k[1] in GCPW for v in get(k).get("fit2d", [None])]
    ms = all(get(k).get("fit2d") == base_rows[k]["fit2d"] for k in base_rows if k[0] == "fixtures" and k[1] in MS)
    c = {"c1": all(map(ok, fixtures)), "c2": not any(axes_regs.values()),
         "c3": len(regs) <= MAX_REGS and all(k[0] != "fixtures" for k in regs) and not below,
         "c4": ms and all(isinstance(v, float) and -GCPW_PCT <= v <= GCPW_PCT for v in gcpw)}
    finite = [v for v in gcpw if isinstance(v, float) and math.isfinite(v)]
    return {**c, "pass": all(c.values()), "passes": passes(rows), "regressions": [f"{f}/{x} n={n}" for f, x, n in regs],
            "families_below": below, "axes_regressions": axes_regs, "ms_unchanged": ms,
            "gcpw_coupons": [min(finite), max(finite)] if finite else None,
            "gcpw_max": max(map(abs, finite), default=None)}


def choose(results: list[dict]) -> str | None:
    """Condition 5: of the candidates that pass, the most passes, then the smallest max |fit2d| over the GCPW
    coupons' sections at n 2 and 3 (condition 4's), then the first in the grid's order."""
    best = min(((-r["passes"], r["gcpw_max"], i) for i, r in enumerate(results) if r["pass"]), default=None)
    return None if best is None else results[best[2]]["id"]


def _call(cmd: list[str], env: dict) -> None:
    """Runs one harness command: CalledProcessError on a non-zero exit. The tests replace it."""
    subprocess.run(cmd, env=env, check=True)


def _tree(out: Path, cand: dict) -> Path:
    """out/tree rebuilt for `cand`: a copy of the repo's src whose rule.py ends with patch's line. Returns it."""
    tree = out / "tree"
    if tree.exists():
        shutil.rmtree(tree)
    shutil.copytree(p0.ROOT / "src", tree / "src", ignore=shutil.ignore_patterns("__pycache__"))
    rule = tree / "src" / "kicad_rf_studio" / "core" / "mesh" / "rule.py"
    rule.write_text(patch(rule.read_text(encoding="utf-8"), cand), encoding="utf-8")
    return tree


def _axes_run(harness: Path, out: Path, tree: Path, name: str) -> None:
    """The axes harness on `tree` with each h of H, into out/axes/<name>-<h>.json."""
    for h, v in H.items():
        _call([sys.executable, str(harness / "ax" / "launch.py"), str(out / "axes" / f"{name}-{h}.json")],
              {**os.environ, "KRS_TREE": str(tree), "KRS_AXIS_H": v})


def _evaluate(harness: Path, boards: Path, out: Path, cand: dict) -> dict:
    """One evaluation of `cand`: out/tree rebuilt for it, hrun.py's board rows at reach 6 into out/rows/<id>.jsonl,
    then its axes. Returns {}: the outputs are the evaluation's record."""
    tree = _tree(out, cand)
    _call([sys.executable, str(harness / "hrun.py"), str(out / "rows" / f"{cand['id']}.jsonl"),
           str(boards / "scratch-T10-r5" / "all.json"), str(boards)],
          {**os.environ, "KRS_SRC": str(tree / "src"), "KRS_REACH": "6"})
    _axes_run(harness, out, tree, cand["id"])
    return {}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(path: Path) -> dict:
    """hrun.py's rows in `path`, by (family, case, n)."""
    return {(r["family"], r["case"], r["n"]): r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}


def _same(mine: Path, frozen: Path) -> bool:
    """Whether an output holds r1's frozen data: rows line by line, axes as parsed dicts."""
    if mine.suffix == ".jsonl":
        return mine.read_text(encoding="utf-8").splitlines() == frozen.read_text(encoding="utf-8").splitlines()
    return _load(mine) == _load(frozen)


def run(harness: Path, boards: Path, out: Path, cands: list[dict] | None = None) -> dict:
    """The search in the folder `out` (design §5.1), each evaluation a p0 step keyed by its candidate and
    p0.code_id(): BASE, then SHAKE's axes, then each of `cands` (default CANDIDATES); returns decide()'s result.
    SystemExit, before any step, when out/meshcal.json exists (the one search is spent), when src differs from HEAD,
    or when a file of PINNED is missing from `harness` or differs; after BASE, when its outputs differ from r1's
    FROZEN files; after the shakedown, when it breaks an axis BASE keeps. A failed command raises out of it."""
    cands = CANDIDATES if cands is None else cands
    if (out / "meshcal.json").exists():
        raise SystemExit(f"meshcal: {out / 'meshcal.json'} exists: the one search is spent")
    out = p0.enter(out)
    if p0.code_id().endswith("+dirty"):
        raise SystemExit("meshcal: src has uncommitted changes; commit them first: each step is keyed by the code")
    bad = [name for name, sha in PINNED.items()
           if not (harness / name).is_file() or hashlib.sha256((harness / name).read_bytes()).hexdigest() != sha]
    if bad:
        raise SystemExit(f"meshcal: {', '.join(bad)} in {harness} missing or unlike plan 6's pinned evaluator; "
                         "restore r1's copy")
    for folder in ("rows", "axes"):
        (out / folder).mkdir(exist_ok=True)
    p0.step(out, "meshcal-off", BASE["id"], partial(_evaluate, harness, boards, out, BASE))
    differ = [f"{mine} against {frozen}" for mine, frozen in FROZEN.items() if not _same(out / mine, harness / frozen)]
    if differ:
        raise SystemExit(f"meshcal: the baseline differs from r1's frozen one ({'; '.join(differ)}); stop and report")
    shake = next(c for c in CANDIDATES if c["id"] == SHAKE)

    def shakedown() -> dict:
        _axes_run(harness, out, _tree(out, shake), "shakedown")
        return {h: axis_regressions(_load(out / "axes" / f"off-{h}.json"), _load(out / "axes" / f"shakedown-{h}.json"))
                for h in H}

    counts = p0.step(out, "meshcal-shakedown", SHAKE, shakedown)["result"]
    if any(counts.values()):
        raise SystemExit(f"meshcal: the shakedown candidate {SHAKE} breaks axes the baseline keeps ("
                         + ", ".join(f"{h} {n}" for h, n in counts.items()) + "); fix Task 2 test-first")
    for cand in cands:  # ponytail: stops at the first failed evaluation; a rerun resumes
        p0.step(out, f"meshcal-{cand['id']}", cand["id"], partial(_evaluate, harness, boards, out, cand))
    return decide(out, cands)


def decide(out: Path, cands: list[dict]) -> dict:
    """The search's result from the records and outputs in `out`: accept() of each of `cands` against the baseline,
    with one candidate's axes in memory at a time (about 50 MB a file), choose()'s winner, out/meshcal.json through
    p0.save and out/meshcal.md; prints the winner. SystemExit from p0.records for a missing record or records of two
    codes. Returns the JSON as saved."""
    records = p0.records(out, ["meshcal-off", "meshcal-shakedown", *(f"meshcal-{c['id']}" for c in cands)])
    base_rows, base_axes = _rows(out / "rows" / "off.jsonl"), {h: _load(out / "axes" / f"off-{h}.json") for h in H}
    results = [{**c, **accept(base_rows, base_axes, _rows(out / "rows" / f"{c['id']}.jsonl"),
                              {h: _load(out / "axes" / f"{c['id']}-{h}.json") for h in H})} for c in cands]
    winner = choose(results)
    data = p0.save(out / "meshcal.json", {
        "base": {"passes": passes(base_rows), "rows": len(base_rows),
                 "axes_failing": {h: sum(any(v[1:]) for v in a.values()) for h, a in base_axes.items()}},
        "candidates": results, "winner": winner, "versions": p0.versions(), "machine": p0.machine(records)})
    base = data["base"]
    (out / "meshcal.md").write_text(
        f"Baseline (the role off): {base['passes']} of {base['rows']} board rows pass; axes failing: "
        + ", ".join(f"{h} {n}" for h, n in base["axes_failing"].items()) + ".\n\n"
        + p0.table(data["candidates"], ["id", "c1", "c2", "c3", "c4", "pass", "passes", "regressions",
                                        "families_below", "gcpw_coupons", "gcpw_max"])
        + f"\n\nWinner: {winner or 'none; no candidate passes, so the rule does not change'}.\n", encoding="utf-8")
    print(f"meshcal: winner {winner}" if winner else "meshcal: no candidate passes", flush=True)
    return data


def main(argv: list[str] | None = None) -> None:
    """python tools/meshcal.py --harness DIR --boards DIR --out DIR: run()."""
    parser = argparse.ArgumentParser(prog="meshcal", description="Plan 6's mesh-rule calibration (design 5.1).")
    parser.add_argument("--harness", required=True, type=Path, metavar="DIR",
                        help="r1's harness: hrun.py, all_r6.jsonl and ax/")
    parser.add_argument("--boards", required=True, type=Path, metavar="DIR",
                        help="plan 2's boards, with scratch-T10-r5/all.json")
    parser.add_argument("--out", required=True, type=Path, metavar="DIR",
                        help="the search's folder, outside every git work tree")
    a = parser.parse_args(argv)
    run(a.harness, a.boards, a.out)


if __name__ == "__main__":
    main()
