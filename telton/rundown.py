"""Stage 2 — turn curated stories into a timed rundown, script, SRT and caption."""

from __future__ import annotations

import re
from typing import Sequence

from .config import Project
from .models import Cue, Rundown, Segment, Story
from .util import (
    ensure_dir,
    estimate_duration,
    read_json,
    seconds_to_clock,
    seconds_to_srt,
    write_json,
)

SECTION_LABELS = {
    "iran_football": "فوتبال ایران",
    "iran_other": "ورزش ایران",
    "controversy": "حواشی و گفت‌وگو",
    "europe_football": "فوتبال اروپا",
    "world": "جهان ورزش",
    "whats_next": "برنامه‌ی بعدی",
}
SECTION_ORDER = list(SECTION_LABELS)

BUCKET_LEAD_IN = {
    "iran_football": "ایران، فوتبال:",
    "iran_other": "ایران، ورزش:",
    "controversy": "و اما حواشی:",
    "europe_football": "اروپا:",
    "world": "جهان ورزش:",
    "whats_next": "و در ادامه:",
}

SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟…])\s+|\n+")


def load_stories(project: Project) -> list[Story]:
    raw = read_json(project.stories_path, default=None)
    if raw is None:
        raise FileNotFoundError(
            f"{project.stories_path} not found — run `telton collect` and curate it first."
        )
    if isinstance(raw, dict):
        raw = raw.get("stories", [])
    return [Story.from_dict(item) for item in raw]


def save_stories(project: Project, stories: Sequence[Story]) -> None:
    write_json(project.stories_path, [s.to_dict() for s in stories])


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def chunk_cues(text: str, max_words: int) -> list[str]:
    """Split narration into subtitle-sized chunks without breaking sentences."""
    chunks: list[str] = []
    for sentence in sentences(text):
        words = sentence.split()
        if len(words) <= max_words:
            chunks.append(sentence)
            continue
        current: list[str] = []
        for word in words:
            if len(current) >= max_words:
                chunks.append(" ".join(current))
                current = []
            current.append(word)
        if current:
            chunks.append(" ".join(current))
    return chunks


def narration_for(story: Story, index: int) -> str:
    lead = BUCKET_LEAD_IN.get(story.bucket, "")
    parts = ["اول، " + lead if index == 0 else lead]
    parts.append(story.summary or story.headline)
    # only read the facts out loud when they add something the summary did not say
    extra = [f for f in story.facts if f.strip() and f.strip()[:10] not in (story.summary or "")]
    if extra:
        parts.append("؛ ".join(extra[:2]) + ".")
    return " ".join(part.strip() for part in parts if part.strip())


def compose(
    project: Project,
    stories: Sequence[Story],
    target_duration: float = 300.0,
    title: str | None = None,
) -> Rundown:
    style = project.style
    wps = float(style.get("narration.words_per_second", 2.9))
    tail = float(style.get("narration.tail_seconds", 0.9))
    title_card = float(style.get("narration.title_card_seconds", 2.4))
    max_words = int(style.get("narration.max_words_per_cue", 26))
    min_story = float(style.get("narration.min_story_seconds", 7.0))

    ordered = sorted(stories, key=lambda s: (SECTION_ORDER.index(s.bucket), s.priority))
    meta = project.meta
    rundown = Rundown(
        slug=project.slug,
        title=title or meta.get("title") or f"خبرهای ورزشی — {project.slug}",
        target_duration=target_duration,
    )

    clock = 0.0
    intro = Segment(id="intro", title=rundown.title, kind="intro", start=clock, end=clock + 6.0)
    intro_lead = str(
        meta.get("intro") or "خبرهای مهم ورزش، در چند دقیقه — ایران، اروپا و حواشی."
    )
    intro.cues.append(Cue(index=0, text=intro_lead, kind="title", start=clock + 0.5, end=clock + 5.2))
    rundown.segments.append(intro)
    clock = intro.end

    last_bucket: str | None = None
    shown_cards: set[str] = set()
    for position, story in enumerate(ordered):
        if story.bucket != last_bucket and story.bucket in SECTION_LABELS and story.bucket not in shown_cards:
            shown_cards.add(story.bucket)
            rundown.segments.append(
                Segment(
                    id=f"card-{story.bucket}",
                    title=SECTION_LABELS[story.bucket],
                    kind="title",
                    bucket=story.bucket,
                    start=clock,
                    end=clock + title_card,
                )
            )
            clock += title_card
            last_bucket = story.bucket

        segment = Segment(
            id=story.id,
            title=story.headline,
            kind="story",
            bucket=story.bucket,
            story=story,
            start=clock,
        )
        cursor = clock + 0.15
        for piece in chunk_cues(narration_for(story, position), max_words):
            length = max(1.4, estimate_duration(piece, wps))
            segment.cues.append(Cue(index=0, text=piece, start=cursor, end=cursor + length))
            cursor += length
        segment.end = max(cursor + tail, segment.start + min_story)
        clock = segment.end
        rundown.segments.append(segment)

    outro = Segment(id="outro", title="جمع‌بندی", kind="outro", start=clock)
    outro_text = str(
        meta.get("outro") or "کدام خبر مهم‌تر بود؟ نظرت را بنویس و برای خبرهای بعدی همراه ما باش."
    )
    length = estimate_duration(outro_text, wps)
    outro.cues.append(Cue(index=0, text=outro_text, kind="title", start=clock + 0.2, end=clock + 0.2 + length))
    outro.end = outro.cues[-1].end + 0.8
    rundown.segments.append(outro)
    rundown.renumber()
    return rundown


