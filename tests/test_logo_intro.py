import os, sys, numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'motion2d'))
import logo_intro as L


def _logo(path):
    im = Image.new('RGB', (400, 300), (230, 190, 240)); d = ImageDraw.Draw(im)
    d.ellipse((60, 40, 340, 260), fill=(255, 255, 255), outline=(10, 10, 10), width=6)
    d.ellipse((120, 90, 190, 150), fill=(250, 120, 110), outline=(10, 10, 10), width=5)
    d.ellipse((210, 140, 280, 200), fill=(80, 190, 180), outline=(10, 10, 10), width=5)
    d.ellipse((10, 10, 30, 30), fill=(250, 220, 90), outline=(10, 10, 10), width=3)
    im.save(path)


def test_split_kinds(tmp_path):
    p = str(tmp_path / 'logo.png'); _logo(p)
    a, bg = L.load_logo(p)
    parts = L.split_parts(a)
    kinds = [q['kind'] for q in parts]
    assert kinds.count('base') == 1 and kinds.count('inner') == 2
    base = [q for q in parts if q['kind'] == 'base'][0]
    al = np.array(base['img'])[..., 3]
    h, w = al.shape
    assert al[h // 2, w // 2] == 255          # holes under inner parts are filled


def test_render_short(tmp_path):
    p = str(tmp_path / 'logo.png'); _logo(p); out = str(tmp_path / 'o.mp4')
    L.render(p, out, size=(360, 640), secs=2.0, tagline='HELLO', audio=False, boil=0.8)
    assert os.path.getsize(out) > 1000
