# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import math

import numpy as np
import pytest

from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import model_of, srf
from kicad_rf_studio.core.post.chain import ideal_schematic, loads, part_impedances, s2p_impedance, terminate, z_part
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


CLASSES = {"gnd_nets": ["GND"], "power_nets": []}


def part(ref, a, b, role="port"):
    return {"ref": ref, "nets": [a, b], "role": role}


def schematic(series=(), shunt=(), nets=("A", "B")):
    return {"chain": {"nets": list(nets), "series": list(series), "shunt": list(shunt)}, "others": [],
            "classes": CLASSES}


BW_C, BW_L = 1 / (2 * np.pi * F0 * 50), 2 * 50 / (2 * np.pi * F0)  # Butterworth n = 3 pi at f0: 3.4788 pF, 17.394 nH
PI = schematic([part("L1", "A", "B")], [part("C1", "A", "GND"), part("C2", "B", "GND")])
W = 2 * np.pi * F
PI_Z = {"L1": 1j * W * BW_L, "C1": 1 / (1j * W * BW_C), "C2": 1 / (1j * W * BW_C)}


@pytest.mark.parametrize(("c", "shown"), [(None, "T_MISSING"), (0.0, "0"), (math.inf, "inf")])
def test_a_part_port_needs_a_usable_c_box(c, shown):  # C-16
    with pytest.raises(KrsError) as e:
        loads({"C1": z_part("C", 1e-12, None, F)}, ["C1"], {} if c is None else {"C1": c}, F)
    assert (e.value.code, e.value.params) == ("E_CBOX", {"ref": "C1", "value": shown})


def test_the_termination_is_scikit_rf_circuit_and_agrees_with_numpy():  # spec 7.2, C-6 (owner-confirmed: 1e-12)
    zk = loads({r: z_part(k, v, M0402, F) for r, k, v in LPF}, [r for r, _, _ in LPF],
               dict.fromkeys([r for r, _, _ in LPF], C_BOX), F)
    assert np.abs(zk[:, 1] - 1 / (1 / z_part("L", 15e-9, M0402, F) + 2j * np.pi * F * C_BOX)).max() <= 1e-9
    assert np.abs(terminate(star(F, 6), [0, 1], zk, F) - terminate_np(star(F, 6), [0, 1], zk)).max() <= 1e-12
    assert np.abs(terminate(star(F, 2), [0, 1], np.zeros((len(F), 0)), F) - star(F, 2)).max() <= 1e-15  # M = 0


def test_the_ideal_schematic_of_a_butterworth_pi():  # C-30: the ABCD oracle in closed form; r6 §6
    s = ideal_schematic(PI, PI_Z, F)
    assert np.abs(np.abs(s[:, 1, 0]) ** 2 - 1 / (1 + (F / F0) ** 6)).max() <= 1e-13
    assert 20 * np.log10(abs(s[71, 1, 0])) == pytest.approx(-3.0103, abs=1e-4)
    assert np.abs((np.abs(s) ** 2).sum(1) - 1).max() <= 1e-13  # lossless


@pytest.mark.parametrize(("model", "s21_db"), [(None, [-1.735, -15.80, -26.36]),
                                               (M0402, [-1.958, -19.971, -39.063])])
def test_lpf915s_ideal_schematic(model, s21_db):  # C-30: R1 (0R) a short, R2 (DNP) left out, C4 (others) excluded
    s = ideal_schematic(lpf(), {r: z_part(k, v, model, F) for r, k, v in LPF}, F)
    assert 20 * np.log10(np.abs(s[[71, 213, 355], 1, 0])) == pytest.approx(s21_db, abs=5e-3)


def test_one_net_a_bridging_shunt_and_the_nets_off_the_chain():  # C-30
    assert np.abs(ideal_schematic(schematic(nets=["LINE"]), {}, F) - np.array([[0, 1], [1, 0]])).max() <= 1e-15
    zl, zx = 1j * W * 15e-9, 1 / (1j * W * 1e-12)
    zs = zl * zx / (zl + zx)
    bridge = ideal_schematic(schematic([part("L1", "A", "B")], [part("X1", "A", "B")]), {"L1": zl, "X1": zx}, F)
    assert np.abs(bridge[:, 1, 0] - 100 / (100 + zs)).max() <= 1e-13
    s = ideal_schematic(schematic([part("L1", "A", "B")], [part("R9", "B", "GND", "copper")]), {"L1": zl}, F)
    assert np.abs(s[:, 1, 0]).max() <= 1e-15 and np.abs(s[:, 1, 1] + 1).max() <= 1e-15  # a grounded port reads −1
    stub = schematic([part("L1", "A", "B")], [part("R2", "B", "SMA", "copper"), part("C9", "B", "SMA")])
    assert np.abs(ideal_schematic(stub, {"L1": zl, "C9": zx}, F)[:, 1, 0] - 100 / (100 + zl)).max() <= 1e-13  # floats
    short = ideal_schematic(schematic([part("R5", "A", "B")]), {"R5": np.zeros(len(F), complex)}, F)  # 0R port, no preset
    assert np.abs(short - np.array([[0, 1], [1, 0]])).max() <= 1e-15


# --- beyond the brief's tests ---------------------------------------------------------------------------------


def test_a_coarse_s2p_with_no_point_in_the_band_still_serves(tmp_path):  # C-14: the fixture check has nothing to judge
    f = np.array([100e6, 4e9])
    file = write_s2p(tmp_path / "coarse.s2p", z_part("C", 3.3e-12, None, f), "series", f)
    z, fits = s2p_impedance(file, "shunt", "C1", F)
    assert fits is None and z.shape == F.shape and np.isfinite(z).all()


def test_the_termination_keeps_ext_in_order_and_closes_the_others_in_index_order():  # spec 7.2
    s = star(F, 4) * np.arange(1, 17).reshape(4, 4) / 16  # no two ports alike: star alone hides a swap
    zk = np.stack([z_part("L", 15e-9, None, F), z_part("C", 3.3e-12, None, F)], -1)  # ports 0 and 2
    assert np.abs(terminate(s, [3, 1], zk, F) - terminate_np(s, [3, 1], zk)).max() <= 1e-12


@pytest.mark.parametrize(("gnd_nets", "power_nets", "far", "grounded"), [
    (None, [], "AGND", True), ([], None, "+3V3", True), ([], ["VBIAS"], "VBIAS", True), ([], [], "AGND", False)])
def test_a_far_net_is_ground_by_its_list_or_by_its_name_where_the_list_is_null(gnd_nets, power_nets, far,
                                                                                 grounded):  # C-30
    p = schematic(shunt=[part("C1", "LINE", far)], nets=["LINE"])
    p["classes"] = {"gnd_nets": gnd_nets, "power_nets": power_nets}
    zc = 1 / (1j * W * 1e-12)
    s21 = ideal_schematic(p, {"C1": zc}, F)[:, 1, 0]
    assert np.abs(s21 - (2 * zc / (2 * zc + 50) if grounded else 1)).max() <= 1e-13  # a shunt C, or one that floats
