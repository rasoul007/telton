"""YouTube upload (Data API v3) with *your own* OAuth client.

Nothing here runs without an explicit approval record for the exact MP4 being uploaded
(see `telton.publish.verify`), so re-rendering invalidates a previous upload.

Setup (once):
  1. console.cloud.google.com → new project → enable "YouTube Data API v3"
  2. OAuth consent screen → External → add yourself as a test user
  3. Credentials → Create credentials → OAuth client ID → Desktop app → download JSON
  4. save it as .secrets/client_secret.json   (git-ignored)
  5. python -m telton youtube auth
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import REPO_ROOT, Project
from .models import Rundown
from .publish import PLATFORMS, verify
from .util import ensure_dir, seconds_to_clock, write_json

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
SECRETS_DIR = REPO_ROOT / ".secrets"
DEFAULT_CLIENT_SECRET = SECRETS_DIR / "client_secret.json"
DEFAULT_TOKEN = SECRETS_DIR / "youtube-token.json"
API_SERVICE = "youtube"
API_VERSION = "v3"
MAX_TITLE = 100
MAX_DESCRIPTION = 5000
MAX_TAGS_CHARS = 500


class YouTubeNotConfigured(RuntimeError):
    """Missing/expired credentials — the message explains the fix."""


def client_secret_path(path: str | Path | None = None) -> Path:
    return Path(path) if path else DEFAULT_CLIENT_SECRET


def token_path(path: str | Path | None = None) -> Path:
    return Path(path) if path else DEFAULT_TOKEN


# --------------------------------------------------------------------- auth
def load_credentials(
    client_secret: str | Path | None = None,
    token: str | Path | None = None,
    interactive: bool = False,
    port: int = 0,
    echo: Callable[[str], None] = print,
):
    """Return valid Google credentials, refreshing the saved token when possible."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    secret = client_secret_path(client_secret)
    token_file = token_path(token)
    creds = None
    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        except Exception:
            creds = None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            write_json(token_file, json.loads(creds.to_json()))
            return creds
        except Exception:
            creds = None
    if not interactive:
        raise YouTubeNotConfigured(
            "اعتبارنامه‌ی یوتیوب آماده نیست — یک‌بار `python -m telton youtube auth` را بزن "
            "(client_secret.json را از Google Cloud بساز و در .secrets/ بگذار)."
        )
    if not secret.exists():
        raise YouTubeNotConfigured(
            f"فایل {secret} پیدا نشد. از Google Cloud Console → Credentials → "
            "OAuth client ID (Desktop app) بساز و JSON را همان‌جا ذخیره کن."
        )
    echo("مرورگر باز می‌شود؛ با اکانت کانال tooop news وارد شو و دسترسی آپلود را تأیید کن.")
    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    creds = flow.run_local_server(port=port, prompt="consent", open_browser=True)
    ensure_dir(token_file.parent)
    write_json(token_file, json.loads(creds.to_json()))
    echo(f"توکن ذخیره شد: {token_file}")
    return creds


def service(client_secret=None, token=None, interactive: bool = False, port: int = 0, echo=print):
    from googleapiclient.discovery import build

    creds = load_credentials(client_secret, token, interactive=interactive, port=port, echo=echo)
    return build(API_SERVICE, API_VERSION, credentials=creds, cache_discovery=False)


# ------------------------------------------------------------------ payload
def _assemble_description(caption: str, source_lines: list[str], tail: str) -> str:
    """Keep the description under the API limit without ever cutting a link in half."""
    if not source_lines:
        return (caption + tail)[:MAX_DESCRIPTION]
    for count in range(len(source_lines), 0, -1):
        block = caption + "\n\nمنابع:\n" + "\n".join(source_lines[:count])
        remaining = len(source_lines) - count
        if remaining:
            block += f"\n(و {remaining} منبع دیگر)"
        block += tail
        if len(block) <= MAX_DESCRIPTION:
            return block
    return (caption + tail)[:MAX_DESCRIPTION]


