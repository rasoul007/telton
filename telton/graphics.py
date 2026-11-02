"""RTL-aware frame painting with Pillow (Vazirmatn + arabic_reshaper + bidi)."""

from __future__ import annotations

from functools import lru_cache

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features as ImageFeatures

from .config import Style
from .util import fa_digits

# Pillow built with Raqm/HarfBuzz does shaping + bidi itself; if it is missing we
# fall back to arabic_reshaper + python-bidi (and draw left-to-right manually).
HAS_RAQM = ImageFeatures.check("raqm")
DIRECTION = {"direction": "rtl"} if HAS_RAQM else {}
_ARABIC = set("اآبپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیئءأؤإۀيك")


def _direction_for(text: str) -> dict:
    """Latin-only strings (handles, URLs, scores) must stay left-to-right."""
    if not HAS_RAQM:
        return {}
    return DIRECTION if any(ch in _ARABIC for ch in text) else {"direction": "ltr"}


@lru_cache(maxsize=512)
def shape(text: str) -> str:
    """Prepare Persian text for Pillow (digits + optional manual bidi)."""
    if not text:
        return ""
    if HAS_RAQM:
        return fa_digits(text)
    return "\n".join(
        get_display(arabic_reshaper.reshape(fa_digits(line))) for line in str(text).split("\n")
    )


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(shape(text), font=font, **_direction_for(text))


def draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill,
    stroke: int = 0,
    stroke_fill=(0, 0, 0),
) -> None:
    draw.text(
        xy,
        shape(text),
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=stroke_fill,
        **_direction_for(text),
    )


class Renderer:
    def __init__(self, style: Style, width: int | None = None, height: int | None = None):
        self.style = style
        self.width = width or style.width
        self.height = height or style.height
        self.bg = style.color("bg", "#0B0E13")
        self.bg2 = style.color("bg2", "#161E2B")
        self.panel = style.color("panel", "#101826")
        self.accent = style.color("accent", "#FFD400")
        self.accent2 = style.color("accent2", "#E10600")
        self.text_color = style.color("text", "#FFFFFF")
        self.muted = style.color("muted", "#9AA4B2")
        self._fonts: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    # ---------------------------------------------------------------- fonts
    def font(self, weight: str, size: int) -> ImageFont.FreeTypeFont:
        key = (weight, size)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(str(self.style.font_path(weight)), size)
        return self._fonts[key]

    # ----------------------------------------------------------------- text
    def wrap(self, text: str, weight: str, size: int, max_width: int) -> list[str]:
        """Greedy word wrap that measures the *shaped* glyphs."""
        font = self.font(weight, size)
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        lines: list[str] = []
        current: list[str] = []
        for word in str(text).split():
            candidate = " ".join(current + [word])
            if text_width(probe, candidate, font) <= max_width or not current:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines

    def text_block(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        xy: tuple[int, int],
        weight: str = "bold",
        size: int = 56,
        max_width: int = 900,
        fill: tuple[int, int, int] | None = None,
        line_gap: int = 10,
        align: str = "right",
        anchor_y: str = "top",
        stroke: int = 0,
        stroke_fill: tuple[int, int, int] = (0, 0, 0),
    ) -> int:
        """Draw wrapped RTL text and return the y coordinate after the block."""
        font = self.font(weight, size)
        lines = self.wrap(text, weight, size, max_width)
        line_height = int(size * 1.2) + line_gap
        y = xy[1]
        if anchor_y == "middle":
            y -= (line_height * len(lines)) // 2
        for line in lines:
            width = text_width(draw, line, font)
            if align == "right":
                x = xy[0] - width
            elif align == "center":
                x = xy[0] - width / 2
            else:
                x = xy[0]
            draw_text(
                draw,
                (x, y),
                line,
                font,
                fill if fill is not None else self.text_color,
                stroke=stroke,
                stroke_fill=stroke_fill,
            )
            y += line_height
        return y

    # ---------------------------------------------------------------- plates
    def plate(self, seed: int = 0, accent: tuple[int, int, int] | None = None) -> Image.Image:
        """Dark vertical gradient with a soft accent glow (cached, copied per use)."""
        return self._plate(seed % 16, accent or self.accent2).copy()

    @lru_cache(maxsize=16)
    def _plate(self, seed: int, accent: tuple[int, int, int]) -> Image.Image:
        w, h = self.width, self.height
        base = Image.new("RGB", (w, h), self.bg)
        draw = ImageDraw.Draw(base)
        for y in range(h):
            t = y / max(1, h - 1)
            color = tuple(
                int(self.bg[i] + (self.bg2[i] - self.bg[i]) * (t ** 0.8)) for i in range(3)
            )
            draw.line([(0, y), (w, y)], fill=color)
        glow = Image.new("RGB", (w, h), (0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        spread = 140 + seed * 25
        y0 = -h // 3 + (seed % 6) * h // 12
        gdraw.ellipse(
            [-w // 3, y0, w // 2, max(y0 + 10, h // 3)],
            fill=tuple(int(c * 0.5) for c in accent),
        )
        glow = glow.filter(ImageFilter.GaussianBlur(spread))
        return Image.blend(base, glow, 0.35)


def chip(
    draw: ImageDraw.ImageDraw,
    renderer: Renderer,
    text: str,
    right_x: int,
    top_y: int,
    size: int = 40,
    fill: tuple[int, int, int] | None = None,
    text_fill: tuple[int, int, int] = (10, 12, 16),
) -> int:
    """Draw a rounded 'fact pill' whose right edge is right_x; returns its left edge."""
    font = renderer.font("bold", size)
    width = text_width(draw, text, font)
    pad_x, pad_y = int(size * 0.62), int(size * 0.34)
    x1 = right_x
    x0 = int(x1 - width - 2 * pad_x)
    y0 = top_y
    y1 = top_y + size + 2 * pad_y
    draw.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) // 2, fill=fill or renderer.accent)
    draw_text(draw, (x0 + pad_x, y0 + pad_y - int(size * 0.08)), text, font, text_fill)
    return x0
