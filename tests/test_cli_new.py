# SPDX-License-Identifier: GPL-3.0-or-later
import io
import os
import re
import sys
from pathlib import Path

import pytest

import kicad_rf_studio.cli as cli
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.kicad import choose_reference, classify, load_board
from kicad_rf_studio.core.kicad.sexpr import child, children, parse
from kicad_rf_studio.core.kicad.tracer import Classes
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.project import board_file, board_hash, load_project, read_project, save_project
from kicad_rf_studio.pipeline import build_model, load
from test_cli_cost import EDGE, SEG
from test_geometry_sections import four_layer

FIX = Path(__file__).parent / "fixtures"
LPF = FIX / "lpf915.kicad_pcb"
# spec 3.2: `new` prints every value it assumed
DEFAULTS = ("Preset normal (provisional default), band factor 1.1, T_max 40 ns, harmonics 3, mesh n 2, "
            "region 3 substrate heights past the chain, margin scale 1, protected reach 6 substrate heights.")
KEYS = {"schema", "board", "f0_hz", "harmonics", "preset", "band_factor", "t_max_s", "region", "mesh", "stackup",
        "lid_height_mm", "lid", "classes", "chain", "others", "ports", "gates", "allow_curve_port"}


def run_new(tmp_path, *extra, board="lpf915.kicad_pcb", start="U1.1", end="J1.1", out=None):
    out = out or tmp_path / "proj"
    code = main(["new", str(FIX / board), "--start", start, "--end", end, "--f0", "915MHz", "-o", str(out), *extra])
    return code, out / "project.json"


def test_new_writes_project(tmp_path, capsys):
    code, pj = run_new(tmp_path, "--lid-height", "2.5")
    assert code == 0
    d = load_project(pj)
    assert (d["schema"], d["f0_hz"], d["harmonics"], d["preset"], d["band_factor"]) == (1, 915e6, 3, "normal", 1.1)
    assert d["t_max_s"] == pytest.approx(40e-9) and d["lid_height_mm"] == 2.5
    assert [p["ref"] for p in d["chain"]["series"]] == ["C1", "L1", "R1"]
    assert [p["signal"] for p in d["ports"]] == ["U1.1", "J1.1"] and d["stackup"]["source"] == "board"
    # The board path is relative when the project folder and the board share a drive. A CI runner may keep its temp
    # folder on another drive than the checkout, and there the path is absolute (see the cross-drive test below).
    same_drive = os.path.splitdrive(pj.resolve())[0] == os.path.splitdrive(FIX.resolve())[0]
    assert Path(d["board"]["path"]).is_absolute() != same_drive and len(d["board"]["sha256"]) == 64
    out = capsys.readouterr().out
    assert "Fills as saved" in out and "U1.2" in out


def test_new_warns_about_missing_lid_height(tmp_path, capsys):
    code, _ = run_new(tmp_path)
    assert code == 0 and "--lid-height" in capsys.readouterr().out


def test_new_refuses_board_without_stackup(tmp_path, capsys, mini_board_file):
    code = main(["new", str(mini_board_file("")), "--start", "A.1", "--end", "B.1", "--f0", "915MHz",
                 "-o", str(tmp_path / "p")])
    assert code == 2 and "--stackup" in capsys.readouterr().err


def test_single_trace_project(tmp_path):
    code, pj = run_new(tmp_path, board="coupon_gcpw_pads.kicad_pcb", start="TP1.1", end="TP2.1")
    d = load_project(pj)
    assert code == 0 and d["chain"]["series"] == [] and d["ports"][1]["rule"] == "copper"


def test_project_path_with_spaces_and_accents(tmp_path):
    out = tmp_path / "pasta com espaço" / "projeto ação"
    code, pj = run_new(tmp_path, out=out)
    d = load_project(pj)
    assert code == 0 and (out / d["board"]["path"]).resolve() == (FIX / "lpf915.kicad_pcb").resolve()


def test_unknown_pad_exit_code(tmp_path, capsys):
    code, _ = run_new(tmp_path, start="U1.99")
    assert code == 2 and "U1." in capsys.readouterr().err


