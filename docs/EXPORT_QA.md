# Finish, export, QA

## Order of operations
render_all → mux (audio, BT.709, chapters, optional burned captions) → grade (optional look) → export presets → qa → thumbnail → package.

## Grade
`python3 scripts/grade.py in.mp4 out.mp4 --look horror|teal_orange|warm|bleach|my.cube [--grain N --vignette 0..1 --ca px --bars 2.39 --mix 0..1]`
LUTs are generated (make_lut.py), so they're licence-free. `--mix 0.7` for a subtle grade on tutorials.

## Export presets (`export.py`)
| Preset | Size | Use |
|---|---|---|
| youtube | 1920×1080 | main upload |
| shorts | 1080×1920 | YouTube Shorts, Reels, TikTok (cut with --start/--end) |
| square | 1080×1080 | LinkedIn / IG feed |
| portrait | 1080×1350 | IG / LinkedIn feed 4:5 |
All: H.264 high, CRF 18, GOP = fps/2, BT.709, AAC 384k 48 kHz, faststart. Vertical reframing: `--fit blur` (default) or `--fit crop --x 0.4`.
For vertical, make captions at 1080×1920 and pass `--ass`.

## QA gate (`qa.py`) — must PASS before delivery
`python3 scripts/qa.py final.mp4 [captions.ass] [--lufs -14]` → exit 1 on FAIL. Checks: black frames, frozen picture,
silence gaps, loudness ±1 LU, true peak ≤ -1 dBTP, clipping, A/V length mismatch, yuv420p, faststart, caption
overlap/speed/length. Horror silences show as WARN (intentional is fine).
Also: `lint.py <dir>` before rendering (hook, scene lengths, VO speed, subtitle length, chapters, genre rules).

## Package
- `chapters.py` → `chapters.txt` (paste in description; YouTube needs 00:00 first, ≥3 chapters, each ≥10 s), `chapters.ffmeta` (mux embeds it), `captions.srt`.
- Thumbnail: thumbgrab.py + thumb.py. Title ≤70 chars, keyword first; 10–15 tags.
- `CREDITS.md`: voice engine, music, every SFX with source + licence.
