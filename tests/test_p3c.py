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


F = np.linspace(2.3e9, 2.5e9, 201)


def run(f_res=2.4e9, depth=-12.0, d=2.57, eta=0.81, verdict="converged"):
    s11 = 10 ** ((depth + 8 * ((F - f_res) / 50e6) ** 2) / 20) + 0j
    return {"f_hz": F, "s11": s11, "band": [2.4e9, 2.4835e9], "d_dbi": d, "far_f_hz": [2.44175e9] * 11,
            "eta_rad": [eta] * 11, "jobs": [{"verdict": verdict, "t_stop": 9.85e-9}]}


def shallow(tilt_db=0.0):  # a broad -5.9 dB minimum at 2.4 GHz (the fixture's, first run), tilted per 100 MHz,
    x = (F - 2.4e9) / 100e6  # its phase turning as the first run's (a 1 % shift moves S11 by about 0.14 in band)
    return {**run(), "s11": 10 ** ((-5.9 + 0.5 * x ** 2 + tilt_db * x) / 20) * np.exp(-2j * np.pi * F * 1.7e-9)}


def free(growth=0.1, t_stop=30e-9, finite=True):
    return {"growth_db": growth, "t_max": 30e-9, "t_stop": t_stop, "finite": finite}


def full(**over):  # every step of both fixtures, every default kept, sheet winning
    m = {}
    for fx in p3c.FIXTURES:
        for cu in p3c.COPPERS:
            m |= {f"{fx}-{cu}-{s}": run(f_res=2.4e9 * (1 + {"n2": 0, "n3": -0.001, "n4": -0.0015}.get(s, 0)))
                  for s in p3c.SETTINGS}
            m[f"{fx}-{cu}-free"] = free()
            if fx == "ifa2g4":
                m[f"ifa2g4-{cu}-mur"], m[f"ifa2g4-{cu}-murfree"] = run(), free(growth=16.0)  # P3-A's twin rose 16 dB
    return m | over


def test_the_extrapolation_takes_the_observed_order_capped_at_1():  # r2 Q3: order 1 is conservative only at p ≥ 1
    def f(n, p, f_inf=2.4e9, c=0.02):
        return f_inf * (1 + c / n ** p)
    assert p3c.extrapolated([f(n, 1) for n in (2, 3, 4)])[:2] == (pytest.approx(2.4e9), "monotone")
    assert p3c.extrapolated([f(n, 1) for n in (2, 3)]) == (pytest.approx(2.4e9), "two meshes", None)
    assert p3c.extrapolated([f(n, 0.5) for n in (2, 3, 4)]) == (
        pytest.approx(2.4e9), "monotone", pytest.approx(0.5, abs=1e-3))  # p < 1: the larger correction
    assert p3c.extrapolated([f(n, 0.5) for n in (2, 3)], p=0.5)[0] == pytest.approx(2.4e9)  # the 2.4 GHz fixture's order
    assert p3c.extrapolated([f(n, 2) for n in (2, 3, 4)])[0] == pytest.approx(f(4, 2) + 3 * (f(4, 2) - f(3, 2)))  # 1 binds
    assert p3c.extrapolated([2.400e9, 2.401e9, 2.403e9])[1] == "not converging"
    assert p3c.extrapolated([2.40e9, 2.39e9, 2.395e9]) == (2.395e9, "oscillating", None)


def test_the_p3c_rules_keep_every_default_on_good_runs():  # design 5.11
    d = p3c.decide(full())
    assert d["decisions"] == {"copper": "sheet", "mesh_n": 2, "gap_factor": 1, "preset": "normal",
                              "boundary": "pml_8", "t_max": "kept", "flat": "kept"}
    assert d["checks"]["mur"]["ifa2g4"]["report_only"] and d["verdict"] == {"value": "pass", "fails": []}
    mesh = d["checks"]["mesh"]["ifa2g4"]
    assert (mesh["kind"], mesh["p"], mesh["value"]) == ("monotone", pytest.approx(1.0, abs=1e-3), pytest.approx(0.003, abs=1e-4))


