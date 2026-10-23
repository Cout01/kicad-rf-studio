# SPDX-License-Identifier: GPL-3.0-or-later
"""P0-C, the private board crop, as a tool (spec 9.4; D-46, r7 §4). The board is copied into OUT/board, the original
never touched, and every CLI child runs through p0.cli with OUT/data as its per-user data folder (p0.enter, D-7), so
C0's first `cost` calibrates OUT/data (PF-42). The base project is `new`'s, OUT/projects/base; each step is a
resumable p0.step that stores only its command's raw outputs: C0 `cost` on the base; C1 `run` at --preset (Strict by
default) with the free RAM sampled meanwhile; C2 `verify` on a copy of C1's project with its results; C3 the
next-best references, C4a mesh.n 3, C4b the margin doubled, C5 no lid and C6 band factor 1.25, each a copy of the base
run at Normal; S2P `retune` to each of the owner's S2P files. Criteria 1–4, the "also" items and the measured values
are computed from the run folders when the reports are written, at the end of every invocation: OUT/report/p0c.json
and p0c.md, private (refs, nets, values, coordinates), and p0c-public.json, PUBLIC's numbers only.

Dev-time only, like p0: the package never imports it. Run: python tools/p0c.py --board PATH --start REF.PAD
--end REF.PAD --f0 F [--harmonics N] [--lid-height MM] [--stackup NAME] --out DIR [--preset draft|normal|strict]
[--steps C0,C1,…] [--s2p DIR]."""
import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import sys
import threading
import traceback
from functools import partial
from pathlib import Path

import numpy as np

import p0
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.cli import _reference
from kicad_rf_studio.core.kicad import choose_reference, classify, load_board
from kicad_rf_studio.core.model.readers import read_stats
from kicad_rf_studio.core.post.chain import loads, part_impedances
from kicad_rf_studio.core.post.checks import LOSS_LIMIT, RECIP_LIMIT, SIGMA_LIMIT, loss_budget, recip_err, sigma_max
from kicad_rf_studio.core.post.waves import grid, layout
from kicad_rf_studio.core.project import GATES, board_file, load_project, save_project
from kicad_rf_studio.stoprule import PRESETS

STEPS = ("C0", "C1", "C2", "C3", "C4a", "C4b", "C5", "C6", "S2P")
NORMAL = {"preset": "normal"}  # comparisons against dB limits run at Normal (D-10)
VARIANTS = {"C3": NORMAL, "C4a": {**NORMAL, "mesh.n": 3, "gates.fit2d_limit": GATES["fit2d_limit"]},
            "C4b": {**NORMAL, "region.margin_scale": 2.0}, "C5": {**NORMAL, "lid": False},
            "C6": {**NORMAL, "band_factor": 1.25}}  # the edits of the base copies that run (C3's references aside)
FIT2D_RAISED = 0.05  # C4a's gates.fit2d_limit after E_FIT2D_FINE, as P0-B's B5
RAM_POLL_S = 5.0  # how often C1 samples the free RAM
MARKS = {"f0": 1, "2f0": 2, "3f0": 3}  # the harmonics the lid and band deltas are read at
LIMITS = {"c1": p0.LIMITS1, "c2": {"sigma_max": SIGMA_LIMIT, "recip": RECIP_LIMIT, "loss_excess": LOSS_LIMIT},
          "c3": {"ds21_db": 0.2}, "c4": {"n3_ds21_db": 0.1, "margin_ds21_db": 0.1}}  # spec 9.4 criteria 1–4
# p0c-public.json's allowlist: a dict recurses, a tuple names keys kept whole, whose values are numbers only
PUBLIC = {"criteria": {"c1": ("ds21_db_f0", "ds11_f0", "ds_max", "pass"),
                       "c2": ("sigma_max", "recip", "loss_excess", "pass"), "c3": ("ds21_db", "pass"),
                       "c4": ("n3_ds21_db", "margin_ds21_db", "pass")},
          "verdict": ("pass", "refine_mesh", "fallback", "prominent_reference"),
          "measured": ("mcells", "dt", "stop_ns", "wall_s", "speeds_mcs", "ram_mb_per_mcell", "lid_ds", "band_ds",
                       "s2p_ds_max"),
          "machine": ("machine_hours", "elapsed_days", "loaded_steps")}


