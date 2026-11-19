# Characters: painted pose packs (the Rigpop Motion way)

`template/posepack3d.js` puts painted characters into the three.js engine using the pose-to-pose method from
[rigpop-motion](https://github.com/swapagrawal14/rigpop-motion) by Swapnil Agrawal (BDS intern).

**Pose first, motion second.** Every gesture is a fully drawn pose. Motion is the life laid on top of the
current drawing, never limbs swung by code.

## Hard rules

- **No SVG, ever.** No vector characters, no primitive-shape dolls (spheres and capsules), no puppet limbs.
  Characters are raster pose packs (PNG). `lint.py` fails any project that contains SVG.
- **Every beat names a drawn pose.** If the script needs a gesture that has no pack, generate the pose pack
  before rendering (`rigpop-motion poses <character>`). Never fake it with transforms.
- **Change drawings on a hard cut.** Never cross-dissolve two poses: you get ghosting and a double character.
  The settle after the cut, plus breath, blink and mouth, sells the change.
- **A speaking pose must have mouth patches** (`key*.m.{rest,M,A,E,O}.png`). A pack without them renders a
  dead mouth. `loadCast` marks such packs `talks:false`: use them only while that character is silent
  (think, listen).
- **New idea, new cast.** A new video gets its own characters and packs. Reuse the engine, sets and mouth
  shapes, not another reel's performance. Continuing a series is the one exception, and the script must say so.
- **Same character everywhere.** Use one style bible plus the model sheet in every pose prompt, and regenerate
  any pose that drifts.

## Asset layout (rigpop-motion format, copied as-is)

```
cast/<name>/<pose>/pack.json   key0.png  key0.blink.png  key0.eyes.png  key0.pupils.png  key0.m.{rest,M,A,E,O}.png
set-<place>.png                AI-painted backdrop in the same style as the cast (no people, no text)
```

Build packs with rigpop-motion (`poses`, then `faces`), then copy `characters/<name>/poses/<pose>/` into
`cast/<name>/<pose>/`. Face rects must sit exactly on the drawn eyes and mouth. Check them with the
rigpop-motion tools `face-rects.mjs` and `face-paste-preview.mjs`.

## API

```js
import { loadCast, makeActor, drawActor, speechTrack, paintedSet } from './posepack3d.js';
const set = paintedSet(await new THREE.TextureLoader().loadAsync('set-aangan.png'), cam, -3.2, 1.25, 1.2);
const SH = makeActor(await loadCast('cast/sharmaji', ['idle','talk','point','listen','laugh']), { height: 1.62, home: 'idle', tint: '#fff4e6' });
scene.add(set, SH.group);
const dir = {
  x: -.4, z: 0, seed: 3, flip: false, look: 1,               // look: eye darts lean toward the other speaker
  speech: speechTrack(TL.mouth.sharmaji, TL.fps),            // per-frame {lv, shape} from scripts/mouth.py
  acts: [{ t: 0, pose: 'idle' }, { t: 4.4, pose: 'listen' }, { t: 14.6, pose: 'laugh' }],      // pinned poses, hard cuts
  rotations: [{ t0: .6, t1: 4.4, poses: ['talk', 'point', 'talk'], hold: 1.25 }],              // speaking rotation
};
window.renderAt = t => { drawActor(SH, t, dir); renderer.render(scene, cam); };
```

- `makeActor` makes a camera-facing painted card with its pivot at the feet, plus a soft contact shadow.
  `height` is in world units from the feet to the top of the home pose. `tint` multiplies the art to match
  the scene light (warm for golden hour, blue-grey for night).
- `poseAt` and `drawActor` pick the drawing at `t`. A pinned `acts` entry holds until the next one. A
  `rotations` window cycles its poses every `hold` seconds (Rigpop `[K poses talk point talk 60s &]`). A
  multi-key pack (such as `talk` with three keys) cycles inside its own turn.
- The face layer is drawn onto the card every frame:
  - Blink: a seeded schedule, about one every 3.3 s, lasting 0.12 s.
  - Eye darts: the pupil sprite moves 1 to 2 px over flat sclera.
  - Mouth: the viseme patch pasted exactly over the drawn mouth.
- Secondary motion (offsets only): breathing scale, a slow sway, a talk bob, and an overshoot-and-settle
  squash after every cut.
- `flip: true` mirrors a character so that two speakers face each other.

## Lip-sync

```bash
python3 scripts/mouth.py vo/line0.mp3 --fps 30 -o /tmp/m0.json      # [{lv, shape}] per frame, shapes rest/M/A/E/O
```

Place each line's frames at that line's start in a per-speaker track (`timeline.json` → `mouth.<name>`). The
speaker who is silent gets `rest`. `examples/painted-duet/` shows the whole build: per-line edge-tts, a
timeline, captions, and a mix at -14 LUFS.

## Directing tips

- One pose per beat. On a line longer than about 3 s, rotate talk → gesture → talk. Do not put a resting
  pose (hands on hips, arms folded) in the middle of a sentence.
- The listener holds a `listen` or `think` pose, and their eye darts lean toward the speaker.
- Camera last: a slow push on the two-shot, a hard cut to a medium on the punchline, and a cut back wide for
  the reaction. The backdrop drifts at about 0.35 of the camera's x, which gives a little parallax.
- Framing for a full-body drawing in 9:16: feet about 15 to 20% up from the bottom of the frame, heads below
  the top third, and caption safe zone kept clear.
- Horror: make the set blue-grey with a cold tint, and use few poses with long holds. A single hard cut to a
  new drawing in near-darkness is scarier than any movement.
