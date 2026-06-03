"""Feishu webhook distributor."""

import httpx
from typing import Any


class FeishuDistributor:
    name = "feishu"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.webhook_url = config.get("webhook_url", "")

    def send(self, title: str, content: str) -> bool:
        if not self.webhook_url:
            print("[WARN] Feishu: no webhook_url configured")
            return False

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"📡 {title}"},
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content[:4000],  # Feishu limit
                    }
                ],
            }
        }

        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=30)
            resp.raise_for_status()
            print("[FEISHU] Sent")
            return True
        except Exception as e:
            print(f"[ERROR] Feishu: {e}")
            return False
