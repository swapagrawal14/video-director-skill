"""Pre-render lint of project.json + timing.json: catches the craft mistakes that make AI videos look cheap.
Usage: python3 scripts/lint.py <project-dir> [--json] [--pre-build]   (exit 1 on any ERROR)
Checks: hook (first VO/text within 1 s, first scene <=10 s), scene length (3-25 s), VO speed (130-190 wpm English-ish),
subtitle chunk length (<=90 chars), dead air (scene with no VO and no 'secs'/'shot'), outro credit present,
>=3 chapters >=10 s for videos over 60 s, numbers written as digits inside 'vo' (TTS mispronounces), missing VO files,
genre-specific bans from docs/STYLES.md (e.g. horror without silence-before-stinger, promo without CTA), no SVG.
Anti-clone checks (docs/FRESH_LOOK.md; every video gets its own look, examples are a quality bar, never a template):
  (a) project.json needs a filled "look" block {set, palette[3-5 hex], character, type, captions, camera, signature,
      reuse_reason?}; any "CHANGE ME" left in "look" or "theme" is an ERROR.
  (b) theme equal to the Pixar Clinic / template defaults (3+ of accent, accent2, bench, mat, background) is an ERROR
      unless look.reuse_reason is a non-empty string.
  (c) index.html still has the default tooth mascot ("Dentu" or the template's mascot block) while scenes use
      "mascot", or the template's wooden-bench texture with the bench still visible.
  (d) index.html too similar to examples/braces-tutorial/index.html or template/index.html
      (difflib ratio on normalised lines > 0.85).
  (e) a scene "vo"/"sub" line identical to a line of examples/braces-tutorial/script.json.
  --pre-build skips (c) and (d): make_video.py lints right after timing, before index.html is built."""
import json, os, re, sys
d = sys.argv[1]; asjson = '--json' in sys.argv
P = json.load(open(os.path.join(d, 'project.json'))); tp = os.path.join(d, 'timing.json')
T = json.load(open(tp)) if os.path.exists(tp) else None
E, W = [], []
S = P.get('scenes', []); genre = (P.get('recipe') or P.get('genre') or '').lower()
if T and T.get('scenes'):
    s0 = T['scenes'][0]
    if s0['off'] > 1.0: W.append(f"hook: first VO starts at {s0['off']} s; set intro_lead <= 0.3 so the hook lands in the first second")
    if s0['d'] > 10: W.append(f"hook: first scene is {s0['d']} s; a hook should land and turn within 10 s")
for i, s in enumerate(S):
    ts = T['scenes'][i] if T and i < len(T.get('scenes') or []) else None; vo = s.get('vo', '') or ''
    if ts:
        if ts['d'] > 25: W.append(f's{i:02d}: {ts["d"]} s long; split it (one idea per scene, 8-14 s sweet spot)')
        if ts['d'] < 2.5 and s.get('type') not in ('title', 'end'): W.append(f's{i:02d}: only {ts["d"]} s; viewers cannot read it')
        if vo and ts['vo']:
            wpm = len(vo.split()) / ts['vo'] * 60
            if wpm > 200: W.append(f's{i:02d}: VO {wpm:.0f} wpm, too fast; slow the TTS or cut words')
            if wpm < 75 and len(vo.split()) > 6: W.append(f's{i:02d}: VO {wpm:.0f} wpm, sluggish; check for long pauses')
        if vo and not ts['vo']: E.append(f's{i:02d}: has vo text but vo/s{i:02d}.wav missing or empty (run TTS, then build_timing.py)')
    if re.search(r'\d', vo): W.append(f's{i:02d}: digits in vo ("{re.findall(r"[^ ]*\d[^ ]*", vo)[0]}"); write numbers as words for TTS, digits go in sub')
    for c in (s.get('sub') or '').split('|'):
        if len(c.strip()) > 90: E.append(f's{i:02d}: subtitle chunk {len(c.strip())} chars (>90): "{c.strip()[:40]}..."')
    if not vo and not s.get('secs') and s.get('type') not in ('title', 'end'): W.append(f's{i:02d}: no vo and no secs; dead air (default 4 s)')
