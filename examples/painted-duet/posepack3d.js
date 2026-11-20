// posepack3d.js: painted characters, the Rigpop Motion way, inside a three.js scene.
// Pose first, motion second: every gesture is a fully drawn pose (a pose pack), switched on a HARD CUT.
// Life on top of the pose: breath, sway, a settle after each cut, blinks, eye darts, lip-sync mouth patches.
// Raster art only (PNG pose packs from rigpop-motion `poses` / `faces`). No SVG, no puppet limbs.
//
// Pack layout (rigpop-motion format, copied as-is):  cast/<name>/<pose>/pack.json + key0.png, key0.blink.png,
//   key0.eyes.png, key0.pupils.png, key0.m.{rest,M,A,E,O}.png
import * as THREE from 'three';

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const hash = n => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const noise1 = x => { const i = Math.floor(x), f = x - i, s = f * f * (3 - 2 * f); return (hash(i) * (1 - s) + hash(i + 1) * s) * 2 - 1; };
const img = src => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('missing ' + src)); i.src = src; });

/** loadCast('cast/sharmaji', ['idle','talk','point']) → { name, packs:{pose:{keys:[...]}} } with every PNG decoded */
export async function loadCast(base, poses) {
  const packs = {};
  for (const p of poses) {
    const dir = `${base}/${p}/`, pk = await (await fetch(dir + 'pack.json')).json();
    for (const k of pk.keys) {
      k.img = await img(dir + k.file);
      const f = k.face || {};
      if (f.blink) f.blink.img = await img(dir + f.blink.file);
      if (f.eyes?.file) { f.eyes.img = await img(dir + f.eyes.file); if (f.eyes.pupil?.file) f.eyes.pupil.img = await img(dir + f.eyes.pupil.file); }
      if (f.mouth?.files) { f.mouth.imgs = {}; for (const [s, fn] of Object.entries(f.mouth.files)) f.mouth.imgs[s] = await img(dir + fn); }
    }
    pk.talks = pk.keys.every(k => k.face?.mouth?.imgs);     // a pose without mouth patches must not carry a spoken line
    packs[p] = pk;
  }
  return { name: base.split('/').pop(), packs };
}

/** makeActor(cast, { height }) → actor. height = world units from feet to head top of the home pose. */
export function makeActor(cast, o = {}) {
  const keys = Object.values(cast.packs).flatMap(p => p.keys);
  const left = Math.max(...keys.map(k => k.foot.x)), right = Math.max(...keys.map(k => k.w - k.foot.x));
  const up = Math.max(...keys.map(k => k.foot.y)), down = Math.max(...keys.map(k => k.h - k.foot.y));
  const cw = Math.ceil(2 * Math.max(left, right)) + 8, ch = Math.ceil(up + down) + 8;
  const canvas = document.createElement('canvas'); canvas.width = cw; canvas.height = ch;
  const ctx = canvas.getContext('2d');
  const tex = new THREE.CanvasTexture(canvas); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const home = cast.packs[o.home || Object.keys(cast.packs)[0]].keys[0];
  const ppu = home.foot.y / (o.height || 1.6);                       // drawing pixels per world unit
  const geo = new THREE.PlaneGeometry(cw / ppu, ch / ppu);
  const ox = cw / 2, oy = up + 4;                                     // foot point inside the canvas
  geo.translate(0, (oy - ch / 2) / ppu, 0);                           // pivot = feet
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, alphaTest: .02, color: o.tint || '#ffffff', depthWrite: true });
  const mesh = new THREE.Mesh(geo, mat);
  const group = new THREE.Group(); group.add(mesh);
  // contact shadow: a soft ellipse painted on a canvas (raster, not vector)
  const sc = document.createElement('canvas'); sc.width = 128; sc.height = 32; const sg = sc.getContext('2d');
  const gr = sg.createRadialGradient(64, 16, 2, 64, 16, 62); gr.addColorStop(0, 'rgba(40,20,10,.55)'); gr.addColorStop(1, 'rgba(40,20,10,0)');
  sg.fillStyle = gr; sg.fillRect(0, 0, 128, 32);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(home.w / ppu * 1.1, home.w / ppu * .22), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sc), transparent: true, depthWrite: false }));
  shadow.position.set(0, .005, -.02); group.add(shadow);
  return { cast, canvas, ctx, tex, mesh, group, ox, oy, ppu, last: null, o };
}

/**
 * Which drawing is on screen at t. dir = {
 *   acts: [{t, pose, key?}]                    pinned poses (hard cut at t)
 *   rotations: [{t0, t1, poses:['talk','point','talk'], hold:1.7}]   speaking rotation (Rigpop `[K poses talk point talk 60s &]`)
 * } → { pose, key, cutT }
 */
export function poseAt(A, t, dir) {
  let pose = dir.acts?.[0]?.pose || Object.keys(A.cast.packs)[0], key = 0, cutT = 0;
  for (const a of dir.acts || []) if (a.t <= t) { pose = a.pose; key = a.key || 0; cutT = a.t; }
  for (const r of dir.rotations || []) if (t >= r.t0 && t < r.t1) {
    const hold = r.hold || 1.7, n = Math.floor((t - r.t0) / hold);
    pose = r.poses[n % r.poses.length]; cutT = r.t0 + n * hold;
    const keysR = r.keys || [];                                                // optional key per turn, e.g. talk key0 then key1
    key = keysR.length ? keysR[n % keysR.length] : 0;
  }
  if (!A.cast.packs[pose]) pose = Object.keys(A.cast.packs)[0];
  return { pose, key: Math.min(key, A.cast.packs[pose].keys.length - 1), cutT };
}

