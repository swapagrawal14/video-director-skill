// headrig3d.js: painted cutout characters with ONE shared head per character, inside a three.js scene.
// Why: when every pose drawing carries its own face, each cut changes the expression at random. Here the
// body poses are headless paintings; a single painted head rides on the neck of every pose, so the face is
// continuous and every expression change is DIRECTED (brows, eyes, mouth sprites painted on that head).
// Raster only (PNG). No SVG, no primitive shapes, no puppet limbs.
//
// cast/<name>/rig.json: { head:{file,w,h,neck:[x,y],sprites:{'mouth.rest':{file,x,y},'mouth.A'..,'mouth.laugh',
//   'eyes.closed','brows.angry','brows.up'}}, bodies:{pose:{file,w,h,neck:[x,y],foot:[x,y]}}, head_scale }
import * as THREE from 'three';

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const hash = n => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const noise1 = x => { const i = Math.floor(x), f = x - i, s = f * f * (3 - 2 * f); return (hash(i) * (1 - s) + hash(i + 1) * s) * 2 - 1; };
const ease = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const img = src => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('missing ' + src)); i.src = src; });

export async function loadRig(base) {
  const R = await (await fetch(base + '/rig.json')).json();
  R.head.img = await img(`${base}/${R.head.file}`);
  for (const s of Object.values(R.head.sprites || {})) s.img = await img(`${base}/${s.file}`);
  for (const b of Object.values(R.bodies)) b.img = await img(`${base}/${b.file}`);
  R.name = base.split('/').pop(); return R;
}

/** makeRigActor(rig, { height, tint }) → actor; height = world units feet→head top in the idle pose */
export function makeRigActor(rig, o = {}) {
  const hs = rig.head_scale || 1, H = rig.head, B = Object.values(rig.bodies);
  const headUp = H.neck[1] * hs, headSide = Math.max(H.neck[0], H.w - H.neck[0]) * hs;
  const left = Math.max(...B.map(b => Math.max(b.foot[0], b.neck[0] + headSide))), right = Math.max(...B.map(b => Math.max(b.w - b.foot[0], b.w - b.neck[0] + headSide)));
  const up = Math.max(...B.map(b => b.foot[1] - b.neck[1] + headUp)) + 24;
  const cw = Math.ceil(2 * Math.max(left, right)) + 16, ch = Math.ceil(up) + 8;
  const canvas = document.createElement('canvas'); canvas.width = cw; canvas.height = ch;
  const ctx = canvas.getContext('2d');
  const tex = new THREE.CanvasTexture(canvas); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const idle = rig.bodies.idle || B[0], fullH = idle.foot[1] - idle.neck[1] + headUp;
  const ppu = fullH / (o.height || 1.6), ox = cw / 2, oy = up;
  const geo = new THREE.PlaneGeometry(cw / ppu, ch / ppu); geo.translate(0, (oy - ch / 2) / ppu, 0);   // pivot = feet
  const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: tex, transparent: true, alphaTest: .02, color: o.tint || '#ffffff' }));
  const group = new THREE.Group(); group.add(mesh);
  const sc = document.createElement('canvas'); sc.width = 128; sc.height = 32; const sg = sc.getContext('2d');
  const gr = sg.createRadialGradient(64, 16, 2, 64, 16, 62); gr.addColorStop(0, 'rgba(40,20,10,.5)'); gr.addColorStop(1, 'rgba(40,20,10,0)');
  sg.fillStyle = gr; sg.fillRect(0, 0, 128, 32);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(idle.w / ppu * 1.15, idle.w / ppu * .22), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sc), transparent: true, depthWrite: false }));
  shadow.position.set(0, .005, -.02); group.add(shadow);
  return { rig, canvas, ctx, tex, mesh, group, ox, oy, ppu, hs };
}

// the value of a step track [{t, v}] at t (holds the last value)
const at = (track, t, d) => { let v = d; for (const k of track || []) if (k.t <= t) v = k.v ?? k.pose ?? k.expr; return v; };
const lastT = (track, t) => { let c = -9; for (const k of track || []) if (k.t <= t) c = k.t; return c; };

