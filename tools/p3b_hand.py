# SPDX-License-Identifier: GPL-3.0-or-later
"""P3-B's hand-built model of the 2.4 GHz fixture ifa2g4 (Stage 3 design 5.11), written by hand from
tools/make_fixtures.py's numbers and KiCad's Texas_SWRA117D_2.4GHz_Left footprint, its pads from
tests/fixtures/ifa2g4.pads.json (pcbnew's own) and its vias from the board's text: its own mesh, MUR on all six faces
at λ/2 at f_lo, a 50 Ω lumped port across U1.1–U1.2's gap, a Gaussian pulse, a frequency-domain far-field box
over-sampled 4 times read with read_cached=False. It imports nothing of the product, and openEMS and CSXCAD only
inside mesh() and run(), always in a process of its own: `python tools/p3b_hand.py --out DIR [--fine-mm MM]
[--wall-mm MM]`, or `--mesh FILE` for the mesh lines alone."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import secrets
import sys
import time
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry

FIX = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
F_LO, F_HI = 2.4e9, 2.4835e9  # the band of `new --band 2400MHz:2483.5MHz`
F0 = (F_LO + F_HI) / 2
F11 = [F0, *(F_LO + (F_HI - F_LO) * k / 9 for k in range(10))]  # f0, then 10 evenly from f_lo to f_hi
WALL_MM = 62.456762  # λ/2 at f_lo
# 0.2 mm on the antenna and its feed, λ_eff(f2)/20 in the board and λ(f2)/20 in air, graded 1.4 where the smoother
# adds lines; seeds nearer than 0.1 mm merge
FINE_MM, BOARD_MM, AIR_MM, RATIO, MERGE_MM = 0.2, 2.36, 5.0, 1.4, 0.1
GAUSS = (2.415e9, 0.575e9)  # SetGaussExcite's f0 and fc: 1.84 to 2.99 GHz at −20 dB
END_CRITERIA, T_END_S, THREADS = 1e-5, 30e-9, 4
GRID_HZ = np.arange(1840, 2991) * 1e6  # S11's grid: 1840 to 2990 MHz every 1 MHz
CENTER = [107.0, -109.0, 0.39]  # mm: the outline's centre, halfway up the board's copper and core

# mm with y up, KiCad's y negated. The stackup (make_fixtures.py:45-47): B.Cu z 0–0.035, the FR4 core 0.035–0.745
# (εr 4.5, tan δ 0.02), F.Cu 0.745–0.78, a 10 µm mask on each face at KiCad's default εr 3.3.
OUTLINE = box(87, -124, 127, -94)  # make_fixtures.py:382, IFA's outline (87, 94)–(127, 124); :357 its Edge.Cuts
ZONE = box(87.5, -123.5, 126.5, -99.75)  # :370-372, both layers' GND zone: 0.5 mm inside it, from ground_top 99.75
CLEARANCE = 1.0  # :372, the zones' clearance to the RF and VDD nets
# AE1 at (100, 100), angle 0 (make_fixtures.py:382, :353): its fp_poly (the board's text, l.314) as 12 rectangles,
# local (x0, x1, y0, y1) with y down (r1 Q2); the polygon's keyhole round the 0.3 mm drill is left to pad 2
RECTS = [(-11.85, -11.35, -5.15, -0.71), (-11.35, -9.15, -5.15, -4.65), (-9.65, -9.15, -4.65, -2.01),
         (-9.65, -6.65, -2.51, -2.01), (-7.15, -6.65, -5.15, -2.51), (-7.15, -4.45, -5.15, -4.65),
         (-4.95, -4.45, -4.65, -2.01), (-4.95, -1.95, -2.51, -2.01), (-2.45, -1.95, -5.15, -2.51),
         (-2.45, 2.55, -5.15, -4.65), (-0.25, 0.25, -4.65, 0.25), (1.65, 2.55, -4.65, 0.25)]
FINE = {"x": (88.15, 102.55), "y": (-112.95, -94.85)}  # the antenna and its feed to U1.1's far end (KiCad y 112.95)
PADS = {p["name"]: p for p in json.loads((FIX / "ifa2g4.pads.json").read_text(encoding="utf-8")).values()}


def pads() -> dict[str, BaseGeometry]:
    """Every pad of pcbnew's tests/fixtures/ifa2g4.pads.json by name: its polygons."""
    return {name: shapely.union_all([Polygon(ring) for ring in p["polygons"]]) for name, p in PADS.items()}


