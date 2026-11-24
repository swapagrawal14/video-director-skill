---
name: motion-doodle
description: Pinterest-style flat 2D motion reels (bouncy logo stings, line-art gag loops, pastel cel slice-of-life loops): flat fills, clean uniform black outlines, bright limited palettes, 9:16 or 1:1, 24 fps crisp with line boil.
author: Swapnil Agrawal (BDS intern)
---

# Motion Doodle playbook

Module: `motion2d/doodle.py` (tests: `tests/test_doodle.py`). It is a style preset on top of the
`motion2d/` engine, not a new engine. Read [MOTION2D.md](MOTION2D.md) first; every rule there still holds.

## The one rule (same as MOTION2D)
**Never SVG / vector / code-drawn characters.** Mascots, characters, props and logo marks are
AI-generated RASTER cut-outs, generated on chroma green `#00FF00` and keyed out. Code only adds what is
FX or type: speed lines, impact bursts, the slam-in text, the flat colour plate, the line boil.

## When to use
- Short loops and stings: 3-12 s, often no VO, music-led (logo sting, brand mascot, reel intro/outro, sticker-like gag loops).
- The person shows a flat, bold, "motion design" Pinterest pin: flat colours, thick even black lines, no shading.
- Not for: procedures that need accuracy (use bench demo / 3D), horror (use the horror recipe), long acting scenes
  with dialogue (use pose packs + `vidliboom/`). A doodle character CAN carry a short VO hook.

## Three reference looks (style only, described in words)
Copy palette, line weight and motion feel. Never copy a brand, logo, mascot design or any text from a reference.

| # | Look | Palette (`PALETTES`) | What moves |
|---|---|---|---|
| 1 | **Bouncy logo sting**: flat pink plate, a black-and-cream vehicle mascot (e.g. an ice-cream truck) hops in place | `bubblegum` | body `bounce()` with squash on every landing, wheels `wheel_spin()`, a speech bubble pops in (`back()` + `impact_burst`), bold word slams in with `pop_text()`, line boil on everything |
| 2 | **Line-art runner gag**: yellow plate, black line-art on white, a delivery man balancing on one wheel | `sunny_lineart` | one wheel spins, body rocks with `Puppet.wiggle`, `speed_lines()` trail behind, background props scroll past for speed, seamless loop |
| 3 | **Pastel cel bedroom**: soft pastel flat cartoon, a guy stretching after waking up, ceiling fan above | `pastel_cel` | arms rise with `Puppet.bend` on rubber-hose pins, `Tweener` between yawn/stretch keys, fan blades spin as a separate layer, curtain wiggle, loop |

`mono_ink` (off-white, black, one red spot) is the fallback for anything editorial.

## Asset generation
1. **Master asset first.** `asset_prompt(subject, palette, kind)` gives the prompt core (flat fills, uniform black
   outline ~6 px at 1080, no gradients/shading/texture, on `#00FF00`, NEGATIVE list). Generate the whole character/mascot
   once, check it, key it, `despill_edge()`, `alpha_coverage()` (posepack.py QA gates).
2. **Parts from the master.** With the master as FIRST reference image, generate every part that must move on its own as a
   separate image: wheels (one wheel, flat-on, centred, square canvas), speech bubble (empty, no text), fan blades
   (centred hub), the body WITHOUT wheels, arms if they need big moves. "Same character, same outline weight, same palette
   as the first reference."
3. **Poses, if acting.** Short acting = 3-5 registered key poses (pose-pack method) + `Tweener` / `Puppet` in between.
4. **Background plate** with `kind='background'`, or just `flat_bg(W, H, palette)` (most doodle reels use a flat plate).
5. **Text is rendered by code** (`pop_text`, `text_layer`, fonts `motion2d/fonts/Fredoka.ttf` Bold or `fonts/baloo2.ttf`
   ExtraBold). Only a `logo_mark` may carry lettering from the model, and only text the person gave.
6. If the person sends a style reference, pass it as the FIRST image on every asset (INTAKE.md, style reference rules)
   and do a 3-frame style test before making the rest.

## Combining with the other motion2d modules
These are written in parallel; use them by these APIs.
- **`motion2d/warp.py`**: rubber-hose limbs on a single cut-out.
  `P = Puppet(im, {'shoulder': (x, y), 'elbow': ..., 'hand': ..., 'hip': ...}, pad=40)`
  `P.pose({'hand': (x2, y2)})`, `P.bend('shoulder', ['elbow', 'hand'], -35)`, `P.wiggle(t, ['hand', 'hat'])`.
  Pin anchors (hips, feet) stay put; bends stay smooth like a rubber hose. Apply `line_boil()` AFTER the warp.
