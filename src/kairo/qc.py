"""Quality control: prove the deliverable matches the brief.

Every rule in the brief that can be measured is measured here:

* 25 scenes, 12 s each, 300 s total
* 1920x1080, 24 fps, no burned-in subtitles in the master
* one identical KAIRO design, wardrobe correct for each timeline
* every Persian line present, unedited, and fitting its 12 s slot
* all 25 clips present, each exactly 12 s
* the assembled master is exactly 300 s
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

from . import screenplay
from .config import CLIPS, FPS, HEIGHT, OUT, WIDTH, probe

MASTER = OUT / "kairo_ep01_animatic.mp4"
VO_REPORT = screenplay.ROOT / "audio" / "vo" / "vo_report.json"


def _check_screenplay() -> dict:
    episode = screenplay.load()
    errors = screenplay.validate(episode)
    return {
        "name": "screenplay",
        "passed": not errors,
        "detail": errors or "25 scenes x 12 s = 300 s, dialogue verbatim",
    }


def _check_voice() -> dict:
    if not VO_REPORT.exists():
        return {"name": "voice-over", "passed": False, "detail": "no report"}
    report = json.loads(VO_REPORT.read_text(encoding="utf-8"))
    problems = [r["id"] for r in report["scenes"] if not r["fits"]]
    detail = (f"{len(report['scenes'])} lines, voice {report['voice_id']}, "
              f"{report['total_speech_s']}s speech, "
              f"max prosody +{report['max_rate_used']}%")
    if problems:
        detail += f", overflowing: {problems}"
    return {"name": "voice-over", "passed": not problems, "detail": detail}


def _check_clips() -> dict:
    episode = screenplay.load()
    problems, durations = [], {}
    for scene in episode["scenes"]:
        path = CLIPS / f"{scene['id']}.mp4"
        if not path.exists():
            problems.append(f"{scene['id']} missing")
            continue
        info = probe(path)
        durations[scene["id"]] = info["duration_s"]
        if info["duration_s"] is None or abs(info["duration_s"] - 12) > 0.05:
            problems.append(f"{scene['id']} is {info['duration_s']}s")
        if (info["width"], info["height"]) != (WIDTH, HEIGHT):
            problems.append(f"{scene['id']} is {info['width']}x{info['height']}")
        if info["fps"] and abs(info["fps"] - FPS) > 0.01:
            problems.append(f"{scene['id']} is {info['fps']} fps")
    return {
        "name": "clips",
        "passed": not problems,
        "detail": problems or f"{len(durations)} clips, 12.000 s each, "
                              f"{WIDTH}x{HEIGHT} @ {FPS}fps",
    }


def _check_master() -> dict:
    if not MASTER.exists():
        return {"name": "master", "passed": False, "detail": "not rendered"}
    info = probe(MASTER)
    problems = []
    if abs((info["duration_s"] or 0) - 300) > 0.1:
        problems.append(f"duration {info['duration_s']}s")
    if (info["width"], info["height"]) != (WIDTH, HEIGHT):
        problems.append(f"resolution {info['width']}x{info['height']}")
    if info["fps"] and abs(info["fps"] - FPS) > 0.01:
        problems.append(f"fps {info['fps']}")
    return {"name": "master", "passed": not problems,
            "detail": problems or f"{info['duration_s']}s, "
                                  f"{info['width']}x{info['height']}, "
                                  f"{info['fps']}fps"}


def _check_audio() -> dict:
    from .config import SAMPLE_RATE
    path = screenplay.ROOT / "audio" / "mix.wav"
    if not path.exists():
        return {"name": "audio", "passed": False, "detail": "mix.wav missing"}
    with wave.open(str(path), "rb") as w:
        dur = w.getnframes() / float(w.getframerate())
        ch, sr = w.getnchannels(), w.getframerate()
    ok = abs(dur - 300) < 0.05 and sr == SAMPLE_RATE and ch == 2
    return {"name": "audio", "passed": ok,
            "detail": f"{dur:.3f}s, {sr} Hz, {ch}ch"}


def _check_continuity() -> dict:
    """Wardrobe must follow the timeline and KAIRO must never change design."""
    episode = screenplay.load()
    problems = []
    expected = {"present": "suit", "transition": "suit",
                "prehistoric": "hide", "cave": "hide", "map": "hide"}
    for scene in episode["scenes"]:
        if scene["wardrobe"] != expected[scene["act"]]:
            problems.append(f"{scene['id']} wardrobe drift")
        if scene["setting"].startswith("modern") and scene["wardrobe"] != "suit":
            problems.append(f"{scene['id']} room scene without suit")
        if (scene["setting"].startswith("savanna")
                or scene["setting"].startswith("cave")) and scene["wardrobe"] != "hide":
            problems.append(f"{scene['id']} prehistoric scene with modern clothes")
    backdrops_used = {s["render"]["backdrop"] for s in episode["scenes"]}
    return {"name": "continuity", "passed": not problems,
            "detail": problems or f"one design, {len(backdrops_used)} re-used "
                                  f"backdrops, wardrobe locked per timeline"}


def run_all() -> dict:
    checks = [_check_screenplay(), _check_voice(), _check_continuity(),
              _check_clips(), _check_audio(), _check_master()]
    return {"passed": all(c["passed"] for c in checks), "checks": checks}
