# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import io
import json
import subprocess
import sys
from dataclasses import replace

from matplotlib.figure import Figure

from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.messages import english
from kicad_rf_studio.core.review.outputs import CSV_COLUMNS, draw_review, review_csv, review_json, review_png
from kicad_rf_studio.core.review.rules import SOURCES
from test_review import FIX, run

SHA, PNG = "ab" * 32, b"\x89PNG\r\n\x1a\n"


def test_review_json_holds_schema_1s_keys_in_kicads_frame():  # design 5.3; ruling 1
    r = run()
    text = review_json(r, "b.kicad_pcb", SHA)
    data = json.loads(text)
    assert text.endswith(b"}\n") and list(data) == ["schema", "board", "settings", "notes", "findings", "cavities"]
    assert (data["schema"], data["board"], data["cavities"]) == (1, {"path": "b.kicad_pcb", "sha256": SHA}, [])
    assert data["settings"] == r.settings and data["notes"][1] == {"code": "I_REVIEW_RELATIVE", "params": {}}
    assert data["notes"][-1] == {"code": "I_LIMIT_REVIEW_KEEPOUT", "params": {}}  # design 5.1: the output says so
    f = data["findings"][1]
    assert list(f) == ["id", "rule", "code", "params", "net", "layer", "ref_layer", "ref_net", "h_mm", "at_mm",
                       "bbox_mm", "measured", "limit", "limit_source", "tag_source", "kiids"]
    assert (f["rule"], f["at_mm"], f["bbox_mm"], f["ref_layer"], f["ref_net"], f["h_mm"], f["limit"]) == (
        "R3", [113.0, 100.6], [102.75, 100.35, 123.25, 100.85], "In1.Cu", "GND", 0.2, 0.4)  # y down
    assert (f["limit_source"], f["tag_source"], f["id"]) == (SOURCES["R3"], "pattern:CLK", r.findings[1].id)
    assert list(f["kiids"]) == ["tracks", "vias", "zones", "pads", "footprints"] and len(f["kiids"]["tracks"]) == 1


def test_review_csv_has_a_row_per_finding_with_its_measures_kiids_and_english_message():  # design 5.3
    r = run()
    rows = list(csv.reader(io.StringIO(review_csv(r).decode("utf-8"))))
    assert rows[0] == list(CSV_COLUMNS) and len(rows) == 3
    row = dict(zip(rows[0], rows[2]))
    edge = r.findings[1]
    assert (row["id"], row["rule"], row["x_mm"], row["y_mm"], row["limit"]) == (edge.id, "R3", "113.000", "100.600",
                                                                                "0.400")
    assert row["measured"] == "d_mm=0.350;h_mm=0.200;k=2.000;share_pct=16.500"
    assert row["kiids"] == f"tracks:{edge.kiids['tracks'][0]}" and row["message"] == english("W_EMC_EDGE", **edge.params)


def test_review_png_numbers_each_finding_and_draws_the_reviews_cover_whatever_the_stackup(mini_board):  # design 5.3
    board = load_board(FIX / "emc_review.kicad_pcb")
    board.stackup = None  # as under --stackup: the review's own cover is drawn, never rebuilt
    r = run()
    fig = Figure()
    draw_review(fig, r, board)
    ax = fig.axes[0]
    assert [t.get_text() for t in ax.texts] == ["1", "2"] and len(ax.patches) >= 1
    assert review_png(r, board)[:8] == PNG
    assert review_png(replace(r, findings=[]), mini_board())[:8] == PNG  # a board with no outline


def test_the_review_imports_neither_openems_nor_matplotlib():  # Stage 1 3.1; ruling 5
    probe = ("import sys, kicad_rf_studio.core.review, kicad_rf_studio.core.review.outputs; "
             "print(sorted(m for m in ('openEMS', 'CSXCAD', 'matplotlib') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr
