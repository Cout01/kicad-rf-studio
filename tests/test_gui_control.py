# SPDX-License-Identifier: GPL-3.0-or-later
"""The GUI's Qt-free logic (Stage 2 design 5.1, 5.3, 5.8): the detached start, the events tail, re-attach through the
lock and the end events, the project read off the GUI thread, and the retune session. Detached runs go through
tests/fake_cli.py."""
import json
import re
import string
import subprocess
import sys
import time
import tomllib
from dataclasses import replace
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import skrf as rf

from kicad_rf_studio import __version__, button, pipeline, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core import messages
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.messages import CATALOG, KrsError, render
from kicad_rf_studio.core.model.spec import spec_hash
from kicad_rf_studio.core.post.antenna import ANTENNA_LIMITS, DELTA_COLUMNS
from kicad_rf_studio.core.post.outputs import LIMITS
from kicad_rf_studio.core.post.si import si_limits
from kicad_rf_studio.core.post.waves import grid
from kicad_rf_studio.core.project import board_file, load_project, parts, save_project
from kicad_rf_studio.gui import control
from networks import star, terminate_np
from test_antenna_kicad import KINDS
from test_cli_antenna import antenna_project
from test_cli_cost import FIX, new_project
from test_cli_si import si_project
from test_compare import twin
from test_match_antenna import pi_run
from test_post_chain import M0402, lpf
from test_run import lpf_loads, lpf_run
from test_sexpr import mo_pairs
from test_si_run import verified_si

F, _ = grid(915e6, 3, 1.1)
FAKE_CLI = Path(__file__).with_name("fake_cli.py")
FAKE_PREFIX = [sys.executable, "-X", "utf8", "-I", str(FAKE_CLI)]


def until(check, timeout=60.0):
    """Polls `check` every 0.1 s until it holds; fails after `timeout` s."""
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.1)


def ends(run_dir):
    return (control.last_event(run_dir) or {}).get("kind") == "end"


@pytest.mark.parametrize(("exe", "python"), [
    (("venv", "Scripts", "pythonw.exe"), ("venv", "Scripts", "python.exe")),  # a gui-scripts entry on Windows
    (("venv", "bin", "python3"), ("venv", "bin", "python3"))])
def test_the_orchestrator_is_the_console_python_beside_the_guis(monkeypatch, exe, python):  # design 5.1
    monkeypatch.setattr(sys, "executable", str(Path(*exe)))
    assert control.orchestrator() == [str(Path(*python)), "-X", "utf8", "-I", "-m", "kicad_rf_studio"]


def recorder(monkeypatch, refuse_first=False):
    calls = []

    def popen(args, **kw):
        calls.append(SimpleNamespace(args=args, **kw))
        if refuse_first and len(calls) == 1:
            raise PermissionError(13, "the job forbids breakaway")
        return calls[-1]

    monkeypatch.setattr(subprocess, "Popen", popen)
    return calls


@pytest.mark.skipif(sys.platform != "win32", reason="Windows' creation flags")
def test_start_is_detached_windowless_and_breaks_away_when_it_may(tmp_path, monkeypatch):  # design 5.1
    calls = recorder(monkeypatch, refuse_first=True)
    monkeypatch.setenv("KICAD_API_TOKEN", "t")
    monkeypatch.setenv("KICAD_API_SOCKET", "s")
    d = tmp_path / "run"
    control.start(["py"], "cost", tmp_path / "project.json", d)
    base = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    assert [c.creationflags for c in calls] == [base | subprocess.CREATE_BREAKAWAY_FROM_JOB, base]
    assert calls[1].args == ["py", "cost", str(tmp_path / "project.json"), "--run-dir", str(d)]
    assert (calls[1].stdin, calls[1].stderr, calls[1].cwd) == (subprocess.DEVNULL, subprocess.STDOUT, d)
    assert (d / "cli.log").is_file() and not {"KICAD_API_TOKEN", "KICAD_API_SOCKET"} & set(calls[1].env)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX sessions")
def test_start_runs_in_a_session_of_its_own(tmp_path, monkeypatch):  # design 5.1
    calls = recorder(monkeypatch)
    control.start(["py"], "run", tmp_path / "project.json", tmp_path / "run")
    assert calls[0].start_new_session is True and not hasattr(calls[0], "creationflags")
    assert calls[0].cwd == tmp_path / "run"


def test_the_tail_holds_back_a_partial_last_line(tmp_path):  # Review Focus 3
    path = tmp_path / "events.jsonl"
    tail = control.Tail(path)
    assert tail.read() == []  # no file yet
    one, two = (json.dumps({"kind": "message", "job": None, "code": c, "params": {}}).encode() for c in "AB")
    path.write_bytes(one + b"\r\n" + two[:9])  # emit writes text mode: \r\n on Windows
    assert tail.read() == [json.loads(one)] and tail.offset == len(one) + 2
    with open(path, "ab") as f:
        f.write(two[9:] + b"\n{not json\n" + one + b"\n")
    assert tail.read(limit=len(two) + 1) == [json.loads(two)]  # at most `limit` bytes a read
    assert tail.read() == [json.loads(one)]  # the line that does not parse is skipped


def test_a_replay_keeps_only_the_last_progress_of_each_job():  # r2 §1: no frozen window on an 8 h run's replay
    events = [{"kind": "progress", "job": 1 + k % 2, "n": k} for k in range(1000)]
    events += [{"kind": "verdict", "job": 1, "n": "v"}, {"kind": "progress", "job": 2, "n": "late"}]
    assert [e["n"] for e in control.latest(events)] == [998, "v", "late"]


def test_the_projects_ended_runs_and_its_last_matching_cost(fake, tmp_path):  # design 5.1, 5.2 item 3, 5.3
    pj, other = tmp_path / "lpf915" / "project.json", tmp_path / "lpf915-45" / "project.json"
    for name, project, command, code, t, spec in [
            ("lpf915-1", pj, "cost", 0, 1.0, {"m": 1}), ("lpf915-2", pj, "run", 4, 2.0, None),
            ("lpf915-3", pj, "cost", 0, 3.0, {"m": 2}), ("lpf915-4", pj, "cost", 3, 4.0, {"m": 1}),
            ("lpf915-45-5", other, "cost", 0, 5.0, {"m": 1}), ("lpf915-6", pj, None, None, 6.0, None)]:
        d = fake / "runs" / name
        d.mkdir(parents=True)
        if spec is not None:
            runs.write_spec(d, spec)
        event = {"t": t, "kind": "end", "job": None, "code": "I_END",
                 "params": {"exit_code": code, "command": command, "project": str(project)}}
        (d / "events.jsonl").write_text(json.dumps(event if command else {"t": t, "kind": "progress"}) + "\n",
                                        encoding="utf-8")
    assert [(d.name, e["params"]["command"]) for d, e in control.ended(pj)] == [
        ("lpf915-4", "cost"), ("lpf915-3", "cost"), ("lpf915-2", "run"), ("lpf915-1", "cost")]
    assert control.last_cost(pj, spec_hash({"m": 1})) == fake / "runs" / "lpf915-1"  # lpf915-4's gate blocked
    assert control.last_cost(pj, spec_hash({"m": 2})) == fake / "runs" / "lpf915-3"
    assert control.last_cost(pj, spec_hash({"m": 3})) is None and control.last_cost(pj, None) is None


