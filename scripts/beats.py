#!/usr/bin/env python3
"""Beat / downbeat-ish / onset grid for cutting on the beat.
Usage: python3 scripts/beats.py music.wav beats.json
Out: {"bpm":..,"beats":[s..],"bars":[s..] (every 4th beat from the strongest phase),"onsets":[s..],"hits":[s..] (top-strength onsets)}
Use: snap scene cuts (timing.json scene starts) to the nearest beat within +-0.25 s; put title slams/whooshes on "hits"."""
import json, sys
import numpy as np, librosa
y, sr = librosa.load(sys.argv[1], sr=22050, mono=True)
env = librosa.onset.onset_strength(y=y, sr=sr)
tempo, bf = librosa.beat.beat_track(onset_envelope=env, sr=sr, units='frames')
beats = librosa.frames_to_time(bf, sr=sr)
# crude bar phase: pick the 4-beat phase with the most onset energy
ph = int(np.argmax([env[bf[p::4]].sum() if len(bf[p::4]) else 0 for p in range(4)])) if len(bf) >= 4 else 0
bars = beats[ph::4]
of = librosa.onset.onset_detect(onset_envelope=env, sr=sr, units='frames', backtrack=True)
onsets = librosa.frames_to_time(of, sr=sr)
strong = of[np.argsort(env[of])[::-1][:max(1, len(of) // 8)]] if len(of) else of
out = {'bpm': float(np.atleast_1d(tempo)[0]), 'beats': np.round(beats, 3).tolist(), 'bars': np.round(bars, 3).tolist(),
       'onsets': np.round(onsets, 3).tolist(), 'hits': sorted(np.round(librosa.frames_to_time(strong, sr=sr), 3).tolist())}
json.dump(out, open(sys.argv[2], 'w'))
print(f"bpm {out['bpm']:.1f}  beats {len(beats)}  bars {len(bars)}  onsets {len(onsets)}  hits {len(out['hits'])}")

def snap(t, grid, tol=0.25):
    """Move a cut to the nearest beat if within tol seconds."""
    g = np.asarray(grid); i = int(np.abs(g - t).argmin()) if len(g) else -1
    return float(g[i]) if i >= 0 and abs(g[i] - t) <= tol else t
