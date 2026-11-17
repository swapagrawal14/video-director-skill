#!/usr/bin/env bash
# Usage: scripts/new_project.sh projects/my-video
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; DEST="$1"
[ -z "$DEST" ] && { echo "usage: $0 <project-dir>"; exit 1; }
mkdir -p "$DEST/vo" "$DEST/shots"
cp "$ROOT/template/index.html" "$ROOT/template/project.json" "$DEST/"
ln -sfn "$ROOT/node_modules" "$DEST/node_modules"
ln -sfn "$ROOT/fonts" "$DEST/fonts"
echo "Project ready at $DEST. Edit project.json, then run scripts/tts_cartesia.py $DEST (or add vo/sNN.wav yourself)."
