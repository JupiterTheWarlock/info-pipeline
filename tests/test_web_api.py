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
from lib.db import init_db, insert_item, save_collector_run, save_report, update_analysis, get_unanalyzed

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

    def test_api_collectors(self, tmp_path):
        _setup(tmp_path)
        try:
            save_collector_run("linuxdo", "error", 0, 0, ["403"], 10.0, 12.0)
            port = 13461
            server = _start_server(port)
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/api/collectors", timeout=5)
                assert resp.status_code == 200
                collectors = resp.json()["collectors"]
                names = {c["name"] for c in collectors}
                assert "linuxdo" in names
                assert "reddit" in names
                linuxdo = next(c for c in collectors if c["name"] == "linuxdo")
                assert linuxdo["latest_run"]["status"] == "error"
                assert linuxdo["latest_run"]["errors"] == ["403"]
            finally:
                server.shutdown()
        finally:
            _teardown()

    def test_api_items(self, tmp_path):
        _setup(tmp_path)
        try:
            insert_item(
                "https://example.com/1",
                "reddit",
                title="A",
                content='<p>Hello</p><img src="https://example.com/card.jpg">',
                extra={"thumbnail": "https://example.com/thumb.jpg"},
            )
            item = get_unanalyzed()[0]
            update_analysis(
                item["id"],
                "Indie Game / 独立游戏",
                7.0,
                "Summary",
                preference_score=8.0,
                why_relevant="Relevant",
                tags=["indie"],
            )
            port = 13462
            server = _start_server(port)
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/api/items?source=reddit", timeout=5)
                assert resp.status_code == 200
                data = resp.json()
                assert data["items"][0]["preference_score"] == 8.0
                assert data["items"][0]["image_url"] == "https://example.com/thumb.jpg"
                assert "reddit" in data["facets"]["sources"]
            finally:
                server.shutdown()
        finally:
            _teardown()

    def test_api_run_collect(self, tmp_path):
        _setup(tmp_path)
        try:
            port = 13463
            server = _start_server(port)
            try:
                with patch("main.run_collectors", return_value=2) as mock_run:
                    resp = httpx.post(
                        f"http://127.0.0.1:{port}/api/run/collect?collectors=twitter,reddit",
                        timeout=5,
                    )
                assert resp.status_code == 200
                data = resp.json()
                assert data["action"] == "collect"
                assert data["total_new"] == 2
                mock_run.assert_called_once_with(["twitter", "reddit"])
            finally:
                server.shutdown()
        finally:
            _teardown()

    def test_api_run_analyze(self, tmp_path):
        _setup(tmp_path)
        try:
            port = 13464
            server = _start_server(port)
            try:
                with patch("main.run_analysis") as mock_run:
                    resp = httpx.post(f"http://127.0.0.1:{port}/api/run/analyze", timeout=5)
                assert resp.status_code == 200
                assert resp.json()["action"] == "analyze"
                mock_run.assert_called_once()
            finally:
                server.shutdown()
        finally:
            _teardown()

    def test_api_run_report_invalid_date(self, tmp_path):
        _setup(tmp_path)
        try:
            port = 13465
            server = _start_server(port)
            try:
                resp = httpx.post(f"http://127.0.0.1:{port}/api/run/report?date=nope", timeout=5)
                assert resp.status_code == 400
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
