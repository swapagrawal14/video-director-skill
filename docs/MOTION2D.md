---
name: layered-motion-video
description: Make polished explainer / tutorial / story videos where the OBJECTS and CHARACTERS themselves move and act (bounce, pour, paint, drip, tick), in any visual style (claymation, desi flat illustration, paper cut-out, 3D-toy, ink), on any topic, synced to a voiceover. Use when someone asks for an "animated video", "motion graphics", "explainer", "claymation video", "tutorial video" — anything beyond a slideshow.
author: Swapnil Agrawal (BDS intern)
---

# Layered Motion Video

> **Agents:** start with [AGENTS.md](AGENTS.md) (prerequisites, what to ask first, step-by-step pipeline, **QA gates**, rules). This file is the craft playbook.

## The one rule
**Things move, not text boxes.** A slideshow with a static background and text plates popping up is NOT motion graphics.
In every shot something physical must be *doing the action the voiceover describes*: the brush paints, the gel squeezes out, the drop falls and splats, the clock hand spins, the tray flips and seats. Text is a small supporting label, never the star.

Why: viewers remember actions, not captions. If you mute the video it should still explain itself.

## How it works (pipeline)
1. **Script → beats.** Write the VO (≈150 words/min). For every sentence write the *action* that will be on screen (verb + object). If a sentence has no action, redesign it until it does.
2. **Voiceover first.** Generate VO (any TTS: Cartesia, ElevenLabs…). Timing of every animation is keyed to the words (`word_time()` or real TTS word timestamps). VO drives the edit, never the other way round.
3. **Style frame.** Generate ONE background plate for the whole video in the chosen style (plain/minimal, room for objects, no text, no main objects baked in). 16:9 → render at 1920×1080.
4. **Cut-out layers.** Generate every object/character part as a SEPARATE image with transparent background (prompt on chroma green #00FF00, key it out). Pass the first good asset as a style reference to every later one so the set matches. Characters → separate parts (head, torso, arm upper/lower, hand) so they can be rigged.
5. **Masks for state changes.** Where an object changes (teeth turning amber, glass filling, stain spreading) make a mask and a "changed" version; reveal it progressively along the action path (see `reveal` in the example).
6. **Animate in code** (`motion2d/motion.py`): easing, overshoot pop, squash-and-stretch on impact, objects following paths, pivot rotation, particles (drops, sparkles, crumbs), cast shadows, slow camera push, stop-motion jitter, grain and vignette.
7. **SFX on every action** (`motion2d/sfx.py`): pop, whoosh, squish, dab, plip, tick, boing, pour — logged during render as `(time, kind)` so they're frame-accurate. Soft music bed under VO. Loudness-normalise to −16 LUFS.
8. **Preview before full render.** Render 6–8 still frames (`PREVIEW=12,40,80…`), contact-sheet them, LOOK at them, fix, then render. Send progress (frames, sample) to the person as you go.
9. **Pass the QA gates** in [AGENTS.md §4](AGENTS.md#4-qa-gates-every-video-before-the-human-sees-it) (alpha coverage, despill, pose registration, walk check, contact registration, preview sheet, audio numbers, file size) before anything goes to the person.
10. **Render in chunks** when shell commands time out: `motion2d/chunkrender.py` (parallel chunks with warm-up frames, then concat + mux).

## Characters that ACT: pose packs (read this before animating any character)
**Never build characters out of SVG / vector shapes / code-drawn puppets.** The person hates that look and it reads as clip-art. Rigging one cut-out with rotating limbs also looks stiff ("characters are still, they're doing nothing"). What works (rigpop-motion method, `motion2d/posepack.py` + `motion2d/sheets.py`):

1. **Design the character once** (full body, AI image, transparent). This is the master reference.
2. **Generate a POSE PACK: 5–10 key poses per character per scene**, one image each, with the master as the FIRST reference image and the prompt "same character, same size, same position in frame and same framing as the first reference … POSE: <acting beat>". Because the model copies the first reference's canvas, every pose comes out REGISTERED (same canvas size, same scale, feet on the same baseline) and can be swapped with zero drift. Check with `alpha_bbox`: bottoms should match within a few px; fix outliers with `fix_scale` or regenerate with the registered pose as first ref.
   - Act the beats, not the words: wave, proud, look-up, worried, flinch, smug, flail, grope, slump, giggle, photo, shrug, arms-up, zen…
   - If an output comes back at a different canvas size or fully opaque (keying failed), regenerate it with a registered pose as first ref. Always check `(alpha>40).mean()`; 1.0 means no transparency.
3. **Animate with hard cuts between poses** (`seq(t, [(t0,'pose'),…])`), never cross-dissolves. `Cast.draw` keeps every pose alive: breathing, slow sway, a squash "pop" on each cut, bob; add per-pose wobble/shake/rot for acting.
4. **Cycles (walk / run) = sprite sheets.** Pass a blank WIDE canvas (e.g. 2400×700 #00FF00) as the FIRST reference and the character pose as the second; ask for "exactly N frames in one horizontal row, strict side view facing RIGHT, feet on one baseline, no ground line". `slice_sheet(path, N)` cuts it into registered frames (blobs assigned by centre, floor lines removed, torso-centred). Drop frames whose arms differ from the rest (they flicker). Walk ≈ 6 fps per frame at ~175 px/s for a 370 px tall character; run ≈ 12 fps at ~600 px/s.
5. **Props follow anchors.** Measure an anchor once in source pixels (dome centre, hand, phone) and call `cast.world(anchor)` after drawing; props, FX, fog, stars attach there, so they track every pose and lean.
6. **Locations = wide panoramas.** Pass a blank wide canvas (2400×768) as FIRST ref + an existing style frame as second → a side-scroller strip (~3:1). Scale to 1080 high and move a camera over it: tracking wide shots, hard cut to a 1.6–1.8× medium shot for the gag. Character poses for a side-scroller are side views; generate them at the same scale as the walk frames.
7. Squash the pose on impacts (`sq=(0.9,1.04)`), camera shake, white flash frame, impact lines, orbiting stars; procedural rain/fog/flash on top.

Reference renders: `motion2d/examples/posepack/metro_scene.py` (3 seated characters, 22 key poses, props on anchors) and `motion2d/examples/posepack/street_scene.py` (walk cycle, run cycle, panorama camera, rain, fog, bonk).

## Lessons (from the zebra-crossing sample)
- **The VO leads the mix.** Normalise the VO stem *alone* to ~−16 LUFS; music/ambience beds ~−30 LUFS. Sidechain-duck music, ambience, horns and whooshes 8–12 dB off a VO envelope (80 ms attack / 300 ms release). Keep horns and whooshes short (trim to ~0.3–0.9 s) with a per-SFX loudness target instead of one global gain. Before muxing, measure VO-only vs bed-only loudness inside the VO windows: VO must sit **≥10 dB** above the bed, else fix the mix. Then loudnorm the full mix to −16 LUFS. Reusable version: `motion2d/mix.py` (`Mix`, `verify()`, `check()`, `loudnorm_filter()`); zebra's own build is `motion2d/examples/zebra/audio_mix.py`.
- **Never slide a static pose across the ground.** A character moving toward/away from camera needs front/back **stepping sheets** (4-frame walk, 6-frame hurry), registered on the master pose's canvas like any pose pack. If the model keeps drawing the same leg forward in every frame, mirror only the legs below the hem and blend that strip back in for the alternate frames (`sheets.mirror_legs_below_hem`).
- **Tie cycle fps to ground speed.** Frame rate of a walk/hurry cycle = ground speed ÷ stride length (in the same screen units, scaled with the character), so feet plant instead of skating (`sheets.cycle_fps`). Change speed → change fps, not just the path.

## Animation principles to always apply
- **Anticipation → action → follow-through.** Brush lifts slightly before diving in; arch overshoots and squashes on landing.
- **Squash & stretch** on every landing/impact (`squash()`), pop-in overshoot on every appearance (`back()`, `POP`).
- **Arcs, not straight lines** for flying objects; things enter from off-screen with a whoosh.
- **Secondary motion:** hover bob, little wobble on idle objects, droplets flung from a wiping gauze, sparkles on splats.
- **Contact shadows** under everything that touches the set; cast shadows lift when the object lifts.
- **Stagger.** Never pop two things on the same frame.
- **One focus at a time.** Exit tools (fly off) when their job is done.
- **Claymation feel:** animate "on twos" (12 fps internal → 24 fps out), ±1 px jitter + tiny rotation per step, fingerprint noise texture on clay, slight light flicker. For flat/illustrated styles: 24 fps internal, no jitter, crisper easing.

## Styles (swap the asset prompts, keep the engine)
| Style | Asset prompt core | Motion feel |
|---|---|---|
| Claymation | plasticine stop-motion, Aardman-like, fingerprint texture, soft studio light | on twos, jitter, squash heavy |
| Desi flat illustration | flat Indian illustration, limited palette, bold shapes, slight grain, ornate frame motifs (jharokha arch) | smooth 24 fps, pour/peel actions, characters with blinks and head tilts |
| Paper cut-out | layered paper, visible paper edges, drop shadows | stepped motion, parts hinge at joints |
| 3D toy | glossy soft 3D, pastel | smooth, bouncy overshoot |

## Honest limits (tell the person up front)
- Acting comes from AI-drawn key poses (pose packs) + cycles, not from rotating vector limbs. Lip-sync needs mouth patches per pose (not built yet).
- AI image gen drifts a little between poses: always pass the master pose as the FIRST reference and check registration; regenerate outliers instead of hiding them.
- Facts on screen (dosages, numbers) must be checked by a human expert before publishing.

## Workflow rules
- Show a ~20 s sample scene first; build the full video only after the look is approved.
- Send progress (each generated asset, preview sheets, sample) while working.
- Never publish/post anything in the person's name without asking.
- Credit line as the person specifies (e.g. "Swapnil Agrawal (BDS intern)").

## Repo layout
```
motion2d/claylib.py    clay text plates (Fredoka font), make_item(), pop curve
motion2d/motion.py     easing, squash, paste/pivot/shadow, Path, camera, finish, word_time, ffmpeg_writer
motion2d/sfx.py        procedural SFX + pluck music bed + mix() (simple; prefer motion2d/mix.py for VO-led videos)
motion2d/posepack.py   pose-pack characters: registered key poses, hard cuts, living-pose warp, cycles, anchors;
                     QA: alpha_coverage, green_fringe, despill_edge, check_registration (CLI)
motion2d/sheets.py     slice AI sprite sheets (walk/run) into registered frames; mirror_legs_below_hem, cycle_fps,
                     contact_sheet (walk-check CLI)
motion2d/mix.py        VO-led mix: Mix builder, per-SFX loudness (measured before trim), ducking, master limiter,
                     verify()/check(), linear two-pass loudnorm_filter() (CLI: verify, loudnorm)
motion2d/chunkrender.py parallel chunked frame rendering with warm-up frames, concat + audio mux (CLI)
motion2d/examples/varnish/    claymation: arch drops in, gauze wipes, brush paints with reveal mask, saliva drips, clock spins
motion2d/examples/chai/       desi illustration: kettle tilt + pour stream, cup fill, pods, steam
motion2d/examples/rocket/     paper cut-out (12 fps stepped): countdown, smoke particles, camera follow
motion2d/examples/sprout/     3D toy: slide-in overshoot, watering, sun rays, growth from base
motion2d/examples/vibes/      70s print + deadpan dark humour, built from one style reference
motion2d/examples/posepack/   character acting: metro scene (pose packs) + street scene (walk/run, panorama, rain)
motion2d/examples/zebra/      desi illustration + Hinglish VO: front/back stepping sheets, traffic, tapri pose packs, VO-led ducked mix
motion2d/examples/pawplay/    hand-drawn doodle intro (no VO): 5 pose-pack animals, letter pops, note routed around text, line boil, music-led mix
examples/common.py   shared runner: copy a sample folder, replace assets + draw(), run
AGENTS.md            agent quickstart + QA gates
fonts/               Fredoka
```

## Run the example
```bash
pip install -r requirements.txt   # + ffmpeg on PATH
cd motion2d/examples/varnish
PREVIEW=40,110,185,250 python3 render.py   # stills first
python3 render.py && python3 audio.py      # → final.mp4
```

## New scene recipe (copy motion2d/examples/varnish/render.py)
1. Load BG + layers; set positions/scales.
2. Compute key times from VO words.
3. Per step: `fr = camera(...)` → draw layers back-to-front with their motion functions → particles → labels (small) → `finish(fr, step)`.
4. Append `(t, 'pop'|'whoosh'|...)` to SFX at each action; dump to sfx.json; `sfx.mix()` + ffmpeg mux.


## From a style reference (art style + humour)

When given a reference image (Pinterest pin, poster, frame), copy **two** things, not one:
1. **Look**: palette, outline weight, texture/grain, lettering, how backgrounds are built. Pass the reference as `image_paths` to every asset generation so all cutouts match.
2. **Tone / humour**: what makes it funny or eerie (deadpan, dark sarcasm, absurd, wholesome). Write the VO and the gags around it, and let the *motion* deliver the joke: the calm character stays calm while the world falls apart around him; timing beats (pause, then the punchline action).

Steps: read the reference -> name its style + tone in one line -> write a 10-15 s script with 3 escalating beats and a button ending -> generate bg + 4-6 cutouts with the reference -> time actions to the VO's measured pauses (sentence starts from the energy envelope beat word_time for comic timing) -> stepped fps if the style is print/cut-out. Never commit the reference image itself (it's someone else's art). See `motion2d/examples/vibes/`.
