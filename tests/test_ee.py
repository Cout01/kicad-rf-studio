# SPDX-License-Identifier: GPL-3.0-or-later
import json

import numpy as np
import pytest

import ee
import p0
from kicad_rf_studio import stoprule
from kicad_rf_studio.core.mesh.rule import lint_hits
from kicad_rf_studio.core.model.csx import PML_CELLS


def test_the_spec_is_design_5_12s_plane_pair_with_a_corner_port_in_air_under_pml():  # design 5.12 E-E run
    s = ee.spec()
    assert (s["boundary"], s["copper"], s["grid"]) == ("pml_8", "sheet", [])
    plate = {"x": [0.0, 50.0, 50.0, 0.0], "y": [0.0, 0.0, 30.0, 30.0]}
    assert s["metal"]["copper"] == [{**plate, "z": [0.0, 0.0]}, {**plate, "z": [0.8, 0.8]}]
    (m,) = s["materials"]
    slab = {"x": [-5.0, 55.0, 55.0, -5.0], "y": [-5.0, -5.0, 35.0, 35.0], "z": [0.0, 0.8]}  # laminate past the plates
    assert (m["eps"], m["kappa"], m["solids"]) == (4.4, 0.0, [slab])
    (p,) = s["ports"]
    assert ee.PORT[0] == pytest.approx(2.0, abs=0.1)
    assert (p["kind"], p["dir"], p["start"], p["stop"], p["part"]) == ("lumped", "z", [*ee.PORT, 0.0],
                                                                       [*ee.PORT, 0.8], False)
    exc = s["excitation"]
    assert (exc["f1"], exc["f2"], exc["t_max"], exc["window_s"]) == (0.0, 6.5e9, 30e-9, 2e-9)  # SI's DC pulse
    for axis, lo, hi in (("x", 0.0, 50.0), ("y", 0.0, 30.0)):
        lines = s["mesh"][axis]
        inner = lines[PML_CELLS:-PML_CELLS]
        assert ee.PORT[0] in lines and inner[0] <= lo - 15 and inner[-1] >= hi + 15
        assert lint_hits(np.array(lines), [(lo, 1), (hi, -1)], ee.FINE_MM) == []  # no line on a plate edge: thirds
        assert np.diff([v for v in lines if lo <= v <= hi]).max() <= 0.5 + 1e-9
        assert np.diff(lines).max() <= ee.CMAX_MM + 1e-9
    z = s["mesh"]["z"]
    assert {0.0, 0.8} <= set(z) and np.diff([v for v in z if 0 <= v <= 0.8]).max() <= 0.2 + 1e-9


def test_z_in_reads_a_resistor_and_peaks_refine_two_resonances_and_skip_bumps_and_ripple():  # the run's reading
    t = np.arange(4000) * 5e-12
    i = np.exp(-((t - 2e-9) / 2e-10) ** 2)
    assert np.allclose(ee.z_in(t, 50 * i, t, i, np.array([1e9, 3e9])), 50)
    f = ee.F_GRID
    lorentz = lambda f0, q: 1 / (1 + (2 * q * (f / f0 - 1)) ** 2)  # noqa: E731
    re_z = 1 + 40 * lorentz(1.5004e9, 30) + 30 * lorentz(3.0e9, 30) + 0.2 * lorentz(4.5e9, 5)  # 4.5 GHz: under 3 dB
    two = [pytest.approx(1.5004e9, abs=0.05e6), pytest.approx(3.0e9, abs=0.05e6)]
    assert ee.peaks(f, re_z) == two
    noisy = re_z - 1 + 1e-3 * (-1.0) ** np.arange(len(f))  # a lossless pair's troughs near 0, the DFT's ripple on them
    assert ee.peaks(f, noisy) == two  # the bump and the ripple stay under 1 % of the largest peak


