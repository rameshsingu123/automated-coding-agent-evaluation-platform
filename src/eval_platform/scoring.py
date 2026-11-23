"""Validated weighted scoring for exact-match evaluation outcomes."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Iterable, Sequence

from .models import AdapterScore, EvaluationCase, EvaluationOutcome


def validate_cases(cases: Sequence[EvaluationCase]) -> None:
    if not cases:
        raise ValueError("At least one evaluation case is required")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case.case_id, str) or not case.case_id.strip():
            raise ValueError("Each case_id must be a non-empty string")
        if case.case_id in seen:
            raise ValueError(f"Duplicate case_id: {case.case_id}")
        seen.add(case.case_id)
        if not isinstance(case.prompt, str) or not isinstance(case.expected_output, str):
            raise ValueError(f"Case {case.case_id!r} prompt and expected_output must be strings")
        if isinstance(case.weight, bool) or not isinstance(case.weight, (int, float)):
            raise ValueError(f"Case {case.case_id!r} weight must be a finite positive number")
        if not math.isfinite(case.weight) or case.weight <= 0:
            raise ValueError(f"Case {case.case_id!r} weight must be a finite positive number")


def _normalize(text: str) -> str:
    """Normalize line endings and surrounding whitespace, but not internal content."""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def score_adapter(
    cases: Sequence[EvaluationCase],
    outcomes: Iterable[EvaluationOutcome],
    adapter_name: str,
) -> AdapterScore:
    """Score one adapter; failed cases earn zero while retaining their case weight."""
    validate_cases(cases)
    case_by_id = {case.case_id: case for case in cases}
    selected: dict[str, EvaluationOutcome] = {}
    for outcome in outcomes:
        if outcome.adapter_name != adapter_name:
            continue
        if outcome.case_id not in case_by_id:
            raise ValueError(f"Outcome references unknown case_id: {outcome.case_id}")
        if outcome.case_id in selected:
            raise ValueError(f"Duplicate outcome for adapter {adapter_name!r}, case {outcome.case_id!r}")
        selected[outcome.case_id] = outcome
    missing = set(case_by_id) - set(selected)
    if missing:
        raise ValueError(f"Missing outcomes for adapter {adapter_name!r}: {', '.join(sorted(missing))}")

    total_weight = sum(float(case.weight) for case in cases)
    earned_weight = 0.0
    correct_cases = 0
    for case in cases:
        outcome = selected[case.case_id]
        correct = (
            outcome.error is None
            and outcome.actual_output is not None
            and _normalize(outcome.actual_output) == _normalize(case.expected_output)
        )
        if correct:
            earned_weight += float(case.weight)
            correct_cases += 1
    return AdapterScore(
        adapter_name=adapter_name,
        score=earned_weight / total_weight,
        earned_weight=earned_weight,
        total_weight=total_weight,
        correct_cases=correct_cases,
        case_count=len(cases),
    )


def score_all(
    cases: Sequence[EvaluationCase], outcomes: Iterable[EvaluationOutcome]
) -> tuple[AdapterScore, ...]:
    """Return scores in the first-seen adapter order."""
    validate_cases(cases)
    outcome_list = tuple(outcomes)
    adapter_names = list(dict.fromkeys(outcome.adapter_name for outcome in outcome_list))
    return tuple(score_adapter(cases, outcome_list, name) for name in adapter_names)
