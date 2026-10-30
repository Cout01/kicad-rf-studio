# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace

import pytest
from shapely.geometry import Point

from kicad_rf_studio.core.geometry import chain_of
from kicad_rf_studio.core.geometry.region import band, build_region, f_max
from kicad_rf_studio.core.geometry.zstack import zstack
from kicad_rf_studio.core.kicad import classify
from kicad_rf_studio.core.kicad.stackup import Stackup
from kicad_rf_studio.core.model.parts import model_of, project_parts, role
from test_gates import project_of


def lpf_parts(**changes):
    """lpf915's parts; each keyword names a footprint that takes those fields, as in lpf_parts(C4={"dnp": True})."""
    board, p = project_of("lpf915", "U1.1", "J1.1")  # tests/test_gates.py
    board = replace(board, footprints={r: replace(fp, **changes.get(r, {})) for r, fp in board.footprints.items()})
    zs = zstack(Stackup.from_json(p["stackup"]), board.copper_layers)
    roi = build_region(board, chain_of(p), p["ports"], zs, f_max(p)).roi
    return project_parts(board, chain_of(p), classify(board, p["classes"]), roi, *band(p))


def test_lpf915_roles_and_models():  # spec 5.7
    series, shunt, others, notes = lpf_parts()
    assert {q["ref"]: q["role"] for q in series + shunt + others} == {
        "C1": "port", "L1": "port", "R1": "copper", "C2": "port", "C3": "port", "R2": "open", "C4": "open"}
    assert [q["ref"] for q in others] == ["C4"] and [q["dnp"] for q in shunt] == [False, False, True]
    assert series[0]["model"] == {"package": "0402", "esl_h": 5e-10, "esr_ohm": 0.1, "cp_f": 3e-14}
    assert others[0]["model"]["package"] == "0603" and notes == [("W_PART_OPEN", {"refs": "C4"})]


C0402 = model_of("Capacitor_SMD:C_0402_1005Metric")


@pytest.mark.parametrize(("kind", "value", "dnp", "angle", "place", "expected"), [
    ("C", 1e-10, True, 0, "series", "open"),            # DNP
    ("R", 0.0, False, 0, "series", "copper"),           # 0R
    ("R", 0.0, False, 45, "shunt", "copper"),           # a turned 0R is still copper
    ("L", 1.5e-8, False, 45, "series", "curve_port"),   # rotated
    ("L", 1.5e-8, False, 0, "series", "port"),          # a series inductor is always a port
    ("C", 0.4e-12, False, 90, "other", "grid"),         # SRF 11.3 GHz > 3·f2 = 9.06 GHz
    ("C", 1e-12, False, 0, "other", "open"),            # SRF 7.1 GHz
    ("R", 1e3, False, 0, "other", "grid"),              # SRF 41 GHz
    ("L", 1e-6, False, 0, "other", "port"),             # spec 5.7: no choke (3.8 kΩ at f1), so a port
    (None, None, False, 0, "series", "port")])          # a diode on the path: a port with no model
def test_role(kind, value, dnp, angle, place, expected):
    assert role(kind, value, C0402 if kind else None, dnp, angle, place, 457.5e6, 3.0195e9) == expected


def test_a_choke_is_open_only_while_it_holds_200_z0_over_the_band():  # C-12, spec 5.7
    m = model_of("Inductor_SMD:L_0402_1005Metric")
    assert role("L", 10e-3, m, False, 0, "shunt", 0.5e6, 3.3e6) == "open"      # ≥ 31 kΩ, SRF 9.2 MHz
    assert role("L", 1e-6, m, False, 0, "shunt", 457.5e6, 3.0195e9) == "port"  # 3.8 kΩ at f1
    assert role("L", 10e-6, m, False, 0, "shunt", 457.5e6, 3.0195e9) == "port" # SRF 290 MHz: 1.8 kΩ at f2


# --- beyond the brief's tests ------------------------------------------------------------------


def test_unreadable_values_are_noted_for_c_l_and_r_parts_and_a_dnp_part_is_not_warned_open():  # L-7, P4, P5
    # L1 is series, C2 shunt with an inductor's unit, R2 a DNP shunt part, C4 the other part, made DNP here
    series, shunt, others, notes = lpf_parts(L1={"value": ""}, C2={"value": "15nH"}, R2={"value": "TBD"},
                                             C4={"value": "??", "dnp": True})
    assert [q["value"] for q in series + shunt + others] == ["100pF", "", "0R", "15nH", "3.3pF", "TBD", "??"]
    assert notes == [("W_VALUE_UNREADABLE", {"refs": "C2, C4, L1, R2"})]


