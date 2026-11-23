"""M2 考虑项（已做成可运行钩子，非纸面规划）：
- 轮换保留集（防应试进化/防过拟合评测）
- judge 校准表 + 一致性/kappa 计算
- 跨运行漂移监控（PSI + 通过率差）
- 影子模式提案接口（不生效，只对比）
- LLM judge 钩子（指令歧义判定，可选启用）"""
from __future__ import annotations
import csv
import math
import random
import tempfile
from collections import Counter
from pathlib import Path


def rotate_holdout(ids: list[str], seed: int, frac: float = 0.3) -> dict:
    rnd = random.Random(seed)
    shuffled = list(ids)
    rnd.shuffle(shuffled)
    k = max(1, int(len(shuffled) * frac))
    return {"seed": seed, "holdout": sorted(shuffled[:k]), "dev": sorted(shuffled[k:])}


def filter_tasks(tasks, split: dict, part: str):
    ids = set(split.get(part, []))
    return [t for t in tasks if t.id in ids]


def calibration_sheet(run: dict, path: Path, sample_n: int = 20):
    rows = [r for r in run["results"] if r["attribution"]["cls"] != "通过"][:sample_n]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "auto_cls", "auto_sub", "human_cls", "human_sub", "evidence"])
        for r in rows:
            a = r["attribution"]
            w.writerow([r["task_id"], a["cls"], a["sub"], "", "", "；".join(a["evidence"])[:200]])
    return len(rows)


def agreement(csv_path: Path) -> dict:
    pairs = []
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("human_cls"):
                pairs.append((row["auto_cls"], row["human_cls"]))
    if not pairs:
        return {"n": 0, "agreement": None, "kappa": None}
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    cats = set(ca) | set(cb)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    return {"n": n, "agreement": round(po, 4), "kappa": round(kappa, 4)}


def _dist(run: dict) -> Counter:
    return Counter(r["attribution"]["cls"] for r in run["results"])


def psi(a: Counter, b: Counter, eps: float = 1e-6) -> float:
    na, nb = sum(a.values()) or 1, sum(b.values()) or 1
    cats = set(a) | set(b)
    return sum(((a[c] / na) - (b[c] / nb)) * math.log((a[c] / na + eps) / (b[c] / nb + eps)) for c in cats)


def drift(run_a: dict, run_b: dict) -> dict:
    da, db = _dist(run_a), _dist(run_b)
    p = psi(da, db)
    dpass = run_b["metrics"]["pass_rate"] - run_a["metrics"]["pass_rate"]
    return {"psi": round(p, 4), "pass_rate_delta": round(dpass, 4),
            "flag": bool(p > 0.2 or abs(dpass) > 0.05),
            "dist_a": dict(da), "dist_b": dict(db)}


def shadow_proposals(tasks, adapter) -> list[dict]:
    """影子模式：只取提案不执行（与生产/人工并行对比用，M2 接 ERP 影子 runner）。"""
    out = []
    for t in tasks:
        ws = Path(tempfile.mkdtemp(prefix="shadow_"))
        r = adapter.solve(t, ws)
        out.append({"task_id": t.id, "files": r.files, "patch": r.patch,
                    "plan_ok": r.plan_ok, "model_id": r.model_id})
    return out


class LLMJudge:
    """指令歧义 judge（归因第 1 步的可插拔增强；默认启发式=探针标签）。"""
    def __init__(self, base_url=None, api_key=None, model=None):
        import os
        self.base_url = (base_url or os.environ.get("EVAL_LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("EVAL_LLM_API_KEY", "")
        self.model = model or os.environ.get("EVAL_LLM_MODEL", "qwen-max")

    def available(self):
        return bool(self.base_url and self.api_key)

    def label(self, task) -> str | None:
        if not self.available():
            return None
        import httpx
        try:
            r = httpx.post(f"{self.base_url}/chat/completions",
                           headers={"Authorization": f"Bearer {self.api_key}"},
                           json={"model": self.model, "temperature": 0,
                                 "messages": [{"role": "system",
                                               "content": "判断指令是否歧义或自相矛盾。只回答 instruction 或 ok。"},
                                              {"role": "user", "content": task.instruction}]},
                           timeout=30)
            txt = r.json()["choices"][0]["message"]["content"].strip().lower()
            return "instruction" if "instruction" in txt else "ok"
        except Exception:  # noqa: BLE001
            return None
