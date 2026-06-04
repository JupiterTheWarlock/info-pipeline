"""Indie games collector (replaces existing openclaw cron pipeline)."""

from typing import Any

from collectors.shared import run_opencli

import feedparser


class IndieGamesCollector:
    name = "indie_games"

    def __init__(self, config: dict[str, Any]):
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
        from lib.db import insert_item
        subreddits = source.get("subreddits", [])
        count = 0
        for sub in subreddits:
            items, err = run_opencli(
                "opencli", "reddit", "hot",
                "--subreddit", sub, "--limit", str(self.limit),
            )
            if err:
                print(f"[WARN] IndieGames reddit r/{sub}: {err[:100]}")
                continue
            for item in items:
                url = item.get("url", "")
                if url and insert_item(
                    url=url,
                    source=self.name,
                    title=item.get("title", ""),
                    content=item.get("selftext", ""),
                    author=item.get("author", ""),
                    source_detail=f"reddit/r/{sub}",
                ):
                    count += 1
        return count

    def _collect_rss(self, source: dict) -> int:
        from lib.db import insert_item
        url = source.get("url", "")
        name = source.get("name", url)
        try:
            parsed = feedparser.parse(url)
            count = 0
            for entry in parsed.entries[:self.limit]:
                link = entry.get("link", "")
                if not link:
                    continue
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
