"""Stage 6 — the publish kit. Gated: nothing leaves without an approval record."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import Project
from .models import Rundown
from .review import CHECKLIST, approval_status
from .rundown import SECTION_LABELS
from .util import ensure_dir, read_json, seconds_to_clock, sha256_file, write_json

PLATFORMS = {
    "youtube": {"aspect": "9:16", "max_seconds": 60, "note": "Shorts؛ یا همین فایل را به‌عنوان ویدیوی بلند آپلود کن"},
    "instagram": {"aspect": "9:16", "max_seconds": 90, "note": "Reels؛ کاور ۱۰۸۰×۱۹۲۰"},
    "telegram": {"aspect": "9:16", "max_seconds": 600, "note": "فایل کامل بدون محدودیت شدید"},
    "tiktok": {"aspect": "9:16", "max_seconds": 600, "note": "زیرنویس چسبیده لازم است"},
    "x": {"aspect": "9:16", "max_seconds": 140, "note": "برای نسخه‌ی خبری سریع"},
}


class NotApproved(PermissionError):
    pass


def verify(project: Project) -> dict:
    """Raise NotApproved unless the current MP4 is approved and unchanged."""
    status = approval_status(project)
    if not status["approved"]:
        raise NotApproved(
            "انتشار متوقف شد: " + "؛ ".join(status["reasons"])
            + " → اول `telton review` را ببین و با `telton approve --by \"نام\"` تأیید کن."
        )
    return status


def make_kit(project: Project, rundown: Rundown, video: Path | None = None) -> Path:
    """Bundle everything a scheduler/phone needs to post the video."""
    status = verify(project)
    video = video or project.video_path
    kit = ensure_dir(project.out / "publish-kit")

    shutil.copy2(video, kit / "video-9x16.mp4")
    for name in ("subtitles.srt", "caption.txt"):
        source = project.build / name
        if source.exists():
            shutil.copy2(source, kit / name)
    thumb = project.out / "thumbnail.jpg"
    if thumb.exists():
        shutil.copy2(thumb, kit / "thumbnail.jpg")

    stories = [s.story for s in rundown.segments if s.story]
    sources = ["# منابع", ""]
    for story in stories:
        sources.append(f"## {story.headline}")
        sources.append(f"- بخش: {SECTION_LABELS.get(story.bucket, story.bucket)}")
        for source in story.sources:
            sources.append(f"- {source.name} — {source.url}" if source.url else f"- {source.name}")
        sources.append("")
    (kit / "sources.md").write_text("\n".join(sources), encoding="utf-8")

    checklist = ["# چک‌لیست انتشار", ""]
    checklist += [f"- [ ] {item}" for item in CHECKLIST]
    checklist += ["", "## مشخصات پلتفرم‌ها", ""]
    for name, spec in PLATFORMS.items():
        checklist.append(f"- **{name}**: {spec['aspect']} · حداکثر {spec['max_seconds']}s — {spec['note']}")
    (kit / "checklist.md").write_text("\n".join(checklist), encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": project.slug,
        "title": rundown.title,
        "duration": round(rundown.end, 3),
        "duration_human": seconds_to_clock(rundown.end),
        "files": {
            "video": "video-9x16.mp4",
            "subtitles": "subtitles.srt",
            "caption": "caption.txt",
            "thumbnail": "thumbnail.jpg",
            "sources": "sources.md",
            "checklist": "checklist.md",
        },
        "sha256": sha256_file(kit / "video-9x16.mp4"),
        "approval": status["record"],
        "platforms": PLATFORMS,
        "stories": [
            {"id": s.id, "headline": s.headline, "bucket": s.bucket, "verified": s.verified}
            for s in stories
        ],
    }
    write_json(kit / "manifest.json", manifest)
    return kit


def upload(project: Project, platform: str, dry_run: bool = True) -> dict:
    """Direct API upload is intentionally a stub: it needs *your* credentials."""
    verify(project)
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform {platform!r}; use one of {sorted(PLATFORMS)}")
    kit = project.out / "publish-kit"
    if not (kit / "video-9x16.mp4").exists():
        raise FileNotFoundError("run `telton publish` first to build the kit")
    return {
        "platform": platform,
        "dry_run": dry_run,
        "status": "ready-to-upload",
        "video": str(kit / "video-9x16.mp4"),
        "caption": str(kit / "caption.txt"),
        "note": (
            "آپلود خودکار نیاز به اعتبارنامه‌ی خودت دارد: برای یوتیوب "
            "YouTube Data API v3 + OAuth (video.insert)، برای اینستاگرام Graph API "
            "(media + media_publish). فایل‌ها آماده‌اند؛ می‌توانی همین پوشه را به "
            "زمان‌بند (cron/n8n) وصل کنی."
        ),
    }
