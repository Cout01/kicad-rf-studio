# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.post.chain import with_box, z_part
from kicad_rf_studio.core.post.outputs import LIMITS
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import load_project, parts, save_project
from kicad_rf_studio.pipeline import assign, command_line
from networks import C_BOX, read_s, star, terminate_np, write_s2p
from test_cli_cost import fail
from test_gates import project_of
from test_post_chain import FB1, M0402
from test_run import coupon, lpf_loads, lpf_project, lpf_run

F, _ = grid(915e6, 3, 1.1)


def chain_of(pj):
    return read_s(pj.parent / "results" / "chain.s2p")


def test_retune_stores_a_value_and_rewrites_the_outputs_without_a_worker(tmp_path, calibrated, monkeypatch,
                                                                          capsys):  # spec 3.2, 7.2, C-17..C-19
    pj = lpf_run(tmp_path, monkeypatch)  # tests/test_run.py
    monkeypatch.setattr(subprocess, "Popen", fail)  # tests/test_cli_cost.py
    capsys.readouterr()
    assert main(["retune", str(pj), "C2=4.7pF"]) == 0
    assert (parts(load_project(pj))["C2"]["value"], parts(load_project(pj))["C2"]["s2p"]) == ("4.7pF", None)
    oracle = terminate_np(star(F, 6), [0, 1], lpf_loads(M0402, C2=4.7e-12))
    assert np.abs(chain_of(pj) - oracle).max() <= 1e-5
    assert b"! terminated C2: part 4.7pF, C_box 2e-14 F" in (pj.parent / "results" / "chain.s2p").read_bytes()
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("Results of the run in ") and out[-len(LIMITS):] == [render(c) for c in LIMITS]
    assert "openEMS" not in sys.modules
    board = pj.parent.parent / "lpf915.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n")  # re-saved in KiCad, its model unchanged: still not stale
    (pj.parent / "results" / "chain.s2p").unlink()
    assert main(["retune", str(pj)]) == 0 and np.abs(chain_of(pj) - oracle).max() <= 1e-5  # C-19: no assignment


def test_an_s2p_assignment_keeps_the_value_and_a_value_clears_it(tmp_path, calibrated, monkeypatch):  # C-17, C-18
    pj = lpf_run(tmp_path, monkeypatch)
    (tmp_path / "parts").mkdir()
    s2p = write_s2p(tmp_path / "parts" / "l1.s2p", z_part("L", 18e-9, None, F), "series", F)
    assert main(["retune", str(pj), f"L1={s2p}:series"]) == 0
    l1 = parts(load_project(pj))["L1"]
    assert (l1["value"], l1["s2p"]) == ("15nH", {"file": "../parts/l1.s2p", "connection": "series"})
    zk = lpf_loads(M0402)
    zk[:, 1] = with_box(z_part("L", 18e-9, None, F), F, C_BOX)
    assert np.abs(chain_of(pj) - terminate_np(star(F, 6), [0, 1], zk)).max() <= 1e-5
    assert main(["retune", str(pj), "L1=12nH"]) == 0
    assert (parts(load_project(pj))["L1"]["value"], parts(load_project(pj))["L1"]["s2p"]) == ("12nH", None)


def test_bad_assignments_are_refused_and_store_nothing(tmp_path, calibrated, monkeypatch, capsys):  # C-17, C-20, spec 8
    pj = lpf_run(tmp_path, monkeypatch)  # one run serves every case: a refusal stores nothing
    before, stamp = pj.read_bytes(), (pj.parent / "results" / "chain.s2p").stat().st_mtime_ns
    missing = pj.parent / "missing.s2p"
    for args, code, params in [
            (["C1"], "E_RETUNE_ARG", {"arg": "C1"}),
            (["C1=1pF", "C1=2pF"], "E_RETUNE_TWICE", {"ref": "C1"}),
            (["X9=1pF"], "E_RETUNE_UNKNOWN", {"ref": "X9", "refs": "C1, L1, C2, C3"}),
            (["R1=0R"], "E_RETUNE_ROLE", {"ref": "R1", "role": "copper"}),
            (["C4=1pF"], "E_RETUNE_ROLE", {"ref": "C4", "role": "open"}),
            (["C1=15nH"], "E_RETUNE_VALUE", {"ref": "C1", "value": "15nH"}),
            (["C1=part.s2p"], "E_RETUNE_VALUE", {"ref": "C1", "value": "part.s2p"}),
            (["C2=0"], "E_RETUNE_VALUE", {"ref": "C2", "value": "0"}),  # a C of 0 is an open: every output NaN
            ([f"C1={missing}:series"], "E_S2P_MISSING", {"ref": "C1", "path": str(missing)})]:
        capsys.readouterr()
        assert main(["retune", str(pj), *args]) == 2
        assert capsys.readouterr().err == render(code, **params) + "\n"
    assert pj.read_bytes() == before and (pj.parent / "results" / "chain.s2p").stat().st_mtime_ns == stamp


