"""Unit tests for the low-level helpers and the data model."""

from __future__ import annotations

import pytest

from telton.models import Rundown, Segment, Cue, Source, Story
from telton.util import (
    estimate_duration,
    fa_digits,
    normalize_title,
    seconds_to_clock,
    seconds_to_srt,
    word_count,
)


def test_fa_digits_converts_ascii_numbers():
    assert fa_digits("2026 سال 11") == "۲۰۲۶ سال ۱۱"
    assert fa_digits("بدون عدد") == "بدون عدد"


def test_seconds_to_srt_and_clock():
    assert seconds_to_srt(0) == "00:00:00,000"
    assert seconds_to_srt(75.25) == "00:01:15,250"
    assert seconds_to_srt(3725.5) == "01:02:05,500"
    assert seconds_to_clock(300) == "05:00"
    assert seconds_to_clock(59.4) == "00:59"


def test_estimate_duration_scales_with_words():
    short = estimate_duration("یک دو سه", 3.0)
    long = estimate_duration("یک دو سه چهار پنج شش", 3.0)
    assert long > short
    assert estimate_duration("", 3.0) == 1.2  # never zero-length


def test_word_count_and_normalize_title():
    assert word_count("  یک   دو سه ") == 3
    assert normalize_title("Liverpool 0-1 Arsenal | BBC Sport") == "liverpool 0 1 arsenal"


def test_story_roundtrip_and_validation():
    story = Story.from_dict(
        {
            "id": "x",
            "bucket": "iran_other",
            "headline": "ایران قهرمان شد",
            "summary": "تیم ملی کشتی فرنگی قهرمان جهان شد.",
            "facts": ["۶ طلا"],
            "sources": ["فدراسیون کشتی"],
            "verified": True,
        }
    )
    assert story.sources[0].name == "فدراسیون کشتی"
    assert story.source_line == "فدراسیون کشتی"
    again = Story.from_dict(story.to_dict())
    assert again.headline == story.headline
    with pytest.raises(ValueError):
        Story(id="y", bucket="nope", headline="h", summary="s")


def test_source_accepts_dict_or_string():
    assert Source.from_dict("BBC").url == ""
    assert Source.from_dict({"name": "BBC", "url": "u"}).url == "u"


def test_rundown_renumber_and_serialisation():
    segment = Segment(id="s", title="t", start=0, end=2)
    segment.cues = [Cue(index=0, text="الف"), Cue(index=0, text="ب")]
    rundown = Rundown(slug="s", title="t", segments=[segment])
    rundown.renumber()
    assert [c.index for c in rundown.cues] == [1, 2]
    clone = Rundown.from_dict(rundown.to_dict())
    assert clone.end == rundown.end
    assert [c.text for c in clone.cues] == ["الف", "ب"]
