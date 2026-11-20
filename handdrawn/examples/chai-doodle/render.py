"""Demo: 9 s hand-drawn reel in any style pack. python3 render.py [style] [out.mp4]
Title writes on + marker swipe, kettle and kulhad draw themselves with the pen, line boil throughout, end card."""
import sys, os
EX = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(EX, '..', '..'))
from hd import *
STYLE = sys.argv[1] if len(sys.argv) > 1 else 'swap-edu'; OUT = sys.argv[2] if len(sys.argv) > 2 else f'/tmp/hd_{STYLE}.mp4'
W, H, FPS, DUR = 720, 1280, 30, 9.0
S = load_style(STYLE); C = S['colors']
A = os.path.join(EX, '..', '..', '..', 'motion2d', 'examples', 'chai', 'assets')
BG = paper(W, H, S)
kettle = DrawOn(f'{A}/kettle.png', scale=420 / Image.open(f'{A}/kettle.png').width)
kulhad = DrawOn(f'{A}/kulhad.png', scale=300 / Image.open(f'{A}/kulhad.png').width)
title = text_img('Chai kaise', font(S, 'title', 96), hexc(C['ink']))
title2 = text_img('banti hai?', font(S, 'title', 96), hexc(C['ink']))
sw = marker_swipe(title2.shape[1] + 30, int(title2.shape[0] * .8), hexc(C['accent'], 230), 1)
deco = [p for p in S.get('decorations', []) if os.path.exists(os.path.join(EX, '..', '..', p))]
deco_im = DrawOn(os.path.join(EX, '..', '..', deco[0]), scale=.35) if deco else None
words = [{'word': w, 'start': s, 'end': e} for w, s, e in [('Pehle', 3.0, 3.4), ('paani', 3.4, 3.8), ('ubaalo,', 3.8, 4.4), ('phir', 4.6, 4.9), ('kulhad', 4.9, 5.4), ('mein', 5.4, 5.7), ('daalo!', 5.7, 6.3)]]

def frame(t):
    f = BG.copy()
    if t < 7.0:
        over(f, boil(write_on(title, ease((t - .2) / 1.0)), t, .8), (W - title.shape[1]) / 2, 120)
        over(f, boil(marker_swipe(sw.shape[1], sw.shape[0], hexc(C['accent'], 230), ease((t - 1.3) / .5)), t, .6, seed=2), (W - sw.shape[1]) / 2, 250)
        over(f, boil(write_on(title2, ease((t - 1.0) / 1.0)), t, .8, seed=1), (W - title2.shape[1]) / 2, 235)
        k = boil(kettle.frame(ease((t - 1.6) / 2.6)), t, 1.4, seed=3); over(f, k, 60, 430)
        q = boil(kulhad.frame(ease((t - 3.6) / 2.0)), t, 1.4, seed=4); over(f, q, W - 340, 760)
        if deco_im is not None: over(f, boil(deco_im.frame(ease((t - 5.4) / 1.0)), t, 1.2, seed=5), 40, 980)
        karaoke(f, words, t, S, H - 140, size=56)
        fade = ease((t - 6.6) / .4)
        if fade > 0: f[:] = (f * (1 - fade) + BG * fade).astype(np.uint8)
    else:
        end_card(f, S, ease((t - 7.0) / 1.4), 'Swapnil Agrawal', '(BDS intern)')
    return f

if __name__ == '__main__':
    encode((frame(i / FPS) for i in range(int(DUR * FPS))), OUT, W, H, FPS); print('wrote', OUT)