/** speech track: per-frame mouth.py output → smoothed open level + a viseme held >= 3 frames (no flicker) */
export function speechTrack(frames, fps) {
  const n = frames.length, open = new Float32Array(n), shape = new Array(n); let v = 0, cur = 'rest', held = 0;
  for (let i = 0; i < n; i++) {
    let a = 0; for (let j = -2; j <= 2; j++) a += (frames[Math.max(0, Math.min(n - 1, i + j))]?.lv || 0);
    a = clamp(a / 5 * 1.7); v = a > v ? v + (a - v) * .7 : v + (a - v) * .35; open[i] = v;
    let want = v < .08 ? (cur === 'rest' || cur === 'M' ? 'rest' : 'M') : (frames[i]?.shape && frames[i].shape !== 'rest' ? frames[i].shape : (v > .55 ? 'A' : 'E'));
    if (want !== cur && held >= 3) { cur = want; held = 0; } else held++;
    shape[i] = cur;
  }
  return t => { const i = Math.max(0, Math.min(n - 1, Math.round(t * fps))); return { lv: open[i], shape: shape[i] }; };
}

/**
 * drawRigActor(A, t, dir)
 * dir = { x, z, flip, seed, speech,
 *   body:  [{t, v:'idle'}, {t:4.4, v:'point'}]        hard-cut body poses (the head stays continuous)
 *   brows: [{t, v:null|'angry'|'up'}]                  directed expression changes, held until the next key
 *   mouth: [{t, v:null|'laugh'}]                       a pinned mouth (laugh) overrides lip-sync while set
 *   eyes:  [{t, v:null|'closed'}]                      eyes held shut (laughing, savouring)
 *   tilt:  [{t, v:-0.05}]                              head tilt in radians, eased between keys
 *   nod:   0.04                                        speech-driven nod amplitude (radians)
 * }
 */
export function drawRigActor(A, t, dir) {
  const R = A.rig, H = R.head, S = H.sprites || {}, g = A.ctx, seed = dir.seed || 1;
  const pose = at(dir.body, t, 'idle'), Bd = R.bodies[pose] || R.bodies.idle, cutT = lastT(dir.body, t);
  const sp = dir.speech ? dir.speech(t) : { lv: 0, shape: 'rest' };
  g.clearRect(0, 0, A.canvas.width, A.canvas.height);
  // body: breath lifts the chest a hair; one soft ease on a new pose (no wobble)
  const br = Math.sin(t * Math.PI * 2 * .22 + seed), k = t - cutT, settle = k >= 0 && k < .35 ? (1 - ease(k / .35)) : 0;
  const bx = Math.round(A.ox - Bd.foot[0]), by = Math.round(A.oy - Bd.foot[1]);
  const bs = 1 + br * .006 + settle * .012;                               // vertical breath scale anchored at the feet
  // neck point after breath
  const nx = bx + Bd.neck[0], ny = A.oy - (A.oy - (by + Bd.neck[1])) * bs;
  // head: eased directed tilt + small speech nods + slow idle drift
  let tilt = 0; const tk = dir.tilt || [];
  for (let i = 0; i < tk.length; i++) if (tk[i].t <= t) { const nx2 = tk[i + 1]; tilt = tk[i].v; if (nx2 && t < nx2.t && nx2.t - t < .4) tilt += (nx2.v - tk[i].v) * ease(1 - (nx2.t - t) / .4); }
  const nod = (dir.nod ?? .035) * sp.lv * Math.sin(t * 7.5 + seed) * .6 + noise1(t * .3 + seed * 5) * .012;
  g.save(); g.translate(nx, ny); g.rotate(tilt + nod); g.scale(A.hs, A.hs); g.translate(-H.neck[0], -H.neck[1]);
  g.drawImage(H.img, 0, 0);
  const put = name => { const s = S[name]; if (s) g.drawImage(s.img, s.x, s.y); };
  // eyes: directed hold, else a seeded natural blink (~every 3.5 s, 0.12 s)
  const slot = Math.floor((t + seed * 1.7) / 3.5), bt = (t + seed * 1.7) - slot * 3.5 - hash(slot + seed) * 2.8;
  if (at(dir.eyes, t, null) === 'closed' || (bt > 0 && bt < .12)) put('eyes.closed');
  const bw = at(dir.brows, t, null); if (bw) put('brows.' + bw);
  const pm = at(dir.mouth, t, null);
  put('mouth.' + (pm || (S['mouth.' + sp.shape] ? sp.shape : 'rest')));
  g.restore();
  // body last: the collar covers the head's neck stub, and a hand at the chin stays in front of the face
  g.save(); g.translate(A.ox, A.oy); g.scale(1, bs); g.translate(-A.ox, -A.oy); g.drawImage(Bd.img, bx, by); g.restore();
  A.tex.needsUpdate = true;
  A.mesh.scale.x = dir.flip ? -1 : 1;
  A.mesh.rotation.z = noise1(t * .25 + seed * 3) * .004;
  A.group.position.set(dir.x || 0, 0, dir.z || 0);
  return { pose };
}

export { paintedSet } from './posepack3d.js';
