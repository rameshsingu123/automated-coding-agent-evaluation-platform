"""Command-line entry points for local deterministic evaluation experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .adapters import DeterministicBaselineAdapter
from .leaderboard import render_leaderboard
from .models import EvaluationCase
from .orchestrator import AdapterBinding, evaluate
from .report import format_run_report
from .tracking import ExperimentTracker


def _load_experiment(path: Path) -> tuple[str, str, str, list[EvaluationCase], list[AdapterBinding]]:
    with path.open(encoding="utf-8") as source:
        payload: Any = json.load(source)
    if not isinstance(payload, dict):
        raise ValueError("Experiment file must contain a JSON object")
    try:
        experiment_id = payload["experiment_id"]
        experiment_name = payload["name"]
        description = payload.get("description", "")
        raw_cases = payload["cases"]
        raw_adapters = payload["adapters"]
    except KeyError as exc:
        raise ValueError(f"Missing required experiment field: {exc.args[0]}") from exc
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ValueError("experiment_id must be a non-empty string")
    if not isinstance(experiment_name, str) or not experiment_name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(description, str):
        raise ValueError("description must be a string")
    if not isinstance(raw_cases, list) or not isinstance(raw_adapters, list):
        raise ValueError("cases and adapters must be JSON arrays")
    cases = []
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise ValueError(f"cases[{index}] must be a JSON object")
        try:
            cases.append(EvaluationCase(
                case_id=raw["case_id"], prompt=raw["prompt"],
                expected_output=raw["expected_output"], weight=raw.get("weight", 1.0),
            ))
        except KeyError as exc:
            raise ValueError(f"cases[{index}] is missing {exc.args[0]!r}") from exc
    adapters = []
    for index, raw in enumerate(raw_adapters):
        if not isinstance(raw, dict):
            raise ValueError(f"adapters[{index}] must be a JSON object")
        if raw.get("type") != "deterministic_baseline":
            raise ValueError(f"adapters[{index}] type must be 'deterministic_baseline'")
        try:
            adapter_name = raw["name"]
        except KeyError as exc:
            raise ValueError(f"adapters[{index}] is missing 'name'") from exc
        responses = raw.get("responses", {})
        if not isinstance(responses, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in responses.items()
        ):
            raise ValueError(f"adapters[{index}].responses must map strings to strings")
        if not isinstance(adapter_name, str) or not adapter_name.strip():
            raise ValueError(f"adapters[{index}].name must be a non-empty string")
        adapters.append(AdapterBinding(adapter_name, DeterministicBaselineAdapter(responses)))
    return experiment_id, experiment_name, description, cases, adapters


def run_experiment_file(path: Path, db_path: Path) -> str:
    experiment_id, name, description, cases, adapters = _load_experiment(path)
    tracker = ExperimentTracker(db_path)
    tracker.register_experiment(experiment_id, name, description)
    run = evaluate(experiment_id, cases, adapters)
    tracker.record_run(run)
    baseline = tracker.previous_scores(run.run_id)
    return format_run_report(run, baseline)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eval-platform", description="Deterministic coding-agent evaluation demo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run a JSON experiment")
    run_parser.add_argument("experiment", type=Path, help="experiment JSON file")
    run_parser.add_argument("--db", type=Path, default=Path("eval_platform.sqlite3"), help="SQLite database path")

    demo_parser = subparsers.add_parser("demo", help="run the bundled sample experiment")
    demo_parser.add_argument("--db", type=Path, default=Path("eval_platform.sqlite3"), help="SQLite database path")

    board_parser = subparsers.add_parser("leaderboard", help="show the latest leaderboard for an experiment")
    board_parser.add_argument("experiment_id")
    board_parser.add_argument("--db", type=Path, default=Path("eval_platform.sqlite3"))

    report_parser = subparsers.add_parser("report", help="show a stored run and compare with its predecessor")
    report_parser.add_argument("run_id")
    report_parser.add_argument("--db", type=Path, default=Path("eval_platform.sqlite3"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            print(run_experiment_file(args.experiment, args.db))
        elif args.command == "demo":
            sample = Path(__file__).resolve().parents[2] / "examples" / "experiment_sample.json"
            print(run_experiment_file(sample, args.db))
        elif args.command == "leaderboard":
            print(render_leaderboard(ExperimentTracker(args.db).leaderboard(args.experiment_id)))
        else:
            tracker = ExperimentTracker(args.db)
            run = tracker.load_run(args.run_id)
            print(format_run_report(run, tracker.previous_scores(args.run_id)))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
