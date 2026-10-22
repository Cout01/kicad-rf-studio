# SPDX-License-Identifier: GPL-3.0-or-later
"""Build tests/fixtures/microstrip: the waves of a real openEMS run of tools/make_dumps.py's microstrip, for the
tests of the reduction that run without openEMS (tests/test_post_real.py).

Dev-time only: it runs in the dev venv, and the product never imports it. It imports neither openEMS nor CSXCAD: it
writes a model spec and starts kicad_rf_studio.worker in each job folder as a run does, so the worker's Python needs
openEMS (setup-openems). Regenerate from the repository root with

    python tools/make_waves.py [OUT] [T_MAX]

OUT defaults to tests/fixtures/microstrip and T_MAX to 15e-9 s. The jobs run in a new run folder in the data folder
(runs.run_dir_for, never the system temp), which stays there. OUT gets job-1.npz and job-2.npz, the waves.npz of the
jobs that excite P1 and P2, and meta.json: job 1's dt (s) as openEMS_stats.txt holds it, the setup's C_box of P1 (F),
f0 and the band [f1, f2] (Hz).
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np

from kicad_rf_studio import runs
from kicad_rf_studio.core.model.readers import read_stats
from kicad_rf_studio.core.model.spec import excitation, kappa

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "microstrip"
F0 = 915e6


def rect(x0, x1, y0, y1, z0, z1) -> dict:
    """The box x0–x1 × y0–y1 × z0–z1 (mm) as a model spec's solid."""
    return {"x": [x0, x1, x1, x0], "y": [y0, y0, y1, y1], "z": [z0, z1]}


def microstrip(t_max: float) -> dict:
    """tools/make_dumps.py's microstrip as a model spec, run up to `t_max` s: its ground a PEC slab under z = 0, as a
    model spec has no zero-thickness sheet, and both ports marked as parts, so the setup job dumps the operator."""
    def port(k: int, x: float) -> dict:
        return {"name": f"P{k}", "kind": "lumped", "dir": "z", "start": [x, -0.5, 0.0], "stop": [x, 0.5, 0.5],
                "nodes": [[x, 0, 0], [x, 0, 0.5], [x, 2, 0], [0, 0, 0.535]], "part": True}

    return {"mesh": {"x": np.arange(-8, 8.001, 0.25).round(6).tolist(),
                     "y": np.arange(-4, 4.001, 0.25).round(6).tolist(),
                     "z": [-1, -0.5, 0, 0.125, 0.25, 0.375, 0.5, 0.535, 0.6, 0.75, 1, 1.5, 2, 2.5, 3, 3.5]},
            "excitation": excitation({"f0_hz": F0, "harmonics": 3, "band_factor": 1.1, "t_max_s": t_max}),
            "materials": [{"name": "substrate_0", "eps": 4.3, "kappa": kappa(4.3, 0.02, F0), "priority": 10,
                           "solids": [rect(-8, 8, -4, 4, 0.0, 0.5)]}],
            "metal": {"copper": [rect(-8, 8, -4, 4, -0.5, 0.0), rect(-5, 5, -0.5, 0.5, 0.5, 0.535)],
                      "lid": {"plate": None, "walls": []}, "cylinders": [], "curves": []},
            "ports": [port(1, -5.0), port(2, 5.0)],
            "grid": []}


def main(out: Path = OUT, t_max: float = 15e-9) -> None:
    """Runs the microstrip's setup job and the jobs that excite P1 and P2, all at once at 4 threads each, and writes
    the fixture to `out`. Raises what check_job raises."""
    run_dir, spec, settings = runs.run_dir_for("make_waves"), microstrip(t_max), runs.load_settings()
    runs.write_spec(run_dir, spec)
    jobs = {name: runs.write_job(runs.job_dir(run_dir, k, name), port, mode, 4, t_max)
            for k, name, port, mode in ((0, "setup", 1, "setup"), (1, "P1", 1, "run"), (2, "P2", 2, "run"))}
    ends = runs.run_jobs(list(jobs.values()), 3, run_dir, settings)
    for name, job in jobs.items():
        runs.check_job(job, ends[job], name, settings)
    out.mkdir(parents=True, exist_ok=True)
    for k in (1, 2):
        shutil.copyfile(jobs[f"P{k}"] / "waves.npz", out / f"job-{k}.npz")
    meta = {"dt": read_stats((jobs["P1"] / "openEMS_stats.txt").read_text(encoding="utf-8"))["dt"],
            "c_box": json.loads((jobs["setup"] / "setup.json").read_text(encoding="utf-8"))["c_box"]["P1"],
            "f0_hz": F0, "band": [spec["excitation"]["f1"], spec["excitation"]["f2"]]}
    (out / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(*(cast(arg) for cast, arg in zip((Path, float), sys.argv[1:])))  # OUT and T_MAX, each optional
