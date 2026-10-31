# SPDX-License-Identifier: GPL-3.0-or-later
import json

import numpy as np
import pytest

import p3
import p3c
from kicad_rf_studio.core.project import load_project
from test_p3 import gates  # noqa: F401 (the fixture)


@pytest.fixture(autouse=True)
def nothing_raised(monkeypatch):  # the gates' own RAISED, set at a checkpoint, never reaches a test
    monkeypatch.setattr(p3c, "RAISED", {"ifa2g4": {}, "meander915": {}})


def test_the_variants_edits(monkeypatch):  # rulings 2, 3; r2 Q3; RAISED per fixture
    base = {"air_gap_mm": 31.228381, "mesh": {"n": 2}, "preset": "normal", "t_max_s": 3e-8}
    assert p3c.edits("ifa2g4-sheet-n3", base) == {"copper": "sheet", "mesh.n": 3, "gates.fit2d_limit": 0.05}
    assert p3c.edits("meander915-solid-n4", base) == {"copper": "solid", "mesh.n": 4}  # passes fit2d at every n
    assert p3c.edits("ifa2g4-solid-gap2", base) == {"copper": "solid", "air_gap_mm": 62.456762}
    assert p3c.edits("ifa2g4-solid-strict", base) == {"copper": "solid", "preset": "strict"}  # mesh.n stays 2
    assert p3c.edits("ifa2g4-solid-mur", base) == {"copper": "solid", "boundary": "mur", "air_gap_mm": 62.456762}
    monkeypatch.setattr(p3c, "RAISED", {"ifa2g4": {}, "meander915": {"t_max_s": 1.2e-7, "flat_s": 4.4e-8}})
    assert p3c.edits("meander915-sheet-gap2", base) == {"copper": "sheet", "air_gap_mm": 62.456762,
                                                         "t_max_s": 1.2e-7, "flat_s": 4.4e-8}


def test_p3c_runs_its_steps_through_the_product(gates):  # design 5.11; ruling 4
    assert p3c.main(["--out", str(gates), "--steps", "ifa2g4-solid-n2,ifa2g4-solid-strict,ifa2g4-solid-free"]) == 0
    n2, free = p3.measure(gates, "ifa2g4-solid-n2"), p3.measure(gates, "ifa2g4-solid-n2", "free")
    assert free["t_max"] == max(30e-9, 3 * max(j["t_stop"] for j in n2["jobs"]))
    strict = load_project(p3.project_path(gates, "ifa2g4-solid-strict"))
    assert (strict["preset"], strict["mesh"]["n"], strict["copper"]) == ("strict", 2, "solid")
