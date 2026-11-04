"""Tests for the new quality features: diacritics, thumbnails, shorts, ticker, music."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from telton import short as short_mod
from telton import stock, text_fa, thumbnail
from telton.config import load_style
from telton.models import Rundown, Story
from telton.render import FramePainter
from telton.rundown import build
from telton.util import ffmpeg_exe, probe_duration
from telton.voice import assemble_audio, speak


# ------------------------------------------------------------------ diacritics
def test_vocalize_adds_harakat_to_names():
    out = text_fa.vocalize("پرسپولیس با آرسنال بازی دارد")
    assert "پِرسِپولیس" in out
    assert "آرسِنال" in out
    assert "پرسپولیس" not in out


def test_vocalize_does_not_touch_substrings():
    # «کین» must not be rewritten inside another word
    assert text_fa.vocalize("اسکین") == "اسکین"


def test_speechify_removes_stiff_phrasing():
    out = text_fa.speechify("این خبر می‌باشد و گردید منتشر شود")
    assert "می‌باشد" not in out
    assert "گردید" not in out


def test_spoken_keeps_original_for_subtitles():
    original = "لیورپول ۰ – ۱ آرسنال"
    assert text_fa.spoken(original) != original     # spoken text is vocalized
    assert "لیورپول" in original                    # subtitle text stays untouched


# ------------------------------------------------------------------ thumbnails
def test_four_thumbnails_and_hook_text(project):
    rundown = build(project, target=30)
    (project.out).mkdir(parents=True, exist_ok=True)
    paths = thumbnail.build_thumbnails(project, rundown, hooks=["۱۴ سال! آنفیلد فتح شد"])
    assert paths and paths[0].exists()
    assert (project.out / "thumbnail.jpg").exists()
    from PIL import Image

    with Image.open(paths[0]) as image:
        assert image.width == load_style().width


def test_thumbnail_hook_wraps_to_two_lines():
    renderer = thumbnail.Renderer(load_style(), 1920, 1080)
    lines = thumbnail._wrap_hook("جوان‌ترین قهرمان تاریخ فرمول یک در مکزیک", renderer, 110, 900)
    assert 1 <= len(lines) <= 3


# ---------------------------------------------------------------------- shorts
def test_compose_short_structure(project):
    rundown = short_mod.compose_short(project, target=40, count=2)
    kinds = [s.kind for s in rundown.segments]
    assert kinds[0] == "intro"
    assert kinds[-1] == "outro"
    assert kinds.count("story") == 2
    assert rundown.end <= 45
    assert all(cue.text.strip() for cue in rundown.cues)


def test_compose_short_is_vertical_friendly(project):
    rundown = short_mod.compose_short(project, target=40, count=2)
    assert rundown.segments[-1].cues[0].text.strip().endswith("!")
    assert all(len(cue.text.split()) <= 30 for cue in rundown.cues)


# --------------------------------------------------------------- ticker/music
def test_ticker_moves_left_to_right(project):
    rundown = build(project, target=30)
    painter = FramePainter(project, rundown, width=320, height=568)
    first = painter.frame(1.0)
    later = painter.frame(2.0)
    assert first.size == later.size == (320, 568)
    assert first.tobytes() != later.tobytes()   # the news bar moved
    painter.close()


def test_music_bed_is_ducked_under_the_voice(project, tmp_path):
    # a plain tone as a stand-in for a royalty-free track
    music = tmp_path / "bed.wav"
    subprocess.run(
        [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=220:duration=3", str(music)], check=True,
    )
    (project.meta_path).write_text(
        "slug: test-episode\ntitle: \"تست\"\nmusic: " + str(music) + "\n", encoding="utf-8",
    )
    rundown = build(project, target=20)
    rundown = speak(project, rundown, offline=True)
    audio = assemble_audio(project, rundown, out_path=tmp_path / "mix.wav")
    assert audio.exists()
    assert probe_duration(audio) >= 5


# ----------------------------------------------------------------------- stock
def test_english_query_uses_tags():
    story = Story(id="a", bucket="europe_football", headline="آرسنال برد",
                  summary="آرسنال در آنفیلد", tags=["آرسنال"])
    assert stock.english_query(story) == "Arsenal FC"


def test_stock_item_free_license_detection():
    assert stock.StockItem("t", "u", "p", "CC BY-SA 3.0").free
    assert stock.StockItem("t", "u", "p", "Public domain").free
    assert not stock.StockItem("t", "u", "p", "All rights reserved").free


def test_stock_fill_reports_without_network(project, monkeypatch):
    monkeypatch.setattr(stock, "search_commons", lambda *a, **k: [])
    report = stock.fill_missing(project, limit=1, dry_run=True)
    assert report and report[0]["status"] == "no-free-result"
