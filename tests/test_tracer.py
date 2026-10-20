# SPDX-License-Identifier: GPL-3.0-or-later
from itertools import count
from pathlib import Path

import pytest

from kicad_rf_studio.core.kicad import choose_reference, classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.tracer import Reference, is_gnd, is_power
from kicad_rf_studio.core.messages import KrsError

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def lpf(): return load_board(FIX / "lpf915.kicad_pcb")


def test_classify_lpf915(lpf):
    c = classify(lpf)
    assert "GND" in c.gnd and "VDD" in c.power and {"J1", "J2"} <= c.connectors and c.shields == {"SH1"}


@pytest.mark.parametrize("net, gnd, power", [
    ("/GND", True, False), ("GNDA", True, False), ("AGND", True, False), ("VSS", True, False),
    ("+3V3", False, True), ("3V3", False, True), ("VDD_RF", False, True), ("RF_OUT", False, False)])
def test_net_name_rules(net, gnd, power):
    assert (is_gnd(net), is_power(net)) == (gnd, power)


def test_output_chain(lpf):
    ch = trace_chain(lpf, "U1.1", "J1.1")
    assert ch.nets == ("RF_A", "RF_B", "RF_C", "RF_OUT")
    assert [p.ref for p in ch.series] == ["C1", "L1", "R1"] and ch.series[0].pads == ("C1.1", "C1.2")
    assert [p.ref for p in ch.shunt] == ["C2", "C3", "R2"]


def test_reverse_direction(lpf):
    assert [p.ref for p in trace_chain(lpf, "J1.1", "U1.1").series] == ["R1", "L1", "C1"]


def test_dnp_part_blocks_the_walk(lpf):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "U1.1", "J2.1")
    assert e.value.code == "E_NO_CHAIN"


def test_unknown_pad_lists_candidates(lpf):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "U1.99", "J1.1")
    assert e.value.code == "E_UNKNOWN_PAD" and e.value.params["candidates"].startswith("U1.")


def test_single_trace():
    b = load_board(FIX / "coupon_gcpw_pads.kicad_pcb")
    ch = trace_chain(b, "TP1.1", "TP2.1")
    assert ch.nets == ("LINE",) and ch.series == () and ch.shunt == ()


def test_references(lpf):
    c = classify(lpf)
    r = choose_reference(lpf, c, "U1.1"); assert (r.rule, r.pad) == ("ic", "U1.2")
    r = choose_reference(lpf, c, "J1.1"); assert r.rule == "connector" and lpf.pads(r.pad)[0].net == "GND"
    t = load_board(FIX / "coupon_gcpw_pads.kicad_pcb")
    r = choose_reference(t, classify(t), "TP1.1")
    assert r.rule == "copper" and r.layer == "F.Cu" and r.point is not None


# --- beyond the brief's eight tests: the rulings, and the rules the brief leaves open ------------------
# --- synthetic boards ----------------------------------------------------------------------------------

_ids = count(1)


def smd(number, net="", x=0.0, y=0.0, layer="F.Cu", size=1.0, uuid=None):
    """A square SMD pad at (x, y) of its footprint, where y points down as in the file."""
    net_node, uuid = (f'(net "{net}")' if net else ""), uuid or f"u{next(_ids)}"
    return (f'(pad "{number}" smd rect (at {x} {y}) (size {size} {size}) (layers "{layer}") {net_node} '
            f'(uuid "{uuid}"))')


def tht(number, net="", x=0.0, y=0.0):
    """A plated through-hole pad, which has copper on every layer."""
    net_node = f'(net "{net}")' if net else ""
    return (f'(pad "{number}" thru_hole circle (at {x} {y}) (size 1.5 1.5) (drill 0.8) (layers "*.Cu" "*.Mask") '
            f'{net_node} (uuid "u{next(_ids)}"))')


def paste(number, net="", x=0.0, y=0.0):
    """A paste-only pad: no copper, but it carries the net of its pad number, as in a KiCad file."""
    net_node = f'(net "{net}")' if net else ""
    return f'(pad "{number}" smd rect (at {x} {y}) (size 1 1) (layers "F.Paste") {net_node} (uuid "u{next(_ids)}"))'


