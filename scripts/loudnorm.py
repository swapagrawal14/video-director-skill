#!/usr/bin/env python3
"""Two-pass (linear) EBU R128 loudness normalisation.
Usage: python3 scripts/loudnorm.py in.wav out.wav [-14] [-1.0]
  -14 LUFS / -1 dBTP for YouTube/Shorts/Reels, -16 LUFS / -1.5 dBTP for podcasts/Spotify."""
import json, re, subprocess, sys
src, dst = sys.argv[1], sys.argv[2]
I = float(sys.argv[3]) if len(sys.argv) > 3 else -14.0
TP = float(sys.argv[4]) if len(sys.argv) > 4 else -1.0
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
