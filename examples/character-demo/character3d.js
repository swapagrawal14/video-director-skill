// character3d.js: deterministic 3D toon characters with an always-alive motion system.
// Pure three.js primitives. No SVG, no image sprites, no keyframe files.
// Motion design ported from Rigpop (rigpop-motion v2 layers + rigpop-agents auto-gestures/visemes),
// rebuilt for 3D by Swapnil Agrawal's Video Director Skill.
//
// Layers, bottom to top (all summed every frame from t, so renders are frame-exact):
//   locomotion  walk / sneak / run between marks: stride cycle, hip bob, counter arm swing
//   clips       wave, point, nod, shake, laugh, jump, shock, shrug, think, thumbs, bow, cower, sip
//               each weighted by a back-eased envelope, so moves anticipate and overshoot
//   idle        breathing, weight-shift sway, head drift, blinks, eye saccades (always on)
//   speech      visemes (rest/A/E/O/M) from mouth.json or words.json, head bob + brow lift on stress
//   face        expression presets (EXPR) blended per clip or per line
import * as THREE from 'three';

/* ---------------- utils ---------------- */
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, k) => a + (b - a) * k;
const hash = n => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const smooth = x => { x = clamp(x); return x * x * (3 - 2 * x); };
const backOut = x => { x = clamp(x); const c = 1.70158; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2; };
const noise1 = x => { const i = Math.floor(x), f = x - i; return lerp(hash(i), hash(i + 1), smooth(f)) * 2 - 1; };
const fbm = (x, s = 0) => noise1(x + s * 17.3) * .6 + noise1(x * 2.1 + s * 5.1) * .3 + noise1(x * 4.3 + s * 2.7) * .1;
/** envelope: 0 → 1 (back-eased, overshoots) → 0 over a clip of length d; ramp in/out seconds */
export function envelope(u, d, rin = .25, rout = .3) { if (u < 0 || u > d) return 0; return Math.min(backOut(u / rin), smooth((d - u) / rout)); }

/* ---------------- expressions (from rigpop-motion EXPR) ---------------- */
export const EXPR = {
  neutral: { brow: 0, browTilt: 0, lid: .12, pupil: 1, wide: 0, mouth: 'rest', blush: .3 },
  happy:   { brow: .35, browTilt: -.1, lid: .08, pupil: 1.05, wide: 0, mouth: 'smile', blush: .6 },
  excited: { brow: .7, browTilt: -.15, lid: 0, pupil: 1.15, wide: .4, mouth: 'grin', blush: .7 },
  laugh:   { brow: .6, browTilt: -.2, lid: .85, pupil: 1, wide: 0, mouth: 'laugh', blush: .9 },
  smug:    { brow: .1, browTilt: .25, lid: .38, pupil: 1, wide: 0, mouth: 'smirk', blush: .4 },
  sneaky:  { brow: -.15, browTilt: .45, lid: .42, pupil: .95, wide: 0, mouth: 'smirk', blush: .3 },
  shock:   { brow: 1.1, browTilt: -.35, lid: -.1, pupil: .5, wide: 1, mouth: 'shock', blush: .1 },
  scared:  { brow: .8, browTilt: -.6, lid: 0, pupil: .55, wide: .6, mouth: 'wobble', blush: .1 },
  sad:     { brow: .25, browTilt: -.7, lid: .38, pupil: 1.1, wide: 0, mouth: 'frown', blush: .2 },
  angry:   { brow: -.2, browTilt: .8, lid: .25, pupil: .9, wide: 0, mouth: 'frown', blush: .2 },
  thinking:{ brow: .3, browTilt: .3, lid: .3, pupil: 1, wide: 0, mouth: 'smirk', blush: .3 },
};
const NUM = ['brow', 'browTilt', 'lid', 'pupil', 'wide', 'blush'];
function blendExpr(a, b, k) { const o = { ...(k > .5 ? b : a) }; for (const n of NUM) o[n] = lerp(a[n], b[n], k); return o; }

