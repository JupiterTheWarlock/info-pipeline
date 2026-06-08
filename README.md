# InfoPipeline 📡

> Personal information collection & aggregation pipeline.
> Collect from multiple platforms → deduplicate → LLM analyze → push reports.

## Architecture

```
System Cron (crontab / systemd timer)
  └─ main.py (entry point)
       ├─ Collectors  — opencli, RSS, web_fetch, Firecrawl
       ├─ Processor   — dedup, categorize, LLM score/summarize
       ├─ Distributor — Discord webhook, Feishu, Telegram
       └─ Web UI      — browse historical reports by date
```

## Features

- **Multi-source collection**: Reddit, HackerNews, Twitter/X, Bilibili, Zhihu, Weibo, RSS, GitHub Trending
- **LLM-powered analysis**: auto-categorization, importance scoring, summarization
- **Deduplication**: URL hash based, no duplicate pushes
- **Multi-channel delivery**: Discord, Feishu, Telegram
- **Web UI**: treeview interface to browse collected reports by date
- **Config-driven**: add new sources by editing `config.yaml`

## Quick Start

```bash
# 1. Clone
git clone https://github.com/JupiterTheWarlock/info-pipeline.git
cd info-pipeline

# 2. Setup
cp config.yaml.example config.yaml
# Edit config.yaml with your API keys and data sources

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run once (test)
python main.py --once

# 5. Start web UI
python main.py --web

# 6. Setup cron (after verifying it works)
crontab -e
# Add lines based on your schedule (see config.yaml schedule section)
```

## Requirements

- Python 3.11+
- [opencli](https://github.com/nicepkg/opencli) (for social media scraping)
- Chrome/Chromium (for opencli browser automation)
- An LLM API endpoint (OpenAI-compatible, e.g. new-api)

## Project Structure

```
info-pipeline/
├── config.yaml.example   # Configuration template
├── config.yaml           # Your config (gitignored)
├── main.py               # Entry point
├── collectors/           # Platform-specific data collectors
│   ├── __init__.py
│   ├── base.py           # Base collector interface
│   ├── reddit.py
│   ├── hackernews.py
│   ├── twitter.py
│   ├── bilibili.py
│   ├── zhihu.py
│   ├── weibo.py
│   ├── rss.py
│   ├── github_trending.py
│   └── indie_games.py
├── processors/           # Data processing pipeline
│   ├── __init__.py
│   ├── dedup.py          # Deduplication
│   └── analyzer.py       # LLM analysis & scoring
├── distributors/         # Report delivery
│   ├── __init__.py
│   ├── base.py
│   ├── discord.py
│   ├── feishu.py
│   └── telegram.py
├── web/                  # Frontend + API server
│   ├── index.html        # Dashboard shell
│   ├── app.js            # Browser interactions
│   ├── style.css         # Responsive dark tool UI
│   └── server.py         # Static files and JSON API
├── lib/                  # Shared utilities
│   ├── __init__.py
│   ├── db.py             # SQLite operations
│   ├── llm.py            # LLM client
│   └── config.py         # Config loader
├── data/                 # Runtime data (gitignored)
│   └── pipeline.db
├── output/               # Generated reports (gitignored)
│   └── 2026/
│       └── 06/
│           └── 03.md
└── requirements.txt
```

## License

MIT
