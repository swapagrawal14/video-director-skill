#!/usr/bin/env python3
"""align.py - word + viseme timings for Hinglish VO by forced alignment (lip-sync and karaoke captions).

Aligns the KNOWN script (Devanagari, Roman Hinglish, or mixed) to the voice with torchaudio's MMS_FA
(multilingual wav2vec2 CTC, 1100+ languages; text romanized with uroman), then maps the romanized letters to
mouth shapes:  a/aa -> A,  o/u/w -> O,  e/i/y -> E,  m/b/p -> M (closed lips),  word gaps -> rest.
Other consonants take the shape of the nearest vowel in their word (coarticulation). Shapes shorter than
--min-hold (60 ms) are merged away, except a lone M closure which is stretched to min-hold.
If torch / the model / uroman are unavailable (or --method loudness) it falls back to the loudness track of
scripts/mouth.py and spreads the words over the voiced span by letter count (method: "loudness").

Usage:
  python3 scripts/align.py vo.wav --text "नमस्ते दोस्तों, aaj brushing seekhenge" -o vo.align.json
  python3 scripts/align.py vo.wav --text-file line.txt -o vo.align.json [--method auto|mms|loudness]
  python3 scripts/align.py --project <dir>        # timeline.json + vo_full.wav (screencast / handdrawn
        talking-explainer). Texts: script.json beats[].vo (captions keep beats[].sub) or lines.json.
        Aligns each seg of the final timeline separately; writes <dir>/align.json.
  add --frames-out mouth.json [--fps 30] for a scripts/mouth.py-style per-frame [{lv, shape}] (JS rigs' speechTrack).
Output JSON: {"method", "duration", "segs", "words": [{"w","start","end"}], "visemes": [{"t","shape"}]}
  visemes are change points (shape holds until the next t).  Per-frame: load_mouth_track(path, fps).
Install (optional extra, CPU-only, ~1.2 GB weights cached under ~/.cache/torch/hub on first run):
  pip install --index-url https://download.pytorch.org/whl/cpu torch torchaudio && pip install uroman
"""
import argparse, json, math, os, subprocess, sys, unicodedata, warnings

SR = 16000
SHAPES = ('rest', 'A', 'O', 'E', 'M')
MIN_HOLD = 0.06
PAUSE = 0.10          # silence between words longer than this closes the mouth (rest)
FALLBACK = {'M': ['rest'], 'E': ['A', 'O', 'rest'], 'O': ['A', 'E', 'rest'], 'A': ['O', 'E', 'rest'], 'rest': []}
CHAR_SHAPE = {**dict.fromkeys('a', 'A'), **dict.fromkeys('ouw', 'O'), **dict.fromkeys('eiy', 'E'), **dict.fromkeys('mbp', 'M')}
MMS_CHARS = set("aienoutsrmkldghybpwcvjzf'qx")
LABIALS = set('पफबभम')

# ----------------------------------------------------------------------------------------- text
def is_deva(s): return any('\u0900' <= c <= '\u097f' for c in s)


def split_words(text):
    """Display tokens: whitespace split, '.' trimmed (like the timeline builders), punctuation-only tokens dropped."""
    out = []
    for tok in text.split():
        w = tok.strip('.').strip()
        if any(c.isalnum() for c in w): out.append(w)
    return out


def _fix_nasals(w):
    """uroman turns anusvara/chandrabindu into 'm', which would read as a lip closure. Use n (m only before a labial)."""
    out = []
    for i, c in enumerate(w):
        if c == '\u0902':                       # ं
            nxt = w[i + 1] if i + 1 < len(w) else ''
            out.append('म्' if nxt in LABIALS else 'न्')
        elif c == '\u0901': continue            # ँ  (nasal vowel, no consonant)
        else: out.append(c)
    return ''.join(out)


_UROMAN = None
def _uroman():
    global _UROMAN
    if _UROMAN is None:
        import uroman as ur
        _UROMAN = ur.Uroman()
    return _UROMAN