def test_eigen_labels_both_solves_by_mn_and_flags_none_nodal_at_the_corner_port():  # design 5.12
    assert ee.DELTA_MM == pytest.approx(0.412 * 0.8 * 4.7 / 4.142)
    modes = ee.eigen()
    a, b = 50 + 2 * ee.DELTA_MM, 30 + 2 * ee.DELTA_MM
    assert len(modes) == 13 and len({tuple(m["mn"]) for m in modes}) == 13  # the non-DC modes from 1 to 6.5 GHz
    for m in modes:
        p, q = m["mn"]
        exact = 299792458 / (2 * np.sqrt(4.4)) * np.hypot(p / a, q / b) * 1e3
        assert m["f_hz"] == pytest.approx(exact, rel=5e-3) and m["f_hz"] < m["plain_hz"] and not m["nodal"]


def test_the_committed_references_are_the_solvers_and_are_never_regenerated():  # design 5.12: frozen before the run
    refs = json.loads(ee.REFERENCES.read_text(encoding="utf-8"))
    now = ee.references()
    assert {k: v for k, v in refs.items() if k != "modes"} == {k: v for k, v in now.items() if k != "modes"}
    assert [m["mn"] for m in refs["modes"]] == [m["mn"] for m in now["modes"]]
    for key in ("f_hz", "plain_hz"):
        assert np.allclose([m[key] for m in refs["modes"]], [m[key] for m in now["modes"]], rtol=1e-9, atol=0)
    with pytest.raises(SystemExit, match="never regenerated"):
        ee.main(["--references"])


EIG = [{"mn": [1, 0], "f_hz": 1.4e9, "plain_hz": 1.42e9, "nodal": False},
       {"mn": [0, 1], "f_hz": 2.4e9, "plain_hz": 2.43e9, "nodal": False},
       {"mn": [2, 0], "f_hz": 3.0e9, "plain_hz": 3.03e9, "nodal": True}]


def test_the_e_e_rule_matches_each_peak_to_its_nearest_non_nodal_mode_within_2_percent():  # design 5.12
    d = ee.decide([1.39e9, 2.44e9, 5.0e9], EIG)  # 5 GHz claims 2.4 GHz too; 2.44 GHz is nearer and keeps it
    assert d["verdict"] == "pass" and [m["peak_hz"] for m in d["matched"]] == [1.39e9, 2.44e9]
    assert d["unmatched_peaks_hz"] == [5.0e9] and d["unmatched_modes_hz"] == []
    assert d["offset_pct"] == pytest.approx(100 * np.mean([1.39 / 1.42 - 1, 2.44 / 2.43 - 1]))
    late = ee.decide([2.45e9], EIG)  # 2.08 % from 2.4 GHz
    assert (late["verdict"], late["unmatched_modes_hz"]) == ("fail", [1.4e9])
    none = ee.decide([], EIG)
    assert (none["verdict"], none["matched"], none["offset_pct"]) == ("incomplete", [], None)


def test_predict_counts_cells_and_prices_t_max_and_the_ring_ceiling():  # cost first (ruling 5)
    s = ee.spec()
    p = ee.predict(s, 100.0)
    cells = int(np.prod([len(s["mesh"][a]) for a in "xyz"]))
    assert p["cells"] == cells and 0.5e6 < cells < 2.5e6  # the critics' probe: about 1.15 M
    assert p["to_ceiling_s"] == pytest.approx(stoprule.RING_CEILING * p["to_t_max_s"])


def test_the_ee_step_runs_through_the_harness_with_the_fake_worker(p0_out, monkeypatch, capsys):  # ruling 5: fakes
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    assert ee.main(["--out", str(p0_out), "--cost"]) == 0
    assert {"cells", "dt", "to_t_max_s", "to_ceiling_s"} <= json.loads(capsys.readouterr().out).keys()
    assert ee.main(["--out", str(p0_out)]) == 0
    result = json.loads((p0_out / "ee" / "ee.json").read_text(encoding="utf-8"))
    assert set(result) == {"gate", "versions", "spec_hash", "references", "run", "decision", "calibration"}
    assert result["references"]["file"] == "tests/fixtures/ee/references.json"
    d = result["decision"]
    assert set(d) == {"verdict", "matched", "unmatched_peaks_hz", "unmatched_modes_hz", "offset_pct"}
    assert d["verdict"] in ("pass", "fail", "incomplete")
    assert "/" not in result["run"]["run_dir"] and "\\" not in result["run"]["run_dir"]  # a name, never a path
    assert (p0_out / "ee" / "ee.md").read_text(encoding="utf-8").startswith("## EE-1")
