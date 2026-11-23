"""Talking-character whiteboard explainer (demo: hypnic jerk, Hinglish).
Usage: python3 render.py <start_frame> <end_frame> <out.mp4>   (render in 2 chunks, then concat + mux mix.wav)
       python3 render.py 0 0 <dir> <t1> <t2> ...                 (preview stills)
Lip-sync: uses ./align.json (python3 ../../../scripts/align.py --project .) when it matches timeline.json, else loudness.
       --lipsync align|loudness|auto (default auto; align = build align.json if missing/stale)"""
import sys, os, json, math
if '--lipsync' in sys.argv: _i = sys.argv.index('--lipsync'); os.environ['VD_LIPSYNC'] = sys.argv[_i + 1]; del sys.argv[_i:_i + 2]
PROJ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from hd import *

W, H = 720, 1280
S = load_style('whiteboard-multi'); C = S['colors']
TL = json.load(open(f'{PROJ}/timeline.json')); FPS = TL['fps']; DUR = TL['duration']
SEG = TL['segs']; WORDS = TL['words']; MOUTH = TL['mouth']
sys.path.append(os.path.join(PROJ, '..', '..', '..', 'scripts')); from align import project_track
LIP, _aw = project_track(PROJ, TL, {'rest', 'A', 'O'})   # aligned visemes (E->A, M->rest) + word times, or (None, None)
if _aw: WORDS = _aw
A = f'{PROJ}/assets'
BG = paper(W, H, S)

# ---------- character: base + painted face patches (diff regions of the image edits) ----------
CH_SCALE = .62
def load(n): return Image.open(f'{A}/{n}.png').convert('RGBA')
base = load('char_base')
def patch(n):
    v = load(n); d = np.abs(np.array(v, np.int16)[..., :3] - np.array(base, np.int16)[..., :3]).sum(-1)
    m = (d > 60).astype(np.uint8); m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.nonzero(m[100:600, 200:700]); x0, x1, y0, y1 = xs.min() + 200 - 8, xs.max() + 200 + 8, ys.min() + 100 - 8, ys.max() + 100 + 8
    out = base.copy(); out.paste(v.crop((x0, y0, x1, y1)), (x0, y0)); return out
def sc(im): return np.array(im.resize((int(im.width * CH_SCALE), int(im.height * CH_SCALE)), Image.LANCZOS)).astype(np.float32)
CHAR = {'rest': sc(base), 'A': sc(patch('char_mA')), 'O': sc(patch('char_mO'))}
blink_im = patch('char_blink')
CHAR_BLINK = sc(blink_im)

def mouth_at(t):
    if LIP: return LIP[min(int(t * FPS), len(LIP) - 1)]
    k = int(t * FPS); lv = MOUTH[k] if k < len(MOUTH) else 0
    lv2 = MOUTH[k - 1] if 0 < k < len(MOUTH) else 0; v = (lv + lv2) / 2
    if v > .38: return 'A'
    if v > .14: return 'O'
    return 'rest'
BLINKS = [1.7 + i * 3.3 + (i * 0.77 % 1.1) for i in range(20)]
def blinking(t): return any(b <= t < b + .12 for b in BLINKS)

def speaking(t): return any(s['start'] <= t <= s['end'] for s in SEG)

# ---------- scene art ----------
def fit(path, bw, bh):
    im = Image.open(path); s = min(bw / im.width, bh / im.height); return DrawOn(path, scale=s)
ART_BOX = (640, 470)
ART = {i: fit(f'{A}/{n}.png', *ART_BOX) for i, n in enumerate(['s0_bed', 's1_crowd', 's2_muscle', 's3_brain', 's4_alarm', 's5_triggers'])}
LABELS = ['Sote waqt JHATKA kyun?', 'HYPNIC JERK', 'Muscles dheeli', 'Dimaag confuse!', 'Body ko ALERT!', 'Chai + Stress + Thakaan', 'Bilkul NORMAL hai']
ACC = S['sceneAccents']
LBL = []
for i, txt in enumerate(LABELS):
    f = font(S, 'title', 62 if len(txt) < 16 else (50 if len(txt) < 20 else 42))
    im = text_img(txt, f, hexc(C['ink'])); LBL.append(im)

