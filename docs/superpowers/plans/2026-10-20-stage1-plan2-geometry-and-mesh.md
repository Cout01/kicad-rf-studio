# Stage 1 · Plan 2: Geometry, Mesh and Mesh Gates — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a loaded board and its `project.json` into clipped copper, vias, mask and lid geometry plus x/y/z mesh lines that pass the mesh gates, and make `kicad-rf-studio cost` print the 2D Z0/εeff readout of each straight section of the measured nets.

**Architecture:**
- `core.geometry` builds, in order: the z-stack (layers by position), the region (ROI, walls, through-crop), copper pieces per (layer, net), vias, the mask model, the measured sections and their cross-sections, and the shield lid.
- `core.mesh` builds the protected set, the rule lines, the graded mesh and the gates (edge lint with one re-mesh, fit2d, timestep-floor reference).
- `core.cs2d` is a finite-difference Laplace solver on a rectilinear (possibly non-uniform) grid. With its own fine grid it is the 2D reference; with the FDTD mesh lines it is fit2d's "actual mesh" estimate.
- `cli.py` gains `cost`, which in this plan prints only the 2D readout; plan 3 appends the setup-only part.

**Tech Stack:** Python ≥ 3.11, shapely 2, numpy, scipy (`scipy.sparse.linalg.spsolve`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-stage1-validated-engine-design.md`. This plan covers §5.1–5.5, the 2D readout of `cost` in §3.2, the NOTICE entries of §3.6 for SmoothMeshLines and the KiCad line formulas, and the "2D reference against the ported KiCad line formulas" part of CI tier (a) in §9.1.

**Stage 1 is split into five plans.** Each one ends in working, tested software:
1. Foundation and board import.
2. Geometry, mesh and the mesh gates, including the 2D Z0/εeff readout of `cost` (this plan).
3. Model, worker and run control: `cost`, `run`, `preview`, `calibrate` and `setup-openems`.
4. Co-simulation and results: `retune`, `verify`, the outputs and the validity indicators.
5. Validation gates P0-A to P0-D, the KiCad button pre-check and the reports.

**Branch:** work on `stage1-plan2`, from `main`. Commands assume the dev venv is active.

## Global Constraints

- **Python:** ≥ 3.11. Every `.py` file starts with `# SPDX-License-Identifier: GPL-3.0-or-later`, except `core/mesh/smooth.py`, which keeps CSXCAD's LGPL-3.0-or-later header.
- **Dependencies:** runtime `shapely>=2.0`, `numpy`, `scipy`; dev `pytest>=8`. No openEMS, CSXCAD, Qt or pcbnew imports anywhere in this plan.
- **User-facing strings:** message codes with parameters in `core.messages`; the English template is the msgid.
- **Units:** mm, Hz, s. Board frame is (x, −y), y up; z = 0 at the bottom face of the bottom copper layer, z up.
- **Quantisation:** every coordinate and mesh line goes to 1e-6 mm (`shapely.set_precision(g, 1e-6)`, `np.round(v, 6)`).
- **Copper pipeline:** make_valid → union → clip 1 mm past the walls → simplify ≤ 10 µm preserving topology → quantise 1e-6 mm → vertical hole split. Never tile; never use `.exterior` alone.
- **Solid copper:** solid PEC of stackup thickness wherever any width or gap is below 30·t; sheets only for structures wide everywhere.
- **Mask defaults:** 10 µm, εr 3.3 (from the stackup when it has a mask layer).
- **Mesh numbers:** n = 2 (standard) or 3 (fine); d capped at 0.9·λ_min/20; lines d/4 inside and 3d/4 outside solid-copper edges; one z-cell per copper thickness; dz0 = max(t_m, min(d/3, h/4)); grading ratio ≤ 1.3; merge in-plane below d/3, in z below dz0/3; protected lines never move.
- **Gates:** edge lint (one automatic re-mesh), fit2d 3 % in Z0, timestep-floor reference = vacuum Courant step of the smallest rule cell (the 0.8 × comparison with openEMS's dt is plan 3).
- **Region:** ROI = bbox of chain nets, part pads and port pads expanded by 3 substrate heights (project field), clipped to the outline; walls at ROI + 4 mm + 8 coarse cells on all six faces; through-crop 1 mm past the walls.
- **Privacy:** synthetic data only; no private names, paths or e-mail addresses in committed text.
- **Commits:** no co-author lines.
- **Language:** English.

## Review Focus

1. **A pad whose polygon is a MultiPolygon, or a paste-only / covered NPTH pad with `layers == ()`.** Copper must come from `Pad.layers`, every piece of a MultiPolygon must survive, and an NPTH must add no copper. Test: `test_copper_follows_pad_layers` (Task 3).
2. **An Edge.Cuts outline with 1–10 µm gaps between ends** (KiCad chains them; shapely does not). It must close into one polygon instead of losing the substrate clip. Test: `test_outline_joins_ends_within_10_um` (Task 1).
3. **A copper pour with holes (via antipads, thermal reliefs) straddling the crop.** Pieces must be hole-free, cover the same area to 1e-6 mm², and stay valid. Test: `test_hole_split_keeps_area` (Task 3).
4. **A measured net with no straight axis-aligned section** (all 45° or arcs). `cost` must print the staircase warning and no table rows, not crash; the d rule must still get a width. Tests: `test_diagonal_net_has_no_sections` (Task 6) and `test_cost_on_45_degree_coupon` (Task 13).
5. **A stackup whose copper sub-layers share a name, or whose copper count differs from the board's.** Layers are matched by position; a count mismatch is an error, not a silent shift. Test: `test_zstack_by_position` and `test_zstack_count_mismatch` (Task 2).

---

## File structure

```
pyproject.toml                                    # + numpy, scipy
NOTICE                                            # create: SmoothMeshLines (LGPL), KiCad line formulas (GPL)
src/kicad_rf_studio/cli.py                        # + cost
src/kicad_rf_studio/core/messages.py              # + new codes
src/kicad_rf_studio/core/kicad/board.py           # outline join, dropped-copper warnings
src/kicad_rf_studio/core/geometry/__init__.py     # Geometry, build_geometry()
src/kicad_rf_studio/core/geometry/zstack.py       # Slab, zstack()
src/kicad_rf_studio/core/geometry/region.py       # Region, coarse_cell(), build_region()
src/kicad_rf_studio/core/geometry/copper.py       # Piece, clean(), split_holes(), copper_pieces(), connectivity()
src/kicad_rf_studio/core/geometry/vias.py         # Rod, via_rods()
src/kicad_rf_studio/core/geometry/mask.py         # MaskModel, smeared_epsilon(), mask_model()
src/kicad_rf_studio/core/geometry/sections.py     # Section, sections(), cross_section()
src/kicad_rf_studio/core/geometry/lid.py          # Lid, find_lid(), snap_lid()
src/kicad_rf_studio/core/cs2d.py                  # Rect, CrossSection, Line, solve()
src/kicad_rf_studio/core/mesh/__init__.py         # Mesh, build_mesh()
src/kicad_rf_studio/core/mesh/protect.py          # Protected, protected_set()
src/kicad_rf_studio/core/mesh/smooth.py           # copy of CSXCAD SmoothMeshLines (LGPL-3.0-or-later)
src/kicad_rf_studio/core/mesh/rule.py             # cell_size(), edge_lines(), z_lines(), merge()
src/kicad_rf_studio/core/mesh/gates.py            # edge_lint(), mesh_with_lint(), fit2d(), dt_floor_reference()
tests/kicad_lines.py                              # ported KiCad line-calculator formulas (GPL), tests only
tests/test_geometry_*.py  tests/test_cs2d.py  tests/test_mesh_*.py  tests/test_gates.py  tests/test_cli_cost.py
```

## Decisions this plan makes (owner to confirm)

- **cs2d method:** 5-point finite-volume Laplace on a non-uniform rectilinear grid, ε per cell, potentials on nodes, conductor nodes fixed (signal 1 V, every other conductor 0 V), outer box PEC; C from field energy C = ε0 Σ εr |∇φ|² ΔA. Solved twice (εr and vacuum): εeff = C/C0, Z0 = 1/(c0·√(C·C0)). One sparse `spsolve`, no iteration.
- **Non-signal conductors are grounded** in cs2d, including other non-GND nets (for example `coupon_dense`'s AUX). Floating conductors are deferred.
- **Exact mask model in cs2d (the reference):** the mask fills the gaps between conductors up to the copper top, plus a planar coat t_m above copper and gaps; openings remove both. The FDTD model (and fit2d's mesh-side solve) uses the smeared coat.
- **Coarse cell** (the spec's "8 coarse cells"): λ_min/20 with λ_min = c0/(f_max·√εr,max), f_max = band_factor × harmonics × f0, εr,max over the stackup's dielectric and mask layers. The d cap uses the same λ_min.
- **n from the preset:** draft 2, normal 2, strict 3; overridable as `project["mesh"]["n"]`.
- **Lid:** the plate is the convex hull of the shield's frame pads; the walls are the frame pads only, so gaps in the frame (the connector opening) stay open. On when a shield overlaps the ROI and `lid_height_mm` is set, and `harmonics > 1` unless `project["lid"]` says otherwise.
- **Protected-line collisions:** two protected lines closer than d/3 become one line at the position of the pattern whose copper edge is nearer; fit2d then checks the section.
- **Tolerances:** see Tasks 7–8 (cs2d vs exact: 0.5 %; vs Hammerstad–Jensen microstrip: 2 % Z0 and εeff; vs KiCad GCPW: 3 % Z0 and εeff).

---

### Task 1: Board-reader carry-overs and dependencies

**Files:**
- Modify: `src/kicad_rf_studio/core/kicad/board.py` (`_outline`, `_graphic`, `_zone`), `src/kicad_rf_studio/core/messages.py`, `pyproject.toml`
- Test: `tests/test_board.py`

**Interfaces:**
- Produces: `Board.outline` closes when Edge.Cuts ends are within 0.01 mm; `Board.warnings` gains `("W_COPPER_DROPPED", {"kind", "layer", "uuid"})` for `gr_text`, `gr_curve` (Bézier) and hatched zone fills on copper layers.

- [ ] **Step 1: Write the failing tests**

```python
def test_outline_joins_ends_within_10_um(mini_board_text):
    # a 10 x 10 square whose four gr_line ends miss by 0, 3, 7 and 9.9 µm
    b = load_board(mini_board_text(edge_gaps_um=(0, 3, 7, 9.9)))
    assert b.outline is not None and b.outline.area == pytest.approx(100, abs=1e-3)

def test_outline_gap_above_10_um_still_open(mini_board_text):
    b = load_board(mini_board_text(edge_gaps_um=(0, 0, 0, 12)))
    assert b.outline is None and ("W_NO_OUTLINE", {}) in b.warnings

@pytest.mark.parametrize("item,kind", [
    ('(gr_text "RF" (at 1 1) (layer "F.Cu") (uuid "t1"))', "gr_text"),
    ('(gr_curve (pts (xy 0 0) (xy 1 1) (xy 2 1) (xy 3 0)) (layer "F.Cu") (uuid "c1"))', "gr_curve")])
def test_dropped_copper_warns(mini_board, item, kind):
    b = mini_board(item)
    assert ("W_COPPER_DROPPED", {"kind": kind, "layer": "F.Cu", "uuid": item.split('"')[-2]}) in b.warnings

def test_hatched_fill_warns(mini_board):  # a filled zone with (fill yes (mode hatch))
    assert any(c == "W_COPPER_DROPPED" and p["kind"] == "hatched zone" for c, p in mini_board(HATCHED_ZONE).warnings)
```

- [ ] **Step 2: Run** `python -m pytest tests/test_board.py -q`. Expected: the four new tests FAIL.
- [ ] **Step 3: Implement.** In `_outline`, before polygonising, snap each segment end to the first earlier end within 0.01 mm (KiCad's chaining epsilon), then snap to the 1 µm grid as today. Add `W_COPPER_DROPPED`: "{kind} {uuid} on {layer} is left out of the simulation; convert it to a filled shape or a solid zone in KiCad if it carries current." Add `numpy` and `scipy` to `dependencies`.
- [ ] **Step 4: Run** the full suite. Expected: all pass.
- [ ] **Step 5: Commit.** `feat: join outline ends within 10 µm and warn about dropped copper`

---

### Task 2: Z-stack by position and the region

**Files:**
- Create: `src/kicad_rf_studio/core/geometry/__init__.py`, `zstack.py`, `region.py`
- Test: `tests/test_geometry_region.py`

**Interfaces:**
- Consumes: `Stackup`, `Board`, `Chain` (plan 1); `project["ports"]`.
- Produces:
  - `@dataclass(frozen=True) Slab(kind: str, z0: float, z1: float, eps_r: float | None, tan_d: float | None, copper: str | None)`; `copper` is the board's copper-layer name, matched by position.
  - `zstack(stackup: Stackup, copper_layers: tuple[str, ...]) -> tuple[Slab, ...]`, bottom to top, z = 0 at the bottom face of the bottom copper; mask slabs sit outside the copper. Raises `KrsError("E_STACKUP_LAYERS", stackup=, board=)` on a copper-count mismatch.
  - `substrate_h(zs) -> float`: thickness of the dielectric between the measured nets' layer and the next copper (used for ROI expansion, d rule and dz0).
  - `f_max(project) -> float` = `band_factor * harmonics * f0_hz`; `lambda_min(f_max, eps_r_max) -> float` = c0/(f_max·√εr,max) in mm; `coarse_cell(...) = lambda_min/20`.
  - `@dataclass(frozen=True) Region(roi: Polygon, walls: tuple[float, float, float, float, float, float], crop: Polygon, coarse: float)`; walls are (x0, x1, y0, y1, z0, z1).
  - `build_region(board, chain, ports, zs, f_max, expand_h=3.0) -> Region`.

- [ ] **Step 1: Write the failing tests**

```python
def test_zstack_by_position():  # two copper layers both named "F.Cu" in the stackup (sub-layer naming)
    zs = zstack(stackup_with_duplicate_copper_names(), ("F.Cu", "B.Cu"))
    assert [s.copper for s in zs if s.kind == "copper"] == ["B.Cu", "F.Cu"]
    assert zs[0].kind == "mask" and zs[0].z1 == 0.0

def test_zstack_count_mismatch():
    with pytest.raises(KrsError, match="E_STACKUP_LAYERS"):
        zstack(preset("jlcpcb-2l", 1.6, 2), ("F.Cu", "In1.Cu", "B.Cu"))

def test_coarse_cell():
    assert coarse_cell(3.0195e9, 4.5) == pytest.approx(299.792458 / 3.0195 / math.sqrt(4.5) / 20, rel=1e-9)

def test_roi_on_coupon_ms():
    b, p = load_fixture_project("coupon_ms")
    r = build_region(b, chain_of(p), p["ports"], zs := zstack_of(p, b), f_max(p))
    h = substrate_h(zs)
    x0, y0, x1, y1 = r.roi.bounds
    assert (x0, x1) == pytest.approx((100 - 0, 120))  # clipped to the outline at x: the board ends 1 mm past the pads
    assert y1 - y0 == pytest.approx(min(1.35 + 6 * h, 10), abs=1e-6)  # 3h each side, clipped to the 10 mm board
    margin = 4 + 8 * r.coarse
    assert r.walls[0] == pytest.approx(x0 - margin) and r.walls[1] == pytest.approx(x1 + margin)
    assert r.crop.bounds == pytest.approx((r.walls[0] - 1, r.walls[2] - 1, r.walls[1] + 1, r.walls[3] + 1))
    assert r.walls[4] == pytest.approx(zs[0].z0 - margin) and r.walls[5] == pytest.approx(zs[-1].z1 + margin)
```

(Replace the expected x bounds with the fixture's pad extents if they differ; the assertion is "ROI = bbox expanded by 3h, intersected with the outline".)

- [ ] **Step 2: Run** `python -m pytest tests/test_geometry_region.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `zstack`, `substrate_h`, `f_max`, `lambda_min`, `coarse_cell`, `build_region`. The ROI's bbox covers chain-net copper (tracks, areas, pads with the net) plus chain-part pads and port pads; containment against the outline uses a 1 µm tolerance (`outline.buffer(1e-3)`). Add `E_STACKUP_LAYERS`: "The stackup has {stackup} copper layers but the board has {board}. Fix the board stackup in KiCad, or choose a matching --stackup."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: add the z-stack and the simulation region`

---

### Task 3: Copper pipeline

**Files:**
- Create: `src/kicad_rf_studio/core/geometry/copper.py`
- Test: `tests/test_geometry_copper.py`

**Interfaces:**
- Consumes: `Board`, `Region.crop`, `zstack` (copper thickness per layer).
- Produces:
  - `@dataclass(frozen=True) Piece(layer: str, net: str, polygon: Polygon, solid: bool)`; `polygon` has no interiors, is quantised and `shapely.normalize`d.
  - `clean(geom: BaseGeometry, crop: Polygon) -> MultiPolygon` (steps 1–5: make_valid, union, clip, `simplify(0.01, preserve_topology=True)`, `set_precision(1e-6)`, normalize).
  - `split_holes(p: Polygon) -> list[Polygon]` (step 6).
  - `copper_pieces(board, crop, thickness: dict[str, float]) -> tuple[list[Piece], list[tuple[str, dict]]]`, grouped per (layer, net) from tracks, areas and pads; pads add copper on exactly `pad.layers`, every part of a MultiPolygon included.
  - `is_solid(piece_geom: Polygon, others: BaseGeometry, t: float) -> bool`: True when any width or gap is below 30·t.

- [ ] **Step 1: Write the failing tests**

```python
def test_copper_follows_pad_layers():
    b = load_board(FIX / "pads_zoo.kicad_pcb")
    pieces, _ = copper_pieces(b, big_crop(b), {"F.Cu": .035, "B.Cu": .035})
    npth = next(p for p in b.all_pads() if p.kind == "np_thru_hole")
    assert not any(pc.polygon.intersects(npth.polygon.buffer(-1e-3)) for pc in pieces)
    multi = next(p for p in b.all_pads() if p.polygon.geom_type == "MultiPolygon")
    covered = unary_union([pc.polygon for pc in pieces if pc.layer == multi.layers[0]])
    assert all(covered.contains(g.buffer(-1e-3)) for g in multi.polygon.geoms)
    tht = next(p for p in b.all_pads() if p.kind == "thru_hole")
    assert {pc.layer for pc in pieces if pc.polygon.contains(Point(tht.center))} == set(tht.layers)

def test_hole_split_keeps_area():
    sq = box(0, 0, 10, 10).difference(Point(3, 3).buffer(1)).difference(Point(7, 6).buffer(1))
    parts = split_holes(sq)
    assert all(not p.interiors and p.is_valid for p in parts)
    assert sum(p.area for p in parts) == pytest.approx(sq.area, abs=1e-6)
    assert unary_union(parts).symmetric_difference(sq).area < 1e-6

def test_clean_simplifies_within_10_um_and_quantises():
    arc = Point(0, 0).buffer(1, quad_segs=256)
    out = clean(arc, box(-5, -5, 5, 5))
    assert out.hausdorff_distance(arc) <= 0.010 + 1e-9
    assert all(round(c, 6) == c for g in out.geoms for xy in g.exterior.coords for c in xy)

def test_clip_one_mm_past_walls_not_at_roi():  # a 30 mm trace on a 10 mm-wide region keeps copper out to the crop
    ...assert piece.polygon.bounds[2] == pytest.approx(region.crop.bounds[2])

def test_solid_vs_sheet():
    t = 0.035
    assert is_solid(box(0, 0, 0.6, 20), box(0.75, 0, 5, 20), t)            # 0.15 mm gap < 30·t
    assert not is_solid(box(0, 0, 5, 20), box(7, 0, 12, 20), t)             # 5 mm wide, 2 mm gap
    assert is_solid(box(0, 0, 5, 5).union(box(5, 2, 6, 2.5)), Polygon(), t) # 0.5 mm neck

def test_copper_lost_in_cleanup_warns():  # a 5 µm sliver vanishes in simplify
    _, w = copper_pieces(board_with_sliver(), ...)
    assert ("W_COPPER_EMPTIED", {"net": "N1", "layer": "F.Cu"}) in w
```

- [ ] **Step 2: Run** `python -m pytest tests/test_geometry_copper.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** `split_holes` is not pinned by the area test alone; use this:

```text
queue = [p]; out = []
while queue:
    q = queue.pop()
    if not q.interiors: out.append(q); continue
    x = q.interiors[0].coords[min-x vertex].x        # vertical cut through the leftmost vertex of the first hole
    cut = box(x, miny-1, maxx+1, maxy+1)
    queue += valid_polygons(q.intersection(cut)) + valid_polygons(q.difference(cut))
```

Quantise each resulting part again. `is_solid`: `g.buffer(-15t).buffer(15t)` differs from `g` by > 1e-6 mm² or `g.distance(others) < 30t`. Add `W_COPPER_EMPTIED`: "Copper of net {net} on {layer} is smaller than the 10 µm simplification and was left out."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: add the copper pipeline`

---

### Task 4: Protected set, vias and connectivity

**Files:**
- Create: `src/kicad_rf_studio/core/mesh/__init__.py` (empty for now), `src/kicad_rf_studio/core/mesh/protect.py`, `src/kicad_rf_studio/core/geometry/vias.py`
- Modify: `src/kicad_rf_studio/core/geometry/copper.py` (+ `connectivity`)
- Test: `tests/test_geometry_vias.py`

**Interfaces:**
- Consumes: `Piece`, `Region`, `Chain`, `Classes`, `zstack`.
- Produces:
  - `@dataclass(frozen=True) Protected(nets: frozenset[str], area: dict[str, BaseGeometry], vias: frozenset[str], boxes: tuple[Polygon, ...])`: `area` per layer is the measured-net copper, part pads, and reference (GND) copper within `reach` of the measured nets; `vias` holds via uuids; `boxes` are port boxes (empty until plan 3).
  - `protected_set(board, chain, classes, pieces, h, reach_h=3.0, boxes=()) -> Protected`.
  - `@dataclass(frozen=True) Rod(net: str, at: XY, radius: float, z0: float, z1: float, solid: bool)`.
  - `via_rods(board, crop, zs, prot) -> list[Rod]`: solid iff the via uuid is in `prot.vias`; otherwise a PEC curve (snapped to mesh lines in Task 10).
  - `connectivity(pieces, rods, roi, nets) -> list[tuple[str, dict]]`: per net, connected components across layers (joined by rods); `E_OPEN_IN_ROI`/`E_SHORT_IN_ROI` when the split or overlap lies in the ROI, `W_OPEN_IN_MARGIN`/`W_SHORT_IN_MARGIN` otherwise. The caller turns `E_` entries into a blocking gate.

- [ ] **Step 1: Write the failing tests**

```python
def test_fence_vias_near_line_are_solid():   # coupon_gcpw: fence 0.6 mm from the line edges, h = 1.5 mm class
    rods = via_rods(b, region.crop, zs, prot)
    near = [r for r in rods if line.distance(Point(r.at)) <= 3 * h]
    assert near and all(r.solid for r in near)
    assert all(not r.solid for r in rods if line.distance(Point(r.at)) > 3 * h + 0.5)

def test_rod_spans_its_layers():
    r = rods[0]; assert (r.z0, r.z1) == (zs_copper("B.Cu").z0, zs_copper("F.Cu").z1)

def test_open_in_roi_blocks():   # coupon_ms with a 0.1 mm cut in LINE inside the ROI
    assert ("E_OPEN_IN_ROI", {"net": "LINE"}) in connectivity(...)

def test_short_in_margin_warns(): # a LINE stub touching GND outside the ROI but inside the crop
    assert any(c == "W_SHORT_IN_MARGIN" for c, _ in connectivity(...))
```

- [ ] **Step 2: Run** `python -m pytest tests/test_geometry_vias.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Reach is `reach_h · h` (provisional per §5.4). Messages: `E_OPEN_IN_ROI` "Net {net} is broken inside the simulated region. Check the copper in KiCad and refill zones (B)."; `E_SHORT_IN_ROI` "Nets {nets} touch inside the simulated region."; the two `W_` codes say the same for the margin and that the result may be affected.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: add the protected set, vias and the connectivity check`

---

### Task 5: Solder-mask model

**Files:**
- Create: `src/kicad_rf_studio/core/geometry/mask.py`
- Test: `tests/test_geometry_mask.py`

**Interfaces:**
- Consumes: `mask_openings(board, side)` (plan 1), `Piece`, `zstack`, `Region.crop`.
- Produces:
  - `smeared_epsilon(t_m: float, eps_m: float, dz0: float) -> float` = (t_m·ε_m + (dz0 − t_m))/dz0; raises `ValueError` if t_m > dz0.
  - `@dataclass(frozen=True) MaskModel(side: str, eps_m: float, t_m: float, gap_fill: MultiPolygon, coat: MultiPolygon, z_fill: tuple[float, float], z_coat0: float)`: `gap_fill` = crop − openings − copper on the outer layer, spanning the copper z-cell; `coat` = crop − openings, spanning [z_coat0, z_coat0 + dz0] once the mesh gives dz0.
  - `mask_model(board, pieces, zs, crop, side) -> MaskModel | None` (None when the stackup has no mask on that side). Both polygons are quantised and normalised so the plan-3 model hash is order-independent.

- [ ] **Step 1: Write the failing tests**

```python
def test_smeared_epsilon():
    assert smeared_epsilon(0.010, 3.3, 0.025) == pytest.approx((0.033 + 0.015) / 0.025)
    assert smeared_epsilon(0.010, 3.3, 0.010) == pytest.approx(3.3)
    with pytest.raises(ValueError): smeared_epsilon(0.02, 3.3, 0.01)

def test_openings_are_honoured():   # coupon_gcpw_masked vs coupon_gcpw_pads: pad openings absent from both polygons
    m = mask_model(...); pad = b.pads("J1.1")[0].polygon
    assert m.coat.intersection(pad.buffer(-0.01)).area == 0 and m.gap_fill.intersection(pad).area < 1e-9

def test_gap_fill_is_between_conductors():
    assert m.gap_fill.intersection(signal_piece.polygon).area < 1e-9
    assert m.gap_fill.contains(gap_midpoint)

def test_mask_hash_input_is_order_independent():
    a = mask_model(board_with_pads_in_order(1, 2)); b_ = mask_model(board_with_pads_in_order(2, 1))
    assert a.coat.wkb == b_.coat.wkb and a.gap_fill.wkb == b_.gap_fill.wkb

def test_default_mask_values():  # a stackup mask layer without values falls back to 10 µm, εr 3.3
    assert (m.t_m, m.eps_m) == (0.010, 3.3)
```

- [ ] **Step 2: Run** `python -m pytest tests/test_geometry_mask.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Note in the docstring that `mask_openings`' closing shaves about 1 µm off convex corners (accepted).
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: add the smeared solder-mask model`

---

### Task 6: Measured sections and cross-sections

**Files:**
- Create: `src/kicad_rf_studio/core/geometry/sections.py`, `src/kicad_rf_studio/core/cs2d.py` (dataclasses only)
- Test: `tests/test_geometry_sections.py`

**Interfaces:**
- Consumes: `Board`, `Piece`, `zstack`, `MaskModel`; `cs2d.Rect`, `cs2d.CrossSection`: this task creates `src/kicad_rf_studio/core/cs2d.py` with just these two dataclasses (fields as in Task 7); Task 7 adds `Line` and `solve`.
- Produces:
  - `@dataclass(frozen=True) Section(net: str, layer: str, axis: str, start: XY, end: XY, width: float, gap: float | None, length: float)`; `axis` is "x" or "y"; `gap` is the smaller distance to other copper on the same layer at the midpoint, None when there is none within the crop.
  - `sections(board, nets, pieces) -> tuple[list[Section], list[tuple[str, dict]]]`: straight tracks of the nets whose ends share x or y within 1e-6 mm, collinear same-width neighbours merged; any other segment or arc on a measured net adds one `W_STAIRCASED` per net.
  - `cross_section(sec, pieces, zs, mask: MaskModel | None, mode: str, dz0: float | None = None) -> CrossSection`: the cut perpendicular to `sec` at its midpoint, across the crop; `mode` is "none", "exact" or "smeared" (Decisions above). The section's own net is the signal; every other conductor is ground.

- [ ] **Step 1: Write the failing tests**

```python
def test_gcpw_section():
    s, w = sections(b := load_board(FIX / "coupon_gcpw.kicad_pcb"), ("LINE",), pieces_of(b))
    assert len(s) == 1 and not w
    assert (s[0].axis, s[0].layer) == ("x", "F.Cu")
    assert (s[0].width, s[0].gap, s[0].length) == pytest.approx((0.6, 0.15, 20.0), abs=1e-6)

def test_microstrip_section_has_no_gap():
    s, _ = sections(load_board(FIX / "coupon_ms.kicad_pcb"), ("LINE",), ...)
    assert s[0].width == pytest.approx(1.35) and s[0].gap is None

def test_diagonal_net_has_no_sections():
    s, w = sections(load_board(FIX / "coupon_gcpw_45.kicad_pcb"), ("LINE",), ...)
    assert s == [] and ("W_STAIRCASED", {"net": "LINE"}) in w

def test_arc_coupon_keeps_straight_parts():  # coupon_gcpw_arc: two straights either side of the arc
    s, w = sections(load_board(FIX / "coupon_gcpw_arc.kicad_pcb"), ("LINE",), ...)
    assert len(s) == 2 and ("W_STAIRCASED", {"net": "LINE"}) in w

def test_cross_section_layers():
    cs = cross_section(s[0], pieces, zs, mask, "exact")
    sig = [r for r in cs.conductors if r.role == "signal"]
    assert len(sig) == 1 and sig[0].x1 - sig[0].x0 == pytest.approx(0.6)
    assert sig[0].z1 - sig[0].z0 == pytest.approx(0.035)
    assert any(r.eps_r == pytest.approx(3.3) for r in cs.dielectrics)  # mask present
    assert not any(r.eps_r == pytest.approx(3.3) for r in cross_section(s[0], pieces, zs, None, "none").dielectrics)
```

- [ ] **Step 2: Run** `python -m pytest tests/test_geometry_sections.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** `W_STAIRCASED`: "Net {net} has copper that is not axis-aligned (45° segments or arcs); it is staircased and its accuracy is not validated."
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: extract measured sections and their cross-sections`

---

### Task 7: cs2d — the 2D quasi-static solver

**Files:**
- Modify: `src/kicad_rf_studio/core/cs2d.py`
- Create: `tests/kicad_lines.py` (the two ported formulas of Task 8's Interfaces, written here so these tests can use them)
- Test: `tests/test_cs2d.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Rect(x0: float, x1: float, z0: float, z1: float, eps_r: float = 1.0, role: str = "")`; `role` is "signal", "ground" or "" (dielectric).
  - `@dataclass(frozen=True) CrossSection(conductors: tuple[Rect, ...], dielectrics: tuple[Rect, ...], box: tuple[float, float, float, float], sides: str = "pec")`; later dielectrics override earlier ones; `sides="open"` makes the left and right box faces Neumann (used by the parallel-plate test).
  - `@dataclass(frozen=True) Line(z0: float, eps_eff: float)`.
  - `solve(cs: CrossSection, x: np.ndarray | None = None, z: np.ndarray | None = None) -> Line`. With `x`/`z` None, it builds its own reference grid: lines at every rect edge, cells ≤ min(feature)/20 next to conductor edges, graded ×1.2 to ≤ box/40. With given lines it solves on exactly those (fit2d).
  - `reference_box(conductors, h) -> tuple`: ±(signal extent + 10h) sideways, 10h above the top copper, the bottom ground plane or −10h below.

- [ ] **Step 1: Write the failing tests**

```python
def test_homogeneous_eps_eff():          # any line fully embedded in εr = 4.0
    assert solve(ms_cs(w=1.0, h=0.5, t=0.035, er=4.0, fill_all=True)).eps_eff == pytest.approx(4.0, rel=1e-3)

def test_parallel_plate():               # strip spanning the box width, open sides
    r = solve(CrossSection((Rect(0, 2, 1.0, 1.035, role="signal"), Rect(0, 2, -0.035, 0, role="ground")),
                           (Rect(0, 2, 0, 1.0, 4.0),), (0, 2, -0.035, 1.035), sides="open"))
    assert r.z0 == pytest.approx(376.730313 * 1.0 / 2 / 2.0, rel=5e-3) and r.eps_eff == pytest.approx(4.0, rel=1e-3)

@pytest.mark.parametrize("w,h,er", [(1.35, 0.76, 4.5), (3.0, 1.5, 4.5), (0.3, 0.2, 3.66)])
def test_microstrip_vs_hammerstad_jensen(w, h, er):
    z, e = kicad_lines.microstrip(w, h, 0.035, er)
    r = solve(ms_cs(w, h, 0.035, er))
    assert r.z0 == pytest.approx(z, rel=0.02) and r.eps_eff == pytest.approx(e, rel=0.02)

@pytest.mark.parametrize("w,s,h,er", [(0.6, 0.15, 0.76, 4.5), (1.0, 0.2, 1.5, 4.5)])
def test_gcpw_vs_kicad(w, s, h, er):
    z, e = kicad_lines.cpwg(w, s, h, 0.035, er)
    r = solve(gcpw_cs(w, s, h, 0.035, er))
    assert r.z0 == pytest.approx(z, rel=0.03) and r.eps_eff == pytest.approx(e, rel=0.03)

def test_mask_lowers_z0_and_smear_matches_exact():   # 50 Ω-class GCPW
    a, b_, c = (solve(gcpw_cs(0.6, 0.15, 0.76, 0.035, 4.5, mask=m)) for m in ("none", "exact", "smeared"))
    assert -0.10 < b_.z0 / a.z0 - 1 < -0.02 and b_.eps_eff > a.eps_eff
    assert c.z0 == pytest.approx(b_.z0, rel=0.005) and c.eps_eff == pytest.approx(b_.eps_eff, rel=0.01)

def test_grid_convergence():            # given coarse lines give a different but close answer
    ref = solve(cs := gcpw_cs(0.6, 0.15, 0.76, 0.035, 4.5)); x, z = coarse_lines(cs, d=0.075)
    assert abs(solve(cs, x, z).z0 / ref.z0 - 1) < 0.05

def test_speed():                       # spec: about 0.1 s per section
    t = time.perf_counter(); solve(gcpw_cs(0.6, 0.15, 0.76, 0.035, 4.5)); assert time.perf_counter() - t < 1.0
```

`ms_cs`/`gcpw_cs`/`coarse_lines` are test helpers in `tests/test_cs2d.py`.

- [ ] **Step 2: Run** `python -m pytest tests/test_cs2d.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Node potentials φ on the grid; for each interior node, the 5-point flux balance with face permittivity = area-weighted mean of the (up to) two cells sharing that face; conductor nodes and box nodes are Dirichlet (box: 0; with `sides="open"`, left/right faces get zero flux). Assemble with `scipy.sparse.coo_matrix`, solve with `spsolve`. C = ε0 Σ_cells εr·|∇φ|²·Δx·Δz (gradient from the cell's four nodes, V = 1 so C = 2W). Z0 = 1/(c0·√(C·C0)), εeff = C/C0.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: add the cs2d quasi-static solver`

---

### Task 8: Ported KiCad line formulas, CI tier (a), NOTICE

**Files:**
- Create: `NOTICE`, `tests/test_cs2d_coupons.py`
- Modify: `tests/kicad_lines.py` (pin it to KiCad's calculator values)
- Test: `tests/test_cs2d_coupons.py`

**Interfaces:**
- Produces:
  - `microstrip(w, h, t, er) -> tuple[float, float]`: Z0 and εeff from KiCad's `pcb_calculator/transline/microstrip.cpp` quasi-static path (Hammerstad–Jensen with the thickness correction; dispersion off, f → 0, no cover).
  - `cpwg(w, s, h, t, er) -> tuple[float, float]`: from KiCad's `coplanar.cpp` with backside metal (conformal mapping with the thickness correction).
  - Files carry the GPL SPDX header and a comment naming the KiCad source files and version they were ported from.

- [ ] **Step 1: Write the failing tests**

```python
def test_kicad_microstrip_reference_point():   # value read from KiCad 9's line calculator, same inputs
    z, e = microstrip(1.35, 0.76, 0.035, 4.5)
    assert z == pytest.approx(KICAD_MS_Z, rel=1e-3) and e == pytest.approx(KICAD_MS_E, rel=1e-3)

def test_kicad_cpwg_reference_point():
    z, e = cpwg(0.6, 0.15, 0.76, 0.035, 4.5)
    assert z == pytest.approx(KICAD_CPWG_Z, rel=1e-3) and e == pytest.approx(KICAD_CPWG_E, rel=1e-3)

@pytest.mark.parametrize("name,formula,tol", [("coupon_ms", "ms", 0.02), ("coupon_gcpw", "cpwg", 0.03)])
def test_cs2d_matches_kicad_on_coupons(name, formula, tol):  # CI tier (a): mask-free, through the full pipeline
    sec, cs = coupon_cross_section(name, mask="none")
    h, t, er = coupon_stackup_values(name)
    z, _ = microstrip(sec.width, h, t, er) if formula == "ms" else cpwg(sec.width, sec.gap, h, t, er)
    assert solve(cs).z0 == pytest.approx(z, rel=tol)

def test_notice_lists_third_party():
    text = (ROOT / "NOTICE").read_text(encoding="utf-8")
    assert "SmoothMeshLines" in text and "LGPL-3.0-or-later" in text and "KiCad" in text and "GPL" in text
```

`KICAD_*` constants are filled in once from KiCad 9's calculator GUI (the implementer runs it; record the four numbers with a comment giving the inputs).
- [ ] **Step 2: Run** `python -m pytest tests/test_cs2d_coupons.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `NOTICE`, correcting `tests/kicad_lines.py` if a reference point misses (entries: CSXCAD `SmoothMeshLines`, LGPL-3.0-or-later, copied into `core/mesh/smooth.py`; KiCad line-calculator formulas, GPL-3.0-or-later, in `tests/kicad_lines.py`). Make sure CI (`.github/workflows/ci.yml`) already runs the whole `tests/` folder on Windows and ubuntu-24.04; if not, add these files to it.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `test: compare cs2d with the KiCad line formulas on the coupons`

---

### Task 9: SmoothMeshLines copy

**Files:**
- Create: `src/kicad_rf_studio/core/mesh/smooth.py`
- Test: `tests/test_mesh_smooth.py`

**Interfaces:**
- Produces: `smooth_mesh_lines(lines: np.ndarray, max_res: float, ratio: float = 1.3) -> np.ndarray`, a verbatim copy of `SmoothMeshLines` (and its helpers) from CSXCAD's Python package at the v0.37.0 tag, renamed only at the public entry, with the original LGPL-3.0-or-later header and copyright kept and one line stating the source tag. No CSXCAD import.

- [ ] **Step 1: Write the failing tests**

```python
def test_keeps_input_lines_and_limits():
    out = smooth_mesh_lines(np.array([0.0, 0.1, 10.0]), max_res=1.0, ratio=1.3)
    assert {0.0, 0.1, 10.0} <= set(np.round(out, 9))
    steps = np.diff(out)
    assert steps.max() <= 1.0 + 1e-9 and (steps[1:] / steps[:-1]).max() <= 1.3 + 1e-6
    assert (steps[:-1] / steps[1:]).max() <= 1.3 + 1e-6

def test_no_csxcad_import():
    assert "CSXCAD" not in sys.modules
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Copy the file.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `feat: vendor CSXCAD SmoothMeshLines (LGPL-3.0-or-later)`

---

### Task 10: Mesh rule

**Files:**
- Create: `src/kicad_rf_studio/core/mesh/rule.py`
- Modify: `src/kicad_rf_studio/core/mesh/__init__.py`
- Test: `tests/test_mesh_rule.py`

**Interfaces:**
- Consumes: `Protected`, `Piece`, `Rod`, `Region`, `zstack`, `Section`, `MaskModel.t_m`, `smooth_mesh_lines`.
- Produces:
  - `cell_size(sections: list[Section], fallback_width: float, n: int, lam_min: float) -> float` = min(widths and gaps)/n, capped at 0.9·λ_min/20; `fallback_width` (the narrowest track of the measured nets) is used when there are no sections.
  - `edge_lines(edge: float, inside: int, d: float) -> tuple[float, float]` returns (inner, outer) = (edge + inside·d/4, edge − inside·3d/4), where `inside` (−1 or +1) points from the edge into the metal.
  - `dz0(t_m: float, d: float, h: float) -> float` = max(t_m, min(d/3, h/4)).
  - `z_lines(zs, d, t_m, h, z_walls, extra=()) -> np.ndarray`: lines at both faces of every copper slab (one cell across each), first cell dz0 outside each face, graded ×1.3 to the walls with max cell `coarse`.
  - `merge(lines, pinned, tol) -> np.ndarray`: drops unpinned lines closer than `tol` to a neighbour; two pinned lines closer than `tol` collapse to the one whose edge is nearer (Decisions).
  - `@dataclass(frozen=True) Mesh(x: np.ndarray, y: np.ndarray, z: np.ndarray, d: float, dz0: float, pinned: dict[str, np.ndarray], edges: dict[str, list[tuple[float, int]]])`; `edges` holds the protected axis-aligned copper edges per axis as (position, inside sign) for the lint.
  - `build_mesh(geom: Geometry, prot: Protected, n: int, extra_edges: dict[str, list[tuple[float, int]]] | None = None) -> Mesh`. Rods that are not solid are snapped here: `Geometry.rods` positions move to the nearest x and y lines (returned via `Mesh`, no geometry mutation; add `snapped_rods: tuple[Rod, ...]` to `Mesh`).

- [ ] **Step 1: Write the failing tests**

```python
def test_cell_size_rule():
    s = [section(width=0.6, gap=0.15)]
    assert cell_size(s, 0.6, 2, 1e9) == pytest.approx(0.075)
    assert cell_size(s, 0.6, 3, 1e9) == pytest.approx(0.05)
    lam = lambda_min(100e9, 4.5)
    assert cell_size(s, 0.6, 2, lam) == pytest.approx(0.9 * lam / 20)

def test_edge_pattern():
    d = 0.075
    assert edge_lines(1.0, -1, d) == pytest.approx((1.0 - d / 4, 1.0 + 3 * d / 4))  # metal at x < 1
    assert edge_lines(1.0, +1, d) == pytest.approx((1.0 + d / 4, 1.0 - 3 * d / 4))

def test_dz0():
    assert dz0(0.010, 0.075, 1.5) == pytest.approx(0.025)
    assert dz0(0.010, 0.015, 1.5) == pytest.approx(0.010)
    assert dz0(0.010, 0.9, 0.1) == pytest.approx(0.025)

def test_one_z_cell_across_copper_then_dz0():
    z = z_lines(zs, 0.075, 0.010, h, walls)
    top = copper_slab(zs, "F.Cu")
    i = np.flatnonzero(np.isclose(z, top.z0))[0]
    assert z[i + 1] == pytest.approx(top.z1) and z[i + 2] - z[i + 1] == pytest.approx(0.025)
    steps = np.diff(z); assert (steps[1:] / steps[:-1]).max() <= 1.3 + 1e-6

def test_protected_region_filled_at_d_or_finer_and_graded_outside():
    m = build_mesh(gcpw_geometry, prot, 2)
    lo, hi = protected_extent_y(prot)
    inside = m.y[(m.y >= lo) & (m.y <= hi)]
    assert np.diff(inside).max() <= m.d + 1e-6
    assert ratio_max(m.x) <= 1.3 + 1e-6 and ratio_max(m.y) <= 1.3 + 1e-6

def test_merge_thresholds_and_pinned_lines_stay():
    out = merge(np.array([0, 0.01, 0.5, 0.51]), pinned={0.0, 0.5}, tol=0.075 / 3)
    assert list(out) == [0.0, 0.5]

def test_lines_quantised():
    m = build_mesh(...); assert all(np.array_equal(np.round(a, 6), a) for a in (m.x, m.y, m.z))

def test_curve_vias_snap_to_lines():
    assert all(r.at[0] in m.x and r.at[1] in m.y for r in m.snapped_rods if not r.solid)
```

- [ ] **Step 2: Run** `python -m pytest tests/test_mesh_rule.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Per in-plane axis:

```text
pinned  = edge_lines() of every protected edge (+ extra_edges), and the walls
fill    = between pinned lines inside the protected extent, uniform steps ≤ d
free    = every other copper/pad/rod/lid vertex coordinate in the crop
free    = cluster(free, d): sort, group runs whose span < d, keep each group's mean
free    = drop free lines within d/3 of any pinned line            # unprotected lines move first
lines   = smooth_mesh_lines(merge(pinned ∪ fill ∪ free, pinned, d/3), max_res=region.coarse, ratio=1.3)
lines   = merge(round(lines, 6), pinned, d/3)
```

z: `z_lines` then `merge(..., tol=dz0/3)` with copper faces pinned.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: add the mesh rule`

---

### Task 11: Shield lid

**Files:**
- Create: `src/kicad_rf_studio/core/geometry/lid.py`
- Test: `tests/test_geometry_lid.py`

**Interfaces:**
- Consumes: `Classes.shields`, `Region`, `zstack`, `Mesh.z`.
- Produces:
  - `@dataclass(frozen=True) Lid(ref: str, plate: Polygon, walls: MultiPolygon, z0: float, z1: float)`; `z0` is the top copper's top face.
  - `find_lid(board, classes, region, zs, project) -> tuple[Lid | None, list[tuple[str, dict]]]`: trigger is a shield footprint whose plate (convex hull of its frame pads) overlaps the ROI; uses `project["lid_height_mm"]`; returns `("E_LID_HEIGHT", {"refs": ...})` in the list when the height is missing (plan 3's `run` refuses on it). Plate and walls are clipped to the crop.
  - `snap_lid(lid, z: np.ndarray) -> Lid`: `z1` moves to the nearest existing z line (no new line). `build_mesh` grows the z walls to cover `z0 + lid_height` before snapping.

- [ ] **Step 1: Write the failing tests**

```python
def test_lpf915_lid_found():   # lpf915: SH1 frame around the chain, gap in the right side for R2
    lid, notes = find_lid(b, classes, region, zs, {**p, "lid_height_mm": 2.0, "harmonics": 3})
    assert lid.ref == "SH1" and lid.z1 == pytest.approx(lid.z0 + 2.0)
    assert not lid.walls.intersects(gap_probe_point)        # the frame gap stays open

def test_no_height_reports():
    lid, notes = find_lid(..., {**p, "lid_height_mm": None})
    assert lid is None and notes[0][0] == "E_LID_HEIGHT"

def test_lid_off_for_fundamental_only():
    assert find_lid(..., {**p, "lid_height_mm": 2.0, "harmonics": 1})[0] is None

def test_snap_adds_no_line():
    snapped = snap_lid(lid, z := np.array([0, 1.6, 3.55, 3.7, 6]))
    assert snapped.z1 in z

def test_frame_outside_roi_ignored():   # coupon boards have no shield
    assert find_lid(coupon_board, ...)[0] is None
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** `E_LID_HEIGHT`: "Shield {refs} covers the simulated region but project.json has no lid_height_mm. Set it, or re-create the project with --lid-height."
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit.** `feat: add the shield lid`

---

### Task 12: Mesh gates and `build_geometry`

**Files:**
- Create: `src/kicad_rf_studio/core/mesh/gates.py`
- Modify: `src/kicad_rf_studio/core/geometry/__init__.py`
- Test: `tests/test_gates.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `@dataclass Geometry(region, zs, pieces, rods, mask: MaskModel | None, sections, lid, notes: list[tuple[str, dict]])` and `build_geometry(board, project) -> Geometry` (Tasks 2–6, 11 in order; `notes` collects every warning and `E_` gate entry).
  - `@dataclass(frozen=True) LintHit(axis: str, edge: float, reason: str)`; `reason` is "on_edge", "inside_too_close" or "outside_closer".
  - `edge_lint(mesh: Mesh) -> list[LintHit]` over `mesh.edges` (in-plane only; z faces exempt).
  - `mesh_with_lint(geom, prot, n) -> Mesh`: builds, lints, on failure rebuilds once with the failing edges in `extra_edges`, and raises `KrsError("E_EDGE_LINT", axis=, edge_mm=, reason=)` if the second lint fails.
  - `@dataclass(frozen=True) Fit(section: Section, z0_mesh: float, z0_ref: float, err: float)`; `fit2d(geom, mesh) -> list[Fit]` (mesh side: `cross_section(..., "smeared", mesh.dz0)` solved on the mesh lines inside the section's perpendicular axis and `mesh.z`; reference: `"exact"` on cs2d's own grid). `check_fit2d(fits)` raises `KrsError("E_FIT2D", net=, layer=, err_pct=, limit_pct=3)` above 0.03.
  - `dt_floor_reference(mesh) -> float` = 1/(c0·√(dx⁻² + dy⁻² + dz⁻²)) in s, with dx, dy, dz the smallest steps among the rule's pinned/fill lines (mm → m).

- [ ] **Step 1: Write the failing tests**

```python
D = 0.08
def lint_mesh(x, edges): return Mesh(np.array(x), np.array([0., 1]), np.array([0., 1]), D, 0.01, {}, {"x": edges, "y": []})

def test_lint_clean():          assert edge_lint(lint_mesh([0.98, 1.06], [(1.0, -1)])) == []
def test_lint_line_on_edge():   assert edge_lint(lint_mesh([0.98, 1.0, 1.06], [(1.0, -1)]))[0].reason == "on_edge"
def test_lint_1um_inside():     assert edge_lint(lint_mesh([0.999, 1.06], [(1.0, -1)]))[0].reason == "inside_too_close"
def test_lint_outside_closer(): assert edge_lint(lint_mesh([0.97, 1.02], [(1.0, -1)]))[0].reason == "outside_closer"

def test_remesh_once_fixes(monkeypatch):   # first build places a line on an edge; the rebuild with extra_edges is clean
    m = mesh_with_lint(geom_with_unpinned_edge, prot, 2); assert edge_lint(m) == []

def test_remesh_failure_blocks(monkeypatch):  # build_mesh patched to always put a line on the edge
    with pytest.raises(KrsError, match="E_EDGE_LINT"): mesh_with_lint(...)

def test_fit2d_passes_on_rule_mesh():
    fits = fit2d(g := build_geometry(*coupon("coupon_gcpw_masked")), mesh_with_lint(g, prot, 2))
    assert fits and all(f.err < 0.03 for f in fits)

def test_fit2d_blocks_on_coarse_mesh():       # a mesh with 0.3 mm cells across a 0.6 mm GCPW
    with pytest.raises(KrsError, match="E_FIT2D"): check_fit2d(fit2d(g, coarse_mesh))

def test_dt_floor_reference():
    m = Mesh(np.array([0, .075, 1]), np.array([0, .05, 1]), np.array([0, .035, 1]), .075, .025, {...}, {})
    assert dt_floor_reference(m) == pytest.approx(1 / (299792458 * math.sqrt(.075e-3**-2 + .05e-3**-2 + .035e-3**-2)))
```

- [ ] **Step 2: Run** `python -m pytest tests/test_gates.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Messages: `E_EDGE_LINT` "A mesh line sits badly at the copper edge {edge_mm} mm ({axis}, {reason}) even after one re-mesh. Use --preset strict, or widen the gap at that edge." `E_FIT2D` "The mesh misses the 2D reference on net {net} ({layer}) by {err_pct} % (limit {limit_pct} %). Use --preset strict."
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit.** `feat: add the mesh gates`

---

### Task 13: `cost` — the 2D readout

**Files:**
- Modify: `src/kicad_rf_studio/cli.py`, `src/kicad_rf_studio/core/messages.py`, `src/kicad_rf_studio/core/project.py` (`region_expand_h`, `mesh.n` defaults read with `.get`; `new` writes `"region": {"expand_h": 3.0}` and `"mesh": {"n": 2|3 by preset}`; schema unchanged since both are optional)
- Test: `tests/test_cli_cost.py`

**Interfaces:**
- Consumes: `load_project`, `board_file`, `load_board`, `build_geometry`, `cross_section`, `solve`.
- Produces: `kicad-rf-studio cost PROJECT`: prints `I_2D_HEADER`, then one `I_2D_SECTION` per section (in chain-net order, then by position), then the geometry notes; exits 0. No mesh, no worker (plan 3 adds them after this output).
  - `I_2D_HEADER`: "2D estimate: bends, vias, pads and parts not included"
  - `I_2D_SECTION`: "{net} on {layer}: width {width_mm} mm, gap {gap_mm}, length {length_mm} mm — Z0 {z0} Ω, εeff {eeff} without mask; Z0 {z0_mask} Ω, εeff {eeff_mask} with mask" (`gap_mm` is "none" for microstrip; numbers as `:.2f`/`:.3f`)
  - `W_NO_SECTIONS`: "The measured nets have no straight, axis-aligned sections, so there is no 2D estimate."

- [ ] **Step 1: Write the failing tests**

```python
def test_cost_prints_2d_readout(tmp_path, capsys):
    proj = new_project(tmp_path, "coupon_gcpw_masked")
    assert main(["cost", str(proj)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "2D estimate: bends, vias, pads and parts not included"
    row = out[1]
    assert row.startswith("LINE on F.Cu: width 0.600 mm, gap 0.150, length 20.000 mm")
    z, zm = parse_z0s(row); assert zm < z

def test_cost_on_45_degree_coupon(tmp_path, capsys):
    main(["cost", str(new_project(tmp_path, "coupon_gcpw_45"))])
    out = capsys.readouterr().out
    assert "no straight, axis-aligned sections" in out and "staircased" in out

def test_cost_starts_no_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", fail); main(["cost", str(new_project(tmp_path, "coupon_ms"))])
    assert "openEMS" not in sys.modules

def test_new_writes_region_and_mesh_defaults(tmp_path):
    d = load_project(new_project(tmp_path, "coupon_ms", preset="strict"))
    assert d["region"] == {"expand_h": 3.0} and d["mesh"] == {"n": 3}
```

- [ ] **Step 2: Run** `python -m pytest tests/test_cli_cost.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the `cost` subparser and `_cost`.
- [ ] **Step 4: Run** the full suite, then `kicad-rf-studio cost` on a `coupon_gcpw_masked` project by hand. Expected: all pass; the readout shows the mask lowering Z0.
- [ ] **Step 5: Commit.** `feat: print the 2D Z0 and εeff readout in cost`

---

## Not in this plan

- Port boxes, C_box, the PEC-dump port check, part roles and the CSX build: plan 3 (`Protected.boxes` is the hook).
- The 0.8 × dt comparison against openEMS and the limiting node: plan 3, using `dt_floor_reference`.
- The local-refinement offer for staircased copper and the P0-A refusal above budget: plan 5 decides from P0-A.
- Via tenting and padstacks are still not read (plan 1 limit); a shunt with both pads on chain nets has no meaningful chain side, which matters only to plan 3's part roles.
