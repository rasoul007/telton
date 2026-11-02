"""Voice stage tests — offline mode uses silence so no network is required."""

from __future__ import annotations

import pytest

from telton.models import Rundown
from telton.rundown import build
from telton.util import probe_duration, read_json
from telton.voice import assemble_audio, drop_to_fit, speak, voice_stage


def test_offline_voice_creates_one_audio_file_per_cue(project):
    rundown = build(project, target=30)
    rundown = speak(project, rundown, offline=True)
    assert rundown.cues
    for cue in rundown.cues:
        assert cue.audio, "every cue needs an audio file"
        assert (project.root / cue.audio).exists()
        assert cue.end > cue.start


def test_voice_stage_mixes_audio_and_rewrites_srt(project):
    rundown, audio = voice_stage(project, offline=True, target=25)
    assert audio.exists()
    assert audio.stat().st_size > 1000
    duration = probe_duration(audio)
    assert duration >= 15
    # the rundown on disk must match the audio that was just produced
    stored = Rundown.from_dict(read_json(project.build / "rundown.json"))
    assert stored.end == pytest.approx(rundown.end, abs=0.5)
    srt = (project.build / "subtitles.srt").read_text(encoding="utf-8")
    assert srt.count("-->") == len(rundown.cues)


def test_assemble_audio_places_cues_at_their_offsets(project):
    rundown = build(project, target=20)
    rundown = speak(project, rundown, offline=True)
    audio = assemble_audio(project, rundown)
    assert probe_duration(audio) == pytest.approx(rundown.end, abs=1.5)


def test_drop_to_fit_removes_least_important_stories(project):
    rundown = build(project, target=60)
    before = len([s for s in rundown.segments if s.kind == "story"])
    # pretend the narration came out three times longer than planned
    for segment in rundown.segments:
        for cue in segment.cues:
            cue.start *= 3
            cue.end *= 3
        segment.start *= 3
        segment.end *= 3
    assert rundown.end > 100
    before_end = rundown.end
    drop_to_fit(rundown, target=60, min_stories=1)
    after = len([s for s in rundown.segments if s.kind == "story"])
    assert after < before, "the least important story must be dropped"
    assert rundown.segments[0].start == 0
    assert rundown.end < before_end * 0.8, "removing stories must shorten the timeline"
