"""Build a 40-60 second vertical short (YouTube Shorts / Instagram Reels).

Same stories as the long episode, but cut down to: one hook + the two or three
strongest items + a call to action. Burned-in captions, 9:16, punchy pacing.
"""

from __future__ import annotations

from pathlib import Path

from .config import Project
from .models import Cue, Rundown, Segment
from .rundown import SECTION_ORDER, load_stories, write_json, write_srt
from .util import ensure_dir, estimate_duration, read_json

HOOK_FALLBACK = "این خبر را از دست نده!"
CTA = "سابسکرایب کن و زنگوله رو بزن!"


def pick_stories(project: Project, count: int = 3):
    stories = [s for s in load_stories(project) if s.summary.strip()]
    stories.sort(key=lambda s: (SECTION_ORDER.index(s.bucket), s.priority))
    return stories[:count]


def _punchline(story) -> str:
    first = story.summary.split(".")[0].strip()
    return first if len(first.split()) <= 28 else " ".join(first.split()[:26])


def compose_short(project: Project, target: float = 50.0, count: int = 3) -> Rundown:
    style = project.style
    wps = float(style.get("narration.words_per_second", 2.9))
    stories = pick_stories(project, count)
    hooks = project.meta.get("thumb_hooks") or [HOOK_FALLBACK]
    hook_text = str(hooks[0] if isinstance(hooks, list) else hooks)

    rundown = Rundown(slug=project.slug, title=str(project.meta.get("title") or project.slug),
                      target_duration=target)
    clock = 0.0

    hook = Segment(id="short-hook", title=hook_text, kind="intro", start=clock)
    for piece in (hook_text, "بزن بریم!"):
        length = max(1.2, estimate_duration(piece, wps))
        hook.cues.append(Cue(index=0, text=piece, kind="hook", start=clock + 0.2, end=clock + 0.2 + length))
        clock += length + 0.15
    hook.end = clock + 0.4
    clock = hook.end
    rundown.segments.append(hook)

    for story in stories:
        text = _punchline(story)
        segment = Segment(id=story.id, title=story.headline, kind="story", bucket=story.bucket,
                          story=story, start=clock)
        length = max(1.6, estimate_duration(text, wps))
        segment.cues.append(Cue(index=0, text=text, kind="narration", start=clock + 0.1,
                                end=clock + 0.1 + length))
        segment.end = segment.cues[-1].end + 0.7
        clock = segment.end
        rundown.segments.append(segment)

    cta = Segment(id="short-cta", title="tooop news", kind="outro", start=clock)
    length = max(1.6, estimate_duration(CTA, wps))
    cta.cues.append(Cue(index=0, text=CTA, kind="title", start=clock + 0.1, end=clock + 0.1 + length))
    cta.end = cta.cues[-1].end + 0.6
    rundown.segments.append(cta)
    rundown.renumber()
    return rundown


def make_short(
    project: Project,
    target: float = 50.0,
    count: int = 3,
    offline: bool = False,
    voice: str | None = None,
) -> dict:
    """Compose + voice + render a vertical short. Returns the output paths."""
    from .render import render_video
    from .voice import assemble_audio, speak

    project.ensure()
    rundown = compose_short(project, target=target, count=count)
    write_json(project.build / "short-rundown.json", rundown.to_dict())

    work = ensure_dir(project.build / "short")
    for segment in rundown.segments:                 # isolate short audio from the long one
        for cue in segment.cues:
            cue.audio = None
    rundown = speak(project, rundown, voice=voice, offline=offline, subdir="short-voice")
    write_srt(rundown, work / "short.srt")
    audio = assemble_audio(project, rundown, out_path=work / "short-audio.wav")

    out_path = project.out / "short-1080x1920.mp4"
    render_video(project, rundown, audio, out_path=out_path, width=1080, height=1920,
                 max_seconds=target + 2)
    return {
        "short": str(out_path),
        "seconds": round(rundown.end, 1),
        "stories": [s.id for s in rundown.segments if s.story],
        "subtitles": str(work / "short.srt"),
    }
