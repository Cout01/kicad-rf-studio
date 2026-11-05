# SPDX-License-Identifier: GPL-3.0-or-later
"""P4-D, ports, pulse and loss (Stage 4 design 5.3–5.5, 5.11; plan 4 rulings D-1 to D-5). It runs:
- the vertical port against the horizontal one on two pad coupons;
- the DC point against the ports' copper connectivity;
- a 100 mm line, lossless and Debye, against scikit-rf's MLine;
- the Debye cell weight and the USB 2.0 fixture's predicted slowdown.

Each is judged against `tests/fixtures/p4d/criteria.json` and the committed `references.json`, and p4d.json and p4d.md
are written in <out>/p4d. Run: `python tools/p4d.py --out DIR [--steps ...] [--references]`."""
import argparse
import json
import math
import sys
import tempfile
import warnings
from functools import partial
from pathlib import Path

import numpy as np
import skrf as rf
from shapely.geometry import Point
from skrf.media import MLine

import p0
import p3
import p4
from kicad_rf_studio import pipeline
from kicad_rf_studio.core.model.parts import COPPER, CURVE_PORT, GRID, PORT
from kicad_rf_studio.core.model.ports import _pad
from kicad_rf_studio.core.model.spec import debye_cells
from kicad_rf_studio.core.post.si import Reading, db, uniform_grid
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import load_project, parts, save_project

CRITERIA = json.loads((p0.FIX / "p4d" / "criteria.json").read_text(encoding="utf-8"))  # committed before any run
REFERENCES = p0.FIX / "p4d" / "references.json"  # written once by --references, committed before any run
VERTICAL = {"si_pad_coupon": "In1.Cu", "si_pad_coupon_tall": "B.Cu"}  # each pad coupon's plane, 0.2 and 1.51 mm down
LINE, USB = "si_line100", "usb2_hs"  # the 100 mm line (D-1) and the USB 2.0 fixture, each lossless and with Debye
# each step's (board, dielectric, tag): a pad coupon's h and v ports, then each lossless run and its Debye twin
STEPS = {**{f"{b}-{side}": (b, "lossless", tag) for b in VERTICAL for side, tag in (("h", ""), ("v", "v"))},
         **{f"{b}{end}": (b, d, "") for b in (LINE, USB) for end, d in (("", "lossless"), ("-debye", "debye"))}}
DC_BOARDS = (*VERTICAL, LINE, USB, "usb2_hs_neck", "usb2_hs_gap")  # the boards whose DC point is referenced (D-2)
# scikit-rf's MLine (D-1, D-3): si_line100's 0.33 mm trace on 0.2 mm of FR-4, Djordjevic-Sarkar, t 35 µm; il_ref takes
# its dielectric loss alone, as the model's copper is PEC
MLINE = {"z0_port": 50, "w": 0.33e-3, "h": 0.2e-3, "t": 35e-6, "ep_r": 4.3, "tand": 0.02, "rho": 1.68e-8,
         "diel": "djordjevicsvensson", "f_low": 1e3, "f_high": 1e12, "f_epr_tand": 1e9}
COPPER_DS = 1.5e-3  # the 100 mm line's R/100: real copper's move of its DC S, which the ideal wires leave out


def make_vertical(pj: Path, plane: str) -> None:
    """Makes every external port of the project at `pj` vertical (Stage 4 design 5.5): its reference {"plane": plane},
    its rule "plane", saving only on a change, so its results stay. Dotted edits cannot reach a list."""
    data = load_project(pj)
    ports = [{**port, "reference": {"plane": plane}, "rule": "plane"} for port in data["ports"]]
    if ports != data["ports"]:
        save_project(pj, {**data, "ports": ports})


