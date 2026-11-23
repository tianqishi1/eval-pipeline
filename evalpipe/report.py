# SPDX-License-Identifier: Apache-2.0
"""报告三件套：JSON（机器）/ Markdown（人读）/ HTML 看板（趋势+归因分布+明细）。"""
from __future__ import annotations
import json
from pathlib import Path

CLS_COLOR = {"通过": "#1e8e3e", "题坏": "#b26a00", "环境": "#7b1fa2", "模型": "#c5221f", "上下文": "#1a56b0"}


def write_json(run: dict, path: Path):
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(run: dict, path: Path):
    m = run["metrics"]
    lines = [f"# 评测报告 {run['run_id']}", f"- 时间: {run['ts']}  适配器: {run['adapter']}  容器: {run['docker']}",
             f"- 任务数: {m['total']}  通过: {m['passed']}  通过率: {m['pass_rate']:.1%}",
             f"- 指令理解率: {m['instruction_understanding_rate']:.1%}  可运行率: {m['runnability_rate']:.1%}",
             f"- 单测通过率: {m['unit_test_pass_rate']:.1%} ({m['tests_passed']}/{m['tests_total']})  工具成功率: {m['tool_success_rate']:.1%}",
             f"- 探针验证: {m['probes_verified']}/{m['probes_total']}  平均耗时: {m['avg_duration_s']}s  tokens: {m['tokens']}",
             "", "## 归因分布", ""]
    for k, v in sorted(m["attribution_distribution"].items(), key=lambda x: -x[1]):
        lines.append(f"- {k}: {v}")
    lines += ["", "## 明细", "", "| 任务 | 归因 | 单测 | 探针 | 复现 |", "|---|---|---|---|---|"]
    for r in run["results"]:
        a = r["attribution"]
        lines.append(f"| {r['task_id']} | {a['cls']}/{a['sub']} | {r['tests']['passed']}/{r['tests']['total']} | "
                     f"{r['probe'] or '-'} | {Path(a['repro']).name} |")
    lines += ["", "## Badcase 证据（非通过）", ""]
    for r in run["results"]:
        if r["attribution"]["cls"] != "通过":
            lines.append(f"### {r['task_id']} → {r['attribution']['cls']}/{r['attribution']['sub']}（排查第 {r['attribution']['step']} 步）")
            lines += [f"- {e}" for e in r["attribution"]["evidence"]]
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_dashboard(run: dict, history: list[dict], path: Path):
    m = run["metrics"]
    cards = "".join(
        f'<div class="card"><div class="v">{v}</div><div class="k">{k}</div></div>'
        for k, v in [("通过率", f"{m['pass_rate']:.0%}"), ("单测通过率", f"{m['unit_test_pass_rate']:.0%}"),
                     ("指令理解", f"{m['instruction_understanding_rate']:.0%}"), ("可运行", f"{m['runnability_rate']:.0%}"),
                     ("工具成功", f"{m['tool_success_rate']:.0%}"), ("探针验证", f"{m['probes_verified']}/{m['probes_total']}")])
    dist = m["attribution_distribution"]
    mx = max(dist.values()) if dist else 1
    bars = "".join(
        f'<div class="row"><span class="lbl">{k}</span><div class="bar" style="width:{int(v/mx*100)}%;background:{CLS_COLOR.get(k.split("/")[0],"#888")}"></div><span>{v}</span></div>'
        for k, v in sorted(dist.items(), key=lambda x: -x[1]))
    rows = "".join(
        f'<tr><td>{r["task_id"]}</td><td><span class="tag" style="background:{CLS_COLOR.get(r["attribution"]["cls"],"#888")}">{r["attribution"]["cls"]}</span> {r["attribution"]["sub"]}</td>'
        f'<td>{r["tests"]["passed"]}/{r["tests"]["total"]}</td><td>{r["probe"] or "-"}</td><td>{r["duration"]}s</td>'
        f'<td class="ev">{"；".join(r["attribution"]["evidence"])[:160]}</td></tr>'
        for r in run["results"])
    trend = "".join(
        f'<tr><td>{h["ts"]}</td><td>{h["adapter"]}</td><td>{h["metrics"]["pass_rate"]:.0%}</td>'
        f'<td>{h["metrics"]["unit_test_pass_rate"]:.0%}</td><td>{h["metrics"]["total"]}</td></tr>'
        for h in history[-12:])
    html = f"""<!doctype html><html lang=zh><head><meta charset=utf-8><title>EvalPipe 看板 {run['run_id']}</title>
<style>body{{font-family:system-ui,'Microsoft YaHei',sans-serif;margin:0;background:#f3f5f8;color:#222}}
header{{background:#1a2b4a;color:#fff;padding:14px 24px}}main{{padding:20px 24px;max-width:1100px}}
.cards{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:18px}}
.card{{background:#fff;border-radius:8px;padding:14px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.card .v{{font-size:24px;font-weight:700;color:#1a2b4a}}.card .k{{font-size:12px;color:#888;margin-top:4px}}
.panel{{background:#fff;border-radius:8px;padding:16px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
h2{{font-size:15px;margin:0 0 12px;color:#1a2b4a}}
.row{{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px}}.lbl{{width:220px}}
.bar{{height:14px;border-radius:3px;min-width:2px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}td,th{{border-bottom:1px solid #eee;padding:7px 6px;text-align:left}}
th{{background:#fafbfc;color:#666}}.tag{{color:#fff;border-radius:4px;padding:2px 8px;font-size:12px}}
.ev{{color:#888;font-size:12px;max-width:340px}}</style></head><body>
<header><b>衡评 EvalPipe</b> · 运行 {run['run_id']} · {run['ts']} · 适配器 {run['adapter']} · 容器隔离 {'是' if run['docker'] else '否(本地沙箱)'}</header>
<main><div class=cards>{cards}</div>
<div class=panel><h2>归因分布（固定顺序排查：指令→单测→环境→Agent→上下文）</h2>{bars}</div>
<div class=panel><h2>任务明细</h2><table><tr><th>任务</th><th>归因</th><th>单测</th><th>探针</th><th>耗时</th><th>证据</th></tr>{rows}</table></div>
<div class=panel><h2>历史趋势</h2><table><tr><th>时间</th><th>适配器</th><th>通过率</th><th>单测通过率</th><th>任务数</th></tr>{trend}</table></div>
</main></body></html>"""
    path.write_text(html, encoding="utf-8")


def write_all(run: dict, out_dir: Path, history: list[dict] | None = None):
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(run, out_dir / "report.json")
    write_markdown(run, out_dir / "report.md")
    write_dashboard(run, history or [run], out_dir / "dashboard.html")