def clean_roman(s):
    """Lower-case, strip accents, keep only letters the MMS_FA dictionary knows."""
    s = unicodedata.normalize('NFKD', s.lower())
    return ''.join(c for c in s if c in MMS_CHARS)


def romanize(words):
    """Display words -> MMS-ready romanized strings ('' when nothing alignable, e.g. digits)."""
    out = []
    for w in words:
        if is_deva(w):
            w = _fix_nasals(w)
            try: w = _uroman().romanize_string(w)
            except ImportError: w = ''           # no romanizer: word is time-interpolated instead
        out.append(clean_roman(w))
    return out


# ----------------------------------------------------------------------------------------- visemes (pure)
def char_shape(c): return CHAR_SHAPE.get(c)


def word_segments(chars, starts, word_end):
    """chars: romanized letters of one word; starts: each letter's start (s). -> [(t0, t1, shape)].
    Consonants without a shape take the next vowel's shape in the word, else the previous one, else A."""
    sh = [char_shape(c) for c in chars]
    vow = {'A', 'O', 'E'}
    res = []
    for i, s in enumerate(sh):
        if s is None:
            nxt = next((x for x in sh[i + 1:] if x in vow), None)
            prv = next((x for x in reversed(sh[:i]) if x in vow), None)
            s = nxt or prv or 'A'
        t1 = starts[i + 1] if i + 1 < len(starts) else word_end
        res.append((starts[i], max(starts[i], t1), s))
    return res


def merge_same(segs):
    out = []
    for a, b, s in segs:
        if b <= a: continue
        if out and out[-1][2] == s and abs(out[-1][1] - a) < 1e-6: out[-1] = (out[-1][0], b, s)
        else: out.append((a, b, s))
    return out


def smooth(segs, min_hold=MIN_HOLD):
    """Contiguous [(t0, t1, shape)] -> no segment shorter than min_hold. A short M between two open shapes is
    stretched to min_hold (lip closures read as sync); any other short segment joins its longer neighbour."""
    segs = merge_same(segs)
    for _ in range(10000):
        short = [i for i, (a, b, _) in enumerate(segs) if b - a < min_hold - 1e-9]
        if not short or len(segs) < 2: break
        i = min(short, key=lambda k: segs[k][1] - segs[k][0])
        a, b, s = segs[i]; need = min_hold - (b - a)
        L = segs[i - 1] if i > 0 else None; R = segs[i + 1] if i + 1 < len(segs) else None
        if s == 'M' and L and R and L[2] != 'M' and R[2] != 'M' and \
                (L[1] - L[0]) - need / 2 >= min_hold and (R[1] - R[0]) - need / 2 >= min_hold:
            segs[i - 1] = (L[0], L[1] - need / 2, L[2]); segs[i] = (a - need / 2, b + need / 2, s)
            segs[i + 1] = (R[0] + need / 2, R[1], R[2]); continue
        if L is None or (R is not None and (R[1] - R[0]) > (L[1] - L[0])):
            segs[i + 1] = (a, R[1], R[2])
        else:
            segs[i - 1] = (L[0], b, L[2])
        del segs[i]; segs = merge_same(segs)
    return segs


def visemes_from_chars(words, duration, pause=PAUSE, min_hold=MIN_HOLD):
    """words: [{'start','end','chars': [(letter, t_start), ...]}] (sorted) -> [{'t','shape'}] change points."""
    segs, t = [], 0.0
    for k, w in enumerate(words):
        if not w.get('chars'): continue
        st = w['chars'][0][1]
        if st - t > 1e-6:
            if segs and st - t <= pause:      # tiny gap between words: keep the mouth where it was
                a, _, s = segs[-1]; segs[-1] = (a, st, s)
            else: segs.append((t, st, 'rest'))
        segs += word_segments([c for c, _ in w['chars']], [x for _, x in w['chars']], w['end'])
        t = max(t, w['end'])
    if duration > t: segs.append((t, duration, 'rest'))
    if not segs: segs = [(0.0, max(duration, 0.0), 'rest')]
    return to_changes(smooth(segs, min_hold))


