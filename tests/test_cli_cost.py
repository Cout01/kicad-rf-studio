# SPDX-License-Identifier: GPL-3.0-or-later
import re
import subprocess
import sys
from pathlib import Path

import pytest

from kicad_rf_studio.cli import main
from kicad_rf_studio.core import cs2d
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.kicad.stackup import kicad_default
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.project import SCHEMA, board_hash, load_project, mesh_n, region_expand_h, save_project

FIX = Path(__file__).parent / "fixtures"
PADS = {"coupon_gcpw_pads": ("TP1.1", "TP2.1"), "lpf915": ("U1.1", "J1.1")}
HEADER = "2D estimate: bends, vias, pads and parts not included"
SEG = '(segment (start {} {}) (end {} {}) (width {}) (layer "{}") (net "{}") (uuid "{}")) '
EDGE = '(gr_rect (start 0 0) (end 40 20) (stroke (width 0.05) (type default)) (fill no) (layer "Edge.Cuts")) '


def zone(layer, net, x0, y0, x1, y1):
    """A filled rectangular zone."""
    pts = "(pts " + " ".join(f"(xy {x} {y})" for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))) + ")"
    return f'(zone (net "{net}") (layer "{layer}") (polygon {pts}) (filled_polygon (layer "{layer}") {pts})) '


def by_hand(pj, board, nets=("LINE",), stackup=None, preset="normal"):
    """project.json written as `new` lays it out, for a board `new` cannot trace (R-P2-8: schema 1, no ports)."""
    pj.parent.mkdir(parents=True, exist_ok=True)
    save_project(pj, {
        "schema": SCHEMA, "board": {"path": board.as_posix(), "sha256": board_hash(board)},
        "f0_hz": 915e6, "harmonics": 3, "preset": preset, "band_factor": 1.1, "t_max_s": 40e-9,
        "stackup": stackup or load_board(board).stackup.to_json(), "lid_height_mm": None,
        "chain": {"start": "", "end": "", "nets": list(nets), "series": [], "shunt": []}, "ports": []})
    return pj


def new_project(tmp_path, name, preset=None):
    """`name`'s project.json: through `new` for a board with two chain pads, by hand for a pad-less coupon."""
    board, out = FIX / f"{name}.kicad_pcb", tmp_path / name
    if name not in PADS:
        return by_hand(out / "project.json", board, preset=preset or "normal")
    start, end = PADS[name]
    assert main(["new", str(board), "--start", start, "--end", end, "--f0", "915MHz", "-o", str(out),
                 *(["--preset", preset] if preset else [])]) == 0
    return out / "project.json"


def parse_z0s(row):
    return [float(z) for z in re.findall(r"Z0 (\d+\.\d\d) Ω", row)]


def fail(*args, **kwargs):
    raise AssertionError("cost started a process")


