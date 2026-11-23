"""Compose a 9:16 screencast tutorial reel: graph-paper desk, torn-strip title, tilted taped screen card
playing the capture (auto zoom to the action, eased cursor, click bursts, marker circles), a painted talking
host with gesture poses on hard cuts, karaoke captions and a follow-badge outro. Raster only, never SVG.

Inputs (all files in one project dir):
  script.json   {"title", "style"?, "end": {"name","handle"}, "beats": [{"vo","sub"?,"pose","zoom"?,"circle"?,"step"?,"after_click"?: "out"}], "steps": [...]}
                beat k plays capture time [mark k, mark k+1] (first beat starts at 0, last runs to the end):
                put exactly len(beats)-1 {"mark": ...} steps in "steps".
  capture/capture.json + capture/frames/     from screencast.capture
  timeline.json                               from screencast.__main__ build (VO-driven beat times, words, mouth levels)
  host/pack.json                              from screencast.make_pack host
"""
import os, sys, json, math
import numpy as np, cv2
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'handdrawn'))
from hd import load_style, font, text_img, write_on, karaoke, over, ease, hexc, encode  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screencast import fx  # noqa: E402

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
W, H = 720, 1280
CARD_W = 668                 # on-screen card width (px) incl. border
CARD_Y = 315                 # card centre y
ZOOM = 1.9
CAP_LEAD = .35               # capture starts moving this long after the beat starts
MIN_SPEED = .6               # a short span is slowed (down to 0.6x) to fill its VO, then holds


def back(x, s=1.7):
    x = min(1, max(0, x)) - 1
    return 1 + x * x * ((s + 1) * x + s)


def rgba(path, max_side=None):
    im = Image.open(path).convert('RGBA')
    if max_side and max(im.size) > max_side:
        k = max_side / max(im.size); im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    return np.array(im).astype(np.float32)


def scaled(a, k):
    if abs(k - 1) < 1e-3: return a
    return cv2.resize(a, (max(1, int(a.shape[1] * k)), max(1, int(a.shape[0] * k))), interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)


