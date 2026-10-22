#!/usr/bin/env python3
"""Audit the script, fact ledger and timing before anything is rendered.

  python3 scripts/check_content.py --project ./film
  python3 scripts/check_content.py --project ./film --strict --json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from film_lib import cps_for, read_json, split_caption, write_json

TYPES = {"hook", "statement", "pipeline", "bitfield", "code", "compare", "numbers", "layers", "recap", "outro"}
STATUS = {"verified", "needs-review", "unverified", "opinion"}
PLACEHOLDERS = ("待定", "在这里", "replace-me", "TODO", "Lorem", "下一个问题，", "第一句话")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--film", type=Path)
    ap.add_argument("--facts", type=Path)
    ap.add_argument("--timeline", type=Path)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--allow-placeholders", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    project = args.project.expanduser().resolve()
    film = read_json(args.film or project / "film.json")
    if not film:
        raise SystemExit("film.json not found")
    facts = read_json(args.facts or project / "facts.json", {"claims": [], "analogies": []})
    timeline = read_json(args.timeline or project / "timeline.json", None)
    errors: list[str] = []
    warnings: list[str] = []

    meta = film.get("meta", {})
    for key in ("title", "language", "takeaway"):
        if not meta.get(key):
            (errors if key != "takeaway" else warnings).append(f"meta.{key} is empty")
    if meta.get("width", 1920) != 1920 or meta.get("height", 1080) != 1080:
        warnings.append("this template is authored for 1920x1080; other sizes need a layout pass")

    scenes = film.get("scenes", [])
    if len(scenes) < 3:
        errors.append("a film needs at least 3 scenes (hook, mechanism, recap/outro)")
    ids = set()
    claims = {c.get("id"): c for c in facts.get("claims", [])}
    used_claims: set[str] = set()
    marks: set[tuple[str, str]] = set()
    total_chars = 0
    for index, scene in enumerate(scenes):
        sid = scene.get("id")
        if not sid:
            errors.append(f"scene {index}: missing id")
            continue
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,30}", str(sid)):
            errors.append(f"scene {sid}: id must be a lowercase ASCII slug")
        if sid in ids:
            errors.append(f"scene {sid}: duplicate id")
        ids.add(sid)
        if scene.get("type") not in TYPES:
            errors.append(f"scene {sid}: unknown type {scene.get('type')!r}")
        narration = scene.get("narration") or []
        if not narration:
            warnings.append(f"scene {sid}: visual-only (no narration)")
        for i, line in enumerate(narration):
            text = line.get("tts") or line.get("caption") or ""
            if not text.strip():
                errors.append(f"scene {sid} line {i}: empty narration")
            if not line.get("caption"):
                warnings.append(f"scene {sid} line {i}: no caption; TTS text will be used")
            total_chars += len(text)
            for piece in split_caption(line.get("caption") or text):
                if len(piece) > 38:
                    warnings.append(f"scene {sid} line {i}: caption too long ({len(piece)} chars): {piece}")
            if line.get("mark"):
                key = (str(sid), str(line["mark"]))
                if key in marks:
                    warnings.append(f"scene {sid}: mark {line['mark']} appears twice")
                marks.add(key)
        if scene.get("claim"):
            source_ids = scene.get("sources") or []
            if not source_ids:
                errors.append(f"scene {sid}: claim=true but no sources")
            for cid in source_ids:
                if cid not in claims:
                    errors.append(f"scene {sid}: source id {cid!r} not found in facts.json")
                else:
                    used_claims.add(cid)
        if scene.get("type") in {"numbers", "bitfield"} and not scene.get("claim"):
            warnings.append(f"scene {sid}: number/encoding scene does not cite a claim")

    for cid in used_claims:
        claim = claims[cid]
        if claim.get("status") not in STATUS:
            errors.append(f"claim {cid}: status must be one of {sorted(STATUS)}")
        if claim.get("status") in {"needs-review", "unverified"}:
            (errors if args.strict else warnings).append(f"claim {cid}: status is {claim.get('status')}")
        sources = claim.get("sources") or []
        if not sources:
            errors.append(f"claim {cid}: no sources")
        for source in sources:
            url = str(source.get("url", ""))
            if not re.match(r"https?://", url):
                errors.append(f"claim {cid}: source url is not http(s): {url!r}")
            if source.get("kind") == "primary":
                pass
        if not claim.get("verification"):
            warnings.append(f"claim {cid}: no verification note (how did you check it?)")

    primary = sum(1 for c in claims.values() for s in c.get("sources", []) if s.get("kind") == "primary")
    if primary < 2:
        warnings.append(f"only {primary} primary source(s); a science explainer should have at least 2")
    for analogy in facts.get("analogies", []):
        if not analogy.get("breaks"):
            errors.append(f"analogy {analogy.get('text', '')!r}: missing 'breaks' (where the analogy stops working)")

    for name in ("DIRECTION.md", "SOURCES.md"):
        path = project / name
        if not path.exists() or path.stat().st_size < 80:
            warnings.append(f"{name} is missing or too short")
    try:
        direction = (project / "DIRECTION.md").read_text(encoding="utf-8")
        for section in ("一句话", "镜头表"):
            if section not in direction:
                warnings.append(f"DIRECTION.md: missing section {section}")
    except FileNotFoundError:
        pass

    if not args.allow_placeholders:
        haystack = json.dumps(film, ensure_ascii=False)
        for token in PLACEHOLDERS:
            if token in haystack:
                warnings.append(f"placeholder text still present: {token!r}")

    target = float(meta.get("targetSeconds") or 0) or None
    if timeline:
        total = float(timeline.get("duration", 0))
        if target and abs(total - target) > max(8.0, target * 0.18):
            warnings.append(f"timeline {total:.1f}s is far from target {target:.0f}s")
        for ts in timeline.get("scenes", []):
            chunks = ts.get("chunks", [])
            if not chunks:
                continue
            speech = sum(float(c.get("dur", 0)) for c in chunks)
            ratio = speech / max(0.1, float(ts.get("duration", 1)))
            if ratio > 0.90:
                warnings.append(f"scene {ts.get('id')}: speech fills {ratio:.0%} of the scene; leave breathing room")
            if ratio < 0.35:
                warnings.append(f"scene {ts.get('id')}: speech is only {ratio:.0%} of the scene; visuals may drag")
            chars = sum(len(c.get("text", "")) for c in chunks)
            cps = chars / speech if speech else 0
            if cps > 6.0:
                warnings.append(f"scene {ts.get('id')}: {cps:.1f} chars/s is fast; slow the read")
            if cps < 2.2:
                warnings.append(f"scene {ts.get('id')}: {cps:.1f} chars/s is slow; tighten the copy")
    else:
        warnings.append("timeline.json missing; run TTS + make_timeline.py before rendering")

    report = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "scenes": len(scenes),
        "facts": len(claims),
        "usedClaims": sorted(used_claims),
        "narrationChars": total_chars,
        "timeline": bool(timeline),
    }
    write_json(project / "evidence" / "content-check.json", report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f"content: {len(scenes)} scenes · {len(claims)} claims · {total_chars} narration chars")
        for error in errors:
            print(f"ERROR   {error}")
        for warning in warnings:
            print(f"warning {warning}")
        print("content check passed" if not errors else "content check failed")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
