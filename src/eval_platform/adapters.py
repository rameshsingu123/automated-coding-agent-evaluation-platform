"""Adapter contract and deterministic local baseline (no external model calls)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, runtime_checkable

from .models import EvaluationCase


@runtime_checkable
class AgentAdapter(Protocol):
    """An implementation that returns an answer for a single evaluation case."""

    def run(self, case: EvaluationCase) -> str:
        """Return the adapter's answer; raise an exception to report a case error."""
        ...


@dataclass(frozen=True)
class DeterministicBaselineAdapter:
    """Return a configured answer by case ID, falling back to a fixed response.

    This deliberately does not call a model, network service, or commercial API.
    It is useful for validating orchestration and scoring behavior reproducibly.
    """

    responses: Mapping[str, str] = field(default_factory=dict)
    default_response: str = ""

    def run(self, case: EvaluationCase) -> str:
        return self.responses.get(case.case_id, self.default_response)
