# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import sys
from pathlib import Path

import pytest

from kicad_rf_studio import runs
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


@pytest.mark.parametrize(("text", "why"), [("{", "not JSON"), ("[]", "not a JSON object")])
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
