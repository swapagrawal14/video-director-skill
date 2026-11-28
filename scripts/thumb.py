"""YouTube thumbnail from a clean frame: pill tag, big title, lines, credit.
16:9 projects -> 1280x720 (frame shifted right, dark left gradient).
9:16 projects (project.json "aspect": [9, 16], or height > width) -> 720x1280 for Shorts/Reels
(frame cover-fit, never squashed, dark bottom gradient, text in the lower third). Force with "thumbnail": {"vertical": true/false}.
Usage: python3 scripts/thumb.py <project-dir> clean_21.png   (text from project.json "thumbnail")
"thumbnail": {"pill":"STEP BY STEP","big":"BRACES","line1":"kaise lagte hain?","line2":"Bonding se Debonding tak","line3":"3D Animation • Hinglish","shift":230,"dark":[10,20,40]}"""
import sys, os, json
from PIL import Image, ImageDraw, ImageFont
d = sys.argv[1]; P = json.load(open(os.path.join(d, 'project.json'))); C = P.get('thumbnail', {}); TH = P.get('theme', {})
_asp = P.get('aspect'); _vert = C.get('vertical')
if _vert is None:
    _vert = bool(_asp and _asp[1] > _asp[0]) or P.get('height', 0) > P.get('width', 10**9)
if _vert:
    W, H = 720, 1280
    src = Image.open(os.path.join(d, sys.argv[2])).convert('RGB')
    sc = max(W / src.width, H / src.height); src = src.resize((round(src.width * sc), round(src.height * sc)))
    cv = src.crop(((src.width - W) // 2, (src.height - H) // 2, (src.width - W) // 2 + W, (src.height - H) // 2 + H))
    g = Image.new('L', (W, H)); dr = ImageDraw.Draw(g); top = C.get('edge', 620)
    for y in range(H): dr.line([(0, y), (W, y)], fill=0 if y < top else int(min(235, 235 * (y - top) / 260)))
    cv = Image.composite(Image.new('RGB', (W, H), tuple(C.get('dark', [10, 20, 40]))), cv, g); D = ImageDraw.Draw(cv)
    F = lambda s: ImageFont.truetype(os.path.join(d, 'fonts', 'baloo2.ttf'), s)
    hexrgb = lambda h: tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
    def fit(text, size, maxw):
        while size > 20 and D.textlength(text, font=F(size)) > maxw: size -= 4
        return F(size)
    y = 820
    if C.get('pill'):
        f = F(30); w = D.textlength(C['pill'], font=f) + 60; D.rounded_rectangle((48, y, 48 + w, y + 52), radius=26, fill=hexrgb(TH.get('accent', '#e23040')))
        D.text((48 + w / 2, y + 26), C['pill'], font=f, fill='white', anchor='mm'); y += 70
    big = C.get('big', P.get('title', '')); D.text((48, y), big, font=fit(big, 130, 624), fill='white'); y += 140
    D.text((50, y), C.get('line1', ''), font=fit(C.get('line1', ''), 60, 620), fill=hexrgb(TH.get('highlight', '#ffd23f'))); y += 80
    D.text((50, y), C.get('line2', ''), font=fit(C.get('line2', ''), 38, 620), fill='white'); y += 52
    D.text((50, y), C.get('line3', ''), font=fit(C.get('line3', ''), 30, 620), fill=(190, 210, 230))
    if P.get('credit'): D.text((50, 1220), P['credit'], font=F(28), fill=(230, 235, 245))
    cv.save(os.path.join(d, 'thumbnail.jpg'), quality=92); print('thumbnail.jpg (720x1280 vertical)'); sys.exit(0)
im = Image.open(os.path.join(d, sys.argv[2])).convert('RGB').resize((1280, 720)); sh = C.get('shift', 230)
cv = Image.new('RGB', (1280, 720)); cv.paste(im, (sh, 0)); cv.paste(im.crop((0, 0, sh, 720)).transpose(Image.FLIP_LEFT_RIGHT), (0, 0))
g = Image.new('L', (1280, 720)); dr = ImageDraw.Draw(g); edge = C.get('edge', 520)
for x in range(1280): dr.line([(x, 0), (x, 720)], fill=235 if x <= edge else int(max(0, 235 * (1 - (x - edge) / 380))))
cv = Image.composite(Image.new('RGB', (1280, 720), tuple(C.get('dark', [10, 20, 40]))), cv, g); D = ImageDraw.Draw(cv)
F = lambda s: ImageFont.truetype(os.path.join(d, 'fonts', 'baloo2.ttf'), s)
hexrgb = lambda h: tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))
def fit(text, size, maxw):
    while size > 20 and D.textlength(text, font=F(size)) > maxw: size -= 4
    return F(size)
if C.get('pill'):
    f = F(30); w = D.textlength(C['pill'], font=f) + 60; D.rounded_rectangle((60, 70, 60 + w, 122), radius=26, fill=hexrgb(TH.get('accent', '#e23040')))
    D.text((60 + w / 2, 96), C['pill'], font=f, fill='white', anchor='mm')
D.text((60, 140), C.get('big', P.get('title', '')), font=fit(C.get('big', P.get('title', '')), 150, 700), fill='white')
D.text((64, 290), C.get('line1', ''), font=fit(C.get('line1', ''), 70, 680), fill=hexrgb(TH.get('highlight', '#ffd23f')))
D.text((64, 395), C.get('line2', ''), font=fit(C.get('line2', ''), 42, 680), fill='white')
D.text((64, 450), C.get('line3', ''), font=F(32), fill=(190, 210, 230))
if P.get('credit'): D.text((64, 640), P['credit'], font=F(30), fill=(230, 235, 245))
cv.save(os.path.join(d, 'thumbnail.jpg'), quality=92); print('thumbnail.jpg')
