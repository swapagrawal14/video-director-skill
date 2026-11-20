#!/usr/bin/env python3
import json
from PIL import Image, ImageDraw
D = '/workspace/work/videoskill/examples/painted-duet/cast2/dadi/'
rig = json.load(open(D + 'rig.json'))
H = rig['head']; hs = rig['head_scale']
head = Image.open(D + H['file'])


def head_with(keys):
    h = head.copy()
    for k in keys:
        s = H['sprites'][k]
        sp = Image.open(D + s['file'])
        h.alpha_composite(sp, (s['x'], s['y']))
    return h


def compose(pose, keys=('mouth.rest',), bg=(236, 226, 205, 255), marks=False):
    b = rig['bodies'][pose]
    body = Image.open(D + b['file'])
    hh = head_with(keys)
    hw, hhh = int(round(hh.width * hs)), int(round(hh.height * hs))
    hh = hh.resize((hw, hhh), Image.LANCZOS)
    hx = b['neck'][0] - H['neck'][0] * hs
    hy = b['neck'][1] - H['neck'][1] * hs
    pad_top = int(max(0, -hy)) + 10
    pad_l = int(max(0, -hx)) + 10
    W = max(body.width + pad_l, int(hx + pad_l + hw)) + 10
    Ht = body.height + pad_top + 10
    c = Image.new('RGBA', (W, Ht), bg)
    c.alpha_composite(hh, (int(round(hx)) + pad_l, int(round(hy)) + pad_top))
    c.alpha_composite(body, (pad_l, pad_top))
    if marks:
        d = ImageDraw.Draw(c)
        nx, ny = b['neck'][0] + pad_l, b['neck'][1] + pad_top
        d.ellipse((nx - 3, ny - 3, nx + 3, ny + 3), outline=(255, 0, 0, 255))
    return c


if __name__ == '__main__':
    tiles = [compose(p) for p in rig['bodies']]
    # reference: keyed model sheet at body scale
    sh = Image.open(D + 'sheet_keyed.png'); bb = sh.getbbox(); sh = sh.crop(bb)
    tgt_h = max(t.height for t in tiles) - 20
    sh = sh.resize((int(sh.width * tgt_h / sh.height), tgt_h), Image.LANCZOS)
    shc = Image.new('RGBA', (sh.width + 20, tgt_h + 20), (220, 235, 236, 255)); shc.alpha_composite(sh, (10, 10))
    tiles = [shc] + tiles
    W = sum(t.width for t in tiles); Hh = max(t.height for t in tiles)
    out = Image.new('RGB', (W, Hh), (255, 255, 255)); x = 0
    for t in tiles:
        out.paste(t.convert('RGB'), (x, Hh - t.height)); x += t.width
    out.save(D + 'qa_poses.jpg', quality=92)
    keys = ['mouth.rest', 'mouth.M', 'mouth.A', 'mouth.E', 'mouth.O', 'mouth.laugh', 'eyes.closed', 'brows.angry', 'brows.up']
    hts = []
    for k in keys:
        h = head_with([k] if k.startswith('mouth') else ['mouth.rest', k])
        c = Image.new('RGBA', h.size, (236, 226, 205, 255)); c.alpha_composite(h)
        d = ImageDraw.Draw(c); d.text((8, 8), k, fill=(0, 0, 0, 255))
        hts.append(c.convert('RGB'))
    plain = Image.new('RGBA', head.size, (236, 226, 205, 255)); plain.alpha_composite(head)
    hts = [plain.convert('RGB')] + hts
    w, h = hts[0].size
    out = Image.new('RGB', (w * 5, h * 2), (255, 255, 255))
    for i, t in enumerate(hts):
        out.paste(t, ((i % 5) * w, (i // 5) * h))
    out.save(D + 'qa_mouths.jpg', quality=90)