def _project(out: Path, name: str) -> Path:
    """The project.json of `name` ("base", a step or an S2P file's copy) in the P0 folder `out`."""
    return out / "projects" / name / "project.json"


def base(out: Path, a: argparse.Namespace) -> Path:
    """The base project, made by `new` from the board's copy with the options `a` when it is missing (RuntimeError on
    a non-zero exit; new writes project.json only once every refusal check passed)."""
    pj = _project(out, "base")
    if not pj.is_file():
        options = (("--harmonics", a.harmonics), ("--lid-height", a.lid_height), ("--stackup", a.stackup))
        code, text = p0.cli("new", str(out / "board" / Path(a.board).name), "--start", a.start, "--end", a.end,
                            "--f0", a.f0, *(x for flag, v in options if v is not None for x in (flag, v)),
                            "-o", str(pj.parent))
        if code:
            raise RuntimeError(f"p0c: new exited {code}: {(text.strip().splitlines() or [''])[-1]}")
    return pj


def variant(out: Path, name: str, edits: dict) -> Path:
    """The project of the run step `name`: made when missing as a copy of the base without results, then `edits`
    (p0.edit) on every call, saved only when they change it, so that it keeps its own run's results."""
    pj = _project(out, name)
    if not pj.is_file():
        pj.parent.mkdir(parents=True, exist_ok=True)
        save_project(pj, {k: v for k, v in load_project(_project(out, "base")).items() if k != "results"})
    data = load_project(pj)
    edited = p0.edit(copy.deepcopy(data), edits)
    if edited != data:
        save_project(pj, edited)
    return pj


def copy_of_c1(out: Path, name: str, edits: dict) -> Path:
    """The project `name` (C2, an S2P file's): a fresh copy of C1's project with its results and `edits`, made as its
    step runs, so that it holds the C1 run the step is keyed by; results_of accepts it, the preset not being in the
    spec hash."""
    pj = _project(out, name)
    pj.parent.mkdir(parents=True, exist_ok=True)
    save_project(pj, p0.edit(load_project(_project(out, "C1")), edits))
    return pj


def events(run_dir: str | None) -> list[dict]:
    """The events of the run folder named `run_dir`; none without one."""
    path = p0.run_path(run_dir) / "events.jsonl" if run_dir else None
    if path is None or not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def command(pj: Path, name: str) -> dict:
    """p0.cli_run's raw outputs of `name` ("cost", whose jobs and wall_s read None as it stores no results, "run" or
    "verify") on the project `pj`, plus "codes": the E_ and W_ codes of its run folder's events, sorted."""
    res = p0.cli_run(pj, name)
    return {**res, "codes": sorted({e["code"] for e in events(res["run_dir"]) if e["code"][:2] in ("E_", "W_")})}


def sampled(pj: Path) -> dict:
    """C1's `run` on `pj`, runs.free_ram_mb() sampled every RAM_POLL_S by a thread meanwhile: command's outputs plus
    "ram_free_mb", [the free RAM before the run, the lowest sample] in MB."""
    free, done = [runs.free_ram_mb()], threading.Event()

    def sample() -> None:
        while not done.wait(RAM_POLL_S):
            free.append(runs.free_ram_mb())

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        res = command(pj, "run")
    finally:
        done.set()
        thread.join()
    return {**res, "ram_free_mb": [free[0], min(free)]}


def fine_mesh(pj: Path) -> dict:
    """C4a's `run` on `pj`; after an exit 3 naming E_FIT2D_FINE, gates.fit2d_limit FIT2D_RAISED and `run` again, the
    first run's outputs kept under "first" (W_GATE_LIMITS is among the second's codes)."""
    first = command(pj, "run")
    if first["exit"] != 3 or "E_FIT2D_FINE" not in first["codes"]:
        return first
    save_project(pj, p0.edit(load_project(pj), {"gates.fit2d_limit": FIT2D_RAISED}))
    return {**command(pj, "run"), "first": first}


