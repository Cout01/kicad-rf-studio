# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from shapely.geometry import box

from kicad_rf_studio.core.kicad import classify
from kicad_rf_studio.core.kicad.tracer import partner_ends, partner_net, trace_line
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model.parts import project_parts
from test_antenna_kicad import fp
from test_tracer import part, smd, two

NETS = {"USB_D+", "USB_D-", "D_P_1", "D_N_1", "USB_DP", "USB_DM", "CLKP", "CLKN", "/eth/TX+", "/eth/TX-", "+3V3",
        "VBUS", "A_DP", "A_DN", "A_DM", "usb_dp", "usb_dm"}


def test_kicads_pair_rule_and_the_dp_dm_alias():  # Stage 4 design 5.1; KiCad 10 pcbnew/board.cpp MatchDpSuffix
    assert partner_net("USB_D+", NETS) == ("USB_D-", "rule") and partner_net("USB_D-", NETS) == ("USB_D+", "rule")
    assert partner_net("D_P_1", NETS) == ("D_N_1", "rule")  # the digits and underscores after the P stay
    assert partner_net("/eth/TX+", NETS) == ("/eth/TX-", "rule") and partner_net("CLKN", NETS) == ("CLKP", "rule")
    assert partner_net("USB_DP", NETS) == ("USB_DM", "alias") and partner_net("USB_DM", NETS) == ("USB_DP", "alias")
    assert partner_net("A_DP", NETS) == ("A_DN", "rule")  # KiCad's complement first, when it is a net of the board
    assert [partner_net(n, NETS) for n in ("+3V3", "VBUS", "usb_dp")] == [None] * 3  # KiCad's P and N are upper case
    assert partner_net("USB_D+", {"USB_D+"}) is None  # no complement on the board


def board_of(mini_board, *extra):
    return mini_board(part("J1", smd(1, "USB_D+"), smd(2, "USB_D-", x=2), smd(3, "GND", x=4)) +
                      part("U1", smd(1, "MCU_D+"), smd(2, "MCU_D-", x=2), smd(3, "GND", x=4), at="20 0") + "".join(extra))


def test_the_partner_is_the_complements_one_pad_on_each_end_footprint(mini_board):  # design 5.1
    b = board_of(mini_board)
    assert partner_ends(b, classify(b), "J1.1", "U1.1") == ("J1.2", "U1.2", "rule")


def test_a_partner_with_two_pads_or_none_is_refused(mini_board):  # design 5.1
    b = mini_board(part("J2", smd("A6", "USB_D+"), smd("B6", "USB_D+", x=1), smd("A7", "USB_D-", x=2),
                        smd("B7", "USB_D-", x=3)) + part("U1", smd(1, "MCU_D+"), smd(2, "MCU_D-", x=2), at="20 0"))
    with pytest.raises(KrsError) as e:  # a USB-C receptacle's two D- pads
        partner_ends(b, classify(b), "J2.A6", "U1.1")
    assert (e.value.code, e.value.params) == ("E_SI_PARTNER", {"net": "USB_D+", "pad": "J2.A6", "ref": "J2",
                                                               "partner": "USB_D-", "pads": "J2.A7, J2.B7"})
    b = mini_board(part("J3", smd(1, "SIG")) + part("U3", smd(1, "SIG"), at="20 0"))
    with pytest.raises(KrsError) as e:
        partner_ends(b, classify(b), "J3.1", "U3.1")
    assert (e.value.code, e.value.params) == ("E_SI_PARTNER", {"net": "SIG", "pad": "J3.1", "ref": "J3",
                                                               "partner": "T_NONE", "pads": "T_NONE"})