if P.get('burn_captions') and any(x.get('sub') for x in S):
    E.append('burn_captions is set but scenes also have "sub": the two caption layers overlap. Clear "sub" (keep text in "cap"/"vo") or drop burn_captions')
last = json.dumps(S[-1]).lower() if S else ''
if S and not any(k in last for k in ('credit', 'by ', 'subscribe', 'follow', 'end')): W.append('outro: last scene has no credit / CTA')
if T and T.get('duration', 0) > 60 and sum(1 for s in S if s.get('chapter')) < 3: W.append('chapters: add "chapter" titles to >=3 scenes (>=10 s apart) for YouTube chapters')
if 'horror' in genre:
    if not P.get('mute') : W.append('horror: no "mute" window; put 0.5-1 s of silence right before each stinger (scares need a vacuum)')
    if not any('sting' in x.get('file', '') for x in P.get('sfx', [])): W.append('horror: no stinger in sfx; run scripts/sfx_horror.sh')
if any(k in genre for k in ('promo', 'product')) and not any(k in last for k in ('link', 'download', 'try', 'buy', 'visit', 'cta')):
    W.append('promo: last scene needs a clear call to action')
# STRICT no-SVG rule: no .svg files and no inline <svg> / SVG data URIs anywhere in the project
for _r, _ds, _fs in os.walk(d):
    if 'node_modules' in _r: continue
    for _f in _fs:
        _p = os.path.join(_r, _f)
        if _f.lower().endswith('.svg'): E.append(f'SVG file not allowed: {os.path.relpath(_p, d)}')
        elif _f.lower().endswith(('.html', '.js', '.mjs', '.css', '.json')):
            try: _t = open(_p, encoding='utf-8', errors='ignore').read()
            except Exception: continue
            if re.search(r'<svg[\s>]|image/svg\+xml|SVGLoader|createElementNS\([^)]*svg', _t, re.I): E.append(f'SVG usage not allowed in {os.path.relpath(_p, d)}')
# ---------------- anti-clone checks (docs/FRESH_LOOK.md) ----------------
import difflib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRESH = 'build your own set/characters/look (docs/FRESH_LOOK.md)'
PRE_BUILD = '--pre-build' in sys.argv
LOOK_KEYS = ('set', 'palette', 'character', 'type', 'captions', 'camera', 'signature')
LOOK = P.get('look')
REUSE = isinstance(LOOK, dict) and isinstance(LOOK.get('reuse_reason'), str) and LOOK['reuse_reason'].strip() \
    and 'change me' not in LOOK['reuse_reason'].lower()
# (a) look sheet present and filled in
if not isinstance(LOOK, dict):
    E.append('look: project.json has no "look" block; write the look sheet first (set, palette, character, type, captions, '
             'camera, signature) - docs/FRESH_LOOK.md')
