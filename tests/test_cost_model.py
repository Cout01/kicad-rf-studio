# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest

from kicad_rf_studio.core.mesh import Mesh
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.project import GATES
from kicad_rf_studio.pipeline import Model, cost_notes, driver, duration, port_gates, smallest_cell


def test_cost_notes_follow_the_cost_model():  # spec 6.4
    lines = np.linspace(0.0, 9.0, 10)
    m = Model(Mesh(lines, lines, lines, 1.0, 0.4, {}, {}), {"ports": [{"part": False}, {"part": False},
              {"part": True}]}, [], 1.5e-12)
    p = {"t_max_s": 1e-9, "gates": GATES, "mesh": {"n": 2}}
    notes = cost_notes(m, p, {"dt": 1e-12, "node": [0, 1, 2, 3]}, 4, 2, 1.0)
    assert notes == [
        ("I_COST_CELLS", {"nx": 10, "ny": 10, "nz": 10, "mcells": "0.00", "n": 2, "d_mm": "1.0000"}),
        ("I_COST_SMALLEST", {"size_um": "1000.0", "axis": "x", "at_mm": "0.500"}),
        ("I_COST_DT", {"dt": "1.0000e-12", "floor": "0.8", "ref": "1.5000e-12", "axis": "x", "x": "1.000",
                       "y": "-2.000", "z": "3.000"}),
        ("I_COST_TIME", {"time": "2 s", "runs": 3, "t_max_ns": "1", "pool": 2, "threads": 4}),
        ("I_COST_RAM", {"gb": "0.1", "pool": 2}),
        ("I_COST_DRIVER_RUNS", {"runs": 3, "parts": 1})]
    def predicted(model_hash, *jobs):
        results = {"model_hash": model_hash, "jobs": [{"verdict": v, "t_stop": t} for v, t in jobs]}
        notes = cost_notes(m, {**p, "results": results}, {"dt": 1e-12, "node": [0, 1, 2, 3]}, 4, 2, 1.0)
        return [q for c, q in notes if c == "I_COST_PREDICTED"]

    kept = (("converged", 5e-10), ("t_max", None), ("flat", 2e-10))
    assert predicted(spec_hash(m.spec), *kept) == [{"time": "1 s"}]
    # final review M3: a stopped job's stop time (5 ns, 10 s) and another model's run predict nothing
    assert predicted(spec_hash(m.spec), *kept, ("stopped", 5e-9), ("unclassified", 5e-9)) == [{"time": "1 s"}]
    assert predicted("another model", *kept) == predicted(spec_hash(m.spec), ("t_max", None)) == []
    assert (duration(5307.2), duration(840), duration(45.4)) == ("1 h 28 min", "14 min", "45 s")


@pytest.mark.parametrize(("roots", "notes"), [
    ([[1, 2, 1, 2]], []), ([[1, 1, 1, 1]], [("E_PORT_SHORT", {"name": "P1"})]),
    ([[1, 2, 3, 2]], [("E_PORT_OPEN", {"name": "P1", "end": "reference"})]),
    ([[1, -1, 1, 2]], [("E_PORT_OPEN", {"name": "P1", "end": "signal"})]),
    ([[4, 9]], []), ([[4, 4]], [("E_PORT_SHORT", {"name": "P1"})]),  # a CurvePort has no caps
    ([[-1, 9]], [("E_PORT_OPEN", {"name": "P1", "end": "reference"})])])
def test_port_gates(roots, notes):  # C-15
    assert port_gates([{"name": "P1"}], roots) == notes


# --- beyond the brief's tests: the branches and edge cases they leave open ------------------------------------------


def test_the_driver_names_a_cell_under_d_over_3_else_the_runs_else_the_cell_count():  # C-36
    x = np.array([0.0, 1.0, 2.0])
    y = np.array([-3.0, -2.0, -1.9, -1.0, -0.9])  # two 0.1 mm cells, the second 1e-16 smaller: the first wins
    z = np.array([0.0, 1.3, 1.4])  # a 0.1 mm cell 1e-16 smaller still, but z comes after y
    mesh = Mesh(x, y, z, 1.0, 0.4, {}, {})
    assert smallest_cell(mesh) == (pytest.approx(0.1), "y", pytest.approx(1.95))  # KiCad's frame: y down
    assert driver(mesh, 2, 0) == ("I_COST_DRIVER_CELL", {"size_um": "100.0", "axis": "y", "at_mm": "1.950"})
    third = Mesh(x, x, np.array([0.0, 0.033333, 0.1]), 0.1, 0.05, {}, {})  # d/3 on the 1e-6 mm grid is not under it
    assert driver(third, 3, 1) == ("I_COST_DRIVER_RUNS", {"runs": 3, "parts": 1})
    assert driver(third, 2, 1) == ("I_COST_DRIVER_CELLS", {"d_mm": "0.1000"})


def test_two_open_ends_are_no_short():  # pec_roots gives -1 for every node no PEC edge touches
    assert port_gates([{"name": "P1"}, {"name": "P2"}], [[-1, -1, -1, -1], [-1, -1]]) == [
        ("E_PORT_OPEN", {"name": "P1", "end": "reference"}), ("E_PORT_OPEN", {"name": "P1", "end": "signal"}),
        ("E_PORT_OPEN", {"name": "P2", "end": "reference"}), ("E_PORT_OPEN", {"name": "P2", "end": "signal"})]
