# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pytest

from kicad_rf_studio import cli
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.project import parts, read_project
from test_tracer import part, smd, track

FIX = Path(__file__).parent / "fixtures"
USB, QSPI = FIX / "usb2_hs.kicad_pcb", FIX / "qspi_clk.kicad_pcb"


def si_args(board: Path) -> tuple[tuple, dict]:
    """new_si's arguments for a fixture: a usb2_hs board's pair from J1.3 to U1.3 with the victim TP1.1:TP2.1, at
    usb2-hs; qspi_clk's net from U1.11 to U2.6, at se50."""
    if board.stem.startswith("usb2_hs"):
        return ("J1.3", "U1.3", "usb2-hs"), {"pair": True, "victims": [("TP1.1", "TP2.1")]}
    return ("U1.11", "U2.6", "se50"), {}


def si_project(folder: Path, board: Path = USB, **kw) -> Path:
    """project.json of a fixture as new_si writes it into `folder` (si_args)."""
    args, given = si_args(board)
    return cli.new_si(board, *args, **{**given, **kw}, output=folder)[0]


def test_new_interface_writes_an_si_project(tmp_path, capsys):  # design 5.1, 5.4, 5.5; Review Focus 2
    assert main(["new", str(USB), "--start", "J1.3", "--end", "U1.3", "--interface", "usb2-hs", "--pair",
                 "--victim", "TP1.1:TP2.1", "-o", str(tmp_path / "p")]) == 0
    d = read_project(tmp_path / "p" / "project.json")
    assert (d["schema"], d["kind"], d["interface"], d["dielectric"]) == (3, "si", "usb2-hs", "lossless")
    assert [(x["role"], x["chain"]["start"], x["chain"]["end"], x["chain"]["nets"]) for x in d["lines"]] == [
        ("measured", "J1.3", "U1.3", ["USB_D+", "MCU_D+"]), ("measured", "J1.2", "U1.2", ["USB_D-", "MCU_D-"]),
        ("victim", "TP1.1", "TP2.1", ["AUX"])]
    assert d["pair"] == {"p": "USB_D+", "n": "USB_D-", "by": "rule"}
    assert [(p["name"], p["signal"], p["rule"]) for p in d["ports"]] == [
        ("P1", "J1.3", "plane"), ("P2", "J1.2", "plane"), ("P3", "U1.3", "ic"), ("P4", "U1.2", "ic"),
        ("P5", "TP1.1", "plane"), ("P6", "TP2.1", "plane")]  # J1's ground pin lies past its ID pin: vertical
    assert d["ports"][0]["reference"] == {"plane": "In1.Cu"} and d["ports"][2]["reference"]["pad"] == "U1.17"
    assert [(q["ref"], q["role"]) for x in d["lines"] for q in x["chain"]["series"]] == [("R1", "port"), ("R2", "port")]
    assert [(q["ref"], q["role"]) for q in d["others"]] == [("C1", "copper")]
    assert (d["t_max_s"], d["window_s"], d["region"]["expand_h"]) == (9e-9, 2e-9, 6.0)  # 30.405 mm: the T_max floor
    assert d["mesh"]["max_cell_mm"] == pytest.approx(0.4141, abs=5e-4)  # λ/40 at 10 GHz, the 2D εeff 3.28
    out = capsys.readouterr().out
    for line in (render("I_SI_PAIR", p="USB_D+", n="USB_D-", how="T_PAIR_RULE"),
                 render("I_SI_INTERFACE", interface="usb2-hs", target="90", kind="T_DIFFERENTIAL", tolerance_pct="10",
                        rise_ps="500", marker_mhz="240", f_max_ghz="10", local_ps="125"),
                 render("I_PORT_PLANE", name="P1", signal="J1.3", layer="In1.Cu"),
                 render("I_SI_VICTIM", start="TP1.1", end="TP2.1", net="AUX"),
                 render("I_SI_DEFAULTS", preset="normal", t_max_ns="9", window_ns="2", mesh_n=2, max_cell_mm="0.414",
                        eeff="3.28", dielectric="lossless", dt_floor="0.6", reach_h="6", reach_mm="1.2")):
        assert line in out


def test_new_interface_on_the_qspi_clock(tmp_path):  # design 5.1, 5.11; Review Focus 1
    pj, notes = cli.new_si(QSPI, "U1.11", "U2.6", "se50", output=tmp_path / "q")
    d = read_project(pj)
    assert (d["pair"], [x["role"] for x in d["lines"]], d["target_ohm"], d["t_max_s"]) == (None, ["measured"], 50.0, 9e-9)
    assert [(p["signal"], p["rule"]) for p in d["ports"]] == [("U1.11", "ic"), ("U2.6", "plane")]
    assert d["lines"][0]["chain"]["shunt"] == []  # U1 has three netted pads: no part across P1's own pads
    assert [(q["ref"], q["role"]) for q in d["others"]] == [("C1", "copper")]  # in the ROI U1.17's reference widens
    assert "W_SI_LONG_PORT" not in [c for c, _ in notes]


