---
name: logo-intro
description: Give any client logo (PNG), get a polished animated logo intro. The tool breaks the logo into its own parts (base shape, colour fills, letters, sparkles) and builds it on screen piece by piece with pops, bounces, twinkles, line boil, tagline and SFX.
author: Swapnil Agrawal (BDS intern)
---

# Logo intro playbook

Module: `motion2d/logo_intro.py` (tests: `tests/test_logo_intro.py`). A preset on top of `motion2d/` + the doodle kit
(`motion2d/doodle.py`). Example: [`examples/swap-creations-intro/`](../examples/swap-creations-intro/).

## The rule
The logo is the client's own raster art. The tool only **cuts it into parts and moves them**. It never redraws,
traces or vectorises a logo (no SVG, ever), and never changes its colours or letters.

## One command
```bash
python3 motion2d/logo_intro.py logo.png out.mp4 --size 1080x1920 --secs 8 \
  --tagline "ART · FASHION · YOU" --sub "LAUNCHING SOON" --parts-sheet parts.png
```
`--size 1920x1080` for YouTube, `1080x1080` for square. `--bg auto` keeps the logo's own background colour,
or pass a hex. `--boil 0` for a clean (non hand-drawn) look. `--seed` changes the fly-in directions.

## How it breaks the logo (automatic)
1. **Key**: PNG alpha is used as is. On a flat background, only the background connected to the border is keyed
   (fills inside outlines that share the background colour survive).
2. **Fills -> parts**: every solid colour region is a part. Anti-aliased slivers are dropped from the fills.
3. **Outlines**: each outline pixel goes to its nearest fill; smaller parts also carry their full outline so they
   land complete. Line art far from any fill (scissors, swashes) becomes its own part.
4. **Holes**: a big part that had smaller parts on top gets those holes painted in its own fill colour, so the base
   looks whole when it pops alone (you see a "colour-by-number" sketch that the fills then complete).
5. **Kinds**: `base` (largest), `inner` (sits inside the base), `letter` (mid-size, outside), `sparkle` (tiny).

Always look at `--parts-sheet` first. If the split is wrong, fix the input (clean PNG with alpha, bigger size)
rather than hand-placing parts.

## Timeline (built from the parts, seeded)
base pops with overshoot + squash (boing) -> inner parts fly in from around and land (pop each) ->
letters drop in left to right with a bounce (plip/tick) -> sparkles twinkle -> tagline slams in (squish) ->
sub-line pops -> hold -> 0.35 s fade. Audio is mixed from the same event list, loudness -14 LUFS.

## Quality bar
- Hook in the first 0.3 s (the base is already moving). Total 6-10 s for a sting, 12-15 s with a tagline hold.
- Tagline in the brand's own words; check spelling with the client. Max 2 text lines.
- Different brands should feel different: change `--bg`, `--seed`, timing (`--secs`) and the tagline colours
  (`--tag-fill`, `--sub-fill`, `--ink`) to fit the brand. Don't ship the Swap Creations look for every client.
- QA: watch it once muted (does it read?) and once with sound (is every landing on a sound?).
