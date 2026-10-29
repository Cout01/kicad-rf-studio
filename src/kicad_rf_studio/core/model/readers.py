# SPDX-License-Identifier: GPL-3.0-or-later
"""Readers of openEMS's output (v0.37.0): its log and stderr, the probes, the statistics and the VTK dumps; from the
dumps, the PEC pieces of the ports' nodes (C-15) and the capacitance of a port box (C-18), a CurvePort's being its one
edge (curve_edge). Standard library and numpy only: the worker imports this module."""
from __future__ import annotations

import base64
import itertools
import math
import re
import zlib
from pathlib import Path
from xml.etree import ElementTree

import numpy as np

CELLS = ("Verts", "Lines", "Strips", "Polys")  # the cell blocks of a .vtp, each with its connectivity and offsets


def _num(token: str) -> float:
    """`token` as a float; one float() refuses that holds "nan" or "inf" (MSVC's -nan(ind)) reads as NaN or ±inf."""
    try:
        return float(token)
    except ValueError:
        low = token.lower()
        if "nan" in low:
            return math.nan
        if "inf" in low:
            return -math.inf if low.startswith("-") else math.inf
        raise


def _columns(text: str, n: int) -> np.ndarray:
    """The `n` columns of the complete lines of `text` (a partial last line is ignored), "%" and blank lines skipped."""
    rows = [[_num(t) for t in line.split()] for line in text.split("\n")[:-1]
            if line.strip() and not line.startswith("%")]
    return np.array(rows, dtype=float).reshape(len(rows), n).T


def read_probe(text: str) -> tuple[np.ndarray, np.ndarray]:
    """The time (s) and value columns of an openEMS probe file, CRLF or LF, complete lines only."""
    t, v = _columns(text, 2)
    return t, v


