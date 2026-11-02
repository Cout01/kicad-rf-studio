# SPDX-License-Identifier: GPL-3.0-or-later
"""The antenna golden pins (Stage 4 design 3, 4, 5.12 item 1): sha256 digests of what the antenna fixtures build and
write, and of v1's 2D readouts, which golden_v1 does not pin, recorded once at 037bc4b, before Stage 4 changed any
code, in tests/fixtures/golden_antenna.json, with golden_v1.env(). tests/test_golden_antenna.py compares the models
everywhere and the outputs where env() matches. Dev-time only: run it once with `python tools/golden_antenna.py`,
which records in English through golden_v1.record. It refuses to overwrite the JSON; a new recording is a controller
ruling, which deletes the file first."""
import os

if __name__ == "__main__":
    os.environ["LANGUAGE"] = "en"  # the suite's language, set before core.messages binds one: the PNGs' labels

import json
import shutil
import sys
from pathlib import Path
from unittest import mock

import numpy as np

import golden_v1
import p0
from golden_v1 import sha
from kicad_rf_studio import cli, pipeline, runs
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.model.spec import far_field_box, spec_hash, verify_spec
from kicad_rf_studio.core.project import GATES, parts

sys.path.append(str(p0.ROOT / "tests"))  # networks: the known N-port the KRS_FAKE=network fake replays
from networks import star, synth_records  # noqa: E402

GOLDEN = p0.FIX / "golden_antenna.json"
WIFI, ISM = (2.4e9, 2.4835e9), (902e6, 928e6)
BANDS = {"ifa2g4": WIFI, "ifa2g4_pi": WIFI, "ifa2g4_pi_shift": WIFI, "ifa2g4_pi_dxp": WIFI, "ifa2g4_pi_dxm": WIFI,
         "ifa2g4_pi_pour": WIFI, "meander915": ISM}  # every antenna fixture, new_antenna from U1.1 to AE1, defaults
TRACED = ("ifa2g4", "ifa2g4_pi")  # the cases whose outputs the committed fixtures let the suite write


def _board(name: str) -> str:
    """The fixture `name`'s board, copied into the working folder with LF line ends, as git stores it."""
    Path(f"{name}.kicad_pcb").write_bytes((p0.FIX / f"{name}.kicad_pcb").read_bytes().replace(b"\r\n", b"\n"))
    return f"{name}.kicad_pcb"


def _readout(geom) -> str:
    return sha(json.dumps(pipeline.readout_2d(geom), sort_keys=True).encode())


def digests() -> dict:
    """{"models": {case: {"spec_hash", "model_json", "project", "notes", "blocked"}, the pi's with "verify"},
    "outputs": {case: {"readout"}, TRACED's with each results/ file and "lines", and each of golden_v1.CASES with its
    "readout"}}, each board copied into the working folder (_board) and built there by new_antenna, or by new at
    golden_v1's settings. The pi's verify model is golden_v1's lpf915 recipe with its far-field box. ifa2g4's run is
    the far-field fixture's 58 mm dipole job (M = 0); the pi's 4 jobs are synth_records' star(f, 4) to 10 ns under its
    pulse, every part port at C_box 2e-14 F."""
    models, outputs = {}, {}
    for name, band in BANDS.items():
        pj, notes = cli.new_antenna(_board(name), "U1.1", "AE1", band, output=Path(name))
        project, board, geom, _ = pipeline.load(pj)
        model = pipeline.build_model(project, board, geom)
        spec = model.spec
        models[name] = {"spec_hash": spec_hash(spec), "model_json": sha(json.dumps(spec).encode()),
                        "project": sha(pj.read_bytes()),
                        "notes": sha(json.dumps(notes[:-1], sort_keys=True, default=str).encode()),
                        "blocked": sha(json.dumps(model.blocked, sort_keys=True, default=str).encode())}
        outputs[name] = {"readout": _readout(geom)}
        if name == "ifa2g4_pi":
            dump = Path(name) / "operator_dump.vtr"
            dump.write_bytes(b"")
            with mock.patch.object(spec_module, "c_box", lambda *_: 2e-14):
                vspec = verify_spec(spec, parts(project), dump, 1e-13, far_field=far_field_box(project, board, geom))
            models[name]["verify"] = {"spec_hash": spec_hash(vspec), "model_json": sha(json.dumps(vspec).encode())}
        if name not in TRACED:
            continue
        run_dir, jobs, far = Path(name) / "run", [], None
        runs.write_spec(run_dir, spec)
        n, exc = len(spec["ports"]), spec["excitation"]
        if n == 1:  # no part port: the far-field fixture's job, waves and transforms
            (run_dir / "job-1").mkdir()
            for file in ("waves.npz", "sphere.h5", "elevation.h5", "azimuth.h5"):
                shutil.copyfile(p0.FIX / "farfield" / file, run_dir / "job-1" / file)
            far = {grid: f"job-1/{grid}.h5" for grid in ("sphere", "elevation", "azimuth")}
            jobs.append({"port": "P1", "verdict": "converged", "t_cut": None, "t_stop": 1e-8, "residual_db": -60.0,
                         "waves": "job-1/waves.npz"})
        else:
            for k, (t_u, u, t_i, i) in enumerate(synth_records(lambda f: star(f, n), n, exc["f1"], exc["f2"], 1e-13,
                                                               10e-9), 1):
                (run_dir / f"job-{k}").mkdir()
                np.savez(run_dir / f"job-{k}" / "waves.npz", t_u=t_u, u=u, t_i=t_i, i=i)
                jobs.append({"port": spec["ports"][k - 1]["name"], "verdict": "converged", "t_cut": None,
                             "t_stop": float(t_u[-1]), "residual_db": -60.0, "waves": f"job-{k}/waves.npz"})
        results = {"run_dir": str(run_dir), "preset": "normal", "gates": GATES, "jobs": jobs,
                   "loss_expected": pipeline.expected_loss(geom, project["f0_hz"]),
                   "c_box": {q["name"]: 2e-14 for q in spec["ports"] if q["part"]}, "far_field": far}
        lines = pipeline.write_outputs(pj, {**project, "results": results}, "c")
        outputs[name] |= {**{f.name: sha(f.read_bytes()) for f in sorted((pj.parent / "results").iterdir())},
                          "lines": sha(json.dumps(lines, sort_keys=True, default=str).encode())}
    for name, (start, end, lid) in golden_v1.CASES.items():  # v1's 2D readouts, which golden_v1 does not pin
        pj, _ = cli.new(_board(name), start, end, 915e6, lid_height=lid, output=Path(name))
        outputs[name] = {"readout": _readout(pipeline.load(pj)[2])}
    return {"models": models, "outputs": outputs}


def main() -> int:
    """Records digests() in GOLDEN through golden_v1.record; 1 when GOLDEN exists."""
    return golden_v1.record(GOLDEN, digests)


if __name__ == "__main__":
    sys.exit(main())
