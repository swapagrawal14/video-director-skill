"""Screen-capture front end for the screencast engine.

capture(steps, out_dir) drives headless Chromium (Playwright sync API) and writes a
PNG frame sequence at a fixed fps on a *virtual* clock: every saved frame advances
time by 1/fps, so output is smooth regardless of how slow screenshots are.

load_recording(mp4, out_dir) turns an existing screen recording into the same
frame-sequence dict via ffmpeg.

Returned dict:
  {"frames_dir", "fps", "n_frames",
   "boxes":  {selector: [x, y, w, h]}   # viewport px at the moment it was used
   "events": [{"t", "type", "selector", "box", ...}]}
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import warnings

STEP_KEYS = ("goto", "wait", "scroll_to", "scroll", "click", "type", "hover", "press", "mark")
SCROLL_SECONDS = 0.6
NAV_TIMEOUT_MS = 30000
SELECTOR_TIMEOUT_MS = 5000
TYPE_FRAMES_PER_CHAR = 2
HOVER_SECONDS = 0.4
CLICK_LEAD_SECONDS = 0.3      # hold on the target before clicking
POST_ACTION_SECONDS = 0.3     # settle frames after click / goto


# ---------------------------------------------------------------- pure helpers
def validate_steps(steps):
    """Return a normalised list of (kind, value) tuples; raise ValueError on bad input."""
    if not isinstance(steps, (list, tuple)):
        raise ValueError("steps must be a list of dicts")
    out = []
    for i, st in enumerate(steps):
        if not isinstance(st, dict) or len(st) != 1:
            raise ValueError(f"step {i}: must be a dict with exactly one key, got {st!r}")
        (k, v), = st.items()
        if k not in STEP_KEYS:
            raise ValueError(f"step {i}: unknown action {k!r} (allowed: {', '.join(STEP_KEYS)})")
        if k == "goto":
            if not isinstance(v, str) or not v:
                raise ValueError(f"step {i}: goto needs a url string")
        elif k == "wait":
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
                raise ValueError(f"step {i}: wait needs seconds >= 0")
        elif k == "scroll":
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError(f"step {i}: scroll needs a pixel number")
        elif k == "press":
            if not isinstance(v, str) or not v:
                raise ValueError(f"step {i}: press needs a key name (e.g. Enter)")
        elif k == "mark":
            if not isinstance(v, str) or not v:
                raise ValueError(f"step {i}: mark needs a name")
        elif k == "type":
            if (not isinstance(v, (list, tuple)) or len(v) != 2
                    or not all(isinstance(x, str) for x in v) or not v[0]):
                raise ValueError(f"step {i}: type needs [selector, text]")
            v = (v[0], v[1])
        else:  # selector actions
            if not isinstance(v, str) or not v:
                raise ValueError(f"step {i}: {k} needs a selector string")
        out.append((k, v))
    return out


def frames_for(seconds, fps):
    """Number of frames covering `seconds` at `fps` (>=0, rounded)."""
    return max(0, int(round(float(seconds) * fps)))


def frame_time(index, fps):
    """Timestamp (s) of frame `index` (0-based) on the virtual clock."""
    return round(index / float(fps), 4)


def ease_in_out(x):
    """Cosine ease 0..1 -> 0..1."""
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def scroll_increments(total_px, n_frames):
    """Integer per-frame scrollBy deltas following an ease-in-out curve; they sum to total_px."""
    total_px = int(round(total_px))
    n = max(1, int(n_frames))
    pos = [int(round(total_px * ease_in_out((i + 1) / n))) for i in range(n)]
    prev, incs = 0, []
    for p in pos:
        incs.append(p - prev)
        prev = p
    return incs


def box_to_list(box):
    """Playwright bounding_box dict -> [x, y, w, h] ints, or None."""
    if not box:
        return None
    return [int(round(box["x"])), int(round(box["y"])),
            int(round(box["width"])), int(round(box["height"]))]


def scroll_to_delta(box, viewport_h, anchor=0.3):
    """px to scroll so the element's top lands at `anchor` * viewport height."""
    if not box:
        return 0
    return int(round(box[1] - anchor * viewport_h))


