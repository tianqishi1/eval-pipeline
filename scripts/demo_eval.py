# SPDX-License-Identifier: Apache-2.0
"""一键全链路演示：python scripts/demo_eval.py"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def cli(*args):
    print("\n$ evalpipe", " ".join(args))
    p = subprocess.run([PY, "-m", "evalpipe", *args], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    print(p.stdout.strip()[:1500])
    return p.returncode


cli("run", "suites/coding_mini", "--adapter", "oracle", "--out", "runs/demo_oracle")
cli("run", "suites/coding_mini", "--adapter", "mutant:logic", "--out", "runs/demo_mutant")
cli("run", "suites/probes", "--adapter", "mutant:hallucination", "--out", "runs/demo_probes")
code = cli("gate", "runs/demo_mutant/report.json", "--baseline", "runs/demo_oracle/report.json")
print("门禁 exit =", code, "(1=阻断回归, 符合预期)")
cli("backflow", "runs/demo_mutant/report.json", "--out", "runs/demo_mutant/backflow")
cli("rotate", "suites/coding_mini", "--seed", "42", "--out", "runs/demo_split.json")
cli("calibrate", "runs/demo_mutant/report.json", "--out", "runs/demo_cal.csv")
cli("drift", "runs/demo_oracle/report.json", "runs/demo_mutant/report.json")
print("\n看板: runs/demo_mutant/dashboard.html  设计文档: docs/评测流水线设计.md")
