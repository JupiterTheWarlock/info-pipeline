"""SQLite database operations for the pipeline."""

import hashlib
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get


def get_connection() -> sqlite3.Connection:
    db_path = get("storage.db_path")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            source TEXT NOT NULL,
            source_detail TEXT,
            author TEXT,
            content TEXT,
            collected_at REAL NOT NULL,
            published_at REAL,
            extra_json TEXT,

            -- Analysis fields (populated by processor)
            category TEXT,
            score REAL DEFAULT 0,
            summary TEXT,
            analyzed_at REAL
        );

        CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
        CREATE INDEX IF NOT EXISTS idx_items_collected_at ON items(collected_at);
        CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
        CREATE INDEX IF NOT EXISTS idx_items_score ON items(score DESC);

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_date_type ON reports(date, type);
    """)
    conn.commit()
    conn.close()


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def insert_item(
    url: str,
    source: str,
    title: str = "",
    content: str = "",
    author: str = "",
    published_at: float | None = None,
    source_detail: str = "",
    extra: dict | None = None,
) -> bool:
    """Insert a collected item. Returns True if new, False if duplicate."""
    h = url_hash(url)
    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO items
               (url_hash, url, title, source, source_detail, author, content,
                collected_at, published_at, extra_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                h, url, title, source, source_detail, author, content,
                time.time(), published_at,
                __import__("json").dumps(extra) if extra else None,
            ),
        )
        conn.commit()
        changed = conn.total_changes
        return changed > 0
    finally:
        conn.close()


def get_unanalyzed(limit: int = 100) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM items WHERE analyzed_at IS NULL ORDER BY collected_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_analysis(item_id: int, category: str, score: float, summary: str):
    conn = get_connection()
    conn.execute(
        """UPDATE items SET category = ?, score = ?, summary = ?, analyzed_at = ?
           WHERE id = ?""",
        (category, score, summary, time.time(), item_id),
    )
    conn.commit()
    conn.close()


def get_items_for_report(
    date_str: str,
    min_score: float = 3.0,
    limit_per_category: int = 20,
) -> list[dict]:
    """Get analyzed items for a specific date, grouped by category."""
    # Parse date string to timestamp range
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_ts = dt.timestamp()
    end_ts = start_ts + 86400

    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM items
           WHERE collected_at >= ? AND collected_at < ?
             AND analyzed_at IS NOT NULL AND score >= ?
           ORDER BY score DESC, collected_at DESC""",
        (start_ts, end_ts, min_score),
    ).fetchall()
    conn.close()

    # Group by category with limit
    categories: dict[str, list[dict]] = {}
    for row in rows:
        item = dict(row)
        cat = item.get("category") or "其他"
        if cat not in categories:
            categories[cat] = []
        if len(categories[cat]) < limit_per_category:
            categories[cat].append(item)

    return categories


def save_report(date_str: str, report_type: str, content: str):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO reports (date, type, content, created_at)
           VALUES (?, ?, ?, ?)""",
        (date_str, report_type, content, time.time()),
    )
    conn.commit()
    conn.close()


def get_reports_list() -> list[dict]:
    """Get all report dates with types."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT date, type FROM reports ORDER BY date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report(date_str: str, report_type: str) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT content FROM reports WHERE date = ? AND type = ?",
        (date_str, report_type),
    ).fetchone()
    conn.close()
    return row["content"] if row else None


def get_available_dates() -> list[str]:
    """Get list of dates that have any items."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT DISTINCT date(collected_at, 'unixepoch') as date
           FROM items ORDER BY date DESC"""
    ).fetchall()
    conn.close()
    return [r["date"] for r in rows]
