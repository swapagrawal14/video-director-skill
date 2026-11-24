# ZIPZOOM truck sting (hand-drawn finish demo)

6 s, 1080x1920, 24 fps, on twos (ones for the title slam). Fully procedural: the truck, wheels, bubble, puffs,
clouds and type are drawn with PIL as raster, music and SFX are synthesised with numpy. No image model, no SVG.

```
python3 examples/truck-sting/render.py --sheet --gif
python3 scripts/qa.py examples/truck-sting/zipzoom_sting.mp4      # QA PASSED
```
Writes `zipzoom_sting.mp4` (gitignored), `contact_sheet.jpg`, `onion.png` and `docs/img/truck-sting.gif`.
`--still 3.1` renders one frame to `still.png`.

Beat sheet (120 bpm): 0-1.5 s truck putters in hopping on beats, wheels roll, speed lines, dust trail, smear on
the fastest drawings -> 1.5 brake squeak + nose dip + dust cloud + boing -> 2.0 "COOL!" bubble pops -> 2.8 whoosh,
3.0 ZIPZOOM slams with shake -> 3.45 ink underline draws on (scribble) -> 4.0 tagline pops -> 5.0 big hop ->
5.5 end chord. Exhaust putts on 2.5/3.5/4.5/5.5.

Look: tangerine paper `#FF8F45`, cream `#FFF3D6`, cobalt `#2D5BD3`, sun `#FFC93C`, coral `#FF5A5F`, ink `#1A1423`.
"ZIPZOOM" and the truck are original. How it works: `docs/HAND_DRAWN.md`. Credit: Swapnil Agrawal (BDS intern).
