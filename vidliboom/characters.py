"""Character layer. Poses live in assets/characters/<NAME>/<pose>.png
(AI-art cut-outs). A single assets/characters/<NAME>.png also works, and a
missing character falls back to a simple stand-in."""
import math
import os
from PIL import Image, ImageDraw

import os as _os
ASSETS = _os.environ.get("VIDLIBOOM_ASSETS", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "assets", "characters"))
_cache = {}


def _placeholder(name, size=360):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    hue = (sum(map(ord, name)) * 37) % 200 + 30
    d.ellipse((60, 20, 300, 260), fill=(255, 214, 170, 255))
    d.rounded_rectangle((90, 230, 270, 360), 40, fill=(hue, 120, 220 - hue // 2, 255))
    d.ellipse((130, 110, 155, 140), fill=(30, 30, 30, 255))
    d.ellipse((205, 110, 230, 140), fill=(30, 30, 30, 255))
    return im


def load(name, pose="idle"):
    k = (name, pose)
    if k not in _cache:
        for p in (f"{ASSETS}/{name}/{pose}.png", f"{ASSETS}/{name}/idle.png", f"{ASSETS}/{name}.png"):
            if os.path.exists(p):
                _cache[k] = Image.open(p).convert("RGBA")
                break
        else:
            _cache[k] = _placeholder(name)
    return _cache[k]


def has_poses(name):
    return os.path.isdir(f"{ASSETS}/{name}")


def pose(name, t, loud, h_target, pose_name="idle", phase=0.0):
    """loud: 0..1 speech loudness this frame (0 when silent)."""
    im = load(name, pose_name)
    s = h_target / im.height
    breathe = 0.012 * math.sin(t * 1.8 + phase)
    sq = 1 + breathe + 0.05 * loud
    tilt = 2.5 * loud * math.sin(t * 9 + phase)
    im = im.resize((max(1, int(im.width * s / sq)), max(1, int(im.height * s * sq))), Image.LANCZOS)
    if abs(tilt) > 0.2:
        im = im.rotate(tilt, resample=Image.BICUBIC, expand=True)
    bob = int(4 * math.sin(t * 2.2 + phase) - 10 * loud)
    return im, bob
