# SPDX-License-Identifier: GPL-3.0-or-later
"""P0-D and CI tier (b) (spec 9.5, 9.1; D-47, D-48): what .github/workflows/linux-openems.yml runs, and the writers of
the Windows fixtures it compares with. `models` builds each P0 model's spec with this code, mesh.reach_h pinned to the
P0 runs' (PIN), and the (model, port) matrix; `excite` runs one excitation at Draft in a fresh P0 folder; `compare`
judges each model's Linux S against its Windows reference under criterion 1, and a coupon's line constants within
ZE_LIMIT_PCT: tier (b)'s permanent trace-impedance regression test (spec L541). `references` (D-48) and `traces` (D-40)
write tests/fixtures/p0d and tests/fixtures/traces from a P0 folder's P0-A and P0-B records.

Dev-time only, like p0: the package never imports it. Run: python tools/p0d.py models --out DIR [--only M,…] |
excite --spec FILE --port K --out DIR | compare --runs DIR --refs DIR --models DIR --out FILE | references --p0 DIR
--out DIR [--only M,…] | traces --p0 DIR --out DIR [--only M,…]."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

import kicad_rf_studio.cli  # by module: p0 defines a cli of its own, the product's CLI as a child process
import p0
import p0a
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.checks import compare
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import BAND_FACTOR, HARMONICS, load_project, save_project
from kicad_rf_studio.stoprule import PRESETS
from p0b import harness

MODELS = (*p0a.COUPONS, "coupon_gcpw_pads", "lpf915")
NEW = {"coupon_gcpw_pads": p0a.PAD_NEW, "lpf915": harness.NEW}  # new's arguments, as P0-A and P0-B make them (PF-44)
STEPS = {**{name: f"p0a-{name}-n2" for name in p0a.COUPONS}, "coupon_gcpw_pads": "p0a-pad",
         "lpf915": "p0b-B1"}  # the step whose Windows run is each model's reference (D-48)
TRACES = ("coupon_gcpw_pads", "lpf915")  # the models whose step (STEPS) also gives trace fixtures (D-40)
PIN = p0a.PIN  # the P0 runs' reach, the one constant P0-A's harness pins too
FLOOR = 10 * PRESETS["draft"][1]  # the null floor, as verify derives it
ZE_LIMIT_PCT = 0.5  # Linux's Z0 and εeff against Windows': one model at one stop level, which r7 expects within 0.1 %
F = grid(p0a.F0, HARMONICS, BAND_FACTOR)[0]  # the co-simulation grid of every model (f0 915 MHz, 3 harmonics)


def judge(ref: dict, s: np.ndarray, model_hash: str) -> dict:
    """The Linux S `s` against the Windows reference `ref` (its npz members) on ref["f"] (D-47, D-48): checks.compare
    at f0 (the grid's index 71) with the Draft null floor, criterion 1 on it, and whether `model_hash`, the spec_hash
    of the model Linux ran, is the reference's: a mismatch is reported, never fatal."""
    cmp = compare(ref["S"], s, ref["f"], 71, FLOOR)
    return {"compare": cmp, "criterion1": p0.criterion1(cmp), "spec_hash_equal": str(ref["spec_hash"]) == model_hash}


def constants(name: str, job: Path, spec: dict, f: np.ndarray, t_cut: float) -> tuple[np.ndarray, np.ndarray]:
    """Re Z0 and εeff (points × f) of the coupon `name` in its job folder `job`, cut at `t_cut` (s; NaN for the whole
    record): each point of p0a.coupon_model at n = 2 with PIN, whose label and theta the probes do not hold (PF-46),
    read from its probes in the model spec `spec` by p0a.line_constants."""
    cut = None if np.isnan(t_cut) else float(t_cut)
    z0, eeff = zip(*(p0a.line_constants(job, [q for q in spec["probes"] if q["name"].rsplit("_", 1)[0] == pt["label"]],
                                        f, cut, pt["theta"]) for pt in p0a.coupon_model(name, 2, edits=PIN)[2]))
    return np.real(z0), np.array(eeff)


def models(out: Path, only: list[str] | None = None) -> list[dict]:
    """Writes out/<model>.json, the model spec this code builds of each of MODELS (or of `only`) with mesh.reach_h
    pinned (PIN), and out/matrix.json, the [{"model", "port"}] it returns, on one line for the workflow's matrix
    (PF-49): port 1 of a coupon, whose P0-A run excites P1 alone, every port of the others. A coupon is
    p0a.coupon_model at n = 2; coupon_gcpw_pads and lpf915 are made by `new`, in this process, into out/<model>/ when
    it is missing (NEW, PF-44), PIN saved, then built by pipeline.load and build_model."""
    matrix = []
    for name in (m for m in MODELS if only is None or m in only):
        if name in p0a.COUPONS:
            spec, ports = p0a.coupon_model(name, 2, edits=PIN)[0].spec, 1
        else:
            pj = out / name / "project.json"
            new = ["new", str(p0.FIX / f"{name}.kicad_pcb"), *NEW[name], "-o", str(pj.parent)]
            if not pj.is_file() and (code := kicad_rf_studio.cli.main(new)):
                raise SystemExit(f"p0d: new exited {code} on {name}")
            save_project(pj, p0.edit(load_project(pj), PIN))
            project, board, geom, _ = pipeline.load(pj)
            spec = pipeline.build_model(project, board, geom).spec
            ports = len(spec["ports"])
        p0.save(out / f"{name}.json", spec)
        matrix += [{"model": name, "port": k} for k in range(1, ports + 1)]
    (out / "matrix.json").write_text(json.dumps(matrix, separators=(",", ":")) + "\n", encoding="utf-8")
    return matrix


def excite(spec_path: Path, port: int, out: Path) -> dict:
    """One excitation of the matrix (D-47): enters the P0 folder `out` first (D-7: outside every work tree), then runs
    the model spec at `spec_path` on port `port` (1-based) at Draft through p0.run_model, in a run folder named after
    the spec's file and the port. Returns run_model's result, also written as out/result.json."""
    out = p0.enter(out)
    run = p0.run_model(p0.model_of(harness._read(spec_path)), "draft", f"{spec_path.stem}-k{port}", [port])
    return p0.save(out / "result.json", run)


def references(p0_dir: Path, out: Path, models: tuple[str, ...] = MODELS) -> list[Path]:
    """The Windows references (D-48), from the P0 folder `p0_dir`, entered first (never `out`: tests/fixtures/p0d is
    inside the work tree): each model's record (STEPS), read with one p0.records call per harness, since the two may
    have run on different product code (PF-43); its jobs' records replayed at Draft on F (p0.s_of, tails included:
    exact, by causality), written as out/<model>.npz: f, S, t_cut, spec_hash (of its run's model.json) and, for a
    coupon, z0 and eeff at the Draft cut (constants). Returns the paths."""
    p0_dir = p0.enter(p0_dir)
    recs = {}
    for prefix in ("p0a-", "p0b-"):  # PF-43
        ids = [STEPS[name] for name in models if STEPS[name].startswith(prefix)]
        recs |= zip(ids, p0.records(p0_dir, ids))
    paths = []
    for name in models:
        res = recs[STEPS[name]]["result"]
        folder = p0.run_path(res["run_dir"])
        spec = harness._read(folder / "model.json")
        s, cuts = p0.s_of(harness._traces(res["run_dir"], res["jobs"]), F, "draft")
        lines = {}
        if name in p0a.COUPONS:
            lines = dict(zip(("z0", "eeff"), constants(name, folder / res["jobs"][0]["job"], spec, F, cuts[0])))
        out.mkdir(parents=True, exist_ok=True)
        paths.append(out / f"{name}.npz")
        np.savez_compressed(paths[-1], f=F, S=s, t_cut=cuts, spec_hash=np.array(spec_hash(spec)), **lines)
    return paths


def traces(p0_dir: Path, out: Path, models: tuple[str, ...] = TRACES) -> list[Path]:
    """The trace fixtures (D-40) of `models`, from the P0 folder `p0_dir`, entered first: p0.save_trace of the jobs of
    each one's record (STEPS: the pad coupon's two, p0a-pad, and B1's six, p0b-B1), each record read on its own (PF-43)
    and no other one, as out/<model>-k<k>.npz, k the job's port number, with its live t_cut. SystemExit naming every job
    whose live verdict (p0.summary's: the stored results, else the verdict events) is not "converged", before any file
    is written: the fixtures are the live converged branch. Returns the paths."""
    p0_dir = p0.enter(p0_dir)
    todo, bad = [], []
    for name in models:
        (record,) = p0.records(p0_dir, [STEPS[name]])
        folder = p0.run_path(record["result"]["run_dir"])
        spec, dt = harness._read(folder / "model.json"), harness._read(folder / "job-0-setup" / "setup.json")["dt"]
        names = [q["name"] for q in spec["ports"]]
        for job in p0.summary(record)["jobs"]:
            k = names.index(job["port"]) + 1
            if job["verdict"] != "converged":
                bad.append(f"{name}-k{k} ended {job['verdict']}")
            todo.append((runs.job_dir(folder, k, job["port"]), len(names), dt, k, spec["excitation"], job["t_cut"],
                         out / f"{name}-k{k}.npz"))
    if bad:
        raise SystemExit(f"p0d: {', '.join(bad)}, not converged; a trace fixture is the live converged branch (D-40)")
    return [p0.save_trace(*args) for args in todo]


def compare_runs(runs_dir: Path, refs: Path, models_dir: Path) -> dict:
    """The verdict of P0-D and tier (b) (D-47): per reference <model>.npz in `refs`, the Linux records of each of its
    excitations k = 1..its S's columns (PF-45), from runs_dir/<model>-k<k>/: its result.json and the job folder in its
    own data folder, never through p0.run_path (PF-47); replayed at Draft on the reference's f and judged against it.
    A model with an excitation missing fails, naming it. A coupon's max |ΔZ0| and |Δεeff| in %, over its points and f,
    against the reference (the probes of models_dir/<model>.json) must also be within ZE_LIMIT_PCT. SystemExit when
    `refs` holds no reference. Returns {"models": {model: judge's plus "dz0_pct" and "deeff_pct" (None but for a
    coupon) and "pass", or "missing" and "pass"}, "pass": every model passed}."""
    paths = sorted(refs.glob("*.npz"))
    if not paths:
        raise SystemExit(f"p0d: no reference in {refs}")
    out = {}
    for path in paths:
        name = path.stem
        with np.load(path) as z:
            ref = dict(z)
        folders = [runs_dir / f"{name}-k{k}" for k in range(1, ref["S"].shape[2] + 1)]
        if missing := [d.name for d in folders if not (d / "result.json").is_file()]:
            out[name] = {"missing": missing, "pass": False}
            continue
        spec, jobs = harness._read(models_dir / f"{name}.json"), []
        for d in folders:
            res = harness._read(d / "result.json")
            jobs.append((d / "data" / "kicad-rf-studio" / "runs" / res["run_dir"] / res["jobs"][0]["job"],
                         res["setup"]["dt"]))
        s, cuts = p0.s_of([(pipeline.records(job, len(spec["ports"]), dt), k, spec["excitation"], None)
                           for k, (job, dt) in enumerate(jobs)], ref["f"], "draft")
        judged, dz0, deeff = judge(ref, s, spec_hash(spec)), None, None
        if name in p0a.COUPONS:
            lines = zip(constants(name, jobs[0][0], spec, ref["f"], cuts[0]), (ref["z0"], ref["eeff"]))
            dz0, deeff = (float(np.abs(100 * (mine / theirs - 1)).max()) for mine, theirs in lines)
        out[name] = {**judged, "dz0_pct": dz0, "deeff_pct": deeff,
                     "pass": judged["criterion1"]["pass"] and (dz0 is None or max(dz0, deeff) <= ZE_LIMIT_PCT)}
    return {"models": out, "pass": all(m["pass"] for m in out.values())}


def main(argv: list[str] | None = None) -> int:
    """python tools/p0d.py models|excite|compare|references|traces … (D-47, D-48). A command that runs or reads a P0
    folder enters it first (D-7). The --only of models, references and traces picks among that command's models
    (MODELS, or TRACES for traces); any other name is a parser error. compare writes its result to its --out and
    returns 1 when a model fails; the others return 0."""
    parser = argparse.ArgumentParser(prog="p0d", description="P0-D and CI tier (b) (spec 9.5, 9.1).")
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("models", help="write each model spec and matrix.json")
    cmd.add_argument("--out", required=True, type=Path, metavar="DIR")
    cmd.add_argument("--only", metavar="M,...", help=f"the models, comma-separated, among {','.join(MODELS)}")
    cmd = commands.add_parser("excite", help="run one excitation of a model spec at Draft")
    cmd.add_argument("--spec", required=True, type=Path, metavar="FILE")
    cmd.add_argument("--port", required=True, type=int, metavar="K")
    cmd.add_argument("--out", required=True, type=Path, metavar="DIR", help="a P0 folder, outside every work tree")
    cmd = commands.add_parser("compare", help="judge the Linux runs against the Windows references")
    for flag in ("--runs", "--refs", "--models"):
        cmd.add_argument(flag, required=True, type=Path, metavar="DIR")
    cmd.add_argument("--out", required=True, type=Path, metavar="FILE")
    for name, text, among in (("references", "write the Windows references (D-48)", MODELS),
                              ("traces", "write the traces (D-40)", TRACES)):
        cmd = commands.add_parser(name, help=text)
        cmd.add_argument("--p0", required=True, type=Path, metavar="DIR", help="the P0 folder")
        cmd.add_argument("--out", required=True, type=Path, metavar="DIR")
        cmd.add_argument("--only", metavar="M,...", help=f"the models, comma-separated, among {','.join(among)}")
    a = parser.parse_args(argv)
    known = TRACES if a.command == "traces" else MODELS
    only = a.only.split(",") if getattr(a, "only", None) else None  # excite and compare take no --only
    if unknown := sorted(set(only or ()) - set(known)):
        parser.error(f"unknown model: {', '.join(unknown)}")
    if a.command == "models":
        models(a.out, only)
    elif a.command == "excite":
        excite(a.spec, a.port, a.out)
    elif a.command == "compare":
        result = p0.save(a.out, compare_runs(a.runs, a.refs, a.models))
        for name, m in result["models"].items():
            print(f"p0d: {name}: {'pass' if m['pass'] else 'fail'}", *m.get("missing", []), flush=True)
        return 0 if result["pass"] else 1
    else:
        for path in (references if a.command == "references" else traces)(a.p0, a.out, tuple(only or known)):
            print(path, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