def part(ref, *pads, at="0 0", dnp=False):
    attr = "(attr smd dnp) " if dnp else ""
    return (f'(footprint "Lib:{ref}" (layer "F.Cu") (uuid "f-{ref}") (at {at}) (property "Reference" "{ref}") '
            f'(property "Value" "x") {attr}{"".join(pads)})')


def two(ref, a, b, **kw):
    """A two-pad part: pad 1 on net `a`, pad 2 on net `b`."""
    return part(ref, smd(1, a), smd(2, b, x=2), **kw)


def frame(*extra, ref="SH", net="GND"):
    """Four pads at the corners of a 10 x 10 mm square, and any `extra` pads."""
    corners = [smd(i, net, x, y) for i, (x, y) in enumerate([(0, 0), (10, 0), (10, 10), (0, 10)], 1)]
    return part(ref, *corners, *extra)


def track(layer, net, x1, y1, x2, y2, width=0.2):
    return (f'(segment (start {x1} {y1}) (end {x2} {y2}) (width {width}) (layer "{layer}") (net "{net}") '
            f'(uuid "u{next(_ids)}"))')


def pour(layer, net, x0, y0, x1, y1):
    """A zone filled over the rectangle (x0, y0) to (x1, y1)."""
    pts = f"(pts (xy {x0} {y0}) (xy {x1} {y0}) (xy {x1} {y1}) (xy {x0} {y1}))"
    return (f'(zone (net "{net}") (layer "{layer}") (uuid "u{next(_ids)}") (polygon {pts}) '
            f'(filled_polygon (layer "{layer}") {pts}))')


def ref_of(board, signal):
    return choose_reference(board, classify(board), signal)


# --- net names and classes -----------------------------------------------------------------------------


@pytest.mark.parametrize("net, gnd, power", [
    ("0V", True, False),  # both patterns fit it: ground wins
    ("gnd", True, False), ("Vdd", False, True),  # case does not matter
    ("/Rf/Filter/AGND", True, False), ("/Supply/+5V", False, True),  # only the name after the last "/" counts
    ("EARTH", True, False), ("SGND", True, False), ("GND_RF", True, False),
    ("VBUS", False, True), ("VCC_3V3", False, True), ("12V", False, True),
    ("RF_GND_SENSE", False, False), ("VDD-RF", False, False),  # the whole name must fit the pattern, not a part of it
    ("Net-(U1-Pad3)", False, False), ("", False, False)])
def test_more_net_name_rules(net, gnd, power):
    assert (is_gnd(net), is_power(net)) == (gnd, power)


def test_lpf915_classes_are_exactly_these(lpf):
    c = classify(lpf)
    assert (c.gnd, c.power, c.connectors, c.shields) == ({"GND"}, {"VDD"}, {"J1", "J2"}, {"SH1"})


def test_overrides_replace_the_computed_sets(lpf):
    c = classify(lpf, {"gnd_nets": ["RF_A"], "power_nets": [], "connectors": ["R1"], "shields": ["C1"]})
    assert (c.gnd, c.power, c.connectors, c.shields) == ({"RF_A"}, set(), {"R1"}, {"C1"})


def test_a_key_that_is_left_out_or_null_keeps_the_computed_set(lpf):
    c = classify(lpf, {"connectors": ["R1"], "shields": None})
    assert (c.gnd, c.power, c.connectors, c.shields) == ({"GND"}, {"VDD"}, {"R1"}, {"SH1"})


def test_shields_are_found_among_the_ground_nets_in_force(lpf):
    assert classify(lpf, {"gnd_nets": []}).shields == set()


def test_connectors_are_the_references_that_start_with_one_of_the_letter_groups(mini_board):
    refs = ["J1", "P2", "X3", "CN4", "TP1", "JP1", "PWR1", "XTAL1", "R5", "REF**", "REF**"]
    b = mini_board("".join(part(r, smd(1, "N")) for r in refs))
    assert "REF**#2" in b.footprints  # the second REF** was renamed
    assert classify(b).connectors == {"J1", "P2", "X3", "CN4"}