def build_payload(
    project: Project,
    rundown: Rundown,
    privacy: str = "unlisted",
    publish_at: str | None = None,
) -> dict:
    """The exact `videos.insert` body; also what `--dry-run` prints."""
    meta = project.meta
    title = str(meta.get("youtube_title") or rundown.title)[:MAX_TITLE]

    caption_file = project.build / "caption.txt"
    caption = caption_file.read_text(encoding="utf-8") if caption_file.exists() else ""
    # the caption already carries a short source line; we rebuild a fuller one below
    description = "\n".join(
        line for line in caption.splitlines() if not line.strip().startswith("📌 منابع")
    ).strip()

    seen: set[str] = set()
    source_lines: list[str] = []
    for segment in rundown.segments:
        if not segment.story:
            continue
        for source in segment.story.sources:
            key = f"{source.name}|{source.url}"
            if key in seen:
                continue
            seen.add(key)
            source_lines.append(f"- {source.name}" + (f": {source.url}" if source.url else ""))

    tail = f"\n\n⏱ {seconds_to_clock(rundown.end)} · tooop news"
    description = _assemble_description(description, source_lines, tail)

    tags: list[str] = []
    for item in str(meta.get("hashtags") or "").split():
        tag = item.lstrip("#").strip()
        if tag and tag not in tags:
            tags.append(tag)
    while tags and sum(len(t) + 1 for t in tags) > MAX_TAGS_CHARS:
        tags.pop()

    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": bool(meta.get("made_for_kids", False)),
        "license": "youtube",
        "embeddable": True,
    }
    if publish_at:
        status["privacyStatus"] = "private"   # YouTube requires private + publishAt
        status["publishAt"] = publish_at

    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": str(meta.get("youtube_category", "17")),  # 17 = Sports
            "defaultLanguage": "fa",
            "defaultAudioLanguage": "fa",
        },
        "status": status,
    }


def validate_payload(payload: dict) -> list[str]:
    """Cheap pre-flight checks so the API doesn't reject us mid-upload."""
    problems: list[str] = []
    snippet = payload.get("snippet", {})
    title = snippet.get("title", "")
    if not title.strip():
        problems.append("عنوان خالی است")
    if len(title) > MAX_TITLE:
        problems.append(f"عنوان {len(title)} کاراکتر است (حداکثر {MAX_TITLE})")
    description = snippet.get("description", "")
    if len(description) > MAX_DESCRIPTION:
        problems.append(f"توضیحات بیش از {MAX_DESCRIPTION} کاراکتر است")
    tag_chars = sum(len(t) + 1 for t in snippet.get("tags", []))
    if tag_chars > MAX_TAGS_CHARS:
        problems.append(f"هشتگ‌ها {tag_chars} کاراکتر است (حداکثر {MAX_TAGS_CHARS})")
    if "<" in title or ">" in title:
        problems.append("عنوان نباید شامل < یا > باشد")
    status = payload.get("status", {})
    if status.get("privacyStatus") not in {"public", "private", "unlisted"}:
        problems.append("privacyStatus نامعتبر است")
    if status.get("publishAt") and status.get("privacyStatus") != "private":
        problems.append("برای زمان‌بندی، privacyStatus باید private باشد")
    return problems


