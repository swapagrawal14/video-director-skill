#!/usr/bin/env python3
"""Generate a 33^3 .cube LUT procedurally (no downloads, no licence issues).
Usage: python3 scripts/make_lut.py horror.cube horror|teal_orange|warm|bleach"""
import sys, colorsys
out, look = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'horror')
N = 33
def clamp(x): return max(0.0, min(1.0, x))
def scurve(x, k):  # contrast around 0.5
    return clamp(0.5 + (x - 0.5) * k) if k != 1 else x
def grade(r, g, b):
    l = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if look == 'horror':      # desaturated, crushed, cold teal shadows, sickly green mids
        s = 0.45; r, g, b = [l + (c - l) * s for c in (r, g, b)]
        sh = (1 - l) ** 2
        r -= 0.06 * sh; g += 0.02 * sh; b += 0.05 * sh
        g += 0.015 * (1 - abs(l - 0.5) * 2)
        r, g, b = [scurve(c, 1.25) - 0.03 for c in (r, g, b)]
    elif look == 'teal_orange':
        sh = (1 - l) ** 1.5; hi = l ** 1.5
        r += 0.08 * hi - 0.05 * sh; g += 0.02 * hi + 0.01 * sh; b += -0.07 * hi + 0.07 * sh
        r, g, b = [scurve(c, 1.12) for c in (r, g, b)]
    elif look == 'warm':
        r, g, b = r * 1.05 + 0.01, g * 1.01, b * 0.92
    elif look == 'bleach':    # bleach bypass
        s = 0.35; r, g, b = [l + (c - l) * s for c in (r, g, b)]
        r, g, b = [scurve(c, 1.35) for c in (r, g, b)]
    return clamp(r), clamp(g), clamp(b)
with open(out, 'w') as f:
    f.write(f'TITLE "{look}"\nLUT_3D_SIZE {N}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
    for bi in range(N):          # .cube order: red changes fastest
        for gi in range(N):
            for ri in range(N):
                r, g, b = grade(ri / (N - 1), gi / (N - 1), bi / (N - 1))
                f.write(f'{r:.6f} {g:.6f} {b:.6f}\n')
print('wrote', out)
