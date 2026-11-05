"""Voice engine plumbing + pronunciation fixes (no network needed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from telton import text_fa
from telton import voice as voice_mod


def test_latin_abbreviations_are_spelled_out():
    assert text_fa.latin_to_persian("در VAR و F1") == "در وی ای آر و اف یک"
    assert "اف سی" in text_fa.latin_to_persian("آرسنال FC")


def test_say_as_forces_pronunciation():
    assert text_fa.apply_say_as("پرسپولیس") == "پِرسِپُلیس"
    # inside a longer word nothing changes
    assert text_fa.apply_say_as("پرسپولیسی") == "پرسپولیسی"


def test_spoken_pipeline_applies_everything():
    out = text_fa.spoken("آرسنال با VAR در F1")
    assert "آرسِنال" in out
    assert "وی ای آر" in out
    assert "اف یک" in out


def test_available_engines_reports_state():
    status = voice_mod.available_engines()
    assert set(status) >= {"edge", "google", "openai", "elevenlabs", "piper"}
    assert all(isinstance(value, str) for value in status.values())


def test_synthesize_uses_requested_engine(tmp_path):
    target = tmp_path / "a.mp3"
    calls = []

    def fake(text, out, voice=None, **kwargs):
        calls.append(text)
        Path(out).write_bytes(b"x" * 2000)

    engines = dict(voice_mod.ENGINES)
    engines["fake"] = fake
    original = voice_mod.ENGINES
    voice_mod.ENGINES = engines
    try:
        used = voice_mod.synthesize("سلام", target, engine="fake")
    finally:
        voice_mod.ENGINES = original
    assert used == "fake"
    assert calls == ["سلام"]
    assert target.exists()


def test_synthesize_falls_back_when_engine_fails(tmp_path):
    target = tmp_path / "b.mp3"

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    def good(text, out, voice=None, **kwargs):
        Path(out).write_bytes(b"y" * 2000)

    engines = dict(voice_mod.ENGINES)
    engines["broken"] = broken
    engines["edge"] = good
    original = voice_mod.ENGINES
    voice_mod.ENGINES = engines
    try:
        used = voice_mod.synthesize("سلام", target, engine="broken")
    finally:
        voice_mod.ENGINES = original
    assert used == "edge", "must fall back to a working engine"


def test_synthesize_raises_when_all_fail(tmp_path):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    engines = dict(voice_mod.ENGINES)
    engines.update({"edge": broken, "google": broken, "broken": broken})
    original = voice_mod.ENGINES
    voice_mod.ENGINES = engines
    try:
        with pytest.raises(RuntimeError):
            voice_mod.synthesize("سلام", tmp_path / "c.mp3", engine="broken")
    finally:
        voice_mod.ENGINES = original
