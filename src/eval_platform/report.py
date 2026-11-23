"""Human-readable run and regression reports."""

from __future__ import annotations

from typing import Iterable

from .leaderboard import render_leaderboard
from .models import AdapterScore, EvaluationRun


def regression_lines(
    current: Iterable[AdapterScore], baseline: Iterable[AdapterScore]
) -> list[str]:
    """Describe score changes against a prior run, matching adapters by name."""
    current_by_name = {score.adapter_name: score for score in current}
    baseline_by_name = {score.adapter_name: score for score in baseline}
    lines: list[str] = []
    for name in sorted(current_by_name, key=str.casefold):
        now = current_by_name[name]
        before = baseline_by_name.get(name)
        if before is None:
            lines.append(f"- {name}: new adapter; current score {now.score:.1%} (no baseline).")
            continue
        delta = now.score - before.score
        if delta < 0:
            status = "REGRESSION"
        elif delta > 0:
            status = "IMPROVEMENT"
        else:
            status = "UNCHANGED"
        lines.append(
            f"- {name}: {status}; {before.score:.1%} -> {now.score:.1%} ({delta:+.1%})."
        )
    for name in sorted(set(baseline_by_name) - set(current_by_name), key=str.casefold):
        lines.append(f"- {name}: absent from current run; baseline was {baseline_by_name[name].score:.1%}.")
    return lines or ["- No adapters to compare."]


def format_run_report(
    run: EvaluationRun, baseline_scores: Iterable[AdapterScore] | None = None
) -> str:
    lines = [
        f"Evaluation run {run.run_id}",
        f"Experiment: {run.experiment_id}",
        f"Started: {run.started_at.isoformat()}",
        f"Completed: {run.completed_at.isoformat()}",
        "",
        "Leaderboard",
        render_leaderboard(run.scores),
    ]
    failures = [outcome for outcome in run.outcomes if outcome.error]
    lines.extend(["", f"Case errors: {len(failures)}"])
    for failure in failures:
        lines.append(f"- {failure.adapter_name} / {failure.case_id}: {failure.error}")
    if baseline_scores is not None:
        lines.extend(["", "Regression comparison", *regression_lines(run.scores, baseline_scores)])
    return "\n".join(lines)
