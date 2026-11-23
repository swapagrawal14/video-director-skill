---
name: artstyles
description: Gallery of the 10 cartoon style packs in motion2d/cartoon.py (ARTSTYLES): outline, palette, motion feel, night grade, best use and prompt tips; plus how to add a pack or derive one from a reference.
author: Swapnil Agrawal (BDS intern)
---

# Art style packs

A style pack locks everything that keeps a cartoon consistent across every asset and shot. Pick ONE per video
(playbook: [CARTOON.md](CARTOON.md)). Values below are read from `motion2d/cartoon.py`; if they ever differ, the
code wins. Packs describe a look in words only: never name or copy a studio, show, brand or living artist's
characters, and never put such names in prompts.

**How each field is used**
| Field | Used by | Effect |
|---|---|---|
| `core` | `style_prompt()` | style words in every asset prompt |
| `outline_px`, `ink` | `style_prompt()` | outline weight at 1080 px and its colour (0 = "no outlines at all") |
| `palette` | `style_prompt()`, `palette_match()`, `palette_sheet()` | the only colours allowed; the >= 0.6 style-lock gate |
| `hold` | `hold_time(t, hold)` | `ones` (24 drawings/s), `twos` (12), `threes` (8) |
| `squash` | `Cast(..., pop=...)` | squash-and-stretch on each pose cut and landing |
| `boil` | `doodle.line_boil(..., amp=...)` | hand-drawn line wobble in px (0 = off) |
| `paper`, `grain` | `make_style_finish()` | paper texture amount and film grain |
| `night` | `night_grade_for()` | the grade a lamp-off / night beat uses (a `GRADES` key) |

Quick look at any pack: `cv2.imwrite('swatch.png', palette_sheet('desi_gouache'))`.

## The 10 packs

### `pastel_outline`
Pastel cel, thin outline (cosy slice-of-life / gentle spooky)

| | |
|---|---|
| Outline | 4 px at 1080 in `#1E1E3A` |
| Palette | `#BDF4FF` `#A8F0D0` `#F25CC4` `#8C7BFF` `#FFE7B3` `#F7A08F` |
| Motion feel | hold `twos`, squash 0.07, boil 0.8 px |
| Finish | paper 0.0, grain 0.0 |
| Night grade | `violet` |
| Best for | cosy rooms, morning routines, gentle spooky gags, relatable reels |
| Prompt tips | Keep shapes round and silhouettes big; one flat shadow tone max. Name the room objects you will animate as separate parts. |

### `flat_no_outline`
Flat motion-design, no outlines (promo loops, brand mascots)

| | |
|---|---|
| Outline | none (ink `#2B3A55` for small details) |
| Palette | `#3FA9F5` `#FFE14D` `#F26A3D` `#E8E0D0` `#3C4A5E` `#2FA36B` |
| Motion feel | hold `ones`, squash 0.1, boil 0.0 px |
| Finish | paper 0.0, grain 0.0 |
| Night grade | `blue` |
| Best for | promo loops, brand mascots, app explainers, logo-adjacent stings |
| Prompt tips | Ask for "shapes separated by colour only"; give every object one flat shadow shape. Hold on ones = crisp, so ease snappily. |

### `rubber_hose`
1930s rubber-hose (bouncy vintage gags)

| | |
|---|---|
| Outline | 7 px at 1080 in `#141010` |
| Palette | `#F3E6C8` `#141010` `#C8452F` `#E9B949` `#8A7F6A` |
| Motion feel | hold `twos`, squash 0.14, boil 1.4 px |
| Finish | paper 0.25, grain 6.0 |
| Night grade | `sepia` |
| Best for | bouncy vintage gags, music-synced loops, slapstick |
| Prompt tips | Noodle limbs bend well with `warp.Puppet`; pie-cut eyes and gloves are generic period traits, never a known character. |

### `anime_cel`
Anime cel (emotional, cinematic)

| | |
|---|---|
| Outline | 3 px at 1080 in `#2A2230` |
| Palette | `#FCE4D6` `#6C8EBF` `#F2A6A0` `#2A2230` `#FFF6E0` `#9BC4A8` |
| Motion feel | hold `twos`, squash 0.03, boil 0.0 px |
| Finish | paper 0.0, grain 2.0 |
| Night grade | `blue` |
| Best for | emotional beats, cinematic establishing shots, quiet drama |
| Prompt tips | Few, well-drawn poses; long holds; painted backgrounds carry mood. Squash is tiny (0.03): acting comes from eyes and holds. |

### `chibi_sticker`
Chibi sticker (cute mascots, reactions)

| | |
|---|---|
| Outline | 6 px at 1080 in `#3A2E3F` |
| Palette | `#FFD6E0` `#FFF1B8` `#B8F2E6` `#A0C4FF` `#3A2E3F` `#FFFFFF` |
| Motion feel | hold `twos`, squash 0.12, boil 0.6 px |
| Finish | paper 0.0, grain 0.0 |
| Night grade | `violet` |
| Best for | cute mascots, reaction shorts, sticker-pack style intros |
| Prompt tips | Head about half the body height; thick white sticker border survives keying, so check `green_fringe` on it. |

### `crayon_kids`
Crayon / kid drawing (storybook, nostalgia)

| | |
|---|---|
| Outline | 5 px at 1080 in `#22252B` |
| Palette | `#FFFFFF` `#E63946` `#1D70B8` `#FFC43D` `#3BB273` `#22252B` |
| Motion feel | hold `twos`, squash 0.08, boil 2.0 px |
| Finish | paper 0.5, grain 4.0 |
| Night grade | `blue` |
| Best for | storybook tales, nostalgia, kids' learning |
| Prompt tips | Embrace wobble: boil 2.0 on twos. Paper texture comes from the finish; ask for white-paper ground on the set only. |

