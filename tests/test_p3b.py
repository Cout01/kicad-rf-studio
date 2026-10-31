# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import json
import re
import subprocess
import sys

import numpy as np
import pytest
import shapely
from shapely.geometry import Polygon

import p0
import p3b
import p3b_hand
from test_cli_antenna import antenna_project
from test_p3 import gates  # noqa: F401 (the fixture)
from kicad_rf_studio.core.project import load_project, save_project

BOARD = p0.FIX / "ifa2g4.kicad_pcb"
F = np.linspace(2.3e9, 2.5e9, 201)


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


def side(f_res=2.4e9, depth=-12.0, d=2.57, eta=0.81, verdict="converged"):  # a measure: a dip of `depth` dB at f_res
    s11 = 10 ** ((depth + 8 * ((F - f_res) / 50e6) ** 2) / 20) + 0j  # a parabola in dB: resonance() finds f_res
    return {"f_hz": F, "s11": s11, "band": [2.4e9, 2.4835e9], "d_dbi": d, "far_f_hz": [2.44175e9] * 11,
            "eta_rad": [eta] * 11, "jobs": [{"verdict": verdict}]}


def shallow(tilt_db=0.0, scale=1.0, tau=1.7e-9):  # a broad -5.9 dB minimum at 2.4 GHz (the fixture's, first run),
    f = F / scale  # tilted per 100 MHz, its frequency axis scaled, its phase turning over tau s (the first run's)
    x = (f - 2.4e9) / 100e6
    return {**side(), "s11": 10 ** ((-5.9 + 0.5 * x ** 2 + tilt_db * x) / 20) * np.exp(-2j * np.pi * f * tau)}


def m(hand=None, product=None, hit=True, decay=-45.0, xor=(0.5, 0.05), **diagnostics):
    return {"hand": {**(hand or side()), "criterion_hit": hit, "decay_db": decay}, "product": product or side(),
            "geometry": {"xor_mm2": {"F.Cu": xor[0], "B.Cu": xor[1]}}, **diagnostics}


def test_the_p3b_rules_inclusive_signed_and_conditioned():  # design 5.11; ruling 1; RF 3, 4
    assert p3b.decide(m())["verdict"] == {"value": "pass", "fails": [], "diagnosis": None}
    for change, fails in [({"product": side(f_res=2.4239e9)}, []), ({"product": side(f_res=2.4241e9)}, ["f_res"]),
                          ({"product": side(f_res=2.3761e9)}, []), ({"product": side(f_res=2.3759e9)}, ["f_res"]),
                          ({"product": side(d=2.272)}, []), ({"product": side(d=2.268)}, ["d"]),
                          ({"product": side(d=2.868)}, []), ({"product": side(d=None)}, ["d"]),
                          ({"product": side(eta=0.81 * 10 ** -0.0298)}, []),
                          ({"product": side(eta=0.81 * 10 ** -0.0302)}, ["eta"]),
                          ({"hit": False, "decay": -40.0}, []), ({"hit": False, "decay": -39.9}, ["valid"]),
                          ({"hit": False, "decay": 45.0}, ["valid"]),  # a grown run is no reference: signed
                          ({"product": side(verdict="t_max")}, ["valid"]),  # nor a product run cut at T_max
                          ({"xor": (1.01, 0.05)}, ["geometry"]), ({"xor": (0.99, 0.21)}, ["geometry"])]:
        assert p3b.decide(m(**change))["verdict"]["fails"] == fails
    explained = p3b.decide(m(hand=shallow(), product=shallow(-0.6)))  # the argmin 60 MHz away, |dS11| about 0.03
    e = explained["f_res"]  # a 1 % shift of the hand's S11 moves it by about 0.14 in band (the first run's slope)
    assert e["conditioned"] is False and e["ds11"] < 0.05 < 0.1 < e["ds11_shift"] < 0.2
    assert explained["verdict"] == {"value": "explained", "fails": [], "diagnosis": None}
    moved = p3b.decide(m(hand=shallow(), product=shallow(-5.0)))  # |dS11| about 0.20 in band: more than a 1 % shift
    assert moved["f_res"]["ds11"] > moved["f_res"]["ds11_shift"] and moved["verdict"]["fails"] == ["f_res"]
    turned = p3b.decide(m(hand=shallow(), product=shallow(scale=1.015)))  # a real 1.5 % shift
    assert turned["f_res"]["ds11"] > turned["f_res"]["ds11_shift"] and turned["verdict"]["fails"] == ["f_res"]
    edge = p3b.decide(m(product=side(f_res=2.52e9)))  # the product's lowest |S11| at the grid's end: no dip
    assert edge["f_res"]["conditioned"] is False and edge["verdict"]["fails"] == ["f_res"]


