# Hand-drawn / whiteboard engine (`handdrawn/`)

Raster-only hand-drawn animation: no SVG, no vector shapes, no code-drawn doodles. Every element is a PNG
(AI-painted line art made with the pack's `imageStylePrompt`, or the user's own art) or text rendered from a real font,
and everything moves through masks. The look comes from the swap-studio **style packs**.

## What it gives you (`handdrawn/hd.py`)
| Function | Effect |
|---|---|
| `load_style(name)` | One of 7 packs in `handdrawn/styles/` (swap-edu, swap-ai, chalkboard, minimal-mono, anime-pastel, newspaper-retro, neon-tech) or your own copied from `_template`. `extends` works. |
| `paper(W, H, S)` | Paper or board background with fibre grain and a soft vignette |
| `DrawOn(png).frame(p)` | **Pen draw-on**: the ink lines grow along themselves (per stroke group, geodesic order), then the colour washes in |
| `boil(rgba, t)` | Hand-drawn line boil, redrawn 8 times a second |
| `text_img` + `write_on` | Text writes itself with a ragged ink edge |
| `marker_swipe` | Highlighter swipe behind a key word |
| `karaoke(...)` | Captions that pop the spoken word in the pack's accent colour (feed it words.json from TTS) |
| `end_card(...)` | Avatar, name writing on, handle |
| `encode(...)` | Frames to H.264 MP4, with optional audio |

## Making a video
1. Pick a pack. Generate every illustration as a separate PNG with the pack's `imageStylePrompt`, using **bold dark outlines**, since `DrawOn` traces dark ink.
2. Make the VO and words.json with `scripts/tts_edge.py` or `scripts/tts_cartesia.py`.
3. Copy `handdrawn/examples/chai-doodle/render.py` and key each draw-on and write-on to the VO words.
4. Render with `python3 render.py <style> out.mp4`, then run `scripts/motion_qa.py out.mp4` and look at the strips before delivering.

`swap-edu` and `swap-ai` are Swapnil's own brand. Don't reuse them for anyone else; use a neutral pack or make a new one.
