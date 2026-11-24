#!/usr/bin/env python3
"""Word timestamps JSON -> burned-caption ASS file, in one of several caption PRESETS (docs/TEXT_STYLES.md).
words.json: [{"word":"Hello","start":0.00,"end":0.34}, ...]  (faster-whisper / stable-ts / edge-tts / Cartesia timestamps)
            or an align.json from scripts/align.py ({"words": [{"w","start","end"}]}, forced-aligned: tightest timing)

There is NO default look: every video picks its own caption preset (docs/FRESH_LOOK.md). Choose with
  --preset NAME          one of: pop-word karaoke-sweep lower-third-ticker marker-highlight outline-bold
                         typewriter-reveal stacked-bounce minimal-serif chalk-hand pill   (--list prints them)
  --project DIR          reads look.captions_preset, look.palette and look.captions_position from DIR/project.json
  --style pop|karaoke    the original yellow/white Baloo look, byte-for-byte unchanged (legacy; --style NAME also
                         accepts a preset name)
Colours come from --palette "#0e1621,#7fd1ff,#f4f1ea,#ff8a3d" or the project's look.palette (darkest = outline/box,
lightest = text, most saturated = accent). --position bottom|center|top|lower-third overrides the preset's spot.

Usage: python3 scripts/captions.py words.json out.ass --w 1080 --h 1920 --preset chalk-hand --palette "#2f3e46,#f1faee,#e76f51"
       python3 scripts/captions.py words.json out.ass --w 1080 --h 1920 --project projects/my-video
Burn:  ffmpeg -i in.mp4 -vf "ass=out.ass:fontsdir=fonts" -c:v libx264 -crf 18 -c:a copy out.mp4"""
import json, argparse, os, sys, colorsys, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from text_presets import CAPTION_PRESETS, LEGACY_STYLES, CAPTION_POSITIONS, norm  # noqa: E402

DOC = 'docs/TEXT_STYLES.md'


