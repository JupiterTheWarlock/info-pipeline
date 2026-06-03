"""Reddit collector via opencli."""

import json
import subprocess
from typing import Any


class RedditCollector:
    name = "reddit"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.subreddits = config.get("subreddits", [])
        self.limit = config.get("limit", 50)

    def collect(self) -> int:
        count = 0
        for sub in self.subreddits:
            count += self._collect_subreddit(sub)
        return count

    def _collect_subreddit(self, subreddit: str) -> int:
        try:
            result = subprocess.run(
                ["opencli", "reddit", "hot", "--subreddit", subreddit, "--limit", str(self.limit)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                print(f"[WARN] Reddit {subreddit}: {result.stderr[:200]}")
                return 0

            # opencli outputs JSON lines
            items = self._parse_output(result.stdout)
            new_count = 0
            for item in items:
                if self._insert(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    content=item.get("selftext", ""),
                    author=item.get("author", ""),
                    published_at=item.get("created_utc"),
                    source_detail=f"r/{subreddit}",
                ):
                    new_count += 1
            return new_count
        except subprocess.TimeoutExpired:
            print(f"[WARN] Reddit {subreddit}: timed out")
            return 0
        except Exception as e:
            print(f"[ERROR] Reddit {subreddit}: {e}")
            return 0

    def _parse_output(self, output: str) -> list[dict]:
        """Parse opencli JSON output."""
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
        from lib.db import insert_item
        return insert_item(source=self.name, **kwargs)
