#!/usr/bin/env bash
# Install pop-science-video into a skills directory.
#
#   ./install.sh                         # copy to ~/.agents/skills/pop-science-video
#   ./install.sh --link                  # symlink instead (edits in this checkout are live)
#   ./install.sh --target ~/.claude/skills/pop-science-video
#   ./install.sh --with-media            # include the demo MP4/stills (larger)
#
# Default copy excludes generated media so the installed skill stays small;
# the example project, template, scripts and references are included.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HOME}/.agents/skills/pop-science-video"
MODE="copy"
FORCE=0
WITH_MEDIA=0

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) MODE="link"; shift ;;
    --copy) MODE="copy"; shift ;;
    --target) TARGET="${2:?--target needs a path}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --with-media) WITH_MEDIA=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -f "$SRC/SKILL.md" ]] || { echo "SKILL.md not found in $SRC" >&2; exit 1; }
[[ "$TARGET" != "$SRC" ]] || { echo "target is the source checkout; choose another path" >&2; exit 1; }

mkdir -p "$(dirname "$TARGET")"
if [[ -e "$TARGET" || -L "$TARGET" ]]; then
  if [[ "$FORCE" -ne 1 ]]; then
    echo "target already exists: $TARGET" >&2
    echo "use --force to move it aside (a timestamped .bak is kept)" >&2
    exit 1
  fi
  backup="${TARGET}.bak.$(date +%Y%m%d%H%M%S)"
  mv "$TARGET" "$backup"
  echo "existing target moved to $backup"
fi

if [[ "$MODE" == "link" ]]; then
  ln -s "$SRC" "$TARGET"
  echo "linked $TARGET -> $SRC"
else
  mkdir -p "$TARGET"
  excludes=(--exclude '.git' --exclude '__pycache__' --exclude '.hyperframes'
            --exclude '*.pyc' --exclude '.DS_Store')
  if [[ "$WITH_MEDIA" -ne 1 ]]; then
    excludes+=(--exclude 'renders' --exclude 'assets/tts' --exclude 'assets/mix.wav'
               --exclude 'assets/music.wav' --exclude 'assets/voice.wav'
               --exclude 'recording/auditions' --exclude 'recording/takes'
               --exclude 'recording/guide' --exclude 'recording/import-report.json')
  fi
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "${excludes[@]}" "$SRC/" "$TARGET/"
  else
    # Fallback: copy, then remove generated media if not requested.
    cp -R "$SRC/." "$TARGET/"
    if [[ "$WITH_MEDIA" -ne 1 ]]; then
      rm -rf "$TARGET/examples"/*/renders "$TARGET/examples"/*/assets/tts \
             "$TARGET/examples"/*/recording/auditions "$TARGET/examples"/*/recording/takes
      rm -f "$TARGET/examples"/*/assets/mix.wav "$TARGET/examples"/*/assets/music.wav \
            "$TARGET/examples"/*/assets/voice.wav
    fi
  fi
  echo "copied $SRC -> $TARGET"
fi

[[ -f "$TARGET/SKILL.md" ]] || { echo "install verification failed: $TARGET/SKILL.md missing" >&2; exit 1; }

echo
echo "installed: $TARGET"
echo "skill name: pop-science-video"
echo
echo "Dependencies (not installed by this script):"
for cmd in node ffmpeg ffprobe python3 npx; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf '  [ok]   %s\n' "$cmd"
  else
    printf '  [miss] %s\n' "$cmd"
  fi
done
echo "  Node.js >= 22, FFmpeg, Chrome, Python >= 3.9 + numpy are required."
echo
echo "Next:"
echo "  1. Reopen your agent session so it picks up the new skill."
echo "  2. Ask: 用 pop-science-video，把“为什么 0.1 + 0.2 不等于 0.3”做成 90 秒中文横版科普片。"
echo "  3. Or create a project manually:"
echo "     python3 \"$TARGET/scripts/init_project.py\" --output ~/films/my-topic"
echo "     python3 \"$TARGET/scripts/check_environment.py\" --project ~/films/my-topic"
echo
echo "Full guide: $TARGET/INSTALL.md"
