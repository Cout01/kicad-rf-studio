# SPDX-License-Identifier: GPL-3.0-or-later
"""Stands in for kicad_rf_studio.worker, run as `python -I -u tests/fake_worker.py job.json` in a job folder: it writes
what openEMS and the worker would, from tests/traces.py, in milliseconds and without openEMS. $KRS_FAKE_EXIT is an
exit code and $KRS_FAKE "hang" a worker that never ends, in any mode; otherwise $KRS_FAKE is the run's kind:
"converge" (the default), "slow", "crash" (only on port $KRS_FAKE_JOB when it is set) or a kind of traces.trace.
$KRS_FAKE_SETUP is JSON that setup.json takes, and $KRS_FAKE_LOG a file that gets a line as each fake starts and
ends."""
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))  # -I leaves the script's folder off sys.path
from traces import trace  # noqa: E402

DT = 1e-13  # s, the fake's FDTD timestep


def note(what: str, port: int) -> None:
    """Appends `<what> <port> <time>` to $KRS_FAKE_LOG when it is set. The time has a fixed width: appends are not
    atomic on Windows, and two fakes that start (or end) at once then lose a line rather than garble one."""
    if path := os.environ.get("KRS_FAKE_LOG"):
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{what} {port} {time.time():.6f}\n")


def run(job: dict, spec: dict) -> int:
    """Mode "run": the records of the kind, sample by sample as openEMS writes them, until an ABORT file appears;
    "slow" converges at 0.2 s per sample, and "crash" writes the converging samples up to 12 ns, ignoring ABORT, and
    exits 7 with no waves.npz."""
    kind, ports, ex = os.environ.get("KRS_FAKE", "converge"), range(1, len(spec["ports"]) + 1), spec["excitation"]
    if kind == "crash" and os.environ.get("KRS_FAKE_JOB", str(job["port"])) != str(job["port"]):
        kind = "converge"
    rec = trace(kind, len(ports), job["port"] - 1, ex["f1"], ex["f2"], t_end=job["t_max"])  # "slow", "crash" converge
    steps, end = round(job["t_max"] / DT), 12e-9 if kind == "crash" else math.inf
    print(f"Max. number of timesteps: {steps}")
    probes = [(open(f"port_{q}t_{k}", "w", encoding="utf-8"), t, v[k - 1])
              for k in ports for q, t, v in (("u", rec.t_u, rec.u), ("i", rec.t_i, rec.i))]
    for f, _, _ in probes:
        print("% t/s\tvalue", file=f, flush=True)
    stats, start, n = open("openEMS_run_stats.txt", "w", encoding="utf-8"), time.time(), 0
    while n < len(rec.t_u) and rec.t_u[n] < end and (kind == "crash" or not Path("ABORT").exists()):
        for f, t, v in probes:
            print(f"{t[n]}\t{v[n]}", file=f, flush=True)
        print(f"{time.time() - start:.6f}\t{round(rec.t_u[n] / DT)}\t5e+07\t{rec.e[n]}", file=stats, flush=True)
        n += 1
        time.sleep(0.2 if kind == "slow" else 0.001)
    if kind == "crash":
        return 7
    iterations = steps if n == len(rec.t_u) else round(rec.t_u[n] / DT)
    cells = math.prod(len(spec["mesh"][a]) for a in "xyz")
    print(f"Time for {iterations} iterations with {cells} cells : 1.00 sec")
    Path("openEMS_stats.txt").write_text("".join(f"{v}\n" for v in (cells, DT, iterations, iterations * DT, 1.0,
                                                                     5e7 * job["threads"])), encoding="utf-8")
    np.savez("waves.npz", t_u=rec.t_u[:n], u=rec.u[:, :n], t_i=rec.t_i[:n], i=rec.i[:, :n])
    return 0


def act(job: dict, spec: dict) -> int:
    """What the fake does in its job's mode, as $KRS_FAKE* ask; returns the exit code."""
    if "KRS_FAKE_EXIT" in os.environ:
        return int(os.environ["KRS_FAKE_EXIT"])
    if os.environ.get("KRS_FAKE") == "hang":
        time.sleep(600)
        return 0
    if job["mode"] == "setup":
        ports = spec["ports"]
        setup = {"dt": DT, "cells": [len(spec["mesh"][a]) for a in "xyz"], "node": [2, 0, 0, 1], "unused": [],
                 "dumps": [], "pec": [[1, 2, 1, 2] if p["kind"] == "lumped" else [1, 2] for p in ports],
                 "c_box": {p["name"]: 2e-14 for p in ports if p["part"]}}
        setup.update(json.loads(os.environ.get("KRS_FAKE_SETUP") or "{}"))
        Path("setup.json").write_text(json.dumps(setup), encoding="utf-8")
        return 0
    if job["mode"] == "xml":
        Path("model.xml").write_text("<openEMS/>", encoding="utf-8")
        return 0
    return run(job, spec)


def main() -> int:
    """Writes env.json, then does the job of job.json (argv[1]) in the current folder, its job folder."""
    seen ={"cwd": os.getcwd(), "pid": os.getpid(), "isolated": sys.flags.isolated,
            **{name: os.environ.get(name) for name in ("OPENBLAS_NUM_THREADS", "CSXCAD_INSTALL_PATH")}}
    Path("env.json").write_text(json.dumps(seen), encoding="utf-8")
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    spec = json.loads(Path(job["spec"]).read_text(encoding="utf-8"))
    note("start", job["port"])
    code = act(job, spec)
    note("end", job["port"])
    return code


if __name__ == "__main__":
    sys.exit(main())
