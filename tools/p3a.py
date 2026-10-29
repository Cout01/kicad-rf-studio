# SPDX-License-Identifier: GPL-3.0-or-later
"""P3-A, the far-field sanity gate (Stage 3 design 5.11). Part 1, the dipoles. Dev-time only, like p0."""
import numpy as np

from kicad_rf_studio.core.geometry.region import C0
from kicad_rf_studio.core.mesh.smooth import smooth_mesh_lines
from kicad_rf_studio.core.model.spec import pulse, with_pml

F0, F_LO, F_HI = 2.45e9, 2.40e9, 2.50e9  # the dipoles' band, f0 its centre
F1, F2 = 1.85e9, 3.0e9  # the pulse: f_lo/1.3 and 1.2·f_hi, rounded (design 5.4)
F_HZ = [F0, F_LO, F_HI]  # the far-field frequencies, f0 first (design 5.5)
T_MAX = 30e-9  # 2·t0 + 60/f0 = 29.5 ns, rounded up (design 5.4)
GAP_MM = C0 / F_LO * 1e3 / 4  # the air gap: λ/4 at f_lo (design 5.2)
CMAX_MM = C0 / F2 * 1e3 / 20  # the air's largest cell, λ(f2)/20
CELL_MM, FEED_MM = 0.5, 1.0  # the wire's cell and the port's gap (r1's probes)
SHORT_MM, HALF_MM = 12.0, 58.0  # λ/10 at f0 (λ/20 read η_rad 0.971 in the architect's probe); r1's half-wave wire


def dipole(length_mm: float, *, f_hz: list[float] = F_HZ, boundary: str | None = "pml_8",
           box: list[list[float]] | None = None) -> dict:
    """A z-directed PEC wire dipole `length_mm` long, centred on the origin, in vacuum, as a model spec (design 5.11).
    Its arms are two curves on the x = y = 0 lines, and a 50 Ω lumped port P1 spans the FEED_MM gap, with witnesses one
    CELL_MM into each arm. The pulse runs over F1–F2 to T_MAX. Mesh lines fall every CELL_MM out to 1 mm past the wire's
    ends and to ±1 mm in x and y, then GAP_MM of air graded at 1.3 up to CMAX_MM, then with_pml. `boundary` is "pml_8"
    (None: MUR). The far field is recorded at `f_hz` about the origin, in `box` when given."""
    half, gap = length_mm / 2, FEED_MM / 2
    fine = {"x": [-1.0, -0.5, 0.0, 0.5, 1.0], "y": [-1.0, -0.5, 0.0, 0.5, 1.0],
            "z": np.arange(-half - 1.0, half + 1.0 + 1e-9, CELL_MM).tolist()}
    ends = {"x": (0.0, 0.0), "y": (0.0, 0.0), "z": (-half, half)}
    mesh = {a: with_pml([round(float(v), 6) for v in smooth_mesh_lines(
        np.array([*fine[a], ends[a][0] - GAP_MM, ends[a][1] + GAP_MM]), CMAX_MM, 1.3)]) for a in "xyz"}
    start, stop = [0.0, 0.0, -gap], [0.0, 0.0, gap]
    spec = {"mesh": mesh, "excitation": pulse(F1, F2, T_MAX), "materials": [],
            "metal": {"copper": [], "lid": {"plate": None, "walls": []}, "cylinders": [],
                      "curves": [{"at": [0.0, 0.0], "z": [gap, half]}, {"at": [0.0, 0.0], "z": [-half, -gap]}]},
            "ports": [{"name": "P1", "kind": "lumped", "dir": "z", "start": start, "stop": stop, "part": False,
                       "nodes": [start, stop, [0.0, 0.0, -gap - CELL_MM], [0.0, 0.0, gap + CELL_MM]]}],
            "grid": [], "nf2ff": {"f_hz": list(f_hz), "center": [0.0, 0.0, 0.0], **({"box": box} if box else {})}}
    return {**spec, "boundary": boundary} if boundary else spec
