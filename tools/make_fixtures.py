# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the synthetic fixture boards in tests/fixtures, with pcbnew's own pad outlines beside them.

Dev-time only: it runs under KiCad 9's bundled Python, and the product never imports it. Regenerate
from the repository root with

    "%KICAD_PYTHON%" tools/make_fixtures.py tests/fixtures [name ...]

KICAD_PYTHON names python.exe in KiCad 9's bin folder. With no names it builds every board in BOARDS; a
rerun of named boards rewrites only those. Before pcbnew loads, the script points
KICAD_CONFIG_HOME, KICAD_DOCUMENTS_HOME, KICAD_CACHE_HOME, TEMP and TMP at build/kicad-profile in this
repository, creating it, whatever the caller's environment says, so KiCad reads and writes none of the
user's settings. Run kicad-cli (to preview a fixture, say) with those five variables set the same way.

Footprints are loaded by path from KICAD9_FOOTPRINT_DIR, or from <bin>/../share/kicad/footprints when it
is unset, because the isolated profile has no library table. The uuids are seeded, so a rerun writes the
same files.

<name>.pads.json maps each pad uuid to {"name": "REF.NUM", "center": [x, y], "polygons": [ring, ...]}:
pcbnew's ShapePos and the outer rings of GetEffectivePolygon(<first copper layer>, ERROR_INSIDE), in mm
with y up. A pad without copper (a paste-only pad) uses its first layer.
"""
import json
import math
import os
import sys
import zlib
from pathlib import Path

PROFILE = Path(__file__).resolve().parents[1] / "build" / "kicad-profile"
PROFILE.mkdir(parents=True, exist_ok=True)
for var in ("KICAD_CONFIG_HOME", "KICAD_DOCUMENTS_HOME", "KICAD_CACHE_HOME", "TEMP", "TMP"):
    os.environ[var] = str(PROFILE)  # set before pcbnew loads

import pcbnew  # noqa: E402

FP_DIR = Path(os.environ.get("KICAD9_FOOTPRINT_DIR")
              or Path(sys.executable).parents[1] / "share" / "kicad" / "footprints")
MM = pcbnew.FromMM
# KiCad's default stackup (BOARD_STACKUP::BuildDefaultStackupList) for 2 layers and 0.8 mm: the core is
# the thickness less 2 x 0.035 mm copper and 2 x 0.01 mm mask. pcbnew writes only a stackup it has
# read, so new_board() splices this into a saved empty board and loads that back.
STACKUP = """(stackup
 (layer "F.SilkS" (type "Top Silk Screen")) (layer "F.Paste" (type "Top Solder Paste"))
 (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01)) (layer "F.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 1" (type "core") (thickness 0.71) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "B.Cu" (type "copper") (thickness 0.035)) (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
 (layer "B.Paste" (type "Bottom Solder Paste")) (layer "B.SilkS" (type "Bottom Silk Screen"))
 (copper_finish "None") (dielectric_constraints no))
