# SPDX-License-Identifier: GPL-3.0-or-later
import math
import sys
import types

import pytest

from kicad_rf_studio.core.model.csx import METAL_PRIORITY, _prism, build_csx
from kicad_rf_studio.core.model.spec import dc_pulse, excitation


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


def test_the_si_pulse_goes_through_v1s_custom_excitation(monkeypatch):  # Stage 4 design 5.4
    log = fake_openems(monkeypatch)
    exc = dc_pulse(10e9, 10e-9, 2e-9)
    build_csx({**TINY, "excitation": exc}, 1, 10e-9)
    assert ("SetCustomExcite", (exc["expr"], 10e9, 10e9), {}) in log and ("SetMaxTime", (10e-9,), {}) in log
    assert log[0] == ("openEMS", (), {"EndCriteria": 1e-15})  # the port residual alone stops it (design 5.4)


def test_a_debye_material_is_csxcads_debye_property_and_a_plain_one_is_not(monkeypatch):  # 5.3; SI keys only in SI
    log = fake_openems(monkeypatch)
    monkeypatch.setitem(sys.modules, "CSXCAD.CSProperties",
                        types.SimpleNamespace(CSPropDebyeMaterial=Rec(log, "CSPropDebyeMaterial")))
    db = {"eps_inf": 4.0, "delta": [0.2, 0.1], "f_relax_hz": [1e9, 1e10]}
    build_csx({**TINY, "materials": [{**TINY["materials"][0], "kappa": 0.0, "debye": db}]}, 1, 1e-9)
    assert [kw for n, _, kw in log if n == "CSPropDebyeMaterial"] == [{"order": 2, "name": "substrate_0", "epsilon": 4.0}]
    assert [(a, kw) for n, a, kw in log if n == "SetDispersiveMaterialProperty"] == [
        ((0,), {"eps_delta": 0.2, "eps_relax": 1 / (2 * math.pi * 1e9)}),  # relaxation times, in s
        ((1,), {"eps_delta": 0.1, "eps_relax": 1 / (2 * math.pi * 1e10)})]
    names = [n for n, _, _ in log]
    assert "AddProperty" in names and "AddMaterial" not in names  # no κ
    assert [kw["priority"] for n, _, kw in log if n == "AddLinPoly"] == [10, METAL_PRIORITY]
    log.clear()
    build_csx(TINY, 1, 1e-9)  # a v1 spec: the plain material, as before
    assert ("AddMaterial", ("substrate_0",), {"epsilon": 4.5, "kappa": 0.0046}) in log
    assert "CSPropDebyeMaterial" not in [n for n, _, _ in log]


def test_the_boundary_is_mur_without_the_key_and_pml_8_on_all_six_faces_with_it(monkeypatch):  # design 5.2; S1 5.1
    log = fake_openems(monkeypatch)
    assert build_csx(TINY, 1, 1e-9)[2] is None  # a v1 spec: MUR (the test above) and no far-field box
    build_csx({**TINY, "boundary": "pml_8"}, 1, 1e-9)
    assert ("SetBoundaryCond", (["PML_8"] * 6,), {}) in log
    with pytest.raises(KeyError):  # MUR is the key's absence, never a value
        build_csx({**TINY, "boundary": "mur"}, 1, 1e-9)


FAR = {"f_hz": [1e9, 0.5e9, 1.1e9], "center": [2.0, 2.0, 2.0]}  # TINY's band, f1 0.5 GHz to f2 1.1 GHz, both ends in


def test_the_far_field_box_records_the_frequencies_in_the_frequency_domain(monkeypatch):  # design 5.5; RF 1
    log = fake_openems(monkeypatch)
    assert build_csx({**TINY, "nf2ff": FAR}, 1, 1e-9)[2] is not None
    assert build_csx({**TINY, "nf2ff": {**FAR, "f_hz": [0.6e9] * 11}}, 1, 1e-9)[2] is not None  # NF2FF_MAX itself
    names = [n for n, _, _ in log]
    # openEMS's own placement under PML_8, accumulated every Nyquist/4 steps, as the port probes sample
    assert ("CreateNF2FFBox", ("nf2ff",), {"frequency": FAR["f_hz"], "over_sampling": 4}) in log
    assert names.index("CreateNF2FFBox") > names.index("SetBoundaryCond")  # it reads the grid and the boundary
    build_csx({**TINY, "nf2ff": {**FAR, "box": [[1.0, 1.0, 1.0], [3.0, 3.0, 3.0]]}}, 1, 1e-9)
    assert ("CreateNF2FFBox", ("nf2ff",), {"frequency": FAR["f_hz"], "over_sampling": 4, "start": [1.0, 1.0, 1.0],
                                           "stop": [3.0, 3.0, 3.0]}) in log


@pytest.mark.parametrize("f_hz", [[1.2e9], [0.4e9], [], [0.6e9] * 12])  # RF 1
def test_far_field_frequencies_outside_the_band_or_more_than_11_are_refused(monkeypatch, f_hz):  # design 5.5
    log = fake_openems(monkeypatch)
    with pytest.raises(ValueError, match="far-field frequencies"):
        build_csx({**TINY, "nf2ff": {**FAR, "f_hz": f_hz}}, 1, 1e-9)
    assert "CreateNF2FFBox" not in [n for n, _, _ in log]


