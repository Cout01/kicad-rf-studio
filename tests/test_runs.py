# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from kicad_rf_studio import pipeline, runs
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import KrsError, render

TAG = f"cp{sys.version_info[0]}{sys.version_info[1]}"


def package(tmp_path, tag=TAG):
    """A folder laid out like the official Windows package: openEMS.exe, and python/ with the two wheels."""
    d = tmp_path / "openEMS"
    (d / "python").mkdir(parents=True)
    (d / "openEMS.exe").write_bytes(b"")
    for name in ("openems-0.37.0", "csxcad-0.7.0"):
        (d / "python" / f"{name}-{tag}-{tag}-win_amd64.whl").write_bytes(b"")
    return d


@pytest.fixture
def calls(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: seen.append(cmd) or
                        subprocess.CompletedProcess(cmd, 0, "0.37.0 0.7.0\n", ""))
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")  # not created: save_settings makes it
    monkeypatch.setattr(runs, "WINDOWS", True)
    return seen


def test_setup_openems_installs_both_wheels_offline_and_records_the_folder(tmp_path, calls, capsys):
    pkg = package(tmp_path)
    assert main(["setup-openems", str(pkg)]) == 0
    assert calls[0] == [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--force-reinstall",
                        "--find-links", str(pkg / "python"), "openEMS", "CSXCAD"]
    assert runs.load_settings() == {"openems_dir": str(pkg.resolve())}
    assert capsys.readouterr().out.splitlines()[-1] == render(
        "I_OPENEMS_INSTALLED", openems="0.37.0", csxcad="0.7.0", dir=str(pkg.resolve()),
        settings=str(tmp_path / "data" / "settings.json"))


def test_setup_openems_is_for_windows_only(tmp_path, calls, monkeypatch):
    monkeypatch.setattr(runs, "WINDOWS", False)
    with pytest.raises(KrsError) as e:
        runs.setup_openems(package(tmp_path))
    assert (e.value.code, e.value.params, calls) == ("E_SETUP_OPENEMS_WINDOWS", {}, [])


def test_setup_openems_needs_the_wheels_of_this_python(tmp_path, calls):
    pkg = package(tmp_path, tag="cp39")
    with pytest.raises(KrsError) as e:
        runs.setup_openems(pkg)
    assert (e.value.code, e.value.params, calls) == ("E_SETUP_OPENEMS_DIR", {"dir": str(pkg), "tag": TAG}, [])


@pytest.mark.parametrize(("out", "rc", "code", "params"), [
    ("0.37.0 0.7.0\n", 0, None, {}),
    ("0.38.1 0.7.2\n", 0, "W_OPENEMS_UNTESTED", {"openems": "0.38.1"}),
    ("0.36.2 0.7.0\n", 0, "E_OPENEMS_OLD", {"openems": "0.36.2", "csxcad": "0.7.0"}),
    ("0.37.0 0.6.9\n", 0, "E_OPENEMS_OLD", {"openems": "0.37.0", "csxcad": "0.6.9"}),
    ("", 1, "E_OPENEMS_MISSING", {"python": sys.executable})])
def test_the_version_check_reads_metadata_in_an_isolated_subprocess(monkeypatch, out, rc, code, params):
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: seen.append(cmd) or
                        subprocess.CompletedProcess(cmd, rc, out, ""))
    if code and code.startswith("E_"):
        with pytest.raises(KrsError) as e:
            runs.check_openems()
        got = [(e.value.code, e.value.params)]
    else:
        got = runs.check_openems()
    assert got == ([(code, {**params, "command": runs.install_command()})] if code else [])
    assert seen[0][:3] == [sys.executable, "-I", "-c"] and "import openEMS" not in seen[0][3]  # no DLL load


@pytest.mark.parametrize("probe", [subprocess.TimeoutExpired(["python"], 120),  # a probe that hung
                                   subprocess.CompletedProcess([], 0, "0.37.0\n", "")])  # one word printed
