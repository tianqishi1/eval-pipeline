# 衡评 EvalPipe — Coding/Agent 评测流水线

[![eval-gate](https://github.com/tianqishi1/eval-pipeline/actions/workflows/eval-gate.yml/badge.svg)](https://github.com/tianqishi1/eval-pipeline/actions/workflows/eval-gate.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](README.md) | 简体中文

> **生态**：评测 eval-pipeline · 底座 [agent-base](https://github.com/tianqishi1/agent-base) · 技能生态 [marketing-skills-cn](https://github.com/tianqishi1/marketing-skills-cn) · 评测对象示例 [heng-erp](https://github.com/tianqishi1/heng-erp) / [afterpilot](https://github.com/tianqishi1/afterpilot)

归因先于指标 · 双轨断言 · 隔离复现 · badcase 回流 · 回归门禁 · M2 钩子就绪。
设计文档：docs/评测流水线设计.md（含图片四要素映射与系统性补充）。

## 快速开始

```bash
git clone https://github.com/tianqishi1/eval-pipeline.git && cd eval-pipeline
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python -m pytest                                    # 流水线自测（离线）
python -m evalpipe run suites/coding_mini --adapter oracle --out runs/oracle
python -m evalpipe run suites/coding_mini --adapter mutant:logic --out runs/mutant_logic
python -m evalpipe run suites/probes --adapter mutant:hallucination --out runs/probes_injected
python -m evalpipe gate runs/mutant_logic/report.json --baseline runs/oracle/report.json   # exit 1 = 阻断
python -m evalpipe backflow runs/mutant_logic/report.json --out runs/mutant_logic/backflow
python scripts/demo_eval.py                         # 一键全链路演示
```

看板：runs/<run>/dashboard.html（指标卡 / 归因分布 / 明细证据 / 历史趋势）。

## 适配器

- `oracle`：参考解基线 + 题目有效性校验
- `mutant:logic|hallucination|tool|plan|context`：故意失败，练归因
- `llm`：OpenAI 兼容模型（EVAL_LLM_BASE_URL/KEY/MODEL）
- `cli:["codex","exec",...]`：外部 Coding Agent 协议（git diff 捕获改动）

## M2 钩子

```bash
python -m evalpipe rotate suites/coding_mini --seed 42 --out split.json   # 轮换保留集
python -m evalpipe run suites/coding_mini --split split.json --part dev   # 只跑 dev
python -m evalpipe calibrate runs/mutant_logic/report.json --out cal.csv  # judge 校准表
python -m evalpipe calibrate x --labels cal_filled.csv                    # 一致率+kappa
python -m evalpipe drift runs/oracle/report.json runs/mutant_logic/report.json
```

## 目录

evalpipe/（spec sandbox adapters attribution metrics runner report backflow gate m2 CLI）
suites/coding_mini（8 任务）· suites/probes（3 故意失败探针）· runs/（产物）· docs/ · tests/

## 自动评测 ERP（已接通）

```bash
python -m evalpipe heng --adapter baseline --out runs/heng_baseline --feed-evolution
python -m evalpipe heng --adapter mutant:auto_confirm --out runs/heng_mutant_auto   # 安全变异体
python -m evalpipe gate runs/heng_mutant_auto/report.json --baseline baselines/heng_erp_baseline.json
python -m evalpipe watch-heng --interval 3600        # 常驻巡检循环
# Windows 单轮巡检（可挂任务计划程序）: powershell -NoProfile -File scripts/auto_eval.ps1
```

## 许可与贡献
- 许可：**Apache-2.0**（见 LICENSE）
- 贡献：[CONTRIBUTING.md](CONTRIBUTING.md)（DCO sign-off + 门禁证据）· [行为准则](CODE_OF_CONDUCT.md) · [安全政策](SECURITY.md)
- 设计文档：[docs/评测流水线设计.md](docs/评测流水线设计.md)（含图片方法论映射、系统性补充、M2 钩子、自动化三方式）
- 业务 Agent 评测对象示例：[heng-erp](https://github.com/tianqishi1/heng-erp)（LGPL-3.0）