def s2p_files(folder: Path) -> list[Path]:
    """The owner's S2P files in `folder`, by name: each <REF>.series.s2p or <REF>.shunt.s2p."""
    return sorted(p for p in folder.iterdir() if re.fullmatch(r"[^.]+\.(series|shunt)\.s2p", p.name))


def retunes(out: Path, files: list[Path]) -> dict:
    """`retune` of each file's part to it, each on its own copy of C1's project with its results,
    S2P-<REF>.<connection>: {"files": [{"file", "ref", "connection", "exit"}]}."""
    rows = []
    for file in files:
        ref, connection, _ = file.name.split(".")
        pj = copy_of_c1(out, f"S2P-{ref}.{connection}", {})
        rows.append({"file": file.name, "ref": ref, "connection": connection,
                     "exit": p0.cli("retune", str(pj), f"{ref}={file}:{connection}")[0]})
    return {"files": rows}


def next_best(pj: Path) -> list[dict] | None:
    """The ports of the project `pj` with each reference moved to the next-best one, choose_reference(rank=1), stored
    as `new` stores one (PF-40): a port without one keeps its own; None when no port has one."""
    data = load_project(pj)
    board = load_board(board_file(pj, data))
    classes = classify(board, data["classes"])
    refs = [choose_reference(board, classes, port["signal"], rank=1) for port in data["ports"]]
    if all(ref is None for ref in refs):
        return None
    return [port if ref is None else {**port, "rule": ref.rule, "reference": _reference(ref)}
            for port, ref in zip(data["ports"], refs)]


def c1_run(out: Path) -> str:
    """The name of C1's run folder, from its record; RuntimeError, so that main logs the step that needs it and goes
    on, while C1 has no record of a run that stored results."""
    path = out / "steps" / "p0c-C1.json"
    res = json.loads(path.read_text(encoding="utf-8"))["result"] if path.is_file() else None
    if res is None or res["exit"] or res["jobs"] is None:
        raise RuntimeError("p0c: C1 has no run with results yet; run C1 first")
    return res["run_dir"]


def run_step(out: Path, a: argparse.Namespace, name: str) -> None:
    """The step `name` (STEPS) through p0.step (D-6). C0 is keyed by the base's model key, C1 by that and the preset,
    C2 by C1's run folder, S2P by that and the files' names and sha256, the other variants by their own model key; C3
    is skipped, with a line, when no port has a next-best reference (PF-40)."""
    sid, pj = f"p0c-{name}", base(out, a)
    if name == "C0":
        p0.step(out, sid, p0.model_key(pj), partial(command, pj, "cost"))
    elif name == "C1":
        p0.step(out, sid, f"{p0.model_key(pj)}|{a.preset}", partial(sampled, variant(out, "C1", {"preset": a.preset})))
    elif name == "C2":
        p0.step(out, sid, c1_run(out), lambda: command(copy_of_c1(out, "C2", NORMAL), "verify"))
    elif name == "S2P":
        files = s2p_files(Path(a.s2p))
        key = "|".join([c1_run(out), *(f"{p.name}:{hashlib.sha256(p.read_bytes()).hexdigest()}" for p in files)])
        p0.step(out, sid, key, partial(retunes, out, files))
    else:
        edits = VARIANTS[name]
        if name == "C3":
            if (ports := next_best(pj)) is None:
                print("p0c: C3 skipped: no port has a next-best reference", flush=True)
                return
            edits = {**edits, "ports": ports}
        pj = variant(out, name, edits)
        p0.step(out, sid, p0.model_key(pj), partial(fine_mesh, pj) if name == "C4a" else partial(command, pj, "run"))


