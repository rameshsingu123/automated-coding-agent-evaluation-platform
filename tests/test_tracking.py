from datetime import datetime, timedelta, timezone

import pytest

from eval_platform.leaderboard import rank_scores, render_leaderboard
from eval_platform.models import AdapterScore, EvaluationCase
from eval_platform.orchestrator import AdapterBinding, evaluate
from eval_platform.adapters import DeterministicBaselineAdapter
from eval_platform.report import regression_lines
from eval_platform.tracking import ExperimentTracker


def _make_run(experiment_id, response, *, started_at=None):
    case = EvaluationCase("case", "prompt", "expected", 2)
    run = evaluate(
        experiment_id,
        [case],
        [AdapterBinding("baseline", DeterministicBaselineAdapter({"case": response}))],
    )
    if started_at is not None:
        from dataclasses import replace
        run = replace(run, started_at=started_at, completed_at=started_at + timedelta(seconds=1))
    return run


def test_round_trip_and_latest_leaderboard(tmp_path):
    tracker = ExperimentTracker(tmp_path / "runs.sqlite3")
    tracker.register_experiment("exp", "Example", "tracked test")
    first = _make_run("exp", "expected")
    tracker.record_run(first)

    stored = tracker.load_run(first.run_id)
    assert stored.outcomes == first.outcomes
    assert stored.scores == first.scores
    assert tracker.leaderboard("exp") == list(first.scores)
    assert tracker.list_experiments()[0]["name"] == "Example"
    assert tracker.previous_scores(first.run_id) is None


def test_previous_run_regression_and_new_leaderboard(tmp_path):
    tracker = ExperimentTracker(tmp_path / "runs.sqlite3")
    tracker.register_experiment("exp", "Example")
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    first = _make_run("exp", "expected", started_at=base)
    second = _make_run("exp", "wrong", started_at=base + timedelta(minutes=1))
    tracker.record_run(first)
    tracker.record_run(second)

    previous = tracker.previous_scores(second.run_id)
    assert previous is not None
    assert previous[0].score == 1.0
    assert tracker.leaderboard("exp")[0].score == 0.0
    assert "REGRESSION" in "\n".join(regression_lines(second.scores, previous))


def test_duplicate_run_write_is_atomic(tmp_path):
    tracker = ExperimentTracker(tmp_path / "runs.sqlite3")
    tracker.register_experiment("exp", "Example")
    run = _make_run("exp", "expected")
    tracker.record_run(run)
    with pytest.raises(Exception):
        tracker.record_run(run)
    assert len(tracker.load_run(run.run_id).outcomes) == 1


def test_leaderboard_breaks_ties_deterministically():
    scores = [
        AdapterScore("zeta", 0.5, 1, 2, 1, 2),
        AdapterScore("alpha", 0.5, 1, 2, 1, 2),
    ]
    assert [score.adapter_name for score in rank_scores(scores)] == ["alpha", "zeta"]
    assert "50.0%" in render_leaderboard(scores)