def rods() -> list[tuple[float, float]]:
    """Every via of the board's text (make_fixtures.py:97-103, 0.3 mm drill), y negated, then AE1.2's plated hole at
    its pads.json centre: the fixture's one thru_hole pad, the IFA's short, whose barrel the product builds too."""
    text = (FIX / "ifa2g4.kicad_pcb").read_text(encoding="utf-8")
    vias = [(float(x), -float(y)) for x, y in re.findall(r"\(via\s+\(at ([-\d.]+) ([-\d.]+)\)", text)]
    return [*vias, tuple(PADS["AE1.2"]["center"])]


def _rects() -> list[Polygon]:
    """AE1's 12 rectangles, placed."""
    return [box(100 + x0, -100 - y1, 100 + x1, -100 - y0) for x0, x1, y0, y1 in RECTS]


def antenna() -> BaseGeometry:
    """AE1's copper: its 12 rectangles."""
    return shapely.union_all(_rects())


def _pieces() -> tuple[list[BaseGeometry], list[BaseGeometry]]:
    """Every piece the copper is built from (each AE1 rectangle, pad, track and C1's hull), and those of the RF and
    VDD nets, which the fill clears (AE1.1, the feed, U1.1, U1.8, the VDD track, C1.1). Tracks have round caps."""
    p = pads()
    feed = [LineString([(100, -100), (100, -110)]).buffer(1.35 / 2),  # make_fixtures.py:368, from AE1.1
            LineString([(100, -110), (100, -111.975)]).buffer(0.6 / 2)]  # :369, into U1.1 (pin 1, :355)
    vdd = LineString([(100, -116.925), PADS["C1.1"]["center"]]).buffer(0.25 / 2)  # :376, from U1.8 (pin 8)
    gnd = LineString([PADS["C1.2"]["center"], (103.68, -116.925)]).buffer(0.3 / 2)  # :377, to_gnd's via (:343-344)
    hull = shapely.union_all([p["C1.1"], p["C1.2"]]).convex_hull  # C1 (:374), 100 nF, bridged as copper
    return [*_rects(), *p.values(), *feed, vdd, gnd, hull], [p["AE1.1"], *feed, p["U1.1"], p["U1.8"], vdd, p["C1.1"]]


def copper() -> dict[str, BaseGeometry]:
    """Each copper layer: F.Cu the zone less the clearance round the RF and VDD copper, and every piece; B.Cu the zone
    and AE1.2, the one pad on both layers."""
    # ponytail: the fill rebuilt by its rule, not KiCad's min-thickness rounding (r1: ≤ 1 mm² on F.Cu)
    pieces, cleared = _pieces()
    fill = ZONE.difference(shapely.union_all(cleared).buffer(CLEARANCE))
    return {"F.Cu": shapely.union_all([fill, *pieces]), "B.Cu": ZONE.union(pads()["AE1.2"])}


def port() -> tuple[list[float], list[float]]:
    """The 50 Ω lumped port, along x: exactly the gap from U1.2's edge to U1.1's, along U1.1, across F.Cu."""
    return [99.03, -112.95, 0.745], [99.7, -111.0, 0.78]


