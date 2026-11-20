"""Procedural SFX + music bed (no sample files needed). All return mono float32 @ SR."""
import numpy as np
SR = 44100
_r = np.random.default_rng(1)
def _env(sec, decay): t = np.arange(int(sec * SR)) / SR; return t, np.exp(-t * decay)
def pop():    t, e = _env(.12, 38); f = 520 * np.exp(-t * 9) + 180; return np.sin(2 * np.pi * np.cumsum(f) / SR) * e * .18
def squish(): t, e = _env(.25, 14); f = 140 + 60 * np.sin(t * 40); return (np.sin(2 * np.pi * np.cumsum(f) / SR) * .5 + _r.standard_normal(len(t)) * .15) * e * .35
def whoosh():
    L = int(.45 * SR); k = np.convolve(_r.standard_normal(L), np.ones(30) / 30, 'same'); t = np.arange(L) / L; return k * np.sin(np.pi * t) ** 2 * .5
def dab():    t, e = _env(.06, 70); return _r.standard_normal(len(t)) * e * .05
def plip():   t, e = _env(.15, 30); f = 900 + 1400 * np.exp(-t * 40); return np.sin(2 * np.pi * np.cumsum(f) / SR) * e * .12
def tick():   t, e = _env(.04, 150); return np.sin(2 * np.pi * 2500 * t) * e * .08
def boing():  t, e = _env(.35, 8); f = 220 + 120 * np.sin(t * 60) * np.exp(-t * 6); return np.sin(2 * np.pi * np.cumsum(f) / SR) * e * .2
def pour(sec=1.0):
    L = int(sec * SR); n = np.convolve(_r.standard_normal(L), np.ones(8) / 8, 'same'); m = 0.6 + 0.4 * np.sin(np.arange(L) / SR * 40); return n * m * .08
def thunder():
    L = int(1.6 * SR); n = _r.standard_normal(L); k = np.convolve(n, np.ones(60) / 60, 'same'); t = np.arange(L) / SR
    crack = _r.standard_normal(int(.08 * SR)) * np.exp(-np.arange(int(.08 * SR)) / SR * 40) * .5
    out = k * np.exp(-t * 2.2) * (1 + .5 * np.sin(t * 9)) * 1.4; out[:len(crack)] += crack; return out * .6
def ring():
    t = np.arange(int(.5 * SR)) / SR; g = (np.sin(2 * np.pi * 22 * t) > 0).astype(np.float32)
    return (np.sin(2 * np.pi * 1300 * t) + .6 * np.sin(2 * np.pi * 1700 * t)) * g * np.exp(-t * 1.5) * .07
FX = dict(thunder=thunder, ring=ring, pop=pop, squish=squish, whoosh=whoosh, dab=dab, plip=plip, tick=tick, boing=boing, pour=pour)

def pluck_bed(dur, vol=.03, bpm=120):
    notes = [261.63, 293.66, 329.63, 392.0, 440.0, 523.25]; prog = [[0, 2, 4], [1, 3, 5], [0, 2, 3], [2, 4, 5]]
    N = int(dur * SR); out = np.zeros(N, np.float32); tp = np.arange(int(1.2 * SR)) / SR; k = 0; tt = 0; step = 60 / bpm
    while tt < dur - .5:
        ch = prog[(k // 8) % 4]; fr = notes[ch[k % 3]] * (.5 if k % 4 == 0 else 1)
        tone = (np.sin(2 * np.pi * fr * tp) + .3 * np.sin(2 * np.pi * fr * 4 * tp) * np.exp(-tp * 12)) * np.exp(-tp * 4.5)
        i = int(tt * SR); L = min(len(tone), N - i); out[i:i + L] += tone[:L] * vol; k += 1; tt += step
    return out

def mix(dur, vo=None, vo_at=0.0, vo_gain=1.6, events=(), bed=True):
    """events: list of (time_sec, fx_name). Returns normalised mono mix."""
    N = int(dur * SR); m = np.zeros(N, np.float32)
    if vo is not None:
        i = int(vo_at * SR); L = min(len(vo), N - i); m[i:i + L] += vo[:L] * vo_gain
    for t, k in events:
        s = FX[k](); i = int(t * SR)
        if 0 <= i < N: L = min(len(s), N - i); m[i:i + L] += s[:L]
    if bed: m += pluck_bed(dur)
    return m / max(1, np.abs(m).max() / .95)
