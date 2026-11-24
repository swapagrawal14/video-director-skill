#!/usr/bin/env python3
"""One-command orchestrator that walks the SKILL.md stages with resumable checkpoints.

  python3 scripts/make_video.py "Adams clasp wire bending" --format reel --engine auto
      -> projects/<slug>/brief.json, prints the treatment menu (docs/INTAKE.md) and STOPS for the user's pick
  python3 scripts/make_video.py "Adams clasp wire bending" --treatment 1
      -> script -> vo -> timing -> build -> preview -> (storyboard approval) -> render -> mix -> mux -> qa -> package

Stages: brief, treatment, script, vo, timing, build, preview, render, mix, mux, qa, package.
Progress lives in projects/<slug>/state.json; re-running the same command resumes at the first unfinished stage.
Where a stage needs an agent's creative work (writing the script and action sheet, building the scene/assets,
the title/description) it writes TODO_<stage>.md with exact instructions and stops cleanly (exit 0). Do the
TODO, then re-run. Approvals (treatment pick, storyboard) are explicit flags, never assumed.

Options:
  --format reel|youtube|square   --engine auto|template|motion2d|handdrawn|screencast|vidliboom
  --treatment N (1-13, docs/INTAKE.md)   --approve-storyboard   --style 2d|3d (tie-break for treatment 1)
  --tts edge|cartesia|none (default edge)   --voice hi-IN-SwaraNeural   --lang hi   --credit "Name (role)"
  --stop-after <stage>   --redo <stage> (reset it and everything after)   --status   --dry-run (print, change nothing)
  --slug NAME   --projects-dir DIR (default <repo>/projects)   --variants 16x9,1x1 (reframe.py at package)
Exit codes: 0 = finished or stopped cleanly (TODO / approval / --stop-after), 1 = a stage failed, 2 = bad usage."""
import argparse, datetime as dt, glob, json, os, re, shlex, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
STAGES = ['brief', 'treatment', 'script', 'vo', 'timing', 'build', 'preview', 'render', 'mix', 'mux', 'qa', 'package']
FORMATS = {'reel': (1080, 1920), 'youtube': (1920, 1080), 'square': (1080, 1080)}
BUILTIN = ['template', 'motion2d', 'handdrawn', 'screencast', 'vidliboom']
OWNS_AUDIO = {'screencast', 'vidliboom'}          # these engines do their own VO, timing and mix
KEYWORDS = {
    1: ['procedure', 'bend', 'bending', 'wire', 'clasp', 'step by step', 'recipe', 'lab', 'diy', 'how to make', 'banaye', 'banana',
        'technique', 'fabrication', 'make a', 'build a', 'cook', 'retainer', 'spring'],
    2: ['explain', 'concept', 'why', 'what is', 'kya hai', 'kyun', 'tips', 'guide', 'introduction', 'basics', 'myth'],
    3: ['fact', 'facts', 'ad', 'promo', 'launch', 'fun', 'did you know', 'product', 'short'],
    4: ['anatomy', 'mechanism', '3d', 'implant', 'root canal', 'surgery', 'extraction', 'cross-section', 'engine', 'organ', 'tooth', 'teeth'],
    5: ['theory', 'overview', 'revision', 'notes', 'whiteboard', 'diagram', 'classification', 'types of', 'exam'],
    6: ['app', 'website', 'software', 'browser', 'chatgpt', 'excel', 'site', 'online', 'portal', 'tutorial on using', 'figma', 'github'],
    7: ['story', 'skit', 'dialogue', 'patient', 'conversation', 'episode', 'kahani', 'cartoon'],
    8: ['horror', 'scary', 'ghost', 'haunted', 'bhoot', 'creepy', 'mystery', 'true crime'],
    9: ['q&a', 'talking', 'hook', 'meme'],
    12: ['podcast', 'voice note', 'audiogram', 'interview'],
}
DEFAULT_ORDER = [1, 2, 3, 5, 4, 6, 7, 9, 8, 12]


# ---------------------------------------------------------------- pure helpers (unit tested)
def slugify(s, maxlen=48):
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return (s[:maxlen].rstrip('-') or 'video')


def parse_intake(md):
    """docs/INTAKE.md table -> [{n, name, what, engine, best}]"""
    out = []
    for ln in md.splitlines():
        m = re.match(r'^\|\s*(\d+)\s*\|(.*)\|\s*$', ln)
        if not m: continue
        cells = [c.strip() for c in m.group(2).split('|')]
        if len(cells) < 4: continue
        out.append(dict(n=int(m.group(1)), name=re.sub(r'\*\*', '', cells[0]).strip(), what=cells[1], engine=cells[2], best=cells[3]))
    return out


