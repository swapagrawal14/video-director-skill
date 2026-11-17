"""Project-wide word timings -> words.json on the FINAL timeline (input for captions.py, chapters.py, qa).
Per scene it uses, in order: vo/sNN.words.json (TTS-native timings: tts_free.py edge, or your own TTS) ->
faster-whisper on vo/sNN.wav (scripts/words_whisper.py). Whisper's TEXT is never shown: when the scene's script
has the same word count, the script's words are used with Whisper's times (fixes Hindi->Urdu-script and mishearings).
Usage: python3 scripts/words_project.py <project-dir> [--model small] [--lang hi|en|auto]"""
import argparse, json, os, subprocess, sys, re
ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--model', default='small'); ap.add_argument('--lang', default='auto')
A = ap.parse_args(); d = A.dir; here = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(d, 'project.json'))); T = json.load(open(os.path.join(d, 'timing.json'))); out = []
for i, (s, ts) in enumerate(zip(P['scenes'], T['scenes'])):
    wav = os.path.join(d, 'vo', f's{i:02d}.wav'); wj = os.path.join(d, 'vo', f's{i:02d}.words.json')
    if not ts['vo'] or not os.path.exists(wav): continue
    if not os.path.exists(wj):
        subprocess.run([sys.executable, os.path.join(here, 'words_whisper.py'), wav, wj, A.model, A.lang, (s.get('sub') or '')[:200]], check=True)
        W = json.load(open(wj)); script = (s.get('cap') or s.get('sub') or '').replace('|', ' ').split()
        if len(script) == len(W):
            for w, txt in zip(W, script): w['word'] = txt
        else: print(f'  s{i:02d}: script has {len(script)} words, whisper {len(W)}; keeping whisper text, CHECK it'); json.dump(W, open(wj, 'w'), ensure_ascii=False)
    off = ts['t'] + ts['off']
    for w in json.load(open(wj)): out.append(dict(w, start=round(w['start'] + off, 3), end=round(w['end'] + off, 3)))
json.dump(out, open(os.path.join(d, 'words.json'), 'w'), ensure_ascii=False, indent=0)
low = [w['word'] for w in out if w.get('p', 1) < 0.5]
print(f'words.json: {len(out)} words' + (f'; low-confidence (check): {low[:20]}' if low else ''))
