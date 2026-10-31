# SPDX-License-Identifier: GPL-3.0-or-later
"""P3-C, convergence and defaults (Stage 3 design 5.11) on both fixtures: mesh n 2/3/4, the air gap λ/4 against λ/2,
Normal against Strict, a free run to 3 × the stop time, solid against all-sheet copper, and MUR at λ/2 as report-only
evidence; each variant a project edit run through the product, each delta computed in-process (compare refuses
different settings); p3c.json and p3c.md in <out>/p3c, written from whatever steps are recorded. Run: python
tools/p3c.py --out DIR [--steps ...]."""
import argparse
import json
import sys
from functools import partial
from pathlib import Path

import p0
import p3
from kicad_rf_studio.core.project import load_project
from kicad_rf_studio.stoprule import KEPT

CRITERIA = json.loads((p0.FIX / "p3c" / "criteria.json").read_text(encoding="utf-8"))  # committed before any run
FIXTURES = ("ifa2g4", "meander915")
COPPERS = ("solid", "sheet")
SETTINGS = ("n2", "n3", "n4", "gap2", "strict")
FREE = {"free": "n2", "murfree": "mur"}  # each free step's project, by its setting
# each fixture's raised "t_max_s" and "flat_s", set only at a checkpoint (Task 10), a recorded deviation
RAISED: dict[str, dict] = {"ifa2g4": {}, "meander915": {}}


def names() -> list[str]:
    """Every step, fixture by fixture, copper by copper: <fixture>-<copper>-<setting> for each of SETTINGS, then mur
    (MUR at λ/2; the meander's runs only when its PML fails), then the free runs free, on the n2 project, and murfree,
    on the mur project."""
    return [f"{fixture}-{copper}-{setting}" for fixture in FIXTURES for copper in COPPERS
            for setting in (*SETTINGS, "mur", *FREE)]


def edits(name: str, base: dict) -> dict:
    """The project edits (p0.edit's dotted keys) of the run step `name` on its fixture's base project `base`: its
    copper; n3 and n4 their mesh n, ifa2g4's with the fit2d limit fit2d_raised (ruling 2); gap2 the air gap at λ/2,
    twice the base's; strict the stop rule's preset alone, mesh n kept at 2 (`new --preset strict` would write n 3);
    mur the MUR boundary at λ/2; then RAISED's edits of its fixture."""
    fixture, copper, setting = name.split("-")
    gap = {"air_gap_mm": round(2 * base["air_gap_mm"], 6)}
    fit2d = {"gates.fit2d_limit": CRITERIA["fit2d_raised"]} if fixture == "ifa2g4" else {}
    return {"copper": copper, **{"n2": {}, "n3": {"mesh.n": 3, **fit2d}, "n4": {"mesh.n": 4, **fit2d}, "gap2": gap,
                                 "strict": {"preset": "strict"}, "mur": {"boundary": "mur", **gap}}[setting],
            **RAISED[fixture]}


def _ran(out: Path, name: str) -> dict:
    """p3.measure of the project `name`'s run step; RuntimeError "run <name> first" when that step has no record."""
    if (m := p3.measure(out, name)) is None:
        raise RuntimeError(f"p3c: run {name} first")
    return m


def run(out: Path, name: str) -> None:
    """The step `name` of names() in <out> (<GATES>); KeyError for another name. A run step: p3.variant of its fixture's
    base with edits(name, the base project), then p3.run_step. A free step: p3.free_step of its project (FREE), as that
    project's run left it, to t_free: for free, and for the meander's murfree (its PML free run's length), max(n2's
    t_max_s, free_factor × n2's longest kept t_stop) (ruling 4; ValueError when n2 kept none); for ifa2g4's murfree,
    free_factor × the mur project's t_max_s (P3-A's 3 × T_max window, where its MUR twin rose 16 dB). RuntimeError "run
    <project> first" when its project's run, or n2's, which sets its length, has no record."""
    if name not in names():
        raise KeyError(name)
    fixture, copper, setting = name.split("-")
    if setting not in FREE:
        p3.variant(out, name, fixture, edits(name, load_project(p3.base(out, fixture))))
        p3.run_step(out, name)
        return
    project, n2 = f"{fixture}-{copper}-{FREE[setting]}", f"{fixture}-{copper}-n2"
    m = _ran(out, project)
    if (fixture, setting) == ("ifa2g4", "murfree"):
        t_free = CRITERIA["free_factor"] * load_project(p3.project_path(out, project))["t_max_s"]
    else:
        jobs = (m if project == n2 else _ran(out, n2))["jobs"]
        kept = [job["t_stop"] for job in jobs if job["verdict"] in KEPT and job["t_stop"] is not None]
        t_free = max(load_project(p3.project_path(out, n2))["t_max_s"], CRITERIA["free_factor"] * max(kept))
    p3.free_step(out, project, t_free)


def main(argv: list[str] | None = None) -> int:
    """python tools/p3c.py --out DIR --steps a,b: enters <GATES> (p3.enter) first, then runs each of the steps in order
    (p3.run_steps) and returns 1 when one raised, else 0."""
    parser = argparse.ArgumentParser(prog="p3c", description="P3-C, convergence and defaults (Stage 3 design 5.11).")
    parser.add_argument("--out", required=True, help="<GATES>, outside every git work tree")
    parser.add_argument("--steps", required=True, help=f"comma-separated <fixture>-<copper>-<setting>, of "
                        f"{'/'.join(FIXTURES)}, {'/'.join(COPPERS)} and {'/'.join((*SETTINGS, 'mur', *FREE))}")
    args = parser.parse_args(argv)
    out = p3.enter(Path(args.out))
    return p3.run_steps(args.steps.split(","), partial(run, out))


if __name__ == "__main__":
    sys.exit(main())