def test_a_ground_frame_with_a_pad_inside_is_a_shield(mini_board):
    assert classify(mini_board(frame() + part("U1", smd(1, "SIG", 5, 5)))).shields == {"SH"}


@pytest.mark.parametrize("x, y", [(20, 20), (5, 20), (20, 5)], ids=["far", "beside-in-x", "beside-in-y"])
def test_a_frame_with_nothing_inside_is_no_shield(mini_board, x, y):
    assert classify(mini_board(frame() + part("U1", smd(1, "SIG", x, y)))).shields == set()


def test_a_frame_with_a_pad_on_another_net_is_no_shield(mini_board):
    assert classify(mini_board(frame(smd(5, "SIG", 5, 0)) + part("U1", smd(1, "SIG", 5, 5)))).shields == set()


def test_one_ground_pad_is_no_shield(mini_board):
    assert classify(mini_board(part("G1", smd(1, "GND", 5, 5)) + part("U1", smd(1, "SIG", 5, 5)))).shields == set()


def test_a_shield_counts_only_its_copper_pads(mini_board):
    """A paste-only pad has no net and no copper: it must not stop a frame of ground pads from being a shield."""
    assert classify(mini_board(frame(paste(5)) + part("U1", smd(1, "SIG", 5, 5)))).shields == {"SH"}


def test_a_pad_without_copper_inside_the_frame_makes_no_shield(mini_board):
    assert classify(mini_board(frame() + part("U1", paste(1, "", 5, 5)))).shields == set()


# --- the chain -----------------------------------------------------------------------------------------


def test_unknown_pad_candidates_are_distinct_pads(lpf):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "SH1.9", "J1.1")  # SH1 has twenty pads called SH1.1: they are one candidate
    assert e.value.params["candidates"] == "SH1.1, U1.9"
    assert "SH1.1, U1.9" in str(e.value)  # the message renders with the parameters


def test_a_pad_without_copper_is_not_a_pad(lpf):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "U1.", "J1.1")  # U1 has four paste-only pads of that name
    assert e.value.code == "E_UNKNOWN_PAD" and "U1." not in e.value.params["candidates"].split(", ")


def test_the_end_pad_is_checked_too(lpf):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "U1.1", "J9.1")
    assert (e.value.code, e.value.params["name"]) == ("E_UNKNOWN_PAD", "J9.1")


def test_a_pad_name_on_two_nets_is_ambiguous(mini_board):
    b = mini_board(part("A", smd(1, "N1"), smd(1, "N2", 3)) + two("R1", "N1", "N3"))
    with pytest.raises(KrsError) as e:
        trace_chain(b, "A.1", "R1.2")
    assert (e.value.code, e.value.params) == ("E_AMBIGUOUS_PAD", {"name": "A.1", "nets": "N1, N2"})
    assert "N1, N2" in str(e.value)


def test_pads_of_one_name_on_one_net_are_one_pad(mini_board):
    b = mini_board(part("A", smd(1, "N1"), smd(1, "N1", 3), smd(2, "N2", 6)) + two("R1", "N1", "N3"))
    assert trace_chain(b, "A.1", "R1.2").nets == ("N1", "N3")


@pytest.mark.parametrize("start, end, name, net", [
    ("U1.2", "J1.1", "U1.2", "GND"), ("U1.8", "J1.1", "U1.8", "VDD"), ("U1.3", "J1.1", "U1.3", ""),
    ("U1.1", "J1.2", "J1.2", "GND")], ids=["start-gnd", "start-power", "start-no-net", "end-gnd"])
def test_a_chain_cannot_start_or_end_on_gnd_power_or_no_net(lpf, start, end, name, net):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, start, end)
    assert (e.value.code, e.value.params) == ("E_START_ON_GND", {"name": name, "net": net})
    assert name in str(e.value)


