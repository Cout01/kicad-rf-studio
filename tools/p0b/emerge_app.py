# SPDX-License-Identifier: GPL-3.0-or-later
"""P0-B's EMerge cross-check (spec 9.3; D-41..D-44), the side that runs in the app venv. One command makes the
validation venv inside the P0 folder, exports B1's model with what an EMerge model needs beside it (input.json), runs
the FEM steps (tools/p0b/emerge_fem.py in that venv, each a resumable p0.step), cross-checks EMerge's chain against
openEMS's at EMerge's frequencies (emerge.json) and rewrites p0b.json; after a "fail" it runs D-43's no-mask pair
first.

Dev-time only, like p0: the package never imports it. Run: python tools/p0b/emerge_app.py run [--out DIR]."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import traceback
from dataclasses import asdict
from datetime import date
from functools import partial
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, box

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.cs2d import solve
from kicad_rf_studio.core.geometry.sections import BOX_H, cross_section
from kicad_rf_studio.core.kicad.values import part_kind, port_value
from kicad_rf_studio.core.model.ports import End, ends
from kicad_rf_studio.core.model.spec import _solids, spec_hash
from kicad_rf_studio.core.post.chain import loads, terminate, z_part
from kicad_rf_studio.core.post.checks import compare
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import load_project, parts

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/, for p0 when this runs as a script
import p0  # noqa: E402
import p0a  # noqa: E402
from p0b import harness  # noqa: E402

NPORT_FREE_MB = 21000  # r6 §6: the 60 µm level peaks near 20 GB on this 31 GB PC; 1 GB of headroom, the page file covers an overshoot
COUPONS = ("coupon_ms", "coupon_gcpw")  # D-43's coupons, solved at 50 µm
LEVELS = ("75", "60")  # µm, the 6-port's two mesh levels (D-43); the last, the finer, is the one compared
PRECONDITIONS = {"z0_pct": 5.0, "eeff_pct": 3.0, "move": 0.01, "sigma": 1.01, "recip": 0.01}  # D-43's limits
STATS = ("nodes", "tets", "t_s", "peak_gb", "sigma_max", "recip")  # what emerge.json keeps of a 6-port's JSON
NOMASK_FEM, NOMASK_OPENEMS = "p0b-emerge-nport-75-nomask", "p0b-emerge-nomask-openems"  # D-43's no-mask pair
FEM = p0.ROOT / "tools" / "p0b" / "emerge_fem.py"  # by its absolute path: it runs in <P0>/emerge (PF-37)
REQUIREMENTS = p0.ROOT / "tools" / "p0b" / "requirements.txt"


def _read(path: Path):
    """The JSON at `path`."""
    return json.loads(path.read_text(encoding="utf-8"))


def _python(e: Path) -> Path:
    """The validation venv's Python in the EMerge folder `e`."""
    return e / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def freqs(f0: float, f2: float) -> np.ndarray:
    """EMerge's frequencies (D-43): f0·j/8 for j = 4…26, then f2; 24 points, f0, 2f0 and 3f0 exactly among them."""
    return np.append(f0 * np.arange(4, 27) / 8, f2)


def _coupon(name: str) -> dict:
    """The coupon `name` as EMerge's coupon and its references take it: P0-A's model at mesh.n 2; "cs", its section's
    cross-section with no mask in the BOX_REF (45 h) box, where its references are read (p0a.references): "z0_ref",
    KiCad's, and "eeff_ref", the 2D εeff; for OI-7's fallback (PF-35), "cs_10h", the same cross-section in fit2d's
    10 h box (BOX_H), and "eeff_ref_10h", cs2d's exact-mask εeff in that box."""
    model, geom, pts, _ = p0a.coupon_model(name, 2)
    sec, ref = geom.sections[0], p0a.references(geom, model.mesh, pts[0])

    def cut(mode: str, box_h: float):
        return cross_section(sec, geom.pieces, geom.zs, geom.masks.get(sec.layer), mode, box_h=box_h)

    return {"cs": asdict(cut("none", p0a.BOX_REF)), "z0_ref": ref["z0_ref"], "eeff_ref": ref["eeff_ref"],
            "cs_10h": asdict(cut("none", BOX_H)), "eeff_ref_10h": solve(cut("exact", BOX_H)).eps_eff}


