"""Data model for stories, narration cues and the rendered rundown."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BUCKETS = (
    "iran_football",
    "iran_other",
    "controversy",
    "europe_football",
    "world",
    "whats_next",
)


@dataclass
class Source:
    name: str
    url: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "url": self.url}

    @classmethod
    def from_dict(cls, data: Any) -> "Source":
        if isinstance(data, str):
            return cls(name=data)
        return cls(name=str(data.get("name", "")), url=str(data.get("url", "")))


@dataclass
class Story:
    """One news item, already written in Persian and fact-checked."""

    id: str
    bucket: str
    headline: str                      # on-screen headline (short)
    summary: str                        # 1-3 narration sentences
    facts: list[str] = field(default_factory=list)      # chips shown on screen
    sources: list[Source] = field(default_factory=list)
    broll: str | None = None            # optional filename inside broll/
    priority: int = 3                   # lower = earlier / more important
    verified: bool = False              # must be True before publish
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.bucket not in BUCKETS:
            raise ValueError(f"unknown bucket {self.bucket!r}; allowed: {BUCKETS}")
        self.sources = [s if isinstance(s, Source) else Source.from_dict(s) for s in self.sources]

    @property
    def source_line(self) -> str:
        return " · ".join(s.name for s in self.sources if s.name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bucket": self.bucket,
            "headline": self.headline,
            "summary": self.summary,
            "facts": self.facts,
            "sources": [s.to_dict() for s in self.sources],
            "broll": self.broll,
            "priority": self.priority,
            "verified": self.verified,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Story":
        return cls(
            id=str(data["id"]),
            bucket=str(data.get("bucket", "world")),
            headline=str(data.get("headline", "")).strip(),
            summary=str(data.get("summary", "")).strip(),
            facts=[str(f) for f in data.get("facts", [])],
            sources=[Source.from_dict(s) for s in data.get("sources", [])],
            broll=data.get("broll"),
            priority=int(data.get("priority", 3)),
            verified=bool(data.get("verified", False)),
            tags=[str(t) for t in data.get("tags", [])],
        )


@dataclass
class Cue:
    """A subtitle / narration unit."""

    index: int
    text: str
    kind: str = "narration"   # narration | title | ticker
    start: float = 0.0
    end: float = 0.0
    audio: str | None = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "kind": self.kind,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "audio": self.audio,
        }


@dataclass
class Segment:
    """A chapter of the video (usually one story, sometimes a title card)."""

    id: str
    title: str
    kind: str = "story"                 # intro | title | story | outro
    bucket: str = "world"
    story: Story | None = None
    cues: list[Cue] = field(default_factory=list)
    start: float = 0.0
    end: float = 0.0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "bucket": self.bucket,
            "story": self.story.to_dict() if self.story else None,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "cues": [c.to_dict() for c in self.cues],
        }


@dataclass
class Rundown:
    slug: str
    title: str
    segments: list[Segment] = field(default_factory=list)
    target_duration: float = 300.0

    @property
    def end(self) -> float:
        return self.segments[-1].end if self.segments else 0.0

    @property
    def cues(self) -> list[Cue]:
        return [cue for seg in self.segments for cue in seg.cues]

    def renumber(self) -> None:
        for i, cue in enumerate(self.cues, start=1):
            cue.index = i

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "target_duration": self.target_duration,
            "duration": round(self.end, 3),
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Rundown":
        rundown = cls(
            slug=data["slug"],
            title=data["title"],
            target_duration=float(data.get("target_duration", 300)),
        )
        for seg in data["segments"]:
            story = Story.from_dict(seg["story"]) if seg.get("story") else None
            segment = Segment(
                id=seg["id"],
                title=seg["title"],
                kind=seg.get("kind", "story"),
                bucket=seg.get("bucket", "world"),
                story=story,
                start=float(seg.get("start", 0)),
                end=float(seg.get("end", 0)),
            )
            for cue in seg.get("cues", []):
                segment.cues.append(
                    Cue(
                        index=int(cue["index"]),
                        text=cue["text"],
                        kind=cue.get("kind", "narration"),
                        start=float(cue.get("start", 0)),
                        end=float(cue.get("end", 0)),
                        audio=cue.get("audio"),
                    )
                )
            rundown.segments.append(segment)
        return rundown
