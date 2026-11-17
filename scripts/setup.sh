#!/usr/bin/env bash
# One-time setup: three.js, fonts, Python deps, headless Chromium. Needs ffmpeg on PATH.
set -e
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo "Install ffmpeg first"; exit 1; }
npm install --no-audit --no-fund three@0.160.0
mkdir -p fonts
curl -fsSL -o fonts/baloo2.ttf "https://github.com/google/fonts/raw/main/ofl/baloo2/Baloo2%5Bwght%5D.ttf"
curl -fsSL -o fonts/caveat.ttf "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf"
pip install -r requirements.txt
python3 -m playwright install chromium
echo "Setup done."
