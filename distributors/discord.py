"""Discord webhook distributor."""

import httpx
from typing import Any


class DiscordDistributor:
    name = "discord"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.webhook_url = config.get("webhook_url", "")
        self.channel_id = config.get("channel_id", "")

    def send(self, title: str, content: str) -> bool:
        if not self.webhook_url:
            print("[WARN] Discord: no webhook_url configured")
            return False

        # Discord has 2000 char limit, split if needed
        max_len = 1900
        chunks = []
        if len(content) <= max_len:
            chunks.append(content)
        else:
            lines = content.split("\n")
            current = ""
            for line in lines:
                if len(current) + len(line) + 1 > max_len:
                    chunks.append(current)
                    current = line + "\n"
                else:
                    current += line + "\n"
            if current.strip():
                chunks.append(current)

        for i, chunk in enumerate(chunks):
            payload = {
                "content": chunk,
                "username": "InfoPipeline 📡",
            }
            if i == 0:
                payload["content"] = f"## {title}\n\n{chunk}"

            try:
                resp = httpx.post(self.webhook_url, json=payload, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                print(f"[ERROR] Discord: {e}")
                return False

        print(f"[DISCORD] Sent {len(chunks)} chunks")
        return True
