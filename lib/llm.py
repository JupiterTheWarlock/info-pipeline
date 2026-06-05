"""LLM client for analysis and summarization."""

import json
from typing import Any

import httpx

from .config import get


def call_llm(
    prompt: str,
    system: str = "",
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.3,
) -> str:
    """Call the LLM API (OpenAI-compatible). Returns the assistant message content."""
    cfg = get("llm")
    base_url = cfg["base_url"]
    api_key = cfg["api_key"]
    model = model or cfg.get("model", "gpt-4o-mini")
    max_tokens = max_tokens or cfg.get("max_tokens", 4096)
    timeout = cfg.get("timeout_seconds", 60)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def analyze_items(items: list[dict]) -> list[dict[str, Any]]:
    """Analyze a batch of items with LLM. Returns list with category, score, summary."""
    categories = get("processor.categories")
    preferences = get("processor.preferences", ["独立游戏", "AI"])
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += f"\n--- [{i}] ---\n"
        items_text += f"标题: {item.get('title', 'N/A')}\n"
        items_text += f"来源: {item.get('source', 'N/A')}"
        if item.get("source_detail"):
            items_text += f" ({item.get('source_detail')})"
        items_text += f"\nURL: {item.get('url', 'N/A')}\n"
        content = item.get("content", "") or ""
        if len(content) > 500:
            content = content[:500] + "..."
        items_text += f"内容摘要: {content}\n"

    prompt = f"""请分析以下 {len(items)} 条信息，为每条进行分类、打分和摘要。

可选分类: {', '.join(categories)}
用户重点偏好: {', '.join(preferences)}
评分标准 (1-10): 
- 9-10: 重大突破、行业变革、高度相关
- 7-8: 重要新闻、有深度、值得关注
- 5-6: 一般信息、有一定参考价值
- 3-4: 可看可不看、信息量一般
- 1-2: 低质量、重复、不相关
偏好匹配分 preference_score (1-10):
- 9-10: 对独立游戏开发、游戏商业化、AI 工具/agent 实践高度相关
- 7-8: 与上述方向明显相关，值得优先阅读
- 5-6: 间接相关或背景信息
- 1-4: 与偏好弱相关或噪音

请严格按以下 JSON 格式返回，不要加任何其他文字：
```json
[
  {{"index": 1, "category": "分类名", "score": 7, "preference_score": 8, "summary": "一句话摘要", "why_relevant": "为什么值得看", "risk": "潜在噪音或风险", "tags": ["标签"]}},
  {{"index": 2, "category": "分类名", "score": 5, "preference_score": 4, "summary": "一句话摘要", "why_relevant": "为什么值得看", "risk": "", "tags": ["标签"]}}
]
```

待分析信息:
{items_text}
"""

    response = call_llm(
        prompt,
        system="你是一个为独立游戏开发者和 AI 工具实践者服务的信息筛选助手，需要判断每条信息是否值得用户花时间阅读。",
    )

    # Parse JSON from response
    try:
        # Extract JSON from markdown code block if present
        json_str = response
        if "```json" in response:
            json_str = response.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in response:
            json_str = response.split("```", 1)[1].split("```", 1)[0]

        results = json.loads(json_str.strip())
        # Build a map by index
        result_map = {r["index"]: r for r in results}

        analyzed = []
        for i, item in enumerate(items, 1):
            r = result_map.get(i, {})
            analyzed.append({
                **item,
                "category": normalize_category(r.get("category", "其他"), categories),
                "score": float(r.get("score", 3)),
                "preference_score": float(r.get("preference_score", r.get("score", 3))),
                "summary": r.get("summary", item.get("title", "")),
                "why_relevant": r.get("why_relevant", ""),
                "risk": r.get("risk", ""),
                "tags": r.get("tags", []),
            })
        return analyzed
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"[WARN] Failed to parse LLM response: {e}")
        # Fallback: return items with defaults
        return [
            {
                **item,
                "category": "其他",
                "score": 3.0,
                "preference_score": 3.0,
                "summary": item.get("title", ""),
                "why_relevant": "",
                "risk": "LLM response parse failed",
                "tags": [],
            }
            for item in items
        ]


def normalize_category(category: str, categories: list[str]) -> str:
    """Map model shorthand category names back to configured category labels."""
    if category in categories:
        return category

    category_norm = str(category).strip().lower()
    for configured in categories:
        configured_norm = configured.lower()
        aliases = {configured_norm}
        if "/" in configured:
            aliases.update(part.strip().lower() for part in configured.split("/"))
        if category_norm in aliases:
            return configured

    english_aliases = {
        "indie game": "Indie Game / 独立游戏",
        "game dev": "Game Dev / 游戏开发",
        "ai product": "AI Product / AI 产品",
        "ai engineering": "AI Engineering / AI 工程",
        "agents": "Agents / 智能体",
        "tools": "Tools / 工具链",
        "business": "Business / 商业化",
        "other": "Other / 其他",
    }
    mapped = english_aliases.get(category_norm)
    if mapped in categories:
        return mapped
    return categories[-1] if categories else "其他"


def generate_report(categories_items: dict[str, list[dict]], date_str: str) -> str:
    """Generate a markdown report from categorized items."""
    lines = [f"# 📡 InfoPipeline 日报 — {date_str}\n"]

    total = sum(len(items) for items in categories_items.values())
    lines.append(f"> 共收集 **{total}** 条有价值信息\n")

    for category, items in categories_items.items():
        if not items:
            continue
        lines.append(f"\n## {category}")
        lines.append("")

        for item in sorted(items, key=lambda x: (x.get("preference_score", 0), x.get("score", 0)), reverse=True):
            score = item.get("score", 0)
            preference_score = item.get("preference_score", 0)
            score_emoji = "⭐" if score >= 8 else "🔹" if score >= 5 else "🔸"
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            summary = item.get("summary", "")
            source = item.get("source", "")
            source_detail = item.get("source_detail", "")

            lines.append(f"- {score_emoji} **[{score}/10 | 偏好 {preference_score}/10]** [{title}]({url})")
            if source_detail:
                lines.append(f"  - 来源: {source} ({source_detail})")
            else:
                lines.append(f"  - 来源: {source}")
            if summary:
                lines.append(f"  - {summary}")
            if item.get("why_relevant"):
                lines.append(f"  - 值得看: {item.get('why_relevant')}")
            if item.get("risk"):
                lines.append(f"  - 风险: {item.get('risk')}")
            lines.append("")

    return "\n".join(lines)
