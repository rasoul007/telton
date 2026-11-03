"""The approval gate is the most important safety property: nothing ships unapproved."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from telton.publish import NotApproved, make_kit, upload, verify
from telton.review import approval_status, approve, build_review
from telton.rundown import build, save_stories, load_stories


@pytest.fixture()
def rendered(project):
    """A project with a fake-but-real video file and a rundown."""
    rundown = build(project, target=30)
    project.video_path.write_bytes(b"\x00fake-mp4-bytes" * 100)
    return project, rundown


def test_status_is_not_approved_without_record(rendered):
    project, _ = rendered
    status = approval_status(project)
    assert status["approved"] is False
    assert status["reasons"]


def test_publish_refuses_without_approval(rendered):
    project, rundown = rendered
    with pytest.raises(NotApproved):
        verify(project)
    with pytest.raises(NotApproved):
        make_kit(project, rundown)
    with pytest.raises(NotApproved):
        upload(project, "youtube")


def test_approve_then_publish_creates_kit(rendered):
    project, rundown = rendered
    record = approve(project, by="راسول")
    assert record["sha256"]
    assert approval_status(project)["approved"] is True
    kit = make_kit(project, rundown)
    video_name = f"video-{project.style.width}x{project.style.height}.mp4"
    for name in (video_name, "subtitles.srt", "caption.txt", "sources.md",
                 "checklist.md", "manifest.json"):
        assert (kit / name).exists(), name
    manifest = (kit / "manifest.json").read_text(encoding="utf-8")
    assert "راسول" in manifest
    assert f"{project.style.width}:{project.style.height}" in manifest


def test_editing_the_video_after_approval_blocks_publish(rendered):
    project, rundown = rendered
    approve(project, by="راسول")
    project.video_path.write_bytes(project.video_path.read_bytes() + b"changed")
    status = approval_status(project)
    assert status["approved"] is False
    assert "هش" in " ".join(status["reasons"])
    with pytest.raises(NotApproved):
        make_kit(project, rundown)


def test_unverified_story_blocks_approval_unless_forced(rendered):
    project, _ = rendered
    stories = load_stories(project)
    stories[0].verified = False
    save_stories(project, stories)
    build(project, target=30)
    project.video_path.write_bytes(b"video")
    with pytest.raises(PermissionError):
        approve(project, by="راسول")
    record = approve(project, by="راسول", force=True)
    assert record["forced"] is True


def test_review_page_contains_sources_and_commands(rendered):
    project, rundown = rendered
    page = build_review(project, rundown)
    html = page.read_text(encoding="utf-8")
    assert "telton approve" in html
    assert "example.com/a" in html
    assert "بازبینی" in html


def test_upload_stub_reports_ready(rendered):
    project, _ = rendered
    approve(project, by="راسول")
    make_kit(project, build(project, target=30))
    payload = upload(project, "instagram")
    assert payload["status"] == "ready-to-upload"
    assert payload["dry_run"] is True
    with pytest.raises(ValueError):
        upload(project, "myspace")
