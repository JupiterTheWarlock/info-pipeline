"""LLM analyzer processor."""

from typing import Any

from lib.config import get
from lib.db import get_unanalyzed, update_analysis
from lib.llm import analyze_items


def run_analysis():
    """Fetch unanalyzed items, batch process with LLM, update DB."""
    batch_size = get("processor.batch_size", 10)

    while True:
        items = get_unanalyzed(limit=batch_size)
        if not items:
            break

        print(f"[ANALYZE] Processing {len(items)} items...")
        analyzed = analyze_items(items)

        for item in analyzed:
            item_id = item["id"]
            update_analysis(
                item_id=item_id,
                category=item.get("category", "其他"),
                score=float(item.get("score", 3)),
                summary=item.get("summary", ""),
                preference_score=float(item.get("preference_score", 0)),
                why_relevant=item.get("why_relevant", ""),
                risk=item.get("risk", ""),
                tags=item.get("tags", []),
            )
        print(f"[ANALYZE] Batch done")

    print("[ANALYZE] All items analyzed")
