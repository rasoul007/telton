"""Stage 5 — human review page + the approval gate that guards publishing."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from .config import Project
from .models import Rundown
from .rundown import SECTION_LABELS
from .util import read_json, seconds_to_clock, sha256_file, write_json

CHECKLIST = [
    "همه‌ی خبرها راستی‌آزمایی و منبع‌دار شده‌اند",
    "نام‌ها، عددها و تاریخ‌ها در نریشن و روی کارت‌ها یکی است",
    "زیرنویس‌ها با صدا هم‌تراز است (±۰.۲ ثانیه)",
    "تست تماشای بدون صدا انجام شد (همه چیز خواناست)",
    "فوتیج‌ها دارای مجوز/کردیت هستند و لوگوی منبع روی تصویر است",
    "موسیقی و افکت‌ها بدون کپی‌رایت‌اند",
    "کپشن، هشتگ و تامبنیل آماده است",
    "لحن خبرها بی‌طرف و بدون توهین است",
]


def approval_status(project: Project) -> dict:
    """Is the current video file approved (and not stale)?"""
    if not project.video_path.exists():
        return {"approved": False, "stale": False, "reasons": ["ویدیو ساخته نشده است"], "record": None}
    digest = sha256_file(project.video_path)
    record = read_json(project.approval_path, default=None)
    if not record:
        return {"approved": False, "stale": False, "reasons": ["تأیید ثبت نشده است"], "record": None}
    reasons: list[str] = []
    if record.get("sha256") != digest:
        reasons.append("ویدیو بعد از تأیید تغییر کرده است (هش متفاوت)")
    if not record.get("by"):
        reasons.append("نام تأییدکننده ثبت نشده است")
    return {
        "approved": not reasons,
        "stale": bool(reasons),
        "reasons": reasons,
        "record": record,
        "sha256": digest,
    }


def unverified_stories(rundown: Rundown) -> list[str]:
    return [s.story.id for s in rundown.segments if s.story and not s.story.verified]


def build_review(project: Project, rundown: Rundown) -> Path:
    """A single self-contained HTML page: watch, check facts, then approve."""
    project.ensure()
    status = approval_status(project)
    rows: list[str] = []
    for segment in rundown.segments:
        if not segment.story:
            continue
        story = segment.story
        sources = " ".join(
            f'<a href="{html.escape(s.url)}" target="_blank" rel="noreferrer">{html.escape(s.name)}</a>'
            for s in story.sources
        ) or "—"
        flag = "✅" if story.verified else "⚠️"
        rows.append(
            "<tr>"
            f"<td>{seconds_to_clock(segment.start)}–{seconds_to_clock(segment.end)}</td>"
            f"<td>{html.escape(SECTION_LABELS.get(story.bucket, story.bucket))}</td>"
            f"<td><b>{html.escape(story.headline)}</b><br><small>{html.escape(story.summary)}</small></td>"
            f"<td>{html.escape(' · '.join(story.facts))}</td>"
            f"<td>{sources}</td>"
            f"<td>{flag}</td>"
            "</tr>"
        )

    checklist = "".join(
        f"<li><label><input type=checkbox> {html.escape(item)}</label></li>" for item in CHECKLIST
    )
    badge = (
        '<span class="ok">تأیید شده</span>'
        if status["approved"]
        else '<span class="bad">منتشر نمی‌شود تا تأیید کنی</span>'
    )
    unverified = unverified_stories(rundown)
    warning = (
        f'<p class="bad">این خبرها هنوز verified نشده‌اند: {html.escape(", ".join(unverified))}</p>'
        if unverified
        else ""
    )
    video = (
        f'<video src="{project.video_path.name}" controls width="360"></video>'
        if project.video_path.exists()
        else "<p>ویدیو هنوز ساخته نشده است.</p>"
    )
    page = f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>بازبینی — {html.escape(rundown.title)}</title>
<style>
 body{{background:#0b0e13;color:#e7ecf3;font:16px/1.7 Vazirmatn,system-ui,sans-serif;margin:0;padding:32px}}
 h1{{font-size:26px;margin:0 0 8px}} h2{{font-size:19px;margin-top:32px;color:#ffd400}}
 table{{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px}}
 td,th{{border-bottom:1px solid #22303f;padding:10px;vertical-align:top;text-align:right}}
 th{{color:#9aa4b2;font-weight:600}} a{{color:#7cc4ff}}
 .ok{{background:#12351f;color:#4ade80;padding:4px 12px;border-radius:99px}}
 .bad{{background:#3a1113;color:#ff8b8b;padding:4px 12px;border-radius:99px}}
 ul{{line-height:2;list-style:none;padding:0}} code{{background:#161e2b;padding:2px 6px;border-radius:6px}}
 .grid{{display:flex;gap:32px;flex-wrap:wrap}}
</style></head>
<body>
<h1>بازبینی و تأیید انتشار</h1>
<p>{badge} · مدت: {seconds_to_clock(rundown.end)} · سگمنت: {len(rundown.segments)} · فایل: <code>{html.escape(project.video_path.name)}</code></p>
{warning}
<div class="grid">
  <div>{video}</div>
  <div><h2>چک‌لیست انتشار</h2><ul>{checklist}</ul></div>
</div>
<h2>خبر‌ها و منابع</h2>
<table><tr><th>زمان</th><th>بخش</th><th>خبر</th><th>کارت‌ها</th><th>منبع</th><th>وضعیت</th></tr>
{''.join(rows)}
</table>
<h2>تأیید</h2>
<p>اگر همه چیز درست است اجرا کن:</p>
<pre><code>telton approve --project {html.escape(project.slug)} --by "نام تو"</code></pre>
<p>بعد از تأیید: <code>telton publish --project {html.escape(project.slug)}</code></p>
</body></html>"""
    path = project.out / "review.html"
    path.write_text(page, encoding="utf-8")
    return path


def approve(
    project: Project,
    by: str,
    platforms: list[str] | None = None,
    force: bool = False,
) -> dict:
    """Record a signed-off approval for the *exact* current video file."""
    if not project.video_path.exists():
        raise FileNotFoundError("ویدیو ساخته نشده است؛ اول `telton render`")
    rundown = read_json(project.build / "rundown.json")
    if not rundown:
        raise FileNotFoundError("rundown.json missing; run `telton build`")
    unverified = [
        seg["story"]["id"]
        for seg in rundown["segments"]
        if seg.get("story") and not seg["story"].get("verified")
    ]
    if unverified and not force:
        raise PermissionError(
            "این خبرها verified نیستند: " + ", ".join(unverified)
            + " — بعد از راستی‌آزمایی verified=true بگذار، یا با --force تأیید کن."
        )
    record = {
        "by": by,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha256_file(project.video_path),
        "duration": rundown.get("duration"),
        "platforms": platforms or ["youtube", "instagram", "telegram"],
        "forced": bool(unverified and force),
        "stories": [
            {
                "id": seg["story"]["id"],
                "headline": seg["story"]["headline"],
                "sources": seg["story"]["sources"],
            }
            for seg in rundown["segments"]
            if seg.get("story")
        ],
    }
    write_json(project.approval_path, record)
    return record
