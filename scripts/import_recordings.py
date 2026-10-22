#!/usr/bin/env python3
"""Import human (or externally generated) takes and rebuild the narration manifest.

Put one file per line in recording/takes/, named like `hook-000.wav` (also accepts
`01-hook-000`, `hook_000`, `.m4a`, `.mp3`, `.aiff`, `.flac`, `.ogg`, `.mp4`).
The importer trims silence, high-passes rumble, peak-normalises to -3 dBFS, measures
duration, and writes assets/tts/manifest.json for make_timeline.py.

  python3 scripts/import_recordings.py --project ./film
  python3 scripts/import_recordings.py --project ./film --dir ./my-takes --force
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

from film_lib import duration, estimate_timeline, read_json, run, write_json

AUDIO_EXT = {".wav", ".m4a", ".mp3", ".aiff", ".aif", ".flac", ".ogg", ".opus", ".mp4", ".aac"}


def normalise_stem(stem: str) -> str:
    return re.sub(r"[\s_]+", "-", stem.strip().lower())


def discover_takes(folder: Path, scene_ids: list[str]) -> tuple[dict[str, Path], list[str]]:
    """Map line id -> path. Accepts hook-000, 01-hook-000, hook_0, etc."""
    found: dict[str, Path] = {}
    duplicates: list[str] = []
    if not folder.exists():
        return found, duplicates
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXT or path.name.startswith("."):
            continue
        stem = normalise_stem(path.stem)
        best = None
        for scene in sorted(scene_ids, key=len, reverse=True):
            pattern = re.compile(rf"(?:^|-){re.escape(scene)}-(\d{{1,3}})$")
            match = pattern.search(stem)
            if match:
                best = (scene, int(match.group(1)))
                break
        if not best:
            continue
        line_id = f"{best[0]}-{best[1]:03d}"
        if line_id in found:
            duplicates.append(f"{line_id}: {found[line_id].name} / {path.name}")
            continue
        found[line_id] = path
    return found, duplicates


def sha_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()[:16]


def peak_db(path: Path) -> float | None:
    result = run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                 check=False)
    match = re.search(r"max_volume:\s*(-?[\d.]+) dB", result.stderr or "")
    return float(match.group(1)) if match else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--dir", type=Path, help="default <project>/recording/takes")
    ap.add_argument("--manifest", type=Path, help="default <project>/assets/tts/manifest.json")
    ap.add_argument("--voice-name", default="human", help="label stored in the manifest")
    ap.add_argument("--force", action="store_true", help="re-process every take")
    ap.add_argument("--allow-missing", action="store_true", help="keep old chunks for lines without a take")
    ap.add_argument("--no-normalize", action="store_true", help="keep the recorded level (still peak-safe)")
    ap.add_argument("--denoise", action="store_true", help="apply light afftdn; can dull the voice")
    ap.add_argument("--highpass", type=int, default=70, help="high-pass frequency in Hz (default 70)")
    ap.add_argument("--trim-db", type=float, default=-50.0, help="silence threshold for trim (default -50 dB)")
    ap.add_argument("--target-peak", type=float, default=-3.0, help="per-line peak after normalize (default -3 dBFS)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    project = args.project.expanduser().resolve()
    film = read_json(project / "film.json")
    if not film:
        raise SystemExit("film.json not found")
    timeline = read_json(project / "timeline.json", {}) or estimate_timeline(film)
    old = read_json(args.manifest or project / "assets" / "tts" / "manifest.json", {}) or {}
    old_by_id = {c["id"]: c for c in old.get("chunks", [])}
    takes_dir = (args.dir or project / "recording" / "takes").expanduser().resolve()
    out_dir = project / "assets" / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for scene in film.get("scenes", []):
        for i, line in enumerate(scene.get("narration", [])):
            rows.append({
                "id": f"{scene['id']}-{i:03d}", "scene": scene["id"], "i": i,
                "text": line.get("tts") or line.get("caption") or "",
                "caption": line.get("caption") or line.get("tts") or "",
            })
    scene_ids = [s["id"] for s in film.get("scenes", [])]
    takes, duplicates = discover_takes(takes_dir, scene_ids)
    missing = [r for r in rows if r["id"] not in takes]

    if args.dry_run:
        print(json.dumps({"takes": len(takes), "expected": len(rows), "missing": [r["id"] for r in missing],
                          "duplicates": duplicates}, ensure_ascii=False, indent=1))
        return
    if missing and not args.allow_missing:
        preview = "\n".join(f"  {r['id']}: {takes_dir / (r['id'] + '.wav')}" for r in missing[:12])
        raise SystemExit(f"missing {len(missing)} take(s) in {takes_dir}:\n{preview}\n"
                         f"Record them, or pass --allow-missing to keep TTS for those lines.")
    if not takes:
        raise SystemExit(f"no takes found in {takes_dir}")

    chunks = []
    report_lines = []
    warnings = []
    speech_total = 0.0
    target_total = sum(float(c.get("dur", 0)) for s in timeline.get("scenes", []) for c in s.get("chunks", []))
    for row in rows:
        src = takes.get(row["id"])
        old_chunk = old_by_id.get(row["id"])
        target = project / "assets" / "tts" / f"{row['id']}.wav"
        if not src:
            if old_chunk and (project / old_chunk["file"]).exists():
                chunks.append(old_chunk)
                warnings.append(f"{row['id']}: no take; kept old {old_chunk.get('provider', 'unknown')} chunk")
                speech_total += float(old_chunk.get("dur", 0))
            continue

        settings = f"hp{args.highpass}|trim{args.trim_db}|norm{args.target_peak}|denoise{int(args.denoise)}"
        key = sha_file(src) + "-" + hashlib.sha1(settings.encode()).hexdigest()[:8]
        if not args.force and old_chunk and old_chunk.get("key") == key and old_chunk.get("provider") == "human" and target.exists():
            chunks.append(old_chunk)
            speech_total += float(old_chunk.get("dur", 0))
            report_lines.append({"id": row["id"], "source": str(src.relative_to(takes_dir)), "dur": old_chunk["dur"], "cached": True})
            continue

        with tempfile.TemporaryDirectory(prefix="cs-voice-") as td:
            raw = Path(td) / "raw.wav"
            filters = []
            if args.denoise:
                filters.append("afftdn=nf=-25")
            if args.highpass > 0:
                filters.append(f"highpass=f={args.highpass}")
            filters.append(f"silenceremove=start_periods=1:start_threshold={args.trim_db}dB:start_duration=0.02")
            filters.append("areverse")
            filters.append(f"silenceremove=start_periods=1:start_threshold={args.trim_db}dB:start_duration=0.02")
            filters.append("areverse")
            run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", ",".join(filters),
                 "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(raw)])
            measured_peak = peak_db(raw)
            gain = 0.0
            if not args.no_normalize and measured_peak is not None:
                gain = max(-12.0, min(18.0, args.target_peak - measured_peak))
            af = f"volume={gain:.2f}dB" if abs(gain) > 0.05 else "anull"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", af,
                 "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(target)])

        dur = round(duration(target), 3)
        peak = peak_db(target)
        if dur < 0.25:
            warnings.append(f"{row['id']}: only {dur:.2f}s; did you record the whole line?")
        if peak is not None and peak > -0.1:
            warnings.append(f"{row['id']}: peak {peak:.1f} dBFS; lower the input gain")
        target_dur = 0.0
        for scene in timeline.get("scenes", []):
            for chunk in scene.get("chunks", []):
                if chunk.get("id") == row["id"]:
                    target_dur = float(chunk.get("dur", 0))
        if target_dur and dur > target_dur * 1.65:
            warnings.append(f"{row['id']}: {dur:.2f}s vs target {target_dur:.2f}s (much longer); "
                            f"consider re-reading tighter")
        elif target_dur and dur < target_dur * 0.6:
            warnings.append(f"{row['id']}: {dur:.2f}s vs target {target_dur:.2f}s (much shorter); check for a cut line")
        speech_total += dur
        chunks.append({
            **row, "file": str(target.relative_to(project)), "dur": dur, "key": key,
            "provider": "human", "voice": args.voice_name, "source": str(src.relative_to(project))
            if src.is_relative_to(project) else str(src), "peakDb": peak,
        })
        report_lines.append({"id": row["id"], "source": str(src.relative_to(takes_dir)),
                             "dur": dur, "target": target_dur, "peakDb": peak, "gainDb": round(gain, 2)})

    if duplicates:
        warnings.extend(f"duplicate take ignored: {d}" for d in duplicates)
    if any(c.get("provider") != "human" for c in chunks):
        warnings.append("manifest mixes human takes with old TTS chunks; the voice will change mid-film")

    manifest = {"provider": "human", "voice": args.voice_name, "rate": None, "chunks": chunks}
    if args.manifest:
        write_json(args.manifest, manifest)
    else:
        write_json(out_dir / "manifest.json", manifest)
    report = {
        "ok": not any("missing" in w for w in warnings),
        "voice": args.voice_name,
        "takes": len(takes), "lines": len(rows), "speechSeconds": round(speech_total, 2),
        "targetSpeechSeconds": round(target_total, 2),
        "deltaSeconds": round(speech_total - target_total, 2),
        "warnings": warnings, "linesDetail": report_lines,
    }
    write_json(project / "recording" / "import-report.json", report)
    print(json.dumps({"voice": args.voice_name, "lines": len(chunks), "speechSeconds": round(speech_total, 2),
                      "targetSpeechSeconds": round(target_total, 2), "deltaSeconds": round(speech_total - target_total, 2),
                      "warnings": len(warnings)}, ensure_ascii=False))
    for warning in warnings:
        print("warning:", warning)
    if not warnings:
        print("next: python3 <SKILL>/scripts/make_timeline.py --project . && "
              "python3 <SKILL>/scripts/mix_audio.py --project . && node build.mjs")


if __name__ == "__main__":
    main()
