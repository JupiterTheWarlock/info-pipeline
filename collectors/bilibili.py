"""Bilibili collector via opencli."""

import json
import subprocess
from typing import Any


class BilibiliCollector:
    name = "bilibili"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.keywords = config.get("keywords", [])
        self.limit = config.get("limit", 30)

    def collect(self) -> int:
        count = 0
        if self.keywords:
            for kw in self.keywords:
                count += self._search(kw)
        else:
            count = self._hot()
        return count

    def _hot(self) -> int:
        try:
            result = subprocess.run(
                ["opencli", "bilibili", "hot", "--limit", str(self.limit)],
                capture_output=True, text=True, timeout=120,
            )
            return self._process_result(result, "热门")
        except Exception as e:
            print(f"[ERROR] Bilibili hot: {e}")
            return 0

    def _search(self, keyword: str) -> int:
        try:
            result = subprocess.run(
                ["opencli", "bilibili", "search", "--keyword", keyword, "--limit", str(self.limit)],
                capture_output=True, text=True, timeout=120,
            )
            return self._process_result(result, f"搜索:{keyword}")
        except Exception as e:
            print(f"[ERROR] Bilibili search '{keyword}': {e}")
            return 0

    def _process_result(self, result: subprocess.CompletedProcess, detail: str) -> int:
        if result.returncode != 0:
            print(f"[WARN] Bilibili {detail}: {result.stderr[:200]}")
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
            url = item.get("url", "") or item.get("link", "")
            if not url:
                continue
            if self._insert(
                url=url,
                title=item.get("title", ""),
                content=item.get("description", item.get("desc", "")),
                author=item.get("author", item.get("owner", {}).get("name", "")),
                source_detail=detail,
            ):
                new_count += 1
        return new_count

    def _insert(self, **kwargs) -> bool:
        from lib.db import insert_item
        return insert_item(source=self.name, **kwargs)
