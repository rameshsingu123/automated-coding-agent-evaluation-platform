import pytest

from eval_platform.models import EvaluationCase, EvaluationOutcome
from eval_platform.scoring import score_adapter, score_all, validate_cases


def test_weighted_score_uses_case_weights_and_normalizes_outer_whitespace():
    cases = [
        EvaluationCase("small", "p1", "yes", 1),
        EvaluationCase("large", "p2", "answer\nline", 3),
    ]
    outcomes = [
        EvaluationOutcome("agent", "small", "yes", " yes\n"),
        EvaluationOutcome("agent", "large", "answer\nline", "answer\nline "),
    ]

    result = score_adapter(cases, outcomes, "agent")

    assert result.score == 1.0
    assert result.earned_weight == 4.0
    assert result.total_weight == 4.0
    assert result.correct_cases == 2


def test_failed_and_incorrect_cases_remain_in_denominator():
    cases = [EvaluationCase("ok", "p1", "same", 1), EvaluationCase("error", "p2", "expected", 3)]
    outcomes = [
        EvaluationOutcome("agent", "ok", "same", "same"),
        EvaluationOutcome("agent", "error", "expected", None, "RuntimeError: unavailable"),
    ]

    result = score_adapter(cases, outcomes, "agent")

    assert result.score == 0.25
    assert result.earned_weight == 1.0
    assert result.total_weight == 4.0


def test_score_all_preserves_first_seen_adapter_order():
    cases = [EvaluationCase("one", "p", "x")]
    outcomes = [
        EvaluationOutcome("zeta", "one", "x", "x"),
        EvaluationOutcome("alpha", "one", "x", "not x"),
    ]
    assert [score.adapter_name for score in score_all(cases, outcomes)] == ["zeta", "alpha"]


@pytest.mark.parametrize("weight", [0, -1, float("inf"), float("nan"), True])
def test_rejects_invalid_weights(weight):
    with pytest.raises(ValueError, match="weight"):
        validate_cases([EvaluationCase("bad", "prompt", "answer", weight)])


def test_rejects_duplicate_case_ids():
    cases = [EvaluationCase("same", "p1", "a"), EvaluationCase("same", "p2", "b")]
    with pytest.raises(ValueError, match="Duplicate case_id"):
        validate_cases(cases)


def test_rejects_missing_or_duplicate_outcomes():
    cases = [EvaluationCase("one", "p", "x")]
    with pytest.raises(ValueError, match="Missing outcomes"):
        score_adapter(cases, [], "agent")
    repeated = [
        EvaluationOutcome("agent", "one", "x", "x"),
        EvaluationOutcome("agent", "one", "x", "x"),
    ]
    with pytest.raises(ValueError, match="Duplicate outcome"):
        score_adapter(cases, repeated, "agent")
