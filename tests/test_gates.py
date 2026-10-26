# SPDX-License-Identifier: GPL-3.0-or-later
import math
from dataclasses import replace
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

from kicad_rf_studio.cli import main
from kicad_rf_studio.core.geometry import build_geometry, chain_of
from kicad_rf_studio.core.geometry.sections import Section
from kicad_rf_studio.core.geometry.vias import via_rods
from kicad_rf_studio.core.geometry.zstack import substrate_h
from kicad_rf_studio.core.kicad import classify, load_board, trace_chain
from kicad_rf_studio.core.kicad.stackup import kicad_default
from kicad_rf_studio.core.mesh import Mesh, build_mesh, gates
from kicad_rf_studio.core.mesh.gates import (Fit, LintHit, check_fit2d, dt_floor_reference, edge_lint, fit2d,
                                             mesh_with_lint)
from kicad_rf_studio.core.mesh.protect import protected_set
from kicad_rf_studio.core.messages import KrsError, render
from kicad_rf_studio.core.project import REACH_H, load_project
from test_cli_cost import SEG, gcpw
from test_mesh_rule import FIXTURES, build

FIX = Path(__file__).parent / "fixtures"
D = 0.08
C0 = 299792458.0


@cache
def project_of(name, start="", end="", *more):
    """`name`'s board and its project.json: through `new` (f0 915 MHz, 3 harmonics) for a chain between two pads, by
    hand for a pad-less coupon (R-P2-1, R-P2-8: LINE alone, no ports), at the mesh tests' 3 GHz top of band."""
    board = load_board(FIX / f"{name}.kicad_pcb")
    if not start:
        return board, {"f0_hz": 1e9, "harmonics": 3, "band_factor": 1.0, "stackup": board.stackup.to_json(),
                       "chain": {"start": "", "end": "", "nets": ["LINE"], "series": [], "shunt": []}, "ports": []}
    with TemporaryDirectory() as out:
        assert main(["new", str(FIX / f"{name}.kicad_pcb"), "--start", start, "--end", end, "--f0", "915MHz",
                     "-o", out, *more]) == 0
        return board, load_project(Path(out) / "project.json")


@cache
def geom_of(name, start="", end=""):
    """build_geometry's geometry of `name` (with a 2 mm lid where `new` makes the project) and the protected set it
    keeps."""
    board, p = project_of(name, start, end, *(["--lid-height", "2"] if start else []))
    g = build_geometry(board, p)
    return g, g.protected


def lint_mesh(x, edges):
    return Mesh(np.array(x), np.array([0., 1]), np.array([0., 1]), D, 0.01, {}, {"x": edges, "y": []})


def test_lint_clean():
    assert edge_lint(lint_mesh([0.98, 1.06], [(1.0, -1)])) == []


def test_lint_line_on_edge():
    assert edge_lint(lint_mesh([0.98, 1.0, 1.06], [(1.0, -1)])) == [LintHit("x", 1.0, "on_edge")]


def test_lint_1um_inside():
    assert edge_lint(lint_mesh([0.999, 1.06], [(1.0, -1)]))[0].reason == "inside_too_close"


def test_lint_inside_line_d_over_8_in_passes():  # spec 5.5: nearer than d/8 fails
    assert edge_lint(lint_mesh([0.99, 1.06], [(1.0, -1)])) == []
    assert edge_lint(lint_mesh([0.991, 1.06], [(1.0, -1)])) == [LintHit("x", 1.0, "inside_too_close")]


def test_lint_outside_closer():
    assert edge_lint(lint_mesh([0.97, 1.02], [(1.0, -1)]))[0].reason == "outside_closer"