def make_event(t, type_, selector=None, box=None, **extra):
    ev = {"t": round(float(t), 4), "type": type_, "selector": selector, "box": box}
    ev.update(extra)
    return ev


def proxy_from_env(env=None):
    """Playwright proxy dict from HTTPS_PROXY/HTTP_PROXY (Chromium ignores env proxies)."""
    from urllib.parse import urlsplit, unquote
    env = os.environ if env is None else env
    raw = next((env.get(k) for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")
                if env.get(k)), None)
    if not raw:
        return None
    u = urlsplit(raw if "://" in raw else "http://" + raw)
    if not u.hostname:
        return None
    out = {"server": f"{u.scheme}://{u.hostname}" + (f":{u.port}" if u.port else "")}
    if u.username:
        out["username"] = unquote(u.username)
        out["password"] = unquote(u.password or "")
    no = env.get("NO_PROXY") or env.get("no_proxy")
    if no:
        out["bypass"] = no
    return out


def _prepare_dir(out_dir):
    frames_dir = os.path.join(out_dir, "frames")
    if os.path.isdir(frames_dir):
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir, exist_ok=True)
    return frames_dir


# ---------------------------------------------------------------- browser capture
class _Recorder:
    def __init__(self, page, frames_dir, fps):
        self.page, self.dir, self.fps, self.n = page, frames_dir, fps, 0

    @property
    def t(self):
        return frame_time(self.n, self.fps)

    def _path(self, i):
        return os.path.join(self.dir, f"{i:05d}.png")

    def shot(self):
        try:
            self.page.screenshot(path=self._path(self.n), timeout=15000)
        except Exception as e:  # keep the timeline intact
            if self.n == 0:
                raise
            warnings.warn(f"screenshot failed ({e}); repeating previous frame")
            shutil.copyfile(self._path(self.n - 1), self._path(self.n))
        self.n += 1

    def hold(self, frames):
        for _ in range(frames):
            if self.n == 0:
                self.shot()
            else:
                shutil.copyfile(self._path(self.n - 1), self._path(self.n))
                self.n += 1


def _box(page, selector):
    try:
        loc = page.locator(selector).first
        loc.wait_for(state="visible", timeout=SELECTOR_TIMEOUT_MS)
        return box_to_list(loc.bounding_box(timeout=SELECTOR_TIMEOUT_MS))
    except Exception as e:
        warnings.warn(f"selector {selector!r} not found/visible ({type(e).__name__}); skipping step")
        return None


# behavior:'instant' overrides sites (e.g. GitHub) that set CSS scroll-behavior:smooth,
# which never advances in headless screenshot loops.
_SCROLL_JS = "d => window.scrollBy({top: d, left: 0, behavior: 'instant'})"


def _smooth_scroll(page, rec, px):
    for d in scroll_increments(px, frames_for(SCROLL_SECONDS, rec.fps)):
        if d:
            page.evaluate(_SCROLL_JS, d)
        rec.shot()


