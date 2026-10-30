# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio import __version__, pipeline
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.post.antenna import ANTENNA_LIMITS, eta_what_if_lines
from kicad_rf_studio.core.post.chain import with_box, z_part
from kicad_rf_studio.core.post.checks import loss_budget
from kicad_rf_studio.core.post.waves import band_grid
from kicad_rf_studio.core.project import load_project, save_project
from kicad_rf_studio.gui.control import default_series, snapped
from networks import C_BOX, read_s, star, terminate_np
from test_cli_antenna import FIX, antenna_project, placeholders
from test_post_chain import M0402
from test_run import lpf_project

BAND = (2.4e9, 2.4835e9)
OPEN = None  # a part port closed by its box's C alone


def pi_run(tmp_path, monkeypatch, board=FIX / "ifa2g4_pi.kicad_pcb"):
    """`board`, the pi variant by default, run on the network fake (its layout is star(f, 4)), with the cell C that
    verify reads stood in for at 6e-16 F, as test_verify.verified does: the project file."""
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)
    pj = antenna_project(tmp_path / board.stem, board, BAND)
    assert pipeline.run(pj) == 0
    return pj


def oracle(f, *z):
    """S11 of star(f, 4) at port 1, its three part ports closed in job order by `z`: each a Z_part on f across C_BOX,
    or OPEN."""
    zk = [1 / (2j * np.pi * f * C_BOX) if v is OPEN else with_box(v, f, C_BOX) for v in z]
    return terminate_np(star(f, 4), [0], np.stack(zk, -1))[:, 0, 0]


def chain_s11(pj):
    return read_s(pj.parent / "results" / "chain.s1p")[:, 0, 0]


