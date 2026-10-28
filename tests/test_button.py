# SPDX-License-Identifier: GPL-3.0-or-later
"""The KiCad button (Stage 2 design 5.5, 5.8): the helper KiCad runs, its handoff and its quiet contract, a run
outliving KiCad's job, the plugin that install-kicad-plugin writes, and refill and save. KiCad is
tests/fake_kicad.py."""
import contextlib
import ctypes
import json
import os
import signal
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import pytest

from kicad_rf_studio import button, runs
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.messages import CATALOG, render
from test_cli_cost import FIX
from test_gui_control import recorder, until

LPF = FIX / "lpf915.kicad_pcb"
KIID = {p.name: p.uuid for p in load_board(LPF).all_pads()}  # J1.2 is two pads: never selected here
HELPER_CODES = ("E_KICAD_UNREACHABLE", "E_KICAD_BUSY", "E_KICAD_UNSUPPORTED", "E_KICAD_VERSION", "E_KICAD_NO_BOARD",
                "E_HANDOFF_WRITE", "E_GUI_START", "E_INTERNAL")


def gui_python() -> str:
    """The Python a stand-in GUI runs on: pythonw beside this one on Windows, which opens no console when started
    detached."""
    return str(Path(sys.executable).with_name("pythonw.exe")) if sys.platform == "win32" else sys.executable


def test_the_helper_hands_the_selection_to_a_detached_gui_and_prints_nothing(fake, kicad, monkeypatch, capsys):
    # design 5.5 steps 1-5; 10.0.7 is newer than kipy 0.8.0's 10.0.6, which check_version() would refuse
    k = kicad(pads=[KIID["J1.1"], KIID["U1.1"]], footprints=["C1"], version=(10, 0, 7),
              errors={"GetSelection": ["AS_BUSY"]})
    monkeypatch.setenv("KICAD_API_SOCKET", k.url)
    monkeypatch.setenv("KICAD_API_TOKEN", k.token)
    calls = recorder(monkeypatch)
    assert button.main() == 0
    assert capsys.readouterr() == ("", "")  # KiCad 10 shows any stderr text as an error
    handoff = fake / "handoff.json"
    assert json.loads(handoff.read_text(encoding="utf-8")) == {
        "board": str(LPF), "pads": [KIID["J1.1"], KIID["U1.1"]], "footprints": ["C1"], "kicad": "10.0.7",
        "socket": k.url, "token": k.token}
    assert k.seen == ["GetVersion", "GetOpenDocuments", "GetSelection", "GetSelection"]  # AS_BUSY: asked again
    assert set(k.tokens) == {k.token} and not (fake / "button.log").exists()
    name = "kicad-rf-studio-gui.exe" if sys.platform == "win32" else "kicad-rf-studio-gui"
    (call,) = calls
    assert call.args == button.gui_command(handoff) == [
        str(Path(sysconfig.get_path("scripts"), name)), "--handoff", str(handoff)]  # this environment's, not PATH's
    assert (call.stdin, call.stdout, call.cwd) == (subprocess.DEVNULL, subprocess.DEVNULL, fake)
    assert Path(call.stderr.name) == fake / "gui.log"  # its tracebacks: pythonw on a null stderr would lose them
    if sys.platform == "win32":
        assert call.creationflags == subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # design 5.5's
    else:
        assert call.start_new_session is True


@pytest.mark.parametrize(("serve", "token", "code", "params"), [
    ({"errors": {"GetVersion": ["AS_BUSY"] * 4}}, None, "E_KICAD_BUSY", {}),  # still busy when its 1 s is up
    ({"errors": {kind: ["AS_BUSY"] * 3 for kind in ("GetVersion", "GetOpenDocuments", "GetSelection")}}, None,
     "E_KICAD_BUSY", {}),  # one 1 s for the whole press, not one for each call: about 2 s in all (design 5.5)
    ({"errors": {"GetSelection": ["AS_UNHANDLED"]}}, None, "E_KICAD_UNSUPPORTED", {}),  # not in this KiCad
    ({"errors": {"GetOpenDocuments": ["AS_UNIMPLEMENTED"]}}, None, "E_KICAD_UNSUPPORTED", {}),
    ({"version": (8, 0, 9)}, None, "E_KICAD_VERSION", {"version": "8.0.9"}),
    ({"version": (11, 0, 0)}, None, "E_KICAD_VERSION", {"version": "11.0.0"}),
    ({"board": Path("")}, None, "E_KICAD_NO_BOARD", {}),  # a new board KiCad never saved has no file name
    ({}, "another KiCad's", "E_KICAD_UNREACHABLE", {}),  # AS_TOKEN_MISMATCH: KiCad restarted since
    (None, None, "E_KICAD_UNREACHABLE", {}),  # no API server at the socket
    ({"errors": {"GetSelection": ["AS_BAD_REQUEST"]}}, None, "E_INTERNAL",
     {"detail": "ApiError: KiCad returned error:"})])
def test_the_helper_says_why_on_one_stderr_line_and_in_button_log_and_starts_nothing(
        fake, kicad, tmp_path, monkeypatch, capsys, serve, token, code, params):  # design 5.5; Review Focus 4
    k = None if serve is None else kicad(**serve)
    monkeypatch.setenv("KICAD_API_SOCKET", k.url if k else f"ipc://{tmp_path / 'none.sock'}")
    monkeypatch.setenv("KICAD_API_TOKEN", token or (k.token if k else ""))
    calls = recorder(monkeypatch)
    assert button.main() == 1
    line = render(code, **params)
    assert capsys.readouterr() == ("", line + "\n")
    assert (fake / "button.log").read_text(encoding="utf-8").splitlines()[-1].endswith(" " + line)
    assert calls == [] and not (fake / "handoff.json").exists()


