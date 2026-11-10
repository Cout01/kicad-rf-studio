# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from kicad_rf_studio import cli, pipeline
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import render

FIX = Path(__file__).parent / "fixtures"
EMC, LPF = FIX / "emc_review.kicad_pcb", FIX / "lpf915.kicad_pcb"


def settings(folder):
    return json.loads((folder / "review.json").read_text(encoding="utf-8"))["settings"]


def test_review_writes_its_three_files_and_prints_its_lines_in_seconds(tmp_path, capsys):  # design 5.1, 5.3; ruling 8
    start = time.perf_counter()
    assert main(["review", str(EMC), "-o", str(tmp_path)]) == 0
    assert time.perf_counter() - start < 30  # generous: r1 measured the rules in milliseconds; the PNG included
    assert sorted(p.name for p in tmp_path.iterdir()) == ["review.csv", "review.json", "review.png"]
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == [render("W_FILLS_AS_SAVED"), render("I_REVIEW_RELATIVE")]
    assert out[-3:] == [render("I_REVIEW_FINDINGS", count=2),
                        render("I_OUTPUTS", files="review.csv, review.json, review.png", folder=str(tmp_path)),
                        render("I_LIMIT_REVIEW_KEEPOUT")]
    assert json.loads((tmp_path / "review.json").read_text(encoding="utf-8"))["board"]["path"] == str(EMC)
    assert "openEMS" not in sys.modules and "CSXCAD" not in sys.modules


def test_review_writes_to_the_working_folder_and_a_held_file_is_an_e_line(tmp_path, monkeypatch):  # design 5.1
    monkeypatch.chdir(tmp_path)
    assert main(["review", str(EMC)]) == 0 and (tmp_path / "review.json").is_file()
    real = os.replace

    def replace(src, dst):  # a viewer holds review.png
        if Path(dst).name == "review.png":
            raise PermissionError(13, "in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    lines, out = [], tmp_path / "out"
    assert cli.review(EMC, nets=["CLK_*"], edge_fence=True, output=out,  # a Path, as the GUI gives it
                      emit=lambda code, params: lines.append((code, params))) == 2
    (err,) = [params for code, params in lines if code == "E_RESULTS_WRITE"]
    assert err["command"] == pipeline.command_line("kicad-rf-studio", "review", str(EMC), "--net", "CLK_*",
                                                   "--edge-fence", "-o", str(out))
    assert "I_OUTPUTS" not in [code for code, _ in lines] and lines[-1] == ("I_LIMIT_REVIEW_KEEPOUT", {})
    assert not (out / "review.json").exists()  # review.json goes last: a held file refuses before it changes


def test_review_tags_a_projects_chain_takes_its_carrier_and_the_flags_win(tmp_path):  # design 5.1; BC1, BC2
    project, _ = cli.new(LPF, "U1.1", "J1.1", 915e6, output=tmp_path / "p")
    assert main(["review", str(LPF), "--project", str(tmp_path / "p"), "-o", str(tmp_path / "a")]) == 0
    s = settings(tmp_path / "a")
    assert (s["f_max_hz"], s["f_max_source"], s["l_mm"]) == (4.575e9, "carrier", 1.545)
    assert s["tags"] == [{"net": n, "source": "project"} for n in ("RF_A", "RF_B", "RF_C", "RF_OUT")]
    assert main(["review", str(LPF), "--project", str(project), "--f0", "868MHz", "--clock", "32MHz",
                 "-o", str(tmp_path / "b")]) == 0
    assert (settings(tmp_path / "b")["f_max_hz"], settings(tmp_path / "b")["f_max_source"]) == (4.34e9, "carrier")
    assert main(["review", str(LPF), "--f-max", "3GHz", "--edge-k", "3", "-o", str(tmp_path / "c")]) == 0
    assert (settings(tmp_path / "c")["f_max_hz"], settings(tmp_path / "c")["edge_k"]) == (3e9, 3.0)


def test_a_board_with_no_stackup_is_refused_and_a_preset_reviews_it(mini_board_file, tmp_path, capsys):  # design 5.1
    board = mini_board_file()
    assert main(["review", str(board), "-o", str(tmp_path / "o")]) == 2
    assert render("E_NO_STACKUP") in capsys.readouterr().err and not (tmp_path / "o").exists()
    assert main(["review", str(board), "--stackup", "kicad-default", "-o", str(tmp_path / "o")]) == 0


def test_the_parser_holds_the_designs_synopsis_and_no_run_dir():  # design 5.1; ruling 6
    a = cli._parser().parse_args(["review", "b.kicad_pcb"])
    assert (a.net, a.project, a.f0, a.clock, a.f_max, a.edge_k, a.edge_fence, a.stackup, a.output) == (
        [], None, None, [], None, None, False, None, None)
    assert not hasattr(a, "run_dir")


def test_the_cli_with_the_review_imports_neither_openems_nor_matplotlib():  # Stage 1 3.1; ruling 5
    probe = ("import sys, kicad_rf_studio.cli, kicad_rf_studio.core.review, kicad_rf_studio.core.review.outputs; "
             "print(sorted(m for m in ('openEMS', 'CSXCAD', 'matplotlib') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr
