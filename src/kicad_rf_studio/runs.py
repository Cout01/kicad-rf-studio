# SPDX-License-Identifier: GPL-3.0-or-later
"""What a run needs besides the project: the per-user data folder with its settings.json, and openEMS in this Python.
`setup-openems` installs the wheels of the official Windows package; `check_openems` reads the installed versions."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from kicad_rf_studio.core.messages import KrsError, reason
from kicad_rf_studio.core.project import save_project

WINDOWS = sys.platform == "win32"  # tests patch it
# metadata only, so no openEMS DLL loads; run with -I, which sees what a worker sees
PROBE = "import importlib.metadata as m; print(m.version('openEMS'), m.version('CSXCAD'))"


def data_dir() -> Path:
    """The per-user data folder, never a temp folder (spec 3.3): %LOCALAPPDATA% on Windows, else $XDG_DATA_HOME."""
    name, default = ("LOCALAPPDATA", "~/AppData/Local") if WINDOWS else ("XDG_DATA_HOME", "~/.local/share")
    return Path(os.environ.get(name) or default).expanduser() / "kicad-rf-studio"


def load_settings() -> dict:
    """settings.json in data_dir(), or {} before anything wrote it."""
    path = data_dir() / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))  # -sig: as load_project, for a hand edit
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:  # ValueError: UnicodeError or json.JSONDecodeError
        raise KrsError("E_SETTINGS_UNREADABLE", path=str(path), reason=reason(e)) from None
    if not isinstance(data, dict):
        raise KrsError("E_SETTINGS_UNREADABLE", path=str(path), reason="not a JSON object")
    return data


def save_settings(data: dict) -> None:
    """Writes settings.json, making data_dir() first."""
    data_dir().mkdir(parents=True, exist_ok=True)
    save_project(data_dir() / "settings.json", data)


def install_command() -> str:
    """How to give this Python openEMS, as the E_OPENEMS_* messages say it."""
    if WINDOWS:
        return "kicad-rf-studio setup-openems <openEMS folder>"
    return "update_openEMS.sh <prefix> --python with this venv active (see README)"


def openems_versions() -> tuple[str, str]:
    """The openEMS and CSXCAD versions installed in this Python. Raises E_OPENEMS_MISSING."""
    probe = subprocess.run([sys.executable, "-I", "-c", PROBE], capture_output=True, text=True, timeout=120)
    if probe.returncode:
        raise KrsError("E_OPENEMS_MISSING", python=sys.executable, command=install_command())
    openems, csxcad = probe.stdout.split()
    return openems, csxcad


def check_openems() -> list[tuple[str, dict]]:
    """W_OPENEMS_UNTESTED outside openEMS 0.37.x. Raises E_OPENEMS_MISSING, or E_OPENEMS_OLD below openEMS 0.37 or
    CSXCAD 0.7."""
    openems, csxcad = openems_versions()
    em, cs = (tuple(map(int, re.match(r"(\d+)\.(\d+)", v).groups())) for v in (openems, csxcad))
    if em < (0, 37) or cs < (0, 7):
        raise KrsError("E_OPENEMS_OLD", openems=openems, csxcad=csxcad, command=install_command())
    return [] if em == (0, 37) else [("W_OPENEMS_UNTESTED", {"openems": openems, "command": install_command()})]


def setup_openems(folder: Path) -> list[tuple[str, dict]]:
    """Installs the openEMS and CSXCAD wheels of the official Windows package in `folder` into this Python, without
    their dependencies (pyproject.toml lists them), and records the folder in settings.json."""
    if not WINDOWS:
        raise KrsError("E_SETUP_OPENEMS_WINDOWS")
    tag, wheels = f"cp{sys.version_info.major}{sys.version_info.minor}", folder / "python"
    has_wheels = all(any(wheels.glob(f"{name}-*-{tag}-*.whl")) for name in ("openems", "csxcad"))
    if not (has_wheels and (folder / "openEMS.exe").exists()):
        raise KrsError("E_SETUP_OPENEMS_DIR", dir=str(folder), tag=tag)
    # --no-index: neither name is claimed on PyPI, so pip must never look there for them. --force-reinstall: else pip
    # keeps an installed openEMS of another version while settings.json names this folder
    pip = subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--force-reinstall",
                          "--find-links", str(wheels), "openEMS", "CSXCAD"])
    if pip.returncode:
        raise KrsError("E_SETUP_OPENEMS_PIP", exit_code=pip.returncode)
    settings = load_settings()
    settings["openems_dir"] = str(folder.resolve())
    save_settings(settings)
    openems, csxcad = openems_versions()
    return [("I_OPENEMS_INSTALLED", {"openems": openems, "csxcad": csxcad, "dir": settings["openems_dir"],
                                     "settings": str(data_dir() / "settings.json")})]
