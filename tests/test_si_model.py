# SPDX-License-Identifier: GPL-3.0-or-later
import math

import numpy as np
import pytest
import shapely

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.spec import dc_pulse, debye, debye_cells
from kicad_rf_studio.core.project import load_project, save_project
from test_cli_si import si_project


@pytest.fixture(scope="module")
def usb(tmp_path_factory):
    project, board, geom, _ = pipeline.load(pj := si_project(tmp_path_factory.mktemp("usb")))
    return pj, geom, pipeline.build_model(project, board, geom)


def test_an_si_model_is_mur_lossless_and_pulsed_from_dc(usb):  # design 5.2-5.5; Global Constraints
    _, geom, model = usb
    spec = model.spec
    assert spec["excitation"] == dc_pulse(10e9, 9e-9, 2e-9) and not {"boundary", "nf2ff", "join", "copper"} & set(spec)
    assert all(m["kappa"] == 0.0 and "debye" not in m for m in spec["materials"])  # never v1's κ (design 3)
    assert [(q["name"], q["dir"], q["part"]) for q in spec["ports"]] == [
        ("P1", "z", False), ("P2", "z", False), ("P3", "x", False), ("P4", "x", False), ("P5", "z", False),
        ("P6", "z", False), ("R1", "x", True), ("R2", "x", True)]
    assert model.blocked == []
    x, box = model.mesh.x, shapely.total_bounds(list(geom.protected.area.values()))
    mids = (x[1:] + x[:-1]) / 2
    assert np.diff(x)[(mids > box[0]) & (mids < box[2])].max() > 2 * model.mesh.d  # the SI rule, not the d fill


def test_a_debye_si_model_fits_each_lossy_substrate(tmp_path):  # design 5.3
    pj = si_project(tmp_path / "d")
    save_project(pj, {**load_project(pj), "dielectric": "debye"})
    project, board, geom, _ = pipeline.load(pj)
    materials = pipeline.build_model(project, board, geom).spec["materials"]
    subs = [m for m in materials if m["name"].startswith("substrate")]
    assert subs and [m["debye"] for m in subs] == [debye(m["eps"], 0.02, 10e9) for m in subs]
    assert all(m["kappa"] == 0.0 for m in materials) and not [m for m in materials if "debye" in m and
                                                              m["name"].startswith("mask")]
    data = load_project(pj)
    data["stackup"]["layers"] = [{**x, "epsilon_r": 1.5, "loss_tangent": 0.3} if x["name"] == "dielectric 3" else x
                                 for x in data["stackup"]["layers"]]  # the bottom prepreg: the first material
    save_project(pj, data)
    project, board, geom, _ = pipeline.load(pj)
    with pytest.raises(KrsError) as e:  # its ValueError's text never reaches the user (plan 1's carried item)
        pipeline.build_model(project, board, geom)
    assert (e.value.code, e.value.params) == ("E_DEBYE_FIT", {"eps_r": "1.5", "tan_d": "0.3"})


def test_a_debye_models_cells_are_its_substrates_nodes(usb, tmp_path):  # ruling D-4: the cost's weight
    pj = si_project(tmp_path / "d")
    save_project(pj, {**load_project(pj), "dielectric": "debye"})
    project, board, geom, _ = pipeline.load(pj)
    spec = pipeline.build_model(project, board, geom).spec
    assert (debye_cells(spec), math.prod(len(spec["mesh"][a]) for a in "xyz")) == (582291, 2072070)  # share 0.281
    assert debye_cells(usb[2].spec) == 0  # lossless: no Debye material


def test_a_debye_request_on_a_loss_tangent_of_0_runs_that_layer_lossless_and_says_so(tmp_path):  # ruling D-4
    pj = si_project(tmp_path / "d")
    data = {**load_project(pj), "dielectric": "debye"}

    def tan_3(tan):  # dielectric 3, the bottom prepreg, at this loss tangent
        return [{**x, "loss_tangent": tan} if x["name"] == "dielectric 3" else x for x in data["stackup"]["layers"]]
    save_project(pj, {**data, "stackup": {**data["stackup"], "layers": tan_3(0.0)}})
    project, board, geom, notes = pipeline.load(pj)
    assert ("W_SI_DEBYE_NO_LOSS", {"layers": "dielectric 3"}) in notes
    subs = [m for m in pipeline.build_model(project, board, geom).spec["materials"] if m["name"].startswith("substrate")]
    assert [m["name"] for m in subs if "debye" not in m] == ["substrate_0"]  # In2.Cu's slab keeps the mean, 0.01
    for tan, dielectric in ((None, "debye"), (0.0, "lossless")):  # None reads KiCad's 0.02; lossless fits nothing
        save_project(pj, {**data, "dielectric": dielectric, "stackup": {**data["stackup"], "layers": tan_3(tan)}})
        assert "W_SI_DEBYE_NO_LOSS" not in dict(pipeline.load(pj)[3])