- **`motion2d/inbetween.py`**: smooth pose changes. `Tweener` between key pin sets, `tween(a, b, t)` for any
  value/pin dict, `smear()` for one-frame smear on fast moves (arm swing, slam).
- **`motion2d/loop.py`**: `Beat(bpm)` to put hops and pops on the beat, `cyc(t, L)` for loop-safe phase,
  `export_loop(...)` for seamless loops. Choose `period` (bounce) and `rpm` (wheels/fan) so they complete whole
  cycles in the loop length L (e.g. L = 4 s, period 0.5 s, wheel 60 rpm = 4 turns).
- **`motion2d/handdrawn.py`**: frame-by-frame finish (on twos, boil per drawing, wobble outline, texture fills, paper grain, smears, draw-on, onion skin); read [HAND_DRAWN.md](HAND_DRAWN.md), demo `examples/truck-sting/`.
- **`motion.py`**: `paste`, `xform`, `place_pivot`, `back`, `squash`, `ffmpeg_writer(..., fps=24, out_fps=24)`.

## Pipeline (8 steps)
1. **Brief in one line**: look (1/2/3 above), format (9:16 1080x1920 or 1:1 1080x1080), length, loop or sting, music/VO.
2. **Beat sheet**: one row per beat: `t, what moves, FX, SFX` (land/boing, pop, whoosh, slam). Put beats on `Beat(bpm)`.
3. **Assets**: master -> keyed -> QA -> parts (wheels, bubble, blades) -> 3-5 poses if acting.
4. **Rig**: pivots for parts (wheel centres measured once in source px), Puppet pins for limbs.
5. **Animate** at 24 fps: per step `fr = BG.copy()` -> back-to-front: speed lines, body (`bounce` + `xform`, placed by its
   bottom edge), wheels, bubble, `pop_text` -> `line_boil()` on each character/prop layer -> `finish(fr, step)`.
6. **Preview**: 6-8 stills contact sheet, LOOK (outline even? no green fringe? text readable at phone size?).
7. **Render** via `ffmpeg_writer(path, W, H, fps=24, out_fps=24)`; loops via `export_loop`. SFX logged per action, `mix.py`.
8. **QA + deliver**: AGENTS.md gates, loop seam check (first vs last frame), ask before posting anything.

## Timing rules
- **Doodle = 24 fps internal, crisp.** No stop-motion jitter, no flicker, no vignette, no grain (`DOODLE_FINISH` default).
  12 fps "on twos" is for claymation/paper looks, not this one.
- **Line boil holds 2-3 frames** (`line_boil(im, step, hold=3)`, amp 0.8-1.6 px at 1080). Use the same `hold` for every
  layer, and different `seed` per layer so they do not boil in lockstep.
- **Snappy easing**: entrances with `back()` over 6-8 frames (0.25-0.33 s); landings with squash 0.1-0.15; holds of
  8-12 frames between beats so the eye can read.
- **Stagger**: never pop two things on the same frame (bubble, then 3-4 frames later the word).
- **Wheels roll, not skid**: `rpm = 60 * speed_px_s / (pi * wheel_diameter_px)`; when the vehicle hops in place, 60-120 rpm.
- **Loops**: every cycle (bounce period, rpm, wiggle freq, speed-line `speed`) must divide the loop length.

## Checklist
- [ ] No code-drawn character or prop; all art is keyed raster cut-outs (FX strokes and type are the only code drawing)
- [ ] Flat fills, one even outline weight across all assets (regenerate outliers, do not fake it)
- [ ] Palette = one `PALETTES` entry; no stray gradient, no green fringe (`green_fringe < 0.05`)
- [ ] 24 fps, boil hold 2-3, boil amp <= 1.6 px
- [ ] Every landing squashes, every entrance overshoots, nothing pops on the same frame
- [ ] Text rendered by code, readable on a phone, no text copied from any reference
- [ ] Loop seam invisible (if a loop); sting ends on a 0.5-1 s hold
- [ ] Credit "Swapnil Agrawal (BDS intern)"; nothing posted without asking

## Honest limits (tell the person up front)
- True frame-by-frame hand animation (every frame redrawn) is approximated with key poses + warp + tweening + line boil.
  Expect about an 80% match to a hand-animated pin: the boil and squash sell it, but big turns (a head turning 3/4 to
  profile) still need an extra AI key pose, and smears are faked.
- Line boil is a raster displacement, so it wobbles fills and lines together; at amp > 2 px thin details smear.
- AI image models drift in outline weight between parts; the fix is regeneration with the master as first reference.
- Puppet/inbetween/loop APIs above are referenced as specified; check their docstrings once those modules land.