def to_changes(segs):
    out = []
    for a, _, s in segs:
        if not out or out[-1]['shape'] != s: out.append({'t': round(a, 3), 'shape': s})
    if out and out[0]['t'] > 0: out.insert(0, {'t': 0.0, 'shape': 'rest'})
    if out and out[-1]['shape'] != 'rest': out.append({'t': round(segs[-1][1], 3), 'shape': 'rest'})
    return out


def fallback_shape(shape, available):
    if available is None or shape in available: return shape
    return next((s for s in FALLBACK.get(shape, []) if s in available), 'rest')


def load_mouth_track(path_or_json, fps, n_frames=None, available=None, lead=0.0):
    """align.json path | dict | visemes list -> per-frame shapes ('rest'|'A'|'O'|'E'|'M').
    available: the mouth patches the rig has (e.g. {'rest','A','O'}); missing shapes fall back (M -> rest).
    lead: show each shape this many seconds early (animators often lead lips by ~1 frame)."""
    d = path_or_json
    if isinstance(d, str):
        with open(d) as fh: d = json.load(fh)
    vis = d['visemes'] if isinstance(d, dict) else d
    if n_frames is None:
        dur = d.get('duration') if isinstance(d, dict) else None
        n_frames = int(math.ceil((dur or (vis[-1]['t'] if vis else 0)) * fps)) + 1
    out, j, cur = [], 0, 'rest'
    for f in range(n_frames):
        t = f / fps + lead
        while j < len(vis) and vis[j]['t'] <= t + 1e-9: cur = vis[j]['shape']; j += 1
        out.append(fallback_shape(cur, available))
    return out


def frames_track(audio_path, d, fps):
    """scripts/mouth.py-compatible per-frame [{'lv','shape'}] (lv = real loudness, shape = aligned viseme) for the
    JS rigs' speechTrack() (template/headrig3d.js, posepack3d.js)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import mouth
    lv = mouth.track(mouth.decode(audio_path), fps)
    sh = load_mouth_track(d, fps, len(lv))
    return [{'lv': r['lv'], 'shape': s} for r, s in zip(lv, sh)]


def caption_words(d):
    """align dict/path -> [{'word','start','end'}] for captions.py / hd.karaoke / fx.box_captions."""
    if isinstance(d, str):
        with open(d) as fh: d = json.load(fh)
    ws = d['words'] if isinstance(d, dict) else d
    return [{'word': w.get('w', w.get('word')), 'start': w['start'], 'end': w['end']} for w in ws]


def redistribute(display, aligned):
    """Caption text that differs from the spoken text (beat 'sub' vs 'vo'): same word count -> 1:1 times,
    else spread the display words over the aligned span by letter count."""
    if not aligned: return []
    if len(display) == len(aligned):
        return [{'w': d, 'start': a['start'], 'end': a['end']} for d, a in zip(display, aligned)]
    return spread(display, aligned[0]['start'], aligned[-1]['end'])


def spread(display, t0, t1):
    wt = [len(w) + 2 for w in display]; tot = sum(wt) or 1; c = t0; out = []
    for w, k in zip(display, wt):
        du = (t1 - t0) * k / tot; out.append({'w': w, 'start': round(c, 3), 'end': round(c + du * .9, 3)}); c += du
    return out


def envelope(audio, hop=SR // 100):
    """RMS per 10 ms frame (list of floats)."""
    import numpy as np
    n = len(audio) // hop
    if n == 0: return []
    return np.sqrt((np.asarray(audio[:n * hop], np.float32).reshape(n, hop) ** 2).mean(1)).tolist()


def refine_edges(words, env, step=.01, offset=0.0, rel=.25, max_tail=.2, max_head=.08):
    """CTC spans are peaky: the last letter's span ends when its emission peak does, though the vowel rings on, and
    the first letter often fires a frame or two after the onset. Push each word's end forward (and start back) while
    the 10 ms energy stays above rel x the word's peak, never into a neighbour. env[i] covers t = offset + i*step."""
    al = [w for w in words if w.get('chars')]
    idx = lambda t: int(round((t - offset) / step))
    for k, w in enumerate(al):
        a, b = idx(w['start']), idx(w['end'])
        seg = env[max(0, a):max(a + 1, b)]
        if not seg: continue
        thr = rel * max(seg)
        nxt = idx(al[k + 1]['chars'][0][1]) if k + 1 < len(al) else len(env)
        prv = idx(al[k - 1]['end']) if k > 0 else 0
        e = b
        while e < min(nxt, len(env), b + int(max_tail / step)) and env[e] > thr: e += 1
        s0 = a
        while s0 - 1 > max(prv, a - int(max_head / step)) and env[s0 - 1] > thr: s0 -= 1
        w['end'] = round(max(w['end'], offset + e * step), 3)
        if s0 < a:
            w['start'] = round(offset + s0 * step, 3); w['chars'][0] = (w['chars'][0][0], w['start'])
    return words


