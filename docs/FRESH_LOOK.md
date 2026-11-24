# Fresh look every video (anti-clone)

**Rule: every video gets its own look. The examples in `examples/` are a QUALITY BAR, never a template.**

`examples/braces-tutorial` shows how polished a finished film must be (modelling detail, tools that travel and act,
per-scene FX, clean labels). It does not show what your video should look like. Do not copy its wooden bench,
its tooth mascot "Dentu", its Pixar Clinic colours, its title card, step chips or caption pill. The same holds for the
`template/` defaults: the bokeh backdrop, wooden bench + mat, tooth mascot and Pixar Clinic theme are placeholders
that prove the engine runs. Replace them every time.

If someone asks for "an ortho appliance tutorial like the braces one", they want the same *quality*, not the same
*video*. A viewer who watched one of these videos must not recognise the set, the character or the captions in the next.

`scripts/lint.py` enforces this (build fails on ERROR):

| Check | Fails when |
|---|---|
| (a) look sheet | `project.json` has no `look` block, a field is empty, or any `"CHANGE ME"` is left in `look` / `theme` |
| (a2) text look | `look.title_motion` / `look.captions_preset` missing or not a preset name from `docs/TEXT_STYLES.md`; `step_style` / `captions_position` not a known value; or the pair equals an example's (braces-tutorial: `card-rise` + `pop-word` or `pill`) without `look.reuse_reason` |
| (b) default palette | 3+ of `accent #e2475b`, `accent2 #3b82c4`, `bench #c98e5a`, `mat #3e8e93`, `background ["#24557a","#5fa6b8","#f2cfa8"]` are kept (missing keys count, since the template falls back to them), unless `look.reuse_reason` explains why |
| (c) default set / mascot | `index.html` still contains "Dentu", or the template tooth mascot while scenes use `"mascot"`, or the template wood-grain bench with the bench visible |
| (d) copied scene | `index.html` is more than 85 % identical (normalised lines) to `examples/braces-tutorial/index.html` or `template/index.html` |
| (e) copied script | any `vo` / `sub` line is identical to a line of `examples/braces-tutorial/script.json` |

