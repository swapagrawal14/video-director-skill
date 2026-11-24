// Smoke-runs the TEXTFX kit of template/index.html (between TEXTFX-BEGIN / TEXTFX-END) for every title motion x
// step style x caption preset against a stub 2D context. Used by tests/test_text_presets.py. Usage: node textfx_smoke.mjs index.html
import fs from 'fs';
const src = fs.readFileSync(process.argv[2], 'utf8');
const blk = src.slice(src.indexOf('/* TEXTFX-BEGIN'), src.indexOf('/* TEXTFX-END */'));
const calls = []; const grad = { addColorStop() {} };
const g2 = new Proxy({ letterSpacing: '0px' }, { get: (o, k) => k in o ? o[k] : (k === 'measureText' ? (t => ({ width: String(t).length * 12 })) : (k.startsWith('create') ? () => grad : (...a) => { calls.push(k); })), set: (o, k, v) => { o[k] = v; return true; }, has: (o, k) => k === 'letterSpacing' || k in o });
const K = 1, W = 1280, H = 720, ACC = '#ff8a3d', ACC2 = '#7fd1ff', INK = '#23324a';
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x)); const lerp = (a, b, t) => a + (b - a) * t;
const ease = x => { x = clamp(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const easeOut = x => 1 - Math.pow(1 - clamp(x), 3);
const back = x => { x = clamp(x); const c1 = 1.7, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const F = (wt, px) => `${wt} ${Math.round(px * K)}px Baloo`;
function wrapLines(text, maxW, font) { return [text]; }
const modes = ['card-rise','slam-squash','typewriter','mask-wipe','letter-bounce','slide-stack','marker-sweep','draw-on','slow-fade','none','fade'];
const steps = ['chip','counter-dial','tape-strip','none'];
const caps = ['pill','pop-word','karaoke-sweep','lower-third-ticker','marker-highlight','outline-bold','typewriter-reveal','stacked-bounce','minimal-serif','chalk-hand'];
for (const m of modes) { for (const st of steps) { for (const c of caps) {
  const P = { look: { title_motion: m, step_style: st, captions_preset: c } };
  const f = new Function('P','g2','K','W','H','ACC','ACC2','INK','clamp','lerp','ease','easeOut','back','F','wrapLines', blk + `
    for (const t of [0, .1, .3, .7, 1.5, 4]) {
      if (TMODE !== 'card-rise') titleFx(t, 6, [['KICK', 700, 20, ACC], ['Title text', 800, 62, '#fff']], .3);
      fxText(TMODE, 'Label', 10, 10, t, {}); if (STEP_STYLE === 'counter-dial') stepDial(2, 4, 'Bend', 'ACTION', t, {d: 6}); if (STEP_STYLE === 'tape-strip') stepTape(2, 4, 'Bend', 'ACTION', t, {d: 6});
      if (SUB_FX[CAPS]) SUB_FX[CAPS]('some caption words here', 1, Math.min(1, t / 2), t, 2);
    }`);
  f(P, g2, K, W, H, ACC, ACC2, INK, clamp, lerp, ease, easeOut, back, F, wrapLines);
}}}
console.log('OK', calls.length);