def rank_treatments(topic, treatments, k=3):
    """Top-k treatment numbers for a topic: keyword hits first, then a sensible default order. First = pick."""
    t = ' ' + topic.lower() + ' '
    avail = {x['n'] for x in treatments}

    def score(n):
        return sum(1 for w in KEYWORDS.get(n, []) if re.search(r'(?<![a-z])' + re.escape(w) + r'(?![a-z])', t))
    order = [n for n in DEFAULT_ORDER if n in avail]
    ranked = sorted(order, key=lambda n: (-score(n), order.index(n)))
    hits = [n for n in ranked if score(n) > 0]
    rest = [n for n in order if n not in hits]
    return (hits + rest)[:k]


def engine_for(treatment, override='auto', style=None):
    """Engine for a treatment row (its Engine cell) unless overridden. Unknown/external -> 'external:<name>'."""
    if override and override != 'auto': return override
    cell = treatment['engine'] if isinstance(treatment, dict) else str(treatment)
    names = re.findall(r'`([^`]+)`', cell)
    names = [n.strip().strip('/').split('/')[0].split(' ')[0] for n in names]
    builtin = [n for n in names if n in BUILTIN]
    if style and style.lower() == '3d' and 'template' in builtin: return 'template'
    if builtin: return builtin[0]
    if names: return 'external:' + names[0]
    return 'external:' + slugify(cell or 'unknown')


def format_menu(topic, treatments, picks):
    by = {x['n']: x for x in treatments}; lines = [f'Treatments for "{topic}" (pick one, then re-run with --treatment N):']
    for i, n in enumerate(picks):
        x = by[n]; tag = ' (pick)' if i == 0 else ''
        lines.append(f'{n}. **{x["name"]}{tag}:** {x["what"]}. Engine: {engine_for(x)}. Best for: {x["best"]}.')
    others = [f'{x["n"]} {x["name"]}' for x in treatments if x['n'] not in picks]
    if others: lines.append('Other treatments: ' + ', '.join(others) + '.')
    return '\n'.join(lines)


def new_state(slug):
    return {'slug': slug, 'version': 1, 'stages': {}}


def next_stage(state, stages=STAGES):
    for s in stages:
        if state['stages'].get(s, {}).get('status') not in ('done', 'skipped'): return s
    return None


def invalidate(state, from_stage, stages=STAGES):
    """Reset `from_stage` and every later stage (keeps earlier work)."""
    if from_stage not in stages: raise ValueError(f'unknown stage {from_stage}')
    for s in stages[stages.index(from_stage):]: state['stages'].pop(s, None)
    if STAGES.index(from_stage) <= STAGES.index('preview'): state.pop('storyboard_approved', None); state.pop('preview_stills', None)
    if from_stage in ('brief', 'treatment'): state.pop('treatment', None); state.pop('engine', None)
    return state


def scenes_ready(project, template_project=None):
    """(ok, problems) for project.json scenes written by the agent."""
    probs = []; sc = project.get('scenes') or []
    if not sc: probs.append('project.json has no scenes')
    if project.get('_todo'): probs.append('project.json still has "_todo": ' + str(project['_todo']))
    if template_project and sc == template_project.get('scenes'): probs.append('scenes are still the template demo')
    for i, s in enumerate(sc):
        if not (s.get('vo') or '').strip() and not s.get('secs'): probs.append(f's{i:02d}: no "vo" and no "secs"')
    if 'TODO' in json.dumps(sc): probs.append('a scene still contains TODO')
    return (not probs, probs)


def missing_vo(project, d):
    return [i for i, s in enumerate(project.get('scenes', [])) if (s.get('vo') or '').strip()
            and not os.path.exists(os.path.join(d, 'vo', f's{i:02d}.wav'))]


def preview_times(timing, n=8):
    """Scene mid-points (plus the hook at 1 s), at most n, rounded to 0.1 s."""
    sc = timing.get('scenes') or []
    if not sc:
        D = float(timing.get('duration', 10)); return [round(D * (k + 0.5) / n, 1) for k in range(n)]
    mids = [round(s['t'] + s['d'] / 2, 1) if 't' in s else None for s in sc]
    if None in mids:
        t, mids = 0.0, []
        for s in sc: mids.append(round(t + s['d'] / 2, 1)); t += s['d']
    ts = [1.0] + mids
    if len(ts) > n:
        step = (len(ts) - 1) / (n - 1); ts = [ts[round(k * step)] for k in range(n)]
    return sorted(set(ts))


LOOK_KEYS = ('set', 'palette', 'character', 'type', 'captions', 'camera', 'signature', 'title_motion', 'captions_preset')


