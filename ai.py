"""Optional OpenAI-compatible AI search integration.

Uses only the Python standard library so it can run inside Binary Ninja's embedded
interpreter. The provider must implement POST /chat/completions.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .search import categories_for_prompt, compact_view_summary


def _setting(settings: Any, key: str, default: Any) -> Any:
    try:
        value = settings.get(key)
        return default if value in (None, "") else value
    except Exception:
        return default


def ai_search(bv: Any, query: str, settings: Any) -> list[dict[str, Any]]:
    base_url = str(_setting(settings, "AdvancedSearch.ai.base_url", "https://api.openai.com/v1")).rstrip("/")
    api_key = str(_setting(settings, "AdvancedSearch.ai.api_key", ""))
    model = str(_setting(settings, "AdvancedSearch.ai.model", "gpt-4o-mini"))
    timeout = int(_setting(settings, "AdvancedSearch.ai.timeout_seconds", 30))
    if not api_key:
        raise RuntimeError("AI search is enabled but no API key is configured")
    summary = compact_view_summary(bv, int(_setting(settings, "AdvancedSearch.ai.max_functions", 250)))
    system = ("You are a reverse-engineering assistant. Given a user behavior query and a list of Binary Ninja functions, "
              "return JSON only with an object containing a 'matches' array. Each match must contain name, address, "
              "category, confidence (0-1), and rationale. Do not invent functions or addresses.\n\nKnown categories:\n" + categories_for_prompt())
    payload = {"model": model, "temperature": 0, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps({"query": query, "functions": summary}, ensure_ascii=False)},
    ]}
    request = urllib.request.Request(base_url + "/chat/completions", data=json.dumps(payload).encode(), headers={
        "Authorization": "Bearer " + api_key, "Content-Type": "application/json", "User-Agent": "AdvancedSearch/1.0"
    }, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=max(5, min(timeout, 120))) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Provider returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Provider connection failed: {exc.reason}") from exc
    content = data["choices"][0]["message"]["content"]
    if isinstance(content, str):
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = json.loads(cleaned.strip())
    else:
        parsed = content
    matches = parsed.get("matches", []) if isinstance(parsed, dict) else []
    allowed = {(row["name"], row["address"]) for row in summary}
    output = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        key = (str(match.get("name", "")), int(match.get("address", -1)))
        if key in allowed:
            output.append(match)
    return output
