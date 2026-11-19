#!/usr/bin/env python3
"""mouth.py - per-frame mouth shapes (lip-sync track) from a voice file.

Python port of mouthTrack() in rigpop-agents/src/render.js:
  RMS + zero-crossing count per frame over a 1024-sample window (ending at the
  frame time), rolling peak (decay 0.995, floor 0.02), smoothed level
  lv = lv*0.4 + min(1, rms/peak*0.9)*0.6, median zero-crossing of voiced
  frames (lv>0.2) -> shapes rest / A / E / O, then the renderer's 0.07 s hold
  before a shape change. Extra: 'M' (closed lips) for brief dips (lv<0.16
  lasting <=2 frames between voiced frames); M is applied after the hold.

Usage:
  python3 scripts/mouth.py voice.wav|mp3 --fps 30 [--start 0] -o mouth.json
Output: JSON list, one {"lv": float(3dp), "shape": "rest|A|E|O|M"} per frame.
Audio is decoded by ffmpeg to mono 16 kHz float32. Pure Python (no numpy).
"""
import argparse, array, json, math, subprocess, sys

SR, N = 16000, 1024


def decode(path, start=0.0):
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", path,
           "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    a = array.array("f"); a.frombytes(subprocess.run(cmd, capture_output=True, check=True).stdout)
    return a


def track(voice, fps):
    nf = math.ceil(len(voice) / SR * fps)
    peak, lv, raw = 0.05, 0.0, []
    for f in range(nf):
        st = max(0, int(f / fps * SR) - N)
        win = voice[st:st + N]
        s2 = sum(x * x for x in win)
        zc, prev = 0, 0.0
        for x in win:
            if (x >= 0) != (prev >= 0): zc += 1
            prev = x
        rms = math.sqrt(s2 / N)  # missing samples count as 0, like the JS
        peak = max(rms, peak * 0.995, 0.02)
        lv = lv * 0.4 + min(1.0, rms / peak * 0.9) * 0.6
        raw.append((lv, zc))
    voiced = sorted(z for l, z in raw if l > 0.2)
    med = voiced[len(voiced) // 2] if voiced else 40
    shapes = []
    for l, z in raw:
        s = "rest"
        if l >= 0.16:
            if z > med * 1.35 and l < 0.6: s = "E"
            elif z < med * 0.75 and 0.25 < l < 0.6: s = "O"
            else: s = "A" if l > 0.38 else "E"
        shapes.append(s)
    # renderer hold: only switch shape if >0.07 s since the last switch
    held, cur, t0 = [], "rest", -1.0
    for f, s in enumerate(shapes):
        t = f / fps
        if s != cur and t - t0 > 0.07: cur, t0 = s, t
        held.append(cur)
    # brief dips (<=2 frames of lv<0.16) between voiced frames -> closed lips
    f = 0
    while f < nf:
        if raw[f][0] < 0.16:
            e = f
            while e < nf and raw[e][0] < 0.16: e += 1
            if 0 < f and e < nf and e - f <= 2:
                for k in range(f, e): held[k] = "M"
            f = e
        else:
            f += 1
    return [{"lv": round(l, 3), "shape": s} for (l, _), s in zip(raw, held)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("audio"); ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--start", type=float, default=0.0); ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    res = track(decode(a.audio, a.start), a.fps)
    with open(a.out, "w") as fh: json.dump(res, fh)
    dist = {}
    for r in res: dist[r["shape"]] = dist.get(r["shape"], 0) + 1
    print(f"{len(res)} frames -> {a.out}  {dist}", file=sys.stderr)


if __name__ == "__main__":
    main()
