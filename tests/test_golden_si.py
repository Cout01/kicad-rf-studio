# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os

import golden_s5
import golden_si
import golden_v1
import pytest

GOLDEN = json.loads(golden_si.GOLDEN.read_text(encoding="utf-8"))
SHARED = json.loads(golden_s5.GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def now(tmp_path_factory):
    home = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("golden_si"))  # relative paths only, as golden_v1's
    try:
        return golden_si.digests()
    finally:
        os.chdir(home)


@pytest.fixture(scope="module")
def shared(tmp_path_factory):
    home = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("shared"))  # relative paths only, as `now`
    try:
        return golden_s5.shared_si()
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


def test_the_si_fixtures_shared_outputs_stand_as_they_were_at_a87bcc1(shared):  # plan 3 ruling 2
    pins = SHARED["si"]
    assert set(shared["cases"]) == set(golden_si.CASES) and set(shared["run"]) == {"usb2_hs"}
    assert all({"load", "cost", "csx", "fingerprint"} <= set(c) for c in shared["cases"].values())
    assert shared["cases"] == pins["cases"]
    if golden_v1.env() != SHARED["env"]:
        pytest.skip("the run pins compare only on the env that recorded them (golden_v1.env())")
    assert shared["run"] == pins["run"]  # SI's results/ files and lines included