def test_a_probe_that_hangs_or_prints_one_version_reads_as_openems_missing(monkeypatch, probe):  # plan 3's minor
    def run(cmd, **kw):
        if isinstance(probe, Exception):
            raise probe
        return probe

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(KrsError) as e:
        runs.openems_versions()
    assert (e.value.code, e.value.params) == ("E_OPENEMS_MISSING", {"python": sys.executable,
                                                                   "command": runs.install_command()})


@pytest.mark.parametrize(("windows", "code", "text"), [
    (True, "T_INSTALL_WINDOWS", "kicad-rf-studio setup-openems <openEMS folder>"),
    (False, "T_INSTALL_LINUX", "update_openEMS.sh <prefix> --python with this venv active (see README)")])
def test_the_install_hint_is_a_term_and_reads_as_before(monkeypatch, windows, code, text):  # pt-BR design 5.1
    monkeypatch.setattr(runs, "WINDOWS", windows)
    assert runs.install_command() == code and render(code) == text


@pytest.mark.parametrize(("windows", "env", "expected"), [
    (True, {"LOCALAPPDATA": "/x/Local"}, "/x/Local/kicad-rf-studio"),
    (False, {"XDG_DATA_HOME": "/x/share"}, "/x/share/kicad-rf-studio"),
    (False, {}, "~/.local/share/kicad-rf-studio")])
def test_the_data_folder_is_per_user_never_temp(monkeypatch, windows, env, expected):  # spec 3.3
    monkeypatch.setattr(runs, "WINDOWS", windows)
    for name in ("LOCALAPPDATA", "XDG_DATA_HOME"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert runs.data_dir() == Path(expected).expanduser()


@pytest.mark.openems
def test_openems_imports_in_this_python():  # tier b: the dev venv after setup-openems
    assert runs.check_openems() == []


# --- beyond the brief's tests: the settings file and a failed pip ------------------------------------------------


@pytest.mark.parametrize(("text", "why"), [("{", "T_NOT_JSON"), ("[]", "T_NOT_A_JSON_OBJECT")])
def test_unreadable_settings_name_the_file_and_why(tmp_path, calls, text, why):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "settings.json").write_text(text, encoding="utf-8")
    with pytest.raises(KrsError) as e:
        runs.load_settings()
    assert (e.value.code, e.value.params) == (
        "E_SETTINGS_UNREADABLE", {"path": str(tmp_path / "data" / "settings.json"), "reason": why})


def test_setup_openems_keeps_the_other_settings(tmp_path, calls):
    runs.save_settings({"machines": {"pc": {"threads": 2}}})  # calibrate's
    runs.setup_openems(package(tmp_path))
    assert runs.load_settings()["machines"] == {"pc": {"threads": 2}}


def test_setup_openems_needs_openems_exe(tmp_path, calls):
    pkg = package(tmp_path)
    (pkg / "openEMS.exe").unlink()
    with pytest.raises(KrsError) as e:
        runs.setup_openems(pkg)
    assert (e.value.code, calls) == ("E_SETUP_OPENEMS_DIR", [])


