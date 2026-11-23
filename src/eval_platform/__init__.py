"""A small, local platform for deterministic coding-agent evaluations."""

from .adapters import AgentAdapter, DeterministicBaselineAdapter
from .models import AdapterScore, EvaluationCase, EvaluationOutcome, EvaluationRun
from .orchestrator import AdapterBinding, evaluate
from .scoring import score_adapter, score_all
from .tracking import ExperimentTracker

__all__ = [
    "AdapterBinding",
    "AdapterScore",
    "AgentAdapter",
    "DeterministicBaselineAdapter",
    "EvaluationCase",
    "EvaluationOutcome",
    "EvaluationRun",
    "ExperimentTracker",
    "evaluate",
    "score_adapter",
    "score_all",
]
