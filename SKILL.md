---
name: video-director
description: Direct and produce outstanding, fully finished videos on ANY topic and in any genre (3D explainers and tutorials, medical/dental procedures, science, horror shorts, product promos, story/narrative, kinetic typography, data stories) as code: deterministic three.js / canvas scenes rendered frame by frame to MP4 with voice-over, music, subtitles, labels and a thumbnail. Use whenever someone asks an AI agent to "make a video", "animate this", "explainer", "tutorial video", "reel", "trailer" or similar.
---

# Video Director

You are not "generating a video". You are a **director + 3D artist + editor** shipping a polished film.
The bar: a viewer should think a small studio made it. Never basic, never a slideshow of text, never stock-looking.

Proven on real projects (examples/braces-tutorial: a 4:40 Pixar-style 3D dental tutorial with Hinglish VO).

---

## 0. Golden rules (read first)

1. **Picture is a pure function of time.** Everything on screen is computed from `t` inside `window.renderAt(t)`. No `requestAnimationFrame`, no `Date.now()`, no `Math.random()` at render time (use the seeded `rnd()` at build time only). This is what makes frame-perfect offline rendering possible. Full render contract + `timeshim` for custom scenes: `docs/CRAFT.md` §1.
2. **Audio drives timing.** Write the script, generate VO, *then* derive scene lengths from VO durations (`build_timing.py`). Picture and audio read the same `timing.json`, so they can never drift.
3. **Show, don't tell.** Every sentence of VO must have something *moving* on screen that illustrates it: a tool travelling to the subject, a part highlighting, a camera move revealing. Text cards are seasoning, not the meal.
4. **One idea per scene.** 8–14 s per scene is the sweet spot. 15–25 scenes for a 3–5 min video.
5. **Preview before render.** Always render stills at 4–8 timestamps (`shot.py`) and LOOK at them. Fix framing, overlapping labels, off-screen objects, unreadable text. A full render costs minutes; a still costs a second.
6. **Facts are sacred.** For educational/medical/technical topics, put exact values on screen (concentrations, times, sizes) and list every protocol-dependent value for the human to verify. End card says "confirm with your protocol/guide".
7. **Hook in the first second, change every 2–3 s.** Open on motion + a promise, never a logo. Retention rules: `docs/CRAFT.md` §2.
8. **Nothing ships without `qa.py` PASSED.** Loudness, black/frozen frames, clipping, A/V sync, caption overlap are checked by machine, not by hope.
9. **Finish the job.** Deliver the MP4 + thumbnail + title/description/tags (and a social caption if asked). Never stop at "here's the code".

---

## 1. Brief (2 minutes, ask at most 2–3 questions)

Pin down only what changes the output:
- **Topic + exact variant** (e.g. "Begg's wrap-around retainer", not "retainers").
- **Audience + language** (students? patients? kids? English / Hindi / Hinglish?).
- **Genre + length** (default: 3D explainer, 2.5–5 min, 1280x720 @ 24 fps).
- **Credit line / branding** (name + role exactly as they want it).
If the user says "decide yourself", decide and state your choices in one line.

## 2. Pick the genre recipe

Read `docs/STYLES.md` and pick ONE recipe. Each recipe fixes palette, camera language, pacing, music mood, overlay style and typography. Mixing recipes is how videos end up looking cheap.

| Recipe | Use for | Music mood |
|---|---|---|
| Pixar Clinic (default) | tutorials, procedures, how-things-work | calm / upbeat |
| Blueprint Tech | engineering, software, architecture | lofi |
| Cinematic Horror | horror shorts, mystery, true crime | horror |
| Product Hero | launches, promos, app demos | upbeat / epic |
| Storybook | kids, fables, narratives | calm |
| Kinetic Type | quotes, motivation, listicles, reels | upbeat |
| Data Story | stats, finance, history timelines | lofi / epic |

## 3. Script (project.json)