def dc_s(pj: Path) -> tuple[list[str], np.ndarray]:
    """The DC point of the project at `pj` (ruling D-2), from its copper's connectivity. Its ports are the model's,
    external then parts (core.model.ports.ends), each a branch between two nets:
    - an external port's from its signal pad's net to its reference's: a "pad" reference's pad's; a "point" one's, the
      net of the piece on its layer covering it; a "plane" one's, the net of the plane piece under the signal pad's
      centroid (each the nearest piece, as the pieces are simplified);
    - a part port's between its two pads' nets.
    Nets joined by a part of role "copper" are one node. With A the node-by-port incidence (+1 signal, −1 reference),
    P = Aᵀ(AAᵀ)⁺A, the projector onto its cut space, and S = 2P − I. Returns (the port names, S)."""
    # ponytail: PEC copper, so the network is ideal wires; real copper moves DC S by about R/100 (1.5e-3 on 100 mm),
    # recorded
    project, board, geom, _ = pipeline.load(pj)

    def net(layer: str, at: Point) -> str:  # the piece on `layer` covering `at`, or within the simplification of it
        return min((pc for pc in geom.pieces if pc.layer == layer), key=lambda pc: pc.polygon.distance(at)).net

    branches = []  # (name, signal's net, reference's net)
    for port in project["ports"]:
        ref, layer = port["reference"], port["layer"]
        sig = _pad(board, port["signal"], port["signal_uuid"], layer)
        if "plane" in ref:
            other = net(ref["plane"], sig.polygon.centroid)
        elif "pad" in ref:
            other = _pad(board, ref["pad"], ref["uuid"], layer).net
        else:
            other = net(ref["layer"], Point(ref["point"][0], -ref["point"][1]))  # project.json has y down
        branches.append((port["name"], sig.net, other))
    branches += [(ref, *q["nets"]) for ref, q in parts(project).items() if q["role"] in (PORT, CURVE_PORT, GRID)]
    joined = {}  # a net a copper part joins to another, toward the node's last

    def node(n: str) -> str:
        while n in joined:
            n = joined[n]
        return n

    for q in parts(project).values():
        if q["role"] == COPPER and (one := node(q["nets"][0])) != (other := node(q["nets"][1])):
            joined[one] = other
    nodes = sorted({node(n) for _, *nets in branches for n in nets})
    a = np.zeros((len(nodes), len(branches)))
    for k, (_, signal, reference) in enumerate(branches):
        a[nodes.index(node(signal)), k] += 1
        a[nodes.index(node(reference)), k] -= 1
    p = np.linalg.pinv(a) @ a  # Aᵀ(AAᵀ)⁺A, from A's own SVD
    return [name for name, *_ in branches], 2 * p - np.eye(len(branches))


def dc_check(pj: Path, ref: dict) -> float:
    """The DC point's miss of the run in the results of the project at `pj` (ruling D-2): the largest
    | |S(0)| − |S_ref| | over every entry, S(0) its layout's at DC (core.post.waves.layout) and S_ref ref's "s"
    (references' dc[board]). A part port's sign is its box's orientation, which the reference does not read; a -v
    project takes its board's entry, its plane being on the reference's net. ValueError when the layout's port names
    are not ref's "names"."""
    project = load_project(pj)
    lay = layout(project, project["results"])
    if (names := [port["name"] for port in lay.ports]) != ref["names"]:
        raise ValueError(f"p4d: the layout's ports {names} are not the reference's {ref['names']}")
    return float(np.abs(np.abs(lay.s[0]) - np.abs(np.asarray(ref["s"]))).max())


def il_ref(f: np.ndarray) -> np.ndarray:
    """The 100 mm line's dielectric loss in dB on `f` (Hz) (D-1, D-3): 8.686·alpha_dielectric·0.1 m of scikit-rf's
    MLine called with MLINE, its warnings suppressed."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        line = MLine(frequency=rf.Frequency.from_f(f, unit="Hz"), **MLINE)
    return 8.686 * line.alpha_dielectric * 0.1


def il_metric(s: np.ndarray) -> np.ndarray:
    """The insertion loss in dB of the 2-port S `s` (F, 2, 2) with its mismatch taken out: −10·log10(|S21|²/(1 −
    |S11|²))."""
    return -10 * np.log10(np.abs(s[:, 1, 0]) ** 2 / (1 - np.abs(s[:, 0, 0]) ** 2))


def share(spec: dict) -> float:
    """The share of the model spec `spec`'s cells that are Debye: debye_cells over its cells, as cost counts them."""
    return debye_cells(spec) / math.prod(len(spec["mesh"][a]) for a in "xyz")