def result_lines(run_dir):
    events = (Path(run_dir) / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [(e["code"], e["params"]) for e in map(json.loads, events) if e["kind"] == "result"]


def test_the_antenna_seen_through_its_feed_line(tmp_path, calibrated, monkeypatch):  # design 5.7; RF 2
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.retune(pj, ["L1=0R", "C2=open", "C3=open"]) == 0  # the series part shorted, both shunts removed
    f = band_grid(load_project(pj))
    assert np.abs(chain_s11(pj) - oracle(f, np.zeros(len(f)), OPEN, OPEN)).max() <= 1e-5


def test_a_placeholder_board_runs_its_placeholders_as_ports_there_and_back(tmp_path, calibrated, monkeypatch):  # RF 2
    pj = pi_run(tmp_path, monkeypatch, placeholders(tmp_path))
    f, chain = band_grid(load_project(pj)), pj.parent / "results" / "chain.s1p"
    short, c1, before = np.zeros(len(f)), z_part("C", 1e-12, M0402, f), chain.read_bytes()
    assert np.abs(chain_s11(pj) - oracle(f, short, OPEN, c1)).max() <= 1e-5  # R1 at 0 Ω, C2 open, C3 1 pF
    assert pipeline.retune(pj, ["C2=1pF"]) == 0  # the DNP placeholder fitted
    assert np.abs(chain_s11(pj) - oracle(f, short, c1, c1)).max() <= 1e-5
    assert pipeline.retune(pj, ["C2=open"]) == 0 and chain.read_bytes() == before  # and removed again


def test_snapping_leaves_a_bypass_as_typed():  # design 5.7: E24 snapping as in v1, the GUI's (Stage 2 design 5.3)
    typed = {"L1": "3.1nH", "C2": "0.95pF", "C3": "1.25pF", "R1": "0R", "C4": "open", "L2": "0R"}
    assert {ref: snapped(ref, text, default_series(ref)) for ref, text in typed.items()} == {
        "L1": "3nH", "C2": "0.91pF", "C3": "1.3pF", "R1": "0R", "C4": "open", "L2": "0R"}


def test_a_part_port_run_says_where_its_far_field_comes_from(tmp_path, calibrated, monkeypatch):  # design 5.5, 5.7
    pj = pi_run(tmp_path, monkeypatch)
    d = load_project(pj)
    lines, verify = result_lines(d["results"]["run_dir"]), pipeline.command_line("kicad-rf-studio", "verify", str(pj))
    codes = [code for code, _ in lines]
    assert ("I_ANTENNA_NO_FAR_FIELD", {"command": verify}) in lines and d["results"]["far_field"] is None
    assert codes.index("I_ANTENNA_RELATIVE") < codes.index("I_ANTENNA_NO_FAR_FIELD") < codes.index("I_WHAT_IF")
    seen = []
    monkeypatch.setattr(pipeline, "antenna_png", lambda f, s11, project, far, name, label=None: seen.append(label) or b"")
    assert pipeline.retune(pj, []) == 0 and seen == [render("I_WHAT_IF", command=verify)]  # the PNG's label


def test_an_antenna_run_records_its_settings_fingerprint(tmp_path, calibrated):  # design 5.8
    pj = antenna_project(tmp_path / "p")
    assert pipeline.run(pj) == 0
    d = load_project(pj)
    keys = ("preset", "mesh", "region", "band", "f0_hz", "t_max_s", "air_gap_mm", "boundary", "far_field", "stackup",
            "lid_height_mm")
    assert d["results"]["fingerprint"] == {**{key: d[key] for key in keys}, "start": "U1.1", "copper": "solid",
                                           "app": __version__, "openems": "0.37.0"}  # fake_cli's openems_versions


def test_an_antenna_takes_its_fingerprint_before_any_job(tmp_path, calibrated, monkeypatch):  # final review
    pj = pi_run(tmp_path, monkeypatch)  # part ports and a run: verify has something to verify
    calls = []
    monkeypatch.setattr(pipeline, "fingerprint", lambda project: calls.append("fingerprint") or {})
    monkeypatch.setattr(pipeline, "simulate", lambda *a, **k: calls.append("simulate"))  # None: the command ends at 3
    assert pipeline.run(pj) == 3 and pipeline.verify(pj) == 3
    assert calls == ["fingerprint", "simulate"] * 2  # a failed openEMS probe costs no job
    calls.clear()
    assert pipeline.run(lpf_project(tmp_path)) == 3 and calls == ["simulate"]  # v1: no fingerprint


def test_verify_runs_an_antennas_network_in_one_job_and_records_its_far_field(tmp_path, calibrated, monkeypatch):
    pj = pi_run(tmp_path, monkeypatch)  # design 5.1, 5.5, 5.7
    m0 = antenna_project(tmp_path / "m0")
    with pytest.raises(KrsError) as e:  # no part on the chain: its run is its far-field run
        pipeline.verify(m0)
    assert e.value.code == "E_VERIFY_NO_PARTS"
    with pytest.raises(KrsError) as e:  # nor anything to retune: v1's refusals stand (design 5.1)
        pipeline.retune(m0, ["C1=1pF"])
    assert e.value.code == "E_RETUNE_NO_PARTS"
    before = load_project(pj)["results"]
    assert pipeline.verify(pj) == 0  # one external port: no E_VERIFY_PORTS for an antenna
    d = load_project(pj)
    v, run_dir = d["verify"], Path(d["verify"]["run_dir"])
    assert d["results"] == before and set(v) == {"model_hash", "base_hash", "values", "run_dir", "jobs", "compare",
                                                 "far_field", "fingerprint"}
    assert v["values"] == {"L1": "2.7nH", "C2": "1pF", "C3": "1pF"} and v["fingerprint"] == before["fingerprint"]
    assert [(j["port"], j["verdict"]) for j in v["jobs"]] == [("P1", "converged")]
    model = json.loads((run_dir / "model.json").read_text(encoding="utf-8"))
    assert [q["name"] for q in model["ports"]] == ["P1"] and [g["name"] for g in model["grid"]] == ["L1", "C2", "C3"]
    assert model["nf2ff"]["f_hz"] == d["far_field"]["f_hz"] and list(v["far_field"]) == [
        "sphere", "elevation", "azimuth"]
    assert all((run_dir / p).is_file() for p in v["far_field"].values())
    f = band_grid(d)
    retuned = oracle(f, *(z_part(k, x, None, f) for k, x in (("L", 2.7e-9), ("C", 1e-12), ("C", 1e-12))))  # ideal
    assert v["compare"]["ds11_max"] == pytest.approx(np.abs(star(f, 1)[:, 0, 0] - retuned).max(), abs=1e-4)
    assert v["compare"]["shift"] is None  # star(f, 1) has no dip: its |S11| is 0.9025 at every f
    assert sorted(p.name for p in (pj.parent / "results").iterdir()) == [
        "antenna_summary.png", "chain.s1p", "layout.s4p", "verify.s1p", "verify_farfield.csv", "verify_summary.csv",
        "verify_summary.png"]
    codes = [code for code, _ in result_lines(run_dir)]
    assert codes[0] == "I_VERIFY_RESULTS" and codes.index("I_ANTENNA_RELATIVE") < codes.index("I_VERIFY_COMPARE_S11")
    assert codes[codes.index("I_VERIFY_COMPARE_S11") + 1] == "I_RESONANCE_NOT_COMPARED"
    assert codes.count("I_ANTENNA_FAR_FIELD") == 2  # the fixture's 2 f
    assert not {"I_VERIFY_LOSS_BUDGET", "W_VERIFY_LOSS_BUDGET"} & set(codes)
    assert codes[-7:] == ["I_OUTPUTS", "I_VERIFY_SCOPE_ANTENNA", *ANTENNA_LIMITS]


def test_verify_of_the_antenna_through_its_feed_line(tmp_path, calibrated, monkeypatch):  # design 5.7; RF 2
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.retune(pj, ["L1=0R", "C2=open", "C3=open"]) == 0
    monkeypatch.setattr(spec_module, "c_box", None)  # nothing in the grid: verify reads no cell C
    assert pipeline.verify(pj) == 0
    d = load_project(pj)
    run = json.loads((Path(d["results"]["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    model = json.loads((Path(d["verify"]["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    assert model["grid"] == [] and len(model["metal"]["copper"]) == len(run["metal"]["copper"]) + 1  # L1's box
    assert d["verify"]["values"] == {"L1": "0R", "C2": "open", "C3": "open"}


@pytest.mark.parametrize(("held", "stored", "written"), [
    ("verify_summary.png", True, None),  # stored with its far field; the second write refused, so no I_OUTPUTS
    ("project.json", False, "verify.s1p, verify_summary.png")])  # nothing stored, so no transform; the first write's
def test_a_held_file_costs_an_antennas_verify_only_that_file(tmp_path, calibrated, monkeypatch, held, stored, written):
    pj = pi_run(tmp_path, monkeypatch)  # RF 3; as test_verify's HELD
    real = os.replace

    def replace(src, dst):  # another program holds the file: an image viewer, an indexer
        if Path(dst).name == held:
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    assert pipeline.verify(pj) == 2
    d = load_project(pj)
    assert ("verify" in d) is stored
    assert not stored or list(d["verify"]["far_field"]) == ["sphere", "elevation", "azimuth"]
    (own,) = [p for p in (calibrated / "runs").iterdir() if str(p) != d["results"]["run_dir"]]  # verify's run folder
    events = [json.loads(line) for line in (own / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["kind"] for e in events if e["code"] == "E_RESULTS_WRITE"] == ["message"]  # one, the write that stands
    lines = result_lines(own)
    assert ("I_VERIFY_RESULTS" in [code for code, _ in lines]) is stored
    assert [p["files"] for code, p in lines if code == "I_OUTPUTS"] == ([written] if written else [])
    assert [code for code, _ in lines][-6:] == ["I_VERIFY_SCOPE_ANTENNA", *ANTENNA_LIMITS]


def test_a_verify_whose_transform_fails_keeps_its_comparison(tmp_path, calibrated, monkeypatch):  # RF 3
    pj = pi_run(tmp_path, monkeypatch)

    def fail(*_, **__):
        raise KrsError("E_WORKER_FAILED", job="T_JOB_FAR_FIELD", exit_code=1, log="log.txt")

    monkeypatch.setattr(pipeline, "far_field", fail)
    assert pipeline.verify(pj) == 2
    v = load_project(pj)["verify"]
    events = [json.loads(line)
              for line in (Path(v["run_dir"]) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert v["far_field"] is None and "ds11_f0" in v["compare"]
    assert [e["kind"] for e in events if e["code"] == "E_WORKER_FAILED"] == ["message"]
    written = sorted(p.name for p in (pj.parent / "results").iterdir())
    assert {"verify.s1p", "verify_summary.png"} <= set(written) and "verify_farfield.csv" not in written
    assert [p["files"] for c, p in result_lines(v["run_dir"]) if c == "I_OUTPUTS"] == ["verify.s1p, verify_summary.png"]


def test_a_stopped_verify_transform_keeps_the_comparison(tmp_path, calibrated, monkeypatch):  # RF 3; Stage 1 7.8
    pj = pi_run(tmp_path, monkeypatch)

    def stop(*_, **__):
        raise KeyboardInterrupt  # STOP or Ctrl+C during the transform

    monkeypatch.setattr(pipeline, "far_field", stop)
    with pytest.raises(KeyboardInterrupt):
        pipeline.verify(pj)
    v = load_project(pj)["verify"]
    assert v["far_field"] is None and [j["verdict"] for j in v["jobs"]] == ["converged"]
    assert [code for code, _ in result_lines(v["run_dir"])] == ["I_VERIFY_RESULTS"]  # said before the transform
    assert (pj.parent / "results" / "verify.s1p").is_file()
    assert not (pj.parent / "results" / "verify_farfield.csv").exists()


def test_after_verify_the_retune_shows_the_what_if_total_efficiency(tmp_path, calibrated, monkeypatch):  # 5.7; RF 4
    pj = pi_run(tmp_path, monkeypatch)
    assert pipeline.verify(pj) == 0

    def retune(*assignments):
        lines = []
        assert pipeline.retune(pj, list(assignments), lambda code, params: lines.append((code, params))) == 0
        return lines

    lines = retune("C3=1.2pF")
    d = load_project(pj)
    v = d["verify"]
    assert pipeline.current_verify(d) == v and {"verify.s1p", "verify_farfield.csv", "verify_summary.csv",
                                                "verify_summary.png"} <= {p.name for p in (pj.parent / "results").iterdir()}
    far = pipeline.far_of(v)
    ff, up = far["sphere"].f, np.argsort(far["sphere"].f)  # the lines run by ascending frequency
    zk = np.stack([with_box(z_part(k, x, M0402, ff), ff, C_BOX)
                   for k, x in (("L", 2.7e-9), ("C", 1e-12), ("C", 1.2e-12))], -1)  # the retune's presets
    p = loss_budget(star(ff, 4), [0], zk)  # the fake's layout is star(f, 4) at any f
    got = [params for code, params in lines if code == "I_ANTENNA_ETA_WHAT_IF"]
    assert [float(g["delivered_pct"]) for g in got] == pytest.approx(100 * p[up], abs=0.06)
    assert [g["eta_rad_pct"] for g in got] == [f"{100 * x:.1f}" for x in far["eff"]["eta_rad"][up]]
    assert "I_ANTENNA_NO_FAR_FIELD" not in [code for code, _ in lines]
    for verify in ({**v, "far_field": None}, {**v, "base_hash": "0" * 64}):  # its transform failed; another run's
        save_project(pj, {**d, "verify": verify})
        assert (pipeline.current_verify(load_project(pj)) is None) is (verify["base_hash"] != v["base_hash"])
        assert "I_ANTENNA_NO_FAR_FIELD" in [code for code, _ in retune()]
    save_project(pj, {**d, "verify": v})
    shutil.rmtree(v["run_dir"])  # verify's folder deleted
    codes = [code for code, _ in retune()]
    assert pipeline.current_verify(load_project(pj)) is None
    assert "I_ANTENNA_NO_FAR_FIELD" in codes and "I_ANTENNA_ETA_WHAT_IF" not in codes


# --- beyond the brief's tests ------------------------------------------------------------------------------------


def test_verify_reports_the_resonance_shift(tmp_path, calibrated, monkeypatch):  # design 5.7: the fake has no dip
    pj = pi_run(tmp_path, monkeypatch)
    cmp = {"ds11_f0": 0.01, "ds11_max": 0.02, "f_res_hz": 2.4495e9, "f_res_retune_hz": 2.438e9,
           "shift": 11.5e6 / 2.438e9}
    monkeypatch.setattr(pipeline, "compare_s11", lambda *a: cmp)
    assert pipeline.verify(pj) == 0
    lines = result_lines(load_project(pj)["verify"]["run_dir"])
    assert lines[[code for code, _ in lines].index("I_VERIFY_COMPARE_S11") + 1] == (
        "I_VERIFY_SHIFT", {"f_res_mhz": "2449.5", "f_res_retune_mhz": "2438.0", "shift_pct": "+0.47"})
