# SPDX-License-Identifier: GPL-3.0-or-later
import sys
import types

from kicad_rf_studio.core.model.csx import METAL_PRIORITY, build_csx
from kicad_rf_studio.core.model.spec import excitation


class Rec:
    """Stands in for CSXCAD and openEMS: every call is logged as (name, args, kwargs); Run returns 0 (setup OK),
    any other call another Rec."""

    def __init__(self, log, name=""):
        self.log, self.name = log, name

    def __getattr__(self, name):
        return Rec(self.log, name)

    def __call__(self, *args, **kw):
        self.log.append((self.name, args, kw))
        return 0 if self.name == "Run" else Rec(self.log, self.name)


def fake_openems(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "CSXCAD", types.SimpleNamespace(ContinuousStructure=Rec(calls, "ContinuousStructure")))
    monkeypatch.setitem(sys.modules, "openEMS", types.SimpleNamespace(openEMS=Rec(calls, "openEMS")))
    return calls


SQUARE = {"x": [0.0, 4.0, 4.0, 0.0], "y": [0.0, 0.0, 4.0, 4.0]}
TINY = {  # a 5 × 5 × 5-line model: a substrate slab, a copper block, one port
    "mesh": {"x": [0.0, 1.0, 2.0, 3.0, 4.0], "y": [0.0, 1.0, 2.0, 3.0, 4.0], "z": [0.0, 1.0, 2.0, 3.0, 4.0]},
    "excitation": excitation({"f0_hz": 1e9, "harmonics": 1, "band_factor": 1.1, "t_max_s": 1e-9}),
    "materials": [{"name": "substrate_0", "eps": 4.5, "kappa": 0.0046, "priority": 10,
                   "solids": [{**SQUARE, "z": [0.0, 1.0]}]}],
    "metal": {"copper": [{"x": [1.0, 3.0, 3.0, 1.0], "y": [1.0, 1.0, 3.0, 3.0], "z": [1.0, 2.0]}],
              "lid": {"plate": None, "walls": []}, "cylinders": [], "curves": []},
    "ports": [{"name": "P1", "kind": "lumped", "dir": "z", "start": [2.0, 2.0, 0.0], "stop": [2.0, 2.0, 1.0],
               "nodes": [[2.0, 2.0, 0.0], [2.0, 2.0, 1.0], [0.0, 0.0, 0.0], [2.0, 2.0, 2.0]], "part": False}],
    "grid": []}


def test_build_csx_follows_the_spec_and_the_engine_settings(monkeypatch):  # spec 5.8, 6.2, W-1
    log = fake_openems(monkeypatch)
    build_csx(TINY, 1, 1e-9)
    names = [n for n, _, _ in log]
    assert log[0] == ("openEMS", (), {"EndCriteria": 1e-15})
    assert ("SetDeltaUnit", (1e-3,), {}) in log and ("SetBoundaryCond", (["MUR"] * 6,), {}) in log
    f2 = TINY["excitation"]["f2"]
    assert ("SetCustomExcite", (TINY["excitation"]["expr"], f2, f2), {}) in log and ("SetMaxTime", (1e-9,), {}) in log
    assert not {"SetTimeStepMethod", "SetTimeStep", "SetTimeStepFactor"} & set(names)
    assert ("AddMaterial", ("substrate_0",), {"epsilon": 4.5, "kappa": 0.0046}) in log
    assert [kw["priority"] for n, _, kw in log if n == "AddLinPoly"] == [10, METAL_PRIORITY]
    assert ("AddLumpedPort", (1, 50, [2.0, 2.0, 0.0], [2.0, 2.0, 1.0], "z"), {"excite": 1}) in log


def test_the_lid_and_the_vias_are_metal_primitives(monkeypatch):  # C-39, C-40, R3-057
    log = fake_openems(monkeypatch)
    lid = {"plate": {**SQUARE, "z": 3.0}, "walls": [{**SQUARE, "z": [2.0, 3.0]}]}
    build_csx({**TINY, "metal": {**TINY["metal"], "lid": lid, "cylinders": [{"at": [1.0, 1.0], "r": 0.15, "z": [0.0, 2.0]}],
                                 "curves": [{"at": [3.0, 3.0], "z": [0.0, 2.0]}]}}, 1, 1e-9)
    assert ("AddPolygon", ([SQUARE["x"], SQUARE["y"]], "z", 3.0), {"priority": METAL_PRIORITY}) in log
    assert ("AddLinPoly", ([SQUARE["x"], SQUARE["y"]], "z", 2.0, 1.0), {"priority": METAL_PRIORITY}) in log
    assert ("AddCylinder", ([1.0, 1.0, 0.0], [1.0, 1.0, 2.0], 0.15), {"priority": METAL_PRIORITY}) in log
    assert ("AddCurve", ([[3.0, 3.0], [3.0, 3.0], [0.0, 2.0]],), {}) in log


def test_grid_parts_are_lumped_elements_named_for_the_gate(monkeypatch):  # C-16
    log = fake_openems(monkeypatch)
    part = {**TINY["ports"][0], "name": "C4", "R": None, "C": 1e-12}
    build_csx({**TINY, "grid": [part]}, 1, 1e-9)
    assert ("AddLumpedElement", ("lumped_0",), {"ny": 2, "caps": True, "C": 1e-12}) in log
