# SPDX-License-Identifier: GPL-3.0-or-later
import json
import re
import subprocess
import tomllib
from pathlib import Path
import pytest
import kicad_rf_studio
from kicad_rf_studio.cli import main
from kicad_rf_studio.core.messages import CATALOG
from kicad_rf_studio.core.post.si import DIFF_OHM, SE_OHM

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

def test_notice_names_each_kicad_calculator_file_the_tests_port():  # ruling 13; P4-A's c_microstrip.cpp
    ported = set(re.findall(r"pcb_calculator/transline/(\w+\.(?:cpp|h))",
                            (ROOT / "tests" / "kicad_lines.py").read_text(encoding="utf-8")))
    entry = next(e for e in (ROOT / "NOTICE").read_text(encoding="utf-8").split("\n\n\n")
                 if e.startswith("KiCad line-calculator formulas"))
    assert ported == {"microstrip.cpp", "c_microstrip.cpp", "coplanar.cpp", "transline.cpp", "units.h"}
    assert ported <= set(re.findall(r"\b\w+\.(?:cpp|h)\b", entry))

def test_every_golden_pin_names_a_clean_product_tree():  # ruling 13: golden_antenna's +dirty stamp (plan 4's R-11)
    stamps = {p.name: json.loads(p.read_text(encoding="utf-8"))["code"]
              for p in sorted((ROOT / "tests" / "fixtures").glob("golden_*.json"))}
    assert sorted(stamps) == ["golden_antenna.json", "golden_si.json", "golden_v1.json"]
    assert [name for name, code in stamps.items() if not re.fullmatch(r"[0-9a-f]{40}", code)] == []
    assert stamps["golden_antenna.json"] == "e5469200427c76d82e9d2893363696ead16cf351"  # R-11's src tree, at 8faa7d6

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

def test_the_readme_has_an_antenna_tutorial():  # Stage 3 design 5.12 item 5
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.index("\n## Tutorial\n") < readme.index("\n## Antenna tutorial\n") < readme.index(
        "\n## Development setup\n")
    tutorial = readme.split("\n## Antenna tutorial\n", 1)[1].split("\n## ", 1)[0]
    band = "--start U1.1 --antenna AE1 --band 2400MHz:2483.5MHz"
    for command in (f"new tests/fixtures/ifa2g4_pi.kicad_pcb {band} -o ifa2g4_pi", "cost ifa2g4_pi",
                    "run ifa2g4_pi", "retune ifa2g4_pi L1=0R C2=0.13pF C3=1pF", "verify ifa2g4_pi",
                    f"new tests/fixtures/ifa2g4_pi_pour.kicad_pcb {band} -o ifa2g4_pi_pour",
                    "compare ifa2g4_pi ifa2g4_pi_pour -o compare"):
        assert f"kicad-rf-studio {command}\n" in tutorial, command
    assert "\n### What these results do not tell you\n" in tutorial and CATALOG["I_ANTENNA_RELATIVE"] in tutorial

def test_the_readme_has_an_si_tutorial():  # Stage 4 design 5.12 item 5; ruling 11
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.index("\n## Antenna tutorial\n") < readme.index("\n## Signal-integrity tutorial\n") < readme.index(
        "\n## Development setup\n")
    tutorial = readme.split("\n## Signal-integrity tutorial\n", 1)[1].split("\n## ", 1)[0]
    pair = "--start J1.3 --end U1.3 --interface usb2-hs --pair --victim TP1.1:TP2.1"
    for command in (f"new tests/fixtures/usb2_hs.kicad_pcb {pair} -o usb2_hs", "cost usb2_hs", "run usb2_hs",
                    "retune usb2_hs R1=24 R2=24", "verify usb2_hs",
                    f"new tests/fixtures/usb2_hs_gap.kicad_pcb {pair} -o usb2_hs_gap", "run usb2_hs_gap",
                    "retune usb2_hs_gap R1=24 R2=24", "verify usb2_hs_gap", "compare usb2_hs usb2_hs_gap -o compare"):
        assert f"kicad-rf-studio {command}\n" in tutorial, command
    assert "\n### What these results do not tell you\n" in tutorial and CATALOG["I_SI_RELATIVE"] in tutorial
    assert f"{DIFF_OHM:g} Ω" in tutorial and f"{SE_OHM:g} Ω" in tutorial  # the short band and compare's thresholds
    assert "a track, arc or via" in readme.split("\n## Install\n", 1)[1].split("\n## ", 1)[0]

def test_the_readme_installs_the_app_openems_and_the_button_with_real_commands(capsys):  # design 5.6, 7; RF 4
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = readme.split("\n## Install\n", 1)[1].split("\n## ", 1)[0]
    step = "Preferences › Plugins › Enable KiCad API, then restart KiCad"
    assert step in CATALOG["I_PLUGIN_NEXT"] and step in install  # the README quotes the command's own words
    assert r"%LOCALAPPDATA%\kicad-rf-studio\venv" in install  # design 5.6's concrete venv
    assert "run `install-kicad-plugin` again" in install  # Review Focus 4: a moved venv
    assert "-m pip install --force-reinstall --no-deps <source>" in install  # its programs first (final review)
    # ponytail: code spans and fences only; a command named in prose goes unchecked
    code = "\n".join(re.findall(r"```[^\n]*\n(.*?)```", readme, re.S) + re.findall(r"`([^`\n]+)`", readme))
    named = set(re.findall(r"kicad-rf-studio[\"']? ([a-z][a-z-]*)", code))
    assert {"setup-openems", "install-kicad-plugin"} <= named
    for command in sorted(named):  # each a real subcommand: argparse shows its help and exits 0, else 2
        with pytest.raises(SystemExit) as e:
            main([command, "--help"])
        assert e.value.code == 0, command
    capsys.readouterr()

def test_every_workflow_starts_with_an_spdx_header():  # D-55
    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert files and [p.name for p in files if p.read_text(encoding="utf-8").splitlines()[0] != SPDX] == []

def test_the_release_check_workflow_runs_on_a_version_tag_or_by_hand_on_windows_and_at_the_linux_floor():  # A-20
    flow = (ROOT / ".github" / "workflows" / "release-check.yml").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    floor = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["requires-python"]
    triggers = flow.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]  # the whole block: a trigger added fails it
    assert triggers == '  push:\n    tags: ["v*"]\n  workflow_dispatch:\n'  # never a branch push (design 4)
    assert "\npermissions:\n  contents: read\n" in flow and "persist-credentials: false" in flow  # no token kept
    assert "fetch-depth: 0" in flow  # a shallow clone would leave the privacy gate one commit to scan
    pairs = re.findall(r"- os: (\S+)\n\s+python-version: \"([\d.]+)\"", flow)  # the matrix's (os, Python) pairs
    assert pairs == [("windows-latest", "3.14"), ("ubuntu-24.04", floor[2:])]  # the README's Python, Linux's floor
    assert next(line for line in ci.splitlines() if "libegl1" in line) in flow.splitlines()  # Review Focus 5
    assert flow.splitlines()[-1] == "      - run: python tools/release_check.py"