# ------------------------------------------------------------------- upload
def upload_video(
    project: Project,
    rundown: Rundown,
    privacy: str = "unlisted",
    publish_at: str | None = None,
    dry_run: bool = False,
    upload_thumbnail: bool = True,
    upload_captions: bool = True,
    client_secret=None,
    token=None,
    echo: Callable[[str], None] = print,
    api=None,
) -> dict:
    """Upload the approved MP4 (+ thumbnail + Persian subtitles) to YouTube."""
    from .review import approval_status

    # a dry-run is only a preview, so it may run before approval; a real upload may not
    status = approval_status(project) if dry_run else verify(project)
    video = project.video_path
    if not video.exists():
        raise FileNotFoundError("ویدیو ساخته نشده است؛ اول `telton render`")

    aspect = f"{project.style.width}:{project.style.height}"
    payload = build_payload(project, rundown, privacy=privacy, publish_at=publish_at)
    problems = validate_payload(payload)
    if problems:
        raise ValueError("درخواست آپلود معتبر نیست: " + "؛ ".join(problems))

    record = status.get("record") or {}
    if dry_run:
        return {
            "dry_run": True,
            "approved": status.get("approved", False),
            "video": str(video),
            "size_mb": round(video.stat().st_size / 1e6, 1),
            "aspect": aspect,
            "approved_by": record.get("by"),
            "sha256": status.get("sha256"),
            "api_request": payload,
            "note": "هیچ آپلودی انجام نشد؛ فقط بدنه‌ی videos.insert چاپ شد.",
        }

    service_api = api or service(client_secret, token, interactive=False, echo=echo)
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    request = service_api.videos().insert(
        part="snippet,status", body=payload, media_body=media, notifySubscribers=True
    )
    response = None
    guard = 0
    while response is None:
        chunk, response = request.next_chunk()
        if chunk:
            echo(f"  uploading… {int(chunk.progress() * 100)}%")
        guard += 1
        if guard > 500:
            raise RuntimeError("upload stalled")

    video_id = response.get("id", "")
    result = {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "studio": f"https://studio.youtube.com/video/{video_id}/edit",
        "privacy": payload["status"]["privacyStatus"],
        "title": payload["snippet"]["title"],
        "duration": seconds_to_clock(rundown.end),
        "aspect": aspect,
        "approved_by": status["record"].get("by"),
        "sha256": status["sha256"],
        "thumbnail": None,
        "captions": None,
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    thumb = project.out / "thumbnail.jpg"
    if upload_thumbnail and thumb.exists() and video_id:
        try:
            service_api.thumbnails().set(videoId=video_id, media_body=str(thumb)).execute()
            result["thumbnail"] = True
        except Exception as exc:                  # unverified channel → 403
            result["thumbnail"] = f"failed: {type(exc).__name__}"
            echo(f"  تامبنیل آپلود نشد ({type(exc).__name__}) — دستی در Studio بگذار.")

    srt = project.build / "subtitles.srt"
    if upload_captions and srt.exists() and video_id:
        try:
            service_api.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": "fa",
                        "name": "فارسی",
                        "isDraft": False,
                    }
                },
                media_body=str(srt),
            ).execute()
            result["captions"] = True
        except Exception as exc:
            result["captions"] = f"failed: {type(exc).__name__}"
            echo(f"  زیرنویس آپلود نشد ({type(exc).__name__}) — فایل SRT را دستی بگذار.")

    write_json(project.out / "upload-youtube.json", result)
    return result


def status(client_secret=None, token=None) -> dict:
    """Is upload configured, and whose channel is it?"""
    secret = client_secret_path(client_secret)
    token_file = token_path(token)
    info = {
        "client_secret": str(secret),
        "client_secret_exists": secret.exists(),
        "token": str(token_file),
        "token_exists": token_file.exists(),
        "ready": False,
        "platform_note": PLATFORMS["youtube"]["note"],
    }
    if token_file.exists():
        try:
            api = service(client_secret, token, interactive=False, echo=lambda *_: None)
            channels = api.channels().list(part="snippet,statistics", mine=True).execute()
            item = (channels.get("items") or [{}])[0]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            info.update(
                {
                    "ready": True,
                    "channel_title": snippet.get("title"),
                    "channel_id": item.get("id"),
                    "subscribers": stats.get("subscriberCount"),
                    "videos": stats.get("videoCount"),
                }
            )
        except Exception as exc:
            info["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return info
