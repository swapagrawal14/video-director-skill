"""1280x720 YouTube thumbnail: clean frame shifted right, dark left gradient, pill tag, big title, credit.
Usage: python3 scripts/thumb.py <project-dir> clean_21.png   (text from project.json "thumbnail")
"thumbnail": {"pill":"STEP BY STEP","big":"BRACES","line1":"kaise lagte hain?","line2":"Bonding se Debonding tak","line3":"3D Animation • Hinglish","shift":230,"dark":[10,20,40]}"""
import sys, os, json
from PIL import Image, ImageDraw, ImageFont
d = sys.argv[1]; P = json.load(open(os.path.join(d, 'project.json'))); C = P.get('thumbnail', {}); TH = P.get('theme', {})
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
