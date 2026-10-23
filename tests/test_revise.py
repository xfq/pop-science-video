#!/usr/bin/env python3
"""Tests for the one-command revision helpers and dry-run plan."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from revise import (  # noqa: E402
    Revision,
    collect_lines,
    parse_args,
    diff_narration,
    mark_changes,
    music_settings,
    stale_screen_text,
    stale_takes,
    voice_config,
)
from tts import resolve_provider  # noqa: E402


def sample_film() -> dict:
    return {
        "meta": {
            "title": "测试片",
            "slug": "test",
            "language": "zh-CN",
            "takeaway": "一句话结论。",
            "targetSeconds": 30,
            "voice": {
                "provider": "auto", "voice": "Tingting", "rate": 180,
                "edgeVoice": "zh-CN-YunxiNeural", "edgeRate": "+8%", "lexicon": {},
            },
        },
        "scenes": [
            {"id": "hook", "type": "hook", "note": "旧句。", "narration": [
                {"caption": "旧句。", "tts": "旧句。", "mark": "q"},
                {"caption": "第二句。", "tts": "第二句。"},
            ]},
            {"id": "body", "type": "statement", "line1": "正题。", "narration": [
                {"caption": "正题。", "tts": "正题。", "mark": "one"},
            ]},
            {"id": "outro", "type": "outro", "next": "下期", "narration": [
                {"caption": "收尾。", "tts": "收尾。", "mark": "end"},
            ]},
        ],
    }


def sample_manifest(film: dict, provider: str = "say", voice: str = "Tingting",
                    rate: int = 190) -> dict:
    lines = collect_lines(film, human=(provider == "human"))
    return {
        "provider": provider, "voice": voice, "rate": rate, "edgeRate": "+8%",
        "chunks": [
            {"id": line["id"], "scene": line["scene"], "i": line["i"],
             "text": line["spoken"], "caption": line["caption"],
             "dur": 2.0, "key": "key-" + line["id"], "provider": provider, "voice": voice}
            for line in lines
        ],
    }


class CollectTests(unittest.TestCase):
    def test_lexicon_applies_only_to_tts(self):
        film = sample_film()
        film["meta"]["voice"]["lexicon"] = {"0.1": "零点一"}
        film["scenes"][0]["narration"][0]["tts"] = "0.1 加 0.2"
        self.assertEqual(collect_lines(film)[0]["spoken"], "零点一 加 0.2")
        self.assertEqual(collect_lines(film, human=True)[0]["spoken"], "0.1 加 0.2")

    def test_caption_falls_back_to_tts(self):
        film = sample_film()
        del film["scenes"][0]["narration"][0]["caption"]
        self.assertEqual(collect_lines(film)[0]["caption"], "旧句。")


class DiffTests(unittest.TestCase):
    def setUp(self):
        self.film = sample_film()
        self.manifest = sample_manifest(self.film)

    def test_caption_only_is_not_audio_change(self):
        film = copy.deepcopy(self.film)
        film["scenes"][0]["narration"][0]["caption"] = "换个字幕。"
        diff = diff_narration(collect_lines(film), self.manifest)
        self.assertEqual(diff["changed"], [])
        self.assertEqual([line["id"] for line in diff["caption_changed"]], ["hook-000"])

    def test_reword_add_remove(self):
        film = copy.deepcopy(self.film)
        film["scenes"][0]["narration"][0]["tts"] = "新句。"
        film["scenes"][0]["narration"][0]["caption"] = "新句。"
        film["scenes"][2]["narration"].append({"caption": "补充。", "tts": "补充。"})
        film["scenes"][1]["narration"] = []
        diff = diff_narration(collect_lines(film), self.manifest)
        self.assertEqual([line["id"] for line in diff["changed"]], ["hook-000"])
        self.assertEqual([line["id"] for line in diff["added"]], ["outro-001"])
        self.assertEqual([chunk["id"] for chunk in diff["removed"]], ["body-000"])

    def test_inserted_line_marks_shifted_audio(self):
        film = copy.deepcopy(self.film)
        film["scenes"][0]["narration"].insert(1, {"caption": "插入。", "tts": "插入。"})
        diff = diff_narration(collect_lines(film), self.manifest)
        changed = {line["id"]: line for line in diff["changed"]}
        added = {line["id"]: line for line in diff["added"]}
        # The old hook-001 take still exists, so the inserted line replaces it
        # in place and the old audio has to move down to hook-002.
        self.assertIn("hook-001", changed)
        self.assertFalse(changed["hook-001"]["shifted"])
        self.assertTrue(added["hook-002"]["shifted"])
        self.assertEqual(added["hook-002"]["source"]["id"], "hook-001")

    def test_reworded_line_is_not_shifted(self):
        film = copy.deepcopy(self.film)
        film["scenes"][0]["narration"][0]["tts"] = "完全新的一句。"
        diff = diff_narration(collect_lines(film), self.manifest)
        self.assertFalse(diff["changed"][0]["shifted"])
        self.assertIsNone(diff["changed"][0]["source"])


class ScreenTextTests(unittest.TestCase):
    def test_old_caption_left_in_scene_field(self):
        film = sample_film()
        film["scenes"][0]["note"] = "旧句子。"
        film["scenes"][0]["narration"][0]["caption"] = "旧句子。"
        film["scenes"][0]["narration"][0]["tts"] = "旧句子。"
        manifest = sample_manifest(film)
        film["scenes"][0]["narration"][0] = {"caption": "新句。", "tts": "新句。", "mark": "q"}
        diff = diff_narration(collect_lines(film), manifest)
        hits = stale_screen_text(film, [diff["changed"][0]["old"]])
        self.assertTrue(any(hit["path"] == "scenes[0].note" and hit["text"] == "旧句子。"
                            for hit in hits), hits)


class MarkTests(unittest.TestCase):
    def test_lost_mark_detected(self):
        film = sample_film()
        del film["scenes"][0]["narration"][0]["mark"]
        timeline = {"scenes": [
            {"id": "hook", "marks": {"q": 0.5}, "chunks": []},
            {"id": "body", "marks": {"one": 3.0}, "chunks": []},
            {"id": "outro", "marks": {"end": 6.0}, "chunks": []},
        ]}
        added, lost = mark_changes(collect_lines(film), timeline)
        self.assertEqual(added, [])
        self.assertIn(("hook", "q"), lost)


class VoiceTests(unittest.TestCase):
    def test_manifest_voice_wins_over_film_meta(self):
        film = sample_film()  # meta says rate 180
        manifest = sample_manifest(film, provider="say", voice="Tingting", rate=190)
        cfg = voice_config(film, manifest)
        self.assertEqual(cfg["provider"], "say")
        self.assertEqual(cfg["voice"], "Tingting")
        self.assertEqual(cfg["rate"], 190)

    def test_revoice_uses_film_meta(self):
        film = sample_film()
        film["meta"]["voice"]["provider"] = "say"
        manifest = sample_manifest(film, provider="say", voice="Tingting", rate=190)
        cfg = voice_config(film, manifest, revoice=True)
        self.assertEqual(cfg["rate"], 180)

    def test_revoice_auto_keeps_recorded_provider(self):
        film = sample_film()  # meta provider is auto
        manifest = sample_manifest(film, provider="say", voice="Tingting", rate=190)
        cfg = voice_config(film, manifest, revoice=True)
        self.assertEqual(cfg["provider"], "say")
        self.assertEqual(cfg["rate"], 180)

    def test_missing_manifest_keeps_film_meta(self):
        film = sample_film()
        cfg = voice_config(film, {})
        self.assertEqual(cfg["provider"], "auto")

    def test_tts_provider_resolution(self):
        self.assertEqual(resolve_provider("edge", {"provider": "say"}, {"provider": "auto"}), "edge")
        self.assertEqual(resolve_provider(None, {"provider": "say"}, {"provider": "auto"}), "say")
        self.assertEqual(resolve_provider(None, {"provider": "human"}, {"provider": "edge"}), "edge")
        self.assertEqual(resolve_provider(None, {}, {"provider": "auto"}), "auto")


class MusicTests(unittest.TestCase):
    def test_keeps_mood_bpm_and_seed(self):
        settings, args = music_settings({"mood": "focused", "bpm": 84, "seed": 7})
        self.assertEqual(settings, {"mood": "focused", "bpm": 84, "seed": 7})
        self.assertEqual(args, ["--mood", "focused", "--bpm", "84", "--seed", "7"])

    def test_unknown_mood_falls_back(self):
        settings, args = music_settings({"mood": "loud"})
        self.assertEqual(settings["mood"], "curious")
        self.assertEqual(args[0:2], ["--mood", "curious"])


class StaleTakeTests(unittest.TestCase):
    def test_unchanged_take_hash_is_flagged(self):
        before = {"chunks": [{"id": "hook-000", "text": "旧句。", "key": "abc"}]}
        after = {"chunks": [{"id": "hook-000", "text": "新句。", "key": "abc"}]}
        self.assertEqual(stale_takes(before, after, [{"id": "hook-000", "spoken": "新句。"}]),
                         ["hook-000"])

    def test_new_take_hash_passes(self):
        before = {"chunks": [{"id": "hook-000", "text": "旧句。", "key": "abc"}]}
        after = {"chunks": [{"id": "hook-000", "text": "新句。", "key": "def"}]}
        self.assertEqual(stale_takes(before, after, [{"id": "hook-000", "spoken": "新句。"}]), [])


class HumanTodoTests(unittest.TestCase):
    def test_inserted_line_asks_for_rename_then_rerecord(self):
        film = sample_film()
        manifest = sample_manifest(film, provider="human")
        film["scenes"][0]["narration"].insert(1, {"caption": "插入。", "tts": "插入。"})
        with tempfile.TemporaryDirectory(prefix="cs-todo-") as td:
            project = Path(td)
            (project / "film.json").write_text(json.dumps(film, ensure_ascii=False), encoding="utf-8")
            (project / "assets" / "tts").mkdir(parents=True)
            (project / "assets" / "tts" / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            revision = Revision(parse_args(["--project", td, "--dry-run"]), project)
            todo = {row["id"]: row for row in revision.recording_todo}
            self.assertEqual(todo["hook-001"]["action"], "重录")
            self.assertEqual(todo["hook-002"]["action"], "改名")
            self.assertIn("hook-001.wav", todo["hook-002"]["detail"])


class DryRunTests(unittest.TestCase):
    def project(self, td: str) -> Path:
        project = Path(td)
        (project / "evidence").mkdir()
        film = sample_film()
        (project / "film.json").write_text(json.dumps(film, ensure_ascii=False), encoding="utf-8")
        (project / "facts.json").write_text('{"claims": [], "analogies": []}', encoding="utf-8")
        manifest = sample_manifest(film)
        (project / "assets" / "tts").mkdir(parents=True)
        (project / "assets" / "tts" / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return project

    def run_revise(self, project: Path) -> subprocess.CompletedProcess:
        return subprocess.run([
            sys.executable, str(ROOT / "scripts" / "revise.py"),
            "--project", str(project), "--dry-run", "--json",
        ], capture_output=True, text=True)

    def test_dry_run_plan_without_touching_audio(self):
        with tempfile.TemporaryDirectory(prefix="cs-revise-") as td:
            project = self.project(td)
            proc = self.run_revise(project)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(report["dryRun"])
            self.assertFalse(report["lines"]["audioChanged"])
            self.assertTrue(any("旁白文本没变" in row for row in report["plan"]))
            self.assertFalse((project / "assets" / "mix.wav").exists())

    def test_dry_run_detects_changed_line(self):
        with tempfile.TemporaryDirectory(prefix="cs-revise-") as td:
            project = self.project(td)
            film = json.loads((project / "film.json").read_text(encoding="utf-8"))
            film["scenes"][0]["narration"][0]["tts"] = "新句。"
            film["scenes"][0]["narration"][0]["caption"] = "新句。"
            (project / "film.json").write_text(json.dumps(film, ensure_ascii=False), encoding="utf-8")
            proc = self.run_revise(project)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(report["lines"]["audioChanged"])
            self.assertEqual(report["lines"]["changed"], ["hook-000"])
            self.assertTrue(any("重录 1 句" in row for row in report["plan"]))


class HumanImportTests(unittest.TestCase):
    def test_stale_take_is_rejected_after_text_change(self):
        with tempfile.TemporaryDirectory(prefix="cs-human-revise-") as td:
            project = Path(td)
            film = sample_film()
            (project / "film.json").write_text(json.dumps(film, ensure_ascii=False), encoding="utf-8")
            (project / "facts.json").write_text('{"claims": [], "analogies": []}', encoding="utf-8")
            takes = project / "recording" / "takes"
            takes.mkdir(parents=True)
            for i, line in enumerate(collect_lines(film)):
                subprocess.run([
                    "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency={440 + i * 40}:duration=0.8",
                    str(takes / f"{line['id']}.wav"),
                ], check=True)
            imported = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "import_recordings.py"),
                "--project", str(project), "--force",
            ], capture_output=True, text=True)
            self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)

            film["scenes"][0]["narration"][0]["tts"] = "新句子。"
            film["scenes"][0]["narration"][0]["caption"] = "新句子。"
            (project / "film.json").write_text(json.dumps(film, ensure_ascii=False), encoding="utf-8")
            proc = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "revise.py"),
                "--project", str(project), "--import",
            ], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("take 没换", proc.stderr)
            self.assertIn("hook-000", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
