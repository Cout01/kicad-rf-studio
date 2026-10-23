# kicad-rf-studio

kicad-rf-studio imports KiCad boards and simulates their RF parts with openEMS. It is free software, licensed under the GNU General Public License v3.0 or later (see `LICENSE`); its copy of CSXCAD's SmoothMeshLines is under the GNU Lesser General Public License v3.0 or later (see `COPYING.LESSER`).

## Install

### Windows

1. Create a virtual environment with Python 3.14: `py -3.14 -m venv <venv>`
2. Install kicad-rf-studio into it: `<venv>\Scripts\python -m pip install <clone of this repository>`
3. Unpack the official Windows package of openEMS 0.37 and give its folder, the one that holds `openEMS.exe` and `python\`, to `<venv>\Scripts\kicad-rf-studio setup-openems <openEMS folder>`. It installs the package's openEMS and CSXCAD wheels into the venv, offline, and records the folder.

### Linux

On Debian 12, Ubuntu 24.04 or Fedora, with the system Python (3.11 or newer):

1. Create a virtual environment and activate it: `python3 -m venv <venv>`, then `source <venv>/bin/activate`
2. Install kicad-rf-studio into it: `pip install <clone of this repository>`
3. In a clone of upstream's openEMS-Project, install the build dependencies with `./scripts/install_deps.sh --install --python`, then build with `./update_openEMS.sh <prefix> --python` while the venv is active. Leave the GUI build on (no `--disable-GUI`): it builds AppCSXCAD.

## Development setup

1. Create a virtual environment: `python -m venv .venv`
2. Activate it: `.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere.
3. Install the package in editable mode with the development extras: `python -m pip install -e .[dev]`
4. Give the venv openEMS as Install says (on Windows, `kicad-rf-studio setup-openems <openEMS folder>`). Without it, the tests marked `openems` are skipped.
5. Run the tests: `python -m pytest -q`

## Contributing

Set up the local privacy gate before you commit or push. It refuses private names, absolute drive and home paths, network shares and e-mail addresses. CI repeats only the generic checks.

1. Write the words that must never leave your machine in a UTF-8 text file kept outside the repository, one per line. Blank lines and lines starting with `#` are ignored, and matching ignores case.
2. Point `KRS_PRIVATE_LIST` at that file. In PowerShell: `$env:KRS_PRIVATE_LIST = "<path to the file>"`. In a POSIX shell: `export KRS_PRIVATE_LIST=<path to the file>`.
3. Enable the hooks: `git config core.hooksPath .githooks`

The hooks run `tools/privacy_gate.py` with the Python found on your `PATH`; it needs only the standard library. Without a usable list they refuse the commit or push. `python tools/privacy_gate.py --all` scans the whole history by hand.

A hit prints as `<where>:<line>: <rule>`. `deny#N` is the N-th entry of your list, counting entries only, and `generic:...` is one of the built-in rules. The gate never prints matched text; a file whose name matched shows as `path#N`.