def test_each_failed_check_raises_its_default():  # design 5.11's fallbacks; RF 3
    late = full(**{f"ifa2g4-{cu}-n2": run(f_res=2.43e9) for cu in p3c.COPPERS})  # 1.6 % off the extrapolation
    assert p3c.decide(late)["decisions"]["mesh_n"] == 3
    assert p3c.decide(full(**{"meander915-sheet-gap2": run(d=2.36)}))["decisions"]["gap_factor"] == 2  # ΔD 0.21 dB
    assert p3c.decide(full(**{"meander915-sheet-gap2": run(d=2.38)}))["decisions"]["gap_factor"] == 1  # 0.19 dB
    assert p3c.decide(full(**{"meander915-sheet-gap2": run(f_res=2.3951e9)}))["decisions"]["gap_factor"] == 2  # -0.204 %
    assert p3c.decide(full(**{"ifa2g4-sheet-strict": run(eta=0.81 * 10 ** -0.006)}))["decisions"]["preset"] == "strict"
    assert p3c.decide(full(**{"meander915-sheet-n2": run(f_res=2.4121e9)}))["decisions"]["copper"] == "solid"  # 0.504 %
    assert p3c.decide(full(**{"meander915-sheet-n2": run(f_res=2.3881e9)}))["decisions"]["copper"] == "sheet"  # -0.496 %
    grew = p3c.decide(full(**{"ifa2g4-sheet-free": free(growth=6.1)}))
    assert grew["checks"]["pml"]["pass"] is False and grew["verdict"]["value"] == "blocked"  # MUR's own run grew too
    assert p3c.decide(full(**{"ifa2g4-sheet-free": free(growth=6.1), "ifa2g4-sheet-murfree": free()}))[
        "decisions"]["boundary"] == "mur"
    meander = {"meander915-sheet-free": free(growth=6.1), "ifa2g4-sheet-murfree": free()}
    assert p3c.decide(full(**meander))["verdict"]["value"] == "incomplete"  # the meander's own MUR run is needed
    assert p3c.decide(full(**meander, **{"meander915-sheet-mur": run(), "meander915-sheet-murfree": free()}))[
        "decisions"]["boundary"] == "mur"


def test_an_unconditioned_miss_within_its_shift_equivalent_is_explained():  # ruling 1, amended at commit
    d = p3c.decide(full(**{f"ifa2g4-{cu}-{s}": shallow() if s in ("n3", "n4") else shallow(-0.6)
                           for cu in p3c.COPPERS for s in p3c.SETTINGS}))
    mesh = d["checks"]["mesh"]["ifa2g4"]
    assert (mesh["pass"], mesh["explained"], mesh["kind"]) == (False, True, "oscillating")
    assert mesh["ds11"] < 0.05 < 0.1 < mesh["ds11_shift"]  # |dS11| about 0.03 against a 1 % shift's 0.14
    assert d["decisions"]["copper"] == "sheet" and d["decisions"]["mesh_n"] == 2
    copper = p3c.decide(full(**{"meander915-solid-n2": shallow(), "meander915-sheet-n2": shallow(-2.0)}))
    c = copper["checks"]["copper"]["meander915"]  # |dS11| about 0.09 against a 0.5 % shift's 0.07
    assert c["explained"] is False and c["ds11"] > c["ds11_shift"] and copper["decisions"]["copper"] == "solid"
    near = p3c.decide(full(**{"meander915-solid-n2": shallow(), "meander915-sheet-n2": shallow(-0.6)}))
    assert near["checks"]["copper"]["meander915"]["explained"] is True and near["decisions"]["copper"] == "sheet"


