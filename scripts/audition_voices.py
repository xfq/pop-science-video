#!/usr/bin/env python3
"""Generate the same line in several installed macOS Chinese voices for comparison.

  python3 scripts/audition_voices.py --project ./film
  python3 scripts/audition_voices.py --project ./film --text "这是试听句子。" --voices Tingting,Flo,Reed

This is still TTS. Use it only to choose a less mechanical fallback; a human recording
is the recommended path for a published film.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from film_lib import duration, read_json, trim_silence, write_json


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--text", help="default: first narration line")
    ap.add_argument("--voices", default="Tingting,Flo,Reed,Sandy,Meijia")
    ap.add_argument("--rate", type=int, default=190)
    ap.add_argument("--out", type=Path, help="default <project>/recording/auditions")
    args = ap.parse_args()

    if not shutil.which("say"):
        raise SystemExit("macOS `say` is not available on this machine")
    project = args.project.expanduser().resolve()
    film = read_json(project / "film.json")
    if not film:
        raise SystemExit("film.json not found")
    text = args.text
    if not text:
        for scene in film.get("scenes", []):
            for line in scene.get("narration", []):
                text = line.get("tts") or line.get("caption")
                if text:
                    break
            if text:
                break
    if not text:
        raise SystemExit("no narration text found; pass --text")

    out = (args.out or project / "recording" / "auditions").expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for voice in [v.strip() for v in args.voices.split(",") if v.strip()]:
        with tempfile.TemporaryDirectory(prefix="cs-audition-") as td:
            aiff = Path(td) / "take.aiff"
            wav = out / f"{voice.replace(' ', '-')}.wav"
            proc = subprocess.run(["say", "-v", voice, "-r", str(args.rate), "-o", str(aiff), text],
                                  capture_output=True, text=True)
            if proc.returncode != 0 or not aiff.exists():
                print(f"skip {voice}: {proc.stderr.strip() or 'voice not available'}")
                continue
            trim_silence(aiff, wav)
            if not wav.exists() or wav.stat().st_size < 2000 or duration(wav) < 0.2:
                wav.unlink(missing_ok=True)
                print(f"skip {voice}: no usable audio (voice may not be installed for Chinese)")
                continue
            rows.append({"voice": voice, "file": str(wav.relative_to(project)) if wav.is_relative_to(project) else str(wav)})
    write_json(out / "index.json", {"text": text, "rate": args.rate, "voices": rows})
    md = [f"# 音色试听", "", f"同一句：{text}", "", "| 音色 | 文件 |", "| --- | --- |"]
    md += [f"| {r['voice']} | `{r['file']}` |" for r in rows]
    (out / "index.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "voices": len(rows), "text": text}, ensure_ascii=False))


if __name__ == "__main__":
    main()
