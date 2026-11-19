# Characters: `template/character3d.js`

Deterministic 3D toon characters built only from three.js primitives (spheres, capsules, boxes, tori). No SVG, no image sprites, no keyframe files. Every pose is computed from `t`, so a character renders frame-exact under `renderAt(t)` like the rest of the engine.

The motion system is ported from Swapnil Agrawal's Rigpop repos and rebuilt for 3D: the layered motion model and `EXPR` presets come from **rigpop-motion v2**, the visemes and keyword auto-gestures from **rigpop-agents**. Credit: Swapnil Agrawal (BDS intern).

Working example: `examples/character-demo/` (two characters, walk + sneak entrances, look-at, keyword gestures, expressions, 12 s).

## Layer stack

All layers are summed every frame on top of a reset bind pose, bottom to top:

| Layer | What it does |
|---|---|
| locomotion | `walk` / `sneak` / `run` between marks: stride cycle, hip bob, counter arm swing, chest lean (sneak crouches lower) |
| clips | one-shot moves (wave, point, jump...), each weighted by a back-eased envelope, so they anticipate and overshoot |
| idle | always on: breathing, weight-shift sway, head drift, blinks (~3 s), eye saccades, ponytail swing |
| speech | visemes `rest / M / A / E / O` from `mouth.json` or `words.json`, plus head bob while talking |
| face | `EXPR` preset per line, auto-blended toward a clip's expression (laugh, shock, cower to scared, think to thinking, wave/thumbs to happy, jump to excited) |

## API

```js
import { makeCharacter, animate, direct, speechFrom, reach, envelope, CLIPS, EXPR, AUTO_WORDS } from './character3d.js';
```

**`makeCharacter(opts)`** returns `{ root, rig, face, opts }`. Add `root` to the scene. 1 unit is about 1 m; height 1.0 is about 1.6 m.

| Option | Default | Notes |
|---|---|---|
| `skin`, `shirt`, `pants`, `hair`, `shoes`, `eyes` | warm toon palette | any CSS colour |
| `height` | `1.0` | uniform scale |
| `headScale` | `1.0` | bigger reads cuter |
| `hairStyle` | `'short'` | `'short' \| 'long' \| 'ponytail'` |
| `toon` | `false` | `true` uses `MeshToonMaterial` (flat cel look) |

Rig bones on `C.rig`: `hips, spine, chest, neck, head, shoulderL/R, elbowL/R, wristL/R, indexL/R, thumbL/R, hipL/R, kneeL/R, ankleL/R` (+ `tail` for ponytail).

**`animate(C, t, A)`** poses one character for time `t`. Call it every frame inside `renderAt`. `A`:

| Field | Meaning |
|---|---|
| `seed` | per-character idle variation (`direct` derives it from `id`) |
| `moves` | `[{ t0, t1, from:[x,z], to:[x,z], style }]` |
| `start`, `baseYaw` | standing position and facing (radians) |
| `clips` | `[{ t, d, do, side }]`, `side` is `'L'` or `'R'` (default `'R'`) |
| `expr` | `[{ t, name }]`, last one with `t <= now` wins |
| `look` | world point `{x,y,z}` for head and eyes, or `null` |
| `speech` | `(t) => ({ lv, shape })`, usually from `speechFrom` |

Returns `{ loc, expr }`.

**`direct(spec, words)`** turns a stage direction into `animate` args. `words` is `words.json` (`[{word, start, end}]`).

```js
const dA = direct({
  id: 'swapnil',                       // seeds idle variation
  marks: { door: [-2.5, .4], desk: [-.45, 0] },
  start: 'door',                       // mark name or [x, z]
  yaw: .5,                             // standing facing, radians
  speaks: [[.8, 5], [8.9, 9.7]],       // this character's talking windows (s)
  autoGestures: true,                  // default true when speaks is set
  acts: [
    { t: 0, do: 'walk', to: 'desk', d: 1.4 },  // walk | sneak | run; d defaults from distance
    { t: 5, do: 'think' },                      // any CLIPS name, optional d, side
    { at: 'namaste', do: 'wave' },              // fires on a spoken word
    { at: 'dekho', after: 6, lead: -.2, do: 'point', side: 'L' },
    { t: 0, expr: 'happy' }, { t: 6.3, expr: 'thinking' },
  ],
}, words);
```

- `at` matches the normalised word (case and punctuation stripped, Devanagari kept). `after` skips earlier occurrences, `lead` offsets from the word start (default `-0.15` s, so the move anticipates the word). An `at` act whose word is not found is dropped silently: check spelling against `words.json`.
- Auto-gestures scan words inside `speaks` windows for `AUTO_WORDS`. One fires per keyword, only if no other clip is within 1.5 s, then the next is blocked for 2.2 s.
- Walk speeds when `d` is omitted: walk 1.2 m/s, sneak 0.6, run 3.0 (minimum 0.8 s).
- Set `look` and `speech` on the returned object yourself (see snippet).
- Caveat: when standing, facing comes from `yaw` (`baseYaw`). A move's `face` value is currently overridden by it, so set `yaw` on the spec.

**`speechFrom(mouth, fps, windows, words)`** returns a `speech` function. Silent outside `windows`. Uses `mouth` frames when given, else falls back to syllable-rate visemes inside each word from `words`.

**`reach(C, side, target, k = 1)`** two-bone IK: aims arm `'L'`/`'R'` so the wrist reaches a world-space `THREE.Vector3`, blended by `k` (feed it an `envelope`). Call it after `animate`, which resets the pose.

