"""RSS collector."""

import feedparser
from typing import Any
from datetime import timezone


class RSSCollector:
    name = "rss"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.feeds = config.get("feeds", [])

    def collect(self) -> int:
        count = 0
        for feed in self.feeds:
            count += self._collect_feed(feed)
        return count

    def _collect_feed(self, feed: dict) -> int:
        url = feed.get("url", "")
        name = feed.get("name", url)

        try:
            parsed = feedparser.parse(url)
            if not parsed.entries:
                return 0

            new_count = 0
            for entry in parsed.entries[:30]:
                link = entry.get("link", "")
                if not link:
                    continue

                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    import calendar, time
                    published_at = calendar.timegm(entry.published_parsed)

                summary = entry.get("summary", "") or ""
                if len(summary) > 1000:
                    summary = summary[:1000]

                if self._insert(
                    url=link,
                    title=entry.get("title", ""),
                    content=summary,
                    author=entry.get("author", ""),
                    published_at=published_at,
                    source_detail=name,
                ):
                    new_count += 1
            return new_count
        except Exception as e:
            print(f"[ERROR] RSS {name}: {e}")
            return 0

    def _insert(self, **kwargs) -> bool:
        from collectors.base import BaseCollector
        return BaseCollector.__new__(BaseCollector)._insert(
            source=self.name, **kwargs
        )
