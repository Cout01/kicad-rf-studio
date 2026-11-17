# SPDX-License-Identifier: GPL-3.0-or-later
from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.core.project import load_project
from test_cli_emission import emission_project
from test_project import VIA


def test_the_emission_fingerprint_leaves_out_the_lid_the_overrides_and_the_board(tmp_path, monkeypatch):  # 5.10
    monkeypatch.setattr(runs, "openems_versions", lambda: ("0.37.0", "0.7.0"))
    base = load_project(emission_project(tmp_path / "a"))
    fp = pipeline.fingerprint(base)
    assert fp["ends"] == [["TP1.1", 50.0], ["TP2.1", 50.0]] and {"lid", "overrides", "board", "results"}.isdisjoint(fp)
    for same in ({"lid": False}, {"overrides": [VIA]}, {"board": {"path": "b.kicad_pcb", "sha256": "0" * 64}}):
        assert pipeline.fingerprint({**base, **same}) == fp
    for other in ({"lid_height_mm": 2.0}, {"near_field": True}, {"t_max_s": 40e-9}, {"preset": "strict"},
                  {"ports": [base["ports"][0], {**base["ports"][1], "R": 75.0}]}):
        assert pipeline.fingerprint({**base, **other}) != fp