@pytest.mark.parametrize(("end", "holder", "own", "returncode", "code"), [
    ({"params": {"exit_code": 0}}, None, True, 0, "G_END_DONE"),
    ({"params": {"exit_code": 2}}, None, False, None, "G_END_REFUSED"),  # Review Focus 2
    ({"params": {"exit_code": 3}}, None, False, None, "G_END_BLOCKED"),
    ({"params": {"exit_code": 4}}, None, False, None, "G_END_NOT_KEPT"),
    ({"params": {"exit_code": 130}}, None, False, None, "G_END_STOPPED"),
    ({"params": {"exit_code": 1}}, None, False, None, "G_END_FAILED"),
    (None, None, True, None, "G_RUNNING"),  # this window's process, going on
    (None, None, True, 3, "G_END_EXITED"),  # Review Focus 4: it exited with no end event, killed or failed at start
    (None, {"run_dir": "R", "alive": True}, False, None, "G_RUNNING"),  # another's run, its lock live
    (None, {"run_dir": "R", "alive": False}, False, None, "G_END_LOST"),  # Review Focus 4: a stale lock
    (None, {"run_dir": "other", "alive": True}, False, None, "G_ENDED"),
    (None, None, False, None, "G_ENDED")])  # its lock gone with no end event yet, or a run of an older version
def test_the_run_state(end, holder, own, returncode, code):  # design 5.1, 5.3
    state, params = control.run_state(Path("R"), end, holder, own, returncode)
    assert (state, params["exit_code"]) == (code, end["params"]["exit_code"] if end else returncode)


def test_the_gui_words_the_cli_advice_its_own_way():  # design 5.3, 5.7
    assert control.text("I_WHAT_IF", {"command": "x"}) == render("G_WHAT_IF")
    assert render("G_WHAT_IF") == render("I_WHAT_IF", command="X").replace("`X`", "Verify")  # §7.6's text
    held = {"lock": "L", "run": "R", "started": "S"}
    assert control.text("E_LOCKED", held) == render("G_LOCKED", **held)
    assert control.text("I_GATES_PASSED", {"dt": "1"}) == render("I_GATES_PASSED", dt="1")


def test_the_pad_picker_lists_each_pad_with_copper_once_in_natural_order():  # design 5.3 Project
    assert control.pads(FIX / "coupon_gcpw_pads.kicad_pcb") == ["TP1.1", "TP2.1"]
    names = control.pads(FIX / "lpf915.kicad_pcb")
    assert len(names) == 36 and names[:4] == ["C1.1", "C1.2", "C2.1", "C2.2"] and names[-9:-7] == ["U1.9", "U1.10"]
    assert control.pads(FIX / "coupon_ms.kicad_pcb") == []  # a pad-less coupon
    with pytest.raises(KrsError) as e:
        control.pads(FIX / "nope.kicad_pcb")
    assert (e.value.code, e.value.params["reason"]) == ("E_BOARD_UNREADABLE", "T_FILE_NOT_FOUND")


def test_new_reads_a_boards_pads_and_antennas_once_but_its_connectors(mini_board_file):  # design 5.10; r2
    pads, kinds = control.board_choices(FIX / "ifa2g4_pi.kicad_pcb")
    assert pads == control.pads(FIX / "ifa2g4_pi.kicad_pcb") and kinds == {"AE1": "printed"}
    assert control.board_choices(FIX / "lpf915.kicad_pcb")[1] == {}  # J1, a U.FL with a keep-out, is a connector
    assert control.board_choices(mini_board_file(KINDS))[1] == {
        "AE1": "printed", "AE2": "chip", "AE3": "chip", "AE4": "chip", "AE5": "chip", "U2": "module", "U3": "module",
        "U4": "printed"}
    assert [(label, f_lo, f_hi) for label, f_lo, f_hi in control.BANDS] == [
        ("868 MHz (863–870 MHz)", 863e6, 870e6), ("915 MHz (902–928 MHz)", 902e6, 928e6),
        ("2.4 GHz (2400–2483.5 MHz)", 2.4e9, 2.4835e9)]  # design 5.10, 7's presets


def press(board, pads=(), footprints=(), socket="ipc://s", token="T", tracks=()):
    """A button press's handoff file (button.write_handoff) for `board`: the pads named REF.PAD by their KIIDs in
    the file (a name the file lacks passes as it is, as a KIID), the footprints by reference and the tracks, arcs and
    vias by their KIIDs (track_of)."""
    kiid = {p.name: p.uuid for p in load_board(board).all_pads()}
    return button.write_handoff({"board": str(board), "pads": [kiid.get(n, n) for n in pads],
                                 "footprints": list(footprints), "tracks": list(tracks), "kicad": "9.0.7",
                                 "socket": socket, "token": token})


def track_of(board, net, via=False):
    """The KIID of the first track, or via, of `net` in the saved `board`."""
    b = load_board(board)
    return next(t.uuid for t in (b.vias if via else b.tracks) if t.net == net)


def test_a_handoff_joins_the_selection_to_the_saved_boards_pads(fake, tmp_path):  # design 5.5; Review Focus 2
    board = FIX / "lpf915.kicad_pcb"
    every = control.pads(board)

    def read(pads=(), footprints=()):
        return control.handed(press(board, pads, footprints))

    assert read(["J1.1", "U1.1"]) == control.Handed(board, "ipc://s", "T", every, "U1.1", "J1.1", None)  # J1: end
    assert (read(["C2.1", "C3.1"]).start, read(["C2.1", "C3.1"]).end) == ("C2.1", "C3.1")  # no connector: as sent
    both = read(["J2.1", "J1.1"])  # both connectors' pads: as sent, never swapped
    assert (both.start, both.end, both.problem) == ("J2.1", "J1.1", None)
    one, none = read(["C3.1"]), read()
    assert (one.start, one.end, none.start, none.end, none.pads, none.problem) == ("C3.1", "", "", "", every, None)
    narrowed = read(["U1.1"], ["C1", "J1"])  # a footprint narrows the pickers to its pads and the selected ones
    assert (narrowed.pads, narrowed.start, narrowed.problem) == (["C1.1", "C1.2", "J1.1", "J1.2", "U1.1"], "U1.1", None)
    assert narrowed.kind == "chain"
    three = read(["C1.1", "C2.1", "C3.1"])
    assert (three.start, three.end, three.problem) == ("", "", ("G_HANDOFF_PADS", {"count": 3}))
    for unsaved in (read(["U1.1", "00000000-0000-0000-0000-000000000001"]), read(footprints=["C9"])):
        assert (unsaved.pads, unsaved.start, unsaved.problem) == (every, "", ("G_HANDOFF_UNSAVED",
                                                                              {"board": str(board)}))
    paste = next(p.uuid for p in load_board(board).all_pads() if not p.layers)  # one of U1's paste-only pads
    assert (read([paste, "C3.1"]).start, read([paste, "C3.1"]).problem) == ("C3.1", None)  # never an end
    nope = tmp_path / "nope.kicad_pcb"
    gone = control.handed(button.write_handoff({"board": str(nope), "pads": [], "footprints": [], "kicad": "9.0.7",
                                                "socket": "ipc://s", "token": "T"}))
    assert (gone.board, gone.pads, gone.problem) == (nope, [], ("E_BOARD_UNREADABLE", {
        "path": str(nope), "reason": "T_FILE_NOT_FOUND"}))


