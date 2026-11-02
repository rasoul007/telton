"""Telegram source tests — parsing and matching run fully offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from telton import telegram
from telton.models import Story
from telton.rundown import load_stories

MARKUP = """
<div class="tgme_widget_message_wrap" data-post="varzesh3/1001">
  <a class="tgme_widget_message_video_player"><i class="tgme_widget_message_video_thumb"
     style="background-image:url('https://cdn4.telesco.pe/file/aaa.jpg?x=1&amp;y=2')"></i></a>
  <div class="tgme_widget_message_text js-message_text">گل اول آرسنال مقابل لیورپول &amp; VAR</div>
  <video src="https://cdn4.telesco.pe/file/aaa.mp4?token=t1&amp;x=2"></video>
</div>
<div class="tgme_widget_message_wrap" data-post="varzesh3/1002">
  <div class="tgme_widget_message_text js-message_text">ترکیب یوونتوس و ناپولی</div>
</div>
<div class="tgme_widget_message_wrap" data-post="varzesh3/1003">
  <a class="tgme_widget_message_photo_wrap">
     <i class="tgme_widget_message_photo" style="background-image:url('https://cdn4.telesco.pe/file/bbb.jpg')"></i>
  </a>
  <div class="tgme_widget_message_text js-message_text">تصویر جدول کشتی فرنگی</div>
</div>
"""


def test_parse_posts_extracts_media_and_text():
    posts = telegram.parse_posts(MARKUP, "varzesh3")
    assert len(posts) == 2  # the message without media is skipped
    video_post, photo_post = posts
    assert video_post.id == "1001"
    assert video_post.channel == "varzesh3"
    assert video_post.videos == ["https://cdn4.telesco.pe/file/aaa.mp4?token=t1&x=2"]
    assert "VAR" in video_post.clean_text and "&" in video_post.clean_text
    assert photo_post.photos and not photo_post.videos
    assert video_post.url.endswith("/varzesh3/1001")


def test_match_score_ignores_generic_words():
    generic = Story(id="t", bucket="iran_football", headline="صدر جدول لیگ برتر",
                    summary="جدول لیگ برتر ایران", tags=["لیگ برتر", "جدول"])
    specific = Story(id="a", bucket="europe_football", headline="آرسنال در آنفیلد",
                     summary="برد آرسنال", tags=["آرسنال", "لیورپول"])
    post = telegram.TgPost(channel="varzesh3", id="1", text="جدول لیگ برتر ایران")
    assert telegram.match_score(generic, post) == 0
    post2 = telegram.TgPost(channel="varzesh3", id="2", text="ترکیب آرسنال و لیورپول امشب")
    assert telegram.match_score(specific, post2) >= 4


def test_auto_broll_writes_broll_into_stories(project, monkeypatch):
    posts = [
        telegram.TgPost(channel="varzesh3", id="9001", text="ترکیب آرسنال و لیورپول",
                        videos=["https://example.com/clip.mp4"]),
    ]
    monkeypatch.setattr(telegram, "fetch_posts", lambda *a, **k: posts)
    monkeypatch.setattr(telegram, "REPO_ROOT", project.root)
    downloaded: list[Path] = []

    def fake_download(url: str, dest: Path, timeout: float = 60.0) -> int:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake")
        downloaded.append(dest)
        return 4

    monkeypatch.setattr(telegram, "download", fake_download)
    report = telegram.auto_broll(project, channel="varzesh3", min_score=4, max_clips=2)
    statuses = {item["story"]: item["status"] for item in report}
    assert statuses["beta"] == "downloaded-video"
    assert downloaded and downloaded[0].name == "tg-varzesh3-9001.mp4"
    stories = {story.id: story for story in load_stories(project)}
    assert stories["beta"].broll == "tg-varzesh3-9001.mp4"


def test_auto_broll_dry_run_does_not_change_stories(project, monkeypatch):
    posts = [telegram.TgPost(channel="varzesh3", id="9002", text="آرسنال لیورپول",
                            videos=["https://example.com/c.mp4"])]
    monkeypatch.setattr(telegram, "fetch_posts", lambda *a, **k: posts)
    before = project.stories_path.read_text(encoding="utf-8")
    report = telegram.auto_broll(project, channel="varzesh3", min_score=4, dry_run=True)
    assert any(item["status"] == "would-download-video" for item in report)
    assert project.stories_path.read_text(encoding="utf-8") == before


def test_download_failure_is_reported_not_raised(project, monkeypatch):
    posts = [telegram.TgPost(channel="varzesh3", id="9003", text="آرسنال لیورپول",
                            videos=["https://example.com/broken.mp4"])]
    monkeypatch.setattr(telegram, "fetch_posts", lambda *a, **k: posts)

    def boom(*args, **kwargs):
        raise OSError("HTTP Error 500")

    monkeypatch.setattr(telegram, "download", boom)
    report = telegram.auto_broll(project, channel="varzesh3", min_score=4)
    assert any(item["status"] == "download-failed" for item in report)
    assert json.loads(project.stories_path.read_text(encoding="utf-8"))[1]["broll"] in (None, "")