"""
# A zone fill keeps the larger of the zone's clearance and the netclass's (0.2 mm by default). LoadBoard
# compiles <board>.kicad_dru into its rules, and this one brings every clearance down to the 0.15 mm gap.
RULES = '(version 1)\n(rule "gcpw gap" (constraint clearance (min 0.15mm)))\n'


def pt(x, y):
    return pcbnew.VECTOR2I_MM(x, y)


def pad_at(fp, number):
    p = fp.FindPadByNumber(number).GetPosition()
    return p.x / 1e6, p.y / 1e6


def net(b, name):
    n = b.FindNet(name)
    if n is None:
        n = pcbnew.NETINFO_ITEM(b, name)
        b.Add(n)
    return n


def copper(b, item, name, width):
    item.SetWidth(MM(width))
    item.SetLayer(pcbnew.F_Cu)
    item.SetNet(net(b, name))
    b.Add(item)


def track(b, name, width, *points):
    """F.Cu segments through `points` (mm)."""
    for p, q in zip(points, points[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pt(*p))
        t.SetEnd(pt(*q))
        copper(b, t, name, width)


def arc(b, name, width, start, mid, end):
    a = pcbnew.PCB_ARC(b)
    a.SetStart(pt(*start))
    a.SetMid(pt(*mid))
    a.SetEnd(pt(*end))
    copper(b, a, name, width)


def via(b, at):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pt(*at))
    v.SetDrill(MM(0.3))
    v.SetWidth(MM(0.6))
    v.SetNet(net(b, "GND"))
    b.Add(v)


def zone(b, layer, corners, clearance=0.15):
    """A GND zone joined solidly to GND pads, `clearance` mm from other nets (0.15: the GCPW gap)."""
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(net(b, "GND"))
    z.SetLocalClearance(MM(clearance))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.Outline().NewOutline()
    for c in corners:
        z.Outline().Append(pt(*c))
    b.Add(z)


def rect(b, layer, x0, y0, x1, y1, filled=False):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetStart(pt(x0, y0))
    s.SetEnd(pt(x1, y1))
    s.SetLayer(layer)
    s.SetFilled(filled)
    s.SetWidth(0 if filled else MM(0.05))
    b.Add(s)


def place(b, lib_id, ref, value, at, angle=0, nets=None):
    lib, name = lib_id.split(":")
    fp = pcbnew.FootprintLoad(str(FP_DIR / f"{lib}.pretty"), name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetPosition(pt(*at))
    fp.SetOrientationDegrees(angle)
    b.Add(fp)
    for p in fp.Pads():
        if p.GetNumber() in (nets or {}):
            p.SetNet(net(b, nets[p.GetNumber()]))
    return fp


def fence_points(path, offset, pitch=1.0):
    """Points `offset` either side of `path` every `pitch` along it. A path is a list of
    ("line", start, end) and ("arc", centre, radius, from_deg, to_deg), with y down."""
    for kind, *g in path:
        if kind == "line":
            (x0, y0), (x1, y1) = g
            length = math.hypot(x1 - x0, y1 - y0)
            ux, uy = (x1 - x0) / length, (y1 - y0) / length
            for k in range(int(length / pitch) + 1):
                for side in (offset, -offset):
                    yield x0 + ux * k * pitch - uy * side, y0 + uy * k * pitch + ux * side
        else:
            (cx, cy), r, t0, t1 = g
            for rr in (r + offset, r - offset):
                n = max(1, round(math.radians(abs(t1 - t0)) * rr / pitch))
                for k in range(n + 1):
                    t = math.radians(t0 + (t1 - t0) * k / n)
                    yield cx + rr * math.cos(t), cy + rr * math.sin(t)


def fence(b, points, box, keep=0.5):
    """GND vias at `points`, except where the centre of one would come within `keep` mm of a pad or of a
    track of another net (0.5: the via's edge 0.2 mm off), closer than 0.8 mm to a placed via, or within
    0.8 mm of the board edge (KiCad's 0.5 mm copper-to-edge clearance plus the via's radius)."""
    x0, y0, x1, y1 = box
    blockers = list(b.GetPads()) + [t for t in b.GetTracks() if t.GetNetname() != "GND"]
    placed = []
    for x, y in points:
        if (x0 + 0.8 <= x <= x1 - 0.8 and y0 + 0.8 <= y <= y1 - 0.8
                and all(math.dist((x, y), q) >= 0.8 for q in placed)
                and not any(i.HitTest(pt(x, y), MM(keep)) for i in blockers)):
            via(b, (x, y))
            placed.append((x, y))


def coupon(b, ms=False, mask_open=True, pads=False, aux=False, angle=0, bend=False):
    """20 mm of net LINE from (100, 100) along +x, turned by `angle`: a 1.35 mm microstrip over a B.Cu GND
    zone, or a 0.6 mm GCPW with 0.15 mm gaps to an F.Cu GND zone and a via fence 0.6 mm from each line edge.
    The board runs 1 mm past the ends and 5 mm to the sides. `bend` puts a 90-degree arc of 5 mm radius in
    the middle of the 20 mm; `aux` stops the top ground 1.5 mm from the centre line on one side and runs a
    0.3 mm AUX trace 0.2 mm beyond it."""
    w = 1.35 if ms else 0.6
    if bend:
        a = (20 - 2.5 * math.pi) / 2  # the straight runs either side of the 7.85 mm arc
        path = [("line", (0, 0), (a, 0)), ("arc", (a, 5), 5, -90, 0), ("line", (a + 5, 5), (a + 5, a + 5))]
        x0, y0, x1, y1 = -1, -5, a + 10, a + 6
    else:
        path = [("line", (0, 0), (20, 0))]
        x0, y0, x1, y1 = -1, -5, 21, 5
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def at(p):  # counter-clockwise on screen, in KiCad's y-down frame
        return 100 + p[0] * c + p[1] * s, 100 - p[0] * s + p[1] * c

    def corners(left, top, right, bottom):
        return [at(p) for p in ((left, top), (right, top), (right, bottom), (left, bottom))]

    for kind, *g in path:
        if kind == "line":
            track(b, "LINE", w, at(g[0]), at(g[1]))
        else:
            (cx, cy), r, t0, t1 = g
            arc(b, "LINE", w, *(at((cx + r * math.cos(math.radians(t)), cy + r * math.sin(math.radians(t))))
                                for t in (t0, (t0 + t1) / 2, t1)))
    xs, ys = zip(*corners(x0, y0, x1, y1))
    box = min(xs), min(ys), max(xs), max(ys)
    rect(b, pcbnew.Edge_Cuts, *box)
    if mask_open:
        rect(b, pcbnew.F_Mask, *box, filled=True)
    # the zones stop where KiCad's 0.5 mm copper-to-edge clearance stops an axis-aligned fill, so a turned
    # coupon's copper is its twin's copper turned
    zone(b, pcbnew.B_Cu, corners(x0 + 0.5, y0 + 0.5, x1 - 0.5, y1 - 0.5))
    if pads:
        for ref, p in (("TP1", (0, 0)), ("TP2", (20, 0))):
            place(b, "TestPoint:TestPoint_Pad_1.0x1.0mm", ref, "TP", at(p), angle, {"1": "LINE"})
    if aux:
        track(b, "AUX", 0.3, at((0, 1.85)), at((20, 1.85)))
    if not ms:
        zone(b, pcbnew.F_Cu, corners(x0 + 0.5, y0 + 0.5, x1 - 0.5, 1.5 if aux else y1 - 0.5))
        fence(b, [at(p) for p in fence_points(path, w / 2 + 0.6)], box)


def lpf915(b, l1_angle=0):
    """The output chain along y = 100, left to right: U1 pin 1 -> C1 -> C2 (shunt) -> L1 -> C3 (shunt) -> R1
    -> J1 (U.FL), all inside the shield frame SH1. R2 (DNP) branches from RF_OUT through a gap in the frame
    to the edge SMA J2 on the board's right edge."""

    def at(x, y=0.0):
        return 100 + x, 100 + y

    u1 = place(b, "Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm", "U1", "RFIC", at(0, -0.75), 180,
               {"1": "RF_A", "2": "GND", "4": "GND", "17": "GND", "8": "VDD"})  # pin 1 lands on y = 100
    c4 = place(b, "Capacitor_SMD:C_0603_1608Metric", "C4", "10uF/16V", at(-0.75, -4.25), 90,
               {"1": "VDD", "2": "GND"})  # above pin 8
    c1 = place(b, "Capacitor_SMD:C_0402_1005Metric", "C1", "100pF", at(3.5), 0, {"1": "RF_A", "2": "RF_B"})
    place(b, "Capacitor_SMD:C_0402_1005Metric", "C2", "3.3pF", at(5, 0.48), 270, {"1": "RF_B", "2": "GND"})
    l1 = place(b, "Inductor_SMD:L_0402_1005Metric", "L1", "15nH", at(6.5), l1_angle, {"1": "RF_B", "2": "RF_C"})
    place(b, "Capacitor_SMD:C_0402_1005Metric", "C3", "3.3pF", at(8, 0.48), 270, {"1": "RF_C", "2": "GND"})
    r1 = place(b, "Resistor_SMD:R_0402_1005Metric", "R1", "0R", at(9.5), 0, {"1": "RF_C", "2": "RF_OUT"})
    r2 = place(b, "Resistor_SMD:R_0402_1005Metric", "R2", "0R", at(11, 0.51), 270,
               {"1": "RF_OUT", "2": "RF_SMA"})
    r2.SetDNP(True)
    j1 = place(b, "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", "J1", "U.FL", at(13.45), 0,
               {"1": "RF_OUT", "2": "GND"})
    j2 = place(b, "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount", "J2", "SMA", at(20.5, 6.25), 0,
               {"1": "RF_SMA", "2": "GND"})  # level with the gap in the frame's right side
    place(b, "RF_Shielding:Wuerth_36103205_20x20mm", "SH1", "SHIELD", at(6.575), 0,
          {"1": "GND"})  # centred on U1..J1, 1.3 mm clear of each

    track(b, "RF_A", 0.25, pad_at(u1, "1"), at(2.3))  # necked to the 0.25 mm pin, clear of pin 2
    track(b, "RF_A", 0.6, at(2.3), pad_at(c1, "1"))
    rf_b, rf_c = [pad_at(c1, "2"), pad_at(l1, "1")], [pad_at(l1, "2"), pad_at(r1, "1")]
    if l1_angle:  # 45-degree jogs between the line and L1's turned pads
        rf_b.insert(1, (rf_b[1][0] - (rf_b[1][1] - 100), 100))
        rf_c.insert(1, (rf_c[0][0] - (rf_c[0][1] - 100), 100))
    track(b, "RF_B", 0.6, *rf_b)
    track(b, "RF_C", 0.6, *rf_c)
    track(b, "RF_OUT", 0.6, pad_at(r1, "2"), pad_at(j1, "1"))
    track(b, "RF_SMA", 0.6, pad_at(r2, "2"), at(11, 6.25), pad_at(j2, "1"))
    track(b, "VDD", 0.25, pad_at(u1, "8"), pad_at(c4, "1"))
    track(b, "GND", 0.25, pad_at(u1, "2"), at(0.6, -0.5))  # pin 2 into the exposed pad
    for x in (-0.45, 0.45):
        for y in (-1.2, -0.3):
            via(b, at(x, y))  # exposed pad to the bottom ground

    box = 94.825, 88.25, 123.04, 112.25  # 1 mm around SH1 and J2; J2's pads end on the right edge
    rect(b, pcbnew.Edge_Cuts, *box)
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone(b, layer, [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])])
    rf = [("line", at(2.3), pad_at(j1, "1")), ("line", pad_at(r2, "2"), at(11, 6.25)),
          ("line", at(11, 6.25), pad_at(j2, "1"))]
    fence(b, fence_points(rf, 0.9), box)