def held(out: Path, name: str, record: dict) -> Path | None:
    """The project of the step `name` when its `record`'s command exited 0 and stored results that the project still
    holds (C2: its verify), else None: a variant that exits non-zero is not measured."""
    res = record["result"]
    if res.get("exit") != 0 or res.get("jobs") is None:
        return None
    pj = _project(out, name)
    stored = load_project(pj).get("verify" if name == "C2" else "results", {}) if pj.is_file() else {}
    return pj if Path(stored.get("run_dir", "")).name == res["run_dir"] else None


def traces(run_dir: str, jobs: list[dict]) -> list[tuple]:
    """p0.s_of's traces of a run's `jobs` (results' jobs: every port, in order) in the run folder named `run_dir`."""
    folder = p0.run_path(run_dir)
    exc = json.loads((folder / "model.json").read_text(encoding="utf-8"))["excitation"]
    dt = json.loads((folder / "job-0-setup" / "setup.json").read_text(encoding="utf-8"))["dt"]
    return [(pipeline.records(runs.job_dir(folder, k, job["port"]), len(jobs), dt), k - 1, exc, job["t_cut"])
            for k, job in enumerate(jobs, 1)]


def speeds(run_dir: str, jobs: list[dict]) -> list[float | None]:
    """Each job's openEMS speed in MC/s, from its openEMS_stats.txt; None for a job without one."""
    stats = [runs.job_dir(p0.run_path(run_dir), k, job["port"]) / "openEMS_stats.txt" for k, job in enumerate(jobs, 1)]
    return [read_stats(p.read_text(encoding="utf-8"))["speed"] / 1e6 if p.is_file() else None for p in stats]


def walls(run_dir: str, pool: int | None, stop_ns: dict) -> dict:
    """The wall time in s of the run's jobs at each preset of `stop_ns` (each job's stop time in ns, None for none),
    from the I_PROGRESS times of the run folder named `run_dir`: a job takes from its first progress line to the first
    at or past its stop time (its last for None). None without the pool or a job's progress lines."""
    # ponytail: a round model: each round of pool jobs starts when its slowest job would have stopped; a job's clock
    # starts at its first progress line, so its setup is not counted
    seen = {}
    for e in events(run_dir):
        if e["code"] == "I_PROGRESS":
            seen.setdefault(e["job"], []).append((e["t"], float(e["params"]["t_ns"])))

    def took(k: int, ns: float | None) -> float | None:
        lines = seen.get(k)
        if not lines:
            return None
        return next((t for t, at in lines if ns is not None and at >= round(ns, 2)), lines[-1][0]) - lines[0][0]

    out = {}
    for preset, cuts in stop_ns.items():
        d = [took(k, ns) for k, ns in enumerate(cuts, 1)]
        out[preset] = None if not pool or None in d else sum(max(d[i:i + pool]) for i in range(0, len(d), pool))
    return out


def validity(pj: Path, data: dict, cuts: list[float | None]) -> dict:
    """Criterion 2's values (spec 9.4, L586) on the layout N-port of C1's project `pj` (`data`) at the Normal cuts
    `cuts`: σ_max and the reciprocity error, each its largest over f, and the loss budget at f0 less loss_expected,
    the part ports closed as `run` closes them."""
    res = data["results"]
    lay = layout(data, {**res, "jobs": [{**job, "t_cut": t} for job, t in zip(res["jobs"], cuts, strict=True)]})
    ext, refs = [k for k, q in enumerate(lay.ports) if not q["part"]], [q["name"] for q in lay.ports if q["part"]]
    zk = loads(part_impedances(data, pj.parent, refs, lay.f)[0], refs, res["c_box"], lay.f)
    return {"sigma_max": float(sigma_max(lay.s).max()), "recip": float(recip_err(lay.s).max()),
            "loss_excess": float(loss_budget(lay.s, ext, zk)[lay.markers[0]] - res["loss_expected"])}


def judged(values: dict, limits: dict) -> dict:
    """`values` with "pass": each within its limit in `limits`; None when one is None (not measured, so not passed)."""
    return {**values, "pass": None if None in values.values() else all(values[k] <= v for k, v in limits.items())}


