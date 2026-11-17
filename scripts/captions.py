#!/usr/bin/env python3
"""Word timestamps JSON -> TikTok-style ASS captions (karaoke sweep OR pop-in active word).
words.json: [{"word":"Hello","start":0.00,"end":0.34}, ...]  (faster-whisper / stable-ts / edge-tts / Cartesia timestamps)
Usage: python3 scripts/captions.py words.json out.ass --w 1080 --h 1920 --style pop|karaoke --font "Baloo 2" --max-words 3
Burn:  ffmpeg -i in.mp4 -vf "ass=out.ass:fontsdir=fonts" -c:v libx264 -crf 18 -c:a copy out.mp4"""
import json, argparse
ap = argparse.ArgumentParser()
ap.add_argument('words'); ap.add_argument('out')
ap.add_argument('--w', type=int, default=1920); ap.add_argument('--h', type=int, default=1080)
ap.add_argument('--style', default='pop'); ap.add_argument('--font', default='Baloo 2')
ap.add_argument('--max-words', type=int, default=3); ap.add_argument('--max-gap', type=float, default=0.6)
ap.add_argument('--upper', action='store_true')
a = ap.parse_args()
W = json.load(open(a.words))
vertical = a.h > a.w
fs = int(a.h * (0.055 if vertical else 0.065))        # ~105 px on 1920 tall, ~70 px on 1080
mv = int(a.h * (0.30 if vertical else 0.08))          # vertical: keep above Shorts/Reels UI (bottom ~25-30%)
ol = max(3, fs // 14)
def ts(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'
# ASS colours are &HAABBGGRR
WHITE, YELLOW, BLACK, SHADOW = '&H00FFFFFF', '&H0000E5FF', '&H00000000', '&H80000000'
hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {a.w}
PlayResY: {a.h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{a.font},{fs},{YELLOW},{WHITE},{BLACK},{SHADOW},1,0,0,0,100,100,0,0,1,{ol},{max(2, ol // 2)},2,60,60,{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
# group words into short lines: break on max words, long pauses, or sentence punctuation
groups, cur = [], []
for w in W:
    w = dict(w, word=w['word'].strip())
    if cur and (len(cur) >= a.max_words or w['start'] - cur[-1]['end'] > a.max_gap or cur[-1]['word'][-1:] in '.?!,।'):
        groups.append(cur); cur = []
    cur.append(w)
if cur: groups.append(cur)
ev = []
for gi, g in enumerate(groups):
    g_end = g[-1]['end'] + 0.15
    if gi + 1 < len(groups): g_end = min(g_end, groups[gi + 1][0]['start'])   # never overlap next line
    txt = lambda w: (w['word'].upper() if a.upper else w['word'])
    if a.style == 'karaoke':      # one event per line, \kf sweep (SecondaryColour -> PrimaryColour)
        parts, t = [], g[0]['start']
        for w in g:
            if w['start'] > t: parts.append(f"{{\\k{int(round((w['start'] - t) * 100))}}}"); t = w['start']
            parts.append(f"{{\\kf{max(1, int(round((w['end'] - t) * 100)))}}}{txt(w)} "); t = w['end']
        ev.append(f"Dialogue: 0,{ts(g[0]['start'])},{ts(g_end)},Cap,,0,0,0,,{{\\fad(60,60)}}{''.join(parts).strip()}")
    else:                         # pop: one event per word; active word yellow + scale bounce, others white
        for i, w in enumerate(g):
            st = w['start']; en = g[i + 1]['start'] if i + 1 < len(g) else g_end
            line = []
            for j, x in enumerate(g):
                if j == i:
                    line.append(f"{{\\1c{YELLOW}\\fscx118\\fscy118\\t(0,90,\\fscx100\\fscy100)}}{txt(x)}{{\\r}}")
                else:
                    line.append(f"{{\\1c{WHITE}}}{txt(x)}")
            ev.append(f"Dialogue: 0,{ts(st)},{ts(en)},Cap,,0,0,0,,{' '.join(line)}")
open(a.out, 'w', encoding='utf-8').write(hdr + '\n'.join(ev) + '\n')
print(a.out, len(groups), 'lines', len(ev), 'events')