def mesh(fine_mm: float = FINE_MM, wall_mm: float = WALL_MM) -> dict[str, list[float]]:
    """The mesh lines, by CSXCAD's own smoother at RATIO. In plane, the seeds are the bounds of every piece the copper
    is built from and each rod, of each RF or VDD piece grown by the clearance, of the zone and of the outline, never
    the fill's arc vertices; merged within MERGE_MM in ascending order, the port's edges always kept. Those inside FINE
    are smoothed at `fine_mm`, then all of them at BOARD_MM, then the walls at the outline ± `wall_mm` at AIR_MM. z:
    the copper's faces, the masks' outer faces and 4 equal cells across the core at BOARD_MM, then the walls `wall_mm`
    past the masks at AIR_MM. Every line to 1e-6 mm."""
    from CSXCAD.SmoothMeshLines import SmoothMeshLines  # here only, in a process of its own

    pieces, cleared = _pieces()
    bounds = [g.bounds for g in [*pieces, *(g.buffer(CLEARANCE) for g in cleared), ZONE, OUTLINE]]
    bounds += [(x, y, x, y) for x, y in rods()]
    lines = {}
    for a, axis in enumerate("xy"):
        seeds = [corner[a] for corner in port()]  # the port's edges, always kept
        for s in sorted(b[i] for b in bounds for i in (a, a + 2)):
            if all(abs(s - k) >= MERGE_MM for k in seeds):
                seeds.append(s)
        fine = SmoothMeshLines([s for s in seeds if FINE[axis][0] <= s <= FINE[axis][1]], fine_mm, RATIO)
        board = SmoothMeshLines(np.r_[seeds, fine], BOARD_MM, RATIO)
        walls = OUTLINE.bounds[a] - wall_mm, OUTLINE.bounds[a + 2] + wall_mm
        lines[axis] = SmoothMeshLines(np.r_[board, walls], AIR_MM, RATIO)
    board = SmoothMeshLines([-0.1, 0, *np.linspace(0.035, 0.745, 5), 0.78, 0.88], BOARD_MM, RATIO)
    lines["z"] = SmoothMeshLines(np.r_[board, -0.1 - wall_mm, 0.88 + wall_mm], AIR_MM, RATIO)
    return {axis: [round(float(v), 6) for v in lines[axis]] for axis in "xyz"}


def _hole_free(geom: BaseGeometry) -> list[Polygon]:
    """`geom`'s polygons with no holes, as AddLinPoly takes them: each hole opened by a 1 µm slit from inside it
    straight down out of the copper (the fill's VDD pocket: through the ground under it, clear of the RF copper)."""
    # ponytail: 1 µm slits for the holes AddLinPoly takes none of, 200 times under the mesh's finest cell; CSXCAD's
    # polygons with holes if a slit ever shows
    for hole in [ring for p in shapely.get_parts(geom) for ring in p.interiors]:
        x, y = Polygon(hole).representative_point().coords[0]
        geom = geom.difference(box(x - 0.0005, geom.bounds[1] - 1, x + 0.0005, y))
    return list(shapely.get_parts(geom))


