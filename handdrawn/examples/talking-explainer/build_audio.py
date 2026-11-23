"""Step 1: after VO wavs exist in vo/s00.wav.., build vo_full.wav + timeline.json (scene times, word timings, per-frame mouth levels)."""
import json, subprocess, wave, numpy as np, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
L = json.load(open('lines.json'))
LEAD, GAP, TAIL = 0.5, 0.35, 2.4
SR = 44100
segs = []; t = LEAD; audio = []
def readwav(p):
    w = wave.open(p); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if w.getnchannels() == 2: a = a.reshape(-1, 2).mean(1)
    return a
pcm = np.zeros(int(SR * 80), np.float32)
words = []
for i, line in enumerate(L):
    a = readwav(f'vo/s{i:02d}.wav')
    # trim leading/trailing silence
    env = np.abs(a); thr = 0.02
    idx = np.nonzero(env > thr)[0]; s, e = (idx[0], idx[-1]) if len(idx) else (0, len(a))
    s = max(0, s - int(.03 * SR)); e = min(len(a), e + int(.06 * SR)); a = a[s:e]
    d = len(a) / SR; i0 = int(t * SR); pcm[i0:i0 + len(a)] += a
    # word timings: proportional to char length inside speech span, pauses at punctuation
    ws = line.split(); wts = [len(w.strip('.,!?')) + 2 + (4 if w[-1] in ',.!?' else 0) for w in ws]
    tot = sum(wts); c = t
    for w, k in zip(ws, wts):
        dur = d * k / tot; words.append({'word': w.strip('.'), 'start': round(c, 3), 'end': round(c + dur * .85, 3), 'scene': i}); c += dur
    segs.append({'i': i, 'start': round(t, 3), 'end': round(t + d, 3)})
    t += d + GAP
DUR = t - GAP + TAIL
pcm = pcm[:int(DUR * SR)]
# per-frame mouth level at 30fps
FPS = 30; hop = SR // FPS
lv = [float(np.sqrt(np.mean(pcm[k * hop:(k + 1) * hop] ** 2)) if k * hop < len(pcm) else 0) for k in range(int(DUR * FPS) + 2)]
m = max(lv) or 1; lv = [x / m for x in lv]
pcm16 = (np.clip(pcm, -1, 1) * 32767).astype(np.int16)
w = wave.open('vo_full.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm16.tobytes()); w.close()
json.dump({'duration': DUR, 'fps': FPS, 'segs': segs, 'words': words, 'mouth': lv}, open('timeline.json', 'w'))
print('duration', DUR, segs)