def test_a_part_with_no_kind_takes_only_an_s2p(tmp_path):  # C-15, M-5: FB1, a ferrite bead, has no ideal value
    p = copy.deepcopy(project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2.5")[1])
    p["chain"]["series"].append(dict(FB1))
    with pytest.raises(KrsError) as e:
        assign(p, ["FB1=4.7pF"], tmp_path)
    assert (e.value.code, e.value.params) == ("E_RETUNE_VALUE", {"ref": "FB1", "value": "4.7pF"})
    file = write_s2p(tmp_path / "fb1.s2p", np.full(len(F), 30 + 40j), "series", F)
    assert parts(assign(p, [f"FB1={file}:series"], tmp_path))["FB1"]["s2p"] == {"file": "fb1.s2p",
                                                                                "connection": "series"}


def test_a_single_trace_has_no_retune(tmp_path, calibrated, capsys):  # spec 7.3, C-21
    assert main(["retune", str(coupon(tmp_path)), "C1=1pF"]) == 2
    assert capsys.readouterr().err == render("E_RETUNE_NO_PARTS") + "\n"


def test_retune_needs_results_of_this_model(tmp_path, calibrated, monkeypatch, capsys):  # spec 7.8, C-22, C-23
    assert main(["retune", str(lpf_project(tmp_path))]) == 2
    assert capsys.readouterr().err == render("E_NO_RESULTS") + "\n"
    (tmp_path / "b").mkdir()  # lpf_project writes the board into a folder it never creates
    pj = lpf_run(tmp_path / "b", monkeypatch)
    save_project(pj, {**load_project(pj), "t_max_s": 30e-9})  # the excitation is in the model hash
    assert main(["retune", str(pj)]) == 2 and capsys.readouterr().err == render("E_RESULTS_STALE") + "\n"
    d = load_project(pj)
    d["t_max_s"] = 40e-9
    del d["results"]["loss_expected"]  # a run before this plan
    save_project(pj, d)
    assert main(["retune", str(pj)]) == 2 and capsys.readouterr().err == render("E_RESULTS_STALE") + "\n"


def test_a_csv_held_open_refuses_and_stores_nothing(tmp_path, calibrated, monkeypatch, capsys):  # Review Focus 1
    pj = lpf_run(tmp_path, monkeypatch)
    csv_file = pj.parent / "results" / "summary.csv"
    before, held, real = pj.read_bytes(), csv_file.read_bytes(), os.replace

    def replace(src, dst):
        if Path(dst).name == "summary.csv":
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    capsys.readouterr()
    assert main(["retune", str(pj), "C2=4.7pF"]) == 2
    command = command_line("kicad-rf-studio", "retune", str(pj), "C2=4.7pF")  # the rerun keeps the assignment
    assert capsys.readouterr().err == render("E_RESULTS_WRITE", path=str(csv_file), reason="permission denied",
                                             command=command) + "\n"
    assert "C2=4.7pF" in command and pj.read_bytes() == before and csv_file.read_bytes() == held


def test_a_windows_path_with_spaces_and_accents(tmp_path, calibrated, monkeypatch):  # Review Focus 4
    pj = lpf_run(tmp_path, monkeypatch)
    (tmp_path / "peça 1").mkdir()
    s2p = write_s2p(tmp_path / "peça 1" / "bobina ç.s2p", z_part("L", 18e-9, None, F), "series", F)
    assert main(["retune", str(pj), f"L1={s2p}:series", "C2=3,9pF"]) == 0  # on Windows the path has a drive letter
    d = load_project(pj)
    assert parts(d)["L1"]["s2p"] == {"file": "../peça 1/bobina ç.s2p", "connection": "series"}
    assert parts(d)["C2"]["value"] == "3,9pF"
    head = (pj.parent / "results" / "layout.s6p").read_bytes().split(b"#")[0]
    assert max(head) < 128 and b"part s2p ../pe\\xe7a 1/bobina \\xe7.s2p:series" in head


def test_a_deleted_run_folder_refuses_the_retune(tmp_path, calibrated, monkeypatch, capsys):  # Review Focus 5
    pj = lpf_run(tmp_path, monkeypatch)
    run_dir = Path(load_project(pj)["results"]["run_dir"])
    shutil.rmtree(run_dir)
    before = sorted(p.name for p in (pj.parent / "results").iterdir())
    capsys.readouterr()
    assert main(["retune", str(pj)]) == 2
    assert capsys.readouterr().err == render("E_RESULTS_WAVES", path=str(run_dir / "model.json")) + "\n"
    assert sorted(p.name for p in (pj.parent / "results").iterdir()) == before


def test_retune_refuses_while_a_run_holds_the_lock(tmp_path, calibrated, monkeypatch, capsys):  # C-20
    pj = lpf_run(tmp_path, monkeypatch)
    before, lock = pj.read_bytes(), pj.parent / "project.json.lock"
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    capsys.readouterr()
    assert main(["retune", str(pj), "C2=4.7pF"]) == 2
    assert capsys.readouterr().err == render("E_LOCKED", lock=str(lock), run="R", started="S") + "\n"
    assert pj.read_bytes() == before


# --- beyond the brief's tests ------------------------------------------------------------------------------------


def test_retune_without_assignments_rewrites_a_single_trace(tmp_path, calibrated, monkeypatch):  # spec 7.3, C-19
    monkeypatch.setenv("KRS_FAKE", "network")  # as test_the_network_fake_records_the_waves_of_a_known_network
    pj = coupon(tmp_path, "normal")
    assert main(["run", str(pj)]) == 0
    layout_file = pj.parent / "results" / "layout.s2p"
    layout_file.unlink()
    assert main(["retune", str(pj)]) == 0 and layout_file.is_file()  # E_RESULTS_WRITE's `retune PROJECT` holds at M = 0


def test_a_project_in_a_missing_folder_is_a_refusal(tmp_path, capsys):  # exit 2 as in run, never E_INTERNAL
    pj = tmp_path / "missing" / "project.json"  # the lock file, project.json.lock, has no folder to go in
    assert main(["retune", str(pj), "C2=4.7pF"]) == 2
    assert capsys.readouterr().err == render("E_PROJECT_UNREADABLE", path=str(pj), reason="file not found") + "\n"
