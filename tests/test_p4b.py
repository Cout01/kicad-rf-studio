# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math

import pytest

import p4b
from kicad_rf_studio.core.post.si import read
from p4a import even_odd_s
from test_p4 import gates  # noqa: F401 (the fixture)
from test_post_si import F, P100, pair6

MS = {"next_db": -17.546, "f_q_hz": 0.6895e9, "z_ref": 50.28}  # a coupon's mesh modes' model at one n
REFS = {"coupons": {c: {"fit2d": {"2": {"z0_mesh": z2, **MS}, "3": {"z0_mesh": z3, **MS}}}
                    for c, z2, z3 in (("p4b_ms90", 91.153, 90.711), ("p4b_ms100", 100.271, 101.32),
                                      ("p4b_sl90", 91.71, 92.383))},
        "bends": {"p4b_ms90_45": {"t_mid_s": 399.6e-12}, "p4b_ms100_45": {"t_mid_s": 399.6e-12}}}


def row(plateau, next_db=-17.546, fext=-60.0, valid=True, level=None, blocked=False):
    return {"plateau_ohm": plateau, "next_db": next_db, "fext_db": fext, "valid": valid, "level_ohm": level,
            "blocked": blocked}


def z(c, n=2):
    return REFS["coupons"][c]["fit2d"][str(n)]["z0_mesh"]


def full(**over):  # every step run and passing: each coupon on its own mesh's fit2d value, the bends on their twins'
    m = {f"{c}-n{k}": row(z(c, k)) for c in p4b.COUPONS for k in (2, 3)}
    m |= {f"{b}-n2": row(None, level=z(t)) for b, t in p4b.BENDS.items()}
    return {**m, "victim": {"ds_pair": 0.0}, "bends_n3": "pending"} | over


def test_the_p4b_rules_keep_n2_and_the_warning_on_good_runs():  # design 5.11; B-4, B-6
    d = p4b.decide(full(), REFS)
    assert d["decisions"] == {"mesh_n": 2, "staircase": "warn", "cut_victim": "refusal kept"}
    assert d["verdict"] == {"value": "pass", "fails": []}


def test_each_p4b_check_inclusive_with_its_fallback():  # design 5.11's fallbacks
    def verdict(**over):
        return p4b.decide(full(**over), REFS)
    assert verdict(**{"p4b_ms100-n3": row(z("p4b_ms100", 3) * 1.0099)})["decisions"]["mesh_n"] == 2
    moved = verdict(**{"p4b_ms100-n3": row(z("p4b_ms100", 3) * 1.0101)})  # the FDTD's own move past 1 %: n 3 (B-6)
    assert moved["decisions"]["mesh_n"] == 3 and moved["verdict"] == {"value": "fallback", "fails": []}
    raw = verdict(**{"p4b_ms100-n3": row(z("p4b_ms100", 2) * 1.0105)})  # +1.05 % raw, the move fit2d predicts
    assert raw["decisions"]["mesh_n"] == 2
    bug = verdict(**{"p4b_ms90-n2": row(z("p4b_ms90") * 1.0151)})
    assert bug["verdict"]["value"] == "blocked" and "p4b_ms90-n2: zdiff" in bug["verdict"]["fails"]
    assert verdict(**{"p4b_ms90-n2": row(z("p4b_ms90"), next_db=-17.046)})["verdict"]["fails"] == []  # 0.5 dB
    assert verdict(**{"p4b_ms90-n2": row(z("p4b_ms90"), next_db=-17.036)})["verdict"]["value"] == "fail"
    assert verdict(**{"p4b_sl90-n2": row(z("p4b_sl90"), fext=-40.0)})["verdict"]["fails"] == []
    assert verdict(**{"p4b_sl90-n2": row(z("p4b_sl90"), fext=-39.9)})["verdict"]["fails"] == ["p4b_sl90-n2: fext"]
    assert verdict(**{"p4b_ms90-n2": row(z("p4b_ms90"), valid=False)})["verdict"]["fails"] == ["p4b_ms90-n2: valid"]
    assert verdict(**{"p4b_ms90-n2": row(None)})["verdict"]["fails"][0] == "p4b_ms90-n2: no reading"
    assert p4b.decide({k: v for k, v in full().items() if k != "p4b_sl90-n3"}, REFS)["verdict"]["value"] == "incomplete"
    unrun = p4b.decide(full(victim=None), REFS)
    assert unrun["decisions"]["cut_victim"] is None and unrun["verdict"]["value"] == "incomplete"


def test_the_45_degree_rule():  # B-4: the twins at n 2; n 3 only for a twin that missed, with the owner's go
    off = {"p4b_ms90_45-n2": row(None, level=z("p4b_ms90") * 1.051)}
    assert p4b.decide(full(**off), REFS)["decisions"]["staircase"] is None  # its n 3 run first
    declined = p4b.decide(full(**off, bends_n3="declined"), REFS)
    assert declined["decisions"]["staircase"] == "owner" and declined["verdict"]["value"] == "fallback"
    n3 = {"p4b_ms90_45-n3": row(None, level=z("p4b_ms90", 3))}
    assert p4b.decide(full(**off, **n3), REFS)["decisions"]["staircase"] == "n3"
    up = {"p4b_ms100-n3": row(z("p4b_ms100", 3) * 1.0101)}  # n 3 the default already: the staircase passes there
    assert p4b.decide(full(**off, **n3, **up), REFS)["decisions"]["staircase"] == "warn"
    worse = {"p4b_ms90_45-n3": row(None, level=z("p4b_ms90", 3) * 1.06)}
    assert p4b.decide(full(**off, **worse), REFS)["decisions"]["staircase"] == "refuse"
    blocked = {"p4b_ms90_45-n3": row(None, blocked=True)}  # its setup refused at n 3
    assert p4b.decide(full(**off, **blocked), REFS)["decisions"]["staircase"] == "refuse"
    assert p4b.decide(full(**{"p4b_ms90_45-n2": row(None, level=z("p4b_ms90") * 1.049)}), REFS)[
        "decisions"]["staircase"] == "warn"