def measure(out: Path) -> dict:
    """The private report of the P0 folder `out`, from its step records (p0.records: one product code) and run
    folders. The base at Normal is C1's records replayed at Normal (p0.s_of, causal), closed as `run` closes them
    (p0.closed_chain with those cuts, PF-41); with C1 below Normal it, and so criteria 2 to 4 and the lid and band
    deltas, read None (PF-39). Criterion 1 is C2's verify against C1's run, criterion 2 on the base's layout N-port,
    criterion 3 C3's |ΔS21| in dB at f0 against the base, criterion 4 C4a's and C4b's; a criterion of a step that is
    absent, exited non-zero or ran against another C1 run reads None."""
    ids = [s for s in STEPS if (out / "steps" / f"p0c-{s}.json").is_file()]
    recs = dict(zip(ids, p0.records(out, [f"p0c-{s}" for s in ids])))
    pjs = {s: held(out, s, r) for s, r in recs.items()}
    summaries = {s: {**p0.summary(r), "codes": r["result"]["codes"]} for s, r in recs.items() if s != "S2P"}
    c0 = summaries.get("C0", {})
    m = {"mcells": c0.get("cells") and c0["cells"] / 1e6, "dt": c0.get("dt"), "stop_ns": {}, "s_dev": {}, "wall_s": {},
         "speeds_mcs": [], "ram_mb": None, "ram_mb_per_job": None, "ram_mb_per_mcell": None}
    f = f0 = s = k0 = c2 = c1_dir = None  # C1's grid and f0; the base at Normal on f and the index of f0 in f
    if pj1 := pjs.get("C1"):
        data, res, s1 = load_project(pj1), recs["C1"]["result"], summaries["C1"]
        c1_dir, f0 = res["run_dir"], data["f0_hz"]
        tr, f = traces(c1_dir, res["jobs"]), grid(f0, data["harmonics"], data["band_factor"])[0]
        own = p0.s_of(tr, f)[0]  # each job cut at its own t_cut
        presets = list(PRESETS)[:list(PRESETS).index(data["results"]["preset"]) + 1]  # every preset up to C1's
        replays = {p: p0.s_of(tr, f, p) for p in presets}
        cuts = {p: [None if math.isnan(t) else float(t) for t in times] for p, (_, times) in replays.items()}
        stop = {p: [None if t is None else t * 1e9 for t in c] for p, c in cuts.items()}
        used = res["ram_free_mb"][0] - res["ram_free_mb"][1]  # ponytail: system-wide free RAM
        per_job = used / s1["pool"] if s1["pool"] else None
        m |= {"stop_ns": stop, "s_dev": {p: float(np.abs(sp - own).max()) for p, (sp, _) in replays.items()},
              "wall_s": walls(c1_dir, s1["pool"], stop), "speeds_mcs": speeds(c1_dir, res["jobs"]), "ram_mb": used,
              "ram_mb_per_job": per_job,
              "ram_mb_per_mcell": per_job / (s1["cells"] / 1e6) if per_job is not None and s1["cells"] else None}
        if "normal" in cuts:
            _, s, k0 = p0.closed_chain(pj1, cuts=cuts["normal"])  # on f, the project's grid
            c2 = validity(pj1, data, cuts["normal"])

    def chain(name: str, **kw) -> np.ndarray | None:
        """The closed chain of the variant `name`, None when it is not measured or there is no base at Normal."""
        return p0.closed_chain(pjs[name], **kw)[1] if s is not None and pjs.get(name) else None

    def ds21(other: np.ndarray | None) -> float | None:
        """|ΔS21| in dB at f0 of `other` against the base at Normal."""
        return None if other is None else float(abs(20 * np.log10(abs(other[k0, 1, 0]) / abs(s[k0, 1, 0]))))

    def at_marks(other: np.ndarray | None) -> dict:
        """max |ΔS| over the entries of `other` against the base at Normal at f0, 2f0 and 3f0, each None when f does
        not hold it."""
        out_ = {}
        for name, n in MARKS.items():
            k = np.flatnonzero(np.isclose(f, n * f0, rtol=1e-9, atol=0)) if other is not None else []
            out_[name] = float(np.abs(other[k[0]] - s[k[0]]).max()) if len(k) else None
        return out_

    def fresh(name: str) -> bool:
        """Whether the record of `name` (C2, S2P) is keyed by C1's measured run."""
        return bool(c1_dir) and name in recs and recs[name]["key"].startswith(c1_dir)

    c1 = dict.fromkeys(("ds21_db_f0", "ds11_f0", "ds_max", "nulls", "within", "pass"))
    if pjs.get("C2") and fresh("C2"):
        cmp = load_project(pjs["C2"])["verify"]["compare"]
        within = p0.criterion1(cmp)
        c1 = {**{k: cmp[k] for k in ("ds21_db_f0", "ds11_f0", "ds_max", "nulls")}, "within": within,
              "pass": within["pass"]}
    s2p = {}
    if fresh("S2P"):
        mine = p0.closed_chain(pj1)[1]  # C1's chain with the part presets
        for row in recs["S2P"]["result"]["files"]:
            other = _project(out, f"S2P-{row['ref']}.{row['connection']}")
            s2p[row["file"]] = float(np.abs(p0.closed_chain(other)[1] - mine).max()) if row["exit"] == 0 else None
    c6 = summaries.get("C6", {})
    m |= {"lid_ds": at_marks(chain("C5")),
          "band_ds": {**at_marks(chain("C6", f=f)), "mcells": c6.get("cells") and c6["cells"] / 1e6,
                      "wall_s": c6.get("wall_s")},
          "s2p_ds": s2p, "s2p_ds_max": max((v for v in s2p.values() if v is not None), default=None)}
    criteria = {"c1": c1, "c2": judged(c2 or dict.fromkeys(LIMITS["c2"]), LIMITS["c2"]),
                "c3": judged({"ds21_db": ds21(chain("C3"))}, LIMITS["c3"]),
                "c4": judged({"n3_ds21_db": ds21(chain("C4a")), "margin_ds21_db": ds21(chain("C4b"))}, LIMITS["c4"])}
    c = {k: bool(v["pass"]) for k, v in criteria.items()}
    machine = p0.machine(list(recs.values()))
    return {"gate": "P0-C", "versions": p0.versions(),
            "calibration": runs.load_settings().get("machines", {}).get(runs.machine_key()),
            "criteria": criteria, "limits": LIMITS,
            "verdict": {"pass": c["c1"] and c["c2"] and c["c4"], "refine_mesh": not c["c4"],
                        "fallback": not (c["c1"] and c["c2"]), "prominent_reference": not c["c3"]},  # spec L599
            "measured": m,
            "cost": {e["code"]: e["params"] for e in events(c0.get("run_dir")) if e["kind"] == "cost"},
            "runs": summaries, "machine": {**machine, "loaded_steps": len(machine["loaded"])}}  # PF-38


