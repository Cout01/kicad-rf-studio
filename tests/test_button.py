# SPDX-License-Identifier: GPL-3.0-or-later
"""The KiCad button (Stage 2 design 5.5, 5.8): the helper KiCad runs, its handoff and its quiet contract, a run
outliving KiCad's job, the plugin that install-kicad-plugin writes, refill and save, and select (Stage 5 design 5.5).
KiCad is tests/fake_kicad.py."""
import contextlib
import ctypes
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import pytest

from kicad_rf_studio import button, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.kicad import load_board
from kicad_rf_studio.core.messages import CATALOG, KrsError, english, render
from test_cli_cost import FIX
from test_gui_control import recorder, until
import release_check

LPF = FIX / "lpf915.kicad_pcb"
EMC = FIX / "emc_review.kicad_pcb"
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
        "board": str(LPF), "pads": [KIID["J1.1"], KIID["U1.1"]], "footprints": ["C1"], "tracks": [],
        "kicad": "10.0.7", "socket": k.url, "token": k.token}
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


def test_a_press_hands_the_selected_tracks_arcs_and_vias_by_their_kiids(fake, kicad, monkeypatch):  # 5.10; ruling 9
    def pressed(**selection):
        k = kicad(**selection)
        monkeypatch.setenv("KICAD_API_SOCKET", k.url)
        monkeypatch.setenv("KICAD_API_TOKEN", k.token)
        assert button.main() == 0
        return json.loads((fake / "handoff.json").read_text(encoding="utf-8"))

    recorder(monkeypatch)
    data = pressed(pads=[KIID["U1.1"]], tracks=["t-1"], arcs=["a-1"], vias=["v-1"])
    assert (data["pads"], data["footprints"], data["tracks"]) == ([KIID["U1.1"]], [], ["t-1", "a-1", "v-1"])
    assert pressed(arcs=["a-2"])["tracks"] == ["a-2"]  # KOT_PCB_ARC asked for: the fake answers only asked types


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


def test_with_pt_br_active_the_helpers_line_stays_english_and_ascii(fake, kicad, pt_br, tmp_path, monkeypatch,
                                                                    capsys):  # pt-BR design 5.4
    k = kicad(version=(8, 0, 9))
    monkeypatch.setenv("KICAD_API_SOCKET", k.url)
    monkeypatch.setenv("KICAD_API_TOKEN", k.token)
    assert button.main() == 1
    line = english("E_KICAD_VERSION", version="8.0.9")
    assert line != render("E_KICAD_VERSION", version="8.0.9")  # pt-BR is active
    assert capsys.readouterr() == ("", line + "\n") and line.isascii()
    assert (fake / "button.log").read_text(encoding="utf-8").splitlines()[-1].endswith(" " + line)
    k = kicad()  # a GUI that cannot start: its reason, a term, in English too
    monkeypatch.setenv("KICAD_API_SOCKET", k.url)
    monkeypatch.setenv("KICAD_API_TOKEN", k.token)
    missing = tmp_path / "no-gui"
    monkeypatch.setattr(button, "gui_command", lambda handoff: [str(missing), "--handoff", str(handoff)])
    assert button.main() == 1
    err = capsys.readouterr().err
    assert err == english("E_GUI_START", program=str(missing), reason="T_FILE_NOT_FOUND") + "\n"
    assert err.replace(str(missing), "").isascii()


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


SEGMENT = "KiCad" if sys.platform == "win32" else "kicad"  # KiCad's own name for its documents folder
LAUNCHER = "launch.cmd" if sys.platform == "win32" else "launch.sh"
FILES = sorted(["plugin.json", LAUNCHER, "icon-dark-24.png", "icon-dark-48.png", "icon-light-24.png",
                "icon-light-48.png"])