`lint.py --pre-build` skips (c) and (d) (used by `make_video.py` right after timing, before `index.html` is built).
`look.reuse_reason` is only for a deliberate series look (e.g. "part 2 of the user's braces series, she asked for the
same set"). Write the user's actual reason; "looks nice" is not one.

---

## The look sheet (mandatory, before any asset)

Write it right after the treatment pick (`docs/INTAKE.md`, "After the pick", step 0) and before any image, model,
voice or storyboard. Put it in `project.json` as `look`, and set `theme` from `look.palette`.

```json
"look": {
  "set": "where the action happens: the stage, surface, background and lighting",
  "palette": ["#0e1621", "#7fd1ff", "#f4f1ea", "#ff8a3d"],
  "character": "who (if anyone) guides the viewer, or \"none\"",
  "type": "title font and title treatment",
  "captions": "caption, label and step-marker style",
  "camera": "camera language: lens feel, moves, framing habits",
  "signature": "the one visual move this video is remembered for",
  "title_motion": "mask-wipe",
  "captions_preset": "lower-third-ticker",
  "step_style": "counter-dial",
  "captions_position": "lower-third",
  "reuse_reason": ""
}
```

| Field | What to decide | Bad (clone) | Good (own) |
|---|---|---|---|
| set / stage | Surface, backdrop, light, scale world | wooden bench + teal mat + bokeh | a lab counter under a magnifier lamp, an X-ray lightbox wall, inside the mouth at tooth scale |
| palette | 3-5 hex, one accent, one secondary, one highlight, darks/lights | `#e2475b / #3b82c4 / #ffd23f` | built from the set (steel blue + acrylic pink, lightbox cyan + amber) |
| hero object | The thing that is built or acts on screen | generic typodont reused | the appliance itself, modelled for this video |
| character | Guide or none; never the tooth mascot | Dentu | a gloved hand, the user's painted host (`hosts/dentist`), a talking plier, a molar band with eyes, none |
| typography + captions | Font, title motion (`title_motion`), caption preset (`captions_preset`), label and step style (`step_style`); pick by name from [`docs/TEXT_STYLES.md`](TEXT_STYLES.md) | cream card rising + "STEP n / N" chip + dark caption pill (`card-rise` + `chip` + `pill`/`pop-word`) | `draw-on` titles + `chalk-hand` captions, `typewriter` + `typewriter-reveal` readouts, `slide-stack` + `lower-third-ticker`, `tape-strip` steps |
| camera language | How we look | slow orbit around a mat | macro slides, top-down "recipe" cam, POV from the palate, fixed tripod + inserts |
| signature move | One memorable visual idea per video | none | each bend glows on a radiograph, screw turns count up like a dial, plates snap like magnets |

`title_motion`, `captions_preset`, `step_style` and `captions_position` are preset NAMES (the other fields are free text):
`scripts/captions.py --project`, `template/index.html` and `motion2d/textfx.py` read them. Full list with when to use each:
[`docs/TEXT_STYLES.md`](TEXT_STYLES.md).

The style the user names (hand-drawn, clay, 3D toy...) sits on top of the look sheet: same style can still have a
different set, palette, character and captions every time.

---

## Starting looks for common ortho appliances

Distinct starting points so no two videos match. None uses the wooden bench, the tooth mascot or the Pixar Clinic
palette. Treat each row as a seed: change it to the user's brief, style and audience.

| Appliance | Set / stage | Palette | Character idea | Type + captions | Camera | Signature move |
|---|---|---|---|---|---|---|
| **Hawley retainer** | Stone working cast on a lab counter under a round magnifier lamp, acrylic dust in the light | `#1d2b2a` `#e9e4d8` `#f28aa0` `#c7ccd1` | none; two gloved hands | rounded slab-serif titles, labels on masking-tape strips | top-down "recipe" cam, cut to 45° inserts | the pink baseplate pours in and sets around the wires in time-lapse |
| **Adams clasp** | Single molar on the cast, macro world: the tooth is a cliff, the wire a rope | `#0f1b2d` `#ffd166` `#d8dee6` `#ef6f6c` | a talking three-prong plier ("Teen-Prong") | condensed caps, measurement callouts like a technical drawing | macro slide along the wire, rack focus | the arrowheads glow when they seat into the undercuts |
| **Labial bow** | Front view of the upper anterior cast on a clean light table, soft shadowless light | `#f6f1e7` `#2b2d42` `#3a86ff` `#ffbe0b` | the user's painted host (`hosts/dentist`) pointing beside the cast | hand-lettered marker labels, caption as a lower-third ticker | locked tripod front view + side inserts | the U-loops draw themselves in light, then the wire follows the path |
| **Z-spring / finger spring** | Palatal view on a slate tile with chalk marks | `#2f3e46` `#f1faee` `#e76f51` `#84a98c` | none; a chalk arrow "character" that shows force direction | chalkboard type, captions written on in chalk | fixed occlusal (palatal) camera, slow push to the spring | the coil winds like a watch spring and the tooth eases along the chalk arrow |
| **RPE / rapid palatal expander** | Inside the mouth at tooth scale, looking up at the palatal vault like a cathedral ceiling | `#14213d` `#fca311` `#e5e5e5` `#9b2226` | a tiny engineer on the jackscrew (painted raster) | mono "readout" captions, step shown as a turn counter dial | POV from the tongue looking up, slow tilt | the screw turns and a dial counts the turns while the midline opens a hairline |
| **Twin block** | Side profile silhouette against a gradient wall, appliance shown inside a cut-away jaw | `#22223b` `#c9ada7` `#4ea8de` `#f2e9e4` | none; the two blocks behave like magnets | bold geometric sans, captions as arrows on the profile | lateral profile, fixed, then cut-away zoom | the blocks snap together and the lower jaw slides forward with them |
| **Headgear / facemask** | Studio cyclorama with a neutral head bust, one strong key light | `#111111` `#f5f5f5` `#2ec4b6` `#ff9f1c` | the painted host wearing it as a model | big poster-type titles, force vectors as animated arrows | 360° turntable around the bust, then side profile | force arrows grow from the strap/pad to the teeth and the maxilla |
| **Lingual arch** | Lower arch seen from above on a blueprint grid | `#0b2545` `#8da9c4` `#eef4ed` `#f4a259` | none; dimension lines and a ruler that moves | blueprint mono labels, dimension callouts | isometric overhead, lateral tracks | the arch length is "measured" live and holds steady as the molars try to drift |
| **Nance appliance** | Palatal view on a dark velvet tray, jewel-box lighting | `#1b1b2f` `#e43f5a` `#e9d8a6` `#94a1b2` | none | elegant serif titles, captions on thin gold rules | slow overhead push, macro on the acrylic button | the acrylic button settles on the rugae like a stamp pressing wax |
| **Space maintainer (band and loop)** | Kid-friendly paper-cut mouth with layered parallax, bright daylight | `#ffcad4` `#3d5a80` `#98c1d9` `#ee6c4d` | a baby molar and its loop as cut-out paper friends | rounded hand-cut paper letters, speech-bubble captions | side-scrolling parallax pans | the loop "holds the door open" for the permanent tooth to erupt |
| **Clear aligner** | Bright bathroom-shelf set or a clean product cyclorama, glossy reflections | `#f8f9fa` `#00b4d8` `#023e8a` `#ffb703` | none; product-hero treatment | thin modern sans, feature callouts one word + one line | turntable + macro on attachments | trays stack up in sequence and the smile updates tray by tray |
| **Bracket bonding** | Operatory chair-side tray of real instruments, cool clinical light, mouth with cheek retractor | `#0d1b2a` `#e0e1dd` `#06d6a0` `#ef476f` | none; gloved hands and instruments act | stencil-style step numbers on the tray, captions as instrument tags | over-the-shoulder operator view, cut to intraoral macro | the curing light's blue glow hardens each bracket with a tick on a progress strip |

Text presets that fit those rows (seeds, change them freely): Hawley `slide-stack` + `minimal-serif` + `tape-strip`;
Adams clasp `draw-on` + `lower-third-ticker`; labial bow `marker-sweep` + `lower-third-ticker`; Z-spring `draw-on` +
`chalk-hand`; RPE `typewriter` + `typewriter-reveal` + `counter-dial`; twin block `slam-squash` + `outline-bold`;
headgear `letter-bounce` + `stacked-bounce`; lingual arch `typewriter` + `typewriter-reveal`; Nance `slow-fade` +
`minimal-serif`; space maintainer `letter-bounce` + `pop-word`; clear aligner `mask-wipe` + `karaoke-sweep`; bracket
bonding `marker-sweep` + `marker-highlight` + `tape-strip`.

Before you start, check the project against older videos you or the user have made: if the set, palette, character
or caption style matches another of her videos, change it.

## Clinical accuracy

Look is free; facts are not. Appliance parts, steps, wire gauges, timings and indications must be correct. List
every clinical value in `FACTS.md` for review. Swapnil reviews the clinical details herself before anything ships;
never publish for her.

Credit: Swapnil Agrawal (BDS intern)
