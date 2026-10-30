"""Review subtitles for the Persian dialogue.

The delivered film has no subtitles (per the brief). This SRT exists so
editors and the voice-over artist can check timing, and so the review cut can
be screened with burned-in Persian captions.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

from . import screenplay

OUT = screenplay.ROOT / "out" / "kairo_ep01_review.srt"


def _stamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vo_duration(scene_id: str) -> float:
    path = screenplay.ROOT / "audio" / "vo" / f"{scene_id}.wav"
    if not path.exists():
        return 0.0
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def write_srt() -> Path:
    episode = screenplay.load()
    report = screenplay.ROOT / "audio" / "vo" / "vo_report.json"
    lead = json.loads(report.read_text(encoding="utf-8"))["lead_in_s"] \
        if report.exists() else 0.55

    lines = []
    for i, scene in enumerate(episode["scenes"], start=1):
        start = scene["start_s"] + lead
        dur = _vo_duration(scene["id"]) or (scene["duration_s"] - 2 * lead)
        end = min(scene["start_s"] + scene["duration_s"] - 0.1, start + dur + 0.45)
        lines += [str(i),
                  f"{_stamp(start)} --> {_stamp(end)}",
                  scene["dialogue_fa"],
                  ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    return OUT