def test_an_other_part_has_two_nets_a_pad_in_the_roi_and_is_no_connector_or_shield():
    board, p = project_of("lpf915", "U1.1", "J1.1")
    c4 = board.footprints["C4"]  # on VDD and GND: lpf915's only two-pad part off the chain

    def others(roi=c4.pads[0].polygon, fp=c4, **classes):
        b = replace(board, footprints={**board.footprints, "C4": fp})
        parts = project_parts(b, chain_of(p), classify(b, {**p["classes"], **classes}), roi, *band(p))
        return [q["ref"] for q in parts[2]]

    assert others() == ["C4"] and others(roi=Point(1e3, 1e3).buffer(1.0)) == []
    assert others(connectors=["C4"]) == [] and others(shields=["C4"]) == []
    assert others(fp=replace(c4, pads=tuple(replace(q, net="GND") for q in c4.pads))) == []


def test_a_part_that_is_not_a_c_l_or_r_has_no_model():  # spec 5.7: a model is the ideal value plus the preset
    board, p = project_of("lpf915", "U1.1", "J1.1")
    fps = dict(board.footprints)
    fps["D4"] = replace(fps.pop("C4"), ref="D4", lib_id="Diode_SMD:D_0603_1608Metric")  # C4's place, a diode
    b = replace(board, footprints=fps)
    others = project_parts(b, chain_of(p), classify(b, p["classes"]), fps["D4"].pads[0].polygon, *band(p))[2]
    assert [(q["ref"], q["model"]) for q in others] == [("D4", None)]


# --- Stage 3 plan 2, task 3: the rest of an antenna's board ----------------------------------------------------
G24, M915 = (1.84e9, 2.99e9), (693e6, 1.12e9)  # the pulse bands of 2400-2483.5 and 902-928 MHz


@pytest.mark.parametrize(("kind", "value", "dnp", "angle", "place", "pulse", "expected"), [
    ("C", 100e-9, False, 0, "board", G24, "copper"),   # a decoupling C: close to a short at RF
    ("C", 10e-12, False, 45, "far", G24, "copper"),    # at any angle, anywhere on the board
    ("C", 4.7e-12, False, 0, "board", G24, "copper"),  # 14.0 Ω − 7.6 Ω of ESL at 2.415 GHz: 6.4 Ω ≤ Z0/5
    ("C", 2.2e-12, False, 0, "board", G24, "open"),    # 22.4 Ω, and its SRF of 4.8 GHz is under 3·f2
    ("C", 1e-12, False, 0, "board", G24, "open"),      # 58 Ω: design 5.3's SRF wording would have shorted it
    ("C", 0.4e-12, False, 90, "board", G24, "grid"),   # SRF 11.3 GHz: in the grid in the measured region
    ("C", 0.4e-12, False, 90, "far", G24, "open"),     # but open past it
    ("C", 22e-12, False, 0, "board", M915, "copper"),  # 5.1 Ω at 906.5 MHz
    ("C", 4.7e-12, False, 0, "board", M915, "open"),   # 34.5 Ω, its SRF of 3.28 GHz under 3·f2 = 3.36 GHz
    ("R", 1e3, False, 0, "board", G24, "grid"), ("R", 1e3, False, 0, "far", G24, "open"),
    ("R", 0.0, False, 0, "far", G24, "copper"),        # a 0R
    ("L", 1e-6, False, 0, "board", G24, "open"),       # an inductor is never a port here
    ("C", None, False, 0, "board", G24, "open"),       # a value that does not read
    (None, None, False, 0, "board", G24, "open"),      # a bead, a diode
    ("C", 100e-9, True, 0, "board", G24, "open")])     # DNP
def test_the_rest_of_an_antennas_board_is_never_a_port(kind, value, dnp, angle, place, pulse, expected):  # 5.3; RF 4
    assert role(kind, value, C0402 if kind else None, dnp, angle, place, *pulse) == expected


def test_an_antennas_parts_are_every_two_pad_part_off_the_chain(mini_board):  # design 5.3; RF 4
    from shapely.geometry import box
    from test_antenna_kicad import fp
    from test_tracer import smd
    from kicad_rf_studio.core.kicad.tracer import Chain
    lib = "Resistor_SMD:R_0402_1005Metric"
    b = mini_board(fp("R1", lib, smd(1, "N1"), smd(2, "GND", x=2), value="1k") +
                   fp("R2", lib, smd(1, "N2"), smd(2, "GND", x=2), at="50 0", value="1k"))
    _, _, others, notes = project_parts(b, Chain("A.1", "B.1", ("RF",), (), ()), classify(b), box(-5, -5, 5, 5),
                                        1.84e9, 2.99e9, antenna=True)
    assert [(q["ref"], q["role"]) for q in others] == [("R1", "grid"), ("R2", "open")]
    assert notes == [("W_BOARD_PARTS_OPEN", {"refs": "R2"})]
