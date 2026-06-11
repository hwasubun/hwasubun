"""SQLite 신호 이력 저장소."""
import sqlite3
from datetime import date

import pandas as pd

import config
from signal_engine import Signal

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_history (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date      TEXT NOT NULL,
    rule_id   TEXT NOT NULL,
    name      TEXT NOT NULL,
    severity  TEXT NOT NULL,
    detail    TEXT NOT NULL,
    UNIQUE(date, rule_id)
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def save_triggered(signals: list[Signal]) -> int:
    """발동된 신호만 저장. 같은 날 같은 규칙은 중복 저장하지 않음. 신규 저장 건수 반환."""
    today = date.today().isoformat()
    saved = 0
    with _conn() as conn:
        for s in signals:
            if not s.triggered:
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO signal_history (date, rule_id, name, severity, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                (today, s.rule_id, s.name, s.severity, s.detail),
            )
            saved += cur.rowcount
    return saved


def load_history(limit: int = 100) -> pd.DataFrame:
    with _conn() as conn:
        return pd.read_sql_query(
            "SELECT date AS 날짜, rule_id AS 규칙, name AS 신호명, severity AS 등급, detail AS 상세 "
            "FROM signal_history ORDER BY date DESC, id DESC LIMIT ?",
            conn,
            params=(limit,),
        )
