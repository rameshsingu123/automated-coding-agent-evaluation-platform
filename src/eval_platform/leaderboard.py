"""Leaderboard ordering and text rendering."""

from __future__ import annotations

from typing import Iterable

from .models import AdapterScore


def rank_scores(scores: Iterable[AdapterScore]) -> list[AdapterScore]:
    """Rank by score descending, then adapter name for deterministic ties."""
    items = list(scores)
    if len({item.adapter_name for item in items}) != len(items):
        raise ValueError("Leaderboard input must contain at most one score per adapter")
    return sorted(items, key=lambda item: (-item.score, item.adapter_name.casefold(), item.adapter_name))


def render_leaderboard(scores: Iterable[AdapterScore]) -> str:
    ranked = rank_scores(scores)
    if not ranked:
        return "No completed evaluations."
    name_width = max(len("Adapter"), *(len(item.adapter_name) for item in ranked))
    lines = [
        f"{'Rank':>4}  {'Adapter':<{name_width}}  {'Score':>7}  {'Cases':>7}  {'Weight':>12}",
        f"{'-' * 4}  {'-' * name_width}  {'-' * 7}  {'-' * 7}  {'-' * 12}",
    ]
    for rank, item in enumerate(ranked, start=1):
        lines.append(
            f"{rank:>4}  {item.adapter_name:<{name_width}}  {item.score:>6.1%}  "
            f"{item.correct_cases:>3}/{item.case_count:<3}  "
            f"{item.earned_weight:>5.2f}/{item.total_weight:<5.2f}"
        )
    return "\n".join(lines)