def test_a_press_on_an_antenna_gives_its_kind_and_never_its_own_pad_as_the_start(fake):  # design 5.10; r2
    board = FIX / "ifa2g4_pi.kicad_pcb"

    def read(pads=(), footprints=()):
        return control.handed(press(board, pads, footprints))

    every = [name for name in control.pads(board) if not name.startswith("AE1.")]
    assert read(["U1.1"], ["AE1"]) == control.Handed(board, "ipc://s", "T", every, "U1.1", "", None, "antenna", "AE1",
                                                     {"AE1": "printed"})
    for pads in (["AE1.1"], ["AE1.2"], ["AE1.1", "AE1.2"]):  # its own pads select it (new refuses them as start)
        h = read(pads)
        assert (h.kind, h.antenna, h.start, h.problem) == ("antenna", "AE1", "", None)
    assert (read(["AE1.2", "U1.1"]).antenna, read(["AE1.2", "U1.1"]).start) == ("AE1", "U1.1")
    two = read(["U1.1", "C1.1"], ["AE1"])
    assert (two.antenna, two.start, two.problem) == ("AE1", "", ("G_HANDOFF_START", {"count": 2}))


def test_a_press_on_two_antennas_or_on_a_module_or_a_chip_antenna_says_so(fake, mini_board_file):  # design 5.10
    board = mini_board_file(KINDS)

    def read(footprints):
        return control.handed(press(board, (), footprints))

    both = read(["AE1", "U4"])
    assert (both.kind, both.antenna, both.problem) == ("antenna", "", ("G_HANDOFF_ANTENNAS",
                                                                       {"count": 2, "refs": "AE1, U4"}))
    for ref, code in (("U2", "E_ANTENNA_MODULE"), ("U3", "E_ANTENNA_MODULE"), ("AE2", "E_ANTENNA_CHIP"),
                      ("AE4", "E_ANTENNA_CHIP")):
        h = read([ref])
        assert (h.kind, h.antenna, h.problem) == ("chain", "", (code, {"ref": ref}))  # v1's chain still applies
    assert read(["R1"]).problem is None and read(["AE1", "U2"]).kind == "antenna"  # a printed one wins


def test_a_press_on_a_track_arc_or_via_pre_fills_its_line(fake):  # design 5.10 as A-66 amends it; RF 3
    usb, qspi, arc = (FIX / f"{name}.kicad_pcb" for name in ("usb2_hs", "qspi_clk", "coupon_gcpw_arc"))

    def read(board, tracks, pads=(), footprints=()):
        return control.handed(press(board, pads, footprints, tracks=tracks))

    q = read(qspi, [track_of(qspi, "FLASH_CLK")])
    assert (q.kind, q.net, q.partner, q.start, q.end, q.problem) == ("si", "FLASH_CLK", "", "U1.11", "U2.6", None)
    assert q.pads == control.pads(qspi)
    v = read(qspi, [track_of(qspi, "FLASH_CLK", via=True)])  # a via alone: the same line through R1
    assert (v.start, v.end) == ("U1.11", "U2.6")
    four = ("G_HANDOFF_SI_ENDS", {"net": "USB_D+", "count": 4, "pads": "J1.3, U1.3, U2.3, U2.4"})
    p = read(usb, [track_of(usb, "USB_D+")])
    assert (p.kind, p.net, p.partner, p.start, p.end, p.problem) == ("si", "USB_D+", "USB_D-", "", "", four)
    n = read(usb, [track_of(usb, "MCU_D-")])  # the N side: the P net and its partner
    assert (n.net, n.partner, n.problem) == ("MCU_D+", "MCU_D-", (four[0], {**four[1], "net": "MCU_D+"}))
    assert read(usb, [track_of(usb, x) for x in ("USB_D+", "USB_D-", "MCU_D+")]).problem == four  # one line
    box = read(usb, [track_of(usb, "USB_D+")], (), ["R1", "R2"])  # a box selection's parts narrow no picker
    assert (box.pads, box.problem) == (control.pads(usb), four)
    ends = read(usb, [track_of(usb, "USB_D+")], ["U1.3", "J1.3"])  # its ends selected: the connector's first
    assert (ends.start, ends.end, ends.problem) == ("J1.3", "U1.3", None)
    legs = read(usb, [track_of(usb, "USB_D-")], ["J1.2", "U1.2"])  # the N leg's own ends, taken to the P side
    assert (legs.net, legs.start, legs.end, legs.problem) == ("USB_D+", "J1.3", "U1.3", None)
    nets = read(usb, [track_of(usb, "AUX"), track_of(usb, "USB_D+")])
    assert (nets.kind, nets.start, nets.problem) == ("si", "", ("G_HANDOFF_NETS", {"count": 2, "nets": "AUX, USB_D+"}))
    assert read(usb, [track_of(usb, "AUX")]).problem == ("G_HANDOFF_SI_ENDS", {"net": "AUX", "count": 0,
                                                                                "pads": "T_NONE"})
    gnd = read(usb, [track_of(usb, "GND", via=True)])
    assert (gnd.kind, gnd.problem) == ("si", ("G_HANDOFF_SI_NET", {"net": "GND"}))
    curve = read(arc, [next(t.uuid for t in load_board(arc).tracks if t.mid is not None)])
    assert (curve.net, curve.problem) == ("LINE", ("G_HANDOFF_SI_ENDS", {"net": "LINE", "count": 0, "pads": "T_NONE"}))
    assert read(usb, ["00000000-0000-0000-0000-000000000001"]).problem == ("G_HANDOFF_UNSAVED", {"board": str(usb)})
    ifa = FIX / "ifa2g4_pi.kicad_pcb"
    assert read(ifa, [track_of(ifa, "RF_A")], (), ["AE1"]).kind == "antenna"  # the antenna's rules first
    assert (read(usb, [], ["J1.3", "U1.3"]).kind, read(usb, [], ["J1.3", "U1.3"]).end) == ("chain", "J1.3")  # v1's


def test_every_gui_wording_keeps_its_cli_params_and_drops_terminal_syntax():  # design 5.3, 5.7
    def fields(code):
        return {name for _, name, _, _ in string.Formatter().parse(CATALOG[code]) if name}

    pt = mo_pairs()
    for cli_code, gui_code in control.GUI.items():  # later tasks' entries too
        assert fields(gui_code) <= fields(cli_code), gui_code  # rendered with the CLI line's own params
        for text in (CATALOG[gui_code], pt[CATALOG[gui_code]]):  # English, then pt-BR (pt-BR design 7.2)
            assert not re.search(r"`|--[a-z]|(?<!\w)-o |PROJECT", text), gui_code  # "Abra-o" is no -o
    assert control.text("E_PROJECT_EXISTS", {"path": "P"}) == render("G_PROJECT_EXISTS", path="P")
    assert control.message(KrsError("E_NO_STACKUP")) == render("G_NO_STACKUP")
    assert control.message(ZeroDivisionError("division by zero")) == render(
        "E_INTERNAL", detail="ZeroDivisionError: division by zero")