Copy `template/` via `scripts/new_project.sh projects/<slug>`. Fill `project.json`:
- `scenes[i].vo`: what the voice says. Write numbers as words in the VO language for TTS ("thirty seven percent"), digits in `sub`.
- `scenes[i].sub`: on-screen subtitle, split into readable chunks with `|` (≤ 90 chars each).
- `step`, `labels`, `badge`, `list`, `type: "title" | "end"`, `mascot`, `shot` — see `docs/ENGINE.md`.
Write a shot list in `SPEC.md` (format in `docs/CRAFT.md` §3) and get the human's OK before building scenes when the brief is big.
Optional keys: `recipe`, `intro_lead` (0.3), `lufs` (-14), `chapter` per scene, `sfx`, `mute`, `beat_snap`, `burn_captions`, `timeshim`.
Structure that works: **hook (≤10 s) → what you'll learn → setup/parts → steps → common mistakes or golden rules → recap → outro with credit.**
Write like a friendly expert talking, short sentences, one fact each.

## 4. Voice-over

- Preferred: Cartesia `sonic-latest` via `scripts/tts_cartesia.py` (env `CARTESIA_API_KEY`, `CARTESIA_VOICE_ID` — the user's own cloned voice if they have one). Never hard-code or commit keys.
- Free, no key: `scripts/tts_free.py projects/<slug> --engine edge --voice hi-IN-SwaraNeural` (exact word timings; Hindi/Hinglish/English). Offline: `--engine kokoro` or `--engine piper`. See `docs/AUDIO_CAPTIONS.md`.
- Any TTS works: just put one file per scene at `vo/s00.wav, vo/s01.wav …`.
- No TTS? Leave `vo` empty and set `secs` per scene; it becomes a music + subtitle video.
- Listen check: ffprobe durations; a scene VO > 20 s means split the scene.

Then:
```
python3 scripts/build_timing.py projects/<slug>
python3 scripts/lint.py projects/<slug>        # hook, scene lengths, VO speed, subtitle length, chapters, genre rules
python3 scripts/words_project.py projects/<slug>   # words.json on the final timeline (for captions + SRT)
```

## 5. Build the world (index.html) — where quality is won

The template gives you: renderer with ACES tone mapping + soft shadows + environment reflections, bokeh gradient backdrop, wooden bench + mat stage, a mascot with blink/hop/wave/point, orbit camera keys per scene, and the full 2D overlay kit (title card, step chip, 3D-anchored callout labels, timer badge, list cards, subtitles, progress bar, fades).

You replace two things:
1. **`buildSubject()`** — the hero model, built from three.js primitives: `LatheGeometry` (teeth, bottles, vases), `ExtrudeGeometry` (plates, gums, logos), `TubeGeometry` on `CatmullRomCurve3` (wires, cables, vessels), deformed `SphereGeometry` (organic shapes). Return named parts.
2. **`SCENE_FX[i](u, S, t)`** — per-scene animation: tools fly in on eased paths, parts appear with `back()` overshoot, colours/opacity change to show a process, particles for sprays/sparks.

Craft checklist (do these, they are the difference between "AI slop" and "studio"):
- **Materials**: `MeshPhysicalMaterial` with clearcoat for plastic/enamel, metalness .7 roughness .25 for steel, sheen for soft tissue/fabric. Never flat `MeshBasicMaterial` on hero objects.
- **Light**: key + rim + warm fill, shadows on. Rim light separates subject from background.
- **Motion**: everything eases (`ease`, `easeOut`, `back`). Nothing teleports. Tools approach, pause, act, retreat.
- **Camera**: every scene moves slowly (dolly or orbit 10–25°). Close-ups for detail steps, wide for context. Cut on scene change, never mid-sentence.
- **Scale & contact**: objects sit ON surfaces (check shadows touch), tools actually touch the subject.
- **Labels**: max 3 on screen, leader lines never cross, keep 40 px from frame edges, never over the subtitle zone (bottom 140 px).
- **Mascot / character** only at intro, rules/recap and outro, and must be fully in frame.
- **Colour**: one accent, one secondary, one highlight (theme in project.json). Consistent per recipe.

## 6. Preview & QA (mandatory)

```
python3 scripts/shot.py projects/<slug> 3 15 40 75 120 180   # -> shots/ + shots/sheet.jpg
```
Open the sheet. Check: nothing cut off at edges, labels readable and not overlapping, subtitles ≤ 2 lines, correct step numbers, subject well-framed in each shot, title & end card text fits. Fix, re-shoot, repeat. Also open any scene with tricky motion at 3 timestamps (start, middle, end). Log problems in `REVIEW.md`; render only when it's empty. Banned defaults: `docs/CRAFT.md` §5.

## 7. Music & mix

```
python3 scripts/music.py projects/<slug> calm     # calm | upbeat | lofi | epic | horror
python3 scripts/beats.py music.wav beats.json     # optional: + "beat_snap": true, re-run build_timing.py
python3 scripts/mix.py   projects/<slug>          # VO (30 ms fades) + ducked music + sfx + mute windows -> -14 LUFS / -1 dBTP, 48 kHz
python3 scripts/captions.py projects/<slug>/words.json projects/<slug>/captions.ass --w 1280 --h 720 --style pop
```
Music is procedural and royalty-free. Horror: `bash scripts/sfx_horror.sh projects/<slug>/sfx` + the scare structure in `docs/CRAFT.md` §6. Track every external asset in `CREDITS.md` (template: `CREDITS.template.md`).

## 8. Render

```
python3 scripts/render_all.py projects/<slug> --jobs 2 --chunk 200   # resumable; re-run if a job dies
python3 scripts/chapters.py projects/<slug> projects/<slug>/words.json   # chapters.txt + chapters.ffmeta + captions.srt
python3 scripts/mux.py projects/<slug> My_Video_Title.mp4   # AAC 384k, BT.709, chapters, burn_captions
python3 scripts/grade.py My_Video_Title.mp4 Graded.mp4 --look teal_orange --mix 0.7   # optional look (horror: --look horror --grain 14 --vignette 0.6 --ca 2)
python3 scripts/export.py Graded.mp4 shorts Short.mp4 --start 0 --end 55            # youtube | shorts | square | portrait
python3 scripts/qa.py Graded.mp4 projects/<slug>/captions.ass                        # MUST print QA PASSED
```
- Headless Chromium + SwiftShader (CPU). Expect ~1–4 s per frame per job; a 4-min video ≈ 1–2 h on CPU. Tell the user an honest ETA.
- If the agent's shell has a per-command timeout, run chunks as background jobs and keep each under it (200 frames is safe). `render_all.py` skips finished chunks, so just re-run.
- Verify: assembled frames == `timing.json` frames (±1), final duration == timing duration.
- 1080p: `--width 1920` (all 2D overlay sizes scale automatically).

## 9. Package & deliver

- Thumbnail: `scripts/thumbgrab.py <dir> <t>` (clean 3D frame, no overlays) → `scripts/thumb.py <dir> clean_<t>.png` (dark left gradient, pill tag, huge title, credit). Look at it before delivering.
- Write: YouTube title (≤ 70 chars, keyword first), description with `chapters.txt`, 10–15 tags, and a social caption with hashtags if asked.
- List every factual value that needs human verification.
- Never post/publish anything on the user's behalf without explicit permission.

---

## Files
- `template/index.html` — scene engine (edit `buildSubject` + `SCENE_FX`).
- `template/project.json` — content/timing/theme schema with a working 5-scene demo.
- `scripts/` — setup, new_project, tts_cartesia, tts_free, build_timing, lint, words_project, words_whisper, captions, shot, music, beats, sfx_horror, mix, loudnorm, render, render_all, timeshim.js, mux, chapters, make_lut, grade, export, qa, thumbgrab, thumb.
- `docs/STYLES.md` — genre recipes. `docs/ENGINE.md` — project.json + engine reference. `docs/TROUBLESHOOTING.md`. `docs/CRAFT.md` — render contract, hook/retention, shot list, review loop, banned defaults, horror scare structure, beat cuts. `docs/AUDIO_CAPTIONS.md` — TTS engines, word timings, captions, SFX, mix. `docs/EXPORT_QA.md` — grade, platform presets, QA gate, packaging. `docs/CHARACTERS.md` — character3d.js API, stage directions, lip-sync, craft tips.
- `template/character3d.js` — 3D toon characters from three.js primitives (no SVG, no sprites): walk/sneak/run, gesture clips, idle, lip-sync, expressions, keyword auto-gestures (Hindi too). Reference: `docs/CHARACTERS.md`. Demo: `examples/character-demo/`.
- `examples/braces-tutorial/` — a complete, real 21-scene production to learn from (models, tools, per-scene FX, labels).
