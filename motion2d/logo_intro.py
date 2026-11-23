"""Logo intro: give ANY raster logo, get an animated doodle intro (9:16 / 16:9 / 1:1 MP4 with SFX).

The tool breaks the logo into its own parts (base shape, inner colour fills, letters, sparkles) straight
from the pixels, then builds the mark on screen piece by piece: the base pops with overshoot + squash,
inner parts fly in and land with a pop each, letters bounce in one by one, sparkles twinkle, an optional
tagline slams in, line boil keeps it hand-drawn. Picture is a pure function of t (seeded), audio is
built from the same event list, so picture and sound never drift.

Never redraws or vectorises the logo: every part is cut from the client's own raster (no SVG).

    python3 motion2d/logo_intro.py LOGO.png out.mp4 [--size 1080x1920] [--secs 8] [--bg auto|#E7C0F0]
        [--tagline "ART · FASHION · YOU"] [--sub "LAUNCHING SOON"] [--logo-w 0.78] [--boil 1.1]
        [--seed 7] [--no-audio] [--parts-sheet parts.png]

Input: PNG with transparency is best. A logo on a flat background works too: the background colour is
read from the corners and keyed out (tolerance --key-tol). Credit: Swapnil Agrawal (BDS intern).
Playbook: docs/LOGO_INTRO.md.
"""
import argparse, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from motion import back, ease_out, clamp, xform, paste, squash          # noqa: E402
from doodle import line_boil, pop_text, hex_bgr, hex_rgb, impact_burst  # noqa: E402
import sfx                                                              # noqa: E402

FPS = 24


# ------------------------------------------------------------------ load + key
def load_logo(path, key_tol=38):
    """RGBA uint8 array, background keyed out when the image has no real alpha. Returns (rgba, bg_rgb)."""
    im = Image.open(path).convert('RGBA'); a = np.array(im)
    h, w = a.shape[:2]
    corners = np.concatenate([a[:6, :6].reshape(-1, 4), a[:6, -6:].reshape(-1, 4),
                              a[-6:, :6].reshape(-1, 4), a[-6:, -6:].reshape(-1, 4)])
    bg = tuple(int(v) for v in np.median(corners[:, :3], 0))
    if a[..., 3].min() > 250:                                  # no transparency: key flat background
        d = np.abs(a[..., :3].astype(int) - np.array(bg)).sum(2)
        # key only background CONNECTED to the border: fills inside outlines that share the bg colour stay
        near = d <= key_tol; lab, _ = ndi.label(near)
        edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])); edge = edge[edge > 0]
        a[..., 3] = np.where(np.isin(lab, edge), 0, 255).astype(np.uint8)
        a[..., 3] = (ndi.binary_opening(a[..., 3] > 0, iterations=1) * 255).astype(np.uint8)
    ys, xs = np.where(a[..., 3] > 0)
    if len(ys) == 0: raise SystemExit('logo is empty after keying; pass a PNG with alpha or raise --key-tol')
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return a, bg


