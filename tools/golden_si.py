# SPDX-License-Identifier: GPL-3.0-or-later
"""The SI golden pins (Stage 4 plan 2): sha256 digests of what `new --interface` writes and the model it builds for
each SI fixture, everywhere, and of its 2D table where golden_v1.env() matches, recorded once at plan 2's end in
tests/fixtures/golden_si.json through golden_v1.record. Plans 3 to 5 keep them; a deliberate change (plan 4's
defaults) is a ruled re-recording."""
import os

if __name__ == "__main__":
    os.environ["LANGUAGE"] = "en"  # the suite's language, set before core.messages binds one: golden_v1.env() holds it

import json
import sys
from pathlib import Path

import golden_v1
import p0
from golden_antenna import _board
from golden_v1 import sha
from kicad_rf_studio import cli, pipeline
from kicad_rf_studio.core.model.spec import spec_hash

sys.path.append(str(p0.ROOT / "tests"))  # test_cli_si: si_args, the fixtures' five commands written once
from test_cli_si import si_args  # noqa: E402

GOLDEN = p0.FIX / "golden_si.json"
CASES = ("usb2_hs", "usb2_hs_neck", "usb2_hs_gap", "usb2_hs_45", "qspi_clk")


def digests() -> dict:
    """{"models": {case: {"spec_hash", "model_json", "project", "notes", "blocked"}}, "outputs": {case: {"readout"}}},
    each board copied into the working folder (_board) and built there by new_si with test_cli_si's si_args: the model
    spec by its hash and model.json's bytes, project.json by its bytes, new's lines without I_WROTE, the mesh gates
    that block a run, and cost's 2D table (si_readout)."""
    models, outputs = {}, {}
    for name in CASES:
        file = Path(_board(name))
        args, kw = si_args(file)
        pj, notes = cli.new_si(file, *args, **kw, output=Path(name))
        project, board, geom, _ = pipeline.load(pj)
        model = pipeline.build_model(project, board, geom)
        spec = model.spec
        models[name] = {"spec_hash": spec_hash(spec), "model_json": sha(json.dumps(spec).encode()),
                        "project": sha(pj.read_bytes()),
                        "notes": sha(json.dumps(notes[:-1], sort_keys=True, default=str).encode()),
                        "blocked": sha(json.dumps(model.blocked, sort_keys=True, default=str).encode())}
        table = pipeline.si_readout(board, geom, project)
        outputs[name] = {"readout": sha(json.dumps(table, sort_keys=True).encode())}
    return {"models": models, "outputs": outputs}


def main() -> int:
    """Records digests() in GOLDEN through golden_v1.record; 1 when GOLDEN exists."""
    return golden_v1.record(GOLDEN, digests)


if __name__ == "__main__":
    sys.exit(main())