/* ---------------- auto gestures (from rigpop-agents AUTO_WORDS, + Hindi/Hinglish) ---------------- */
export const AUTO_WORDS = {
  wave: ['hello', 'hi', 'hey', 'bye', 'namaste', 'welcome', 'नमस्ते', 'bye-bye', 'alvida'],
  point: ['tip', 'listen', 'look', 'this', 'here', 'remember', 'wait', 'first', 'dekho', 'yeh', 'ye', 'suno', 'देखो', 'यह', 'सुनो', 'pehle'],
  thumbs: ['great', 'yes', 'awesome', 'perfect', 'okay', 'nice', 'done', 'badhiya', 'बढ़िया', 'haan', 'हाँ', 'sahi'],
  shrug: ['why', 'what', 'how', 'guess', 'imagine', 'kya', 'kyun', 'kaise', 'क्या', 'क्यों', 'कैसे', 'pata'],
  think: ['think', 'socho', 'सोचो', 'hmm', 'maybe', 'shayad', 'शायद'],
  laugh: ['haha', 'hahaha', 'lol', 'funny', 'mazaa', 'मज़ा'],
  shock: ['wow', 'whoa', 'arre', 'अरे', 'omg', 'what!'],
};

/* ---------------- the rig ---------------- */
const DEF = { skin: '#f2c3a0', shirt: '#e2475b', pants: '#2c3e64', hair: '#2a1a12', shoes: '#1d1d22', eyes: '#2a1a0e', height: 1.0, headScale: 1.0, hairStyle: 'short', toon: false };

