# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import p0
from kicad_rf_studio import runs
from kicad_rf_studio.core.post.waves import layout
from kicad_rf_studio.core.project import load_project
from p0b import emerge_app, harness
from test_p0 import in_process


def test_the_frequencies_hold_f0_its_harmonics_and_f2():  # D-43
    f = emerge_app.freqs(915e6, 3.0195e9)
    assert len(f) == 24 and {915e6, 1830e6, 2745e6} <= set(f.tolist()) and (f[0], f[-1]) == (457.5e6, 3.0195e9)


def test_the_export_cuts_each_port_face_from_the_models_own_copper(p0_out, monkeypatch):  # D-42; r6 §4.3
    monkeypatch.setattr(p0, "cli", in_process)
    data = emerge_app.export(harness.project(p0_out, "B1"), p0_out)
    lpf = data["lpf915"]
    assert [fc["name"] for fc in lpf["faces"]] == ["P1", "P2", "C1", "L1", "C2", "C3"]
    assert [("xy"[fc["p"]], fc["sign"]) for fc in lpf["faces"]] == [
        ("y", 1.0), ("y", 1.0), ("x", 1.0), ("x", 1.0), ("y", -1.0), ("y", -1.0)]
    assert lpf["faces"][0]["line"][1] == pytest.approx(-99.7231, abs=1e-3)  # P1's reference: the GND pour's edge
    assert len(lpf["labels"]) == len(lpf["spec"]["metal"]["copper"]) and len(lpf["rods"]) == 36
    assert set(data["coupons"]) == {"coupon_ms", "coupon_gcpw"} and (p0_out / "emerge" / "input.json").is_file()


def test_the_emerge_verdict_follows_d43():  # D-43, D-44
    ok = {"ds21_db_f0": 0.05, "ds11_f0": 0.01, "ds_max": 0.02, "nulls": []}
    coupons = [{"name": "coupon_ms", "dz0_pct": -1.08, "deeff_pct": 0.14},
               {"name": "coupon_gcpw", "dz0_pct": -4.03, "deeff_pct": 0.40}]  # r6 at 50 µm
    assert emerge_app.verdict(ok, coupons, 0.004, 1.0018, 0.008) == ("pass", [])
    assert emerge_app.verdict({**ok, "ds_max": 0.031}, coupons, 0.004, 1.0018, 0.008) == ("fail", [])
    miss = [coupons[0], {**coupons[1], "dz0_pct": -5.2}]
    assert emerge_app.verdict(ok, miss, 0.004, 1.0018, 0.008) == ("inconclusive", ["coupon_gcpw z0 -5.20 %"])
    assert emerge_app.verdict(ok, coupons, 0.012, 1.0018, 0.008) == ("inconclusive",
                                                                     ["chain moved 0.0120 from 75 to 60 um"])
    assert emerge_app.verdict(None, coupons, None, 1.0018, 0.008, ["60 um"]) == ("inconclusive",
                                                                                 ["EMerge 60 um not solved"])


def test_an_nport_solve_waits_for_free_ram(tmp_path, monkeypatch):  # r6 §6: the 60 µm level peaks near 20 GB
    monkeypatch.setattr(runs, "free_ram_mb", lambda: 15000.0)
    with pytest.raises(SystemExit):
        emerge_app.fem(tmp_path, "nport", "--edge-um", "60")


def test_a_fem_step_runs_the_script_isolated_in_the_emerge_folder(tmp_path, monkeypatch):  # D-41, PF-37
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append((cmd, kw)) or SimpleNamespace(
        returncode=3, stderr="one\ntwo\n"))
    assert emerge_app.fem(tmp_path, "coupon", "--name", "coupon_ms", "--out", "coupon_ms-50.json") == {
        "exit": 3, "output": "coupon_ms-50.json", "stderr": "one\ntwo"}
    ((cmd, kw),), e = calls, tmp_path / "emerge"
    assert cmd[1:4] == ["-I", str(p0.ROOT / "tools" / "p0b" / "emerge_fem.py"), "coupon"] and kw["cwd"] == e
    assert {kw["env"][name] for name in ("TEMP", "TMP", "TMPDIR")} == {str(e / "tmp")}  # Git Bash sets TMPDIR


