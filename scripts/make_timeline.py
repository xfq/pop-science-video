#!/usr/bin/env python3
"""Turn measured narration clips into a scene timeline, captions and marks.

  python3 scripts/make_timeline.py --project ./film
  python3 scripts/make_timeline.py --project ./film --estimate   # no voice yet
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from film_lib import cap_captions, estimate_timeline, read_json, split_caption, write_json


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--film", type=Path)
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--estimate", action="store_true", help="use text length instead of measured clips")
    ap.add_argument("--target", type=float, help="target duration in seconds (default: meta.targetSeconds)")
    ap.add_argument("--fps", type=int)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    project = args.project.expanduser().resolve()
    film = read_json(args.film or project / "film.json")
    if not film:
        raise SystemExit("film.json not found")
    meta = film.get("meta", {})
    target = args.target or float(meta.get("targetSeconds") or 0) or None
    fps = args.fps or int(meta.get("fps") or 30)

    if args.estimate:
        timeline = estimate_timeline(film)
    else:
        manifest = read_json(args.manifest or project / "assets" / "tts" / "manifest.json")
        if not manifest:
            raise SystemExit("no TTS manifest. Run scripts/tts.py first, or pass --estimate.")
        by_id = {c["id"]: c for c in manifest.get("chunks", [])}
        scenes = []
        captions = []
        cursor = 0.0
        for index, scene in enumerate(film.get("scenes", [])):
            gap = 0.0 if index == 0 else float(scene.get("gap", meta.get("sceneGap", 0.02)))
            start = cursor + gap
            local = float(scene.get("lead", 0.15))
            marks: dict[str, float] = {}
            chunks = []
            for i, line in enumerate(scene.get("narration", [])):
                cid = f"{scene['id']}-{i:03d}"
                chunk = by_id.get(cid)
                if not chunk:
                    raise SystemExit(f"TTS missing for {cid}. Re-run scripts/tts.py.")
                dur = float(chunk["dur"])
                if line.get("mark") and line["mark"] not in marks:
                    marks[line["mark"]] = round(start + local + 0.05, 3)
                chunks.append({"id": cid, "caption": line.get("caption") or chunk.get("caption") or "",
                               "text": chunk.get("text", ""), "start": round(start + local, 3),
                               "dur": round(dur, 3), "mark": line.get("mark"), "sfx": line.get("sfx")})
                cap_text = line.get("caption") or chunk.get("caption") or chunk.get("text", "")
                pieces = split_caption(cap_text)
                if pieces:
                    weights = [max(1, len(p)) for p in pieces]
                    total_w = sum(weights)
                    t = start + local
                    for piece, weight in zip(pieces, weights):
                        piece_dur = max(0.55, dur * weight / total_w)
                        captions.append({"text": piece, "start": round(t, 3), "dur": round(piece_dur, 3)})
                        t += piece_dur
                local += dur + float(line.get("pause", scene.get("pause", 0.26)))
            tail = float(scene.get("tail", meta.get("sceneTail", 0.75)))
            scene_dur = max(float(scene.get("minDuration", 2.4)), local + tail)
            if not scene.get("narration"):
                scene_dur = max(scene_dur, float(scene.get("duration", 3.0)))
            scenes.append({"id": scene["id"], "index": index, "start": round(start, 3),
                           "duration": round(scene_dur, 3), "marks": marks, "chunks": chunks,
                           "estimated": False})
            scene_end = start + scene_dur - 0.08
            for cap in captions:
                if cap["start"] >= start and cap["start"] < scene_end:
                    cap["dur"] = max(0.35, min(cap["dur"], scene_end - cap["start"]))
            cursor = start + scene_dur
        total = round(cursor, 3)
        timeline = {"version": 1, "estimated": False, "duration": total,
                    "scenes": scenes, "captions": cap_captions(captions, total)}

    total = timeline["duration"]
    timeline["fps"] = fps
    timeline["targetSeconds"] = target
    write_json(project / "timeline.json", timeline)
    write_json(project / "evidence" / "timing.json", {
        "duration": total, "target": target, "fps": fps, "estimated": timeline.get("estimated", False),
        "scenes": [{"id": s["id"], "start": s["start"], "duration": s["duration"]} for s in timeline["scenes"]],
        "speechSeconds": round(sum(c["dur"] for s in timeline["scenes"] for c in s["chunks"]), 2),
        "captions": len(timeline["captions"]),
    })

    if not args.quiet:
        print(f"timeline: {total:.2f}s · {len(timeline['scenes'])} scenes · {len(timeline['captions'])} captions · {fps} fps"
              + (" (estimated)" if timeline.get("estimated") else ""))
        for s in timeline["scenes"]:
            print(f"  {s['id']:<14} {s['start']:>6.2f} + {s['duration']:>5.2f}s")
        if target and total > target * 1.12:
            print(f"warning: {total:.1f}s is more than 12% over the {target:.0f}s target; trim narration, not tail.")
        elif target and total < target * 0.78:
            print(f"warning: {total:.1f}s is well under the {target:.0f}s target; add a beat or lengthen the mechanism.")
        missing = [s["id"] for s in timeline["scenes"] if not s["chunks"] and not any(x.get("narration") for x in film["scenes"] if x["id"] == s["id"])]
        if missing:
            print("note: visual-only scenes: " + ", ".join(missing))


if __name__ == "__main__":
    main()
