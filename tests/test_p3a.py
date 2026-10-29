# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest

import p3a
from kicad_rf_studio.core.model.csx import PML_CELLS


@pytest.mark.parametrize("length", [p3a.SHORT_MM, p3a.HALF_MM])
def test_p3as_dipoles_are_wires_on_the_mesh_in_vacuum_under_pml_8(length):  # design 5.2, 5.11
    s, half, gap = p3a.dipole(length), length / 2, p3a.FEED_MM / 2
    assert (s["boundary"], s["materials"], s["grid"], s["metal"]["copper"]) == ("pml_8", [], [], [])
    assert s["metal"]["curves"] == [{"at": [0.0, 0.0], "z": [gap, half]}, {"at": [0.0, 0.0], "z": [-half, -gap]}]
    (port,) = s["ports"]
    assert (port["kind"], port["dir"], port["start"], port["stop"], port["part"]) == (
        "lumped", "z", [0.0, 0.0, -gap], [0.0, 0.0, gap], False)
    assert s["nf2ff"] == {"f_hz": [2.45e9, 2.4e9, 2.5e9], "center": [0.0, 0.0, 0.0]}
    assert (s["excitation"]["f1"], s["excitation"]["f2"], s["excitation"]["t_max"]) == (1.85e9, 3.0e9, 30e-9)
    for axis in "xyz":
        steps = np.diff(s["mesh"][axis])
        assert np.allclose(steps[:PML_CELLS], steps[0]) and np.allclose(steps[-PML_CELLS:], steps[-1])
        assert steps.max() <= p3a.CMAX_MM and steps.min() == pytest.approx(p3a.CELL_MM)
    z = s["mesh"]["z"]
    assert z[PML_CELLS] == round(-half - p3a.GAP_MM, 6) and {-half, -gap, gap, half} <= set(z)
    assert 0.0 in s["mesh"]["x"] and 0.0 in s["mesh"]["y"]


def test_a_dipole_drops_the_pml_or_places_its_box_on_the_same_mesh():  # P3-A's MUR twin and moved box
    box = [[-9.0, -9.0, -40.0], [9.0, 9.0, 40.0]]
    mur = p3a.dipole(p3a.HALF_MM, boundary=None, box=box)
    assert "boundary" not in mur and mur["nf2ff"]["box"] == box and mur["mesh"] == p3a.dipole(p3a.HALF_MM)["mesh"]