/** makeCharacter(opts) → { root, rig, face, opts }. 1 unit ≈ 1 m at height 1.0 (character ≈ 1.6 m). */
export function makeCharacter(o = {}) {
  o = { ...DEF, ...o };
  const M = c => o.toon ? new THREE.MeshToonMaterial({ color: c }) : new THREE.MeshStandardMaterial({ color: c, roughness: .6 });
  const skin = M(o.skin), shirt = M(o.shirt), pants = M(o.pants), hair = M(o.hair), shoe = M(o.shoes);
  const G = (parent, x = 0, y = 0, z = 0) => { const g = new THREE.Group(); g.position.set(x, y, z); parent.add(g); return g; };
  const cap = (r, len, mat, parent, down = true) => { const m = new THREE.Mesh(new THREE.CapsuleGeometry(r, len, 6, 14), mat); m.position.y = down ? -len / 2 : len / 2; m.castShadow = true; parent.add(m); return m; };
  const root = new THREE.Group(); root.scale.setScalar(o.height);
  const R = {}; R.root = root;
  R.hips = G(root, 0, .86, 0);
  const pelvis = new THREE.Mesh(new THREE.SphereGeometry(.15, 20, 14), pants); pelvis.scale.set(1.15, .7, .8); R.hips.add(pelvis);
  R.spine = G(R.hips, 0, .05, 0);
  R.chest = G(R.spine, 0, .2, 0);
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(.15, .22, 6, 18), shirt); torso.scale.set(1.15, 1, .8); torso.position.y = .02; torso.castShadow = true; R.chest.add(torso);
  R.neck = G(R.chest, 0, .25, 0); cap(.045, .06, skin, R.neck, false);
  R.head = G(R.neck, 0, .1, 0);
  const hs = o.headScale;
  const skull = new THREE.Mesh(new THREE.SphereGeometry(.13 * hs, 32, 24), skin); skull.scale.set(1, 1.08, .98); skull.position.y = .12 * hs; skull.castShadow = true; R.head.add(skull);
  // hair (all primitives)
  const hairCap = new THREE.Mesh(new THREE.SphereGeometry(.137 * hs, 32, 18, 0, Math.PI * 2, 0, Math.PI * .52), hair); hairCap.position.y = .135 * hs; hairCap.rotation.x = -.18; R.head.add(hairCap);
  if (o.hairStyle === 'long' || o.hairStyle === 'ponytail') {
    const back = new THREE.Mesh(new THREE.CapsuleGeometry(.11 * hs, o.hairStyle === 'long' ? .22 : .05, 6, 14), hair); back.scale.set(1.15, 1, .6); back.position.set(0, (o.hairStyle === 'long' ? .02 : .1) * hs, -.06 * hs); R.head.add(back);
    if (o.hairStyle === 'ponytail') { R.tail = G(R.head, 0, .2 * hs, -.13 * hs); cap(.035, .16, hair, R.tail); }
  }
  for (const sx of [-1, 1]) { const ear = new THREE.Mesh(new THREE.SphereGeometry(.028 * hs, 12, 10), skin); ear.scale.set(.5, 1, .8); ear.position.set(sx * .128 * hs, .12 * hs, 0); R.head.add(ear); }
  const nose = new THREE.Mesh(new THREE.SphereGeometry(.018 * hs, 12, 10), skin); nose.position.set(0, .1 * hs, .128 * hs); R.head.add(nose);
  // face
  const F = { eyes: [], pupils: [], lids: [], brows: [], cheeks: [] };
  const white = new THREE.MeshStandardMaterial({ color: '#fbfbf8', roughness: .3 });
  const iris = new THREE.MeshStandardMaterial({ color: o.eyes, roughness: .2 });
  const dark = new THREE.MeshBasicMaterial({ color: '#3a1414' });
  const blushM = new THREE.MeshBasicMaterial({ color: '#ff7a8a', transparent: true, opacity: .3, depthWrite: false });
  for (const sx of [-1, 1]) {
    const eg = G(R.head, sx * .048 * hs, .14 * hs, .112 * hs);
    const ball = new THREE.Mesh(new THREE.SphereGeometry(.026 * hs, 20, 14), white); ball.scale.z = .6; eg.add(ball);
    const pup = new THREE.Mesh(new THREE.SphereGeometry(.013 * hs, 14, 10), iris); pup.position.z = .014 * hs; eg.add(pup);
    const lid = new THREE.Mesh(new THREE.SphereGeometry(.028 * hs, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2), skin); lid.position.z = .002; eg.add(lid);
    const brow = new THREE.Mesh(new THREE.BoxGeometry(.04 * hs, .008 * hs, .01 * hs), hair); brow.position.set(sx * .048 * hs, .185 * hs, .118 * hs); R.head.add(brow);
    const ck = new THREE.Mesh(new THREE.CircleGeometry(.02 * hs, 16), blushM); ck.position.set(sx * .075 * hs, .085 * hs, .118 * hs); R.head.add(ck);
    F.eyes.push(eg); F.pupils.push(pup); F.lids.push(lid); F.brows.push(brow); F.cheeks.push(ck);
  }
  F.mouth = G(R.head, 0, .058 * hs, .124 * hs);
  F.mouthHole = new THREE.Mesh(new THREE.SphereGeometry(.02 * hs, 18, 12), dark); F.mouthHole.scale.set(1.4, .3, .4); F.mouth.add(F.mouthHole);
  F.smile = new THREE.Mesh(new THREE.TorusGeometry(.024 * hs, .004 * hs, 6, 18, Math.PI), dark); F.smile.rotation.z = Math.PI; F.mouth.add(F.smile);
  F.teeth = new THREE.Mesh(new THREE.BoxGeometry(.03 * hs, .006 * hs, .005 * hs), white); F.teeth.position.set(0, .008 * hs, .006 * hs); F.mouth.add(F.teeth);
  // arms: shoulder → elbow → wrist → hand (+ index finger and thumb for point/thumbs)
  for (const [side, sx] of [['L', 1], ['R', -1]]) {
    const sh = G(R.chest, sx * .2, .19, 0); cap(.048, .22, shirt, sh);
    const el = G(sh, 0, -.27, 0); cap(.04, .2, skin, el);
    const wr = G(el, 0, -.25, 0);
    const palm = new THREE.Mesh(new THREE.SphereGeometry(.045, 16, 12), skin); palm.scale.set(.8, 1, .55); palm.position.y = -.04; wr.add(palm);
    const idx = G(wr, sx * .012, -.07, .015); cap(.011, .04, skin, idx);
    const th = G(wr, -sx * .03, -.035, .02); cap(.012, .03, skin, th); th.rotation.z = -sx * .7;
    R['shoulder' + side] = sh; R['elbow' + side] = el; R['wrist' + side] = wr; R['index' + side] = idx; R['thumb' + side] = th;
  }
  for (const [side, sx] of [['L', 1], ['R', -1]]) {
    const hp = G(R.hips, sx * .085, -.04, 0); cap(.065, .32, pants, hp);
    const kn = G(hp, 0, -.4, 0); cap(.055, .32, pants, kn);
    const an = G(kn, 0, -.4, 0);
    const foot = new THREE.Mesh(new THREE.CapsuleGeometry(.05, .1, 4, 10), shoe); foot.rotation.x = Math.PI / 2; foot.position.set(0, -.03, .05); foot.scale.set(1, 1, .7); an.add(foot);
    R['hip' + side] = hp; R['knee' + side] = kn; R['ankle' + side] = an;
  }
  root.traverse(m => { if (m.isMesh) { m.castShadow = true; } });
  return { root, rig: R, face: F, opts: o };
}

