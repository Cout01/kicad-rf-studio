# SPDX-License-Identifier: GPL-3.0-or-later
"""Build tests/fixtures/dumps: openEMS's PEC_dump.vtp and operator_dump.vtr of a small microstrip, for the readers'
tests.

Dev-time only: it runs in the dev venv with openEMS and CSXCAD installed (setup-openems), and the product never imports
it. Regenerate from the repository root with

    python tools/make_dumps.py

The model, in mm: a 16 × 8 mm FR4 board 0.5 mm thick on a PEC ground at z = 0, a 1 mm wide PEC strip 35 µm thick
from x = -5 to 5, and a 50 Ω lumped port from the ground to the strip at each end, port 1 excited by the pulse of the
915 MHz project below. openEMS only sets up (no time steps); the excitation files et and ht it writes are deleted.
"""
import os
from pathlib import Path

import numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS

from kicad_rf_studio.core.model.spec import excitation, kappa

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "dumps"
PROJECT = {"f0_hz": 915e6, "harmonics": 3, "band_factor": 1.1, "t_max_s": 40e-9}


def main() -> None:
    pulse = excitation(PROJECT)
    fdtd = openEMS(EndCriteria=1e-15)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    grid = csx.GetGrid()
    grid.SetDeltaUnit(1e-3)
    grid.SetLines("x", np.arange(-8, 8.001, 0.25))
    grid.SetLines("y", np.arange(-4, 4.001, 0.25))
    grid.SetLines("z", [-1, -0.5, 0, 0.125, 0.25, 0.375, 0.5, 0.535, 0.6, 0.75, 1, 1.5, 2, 2.5, 3, 3.5])
    csx.AddMaterial("FR4", epsilon=4.3, kappa=kappa(4.3, 0.02, 915e6)).AddBox([-8, -4, 0], [8, 4, 0.5], priority=0)
    pec = csx.AddMetal("PEC")
    pec.AddBox([-8, -4, 0], [8, 4, 0], priority=10)
    pec.AddBox([-5, -0.5, 0.5], [5, 0.5, 0.535], priority=10)
    fdtd.AddLumpedPort(1, 50, [-5, -0.5, 0], [-5, 0.5, 0.5], "z", excite=1)
    fdtd.AddLumpedPort(2, 50, [5, -0.5, 0], [5, 0.5, 0.5], "z", excite=0)
    fdtd.SetBoundaryCond(["MUR"] * 6)
    fdtd.SetCustomExcite(pulse["expr"], pulse["f2"], pulse["f2"])
    fdtd.SetMaxTime(5e-9)
    OUT.mkdir(exist_ok=True)
    os.chdir(OUT)
    fdtd.Run(".", setup_only=True, numThreads=1, debug_PEC=True, debug_operator=True)
    for name in ("et", "ht"):
        Path(name).unlink()


if __name__ == "__main__":
    main()
