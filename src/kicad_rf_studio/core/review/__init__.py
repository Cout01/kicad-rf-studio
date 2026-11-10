# SPDX-License-Identifier: GPL-3.0-or-later
"""The geometry review (Stage 5 design 5.1 to 5.3): rules R1 to R4 over tagged nets, no solver."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import shapely
from shapely.geometry.base import BaseGeometry

from kicad_rf_studio.core.geometry import chain_of
from kicad_rf_studio.core.geometry.region import coarse_cell
from kicad_rf_studio.core.geometry.zstack import Slab
from kicad_rf_studio.core.kicad.board import Board
from kicad_rf_studio.core.kicad.shapes import XY
from kicad_rf_studio.core.kicad.stackup import Stackup
from kicad_rf_studio.core.kicad.tracer import Classes
from kicad_rf_studio.core.project import antenna, si
from kicad_rf_studio.core.review.planes import plane_map, plane_nets
from kicad_rf_studio.core.review.rules import EDGE_K, Finding, exclusions, groups, r1, r2, r3, r4
from kicad_rf_studio.core.review.tags import tag

F_MAX_DEFAULT = 5e9  # Hz: FCC 15.33(b)(1)'s upper measurement frequency for a highest frequency of 500 to 1000 MHz (A2)
F_MAX_CAP = 6e9  # Hz: a carrier's or an SI project's f_max goes no higher (BC1)
CARRIER_HARMONICS = 5  # a carrier's f_max is this many times it (BC1)
REVIEW_LIMITS = ("I_LIMIT_REVIEW_KEEPOUT",)  # printed last and written at the end of review.json's notes (design 5.1)


@dataclass
class Review:
    """A board's review: its settings and notes as review.json writes them, its findings, numbered, and `cover`, the
    union of every plane of the plane map, which review.png draws. The carrier and the clocks are kept for plan 2's
    cavity marks; plan 1 writes them nowhere."""
    settings: dict
    notes: list[tuple[str, dict]]
    findings: list[Finding]
    cover: BaseGeometry
    carrier: float | None
    clocks: tuple[float, ...]


def resolve_f_max(f_max: float | None, f0: float | None, project: dict | None) -> tuple[float, str, float | None]:
    """(f_max, its source, the carrier) in BC1's order (design 5.1): `f_max` given, "cli"; else with a carrier,
    CARRIER_HARMONICS times it, at most F_MAX_CAP, "carrier"; else an SI project's f_max_hz, at most F_MAX_CAP, "si";
    else F_MAX_DEFAULT, "default". The carrier is `f0`, else an antenna project's band centre, else a v1 project's
    f0_hz, else None. A project's simulation f_max (region.f_max) is never read."""
    carrier = f0
    if carrier is None and project is not None:
        if antenna(project):
            carrier = (project["band"]["f_lo_hz"] + project["band"]["f_hi_hz"]) / 2
        elif not si(project):
            carrier = project["f0_hz"]
    if f_max is not None:
        return f_max, "cli", carrier
    if carrier is not None:
        return min(F_MAX_CAP, CARRIER_HARMONICS * carrier), "carrier", carrier
    if project is not None and si(project):
        return min(project["f_max_hz"], F_MAX_CAP), "si", None
    return F_MAX_DEFAULT, "default", None


def _kicad(at: XY) -> XY:
    """A place in KiCad's frame, y down; adding 0.0 turns a -0.0 into 0.0."""
    return at[0] + 0.0, 0.0 - at[1] + 0.0


def finding_ids(findings: Sequence[Finding]) -> list[str]:
    """Each finding's id (design 5.3): its rule, "-" and the first 8 hex digits of the SHA-256 of the compact JSON of
    [rule, its sorted KIIDs of every kind, its place in KiCad's frame rounded to 0.01 mm], so the same copper keeps its
    id across reruns. A repeated id takes "-2", "-3" and so on, in list order."""
    ids, seen = [], Counter()
    for f in findings:
        kiids = sorted(k for kind in f.kiids.values() for k in kind)
        at = [round(v, 2) + 0.0 for v in _kicad(f.at)]  # again after rounding: round(-0.004, 2) is -0.0
        key = json.dumps([f.rule, kiids, at], separators=(",", ":"))
        base = f"{f.rule}-{hashlib.sha256(key.encode()).hexdigest()[:8]}"
        seen[base] += 1
        ids.append(base if seen[base] == 1 else f"{base}-{seen[base]}")
    return ids


