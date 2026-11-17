"""Scene timing from VO durations -> timing.json (single source of truth for picture AND audio).
Each scene: lead-in (off) + VO + hold (scene 'hold' sec, default 0.6) ; first scene lead-in = project 'intro_lead' (default 0.3 s: hook in the first second), last gets +3s tail.
Scenes without VO use their 'secs'. Usage: python3 scripts/build_timing.py <project-dir>"""
import json, os, sys, subprocess, math
d = sys.argv[1]; P = json.load(open(os.path.join(d, 'project.json'))); fps = P.get('fps', 24)
def dur(f):
    if not os.path.exists(f): return 0.0
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.strip()
    return float(r or 0)
t = 0.0; out = []; n = len(P['scenes'])
for i, s in enumerate(P['scenes']):
    vo = round(dur(os.path.join(d, 'vo', f's{i:02d}.wav')), 3)
    off = s.get('lead', P.get('intro_lead', 0.3)) if i == 0 else s.get('lead', 0.5)
    dd = (off + vo + s.get('hold', 0.6) + (P.get('outro_tail', 3.0) if i == n - 1 else 0)) if vo else s.get('secs', 4.0)
    dd = max(dd, s.get('min_secs', 0))
    out.append({'t': round(t, 3), 'd': round(dd, 3), 'off': off, 'vo': vo}); t += dd
T = {'fps': fps, 'duration': round(t, 3), 'frames': math.ceil(t * fps), 'scenes': out}
json.dump(T, open(os.path.join(d, 'timing.json'), 'w'), indent=1)
print(f"duration {t:.2f}s, {T['frames']} frames @ {fps}fps, {n} scenes")

# optional: snap scene cuts to music beats (project.json "beat_snap": true; run scripts/beats.py music.wav beats.json first).
# Each cut moves <=0.25 s to the nearest beat; the scene's END stays put, so total length and later scenes are unchanged.
bj = os.path.join(d, 'beats.json')
if P.get('beat_snap') and os.path.exists(bj):
    beats = json.load(open(bj))['beats']; moved = 0
    for k in range(1, len(out)):
        c = out[k]['t']; b = min(beats, key=lambda x: abs(x - c)) if beats else c
        delta = round(b - c, 3)
        if delta and abs(delta) <= 0.25 and out[k-1]['d'] + delta > 1 and out[k]['d'] - delta > 1:
            out[k-1]['d'] = round(out[k-1]['d'] + delta, 3); out[k]['t'] = round(b, 3); out[k]['d'] = round(out[k]['d'] - delta, 3); moved += 1
    json.dump(T, open(os.path.join(d, 'timing.json'), 'w'), indent=1); print(f'beat-snapped {moved} cuts')