def fill_missing(words):
    """Words that could not be aligned (no romanizable letters) get the gap between their neighbours."""
    n = len(words)
    for i, w in enumerate(words):
        if w.get('start') is not None: continue
        j = i
        while j < n and words[j].get('start') is None: j += 1
        a = words[i - 1]['end'] if i > 0 else (words[j]['start'] if j < n else 0.0)
        b = words[j]['start'] if j < n else a + .3 * (j - i)
        if b < a: b = a
        step = (b - a) / (j - i)
        for k in range(i, j): words[k]['start'] = round(a + step * (k - i), 3); words[k]['end'] = round(a + step * (k - i + 1), 3)
    return words


# ----------------------------------------------------------------------------------------- audio + model
def decode(path):
    import numpy as np
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()


_MMS = None
def weights_cached():
    try:
        import torch
        p = os.path.join(torch.hub.get_dir(), 'checkpoints', 'model.pt')
        return os.path.exists(p) and os.path.getsize(p) > 1e9
    except Exception:
        return False


def mms_available(download=True):
    try:
        import torch, torchaudio  # noqa: F401
        from torchaudio.pipelines import MMS_FA  # noqa: F401
        import uroman  # noqa: F401
    except Exception:
        return False
    return download or weights_cached()


def _mms():
    global _MMS
    if _MMS is None:
        import torch
        from torchaudio.pipelines import MMS_FA as B
        torch.set_num_threads(max(1, os.cpu_count() or 1))
        _MMS = (B.get_model(with_star=False).eval(), B.get_tokenizer(), B.get_aligner(), B.get_dict())
    return _MMS


def align_samples(audio, words, offset=0.0):
    """audio: float32 mono 16 kHz numpy; words: display words. -> [{'w','start','end','chars':[(c,t)], 'score'}]"""
    import torch
    model, tok, aligner, _ = _mms()
    roman = romanize(words)
    idx = [i for i, r in enumerate(roman) if r]
    out = [{'w': w, 'start': None, 'end': None, 'chars': []} for w in words]
    if not idx or len(audio) < SR * .05: return fill_missing(out)
    with torch.inference_mode():
        em, _ = model(torch.from_numpy(audio).unsqueeze(0))
    ratio = len(audio) / em.size(1) / SR
    with warnings.catch_warnings():       # torchaudio 2.8 deprecation notice for forced_align (pin torchaudio<2.9)
        warnings.simplefilter('ignore'); spans = aligner(em[0], tok([roman[i] for i in idx]))
    for i, sp in zip(idx, spans):
        chars = roman[i]
        out[i]['chars'] = [(chars[k], round(offset + s.start * ratio, 3)) for k, s in enumerate(sp)]
        out[i]['start'] = round(offset + sp[0].start * ratio, 3); out[i]['end'] = round(offset + sp[-1].end * ratio, 3)
        out[i]['score'] = round(sum(s.score * (s.end - s.start) for s in sp) / max(1, sum(s.end - s.start for s in sp)), 3)
    refine_edges(out, envelope(audio), offset=offset)
    return fill_missing(out)