def weight(lossless_mcs: float, debye_mcs: float, f: float) -> float:
    """A Debye cell's weight (design 5.3; D-3): 1 + (R − 1)/f, R = `lossless_mcs`/`debye_mcs` (MC/s), the Debye run's
    share of cells `f`."""
    return 1 + (lossless_mcs / debye_mcs - 1) / f


def slowdown(w: float, f: float) -> float:
    """A model's predicted slowdown with Debye: 1 + f·(w − 1), the Debye share `f` of its cells at the weight `w`."""
    return 1 + f * (w - 1)


def references() -> dict:
    """P4-D's references (G-1), computed in memory in a temporary folder, no openEMS, the only caller of dc_s and
    il_ref:
    - "il_ref": {"f_hz", "db"}, il_ref on uniform_grid(10e9)'s points from f_lo_hz, and "call", MLINE;
    - "dc": {board: {"names", "s"}}, dc_s of each board of DC_BOARDS' base (p4.base, `new` with P4_NEW);
    - "z0": each P4-D board's 2D Z0, its I_SI_2D_LINE row (pipeline.si_readout); "copper_ds": COPPER_DS.
    Then "code" (p0.code_id()) and "versions"."""
    f = uniform_grid(10e9)
    f = f[f >= CRITERIA["f_lo_hz"]]
    dc, z0 = {}, {}
    with tempfile.TemporaryDirectory() as folder:
        for board in DC_BOARDS:
            pj = p4.base(Path(folder), board)
            names, s = dc_s(pj)
            dc[board] = {"names": names, "s": s}
            if board in (*VERTICAL, LINE):
                project, board_, geom, _ = pipeline.load(pj)
                z0[board] = next(float(p["z0"]) for code, p in pipeline.si_readout(board_, geom, project)
                                 if code == "I_SI_2D_LINE")
    return {"source": "tools/p4d.py --references, before any P4-D run: scikit-rf's MLine dielectric loss of the 100 mm "
                      "line (8.686 alpha_dielectric 0.1 m), the DC point 2P - I of each board's copper and each P4-D "
                      "board's 2D Z0",
            "il_ref": {"f_hz": f, "db": il_ref(f), "call": MLINE}, "dc": dc, "z0": z0, "copper_ds": COPPER_DS,
            "code": p0.code_id(), "versions": p0.versions()}


def _name(step: str) -> str:
    """The project of the step `step` of STEPS at p4.N and p4.RULE."""
    board, dielectric, tag = STEPS[step]
    return p4.name(board, dielectric=dielectric, tag=tag)


def step(out: Path, name: str) -> dict:
    """The step `name` of STEPS, p4's run step at p4.N and p4.RULE: a pad coupon's h port (its project as `new` made
    it) or v port (tagged "v", after make_vertical to its VERTICAL plane), or the line's or the USB fixture's run,
    lossless or with "-debye". The lossless usb2_hs is P4-F's base, the same step. KeyError for another name."""
    board, dielectric, tag = STEPS[name]
    title, pj = p4.project(out, board, dielectric=dielectric, tag=tag)
    if tag:
        make_vertical(pj, VERTICAL[board])
    return p4.run_step(out, title)


def _dc_projects(out: Path) -> list[str]:
    """The projects of the run steps recorded in <out> whose board has a DC reference (DC_BOARDS) and that are
    lossless: every lossless P4-D project and every usb2_hs* one, P4-F's included."""
    names = [p.stem.removeprefix("p4-").removesuffix("-run") for p in sorted((out / "steps").glob("p4-*-run.json"))]
    return [n for n in names if n.partition("-n")[0] in DC_BOARDS
            and load_project(p3.project_path(out, n))["dielectric"] == "lossless"]


