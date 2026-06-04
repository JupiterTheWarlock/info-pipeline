"""Bilibili collector via opencli."""

from typing import Any

from collectors.shared import run_opencli


class BilibiliCollector:
    name = "bilibili"

    def __init__(self, config: dict[str, Any]):
        self.keywords = config.get("keywords", [])
        self.limit = config.get("limit", 30)

    def collect(self) -> int:
        count = 0
        if self.keywords:
            for kw in self.keywords:
                count += self._search(kw)
        else:
            count = self._hot()
        return count

    def _hot(self) -> int:
        items, err = run_opencli(
            "opencli", "bilibili", "hot", "--limit", str(self.limit),
        )
        if err:
            print(f"[WARN] Bilibili hot: {err[:100]}")
            return 0
        return self._process(items, "热门")

    def _search(self, keyword: str) -> int:
        items, err = run_opencli(
            "opencli", "bilibili", "search",
            "--keyword", keyword, "--limit", str(self.limit),
        )
        if err:
            print(f"[WARN] Bilibili search '{keyword}': {err[:100]}")
            return 0
        return self._process(items, f"搜索:{keyword}")

    def _process(self, items: list[dict], detail: str) -> int:
        from lib.db import insert_item
        new_count = 0
        for item in items:
            url = item.get("url", "") or item.get("link", "")
            if not url:
                continue
            if insert_item(
                url=url,
                source=self.name,
                title=item.get("title", ""),
                content=item.get("description", item.get("desc", "")),
                author=item.get("author", item.get("owner", {}).get("name", "")),
                source_detail=detail,
            ):
                new_count += 1
        return new_count
