# Troubleshooting

- **Chromium won't launch: `libatk-1.0.so.0` / `libXcomposite` / `libXdamage` / `libatspi` not found** — run `python3 -m playwright install-deps chromium` (root). Without root: download the Debian/Ubuntu .debs for those libs (`libatk1.0-0t64 libatspi2.0-0t64 libxcomposite1 libxdamage1`), `dpkg-deb -x` them into a folder and `export LD_LIBRARY_PATH=<folder>/usr/lib/<arch>-linux-gnu`.
- **Black frames / WebGL error** — keep the SwiftShader flags in `_server.py`; `preserveDrawingBuffer: true` must stay on.
- **Fonts look like Times** — fonts/ missing; run `scripts/setup.sh` or copy any `.ttf` to `fonts/baloo2.ttf`.
- **Render job killed by a timeout** — lower `--chunk` and re-run `render_all.py` (finished chunks are skipped). Check chunks with ffprobe `-count_frames`.
- **Frame count off by one** — fine (±1). More? delete the short chunk and re-run.
- **Audio ends early / end card cut** — `mux.py` pads audio (`apad`) and trims to timing duration; don't use `-shortest`.
- **`+faststart` fails on network drives** — `mux.py` writes to /tmp first, then copies.
- **Subtitles out of sync** — you changed VO after `build_timing.py`. Re-run timing, then mix.
- **TTS reads numbers weirdly** — spell numbers as words in `vo`, keep digits in `sub`.
- **Labels jump between frames** — the anchor is computed from something not deterministic in t. Everything must derive from t.