def test_a_handoff_that_cannot_be_written_or_a_gui_that_cannot_start_is_its_own_line(fake, kicad, monkeypatch,
                                                                                     capsys):  # design 5.5
    assert all(CATALOG[c].isascii() for c in HELPER_CODES)  # KiCad 10 decodes stderr in a code page nobody can check
    k = kicad()
    monkeypatch.setenv("KICAD_API_SOCKET", k.url)
    monkeypatch.setenv("KICAD_API_TOKEN", k.token)
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text("")  # a file where the data folder goes
    assert button.main() == 1
    assert capsys.readouterr().err == render("E_HANDOFF_WRITE", path=str(fake / "handoff.json"),
                                             reason="already exists as a file") + "\n"
    fake.unlink()
    missing = fake / "no-gui"
    monkeypatch.setattr(button, "gui_command", lambda handoff: [str(missing), "--handoff", str(handoff)])
    assert button.main() == 1
    assert capsys.readouterr().err == render("E_GUI_START", program=str(missing), reason="file not found") + "\n"


def test_run_as_kicad_10_runs_it_the_helper_ends_quickly_says_nothing_and_its_gui_holds_no_pipe(kicad, tmp_path):
    # design 5.5's output contract, 4 and 5.8 (no Qt in the helper, when run), 5.11 item 3; Review Focus 3, 4
    k = kicad(pads=[KIID["U1.1"], KIID["J1.1"]])
    stand_in = tmp_path / "gui.py"  # the GUI's stand-in: says how it was started, then runs on
    stand_in.write_text(
        "import json, os, sys, time\n"
        "with open(os.environ['KRS_FAKE_GUI'] + '.tmp', 'w') as out:\n"
        "    json.dump({'argv': sys.argv[1:], 'pid': os.getpid()}, out)\n"
        "os.replace(os.environ['KRS_FAKE_GUI'] + '.tmp', os.environ['KRS_FAKE_GUI'])\n"
        "time.sleep(10)\n", encoding="utf-8")
    helper = ("import sys; from kicad_rf_studio import button; button.gui_command = lambda handoff: "
              f"[{gui_python()!r}, '-I', {str(stand_in)!r}, '--handoff', str(handoff)]; rc = button.main(); "
              "assert not {'PySide6', 'shiboken6', 'matplotlib'} & {m.split('.')[0] for m in sys.modules}; "
              "sys.exit(rc)")
    local, started = tmp_path / "local", tmp_path / "gui.json"
    env = {**os.environ, "KICAD_API_SOCKET": k.url, "KICAD_API_TOKEN": k.token, "LOCALAPPDATA": str(local),
           "XDG_DATA_HOME": str(local), "KRS_FAKE_GUI": str(started)}
    begin = time.monotonic()
    out = subprocess.run([sys.executable, "-X", "utf8", "-I", "-c", helper], capture_output=True, env=env, timeout=60)
    took = time.monotonic() - begin
    assert (out.returncode, out.stdout, out.stderr) == (0, b"", b"")
    assert took < 5.0  # had the GUI kept the pipes, they would close only at its end, 10 s on
    until(started.exists)
    gui = json.loads(started.read_text(encoding="utf-8"))
    try:
        assert gui["argv"] == ["--handoff", str(local / "kicad-rf-studio" / "handoff.json")]
        assert runs._alive(gui["pid"])  # detached: it outlives the helper
    finally:
        with contextlib.suppress(OSError):
            os.kill(gui["pid"], signal.SIGTERM)


KICAD_JOB = r'''
import ctypes, sys
from pathlib import Path
from kicad_rf_studio.gui import control
k32 = ctypes.WinDLL("kernel32")
k32.OpenJobObjectW.restype = ctypes.c_void_p
job = ctypes.c_void_p(k32.OpenJobObjectW(0x1F001F, False, sys.argv[1]))  # JOB_OBJECT_ALL_ACCESS
assert job.value and k32.AssignProcessToJobObject(job, ctypes.c_void_p(-1))  # this process: a GUI in KiCad's job
folder = Path(sys.argv[2])
run = control.start([sys.executable, "-I", "-c", "import time; time.sleep(30)"], "run", folder / "project.json",
                    folder / "run")
k32.CloseHandle(job)
print(run.pid)
'''


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job objects")
def test_a_run_the_gui_starts_inside_a_kicad_job_that_kills_on_close_outlives_it(tmp_path):
    # design 3 (a lost run) and plan 1's carry-over: the GUI stays in any job KiCad runs its actions in, but the runs
    # it starts leave it (control.start's breakaway), so they outlive KiCad; Review Focus 3
    k32 = ctypes.WinDLL("kernel32")
    k32.CreateJobObjectW.restype = ctypes.c_void_p  # a HANDLE, which the default int would cut to 32 bits
    name = f"Local\\krs-test-job-{os.getpid()}"
    job = ctypes.c_void_p(k32.CreateJobObjectW(None, name))
    info = (ctypes.c_ulonglong * 18)()  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION (x64), as runs._job_object builds it
    info[2] = 0x2000 | 0x800  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_BREAKAWAY_OK
    assert k32.SetInformationJobObject(job, 9, info, ctypes.sizeof(info))
    out = subprocess.run([sys.executable, "-I", "-c", KICAD_JOB, name, str(tmp_path)], capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    pid = int(out.stdout)
    try:
        k32.CloseHandle(job)  # KiCad closes: its job kills every process still in it
        time.sleep(0.5)
        assert runs._alive(pid)  # out of KiCad's job, so the run outlives KiCad
    finally:
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGTERM)
