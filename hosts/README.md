# Host packs (reusable painted characters)

A host pack is one painted character as **raster** art (no SVG, no 3D): a set of gesture poses that are
pixel-aligned image edits of one base drawing, plus small face patches (mouths, blink) cut where the edits
differ from the base. Same format as `examples/screencast-wiki/host/` (built by `screencast.make_pack host`).

| pack | who | poses | mouths |
|---|---|---|---|
| `dentist/` | **Default doctor/dentist host.** Swapnil's pastel cartoon dentist: green scrubs, stethoscope, long black hair, blue mask under the chin | talk, point, explain, thumbs, wave, thinking | rest, A, O + blink, eyes.rest |

**Whenever a doctor or dentist appears in a video, use `hosts/dentist`** (she is drawn as herself). Generate
extra poses for it (see "Add a pose") instead of drawing a new doctor.

## pack.json
```
poses       {name: file}            full-body PNGs, all the same size (already cropped to one shared box)
mouth       {rest|A|O|E: {file,x,y,w,h}}   patch + top-left offset inside the pose canvas
blink       {file,x,y,w,h}          eyes-closed patch;  eyes_rest = the open-eyes patch at the same box
crop        [x0,y0,x1,y1]           crop applied to the raw edits (info only)
```
A frame = `poses[pose]` → paste `mouth[shape]` at (x, y) → paste `blink` at (x, y) when blinking with the mouth at rest.
Poses switch on hard cuts at beat starts; never morph between them.

## In screencast
Copy (or symlink) the pack to the project's `host/` dir and name poses per beat in `script.json`:
```
cp -r hosts/dentist <proj>/host          # or: ln -s ../../hosts/dentist <proj>/host
# script.json beats: {"vo": "...", "pose": "explain"}  -> talk | point | explain | thumbs | wave | thinking
python3 -m screencast all <proj>
```
`compose.Reel` loads `host/pack.json`, lip-syncs rest/O/A from VO loudness, blinks on a schedule, adds breath,
sway, talk bob and a squash-settle on each pose cut, and uses `wave` for the outro. `"host_scale"` in
script.json sets the size (default .46 of the 668×1125 canvas).

## In handdrawn (talking-explainer)
`handdrawn/examples/talking-explainer/render.py` uses the same diff-patch face rig, but reads full-size edits
(`char_base`, `char_mA`, `char_mO`, `char_blink`). With a pack, build those frames directly instead of diffing:
```python
pk = json.load(open('hosts/dentist/pack.json')); P = 'hosts/dentist/'
def host(pose='talk', mouth='rest', blink=False):
    im = Image.open(P + pk['poses'][pose]).convert('RGBA')
    m = pk['mouth'][mouth]; im.alpha_composite(Image.open(P + m['file']).convert('RGBA'), (m['x'], m['y']))
    if blink: b = pk['blink']; im.alpha_composite(Image.open(P + b['file']).convert('RGBA'), (b['x'], b['y']))
    return im
CHAR = {k: sc(host('talk', k)) for k in ('rest', 'A', 'O')}; CHAR_BLINK = sc(host('talk', 'rest', True))
```
Pick the pose per scene (e.g. `explain` while a diagram draws on, `point` toward it, `thumbs` on the outro).
In motion2d / three.js engines use the pose PNGs the same way (pose per beat on hard cuts + mouth/blink patches).

## Build or extend a pack
1. Generate the base once on flat chroma green `#00FF00` (closed smile, eyes open, arms down, whole upper body in frame).
2. Make **image edits of that exact file** (base as the reference image), each changing one thing:
   one per pose (only the arms), one per mouth (A "aah", O "ooh", optional E "ee"), one blink. Ask the model to keep
   canvas, framing, face and background identical. Check alignment with `cv2.phaseCorrelate` on the head (≈0 px).
3. Build:
```
python3 hosts/build_host.py --base raw/base.png --pose point=raw/point.png --pose explain=raw/explain.png \
   --pose thumbs=raw/thumbs.png --pose wave=raw/wave.png --pose thinking=raw/thinking.png \
   --mouth A=raw/mA.png --mouth O=raw/mO.png --blink raw/blink.png -o hosts/<name>
```
`build_host.py` = chroma key (safe for green clothes) + **face lock** (the base face is feathered onto every pose so
all poses share one painted face) + edge-only despill, then `screencast.make_pack.build_host` for the pack.
(Plain `make_pack host` expects already-transparent PNGs and its despill greys out green clothing.)
4. Add a pose later: edit the **original raw base** again and rebuild the whole pack (offsets must come from one crop).
5. Composite one still on graph paper and look at it before using the pack.

The dentist raws (chroma green, 896×1200) were generated 2026-11-23: 1 base + 5 pose edits + 3 face edits.