def ts(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'


# ASS colours are &HAABBGGRR
def bgr(h, alpha=0):
    h = h.lstrip('#').upper(); return f'&H{alpha:02X}' + h[4:6] + h[2:4] + h[0:2]


def load_words(path):
    W = json.load(open(path, encoding='utf-8'))
    if isinstance(W, dict): W = W['words']                     # align.json (scripts/align.py): forced-aligned word times
    return [dict(w, word=w.get('word', w.get('w', ''))) for w in W]


def group_words(W, max_words, max_gap, skip_empty=False):
    """short lines: break on max words, long pauses, or sentence punctuation"""
    groups, cur = [], []
    for w in W:
        w = dict(w, word=w['word'].strip())
        if skip_empty and not w['word']: continue
        if cur and (len(cur) >= max_words or w['start'] - cur[-1]['end'] > max_gap or cur[-1]['word'][-1:] in '.?!,।'):
            groups.append(cur); cur = []
        cur.append(w)
    if cur: groups.append(cur)
    return groups


HDR_FMT = 'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, ' \
          'Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, ' \
          'MarginR, MarginV, Encoding'


def header(w, h, style_lines):
    return (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
            f"[V4+ Styles]\n{HDR_FMT}\n" + '\n'.join(style_lines) +
            "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")


# ---------------------------------------------------------------- legacy --style pop|karaoke (unchanged output)
def legacy(a, W):
    vertical = a.h > a.w
    fs = int(a.h * (0.055 if vertical else 0.065))        # ~105 px on 1920 tall, ~70 px on 1080
    mv = int(a.h * (0.30 if vertical else 0.08))          # vertical: keep above Shorts/Reels UI (bottom ~25-30%)
    ol = max(3, fs // 14)
    WHITE, YELLOW, BLACK, SHADOW = bgr((a.idle or 'FFFFFF').upper()), bgr((a.active or 'FFE500').upper()), '&H00000000', '&H80000000'
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {a.w}
PlayResY: {a.h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{a.font or 'Baloo 2'},{fs},{YELLOW},{WHITE},{BLACK},{SHADOW},1,0,0,0,100,100,0,0,1,{ol},{max(2, ol // 2)},2,60,60,{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    groups = group_words(W, a.max_words or 3, a.max_gap)
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
    return hdr + '\n'.join(ev) + '\n', len(groups), len(ev)


# ---------------------------------------------------------------- palette -> colour roles
FALLBACK = ['#111418', '#F5F3EE', '#FF7A45', '#5BC0EB']


def _rgb(h):
    h = h.lstrip('#'); return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def roles(palette):
    """dark (outline/box), light (text), accent, accent2 from a 3-5 hex palette."""
    pal = [p if p.startswith('#') else '#' + p for p in (palette or FALLBACK)]
    lum = lambda h: sum(c * k for c, k in zip(_rgb(h), (.2126, .7152, .0722)))
    sat = lambda h: colorsys.rgb_to_hsv(*_rgb(h))[1] * (0.4 + colorsys.rgb_to_hsv(*_rgb(h))[2])
    dark = min(pal, key=lum); light = max(pal, key=lum)
    rest = sorted([p for p in pal if p not in (dark, light)], key=sat, reverse=True)
    accent = rest[0] if rest else light
    accent2 = rest[1] if len(rest) > 1 else accent
    if lum(dark) > 0.35: dark = '#111418'          # captions need a dark edge to read on video
    if lum(light) < 0.55: light = '#F5F3EE'
    return dict(dark=dark, light=light, accent=accent, accent2=accent2)


# ---------------------------------------------------------------- presets
# font, size factor, bold, default position, column (1 left / 2 centre), max words per line, upper-case
SPEC = {
    'pop-word':           dict(font='Baloo 2', k=1.00, bold=1, pos='bottom', col=2, mw=3, upper=False),
    'karaoke-sweep':      dict(font='Fredoka', k=0.95, bold=1, pos='lower-third', col=2, mw=5, upper=False),
    'lower-third-ticker': dict(font='Baloo 2', k=0.72, bold=0, pos='lower-third', col=1, mw=6, upper=False),
    'marker-highlight':   dict(font='Baloo 2', k=0.90, bold=1, pos='bottom', col=2, mw=4, upper=False),
    'outline-bold':       dict(font='Fredoka', k=1.15, bold=1, pos='center', col=2, mw=3, upper=True),
    'typewriter-reveal':  dict(font='DejaVu Sans Mono', k=0.66, bold=0, pos='bottom', col=1, mw=6, upper=False),
    'stacked-bounce':     dict(font='Baloo 2', k=1.25, bold=1, pos='center', col=2, mw=3, upper=True),
    'minimal-serif':      dict(font='DejaVu Serif', k=0.62, bold=0, pos='bottom', col=2, mw=7, upper=False),
    'chalk-hand':         dict(font='Caveat', k=1.15, bold=1, pos='bottom', col=2, mw=4, upper=False),
    'pill':               dict(font='Baloo 2', k=0.72, bold=0, pos='bottom', col=2, mw=7, upper=False),
}
assert set(SPEC) == set(CAPTION_PRESETS)


def place(pos, col, w, h):
    vertical = h > w
    row = {'bottom': 0, 'lower-third': 0, 'center': 3, 'top': 6}[pos]
    mv = {'bottom': h * (0.30 if vertical else 0.08), 'lower-third': h * (0.36 if vertical else 0.20),
          'center': 0, 'top': h * (0.13 if vertical else 0.07)}[pos]
    return row + col, int(mv)


def build(name, W, a, R, pos):
    S = SPEC[name]; w, h = a.w, a.h; vertical = h > w
    fs = int(h * (0.055 if vertical else 0.065) * S['k']); ol = max(3, fs // 14)
    al, mv = place(pos, S['col'], w, h)
    ml = int(w * (0.07 if S['col'] == 1 else 0.05)); mr = ml
    font = a.font or S['font']; up = a.upper or S['upper']
    D, L, A, A2 = R['dark'], R['light'], R['accent'], R['accent2']
    if a.active: A = '#' + a.active.lstrip('#')
    if a.idle: L = '#' + a.idle.lstrip('#')
    txt = lambda x: x['word'].upper() if up else x['word']
    groups = group_words(W, a.max_words or S['mw'], a.max_gap, skip_empty=True)

    def sty(prim, sec, outc, back, bold, spacing, angle, bstyle, outline, shadow):
        return (f"Style: {name},{font},{fs},{prim},{sec},{outc},{back},{bold},0,0,0,100,100,{spacing},{angle},"
                f"{bstyle},{outline},{shadow},{al},{ml},{mr},{mv},1")
    ev = []
    def dlg(st, en, body, layer=0):
        if ts(en) > ts(max(0, st)): ev.append(f"Dialogue: {layer},{ts(st)},{ts(en)},{name},,0,0,0,,{body}")
    def gend(gi, g):
        e = g[-1]['end'] + 0.15
        return min(e, groups[gi + 1][0]['start']) if gi + 1 < len(groups) else e
    HIDE = '{\\alpha&HFF&}'

    if name == 'pop-word':
        style = sty(bgr(L), bgr(L), bgr(D), bgr(D, 0x80), 1, 0, 0, 1, ol, max(2, ol // 2))
        for gi, g in enumerate(groups):
            ge = gend(gi, g)
            for i, x in enumerate(g):
                en = g[i + 1]['start'] if i + 1 < len(g) else ge
                line = [f"{{\\1c{bgr(A)}\\fscx122\\fscy122\\t(0,100,\\fscx100\\fscy100)}}{txt(y)}{{\\r}}" if j == i
                        else f"{{\\1c{bgr(L)}}}{txt(y)}" for j, y in enumerate(g)]
                dlg(x['start'], en, ' '.join(line))
    elif name == 'karaoke-sweep':
        style = sty(bgr(A), bgr(L), bgr(D), '&H00000000', 1, 1, 0, 1, int(ol * 1.3), 0)
        for gi, g in enumerate(groups):
            parts, t = [], g[0]['start']
            for x in g:
                if x['start'] > t: parts.append(f"{{\\k{int(round((x['start'] - t) * 100))}}}"); t = x['start']
                parts.append(f"{{\\kf{max(1, int(round((x['end'] - t) * 100)))}}}{txt(x)} "); t = x['end']
            dlg(g[0]['start'], gend(gi, g), "{\\fad(120,80)}" + ''.join(parts).strip())
    elif name == 'lower-third-ticker':
        pad = max(6, int(fs * 0.38))
        style = sty(bgr(L), bgr(L), bgr(D, 0x18), bgr(D, 0x18), 0, 0, 0, 3, pad, 0)
        for gi, g in enumerate(groups):
            first, rest = txt(g[0]), ' '.join(txt(x) for x in g[1:])
            body = f"{{\\fad(80,140)\\fsp{int(fs * 0.35)}\\t(0,260,\\fsp0)}}{{\\1c{bgr(A)}}}{first}{{\\1c{bgr(L)}}}" + (' ' + rest if rest else '')
            dlg(g[0]['start'] - 0.05, gend(gi, g), body)
    elif name == 'marker-highlight':
        big = max(8, int(fs * 0.26))
        style = sty(bgr(L), bgr(L), bgr(D), '&H00000000', 1, 0, 0, 1, max(2, ol - 1), 0)
        for gi, g in enumerate(groups):
            ge = gend(gi, g)
            for i, x in enumerate(g):
                en = g[i + 1]['start'] if i + 1 < len(g) else ge
                line = [f"{{\\1c{bgr(D)}\\3c{bgr(A)}\\bord0\\t(0,140,\\bord{big})}}{txt(y)}{{\\r}}" if j == i
                        else f"{{\\1c{bgr(L)}}}{txt(y)}" for j, y in enumerate(g)]
                dlg(x['start'], en, ' '.join(line))
    elif name == 'outline-bold':
        style = sty(bgr(L), bgr(L), bgr(D), '&H00000000', 1, 2, 0, 1, max(4, fs // 7), 0)
        for gi, g in enumerate(groups):
            body = "{\\fscx70\\fscy70\\t(0,120,\\fscx106\\fscy106)\\t(120,210,\\fscx100\\fscy100)}" + ' '.join(txt(x) for x in g)
            dlg(g[0]['start'], gend(gi, g), body)
    elif name == 'typewriter-reveal':
        pad = max(5, int(fs * 0.28))
        style = sty(bgr(L), bgr(L), bgr(D, 0x30), bgr(D, 0x30), 0, 0, 0, 3, pad, 0)
        for gi, g in enumerate(groups):
            line = ' '.join(txt(x) for x in g); ge = gend(gi, g)
            # character -> time it is typed: each word types across its own spoken span
            times, k = [], 0
            for wi, x in enumerate(g):
                wd = txt(x); span = max(0.05, min(x['end'] - x['start'], 0.07 * len(wd)))
                times += [x['start'] + span * c / max(1, len(wd)) for c in range(len(wd))]
                if wi + 1 < len(g): times.append(x['end'])         # the space
            done = times[-1] + 0.05
            for c in range(len(line)):
                st = times[c]; en = times[c + 1] if c + 1 < len(line) else done
                if en <= st: continue
                dlg(st, en, line[:c + 1] + f"{{\\1c{bgr(A)}}}▌" + HIDE + line[c + 1:])
            dlg(done, ge, line)
    elif name == 'stacked-bounce':
        style = sty(bgr(L), bgr(L), bgr(D), bgr(D, 0x60), 1, 1, 0, 1, max(4, fs // 9), 2)
        cols = [A, L, A2]
        for gi, g in enumerate(groups):
            ge = gend(gi, g)
            for i, x in enumerate(g):
                en = g[i + 1]['start'] if i + 1 < len(g) else ge
                rows = []
                for j, y in enumerate(g):
                    c = bgr(cols[j % len(cols)])
                    if j < i: rows.append(f"{{\\1c{c}}}{txt(y)}")
                    elif j == i: rows.append(f"{{\\1c{c}\\fscx130\\fscy40\\t(0,90,\\fscx92\\fscy118)\\t(90,200,\\fscx100\\fscy100)}}{txt(y)}{{\\r}}")
                    else: rows.append(HIDE + txt(y) + '{\\r}')
                dlg(x['start'], en, '\\N'.join(rows))
    elif name == 'minimal-serif':
        style = sty(bgr(L), bgr(L), bgr(D), bgr(D, 0x70), 0, 0.5, 0, 1, 0, 2)
        for gi, g in enumerate(groups):
            dlg(g[0]['start'] - 0.1, gend(gi, g) + 0.1, "{\\fad(260,260)\\blur0.6}" + ' '.join(txt(x) for x in g))
    elif name == 'chalk-hand':
        style = sty(bgr(L), bgr(L), bgr(D, 0x70), '&H00000000', 1, 1, 2, 1, 2, 0)
        for gi, g in enumerate(groups):
            ge = gend(gi, g)
            for i, x in enumerate(g):
                en = g[i + 1]['start'] if i + 1 < len(g) else ge
                parts = []
                for j, y in enumerate(g):
                    if j < i: parts.append("{\\blur0.8}" + txt(y))
                    elif j == i: parts.append("{\\alpha&HFF&\\blur3\\t(0,180,\\alpha&H00&\\blur0.8)}" + txt(y) + '{\\r}')
                    else: parts.append(HIDE + txt(y) + '{\\r}')
                dlg(x['start'], en, ' '.join(parts))
    elif name == 'pill':
        pad = max(6, int(fs * 0.32))
        style = sty('&H00FFFFFF', '&H00FFFFFF', bgr(D, 0x60), bgr(D, 0x60), 0, 0, 0, 3, pad, 0)
        for gi, g in enumerate(groups):
            dlg(g[0]['start'], gend(gi, g), "{\\fad(200,200)}" + ' '.join(txt(x) for x in g))
    return header(w, h, [style]) + '\n'.join(ev) + '\n', len(groups), len(ev)


def no_style_error():
    sys.exit('captions.py: no caption style chosen, and there is no default on purpose (every video gets its own look).\n'
             '  pick one: --preset ' + ' | '.join(CAPTION_PRESETS) + '\n'
             '  or set look.captions_preset in project.json and pass --project DIR\n'
             '  (--style pop|karaoke keeps the old yellow/white look). When to use which: ' + DOC)


def read_project(p):
    if not p: return {}
    f = os.path.join(p, 'project.json') if os.path.isdir(p) else p
    P = json.load(open(f, encoding='utf-8'))
    return P.get('look') if isinstance(P.get('look'), dict) else {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('words', nargs='?'); ap.add_argument('out', nargs='?')
    ap.add_argument('--w', type=int, default=1920); ap.add_argument('--h', type=int, default=1080)
    ap.add_argument('--style', default=None, help='pop | karaoke (legacy look) or a preset name')
    ap.add_argument('--preset', default=None, help='caption preset, see --list and ' + DOC)
    ap.add_argument('--project', default=None, help='project dir or project.json: look.captions_preset / palette / captions_position')
    ap.add_argument('--palette', default=None, help='comma-separated hex list, e.g. "#0e1621,#7fd1ff,#f4f1ea"')
    ap.add_argument('--position', default=None, choices=CAPTION_POSITIONS)
    ap.add_argument('--font', default=None)
    ap.add_argument('--max-words', type=int, default=None); ap.add_argument('--max-gap', type=float, default=0.6)
    ap.add_argument('--upper', action='store_true')
    ap.add_argument('--active', default=None, help='override accent / active-word colour RRGGBB')
    ap.add_argument('--idle', default=None, help='override text / idle-word colour RRGGBB')
    ap.add_argument('--list', action='store_true', help='print the presets and exit')
    a = ap.parse_args(argv)
    if a.list:
        for k, v in CAPTION_PRESETS.items(): print(f'{k:20s} {v}')
        return
    if not a.words or not a.out: ap.error('words and out are required')
    look = read_project(a.project)
    choice = norm(a.preset or a.style or look.get('captions_preset') or '')
    if not choice: no_style_error()
    W = load_words(a.words)
    if choice in LEGACY_STYLES and not a.preset:
        a.style = choice; body, ng, ne = legacy(a, W)
    else:
        if choice not in CAPTION_PRESETS:
            sys.exit(f'captions.py: unknown caption preset "{choice}". Use one of: {", ".join(CAPTION_PRESETS)} ({DOC})')
        pal = [c.strip() for c in a.palette.split(',') if c.strip()] if a.palette else look.get('palette')
        if isinstance(pal, list) and not all(re.fullmatch(r'#?[0-9a-fA-F]{6}', str(c)) for c in pal): pal = None
        if not pal: print('captions.py: no --palette / look.palette; using neutral fallback colours', file=sys.stderr)
        pos = a.position or (look.get('captions_position') if look.get('captions_position') in CAPTION_POSITIONS else None) \
            or SPEC[choice]['pos']
        body, ng, ne = build(choice, W, a, roles(pal), pos)
    open(a.out, 'w', encoding='utf-8').write(body)
    print(a.out, ng, 'lines', ne, 'events')


if __name__ == '__main__':
    main()
