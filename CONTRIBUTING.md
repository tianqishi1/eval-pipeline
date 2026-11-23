# 贡献指南（EvalPipe）

归因先于指标的评测流水线。欢迎新任务集、新适配器、归因规则与 M2 钩子完善。

## 快速开始
```powershell
git clone https://github.com/tianqishi1/eval-pipeline.git
cd eval-pipeline
uv venv .venv --python 3.12
uv pip install -e . --python .venv\Scripts\python.exe
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m evalpipe run suites/coding_mini --adapter oracle --out runs/dev
```

## 贡献流程
Fork → 分支 → `git commit -s`（DCO）→ PR（附运行报告/归因证据）→ CI 门禁 → review。

## 硬性规则
- 新任务必须含：指令 / 初始文件 / 隐藏单测 / oracle 参考解（用于 test-the-tests）；
- 新失败模式请做成**探针或变异适配器**，并补归因单测（固定顺序：指令→单测→环境→Agent→上下文）；
- 不得用 LLM judge 裁决对错；judge 只评过程且需校准；
- 门禁/基线变更需说明统计理由（eps/逐任务回归/保留集轮换）。

## 好的第一个贡献
- 导入 SWE-bench lite / Aider polyglot 子集的转换适配器；
- 新语言任务集（JUnit/Go test  runner）；
- 看板可视化改进；漂移/校准报表完善。

## 许可
Apache-2.0（见 LICENSE）；贡献按 Apache-2.0 第 5 条自动授权。