def loudness_visemes(audio_path, fps=100):
    """Fallback: scripts/mouth.py loudness/zero-crossing shapes -> change points (+ voiced span)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import mouth
    tr = mouth.track(mouth.decode(audio_path), fps)
    segs = [(f / fps, (f + 1) / fps, r['shape']) for f, r in enumerate(tr)]
    voiced = [f for f, r in enumerate(tr) if r['shape'] != 'rest']
    span = (voiced[0] / fps, (voiced[-1] + 1) / fps) if voiced else (0.0, len(tr) / fps)
    return to_changes(smooth(segs)), span, len(tr) / fps


# ----------------------------------------------------------------------------------------- drivers
def _pick(method, download=True):
    if method == 'loudness': return 'loudness'
    ok = mms_available(download)
    if method == 'mms' and not ok: raise SystemExit('MMS_FA unavailable: pip install torch torchaudio uroman (see docs/AUDIO_CAPTIONS.md)')
    return 'mms_fa' if ok else 'loudness'


def align_clip(audio_path, text, method='auto', caption_text=None, download=True):
    m = _pick(method, download); disp = split_words(caption_text or text)
    if m == 'mms_fa':
        try:
            a = decode(audio_path); dur = len(a) / SR
            ws = align_samples(a, split_words(text))
            return {'method': m, 'duration': round(dur, 3), 'words': _pub(redistribute(disp, ws)),
                    'visemes': visemes_from_chars(ws, dur)}
        except Exception as e:  # noqa: BLE001
            print(f'align: MMS_FA failed ({e}); falling back to loudness', file=sys.stderr)
    vis, span, dur = loudness_visemes(audio_path)
    return {'method': 'loudness', 'duration': round(dur, 3), 'words': spread(disp, *span), 'visemes': vis}


def _pub(ws): return [{'w': w['w'], 'start': w['start'], 'end': w['end']} for w in ws]


def project_texts(proj):
    if os.path.exists(f'{proj}/script.json'):
        S = json.load(open(f'{proj}/script.json'))
        if 'beats' in S: return [(b['vo'], b.get('sub')) for b in S['beats']]
    if os.path.exists(f'{proj}/lines.json'):
        return [(x, None) for x in json.load(open(f'{proj}/lines.json'))]
    raise SystemExit(f'{proj}: need script.json (beats[].vo) or lines.json')


def align_project(proj, method='auto', download=True, out=None):
    """Final-timeline alignment for timeline.json projects (screencast, handdrawn talking-explainer)."""
    T = json.load(open(f'{proj}/timeline.json')); segs = T['segs']; texts = project_texts(proj)
    if len(texts) != len(segs): raise SystemExit(f'{len(texts)} texts but {len(segs)} timeline segs')
    wav = f'{proj}/vo_full.wav'; dur = T['duration']; m = _pick(method, download)
    words, chars = [], []
    if m == 'mms_fa':
        try:
            a = decode(wav)
            for k, (s, (vo, sub)) in enumerate(zip(segs, texts)):
                lo = s['start'] - .15 if k == 0 else max(s['start'] - .15, (segs[k - 1]['end'] + s['start']) / 2)
                hi = s['end'] + .15 if k + 1 == len(segs) else min(s['end'] + .15, (s['end'] + segs[k + 1]['start']) / 2)
                lo = max(0.0, lo); ws = align_samples(a[int(lo * SR):int(hi * SR)], split_words(vo), offset=lo)
                chars += ws; words += redistribute(split_words(sub or vo), ws)
            vis = visemes_from_chars(chars, dur)
        except Exception as e:  # noqa: BLE001
            print(f'align: MMS_FA failed ({e}); falling back to loudness', file=sys.stderr); m = 'loudness'
    if m == 'loudness':
        vis, _, _ = loudness_visemes(wav)
        for s, (vo, sub) in zip(segs, texts): words += spread(split_words(sub or vo), s['start'], s['end'])
    res = {'method': m, 'duration': dur, 'segs': [[s['start'], s['end']] for s in segs], 'words': _pub(words), 'visemes': vis}
    out = out or f'{proj}/align.json'
    with open(out, 'w') as fh: json.dump(res, fh, ensure_ascii=False, indent=0)
    return res


def project_track(proj, T, available=None, mode=None):
    """For renderers: (per-frame shapes, caption words) from <proj>/align.json, or (None, None) to keep loudness.
    The mouth leads the sound by one frame (MMS onsets land ~30-40 ms after the acoustic onset).
    mode: 'auto' (use align.json if present and matching the timeline) | 'align' (build it if missing) | 'loudness'.
    env VD_LIPSYNC (set by --lipsync) overrides mode; default 'auto'."""
    mode = os.environ.get('VD_LIPSYNC') or mode or 'auto'
    p = f'{proj}/align.json'
    if mode == 'loudness': return None, None
    if mode == 'align' and not is_fresh(p, T): align_project(proj)
    if not os.path.exists(p): return None, None
    if not is_fresh(p, T):
        print(f'lipsync: {p} does not match timeline.json (re-run scripts/align.py --project); using loudness', file=sys.stderr)
        return None, None
    d = json.load(open(p)); n = int(T['duration'] * T['fps']) + 3
    return load_mouth_track(d, T['fps'], n, available, lead=1 / T['fps']), caption_words(d)


def is_fresh(p, T):
    if not os.path.exists(p): return False
    try: s = json.load(open(p)).get('segs')
    except Exception: return False
    return s is not None and len(s) == len(T['segs']) and all(
        abs(a - x['start']) < .02 and abs(b - x['end']) < .02 for (a, b), x in zip(s, T['segs']))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('audio', nargs='?'); ap.add_argument('--text'); ap.add_argument('--text-file')
    ap.add_argument('--caption-text', help='display words if they differ from the spoken text')
    ap.add_argument('--project'); ap.add_argument('-o', '--out')
    ap.add_argument('--method', default='auto', choices=['auto', 'mms', 'loudness'])
    ap.add_argument('--no-download', action='store_true', help='fall back to loudness instead of fetching 1.2 GB weights')
    ap.add_argument('--frames-out', help='also write mouth.py-style per-frame [{lv, shape}] (for headrig3d/posepack3d speechTrack)')
    ap.add_argument('--fps', type=float, default=30)
    a = ap.parse_args()
    if a.project:
        r = align_project(os.path.abspath(a.project), a.method, not a.no_download, a.out)
    else:
        if not a.audio: ap.error('audio or --project required')
        text = a.text if a.text is not None else open(a.text_file, encoding='utf-8').read() if a.text_file else None
        if not text: ap.error('--text or --text-file required')
        r = align_clip(a.audio, text, a.method, a.caption_text, not a.no_download)
        out = a.out or os.path.splitext(a.audio)[0] + '.align.json'
        with open(out, 'w') as fh: json.dump(r, fh, ensure_ascii=False, indent=0)
    if a.frames_out:
        with open(a.frames_out, 'w') as fh: json.dump(frames_track(a.audio or f'{a.project}/vo_full.wav', r, a.fps), fh)
    dist = {}
    for x, y in zip(r['visemes'], r['visemes'][1:] + [{'t': r['duration']}]): dist[x['shape']] = round(dist.get(x['shape'], 0) + y['t'] - x['t'], 2)
    print(f"{r['method']}: {len(r['words'])} words, {len(r['visemes'])} viseme changes, seconds per shape {dist}", file=sys.stderr)


if __name__ == '__main__':
    main()
