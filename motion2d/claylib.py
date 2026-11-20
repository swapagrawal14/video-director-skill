import json, math, random, subprocess, wave, os
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1920, 1080, 12
D = os.environ.get('MOTION_ROOT', os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else '.'))) + '/'
random.seed(7); np.random.seed(7)

def font(size, wght=600):
    f = ImageFont.truetype(D + 'fonts/Fredoka.ttf', size)
    ax=[a['name'] for a in f.get_variation_axes()]
    vals={b'Weight':wght,'Weight':wght}
    f.set_variation_by_axes([wght if (n in (b'Weight','Weight')) else 100 for n in ax])
    return f

BROWN = (74, 44, 34)
CREAM = (251, 243, 228)
CORAL = (226, 112, 86)
TEAL = (64, 160, 150)
DOTS = [(226, 112, 86), (64, 160, 150), (240, 180, 70), (150, 120, 200), (90, 150, 220)]

def clay_plate(text, size=38, fill=CREAM, fg=BROWN, pad=(30, 16), dot=None, wght=600, radius=None, number=None):
    f = font(size, wght)
    lines = text.split('\n')
    bb = [f.getbbox(l) for l in lines]
    lh = int(size * 1.18)
    tw = max(b[2] for b in bb); th = lh * len(lines)
    extra = 0
    if dot: extra = int(size * 0.75)
    if number: extra = int(size * 1.6)
    pw, ph = tw + pad[0] * 2 + extra, th + pad[1] * 2
    r = radius or min(ph // 2, 40)
    S = 20
    img = Image.new('RGBA', (pw + S * 2, ph + S * 2), (0, 0, 0, 0))
    # shadow
    sh = Image.new('L', img.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle([S + 4, S + 9, S + pw + 4, S + ph + 9], r, fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(7))
    img.paste((40, 20, 10, 255), (0, 0), sh)
    body = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    d.rounded_rectangle([S, S, S + pw, S + ph], r, fill=fill + (255,))
    # clay shading: darker bottom, lighter top rim
    shade = Image.new('L', img.size, 0); sd = ImageDraw.Draw(shade)
    sd.rounded_rectangle([S, S + ph * 0.55, S + pw, S + ph], r, fill=55)
    shade = shade.filter(ImageFilter.GaussianBlur(10))
    m = Image.new('L', img.size, 0); ImageDraw.Draw(m).rounded_rectangle([S, S, S + pw, S + ph], r, fill=255)
    shade = Image.fromarray(np.minimum(np.array(shade), np.array(m)))
    body.paste((0, 0, 0, 255), (0, 0), shade.point(lambda v: v // 2))
    hl = Image.new('L', img.size, 0)
    ImageDraw.Draw(hl).rounded_rectangle([S + 8, S + 5, S + pw - 8, S + ph * 0.35], r, fill=70)
    hl = hl.filter(ImageFilter.GaussianBlur(6))
    hl = Image.fromarray(np.minimum(np.array(hl), np.array(m)))
    body.paste((255, 255, 255, 255), (0, 0), hl)
    # fingerprint-ish noise
    a = np.array(body).astype(np.int16)
    n = cv2.GaussianBlur(np.random.randn(*img.size[::-1]).astype(np.float32), (0, 0), 1.6) * 9
    for c in range(3): a[..., c] = np.clip(a[..., c] + n, 0, 255)
    body = Image.fromarray(a.astype(np.uint8))
    img.alpha_composite(body)
    d = ImageDraw.Draw(img)
    x = S + pad[0]
    if dot:
        cy = S + ph // 2; rr = size * 0.22
        d.ellipse([x, cy - rr, x + rr * 2, cy + rr], fill=dot)
        x += extra
    if number:
        cy = S + ph // 2; rr = size * 0.62
        d.ellipse([x - 6, cy - rr, x - 6 + rr * 2, cy + rr], fill=CREAM)
        nf = font(int(size * 0.7), 700)
        d.text((x - 6 + rr, cy), number, font=nf, fill=fill, anchor='mm')
        x += extra
    for i, l in enumerate(lines):
        y = S + pad[1] + i * lh + (lh - size) // 2 - f.getbbox(l)[1] // 3
        d.text((x, S + pad[1] + i * lh + lh // 2), l, font=f, fill=fg, anchor='lm')
    return img


def make_item(text, kind, num=None):
    if kind == 'title':
        return clay_plate(text, size=78, fill=CORAL, fg=CREAM, pad=(44, 26), wght=650, radius=46)
    if kind == 'head':
        return clay_plate(text, size=50, fill=CORAL, fg=CREAM, pad=(34, 18), wght=650, number=num)
    if kind == 'headc':
        return clay_plate(text, size=52, fill=CORAL, fg=CREAM, pad=(36, 18), wght=650)
    if kind == 'headc2':
        return clay_plate(text, size=52, fill=TEAL, fg=CREAM, pad=(36, 18), wght=650)
    if kind == 'big':
        return clay_plate(text, size=66, fill=CREAM, fg=BROWN, pad=(36, 18), wght=650)
    if kind == 'credit':
        return clay_plate(text, size=36, fill=TEAL, fg=CREAM, pad=(30, 14), wght=550)
    if kind == 'chipW':
        return clay_plate(text, size=36, fill=(255, 226, 205), fg=BROWN, dot=(200, 70, 50))
    return clay_plate(text, size=36, fill=CREAM, fg=BROWN, dot=random.choice(DOTS))

# pop curve over steps (scale)
POP = [0.3, 0.75, 1.12, 1.04, 0.97, 1.0]
def pop_scale(step):
    return POP[step] if step < len(POP) else 1.0

