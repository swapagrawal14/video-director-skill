#!/usr/bin/env python3
"""timing.json + project.json -> YouTube chapters text, MP4 chapter metadata, and SRT captions.
Usage: python3 scripts/chapters.py <project-dir> [words.json]
Writes: chapters.txt (paste into description), chapters.ffmeta (embed), captions.srt (upload as CC track).
Chapter rules (YouTube Help 9884579): first 00:00, >=3 chapters ascending, each >=10 s.
Scene titles: project.json scenes[i].chapter (preferred) else step/title/first words of sub."""
import json, os, sys, re
d = sys.argv[1]; P = json.load(open(os.path.join(d, 'project.json'))); T = json.load(open(os.path.join(d, 'timing.json')))
words = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
def name(s, i):
    for k in ('chapter', 'step', 'title'):
        if isinstance(s.get(k), str) and s[k].strip(): return s[k].strip()
    sub = (s.get('sub') or '').split('|')[0]; return ' '.join(sub.split()[:6]) or f'Part {i+1}'
# candidate chapters = scenes that declare 'chapter' (or every scene if none do)
marked = [i for i, s in enumerate(P['scenes']) if s.get('chapter')]
idx = marked or list(range(len(P['scenes'])))
ch = [(0.0 if k == 0 else T['scenes'][i]['t'], name(P['scenes'][i], i)) for k, i in enumerate(idx)]
ch[0] = (0.0, ch[0][1] if marked and marked[0] == 0 else 'Intro')
merged = []                                   # merge so every chapter >= 10 s
for t, n in ch:
    if merged and t - merged[-1][0] < 10: continue
    merged.append((t, n))
while len(merged) > 1 and T['duration'] - merged[-1][0] < 10: merged.pop()
fmt = lambda t: (f'{int(t//3600)}:{int(t%3600//60):02d}:{int(t%60):02d}' if T['duration'] >= 3600 else f'{int(t//60):02d}:{int(t%60):02d}')
ok = len(merged) >= 3
open(os.path.join(d, 'chapters.txt'), 'w').write('\n'.join(f'{fmt(t)} {n}' for t, n in merged) + '\n')
with open(os.path.join(d, 'chapters.ffmeta'), 'w') as f:
    f.write(';FFMETADATA1\ntitle=' + P.get('title', '') + '\n')
    for k, (t, n) in enumerate(merged):
        e = merged[k + 1][0] if k + 1 < len(merged) else T['duration']
        f.write(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(t*1000)}\nEND={int(e*1000)}\ntitle={n}\n')
def srt_t(t): return f'{int(t//3600):02d}:{int(t%3600//60):02d}:{int(t%60):02d},{int(round((t%1)*1000)) % 1000:03d}'
cues = []
if words:                                     # word-accurate cues: <=42 chars, <=7 s, break on pauses/punctuation
    cur = []
    for w in words:
        line = ' '.join(x['word'] for x in cur + [w])
        if cur and (len(line) > 42 or w['end'] - cur[0]['start'] > 7 or w['start'] - cur[-1]['end'] > 0.7 or cur[-1]['word'][-1:] in '.?!।'):
            cues.append((cur[0]['start'], cur[-1]['end'], ' '.join(x['word'] for x in cur))); cur = []
        cur.append(w)
    if cur: cues.append((cur[0]['start'], cur[-1]['end'], ' '.join(x['word'] for x in cur)))
else:                                         # from scene subs: spread chunks over the VO span by character count
    for s, ts in zip(P['scenes'], T['scenes']):
        chunks = [c.strip() for c in (s.get('sub') or '').split('|') if c.strip()]
        if not chunks: continue
        st = ts['t'] + ts['off']; span = ts['vo'] or ts['d'] - ts['off']; tot = sum(map(len, chunks))
        for c in chunks:
            dd = span * len(c) / tot; cues.append((st, st + dd, c)); st += dd
with open(os.path.join(d, 'captions.srt'), 'w', encoding='utf-8') as f:
    for k, (a, b, txt) in enumerate(cues, 1):
        b = min(b, cues[k][0] - 0.001) if k < len(cues) else b
        f.write(f'{k}\n{srt_t(a)} --> {srt_t(b)}\n{txt}\n\n')
print(open(os.path.join(d, 'chapters.txt')).read().strip())
print('chapters valid for YouTube' if ok else 'WARNING: <3 chapters of >=10 s; YouTube will ignore them', '|', len(cues), 'SRT cues')