def test_the_lid_and_the_vias_are_metal_primitives(monkeypatch):  # C-39, C-40, R3-057
    log = fake_openems(monkeypatch)
    lid = {"plate": {**SQUARE, "z": 3.0}, "walls": [{**SQUARE, "z": [2.0, 3.0]}]}
    build_csx({**TINY, "metal": {**TINY["metal"], "lid": lid, "cylinders": [{"at": [1.0, 1.0], "r": 0.15, "z": [0.0, 2.0]}],
                                 "curves": [{"at": [3.0, 3.0], "z": [0.0, 2.0]}]}}, 1, 1e-9)
    assert ("AddPolygon", ([SQUARE["x"], SQUARE["y"]], "z", 3.0), {"priority": METAL_PRIORITY}) in log
    assert ("AddLinPoly", ([SQUARE["x"], SQUARE["y"]], "z", 2.0, 1.0), {"priority": METAL_PRIORITY}) in log
    assert ("AddCylinder", ([1.0, 1.0, 0.0], [1.0, 1.0, 2.0], 0.15), {"priority": METAL_PRIORITY}) in log
    assert ("AddCurve", ([[3.0, 3.0], [3.0, 3.0], [0.0, 2.0]],), {}) in log


def test_a_sheet_of_no_thickness_is_a_polygon_in_its_plane():  # design 5.3: sheet copper, antenna only
    calls = []

    class Prop:
        def AddLinPoly(self, *a, **k):
            calls.append(("linpoly", a, k))

        def AddPolygon(self, *a, **k):
            calls.append(("polygon", a, k))

    xy = {"x": [0.0, 1.0, 1.0], "y": [0.0, 0.0, 1.0]}
    _prism(Prop(), {**xy, "z": [0.71, 0.71]}, 1000, True)
    _prism(Prop(), {**xy, "z": [0.0, 0.035]}, 1000, True)
    _prism(Prop(), {**xy, "z": [0.71, 0.71]}, 1000)  # without the spec's key, as every v1 model: as before
    assert calls == [("polygon", ([xy["x"], xy["y"]], "z", 0.71), {"priority": 1000}),
                     ("linpoly", ([xy["x"], xy["y"]], "z", 0.0, 0.035), {"priority": 1000}),
                     ("linpoly", ([xy["x"], xy["y"]], "z", 0.71, 0.0), {"priority": 1000})]


def test_grid_parts_are_lumped_elements_named_for_the_gate(monkeypatch):  # C-16
    log = fake_openems(monkeypatch)
    part = {**TINY["ports"][0], "name": "C4", "R": None, "C": 1e-12}
    build_csx({**TINY, "grid": [part]}, 1, 1e-9)
    assert ("AddLumpedElement", ("lumped_0",), {"ny": 2, "caps": True, "C": 1e-12}) in log


def test_an_inductor_in_the_grid_is_letype_0_with_its_explicit_c(monkeypatch):  # spec 7.6, 11: never LEtype 1
    log = fake_openems(monkeypatch)
    build_csx({**TINY, "grid": [{**TINY["ports"][0], "name": "L1", "R": None, "C": 6e-16, "L": 1.5e-8}]}, 1, 1e-9)
    assert ("AddLumpedElement", ("lumped_0",), {"ny": 2, "caps": True, "C": 6e-16, "L": 1.5e-8}) in log
    assert not any("LEtype" in kw for _, _, kw in log)


def test_build_csx_adds_a_curve_port(monkeypatch):
    log = fake_openems(monkeypatch)
    build_csx({**TINY, "ports": [{**TINY["ports"][0], "kind": "curve"}]}, 1, 1e-9)
    assert ("AddCurvePort", (1, 50, [2.0, 2.0, 0.0], [2.0, 2.0, 1.0]), {"excite": 1}) in log


def test_probes_follow_the_ports(monkeypatch):  # D-13
    log = fake_openems(monkeypatch)
    volt = {"name": "s0_v1", "type": 0, "weight": 1, "start": [2.0, 2.0, 1.0], "stop": [2.0, 2.0, 0.0]}
    loop = {"name": "s0_i0", "type": 1, "weight": 1, "norm_dir": 0, "start": [2.5, 1.5, 0.5], "stop": [2.5, 2.5, 2.5]}
    build_csx({**TINY, "probes": [volt, loop]}, 1, 1e-9)
    names = [n for n, _, _ in log]
    assert ("AddProbe", ("s0_v1",), {"p_type": 0, "weight": 1}) in log
    assert ("AddProbe", ("s0_i0",), {"p_type": 1, "weight": 1, "norm_dir": 0}) in log
    assert ("AddBox", ([2.5, 1.5, 0.5], [2.5, 2.5, 2.5]), {}) in log and names.index("AddProbe") > names.index("AddLumpedPort")
