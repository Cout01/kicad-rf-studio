# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import csv
import io
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import skrf
from matplotlib.figure import Figure

from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.post.chain import ideal_schematic
from kicad_rf_studio.core.post.outputs import (COLUMNS, LIMITS, OUTPUTS, marker_lines, port_map, summary_csv,
                                               summary_png, touchstone, write)
from kicad_rf_studio.core.post.waves import Layout, grid
from kicad_rf_studio.core.project import parts
from networks import read_s, star
from test_gates import project_of
from test_post_chain import PI, PI_Z

F0 = 915e6
F, _ = grid(F0, 3, 1.1)
EXT = [{"name": "P1", "part": False}, {"name": "P2", "part": False}]


def lay_of(ports, s, flipped=None):
    return Layout(F, [71, 213, 355], s, np.full(len(F), -3.0), ports, flipped or [False] * len(ports))


def test_touchstone_is_1_1_ascii_with_the_port_map_before_the_option_line(tmp_path):  # C-28
    data = touchstone(star(F, 6), F, ["P1", "P2", "C1", "L1", "C2", "C3"], ["port 3 C1: part 4,7µF", "two"])
    assert data.decode("ascii").splitlines()[:4] == [
        "! port 3 C1: part 4,7\\xb5F", "! two", f"! Created with skrf {skrf.__version__} (http://scikit-rf.org).",
        "# Hz S RI R 50.0 "]
    (tmp_path / "layout.s6p").write_bytes(data)
    assert np.abs(read_s(tmp_path / "layout.s6p") - star(F, 6)).max() == 0


