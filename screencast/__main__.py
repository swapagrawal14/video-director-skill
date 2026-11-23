"""Screencast tutorial reels, one command per stage (or `all`).

  python3 -m screencast capture <proj>          # browser steps from script.json -> capture/
  python3 -m screencast voice   <proj>          # VO per beat -> vo/sNN.wav (Cartesia if CARTESIA_VOICE_ID/voice_id set, else edge-tts)
  python3 -m screencast build   <proj>          # timeline.json + vo_full.wav + music + mix.wav (-14 LUFS, ducked)
  python3 -m screencast sfx     <proj>          # procedural SFX on cuts/clicks/typing/stickers -> mix_sfx.wav
  python3 -m screencast stills  <proj> 1 5 9    # preview frames -> <proj>/shots/  (LOOK at them)
  python3 -m screencast render  <proj> [out.mp4] [--jobs 2]   # chunked render + mux, 1080x1920
  python3 -m screencast all     <proj> [out.mp4]

<proj> holds script.json and host/ (python3 -m screencast.make_pack host ...). See docs/SCREENCAST.md.
Chromium needs its shared libs; if Playwright says a .so is missing, set LD_LIBRARY_PATH to a folder with them.
"""
import sys, os, json, subprocess, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
LEAD, GAP, OUTRO = .5, .3, 2.6


def capture(proj):
    sys.path.insert(0, ROOT)
    from screencast.capture import capture as cap
    S = json.load(open(f'{proj}/script.json'))
    r = cap(S['steps'], f'{proj}/capture', viewport=tuple(S.get('viewport', [1280, 800])), fps=S.get('capture_fps', 30), css=S.get('css'))
    json.dump(r, open(f'{proj}/capture/capture.json', 'w'), indent=1)
    marks = sum(1 for e in r['events'] if e['type'] == 'mark')
    print(f"captured {r['n_frames']} frames, {marks} marks for {len(S['beats'])} beats")