def test_cli_survives_a_cp1252_console(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    code, _ = run_new(tmp_path, "--lid-height", "2.5")
    assert code == 0


# --- beyond the brief's tests: the project file, the printed summary and the rulings ------------------------
# --- what is written ------------------------------------------------------------------------------------------


def test_project_layout(tmp_path):
    code, pj = run_new(tmp_path, "--lid-height", "2.5")
    d, board = load_project(pj), load_board(LPF)
    assert code == 0
    assert set(d) == KEYS
    assert set(d["board"]) == {"path", "sha256"} and d["board"]["sha256"] == board_hash(LPF)
    assert d["stackup"] == board.stackup.to_json()
    m0402 = {"package": "0402", "esl_h": 5e-10, "esr_ohm": 0.1, "cp_f": 3e-14}
    assert d["chain"] == {
        "start": "U1.1", "end": "J1.1", "nets": ["RF_A", "RF_B", "RF_C", "RF_OUT"],
        "series": [
            {"ref": "C1", "pads": ["C1.1", "C1.2"], "nets": ["RF_A", "RF_B"], "value": "100pF", "dnp": False,
             "role": "port", "model": m0402, "s2p": None},
            {"ref": "L1", "pads": ["L1.1", "L1.2"], "nets": ["RF_B", "RF_C"], "value": "15nH", "dnp": False,
             "role": "port", "model": m0402, "s2p": None},
            {"ref": "R1", "pads": ["R1.1", "R1.2"], "nets": ["RF_C", "RF_OUT"], "value": "0R", "dnp": False,
             "role": "copper", "model": m0402, "s2p": None}],
        "shunt": [
            {"ref": "C2", "pads": ["C2.1", "C2.2"], "nets": ["RF_B", "GND"], "value": "3.3pF", "dnp": False,
             "role": "port", "model": m0402, "s2p": None},
            {"ref": "C3", "pads": ["C3.1", "C3.2"], "nets": ["RF_C", "GND"], "value": "3.3pF", "dnp": False,
             "role": "port", "model": m0402, "s2p": None},
            {"ref": "R2", "pads": ["R2.1", "R2.2"], "nets": ["RF_OUT", "RF_SMA"], "value": "0R", "dnp": True,
             "role": "open", "model": m0402, "s2p": None}]}
    assert d["others"] == [  # VDD's decoupling capacitor, in the region but on no chain net
        {"ref": "C4", "pads": ["C4.1", "C4.2"], "nets": ["VDD", "GND"], "value": "10uF/16V", "dnp": False,
         "role": "open", "model": {"package": "0603", "esl_h": 7e-10, "esr_ohm": 0.1, "cp_f": 5e-14},
         "s2p": None}]
    assert d["ports"] == [  # a port records the pad it resolved: a number can repeat in a footprint
        {"name": "P1", "signal": "U1.1", "signal_uuid": board.pads("U1.1")[0].uuid, "layer": "F.Cu", "rule": "ic",
         "reference": {"pad": "U1.2", "uuid": board.pads("U1.2")[0].uuid}},
        {"name": "P2", "signal": "J1.1", "signal_uuid": board.pads("J1.1")[0].uuid, "layer": "F.Cu",
         "rule": "connector", "reference": {"pad": "J1.2", "uuid": board.pads("J1.2")[0].uuid}}]


def test_lid_height_is_null_until_given(tmp_path):
    _, pj = run_new(tmp_path)
    assert load_project(pj)["lid_height_mm"] is None


def test_options_reach_the_project_and_the_summary(tmp_path, capsys):
    out = tmp_path / "proj"
    code = main(["new", str(LPF), "--start", "U1.1", "--end", "J1.1", "--f0", "2.4GHz", "--harmonics", "5",
                 "--preset", "strict", "-o", str(out)])
    d = load_project(out / "project.json")
    assert code == 0 and (d["f0_hz"], d["harmonics"], d["preset"]) == (2.4e9, 5, "strict")
    lines = capsys.readouterr().out.splitlines()
    assert "f0 2400 MHz, with 5 harmonics." in lines
    assert ("Preset strict (provisional default), band factor 1.1, T_max 40 ns, harmonics 5, mesh n 3, "
            "region 3 substrate heights past the chain, margin scale 1, protected reach 6 substrate heights.") in lines


def test_classes_are_the_computed_sets(tmp_path):
    _, pj = run_new(tmp_path)
    assert load_project(pj)["classes"] == {
        "gnd_nets": ["GND"], "power_nets": ["VDD"], "connectors": ["J1", "J2"], "shields": ["SH1"]}
    # a set that is empty on this board is an empty list: classify() reads it back as "none", as computed
    _, pj = run_new(tmp_path, board="coupon_gcpw_pads.kicad_pcb", start="TP1.1", end="TP2.1", out=tmp_path / "c")
    assert load_project(pj)["classes"] == {"gnd_nets": ["GND"], "power_nets": [], "connectors": [], "shields": []}


class Descending(frozenset):
    """A frozenset that iterates from the largest member down, so that a list made without sorted() shows it."""

    def __iter__(self):
        return iter(sorted(frozenset.__iter__(self), reverse=True))


def test_classes_are_written_sorted(tmp_path, monkeypatch):
    real = cli.classify

    def descending(board, overrides=None):
        c = real(board, overrides)
        return Classes(*(Descending(s) for s in (c.gnd, c.power, c.connectors, c.shields)))

    monkeypatch.setattr(cli, "classify", descending)
    _, pj = run_new(tmp_path)
    assert load_project(pj)["classes"]["connectors"] == ["J1", "J2"]


def test_a_copper_reference_is_a_point_on_a_layer(tmp_path, capsys):
    code, pj = run_new(tmp_path, board="coupon_gcpw_pads.kicad_pcb", start="TP1.1", end="TP2.1")
    d, board = load_project(pj), load_board(FIX / "coupon_gcpw_pads.kicad_pcb")
    assert code == 0
    for port, pad in zip(d["ports"], ("TP1.1", "TP2.1")):
        x, y = choose_reference(board, classify(board), pad).point  # y up, as the board is read
        assert port["rule"] == "copper" and port["reference"] == {"point": [x, -y], "layer": "F.Cu"}
    out = capsys.readouterr().out
    assert re.search(r"Port P1: signal TP1\.1, reference \(-?\d+\.\d{3}, -?\d+\.\d{3}\) on F\.Cu \(copper\)\.", out)
    assert "GND nets: GND. Power nets: none. Connectors: none. Shields: none." in out
    assert "Chain TP1.1 → TP2.1: series none; shunt none." in out


def test_a_reference_point_is_stored_and_shown_in_kicads_frame(tmp_path, capsys):
    """KiCad's y points down. The point keeps the sign of y the file gives TP1, (at 100 100), as KiCad shows it."""
    code, pj = run_new(tmp_path, board="coupon_gcpw_pads.kicad_pcb", start="TP1.1", end="TP2.1")
    root = parse((FIX / "coupon_gcpw_pads.kicad_pcb").read_text(encoding="utf-8"))
    tp1 = next(f for f in children(root, "footprint")
               if ["Reference", "TP1"] in (p[1:3] for p in children(f, "property")))
    file_y = float(child(tp1, "at")[2])
    x, y = load_project(pj)["ports"][0]["reference"]["point"]
    assert code == 0 and y * file_y > 0 and abs(y - file_y) < 1  # the same sign, and less than 1 mm off the pad
    assert f"Port P1: signal TP1.1, reference ({x:.3f}, {y:.3f}) on F.Cu (copper)." in capsys.readouterr().out


def test_a_reference_point_on_the_x_axis_is_not_minus_zero(tmp_path, mini_board_file):
    pts = "(pts (xy 2 -1) (xy 5 -1) (xy 5 1) (xy 2 1))"  # GND copper whose nearest point to the pads is (2, 0)
    pour = f'(zone (net "GND") (layer "F.Cu") (uuid "z") (polygon {pts}) (filled_polygon (layer "F.Cu") {pts}))'
    board = mini_board_file(footprint("TP1", pad(1, "SIG")) + footprint("TP2", pad(1, "SIG", x=-5)) + pour)
    out = tmp_path / "p"
    code = main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "--stackup", "jlcpcb-2l",
                 "-o", str(out)])
    text = (out / "project.json").read_text(encoding="utf-8")
    assert code == 0 and load_project(out / "project.json")["ports"][0]["reference"]["point"] == [2, 0]
    assert "-0.0" not in text


