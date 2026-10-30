# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import pytest

from kicad_rf_studio import cli
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.kicad.values import parse_band
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.project import load_project, read_project
from test_antenna_kicad import fp
from test_tracer import smd

FIX = Path(__file__).parent / "fixtures"
IFA = FIX / "ifa2g4.kicad_pcb"
BANDS = {"ifa2g4": (2.4e9, 2.4835e9), "ifa2g4_pi": (2.4e9, 2.4835e9), "meander915": (902e6, 928e6)}


def antenna_project(folder: Path, board: Path = IFA, band=None) -> Path:
    """project.json of `board`'s AE1 fed from U1.1, as new_antenna writes it into `folder`."""
    return cli.new_antenna(board, "U1.1", "AE1", band or BANDS[board.stem], output=folder)[0]


def test_new_antenna_writes_schema_2(tmp_path, capsys):  # design 5.1
    code = main(["new", str(IFA), "--start", "U1.1", "--antenna", "AE1", "--band", "2400MHz:2483.5MHz",
                 "-o", str(tmp_path / "p")])
    d = read_project(tmp_path / "p" / "project.json")
    assert code == 0 and (d["schema"], d["kind"], d["band"]) == (2, "antenna", {"f_lo_hz": 2.4e9, "f_hi_hz": 2.4835e9})
    assert d["chain"] == {"start": "U1.1", "end": "AE1.1", "nets": ["RF"], "series": [], "shunt": []}
    assert [p["signal"] for p in d["ports"]] == ["U1.1"] and d["ports"][0]["reference"]["pad"] == "U1.2"
    assert (d["antenna"], d["t_max_s"]) == ({"ref": "AE1", "join": ["AE1.2"]}, 30e-9)
    assert [(q["ref"], q["role"]) for q in d["others"]] == [("C1", "copper")]  # a decoupling C, bridged (RF 4)
    out = capsys.readouterr().out
    for line in (render("I_ANTENNA", ref="AE1", feed="AE1.1", net="RF"), render("I_ANTENNA_JOIN", ref="AE1", pads="AE1.2"),
                 render("I_BAND", f_lo_mhz="2400", f_hi_mhz="2483.5", f0_mhz="2441.75", f1_mhz="1840", f2_mhz="2990"),
                 render("I_ANTENNA_DEFAULTS", preset="normal", t_max_ns="30", mesh_n=2, expand_h="6", reach_h="6",
                        air_gap_mm="31.2", boundary="pml_8", count=11, step_deg=5)):
        assert line in out
    assert "no net and is simulated as floating copper" not in out  # the antenna's copper took RF


def test_new_antenna_on_the_915_meander_and_the_pi_variant(tmp_path):  # design 5.1, 5.11
    _, notes = cli.new_antenna(FIX / "meander915.kicad_pcb", "U1.1", "AE1", (902e6, 928e6), output=tmp_path / "m")
    d = load_project(tmp_path / "m" / "project.json")
    assert (d["antenna"], d["t_max_s"], d["chain"]["nets"]) == ({"ref": "AE1", "join": []}, 79e-9, ["RF"])
    assert "I_ANTENNA_JOIN" not in [c for c, _ in notes] and notes[-1][0] == "I_WROTE"
    d = load_project(antenna_project(tmp_path / "pi", FIX / "ifa2g4_pi.kicad_pcb"))
    assert ([q["ref"] for q in d["chain"]["series"]], [q["ref"] for q in d["chain"]["shunt"]]) == (["L1"], ["C2", "C3"])


def test_new_refuses_a_module_before_writing(tmp_path, mini_board_file):  # design 5.1; RF 1
    board = mini_board_file(fp("U2", "RF_Module:ESP32-WROOM-32", smd(1, "RF")))
    with pytest.raises(KrsError) as e:
        cli.new_antenna(board, "U2.1", "U2", (2.4e9, 2.4835e9), stackup="jlcpcb-2l", output=tmp_path / "p")
    assert (e.value.code, e.value.params) == ("E_ANTENNA_MODULE", {"ref": "U2"}) and not (tmp_path / "p").exists()


@pytest.mark.parametrize(("text", "code"), [("2400MHz", "E_BAD_BAND"), ("2483.5MHz:2400MHz", "E_BAD_BAND"),
                                            ("2.4GHz:2.4GHz", "E_BAD_BAND"), ("x:2.4GHz", "E_BAD_FREQUENCY")])
def test_a_band_that_does_not_read_is_refused(text, code):  # RF 5
    with pytest.raises(KrsError) as e:
        parse_band(text)
    assert e.value.code == code
    assert parse_band(" 2400MHz : 2483.5MHz ") == (2.4e9, 2.4835e9)


def test_a_band_wider_than_an_octave_is_refused(tmp_path):  # design 3: one band a run; RF 5
    with pytest.raises(KrsError) as e:
        cli.new_antenna(IFA, "U1.1", "AE1", (868e6, 2.4835e9), output=tmp_path / "p")
    assert (e.value.code, e.value.params) == ("E_BAND_WIDE", {"f_lo_mhz": "868", "f_hi_mhz": "2483.5"})


def test_a_band_with_no_unit_is_warned(tmp_path):  # RF 5: "2400:2483.5" reads as Hz
    _, notes = cli.new_antenna(IFA, "U1.1", "AE1", (2400.0, 2483.5), output=tmp_path / "hz")
    assert ("W_F0_RANGE", {"f0_hz": "2441.75"}) in notes


def test_end_goes_with_f0_and_antenna_with_band(tmp_path, capsys):  # design 5.1
    for argv in (["--end", "AE1.1", "--band", "2.4GHz:2.5GHz"],
                 ["--antenna", "AE1", "--band", "2.4GHz:2.5GHz", "--harmonics", "3"]):  # harmonics do not apply
        assert main(["new", str(IFA), "--start", "U1.1", *argv, "-o", str(tmp_path)]) == 2
        assert render("E_NEW_KIND") in capsys.readouterr().err
