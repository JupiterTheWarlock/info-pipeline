"""Weibo collector via opencli."""

import json
import subprocess
from typing import Any


class WeiboCollector:
    name = "weibo"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.keywords = config.get("keywords", [])
        self.limit = config.get("limit", 30)

    def collect(self) -> int:
        count = 0
        for kw in self.keywords:
            count += self._search(kw)
        return count

    def _search(self, keyword: str) -> int:
        try:
            result = subprocess.run(
                ["opencli", "weibo", "search", "--keyword", keyword, "--limit", str(self.limit)],
                capture_output=True, text=True, timeout=120,
            )
            return self._process_result(result, f"搜索:{keyword}")
        except FileNotFoundError:
            print("[WARN] Weibo: opencli weibo command not available")
            return 0
        except Exception as e:
            print(f"[ERROR] Weibo search '{keyword}': {e}")
            return 0

    def _process_result(self, result: subprocess.CompletedProcess, detail: str) -> int:
        if result.returncode != 0:
            print(f"[WARN] Weibo {detail}: {result.stderr[:200]}")
            return 0

        items = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        new_count = 0
        for item in items:
            url = item.get("url", "")
            if not url:
                continue
            if self._insert(
                url=url,
                title=item.get("text", "")[:200],
                content=item.get("text", ""),
                author=item.get("user", {}).get("screen_name", ""),
                source_detail=detail,
            ):
                new_count += 1
        return new_count

    def _insert(self, **kwargs) -> bool:
        from collectors.base import BaseCollector
        return BaseCollector.__new__(BaseCollector)._insert(
            source=self.name, **kwargs
        )
