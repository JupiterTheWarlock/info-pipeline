"""GitHub Trending collector via web scraping."""

import re
from typing import Any
from datetime import datetime, timezone

import httpx

from lib.db import insert_item


class GitHubTrendingCollector:
    name = "github_trending"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.languages = config.get("languages", [])
        self.since = config.get("since", "daily")

    def collect(self) -> int:
        count = 0
        if self.languages:
            for lang in self.languages:
                count += self._fetch_trending(lang)
        else:
            count = self._fetch_trending(None)
        return count

    def _fetch_trending(self, language: str | None) -> int:
        url = "https://github.com/trending"
        if language:
            url += f"/{language}"
        if self.since and self.since != "daily":
            url += f"?since={self.since}"

        try:
            resp = httpx.get(url, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            repos = self._parse_html(resp.text, language or "all")
            new_count = 0
            for repo in repos:
                if insert_item(
                    url=repo["url"],
                    source=self.name,
                    title=repo["name"],
                    content=repo["description"],
                    source_detail=f"trending/{language or 'all'}",
                    extra={"stars": repo.get("stars"), "language": language},
                ):
                    new_count += 1
            return new_count
        except Exception as e:
            print(f"[ERROR] GitHub Trending {language}: {e}")
            return 0

    def _parse_html(self, html: str, language: str) -> list[dict]:
        """Parse GitHub trending page for repo info."""
        repos = []
        # Match article tags that contain repo info
        article_pattern = re.compile(
            r'<article[^>]*class="Box-row"[^>]*>(.*?)</article>',
            re.DOTALL,
        )
        for match in article_pattern.finditer(html):
            content = match.group(1)

            # Extract repo name
            name_match = re.search(r'<h2[^>]*>.*?<a[^>]*href="/([^"]+)"[^>]*>(.*?)</a>', content, re.DOTALL)
            if not name_match:
                continue
            repo_path = name_match.group(1)
            repo_name = repo_path.replace("/", " / ").strip()

            # Extract description
            desc_match = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', content, re.DOTALL)
            description = ""
            if desc_match:
                description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()

            # Extract stars
            stars_match = re.search(r'href="/[^"]+/stargazers"[^>]*>\s*([\d,]+)\s*<', content)
            stars = 0
            if stars_match:
                stars = int(stars_match.group(1).replace(",", ""))

            repos.append({
                "url": f"https://github.com/{repo_path}",
                "name": repo_name,
                "description": description,
                "stars": stars,
            })
        return repos
