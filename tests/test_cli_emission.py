# SPDX-License-Identifier: GPL-3.0-or-later
import gettext

import pytest

from kicad_rf_studio import cli
from kicad_rf_studio.cli import main
from kicad_rf_studio.core import messages
from kicad_rf_studio.core.geometry.region import air_gap
from kicad_rf_studio.core.messages import CATALOG, KrsError, render
from kicad_rf_studio.core.model.spec import emission_pulse, emission_t_max
from kicad_rf_studio.core.project import emission_far_field_hz, read_project
from test_cli_new import FIX

LPF, COUPON = FIX / "lpf915.kicad_pcb", FIX / "coupon_gcpw_pads.kicad_pcb"
NEW = ["new", str(COUPON), "--start", "TP1.1", "--end", "TP2.1"]


def emission_project(folder, board=COUPON, start="TP1.1", end="TP2.1", **kw):
    """project.json of an emission project as new_emission writes it into `folder`, f0 915 MHz unless told."""
    return cli.new_emission(board, start, end, **({"f0": 915e6} | kw), output=folder)[0]


def test_the_emission_pulse_and_its_t_max():  # design 5.7
    exc = emission_pulse(1.83e9, 3e9)
    assert (exc["f1"], exc["f2"], exc["t_max"], exc["emission"]) == (1.40e9, 3e9, 31e-9, True)  # the probe's
    assert exc["t0"] == pytest.approx(1.7905e-9, rel=1e-4)
    assert [emission_t_max(*b) for b in ((1e9, 6e9), (1.83e9, 4.575e9), (1e9, 2.5e9), (5e8, 1.5e9))] == [
        19e-9, 22e-9, 41e-9, 69e-9]


def test_new_emission_writes_schema_4_on_the_whole_board(tmp_path):  # design 5.6, 5.7, 5.8
    d = read_project(emission_project(tmp_path / "e", LPF, "U1.1", "J1.1", lid_height=2.5))
    assert (d["schema"], d["kind"], d["f0_hz"], d["band"]) == (4, "emission", 915e6,
                                                                {"f_lo_hz": 1.83e9, "f_max_hz": 4.575e9})
    assert (d["t_max_s"], d["air_gap_mm"], d["lid"], d["near_field"]) == (22e-9, air_gap(1.83e9), True, False)
    assert d["far_field"]["f_hz"] == emission_far_field_hz(915e6, 1.83e9, 4.575e9) and "overrides" not in d
    assert [p["signal"] for p in d["ports"]] == ["U1.1", "J1.1"] and not any("R" in p for p in d["ports"])
    roles = {q["ref"]: q["role"] for q in (*d["chain"]["series"], *d["chain"]["shunt"], *d["others"])}
    assert {roles[r] for r in ("C2", "L1", "C3")} == {"port"} and roles["C4"] == "copper"  # A-27's bypass
    assert roles["R1"] == "copper"  # a 0R at its value, as v1 places it (the controller's ruling on Task 4)


def test_new_emission_with_a_band_has_no_carrier(tmp_path):  # design 5.6: --band F_LO:F_HI
    d = read_project(emission_project(tmp_path / "b", f0=None, band=(1e9, 6e9)))
    assert (d["f0_hz"], d["band"], d["t_max_s"]) == (None, {"f_lo_hz": 1e9, "f_max_hz": 6e9}, 19e-9)
    assert d["far_field"]["f_hz"] == [1e9 + 1e8 * k for k in range(51)]


@pytest.mark.parametrize("kw", [{"f0": 2.4e9, "f_max": 4.8e9}, {"f0": 3e9}, {"f0": None, "band": (3e8, 9e8)}])
def test_an_empty_emission_band_is_refused_before_anything_is_written(tmp_path, kw):  # Review Focus 1
    with pytest.raises(KrsError) as e:
        cli.new_emission(COUPON, "TP1.1", "TP2.1", **kw, output=tmp_path / "x")
    assert e.value.code == "E_EMISSION_BAND" and not (tmp_path / "x").exists()


@pytest.mark.parametrize("args", [
    ["--emission", "--band", "1GHz:6GHz", "--f-max", "3GHz"], ["--emission", "--interface", "se50"],
    ["--emission", "--f0", "915MHz", "--harmonics", "3"], ["--emission", "--f0", "915MHz", "--pair"],
    ["--emission", "--f0", "915MHz", "--target", "50"], ["--f0", "915MHz", "--review", "r.json", "--finding", "R1-0"],
    ["--emission", "--f0", "915MHz", "--review", "r.json"], ["--emission", "--f0", "915MHz", "--pitch", "1"]])
def test_new_refuses_an_emission_mix(tmp_path, capsys, args):  # design 5.6
    assert main([*NEW, *args, "-o", str(tmp_path / "x")]) == 2
    assert render("E_NEW_KIND") in capsys.readouterr().err and not (tmp_path / "x").exists()


def test_emission_with_an_antenna_is_refused(tmp_path, capsys):  # design 5.6
    assert main(["new", str(COUPON), "--start", "TP1.1", "--antenna", "TP2", "--band", "1GHz:2GHz", "--emission"]) == 2
    assert render("E_NEW_KIND") in capsys.readouterr().err


def test_the_emission_options_stay_off_the_usage_and_every_abbreviation_reads_as_before(tmp_path, capsys):  # B10
    with pytest.raises(SystemExit):
        main(["new", "--help"])
    out = capsys.readouterr().out
    assert "--band" in out and not any(o in out for o in ("--emission", "--review", "--finding", "--pitch"))
    pt = gettext.translation("kicad_rf_studio", messages.LOCALE, ["pt_BR"]).gettext(CATALOG["E_NEW_KIND"])
    assert "emiss" not in CATALOG["E_NEW_KIND"].lower() and "emiss" not in pt.lower()
    assert main(["new", str(COUPON), "--start", "TP1.1", "--e", "TP2.1", "--f0", "915MHz",
                 "-o", str(tmp_path / "v")]) == 0  # AR-16: --e is still --end alone
    assert read_project(tmp_path / "v" / "project.json")["schema"] == 1


def test_new_emission_through_main(tmp_path, capsys):  # design 5.6: --f-max with --f0
    assert main([*NEW, "--emission", "--f0", "915MHz", "--f-max", "3GHz", "-o", str(tmp_path / "e")]) == 0
    d = read_project(tmp_path / "e" / "project.json")
    assert (d["band"], d["t_max_s"]) == ({"f_lo_hz": 1.83e9, "f_max_hz": 3e9}, 31e-9)
    assert "not a compliance verdict" in capsys.readouterr().out  # I_EMISSION_DEFAULTS
