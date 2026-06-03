"""Twitter/X collector via opencli."""

import json
import subprocess
from typing import Any


class TwitterCollector:
    name = "twitter"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.accounts = config.get("accounts", [])
        self.keywords = config.get("keywords", [])
        self.limit = config.get("limit", 30)

    def collect(self) -> int:
        count = 0
        # Search by keywords
        for kw in self.keywords:
            count += self._search(kw)
        # Search by accounts
        for account in self.accounts:
            count += self._search(f"from:{account}")
        # If no keywords/accounts, get timeline
        if not self.keywords and not self.accounts:
            count = self._timeline()
        return count

    def _timeline(self) -> int:
        try:
            result = subprocess.run(
                ["opencli", "twitter", "timeline", "--limit", str(self.limit)],
                capture_output=True, text=True, timeout=120,
            )
            return self._process_result(result, "timeline")
        except Exception as e:
            print(f"[ERROR] Twitter timeline: {e}")
            return 0

    def _search(self, query: str) -> int:
        try:
            result = subprocess.run(
                ["opencli", "twitter", "search", "--query", query, "--limit", str(self.limit)],
                capture_output=True, text=True, timeout=120,
            )
            return self._process_result(result, f"search:{query}")
        except Exception as e:
            print(f"[ERROR] Twitter search '{query}': {e}")
            return 0

    def _process_result(self, result: subprocess.CompletedProcess, detail: str) -> int:
        if result.returncode != 0:
            print(f"[WARN] Twitter {detail}: {result.stderr[:200]}")
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
            tweet_id = item.get("id", "")
            url = item.get("url", "") or f"https://x.com/i/status/{tweet_id}"
            if self._insert(
                url=url,
                title=item.get("text", "")[:200],
                content=item.get("text", ""),
                author=item.get("username", item.get("author", "")),
                source_detail=detail,
            ):
                new_count += 1
        return new_count

    def _insert(self, **kwargs) -> bool:
        from lib.db import insert_item
        return insert_item(source=self.name, **kwargs)