def _port(r: Reading | None) -> tuple[float | None, float | None, float | None]:
    """A pad coupon's port readings of the Reading `r`, t_r = r.rise[0], each None without `r`: its plateau, the median
    of the localising TDR from t_r to t_far − t_r (p4.plateau; None without t_far); then its launch, recorded: the
    largest db(S11) up to f_max, and the largest |z − plateau| over 0 ≤ t ≤ t_r (None without the plateau)."""
    if r is None:
        return None, None, None
    t_r = r.rise[0]
    z = r.t_far and p4.plateau(r, t_r, r.t_far - t_r)
    first = r.z[(r.t >= 0) & (r.t <= t_r)]
    return z, float(db(r.s[:, 0, 0]).max()), None if z is None else float(np.abs(first - z).max())


def measure(out: Path) -> dict:
    """P4-D's measurements in <out>, in this process:
    - "runs": p4.measure of each recorded step of STEPS, by its name;
    - "ports": per pad coupon with both its steps recorded, "h" and "v", its two plateaus, with "<side>_launch_db" and
      "<side>_launch_ohm" (_port of each reading);
    - "dc": {project: dc_check of it against its board's references} for each of _dc_projects, None when its run's
      results are not its own (p4.measure's fingerprint None);
    - "invalid": the recorded steps whose run is not valid;
    - "debye", from the line's two runs: "il_ok", the Debye run's insertion loss (il_metric) less its lossless twin's
      against refs' il_ref over f_lo_hz ≤ f ≤ f_max, within max(il_db, il_rel·IL_ref), with "il_worst", its worst
      [ratio, f]; "dc_loss", 1 − |S11(0)|² − |S21(0)|² of the Debye run; "il_lossless_db", the twin's largest IL, the
      walls' and radiation's floor (each None while a run is unrecorded, il_ok False for a run without a reading); "w",
      weight of their node_mcs at share of the Debye run's model.json; "f_usb", share of usb2_hs's Debye model at p4.N
      and p4.RULE, built in memory; "measured", the usb2_hs pair's node_mcs ratio, lossless over Debye, when both ran,
      else None."""
    c, refs = CRITERIA, json.loads(REFERENCES.read_text(encoding="utf-8"))
    runs = {s: x for s in STEPS if (x := p4.measure(out, _name(s))) is not None}
    ports = {}
    for board in VERTICAL:
        if all(f"{board}-{side}" in runs for side in "hv"):
            ports[board] = {}
            for side in "hv":
                z, s11, dz = _port(runs[f"{board}-{side}"]["reading"])
                ports[board] |= {side: z, f"{side}_launch_db": s11, f"{side}_launch_ohm": dz}
    dc, ours = {}, {_name(s): x for s, x in runs.items()}
    for name in _dc_projects(out):
        x = ours.get(name) or p4.measure(out, name)
        dc[name] = None if x["fingerprint"] is None else dc_check(p3.project_path(out, name),
                                                                   refs["dc"][name.partition("-n")[0]])
    lossless, debye = runs.get(LINE), runs.get(f"{LINE}-debye")
    il = dict.fromkeys(("il_ok", "il_worst", "dc_loss", "il_lossless_db"))
    if lossless and debye:
        a, b = lossless["reading"], debye["reading"]
        il["il_ok"] = False
        if a and b:
            f = b.f
            band = (f >= c["f_lo_hz"]) & (f <= debye["project"]["f_max_hz"])
            floor = il_metric(a.s[band])
            ref = np.interp(f[band], refs["il_ref"]["f_hz"], refs["il_ref"]["db"])
            ratio = np.abs(il_metric(b.s[band]) - floor - ref) / np.maximum(c["il_db"], c["il_rel"] * ref)
            k = int(ratio.argmax())
            il = {"il_ok": bool(ratio[k] <= 1), "il_worst": [float(ratio[k]), float(f[band][k])],
                  "dc_loss": float(1 - abs(b.s[0, 0, 0]) ** 2 - abs(b.s[0, 1, 0]) ** 2),
                  "il_lossless_db": float(floor.max())}
    w = None
    if lossless and debye and lossless["node_mcs"] and debye["node_mcs"]:
        spec = json.loads((p0.run_path(debye["run_dir"]) / "model.json").read_text(encoding="utf-8"))
        w = weight(lossless["node_mcs"], debye["node_mcs"], share(spec))
    project, board, geom, _ = pipeline.load(p4.project(out, USB, dielectric="debye")[1])
    usb = [runs.get(s, {}).get("node_mcs") for s in (USB, f"{USB}-debye")]
    return {"runs": runs, "ports": ports, "dc": dc, "invalid": [s for s, x in runs.items() if not x["valid"]],
            "debye": {**il, "w": w, "f_usb": share(pipeline.build_model(project, board, geom).spec),
                      "measured": usb[0] / usb[1] if all(usb) else None}}