def rotate(a, deg):
    h, w = a.shape[:2]; M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1)
    c, s = abs(M[0, 0]), abs(M[0, 1]); nw, nh = int(h * s + w * c), int(h * c + w * s)
    M[0, 2] += nw / 2 - w / 2; M[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(a, M, (nw, nh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


class Reel:
    def __init__(self, proj):
        self.p = proj
        self.S = json.load(open(f'{proj}/script.json'))
        self.T = json.load(open(f'{proj}/timeline.json'))
        self.C = json.load(open(f'{proj}/capture/capture.json'))
        self.fps = self.T['fps']; self.dur = self.T['duration']
        self.style = load_style(self.S.get('style', 'whiteboard-multi')); self.col = self.style['colors']
        self.frames_dir = f'{proj}/capture/frames'; self.cap_fps = self.C['fps']; self.cap_n = self.C['n_frames']
        ev = self.C['events']
        marks = [e['t'] for e in ev if e['type'] == 'mark']
        nb = len(self.S['beats'])
        if len(marks) != nb - 1:
            raise SystemExit(f'script has {nb} beats but capture has {len(marks)} marks (need {nb - 1})')
        cap_end = self.cap_n / self.cap_fps
        self.spans = list(zip([0.] + marks, marks + [cap_end]))
        self.segs = self.T['segs']
        # beat windows on the final timeline: from (start - gap/2) to next start
        self.win = []
        for k, s in enumerate(self.segs):
            a = 0 if k == 0 else (self.segs[k - 1]['end'] + s['start']) / 2
            b = (s['end'] + self.segs[k + 1]['start']) / 2 if k + 1 < len(self.segs) else s['end'] + .3
            self.win.append((a, b))
        self.end_t = self.win[-1][1]
        # boxed events per beat (in capture time)
        self.events = [e for e in ev if e.get('box') and e['type'] in ('click', 'type', 'hover', 'scroll_to')]
        self.vw, self.vh = Image.open(f'{self.frames_dir}/00000.png').size
        self.card_scale = (CARD_W - 24) / self.vw
        self.fx = {'camera': True, 'transitions': True, 'captions': 'box', 'finish': True, **self.S.get('fx', {})}
        self.cuts = [(self.win[k][0], self.S['beats'][k].get('transition', fx.ROTATION[(k - 1) % len(fx.ROTATION)])) for k in range(1, len(self.win))]
        self.cuts.append((self.end_t, self.S.get('outro_transition', 'zoomblur')))
        self._load_art()

    # ------------------------------------------------------------------ assets
    def _load_art(self):
        self.paper = cv2.resize(np.array(Image.open(f'{ASSETS}/graphpaper.jpg').convert('RGB')), (W, H), interpolation=cv2.INTER_AREA)
        rot = self.S.get('backgrounds', fx.BG_ROTATION if self.fx.get('bg_rotate', True) else ['graph'])
        self.bg_kind = [self.S['beats'][k].get('bg', rot[k % len(rot)]) for k in range(len(self.S['beats']))] + [self.S.get('outro_bg', 'sun')]
        self._bgs = {k: fx.make_bg(k, W, H, self.paper) for k in set(self.bg_kind)}
        self.torn = rgba(f'{ASSETS}/torn_strip.png', 760)
        self.tape = rgba(f'{ASSETS}/tape.png', 200)
        self.cursor = rgba(f'{ASSETS}/cursor_hand.png', 64)
        self.burst = rgba(f'{ASSETS}/click_burst.png', 120)
        self.circle = rgba(f'{ASSETS}/marker_circle.png')
        self.badge = rgba(f'{ASSETS}/follow_badge.png', 460)
        self.hl = rgba(f'{ASSETS}/highlighter.png', 260)
        self.arrow = rgba(f'{ASSETS}/marker_arrow.png', 170)[:, ::-1].copy()   # flipped to point back at the badge
        self.play = fx.sketch_play_sticker(150)
        self._stickers = {}
        hp = f'{self.p}/host'; pk = json.load(open(f'{hp}/pack.json'))
        self.host_k = self.S.get('host_scale', .46)
        self.poses = {k: rgba(f'{hp}/{v}') for k, v in pk['poses'].items()}
        self.mouth = {k: (rgba(f"{hp}/{v['file']}"), v['x'], v['y']) for k, v in pk['mouth'].items()}
        self.blink = (rgba(f"{hp}/{pk['blink']['file']}"), pk['blink']['x'], pk['blink']['y']) if 'blink' in pk else None
        sz = 48
        while sz > 22:
            self.title = text_img(self.S['title'], font(self.style, 'title', sz), hexc(self.col['ink']))
            if self.title.shape[1] <= self.torn.shape[1] - 110: break
            sz -= 2
        lbl = text_img(self.S.get('follow_text', 'FOLLOW'), font(self.style, 'title', 64), (255, 255, 255, 255), stroke=3, stroke_color=hexc(self.col['ink']))
        bx, by = self.badge.shape[1] / 2 - lbl.shape[1] / 2, self.badge.shape[0] / 2 - lbl.shape[0] / 2 - 6
        self.badge = self.badge.copy(); over_rgba(self.badge, lbl, bx, by)
        self.step_imgs = {}
        for b in self.S['beats']:
            if b.get('step'):
                self.step_imgs[b['step']] = text_img(f"STEP {b['step']}", font(self.style, 'title', 40), hexc(self.col['ink']))

    # ------------------------------------------------------------------ timing
    def beat_at(self, t):
        for k, (a, b) in enumerate(self.win):
            if t < b: return k
        return len(self.win) - 1

    def cap_time(self, t):
        """Final-timeline t -> capture time. Each beat plays its span at 1x after CAP_LEAD, then holds;
        a span longer than the window is sped up to fit."""
        k = self.beat_at(t); a, b = self.win[k]; c0, c1 = self.spans[k]
        avail = max(.1, (b - a) - CAP_LEAD - .15); span = c1 - c0
        speed = max(MIN_SPEED, span / avail)
        return min(c1 - 1.0 / self.cap_fps, c0 + max(0, t - a - CAP_LEAD) * speed), k

    def to_final(self, ct, k):
        a, b = self.win[k]; c0, c1 = self.spans[k]
        avail = max(.1, (b - a) - CAP_LEAD - .15); speed = max(MIN_SPEED, (c1 - c0) / avail)
        return a + CAP_LEAD + (ct - c0) / speed

    def frame_img(self, ct):
        i = min(self.cap_n - 1, max(0, int(round(ct * self.cap_fps))))
        return np.array(Image.open(f'{self.frames_dir}/{i:05d}.png').convert('RGB')).astype(np.float32)

    def beat_events(self, k):
        c0, c1 = self.spans[k]
        return [e for e in self.events if c0 - 1e-3 <= e['t'] < c1 - 1e-3]

    @staticmethod
    def target(e):
        x, y, w, h = e['box']
        if e['type'] == 'type': return x + min(w * .5, 40 + 9 * len(e.get('text', ''))), y + h * .55
        return x + w / 2, y + h / 2

    # ------------------------------------------------------------------ layers
    def card(self, t):
        ct, k = self.cap_time(t); beat = self.S['beats'][k]; img = self.frame_img(ct)
        for bx in self.S.get('blur', []) + beat.get('blur', []):   # redact emails, names, keys: [x, y, w, h] in capture px
            x, y, w, h = map(int, bx); x0_, y0_ = max(0, x), max(0, y)
            if w > 0 and h > 0: img[y0_:y + h, x0_:x + w] = cv2.GaussianBlur(img[y0_:y + h, x0_:x + w], (0, 0), max(6, h / 3))
        evs = self.beat_events(k)
        # zoom window
        z = 1
        if beat.get('zoom', True) and evs:
            a, b = self.win[k]
            zin = ease((t - a) / .5); zout = 1 - ease((t - (b - .35)) / .35) if k + 1 < len(self.win) else 1
            clicks = [self.to_final(e['t'], k) for e in evs if e['type'] == 'click']
            if clicks and beat.get('after_click') == 'out' and t > clicks[-1] + .35: zout = min(zout, 1 - ease((t - clicks[-1] - .35) / .45))
            z = 1 + (ZOOM - 1) * zin * zout
            # follow the most recent (or upcoming) event in this beat
            cur = evs[0]
            for e in evs:
                if e['t'] <= ct + .2: cur = e
            fx, fy = self.target(cur)
        else:
            fx, fy = self.vw / 2, self.vh / 2
        cw, ch = self.vw / z, self.vh / z
        x0 = min(max(0, fx - cw / 2), self.vw - cw); y0 = min(max(0, fy - ch / 2), self.vh - ch)
        M = np.float32([[z, 0, -x0 * z], [0, z, -y0 * z]])
        view = cv2.warpAffine(img, M, (self.vw, self.vh), flags=cv2.INTER_LINEAR)

        def to_view(px, py): return (px - x0) * z, (py - y0) * z
        vx = np.zeros((self.vh, self.vw, 4), np.float32); vx[..., :3] = view; vx[..., 3] = 255
        # marker circle around this beat's first click target, drawn on with a wipe
        if beat.get('circle') and evs:
            e = next((e for e in evs if e['type'] == 'click'), evs[-1]); ft = self.to_final(e['t'], k)
            p = ease((t - (ft - .9)) / .5) * (1 - ease((t - ft - .15) / .2))
            if p > 0:
                bx, by, bw, bh = e['box']; (cx0, cy0), (cx1, cy1) = to_view(bx, by), to_view(bx + bw, by + bh)
                cw2, ch2 = int((cx1 - cx0) * 1.5 + 40), int((cy1 - cy0) * 1.9 + 30)
                circ = cv2.resize(self.circle, (cw2, ch2), interpolation=cv2.INTER_AREA)
                over_rgba(vx, write_on(circ, p, soft=40), (cx0 + cx1) / 2 - cw2 / 2, (cy0 + cy1) / 2 - ch2 / 2)
        # cursor: eased travel to each event target, burst on clicks
        pos = self.cursor_pos(t, k, evs)
        if pos:
            px, py, clicked = pos; vx_, vy_ = to_view(px, py)
            if clicked is not None and 0 <= clicked < .4:
                s = .6 + clicked * 2; b = scaled(self.burst, s); b[..., 3] *= 1 - clicked / .4
                over_rgba(vx, b, vx_ - b.shape[1] / 2, vy_ - b.shape[0] / 2)
            cur = scaled(self.cursor, 1.15 / max(1, z) * z ** .5 * (0.88 if clicked is not None and clicked < .12 else 1))
            over_rgba(vx, cur, vx_ - cur.shape[1] * .32, vy_ - cur.shape[0] * .05)
        # to card: scale, white border, shadow, tilt
        s = self.card_scale; small = cv2.resize(vx, (int(self.vw * s), int(self.vh * s)), interpolation=cv2.INTER_AREA)
        bw = 12; cardi = np.zeros((small.shape[0] + 2 * bw, small.shape[1] + 2 * bw, 4), np.float32)
        cardi[..., :3] = 255; cardi[..., 3] = 255; cardi[bw:-bw, bw:-bw] = small
        tilt = -2.2 + .5 * math.sin(t * .6)
        return rotate(cardi, tilt)

    def cursor_pos(self, t, k, evs):
        if not evs: return None
        ft = [(self.to_final(e['t'], k), self.target(e), e['type']) for e in evs]
        start = (self.vw * .72, self.vh * .78)
        prev, prev_t = start, self.win[k][0]
        clicked = None
        for tt, tg, ty in ft:
            if t < tt:
                u = ease((t - max(prev_t, tt - .7)) / min(.7, max(.05, tt - prev_t)))
                return prev[0] + (tg[0] - prev[0]) * u, prev[1] + (tg[1] - prev[1]) * u + math.sin(u * math.pi) * -18, None
            prev, prev_t = tg, tt
            if ty == 'click': clicked = t - tt
        return prev[0], prev[1], clicked

    def host(self, t, k):
        beat = self.S['beats'][min(k, len(self.S['beats']) - 1)]
        outro = t >= self.end_t
        pose = 'wave' if outro and 'wave' in self.poses else beat.get('pose', 'talk')
        base = self.poses.get(pose, self.poses['talk']).copy()
        speaking = any(s['start'] <= t <= s['end'] for s in self.segs)
        fi = int(t * self.fps); m = self.T['mouth']
        lv = (m[fi] + m[fi - 1]) / 2 if 0 < fi < len(m) else 0
        shape = ('A' if lv > .38 else 'O' if lv > .14 else 'rest') if speaking else 'rest'
        if shape not in self.mouth: shape = 'O' if 'O' in self.mouth and shape != 'rest' else 'rest'
        mp, mx, my = self.mouth[shape]; over_rgba(base, mp, mx, my)
        blinks = [1.6 + i * 3.1 + (i * .73 % 1.2) for i in range(40)]
        if self.blink and shape == 'rest' and any(b <= t < b + .12 for b in blinks):
            bp, bx, by = self.blink; over_rgba(base, bp, bx, by)
        a = self.win[k][0] if not outro else self.end_t
        u = t - a
        settle = 1 + .05 * math.exp(-u * 9) * math.cos(u * 26) if u < .6 else 1   # squash-settle after a pose cut
        breath = 1 + .007 * math.sin(t * 2 * math.pi / 3.3)
        img = scaled(base, self.host_k)
        img = cv2.resize(img, (int(img.shape[1] * (2 - settle)), int(img.shape[0] * settle * breath)), interpolation=cv2.INTER_LINEAR)
        sway = math.sin(t * 1.3) * 1.2 + (math.sin(t * 7.5) * .8 if speaking else 0)
        img = rotate(img, sway)
        bob = (math.sin(t * 9) * 2.5 if speaking else 0)
        return img, bob

    # ------------------------------------------------------------------ frame
    def frame(self, t):
        """Finished frame: raw layout -> camera -> cut transition -> vignette/grain."""
        def cam(tt):
            img = self.raw(tt)
            if not self.fx['camera']: return img
            k = self.beat_at(min(tt, self.end_t - 1e-3))
            a, b = (self.win[k] if tt < self.end_t else (self.end_t, self.end_t + 2.6))
            return fx.camera(img, tt, a, b)
        img = None
        if self.fx['transitions']:
            for c, kind in self.cuts:
                if abs(t - c) < .2: img = fx.transition(kind, cam, t, c); break
        if img is None: img = cam(t)
        return fx.finish(img, int(t * self.fps)) if self.fx['finish'] else img

    def raw(self, t):
        k = self.beat_at(min(t, self.end_t - 1e-3)); beat = self.S['beats'][k]
        bgk = self.bg_kind[-1] if t >= self.end_t else self.bg_kind[k]; f = self._bgs[bgk].copy(); dark = bgk in fx.DARK_BGS
        acc = self.style['sceneAccents'][k % len(self.style['sceneAccents'])]
        # torn strip + title
        sy = 40 - 120 * (1 - back(t / .6)); over(f, self.torn, (W - self.torn.shape[1]) / 2, sy)
        ti = write_on(self.title, ease((t - .3) / .9)); over(f, ti, (W - ti.shape[1]) / 2, sy + self.torn.shape[0] / 2 - ti.shape[0] / 2)
        if t < self.end_t:
            # card (slides up on enter), tape
            cd = self.card(t); enter = back((t - .2) / .6)
            cy = CARD_Y + 130 + (1 - enter) * 700
            over(f, cd, (W - cd.shape[1]) / 2, cy - cd.shape[0] / 2)
            over(f, self.tape, W / 2 - self.tape.shape[1] / 2 + 6, cy - cd.shape[0] / 2 - self.tape.shape[0] * .45)
            # step chip
            if beat.get('step'):
                a = self.win[k][0]; si = self.step_imgs[beat['step']]; p = back((t - a) / .35)
                hl = cv2.resize(self.hl, (si.shape[1] + 30, int(si.shape[0] * .9)), interpolation=cv2.INTER_AREA)
                hl[..., :3] = np.array(hexc(acc['swipe'])[:3], np.float32)
                x = 30; y = cy - cd.shape[0] / 2 - 62
                over(f, write_on(hl, ease((t - a) / .4)), x - 15, y + 4)
                over(f, scaled(si, max(.01, p)), x, y)
            if self.fx['captions'] == 'box':
                fx.box_captions(f, self.T['words'], t, lambda sz: font(self.style, 'caption', sz), hexc(acc['karaoke']), y=742,
                                text_img=text_img, over=over, light=dark)
            else:
                karaoke(f, self.T['words'], t, {**self.style, 'colors': {**self.col, 'accent': acc['karaoke']}}, 742, size=46)
            st = beat.get('sticker')
            if st:   # {"text": "FREE!", "at": .5, "color": "#ffd23f", "x": .78, "y": 215, "tilt": -8}
                key = (k, st['text'])
                if key not in self._stickers:
                    self._stickers[key] = fx.text_sticker(st['text'], font(self.style, 'title', st.get('size', 44)), text_img, st.get('color', '#ffd23f'), seed=k)
                u = t - self.win[k][0] - float(st.get('at', .5))
                if u > 0:
                    sk = rotate(scaled(self._stickers[key], max(.01, back(u / .35))), st.get('tilt', -8) + 2 * math.sin(t * 2.5))
                    over(f, sk, W * st.get('x', .78) - sk.shape[1] / 2, st.get('y', 215) - sk.shape[0] / 2)
        else:
            u = t - self.end_t; b = scaled(self.badge, max(.01, back(u / .5)))
            over(f, b, (W - b.shape[1]) / 2, 420 - b.shape[0] / 2)
            ar = write_on(self.arrow, ease((u - .45) / .4)); over(f, ar, W - ar.shape[1] - 18, 250)
            pl = rotate(scaled(self.play, max(.01, back((u - .6) / .4))), 12 + 3 * math.sin(t * 3)); over(f, pl, 34, 230)
            end = self.S.get('end', {})
            if end.get('name'):
                nm = write_on(text_img(end['name'], font(self.style, 'title', 52), hexc(self.col['ink'])), ease((u - .3) / .8))
                over(f, nm, (W - nm.shape[1]) / 2, 610)
            if end.get('handle'):
                hd_ = text_img(end['handle'], font(self.style, 'body', 36), hexc(self.col.get('mark', self.col['ink'])))
                over(f, hd_, (W - hd_.shape[1]) / 2, 680, ease((u - .8) / .4))
        hi, bob = self.host(t, k)
        hy = 790 + bob if t < self.end_t else 790 + bob - 40 * ease((t - self.end_t) / .5)
        over(f, hi, (W - hi.shape[1]) / 2, hy)
        if t < .2: f[:] = (self._bgs[self.bg_kind[0]] * (1 - t / .2) + f * (t / .2)).astype(np.uint8)
        return f


def over_rgba(dst, src, x, y):
    """Alpha-composite float RGBA src onto float RGBA dst (in place), clipped."""
    H_, W_ = dst.shape[:2]; h, w = src.shape[:2]; x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W_, x + w), min(H_, y + h)
    if x0 >= x1 or y0 >= y1: return dst
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]; a = s[..., 3:4] / 255
    d = dst[y0:y1, x0:x1]
    d[..., :3] = d[..., :3] * (1 - a) + s[..., :3] * a
    d[..., 3:4] = np.maximum(d[..., 3:4], s[..., 3:4])
    return dst


def render(proj, a, b, out, stills=None):
    R = Reel(proj); n = int(R.end_t * R.fps + 2.6 * R.fps)
    if stills:
        os.makedirs(out, exist_ok=True)
        for tt in stills: Image.fromarray(R.frame(float(tt))).save(f'{out}/still_{tt}.png')
        return
    b = min(b, n)
    encode((R.frame(i / R.fps) for i in range(a, b)), out, W, H, R.fps)
    return out


def total_frames(proj):
    R = Reel(proj); return int(R.end_t * R.fps + 2.6 * R.fps)
