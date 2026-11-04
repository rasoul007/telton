"""Thumbnails that actually stop the scroll.

A thumbnail is one promise + one face. We build it from the best available frame
(a downloaded clip/photo, otherwise a generated plate) and stamp a 3-5 word hook
on it with a yellow highlight so it reads on a phone at a glance.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from .config import REPO_ROOT, Project
from .graphics import Renderer, draw_text, text_width
from .models import Rundown
from .util import ensure_dir, ffmpeg_exe

DEFAULT_HOOKS = [
    "۱۴ سال! آنفیلد فتح شد",
    "جوان‌ترین قهرمان تاریخ",
    "قهرمانی جهان برای ایران",
]


def _frame_from_media(path: Path, size: tuple[int, int], at: float = 0.35) -> Image.Image | None:
    """Grab a punchy frame from a clip (or load a still) and cover-fit it."""
    w, h = size
    if not path.exists():
        return None
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
        try:
            image = Image.open(path).convert("RGB")
        except Exception:
            return None
    else:
        tmp = Path("/tmp") / f"thumb-{path.stem}.png"
        try:
            subprocess.run(
                [ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", str(at), "-i", str(path),
                 "-frames:v", "1", str(tmp)],
                check=True,
            )
            image = Image.open(tmp).convert("RGB")
        except Exception:
            return None
    scale = max(w / image.width, h / image.height)
    image = image.resize((max(w, int(image.width * scale)), max(h, int(image.height * scale))))
    left = (image.width - w) // 2
    top = (image.height - h) // 3
    return image.crop((left, top, left + w, top + h))


def _scrim(image: Image.Image) -> Image.Image:
    """Darken the right side (where the Persian hook sits) + the bottom."""
    w, h = image.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for y in range(h):
        t = y / max(1, h - 1)
        alpha = int(20 + 200 * max(0.0, (t - 0.25)) ** 1.5)
        draw.line([(0, y), (w, y)], fill=(4, 6, 10, min(240, alpha)))
    draw.rectangle([int(w * 0.42), 0, w, h], fill=(4, 6, 10, 120))
    return Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")


def _wrap_hook(hook: str, renderer: Renderer, size: int, max_width: int) -> list[str]:
    """Break the hook into at most 2 short lines (thumbnails must read instantly)."""
    words = hook.split()
    lines: list[list[str]] = [[]]
    for word in words:
        trial = " ".join(lines[-1] + [word])
        if lines[-1] and len(renderer.wrap(trial, "black", size, max_width)) > 1:
            lines.append([word])
        else:
            lines[-1].append(word)
    return [" ".join(line) for line in lines if line]


def _draw_hook(canvas: Image.Image, hook: str, renderer: Renderer) -> Image.Image:
    w, h = canvas.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    margin = int(w * 0.05)
    unit = min(w, h)
    size = int(unit * 0.105)
    max_width = int(w * 0.50)

    lines = _wrap_hook(hook, renderer, size, max_width)[:2]
    line_height = int(size * 1.2)
    y = int(h * 0.68) - (line_height * len(lines)) // 2
    for line in lines:
        width = text_width(draw, line, renderer.font("black", size))
        x = w - margin - width
        draw.rounded_rectangle(
            [x - int(size * 0.22), y + int(size * 0.64),
             w - margin + int(size * 0.22), y + int(size * 1.14)],
            radius=int(size * 0.1), fill=(255, 212, 0, 232),
        )
        draw_text(draw, (x, y), line, renderer.font("black", size),
                  (255, 255, 255, 255), stroke=max(4, int(size * 0.07)), stroke_fill=(6, 8, 12))
        y += line_height
    return Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")


def _draw_brand(canvas: Image.Image, project: Project, renderer: Renderer) -> Image.Image:
    w, h = canvas.size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    brand = str(project.style.get("branding.name", "tooop news"))
    handle = str(project.style.get("branding.handle", ""))
    m = int(w * 0.045)
    size = int(min(w, h) * 0.045)
    box_w = int(size * 6.6)
    draw.rounded_rectangle(
        [w - m - box_w, m, w - m, m + int(size * 1.9)],
        radius=int(size * 0.95), fill=(225, 6, 0, 235),
    )
    draw_text(draw, (w - m - int(size * 0.6) - text_width(draw, brand, renderer.font("black", size)), m + int(size * 0.35)),
              brand, renderer.font("black", size), (255, 255, 255, 255))
    if handle:
        draw_text(draw, (w - m - int(size * 4.4), m + int(size * 2.1)), handle,
                  renderer.font("regular", int(size * 0.7)), (255, 255, 255, 190))
    return Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")


def build_thumbnails(project: Project, rundown: Rundown, hooks: list[str] | None = None) -> list[Path]:
    """Create up to 3 thumbnail variants so YouTube A/B testing has something to test."""
    project.ensure()
    ensure_dir(project.out)
    renderer = Renderer(project.style)
    size = (project.style.width, project.style.height)

    meta_hooks = project.meta.get("thumb_hooks") or []
    if isinstance(meta_hooks, str):
        meta_hooks = [meta_hooks]
    candidates = list(hooks or []) or list(meta_hooks) or DEFAULT_HOOKS

    backgrounds: list[Image.Image] = []
    for segment in rundown.segments:
        if not segment.story or not segment.story.broll:
            continue
        path = Path(segment.story.broll)
        if not path.is_absolute():
            path = REPO_ROOT / "broll" / path
        frame = _frame_from_media(path, size)
        if frame is not None:
            backgrounds.append(_scrim(frame))
        if len(backgrounds) >= 3:
            break
    if not backgrounds:
        backgrounds = [_scrim(renderer.plate(3).resize(size))]

    paths: list[Path] = []
    for index, hook in enumerate(candidates[:3], start=1):
        canvas = _draw_hook(backgrounds[(index - 1) % len(backgrounds)].copy(), hook, renderer)
        canvas = _draw_brand(canvas, project, renderer)
        target = project.out / f"thumbnail-{index}.jpg"
        canvas.save(target, quality=92)
        if index == 1:
            canvas.save(project.out / "thumbnail.jpg", quality=92)
        paths.append(target)
    return paths