def test_cost_prints_2d_readout(tmp_path, capsys):
    proj = new_project(tmp_path, "coupon_gcpw_masked")
    assert main(["cost", str(proj)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "2D estimate: bends, vias, pads and parts not included"
    row = out[1]
    assert row.startswith("LINE on F.Cu: width 0.600 mm, gap 0.150, length 20.000 mm")
    z, zm = parse_z0s(row)
    assert zm < z


def test_cost_on_45_degree_coupon(tmp_path, capsys):
    # Review Focus 4: no straight, axis-aligned section prints the staircase warning and no row, and does not crash
    assert main(["cost", str(new_project(tmp_path, "coupon_gcpw_45"))]) == 0
    out = capsys.readouterr().out
    assert "no straight, axis-aligned sections" in out and "staircased" in out
    assert out.splitlines() == [render("W_NO_SECTIONS"), render("W_STAIRCASED", net="LINE")]


def test_cost_starts_no_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", fail)
    assert main(["cost", str(new_project(tmp_path, "coupon_ms"))]) == 0
    assert "openEMS" not in sys.modules


@pytest.mark.parametrize(("preset", "n"), [("strict", 3), ("draft", 2), (None, 2)])
def test_new_writes_region_and_mesh_defaults(tmp_path, preset, n):
    # R-P2-8: `new` needs two pads, so coupon_gcpw_pads (TP1.1 → TP2.1) stands in for the pad-less coupon_ms
    d = load_project(new_project(tmp_path, "coupon_gcpw_pads", preset=preset))
    assert d["region"] == {"expand_h": 3.0} and d["mesh"] == {"n": n}


def test_a_project_without_region_or_mesh_reads_their_defaults():  # both optional: schema 1 is unchanged
    assert region_expand_h({}) == 3.0 and region_expand_h({"region": {"expand_h": 2}}) == 2
    assert mesh_n({"preset": "strict"}) == 3 and mesh_n({"preset": "draft"}) == 2 and mesh_n({"preset": "normal"}) == 2
    assert mesh_n({"preset": "strict", "mesh": {"n": 2}}) == 2


# --- beyond the brief's tests ---------------------------------------------------------------------------------


def test_a_microstrip_has_no_gap_and_its_mask_lowers_z0(tmp_path, capsys):
    assert main(["cost", str(new_project(tmp_path, "coupon_ms_masked"))]) == 0
    assert capsys.readouterr().out.splitlines() == [
        HEADER, "LINE on F.Cu: width 1.350 mm, gap none, length 20.000 mm — Z0 48.53 Ω, εeff 3.326 without mask; "
                "Z0 47.85 Ω, εeff 3.420 with mask"]


def test_rows_follow_the_chain_then_the_position_and_the_notes_come_last(tmp_path, capsys):
    proj = new_project(tmp_path, "lpf915")
    capsys.readouterr()  # `new`'s summary
    assert main(["cost", str(proj)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == HEADER and [row.split(":")[0] for row in out[1:-1]] == [
        "RF_A on F.Cu", "RF_A on F.Cu", "RF_B on F.Cu", "RF_C on F.Cu", "RF_OUT on F.Cu"]
    assert out[1].startswith("RF_A on F.Cu: width 0.250 mm") and out[2].startswith("RF_A on F.Cu: width 0.600 mm")
    assert out[-1] == render("E_LID_HEIGHT", refs="SH1")  # `run` refuses on this gate entry; `cost` reports it


def cost_on(tmp_path, capsys, board, nets=("SIG",)):
    """`cost`'s exit code and stdout lines on a mini board, with a 0.8 mm kicad-default stackup."""
    pj = by_hand(tmp_path / board.stem / "project.json", board, nets=nets, stackup=kicad_default(0.8).to_json())
    return main(["cost", str(pj)]), capsys.readouterr().out.splitlines()


SHORT = render("W_2D_SHORT", net="SIG", layer="F.Cu", width_mm="0.300", length_mm="30.000")


def test_a_short_at_the_cut_gets_a_note_in_place_of_its_row(tmp_path, capsys, mini_board_file):
    # a 2D solve cannot hold apart copper that touches the line at its cut, so the row says why it has no numbers
    board = mini_board_file(SEG.format(5, 15, 35, 15, 0.3, "F.Cu", "SIG", "s") +
                            SEG.format(5, 15.2, 35, 15.2, 0.3, "F.Cu", "GND", "g"))  # 0.1 mm overlap
    assert cost_on(tmp_path, capsys, board) == (0, [
        HEADER, SHORT, render("W_NO_OUTLINE"), render("E_SHORT_IN_ROI", nets="GND, SIG")])  # board, then geometry


def test_copper_with_no_net_on_the_line_gets_a_note_in_place_of_its_row(tmp_path, capsys, mini_board_file):
    # verifier: copper with no net shorts nothing in the connectivity check, but at the cut it is a conductor that
    # touches the line; its row vanished with no message
    rect = '(gr_rect (start 4 14.95) (end 36 15.05) (stroke (width 0)) (fill yes) (layer "F.Cu") (uuid "r1")) '
    board = mini_board_file(SEG.format(5, 15, 35, 15, 0.3, "F.Cu", "SIG", "s") + rect)
    assert cost_on(tmp_path, capsys, board) == (0, [
        HEADER, SHORT, render("W_NETLESS_COPPER", uuid="r1", layer="F.Cu"), render("W_NO_OUTLINE")])


@pytest.mark.parametrize("pitch", [4.0, 8.0])
def test_each_arm_of_a_hairpin_reads_as_the_line_it_is(tmp_path, capsys, mini_board_file, pitch):
    # verifier: a 1.35 mm U of SIG over a B.Cu plane, its arms 2.65 or 6.65 mm apart. Both arms were the signal, so
    # they read the pair's 24.73 Ω; at 6.65 mm the far arm, clipped at the box's side, touched its 0 V face: 4.43 Ω.
    # Each arm reads the leg's Z0 now, the other arm a grounded neighbour as any other conductor is
    y0, y1 = 10 - pitch / 2, 10 + pitch / 2
    u = [(5, y0, 35, y0), (35, y0, 35, y1), (35, y1, 5, y1)]
    board = mini_board_file(EDGE + "".join(SEG.format(*p, 1.35, "F.Cu", "SIG", i) for i, p in enumerate(u)) +
                            zone("B.Cu", "GND", 0, 0, 40, 20))
    code, out = cost_on(tmp_path, capsys, board)
    arm, other, leg = (parse_z0s(row) for row in out[1:4])  # by place: the arms start at x = 5, the leg at 35
    assert code == 0 and out[3].startswith(f"SIG on F.Cu: width 1.350 mm, gap none, length {pitch:.3f} mm")
    assert arm == pytest.approx(leg, rel=0.005) and other == pytest.approx(leg, rel=0.005)


def test_a_line_on_the_bottom_copper_reads_under_the_bottom_mask(tmp_path, capsys, mini_board_file):
    # verifier: a 0.6 mm GCPW mirrored onto B.Cu printed its bare numbers as "with mask", since every row took the F
    # mask; the mask over each line is the one on its own side
    rows = []
    for line, plane in (("F.Cu", "B.Cu"), ("B.Cu", "F.Cu")):
        board = mini_board_file(EDGE + SEG.format(5, 10, 35, 10, 0.6, line, "SIG", "s") + zone(plane, "GND", 0, 0, 40, 20)
                                + zone(line, "GND", 0, 0, 40, 9.55) + zone(line, "GND", 0, 10.45, 40, 20))
        code, out = cost_on(tmp_path / line, capsys, board)
        assert code == 0 and out[1].startswith(f"SIG on {line}: width 0.600 mm, gap 0.150")
        rows.append(parse_z0s(out[1]))
    (z_top, zm_top), (z_bottom, zm_bottom) = rows
    assert zm_top < 0.95 * z_top and [z_bottom, zm_bottom] == pytest.approx([z_top, zm_top], rel=1e-3)


def test_any_other_fault_in_the_2d_solve_is_an_internal_error(tmp_path, capsys, monkeypatch):
    # verifier: the guard took every ValueError for a short, so a fault in the solve printed an empty table, exit 0
    def broken(*args):
        raise ValueError("operands could not be broadcast together")
    monkeypatch.setattr(cs2d, "_capacitance", broken)
    assert main(["cost", str(new_project(tmp_path, "coupon_gcpw_masked"))]) == 1
    assert capsys.readouterr().err == render("E_INTERNAL", detail="ValueError: operands could not be broadcast "
                                                                  "together") + "\n"


def test_a_geometry_error_is_printed_as_new_prints_errors(tmp_path, capsys):
    pj = new_project(tmp_path, "coupon_ms")
    d = load_project(pj)
    save_project(pj, {**d, "chain": {**d["chain"], "nets": ["LNIE"]}})  # a net name edited by hand
    assert main(["cost", str(pj)]) == 2
    assert capsys.readouterr() == ("", render("E_CHAIN_OFF_OUTLINE", nets="LNIE") + "\n")


@pytest.mark.parametrize(("name", "text", "why"), [
    ("nope.json", None, "file not found"), ("folder", "", "not a file"), ("bad.json", '{"schema": 1,', "not JSON"),
    ("latin1.json", b'{"schema": 1, "x": "\xe9"}', "not UTF-8 text")])
def test_a_project_that_cannot_be_read_is_a_user_error(tmp_path, capsys, name, text, why):
    pj = tmp_path / name
    if text == "":
        pj.mkdir()
    elif text is not None:
        pj.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    assert main(["cost", str(pj)]) == 2
    assert capsys.readouterr() == (
        "", f"Cannot read the project {pj}: {why}. Check the path, or fix project.json in a text editor.\n")
