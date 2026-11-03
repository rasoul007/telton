"""Small helpers shared by every stage."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_digits(text: str) -> str:
    """Convert ASCII digits to Persian digits."""
    return str(text).translate(_FA_DIGITS)


def seconds_to_srt(value: float) -> str:
    """00:00:01,250"""
    ms = int(round(value * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def seconds_to_clock(value: float) -> str:
    """01:05 — used inside scripts and review pages."""
    total = int(round(value))
    return f"{total // 60:02d}:{total % 60:02d}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_title(title: str) -> str:
    """Loose key used to de-duplicate headlines coming from several feeds."""
    text = re.sub(r"\s*[|\-–—]\s*[^|\-–—]{2,40}$", "", title)  # drop trailing " | Source"
    text = re.sub(r"[^\w\u0600-\u06FF]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def estimate_duration(text: str, words_per_second: float) -> float:
    """Rough narration length; refined later by measuring the real TTS audio."""
    return max(1.2, word_count(text) / max(0.5, words_per_second))


def run(cmd: Iterable[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(list(cmd), capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(
            "command failed: %s\n%s" % (" ".join(map(str, cmd)), (result.stderr or "")[-2000:])
        )
    return result


def ffmpeg_exe() -> str:
    """ffmpeg shipped with imageio-ffmpeg (no system package needed)."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover - optional dependency
        return "ffmpeg"


def probe_duration(path: Path) -> float:
    """Duration in seconds using ffmpeg's own report (no ffprobe needed)."""
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
    )
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr or "")
    if not match:
        raise RuntimeError(f"could not read duration of {path}")
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)
