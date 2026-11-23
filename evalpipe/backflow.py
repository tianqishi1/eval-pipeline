# SPDX-License-Identifier: Apache-2.0
"""Badcase 回流（图片§2）：区分 题坏/环境/模型，路由到数据集修订/环境修复/模型回归集；
并提供 HengERP 进化案例池导出格式（模型类 badcase → 进化中心）。"""
from __future__ import annotations
import json
from pathlib import Path


def write_badcases(run: dict, path: Path):
    with path.open("w", encoding="utf-8") as f:
        for r in run["results"]:
            if r["attribution"]["cls"] != "通过":
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


def route(run: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = {"题坏": [], "环境": [], "模型": [], "上下文": []}
    for r in run["results"]:
        c = r["attribution"]["cls"]
        if c in groups:
            groups[c].append(r)
    ds = ["# 数据集修订清单（题坏）", ""]
    for r in groups["题坏"]:
        ds.append(f"- {r['task_id']}: {r['attribution']['sub']}；证据: {'；'.join(r['attribution']['evidence'])[:200]}")
    (out_dir / "dataset_issues.md").write_text("\n".join(ds) or "# 无\n", encoding="utf-8")
    ev = ["# 环境修复清单（环境）", ""]
    for r in groups["环境"]:
        ev.append(f"- {r['task_id']}: missing={r['env']['missing_deps']} python={r['env']['python']}")
    (out_dir / "env_fixes.md").write_text("\n".join(ev) or "# 无\n", encoding="utf-8")
    with (out_dir / "model_cases.jsonl").open("w", encoding="utf-8") as f:
        for r in groups["模型"] + groups["上下文"]:
            f.write(json.dumps({"task_id": r["task_id"], "attribution": r["attribution"],
                                "patch": r["patch"], "repro": r["attribution"]["repro"]},
                               ensure_ascii=False) + "\n")
    with (out_dir / "heng_evolution_export.jsonl").open("w", encoding="utf-8") as f:
        for r in groups["模型"] + groups["上下文"]:
            f.write(json.dumps({"source": "eval_backflow", "utterance": r["task_id"],
                                "detail": {"attribution": r["attribution"]["sub"],
                                           "repro": r["attribution"]["repro"],
                                           "suite": r["suite"]}}, ensure_ascii=False) + "\n")
    return {k: len(v) for k, v in groups.items()}
