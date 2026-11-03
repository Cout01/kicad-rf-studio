# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest
import shapely

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.spec import dc_pulse, debye
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
