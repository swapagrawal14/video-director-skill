// Render contract shim (injected before any page script by _server.open_page).
// Makes ANY HTML/JS/three.js/GSAP/CSS-free animation deterministic for frame-by-frame capture:
//  - virtual clock: Date.now, performance.now, requestAnimationFrame, setTimeout/setInterval follow window.__vt (ms)
//  - seeded Math.random (mulberry32, seed = window.__SEED || 1337)
// Drive it with window.__setTime(seconds). The template engine uses renderAt(t) directly and does not need it,
// but custom scenes (copied codepens, GSAP timelines, particle libs) become renderable through it.
(() => {
  let vt = 0; const start = 1700000000000; let seed = (window.__SEED || 1337) >>> 0;
  Math.random = () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const RD = Date; class VDate extends RD { constructor(...a) { a.length ? super(...a) : super(start + vt); } static now() { return start + vt; } }
  window.Date = VDate; performance.now = () => vt;
  let rafQ = [], timers = [], tid = 1;
  window.requestAnimationFrame = cb => { rafQ.push(cb); return rafQ.length; };
  window.cancelAnimationFrame = () => {};
  window.setTimeout = (cb, ms = 0, ...a) => { timers.push({ id: tid, at: vt + ms, cb, a }); return tid++; };
  window.setInterval = (cb, ms = 0, ...a) => { const id = tid++; const tick = () => { cb(...a); timers.push({ id, at: vt + ms, cb: tick, a: [] }); };
    timers.push({ id, at: vt + ms, cb: tick, a: [] }); return id; };
  window.clearTimeout = window.clearInterval = id => { timers = timers.filter(x => x.id !== id); };
  window.__setTime = s => {           // advance virtual time to s seconds, firing due timers then one rAF batch
    vt = s * 1000;
    for (let guard = 0; guard < 1000; guard++) { const due = timers.filter(x => x.at <= vt); if (!due.length) break;
      timers = timers.filter(x => x.at > vt); due.forEach(x => x.cb(...x.a)); }
    const q = rafQ; rafQ = []; q.forEach(cb => cb(vt));
    document.getAnimations && document.getAnimations().forEach(an => { an.pause(); an.currentTime = vt; });  // CSS/WAAPI animations
  };
})();
