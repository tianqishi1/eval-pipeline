# SPDX-License-Identifier: Apache-2.0
"""Agent 适配器：oracle(基线 sanity) / mutant(故意失败，练归因) / llm(可选) / cli(Codex/Claude Code/Qoder 协议)。
统一输出 AgentResult；任何适配器都只产出"提案"，由沙箱裁决。"""
from __future__ import annotations
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from .spec import TaskSpec


@dataclass
class AgentResult:
    files: dict | None = None
    patch: str | None = None
    plan_ok: bool = True
    transcript: list = field(default_factory=list)
    tokens: int = 0
    cost: float = 0.0
    tool_calls: list = field(default_factory=list)   # {name, ok}
    truncated: bool = False
    model_id: str = ""


class OracleAdapter:
    """参考解：用于验证题目/单测本身有效（归因第 2 步），也作基线。"""
    name = "oracle"

    def solve(self, task: TaskSpec, ws: Path) -> AgentResult:
        return AgentResult(files=dict(task.oracle_files), model_id="oracle",
                           tool_calls=[{"name": "write_files", "ok": True}])


class MutantAdapter:
    """故意制造失败（图片§1：题目歧义/环境依赖缺失/模型幻觉 + 规划/工具/上下文）。"""
    def __init__(self, mode: str):
        self.mode = mode
        self.name = f"mutant:{mode}"

    def solve(self, task: TaskSpec, ws: Path) -> AgentResult:
        base = dict(task.mutant_files or task.oracle_files)
        if self.mode == "logic":
            return AgentResult(files=base, model_id=self.name,
                               tool_calls=[{"name": "write_files", "ok": True}])
        if self.mode == "hallucination":
            files = dict(base)
            first = next(iter(files))
            files[first] = "import phantom_accelerator  # 幻觉：不存在的依赖\n" + files[first]
            return AgentResult(files=files, model_id=self.name,
                               tool_calls=[{"name": "write_files", "ok": True}])
        if self.mode == "tool":
            return AgentResult(patch="this is not a valid unified diff\n", model_id=self.name,
                               tool_calls=[{"name": "git_apply", "ok": False}])
        if self.mode == "plan":
            return AgentResult(files=None, plan_ok=False, model_id=self.name,
                               transcript=["无法理解指令，未产出计划"])
        if self.mode == "context":
            return AgentResult(files=base, truncated=True, model_id=self.name,
                               transcript=["[context truncated at turn 3]"])
        raise ValueError(self.mode)


class LLMPatchAdapter:
    """OpenAI 兼容模型：产出整文件 JSON 提案（配 EVAL_LLM_BASE_URL/KEY 启用）。"""
    def __init__(self, base_url=None, api_key=None, model=None):
        self.base_url = (base_url or os.environ.get("EVAL_LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("EVAL_LLM_API_KEY", "")
        self.model = model or os.environ.get("EVAL_LLM_MODEL", "qwen-max")
        self.name = f"llm:{self.model}"

    def available(self):
        return bool(self.base_url and self.api_key)

    def solve(self, task: TaskSpec, ws: Path) -> AgentResult:
        import httpx
        listing = "\n".join(f"--- {n} ---\n{c}" for n, c in task.files.items())
        sys = ("你是代码 Agent。只输出 JSON：{\"files\": {路径: 完整新内容}}。"
               "不要引用不存在的模块；满足指令与隐藏单测。")
        try:
            r = httpx.post(f"{self.base_url}/chat/completions",
                           headers={"Authorization": f"Bearer {self.api_key}"},
                           json={"model": self.model, "temperature": 0,
                                 "response_format": {"type": "json_object"},
                                 "messages": [{"role": "system", "content": sys},
                                              {"role": "user", "content": task.instruction + "\n\n" + listing}]},
                           timeout=120)
            r.raise_for_status()
            j = r.json()
            files = json.loads(j["choices"][0]["message"]["content"]).get("files")
            usage = j.get("usage", {})
            return AgentResult(files=files, plan_ok=bool(files), model_id=self.name,
                               tokens=usage.get("total_tokens", 0),
                               tool_calls=[{"name": "llm_call", "ok": True}])
        except Exception as e:  # noqa: BLE001
            return AgentResult(plan_ok=False, model_id=self.name,
                               transcript=[f"llm error: {e}"],
                               tool_calls=[{"name": "llm_call", "ok": False}])


class CLIAdapter:
    """外部 Coding Agent（Codex/Claude Code/Qoder）协议：
    在隔离工作区写入 INSTRUCTION.md → 运行命令 → 用 git diff 捕获其改动作为 patch。
    command 例: ["codex","exec","--cd","{ws}","{instruction}"]"""
    def __init__(self, command: list[str], name: str = "cli"):
        self.command = command
        self.name = name

    def solve(self, task: TaskSpec, ws: Path) -> AgentResult:
        (ws / "INSTRUCTION.md").write_text(task.instruction, encoding="utf-8")
        cmd = [c.replace("{ws}", str(ws)).replace("{instruction}", task.instruction)
               for c in self.command]
        try:
            p = subprocess.run(cmd, cwd=ws, capture_output=True, text=True, timeout=task.timeout * 5)
            ok = p.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return AgentResult(plan_ok=False, model_id=self.name, transcript=[str(e)],
                               tool_calls=[{"name": "cli_run", "ok": False}])
        from .sandbox import capture_patch
        patch = capture_patch(ws)
        return AgentResult(patch=patch or None, plan_ok=ok and bool(patch), model_id=self.name,
                           transcript=[(p.stdout or "")[-2000:], (p.stderr or "")[-2000:]],
                           tool_calls=[{"name": "cli_run", "ok": ok}])
