"""Generate an original sports background bed (no copyright, no downloads).

    python scripts/make_music.py                 # -> assets/music/tooop-sports-bed.wav

Everything is synthesised from oscillators/noise, so the result is 100% original:
you can monetise it and no Content-ID claim can match it.

Style: 128 BPM, D-minor "heroic" loop, punchy kick, snare on 2 & 4, 8th hats,
side-chained bass, and an arpeggio that opens up in the second half.
"""

from __future__ import annotations

import argparse
import math
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 128.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT


def _t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def env(n: int, attack: float, curve: float = 2.0) -> np.ndarray:
    """Attack + exponential-ish decay envelope with `n` samples."""
    a = max(1, int(attack * SR))
    a = min(a, n)
    decay = np.linspace(1, 0, n - a) ** curve if n > a else np.array([])
    return np.concatenate([np.linspace(0, 1, a, endpoint=False), decay])[:n]


def kick(dur: float = 0.30) -> np.ndarray:
    t = _t(dur)
    freq = 118 * np.exp(-t * 22) + 44
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    click = np.exp(-t * 260) * 0.30 * np.random.default_rng(7).standard_normal(t.size)
    return (body * np.exp(-t * 7.5) + click) * 0.95


def snare(dur: float = 0.22) -> np.ndarray:
    t = _t(dur)
    noise = np.random.default_rng(3).standard_normal(t.size)
    noise = np.diff(noise, prepend=0.0)              # cheap high-pass
    tone = np.sin(2 * np.pi * 185 * t) * 0.35
    return (noise * 0.5 + tone) * np.exp(-t * 26)


def hat(dur: float = 0.05, open_hat: bool = False) -> np.ndarray:
    t = _t(dur * (4 if open_hat else 1))
    noise = np.diff(np.random.default_rng(11).standard_normal(t.size), prepend=0.0)
    return noise * np.exp(-t * (55 if open_hat else 210)) * 0.30


def saw(freq: float, dur: float, harmonics: int = 12) -> np.ndarray:
    t = _t(dur)
    out = np.zeros_like(t)
    for h in range(1, harmonics + 1):
        if freq * h > SR / 2.2:
            break
        out += np.sin(2 * np.pi * freq * h * t) / h
    return out * 0.5


def lowpass(sig: np.ndarray, cutoff: float) -> np.ndarray:
    """One-pole low-pass filter."""
    alpha = math.exp(-2 * math.pi * cutoff / SR)
    out = np.empty_like(sig)
    prev = 0.0
    for i, x in enumerate(sig):
        prev = (1 - alpha) * x + alpha * prev
        out[i] = prev
    return out


NOTE_NAMES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
              "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def note(name: str) -> float:
    pitch, octave = name[:-1], int(name[-1])
    midi = 12 * (octave + 1) + NOTE_NAMES[pitch]
    return 440.0 * 2 ** ((midi - 69) / 12)


# D-minor heroic progression: Dm - Bb - F - C (two bars each)
PROGRESSION = [
    ("D3", ["D3", "F3", "A3"]),
    ("D3", ["D3", "F3", "A3"]),
    ("A#2", ["A#2", "D3", "F3"]),
    ("A#2", ["A#2", "D3", "F3"]),
    ("F3", ["F3", "A3", "C4"]),
    ("F3", ["F3", "A3", "C4"]),
    ("C3", ["C3", "E3", "G3"]),
    ("C3", ["C3", "E3", "G3"]),
]


def build(bars: int = 16) -> np.ndarray:
    total = bars * BAR + 0.5
    mix = np.zeros(int(total * SR))
    kick_env = np.zeros_like(mix)

    def place(sig: np.ndarray, at: float, gain: float = 1.0) -> None:
        start = int(at * SR)
        if start >= mix.size:
            return
        end = min(mix.size, start + sig.size)
        mix[start:end] += sig[: end - start] * gain

    for bar in range(bars):
        bar_start = bar * BAR
        root, tones = PROGRESSION[bar % len(PROGRESSION)]
        half = bar >= bars // 2                     # second half = more energy

        for beat_index in range(4):
            at = bar_start + beat_index * BEAT
            if beat_index in (0, 2):
                k = kick()
                place(k, at, 1.0)
                start = int(at * SR)
                end = min(mix.size, start + k.size)
                kick_env[start:end] = np.maximum(kick_env[start:end], np.abs(k[: end - start]))
            if beat_index in {1, 3}:
                place(snare(), at, 0.5)
            for eighth in (0.0, 0.5):
                open_hat = half and eighth == 0.5 and bar % 4 == 3
                place(hat(open_hat=open_hat), at + eighth * BEAT, 0.45)

        for step in range(8):                        # bass on 8ths
            at = bar_start + step * BEAT / 2
            freq = note(root) * (2 if step % 4 == 3 else 1)
            sig = lowpass(saw(freq, BEAT / 2 * 0.9, harmonics=8), 320)
            place(sig * env(sig.size, 0.004, 1.7), at, 0.55)

        if half:                                     # arpeggio for lift
            for step in range(16):
                at = bar_start + step * BEAT / 4
                freq = note(tones[step % len(tones)]) * 2
                sig = saw(freq, BEAT / 4 * 0.8, harmonics=6)
                place(sig * env(sig.size, 0.003, 2.4), at, 0.20)

        for tone in tones:                           # soft pad for width
            freq = note(tone)
            sig = lowpass(saw(freq, BAR * 0.98, harmonics=5), 900)
            place(sig * env(sig.size, 0.12, 0.4) * 0.10, bar_start, 0.55)

    # side-chain: duck the music on every kick (modern sports-trailer pump)
    duck = 1.0 - 0.55 * np.clip(kick_env * 6, 0, 1)
    mix = mix * duck
    mix = np.tanh(mix * 1.15)                        # gentle saturation/limit
    peak = float(np.max(np.abs(mix)) or 1.0)
    return mix / peak * 0.85


def write_wav(path: Path, mono: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    right = np.concatenate([np.zeros(int(0.012 * SR)), mono])[: mono.size] * 0.98
    stereo = np.clip(np.stack([mono, right], axis=1), -1, 1)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes((stereo * 32767).astype("<i2").tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description="make an original royalty-free sports bed")
    parser.add_argument("--bars", type=int, default=16, help="16 bars ≈ 30s at 128 BPM")
    parser.add_argument("--out", default="assets/music/tooop-sports-bed.wav")
    args = parser.parse_args()

    print("composing… (10-20 seconds)")
    audio = build(bars=args.bars)
    path = Path(args.out)
    write_wav(path, audio)
    print(f"done: {path}  ({audio.size / SR:.1f}s, {path.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
