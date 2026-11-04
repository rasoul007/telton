"""Copyright-safe visuals from free sources.

Wikimedia Commons needs no API key and shows the license of every file, so it is the
default provider. Pexels/Pixabay are supported when you add a free API key.

Usage:
    telton stock -p <slug> --query "football stadium" --kind video
    telton stock -p <slug> --auto            # match missing stories automatically
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .config import REPO_ROOT, Project
from .models import Story
from .rundown import load_stories, save_stories

UA = "Mozilla/5.0 (compatible; TeltonBot/0.1)"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
FREE_LICENSES = ("cc0", "cc by", "cc-by", "public domain", "pd", "cc by-sa", "cc-by-sa")

# Persian tags/keywords -> English query used by the stock providers
TERMS = {
    "آرسنال": "Arsenal FC",
    "لیورپول": "Liverpool FC",
    "آنفیلد": "Anfield stadium",
    "پرسپولیس": "Persepolis FC",
    "استقلال": "Esteghlal FC",
    "سپاهان": "Sepahan FC",
    "تراکتور": "Tractor SC",
    "کشتی": "wrestling",
    "کشتی فرنگی": "Greco-Roman wrestling",
    "فرنگی": "wrestling",
    "فرمول یک": "Formula One",
    "آنتونلی": "Andrea Kimi Antonelli",
    "فرشتپن": "Max Verstappen",
    "رئال مادرید": "Real Madrid",
    "بارسلونا": "FC Barcelona",
    "بایرن": "Bayern Munich",
    "لاجیو": "SS Lazio",
    "یوونتوس": "Juventus",
    "توپ طلا": "Ballon d'Or",
    "کین": "Harry Kane",
    "امباپه": "Kylian Mbappe",
    "لیگ قهرمانان": "UEFA Champions League",
    "ورزشگاه": "stadium crowd",
    "هوادار": "football fans",
}


@dataclass
class StockItem:
    title: str
    url: str
    page: str
    license: str

    @property
    def free(self) -> bool:
        text = self.license.lower()
        return any(token in text for token in FREE_LICENSES)


def english_query(story: Story) -> str:
    for tag in story.tags:
        if tag in TERMS:
            return TERMS[tag]
    for key, value in TERMS.items():
        if key in story.headline or key in story.summary:
            return value
    return "sport"


def search_commons(query: str, kind: str = "video", limit: int = 6, timeout: float = 20.0) -> list[StockItem]:
    """Search Wikimedia Commons (video: webm/ogv, image: bitmap). No API key needed."""
    filetype = "video" if kind == "video" else "bitmap"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"{query} filetype:{filetype}",
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
    }
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except Exception:
        return []

    items: list[StockItem] = []
    for page in (payload.get("query", {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        link = info.get("url")
        if not link:
            continue
        meta = info.get("extmetadata") or {}
        license_name = str((meta.get("LicenseShortName") or {}).get("value", "unknown"))
        items.append(
            StockItem(
                title=str(page.get("title", "")).replace("File:", ""),
                url=link,
                page=str(info.get("descriptionurl", "")),
                license=license_name,
            )
        )
    return items


def download(url: str, dest: Path, timeout: float = 90.0) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    dest.write_bytes(data)
    return len(data)


def _safe_name(text: str, limit: int = 40) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return slug[:limit] or "clip"


def fetch_for_story(story: Story, kind: str = "video", dry_run: bool = False) -> dict:
    query = english_query(story)
    items = [item for item in search_commons(query, kind=kind) if item.free]
    if not items:
        return {"story": story.id, "status": "no-free-result", "query": query}
    item = items[0]
    suffix = Path(urllib.parse.urlparse(item.url).path).suffix or (".webm" if kind == "video" else ".jpg")
    name = f"stock-{_safe_name(query)}{suffix}"
    target = REPO_ROOT / "broll" / name
    if dry_run:
        return {"story": story.id, "status": "would-download", "query": query,
                "file": name, "license": item.license, "page": item.page}
    try:
        size = download(item.url, target)
    except Exception as exc:
        return {"story": story.id, "status": "download-failed", "error": str(exc)[:100]}
    story.broll = name
    return {"story": story.id, "status": "downloaded", "query": query, "file": name,
            "bytes": size, "license": item.license, "page": item.page}


def fill_missing(project: Project, kind: str = "video", limit: int = 4, dry_run: bool = False) -> list[dict]:
    """Give every story without footage a copyright-safe clip."""
    stories = load_stories(project)
    report: list[dict] = []
    filled = 0
    for story in stories:
        if story.broll or filled >= limit:
            continue
        entry = fetch_for_story(story, kind=kind, dry_run=dry_run)
        report.append(entry)
        if entry["status"] == "downloaded":
            filled += 1
    if filled and not dry_run:
        save_stories(project, stories)
    return report
