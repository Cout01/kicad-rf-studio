# SPDX-License-Identifier: GPL-3.0-or-later
import json
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import skrf

from kicad_rf_studio import __version__, cli, pipeline, runs
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.model.spec import verify_spec
from kicad_rf_studio.core.post.chain import above_dc, s2p_impedance, with_box, z_part
from kicad_rf_studio.core.post.si import read, si_limits, si_lines, uniform_grid
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import GATES_SI, load_project, parts, save_project
from kicad_rf_studio.stoprule import KEPT
from networks import C_BOX, read_s, star, terminate_np, write_s2p
from test_cli_si import FIX, QSPI, USB, si_project
from test_match_antenna import result_lines
from test_project import si_dict
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


def test_a_marker_off_the_grid_takes_its_nearest_point(tmp_path, calibrated, monkeypatch):  # se50's 133 MHz
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    assert layout(p, p["results"]).markers == [27]  # 135 MHz: round(133/5)


def test_a_debye_run_leaves_the_calibrations_levels(tmp_path, calibrated, monkeypatch):  # D-4, D-16; Review Focus 2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "d", QSPI)
    save_project(pj, {**load_project(pj), "dielectric": "debye"})
    assert pipeline.run(pj) == 0
    assert "levels" not in runs.load_settings()["machines"][runs.machine_key()]  # a Debye cell's speed is no plain one's
    save_project(pj, {**load_project(pj), "dielectric": "lossless"})
    assert pipeline.run(pj) == 0
    assert runs.load_settings()["machines"][runs.machine_key()]["levels"] == {"2": 100.0}  # the fake's 5e7 a thread


def test_an_si_runs_jobs_may_run_to_four_times_t_max(tmp_path, calibrated, monkeypatch):  # ruling T-2
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "q", QSPI)
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    job = json.loads((Path(d["results"]["run_dir"]) / "job-1-P1" / "job.json").read_text(encoding="utf-8"))
    assert job["t_max"] == pytest.approx(4 * d["t_max_s"])


def test_a_job_the_ring_rule_ends_reads_where_its_s_ends():  # ruling T-2: its S is cut at T_max, its last sample later
    jobs = [{"port": p, "verdict": v, "t_cut": cut, "t_stop": stop, "residual_db": -48.0}
            for p, v, cut, stop in (("P1", "t_max", 9e-9, 9.31e-9), ("P2", "t_max", None, 9e-9),
                                    ("P3", "flat", 7e-9, 7.4e-9))]
    lines = pipeline.basis_lines({"jobs": jobs, "run_dir": "R", "preset": "normal", "gates": GATES_SI}, GATES_SI)
    assert [(c, p["t_ns"]) for c, p in lines[1:4]] == [("W_JOB_T_MAX", "9.00"), ("W_JOB_T_MAX", "9.00"),
                                                       ("W_JOB_FLAT", "7.00")]


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


