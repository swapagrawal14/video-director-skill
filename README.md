<div align="center">

<img src="docs/img/hero-v2.jpg" alt="Video Director Skill" width="100%">

# 🎬 Video Director Skill

### Paste one prompt into any AI coding agent. Get back a finished, YouTube-ready video.

**3D explainers · step-by-step tutorials · dental/medical procedures · horror shorts · product promos · kinetic-type reels**

![three.js](https://img.shields.io/badge/three.js-r160-black?logo=threedotjs)
![ffmpeg](https://img.shields.io/badge/ffmpeg-render%20%2B%20mux-007808?logo=ffmpeg)
![TTS](https://img.shields.io/badge/voice-free%20Hindi%20%2B%20English-e2475b)
![Formats](https://img.shields.io/badge/formats-16%3A9%20·%209%3A16%20·%201%3A1-3b82c4)
![Audio](https://img.shields.io/badge/audio--14%20LUFS-broadcast%20ready-ffd23f)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

> **Agents: raster first.** Everything here, even the shots that look 3D, is built from generated image frames, pose packs, cut-out rigs and frame-by-frame animation. Use the three.js engine only when someone explicitly asks for real 3D models. See the Routing priority in [SKILL.md](SKILL.md).

Works with **Claude Code · Codex · Cursor · Gemini CLI · Hark** — or any agent that can run a shell.

</div>

---

## 👀 Made with this skill

<table>
<tr>
<td width="42%" align="center">

<img src="docs/img/dhai-baje.gif" alt="ढाई बजे horror short" width="270">

**ढाई बजे · 2:30 AM** — Hindi horror Short (9:16, 64 s)<br>
*Every time the bulb flickers, she gets closer.*<br>
[Source](examples/dhai-baje/)

</td>
<td width="58%" align="center">

<img src="docs/img/braces-thumbnail.jpg" alt="Braces tutorial" width="100%">

**Braces kaise lagte hain?** — 3D dental tutorial (16:9, Hinglish)<br>
*Bonding to debonding, step by step, with callout labels.*<br>
[Source](examples/braces-tutorial/)

</td>
</tr>
</table>

<p align="center">
<img src="docs/img/swap-creations-intro.gif" alt="Swap Creations logo intro" width="240"><br>
<b>Swap Creations</b> — logo intro (9:16, 15 s)<br>
<i>Give any logo: the tool breaks it into parts (shape, colours, letters, sparkles) and animates the intro.</i><br>
<a href="examples/swap-creations-intro/">Source</a> · <a href="docs/LOGO_INTRO.md">How</a> · <code>python3 motion2d/logo_intro.py logo.png out.mp4</code>
</p>

<p align="center"><img src="docs/img/truck-sting.gif" alt="ZIPZOOM truck sting: hand-drawn finish" width="240"><br><b>ZIPZOOM</b> — hand-drawn truck sting (9:16, 6 s, fully procedural): on twos, line boil, wobbly re-inked outlines, marker fills, paper grain · <a href="examples/truck-sting/">Source</a> · <a href="docs/HANDDRAWN_FINISH.md">How</a></p>

<p align="center">
<img src="docs/img/powercut-cartoon.gif" alt="2 AM Power Cut: pastel cartoon short" width="270"><br>
<b>2 AM Power Cut</b> — pastel cartoon Short (9:16, 12 s, SFX only)<br>
<i>Exam kal hai, light chali gayi, takiye pe do aankhein... aur nikli hostel ki billi.</i><br>
<a href="examples/powercut-cartoon/">Source</a> · <a href="examples/powercut-cartoon/2AM_Power_Cut.mp4">Watch with sound (MP4)</a> · <a href="docs/CARTOON.md">How</a>
</p>

> The horror short above was written, voiced, lit, scored, captioned, graded and QA-checked by an agent using this repo — in under an hour, with **zero paid APIs and zero stock footage.**

---


## Use it as an MCP server
Run the repo from Claude Desktop, Cursor, Claude Code or any MCP client: see [`mcp/`](mcp/README.md). One file, no extra dependencies.

## What can I ask for?
Open [`prompts/`](prompts/README.md) for ready-to-use prompts: tutorials, explainers, stories, promos, science, and ways to remix the engines into something new.

## 🎭 Painted characters that act (new)

`template/headrig3d.js` (default) and `template/posepack3d.js` bring the [Rigpop Motion](https://github.com/swapagrawal14/rigpop-motion) method into the three.js engine: **pose first, motion second**.

- Characters are **painted cutout rigs** (PNG): headless painted body poses + ONE shared painted head, so expressions never change by themselves. Never vector or primitive dolls.
- **Directed expressions:** brows, eyes, mouth and head tilt are keyed in time; lip-sync visemes are smoothed and held ≥ 3 frames
- **Motion QA:** `scripts/motion_qa.py` makes consecutive-frame strips that must be checked before delivery
- **Always alive on top of the pose:** breathing, sway, settle after each cut, blinks, eye darts toward the other speaker
- **Lip-sync patches** (rest, M, A, E, O) driven by the VO through `scripts/mouth.py`
- **Speaking rotations** (talk, point, talk) and pinned listen, think and laugh poses, all directed in time
- **Painted sets** as backdrops with camera parallax, push-ins and hard cuts to a medium on the punchline
- **Strict no-SVG rule,** enforced by `lint.py`

<p align="center"><img src="docs/img/painted-duet.gif" alt="चाय में नमक: painted duet" width="270"></p>

Docs: [docs/CHARACTERS.md](docs/CHARACTERS.md) · Demo: [examples/painted-duet](examples/painted-duet) (Hindi dialogue, 16 s)

## ⚡ Use it in 10 seconds

Paste this into your agent:

```text
Use the skill at https://github.com/swapagrawal14/video-director-skill
(read SKILL.md and follow it exactly). Make a ~60 second video on [topic]
for [audience] in [language], style [recipe or "you decide"], format [16:9 or 9:16].
Credit: [name (role)]. Deliver the MP4, thumbnail, title, description and tags.
```

Try: *"a 9:16 Hindi horror short about a hostel lift that stops at a floor that doesn't exist"* or *"a 3-minute Hinglish 3D tutorial on root canal treatment."*

---

## 🧩 More engines, merged in (new)

| Engine | Use it for | Run |
|---|---|---|
| `motion2d/` (from vid-shark) | Motion graphics where objects do the action: pours, wipes, drops, launches. Procedural SFX on every action, VO-led mix, chunked parallel render | `python3 motion2d/examples/chai/render.py` |
| `motion2d/` doodle preset | Flat motion-doodle reels: puppet-pin warp for rubber-hose limbs, optical-flow in-betweening, beat-synced seamless loops (mp4/gif/webm) | see `docs/MOTION_DOODLE.md` |
| `motion2d/cartoon.py` cartoon kit (new) | Cute cartoon scenes and full episodes in ANY art style: 10 style packs (pastel outline, flat no-outline, rubber-hose, anime cel, chibi, crayon, paper cut-out, watercolour, desi gouache, dark cartoon) or read the style off any reference video (`scripts/style_ref.py`); beat-sheet acting with SFX gates, lighting that tells the story (lamp off, power cut, glow eyes), fan/swing/shake rigs, parallax and tiny-planet worlds. No animation skills needed: give your agent this repo link and a reference | see `docs/CARTOON.md` |
| `handdrawn/` (swap-studio style packs) | Hand-drawn / whiteboard reels: pen draw-on of line art, line boil, write-on titles, marker swipes, karaoke captions, end cards, in 7 style packs. Raster only | `python3 handdrawn/examples/chai-doodle/render.py chalkboard out.mp4` |
| `screencast/` (new) | Tutorial reels: a real browser recording on a tilted, taped card, with auto-zoom to each click, an eased cursor, marker circles and STEP chips. A painted talking host switches gesture poses every beat. Camera push-ins, whip/rip/zoom-blur cuts, contrasting backgrounds that swap each beat, scramble captions (Hindi too), procedural SFX on every cut and click, pop-in word stickers, blur for private info. Assets are a starter kit; agents generate new ones per video | `python3 -m screencast all examples/screencast-wiki out.mp4` |
| `vidliboom/` (from vid-liboom) | One script in, a whole cartoon episode out: scene planner, pose-pack characters, shader skies, music, subtitles | `python3 -m vidliboom examples/episode/bablu_mausam.md -o episode.mp4 --format vertical` |

<p align="center"><img src="docs/img/handdrawn.gif" alt="Hand-drawn engine demo, swap-edu pack" width="240"> &nbsp; <img src="docs/img/screencast.gif" alt="Screencast tutorial engine demo: Wikipedia in Hindi" width="216"></p>

Docs: [docs/SCREENCAST.md](docs/SCREENCAST.md) · [docs/HANDDRAWN.md](docs/HANDDRAWN.md) · [docs/HANDDRAWN_FINISH.md](docs/HANDDRAWN_FINISH.md) · [docs/MOTION2D.md](docs/MOTION2D.md) · [docs/MOTION_DOODLE.md](docs/MOTION_DOODLE.md) · [docs/CARTOON.md](docs/CARTOON.md) · [docs/ARTSTYLES.md](docs/ARTSTYLES.md) · [docs/EPISODE_SCRIPT.md](docs/EPISODE_SCRIPT.md). Raster art only; the no-SVG rule applies to every engine.

---

## ✨ What makes the videos good

| | |
|---|---|
| 🎥 **Frame-perfect rendering** | Every engine renders each frame as a pure function of `t` (raster engines by default, three.js only on request). `timeshim.js` makes even custom GSAP/CSS/particle scenes render without dropped frames. |
| 🗣️ **Free voices that sound right** | Edge → Kokoro → Piper chain with Hindi, Hinglish and English voices and native word timings. Cartesia for premium/cloned voices. |
| 💬 **Captions people actually read** | Word-by-word TikTok-pop or karaoke captions, safe-zone aware for Shorts/Reels, plus SRT. |
| 🔊 **Sound that hits** | Ducking, anti-click fades, SFX bus, silence windows before scares, two-pass loudness to **-14 LUFS / -1.5 dBTP**. |
| 👻 **A horror toolkit** | Procedural drones, heartbeats, risers and stingers, plus a scare-structure guide (hook, false calm, vacuum, hit). |
| 🎨 **Film look** | Generated LUTs (horror, teal-orange, warm, bleach), grain, vignette, chromatic aberration, letterbox. |
| 📱 **Every platform** | YouTube 16:9, Shorts/Reels 9:16 (native, crop or blur-fill), square, 4:5. |
| ✅ **Quality gates** | Lint before render (hook timing, pacing, VO speed) and QA after (black/frozen frames, loudness, clipping, colour range, caption overlap). |
| 📦 **Packaging** | YouTube-valid chapters, embedded MP4 chapters, thumbnail, title and tags. |

---

## 🎭 Genre recipes

| Recipe | Feels like | Best for |
|---|---|---|
| 🦷 **Pixar Clinic** | Soft, glossy 3D models, numbered steps, callout labels | Tutorials, dental/medical procedures |
| 📐 **Blueprint Tech** | Wireframes, glowing lines, exploded views | Engineering, software, systems |
| 👻 **Cinematic Horror** | Dark practicals, flicker, slow dread, one earned scare | Horror shorts, creepy stories |
| ✨ **Product Hero** | Studio lighting, hero turntables, cuts on the beat | Launches, promos, app demos |
| 📖 **Storybook** | Warm, painterly scenes and narration | Fables, kids' stories |
| 🔤 **Kinetic Type** | Big type, motion graphics, beat-synced | Quotes, listicles, reels |
| 📊 **Data Story** | Animated charts and maps | Stats, finance, history |

Full recipes in [`docs/STYLES.md`](docs/STYLES.md).

---

## 🛠️ How it works

```mermaid
flowchart LR
  A[Brief] --> B[Recipe + script<br>project.json]
  B --> C[Voice-over<br>+ word timings]
  C --> D[timing.json]
  D --> E[3D scene<br>index.html]
  E --> F[Lint + preview stills]
  F --> G[Chunked parallel render]
  C --> H[Music + SFX mix<br>-14 LUFS]
  G --> I[Grade + captions + mux]
  H --> I
  I --> J[Exports 16:9 · 9:16]
  J --> K[QA gate]
  K --> L[🎬 MP4 + thumbnail + title/tags]
```

---

## 🤖 For the AI agent

Read **[SKILL.md](SKILL.md)** first and follow it end to end. Then:

- [`docs/STYLES.md`](docs/STYLES.md) — genre recipes and finishing table
- [`docs/CRAFT.md`](docs/CRAFT.md) — render contract, hooks, pacing, horror scares
- [`docs/AUDIO_CAPTIONS.md`](docs/AUDIO_CAPTIONS.md) — voice, mix, captions
- [`docs/EXPORT_QA.md`](docs/EXPORT_QA.md) — grading, exports, QA gate
- [`docs/ENGINE.md`](docs/ENGINE.md) — engine and `project.json`
- Study [`examples/braces-tutorial/`](examples/braces-tutorial/) (16:9 tutorial) and [`examples/dhai-baje/`](examples/dhai-baje/) (9:16 horror, custom scene).

<details>
<summary><b>🧑‍💻 Quick start for humans (click to open)</b></summary>

```bash
git clone https://github.com/swapagrawal14/video-director-skill && cd video-director-skill
bash scripts/setup.sh                         # three.js, fonts, playwright + chromium (needs ffmpeg, node, python3)
bash scripts/new_project.sh projects/demo     # copies the template (working 5-scene demo)
python3 scripts/tts_free.py projects/demo --engine edge          # free Hindi/English VO with word timings
python3 scripts/build_timing.py projects/demo && python3 scripts/lint.py projects/demo
python3 scripts/words_project.py projects/demo                    # words.json for captions
python3 scripts/shot.py projects/demo 3 9 15 21 27                # preview stills -> shots/sheet.jpg
python3 scripts/music.py projects/demo calm && python3 scripts/mix.py projects/demo   # -14 LUFS, ducked, 48 kHz
python3 scripts/captions.py projects/demo/words.json projects/demo/captions.ass --w 1280 --h 720 --project projects/demo   # look.captions_preset (docs/TEXT_STYLES.md)
python3 scripts/render_all.py projects/demo --jobs 2
python3 scripts/chapters.py projects/demo projects/demo/words.json && python3 scripts/mux.py projects/demo Demo.mp4
python3 scripts/export.py projects/demo/Demo.mp4 shorts projects/demo/Demo_short.mp4
python3 scripts/qa.py projects/demo/Demo.mp4                      # must print QA PASSED
```

**Vertical (9:16):** set `"width": 720, "aspect": [9, 16]` in `project.json` and render with `--width 720`; captions with `--w 720 --h 1280`.

**Premium voice:** `CARTESIA_API_KEY=... CARTESIA_VOICE_ID=... python3 scripts/tts_cartesia.py projects/demo`. Offline: `--engine kokoro` / `--engine piper`. Or drop your own `vo/s00.wav, s01.wav …`.

**Horror captions:** `--style pop --active E8E8E8 --idle 8A8A8A` (no yellow in a horror film).

</details>

---

## 🙏 Inspired by

Patterns studied (no code copied) from HeyGen HyperFrames, Remotion agent skills, OpenMontage, browser-use video-use, manim-voiceover, timesnap/CCapture.js, faster-whisper and stable-ts.

## 💜 Made by

**Swapnil Agrawal (BDS intern)** — AI builder, author and educator<br>
YouTube: *Swap's AI World* · [LinkedIn](https://www.linkedin.com/in/swapnil-agrawal-109a3321b) · [X @ai_artist1411](https://x.com/ai_artist1411) · [GitHub](https://github.com/swapagrawal14)

⭐ If this made you a video, star the repo and tag me. I'd love to see it.

<sub>MIT licensed. Fonts under OFL. Educational/medical content made with this skill must be verified by a qualified person before use.</sub>
