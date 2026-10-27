# SPDX-License-Identifier: GPL-3.0-or-later
"""Plan 7's gate tool (design 2026-10-26 §5.2): A-10's single-L coupon check (E-7), its runs resumable p0.steps in the
fresh P0 folder. Dev-time only, like p0: the package never imports it. Run: python tools/p0b2.py coupon --out DIR"""
# ponytail: single-use, plan 7's checks and its one P0-B2
import argparse
import json
import sys
from functools import partial
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

import p0
from kicad_rf_studio.core.kicad.values import part_kind, port_value
from kicad_rf_studio.core.model.spec import strip_dl
from kicad_rf_studio.core.post.chain import loads, terminate, z_part
from kicad_rf_studio.core.post.checks import compare
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import load_project
from kicad_rf_studio.stoprule import PRESETS

COUPON = ("--start", "TP1.1", "--end", "TP2.1", "--f0", "2.4GHz")  # new's arguments for the single-L coupon (E-7)
L_COUPON = "6.8nH"  # the coupon's L1
DL_BAND = (0.0870e-9, 0.1616e-9)  # the closed form's ±30 % on the coupon's L1 box, 0.124283 nH (E-7)
DS21_COUPON_DB = 0.02  # the limit on the compensated run's |ΔS21(f0)| in dB (E-7)
FLOOR = 10 * PRESETS["normal"][1]  # the null floor, as verify derives it at Normal


def single_l(value: str) -> str:
    """tests/fixtures/coupon_gcpw_pads.kicad_pcb with an 0402 inductor of `value` across a 1 mm cut of its line at
    x 110 (A-10's coupon, E-7): net 3 LINE_B; the line 100→120 split into 100→109.5 on LINE and 110.5→120 on LINE_B;
    TP2's pad on LINE_B; lpf915's L1 footprint at (110, 100) between LINE and LINE_B, its Value `value`. ValueError
    when an edit does not apply exactly once."""
    def once(text: str, old: str, new: str) -> str:
        if text.count(old) != 1:
            raise ValueError(f"p0b2: {old!r} is in the board {text.count(old)} times, not once")
        return text.replace(old, new)

    text = (p0.FIX / "coupon_gcpw_pads.kicad_pcb").read_text(encoding="utf-8")
    lpf = (p0.FIX / "lpf915.kicad_pcb").read_text(encoding="utf-8")
    a = lpf.index('\t(footprint "Inductor_SMD:L_0402_1005Metric"')
    l1 = lpf[a:lpf.index("\n\t(footprint", a + 1) + 1]
    for old, new in (("(at 106.5 100)", "(at 110 100)"), ('(net 4 "RF_B")', '(net 1 "LINE")'),
                     ('(net 5 "RF_C")', '(net 3 "LINE_B")'), ('"Value" "15nH"', f'"Value" "{value}"')):
        l1 = once(l1, old, new)
    text = once(text, '\t(net 2 "GND")\n', '\t(net 2 "GND")\n\t(net 3 "LINE_B")\n')
    text = once(text,
                '\t(segment\n\t\t(start 100 100)\n\t\t(end 120 100)\n\t\t(width 0.6)\n\t\t(layer "F.Cu")\n\t\t(net 1)\n',
                '\t(segment\n\t\t(start 100 100)\n\t\t(end 109.5 100)\n\t\t(width 0.6)\n\t\t(layer "F.Cu")\n\t\t(net 1)\n'
                '\t\t(uuid "00000000-0000-4000-8000-0000000000a1")\n\t)\n'
                '\t(segment\n\t\t(start 110.5 100)\n\t\t(end 120 100)\n\t\t(width 0.6)\n\t\t(layer "F.Cu")\n\t\t(net 3)\n')
    i = text.index('(net 1 "LINE")', text.index("\t(footprint"))  # TP2, the first footprint, at (120, 100)
    text = text[:i] + '(net 3 "LINE_B")' + text[i + len('(net 1 "LINE")'):]
    i = text.index("\t(segment")
    return text[:i] + l1 + text[i:]