else:
    for k in LOOK_KEYS:
        v = LOOK.get(k)
        if v in (None, '', []): E.append(f'look.{k} is empty; fill the look sheet (docs/FRESH_LOOK.md)')
    pal = LOOK.get('palette')
    if pal not in (None, '', []) and 'change me' not in json.dumps(pal).lower() and (not isinstance(pal, list) or not all(isinstance(c, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', c) for c in pal)
                                      or not 3 <= len(pal) <= 5):
        E.append('look.palette must be a list of 3-5 hex colours like "#1a2b3c"')
if 'change me' in json.dumps(P.get('look', {}), ensure_ascii=False).lower() or 'change me' in json.dumps(P.get('theme', {}), ensure_ascii=False).lower():
    E.append('look/theme still contain "CHANGE ME" placeholders; ' + FRESH)
# (b) theme equal to the Pixar Clinic / template defaults
DEF_THEME = {'accent': '#e2475b', 'accent2': '#3b82c4', 'bench': '#c98e5a', 'mat': '#3e8e93',
             'background': ['#24557a', '#5fa6b8', '#f2cfa8']}
_ip = os.path.join(d, 'index.html'); IDX = open(_ip, encoding='utf-8', errors='ignore').read() if os.path.exists(_ip) else ''
_th = P.get('theme') if isinstance(P.get('theme'), dict) else None
if _th is not None or ('TH.accent ||' in IDX and "'#e2475b'" in IDX):
    _th = _th or {}
    _fallback = 'TH.accent ||' in IDX  # the template engine falls back to the Pixar Clinic colours for missing keys
    _low = lambda v: [x.lower() for x in v] if isinstance(v, list) else (v.lower() if isinstance(v, str) else v)
    same = [k for k, dv in DEF_THEME.items() if (k in _th and _low(_th[k]) == _low(dv)) or (k not in _th and _fallback)]
    if len(same) >= 3:
        if REUSE: W.append(f'theme reuses the Pixar Clinic defaults ({", ".join(same)}); allowed by look.reuse_reason')
        else: E.append(f'theme is the Pixar Clinic / template default ({", ".join(same)}); pick this video\'s own palette from '
                       'look.palette, or give look.reuse_reason - docs/FRESH_LOOK.md')
# (e) VO / subtitles copied from the braces example
try: _bs = json.load(open(os.path.join(ROOT, 'examples', 'braces-tutorial', 'script.json'), encoding='utf-8'))
except Exception: _bs = []
_nz = lambda x: re.sub(r'\s+', ' ', str(x)).strip().lower()
_BL = {_nz(x) for x in (_bs if isinstance(_bs, list) else []) if len(_nz(x)) >= 15}
for i, s in enumerate(S):
    for k in ('vo', 'sub'):
        for line in [s.get(k) or ''] + (s.get(k) or '').split('|'):
            if _nz(line) in _BL:
                E.append(f's{i:02d}: "{k}" copied from examples/braces-tutorial/script.json; write this video\'s own script (docs/FRESH_LOOK.md)'); break
if IDX and not PRE_BUILD:
    uses_mascot = any(s.get('mascot') for s in S)
    # (c) default mascot / wooden bench left in place
    if re.search(r'\bdentu\b', IDX, re.I): E.append('index.html still contains the "Dentu" tooth mascot from the braces example; ' + FRESH)
    MASCOT_SIG = ('new THREE.LatheGeometry(prof, 48), white); crown.position.y = 10',
                  '[[-6, -5], [6, -5], [-6, 5], [6, 5]].forEach')
    if uses_mascot and any(sig in IDX for sig in MASCOT_SIG):
        E.append('index.html still has the template\'s default tooth mascot and scenes use "mascot"; design this video\'s own '
                 'character (or none) from look.character - docs/FRESH_LOOK.md')
    if "'120,70,35' : '230,180,130'" in IDX and not re.search(r'bench\.visible\s*=\s*false', IDX):
        E.append('index.html still uses the default wooden bench texture; build this video\'s own set from look.set (or set '
                 'bench.visible = false) - docs/FRESH_LOOK.md')
    # (d) whole file copied from the braces example or the template
    def _norm(t):
        out = []
        for l in t.splitlines():
            l = re.sub(r'\s+', ' ', l).strip()
            if l and not l.startswith(('//', '/*', '*', '<!--')): out.append(l)
        return out
    _mine = _norm(IDX)
    for ref in ('examples/braces-tutorial/index.html', 'template/index.html'):
        rp = os.path.join(ROOT, ref)
        if not os.path.exists(rp) or os.path.abspath(rp) == os.path.abspath(_ip): continue
        sm = difflib.SequenceMatcher(None, _mine, _norm(open(rp, encoding='utf-8', errors='ignore').read()), autojunk=False)
        if sm.real_quick_ratio() > .85 and sm.quick_ratio() > .85 and sm.ratio() > .85:
            E.append(f'index.html copied from {ref} ({sm.ratio():.0%} identical); {FRESH}')
if asjson: print(json.dumps({'errors': E, 'warnings': W}, indent=1))
else:
    for x in E: print('ERROR', x)
    for x in W: print('WARN ', x)
    print('LINT', 'FAILED' if E else 'PASSED', f'({len(E)} errors, {len(W)} warnings)')
sys.exit(1 if E else 0)