def test_the_si_view_is_what_run_prints_and_write_outputs_reports(tmp_path, calibrated, monkeypatch):  # RF 1, ruling 1
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    p = load_project(pj)
    res = pipeline.chain_results(pj, p, errors_as_lines=True)
    reading, lines = pipeline.si_view(p, res)
    assert lines == result_lines(p["results"]["run_dir"])[1:len(lines) + 1]  # run printed them after I_RESULTS
    assert np.array_equal(reading.m, read(res.chain, res.lay.f, p, p["results"]["route"]["eeff"]).m)
    outputs = pipeline.write_outputs(pj, p, "x", errors_as_lines=True)
    assert outputs[:len(lines)] == lines
    assert [c for c, _ in outputs[len(lines):]] == ["I_WHAT_IF", "I_OUTPUTS", *si_limits(p)]
    assert pipeline.si_view(p, replace(res, chain=None)) == (None, res.lines)  # a part's refusal: no reading
    assert res.reading is None  # chain_results leaves it to si_view's callers


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
    assert (e.value.code, e.value.params) == ("E_NO_RESULTS", {})
    with pytest.raises(KrsError) as e:
        pipeline.compare_projects(pj, pj)
    assert (e.value.code, e.value.params) == ("E_COMPARE_NO_RESULT", {"path": str(pj)})  # no run
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
    assert d["results"]["fingerprint"] == {**{key: d[key] for key in keys},
                                           "mesh": {"n": 2, "reach_h": 6.0, "d_fill": True},  # new's null, gate P4-C
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
    assert a["mesh"]["max_cell_mm"] is b["mesh"]["max_cell_mm"] is None  # the d fill on both (gate P4-C)
    assert pipeline.fingerprint(a) == pipeline.fingerprint(b)  # a 45° bend is a variant compare takes


def test_an_si_fingerprint_holds_whether_the_mesh_is_the_d_fill(tmp_path, fake):  # design 5.8; gate P4-C
    p, prints = load_project(si_project(tmp_path / "p")), []
    for cell in (None, 0.414, 0.3):  # the d fill, then two hand-set cells
        p["mesh"]["max_cell_mm"] = cell
        prints.append(pipeline.fingerprint(p))
    d_fill, set_cell, finer = prints
    assert [key for key in d_fill if d_fill[key] != set_cell[key]] == ["mesh"]  # never compared with a set cell's run
    assert set_cell == finer  # the cell's value stays out


def test_an_si_retune_closes_the_part_ports_at_their_new_values(tmp_path, calibrated, monkeypatch):  # design 5.7
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    lines, seen = [], []
    monkeypatch.setattr(pipeline, "si_png", lambda curves, project, title, label=None: seen.append(label) or b"")
    assert pipeline.retune(pj, ["R1=33", "R2=33"], lambda code, params: lines.append((code, params))) == 0
    p = load_project(pj)
    assert [(ref, q["value"]) for ref, q in parts(p).items() if ref[0] == "R"] == [("R1", "33"), ("R2", "33")]
    f, model = uniform_grid(10e9), parts(p)["R1"]["model"]
    z = with_box(z_part("R", 33.0, model, f[1:]), f[1:], C_BOX)
    oracle = terminate_np(star(f, 8), list(range(6)), np.stack([np.r_[z[:1], z]] * 2, -1))
    assert np.abs(read_s(pj.parent / "results" / "chain.s6p") - oracle).max() <= 1e-5
    verify = {"command": pipeline.command_line("kicad-rf-studio", "verify", str(pj))}
    assert ("I_WHAT_IF", verify) in lines and seen == [render("I_WHAT_IF", **verify)]  # the PNG's label too
    assert [code for code, _ in lines][-6:] == list(si_limits(p))


def test_an_si_retune_takes_an_s2p_file_from_the_first_point_above_dc(tmp_path, calibrated, monkeypatch):  # 5.7; RF 1
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    fs, late = np.linspace(1e6, 20e9, 2000), np.linspace(10e6, 20e9, 2000)
    c = write_s2p(tmp_path / "c.s2p", 1 / (2j * np.pi * fs * 100e-9), "series", fs)  # an AC-coupling capacitor's data
    write_s2p(tmp_path / "late.s2p", 1 / (2j * np.pi * late * 100e-9), "series", late)
    assert pipeline.retune(pj, [f"R1={c}:series"]) == 0
    f = uniform_grid(10e9)
    zk = np.stack([with_box(z, f[1:], C_BOX) for z in (s2p_impedance(c, "series", "R1", f[1:])[0],
                                                        z_part("R", 22.0, parts(load_project(pj))["R2"]["model"],
                                                               f[1:]))], -1)
    oracle = terminate_np(star(f, 8), list(range(6)), np.vstack([zk[:1], zk]))  # the file's 5 MHz point held to DC
    assert np.abs(read_s(pj.parent / "results" / "chain.s6p") - oracle).max() <= 1e-5
    with pytest.raises(KrsError) as e:  # a file must reach the grid's first point above DC
        pipeline.retune(pj, [f"R1={tmp_path / 'late.s2p'}:series"])
    assert (e.value.code, e.value.params["f1"], e.value.params["f_lo"]) == ("E_S2P_BAND", "5.0", "10.0")


def test_an_si_retune_takes_the_bypasses_and_their_refusals(tmp_path):  # design 5.7, A-33's rules; Review Focus 5
    def port(ref, nets, **kw):
        return {"ref": ref, "pads": [f"{ref}.1", f"{ref}.2"], "nets": nets, "value": "22", "dnp": False,
                "role": "port", "model": None, "s2p": None, **kw}

    d = si_dict()
    d["lines"][0]["chain"]["series"] = [port("R1", ["USB_D+", "MCU_D+"])]
    d["lines"][0]["chain"]["shunt"] = [port("R7", ["USB_D+", "GND"]),
                                       port("R5", ["USB_D+", "+3V3"], value="1.5k", role="open")]  # a pull-up
    d["lines"][1]["chain"]["shunt"] = [port("R9", ["USB_D-", "USB_D+"])]  # across the pair: both nets measured
    new = pipeline.assign(d, ["R1=0R", "R7=open", "R9=0R"], tmp_path)
    assert {ref: q["value"] for ref, q in parts(new).items()} == {"R1": "0R", "R7": "open", "R5": "1.5k", "R9": "0R"}
    for arg, code, params in [("R1=open", "E_RETUNE_OPEN_SERIES", {"ref": "R1"}),
                              ("R7=0R", "E_RETUNE_SHORT_SHUNT", {"ref": "R7", "net": "GND"}),
                              ("R1=abc", "E_RETUNE_ANTENNA_VALUE", {"ref": "R1", "value": "abc"}),
                              ("R5=2.2k", "E_RETUNE_ROLE", {"ref": "R5", "role": "open"})]:
        with pytest.raises(KrsError) as e:
            pipeline.assign(d, [arg], tmp_path)
        assert (e.value.code, e.value.params) == (code, params)


def verified_si(tmp_path, monkeypatch, board=USB):
    """An SI fixture run on the network fake, its run's operator dump stood in for and the cell C read as 6e-16 F
    (test_verify.verified's), so that verify runs: the project file."""
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / board.stem, board)
    assert pipeline.run(pj) == 0
    (Path(load_project(pj)["results"]["run_dir"]) / "job-0-setup" / "operator_dump.vtr").write_bytes(b"")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    return pj