def refit(rundown: Rundown, target: float) -> Rundown:
    """Squeeze or pad a measured rundown to match the target duration."""
    total = rundown.end
    story_segments = [s for s in rundown.segments if s.kind == "story"]
    if total <= 0 or not story_segments:
        return rundown
    delta = target - total

    if delta < -1.0:
        deficit = -delta
        for segment in sorted(story_segments, key=lambda s: s.duration, reverse=True):
            narrated = segment.cues[-1].end - segment.start if segment.cues else 0.0
            spare = max(0.0, segment.duration - narrated - 0.4)
            take = min(spare, deficit)
            segment.end -= take
            deficit -= take
            if deficit <= 0.5:
                break
    elif delta > 0.5:
        share = delta / len(story_segments)
        for segment in story_segments:
            segment.end += min(share, 4.0)

    clock = 0.0
    for segment in rundown.segments:
        length = segment.duration
        shift = clock - segment.start
        segment.start = clock
        segment.end = clock + length
        for cue in segment.cues:
            cue.start += shift
            cue.end += shift
        clock = segment.end
    rundown.renumber()
    return rundown


def write_srt(rundown: Rundown, path) -> None:
    lines: list[str] = []
    for cue in rundown.cues:
        if cue.kind == "ticker":
            continue
        lines.append(str(cue.index))
        lines.append(f"{seconds_to_srt(cue.start)} --> {seconds_to_srt(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    ensure_dir(path.parent)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_script(rundown: Rundown, path) -> None:
    out: list[str] = [
        f"# {rundown.title}",
        "",
        f"**مدت هدف:** {seconds_to_clock(rundown.target_duration)} · "
        f"**مدت برنامه‌ریزی‌شده:** {seconds_to_clock(rundown.end)} · "
        f"**تعداد سگمنت:** {len(rundown.segments)}",
        "",
    ]
    for segment in rundown.segments:
        out.append(
            f"## {seconds_to_clock(segment.start)}–{seconds_to_clock(segment.end)} — "
            f"{segment.title}  `{segment.kind}`"
        )
        if segment.story:
            story = segment.story
            out.append(f"**بخش:** {SECTION_LABELS.get(story.bucket, story.bucket)}")
            out.append(f"**منبع:** {story.source_line or '—'}")
            if story.facts:
                out.append("**کارت‌ها:** " + " · ".join(story.facts))
            if story.broll:
                out.append(f"**فوتیج:** `{story.broll}`")
        out.append("")
        for cue in segment.cues:
            out.append(f"- `{seconds_to_clock(cue.start)}` {cue.text}")
        out.append("")
    ensure_dir(path.parent)
    path.write_text("\n".join(out), encoding="utf-8")


def write_caption(project: Project, rundown: Rundown, path) -> None:
    meta = project.meta
    stories = [s.story for s in rundown.segments if s.story]
    bullets = [
        f"{i}) {story.headline} — {story.summary.split('.')[0].strip()}."
        for i, story in enumerate(stories, start=1)
    ]
    # one clean, de-duplicated source line (outlet names, article titles live in sources.md)
    names = sorted(
        {
            source.name.split(" — ")[0].strip()
            for story in stories
            for source in story.sources
            if source.name
        }
    )
    lines = [
        str(meta.get("caption_intro") or rundown.title),
        "",
        *bullets,
        "",
        str(meta.get("cta") or "نظرت را کامنت کن و برای خبرهای بعدی فالو کن."),
        "",
        "📌 منابع: " + (" · ".join(names) if names else "—"),
        "",
        str(meta.get("hashtags") or "#ورزش #فوتبال #خبر_ورزشی #پرسپولیس #آرسنال"),
        "",
    ]
    ensure_dir(path.parent)
    path.write_text("\n".join(lines), encoding="utf-8")


def build(project: Project, target: float = 300.0, title: str | None = None) -> Rundown:
    project.ensure()
    stories = [s for s in load_stories(project) if s.summary.strip()]
    if not stories:
        raise ValueError("stories.json has no usable summaries")
    rundown = compose(project, stories, target_duration=target, title=title)
    rundown = refit(rundown, target)
    write_json(project.build / "rundown.json", rundown.to_dict())
    write_srt(rundown, project.build / "subtitles.srt")
    write_script(rundown, project.build / "script.md")
    write_caption(project, rundown, project.build / "caption.txt")
    return rundown