def scene_at(t):
    cur = 0
    for s in SEG:
        if t >= s['start'] - .35: cur = s['i']
    return cur

def frame(t):
    f = BG.copy()
    i = scene_at(t); s0 = SEG[i]['start'] - .35; u = t - s0
    nxt = SEG[i + 1]['start'] - .35 if i + 1 < len(SEG) else DUR
    out = ease((t - (nxt - .28)) / .28) if i + 1 < len(SEG) else 0  # erase before next scene
    acc = ACC[i % len(ACC)]
    end_t = SEG[-1]['end'] + .2
    if t >= end_t:
        end_card(f, S, ease((t - end_t) / 1.3), 'Swapnil Agrawal', '(BDS intern)')
        return f
    # label + marker swipe
    lb = LBL[i]; lx = (W - lb.shape[1]) / 2; ly = 70
    sw = marker_swipe(lb.shape[1] + 30, int(lb.shape[0] * .75), hexc(acc['swipe'], 220), ease((u - .9) / .45), seed=i + 3)
    over(f, boil(sw, t, .6, seed=i), lx - 15, ly + lb.shape[0] * .2, 1 - out)
    over(f, boil(write_on(lb, ease((u - .05) / .8)), t, .8, seed=i + 9), lx, ly, 1 - out)
    # art: pen draw-on, settle bob
    if i in ART:
        a = ART[i]; p = ease(u / 1.7)
        im = boil(a.frame(p), t, 1.3, seed=i + 20)
        bob = math.sin(u * 2.2) * 4 * min(1, u / 2)
        if i == 0: bob += -abs(math.sin(min(max(u - 3.6, 0), 1) * math.pi)) * 30  # the jolt
        if i == 4 and u > 1.8: bob += math.sin(u * 40) * 3 * max(0, 1 - (u - 1.8) / 1.2)
        over(f, im, (W - im.shape[1]) / 2, 175 + (ART_BOX[1] - im.shape[0]) / 2 + bob, 1 - out)
    else:  # last scene: big character centred handled below; draw a pen tick-mark row of label only
        pass
    # character
    m = mouth_at(t) if speaking(t) else 'rest'
    ch = CHAR_BLINK if (blinking(t) and m == 'rest') else CHAR[m]
    breath = 1 + .008 * math.sin(t * 2 * math.pi / 3.2)
    talk = math.sin(t * 9) * 2.5 if speaking(t) else 0
    hop = -max(0, math.sin(min(max(u, 0), .35) / .35 * math.pi)) * 14 if u < .35 and i > 0 else 0
    big = i == len(SEG) - 1
    chs = ch
    if big:
        g = 1 + .35 * ease(u / .6)
        chs = cv2.resize(ch, (int(ch.shape[1] * g), int(ch.shape[0] * g)), interpolation=cv2.INTER_LINEAR)
    if breath != 1:
        chs = cv2.resize(chs, (chs.shape[1], int(chs.shape[0] * breath)), interpolation=cv2.INTER_LINEAR)
    cy = (770 if not big else 770 - 420 * ease(u / .6)) + talk + hop
    over(f, chs, (W - chs.shape[1]) / 2, cy)
    # captions
    karaoke(f, [w for w in WORDS], t, {**S, 'colors': {**C, 'accent': acc['karaoke']}}, 700 if not big else 1180, size=52)
    # intro fade from paper
    if t < .25: f[:] = (BG * (1 - t / .25) + f * (t / .25)).astype(np.uint8)
    return f

if __name__ == '__main__':
    a, b, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    b = min(b, int(DUR * FPS))
    if len(sys.argv) > 4:  # stills
        for tt in sys.argv[4:]:
            Image.fromarray(frame(float(tt))).save(f'{out}/still_{tt}.png')
    else:
        encode((frame(k / FPS) for k in range(a, b)), out, W, H, FPS)
        print('wrote', out, a, b)