def test_verify_puts_an_si_lines_parts_in_the_grid_and_compares(tmp_path, calibrated, monkeypatch):  # 5.7; RF 1, 2
    pj = verified_si(tmp_path, monkeypatch)
    before = load_project(pj)["results"]
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)  # no division by zero at DC
        assert pipeline.verify(pj) == 0
    d = load_project(pj)
    v = d["verify"]
    assert d["results"] == before and set(v) == {"model_hash", "base_hash", "values", "run_dir", "jobs", "compare",
                                                 "fingerprint"}
    assert v["values"] == {"R1": "22", "R2": "22"} and v["fingerprint"] == before["fingerprint"]
    assert [j["port"] for j in v["jobs"]] == ["P1", "P2", "P3", "P4", "P5", "P6"]
    # star(f, 6) against star(f, 8) closed by 22 Ω ∥ C_BOX; the star's pair passes no differential step
    assert v["compare"] == {"ds_max": pytest.approx(0.12326, abs=1e-4), "f_hz": 10e9, "levels": None}
    model = json.loads((Path(v["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    assert [g["name"] for g in model["grid"]] == ["R1", "R2"]
    assert "verify.s6p" in {f.name for f in (pj.parent / "results").iterdir()}
    codes = result_codes(v["run_dir"])
    k = codes.index("I_VERIFY_COMPARE_SI")
    assert codes[:2] == ["I_VERIFY_RESULTS", "I_SI_RELATIVE"] and codes[k + 1] == "I_VERIFY_NO_LEVELS"
    assert codes[-7:] == ["I_VERIFY_SCOPE_SI", *si_limits(d)]


def test_verify_of_a_net_compares_its_tdr_levels(tmp_path, calibrated, monkeypatch):  # design 5.7
    pj = verified_si(tmp_path, monkeypatch, QSPI)
    assert pipeline.verify(pj) == 0
    d = load_project(pj)
    (low_v, low_r, low_s), (high_v, high_r, high_s) = d["verify"]["compare"]["levels"]
    # verify's own S is star(f, 2) back from the fake's waves, within 2e-6: matched, its levels 50 Ω to 1.6e-6
    assert (low_v, high_v) == (pytest.approx(50.0, abs=1e-4), pytest.approx(50.0, abs=1e-4))
    assert not (low_s or high_s)
    assert [p for c, p in result_lines(d["verify"]["run_dir"]) if c == "I_VERIFY_LEVEL"] == [
        {"level": "T_LOWEST", "verify": f"{low_v:.2f}", "retune": f"{low_r:.2f}"},
        {"level": "T_HIGHEST", "verify": f"{high_v:.2f}", "retune": f"{high_r:.2f}"}]


def test_verify_spec_puts_an_si_bypass_as_copper_or_leaves_it_out(tmp_path, monkeypatch):  # 5.7, A-33's rule
    project, board, geom, _ = pipeline.load(si_project(tmp_path))
    spec = pipeline.build_model(project, board, geom).spec
    by_ref = parts(project)
    by_ref["R1"]["value"], by_ref["R2"]["value"] = "0R", "open"
    dump = tmp_path / "operator_dump.vtr"
    dump.write_bytes(b"")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    out = verify_spec(spec, by_ref, dump, 1e-13, bypasses=True)
    assert out["grid"] == [] and len(out["metal"]["copper"]) == len(spec["metal"]["copper"]) + 1
    with pytest.raises(KrsError) as e:  # without it, v1's: R1 an R of 0 Ω, then R2's open refused
        verify_spec(spec, by_ref, dump, 1e-13)
    assert (e.value.code, e.value.params) == ("E_VERIFY_VALUE", {"ref": "R2", "value": "open"})
