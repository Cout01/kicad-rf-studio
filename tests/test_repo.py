# SPDX-License-Identifier: GPL-3.0-or-later
import subprocess
from pathlib import Path
import kicad_rf_studio

ROOT = Path(__file__).resolve().parents[1]
SPDX = "# SPDX-License-Identifier: GPL-3.0-or-later"

def test_version():
    assert kicad_rf_studio.__version__ == "0.1.0.dev0"

def test_every_python_file_has_spdx_header():
    files = [p for d in ("src", "tools", "tests") if (ROOT / d).is_dir() for p in (ROOT / d).rglob("*.py")]
    missing = [str(p.relative_to(ROOT)) for p in files
               if SPDX not in p.read_text(encoding="utf-8").splitlines()[:2]]
    assert missing == []

def test_env_files_are_ignored():
    paths = [".env", ".env.local", "secrets.env", ".envrc", "venv/x.py", "env/x.py", ".venv-2/x.py"]
    not_ignored = [p for p in paths
                   if subprocess.run(["git", "check-ignore", "-q", p], cwd=ROOT).returncode != 0]
    assert not_ignored == []
