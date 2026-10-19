# kicad-rf-studio

kicad-rf-studio imports KiCad boards and simulates their RF parts with openEMS. It is free software, licensed under the GNU General Public License v3.0 or later (see `LICENSE`).

## Development setup

1. Create a virtual environment: `python -m venv .venv`
2. Activate it: `.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere.
3. Install the package in editable mode with the development extras: `python -m pip install -e .[dev]`
4. Run the tests: `python -m pytest -q`

## Contributing

Set up the local privacy gate before you commit or push. It refuses private names, absolute drive and home paths, network shares and e-mail addresses. CI repeats only the generic checks.

1. Write the words that must never leave your machine in a UTF-8 text file kept outside the repository, one per line. Blank lines and lines starting with `#` are ignored, and matching ignores case.
2. Point `KRS_PRIVATE_LIST` at that file. In PowerShell: `$env:KRS_PRIVATE_LIST = "<path to the file>"`. In a POSIX shell: `export KRS_PRIVATE_LIST=<path to the file>`.
3. Enable the hooks: `git config core.hooksPath .githooks`

The hooks run `tools/privacy_gate.py` with the Python found on your `PATH`; it needs only the standard library. Without a usable list they refuse the commit or push. `python tools/privacy_gate.py --all` scans the whole history by hand.

A hit prints as `<where>:<line>: <rule>`. `deny#N` is the N-th entry of your list, counting entries only, and `generic:...` is one of the built-in rules. The gate never prints matched text; a file whose name matched shows as `path#N`.
