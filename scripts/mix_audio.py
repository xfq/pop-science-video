#!/usr/bin/env python3
"""Mix narration, music and SFX with speech-triggered ducking; normalise to -16 LUFS.

  python3 scripts/mix_audio.py --project ./film
  python3 scripts/mix_audio.py --project ./film --duck-db 10 --target-lufs -16
"""
from __future__ import annotations

import argparse
import json
import math
import wave
from pathlib import Path

import numpy as np

from film_lib import integrated_loudness, loudnorm, read_json, write_json

SR = 48000
BLOCK = 480  # 10 ms


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as fh:
        channels = fh.getnchannels()
        width = fh.getsampwidth()
        rate = fh.getframerate()
        frames = fh.readframes(fh.getnframes())
    if width != 2:
        raise SystemExit(f"{path}: expected 16-bit PCM, got {width * 8}-bit")
    data = np.frombuffer(frames, dtype="<i2").astype(np.float64) / 32768.0
    if channels == 1:
        data = np.stack([data, data], axis=1)
    elif channels > 2:
        data = data.reshape(-1, channels)[:, :2]
    else:
        data = data.reshape(-1, 2)
    if rate != SR:
        raise SystemExit(f"{path}: expected {SR} Hz, got {rate}. Re-run tts.py / music.py.")
    return data


