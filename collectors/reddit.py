"""Reddit collector via opencli."""

from typing import Any

from collectors.shared import run_opencli


class RedditCollector:
    name = "reddit"

    def __init__(self, config: dict[str, Any]):
        self.subreddits = config.get("subreddits", [])
        self.limit = config.get("limit", 50)

    def collect(self) -> int:
        count = 0
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
            print(f"[WARN] Reddit r/{subreddit}: {err[:100]}")
            return 0

        from lib.db import insert_item
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
