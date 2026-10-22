#!/usr/bin/env python3
"""Generate the small original SFX set used by the template (no samples, no licence traps).

  python3 scripts/make_sfx.py --out ./film/assets/sfx
"""
from __future__ import annotations

import argparse
import math
import wave
from pathlib import Path

import numpy as np

SR = 48000


def wav(path: Path, audio: np.ndarray, peak_db: float = -10.0) -> None:
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = audio / peak * (10 ** (peak_db / 20))
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes(pcm.tobytes())


def t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def click(duration=0.035, freq=1900) -> np.ndarray:
    x = t(duration)
    env = np.exp(-x * 140)
    tone = np.sin(2 * np.pi * freq * x) * 0.6
    noise = np.random.default_rng(11).normal(0, 0.4, len(x)) * np.exp(-x * 220)
    return (tone + noise) * env


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("assets/sfx"))
    args = ap.parse_args()
    out = args.out.expanduser().resolve()
    rng = np.random.default_rng(2026)

    # tick — a dry UI tick
    wav(out / "tick.wav", click(0.04, 2200))

    # pop — a rounded UI pop
    x = t(0.16)
    freq = 220 + 700 * np.exp(-x * 26)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    pop = np.sin(phase) * np.exp(-x * 24)
    pop[: int(0.004 * SR)] += click(0.004, 2400)[: int(0.004 * SR)] * 0.3
    wav(out / "pop.wav", pop)

    # whoosh — transition air
    x = t(0.65)
    env = np.minimum(1, x / 0.12) * np.exp(-np.maximum(0, x - 0.18) * 5.2)
    n = rng.normal(0, 1, len(x))
    smooth = np.convolve(n, np.ones(9) / 9, mode="same")
    bright = n - smooth
    sweep = np.concatenate([np.linspace(0.1, 1, len(x) // 2), np.linspace(1, 0.25, len(x) - len(x) // 2)])
    w = (bright * 0.55 + smooth * 0.45) * env * sweep
    wav(out / "whoosh.wav", w, -14)

    # chime — positive confirmation
    x = t(1.1)
    chime = (np.sin(2 * np.pi * 880 * x) * 0.55 + np.sin(2 * np.pi * 1320 * x) * 0.3 +
             np.sin(2 * np.pi * 1760 * x) * 0.12) * np.exp(-x * 4.2)
    chime[: int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
    wav(out / "chime.wav", chime, -12)

    # error — a soft denial, not a cartoon buzzer
    x = t(0.34)
    buzz = (np.sign(np.sin(2 * np.pi * 150 * x)) * 0.35 + np.sin(2 * np.pi * 103 * x) * 0.4)
    buzz *= (0.55 + 0.45 * np.sin(2 * np.pi * 18 * x)) * np.exp(-x * 3)
    wav(out / "error.wav", buzz, -14)

    # typing — a short burst of key clicks
    total = np.zeros(int(0.42 * SR))
    for at in (0.0, 0.075, 0.14, 0.23, 0.29):
        c = click(0.025, 1500 + rng.integers(-180, 220))
        start = int(at * SR)
        total[start:start + len(c)] += c * (0.65 + 0.35 * rng.random())
    wav(out / "typing.wav", total, -14)

    # riser — a short build for a reveal
    x = t(1.5)
    env = np.minimum(1, x / 0.4) ** 1.6
    n = rng.normal(0, 1, len(x))
    air = n - np.convolve(n, np.ones(14) / 14, mode="same")
    tone = np.sin(2 * np.pi * np.cumsum(220 + 1100 * (x / x[-1]) ** 1.5) / SR)
    wav(out / "riser.wav", (air * 0.6 + tone * 0.35) * env, -15)

    # stamp — a low, decisive thud
    x = t(0.22)
    thud = np.sin(2 * np.pi * np.cumsum(70 + 60 * np.exp(-x * 30)) / SR) * np.exp(-x * 14)
    wav(out / "stamp.wav", thud, -10)

    (out / "SOURCE.md").write_text(
        "# SFX\n\nThese WAVs are original numpy synthesis from `scripts/make_sfx.py`.\n"
        "No third-party samples. Regenerate with:\n\n```sh\npython3 scripts/make_sfx.py --out ./assets/sfx\n```\n",
        encoding="utf-8",
    )
    print(f"wrote 8 SFX to {out}")


if __name__ == "__main__":
    main()
