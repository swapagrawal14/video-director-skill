"""Procedural sound effects for screencast reels: synthesized in numpy, so every sound is original and
needs no sample pack or licence. Each cue is a pure function of its kind and seed.

  whoosh   band-swept noise for whip / zoomblur cuts
  rip      crackly torn-paper burst for rip cuts
  flash    short bright shimmer for flash cuts
  click    mouse click (two tiny transients)
  type     a run of key ticks for typing
  pop      bubbly pitch-drop for stickers and STEP chips
  ding     soft bell for the outro / success beats
  riser    rising noise sweep into the outro

python3 -m screencast.sfx demo out_dir/    # writes one wav per kind to audition
"""
import os, sys, wave
import numpy as np

SR = 48000


def _env(n, a=.004, r=.08):
    t = np.arange(n) / SR; e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / max(r, 1e-4))
    return e.astype(np.float32)


def _bandnoise(n, lo, hi, rng):
    """Noise whose band centre sweeps lo -> hi (Hz) over its length, via FFT segments."""
    x = rng.standard_normal(n).astype(np.float32); out = np.zeros(n, np.float32); seg = 1024
    win = np.hanning(seg * 2).astype(np.float32)
    for s in range(0, n, seg):
        c = lo * (hi / lo) ** (s / max(1, n))
        chunk = x[s:s + seg * 2]
        if len(chunk) < 8: break
        F = np.fft.rfft(chunk * win[:len(chunk)]); f = np.fft.rfftfreq(len(chunk), 1 / SR)
        F *= np.exp(-((np.log(f + 1) - np.log(c)) ** 2) / .35)
        y = np.fft.irfft(F, len(chunk)); out[s:s + len(y)] += y
    return out / (np.abs(out).max() + 1e-9)


def make(kind, seed=0, dur=None):
    rng = np.random.default_rng(seed)
    if kind == 'whoosh':
        n = int(SR * (dur or .38)); t = np.linspace(0, 1, n)
        y = _bandnoise(n, 300, 5000, rng) * np.sin(np.pi * t) ** 1.5; return .7 * y
    if kind == 'riser':
        n = int(SR * (dur or 1.1)); t = np.linspace(0, 1, n)
        y = _bandnoise(n, 200, 7000, rng) * t ** 2.2 * (1 - np.clip((t - .96) / .04, 0, 1)); return .5 * y
    if kind == 'rip':
        n = int(SR * (dur or .32)); y = np.zeros(n, np.float32)
        for k in range(int(n / SR * 260)):
            p = int(rng.uniform(0, n - 400)); L = int(rng.uniform(40, 300))
            y[p:p + L] += rng.standard_normal(L) * _env(L, .0005, .002) * rng.uniform(.3, 1)
        y = np.convolve(y, [1, -.6], 'same') * np.linspace(1, .3, n); return .55 * y / (np.abs(y).max() + 1e-9)
    if kind == 'flash':
        n = int(SR * .45); t = np.arange(n) / SR
        y = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in (2093, 2637, 3136, 4186)) / 4
        y = y * _env(n, .002, .12) + .15 * _bandnoise(n, 6000, 9000, rng) * _env(n, .001, .05); return .35 * y
    if kind == 'click':
        n = int(SR * .06); y = np.zeros(n, np.float32)
        for off, g in ((0, 1), (int(SR * .018), .55)):
            L = int(SR * .006); y[off:off + L] += rng.standard_normal(L) * _env(L, .0002, .0012) * g
        return .6 * np.convolve(y, [1, -.85], 'same')
    if kind == 'type':
        n = int(SR * (dur or .8)); y = np.zeros(n, np.float32); p = 0
        while p < n - 800:
            L = int(SR * .012); y[p:p + L] += rng.standard_normal(L) * _env(L, .0002, .002) * rng.uniform(.4, 1)
            p += int(SR * rng.uniform(.055, .12))
        return .4 * np.convolve(y, [1, -.7], 'same')
    if kind == 'pop':
        n = int(SR * .14); t = np.arange(n) / SR; f = 900 * np.exp(-t * 28) + 260
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, .001, .04); return .55 * y
    if kind == 'ding':
        n = int(SR * 1.2); t = np.arange(n) / SR
        y = (np.sin(2 * np.pi * 1318.5 * t) + .4 * np.sin(2 * np.pi * 2637 * t) + .2 * np.sin(2 * np.pi * 3955 * t)) * _env(n, .002, .35)
        return .3 * y
    raise ValueError(kind)


CUT_SOUND = {'whip': 'whoosh', 'zoomblur': 'whoosh', 'rip': 'rip', 'flash': 'flash'}


def cues(R):
    """(time, kind) list for a compose.Reel: a sound on every cut, click and typed field, a pop on each
    STEP chip and sticker, a riser + ding into the outro. Beat keys `"sfx": false` silence one beat."""
    out = []
    for c, kind in R.cuts[:-1]: out.append((c - .12, CUT_SOUND.get(kind, 'whoosh')))
    for k, beat in enumerate(R.S['beats']):
        if beat.get('sfx') is False: continue
        a = R.win[k][0]
        if beat.get('step'): out.append((a + .05, 'pop'))
        if beat.get('sticker'): out.append((a + float(beat['sticker'].get('at', .5)), 'pop'))
        for e in R.beat_events(k):
            ft = R.to_final(e['t'], k)
            if e['type'] == 'click': out.append((ft, 'click'))
            if e['type'] == 'type': out.append((ft, 'type'))
    out += [(R.end_t - 1.0, 'riser'), (R.end_t + .05, 'ding')]
    return sorted(out)


def _read(p):
    w = wave.open(p); sr = w.getframerate(); ch = w.getnchannels()
    a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return (a.reshape(-1, ch) if ch > 1 else np.stack([a, a], 1)), sr


def _write(p, a, sr=SR):
    w = wave.open(p, 'wb'); w.setnchannels(a.shape[1] if a.ndim > 1 else 1); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()


def mix(proj, gain=.5):
    """mix.wav + cues -> mix_sfx.wav (render picks it up when present)."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from screencast.compose import Reel
    R = Reel(proj); src = f'{proj}/mix.wav'; base, sr = _read(src)
    if sr != SR:   # loudnorm upsamples (often to 192 kHz); bring it back to 48 kHz
        import subprocess; tmp = f'{proj}/.mix48.wav'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-ar', str(SR), '-ac', '2', tmp], check=True)
        base, sr = _read(tmp); os.remove(tmp)
    lay = np.zeros(len(base), np.float32); cs = cues(R)
    for i, (t, kind) in enumerate(cs):
        s = make(kind, seed=i); p = max(0, int(t * SR)); e = min(len(lay), p + len(s))
        if p < e: lay[p:e] += s[:e - p]
    out = base + gain * lay[:, None]
    pk = np.abs(out).max(); out = out / pk * .89 if pk > .89 else out
    _write(f'{proj}/mix_sfx.wav', out); print(f'sfx: {len(cs)} cues -> mix_sfx.wav')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'demo':
        os.makedirs(sys.argv[2], exist_ok=True)
        for k in ('whoosh', 'rip', 'flash', 'click', 'type', 'pop', 'ding', 'riser'):
            _write(f'{sys.argv[2]}/{k}.wav', make(k)[:, None].repeat(2, 1))
        print('wrote demos to', sys.argv[2])
    else: sys.exit(__doc__)