def write_wav(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.clip(audio, -1, 1)
    pcm = (audio * 32767).astype("<i2")
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes(pcm.tobytes())


def place(buf: np.ndarray, clip: np.ndarray, at: float, gain_db: float = 0.0) -> None:
    start = int(round(at * SR))
    if start >= buf.shape[0]:
        return
    n = min(clip.shape[0], buf.shape[0] - start)
    if n <= 1:
        return
    gain = 10 ** (gain_db / 20)
    ramp = min(int(0.008 * SR), n // 2)
    piece = clip[:n] * gain
    if ramp > 2:
        piece[:ramp] *= np.linspace(0, 1, ramp)[:, None]
        piece[-ramp:] *= np.linspace(1, 0, ramp)[:, None]
    buf[start:start + n] += piece


def duck_curve(voice: np.ndarray, duck_db: float) -> np.ndarray:
    mono = np.max(np.abs(voice), axis=1)
    n = mono.shape[0]
    blocks = int(math.ceil(n / BLOCK))
    padded = np.pad(mono, (0, blocks * BLOCK - n))
    rms = np.sqrt(np.mean(padded.reshape(blocks, BLOCK) ** 2, axis=1) + 1e-12)
    # Normalise the envelope so normal speech reaches ~1.
    ref = np.percentile(rms, 92) or rms.max() or 1.0
    env = np.clip(rms / ref, 0, 1)
    # Attack fast, release slow, at 100 Hz.
    smooth = np.zeros_like(env)
    acc = 0.0
    for i, value in enumerate(env):
        coeff = 0.55 if value > acc else 0.12
        acc = acc + (value - acc) * coeff
        smooth[i] = acc
    # A short pre-roll so the duck is already down on the first syllable.
    pre = 4
    smooth = np.maximum(smooth, np.roll(smooth, pre) * 0.85)
    x = np.arange(n)
    centers = np.arange(blocks) * BLOCK + BLOCK / 2
    curve = np.interp(x, centers, 10 ** (-duck_db * smooth / 20), left=1.0, right=1.0)
    return curve


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--timeline", type=Path)
    ap.add_argument("--music", type=Path)
    ap.add_argument("--sfx-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--duck-db", type=float, default=9.0)
    ap.add_argument("--music-db", type=float, default=-17.0)
    ap.add_argument("--sfx-db", type=float, default=-12.0)
    ap.add_argument("--target-lufs", type=float, default=-16.0)
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--no-sfx", action="store_true")
    ap.add_argument("--mute-voice", action="store_true", help="music/SFX only; keep captions and timing")
    args = ap.parse_args()

    project = args.project.expanduser().resolve()
    timeline = read_json(args.timeline or project / "timeline.json")
    if not timeline:
        raise SystemExit("timeline.json not found")
    total = float(timeline["duration"])
    n = int(math.ceil((total + 0.25) * SR))
    voice = np.zeros((n, 2), dtype=np.float64)
    placed = 0
    if not args.mute_voice:
        for scene in timeline["scenes"]:
            for chunk in scene.get("chunks", []):
                path = project / chunk.get("file", f"assets/tts/{chunk['id']}.wav")
                if not path.exists():
                    raise SystemExit(f"narration missing: {path}")
                clip = read_wav(path)
                place(voice, clip, float(chunk["start"]), 0.0)
                placed += 1
        if placed == 0:
            raise SystemExit("no narration chunks in timeline")
        peak = float(np.max(np.abs(voice))) or 1.0
        voice = voice / peak * (10 ** (-3.0 / 20))

    music = np.zeros_like(voice)
    music_path = args.music or project / "assets" / "music.wav"
    if not args.no_music:
        if not music_path.exists():
            raise SystemExit(f"music missing: {music_path}. Run scripts/music.py first.")
        m = read_wav(music_path)
        if m.shape[0] < n:
            m = np.pad(m, ((0, n - m.shape[0]), (0, 0)))
        music = m[:n] * (10 ** (args.music_db / 20))
        music *= duck_curve(voice, args.duck_db)[:, None]

    sfx_track = np.zeros_like(voice)
    cues = []
    if not args.no_sfx:
        sfx_dir = args.sfx_dir or project / "assets" / "sfx"
        if not sfx_dir.exists():
            raise SystemExit(f"sfx dir missing: {sfx_dir}. Run scripts/make_sfx.py first.")
        cache = {}
        def cue(name: str, at: float, gain_db: float, note: str = ""):
            if not name:
                return
            path = sfx_dir / f"{name}.wav"
            if not path.exists():
                return
            if name not in cache:
                cache[name] = read_wav(path)
            place(sfx_track, cache[name], at, args.sfx_db + gain_db)
            cues.append({"name": name, "at": round(at, 3), "note": note})

        for i, scene in enumerate(timeline["scenes"]):
            if i > 0:
                cue("whoosh", max(0.0, float(scene["start"]) - 0.10), -4.0, "scene transition")
            for item in scene.get("sfx", []) or []:
                if isinstance(item, str):
                    cue(item, float(scene["start"]), 0.0, "scene")
                elif isinstance(item, dict):
                    cue(item.get("name", ""), float(scene["start"]) + float(item.get("at", 0)), float(item.get("gain", 0)), "scene")
            for chunk in scene.get("chunks", []):
                if chunk.get("sfx"):
                    cue(str(chunk["sfx"]), float(chunk["start"]), 0.0, f"narration {chunk.get('id')}")

    mix = voice + music + sfx_track
    mix = mix[: int(total * SR)]
    if float(np.max(np.abs(mix))) < 1e-7:
        raise SystemExit("mix is silent: voice is muted and no music/SFX was added")
    # Keep headroom before the loudness pass; avoid hard clipping in the sum.
    peak = float(np.max(np.abs(mix))) or 1.0
    if peak > 0.98:
        mix *= 0.98 / peak

    scratch = project / "assets" / ".mix-raw.wav"
    write_wav(scratch, mix)
    out = args.out or project / "assets" / "mix.wav"
    measured = loudnorm(scratch, out, target_i=args.target_lufs, target_tp=-1.5)
    scratch.unlink(missing_ok=True)
    if not args.mute_voice:
        write_wav(project / "assets" / "voice.wav", voice[: int(total * SR)])
    lufs, true_peak = integrated_loudness(out)
    write_json(project / "evidence" / "audio-mix.json", {
        "file": str(out.relative_to(project)) if out.is_relative_to(project) else str(out),
        "duration": round(total, 3), "chunks": placed,
        "voice": "muted" if args.mute_voice else "narration",
        "music": None if args.no_music else {"file": str(music_path.relative_to(project)) if music_path.is_relative_to(project) else str(music_path), "gainDb": args.music_db, "duckDb": args.duck_db},
        "sfx": cues, "targetLufs": args.target_lufs, "measuredLufs": lufs, "truePeak": true_peak,
        "loudnorm": measured,
    })
    print(json.dumps({"out": str(out), "duration": round(total, 2), "lufs": lufs,
                      "truePeak": true_peak, "chunks": placed, "sfx": len(cues)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
