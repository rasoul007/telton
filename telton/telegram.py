"""B-roll from public Telegram channel previews (t.me/s/<channel>) — e.g. @varzesh3.

Two jobs:
  * `fetch_posts()`  — read the public web preview of a channel (no API key needed)
  * `auto_broll()`    — match each story to the most relevant clip, download it into
                        broll/ and write the filename into stories.json

Rights note: these clips are third-party highlights. Only use what you are allowed to
use, always credit the source on screen and in `publish-kit/sources.md`.
"""

from __future__ import annotations

import html
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .config import Project, REPO_ROOT
from .models import Story
from .rundown import load_stories, save_stories

UA = "Mozilla/5.0 (compatible; TeltonBot/0.1)"
VIDEO_RE = re.compile(r"https://[^\"'\s]+\.mp4[^\"'\s]*")
TEXT_RE = re.compile(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
POST_ID_RE = re.compile(r'data-post="([^/"]+)/(\d+)"')
STOPWORDS = {
    "این", "آن", "برای", "است", "شد", "کرد", "با", "از", "که", "را", "در", "به", "و",
    "یک", "دو", "سه", "ها", "های", "بعد", "قبل", "اما", "هم", "تا", "بر", "می", "نیز",
    "the", "and", "for", "with", "from", "are", "was", "his",
}
# words that show up in almost every sports post and would create false matches
GENERIC = {
    "ایران", "تیم", "بازی", "خبر", "ورزش", "لیگ", "دنیا", "جهان", "امروز", "ملی",
    "مهم", "جدید", "برد", "باخت", "گل", "بازیکن", "سرمربی", "دقیقه", "نیمه", "فصل",
    "برتر", "جدول", "هفته", "برنامه", "دور", "جام", "مسابقات", "قهرمانی", "صدر",
    "امتیاز", "شکست", "پیروزی", "مسابقه", "ورزشی", "ایرانی", "خبری", "بازیها",
}
# a tag only counts as an "entity" (team/athlete/competition) if it is not generic
GENERIC_TAGS = GENERIC | {"لیگ برتر", "جدول", "برنامه", "توپ طلا", "قهرمانی"}


@dataclass
class TgPost:
    channel: str
    id: str
    text: str = ""
    videos: list[str] = field(default_factory=list)
    photos: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://t.me/{self.channel}/{self.id}"

    @property
    def clean_text(self) -> str:
        return re.sub(r"\s+", " ", self.text).strip()


def fetch_html(channel: str, before: str | None = None, timeout: float = 15.0) -> str:
    url = f"https://t.me/s/{channel.lstrip('@')}"
    if before:
        url += f"?before={before}"
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def parse_posts(markup: str, channel: str) -> list[TgPost]:
    """Split the channel preview into messages (keeps only those with media)."""
    posts: list[TgPost] = []
    chunks = re.split(r'(?=data-post=")', markup)
    for chunk in chunks:
        match = POST_ID_RE.search(chunk)
        if not match:
            continue
        post = TgPost(channel=match.group(1), id=match.group(2))
        text_match = TEXT_RE.search(chunk)
        if text_match:
            post.text = html.unescape(re.sub(r"<[^>]+>", " ", text_match.group(1))).strip()
        post.videos = [u.replace("&amp;", "&") for u in dict.fromkeys(VIDEO_RE.findall(chunk))]
        photos = re.findall(r"background-image:url\('([^']+)'\)", chunk)
        post.photos = [u.replace("&amp;", "&") for u in dict.fromkeys(photos)]
        if post.videos or post.photos:
            posts.append(post)
    return posts


def fetch_posts(channel: str, limit: int = 20, timeout: float = 15.0, max_pages: int = 8) -> list[TgPost]:
    """Read the public preview, walking backwards with ?before= until `limit` posts."""
    posts: list[TgPost] = []
    before: str | None = None
    for _ in range(max_pages):
        try:
            markup = fetch_html(channel, before=before, timeout=timeout)
        except Exception:
            break
        batch = parse_posts(markup, channel.lstrip("@"))
        if not batch:
            break
        posts = batch + posts            # pages come oldest→newest, prepend older pages
        before = batch[0].id
        if len(posts) >= limit:
            break
    return posts[-limit:][::-1] if posts else []


def download(url: str, dest: Path, timeout: float = 60.0) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    dest.write_bytes(data)
    return len(data)


def keywords(*texts: Iterable[str]) -> set[str]:
    words: set[str] = set()
    for text in texts:
        for word in re.split(r"[^\w\u0600-\u06FF]+", str(text)):
            word = word.strip()
            if len(word) >= 3 and word.lower() not in STOPWORDS and word.lower() not in GENERIC:
                words.add(word.lower())
    return words


def link_hits(story: Story, post: TgPost) -> dict:
    """Which specific entities (teams/athletes) of the story appear in the post?"""
    haystack = post.clean_text.lower()
    entities = [t for t in story.tags if t.lower() not in GENERIC_TAGS and len(t) >= 3]
    head = keywords(story.headline) - set(entities)
    return {
        "entities": [t for t in entities if t.lower() in haystack],
        "entity": entities,
        "headline": [w for w in head if w in haystack],
    }


def match_score(story: Story, post: TgPost) -> int:
    """Score a post for a story.

    A post only counts when it mentions a *specific* entity of the story (a team,
    player or competition tag). Two headline words are an acceptable fallback.
    Generic words like «ایران» or «لیگ» never create a match on their own.
    """
    hits = link_hits(story, post)
    if not hits["entity"]:
        return 0            # story has no specific tag -> leave it to a human
    entity_hits = len(hits["entities"])
    head_hits = len(hits["headline"])
    if entity_hits == 0 and head_hits < 2:
        return 0
    return 4 * entity_hits + head_hits


def auto_broll(
    project: Project,
    channel: str = "varzesh3",
    limit: int = 20,
    min_score: int = 3,
    dry_run: bool = False,
    max_clips: int = 8,
) -> list[dict]:
    """Match stories to channel clips, download, and record them in stories.json."""
    posts = fetch_posts(channel, limit=limit)
    stories = load_stories(project)
    broll_dir = REPO_ROOT / "broll"
    used: set[str] = set()
    report: list[dict] = []
    downloaded = 0

    for story in stories:
        if story.broll or downloaded >= max_clips:
            continue
        ranked = sorted(
            ((match_score(story, post), post) for post in posts if post.id not in used),
            key=lambda pair: pair[0],
            reverse=True,
        )
        if not ranked or ranked[0][0] < min_score:
            report.append({"story": story.id, "status": "no-match"})
            continue
        score, post = ranked[0]
        if not post.videos and not post.photos:
            report.append({"story": story.id, "status": "no-media", "post": post.url})
            continue
        used.add(post.id)
        if post.videos:
            name = f"tg-{channel}-{post.id}.mp4"
            source_url = post.videos[0]
            kind = "video"
        else:
            name = f"tg-{channel}-{post.id}.jpg"
            source_url = post.photos[0]
            kind = "photo"
        target = broll_dir / name
        entry = {
            "story": story.id,
            "post": post.url,
            "caption": post.clean_text[:80],
            "score": score,
            "file": name,
            "kind": kind,
        }
        if dry_run:
            entry["status"] = f"would-download-{kind}"
        else:
            try:
                entry["bytes"] = download(source_url, target)
            except Exception as exc:  # expired token / rate limit — keep going
                entry["status"] = "download-failed"
                entry["error"] = f"{type(exc).__name__}: {exc}"[:120]
                report.append(entry)
                continue
            story.broll = name
            downloaded += 1
            entry["status"] = f"downloaded-{kind}"
        report.append(entry)

    if not dry_run:
        save_stories(project, stories)
    return report