def test_a_failed_pip_records_nothing(tmp_path, calls, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", ""))
    with pytest.raises(KrsError) as e:
        runs.setup_openems(package(tmp_path))
    assert (e.value.code, e.value.params, runs.load_settings()) == ("E_SETUP_OPENEMS_PIP", {"exit_code": 1}, {})


# --- run folders, the lock and events ------------------------------------------------------------------------------


def test_run_and_job_folder_names_are_ascii(tmp_path, monkeypatch):  # Review Focus 2, C-23
    monkeypatch.setattr(runs, "data_dir", lambda: tmp_path / "data")
    d = runs.run_dir_for("projeto ação")
    assert d.parent == tmp_path / "data" / "runs" and re.fullmatch(r"projeto_a__o-\d{8}-\d{6}-[0-9a-f]{4}", d.name)
    assert runs.job_dir(d, 3, "C1·Ω").name == "job-3-C1__"
    assert runs.write_job(d / "job-1-P1", 1, "run", 2, 1e-9) == d / "job-1-P1"


def test_a_live_lock_refuses_and_a_stale_one_is_reclaimed(tmp_path, capsys):  # C-24
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    with pytest.raises(KrsError) as e:
        with runs.project_lock(pj, tmp_path / "new"):
            pass
    assert (e.value.code, e.value.params) == ("E_LOCKED", {"lock": str(lock), "run": "R", "started": "S"})
    assert json.loads(lock.read_text(encoding="utf-8"))["run_dir"] == "R"  # the holder's lock is intact
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    with runs.project_lock(pj, tmp_path / "new"):
        assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == os.getpid()
    assert not lock.exists() and capsys.readouterr().out == render("W_STALE_LOCK", lock=str(lock), run="R") + "\n"


def test_a_stale_lock_reclaimed_for_an_existing_run_folder_is_an_event_there(tmp_path, capsys):  # final review F6
    pj, lock, run_dir = tmp_path / "project.json", tmp_path / "project.json.lock", tmp_path / "run"
    run_dir.mkdir()  # as cli.main makes a --run-dir folder before the lock: the GUI's Run tab shows its events
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    assert pipeline._locked(pj, lambda path, d: 0, run_dir) == 0  # run's and verify's lock (final review F11)
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(e["kind"], e["code"], e["params"]) for e in events] == [
        ("message", "W_STALE_LOCK", {"lock": str(lock), "run": "R"})]
    assert capsys.readouterr().out == render("W_STALE_LOCK", lock=str(lock), run="R") + "\n"  # the same line


def test_a_stale_lock_reclaimed_without_events_is_only_printed(tmp_path, capsys):  # final review F11: retune, p0
    pj, lock, run_dir = tmp_path / "project.json", tmp_path / "project.json.lock", tmp_path / "results"
    run_dir.mkdir()  # retune's results/ or the P0 folder: no run folder, so no stray events.jsonl
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    with runs.project_lock(pj, run_dir):
        pass
    assert not (run_dir / "events.jsonl").exists()
    assert capsys.readouterr().out == render("W_STALE_LOCK", lock=str(lock), run="R") + "\n"  # the same line


def test_events_are_json_lines_mirrored_on_stdout(tmp_path, capsys):  # spec 3.3, 6.1
    params = {"kind": "gr_text", "uuid": "u", "layer": "F.Cu"}  # W_COPPER_DROPPED has a field named kind
    runs.emit(tmp_path, "message", "W_COPPER_DROPPED", params, job=2)
    e = json.loads((tmp_path / "events.jsonl").read_text(encoding="utf-8"))
    assert set(e) == {"t", "kind", "job", "code", "params"}
    assert (e["kind"], e["job"], e["code"], e["params"]) == ("message", 2, "W_COPPER_DROPPED", params)
    assert capsys.readouterr().out == render("W_COPPER_DROPPED", **params) + "\n"


def test_pool_size_follows_cores_and_ram():  # C-25, spec 6.4
    assert runs.pool_size(2_000_000, 4, 32_000, 16) == 4
    assert runs.pool_size(2_000_000, 4, 1_000, 16) == 2  # 1000 // (340 + 50)
    assert runs.pool_size(20_000_000, 4, 1_000, 16) == 1  # never 0


# beyond the brief's tests: a failed run's lock, and free_ram_mb, which no other test reaches


def test_a_failed_run_releases_its_lock(tmp_path):  # C-24: removed on exit, exceptions included
    lock = tmp_path / "project.json.lock"
    with pytest.raises(ZeroDivisionError):
        with runs.project_lock(tmp_path / "project.json", tmp_path / "run"):
            held = json.loads(lock.read_text(encoding="utf-8"))
            1 / 0
    assert not lock.exists() and held["run_dir"] == str(tmp_path / "run")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d(:\d\d){2}", held["started"])  # ISO time


def test_free_ram_is_read_from_the_system():  # a wrong MEMORYSTATUSEX size reads 0, and every pool would be 1
    assert 0 < runs.free_ram_mb() < 2**24  # MB: under 16 TB


