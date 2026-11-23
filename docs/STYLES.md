# Genre recipes

Pick one. Each recipe sets camera language, pacing, overlays, music and type. Recipes are starting points: the colours, set and character come from this video's look sheet (`docs/FRESH_LOOK.md`), put into `project.json` `look` + `theme`.

---

## 1. Pixar Clinic (one option for tutorials & procedures, not the default for every dental video)
> Pick it only when it fits; most dental videos need their own set and palette (`docs/FRESH_LOOK.md`). Even with this recipe, build a new set, character and caption style: the example below is a quality reference only.
- **Look**: soft clearcoat plastics, warm key + cool rim, bokeh teal-to-peach backdrop, wooden bench + coloured mat. Chunky rounded models (typodont, organs, devices) slightly stylised but anatomically/technically correct.
- **Theme**: accent `#e2475b`, accent2 `#3b82c4`, highlight `#ffd23f`, background `["#24557a","#5fa6b8","#f2cfa8"]`.
- **Camera**: slow orbits 10–25°, push-in for every detail step, wide shot for "armamentarium"/parts.
- **Overlays**: step chip ("STEP 3 / 12 · BONDING"), 3D callout labels, timer badge for durations, list cards for rules.
- **Pacing**: 9–14 s scenes. Mascot at intro, rules, outro.
- **Music**: `calm` (or `upbeat` for younger audience), gain 0.5–0.6.
- **Example (quality reference only, never copy its set, mascot, colours or captions)**: `examples/braces-tutorial`. Using these exact theme colours needs `look.reuse_reason` or lint fails.

## 2. Blueprint Tech (engineering, software, systems)
- **Look**: dark navy `#0b1a2e` background (set `background` to three navy tones), cyan wireframe edges (`EdgesGeometry` + `LineBasicMaterial`) over matte solids, grid floor (`GridHelper`), glowing data packets (small emissive spheres moving along `CatmullRomCurve3`).
- **Theme**: accent `#22d3ee`, accent2 `#a78bfa`, highlight `#facc15`, bench/mat hidden (`bench.visible=false`).
- **Camera**: isometric-ish (`el` ≈ 0.6), smooth lateral tracks, exploded views (parts slide apart on their normals).
- **Overlays**: monospace-feel labels, code snippets on cards, flow arrows.
- **Music**: `lofi`.

## 3. Cinematic Horror (adult, genuinely unsettling)
- **Look**: near-black backdrop, single cold key light (`#9fb4ff`, low intensity) + flickering warm practical (point light whose intensity = noise(t) from a seeded table), heavy fog (`scene.fog = new THREE.FogExp2('#05070a', .012)`), desaturated grade (exposure .7), film grain + vignette drawn in the 2D overlay (pre-generate a few noise canvases, pick by frame).
- **Camera**: slow creeping dollies, low angles, long holds, a sudden whip/cut for the scare. Dutch tilt (camera.rotation.z) in tense beats.
- **Story**: cold open (strange detail) → normal world → wrongness escalates in 3 beats → reveal → unresolved sting. Never cartoon monsters; imply with silhouettes, doors, shadows, things that moved between shots.
- **Type**: no cute fonts; thin serif or condensed caps, white at 80% opacity, slow fades. No mascot, no progress bar, no step chips.
- **Audio**: `music.py horror` + `bash scripts/sfx_horror.sh <dir>/sfx` (sub drone, dark room tone, riser, stinger, heartbeat). Build → 0.5–1 s `mute` vacuum → stinger on the visual frame (docs/CRAFT.md §6).
- **Finish**: `grade.py --look horror --grain 14 --vignette 0.6 --ca 2` (optional `--bars 2.39`). Captions: `--style pop`, thin white, no yellow.

## 4. Product Hero (launch, promo, app demo)
- **Look**: studio cyclorama (light grey gradient), glossy hero product on a turntable, big soft area lights, reflections on floor (clearcoat floor plane).
- **Camera**: 360° turntable, macro push-ins on features, a final hero angle with logo.
- **Overlays**: bold feature callouts (one word + one line), price/CTA end card.
- **Pacing**: fast. 3–6 s shots, 30–90 s total. Cut on music beats: `beats.py` + `"beat_snap": true`. Grade `teal_orange --vignette 0.3`. Export youtube + shorts + square.
- **Music**: `upbeat` or `epic`.

## 5. Storybook (kids, fables, narrative)
- **Look**: toy-like world, pastel palette, everything round, characters with big eyes (reuse the mascot rig: eyes/lids/arms), paper-cut layers via flat planes at different depths for parallax.
- **Camera**: gentle side-scrolling tracks between "pages".
- **Overlays**: hand-written font (`fonts/caveat.ttf`) for narration text.
- **Music**: `calm`.

## 6. Kinetic Type (quotes, listicles, reels, shorts)
- **Look**: 2D first — draw typography in the overlay canvas, each word animated (scale-in with `back()`, slide, mask reveal), with a subtle 3D background (floating shapes, slow camera drift).
- **Format**: for reels set `width` 720 and use a 9:16 variant (change `H = W*16/9` and viewport in `_server.py`).
- **Pacing**: sync word appearance to VO: split `sub` into words and distribute over the scene's `vo` time.
- **Music**: `upbeat`.

## 7. Data Story (stats, finance, history)
- **Look**: clean white/cream backdrop, 3D bar/columns (`BoxGeometry` scaled by value with eased growth), lines as tubes, a globe from `SphereGeometry` with lat/long dots.
- **Rules**: every number on screen comes from a cited source; show the source in small text on the card.
- **Music**: `lofi` or `epic`.

---

## Universal quality bar
- First 3 seconds must already be beautiful and moving (hook).
- Every scene has motion in 3D, not only text.
- Consistent palette and type across the whole video.
- Subtitles always readable (dark pill, ≤ 2 lines).
- End card: title ✓, one-line takeaway, credit.


## Finishing defaults per recipe
| Recipe | Grade | Captions | Exports |
|---|---|---|---|
| Pixar Clinic | `warm --mix 0.5` or none | engine `sub` (or `pop` for Shorts) | youtube + shorts cut of the best step |
| Blueprint Tech | `teal_orange --mix 0.5` | `karaoke` | youtube |
| Cinematic Horror | `horror --grain 14 --vignette 0.6 --ca 2` | `pop`, white only | youtube + shorts |
| Product Hero | `teal_orange --vignette 0.3` | `pop --upper` | youtube + shorts + square |
| Storybook | `warm --grain 6` | `karaoke` | youtube |
| Kinetic Type | none | the type IS the caption | shorts + portrait |
| Data Story | `bleach --mix 0.4` | `karaoke` | youtube + square |
