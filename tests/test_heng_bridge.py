import os
from pathlib import Path
import pytest
from evalpipe.heng_bridge import (HengBaselineAdapter, HengMutantAdapter,
                                  run_heng_suite, load_tasks, DEFAULT_HENG_ROOT)

HENG = Path(DEFAULT_HENG_ROOT)
pytestmark = pytest.mark.skipif(not (HENG / "packages").exists(), reason="HengERP repo not present")


def test_erp_baseline_all_pass(tmp_path):
    run = run_heng_suite(str(HENG), HengBaselineAdapter(str(HENG)), tmp_path)
    assert run["metrics"]["total"] == 17
    assert run["metrics"]["pass_rate"] == 1.0


def test_erp_safety_mutant_caught(tmp_path):
    run = run_heng_suite(str(HENG), HengMutantAdapter("auto_confirm", str(HENG)), tmp_path)
    bad = [r for r in run["results"] if r["attribution"]["cls"] != "通过"]
    assert len(bad) == 2
    assert all("安全违规" in r["attribution"]["sub"] for r in bad)
    assert all(Path(r["attribution"]["repro"]).exists() for r in bad)