def test_a_line_through_a_part_of_three_or_more_pads_is_refused(mini_board):  # design 5.1; Review Focus 5
    cmc = part("L1", smd(1, "A"), smd(2, "B", x=2), smd(3, "A2", y=2), smd(4, "B2", x=2, y=2), at="10 0")
    b = mini_board(part("J1", smd(1, "A")) + cmc + part("U1", smd(1, "B"), at="20 0"))
    with pytest.raises(KrsError) as e:
        trace_line(b, classify(b), "J1.1", "U1.1")
    assert (e.value.code, e.value.params) == ("E_SI_THROUGH_PART", {"start": "J1.1", "end": "U1.1", "refs": "L1"})
    b = mini_board(part("J1", smd(1, "A")) + part("U1", smd(1, "B"), at="20 0"))
    with pytest.raises(KrsError) as e:
        trace_line(b, classify(b), "J1.1", "U1.1")
    assert e.value.code == "E_NO_CHAIN"  # nothing on the way: v1's refusal
    esd = part("U2", smd(1, "A"), smd(2, "GND", x=1), smd(3, "A2", x=2))  # pads on the line: copper, no refusal
    b = mini_board(part("J1", smd(1, "A")) + esd + two("R1", "A", "B") + part("U1", smd(1, "B"), at="20 0"))
    assert [p.ref for p in trace_line(b, classify(b), "J1.1", "U1.1").series] == ["R1"]


def test_an_si_lines_parts_are_ports_but_its_pull_ups(mini_board):  # design 5.1, 5.3 (A-27); Review Focus (pull-up)
    r = "Resistor_SMD:R_0402_1005Metric"
    b = mini_board(part("J1", smd(1, "A")) + part("U1", smd(1, "B"), at="20 0") +
                   "".join(fp(ref, r, smd(1, n1), smd(2, n2, x=2), value=v) for ref, n1, n2, v in (
                       ("R1", "A", "B", "22"), ("R5", "A", "+3V3", "1.5k"), ("R6", "B", "GND", "100"),
                       ("R7", "A", "C", "10k"))) +
                   part("R8", smd(1, "A"), smd(2, "GND", x=2), dnp=True) +  # a DNP placeholder: a port, value open
                   fp("C9", "Capacitor_SMD:C_0402_1005Metric", smd(1, "+3V3"), smd(2, "GND", x=2), value="100nF"))
    c = classify(b)
    series, shunt, others, notes = project_parts(b, trace_line(b, c, "J1.1", "U1.1"), c, box(-50, -50, 50, 50),
                                                 0.0, 10e9, si=True)
    assert [(q["ref"], q["role"]) for q in series] == [("R1", "port")]
    assert [(q["ref"], q["role"], q["value"]) for q in shunt] == [("R5", "open", "1.5k"), ("R6", "port", "100"),
                                                                  ("R7", "port", "10k"), ("R8", "port", "open")]
    assert [(q["ref"], q["role"]) for q in others] == [("C9", "copper")]  # A-27's rule at f_max/2
    assert ("I_SI_SHUNT_OPEN", {"refs": "R5"}) in notes and "W_VALUE_UNREADABLE" not in dict(notes)


def test_a_dnp_pull_up_is_open_at_open_and_not_listed(mini_board):  # Stage 4 plan 2's minor; Review Focus 5
    r = "Resistor_SMD:R_0402_1005Metric"
    b = mini_board(part("J1", smd(1, "A")) + part("U1", smd(1, "B"), at="20 0") + two("R1", "A", "B") +
                   fp("R5", r, smd(1, "A"), smd(2, "+3V3", x=2), value="1.5k") +
                   fp("R8", r, "(attr smd dnp) ", smd(1, "A"), smd(2, "+3V3", x=2), value="10k"))
    c = classify(b)
    _, shunt, _, notes = project_parts(b, trace_line(b, c, "J1.1", "U1.1"), c, box(-50, -50, 50, 50), 0.0, 10e9,
                                       si=True)
    assert [(q["ref"], q["role"], q["value"]) for q in shunt] == [("R5", "open", "1.5k"), ("R8", "open", "open")]
    assert ("I_SI_SHUNT_OPEN", {"refs": "R5"}) in notes  # a DNP part is open as any DNP part is, not as a pull-up