def test_no_chain_names_the_nets_reached(lpf):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "U1.1", "J2.1")
    assert e.value.params == {"start": "U1.1", "end": "J2.1", "reached": "RF_A, RF_B, RF_C, RF_OUT"}
    assert "RF_A, RF_B, RF_C, RF_OUT" in str(e.value)


def test_the_nets_reached_are_listed_by_name_not_in_the_order_of_the_walk(mini_board):
    b = mini_board(two("R1", "Z", "A") + two("R2", "M", "N"))  # the walk from R1.1 reaches Z, then A
    with pytest.raises(KrsError) as e:
        trace_chain(b, "R1.1", "R2.2")
    assert e.value.params["reached"] == "A, Z"


def test_series_parts_face_from_the_start_to_the_end(lpf):
    ch = trace_chain(lpf, "J1.1", "U1.1")
    assert (ch.start, ch.end, ch.nets) == ("J1.1", "U1.1", ("RF_OUT", "RF_C", "RF_B", "RF_A"))
    assert [(p.pads, p.nets) for p in ch.series] == [
        (("R1.2", "R1.1"), ("RF_OUT", "RF_C")), (("L1.2", "L1.1"), ("RF_C", "RF_B")),
        (("C1.2", "C1.1"), ("RF_B", "RF_A"))]


def test_shunt_parts_face_the_chain_and_include_a_dnp_part(lpf):
    ch = trace_chain(lpf, "U1.1", "J1.1")
    assert [(p.ref, p.pads, p.nets) for p in ch.shunt] == [
        ("C2", ("C2.1", "C2.2"), ("RF_B", "GND")), ("C3", ("C3.1", "C3.2"), ("RF_C", "GND")),
        ("R2", ("R2.1", "R2.2"), ("RF_OUT", "RF_SMA"))]  # R2 is DNP


def test_a_part_with_three_pads_with_a_net_blocks_the_walk(mini_board):
    q1 = part("Q1", smd(1, "B"), smd(2, "C", 2), smd(3, "GND", 4))
    with pytest.raises(KrsError) as e:
        trace_chain(mini_board(two("R1", "A", "B") + q1 + two("R3", "C", "D")), "R1.1", "R3.2")
    assert (e.value.code, e.value.params["reached"]) == ("E_NO_CHAIN", "A, B")


def test_the_walk_stops_at_a_connector(mini_board):
    b = mini_board(two("R1", "A", "B") + two("J5", "B", "C"))
    with pytest.raises(KrsError) as e:
        trace_chain(b, "R1.1", "J5.2")
    assert (e.value.code, e.value.params["reached"]) == ("E_NO_CHAIN", "A, B")


def test_only_pads_with_a_net_count_for_a_part(mini_board):
    b = mini_board(two("R1", "A", "B") + part("Q1", smd(1, "B"), smd(2, "C", 2), smd(3, "", 4)) + two("R3", "C", "D"))
    ch = trace_chain(b, "R1.1", "R3.2")
    assert ch.nets == ("A", "B", "C", "D") and [p.ref for p in ch.series] == ["R1", "Q1", "R3"]


def test_a_paste_only_pad_is_not_a_third_pad_with_a_net(mini_board):
    b = mini_board(part("R1", smd(1, "A"), smd(2, "B", 2), paste(2, "B", 2)))
    assert [p.ref for p in trace_chain(b, "R1.1", "R1.2").series] == ["R1"]


def test_parallel_parts_are_visited_in_ref_order(mini_board):
    b = mini_board(two("R2", "A", "B") + two("R1", "A", "B"))  # R2 comes first in the file
    ch = trace_chain(b, "R1.1", "R1.2")
    assert [p.ref for p in ch.series] == ["R1"] and [(p.ref, p.pads) for p in ch.shunt] == [("R2", ("R2.1", "R2.2"))]


