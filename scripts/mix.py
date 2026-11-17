"""Mix VO (placed at each scene's VO start) + ducked music, loudness -16 LUFS -> final_audio.wav.
Optional sfx: project.json "sfx": [{"file":"sfx/whoosh.wav","at":12.3,"gain":0.6}]. Usage: python3 scripts/mix.py <project-dir>"""
import json, os, sys, subprocess, tempfile, shutil
d = os.path.abspath(sys.argv[1]); P = json.load(open(os.path.join(d, 'project.json'))); T = json.load(open(os.path.join(d, 'timing.json')))
ins, fl, labs = [], [], []
for i, s in enumerate(T['scenes']):
    f = os.path.join(d, 'vo', f's{i:02d}.wav')
    if s['vo'] and os.path.exists(f):
        ms = int(round((s['t'] + s['off']) * 1000)); fl.append(f'[{len(ins)}]adelay={ms}|{ms}[v{len(ins)}]'); labs.append(f'[v{len(ins)}]'); ins.append(f)
for k, x in enumerate(P.get('sfx', [])):
    ms = int(x['at'] * 1000); fl.append(f"[{len(ins)}]adelay={ms}|{ms},volume={x.get('gain', .6)}[v{len(ins)}]"); labs.append(f'[v{len(ins)}]'); ins.append(os.path.join(d, x['file']))
mi = len(ins); ins.append(os.path.join(d, 'music.wav')); mg = P.get('music_gain', .55)
if not labs:
    fl.append(f'[{mi}]volume={mg},loudnorm=I=-16:TP=-1.5[out]')
else:
  fl.append(f"{''.join(labs)}amix=inputs={len(labs)}:normalize=0[vo]"); fl.append('[vo]asplit[vo1][vo2]')
  fl.append(f'[{mi}]volume={mg}[m]'); fl.append('[m][vo1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md]')
  fl.append('[vo2][md]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5[out]')
tmp = os.path.join(tempfile.gettempdir(), 'mix_out.wav')
cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + sum([['-i', f] for f in ins], []) + ['-filter_complex', ';'.join(fl), '-map', '[out]', '-ar', '44100', '-ac', '2', '-t', str(T['duration']), tmp]
subprocess.run(cmd, check=True); shutil.copy(tmp, os.path.join(d, 'final_audio.wav')); print('final_audio.wav', T['duration'], 's')
