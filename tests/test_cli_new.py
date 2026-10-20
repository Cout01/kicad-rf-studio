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
from kicad_rf_studio.core.kicad.tracer import Classes
from kicad_rf_studio.core.project import board_file, board_hash, load_project

FIX = Path(__file__).parent / "fixtures"
LPF = FIX / "lpf915.kicad_pcb"


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
    assert set(d) == {"schema", "board", "f0_hz", "harmonics", "preset", "band_factor", "t_max_s", "stackup",
                      "lid_height_mm", "classes", "chain", "ports"}
    assert set(d["board"]) == {"path", "sha256"} and d["board"]["sha256"] == board_hash(LPF)
    assert d["stackup"] == board.stackup.to_json()
    assert d["chain"] == {
        "start": "U1.1", "end": "J1.1", "nets": ["RF_A", "RF_B", "RF_C", "RF_OUT"],
        "series": [
            {"ref": "C1", "pads": ["C1.1", "C1.2"], "nets": ["RF_A", "RF_B"], "value": "100pF"},
            {"ref": "L1", "pads": ["L1.1", "L1.2"], "nets": ["RF_B", "RF_C"], "value": "15nH"},
            {"ref": "R1", "pads": ["R1.1", "R1.2"], "nets": ["RF_C", "RF_OUT"], "value": "0R"}],
        "shunt": [
            {"ref": "C2", "pads": ["C2.1", "C2.2"], "nets": ["RF_B", "GND"], "value": "3.3pF"},
            {"ref": "C3", "pads": ["C3.1", "C3.2"], "nets": ["RF_C", "GND"], "value": "3.3pF"},
            {"ref": "R2", "pads": ["R2.1", "R2.2"], "nets": ["RF_OUT", "RF_SMA"], "value": "0R"}]}
    assert d["ports"] == [
        {"name": "P1", "signal": "U1.1", "rule": "ic",
         "reference": {"pad": "U1.2", "uuid": board.pads("U1.2")[0].uuid}},
        {"name": "P2", "signal": "J1.1", "rule": "connector",
         "reference": {"pad": "J1.2", "uuid": board.pads("J1.2")[0].uuid}}]


def test_lid_height_is_null_until_given(tmp_path):
    _, pj = run_new(tmp_path)
    assert load_project(pj)["lid_height_mm"] is None


def test_options_reach_the_project_and_the_summary(tmp_path, capsys):
    out = tmp_path / "proj"
    code = main(["new", str(LPF), "--start", "U1.1", "--end", "J1.1", "--f0", "2.4GHz", "--harmonics", "5",
                 "--preset", "strict", "-o", str(out)])
    d = load_project(out / "project.json")
    assert code == 0 and (d["f0_hz"], d["harmonics"], d["preset"]) == (2.4e9, 5, "strict")
    assert "Preset strict (provisional default), band factor 1.1, T_max 40 ns, harmonics 5." in capsys.readouterr().out


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
        ref = choose_reference(board, classify(board), pad)
        assert port["rule"] == "copper" and port["reference"] == {"point": list(ref.point), "layer": "F.Cu"}
    out = capsys.readouterr().out
    assert re.search(r"Port P1: signal TP1\.1, reference \(-?\d+\.\d{3}, -?\d+\.\d{3}\) on F\.Cu \(copper\)\.", out)
    assert "GND nets: GND. Power nets: none. Connectors: none. Shields: none." in out
    assert "Chain TP1.1 → TP2.1: series none; shunt none." in out


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


def test_running_again_overwrites_with_the_same_bytes(tmp_path):
    _, pj = run_new(tmp_path)
    first = pj.read_bytes()
    code, _ = run_new(tmp_path)
    assert code == 0 and pj.read_bytes() == first


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
        "Stackup: board, dielectric 0.71 mm, εr 4.5.",
        "GND nets: GND. Power nets: VDD. Connectors: J1, J2. Shields: SH1.",
        "Chain U1.1 → J1.1: series C1, L1, R1; shunt C2, C3, R2.",
        "Port P1: signal U1.1, reference U1.2 (ic).",
        "Port P2: signal J1.1, reference J1.2 (connector).",
        "Preset normal (provisional default), band factor 1.1, T_max 40 ns, harmonics 3.",
        f"Wrote {pj}."]


