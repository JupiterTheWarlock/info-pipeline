"""linux.do collector using public Discourse JSON endpoints."""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import feedparser
import httpx

from lib.db import insert_item


class LinuxDoCollector:
    name = "linuxdo"

    def __init__(self, config: dict[str, Any]):
        self.base_url = config.get("base_url", "https://linux.do").rstrip("/")
        self.keywords = config.get("keywords", [])
        self.categories = config.get("categories", [])
        self.limit = int(config.get("limit", 50))
        self.timeout = int(config.get("timeout_seconds", 20))
        self.last_errors: list[str] = []

    def collect(self) -> int:
        topics: list[dict[str, Any]] = []
        errors: list[str] = []
        self.last_errors = []

        latest, err = self._get_topics("/latest.json")
        if err:
            errors.append(f"latest: {err}")
        topics.extend(latest)

        for category in self.categories:
            category_topics, err = self._get_topics(f"/c/{quote_plus(str(category))}.json")
            if err:
                errors.append(f"category {category}: {err}")
            topics.extend(category_topics)

        for keyword in self.keywords:
            search_topics, err = self._search(str(keyword))
            if err:
                errors.append(f"search {keyword}: {err}")
            topics.extend(search_topics)

        if errors:
            print("[WARN] linux.do: " + " | ".join(errors)[:500])

        topics = self._dedupe_topics(topics)
        if topics:
            return self._process(topics[: self.limit])

        rss_count = self._collect_rss()
        if rss_count == 0 and errors:
            self.last_errors.extend(errors)
        return rss_count

    def _get_topics(self, path: str) -> tuple[list[dict[str, Any]], str]:
        try:
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers={"User-Agent": "InfoPipeline/0.1"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("topic_list", {}).get("topics", []), ""
        except Exception as exc:
            return [], str(exc)

    def _search(self, keyword: str) -> tuple[list[dict[str, Any]], str]:
        try:
            resp = httpx.get(
                f"{self.base_url}/search.json",
                params={"q": keyword},
                headers={"User-Agent": "InfoPipeline/0.1"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            topics_by_id = {topic.get("id"): topic for topic in data.get("topics", [])}
            topics = []
            for post in data.get("posts", []):
                topic = dict(topics_by_id.get(post.get("topic_id"), {}))
                topic.setdefault("id", post.get("topic_id"))
                topic.setdefault("title", post.get("topic_title", ""))
                topic.setdefault("slug", post.get("topic_slug", ""))
                topic["matched_keyword"] = keyword
                topic["blurb"] = post.get("blurb", topic.get("excerpt", ""))
                topics.append(topic)
            return topics or list(topics_by_id.values()), ""
        except Exception as exc:
            return [], str(exc)

    def _dedupe_topics(self, topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[int | str] = set()
        deduped = []
        for topic in topics:
            topic_id = topic.get("id") or topic.get("topic_id") or topic.get("url")
            if not topic_id or topic_id in seen:
                continue
            seen.add(topic_id)
            deduped.append(topic)
        return deduped

    def _process(self, topics: list[dict[str, Any]]) -> int:
        new_count = 0
        for topic in topics:
            topic_id = topic.get("id") or topic.get("topic_id")
            if not topic_id:
                continue
            slug = topic.get("slug") or topic.get("topic_slug") or "topic"
            url = f"{self.base_url}/t/{slug}/{topic_id}"
            title = topic.get("title") or topic.get("fancy_title") or ""
            content = topic.get("blurb") or topic.get("excerpt") or ""
            published_at = _parse_discourse_time(topic.get("created_at"))
            source_detail = topic.get("matched_keyword") or topic.get("category_id") or "latest"
            posters = topic.get("posters") or [{}]
            if insert_item(
                url=url,
                source=self.name,
                title=title,
                content=content,
                author=str(topic.get("last_poster_username") or posters[0].get("user_id", "")),
                published_at=published_at,
                source_detail=str(source_detail),
                extra=topic,
            ):
                new_count += 1
        return new_count

    def _collect_rss(self) -> int:
        """Fallback to public Discourse RSS feeds when JSON endpoints are blocked."""
        entries = []
        for path in ("/latest.rss", "/top.rss"):
            try:
                feed = feedparser.parse(f"{self.base_url}{path}")
                entries.extend(feed.entries)
            except Exception as exc:
                self.last_errors.append(f"rss {path}: {exc}")

        deduped = []
        seen = set()
        for entry in entries:
            link = entry.get("link", "")
            if not link or link in seen:
                continue
            seen.add(link)
            text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
            if self.keywords and not any(str(keyword).lower() in text for keyword in self.keywords):
                continue
            deduped.append(entry)
            if len(deduped) >= self.limit:
                break

        new_count = 0
        for entry in deduped:
            if insert_item(
                url=entry.get("link", ""),
                source=self.name,
                title=entry.get("title", ""),
                content=entry.get("summary", ""),
                author=entry.get("author", ""),
                source_detail="rss",
                extra={"fallback": "linuxdo_rss"},
            ):
                new_count += 1
        if entries and not deduped:
            self.last_errors.append("rss: entries found but none matched configured keywords")
        return new_count


def _parse_discourse_time(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None
