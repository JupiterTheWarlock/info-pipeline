"""Tests for collectors."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import lib.config as cfg_mod


def _setup_config(tmp_path):
    import yaml
    config = {
        "storage": {"db_path": str(tmp_path / "test.db"), "output_dir": str(tmp_path / "output")},
        "processor": {"categories": ["AI"], "min_score": 3, "max_items_per_category": 20},
    }
    with open(tmp_path / "config.yaml", "w") as f:
        yaml.dump(config, f)
    cfg_mod._config = None
    cfg_mod._project_root = tmp_path
    from lib.db import init_db
    init_db()
    return tmp_path


def _teardown():
    cfg_mod._config = None


def _mock_subprocess_ok(json_lines):
    output = "\n".join(json.dumps(l) for l in json_lines)
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = output
    mock.stderr = ""
    return mock


def _mock_insert():
    """Mock BaseCollector._insert to avoid abstract class instantiation."""
    return patch("collectors.base.BaseCollector._insert", return_value=True)


class TestRedditCollector:
    def test_collect_parses_output(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"url": "https://reddit.com/1", "title": "Post 1", "selftext": "Body", "author": "user1"}]
        mock_result = _mock_subprocess_ok(items)

        with patch("collectors.reddit.subprocess.run", return_value=mock_result), _mock_insert():
            from collectors.reddit import RedditCollector
            c = RedditCollector({"subreddits": ["python"], "limit": 10})
            assert c.collect() == 1
        _teardown()

    def test_collect_empty(self, tmp_path):
        _setup_config(tmp_path)
        mock_result = _mock_subprocess_ok([])

        with patch("collectors.reddit.subprocess.run", return_value=mock_result):
            from collectors.reddit import RedditCollector
            c = RedditCollector({"subreddits": ["python"], "limit": 10})
            assert c.collect() == 0
        _teardown()


class TestHackerNewsCollector:
    def test_collect(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"url": "https://news.com/1", "title": "HN Post", "text": "Desc", "by": "user"}]
        mock_result = _mock_subprocess_ok(items)

        with patch("collectors.hackernews.subprocess.run", return_value=mock_result), _mock_insert():
            from collectors.hackernews import HackerNewsCollector
            c = HackerNewsCollector({"limit": 10})
            assert c.collect() == 1
        _teardown()


class TestTwitterCollector:
    def test_collect_with_keywords(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"url": "https://x.com/1", "text": "Tweet text", "username": "user"}]
        mock_result = _mock_subprocess_ok(items)

        with patch("collectors.twitter.subprocess.run", return_value=mock_result), _mock_insert():
            from collectors.twitter import TwitterCollector
            c = TwitterCollector({"keywords": ["AI"], "accounts": [], "limit": 10})
            assert c.collect() == 1
        _teardown()

    def test_collect_timeline(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"url": "https://x.com/2", "text": "Timeline tweet", "username": "user"}]
        mock_result = _mock_subprocess_ok(items)

        with patch("collectors.twitter.subprocess.run", return_value=mock_result), _mock_insert():
            from collectors.twitter import TwitterCollector
            c = TwitterCollector({"keywords": [], "accounts": [], "limit": 10})
            assert c.collect() == 1
        _teardown()


class TestBilibiliCollector:
    def test_collect_with_keywords(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"url": "https://bilibili.com/video/1", "title": "Video", "description": "Desc"}]
        mock_result = _mock_subprocess_ok(items)

        with patch("collectors.bilibili.subprocess.run", return_value=mock_result), _mock_insert():
            from collectors.bilibili import BilibiliCollector
            c = BilibiliCollector({"keywords": ["AI"], "limit": 10})
            assert c.collect() == 1
        _teardown()

    def test_collect_hot(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"url": "https://bilibili.com/video/2", "title": "Hot Video"}]
        mock_result = _mock_subprocess_ok(items)

        with patch("collectors.bilibili.subprocess.run", return_value=mock_result), _mock_insert():
            from collectors.bilibili import BilibiliCollector
            c = BilibiliCollector({"keywords": [], "limit": 10})
            assert c.collect() == 1
        _teardown()


class TestZhihuCollector:
    def test_collect(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"url": "https://zhihu.com/q/1", "title": "Question", "content": "Detail"}]
        mock_result = _mock_subprocess_ok(items)

        with patch("collectors.zhihu.subprocess.run", return_value=mock_result), _mock_insert():
            from collectors.zhihu import ZhihuCollector
            c = ZhihuCollector({"keywords": ["AI"], "limit": 10})
            assert c.collect() == 1
        _teardown()


class TestWeiboCollector:
    def test_collect(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"url": "https://weibo.com/1", "text": "微博内容", "user": {"screen_name": "user"}}]
        mock_result = _mock_subprocess_ok(items)

        with patch("collectors.weibo.subprocess.run", return_value=mock_result), _mock_insert():
            from collectors.weibo import WeiboCollector
            c = WeiboCollector({"keywords": ["AI"], "limit": 10})
            assert c.collect() == 1
        _teardown()


class TestRSSCollector:
    def test_collect(self, tmp_path):
        _setup_config(tmp_path)
        mock_entry = MagicMock()
        mock_entry.get = lambda k, d="": {"link": "https://blog.com/1", "title": "Post 1", "summary": "Content", "author": "auth"}.get(k, d)
        mock_entry.link = "https://blog.com/1"
        mock_entry.title = "Post 1"
        mock_entry.summary = "Content"
        mock_entry.author = "auth"
        mock_entry.published_parsed = None
        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]

        with patch("collectors.rss.feedparser.parse", return_value=mock_feed), \
             patch("lib.db.insert_item", return_value=True) as mock_ins:
            from collectors.rss import RSSCollector
            c = RSSCollector({"feeds": [{"url": "https://blog.com/rss", "name": "Blog"}]})
            assert c.collect() == 1
            mock_ins.assert_called()
        _teardown()

    def test_collect_empty_feed(self, tmp_path):
        _setup_config(tmp_path)
        mock_feed = MagicMock()
        mock_feed.entries = []

        with patch("collectors.rss.feedparser.parse", return_value=mock_feed):
            from collectors.rss import RSSCollector
            c = RSSCollector({"feeds": [{"url": "https://blog.com/rss"}]})
            assert c.collect() == 0
        _teardown()


class TestGitHubTrendingCollector:
    def test_collect(self, tmp_path):
        _setup_config(tmp_path)
        html = '''<article class="Box-row">
            <h2><a href="/user/repo">repo</a></h2>
            <p class="col-9">A cool project</p>
            <a href="/user/repo/stargazers">1,234</a>
        </article>'''
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()

        with patch("collectors.github_trending.httpx.get", return_value=mock_resp), \
             patch("collectors.github_trending.insert_item", return_value=True):
            from collectors.github_trending import GitHubTrendingCollector
            c = GitHubTrendingCollector({"languages": ["python"], "since": "daily"})
            assert c.collect() == 1
        _teardown()


class TestIndieGamesCollector:
    def test_collect_rss(self, tmp_path):
        _setup_config(tmp_path)
        mock_feed = MagicMock()
        mock_feed.entries = [
            MagicMock(link="https://indie.com/1", title="Indie Game", summary="Cool game"),
        ]

        with patch("collectors.indie_games.feedparser.parse", return_value=mock_feed), \
             patch("lib.db.insert_item", return_value=True):
            from collectors.indie_games import IndieGamesCollector
            c = IndieGamesCollector({"sources": [{"type": "rss", "url": "https://indie.com/rss", "name": "indie"}], "limit": 10})
            assert c.collect() == 1
        _teardown()
