# SPDX-License-Identifier: Apache-2.0
"""HengERP 桥接适配器：把 ERP 黄金评测纳入 EvalPipe 统一归因/门禁/回流/看板。
适配器：baseline（生产配置）/ mutant:auto_confirm（L2 越权自动执行）/ mutant:tax_flag（含税口径错误）。
归因映射：runner/setup 错→环境；judge→模型/过程质量；budget→模型/预算；forbidden→模型/安全违规；其余断言→模型/逻辑。"""
from __future__ import annotations
import json
import os
import sys
import time
import uuid
from pathlib import Path
import yaml

DEFAULT_HENG_ROOT = os.environ.get("HENG_ROOT", r"D:\codex\heng-erp")


def _ensure_paths(heng_root: str):
    root = Path(heng_root)
    if not (root / "packages").exists():
        raise FileNotFoundError(f"HengERP repo not found: {root}")
    for sub in ["packages/contracts", "packages/kernel", "packages/semantic", "packages/actions",
                "packages/agent", "packages/llm", "packages/eval", "packages/evolution", "apps/api"]:
        p = str(root / sub)
        if p not in sys.path:
            sys.path.insert(0, p)
    return root


def load_tasks(heng_root: str) -> list[dict]:
    root = _ensure_paths(heng_root)
    tasks = []
    for f in sorted((root / "evals").rglob("*.yaml")):
        spec = yaml.safe_load(f.read_text(encoding="utf-8"))
        tasks.append({"id": spec["id"], "suite": "heng_erp", "spec": spec,
                      "path": str(f), "probe": None,
                      "instruction": spec.get("when", {}).get("utterance", spec.get("when", {}).get("action", ""))})
    return tasks


class HengBaselineAdapter:
    name = "heng:baseline"

    def __init__(self, heng_root: str = DEFAULT_HENG_ROOT):
        self.root = _ensure_paths(heng_root)

    def _provider(self):
        from heng_agent.providers import RuleBasedProvider
        return RuleBasedProvider()

    def _automation(self):
        return None

    def evaluate(self, task: dict) -> dict:
        from heng_eval.runner import run_scenario
        t0 = time.time()
        try:
            r = run_scenario(task["spec"], provider=self._provider(), automation=self._automation())
        except Exception as e:  # noqa: BLE001
            r = {"id": task["id"], "passed": False,
                 "failures": [f"runner error: {type(e).__name__}: {e}"], "tokens": 0}
        return _to_result(task, r, time.time() - t0, self.name, self.root)


class HengMutantAdapter(HengBaselineAdapter):
    """故意制造 ERP 回归，验证门禁能抓住（安全/口径两类）。"""
    def __init__(self, mode: str, heng_root: str = DEFAULT_HENG_ROOT):
        super().__init__(heng_root)
        self.mode = mode
        self.name = f"heng:mutant:{mode}"

    def _automation(self):
        if self.mode == "auto_confirm":
            return {"*": {"sales.order.create": {"level": "L2"}}}
        return None

    def _provider(self):
        from heng_agent.providers import RuleBasedProvider
        base = RuleBasedProvider()
        if self.mode != "tax_flag":
            return base

        class TaxFlagMutant(RuleBasedProvider):
            def plan(self, utterance, context):
                out = super().plan(utterance, context)
                for st in out["plan"].get("steps", []):
                    for ln in st.get("args", {}).get("lines", []):
                        ln["tax_included"] = False   # 故意忽略"含税"语义
                return out
        return TaxFlagMutant()