def test_the_walk_takes_the_fewest_parts(mini_board):
    # S to T through R1 and R3, or through R2, R4 and R5, which a depth-first walk would reach first
    b = mini_board(two("R1", "S", "A") + two("R2", "S", "B") + two("R3", "A", "T") + two("R4", "B", "C")
                   + two("R5", "C", "T"))
    ch = trace_chain(b, "R1.1", "R3.2")
    assert ch.nets == ("S", "A", "T") and [p.ref for p in ch.series] == ["R1", "R3"]
    assert [(p.ref, p.pads, p.nets) for p in ch.shunt] == [
        ("R2", ("R2.1", "R2.2"), ("S", "B")), ("R5", ("R5.2", "R5.1"), ("T", "C"))]  # R5 is turned to face the chain


def test_a_connector_at_the_end_of_the_chain_is_no_shunt_part(mini_board):
    """J3 has two pads with a net, and one touches the chain. It is the port, not a part to put a port on."""
    b = mini_board(two("R1", "A", "B") + part("J3", smd(1, "B"), smd(2, "GND", 2)))
    ch = trace_chain(b, "R1.1", "J3.1")
    assert ch.nets == ("A", "B") and [p.ref for p in ch.series] == ["R1"] and ch.shunt == ()


def test_a_footprint_with_both_pads_on_one_net_is_no_part(mini_board):
    """A two-pad test point: its pads are one piece of copper, not a part between two nets."""
    b = mini_board(two("R1", "A", "B") + part("TP3", smd(1, "B"), smd(1, "B", 2.54)))
    assert trace_chain(b, "R1.1", "R1.2").shunt == ()


@pytest.mark.parametrize("overrides", [
    {"power_nets": ["RF_B"]}, {"gnd_nets": ["RF_B"]}, {"connectors": ["L1"]}, {"shields": ["C1"]}],
    ids=["power", "gnd", "connector", "shield"])
def test_the_given_classes_decide_where_the_walk_stops(lpf, overrides):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "U1.1", "J1.1", classify(lpf, overrides))
    assert e.value.code == "E_NO_CHAIN"


def test_the_given_classes_decide_what_is_gnd_at_the_ends(lpf):
    with pytest.raises(KrsError) as e:
        trace_chain(lpf, "U1.1", "J1.1", classify(lpf, {"gnd_nets": ["RF_A"]}))
    assert (e.value.code, e.value.params["net"]) == ("E_START_ON_GND", "RF_A")


# --- the references ------------------------------------------------------------------------------------


def test_a_pad_reference_names_the_pad_and_its_uuid(lpf):
    r = ref_of(lpf, "U1.1")
    assert r == Reference("ic", "U1.2", lpf.pads("U1.2")[0].uuid, None, "F.Cu")


def test_the_nearest_ground_pad_is_measured_between_centres(mini_board):
    # pad 2 is large: its edge is 1.5 mm from the signal pad's centre, but its centre is 4 mm away; pad 3 is 2.5 mm away
    pads = [smd(1, "SIG"), smd(2, "GND", 4, 0, size=5), smd(3, "GND", 0, 2.5), smd(4, "VDD", 0, -1.5)]
    assert ref_of(mini_board(part("U1", *pads)), "U1.1").pad == "U1.3"


def test_ties_go_to_the_lower_pad_number_then_the_lower_uuid(mini_board):
    def pick(*ground):  # (number, x, uuid) of ground pads, each 1.5 mm from the signal pad
        pads = [smd(n, "GND", x, 0, uuid=u) for n, x, u in ground]
        r = ref_of(mini_board(part("U1", smd(1, "SIG"), smd(9, "VDD", 0, 3), *pads)), "U1.1")
        return r.pad, r.uuid

    assert pick((3, -1.5, "a"), (2, 1.5, "z")) == ("U1.2", "z")  # the lower number, though its uuid is higher
    assert pick((2, -1.5, "z"), (2, 1.5, "a")) == ("U1.2", "a")  # one number: the lower uuid, though it comes last
    assert pick((2, -1.6, "a"), (3, 1.5, "z")) == ("U1.3", "z")  # 0.1 mm nearer is no tie: it beats the lower number


