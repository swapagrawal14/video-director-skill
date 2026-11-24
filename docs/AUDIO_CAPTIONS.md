# Voice, words, captions, sound

## Voice (pick one)
| Engine | Cost | Word timings | Hindi/Hinglish | Notes |
|---|---|---|---|---|
| Cartesia `tts_cartesia.py` | paid API | via words_project.py | yes (cloned voice) | best quality; env CARTESIA_API_KEY, CARTESIA_VOICE_ID |
| Edge `tts_free.py --engine edge` | free, online | **exact, native** | hi-IN-SwaraNeural / MadhurNeural | unofficial MS service |
| Kokoro `--engine kokoro` | free, offline, Apache-2.0 | via Whisper | hf_alpha, hf_beta, hm_omega, hm_psi | CPU ok |
| Piper `--engine piper --voice x.onnx` | free, offline, GPL pkg | via Whisper | hi_IN-pratham, hi_IN-priyamvada | check each voice licence |
Any other TTS: drop `vo/sNN.wav` files in. All engines cache: a finished scene is never re-synthesised.
Hinglish tip: write the VO in Devanagari for Hindi voices; keep English terms in Latin.

## Words → captions
1. `python3 scripts/words_project.py <dir>` → `words.json` on the final timeline. Uses native TTS timings when present,
   else faster-whisper (CPU int8). Whisper's text is never trusted: if the word count matches the script, the script's
   words are used with Whisper's times. Low-confidence words are listed: check them.
2. `python3 scripts/captions.py <dir>/words.json <dir>/captions.ass --w 1280 --h 720 --project <dir>` (uses `look.captions_preset`,
   `look.palette`, `look.captions_position`), or `--preset NAME --palette "#..,#..,#.."`. There is no default style: pick
   one of the presets in `docs/TEXT_STYLES.md` per video. `--style pop|karaoke` still gives the old yellow/white look.
   Vertical: `--w 1080 --h 1920` (keeps captions above the Shorts/Reels UI). `--upper` for punchy reels. `--max-words 3`.
3. Burn in: set `"burn_captions": "captions.ass"` in project.json before `mux.py`, or pass `--ass` to `export.py`.
4. Upload-able CC: `python3 scripts/chapters.py <dir> <dir>/words.json` also writes `captions.srt`.
Use either burned captions OR the engine's scene subtitles (`sub`), not both on the same frame.

## Music + SFX + mix
- `music.py <dir> calm|upbeat|lofi|epic|horror` (procedural, royalty-free).
- Horror kit: `bash scripts/sfx_horror.sh <dir>/sfx` (drone, room tone, riser, stinger, heartbeat; pure ffmpeg, no licences).
- Other SFX: Freesound CC0 (filter licence = CC0), Pixabay, Mixkit (fine in videos, but never commit their files to a repo). Record each in `CREDITS.md`.
- `mix.py`: VO with 30 ms fades, music ducked under VO (sidechain), SFX bus, `mute` windows, limiter, **two-pass
  loudness to -14 LUFS / -1 dBTP at 48 kHz** (`"lufs": -16` for podcast-style).
