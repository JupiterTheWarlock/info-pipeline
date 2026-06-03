"""Web UI server for browsing reports."""

import json
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from lib.config import get
from lib.db import get_items_for_report, get_available_dates, save_report, get_report, get_connection, time
from lib.llm import generate_report


class PipelineHandler(SimpleHTTPRequestHandler):
    """API + static file handler."""

    web_dir = str(Path(__file__).parent / "web")

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path.startswith("/api/"):
            self._handle_api(parsed.path, parsed.query)
        else:
            # Serve static files from web/
            super().__init__()

    def _handle_api(self, path: str, query: str):
        if path == "/api/tree":
            self._api_tree()
        elif path.startswith("/api/report/"):
            date_str = path.split("/api/report/", 1)[1]
            self._api_report(date_str)
        elif path == "/api/stats":
            self._api_stats()
        else:
            self._json_response({"error": "not found"}, 404)

    def _api_tree(self):
        """Build tree structure from available dates."""
        dates = get_available_dates()
        tree: dict[str, Any] = {}
        for date_str in dates:
            parts = date_str.split("-")
            if len(parts) != 3:
                continue
            year, month, day = parts
            tree.setdefault(year, {"_count": 0})
            tree[year].setdefault(month, {"_count": 0})
            tree[year][month].setdefault(day, 0)
            tree[year]["_count"] = tree[year].get("_count", 0) + 1
            tree[year][month]["_count"] = tree[year][month].get("_count", 0) + 1
            tree[year][month][day] += 1
        self._json_response(tree)

    def _api_report(self, date_str: str):
        """Get or generate report for a date."""
        # Validate date format
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            self._json_response({"error": "invalid date format, use YYYY-MM-DD"}, 400)
            return

        # Check for cached report
        cached = get_report(date_str, "daily")
        if cached:
            stats = self._get_stats(date_str)
            self._json_response({"content": cached, "stats": stats})
            return

        # Generate report on the fly
        min_score = get("processor.min_score", 3)
        limit = get("processor.max_items_per_category", 20)
        categories_items = get_items_for_report(date_str, min_score=min_score, limit_per_category=limit)

        if not categories_items:
            self._json_response({"content": None, "stats": {"items": 0, "categories": 0}})
            return

        content = generate_report(categories_items, date_str)
        save_report(date_str, "daily", content)

        stats = {
            "items": sum(len(v) for v in categories_items.values()),
            "categories": len(categories_items),
        }
        self._json_response({"content": content, "stats": stats})

    def _api_stats(self):
        conn = get_connection()
        total = conn.execute("SELECT COUNT(*) as cnt FROM items").fetchone()["cnt"]
        analyzed = conn.execute("SELECT COUNT(*) as cnt FROM items WHERE analyzed_at IS NOT NULL").fetchone()["cnt"]
        conn.close()
        self._json_response({
            "total_items": total,
            "analyzed_items": analyzed,
            "sources": ["reddit", "hackernews", "twitter", "bilibili", "zhihu", "weibo", "rss", "github_trending", "indie_games"],
        })

    def _get_stats(self, date_str: str) -> dict:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start_ts = dt.timestamp()
        end_ts = start_ts + 86400
        conn = get_connection()
        row = conn.execute(
            "SELECT COUNT(*) as cnt, COUNT(DISTINCT category) as cats FROM items WHERE collected_at >= ? AND collected_at < ? AND analyzed_at IS NOT NULL",
            (start_ts, end_ts),
        ).fetchone()
        conn.close()
        return {"items": row["cnt"], "categories": row["cats"]}

    def _json_response(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def translate_path(self, path: str) -> str:
        """Serve from web/ directory."""
        if path == "/":
            path = "/index.html"
        return str(Path(self.web_dir) / path.lstrip("/"))


def run_server(host: str = "127.0.0.1", port: int = 3456):
    """Start the web UI server."""
    server = HTTPServer((host, port), PipelineHandler)
    print(f"[WEB] Server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WEB] Server stopped")
        server.server_close()