def read_run_stats(text: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The timestep, speed (cells/s) and energy columns of openEMS_run_stats.txt, complete rows only."""
    _, steps, speed, energy = _columns(text, 4)
    return steps, speed, energy


def read_stats(text: str) -> dict | None:
    """openEMS_stats.txt, one value per line: the cells, the timestep dt (s), the iterations, the simulated time
    sim_time (s), the wall-clock time wall (s) and the speed (cells/s). None when it holds fewer than six complete
    lines: a job killed while openEMS wrote it."""
    v = [_num(line.split()[0]) for line in text.split("\n")[:-1] if line.strip()]
    if len(v) < 6:
        return None
    return {"cells": int(v[0]), "dt": v[1], "iterations": int(v[2]), "sim_time": v[3], "wall": v[4], "speed": v[5]}


def read_log(text: str) -> dict:
    """From openEMS's log: the grid size `cells` [nx, ny, nz], the timestep `dt` (s, 6 significant digits), the `node`
    [n, i, j, k] of the smallest timestep (verbose 2), the maximum number of timesteps `nrts` and the `iterations`
    run; None for each the log does not hold."""
    def ints(pattern: str) -> list[int] | None:
        m = re.search(pattern, text)
        return None if m is None else [int(g) for g in m.groups()]

    dt = re.search(r"FDTD timestep is: (\S+) s", text)
    nrts, iterations = ints(r"Max\. number of timesteps: (\d+)"), ints(r"Time for (\d+) iterations")
    return {"cells": ints(r"FDTD simulation size: (\d+)x(\d+)x(\d+) -->"),
            "dt": None if dt is None else float(dt[1]),
            "node": ints(r"found at position: (\d+) : (\d+);(\d+);(\d+)"),
            "nrts": None if nrts is None else nrts[0],
            "iterations": None if iterations is None else iterations[0]}


def read_unused(text: str) -> list[list[str]]:
    """The properties stderr says place nothing (C-16), in order: an unused primitive as [type, property], a property
    without primitives as ["none", property] and a box outside the field domain as ["outside", property]."""
    out = []
    for line in text.splitlines():
        if m := re.search(r"Unused primitive \(type: ([^)]+)\) detected in property: (.+?)!", line):
            out.append([m[1], m[2]])
        elif m := re.search(r"No primitives found in property: (.+?)!", line):
            out.append(["none", m[1]])
        elif m := re.search(r"Warning in (\S+) \(.*\) : Box is outside the field domain!! Disabling", line):
            out.append(["outside", m[1]])
    return out


def _array(s: str, at: int, dtype: str) -> np.ndarray:
    """The array whose base64 starts at `at` in `s`: base64(header) + base64(zlib blocks), the header UInt32
    [nblocks, blocksize, lastblocksize, csize_1..n] (r5); its data is the decompressed blocks joined."""
    n = int.from_bytes(base64.b64decode(s[at:at + 8])[:4], "little")
    h = 4 * math.ceil(4 * (3 + n) / 3)
    sizes = np.frombuffer(base64.b64decode(s[at:at + h]), "<u4")[3:].tolist()
    data = base64.b64decode(s[at + h:at + h + 4 * math.ceil(sum(sizes) / 3)])
    ends = itertools.accumulate(sizes)
    return np.frombuffer(b"".join(zlib.decompress(data[e - c:e]) for c, e in zip(sizes, ends)), dtype)


def read_vtk(path: Path) -> dict[str, np.ndarray]:
    """Every DataArray of the VTK XML file at `path` (openEMS's dumps: little-endian, zlib, base64, appended in a .vtp
    with offsets in characters after the "_", inline in a .vtr) by name, flat: a cell array as "<block>/<name>"
    ("Lines/connectivity", "Lines/offsets", ...) and the Coordinates as "x", "y" and "z" by position (their names are
    pointer addresses)."""
    root = ElementTree.parse(path).getroot()
    appended = root.find("AppendedData")
    tail = "" if appended is None else appended.text.split("_", 1)[1]
    out = {}
    for parent in root.iter():
        for n, a in enumerate(parent.iterfind("DataArray")):
            name = "xyz"[n] if parent.tag == "Coordinates" else a.get("Name")
            if parent.tag in CELLS:
                name = f"{parent.tag}/{name}"
            text, at = (tail, int(a.get("offset"))) if a.get("format") == "appended" else (a.text.strip(), 0)
            out[name] = _array(text, at, a.get("type").lower())
    return out


def _nearest(lines, v) -> np.ndarray:
    """The index of the line of `lines` (ascending) nearest each of `v`."""
    lines = np.asarray(lines, dtype=float)
    return np.searchsorted((lines[1:] + lines[:-1]) / 2, v)


def _flat(lines, xyz) -> list[int]:
    """The index i + nx·(j + ny·k) of the grid node nearest each point of `xyz` (n × 3, in the unit of `lines`)."""
    i, j, k = (_nearest(a, v) for a, v in zip(lines, np.asarray(xyz, dtype=float).T))
    return (i + len(lines[0]) * (j + len(lines[1]) * k)).tolist()


def pec_roots(path: Path, lines, nodes) -> list[int]:
    """The union-find root of each of `nodes` ([x, y, z] in mm, on `lines`) over the edges of PEC_dump.vtp at `path`
    (C-15); -1 for a node no PEC edge touches. A dump point (metres, float32) takes the nearest line per axis."""
    d = read_vtk(path)
    parent = list(range(len(d["Points"]) // 3))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    # ponytail: pure-Python union-find, about 1 s per million PEC edges; numpy label propagation if it shows
    for a, b in d["Lines/connectivity"].reshape(-1, 2).tolist():
        parent[find(a)] = find(b)
    point = dict(zip(_flat([np.asarray(a, dtype=float) * 1e-3 for a in lines], d["Points"].reshape(-1, 3)),
                     range(len(parent))))
    return [find(point[n]) if n in point else -1 for n in _flat(lines, nodes)]


def c_box(path: Path, lines, start, stop, axis: int, dt: float) -> float:
    """The capacitance (F) of the box `start`–`stop` (mm, on `lines`) along `axis` (0, 1, 2 for x, y, z), from
    operator_dump.vtr at `path` and the timestep `dt` (s) (C-18): per layer of the box's edges along `axis`, the sum of
    their C_e = dt·(1 + vv)/(2·vi) (a PEC edge, vi = 0, is skipped); the layers in series."""
    op = read_vtk(path)
    nx, ny, nz = (len(a) for a in lines)
    lo, hi = np.sort([[_nearest(lines[n], p[n]) for n in range(3)] for p in (start, stop)], axis=0)
    box = tuple(slice(lo[n], hi[n] + (n != axis)) for n in range(3))  # layers lo..hi-1 along `axis`
    vv, vi = (op[name].astype(float).reshape(nz, ny, nx, 3)[..., axis].T[box] for name in ("vv", "vi"))  # [i, j, k]
    c = np.divide(dt * (1 + vv), 2 * vi, out=np.zeros(vi.shape), where=vi != 0)
    layers = c.sum(axis=tuple(n for n in range(3) if n != axis))
    return float(1 / (1 / layers).sum())


def curve_edge(lines, start, stop) -> tuple[int, tuple[int, int, int]]:
    """The axis (0, 1, 2 for x, y, z) and the start index [i, j, k] on `lines` of the one-cell edge that openEMS's
    CurvePort (ports.py v0.37.0) builds from `start` to `stop` (mm): the axis is the dominant one of stop − start; ends
    whose nearest lines along it are one cell apart give their own edge, from the end lower along it; otherwise the
    edge starts at the lines nearest the midpoint. A point takes the nearest line per axis, the lower on a tie, as
    openEMS does."""
    a, b = (np.asarray(p, dtype=float) for p in (start, stop))
    axis = int(np.argmax(np.abs(b - a)))
    if a[axis] > b[axis]:
        a, b = b, a

    def snap(p: np.ndarray) -> tuple[int, ...]:
        return tuple(int(np.abs(np.asarray(ln, dtype=float) - v).argmin()) for ln, v in zip(lines, p))

    i = snap(a)
    return axis, i if abs(snap(b)[axis] - i[axis]) == 1 else snap(0.5 * (a + b))