def pads_zoo(b):
    """Library footprints at 0, 30, 90 and 180 degrees, a U.FL placed at 30 degrees and flipped to the
    bottom, and ZOO1, built here with one pad of each other kind, at 30 degrees. No nets."""
    place(b, "Capacitor_SMD:C_0603_1608Metric", "C1", "C", (100, 100), 0)
    place(b, "Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm", "U1", "QFN", (106, 100), 30)
    place(b, "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", "J1", "U.FL", (112, 100), 90)
    place(b, "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount", "J2", "SMA", (129, 100), 180)
    j3 = place(b, "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", "J3", "U.FL", (100, 108), 30)
    j3.Flip(j3.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)

    zoo = pcbnew.FOOTPRINT(b)
    zoo.SetFPID(pcbnew.LIB_ID("fixtures", "ZOO"))
    zoo.SetReference("ZOO1")
    zoo.SetValue("ZOO")
    b.Add(zoo)

    def pad(number, shape, at, size, angle=0, tht=False):  # built at the origin, so `at` is local
        p = pcbnew.PAD(zoo)
        p.SetNumber(number)
        p.SetShape(shape)
        p.SetPosition(pt(*at))
        p.SetSize(pt(*size))
        p.SetOrientationDegrees(angle)
        p.SetAttribute(pcbnew.PAD_ATTRIB_PTH if tht else pcbnew.PAD_ATTRIB_SMD)
        p.SetLayerSet(pcbnew.PAD.PTHMask() if tht else pcbnew.PAD.SMDMask())
        if tht:
            p.SetDrillSize(pt(0.8, 0.8))
        zoo.Add(p)
        return p

    pad("1", pcbnew.PAD_SHAPE_CIRCLE, (0, 0), (1, 1))
    pad("2", pcbnew.PAD_SHAPE_OVAL, (2.5, 0), (2, 1), angle=45)
    pad("3", pcbnew.PAD_SHAPE_TRAPEZOID, (5, 0), (1.5, 1)).SetDelta(pt(0.4, 0))
    p = pad("4", pcbnew.PAD_SHAPE_CHAMFERED_RECT, (7.5, 0), (1.5, 1))
    p.SetRoundRectRadiusRatio(0.2)
    p.SetChamferRectRatio(0.25)
    p.SetChamferPositions(1 | 8)  # RECT_CHAMFER_TOP_LEFT | RECT_CHAMFER_BOTTOM_RIGHT
    # pads 5, 7 and 8 are lopsided in local y, so a reader with a y sign wrong cannot match them
    p = pad("5", pcbnew.PAD_SHAPE_CUSTOM, (10, 0), (0.6, 0.6))
    p.SetAnchorPadShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_RECT)
    p.AddPrimitivePoly(pcbnew.F_Cu, [pt(0.2, -0.5), pt(1.4, -0.2), pt(0.2, 0.5)], MM(0.1), True)
    pad("6", pcbnew.PAD_SHAPE_CIRCLE, (0, 3), (1.6, 1.6), tht=True)
    pad("7", pcbnew.PAD_SHAPE_OVAL, (3, 3), (2, 1.6), angle=30, tht=True).SetOffset(pt(0.3, 0.2))
    pad("8", pcbnew.PAD_SHAPE_TRAPEZOID, (6, 3), (1.5, 1)).SetDelta(pt(0, 0.3))
    zoo.SetPosition(pt(104, 114))
    zoo.SetOrientationDegrees(30)

    box = b.ComputeBoundingBox(False)
    rect(b, pcbnew.Edge_Cuts, box.GetLeft() / 1e6 - 1, box.GetTop() / 1e6 - 1,
         box.GetRight() / 1e6 + 1, box.GetBottom() / 1e6 + 1)


