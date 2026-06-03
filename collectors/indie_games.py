"""Indie games collector (replaces existing openclaw cron pipeline)."""

import json
import subprocess
from typing import Any

import feedparser


class IndieGamesCollector:
    name = "indie_games"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.sources = config.get("sources", [])
        self.limit = config.get("limit", 30)

    def collect(self) -> int:
        count = 0
        for source in self.sources:
            source_type = source.get("type", "")
            if source_type == "reddit":
                count += self._collect_reddit(source)
            elif source_type == "rss":
                count += self._collect_rss(source)
        return count

    def _collect_reddit(self, source: dict) -> int:
        subreddits = source.get("subreddits", [])
        count = 0
        for sub in subreddits:
            try:
                result = subprocess.run(
                    ["opencli", "reddit", "hot", "--subreddit", sub, "--limit", str(self.limit)],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n"):
                        if not line.strip():
                            continue
                        try:
                            item = json.loads(line)
                            url = item.get("url", "")
                            if url:
                                from lib.db import insert_item
                                if insert_item(
                                    url=url,
                                    source=self.name,
                                    title=item.get("title", ""),
                                    content=item.get("selftext", ""),
                                    author=item.get("author", ""),
                                    source_detail=f"reddit/r/{sub}",
                                ):
                                    count += 1
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"[ERROR] IndieGames reddit r/{sub}: {e}")
        return count

    def _collect_rss(self, source: dict) -> int:
        url = source.get("url", "")
        name = source.get("name", url)
        try:
            parsed = feedparser.parse(url)
            count = 0
            for entry in parsed.entries[:self.limit]:
                link = entry.get("link", "")
                if not link:
                    continue
                from lib.db import insert_item
                if insert_item(
                    url=link,
                    source=self.name,
                    title=entry.get("title", ""),
                    content=entry.get("summary", ""),
                    source_detail=f"rss/{name}",
                ):
                    count += 1
            return count
        except Exception as e:
            print(f"[ERROR] IndieGames RSS {name}: {e}")
            return 0
