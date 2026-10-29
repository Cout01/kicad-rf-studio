# SPDX-License-Identifier: GPL-3.0-or-later
"""Build tests/fixtures/farfield: the far field of a real run of tools/p3a.py's 58 mm dipole, recorded at 2.45 and
2.40 GHz. The run goes through the product's job phase (p0.run_model at Normal; its stop rule ends it with ABORT) and
its transform (pipeline.far_field). The reader's tests use the fixture without openEMS. Dev-time only: it imports
openEMS, so it runs with CSXCAD_INSTALL_PATH set, and the product never imports it. Run:
python tools/make_farfield.py --out DIR, where DIR is a P0 folder outside every repository."""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np

import p0
import p3a
from kicad_rf_studio import pipeline

FAR = p0.FIX / "farfield"


def main(argv: list[str] | None = None) -> int:
    """Runs the 58 mm dipole in the P0 folder --out and writes FAR; 0 when done."""
    from openEMS.nf2ff import nf2ff_results  # here only: the product never imports openEMS
    from openEMS.utilities import DFT_time2freq

    parser = argparse.ArgumentParser(prog="make_farfield")
    parser.add_argument("--out", required=True, help="a P0 folder outside every repository")
    p0.enter(Path(parser.parse_args(argv).out))
    spec = p3a.dipole(p3a.HALF_MM, f_hz=[2.45e9, 2.4e9])
    run = p0.run_model(p0.model_of(spec), "normal", "farfield", [1])
    job = p0.run_path(run["run_dir"]) / run["jobs"][0]["job"]
    far = pipeline.far_field(job)
    FAR.mkdir(exist_ok=True)
    for grid, path in far.items():
        shutil.copyfile(path, FAR / f"{grid}.h5")
    shutil.copyfile(job / "waves.npz", FAR / "waves.npz")
    f = np.array(spec["nf2ff"]["f_hz"])  # the spec's float64 frequencies; the files store them as float32
    with np.load(job / "waves.npz") as w:
        u, i = DFT_time2freq(w["t_u"], w["u"][0], f), DFT_time2freq(w["t_i"], w["i"][0], f)
    u_inc, i_inc = (u + 50 * i) / 2, (i + u / 50) / 2  # ports.Port.CalcPort's, at its 50 Ω
    ref = {"f_hz": f.tolist(), "verdict": run["jobs"][0]["verdict"], "aborted": (job / "ABORT").is_file(),
           "blocked": [code for code, _ in run["blocked"]], "p_acc": (0.5 * np.real(u * np.conj(i))).tolist(),
           "p_inc": (0.5 * np.real(u_inc * np.conj(i_inc))).tolist()}
    for grid in far:
        res = nf2ff_results(str(FAR / f"{grid}.h5"))
        ref[grid] = {"d_max": np.asarray(res.Dmax).tolist(), "p_rad": np.asarray(res.Prad).tolist()}
    (FAR / "reference.json").write_text(json.dumps(ref, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
