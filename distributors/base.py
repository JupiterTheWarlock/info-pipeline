"""Base distributor interface."""

from abc import ABC, abstractmethod
from typing import Any


class BaseDistributor(ABC):
    name: str = "base"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def send(self, title: str, content: str) -> bool:
        """Send a report. Returns True on success."""
        ...
