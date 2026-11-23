# Screencast tutorial reels (`screencast/`)

A 9:16 tutorial reel: graph-paper desk, torn-paper title strip, and a **real browser recording** on a tilted, taped card. The recording auto-zooms to each action, with an eased hand cursor, click bursts, marker circles and STEP chips. Below it, a **painted talking host** gestures on hard cuts (point, explain, wave, thumbs-up) with lip-sync and blinks. Karaoke captions run throughout, and it ends on a FOLLOW badge. Everything is raster: no SVG, no 3D.

## Project layout
```
<proj>/script.json     title, end card, beats, browser steps (see examples/screencast-wiki)
<proj>/host/           host pack from make_pack (poses + face patches)
```
- `beats[k]`: `vo` (spoken), `sub` (optional caption text, e.g. Devanagari), `pose` (a pose name from the pack), `step` (chip number), `circle` (marker-circle the beat's click target), `zoom` (default true), `after_click: "out"` (zoom out after a click that navigates).
- `steps`: Playwright actions `goto`, `wait`, `type [sel, text]`, `click`, `press`, `hover`, `scroll`, `scroll_to`, plus `{"mark": name}`. Beat k plays the capture between mark k-1 and mark k, so use exactly `len(beats) - 1` marks.
- `css`: a stylesheet injected on every page to hide cookie or donation banners.
- `voice_id` + `language`: Cartesia (the key goes in the env, or is injected on the wire). Without it, edge-tts `edge_voice` is used.

## Host pack (pose-to-pose, one painted face)
Paint one base drawing, then make **image edits of that exact file**: one per gesture pose (only the arms change), one per mouth (A, O, E) and one blink.
```
python3 -m screencast.make_pack host --base talk.png --pose point=point.png --pose explain=explain.png \
   --pose wave=wave.png --pose thumbs=thumbs.png --mouth A=mA.png --mouth O=mO.png --blink blink.png -o <proj>/host
```
The face patches are cut where each edit differs from the base, so the expression never changes on its own. Poses switch on **hard cuts** at beat starts, with a squash-and-settle. Breathing, sway and a talk bob are layered on top. The outro switches to `wave`.

## Camera, cuts, backgrounds, captions (`screencast/fx.py`, all on by default)
Retention comes from change: something new should land every 2.5 to 3.5 s.
- **Camera**: each beat gets a slow push-in (1.00 to 1.05), sine drift, a tiny roll, and a punch-in kick on the cut.
- **Cuts**: every beat boundary gets a transition: `whip` (motion-blur slide), `rip` (torn-paper wipe), `zoomblur` (radial punch) or `flash`. Set it per beat with `"transition"`, otherwise the cuts rotate. The outro uses `"outro_transition"`.
- **Backgrounds swap on each cut** for contrast: `graph` (paper), `chalk` (dark board), `sun` (yellow halftone), `teal` (stripes), `pink` (confetti). Set one per beat with `"bg"`, or give the whole list with `"backgrounds"`. On a dark background the caption pill flips to light, so the text always contrasts.
- **Captions** `"fx": {"captions": "box"}`: a rounded pill holding chunks of up to 3 words. Latin words scramble in for 0.12 s. The spoken word is in the beat's accent colour. Devanagari words use Noto Sans Devanagari (shaped with raqm). Use `"karaoke"` for the older outline style.
- **Finish**: vignette and per-frame grain. **Outro**: FOLLOW badge, a hand-drawn arrow and a sketched play sticker (raster, drawn in code).
- Turn any of these off with `"fx": {"camera": false, "transitions": false, "bg_rotate": false, "finish": false}`.

## Sound, stickers, redaction
- **SFX** (`screencast/sfx.py`, `python3 -m screencast sfx <proj>`): every sound is synthesized in numpy, so it is original and needs no sample licence. Cuts get a whoosh (whip, zoomblur), a paper rip (rip) or a shimmer (flash). Clicks get a click, typed fields get key ticks, STEP chips and stickers get a pop, and the outro gets a riser and a ding. The result is `mix_sfx.wav`, which `render` uses when it exists. Silence one beat with `"sfx": false`. Audition the kit with `python3 -m screencast.sfx demo <dir>`.
- **Word stickers**: `"sticker": {"text": "1 CLICK", "at": .4, "color": "#ffd23f", "x": .78, "y": 215, "tilt": -8}` on a beat pops a die-cut starburst with a pop sound. Any word or colour; it is drawn in code per video.
- **Redaction**: `"blur": [[x, y, w, h], ...]` (capture pixels) on a beat, or at the top level for the whole video, blurs emails, names, API keys or account details before zoom. Always redact anything personal that shows up in a capture.

## Assets are a starting kit, not a limit
Nothing in `screencast/assets/` is fixed. An agent making a video should generate whatever that video needs: new host characters and poses (image edits of one base drawing), props, stickers, backgrounds, cursors, badges and sounds, raster only (no SVG, no 3D). Add a new background kind to `fx.make_bg`, a new cue to `sfx.make`, or a new pose to the host pack whenever the script calls for one. Reuse the kit only where it already fits.

## Mobile mode (experimental)
`"device": "mobile"` in `script.json` records a phone instead of a desktop browser (Pixel 7 by default, or any Playwright device name), with `tap`, `swipe` and `long_press` steps, a phone frame and a finger. It is still a work in progress: check every still before rendering, and use desktop mode for anything that must ship today.

## Run
```
python3 -m screencast capture <proj>     # Playwright -> capture/frames + capture.json (boxes, events, marks)
python3 -m screencast voice   <proj>
python3 -m screencast build   <proj>     # timeline.json (VO-driven), music, ducked mix at -14 LUFS
python3 -m screencast stills  <proj> 3 8 15 21   # LOOK before rendering
python3 -m screencast render  <proj> out.mp4 --jobs 2
```
- Timing: each beat's capture plays after a 0.35 s lead, slowed down to 0.6x to fill the VO, then holds its last frame. A span that is too long is sped up.
- Chromium on a bare Debian box may be missing `libatk`, `libatspi`, `libXcomposite` or `libXdamage`. Without root, download the debs, run `dpkg -x` on them into a folder, and set `LD_LIBRARY_PATH`.
- Hindi pages need a Devanagari font (`~/.fonts/NotoSansDevanagari.ttf`, then `fc-cache`), or Chromium renders boxes.
- Render speed is about 0.3 to 0.5 s per frame per job at 720×1280. The output is upscaled to 1080×1920.
