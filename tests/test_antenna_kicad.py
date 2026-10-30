# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pytest

from kicad_rf_studio.core.kicad import classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.tracer import adopt, antenna_kind, antenna_kinds, check_antenna, feed_pad
from kicad_rf_studio.core.messages import KrsError
from test_tracer import smd

FIX = Path(__file__).parent / "fixtures"
POLY = ('(fp_poly (pts (xy 0 -2) (xy 4 -2) (xy 4 -1.5) (xy 0 -1.5)) (stroke (width 0) (type solid)) (fill yes) '
        '(layer "F.Cu") (uuid "{}"))')  # 2 mm² of copper against a 1 mm² pad: a radiator
STUB = '(fp_line (start 0 0) (end 2 0) (stroke (width 0.5) (type solid)) (layer "F.Cu") (uuid "{}"))'  # a net-tie stub
KEEPOUT = ('(zone (net 0) (net_name "") (layer "F.Cu") (uuid "k{}") (hatch full 0.5) (keepout (tracks not_allowed) '
           '(vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints not_allowed)) '
           '(polygon (pts (xy 0 -5) (xy 5 -5) (xy 5 -10) (xy 0 -10))))')


def fp(ref, lib, *items, at="0 0", value="x"):
    return (f'(footprint "{lib}" (layer "F.Cu") (uuid "f-{ref}") (at {at}) (property "Reference" "{ref}") '
            f'(property "Value" "{value}") {"".join(items)})')


KINDS = "".join([
    fp("AE1", "Lib:IFA", smd(1, "RF"), POLY.format("g1")),                              # a radiator drawn: printed
    fp("AE2", "RF_Antenna:Johanson_2450AT18x100", smd(1, "RF2"), smd(2, x=3), at="10 0"),  # pads only: chip
    fp("AE3", "Lib:Chip", smd(1, "RF3"), at="20 0"),                                     # AE, pads only: chip
    fp("U2", "RF_Module:ESP32-WROOM-32", smd(1, "GND"), POLY.format("g2"), at="30 0"),   # a module, whatever it draws
    fp("U3", "Lib:Module", smd(1, "RF4"), KEEPOUT.format(3), at="40 0"),                 # keep-out, no copper: module
    fp("U4", "Lib:Ant", smd(1, "RF5"), POLY.format("g3"), KEEPOUT.format(4), at="50 0"),  # keep-out and radiator: printed
    fp("R1", "Lib:R", smd(1, "RF"), smd(2, "GND", x=2), at="60 0"),                       # none
    fp("AE4", "RF_Antenna:Antenova_SR4G013_GPS", smd(1, "RF6"), *(smd(k, "GND", x=2 * (k - 1)) for k in (2, 3, 4)),
       STUB.format("g4"), at="70 0"),                                                    # a stub under its pads: chip
    fp("AE5", "RF_Antenna:Pulse_W3000", smd(1, "RF7"), smd(2, "GND", x=2), KEEPOUT.format(5), at="80 0")])  # chip


def test_antenna_kinds(mini_board):  # design 5.1
    b = mini_board(KINDS)
    assert antenna_kinds(b) == {"AE1": "printed", "AE2": "chip", "AE3": "chip", "AE4": "chip", "AE5": "chip",
                                "U2": "module", "U3": "module", "U4": "printed"}
    assert antenna_kind(b, "R1") is None and b.footprints["U3"].keepout and not b.footprints["AE1"].keepout
    assert [a.ref for a in b.areas] == ["AE1", "U2", "U4", "AE4"]


@pytest.mark.parametrize(("ref", "code"), [("AE2", "E_ANTENNA_CHIP"), ("AE3", "E_ANTENNA_CHIP"),
                                           ("AE4", "E_ANTENNA_CHIP"), ("AE5", "E_ANTENNA_CHIP"),
                                           ("U2", "E_ANTENNA_MODULE"), ("U3", "E_ANTENNA_MODULE")])
