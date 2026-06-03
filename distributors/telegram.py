"""Telegram bot distributor."""

import httpx
from typing import Any


class TelegramDistributor:
    name = "telegram"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.bot_token = config.get("bot_token", "")
        self.chat_id = config.get("chat_id", "")

    def send(self, title: str, content: str) -> bool:
        if not self.bot_token or not self.chat_id:
            print("[WARN] Telegram: no bot_token or chat_id configured")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        full_text = f"📡 *{title}*\n\n{content}"

        # Telegram has 4096 char limit
        max_len = 4000
        chunks = []
        if len(full_text) <= max_len:
            chunks.append(full_text)
        else:
            lines = full_text.split("\n")
            current = ""
            for line in lines:
                if len(current) + len(line) + 1 > max_len:
                    chunks.append(current)
                    current = line + "\n"
                else:
                    current += line + "\n"
            if current.strip():
                chunks.append(current)

        for chunk in chunks:
            try:
                resp = httpx.post(
                    url,
                    json={
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "parse_mode": "Markdown",
                    },
                    timeout=30,
                )
                resp.raise_for_status()
            except Exception as e:
                print(f"[ERROR] Telegram: {e}")
                return False

        print(f"[TELEGRAM] Sent {len(chunks)} chunks")
        return True
