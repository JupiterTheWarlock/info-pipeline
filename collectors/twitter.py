"""Twitter/X collector via opencli."""

from typing import Any

from collectors.shared import run_opencli


class TwitterCollector:
    name = "twitter"

    def __init__(self, config: dict[str, Any]):
        self.accounts = config.get("accounts", [])
        self.keywords = config.get("keywords", [])
        self.limit = config.get("limit", 30)

    def collect(self) -> int:
        count = 0
        for kw in self.keywords:
            count += self._search(kw)
        for account in self.accounts:
            count += self._search(f"from:{account}")
        if not self.keywords and not self.accounts:
            count = self._timeline()
        return count

    def _timeline(self) -> int:
        items, err = run_opencli(
            "opencli", "twitter", "timeline", "--limit", str(self.limit),
        )
        if err:
            print(f"[WARN] Twitter timeline: {err[:100]}")
            return 0
        return self._process(items, "timeline")

    def _search(self, query: str) -> int:
        items, err = run_opencli(
            "opencli", "twitter", "search",
            "--query", query, "--limit", str(self.limit),
        )
        if err:
            print(f"[WARN] Twitter search '{query}': {err[:100]}")
            return 0
        return self._process(items, f"search:{query}")

    def _process(self, items: list[dict], detail: str) -> int:
        from lib.db import insert_item
        new_count = 0
        for item in items:
            tweet_id = item.get("id", "")
            url = item.get("url", "") or f"https://x.com/i/status/{tweet_id}"
            text = item.get("text", "")
            if insert_item(
                url=url,
                source=self.name,
                title=text[:200] if text else "",
                content=text,
                author=item.get("username", item.get("author", "")),
                source_detail=detail,
            ):
                new_count += 1
        return new_count