def test_the_gui_names_a_fixture_by_its_combo_label_not_the_cli_syntax(monkeypatch):  # pt-BR design 5.1
    class Translation:
        def gettext(self, msgid):
            return {"series": "SERIES-LABEL", "shunt": "SHUNT-LABEL"}.get(msgid, msgid)

    monkeypatch.setattr(messages, "_translation", Translation())
    line = control.text("W_S2P_FIXTURE", {"ref": "C3", "path": "p", "named": "series", "fits": "shunt"})
    assert line == render("G_S2P_FIXTURE", ref="C3", path="p", named="SERIES-LABEL", fits="SHUNT-LABEL")


def test_the_window_words_a_picked_partner_without_the_clis_option():  # ruling 6
    picked = control.text("I_SI_PAIR", {"p": "USB_D+", "n": "USB_D-", "how": "T_PAIR_WITH"})
    assert picked == render("I_SI_PAIR", p="USB_D+", n="USB_D-", how=render("G_PAIR_PICKED")) and "--" not in picked
    assert control.text("I_SI_PAIR", {"p": "A", "n": "B", "how": "T_PAIR_RULE"}) == render(
        "I_SI_PAIR", p="A", n="B", how="T_PAIR_RULE")


def test_open_project_reads_results_only_while_they_apply(tmp_path, calibrated, monkeypatch):  # Review Focus 1, 5
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    fresh = control.open_project(pj)
    assert (fresh.results, fresh.problem, fresh.cost, fresh.last) == (None, ("E_NO_RESULTS", {}), None, None)
    d = runs.run_dir_for(pj.parent.name)
    assert main(["cost", str(pj), "--run-dir", str(d)]) == 0 and main(["run", str(pj)]) == 0
    ran, r = control.open_project(pj), Path(load_project(pj)["results"]["run_dir"])
    assert ran.problem is None and ran.spec_hash == fresh.spec_hash == load_project(pj)["results"]["model_hash"]
    assert (ran.results.ext, ran.results.what_if, ran.cost, ran.last) == ([0, 1], False, d, r)  # A-13: it ended r
    save_project(pj, {**load_project(pj), "t_max_s": 30e-9})  # a hand edit: T_max is in the model's excitation
    stale = control.open_project(pj)
    assert (stale.results, stale.problem, stale.cost) == (None, ("E_RESULTS_STALE", {}), None)
    assert fresh.board == ran.board == stale.board == board_file(pj, load_project(pj))  # final review F9
    nope = control.open_project(tmp_path / "nope.json")
    assert nope.problem[0] == "E_PROJECT_UNREADABLE" and nope.board is None
    monkeypatch.setattr(pipeline, "load", lambda path: 1 / 0)
    assert control.open_project(pj).problem == ("E_INTERNAL", {"detail": "ZeroDivisionError: division by zero"})


def test_a_run_going_on_is_found_through_its_lock_and_stops_by_its_stop_file(tmp_path, calibrated,
                                                                              monkeypatch):  # 5.1, Review Focus 1
    monkeypatch.setenv("KRS_FAKE_DATA", str(calibrated))
    monkeypatch.setenv("KRS_FAKE", "slow")
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    d = runs.run_dir_for(pj.parent.name)
    proc = control.start(FAKE_PREFIX, "run", pj, d)
    try:
        until(lambda: (runs.lock_holder(pj) or {}).get("run_dir") == str(d))  # written, not only made
        tail, seen = control.Tail(d / "events.jsonl"), []
        until(lambda: seen.extend(tail.read()) or any(e["kind"] == "progress" for e in seen))
        (d / "STOP").write_text("")
        until(lambda: ends(d))
    finally:
        proc.kill()
        proc.wait()
    assert control.last_event(d)["params"] == {"exit_code": 4, "command": "run", "project": str(pj)}  # not kept
    assert [f for f, _ in control.ended(pj)] == [d] and (d / "cli.log").is_file() and runs.lock_holder(pj) is None


@pytest.mark.parametrize(("ref", "text", "series", "shown"), [
    ("C2", "5pF", "E24", "5.1pF"), ("C2", "5pF", "E12", "4.7pF"), ("C2", "5pF", "off", "5pF"),
    ("L1", "4.0nH", "E24", "3.9nH"), ("C2", "4p7", "E24", "4p7"), ("C2", "3,9pF", "off", "3,9pF"),
    ("C2", "abc", "E24", "abc"), ("C2", "0", "E24", "0"), ("R1", "0R", "E24", "0R"),
    ("C2", "9" * 400 + "pF", "E24", "9" * 400 + "pF"),  # reads as inf, which snap cannot take
    ("C1", "100pF/50V", "E24", "100pF/50V"),  # on the series: kept as typed, its rating too
    ("C2", "0.0000125pF", "E24", "0.0000125pF"), ("R1", "5000000000G", "E24", "5000000000G"),  # outside p to G
    ("C2", "0." + "0" * 311 + "5p", "E24", "0." + "0" * 311 + "5p"),  # subnormal: snap cannot take it
    ("R1", "25", "E24", "24"), ("R1", "25", "E12", "27"), ("R1", "open", "E24", "open")])
def test_snapping_writes_back_the_nearest_value_as_port_value_reads_it(ref, text, series, shown):  # design 5.3, 7
    assert control.snapped(ref, text, series) == shown
    assert [control.default_series(r) for r in ("C2", "L1", "R1", "FB1")] == ["E24", "E24", "off", "off"]
    assert [control.default_series(r, {"schema": 3}) for r in ("R1", "C1", "FB1")] == ["E24"] * 3
    assert control.SERIES == ("off", "E12", "E24")


def test_the_rows_and_the_assignments_of_the_changed_ones(tmp_path):  # design 5.3: free text, or an S2P file
    project, folder, refs = lpf(), tmp_path / "lpf915", ["C1", "L1", "C2", "C3"]  # lpf(): a copy, never the cache
    parts(project)["L1"]["s2p"] = {"file": "../parts/l1.s2p", "connection": "series"}
    rows = control.rows(project, folder, refs)
    l1 = str((tmp_path / "parts" / "l1.s2p").resolve())
    assert rows == [control.Row("C1", "100pF", "", "series"), control.Row("L1", "15nH", l1, "series"),
                    control.Row("C2", "3.3pF", "", "series"), control.Row("C3", "3.3pF", "", "series")]
    assert control.changed(project, folder, rows) == []
    edited = [rows[0], replace(rows[1], connection="shunt"), replace(rows[2], value="4p7"),
              replace(rows[3], s2p="c3.s2p")]  # a file named from the project's folder, never the working one
    assert control.changed(project, folder, edited) == [
        f"L1={l1}:shunt", "C2=4p7", f"C3={(folder / 'c3.s2p').resolve()}:series"]
    assert control.changed(project, folder, [replace(rows[1], s2p="")]) == ["L1=15nH"]  # a value clears the file


