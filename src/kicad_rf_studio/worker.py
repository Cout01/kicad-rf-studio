# SPDX-License-Identifier: GPL-3.0-or-later
"""One openEMS job (spec 6), started as `<python> -I -u -m kicad_rf_studio.worker job.json` in its own job folder.
job.json is {"spec": "../model.json", "port": the excited port (1-based), "mode": "run" | "setup" | "xml" | "nf2ff",
"threads", "t_max"}, mode "nf2ff" adding "dumps" (the finished job's folder, relative) and "out" (the outputs' stem);
the job writes waves.npz, setup.json, model.xml or, in mode "nf2ff" (the far-field transform, Stage 3 design 5.5),
<dumps>/<out>-<grid>.h5 for each grid of GRIDS. It exits 0 when done, 2 when openEMS does not import and SETUP_FAILED
when openEMS's setup fails; any other code is a crash. Standard library and numpy only: openEMS and CSXCAD load inside
build_csx (spec 3.1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from kicad_rf_studio.core.model.csx import build_csx
from kicad_rf_studio.core.model.readers import c_box, curve_edge, pec_roots, read_log, read_probe, read_unused

LOG, ERR = "log.txt", "err.txt"  # the orchestrator sends the worker's stdout and stderr there
SETUP_FAILED = 10
DUMPS = tuple(f"nf2ff_{q}_{n}.h5" for q in "EH" for n in range(6))  # the far-field box's E and H on each face
# design 5.5: the full sphere at 5° at every recorded frequency; the XZ (φ 0°) and YZ (φ 90°) cuts as one θ sweep and
# the XY cut (θ 90°) as a φ sweep, at 1° at f0
# ponytail: fixed steps; plan 2's angle-step field passes its own
GRIDS: dict[str, tuple[np.ndarray, np.ndarray, bool]] = {  # θ in degrees, φ in degrees, f0 only
    "sphere": (np.arange(0, 181, 5), np.arange(0, 360, 5), False),
    "elevation": (np.arange(-180, 180, 1), np.array([0, 90]), True),
    "azimuth": (np.array([90]), np.arange(0, 360, 1), True)}


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


def _far_field(job: dict, spec: dict, box: object) -> None:
    """Mode "nf2ff" (Stage 3 design 5.5): the far field of the finished job in job["dumps"] (relative), one CalcNF2FF
    per grid of GRIDS, always read_cached=False, written to <dumps>/<job["out"]>-<grid>.h5, a name no other call uses:
    the sphere at every recorded frequency, the cuts at f0 (the first), about spec["nf2ff"]["center"] (mm; CalcNF2FF
    takes metres). FileNotFoundError naming the first missing dump, before any transform: CalcNF2FF skips a face whose
    files are missing and integrates the rest."""
    for name in DUMPS:
        if not (path := Path(job["dumps"]) / name).is_file():
            msg = f"{path}: the job ended before its far field was recorded"
            print(msg, flush=True)  # the job's log.txt, which E_WORKER_FAILED names; the traceback goes to err.txt
            raise FileNotFoundError(msg)
    nf = spec["nf2ff"]
    center = [c * 1e-3 for c in nf["center"]]
    for grid, (theta, phi, f0_only) in GRIDS.items():
        box.CalcNF2FF(job["dumps"], nf["f_hz"][:1] if f0_only else nf["f_hz"], theta, phi, center=center,
                      outfile=f"{job['out']}-{grid}.h5", read_cached=False)


def main(argv: list[str] | None = None) -> int:
    """Runs the job of job.json (argv[0]) in the current folder, its job folder: openEMS gets only relative paths."""
    Path("ABORT").unlink(missing_ok=True)  # a stale ABORT would stop the run at its first step (C-20)
    job = json.loads(Path((sys.argv[1:] if argv is None else argv)[0]).read_text(encoding="utf-8"))
    spec = json.loads(Path(job["spec"]).read_text(encoding="utf-8"))
    try:
        _, fdtd, box = build_csx(spec, job["port"], job["t_max"])
    except ImportError:
        return 2
    # ponytail: the whole CSX rebuilt for openEMS's box; on a board, build only the box from model.json's lines if plan
    # 2 measures it slow
    if job["mode"] == "nf2ff":
        _far_field(job, spec, box)
        return 0
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
