"""Base collector interface."""

from abc import ABC, abstractmethod
from typing import Any

from lib.db import insert_item


class BaseCollector(ABC):
    """All collectors must implement `collect()` and return a count."""

    name: str = "base"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def collect(self) -> int:
        """Run collection. Returns number of new items inserted."""
        ...

    def _insert(
        self,
        url: str,
        title: str = "",
        content: str = "",
        author: str = "",
        published_at: float | None = None,
        source_detail: str = "",
        extra: dict | None = None,
    ) -> bool:
        return insert_item(
            url=url,
            source=self.name,
            title=title,
            content=content,
            author=author,
            published_at=published_at,
            source_detail=source_detail,
            extra=extra,
        )