def test_the_partner_given_by_pair_with(tmp_path):  # design 5.1
    d = read_project(cli.new_si(USB, "J1.3", "U1.3", "usb2-hs", pair_with=("J1.2", "U1.2"), output=tmp_path / "w")[0])
    assert d["pair"]["by"] == "given" and [p["signal"] for p in d["ports"]] == ["J1.3", "J1.2", "U1.3", "U1.2"]


def test_a_line_on_a_net_another_line_holds_is_refused(tmp_path):  # the lines ruling: no third end on a line
    for kw in ({"pair_with": ("J1.3", "U1.3")}, {"pair": True, "victims": [("J1.2", "U1.2")]}):
        with pytest.raises(KrsError) as e:
            cli.new_si(USB, "J1.3", "U1.3", "usb2-hs", output=tmp_path / "s", **kw)
        assert e.value.code == "E_SI_LINE_SHARED" and not (tmp_path / "s").exists()
    assert e.value.params == {"start": "J1.2", "end": "U1.2", "net": "USB_D-"}


def test_a_part_on_both_legs_is_stored_once(mini_board_file, tmp_path):  # the lines ruling: kept by the first
    def ends(ref, at):  # D+, D- and a ground pad each side of them, nothing between a pad and its ground
        return part(ref, smd(1, "D+"), smd(2, "D-", y=2), smd(3, "GND", y=-2), smd(4, "GND", y=4), at=at)
    board = mini_board_file(ends("J1", "0 0") + ends("U1", "20 0") + part("R9", smd(1, "D+"), smd(2, "D-", y=2),
                                                                         at="10 0") +
                            track("F.Cu", "D+", 0, 0, 20, 0) + track("F.Cu", "D-", 0, 2, 20, 2))
    pj, notes = cli.new_si(board, "J1.1", "U1.1", "custom", pair=True, f_max=5e9, target=100.0,
                           stackup="kicad-default", output=tmp_path / "r")
    d = read_project(pj)
    assert [[q["ref"] for q in x["chain"]["shunt"]] for x in d["lines"]] == [["R9"], []] and list(parts(d)) == ["R9"]
    assert [p["shunt"] for code, p in notes if code == "I_CHAIN"] == ["R9", "R9"]


def test_a_long_port_is_warned(tmp_path):  # plan 1's open issue 2; Review Focus 2
    _, notes = cli.new_si(QSPI, "U1.11", "U2.6", "custom", f_max=100e9, target=50.0, output=tmp_path / "t")
    assert [(p["name"], p["length_mm"], p["limit_mm"]) for c, p in notes if c == "W_SI_LONG_PORT"] == [
        ("P1", "0.200", "0.071"), ("P2", "0.200", "0.071")]  # U1.11 to U1.17 across, U2.6 down to In1.Cu


def mini(mini_board_file, victim=""):
    line = part("A1", smd(1, "SIG")) + part("A2", smd(1, "SIG"), at="10 0") + track("F.Cu", "SIG", 0, 0, 10, 0)
    return mini_board_file(line + victim)


def test_an_end_with_no_reference_and_no_plane_is_refused(mini_board_file, tmp_path):  # design 5.5; RF 2
    with pytest.raises(KrsError) as e:
        cli.new_si(mini(mini_board_file), "A1.1", "A2.1", "se50", stackup="kicad-default", output=tmp_path / "p")
    assert (e.value.code, e.value.params) == ("E_SI_NO_REFERENCE", {"pad": "A1.1", "layer": "F.Cu", "reach_mm": "4.26"})
    assert not (tmp_path / "p").exists()


def test_a_victim_outside_the_measured_lines_region_is_refused(mini_board_file, tmp_path):  # design 5.1
    victim = part("B1", smd(1, "V"), at="0 30") + part("B2", smd(1, "V"), at="10 30") + track("F.Cu", "V", 0, 30, 10, 30)
    with pytest.raises(KrsError) as e:
        cli.new_si(mini(mini_board_file, victim), "A1.1", "A2.1", "se50", victims=[("B1.1", "B2.1")],
                   stackup="kicad-default", output=tmp_path / "p")
    assert (e.value.code, e.value.params) == ("E_SI_VICTIM_OUTSIDE", {"victim": "B1.1:B2.1", "pad": "B1.1",
                                                                      "reach_mm": "4.26"})
    with pytest.raises(KrsError) as e:
        cli.new_si(USB, "J1.3", "U1.3", "usb2-hs", pair=True, victims=[("TP1.1", "TP2.1")] * 3, output=tmp_path / "v")
    assert (e.value.code, e.value.params) == ("E_SI_VICTIMS", {"count": 3})
