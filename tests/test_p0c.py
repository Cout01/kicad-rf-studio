# SPDX-License-Identifier: GPL-3.0-or-later
import json

import numpy as np

import p0
import p0c
from kicad_rf_studio.core.messages import KrsError
from kicad_rf_studio.core.model import spec as spec_module
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import board_hash, load_project
from networks import write_s2p
from test_p0 import in_process

F, _ = grid(915e6, 3, 1.1)
ARGS = ["--start", "U1.1", "--end", "J1.1", "--f0", "915MHz"]
REPORTS = ("p0c.json", "p0c.md", "p0c-public.json")


def test_p0c_refuses_paths_inside_a_git_work_tree(tmp_path):  # D-46; Review Focus 4
    board = tmp_path / "b.kicad_pcb"
    board.write_bytes((p0.FIX / "lpf915.kicad_pcb").read_bytes())
    for b, out in ((p0.FIX / "lpf915.kicad_pcb", tmp_path / "out"), (board, p0.ROOT / "build" / "p0c"),
                   (board, p0.ROOT / "not-yet" / "deeper")):
        assert p0c.main(["--board", str(b), "--out", str(out), *ARGS]) == 2
    assert not any(p.exists() for p in (tmp_path / "out", p0.ROOT / "build" / "p0c", p0.ROOT / "not-yet"))


def test_a_rerun_with_another_board_or_options_is_refused(tmp_path, p0_out, monkeypatch, capsys):  # final review F1
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(p0c, "run_step", lambda out, a, name: p0c.base(out, a))  # a step here only makes the base
    board, kept = tmp_path / "lpf915.kicad_pcb", (p0.FIX / "lpf915.kicad_pcb").read_bytes()
    board.write_bytes(kept)
    argv = ["--board", str(board), *ARGS, "--lid-height", "2.5", "--out", str(p0_out), "--steps", "C0"]
    assert p0c.main(argv) == 0
    new = {"start": "U1.1", "end": "J1.1", "f0": "915MHz", "harmonics": None, "lid_height": "2.5", "stackup": None}
    assert json.loads((p0_out / "inputs.json").read_text(encoding="utf-8")) == {"board_sha256": board_hash(board),
                                                                                 "new": new}
    made = {p: p.read_bytes() for p in p0_out.rglob("*") if p.is_file()}
    capsys.readouterr()
    for again, data in ((["--f0", "916MHz"], kept), ([], kept + b"\n")):  # another f0; the board one byte longer
        board.write_bytes(data)
        assert p0c.main([*argv, *again]) == 2
        assert capsys.readouterr().err == (f"p0c: {p0_out} was made for another board or other new options; use a "
                                           "fresh --out\n")
        assert {p: p.read_bytes() for p in p0_out.rglob("*") if p.is_file()} == made
    board.write_bytes(kept)
    assert p0c.main(argv) == 0  # the same inputs go on


def test_p0c_on_lpf915_with_the_fake_worker(tmp_path, p0_out, monkeypatch):  # D-46; Review Focus 4
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    monkeypatch.setattr(spec_module, "c_box", lambda *a: 6e-16)  # verify's cells: the fake's dump is empty
    board = tmp_path / "placa ação" / "lpf915.kicad_pcb"
    board.parent.mkdir()
    board.write_bytes((p0.FIX / "lpf915.kicad_pcb").read_bytes())
    s2p = tmp_path / "s2p"
    s2p.mkdir()
    write_s2p(s2p / "C2.shunt.s2p", 1 / (2j * np.pi * F * 3.3e-12), "shunt", F)
    assert p0c.main(["--board", str(board), *ARGS, "--lid-height", "2.5", "--out", str(p0_out), "--preset", "normal",
                     "--steps", "C0,C1,C2,C3,C4a,C4b,C5,C6,S2P", "--s2p", str(s2p)]) == 0
    private = json.loads((p0_out / "report" / "p0c.json").read_text(encoding="utf-8"))
    public = json.loads((p0_out / "report" / "p0c-public.json").read_text(encoding="utf-8"))
    assert set(private["criteria"]) == {"c1", "c2", "c3", "c4"} and (p0_out / "board" / "lpf915.kicad_pcb").is_file()
    assert "compare" in load_project(p0_out / "projects" / "C2" / "project.json")["verify"]
    base = p0_out / "projects" / "base" / "project.json"
    own, best = load_project(base)["ports"], p0c.next_best(base)  # P1's next-best reference leaves no port box
    assert best[0] != own[0] and load_project(p0_out / "projects" / "C3" / "project.json")["ports"] == [own[0], best[1]]

    def leaves(x):
        items = x.values() if isinstance(x, dict) else x if isinstance(x, list) else None
        return [x] if items is None else [v for y in items for v in leaves(y)]

    assert all(v is None or isinstance(v, (bool, int, float)) for v in leaves(public))
    measured = [public["criteria"][c][k] for c, k in (("c1", "ds21_db_f0"), ("c1", "ds_max"), ("c2", "sigma_max"),
                                                      ("c3", "ds21_db"), ("c4", "n3_ds21_db"), ("c4", "margin_ds21_db"))]
    measured += [public["measured"]["lid_ds"]["f0"], public["measured"]["band_ds"]["f0"], public["measured"]["s2p_ds_max"]]
    assert all(isinstance(v, float) for v in measured)  # every step ran and was measured, none read None
    c = {k: bool(v["pass"]) for k, v in public["criteria"].items()}
    assert public["verdict"] == {"pass": c["c1"] and c["c2"] and c["c4"], "refine_mesh": not c["c4"],
                                 "fallback": not (c["c1"] and c["c2"]), "prominent_reference": not c["c3"]}


def test_p0c_skips_c3_when_no_next_best_reference_leaves_a_port_box(tmp_path, p0_out, monkeypatch, capsys):  # PF-40
    monkeypatch.setattr(p0, "cli", in_process)
    moved = iter(["P1", "P2"])  # next_best moves both of lpf915's references

    def refused(pj):  # only C3 asks for a model key here
        raise KrsError("E_PORT_BOX", name=next(moved))

    monkeypatch.setattr(p0, "model_key", refused)
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes((p0.FIX / "lpf915.kicad_pcb").read_bytes())
    assert p0c.main(["--board", str(board), *ARGS, "--lid-height", "2.5", "--out", str(p0_out), "--steps", "C3"]) == 0
    assert "p0c: C3 skipped: no port has a next-best reference that leaves a port box\n" in capsys.readouterr().out
    assert not (p0_out / "steps" / "p0c-C3.json").exists()


def test_p0c_with_c1_at_draft_reads_every_criterion_as_none(tmp_path, p0_out, monkeypatch):  # PF-39
    monkeypatch.setenv("KRS_FAKE", "network")
    monkeypatch.setattr(p0, "cli", in_process)
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes((p0.FIX / "lpf915.kicad_pcb").read_bytes())
    assert p0c.main(["--board", str(board), *ARGS, "--lid-height", "2.5", "--out", str(p0_out), "--preset", "draft",
                     "--steps", "C0,C1"]) == 0
    assert all((p0_out / "report" / name).is_file() for name in REPORTS)
    public = json.loads((p0_out / "report" / "p0c-public.json").read_text(encoding="utf-8"))
    assert all(v is None for criterion in public["criteria"].values() for v in criterion.values())
    assert list(public["measured"]["stop_ns"]) == ["draft"]  # C1 ran, replayed at Draft only: no base at Normal