/* ---------------- two-bone IK (arm reaches a world point) ---------------- */
const _v = new THREE.Vector3(), _w = new THREE.Vector3();
/** Aim arm `side` so the wrist reaches `target` (world). Upper 0.27, fore 0.25 (scaled by character height). */
export function reach(C, side, target, k = 1) {
  if (k <= 0) return; const R = C.rig, sh = R['shoulder' + side], el = R['elbow' + side];
  sh.parent.updateMatrixWorld(true);
  const local = sh.parent.worldToLocal(_v.copy(target)).sub(sh.position);   // in chest space
  const a = .27, b = .25, d = clamp(local.length() / C.root.scale.x, .05, a + b - .001);
  const elbowBend = Math.PI - Math.acos(clamp((a * a + b * b - d * d) / (2 * a * b), -1, 1));
  const toT = Math.acos(clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1));
  // point the bone's -Y axis at the target, then lift by toT inside the arm plane
  const dir = _w.copy(local).normalize();
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, -1, 0), dir);
  const lift = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -toT);
  q.multiply(lift); sh.quaternion.slerp(q, k); el.rotation.x = lerp(el.rotation.x, -elbowBend, k);
}

/* ---------------- clips ---------------- */
// clip(c) adds rotations onto the rig, weighted by c.w (the envelope). c = { u, d, w, t, side, args }
const S = (side) => side === 'L' ? 1 : -1;
export const CLIPS = {
  wave(C, c) { const R = C.rig, s = c.side || 'R', sx = S(s), w = c.w;
    R['shoulder' + s].rotation.z += sx * 2.55 * w; R['shoulder' + s].rotation.x += -.25 * w;
    R['elbow' + s].rotation.z += sx * (.55 + Math.sin(c.u * 11) * .45) * w; R.head.rotation.z += -sx * .08 * w; },
  point(C, c) { const R = C.rig, s = c.side || 'R', sx = S(s), w = c.w;
    R['shoulder' + s].rotation.x += -1.45 * w; R['shoulder' + s].rotation.z += sx * .25 * w; R['elbow' + s].rotation.x += -.1 * w;
    R['index' + s].rotation.x += -.2 * w; R.chest.rotation.y += -sx * .18 * w; R.head.rotation.y += -sx * .12 * w; },
  thumbs(C, c) { const R = C.rig, s = c.side || 'R', sx = S(s), w = c.w;
    R['shoulder' + s].rotation.x += -.7 * w; R['shoulder' + s].rotation.z += sx * .3 * w; R['elbow' + s].rotation.x += -1.5 * w;
    R['thumb' + s].rotation.z += sx * 1.4 * w; R.head.rotation.x += -.06 * w; },
  nod(C, c) { C.rig.head.rotation.x += Math.sin(c.u * 9) * .16 * c.w; },
  shake(C, c) { C.rig.head.rotation.y += Math.sin(c.u * 10) * .25 * c.w; },
  laugh(C, c) { const R = C.rig, w = c.w, b = Math.abs(Math.sin(c.u * 14));
    R.chest.rotation.x += (.12 + b * .06) * w; R.head.rotation.x += (-.25 + b * .1) * w; R.hips.position.y += b * .012 * w;
    for (const s of ['L', 'R']) { R['shoulder' + s].rotation.z += S(s) * .25 * w; R['elbow' + s].rotation.x += -.9 * w; } },
  shrug(C, c) { const R = C.rig, w = c.w;
    for (const s of ['L', 'R']) { R['shoulder' + s].position.y += .03 * w; R['shoulder' + s].rotation.z += S(s) * .35 * w; R['elbow' + s].rotation.x += -1.4 * w; R['elbow' + s].rotation.z += -S(s) * .6 * w; }
    R.head.rotation.z += .14 * w; },
  think(C, c) { const R = C.rig, w = c.w; // hand to chin
    R.shoulderR.rotation.x += -.55 * w; R.shoulderR.rotation.z += -.25 * w; R.elbowR.rotation.x += -2.35 * w; R.elbowR.rotation.z += .2 * w;
    R.head.rotation.z += .1 * w; R.head.rotation.x += -.08 * w; R.chest.rotation.y += .1 * w; },
  shock(C, c) { const R = C.rig, w = c.w;
    R.chest.rotation.x += -.18 * w; R.head.rotation.x += -.12 * w;
    for (const s of ['L', 'R']) { R['shoulder' + s].rotation.z += S(s) * 1.0 * w; R['shoulder' + s].rotation.x += -.5 * w; R['elbow' + s].rotation.x += -1.0 * w; } },
  cower(C, c) { const R = C.rig, w = c.w, tr = Math.sin(c.u * 40) * .015;
    R.hips.position.y += -.12 * w; R.chest.rotation.x += .35 * w; R.head.rotation.x += .2 * w + tr;
    for (const s of ['L', 'R']) { R['shoulder' + s].rotation.x += -1.9 * w; R['shoulder' + s].rotation.z += -S(s) * .3 * w; R['elbow' + s].rotation.x += -1.6 * w; R['hip' + s].rotation.x += -.5 * w; R['knee' + s].rotation.x += .9 * w; } },
  bow(C, c) { const R = C.rig, w = c.w; R.spine.rotation.x += .55 * w; R.head.rotation.x += .2 * w; for (const s of ['L', 'R']) R['shoulder' + s].rotation.x += .25 * w; },
  sip(C, c) { const R = C.rig, w = c.w; R.shoulderR.rotation.x += -.7 * w; R.elbowR.rotation.x += -2.1 * w; R.head.rotation.x += -.15 * w * smooth((c.u - .3) * 3); },
  jump(C, c) { // anticipation crouch → air (squash/stretch) → landing absorb
    const R = C.rig, u = c.u, d = c.d; const crouch = envelope(u, .35, .15, .15), air = u > .3 && u < d - .3 ? Math.sin(Math.PI * (u - .3) / (d - .6)) : 0, land = envelope(u - (d - .35), .35, .08, .25);
    R.hips.position.y += (-.12 * crouch + .55 * air - .1 * land); R.root.scale.y *= 1 - .07 * crouch + .06 * air - .06 * land;
    for (const s of ['L', 'R']) { R['shoulder' + s].rotation.z += S(s) * (2.4 * air - .3 * crouch); R['hip' + s].rotation.x += -.6 * (crouch + land) - .3 * air; R['knee' + s].rotation.x += 1.1 * (crouch + land) + .5 * air; } },
};