def test_a_p3b_fail_is_diagnosed_by_the_pre_registered_pairs():  # design 5.11: blocks until explained
    miss = m(product=side(f_res=2.43e9))  # a conditioned 1.25 % miss
    assert p3b.decide(miss)["verdict"] == {"value": "fail", "fails": ["f_res"], "diagnosis": None}  # none run yet
    assert p3b.decide({**miss, "product-mur": side(f_res=2.405e9)})["verdict"]["diagnosis"] == "boundary"
    assert p3b.decide({**miss, "product-mur": side(f_res=2.43e9), "hand-030": side(f_res=2.428e9)})[
        "verdict"]["diagnosis"] == "mesh"
    both = {**miss, "product-mur": side(f_res=2.43e9), "hand-030": side(f_res=2.4e9)}
    assert p3b.decide(both)["verdict"]["diagnosis"] == "product bug presumed"


def test_the_reference_is_refused_once_the_hand_model_changed(tmp_path, monkeypatch):  # design 5.11; ruling 7
    path = tmp_path / "references.json"
    monkeypatch.setattr(p3b, "REFERENCES", path)
    with pytest.raises(SystemExit):
        p3b.references()  # none committed yet: the product's side may not run
    path.write_text(json.dumps({"script_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(SystemExit):
        p3b.references()


def test_a_hand_run_is_kept_by_the_hand_modules_hash_alone(tmp_path, monkeypatch):  # RF 2; r1: not by the code's id
    p0.save(tmp_path / "p3b" / "hand" / "hand.json", {"script_sha256": p3b_hand.script_sha(), "wall_s": 1.0})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("a kept hand run ran again"))
    assert p3b.hand(tmp_path)["wall_s"] == 1.0


def test_the_hand_copper_matches_the_products_model(tmp_path):  # r1 Q2: the free pre-check, no openEMS
    pj = antenna_project(tmp_path)
    save_project(pj, {**load_project(pj), "copper": "solid"})  # P3-B's product side is solid copper (PRODUCT)
    g = p3b.geometry(pj)
    assert g["xor_mm2"]["F.Cu"] <= 1.0 and g["xor_mm2"]["B.Cu"] <= 0.2
    assert g["port"]["hand"] == [[99.03, -112.95, 0.745], [99.7, -111.0, 0.78]]
    assert g["port"]["product"] == [[98.98, -112.89812, 0.745], [99.787503, -111.07688, 0.78]]  # r1's probe


def test_p3b_runs_its_product_step_and_writes(gates, monkeypatch, tmp_path):  # design 5.11; the harness on the fake
    f = np.arange(1840, 2991) * 1e6
    monkeypatch.setattr(p3b, "REFERENCES", tmp_path / "references.json")
    p0.save(p3b.REFERENCES, {"script_sha256": p3b_hand.script_sha(), "f_hz": f.tolist(), "s11": [[0.5, 0.0]] * len(f),
                             "far": {"f_hz": [2.45e9, 2.4e9], "d_max": [1.8, 1.8], "p_rad": [1.0, 1.0],
                                     "p_acc": [1.25, 1.25], "eta_rad": [0.8, 0.8]},
                             "criterion_hit": True, "decay_db": -45.0, "cells": [1, 1, 1], "t_end": 1e-8, "wall_s": 1.0})
    assert p3b.main(["--out", str(gates), "--steps", "geometry,product"]) == 0
    assert p3b.main(["--out", str(gates)]) == 0
    text = (gates / "p3b" / "p3b.json").read_text(encoding="utf-8")
    assert '"s11"' not in text and '"f_hz"' not in text and json.loads(text)["decisions"]["verdict"]["value"]
    assert (gates / "p3b" / "p3b.md").read_text(encoding="utf-8").startswith("## P3B-1")
