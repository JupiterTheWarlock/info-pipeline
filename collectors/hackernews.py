"""HackerNews collector via opencli."""

import json
import subprocess
from typing import Any


class HackerNewsCollector:
    name = "hackernews"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.limit = config.get("limit", 50)

    def collect(self) -> int:
        try:
            result = subprocess.run(
                ["opencli", "hackernews", "top", "--limit", str(self.limit)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                print(f"[WARN] HackerNews: {result.stderr[:200]}")
                return 0

            items = self._parse_output(result.stdout)
            new_count = 0
            for item in items:
                url = item.get("url", "") or f"https://news.ycombinator.com/item?id={item.get('id', '')}"
                if self._insert(
                    url=url,
                    title=item.get("title", ""),
                    content=item.get("text", ""),
                    author=item.get("by", ""),
                    published_at=item.get("time"),
                ):
                    new_count += 1
            return new_count
        except subprocess.TimeoutExpired:
            print("[WARN] HackerNews: timed out")
            return 0
        except Exception as e:
            print(f"[ERROR] HackerNews: {e}")
            return 0

    def _parse_output(self, output: str) -> list[dict]:
        items = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return items

    def _insert(self, **kwargs) -> bool:
        from collectors.base import BaseCollector
        return BaseCollector.__new__(BaseCollector)._insert(
            source=self.name, **kwargs
        )
