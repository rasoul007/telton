"""Stage 4 — paint frames with Pillow and encode with ffmpeg."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from .config import Project
from .graphics import Renderer, chip, draw_text, shape, text_width
from .models import Cue, Rundown, Segment
from .rundown import SECTION_LABELS
from .util import ensure_dir, ffmpeg_exe


class Layout:
    """All pixel positions are derived from the canvas so 9:16 and 16:9 both work."""

    def __init__(self, width: int, height: int):
        self.w = width
        self.h = height
        self.u = min(width, height)          # typographic unit
        self.margin = round(self.u * 0.0667)
        self.brand_y = round(height * 0.05)
        self.pill_y = round(height * 0.078)
        self.pill_h = round(self.u * 0.076)
        self.headline_y = self.pill_y + self.pill_h + round(height * 0.12)
        self.ticker_h = round(self.u * 0.0889)
        self.ticker_y = height - self.ticker_h
        self.sub_h = round(self.u * 0.145)
        self.sub_y = self.ticker_y - self.sub_h - round(height * 0.014)

    def size(self, factor: float, minimum: int = 18) -> int:
        return max(minimum, round(self.u * factor))


def bell_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, fill) -> None:
    """A small bell, drawn with polygons so we never depend on an emoji font."""
    body = size * 0.5
    draw.polygon(
        [
            (cx - body, cy + size * 0.30),
            (cx - body * 0.86, cy - size * 0.12),
            (cx - body * 0.7, cy - size * 0.42),
            (cx, cy - size * 0.58),
            (cx + body * 0.7, cy - size * 0.42),
            (cx + body * 0.86, cy - size * 0.12),
            (cx + body, cy + size * 0.30),
        ],
        fill=fill,
    )
    draw.rectangle([cx - body * 1.12, cy + size * 0.30, cx + body * 1.12, cy + size * 0.44], fill=fill)
    draw.ellipse([cx - size * 0.13, cy + size * 0.50, cx + size * 0.13, cy + size * 0.74], fill=fill)


def plus_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, fill) -> None:
    """A 'follow' plus sign."""
    draw.rounded_rectangle(
        [cx - size * 0.60, cy - size * 0.14, cx + size * 0.60, cy + size * 0.14],
        radius=int(size * 0.07), fill=fill,
    )
    draw.rounded_rectangle(
        [cx - size * 0.14, cy - size * 0.60, cx + size * 0.14, cy + size * 0.60],
        radius=int(size * 0.07), fill=fill,
    )


def instagram_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, fill) -> None:
    """Instagram-style rounded square + lens + flash dot (drawn, not an emoji)."""
    half = size * 0.62
    stroke = max(2, int(size * 0.13))
    draw.rounded_rectangle(
        [cx - half, cy - half, cx + half, cy + half],
        radius=int(size * 0.34), outline=fill, width=stroke,
    )
    lens = size * 0.34
    draw.ellipse(
        [cx - lens, cy - lens, cx + lens, cy + lens], outline=fill, width=stroke
    )
    dot = size * 0.10
    draw.ellipse(
        [cx + half - stroke - dot * 2, cy - half + stroke, cx + half - stroke, cy - half + stroke + dot * 2],
        fill=fill,
    )


class Broll:
    """Decodes a licensed clip (or any video file) to raw RGB frames of the canvas size."""

    def __init__(self, path: Path, width: int, height: int, fps: int):
        self.path = path
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_bytes = width * height * 3
        self._proc: subprocess.Popen | None = None
        self._index = 0

    def _open(self) -> None:
        vf = (
            f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
            f"crop={self.width}:{self.height},fps={self.fps}"
        )
        self._proc = subprocess.Popen(
            [
                ffmpeg_exe(), "-v", "error", "-i", str(self.path), "-an",
                "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
            ],
            stdout=subprocess.PIPE,
        )
        self._index = 0

    def read(self, t: float) -> Image.Image | None:
        if self._proc is None:
            self._open()
        assert self._proc and self._proc.stdout
        data = self._proc.stdout.read(self.frame_bytes)
        if len(data) < self.frame_bytes:  # clip finished -> loop it
            self.close()
            self._open()
            assert self._proc and self._proc.stdout
            data = self._proc.stdout.read(self.frame_bytes)
            if len(data) < self.frame_bytes:
                return None
        self._index += 1
        return Image.frombytes("RGB", (self.width, self.height), data)

    def close(self) -> None:
        if self._proc:
            try:
                assert self._proc.stdout
                self._proc.stdout.close()
            finally:
                self._proc.kill()
                self._proc = None


class FramePainter:
    def __init__(
        self,
        project: Project,
        rundown: Rundown,
        broll_dir: Path | None = None,
        width: int | None = None,
        height: int | None = None,
    ):
        self.project = project
        self.rundown = rundown
        self.style = project.style
        self.r = Renderer(self.style, width, height)
        self.w = self.r.width
        self.h = self.r.height
        self.L = Layout(self.w, self.h)
        self.broll_dir = broll_dir or (project.root.parent.parent / "broll")
        self._bases: dict[str, Image.Image] = {}
        self._overlays: dict[str, Image.Image] = {}
        self._subtitles: dict[str, Image.Image] = {}
        self._brolls: dict[str, Broll] = {}
        self._stills: dict[str, Image.Image] = {}
        self._ticker: Image.Image = self._ticker_strip()
        self._scrim = self._scrim_layer()
        self._cta: Image.Image = self._cta_layer()

    # --------------------------------------------------------------- cta
    @property
    def horizontal(self) -> bool:
        return self.w >= self.h

    def _cta_label(self) -> str:
        return "SUBSCRIBE" if self.horizontal else "FOLLOW"

    def _cta_layer(self, scale: float = 1.0) -> Image.Image:
        """A pill with a bell (YouTube) or plus (Instagram) + one word."""
        unit = self.L.size(0.032 * scale)
        font = self.r.font("black", unit)
        probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
        label = self._cta_label()
        text_w = int(text_width(probe, label, font))
        pad = int(unit * 0.85)
        height = int(unit * 2.1)
        width = text_w + int(unit * 2.5) + 2 * pad
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=height // 2, fill=(225, 6, 0, 242))
        icon_cx = width - pad - int(unit * 0.55)
        if self.horizontal:
            bell_icon(draw, icon_cx, height // 2, int(unit * 0.85), (255, 255, 255, 255))
        else:
            instagram_icon(draw, icon_cx, height // 2, int(unit * 0.60), (255, 255, 255, 255))
        draw_text(draw, (pad, height // 2 - int(unit * 0.66)), label, font, (255, 255, 255, 255))
        return layer

    # ------------------------------------------------------------- helpers
    def _scrim_layer(self) -> Image.Image:
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for y in range(self.h):
            t = y / max(1, self.h - 1)
            alpha = int(40 + 190 * max(0.0, (t - 0.35)) ** 1.4)
            draw.line([(0, y), (self.w, y)], fill=(4, 6, 10, min(235, alpha)))
        return layer

    def _ticker_strip(self) -> Image.Image:
        height = self.L.ticker_h
        labels = [s.story.headline for s in self.rundown.segments if s.story]
        text = "  •  ".join(labels) if labels else self.rundown.title
        font = self.r.font("bold", self.L.size(0.041))
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        width = int(text_width(probe, text, font)) + 80
        strip = Image.new("RGB", (max(width, self.w), height), self.r.panel)
        draw = ImageDraw.Draw(strip)
        draw_text(draw, (40, height // 2 - font.size * 0.7), text, font, self.r.text_color)
        return strip

    def _plate_tall(self, seed: int) -> Image.Image:
        tall = int(self.h * 1.14)
        plate = self.r.plate(seed)
        return plate.resize((self.w, tall))

    def _broll_for(self, segment: Segment) -> Broll | None:
        story = segment.story
        if not story or not story.broll:
            return None
        path = Path(story.broll)
        if not path.is_absolute():
            path = self.broll_dir / path
        if not path.exists() or path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            return None
        key = str(path)
        if key not in self._brolls:
            self._brolls[key] = Broll(path, self.w, self.h, self.style.fps)
        return self._brolls[key]

    def _still(self, segment: Segment) -> Image.Image | None:
        """A downloaded photo used as a slow ken-burns background."""
        story = segment.story
        if not story or not story.broll:
            return None
        path = Path(story.broll)
        if not path.is_absolute():
            path = self.broll_dir / path
        if not path.exists() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            return None
        key = str(path)
        if key not in self._stills:
            try:
                image = Image.open(path).convert("RGB")
            except Exception:
                return None
            scale = max(self.w * 1.12 / image.width, self.h * 1.12 / image.height)
            self._stills[key] = image.resize(
                (max(self.w, int(image.width * scale)), max(self.h, int(image.height * scale)))
            )
        return self._stills[key]

    def close(self) -> None:
        for broll in self._brolls.values():
            broll.close()

    # -------------------------------------------------------------- overlays
    def overlay(self, segment: Segment) -> Image.Image:
        if segment.id in self._overlays:
            return self._overlays[segment.id]
        L = self.L
        m = L.margin
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        brand = str(self.style.get("branding.name", "tooop news"))
        handle = str(self.style.get("branding.handle", ""))

        draw_text(draw, (m, L.brand_y), brand, self.r.font("black", L.size(0.037)), (255, 255, 255, 155))
        if handle:
            draw_text(
                draw,
                (m, L.brand_y + L.size(0.048)),
                handle,
                self.r.font("regular", L.size(0.028)),
                (255, 255, 255, 115),
            )

        if segment.kind == "intro":
            badge_text = "خبرهای مهم ورزش"
            badge_font = self.r.font("black", L.size(0.046))
            badge_w = text_width(draw, badge_text, badge_font)
            pad = round(L.u * 0.043)
            top = round(self.h * 0.29)
            draw.rounded_rectangle(
                [self.w - m - badge_w - 2 * pad, top, self.w - m, top + round(badge_font.size * 1.9)],
                radius=round(badge_font.size * 0.95),
                fill=(255, 212, 0, 240),
            )
            draw_text(
                draw, (self.w - m - pad - badge_w, top + round(badge_font.size * 0.4)),
                badge_text, badge_font, (10, 12, 16, 255),
            )
            y = self.r.text_block(
                draw, segment.title, (self.w - m, top + round(self.h * 0.14)),
                weight="black", size=L.size(0.078), max_width=self.w - 2 * m, line_gap=14,
                fill=(255, 255, 255, 255),
            )
            self.r.text_block(
                draw, "ایران · اروپا · جهان ورزش · حواشی", (self.w - m, y + round(self.h * 0.026)),
                weight="bold", size=L.size(0.041), max_width=self.w - 2 * m, fill=(255, 212, 0, 255),
            )
        elif segment.kind == "title":
            band_top, band_bottom = round(self.h * 0.40), round(self.h * 0.52)
            draw.rounded_rectangle([0, band_top, self.w, band_bottom], fill=(255, 212, 0, 242))
            self.r.text_block(
                draw, segment.title, (self.w // 2, (band_top + band_bottom) // 2),
                weight="black", size=L.size(0.089), max_width=self.w - 2 * m,
                align="center", anchor_y="middle", fill=(10, 12, 16, 255),
            )
        elif segment.kind == "story" and segment.story:
            story = segment.story
            label = SECTION_LABELS.get(story.bucket, "")
            if label:
                pill_font = self.r.font("bold", L.size(0.035))
                cw = text_width(draw, label, pill_font)
                draw.rounded_rectangle(
                    [self.w - m - cw - 2 * L.size(0.026), L.pill_y,
                     self.w - m, L.pill_y + L.pill_h],
                    radius=L.pill_h // 2, fill=(225, 6, 0, 238),
                )
                draw_text(
                    draw, (self.w - m - L.size(0.026) - cw, L.pill_y + L.size(0.018)),
                    label, pill_font, (255, 255, 255, 255),
                )

            size = L.size(0.054)
            for factor in (0.085, 0.076, 0.068, 0.061, 0.054):
                size = L.size(factor)
                if len(self.r.wrap(story.headline, "black", size, self.w - 2 * m)) <= 3:
                    break
            y = self.r.text_block(
                draw, story.headline, (self.w - m, L.headline_y), weight="black", size=size,
                max_width=self.w - 2 * m, line_gap=12, fill=(255, 255, 255, 255),
            )
            draw.rounded_rectangle(
                [self.w - L.size(0.28), y + L.size(0.017), self.w - m, y + L.size(0.026)],
                radius=5, fill=(255, 212, 0, 255),
            )
            y += L.size(0.069)
            for fact in story.facts[:3]:
                chip(draw, self.r, fact, self.w - m, y, size=L.size(0.037))
                y += L.size(0.085)
            if story.source_line:
                source = "منبع: " + story.source_line
                source_w = text_width(draw, source, self.r.font("regular", L.size(0.028)))
                draw_text(
                    draw, (self.w - m - source_w, y + L.size(0.007)), source,
                    self.r.font("regular", L.size(0.028)), (154, 164, 178, 235),
                )
        else:  # outro
            self.r.text_block(
                draw, segment.title, (self.w // 2, round(self.h * 0.34)), weight="black",
                size=L.size(0.102), max_width=self.w - 2 * m, align="center", fill=(255, 255, 255, 255),
            )
            # big call-to-action: bell for YouTube, plus for Instagram
            cta = self._cta_layer(scale=2.0)
            layer.alpha_composite(cta, ((self.w - cta.width) // 2, int(self.h * 0.50)))
            ask = (
                "سابسکرایب کن و زنگوله را بزن"
                if self.horizontal
                else "فالو کن تا خبر بعدی را از دست ندهی"
            )
            self.r.text_block(
                draw, ask, (self.w // 2, int(self.h * 0.50) + cta.height + int(self.h * 0.03)),
                weight="bold", size=L.size(0.045), max_width=self.w - 2 * m, align="center",
                fill=(255, 212, 0, 255),
            )
        self._overlays[segment.id] = layer
        return layer

    # --------------------------------------------------------------- frames
    def subtitle_strip(self, cue: Cue) -> Image.Image:
        if cue.index in self._subtitles:
            return self._subtitles[cue.index]
        L = self.L
        layer = Image.new("RGBA", (self.w, L.sub_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        max_width = self.w - 2 * L.margin - 40
        size = L.size(0.05)
        for factor in (0.05, 0.045, 0.041, 0.037):
            size = L.size(factor)
            if len(self.r.wrap(cue.text, "bold", size, max_width)) <= 2:
                break
        self.r.text_block(
            draw, cue.text, (self.w // 2, round(L.sub_h * 0.06)), weight="bold", size=size,
            max_width=max_width, align="center", line_gap=8,
            fill=(255, 255, 255, 255), stroke=max(3, L.size(0.006)), stroke_fill=(4, 6, 10),
        )
        self._subtitles[cue.index] = layer
        return layer

    def segment_at(self, t: float) -> Segment:
        for segment in self.rundown.segments:
            if segment.start <= t < segment.end:
                return segment
        return self.rundown.segments[-1]

    def cue_at(self, t: float) -> Cue | None:
        for cue in self.rundown.cues:
            if cue.start <= t <= cue.end and cue.kind == "narration":
                return cue
        return None

    def frame(self, t: float) -> Image.Image:
        segment = self.segment_at(t)
        progress = (t - segment.start) / max(0.001, segment.duration)
        image: Image.Image | None = None
        broll = self._broll_for(segment)
        if broll is not None:
            image = broll.read(t)
            if image is not None:
                image = image.convert("RGB")
                image.paste(self._scrim, (0, 0), self._scrim)
        if image is None:
            still = self._still(segment)
            if still is not None:
                # slow ken-burns pan across the photo
                max_x = max(1, still.width - self.w)
                max_y = max(1, still.height - self.h)
                x = int(max_x * min(1.0, max(0.0, progress)))
                y = int(max_y * 0.5)
                image = still.crop((x, y, x + self.w, y + self.h))
                image.paste(self._scrim, (0, 0), self._scrim)
        if image is None:
            plate = self._bases.get(segment.id)
            if plate is None:
                plate = self._plate_tall(hash(segment.id) % 16)
                self._bases[segment.id] = plate
            offset = int((plate.height - self.h) * min(1.0, max(0.0, progress)))
            image = plate.crop((0, offset, self.w, offset + self.h))

        image.paste(self.overlay(segment), (0, 0), self.overlay(segment))

        cue = self.cue_at(t)
        if cue is not None:
            strip = self.subtitle_strip(cue)
            image.paste(strip, (0, self.L.sub_y), strip)

        # mid-roll subscribe/follow reminder
        start, end = self.rundown.end * 0.52, self.rundown.end * 0.60
        if start <= t <= end and self.rundown.end > 60:
            fade = min(1.0, (t - start) / 0.6, (end - t) / 0.6)
            cta = self._cta
            if fade < 0.99:
                cta = cta.copy()
                cta.putalpha(cta.getchannel("A").point(lambda a: int(a * max(0.0, fade))))
            x = self.L.margin
            y = self.L.pill_y + self.L.pill_h + int(self.h * 0.01)
            image.paste(cta, (x, y), cta)

        if bool(self.style.get("ticker.enabled", True)):
            speed = float(self.style.get("ticker.speed_px_per_second", 170))
            width = self._ticker.width
            # the news bar moves LEFT -> RIGHT (requested by the channel)
            x0 = -width + (int(t * speed) % width)
            band = Image.new("RGB", (self.w, self._ticker.height), self.r.panel)
            band.paste(self._ticker, (x0, 0))
            band.paste(self._ticker, (x0 + width, 0))
            draw = ImageDraw.Draw(band)
            draw.rectangle([0, 0, self.w, max(4, self.L.size(0.006))], fill=self.r.accent)
            image.paste(band, (0, self.L.ticker_y))

        draw = ImageDraw.Draw(image)
        bar_width = int(self.w * min(1.0, max(0.0, t / max(0.1, self.rundown.end))))
        draw.rectangle([0, 0, self.w, 8], fill=(28, 33, 44))
        draw.rectangle([0, 0, bar_width, 8], fill=self.r.accent)
        return image


def render_video(
    project: Project,
    rundown: Rundown,
    audio: Path | None,
    out_path: Path | None = None,
    width: int | None = None,
    height: int | None = None,
    fps: int | None = None,
    max_seconds: float | None = None,
    progress: bool = True,
) -> Path:
    """Encode the whole rundown to MP4 (H.264 + AAC, 9:16 by default)."""
    project.ensure()
    out_path = out_path or project.video_path
    ensure_dir(out_path.parent)
    fps = fps or project.style.fps
    painter = FramePainter(project, rundown, width=width, height=height)
    total = min(max_seconds, rundown.end) if max_seconds else rundown.end
    frames = int(total * fps)
    crf = str(project.style.get("video.crf", 20))
    preset = str(project.style.get("video.preset", "veryfast"))

    cmd = [
        ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{painter.w}x{painter.h}", "-r", str(fps), "-i", "-",
    ]
    if audio and Path(audio).exists():
        cmd += ["-i", str(audio)]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
    cmd += [
        "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
        "-movflags", "+faststart", "-shortest", str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin
    try:
        for i in range(frames):
            if progress and i % (fps * 10) == 0:
                pct = 100 * i / max(1, frames)
                print(f"  rendering {pct:5.1f}%  ({i // fps}s / {total:.0f}s)", file=sys.stderr, flush=True)
            proc.stdin.write(painter.frame(i / fps).tobytes())
        proc.stdin.close()
    finally:
        painter.close()
        stderr = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg encode failed:\n{stderr[-3000:]}")
    return out_path


def export_thumbnail(project: Project, rundown: Rundown, at: float = 6.0, path: Path | None = None) -> Path:
    """Grab a frame for the thumbnail (YouTube/IG)."""
    painter = FramePainter(project, rundown)
    image = painter.frame(min(at, max(0.5, rundown.end - 1)))
    path = path or (project.out / "thumbnail.jpg")
    ensure_dir(path.parent)
    image.save(path, quality=90)
    painter.close()
    return path