def review_board(board: Board, stackup: Stackup, zs: tuple[Slab, ...], classes: Classes, *, nets: Sequence[str] = (),
                 project: dict | None = None, f0: float | None = None, clocks: Sequence[float] = (),
                 f_max: float | None = None, edge_k: float | None = None, edge_fence: bool = False) -> Review:
    """The review of `board` (design 5.1 to 5.3): f_max from resolve_f_max, εr the highest of the stackup's
    dielectrics, L = coarse_cell(f_max, εr) and k = `edge_k`, else EDGE_K. The tags come from the flags `nets` and
    `project`'s chain; the findings are R1 + R2 + R3 + R4, sorted by rule, then KiCad's x and y, each numbered from 1
    with its id, its tag's source and the params n, x_mm and y_mm in KiCad's frame. The notes run in AR-12's order:
    the board's warnings, W_FILLS_AS_SAVED, I_REVIEW_RELATIVE, I_REVIEW_BASIS, one I_REVIEW_TAGS_ line per source in
    BC2's order (I_REVIEW_NO_TAGS with no tag), then W_REVIEW_NET_UNMATCHED per unmatched flag, W_EMC_LAYER_SKIPPED
    per skipped layer and I_EMC_NO_REFERENCE for the nets with a track no plane lies under."""
    never, pm = plane_nets(board, classes), plane_map(board, classes, zs)
    f_hz, source, carrier = resolve_f_max(f_max, f0, project)
    eps_r = max(layer.epsilon_r for layer in stackup.layers if layer.kind == "dielectric")
    l_mm, k = coarse_cell(f_hz, eps_r), EDGE_K if edge_k is None else edge_k
    tags, unmatched = tag(board, classes, never, nets, chain_of(project).nets if project else ())
    found, lost = groups(board, pm, tags, exclusions(board, classes))
    findings = sorted(r1(board, pm, found, l_mm) + r2(board, classes, pm, tags, l_mm) + r3(board, found, k)
                      + r4(board, classes, l_mm, edge_fence), key=lambda f: (f.rule, *_kicad(f.at)))
    for n, (f, fid) in enumerate(zip(findings, finding_ids(findings)), 1):
        x, y = _kicad(f.at)
        f.n, f.id, f.tag_source = n, fid, tags.get(f.net)
        f.params.update(n=str(n), x_mm=f"{x:.3f}", y_mm=f"{y:.3f}")
    by_source: dict[str, list[str]] = {}
    for net, s in tags.items():  # tags is sorted by net, so each line's nets are too
        by_source.setdefault(s.split(":")[0], []).append(net)
    tag_lines = [(f"I_REVIEW_TAGS_{s.upper()}", {"nets": ", ".join(by_source[s])})
                 for s in ("flag", "project", "pattern", "walk") if s in by_source]  # BC2's order
    notes = [*board.warnings, ("W_FILLS_AS_SAVED", {}), ("I_REVIEW_RELATIVE", {}),
             ("I_REVIEW_BASIS", {"f_max_ghz": f"{f_hz / 1e9:g}", "source": f"T_FMAX_{source.upper()}",
                                 "eps_r": f"{eps_r:g}", "l_mm": f"{l_mm:.3f}", "edge_k": f"{k:g}"}),
             *(tag_lines or [("I_REVIEW_NO_TAGS", {})]),
             *[("W_REVIEW_NET_UNMATCHED", {"pattern": p}) for p in unmatched],
             *[("W_EMC_LAYER_SKIPPED", {"layer": layer}) for layer in pm.skipped],
             *([("I_EMC_NO_REFERENCE", {"nets": ", ".join(lost)})] if lost else [])]
    settings = {"f_max_hz": f_hz, "f_max_source": source, "eps_r": eps_r, "l_mm": round(l_mm, 3), "edge_k": float(k),
                "edge_fence": edge_fence, "tags": [{"net": net, "source": s} for net, s in tags.items()]}
    cover = shapely.union_all([g for by_net in pm.planes.values() for g in by_net.values()])
    return Review(settings, notes, findings, cover, carrier, tuple(clocks))
