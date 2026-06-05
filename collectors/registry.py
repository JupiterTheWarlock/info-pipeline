"""Collector registry and execution helpers."""

from dataclasses import dataclass, field
from importlib import import_module
from time import time
from typing import Any


@dataclass(frozen=True)
class CollectorSpec:
    module: str
    class_name: str
    display_name: str
    built_in: bool = True


BUILT_IN_COLLECTORS: dict[str, CollectorSpec] = {
    "reddit": CollectorSpec("collectors.reddit", "RedditCollector", "Reddit"),
    "hackernews": CollectorSpec("collectors.hackernews", "HackerNewsCollector", "Hacker News"),
    "twitter": CollectorSpec("collectors.twitter", "TwitterCollector", "X / Twitter"),
    "bilibili": CollectorSpec("collectors.bilibili", "BilibiliCollector", "Bilibili"),
    "zhihu": CollectorSpec("collectors.zhihu", "ZhihuCollector", "知乎"),
    "weibo": CollectorSpec("collectors.weibo", "WeiboCollector", "微博"),
    "rss": CollectorSpec("collectors.rss", "RSSCollector", "RSS"),
    "github_trending": CollectorSpec("collectors.github_trending", "GitHubTrendingCollector", "GitHub Trending"),
    "indie_games": CollectorSpec("collectors.indie_games", "IndieGamesCollector", "Indie Games"),
    "linuxdo": CollectorSpec("collectors.linuxdo", "LinuxDoCollector", "linux.do"),
}


@dataclass
class CollectorRunResult:
    name: str
    new_count: int = 0
    seen_count: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: float = 0
    finished_at: float = 0

    @property
    def elapsed(self) -> float:
        if not self.started_at or not self.finished_at:
            return 0
        return self.finished_at - self.started_at


def collector_specs(configs: dict[str, dict[str, Any]] | None = None) -> dict[str, CollectorSpec]:
    """Return built-in collectors plus config-declared plugin collectors.

    A config-declared plugin uses:
      collectors.<name>.module: "package.module"
      collectors.<name>.class: "CollectorClass"
    """
    specs = dict(BUILT_IN_COLLECTORS)
    for name, cfg in (configs or {}).items():
        module_path = cfg.get("module")
        class_name = cfg.get("class")
        if module_path and class_name:
            specs[name] = CollectorSpec(
                module=str(module_path),
                class_name=str(class_name),
                display_name=str(cfg.get("display_name") or name),
                built_in=False,
            )
    return specs


def available_collectors(configs: dict[str, dict[str, Any]] | None = None) -> list[str]:
    return sorted(collector_specs(configs))


def collector_metadata(configs: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    specs = collector_specs(configs)
    return [
        {
            "name": name,
            "display_name": spec.display_name,
            "module": spec.module,
            "class": spec.class_name,
            "built_in": spec.built_in,
            "configured": name in (configs or {}),
            "enabled": bool((configs or {}).get(name, {}).get("enabled", False)),
        }
        for name, spec in sorted(specs.items())
    ]


def load_collector(name: str, config: dict[str, Any], configs: dict[str, dict[str, Any]] | None = None):
    specs = collector_specs(configs)
    if name not in specs:
        raise KeyError(f"unknown collector: {name}")
    spec = specs[name]
    module = import_module(spec.module)
    cls = getattr(module, spec.class_name)
    return cls(config)


def run_collector(
    name: str,
    config: dict[str, Any],
    configs: dict[str, dict[str, Any]] | None = None,
) -> CollectorRunResult:
    result = CollectorRunResult(name=name, started_at=time())
    try:
        collector = load_collector(name, config, configs)
        collected = collector.collect()
        if isinstance(collected, CollectorRunResult):
            return collected
        result.new_count = int(collected or 0)
        result.seen_count = result.new_count
        result.errors.extend(str(e) for e in getattr(collector, "last_errors", []) if e)
    except Exception as exc:
        result.errors.append(str(exc))
    finally:
        result.finished_at = time()
    return result