@pytest.mark.parametrize(("e", "a", "side"), [(-100.889, 0.02, 1), (-100.778, 0.01875, -1), (110.0015, 0.01875, 1)])
def test_lint_fails_a_tie_on_the_grid(e, a, side):
    # T7: a line pair symmetric about an edge ties the outer line to the metal under openEMS's inclusive rule (−6.7 % in
    # a probe), so a tie fails; on the 1e-6 mm grid it is exact, but float noise put either distance ahead (T10 round 2)
    m = Mesh(np.array([0.0, 1.0]), np.round([e - a, e + a], 6), np.array([0.0, 1.0]), 0.075, 0.025, {},
             {"x": [], "y": [(e, side)]})
    assert edge_lint(m) == [LintHit("y", e, "outside_closer")]


def test_remesh_once_fixes(monkeypatch):  # spec 5.5: the lint's one automatic re-mesh
    geom, prot = geom_of("coupon_gcpw")
    calls = []

    def first_puts_a_line_on_an_edge(g, p, n, extra_edges=None):
        calls.append(extra_edges)
        m = build_mesh(g, p, n, extra_edges)
        return m if extra_edges else replace(m, x=np.union1d(m.x, [m.edges["x"][0][0]]))

    monkeypatch.setattr(gates, "build_mesh", first_puts_a_line_on_an_edge)
    m = mesh_with_lint(geom, prot, 2)
    assert edge_lint(m) == [] and len(calls) == 2 and calls[1] == {"x": [m.edges["x"][0]], "y": []}


def test_remesh_failure_blocks(monkeypatch):
    geom, prot = geom_of("coupon_gcpw")
    edge = build_mesh(geom, prot, 2).edges["x"][0][0]

    def always_puts_a_line_on_the_edge(g, p, n, extra_edges=None):
        m = build_mesh(g, p, n, extra_edges)
        return replace(m, x=np.union1d(m.x, [edge]))

    monkeypatch.setattr(gates, "build_mesh", always_puts_a_line_on_the_edge)
    with pytest.raises(KrsError) as e:  # Task 2 ruling: str(KrsError) is the message, so check .code, not match=
        mesh_with_lint(geom, prot, 2)
    assert (e.value.code, e.value.params) == ("E_EDGE_LINT", {"axis": "x", "edge_mm": edge, "reason": "on edge",
                                                              "n": 2})
    assert str(e.value) == render("E_EDGE_LINT", axis="x", edge_mm=edge, reason="on edge", n=2)


@pytest.mark.parametrize(("name", "n", "pct"), [("coupon_gcpw", 2, 2.53), ("coupon_gcpw_masked", 3, 2.79)])
def test_fit2d_passes_on_rule_mesh(name, n, pct):
    # R-P2-20: the cases measured under the 3 % gate; coupon_gcpw_masked reads +3.78 % at n = 2 (carried to P0-A)
    g, prot = geom_of(name)
    fits = fit2d(g, mesh_with_lint(g, prot, n))
    assert [f.section for f in fits] == g.sections and all(f.err < 0.03 for f in fits)
    assert 100 * (fits[0].z0_mesh / fits[0].z0_ref - 1) == pytest.approx(pct, abs=0.01)
    check_fit2d(fits, 0.03, n)


@pytest.mark.parametrize("lines", [
    np.round(np.arange(-130.2, -69.8, 0.3), 6),  # T7: multiples of 0.3 mm put a grid node on LINE and on GND (a short)
    np.round(np.r_[np.arange(-130.0, -101.0, 0.5), -101.0, -99.65, np.arange(-99.0, -69.9, 0.5)], 6),  # LINE lost
])
def test_fit2d_blocks_on_coarse_mesh(lines):
    # T7 fix ruling: a mesh that shorts or loses the line is no skip and no NaN; it misses the reference by 100 %
    g, prot = geom_of("coupon_gcpw_masked")
    fits = fit2d(g, replace(mesh_with_lint(g, prot, 2), y=lines))
    assert [(f.z0_mesh, f.err) for f in fits] == [(0.0, 1.0)]
    with pytest.raises(KrsError) as e:
        check_fit2d(fits, 0.03, 2)
    assert e.value.code == "E_FIT2D"
    assert e.value.params == {"net": "LINE", "layer": "F.Cu", "err_pct": 100.0, "limit_pct": "3", "n": 2}


