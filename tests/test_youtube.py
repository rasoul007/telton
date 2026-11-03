"""YouTube upload tests — the API is faked, so nothing leaves the machine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from telton import youtube as yt
from telton.publish import NotApproved
from telton.review import approve
from telton.rundown import build


class FakeRequest:
    def __init__(self, response):
        self._response = response
        self.calls = 0

    def next_chunk(self):
        self.calls += 1
        return (type("Chunk", (), {"progress": lambda self=None: 1.0})(), self._response)

    def execute(self):
        self.calls += 1
        return self._response


class FakeVideos:
    def __init__(self, parent):
        self.parent = parent

    def insert(self, **kwargs):
        self.parent.insert_body = kwargs
        return FakeRequest({"id": "VID123"})


class FakeThumbnails:
    def __init__(self, parent):
        self.parent = parent

    def set(self, **kwargs):
        self.parent.thumbnail_args = kwargs
        return FakeRequest({"kind": "youtube#thumbnailSetResponse"})


class FakeCaptions:
    def __init__(self, parent):
        self.parent = parent

    def insert(self, **kwargs):
        self.parent.caption_args = kwargs
        return FakeRequest({"kind": "youtube#caption"})


class FakeYouTube:
    def __init__(self, fail_thumbnail: bool = False):
        self.insert_body = None
        self.thumbnail_args = None
        self.caption_args = None
        self.fail_thumbnail = fail_thumbnail

    def videos(self):
        return FakeVideos(self)

    def thumbnails(self):
        if self.fail_thumbnail:
            class Boom:
                def set(self, **kwargs):
                    def execute():
                        raise RuntimeError("403 forbidden")

                    return type("Req", (), {"execute": staticmethod(execute)})()
            return Boom()
        return FakeThumbnails(self)

    def captions(self):
        return FakeCaptions(self)


@pytest.fixture()
def approved_project(project):
    rundown = build(project, target=30)
    project.video_path.write_bytes(b"\x00fake" * 500)
    (project.build / "subtitles.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nسلام\n", "utf-8")
    (project.out).mkdir(parents=True, exist_ok=True)
    (project.out / "thumbnail.jpg").write_bytes(b"\xff\xd8\xff")
    approve(project, by="راسول")
    return project, rundown


def test_upload_requires_approval(project):
    rundown = build(project, target=20)
    project.video_path.write_bytes(b"x")
    with pytest.raises(NotApproved):
        yt.upload_video(project, rundown, api=FakeYouTube())


def test_payload_has_title_tags_and_sports_category(approved_project):
    project, rundown = approved_project
    payload = yt.build_payload(project, rundown, privacy="unlisted")
    assert payload["snippet"]["title"]
    assert len(payload["snippet"]["title"]) <= yt.MAX_TITLE
    assert payload["snippet"]["categoryId"] == "17"
    assert payload["snippet"]["defaultLanguage"] == "fa"
    assert payload["status"]["privacyStatus"] == "unlisted"
    assert payload["status"]["selfDeclaredMadeForKids"] is False
    assert isinstance(payload["snippet"]["tags"], list)
    assert yt.validate_payload(payload) == []


def test_scheduling_forces_private(approved_project):
    project, rundown = approved_project
    payload = yt.build_payload(project, rundown, privacy="public", publish_at="2026-11-03T18:30:00Z")
    assert payload["status"]["privacyStatus"] == "private"
    assert payload["status"]["publishAt"] == "2026-11-03T18:30:00Z"
    assert yt.validate_payload(payload) == []


def test_validate_catches_bad_payload():
    problems = yt.validate_payload(
        {"snippet": {"title": "x" * 200, "description": "", "tags": []}, "status": {"privacyStatus": "nope"}}
    )
    assert any("عنوان" in p for p in problems)
    assert any("privacyStatus" in p for p in problems)


def test_long_description_is_trimmed_without_breaking_links():
    caption = "توضیح\n" + ("متن " * 1200)      # already near the 5000-char limit
    sources = [f"- منبع {i}: https://example.com/very/long/path/{i}" for i in range(40)]
    result = yt._assemble_description(caption, sources, "\n\n⏱ 05:00 · tooop news")
    assert len(result) <= yt.MAX_DESCRIPTION
    assert "منبع دیگر" in result            # tells the reader where it stopped
    assert "https://example.com/very/long/path/" in result  # links stay whole
    assert not result.endswith(".com/very/long")  # never a half link


def test_dry_run_touches_nothing(approved_project):
    project, rundown = approved_project
    result = yt.upload_video(project, rundown, dry_run=True, api=FakeYouTube())
    assert result["dry_run"] is True
    assert result["api_request"]["snippet"]["categoryId"] == "17"
    assert result["approved_by"] == "راسول"
    assert not (project.out / "upload-youtube.json").exists()


def test_upload_returns_url_thumbnail_and_captions(approved_project):
    project, rundown = approved_project
    fake = FakeYouTube()
    result = yt.upload_video(project, rundown, api=fake, echo=lambda *_: None)
    assert fake.insert_body["part"] == "snippet,status"
    assert fake.insert_body["body"]["snippet"]["title"] == result["title"]
    assert result["video_id"] == "VID123"
    assert result["url"] == "https://youtu.be/VID123"
    assert result["thumbnail"] is True
    assert result["captions"] is True
    assert fake.caption_args["body"]["snippet"]["language"] == "fa"
    saved = json.loads((project.out / "upload-youtube.json").read_text(encoding="utf-8"))
    assert saved["video_id"] == "VID123"


def test_thumbnail_failure_does_not_kill_the_upload(approved_project):
    project, rundown = approved_project
    result = yt.upload_video(project, rundown, api=FakeYouTube(fail_thumbnail=True), echo=lambda *_: None)
    assert result["video_id"] == "VID123"
    assert str(result["thumbnail"]).startswith("failed")


def test_missing_credentials_message_is_actionable(project, tmp_path):
    with pytest.raises(yt.YouTubeNotConfigured) as excinfo:
        yt.load_credentials(
            client_secret=tmp_path / "nope.json", token=tmp_path / "nope-token.json", interactive=False
        )
    assert "youtube auth" in str(excinfo.value)


def test_status_reports_missing_secret(tmp_path):
    info = yt.status(client_secret=tmp_path / "c.json", token=tmp_path / "t.json")
    assert info["ready"] is False
    assert info["client_secret_exists"] is False
