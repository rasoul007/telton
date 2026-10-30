"""Screenplay loading, validation and merging.

The source of truth is one JSON file per scene in ``film/scenes`` plus
``film/episode_header.json``.  ``merge()`` produces the single canonical
``film/episode01.json`` that every other stage consumes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILM_DIR = ROOT / "film"
SCENES_DIR = FILM_DIR / "scenes"
HEADER = FILM_DIR / "episode_header.json"
EPISODE = FILM_DIR / "episode01.json"

REQUIRED_KEYS = (
    "id", "index", "title", "start_s", "duration_s", "timecode", "act",
    "setting", "wardrobe", "shot", "camera", "action", "expression",
    "lighting", "audio", "dialogue_fa", "gloss_en", "render",
    "continuity", "transition", "image_prompt", "video_prompt",
)

PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")
LATIN_RE = re.compile(r"[A-Za-z]")

WARDROBE_BY_ACT = {"present": "suit", "transition": "suit",
                   "prehistoric": "hide", "map": "hide", "cave": "hide"}


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_scene_files() -> list[dict]:
    files = sorted(SCENES_DIR.glob("S*.json"))
    return [_read(p) for p in files]


def merge() -> dict:
    """Merge header + scene files into the canonical episode document."""
    header = _read(HEADER)
    scenes = sorted(load_scene_files(), key=lambda s: s["index"])
    episode = dict(header)
    episode["scenes"] = scenes
    episode["scene_count"] = len(scenes)
    episode["total_duration_s"] = sum(s["duration_s"] for s in scenes)
    with EPISODE.open("w", encoding="utf-8") as fh:
        json.dump(episode, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return episode


def load() -> dict:
    return _read(EPISODE) if EPISODE.exists() else merge()


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
def validate(episode: dict) -> list[str]:
    """Return a list of hard errors (empty list == screenplay is valid)."""
    errors: list[str] = []
    scenes = episode["scenes"]

    if len(scenes) != 25:
        errors.append(f"expected 25 scenes, found {len(scenes)}")

    total = 0.0
    for expected_index, scene in enumerate(scenes, start=1):
        sid = scene.get("id", f"#{expected_index}")
        missing = [k for k in REQUIRED_KEYS if k not in scene]
        if missing:
            errors.append(f"{sid}: missing keys {missing}")
            continue

        if scene["index"] != expected_index:
            errors.append(f"{sid}: index {scene['index']} != {expected_index}")
        if scene["id"] != f"S{expected_index:02d}":
            errors.append(f"{sid}: id does not match position")

        if scene["duration_s"] != 12:
            errors.append(f"{sid}: duration {scene['duration_s']}s != 12s")
        expected_start = (expected_index - 1) * 12.0
        if abs(scene["start_s"] - expected_start) > 1e-6:
            errors.append(
                f"{sid}: start {scene['start_s']}s != {expected_start}s")
        total += scene["duration_s"]

        line = scene["dialogue_fa"].strip()
        if not line:
            errors.append(f"{sid}: empty dialogue")
        if not PERSIAN_RE.search(line):
            errors.append(f"{sid}: dialogue is not Persian")
        if LATIN_RE.search(line):
            errors.append(f"{sid}: dialogue contains latin characters")
        if "  " in line:
            errors.append(f"{sid}: double space in dialogue")

        act = scene["act"]
        expected_wardrobe = WARDROBE_BY_ACT.get(act)
        if expected_wardrobe and scene["wardrobe"] != expected_wardrobe:
            errors.append(
                f"{sid}: wardrobe {scene['wardrobe']} != {expected_wardrobe} "
                f"for act {act}")

        for key in ("image_prompt", "video_prompt"):
            if len(scene[key].split()) < 25:
                errors.append(f"{sid}: {key} is too short to be useful")

    if abs(total - 300) > 1e-6:
        errors.append(f"total duration {total}s != 300s")

    return errors


def sentences(line: str) -> list[str]:
    parts = re.split(r"(?<=[.!؟])\s+", line.strip())
    return [p for p in parts if p]


def stats(episode: dict) -> dict:
    scenes = episode["scenes"]
    words = sum(len(s["dialogue_fa"].split()) for s in scenes)
    chars = sum(len(s["dialogue_fa"]) for s in scenes)
    return {
        "scenes": len(scenes),
        "duration_s": sum(s["duration_s"] for s in scenes),
        "dialogue_words": words,
        "dialogue_chars": chars,
        "sentences": sum(len(sentences(s["dialogue_fa"])) for s in scenes),
        "acts": sorted({s["act"] for s in scenes}),
        "settings": sorted({s["setting"] for s in scenes}),
        "poses": sorted({s["render"]["pose"] for s in scenes}),
    }
