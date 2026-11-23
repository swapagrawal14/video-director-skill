#!/usr/bin/env python3
"""Read the art style of a reference (image or video, e.g. a Pinterest reel the person likes) and write a style
pack you can lock a whole cartoon to: palette, outline, prompt core, and a swatch sheet.

    python3 scripts/style_ref.py ref.mp4 projects/<slug>/style.json [--name cosy_room] [--k 6]

The style is the LOOK only. Never copy the reference's characters, brand, logo, text or story.
Then: style_prompt(json.load(open('style.json')), '<subject>', kind='character') for every asset.
"""
import argparse, json, os, sys
import cv2
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'motion2d'))
from cartoon import style_from_reference, palette_sheet, style_prompt  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('ref'); ap.add_argument('out')
ap.add_argument('--name', default='from_reference'); ap.add_argument('--k', type=int, default=6)
a = ap.parse_args()
st = style_from_reference(a.ref, k=a.k, name=a.name)
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
json.dump(st, open(a.out, 'w'), indent=1)
sheet = os.path.splitext(a.out)[0] + '_palette.png'
cv2.imwrite(sheet, palette_sheet(st))
print(json.dumps(st['measured']))
print('palette:', ' '.join(st['palette']), '| outline px:', st['outline_px'], '| ink:', st['ink'])
print('prompt core:', st['core'])
print('example prompt:\n' + style_prompt(st, 'a sleepy girl in a striped kurta', kind='character'))
print('wrote', a.out, 'and', sheet)