def test_next_is_read_on_its_first_lobe_against_the_even_odd_model():  # B-3
    s = even_odd_s(58.9864, 3.5015, 45.1268, 3.0629, 60.0, F)  # the 90 ohm coupon's modes, 50 ohm ports
    assert p4b.next_peak(s, F, 0.6895e9) == (pytest.approx(-17.546, abs=1e-3), 685e6)


def test_stripline_fext_is_read_on_its_first_lobe_at_root_ze_zo():  # B-3; the launches' FEXT lies above it
    f_q = 2.99792458e8 / (4 * 60e-3 * math.sqrt(4.3))  # 0.602 GHz
    s = even_odd_s(56.0141, 4.3, 45.1337, 4.3, 60.0, F)  # the stripline's modes: sqrt(Ze Zo) 50.28 ohm
    assert p4b.fext_db(s, F, 50.0, 2 * f_q) == pytest.approx(-64.46, abs=0.01)
    assert p4b.fext_db(s, F, math.sqrt(56.0141 * 45.1337), 2 * f_q) <= -250.0  # none at its own reference
    late = s.copy()
    late[F > 5e9, 3, 0] = late[F > 5e9, 0, 3] = 0.1  # a launch's FEXT from 5 GHz up
    assert p4b.fext_db(late, F, 50.0, 2 * f_q) == pytest.approx(-64.46, abs=0.01) and p4b.fext_db(late, F, 50.0) > -21
    assert p4b.fext_db(even_odd_s(70.0, 4.3, 45.0, 4.3, 60.0, F), F, 50.0) == pytest.approx(-32.30, abs=0.01)


def test_the_victim_case_reads_the_pairs_own_block():  # B-5; Review Focus 3: 6 ports against 4
    vic = read(pair6(0.05, 0.02), F, P100, 3.0)
    cut = read(pair6()[:, :4, :4], F, {**P100, "lines": P100["lines"][:2]}, 3.0)
    v = p4b.victim(P100, vic, cut)
    assert [r["quantity"] for r in v["rows"]] == ["tdr_lowest", "tdr_highest", "sdd21", "sdd21", "sdd11_worst",
                                                  "scd21_worst", "skew"]  # the pair's rows: the cut has no victim
    assert v["ds_pair"] == 0.0 and (v["next_db"], v["fext_db"]) == (pytest.approx(-29.03, abs=0.01),
                                                                   pytest.approx(-36.99, abs=0.01))


def test_the_committed_references_hold_the_replicas_numbers():  # G-1; design 5.11: committed before any run
    refs = json.loads(p4b.REFERENCES.read_text(encoding="utf-8"))
    for c, (z2, z3) in {"p4b_ms90": (91.153, 90.711), "p4b_ms100": (100.271, 101.32),
                        "p4b_sl90": (91.71, 92.383)}.items():
        mesh = refs["coupons"][c]["fit2d"]
        assert (mesh["2"]["z0_mesh"], mesh["3"]["z0_mesh"]) == (pytest.approx(z2, abs=0.02), pytest.approx(z3, abs=0.02))
        assert all(m["z0_mesh"] == pytest.approx(2 * m["z_odd"], rel=1e-9) for m in mesh.values())  # Zdiff = 2 Zodd
    exact = refs["coupons"]["p4b_ms90"]["exact"]
    assert (exact["z_diff"], exact["next_db"]) == (pytest.approx(90.2537, abs=0.02), pytest.approx(-17.546, abs=0.01))
    assert refs["coupons"]["p4b_sl90"]["exact"]["fext50_db"] == pytest.approx(-64.46, abs=0.05)


def test_p4b_runs_its_steps_and_writes_its_report(gates):  # design 5.11: the tool on the network fake
    assert p4b.main(["--out", str(gates), "--steps", "p4b_ms90-n2,p4b_ms90-n3,p4b_ms90-n4"]) == 1  # no n 4 step
    with pytest.raises(SystemExit, match="never regenerated"):
        p4b.main(["--references"])
    assert p4b.main(["--out", str(gates)]) == 0
    text = (gates / "p4b" / "p4b.json").read_text(encoding="utf-8")
    result = json.loads(text)
    rows, verdict = result["rows"], result["verdict"]
    assert sorted(rows) == ["p4b_ms90-n2", "p4b_ms90-n3"] and rows["p4b_ms90-n3"]["n_ds"] == 0.0  # one S at both n
    assert verdict["value"] == "blocked" and verdict["fails"][0] == "p4b_ms90-n2: no reading"  # no differential step
    assert result["victim"] is None and '"reading"' not in text and '"project"' not in text
    assert (gates / "p4b" / "p4b.md").read_text(encoding="utf-8").startswith("## P4B-1 Checks")