def allowed(report: dict, spec: dict = PUBLIC) -> dict:
    """The keys of `spec` (PUBLIC or a part of it) in `report`: a dict recurses, a tuple names keys kept whole."""
    return {k: allowed(report[k], sub) if isinstance(sub, dict) else {key: report[k][key] for key in sub}
            for k, sub in spec.items()}


def _cell(v) -> str:
    """`v` as p0c.md shows it: None and an empty list as "–", a float as :.4g, a list's items and a dict's
    "key value" pairs joined by ", "."""
    if isinstance(v, dict):
        return ", ".join(f"{key} {_cell(x)}" for key, x in v.items())
    if isinstance(v, list):
        return ", ".join(map(_cell, v)) or "–"
    return "–" if v is None else f"{v:.4g}" if isinstance(v, float) else str(v)


def markdown(report: dict) -> str:
    """p0c.md: each section of the private `report` as a table, one row per key: the columns of its values when they
    are dicts that share their keys (the runs), else one "value" column."""
    blocks = ["# P0-C (private)"]
    for name, part in report.items():
        if not isinstance(part, dict):
            continue
        first = next(iter(part.values()), None)
        if isinstance(first, dict) and all(isinstance(v, dict) and v.keys() == first.keys() for v in part.values()):
            cols, rows = list(first), [{"item": k, **{c: _cell(v[c]) for c in first}} for k, v in part.items()]
        else:
            cols, rows = ["value"], [{"item": k, "value": _cell(v)} for k, v in part.items()]
        blocks.append(f"## {name}\n\n" + p0.table(rows, ["item", *cols]))
    return "\n\n".join(blocks) + "\n"


