---
name: cartoon
description: Full cartoon scenes and short episodes in ANY art style (pastel cel, anime, rubber-hose, chibi, crayon, paper, watercolour, desi gouache, dark horror, or a style read from the user's reference): locked style, acting pose packs, layered sets, story lighting, prop rigs, moving worlds, one beat sheet driving pose + SFX + camera.
author: Swapnil Agrawal (BDS intern)
---

# Cartoon playbook (agent-first)

Module: `motion2d/cartoon.py` on top of the `motion2d/` engine. Read [MOTION2D.md](MOTION2D.md) once; its rules
still hold. Style gallery: [ARTSTYLES.md](ARTSTYLES.md). The person may know nothing about animation: you are the
director, the animator and the editor. They only answer short questions and approve stills.

**Hard rules**
- **Raster only, no SVG ever.** Characters, props, parts and sets are generated per video as raster images in the
  locked style, keyed off `#00FF00`. Code adds only light, FX, camera, timing and finish.
- **Never copy** a studio's, show's, brand's or living artist's characters, logos, text or story. A reference gives
  the LOOK only (palette, line, texture, motion feel).
- **Horror, when chosen, is adult and genuinely scary**: real dread, slow build, silence before the hit, no cute
  faces, no kiddie jokes. Use `dark_cartoon` or a night grade; see the lamp-off gag below.
- Nothing is posted, published or sent in anyone's name without asking.

## 1. When to use
| Use cartoon.py | Use something else |
|---|---|
| A cartoon scene or short (5 s to ~3 min) where characters act, lights change, the world moves | Procedures with exact steps (bench demo, `docs/MOTION2D.md` / `template/`) |
| "Make a cartoon like <reference>", any named art style, YouTube-animator look | Dialogue-heavy script-to-episode with lip-sync → `vidliboom/` (`docs/EPISODE_SCRIPT.md`) |
| Mood gags (lamp off, power cut, TV glow), loops (tiny planet ride, side-scroller), mascot shorts | Flat logo stings / beat-synced doodle loops → `docs/MOTION_DOODLE.md` (combine freely) |

## 2. Zero-knowledge intake (one message, defaults so one word works)
Ask in the person's language (Hinglish if they write Hinglish). Each line has a default; "ok" accepts all.
1. **Idea** — one line, or "surprise me" (then offer 3 ideas from `prompts/README.md` that fit them).
2. **Look** — a reference (link, screenshot, short clip) OR a style name: `pastel_outline` (default), `flat_no_outline`,
   `rubber_hose`, `anime_cel`, `chibi_sticker`, `crayon_kids`, `paper_cutout`, `watercolor_storybook`,
   `desi_gouache`, `dark_cartoon`. Describe them in plain words ("soft pastel with thin outlines"), not keys.
3. **Format** — 9:16 reel 1080x1920 (default), 16:9 1920x1080, or 1:1.
4. **Length** — 20-30 s (default), a 4-8 s loop, or 1-3 min episode.
5. **Voice** — no voice: SFX + music, the acting tells it (default); or VO / character voices (which language).
6. **Credit** — end-card name/handle exactly as they want it (default: none on screen).

Then, still mandatory (SKILL.md): **3 numbered treatments**, one line each, all in the chosen style, your pick
marked, wait for a choice. Example for "lamp off, gentle spooky, pastel":
1. **Mood gag (pick):** one room, lamp click → violet power cut, clothes on the hook become hooded figures with glowing eyes, lamp back on, just clothes.
2. **Mini episode:** 3 shots (bedroom wide, close on the boy, close on the hook) with hard cuts and a match on action.
3. **Seamless loop:** the boy keeps clicking the lamp on/off and the figures inch closer each cycle, 6 s loop.

## 3. Style lock (before any asset)
Pick ONE pack and keep it for every asset and shot.
| Key | One-line use |
|---|---|
| `pastel_outline` | cosy slice-of-life, gentle spooky, Pinterest pastel cel |
| `flat_no_outline` | promo loops, brand mascots, clean motion design |
| `rubber_hose` | bouncy 1930s-style vintage gags |
| `anime_cel` | emotional, cinematic moments |
| `chibi_sticker` | cute mascots, reactions, sticker energy |
| `crayon_kids` | storybook, nostalgia, kid-drawing charm |
| `paper_cutout` | crafty explainers, layered sets |
| `watercolor_storybook` | soft, warm narrated stories |
| `desi_gouache` | Indian homes, streets, festivals |
| `dark_cartoon` | adult creepy horror, stylised |

**From a reference (any style):**
```bash
python3 scripts/style_ref.py ref.mp4 projects/<slug>/style.json --name cosy_room   # image or video
```
It writes `style.json` (palette, outline px, ink, prompt core, night grade, `measured` numbers) plus
`style_palette.png`. Show the swatch sheet to the person. Then **also** pass the reference image as the FIRST image
input on every asset generation (INTAKE.md, style-reference rules): words alone drift. Copy the look only, never
its characters, brand, logo, text or story, and never commit the reference file.

```python
import json, sys; sys.path.insert(0, 'motion2d')
from cartoon import ARTSTYLES, style_prompt, palette_sheet
STYLE = json.load(open('projects/<slug>/style.json'))     # or ARTSTYLES['pastel_outline']
```
Do a **3-frame style test** (master character, set, one prop) and get a yes before generating the rest.

## 4. Character sheet → pose pack
1. **Master first:** `style_prompt(STYLE, '<who, clothes, colours, one silhouette hook>', kind='character')`.
   Generate, key `#00FF00`, `despill_edge()`, check `alpha_coverage()` 0.05-0.6.
2. **4-8 poses** for this video's beats, each with the master as the FIRST reference image:
   `style_prompt(STYLE, 'POSE: reaching for the lamp, same canvas and framing as the first reference', kind='pose')`.
   Act beats, not words: idle, reach, freeze, peek, slap_switch, relief, yank_blanket...
3. **Name files** `cast/<name>/<name>_<pose>.png` (that is what `Cast(prefix, poses)` loads).
4. **Gates (every asset, regenerate failures, never hide them):**
```python
import glob; from PIL import Image
from posepack import check_registration, despill_edge, alpha_coverage
from cartoon import palette_match
rows, probs = check_registration(sorted(glob.glob('cast/boy/boy_*.png')))   # same canvas, feet baseline, height
assert not probs, probs                                                    # fix_scale or regenerate outliers
for p in glob.glob('cast/**/*.png', recursive=True) + glob.glob('props/*.png'):
    assert palette_match(Image.open(p), STYLE) >= 0.6, p                     # style lock; textured styles may sit lower, look first
```
CLI: `python3 motion2d/posepack.py 'cast/boy/boy_*.png'`. Faces must not change on their own between poses
(CHARACTERS.md); if they do, regenerate with the registered pose as first ref.

## 5. Set plates and separate parts
- **Set:** `style_prompt(STYLE, 'small bedroom at night-light hour, bed left, lamp on side table, coat hook right', kind='set')`
  → full plate, no characters, room for action in the middle third. Wide panorama (2400x768 blank canvas as first ref)
  for side-scrolls.
- **Anything that moves is its own part** (`kind='part'`, master/set as first ref): fan blades (centred hub, square
  canvas), lamp shade + lamp glow, door, curtain, clothes on the hook (one PNG per garment), a second "figure"
  version of each garment on the SAME canvas (hood taller, shoulders hunched) for the swap, bike wheels.
- Paint the set WITHOUT those parts, so nothing is doubled. Measure pivots once in source px (hook top, hub centre).

## 6. Beat sheet (acting + SFX + camera in one table)
Write it before coding. One row per thing that happens: `(t, actor, act, sfx, note)`. Actors are cast names or
props; `cam` and `light` rows need no SFX.
```python
from cartoon import BeatSheet
beats = BeatSheet([(0.0, 'boy', 'read', 'dab', 'fan spinning'), (2.2, 'boy', 'reach', 'whoosh'), ...])
probs = beats.check(DUR, max_still=4.0)          # no character holds >4 s; every character/prop beat has a sound
assert not probs, probs
print(beats.action_list())                        # paste into the storyboard message
beats.to_json('projects/<slug>/beats.json')
```
- `beats.pose('boy', t)` = current pose; `beats.since('boy', t)` = seconds since its last beat (squash, settle).
- `beats.sfx_events()` → `[(t, name)]` for the mix. Names are `sfx.FX` keys (`pop squish whoosh dab plip tick boing
  pour thunder ring`) or your own WAVs (`bash scripts/sfx_horror.sh sfx/` gives `drone_sub room_tone_dark riser_4s
  stinger heartbeat`).
- **Mute test:** with sound off, the beat table alone must tell the story. A row with no visible change is a FAIL.

## 7. Light tells the story
```python
from cartoon import Light, glow_eyes, light_pool, night_grade_for
NIGHT = night_grade_for(STYLE)                     # violet / blue / indigo / sepia / horror per pack
L = Light([(0, 'day'), (2.4, NIGHT), (6.2, 'day')], fade=0.0, flicker=[(2.4, 0.35), (6.2, 0.25)])
fr = L.apply(fr, t)                                # grade the whole room first
light_pool(fr, LAMP_XY, 260, '#FFE7B3', 0.55 * L.level(t, 'day'))          # emissive AFTER the grade
glow_eyes(fr, EYES, t, on=L.level(t, NIGHT), color='#FF3D9A', blink=[(4.4, 0.12)])
```
- Grades (`GRADES`): `day sunset night violet powercut blue indigo sepia horror tv_glow`. A switch is instant
  (`fade=0`), a dawn is `fade=1.5`. `flicker=[(t, dur)]` makes a bulb stutter before it settles.
- `L.level(t, name)` is 0..1: drive every light source with it so eyes, lamp pools and screens follow the switch and the flicker.
- **Hide drawing swaps inside flicker frames** (clothes → figures): the eye never sees the change happen. Scarier, and cheaper.

## 8. Prop rigs (keep the frame alive)
```python
from cartoon import spin, swing, shake, push, camera_frame
paste(fr, spin(BLADES, t, rpm=90, blur_deg=18), *FAN_HUB)                       # ceiling fan
place_pivot(fr, HOODIE, *HOOK, (HOODIE.width / 2, 10), swing(t, 3.0, 0.5, damp=1.2, t0=6.2))  # bumped garment settles
dx, dy = shake(t, 6.2, dur=0.3, amp=10)                                           # impact / scare
fr = camera_frame(fr, zoom=push(t, 3.4, 6.0, 1.0, 1.15), cx=W * 0.6, cy=H * 0.45, dx=dx, dy=dy)
```
Idle props move too: fan always spins, curtain/garments sway `swing(t, 1.5, 0.3)`, a clock ticks. `doodle.line_boil(part,
step, amp=STYLE['boil'], hold=2)` on prop/part layers when the style boils (amp 0 = skip).

## 9. Moving worlds
- **Parallax** (side-scroller): `PX = Parallax([(sky, 0.0), (hills, 0.25), (trees, 0.6), (road, 1.0)], W, H, speed=240)`;
  `fr = PX.render(t)`. For a loop, `speed * depth * L` must be a multiple of each layer's width.
- **TinyPlanet** (ride loop): `TP = TinyPlanet(disc, (W/2, H*0.95), R, props=[(tree, 0, 0), (house, 90, -6), ...], deg_per_s=-22.5)`;
  `TP.draw(fr, t)`; the hero stands at `TP.top()`. For a loop: props and disc pattern n-fold symmetric and
  `|deg_per_s| * L == 360 / n` (or one full turn per loop).

## 10. Timing on twos
`t = hold_time(step / FPS, STYLE['hold'])` quantises motion like hand animation (`ones` for flat motion design,
`twos` for most cartoon packs, `threes` for crayon/stop-motion feel). Write 24 fps out; held drawings repeat.
Hard-cut poses; `inbetween.Tweener` 3-5 frames only for small changes; `inbetween.smear` 1-2 frames on fast moves.
`Cast(..., pop=STYLE['squash'])` sets the squash on each cut.

## 11. Episodes (several shots)
```python
from cartoon import Episode
EP = Episode([('wide_room', 3.0), ('close_boy', 2.0), ('close_hook', 2.5), ('wide_room_2', 2.5)])
i, shot, lt, u = EP.at(t)              # shot index, name, local time, 0..1 progress
```
Hard cuts only. **Match on action:** start a move in shot A (hand reaching), cut 2 frames before it lands, finish it
in shot B (hand hits the switch). Keep screen direction; same `Light` across shots so a cut never resets the mood.
Wide → close for the gag → wide for the reaction. One beat sheet for the whole episode (global `t`).

## 12. Finish
`finish = make_style_finish(W, H, STYLE)` adds the pack's paper texture and grain and returns uint8. Call it last
(after grade, light, camera). Flat packs have paper=grain=0, so finish only clips.

## 13. Render loop skeleton (chunkrender-compatible)
```python
# projects/<slug>/scene.py   (run from the repo root)
import os, sys, json, glob, numpy as np, cv2
sys.path.insert(0, 'motion2d')
from PIL import Image
from motion import paste, place_pivot, ffmpeg_writer
from posepack import Cast, despill_edge
from cartoon import (ARTSTYLES, Light, glow_eyes, light_pool, night_grade_for, spin, swing, shake, push,
                     camera_frame, BeatSheet, hold_time, make_style_finish)
import sfx, mix

P = 'projects/lamp-gag'
FPS, DUR, W, H = 24, 9.0, 1080, 1920
STYLE = ARTSTYLES['pastel_outline']                  # or json.load(open(f'{P}/style.json'))
NIGHT = night_grade_for(STYLE)
SET = cv2.imread(f'{P}/set.png').astype(np.float32)  # pre-sized to W x H
part = lambda n: despill_edge(Image.open(f'{P}/props/{n}.png'))
BLADES, HOODIE, HOODIE_FIG = part('fan_blades'), part('hoodie'), part('hoodie_figure')
FAN_HUB, HOOK, LAMP = (540, 210), (880, 760), (250, 1010)
EYES_SRC = [(118, 92), (150, 92)]                    # eye spots in hoodie_figure source px
BOY = Cast(f'{P}/cast/boy/boy', ['read', 'yawn', 'reach', 'freeze', 'peek', 'slap_switch', 'stare', 'relief',
           'yank_blanket'], x=380, floor=1500, scale=0.9, pop=STYLE['squash'])
beats = BeatSheet(json.load(open(f'{P}/beats_src.json')))     # [[t, actor, act, sfx, note], ...] = table A below
L = Light([(0, 'day'), (2.4, NIGHT), (6.2, 'day')], flicker=[(2.4, 0.35), (6.2, 0.25)])
finish = make_style_finish(W, H, STYLE)

def frame(t, step):
    t = hold_time(t, STYLE['hold'], FPS)
    fr = SET.copy()
    paste(fr, spin(BLADES, t, rpm=90, blur_deg=18), *FAN_HUB)
    dark = beats.pose('hoodie', t) in ('figures', 'eyes_blink', 'lean')   # 'figures' row sits inside the flicker
    g = HOODIE_FIG if dark else HOODIE                             # swap lands inside a flicker frame
    ang = swing(t, 3.0, 0.5, damp=1.2, t0=6.2) + swing(t, 1.2, 0.3)
    place_pivot(fr, g, *HOOK, (g.width / 2, 10), ang)
    BOY.draw(fr, t, beats.pose('boy', t))
    fr = L.apply(fr, t)                                            # grade
    light_pool(fr, LAMP, 260, '#FFE7B3', 0.55 * L.level(t, 'day'))
    ex = [(HOOK[0] - g.width / 2 + x, HOOK[1] - 10 + y) for x, y in EYES_SRC]   # ok while the swing is small
    glow_eyes(fr, ex, t, on=L.level(t, NIGHT) * dark, blink=[(4.4, 0.12)])
    dx, dy = shake(t, 6.2, dur=0.3, amp=10)
    fr = camera_frame(fr, zoom=push(t, 3.4, 6.0, 1.0, 1.15), cx=W * 0.6, cy=H * 0.45, dx=dx, dy=dy)
    return finish(fr, step)

def audio(path):
    N = int(DUR * sfx.SR); buf = np.zeros(N, np.float32)
    MAXLEN = {'drone_sub': 3.6, 'heartbeat': 1.8, 'riser_4s': 0.6}  # long beds/risers cut dead at the lamp-on
    for t, name in beats.sfx_events():
        clip = sfx.FX[name]() if name in sfx.FX else mix.read(f'{P}/sfx/{name}.wav')
        clip = clip[:int(MAXLEN.get(name, 99) * sfx.SR)]
        mix.place(buf, clip, t, 0.8)
    mix.place(buf, sfx.pluck_bed(DUR, vol=0.02), 0)                 # or scripts/music.py; VO videos: mix.Mix
    mix.write(path, buf / max(1.0, np.abs(buf).max() / 0.9))

if __name__ == '__main__':
    prev = os.environ.get('PREVIEW')                                # PREVIEW=0.5,2.5,3.5,6.3,8.4
    if prev:
        for s in prev.split(','):
            cv2.imwrite(f'{P}/shots/t{float(s):05.2f}.jpg', frame(float(s), int(float(s) * FPS)))
        sys.exit()
    assert not beats.check(DUR), beats.check(DUR)
    wr = ffmpeg_writer(f'{P}/video.mp4', W, H, fps=FPS, out_fps=FPS)
    for step in range(int(DUR * FPS)):
        wr.stdin.write(frame(step / FPS, step).tobytes())
    wr.stdin.close(); wr.wait(); audio(f'{P}/mix.wav')
```
Then `python3 scripts/loudnorm.py mix.wav mix_ln.wav -14` and mux (`ffmpeg -i video.mp4 -i mix_ln.wav -c:v copy
-c:a aac -b:a 192k -ar 48000 -movflags +faststart final.mp4`). Long or 1080p renders that hit a shell timeout:
`python3 motion2d/chunkrender.py projects/<slug>/scene.py --chunks 8 --chunk i --work /tmp/cr`, then `--join`
(warm-up keeps `Cast` pop state right). Make `mkdir -p shots` first. Positions above are placeholders: measure yours.

## 14. Storyboard stills before the full render
`PREVIEW=0.5,2.5,3.5,4.6,6.3,8.4 python3 projects/<slug>/scene.py` → one still per beat → contact sheet → LOOK at
it yourself (style match, faces consistent, no green fringe, eyes on the garment, readable at phone size) → send it
to the person with `beats.action_list()` and get a yes. Looking at stills yourself is not approval.

## 15. QA and delivery
- `python3 scripts/qa.py final.mp4` must print **QA PASSED** (loudness, black/frozen frames, A/V sync, yuv420p).
  A true blackout longer than 0.25 s fails blackdetect: keep night grades lifted (check a still of the darkest beat).
- `python3 scripts/motion_qa.py final.mp4 --at 2.2,6.0 --len 2.4` → look at the strips: no face changing by itself,
  no pose under 4 frames, no sliding feet, no jitter.
- Loops: `loop.assert_seamless(frame(0, 0), frame(L, N))`, then `loop.export_loop(frames, 'reel.mp4', repeat=3, audio=...)`.
- Deliver MP4 + thumbnail + title/description/tags; credit line exactly as given. Never post for them.

---

## Worked example A: the lamp-off gag (9 s, 9:16, no VO)
Room at night-light hour: boy reading in bed, ceiling fan turning, lamp on the side table, a hoodie and a raincoat on
the wall hook. Pastel → gentle spooky comedy. `dark_cartoon` → play it straight and scary (longer dark, no relief beat,
button = one hook is empty).

| t (s) | actor | act | sfx | note |
|---|---|---|---|---|
| 0.00 | boy | read | dab | lamp pool on, fan spins, garments sway softly |
| 1.20 | boy | yawn | squish | slow push not started yet |
| 2.20 | boy | reach | whoosh | arm to the lamp, anticipation |
| 2.40 | lamp | click_off | tick | `Light` → NIGHT, flicker 0.35 s |
| 2.40 | light | NIGHT | - | room goes violet (pastel pack) |
| 2.60 | hoodie | figures | drone_sub | drawing swap lands inside the flicker; glow eyes follow `L.level` |
| 3.30 | boy | freeze | plip | gulp; hold |
| 3.40 | cam | push 1.0→1.15 | - | toward the hook, ends 6.0 |
| 4.40 | hoodie | eyes_blink | heartbeat | one 0.12 s blink: the "figures" are alive |
| 4.80 | boy | peek | squish | blanket up to the nose |
| 5.60 | hoodie | lean | riser_4s | figure tilts toward the bed (swing offset); riser cut dead at 6.2 |
| 6.20 | boy | slap_switch | tick | `Light` → day, flicker 0.25 s, `shake` |
| 6.20 | lamp | click_on | pop | lamp pool returns |
| 6.25 | hoodie | just_clothes | boing | swap back inside flicker; garment swings (damp bump at 6.2) |
| 6.60 | boy | stare | squish | at the hook, deadpan |
| 7.40 | boy | relief | whoosh | exhale, shoulders drop |
| 8.20 | hoodie | sleeve_wave | whoosh | button: one sleeve lifts by itself (swing on the sleeve part) |
| 8.50 | boy | yank_blanket | squish | over the head; end on a 0.5 s hold |

`beats.check(9.0)` passes: boy never holds >1.5 s, lamp ≤3.8 s, every character/prop row has a sound.

## Worked example B: tiny-planet ride loop (4 s seamless, 1:1, music-led)
Hero pedals a bicycle on top of a small round planet; a tree, a house, a lamp post and a sleeping cat stand at 0/90/180/270°
and pass by. 120 bpm, `L = loop_len(120, bars=2) = 4.0 s`. Disc pattern 4-fold symmetric, `deg_per_s = -22.5`
(90° per loop = one prop slot). Walk/pedal cycle from a sprite sheet (`sheets.slice_sheet`), fps so
`fps * L` is a multiple of its frame count. Call `RIDER.draw(fr, t, RIDER.cycle('pedal', t, fps), live=False, dy=bob)`
with `bob = 6 * loop.csin(t, L, k=8)`: the built-in raw-`t` breathing would break the seam. Wheels: `spin(wheel, t, rpm=60)` (4 turns per loop).

| t (s) | actor | act | sfx | note |
|---|---|---|---|---|
| 0.00 | rider | pedal | tick | frame 0 is mid-motion; bob on every beat (`Beat.pulse`) |
| 0.00 | cam | bob on beat | - | tiny `camera_frame` zoom pulse 1.0→1.02 |
| 1.00 | rider | wave | pop | waves at the cat passing the top |
| 1.50 | cat | ear_flick | plip | cat part swaps one drawing |
| 2.00 | rider | bell | ring | on the bar; lamp post blinks on (`light_pool`) |
| 3.00 | rider | hop | boing | small bump on the disc; squash on landing |
| 3.50 | rider | pedal | whoosh | back to the frame-0 pose before the seam |

Render one warm-up loop and export the second pass (keeps `Cast` pop state identical at the seam); then
`assert_seamless`, `music_for_loop(..., after=4.0)`, `export_loop(frames, 'ride.mp4', repeat=3, audio='loop.wav')`.

## Gotchas learned on `examples/powercut-cartoon`
- Image models return **RGB with the green screen baked in**. Run `posepack.chroma_key(im)` (float maths, then despill) and `drop_specks(im)` on every pose/prop before `check_registration`; coverage ~0.99 means the key failed.
- SFX-only mixes (thunder, stingers) fail qa.py true peak with plain loudnorm: use `scripts/loudnorm.py in.wav out.wav -14 -1.0 --tame`.
- A ceiling fan from a top-down blade PNG reads right if you rotate it, then squash it to ~0.26 height for perspective; integrate the rpm for wind-down/up instead of `spin(t)`.

Credit: Swapnil Agrawal (BDS intern)
