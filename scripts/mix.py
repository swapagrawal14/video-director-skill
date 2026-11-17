"""Mix VO (placed at each scene's VO start) + ducked music + SFX -> final_audio.wav (48 kHz stereo, two-pass loudness).
Targets: YouTube/Shorts/Reels -14 LUFS, true peak -1 dBTP (project.json "lufs": -14). Podcasts: -16.
SFX: project.json "sfx": [{"file":"sfx/stinger.wav","at":12.3,"gain":0.8}]  ("scene": k + "at" = seconds into scene k also works)
Silence-before-scare: "mute": [{"from":41.2,"to":42.0}] mutes music (not VO/SFX) in that window, for horror hits.
Every VO clip gets 30 ms fades so cuts never click. Usage: python3 scripts/mix.py <project-dir>"""
import json, os, sys, subprocess, tempfile, shutil
here = os.path.dirname(os.path.abspath(__file__))
d = os.path.abspath(sys.argv[1]); P = json.load(open(os.path.join(d, 'project.json'))); T = json.load(open(os.path.join(d, 'timing.json')))
lufs = P.get('lufs', -14); D = T['duration']
ins, fl, labs = [], [], []
for i, s in enumerate(T['scenes']):
    f = os.path.join(d, 'vo', f's{i:02d}.wav')
    if s['vo'] and os.path.exists(f):
        ms = int(round((s['t'] + s['off']) * 1000)); n = len(ins)
        fl.append(f"[{n}]aresample=48000,afade=t=in:d=0.03,areverse,afade=t=in:d=0.03,areverse,adelay={ms}|{ms}[v{n}]"); labs.append(f'[v{n}]'); ins.append(f)
fx = []
for x in P.get('sfx', []):
    at = x['at'] + (T['scenes'][x['scene']]['t'] if 'scene' in x else 0); ms = int(at * 1000); n = len(ins)
    fl.append(f"[{n}]aresample=48000,adelay={ms}|{ms},volume={x.get('gain', .6)}[x{n}]"); fx.append(f'[x{n}]'); ins.append(os.path.join(d, x['file']))
mi = len(ins); ins.append(os.path.join(d, 'music.wav')); mg = P.get('music_gain', .55)
mute = ''.join(f",volume=enable='between(t,{m['from']},{m['to']})':volume=0" for m in P.get('mute', []))
fl.append(f'[{mi}]aresample=48000,volume={mg}{mute}[m]')
if labs:
    fl.append(f"{''.join(labs)}amix=inputs={len(labs)}:normalize=0[vo]"); fl.append('[vo]asplit[vo1][vo2]')
    fl.append('[m][vo1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md]'); bus = ['[vo2]', '[md]']
else: bus = ['[m]']
bus += fx
fl.append(f"{''.join(bus)}amix=inputs={len(bus)}:normalize=0,alimiter=limit=0.95[out]" if len(bus) > 1 else f"{bus[0]}alimiter=limit=0.95[out]")
pre = os.path.join(tempfile.gettempdir(), 'mix_pre.wav'); outp = os.path.join(tempfile.gettempdir(), 'mix_out.wav')
cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + sum([['-i', f] for f in ins], []) + ['-filter_complex', ';'.join(fl), '-map', '[out]', '-ar', '48000', '-ac', '2', '-t', str(D), pre]
subprocess.run(cmd, check=True)
subprocess.run([sys.executable, os.path.join(here, 'loudnorm.py'), pre, outp, str(lufs), '-1.0'], check=True, stdout=subprocess.DEVNULL)
shutil.copy(outp, os.path.join(d, 'final_audio.wav')); print(f'final_audio.wav {D}s, {lufs} LUFS / -1 dBTP, 48 kHz')
