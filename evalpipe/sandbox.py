"""隔离执行沙箱：临时工作区 + git 初始化/patch 应用 + 环境探针 + pytest 子进程 + 可选 Docker。
复现脚本自动生成（归因证据的一部分）。"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from .spec import TaskSpec

PY = sys.executable


@dataclass
class EnvReport:
    ok: bool
    python: str
    missing_deps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class TestReport:
    ran: bool
    exit_code: int | None
    passed: int
    failed: int
    errors: int
    total: int
    output: str
    duration: float


def run_cmd(args, cwd, timeout=120):
    t0 = time.time()
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT", time.time() - t0


def prepare_workspace(task: TaskSpec, root: Path) -> Path:
    ws = root / task.id
    ws.mkdir(parents=True, exist_ok=True)
    for name, content in task.files.items():
        f = ws / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    for name, content in task.tests.items():
        f = ws / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    if task.requirements:
        (ws / "requirements.txt").write_text("\n".join(task.requirements), encoding="utf-8")
    run_cmd(["git", "init", "-q"], ws)
    run_cmd(["git", "add", "-A"], ws)
    run_cmd(["git", "-c", "user.email=eval@local", "-c", "user.name=eval", "commit", "-qm", "base"], ws)
    return ws


def env_check(task: TaskSpec, ws: Path) -> EnvReport:
    missing = []
    for dep in task.requirements:
        mod = dep.split("==")[0].split(">=")[0].replace("-", "_")
        code, out, _ = run_cmd([PY, "-c", f"import {mod}"], ws, timeout=30)
        if code != 0:
            missing.append(dep)
    return EnvReport(ok=not missing, python=sys.version.split()[0], missing_deps=missing)


def apply_solution(ws: Path, files: dict | None, patch: str | None) -> tuple[bool, str]:
    if patch:
        pf = ws / "_agent.patch"
        pf.write_text(patch, encoding="utf-8")
        code, out, _ = run_cmd(["git", "apply", "--whitespace=nowarn", "_agent.patch"], ws)
        pf.unlink(missing_ok=True)
        return code == 0, out
    if files:
        for name, content in files.items():
            f = ws / name
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")
        return True, ""
    return False, "adapter returned no solution"


def capture_patch(ws: Path) -> str:
    run_cmd(["git", "add", "-A"], ws)
    code, out, _ = run_cmd(["git", "diff", "--cached"], ws)
    return out if code == 0 else ""


def run_tests(ws: Path, timeout: int) -> TestReport:
    junit = ws / "_junit.xml"
    t0 = time.time()
    code, out, dur = run_cmd([PY, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider",
                              f"--junitxml={junit.name}"], ws, timeout=timeout)
    passed = failed = errors = 0
    if junit.exists():
        import xml.etree.ElementTree as ET
        try:
            root = ET.parse(junit).getroot()
            suites = root.iter("testsuite")
            for s in suites:
                passed += int(s.get("tests", 0)) - int(s.get("failures", 0)) - int(s.get("errors", 0)) - int(s.get("skipped", 0))
                failed += int(s.get("failures", 0))
                errors += int(s.get("errors", 0))
        except ET.ParseError:
            pass
    total = passed + failed + errors
    return TestReport(ran=code != -1, exit_code=code, passed=passed, failed=failed,
                      errors=errors, total=total, output=out[-6000:], duration=dur)


def import_check(ws: Path, files: dict) -> tuple[bool, str]:
    mods = [Path(n).stem for n in (files or {}) if n.endswith(".py") and not n.startswith("test")]
    if not mods:
        return True, ""
    code, out, _ = run_cmd([PY, "-c", "import " + ", ".join(mods)], ws, timeout=30)
    return code == 0, out


def write_repro(ws: Path, task: TaskSpec, patch: str, dest: Path):
    """复现脚本：重建工作区→应用 patch→跑单测（归因证据链）。"""
    lines = ["# repro for " + task.id, "import subprocess, sys, pathlib, tempfile",
             "ws = pathlib.Path(tempfile.mkdtemp(prefix='repro_'))"]
    for name, content in {**task.files, **task.tests}.items():
        lines.append(f"(ws / {name!r}).parent.mkdir(parents=True, exist_ok=True)")
        lines.append(f"(ws / {name!r}).write_text({content!r}, encoding='utf-8')")
    if patch:
        lines.append(f"(ws / '_agent.patch').write_text({patch!r}, encoding='utf-8')")
        lines.append("subprocess.run(['git','apply','_agent.patch'], cwd=ws)")
    lines.append("r = subprocess.run([sys.executable,'-m','pytest','-q'], cwd=ws)")
    lines.append("sys.exit(r.returncode)")
    dest.write_text("\n".join(lines), encoding="utf-8")


def docker_available() -> bool:
    code, _, _ = run_cmd(["docker", "version", "--format", "{{.ServerVersion}}"], Path("."), timeout=10)
    return code == 0


def docker_command(task: TaskSpec, ws: Path) -> list[str]:
    """容器隔离复现命令（M1 提供命令生成；--docker 执行在环境具备时启用）。"""
    return ["docker", "run", "--rm", "--network=none", "-v", f"{ws}:/work", "-w", "/work",
            "python:3.12-slim", "sh", "-c", "pip install -q pytest && python -m pytest -q"]
