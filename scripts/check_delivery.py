#!/usr/bin/env python3
"""Verify the rendered MP4 and the delivery folder; never claims a human review happened.

  python3 scripts/check_delivery.py --project ./film --video ./film/renders/final.mp4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from film_lib import ffprobe_json, integrated_loudness, mean_volume, read_json, run, write_json


def first_frame_stats(video: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="cs-frame-") as td:
        frame = Path(td) / "first.png"
        run(["ffmpeg", "-v", "error", "-y", "-ss", "0", "-i", str(video), "-frames:v", "1", str(frame)])
        if not frame.exists():
            return {"ok": False, "reason": "could not extract first frame"}
        try:
            from PIL import Image, ImageStat
        except ImportError:
            return {"ok": True, "note": "Pillow not installed; first-frame stats skipped"}
        image = Image.open(frame).convert("L")
        stat = ImageStat.Stat(image)
        stddev = float(stat.stddev[0])
        mean = float(stat.mean[0])
        colors = len(image.convert("RGB").getcolors(maxcolors=2_000_000) or [])
        return {"ok": stddev >= 6.0 and colors > 40, "stddev": round(stddev, 2),
                "mean": round(mean, 2), "colors": colors}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--video", type=Path)
    ap.add_argument("--timeline", type=Path)
    ap.add_argument("--pre-render", action="store_true", help="check the project only, no MP4")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    project = args.project.expanduser().resolve()
    timeline = read_json(args.timeline or project / "timeline.json", {})
    build = read_json(project / "build-report.json", {})
    errors: list[str] = []
    warnings: list[str] = []
    info: dict = {"project": "."}

    for name in ("film.json", "timeline.json", "index.html", "assets/mix.wav"):
        if not (project / name).exists():
            errors.append(f"missing {name}")
    for name in ("DIRECTION.md", "SOURCES.md", "facts.json"):
        if not (project / name).exists():
            warnings.append(f"missing {name} (delivery provenance)")
    if not (project / "assets" / "fonts" / "NotoSansSC.woff2").exists():
        warnings.append("NotoSansSC.woff2 missing: CJK text may fall back on another machine")
    if build.get("estimatedTimeline"):
        errors.append("build used an estimated timeline; run TTS + make_timeline.py and rebuild")
    if build.get("audio") is None:
        errors.append("build has no audio track; run mix_audio.py and rebuild")

    video = (args.video or project / "renders" / "final.mp4").expanduser().resolve()
    info["video"] = str(video.relative_to(project)) if video.is_relative_to(project) else str(video)
    if args.pre_render or not video.exists():
        if not args.pre_render:
            errors.append(f"video missing: {video}")
        report = {"ok": not errors, "errors": errors, "warnings": warnings, "info": info}
        write_json(project / "evidence" / "delivery.json", report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=1))
        else:
            print("delivery check:", "passed (pre-render)" if not errors else "failed")
            for e in errors:
                print("ERROR  ", e)
            for w in warnings:
                print("warning", w)
        raise SystemExit(1 if errors else 0)

    probe = ffprobe_json(video)
    fmt = probe.get("format", {})
    streams = probe.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video_stream:
        errors.append("no video stream")
    else:
        width, height = int(video_stream.get("width", 0)), int(video_stream.get("height", 0))
        fps_txt = str(video_stream.get("avg_frame_rate", "0/1"))
        try:
            num, den = fps_txt.split("/")
            fps = float(num) / float(den)
        except Exception:
            fps = 0
        info.update({"width": width, "height": height, "fps": round(fps, 3),
                     "videoCodec": video_stream.get("codec_name")})
        if (width, height) != (1920, 1080):
            errors.append(f"expected 1920x1080, got {width}x{height}")
        if abs(fps - 30) > 0.2 and abs(fps - 24) > 0.2:
            warnings.append(f"frame rate is {fps:.2f}, not 30/24")
    info["audioCodec"] = audio_stream.get("codec_name") if audio_stream else None
    if not audio_stream:
        errors.append("no audio stream (the final MP4 would be silent)")

    duration = float(fmt.get("duration", 0))
    info["duration"] = round(duration, 3)
    expected = float(timeline.get("duration", 0)) if timeline else 0
    if expected and abs(duration - expected) > max(1.2, expected * 0.02):
        warnings.append(f"video is {duration:.2f}s but the timeline is {expected:.2f}s")

    lufs, peak = integrated_loudness(video)
    info.update({"lufs": lufs, "truePeak": peak})
    if lufs is not None and not (-20.0 <= lufs <= -11.0):
        warnings.append(f"integrated loudness {lufs:.1f} LUFS is outside the -20..-11 window")
    if peak is not None and peak > -0.2:
        warnings.append(f"true peak {peak:.1f} dBFS may clip")
    mv = mean_volume(video)
    info["meanVolume"] = mv
    if mv is not None and mv < -48:
        errors.append(f"audio is effectively silent (mean {mv:.1f} dB)")

    frame = first_frame_stats(video)
    info["firstFrame"] = frame
    if not frame.get("ok"):
        errors.append(f"first frame looks blank or broken: {frame}")

    captions = len((timeline or {}).get("captions", []))
    info["captions"] = captions
    if captions == 0:
        warnings.append("no captions in the timeline")

    report = {"ok": not errors, "errors": errors, "warnings": warnings, "info": info}
    write_json(project / "evidence" / "delivery.json", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f"delivery: {duration:.2f}s · {info.get('width')}x{info.get('height')} · "
              f"{info.get('videoCodec')}/{info.get('audioCodec')} · {lufs:.1f} LUFS" if lufs is not None
              else f"delivery: {duration:.2f}s")
        for e in errors:
            print("ERROR  ", e)
        for w in warnings:
            print("warning", w)
        print("delivery check passed" if not errors else "delivery check failed")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
