"""Procedural score and sound design for KAIRO Episode 01.

The cue sheet follows the film's acts, so the music always serves the story:

    00:00-01:00  modern room   warm low pad, sparse piano, slow clock tick
    00:48-01:12  memory        pad dissolves into wind, warm string swell
    01:00-02:00  savanna       wind, insects, distant wildlife, low drone
    02:00-02:36  chase         driving low percussion, running bed
    02:24-03:24  cave          deep sub drone, stone echoes, water drips
    03:24-04:48  mystery/map   harmonic shimmer, restrained chimes
    04:48-05:00  resolution    one dramatic accent, then decay to silence

Everything is synthesised with numpy so the project needs no third-party
audio assets and the bed is exactly 300.000 s long.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from . import screenplay
from .config import SAMPLE_RATE

SR = SAMPLE_RATE
DURATION = 300.0
OUT_PATH = screenplay.ROOT / "audio" / "music" / "score.wav"
N = int(SR * DURATION)


def _t(dur: float) -> np.ndarray:
    return np.arange(int(SR * dur), dtype=np.float32) / SR


def _env(n: int, attack: float, release: float) -> np.ndarray:
    a = min(max(1, int(SR * attack)), n)
    r = min(max(1, int(SR * release)), n)
    env = np.ones(n, dtype=np.float32)
    env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    env[-r:] *= np.linspace(1, 0, r, dtype=np.float32)
    return env


def add(buf: np.ndarray, start: float, sig: np.ndarray, gain: float = 1.0) -> None:
    i = int(start * SR)
    if i >= buf.size:
        return
    j = min(buf.size, i + sig.size)
    buf[i:j] += sig[: j - i] * gain


def tone(freq: float, dur: float, amp: float, attack: float = 0.8,
         release: float = 1.2, vibrato: float = 0.0) -> np.ndarray:
    t = _t(dur)
    phase = 2 * np.pi * freq * t
    if vibrato:
        phase = phase + vibrato * np.sin(2 * np.pi * 0.21 * t)
    # two soft partials: warm pad instead of a buzzy sine stack
    sig = np.sin(phase) + 0.18 * np.sin(2 * phase) + 0.07 * np.sin(3 * phase)
    return (sig * _env(sig.size, attack, release) * amp).astype(np.float32)


def fast_noise(dur: float, amp: float, cutoff: float = 0.02,
               lfo_hz: float = 0.0, lfo_depth: float = 0.0,
               seed: int = 0) -> np.ndarray:
    """Spectrally shaped noise: wind, air, room tone, ticks."""
    rng = np.random.default_rng(seed)
    n = int(SR * dur)
    raw = rng.standard_normal(n).astype(np.float32)
    spec = np.fft.rfft(raw)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    cutoff_hz = max(cutoff * SR, 1.0)
    spec *= 1.0 / (1.0 + (freqs / cutoff_hz) ** 2)
    out = np.fft.irfft(spec, n).astype(np.float32)
    out /= (np.max(np.abs(out)) + 1e-9)
    if lfo_hz:
        t = _t(dur)
        out *= (1.0 + lfo_depth * np.sin(2 * np.pi * lfo_hz * t)).astype(np.float32)
    return out * amp


def pluck(freq: float, dur: float, amp: float) -> np.ndarray:
    t = _t(dur)
    sig = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
    return (sig * np.exp(-t * 3.2) * amp).astype(np.float32)


def thump(freq: float, dur: float, amp: float) -> np.ndarray:
    t = _t(dur)
    sig = np.sin(2 * np.pi * freq * t * (1 - 0.35 * t))
    return (sig * np.exp(-t * 9.0) * amp).astype(np.float32)


def bell(freq: float, dur: float, amp: float) -> np.ndarray:
    t = _t(dur)
    sig = (np.sin(2 * np.pi * freq * t)
           + 0.5 * np.sin(2 * np.pi * freq * 2.76 * t)
           + 0.25 * np.sin(2 * np.pi * freq * 5.4 * t))
    return (sig * np.exp(-t * 2.4) * amp).astype(np.float32)


def reverb(sig: np.ndarray, decay: float = 0.32) -> np.ndarray:
    out = sig.copy()
    for delay_s, gain in ((0.061, decay), (0.113, decay * 0.6),
                          (0.179, decay * 0.35)):
        d = int(delay_s * SR)
        out[d:] += sig[:-d] * gain
    return out


def build(force: bool = False) -> Path:
    if OUT_PATH.exists() and not force:
        return OUT_PATH
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    dry = np.zeros(N, dtype=np.float32)
    wet = np.zeros(N, dtype=np.float32)

    # ------------------------------------------------------------- present
    # warm low pad: D2 / A2 / F3 add9, very slow swell under the narration
    for f, g in ((73.42, 0.20), (110.00, 0.14), (174.61, 0.07), (329.63, 0.025)):
        add(dry, 0.0, tone(f, 62.0, g, attack=2.5, release=6.0))
    # sparse piano-like plucks, roughly one per scene beat
    for start, f in ((2.0, 587.33), (9.0, 440.00), (15.5, 523.25),
                     (22.0, 392.00), (28.5, 440.00), (34.0, 349.23),
                     (41.0, 293.66), (46.5, 261.63)):
        add(dry, start, pluck(f, 2.4, 0.07))
    # slow clock tick in the modern room, and once more at the very end
    for start in list(np.arange(0.5, 47.0, 1.0)) + [295.0]:
        add(dry, float(start), fast_noise(0.012, 0.05, cutoff=0.35, seed=7))

    # -------------------------------------------------------------- memory
    add(dry, 48.0, tone(146.83, 14.0, 0.10, attack=3.0, release=6.0))

    # ------------------------------------------------------------- savanna
    add(dry, 60.0, fast_noise(84.0, 0.16, cutoff=0.012, lfo_hz=0.11,
                              lfo_depth=0.55, seed=11))
    add(dry, 60.0, fast_noise(84.0, 0.07, cutoff=0.03, lfo_hz=0.07,
                              lfo_depth=0.40, seed=12))
    rng = np.random.default_rng(3)
    for start in np.sort(rng.uniform(61.0, 118.0, 14)):
        add(dry, float(start), pluck(float(rng.uniform(1400, 2600)), 0.22, 0.018))
    for f, g in ((98.00, 0.10), (146.83, 0.06), (196.00, 0.03)):
        add(dry, 60.0, tone(f, 72.0, g, attack=4.0, release=6.0))

    # --------------------------------------------------------------- chase
    # 02:00-02:36 driving low percussion under the run to the cave
    t = 120.0
    while t < 156.0:
        add(dry, t, thump(62.0, 0.5, 0.30))
        add(dry, t + 0.14, thump(48.0, 0.35, 0.16))
        t += 0.36
    add(dry, 120.0, fast_noise(36.0, 0.09, cutoff=0.02, seed=21))

    # ---------------------------------------------------------------- cave
    for f, g in ((36.71, 0.22), (55.00, 0.10), (82.41, 0.05), (110.00, 0.03)):
        add(dry, 144.0, tone(f, 62.0, g, attack=5.0, release=8.0))
    add(wet, 144.0, fast_noise(62.0, 0.05, cutoff=0.006, lfo_hz=0.05,
                               lfo_depth=0.30, seed=31))
    rng = np.random.default_rng(9)
    for start in np.sort(rng.uniform(146.0, 202.0, 22)):
        add(wet, float(start), bell(float(rng.uniform(760, 1500)), 0.7, 0.035))

    # ----------------------------------------------------------- map / awe
    for i, (f, g) in enumerate(((220.00, 0.045), (261.63, 0.038),
                                (329.63, 0.030), (493.88, 0.020))):
        add(wet, 204.0 + i * 1.5, tone(f, 82.0, g, attack=8.0,
                                       release=10.0, vibrato=0.4))
    add(wet, 252.0, bell(523.25, 3.0, 0.10))      # the touch
    add(wet, 264.0, bell(659.25, 3.5, 0.13))      # the illuminated point
    add(wet, 276.0, bell(392.00, 3.0, 0.08))      # the decision
    add(dry, 240.0, fast_noise(48.0, 0.04, cutoff=0.01, seed=44))

    # ---------------------------------------------------------- resolution
    for f, g in ((73.42, 0.18), (110.00, 0.12), (146.83, 0.08),
                 (185.00, 0.05), (293.66, 0.03)):
        add(dry, 288.0, tone(f, 13.0, g, attack=1.2, release=4.5))
    add(dry, 292.4, thump(58.0, 1.2, 0.22))            # dramatic accent
    add(wet, 292.4, bell(146.83, 4.0, 0.10))
    add(dry, 288.0, fast_noise(12.0, 0.03, cutoff=0.008, seed=55))

    mix = dry + reverb(wet, 0.34)
    mix *= _env(mix.size, 0.6, 2.0)                    # fade in / fade out
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak) * 0.42                          # leaves headroom for VO

    # stereo width: 12 ms decorrelation on the right channel
    delay = int(0.012 * SR)
    left = mix
    right = np.concatenate([np.zeros(delay, dtype=np.float32), mix[:-delay]])
    pcm = np.clip(np.stack([left, right], axis=1), -1.0, 1.0)
    pcm16 = (pcm * 32767).astype("<i2")

    with wave.open(str(OUT_PATH), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm16.tobytes())
    return OUT_PATH

