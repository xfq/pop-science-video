#!/usr/bin/env python3
"""Check the tools a CS explainer project needs, without installing anything.

  python3 scripts/check_environment.py --project ./film
  python3 scripts/check_environment.py --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent


def version_tuple(text: str) -> tuple[int, ...]:
    import re
    return tuple(int(x) for x in re.findall(r"\d+", text)[:3])


def check(name: str, ok: bool, detail: str, hint: str = "", required: bool = True) -> dict:
    return {"name": name, "ok": bool(ok), "required": required, "detail": detail, "hint": hint}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, help="film project directory to inspect")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--skip-hyperframes", action="store_true")
    args = ap.parse_args()

    checks: list[dict] = []
    checks.append(check("Python", sys.version_info >= (3, 9), platform.python_version(),
                        "Use Python 3.9+."))
    node = shutil.which("node")
    if node:
        try:
            node_version = subprocess.run([node, "-v"], capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            node_version = "unknown"
        checks.append(check("Node.js", version_tuple(node_version) >= (22, 0, 0), node_version,
                            "HyperFrames requires Node.js 22 or newer."))
    else:
        checks.append(check("Node.js", False, "not found", "Install Node.js 22+."))

    for name in ("ffmpeg", "ffprobe"):
        found = shutil.which(name)
        checks.append(check(name, bool(found), found or "not found", "Install FFmpeg and put it on PATH."))

    for module, required, hint in (
        ("numpy", True, "pip install numpy  # music and mixing"),
        ("edge_tts", False, "pip install edge-tts  # optional cloud voice"),
    ):
        spec = importlib.util.find_spec(module)
        checks.append(check(module, spec is not None, "installed" if spec else "not installed", hint, required=required))

    say = shutil.which("say")
    checks.append(check("macOS say", bool(say), say or "not available",
                         "Optional local voice fallback. On Linux use edge-tts or a recorded voice.",
                         required=False))

    if not args.skip_hyperframes:
        env = os.environ.copy()
        env.setdefault("HYPERFRAMES_SKIP_SKILLS", "1")
        hf = shutil.which("hyperframes")
        cmd = [hf, "--version"] if hf else ["npx", "--yes", "hyperframes@0.8.184", "--version"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
            text = (proc.stdout or proc.stderr or "").strip().splitlines()
            detail = text[-1] if text else f"exit {proc.returncode}"
            checks.append(check("HyperFrames CLI", proc.returncode == 0, detail,
                                "Install with: npm i -g hyperframes@0.8.184 (or let npx fetch it)."))
        except Exception as exc:
            checks.append(check("HyperFrames CLI", False, str(exc),
                                "Install with: npm i -g hyperframes@0.8.184 (or let npx fetch it)."))

    if args.project:
        project = args.project.expanduser().resolve()
        checks.append(check("project film.json", (project / "film.json").exists(),
                            str(project / "film.json"), "Run scripts/init_project.py first."))
        for name in ("NotoSansSC.woff2", "SpaceGrotesk.woff2", "JetBrainsMono.woff2"):
            path = project / "assets" / "fonts" / name
            checks.append(check(f"font {name}", path.exists(), str(path), "Re-copy assets/template/fonts."))
        gsap = project / "assets" / "vendor" / "gsap.min.js"
        checks.append(check("GSAP", gsap.exists(), str(gsap), "Re-copy assets/template/assets/vendor."))
        checks.append(check("timeline.json", (project / "timeline.json").exists(),
                            "measured" if (project / "timeline.json").exists() else "not yet",
                            "Run scripts/tts.py and scripts/make_timeline.py.", required=False))
        checks.append(check("mix", (project / "assets" / "mix.wav").exists(),
                            "ready" if (project / "assets" / "mix.wav").exists() else "not yet",
                            "Run scripts/mix_audio.py before the final render.", required=False))

    ok = all(c["ok"] for c in checks if c["required"])
    report = {"ok": ok, "platform": platform.platform(), "checks": checks}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        for c in checks:
            mark = "OK " if c["ok"] else ("MISS" if c["required"] else "skip")
            print(f"[{mark}] {c['name']}: {c['detail']}")
            if not c["ok"] and c["hint"]:
                print(f"       {c['hint']}")
        print("\nenvironment ready" if ok else "\nrequired tools missing")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
