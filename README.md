# Automated Coding Agent Evaluation Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A compact, local-first Python project for repeatable coding-agent evaluation experiments. It defines an adapter boundary, evaluates cases concurrently, scores outputs deterministically, stores run history in SQLite, and renders leaderboards and regression comparisons. The bundled adapter is a **deterministic baseline** that returns configured strings; no model, network, or commercial API is called.

**Validated with deterministic baselines; these are not commercial AI model results.**

**Independent portfolio project, public on GitHub. Not deployed enterprise or customer system.**

Author: **Ramesh Singu** · [GitHub](https://github.com/rameshsingu123)

## Quick start

Requires Python 3.10 or newer. The runtime uses only the Python standard library. Install the package and optional test dependency:

```bash
python -m pip install -e '.[dev]'
pytest
```

Run the bundled deterministic experiment (SQLite defaults to `eval_platform.sqlite3` in the current directory):

```bash
python -m eval_platform demo --db /tmp/coding-agent-evals.sqlite3
```

Run a custom experiment, then query or report on saved data:

```bash
python -m eval_platform run examples/experiment_sample.json --db /tmp/coding-agent-evals.sqlite3
python -m eval_platform leaderboard sample-coding-tasks --db /tmp/coding-agent-evals.sqlite3
python -m eval_platform report RUN_ID --db /tmp/coding-agent-evals.sqlite3
```

The `run` and `demo` commands print the run ID, leaderboard, and comparison with the preceding run of that experiment when one exists. Re-running the demo intentionally inserts a new run, allowing its report to show a measured change (or no change) against the prior deterministic run.

## Architecture

```text
JSON experiment
      |
      v
Experiment loader ----> Adapter Protocol ----> Deterministic baseline
      |                         |                         |
      +-------------------------+-------------------------+
                                v
                  Concurrent orchestrator
                  (stable result collection;
                   isolated per-case errors)
                                |
                     Weighted exact scoring
                        /             \
                       v               v
              SQLite tracker       Run report
                 |                    |
                 +----> Leaderboard <-+
                        Regression
                        comparison
```

The orchestrator submits adapter/case pairs to a thread pool. Completion timing does not affect result ordering: outcomes are emitted in adapter declaration order and then case declaration order. A raised adapter exception or non-string result becomes an error outcome for that case, and other jobs continue.

## Experiment format

See [`examples/experiment_sample.json`](examples/experiment_sample.json). An experiment declares a stable `experiment_id`, descriptive metadata, cases (`case_id`, `prompt`, `expected_output`, and optional positive numeric `weight`), and named adapters. This implementation currently accepts `type: "deterministic_baseline"`; each adapter maps case IDs to literal string responses. Unspecified cases use an empty-string response. Extend the `AgentAdapter` Protocol to connect a separately authorized implementation, while keeping credentials and secrets out of experiment JSON.

## Weighted scoring

For each case, the baseline metric is exact match after normalizing line endings and stripping whitespace at the two ends; internal whitespace remains significant. A successful match earns that case's configured weight, while a mismatch or failed adapter call earns zero. The reported score is:

```text
score = sum(weights for matching cases) / sum(weights for all cases)
```

All case weights must be finite and strictly positive, case IDs must be unique, and each adapter must have exactly one outcome per case. Errors remain in the denominator, so failures cannot inflate a score by disappearing from a run. Scores are fractions from `0.0` to `1.0`; leaderboard display formats them as percentages. This is deliberately a transparent baseline metric, not a claim that one exact-match metric captures all code quality.

## SQLite experiment tracking

The tracker creates four explicit tables: `experiments`, `runs`, `evaluations`, and `scores`, with foreign keys, primary keys, score/weight checks, and an index for locating recent experiment runs. Each run's metadata, case-level outcomes, and aggregate scores are inserted in a single transaction. Duplicate run or case keys fail rather than silently replacing history. Connections use a busy timeout and enforce foreign keys. The database is local and file-backed; avoid placing credentials in it or in experiment prompts.

## Leaderboards and regression reporting

A leaderboard is scoped to a run (by default, the latest completed run for the requested experiment). It ranks descending by weighted score, then alphabetically by adapter name for deterministic ties. Reports compare adapters by name with the immediately preceding run in the same experiment: decreases are marked `REGRESSION`, increases `IMPROVEMENT`, unchanged values `UNCHANGED`, and new or absent adapters are called out explicitly. This is a simple score-delta report; it does not assert statistical significance.

### Illustrative leaderboard layout

The bundled sample has three cases with weights 1, 2, and 1. Its configured baseline answers match all expected outputs; the second configured baseline misses the final case. The output from `demo` therefore has this deterministic shape:

```text
Rank  Adapter                 Score    Cases        Weight
----  ----------------------  -------  -------  ------------
   1  baseline_reference     100.0%    3/3        4.00/4.00
   2  baseline_variant        75.0%    2/3        3.00/4.00
```

These values are derived directly from the sample's literal responses and scoring formula; they are not measurements of commercial AI systems.

## Development and scope

Run the test suite with `pytest`. The tests cover weighted scoring/validation, transactional SQLite persistence, leaderboard retrieval, and regression history. Runtime dependencies are standard-library only; pytest is a development extra.

The project is intentionally a small portfolio demonstration. It does not ship with an external model adapter, sandboxed code execution, a web service, authentication, or enterprise deployment features. Add those only with an explicit threat model and the necessary isolation and operational controls.