# an antenna board's 50 Ω microstrip keeps its top ground 1 mm off: the fill's clearance, and the gap fit2d reads
ANTENNA_RULES = '(version 1)\n(rule "microstrip gap" (constraint clearance (min 1mm)))\n'


def radio(b, at, rf="RF"):
    """U1, a SOIC-8 "RFIC" turned 270 degrees at `at`: pin 1 (`rf`) on top, 8 VDD, the rest GND."""
    nets = {str(k): "GND" for k in range(2, 8)} | {"1": rf, "8": "VDD"}
    return place(b, "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "U1", "RFIC", at, 270, nets)


def to_gnd(b, pad):
    """A GND via 1.2 mm right of `pad` (x, y), and a 0.3 mm GND track to it."""
    via(b, (pad[0] + 1.2, pad[1]))
    track(b, "GND", 0.3, pad, (pad[0] + 1.2, pad[1]))


def antenna_board(b, lib, ae_nets, ae_at, outline, ground_top, radio_y, pi=False, decap=True, pitch=5.0, dx=0.0,
                  pour=None):
    """A printed antenna on a rectangular ground (Stage 3 design 5.11): AE1 from `lib` at `ae_at`, the board `outline`
    (x0, y0, x1, y1), GND zones on both layers from y = `ground_top` down, 0.5 mm inside the outline, 1 mm clear of
    other nets; U1 straight below AE1's feed pad, pin 1's top end at `radio_y`, fed by a 1.35 mm microstrip and a 0.6
    mm stub into pin 1, or with `pi` C3 (shunt), L1 (series) and C2 (shunt) on a 0.6 mm line; `decap` a 100 nF C1
    beside pin 8; GND stitching vias every `pitch` mm over the ground. `dx` then moves the front end (AE1, U1, the
    parts, their tracks and to_gnd vias) along x, leaving the ground, the outline and the stitching vias in place;
    `pour` adds a GND zone with those corners on both layers, 1 mm clear of other nets."""
    ae = place(b, lib, "AE1", lib.split(":")[1], ae_at, 0, ae_nets)
    fx, fy = pad_at(ae, "1")
    radio(b, (fx - 1.905, radio_y + 3.45), "RF_A" if pi else "RF")  # pin 1 at (fx, radio_y + 0.975)
    x0, y0, x1, y1 = outline
    rect(b, pcbnew.Edge_Cuts, *outline)
    if pi:
        c3 = place(b, "Capacitor_SMD:C_0402_1005Metric", "C3", "1pF", (fx + 0.48, fy + 4.0), 0, {"1": "RF", "2": "GND"})
        l1 = place(b, "Inductor_SMD:L_0402_1005Metric", "L1", "2.7nH", (fx, fy + 6.0), 90, {"1": "RF_A", "2": "RF"})
        c2 = place(b, "Capacitor_SMD:C_0402_1005Metric", "C2", "1pF", (fx + 0.48, fy + 8.0), 0,
                   {"1": "RF_A", "2": "GND"})
        track(b, "RF", 0.6, (fx, fy), pad_at(l1, "2"))
        track(b, "RF_A", 0.6, pad_at(l1, "1"), (fx, radio_y + 0.975))
        to_gnd(b, pad_at(c3, "2"))
        to_gnd(b, pad_at(c2, "2"))
    else:
        track(b, "RF", 1.35, (fx, fy), (fx, radio_y - 1.0))
        track(b, "RF", 0.6, (fx, radio_y - 1.0), (fx, radio_y + 0.975))
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone(b, layer, [(x0 + 0.5, ground_top), (x1 - 0.5, ground_top), (x1 - 0.5, y1 - 0.5), (x0 + 0.5, y1 - 0.5)],
             clearance=1.0)
        if pour:
            zone(b, layer, pour, clearance=1.0)
    if decap:
        c1 = place(b, "Capacitor_SMD:C_0402_1005Metric", "C1", "100nF", (fx + 2.0, radio_y + 5.925), 0,
                   {"1": "VDD", "2": "GND"})
        track(b, "VDD", 0.25, (fx, radio_y + 5.925), pad_at(c1, "1"))  # from pin 8
        to_gnd(b, pad_at(c1, "2"))
    front = [*b.GetFootprints(), *b.GetTracks()]  # AE1, U1, the parts, their tracks and to_gnd vias
    # the fence at the base's positions: after a +0.3 mm move it would drop the via at (104.5, 116.25) by C1 (r3)
    fence(b, [(x0 + 2.5 + i * pitch, ground_top + 1.5 + j * pitch) for i in range(int((x1 - x0 - 4) / pitch) + 1)
              for j in range(int((y1 - ground_top - 3) / pitch) + 1)], outline, keep=1.5)
    for item in front:
        item.Move(pcbnew.VECTOR2I(MM(dx), 0))


def moved(ae_at, outline, ground_top, radio_y, dx, dy):
    """`antenna_board`'s placement offset by (dx, dy) mm: AE1, the outline, the ground's top and the radio, and with
    them the fence grid derived from them."""
    x0, y0, x1, y1 = outline
    return (ae_at[0] + dx, ae_at[1] + dy), (x0 + dx, y0 + dy, x1 + dx, y1 + dy), ground_top + dy, radio_y + dy


IFA = ("RF_Antenna:Texas_SWRA117D_2.4GHz_Left", {"1": "RF", "2": "GND"}, (100, 100), (87, 94, 127, 124), 99.75, 111.0)
# one fine cell at the antenna's copper at mesh n 2 (the 0.6 mm stub over n, r3); 0.2 at n 3, which Task 11 regenerates
# when P3-C sets n 3
D_MOVE = 0.3
# P3-E's ground pour, GND on both layers 1.0 mm from AE1's open end and meander bottoms, overlapping the main zone by
# 0.5 mm so the fills join (r3 Q4)
POUR = [(89.65, 98.99), (98.3, 98.99), (98.3, 100.25), (89.65, 100.25)]


BOARDS = {
    "coupon_ms": lambda b: coupon(b, ms=True),
    "coupon_ms_masked": lambda b: coupon(b, ms=True, mask_open=False),
    "coupon_gcpw": coupon,
    "coupon_gcpw_masked": lambda b: coupon(b, mask_open=False),
    "coupon_gcpw_pads": lambda b: coupon(b, pads=True),
    "coupon_dense": lambda b: coupon(b, aux=True),
    "coupon_gcpw_45": lambda b: coupon(b, angle=45),
    "coupon_gcpw_arc": lambda b: coupon(b, bend=True),
    "lpf915": lpf915,
    "lpf915-45": lambda b: lpf915(b, l1_angle=45),
    "pads_zoo": pads_zoo,
    "ifa2g4": lambda b: antenna_board(b, *IFA),
    "ifa2g4_pi": lambda b: antenna_board(b, *IFA, pi=True),
    "ifa2g4_pi_shift": lambda b: antenna_board(b, *IFA[:2], *moved(*IFA[2:], D_MOVE, D_MOVE), pi=True),
    "ifa2g4_pi_dxp": lambda b: antenna_board(b, *IFA, pi=True, dx=D_MOVE),
    "ifa2g4_pi_dxm": lambda b: antenna_board(b, *IFA, pi=True, dx=-D_MOVE),
    "ifa2g4_pi_pour": lambda b: antenna_board(b, *IFA, pi=True, pour=POUR),
    "meander915": lambda b: antenna_board(b, "RF_Antenna:Texas_SWRA416_868MHz_915MHz", {"1": "RF"}, (110, 100),
                                          (89, 92.5, 129, 146.5), 106.5, 111.0, decap=False),
}


def new_board(path, seed, rules=RULES):
    """An empty 0.8 mm, 2-layer board with KiCad's default stackup, saved at `path` and loaded back under the
    design `rules` (a .kicad_dru's text)."""
    pcbnew.KIID.SeedGenerator(seed)
    b = pcbnew.CreateEmptyBoard()
    b.GetDesignSettings().SetBoardThickness(MM(0.8))
    pcbnew.SaveBoard(str(path), b, True)
    text = path.read_text(encoding="utf-8")
    assert "\t(setup\n" in text, "KiCad's board format changed: splice the stackup elsewhere"
    path.write_text(text.replace("\t(setup\n", "\t(setup\n" + STACKUP, 1), encoding="utf-8", newline="\n")
    dru = path.with_suffix(".kicad_dru")
    dru.write_text(rules, encoding="utf-8")
    try:
        return pcbnew.LoadBoard(str(path))
    finally:
        dru.unlink()


def mm_up(p):
    """KiCad nm with y down -> mm with y up."""
    return [round(p.x / 1e6, 6) + 0.0, round(-p.y / 1e6, 6) + 0.0]


def save(b, path):
    """Fill the zones, save the board and write pcbnew's pad truth next to it."""
    b.BuildConnectivity()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    # 0.1 um chords (KiCad's default is 5 um), so that the truth lies on the true pad outline; the
    # fills above keep the default. The setting lives in the project file, not in the board.
    b.GetDesignSettings().m_MaxError = 100
    truth = {}
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            pad.SetDirty()
            layers = pad.GetLayerSet()
            layer = (list(layers.CuStack()) or list(layers.Seq()))[0]
            poly = pad.GetEffectivePolygon(layer, pcbnew.ERROR_INSIDE)
            truth[pad.m_Uuid.AsString()] = {
                "name": f"{fp.GetReference()}.{pad.GetNumber()}",
                "center": mm_up(pad.ShapePos(layer)),
                "polygons": [[mm_up(q) for q in poly.COutline(i).CPoints()] for i in range(poly.OutlineCount())]}
    pcbnew.SaveBoard(str(path), b, True)
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))  # KiCad writes CRLF on Windows
    lines = ",\n".join(f"{json.dumps(k)}: {json.dumps(v)}" for k, v in truth.items())  # a pad per line
    text = "{\n" + lines + "\n}\n" if lines else "{}\n"
    path.with_suffix(".pads.json").write_text(text, encoding="utf-8", newline="\n")


def main(out, names=()):
    """Build the boards `names` (every one in BOARDS when empty) into the folder `out`. An unknown name exits first,
    before any board is written."""
    if unknown := [n for n in names if n not in BOARDS]:
        sys.exit(f"unknown boards: {' '.join(unknown)}; known: {' '.join(BOARDS)}")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in names or BOARDS:
        path = out / f"{name}.kicad_pcb"
        rules = ANTENNA_RULES if name.startswith(("ifa2g4", "meander915")) else RULES
        b = new_board(path, zlib.crc32(name.encode()), rules)
        BOARDS[name](b)
        save(b, path)
        print(name)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
