#!/usr/bin/env python3
"""Export a line-by-line recording kit from film.json + timeline.json.

  python3 scripts/make_recording_kit.py --project ./film
  python3 scripts/make_recording_kit.py --project ./film --guide

Creates recording/ with NARRATION.md, lines.csv, lines.json, takes/ and an import README.
`--guide` also copies the current TTS clips into recording/guide/ for pacing reference.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

from film_lib import estimate_timeline, read_json, write_json


def load_timeline(project: Path, film: dict) -> dict:
    timeline = read_json(project / "timeline.json")
    return timeline or estimate_timeline(film)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, help="default <project>/recording")
    ap.add_argument("--guide", action="store_true", help="copy current TTS clips as guide/")
    ap.add_argument("--force", action="store_true", help="overwrite kit text files (takes are never deleted)")
    args = ap.parse_args()

    project = args.project.expanduser().resolve()
    film = read_json(project / "film.json")
    if not film:
        raise SystemExit("film.json not found")
    timeline = load_timeline(project, film)
    out = (args.out or project / "recording").expanduser().resolve()
    takes = out / "takes"
    guide = out / "guide"
    takes.mkdir(parents=True, exist_ok=True)
    (takes / ".gitkeep").touch()
    if args.guide:
        guide.mkdir(parents=True, exist_ok=True)

    chunks = {}
    for scene_tl in timeline.get("scenes", []):
        for i, chunk in enumerate(scene_tl.get("chunks", [])):
            chunks[chunk.get("id") or f"{scene_tl['id']}-{i:03d}"] = chunk
    rows = []
    for scene in film.get("scenes", []):
        for i, line in enumerate(scene.get("narration", [])):
            cid = f"{scene['id']}-{i:03d}"
            chunk = chunks.get(cid, {})
            rows.append({
                "scene": scene["id"],
                "scene_index": 0,
                "i": i,
                "id": cid,
                "file": f"{cid}.wav",
                "caption": line.get("caption") or line.get("tts") or "",
                "tts": line.get("tts") or line.get("caption") or "",
                "targetSeconds": round(float(chunk.get("dur", 0)), 2),
                "pauseAfter": round(float(line.get("pause", scene.get("pause", 0.26))), 2),
                "mark": line.get("mark") or "",
            })
    # stable scene numbers
    scene_order = [s["id"] for s in film.get("scenes", [])]
    for row in rows:
        row["scene_index"] = scene_order.index(row["scene"]) + 1

    lines_path = out / "lines.json"
    if lines_path.exists() and not args.force:
        print(f"keeping existing {lines_path} (pass --force to rewrite)")
    else:
        write_json(lines_path, {"version": 1, "lines": rows})
        with (out / "lines.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["id"])
            writer.writeheader()
            writer.writerows(rows)

    total = sum(r["targetSeconds"] for r in rows)
    by_scene: dict[str, list[dict]] = {}
    for row in rows:
        by_scene.setdefault(row["scene"], []).append(row)

    md = [f"# 录音稿 · {film.get('meta', {}).get('title', '')}", ""]
    md += [
        f"共 {len(rows)} 句，目标语音约 {total:.1f} 秒（不含句间停顿）。",
        "",
        "## 怎么录",
        "",
        "1. 手机自带录音机/麦克风即可。找一间有窗帘、地毯、床的安静房间，避开空调、冰箱、电脑风扇。",
        "2. 麦克风离嘴 15–20 cm，稍微偏一点，避免喷麦；不要用手捂着手机底部麦克风。",
        "3. **一句一个文件**，文件名严格用下面的英文名（`hook-000.wav`）。每句前后留 0.5 秒安静，读错就整句重来。",
        "4. 先读 `读法` 那一行（它处理了数字、英文缩写和断句），不要照着字幕里的阿拉伯数字硬读。",
        "5. 语速按目标时长走；宁可慢一点，不要为了赶时长吞字。",
        "6. 录完把文件放进 `recording/takes/`，然后运行（把 `<SKILL>` 换成 skill 安装目录）：",
        "",
        "```sh",
        "python3 <SKILL>/scripts/import_recordings.py --project .",
        "python3 <SKILL>/scripts/make_timeline.py --project .",
        "python3 <SKILL>/scripts/mix_audio.py --project .",
        "node build.mjs",
        "npx --yes hyperframes@0.8.184 render --quality delivery --output renders/final.mp4",
        "```",
        "",
        "更完整的设备、表演、降噪和混音说明见 skill 的 `references/human-voice.md`。",
        "",
        "## 清单",
        "",
    ]
    for scene in film.get("scenes", []):
        sid = scene["id"]
        if sid not in by_scene:
            continue
        scene_chunks = [c for c in timeline.get("scenes", []) if c["id"] == sid]
        scene_dur = scene_chunks[0]["duration"] if scene_chunks else 0
        md += [f"### {by_scene[sid][0]['scene_index']:02d} · {scene.get('chapter', sid)} · 目标 {scene_dur:.1f}s", ""]
        for row in by_scene[sid]:
            md += [
                f"**{row['file']}**  ·  目标 {row['targetSeconds']:.1f}s  ·  停顿 {row['pauseAfter']:.2f}s",
                "",
                f"- 读法：{row['tts']}",
                f"- 字幕：{row['caption']}",
                "",
            ]
    (out / "NARRATION.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    readme = out / "README.md"
    if not readme.exists() or args.force:
        readme.write_text(
            "# 录音工作区\n\n"
            "- `NARRATION.md`：逐句录音稿、目标时长、读法。\n"
            "- `lines.csv` / `lines.json`：同样的内容，方便导入表格或提词器。\n"
            "- `takes/`：把录好的文件放这里，命名必须和稿子里的英文名一致。\n"
            "- `guide/`：可选，当前 TTS 的参考音，只用来听节奏，不要跟着它的机器感读。\n\n"
            "导入后时间轴会按你的真实语速重排；不需要手动改字幕时间。\n",
            encoding="utf-8",
        )

    if args.guide:
        copied = 0
        for row in rows:
            src = project / "assets" / "tts" / f"{row['id']}.wav"
            if src.exists():
                shutil.copyfile(src, guide / f"{row['id']}.wav")
                copied += 1
        print(f"guide: {copied} clips -> {guide}")

    print(json.dumps({"kit": str(out), "lines": len(rows), "targetSeconds": round(total, 2),
                      "takes": str(takes)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