def test_the_lid_warning_names_the_shield(tmp_path, capsys):
    run_new(tmp_path)
    assert "Shield SH1 found but no --lid-height was given" in capsys.readouterr().out


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
    assert code == 0 and lines[n - 1].startswith("Preset normal") and lines[n + 1].startswith("Shield SH1 found")
    assert not any("Copper layers" in line for line in lines[:n] + lines[n + 1:])


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
    assert d["ports"] == [{"name": "P1", "signal": "TP1.1", "rule": None, "reference": None},
                          {"name": "P2", "signal": "TP2.1", "rule": None, "reference": None}]
    assert d["chain"] == {"start": "TP1.1", "end": "TP2.1", "nets": ["SIG"], "series": [], "shunt": []}
    assert d["lid_height_mm"] is None and d["stackup"]["source"] == "jlcpcb-2l"
    assert printed.splitlines() == [
        "The board has no Edge.Cuts outline, so the substrate is not clipped.",
        "Fills as saved — refill (B) in KiCad and save if you changed copper.",
        "Stackup: jlcpcb-2l, dielectric 0.69952 mm, εr 4.5.",
        "GND nets: none. Power nets: none. Connectors: none. Shields: none.",
        "Chain TP1.1 → TP2.1: series none; shunt none.",
        "Port P1: signal TP1.1, reference none (none).",
        "Port P2: signal TP2.1, reference none (none).",
        "Preset normal (provisional default), band factor 1.1, T_max 40 ns, harmonics 3.",
        "No reference found for TP1.1; set it in project.json before `run`.",
        "No reference found for TP2.1; set it in project.json before `run`.",
        f"Wrote {out / 'project.json'}."]


# --- the stackup ----------------------------------------------------------------------------------------------


def test_the_stackup_option_replaces_the_boards_own(tmp_path, capsys):
    code, pj = run_new(tmp_path, "--stackup", "jlcpcb-2l")
    d = load_project(pj)
    assert code == 0 and d["stackup"]["source"] == "jlcpcb-2l"
    assert [x["name"] for x in d["stackup"]["layers"]] == ["F.Mask", "F.Cu", "dielectric 1", "B.Cu", "B.Mask"]
    assert "Stackup: jlcpcb-2l, dielectric 0.69952 mm, εr 4.5." in capsys.readouterr().out


def test_the_dielectric_thickness_is_shown_without_float_noise(tmp_path, capsys):
    code, pj = run_new(tmp_path, "--stackup", "kicad-default")  # 0.8 - 2 x (0.035 + 0.01) is 0.7100000000000001
    assert code == 0 and "Stackup: kicad-default, dielectric 0.71 mm, εr 4.5." in capsys.readouterr().out


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
    code = main(["new", str(tmp_path / "nope.kicad_pcb"), "--start", "A.1", "--end", "B.1", "--f0", "915MHz",
                 "-o", str(tmp_path / "p")])
    assert code == 2 and "nope.kicad_pcb is not a KiCad board file." in capsys.readouterr().err


def test_another_kicad_file_is_a_user_error(tmp_path, capsys):
    schematic = tmp_path / "x.kicad_sch"; schematic.write_text("(kicad_sch (version 20250114))", encoding="utf-8")
    code = main(["new", str(schematic), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    assert code == 2 and "x.kicad_sch is not a KiCad board file." in capsys.readouterr().err


def test_a_malformed_board_is_an_internal_error(tmp_path, capsys, mini_board_file):
    board = mini_board_file('(segment (end 1 1) (width 0.2) (layer "F.Cu") (net "A"))')  # no (start ...)
    code = main(["new", str(board), "--start", "A.1", "--end", "B.1", "--f0", "915MHz", "-o", str(tmp_path / "p")])
    out, err = capsys.readouterr()
    assert code == 1 and out == ""
    assert err.startswith("Internal error: TypeError(") and err.endswith(". Please report it.\n")
    assert len(err.splitlines()) == 1


class Chatty(Exception):
    def __repr__(self):
        return "Chatty(\n    'first',\n    'second',\n)"


def test_the_internal_error_is_one_line(tmp_path, monkeypatch, capsys):
    def boom(path):
        raise Chatty()

    monkeypatch.setattr(cli, "load_board", boom)
    code, _ = run_new(tmp_path)
    assert code == 1 and capsys.readouterr().err == "Internal error: Chatty( 'first', 'second', ). Please report it.\n"


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
    assert "Stackup: board, dielectric 0.71 mm, ?r 4.5." in out and "Chain U1.1 ? J1.1:" in out


def test_unencodable_characters_become_question_marks_on_stderr(tmp_path, monkeypatch):
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stderr", console)
    code, _ = run_new(tmp_path, start="Ω.1")  # a Greek capital omega: not in cp1252
    console.flush()
    assert code == 2 and "Pad ?.1 does not exist." in raw.getvalue().decode("cp1252")