def decide(m: dict) -> dict:
    """P4-D's decisions (design 5.11's fallbacks; D-2, D-3, D-5) on the measures `m` (measure's shape) by CRITERIA,
    each limit inclusive and a None value a miss:
    - "port": "kept" when both coupons' |v/h − 1| ≤ plateau_rel, "graded" when only si_pad_coupon_tall misses,
      "ruling" when si_pad_coupon misses; None while a coupon is unmeasured. A coupon whose v step is in m["invalid"]
      misses, whatever its plateau: its vertical port's run is judged as its port (plan 4 ruling R-5);
    - the DC point passes when every value of m["dc"] is at most dc_abs;
    - "debye": "predicted", slowdown(w, f_usb) (None without either); "run_usb", predicted inside run_usb while
      "measured" is None; "accurate", il_ok and dc_loss ≤ the criteria's dc_loss;
    - "dielectric": None while the line's runs are unrecorded (il_ok None); else "lossless" unless accurate; else None
      while run_usb; else "debye" when measured, else predicted, is at most slowdown_max, "lossless" above it (None
      without either);
    - "verdict": {"value": "fail" on a DC miss, a port "ruling" or an invalid run other than a pad coupon's v step
      (each a controller ruling, src being frozen), else "incomplete" while the port or the dielectric is None, else
      "fallback" when the port is "graded" or Debye is not accurate, else "pass"; "fails": "<project>: dc",
      "si_pad_coupon: port" and "<step>: valid", each invalid step but the two v steps (R-5)}."""
    c, d = CRITERIA, m["debye"]

    def kept(board: str) -> bool | None:  # its v plateau within plateau_rel of its h one; None while unmeasured
        if f"{board}-v" in m["invalid"]:  # R-5: an invalid v run misses, whatever its plateau
            return False
        x = m["ports"].get(board)
        return None if x is None else None not in (x["h"], x["v"]) and abs(x["v"] / x["h"] - 1) <= c["plateau_rel"]

    short, tall = kept("si_pad_coupon"), kept("si_pad_coupon_tall")
    port = None if None in (short, tall) else "ruling" if not short else "kept" if tall else "graded"
    predicted = None if None in (d["w"], d["f_usb"]) else slowdown(d["w"], d["f_usb"])
    run_usb = predicted is not None and c["run_usb"][0] <= predicted <= c["run_usb"][1] and d["measured"] is None
    accurate = bool(d["il_ok"]) and d["dc_loss"] is not None and d["dc_loss"] <= c["dc_loss"]
    speed = predicted if d["measured"] is None else d["measured"]
    if d["il_ok"] is None or accurate and (run_usb or speed is None):  # unread, or its speed not yet known
        dielectric = None
    elif accurate and speed <= c["slowdown_max"]:
        dielectric = "debye"
    else:
        dielectric = "lossless"
    fails = [f"{p}: dc" for p, x in m["dc"].items() if x is None or x > c["dc_abs"]]
    fails += ["si_pad_coupon: port"] if port == "ruling" else []
    v_steps = {f"{board}-v" for board in VERTICAL}  # R-5: judged as their coupon's port, not as "<step>: valid"
    fails += [f"{s}: valid" for s in m["invalid"] if s not in v_steps]
    if fails:
        value = "fail"
    elif port is None or dielectric is None:
        value = "incomplete"
    elif port == "graded" or not accurate:
        value = "fallback"
    else:
        value = "pass"
    return {"port": port, "dielectric": dielectric,
            "debye": {"predicted": predicted, "run_usb": run_usb, "accurate": accurate},
            "verdict": {"value": value, "fails": fails}}


