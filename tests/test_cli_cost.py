# SPDX-License-Identifier: GPL-3.0-or-later
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from kicad_rf_studio import runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core import cs2d
from kicad_rf_studio.core.geometry import build_geometry
from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.kicad.stackup import kicad_default
from kicad_rf_studio.core.mesh.gates import fit2d
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.project import (board_hash, load_project, make_project, mesh_n, mesh_reach_h,
                                          region_expand_h, region_margin_scale, save_project)
from kicad_rf_studio.pipeline import build_model, load
from test_geometry_sections import four_layer

FIX = Path(__file__).parent / "fixtures"
PADS = {"coupon_gcpw_pads": ("TP1.1", "TP2.1"), "lpf915": ("U1.1", "J1.1"), "lpf915-45": ("U1.1", "J1.1")}
HEADER = "2D estimate: bends, vias, pads and parts not included"
FILLS, PORTLESS = render("W_FILLS_AS_SAVED"), render("W_NO_PORTS")
SEG = '(segment (start {} {}) (end {} {}) (width {}) (layer "{}") (net "{}") (uuid "{}")) '
EDGE = '(gr_rect (start 0 0) (end 40 20) (stroke (width 0.05) (type default)) (fill no) (layer "Edge.Cuts")) '


def zone(layer, net, x0, y0, x1, y1):
    """A filled rectangular zone."""
    pts = "(pts " + " ".join(f"(xy {x} {y})" for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))) + ")"
    return f'(zone (net "{net}") (layer "{layer}") (polygon {pts}) (filled_polygon (layer "{layer}") {pts})) '


def gcpw(line):
    """A 0.6 mm GCPW of SIG on `line`, the plane on the other outer layer."""
    plane = "B.Cu" if line == "F.Cu" else "F.Cu"
    return (EDGE + SEG.format(5, 10, 35, 10, 0.6, line, "SIG", "s") + zone(line, "GND", 0, 0, 40, 9.55)
            + zone(line, "GND", 0, 10.45, 40, 20) + zone(plane, "GND", 0, 0, 40, 20))


def by_hand(pj, board, nets=("LINE",), stackup=None, preset="normal"):
    """project.json written as `new` writes it, for a board `new` cannot trace (R-P2-8: no parts and no ports)."""
    pj.parent.mkdir(parents=True, exist_ok=True)
    b = load_board(board)
    chain = {"start": "", "end": "", "nets": list(nets), "series": [], "shunt": []}
    save_project(pj, make_project(board.as_posix(), board_hash(board), 915e6, stackup or b.stackup, classify(b), chain,
                                  [], [], preset=preset))
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


def half_its_error(pj: Path) -> float:
    """Half the largest fit2d error of the project `pj`, to one significant digit: a limit its own mesh misses,
    whatever the rule reads (plan 6)."""
    p, board, g, _ = load(pj)
    return float(f"{max(f.err for f in fit2d(g, build_model(p, board, g).mesh)) / 2:.1g}")


