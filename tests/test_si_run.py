# SPDX-License-Identifier: GPL-3.0-or-later
import json
import warnings
from pathlib import Path

import numpy as np
import pytest
import skrf

from kicad_rf_studio import __version__, cli, pipeline
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.post.chain import above_dc, with_box
from kicad_rf_studio.core.post.si import read, si_limits, si_lines, uniform_grid
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import load_project, save_project
from kicad_rf_studio.stoprule import KEPT
from networks import read_s, star, terminate_np
from test_cli_si import FIX, QSPI, USB, si_project
from test_match_antenna import result_lines
from test_run import result_codes
from test_tracer import part, smd, track


def test_an_si_run_writes_its_layout_on_the_grid_from_dc(tmp_path, calibrated, monkeypatch):  # design 5.12 item 2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    results = p["results"]
    assert [j["port"] for j in results["jobs"]] == ["P1", "P2", "P3", "P4", "P5", "P6", "R1", "R2"]  # Stage 1 7.1
    assert {j["verdict"] for j in results["jobs"]} <= KEPT and results["loss_expected"] is None  # no loss budget (5.6)
    out, files = pj.parent / "results", ["chain.s6p", "layout.s8p", "si_summary.csv", "si_summary.png", "si_tdr.csv"]
    assert sorted(f.name for f in out.iterdir()) == files
    n = skrf.Network(str(out / "layout.s8p"))
    assert (n.f[0], n.f[-1], len(n.f)) == (0.0, 10e9, 2001) and np.abs(n.s - star(n.f, 8)).max() <= 1e-5
    assert "port 1 P1: external, signal J1.3, reference plane In1.Cu, as built" in (out / "layout.s8p").read_text()
    codes = {e["code"] for e in map(json.loads,
                                    (Path(results["run_dir"]) / "events.jsonl").read_text("utf-8").splitlines())}
    assert not {"W_GATE_LIMITS", "W_GATE_LIMITS_SI"} & codes  # every verdict judged against GATES_SI
    lay = layout(p, results)
    assert lay.f.tolist() == uniform_grid(10e9).tolist() and lay.markers == [48]  # 240 MHz on the 5 MHz grid
    assert pipeline.retune(pj, []) == 0 and sorted(f.name for f in out.iterdir()) == files
    with pytest.raises(KrsError) as e:  # a part value would be stored and change nothing until plan 3
        pipeline.retune(pj, ["R1=33"])
    assert (e.value.code, e.value.params) == ("E_RETUNE_SI", {}) and load_project(pj) == p


def test_a_marker_off_the_grid_takes_its_nearest_point(tmp_path, calibrated, monkeypatch):  # se50's 133 MHz
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    assert layout(p, p["results"]).markers == [27]  # 135 MHz: round(133/5)


def test_an_si_run_writes_its_results(tmp_path, calibrated, monkeypatch):  # design 5.6, 5.12 item 3; Review Focus 2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    res = pipeline.chain_results(pj, p)
    block = si_lines(p, read(res.chain, res.lay.f, p, p["results"]["route"]["eeff"]), p["results"]["route"])
    lines = result_lines(p["results"]["run_dir"])
    codes, k = [code for code, _ in lines], [code for code, _ in lines].index("I_SI_RELATIVE")
    assert codes[:k] == ["I_RESULTS", "I_BASIS", "I_PASSIVITY", "I_RECIPROCITY"] and lines[k:k + len(block)] == block
    assert codes[k + len(block):] == ["I_WHAT_IF", "I_OUTPUTS", *si_limits(p)]
    assert ("I_SI_TDR_NO_ARRIVAL", {"floor": "0.001"}) in block  # the fake's star passes no differential step
    assert np.abs(read_s(pj.parent / "results" / "chain.s6p") - res.chain).max() <= 1e-12
    assert layout(p, p["results"], np.array([0.0, 2e8, 2.5e8, 1e9])).markers == [2]  # the nearest point, on any grid


def test_a_nets_run_reads_its_levels_and_holds_each_load_at_dc(tmp_path, calibrated, monkeypatch):  # RF 1, 5
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    lines = result_lines(p["results"]["run_dir"])
    low = next(params for code, params in lines if code == "I_SI_TDR_LEVEL" and params["level"] == "T_LOWEST")
    assert (low["z"], low["verdict"]) == ("26.87", "T_OUT_OF_BAND") and "I_SI_CROSSTALK" not in dict(lines)
    assert sorted(f.name for f in (pj.parent / "results").iterdir()) == [
        "chain.s2p", "layout.s3p", "si_summary.csv", "si_summary.png", "si_tdr.csv"]
    p["lines"][0]["chain"]["series"][0]["value"] = "open"  # R1 as a DNP placeholder: no impedance at any f, DC too
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)  # with_box divided by zero at DC
        res = pipeline.chain_results(pj, p)
    z = with_box(np.full(2000, np.inf), res.lay.f[1:], p["results"]["c_box"]["R1"])
    held = terminate_np(res.lay.s, [0, 1], np.r_[z[:1], z][:, None])  # the load at 5 MHz, held to DC
    assert np.isfinite(res.chain).all() and np.abs(res.chain - held).max() <= 1e-12
    assert above_dc(np.array([1e9, 2e9])).tolist() == [1e9, 2e9]  # a grid off DC (v1's, an antenna's) as it is


