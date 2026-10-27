# SPDX-License-Identifier: GPL-3.0-or-later
import json
from pathlib import Path

import pytest

import p0
import p0b2
from kicad_rf_studio import pipeline
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.model.spec import strip_dl
from kicad_rf_studio.core.post.chain import loads, terminate, z_part
from kicad_rf_studio.core.post.waves import grid
from test_p0 import in_process
from test_p0b import skewed

F, _ = grid(915e6, 3, 1.1)


def test_fit_dl_gives_back_a_series_inductance():  # E-7: the fit the coupon check reads ΔL from
    s = skewed(F)[:, :3, :3]
    measured = terminate(s, [0, 1], loads({"L1": z_part("L", 6.8e-9 + 0.1243e-9, None, F)}, ["L1"], {"L1": 3e-15}, F), F)
    assert p0b2.fit_dl(s, F, {"L1": 3e-15}, {"L1": 6.8e-9}, "L1", measured) == pytest.approx(0.1243e-9, rel=1e-6)


@pytest.mark.parametrize(("verdicts", "dl_h", "ds21_db", "rule"), [
    (["converged"] * 7, 0.0870e-9, 0.02, (False, True)), (["converged"] * 7, 0.1616e-9, 0.0, (False, True)),
    (["converged"] * 7, 0.0869e-9, 0.0, (False, False)), (["converged"] * 7, 0.1617e-9, 0.0, (False, False)),
    (["converged"] * 7, 0.124e-9, 0.0201, (False, False)), (["converged"] * 6 + ["t_max"], 0.124e-9, 0.0, (True, False)),
    (["converged"] * 3, None, None, (True, False))])  # the co-simulation alone
def test_a10s_rule_is_e7s(verdicts, dl_h, ds21_db, rule):  # E-7: both parts, edges inclusive; void unless 7 converged
    assert p0b2.a10(verdicts, dl_h, ds21_db) == dict(zip(("void", "pass"), rule))


def test_the_single_l_coupon(tmp_path):  # E-7: coupon_gcpw_pads with an 0402 6.8 nH across a 1 mm cut of its line
    board = tmp_path / "coupon_gcpw_l.kicad_pcb"
    board.write_text(p0b2.single_l(p0b2.L_COUPON), encoding="utf-8")
    assert main(["new", str(board), *p0b2.COUPON, "-o", str(tmp_path / "proj")]) == 0
    project, b, geom, notes = pipeline.load(tmp_path / "proj" / "project.json")
    spec, chain = pipeline.build_model(project, b, geom).spec, project["chain"]
    assert (notes, [(q["ref"], q["value"], q["role"]) for q in chain["series"]], chain["shunt"], project["others"]) == (
        [], [("L1", "6.8nH", "port")], [], [])
    assert [(q["name"], q["part"], q["dir"]) for q in spec["ports"]] == [("P1", False, "y"), ("P2", False, "y"),
                                                                         ("L1", True, "x")]
    assert strip_dl(spec["ports"][2], [spec["mesh"][a] for a in "xyz"]) == pytest.approx(1.24283e-10, rel=1e-4)


def test_the_coupon_check_runs_verify_uncompensated_then_compensated(p0_out, monkeypatch):  # E-7; Review Focus 4
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)  # verify's cells: the fake's dump is empty
    r = p0b2.coupon(p0_out)
    steps = {s: json.loads((p0_out / "steps" / f"{s}.json").read_text(encoding="utf-8"))
             for s in ("a10-run", "a10-uncomp", "a10-comp")}
    grid_l = [next(g["L"] for g in json.loads((Path(steps[s]["result"]["verify"]["run_dir"]) / "model.json")
                                              .read_text(encoding="utf-8"))["grid"] if g["name"] == "L1")
              for s in ("a10-uncomp", "a10-comp")]
    assert grid_l == [pytest.approx(6.8e-9, rel=1e-6), pytest.approx(6.8e-9 - 1.24283e-10, rel=1e-6)]
    assert (r["dl_cf_h"], r["band_h"], r["verdicts"], r["void"]) == (
        pytest.approx(1.24283e-10, rel=1e-4), [0.0870e-9, 0.1616e-9], ["converged"] * 7, False)
    run = steps["a10-run"]
    assert steps["a10-comp"]["key"].startswith(f"{run['key'].split('@')[0]}|{run['result']['run_dir']}@")
    assert {k: v for k, v in json.loads((p0_out / "p0b2" / "a10.json").read_text(encoding="utf-8")).items()
            if k != "versions"} == r
    (p0_out / "steps" / "a10-comp.json").unlink()  # the compensated verify again, keeping no S this time
    monkeypatch.setenv("KRS_FAKE", "nan")
    r = p0b2.coupon(p0_out)
    assert (r["verdicts"], r["dl_fit_h"], r["void"], r["pass"]) == (["converged"] * 5, None, True, False)
    for s in ("a10-uncomp", "a10-comp"):  # the uncompensated verify keeping no S: the compensated one never runs
        (p0_out / "steps" / f"{s}.json").unlink()
    r = p0b2.coupon(p0_out)
    assert (r["verdicts"], r["void"], (p0_out / "steps" / "a10-comp.json").exists()) == (["converged"] * 3, True, False)
