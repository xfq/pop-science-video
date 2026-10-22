#!/usr/bin/env python3
"""Small shared helpers for the CS explainer pipeline."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
CPS_ZH = 4.4
CPS_EN = 14.0


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(cmd, *, check=True, capture=True, cwd=None):
    result = subprocess.run(
        [str(x) for x in cmd],
        check=False,
        text=True,
        capture_output=capture,
        cwd=cwd,
    )
    if check and result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(map(str, cmd))}\n{message}")
    return result


def ffprobe_json(path: Path):
    out = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]).stdout
    return json.loads(out)


def duration(path: Path) -> float:
    return float(ffprobe_json(path)["format"]["duration"])


def split_caption(text: str, max_len: int = 26) -> list[str]:
    """Same rule as the JS builder: natural punctuation, then merge short pieces."""
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return []
    raw = re.findall(r"[^，。！？；：、!?;]+[，。！？；：、!?;]?", clean)
    merged: list[str] = []
    for part in raw:
        piece = part.strip()
        if not piece:
            continue
        if merged and len(merged[-1] + piece) <= max_len:
            merged[-1] += piece
        else:
            merged.append(piece)
    out: list[str] = []
    for piece in merged:
        if len(piece) <= max_len + 6:
            out.append(piece)
        else:
            out.extend(piece[i:i + max_len] for i in range(0, len(piece), max_len))
    return out


def cps_for(language: str) -> float:
    return CPS_EN if str(language or "").lower().startswith("en") else CPS_ZH


def estimate_timeline(film: dict) -> dict:
    """Text-length estimate; used before/without narration. Never mixes with measured audio."""
    cps = cps_for(film.get("meta", {}).get("language", "zh-CN"))
    meta = film.get("meta", {})
    scenes = []
    captions = []
    cursor = 0.0
    for index, scene in enumerate(film.get("scenes", [])):
        gap = 0.0 if index == 0 else float(scene.get("gap", meta.get("sceneGap", 0.02)))
        start = cursor + gap
        local = float(scene.get("lead", 0.15))
        marks: dict[str, float] = {}
        chunks = []
        for line in scene.get("narration", []):
            text = line.get("tts") or line.get("caption") or ""
            dur = max(1.1, len(re.sub(r"\s", "", text)) / cps + float(line.get("pause", 0.25)))
            if line.get("mark") and line["mark"] not in marks:
                marks[line["mark"]] = round(start + local + 0.04, 3)
            chunks.append({
                "caption": line.get("caption") or text,
                "text": text,
                "start": round(start + local, 3),
                "dur": round(dur, 3),
                "mark": line.get("mark"),
                "sfx": line.get("sfx"),
            })
            caption_text = line.get("caption") or text
            for piece in split_caption(caption_text):
                p_dur = max(0.9, dur * len(piece) / max(1, len(caption_text)))
                captions.append({"text": piece, "start": round(start + local, 3), "dur": round(p_dur, 3)})
            local += dur
        tail = float(scene.get("tail", meta.get("sceneTail", 0.7)))
        dur = max(float(scene.get("minDuration", 2.4)), local + tail)
        scenes.append({"id": scene["id"], "index": index, "start": round(start, 3),
                       "duration": round(dur, 3), "marks": marks, "chunks": chunks, "estimated": True})
        scene_end = start + dur - 0.08
        for cap in captions:
            if cap["start"] >= start and cap["start"] < scene_end:
                cap["dur"] = max(0.35, min(cap["dur"], scene_end - cap["start"]))
        cursor = start + dur
    return {"version": 1, "estimated": True, "duration": round(cursor, 3),
            "scenes": scenes, "captions": cap_captions(captions, cursor)}


def cap_captions(captions: list[dict], total: float) -> list[dict]:
    ordered = sorted((dict(c) for c in captions), key=lambda c: c["start"])
    for i, cap in enumerate(ordered):
        cap["start"] = max(0.0, cap["start"])
        nxt = ordered[i + 1] if i + 1 < len(ordered) else None
        cap["dur"] = max(0.5, min(cap["dur"], (nxt["start"] if nxt else total) - cap["start"] - 0.06))
        if cap["start"] + cap["dur"] > total:
            cap["dur"] = max(0.4, total - cap["start"] - 0.05)
        cap["start"] = round(cap["start"], 3)
        cap["dur"] = round(cap["dur"], 3)
    return ordered


def normalize_lexicon(text: str, lexicon: dict | None) -> str:
    if not lexicon:
        return text
    # One pass, longest first: replacing sequentially would re-replace digits inside
    # an earlier replacement ("IEEE 754" -> "I triple E 754" then "754" -> "七五四").
    pattern = re.compile("|".join(re.escape(k) for k in sorted(lexicon, key=len, reverse=True)))
    return pattern.sub(lambda m: str(lexicon[m.group(0)]), text)


def trim_silence(src: Path, dst: Path, sample_rate: int = 48000) -> None:
    """Convert to 48 kHz mono and remove leading/trailing room silence."""
    af = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
          "silenceremove=start_periods=1:start_threshold=-45dB,areverse")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", af,
         "-ar", str(sample_rate), "-ac", "1", "-c:a", "pcm_s16le", str(dst)])


def wav_seconds(path: Path) -> float:
    return duration(path)


def mean_volume(path: Path) -> float | None:
    result = run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                 check=False)
    match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", result.stderr or "")
    return float(match.group(1)) if match else None


def integrated_loudness(path: Path) -> tuple[float | None, float | None]:
    result = run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                 check=False)
    text = result.stderr or ""
    integrated = re.findall(r"I:\s*(-?[\d.]+) LUFS", text)
    true_peak = re.findall(r"Peak:\s*(-?[\d.]+) dBFS", text)
    return (float(integrated[-1]) if integrated else None,
            float(true_peak[-1]) if true_peak else None)


def loudnorm(src: Path, dst: Path, target_i: float = -16.0, target_tp: float = -1.5) -> dict:
    """Two-pass EBU R128 normalisation. Returns measured values from pass 1."""
    first = run(["ffmpeg", "-hide_banner", "-i", str(src), "-af",
                 f"loudnorm=I={target_i}:TP={target_tp}:LRA=11:print_format=json",
                 "-f", "null", "-"], check=False)
    blob = (first.stderr or "")
    start = blob.rfind("{")
    end = blob.rfind("}")
    measured = {}
    if start != -1 and end > start:
        try:
            measured = json.loads(blob[start:end + 1])
        except json.JSONDecodeError:
            measured = {}
    if measured:
        af = (f"loudnorm=I={target_i}:TP={target_tp}:LRA=11:"
              f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
              f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
              f"offset={measured.get('target_offset', 0)}:linear=true")
    else:
        af = f"loudnorm=I={target_i}:TP={target_tp}:LRA=11"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", af,
         "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(dst)])
    return measured


def which(name: str) -> str | None:
    return shutil.which(name)


def require_ffmpeg() -> None:
    for name in ("ffmpeg", "ffprobe"):
        if not which(name):
            raise SystemExit(f"{name} not found on PATH. Install FFmpeg, then re-run.")


def atomic_dir(path: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix=path.name + ".", dir=str(path.parent)))
    return tmp


def human_seconds(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    return f"{int(seconds // 60)}:{seconds % 60:05.2f}"


def safe_float(value, fallback=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def clamp(value, lo, hi):
    return max(lo, min(hi, value))