# ------------------------------------------------------------------ split into parts
def split_parts(a, ink_lum=85, min_area=None):
    """Cut the logo into parts. Coloured/white fills are the parts; the dark outline around a fill is owned
    by the SMALLEST fill it touches (so an inner blob keeps its full outline). Holes a big part had under
    smaller parts are painted with that part's own fill colour, so the base looks whole when it pops alone.
    Returns list of dicts: {img (RGBA PIL), cx, cy (centre in logo px), area, kind}."""
    h, w = a.shape[:2]; op = a[..., 3] > 0
    rgb = a[..., :3].astype(np.float32)
    lum = rgb @ np.array([.299, .587, .114], np.float32)
    ink = op & (lum < ink_lum)
    min_area = min_area or max(40, int(h * w * 0.0002))
    # fills = solid colour regions; opening drops anti-aliased edge slivers (they are treated like ink)
    fill = ndi.binary_opening(op & ~ink, iterations=2)
    lab, n = ndi.label(fill)
    areas = ndi.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1)) if n else []
    small = [i + 1 for i in range(n) if areas[i] < min_area]
    if small: lab[np.isin(lab, small)] = 0
    line = op & (lab == 0)                       # outline + slivers + tiny bits
    stroke = 2 * float(np.percentile(ndi.distance_transform_edt(line)[line], 95)) if line.any() else 4
    r = max(2, int(round(min(h, w) * 0.012)), int(round(stroke * 1.2)))
    # each line pixel belongs to its nearest fill (if close); far line art forms its own parts
    dist, (iy, ix) = ndi.distance_transform_edt(lab == 0, return_indices=True)
    owner = lab.copy()
    near = line & (dist <= r * 1.6)
    owner[near] = lab[iy[near], ix[near]]
    far = line & ~near
    rlab, rn = ndi.label(far, structure=np.ones((3, 3)))
    nid = int(lab.max()) + 1
    for j in range(1, rn + 1):
        m = rlab == j
        ring = ndi.binary_dilation(m, iterations=2) & ~m & (owner > 0) & ~far
        if ring.any():                           # touches a part: it is that part's outline
            vals, cnt = np.unique(owner[ring], return_counts=True); owner[m] = vals[cnt.argmax()]
        elif m.sum() >= min_area * 0.6: owner[m] = nid; nid += 1
        else:                                   # speck: give it to the nearest part
            yy, xx = np.argwhere(m)[0]; owner[m] = lab[iy[yy, xx], ix[yy, xx]]
    ids = [L for L in np.unique(owner) if L > 0]
    areas_o = {L: int((owner == L).sum()) for L in ids}
    parts = []
    for L in ids:
        m = owner == L
        if (lab == L).any() and areas_o[L] < max(areas_o.values()) * 0.5:
            # smaller fills also carry their FULL outline (copied), so they land complete on the base
            m = m | (line & ndi.binary_dilation(lab == L, iterations=r))
        filled = ndi.binary_fill_holes(m)
        hole = filled & ~m & ~op if False else filled & ~m
        img = np.zeros_like(a); img[m] = a[m]
        if hole.any() and (lab == L).any():
            col = np.median(a[lab == L][:, :3], 0).astype(np.uint8)
            img[hole, :3] = col; img[hole, 3] = 255
        ys, xs = np.where(filled)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        parts.append(dict(img=Image.fromarray(img[y0:y1, x0:x1], 'RGBA'), cx=(x0 + x1) / 2, cy=(y0 + y1) / 2,
                          area=int(filled.sum()), bbox=(x0, y0, x1, y1), kind=''))
    return classify(parts, w, h)


def classify(parts, w, h):
    """base = biggest part; inner = parts whose centre sits inside the base; sparkle = tiny parts;
    letter = mid-size parts outside the base (ordered left to right along the text); other = rest."""
    if not parts: return parts
    parts.sort(key=lambda p: -p['area'])
    base = parts[0]; base['kind'] = 'base'
    bx0, by0, bx1, by1 = base['bbox']
    bm = np.array(base['img'])[..., 3] > 0
    big = base['area']
    for p in parts[1:]:
        x, y = int(p['cx'] - bx0), int(p['cy'] - by0)
        inside = 0 <= x < bm.shape[1] and 0 <= y < bm.shape[0] and bm[y, x]
        if inside and p['area'] < big * 0.5: p['kind'] = 'inner'
        elif p['area'] < big * 0.012: p['kind'] = 'sparkle'
        elif p['area'] < big * 0.25: p['kind'] = 'letter'
        else: p['kind'] = 'other'
    return parts


