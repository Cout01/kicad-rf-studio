# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from kicad_rf_studio import pipeline
from kicad_rf_studio.core.geometry.region import air_gap
from kicad_rf_studio.core.model.csx import EMISSION_NF2FF_MAX, PML_CELLS, build_csx
from kicad_rf_studio.core.model.spec import emission_pulse, spec_hash
from kicad_rf_studio.core.project import harmonics_hz, load_project, save_project
from test_antenna_kicad import fp
from test_cli_antenna import IFA, antenna_project
from test_cli_emission import LPF, emission_project
from test_cli_new import run_new
from test_cli_si import si_project
from test_model_csx import TINY, fake_openems
from test_tracer import smd


def built(pj, **edits):
    if edits:
        save_project(pj, {**load_project(pj), **edits})
    project, board, geom, notes = pipeline.load(pj)
    return project, board, geom, notes, pipeline.build_model(project, board, geom)


def test_an_emission_model_is_the_whole_board_in_air_under_pml_lossless(tmp_path):  # design 5.6, 5.7; B3
    project, board, geom, notes, model = built(emission_project(tmp_path / "e"))
    s, gap = model.spec, project["air_gap_mm"]
    assert geom.antenna and not model.blocked and not [c for c, _ in notes if c.startswith("E_")]
    assert (s["boundary"], s["excitation"]) == ("pml_8", emission_pulse(1.83e9, 4.575e9, 22e-9))
    assert {"nf2ff", "copper", "join", "near_field"}.isdisjoint(s) and all(m["kappa"] == 0.0 for m in s["materials"])
    x0, _, x1, _ = board.outline.bounds
    assert s["mesh"]["x"][PML_CELLS] <= x0 - gap and s["mesh"]["x"][-1 - PML_CELLS] >= x1 + gap


def test_a_terminations_r_reaches_the_spec_and_the_csx(tmp_path, monkeypatch):  # design 5.6
    pj = emission_project(tmp_path / "e")
    base = built(pj)[4].spec
    d = load_project(pj)
    spec = built(pj, ports=[d["ports"][0], {**d["ports"][1], "R": 75.0}])[4].spec
    p1, p2 = spec["ports"]
    assert "R" not in p1 and p2["R"] == 75.0 and spec_hash(spec) != spec_hash(base)
    log = fake_openems(monkeypatch)
    build_csx(spec, 1, 1e-9)
    assert [a[:2] for n, a, _ in log if n == "AddLumpedPort"] == [(1, 50), (2, 75.0)]


@pytest.mark.parametrize("make", [lambda f: run_new(f)[1], antenna_project, si_project], ids=["v1", "antenna", "si"])
def test_no_other_kind_writes_an_r_or_a_near_field_plane(tmp_path, make):  # Review Focus 5; B11
    pj = make(tmp_path / "p")
    plain = spec_hash(built(pj)[4].spec)
    ports = [{**q, "R": 75.0} for q in load_project(pj)["ports"]]
    assert spec_hash(built(pj, ports=ports, near_field=True)[4].spec) == plain


def test_the_far_field_cap_is_64_for_an_emission_spec_and_stays_11_otherwise(monkeypatch):  # design 5.8; 3
    exc, grid = emission_pulse(1e9, 6e9), [1e9 + 1e8 * k for k in range(51)]
    spec = {**TINY, "excitation": exc, "nf2ff": {"f_hz": grid, "center": [2.0, 2.0, 2.0]}}
    log = fake_openems(monkeypatch)
    build_csx(spec, 1, 1e-9)
    assert any(n == "CreateNF2FFBox" for n, _, _ in log)
    with pytest.raises(ValueError):
        build_csx({**spec, "nf2ff": {"f_hz": [2e9] * (EMISSION_NF2FF_MAX + 1), "center": [0, 0, 0]}}, 1, 1e-9)
    plain = {k: v for k, v in exc.items() if k != "emission"}
    with pytest.raises(ValueError):
        build_csx({**spec, "excitation": plain, "nf2ff": {"f_hz": grid[:12], "center": [0, 0, 0]}}, 1, 1e-9)


def test_the_near_field_plane_sits_1_5_mm_over_the_lid_at_the_harmonics(tmp_path, monkeypatch):  # design 5.8
    pj = emission_project(tmp_path / "e", LPF, "U1.1", "J1.1", lid_height=2.5)
    s = built(pj, near_field=True)[4].spec
    near, plate = s["near_field"], s["metal"]["lid"]["plate"]["z"]
    assert near["start"][2] == near["stop"][2] == round(plate + 1.5, 6)
    assert near["f_hz"] == harmonics_hz(915e6, 4.575e9)
    log = fake_openems(monkeypatch)
    build_csx(s, 1, 1e-9)
    assert ("AddDump", ("near_field",), {"dump_type": 11, "file_type": 1, "frequency": near["f_hz"],
                                         "over_sampling": 4}) in log
    assert ("AddBox", (near["start"], near["stop"]), {}) in log


def test_an_emission_air_box_under_a_quarter_wave_is_flagged(tmp_path):  # design 5.6: the air gap
    notes = built(emission_project(tmp_path / "e"), air_gap_mm=20.0)[3]
    assert ("W_EMISSION_AIR_BOX", {"gap_mm": "20.0", "quarter_mm": f"{air_gap(1.83e9):.1f}",
                                   "boundary": "pml_8"}) in notes


def test_the_shields_the_one_lid_leaves_out_are_named_in_the_emission_twin(tmp_path):  # design 5.6; AR-11
    def frame(ref, x, y, s):  # a shield: GND pads at the corners of an s mm square, around a part's pad
        corners = enumerate(((0, 0), (s, 0), (0, s), (s, s)), 1)
        return fp(ref, "Lib:Shield", *(smd(k, "GND", x=dx, y=dy) for k, (dx, dy) in corners), at=f"{x} {y}")

    lib = "Resistor_SMD:R_0402_1005Metric"  # the antenna's test's two shields
    shields = (frame("SH1", 108, 104, 8) + fp("R9", lib, smd(1, "N9"), smd(2, "GND", x=1), at="112 108", value="1k")
               + frame("SH2", 116, 116, 4) + fp("R8", lib, smd(1, "N8"), smd(2, "GND", x=1), at="117.5 118", value="1k"))
    board = tmp_path / "shields.kicad_pcb"
    board.write_text(IFA.read_text(encoding="utf-8").rstrip()[:-1] + shields + ")\n", encoding="utf-8")
    notes = pipeline.load(emission_project(tmp_path / "p", board, "U1.1", "AE1.1", lid_height=1.5))[3]
    assert ("W_EMISSION_LIDS_LEFT_OUT", {"ref": "SH1", "refs": "SH2"}) in notes
    assert "W_LIDS_LEFT_OUT" not in [c for c, _ in notes]
