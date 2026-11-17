#!/usr/bin/env python3
"""Automated QA gate for a finished MP4 (+ optional .ass). Exit code 1 if any FAIL.
Usage: python3 scripts/qa.py final.mp4 [captions.ass] [--lufs -14] [--allow-black-intro 0.5]
Checks: black frames, frozen frames, silence gaps, clipping/true-peak, integrated loudness,
duration A/V mismatch, faststart, caption overlap/too-fast/too-long lines."""
import json, re, subprocess, sys
args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = dict(zip(sys.argv[1::1], sys.argv[2::1]))
mp4 = args[0]; ass = args[1] if len(args) > 1 and args[1].endswith('.ass') else None
target = float(opt.get('--lufs', -14)); allow_black = float(opt.get('--allow-black-intro', 0.5))
fails, warns = [], []
def run(cmd): return subprocess.run(cmd, capture_output=True, text=True).stderr
probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', mp4],
                                  capture_output=True, text=True).stdout)
dur = float(probe['format']['duration'])
v = next(s for s in probe['streams'] if s['codec_type'] == 'video')
a = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
if a is None: fails.append('no audio stream')
else:
    vd, ad = float(v.get('duration', dur)), float(a.get('duration', dur))
    if abs(vd - ad) > 0.1: fails.append(f'A/V duration mismatch video={vd:.2f}s audio={ad:.2f}s')
    if int(a.get('sample_rate', 0)) != 48000: warns.append(f"audio sample rate {a.get('sample_rate')} (48000 recommended)")
if v.get('pix_fmt') != 'yuv420p': fails.append(f"pix_fmt {v.get('pix_fmt')} (must be yuv420p for phones/social)")
# faststart: moov before mdat
head = open(mp4, 'rb').read(1 << 20)
mi, di = head.find(b'moov'), head.find(b'mdat')
if mi == -1 or (di != -1 and mi > di): warns.append('moov atom not at front (add -movflags +faststart)')
# video: black + freeze
log = run(['ffmpeg', '-hide_banner', '-nostats', '-i', mp4, '-vf',
           'blackdetect=d=0.25:pix_th=0.10,freezedetect=n=-60dB:d=1.5', '-an', '-f', 'null', '-'])
for s, e in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', log):
    s, e = float(s), float(e)
    if s < 0.01 and e <= allow_black: continue                # intentional fade-in
    if e >= dur - 1.0: continue                               # fade-out at end
    (warns if e - s < 0.6 else fails).append(f'black frames {s:.2f}-{e:.2f}s')
fs = [float(x) for x in re.findall(r'freeze_start: ([\d.]+)', log)]
fe = [float(x) for x in re.findall(r'freeze_end: ([\d.]+)', log)]
for i, s in enumerate(fs):
    e = fe[i] if i < len(fe) else dur
    warns.append(f'frozen picture {s:.2f}-{e:.2f}s (fine for a held title; bad mid-scene)')
# audio: loudness, true peak, clipping, silence
if a:
    ln = run(['ffmpeg', '-hide_banner', '-nostats', '-i', mp4, '-af',
              'ebur128=peak=true,astats=measure_perchannel=none:measure_overall=Peak_level+Flat_factor,silencedetect=n=-50dB:d=2',
              '-vn', '-f', 'null', '-'])
    I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', ln)[-1])
    tp = float(re.findall(r'Peak:\s+(-?[\d.inf]+) dBFS', ln)[-1])
    if abs(I - target) > 1.0: fails.append(f'integrated loudness {I} LUFS (target {target}±1)')
    if tp > -1.0: fails.append(f'true peak {tp} dBTP (> -1.0, will clip after AAC/Opus transcode)')
    ff = re.findall(r'Flat factor: ([\d.]+)', ln)
    if ff and float(ff[-1]) > 0: fails.append(f'flat factor {ff[-1]} > 0 (hard clipping present)')
    for s, d in re.findall(r'silence_start: ([\d.]+)[\s\S]*?silence_duration: ([\d.]+)', ln):
        warns.append(f'silence {float(s):.2f}s for {float(d):.2f}s (intentional? horror beats ok)')
# captions
if ass:
    def t(x): h, m, s = x.split(':'); return int(h) * 3600 + int(m) * 60 + float(s)
    ev = []
    for line in open(ass, encoding='utf-8'):
        if line.startswith('Dialogue:'):
            p = line.split(',', 9)
            if p[0].strip().endswith('0') or True:
                txt = re.sub(r'\{[^}]*\}', '', p[9]).strip()
                ev.append((t(p[1]), t(p[2]), int(p[0].split(':')[1]), txt))
    ev.sort()
    for i in range(1, len(ev)):
        if ev[i][2] == ev[i - 1][2] and ev[i][0] < ev[i - 1][1] - 0.01:
            fails.append(f'caption overlap at {ev[i][0]:.2f}s: "{ev[i-1][3][:30]}" / "{ev[i][3][:30]}"')
    lines = []                                 # merge per-word "pop" events showing the same line
    for s, e, l, txt in ev:
        if lines and lines[-1][3] == txt and abs(s - lines[-1][1]) < 0.02: lines[-1] = (lines[-1][0], e, l, txt)
        else: lines.append((s, e, l, txt))
    for s, e, _, txt in lines:
        if e > dur + 0.05: fails.append(f'caption past end of video at {s:.2f}s')
        if len(txt) > 42: warns.append(f'caption line {len(txt)} chars at {s:.2f}s (>42)')
        if e - s > 0 and len(txt) / (e - s) > 25 and len(txt) > 12: warns.append(f'caption {len(txt)/(e-s):.0f} chars/s at {s:.2f}s (>25 hard to read)')
print(f'{mp4}: {dur:.2f}s {v["width"]}x{v["height"]} {v.get("r_frame_rate")}')
for w in warns: print('WARN', w)
for f in fails: print('FAIL', f)
print('QA', 'FAILED' if fails else 'PASSED'); sys.exit(1 if fails else 0)