/* ---------------- locomotion ---------------- */
/** moves: [{t0, t1, from:[x,z], to:[x,z], style:'walk'|'sneak'|'run'}]; returns {x, z, yaw, walking, phase, style} */
export function locomotion(moves, t, start) {
  let cur = start || (moves[0] ? moves[0].from : [0, 0]), yaw = 0;
  for (const m of moves) {
    if (t >= m.t1) { cur = m.to; yaw = m.faceAfter ?? 0; continue; }
    if (t >= m.t0) {
      const k = (t - m.t0) / (m.t1 - m.t0), kk = smooth(k) * .25 + k * .75;
      const dx = m.to[0] - m.from[0], dz = m.to[1] - m.from[1], dist = Math.hypot(dx, dz);
      const cad = m.style === 'run' ? 2.6 : m.style === 'sneak' ? .8 : 1.7;      // steps per second (pairs)
      const cycles = Math.max(1, Math.round((m.t1 - m.t0) * cad / 2) * 1);
      return { x: lerp(m.from[0], m.to[0], kk), z: lerp(m.from[1], m.to[1], kk), yaw: Math.atan2(dx, dz), walking: true, phase: kk * cycles, style: m.style || 'walk', stride: dist / cycles };
    }
    break;
  }
  return { x: cur[0], z: cur[1], yaw, walking: false, phase: 0, style: 'stand' };
}
function applyWalk(C, L) {
  const R = C.rig; if (!L.walking) return;
  const p = L.phase * Math.PI * 2, big = L.style === 'run' ? 1.5 : L.style === 'sneak' ? .7 : 1;
  const sw = Math.sin(p) * .45 * big;
  R.hipL.rotation.x += sw; R.hipR.rotation.x += -sw;
  R.kneeL.rotation.x += Math.max(0, Math.sin(p + 1.6)) * .8 * big; R.kneeR.rotation.x += Math.max(0, Math.sin(p + 1.6 + Math.PI)) * .8 * big;
  R.shoulderL.rotation.x += -sw * .7; R.shoulderR.rotation.x += sw * .7;
  R.elbowL.rotation.x += -.25 * big; R.elbowR.rotation.x += -.25 * big;
  R.hips.position.y += -Math.abs(Math.cos(p)) * .025 * big + (L.style === 'sneak' ? -.08 : 0);
  R.hips.rotation.y += Math.sin(p) * .08; R.chest.rotation.y += -Math.sin(p) * .12;
  R.chest.rotation.x += L.style === 'run' ? .2 : L.style === 'sneak' ? .25 : .04;
}

