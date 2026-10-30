# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path

import numpy as np

from kicad_rf_studio import __version__, pipeline
from kicad_rf_studio.core.messages import render
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.post.chain import with_box, z_part
from kicad_rf_studio.core.post.waves import band_grid
from kicad_rf_studio.core.project import load_project
from kicad_rf_studio.gui.control import default_series, snapped
from networks import C_BOX, read_s, star, terminate_np
from test_cli_antenna import FIX, antenna_project, placeholders
from test_post_chain import M0402

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
