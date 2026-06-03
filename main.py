#!/usr/bin/env python3
"""InfoPipeline - Personal information collection & aggregation pipeline.

Usage:
    python main.py --collect       # Run all collectors
    python main.py --analyze       # Run LLM analysis on unanalyzed items
    python main.py --report        # Generate today's report
    python main.py --push          # Push today's report to distributors
    python main.py --run            # Full pipeline: collect → analyze → report → push
    python main.py --web           # Start web UI server
    python main.py --once          # Alias for --run
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def load_config():
    """Load and validate config."""
    from lib.config import load
    return load()


def run_collectors(collector_names: list[str] | None = None):
    """Run data collectors."""
    from lib.db import init_db
    from lib.config import get

    init_db()
    collector_cfg = get("collectors", {})

    total_new = 0

    # Import and instantiate collectors
    collectors_map = {
        "reddit": ("collectors.reddit", "RedditCollector"),
        "hackernews": ("collectors.hackernews", "HackerNewsCollector"),
        "twitter": ("collectors.twitter", "TwitterCollector"),
        "bilibili": ("collectors.bilibili", "BilibiliCollector"),
        "zhihu": ("collectors.zhihu", "ZhihuCollector"),
        "weibo": ("collectors.weibo", "WeiboCollector"),
        "rss": ("collectors.rss", "RSSCollector"),
        "github_trending": ("collectors.github_trending", "GitHubTrendingCollector"),
        "indie_games": ("collectors.indie_games", "IndieGamesCollector"),
    }

    names = collector_names or [k for k, v in collector_cfg.items() if v.get("enabled", False)]

    for name in names:
        if name not in collector_cfg:
            print(f"[SKIP] {name}: not in config")
            continue
        if not collector_cfg[name].get("enabled", False):
            print(f"[SKIP] {name}: disabled")
            continue

        if name not in collectors_map:
            print(f"[WARN] {name}: no collector implementation")
            continue

        module_path, class_name = collectors_map[name]
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            collector = cls(collector_cfg[name])
            print(f"[COLLECT] {name}...")
            start = time.time()
            new_count = collector.collect()
            elapsed = time.time() - start
            print(f"[COLLECT] {name}: {new_count} new items ({elapsed:.1f}s)")
            total_new += new_count
        except Exception as e:
            print(f"[ERROR] {name}: {e}")

    print(f"\n[COLLECT] Total: {total_new} new items collected")
    return total_new


def run_analysis():
    """Run LLM analysis on unanalyzed items."""
    from lib.db import init_db
    from processors.analyzer import run_analysis

    init_db()
    run_analysis()


def run_report(date_str: str | None = None):
    """Generate report for a date."""
    from lib.db import init_db, save_report, get_items_for_report
    from lib.llm import generate_report
    from lib.config import get

    init_db()

    if date_str is None:
        tz = timezone(timedelta(hours=8))  # Asia/Shanghai
        date_str = datetime.now(tz).strftime("%Y-%m-%d")

    min_score = get("processor.min_score", 3)
    limit = get("processor.max_items_per_category", 20)
    categories_items = get_items_for_report(date_str, min_score=min_score, limit_per_category=limit)

    if not categories_items:
        print(f"[REPORT] No analyzed items for {date_str}")
        return None

    content = generate_report(categories_items, date_str)

    # Save to DB
    save_report(date_str, "daily", content)

    # Also save to file
    output_dir = get("storage.output_dir")
    date_parts = date_str.split("-")
    file_dir = Path(output_dir) / date_parts[0] / date_parts[1]
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / f"{date_parts[2]}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    total = sum(len(v) for v in categories_items.values())
    print(f"[REPORT] Generated for {date_str}: {total} items, {len(categories_items)} categories")
    print(f"[REPORT] Saved to {file_path}")
    return content


def run_push(date_str: str | None = None):
    """Push report to all enabled distributors."""
    from lib.db import init_db, get_report
    from lib.config import get

    init_db()

    if date_str is None:
        tz = timezone(timedelta(hours=8))
        date_str = datetime.now(tz).strftime("%Y-%m-%d")

    content = get_report(date_str, "daily")
    if not content:
        # Try generating on the fly
        print(f"[PUSH] No cached report for {date_str}, generating...")
        content = run_report(date_str)
        if not content:
            print(f"[PUSH] Nothing to push for {date_str}")
            return

    dist_cfg = get("distributors", {})

    distributors_map = {
        "discord": ("distributors.discord", "DiscordDistributor"),
        "feishu": ("distributors.feishu", "FeishuDistributor"),
        "telegram": ("distributors.telegram", "TelegramDistributor"),
    }

    for name, cfg in dist_cfg.items():
        if not cfg.get("enabled", False):
            continue
        if name not in distributors_map:
            continue

        module_path, class_name = distributors_map[name]
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            dist = cls(cfg)
            print(f"[PUSH] {name}...")
            dist.send(f"InfoPipeline 日报 — {date_str}", content)
        except Exception as e:
            print(f"[ERROR] {name}: {e}")

    # OpenClaw webhook notification
    oc_cfg = dist_cfg.get("openclaw", {})
    if oc_cfg.get("enabled", False):
        try:
            import httpx
            gateway_url = oc_cfg.get("gateway_url", "")
            gateway_token = oc_cfg.get("gateway_token", "")
            resp = httpx.post(
                f"{gateway_url}/api/webhook/report",
                headers={"Authorization": f"Bearer {gateway_token}"},
                json={
                    "date": date_str,
                    "status": "complete",
                    "message": f"InfoPipeline report for {date_str} generated and pushed.",
                },
                timeout=10,
            )
            print(f"[PUSH] OpenClaw notification sent")
        except Exception as e:
            print(f"[WARN] OpenClaw notification failed: {e}")

    print("[PUSH] All distributors notified")


def run_full_pipeline(date_str: str | None = None):
    """Run the complete pipeline: collect → analyze → report → push."""
    print("=" * 60)
    print(f"InfoPipeline - Full Run ({date_str or 'today'})")
    print("=" * 60)

    start = time.time()

    print("\n📋 Step 1: Collecting...")
    run_collectors()

    print("\n🤖 Step 2: Analyzing...")
    run_analysis()

    print("\n📝 Step 3: Generating report...")
    run_report(date_str)

    print("\n📤 Step 4: Pushing...")
    run_push(date_str)

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"✅ Pipeline complete ({elapsed:.1f}s)")
    print(f"{'=' * 60}")


def run_web():
    """Start the web UI server."""
    from lib.db import init_db
    from lib.config import get
    from web.server import run_server

    init_db()

    web_cfg = get("web", {})
    host = web_cfg.get("host", "127.0.0.1")
    port = web_cfg.get("port", 3456)

    run_server(host=host, port=port)


def main():
    parser = argparse.ArgumentParser(description="InfoPipeline - Information collection pipeline")
    parser.add_argument("--collect", action="store_true", help="Run collectors only")
    parser.add_argument("--analyze", action="store_true", help="Run LLM analysis only")
    parser.add_argument("--report", action="store_true", help="Generate report only")
    parser.add_argument("--push", action="store_true", help="Push report to distributors only")
    parser.add_argument("--run", action="store_true", help="Full pipeline: collect → analyze → report → push")
    parser.add_argument("--once", action="store_true", help="Alias for --run")
    parser.add_argument("--web", action="store_true", help="Start web UI server")
    parser.add_argument("--date", type=str, help="Specify date (YYYY-MM-DD) for report/push")
    parser.add_argument("--collectors", type=str, help="Comma-separated collector names to run")

    args = parser.parse_args()

    if not any([args.collect, args.analyze, args.report, args.push, args.run, args.once, args.web]):
        parser.print_help()
        sys.exit(1)

    load_config()

    if args.web:
        run_web()
    elif args.collect:
        names = args.collectors.split(",") if args.collectors else None
        run_collectors(names)
    elif args.analyze:
        run_analysis()
    elif args.report:
        run_report(args.date)
    elif args.push:
        run_push(args.date)
    elif args.run or args.once:
        run_full_pipeline(args.date)


if __name__ == "__main__":
    main()
