"""Shared fixtures for info-pipeline tests."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config.yaml and patch lib.config to use it."""
    config_data = {
        "storage": {
            "db_path": str(tmp_path / "pipeline.db"),
            "output_dir": str(tmp_path / "output"),
        },
        "llm": {
            "base_url": "https://api.example.com/v1",
            "api_key": "test-key",
            "model": "test-model",
            "max_tokens": 1024,
            "timeout_seconds": 30,
        },
        "processor": {
            "categories": ["AI", "安全", "开源", "游戏", "其他"],
            "min_score": 3,
            "max_items_per_category": 20,
            "batch_size": 5,
        },
        "collectors": {
            "reddit": {"enabled": True, "subreddits": ["python"], "limit": 10},
            "hackernews": {"enabled": True, "limit": 10},
            "twitter": {"enabled": True, "keywords": ["AI"], "limit": 10},
            "bilibili": {"enabled": True, "keywords": ["AI"], "limit": 10},
            "zhihu": {"enabled": True, "keywords": ["AI"], "limit": 10},
            "weibo": {"enabled": True, "keywords": ["AI"], "limit": 10},
            "rss": {"enabled": True, "feeds": [{"url": "https://example.com/rss", "name": "test"}]},
            "github_trending": {"enabled": True, "languages": ["python"], "since": "daily"},
            "indie_games": {"enabled": True, "sources": [{"type": "rss", "url": "https://example.com/indie", "name": "indie"}]},
        },
        "distributors": {
            "discord": {"enabled": True, "webhook_url": "https://discord.com/webhook/test"},
            "telegram": {"enabled": True, "bot_token": "bot123", "chat_id": "chat456"},
            "feishu": {"enabled": True, "webhook_url": "https://feishu.cn/webhook/test"},
        },
        "web": {"host": "127.0.0.1", "port": 3456},
    }
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config_data, f)
    return config_path, config_data, tmp_path


@pytest.fixture
def loaded_config(tmp_config):
    """Load config from tmp_config and return it."""
    import lib.config as cfg_mod
    config_path, config_data, tmp_path = tmp_config

    # Reset global state
    cfg_mod._config = None
    cfg_mod._project_root = tmp_path

    with patch.object(cfg_mod.Path, "exists", return_value=True):
        loaded = cfg_mod.load()

    yield loaded, tmp_path

    cfg_mod._config = None
