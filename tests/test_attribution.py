from pathlib import Path
from evalpipe.spec import TaskSpec
from evalpipe.sandbox import EnvReport, TestReport
from evalpipe.adapters import AgentResult
from evalpipe.attribution import attribute

TASK = TaskSpec(id="t", suite="s", kind="implement", instruction="do it",
                files={"solution.py": ""}, tests={"test_x.py": ""}, oracle_files={"solution.py": ""})
OK_ENV = EnvReport(ok=True, python="3.12")
OK_TESTS = TestReport(ran=True, exit_code=0, passed=2, failed=0, errors=0, total=2, output="", duration=1)
BAD_TESTS = TestReport(ran=True, exit_code=1, passed=1, failed=1, errors=0, total=2, output="assert", duration=1)
AGENT = AgentResult(files={"solution.py": "x=1"})


def attr(**kw):
    base = dict(task=TASK, env=OK_ENV, oracle_tests=OK_TESTS, applied=True, apply_msg="",
                import_ok=True, import_msg="", tests=OK_TESTS, agent=AGENT)
    base.update(kw)
    return attribute(**base)


def test_pass():
    assert attr().cls == "通过"


def test_step1_instruction():
    t = TaskSpec(**{**TASK.__dict__, "probe": "ambiguity"})
    assert attr(task=t, tests=BAD_TESTS).cls == "题坏"
    assert attr(task=t, tests=BAD_TESTS).step == 1


def test_step2_bad_tests():
    a = attr(oracle_tests=BAD_TESTS, tests=BAD_TESTS)
    assert a.cls == "题坏" and a.step == 2


def test_step3_env():
    a = attr(env=EnvReport(ok=False, python="3.12", missing_deps=["numpy"]), tests=BAD_TESTS)
    assert a.cls == "环境" and a.step == 3


def test_step4_plan():
    a = attr(agent=AgentResult(plan_ok=False), tests=BAD_TESTS)
    assert a.cls == "模型" and "规划" in a.sub


def test_step4_tool():
    a = attr(applied=False, apply_msg="error: patch failed", tests=BAD_TESTS)
    assert "工具调用" in a.sub


def test_step4_hallucination():
    a = attr(import_ok=False, import_msg="ModuleNotFoundError: No module named 'phantom_x'",
             tests=BAD_TESTS)
    assert a.cls == "模型" and "幻觉" in a.sub


def test_step5_context():
    a = attr(agent=AgentResult(files={"solution.py": "x"}, truncated=True), tests=BAD_TESTS)
    assert a.cls == "上下文" and a.step == 5


def test_step4_logic():
    a = attr(tests=BAD_TESTS)
    assert a.cls == "模型" and "逻辑" in a.sub
