# InfoPipeline Evaluation Log

Date: 2026-06-05

## Scope

This evaluation covers the first implementation pass for:

- UI refactor into a compact developer dashboard.
- DeepSeek AI integration.
- Config-driven collector plugin architecture.
- First-source collection attempt for X / Twitter, Reddit, linux.do, and Zhihu.
- Preference focus on indie games and AI.

## Commands Run

```powershell
python -m pip install -r requirements.txt
python main.py --collect --collectors twitter,reddit,linuxdo,zhihu
$env:DEEPSEEK_API_KEY='***'; python main.py --analyze
$env:DEEPSEEK_API_KEY='***'; python main.py --report
python main.py --web
python -m pytest
```

The real API key was passed only through process environment variables during evaluation and was not written to tracked files.

## Test Result

```text
60 passed
```

## AI Evaluation

DeepSeek endpoint:

- `base_url`: `https://api.deepseek.com`
- `model`: `deepseek-v4-flash`

Temporary local sample:

```text
A solo developer shares Steam launch lessons for an indie tactics game using AI-assisted localization
```

Observed parsed result:

```text
category: Indie Game / 独立游戏
score: 7.0
preference_score: 8.0
has_summary: true
has_why_relevant: true
tags: 独立游戏, 本地化, AI工具, Steam发布
```

Finding:

- The endpoint, model, key, JSON parsing, and preference fields are working for a controlled sample.
- A prompt bug was found and fixed: `analyze_items()` built `items_text` but did not include it in the prompt, causing fallback parsing in the first evaluation.

## Collector Evaluation

### X / Twitter

Result:

```text
0 new items
```

Reason:

```text
command not found: opencli
```

Current state:

- Collector implementation exists.
- Config has indie-game and AI keywords.
- Runtime requires `opencli` installation and any required platform login/session setup.

### Reddit

Result:

```text
150 new items
```

Reason:

```text
opencli unavailable; JSON fallback was blocked with 403; RSS fallback succeeded
```

Current state:

- Collector implementation exists.
- Public JSON fallback exists.
- Public RSS fallback exists and collected real items in this environment.

### linux.do

Result:

```text
26 new items
```

Reason:

```text
403 Forbidden for latest.json and search.json; RSS fallback succeeded
```

Current state:

- Collector implementation exists using public Discourse JSON endpoints.
- JSON access appears to require accepted browser/session headers, login state, or another supported public API.
- Public RSS fallback exists and collected real items matching configured keywords in this environment.
- The collector does not bypass permissions.

## End-to-End Data Evaluation

After RSS fallback implementation:

```text
Collected: 176 items
Analyzed: 176 items
Report: output/2026/06/05.md
Report included: 117 scored items across 8 normalized categories
```

Source counts:

```text
reddit: 150
linuxdo: 26
```

Category normalization:

```text
Other / 其他: 45
Indie Game / 独立游戏: 41
AI Engineering / AI 工程: 32
Game Dev / 游戏开发: 19
AI Product / AI 产品: 15
Business / 商业化: 10
Tools / 工具链: 9
Agents / 智能体: 5
```

Finding:

- Model shorthand categories such as `Indie Game` and `AI Engineering` were normalized to configured bilingual labels.

### Zhihu

Result:

```text
0 new items
```

Reason:

```text
command not found: opencli
```

Current state:

- Collector implementation exists.
- Config has Chinese indie-game and AI keywords.
- Runtime requires `opencli` installation and any required platform login/session setup.

## Web UI Evaluation

HTTP checks:

```text
GET / -> 200
GET /api/collectors -> includes linuxdo, reddit, twitter, zhihu
GET /api/collectors -> includes latest_run status, counts, elapsed, and errors
GET /api/items?limit=5 -> returns items/facets shape
GET /api/stats -> includes registry-driven source list
POST /api/run/collect -> runs selected collectors and returns refreshed collector metadata
POST /api/run/analyze -> runs pending-item AI analysis
POST /api/run/report -> validates date and generates a report
```

Current running URL:

```text
http://127.0.0.1:3456
```

Browser screenshot verification was completed with temporary Python Playwright:

```text
desktop 1440x900: no horizontal overflow, action buttons visible, source run states visible
mobile 390x844: no horizontal overflow, action buttons visible, source run states visible
latest screenshot state: 176 items, reddit +150, linux.do +26, X / Twitter err, Zhihu err
screenshots: logs/ui-desktop.png, logs/ui-mobile.png
```

## Plugin Architecture Evaluation

Implemented:

- Built-in collector registry.
- Persisted collector run history in `collector_runs`.
- Web collector metadata includes latest run status, counts, elapsed time, and errors.
- Web UI has local action buttons for `Collect`, `Analyze`, and `Report`.
- Config-declared plugin collectors using:

```yaml
collectors:
  my_source:
    enabled: true
    module: "my_package.my_collector"
    class: "MyCollector"
    display_name: "My Source"
```

Tested:

- A temporary external collector module was loaded from config and executed through `run_collector()`.
- `main.py` and Web API now use registry metadata instead of local hard-coded source lists.
- X / Twitter, Reddit, linux.do, and Zhihu expose runtime errors through `last_errors`, which registry persists.

## Next Work

- Install and configure `opencli`, then rerun X / Twitter and Zhihu collectors.
- Consider authenticated/API collection for Reddit and linux.do only if RSS coverage is not enough.
- Add browser-level UI verification once Playwright or Chrome is available.