def run(out: Path, fine_mm: float = FINE_MM, wall_mm: float = WALL_MM) -> dict:
    """Runs the model on mesh(`fine_mm`, `wall_mm`) in `out`/sim and writes `out`/hand.json, which it returns: S11 on
    GRID_HZ; D_max, P_rad, P_acc and η_rad at F11; the line counts; the port voltage's last sample time, whether the
    end criterion stopped it and its last 2 ns against its peak; the settings, wall_s, versions and script_sha(); no
    path."""
    from CSXCAD import ContinuousStructure  # here only, in a process of its own
    from openEMS import openEMS
    from openEMS.physical_constants import EPS0

    t0, out = time.monotonic(), Path(out).resolve()  # absolute: Run changes into its folder
    lines = mesh(fine_mm, wall_mm)
    fdtd = openEMS(EndCriteria=END_CRITERIA)
    fdtd.SetMaxTime(T_END_S)
    fdtd.SetGaussExcite(*GAUSS)
    fdtd.SetBoundaryCond(["MUR"] * 6)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    grid = csx.GetGrid()
    grid.SetDeltaUnit(1e-3)
    for axis in "xyz":
        grid.SetLines(axis, lines[axis])
    x0, y0, x1, y1 = OUTLINE.bounds
    core = csx.AddMaterial("core", epsilon=4.5, kappa=2 * np.pi * F0 * EPS0 * 4.5 * 0.02)  # tan δ 0.02 at f0
    core.AddBox([x0, y0, 0.035], [x1, y1, 0.745], priority=1)
    mask = csx.AddMaterial("mask", epsilon=(0.01 * 3.3 + (0.1 - 0.01)) / 0.1)  # 10 µm at 3.3 and air, over 0.1 mm
    mask.AddBox([x0, y0, 0.78], [x1, y1, 0.88], priority=1)
    mask.AddBox([x0, y0, -0.1], [x1, y1, 0], priority=1)
    metal, cu = csx.AddMetal("copper"), copper()
    for layer, z0 in (("F.Cu", 0.745), ("B.Cu", 0)):
        for piece in _hole_free(cu[layer]):  # 35 µm thick; [xs, ys] without the closing point
            metal.AddLinPoly(np.asarray(piece.exterior.coords)[:-1].T, "z", z0, 0.035, priority=10)
    for x, y in rods():  # on its mesh lines: its x and y are seeds
        metal.AddCurve([[x, x], [y, y], [0, 0.78]])
    start, stop = port()
    lumped = fdtd.AddLumpedPort(1, 50, start, stop, "x", 1.0, priority=5)
    nf2ff = fdtd.CreateNF2FFBox("nf2ff", start=[lines[a][3] for a in "xyz"], stop=[lines[a][-4] for a in "xyz"],
                                frequency=F11, over_sampling=4)
    out.mkdir(parents=True, exist_ok=True)
    sim = str(out / "sim")
    if fdtd.Run(sim, numThreads=THREADS):  # its setup's error code; None after a full run
        raise RuntimeError("openEMS's setup failed")
    lumped.CalcPort(sim, GRID_HZ)
    s11, t, u = lumped.uf_ref / lumped.uf_inc, lumped.u_time, np.abs(lumped.ut_tot)
    lumped.CalcPort(sim, F11)
    far = nf2ff.CalcNF2FF(sim, F11, np.arange(0, 181, 5), np.arange(-180, 181, 5), center=[c * 1e-3 for c in CENTER],
                          read_cached=False, outfile=f"hand-{secrets.token_hex(4)}.h5")  # metres
    hand = {"f_hz": GRID_HZ.tolist(), "s11": np.c_[s11.real, s11.imag].tolist(),
            "far": {"f_hz": F11, "d_max": far.Dmax.tolist(), "p_rad": far.Prad.tolist(),
                    "p_acc": lumped.P_acc.tolist(), "eta_rad": (far.Prad / lumped.P_acc).tolist()},
            "cells": [len(lines[a]) for a in "xyz"], "t_end": float(t[-1]),
            "criterion_hit": bool(t[-1] < 0.99 * T_END_S),
            "decay_db": float(20 * np.log10(u[t >= t[-1] - 2e-9].max() / u.max())),
            "fine_mm": fine_mm, "wall_mm": wall_mm, "wall_s": time.monotonic() - t0,
            "versions": {"openems": importlib.metadata.version("openEMS"),
                         "csxcad": importlib.metadata.version("CSXCAD"),
                         "python": platform.python_version(), "os": platform.platform()},
            "script_sha256": script_sha()}
    (out / "hand.json").write_text(json.dumps(hand, indent=1) + "\n", encoding="utf-8")
    return hand


def script_sha() -> str:
    """The sha256 of this file, its CRLF read as LF: the reference's key."""
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    """--mesh FILE writes mesh()'s lines as JSON ({"x", "y", "z"}); else --out DIR runs. Returns 0."""
    parser = argparse.ArgumentParser(prog="p3b_hand", description="P3-B's hand-built openEMS model of ifa2g4.")
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--out", type=Path, help="the run's folder: sim/ and hand.json")
    what.add_argument("--mesh", type=Path, help="the JSON file of the mesh lines alone")
    parser.add_argument("--fine-mm", type=float, default=FINE_MM, help="the antenna's and feed's cell")
    parser.add_argument("--wall-mm", type=float, default=WALL_MM, help="the MUR walls' distance from the board")
    args = parser.parse_args(argv)
    if args.mesh:
        args.mesh.write_text(json.dumps(mesh(args.fine_mm, args.wall_mm)), encoding="utf-8")
    else:
        run(args.out, args.fine_mm, args.wall_mm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
