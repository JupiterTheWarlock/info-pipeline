"""Web UI server for browsing reports."""

import json
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from lib.config import get
from lib.db import (
    get_available_dates,
    get_connection,
    get_item_facets,
    get_items_for_report,
    get_latest_collector_runs,
    get_report,
    query_items,
    save_report,
    time,
)
from lib.llm import generate_report


class PipelineHandler(SimpleHTTPRequestHandler):
    """API + static file handler."""

    web_dir = str(Path(__file__).parent / "web")

    def do_GET(self):
        try:
            parsed = urlparse(self.path)

            if parsed.path.startswith("/api/"):
                self._handle_api(parsed.path, parsed.query)
            else:
                super().do_GET()
        except ConnectionResetError:
            pass
        except Exception as e:
            try:
                self.send_error(500, str(e))
            except Exception:
                pass

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/run/"):
                self._handle_run(parsed.path, parsed.query)
            else:
                self._json_response({"error": "not found"}, 404)
        except ConnectionResetError:
            pass
        except Exception as e:
            try:
                self._json_response({"error": str(e)}, 500)
            except Exception:
                pass

    def _handle_api(self, path: str, query: str):
        if path == "/api/tree":
            self._api_tree()
        elif path.startswith("/api/report/"):
            date_str = path.split("/api/report/", 1)[1]
            self._api_report(date_str)
        elif path == "/api/stats":
            self._api_stats()
        elif path == "/api/items":
            self._api_items(query)
        elif path == "/api/collectors":
            self._api_collectors()
        else:
            self._json_response({"error": "not found"}, 404)

    def _handle_run(self, path: str, query: str):
        params = parse_qs(query)
        action = path.rsplit("/", 1)[-1]

        if action == "collect":
            from main import run_collectors

            names_raw = _first(params, "collectors")
            names = [n.strip() for n in names_raw.split(",") if n.strip()] if names_raw else None
            total_new = run_collectors(names)
            self._json_response({
                "status": "ok",
                "action": "collect",
                "total_new": total_new,
                "collectors": _collectors_payload(),
            })
            return

        if action == "analyze":
            from main import run_analysis

            run_analysis()
            self._json_response({"status": "ok", "action": "analyze"})
            return

        if action == "report":
            from main import run_report

            date_str = _first(params, "date")
            if date_str:
                try:
                    datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    self._json_response({"error": "invalid date format, use YYYY-MM-DD"}, 400)
                    return
            content = run_report(date_str)
            self._json_response({
                "status": "ok",
                "action": "report",
                "generated": content is not None,
                "content": content,
            })
            return

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
        from collectors.registry import available_collectors

        collector_cfg = get("collectors", {})
        conn = get_connection()
        total = conn.execute("SELECT COUNT(*) as cnt FROM items").fetchone()["cnt"]
        analyzed = conn.execute("SELECT COUNT(*) as cnt FROM items WHERE analyzed_at IS NOT NULL").fetchone()["cnt"]
        conn.close()
        self._json_response({
            "total_items": total,
            "analyzed_items": analyzed,
            "sources": available_collectors(collector_cfg),
        })

    def _api_items(self, query: str):
        params = parse_qs(query)
        date_str = _first(params, "date")
        source = _first(params, "source")
        category = _first(params, "category")
        min_score_raw = _first(params, "min_score")
        limit_raw = _first(params, "limit")

        if date_str:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                self._json_response({"error": "invalid date format, use YYYY-MM-DD"}, 400)
                return

        min_score = float(min_score_raw) if min_score_raw else None
        limit = min(max(int(limit_raw or 200), 1), 500)
        items = query_items(
            date_str=date_str,
            source=source,
            category=category,
            min_score=min_score,
            limit=limit,
        )
        self._json_response({
            "items": [_dashboard_item(item) for item in items],
            "facets": get_item_facets(date_str),
        })

    def _api_collectors(self):
        self._json_response({"collectors": _collectors_payload()})

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
        web = Path(__file__).parent.resolve() / path.lstrip("/")
        return str(web)


def run_server(host: str = "127.0.0.1", port: int = 3456):
    """Start the web UI server."""
    import socketserver
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True
    server = ThreadedHTTPServer((host, port), PipelineHandler)
    print(f"[WEB] Server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[WEB] Server stopped")
        server.server_close()


def _first(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key) or []
    return values[0] if values and values[0] else None


def _dashboard_item(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "url": item.get("url"),
        "title": item.get("title") or "Untitled",
        "source": item.get("source"),
        "source_detail": item.get("source_detail"),
        "author": item.get("author"),
        "content": item.get("content"),
        "category": item.get("category") or "未分析",
        "score": item.get("score") or 0,
        "preference_score": item.get("preference_score") or 0,
        "summary": item.get("summary") or "",
        "why_relevant": item.get("why_relevant") or "",
        "risk": item.get("risk") or "",
        "tags": item.get("tags") or [],
        "collected_at": item.get("collected_at"),
        "published_at": item.get("published_at"),
    }


def _collector_run(run: dict | None) -> dict | None:
    if not run:
        return None
    return {
        "status": run.get("status"),
        "new_count": run.get("new_count") or 0,
        "seen_count": run.get("seen_count") or 0,
        "errors": run.get("errors") or [],
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "elapsed": run.get("elapsed") or 0,
    }


def _collectors_payload() -> list[dict]:
    from collectors.registry import collector_metadata

    collector_cfg = get("collectors", {})
    runs = get_latest_collector_runs()
    collectors = []
    for meta in collector_metadata(collector_cfg):
        latest = runs.get(meta["name"])
        collectors.append({
            **meta,
            "latest_run": _collector_run(latest) if latest else None,
        })
    return collectors
