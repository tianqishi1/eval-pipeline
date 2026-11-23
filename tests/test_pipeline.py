# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import pytest
from evalpipe.spec import load_suite
from evalpipe.adapters import OracleAdapter, MutantAdapter
from evalpipe.runner import run_suite
from evalpipe.gate import compare
from evalpipe.backflow import route
from evalpipe.report import write_all
from evalpipe import m2
from test_spec import ROOT, one


@pytest.fixture(scope="module")
def oracle_run(tmp_path_factory):
    return run_suite(load_suite(ROOT / "suites" / "coding_mini"), OracleAdapter(),
                     tmp_path_factory.mktemp("oracle"))


def test_oracle_all_pass(oracle_run):
    assert oracle_run["metrics"]["pass_rate"] == 1.0
    assert oracle_run["metrics"]["unit_test_pass_rate"] == 1.0


def test_mutant_logic_attributed_model(tmp_path):
    tasks = [one("coding_mini", "two-sum-001"), one("coding_mini", "money-round-003")]
    run = run_suite(tasks, MutantAdapter("logic"), tmp_path)
    assert run["metrics"]["pass_rate"] == 0.0
    assert all(r["attribution"]["cls"] == "模型" and "逻辑" in r["attribution"]["sub"]
               for r in run["results"])
    assert all(Path(r["attribution"]["repro"]).exists() for r in run["results"])


def test_mutant_tool_plan_context(tmp_path):
    t = [one("coding_mini", "two-sum-001")]
    for mode, sub in [("tool", "工具调用"), ("plan", "规划"), ("context", None)]:
        run = run_suite(t, MutantAdapter(mode), tmp_path / mode)
        a = run["results"][0]["attribution"]
        if mode == "context":
            assert a["cls"] == "上下文"
        else:
            assert sub in a["sub"]


def test_probes_attribution(tmp_path):
    probes = load_suite(ROOT / "suites" / "probes")
    amb = next(p for p in probes if p.probe == "ambiguity")
    hal = next(p for p in probes if p.probe == "hallucination")
    dep = next(p for p in probes if p.probe == "dep_missing")
    r1 = run_suite([amb], MutantAdapter("logic"), tmp_path / "a")["results"][0]["attribution"]
    r2 = run_suite([hal], MutantAdapter("hallucination"), tmp_path / "h")["results"][0]["attribution"]
    r3 = run_suite([dep], OracleAdapter(), tmp_path / "d")["results"][0]["attribution"]
    assert r1["cls"] == "题坏" and r1["step"] == 1
    assert r2["cls"] == "模型" and "幻觉" in r2["sub"]
    assert r3["cls"] == "环境" and "numpy" in r3["evidence"][0]


def test_gate_blocks_regression(oracle_run, tmp_path):
    mutant = run_suite(load_suite(ROOT / "suites" / "coding_mini"), MutantAdapter("logic"), tmp_path)
    res = compare(mutant, oracle_run)
    assert not res["ok"] and res["violations"]
    assert compare(oracle_run, oracle_run)["ok"]


def test_backflow_routing(oracle_run, tmp_path):
    mutant = run_suite([one("coding_mini", "two-sum-001")], MutantAdapter("logic"), tmp_path / "m")
    counts = route(mutant, tmp_path / "bf")
    assert counts["模型"] == 1
    lines = (tmp_path / "bf" / "heng_evolution_export.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[0])["source"] == "eval_backflow"


def test_report_files(oracle_run, tmp_path):
    write_all(oracle_run, tmp_path / "rep", [oracle_run])
    for n in ("report.json", "report.md", "dashboard.html"):
        assert (tmp_path / "rep" / n).exists()
    assert "归因分布" in (tmp_path / "rep" / "dashboard.html").read_text(encoding="utf-8")


def test_m2_hooks(oracle_run, tmp_path):
    ids = [r["task_id"] for r in oracle_run["results"]]
    s1 = m2.rotate_holdout(ids, 42)
    s2 = m2.rotate_holdout(ids, 42)
    assert s1 == s2 and set(s1["dev"]) | set(s1["holdout"]) == set(ids)
    assert not (set(s1["dev"]) & set(s1["holdout"]))
    n = m2.calibration_sheet(oracle_run, tmp_path / "cal.csv")
    assert n == 0  # oracle 全通过，无 badcase 需校准
    d = m2.drift(oracle_run, oracle_run)
    assert d["psi"] == 0 and not d["flag"]
    props = m2.shadow_proposals([one("coding_mini", "two-sum-001")], OracleAdapter())
    assert props[0]["files"]
