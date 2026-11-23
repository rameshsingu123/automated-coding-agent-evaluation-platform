"""Concurrent evaluation orchestration with deterministic result ordering."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from .adapters import AgentAdapter
from .models import EvaluationCase, EvaluationOutcome, EvaluationRun
from .scoring import score_all, validate_cases


@dataclass(frozen=True)
class AdapterBinding:
    name: str
    adapter: AgentAdapter


def evaluate(
    experiment_id: str,
    cases: Sequence[EvaluationCase],
    adapters: Sequence[AdapterBinding],
    *,
    max_workers: int | None = None,
) -> EvaluationRun:
    """Run every adapter/case pair concurrently, returning stable ordered results.

    Errors are isolated to their adapter/case pair and represented in the outcome;
    other work continues. Results are returned in adapter order, then case order,
    regardless of the order in which worker futures complete.
    """
    if not experiment_id.strip():
        raise ValueError("experiment_id must be a non-empty string")
    validate_cases(cases)
    if not adapters:
        raise ValueError("At least one adapter is required")
    names = [binding.name for binding in adapters]
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("Adapter names must be non-empty strings")
    if len(set(names)) != len(names):
        raise ValueError("Adapter names must be unique within a run")

    started_at = datetime.now(timezone.utc)
    indexed_outcomes: dict[tuple[int, int], EvaluationOutcome] = {}

    def invoke(binding: AdapterBinding, case: EvaluationCase) -> str:
        output = binding.adapter.run(case)
        if not isinstance(output, str):
            raise TypeError(f"adapter returned {type(output).__name__}; expected str")
        return output

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for adapter_index, binding in enumerate(adapters):
            for case_index, case in enumerate(cases):
                future = executor.submit(invoke, binding, case)
                futures[future] = (adapter_index, case_index, binding, case)
        for future in as_completed(futures):
            adapter_index, case_index, binding, case = futures[future]
            try:
                output = future.result()
                outcome = EvaluationOutcome(binding.name, case.case_id, case.expected_output, output)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}".strip()
                outcome = EvaluationOutcome(binding.name, case.case_id, case.expected_output, None, message)
            indexed_outcomes[(adapter_index, case_index)] = outcome

    outcomes = tuple(
        indexed_outcomes[(adapter_index, case_index)]
        for adapter_index in range(len(adapters))
        for case_index in range(len(cases))
    )
    scores = score_all(cases, outcomes)
    return EvaluationRun(
        run_id=str(uuid4()),
        experiment_id=experiment_id,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        outcomes=outcomes,
        scores=scores,
    )
