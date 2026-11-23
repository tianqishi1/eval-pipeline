# 衡评 EvalPipe — Coding/Agent 评测流水线

归因先于指标 · 双轨断言 · 隔离复现 · badcase 回流 · 回归门禁 · M2 钩子就绪。
设计文档：docs/评测流水线设计.md（含图片四要素映射与系统性补充）。

## 快速开始

```powershell
cd D:\codex\eval-pipeline
uv venv .venv --python 3.12
uv pip install -e . --python .venv\Scripts\python.exe
.venv\Scripts\python.exe -m pytest                                  # 流水线自测
.venv\Scripts\python.exe -m evalpipe run suites/coding_mini --adapter oracle --out runs/oracle
.venv\Scripts\python.exe -m evalpipe run suites/coding_mini --adapter mutant:logic --out runs/mutant_logic
.venv\Scripts\python.exe -m evalpipe run suites/probes --adapter mutant:hallucination --out runs/probes_injected
.venv\Scripts\python.exe -m evalpipe gate runs/mutant_logic/report.json --baseline runs/oracle/report.json   #  exit 1 = 阻断
.venv\Scripts\python.exe -m evalpipe backflow runs/mutant_logic/report.json --out runs/mutant_logic/backflow
.venv\Scripts\python.exe scripts\demo_eval.py                        # 一键全链路演示
```

看板：runs/<run>/dashboard.html（指标卡 / 归因分布 / 明细证据 / 历史趋势）。

## 适配器

- `oracle`：参考解基线 + 题目有效性校验
- `mutant:logic|hallucination|tool|plan|context`：故意失败，练归因
- `llm`：OpenAI 兼容模型（EVAL_LLM_BASE_URL/KEY/MODEL）
- `cli:["codex","exec",...]`：外部 Coding Agent 协议（git diff 捕获改动）

## M2 钩子

```powershell
python -m evalpipe rotate suites/coding_mini --seed 42 --out split.json   # 轮换保留集
python -m evalpipe run suites/coding_mini --split split.json --part dev   # 只跑 dev
python -m evalpipe calibrate runs/mutant_logic/report.json --out cal.csv  # judge 校准表
python -m evalpipe calibrate x --labels cal_filled.csv                    # 一致率+kappa
python -m evalpipe drift runs/oracle/report.json runs/mutant_logic/report.json
```

## 目录

evalpipe/（spec sandbox adapters attribution metrics runner report backflow gate m2 CLI）
suites/coding_mini（8 任务）· suites/probes（3 故意失败探针）· runs/（产物）· docs/ · tests/