**`envelope(u, d, rin = .25, rout = .3)`** 0 to 1 (back-eased, overshoots) to 0 over `d` seconds. Use it to weight your own moves.

**`CLIPS`** (default `d` in seconds):

| Clip | d | Clip | d | Clip | d |
|---|---|---|---|---|---|
| wave | 1.6 | shake | 1.3 | shrug | 1.3 |
| point | 1.3 | laugh | 1.3 | cower | 1.3 |
| thumbs | 1.3 | think | 1.3 | bow | 1.3 |
| nod | 1.3 | shock | 1.3 | sip | 1.3 |
| jump | 1.1 | | | | |

Add your own: `CLIPS.myMove = (C, c) => { C.rig.head.rotation.x += .2 * c.w; }` (`c = { u, d, w, t, side, args }`, always multiply by `c.w`).

**`EXPR`**: `neutral, happy, excited, laugh, smug, sneaky, shock, scared, sad, angry, thinking`.

**`AUTO_WORDS`** (English, Hinglish, Hindi):

| Gesture | Trigger words |
|---|---|
| wave | hello, hi, hey, bye, namaste, नमस्ते, welcome, bye-bye, alvida |
| point | tip, listen, look, this, here, remember, wait, first, dekho, देखो, yeh, ye, यह, suno, सुनो, pehle |
| thumbs | great, yes, awesome, perfect, okay, nice, done, badhiya, बढ़िया, haan, हाँ, sahi |
| shrug | why, what, how, guess, imagine, kya, क्या, kyun, क्यों, kaise, कैसे, pata |
| think | think, socho, सोचो, hmm, maybe, shayad, शायद |
| laugh | haha, hahaha, lol, funny, mazaa, मज़ा |
| shock | wow, whoa, arre, अरे, omg, what! |

Extend in place: `AUTO_WORDS.nod = ['haan ji', 'bilkul']` (add the clip name as the key).

## Minimal usage

```html
<script type="importmap">{"imports":{"three":"./node_modules/three/build/three.module.js"}}</script>
<script type="module">
import * as THREE from 'three';
import { makeCharacter, animate, direct, speechFrom } from './character3d.js';
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(innerWidth, innerHeight); renderer.shadowMap.enabled = true;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(32, innerWidth / innerHeight, .1, 50);
scene.add(new THREE.HemisphereLight('#fff6ea', '#c9a98a', 1.4));
const sun = new THREE.DirectionalLight('#fff1dc', 2.2); sun.position.set(2.5, 5, 3.5); sun.castShadow = true; scene.add(sun);

const words = await (await fetch('words.json')).json();
const mouth = await (await fetch('mouth.json')).json();          // optional
const C = makeCharacter({ shirt: '#e2475b', hairStyle: 'ponytail' });
scene.add(C.root);
const talk = [[0.5, 4.0]];
const d = direct({ id: 'host', start: [-2, 0], yaw: 0, speaks: talk,
  acts: [{ t: 0, do: 'walk', to: [0, 0], d: 1.2 }, { t: 0, expr: 'happy' }] }, words);
d.speech = speechFrom(mouth, 30, talk, words);
d.look = new THREE.Vector3(0, 1.4, 4);                            // at camera

window.DURATION = 6;
window.renderAt = (t) => {
  animate(C, t, d);
  cam.position.set(0, 1.35, 4); cam.lookAt(0, 1.0, 0);
  renderer.render(scene, cam);
};
window.renderAt(0); window.READY = true;
</script>
```

No `requestAnimationFrame`, `Date.now()` or `Math.random()` anywhere (render contract: `docs/CRAFT.md` §1).

## Lip-sync from audio

```bash
python3 scripts/mouth.py vo.wav --fps 30 -o mouth.json
```

Accepts wav or mp3 (decoded by ffmpeg); `--start` skips seconds at the head of the file. `mouth.json` is one entry per frame, `[{ "lv": 0..1, "shape": "rest|M|A|E|O" }, ...]`. Load it and pass `speechFrom(mouth, 30, windows)`, where `windows` are that character's talking spans so the other character stays closed-mouthed during shared VO. Use the same fps as the render. Without `mouth.json`, pass `words` instead: the syllable fallback is good for wide shots, `mouth.json` is better for close-ups.

## Craft tips

- Keep gestures 2+ s apart. Back-to-back clips read as twitching; one strong move per line is enough. Let auto-gestures handle filler, place key beats by hand with `at`.
- During dialogue, `look` at the other speaker's head (around y 1.4 to 1.5 at their mark). Prefer a fixed world point from their mark over reading `getWorldPosition()` each frame, which uses the previous frame's pose and breaks if chunks render out of order.
- Anticipation comes free from `envelope` (back-eased overshoot) and the default `-0.15` s word lead. For custom moves, weight by `envelope(t - t0, d)`; for a bigger wind-up, start the act 0.3 s early.
- Change `expr` slightly before the line that motivates it, not on it.
- Silent characters still breathe and blink. Never freeze a background character; give it a different `id` so idle sway does not mirror the lead.
- Horror: `sneak` in, `cower` on the scare, `scared` expression, low key light with heavy fog, slow camera push. Keep it adult and genuinely tense (scare structure: `docs/CRAFT.md` §6). Hold the `scared` face after the cower ends.
- Contact sheet check (`scripts/shot.py`): feet on the floor during walks, hands not through the body on `think`/`sip`, faces readable at final size.
