# SPDX-License-Identifier: GPL-3.0-or-later
"""The v1 golden pins (Stage 3 design 3, 4, 5.12 item 1): sha256 digests of what v1 builds and writes from the
committed fixtures, recorded once, before Stage 3 changed any code, in tests/fixtures/golden_v1.json, with env(), what
the output bytes depend on besides the code. tests/test_golden_v1.py compares the models everywhere and the outputs
where env() matches. Every path is relative to the working folder.

Dev-time only: run it once with `python tools/golden_v1.py`, which records in English, the suite's language. It refuses
to overwrite the JSON; a new recording is a controller ruling, which deletes the file first."""
import os

if __name__ == "__main__":
    # the suite's language (tests/conftest.py), set before core.messages binds one at import: summary.png's labels are
    # drawn in it
    os.environ["LANGUAGE"] = "en"

import hashlib
import json
import platform
import sys
import tempfile
from pathlib import Path
from unittest import mock

import matplotlib
import numpy as np
import scipy
import skrf

import p0
from kicad_rf_studio import cli, pipeline, runs
from kicad_rf_studio.core import messages
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.model.spec import spec_hash, verify_spec
from kicad_rf_studio.core.project import GATES, load_project, parts, save_project

GOLDEN = p0.FIX / "golden_v1.json"
CASES = {"lpf915": ("U1.1", "J1.1", 2.5), "lpf915-45": ("U1.1", "J1.1", 2.5),
         "coupon_gcpw_pads": ("TP1.1", "TP2.1", None)}  # new's start, end and lid height, at f0 915 MHz
TRACED = ("lpf915", "coupon_gcpw_pads")  # the cases whose every job tests/fixtures/traces holds


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def env() -> list:
    """What the output bytes depend on besides the code, with no host name: the platform, the CPU, the numpy, scipy,
    matplotlib and scikit-rf versions, and the catalog's language."""
    # ponytail: the output bytes carry scikit-rf's and matplotlib's versions, summary.png's language and this CPU's
    # BLAS bits; on any other env() only the model digests are compared
    return [sys.platform, platform.processor(), np.__version__, scipy.__version__, matplotlib.__version__,
            skrf.__version__, messages.language()]


def digests() -> dict:
    """{"models": {case: {"spec_hash", "model_json", "project", "notes"}, lpf915's with "verify", "calibration":
    {"spec_hash", "model_json"}}, "outputs": {case of TRACED: {each results/ file: its sha256, "lines"}}}. Each case's
    board is copied into the working folder with LF line ends, as git stores it, and built there by `new` at v1's
    defaults (lpf915-45 with allow_curve_port, else E_ROTATED_PART), so project.json's relative board path, its board
    hash and new's lines are the same on every machine. The model spec is pinned by its hash and by model.json's bytes
    as runs.write_spec writes them, project.json by its bytes, and new's lines without I_WROTE. verify's model of
    lpf915 (verify refuses lpf915-45, E_VERIFY_CURVE, and the coupon, E_VERIFY_NO_PARTS) is verify_spec's at the fake's
    dt, 1e-13 s, with the dump's reader stood in for as tests/fake_cli.py does: 2e-14 F a cell. A traced case's
    <case>/run holds its model.json and its jobs' waves from the traces: every job converged at its trace's cut, C_box
    2e-14 F per part port, the expected loss of its geometry."""
    models, outputs = {}, {}
    for name, (start, end, lid) in CASES.items():
        # the bytes git stores: project.json holds the board's sha256, which a CRLF checkout (core.autocrlf) moves
        Path(f"{name}.kicad_pcb").write_bytes((p0.FIX / f"{name}.kicad_pcb").read_bytes().replace(b"\r\n", b"\n"))
        pj, notes = cli.new(f"{name}.kicad_pcb", start, end, 915e6, lid_height=lid, output=Path(name))
        if name == "lpf915-45":
            save_project(pj, {**load_project(pj), "allow_curve_port": True})
        project, board, geom, _ = pipeline.load(pj)
        spec = pipeline.build_model(project, board, geom).spec
        models[name] = {"spec_hash": spec_hash(spec), "model_json": sha(json.dumps(spec).encode()),
                        "project": sha(pj.read_bytes()),
                        "notes": sha(json.dumps(notes[:-1], sort_keys=True, default=str).encode())}
        if name == "lpf915":
            dump = Path(name) / "operator_dump.vtr"
            dump.write_bytes(b"")
            with mock.patch.object(spec_module, "c_box", lambda *_: 2e-14):
                vspec = verify_spec(spec, parts(project), dump, 1e-13)
            models[name]["verify"] = {"spec_hash": spec_hash(vspec), "model_json": sha(json.dumps(vspec).encode())}
        if name not in TRACED:
            continue
        run_dir, jobs = Path(name) / "run", []
        runs.write_spec(run_dir, spec)
        for k, port in enumerate(spec["ports"], 1):
            rec, _, _, t_cut = p0.load_trace(p0.FIX / "traces" / f"{name}-k{k}.npz")
            (run_dir / f"job-{k}").mkdir()
            np.savez(run_dir / f"job-{k}" / "waves.npz", t_u=rec.t_u, u=rec.u, t_i=rec.t_i, i=rec.i)
            jobs.append({"port": port["name"], "verdict": "converged", "t_cut": t_cut, "t_stop": float(rec.t_u[-1]),
                         "residual_db": -60.0, "waves": f"job-{k}/waves.npz"})
        results = {"run_dir": str(run_dir), "preset": "normal", "gates": GATES, "jobs": jobs,
                   "loss_expected": pipeline.expected_loss(geom, 915e6),
                   "c_box": {q["name"]: 2e-14 for q in spec["ports"] if q["part"]}}
        lines = pipeline.write_outputs(pj, {**project, "results": results}, "c")
        outputs[name] = {**{f.name: sha(f.read_bytes()) for f in sorted((pj.parent / "results").iterdir())},
                         "lines": sha(json.dumps(lines, sort_keys=True, default=str).encode())}
    calibration = runs.calibration_spec()
    models["calibration"] = {"spec_hash": spec_hash(calibration), "model_json": sha(json.dumps(calibration).encode())}
    return {"models": models, "outputs": outputs}


def main() -> int:
    """Records digests(), run in a fresh temporary folder, in GOLDEN with the product tree's id (p0.code_id) and env(),
    and returns 0; refuses with 1 when GOLDEN exists."""
    if GOLDEN.exists():
        print(f"golden_v1: {GOLDEN.name} exists; a new recording is a controller ruling, which deletes it first",
              file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as folder:
        here = os.getcwd()
        os.chdir(folder)
        try:
            pins = digests()
        finally:
            os.chdir(here)  # out of the folder first: Windows cannot remove a working folder
    GOLDEN.write_text(json.dumps({"code": p0.code_id(), "env": env(), **pins}, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
