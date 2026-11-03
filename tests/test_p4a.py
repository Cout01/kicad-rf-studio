# SPDX-License-Identifier: GPL-3.0-or-later
import json

import pytest

import kicad_lines
import p4a


@pytest.fixture(scope="module")
def measured():
    return p4a.measure()  # about 12 s: thirteen cs2d pairs of three solves each


def test_p4a_passes(measured):  # Stage 4 design 5.11: P4-A in CI; a failure is a code bug, which blocks Stage 4
    rows = measured["rows"]
    assert [r for r in rows if r["pass"] is False] == [] and measured["verdict"] == "pass"
    assert {r["check"] for r in rows} == {"cohn", "kj_1um", "kj_35um", "kj_recorded", "identity", "tdr"}
    assert [r["check"] for r in rows].count("cohn") == 8 and len(rows) == 50  # 8 + 16 + 12 + 8 + 4 + 2
    assert all(r["pass"] is None for r in rows if r["check"] == "kj_recorded")  # recorded, never gated
    assert [r["quantity"] for r in rows if r["check"] == "kj_35um" and r["pass"] is None] == ["eps_even", "eps_odd"] * 3


def test_the_references_are_the_formulas_as_ported():  # design 5.11: committed before the gate, never regenerated
    for c in p4a.REFS["cohn"]["cases"]:
        assert p4a.cohn(c["w"], c["s"], c["b"], c["er"]) == pytest.approx((c["z_even"], c["z_odd"]), rel=1e-12)
    for key in ("kj_1um", "kj_35um", "kj_recorded"):
        for c in p4a.REFS[key]["cases"]:
            t = c.get("t_mm", p4a.REFS[key]["t_mm"])  # a case's own thickness, else its group's
            assert kicad_lines.coupled_microstrip(c["w"], c["s"], c["h"], t, c["er"]) == pytest.approx(
                (c["z_even"], c["eps_even"], c["z_odd"], c["eps_odd"]), rel=1e-9)


def test_p4a_writes_its_record(measured, tmp_path, monkeypatch):  # design 5.11: a short report under docs/validation
    monkeypatch.setattr(p4a, "measure", lambda: measured)
    assert p4a.main(["--out", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "p4a" / "p4a.json").read_text(encoding="utf-8"))
    assert (data["gate"], data["verdict"], len(data["rows"])) == ("P4-A", "pass", 50) and data["wall_s"] >= 0
    assert (tmp_path / "p4a" / "p4a.md").read_text(encoding="utf-8").startswith("## P4A-1 Checks")