def voice(proj):
    S = json.load(open(f'{proj}/script.json')); os.makedirs(f'{proj}/vo', exist_ok=True)
    vid = os.environ.get('CARTESIA_VOICE_ID') or S.get('voice_id')
    for i, b in enumerate(S['beats']):
        out = f'{proj}/vo/s{i:02d}.wav'
        if vid:
            body = json.dumps({"model_id": S.get('tts_model', 'sonic-latest'), "transcript": b['vo'], "voice": {"mode": "id", "id": vid},
                               "language": S.get('language', 'hi'), "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100}})
            hdr = ['-H', f"X-API-Key: {os.environ['CARTESIA_API_KEY']}"] if os.environ.get('CARTESIA_API_KEY') else []
            code = subprocess.run(['curl', '-s', '-o', out, '-w', '%{http_code}', 'https://api.cartesia.ai/tts/bytes', *hdr,
                                   '-H', 'Cartesia-Version: 2024-11-13', '-H', 'Content-Type: application/json', '-d', body], capture_output=True, text=True).stdout
            print(i, code)
        else:
            mp3 = out[:-4] + '.mp3'
            subprocess.run(['edge-tts', '--voice', S.get('edge_voice', 'hi-IN-SwaraNeural'), '--text', b['vo'], '--write-media', mp3], check=True)
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', mp3, '-ar', '44100', '-ac', '1', out], check=True); print(i, 'edge')


def _read(p):
    w = wave.open(p); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if w.getnchannels() == 2: a = a.reshape(-1, 2).mean(1)
    return a, w.getframerate()


def build(proj, fps=30):
    S = json.load(open(f'{proj}/script.json')); SR = 44100
    pcm = np.zeros(SR * 600, np.float32); t = LEAD; segs = []; words = []
    for i, b in enumerate(S['beats']):
        a, sr = _read(f'{proj}/vo/s{i:02d}.wav')
        if sr != SR: raise SystemExit('VO must be 44.1 kHz')
        idx = np.nonzero(np.abs(a) > .02)[0]
        if len(idx): a = a[max(0, idx[0] - int(.03 * SR)):idx[-1] + int(.06 * SR)]
        d = len(a) / SR; pcm[int(t * SR):int(t * SR) + len(a)] += a
        ws = b.get('sub', b['vo']).split(); wt = [len(w.strip('.,!?')) + 2 + (4 if w[-1] in ',.!?' else 0) for w in ws]; c = t
        for w, k in zip(ws, wt):
            du = d * k / sum(wt); words.append({'word': w.strip('.'), 'start': round(c, 3), 'end': round(c + du * .85, 3)}); c += du
        segs.append({'i': i, 'start': round(t, 3), 'end': round(t + d, 3)}); t += d + GAP
    dur = t - GAP + .3 + OUTRO; pcm = pcm[:int(dur * SR)]
    hop = SR // fps; lv = [float(np.sqrt(np.mean(pcm[k * hop:(k + 1) * hop] ** 2))) if k * hop < len(pcm) else 0 for k in range(int(dur * fps) + 2)]
    m = max(lv) or 1; lv = [x / m for x in lv]
    w = wave.open(f'{proj}/vo_full.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
    json.dump({'duration': dur, 'fps': fps, 'segs': segs, 'words': words, 'mouth': lv}, open(f'{proj}/timeline.json', 'w'))
    md = f'{proj}/mus'; os.makedirs(md, exist_ok=True)
    json.dump({'music_mood': S.get('music', 'upbeat')}, open(f'{md}/project.json', 'w')); json.dump({'duration': dur}, open(f'{md}/timing.json', 'w'))
    subprocess.run([sys.executable, f'{ROOT}/scripts/music.py', md, S.get('music', 'upbeat')], check=True)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', f'{proj}/vo_full.wav', '-i', f'{md}/music.wav', '-filter_complex',
                    '[0:a]aresample=48000,asplit=2[vo][sc];[1:a]aresample=48000,volume=0.33[m];[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[md];'
                    '[vo][md]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[out]', '-map', '[out]', '-ac', '2', f'{proj}/mix.wav'], check=True)
    print(f'timeline {dur:.1f}s, {len(segs)} beats')


def stills(proj, ts):
    sys.path.insert(0, ROOT); from screencast.compose import render as r
    r(proj, 0, 0, f'{proj}/shots', stills=ts); print('stills ->', f'{proj}/shots')


def render(proj, out=None, jobs=2):
    sys.path.insert(0, ROOT); from screencast.compose import total_frames
    audio = f'{proj}/mix_sfx.wav' if os.path.exists(f'{proj}/mix_sfx.wav') else f'{proj}/mix.wav'
    out = out or f'{proj}/final.mp4'; n = total_frames(proj); step = -(-n // jobs); tmp = f'{proj}/chunks'; os.makedirs(tmp, exist_ok=True)
    code = "import sys; sys.path.insert(0, %r); from screencast.compose import render; render(%r, %d, %d, %r)"
    ps = [subprocess.Popen([sys.executable, '-c', code % (ROOT, proj, i * step, min(n, (i + 1) * step), f'{tmp}/c{i}.mp4')]) for i in range(jobs)]
    if any(p.wait() for p in ps): raise SystemExit('a render chunk failed; re-run')
    open(f'{tmp}/list.txt', 'w').write(''.join(f"file 'c{i}.mp4'\n" for i in range(jobs)))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', f'{tmp}/list.txt', '-i', audio,
                    '-vf', 'scale=1080:1920:flags=lanczos', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out], check=True)
    print('wrote', out)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    cmd, proj = sys.argv[1], os.path.abspath(sys.argv[2]); rest = sys.argv[3:]
    jobs = 2
    if '--jobs' in rest: i = rest.index('--jobs'); jobs = int(rest[i + 1]); rest = rest[:i] + rest[i + 2:]
    if cmd == 'capture': capture(proj)
    elif cmd == 'voice': voice(proj)
    elif cmd == 'build': build(proj)
    elif cmd == 'sfx':
        sys.path.insert(0, ROOT); from screencast.sfx import mix; mix(proj)
    elif cmd == 'stills': stills(proj, rest or ['1', '5', '9'])
    elif cmd == 'render': render(proj, rest[0] if rest else None, jobs)
    elif cmd == 'all':
        capture(proj); voice(proj); build(proj)
        sys.path.insert(0, ROOT); from screencast.sfx import mix; mix(proj)
        render(proj, rest[0] if rest else None, jobs)
    else: sys.exit(__doc__)
