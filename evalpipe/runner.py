"""运行器：隔离工作区 → 环境探针 → oracle 有效性校验 → Agent 提案 → 应用 → 单测 → 归因 → 复现脚本。"""
from __future__ import annotations
import datetime as dt
import uuid
from pathlib import Path
from .spec import TaskSpec
from .sandbox import (prepare_workspace, env_check, apply_solution, capture_patch,
                      run_tests, import_check, write_repro, TestReport, docker_available)
from .attribution import attribute
from .metrics import aggregate


def run_task(task: TaskSpec, adapter, root: Path, oracle_cache: dict, judge=None) -> dict:
    ws = prepare_workspace(task, root / "work")
    env = env_check(task, ws)
    if task.id not in oracle_cache:
        ows = prepare_workspace(task, root / "oracle")
        apply_solution(ows, task.oracle_files, None)
        oracle_cache[task.id] = run_tests(ows, task.timeout)
    oracle_tests = oracle_cache[task.id]
    agent = adapter.solve(task, ws)
    applied, apply_msg = apply_solution(ws, agent.files, agent.patch)
    if applied:
        import_ok, import_msg = import_check(ws, agent.files or {})
        tests = run_tests(ws, task.timeout)
        patch = capture_patch(ws)
    else:
        import_ok, import_msg = False, "solution not applied"
        tests = TestReport(ran=False, exit_code=None, passed=0, failed=0, errors=0,
                           total=0, output="", duration=0.0)
        patch = agent.patch or ""
    judge_label = judge.label(task) if judge else None
    attr = attribute(task, env, oracle_tests, applied, apply_msg, import_ok, import_msg,
                     tests, agent, judge_label=judge_label)
    repro_dir = root / "repro"
    repro_dir.mkdir(parents=True, exist_ok=True)
    repro = repro_dir / f"{task.id}.py"
    write_repro(ws, task, patch, repro)
    attr.repro = str(repro)
    return {
        "task_id": task.id, "suite": task.suite, "kind": task.kind, "probe": task.probe,
        "instruction": task.instruction.strip()[:300],
        "expected_fail": task.expected_fail, "tags": task.tags,
        "plan_ok": agent.plan_ok, "applied": applied, "import_ok": import_ok,
        "env": {"ok": env.ok, "missing_deps": env.missing_deps, "python": env.python},
        "tests": {"ran": tests.ran, "passed": tests.passed, "failed": tests.failed,
                  "errors": tests.errors, "total": tests.total, "exit_code": tests.exit_code},
        "attribution": {"cls": attr.cls, "sub": attr.sub, "step": attr.step,
                        "evidence": attr.evidence, "repro": attr.repro,
                        "needs_human": attr.needs_human},
        "patch": patch[:8000], "model_id": agent.model_id,
        "tokens": agent.tokens, "cost": agent.cost,
        "duration": round(tests.duration, 2),
        "transcript": agent.transcript[:3],
    }


def run_suite(tasks: list[TaskSpec], adapter, out_dir: Path, judge=None,
              use_docker: bool = False, split_part: str | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    oracle_cache: dict = {}
    results = [run_task(t, adapter, out_dir, oracle_cache, judge) for t in tasks]
    run = {
        "run_id": uuid.uuid4().hex[:10],
        "ts": dt.datetime.now().isoformat(timespec="seconds"),
        "adapter": adapter.name,
        "docker": bool(use_docker and docker_available()),
        "split_part": split_part,
        "suites": sorted({t.suite for t in tasks}),
        "metrics": aggregate(results),
        "results": results,
    }
    return run