def test_check_fit2d_names_the_worst_section_over_3_percent():
    a, b = (Section(net, "F.Cu", "x", (0.0, 0.0), (10.0, 0.0), 0.6, 0.15, 10.0, (5.0, 0.0)) for net in ("A", "B"))
    check_fit2d([Fit(a, 51.5, 50.0, 0.03), Fit(b, 48.5, 50.0, 0.03)], 0.03, 2)  # at the limit
    with pytest.raises(KrsError) as e:
        check_fit2d([Fit(a, 51.6, 50.0, 0.032), Fit(b, 47.5, 50.0, 0.05)], 0.03, 2)
    assert (e.value.code, e.value.params) == ("E_FIT2D", {"net": "B", "layer": "F.Cu", "err_pct": 5.0,
                                                          "limit_pct": "3", "n": 2})
    assert str(e.value) == ("The mesh misses the 2D reference on net B (F.Cu) by 5.0 % (limit 3 %) at mesh.n 2. "
                            "Set mesh.n to 3 in project.json.")


def approx_s(t):
    """`t`, a time step in s (about 1e-13), to 1e-9 of itself: pytest.approx's default abs of 1e-12 s would take 0."""
    return pytest.approx(t, rel=1e-9, abs=0)


def test_dt_floor_reference():
    x, y, z = np.array([0, .075, 1]), np.array([0, .05, 1]), np.array([0, .035, 1])
    m = Mesh(x, y, z, .075, .025, {"x": x, "y": y, "z": z}, {})
    assert dt_floor_reference(m) == approx_s(1 / (299792458 * math.sqrt(.075e-3**-2 + .05e-3**-2 + .035e-3**-2)))
    # T10 carry: the smallest cell of the final lines counts though no pinned line bounds it (the grading placed it)
    graded = replace(m, x=np.array([0, .03, .075, 1]))
    assert dt_floor_reference(graded) == approx_s(1 / (299792458 * math.sqrt(.03e-3**-2 + .05e-3**-2 + .035e-3**-2)))


def openems_dt(m):
    """A floor under openEMS's dt on `m`'s lines, in s: its default method (operator.cpp CalcTimestep_Var3, Rennings)
    in vacuum, where a dielectric only raises it, over the inner nodes (the walls' cells are coarse). With an E edge
    along n and the cells Δ, dual widths W = (Δ[i−1] + Δ[i])/2 and ratios r = Δ[j]/Δ[j−1] of the other two axes p, q,
    its 2/√(w/c²) has w/c² = Σ_{p,q} Σ (1/(Δ[j]W[j+1]) + 1/(Δ[j]W[j]) + 1/(Δ[j−1]W[j]) + 1/(Δ[j−1]W[j−1]))
    + (1/(Δ_n[i]W_n[i]) + 1/(Δ_n[i]W_n[i+1]))·(2 + r_p + r_q − 2·min(1, r_p, r_q)); on a uniform grid it is the
    vacuum Courant step."""
    cells = [np.diff(v) * 1e-3 for v in (m.x, m.y, m.z)]
    dual = [np.r_[c[0], (c[1:] + c[:-1]) / 2, c[-1]] for c in cells]
    j = [np.arange(1, len(c)) for c in cells]  # the inner nodes
    qp = [1 / (c[k] * w[k + 1]) + 1 / (c[k] * w[k]) + 1 / (c[k - 1] * w[k]) + 1 / (c[k - 1] * w[k - 1])
          for c, w, k in zip(cells, dual, j)]
    r = [c[k] / c[k - 1] for c, k in zip(cells, j)]
    worst = 0.0
    for n in range(3):
        p, q = (n + 1) % 3, (n + 2) % 3
        c, w, k = cells[n], dual[n], j[n]
        t = (1 / (c[k] * w[k]) + 1 / (c[k] * w[k + 1])).max()
        g = 2 + r[p][:, None] + r[q][None, :] - 2 * np.minimum(1, np.minimum(r[p][:, None], r[q][None, :]))
        worst = max(worst, (qp[p][:, None] + qp[q][None, :] + t * g).max())
    return 2 / (C0 * math.sqrt(worst))


