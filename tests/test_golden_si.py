# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os

import golden_si
import golden_v1
import pytest

GOLDEN = json.loads(golden_si.GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def now(tmp_path_factory):
    home = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("golden_si"))  # relative paths only, as golden_v1's
    try:
        return golden_si.digests()
    finally:
        os.chdir(home)


def test_the_si_fixtures_build_byte_for_byte_what_they_did_at_plan_2(now):  # Stage 4 design 5.11
    assert set(now["models"]) == set(golden_si.CASES)
    assert now["models"] == GOLDEN["models"]  # an SI project, its new lines, model spec, hash or a blocking gate moved


def test_the_si_2d_tables_are_byte_for_byte_what_they_were_at_plan_2(now):  # cost's output before plan 3's
    assert set(now["outputs"]) == set(golden_si.CASES)
    if golden_v1.env() != GOLDEN["env"]:
        pytest.skip("the 2D table pins compare only on the env that recorded them (golden_v1.env())")
    assert now["outputs"] == GOLDEN["outputs"]
