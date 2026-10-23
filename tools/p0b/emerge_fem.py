# SPDX-License-Identifier: GPL-3.0-or-later
"""P0-B's FEM side (D-41, D-42): EMerge's models of the coupons and of lpf915's layout 6-port, built from the
input.json that tools/p0b/emerge_app.py exports; r6's em_coupon.py and em_lpf.py, ported. It runs in the validation
venv only, with numpy, EMerge and psutil, and never imports the app: data comes in as JSON and leaves as JSON and NPZ.
Its JSON output is written last, through a temporary file, so a crash leaves none.

  coupon --input FILE --name NAME --edge-um UM [--box 45|10] --out FILE.json
  nport --input FILE --edge-um UM [--mask clean|none] --out FILE.npz, and FILE.json beside it"""
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import psutil

T0 = time.perf_counter()
MM = 1e-3  # m: EMerge works in metres, input.json in mm
C0 = 299792458.0  # m/s
COUPON_F = (0.4575e9, 0.915e9)  # Hz; Z0 and εeff are read at the lowest, as the port mode's rise with f (r6 §5.2)
COUPON_MM = 4.0  # the coupon's length along its line, as r6 §5.1 measured it
RESOLUTION, GROWTH = 0.33, 2.0  # the largest element in wavelengths; the growth away from a refined edge
PEC_PRIORITY = 1000


def peak_rss() -> dict:
    """{"bytes": the largest resident memory of this process and its children so far}, kept by a daemon thread that
    reads it every 0.2 s."""
    peak = {"bytes": 0}

    def watch() -> None:
        me = psutil.Process()
        while True:
            try:
                rss = me.memory_info().rss + sum(child.memory_info().rss for child in me.children(recursive=True))
            except psutil.Error:  # a child ended meanwhile
                rss = 0
            peak["bytes"] = max(peak["bytes"], rss)
            time.sleep(0.2)

    threading.Thread(target=watch, daemon=True).start()
    return peak


def simulation(em, name: str):
    """An EMerge Simulation that gives raw S: no capping of |S_ij| at 1, no column power normalisation, no size check
    (r6 §3), which would hide a passivity error."""
    model = em.Simulation(name)
    model.settings.mw_cap_sp_single = False
    model.settings.mw_cap_sp_col = False
    model.settings.size_check = False
    return model


def stats(model, peak: dict) -> dict:
    """The mesh's nodes and tetrahedra, the seconds since this script started and the peak memory in GB."""
    return {"nodes": int(model.mesh.nodes.shape[1]), "tets": int(model.mesh.n_tets), "t_s": time.perf_counter() - T0,
            "peak_gb": peak["bytes"] / 2**30}