def test_openems_dt_is_the_courant_step_on_a_uniform_grid():  # the model's own check
    v = np.arange(0, 2.0001, 0.1)
    m = Mesh(v, v, v, 0.1, 0.1, {}, {})
    courant = 0.1e-3 / (C0 * math.sqrt(3))
    assert openems_dt(m) == approx_s(courant) and dt_floor_reference(m) == approx_s(courant)


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize(("name", "start", "end"), FIXTURES)
def test_rule_meshes_pass_the_lint_and_never_trip_the_timestep_floor(name, start, end, n):
    # T10 carry: openEMS's dt on our own mesh never falls under plan 3's 0.8 × the reference, which counts the smallest
    # cells of the final lines (test_dt_floor_reference; lpf915 at n = 2 once had a 30.3 µm x cell between pinned lines
    # 35.2 µm apart); the copper's z faces carry lines and are exempt from the lint
    g, prot = geom_of(name, start, end)
    m = mesh_with_lint(g, prot, n)
    assert edge_lint(m) == [] and any(s.z1 in m.z for s in g.zs if s.kind == "copper")
    assert openems_dt(m) >= 0.8 * dt_floor_reference(m)


@pytest.mark.parametrize("name", [name for name, start, _ in FIXTURES if not start])
def test_build_geometry_assembles_tasks_2_to_6(name):
    # test_mesh_rule's builder does by hand what build_geometry does from project.json; on the coupons the
    # connectivity check and the lid add no note
    assert geom_of(name)[0] == build(FIX / f"{name}.kicad_pcb", reach_h=REACH_H)[0]


def test_build_geometry_reads_the_chain_and_the_lid_from_new():
    board, p = project_of("lpf915", "U1.1", "J1.1")  # no --lid-height
    assert chain_of(p) == trace_chain(board, "U1.1", "J1.1")
    g = build_geometry(board, p)
    assert g.lid is None and ("E_LID_HEIGHT", {"refs": "SH1"}) in g.notes  # a gate entry: plan 3's run refuses
    lidded = geom_of("lpf915", "U1.1", "J1.1")[0]
    assert lidded.lid.ref == "SH1" and lidded.lid.z1 == pytest.approx(lidded.lid.z0 + 2)
    assert not [code for code, _ in lidded.notes if code.startswith("E_")]
    untagged = build_geometry(board, {**p, "classes": {**p["classes"], "shields": []}})  # the user's edit wins
    assert untagged.lid is None and "E_LID_HEIGHT" not in [code for code, _ in untagged.notes]


def mini(ports=()):
    """project.json by hand for a mini board: SIG the chain, `ports`, KiCad's 0.8 mm default stackup, 3 GHz."""
    return {"f0_hz": 1e9, "harmonics": 3, "band_factor": 1.0, "stackup": kicad_default(0.8).to_json(),
            "chain": {"start": "", "end": "", "nets": ["SIG"], "series": [], "shunt": []}, "ports": list(ports)}


def edge_cuts(*boxes):
    return "".join(f'(gr_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.05) (type default)) (fill no) '
                   f'(layer "Edge.Cuts") (uuid "e{k}")) ' for k, (x0, y0, x1, y1) in enumerate(boxes))


def track(x0, x1, y, uuid="t1"):
    return f'(segment (start {x0} {y}) (end {x1} {y}) (width 0.3) (layer "F.Cu") (net "SIG") (uuid "{uuid}")) '


