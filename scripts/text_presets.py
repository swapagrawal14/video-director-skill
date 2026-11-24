"""Canonical names of the text / caption presets (docs/TEXT_STYLES.md). One source of truth for
scripts/captions.py, scripts/lint.py, template/index.html (title_motion / step_style) and motion2d/textfx.py.
Every video picks its own pair (look.title_motion + look.captions_preset); the examples' pairs are listed in
EXAMPLE_LOOKS so lint.py can flag a clone."""
import re

# burned captions (scripts/captions.py --preset NAME). name -> one-line description
CAPTION_PRESETS = {
    'pop-word':           'active word pops (scale bounce) in the accent colour, others in the light colour; Baloo 2',
    'karaoke-sweep':      'left-to-right colour sweep through each line (\\kf); Fredoka',
    'lower-third-ticker': 'left-aligned strip in a solid box at the lower third, letters tick in from wide tracking',
    'marker-highlight':   'dark ink on a fat highlighter swipe that grows behind the active word',
    'outline-bold':       'heavy-outline caps, no box, whole line punches in; Fredoka',
    'typewriter-reveal':  'mono type revealed letter by letter, left-aligned, with a cursor',
    'stacked-bounce':     'one word per row, stacked; each word bounces in, alternating accent colours',
    'minimal-serif':      'small sentence-case serif, soft shadow, slow fades; no box, no outline',
    'chalk-hand':         'Caveat handwriting in chalk colour, slight tilt and dust blur, words written on one by one',
    'pill':               'white text in a dark rounded pill (the template / braces-tutorial default look)',
}
LEGACY_STYLES = ('pop', 'karaoke')   # captions.py --style pop|karaoke: the original yellow/white Baloo look, unchanged
CAPTION_POSITIONS = ('bottom', 'center', 'top', 'lower-third')

# title / label motion (template/index.html look.title_motion, motion2d/textfx.py)
TITLE_MOTIONS = {
    'card-rise':     'cream card rises with back overshoot (template default; used by braces example)',
    'slam-squash':   'type slams in from 2x scale and squashes on landing',
    'typewriter':    'letters typed one by one with a blinking cursor',
    'mask-wipe':     'an accent bar sweeps across and leaves the text behind it',
    'letter-bounce': 'each letter drops in and bounces, staggered',
    'slide-stack':   'lines slide in from alternating sides and stack',
    'marker-sweep':  'a highlighter swipe draws behind the text left to right',
    'draw-on':       'outline strokes reveal left to right (raster clip), then the fill floods in; never SVG',
    'slow-fade':     'long fade with tracking closing in (horror, documentary)',
    'none':          'no on-screen titles at all (pure character / story pieces)',
}
STEP_STYLES = ('chip', 'counter-dial', 'tape-strip', 'none')

# what the shipped examples use. braces-tutorial has no project.json: its titles are card-rise and its captions the
# dark pill (and the pop-word burn), so either caption preset with card-rise counts as a clone of it.
EXAMPLE_LOOKS = {
    'braces-tutorial': {'title_motion': 'card-rise', 'captions_preset': ['pop-word', 'pill']},
}


def norm(name):
    return re.sub(r'[\s_]+', '-', str(name or '').strip().lower())
