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

MARGIN = 72
SUBTITLE_Y = 1500
TICKER_Y = 1734


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
                ffmpeg_exe(), "-v", "error", "-re", "-i", str(self.path), "-an",
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
        self.broll_dir = broll_dir or (project.root.parent.parent / "broll")
        self._bases: dict[str, Image.Image] = {}
        self._overlays: dict[str, Image.Image] = {}
        self._subtitles: dict[str, Image.Image] = {}
        self._brolls: dict[str, Broll] = {}
        self._ticker: Image.Image = self._ticker_strip()
        self._scrim = self._scrim_layer()

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
        height = 96
        labels = [s.story.headline for s in self.rundown.segments if s.story]
        text = "  •  ".join(labels) if labels else self.rundown.title
        font = self.r.font("bold", 44)
        probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        width = int(text_width(probe, text, font)) + 80
        strip = Image.new("RGB", (max(width, self.w), height), self.r.panel)
        draw = ImageDraw.Draw(strip)
        draw_text(draw, (40, height // 2 - 30), text, font, self.r.text_color)
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
        if not path.exists():
            return None
        key = str(path)
        if key not in self._brolls:
            self._brolls[key] = Broll(path, self.w, self.h, self.style.fps)
        return self._brolls[key]

    def close(self) -> None:
        for broll in self._brolls.values():
            broll.close()

    # -------------------------------------------------------------- overlays
    def overlay(self, segment: Segment) -> Image.Image:
        if segment.id in self._overlays:
            return self._overlays[segment.id]
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        brand = str(self.style.get("branding.name", "تلتون اسپرت"))
        handle = str(self.style.get("branding.handle", ""))
        accent_bar = [self.w - MARGIN - 8, 150, self.w - MARGIN, 300]

        # brand watermark (top-left, mirrored for RTL audience)
        draw_text(draw, (MARGIN, 96), brand, self.r.font("black", 40), (255, 255, 255, 150))
        if handle:
            draw_text(draw, (MARGIN, 146), handle, self.r.font("regular", 30), (255, 255, 255, 110))

        if segment.kind == "intro":
            badge = "خبرهای مهم ورزش"
            badge_font = self.r.font("black", 50)
            badge_w = text_width(draw, badge, badge_font)
            pad = 46
            top = 560
            draw.rounded_rectangle(
                [self.w - MARGIN - badge_w - 2 * pad, top, self.w - MARGIN, top + 96],
                radius=48, fill=(255, 212, 0, 240),
            )
            draw_text(
                draw,
                (self.w - MARGIN - pad - badge_w, top + 20),
                badge,
                badge_font,
                (10, 12, 16, 255),
            )
            y = self.r.text_block(
                draw, segment.title, (self.w - MARGIN, top + 150),
                weight="black", size=84, max_width=self.w - 2 * MARGIN, line_gap=14,
                fill=(255, 255, 255, 255),
            )
            y += 26
            self.r.text_block(
                draw, "ایران · اروپا · جهان ورزش · حواشی", (self.w - MARGIN, y),
                weight="bold", size=44, max_width=self.w - 2 * MARGIN, fill=(255, 212, 0, 255),
            )
        elif segment.kind == "title":
            label_size = 96
            draw.rounded_rectangle([0, 760, self.w, 1000], fill=(255, 212, 0, 240))
            self.r.text_block(
                draw, segment.title, (self.w // 2, 880), weight="black", size=label_size,
                max_width=self.w - 2 * MARGIN, align="center", anchor_y="middle", fill=(10, 12, 16, 255),
            )
        elif segment.kind == "story" and segment.story:
            story = segment.story
            label = SECTION_LABELS.get(story.bucket, "")
            if label:
                cw = text_width(draw, label, self.r.font("bold", 38))
                draw.rounded_rectangle(
                    [self.w - MARGIN - cw - 56, 150, self.w - MARGIN, 232], radius=41,
                    fill=(225, 6, 0, 235),
                )
                draw_text(
                    draw, (self.w - MARGIN - cw - 28, 172), label,
                    self.r.font("bold", 38), (255, 255, 255, 255),
                )
            else:
                accent_bar = accent_bar

            y = 470
            for size in (92, 82, 74, 66, 58):
                lines = self.r.wrap(story.headline, "black", size, self.w - 2 * MARGIN)
                if len(lines) <= 3:
                    break
            y = self.r.text_block(
                draw, story.headline, (self.w - MARGIN, y), weight="black", size=size,
                max_width=self.w - 2 * MARGIN, line_gap=12, fill=(255, 255, 255, 255),
            )
            draw.rounded_rectangle([self.w - 300, y + 18, self.w - MARGIN, y + 28], radius=5, fill=(255, 212, 0, 255))
            y += 74
            for fact in story.facts[:3]:
                chip(draw, self.r, fact, self.w - MARGIN, y, size=40)
                y += 92
            if story.source_line:
                source = "منبع: " + story.source_line
                source_w = text_width(draw, source, self.r.font("regular", 30))
                draw_text(
                    draw, (self.w - MARGIN - source_w, y + 8), source,
                    self.r.font("regular", 30), (154, 164, 178, 235),
                )
        else:  # outro
            self.r.text_block(
                draw, segment.title, (self.w // 2, 780), weight="black", size=110,
                max_width=self.w - 2 * MARGIN, align="center", fill=(255, 255, 255, 255),
            )
            self.r.text_block(
                draw, "نظرت را کامنت کن · فالو کن", (self.w // 2, 960), weight="bold", size=52,
                max_width=self.w - 2 * MARGIN, align="center", fill=(255, 212, 0, 255),
            )
        self._overlays[segment.id] = layer
        return layer

    # --------------------------------------------------------------- frames
    def subtitle_strip(self, cue: Cue) -> Image.Image:
        if cue.index in self._subtitles:
            return self._subtitles[cue.index]
        layer = Image.new("RGBA", (self.w, 300), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        size = 54
        for candidate in (54, 48, 44, 40):
            size = candidate
            if len(self.r.wrap(cue.text, "bold", size, self.w - 2 * MARGIN - 40)) <= 2:
                break
        self.r.text_block(
            draw, cue.text, (self.w // 2, 20), weight="bold", size=size,
            max_width=self.w - 2 * MARGIN - 40, align="center", line_gap=8,
            fill=(255, 255, 255, 255), stroke=6, stroke_fill=(4, 6, 10),
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
            image.paste(strip, (0, SUBTITLE_Y), strip)

        if bool(self.style.get("ticker.enabled", True)):
            speed = float(self.style.get("ticker.speed_px_per_second", 170))
            offset = int(t * speed) % self._ticker.width
            band = Image.new("RGB", (self.w, self._ticker.height), self.r.panel)
            band.paste(self._ticker.crop((offset, 0, self._ticker.width, self._ticker.height)), (0, 0))
            if offset > 0:
                band.paste(self._ticker.crop((0, 0, offset, self._ticker.height)), (self._ticker.width - offset, 0))
            draw = ImageDraw.Draw(band)
            draw.rectangle([0, 0, self.w, 6], fill=self.r.accent)
            image.paste(band, (0, TICKER_Y))

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


def export_thumbnail(project: Project, rundown: Rundown, at: float = 6.0) -> Path:
    """Grab a frame for the thumbnail (YouTube/IG)."""
    painter = FramePainter(project, rundown)
    image = painter.frame(min(at, max(0.5, rundown.end - 1)))
    path = project.out / "thumbnail.jpg"
    ensure_dir(path.parent)
    image.save(path, quality=90)
    painter.close()
    return path
