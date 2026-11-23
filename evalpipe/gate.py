# SPDX-License-Identifier: Apache-2.0
"""CI 回归门禁：对比基线。通过率下降/模型类回归/新增题坏 → 阻断；探针任务豁免（其失败是设计目的）。"""
from __future__ import annotations


def compare(run: dict, baseline: dict, eps: float = 0.02) -> dict:
    violations = []
    m, b = run["metrics"], baseline["metrics"]
    if m["pass_rate"] < b["pass_rate"] - eps:
        violations.append(f"通过率下降: {b['pass_rate']:.1%} → {m['pass_rate']:.1%} (eps={eps})")
    base_pass = {r["task_id"] for r in baseline["results"] if r["attribution"]["cls"] == "通过"}
    for r in run["results"]:
        if r["probe"]:
            continue
        if r["task_id"] in base_pass and r["attribution"]["cls"] in ("模型", "上下文"):
            violations.append(f"回归: {r['task_id']} 基线通过 → {r['attribution']['cls']}/{r['attribution']['sub']}")
        if r["attribution"]["cls"] == "题坏":
            violations.append(f"数据集问题需先修订: {r['task_id']} ({r['attribution']['sub']})")
    return {"ok": not violations, "violations": violations,
            "pass_rate": m["pass_rate"], "baseline_pass_rate": b["pass_rate"]}
