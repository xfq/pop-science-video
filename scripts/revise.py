#!/usr/bin/env python3
"""Revise an existing film's narration in one command.

Edit `film.json` (narration[].caption / tts / mark), then run:

  python3 scripts/revise.py --project ./film                # check + rebuild, no render
  python3 scripts/revise.py --project ./film --render draft # fast watchable cut
  python3 scripts/revise.py --project ./film --render delivery

The pipeline keeps the quality gates: content check, mark completeness, target
duration, mix loudness, build report, HyperFrames check before a delivery
render, and check_delivery.py afterwards. Only the lines whose spoken text
changed are re-recorded; the existing voice/provider is preserved.

Human narration: run once without --import to refresh the recording kit and
list the takes that need re-recording/renaming, then run with --import after
recording. The importer is checked for stale takes so a shifted line cannot
silently pair old audio with new text.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from film_lib import duration, ffprobe_json, normalize_lexicon, read_json, write_json

SCRIPTS = Path(__file__).resolve().parent
HYPERFRAMES_VERSION = "0.8.184"
MARK_WARNING = re.compile(r'mark "([^"]+)" has no narration timing')
MOODS = {"curious", "focused", "playful", "tense"}


class ReviseError(RuntimeError):
    pass


# --------------------------------------------------------------------- helpers
def python_script(name: str) -> list[str]:
    return [sys.executable, str(SCRIPTS / name)]


def run_cmd(cmd: list, cwd: Path, timeout: float | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            [str(x) for x in cmd],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout:.0f}s: {' '.join(map(str, cmd))}"
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def tail(text: str, lines: int = 16) -> str:
    rows = [row for row in (text or "").strip().splitlines() if row.strip()]
    return "\n".join(rows[-lines:])


def last_json(text: str) -> dict:
    for row in reversed((text or "").splitlines()):
        row = row.strip()
        if not row.startswith("{"):
            continue
        try:
            parsed = json.loads(row)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def compact(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def collect_lines(film: dict, human: bool = False) -> list[dict]:
    """Flatten narration into stable positional ids (<scene>-<NNN>)."""
    meta_voice = (film.get("meta", {}).get("voice") or {})
    lexicon = meta_voice.get("lexicon") or {}
    lines: list[dict] = []
    for scene in film.get("scenes", []):
        for i, line in enumerate(scene.get("narration", [])):
            raw = str(line.get("tts") or line.get("caption") or "").strip()
            spoken = raw if human else normalize_lexicon(raw, lexicon).strip()
            lines.append({
                "id": f"{scene['id']}-{i:03d}",
                "scene": scene["id"],
                "i": i,
                "spoken": spoken,
                "raw": raw,
                "caption": str(line.get("caption") or raw).strip(),
                "mark": line.get("mark"),
                "sfx": line.get("sfx"),
                "pause": line.get("pause", scene.get("pause", 0.26)),
            })
    return lines


def diff_narration(lines: list[dict], manifest: dict) -> dict:
    old = {c["id"]: c for c in (manifest or {}).get("chunks", []) if c.get("id")}
    changed: list[dict] = []
    added: list[dict] = []
    caption_changed: list[dict] = []
    ids = {line["id"] for line in lines}
    for line in lines:
        chunk = old.get(line["id"])
        # A shifted line keeps its audio but changes position: the same text
        # lives under another id in the old manifest.
        matches = [c for chunk_id, c in old.items()
                   if chunk_id != line["id"] and str(c.get("text") or "").strip() == line["spoken"]]
        if not chunk:
            item = dict(line)
            item["shifted"] = bool(matches)
            item["source"] = matches[0] if matches else None
            added.append(item)
            continue
        if str(chunk.get("text") or "").strip() != line["spoken"]:
            item = dict(line)
            item["old"] = chunk
            item["shifted"] = bool(matches)
            item["source"] = matches[0] if matches else None
            changed.append(item)
        elif str(chunk.get("caption") or "").strip() != line["caption"]:
            caption_changed.append(line)
    removed = [chunk for chunk_id, chunk in old.items() if chunk_id not in ids]
    return {"changed": changed, "added": added, "removed": removed,
            "caption_changed": caption_changed, "old": old}


def stale_screen_text(film: dict, old_chunks: list[dict]) -> list[dict]:
    """Find old narration lines that still live in non-narration scene fields."""
    static: list[tuple[str, str]] = []

    def walk(node, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "narration":
                    continue
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, str):
            static.append((path, node))

    walk(film, "")
    hits: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for chunk in old_chunks:
        for candidate in {str(chunk.get("caption") or ""), str(chunk.get("text") or "")}:
            needle = compact(candidate)
            if len(needle) < 4:
                continue
            for path, value in static:
                if needle not in compact(value):
                    continue
                key = (path, needle)
                if key in seen:
                    continue
                seen.add(key)
                hits.append({"path": path, "text": candidate, "id": chunk.get("id")})
    return hits


def mark_changes(lines: list[dict], timeline: dict) -> tuple[list[tuple], list[tuple]]:
    old = {(scene.get("id"), mark) for scene in (timeline or {}).get("scenes", [])
           for mark in (scene.get("marks") or {})}
    new = {(line["scene"], line["mark"]) for line in lines if line.get("mark")}
    return sorted(new - old), sorted(old - new)


def sfx_changes(lines: list[dict], timeline: dict) -> list[str]:
    old: dict[str, object] = {}
    for scene in (timeline or {}).get("scenes", []):
        for chunk in scene.get("chunks", []):
            old[chunk.get("id")] = chunk.get("sfx")
    return [line["id"] for line in lines if (line.get("sfx") or None) != (old.get(line["id"]) or None)]


def voice_config(film: dict, manifest: dict, revoice: bool = False) -> dict:
    """Keep the recorded voice stable unless --revoice is requested."""
    meta = (film.get("meta", {}).get("voice") or {})
    old_provider = (manifest or {}).get("provider")
    remembered = old_provider in {"say", "edge", "file"} and not revoice
    provider = old_provider if remembered else (meta.get("provider") or "auto")
    # `--revoice` with a film-level "auto" should not silently switch voices.
    if revoice and provider == "auto" and old_provider in {"say", "edge"}:
        provider = old_provider
    if provider not in {"auto", "say", "edge", "file"}:
        provider = "auto"
    cfg: dict = {"provider": provider}
    if provider == "say":
        cfg["voice"] = (manifest.get("voice") if remembered and manifest.get("voice")
                        else meta.get("voice") or "Tingting")
        cfg["rate"] = int((manifest.get("rate") if remembered and manifest.get("rate")
                           else meta.get("rate") or 180))
    elif provider == "edge":
        cfg["voice"] = (manifest.get("voice") if remembered and manifest.get("voice")
                        else meta.get("edgeVoice") or "zh-CN-YunxiNeural")
        cfg["edgeRate"] = (manifest.get("edgeRate") if remembered and manifest.get("edgeRate")
                           else meta.get("edgeRate") or "+8%")
    elif provider == "file":
        cfg["voice"] = manifest.get("voice")
    return cfg


def tts_command(project: Path, cfg: dict, revoice: bool, voice_dir: Path | None) -> list:
    provider = cfg["provider"]
    cmd = python_script("tts.py") + ["--project", str(project), "--provider", provider]
    if provider == "say":
        cmd += ["--voice", cfg.get("voice") or "Tingting", "--rate", str(cfg.get("rate") or 180)]
    elif provider == "edge":
        cmd += ["--voice", cfg.get("voice") or "zh-CN-YunxiNeural",
                "--edge-rate", cfg.get("edgeRate") or "+8%"]
    elif provider == "file":
        if not voice_dir:
            raise ReviseError("旁白来自外部音频（provider=file），请用 --voice-dir 指定音频目录")
        cmd += ["--voice-dir", str(voice_dir)]
    if revoice:
        cmd.append("--force")
    return cmd


def music_settings(evidence: dict) -> tuple[dict, list]:
    evidence = evidence or {}
    mood = evidence.get("mood") if evidence.get("mood") in MOODS else "curious"
    settings = {"mood": mood, "bpm": evidence.get("bpm"), "seed": evidence.get("seed")}
    args = ["--mood", mood]
    if settings["bpm"]:
        args += ["--bpm", str(settings["bpm"])]
    if settings["seed"] is not None:
        args += ["--seed", str(settings["seed"])]
    return settings, args


def stale_takes(before: dict, after: dict, changed: list[dict]) -> list[str]:
    """A changed line whose take hash did not change still has the old audio."""
    old = {c["id"]: c for c in (before or {}).get("chunks", []) if c.get("id")}
    new = {c["id"]: c for c in (after or {}).get("chunks", []) if c.get("id")}
    stale: list[str] = []
    for item in changed:
        line = item["line"] if "line" in item else item
        previous = old.get(line["id"])
        current = new.get(line["id"])
        if not previous or not current:
            continue
        if str(previous.get("text") or "").strip() == line["spoken"]:
            continue
        if previous.get("key") and previous.get("key") == current.get("key"):
            stale.append(line["id"])
    return stale


def snapshot_wavs(folder: Path) -> dict[str, tuple[int, int]]:
    if not folder.exists():
        return {}
    return {path.name: (path.stat().st_mtime_ns, path.stat().st_size)
            for path in folder.glob("*.wav")}


# --------------------------------------------------------------------- pipeline
class Revision:
    def __init__(self, args, project: Path):
        self.args = args
        self.project = project
        self.film_path = project / "film.json"
        self.film = read_json(self.film_path)
        if not self.film:
            raise ReviseError(f"找不到 {self.film_path}")
        self.manifest = read_json(project / "assets" / "tts" / "manifest.json", {}) or {}
        self.timeline = read_json(project / "timeline.json", {}) or {}
        self.music_evidence = read_json(project / "evidence" / "music.json", {}) or {}
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.exit_code = 0
        self.started = time.perf_counter()
        self.report: dict = {
            "project": str(project),
            "title": (self.film.get("meta", {}) or {}).get("title"),
            "dryRun": bool(args.dry_run),
            "steps": {},
            "warnings": self.warnings,
            "errors": self.errors,
        }
        self.human = self.manifest.get("provider") == "human"
        self.lines = collect_lines(self.film, human=self.human)
        self.voice = voice_config(self.film, self.manifest, revoice=args.revoice)
        self.diff = diff_narration(self.lines, self.manifest)
        self.new_marks, self.lost_marks = mark_changes(self.lines, self.timeline)
        self.changed_sfx = sfx_changes(self.lines, self.timeline)
        self.audio_changed = bool(
            self.diff["changed"] or self.diff["added"] or self.diff["removed"]
            or self.changed_sfx or args.revoice
        )
        stale_chunks = [item["old"] for item in self.diff["changed"]] + self.diff["removed"]
        stale_chunks += [self.diff["old"][line["id"]] for line in self.diff["caption_changed"]
                         if line["id"] in self.diff["old"]]
        self.stale_hits = stale_screen_text(self.film, stale_chunks)
        self.report["lines"] = {
            "total": len(self.lines),
            "changed": [item["id"] for item in self.diff["changed"]],
            "added": [line["id"] for line in self.diff["added"]],
            "removed": [chunk.get("id") for chunk in self.diff["removed"]],
            "captionOnly": [line["id"] for line in self.diff["caption_changed"]],
            "audioChanged": self.audio_changed,
        }

    # -- utilities ---------------------------------------------------------
    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def fail(self, message: str) -> None:
        if message not in self.errors:
            self.errors.append(message)
        raise ReviseError(message)

    def say(self, message: str) -> None:
        if self.args.verbose:
            print(message, flush=True)

    def rerun_command(self, *flags: str) -> str:
        parts = ["python3", shlex.quote(str(Path(__file__).resolve())),
                 "--project", shlex.quote(str(self.project))]
        return " ".join(parts + list(flags))

    def step(self, name: str, **values) -> None:
        self.report["steps"][name] = values

    def require(self, name: str) -> str:
        found = shutil.which(name)
        if not found:
            self.fail(f"缺少 {name}，请先安装并确认在 PATH 中")
        return found

    # -- gates -------------------------------------------------------------
    def content_check(self, pre: bool) -> dict:
        rc, out, err = run_cmd(python_script("check_content.py")
                               + ["--project", str(self.project), "--json"], self.project)
        try:
            data = json.loads(out) if out.strip() else {}
        except json.JSONDecodeError:
            data = {}
        if rc not in (0, 1) or not data:
            self.fail("内容检查没有正常跑完：\n" + tail(out + "\n" + err))
        if data.get("errors"):
            self.fail("内容检查未通过：\n" + "\n".join(f"- {e}" for e in data["errors"]))
        for warning in data.get("warnings", []):
            if not pre:
                self.warn(str(warning))
        self.step("content", errors=0, warnings=len(data.get("warnings", [])))
        return data

    # -- voice -------------------------------------------------------------
    def synthesize(self) -> None:
        self.require("ffmpeg")
        before = snapshot_wavs(self.project / "assets" / "tts")
        old_durations = {c["id"]: c.get("dur") for c in self.manifest.get("chunks", []) if c.get("id")}
        cmd = tts_command(self.project, self.voice, self.args.revoice, self.args.voice_dir)
        self.say("配音：" + " ".join(cmd[1:3]) + f" · provider={self.voice['provider']}")
        rc, out, err = run_cmd(cmd, self.project)
        if rc != 0:
            self.fail("配音失败：\n" + tail(out + "\n" + err))
        payload = last_json(out)
        self.manifest = read_json(self.project / "assets" / "tts" / "manifest.json", {}) or {}
        if self.manifest.get("provider") == "human":
            self.fail("manifest 标记为 human；不要用 tts.py 覆盖真人录音")
        after = snapshot_wavs(self.project / "assets" / "tts")
        resynthesized = sorted(name[:-4] for name, stat in after.items()
                               if before.get(name) != stat)
        by_id = {c["id"]: c for c in self.manifest.get("chunks", []) if c.get("id")}
        missing = [line["id"] for line in self.lines if line["id"] not in by_id]
        if missing:
            self.fail("manifest 缺少这些句子：" + ", ".join(missing))
        for line in self.lines:
            path = self.project / "assets" / "tts" / f"{line['id']}.wav"
            if not path.exists():
                self.fail(f"旁白文件缺失：{path.relative_to(self.project)}")
        if (not resynthesized and not self.args.revoice
                and (self.diff["changed"] or self.diff["added"])):
            self.warn("没有句子被重录（缓存命中）；如果改过读音，检查 tts 文本或加 --revoice")
        durations = {}
        for line in self.lines:
            new_dur = by_id[line["id"]].get("dur")
            if line["id"] in resynthesized:
                durations[line["id"]] = [old_durations.get(line["id"]), new_dur]
        self.report["voice"] = {
            "provider": self.manifest.get("provider") or payload.get("provider"),
            "voice": self.manifest.get("voice") or payload.get("voice"),
            "resynthesized": resynthesized,
            "durations": durations,
        }
        self.step("voice", skipped=False, **self.report["voice"])

    def human_step(self) -> None:
        changed = self.diff["changed"] + self.diff["added"]
        if not changed and not self.args.import_takes:
            self.step("voice", skipped=True, provider="human", reason="旁白文本没有变化")
            return
        if not self.args.import_takes:
            rc, out, err = run_cmd(python_script("make_recording_kit.py")
                                   + ["--project", str(self.project), "--force"], self.project)
            if rc != 0:
                self.fail("刷新录音稿失败：\n" + tail(out + "\n" + err))
            self.print_recording_todo()
            self.exit_code = 2
            self.step("voice", skipped=False, provider="human", needsRecording=True,
                      todo=self.recording_todo)
            return
        before = self.manifest
        cmd = python_script("import_recordings.py") + ["--project", str(self.project)]
        rc, out, err = run_cmd(cmd, self.project)
        if rc != 0:
            self.fail("导入真人录音失败：\n" + tail(out + "\n" + err))
        for row in (out + "\n" + err).splitlines():
            if row.strip().lower().startswith("warning:"):
                self.warn(row.strip())
        self.manifest = read_json(self.project / "assets" / "tts" / "manifest.json", {}) or {}
        stale = stale_takes(before, self.manifest, self.diff["changed"])
        if stale:
            self.fail("这些 take 没换，音频还是旧台词：\n"
                      + "\n".join(f"- {cid}" for cid in stale)
                      + "\n重录对应文件，或先把 take 改名到新位置，再跑 --import")
        mixed = [c["id"] for c in self.manifest.get("chunks", [])
                 if c.get("provider") and c.get("provider") != "human"]
        if mixed:
            self.warn(f"{len(mixed)} 句仍是旧 TTS，音色会在片中切换：" + ", ".join(mixed[:6]))
        # A re-recorded take with unchanged text still has to reach the mix.
        self.audio_changed = True
        self.report["lines"]["audioChanged"] = True
        self.step("voice", skipped=False, provider="human", imported=True,
                  chunks=len(self.manifest.get("chunks", [])))

    def print_recording_todo(self) -> None:
        if self.args.json:
            return
        todo = self.recording_todo
        print("\n旁白是真人录音：下面这些 take 需要处理，录完/改名后再跑 --import。")
        for row in todo:
            print(f"  {row['id']:<14} {row['action']:<10} {row['detail']}")

    @property
    def recording_todo(self) -> list[dict]:
        todo: list[dict] = []
        for item in self.diff["changed"]:
            source = item.get("source")
            if source:
                todo.append({"id": item["id"], "action": "改名",
                             "detail": f"把 recording/takes/{source.get('id')}.wav 改成 {item['id']}.wav"})
            else:
                todo.append({"id": item["id"], "action": "重录",
                             "detail": f"改过的句子 → recording/takes/{item['id']}.wav"})
        for item in self.diff["added"]:
            source = item.get("source")
            if source:
                todo.append({"id": item["id"], "action": "改名",
                             "detail": f"把 recording/takes/{source.get('id')}.wav 改成 {item['id']}.wav"})
            else:
                todo.append({"id": item["id"], "action": "重录",
                             "detail": f"新增的句子 → recording/takes/{item['id']}.wav"})
        return todo

    # -- timeline ----------------------------------------------------------
    def rebuild_timeline(self) -> None:
        old = self.timeline
        old_duration = float(old.get("duration") or 0)
        old_starts = {chunk.get("id"): chunk.get("start")
                      for scene in old.get("scenes", []) for chunk in scene.get("chunks", [])}
        rc, out, err = run_cmd(python_script("make_timeline.py")
                               + ["--project", str(self.project)], self.project)
        if rc != 0:
            self.fail("重排时间轴失败：\n" + tail(out + "\n" + err))
        for row in (out + "\n" + err).splitlines():
            if row.strip().lower().startswith("warning:"):
                self.warn(row.strip())
        timeline = read_json(self.project / "timeline.json", {}) or {}
        if not timeline or not timeline.get("scenes"):
            self.fail("timeline.json 没有生成")
        if len(timeline["scenes"]) != len(self.film.get("scenes", [])):
            self.fail("timeline.json 的镜头数与 film.json 不一致")
        total = float(timeline.get("duration") or 0)
        if total <= 0:
            self.fail("时间轴总长为 0")
        by_scene = {scene["id"]: scene for scene in timeline["scenes"]}
        for scene in self.film.get("scenes", []):
            scene_tl = by_scene.get(scene.get("id"))
            if not scene_tl:
                self.fail(f"时间轴缺少镜头 {scene.get('id')}")
            for line in scene.get("narration", []):
                if line.get("mark") and line["mark"] not in (scene_tl.get("marks") or {}):
                    self.fail(f"镜头 {scene['id']} 的 mark {line['mark']!r} 没有时间点")
        for scene_tl in timeline["scenes"]:
            for chunk in scene_tl.get("chunks", []):
                path = self.project / chunk.get("file", f"assets/tts/{chunk['id']}.wav")
                if not path.exists():
                    self.fail(f"旁白文件缺失：{path.relative_to(self.project)}")
        new_starts = {c.get("id"): c.get("start")
                      for scene in timeline["scenes"] for c in scene.get("chunks", [])}
        moved = [cid for cid, start in new_starts.items()
                 if old_starts.get(cid) is not None and abs(float(start) - float(old_starts[cid])) > 0.001]
        delta = total - old_duration if old_duration else None
        self.timeline = timeline
        self.report["timeline"] = {
            "before": old_duration or None,
            "after": total,
            "delta": round(delta, 3) if delta is not None else None,
            "target": (self.film.get("meta", {}) or {}).get("targetSeconds"),
            "scenes": len(timeline["scenes"]),
            "captions": len(timeline.get("captions", [])),
            "movedChunks": moved,
        }
        self.step("timeline", skipped=False, **self.report["timeline"])
        if not timeline.get("captions"):
            self.fail("时间轴没有字幕")

    # -- music / mix -------------------------------------------------------
    def rebuild_music(self) -> None:
        self.require("ffprobe")
        music_path = self.project / "assets" / "music.wav"
        old_total = self.report["timeline"].get("before") or 0
        new_total = self.report["timeline"]["after"]
        delta = abs(new_total - old_total) if old_total else None
        need = (not music_path.exists()) or delta is None or delta > 0.05
        settings, args = music_settings(self.music_evidence)
        settings["recorded"] = bool(self.music_evidence)
        if not need:
            try:
                actual = duration(music_path)
            except SystemExit:
                actual = 0
            if actual + 0.15 < new_total:
                need = True
        if not need:
            self.step("music", skipped=True, **settings)
            return
        if not self.music_evidence:
            self.warn("没有 evidence/music.json，配乐按默认 curious/92 bpm/seed 7418 重生成")
        self.say("配乐：重生成")
        rc, out, err = run_cmd(python_script("music.py")
                               + ["--project", str(self.project)] + args, self.project)
        if rc != 0:
            self.fail("生成配乐失败：\n" + tail(out + "\n" + err))
        self.music_evidence = read_json(self.project / "evidence" / "music.json", {}) or {}
        actual = duration(music_path)
        if actual + 0.15 < new_total:
            self.fail(f"配乐只有 {actual:.2f}s，短于时间轴 {new_total:.2f}s")
        self.step("music", skipped=False, **settings)

    def rebuild_mix(self) -> None:
        self.require("ffmpeg")
        mix_path = self.project / "assets" / "mix.wav"
        old_total = self.report["timeline"].get("before") or 0
        new_total = self.report["timeline"]["after"]
        moved = bool(self.report["timeline"].get("movedChunks"))
        need = (self.audio_changed or moved or not mix_path.exists() or not old_total
                or abs(new_total - old_total) > 0.001)
        if not need:
            try:
                mix_actual = duration(mix_path)
            except SystemExit:
                mix_actual = 0
            if abs(mix_actual - new_total) > 0.5:
                need = True
        if not need:
            self.step("mix", skipped=True)
            return
        self.say("混音：重生成")
        rc, out, err = run_cmd(python_script("mix_audio.py")
                               + ["--project", str(self.project)], self.project)
        if rc != 0:
            self.fail("混音失败：\n" + tail(out + "\n" + err))
        evidence = read_json(self.project / "evidence" / "audio-mix.json", {}) or {}
        chunk_count = evidence.get("chunks")
        if isinstance(chunk_count, int) and chunk_count != len(self.lines):
            self.fail(f"混音只排了 {chunk_count} 段旁白，应为 {len(self.lines)} 段")
        mixed = float(evidence.get("duration") or 0)
        if abs(mixed - new_total) > 0.25:
            self.fail(f"混音时长 {mixed:.2f}s 与时间轴 {new_total:.2f}s 不一致")
        lufs = evidence.get("measuredLufs")
        peak = evidence.get("truePeak")
        if lufs is not None and abs(float(lufs) + 16) > 0.7:
            self.warn(f"混音响度 {float(lufs):.1f} LUFS，偏离 −16 LUFS")
        if peak is not None and float(peak) > -1.5:
            self.warn(f"混音真峰值 {float(peak):.1f} dBFS，高于 −1.5 dBFS 的目标")
        self.step("mix", skipped=False, lufs=lufs, truePeak=peak,
                  chunks=chunk_count, duration=mixed)

    # -- build / check / render -------------------------------------------
    def rebuild_build(self) -> None:
        self.require("node")
        rc, out, err = run_cmd(["node", "build.mjs"], self.project, timeout=600)
        if rc != 0:
            self.fail("构建失败：\n" + tail(out + "\n" + err))
        report = read_json(self.project / "build-report.json", {}) or {}
        if report.get("estimatedTimeline"):
            self.fail("构建用了估算时间轴；先跑真人录音或 tts.py，再重排时间轴")
        if not report.get("audio"):
            self.fail("构建结果没有音频；先跑 mix_audio.py")
        timeline_total = float(self.report["timeline"]["after"])
        if abs(float(report.get("duration") or 0) - timeline_total) > 0.02:
            self.fail("build-report 的时长与 timeline.json 不一致")
        warnings = [str(w) for w in report.get("warnings", [])]
        missing_marks = [w for w in warnings if MARK_WARNING.search(w)]
        if missing_marks and not self.args.allow_missing_marks:
            self.fail("画面揭示点找不到台词时间：\n" + "\n".join(f"- {w}" for w in missing_marks)
                      + "\n把 mark 挪到替代句，或删掉对应的 data-reveal，再加 --allow-missing-marks 跳过")
        for warning in warnings:
            if warning not in missing_marks:
                self.warn(warning)
        if not report.get("captions"):
            self.warn("构建结果没有字幕")
        self.step("build", scenes=len(report.get("scenes", [])),
                  captions=report.get("captions"), duration=report.get("duration"),
                  warnings=len(warnings), missingMarks=len(missing_marks))

    def run_check(self) -> None:
        should = self.args.check if self.args.check is not None else self.args.render != "none"
        if not should:
            self.step("check", ran=False, reason="未请求正式渲染")
            return
        if not shutil.which("npx"):
            if self.args.render == "delivery":
                self.fail("找不到 npx，无法跑 hyperframes check；正式片不能跳过这一步")
            self.warn("找不到 npx，跳过 hyperframes check")
            self.step("check", ran=False, reason="npx missing")
            return
        self.say(f"检查：hyperframes@{HYPERFRAMES_VERSION} check")
        rc, out, err = run_cmd(
            ["npx", "--yes", f"hyperframes@{HYPERFRAMES_VERSION}", "check"],
            self.project, timeout=1800,
        )
        if rc == 0:
            self.step("check", ran=True, ok=True)
            return
        blob = out + "\n" + err
        infrastructure = rc == 127 or "npm error" in blob or "command not found" in blob
        if infrastructure and self.args.render != "delivery":
            self.warn("hyperframes check 没能运行：\n" + tail(blob, 6))
            self.step("check", ran=False, reason="environment")
            return
        self.fail("hyperframes check 未通过：\n" + tail(blob))

    def render(self) -> None:
        quality = self.args.render
        if quality == "none":
            self.step("render", skipped=True, reason="未请求")
            return
        if not shutil.which("npx"):
            self.fail("找不到 npx，无法渲染")
        output = self.project / "renders" / ("draft.mp4" if quality == "draft" else "final.mp4")
        output.parent.mkdir(parents=True, exist_ok=True)
        output_arg = str(output.relative_to(self.project))
        if not self.args.json:
            print(f"渲染中（{quality}）→ {output.relative_to(self.project)} …", flush=True)
        rc, out, err = run_cmd(
            ["npx", "--yes", f"hyperframes@{HYPERFRAMES_VERSION}", "render",
             "--quality", quality, "--output", output_arg],
            self.project, timeout=7200,
        )
        if rc != 0 or not output.exists():
            self.fail("渲染失败：\n" + tail(out + "\n" + err))
        probe = ffprobe_json(output)
        streams = probe.get("streams", [])
        video_duration = float(probe.get("format", {}).get("duration") or 0)
        if not any(s.get("codec_type") == "audio" for s in streams):
            self.fail("渲染结果没有音轨")
        timeline_total = float(self.report["timeline"]["after"])
        if abs(video_duration - timeline_total) > max(1.2, timeline_total * 0.02):
            self.warn(f"成片 {video_duration:.2f}s 与时间轴 {timeline_total:.2f}s 不一致")
        if quality == "delivery" and not (self.report["steps"].get("check") or {}).get("ran"):
            self.warn("正式片没有跑 hyperframes check")
        self.step("render", skipped=False, quality=quality,
                  file=str(output.relative_to(self.project)), duration=video_duration)
        if quality == "delivery":
            rc, out, err = run_cmd(
                python_script("check_delivery.py")
                + ["--project", str(self.project), "--video", str(output), "--json"],
                self.project, timeout=1800,
            )
            try:
                report = json.loads(out) if out.strip() else {}
            except json.JSONDecodeError:
                report = {}
            for warning in report.get("warnings", []):
                self.warn(str(warning))
            if rc != 0 or report.get("errors"):
                problems = report.get("errors") or [tail(out + "\n" + err)]
                self.fail("交付检查未通过：\n" + "\n".join(f"- {p}" for p in problems))
            self.report["steps"]["render"]["delivery"] = {
                "lufs": (report.get("info") or {}).get("lufs"),
                "truePeak": (report.get("info") or {}).get("truePeak"),
                "firstFrame": (report.get("info") or {}).get("firstFrame"),
            }

    # -- dry run / summary -------------------------------------------------
    def print_plan(self) -> None:
        changes = []
        for item in self.diff["changed"]:
            changes.append({"kind": "changed", "id": item["id"],
                            "from": (item.get("old") or {}).get("caption") or "",
                            "to": item["caption"]})
        for item in self.diff["added"]:
            changes.append({"kind": "added", "id": item["id"], "from": "", "to": item["caption"]})
        for chunk in self.diff["removed"]:
            changes.append({"kind": "removed", "id": chunk.get("id"),
                            "from": chunk.get("caption") or "", "to": ""})
        self.report["changes"] = changes
        if self.human and self.audio_changed:
            self.report["recordingTodo"] = self.recording_todo
        lines = []
        if self.human and self.audio_changed:
            lines.append(f"真人旁白：{len(self.diff['changed']) + len(self.diff['added'])} 句要重录/改名；"
                         "先跑不带 --import 的本命令看清单，录完加 --import")
        elif self.args.revoice:
            voice = self.voice
            label = f"{voice['provider']}/{voice.get('voice', '')}".rstrip("/")
            lines.append(f"配音：按 film.json 重录全部 {len(self.lines)} 句（{label}）")
        elif self.audio_changed:
            voice = self.voice
            label = f"{voice['provider']}/{voice.get('voice', '')}".rstrip("/")
            lines.append(f"配音：重录 {len(self.diff['changed']) + len(self.diff['added'])} 句"
                         f"（{label}），其余走缓存")
        else:
            lines.append("配音：旁白文本没变，跳过")
        lines.append("时间轴：按实际语音重排，字幕和 mark 跟着走")
        if self.audio_changed:
            lines.append("配乐：按新时长决定；沿用 evidence/music.json 的 mood/bpm/seed")
            lines.append("混音：重做旁白让位与 −16 LUFS 标准化")
        else:
            lines.append("配乐/混音：时长不变则跳过")
        lines.append("构建：重建 HyperFrames，检查 mark、时长、字幕")
        if self.args.render != "none":
            lines.append(f"检查/渲染：hyperframes check + {self.args.render} 渲染")
        if self.stale_hits:
            lines.append(f"提醒：{len(self.stale_hits)} 处画面文字还是旧台词（见下）")
        self.report["plan"] = lines
        if not self.args.json:
            print(f"\n计划 · {self.report.get('title') or self.project.name}")
            for line in lines:
                print("  - " + line)
            if changes:
                print("  改动")
                for row in changes[:8]:
                    if row["kind"] == "changed":
                        print(f"    ~ {row['id']}：{row['from']} → {row['to']}")
                    elif row["kind"] == "added":
                        print(f"    + {row['id']}：{row['to']}")
                    else:
                        print(f"    - {row['id']}：{row['from']}")
                if len(changes) > 8:
                    print(f"    … 另有 {len(changes) - 8} 处")
            if self.human and self.audio_changed:
                print("  take")
                for row in self.recording_todo:
                    print(f"    {row['id']:<14} {row['action']:<6} {row['detail']}")
            for hit in self.stale_hits[:6]:
                print(f"    · {hit['path']}：{hit['text']}")

    def print_summary(self) -> None:
        steps = self.report["steps"]
        print(f"\n改台词 · {self.report.get('title') or self.project.name}")
        content = steps.get("content")
        if content:
            print(f"  内容     {content.get('errors', 0)} error / {content.get('warnings', 0)} warning")
        voice = steps.get("voice") or {}
        if voice.get("needsRecording"):
            print("  配音     真人录音待补：" + ", ".join(row["id"] for row in voice.get("todo", [])))
        elif voice.get("skipped"):
            print("  配音     跳过（文本没变）")
        elif voice.get("imported"):
            print(f"  配音     真人录音已导入 {voice.get('chunks')} 段")
        elif voice.get("resynthesized") is not None:
            ids = voice.get("resynthesized", [])
            label = f"{voice.get('provider') or '?'}/{voice.get('voice') or ''}".rstrip("/")
            example = ""
            if ids:
                first = ids[0]
                old_new = (voice.get("durations") or {}).get(first) or []
                if len(old_new) == 2 and old_new[1] is not None:
                    example = f" · {first} {old_new[0] or '?'}s → {old_new[1]}s"
                else:
                    example = f" · {first}"
            print(f"  配音     重录 {len(ids)} 句（{label}）{example}")
        timeline = steps.get("timeline") or {}
        if timeline:
            before, after, delta = timeline.get("before"), timeline.get("after"), timeline.get("delta")
            stamp = f"{after:.2f}s" if after else "?"
            if before:
                stamp = f"{before:.2f}s → {after:.2f}s（{delta:+.2f}s）"
            print(f"  时间轴   {stamp} · 目标 {timeline.get('target') or '—'}s · "
                  f"{timeline.get('captions')} 条字幕")
        music = steps.get("music") or {}
        if music:
            mode = "跳过" if music.get("skipped") else "重生成"
            if music.get("recorded"):
                stamp = (f"{music.get('mood')} · {music.get('bpm') or '默认'} bpm · "
                         f"seed {music.get('seed') or '默认'}")
            elif music.get("skipped"):
                stamp = "参数未记录，沿用现有配乐"
            else:
                stamp = "参数未记录，按默认参数重生成"
            print(f"  配乐     {mode} · {stamp}")
        mix = steps.get("mix") or {}
        if mix:
            if mix.get("skipped"):
                print("  混音     跳过（旁白与时长都没变）")
            else:
                lufs = mix.get("lufs")
                peak = mix.get("truePeak")
                loud = f"{float(lufs):.1f} LUFS" if lufs is not None else "LUFS 未测"
                loud += f" · true peak {float(peak):.1f} dBFS" if peak is not None else ""
                print(f"  混音     {loud} · {mix.get('chunks')} 段")
        build = steps.get("build") or {}
        if build:
            print(f"  构建     {build.get('scenes')} 镜 · {build.get('captions')} 字幕 · "
                  f"mark 缺失 {build.get('missingMarks', 0)}")
        check = steps.get("check") or {}
        if check.get("ran"):
            print("  检查     hyperframes check " + ("通过" if check.get("ok") else "未通过"))
        else:
            print("  检查     跳过（" + str(check.get("reason") or "未请求正式渲染") + "）")
        render = steps.get("render") or {}
        if render.get("file"):
            print(f"  渲染     {render.get('file')} · {float(render.get('duration') or 0):.2f}s")
        else:
            print("  渲染     未请求（--render draft|delivery）")
        if self.warnings:
            print("  提醒")
            for warning in self.warnings[:10]:
                print(f"    - {warning}")
            if len(self.warnings) > 10:
                print(f"    … 另有 {len(self.warnings) - 10} 条，见 evidence/revise.json")
        if self.stale_hits:
            print("  旧台词仍在画面里")
            for hit in self.stale_hits[:6]:
                print(f"    - {hit['path']}：{hit['text']}")
        if self.errors:
            print("  错误")
            for error in self.errors:
                print(f"    - {error}")
        if self.exit_code == 2:
            print("  下一步   " + self.rerun_command("--import"))
        elif self.args.render == "none" and not self.errors:
            print("  下一步   " + self.rerun_command("--render", "draft"))
        print(f"  报告     evidence/revise.json · 用时 {time.perf_counter() - self.started:.1f}s")

    def finish(self) -> int:
        self.report["ok"] = (not self.errors and self.exit_code == 0
                             and not (self.args.strict and self.warnings))
        self.report["elapsedSeconds"] = round(time.perf_counter() - self.started, 1)
        write_json(self.project / "evidence" / "revise.json", self.report)
        if self.args.json:
            print(json.dumps(self.report, ensure_ascii=False, indent=1))
        elif self.args.dry_run:
            print(f"  报告     evidence/revise.json · 用时 {self.report['elapsedSeconds']:.1f}s")
        else:
            self.print_summary()
        if self.errors:
            return 1
        if self.exit_code:
            return self.exit_code
        if self.args.strict and self.warnings:
            return 1
        return 0

    # -- orchestration -----------------------------------------------------
    def run(self) -> int:
        if not self.lines:
            self.fail("film.json 没有旁白句子")
        if self.args.import_takes and not self.human:
            self.fail("当前旁白不是真人录音，不需要 --import")
        if self.args.revoice and self.human:
            self.fail("真人录音不能用 --revoice；重录后走 --import")
        self.content_check(pre=True)
        if self.lost_marks:
            self.warn("这些 mark 从 film.json 里删掉了："
                      + ", ".join(f"{scene}:{mark}" for scene, mark in self.lost_marks))
        if self.new_marks:
            self.warn("新增 mark：" + ", ".join(f"{scene}:{mark}" for scene, mark in self.new_marks))
        if self.stale_hits:
            for hit in self.stale_hits[:8]:
                self.warn(f"画面文字可能还是旧台词：{hit['path']}「{hit['text']}」")
        if self.diff["removed"]:
            self.warn("删掉了这些句子：" + ", ".join(str(c.get("id")) for c in self.diff["removed"]))
        self.check_script_drift()
        if self.args.dry_run:
            self.print_plan()
            return self.finish()

        if self.human:
            self.human_step()
            if self.exit_code:
                return self.finish()
        elif self.audio_changed:
            self.synthesize()
        else:
            self.step("voice", skipped=True, reason="文本没变")

        self.rebuild_timeline()
        self.content_check(pre=False)
        self.rebuild_music()
        self.rebuild_mix()
        self.rebuild_build()
        self.run_check()
        self.render()
        return self.finish()

    def check_script_drift(self) -> None:
        script = self.project / "SCRIPT.md"
        if not script.exists():
            return
        try:
            body = compact(script.read_text(encoding="utf-8"))
        except OSError:
            return
        touched = self.diff["changed"] + self.diff["added"] + self.diff["caption_changed"]
        missing = [line["caption"] for line in touched
                   if compact(line["caption"]) and compact(line["caption"]) not in body]
        if missing:
            self.warn(f"SCRIPT.md 还没同步这 {len(missing)} 句："
                      + "；".join(missing[:3]) + ("…" if len(missing) > 3 else ""))


def parse_args(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(
        description="改台词后一条命令重建：增量重录、重排、配乐、混音、构建，可选渲染。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=("示例：\n"
                "  python3 scripts/revise.py --project ./film\n"
                "  python3 scripts/revise.py --project ./film --render draft\n"
                "  python3 scripts/revise.py --project ./film --render delivery\n"
                "  python3 scripts/revise.py --project ./film --import"),
    )
    ap.add_argument("--project", type=Path, default=Path("."), help="工程目录（含 film.json）")
    ap.add_argument("--dry-run", action="store_true", help="只检查并打印计划，不动音频")
    ap.add_argument("--render", choices=["none", "draft", "delivery"], default="none",
                    help="none 只重建；draft 出草稿；delivery 出正式片并跑交付检查")
    ap.add_argument("--import", dest="import_takes", action="store_true",
                    help="真人录音：录完 take 后导入并重建")
    ap.add_argument("--revoice", action="store_true",
                    help="按 film.json 的 voice 设置重录全部（默认沿用已有音色）")
    ap.add_argument("--voice-dir", type=Path, help="provider=file 时的外部音频目录")
    ap.add_argument("--check", dest="check", action="store_true", default=None,
                    help="强制跑 hyperframes check")
    ap.add_argument("--no-check", dest="check", action="store_false",
                    help="不跑 hyperframes check（正式片不建议）")
    ap.add_argument("--allow-missing-marks", action="store_true",
                    help="允许画面 reveal 找不到 mark（默认视为错误）")
    ap.add_argument("--strict", action="store_true", help="有 warning 也返回非零")
    ap.add_argument("--json", action="store_true", help="输出机器可读报告")
    ap.add_argument("--verbose", "-v", action="store_true", help="打印每一步的命令和进度")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project = args.project.expanduser().resolve()
    revision = None
    try:
        revision = Revision(args, project)
        return revision.run()
    except SystemExit as exc:
        code = int(exc.code or 0)
        if code != 0 and revision is not None:
            revision.report["ok"] = False
            revision.report["errors"] = revision.errors or [str(exc)]
            try:
                write_json(revision.project / "evidence" / "revise.json", revision.report)
            except OSError:
                pass
        return code
    except ReviseError as exc:
        if revision is not None:
            revision.report["ok"] = False
            revision.report["errors"] = revision.errors or [str(exc)]
            revision.report["elapsedSeconds"] = round(time.perf_counter() - revision.started, 1)
            try:
                write_json(revision.project / "evidence" / "revise.json", revision.report)
            except OSError:
                pass
            if args.json:
                print(json.dumps(revision.report, ensure_ascii=False, indent=1))
            else:
                for warning in revision.warnings[:6]:
                    print(f"warning: {warning}", file=sys.stderr)
                print("report: evidence/revise.json", file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
