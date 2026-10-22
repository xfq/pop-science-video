#!/usr/bin/env python3
"""Tests for the human recording kit and importer helpers."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from import_recordings import discover_takes  # noqa: E402


class DiscoveryTests(unittest.TestCase):
    def test_accepts_common_names_and_formats(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            for name in ("01-hook-000.M4A", "hook_001.mp3", "pivot-002.aiff", "outro-000.wav"):
                (folder / name).write_bytes(b"x")
            found, duplicates = discover_takes(folder, ["hook", "pivot", "outro"])
            self.assertEqual(set(found), {"hook-000", "hook-001", "pivot-002", "outro-000"})
            self.assertEqual(duplicates, [])

    def test_longest_scene_id_wins(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "s1-a-003.wav").write_bytes(b"x")
            found, _ = discover_takes(folder, ["s1", "s1-a"])
            self.assertIn("s1-a-003", found)

    def test_ignores_unrelated_files(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "notes.txt").write_text("not audio")
            (folder / "hook-000.wav").write_bytes(b"x")
            found, _ = discover_takes(folder, ["hook"])
            self.assertEqual(set(found), {"hook-000"})


class KitTests(unittest.TestCase):
    def test_demo_kit_has_every_line(self):
        demo = ROOT / "examples" / "float-0-1-0-2"
        if not (demo / "film.json").exists():
            self.skipTest("demo missing")
        with tempfile.TemporaryDirectory() as td:
            proc = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "make_recording_kit.py"),
                "--project", str(demo), "--out", td, "--force",
            ], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            lines = json.loads((Path(td) / "lines.json").read_text(encoding="utf-8"))["lines"]
            self.assertEqual(len(lines), 33)
            self.assertEqual(lines[0]["file"], "hook-000.wav")
            self.assertTrue((Path(td) / "NARRATION.md").exists())


class ImportTests(unittest.TestCase):
    def test_import_builds_human_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / "film.json").write_text(json.dumps({
                "meta": {"language": "zh-CN"},
                "scenes": [{"id": "hook", "type": "hook", "narration": [
                    {"caption": "第一句。", "tts": "第一句。"},
                    {"caption": "第二句。", "tts": "第二句。"},
                ]}],
            }, ensure_ascii=False), encoding="utf-8")
            takes = project / "recording" / "takes"
            takes.mkdir(parents=True)
            for i in range(2):
                subprocess.run([
                    "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency={440 + i * 80}:duration=0.8",
                    str(takes / f"hook-{i:03d}.wav"),
                ], check=True)
            proc = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "import_recordings.py"),
                "--project", str(project), "--force",
            ], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            manifest = json.loads((project / "assets" / "tts" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["provider"], "human")
            self.assertEqual(len(manifest["chunks"]), 2)
            self.assertTrue(all(c["provider"] == "human" for c in manifest["chunks"]))
            self.assertTrue(all(c["dur"] > 0 for c in manifest["chunks"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
