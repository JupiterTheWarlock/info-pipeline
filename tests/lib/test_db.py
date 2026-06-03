"""Tests for lib.db."""

import time
from datetime import datetime, timezone
from unittest.mock import patch

import lib.config as cfg_mod
from lib.db import (
    get_available_dates,
    get_items_for_report,
    get_report,
    get_unanalyzed,
    init_db,
    insert_item,
    save_report,
    update_analysis,
    url_hash,
)


def _setup_db(tmp_path):
    """Init config + db in tmp_path."""
    import yaml

    db_path = str(tmp_path / "test.db")
    config = {
        "storage": {"db_path": db_path, "output_dir": str(tmp_path / "output")},
        "processor": {"min_score": 3, "max_items_per_category": 20},
    }
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    cfg_mod._config = None
    cfg_mod._project_root = tmp_path
    return db_path


def _teardown_db():
    cfg_mod._config = None


class TestInitDb:
    def test_creates_tables(self, tmp_path):
        _setup_db(tmp_path)
        try:
            init_db()
            import sqlite3
            conn = sqlite3.connect(str(tmp_path / "test.db"))
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {r[0] for r in tables}
            assert "items" in table_names
            assert "reports" in table_names
            conn.close()
        finally:
            _teardown_db()


class TestInsertItem:
    def test_insert_returns_true(self, tmp_path):
        _setup_db(tmp_path)
        try:
            init_db()
            result = insert_item("https://example.com/1", "test", title="Test")
            assert result is True
        finally:
            _teardown_db()

    def test_duplicate_url_not_inserted(self, tmp_path):
        _setup_db(tmp_path)
        try:
            init_db()
            insert_item("https://example.com/1", "test", title="First")
            result = insert_item("https://example.com/1", "test", title="Second")
            assert result is False
        finally:
            _teardown_db()

    def test_url_hash_deterministic(self):
        assert url_hash("https://example.com") == url_hash("https://example.com")
        assert url_hash("https://a.com") != url_hash("https://b.com")


class TestGetUnanalyzed:
    def test_returns_unanalyzed_items(self, tmp_path):
        _setup_db(tmp_path)
        try:
            init_db()
            insert_item("https://example.com/1", "test", title="A")
            insert_item("https://example.com/2", "test", title="B")
            items = get_unanalyzed()
            assert len(items) == 2
            assert items[0]["analyzed_at"] is None
        finally:
            _teardown_db()


class TestUpdateAnalysis:
    def test_updates_item(self, tmp_path):
        _setup_db(tmp_path)
        try:
            init_db()
            insert_item("https://example.com/1", "test", title="A")
            items = get_unanalyzed()
            item_id = items[0]["id"]
            update_analysis(item_id, "AI", 8.0, "Great stuff")
            remaining = get_unanalyzed()
            assert len(remaining) == 0
        finally:
            _teardown_db()


class TestGetItemsForReport:
    def test_returns_categorized_items(self, tmp_path):
        _setup_db(tmp_path)
        try:
            init_db()
            # Insert and analyze
            now = time.time()
            insert_item("https://example.com/1", "test", title="A")
            items = get_unanalyzed()
            update_analysis(items[0]["id"], "AI", 7.0, "Summary")

            date_str = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%d")
            cats = get_items_for_report(date_str, min_score=3.0)
            assert "AI" in cats
            assert len(cats["AI"]) == 1
        finally:
            _teardown_db()


class TestReports:
    def test_save_and_get_report(self, tmp_path):
        _setup_db(tmp_path)
        try:
            init_db()
            save_report("2026-01-01", "daily", "# Report content")
            content = get_report("2026-01-01", "daily")
            assert content == "# Report content"
        finally:
            _teardown_db()

    def test_get_missing_report(self, tmp_path):
        _setup_db(tmp_path)
        try:
            init_db()
            assert get_report("2099-01-01", "daily") is None
        finally:
            _teardown_db()


class TestGetAvailableDates:
    def test_returns_dates(self, tmp_path):
        _setup_db(tmp_path)
        try:
            init_db()
            insert_item("https://example.com/1", "test")
            dates = get_available_dates()
            assert len(dates) >= 1
        finally:
            _teardown_db()