@pytest.mark.parametrize("lower", [1.45, -1.45])
def test_a_tie_is_not_decided_by_float_noise(mini_board, lower):
    """Turned 90 degrees at (3.3, 4.4), the pads 1.45 mm either side of the signal pad are 1.45 and
    1.4500000000000002 mm away: one distance to the nanometre, so the uuid decides."""
    ground = [smd(2, "GND", 0, y, uuid="a" if y == lower else "b") for y in (1.45, -1.45)]
    b = mini_board(part("U1", smd(1, "SIG"), smd(3, "VDD", 3), *ground, at="3.3 4.4 90"))
    assert ref_of(b, "U1.1").uuid == "a"


@pytest.mark.parametrize("signal, ground", [("J1.1", "J1.2"), ("J2.1", "J2.2")])
def test_a_connector_takes_a_ground_pad_on_the_signal_layer_with_the_lower_uuid(lpf, signal, ground):
    """Both have two ground pads on F.Cu at one distance from the signal pad. J2 has two more on B.Cu, and the
    lowest uuid of its four is on B.Cu: the layer rule, not the uuid alone, picks the pad."""
    r = ref_of(lpf, signal)
    front = [p for p in lpf.pads(ground) if "F.Cu" in p.layers]
    assert len(front) == 2 and (r.rule, r.pad, r.layer, r.point) == ("connector", ground, "F.Cu", None)
    assert r.uuid == min(p.uuid for p in front)


def test_three_pads_with_copper_make_an_ic(mini_board):
    b = mini_board(part("Q1", smd(1, "SIG"), smd(2, "GND", 0, 2), smd(3, "VDD", 2)))
    r = ref_of(b, "Q1.1")
    assert (r.rule, r.pad) == ("ic", "Q1.2")


def test_a_ground_pad_on_the_other_layer_is_never_the_reference(mini_board):
    b = mini_board(part("U1", smd(1, "SIG"), smd(2, "GND", 0, 1, layer="B.Cu"), smd(3, "GND", 0, 4), smd(4, "VDD", 4)))
    r = ref_of(b, "U1.1")
    assert (r.rule, r.pad, r.layer) == ("ic", "U1.3", "F.Cu")


def test_a_through_hole_ground_pad_is_on_the_signal_layer(mini_board):
    b = mini_board(part("U1", smd(1, "SIG"), tht(2, "GND", 0, 2), smd(3, "GND", 0, 4), smd(4, "VDD", 4)))
    assert ref_of(b, "U1.1").pad == "U1.2"


def test_a_through_hole_signal_pad_takes_its_reference_on_its_first_layer(mini_board):
    b = mini_board(part("U1", tht(1, "SIG"), smd(2, "GND", 0, 1, layer="B.Cu"), smd(3, "GND", 0, 3), smd(4, "VDD", 3)))
    r = ref_of(b, "U1.1")
    assert (r.pad, r.layer) == ("U1.3", "F.Cu")


def test_a_signal_pad_on_the_bottom_layer_takes_its_reference_there(mini_board):
    b = mini_board(part("U1", smd(1, "SIG", layer="B.Cu"), smd(2, "GND", 0, 1), smd(3, "GND", 0, 4, layer="B.Cu"),
                        smd(4, "VDD", 4, layer="B.Cu")))
    r = ref_of(b, "U1.1")
    assert (r.pad, r.layer) == ("U1.3", "B.Cu")


# GND copper of each kind, nearest first, with the nearest point to a signal pad at the origin. The decoys are nearer
# than all of it: copper of another net, a supply, and ground of every kind on the other layer.
SIGNAL = part("TP1", smd(1, "SIG"))
DECOYS = (track("F.Cu", "SIG2", -5, 1.5, 5, 1.5) + pour("F.Cu", "VDD", -5, -2, 5, -1.5)
          + track("B.Cu", "GND", -5, -1, 5, -1) + pour("B.Cu", "GND", -5, -3, 5, -1.2)
          + part("C8", smd(1, "GND", 0, -2.5, layer="B.Cu")) + part("C9", smd(1, "VDD", 2)))