def test_the_retune_session_gives_retunes_own_numbers_in_milliseconds_and_writes_nothing(
        tmp_path, calibrated, monkeypatch):  # design 5.1, 5.3, 5.4; Review Focus 1, 2
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # tests/test_run.py: lpf915 on the star network fake
    opened = control.open_project(pj)
    rows = control.rows(opened.project, pj.parent, opened.results.refs)
    rows[2] = replace(rows[2], value="4.7pF")
    before = {p: p.stat().st_mtime_ns for p in (pj, *(pj.parent / "results").iterdir())}
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        res = control.retuned(pj, opened.project, opened.results, rows)
        timings.append(time.perf_counter() - start)
    assert min(timings) < 0.05  # the GUI thread's budget (design goal 4); about 5 ms measured on lpf915
    assert {p: p.stat().st_mtime_ns for p in before} == before  # nothing written: Apply writes
    assert res.what_if and res.lay is opened.results.lay
    oracle = terminate_np(star(F, 6), [0, 1], lpf_loads(M0402, C2=4.7e-12))
    assert np.abs(res.chain - oracle).max() <= 1e-5  # the network the fake ran (tests/networks.py)
    three = tmp_path / "x.s3p"
    rf.Network(frequency=rf.Frequency.from_f(F, unit="Hz"), s=star(F, 3), z0=50).write_touchstone(str(three))
    wrong = control.retuned(pj, opened.project, opened.results, [replace(rows[1], s2p=str(three))])
    assert wrong.chain is None and wrong.lines[-1] == ("E_S2P_PORTS", {"ref": "L1", "path": str(three.resolve()),
                                                                        "ports": 3})
    bad = control.retuned(pj, opened.project, opened.results, [replace(rows[2], value="15nH")])
    assert (bad.chain, bad.what_if, bad.lines) == (None, False, [("E_RETUNE_VALUE", {"ref": "C2", "value": "15nH"})])
    assert main(["retune", str(pj), "C2=4.7pF"]) == 0
    stored = pipeline.chain_results(pj, load_project(pj))
    assert np.array_equal(res.chain, stored.chain) and res.lines == stored.lines  # retune's own numbers and lines
    monkeypatch.setattr(pipeline, "chain_results", lambda *a, **k: 1 / 0)  # any other failure: a line, never a raise
    assert control.retuned(pj, opened.project, opened.results, rows).lines == [
        ("E_INTERNAL", {"detail": "ZeroDivisionError: division by zero"})]


def test_a_read_keeps_the_unapplied_rows_whose_part_it_did_not_change(tmp_path):  # design 5.3; Review Focus 5
    before, folder, refs = lpf(), tmp_path / "lpf915", ["C1", "L1", "C2", "C3"]
    rows = control.rows(before, folder, refs)
    edited = [*rows[:2], replace(rows[2], value="4.7pF"), rows[3]]
    applied, other, mine = lpf(), lpf(), lpf()
    parts(applied)["C2"]["value"] = "4.7pF"  # Apply stored it
    parts(other)["C3"]["value"] = "3.9pF"  # a hand edit, or a terminal's retune, of another part
    parts(mine)["C2"]["value"] = "3.9pF"  # ... of the part being retuned
    assert control.carried(before, lpf(), folder, edited, rows) == (edited, False)  # a cost's or a run's read
    assert control.carried(before, applied, folder, edited, control.rows(applied, folder, refs)) == (edited, False)
    other_rows = control.rows(other, folder, refs)
    assert control.carried(before, other, folder, edited, other_rows) == ([*edited[:3], other_rows[3]], False)
    mine_rows = control.rows(mine, folder, refs)
    assert control.carried(before, mine, folder, edited, mine_rows) == (mine_rows, True)
    assert control.carried(before, None, folder, edited, []) == ([], True)  # a read that failed, or results gone stale
    assert control.carried(before, lpf(), folder, edited, []) == ([], True)  # results gone stale: no row to keep it in
    assert control.carried(before, applied, folder, edited, []) == ([], False)  # stale, but project.json stores it
    assert control.carried(None, before, folder, [], rows) == (rows, False)  # the first read


