# Limb salvage surgery: Zack D look, image frames + pose packs (9:16, Hinglish)

Patient-education reel (~57 s) made the default way: **image frames in a 3D-toy style, not three.js.**

## How it was made
1. **Script** (`script.json`): 8 Hinglish VO lines, one action per line. VO with Cartesia `sonic-latest`, language `hi`,
   the creator's cloned voice (`CARTESIA_API_KEY`, `CARTESIA_VOICE_ID` from env; never commit keys).
2. **Master frames** (one per beat), Zack D lock: glossy ultra-smooth plastic toy shader, subsurface skin,
   octane look, golden rim light back-left, softbox front, flat #6EC6FF background, 9:16.
3. **Pose packs** = image edits of each master with the master as the only reference and "same framing, same
   position and size":
   - patient: worried -> looks up scared
   - surgeon: explain -> "nahi" finger wag -> thumbs-up wink
   - surgeon at MRI hologram: point -> turn to camera and explain
   - physio walk: walk A (left foot) / walk B (right foot), flip-booked at ~3 steps/s with bob
   - end card: stand -> thumbs-up + wave
4. **Object cut-outs and state plates:** leg with tumour -> same leg with the segment removed (`leg_gap`),
   tumour segment alone and implant alone on #00FF00 (transparent). In code the segment lifts out, the implant
   drops into the gap and lands with a flash, then cross-cuts to the leg-with-implant plate.
5. **Cut-outs** from flat backgrounds: `cut.py` keys each frame against the per-row edge colour (soft alpha).
6. **Animation** (`render.py`): living poses (hard cut + squash, breath, sway), camera push/drift, gradient + bokeh
   background behind cut-outs, pulsing tumour glow, MRI scan sweep + ping rings, metal shine sweep, sparkles,
   travelling glow along nerves, pop-in pills with leaders, word-pop captions, zoom-punch transitions.
7. Audio: VO + procedural SFX (`motion2d/sfx.py`) + soft bed, loudness normalised.

`python3 render.py stills 4.5 12 23.5 29.5 46` for a storyboard strip, `python3 render.py video 0 1713 out.mp4` to render.
Image assets are not committed (regenerate from the prompts above).
