"""SQLite persistence for experiments, runs, per-case outcomes, and scores."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import AdapterScore, EvaluationOutcome, EvaluationRun

_SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_experiment_completed
    ON runs(experiment_id, completed_at DESC);
CREATE TABLE IF NOT EXISTS evaluations (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    adapter_name TEXT NOT NULL,
    case_id TEXT NOT NULL,
    expected_output TEXT NOT NULL,
    actual_output TEXT,
    error TEXT,
    PRIMARY KEY (run_id, adapter_name, case_id)
);
CREATE TABLE IF NOT EXISTS scores (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    adapter_name TEXT NOT NULL,
    score REAL NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
    earned_weight REAL NOT NULL CHECK (earned_weight >= 0.0),
    total_weight REAL NOT NULL CHECK (total_weight > 0.0),
    correct_cases INTEGER NOT NULL CHECK (correct_cases >= 0),
    case_count INTEGER NOT NULL CHECK (case_count > 0),
    PRIMARY KEY (run_id, adapter_name)
);
"""


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


class ExperimentTracker:
    """Small SQLite tracker; each write is committed atomically with FK checks."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        if self.db_path == ":memory:":
            raise ValueError("ExperimentTracker requires a file-backed SQLite database")
        Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def register_experiment(self, experiment_id: str, name: str, description: str = "") -> None:
        if not experiment_id.strip() or not name.strip():
            raise ValueError("experiment_id and name must be non-empty")
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT name, description FROM experiments WHERE experiment_id = ?", (experiment_id,)
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO experiments (experiment_id, name, description, created_at) VALUES (?, ?, ?, ?)",
                    (experiment_id, name, description, datetime.now(timezone.utc).isoformat()),
                )
            elif existing["name"] != name or existing["description"] != description:
                raise ValueError(f"Experiment {experiment_id!r} is already registered with different metadata")

    def record_run(self, run: EvaluationRun) -> None:
        """Atomically persist run metadata, all outcomes, and all aggregate scores."""
        if not run.outcomes or not run.scores:
            raise ValueError("A run must contain outcomes and scores")
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO runs (run_id, experiment_id, started_at, completed_at) VALUES (?, ?, ?, ?)",
                (run.run_id, run.experiment_id, run.started_at.isoformat(), run.completed_at.isoformat()),
            )
            connection.executemany(
                """INSERT INTO evaluations
                   (run_id, adapter_name, case_id, expected_output, actual_output, error)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (run.run_id, item.adapter_name, item.case_id, item.expected_output, item.actual_output, item.error)
                    for item in run.outcomes
                ],
            )
            connection.executemany(
                """INSERT INTO scores
                   (run_id, adapter_name, score, earned_weight, total_weight, correct_cases, case_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (run.run_id, score.adapter_name, score.score, score.earned_weight, score.total_weight,
                     score.correct_cases, score.case_count)
                    for score in run.scores
                ],
            )

    def list_experiments(self) -> list[dict[str, str]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT experiment_id, name, description, created_at FROM experiments ORDER BY name, experiment_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def leaderboard(self, experiment_id: str, run_id: str | None = None) -> list[AdapterScore]:
        """Return scores for an explicit run, or the latest completed run."""
        with self._connection() as connection:
            if run_id is None:
                row = connection.execute(
                    "SELECT run_id FROM runs WHERE experiment_id = ? ORDER BY completed_at DESC, run_id DESC LIMIT 1",
                    (experiment_id,),
                ).fetchone()
                if row is None:
                    return []
                run_id = row["run_id"]
            else:
                row = connection.execute(
                    "SELECT run_id FROM runs WHERE run_id = ? AND experiment_id = ?", (run_id, experiment_id)
                ).fetchone()
                if row is None:
                    return []
            rows = connection.execute(
                """SELECT adapter_name, score, earned_weight, total_weight, correct_cases, case_count
                   FROM scores WHERE run_id = ? ORDER BY score DESC, adapter_name COLLATE NOCASE, adapter_name""",
                (run_id,),
            ).fetchall()
        return [AdapterScore(**dict(row)) for row in rows]

    def load_run(self, run_id: str) -> EvaluationRun:
        with self._connection() as connection:
            run_row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run_row is None:
                raise KeyError(f"Unknown run_id: {run_id}")
            outcome_rows = connection.execute(
                "SELECT adapter_name, case_id, expected_output, actual_output, error FROM evaluations "
                "WHERE run_id = ? ORDER BY adapter_name COLLATE NOCASE, adapter_name, case_id", (run_id,)
            ).fetchall()
            score_rows = connection.execute(
                "SELECT adapter_name, score, earned_weight, total_weight, correct_cases, case_count "
                "FROM scores WHERE run_id = ? ORDER BY score DESC, adapter_name COLLATE NOCASE, adapter_name", (run_id,)
            ).fetchall()
        return EvaluationRun(
            run_id=run_row["run_id"],
            experiment_id=run_row["experiment_id"],
            started_at=_parse_time(run_row["started_at"]),
            completed_at=_parse_time(run_row["completed_at"]),
            outcomes=tuple(EvaluationOutcome(**dict(row)) for row in outcome_rows),
            scores=tuple(AdapterScore(**dict(row)) for row in score_rows),
        )

    def previous_scores(self, run_id: str) -> list[AdapterScore] | None:
        """Find the immediately preceding run in the same experiment, if any."""
        with self._connection() as connection:
            current = connection.execute(
                "SELECT experiment_id, completed_at FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if current is None:
                raise KeyError(f"Unknown run_id: {run_id}")
            previous = connection.execute(
                """SELECT run_id FROM runs WHERE experiment_id = ? AND completed_at < ?
                   ORDER BY completed_at DESC, run_id DESC LIMIT 1""",
                (current["experiment_id"], current["completed_at"]),
            ).fetchone()
            if previous is None:
                return None
        return self.leaderboard(current["experiment_id"], previous["run_id"])
