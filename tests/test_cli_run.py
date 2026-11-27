# SPDX-License-Identifier: Apache-2.0
"""Regression: CLI `run` path must work (guards against local-import shadowing bugs)."""
import json
import subprocess
import sys
from pathlib import Path


def test_cli_run_probes(tmp_path):
    out = tmp_path / "run"
    p = subprocess.run(
        [sys.executable, "-m", "evalpipe", "run", "suites/probes",
         "--adapter", "mutant:hallucination", "--out", str(out)],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr[-2000:]
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["metrics"]["probes_total"] == 3
    assert (out / "badcases.jsonl").exists()