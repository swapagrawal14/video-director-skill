"""Desi flat illustration sample: masala chai pour. Objects act: kettle swings in, tilts, pours high, cup fills, elaichi drops, steam curls."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from common import *
FPS = 24
TXT = json.load(open(HERE + '/../lines.json'))['chai'] if os.path.exists(HERE + '/../lines.json') else open(HERE + '/assets/line.txt').read()
PRE = 0.3; VO = vo_info(HERE); DUR = PRE + VO + 0.9
T = lambda w: word_time(TXT, w, VO, PRE)
tPour, tHigh, tKul, tPinch, tSteam, tEnd = T('Pour'), T('high'), T('kulhad'), T('pinch'), T('curl'), T("and that's")
CS = 0.72; CUP = load(HERE, 'kulhad', CS); KS = 0.6; KET = load(HERE, 'kettle', KS)
CX, CY = 1230, 740
MX, MY = CX - CUP.width / 2 + 242 * CS, CY - CUP.height / 2 + 82 * CS; MAX_, MAY = 209 * CS, 62 * CS
KPIV = (330 * KS, 430 * KS); KTIP = (684 * KS, 203 * KS)
TITLE = label('masala chai', 96, (130, 28, 34)); SUB = label('the desi way', 52, (176, 96, 40), wght=500)
EV = [(0.1, 'whoosh'), (0.55, 'squish'), (0.4, 'pop'), (1.0, 'pop')]
rng = random.Random(3); drops = []; pods = []
OUT = (38, 22, 18)
def chai_col(f): return (60, 105, 170)  # BGR chai brown
def draw_pod(fr, x, y, r):
    im = Image.new('RGBA', (60, 60), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([16, 22, 44, 38], fill=(150, 170, 80, 255), outline=OUT + (255,), width=3); d.line([22, 30, 38, 30], fill=(100, 120, 50, 255), width=2)
    paste(fr, im.rotate(r, expand=False), x, y)
def kettle_state(t):
    # returns pivot pos, rotation
    if t < 1.0: return None
    home = (MX - 380, MY - 250)
    if t < tPour:
        k = back((t - 1.0) / 0.8); x = -300 + (home[0] + 300) * k; y = home[1] - 160 * math.sin(min(1, (t - 1.0) / 0.8) * math.pi) 
        return (x, y + 8 * math.sin(t * 4)), 6 * (1 - k)
    if t < tPinch - 0.3:
        u = ease((t - tPour) / 0.5); rot = -38 * u
        high = 110 * ease((t - tHigh) / 0.6) * (1 - ease((t - (tPinch - 0.9)) / 0.6))
        return (home[0] + 4 * math.sin(t * 9), home[1] - high), rot + 1.5 * math.sin(t * 7)
    k = ease((t - (tPinch - 0.3)) / 0.7)
    return (home[0] - 900 * k, home[1] - 300 * k), -38 * (1 - k) - 15 * k
def draw(fr, t, step):
    global drops
    # title
    if t > 0.4:
        s = pop_scale(int((t - 0.4) * 12)); paste(fr, xform(TITLE, s, s), 640, 560)
    if t > 1.0:
        s = pop_scale(int((t - 1.0) * 12)); paste(fr, xform(SUB, s, s), 640, 635)
    # cup drop-in
    if t < 0.55: cy = -300 + (CY + 300) * ease_in(t / 0.55); sx, sy = 1, 1.08
    else: cy = CY; sx, sy = squash(t - 0.55, 0.07, 18, 5)
    if t > tEnd + 0.2:
        k = t - (tEnd + 0.2); cy -= abs(math.sin(min(k, 1.2) / 0.6 * math.pi)) * 30 * math.exp(-k * 1.5)
    dy = cy - CY
    sh = Image.new('RGBA', (CUP.width + 80, 70), (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse([20, 15, CUP.width + 60, 55], fill=(90, 40, 30, 70))
    if t > 0.3: paste(fr, sh.filter(ImageFilter.GaussianBlur(8)), CX, CY + CUP.height / 2 - 10)
    paste(fr, xform(CUP, sx, sy), CX, cy + CUP.height * (1 - sy) / 2)
    # fill level
    f = 0.0
    if t > tPour + 0.55: f = min(0.92, (t - (tPour + 0.55)) / (tPinch - 0.4 - tPour - 0.55) * 0.92)
    if f > 0:
        ax, ay = MAX_ * (0.62 + 0.36 * f), MAY * (0.5 + 0.48 * f); cyy = MY + dy + (1 - f) * MAY * 0.55
        cv2.ellipse(fr, (int(MX), int(cyy)), (int(ax), int(ay)), 0, 0, 360, (55, 100, 165), -1, cv2.LINE_AA)
        cv2.ellipse(fr, (int(MX - ax * 0.25), int(cyy - ay * 0.25)), (int(ax * 0.35), int(ay * 0.22)), 0, 0, 360, (110, 160, 215), -1, cv2.LINE_AA)
    # kettle + stream
    ks = kettle_state(t)
    if ks:
        (px, py), rot = ks
        place_pivot(fr, KET, px, py, KPIV, rot, shadow=(0.18, 10, 14, 26))
        vx, vy = rot_vec(KTIP[0] - KPIV[0], KTIP[1] - KPIV[1], rot); tx, ty = px + vx, py + vy
        if tPour + 0.45 < t < tPinch - 0.35:
            ex, ey = MX + 6 * math.sin(t * 13), MY + dy + MAY * 0.2
            pts = []
            for i in range(21):
                u = i / 20; x = tx + (ex - tx) * u + 35 * math.sin(u * math.pi) * (1 - u); y = ty + (ey - ty) * u ** 1.6
                x += 3 * math.sin(t * 25 + u * 9) * u; pts.append((x, y))
            pts = np.array(pts, np.int32)
            cv2.polylines(fr, [pts], False, OUT[::-1], 20, cv2.LINE_AA); cv2.polylines(fr, [pts], False, (55, 100, 165), 13, cv2.LINE_AA)
            cv2.polylines(fr, [pts + np.array([-3, 0])], False, (110, 160, 215), 3, cv2.LINE_AA)
            if step % 2 == 0:
                for _ in range(2): drops.append([ex, ey, rng.uniform(-7, 7), rng.uniform(-12, -5), 0])
            if step % 18 == 0: EV.append((t, 'pour'))
    # splash drops
    nd = []
    for d_ in drops:
        d_[0] += d_[2]; d_[1] += d_[3]; d_[3] += 1.6; d_[4] += 1
        if d_[4] < 12:
            cv2.circle(fr, (int(d_[0]), int(d_[1])), 6, OUT[::-1], -1, cv2.LINE_AA); cv2.circle(fr, (int(d_[0]), int(d_[1])), 4, (55, 100, 165), -1, cv2.LINE_AA); nd.append(d_)
    drops = nd
    # elaichi pods
    for i in range(3):
        t0 = tPinch + 0.15 + i * 0.28
        if t0 < t < t0 + 0.55:
            u = (t - t0) / 0.5; x = MX - 40 + i * 40; y = -40 + (MY + dy + 10 + 40) * ease_in(min(1, u))
            if u < 1: draw_pod(fr, x, y, (t - t0) * 500 + i * 60)
            if abs(t - (t0 + 0.5)) < 0.5 / FPS: EV.append((t, 'plip'))
        if t0 + 0.5 < t < t0 + 1.1:
            k = (t - t0 - 0.5) / 0.6; x = MX - 40 + i * 40
            cv2.ellipse(fr, (int(x), int(MY + dy + 12)), (int(10 + 40 * k), int(4 + 12 * k)), 0, 0, 360, tuple(int(c * (1 - k) + c2 * k) for c, c2 in zip((140, 190, 230), (55, 100, 165))), 2, cv2.LINE_AA)
    # steam
    if t > tSteam - 0.2:
        a = min(1, (t - tSteam + 0.2) / 0.8)
        ov = fr.copy()
        for i in range(3):
            pts = []
            for j in range(26):
                u = j / 25; ph = t * 2.2 + i * 2
                x = MX - 60 + i * 60 + 22 * math.sin(u * 7 - ph) * u; y = MY + dy - 20 - u * 260 * a - (i % 2) * 20
                pts.append((x, y))
            cv2.polylines(ov, [np.array(pts, np.int32)], False, (150, 150, 170), 7, cv2.LINE_AA)
        fr[:] = fr * (1 - 0.55 * a) + ov * 0.55 * a
    # sparkles at end
    if t > tEnd + 0.3:
        k = (t - tEnd - 0.3)
        for i, (ox, oy) in enumerate([(-230, -120), (220, -160), (260, 40), (-260, 60)]):
            s = max(0, math.sin(k * 3 + i)) * 22
            if s > 2:
                x, y = CX + ox, CY + oy
                cv2.line(fr, (int(x - s), int(y)), (int(x + s), int(y)), (60, 150, 230), 4, cv2.LINE_AA); cv2.line(fr, (int(x), int(y - s)), (int(x), int(y + s)), (60, 150, 230), 4, cv2.LINE_AA)
        if abs(k) < 0.5 / FPS: EV.append((t, 'boing'))
if __name__ == '__main__':
    run(HERE, DUR, FPS, draw, EV, PRE)
