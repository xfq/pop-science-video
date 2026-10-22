#!/usr/bin/env python3
"""Write an original, deterministic music bed for the film. No samples, no model.

  python3 scripts/music.py --project ./film --mood curious
  python3 scripts/music.py --project ./film --mood focused --bpm 84 --seed 7
"""
from __future__ import annotations

import argparse
import json
import math
import wave
from pathlib import Path

import numpy as np

from film_lib import integrated_loudness, read_json, write_json

SR = 48000
MOODS = {
    "curious": {
        "bpm": 92,
        "progression": [(45, "min"), (41, "maj"), (48, "maj"), (43, "maj")],  # Am F C G
        "arp": 0.26, "pad": 0.55, "bass": 0.42, "kick": 0.36, "hat": 0.10, "swing": 0.0,
    },
    "focused": {
        "bpm": 84,
        "progression": [(50, "min"), (46, "maj"), (41, "maj"), (48, "maj")],  # Dm Bb F C
        "arp": 0.16, "pad": 0.68, "bass": 0.38, "kick": 0.30, "hat": 0.06, "swing": 0.0,
    },
    "playful": {
        "bpm": 108,
        "progression": [(48, "maj"), (43, "maj"), (45, "min"), (41, "maj")],  # C G Am F
        "arp": 0.32, "pad": 0.42, "bass": 0.46, "kick": 0.40, "hat": 0.14, "swing": 0.02,
    },
    "tense": {
        "bpm": 100,
        "progression": [(40, "min"), (48, "maj"), (45, "min"), (47, "maj")],  # Em C Am B
        "arp": 0.12, "pad": 0.62, "bass": 0.5, "kick": 0.32, "hat": 0.04, "swing": 0.0,
    },
}
QUALITY = {"min": (0, 3, 7, 10), "maj": (0, 4, 7, 11)}


def midi(note: int) -> float:
    return 440.0 * (2 ** ((note - 69) / 12))


def env_ar(n: int, attack: float, release: float) -> np.ndarray:
    n = max(1, n)
    a = min(n, max(1, int(attack * SR)))
    r = min(n, max(1, int(release * SR)))
    out = np.ones(n, dtype=np.float64)
    out[:a] = np.linspace(0, 1, a) ** 1.4
    out[-r:] *= np.linspace(1, 0, r) ** 1.6
    return out


def add_note(buf: np.ndarray, at: float, dur: float, freq: float, gain: float, timbre: str = "pad") -> None:
    start = int(at * SR)
    if start >= buf.shape[0]:
        return
    n = min(int(dur * SR), buf.shape[0] - start)
    if n <= 2:
        return
    t = np.arange(n, dtype=np.float64) / SR
    if timbre == "pad":
        wave = (0.62 * np.sin(2 * np.pi * freq * t)
                + 0.24 * np.sin(2 * np.pi * freq * 2.001 * t)
                + 0.10 * np.sin(2 * np.pi * freq * 3.002 * t))
        wave *= env_ar(n, 0.45, 0.5)
    elif timbre == "pluck":
        wave = (0.7 * np.sin(2 * np.pi * freq * t)
                + 0.2 * np.sin(2 * np.pi * freq * 2.0 * t)
                + 0.08 * np.sin(2 * np.pi * freq * 3.01 * t))
        wave *= np.exp(-t * 5.2)
        wave[: min(n, int(0.006 * SR))] *= np.linspace(0, 1, min(n, int(0.006 * SR)))
    elif timbre == "bass":
        wave = (0.8 * np.sin(2 * np.pi * freq * t)
                + 0.18 * np.sin(2 * np.pi * freq * 2 * t))
        wave = np.tanh(wave * 1.15) * 0.9
        wave *= env_ar(n, 0.02, 0.15)
    else:
        wave = np.sin(2 * np.pi * freq * t)
        wave *= np.exp(-t * 3)
    buf[start:start + n] += wave * gain


