"""Configuration loading (config/*.yaml) and project paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Style:
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    # convenience accessors -------------------------------------------------
    @property
    def width(self) -> int:
        return int(self.get("video.width", 1080))

    @property
    def height(self) -> int:
        return int(self.get("video.height", 1920))

    @property
    def fps(self) -> int:
        return int(self.get("video.fps", 30))

    def color(self, key: str, default: str = "#FFFFFF") -> tuple[int, int, int]:
        value = str(self.get(f"colors.{key}", default)).lstrip("#")
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]

    def font_path(self, key: str = "bold") -> Path:
        path = Path(self.get(f"fonts.{key}", "assets/fonts/Vazirmatn-Bold.ttf"))
        return path if path.is_absolute() else REPO_ROOT / path


def load_style(path: Path | None = None) -> Style:
    path = path or REPO_ROOT / "config" / "style.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Style(raw=data)


def load_sources(path: Path | None = None) -> dict[str, Any]:
    path = path or REPO_ROOT / "config" / "sources.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


class Project:
    """A single episode: projects/<slug>/…"""

    def __init__(self, slug: str, root: Path | None = None):
        self.slug = slug
        self.root = (root or REPO_ROOT / "projects" / slug)
        self.style = load_style()

    # ---- paths -----------------------------------------------------------
    @property
    def meta_path(self) -> Path:
        return self.root / "project.yaml"

    @property
    def stories_path(self) -> Path:
        return self.root / "stories.json"

    @property
    def candidates_path(self) -> Path:
        return self.build / "candidates.json"

    @property
    def build(self) -> Path:
        return self.root / "build"

    @property
    def out(self) -> Path:
        return self.root / "out"

    @property
    def voice_dir(self) -> Path:
        return self.build / "voice"

    @property
    def video_path(self) -> Path:
        return self.out / "video.mp4"

    @property
    def approval_path(self) -> Path:
        return self.out / "approval.json"

    # ---- metadata --------------------------------------------------------
    @property
    def meta(self) -> dict[str, Any]:
        if self.meta_path.exists():
            return yaml.safe_load(self.meta_path.read_text(encoding="utf-8")) or {}
        return {}

    def ensure(self) -> "Project":
        for path in (self.root, self.build, self.out, self.voice_dir):
            path.mkdir(parents=True, exist_ok=True)
        return self