def save(path: Path, data: dict) -> None:
    """`data` as JSON at `path`, through a temporary file that replaces it."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def coupon(em, a: argparse.Namespace, peak: dict) -> None:
    """The coupon a.name (r6 §5.1): its cross-section ("cs", or "cs_10h" for --box 10; cs2d's x across the line as y,
    its z as z) extruded COUPON_MM along x in its closed PEC box: air, its dielectrics, then its conductors as 35 µm
    solid PEC, each ground's outer edges run out to the box's walls (cs2d holds every ground at 0 V with its box; a
    ground off the walls floats in EMerge and adds a mode); the signal's surfaces meshed at --edge-um; a TEM ModalPort
    on each end face, its voltage line from the top of the ground under the strip to the strip's bottom, at the
    strip's centre. Writes {"name", "edge_um", "z0", "eeff", "freq_hz", "nodes", "tets", "t_s", "peak_gb", "emerge"}
    to --out: the mode's Z0 and εeff = (β/k0)², read at the lowest frequency, freq_hz."""
    cs = json.loads(Path(a.input).read_text(encoding="utf-8"))["coupons"][a.name]["cs" if a.box == 45 else "cs_10h"]
    x0, x1, z0, z1 = cs["box"]
    sig = next(r for r in cs["conductors"] if r["role"] == "signal")
    yc = (sig["x0"] + sig["x1"]) / 2  # EMerge's y = 0 at the strip's centre

    def block(r0: float, r1: float, h0: float, h1: float):
        """The box from r0 to r1 across (cs2d's x) and from h0 to h1 in z, in mm, over the coupon's length."""
        return em.geo.Box(COUPON_MM * MM, (r1 - r0) * MM, (h1 - h0) * MM, position=(0, (r0 - yc) * MM, h0 * MM))

    model = simulation(em, f"coupon_{a.name}")
    block(x0, x1, z0, z1).set_material(em.lib.AIR).prio_set(1)
    for i, r in enumerate(cs["dielectrics"]):
        block(r["x0"], r["x1"], r["z0"], r["z1"]).set_material(em.Material(er=r["eps_r"], name=f"diel{i}")).prio_set(
            10 + i)
    grounds = [r for r in cs["conductors"] if r["role"] == "ground"]
    for r in grounds:
        same = [q for q in grounds if q["z0"] == r["z0"]]
        if r["x0"] == min(q["x0"] for q in same):
            r["x0"] = x0
        if r["x1"] == max(q["x1"] for q in same):
            r["x1"] = x1
    metal = [(r["role"], block(r["x0"], r["x1"], r["z0"], r["z1"]).set_material(em.lib.PEC).prio_set(100))
             for r in cs["conductors"]]
    ends = (0.0, COUPON_MM * MM)
    faces = [em.geo.Plate((x, (x0 - yc) * MM, z0 * MM), (0, (x1 - x0) * MM, 0), (0, 0, (z1 - z0) * MM),
                          name=f"port{k}") for k, x in enumerate(ends, 1)]
    model.commit_geometry()
    model.mw.set_resolution(RESOLUTION)
    model.mw.set_frequency(np.array(COUPON_F))
    for role, g in metal:
        if role == "signal":
            model.mesher.set_boundary_size(g, a.edge_um * 1e-6, growth_rate=GROWTH)
    for _, g in metal:
        model.mesher.set_pec_domain(g)
    print(f"emerge_fem: {a.name} meshing", flush=True)
    model.generate_mesh()
    gnd_top = max(r["z1"] for r in grounds if r["z1"] <= sig["z0"] + 1e-9)
    for k, (face, x) in enumerate(zip(faces, ends), 1):
        port = model.mw.bc.ModalPort(face, k, modetype="TEM", mixed_materials=True)
        port.set_integration_line((x, 0.0, gnd_top * MM), (x, 0.0, sig["z0"] * MM), 101)
    print(f"emerge_fem: {a.name} solving, {stats(model, peak)}", flush=True)
    grid = model.mw.run_sweep(parallel=False, frequency_groups=1).scalar.grid
    f = np.asarray(grid.freq)
    k = int(np.argmin(f))
    beta = float(np.real(np.asarray(grid.beta)[k, 0]))
    result = {"name": a.name, "edge_um": a.edge_um, "z0": float(np.real(np.asarray(grid.Z0)[k, 0])),
              "eeff": float((beta * C0 / (2 * np.pi * f[k])) ** 2), "freq_hz": float(f[k]), **stats(model, peak),
              "emerge": em.__version__}
    save(Path(a.out), result)
    print(f"emerge_fem: {result}", flush=True)