def write(out: Path) -> dict:
    """measure's report of the P0 folder `out` as <out>/report/p0c.json through p0.save, p0c.md beside it, and
    p0c-public.json, PUBLIC's keys only. Returns the report as saved."""
    report = p0.save(out / "report" / "p0c.json", measure(out))
    (out / "report" / "p0c.md").write_text(markdown(report), encoding="utf-8")
    p0.save(out / "report" / "p0c-public.json", allowed(report))
    return report


def main(argv: list[str] | None = None) -> int:
    """python tools/p0c.py … (D-46): exit 2 with one line, nothing written, when --out or --board lies inside a git
    work tree or --board is not a file. Else enters OUT, copies the board into OUT/board when it is missing, runs the
    steps of --steps (default every step, S2P only with --s2p) in STEPS' order, printing a step that raises and going
    on with the next, and writes the reports. Returns 1 when a step raised, else 0."""
    parser = argparse.ArgumentParser(prog="p0c", description="P0-C, the private board crop (spec 9.4).")
    parser.add_argument("--board", required=True, metavar="PATH", help="the board file, outside every git work tree")
    parser.add_argument("--start", required=True, metavar="REF.PAD", help="new's --start")
    parser.add_argument("--end", required=True, metavar="REF.PAD", help="new's --end")
    parser.add_argument("--f0", required=True, metavar="F", help="new's --f0")
    parser.add_argument("--harmonics", metavar="N", help="new's --harmonics")
    parser.add_argument("--lid-height", metavar="MM", help="new's --lid-height")
    parser.add_argument("--stackup", metavar="NAME", help="new's --stackup")
    parser.add_argument("--out", required=True, metavar="DIR", help="the P0-C folder, outside every git work tree")
    parser.add_argument("--preset", choices=PRESETS, default="strict", help="C1's preset (default strict)")
    parser.add_argument("--steps", metavar="C0,C1,...", help=f"the steps to run, among {','.join(STEPS)}")
    parser.add_argument("--s2p", metavar="DIR", help="a folder of <REF>.series.s2p and <REF>.shunt.s2p files")
    a = parser.parse_args(argv)
    steps = a.steps.split(",") if a.steps else [name for name in STEPS if name != "S2P" or a.s2p]
    if unknown := sorted(set(steps) - set(STEPS)):
        parser.error(f"unknown step: {', '.join(unknown)}")
    if "S2P" in steps and not a.s2p:
        parser.error("S2P needs --s2p DIR")
    board, out = Path(a.board), Path(a.out)
    if inside := next((path for path in (out, board) if p0.inside_git(path)), None):
        print(f"p0c: {inside} is inside a git work tree; choose a path outside every repository", file=sys.stderr)
        return 2
    if not board.is_file():
        print(f"p0c: {board} is not a file", file=sys.stderr)
        return 2
    out = p0.enter(out)
    if not (kept := out / "board" / board.name).is_file():
        kept.parent.mkdir(exist_ok=True)
        shutil.copy2(board, kept)
    failed = []
    for name in (name for name in STEPS if name in steps):
        print(f"p0c: {name}", flush=True)
        try:
            run_step(out, a, name)
        except Exception:  # logged and skipped; SystemExit (STOP) and KeyboardInterrupt end the tool
            failed.append(name)
            traceback.print_exc()
    write(out)
    print(f"p0c: reports in {out / 'report'}", flush=True)
    if failed:
        print(f"p0c: failed: {', '.join(failed)}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
