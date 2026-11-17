"""Royalty-free procedural music bed, length = timing.json duration.
Usage: python3 scripts/music.py <project-dir> [mood]   mood: calm | upbeat | horror | epic | lofi  (default from project.json "music_mood")
Writes music.wav. Pure Python + numpy-free; ~20-40 s to generate for a 5-min bed."""
import math, random, wave, array, json, os, sys
d = sys.argv[1]; P = json.load(open(os.path.join(d, 'project.json'))); T = json.load(open(os.path.join(d, 'timing.json')))
mood = sys.argv[2] if len(sys.argv) > 2 else P.get('music_mood', 'calm')
SR = 22050; D = T['duration'] + 0.2; N = int(SR * D); random.seed(7); buf = [0.0] * N
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
MOODS = {
 'calm':   dict(ch=[[48,55,60,64,67],[45,52,57,60,64],[41,48,53,57,60],[43,50,55,59,62]], bar=4.0, bpm=88, pluck=.62, pad=.045, pl=.07, drone=0, noise=0),
 'upbeat': dict(ch=[[48,55,60,64,67],[43,50,55,59,62],[45,52,57,60,64],[41,48,53,57,60]], bar=2.0, bpm=118, pluck=.85, pad=.035, pl=.085, drone=0, noise=0, kick=True),
 'lofi':   dict(ch=[[50,57,60,64,69],[45,52,55,59,64],[47,54,57,62,66],[43,50,53,57,62]], bar=4.0, bpm=78, pluck=.5, pad=.05, pl=.06, drone=0, noise=.004, kick=True),
 'epic':   dict(ch=[[45,52,57,60,64],[41,48,53,57,60],[48,55,60,64,67],[43,50,55,59,62]], bar=4.0, bpm=96, pluck=.75, pad=.06, pl=.06, drone=.05, noise=0, kick=True),
 'horror': dict(ch=[[36,37,43,48],[35,41,42,47],[36,39,42,48],[34,40,41,46]], bar=6.0, bpm=50, pluck=.18, pad=.05, pl=.05, drone=.07, noise=.01),
}[mood]
bar = MOODS['bar']; chs = MOODS['ch']
for ci in range(int(D / bar) + 1):  # pads
    ch = chs[ci % 4]; s0 = int(ci * bar * SR); L = bar + .6; s1 = min(N, int((ci * bar + L) * SR)); fr = [hz(m) for m in ch[:4]]
    for i in range(s0, s1):
        tt = (i - s0) / SR; env = min(1, tt / 1.2) * min(1, (L - tt) / 1.0); v = 0
        for k, f in enumerate(fr): v += math.sin(2 * math.pi * f * i / SR + k) * (.5 if k == 0 else .3)
        buf[i] += v * env * MOODS['pad']
if MOODS['drone']:  # low beating drone
    for i in range(N):
        tt = i / SR; buf[i] += MOODS['drone'] * (math.sin(2 * math.pi * 55 * tt) + .6 * math.sin(2 * math.pi * 55.7 * tt)) * (.6 + .4 * math.sin(tt * .3))
step = 60 / MOODS['bpm'] / 2; t = 2.0
while t < D - 3:  # plucks
    ch = chs[int(t / bar) % 4]
    if random.random() < MOODS['pluck']:
        f = hz(random.choice(ch) + 12); s0 = int(t * SR)
        for j in range(int(1.4 * SR)):
            i = s0 + j
            if i >= N: break
            tt = j / SR; e = math.exp(-tt * 4.2) * min(1, tt / .004); buf[i] += (math.sin(2 * math.pi * f * tt) + .3 * math.sin(4 * math.pi * f * tt)) * e * MOODS['pl']
    t += step
if MOODS.get('kick'):
    t = 4.0
    while t < D - 4:
        s0 = int(t * SR)
        for j in range(int(.25 * SR)):
            i = s0 + j
            if i >= N: break
            tt = j / SR; buf[i] += math.sin(2 * math.pi * (50 + 90 * math.exp(-tt * 30)) * tt) * math.exp(-tt * 14) * .12
        t += 60 / MOODS['bpm']
if MOODS['noise']:
    y = 0
    for i in range(N): y += .02 * ((random.random() * 2 - 1) - y); buf[i] += y * MOODS['noise'] * 40
for i in range(N): tt = i / SR; buf[i] *= min(1, tt / 1.5) * min(1, (D - tt) / 2.5)
mx = max(abs(x) for x in buf) or 1; a = array.array('h', (int(x / mx * .8 * 32767) for x in buf))
w = wave.open(os.path.join(d, 'music.wav'), 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes()); w.close(); print('music.wav', mood, round(D, 1), 's')