def test_a_run_at_t_max_or_flat_is_no_converged_comparison():  # RF 4; design 5.4
    d = p3c.decide(full(**{"meander915-sheet-n2": run(verdict="t_max")}))
    assert d["checks"]["copper"]["meander915"]["pass"] is None and d["checks"]["converged"]["pass"] is False
    assert d["decisions"]["t_max"] == "raised" and d["verdict"]["value"] == "incomplete"
    flat = p3c.decide(full(**{"ifa2g4-sheet-gap2": run(verdict="flat")}))
    assert flat["checks"]["gap"]["ifa2g4"]["pass"] is None and flat["decisions"]["flat"] == "widened"
    assert flat["verdict"]["value"] == "incomplete"


def test_a_raised_t_max_stays_a_decision_after_its_rerun(monkeypatch):  # design 5.4
    monkeypatch.setattr(p3c, "RAISED", {"ifa2g4": {}, "meander915": {"t_max_s": 1.2e-7}})
    d = p3c.decide(full())
    assert d["decisions"]["t_max"] == "raised" and d["verdict"] == {"value": "defaults raised", "fails": ["t_max"]}


def test_a_missing_step_is_not_run_never_a_pass():
    d = p3c.decide({"ifa2g4-solid-n2": run()})  # decide reads m.get(name)
    assert d["checks"]["copper"]["ifa2g4"]["pass"] is None and d["verdict"]["value"] == "incomplete"


def test_the_2g4_edits_p3d_applies():  # ruling 2; P3-D and P3-E take P3-C's defaults
    assert p3c.edits_2g4({"copper": "sheet", "mesh_n": 3, "gap_factor": 2, "preset": "normal", "boundary": "pml_8"},
                         31.228381) == {"copper": "sheet", "mesh.n": 3, "gates.fit2d_limit": 0.05,
                                        "air_gap_mm": 62.456762}


def test_the_projected_stop_from_the_residuals_decay(tmp_path):  # ruling 9: T_max raised from the decay
    events = [{"kind": "progress", "code": "I_PROGRESS", "job": 1,
               "params": {"t_ns": f"{t:.2f}", "residual_db": f"{-0.5 * t:.1f}"}} for t in range(40, 80)]
    (tmp_path / "events.jsonl").write_text("\n".join(map(json.dumps, events)), encoding="utf-8")
    assert p3c.projected_stop(tmp_path, -60.0, 20e-9) == pytest.approx(120e-9, rel=1e-3)  # -0.5 dB/ns from -39.5 dB
    flat = [{**e, "params": {**e["params"], "residual_db": "-30.0"}} for e in events]
    (tmp_path / "events.jsonl").write_text("\n".join(map(json.dumps, flat)), encoding="utf-8")
    assert p3c.projected_stop(tmp_path, -60.0, 20e-9) is None


def test_the_fit2d_probe_reads_each_section_on_the_projects_own_mesh(gates):  # ruling 2; the reviser's probe
    for n, errs in ((2, (0.0099, 0.0031)), (3, (0.0413, 0.0075))):  # RF's 0.6 mm and 1.35 mm sections
        pj = p3.variant(gates, f"ifa2g4-solid-n{n}", "ifa2g4", {"copper": "solid", "mesh.n": n})
        probe = sorted(p3c.fit2d_probe(pj), key=lambda s: s["width"])
        assert [(s["net"], s["width"], s["err"]) for s in probe] == [
            ("RF", pytest.approx(width), pytest.approx(err, abs=5e-5)) for width, err in zip((0.6, 1.35), errs)]


def test_p3c_writes_its_report_from_the_recorded_steps(gates):  # design 5.11; RF 2
    assert p3c.main(["--out", str(gates), "--steps", "ifa2g4-solid-n2,ifa2g4-solid-strict"]) == 0
    assert p3c.main(["--out", str(gates)]) == 0
    text = (gates / "p3c" / "p3c.json").read_text(encoding="utf-8")
    result = json.loads(text)
    assert result["verdict"]["value"] == "incomplete" and isinstance(result["checks"]["preset"]["ifa2g4"]["value"], float)
    assert '"s11"' not in text and '"f_hz"' not in text
    assert (gates / "p3c" / "p3c.md").read_text(encoding="utf-8").startswith("## P3C-1")
