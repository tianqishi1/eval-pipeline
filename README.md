# EvalPipe — attribution-first evaluation pipeline for coding / agent systems

[![eval-gate](https://github.com/tianqishi1/eval-pipeline/actions/workflows/eval-gate.yml/badge.svg)](https://github.com/tianqishi1/eval-pipeline/actions/workflows/eval-gate.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

English | [简体中文](README_CN.md)

**Attribution before metrics.** EvalPipe runs task suites in isolated sandboxes,
asserts on both outcomes and evidence (dual-track), attributes every failure to a
cause class, flows bad cases back into the suite, and gates regressions in CI.

> **Ecosystem**: evaluation eval-pipeline · foundation [agent-base](https://github.com/tianqishi1/agent-base) · skills [marketing-skills-cn](https://github.com/tianqishi1/marketing-skills-cn) · evaluated apps [heng-erp](https://github.com/tianqishi1/heng-erp) / [afterpilot](https://github.com/tianqishi1/afterpilot)

## Why

Most agent evals stop at a pass rate. A pass rate tells you *that* something
regressed, not *why*. EvalPipe makes the failure cause a first-class artifact:

- **Dual-track assertions** — outcome checks + evidence checks (files, diffs, traces).
- **Isolated reproduction** — every task runs in a sandbox; runs are replayable.
- **Attribution** — failures are classified (logic / hallucination / tool / plan / context) with evidence.
- **Badcase backflow** — verified failures become candidate regression cases.
- **CI gate** — `evalpipe gate` exits 1 when metrics drop against a pinned baseline.
- **Judge calibration** — agreement + Cohen's kappa against human labels before trusting an LLM judge.

## Quickstart

```bash
git clone https://github.com/tianqishi1/eval-pipeline.git && cd eval-pipeline
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python -m pytest                                    # offline self-tests
python -m evalpipe run suites/coding_mini --adapter oracle --out runs/oracle
python -m evalpipe run suites/coding_mini --adapter mutant:logic --out runs/mutant_logic
python -m evalpipe gate runs/mutant_logic/report.json --baseline runs/oracle/report.json  # exit 1 = blocked
python -m evalpipe backflow runs/mutant_logic/report.json --out runs/mutant_logic/backflow
python scripts/demo_eval.py                         # full-chain demo
```

Dashboard: `runs/<run>/dashboard.html` (metric cards / attribution breakdown / per-case evidence / history).

## Adapters

- `oracle` — reference-solution baseline + task validity checks
- `mutant:logic|hallucination|tool|plan|context` — deliberately failing agents to exercise attribution
- `llm` — any OpenAI-compatible model (`EVAL_LLM_BASE_URL` / `EVAL_LLM_KEY` / `EVAL_LLM_MODEL`)
- `cli:["codex","exec",...]` — external coding-agent protocol (changes captured via git diff)

## Holdout & judge calibration

```bash
python -m evalpipe rotate suites/coding_mini --seed 42 --out split.json   # rotating holdout
python -m evalpipe run suites/coding_mini --split split.json --part dev   # dev partition only
python -m evalpipe calibrate runs/mutant_logic/report.json --out cal.csv  # calibration sheet
python -m evalpipe calibrate x --labels cal_filled.csv                    # agreement + kappa
python -m evalpipe drift runs/oracle/report.json runs/mutant_logic/report.json
```

## Evaluate a business agent (ERP example)

```bash
python -m evalpipe heng --adapter baseline --out runs/heng_baseline --feed-evolution
python -m evalpipe heng --adapter mutant:auto_confirm --out runs/heng_mutant_auto
python -m evalpipe gate runs/heng_mutant_auto/report.json --baseline baselines/heng_erp_baseline.json
python -m evalpipe watch-heng --interval 3600        # resident patrol loop
```

## Layout

`evalpipe/` (spec, sandbox, adapters, attribution, metrics, runner, report, backflow, gate, CLI) ·
`suites/coding_mini` (8 tasks) · `suites/probes` (3 injected-failure probes) · `runs/` · `docs/` · `tests/`

## Contributing

Apache-2.0. See [CONTRIBUTING.md](CONTRIBUTING.md) (DCO sign-off + gate evidence),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md).
