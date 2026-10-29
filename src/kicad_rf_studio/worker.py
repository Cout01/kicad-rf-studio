# SPDX-License-Identifier: GPL-3.0-or-later
"""One openEMS job (spec 6), started as `<python> -I -u -m kicad_rf_studio.worker job.json` in its own job folder.
job.json is {"spec": "../model.json", "port": the excited port (1-based), "mode": "run" | "setup" | "xml",
"threads", "t_max"}; the job writes waves.npz, setup.json or model.xml. It exits 0 when done, 2 when openEMS does not
import and SETUP_FAILED when openEMS's setup fails; any other code is a crash. Standard library and numpy only:
openEMS and CSXCAD load inside build_csx (spec 3.1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from kicad_rf_studio.core.model.csx import build_csx
from kicad_rf_studio.core.model.readers import c_box, curve_edge, pec_roots, read_log, read_probe, read_unused

LOG, ERR = "log.txt", "err.txt"  # the orchestrator sends the worker's stdout and stderr there
SETUP_FAILED = 10


def run_kwargs(mode: str, threads: int, parts: bool) -> dict:
    """The keywords of fdtd.Run for `mode` ("run" or "setup"), the operator dump only when a port holds a part
    (C-18). Never a False, which drops the options after it (spec 11), and never exact_endcriteria."""
    if mode == "run":
        return {"numThreads": threads, "dump_statistics": True}
    kw = {"setup_only": True, "verbose": 2, "numThreads": threads, "debug_PEC": True}
    return {**kw, "debug_operator": True} if parts else kw


def _waves(ports: int) -> dict[str, np.ndarray]:
    """{"t_u", "u", "t_i", "i"} from the probe files port_ut_k and port_it_k, k = 1..`ports`, cut to the shortest."""
    probes = {q: [read_probe(Path(f"port_{q}t_{k}").read_text(encoding="utf-8")) for k in range(1, ports + 1)]
              for q in "ui"}
    n = min(len(t) for files in probes.values() for t, _ in files)
    waves = {}
    for q, files in probes.items():
        cut = np.array([[t[:n], v[:n]] for t, v in files])  # port × (time, value) × sample
        waves[f"t_{q}"], waves[q] = cut[0, 0], cut[:, 1]
    return waves


def _box(lines: list, port: dict) -> tuple[list, list, int]:
    """The start, stop and axis of the box of `port` that its C_box counts: a lumped port's own box, a CurvePort's one
    edge (curve_edge)."""
    if port["kind"] != "curve":
        return port["start"], port["stop"], "xyz".index(port["dir"])
    axis, i = curve_edge(lines, port["start"], port["stop"])
    return [lines[n][i[n]] for n in range(3)], [lines[n][i[n] + (n == axis)] for n in range(3)], axis


def _setup(spec: dict) -> dict:
    """setup.json: dt, cells and node from the log; the properties stderr says place nothing (C-16); the dump files
    written; the PEC roots of each port's nodes (C-15); the C_box of each port with a part at the log's dt (C-18), over
    its box (_box)."""
    log = read_log(Path(LOG).read_text(encoding="utf-8"))
    if (dt := log["dt"]) is None:
        raise RuntimeError(f"{LOG} holds no FDTD timestep")
    lines = [spec["mesh"][a] for a in "xyz"]
    ports = spec["ports"]
    return {"dt": dt, "cells": log["cells"], "node": log["node"],
            "unused": read_unused(Path(ERR).read_text(encoding="utf-8")),
            "dumps": sorted(f.name for f in Path().glob("*_dump.*")),
            "pec": [pec_roots(Path("PEC_dump.vtp"), lines, p["nodes"]) for p in ports],
            "c_box": {p["name"]: c_box(Path("operator_dump.vtr"), lines, *_box(lines, p), dt)
                      for p in ports if p["part"]}}


def main(argv: list[str] | None = None) -> int:
    """Runs the job of job.json (argv[0]) in the current folder, its job folder: openEMS gets only relative paths."""
    Path("ABORT").unlink(missing_ok=True)  # a stale ABORT would stop the run at its first step (C-20)
    job = json.loads(Path((sys.argv[1:] if argv is None else argv)[0]).read_text(encoding="utf-8"))
    spec = json.loads(Path(job["spec"]).read_text(encoding="utf-8"))
    try:
        _, fdtd, _ = build_csx(spec, job["port"], job["t_max"])
    except ImportError:
        return 2
    if job["mode"] == "xml":
        fdtd.Write2XML("model.xml")  # C-34
        return 0
    rc = fdtd.Run(".", **run_kwargs(job["mode"], job["threads"], any(p["part"] for p in spec["ports"])))
    if rc:  # openEMS returns its setup's error code, None after a full run
        return SETUP_FAILED
    if job["mode"] == "run":
        np.savez("waves.npz", **_waves(len(spec["ports"])))
    else:
        Path("setup.json").write_text(json.dumps(_setup(spec)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