def test_cost_prints_2d_readout(tmp_path, capsys):
    proj = new_project(tmp_path, "coupon_gcpw_masked")
    assert main(["cost", str(proj)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == FILLS and out[1] == "2D estimate: bends, vias, pads and parts not included"
    row = out[2]
    assert row.startswith("LINE on F.Cu: width 0.600 mm, gap 0.150, length 20.000 mm")
    z, zm = parse_z0s(row)
    assert zm < z


def test_cost_on_45_degree_coupon(tmp_path, capsys):
    # Review Focus 4: no straight, axis-aligned section prints the staircase refusal (D-27) and no row, and does not
    # crash; the refusal is a geometry gate, so a portless project stops with exit 3
    assert main(["cost", str(new_project(tmp_path, "coupon_gcpw_45"))]) == 3
    out = capsys.readouterr().out
    assert "no straight, axis-aligned sections" in out and "the run is blocked" in out
    assert out.splitlines() == [FILLS, render("W_NO_SECTIONS"), render("E_STAIRCASED", net="LINE"), PORTLESS]


def test_staircased_measured_copper_is_refused_after_p0a(tmp_path, capsys, calibrated):  # D-27: P0-A's refuse branch
    pj = new_project(tmp_path, "lpf915-45")
    # the switch and a lid height pass E_ROTATED_PART (L1) and E_LID_HEIGHT, so only the staircase stops `cost`
    save_project(pj, {**load_project(pj), "allow_curve_port": True, "lid_height_mm": 2.5})
    capsys.readouterr()
    assert main(["cost", str(pj)]) == 3 and render("E_STAIRCASED", net="RF_B") in capsys.readouterr().out.splitlines()


def test_cost_starts_no_worker(tmp_path, monkeypatch):  # a project without ports stops after the 2D estimate
    monkeypatch.setattr(subprocess, "Popen", fail)
    assert main(["cost", str(new_project(tmp_path, "coupon_ms"))]) == 0
    assert "openEMS" not in sys.modules


@pytest.mark.parametrize(("preset", "n"), [("strict", 3), ("draft", 2), (None, 2)])
def test_new_writes_region_and_mesh_defaults(tmp_path, preset, n):
    # R-P2-8: `new` needs two pads, so coupon_gcpw_pads (TP1.1 → TP2.1) stands in for the pad-less coupon_ms
    d = load_project(new_project(tmp_path, "coupon_gcpw_pads", preset=preset))
    assert d["region"] == {"expand_h": 3.0, "margin_scale": 1.0} and d["mesh"] == {"n": n, "reach_h": 6.0}  # D-37


def test_a_project_without_region_or_mesh_reads_their_defaults():  # a bare dict; read_project requires both
    assert region_expand_h({}) == 3.0 and region_expand_h({"region": {"expand_h": 2}}) == 2
    assert mesh_n({"preset": "strict"}) == 3 and mesh_n({"preset": "draft"}) == 2 and mesh_n({"preset": "normal"}) == 2
    assert mesh_n({"preset": "strict", "mesh": {"n": 2}}) == 2
    assert (mesh_reach_h({}), region_margin_scale({}), mesh_reach_h({"mesh": {"reach_h": 3}})) == (6.0, 1.0, 3)


# --- beyond the brief's tests ---------------------------------------------------------------------------------


def test_a_microstrip_has_no_gap_and_its_mask_lowers_z0(tmp_path, capsys):
    assert main(["cost", str(new_project(tmp_path, "coupon_ms_masked"))]) == 0
    assert capsys.readouterr().out.splitlines() == [
        FILLS, HEADER, "LINE on F.Cu: width 1.350 mm, gap none, length 20.000 mm — Z0 48.53 Ω, εeff 3.326 without "
                       "mask; Z0 47.85 Ω, εeff 3.420 with mask", PORTLESS]


def test_rows_follow_the_chain_then_the_position_and_the_notes_come_last(tmp_path, capsys):
    proj = new_project(tmp_path, "lpf915")
    capsys.readouterr()  # `new`'s summary
    assert main(["cost", str(proj)]) == 2
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == [FILLS, HEADER] and [row.split(":")[0] for row in out[2:-1]] == [
        "RF_A on F.Cu", "RF_A on F.Cu", "RF_B on F.Cu", "RF_C on F.Cu", "RF_OUT on F.Cu"]
    assert out[2].startswith("RF_A on F.Cu: width 0.250 mm") and out[3].startswith("RF_A on F.Cu: width 0.600 mm")
    assert out[-1] == render("E_LID_HEIGHT", refs="SH1")  # a refusal: `cost` reports it, then stops with exit 2


def cost_on(tmp_path, capsys, board, nets=("SIG",)):
    """`cost`'s exit code and stdout lines on a mini board, with a 0.8 mm kicad-default stackup."""
    pj = by_hand(tmp_path / board.stem / "project.json", board, nets=nets, stackup=kicad_default(0.8))
    return main(["cost", str(pj)]), capsys.readouterr().out.splitlines()


SHORT = render("W_2D_SHORT", net="SIG", layer="F.Cu", width_mm="0.300", length_mm="30.000")


def test_a_short_at_the_cut_gets_a_note_in_place_of_its_row(tmp_path, capsys, mini_board_file):
    # a 2D solve cannot hold apart copper that touches the line at its cut, so the row says why it has no numbers
    board = mini_board_file(SEG.format(5, 15, 35, 15, 0.3, "F.Cu", "SIG", "s") +
                            SEG.format(5, 15.2, 35, 15.2, 0.3, "F.Cu", "GND", "g"))  # 0.1 mm overlap
    assert cost_on(tmp_path, capsys, board) == (3, [  # board, then geometry
        FILLS, HEADER, SHORT, render("W_NO_OUTLINE"), render("E_SHORT_IN_ROI", nets="GND, SIG"), PORTLESS])


def test_copper_with_no_net_on_the_line_gets_a_note_in_place_of_its_row(tmp_path, capsys, mini_board_file):
    # verifier: copper with no net shorts nothing in the connectivity check, but at the cut it is a conductor that
    # touches the line; its row vanished with no message
    rect = '(gr_rect (start 4 14.95) (end 36 15.05) (stroke (width 0)) (fill yes) (layer "F.Cu") (uuid "r1")) '
    board = mini_board_file(SEG.format(5, 15, 35, 15, 0.3, "F.Cu", "SIG", "s") + rect)
    assert cost_on(tmp_path, capsys, board) == (0, [
        FILLS, HEADER, SHORT, render("W_NETLESS_COPPER", uuid="r1", layer="F.Cu"), render("W_NO_OUTLINE"), PORTLESS])


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
    arm, other, leg = (parse_z0s(row) for row in out[2:5])  # by place: the arms start at x = 5, the leg at 35
    assert code == 0 and out[4].startswith(f"SIG on F.Cu: width 1.350 mm, gap none, length {pitch:.3f} mm")
    assert arm == pytest.approx(leg, rel=0.005) and other == pytest.approx(leg, rel=0.005)


def test_a_line_on_the_bottom_copper_reads_under_the_bottom_mask(tmp_path, capsys, mini_board_file):
    # verifier: a 0.6 mm GCPW mirrored onto B.Cu printed its bare numbers as "with mask", since every row took the F
    # mask; the mask over each line is the one on its own side
    rows = []
    for line in ("F.Cu", "B.Cu"):
        code, out = cost_on(tmp_path / line, capsys, mini_board_file(gcpw(line)))
        assert code == 0 and out[2].startswith(f"SIG on {line}: width 0.600 mm, gap 0.150")
        assert (render("W_OFF_TOP_LAYER", net="SIG", layer="B.Cu") in out) == (line == "B.Cu")  # C-9
        rows.append(parse_z0s(out[2]))
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


def test_a_dielectric_with_no_thickness_stops_cost_at_once(tmp_path, capsys, mini_board_file):
    # final review: the reader takes a dielectric that gives no thickness for 0 mm, and `new` refuses only a stackup
    # with no dielectric at all, so a 4-layer board whose top prepreg gives none got h = 0: `cost` printed Z0 3.05 Ω
    # with exit 0, and the mesh's d = 0 would run into a MemoryError after about 60 s. The z-stack refuses it first
    board = four_layer(mini_board_file, SEG.format(5, 10, 35, 10, 0.3, "F.Cu", "SIG", "s"),
                       top='(material "FR4") (epsilon_r 4.3) (loss_tangent 0.02)')
    pj = by_hand(tmp_path / "p" / "project.json", board, nets=("SIG",))
    with pytest.raises(KrsError) as e:
        build_geometry(load_board(board), load_project(pj))
    assert (e.value.code, e.value.params) == ("E_DIELECTRIC_THICKNESS", {"layer": "dielectric 1"})
    assert main(["cost", str(pj)]) == 2
    assert capsys.readouterr() == ("", render("E_DIELECTRIC_THICKNESS", layer="dielectric 1") + "\n")


def test_a_geometry_error_is_printed_as_new_prints_errors(tmp_path, capsys):
    pj = new_project(tmp_path, "coupon_ms")
    d = load_project(pj)
    save_project(pj, {**d, "chain": {**d["chain"], "nets": ["LNIE"]}})  # a net name edited by hand
    assert main(["cost", str(pj)]) == 2
    assert capsys.readouterr() == ("", render("E_CHAIN_OFF_OUTLINE", nets="LNIE") + "\n")


@pytest.mark.parametrize(("name", "text", "why"), [
    ("nope.json", None, "file not found"), ("folder", "", "file not found"), ("bad.json", '{"schema": 1,', "not JSON"),
    ("latin1.json", b'{"schema": 1, "x": "\xe9"}', "not UTF-8 text")])
def test_a_project_that_cannot_be_read_is_a_user_error(tmp_path, capsys, name, text, why):
    pj = tmp_path / name
    if text == "":
        pj.mkdir()
    elif text is not None:
        pj.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    assert main(["cost", str(pj)]) == 2
    path = pj / "project.json" if text == "" else pj  # a folder stands for its project.json (O-5)
    assert capsys.readouterr() == (
        "", f"Cannot read the project {path}: {why}. Check the path, or fix project.json in a text editor.\n")


# --- plan 3: the setup gate and the cost ---------------------------------------------------------------------------


def test_cost_runs_one_setup_worker_and_prints_the_cost(tmp_path, capsys, calibrated, monkeypatch):  # spec 3.2
    started, real = [], subprocess.Popen
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: started.append((cmd, kw["cwd"])) or real(cmd, **kw))
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    capsys.readouterr()
    assert main(["cost", str(pj.parent)]) == 0  # a folder works too
    out = capsys.readouterr().out.splitlines()
    assert len(started) == 1 and started[0][0][-1] == "job.json" and started[0][1].name == "job-0-setup"
    assert out[:2] == [render("W_FILLS_AS_SAVED"), HEADER]
    assert [line.split(":")[0].split(" ")[0] for line in out[3:]] == ["Cells", "Smallest", "dt", "Worst", "RAM", "Main"]
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules  # spec 3.1


@pytest.mark.parametrize(("setup", "code", "line"), [
    ({"pec": [[1, 1, 1, 1], [1, 2, 1, 2]]}, 3, render("E_PORT_SHORT", name="P1")),
    ({"unused": [["Box", "port_resist_2"]]}, 3, render("E_UNUSED_PRIMITIVE", property="port_resist_2", type="Box")),
    ({"unused": [["LinPoly", "metal"]]}, 0, render("W_UNUSED_PRIMITIVE", property="metal", type="LinPoly"))])
def test_the_setup_gates(tmp_path, capsys, calibrated, monkeypatch, setup, code, line):  # C-15, C-16
    monkeypatch.setenv("KRS_FAKE_SETUP", json.dumps(setup))
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    assert main(["cost", str(pj)]) == code and line in capsys.readouterr().out.splitlines()


def test_the_timestep_floor_names_the_limiting_node_in_kicads_frame(tmp_path, capsys, calibrated, monkeypatch):
    monkeypatch.setenv("KRS_FAKE_SETUP", json.dumps({"dt": 1e-15, "node": [1, 3, 4, 5]}))  # C-17
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    p, board, g, _ = load(pj)
    m = build_model(p, board, g)
    assert main(["cost", str(pj)]) == 3
    assert render("E_DT_FLOOR", dt="1.0000e-15", floor="0.8", ref=f"{m.dt_ref:.4e}", axis="y",
                  x=f"{m.mesh.x[3]:.3f}", y=f"{0.0 - m.mesh.y[4]:.3f}", z=f"{m.mesh.z[5]:.3f}") in capsys.readouterr().out


def test_a_failed_fit2d_still_prints_the_cost_and_exits_3(tmp_path, capsys, calibrated):  # C-22, C-10
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    limit = half_its_error(pj)
    save_project(pj, {**load_project(pj), "gates": {"fit2d_limit": limit, "dt_floor": 0.8}})
    assert main(["cost", str(pj)]) == 3
    out = capsys.readouterr().out
    assert "misses the 2D reference on net LINE" in out and "Worst case:" in out
    assert render("W_GATE_LIMITS", fit2d_limit=f"{limit:g}", dt_floor="0.8") in out.splitlines()


@pytest.mark.parametrize(("exit_code", "err"), [
    ("2", render("E_OPENEMS_DLL", value="unset", command=runs.install_command()) + "\n"),
    ("7", "The calibration worker ended with code 7")])
def test_a_fresh_machine_that_cannot_load_openems_gets_a_coded_refusal(tmp_path, capsys, fake, monkeypatch,
                                                                       exit_code, err):  # Review Focus 1
    monkeypatch.setenv("KRS_FAKE_EXIT", exit_code)  # no calibration yet: calibrate starts the first worker
    monkeypatch.delenv("CSXCAD_INSTALL_PATH", raising=False)
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    capsys.readouterr()
    assert main(["cost", str(pj)]) == 2
    out, got = capsys.readouterr()
    assert out.splitlines()[:2] == [render("W_FILLS_AS_SAVED"), HEADER] and got.startswith(err)


def test_cost_prints_the_readout_before_it_needs_openems(tmp_path, capsys, fake, monkeypatch):  # C-31
    def missing():
        raise KrsError("E_OPENEMS_MISSING", python="py", command="cmd")

    monkeypatch.setattr(runs, "check_openems", missing)
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")
    capsys.readouterr()
    assert main(["cost", str(pj)]) == 2
    out, err = capsys.readouterr()
    assert out.splitlines()[:2] == [render("W_FILLS_AS_SAVED"), HEADER]
    assert err == render("E_OPENEMS_MISSING", python="py", command="cmd") + "\n"


def test_ctrl_c_during_the_setup_job_exits_130_and_leaves_no_process(tmp_path, calibrated, ctrl_c_on_third_poll,
                                                                       monkeypatch):  # RF 5
    monkeypatch.setenv("KRS_FAKE", "hang")
    started = ctrl_c_on_third_poll  # tests/conftest.py (Task 13)
    assert main(["cost", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 130
    assert len(started) == 1 and started[0].poll() is not None


def test_cost_warns_when_one_job_needs_more_ram_than_is_free(tmp_path, capsys, calibrated, monkeypatch):
    # beyond the brief's tests: prepare's W_RAM branch, and the pool it cuts to one job
    monkeypatch.setattr(runs, "free_ram_mb", lambda: 100.0)  # one job of the coupon needs about 0.6 GB
    assert main(["cost", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 0
    out = capsys.readouterr().out.splitlines()
    assert render("W_RAM", need_gb="0.6", free_gb="0.1") in out and render("I_COST_RAM", gb="0.6", pool=1) in out


def test_the_cost_lines_count_no_more_jobs_at_once_than_runs(tmp_path, capsys, calibrated, monkeypatch):  # review M1
    # a pool of 4 printed "4 at once" and four jobs' RAM for the coupon's two runs
    monkeypatch.setattr(runs, "sizing", lambda entry, cells: (2, 4))
    assert main(["cost", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [line.split(", ")[-1] for line in out if line.startswith("Worst case:")] == ["2 at once with 2 threads each."]
    assert [line.split("(")[-1] for line in out if line.startswith("RAM:")] == ["2 jobs at once)."]


def test_cost_predicts_at_the_speed_of_its_own_level(tmp_path, capsys, calibrated, monkeypatch):  # D-16
    monkeypatch.setattr(runs, "sizing", lambda entry, cells: (2, 2))  # level 2 on any runner, 2 vCPUs too
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft")  # 2 runs

    def worst(levels):
        runs.save_settings({"machines": {runs.machine_key(): {"threads": 2, "pool": 2, "aggregate_mcs": 400.0,
                                                              "levels": levels}}})
        assert main(["cost", str(pj)]) == 0
        return next(x for x in capsys.readouterr().out.splitlines() if x.startswith("Worst case:"))

    assert worst({}) == worst({"2": 200.0}) != worst({"2": 50.0})


@pytest.mark.openems
def test_cost_on_the_pad_coupon_with_openems(tmp_path, capsys, monkeypatch):  # tier b: setup-only at n = 2
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    runs.save_settings({"machines": {runs.machine_key(): {"threads": 2, "pool": 1, "aggregate_mcs": 200.0}}})
    assert main(["cost", str(new_project(tmp_path, "coupon_gcpw_pads", preset="draft"))]) == 0
    out = capsys.readouterr().out
    assert "Cells: " in out and "Main cost:" in out and "unused" not in out
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules
