# Text styles: title motion, captions, step markers

**Every video picks its own text look.** Text is the first thing a viewer recognises, so a new video that reuses
the last one's title card, step chip and caption pill looks like a clone even with a new set. Pick by NAME in the
look sheet (`docs/FRESH_LOOK.md`); the engines read the same names:

```json
"look": {
  "title_motion": "draw-on",            // template/index.html titles + labels, motion2d/textfx.py
  "captions_preset": "chalk-hand",      // scripts/captions.py (burned ASS) + the template's in-canvas "sub" captions
  "step_style": "tape-strip",           // template step marker: chip | counter-dial | tape-strip | none
  "captions_position": "bottom"         // optional: bottom | center | top | lower-third (else the preset's own spot)
}
```

Rules
- `scripts/captions.py` has **no default**. Without `--preset`, `--style` or `--project` (with `look.captions_preset`)
  it exits with an error pointing here. `--style pop|karaoke` still produces the old yellow/white Baloo look, unchanged,
  for old projects.
- Colours come from `look.palette` (or `--palette`): darkest = outline / box, lightest = text, most saturated = accent.
  No more fixed yellow.
- `scripts/lint.py` ERRORs on a missing or unknown `title_motion` / `captions_preset` (and an unknown `step_style` /
  `captions_position`). It also ERRORs when the pair equals a shipped example's: braces-tutorial = `card-rise` + `pop-word`
  or `pill`, dhai-baje = `slow-fade` + `pop-word`, painted-duet = `none` + `pop-word`. With `look.reuse_reason` (a real
  series reason) that becomes a WARN.
- Never two videos in a row with the same pair. Check the user's last videos.
- Devanagari (Hindi) captions: Fredoka, Caveat and the DejaVu fonts have no Devanagari glyphs. Keep the preset and add
  `--font "Baloo 2"` (Baloo 2 covers Devanagari + Latin), or write captions in Hinglish (Latin script).