def test_modules_chip_antennas_and_other_footprints_are_refused(mini_board, ref, code):  # design 5.1; RF 1
    with pytest.raises(KrsError) as e:
        check_antenna(mini_board(KINDS), ref)
    assert (e.value.code, e.value.params) == (code, {"ref": ref})


def test_a_footprint_that_is_no_antenna_names_the_printed_ones(mini_board):
    b = mini_board(KINDS)
    for ref, code in (("R1", "E_NOT_AN_ANTENNA"), ("AE9", "E_ANTENNA_UNKNOWN")):
        with pytest.raises(KrsError) as e:
            check_antenna(b, ref)
        assert (e.value.code, e.value.params) == (code, {"ref": ref, "candidates": "AE1, U4"})
    check_antenna(b, "AE1")  # a printed antenna: no refusal


def test_the_feed_pad_and_adopted_copper_of_an_inverted_f():  # design 5.1, 5.3; RF 2
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    assert feed_pad(b, classify(b), "AE1").name == "AE1.1"
    adopt(b, "AE1", "RF")
    assert [(a.net, a.ref) for a in b.areas if a.source == "graphic"] == [("RF", "AE1")]
    assert [p.net for p in b.footprints["AE1"].pads] == ["RF", "GND"]  # the join pad keeps its GND
    assert [code for code, _ in b.warnings if code == "W_NETLESS_COPPER"] == []


def test_a_two_layer_meander_adopts_its_unnamed_holes():  # design 5.3
    b = load_board(FIX / "meander915.kicad_pcb")
    adopt(b, "AE1", feed_pad(b, classify(b), "AE1").net)
    assert {p.net for p in b.footprints["AE1"].pads} == {a.net for a in b.areas if a.source == "graphic"} == {"RF"}


def test_other_netless_copper_keeps_its_warning(mini_board):
    loose = '(gr_poly (pts (xy 0 20) (xy 2 20) (xy 2 22)) (stroke (width 0)) (fill yes) (layer "F.Cu") (uuid "loose"))'
    b = mini_board(KINDS + loose)
    adopt(b, "AE1", "RF")
    assert [p["uuid"] for code, p in b.warnings if code == "W_NETLESS_COPPER"] == ["g2", "g3", "g4", "loose"]


@pytest.mark.parametrize(("pads", "nets"), [((smd(1, "GND"),), "T_NONE"), ((smd(1, "RF"), smd(2, "RF2", x=2)), "RF, RF2")])
def test_an_antenna_needs_one_feed_net(mini_board, pads, nets):  # design 5.1
    b = mini_board(fp("AE1", "RF_Antenna:X", *pads, POLY.format("g1")))
    with pytest.raises(KrsError) as e:
        feed_pad(b, classify(b), "AE1")
    assert (e.value.code, e.value.params) == ("E_ANTENNA_FEED", {"ref": "AE1", "nets": nets})


def test_the_antenna_ends_the_chain_and_is_never_a_part():  # design 5.1; RF 2
    b = load_board(FIX / "ifa2g4.kicad_pcb")
    assert [p.ref for p in trace_chain(b, "U1.1", "AE1.1").shunt] == ["AE1"]  # v1's tracer: a shunt part
    chain = trace_chain(b, "U1.1", "AE1.1", antenna="AE1")
    assert (chain.nets, chain.series, chain.shunt) == (("RF",), (), ())
    pi = load_board(FIX / "ifa2g4_pi.kicad_pcb")
    chain = trace_chain(pi, "U1.1", "AE1.1", antenna="AE1")
    assert (chain.nets, [p.ref for p in chain.series], [p.ref for p in chain.shunt]) == (
        ("RF_A", "RF"), ["L1"], ["C2", "C3"])


# --- beyond the brief's tests: adopt's own refusal -----------------------------------------------------


def test_adopt_refuses_a_footprint_not_on_the_board(mini_board):  # adopt's docstring
    with pytest.raises(KrsError) as e:
        adopt(mini_board(KINDS), "AE9", "RF")
    assert (e.value.code, e.value.params) == ("E_ANTENNA_UNKNOWN", {"ref": "AE9", "candidates": "AE1, U4"})