def test_install_kicad_plugin_writes_each_kicad_folder_and_nothing_else(tmp_path, monkeypatch, capsys):
    docs = tmp_path / "Documentos do Zé"  # design 3, 5.5; A-17; a space and an accent, as a Documents path may have
    home, config = docs / SEGMENT, tmp_path / "config"
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(docs))
    for name in ("KICAD_CONFIG_HOME", "APPDATA", "XDG_CONFIG_HOME"):  # every place KiCad 9 and 10 read settings from
        monkeypatch.setenv(name, str(config))
    assert main(["install-kicad-plugin"]) == 2  # no KiCad started here yet
    assert capsys.readouterr().err == render("E_NO_KICAD_FOLDER", folder=str(home)) + "\n"
    settings = [config / v / "kicad_common.json" for v in ("9.0", "10.0")] + [
        config / "kicad" / v / "kicad_common.json" for v in ("9.0", "10.0")]  # KICAD_CONFIG_HOME's; APPDATA's, XDG's
    for f, text in [(s, '{"api": {"enable_server": false}}') for s in settings] + [
            (home / "9.0" / "plugins" / "other" / "plugin.json", "{}"), (home / "10.0" / "fp-lib-table", "()")]:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert main(["install-kicad-plugin"]) == 0
    folders = [home / v / "plugins" / "kicad-rf-studio" for v in ("9.0", "10.0")]
    assert capsys.readouterr().out.splitlines() == [render("I_PLUGIN_INSTALLED", folder=str(f)) for f in folders] + [
        render("I_PLUGIN_NEXT")]
    assert [sorted(p.name for p in f.iterdir()) for f in folders] == [FILES, FILES]
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert {p: after[p] for p in before} == before  # KiCad's settings and other plugins untouched
    assert {p.parent for p in after.keys() - before.keys()} == set(folders)  # only its own folders written
    assert main(["install-kicad-plugin", "--remove"]) == 0  # every version's
    assert capsys.readouterr().out.splitlines() == [render("I_PLUGIN_REMOVED", folder=str(f)) for f in folders]
    assert not any(f.exists() for f in folders) and (home / "9.0" / "plugins" / "other").is_dir()
    assert main(["install-kicad-plugin", "--remove", "--kicad", "9.0"]) == 0
    assert capsys.readouterr().out.splitlines() == [render("I_PLUGIN_NONE", folder=str(home))]
    folders[1].write_text("")  # a file where the plugin's folder goes
    assert main(["install-kicad-plugin", "--kicad", "10.0"]) == 2
    assert capsys.readouterr().err == render("E_PLUGIN_WRITE", path=str(folders[1]),
                                             reason="already exists as a file") + "\n"
    folders[1].unlink()
    shutil.rmtree(home / "10.0")
    assert main(["install-kicad-plugin", "--kicad", "10.0"]) == 0  # a version named is written, its folder made
    assert sorted(p.name for p in folders[1].iterdir()) == FILES and not folders[0].exists()


def test_the_plugin_passes_kicads_schema_and_both_identifier_rules_and_its_icons_are_pngs(tmp_path, monkeypatch,
                                                                                         qapp):  # design 5.5, 5.8
    from kipy.packaging.validate import validate_plugin
    from PySide6.QtGui import QColor, QImage
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path))
    folder = tmp_path / SEGMENT / "10.0" / "plugins" / "kicad-rf-studio"
    assert button.install("10.0") == [("I_PLUGIN_INSTALLED", {"folder": str(folder)}), ("I_PLUGIN_NEXT", {})]
    assert validate_plugin(folder).errors == []  # kipy's bundled schema, $schema, the entrypoint and the icons
    assert json.loads((folder / "plugin.json").read_text(encoding="utf-8")) == button.plugin_json(LAUNCHER) == {
        "$schema": "https://go.kicad.org/api/schemas/v1", "identifier": "org.kicadrfstudio.app",
        "name": "kicad-rf-studio", "description": render("G_BUTTON_PLUGIN"), "runtime": {"type": "exec"},
        "actions": [{"identifier": "open", "name": "kicad-rf-studio", "description": render("G_BUTTON_ACTION"),
                     "show-button": True, "scopes": ["pcb"], "entrypoint": LAUNCHER,
                     "icons-light": ["icon-light-24.png", "icon-light-48.png"],
                     "icons-dark": ["icon-dark-24.png", "icon-dark-48.png"]}]}
    assert release_check.identifier_problems(button.IDENTIFIER) == []  # KiCad 9.0.7's, 10.0.7's and design 5.5's rules
    for theme, rgb in button.ICONS.items():
        for size in button.SIZES:
            image = QImage(str(folder / f"icon-{theme}-{size}.png"))
            assert (image.width(), image.height()) == (size, size)
            assert image.pixelColor(0, 0).alpha() == 0 and image.pixelColor(size // 2, size // 4).alpha() == 0
            assert image.pixelColor(size // 2, size // 2) == QColor(*rgb)  # on the diameter, opaque


def test_kicads_documents_folder_is_its_own_choice_a_onedrive_redirect_included(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path))  # design 5.5 Install; Review Focus 5
    assert button.documents() == tmp_path
    monkeypatch.delenv("KICAD_DOCUMENTS_HOME")
    if sys.platform == "win32":  # the shell's Documents folder, as .NET reads it: its path only, never the folder
        shell = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding = "
                                "[Text.Encoding]::UTF8; [Environment]::GetFolderPath('MyDocuments')"],
                               capture_output=True, encoding="utf-8", timeout=60)
        assert button.documents() == Path(shell.stdout.strip())
    else:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        assert button.documents() == tmp_path / "xdg"
        monkeypatch.delenv("XDG_DATA_HOME")
        assert button.documents() == Path("~/.local/share").expanduser()