def tables(result: dict) -> str:
    """The Markdown tables of the gate JSON `result` (write's), by p0.table: P4D-1 the ports (each coupon's h and v
    plateaus, its v run's validity (R-5), their ratio and the 2D Z0, with their launches recorded) and the decisions
    with the verdict; P4D-2 the DC point of each lossless project; P4D-3 Debye and speed; P4D-4 the runs: cells, Debye
    cells, pool, node MC/s, t_stop, predicted to t_stop and to T_max, wall, valid."""
    c, refs, d = result["criteria"], result["references"], result["debye"]
    ports = [{"coupon": k, "plane": VERTICAL[k], **x, "v_valid": result["runs"][f"{k}-v"]["valid"],
              "v_over_h": None if None in (x["h"], x["v"]) else x["v"] / x["h"], "z0_2d": refs["z0"][k]}
             for k, x in result["ports"].items()]
    worst = d["il_worst"] or [None, None]
    items = [*({"item": key, "value": result[key]} for key in ("n_now", "rule_now", "port", "dielectric")),
             {"item": "verdict", "value": result["verdict"]["value"]},
             {"item": "fails", "value": ", ".join(result["verdict"]["fails"]) or "none"}]
    debye = [*({"item": key, "value": d[key]} for key in ("il_ok", "accurate")),
             {"item": "il_worst_ratio", "value": worst[0]}, {"item": "il_worst_hz", "value": worst[1]},
             *({"item": key, "value": d[key]} for key in ("dc_loss", "il_lossless_db", "w", "f_usb", "predicted",
                                                          "measured", "run_usb")),
             {"item": "dielectric", "value": result["dielectric"]}]
    return "\n\n".join([
        "## P4D-1 The ports",
        f"The vertical port (v, to the coupon's plane) against the horizontal one (h, as `new` made it) on each pad "
        f"coupon, lossless at mesh n {result['n_now']} and the rule {result['rule_now']}: each plateau the median of "
        f"the localising TDR from t_r to t_far − t_r; kept when both coupons' |v/h − 1| ≤ {c['plateau_rel']:g}, graded "
        "when only the 1.51 mm coupon misses (a vertical port longer than λ/20 at f_max in the stack's highest εr is "
        "refused), a controller ruling when the 0.2 mm one misses; a coupon whose v run is not valid (v_valid) "
        "misses, whatever its plateau (plan 4 ruling R-5). The plateau tests the port's impedance scale, not its "
        "launch; each launch is recorded: the largest |S11| up to f_max (dB) and the TDR's largest departure from the "
        "plateau within the first t_r (Ω). z0_2d, the 2D table's Z0.",
        p0.table(ports, ["coupon", "plane", "h", "v", "v_valid", "v_over_h", "z0_2d", "h_launch_db", "v_launch_db",
                         "h_launch_ohm", "v_launch_ohm"]),
        p0.table(items, ["item", "value"]),
        "## P4D-2 The DC point",
        f"Each lossless project's largest | |S_layout(0)| − |2P − I| | over every entry, P the projector onto the cut "
        f"space of its ports' copper (nets joined by copper parts) from the committed references, within "
        f"{c['dc_abs']:g}; a Debye run carries its slowest pole's tail and is judged by its DC loss alone. Real "
        f"copper would move it by about R/100, {refs['copper_ds']:g} on the 100 mm line: the model's is PEC.",
        p0.table([{"project": k, "dc": x, "pass": x is not None and x <= c["dc_abs"]} for k, x in result["dc"].items()],
                 ["project", "dc", "pass"]),
        "## P4D-3 Debye and speed",
        f"The 100 mm line's insertion loss −10·log10(|S21|²/(1 − |S11|²)), the Debye run's less its lossless twin's "
        f"(the walls' and radiation's, il_lossless_db), against scikit-rf's MLine dielectric loss over "
        f"{c['f_lo_hz']:g} Hz to f_max, within max({c['il_db']:g} dB, {c['il_rel']:g}·IL_ref): il_worst is its worst "
        f"ratio to that limit and its frequency; accurate also needs 1 − |S11(0)|² − |S21(0)|² ≤ {c['dc_loss']:g}. "
        "The cell weight w = 1 + (R − 1)/f, R the median job MC/s lossless over Debye, f the Debye run's share of "
        "cells; the USB 2.0 fixture's slowdown 1 + f_usb·(w − 1) predicted, run with Debye only inside "
        f"[{c['run_usb'][0]:g}, {c['run_usb'][1]:g}] (run_usb). Debye is the default when accurate and the slowdown, "
        f"measured else predicted, is at most {c['slowdown_max']:g}.",
        p0.table(debye, ["item", "value"]),
        "## P4D-4 Runs",
        p0.table([{"step": k, **x} for k, x in result["runs"].items()],
                 ["step", "cells", "debye_cells", "pool", "node_mcs", "t_stop_s", "predicted_s", "worst_s", "wall_s",
                  "valid"])]) + "\n"