def test_apply_runs_retune_to_its_end_without_a_window_and_returns_its_lines(tmp_path, calibrated, monkeypatch):
    pj = lpf_run(tmp_path, monkeypatch).resolve()  # design 5.3 Apply, 5.4
    monkeypatch.setenv("KRS_FAKE_DATA", str(calibrated))
    code, lines = control.apply(FAKE_PREFIX, pj, ["C2=4.7pF"])
    stored = pipeline.chain_results(pj, load_project(pj))
    assert code == 0 and parts(load_project(pj))["C2"]["value"] == "4.7pF"
    assert lines[:len(stored.lines)] == [render(c, **p) for c, p in stored.lines] and lines[-1] == render(LIMITS[-1])
    assert control.apply(FAKE_PREFIX, pj, ["C2=15nH"]) == (2, [render("E_RETUNE_VALUE", ref="C2", value="15nH")])
    with pytest.raises(FileNotFoundError):
        control.apply([str(tmp_path / "no-python")], pj, [])
    seen = []  # what a real run cannot show: no window, no KiCad API variables, stdin closed
    monkeypatch.setenv("KICAD_API_TOKEN", "t")
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: seen.append(kw) or SimpleNamespace(
        returncode=0, stdout="a\n", stderr="b\n"))
    assert control.apply(["py"], pj, ["C2=1pF"]) == (0, ["a", "b"])
    assert seen[0]["stdin"] == subprocess.DEVNULL and "KICAD_API_TOKEN" not in seen[0]["env"]
    assert seen[0]["creationflags"] == (subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


def test_verify_is_stale_until_it_ran_these_values_on_this_model(tmp_path):  # design 5.3 What-if, Verify
    project = {**lpf(), "results": {"model_hash": "M"}}
    rows = control.rows(project, tmp_path, ["C1", "L1", "C2", "C3"])
    assert control.verify_stale(project, rows) == "G_VERIFY_NONE"
    for broken in ({}, {"base_hash": "M", "values": []}, {"base_hash": "M", "values": {"C1": None}},
                   {"base_hash": "M", "values": {"C1": 1e-10}}):  # hand edits: read as no verify
        assert control.verify_stale({**project, "verify": broken}, rows) == "G_VERIFY_NONE"
    values = {"C1": "100pF", "L1": "15nH", "C2": "3p3", "C3": "3.3pF"}
    project["verify"] = {"base_hash": "M", "values": values, "run_dir": str(tmp_path / "v")}
    assert control.verify_stale(project, rows) is None  # 3p3 reads as 3.3pF
    with_file = [*rows[:2], replace(rows[2], value="4.7pF", s2p="c2.s2p"), rows[3]]
    assert control.verify_stale(project, with_file) is None  # a part with a file: verify runs its stored value
    assert control.verify_stale(project, [*rows[:2], replace(rows[2], value="4.7pF"), rows[3]]) == "G_VERIFY_STALE"
    assert control.verify_stale({**project, "results": {"model_hash": "N"}}, rows) == "G_VERIFY_STALE"  # a run since
    assert control.verify_lines(project) == [] == control.verify_lines(None) == control.verify_lines({"verify": {}})
    (tmp_path / "v").mkdir()
    events = [("progress", "I_PROGRESS", {}), ("result", "I_VERIFY_COMPARE", {"x": 1}),
              ("message", "E_RESULTS_WRITE", {}), ("result", "I_VERIFY_SCOPE", {})]
    (tmp_path / "v" / "events.jsonl").write_text("".join(
        json.dumps({"t": 0, "kind": k, "job": None, "code": c, "params": p}) + "\n" for k, c, p in events),
        encoding="utf-8")
    assert control.verify_lines(project) == [("I_VERIFY_COMPARE", {"x": 1}), ("I_VERIFY_SCOPE", {})]


def test_the_advanced_fields_are_project_jsons_leaves_with_their_defaults_and_units():  # design 5.3 Advanced
    project = {**lpf(), "results": {"run_dir": "R"}, "verify": {"values": {}}}
    by = {f.name: f for f in control.fields(project)}
    assert list(by)[:5] == ["board.path", "board.sha256", "f0_hz", "harmonics", "preset"]
    assert not [name for name in by if name.startswith(("schema", "results", "verify"))]  # records, not settings
    assert (by["t_max_s"].value, by["t_max_s"].default, by["t_max_s"].unit) == (4e-08, "4e-08", "G_UNIT_S")
    assert (by["mesh.n"].default, by["lid_height_mm"].default, by["f0_hz"].default, by["f0_hz"].unit) == (
        "2", "null", "", "G_UNIT_HZ")
    assert (by["chain.series[0].model.esl_h"].unit, by["stackup.layers[0].thickness_mm"].unit) == (
        "G_UNIT_HENRY", "G_UNIT_MM")
    role = by["chain.series[2].role"]
    assert (role.path, role.value) == (("chain", "series", 2, "role"), "copper")
    assert by["classes.gnd_nets"].value == ["GND"]
    broken = {f.name: f for f in control.fields({**project, "preset": ["draft"]})}  # a hand edit to fix here
    assert broken["mesh.n"].default == "2"
    new = control.edited(project, {("preset",): "draft", ("t_max_s",): "3e-08", ("lid",): "false",
                                   ("classes", "gnd_nets"): '["GND", "AGND"]'})
    assert (new["preset"], new["t_max_s"], new["lid"], new["classes"]["gnd_nets"]) == ("draft", 3e-08, False,
                                                                                         ["GND", "AGND"])
    assert project["preset"] == "normal"  # a copy: nothing is saved until Save


def test_open_project_keeps_project_json_as_stored_for_advanced(tmp_path, fake):  # design 5.3 Advanced
    pj = new_project(tmp_path, "coupon_gcpw_pads", preset="draft").resolve()
    save_project(pj, {**load_project(pj), "harmonics": 0})  # a hand edit the project's checks refuse
    broken = control.open_project(pj)
    assert broken.problem[0] == "E_PROJECT_FIELD" and broken.project is None and broken.stored["harmonics"] == 0
    assert control.open_project(tmp_path / "nope.json").stored is None


def test_an_antenna_project_opens_with_its_far_field_and_where_it_comes_from(tmp_path, calibrated):  # design 5.10
    from test_project import antenna_dict
    p = tmp_path / "unread" / "project.json"
    p.parent.mkdir()
    save_project(p, antenna_dict())  # its board is not beside it: the read stops there, Advanced still gets it
    unread = control.open_project(p)
    assert unread.problem[0] == "E_BOARD_UNREADABLE" and unread.stored == antenna_dict()
    assert unread.board == board_file(p, antenna_dict()) and unread.far is None
    pj = antenna_project(tmp_path / "m0").resolve()
    assert pipeline.run(pj) == 0  # M = 0: its run is its far-field run
    opened, d = control.open_project(pj), load_project(pj)
    assert (opened.problem, opened.results.refs, opened.far_lay) == (None, [], None)
    assert opened.far_source == ("T_RUN", d["results"]["run_dir"]) and len(opened.far["sphere"].f) == 2
    outputs = pipeline.antenna_outputs(pj, d, "x", errors_as_lines=True)
    n = len(opened.results.lines)
    assert outputs[:n] == opened.results.lines and [c for c, _ in outputs[n:]] == ["I_OUTPUTS", *ANTENNA_LIMITS]
    assert opened.stored == d and opened.board == board_file(pj, d)


def test_the_retune_session_of_an_antenna_gives_retunes_lines_and_reads_nothing(
        tmp_path, calibrated, monkeypatch):  # design 5.7, 5.10; Review Focus 2, 3
    pj = pi_run(tmp_path, monkeypatch).resolve()
    assert pipeline.verify(pj) == 0
    opened, d = control.open_project(pj), load_project(pj)
    assert opened.far_source == ("T_VERIFY", d["verify"]["run_dir"])
    assert opened.far_lay.f.tolist() == sorted(opened.far["sphere"].f.tolist())
    rows = [replace(row, value=value) for row, value in
            zip(control.rows(d, pj.parent, opened.results.refs), ("0R", "open", "open"))]  # the feed line alone
    with monkeypatch.context() as m:  # read once, on the pool: an edit reads no far field and no waves
        for name in ("far_of", "layout", "current_verify"):
            m.setattr(pipeline, name, lambda *a, **k: 1 / 0)
        res = control.retuned(pj, opened.project, opened.results, rows, opened.far, opened.far_lay)
    lines = []
    assert pipeline.retune(pj, ["L1=0R", "C2=open", "C3=open"], lambda c, p: lines.append((c, p))) == 0
    assert lines[:len(res.lines)] == res.lines and [c for c, _ in res.lines].count("I_ANTENNA_ETA_WHAT_IF") == 2
    assert [c for c, _ in lines[len(res.lines):]] == ["I_WHAT_IF", "I_OUTPUTS", *ANTENNA_LIMITS]
    bad = control.retuned(pj, opened.project, opened.results, [replace(rows[0], value="open")], opened.far,
                          opened.far_lay)
    assert (bad.chain, bad.lines) == (None, [("E_RETUNE_OPEN_SERIES", {"ref": "L1"})])
    assert control.text(*bad.lines[0]) == render("G_RETUNE_OPEN_SERIES", ref="L1")
    none = control.retuned(pj, opened.project, opened.results, rows)  # no far field given: none, nothing read
    assert ("I_ANTENNA_NO_FAR_FIELD" in [c for c, _ in none.lines]
            and control.text("I_ANTENNA_NO_FAR_FIELD", {"command": "x"}) == render("G_ANTENNA_NO_FAR_FIELD"))


def test_an_antenna_read_whose_stored_part_is_refused_keeps_verifys_far_field_for_the_retune(
        tmp_path, calibrated, monkeypatch):  # design 5.7, 5.10; plan 5 final review F1
    pj = pi_run(tmp_path, monkeypatch).resolve()
    assert pipeline.verify(pj) == 0
    d = load_project(pj)
    parts(d)["C3"]["value"] = "x"  # a stored value that reads as none: the read refuses it, the verify untouched
    save_project(pj, d)
    assert pipeline.current_verify(load_project(pj)) == d["verify"]
    opened = control.open_project(pj)
    assert opened.problem is None and opened.results.chain is None
    assert opened.results.lines[-1] == ("E_PART_NO_VALUE", {"ref": "C3", "value": "x"})  # the refusal, last
    assert opened.far is not None and opened.far_source == ("T_VERIFY", d["verify"]["run_dir"])
    assert opened.far_lay.f.tolist() == sorted(opened.far["sphere"].f.tolist())
    rows = [replace(row, value="1pF") if row.ref == "C3" else row
            for row in control.rows(opened.project, pj.parent, opened.results.refs)]  # the user fixes that row
    with monkeypatch.context() as m:  # read once, on the pool: the fix reads no far field and no waves
        for name in ("far_of", "layout", "current_verify"):
            m.setattr(pipeline, name, lambda *a, **k: 1 / 0)
        res = control.retuned(pj, opened.project, opened.results, rows, opened.far, opened.far_lay)
    codes = [c for c, _ in res.lines]
    assert res.chain is not None and codes.count("I_ANTENNA_ETA_WHAT_IF") == 2
    assert "I_ANTENNA_NO_FAR_FIELD" not in codes
    lines = []  # last: retune writes the project
    assert pipeline.retune(pj, ["C3=1pF"], lambda c, p: lines.append((c, p))) == 0
    assert lines[:len(res.lines)] == res.lines


def test_an_antennas_verify_is_stale_when_a_bypass_changes(tmp_path):  # design 5.7; Review Focus 4
    project = load_project(antenna_project(tmp_path / "pi", FIX / "ifa2g4_pi.kicad_pcb"))
    project = {**project, "results": {"model_hash": "M"},
               "verify": {"base_hash": "M", "values": {"L1": "0R", "C2": "open", "C3": "1pF"}, "run_dir": "v"}}

    def stale(l1, c2, c3):
        return control.verify_stale(project, [control.Row(ref, value, "", "series")
                                              for ref, value in (("L1", l1), ("C2", c2), ("C3", c3))])

    assert stale("0R", "open", "1pF") is None and stale("0", "OPEN", "1p") is None  # an L of 0 is a short
    assert stale("open", "open", "1pF") == stale("0R", "0R", "1pF") == "G_VERIFY_STALE"  # 0R against open
    assert stale("0R", "open", "1.2pF") == "G_VERIFY_STALE"


def test_advanced_shows_an_antennas_fields_with_its_own_defaults_and_units():  # design 5.10; ruling 5
    from test_project import antenna_dict
    d = antenna_dict()
    by = {f.name: f for f in control.fields(d)}
    assert not {"kind", "copper", "harmonics", "band_factor"} & set(by)  # sheet copper is not offered (A-35)
    assert {name: (by[name].default, by[name].unit) for name in (
        "t_max_s", "region.expand_h", "lid", "air_gap_mm", "boundary", "far_field.step_deg", "band.f_lo_hz")} == {
        "t_max_s": ("3e-08", "G_UNIT_S"), "region.expand_h": ("6.0", "G_UNIT_SUBSTRATE"), "lid": ("true", None),
        "air_gap_mm": ("31.228381", "G_UNIT_MM"), "boundary": ('"pml_8"', None),
        "far_field.step_deg": ("5", "G_UNIT_DEG"), "band.f_lo_hz": ("", "G_UNIT_HZ")}
    far = by["far_field.f_hz"]
    assert json.loads(far.default) == d["far_field"]["f_hz"] and far.unit == "G_UNIT_HZ"
    broken = {f.name: f for f in control.fields({**d, "band": "x"})}  # a hand edit Advanced is there to fix
    assert (broken["t_max_s"].default, broken["air_gap_mm"].default, broken["boundary"].default) == ("", "", '"pml_8"')
    v1 = {f.name: f.default for f in control.fields(lpf())}
    assert (v1["t_max_s"], v1["region.expand_h"], v1["lid"]) == ("4e-08", "3.0", "null")  # v1's as before


def test_an_si_project_opens_with_the_clis_reading_and_lines(tmp_path, calibrated, monkeypatch):  # 5.10; ruling 1
    from test_project import si_dict
    p = tmp_path / "unread" / "project.json"
    p.parent.mkdir()
    save_project(p, si_dict())  # its board is not beside it: the read stops there, Advanced still gets it
    unread = control.open_project(p)
    assert unread.problem[0] == "E_BOARD_UNREADABLE" and unread.stored == si_dict()
    monkeypatch.setenv("KRS_FAKE", "network")
    pj = si_project(tmp_path / "usb2_hs").resolve()
    assert control.open_project(pj).problem == ("E_NO_RESULTS", {})  # opened, no longer refused
    assert pipeline.run(pj) == 0
    opened, d = control.open_project(pj), load_project(pj)
    reading, lines = pipeline.si_view(d, pipeline.chain_results(pj, d, errors_as_lines=True))
    assert (opened.problem, opened.results.refs, opened.results.lines) == (None, ["R1", "R2"], lines)
    assert np.array_equal(opened.results.reading.m, reading.m) and "G_SI_LATER" not in CATALOG


def test_the_si_retune_session_gives_retunes_reading_and_lines_and_reads_no_waves(tmp_path, calibrated, monkeypatch):
    monkeypatch.setenv("KRS_FAKE", "network")  # design 5.7, 5.10; ruling 3
    pj = si_project(tmp_path / "usb2_hs").resolve()
    assert pipeline.run(pj) == 0
    opened = control.open_project(pj)
    rows = [replace(row, value="24") for row in control.rows(opened.project, pj.parent, opened.results.refs)]
    with monkeypatch.context() as m:  # the stored layout serves the session: no waves read
        m.setattr(pipeline, "layout", lambda *a, **k: 1 / 0)
        res = control.retuned(pj, opened.project, opened.results, rows)
    lines = []
    assert pipeline.retune(pj, ["R1=24", "R2=24"], lambda c, p: lines.append((c, p))) == 0
    assert lines[:len(res.lines)] == res.lines
    assert [c for c, _ in lines[len(res.lines):]] == ["I_WHAT_IF", "I_OUTPUTS", *si_limits(load_project(pj))]
    d = load_project(pj)
    assert np.array_equal(res.reading.m, pipeline.si_view(d, pipeline.chain_results(pj, d))[0].m)
    bad = control.retuned(pj, opened.project, opened.results, [replace(rows[0], value="open"), rows[1]])
    assert (bad.chain, bad.reading, bad.lines) == (None, None, [("E_RETUNE_OPEN_SERIES", {"ref": "R1"})])
    assert control.text(*bad.lines[0]) == render("G_RETUNE_OPEN_SERIES", ref="R1")


def test_an_si_verify_is_stale_when_a_bypass_changes():  # Stage 4 design 5.7; ruling 3; Review Focus 5
    from test_project import si_dict
    d = si_dict()
    d["lines"][0]["chain"]["series"] = [{"ref": "C1", "value": "0R"}]  # an AC-coupling capacitor bypassed
    d = {**d, "results": {"model_hash": "M"}, "verify": {"base_hash": "M", "values": {"C1": "0R"}, "run_dir": "v"}}

    def stale(c1):
        return control.verify_stale(d, [control.Row("C1", c1, "", "series")])

    assert stale("0R") is None and stale("open") == "G_VERIFY_STALE"  # port_value reads both as None


def test_advanced_shows_an_si_projects_fields_with_its_interfaces_defaults_and_units():  # ruling 8
    from test_project import si_dict
    d = si_dict()
    by = {f.name: f for f in control.fields(d)}
    assert not {"kind", "schema"} & set(by)
    names = ("f_max_hz", "rise_s", "marker_hz", "target_ohm", "tolerance", "dielectric", "window_s", "t_max_s",
             "mesh.max_cell_mm", "gates.dt_floor", "region.expand_h", "lid")
    assert {n: (by[n].default, by[n].unit) for n in names} == {
        "f_max_hz": ("10000000000.0", "G_UNIT_HZ"), "rise_s": ("5e-10", "G_UNIT_S"),
        "marker_hz": ("240000000.0", "G_UNIT_HZ"), "target_ohm": ("90.0", "G_UNIT_OHM"), "tolerance": ("0.1", None),
        "dielectric": ('"lossless"', None), "window_s": ("", "G_UNIT_S"), "t_max_s": ("", "G_UNIT_S"),
        "mesh.max_cell_mm": ("null", "G_UNIT_MM"), "gates.dt_floor": ("0.6", None),
        "region.expand_h": ("6.0", "G_UNIT_SUBSTRATE"), "lid": ("true", None)}  # null: the d fill (gate P4-C)
    for interface in ("custom", ["x"]):  # the user's own, and a hand edit that is not text, which Advanced must open
        listed = {f.name: f.default for f in control.fields({**d, "interface": interface})}
        assert [listed[n] for n in ("f_max_hz", "rise_s", "marker_hz", "target_ohm")] == [""] * 4


def test_compare_runs_into_the_bases_own_folder_and_gives_its_table_in_the_windows_words(tmp_path, calibrated):
    a = antenna_project(tmp_path / "a").resolve()  # design 5.8, 5.10
    assert pipeline.run(a) == 0
    b = twin(a, tmp_path / "b")
    code, lines, cells = control.compare(a, b)
    assert code == 0 and lines[0] == ("I_ANTENNA_RELATIVE", {})
    assert [row[0] for row in cells] == [render(q) for q in ("G_QUANTITY_RESONANCE", "G_QUANTITY_BANDWIDTH",
                                                             *["G_QUANTITY_ETA_TOT"] * 3, "G_QUANTITY_PEAK_GAIN")]
    said = dict(lines)  # each delta's line, rounded as the table rounds it
    res, gain = said["I_COMPARE_RESONANCE"], said["I_COMPARE_GAIN"]
    assert (cells[0][3], cells[0][6], cells[5][2], cells[5][4]) == (res["base_mhz"], res["shift_mhz"],
                                                                    gain["f_mhz"], gain["variant_dbi"])
    assert sorted(p.name for p in (a.parent / control.COMPARE_FOLDER).iterdir()) == ["compare.csv", "compare.png"]
    assert not (b.parent / control.COMPARE_FOLDER).exists()


def test_the_compare_tables_cells_word_each_si_quantity_and_mark_and_round_as_the_lines():  # ruling 5
    def row(quantity, marker, f_hz, base, variant, unit, delta, threshold, resolved):
        return dict(zip(DELTA_COLUMNS, (quantity, marker, f_hz, base, variant, unit, delta, unit, threshold, resolved)))

    rows = [row("tdr_highest", "short", "", "95.01", "97.22", "Ω", "2.21", "2.2", "True"),
            row("sdd21", "marker", "240000000.0", "-1.9123", "-1.9", "dB", "0.0123", "0.05", "False"),
            row("scd21_worst", "", "", "-45.56", "-27.89", "dB", "17.67", "0.5", "True"),
            row("skew", "", "", "1.5", "-0.5", "ps", "-2.0", "1.0", "True"),
            row("next", "AUX", "", "-25.72", "-19.37", "dB", "6.35", "0.5", "True")]
    assert control.cells(rows) == [
        [render("G_QUANTITY_TDR_HIGHEST"), render("G_MARK_SHORT"), "", "95.01", "97.22", "Ω", "+2.21", "Ω", "2.20",
         render("T_RESOLVED")],
        ["Sdd21", render("G_MARK_MARKER"), "240.0", "-1.912", "-1.900", "dB", "+0.012", "dB", "0.050",
         render("T_NOT_RESOLVED")],  # an insertion to 3 decimals, as si_delta_lines prints it
        ["Scd21", "", "", "-45.56", "-27.89", "dB", "+17.67", "dB", "0.50", render("T_RESOLVED")],
        [render("G_QUANTITY_SKEW"), "", "", "+1.50", "-0.50", "ps", "-2.00", "ps", "1.00", render("T_RESOLVED")],
        ["NEXT", "AUX", "", "-25.72", "-19.37", "dB", "+6.35", "dB", "0.50", render("T_RESOLVED")]]  # skew signed


def test_compare_gives_two_si_projects_table_in_the_windows_words(tmp_path, calibrated, monkeypatch):  # ruling 5
    a = verified_si(tmp_path, monkeypatch).resolve()
    assert pipeline.verify(a) == 0
    b = twin(a, tmp_path / "b")
    code, lines, cells = control.compare(a, b)
    assert code == 0 and lines[0] == ("I_SI_RELATIVE", {})
    assert [row[0] for row in cells] == [render("G_QUANTITY_TDR_LOWEST"), render("G_QUANTITY_TDR_HIGHEST"), "Sdd21",
                                         "Sdd21", "Sdd11", "Scd21", render("G_QUANTITY_SKEW"), "NEXT", "FEXT"]
    assert [row[1] for row in cells] == ["", "", render("G_MARK_MARKER"), "f_max", "", "", "", "AUX", "AUX"]
    insertion = next(p for c, p in lines if c == "I_SI_COMPARE_INSERTION")
    assert (cells[2][2], cells[2][3], cells[2][6]) == ("240.0", insertion["base"], insertion["delta"])
    assert sorted(p.name for p in (a.parent / control.COMPARE_FOLDER).iterdir()) == ["compare.csv", "compare.png"]


def test_about_names_the_version_the_licence_notices_and_each_runtime_dependency(monkeypatch):  # design 5.3 About
    real = metadata.version

    def version(name):
        if name in ("openEMS", "CSXCAD"):  # installed apart from pip, if at all
            raise metadata.PackageNotFoundError(name)
        return real(name)

    monkeypatch.setattr(metadata, "version", version)
    text = control.about()
    assert text.startswith(f"kicad-rf-studio {__version__}: ") and "ABSOLUTELY NO WARRANTY" in text
    assert "Copyright" in text and "GNU General Public License" in text  # GPL-3.0's appropriate legal notices
    assert "https://www.gnu.org/licenses/" in text  # GPL-3.0 §5(d)
    for name, licence in control.DEPENDENCIES:
        shown = render("G_NOT_INSTALLED") if name in ("openEMS", "CSXCAD") else real(name)
        assert render("G_ABOUT_DEPENDENCY", name=name, version=shown, licence=licence) in text.splitlines()
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {re.split(r"[<>=!~;\[ ]", d, maxsplit=1)[0].lower() for d in pyproject["project"]["dependencies"]}
    assert declared <= {name.lower() for name, _ in control.DEPENDENCIES}  # every core dependency is named


def test_notice_names_each_runtime_dependency_with_its_licence_as_about_does():  # design 5.6 Licensing; A-19
    notice = (Path(__file__).resolve().parents[1] / "NOTICE").read_text(encoding="utf-8")
    entry = next(e for e in notice.split("\n\n\n") if e.startswith("Runtime dependencies (not included)\n"))
    assert re.findall(r"^  - (\S+) \((.+)\)$", entry, re.M) == list(control.DEPENDENCIES)  # one list for both
    assert "start only with a build that bundles them, which is deferred." in " ".join(entry.split())  # design 5.6