def parts_sheet(parts, path):
    """Debug sheet: every part on a tile with its kind, so you can check the split before rendering."""
    cols = 8; t = 140; rows = math.ceil(len(parts) / cols)
    sh = Image.new('RGB', (cols * t, rows * (t + 18)), (235, 235, 235)); d = ImageDraw.Draw(sh)
    for i, p in enumerate(parts):
        im = p['img'].copy(); im.thumbnail((t - 10, t - 10))
        x, y = (i % cols) * t, (i // cols) * (t + 18)
        sh.paste(im, (x + (t - im.width) // 2, y + (t - im.height) // 2), im)
        d.text((x + 4, y + t), f"{i} {p['kind']}", fill=(30, 30, 30))
    sh.save(path)


# ------------------------------------------------------------------ timeline
def plan(parts, secs, seed, has_tag, has_sub):
    """Assign each part a start time + entry move. Returns (schedule, sfx_events)."""
    rs = np.random.RandomState(seed)
    by = {k: [p for p in parts if p['kind'] == k] for k in ('base', 'inner', 'other', 'letter', 'sparkle')}
    ev = []; t = 0.25
    for p in by['base'] + by['other']:
        p.update(t0=t, move='pop', dur=0.45); ev.append((t, 'boing')); t += 0.35
    t += 0.25
    inner = sorted(by['inner'], key=lambda p: (p['cy'], p['cx']))
    step = min(0.16, 1.6 / max(1, len(inner)))
    for p in inner:
        ang = rs.uniform(0, 2 * math.pi)
        p.update(t0=t, move='fly', dur=0.38, dx=math.cos(ang) * 260, dy=math.sin(ang) * 260, rot0=rs.uniform(-40, 40))
        ev.append((t + 0.34, 'pop')); t += step
    t += 0.2
    letters = sorted(by['letter'], key=lambda p: math.atan2(p['cy'] - 1e9, p['cx']) if False else p['cx'])
    step = min(0.09, 1.4 / max(1, len(letters)))
    for i, p in enumerate(letters):
        p.update(t0=t, move='drop', dur=0.34); ev.append((t + 0.3, 'plip') if i % 2 == 0 else (t + 0.3, 'tick')); t += step
    t += 0.15
    for p in by['sparkle']:
        p.update(t0=t + rs.uniform(0, 0.6), move='twinkle', dur=0.3, ph=rs.uniform(0, 6.28))
    if by['sparkle']: ev.append((t + 0.1, 'plip'))
    t_tag = t + 0.55 if has_tag else None
    t_sub = (t_tag or t) + 0.5 if has_sub else None
    if t_tag: ev.append((t_tag + 0.28, 'squish'))
    if t_sub: ev.append((t_sub + 0.25, 'pop'))
    end = max(t_sub or 0, t_tag or 0, t) + 1.6
    if end > secs: print(f'[logo_intro] note: build needs ~{end:.1f} s; --secs {secs} trims the hold')
    return t_tag, t_sub, ev


def part_state(p, t):
    """(visible, scale_x, scale_y, dx, dy, rot, alpha) for a part at time t."""
    u = t - p.get('t0', 0)
    if u < 0: return None
    d = p['dur']; k = clamp(u / d)
    if p['move'] == 'pop':
        if u < d: s = max(0.02, back(k, 2.2)); return (s, s, 0, 0, (1 - k) * -8, 1)
        sx, sy = squash(u - d, amt=0.08, freq=14, damp=5); return (sx, sy, 0, 0, 0, 1)
    if p['move'] == 'fly':
        e = ease_out(k); s = 0.4 + 0.6 * back(k, 1.6)
        if u >= d: sx, sy = squash(u - d, amt=0.12, freq=20, damp=8); return (sx, sy, 0, 0, 0, 1)
        return (s, s, p['dx'] * (1 - e), p['dy'] * (1 - e), p['rot0'] * (1 - e), clamp(k * 3))
    if p['move'] == 'drop':
        if u >= d: sx, sy = squash(u - d, amt=0.14, freq=22, damp=8); return (sx, sy, 0, 0, 0, 1)
        e = back(k, 2.0); return (1, 1, 0, -120 * (1 - e), 0, clamp(k * 4))
    if p['move'] == 'twinkle':
        s = back(k, 2.5) * (1 + 0.18 * math.sin((t * 5.5) + p['ph']))
        return (max(0.02, s), max(0.02, s), 0, 0, 20 * math.sin(t * 2 + p['ph']), 1)
    return (1, 1, 0, 0, 0, 1)


# ------------------------------------------------------------------ render
def render(logo, out, size=(1080, 1920), secs=8.0, bg='auto', tagline=None, sub=None, logo_w=0.78,
           boil=1.1, seed=7, audio=True, sheet=None, key_tol=38, ink='#111111', tag_fill='#FFFFFF', sub_fill='#F4A73B'):
    W, H = size
    a, bg_rgb = load_logo(logo, key_tol)
    parts = split_parts(a)
    if sheet: parts_sheet(parts, sheet)
    lh, lw = a.shape[:2]
    sc = min(W * logo_w / lw, H * 0.42 / lh)
    cx0, cy0 = W / 2, H * (0.42 if tagline else 0.47)
    for p in parts: p['img'] = p['img'].resize((max(1, int(p['img'].width * sc)), max(1, int(p['img'].height * sc))), Image.LANCZOS)
    t_tag, t_sub, ev = plan(parts, secs, seed, bool(tagline), bool(sub))
    plate = np.empty((H, W, 3), np.float32)
    plate[:] = hex_bgr(bg) if bg != 'auto' else bg_rgb[::-1]
    tmp = out + '.v.mp4'
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', tmp]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    drawn = [p for p in parts if p['kind'] != 'sparkle'] + [p for p in parts if p['kind'] == 'sparkle']
    for step in range(int(secs * FPS)):
        t = step / FPS; fr = plate.copy()
        for i, p in enumerate(drawn):
            st = part_state(p, t)
            if st is None: continue
            sx, sy, dx, dy, rot, al = st
            im = xform(p['img'], max(.02, sx), max(.02, sy), rot)
            if boil > 0: im = line_boil(im, step, amp=boil, hold=3, seed=seed + i)
            if al < 1: im.putalpha(Image.fromarray((np.array(im)[..., 3] * al).astype(np.uint8)))
            x = cx0 + (p['cx'] - lw / 2) * sc + dx; y = cy0 + (p['cy'] - lh / 2) * sc + dy
            paste(fr, im, x, y)
        ty = cy0 + lh * sc / 2 + H * 0.07
        if tagline and t >= t_tag:
            pop_text(fr, tagline, None, (W / 2, ty), t - t_tag, size=int(W * 0.068), fill=tag_fill, color=ink,
                     stroke_px=max(6, int(W * 0.008)), rot=-2, burst=False)
        if sub and t >= t_sub:
            pop_text(fr, sub, None, (W / 2, ty + W * 0.1), t - t_sub, size=int(W * 0.045), fill=sub_fill, color=ink,
                     stroke_px=max(4, int(W * 0.005)), rot=-2, burst=False)
        # fade out last 0.35 s
        fo = clamp((secs - t) / 0.35)
        if fo < 1: fr = fr * fo + plate * (1 - fo)
        pr.stdin.write(np.clip(np.rint(fr), 0, 255).astype(np.uint8).tobytes())
    pr.stdin.close(); pr.wait()
    if not audio:
        os.replace(tmp, out); return parts
    wav = out + '.a.wav'
    m = sfx.mix(secs, events=[e for e in ev if e[0] < secs], bed=True)
    import wave
    with wave.open(wav, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sfx.SR)
        wf.writeframes((np.clip(m, -1, 1) * 32767).astype(np.int16).tobytes())
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-i', wav, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k',
                    '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-shortest', out], check=True)
    os.remove(tmp); os.remove(wav)
    return parts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('logo'); ap.add_argument('out')
    ap.add_argument('--size', default='1080x1920'); ap.add_argument('--secs', type=float, default=8.0)
    ap.add_argument('--bg', default='auto'); ap.add_argument('--tagline'); ap.add_argument('--sub')
    ap.add_argument('--logo-w', type=float, default=0.78); ap.add_argument('--boil', type=float, default=1.1)
    ap.add_argument('--seed', type=int, default=7); ap.add_argument('--no-audio', action='store_true')
    ap.add_argument('--parts-sheet'); ap.add_argument('--key-tol', type=int, default=38)
    ap.add_argument('--ink', default='#111111'); ap.add_argument('--tag-fill', default='#FFFFFF'); ap.add_argument('--sub-fill', default='#F4A73B')
    A = ap.parse_args()
    W, H = (int(v) for v in A.size.lower().split('x'))
    parts = render(A.logo, A.out, (W, H), A.secs, A.bg, A.tagline, A.sub, A.logo_w, A.boil, A.seed, not A.no_audio,
                   A.parts_sheet, A.key_tol, A.ink, A.tag_fill, A.sub_fill)
    kinds = {}
    for p in parts: kinds[p['kind']] = kinds.get(p['kind'], 0) + 1
    print('[logo_intro] parts:', kinds, '->', A.out)


if __name__ == '__main__':
    main()
