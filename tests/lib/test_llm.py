"""Tests for lib.llm."""

import json
from unittest.mock import MagicMock, patch

import lib.config as cfg_mod


def _setup_config(tmp_path):
    import yaml
    config = {
        "storage": {"db_path": str(tmp_path / "test.db"), "output_dir": str(tmp_path / "output")},
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
        },
    }
    with open(tmp_path / "config.yaml", "w") as f:
        yaml.dump(config, f)
    cfg_mod._config = None
    cfg_mod._project_root = tmp_path


class TestCallLlm:
    def test_call_llm_sends_correct_request(self, tmp_path):
        _setup_config(tmp_path)
        cfg_mod._config = None
        cfg_mod._project_root = tmp_path

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Hello"}}]}
        mock_resp.raise_for_status = MagicMock()

        with patch("lib.llm.httpx.post", return_value=mock_resp) as mock_post:
            from lib.llm import call_llm
            result = call_llm("test prompt", system="sys")

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            assert "chat/completions" in call_kwargs[0][0] or "chat/completions" in str(call_kwargs)
            assert result == "Hello"
        cfg_mod._config = None


class TestAnalyzeItems:
    def test_normal_json_response(self, tmp_path):
        _setup_config(tmp_path)
        items = [
            {"id": 1, "title": "AI breakthrough", "source": "test", "url": "https://example.com/1"},
            {"id": 2, "title": "Security flaw", "source": "test", "url": "https://example.com/2"},
        ]
        llm_response = json.dumps([
            {"index": 1, "category": "AI", "score": 8, "summary": "Big AI news"},
            {"index": 2, "category": "安全", "score": 6, "summary": "Vuln found"},
        ])

        with patch("lib.llm.call_llm", return_value=llm_response):
            from lib.llm import analyze_items
            result = analyze_items(items)
            assert len(result) == 2
            assert result[0]["category"] == "AI"
            assert result[0]["score"] == 8.0
            assert result[1]["category"] == "安全"
        cfg_mod._config = None

    def test_normalizes_shorthand_category(self):
        from lib.llm import normalize_category

        categories = [
            "Indie Game / 独立游戏",
            "AI Engineering / AI 工程",
            "Other / 其他",
        ]
        assert normalize_category("Indie Game", categories) == "Indie Game / 独立游戏"
        assert normalize_category("AI 工程", categories) == "AI Engineering / AI 工程"
        assert normalize_category("Unknown", categories) == "Other / 其他"

    def test_prompt_includes_item_content(self, tmp_path):
        _setup_config(tmp_path)
        items = [
            {
                "id": 1,
                "title": "Unique indie AI launch post",
                "source": "test",
                "url": "https://example.com/unique",
                "content": "Unique content marker",
            },
        ]
        llm_response = json.dumps([
            {"index": 1, "category": "AI", "score": 8, "summary": "Big AI news"},
        ])

        with patch("lib.llm.call_llm", return_value=llm_response) as mock_call:
            from lib.llm import analyze_items
            analyze_items(items)
            prompt = mock_call.call_args.args[0]
            assert "Unique indie AI launch post" in prompt
            assert "Unique content marker" in prompt
        cfg_mod._config = None

    def test_markdown_code_block_json(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"id": 1, "title": "Test", "source": "test", "url": "https://example.com/1"}]
        llm_response = '```json\n[{"index": 1, "category": "AI", "score": 7, "summary": "Summary"}]\n```'

        with patch("lib.llm.call_llm", return_value=llm_response):
            from lib.llm import analyze_items
            result = analyze_items(items)
            assert result[0]["category"] == "AI"
        cfg_mod._config = None

    def test_parse_failure_fallback(self, tmp_path):
        _setup_config(tmp_path)
        items = [{"id": 1, "title": "Test", "source": "test", "url": "https://example.com/1"}]

        with patch("lib.llm.call_llm", return_value="This is not JSON at all"):
            from lib.llm import analyze_items
            result = analyze_items(items)
            assert result[0]["category"] == "其他"
            assert result[0]["score"] == 3.0
        cfg_mod._config = None


class TestGenerateReport:
    def test_generates_markdown(self):
        from lib.llm import generate_report
        categories_items = {
            "AI": [
                {"title": "AI News", "url": "https://example.com", "score": 8, "summary": "Big news", "source": "test", "source_detail": ""},
            ],
        }
        report = generate_report(categories_items, "2026-01-01")
        assert "# 📡 InfoPipeline 日报" in report
        assert "2026-01-01" in report
        assert "AI" in report
        assert "AI News" in report
        assert "⭐" in report  # score >= 8

    def test_empty_categories(self):
        from lib.llm import generate_report
        report = generate_report({}, "2026-01-01")
        assert "0" in report  # total = 0
