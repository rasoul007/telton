"""Stage 3 — Persian voice-over (edge-tts, with gTTS / silence fallbacks)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from .config import REPO_ROOT, Project
from .models import Rundown
from .rundown import refit, write_srt
from .text_fa import spoken
from .util import ensure_dir, estimate_duration, ffmpeg_exe, probe_duration, run, write_json

DEFAULT_VOICE = "fa-IR-FaridNeural"
FALLBACK_VOICES = ("fa-IR-FaridNeural", "fa-IR-DilaraNeural")


def _edge(text: str, out: Path, voice: str, rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> None:
    import edge_tts

    async def go() -> None:
        await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume).save(str(out))

    asyncio.run(go())


def _google(text: str, out: Path, voice: str | None = None, **_: object) -> None:
    from gtts import gTTS

    gTTS(text=text, lang="fa").save(str(out))


def _openai(text: str, out: Path, voice: str | None = None, **_: object) -> None:
    """OpenAI TTS (needs OPENAI_API_KEY). Best quality if you have a key."""
    import json as _json
    import os
    import urllib.request

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY تنظیم نشده است")
    payload = _json.dumps({
        "model": os.environ.get("TELTON_OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        "voice": voice or os.environ.get("TELTON_OPENAI_VOICE", "alloy"),
        "input": text,
        "response_format": "mp3",
    }).encode()
    request = urllib.request.Request(
        "https://api.openai.com/v1/audio/speech",
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        out.write_bytes(response.read())


def _elevenlabs(text: str, out: Path, voice: str | None = None, **_: object) -> None:
    """ElevenLabs TTS (needs ELEVENLABS_API_KEY). Very natural Persian voices."""
    import json as _json
    import os
    import urllib.request

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice_id = voice or os.environ.get("TELTON_ELEVEN_VOICE", "")
    if not key or not voice_id:
        raise RuntimeError("ELEVENLABS_API_KEY / TELTON_ELEVEN_VOICE تنظیم نشده است")
    payload = _json.dumps({
        "text": text,
        "model_id": os.environ.get("TELTON_ELEVEN_MODEL", "eleven_multilingual_v2"),
        "voice_settings": {"stability": 0.35, "similarity_boost": 0.8, "style": 0.35},
    }).encode()
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=payload,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        out.write_bytes(response.read())


def _piper(text: str, out: Path, voice: str | None = None, rate: str = "+0%", **_: object) -> None:
    """Offline Persian voice (piper). Free, no key, sometimes clearer on names."""
    import os
    import tempfile

    from piper import PiperVoice

    model = Path(voice) if voice and str(voice).endswith(".onnx") else Path(
        os.environ.get("TELTON_PIPER_MODEL", "assets/tts/fa_IR-amir-medium.onnx")
    )
    if not model.exists():
        raise RuntimeError(f"مدل piper پیدا نشد: {model}")
    piper_voice = PiperVoice.load(str(model))
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        raw = Path(handle.name)
    try:
        import wave

        with wave.open(str(raw), "wb") as wav_file:
            piper_voice.synthesize_wav(text, wav_file)
        tempo = 1.0 + float(str(rate).replace("%", "").replace("+", "") or 0) / 100.0
        tempo = max(0.7, min(1.4, tempo))
        run(
            [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(raw),
             "-filter:a", f"atempo={tempo:.3f}", "-codec:a", "libmp3lame", "-b:a", "160k", str(out)]
        )
    finally:
        raw.unlink(missing_ok=True)


ENGINES = {
    "edge": _edge,
    "google": _google,
    "openai": _openai,
    "elevenlabs": _elevenlabs,
    "piper": _piper,
}


def available_engines() -> dict[str, str]:
    """Which engines can run right now (and why not)."""
    import os

    status: dict[str, str] = {}
    try:
        import edge_tts  # noqa: F401

        status["edge"] = "ok"
    except Exception:
        status["edge"] = "نصب نیست"
    try:
        import gtts
        from gtts.lang import tts_langs

        status["google"] = "ok" if "fa" in tts_langs() else "فارسی ندارد"
    except Exception:
        status["google"] = "نصب نیست"
    status["openai"] = "ok" if os.environ.get("OPENAI_API_KEY") else "کلید ندارد"
    status["elevenlabs"] = (
        "ok"
        if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("TELTON_ELEVEN_VOICE")
        else "کلید ندارد"
    )
    try:
        from piper import PiperVoice  # noqa: F401

        model = Path(
            os.environ.get("TELTON_PIPER_MODEL", "assets/tts/fa_IR-amir-medium.onnx")
        )
        status["piper"] = "ok" if model.exists() else "مدل ندارد"
    except Exception:
        status["piper"] = "نصب نیست"
    return status


def synthesize(
    text: str,
    out: Path,
    engine: str = "edge",
    voice: str | None = None,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
) -> str:
    """Render one line of speech with the requested engine; returns the engine used."""
    order = [engine] + [name for name in ("edge", "google") if name != engine]
    last_error: Exception | None = None
    for name in order:
        func = ENGINES.get(name)
        if func is None:
            continue
        try:
            use_voice = voice
            if name == "edge" and not use_voice:
                use_voice = DEFAULT_VOICE      # edge needs an explicit voice id
            func(text, out, voice=use_voice, rate=rate, pitch=pitch, volume=volume)
            if out.exists() and out.stat().st_size > 800:
                return name
        except Exception as exc:          # try the next engine
            last_error = exc
            continue
    raise RuntimeError(f"هیچ موتور صوتی کار نکرد: {last_error}")


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
    rate: str | None = None,
    subdir: str | None = None,
) -> Rundown:
    """Generate one audio file per cue, then re-time the rundown from real audio."""
    style = project.style
    project.ensure()
    voice_dir = ensure_dir(project.build / subdir) if subdir else ensure_dir(project.voice_dir)
    wps = float(style.get("narration.words_per_second", 2.9))
    tail = float(style.get("narration.tail_seconds", 0.9))
    engine = str(style.get("narration.engine", "edge"))
    candidates = [voice] if voice else list(FALLBACK_VOICES)

    base_rate = rate or str(style.get("narration.rate", "+9%"))
    base_pitch = str(style.get("narration.pitch", "+3Hz"))
    volume = str(style.get("narration.volume", "+0%"))
    hook_rate = str(style.get("narration.hook_rate", "+18%"))
    hook_pitch = str(style.get("narration.hook_pitch", "+7Hz"))
    variety = int(style.get("narration.variety_hz", 2))

    for segment in rundown.segments:
        cursor = segment.start + 0.1
        for position, cue in enumerate(segment.cues):
            target = voice_dir / f"cue-{cue.index:03d}.mp3"
            cue.audio = None
            # the hook and chapter titles are delivered faster and higher, like a real anchor
            if cue.kind in {"title", "hook"}:
                cue_rate, cue_pitch = hook_rate, hook_pitch
            else:
                cue_rate = base_rate
                offset = (position % 3 - 1) * variety     # -2, 0, +2 Hz
                cue_pitch = f"{offset:+d}Hz" if offset else base_pitch
                if offset:
                    base_hz = int(str(base_pitch).replace("Hz", "").replace("+", "") or 0)
                    cue_pitch = f"{base_hz + offset:+d}Hz"
            tts_text = spoken(cue.text)
            if not offline:
                used_engine = "edge"
                for candidate in candidates:
                    try:
                        used_engine = synthesize(
                            tts_text, target, engine=engine, voice=candidate,
                            rate=cue_rate, pitch=cue_pitch, volume=volume,
                        )
                        break
                    except Exception:
                        continue
                if not target.exists():
                    try:
                        _google(tts_text, target)          # last resort: free Google voice
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


def music_track(project: Project) -> Path | None:
    """Optional background bed: assets/music/*.mp3 (royalty-free) or project override."""
    custom = project.meta.get("music")
    if custom:
        path = Path(custom)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.exists():
            return path
    folder = REPO_ROOT / "assets" / "music"
    if folder.exists():
        for pattern in ("*.mp3", "*.m4a", "*.wav", "*.ogg"):
            found = sorted(folder.glob(pattern))
            if found:
                return found[0]
    return None


def assemble_audio(project: Project, rundown: Rundown, out_path: Path | None = None) -> Path:
    """Mix every cue at its absolute offset, with the music bed ducked under the voice."""
    out_path = out_path or project.build / "audio.wav"
    cues = [c for c in rundown.cues if c.audio]
    if not cues:
        raise RuntimeError("no narration audio found — run the voice stage first")
    total = max(c.end for c in cues) + 0.5
    music = music_track(project) if bool(project.style.get("audio.music", True)) else None

    cmd = [ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
    for cue in cues:
        cmd += ["-i", str(project.root / cue.audio)]
    music_index = len(cues) + 1
    if music is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music)]

    filters = []
    for i, cue in enumerate(cues, start=1):
        delay = int(round(cue.start * 1000))
        filters.append(f"[{i}:a]aresample=44100,adelay={delay}|{delay}[a{i}]")
    voices = "".join(f"[a{i}]" for i in range(1, len(cues) + 1))
    filters.append(f"[0:a]{voices}amix=inputs={len(cues) + 1}:normalize=0[narr]")

    if music is not None:
        vol = float(project.style.get("audio.music_volume", 0.55))
        ratio = float(project.style.get("audio.duck_ratio", 8))
        threshold = float(project.style.get("audio.duck_threshold", 0.045))
        filters.append("[narr]asplit=2[n1][nsc]")
        # bed sits at `vol` in the gaps and is pushed down by the sidechain while speaking
        filters.append(
            f"[{music_index}:a]aresample=44100,atrim=0:{total:.2f},volume={vol}[bed]"
        )
        filters.append(
            f"[bed][nsc]sidechaincompress=threshold={threshold}:ratio={ratio}:"
            "attack=12:release=420[ducked]"
        )
        filters.append("[n1][ducked]amix=inputs=2:normalize=0,alimiter=limit=0.95[mix]")
    else:
        filters.append("[narr]alimiter=limit=0.95[mix]")

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[mix]", "-t", f"{total:.2f}", "-ar", "44100", "-ac", "1", str(out_path),
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
