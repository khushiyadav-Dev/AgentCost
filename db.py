"""SQLite storage for every LLM call that passes through the gateway."""

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("AGENTCOST_DB", "agentcost.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ts               TEXT    NOT NULL,          -- ISO timestamp (UTC)
    agent            TEXT    NOT NULL,          -- which agent made the call
    user_id          TEXT    NOT NULL,          -- who it was for
    task             TEXT    NOT NULL,          -- feature / task label
    model            TEXT    NOT NULL,
    prompt_tokens    INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_usd         REAL    NOT NULL,
    latency_ms       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_calls_ts    ON calls(ts);
CREATE INDEX IF NOT EXISTS idx_calls_agent ON calls(agent);
"""


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)


def insert_call(row: dict):
    with db() as conn:
        conn.execute(
            """INSERT INTO calls
               (ts, agent, user_id, task, model, prompt_tokens, completion_tokens, cost_usd, latency_ms)
               VALUES (:ts, :agent, :user_id, :task, :model, :prompt_tokens,
                       :completion_tokens, :cost_usd, :latency_ms)""",
            row,
        )


def totals() -> dict:
    with db() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS calls,
                      COALESCE(SUM(cost_usd), 0) AS spend,
                      COALESCE(SUM(prompt_tokens + completion_tokens), 0) AS tokens
               FROM calls"""
        ).fetchone()
        today = conn.execute(
            """SELECT COALESCE(SUM(cost_usd), 0) AS spend
               FROM calls WHERE substr(ts, 1, 10) = date('now')"""
        ).fetchone()
    return {"calls": row["calls"], "spend": row["spend"],
            "tokens": row["tokens"], "today": today["spend"]}


def breakdown(column: str, limit: int = 12) -> list:
    """Spend grouped by agent / task / user / model."""
    assert column in {"agent", "task", "user_id", "model"}
    with db() as conn:
        rows = conn.execute(
            f"""SELECT {column} AS name,
                       COUNT(*)              AS calls,
                       SUM(cost_usd)         AS spend,
                       SUM(prompt_tokens + completion_tokens) AS tokens
                FROM calls
                GROUP BY {column}
                ORDER BY spend DESC
                LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def recent(limit: int = 15) -> list:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM calls ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def daily(days: int = 14) -> list:
    with db() as conn:
        rows = conn.execute(
            """SELECT substr(ts, 1, 10) AS day, SUM(cost_usd) AS spend
               FROM calls
               GROUP BY day
               ORDER BY day DESC
               LIMIT ?""",
            (days,),
        ).fetchall()
    return list(reversed([dict(r) for r in rows]))