def capture(steps, out_dir, viewport=(720, 1280), fps=30):
    plan = validate_steps(steps)
    if fps <= 0:
        raise ValueError("fps must be > 0")
    from playwright.sync_api import sync_playwright

    os.makedirs(out_dir, exist_ok=True)
    frames_dir = _prepare_dir(out_dir)
    w, h = int(viewport[0]), int(viewport[1])
    boxes, events = {}, []

    with sync_playwright() as p:
        launch = {"headless": True}
        px = proxy_from_env()
        if px:
            launch["proxy"] = px
        browser = p.chromium.launch(**launch)
        try:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                      ignore_https_errors=bool(px))
            page = ctx.new_page()
            page.set_default_timeout(NAV_TIMEOUT_MS)
            rec = _Recorder(page, frames_dir, fps)

            for kind, val in plan:
                if kind == "goto":
                    try:
                        page.goto(val, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                        try:
                            page.wait_for_load_state("networkidle", timeout=8000)
                        except Exception:
                            pass
                    except Exception as e:
                        warnings.warn(f"goto {val!r} failed: {e}")
                    events.append(make_event(rec.t, "goto", url=val))
                    rec.shot()
                    rec.hold(frames_for(POST_ACTION_SECONDS, fps) - 1)

                elif kind == "wait":
                    events.append(make_event(rec.t, "wait", seconds=val))
                    if rec.n == 0:
                        rec.shot()
                        rec.hold(frames_for(val, fps) - 1)
                    else:
                        rec.hold(frames_for(val, fps))

                elif kind == "scroll":
                    events.append(make_event(rec.t, "scroll", px=val))
                    _smooth_scroll(page, rec, val)

                elif kind == "scroll_to":
                    b = _box(page, val)
                    if b is None:
                        continue
                    t0 = rec.t
                    _smooth_scroll(page, rec, scroll_to_delta(b, h))
                    b = _box(page, val) or b
                    boxes[val] = b
                    events.append(make_event(t0, "scroll_to", val, b))

                elif kind == "hover":
                    b = _box(page, val)
                    if b is None:
                        continue
                    try:
                        page.locator(val).first.hover(timeout=SELECTOR_TIMEOUT_MS)
                    except Exception as e:
                        warnings.warn(f"hover {val!r} failed: {e}")
                    b = _box(page, val) or b
                    boxes[val] = b
                    events.append(make_event(rec.t, "hover", val, b))
                    rec.shot()
                    rec.hold(frames_for(HOVER_SECONDS, fps) - 1)

                elif kind == "click":
                    b = _box(page, val)
                    if b is None:
                        continue
                    boxes[val] = b
                    rec.shot()                      # target before the click
                    rec.hold(frames_for(CLICK_LEAD_SECONDS, fps) - 1)
                    events.append(make_event(rec.t, "click", val, b))
                    try:
                        page.locator(val).first.click(timeout=SELECTOR_TIMEOUT_MS)
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT_MS)
                            page.wait_for_load_state("networkidle", timeout=5000)
                        except Exception:
                            pass
                    except Exception as e:
                        warnings.warn(f"click {val!r} failed: {e}")
                    for _ in range(max(1, frames_for(POST_ACTION_SECONDS, fps))):
                        rec.shot()

                elif kind == "mark":          # zero-length: beat boundary for compose
                    events.append(make_event(rec.t, "mark", name=val, frame=rec.n))

                elif kind == "press":
                    events.append(make_event(rec.t, "press", key=val))
                    try:
                        page.keyboard.press(val)
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT_MS)
                            page.wait_for_load_state("networkidle", timeout=5000)
                        except Exception:
                            pass
                    except Exception as e:
                        warnings.warn(f"press {val!r} failed: {e}")
                    for _ in range(max(1, frames_for(POST_ACTION_SECONDS, fps))):
                        rec.shot()

                elif kind == "type":
                    sel, text = val
                    b = _box(page, sel)
                    if b is None:
                        continue
                    boxes[sel] = b
                    events.append(make_event(rec.t, "type", sel, b, text=text))
                    loc = page.locator(sel).first
                    try:
                        loc.click(timeout=SELECTOR_TIMEOUT_MS)
                        for ch in text:
                            page.keyboard.type(ch)
                            rec.shot()
                            rec.hold(TYPE_FRAMES_PER_CHAR - 1)
                    except Exception as e:
                        warnings.warn(f"type into {sel!r} failed: {e}")
            if rec.n == 0:
                rec.shot()
            n = rec.n
        finally:
            browser.close()

    return {"frames_dir": frames_dir, "fps": fps, "n_frames": n,
            "boxes": boxes, "events": events}


# ---------------------------------------------------------------- existing recording
def load_recording(mp4, out_dir, fps=30):
    if not os.path.isfile(mp4):
        raise FileNotFoundError(mp4)
    os.makedirs(out_dir, exist_ok=True)
    frames_dir = _prepare_dir(out_dir)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", f"fps={fps}",
           "-start_number", "0", os.path.join(frames_dir, "%05d.png")]
    subprocess.run(cmd, check=True, timeout=600)
    n = len([f for f in os.listdir(frames_dir) if f.endswith(".png")])
    return {"frames_dir": frames_dir, "fps": fps, "n_frames": n, "boxes": {}, "events": []}
