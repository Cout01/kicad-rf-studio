# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import math

import numpy as np
import pytest

from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import model_of, srf
from kicad_rf_studio.core.post.chain import part_impedances, s2p_impedance, z_part
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import parts
from networks import C_BOX, star, terminate_np, write_s2p
from test_gates import project_of

F0 = 915e6
F, _ = grid(F0, 3, 1.1)
M0402 = model_of("0402")  # {"package": "0402", "esl_h": 5e-10, "esr_ohm": 0.1, "cp_f": 3e-14}
LPF = (("C1", "C", 100e-12), ("L1", "L", 15e-9), ("C2", "C", 3.3e-12), ("C3", "C", 3.3e-12))  # lpf915's part ports
FB1 = {"ref": "FB1", "pads": ["FB1.1", "FB1.2"], "nets": ["RF_C", "RF_OUT"], "value": "x", "dnp": False,
       "role": "port", "model": None, "s2p": None}  # a ferrite bead: no kind, so no ideal value (M-5)


def lpf():
    return copy.deepcopy(project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")[1])  # tests/test_gates.py


def test_the_part_models_follow_the_presets():  # C-13, spec 5.7; r6 §4
    f = F[[71, 213, 355]]
    assert z_part("C", 100e-12, M0402, f) == pytest.approx([0.1 + 1.135j, 0.1 + 4.879j, 0.1 + 8.044j], abs=1e-3)
    assert z_part("C", 3.3e-12, M0402, f) == pytest.approx([0.1 - 49.834j, 0.1 - 20.605j, 0.1 - 8.946j], abs=1e-3)
    assert z_part("L", 15e-9, M0402, f) == pytest.approx([0.103 + 87.539j, 0.113 + 183.384j, 0.133 + 298.694j],
                                                          abs=1e-3)
    assert z_part("R", 0.0, M0402, f[:1]) == pytest.approx([2.876j], abs=1e-3)  # a 0R made a port
    assert z_part("L", 15e-9, None, f) == pytest.approx(2j * np.pi * f * 15e-9, rel=1e-15)  # no preset: ideal
    w = 2 * np.pi * F
    assert z_part("L", 1e-6, M0402, F) == pytest.approx(1 / (1 / (0.1 + 1j * w * 1e-6) + 1j * w * 3e-14), rel=1e-12)
    srf_c = srf("C", 100e-12, M0402)
    assert abs(z_part("C", 100e-12, M0402, np.array([srf_c]))[0].imag) < 1e-9  # parts.srf's resonance


@pytest.mark.parametrize(("kind", "value", "connection", "z0"), [
    ("C", 3.3e-12, "series", 50.0), ("C", 3.3e-12, "shunt", 50.0), ("L", 15e-9, "series", 75.0),
    ("L", 15e-9, "shunt", 50.0), ("C", 100e-12, "series", 50.0)])
def test_an_s2p_gives_back_the_impedance_it_was_built_from(tmp_path, kind, value, connection, z0):  # C-14
    z = z_part(kind, value, None, F)
    got, fits = s2p_impedance(write_s2p(tmp_path / "part.s2p", z, connection, F, z0), connection, "C9", F)
    assert np.abs(got / z - 1).max() <= 1e-12 and fits is None


def test_an_s2p_takes_the_mean_of_s21_and_s12(tmp_path):  # C-14
    import skrf as rf

    n = rf.Network()
    n.read_touchstone(str(write_s2p(tmp_path / "l.s2p", z_part("L", 15e-9, None, F), "series", F)))
    s = n.s.copy()
    s[:, 0, 1] *= 1.01
    n.s = s
    n.write_touchstone(str(tmp_path / "skew"))
    m = (s[:, 1, 0] + s[:, 0, 1]) / 2
    assert s2p_impedance(tmp_path / "skew.s2p", "series", "L1", F)[0] == pytest.approx(100 * (1 - m) / m, rel=1e-12)


@pytest.mark.parametrize(("name", "text", "code"), [
    ("gone.s2p", None, "E_S2P_MISSING"), ("bad.s2p", "hello\n", "E_S2P_UNREADABLE"),
    ("empty.s2p", "# Hz S RI R 50\n", "E_S2P_UNREADABLE"),
    ("one.s1p", "# Hz S RI R 50\n1e8 0.5 0\n4e9 0.5 0\n", "E_S2P_PORTS")])
def test_an_s2p_that_cannot_serve_is_refused_by_name(tmp_path, name, text, code):  # spec 8, C-14
    file = tmp_path / name
    if text:
        file.write_text(text, encoding="ascii")
    with pytest.raises(KrsError) as e:
        s2p_impedance(file, "series", "C1", F)
    named = {"ref": "C1", "path": str(file)}
    assert (e.value.code, e.value.params) == (code, {**named, "ports": 1} if code == "E_S2P_PORTS" else named)


def test_an_s2p_that_misses_the_band_is_never_extrapolated(tmp_path):  # C-14
    f = np.linspace(1e9, 3e9, 21)
    file = write_s2p(tmp_path / "c.s2p", z_part("C", 3.3e-12, None, f), "series", f)
    with pytest.raises(KrsError) as e:
        s2p_impedance(file, "series", "C1", F)
    assert (e.value.code, e.value.params) == ("E_S2P_BAND", {"ref": "C1", "path": str(file), "f_lo": "1000.0",
                                                             "f_hi": "3000.0", "f1": "457.5", "f2": "3015.6"})


def test_an_s2p_named_by_the_parts_place_is_warned(tmp_path):  # Review Focus 2: C2 sits in shunt, its file is series
    file = write_s2p(tmp_path / "c2.s2p", z_part("C", 3.3e-12, None, F), "series", F)
    assert s2p_impedance(file, "shunt", "C2", F)[1] == "series"
    p = lpf()
    parts(p)["C2"]["s2p"] = {"file": "c2.s2p", "connection": "shunt"}
    assert part_impedances(p, tmp_path, ["C2"], F)[1] == [
        ("W_S2P_FIXTURE", {"ref": "C2", "path": str(file), "named": "shunt", "fits": "series"})]


def test_each_part_port_gets_its_model_or_its_file(tmp_path):  # C-13..C-15, spec 7.2
    p = lpf()
    p["chain"]["series"].append(dict(FB1))
    write_s2p(tmp_path / "c2.s2p", z_part("C", 4.7e-12, None, F), "shunt", F)
    write_s2p(tmp_path / "fb1.s2p", np.full(len(F), 30 + 40j), "series", F)
    parts(p)["C2"]["s2p"] = {"file": "c2.s2p", "connection": "shunt"}
    parts(p)["FB1"]["s2p"] = {"file": "fb1.s2p", "connection": "series"}  # no kind: an S2P is its only model
    z, notes = part_impedances(p, tmp_path, ["C1", "L1", "C2", "FB1"], F)
    assert np.allclose(z["C1"], z_part("C", 100e-12, M0402, F), rtol=1e-15) and notes == []
    assert np.abs(z["C2"] / z_part("C", 4.7e-12, None, F) - 1).max() <= 1e-12
    assert np.abs(z["FB1"] / (30 + 40j) - 1).max() <= 1e-12
    for ref, value in (("C3", "x"), ("C3", "0pF"), ("FB1", "x")):  # unreadable; a C of 0, an open; FB1 with no file
        parts(p)[ref].update(value=value, s2p=None)
        with pytest.raises(KrsError) as e:
            part_impedances(p, tmp_path, [ref], F)
        assert (e.value.code, e.value.params) == ("E_PART_NO_VALUE", {"ref": ref, "value": value})


# --- beyond the brief's tests ---------------------------------------------------------------------------------


def test_a_coarse_s2p_with_no_point_in_the_band_still_serves(tmp_path):  # C-14: the fixture check has nothing to judge
    f = np.array([100e6, 4e9])
    file = write_s2p(tmp_path / "coarse.s2p", z_part("C", 3.3e-12, None, f), "series", f)
    z, fits = s2p_impedance(file, "shunt", "C1", F)
    assert fits is None and z.shape == F.shape and np.isfinite(z).all()
