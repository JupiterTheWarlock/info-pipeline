"""Tests for web API endpoints."""

import json
import sys
import time
from http.server import HTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

import httpx
import lib.config as cfg_mod
from lib.db import init_db, insert_item, save_report, update_analysis, get_unanalyzed

# Ensure web module is importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _setup(tmp_path):
    import yaml
    config = {
        "storage": {"db_path": str(tmp_path / "test.db"), "output_dir": str(tmp_path / "output")},
        "processor": {"categories": ["AI"], "min_score": 3, "max_items_per_category": 20},
        "web": {"host": "127.0.0.1", "port": 3456},
    }
    with open(tmp_path / "config.yaml", "w") as f:
        yaml.dump(config, f)
    cfg_mod._config = None
    cfg_mod._project_root = tmp_path
    init_db()


def _teardown():
    cfg_mod._config = None


def _start_server(port):
    from web.server import PipelineHandler
    PipelineHandler.web_dir = str(Path(__file__).parent.parent / "web")
    server = HTTPServer(("127.0.0.1", port), PipelineHandler)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


class TestWebAPI:
    def test_api_tree(self, tmp_path):
        _setup(tmp_path)
        try:
            insert_item("https://example.com/1", "test", title="A")
            port = 13456
            server = _start_server(port)
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/api/tree", timeout=5)
                assert resp.status_code == 200
                data = resp.json()
                assert len(data) > 0
            finally:
                server.shutdown()
        finally:
            _teardown()

    def test_api_stats(self, tmp_path):
        _setup(tmp_path)
        try:
            port = 13457
            server = _start_server(port)
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/api/stats", timeout=5)
                assert resp.status_code == 200
                data = resp.json()
                assert "total_items" in data
            finally:
                server.shutdown()
        finally:
            _teardown()

    def test_api_report(self, tmp_path):
        _setup(tmp_path)
        try:
            save_report("2026-01-01", "daily", "# Test Report")
            port = 13458
            server = _start_server(port)
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/api/report/2026-01-01", timeout=5)
                assert resp.status_code == 200
                data = resp.json()
                assert data["content"] == "# Test Report"
            finally:
                server.shutdown()
        finally:
            _teardown()

    def test_api_report_invalid_date(self, tmp_path):
        _setup(tmp_path)
        try:
            port = 13459
            server = _start_server(port)
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/api/report/not-a-date", timeout=5)
                assert resp.status_code == 400
            finally:
                server.shutdown()
        finally:
            _teardown()

    def test_api_not_found(self, tmp_path):
        _setup(tmp_path)
        try:
            port = 13460
            server = _start_server(port)
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/api/nonexistent", timeout=5)
                assert resp.status_code == 404
            finally:
                server.shutdown()
        finally:
            _teardown()