def test_verify_waits_for_the_si_results_and_preview_takes_an_si_project(tmp_path, calibrated, monkeypatch):
    pj = si_project(tmp_path / "p")
    with pytest.raises(KrsError) as e:
        pipeline.verify(pj)
    assert (e.value.code, e.value.params) == ("E_VERIFY_SI", {})
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(pj, pj)
    assert e.value.code == "E_COMPARE_KIND"  # compare comes with the SI results (plan 3)
    opened = []
    monkeypatch.setattr(pipeline, "appcsxcad", lambda settings: "AppCSXCAD")
    monkeypatch.setattr(pipeline, "open_viewer", lambda exe, job: opened.append(job))
    assert pipeline.preview(pj) == 0
    assert json.loads((Path(opened[0]).parent / "model.json").read_text(encoding="utf-8"))["excitation"]["f1"] == 0.0


def test_an_si_route_records_its_2d_eps_eff_length_and_loss(tmp_path):  # design 5.6: the loss lines' numbers
    for board, eeff, length, conductor, dielectric in [(USB, 3.2777, 30.405, [0.0497, 0.3210], [0.0218, 0.9072]),
                                                       (QSPI, 3.3294, 17.0425, [0.0202, 0.1748], [0.0069, 0.5161])]:
        project, b, geom, _ = pipeline.load(si_project(tmp_path / board.stem, board))
        assert pipeline.si_route(b, geom, project) == {
            "eeff": pytest.approx(eeff, abs=1e-4), "length_mm": pytest.approx(length),
            "loss_db": {"conductor": pytest.approx(conductor, abs=1e-4),
                        "dielectric": pytest.approx(dielectric, abs=1e-4)}}


def test_a_route_with_no_section_has_no_loss_estimate(mini_board_file, tmp_path):  # design 5.6; Review Focus 5
    def end(ref, at):  # a signal pad with a ground pad beside it
        return part(ref, smd(1, "SIG"), smd(2, "GND", y=-2), at=at)

    board = mini_board_file(end("A1", "0 0") + end("A2", "10 10") + track("F.Cu", "SIG", 0, 0, 10, 10))  # 45° alone
    project, b, geom, _ = pipeline.load(cli.new_si(board, "A1.1", "A2.1", "custom", f_max=5e9, target=50.0,
                                                   stackup="kicad-default", output=tmp_path / "d")[0])
    assert pipeline.si_route(b, geom, project) == {"eeff": 4.5, "length_mm": pytest.approx(14.1421, abs=1e-4),
                                                   "loss_db": None}  # the stack's largest εr, as new's


def test_an_si_run_records_its_route_and_fingerprint_before_its_jobs(tmp_path, calibrated, monkeypatch):  # 5.6, 5.8
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    project, board, geom, _ = pipeline.load(pj)
    assert d["results"]["route"] == pipeline.si_route(board, geom, project)
    keys = ("preset", "region", "interface", "f_max_hz", "rise_s", "marker_hz", "target_ohm", "stackup", "dielectric",
            "lid", "lid_height_mm")  # design 5.8's fields; t_max_s, window_s, tolerance and gates stay out
    assert d["results"]["fingerprint"] == {**{key: d[key] for key in keys}, "mesh": {"n": 2, "reach_h": 6.0},
                                           "ends": ["U1.11", "U2.6"], "app": __version__,
                                           "openems": "0.37.0"}  # fake_cli's openems_versions
    calls = []
    monkeypatch.setattr(pipeline, "si_route", lambda *a: calls.append("route") or {})
    monkeypatch.setattr(pipeline, "fingerprint", lambda p: calls.append("fingerprint") or {})
    monkeypatch.setattr(pipeline, "simulate", lambda *a, **k: calls.append("simulate"))  # None: the run ends at 3
    assert pipeline.run(pj) == 3 and calls == ["route", "fingerprint", "simulate"]  # a failed probe costs no job
    del d["results"]["route"]  # plan 2's results
    save_project(pj, d)
    with pytest.raises(KrsError) as e:
        pipeline.retune(pj, [])
    assert (e.value.code, e.value.params) == ("E_RESULTS_STALE", {})


def test_an_si_fingerprint_leaves_out_what_the_lines_set(tmp_path, fake):  # design 5.8; Review Focus 4
    a, b = (load_project(si_project(tmp_path / n, FIX / f"{n}.kicad_pcb")) for n in ("usb2_hs", "usb2_hs_45"))
    assert a["mesh"]["max_cell_mm"] != b["mesh"]["max_cell_mm"]  # λ/40 at each board's largest 2D εeff
    assert pipeline.fingerprint(a) == pipeline.fingerprint(b)  # a 45° bend is a variant compare takes
