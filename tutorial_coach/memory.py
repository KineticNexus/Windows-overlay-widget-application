"""Memoria de sesión persistente con SQLite."""
import sqlite3
import json
from datetime import datetime
from tutorial_coach.config import DB_PATH


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crea las tablas si no existen."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            goal       TEXT NOT NULL,
            plan_json  TEXT NOT NULL,
            completed  INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS tutorials (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            steps_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()
    conn.close()


# ── Sesiones ───────────────────────────────────────────────────────────────────
def save_session(goal: str, plan: dict, completed: bool = False) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO sessions (goal, plan_json, completed) VALUES (?, ?, ?)",
        (goal, json.dumps(plan, ensure_ascii=False), int(completed)),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def mark_completed(session_id: int):
    conn = _connect()
    conn.execute("UPDATE sessions SET completed=1 WHERE id=?", (session_id,))
    conn.commit()
    conn.close()


def get_recent_sessions(limit: int = 20) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, goal, completed, created_at FROM sessions "
        "ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Tutoriales grabados ────────────────────────────────────────────────────────
def save_tutorial(name: str, steps: list[dict]) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO tutorials (name, steps_json) VALUES (?, ?)",
        (name, json.dumps(steps, ensure_ascii=False)),
    )
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return tid


def get_tutorials() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, name, created_at FROM tutorials ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_tutorial(tutorial_id: int) -> list[dict]:
    conn = _connect()
    row = conn.execute(
        "SELECT steps_json FROM tutorials WHERE id=?", (tutorial_id,)
    ).fetchone()
    conn.close()
    if row:
        return json.loads(row["steps_json"])
    return []
