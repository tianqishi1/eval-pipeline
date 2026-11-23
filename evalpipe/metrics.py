# SPDX-License-Identifier: Apache-2.0
"""指标聚合（图片§2 + 系统性补充）：理解/可运行/单测通过率/工具成功率 + 归因分布 + 成本时延 + 探针验证。"""
from __future__ import annotations
from collections import Counter


def aggregate(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {"total": 0}
    passed = sum(1 for r in results if r["attribution"]["cls"] == "通过")
    ran = [r for r in results if r["tests"]["ran"]]
    tp = sum(r["tests"]["passed"] for r in ran)
    tt = sum(r["tests"]["total"] for r in ran)
    tool_ok = sum(1 for r in results if r["applied"] and r["tests"]["ran"])
    plan_ok = sum(1 for r in results if r["plan_ok"])
    run_ok = sum(1 for r in results if r["applied"] and r["import_ok"])
    attr = Counter(f'{r["attribution"]["cls"]}/{r["attribution"]["sub"]}' for r in results)
    probes = [r for r in results if r["probe"]]
    probe_verified = sum(1 for r in probes if r["attribution"]["cls"] != "通过"
                         and not r["attribution"]["needs_human"])
    return {
        "total": n,
        "passed": passed,
        "pass_rate": round(passed / n, 4),
        "instruction_understanding_rate": round(plan_ok / n, 4),
        "runnability_rate": round(run_ok / n, 4),
        "unit_test_pass_rate": round(tp / tt, 4) if tt else 0.0,
        "tool_success_rate": round(tool_ok / n, 4),
        "tests_passed": tp, "tests_total": tt,
        "attribution_distribution": dict(attr),
        "probes_total": len(probes), "probes_verified": probe_verified,
        "avg_duration_s": round(sum(r["duration"] for r in results) / n, 2),
        "tokens": sum(r["tokens"] for r in results),
        "cost": round(sum(r["cost"] for r in results), 4),
    }
