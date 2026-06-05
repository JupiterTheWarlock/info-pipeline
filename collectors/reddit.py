"""Reddit collector via opencli."""

from typing import Any

import feedparser
import httpx

from collectors.shared import run_opencli
from lib.db import insert_item


class RedditCollector:
    name = "reddit"

    def __init__(self, config: dict[str, Any]):
        self.subreddits = config.get("subreddits", [])
        self.limit = config.get("limit", 50)
        self.last_errors: list[str] = []

    def collect(self) -> int:
        count = 0
        self.last_errors = []
        for sub in self.subreddits:
            count += self._collect_subreddit(sub)
        return count

    def _collect_subreddit(self, subreddit: str) -> int:
        items, err = run_opencli(
            "opencli", "reddit", "hot",
            "--subreddit", subreddit,
            "--limit", str(self.limit),
        )
        if err:
            if "command not found" in err:
                return self._collect_subreddit_json(subreddit)
            msg = f"r/{subreddit}: {err[:100]}"
            self.last_errors.append(msg)
            print(f"[WARN] Reddit {msg}")
            return 0

        new_count = 0
        for item in items:
            if insert_item(
                url=item.get("url", ""),
                source=self.name,
                title=item.get("title", ""),
                content=item.get("selftext", ""),
                author=item.get("author", ""),
                published_at=item.get("created_utc"),
                source_detail=f"r/{subreddit}",
            ):
                new_count += 1
        return new_count

    def _collect_subreddit_json(self, subreddit: str) -> int:
        """Fallback to Reddit's public JSON endpoint when opencli is unavailable."""
        try:
            resp = httpx.get(
                f"https://www.reddit.com/r/{subreddit}/hot.json",
                params={"limit": self.limit},
                headers={"User-Agent": "InfoPipeline/0.1"},
                timeout=20,
            )
            resp.raise_for_status()
            children = resp.json().get("data", {}).get("children", [])
        except Exception as exc:
            return self._collect_subreddit_rss(subreddit, json_error=str(exc))

        new_count = 0
        for child in children:
            item = child.get("data", {})
            permalink = item.get("permalink", "")
            url = item.get("url") or (f"https://www.reddit.com{permalink}" if permalink else "")
            if not url:
                continue
            if insert_item(
                url=url,
                source=self.name,
                title=item.get("title", ""),
                content=item.get("selftext", ""),
                author=item.get("author", ""),
                published_at=item.get("created_utc"),
                source_detail=f"r/{subreddit}",
                extra={
                    "score": item.get("score"),
                    "num_comments": item.get("num_comments"),
                    "permalink": permalink,
                    "fallback": "reddit_json",
                },
            ):
                new_count += 1
        return new_count

    def _collect_subreddit_rss(self, subreddit: str, json_error: str = "") -> int:
        """Fallback to subreddit Atom/RSS when JSON is blocked."""
        try:
            feed = feedparser.parse(f"https://www.reddit.com/r/{subreddit}/.rss")
            entries = feed.entries[: self.limit]
        except Exception as exc:
            msg = (
                f"r/{subreddit}: opencli unavailable; JSON fallback failed: {json_error[:100]}; "
                f"RSS fallback failed: {str(exc)[:100]}"
            )
            self.last_errors.append(msg)
            print(f"[WARN] Reddit {msg}")
            return 0

        new_count = 0
        for entry in entries:
            url = entry.get("link", "")
            if not url:
                continue
            if insert_item(
                url=url,
                source=self.name,
                title=entry.get("title", ""),
                content=entry.get("summary", ""),
                author=entry.get("author", ""),
                source_detail=f"r/{subreddit}",
                extra={"fallback": "reddit_rss"},
            ):
                new_count += 1
        if not entries:
            msg = f"r/{subreddit}: opencli unavailable; JSON fallback failed: {json_error[:100]}; RSS returned no entries"
            self.last_errors.append(msg)
            print(f"[WARN] Reddit {msg}")
        return new_count