def test_the_lock_holder_and_whether_it_lives(tmp_path):  # design 5.1, 5.2 item 6
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    assert runs.lock_file(pj) == lock and runs.lock_holder(pj) is None
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    assert runs.lock_holder(pj) == {"pid": os.getpid(), "run_dir": "R", "started": "S", "alive": True}
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    lock.write_text(json.dumps({"pid": dead.pid, "run_dir": "R", "started": "S"}), encoding="utf-8")
    assert runs.lock_holder(pj)["alive"] is False
    lock.write_text("", encoding="utf-8")  # made by O_EXCL, not yet written: a run starting
    assert runs.lock_holder(pj) == {"pid": None, "run_dir": None, "started": None, "alive": True}


@pytest.mark.parametrize("text", ["{}", "[]", "null", '{"pid": "7"}'])
def test_a_malformed_lock_reads_as_one_not_yet_written(tmp_path, text):  # final review F5: a hand edit
    pj = tmp_path / "project.json"
    runs.lock_file(pj).write_text(text, encoding="utf-8")
    assert runs.lock_holder(pj) == {"pid": None, "run_dir": None, "started": None, "alive": True}


def test_a_malformed_lock_refuses_the_run(tmp_path):  # final review F5: E_LOCKED after its waits, never E_INTERNAL
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    lock.write_text("{}", encoding="utf-8")
    with pytest.raises(KrsError) as e:
        with runs.project_lock(pj, tmp_path / "run"):
            pass
    assert (e.value.code, e.value.params) == ("E_LOCKED", {"lock": str(lock), "run": None, "started": None})


def test_a_lock_with_only_its_pid_reads_its_folder_and_start_as_none(tmp_path):  # final review F10: a hand edit
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    lock.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    with pytest.raises(KrsError) as e:  # never KeyError, which the GUI's tick would raise too
        with runs.project_lock(pj, tmp_path / "run"):
            pass
    assert (e.value.code, e.value.params) == ("E_LOCKED", {"lock": str(lock), "run": None, "started": None})
    assert runs.lock_holder(pj) == {"pid": os.getpid(), "run_dir": None, "started": None, "alive": True}


def test_a_lock_that_cannot_be_read_reads_as_one_not_yet_written(tmp_path, monkeypatch):  # final review F5
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    real = Path.read_text

    def read_text(self, *args, **kwargs):  # Windows: the lock opened while it is being deleted
        if self == lock:
            raise PermissionError(13, "access denied")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert runs.lock_holder(pj) == {"pid": None, "run_dir": None, "started": None, "alive": True}


def test_a_lock_released_while_it_is_read_is_taken(tmp_path, monkeypatch):  # was E_INTERNAL (FileNotFoundError)
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    lock.write_text(json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"}), encoding="utf-8")
    real = runs.lock_holder

    def released(path):  # the holder ends between this run's O_EXCL and its read
        lock.unlink()
        return real(path)

    monkeypatch.setattr(runs, "lock_holder", released)
    with runs.project_lock(pj, tmp_path / "new"):
        assert json.loads(lock.read_text(encoding="utf-8"))["run_dir"] == str(tmp_path / "new")


def test_a_lock_still_being_written_is_waited_for(tmp_path):  # never "running since None in None"
    pj, lock = tmp_path / "project.json", tmp_path / "project.json.lock"
    lock.write_text("", encoding="utf-8")  # made by O_EXCL, not yet written
    holder = json.dumps({"pid": os.getpid(), "run_dir": "R", "started": "S"})
    threading.Timer(0.1, lock.write_text, [holder], {"encoding": "utf-8"}).start()
    with pytest.raises(KrsError) as e:
        with runs.project_lock(pj, tmp_path / "new"):
            pass
    assert (e.value.code, e.value.params) == ("E_LOCKED", {"lock": str(lock), "run": "R", "started": "S"})


def test_the_lock_is_released_though_a_reader_holds_it_a_moment(tmp_path):  # the GUI reads it every 500 ms
    pj = tmp_path / "project.json"
    with runs.project_lock(pj, tmp_path / "run"):
        reader = open(runs.lock_file(pj), encoding="utf-8")  # Windows refuses to delete a file open elsewhere
        threading.Timer(0.2, reader.close).start()
    assert not runs.lock_file(pj).exists()
