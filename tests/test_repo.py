# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
import tomllib
from pathlib import Path
import kicad_rf_studio

ROOT = Path(__file__).resolve().parents[1]
SPDX = "# SPDX-License-Identifier: GPL-3.0-or-later"
LGPL = {"src/kicad_rf_studio/core/mesh/smooth.py": "# SPDX-License-Identifier: LGPL-3.0-or-later"}  # CSXCAD's copy

def test_version():
    assert kicad_rf_studio.__version__ == "0.1.0.dev0"

def test_every_python_file_has_spdx_header():
    files = [p for d in ("src", "tools", "tests") if (ROOT / d).is_dir() for p in (ROOT / d).rglob("*.py")]
    missing = [str(p.relative_to(ROOT)) for p in files
               if LGPL.get(p.relative_to(ROOT).as_posix(), SPDX) not in p.read_text(encoding="utf-8").splitlines()[:2]]
    assert missing == []

def test_ci_tests_the_declared_python_floor_with_read_only_permissions():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    floor = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["requires-python"]
    assert floor.startswith(">=") and f'python-version: "{floor[2:]}"' in ci
    assert "\npermissions:\n  contents: read\n" in ci and "fail-fast: false" in ci

def test_env_files_are_ignored():
    paths = [".env", ".env.local", "secrets.env", ".envrc", "venv/x.py", "env/x.py", ".venv-2/x.py"]
    not_ignored = [p for p in paths
                   if subprocess.run(["git", "check-ignore", "-q", p], cwd=ROOT).returncode != 0]
    assert not_ignored == []
