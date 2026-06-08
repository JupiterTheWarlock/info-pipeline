"""Zhihu collector via opencli."""

from typing import Any

from collectors.shared import run_opencli


class ZhihuCollector:
    name = "zhihu"

    def __init__(self, config: dict[str, Any]):
        self.keywords = config.get("keywords", [])
        self.limit = config.get("limit", 30)
        self.last_errors: list[str] = []

    def collect(self) -> int:
        count = 0
        self.last_errors = []
        for kw in self.keywords:
            count += self._search(kw)
        return count

    def _search(self, keyword: str) -> int:
        items, err = run_opencli(
            "opencli", "zhihu", "search",
            keyword, "--limit", str(self.limit), "-f", "yaml",
        )
        if err:
            if "command not found" in err.lower() or "not found" not in err.lower():
                msg = f"search '{keyword}': {err[:100]}"
                self.last_errors.append(msg)
                print(f"[WARN] Zhihu {msg}")
            return 0

        from lib.db import insert_item
        new_count = 0
        for item in items:
            url = item.get("url", "")
            if not url:
                continue
            if insert_item(
                url=url,
                source=self.name,
                title=item.get("title", item.get("question", "")),
                content=item.get("content", item.get("excerpt", "")),
                author=item.get("author", ""),
                source_detail=f"搜索:{keyword}",
            ):
                new_count += 1
        return new_count