def test_the_launcher_quotes_this_pythons_absolute_path_for_its_shell():  # design 5.5 Launcher; Review Focus 5
    assert button.launcher("Zé Silva/100%/hi!/python.exe", windows=True) == (
        '@echo off\nsetlocal DisableDelayedExpansion\n"Zé Silva/100%%/hi!/python.exe" -X utf8 -I -m '
        'kicad_rf_studio.button %*\n')
    assert button.launcher("venvs/o'neil/bin/python", windows=False) == (
        "#!/bin/sh\nexec 'venvs/o'\\''neil/bin/python' -X utf8 -I -m kicad_rf_studio.button \"$@\"\n")


def test_the_installed_launcher_runs_the_helper_and_passes_its_line_and_exit_code(tmp_path, monkeypatch):
    docs = tmp_path / "Documentos do Zé"  # design 5.5, 5.11 item 3: KiCad runs the entrypoint in its folder
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(docs))
    install = ("import sys; from kicad_rf_studio.cli import main; rc = main(['install-kicad-plugin', '--kicad', "
               "'10.0']); assert not {'PySide6', 'shiboken6', 'kipy'} & {m.split('.')[0] for m in sys.modules}; "
               "sys.exit(rc)")
    out = subprocess.run([sys.executable, "-X", "utf8", "-I", "-c", install], capture_output=True, encoding="utf-8",
                         timeout=60)
    assert out.returncode == 0, out.stderr  # design 4: install-kicad-plugin, run, loads neither Qt nor kicad-python
    folder = docs / SEGMENT / "10.0" / "plugins" / "kicad-rf-studio"
    text = button.launcher(os.path.abspath(sys.executable), sys.platform == "win32")
    if sys.platform == "win32":
        assert (folder / LAUNCHER).read_bytes() == text.replace("\n", "\r\n").encode("oem")
    else:
        assert (folder / LAUNCHER).read_text(encoding="utf-8") == text
        assert stat.S_IMODE((folder / LAUNCHER).stat().st_mode) == 0o755
    local = tmp_path / "local"
    env = {**os.environ, "KICAD_API_SOCKET": f"ipc://{tmp_path / 'none.sock'}", "KICAD_API_TOKEN": "",
           "LOCALAPPDATA": str(local), "XDG_DATA_HOME": str(local)}
    out = subprocess.run([str(folder / LAUNCHER)], cwd=folder, env=env, capture_output=True, timeout=60)
    assert (out.returncode, out.stdout) == (1, b"")
    assert out.stderr.decode("utf-8").splitlines() == [render("E_KICAD_UNREACHABLE")]  # the helper's, through cmd or sh
    assert (local / "kicad-rf-studio" / "button.log").read_text(encoding="utf-8").endswith(
        " " + render("E_KICAD_UNREACHABLE") + "\n")


