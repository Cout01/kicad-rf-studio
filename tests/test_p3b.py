# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import json
import re
import subprocess
import sys

import pytest
import shapely
from shapely.geometry import Polygon

import p0
import p3b_hand
from test_cli_antenna import antenna_project
from kicad_rf_studio.core.project import load_project

BOARD = p0.FIX / "ifa2g4.kicad_pcb"


def modules(nodes) -> set[str]:
    """The top-level package of every import among `nodes`."""
    return {(a.name if isinstance(n, ast.Import) else n.module).split(".")[0]
            for n in nodes if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}


def test_the_hand_model_imports_none_of_the_product():  # ruling 7; design 5.11 P3-B: independent
    tree = ast.parse((p0.ROOT / "tools" / "p3b_hand.py").read_text(encoding="utf-8"))
    assert not modules(ast.walk(tree)) & {"kicad_rf_studio", "p0", "p3", "p3a", "p3b"}
    assert not modules(tree.body) & {"CSXCAD", "openEMS"}  # only inside mesh() and run(), in the child


def test_the_hand_antenna_is_the_footprints_polygon():  # r1 Q2: 12 rectangles, XOR the 0.3 mm drill's keyhole
    text = BOARD.read_text(encoding="utf-8")
    i = text.index("(fp_poly", text.index('(footprint "RF_Antenna:Texas_SWRA117D_2.4GHz_Left"'))
    xy = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", text[i:text.index("(stroke", i)])
    drawn = Polygon([(100 + float(x), -(100 + float(y))) for x, y in xy])  # AE1 at (100, 100), angle 0; y up
    assert len(xy) == 53 and shapely.area(shapely.symmetric_difference(drawn, p3b_hand.antenna())) <= 0.08
    assert p3b_hand.antenna().difference(p3b_hand.copper()["F.Cu"]).area <= 1e-9  # on the top copper


def test_the_hand_port_spans_the_pads_gap_on_the_top_copper():  # r1 Q3: exactly the gap, no snapping
    start, stop = p3b_hand.port()
    assert (start, stop) == ([99.03, -112.95, 0.745], [99.7, -111.0, 0.78])
    pads = p3b_hand.pads()
    assert pads["U1.2"].bounds[2] == pytest.approx(99.03) and pads["U1.1"].bounds[0] == pytest.approx(99.7)


def test_the_hand_settings_are_pre_registered(tmp_path):  # r1 R4: frozen before any run, its sha in the reference
    assert p3b_hand.WALL_MM == round(299792458 / 2.4e9 / 2 * 1e3, 6)
    assert p3b_hand.F11 == load_project(antenna_project(tmp_path))["far_field"]["f_hz"]  # the product's 11
    rods = p3b_hand.rods()  # the 35 vias and AE1.2's plated hole, the IFA's short (the product's 36 rods)
    assert len(rods) == 36 and (102.1, -100.0) in rods and BOARD.read_text(encoding="utf-8").count("thru_hole") == 1
    assert len(p3b_hand.script_sha()) == 64


@pytest.mark.openems
def test_the_hand_mesh_is_fine_on_the_antenna_and_its_walls_at_half_a_wavelength(tmp_path):  # r1 Q4
    out = tmp_path / "mesh.json"  # mesh() imports CSXCAD's smoother, so it runs in a child: pytest never loads it
    done = subprocess.run([sys.executable, "-X", "utf8", str(p0.ROOT / "tools" / "p3b_hand.py"), "--mesh", str(out)],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    m = json.loads(out.read_text(encoding="utf-8"))
    assert m["x"][0] == pytest.approx(87.0 - p3b_hand.WALL_MM) and m["y"][-1] == pytest.approx(-94.0 + p3b_hand.WALL_MM)
    start, stop = p3b_hand.port()
    for axis, v in [*zip("xyz", start), *zip("xyz", stop)]:  # the port's edges on mesh lines
        assert min(abs(v - line) for line in m[axis]) <= 1e-6
    fine = [b - a for a, b in zip(m["x"], m["x"][1:]) if 88.15 <= a and b <= 102.55]
    assert max(fine) <= 0.2 + 1e-6 and 1.0e6 <= len(m["x"]) * len(m["y"]) * len(m["z"]) <= 1.6e6
    assert "CSXCAD" not in sys.modules
