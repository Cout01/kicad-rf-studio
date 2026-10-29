# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import numpy as np
import pytest

import p0
import p3a
from kicad_rf_studio.core.model.csx import PML_CELLS
from kicad_rf_studio.core.post.farfield import read_far_field


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


def run(d, eta=1.0, verdict="converged", dumps=True, aborted=True, blocked=()):
    return {"verdict": verdict, "aborted": aborted, "dumps": dumps, "blocked": list(blocked), "d_dbi": d,
            "eta_rad": eta}


def free(growth=0.0, finite=True, t_stop=90e-9):
    return {"finite": finite, "growth_db": growth, "t_max": 90e-9, "t_stop": t_stop}


M = {"short": run(1.79), "half": run(2.16), "box2": run(2.14), "short_3x": free(), "half_3x": free(3.0),
     "pml": {"weight": 3.1}, "speed": {"ratio": 0.3}}  # near what the plan-mesh probes predict


def test_the_p3a_rules():  # design 5.11's P3-A row and 5.9's decisions, pre-registered
    d = p3a.decide(M)
    assert d["verdict"] == {"value": "pass", "fails": []}
    assert d["pml_weight"] == {"value": 3.1, "correction": True}
    assert d["small_speed"] == {"ratio": 0.3, "correction": True}
    calm = p3a.decide({**M, "pml": {"weight": 1.2}, "speed": {"ratio": 0.7}})
    assert not calm["pml_weight"]["correction"] and not calm["small_speed"]["correction"]
    for change, fails in [({"short": run(1.87)}, ["short_d"]), ({"half": run(1.99), "box2": run(2.0)}, ["half_d"]),
                          ({"half": run(2.16, eta=1.021)}, ["eta"]), ({"short": run(1.79, eta=0.979)}, ["eta"]),
                          ({"box2": run(2.22)}, ["box"]), ({"half_3x": free(6.5)}, ["growth"]),
                          ({"short_3x": free(finite=False)}, ["growth"]),
                          ({"half_3x": free(t_stop=20e-9)}, ["growth"]),
                          ({"box2": run(2.14, verdict="t_max")}, ["dumps_after_abort"]),
                          ({"half": run(2.16, aborted=False)}, ["dumps_after_abort"]),
                          ({"short": run(1.79, blocked=["E_METAL_IN_PML"])}, ["setup"]),
                          ({"short": run(None, eta=None, dumps=False)}, ["short_d", "eta", "dumps_after_abort"])]:
        assert p3a.decide({**M, **change})["verdict"] == {"value": "fail", "fails": fails}


def test_the_moved_box_sits_its_cells_inside_openems_own_placement():  # design 5.11: the box moved 2 cells
    s, k = p3a.dipole(p3a.HALF_MM), PML_CELLS + 1  # openEMS's placement under PML_8: line 9 (probed)
    assert p3a.inset_box(s, 0) == [[s["mesh"][a][k] for a in "xyz"], [s["mesh"][a][-1 - k] for a in "xyz"]]
    assert p3a.inset_box(s, 2) == [[s["mesh"][a][k + 2] for a in "xyz"], [s["mesh"][a][-3 - k] for a in "xyz"]]


def test_the_p3a_steps_run_through_the_harness_and_the_product(p0_out, monkeypatch):  # P0's harness, the fake worker
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    assert p3a.main(["--out", str(p0_out)]) == 0
    result = json.loads((p0_out / "p3a" / "p3a.json").read_text(encoding="utf-8"))
    sphere = read_far_field(p0.FIX / "farfield" / "sphere.h5")  # the fake's transform copies it
    assert result["half"]["d_dbi"] == pytest.approx(10 * math.log10(sphere.d_max[0]))
    assert (result["half"]["verdict"], result["half"]["aborted"], result["half"]["dumps"]) == ("converged", True, True)
    mur, again = p0.records(p0_out, ["p3a-half-mur", "p3a-half-3x"])
    assert mur["result"]["t_max"] == again["result"]["t_max"] == pytest.approx(3 * p3a.T_MAX)  # 3 × T_max, both twins
    assert (result["half_3x"]["finite"], result["half_3x"]["growth_db"]) == (True, 0.0)
    assert result["half_3x"]["run_dir"].startswith("p3a-half-3x-")  # a folder's name, never a path (privacy gate)
    d = result["decisions"]
    assert d["pml_weight"] == {"value": 1.0, "correction": False}  # the fake runs every job at 100 MC/s
    assert d["small_speed"] == {"ratio": 0.5, "correction": True}  # against the calibration's 400 MC/s / 2 jobs
    # every far field is the 58 mm fixture's, and the fake's dt (1e-13 s) trips E_DT_FLOOR on 0.5 mm cells
    assert d["verdict"] == {"value": "fail", "fails": ["short_d", "eta", "setup"]}
    assert (p0_out / "p3a" / "p3a.md").read_text(encoding="utf-8").startswith("## P3A-1")
