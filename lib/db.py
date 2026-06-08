"""SQLite database operations for the pipeline."""

import hashlib
import json
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
            preference_score REAL DEFAULT 0,
            why_relevant TEXT,
            risk TEXT,
            tags_json TEXT,
            analyzed_at REAL
        );

        CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
        CREATE INDEX IF NOT EXISTS idx_items_collected_at ON items(collected_at);
        CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
        CREATE INDEX IF NOT EXISTS idx_items_score ON items(score DESC);
        CREATE INDEX IF NOT EXISTS idx_items_preference_score ON items(preference_score DESC);

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_date_type ON reports(date, type);

        CREATE TABLE IF NOT EXISTS collector_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            new_count INTEGER DEFAULT 0,
            seen_count INTEGER DEFAULT 0,
            errors_json TEXT,
            started_at REAL NOT NULL,
            finished_at REAL NOT NULL,
            elapsed REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_collector_runs_name_started
          ON collector_runs(name, started_at DESC);
    """)
    _ensure_columns(conn, "items", {
        "preference_score": "REAL DEFAULT 0",
        "why_relevant": "TEXT",
        "risk": "TEXT",
        "tags_json": "TEXT",
    })
    conn.commit()
    conn.close()


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]):
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


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
                json.dumps(extra, ensure_ascii=False) if extra else None,
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


def update_analysis(
    item_id: int,
    category: str,
    score: float,
    summary: str,
    preference_score: float = 0,
    why_relevant: str = "",
    risk: str = "",
    tags: list[str] | None = None,
):
    conn = get_connection()
    conn.execute(
        """UPDATE items SET category = ?, score = ?, summary = ?,
              preference_score = ?, why_relevant = ?, risk = ?, tags_json = ?,
              analyzed_at = ?
           WHERE id = ?""",
        (
            category,
            score,
            summary,
            preference_score,
            why_relevant,
            risk,
            json.dumps(tags or [], ensure_ascii=False),
            time.time(),
            item_id,
        ),
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
           ORDER BY preference_score DESC, score DESC, collected_at DESC""",
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


def query_items(
    date_str: str | None = None,
    source: str | None = None,
    category: str | None = None,
    min_score: float | None = None,
    query: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Query collected items for the dashboard."""
    where, params = _item_query_filters(date_str, source, category, min_score, query)

    sql = "SELECT * FROM items"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY preference_score DESC, score DESC, collected_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    items = []
    for row in rows:
        item = dict(row)
        item["tags"] = json.loads(item.get("tags_json") or "[]")
        items.append(item)
    return items


def count_items(
    date_str: str | None = None,
    source: str | None = None,
    category: str | None = None,
    min_score: float | None = None,
    query: str | None = None,
) -> int:
    """Count collected items matching dashboard filters."""
    where, params = _item_query_filters(date_str, source, category, min_score, query)
    sql = "SELECT COUNT(*) AS cnt FROM items"
    if where:
        sql += " WHERE " + " AND ".join(where)
    conn = get_connection()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return int(row["cnt"])


def _item_query_filters(
    date_str: str | None,
    source: str | None,
    category: str | None,
    min_score: float | None,
    query: str | None,
) -> tuple[list[str], list[Any]]:
    where = []
    params: list[Any] = []

    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start_ts = dt.timestamp()
        end_ts = start_ts + 86400
        where.append("collected_at >= ? AND collected_at < ?")
        params.extend([start_ts, end_ts])
    if source:
        where.append("source = ?")
        params.append(source)
    if category:
        where.append("category = ?")
        params.append(category)
    if min_score is not None:
        where.append("score >= ?")
        params.append(min_score)
    if query:
        pattern = f"%{query.strip()}%"
        where.append(
            """(
                title LIKE ? OR url LIKE ? OR author LIKE ? OR source_detail LIKE ?
                OR content LIKE ? OR summary LIKE ? OR why_relevant LIKE ?
                OR risk LIKE ? OR tags_json LIKE ?
            )"""
        )
        params.extend([pattern] * 9)
    return where, params


def get_item_facets(date_str: str | None = None) -> dict[str, list[str]]:
    """Return source and category facets for the dashboard."""
    where = []
    params: list[Any] = []
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        where.append("collected_at >= ? AND collected_at < ?")
        params.extend([dt.timestamp(), dt.timestamp() + 86400])
    suffix = " WHERE " + " AND ".join(where) if where else ""

    conn = get_connection()
    sources = conn.execute(
        f"SELECT DISTINCT source FROM items{suffix} ORDER BY source",
        params,
    ).fetchall()
    categories = conn.execute(
        f"SELECT DISTINCT category FROM items{suffix} WHERE category IS NOT NULL ORDER BY category"
        if not where
        else f"SELECT DISTINCT category FROM items{suffix} AND category IS NOT NULL ORDER BY category",
        params,
    ).fetchall()
    conn.close()
    return {
        "sources": [r["source"] for r in sources if r["source"]],
        "categories": [r["category"] for r in categories if r["category"]],
    }


def save_collector_run(
    name: str,
    status: str,
    new_count: int,
    seen_count: int,
    errors: list[str] | None,
    started_at: float,
    finished_at: float,
):
    """Persist one collector execution result for UI/evaluation visibility."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO collector_runs
           (name, status, new_count, seen_count, errors_json, started_at, finished_at, elapsed)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            status,
            int(new_count),
            int(seen_count),
            json.dumps(errors or [], ensure_ascii=False),
            started_at,
            finished_at,
            max(finished_at - started_at, 0),
        ),
    )
    conn.commit()
    conn.close()


def get_latest_collector_runs() -> dict[str, dict]:
    """Return the latest persisted run for each collector."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT cr.*
           FROM collector_runs cr
           JOIN (
             SELECT name, MAX(started_at) AS started_at
             FROM collector_runs
             GROUP BY name
           ) latest
             ON cr.name = latest.name AND cr.started_at = latest.started_at
           ORDER BY cr.name"""
    ).fetchall()
    conn.close()
    runs = {}
    for row in rows:
        run = dict(row)
        run["errors"] = json.loads(run.get("errors_json") or "[]")
        runs[run["name"]] = run
    return runs


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