# --- where it is written --------------------------------------------------------------------------------------


def test_without_o_the_project_goes_to_the_working_directory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = main(["new", str(LPF), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz"])
    assert code == 0 and (tmp_path / "project.json").is_file()
    assert board_file(tmp_path / "project.json", load_project(tmp_path / "project.json")) == LPF.resolve()
    assert capsys.readouterr().out.splitlines()[-1] == "Wrote project.json."


def test_o_is_a_folder_and_its_parents_are_created(tmp_path):
    out = tmp_path / "a" / "b" / "c"
    code, pj = run_new(tmp_path, out=out)
    assert code == 0 and pj == out / "project.json" and pj.is_file()
    assert [p.name for p in out.iterdir()] == ["project.json"]


def test_running_again_refuses_and_keeps_the_project_as_it_is(tmp_path, capsys):
    _, pj = run_new(tmp_path)
    first = pj.read_bytes()
    capsys.readouterr()
    code, _ = run_new(tmp_path, "--lid-height", "2.5")  # another option: an overwrite would change the bytes
    out, err = capsys.readouterr()
    assert code == 2 and pj.read_bytes() == first
    assert (out, err) == ("", f"{pj} already exists. Delete it, or give another -o folder.\n")


def test_the_board_path_has_forward_slashes(tmp_path):
    _, pj = run_new(tmp_path, out=tmp_path / "x" / "y")
    assert "\\" not in load_project(pj)["board"]["path"]


def test_a_board_on_another_drive_is_stored_with_its_absolute_path(tmp_path, monkeypatch, capsys):
    def another_drive(path, start):
        raise ValueError("path is on mount 'A:', start on mount 'B:'")

    monkeypatch.setattr(os.path, "relpath", another_drive)
    code, pj = run_new(tmp_path)
    d = load_project(pj)
    assert code == 0 and d["board"]["path"] == LPF.absolute().as_posix()
    assert board_file(pj, d) == LPF.resolve()
    assert "The board is on another drive, so project.json stores its absolute path." in capsys.readouterr().out


@pytest.mark.parametrize("kw", [{"start": "U1.99"}, {"end": "J2.1"}])  # an unknown pad; a DNP part in the way
def test_a_failed_run_writes_nothing(tmp_path, kw):
    code, pj = run_new(tmp_path, **kw)
    assert code == 2 and not pj.parent.exists()


# --- what is printed ------------------------------------------------------------------------------------------


def test_the_printed_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(os.path, "relpath", lambda path, start: "lpf915.kicad_pcb")  # no cross-drive line
    code, pj = run_new(tmp_path, "--lid-height", "2.5")
    out, err = capsys.readouterr()
    assert code == 0 and err == ""
    assert out.splitlines() == [
        "Fills as saved — refill (B) in KiCad and save if you changed copper.",
        "Stackup: board, dielectric 0.71 mm, εr 4.5; mask 0.01 mm, εr 3.3.",
        "GND nets: GND. Power nets: VDD. Connectors: J1, J2. Shields: SH1.",
        "Chain U1.1 → J1.1: series C1, L1, R1; shunt C2, C3, R2.",
        "Part C1 100pF: port; package 0402, ESL 0.5 nH, ESR 0.1 Ω.",
        "Part L1 15nH: port; package 0402, ESL 0.5 nH, ESR 0.1 Ω.",
        "Part R1 0R: copper; package 0402, ESL 0.5 nH, ESR 0.1 Ω.",
        "Part C2 3.3pF: port; package 0402, ESL 0.5 nH, ESR 0.1 Ω.",
        "Part C3 3.3pF: port; package 0402, ESL 0.5 nH, ESR 0.1 Ω.",
        "Part R2 0R: open; package 0402, ESL 0.5 nH, ESR 0.1 Ω.",
        "Part C4 10uF/16V: open; package 0603, ESL 0.7 nH, ESR 0.1 Ω.",
        "Port P1: signal U1.1, reference U1.2 (ic).",
        "Port P2: signal J1.1, reference J1.2 (connector).",
        "f0 915 MHz, with 3 harmonics.",
        DEFAULTS,
        render("I_LID", state="on"),
        render("W_PART_OPEN", refs="C4"),
        f"Wrote {pj}."]


def test_a_bare_f0_is_hertz_and_is_warned(tmp_path, capsys):
    code = main(["new", str(LPF), "--start", "U1.1", "--end", "J1.1", "--f0", "915", "-o", str(tmp_path / "p")])
    lines = capsys.readouterr().out.splitlines()
    assert code == 0 and load_project(tmp_path / "p" / "project.json")["f0_hz"] == 915
    assert "f0 0.000915 MHz, with 3 harmonics." in lines
    assert "f0 = 915 Hz is outside 1 MHz to 100 GHz. Did you forget the unit, as in 915MHz?" in lines


@pytest.mark.parametrize("f0, shown, warned", [
    ("999.999kHz", "0.999999", True), ("1MHz", "1", False), ("100GHz", "100000", False),
    ("100.1GHz", "100100", True)])
def test_f0_is_warned_outside_1_mhz_to_100_ghz(tmp_path, capsys, f0, shown, warned):
    code = main(["new", str(LPF), "--start", "U1.1", "--end", "J1.1", "--f0", f0, "-o", str(tmp_path / "p")])
    lines = capsys.readouterr().out.splitlines()
    assert code == 0 and f"f0 {shown} MHz, with 3 harmonics." in lines
    assert any(" Hz is outside 1 MHz to 100 GHz." in line for line in lines) is warned


NO_MASK = ('(stackup (layer "F.Cu" (type "copper") (thickness 0.035)) '
           '(layer "dielectric 1" (type "core") (thickness 0.73) (epsilon_r 4.4)) '
           '(layer "B.Cu" (type "copper") (thickness 0.035)))')


def test_a_stackup_without_a_mask_shows_none_for_it(tmp_path, capsys, mini_board_file):
    board = mini_board_file(footprint("TP1", pad(1, "SIG")) + footprint("TP2", pad(1, "SIG", x=5)), stackup=NO_MASK)
    code = main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    assert code == 0 and "Stackup: board, dielectric 0.73 mm, εr 4.4; mask none mm, εr none." in (
        capsys.readouterr().out.splitlines())


def test_the_lid_warning_names_the_shield(tmp_path, capsys):
    run_new(tmp_path)
    assert render("W_LID_HEIGHT_MISSING", refs="SH1") in capsys.readouterr().out.splitlines()


@pytest.mark.parametrize("board, start, end, extra, warned", [
    ("lpf915.kicad_pcb", "U1.1", "J1.1", [], True),
    ("lpf915.kicad_pcb", "U1.1", "J1.1", ["--lid-height", "2.5"], False),  # the height is given
    ("coupon_gcpw_pads.kicad_pcb", "TP1.1", "TP2.1", [], False)])  # no shield, so no lid
def test_the_lid_warning_needs_a_shield_and_no_height(tmp_path, capsys, board, start, end, extra, warned):
    code, _ = run_new(tmp_path, *extra, board=board, start=start, end=end)
    assert code == 0 and ("--lid-height" in capsys.readouterr().out) is warned


def test_heavy_copper_is_warned_between_the_defaults_and_the_lid(tmp_path, capsys):
    text = LPF.read_text(encoding="utf-8")
    assert text.count("(thickness 0.035)") == 2  # the fixture's F.Cu and B.Cu
    heavy = tmp_path / "heavy.kicad_pcb"
    heavy.write_text(text.replace("(thickness 0.035)", "(thickness 0.07)", 1), encoding="utf-8")
    code = main(["new", str(heavy), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    lines = capsys.readouterr().out.splitlines()
    n = next(i for i, line in enumerate(lines) if line.startswith("Copper layers F.Cu are not 35"))
    assert code == 0 and lines[n - 1] == render("I_LID", state="on")
    assert lines[n + 1] == render("W_LID_HEIGHT_MISSING", refs="SH1")
    assert not any("Copper layers" in line for line in lines[:n] + lines[n + 1:])


def with_values(tmp_path, **values):
    """A copy of lpf915 where the footprint of each keyword's reference has that Value."""
    text = LPF.read_text(encoding="utf-8")
    for ref, value in values.items():
        start = text.index('(property "Value" "', text.index(f'(property "Reference" "{ref}"')) + 19
        text = text[:start] + value + text[text.index('"', start):]
    board = tmp_path / "values.kicad_pcb"
    board.write_text(text, encoding="utf-8")
    return board


def test_a_part_value_that_cannot_be_read_is_warned(tmp_path, capsys):
    board = with_values(tmp_path, C2="3.3.3pF")  # C3 has the same value, and comes first in the file
    out = tmp_path / "p"
    code = main(["new", str(board), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "-o", str(out)])
    warned = [line for line in capsys.readouterr().out.splitlines() if line.startswith("Cannot read the value")]
    assert code == 0 and warned == ["Cannot read the value of C2. Write values like 4.7pF, 4p7 or 15nH."]
    shunt = load_project(out / "project.json")["chain"]["shunt"]
    assert [p["value"] for p in shunt] == ["3.3.3pF", "3.3pF", "0R"]  # kept as written


def test_unreadable_values_are_one_warning_for_series_shunt_and_dnp_parts(tmp_path, capsys):
    # L1 is a series part, R2 a DNP shunt part; C4, a decoupling capacitor on VDD, is an `others` part
    board = with_values(tmp_path, R2="TBD", L1="", C2="3,3pF", C4="??")  # C2's decimal comma reads
    code = main(["new", str(board), "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    warned = [line for line in capsys.readouterr().out.splitlines() if line.startswith("Cannot read the value")]
    assert code == 0 and warned == ["Cannot read the value of C4, L1, R2. Write values like 4.7pF, 4p7 or 15nH."]


def pad(number, net, x=0.0):
    return f'(pad "{number}" smd rect (at {x} 0) (size 1 1) (layers "F.Cu") (net "{net}"))'


def footprint(ref, *pads):
    return (f'(footprint "Lib:{ref}" (layer "F.Cu") (uuid "f-{ref}") (at 0 0) (property "Reference" "{ref}") '
            f'(property "Value" "x") {"".join(pads)})')


def test_ports_without_a_reference(tmp_path, capsys, mini_board_file):
    """Two pads on one net and no ground anywhere: a single trace whose ports have nothing to refer to."""
    board = mini_board_file(footprint("TP1", pad(1, "SIG")) + footprint("TP2", pad(1, "SIG", x=5)))
    out = tmp_path / "p"
    code = main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "--stackup", "jlcpcb-2l",
                 "-o", str(out)])
    d, (printed, err) = load_project(out / "project.json"), capsys.readouterr()
    assert code == 0 and err == ""
    assert d["ports"] == [  # these pads have no uuid in the file
        {"name": "P1", "signal": "TP1.1", "signal_uuid": "", "layer": "F.Cu", "rule": None, "reference": None},
        {"name": "P2", "signal": "TP2.1", "signal_uuid": "", "layer": "F.Cu", "rule": None, "reference": None}]
    assert d["chain"] == {"start": "TP1.1", "end": "TP2.1", "nets": ["SIG"], "series": [], "shunt": []}
    assert d["lid_height_mm"] is None and d["stackup"]["source"] == "jlcpcb-2l"
    assert printed.splitlines() == [
        "The board has no Edge.Cuts outline, so the substrate is not clipped.",
        "Fills as saved — refill (B) in KiCad and save if you changed copper.",
        "Stackup: jlcpcb-2l, dielectric 0.69952 mm, εr 4.5; mask 0.01524 mm, εr 3.8.",
        "GND nets: none. Power nets: none. Connectors: none. Shields: none.",
        "Chain TP1.1 → TP2.1: series none; shunt none.",
        "Port P1: signal TP1.1, reference none (none).",
        "Port P2: signal TP2.1, reference none (none).",
        "f0 915 MHz, with 3 harmonics.",
        DEFAULTS,
        render("I_LID", state="on"),
        "No reference found for TP1.1; set it in project.json before `run`.",
        "No reference found for TP2.1; set it in project.json before `run`.",
        f"Wrote {out / 'project.json'}."]


# --- the stackup ----------------------------------------------------------------------------------------------


def test_the_stackup_option_replaces_the_boards_own(tmp_path, capsys):
    code, pj = run_new(tmp_path, "--stackup", "jlcpcb-2l")
    d = load_project(pj)
    assert code == 0 and d["stackup"]["source"] == "jlcpcb-2l"
    assert [x["name"] for x in d["stackup"]["layers"]] == ["F.Mask", "F.Cu", "dielectric 1", "B.Cu", "B.Mask"]
    assert "Stackup: jlcpcb-2l, dielectric 0.69952 mm, εr 4.5; mask 0.01524 mm, εr 3.8." in capsys.readouterr().out


def test_the_dielectric_thickness_is_shown_without_float_noise(tmp_path, capsys):
    code, pj = run_new(tmp_path, "--stackup", "kicad-default")  # 0.8 - 2 x (0.035 + 0.01) is 0.7100000000000001
    assert code == 0 and "Stackup: kicad-default, dielectric 0.71 mm, εr 4.5; mask 0.01 mm, εr 3.3." in (
        capsys.readouterr().out)


@pytest.mark.parametrize("name", ["nope", ""])  # an empty name is not "no --stackup"
def test_an_unknown_stackup_preset(tmp_path, capsys, name):
    code, _ = run_new(tmp_path, "--stackup", name)
    assert code == 2
    assert capsys.readouterr().err == f'Unknown stackup preset "{name}". Known presets: kicad-default, jlcpcb-2l.\n'


def test_the_stackup_preset_gets_the_boards_copper_layer_count(tmp_path, capsys, mini_board_file):
    board = mini_board_file("")
    three = board.read_text(encoding="utf-8").replace('(2 "B.Cu" signal)', '(2 "B.Cu" signal) (4 "In1.Cu" signal)')
    board.write_text(three, encoding="utf-8")
    code = main(["new", str(board), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "--stackup", "jlcpcb-2l",
                 "-o", str(tmp_path / "p")])
    assert code == 2 and "this board has 3" in capsys.readouterr().err


ZERO_DIELECTRIC = ('(stackup (layer "F.Cu" (type "copper") (thickness 0.035)) '
                   '(layer "dielectric 1" (type "core") (thickness 0)) '
                   '(layer "B.Cu" (type "copper") (thickness 0.035)))')


def test_a_stackup_with_no_dielectric_is_refused(tmp_path, capsys, mini_board_file):
    code = main(["new", str(mini_board_file("", stackup=ZERO_DIELECTRIC)), "--start", "A.1", "--end", "B.1",
                 "--f0", "915MHz", "-o", str(tmp_path / "p")])
    assert code == 2 and "The board has no stackup" in capsys.readouterr().err


def test_a_preset_that_leaves_no_dielectric_is_refused(tmp_path, capsys, mini_board_file):
    board = mini_board_file("")  # 0.05 mm: 2 x (35 um copper + 10 um mask) leave less than nothing
    board.write_text(board.read_text(encoding="utf-8").replace("(thickness 0.8)", "(thickness 0.05)"), encoding="utf-8")
    code = main(["new", str(board), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "--stackup", "kicad-default",
                 "-o", str(tmp_path / "p")])
    assert code == 2 and "The board has no stackup" in capsys.readouterr().err


# --- exit codes and error text --------------------------------------------------------------------------------


def test_a_bad_frequency_is_a_user_error(tmp_path, capsys):
    code = main(["new", str(LPF), "--start", "U1.1", "--end", "J1.1", "--f0", "fast", "-o", str(tmp_path / "p")])
    assert code == 2 and capsys.readouterr().err == 'Cannot read the frequency "fast". Write it like 915MHz.\n'


def test_a_missing_board_is_a_user_error(tmp_path, capsys):
    board = tmp_path / "nope.kicad_pcb"
    code = main(["new", str(board), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    assert code == 2 and capsys.readouterr().err == (
        f"Cannot read the board {board}: file not found. "
        "Check the path, or open the board in KiCad and save it again.\n")


def test_a_board_that_is_not_utf8_is_a_short_user_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # a relative path keeps the message's length independent of the temp folder
    (tmp_path / "latin1.kicad_pcb").write_bytes(LPF.read_bytes().replace(b'"SHIELD"', b'"SHIELD\xe9"', 1))
    code = main(["new", "latin1.kicad_pcb", "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "-o", "p"])
    err = capsys.readouterr().err
    assert code == 2 and err == ("Cannot read the board latin1.kicad_pcb: not UTF-8 text. "
                                 "Check the path, or open the board in KiCad and save it again.\n")
    assert len(err) < 300  # not the board itself, which the repr of a UnicodeDecodeError would print
    assert not (tmp_path / "p").exists()


def test_another_kicad_file_is_a_user_error(tmp_path, capsys):
    schematic = tmp_path / "x.kicad_sch"; schematic.write_text("(kicad_sch (version 20250114))", encoding="utf-8")
    code = main(["new", str(schematic), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    assert code == 2 and "x.kicad_sch is not a KiCad board file." in capsys.readouterr().err


def test_a_kicad_project_file_is_not_a_board(tmp_path, capsys):
    pro = tmp_path / "x.kicad_pro"; pro.write_text('{\n  "board": {}\n}\n', encoding="utf-8")
    code = main(["new", str(pro), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    assert code == 2 and capsys.readouterr().err == f"{pro} is not a KiCad board file.\n"


def test_an_output_folder_that_is_a_file_is_a_user_error(tmp_path, capsys):
    taken = tmp_path / "taken"; taken.write_bytes(b"x")
    code, _ = run_new(tmp_path, out=taken)
    assert code == 2 and capsys.readouterr().err == (
        f"Cannot write {taken}: already exists as a file. Choose another -o folder.\n")
    assert taken.read_bytes() == b"x"


def test_a_project_file_that_cannot_be_written_is_a_user_error(tmp_path, monkeypatch, capsys):
    def denied(path, data):
        raise PermissionError(13, "the system's own words, never shown", str(path))

    monkeypatch.setattr(cli, "save_project", denied)
    code, pj = run_new(tmp_path)
    assert code == 2 and capsys.readouterr().err == f"Cannot write {pj}: permission denied. Choose another -o folder.\n"


def test_a_malformed_board_is_an_internal_error(tmp_path, capsys, mini_board_file):
    board = mini_board_file('(segment (end 1 1) (width 0.2) (layer "F.Cu") (net "A"))')  # no (start ...)
    code = main(["new", str(board), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    out, err = capsys.readouterr()
    assert code == 1 and out == ""
    assert err.startswith("Internal error: TypeError: ") and err.endswith(". Please report it.\n")
    assert len(err.splitlines()) == 1


class Chatty(Exception):
    def __str__(self):
        return "first\n    second\n"


def test_the_internal_error_is_one_line(tmp_path, monkeypatch, capsys):
    def boom(path):
        raise Chatty()

    monkeypatch.setattr(cli, "load_board", boom)
    code, _ = run_new(tmp_path)
    assert code == 1 and capsys.readouterr().err == "Internal error: Chatty: first second. Please report it.\n"


def test_the_internal_error_is_cut_to_200_characters(tmp_path, monkeypatch, capsys):
    def boom(path):
        raise ValueError("x" * 1000)

    monkeypatch.setattr(cli, "load_board", boom)
    code, _ = run_new(tmp_path)
    detail = "ValueError: " + "x" * 187 + "…"  # 200 characters
    assert code == 1 and capsys.readouterr().err == f"Internal error: {detail}. Please report it.\n"


@pytest.mark.parametrize("extra", [
    [],  # no command
    ["new"],  # no board
    ["new", "b.kicad_pcb", "--end", "J1.1", "--f0", "915MHz"],  # no --start
    ["new", "b.kicad_pcb", "--start", "U1.1", "--end", "J1.1"],  # no --f0
    ["new", "b.kicad_pcb", "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", "--preset", "fast"],
    *(["new", "b.kicad_pcb", "--start", "U1.1", "--end", "J1.1", "--f0", "915MHz", flag, value]
      for flag, value in [("--harmonics", "0"), ("--harmonics", "-2"), ("--harmonics", "two"),
                          ("--lid-height", "0"), ("--lid-height", "-2.5"), ("--lid-height", "nan"),
                          ("--lid-height", "inf"), ("--lid-height", "tall")])])
def test_a_usage_error_exits_2(extra, capsys):
    with pytest.raises(SystemExit) as e:
        main(extra)
    assert e.value.code == 2 and "usage:" in capsys.readouterr().err


def test_main_reads_sys_argv_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["kicad-rf-studio", "new", str(LPF), "--start", "U1.1", "--end", "J1.1",
                                      "--f0", "915MHz", "-o", str(tmp_path / "p")])
    assert main() == 0 and (tmp_path / "p" / "project.json").is_file()


# --- the console ----------------------------------------------------------------------------------------------


def test_unencodable_characters_become_question_marks_on_stdout(tmp_path, monkeypatch):
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)
    code, _ = run_new(tmp_path)
    console.flush()
    out = raw.getvalue().decode("cp1252")
    assert code == 0
    assert "Stackup: board, dielectric 0.71 mm, ?r 4.5; mask 0.01 mm, ?r 3.3." in out and "Chain U1.1 ? J1.1:" in out


def test_a_console_without_reconfigure_works(tmp_path, monkeypatch):
    out, err = io.StringIO(), io.StringIO()  # an embedding program's streams need not be TextIOWrappers
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    code, pj = run_new(tmp_path)
    assert code == 0 and out.getvalue().endswith(f"Wrote {pj}.\n") and err.getvalue() == ""


def test_unencodable_characters_become_question_marks_on_stderr(tmp_path, monkeypatch):
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stderr", console)
    code, _ = run_new(tmp_path, start="Ω.1")  # a Greek capital omega: not in cp1252
    console.flush()
    assert code == 2 and "Pad ?.1 does not exist." in raw.getvalue().decode("cp1252")


# --- plan 3, task 4: the complete project.json ----------------------------------------------------------------


def test_new_writes_every_key_and_reads_it_back(tmp_path):  # C-3, C-10, C-13, C-46
    code, pj = run_new(tmp_path, "--lid-height", "2.5")
    d = read_project(pj)
    assert code == 0 and set(d) == KEYS
    assert (d["lid"], d["gates"], d["allow_curve_port"]) == (None, {"fit2d_limit": 0.03, "dt_floor": 0.8}, False)
    assert d["chain"]["series"][0] == {"ref": "C1", "pads": ["C1.1", "C1.2"], "nets": ["RF_A", "RF_B"],
                                       "value": "100pF", "dnp": False, "role": "port",
                                       "model": {"package": "0402", "esl_h": 5e-10, "esr_ohm": 0.1, "cp_f": 3e-14},
                                       "s2p": None}
    assert [(p["ref"], p["dnp"], p["role"]) for p in d["chain"]["shunt"]][-1] == ("R2", True, "open")
    assert [(p["ref"], p["role"]) for p in d["others"]] == [("C4", "open")]


def test_new_refuses_a_dielectric_with_no_thickness_before_writing(tmp_path, capsys, mini_board_file):  # C-44
    board = four_layer(mini_board_file, "", top='(material "FR4") (epsilon_r 4.3) (loss_tangent 0.02)')
    out = tmp_path / "p"
    assert main(["new", str(board), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "-o", str(out)]) == 2
    assert capsys.readouterr().err == render("E_DIELECTRIC_THICKNESS", layer="dielectric 1") + "\n"
    assert not out.exists()


@pytest.mark.parametrize(("extra", "warned"), [((), True), (("--harmonics", "1"), False),
                                               (("--lid-height", "2.5"), False)])
def test_the_lid_warning_follows_find_lids_condition(tmp_path, capsys, extra, warned):  # C-46, L-2
    run_new(tmp_path, *extra)
    out = capsys.readouterr().out.splitlines()
    assert (render("W_LID_HEIGHT_MISSING", refs="SH1") in out) == warned
    assert render("I_LID", state="off" if "1" in extra else "on") in out


def test_a_through_hole_port_takes_the_layer_its_track_reaches(tmp_path, mini_board_file):  # M-6
    tht = '(pad "1" thru_hole circle (at 0 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask") (net "SIG"))'
    smd = '(pad "1" smd rect (at 0 0) (size 1 1) (layers "B.Cu") (net "SIG"))'
    board = mini_board_file(
        f'(footprint "L:J" (layer "F.Cu") (uuid "j") (at 5 10) (property "Reference" "J9") {tht}) '
        f'(footprint "L:T" (layer "B.Cu") (uuid "t") (at 25 10) (property "Reference" "TP2") {smd}) '
        + SEG.format(5, 10, 25, 10, 0.3, "B.Cu", "SIG", "s"))
    out = tmp_path / "p"
    assert main(["new", str(board), "--start", "J9.1", "--end", "TP2.1", "--f0", "915MHz", "--stackup", "jlcpcb-2l",
                 "-o", str(out)]) == 0
    assert [p["layer"] for p in load_project(out / "project.json")["ports"]] == ["B.Cu", "B.Cu"]


# --- beyond the brief's tests ---------------------------------------------------------------------------------


def test_a_part_that_is_no_c_l_or_r_has_no_package_preset(tmp_path, capsys, mini_board_file):
    # FB1, a ferrite bead in series: no kind, so only an S2P file closes its port (M-5)
    board = mini_board_file(footprint("TP1", pad(1, "A")) + footprint("FB1", pad(1, "A", x=2), pad(2, "B", x=4))
                            + footprint("TP2", pad(1, "B", x=6)))
    code = main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "--stackup", "jlcpcb-2l",
                 "-o", str(tmp_path / "p")])
    assert code == 0 and render("I_PART_NO_MODEL", ref="FB1", value="x", role="port") in (
        capsys.readouterr().out.splitlines())


def test_a_chain_off_the_outline_is_refused_before_writing(tmp_path, capsys, mini_board_file):  # C-44
    board = mini_board_file(EDGE + footprint("TP1", pad(1, "SIG", x=50)) + footprint("TP2", pad(1, "SIG", x=55)))
    out = tmp_path / "p"
    assert main(["new", str(board), "--start", "TP1.1", "--end", "TP2.1", "--f0", "915MHz", "--stackup", "jlcpcb-2l",
                 "-o", str(out)]) == 2
    assert capsys.readouterr().err == render("E_CHAIN_OFF_OUTLINE", nets="SIG") + "\n" and not out.exists()


# --- plan 5, task 3: the optional fields mesh.reach_h and region.margin_scale ---------------------------------


def test_reach_and_margin_are_optional_and_enter_the_model(tmp_path):  # D-12, Review Focus 5
    _, pj = run_new(tmp_path, "--lid-height", "2.5")

    def model_hash():
        project, board, geom, _ = load(pj)
        return spec_hash(build_model(project, board, geom).spec)

    base = model_hash()
    d = load_project(pj)
    del d["mesh"]["reach_h"], d["region"]["margin_scale"]
    save_project(pj, d)
    # a project.json from plan 4 reads today's defaults; since D-37 (reach 6) its results read stale (E_RESULTS_STALE)
    assert model_hash() == base
    for group, key, value in (("mesh", "reach_h", 3.0), ("region", "margin_scale", 2.0)):  # 6.0 is D-37's default
        d[group][key] = value
        save_project(pj, d)
        assert model_hash() != base
        del d[group][key]


def test_new_returns_the_notes_it_prints(tmp_path, capsys):  # design 5.2 item 5
    path, notes = cli.new(LPF, "U1.1", "J1.1", 915e6, lid_height=2.5, output=tmp_path / "a")
    assert path == tmp_path / "a" / "project.json" and path.is_file() and notes[-1] == ("I_WROTE", {"path": path})
    code, pj = run_new(tmp_path, "--lid-height", "2.5", out=tmp_path / "b")
    assert code == 0 and capsys.readouterr().out.splitlines() == [
        *(render(c, **p) for c, p in notes[:-1]), render("I_WROTE", path=pj)]
