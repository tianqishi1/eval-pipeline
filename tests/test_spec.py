# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import pytest
from evalpipe.spec import load_suite, TaskSpec

ROOT = Path(__file__).resolve().parents[1]


def test_load_suites():
    assert len(load_suite(ROOT / "suites" / "coding_mini")) == 8
    probes = load_suite(ROOT / "suites" / "probes")
    assert len(probes) == 3
    assert {p.probe for p in probes} == {"ambiguity", "dep_missing", "hallucination"}


def test_bad_probe_rejected(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text("id: x\ninstruction: i\nfiles: {}\ntests: {}\noracle_files: {}\nprobe: nope\n",
                 encoding="utf-8")
    with pytest.raises(ValueError):
        TaskSpec.load(f)


def one(suite, tid):
    return next(t for t in load_suite(ROOT / "suites" / suite) if t.id == tid)
