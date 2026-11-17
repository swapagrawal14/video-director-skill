# 🎬 Video Director Skill

**Give this repo to any AI coding agent (Claude Code, Codex, Cursor, Gemini CLI, Hark…) and it can direct and render outstanding, fully finished videos on any topic** — 3D explainers, step-by-step tutorials, medical/dental procedures, horror shorts, product promos, stories, kinetic-type reels — with voice-over, music, subtitles, callout labels and a YouTube thumbnail.

Everything is code: a deterministic three.js scene rendered frame by frame to MP4. No paid video API, no stock footage.

![Braces tutorial thumbnail](docs/img/braces-thumbnail.jpg)

## For the AI agent
Read **[SKILL.md](SKILL.md)** first and follow it end to end. Then `docs/STYLES.md` (genre recipes), `docs/CRAFT.md` (render contract, hooks, horror scares), `docs/AUDIO_CAPTIONS.md`, `docs/EXPORT_QA.md`, `docs/ENGINE.md` (engine + project.json), and study `examples/braces-tutorial/`.

Prompt you can paste into any agent:
> Use the skill at https://github.com/swapagrawal14/video-director-skill (read SKILL.md and follow it exactly). Make a ~3 minute video on **[topic]** for **[audience]** in **[language]**, style **[recipe or "you decide"]**. Credit: **[name (role)]**. Deliver the MP4, thumbnail, title, description and tags.

## Quick start (humans)
```bash
git clone https://github.com/swapagrawal14/video-director-skill && cd video-director-skill
bash scripts/setup.sh                         # three.js, fonts, playwright + chromium (needs ffmpeg, node, python3)
bash scripts/new_project.sh projects/demo     # copies the template (working 5-scene demo)
python3 scripts/tts_free.py projects/demo --engine edge          # free Hindi/English VO with word timings
python3 scripts/build_timing.py projects/demo && python3 scripts/lint.py projects/demo
python3 scripts/words_project.py projects/demo                    # words.json for captions
python3 scripts/shot.py projects/demo 3 9 15 21 27                # preview stills -> shots/sheet.jpg
python3 scripts/music.py projects/demo calm && python3 scripts/mix.py projects/demo   # -14 LUFS, ducked, 48 kHz
python3 scripts/captions.py projects/demo/words.json projects/demo/captions.ass --w 1280 --h 720
python3 scripts/render_all.py projects/demo --jobs 2
python3 scripts/chapters.py projects/demo projects/demo/words.json && python3 scripts/mux.py projects/demo Demo.mp4
python3 scripts/export.py projects/demo/Demo.mp4 shorts projects/demo/Demo_short.mp4
python3 scripts/qa.py projects/demo/Demo.mp4                      # must print QA PASSED
```
Premium voice: `CARTESIA_API_KEY=... CARTESIA_VOICE_ID=... python3 scripts/tts_cartesia.py projects/demo`. Offline: `--engine kokoro` / `--engine piper`. Or drop your own `vo/s00.wav, s01.wav …`.

## What's inside
- **Deterministic 3D engine** (three.js) + `timeshim.js` so even custom GSAP/CSS/particle scenes render frame-perfect.
- **Free TTS chain** (Edge → Kokoro → Piper) with Hindi/Hinglish voices and native word timings; Cartesia for premium.
- **Word-level animated captions** (TikTok pop or karaoke sweep), safe-zone aware for 9:16; SRT export.
- **Broadcast-grade audio**: ducking, 30 ms anti-click fades, SFX bus, silence windows, two-pass -14 LUFS / -1 dBTP.
- **Procedural horror sound kit** and a scare-structure guide; **beat detection** to cut on the beat.
- **Colour grading** with generated LUTs (horror, teal-orange, warm, bleach) + grain, vignette, chromatic aberration, letterbox.
- **Platform exports**: YouTube 16:9, Shorts/Reels 9:16 (blur-fill or crop), square, 4:5.
- **Lint before render + QA gate after**: hook timing, pacing, VO speed, black/frozen frames, loudness, clipping, caption overlap.
- **YouTube packaging**: chapters (valid format), embedded MP4 chapters, thumbnail, title/tags.

Template demo frames:

![Template demo](docs/img/template-demo.jpg)

## Pipeline
`brief → genre recipe → script (project.json) → VO → timing.json → 3D world + per-scene FX → lint → preview stills & REVIEW.md → music + beats + mix (-14 LUFS) → word captions → chunked parallel render → mux (chapters) → grade → exports → QA gate → thumbnail + title/tags`

## Inspired by
Patterns studied (no code copied) from HeyGen HyperFrames, Remotion agent skills, OpenMontage, browser-use video-use, manim-voiceover, timesnap/CCapture.js, faster-whisper and stable-ts.

## Made by
**Swapnil Agrawal (BDS intern)** — AI builder & educator · YouTube: *Swap's AI World* · [LinkedIn](https://www.linkedin.com/in/swapnil-agrawal-109a3321b)

MIT licensed. Fonts under OFL. Educational/medical content made with this skill must be verified by a qualified person before use.
