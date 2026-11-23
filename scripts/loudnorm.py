#!/usr/bin/env python3
"""Two-pass (linear) EBU R128 loudness normalisation.
Usage: python3 scripts/loudnorm.py in.wav out.wav [-14] [-1.0]
  -14 LUFS / -1 dBTP for YouTube/Shorts/Reels, -16 LUFS / -1.5 dBTP for podcasts/Spotify.
  --tame : compress + limit BEFORE normalising. Use it for SFX-only / music-only mixes with big transients
           (thunder, stingers, boings): linear loudnorm cannot raise them to -14 LUFS without the true peak
           blowing past -1 dBTP, and qa.py then FAILS. With --tame they pass in one go."""
import json, os, re, subprocess, sys, tempfile
TAME = '--tame' in sys.argv
argv = [a for a in sys.argv if a != '--tame']
src, dst = argv[1], argv[2]
I = float(argv[3]) if len(argv) > 3 else -14.0
TP = float(argv[4]) if len(argv) > 4 else -1.0
if TAME:
    tmp = os.path.join(tempfile.gettempdir(), 'loudnorm_tamed.wav')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-af',
                    'acompressor=threshold=-24dB:ratio=4:attack=5:release=120:makeup=6,alimiter=limit=0.6:level=false',
                    tmp], check=True)
    src = tmp
    TP = min(TP, -1.5)   # AAC re-encode adds ~0.5 dB of inter-sample peak
LRA = 11
p1 = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', src, '-af',
                     f'loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json', '-f', 'null', '-'],
                    capture_output=True, text=True).stderr
m = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', p1, re.S).group(0))
af = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
      f"linear=true:print_format=summary")
p2 = subprocess.run(['ffmpeg', '-y', '-hide_banner', '-nostats', '-i', src, '-af', af, '-ar', '48000', dst],
                    capture_output=True, text=True).stderr
print(p2[p2.find('Input Integrated'):].strip())
