"""Shared paths and binaries for the KAIRO pipeline."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ffmpeg comes from the locally installed ffmpeg-static npm package so the
# pipeline is reproducible without a system ffmpeg.
_FFMPEG_CANDIDATES = [
    ROOT / "node_modules" / "ffmpeg-static" / "ffmpeg",
]


def _find_ffmpeg() -> Path:
    for cand in _FFMPEG_CANDIDATES:
        if cand.exists():
            return cand
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)
    raise RuntimeError(
        "ffmpeg not found. Run `npm install` in the repo root "
        "(ffmpeg-static provides the binary).")


FFMPEG = Path(os.environ.get("KAIRO_FFMPEG", _find_ffmpeg()))

BUILD = ROOT / "build"
STILLS = BUILD / "stills"
CLIPS = BUILD / "clips"
OUT = ROOT / "out"

FPS = 24
WIDTH = 1920
HEIGHT = 1080
SAMPLE_RATE = 48000

# shared palette, kept in one place so every frame matches
INK = (26, 22, 20)
PAPER = (232, 222, 206)

FONT_DIR = Path("/usr/share/fonts/truetype/noto")
FONT_PERSIAN = FONT_DIR / "NotoNaskhArabic-Regular.ttf"
FONT_PERSIAN_BOLD = FONT_DIR / "NotoNaskhArabic-Bold.ttf"
FONT_LATIN = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def probe(path: Path) -> dict:
    """Return {duration_s, width, height, fps, codec} for a media file."""
    import re
    import subprocess

    out = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True).stderr
    info = {"duration_s": None, "width": None, "height": None, "fps": None}
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    if m:
        h, mi, s = m.groups()
        info["duration_s"] = int(h) * 3600 + int(mi) * 60 + float(s)
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", out)
    if m:
        info["width"], info["height"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?) fps", out)
    if m:
        info["fps"] = float(m.group(1))
    return info