### `paper_cutout`
Paper cut-out (craft, explainers with charm)

| | |
|---|---|
| Outline | none (ink `#3B2F2F` for small details) |
| Palette | `#F4E9D8` `#E07A5F` `#3D405B` `#81B29A` `#F2CC8F` |
| Motion feel | hold `twos`, squash 0.05, boil 0.3 px |
| Finish | paper 0.6, grain 3.0 |
| Night grade | `blue` |
| Best for | crafty explainers, layered sets, side-scrollers |
| Prompt tips | Every layer is a separate cut with its own tiny drop shadow; parts hinge at joints; parallax layers are natural here. |

### `watercolor_storybook`
Watercolour storybook (soft, warm narration)

| | |
|---|---|
| Outline | 2 px at 1080 in `#3A3430` |
| Palette | `#F6EEDF` `#E9A178` `#7FA7C9` `#A7C48D` `#3A3430` |
| Motion feel | hold `twos`, squash 0.03, boil 0.4 px |
| Finish | paper 0.7, grain 3.0 |
| Night grade | `blue` |
| Best for | soft narrated stories, bedtime tales, warm memories |
| Prompt tips | Loose ink line + washes; keep motion gentle (slow push, sway). palette_match runs lower on washes: judge by eye too. |

### `desi_gouache`
Desi gouache (Indian homes, streets, festivals)

| | |
|---|---|
| Outline | 3 px at 1080 in `#2E2333` |
| Palette | `#F3D9A4` `#E8833A` `#2F4B8A` `#B83B5E` `#7A9E7E` `#2E2333` |
| Motion feel | hold `twos`, squash 0.05, boil 0.4 px |
| Finish | paper 0.4, grain 3.0 |
| Night grade | `indigo` |
| Best for | Indian homes, streets, festivals, family skits |
| Prompt tips | Matte opaque paint, patterned textiles, flat perspective. Marigold + indigo accents; indigo night grade for power cuts. |

### `dark_cartoon`
Dark cartoon horror (adult, creepy but stylised)

| | |
|---|---|
| Outline | 6 px at 1080 in `#0B0B0F` |
| Palette | `#2B2D3A` `#4C5266` `#B9B7A7` `#0B0B0F` `#9BBF3B` |
| Motion feel | hold `twos`, squash 0.04, boil 1.2 px |
| Finish | paper 0.2, grain 8.0 |
| Night grade | `horror` |
| Best for | adult horror shorts, creepy stories, unsettling loops |
| Prompt tips | Long thin limbs, hollow eyes, flat black shadow shapes, one sickly accent. Scary = long holds, silence, one hard cut in near-dark. |

## Night grades
`GRADES` keys: `day sunset night violet powercut blue indigo sepia horror tv_glow`.
| Grade | Reads as |
|---|---|
| `violet` | pastel room after the lamp clicks off: soft indigo-violet, gently spooky |
| `powercut` | darker violet, low saturation: a real power cut |
| `blue` | cool moonlit night |
| `indigo` | warm-home night, Indian power cut, festival night |
| `sepia` | vintage night, low saturation (rubber hose) |
| `horror` | cold, desaturated, near-mono: adult dread |
| `night`, `sunset`, `tv_glow` | general night, golden hour, a room lit only by a screen |
Emissive things (eyes, lamp pools, phone screens) go on AFTER the grade (`glow_eyes`, `light_pool`), driven by
`Light.level(t, name)`, so they glow instead of being dimmed.

## Add a new style pack
A pack is a plain dict. Keep it in the project (do not edit `cartoon.py` for a one-off video):
```python
import sys; sys.path.insert(0, 'motion2d')
from cartoon import ARTSTYLES
ARTSTYLES['ink_wash_night'] = dict(
    label='Ink wash night (quiet ghost stories)',              # one line: look + best use
    core='2D cartoon, sumi ink wash, dry-brush outlines, grey washes with one warm lantern accent, simple faces',
    outline_px=5, ink='#141414',                              # px at 1080; 0 = no outlines
    palette=['#EDE8DC', '#9A9A92', '#4A4A48', '#141414', '#E8A33D'],   # 4-6 hex, include lights and darks
    boil=0.6, paper=0.5, grain=4.0,                           # line wobble px, paper texture 0-1, grain
    hold='twos', squash=0.04,                                 # timing feel
    night='horror')                                           # any GRADES key
```
All 11 keys are required (`label core outline_px ink palette boil paper grain hold squash night`). Any function
that takes a style also takes the dict itself, so `json.dump` it to `projects/<slug>/style.json` and load it
back. Test it: generate master + set + one prop, check `palette_match >= 0.6`, show a 3-frame style test.
For a new built-in pack, add it to `ARTSTYLES` in `cartoon.py`, this gallery and the CARTOON.md table together.

## Derive a pack from a reference
```bash
python3 scripts/style_ref.py ref.png projects/<slug>/style.json --name cosy_room --k 6
```
`style_from_reference()` reads the LOOK only: k-means palette, outline present or not and its weight and ink,
saturation and value (`pastel` / `bold saturated` / `muted`, `bright` / `dark moody`), flat vs textured fills. It
sets `boil`, `paper`, `night` from those and writes a swatch sheet next to the JSON. Then tune by hand: edit
`core` with words the numbers cannot see (face design, limb style, detail level), set `hold`/`squash` to the
reference's motion, and keep passing the reference image as the FIRST image input on every asset. Never copy the
reference's characters, brand, logo, text or story, and never commit the reference file.

Credit: Swapnil Agrawal (BDS intern)