def test_the_port_map_names_every_port_its_pads_c_box_polarity_and_the_terminated_parts():  # C-28, spec 6.3 flags
    p = copy.deepcopy(project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")[1])
    parts(p)["L1"]["s2p"] = {"file": "../parts/l1.s2p", "connection": "series"}
    results = {"run_dir": "/x/runs/lpf915-20261022-120000-ab12", "preset": "normal",
               "c_box": {"C1": 2.4e-15, "L1": 2.7e-15, "C2": 1.4e-15, "C3": 1.4e-15},
               "jobs": [{"port": "P1", "verdict": "converged", "residual_db": -61.0},
                        {"port": "P2", "verdict": "flat", "residual_db": -45.2}]}
    ports = [{"name": n, "part": n[0] != "P"} for n in ("P1", "P2", "C1", "L1", "C2", "C3")]
    lay = lay_of(ports, star(F, 6), [False, False, False, True, False, False])
    layout_map, chain_map = port_map(p, results, lay, range(6)), port_map(p, results, lay, [0, 1])
    assert layout_map[0] == chain_map[0] == (
        "run lpf915-20261022-120000-ab12, preset normal: P1 converged, P2 flat at -45.2 dB")
    assert len(layout_map) == 7 and layout_map[1:5] == [
        "port 1 P1: external, signal U1.1, reference U1.2, as built",
        "port 2 P2: external, signal J1.1, reference J1.2, as built",
        "port 3 C1: part 100pF, signal C1.1, reference C1.2, C_box 2.4e-15 F, as built",
        "port 4 L1: part s2p ../parts/l1.s2p:series, signal L1.1, reference L1.2, C_box 2.7e-15 F, "
        "row and column negated"]
    assert chain_map[3:] == [
        "terminated C1: part 100pF, C_box 2.4e-15 F", "terminated L1: part s2p ../parts/l1.s2p:series, C_box 2.7e-15 F",
        "terminated C2: part 3.3pF, C_box 1.4e-15 F", "terminated C3: part 3.3pF, C_box 1.4e-15 F"]


def test_markers_give_il_rl_and_harmonic_rejection_with_the_excitation_level():  # C-30, spec 5.8
    chain = ideal_schematic(PI, PI_Z, F)  # the Butterworth pi of tests/test_post_chain.py
    lay = lay_of(EXT, chain)
    assert marker_lines(lay, chain, None) == [
        ("I_MARKER_TRACE", {"marker": "f0", "f_mhz": "915", "a_db": "-3.0", "il_db": "3.01", "rl_db": "3.01"}),
        ("I_MARKER_TRACE", {"marker": "2f0", "f_mhz": "1830", "a_db": "-3.0", "il_db": "18.13", "rl_db": "0.07"}),
        ("I_HR_TRACE", {"marker": "2f0", "hr_db": "15.1"}),
        ("I_MARKER_TRACE", {"marker": "3f0", "f_mhz": "2745", "a_db": "-3.0", "il_db": "28.63", "rl_db": "0.01"}),
        ("I_HR_TRACE", {"marker": "3f0", "hr_db": "25.6"})]
    assert marker_lines(lay, chain, chain)[0] == ("I_MARKER", {
        "marker": "f0", "f_mhz": "915", "a_db": "-3.0", "il_db": "3.01", "rl_db": "3.01", "il_ideal_db": "3.01",
        "rl_ideal_db": "3.01"})


def test_the_csv_is_one_row_per_grid_point():  # C-29
    chain = ideal_schematic(PI, PI_Z, F)
    lay = lay_of(EXT, chain)
    rows = list(csv.reader(io.StringIO(summary_csv(lay, chain, None, np.full(len(F), 0.01), 0.0045).decode("utf-8"))))
    assert rows[0] == list(COLUMNS) and len(rows) == len(F) + 1
    assert [rows[1 + k][1] for k in (70, 71, 213, 355)] == ["", "f0", "2f0", "3f0"]
    assert float(rows[72][0]) == F0 and float(rows[72][5]) == pytest.approx(-3.0103, abs=1e-4)
    assert rows[72][7:11] == ["", "", "", ""] and (float(rows[72][13]), float(rows[72][14])) == (0.01, 0.0045)
    both = list(csv.reader(io.StringIO(summary_csv(lay, chain, chain, np.zeros(len(F)), 0.0).decode("utf-8"))))
    assert both[72][9] == both[72][5]


def test_the_png_draws_on_agg_and_leaves_no_pyplot_figure():  # C-30, spec 3.1
    chain = ideal_schematic(PI, PI_Z, F)
    assert summary_png(lay_of(EXT, chain), chain, chain, "lpf915")[:8] == b"\x89PNG\r\n\x1a\n"
    import matplotlib.pyplot
    assert matplotlib.pyplot.get_fignums() == []


def test_the_png_title_carries_the_what_if_label(monkeypatch):  # D-15
    titles = []
    monkeypatch.setattr(Figure, "suptitle", lambda self, text, **kw: titles.append(text))
    chain = ideal_schematic(PI, PI_Z, F)
    summary_png(lay_of(EXT, chain), chain, chain, "lpf915", label="L")
    summary_png(lay_of(EXT, chain), chain, chain, "lpf915")
    assert titles == [render("I_PLOT_TITLE", name="lpf915") + "\nL", render("I_PLOT_TITLE", name="lpf915")]


def test_only_the_png_writer_imports_matplotlib():  # C-5
    out = subprocess.run([sys.executable, "-I", "-c", "import sys, kicad_rf_studio.core.post.outputs; print(sorted("
                          "m for m in ('matplotlib', 'pandas') if m in sys.modules))"], capture_output=True, text=True)
    assert out.stdout.strip() == "[]"


def test_the_writer_replaces_only_its_own_files(tmp_path):  # C-27: a changed N leaves no stale file
    out = tmp_path / "p" / "results"
    out.mkdir(parents=True)
    for name in ("layout.s6p", "chain.s2p", "summary.csv", "notes.txt", "verify.s2p", "my.s2p"):
        (out / name).write_text("old")
    write(out, {"layout.s7p": b"7", "summary.csv": b"csv"}, OUTPUTS, "kicad-rf-studio retune p")
    assert {p.name: p.read_text() for p in out.iterdir()} == {
        "layout.s7p": "7", "summary.csv": "csv", "notes.txt": "old", "verify.s2p": "old", "my.s2p": "old"}
    write(tmp_path / "q" / "results", {"layout.s2p": b"2"}, OUTPUTS, "c")  # a folder that does not exist yet
    assert (tmp_path / "q" / "results" / "layout.s2p").read_bytes() == b"2"


@pytest.mark.parametrize(("fails", "held", "left"), [
    ("replace", "summary.csv", {"layout.s6p": "old", "summary.csv": "old"}),  # summaries first: nothing changed
    ("remove", "layout.s6p", {"layout.s6p": "old", "layout.s7p": "7", "summary.csv": "new"})])
def test_a_file_another_program_holds_is_a_coded_refusal(tmp_path, monkeypatch, fails, held, left):  # C-27, RF 1
    out = tmp_path / "results"
    out.mkdir()
    for name in ("layout.s6p", "summary.csv"):
        (out / name).write_text("old")
    real = getattr(os, fails)

    def refuse(*args):  # Windows refuses to replace or delete a file another program holds open
        if Path(args[-1]).name == held:
            raise PermissionError(13, "in use")
        real(*args)

    monkeypatch.setattr(os, fails, refuse)
    with pytest.raises(KrsError) as e:
        write(out, {"layout.s7p": b"7", "summary.csv": b"new"}, OUTPUTS, "kicad-rf-studio retune p")
    assert (e.value.code, e.value.params) == ("E_RESULTS_WRITE", {
        "path": str(out / held), "reason": "permission denied", "command": "kicad-rf-studio retune p"})
    assert {p.name: p.read_text() for p in out.iterdir()} == left  # no temporary file left


def test_the_stated_limits_are_nine_lines():  # spec 7.5, C-32
    assert len(LIMITS) == 9 and render(LIMITS[0]) == "Limit: no magnetic coupling between part bodies."