/* ---------------- visemes ---------------- */
// shapes: rest, M (closed), A (open), E (wide), O (round). mouth.json from scripts/mouth.py is [{lv, shape}] per frame.
const VIS = { rest: [1.3, .25], M: [1.1, .12], A: [1.25, 1.5], E: [1.8, .55], O: [.85, 1.15] };
/** visemeAt(words, t): fallback when there is no mouth.json: syllable-rate open/close inside each spoken word */
export function visemeAt(words, t) {
  for (const w of words || []) if (t >= w.start && t < w.end) {
    const n = Math.max(1, Math.round((w.end - w.start) * 6)); const ph = ((t - w.start) / (w.end - w.start)) * n;
    const open = Math.sin(Math.PI * (ph % 1)); const v = hash(Math.floor(ph) + w.start * 13);
    return { lv: open, shape: open < .2 ? 'M' : v < .45 ? 'A' : v < .75 ? 'E' : 'O' };
  }
  return { lv: 0, shape: 'rest' };
}

/* ---------------- the per-frame driver ---------------- */
/**
 * animate(C, t, A): A = { seed, moves, start:[x,z], baseYaw, clips:[{t, d, do, side}], expr:[{t, name}], look:{x,y,z}|null,
 *                       speech: (t)=>({lv, shape}) | null, talking: bool }
 */
