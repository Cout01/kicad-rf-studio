# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np
import pytest

from kicad_rf_studio.core.geometry.region import air_cell
from kicad_rf_studio.core.mesh.gates import edge_lint
from kicad_rf_studio.core.model.csx import PML_CELLS
from kicad_rf_studio.core.model.spec import metal_in_pml
from kicad_rf_studio.core.project import load_project, save_project
from kicad_rf_studio.stoprule import flat_window
from test_antenna_geometry import model_of
from test_cli_antenna import FIX, antenna_project


def test_an_antennas_model_sits_in_an_air_box_under_pml_8(tmp_path):  # design 5.2, 5.3
    model, geom, _ = model_of(antenna_project(tmp_path))
    s, w = model.spec, geom.region.walls
    assert s["boundary"] == "pml_8" and metal_in_pml(s) == [] and edge_lint(model.mesh) == []  # the board's lines kept
    for k, a in enumerate("xyz"):
        v = np.array(s["mesh"][a])
        steps = np.diff(v)
        assert np.allclose(steps[:PML_CELLS], steps[0]) and np.allclose(steps[-PML_CELLS:], steps[-1])
        assert v[PML_CELLS] == pytest.approx(w[2 * k] - 31.228381, abs=2e-6)  # the gap past the walls
        assert v[-1 - PML_CELLS] == pytest.approx(w[2 * k + 1] + 31.228381, abs=2e-6)
        assert steps.max() <= air_cell(2.99e9) + 1e-6
    assert [len(s["mesh"][a]) for a in "xyz"] == [135, 137, 71]  # the prototype's


def test_the_far_field_box_join_and_flat_window_are_the_antennas(tmp_path):  # design 5.3-5.5
    model, geom, _ = model_of(pj := antenna_project(tmp_path))
    s, zs = model.spec, geom.zs
    assert s["nf2ff"] == {"f_hz": load_project(pj)["far_field"]["f_hz"],
                          "center": [107.0, -109.0, round((zs[0].z0 + zs[-1].z1) / 2, 6)]}  # the board's centre
    cu = [z for z in zs if z.kind == "copper"]
    assert s["join"] == [[[101.35, -100.55, cu[0].z0], [102.85, -99.45, cu[-1].z1]]]  # AE1.2 grown by d = 0.3
    exc = s["excitation"]
    assert (exc["f1"], exc["f2"], exc["t_max"]) == (1.84e9, 2.99e9, 30e-9)
    assert exc["flat_s"] == flat_window(2.44175e9) == pytest.approx(8.19085e-9, rel=1e-5)


def test_part_ports_record_no_far_field_and_mur_adds_no_pml(tmp_path):  # design 5.5, 5.2
    model, _, _ = model_of(antenna_project(tmp_path / "pi", FIX / "ifa2g4_pi.kicad_pcb"))
    assert "nf2ff" not in model.spec and model.spec["boundary"] == "pml_8"  # 1 + 3 jobs: a part-port run
    pj = antenna_project(tmp_path / "mur")
    save_project(pj, {**load_project(pj), "boundary": "mur"})
    model, _, _ = model_of(pj)
    # provisional: MUR is the untested fallback (W_AIR_BOX), which plan 4's P3-C tests and may re-pin
    assert "boundary" not in model.spec and [len(model.spec["mesh"][a]) for a in "xyz"] == [119, 121, 55]
