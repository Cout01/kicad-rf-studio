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