def fit_dl(s, f, c_box: dict, values: dict[str, float], ref: str, measured) -> float:
    """ΔL (H) of the part `ref` from the 2-port `measured` (F, 2, 2) on `f` (E-7): least squares over every f and
    entry, real and imaginary parts, of terminate(s, [0, 1], loads) − measured, `s` the layout N-port (F, N, N; ports 0
    and 1 external, then the part ports in the order of `values`), each part port closed by its ideal Z_part at
    values[r] (by ref: F, H or Ω) ∥ c_box[r], `ref`'s at values[ref] + ΔL. With values[ref] the grid L, ΔL is the
    strips' term whatever value sat in the grid."""
    refs = list(values)

    def residual(x: np.ndarray) -> np.ndarray:
        z = {r: z_part(part_kind(r), values[r] + (x[0] * 1e-9 if r == ref else 0.0), None, f) for r in refs}
        d = (terminate(s, [0, 1], loads(z, refs, c_box, f), f) - measured).ravel()
        return np.concatenate([d.real, d.imag])

    return float(least_squares(residual, [0.0]).x[0] * 1e-9)


def a10(verdicts: list[str], dl_h: float | None, ds21_db: float | None) -> dict:
    """A-10's rule (E-7) on the coupon's job verdicts, the uncompensated pair's fitted ΔL (H) and the compensated
    run's |ΔS21(f0)| (dB): "void" unless all seven jobs converged; "pass" when not void, ΔL inside DL_BAND and
    |ΔS21(f0)| at most DS21_COUPON_DB, both edges inclusive."""
    void = verdicts != ["converged"] * 7
    return {"void": void, "pass": not void and DL_BAND[0] <= dl_h <= DL_BAND[1] and ds21_db <= DS21_COUPON_DB}


def _model(run_dir: str) -> dict:
    """The model.json of the run folder named `run_dir`."""
    return json.loads((p0.run_path(run_dir) / "model.json").read_text(encoding="utf-8"))


