"""HackerNews collector via opencli."""

from typing import Any

from collectors.shared import run_opencli


class HackerNewsCollector:
    name = "hackernews"

    def __init__(self, config: dict[str, Any]):
        self.limit = config.get("limit", 50)

    def collect(self) -> int:
        items, err = run_opencli(
            "opencli", "hackernews", "top",
            "--limit", str(self.limit),
        )
        if err:
            print(f"[WARN] HackerNews: {err[:100]}")
            return 0

        from lib.db import insert_item
        new_count = 0
        for item in items:
            url = item.get("url", "") or f"https://news.ycombinator.com/item?id={item.get('id', '')}"
            if insert_item(
                url=url,
                source=self.name,
                title=item.get("title", ""),
                content=item.get("text", ""),
                author=item.get("author", ""),
                published_at=item.get("time"),
            ):
                new_count += 1
        return new_count