def test_install_kicad_plugin_run_again_rewrites_the_launcher_for_the_venv_where_it_now_is(tmp_path, monkeypatch):
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path))  # the README's "Moved the venv?"; Review Focus 4
    launcher = tmp_path / SEGMENT / "10.0" / "plugins" / "kicad-rf-studio" / LAUNCHER
    for venv in ("old venv", "new venv"):  # where install-kicad-plugin ran, then where the venv is now
        monkeypatch.setattr(sys, "executable", str(tmp_path / venv / "python"))
        button.install("10.0")
    assert b"new venv" in launcher.read_bytes() and b"old venv" not in launcher.read_bytes()


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe reads launch.cmd in the console's code page")
def test_a_python_path_launch_cmd_cannot_hold_is_refused(tmp_path, monkeypatch):  # Review Focus 5
    monkeypatch.setenv("KICAD_DOCUMENTS_HOME", str(tmp_path))
    python = str(tmp_path / "venv\U0001F642" / "Scripts" / "python.exe")  # in no code page
    monkeypatch.setattr(sys, "executable", python)
    with pytest.raises(KrsError) as e:
        button.install("9.0")
    assert (e.value.code, e.value.params) == ("E_PLUGIN_PYTHON", {"python": python})
    assert not (tmp_path / SEGMENT / "9.0" / "plugins" / "kicad-rf-studio").exists()  # nothing written


def test_refill_refills_then_saves_only_the_board_the_button_sent(kicad, tmp_path):  # design 5.5 Refill, 7; RF 4
    board = tmp_path / "lpf915.kicad_pcb"
    board.write_bytes(LPF.read_bytes())
    # busy past the press's BUSY_S: the save waits up to FILL_WAIT_S
    k = kicad(board, save=b"(kicad_pcb)", errors={"SaveDocument": ["AS_BUSY"] * 6 + ["SLOW"]})
    assert button.refill(k.url, k.token, board) == board  # busy while KiCad fills, then answered past the helper's 1 s
    assert k.seen == ["GetOpenDocuments", "RefillZones"] + ["SaveDocument"] * 7
    assert board.read_bytes() == b"(kicad_pcb)"  # what KiCad's save wrote
    other = kicad(tmp_path / "other.kicad_pcb", save=b"x")
    with pytest.raises(KrsError) as e:
        button.refill(other.url, other.token, board)
    assert (e.value.code, e.value.params) == ("E_KICAD_OTHER_BOARD", {"board": str(board),
                                                                      "open": str(tmp_path / "other.kicad_pcb")})
    assert other.seen == ["GetOpenDocuments"]  # nothing refilled, nothing saved
    closed = kicad(board, errors={"GetOpenDocuments": ["AS_UNHANDLED"]})  # KiCad's PCB editor closed since the press
    with pytest.raises(KrsError) as e:
        button.refill(closed.url, closed.token, board)
    assert (e.value.code, closed.seen) == ("E_KICAD_NO_BOARD", ["GetOpenDocuments"])
    with pytest.raises(KrsError) as e:
        button.refill(k.url, "another KiCad's", board)
    assert e.value.code == "E_KICAD_UNREACHABLE"


def test_select_clears_then_adds_objects_carrying_only_their_kiid_and_counts_kiCads_answer(kicad):  # 5.5; A13
    k = kicad(EMC, known={"a", "b"})  # kipy 0.8's add_to_selection reads only .id: this pins the duck typing
    assert button.select(k.url, k.token, EMC, ["a", "b", "c"]) == 2  # KiCad skips an unknown KIID
    assert k.seen == ["GetOpenDocuments", "ClearSelection", "AddToSelection"] and k.chosen == ["a", "b"]
    assert k.tokens == [k.token] * 3


def test_select_refuses_another_board_and_sends_nothing_else(kicad, tmp_path):  # design 5.5 Select
    other = kicad(tmp_path / "other.kicad_pcb")
    with pytest.raises(KrsError) as e:
        button.select(other.url, other.token, EMC, ["a"])
    assert (e.value.code, e.value.params) == ("E_KICAD_SELECT_OTHER_BOARD", {
        "board": str(EMC), "open": str(tmp_path / "other.kicad_pcb")})
    assert other.seen == ["GetOpenDocuments"]
    closed = kicad(EMC, errors={"GetOpenDocuments": ["AS_UNHANDLED"]})  # KiCad's PCB editor closed since the press
    with pytest.raises(KrsError) as e:
        button.select(closed.url, closed.token, EMC, ["a"])
    assert (e.value.code, closed.seen) == ("E_KICAD_NO_BOARD", ["GetOpenDocuments"])
    busy = kicad(EMC, errors={"AddToSelection": ["AS_BUSY"] * 9})
    with pytest.raises(KrsError) as e:
        button.select(busy.url, busy.token, EMC, ["a"])
    assert e.value.code == "E_KICAD_BUSY"
