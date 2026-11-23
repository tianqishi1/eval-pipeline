"""归因引擎（图片§4 固定顺序）：1指令 → 2单测/预期 → 3环境 → 4Agent(规划/工具/幻觉/逻辑) → 5上下文。
每个归因带证据与复现脚本；fail-closed：证据不足时归到最保守类别并标注待人工。"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from .spec import TaskSpec
from .sandbox import EnvReport, TestReport
from .adapters import AgentResult

CLASSES = ("通过", "题坏", "环境", "模型", "上下文")


@dataclass
class Attribution:
    cls: str
    sub: str
    step: int
    evidence: list[str] = field(default_factory=list)
    repro: str = ""
    needs_human: bool = False


def _hallucinated_symbol(import_msg: str, task: TaskSpec, ws_files: dict) -> str | None:
    m = re.search(r"No module named '([\w\.]+)'", import_msg or "")
    if m:
        mod = m.group(1).split(".")[0]
        known = {r.split("==")[0].split(">=")[0].replace("-", "_") for r in task.requirements}
        known |= {n.split("/")[0].replace(".py", "") for n in ws_files}
        known |= {"pytest", "json", "os", "sys", "math", "re", "pathlib", "typing", "collections"}
        if mod not in known:
            return mod
    m = re.search(r"has no attribute '(\w+)'", import_msg or "")
    if m:
        return m.group(1)
    return None


def attribute(task: TaskSpec, env: EnvReport, oracle_tests: TestReport | None,
              applied: bool, apply_msg: str, import_ok: bool, import_msg: str,
              tests: TestReport | None, agent: AgentResult,
              judge_label: str | None = None) -> Attribution:
    passed = bool(tests and tests.ran and tests.failed == 0 and tests.errors == 0
                  and tests.total > 0 and applied and import_ok)
    if passed:
        return Attribution("通过", "all_tests_pass", 0,
                           [f"pytest {tests.passed}/{tests.total} passed"])
    ev: list[str] = []
    # 1 指令本身
    if task.probe == "ambiguity" or judge_label == "instruction":
        return Attribution("题坏", "指令歧义/需求矛盾", 1,
                           ["探针标签: ambiguity", "指令摘录: " + task.instruction.strip()[:120],
                            "单测编码了其中一种解释，指令未消歧"])
    # 2 单测/预期答案（以环境健康为前提：环境坏时 oracle 失败不构成题坏证据）
    if env.ok and oracle_tests is not None and (oracle_tests.failed or oracle_tests.errors):
        return Attribution("题坏", "测试或预期答案错误", 2,
                           [f"oracle 参考解也未通过: {oracle_tests.failed} fail / {oracle_tests.errors} error",
                            oracle_tests.output[-400:]])
    # 3 环境
    if not env.ok:
        return Attribution("环境", "依赖缺失/版本/网络", 3,
                           [f"missing deps: {env.missing_deps}", f"python {env.python}"])
    # 4 Agent
    if not agent.plan_ok:
        return Attribution("模型", "规划失败/未理解指令", 4,
                           ["adapter 未产出有效计划"] + agent.transcript[:2])
    if not applied:
        return Attribution("模型", "工具调用失败(patch 无法应用)", 4,
                           [apply_msg[-400:] or "git apply failed"])
    if not import_ok:
        sym = _hallucinated_symbol(import_msg, task, task.files)
        if sym or task.probe == "hallucination":
            return Attribution("模型", "代码生成幻觉", 4,
                               [f"引用不存在的符号/模块: {sym or '(probe)'}", import_msg[-400:]])
        return Attribution("模型", "代码无法运行", 4, [import_msg[-400:]])
    # 5 多轮上下文
    if agent.truncated:
        return Attribution("上下文", "上下文截断/prompt 缺陷", 5,
                           agent.transcript[:2] or ["transcript 标记截断"])
    if tests is None or not tests.ran:
        return Attribution("环境", "测试运行器异常", 3, ["pytest 未正常执行"], needs_human=True)
    return Attribution("模型", "逻辑错误(单测未过)", 4,
                       [f"pytest {tests.failed} fail / {tests.errors} error", tests.output[-400:]])