def test_the_fem_script_compiles_and_never_imports_the_app():  # D-41, D-55
    text = (p0.ROOT / "tools" / "p0b" / "emerge_fem.py").read_text(encoding="utf-8")
    compile(text, "emerge_fem.py", "exec")
    assert "kicad_rf_studio" not in text and "import p0" not in text
    requirements = (p0.ROOT / "tools" / "p0b" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert requirements[0] == "# SPDX-License-Identifier: GPL-3.0-or-later" and "emerge==3.0.0b3" in requirements


def test_a_coupon_moves_to_the_10h_box_only_when_its_45h_solve_fails(p0_out, monkeypatch):  # OI-7, PF-35
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    e = p0_out / "emerge"
    e.mkdir(parents=True)
    (e / "input.json").write_text("{}", encoding="utf-8")
    ran = []

    def fem(out, mode, *args):  # coupon_gcpw's 45 h solve exits 1; every other solve leaves its output
        name = args[args.index("--out") + 1]
        ran.append((mode, name, args[args.index("--box") + 1] if "--box" in args else None))
        if name != "coupon_gcpw-50.json":
            (e / name).write_text("{}", encoding="utf-8")
        return {"exit": int(name == "coupon_gcpw-50.json"), "output": name}

    monkeypatch.setattr(emerge_app, "fem", fem)
    assert emerge_app.fem_steps(p0_out) == []
    assert ran == [("coupon", "coupon_ms-50.json", None), ("coupon", "coupon_gcpw-50.json", None),
                   ("coupon", "coupon_gcpw-50-10h.json", "10"), ("nport", "lpf915-75.npz", None),
                   ("nport", "lpf915-60.npz", None)]
    (e / "coupon_ms-50.json").unlink()  # its step's record stays; its output is gone
    ran.clear()
    assert emerge_app.fem_steps(p0_out) == [] and ran == [("coupon", "coupon_ms-50-10h.json", "10")]


def test_a_fem_step_reruns_after_a_fix_to_its_script_or_its_requirements(p0_out, monkeypatch, tmp_path):
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    (p0_out / "emerge").mkdir(parents=True)
    (p0_out / "emerge" / "input.json").write_text("{}", encoding="utf-8")
    ran = []
    monkeypatch.setattr(emerge_app, "fem", lambda out, mode, *args: ran.append(mode) or {"exit": 0, "output": "x"})
    for name in ("FEM", "REQUIREMENTS"):
        (tmp_path / name).write_bytes(b"1\n")
        monkeypatch.setattr(emerge_app, name, tmp_path / name)

    def step():
        emerge_app._fem_step(p0_out, "p0b-emerge-nport-75", "nport", "--out", "lpf915-75.npz")

    step()
    (tmp_path / "FEM").write_bytes(b"1\r\n")  # a checkout under core.autocrlf
    step()  # the same input.json and scripts (a fix elsewhere in tools/, a checkout's CRLF): the record is kept
    for name in ("FEM", "REQUIREMENTS"):
        (tmp_path / name).write_bytes(b"2\n")  # a fix to it
        step()
    assert ran == ["nport"] * 3


@pytest.fixture
def fakes(p0_out, monkeypatch):
    """emerge_app.main on fakes up to harness.write's records check: no venv, an input.json of {}, a cross-check that
    writes emerge.json with a "pass", P0-B's own steps, measure, decide and tables empty, and a fem that leaves its
    output. Returns `exits`: by output name, the fem's exit code instead of 0 (no output then), or what it raises."""
    monkeypatch.setattr(p0, "command_lines", lambda: [])
    monkeypatch.setattr(emerge_app, "venv", lambda e: None)
    monkeypatch.setattr(emerge_app, "export", lambda pj, out: p0.save(out / "emerge" / "input.json", {}))
    monkeypatch.setattr(emerge_app, "cross_check",
                        lambda out: p0.save(out / "p0b" / "emerge.json", {"verdict": "pass"}))
    for name, value in (("STEPS", ()), ("measure", lambda out: {}), ("decide", lambda m: {}),
                        ("tables", lambda result: "")):
        monkeypatch.setattr(harness, name, value)
    exits = {}

    def fem(out, mode, *args):
        name = args[args.index("--out") + 1]
        if isinstance(code := exits.get(name, 0), Exception):
            raise code
        if not code:
            (out / "emerge" / name).write_text("{}", encoding="utf-8")
        return {"exit": code, "output": name}

    monkeypatch.setattr(emerge_app, "fem", fem)
    return exits


def test_records_that_no_longer_apply_move_aside_before_the_gate_is_written(p0_out, fakes):  # PF-65's folder
    stale = ["p0b-emerge-coupon-coupon_ms-50-10h", emerge_app.NOMASK_FEM, emerge_app.NOMASK_OPENEMS]
    for sid in stale:  # made by other code; coupon_ms's 45 h step solves and the verdict is not "fail"
        p0.save(p0_out / "steps" / f"{sid}.json",
                {"step": sid, "key": "k@older", "code": "older", "wall_s": 1.0, "loaded": False})
    assert emerge_app.main(["run", "--out", str(p0_out)]) == 0
    assert json.loads((p0_out / "p0b" / "p0b.json").read_text(encoding="utf-8"))["machine"]["steps"] == 4
    assert sorted(path.stem for path in (p0_out / f"superseded-{date.today().isoformat()}").iterdir()) == sorted(stale)


def test_a_fem_step_left_unsolved_exits_1_once_the_gate_is_written(p0_out, fakes, capsys):
    fakes.update({"coupon_gcpw-50.json": 1, "lpf915-60.npz": 1})  # coupon_gcpw solves in its 10 h box; 60 µm does not
    assert emerge_app.main(["run", "--out", str(p0_out)]) == 1
    assert capsys.readouterr().out.endswith("emerge_app: failed: p0b-emerge-nport-60\n")
    assert all((p0_out / "p0b" / name).is_file() for name in ("emerge.json", "p0b.json"))


def test_a_fem_step_that_raises_is_logged_and_the_run_goes_on(p0_out, fakes, capsys):  # D-6
    fakes["lpf915-75.npz"] = OSError("no venv")
    assert emerge_app.main(["run", "--out", str(p0_out)]) == 1
    out, err = capsys.readouterr()
    assert "OSError: no venv" in err and out.endswith("emerge_app: failed: p0b-emerge-nport-75\n")
    assert (p0_out / "steps" / "p0b-emerge-nport-60.json").is_file()  # the next step still ran
    assert all((p0_out / "p0b" / name).is_file() for name in ("emerge.json", "p0b.json"))


def test_the_cross_check_closes_both_sides_as_d43_says(p0_out, monkeypatch):  # D-43: the plumbing, on the fake
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    assert harness.main(["--out", str(p0_out), "--only", "B1"]) == 0
    pj = harness.project(p0_out, "B1")
    data, e = emerge_app.export(pj, p0_out), p0_out / "emerge"
    project = load_project(pj)
    f = np.array(data["lpf915"]["freqs"])
    s = layout(project, project["results"], f=f).s  # EMerge as openEMS's own layout N-port
    for um in (75, 60):
        np.savez(e / f"lpf915-{um}.npz", f=f, s=s, names=np.array(["P1", "P2", "C1", "L1", "C2", "C3"]))
        p0.save(e / f"lpf915-{um}.json", {"sigma_max": 1.0, "recip": 0.0, "nodes": 1, "tets": 1, "t_s": 1.0,
                                          "peak_gb": 1.0, "emerge": "3.0.0b3"})
    for name, ref in data["coupons"].items():
        p0.save(e / f"{name}-50.json", {"name": name, "edge_um": 50, "z0": ref["z0_ref"], "eeff": ref["eeff_ref"]})
    (e / "freeze.txt").write_text("emerge==3.0.0b3\n", encoding="utf-8")
    out = emerge_app.cross_check(p0_out)
    assert out["compare_cbox"]["ds_max"] <= 1e-9 and out["reasons"] == [] and out["move"] == 0
    assert (p0_out / "p0b" / "emerge.json").is_file()
    assert out["compare_n3"] is None and out["deviations"] == [] and out["freeze"] == ["emerge==3.0.0b3"]  # PF-33
    # PF-35: a coupon with no 45 h row is read in the 10 h box against that box's 2D εeff, and named
    ref = data["coupons"]["coupon_gcpw"]
    (e / "coupon_gcpw-50.json").unlink()
    p0.save(e / "coupon_gcpw-50-10h.json", {"name": "coupon_gcpw", "edge_um": 50, "z0": ref["z0_ref"],
                                            "eeff": ref["eeff_ref_10h"]})
    out = emerge_app.cross_check(p0_out)
    assert out["deviations"] == ["coupon_gcpw: 10 h box (OI-7)"] and out["reasons"] == []
    assert out["coupons"][1]["eeff_ref"] == ref["eeff_ref_10h"] != ref["eeff_ref"]
    (e / "coupon_gcpw-50-10h.json").unlink()
    assert emerge_app.cross_check(p0_out)["reasons"] == ["EMerge coupon_gcpw 50 um not solved"]

    def fem(out, mode, *args):  # D-43's no-mask 6-port: here the masked one's files again
        for suffix in (".npz", ".json"):
            (e / f"lpf915-75-nomask{suffix}").write_bytes((e / f"lpf915-75{suffix}").read_bytes())
        return {"exit": 0, "output": args[args.index("--out") + 1]}

    monkeypatch.setattr(emerge_app, "fem", fem)
    emerge_app.nomask(p0_out)  # then openEMS's no-mask run, on the fake
    run = json.loads((p0_out / "steps" / "p0b-emerge-nomask-openems.json").read_text(encoding="utf-8"))["result"]
    spec = json.loads((p0.run_path(run["run_dir"]) / "model.json").read_text(encoding="utf-8"))
    assert [m["name"] for m in spec["materials"]] == ["substrate_0"] and len(run["jobs"]) == 6  # B1's, less its masks
    out = emerge_app.cross_check(p0_out)
    assert out["compare_nomask"] == out["compare"]  # the fake's network and C_box do not see the mask
    # a pair whose openEMS half ran on another B1 run, or whose EMerge half on another input.json, is stale
    b1, rec = Path(project["results"]["run_dir"]).name, p0_out / "steps" / "p0b-emerge-nomask-openems.json"
    text = rec.read_text(encoding="utf-8")
    rec.write_text(text.replace(f"|{b1}@", "|older@"), encoding="utf-8")
    assert emerge_app.cross_check(p0_out)["compare_nomask"] is None
    rec.write_text(text, encoding="utf-8")
    (e / "input.json").write_text((e / "input.json").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert emerge_app.cross_check(p0_out)["compare_nomask"] is None