/** drawActor(A, t, dir): dir adds { x, z, flip, seed, speech:(t)=>({lv,shape}), look:-1|0|1 } */
export function drawActor(A, t, dir) {
  const seed = dir.seed || 1, { pose, key, cutT } = poseAt(A, t, dir);
  const K = A.cast.packs[pose].keys[key], F = K.face || {}, g = A.ctx;
  const x0 = Math.round(A.ox - K.foot.x), y0 = Math.round(A.oy - K.foot.y);
  g.clearRect(0, 0, A.canvas.width, A.canvas.height);
  g.drawImage(K.img, x0, y0);
  // eyes: blink on a seeded schedule; slow, small eye darts (one shift every ~2.5 s, never jittery)
  const slot = Math.floor((t + seed * 1.7) / 3.3), bt = (t + seed * 1.7) - slot * 3.3 - hash(slot + seed) * 2.6;
  const blinking = F.blink && bt > 0 && bt < .12;
  if (blinking) g.drawImage(F.blink.img, x0 + F.blink.x, y0 + F.blink.y, F.blink.w, F.blink.h);
  else if (dir.darts && F.eyes?.img && F.eyes.pupil?.img && F.blink) {
    const ds = Math.floor(t / 2.5 + seed), dx = Math.round((hash(ds) - .5) * 2 + (dir.look || 0)), dy = 0;
    if (dx) { g.drawImage(F.eyes.img, x0 + F.blink.x, y0 + F.blink.y); g.drawImage(F.eyes.pupil.img, x0 + F.blink.x + dx, y0 + F.blink.y + dy); }
  }
  // mouth = the DRAWING'S OWN mouth (no pasted generic lips): on a key whose drawn mouth is open, the jaw
  // closes and opens by squashing that painted mouth from its upper lip, over the sampled skin.
  const sp = dir.speech ? dir.speech(t) : { lv: 0, open: 0 };
  const M = F.mouth;
  if (M && (dir.jaw || ['talk']).includes(pose)) {
    if (!K.skin) { const c = document.createElement('canvas'); c.width = K.w; c.height = K.h; const cg = c.getContext('2d'); cg.drawImage(K.img, 0, 0);
      const px = cg.getImageData(Math.round(M.x + M.w / 2), Math.min(K.h - 1, M.y + M.h + 4), 1, 1).data; K.skin = `rgb(${px[0]},${px[1]},${px[2]})`; }
    const open = sp.open || 0, sy = .18 + .92 * open, pad = 2;
    g.fillStyle = K.skin; g.beginPath(); g.ellipse(x0 + M.x + M.w / 2, y0 + M.y + M.h / 2, M.w / 2 + pad, M.h / 2 + pad, 0, 0, Math.PI * 2); g.fill();
    g.drawImage(K.img, M.x - pad, M.y - pad, M.w + pad * 2, M.h + pad * 2, x0 + M.x - pad, y0 + M.y - pad, M.w + pad * 2, (M.h + pad * 2) * sy);
  }
  A.tex.needsUpdate = true;
  // secondary motion: tiny offsets only. One soft ease after a cut (no wobble), breath, slow sway.
  const k = t - cutT, settle = k < .5 ? Math.exp(-k * 7) * (1 - Math.min(1, k * 2)) : 0;
  const br = Math.sin(t * Math.PI * 2 * .22 + seed);
  A.mesh.scale.set((dir.flip ? -1 : 1) * (1 + br * .003), 1 + br * .006 + settle * .015, 1);
  A.mesh.rotation.z = noise1(t * .25 + seed * 3) * .006;
  A.mesh.position.y = 0;
  A.group.position.set(dir.x || 0, 0, dir.z || 0);
  return { pose, key, blinking };
}

/** speech track from timeline.json mouth frames for one speaker */
// smoothed: jaw open = mean level over ~5 frames with fast attack / slower release, so lips never flicker
export function speechTrack(frames, fps) {
  const n = frames.length, open = new Float32Array(n); let v = 0;
  for (let i = 0; i < n; i++) { let a = 0; for (let j = -2; j <= 2; j++) a += (frames[Math.max(0, Math.min(n - 1, i + j))]?.lv || 0); a = clamp(a / 5 * 1.7);
    v = a > v ? v + (a - v) * .7 : v + (a - v) * .35; open[i] = v; }
  return t => { const i = Math.max(0, Math.min(n - 1, Math.round(t * fps))); return { lv: open[i] > .04 ? open[i] : 0, open: open[i] }; };
}

/** paintedSet(texture, camera, depth): a painted backdrop plane that fills the frame at its depth (+margin for camera moves) */
export function paintedSet(tex, cam, z, cy, margin = 1.12) {
  tex.colorSpace = THREE.SRGBColorSpace;
  const D = cam.position.z - z, h = 2 * D * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)) * margin;
  const ar = tex.image.width / tex.image.height, w = Math.max(h * ar, h * cam.aspect * margin);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, w / ar), new THREE.MeshBasicMaterial({ map: tex, depthWrite: false }));
  m.position.set(0, cy, z); return m;
}