export function animate(C, t, A = {}) {
  const R = C.rig, F = C.face, seed = A.seed || 1;
  // reset to bind pose
  for (const k in R) { const g = R[k]; if (g !== R.root) g.rotation.set(0, 0, 0); }
  R.hips.position.y = .86; R.root.scale.set(C.opts.height, C.opts.height, C.opts.height);
  R.shoulderL.position.y = R.shoulderR.position.y = .19;
  // rest pose: arms relaxed, slight elbow bend
  R.shoulderL.rotation.z = .08; R.shoulderR.rotation.z = -.08; R.elbowL.rotation.x = R.elbowR.rotation.x = -.12;
  // locomotion
  const L = locomotion(A.moves || [], t, A.start);
  R.root.position.set(L.x, 0, L.z); R.root.rotation.y = L.walking ? L.yaw : (A.baseYaw ?? L.yaw);
  applyWalk(C, L);
  // idle (always on)
  const br = Math.sin(t * Math.PI * 2 * .27 + seed);
  R.chest.scale.set(1 + br * .012, 1 + br * .018, 1 + br * .012);
  R.hips.rotation.z += fbm(t * .25, seed) * .03; R.spine.rotation.z += -fbm(t * .25, seed) * .025;
  R.head.rotation.y += fbm(t * .3, seed + 3) * .12; R.head.rotation.x += fbm(t * .27, seed + 5) * .05;
  R.shoulderL.rotation.z += fbm(t * .4, seed + 7) * .03; R.shoulderR.rotation.z -= fbm(t * .4, seed + 9) * .03;
  if (R.tail) R.tail.rotation.x = .3 + Math.sin(t * 2.2) * .12 + (L.walking ? Math.sin(L.phase * Math.PI * 4) * .2 : 0);
  // clips
  let exprName = 'neutral';
  for (const e of A.expr || []) if (e.t <= t) exprName = e.name;
  let clipExpr = null, clipW = 0;
  for (const c of A.clips || []) {
    const d = c.d || (c.do === 'jump' ? 1.1 : c.do === 'wave' ? 1.6 : 1.3), u = t - c.t;
    const w = envelope(u, d); if (w <= 0 || !CLIPS[c.do]) continue;
    CLIPS[c.do](C, { u, d, w, t, side: c.side, args: c.args });
    const ce = { laugh: 'laugh', shock: 'shock', cower: 'scared', think: 'thinking', thumbs: 'happy', wave: 'happy', jump: 'excited' }[c.do];
    if (ce && w > clipW) { clipExpr = ce; clipW = w; }
  }
  // speech
  const sp = A.speech ? A.speech(t) : { lv: 0, shape: 'rest' };
  if (sp.lv > 0) { R.head.rotation.x += Math.sin(t * 7.3) * sp.lv * .03; R.head.rotation.z += Math.sin(t * 3.1) * sp.lv * .02; }
  // look-at (head + eyes) toward a world point
  if (A.look) { R.head.parent.updateMatrixWorld(true); const lp = R.head.parent.worldToLocal(_v.set(A.look.x, A.look.y, A.look.z)); R.head.rotation.y += clamp(Math.atan2(lp.x, lp.z), -.8, .8) * .7; R.head.rotation.x += clamp(-Math.atan2(lp.y - .2, Math.hypot(lp.x, lp.z)), -.4, .4) * .5; }
  // face
  let E = EXPR[exprName] || EXPR.neutral; if (clipExpr) E = blendExpr(E, EXPR[clipExpr], clamp(clipW));
  const blinkSlot = Math.floor((t + seed * 1.37) / 3.1), bt = (t + seed * 1.37) - blinkSlot * 3.1 - hash(blinkSlot + seed) * 2.4;
  const blink = bt > 0 && bt < .13 ? Math.sin(Math.PI * bt / .13) : 0;
  const lid = clamp(Math.max(E.lid, blink), -.1, 1);
  const sac = Math.floor(t * .8 + seed), sx = (hash(sac) - .5) * .006, sy = (hash(sac + 9) - .5) * .004;
  F.eyes.forEach((eg, i) => { eg.scale.setScalar(1 + E.wide * .18);
    F.pupils[i].scale.setScalar(E.pupil); F.pupils[i].position.x = sx; F.pupils[i].position.y = sy;
    F.lids[i].rotation.x = lerp(-1.75, -.05, lid) ; F.lids[i].visible = lid > .02;
    const b = F.brows[i]; b.position.y = (.185 + E.brow * .02) * C.opts.headScale; b.rotation.z = (i === 0 ? -1 : 1) * E.browTilt * .35; });
  F.cheeks.forEach(c => c.material.opacity = E.blush * .45);
  // mouth: speech viseme wins, else expression mouth
  const mood = E.mouth; let vis = VIS.rest; F.smile.visible = false; F.teeth.visible = false; F.mouthHole.visible = true;
  if (sp.lv > .05) { const v = VIS[sp.shape] || VIS.A; vis = [v[0], lerp(.25, v[1], clamp(sp.lv * 1.3))]; F.teeth.visible = sp.shape === 'E' || sp.shape === 'A'; }
  else if (mood === 'smile' || mood === 'smirk') { F.mouthHole.visible = false; F.smile.visible = true; F.smile.rotation.z = Math.PI + (mood === 'smirk' ? .25 : 0); }
  else if (mood === 'grin' || mood === 'laugh') { vis = [1.9, mood === 'laugh' ? 1.3 : .8]; F.teeth.visible = true; }
  else if (mood === 'shock') vis = [1.0, 1.9];
  else if (mood === 'frown') { F.mouthHole.visible = false; F.smile.visible = true; F.smile.rotation.z = 0; }
  else if (mood === 'wobble') vis = [1.3, .4 + Math.sin(t * 30) * .15];
  F.mouthHole.scale.set(vis[0], vis[1], .4);
  return { loc: L, expr: exprName };
}

