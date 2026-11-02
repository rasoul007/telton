"""Rendering/graphics tests: RTL shaping, wrapping, and a real (tiny) video render."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from telton.config import load_style
from telton.graphics import HAS_RAQM, Renderer, _direction_for, chip, draw_text, shape, text_width
from telton.models import Rundown
from telton.rundown import build
from telton.render import FramePainter, export_thumbnail, render_video
from telton.util import probe_duration


def test_shape_converts_digits_and_keeps_logical_order():
    out = shape("سلام 1953")
    assert "۱۹۵۳" in out
    assert "سلام" in out


def test_shape_matches_backend():
    if HAS_RAQM:
        # HarfBuzz does the bidi; we must not pre-reverse the string.
        assert shape("سلام دنیا") == "سلام دنیا"
    else:  # pragma: no cover - depends on the Pillow build
        assert shape("سلام دنیا") != "سلام دنیا"


def test_direction_helper_keeps_latin_left_to_right():
    assert _direction_for("telton.sport") == {"direction": "ltr"}
    assert _direction_for("ورزش ایران") == {"direction": "rtl"}
    assert _direction_for("لیورپول ۰ – ۱ آرسنال") == {"direction": "rtl"}


def test_draw_text_renders_rtl_without_mirroring():
    """A Persian phrase must fill a wider-than-tall area and honour its right edge."""
    renderer = Renderer(load_style(), 540, 200)
    image = Image.new("RGB", (540, 200), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = renderer.font("black", 60)
    width = text_width(draw, "ورزش ایران", font)
    draw_text(draw, (520 - width, 60), "ورزش ایران", font, (255, 255, 255))
    bbox = image.convert("L").point(lambda p: 255 if p > 40 else 0).getbbox()
    assert bbox is not None
    drawn_w, drawn_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    assert drawn_w > drawn_h * 2          # a joined RTL phrase, not a stack of glyphs
    assert bbox[2] <= 522                 # stays inside the right margin


def test_wrap_respects_max_width():
    renderer = Renderer(load_style(), 540, 960)
    lines = renderer.wrap("پرسپولیس با برد یک بر صفر در قائمشهر به صدر جدول برگشت", "bold", 48, 400)
    assert len(lines) > 1
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font = renderer.font("bold", 48)
    for line in lines:
        assert draw.textlength(shape(line), font=font) <= 400 + 1


def test_text_block_returns_lower_y_for_multiline():
    renderer = Renderer(load_style(), 540, 960)
    image = Image.new("RGB", (540, 960), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    top = 100
    bottom = renderer.text_block(draw, "خط اول و کلمات بیشتر برای شکستن خط", (500, top), size=40, max_width=260)
    assert bottom > top


def test_chip_draws_left_of_anchor():
    renderer = Renderer(load_style(), 540, 960)
    image = Image.new("RGB", (540, 960), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    left = chip(draw, renderer, "۲۳ امتیاز", 500, 300, size=30)
    assert left < 500
    assert image.getbbox() is not None


def test_plate_is_cached_and_right_size():
    renderer = Renderer(load_style(), 270, 480)
    first = renderer.plate(3)
    second = renderer.plate(3)
    assert first.size == (270, 480)
    assert first is not second  # a copy, so callers may mutate it


def test_plate_survives_every_seed():
    renderer = Renderer(load_style(), 108, 192)
    for seed in range(16):
        assert renderer.plate(seed).size == (108, 192)


@pytest.fixture()
def small_rundown(project) -> Rundown:
    return build(project, target=40)


def test_frame_painter_draws_full_canvas(project, small_rundown):
    painter = FramePainter(project, small_rundown, width=270, height=480)
    frame = painter.frame(1.0)
    assert frame.size == (270, 480)
    assert frame.mode == "RGB"
    painter.close()


def test_render_video_produces_playable_mp4(project, small_rundown, tmp_path: Path):
    out = tmp_path / "draft.mp4"
    path = render_video(
        project, small_rundown, None, out_path=out, width=270, height=480, fps=12,
        max_seconds=3.0, progress=False,
    )
    assert path.exists() and path.stat().st_size > 1000
    assert 2.0 <= probe_duration(path) <= 4.0


def test_export_thumbnail(project, small_rundown):
    thumb = export_thumbnail(project, small_rundown, at=2.0)
    assert thumb.exists()
    with Image.open(thumb) as image:
        assert image.width == load_style().width
