#!/usr/bin/env python3
"""Synthesise one narration clip per line, trim silence, and measure real durations.

Providers:
  edge  Microsoft Edge TTS (network; needs `pip install edge-tts`)
  say   macOS built-in voices (local; `say -v '?'` lists Chinese voices)
  file  bring your own recordings (--voice-dir, names: <scene>-<index:03d>.wav)
  auto  try edge once, then fall back to say on macOS

  python3 scripts/tts.py --project ./film
  python3 scripts/tts.py --project ./film --provider say --voice Tingting --rate 180

Without --provider, an existing manifest's provider is reused so a revision
cannot silently switch voices; pass --provider to change it on purpose.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from film_lib import duration, normalize_lexicon, read_json, require_ffmpeg, run, trim_silence, write_json


class TTSError(RuntimeError):
    pass


def resolve_provider(explicit: str | None, old: dict, voice_cfg: dict) -> str:
    """Keep the provider of existing clips; `auto` must not switch voices mid-film."""
    if explicit:
        return explicit
    remembered = (old or {}).get("provider")
    if remembered in {"edge", "say", "file"}:
        return remembered
    return (voice_cfg or {}).get("provider") or "auto"


def sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def edge_synth(text: str, out_mp3: Path, voice: str, rate: str, retries: int = 3) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise TTSError("edge-tts is not installed: pip install edge-tts") from exc

    async def go():
        for attempt in range(retries):
            try:
                await edge_tts.Communicate(text, voice, rate=rate).save(str(out_mp3))
                return
            except Exception as exc:  # network and token errors are common
                if attempt == retries - 1:
                    raise TTSError(f"edge-tts failed: {exc}") from exc
                await asyncio.sleep(1.5 + attempt)

    asyncio.run(go())
    if not out_mp3.exists() or out_mp3.stat().st_size < 500:
        raise TTSError("edge-tts returned an empty file")


def say_synth(text: str, out_aiff: Path, voice: str, rate: int) -> None:
    if not shutil.which("say"):
        raise TTSError("macOS `say` is not available; use --provider edge or --provider file")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(text)
        txt = Path(fh.name)
    try:
        run(["say", "-v", voice, "-r", str(rate), "-f", str(txt), "-o", str(out_aiff)])
    finally:
        txt.unlink(missing_ok=True)
    if not out_aiff.exists() or out_aiff.stat().st_size < 500:
        raise TTSError("say returned an empty file; check the voice name with `say -v '?'`")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--film", type=Path, help="default <project>/film.json")
    ap.add_argument("--provider", choices=["auto", "edge", "say", "file"])
    ap.add_argument("--voice", help="say voice name, or edge voice id")
    ap.add_argument("--rate", type=int, help="say words-per-minute (default from film.json)")
    ap.add_argument("--edge-rate", help="edge rate such as +8%%")
    ap.add_argument("--voice-dir", type=Path, help="recorded wavs for --provider file")
    ap.add_argument("--only", help="only this scene id")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    require_ffmpeg()
    project = args.project.expanduser().resolve()
    film = read_json((args.film or project / "film.json"))
    if not film:
        raise SystemExit(f"film.json not found in {project}")
    meta = film.get("meta", {})
    voice_cfg = meta.get("voice", {}) or {}
    out_dir = project / "assets" / "tts"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    old = read_json(manifest_path, {}) or {}
    provider = resolve_provider(args.provider, old, voice_cfg)
    say_voice = args.voice or voice_cfg.get("voice") or "Tingting"
    edge_voice = args.voice or voice_cfg.get("edgeVoice") or "zh-CN-YunxiNeural"
    rate = args.rate or int(voice_cfg.get("rate") or 180)
    edge_rate = args.edge_rate or voice_cfg.get("edgeRate") or "+8%"
    lexicon = voice_cfg.get("lexicon") or {}
    if old.get("provider") == "human" and not args.force:
        raise SystemExit("this project uses human recordings (manifest provider=human). "
                         "Run without tts.py, or pass --force to replace them with TTS.")
    old_by_id = {c["id"]: c for c in old.get("chunks", [])}

    chunks = []
    for scene in film.get("scenes", []):
        if args.only and scene.get("id") != args.only:
            continue
        for i, line in enumerate(scene.get("narration", [])):
            spoken = normalize_lexicon(line.get("tts") or line.get("caption") or "", lexicon).strip()
            if not spoken:
                raise SystemExit(f"[{scene['id']}] narration {i} has no tts/caption text")
            chunks.append({"id": f"{scene['id']}-{i:03d}", "scene": scene["id"], "i": i,
                           "text": spoken, "caption": line.get("caption") or spoken})
    if not chunks:
        raise SystemExit("no narration chunks found")

    if args.dry_run:
        for c in chunks:
            print(f"{c['id']}: {c['text']}")
        return

    def key_for(provider_name: str) -> str:
        return sha("|".join([provider_name, say_voice if provider_name == "say" else edge_voice,
                             str(rate), edge_rate if provider_name == "edge" else "", c["text"]]))

    # Resolve auto once, using the first uncached chunk as the probe.
    resolved = provider
    if resolved == "file":
        if not args.voice_dir:
            raise SystemExit("--provider file requires --voice-dir")
        src_dir = args.voice_dir.expanduser().resolve()
    else:
        src_dir = None

    manifest = []
    for c in chunks:
        p = resolved
        if p == "auto":
            p = "edge"
        key = key_for(p)
        old_chunk = old_by_id.get(c["id"])
        target = out_dir / f"{c['id']}.wav"
        if not args.force and old_chunk and old_chunk.get("key") == key and target.exists():
            manifest.append({**c, "file": str(target.relative_to(project)), "dur": old_chunk["dur"], "key": key,
                             "provider": old_chunk.get("provider", p), "voice": old_chunk.get("voice", say_voice if p == "say" else edge_voice)})
            continue

        with tempfile.TemporaryDirectory(prefix="cs-tts-") as td:
            tmp = Path(td)
            try:
                if p == "file":
                    src = src_dir / f"{c['id']}.wav"
                    if not src.exists():
                        src = src_dir / f"{c['scene']}-{c['i']:03d}.wav"
                    if not src.exists():
                        raise TTSError(f"recorded voice missing: {src}")
                    trim_silence(src, target)
                elif p == "say":
                    raw = tmp / "voice.aiff"
                    say_synth(c["text"], raw, say_voice, rate)
                    trim_silence(raw, target)
                elif p == "edge":
                    raw = tmp / "voice.mp3"
                    edge_synth(c["text"], raw, edge_voice, edge_rate)
                    trim_silence(raw, target)
                else:
                    raise TTSError(f"unknown provider {p}")
            except TTSError as exc:
                if resolved == "auto" and p == "edge" and shutil.which("say"):
                    print(f"edge unavailable ({exc}); falling back to macOS say", flush=True)
                    resolved = "say"
                    raw = tmp / "voice.aiff"
                    say_synth(c["text"], raw, say_voice, rate)
                    trim_silence(raw, target)
                    p = "say"
                    key = key_for(p)
                else:
                    raise SystemExit(str(exc))
        manifest.append({**c, "file": str(target.relative_to(project)), "dur": round(duration(target), 3),
                         "key": key, "provider": p, "voice": say_voice if p == "say" else edge_voice})

    # Keep chunks that were skipped by --only when rebuilding the manifest.
    if args.only:
        keep = [x for x in manifest if x["id"] not in {c["id"] for c in chunks}]
        for c in old.get("chunks", []):
            if c["id"] not in {x["id"] for x in manifest} and c["id"] not in {x["id"] for x in chunks}:
                keep.append(c)
        manifest = keep + manifest

    data = {"provider": resolved, "voice": say_voice if resolved == "say" else edge_voice,
            "rate": rate, "edgeRate": edge_rate, "chunks": manifest}
    write_json(manifest_path, data)
    speech = sum(c["dur"] for c in manifest)
    print(json.dumps({"provider": resolved, "voice": data["voice"], "chunks": len(manifest),
                      "speechSeconds": round(speech, 2)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
