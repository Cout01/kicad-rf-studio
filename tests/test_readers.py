# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

import numpy as np
import pytest

from kicad_rf_studio.core.model.readers import (c_box, curve_edge, pec_roots, read_log, read_probe, read_run_stats,
                                                read_stats, read_unused, read_vtk)

SETUP_LOG = ("openEMS - verbose level 2\n"
             "Operator::CalcTimestep_Var3: Smallest timestep (1.73972e-13s) found at position: 2 : 0;0;6\n"
             "FDTD simulation size: 65x33x16 --> 34320 FDTD cells \r\n"
             "FDTD timestep is: 1.73972e-13 s; Nyquist rate: 951 timesteps @3.02211e+09 Hz\n"
             "Max. number of timesteps: 28740 ( --> 1 * Excitation signal length)\n")
STATS = ("34320\t% number of cells\n1.739719832710559e-13\t% timestep (s)\n28740\t% number of iterations\n"
         "4.999954799210147e-09\t% total numerical time (s)\n16.034181\t% simulation time (s)\n"
         "61515882.8505179\t% speed (cells/s)\n")
PROBE = ("% time-domain voltage integration by openEMS v0.37.0 @Wed Oct 21 08:38:31 2026\r\n"
         "% start-coordinates: (-0.005,0,0) m -> [12,16,2]\r\n% stop-coordinates: (-0.005,0,0.0005) m -> [12,16,6]\r\n"
         "% t/s\tvoltage\r\n0\t-0\r\n4.12313600352e-11\t2.93135258289e-07\r\n8.24627200704e-11\t-nan(ind)\r\n1.2369")
DUMPS = Path(__file__).parent / "fixtures" / "dumps"
LINES = (np.arange(-8, 8.001, 0.25), np.arange(-4, 4.001, 0.25),
         np.array([-1, -0.5, 0, .125, .25, .375, .5, .535, .6, .75, 1, 1.5, 2, 2.5, 3, 3.5]))


def test_the_setup_log():  # r5's real lines; the banner (it holds an e-mail address) is left out
    assert read_log(SETUP_LOG) == {"cells": [65, 33, 16], "dt": 1.73972e-13, "node": [2, 0, 0, 6], "nrts": 28740,
                                   "iterations": None}
    assert read_log("Time for 28740 iterations with 34320.00 cells : 16.03 sec\n")["iterations"] == 28740
    assert read_log("Time for 0 iterations with 34320 cells : 0.00011 sec\n")["iterations"] == 0  # a stale ABORT


def test_statistics_and_probes():
    assert read_stats(STATS) == {"cells": 34320, "dt": 1.739719832710559e-13, "iterations": 28740,
                                 "sim_time": 4.999954799210147e-09, "wall": 16.034181, "speed": 61515882.8505179}
    assert read_stats("") is None and read_stats(STATS[:-1]) is None  # C1: a job killed while openEMS wrote it
    steps, speed, e = read_run_stats("%time\ttimestep\tspeed\tenergy\n4.12275\t8058\t6.70792e+07\t2.93607e-15\n"
                                     "8.21882\t15168\t5.95729e+07\t-nan(ind)\n12.304\t222")
    assert steps.tolist() == [8058, 15168] and speed[0] == 6.70792e+07 and e[0] == 2.93607e-15 and np.isnan(e[1])
    t, v = read_probe(PROBE)
    assert t.tolist() == [0.0, 4.12313600352e-11, 8.24627200704e-11] and v[1] == 2.93135258289e-07 and np.isnan(v[2])


def test_unused_primitives_from_stderr():  # C-16
    err = ("Warning: Unused primitive (type: Box) detected in property: port_resist_1!\n"
           "Warning: No primitives found in property: metal!\n"
           "Processing::DefineStartStopCoord: Warning in port_ut_2 (-1,0,0) : Box is outside the field domain!! Disabling\n")
    assert read_unused(err) == [["Box", "port_resist_1"], ["none", "metal"], ["outside", "port_ut_2"]]


def test_the_dumps_decode():  # r5: UInt32 headers, zlib, base64
    pec, op = read_vtk(DUMPS / "PEC_dump.vtp"), read_vtk(DUMPS / "operator_dump.vtr")
    assert len(pec["Points"]) == 3 * 2551 and len(pec["Lines/connectivity"]) == 2 * 4933
    assert [len(op[c]) for c in "xyz"] == [65, 33, 16]
    assert np.linalg.norm(op["vv"].reshape(-1, 3), axis=1).max() == pytest.approx(1.7320508075688772, rel=1e-6)


def test_pec_pieces_tell_the_strip_from_the_ground():  # C-15
    r = pec_roots(DUMPS / "PEC_dump.vtp", LINES, [[-5, 0, 0], [-5, 0, 0.5], [0, 2, 0], [0, 0, 0.535], [0, 3, 2]])
    assert r[0] == r[2] != r[1] == r[3] and min(r[:4]) >= 0 and r[4] == -1


def test_a_cut_join_separates_the_copper_it_held():  # Stage 3 design 5.3: the port-short check; RF 2
    nodes = [[-5, 0, 0.5], [3, 0, 0.535], [-5, 0, 0]]  # the strip at both ends, the ground
    whole = pec_roots(DUMPS / "PEC_dump.vtp", LINES, nodes)
    cut = pec_roots(DUMPS / "PEC_dump.vtp", LINES, nodes, [[[-0.3, -1.0, 0.4], [0.3, 1.0, 0.6]]])
    assert whole[0] == whole[1] != whole[2] and cut[0] != cut[1] and cut[2] == whole[2]
    faces = [[[-0.3, -1.0, 0.4], [0.3, 1.0, 0.5]], [[-0.3, -1.0, 0.535], [0.3, 1.0, 0.6]]]  # each ends on a face's line
    assert pec_roots(DUMPS / "PEC_dump.vtp", LINES, nodes, faces) == cut  # bounds included; float32 metres miss both


def test_c_box_of_port_1():  # C-18: 4 layers of 5 z-edges in series
    c = c_box(DUMPS / "operator_dump.vtr", LINES, [-5, -0.5, 0], [-5, 0.5, 0.5], 2, 1.73972e-13)
    assert c == pytest.approx(2.3796e-14, rel=1e-3)


def test_curve_edge_follows_openems():  # ports.py CurvePort, v0.37.0
    lines = ([0.0, 1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 2.0], [0.0, 1.0])
    assert curve_edge(lines, [0.2, 1.0, 1.0], [3.9, 1.0, 1.0]) == (0, (2, 1, 1))  # the edge at the midpoint
    assert curve_edge(lines, [1.1, 1.0, 1.0], [1.9, 1.0, 1.0]) == (0, (1, 1, 1))  # one cell apart: its own edge