def project_skeleton(brief):
    W, H = FORMATS[brief['format']]
    return {'title': brief['topic'], 'language': brief['lang'], 'fps': 24 if brief['format'] == 'youtube' else 30,
            'width': W, 'height': H, 'aspect': [W // _gcd(W, H), H // _gcd(W, H)], 'credit': brief.get('credit') or '',
            'music_mood': 'calm', 'lufs': -14,
            'look': {k: 'CHANGE ME (docs/FRESH_LOOK.md)' for k in LOOK_KEYS}, '_todo': 'write scenes (see TODO_script.md)', 'scenes': []}


def _gcd(a, b):
    while b: a, b = b, a % b
    return a


# ---------------------------------------------------------------- runtime
class Ctx:
    def __init__(self, A):
        self.A = A; self.dry = A.dry_run
        self.pdir = os.path.abspath(A.projects_dir or os.path.join(ROOT, 'projects'))
        self.slug = A.slug or slugify(A.topic or '')
        self.d = os.path.join(self.pdir, self.slug)
        self.state_path = os.path.join(self.d, 'state.json')
        self.state = json.load(open(self.state_path)) if os.path.exists(self.state_path) else new_state(self.slug)

    def p(self, *a): return os.path.join(self.d, *a)

    def jload(self, *a, default=None):
        f = self.p(*a)
        try: return json.load(open(f, encoding='utf-8'))
        except Exception: return default

    def write(self, name, text):
        f = self.p(name)
        if self.dry: print(f'   [dry] would write {rel(f)}'); return f
        os.makedirs(os.path.dirname(f), exist_ok=True); open(f, 'w', encoding='utf-8').write(text); return f

    def jwrite(self, name, obj): return self.write(name, json.dumps(obj, indent=1, ensure_ascii=False) + '\n')

    def sh(self, cmd, env=None, check=True, cwd=None):
        shown = ' '.join(shlex.quote(c) for c in cmd)
        if env: shown = ' '.join(f'{k}={shlex.quote(v)}' for k, v in env.items()) + ' ' + shown
        print(f'   $ {shown.replace(ROOT + "/", "")}')
        if self.dry: return 0, ''
        r = subprocess.run(cmd, cwd=cwd or ROOT, env={**os.environ, **(env or {})}, capture_output=True, text=True)
        out = (r.stdout or '') + (r.stderr or '')
        if out.strip(): print('     ' + out.strip().replace('\n', '\n     ')[-3000:])
        if check and r.returncode != 0: raise StageFail(f'command failed ({r.returncode}): {shown}')
        return r.returncode, out

    def save(self):
        if self.dry: return
        os.makedirs(self.d, exist_ok=True)
        json.dump(self.state, open(self.state_path, 'w'), indent=1, ensure_ascii=False)

    def mark(self, stage, status, note=''):
        self.state['stages'][stage] = {'status': status, 'at': dt.datetime.now().isoformat(timespec='seconds'), 'note': note}
        self.save()

    @property
    def engine(self): return self.state.get('engine') or (self.A.engine if self.A.engine not in (None, 'auto') else None)

    @property
    def brief(self): return self.jload('brief.json', default={}) or {}


class StageFail(Exception): pass


class Stop(Exception):
    def __init__(self, kind, msg): super().__init__(msg); self.kind = kind; self.msg = msg


def rel(f):
    f = os.path.abspath(f); return os.path.relpath(f, ROOT) if f.startswith(ROOT + os.sep) else f


def py(script, *args): return [sys.executable, os.path.join(HERE, script), *map(str, args)]


def todo(c, stage, body):
    f = c.write(f'TODO_{stage}.md', f'# TODO: {stage} ({c.slug})\n\n{body.strip()}\n\nWhen done, re-run:\n\n    {resume_cmd(c)}\n')
    raise Stop('needs_agent', f'{stage}: agent work needed -> {rel(f)}')


def resume_cmd(c, extra=''):
    return f'python3 scripts/make_video.py --slug {c.slug}' + (f' --projects-dir {c.A.projects_dir}' if c.A.projects_dir else '') + extra


def clear_todo(c, stage):
    f = c.p(f'TODO_{stage}.md')
    if os.path.exists(f) and not c.dry: os.remove(f)


# ---------------------------------------------------------------- stages
def st_brief(c):
    A = c.A
    if not A.topic and not c.brief: raise StageFail('a topic is required for a new video: make_video.py "topic" ...')
    b = dict(c.brief)
    b.update({k: v for k, v in dict(topic=A.topic, format=A.format, lang=A.lang, tts=A.tts, voice=A.voice, credit=A.credit,
                                     engine_request=A.engine, length=A.length, style=A.style).items() if v is not None})
    b.setdefault('format', 'reel'); b.setdefault('lang', 'hi'); b.setdefault('tts', 'edge'); b.setdefault('voice', 'hi-IN-SwaraNeural')
    b.setdefault('engine_request', 'auto'); b['slug'] = c.slug; b['size'] = list(FORMATS[b['format']])
    b.setdefault('created', dt.date.today().isoformat())
    if not b.get('credit'): print('   note: no --credit given; the end card needs the name/handle exactly as the user wants it')
    c.jwrite('brief.json', b)
    return 'done', f'{b["format"]} {b["size"][0]}x{b["size"][1]}, lang {b["lang"]}, tts {b["tts"]}'


def st_treatment(c):
    T = parse_intake(open(os.path.join(ROOT, 'docs', 'INTAKE.md'), encoding='utf-8').read())
    b = c.brief or {'topic': c.A.topic or c.slug}
    n = c.A.treatment or c.state.get('treatment')
    if not n:
        picks = rank_treatments(b.get('topic', ''), T); menu = format_menu(b.get('topic', ''), T, picks)
        c.write('TREATMENT_MENU.md', menu + '\n')
        print('\n' + menu + '\n')
        raise Stop('needs_approval', f'send the menu to the user; then re-run with --treatment N:\n   {resume_cmd(c, " --treatment N")}')
    row = next((x for x in T if x['n'] == int(n)), None)
    if not row: raise StageFail(f'--treatment {n} is not in docs/INTAKE.md (1-{max(x["n"] for x in T)})')
    eng = engine_for(row, c.A.engine or b.get('engine_request') or 'auto', b.get('style') or c.A.style)
    c.state['treatment'] = int(n); c.state['engine'] = eng
    if c.brief: c.jwrite('brief.json', {**c.brief, 'treatment': int(n), 'treatment_name': row['name'], 'engine': eng})
    return 'done', f'{n} {row["name"]} -> engine {eng}'


SCRIPT_TODO = """Write the script for "{topic}" ({fmt}, {w}x{h}, language {lang}). Treatment {tn}: {tname}.
Read SKILL.md sections 1-3, docs/INTAKE.md ("After the pick"), docs/STYLES.md (pick ONE recipe) and docs/CRAFT.md section 2.

1. {target}
2. Hook in the first second, one idea per scene (8-14 s), structure: hook -> what you'll learn -> steps -> mistakes/rules -> recap -> outro with credit "{credit}".
3. Numbers as WORDS inside "vo" (TTS), digits only in "sub". Subtitle chunks <= 90 chars split with |.
4. Write ACTIONS.md: one row per VO sentence: `t | verb | object | close-up? | SFX`. A sentence with no on-screen verb gets rewritten.
5. Facts: list every value a human must verify in FACTS.md.
6. Remove the "_todo" key from project.json. No SVG anywhere.
7. Fill the "look" block in project.json (docs/FRESH_LOOK.md) BEFORE any asset: set, palette (3-5 hex), character, type,
   captions, camera, signature, title_motion, captions_preset (docs/TEXT_STYLES.md). Every video gets its own look; examples/ are a quality bar, never a template.
   Set "theme" from look.palette. lint.py fails "CHANGE ME", Pixar Clinic default colours and copied sets/mascots.
"""


def st_script(c):
    b, eng = c.brief, c.engine or 'template'
    W, H = FORMATS[b.get('format', 'reel')]
    common = dict(topic=b.get('topic'), fmt=b.get('format'), w=W, h=H, lang=b.get('lang'), tn=c.state.get('treatment'),
                  tname=(b.get('treatment_name') or ''), credit=b.get('credit') or '<ask the user>')
    if eng == 'vidliboom':
        if os.path.exists(c.p('script.md')) and os.path.exists(c.p('ACTIONS.md')): clear_todo(c, 'script'); return 'done', 'script.md'
        todo(c, 'script', SCRIPT_TODO.format(**common, target='Write script.md in the episode format of docs/EPISODE_SCRIPT.md '
                                             '(## Scene: name | bg=... | mood=..., SPEAKER [pose]: line). Example: examples/episode/bablu_mausam.md.'))
    if eng == 'screencast':
        S = c.jload('script.json')
        if S and (S.get('beats') or S.get('steps')) and os.path.exists(c.p('ACTIONS.md')) and 'TODO' not in json.dumps(S):
            clear_todo(c, 'script'); return 'done', 'script.json'
        todo(c, 'script', SCRIPT_TODO.format(**common, target='Write script.json for the screencast engine (docs/SCREENCAST.md; '
                                             'example: examples/screencast-wiki/script.json): browser steps + VO per beat.'))
    # project.json engines (template, motion2d, handdrawn, external)
    tpl = json.load(open(os.path.join(ROOT, 'template', 'project.json'), encoding='utf-8'))
    if not os.path.exists(c.p('project.json')):
        if eng == 'template':
            c.sh(['bash', os.path.join(HERE, 'new_project.sh'), c.d])
            if not c.dry:
                P = c.jload('project.json'); P.update({k: v for k, v in project_skeleton(b).items() if k not in ('scenes', 'title')})
                P['credit'] = b.get('credit') or P.get('credit'); c.jwrite('project.json', P)
        else:
            c.jwrite('project.json', project_skeleton(b))
            for f in ('fonts',):
                if not c.dry and not os.path.exists(c.p(f)): os.symlink(os.path.join(ROOT, f), c.p(f))
    P = c.jload('project.json', default={}) or {}
    ok, probs = scenes_ready(P, tpl)
    lk = P.get('look')
    look_ok = isinstance(lk, dict) and 'change me' not in json.dumps(lk).lower()
    if ok and look_ok and os.path.exists(c.p('ACTIONS.md')): clear_todo(c, 'script'); return 'done', f'{len(P["scenes"])} scenes'
    if ok: probs.append('ACTIONS.md (action sheet) missing')
    lk = P.get('look')
    if not isinstance(lk, dict) or 'change me' in json.dumps(lk).lower():
        probs.append('project.json "look" sheet not filled (docs/FRESH_LOOK.md)')
    todo(c, 'script', SCRIPT_TODO.format(**common, target='Fill project.json "scenes" (schema: docs/ENGINE.md; template/project.json has a '
                                         'working demo): each scene "vo" (spoken), "sub" (on screen), optional "chapter", "secs" when silent.')
         + '\nStill open:\n' + '\n'.join(f'- {p}' for p in probs))


def st_vo(c):
    eng = c.engine or 'template'
    if eng in OWNS_AUDIO: return 'skipped', f'{eng} voices its own script'
    b = c.brief; P = c.jload('project.json', default={}) or {}; tts = b.get('tts', 'edge')
    miss = missing_vo(P, c.d)
    if not miss: return 'done', 'all scene VO present'
    if tts == 'none':
        raise StageFail(f'--tts none but scenes {miss} have "vo" text; drop the text, add vo/sNN.wav yourself, or pick a TTS')
    if tts == 'cartesia':
        if not (os.environ.get('CARTESIA_API_KEY') and (os.environ.get('CARTESIA_VOICE_ID') or P.get('voice_id'))):
            raise StageFail('cartesia needs CARTESIA_API_KEY and CARTESIA_VOICE_ID (or project.json voice_id); or use --tts edge')
        c.sh(py('tts_cartesia.py', c.d))
    else:
        c.sh(py('tts_free.py', c.d, '--engine', 'edge', '--voice', b.get('voice') or 'hi-IN-SwaraNeural'))
    if not c.dry:
        miss = missing_vo(P, c.d)
        if miss: raise StageFail(f'VO still missing for scenes {miss}')
    return 'done', tts


def st_timing(c):
    if (c.engine or 'template') in OWNS_AUDIO: return 'skipped', 'engine owns timing'
    c.sh(py('build_timing.py', c.d))
    rc, out = c.sh(py('lint.py', c.d, '--pre-build'), check=False)
    if rc: raise StageFail('lint.py found errors; fix project.json and re-run (--redo timing)')
    P = c.jload('project.json', default={}) or {}
    if any((s.get('vo') or '').strip() for s in P.get('scenes', [])):
        rc, _ = c.sh(py('words_project.py', c.d), check=False)
        if rc: print('   warn: words_project.py failed; captions/chapters will lack word timings')
    return 'done', 'timing.json + lint passed'


BUILD_TODO = {
    'template': """Build the 3D world in index.html (SKILL.md section 5, docs/ENGINE.md, docs/CRAFT.md section 1):
- Replace buildSubject() (hero model from three.js primitives, physical materials) and SCENE_FX[i](u, S, t) per scene so the
  objects perform every verb in ACTIONS.md. Picture is a pure function of t (no Math.random/Date.now at render time).
- {vertical}
- Characters: painted raster pose packs (template/headrig3d.js, docs/CHARACTERS.md), never primitive or vector puppets.
- Check a few frames: python3 scripts/shot.py {d} 1 5 10""",
    'motion2d': """Build the motion2d scene (docs/MOTION2D.md, example motion2d/examples/chai/):
- Generate the style frame + cut-out raster layers (chroma key), props, and a pose pack (motion2d/posepack.py) per ACTIONS.md.
- Write {d}/render.py with this contract:
    PREVIEW=t1,t2,... python3 render.py   -> writes shots/tNNNN.N.jpg for those seconds (no video)
    python3 render.py                     -> writes video_only.mp4 ({w}x{h}, silent, length = timing.json duration)
  Read timing.json for scene starts and vo/*.words.json for word times. SFX: log them into project.json "sfx" for mix.py.""",
    'handdrawn': """Build the hand-drawn scene (docs/HANDDRAWN.md, handdrawn/hd.py, example handdrawn/examples/chai-doodle/):
- Generate raster line art in the chosen style pack (imageStylePrompt), DrawOn/boil/write_on per ACTIONS.md.
- Write {d}/render.py with the same contract as motion2d:
    PREVIEW=t1,t2 python3 render.py -> shots/tNNNN.N.jpg ;  python3 render.py -> video_only.mp4 ({w}x{h}, silent, timing.json length)""",
    'screencast': """Build the screencast project (docs/SCREENCAST.md, example examples/screencast-wiki/):
- host/ pose pack for the presenter (python3 -m screencast.make_pack host ...), generated per video (raster only).
- Check script.json steps run: python3 -m screencast capture {d}""",
    'vidliboom': """vidliboom builds everything from script.md (docs/EPISODE_SCRIPT.md). Check speakers/poses exist in vidliboom/assets
or generate new raster characters for this episode.""",
    'external': """This treatment uses an engine from another repo ({eng}). Fetch it: bash scripts/fetch_engine.sh {ename}
(see docs/ENGINES.md). Build the video there, then write {d}/render.py with the contract:
    PREVIEW=t1,t2 python3 render.py -> shots/*.jpg ;  python3 render.py -> video_only.mp4 (silent) or final.mp4 (with audio).""",
}


def build_ready(c, eng):
    probs = []
    if not os.path.exists(c.p('BUILD_READY')): probs.append('BUILD_READY marker missing (create it after you have looked at test frames)')
    if eng == 'template':
        try:
            if open(c.p('index.html'), 'rb').read() == open(os.path.join(ROOT, 'template', 'index.html'), 'rb').read():
                probs.append('index.html is still the untouched template')
        except OSError: probs.append('index.html missing')
    elif eng == 'screencast':
        if not os.path.isdir(c.p('host')): probs.append('host/ pose pack missing')
    elif eng == 'vidliboom':
        probs = [] if os.path.exists(c.p('script.md')) else ['script.md missing']
    elif not os.path.exists(c.p('render.py')): probs.append('render.py missing')
    for f in glob.glob(os.path.join(c.d, '**', '*.svg'), recursive=True): probs.append(f'SVG not allowed: {os.path.relpath(f, c.d)}')
    return probs


def st_build(c):
    eng = c.engine or 'template'; b = c.brief; W, H = FORMATS[b.get('format', 'reel')]
    probs = build_ready(c, eng)
    if not probs:
        if eng not in OWNS_AUDIO:
            rc, _ = c.sh(py('lint.py', c.d), check=False)
            if rc: raise StageFail('lint.py failed after build (SVG or project errors)')
        clear_todo(c, 'build'); return 'done', eng
    key = eng if eng in BUILD_TODO else 'external'
    vert = ('Vertical project: in index.html set H from the project (const H = P.height || ...) like examples/dhai-baje/, '
            'and keep labels clear of the bottom caption zone.' if H > W else 'Landscape 16:9 (template default).')
    body = BUILD_TODO[key].format(d=c.d, w=W, h=H, vertical=vert, eng=eng, ename=eng.split(':', 1)[-1])
    body += '\n\nRules: raster art only (no SVG, no vector doodles); objects act out every VO verb; a sound on every action.\n'
    body += 'Then: touch ' + c.p('BUILD_READY') + '\n\nStill open:\n' + '\n'.join(f'- {p}' for p in probs)
    todo(c, 'build', body)


def contact_sheet(files, out, label=None):
    from PIL import Image, ImageDraw
    ims = [Image.open(f).convert('RGB') for f in files]
    if not ims: return None
    vertical = ims[0].height > ims[0].width; tw, th = (270, 480) if vertical else (480, 270); cols = 4
    rows = (len(ims) + cols - 1) // cols; sheet = Image.new('RGB', (tw * cols, th * rows), 'black'); D = ImageDraw.Draw(sheet)
    for k, im in enumerate(ims):
        sheet.paste(im.resize((tw, th)), ((k % cols) * tw, (k // cols) * th))
        D.text(((k % cols) * tw + 8, (k // cols) * th + 8), os.path.basename(files[k]), fill='yellow')
    sheet.save(out, quality=85); return out


def final_path(c):
    for f in (c.p(f'{c.slug}.mp4'), c.p('final.mp4')):
        if os.path.exists(f): return f
    return c.p(f'{c.slug}.mp4')


def st_preview(c):
    eng = c.engine or 'template'
    sheet = c.p('shots', 'sheet.jpg')
    if not c.state.get('preview_stills') or not os.path.exists(sheet):
        T = c.jload('timing.json', default={}) or {}
        times = preview_times(T) if T else [1, 3, 6, 10, 15, 20]
        if eng == 'template':
            c.sh(py('shot.py', c.d, *times))
        elif eng == 'screencast':
            for st in ('capture', 'voice', 'build', 'sfx'): c.sh([sys.executable, '-m', 'screencast', st, c.d])
            c.sh([sys.executable, '-m', 'screencast', 'stills', c.d, '1', '3', '5', '7'])
        elif eng == 'vidliboom':
            fmt = {'reel': 'vertical', 'square': 'square'}.get(c.brief.get('format'), 'landscape')
            c.sh([sys.executable, '-m', 'vidliboom', c.p('script.md'), '-o', c.p('final.mp4'), '--format', fmt, '--lang', c.brief.get('lang', 'hi')])
            if not c.dry:
                os.makedirs(c.p('shots'), exist_ok=True)
                for t in times: c.sh(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(t), '-i', c.p('final.mp4'), '-frames:v', '1', c.p('shots', f't{t:06.1f}.jpg')], check=False)
        else:
            c.sh([sys.executable, c.p('render.py')], env={'PREVIEW': ','.join(str(t) for t in times)}, cwd=c.d)
        if not c.dry:
            files = sorted(f for f in glob.glob(c.p('shots', '*.jpg')) if not f.endswith('sheet.jpg'))
            if not files: raise StageFail('no preview stills were written to shots/')
            if not os.path.exists(sheet) or os.path.getmtime(sheet) < max(map(os.path.getmtime, files)): contact_sheet(files, sheet)
        c.state['preview_stills'] = True; c.save()
    if not (c.A.approve_storyboard or c.state.get('storyboard_approved')):
        raise Stop('needs_approval', f'LOOK at {rel(sheet)}, fix problems (log them in REVIEW.md), then send it to the USER. '
                   f'On their yes: {resume_cmd(c, " --approve-storyboard")}')
    c.state['storyboard_approved'] = True
    return 'done', 'storyboard approved'


def st_render(c):
    eng = c.engine or 'template'; b = c.brief; W, H = FORMATS[b.get('format', 'reel')]
    if eng == 'template':
        print('   note: CPU render ~1-4 s/frame/job; if your shell times out, re-run this; finished chunks are skipped')
        c.sh(py('render_all.py', c.d, '--jobs', c.A.jobs, '--chunk', 200, '--width', W))
    elif eng == 'screencast':
        c.sh([sys.executable, '-m', 'screencast', 'render', c.d, c.p('final.mp4'), '--jobs', str(c.A.jobs)])
    elif eng == 'vidliboom':
        if not os.path.exists(c.p('final.mp4')): raise StageFail('final.mp4 missing; --redo preview')
    else:
        c.sh([sys.executable, c.p('render.py')], cwd=c.d)
    if not c.dry and not (os.path.exists(c.p('video_only.mp4')) or os.path.exists(c.p('final.mp4'))):
        raise StageFail('render wrote neither video_only.mp4 nor final.mp4')
    return 'done', 'picture rendered'


def owns_audio(c):
    return (c.engine or 'template') in OWNS_AUDIO or (os.path.exists(c.p('final.mp4')) and not os.path.exists(c.p('video_only.mp4')))


def st_mix(c):
    if owns_audio(c): return 'skipped', 'final.mp4 already has audio'
    P = c.jload('project.json', default={}) or {}
    if P.get('music', True) is not False and not os.path.exists(c.p('music.wav')):
        c.sh(py('music.py', c.d, P.get('music_mood', 'calm')))
    c.sh(py('mix.py', c.d))
    return 'done', 'final_audio.wav'


def st_mux(c):
    if owns_audio(c):
        return 'skipped', 'final.mp4 from engine'
    b = c.brief; W, H = FORMATS[b.get('format', 'reel')]; P = c.jload('project.json', default={}) or {}
    if os.path.exists(c.p('words.json')):
        c.sh(py('chapters.py', c.d, c.p('words.json')), check=False)
        if not os.path.exists(c.p('captions.ass')):
            lk = P.get('look') if isinstance(P.get('look'), dict) else {}
            how = ['--project', c.d] if lk.get('captions_preset') else ['--style', 'pop']   # look.captions_preset wins (docs/TEXT_STYLES.md)
            c.sh(py('captions.py', c.p('words.json'), c.p('captions.ass'), '--w', W, '--h', H, *how), check=False)
    c.sh(py('mux.py', c.d, f'{c.slug}.mp4'))
    return 'done', f'{c.slug}.mp4' + (' (captions burned)' if P.get('burn_captions') else '')


def st_qa(c):
    f = final_path(c); P = c.jload('project.json', default={}) or {}
    args = [f] + ([c.p(P['burn_captions'])] if P.get('burn_captions') and str(P['burn_captions']).endswith('.ass') else [])
    rc, out = c.sh(py('qa.py', *args), check=False)
    if rc: raise StageFail('qa.py FAILED; fix and --redo the stage that caused it (mix for loudness, render for frames)')
    c.sh(py('motion_qa.py', f, '--at', '1', '-o', c.p('qa')), check=False)
    return 'done', 'QA PASSED (look at qa/ strips for characters)'


PACKAGE_TODO = """Write deliver/PACKAGE.md for the user (SKILL.md section 9):
- YouTube title (<= 70 chars, keyword first), description (paste chapters.txt if present), 10-15 tags,
  a social caption with hashtags, and the list of factual values a human must verify (from FACTS.md).
- Look at deliver/thumb.jpg; for a styled thumbnail use scripts/thumb.py (16:9) or make a better one.
Never post or publish anything on the user's behalf."""


def st_package(c):
    f = final_path(c); dd = c.p('deliver')
    if not c.dry:
        os.makedirs(dd, exist_ok=True)
        if os.path.exists(f): shutil.copyfile(f, os.path.join(dd, os.path.basename(f)))
        if os.path.exists(c.p('chapters.txt')): shutil.copyfile(c.p('chapters.txt'), os.path.join(dd, 'chapters.txt'))
        if os.path.exists(c.p('captions.srt')): shutil.copyfile(c.p('captions.srt'), os.path.join(dd, 'captions.srt'))
    if not os.path.exists(os.path.join(dd, 'thumb.jpg')):
        c.sh(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '1.0', '-i', f, '-frames:v', '1', '-q:v', '2', os.path.join(dd, 'thumb.jpg')], check=False)
    if c.A.variants and c.brief.get('format') == 'reel':
        src = c.d if (os.path.exists(c.p('video_only.mp4')) and os.path.exists(c.p('final_audio.wav'))) else f   # clean picture -> captions re-burned at size
        c.sh(py('reframe.py', src, '--to', c.A.variants, '-o', dd, '--stem', c.slug, '--title', c.brief.get('topic', '')), check=False)
    if os.path.exists(os.path.join(dd, 'PACKAGE.md')): clear_todo(c, 'package'); return 'done', f'delivered in {rel(dd)}'
    todo(c, 'package', PACKAGE_TODO)


RUN = dict(brief=st_brief, treatment=st_treatment, script=st_script, vo=st_vo, timing=st_timing, build=st_build, preview=st_preview,
           render=st_render, mix=st_mix, mux=st_mux, qa=st_qa, package=st_package)


def status(c):
    print(f'{c.slug}: {c.d}')
    for s in STAGES:
        x = c.state['stages'].get(s, {}); print(f'  {s:<10} {x.get("status", "-"):<15} {x.get("note", "")}')
    print('  next:', next_stage(c.state) or 'finished')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('topic', nargs='?'); ap.add_argument('--format', choices=list(FORMATS)); ap.add_argument('--engine', default=None,
                    choices=['auto'] + BUILTIN); ap.add_argument('--treatment', type=int); ap.add_argument('--style', choices=['2d', '3d'])
    ap.add_argument('--tts', choices=['edge', 'cartesia', 'none']); ap.add_argument('--voice'); ap.add_argument('--lang'); ap.add_argument('--credit')
    ap.add_argument('--length'); ap.add_argument('--slug'); ap.add_argument('--projects-dir'); ap.add_argument('--stop-after', choices=STAGES)
    ap.add_argument('--redo', choices=STAGES); ap.add_argument('--approve-storyboard', action='store_true'); ap.add_argument('--status', action='store_true')
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--variants'); ap.add_argument('--jobs', type=int, default=2)
    A = ap.parse_args(argv)
    if not A.topic and not A.slug: ap.print_usage(); print('need a topic (new video) or --slug (resume)'); return 2
    c = Ctx(A)
    if A.status: status(c); return 0
    if A.redo: invalidate(c.state, A.redo); c.save()
    if A.treatment and c.state.get('treatment') and A.treatment != c.state['treatment']:
        print(f'treatment changed {c.state["treatment"]} -> {A.treatment}: resetting from treatment'); invalidate(c.state, 'treatment'); c.save()
    print(f'== make_video: {c.slug}  ({rel(c.d)})' + ('  [DRY RUN: nothing is executed or written]' if c.dry else ''))
    if c.dry and not c.engine: print('   [dry] engine not chosen yet; later stages are planned as engine "template"')
    blocked = None
    for s in STAGES:
        cur = c.state['stages'].get(s, {}).get('status')
        if cur in ('done', 'skipped') and not (s == 'brief' and A.topic and not c.dry and any(
                getattr(A, k) is not None for k in ('format', 'lang', 'tts', 'voice', 'credit', 'length', 'style'))):
            print(f'-- {s}: {cur}'); continue
        print(f'-> {s}')
        try:
            st, note = RUN[s](c); c.mark(s, st, note)
            print(f'   [dry] planned (after the stops above): {st}' if c.dry and blocked else f'   {st}: {note}')
        except Stop as e:
            if not c.dry:
                c.mark(s, e.kind, e.msg); print(f'\nSTOPPED at {s} ({e.kind}): {e.msg}'); return 0
            print(f'   [dry] would stop here ({e.kind}): {e.msg}'); blocked = blocked or s
        except StageFail as e:
            if not c.dry: c.mark(s, 'failed', str(e)); print(f'\nFAILED at {s}: {e}'); return 1
            print(f'   [dry] would fail: {e}'); blocked = blocked or s
        except Exception as e:
            if not c.dry: c.mark(s, 'failed', repr(e)); print(f'\nFAILED at {s}: {e!r}'); return 1
            print(f'   [dry] {s} could not be planned yet ({e.__class__.__name__}: {e}); depends on earlier stages')
            blocked = blocked or s
        if A.stop_after == s: print(f'\nstopped after {s} (--stop-after)'); return 0
    if c.dry: print(f'\n[dry] first blocking stage: {blocked or "none"}'); return 0
    print(f'\nDONE: {final_path(c)}  (deliverables in {c.p("deliver")})'); return 0


if __name__ == '__main__':
    sys.exit(main())
