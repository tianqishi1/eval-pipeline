"""CLI: python -m evalpipe <run|report|backflow|gate|rotate|calibrate|drift> ..."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .spec import load_suite
from .adapters import OracleAdapter, MutantAdapter, LLMPatchAdapter, CLIAdapter
from .runner import run_suite
from .report import write_all
from .backflow import write_badcases, route
from .gate import compare
from . import m2


def _adapter(spec: str):
    if spec == "oracle":
        return OracleAdapter()
    if spec.startswith("mutant:"):
        return MutantAdapter(spec.split(":", 1)[1])
    if spec == "llm":
        a = LLMPatchAdapter()
        if not a.available():
            sys.exit("llm 适配器需配置 EVAL_LLM_BASE_URL / EVAL_LLM_API_KEY")
        return a
    if spec.startswith("cli:"):
        return CLIAdapter(json.loads(spec[4:]), name="cli")
    sys.exit(f"unknown adapter: {spec}")


def _history(runs_dir: Path) -> list[dict]:
    out = []
    for f in sorted(runs_dir.glob("*/report.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    return sorted(out, key=lambda r: r["ts"])


def main():
    ap = argparse.ArgumentParser(prog="evalpipe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("suite"); r.add_argument("--adapter", default="oracle")
    r.add_argument("--out", default=None); r.add_argument("--split", default=None)
    r.add_argument("--part", default="dev"); r.add_argument("--docker", action="store_true")
    r.add_argument("--judge", action="store_true")
    rp = sub.add_parser("report"); rp.add_argument("run_json"); rp.add_argument("--out", default=None)
    bf = sub.add_parser("backflow"); bf.add_argument("run_json"); bf.add_argument("--out", default=None)
    g = sub.add_parser("gate"); g.add_argument("run_json"); g.add_argument("--baseline", required=True)
    g.add_argument("--eps", type=float, default=0.02)
    ro = sub.add_parser("rotate"); ro.add_argument("suite"); ro.add_argument("--seed", type=int, default=42)
    ro.add_argument("--frac", type=float, default=0.3); ro.add_argument("--out", default="split.json")
    ca = sub.add_parser("calibrate"); ca.add_argument("run_json"); ca.add_argument("--out", default="calibration.csv")
    ca.add_argument("--labels", default=None)
    dr = sub.add_parser("drift"); dr.add_argument("a"); dr.add_argument("b")
    args = ap.parse_args()

    if args.cmd == "run":
        tasks = load_suite(args.suite)
        part = None
        if args.split:
            split = json.loads(Path(args.split).read_text(encoding="utf-8"))
            tasks = m2.filter_tasks(tasks, split, args.part)
            part = args.part
        out = Path(args.out or f"runs/{args.adapter.replace(':', '_')}")
        judge = m2.LLMJudge() if args.judge else None
        run = run_suite(tasks, _adapter(args.adapter), out, judge=judge,
                        use_docker=args.docker, split_part=part)
        write_all(run, out, _history(out.parent))
        write_badcases(run, out / "badcases.jsonl")
        m = run["metrics"]
        print(f"run {run['run_id']}  adapter={run['adapter']}  tasks={m['total']}  "
              f"pass={m['pass_rate']:.1%}  unit={m['unit_test_pass_rate']:.1%}  "
              f"probes={m['probes_verified']}/{m['probes_total']}")
        print(f"report: {out/'report.md'}  dashboard: {out/'dashboard.html'}")
    elif args.cmd == "report":
        run = json.loads(Path(args.run_json).read_text(encoding="utf-8"))
        out = Path(args.out or Path(args.run_json).parent)
        write_all(run, out, _history(out.parent))
        print(f"dashboard: {out/'dashboard.html'}")
    elif args.cmd == "backflow":
        run = json.loads(Path(args.run_json).read_text(encoding="utf-8"))
        out = Path(args.out or Path(args.run_json).parent / "backflow")
        counts = route(run, out)
        print("backflow routed:", counts, "->", out)
    elif args.cmd == "gate":
        run = json.loads(Path(args.run_json).read_text(encoding="utf-8"))
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        res = compare(run, base, args.eps)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(0 if res["ok"] else 1)
    elif args.cmd == "rotate":
        tasks = load_suite(args.suite)
        split = m2.rotate_holdout([t.id for t in tasks], args.seed, args.frac)
        Path(args.out).write_text(json.dumps(split, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"split: dev={len(split['dev'])} holdout={len(split['holdout'])} -> {args.out}")
    elif args.cmd == "calibrate":
        if args.labels:
            print(json.dumps(m2.agreement(Path(args.labels)), ensure_ascii=False))
        else:
            run = json.loads(Path(args.run_json).read_text(encoding="utf-8"))
            n = m2.calibration_sheet(run, Path(args.out))
            print(f"calibration sheet: {n} rows -> {args.out}（人工填写 human_cls 后用 --labels 计算一致性）")
    elif args.cmd == "drift":
        a = json.loads(Path(args.a).read_text(encoding="utf-8"))
        b = json.loads(Path(args.b).read_text(encoding="utf-8"))
        print(json.dumps(m2.drift(a, b), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