@pytest.mark.parametrize(("x0", "ports"), [
    (45, []),  # 5 mm off the board: an empty ROI
    (41, []),  # 1 mm off: a sliver of the board
    (45, [{"signal": "J9.1", "reference": {"point": [20.0, 15.0], "layer": "F.Cu"}}]),  # a port's reference on it
])
def test_a_chain_off_the_outline_is_an_error(mini_board, x0, ports):
    # R-P2-14: of several Edge.Cuts loops (a panel, a frame, a coupon beside the board) plan 1 keeps the largest; a
    # chain on another one gave a raw GEOS error, or silently a region on the wrong board. A microstrip coupon's port
    # takes the nearest ground copper on its layer, in a panel the main board's, which then lies in the ROI
    body = edge_cuts((0, 0, 40, 30), (x0, 0, x0 + 10, 10)) + track(x0 + 0.5, x0 + 8, 5)
    with pytest.raises(KrsError) as e:
        build_geometry(mini_board(body), mini(ports))
    assert e.value.code == "E_CHAIN_OFF_OUTLINE" and e.value.params == {"nets": "SIG"}


@pytest.mark.parametrize("other", [
    (100, 0, 110, 10),  # a coupon past the crop: its run was a section, and fit2d's reference solve a raw ValueError
    (50, 0, 60, 10),  # a coupon in the crop: its run was measured and gated, and the ROI ran out to the board's edge
    (42, 0, 82, 30),  # a panel, a second board of the same size and nets: its run was measured
])
def test_chain_copper_on_another_outline_is_an_error(mini_board, other):
    # R-P2-14: copy and paste keeps a track's net, so the chain's nets also have copper on the other loop
    body = edge_cuts((0, 0, 40, 30), other) + track(5, 35, 15) + track(other[0] + 1, other[2] - 1, 5, "t2")
    with pytest.raises(KrsError) as e:
        build_geometry(mini_board(body), mini())
    assert e.value.code == "E_CHAIN_OFF_OUTLINE" and e.value.params == {"nets": "SIG"}
    assert str(e.value).startswith("The measured nets (SIG) have copper outside the board outline, or no copper")


def test_chain_copper_partly_off_the_outline_builds(mini_board):  # as an edge-launch pad, a track run past the edge
    body = edge_cuts((0, 0, 40, 30)) + track(10, 41, 15)
    assert [s.net for s in build_geometry(mini_board(body), mini()).sections] == ["SIG"]


@pytest.mark.parametrize("outline", [True, False])
def test_a_chain_with_no_copper_is_an_error(mini_board, outline):  # a net name edited by hand in project.json
    body = edge_cuts((0, 0, 40, 30)) * outline + track(10, 30, 15)
    with pytest.raises(KrsError) as e:  # it was a raw ValueError from total_bounds of nothing
        build_geometry(mini_board(body), {**mini(), "chain": {**mini()["chain"], "nets": ["SGI"]}})
    assert e.value.code == "E_CHAIN_OFF_OUTLINE" and e.value.params == {"nets": "SGI"}


def test_a_chain_on_the_kept_outline_builds(mini_board):
    # the ROI takes the project's ports (a reference point, y down in project.json) and its region.expand_h (spec 5.1)
    body = edge_cuts((0, 0, 40, 30), (41, 0, 51, 10)) + track(10, 30, 15)
    p = {**mini([{"signal": "J9.1", "reference": {"point": [5.0, 25.0], "layer": "F.Cu"}}]), "region": {"expand_h": 2}}
    g = build_geometry(mini_board(body), p)
    assert g.region.roi.bounds == pytest.approx((5 - 1.42, -25 - 1.42, 30.15 + 1.42, -14.85 + 1.42))
    assert [s.net for s in g.sections] == ["SIG"]


def test_build_geometry_notes_the_connectivity_gate(mini_board):  # Task 4: E_OPEN_IN_ROI is a gate entry in notes
    body = edge_cuts((0, 0, 40, 30)) + track(5, 15, 15) + track(16, 30, 15, "t2")
    assert ("E_OPEN_IN_ROI", {"net": "SIG"}) in build_geometry(mini_board(body), mini()).notes


