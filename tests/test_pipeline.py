#!/usr/bin/env python3
"""Regression tests for the content/timeline helpers and the shipped example."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from film_lib import cap_captions, estimate_timeline, normalize_lexicon, split_caption  # noqa: E402
from check_content import banned_phrases  # noqa: E402

DEMO = ROOT / "examples" / "float-0-1-0-2"


class CaptionTests(unittest.TestCase):
    def test_decimal_is_not_split(self):
        pieces = split_caption("但计算机给出的是 0.30000000000000004。")
        self.assertEqual(len(pieces), 1)
        self.assertIn("0.30000000000000004", pieces[0])

    def test_chinese_sentences_split_when_long_enough(self):
        text = "这不是 bug，也不是 Python 的锅，更不是语言设计者的失误。是二进制。"
        pieces = split_caption(text)
        self.assertGreaterEqual(len(pieces), 2)
        self.assertEqual("".join(pieces), text)
        self.assertTrue(any(p.endswith("。") for p in pieces))

    def test_long_fragment_wraps(self):
        pieces = split_caption("一" * 70)
        self.assertTrue(all(len(p) <= 32 for p in pieces))
        self.assertEqual("".join(pieces), "一" * 70)

    def test_captions_do_not_overlap(self):
        caps = cap_captions([
            {"text": "a", "start": 0.0, "dur": 3.0},
            {"text": "b", "start": 2.0, "dur": 3.0},
        ], 10.0)
        self.assertLessEqual(caps[0]["start"] + caps[0]["dur"], caps[1]["start"])


class StyleTests(unittest.TestCase):
    def test_banned_antithesis_is_an_error(self):
        for text in (
            "这不是 bug，而是舍入。",
            "这并不是 Python 的锅，而是二进制。",
            "并非精度问题，而是范围问题。",
        ):
            with self.subTest(text=text):
                self.assertEqual([kind for kind, _ in banned_phrases(text)], ["error"])

    def test_same_sentence_variant_is_a_warning(self):
        self.assertEqual(
            [kind for kind, _ in banned_phrases("这不是 bug，是舍入。")],
            ["warning"],
        )

    def test_plain_negation_is_allowed(self):
        for text in (
            "这不是 bug。",
            "误差是确定的，不是随机噪声。",
            "这不是 bug，也不是 Python 的锅。",
        ):
            with self.subTest(text=text):
                self.assertFalse(banned_phrases(text))

    def test_check_content_rejects_banned_antithesis(self):
        with tempfile.TemporaryDirectory(prefix="cs-banned-") as td:
            project = Path(td)
            (project / "evidence").mkdir()
            film = {
                "meta": {"title": "测试", "language": "zh-CN", "takeaway": "测试"},
                "scenes": [
                    {"id": "a", "type": "hook", "narration": [
                        {"caption": "这不是 bug，而是舍入。", "tts": "这不是 bug，而是舍入。"}]},
                    {"id": "b", "type": "statement", "narration": [
                        {"caption": "正面结论。", "tts": "正面结论。"}]},
                    {"id": "c", "type": "recap", "narration": [
                        {"caption": "收尾。", "tts": "收尾。"}]},
                ],
            }
            (project / "film.json").write_text(json.dumps(film, ensure_ascii=False), encoding="utf-8")
            (project / "facts.json").write_text('{"claims": [], "analogies": []}', encoding="utf-8")
            proc = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "check_content.py"),
                "--project", str(project), "--json",
            ], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(
                any("不是……而是" in error for error in report["errors"]),
                report["errors"],
            )


class TimelineTests(unittest.TestCase):
    def film(self):
        return {
            "meta": {"language": "zh-CN", "sceneGap": 0.02},
            "scenes": [
                {"id": "a", "type": "hook", "narration": [
                    {"caption": "第一句。", "tts": "第一句。", "mark": "one"},
                    {"caption": "第二句。", "tts": "第二句。", "mark": "two"},
                ]},
                {"id": "b", "type": "recap", "narration": [
                    {"caption": "收尾。", "tts": "收尾。", "mark": "end"},
                ]},
            ],
        }

    def test_estimate_is_contiguous(self):
        timeline = estimate_timeline(self.film())
        first, second = timeline["scenes"]
        self.assertAlmostEqual(second["start"], first["start"] + first["duration"] + 0.02, places=3)
        self.assertAlmostEqual(timeline["duration"], second["start"] + second["duration"], places=3)

    def test_marks_stay_inside_scene(self):
        timeline = estimate_timeline(self.film())
        for scene in timeline["scenes"]:
            for mark, at in scene["marks"].items():
                self.assertGreaterEqual(at, scene["start"])
                self.assertLess(at, scene["start"] + scene["duration"] + 1e-6, mark)

    def test_lexicon_replaces_longest_first(self):
        out = normalize_lexicon("IEEE 754 和 754", {"754": "七五四", "IEEE 754": "I triple E 754"})
        self.assertEqual(out, "I triple E 754 和 七五四")


@unittest.skipUnless((DEMO / "film.json").exists(), "demo project not present")
class DemoTests(unittest.TestCase):
    def setUp(self):
        self.film = json.loads((DEMO / "film.json").read_text(encoding="utf-8"))
        self.facts = json.loads((DEMO / "facts.json").read_text(encoding="utf-8"))

    def test_scene_ids_and_types(self):
        ids = [s["id"] for s in self.film["scenes"]]
        self.assertEqual(len(ids), len(set(ids)))
        allowed = {"hook", "statement", "pipeline", "bitfield", "code", "compare", "numbers", "layers", "recap", "outro"}
        self.assertTrue(all(s["type"] in allowed for s in self.film["scenes"]))

    def test_every_claim_has_primary_source_and_verification(self):
        for claim in self.facts["claims"]:
            self.assertTrue(claim["sources"], claim["id"])
            self.assertTrue(claim["verification"], claim["id"])
            self.assertTrue(any(s.get("kind") == "primary" for s in claim["sources"]), claim["id"])

    def test_missing_mark_does_not_ship(self):
        timeline = json.loads((DEMO / "timeline.json").read_text(encoding="utf-8"))
        for scene in self.film["scenes"]:
            ts = next(x for x in timeline["scenes"] if x["id"] == scene["id"])
            for line in scene.get("narration", []):
                if line.get("mark"):
                    self.assertIn(line["mark"], ts["marks"], f"{scene['id']}: {line['mark']}")

    def test_template_builds(self):
        with tempfile.TemporaryDirectory(prefix="cs-build-") as td:
            tmp = Path(td)
            shutil.copytree(ROOT / "assets" / "template", tmp, dirs_exist_ok=True)
            shutil.copyfile(DEMO / "film.json", tmp / "film.json")
            shutil.copyfile(DEMO / "timeline.json", tmp / "timeline.json")
            proc = subprocess.run(["node", "build.mjs"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            index = (tmp / "index.html").read_text(encoding="utf-8")
            self.assertEqual(index.count('data-composition-src="compositions/'), 9)  # 8 scenes + captions
            hook = (tmp / "compositions" / "01-hook.html").read_text(encoding="utf-8")
            self.assertNotIn('class="topbar"', hook, "no persistent top bar")
            self.assertNotIn('class="brand"', hook, "no brand chrome")
            self.assertIn('class="foot"', hook, "footer with sources remains")
            report = json.loads((tmp / "build-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["scenes"][0]["id"], "hook")
            timeline = json.loads((tmp / "timeline.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(report["duration"], timeline["duration"], places=3)

    def test_check_content_passes(self):
        proc = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "check_content.py"),
            "--project", str(DEMO), "--json",
        ], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
