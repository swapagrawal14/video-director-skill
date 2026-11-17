# Engine reference

## project.json
| key | meaning |
|---|---|
| `title`, `subtitle`, `kicker`, `credit` | title card text (credit also on end card + thumbnail) |
| `endTitle`, `endLine` | end card |
| `language` | TTS language code (`hi`, `en`, …) |
| `fps` (24), `width` (1280) | output; height = width·9/16 |
| `music_mood`, `music_gain` | see `scripts/music.py` |
| `theme` | `accent`, `accent2`, `highlight`, `background` [3 colours top→bottom], `bench`, `mat`, `mascot` |
| `thumbnail` | `pill`, `big`, `line1`, `line2`, `line3`, `shift`, `edge`, `dark` |
| `sfx` | `[{ "file": "sfx/boom.wav", "at": 12.3, "gain": 0.6 }]` (seconds on the final timeline) |
| `scenes[]` | one per scene, below |

### scene
| key | meaning |
|---|---|
| `vo` | text spoken (TTS). Empty → silent scene using `secs`. |
| `sub` | subtitle, chunks separated by `|`, timed proportionally across the VO |
| `secs` | length when there is no VO; `min_secs` floor; `lead` (0.5) silence before VO; `hold` (0.6) after |
| `type` | `"title"` or `"end"` to draw those cards |
| `step` | `[n, "Name", "PHASE"]` → step chip; total = highest n |
| `labels` | `[{ "at": [x,y,z], "text": "...", "start": s, "end": s, "dx": 60, "dy": -50, "color": "#hex" }]` (times in seconds into the scene) |
| `badge` | `{ "text": "15–30 s", "sub": "etch time", "start": 0.5, "secs": 6, "color": "#hex" }` ring fills over `secs` |
| `list` | `{ "title": "3 Golden Rules", "items": [...], "starts": [1.2, 3.6, …] }` |
| `mascot` | `"wave" | "hop" | "point" | "idle"`; `mascotPos` [x,y,z] |
| `shot` | `{ "from": [tx,ty,tz,dist,az,el], "to": [...] }` orbit camera, eased across the scene |

Labels anchored to moving parts: do it in code instead — in `renderAt`, after the 3D render, call `label3D(obj.localToWorld(V3(...)), 'Text', alpha)`.

## index.html API
- `window.renderAt(t)` draws frame for time t. `window.grab(t, q)` → JPEG data URL (with overlays). `window.grab3d(t)` → PNG of 3D only. `window.READY` true when loaded. `window.DURATION`.
- Helpers: `clamp lerp ease easeOut back V3 rnd M(color, opts) STEEL shadowAll`.
- Overlay kit: `label3D, badge, listCards, titleCard, endCard, stepChip, subtitles, card, rr, wrapLines`. All sizes scale with `K = W/1280`.
- `SCENE_FX[i](u, S, t)`: u = seconds into scene i, S = `{t,d,off,vo}`. Call `resetSubject()`-style resets at the top of every frame so scenes don't leak state.

## Coordinate conventions (template stage)
- Mat top at y ≈ -25, centre (0,0,0). Units ≈ millimetres-ish; hero object ~40–80 units wide.
- Camera `az` 0 = looking from +z; positive az orbits to the right. `el` radians above the horizon.

## Timing
`build_timing.py`: scene0 lead 2.8 s, others `lead` 0.5 s; duration = lead + VO + hold (+3 s tail on last). Change pacing by editing `hold` per scene, never by stretching VO.