def coupon(out: Path) -> dict:
    """A-10's single-L coupon check (E-7) in the P0 folder `out`, entered first. Its project
    <out>/p0b2/coupon_gcpw_l/project.json is made by `new` with COUPON from single_l(L_COUPON), written to
    <out>/boards/coupon_gcpw_l.kicad_pcb, when it is missing (RuntimeError on a non-zero exit). The steps: a10-run, its
    `run`, keyed by p0.model_key; only when it stored its results, the closed form's ΔL of L1 (strip_dl on its run
    folder's model.json), then a10-uncomp and a10-comp, keyed by that key and a10-run's run, each L1 retuned
    (RuntimeError on a non-zero exit) then `verify`, storing project.json's verify when it stored one: a10-uncomp at
    L_COUPON + ΔL, so that verify's grid holds L_COUPON (the uncompensated construction), a10-comp at L_COUPON. When all
    seven jobs converged, on the project's results (SystemExit unless they hold a10-run's run): each verify pair's
    fitted ΔL over its grid L (fit_dl), the uncompensated run's |ΔS21(f0)| (dB) against the ideal chain at L_COUPON,
    report only, and the compensated run's stored one. Saves <out>/p0b2/a10.json with p0.versions() and returns
    {"dl_cf_h", "band_h", "dl_fit_h": {"uncomp", "comp"}, "ds21_uncomp_db", "ds21_comp_db", "verdicts", "void",
    "pass"} (a10's rule), each value not computed None."""
    out = p0.enter(out)
    pj = out / "p0b2" / "coupon_gcpw_l" / "project.json"
    if not pj.is_file():
        board = out / "boards" / "coupon_gcpw_l.kicad_pcb"
        board.parent.mkdir(parents=True, exist_ok=True)
        board.write_text(single_l(L_COUPON), encoding="utf-8")
        code, text = p0.cli("new", str(board), *COUPON, "-o", str(pj.parent))
        if code:
            raise RuntimeError(f"p0b2: new exited {code}: {(text.strip().splitlines() or [''])[-1]}")
    key = p0.model_key(pj)
    run = p0.step(out, "a10-run", key, partial(p0.cli_run, pj, "run"))

    def verify(value: str) -> dict:
        code, text = p0.cli("retune", str(pj), f"L1={value}")
        if code:
            raise RuntimeError(f"p0b2: retune exited {code}: {(text.strip().splitlines() or [''])[-1]}")
        r = p0.cli_run(pj, "verify")
        return {**r, "verify": load_project(pj)["verify"] if r["jobs"] is not None else None}

    dl_cf, pairs = None, {}
    if run["result"]["jobs"] is not None:
        spec = _model(run["result"]["run_dir"])
        dl_cf = strip_dl(next(q for q in spec["ports"] if q["name"] == "L1"), [spec["mesh"][a] for a in "xyz"])
        uncomp = f"{(port_value('L1', L_COUPON) + dl_cf) * 1e9:.6f}nH"  # verify's grid then holds L_COUPON
        for name, value in (("uncomp", uncomp), ("comp", L_COUPON)):
            pairs[name] = p0.step(out, f"a10-{name}", f"{key}|{run['result']['run_dir']}", partial(verify, value))
    verdicts = [job["verdict"] for rec in (run, *pairs.values()) for job in rec["result"]["jobs"] or []]
    dl_fit = ds21_uncomp = ds21_comp = None
    if verdicts == ["converged"] * 7:
        project = load_project(pj)
        results = project.get("results", {})
        if not p0.holds(results, run):
            raise SystemExit(f"p0b2: {pj} holds another run than a10-run's; delete {out / 'steps' / 'a10-run.json'} "
                             "to run the coupon again")
        lay = layout(project, results)
        measured = {name: layout(project, rec["result"]["verify"]).s for name, rec in pairs.items()}
        grid_l = {name: next(g["L"] for g in _model(rec["result"]["run_dir"])["grid"] if g["name"] == "L1")
                  for name, rec in pairs.items()}
        dl_fit = {name: fit_dl(lay.s, lay.f, results["c_box"], {"L1": grid_l[name]}, "L1", measured[name])
                  for name in pairs}
        # report only: after a10-comp's retune the project holds L1 at L_COUPON, so this is verify's own closure
        ds21_uncomp = compare(measured["uncomp"], p0.closed_chain(pj, ideal=True)[1], lay.f, lay.markers[0],
                              FLOOR)["ds21_db_f0"]
        ds21_comp = pairs["comp"]["result"]["verify"]["compare"]["ds21_db_f0"]
    result = {"dl_cf_h": dl_cf, "band_h": list(DL_BAND), "dl_fit_h": dl_fit, "ds21_uncomp_db": ds21_uncomp,
              "ds21_comp_db": ds21_comp, "verdicts": verdicts,
              **a10(verdicts, dl_fit["uncomp"] if dl_fit else None, ds21_comp)}
    p0.save(out / "p0b2" / "a10.json", {**result, "versions": p0.versions()})
    return result


def main(argv: list[str] | None = None) -> int:
    """python tools/p0b2.py coupon --out DIR: the coupon check in the P0 folder DIR, entered first (D-7); prints the
    saved a10.json and returns 0."""
    parser = argparse.ArgumentParser(prog="p0b2", description="Plan 7's gate tool (design 2026-10-26 5.2).")
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("coupon", help="A-10's single-L coupon check (E-7)")
    cmd.add_argument("--out", required=True, type=Path, metavar="DIR", help="the P0 folder, outside every work tree")
    a = parser.parse_args(argv)
    coupon(a.out)
    print((a.out / "p0b2" / "a10.json").read_text(encoding="utf-8"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
