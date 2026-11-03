"""Rundown composition, approval gate and publish-kit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from telton.collect import classify
from telton.config import load_sources
from telton.models import Rundown, Story
from telton.publish import NotApproved, make_kit, upload, verify
from telton.review import approval_status, approve, build_review, unverified_stories
from telton.rundown import build, chunk_cues, load_stories, refit, save_stories, sentences
from telton.util import read_json


def test_build_never_overshoots_target_and_pads_between(project):
    """With little content the agent pads but must not invent dead air beyond the cap."""
    rundown = build(project, target=60)
    assert rundown.end <= 60.5
    assert rundown.end >= 40  # padded compared to the raw ~41s composition


def test_build_hits_target_with_enough_stories(project):
    """Never overshoot the target; thin content simply yields a shorter episode."""
    stories = load_stories(project)
    template = stories[0]
    expanded = []
    for i in range(12):
        clone = Story.from_dict(
            {**template.to_dict(), "id": f"story-{i}", "headline": f"خبر شماره {i}"}
        )
        expanded.append(clone)
    save_stories(project, expanded)
    rundown = build(project, target=150)
    assert rundown.end <= 150 * 1.02
    assert rundown.end >= 150 * 0.6


def test_segments_and_cues_are_contiguous(project):
    rundown = build(project, target=60)
    clock = 0.0
    for segment in rundown.segments:
        assert segment.start == pytest.approx(clock, abs=0.01)
        for cue in segment.cues:
            assert segment.start - 0.01 <= cue.start <= cue.end <= segment.end + 0.01
        clock = segment.end


def test_section_cards_appear_once_per_bucket(project):
    rundown = build(project, target=60)
    cards = [s.bucket for s in rundown.segments if s.kind == "title"]
    assert len(cards) == len(set(cards))


def test_script_srt_and_caption_are_written(project):
    rundown = build(project, target=60)
    for name in ("script.md", "subtitles.srt", "caption.txt", "rundown.json"):
        assert (project.build / name).exists()
    srt = (project.build / "subtitles.srt").read_text(encoding="utf-8")
    assert "-->" in srt
    assert "پرسپولیس" in srt


def test_chunk_cues_splits_long_sentences():
    text = " ".join(["کلمه"] * 30)
    chunks = chunk_cues(text, 10)
    assert all(len(chunk.split()) <= 10 for chunk in chunks)
    assert sum(len(c.split()) for c in chunks) == 30


def test_sentences_split_on_persian_punctuation():
    assert sentences("اول. دوم؟ سوم!") == ["اول.", "دوم؟", "سوم!"]


def test_refit_respects_target(project):
    rundown = build(project, target=90)
    refit(rundown, 45)
    assert rundown.end <= 90
    assert rundown.segments[0].start == 0


def test_unverified_stories_reported(project):
    stories = load_stories(project)
    stories[0].verified = False
    from telton.rundown import save_stories

    save_stories(project, stories)
    rundown = build(project, target=60)
    assert "alpha" in unverified_stories(rundown)


def test_collect_classification_uses_keyword_rules():
    buckets = load_sources()["buckets"]
    assert classify("پرسپولیس برد", buckets, "world")[0] == "iran_football"
    assert classify("Iran win Greco-Roman wrestling title", buckets, "world")[0] == "iran_other"
    assert classify("Arsenal beat Liverpool in Premier League", buckets, "world")[0] == "europe_football"