def build(duration: float, mood: str, bpm: int, seed: int) -> np.ndarray:
    cfg = MOODS.get(mood, MOODS["curious"])
    bpm = int(bpm or cfg["bpm"])
    beat = 60.0 / bpm
    bar = 4 * beat
    n = int((duration + 2.0) * SR)
    pad = np.zeros((n, 2), dtype=np.float64)
    arp = np.zeros((n, 2), dtype=np.float64)
    bass = np.zeros(n, dtype=np.float64)
    drums = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(seed)
    bars = int(math.ceil((duration + 0.5) / bar))
    for b in range(bars):
        root, quality = cfg["progression"][b % len(cfg["progression"])]
        chord = [root + x for x in QUALITY[quality]]
        at = b * bar
        # Pad: open voicing, one octave up, detuned per channel.
        for j, note in enumerate([chord[0] + 12, chord[2] + 12, chord[1] + 24]):
            f = midi(note)
            add_note(pad[:, 0], at, bar * 1.05, f * 0.999, cfg["pad"] * (0.9 if j else 1.0) / 3)
            add_note(pad[:, 1], at, bar * 1.05, f * 1.001, cfg["pad"] * 0.9 / 3)
        # Bass on 1 and 3.
        for off in (0, 2 * beat):
            add_note(bass, at + off, beat * 0.92, midi(chord[0] - 12), cfg["bass"], "bass")
        # Plucked arpeggio on eighths, with a small deterministic variation.
        pattern = [0, 2, 1, 3, 2, 1, 3, 0]
        for k in range(8):
            note = chord[pattern[k]] + (24 if k in (3, 6) else 12)
            when = at + k * beat / 2 + (cfg["swing"] if k % 2 else 0)
            pan = 0.5 + 0.12 * math.sin((b * 8 + k) * 1.7)
            gain = cfg["arp"] * (0.7 if k % 2 else 1.0) * (0.8 + 0.2 * rng.random())
            start = int(when * SR)
            if start >= n:
                continue
            tmp = np.zeros((max(1, n - start), 2), dtype=np.float64)
            add_note(tmp[:, 0], 0, beat * 0.55, midi(note) * 0.999, gain * (1 - pan))
            add_note(tmp[:, 1], 0, beat * 0.55, midi(note) * 1.001, gain * pan)
            arp[start:start + tmp.shape[0]] += tmp[: n - start]
        # Kick on 1 and 3; hat on offbeats.
        for off in (0, 2 * beat):
            start = int((at + off) * SR)
            if start >= n:
                continue
            t = np.arange(min(int(0.30 * SR), n - start)) / SR
            kick = np.sin(2 * np.pi * np.cumsum(45 + 85 * np.exp(-t * 26)) / SR) * np.exp(-t * 11)
            drums[start:start + len(kick)] += kick * cfg["kick"]
        for k in range(8):
            start = int((at + k * beat / 2 + beat / 4) * SR)
            if start >= n:
                continue
            m = min(int(0.055 * SR), n - start)
            noise = rng.normal(0, 1, m)
            noise = noise - np.convolve(noise, np.ones(6) / 6, mode="same")
            drums[start:start + m] += noise * np.exp(-np.arange(m) / SR * 85) * cfg["hat"] * 0.35
    # Ping-pong delay on the arp.
    delay = int(0.28 * SR)
    arp[delay:] += arp[:-delay] * 0.18
    arp[2 * delay:] += arp[:-2 * delay] * 0.07
    # Sidechain the pad and bass against the kick.
    t = np.arange(n) / SR
    side = np.ones(n)
    for b in range(bars):
        for off in (0, 2 * beat):
            start = int((b * bar + off) * SR)
            m = min(int(0.32 * SR), n - start)
            if m > 0:
                side[start:start + m] *= 1 - 0.22 * np.exp(-np.arange(m) / SR * 12)
    pad *= side[:, None]
    bass *= side
    # Gentle noise floor and fade.
    bed = rng.normal(0, 0.0008, n)
    mix = pad + arp + bass[:, None] + drums[:, None] + bed[:, None]
    fade_in = int(1.4 * SR)
    fade_out = min(int(2.6 * SR), n)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None] ** 1.2
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = mix / peak * 0.72
    return mix[: int(duration * SR)]


def write_wav(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(audio, -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes(pcm.tobytes())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--timeline", type=Path)
    ap.add_argument("--mood", choices=sorted(MOODS), default="curious")
    ap.add_argument("--bpm", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7418)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--duration", type=float)
    args = ap.parse_args()
    project = args.project.expanduser().resolve()
    timeline = read_json(args.timeline or project / "timeline.json")
    if not timeline:
        raise SystemExit("timeline.json not found; run scripts/make_timeline.py first")
    duration = float(args.duration or timeline["duration"])
    audio = build(duration, args.mood, args.bpm, args.seed)
    out = args.out or project / "assets" / "music.wav"
    write_wav(out, audio)
    lufs, peak = integrated_loudness(out)
    write_json(project / "evidence" / "music.json", {
        "file": str(out.relative_to(project)) if out.is_relative_to(project) else str(out),
        "duration": round(duration, 3), "mood": args.mood, "bpm": args.bpm or MOODS[args.mood]["bpm"],
        "seed": args.seed, "source": "original numpy synthesis", "lufs": lufs, "truePeak": peak,
    })
    print(json.dumps({"file": str(out), "duration": round(duration, 2), "mood": args.mood,
                      "bpm": args.bpm or MOODS[args.mood]["bpm"], "lufs": lufs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
