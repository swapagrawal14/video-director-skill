"""Free TTS for a whole project (no API key): one vo/sNN.wav (+ vo/sNN.words.json word timings) per scene with a 'vo'.
Engines, tried in order unless --engine given:
  edge   - Microsoft Edge neural voices, needs internet, exact word timings (pip install edge-tts). Unofficial service.
  piper  - fully offline, GPL-3.0 package, per-voice licences (pip install piper-tts; --voice path/to/voice.onnx).
  kokoro - offline Apache-2.0 82M model (pip install kokoro soundfile); Hindi voices hf_alpha, hf_beta, hm_omega, hm_psi.
Offline engines give no word timings: run scripts/words_project.py afterwards (Whisper alignment).
Usage: python3 scripts/tts_free.py <project-dir> [--engine edge|piper|kokoro] [--voice hi-IN-SwaraNeural] [--rate +0%]
Hindi/Hinglish: hi-IN-SwaraNeural (F), hi-IN-MadhurNeural (M); Indian English: en-IN-NeerjaNeural, en-IN-PrabhatNeural."""
import argparse, json, os, subprocess, sys, asyncio, shutil, tempfile
ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--engine'); ap.add_argument('--voice'); ap.add_argument('--rate', default='+0%')
A = ap.parse_args(); d = A.dir; P = json.load(open(os.path.join(d, 'project.json'))); os.makedirs(os.path.join(d, 'vo'), exist_ok=True)
def to_wav(src, dst): subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-ar', '48000', '-ac', '1', dst], check=True)
def edge(text, wav, words):
    import edge_tts
    if os.environ.get('EDGE_TTS_KEEP_PROXY') is None:   # some sandbox proxies break the websocket; set EDGE_TTS_KEEP_PROXY=1 to keep
        for k in [k for k in os.environ if k.lower() in ('https_proxy', 'http_proxy', 'all_proxy')]: os.environ.pop(k)
    async def go():
        c = edge_tts.Communicate(text, A.voice or 'hi-IN-SwaraNeural', rate=A.rate, boundary='WordBoundary'); W = []
        mp3 = wav + '.mp3'
        with open(mp3, 'wb') as f:
            async for ch in c.stream():
                if ch['type'] == 'audio': f.write(ch['data'])
                elif ch['type'] == 'WordBoundary':
                    s = ch['offset'] / 1e7; W.append({'word': ch['text'], 'start': round(s, 3), 'end': round(s + ch['duration'] / 1e7, 3)})
        to_wav(mp3, wav); os.remove(mp3); json.dump(W, open(words, 'w'), ensure_ascii=False)
    asyncio.run(go())
def piper(text, wav, words):
    if not A.voice: raise RuntimeError('piper needs --voice path/to/voice.onnx (e.g. hi_IN-pratham-medium.onnx)')
    tmp = wav + '.raw.wav'; subprocess.run(['piper', '--model', A.voice, '--output_file', tmp], input=text, text=True, check=True); to_wav(tmp, wav); os.remove(tmp)
def kokoro(text, wav, words):
    from kokoro import KPipeline; import soundfile as sf, numpy as np
    v = A.voice or 'hf_alpha'; pl = KPipeline(lang_code={'h': 'h', 'a': 'a', 'b': 'b'}.get(v[0], 'a'))
    audio = np.concatenate([a for _, _, a in pl(text, voice=v)]); tmp = wav + '.raw.wav'; sf.write(tmp, audio, 24000); to_wav(tmp, wav); os.remove(tmp)
E = {'edge': edge, 'piper': piper, 'kokoro': kokoro}; order = [A.engine] if A.engine else ['edge', 'kokoro', 'piper']
for i, s in enumerate(P['scenes']):
    if not s.get('vo'): continue
    wav = os.path.join(d, 'vo', f's{i:02d}.wav'); words = os.path.join(d, 'vo', f's{i:02d}.words.json')
    if os.path.exists(wav): print('skip', wav); continue          # cache: never re-synthesise (or re-bill) finished scenes
    for e in order:
        try: E[e](s['vo'], wav, words); print(f's{i:02d} via {e}'); break
        except Exception as ex: print(f's{i:02d} {e} failed: {str(ex)[:120]}')
    else: sys.exit(f'no TTS engine worked for scene {i}')
