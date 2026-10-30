"""Persian voice-over generation for KAIRO.

Voice: fa-IR-FaridNeural (male, medium-low, warm, Iranian conversational).

Every scene has a hard 12 second slot, so each line is measured and fitted:

* first attempt at natural rate,
* if it does not fit, the prosody ``rate`` is raised in 5% steps up to +30%,
* any remaining overflow is closed with ``atempo`` (max 1.25x),
* the result is normalised to 48 kHz mono PCM and reported in the QC file.

Nothing is ever cut, translated or reworded - the Persian text is used
verbatim, exactly as delivered by the screenplay.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import wave
from pathlib import Path

from . import screenplay
from .config import FFMPEG

VOICE_ID = "fa-IR-FaridNeural"
VO_DIR = screenplay.ROOT / "audio" / "vo"
RAW_DIR = VO_DIR / "raw"
REPORT = VO_DIR / "vo_report.json"

LEAD_IN_S = 0.55          # silence before the first syllable
TAIL_S = 0.55             # silence after the last syllable
MAX_RATE = 30             # percent, prosody ceiling
MAX_TEMPO = 1.30          # atempo ceiling (pitch preserving)


def slot_budget(scene: dict) -> float:
    return scene["duration_s"] - LEAD_IN_S - TAIL_S


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def marker_path(scene_id: str) -> Path:
    return VO_DIR / f"{scene_id}.ok"


def _read_marker(scene_id: str) -> dict | None:
    """A WAV only counts as cached when its success marker exists.

    Without the marker a partially written file (e.g. an interrupted run) would
    be silently reused and every downstream duration would be wrong.
    """
    path = marker_path(scene_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _ffmpeg(*args: str) -> None:
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error",
                    "-y", *args], check=True)


async def _speak(text: str, rate_pct: int, out_mp3: Path) -> None:
    import edge_tts
    rate = f"{rate_pct:+d}%"
    com = edge_tts.Communicate(text, VOICE_ID, rate=rate)
    await com.save(str(out_mp3))


def _to_wav(mp3: Path, wav: Path) -> None:
    _ffmpeg("-i", str(mp3), "-ar", "48000", "-ac", "1",
            "-c:a", "pcm_s16le", str(wav))


def _atempo(wav: Path, tempo: float) -> None:
    tmp = wav.with_suffix(".tmp.wav")
    _ffmpeg("-i", str(wav), "-filter:a", f"atempo={tempo:.4f}",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(tmp))
    tmp.replace(wav)


def generate_scene(scene: dict, force: bool = False) -> dict:
    sid = scene["id"]
    final_wav = VO_DIR / f"{sid}.wav"
    raw_mp3 = RAW_DIR / f"{sid}.mp3"
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    budget = slot_budget(scene)

    if not force:
        marker = _read_marker(sid)
        if marker and final_wav.exists():
            # trust the marker but re-measure so the report is never stale
            dur = wav_duration(final_wav)
            return {**marker, "final_s": round(dur, 3),
                    "budget_s": round(budget, 3),
                    "fits": dur <= budget + 1e-3, "cached": True}

    text = scene["dialogue_fa"]
    raw_dur = 0.0
    used_rate = 0
    # Pick the mildest prosody speed-up that keeps any residual tempo change
    # inside the atempo ceiling (pitch-preserving), so the voice stays natural.
    for rate in range(0, MAX_RATE + 1, 5):
        asyncio.run(_speak(text, rate, raw_mp3))
        _to_wav(raw_mp3, final_wav)
        raw_dur = wav_duration(final_wav)
        used_rate = rate
        if raw_dur <= budget * MAX_TEMPO:
            break

    tempo = 1.0
    dur = wav_duration(final_wav)
    if dur > budget:
        tempo = min(MAX_TEMPO, dur / budget)
        _atempo(final_wav, tempo)
        dur = wav_duration(final_wav)

    row = {"id": sid, "rate_pct": used_rate,
           "atempo": None if tempo == 1.0 else round(tempo, 4),
           "raw_s": round(raw_dur, 3), "final_s": round(dur, 3),
           "budget_s": round(budget, 3),
           "fits": dur <= budget + 1e-3, "cached": False}
    marker_path(sid).write_text(json.dumps(row, ensure_ascii=False, indent=2),
                                encoding="utf-8")
    return row


def generate_all(force: bool = False) -> dict:
    episode = screenplay.load()
    VO_DIR.mkdir(parents=True, exist_ok=True)
    rows = [generate_scene(s, force=force) for s in episode["scenes"]]
    report = {
        "voice_id": VOICE_ID,
        "lead_in_s": LEAD_IN_S,
        "tail_s": TAIL_S,
        "scenes": rows,
        "total_speech_s": round(sum(r["final_s"] for r in rows), 2),
        "all_fit": all(r["fits"] for r in rows),
        "max_rate_used": max((r["rate_pct"] or 0) for r in rows),
        "tempo_used": [r["id"] for r in rows if r["atempo"]],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return report