def _to_result(task: dict, r: dict, duration: float, model_id: str, root: Path) -> dict:
    failures = r.get("failures", [])
    passed = bool(r.get("passed"))
    if passed:
        attr = {"cls": "通过", "sub": "all_assertions_pass", "step": 0,
                "evidence": ["ERP 场景断言全部通过"], "needs_human": False}
    else:
        first = failures[0] if failures else "unknown"
        if any("forbidden" in f for f in failures):
            cls, sub, step = "模型", "安全违规(越权/自动执行)", 4
        elif first.startswith("runner error") or first.startswith("setup"):
            cls, sub, step = "环境", "评测环境/fixture 异常", 3
        elif first.startswith("judge"):
            cls, sub, step = "模型", "过程质量(judge 轨)", 4
        elif first.startswith("budget"):
            cls, sub, step = "模型", "预算超限", 4
        else:
            cls, sub, step = "模型", "逻辑或口径错误", 4
        attr = {"cls": cls, "sub": sub, "step": step, "evidence": failures[:4],
                "needs_human": False}
    repro_dir = root.parent / "eval-pipeline" / "runs" / "repro_heng"
    repro_dir.mkdir(parents=True, exist_ok=True)
    repro = repro_dir / f"{task['id']}.py"
    repro.write_text(
        "import sys, yaml\n"
        f"sys.path[:0] = {[str(root / s) for s in ['packages/contracts','packages/kernel','packages/semantic','packages/actions','packages/agent','packages/llm','packages/eval','packages/evolution']]!r}\n"
        "from heng_eval.runner import run_scenario\n"
        f"spec = yaml.safe_load(open({task['path']!r}, encoding='utf-8'))\n"
        "r = run_scenario(spec)\n"
        "print(r['passed'], r['failures'])\n"
        "sys.exit(0 if r['passed'] else 1)\n", encoding="utf-8")
    attr["repro"] = str(repro)
    return {
        "task_id": task["id"], "suite": task["suite"], "kind": "erp_scenario",
        "probe": task["probe"], "expected_fail": False, "tags": ["erp"],
        "instruction": task["instruction"][:300],
        "plan_ok": True, "applied": True, "import_ok": True,
        "env": {"ok": True, "missing_deps": [], "python": sys.version.split()[0]},
        "tests": {"ran": True, "passed": 1 if passed else 0, "failed": 0 if passed else 1,
                  "errors": 0, "total": 1, "exit_code": 0 if passed else 1},
        "attribution": attr, "patch": "", "model_id": model_id,
        "tokens": r.get("tokens", 0), "cost": 0.0, "duration": round(duration, 2),
        "transcript": [r.get("reply", "")[:200]],
    }


def run_heng_suite(heng_root: str, adapter, out_dir: Path) -> dict:
    from .metrics import aggregate
    tasks = load_tasks(heng_root)
    results = [adapter.evaluate(t) for t in tasks]
    import datetime as dt
    run = {"run_id": uuid.uuid4().hex[:10],
           "ts": dt.datetime.now().isoformat(timespec="seconds"),
           "adapter": adapter.name, "docker": False, "split_part": None,
           "suites": ["heng_erp"], "metrics": aggregate(results), "results": results}
    out_dir.mkdir(parents=True, exist_ok=True)
    return run


def feed_evolution(run: dict, heng_root: str, tenant_id: str = "t_demo") -> int:
    """模型类 badcase 自动注入 HengERP 进化中心案例池（闭环）。"""
    _ensure_paths(heng_root)
    from heng_kernel import db
    from heng_kernel.db import make_engine, make_session_factory, init_db
    from sqlalchemy import select
    url = os.environ.get("HENG_DB_URL", f"sqlite:///{Path(heng_root) / 'heng_dev.db'}")
    eng = make_engine(url)
    init_db(eng)
    sf = make_session_factory(eng)
    n = 0
    with sf() as s:
        for r in run["results"]:
            if r["attribution"]["cls"] not in ("模型", "上下文"):
                continue
            key = f'{r["task_id"]}: {r["attribution"]["sub"]}'
            dup = s.execute(select(db.EvolutionCase).where(
                db.EvolutionCase.tenant_id == tenant_id,
                db.EvolutionCase.utterance == key)).scalars().first()
            if dup:
                continue
            s.add(db.EvolutionCase(tenant_id=tenant_id, source="eval_backflow",
                                   utterance=key,
                                   detail={"attribution": r["attribution"],
                                           "repro": r["attribution"]["repro"],
                                           "run_id": run["run_id"]}))
            n += 1
        s.commit()
    return n
