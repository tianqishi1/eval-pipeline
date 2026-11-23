# SPDX-License-Identifier: Apache-2.0
"""任务/套件规格（SWE-bench lite 风格精简版）：指令 + 初始文件 + 隐藏单测 + oracle + 探针标签。"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

KINDS = ("implement", "bugfix")
PROBES = ("ambiguity", "dep_missing", "hallucination")


@dataclass
class TaskSpec:
    id: str
    suite: str
    kind: str
    instruction: str
    files: dict[str, str]
    tests: dict[str, str]
    oracle_files: dict[str, str]
    mutant_files: dict[str, str] = field(default_factory=dict)
    requirements: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    probe: str | None = None
    expected_fail: bool = False   # 探针任务：预期失败，用于验证归因链路
    timeout: int = 60

    @staticmethod
    def load(path: Path) -> "TaskSpec":
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        for k in ("id", "instruction", "files", "tests", "oracle_files"):
            if k not in d:
                raise ValueError(f"{path.name}: missing field {k}")
        if d.get("kind", "implement") not in KINDS:
            raise ValueError(f"{path.name}: bad kind")
        if d.get("probe") and d["probe"] not in PROBES:
            raise ValueError(f"{path.name}: bad probe")
        return TaskSpec(id=d["id"], suite=d.get("suite", path.parent.name),
                        kind=d.get("kind", "implement"), instruction=d["instruction"],
                        files=d["files"], tests=d["tests"], oracle_files=d["oracle_files"],
                        mutant_files=d.get("mutant_files", {}),
                        requirements=d.get("requirements", []), tags=d.get("tags", []),
                        probe=d.get("probe"), expected_fail=bool(d.get("expected_fail", False)),
                        timeout=int(d.get("timeout", 60)))


def load_suite(path: str | Path) -> list[TaskSpec]:
    p = Path(path)
    files = sorted((p / "tasks").glob("*.yaml")) if (p / "tasks").exists() else sorted(p.glob("*.yaml"))
    return [TaskSpec.load(f) for f in files]