- Everything is raster: canvas `fillText` / `strokeText` / clip in three.js, PIL in 2D, libass for captions. **No SVG.**
- Readability first: captions stay ≤ 2 lines, ≥ 4.5:1 contrast with their edge or box, and above the Shorts/Reels UI on
  vertical (the presets' `bottom` margin already handles 9:16).

## Title / label motion (`look.title_motion`)

The template draws titles, end card and 3D labels with it (`fxText()` in the TEXTFX block of `template/index.html`).
For 2D pipelines: `from textfx import text_fx` (`motion2d/textfx.py`) returns an RGBA layer at time t; paste it with
`motion.paste`. `settle_time(preset, text)` tells when it is static.

| Preset | What it does | Use it for | Avoid for |
|---|---|---|---|
| `card-rise` | cream rounded card rises with back overshoot (template default, **used by braces example**) | only a deliberate series look with `reuse_reason` | anything new: it is the clone signal |
| `slam-squash` | type slams in from ~2x scale, squashes and settles | punchy reels, comedy, promos, myth-busting hooks | calm clinical explainers, horror |
| `typewriter` | letters typed one by one, accent cursor blinks then leaves | lab readouts, data, "case file", RPE turn logs, mono looks | long titles (> 30 chars gets slow) |
| `mask-wipe` | an accent bar sweeps across and leaves the text behind | clean modern explainers, product-style, chapter cards | hand-made / paper looks |
| `letter-bounce` | each letter drops in and bounces, staggered | kids' content, paper-cut, playful cartoon episodes | serious/clinical, horror |
| `slide-stack` | lines slide in from alternating sides and stack | multi-line titles, step names, editorial / magazine looks | single short words |
| `marker-sweep` | a highlighter swipe draws behind the text left to right | study notes, "important" points, whiteboard / notebook sets | dark horror sets |
| `draw-on` | the outline is revealed left to right (raster clip), then the fill floods in | chalkboard, blueprint, technical drawing, hand-drawn styles | fast cuts (< 1 s on screen) |
| `slow-fade` | long fade with letter tracking closing in | horror, documentary, emotional beats, elegant serif looks | energetic reels |
| `none` | no on-screen titles | pure story / character pieces where text would break the spell | tutorials (they need step names) |

## Step marker (`look.step_style`, template)

| Style | Look | Use it for |
|---|---|---|
| `chip` | cream pill with a red number dot + "STEP n / N" (template default, braces example) | series reuse only |
| `counter-dial` | dark dial, progress arc fills to n/N, tick marks, big number; name animates with title_motion | procedures with a count (turns, steps, trays), RPE, aligners |
| `tape-strip` | masking-tape strip with torn ends, slight tilt, slaps on with overshoot | lab-bench, hand-made, craft, Hawley/wire-bending |
| `none` | no marker | continuous demos where the VO carries the steps |

## Caption presets (`look.captions_preset`)

Burned ASS: `python3 scripts/captions.py words.json captions.ass --w 1080 --h 1920 --project <dir>` or
`--preset NAME --palette "#..,#..,#.."` (`--list` prints them). The template's in-canvas `sub` captions use the same
names. Fonts ship in `fonts/` (Baloo 2, Fredoka, Caveat, DejaVu Serif, DejaVu Sans Mono).

| Preset | Look (default spot) | Use it for | Avoid for |
|---|---|---|---|
| `pop-word` | active word pops in the accent colour, others light; Baloo 2 (bottom) | fast talking-head reels, comedy | the braces example look when paired with `card-rise` |
| `karaoke-sweep` | colour sweeps through each line word by word; Fredoka (lower third) | songs, rhymes, kids, read-along | dense technical lines |
| `lower-third-ticker` | left-aligned strip in a solid box, first word in accent, letters tick in from wide tracking (lower third) | news / documentary / clinical explainers, 16:9 | 9:16 with a busy lower half |
| `marker-highlight` | light text; the active word gets a fat accent highlighter behind dark ink (bottom) | study notes, key terms, tutorials | horror, low-contrast palettes |
| `outline-bold` | heavy-outline caps, no box, the whole line punches in; Fredoka (center) | Shorts/Reels hooks, gaming, hype | long sentences, calm pieces |
| `typewriter-reveal` | mono type revealed letter by letter with a cursor, in a dark box, left-aligned (bottom) | readouts, lab logs, mystery, tech | fast VO (> 190 wpm) |
| `stacked-bounce` | one word per row, each bounces in, alternating accent colours (center) | 3-word punchlines, promos, hooks | full-sentence narration |
| `minimal-serif` | small sentence-case serif, soft shadow, slow fades, no box (bottom) | horror, documentary, emotional, premium | kids, loud reels |
| `chalk-hand` | Caveat handwriting in chalk colour, slight tilt, words written on one by one (bottom) | chalkboard, classroom, hand-drawn, folk tales | clinical precision, tiny screens |
| `pill` | white text in a dark box (template / braces default) | series reuse, accessibility-first CC look | anything new paired with `card-rise` |

Position override: `--position` or `look.captions_position` (`bottom`, `center`, `top`, `lower-third`).
Colour override: `--active RRGGBB` (accent) / `--idle RRGGBB` (text). `--upper`, `--max-words N`, `--font NAME`.

## Picking a pair (quick guide)

| Genre / style | Good pairs (title_motion + captions_preset + step_style) |
|---|---|
| Dental / ortho tutorial, clinical | `mask-wipe` + `lower-third-ticker` + `counter-dial`; `marker-sweep` + `marker-highlight` + `tape-strip` |
| Lab / wire bending | `draw-on` + `chalk-hand` + `tape-strip`; `slide-stack` + `minimal-serif` + `tape-strip` |
| Hindi / Hinglish horror short | `slow-fade` + `minimal-serif`; `typewriter` + `typewriter-reveal` (found-footage) |
| Promo / product | `slam-squash` + `stacked-bounce`; `mask-wipe` + `karaoke-sweep` |
| Kinetic-type reel | `letter-bounce` + `outline-bold`; `slam-squash` + `stacked-bounce` |
| Hand-drawn / chalk / folk | `draw-on` + `chalk-hand` |
| Cartoon episode | `letter-bounce` + `pop-word`; `none` + `karaoke-sweep` |
| Screencast | `typewriter` + `lower-third-ticker` |

Credit: Swapnil Agrawal (BDS intern)