def twin(mini_board_file, line):
    """test_cli_cost's 0.6 mm GCPW of SIG on `line`, the plane on the other outer layer."""
    return build_geometry(load_board(mini_board_file(gcpw(line))), mini())  # tests/test_cli_cost.py


def test_geometry_keeps_both_masks_and_the_protected_set_it_built():  # C-41, M-4
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2")
    g = build_geometry(board, p)
    assert {k: m.side for k, m in g.masks.items()} == {"F.Cu": "F", "B.Cu": "B"}
    assert g.protected == protected_set(board, chain_of(p), classify(board, p["classes"]), g.pieces,
                                        substrate_h(g.zs), reach_h=p["mesh"]["reach_h"])
    assert via_rods(board, g.region.crop, g.zs, g.protected) == g.rods


def test_an_off_chain_part_made_a_port_is_protected():  # spec 5.4, R3-069
    board, p = project_of("lpf915", "U1.1", "J1.1", "--lid-height", "2")
    c4 = board.pads("C4.1")[0].polygon  # on VDD: neither measured nor ground copper
    for role, inside in (("open", False), ("port", True)):
        g = build_geometry(board, {**p, "others": [{**p["others"][0], "role": role}]})
        assert g.protected.area["F.Cu"].buffer(1e-6).contains(c4) == inside


def test_fit2d_reads_each_section_under_its_own_sides_mask(mini_board_file):  # C-7
    refs = []
    for line in ("F.Cu", "B.Cu"):
        g = twin(mini_board_file, line)
        refs.append(fit2d(g, mesh_with_lint(g, g.protected, 2))[0].z0_ref)
    assert refs[1] == pytest.approx(refs[0], rel=1e-3)


def test_copper_on_the_line_at_the_reference_cut_is_a_gate(mini_board_file):  # C-42: never E_INTERNAL
    rect = '(gr_rect (start 4 14.95) (end 36 15.05) (stroke (width 0)) (fill yes) (layer "F.Cu") (uuid "r1")) '
    g = build_geometry(load_board(mini_board_file(SEG.format(5, 15, 35, 15, 0.3, "F.Cu", "SIG", "s") + rect)), mini())
    with pytest.raises(KrsError) as e:
        fit2d(g, mesh_with_lint(g, g.protected, 2))
    assert (e.value.code, e.value.params) == ("E_FIT2D_SHORT", {"net": "SIG", "layer": "F.Cu"})


def fit(err):
    s = Section("RF_B", "F.Cu", "x", (0.0, 0.0), (1.0, 0.0), 0.6, 0.15, 1.0, (0.5, 0.0))
    return Fit(s, 50.0, 50.0 / (1 + err), err)


@pytest.mark.parametrize(("n", "code"), [(2, "E_FIT2D"), (3, "E_FIT2D_FINE")])
def test_the_fit2d_advice_follows_n_and_the_limit_is_a_project_field(n, code):  # C-43, C-10
    with pytest.raises(KrsError) as e:
        check_fit2d([fit(0.044)], 0.03, n)
    assert (e.value.code, e.value.params) == (code, {"net": "RF_B", "layer": "F.Cu", "err_pct": 4.4,
                                                     "limit_pct": "3", "n": n})
    check_fit2d([fit(0.044)], 0.05, n)  # a raised gates.fit2d_limit lets it pass


BAD_Y = Mesh(np.array([0.0, 1.0]), np.array([-100.6, -100.4505, -100.3]), np.array([0.0, 1.0]), D, 0.01, {},
             {"x": [], "y": [(-100.4505, -1)]})


def test_the_edge_lint_names_a_y_edge_in_kicads_frame(monkeypatch):  # C-43, L-4
    monkeypatch.setattr(gates, "build_mesh", lambda *a, **k: BAD_Y)
    with pytest.raises(KrsError) as e:
        mesh_with_lint(None, None, 2)
    assert (e.value.code, e.value.params) == ("E_EDGE_LINT", {"axis": "y", "edge_mm": 100.4505,
                                                              "reason": "on edge", "n": 2})