def write(out: Path) -> dict:
    """p4.records over every run step it reads first (SystemExit on two product codes), then measure and decide of
    <out>: <out>/p4d/p4d.json through p0.save, with the versions, CRITERIA, the references, the calibration
    (p3.calibration), n_now and rule_now, "runs", each recorded step's p4.plain by its --steps name, measure's ports,
    dc and invalid, decide's port, dielectric and verdict, "debye", measure's and decide's ("w", which Task 15 reads,
    "f_usb", "predicted", "measured", "il_ok", "il_worst", "dc_loss" among them), and the steps' machine time
    (p0.machine); p4d.md beside it (tables). Returns the JSON as saved."""
    names = dict.fromkeys([*map(_name, STEPS), *_dc_projects(out)])
    recs = p4.records(out, [p3.step_id(name, "run", "p4") for name in names])
    refs, m = json.loads(REFERENCES.read_text(encoding="utf-8")), measure(out)
    d = decide(m)
    result = p0.save(out / "p4d" / "p4d.json", {
        "gate": "P4-D", "versions": p0.versions(), "criteria": CRITERIA, "references": refs,
        "calibration": p3.calibration(), "n_now": p4.N, "rule_now": p4.RULE,
        "runs": {s: p4.plain(x) for s, x in m["runs"].items()}, "ports": m["ports"], "dc": m["dc"],
        "invalid": m["invalid"], "port": d["port"], "dielectric": d["dielectric"], "debye": m["debye"] | d["debye"],
        "verdict": d["verdict"], "machine": p0.machine(recs)})
    (out / "p4d" / "p4d.md").write_text(tables(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p4d.py --references: writes REFERENCES through p0.save, SystemExit when it exists. python
    tools/p4d.py --out DIR [--steps a,b]: enters <GATES> (p4.enter); with --steps, runs each of them in order
    (p4.run_steps) and returns 1 when one raised, else 0; without, writes the report and returns 0."""
    parser = argparse.ArgumentParser(prog="p4d", description="P4-D, ports, pulse and loss (Stage 4 design 5.11).")
    parser.add_argument("--out", help="<GATES>, outside every git work tree")
    parser.add_argument("--steps", help=f"comma-separated steps of {', '.join(STEPS)}; without it, the report")
    parser.add_argument("--references", action="store_true", help="write the references once, before any run")
    args = parser.parse_args(argv)
    if args.references:
        if REFERENCES.exists():
            raise SystemExit("P4-D's references are committed once, before its runs, and never regenerated")
        p0.save(REFERENCES, references())
        return 0
    if args.out is None:
        parser.error("--out is required without --references")
    out = p4.enter(Path(args.out))
    if args.steps:
        return p4.run_steps(args.steps.split(","), partial(step, out))
    write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
