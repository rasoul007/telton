"""Stage 3 — Persian voice-over (edge-tts, with gTTS / silence fallbacks)."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from .config import Project
from .models import Rundown
from .rundown import refit, write_srt
from .util import ensure_dir, estimate_duration, ffmpeg_exe, probe_duration, run, write_json

DEFAULT_VOICE = "fa-IR-FaridNeural"
FALLBACK_VOICES = ("fa-IR-FaridNeural", "fa-IR-DilaraNeural")


def _edge(text: str, out: Path, voice: str, rate: str = "+0%") -> None:
    import edge_tts

    async def go() -> None:
        await edge_tts.Communicate(text, voice, rate=rate).save(str(out))

    asyncio.run(go())


def _gtts(text: str, out: Path) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="fa").save(str(out))


def _silence(out: Path, seconds: float) -> None:
    run(
        [
            ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", f"{max(0.3, seconds):.2f}", "-q:a", "9", str(out),
        ]
    )


def speak(
    project: Project,
    rundown: Rundown,
    voice: str | None = None,
    offline: bool = False,
    rate: str = "+0%",
) -> Rundown:
    """Generate one audio file per cue, then re-time the rundown from real audio."""
    project.ensure()
    ensure_dir(project.voice_dir)
    wps = float(project.style.get("narration.words_per_second", 2.9))
    tail = float(project.style.get("narration.tail_seconds", 0.9))
    candidates = [voice] if voice else list(FALLBACK_VOICES)

    for segment in rundown.segments:
        cursor = segment.start + 0.1
        for cue in segment.cues:
            target = project.voice_dir / f"cue-{cue.index:03d}.mp3"
            cue.audio = None
            if not offline:
                for candidate in candidates:
                    try:
                        _edge(cue.text, target, candidate, rate=rate)
                        break
                    except Exception:
                        continue
                if not target.exists():
                    try:
                        _gtts(cue.text, target)
                    except Exception:
                        pass
            if not target.exists():
                _silence(target, estimate_duration(cue.text, wps))
            cue.audio = str(target.relative_to(project.root))
            length = probe_duration(target)
            cue.start = cursor
            cue.end = cursor + length
            cursor = cue.end + 0.08
        if segment.cues:
            segment.end = max(segment.cues[-1].end + tail, segment.start + 1.0)
    return rundown


def assemble_audio(project: Project, rundown: Rundown, out_path: Path | None = None) -> Path:
    """Mix every cue at its absolute offset into one mono wav."""
    out_path = out_path or project.build / "audio.wav"
    cues = [c for c in rundown.cues if c.audio]
    if not cues:
        raise RuntimeError("no narration audio found — run the voice stage first")
    total = max(c.end for c in cues) + 0.5
    cmd = [ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
    for cue in cues:
        cmd += ["-i", str(project.root / cue.audio)]
    filters = []
    for i, cue in enumerate(cues, start=1):
        delay = int(round(cue.start * 1000))
        filters.append(f"[{i}:a]aresample=44100,adelay={delay}|{delay}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(1, len(cues) + 1))
    filters.append(f"[0:a]{mix}amix=inputs={len(cues) + 1}:normalize=0[mix]")
    filters.append("[mix]alimiter=limit=0.95[out]")
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[out]", "-t", f"{total:.2f}", "-ar", "44100", "-ac", "1", str(out_path),
    ]
    run(cmd)
    return out_path


def drop_to_fit(rundown: Rundown, target: float, min_stories: int = 4) -> Rundown:
    """Drop the least important stories until the measured video fits the target."""
    while True:
        stories = [s for s in rundown.segments if s.kind == "story"]
        if rundown.end <= target * 1.02 or len(stories) <= min_stories:
            break
        victim = max(stories, key=lambda s: (s.story.priority if s.story else 9, s.duration))
        rundown.segments = [s for s in rundown.segments if s is not victim]
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


def voice_stage(
    project: Project,
    voice: str | None = None,
    offline: bool = False,
    target: float | None = None,
    rate: str = "+0%",
    fit: bool = True,
) -> tuple[Rundown, Path]:
    from .rundown import write_caption, write_script

    rundown_data = project.build / "rundown.json"
    if not rundown_data.exists():
        if target is None:
            raise FileNotFoundError("rundown.json missing — run `telton build` first")
        from .rundown import build as build_rundown

        build_rundown(project, target=target)
    from .util import read_json

    rundown = Rundown.from_dict(read_json(rundown_data))
    rundown = speak(project, rundown, voice=voice, offline=offline, rate=rate)
    if target:
        if fit:
            rundown = drop_to_fit(rundown, target)
        rundown = refit(rundown, target)
    write_json(project.build / "rundown.json", rundown.to_dict())
    write_srt(rundown, project.build / "subtitles.srt")
    write_script(rundown, project.build / "script.md")
    write_caption(project, rundown, project.build / "caption.txt")
    audio = assemble_audio(project, rundown)
    return rundown, audio
