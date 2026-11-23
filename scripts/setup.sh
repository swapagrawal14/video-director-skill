#!/usr/bin/env bash
# One-time setup: three.js, fonts, Python deps, headless Chromium (+ its system libraries). Needs ffmpeg, node, python3.
set -e
cd "$(dirname "$0")/.."
for c in ffmpeg node npm python3; do
  command -v "$c" >/dev/null || { echo "Install $c first"; exit 1; }
done
npm install --no-audit --no-fund
mkdir -p fonts
[ -s fonts/baloo2.ttf ] || curl -fsSL -o fonts/baloo2.ttf "https://github.com/google/fonts/raw/main/ofl/baloo2/Baloo2%5Bwght%5D.ttf"
[ -s fonts/caveat.ttf ] || curl -fsSL -o fonts/caveat.ttf "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf"
python3 -m pip install -r requirements.txt

# Chromium. On Linux it also needs system libraries (libatk, libXcomposite, libXdamage, libatspi, ...)
# that a fresh machine or container often lacks. --with-deps installs them (needs root or passwordless sudo).
if [ "$(uname)" = "Linux" ] && { [ "$(id -u)" = "0" ] || sudo -n true 2>/dev/null; }; then
  python3 -m playwright install --with-deps chromium
else
  python3 -m playwright install chromium
fi

# Smoke test: can headless Chromium actually start?
if python3 - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"]); b.close()
PY
then
  echo "Setup done."
else
  echo
  echo "Setup finished, but headless Chromium could not start."
  echo "On Linux, install its system libraries with:  sudo python3 -m playwright install-deps chromium"
  exit 1
fi
