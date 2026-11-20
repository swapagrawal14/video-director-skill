"""Procedural shader-style backgrounds rendered with numpy."""
import numpy as np

PALETTES = {
    "day": ((0.45, 0.72, 0.98), (0.95, 0.97, 1.0)),
    "sunset": ((0.98, 0.45, 0.35), (1.0, 0.85, 0.55)),
    "night": ((0.04, 0.06, 0.18), (0.18, 0.15, 0.38)),
    "rain": ((0.35, 0.40, 0.48), (0.65, 0.68, 0.72)),
}


def render(w, h, t, mood="day", bg="sky"):
    top, bot = (np.array(c) for c in PALETTES.get(mood, PALETTES["day"]))
    y = np.linspace(0, 1, h)[:, None, None]
    img = top * (1 - y) + bot * y
    img = np.broadcast_to(img, (h, w, 3)).copy()
    xs = np.linspace(0, 1, w)[None, :]
    ys = np.linspace(0, 1, h)[:, None]
    # drifting soft clouds / glow
    n = 0.5 + 0.5 * np.sin(xs * 9 + t * 0.4 + np.sin(ys * 7 - t * 0.3) * 2)
    n *= 0.5 + 0.5 * np.sin(ys * 5 + t * 0.2)
    img += (n * (1 - ys) * 0.12)[..., None]
    if mood == "night":
        rng = np.random.default_rng(7)
        sx, sy = rng.integers(0, w, 120), rng.integers(0, int(h * 0.6), 120)
        tw = 0.6 + 0.4 * np.sin(t * 3 + sx)
        img[sy, sx] = np.clip(img[sy, sx] + tw[:, None], 0, 1)
    if mood == "rain":
        streak = (np.sin(xs * 260 + ys * 40 - t * 30) > 0.985).astype(float)
        img += streak[..., None] * 0.25
    # ground
    ground = ys > 0.78 + 0.02 * np.sin(xs * 6)
    gc = np.array((0.30, 0.62, 0.35)) if mood != "night" else np.array((0.08, 0.18, 0.12))
    img[np.broadcast_to(ground, (h, w))] = gc
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)
