"""Shared, immutable data structures used throughout the evaluation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    prompt: str
    expected_output: str
    weight: float = 1.0


@dataclass(frozen=True)
class EvaluationOutcome:
    adapter_name: str
    case_id: str
    expected_output: str
    actual_output: Optional[str]
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.actual_output is not None


@dataclass(frozen=True)
class AdapterScore:
    adapter_name: str
    score: float
    earned_weight: float
    total_weight: float
    correct_cases: int
    case_count: int


@dataclass(frozen=True)
class EvaluationRun:
    run_id: str
    experiment_id: str
    started_at: datetime
    completed_at: datetime
    outcomes: tuple[EvaluationOutcome, ...]
    scores: tuple[AdapterScore, ...]
