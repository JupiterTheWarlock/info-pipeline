"""Deduplication utilities."""

from lib.db import url_hash, get_connection, time
from typing import Any


def cleanup_old_items(days: int = 90):
    """Remove items older than N days."""
    conn = get_connection()
    cutoff = time.time() - days * 86400
    cursor = conn.execute(
        "DELETE FROM items WHERE collected_at < ?", (cutoff,)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"[CLEANUP] Removed {deleted} items older than {days} days")
    return deleted