def nport(em, a: argparse.Namespace, peak: dict) -> None:
    """lpf915's layout 6-port (r6 §4.3, D-42's workarounds, "the same layout"): an air box over the spec's mesh bounds
    with an order-2 AbsorbingBoundary on its outside; the spec's dielectrics at their priorities as
    Material(er=eps, cond=kappa), the masks from mask_clean (--mask clean) or none; every copper solid a 35 µm PEC
    prism, every via an 8-sided PEC cylinder (compensate_radius), the lid plate a 50 µm PEC slab at its snapped z and
    its walls, all at PEC_PRIORITY and PEC domains; gmsh's remove_all_duplicates a no-op in commit_geometry, since it
    renumbers the faces of the sheets inside volumes; the chain-net copper's surfaces (the copper parts' hulls too)
    meshed at --edge-um; one 50 Ω LumpedPort per face in job order (width hi − lo, height h_eff, direction ±p, its
    midline the voltage line). Writes f, s and names to --out, then {"nodes", "tets", "t_s", "peak_gb", "sigma_max",
    "recip", "emerge"} beside it as its .json: σ_max and the reciprocity error the largest over f."""
    import gmsh  # EMerge's own dependency, after EMerge set it up

    lpf = json.loads(Path(a.input).read_text(encoding="utf-8"))["lpf915"]
    spec = lpf["spec"]

    def at(x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """The coordinate system at (x, y, z) mm, axes as the model's."""
        return em.CoordinateSystem(em.XAX, em.YAX, em.ZAX, np.array([x, y, z]) * MM)

    def prism(s: dict):
        """The spec solid `s` ({"x", "y", "z": [z0, z1]}, mm) as a prism."""
        return em.geo.XYPolygon(np.array(s["x"]) * MM, np.array(s["y"]) * MM).extrude((s["z"][1] - s["z"][0]) * MM,
                                                                                     cs=at(z=s["z"][0]))

    def pec(g):
        return g.set_material(em.lib.PEC).prio_set(PEC_PRIORITY)

    model = simulation(em, "lpf915")
    x, y, z = (spec["mesh"][axis] for axis in "xyz")
    air = em.geo.Box((x[-1] - x[0]) * MM, (y[-1] - y[0]) * MM, (z[-1] - z[0]) * MM,
                     position=(x[0] * MM, y[0] * MM, z[0] * MM)).set_material(em.lib.AIR).prio_set(1)
    masks = lpf["mask_clean"] if a.mask == "clean" else []
    for m in [m for m in spec["materials"] if not m["name"].startswith("mask_")] + masks:
        material = em.Material(er=m["eps"], cond=m["kappa"], name=m["name"])
        for s in m["solids"]:
            prism(s).set_material(material).prio_set(m["priority"])
    chain = set(lpf["chain_nets"]) | {"copper_part"}
    copper = [(label["net"] in chain, pec(prism(s))) for label, s in zip(lpf["labels"], spec["metal"]["copper"])]
    metal = [g for _, g in copper]
    metal += [pec(em.geo.Cylinder(r["radius"] * MM, (r["z1"] - r["z0"]) * MM, at(*r["at"], r["z0"]), Nsections=8,
                                  compensate_radius=True)) for r in lpf["rods"]]
    lid = spec["metal"]["lid"]
    if lid["plate"] is not None:  # a sheet there would lose a face to the walls' tops in gmsh's fragment
        top = lid["plate"]["z"]
        metal.append(pec(prism({**lid["plate"], "z": [top, top + 0.05]})))
    metal += [pec(prism(s)) for s in lid["walls"]]
    faces = [em.geo.XYPolygon(np.array(fc["gap_x"]) * MM, np.array(fc["gap_y"]) * MM).geo(cs=at(z=fc["z"]))
             for fc in lpf["faces"]]
    gmsh.model.occ.remove_all_duplicates = lambda *args, **kwargs: None
    model.commit_geometry()
    model.mw.set_resolution(RESOLUTION)
    model.mw.set_frequency(np.array(lpf["freqs"]))
    for on_chain, g in copper:
        if on_chain:
            model.mesher.set_boundary_size(g, a.edge_um * 1e-6, growth_rate=GROWTH)
    for g in metal:
        model.mesher.set_pec_domain(g)
    print(f"emerge_fem: lpf915 at {a.edge_um:g} um, mask {a.mask}, meshing", flush=True)
    model.generate_mesh()
    model.mw.bc.AbsorbingBoundary(air.outside(), order=2)
    for k, (fc, face) in enumerate(zip(lpf["faces"], faces), 1):
        direction = [0.0, 0.0, 0.0]
        direction[fc["p"]] = fc["sign"]
        port = model.mw.bc.LumpedPort(face, k, width=(fc["hi"] - fc["lo"]) * MM, height=fc["h_eff"] * MM,
                                      direction=tuple(direction), Z0=50)
        g0, g1, mid = fc["line"]
        ends = []
        for u in (g0, g1):  # from the signal copper's edge to the reference's, at the span's middle
            point = [mid, mid, fc["z"]]
            point[fc["p"]] = u
            ends.append(np.array(point) * MM)
        port.voltage_integration_line.append(em.Line.from_points(*ends, 41))  # in place of EMerge's own lines
    print(f"emerge_fem: lpf915 solving, {stats(model, peak)}", flush=True)
    grid = model.mw.run_sweep(parallel=False, frequency_groups=1).scalar.grid
    s = np.asarray(grid.Smat)
    np.savez(a.out, f=np.asarray(grid.freq), s=s, names=np.array([fc["name"] for fc in lpf["faces"]]))
    result = {**stats(model, peak), "sigma_max": float(np.linalg.norm(s, 2, axis=(-2, -1)).max()),
              "recip": float(np.abs(s - np.swapaxes(s, -1, -2)).max()), "emerge": em.__version__}
    save(Path(a.out).with_suffix(".json"), result)
    print(f"emerge_fem: {result}", flush=True)


def main() -> None:
    """Parses the command, sets MKL_NUM_THREADS to 8 unless it is set (EMerge defaults it to 4 at import), imports
    EMerge and builds, solves and writes the model of the mode."""
    sys.stdout.reconfigure(encoding="utf-8")  # loguru writes Ω and β, which a cp1252 console cannot (r6 §1)
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="emerge_fem", description="P0-B's EMerge models (D-41, D-42).")
    modes = parser.add_subparsers(dest="mode", required=True)
    one = modes.add_parser("coupon", help="a coupon's Z0 and εeff")
    one.add_argument("--input", required=True)
    one.add_argument("--name", required=True)
    one.add_argument("--edge-um", type=float, required=True)
    one.add_argument("--box", type=int, choices=(45, 10), default=45)
    one.add_argument("--out", required=True)
    six = modes.add_parser("nport", help="lpf915's layout 6-port")
    six.add_argument("--input", required=True)
    six.add_argument("--edge-um", type=float, required=True)
    six.add_argument("--mask", choices=("clean", "none"), default="clean")
    six.add_argument("--out", required=True)
    a = parser.parse_args()
    os.environ.setdefault("MKL_NUM_THREADS", "8")
    import emerge as em

    (coupon if a.mode == "coupon" else nport)(em, a, peak_rss())


if __name__ == "__main__":
    main()
