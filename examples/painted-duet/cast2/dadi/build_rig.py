#!/usr/bin/env python3
"""Build Dadi's painted cutout rig from the generated raster art in raw/.
Raster only: every pixel comes from the image model; this script only keys, masks, crops, scales."""
import json, numpy as np, cv2
from PIL import Image, ImageFilter
from scipy import ndimage as ndi

D = '/workspace/work/videoskill/examples/painted-duet/cast2/dadi/'
POSES = ['idle', 'talk', 'point', 'sheepish', 'arms_crossed', 'laugh']
HEAD_OUT = 0.5          # head.png = head_raw * 0.5
TARGET_BODY = 480       # neck base -> feet, px


def load(p):
    return np.asarray(Image.open(D + p).convert('RGB')).astype(np.float32)


def key_green(rgb):
    """Soft chroma key + despill. Returns RGBA float array."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    gness = g - np.maximum(r, b)
    a = np.clip(1.0 - (gness - 35.0) / 70.0, 0, 1)
    # despill: clamp green toward max(r,b) where there is any greenness
    g2 = np.where(gness > 0, np.minimum(g, np.maximum(r, b) + 4), g)
    out = np.dstack([r, g2, b, a * 255])
    # drop tiny islands of noise
    lab, n = ndi.label(a > 0.5)
    if n > 1:
        sizes = ndi.sum(np.ones_like(a), lab, range(1, n + 1))
        keep = np.isin(lab, 1 + np.nonzero(sizes > 400)[0])
        keep = ndi.binary_dilation(keep, iterations=3)
        out[..., 3] *= keep
    return out


def hsv(rgb):
    return cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)


def saree_mask(rgb):
    """maroon / mustard cloth pixels."""
    h = hsv(rgb); H, S, V = h[..., 0], h[..., 1], h[..., 2]
    maroon = ((H < 8) | (H > 165)) & (S > 90) & (V > 60) & (V < 200)
    mustard = (H >= 12) & (H <= 30) & (S > 120) & (V > 120)
    return maroon | mustard


# ---------------- HEAD ----------------
hraw = load('raw/head_raw.png')
hk = key_green(hraw)
alpha = hk[..., 3] > 127
sar = saree_mask(hraw)
sar[:560] = False                         # cloth only lives below the chin
sar = ndi.binary_opening(sar, iterations=2)
sar_d = ndi.binary_dilation(sar, iterations=2)   # head keeps its neck skin down to the cloth ink line
headm = alpha & ~sar_d
lab, n = ndi.label(headm)
sizes = ndi.sum(headm, lab, range(1, n + 1))
headm = lab == (1 + int(np.argmax(sizes)))
headm = ndi.binary_fill_holes(headm)
# drop the cloth's own ink lines: per column, nothing at or below the top of the cloth
_yy = np.arange(1024)[:, None]
_low = headm & (_yy > 760)
headm = (headm & (_yy <= 760)) | ndi.binary_opening(_low, iterations=5)
lab, n = ndi.label(headm)
sizes = ndi.sum(headm, lab, range(1, n + 1))
headm = lab == (1 + int(np.argmax(sizes)))
# kill the pale anti-alias halo the model paints between ink and green
headm = ndi.binary_erosion(headm, iterations=2)
# feather only the cut against the cloth; keep keyed edge elsewhere
soft = cv2.GaussianBlur(headm.astype(np.float32), (0, 0), 1.6)
ha = np.minimum(hk[..., 3] / 255.0, soft)
head_rgba_raw = np.dstack([hk[..., :3], ha * 255]).astype(np.uint8)

ys, xs = np.nonzero(ha > 0.02)
bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
# neck attach: bottom of the chin/neck skin, centred on the lower face
low = [(np.nonzero(headm[:, x])[0].max(), x) for x in range(200, 520) if headm[:, x].any()]
ny = max(l[0] for l in low); nx = np.median([l[1] for l in low if l[0] >= ny - 4])
neck_raw = (float(nx), float(ny))
print('chin/neck raw', neck_raw)

head_crop = Image.fromarray(head_rgba_raw).crop((bx0, by0, bx1, by1))
HW, HH = int(round(head_crop.width * HEAD_OUT)), int(round(head_crop.height * HEAD_OUT))
head_crop.resize((HW, HH), Image.LANCZOS).save(D + 'head.png')
head_neck = [round((neck_raw[0] - bx0) * HEAD_OUT, 1), round((neck_raw[1] - by0) * HEAD_OUT, 1)]


def to_head(x, y):
    return (x - bx0) * HEAD_OUT, (y - by0) * HEAD_OUT


# ---------------- SPRITES ----------------
ROI = {
    'mouth': (170, 490, 480, 730),
    'eyes': (130, 360, 540, 505),
    'brows': (120, 270, 540, 425),
}
# rest mouth comes from the original model sheet (its closed smile), upscaled into head_raw space
sheet = Image.open(D + 'raw/sheet_raw.png').convert('RGB').crop((190, 50, 640, 500)).resize((1024, 1024), Image.LANCZOS)
sheet.save(D + 'raw/v_m_rest.png')
VARIANTS = {
    'mouth.rest': ('raw/v_m_rest.png', 'mouth'),
    'mouth.M': ('raw/v_m_M.png', 'mouth'),
    'mouth.A': ('raw/v_m_A.png', 'mouth'),
    'mouth.E': ('raw/v_m_E.png', 'mouth'),
    'mouth.O': ('raw/v_m_O.png', 'mouth'),
    'mouth.laugh': ('raw/v_m_laugh.png', 'mouth'),
    'eyes.closed': ('raw/v_eyes_closed.png', 'eyes'),
    'brows.angry': ('raw/v_brows_angry.png', 'brows'),
    'brows.up': ('raw/v_brows_up.png', 'brows'),
}
sprites = {}
for key, (f, roi) in VARIANTS.items():
    v = load(f)
    x0, y0, x1, y1 = ROI[roi]
    d = np.abs(v - hraw).max(2)
    m = np.zeros(d.shape, bool)
    m[y0:y1, x0:x1] = d[y0:y1, x0:x1] > 45
    m = ndi.binary_opening(m, iterations=1)
    lab, n = ndi.label(ndi.binary_dilation(m, iterations=6))
    if n:
        sizes = ndi.sum(m, lab, range(1, n + 1))
        keep = 1 + np.nonzero(sizes > 60)[0]
        m = np.isin(lab, keep)
    m = ndi.binary_dilation(m, iterations=8) & headm
    a = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 3.0) * (ha)
    ys_, xs_ = np.nonzero(a > 0.01)
    sx0, sy0, sx1, sy1 = xs_.min(), ys_.min(), xs_.max() + 1, ys_.max() + 1
    rgba = np.dstack([v, a * 255]).astype(np.uint8)
    spr = Image.fromarray(rgba).crop((sx0, sy0, sx1, sy1))
    hx, hy = to_head(sx0, sy0)
    spr = spr.resize((max(1, int(round(spr.width * HEAD_OUT))), max(1, int(round(spr.height * HEAD_OUT)))), Image.LANCZOS)
    fn = 'sprite_' + key.replace('.', '_') + '.png'
    spr.save(D + fn)
    sprites[key] = {'file': fn, 'x': int(round(hx)), 'y': int(round(hy)), 'w': spr.width, 'h': spr.height}

# ---------------- BODIES ----------------
# template = upper head (hair, eyes, nose) of head_raw at sheet scale, used to find each body's head
tmpl_full = hraw
tm_mask_full = headm.copy()
tm_mask_full[560:] = False   # exclude mouth/chin (differs per pose)


def find_head(body_rgb):
    best = None
    img = body_rgb[:700].astype(np.uint8)
    for s in np.arange(0.40, 0.49, 0.004):
        tw = int(1024 * s)
        t = cv2.resize(tmpl_full.astype(np.uint8), (tw, tw), interpolation=cv2.INTER_AREA)
        mk = cv2.resize(tm_mask_full.astype(np.uint8) * 255, (tw, tw), interpolation=cv2.INTER_NEAREST)
        mk = cv2.merge([mk, mk, mk])
        r = cv2.matchTemplate(img, t, cv2.TM_SQDIFF, mask=mk)
        r = r / max(1, (mk > 0).sum())
        mn, _, loc, _ = cv2.minMaxLoc(r)
        if best is None or mn < best[0]:
            best = (mn, s, loc)
    return best


bodies_tmp = {}
for p in POSES:
    rgb = load('raw/' + p + '.png')
    bk = key_green(rgb)
    err, s, (ox, oy) = find_head(rgb)
    # head mask placed in body coords
    tw = int(1024 * s)
    hm = cv2.resize(headm.astype(np.uint8), (tw, tw), interpolation=cv2.INTER_NEAREST).astype(bool)
    full = np.zeros(rgb.shape[:2], bool)
    y1c, x1c = min(rgb.shape[0], oy + tw), min(rgb.shape[1], ox + tw)
    full[oy:y1c, ox:x1c] = hm[:y1c - oy, :x1c - ox]
    # head layer sits BEHIND the body: keep all cloth (+ its ink line), erase head/neck skin + hair
    Hb, Wb = rgb.shape[:2]
    yyb = np.arange(Hb)[:, None]
    cloth = saree_mask(rgb) & (yyb > oy + 500 * s)
    cloth = ndi.binary_opening(cloth, iterations=1)
    cloth_keep = ndi.binary_dilation(cloth, iterations=4)
    btop = np.where(cloth.any(0), np.argmax(cloth, 0), Hb)
    above_cloth = yyb < btop[None, :] + 4
    near = ndi.binary_dilation(full, iterations=30)
    E = near & above_cloth & ~cloth_keep
    E |= ndi.binary_dilation(full, iterations=6) & ~cloth_keep
    E &= yyb < oy + 800 * s          # the pose keeps its own lower neck (sits in front of the head's neck)
    # give back limbs raised beside the head (sheepish arm) - only above cheek height, outside the head silhouette
    alpha_b = bk[..., 3] > 60
    C = E & ~ndi.binary_dilation(full, iterations=6) & (yyb < oy + 600 * s) & alpha_b
    R = alpha_b & ~E
    lab_c, n_c = ndi.label(R | C)
    touch = np.unique(lab_c[R])
    over = C & np.isin(lab_c, touch[touch > 0])
    print(p, 'restored limb px', int(over.sum()))
    erase = E & ~over
    # also clear any hair/face leftovers (stray strands, tilted head) above the chin that are not cloth or arm
    chin_body = oy + int(neck_raw[1] * s)
    hs = hsv(rgb)
    cloth = saree_mask(rgb)
    above = np.zeros_like(full); above[:chin_body - int(60 * s * 2.276)] = True
    hairish = (hs[..., 1] < 60) & (hs[..., 2] > 50) & (hs[..., 2] < 200)   # grey hair
    lab, n = ndi.label(bk[..., 3] > 127)
    erase |= above & hairish & ~cloth & ~over
    solid = ndi.binary_erosion(bk[..., 3] > 127, iterations=1)
    bk[..., 3] = np.minimum(bk[..., 3], cv2.GaussianBlur(solid.astype(np.float32), (0, 0), 0.8) * 255)
    keep = ~erase
    keep_f = cv2.GaussianBlur(keep.astype(np.float32), (0, 0), 1.0)
    bk[..., 3] *= keep_f
    # remove small disconnected leftovers
    lab, n = ndi.label(bk[..., 3] > 60)
    if n > 1:
        sizes = ndi.sum(np.ones(lab.shape), lab, range(1, n + 1))
        big = np.isin(lab, 1 + np.nonzero(sizes >= 0.02 * sizes.max())[0])
        bk[..., 3] *= ndi.binary_dilation(big, iterations=2)
    neck = (ox + neck_raw[0] * s, oy + neck_raw[1] * s)
    ys, xs = np.nonzero(bk[..., 3] > 10)
    foot_y = ys.max()
    feet_cols = xs[ys > foot_y - 40]
    foot_x = float((feet_cols.min() + feet_cols.max()) / 2)
    bodies_tmp[p] = dict(rgba=bk, neck=neck, foot=(foot_x, foot_y + 1), s=s, err=float(err),
                         bbox=(xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    print(p, 'scale', round(s, 3), 'err', round(err, 1), 'neck', [round(v) for v in neck], 'foot_y', foot_y)

med_h = np.median([b['foot'][1] - b['neck'][1] for b in bodies_tmp.values()])
BS = TARGET_BODY / med_h
med_s = float(np.median([b['s'] for b in bodies_tmp.values()]))
bodies = {}
for p, b in bodies_tmp.items():
    x0, y0, x1, y1 = b['bbox']
    y1 = int(round(b['foot'][1]))
    im = Image.fromarray(np.clip(b['rgba'], 0, 255).astype(np.uint8)).crop((x0, y0, x1, y1))
    W, H = int(round(im.width * BS)), int(round(im.height * BS))
    im = im.resize((W, H), Image.LANCZOS)
    fn = 'body_' + p + '.png'
    im.save(D + fn)
    bodies[p] = {'file': fn, 'w': W, 'h': H,
                 'neck': [round((b['neck'][0] - x0) * BS, 1), round((b['neck'][1] - y0) * BS, 1)],
                 'foot': [round((b['foot'][0] - x0) * BS, 1), H],
                 'head_fit_scale': round(b['s'] / med_s, 3)}

# head px -> body px: head.png is head_raw*HEAD_OUT; head_raw * s = sheet/body raw scale; body raw * BS = body png
head_scale = round(med_s / HEAD_OUT * BS, 4)

sheet_k = key_green(load('raw/sheet_raw.png'))
Image.fromarray(np.clip(sheet_k, 0, 255).astype(np.uint8)).save(D + 'sheet_keyed.png')

rig = {'character': 'Dadi (Kaushalya)', 'facing': 'left (3/4)',
       'head': {'file': 'head.png', 'w': HW, 'h': HH, 'neck': head_neck, 'sprites': sprites},
       'bodies': bodies, 'head_scale': head_scale,
       'head_layer': 'behind_body', 'notes': 'Scale head (and sprites) by head_scale; place so head.neck*head_scale lands on body.neck. Draw order: head, then sprites at (x,y) in head px, then BODY ON TOP (the saree neckline hides the base of the neck). head_fit_scale per body = measured head size in that pose vs median (info only).'}
json.dump(rig, open(D + 'rig.json', 'w'), indent=2)
print(json.dumps({'head_scale': head_scale, 'BS': BS, 'head': rig['head']['neck']}, indent=1))