def _opened(material: dict) -> dict:
    """The mask material `material` (model spec) opened by 5 µm, mitre joins, on the 1e-6 mm grid, less its slivers
    under 1e-6 mm²: gmsh cannot mesh a sliver ("overlapping facets"), and openEMS drops one under a cell anyway (r6
    §4.4)."""
    whole = shapely.union_all([Polygon(zip(s["x"], s["y"])) for s in material["solids"]])
    opened = whole.buffer(-0.005, join_style="mitre").buffer(0.005, join_style="mitre")
    kept = [g for g in shapely.get_parts(shapely.set_precision(opened, 1e-6))
            if g.geom_type == "Polygon" and g.area >= 1e-6]
    return {**material, "solids": [s for g in kept for s in _solids(g, *material["solids"][0]["z"])]}


def _face(port: dict, end: End, copper: list[dict]) -> dict:
    """The EMerge face of the lumped `port` (model spec) whose ends are `end` (r6 §4.3): p, its box's axis; on each of
    21 cuts across the box's span (lo, hi), the edge of the signal copper toward the reference and the reference
    copper's edge, read on the model's own copper of the box's slab, `copper` (model spec solids), between the middles
    of the signal's and the reference's bounds along p; "gap_x", "gap_y", the gap polygon in that band nearest the
    middle cut's midpoint; "h_eff", the harmonic mean of the cuts' gaps; "line", [g0, g1, t], the middle cut's two
    edges and the span's middle; "sign", +1 when the reference lies at higher p; "z", the slab's middle."""
    p = "xy".index(port["dir"])
    t = 1 - p
    cu = shapely.union_all([Polygon(zip(s["x"], s["y"])) for s in copper if s["z"][0] == port["start"][2]])
    sc, rc = ((b[p] + b[p + 2]) / 2 for b in (end.signal.bounds, end.reference.bounds))
    a0, a1 = sorted((sc, rc))
    sign = 1.0 if rc > sc else -1.0
    lo, hi = sorted((port["start"][t], port["stop"][t]))

    def at(u: float, v: float) -> tuple[float, float]:
        """The point `u` along p and `v` across it."""
        return (u, v) if p == 0 else (v, u)

    def edges(v: float) -> tuple[float, float] | None:
        """The signal's and the reference's facing edges along p at `v` across; None when the cut misses either."""
        segs = [(g.bounds[p], g.bounds[p + 2]) for g in shapely.get_parts(LineString([at(a0, v), at(a1, v)])
                                                                            .intersection(cu)) if g.length > 0]
        s, r = (next((g for g in segs if g[0] - 1e-9 <= c <= g[1] + 1e-9), None) for c in (sc, rc))
        return None if s is None or r is None else (s[1], r[0]) if sign > 0 else (s[0], r[1])

    cuts = [g for g in (edges(lo + (hi - lo) * k / 20) for k in range(21)) if g is not None]
    g0, g1 = cuts[len(cuts) // 2]
    mid = Point(at((g0 + g1) / 2, (lo + hi) / 2))
    gap = min(shapely.get_parts(box(*at(a0, lo), *at(a1, hi)).difference(cu)), key=mid.distance)
    gx, gy = shapely.get_coordinates(shapely.set_precision(gap, 1e-6).exterior)[:-1].T.tolist()
    return {"name": port["name"], "p": p, "z": (port["start"][2] + port["stop"][2]) / 2, "gap_x": gx, "gap_y": gy,
            "h_eff": len(cuts) / sum(1 / abs(b - a) for a, b in cuts), "line": [g0, g1, (lo + hi) / 2],
            "sign": sign, "lo": lo, "hi": hi}


def export(pj: Path, out: Path) -> dict:
    """<out>/emerge/input.json, the EMerge models' input (D-42, r6 §4), written and returned as written: "coupons", by
    name of COUPONS, _coupon's; "lpf915", from the project `pj` (B1's): "spec", the model spec it builds (SystemExit
    when the project holds results of another model), "labels", {"net", "layer"} per copper solid in the spec's order
    ("copper_part" for the 0R hulls), "chain_nets", "rods" ({"at", "radius", "z0", "z1"} per via, solid or not),
    "mask_clean" (_opened, per mask material), "faces" (_face, per spec port in job order), "freqs" (freqs, up to the
    excitation's f2) and "f0"."""
    project, board, geom, _ = pipeline.load(pj)
    spec = pipeline.build_model(project, board, geom).spec
    if "results" in project and spec_hash(spec) != project["results"]["model_hash"]:
        raise SystemExit(f"emerge_app: {pj} no longer builds the model of its results; run B1 again")
    cu = {s.copper: (s.z0, s.z1) for s in geom.zs if s.kind == "copper"}
    labels = [{"net": pc.net, "layer": pc.layer} for pc in geom.pieces for _ in _solids(pc.polygon, *cu[pc.layer])]
    labels += [{"net": "copper_part", "layer": ""}] * (len(spec["metal"]["copper"]) - len(labels))  # model_spec's order
    by_name = {end.name: end for end in ends(board, project, geom.pieces)}
    lpf = {"spec": spec, "labels": labels, "chain_nets": project["chain"]["nets"],
           "rods": [{"at": list(r.at), "radius": r.radius, "z0": r.z0, "z1": r.z1} for r in geom.rods],
           "mask_clean": [_opened(m) for m in spec["materials"] if m["name"].startswith("mask_")],
           "faces": [_face(q, by_name[q["name"]], spec["metal"]["copper"]) for q in spec["ports"]],
           "freqs": freqs(project["f0_hz"], spec["excitation"]["f2"]), "f0": project["f0_hz"]}
    return p0.save(out / "emerge" / "input.json", {"coupons": {name: _coupon(name) for name in COUPONS},
                                                   "lpf915": lpf})


def verdict(cmp: dict | None, coupons: list[dict], move: float | None, sigma: float | None, recip: float | None,
            unsolved: list[str] = ()) -> tuple[str, list[str]]:
    """EMerge's verdict (D-43) and its reasons, each a missing FEM output (PF-34) or a failed precondition of D-43
    under PRECONDITIONS, the ones given as None not judged: "EMerge <level> not solved" per level of `unsolved`; a
    coupon's |ΔZ0| against KiCad and |Δεeff| against the 2D value (its "dz0_pct" and "deeff_pct"); the chain's move
    between the two levels; σ_max; the reciprocity error. "inconclusive" with any reason, else "pass" when `cmp`
    (checks.compare's) holds criterion 1's ds_max and ds21_db_f0 limits, else "fail"."""
    reasons = [f"EMerge {level} not solved" for level in unsolved]
    reasons += [f"{row['name']} {what} {row[key]:.2f} %" for row in coupons for what, key in
                (("z0", "dz0_pct"), ("eeff", "deeff_pct")) if abs(row[key]) > PRECONDITIONS[f"{what}_pct"]]
    if move is not None and move > PRECONDITIONS["move"]:
        reasons.append(f"chain moved {move:.4f} from {LEVELS[0]} to {LEVELS[1]} um")
    if sigma is not None and sigma > PRECONDITIONS["sigma"]:
        reasons.append(f"sigma_max {sigma:.4f}")
    if recip is not None and recip > PRECONDITIONS["recip"]:
        reasons.append(f"reciprocity {recip:.4f}")
    if reasons:
        return "inconclusive", reasons
    ok = cmp["ds_max"] <= p0.LIMITS1["ds_max"] and cmp["ds21_db_f0"] <= p0.LIMITS1["ds21_db_f0"]
    return ("pass" if ok else "fail"), []


def fem(out: Path, mode: str, *args: str) -> dict:
    """A FEM step's work (D-41): emerge_fem.py `mode` `args` by the validation venv's Python, isolated (-I), in the
    working folder <out>/emerge with TEMP and TMP in <out>/emerge/tmp (TMPDIR too: Python's tempfile reads it first,
    and Git Bash sets it), waited for; the output its --out names, and an NPZ's JSON beside it, removed first, so a
    failed solve never leaves an earlier one to read. For "nport", SystemExit first, so nothing is recorded, when the
    free RAM is under NPORT_FREE_MB. Returns {"exit", "output": the output's name, "stderr": its last 20 lines, for the
    step record only}."""
    if mode == "nport" and (free := runs.free_ram_mb()) < NPORT_FREE_MB:
        raise SystemExit(f"emerge_app: {free:.0f} MB of RAM free, under the {NPORT_FREE_MB} MB an nport solve needs; "
                         "close other programs, then run again")
    e, name = out / "emerge", args[args.index("--out") + 1]
    for path in (e / name, (e / name).with_suffix(".json")):
        path.unlink(missing_ok=True)
    tmp = e / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    done = subprocess.run([str(_python(e)), "-I", str(FEM), mode, *args], cwd=e, stderr=subprocess.PIPE,
                          encoding="utf-8", errors="replace",
                          env={**os.environ, "TEMP": str(tmp), "TMP": str(tmp), "TMPDIR": str(tmp)})
    return {"exit": done.returncode, "output": name, "stderr": "\n".join(done.stderr.splitlines()[-20:])}


def _digest(out: Path) -> str:
    """The sha256 of <out>/emerge/input.json, of FEM and of REQUIREMENTS, each read with LF line ends (a checkout under
    core.autocrlf writes CRLF), which key the FEM steps: a fix to either script runs them again, a fix elsewhere in
    tools/ keeps their records."""
    paths = (out / "emerge" / "input.json", FEM, REQUIREMENTS)
    return "|".join(hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for path in paths)


def _key(out: Path, sid: str) -> str:
    """The key of the step `sid`'s record in <out>/steps, "" without one."""
    path = out / "steps" / f"{sid}.json"
    return _read(path)["key"] if path.is_file() else ""


def _fem_step(out: Path, sid: str, mode: str, *args: str) -> dict:
    """The FEM step `sid`, fem(out, mode, *args) through p0.step, keyed by _digest and the arguments."""
    return p0.step(out, sid, f"{_digest(out)}|{' '.join((mode, *args))}", partial(fem, out, mode, *args))


def _supersede(out: Path, *sids: str) -> None:
    """Moves the records of the steps `sids`, conditional steps that do not apply in this call, into
    <out>/superseded-<date> (PF-65's folder, made when needed), so p0b.json counts only the steps this call used and a
    record of other code left there never blocks harness.write."""
    for path in (out / "steps" / f"{sid}.json" for sid in sids):
        if path.is_file():
            folder = out / f"superseded-{date.today().isoformat()}"
            folder.mkdir(exist_ok=True)
            path.replace(folder / path.name)  # ponytail: a record moved aside twice in one day keeps the later one


def _solved(out: Path, sid: str, mode: str, *args: str) -> bool | None:
    """The FEM step `sid`, printed, then run through _fem_step: whether it solved, exiting 0 with its output on disk;
    None, its traceback printed, when it raised (SystemExit, STOP or too little RAM, and KeyboardInterrupt end the
    command)."""
    print(f"emerge_app: {sid}", flush=True)
    try:
        res = _fem_step(out, sid, mode, *args)["result"]
    except Exception:
        traceback.print_exc()
        return None
    return not res["exit"] and (out / "emerge" / res["output"]).is_file()


def fem_steps(out: Path) -> list[str]:
    """The FEM steps (D-43), each through _solved: each coupon of COUPONS at 50 µm in the 45 h box,
    p0b-emerge-coupon-<name>-50, then, only when it ran and did not solve, in the 10 h box,
    p0b-emerge-coupon-<name>-50-10h (OI-7, PF-35), whose record moves aside (_supersede) when the 45 h step solved;
    the 6-port at each level of LEVELS, p0b-emerge-nport-<um>. Returns the ids of the steps that raised or did not
    solve, a coupon's 45 h step not among them when its 10 h step solved."""
    failed = []
    for name in COUPONS:
        sid, args = f"p0b-emerge-coupon-{name}-50", ("--input", "input.json", "--name", name, "--edge-um", "50")
        ok = _solved(out, sid, "coupon", *args, "--out", f"{name}-50.json")
        if ok:  # its fallback does not apply in this call
            _supersede(out, f"{sid}-10h")
        elif ok is False:
            sid += "-10h"
            ok = _solved(out, sid, "coupon", *args, "--box", "10", "--out", f"{name}-50-10h.json")
        if not ok:
            failed.append(sid)
    for um in LEVELS:
        sid = f"p0b-emerge-nport-{um}"
        if not _solved(out, sid, "nport", "--input", "input.json", "--edge-um", um, "--out", f"lpf915-{um}.npz"):
            failed.append(sid)
    return failed


def _nport(e: Path, stem: str) -> tuple[np.ndarray, list[str], dict] | None:
    """The 6-port emerge_fem.py wrote as <stem>.npz in `e`: its S (F, N, N), its port names and the JSON it writes
    beside it last; None when either file is missing."""
    npz, js = e / f"{stem}.npz", e / f"{stem}.json"
    if not (npz.is_file() and js.is_file()):
        return None
    with np.load(npz) as z:
        return z["s"], z["names"].tolist(), _read(js)


def _chain(project: dict, s: np.ndarray, names: list[str], f: np.ndarray, cbox: dict | None = None) -> np.ndarray:
    """The chain of the N-port `s` (F, N, N, its ports `names`) on `f`: terminate at its external ports, each part
    port closed by its ideal Z_part alone (D-43: EMerge's sheet port has no volume, so its N-port holds the gap's
    capacitance), or by Z_part ∥ C_box with `cbox` (F, by ref)."""
    by_ref = parts(project)
    refs = [name for name in names if name in by_ref]
    z = {ref: z_part(part_kind(ref), port_value(ref, by_ref[ref]["value"]), None, f) for ref in refs}
    zk = np.stack([z[ref] for ref in refs], -1) if cbox is None else loads(z, refs, cbox, f)
    return terminate(s, [k for k, name in enumerate(names) if name not in by_ref], zk, f)


def cross_check(out: Path) -> dict:
    """D-43's comparison, from the files: <out>/p0b/emerge.json, written and returned as written. openEMS at EMerge's
    frequencies (input.json's), p0.closed_chain of B1 at the ideal values, Z_ideal ∥ C_box; EMerge's 6-port at each
    level (_nport), closed by Z_ideal alone (_chain); "compare", checks.compare(a = EMerge's chain at the finer level,
    b = openEMS's), "compare_75" at the other level, "compare_cbox" with B1's C_box on EMerge's side too (a
    sensitivity), "compare_n3", B5's chain against EMerge's (D-36; None without a p0b-B5 record, PF-33, its project
    found without harness.project, which would make it), "compare_nomask" once nomask ran on this _digest and B1's
    run (else None: an older pair stays on disk after a model fix): EMerge's no-mask chain against the no-mask openEMS
    run closed by the C_box of its own setup.json; "move", the largest |ΔS| between
    the two levels' chains; "nport", STATS per level (None for one not solved); "coupons", each coupon's 45 h row
    against KiCad's Z0 and the 45 h 2D εeff, else its 10 h row against the 10 h εeff, named in "deviations" (OI-7,
    PF-35); "verdict" and "reasons" (verdict: a level or a coupon with neither row not solved, σ_max and the
    reciprocity error the larger of both levels'); "freeze", freeze.txt's lines."""
    e, pj = out / "emerge", harness._path(out, "B1")
    data, project = _read(e / "input.json"), load_project(pj)
    f, fine = np.array(data["lpf915"]["freqs"]), LEVELS[-1]
    _, oems, k0 = p0.closed_chain(pj, f=f, ideal=True)

    def cmp(a: np.ndarray, b: np.ndarray) -> dict:
        return compare(a, b, f, k0, harness.FLOOR)

    levels = {um: _nport(e, f"lpf915-{um}") for um in LEVELS}
    chains = {um: _chain(project, x[0], x[1], f) for um, x in levels.items() if x}
    stats = {um: x and {key: x[2][key] for key in STATS} for um, x in levels.items()}
    unsolved = [f"{um} um" for um, x in levels.items() if x is None]
    coupons, deviations = [], []
    for name, ref in data["coupons"].items():
        path, eeff_ref = e / f"{name}-50.json", ref["eeff_ref"]
        if not path.is_file():  # OI-7: its 10 h row, against the 10 h box's εeff
            path, eeff_ref = e / f"{name}-50-10h.json", ref["eeff_ref_10h"]
            deviations += [f"{name}: 10 h box (OI-7)"] if path.is_file() else []
        if not path.is_file():
            unsolved.append(f"{name} 50 um")
            continue
        row = _read(path)
        coupons.append({"name": name, "edge_um": row["edge_um"], "z0": row["z0"], "z0_ref": ref["z0_ref"],
                        "dz0_pct": 100 * (row["z0"] / ref["z0_ref"] - 1), "eeff": row["eeff"], "eeff_ref": eeff_ref,
                        "deeff_pct": 100 * (row["eeff"] / eeff_ref - 1)})
    bare, b1 = None, Path(project["results"]["run_dir"]).name
    if (_key(out, NOMASK_FEM).startswith(f"{_digest(out)}|") and f"|{b1}@" in _key(out, NOMASK_OPENEMS)
            and (em := _nport(e, "lpf915-75-nomask"))):
        res = _read(out / "steps" / f"{NOMASK_OPENEMS}.json")["result"]
        lay = layout(project, {"run_dir": str(p0.run_path(res["run_dir"])), "jobs": res["jobs"]}, f=f)
        bare = cmp(_chain(project, em[0], em[1], f),
                   _chain(project, lay.s, [q["name"] for q in lay.ports], f, res["setup"]["c_box"]))
    move = float(np.abs(chains[LEVELS[0]] - chains[fine]).max()) if len(chains) == len(LEVELS) else None
    worst = {key: max((x[key] for x in stats.values() if x), default=None) for key in ("sigma_max", "recip")}
    b5 = (out / "steps" / "p0b-B5.json").is_file() and fine in chains
    result = {"coupons": coupons, "nport": stats, "move": move,
              "compare": cmp(chains[fine], oems) if fine in chains else None,
              "compare_75": cmp(chains[LEVELS[0]], oems) if LEVELS[0] in chains else None,
              "compare_cbox": cmp(_chain(project, *levels[fine][:2], f, project["results"]["c_box"]), oems)
              if fine in chains else None,
              "compare_n3": cmp(chains[fine], p0.closed_chain(harness._path(out, "B5"), f=f, ideal=True)[1])
              if b5 else None,
              "compare_nomask": bare}
    value, reasons = verdict(result["compare"], coupons, move, worst["sigma_max"], worst["recip"], unsolved)
    return p0.save(out / "p0b" / "emerge.json", {
        **result, "verdict": value, "reasons": reasons, "deviations": deviations,
        "freeze": (e / "freeze.txt").read_text(encoding="utf-8").splitlines()})


def nomask(out: Path) -> list[str]:
    """D-43's no-mask diagnostic pair, run after a "fail" (OI-4): EMerge's 6-port at 75 µm with no mask, step
    NOMASK_FEM (_solved); openEMS's, B1's model.json (the run folder of its step record) less its mask_* materials as
    a harness model at Normal on every port, step NOMASK_OPENEMS, keyed by its spec_hash and B1's run, so B1 running
    again runs it again. Returns [NOMASK_FEM] when that FEM step raised or did not solve, else []."""
    ok = _solved(out, NOMASK_FEM, "nport", "--input", "input.json", "--edge-um", LEVELS[0], "--mask", "none",
                 "--out", "lpf915-75-nomask.npz")
    run = p0.records(out, ["p0b-B1"])[0]["result"]["run_dir"]
    spec = _read(p0.run_path(run) / "model.json")
    bare = {**spec, "materials": [m for m in spec["materials"] if not m["name"].startswith("mask_")]}
    p0.step(out, NOMASK_OPENEMS, f"{spec_hash(bare)}|{run}",
            partial(p0.run_model, p0.model_of(bare), "normal", NOMASK_OPENEMS, list(range(1, len(bare["ports"]) + 1))))
    return [] if ok else [NOMASK_FEM]


def venv(e: Path) -> None:
    """The validation venv in the EMerge folder `e` (D-41): made once by `uv venv` with Python 3.13 in <e>/venv,
    filled from REQUIREMENTS (uv keeps what already matches), and its `uv pip freeze` written to <e>/freeze.txt
    (PF-36); every uv call with one explicit environment, so that uv keeps its Pythons and its cache in `e`, takes
    only a Python it manages there, never a global one, and reads no uv config file."""
    env = {**os.environ, "UV_PYTHON_INSTALL_DIR": str(e / "python"), "UV_CACHE_DIR": str(e / "uv-cache"),
           "UV_PYTHON_PREFERENCE": "only-managed", "UV_NO_CONFIG": "1"}
    python = _python(e)
    e.mkdir(parents=True, exist_ok=True)
    if not python.is_file():
        subprocess.run(["uv", "venv", "--python", "3.13", str(e / "venv")], env=env, check=True)
    subprocess.run(["uv", "pip", "install", "--python", str(python), "-r", str(REQUIREMENTS)], env=env, check=True)
    freeze = subprocess.run(["uv", "pip", "freeze", "--python", str(python)], env=env, check=True,
                            capture_output=True, encoding="utf-8", errors="replace").stdout
    (e / "freeze.txt").write_text(freeze, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """python tools/p0b/emerge_app.py run [--out DIR] (D-41..D-43), one background command: enters the P0 folder
    first, then the validation venv, export of B1's project, the FEM steps, the cross-check, the no-mask pair and the
    cross-check again when its verdict is "fail" (else the pair's records move aside, _supersede), then
    harness.write. Returns 1, once the gate is written, when a FEM step raised or did not solve (a coupon solved in
    its 10 h box counts as solved), else 0."""
    parser = argparse.ArgumentParser(prog="emerge_app", description="P0-B's EMerge cross-check (D-41..D-44).")
    parser.add_argument("command", choices=["run"], help="run every step not yet recorded, then write the gate")
    parser.add_argument("--out", help="the P0 folder (default: kicad-rf-studio-p0 beside the per-user data folder)")
    a = parser.parse_args(argv)
    out = p0.enter(Path(a.out) if a.out else p0.default_out())
    venv(out / "emerge")
    export(harness._path(out, "B1"), out)
    failed = fem_steps(out)
    if cross_check(out)["verdict"] == "fail":
        failed += nomask(out)
        cross_check(out)
    else:  # the pair runs only after a "fail" (D-43)
        _supersede(out, NOMASK_FEM, NOMASK_OPENEMS)
    harness.write(out)
    if failed:
        print(f"emerge_app: failed: {', '.join(failed)}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
