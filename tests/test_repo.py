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

def test_the_lgpl_text_ships_with_the_lgpl_code():
    # R-P2-17: smooth.py is LGPL-3.0-or-later code conveyed in a GPL-3.0-or-later package, which carries both texts
    lesser = (ROOT / "COPYING.LESSER").read_text(encoding="utf-8").splitlines()
    assert [line.strip() for line in lesser[:2]] == ["GNU LESSER GENERAL PUBLIC LICENSE", "Version 3, 29 June 2007"]
    entries = (ROOT / "NOTICE").read_text(encoding="utf-8").split("\n\n\n")
    assert "COPYING.LESSER" in next(e for e in entries if "SmoothMeshLines" in e)
    licence = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["license"]
    assert licence == "GPL-3.0-or-later AND LGPL-3.0-or-later"

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

def test_run_folders_and_kicad_side_files_are_ignored_and_the_p0_fixtures_are_not():  # D-20, spec 9.1
    ignored = ["runs/r/model.json", "p0/runs/job-1/waves.npz", "#auto_saved_files#", "_autosave-x", "a.kicad_sch",
               "a.kicad_dru", "fp-lib-table", "sym-lib-table"]
    kept = ["tests/fixtures/traces/lpf915-k1.npz", "tests/fixtures/p0d/lpf915.npz", "tests/fixtures/lpf915.kicad_pcb",
            "docs/validation/2026-11-05-p0-a.md", "docs/validation/2026-11-05-p0-a.json",
            "tests/fixtures/a.kicad_sch", "tests/fixtures/a.kicad_dru", "tests/fixtures/fp-lib-table",
            "tests/fixtures/sym-lib-table"]  # PF-1: KiCad side files stay committable under tests/fixtures

    def by_git(path):  # --no-index: a tracked fixture is held to the patterns too
        return subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT).returncode == 0

    assert [p for p in ignored if not by_git(p)] == [] and [p for p in kept if by_git(p)] == []

def test_the_readme_names_both_licence_texts():  # D-21
    first = (ROOT / "README.md").read_text(encoding="utf-8").split("\n\n")[1]
    assert "`LICENSE`" in first and "`COPYING.LESSER`" in first

def test_the_readme_has_a_tutorial():  # D-21
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "\n## Tutorial\n" in readme
    tutorial = readme.split("\n## Tutorial\n", 1)[1].split("\n## ", 1)[0]
    assert [c for c in ("new", "cost", "run", "retune", "verify") if f"kicad-rf-studio {c} " not in tutorial] == []

def test_every_workflow_starts_with_an_spdx_header():  # D-55
    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert files and [p.name for p in files if p.read_text(encoding="utf-8").splitlines()[0] != SPDX] == []
