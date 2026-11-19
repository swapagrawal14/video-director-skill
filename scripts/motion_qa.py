#!/usr/bin/env python3
"""Character motion QA: consecutive-frame strips you MUST look at before delivering any character video.
Usage: python3 scripts/motion_qa.py out.mp4 --at 0.6,4.6,11 --len 2.4 --fps 10 --crop W:H:X:Y -o qa/
Writes one strip per start time (rows of consecutive frames). Look for, and fix before shipping:
  - expression changing on its own between frames (a new drawing with a different face)  -> use one shared head (headrig3d.js)
  - pose cuts faster than ~1 s, or a key that shows for under 4 frames                    -> longer holds, one gesture per beat
  - lips that flicker, or a mouth that does not match the art                              -> painted mouth sprites of THAT head, visemes held >= 3 frames
  - head jumping position/scale on a body cut, gaps or double necks                        -> fix neck anchors in rig.json
  - jitter, wobble, sliding feet                                                           -> remove the motion, never add more"""
import argparse, subprocess, os
ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--at', default='0'); ap.add_argument('--len', type=float, default=2.4)
ap.add_argument('--fps', type=float, default=10); ap.add_argument('--crop', default=''); ap.add_argument('-o', default='qa')
a = ap.parse_args(); os.makedirs(a.o, exist_ok=True)
n = int(a.len * a.fps); cols = min(12, n); rows = (n + cols - 1) // cols
for s in a.at.split(','):
    vf = f"fps={a.fps}," + (f"crop={a.crop}," if a.crop else '') + f"scale=120:-1,tile={cols}x{rows}"
    out = f"{a.o}/strip_{float(s):06.2f}.jpg"
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', s, '-t', str(a.len), '-i', a.video, '-vf', vf, '-frames:v', '1', out], check=True)
    print(out)