/* ---------------- stage directions ---------------- */
/**
 * direct(spec, words) turns a cast entry into animate() args.
 * spec = { id, marks:{door:[x,z], desk:[x,z]}, start:'door', acts:[ {t, do:'walk', to:'desk', d}, {t, do:'wave'}, {at:'namaste', do:'wave'}, {t, expr:'happy'} ],
 *          speaks:[ [t0,t1], ... ], autoGestures:true }
 */
export function direct(spec, words = []) {
  const marks = spec.marks || {}; const P = m => Array.isArray(m) ? m : marks[m] || [0, 0];
  const out = { seed: spec.seed || hashStr(spec.id || 'a'), moves: [], clips: [], expr: [], start: P(spec.start || [0, 0]), baseYaw: spec.yaw };
  let pos = out.start;
  const findWord = (w, after = 0) => words.find(x => x.start >= after && norm(x.word) === norm(w));
  for (const a of spec.acts || []) {
    let t = a.t; if (a.at) { const w = findWord(a.at, a.after || 0); if (!w) continue; t = w.start + (a.lead ?? -.15); }
    if (a.expr) out.expr.push({ t, name: a.expr });
    if (!a.do) continue;
    if (['walk', 'sneak', 'run'].includes(a.do)) { const to = P(a.to); const d = a.d || Math.max(.8, Math.hypot(to[0] - pos[0], to[1] - pos[1]) / (a.do === 'run' ? 3 : a.do === 'sneak' ? .6 : 1.2)); out.moves.push({ t0: t, t1: t + d, from: pos, to, style: a.do, faceAfter: a.face ?? 0 }); pos = to; }
    else out.clips.push({ t, d: a.d, do: a.do, side: a.side });
  }
  if (spec.autoGestures !== false && spec.speaks) {                   // rigpop-agents style: gestures from keywords while talking
    let next = 0;
    for (const w of words) {
      if (w.start < next || !(spec.speaks || []).some(([a, b]) => w.start >= a && w.start < b)) continue;
      const key = norm(w.word); const g = Object.keys(AUTO_WORDS).find(k => AUTO_WORDS[k].includes(key));
      if (g && !out.clips.some(c => Math.abs(c.t - w.start) < 1.5)) { out.clips.push({ t: w.start - .15, do: g }); next = w.start + 2.2; }
    }
  }
  out.moves.sort((a, b) => a.t0 - b.t0); out.clips.sort((a, b) => a.t - b.t); out.expr.sort((a, b) => a.t - b.t);
  return out;
}
const norm = s => String(s).toLowerCase().replace(/[^\p{L}\p{N}\p{M}'-]/gu, '');
const hashStr = s => { let h = 7; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 9973; return h; };

/** speechFrom(mouthFrames, fps, windows): returns (t)=>viseme, silent outside the speaker's windows */
export function speechFrom(mouth, fps, windows, words) {
  return t => {
    if (windows && !windows.some(([a, b]) => t >= a && t < b)) return { lv: 0, shape: 'rest' };
    if (mouth && mouth.length) { const f = mouth[Math.min(mouth.length - 1, Math.max(0, Math.round(t * fps)))]; return f || { lv: 0, shape: 'rest' }; }
    return visemeAt(words, t);
  };
}
