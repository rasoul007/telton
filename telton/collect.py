"""Stage 1 — collect raw headlines from RSS into build/candidates.json.

The agent never invents facts: this stage only gathers *pointers*.  A human
(or an LLM writing stage) turns the good ones into `stories.json` in Persian,
which is the file the rest of the pipeline trusts.
"""

from __future__ import annotations

import re
import urllib.request
from datetime import datetime, timezone
from typing import Any

import feedparser

from .config import Project, load_sources
from .util import normalize_title, write_json

USER_AGENT = "Mozilla/5.0 (compatible; TeltonBot/0.1; +https://github.com/rasoul007/telton)"


def fetch(url: str, timeout: float = 8.0) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception:
        return None


def classify(title: str, buckets: dict[str, dict[str, Any]], default: str) -> tuple[str, int]:
    """Return (bucket, keyword hits) for a headline."""
    lowered = title.lower()
    best, hits_best = default, 0
    for name, spec in buckets.items():
        hits = 0
        for keyword in spec.get("keywords", []):
            if keyword.lower() in lowered:
                hits += 1
        if hits > hits_best:
            best, hits_best = name, hits
    return best, hits_best


def collect(project: Project, limit_per_feed: int = 25) -> dict[str, Any]:
    sources = load_sources()
    buckets = sources.get("buckets", {})
    default_bucket = sources.get("default_bucket", "world")
    seen: dict[str, dict[str, Any]] = {}
    report: list[dict[str, Any]] = []

    for feed in sources.get("rss", []):
        if not feed.get("enabled", True):
            report.append({"id": feed["id"], "status": "disabled"})
            continue
        payload = fetch(feed["url"])
        if payload is None:
            report.append({"id": feed["id"], "status": "unreachable"})
            continue
        parsed = feedparser.parse(payload)
        count = 0
        for entry in parsed.entries[:limit_per_feed]:
            title = getattr(entry, "title", "").strip()
            if not title:
                continue
            key = normalize_title(title)
            bucket, hits = classify(title, buckets, default_bucket)
            candidate = {
                "title": title,
                "url": getattr(entry, "link", ""),
                "source": feed.get("name", feed["id"]),
                "source_id": feed["id"],
                "published": getattr(entry, "published", ""),
                "bucket": bucket,
                "keyword_hits": hits,
                "score": int(feed.get("weight", 1)) * 10 + hits * 3,
            }
            existing = seen.get(key)
            if existing is None or candidate["score"] > existing["score"]:
                seen[key] = candidate
            count += 1
        report.append({"id": feed["id"], "status": "ok", "entries": count})

    items = sorted(seen.values(), key=lambda c: (-c["score"], c["title"]))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "feeds": report,
        "count": len(items),
        "candidates": items,
    }
    write_json(project.candidates_path, payload)
    write_digest(project, payload)
    return payload


def write_digest(project: Project, payload: dict) -> Path:
    """Human-friendly checklist of today's candidates, ready to be turned into stories.json."""
    lines = [
        f"# تیترهای خام — {payload['generated_at']}",
        "",
        "هر مورد را که خواستی بردار، به فارسی بازنویسی کن و در `stories.json` بگذار:",
        "",
        "```json",
        '{ "id": "unique-slug", "bucket": "iran_football", "priority": 1,',
        '  "headline": "تیتر کوتاه", "summary": "دو جمله‌ی نریشن.",',
        '  "facts": ["کارت ۱", "کارت ۲"],',
        '  "sources": [{"name": "BBC Sport", "url": "https://…"}],',
        '  "broll": null, "verified": true }',
        "```",
        "",
        "## فیدها",
        "",
    ]
    for feed in payload["feeds"]:
        lines.append(f"- `{feed['id']}` → {feed['status']}" + (f" ({feed['entries']} مورد)" if feed.get("entries") else ""))
    lines += ["", "## تیترها به‌ترتیب امتیاز", ""]
    for candidate in payload["candidates"]:
        lines.append(
            f"- [ ] **{candidate['bucket']}** · {candidate['title']}  \n"
            f"      {candidate['source']} — {candidate['url']}"
        )
    path = project.build / "candidates.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\u0600-\u06FF]+", "-", text.strip().lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:60] or "story"
