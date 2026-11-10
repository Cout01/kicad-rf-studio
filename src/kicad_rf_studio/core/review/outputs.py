# SPDX-License-Identifier: GPL-3.0-or-later
"""The review's three files (Stage 5 design 5.3): review.json, schema 1, and review.csv, every place in KiCad's frame
(mm, y down) rounded to 1e-3, and review.png. matplotlib is loaded inside review_png only (C-5)."""
from __future__ import annotations

import csv
import io
import json
import re

import shapely
from shapely.geometry import MultiLineString
from shapely.geometry.base import BaseGeometry
from shapely.plotting import plot_line, plot_polygon  # their matplotlib imports run in the call, never here

from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.shapes import XY
from kicad_rf_studio.core.messages import english
from kicad_rf_studio.core.review import REVIEW_LIMITS, Review, _kicad
from kicad_rf_studio.core.review.planes import centre_line
from kicad_rf_studio.core.review.rules import SOURCES

REVIEW_OUTPUTS = re.compile(r"review\.(json|csv|png)")  # the review's files, matched whole
CSV_COLUMNS = ("id", "rule", "code", "net", "layer", "ref_layer", "ref_net", "x_mm", "y_mm", "measured", "limit",
               "kiids", "message")


def _mm(*at: XY) -> list[float]:
    """The places `at` in KiCad's frame, y down, flattened and rounded to 1e-3; adding 0.0 after rounding turns a
    -0.0 into 0.0."""
    return [round(v, 3) + 0.0 for p in at for v in _kicad(p)]


def _down(g: BaseGeometry) -> BaseGeometry:
    """`g` in KiCad's frame, y down."""
    return shapely.transform(g, lambda xy: xy * (1, -1))


def review_json(r: Review, path: str, sha256: str) -> bytes:
    """review.json, schema 1 (design 5.3): the board's `path` as given and its `sha256`, r.settings, the notes (r.notes,
    then REVIEW_LIMITS), the findings, and `cavities`, last: r.cavities as review_board fills them, each plane pair's
    cavity with its grid's h_mm, narrow_slot and modes (design 5.4; AR-2). A finding's ref_layer, ref_net and h_mm come
    from its reference, None without one; at_mm and bbox_mm, [x0, y0, x1, y1], are in KiCad's frame; limit and h_mm are
    rounded to 1e-3. limit_source, SOURCES[rule], is an English record for the file's readers: a GUI shows the finding's
    message, which names the source in the user's language, never limit_source."""
    findings = []
    for f in r.findings:
        x0, y0, x1, y1 = f.bounds
        findings.append({
            "id": f.id, "rule": f.rule, "code": f.code, "params": f.params, "net": f.net, "layer": f.layer,
            "ref_layer": f.ref.layer if f.ref else None, "ref_net": f.ref.net if f.ref else None,
            "h_mm": round(f.ref.h, 3) if f.ref else None, "at_mm": _mm(f.at), "bbox_mm": _mm((x0, y1), (x1, y0)),
            "measured": f.measured, "limit": round(f.limit, 3), "limit_source": SOURCES[f.rule],
            "tag_source": f.tag_source, "kiids": f.kiids})
    notes = [*r.notes, *((code, {}) for code in REVIEW_LIMITS)]
    data = {"schema": 1, "board": {"path": path, "sha256": sha256}, "settings": r.settings,
            "notes": [{"code": code, "params": params} for code, params in notes], "findings": findings,
            "cavities": r.cavities}
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def review_csv(r: Review) -> bytes:
    """review.csv (design 5.3), for the user only, in UTF-8: CSV_COLUMNS, then a row per finding with its place in
    KiCad's frame, its measured values as name=value joined by ";" (a None value empty), its KIIDs as kind:KIID joined
    by ";" in the kinds' order, and its message in English."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for f in r.findings:
        x, y = _mm(f.at)
        measured = ";".join(f"{name}=" + ("" if v is None else f"{v:.3f}") for name, v in f.measured.items())
        kiids = ";".join(f"{kind}:{kiid}" for kind, ids in f.kiids.items() for kiid in ids)
        writer.writerow([f.id, f.rule, f.code, f.net, f.layer, f.ref.layer if f.ref else None,
                         f.ref.net if f.ref else None, f"{x:.3f}", f"{y:.3f}", measured, f"{f.limit:.3f}", kiids,
                         english(f.code, **f.params)])
    return out.getvalue().encode("utf-8")


def draw_review(fig, r: Review, board: Board) -> None:
    """review.png's drawing (design 5.3) on the matplotlib Figure `fig` (review_png's, or plan 2's GUI canvas), on one
    axes in KiCad's frame, mm with y down, at equal aspect: r.cover, the planes' union, filled light grey with its holes
    left open; the outline, when the board has one; the centre lines of the tagged nets' tracks; and each finding's
    number at its place. It draws the review's own cover, so it never rebuilds the plane map, the classes or the
    z-stack."""
    ax = fig.subplots()
    if not r.cover.is_empty:
        plot_polygon(_down(r.cover), ax=ax, add_points=False, facecolor="lightgrey", edgecolor="none")
    if board.outline is not None:
        plot_polygon(_down(board.outline), ax=ax, add_points=False, facecolor="none", edgecolor="black")
    tagged = {t["net"] for t in r.settings["tags"]}
    lines = [centre_line(t) for t in board.tracks if t.net in tagged]
    if lines:
        plot_line(_down(MultiLineString(lines)), ax=ax, add_points=False, linewidth=1)
    # ponytail: text does not widen the view, so a number far from everything drawn (an R4 frame on a board with no
    # outline or plane near it) can fall outside it; ax.update_datalim with the places if one turns up
    for f in r.findings:
        ax.text(*_kicad(f.at), str(f.n), ha="center", va="center", color="red", fontweight="bold")
    ax.set(aspect="equal", xlabel="x (mm)", ylabel="y (mm)")
    ax.invert_yaxis()


def review_png(r: Review, board: Board) -> bytes:
    """review.png (design 5.3): draw_review on a Figure drawn by Agg, never a pyplot figure, as PNG at 100 dpi, as
    outputs.summary_png builds summary.png."""
    from matplotlib.figure import Figure  # here only: no other code of the core loads matplotlib (C-5)

    fig = Figure(figsize=(8, 8), layout="constrained")
    draw_review(fig, r, board)
    out = io.BytesIO()
    fig.savefig(out, format="png", dpi=100)
    return out.getvalue()