GROUND = {"track": (track("F.Cu", "GND", -5, 3, 5, 3), (0.0, -2.9)),
          "area": (pour("F.Cu", "GND", -5, 4, 5, 8), (0.0, -4.0)),
          "pad": (part("G1", smd(1, "GND", 0, 5)), (0.0, -4.5))}


@pytest.mark.parametrize("kind", GROUND)
def test_the_copper_rule_takes_the_nearest_ground_copper_of_any_kind(mini_board, kind):
    kinds = list(GROUND)
    copper = "".join(GROUND[k][0] for k in kinds[kinds.index(kind):])  # this kind and the farther ones
    r = ref_of(mini_board(SIGNAL + DECOYS + copper), "TP1.1")
    assert (r.rule, r.pad, r.uuid, r.layer) == ("copper", None, None, "F.Cu")
    assert r.point == pytest.approx(GROUND[kind][1], abs=1e-9)


def test_no_reference_without_ground_copper_on_the_signal_layer(mini_board):
    behind = track("B.Cu", "GND", -5, 3, 5, 3) + part("G1", smd(1, "GND", 0, 5, layer="B.Cu"))
    ic = part("U1", smd(1, "SIG"), smd(2, "GND", 0, 2, layer="B.Cu"), smd(3, "VDD", 2))
    assert ref_of(mini_board(SIGNAL + behind), "TP1.1") is None
    assert ref_of(mini_board(ic + behind), "U1.1") is None


@pytest.mark.parametrize("ref, pads", [("J1", [smd(2, "SIG2", 2)]), ("U1", [smd(2, "SIG2", 2), smd(3, "VDD", 4)])],
                         ids=["connector", "ic"])
def test_a_connector_or_ic_without_a_ground_pad_falls_back_to_ground_copper(mini_board, ref, pads):
    r = ref_of(mini_board(part(ref, smd(1, "SIG"), *pads) + pour("F.Cu", "GND", -5, 4, 5, 8)), f"{ref}.1")
    assert (r.rule, r.pad, r.layer) == ("copper", None, "F.Cu") and r.point == pytest.approx((0.0, -4.0), abs=1e-9)


def test_pads_without_copper_are_neither_references_nor_counted_as_pads(mini_board):
    # two pads with copper and a paste aperture make no IC; the aperture, on GND and nearer, is no copper to be near
    r = ref_of(mini_board(part("D1", smd(1, "SIG"), smd(2, "GND", 0, 2), paste(3, "GND", 0, 1))), "D1.1")
    assert (r.rule, r.pad) == ("copper", None) and r.point == pytest.approx((0.0, -1.5), abs=1e-9)
    # the nearest pad on GND is an aperture: the pad with copper is the reference
    pads = [smd(1, "SIG"), smd(2, "GND", 0, 2, uuid="copper"), smd(3, "VDD", 4), paste(2, "GND", 0, 0.6)]
    r = ref_of(mini_board(part("U1", *pads)), "U1.1")
    assert (r.rule, r.pad, r.uuid) == ("ic", "U1.2", "copper")


def test_a_track_without_width_is_no_copper_to_be_near(mini_board):
    # it buffers to an empty shape, whose distance is NaN: it must not stay "nearest"
    b = mini_board(SIGNAL + track("F.Cu", "GND", 0, 1, 1, 1, width=0) + track("F.Cu", "GND", -5, 3, 5, 3))
    assert ref_of(b, "TP1.1").point == pytest.approx((0.0, -2.9), abs=1e-9)


@pytest.mark.parametrize("name, code", [
    ("U1.99", "E_UNKNOWN_PAD"), ("U1.2", "E_START_ON_GND"), ("U1.8", "E_START_ON_GND")])
def test_the_signal_must_be_a_pad_a_chain_may_touch(lpf, name, code):
    with pytest.raises(KrsError) as e:
        ref_of(lpf, name)
    assert e.value.code == code
