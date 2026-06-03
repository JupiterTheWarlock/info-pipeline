"""Tests for distributors."""

from unittest.mock import MagicMock, patch


class TestDiscordDistributor:
    def test_send_short_message(self):
        from distributors.discord import DiscordDistributor
        d = DiscordDistributor({"webhook_url": "https://discord.com/webhook/test"})
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("distributors.discord.httpx.post", return_value=mock_resp) as mock_post:
            result = d.send("Test Report", "Short content")
            assert result is True
            mock_post.assert_called_once()
            payload = mock_post.call_args[1]["json"]
            assert "Test Report" in payload["content"]

    def test_send_no_webhook(self):
        from distributors.discord import DiscordDistributor
        d = DiscordDistributor({"webhook_url": ""})
        assert d.send("Title", "Content") is False

    def test_long_message_splitting(self):
        from distributors.discord import DiscordDistributor
        d = DiscordDistributor({"webhook_url": "https://discord.com/webhook/test"})
        long_content = "\n".join([f"Line {i} " + "x" * 100 for i in range(30)])
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("distributors.discord.httpx.post", return_value=mock_resp) as mock_post:
            result = d.send("Report", long_content)
            assert result is True
            assert mock_post.call_count > 1


class TestTelegramDistributor:
    def test_send(self):
        from distributors.telegram import TelegramDistributor
        d = TelegramDistributor({"bot_token": "tok", "chat_id": "123"})
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("distributors.telegram.httpx.post", return_value=mock_resp) as mock_post:
            assert d.send("Report", "Content") is True
            payload = mock_post.call_args[1]["json"]
            assert payload["chat_id"] == "123"
            assert "Markdown" in payload["parse_mode"]

    def test_send_no_config(self):
        from distributors.telegram import TelegramDistributor
        d = TelegramDistributor({"bot_token": "", "chat_id": ""})
        assert d.send("Title", "Content") is False


class TestFeishuDistributor:
    def test_send(self):
        from distributors.feishu import FeishuDistributor
        d = FeishuDistributor({"webhook_url": "https://feishu.cn/webhook/test"})
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("distributors.feishu.httpx.post", return_value=mock_resp) as mock_post:
            assert d.send("Report", "Content") is True
            payload = mock_post.call_args[1]["json"]
            assert payload["msg_type"] == "interactive"

    def test_send_no_webhook(self):
        from distributors.feishu import FeishuDistributor
        d = FeishuDistributor({"webhook_url": ""})
        assert d.send("Title", "Content") is False
