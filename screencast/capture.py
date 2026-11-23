"""Screen-capture front end for the screencast engine.

capture(steps, out_dir) drives headless Chromium (Playwright sync API) and writes a
PNG frame sequence at a fixed fps on a *virtual* clock: every saved frame advances
time by 1/fps, so output is smooth regardless of how slow screenshots are.

load_recording(mp4, out_dir) turns an existing screen recording into the same
frame-sequence dict via ffmpeg (pass device="mobile" + marks/touches for a phone recording).

Mobile mode: capture(..., device="mobile") emulates a phone (default Pixel 7; also "iPhone 14", or any
Playwright device name via device_name): viewport, DPR, touch, mobile UA. Touch steps `tap`, `swipe`,
`long_press` are only valid in mobile mode. Frames are saved at min(device DPR, max_dpr) and every box /
point in the result is in frame pixels (result["dpr"] says the factor from CSS px).

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

STEP_KEYS = ("goto", "wait", "scroll_to", "scroll", "click", "type", "hover", "press", "mark",
             "tap", "swipe", "long_press")
TOUCH_KEYS = ("tap", "swipe", "long_press")
SWIPE_DIRS = ("up", "down", "left", "right")
SWIPE_SECONDS = 0.45          # finger travel time of a swipe (default)
LONG_PRESS_SECONDS = 0.8      # default hold of a long press
TAP_LEAD_SECONDS = 0.35       # hold on the target before tapping (finger travels in)

# Fallback device table (used when Playwright's own registry lacks the name). CSS viewport + DPR + UA.
DEVICES = {
    "Pixel 7": {"viewport": {"width": 412, "height": 839}, "device_scale_factor": 2.625,
                "is_mobile": True, "has_touch": True,
                "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Mobile Safari/537.36"},
    "iPhone 14": {"viewport": {"width": 390, "height": 664}, "device_scale_factor": 3,
                  "is_mobile": True, "has_touch": True,
                  "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
                                "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"},
}
DEFAULT_DEVICE = "Pixel 7"
SCROLL_SECONDS = 0.6
NAV_TIMEOUT_MS = 30000
SELECTOR_TIMEOUT_MS = 5000
TYPE_FRAMES_PER_CHAR = 2
HOVER_SECONDS = 0.4
CLICK_LEAD_SECONDS = 0.3      # hold on the target before clicking
POST_ACTION_SECONDS = 0.3     # settle frames after click / goto


# ---------------------------------------------------------------- pure helpers
def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _target(v):
    """A touch target: selector string or [x, y] CSS-px point. Returns it normalised or None."""
    if isinstance(v, str) and v:
        return v
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(_is_num(c) and c >= 0 for c in v):
        return (float(v[0]), float(v[1]))
    return None


def _validate_touch(i, k, v):
    if k == "tap":
        tg = _target(v)
        if tg is None:
            raise ValueError(f"step {i}: tap needs a selector string or an [x, y] point")
        return tg
    if k == "long_press":
        if isinstance(v, dict):
            extra = set(v) - {"target", "seconds"}
            if extra or "target" not in v:
                raise ValueError(f"step {i}: long_press dict takes 'target' and optional 'seconds'")
            tg, sec = _target(v["target"]), v.get("seconds", LONG_PRESS_SECONDS)
        else:
            tg, sec = _target(v), LONG_PRESS_SECONDS
        if tg is None:
            raise ValueError(f"step {i}: long_press needs a selector string, an [x, y] point or {{target, seconds}}")
        if not _is_num(sec) or not 0.2 <= sec <= 10:
            raise ValueError(f"step {i}: long_press seconds must be 0.2..10")
        return {"target": tg, "seconds": float(sec)}
    # swipe: "up" | {"dir": "up", "px": 400, "from": sel|[x,y], "seconds": .45}
    if isinstance(v, str):
        v = {"dir": v}
    if not isinstance(v, dict):
        raise ValueError(f"step {i}: swipe needs a direction string or {{dir, px?, from?, seconds?}}")
    extra = set(v) - {"dir", "px", "from", "seconds"}
    if extra:
        raise ValueError(f"step {i}: swipe has unknown keys {sorted(extra)}")
    d = v.get("dir")
    if d not in SWIPE_DIRS:
        raise ValueError(f"step {i}: swipe dir must be one of {', '.join(SWIPE_DIRS)}")
    px = v.get("px", 400)
    if not _is_num(px) or px <= 0:
        raise ValueError(f"step {i}: swipe px must be a positive number")
    sec = v.get("seconds", SWIPE_SECONDS)
    if not _is_num(sec) or not 0.1 <= sec <= 5:
        raise ValueError(f"step {i}: swipe seconds must be 0.1..5")
    frm = None
    if "from" in v:
        frm = _target(v["from"])
        if frm is None:
            raise ValueError(f"step {i}: swipe from needs a selector string or an [x, y] point")
    return {"dir": d, "px": float(px), "from": frm, "seconds": float(sec)}


def validate_steps(steps, mobile=False):
    """Return a normalised list of (kind, value) tuples; raise ValueError on bad input.
    Touch steps (tap, swipe, long_press) need mobile=True (script "device": "mobile")."""
    if not isinstance(steps, (list, tuple)):
        raise ValueError("steps must be a list of dicts")
    out = []
    for i, st in enumerate(steps):
        if not isinstance(st, dict) or len(st) != 1:
            raise ValueError(f"step {i}: must be a dict with exactly one key, got {st!r}")
        (k, v), = st.items()
        if k not in STEP_KEYS:
            raise ValueError(f"step {i}: unknown action {k!r} (allowed: {', '.join(STEP_KEYS)})")
        if k in TOUCH_KEYS:
            if not mobile:
                raise ValueError(f"step {i}: {k} is a touch step; set \"device\": \"mobile\" to use it")
            out.append((k, _validate_touch(i, k, v)))
            continue
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


def swipe_path(start, direction, px, viewport, margin=12):
    """Finger start/end points (CSS px) for a swipe. 'up' moves the finger up (content scrolls down).
    The end point is clamped inside the viewport."""
    w, h = viewport
    x0, y0 = start
    dx, dy = {"up": (0, -px), "down": (0, px), "left": (-px, 0), "right": (px, 0)}[direction]
    x1 = min(max(margin, x0 + dx), w - margin)
    y1 = min(max(margin, y0 + dy), h - margin)
    return (float(x0), float(y0)), (float(x1), float(y1))


def swipe_default_start(direction, viewport):
    """Where a thumb naturally starts a swipe when no 'from' is given."""
    w, h = viewport
    return {"up": (w * .5, h * .72), "down": (w * .5, h * .3),
            "left": (w * .8, h * .5), "right": (w * .2, h * .5)}[direction]


def point_box(pt, size=24):
    """[x, y, w, h] box centred on a point (for events that target a coordinate)."""
    return [int(round(pt[0] - size / 2)), int(round(pt[1] - size / 2)), size, size]


def device_profile(name=None, max_dpr=2.0, registry=None):
    """Playwright new_context kwargs for a phone. Uses Playwright's registry when given (p.devices),
    else the fallback DEVICES table. DPR is capped at max_dpr (frame size vs. render cost)."""
    name = name or DEFAULT_DEVICE
    src = (registry or {}).get(name) or DEVICES.get(name)
    if not src:
        raise ValueError(f"unknown device {name!r} (known: {', '.join(DEVICES)})")
    prof = {k: v for k, v in dict(src).items() if k != "default_browser_type"}
    prof["is_mobile"] = True
    prof["has_touch"] = True
    prof["device_scale_factor"] = float(min(float(prof.get("device_scale_factor", 2)), float(max_dpr)))
    if "screen" in prof:
        prof.pop("screen")
    return prof


def scale_geometry(result, k):
    """Multiply every box / point in a capture result (boxes, events) by k (CSS px -> frame px)."""
    if k == 1:
        return result
    sc = lambda v: [int(round(c * k)) for c in v]
    result["boxes"] = {s: sc(b) for s, b in result["boxes"].items() if b}
    for e in result["events"]:
        for key in ("box", "from", "to", "point"):
            if e.get(key):
                e[key] = sc(e[key])
    return result


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


def _resolve_point(page, tg):
    """Touch target -> (CSS point, box) or (None, None). Selector -> centre of its box."""
    if isinstance(tg, str):
        b = _box(page, tg)
        if b is None:
            return None, None
        return (b[0] + b[2] / 2, b[1] + b[3] / 2), b
    return tg, point_box(tg)


def _settle(page):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT_MS)
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass


def capture(steps, out_dir, viewport=(720, 1280), fps=30, css=None, device=None, device_name=None, max_dpr=2.0):
    """css: optional stylesheet injected on every page (hide cookie/donation banners).
    device: None (desktop, `viewport` used) or "mobile" (phone emulation; `viewport` ignored,
    device_name picks the phone, default Pixel 7)."""
    if device not in (None, "desktop", "mobile"):
        raise ValueError(f"device must be 'mobile' or omitted, got {device!r}")
    mobile = device == "mobile"
    plan = validate_steps(steps, mobile=mobile)
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
        dpr = 1.0
        try:
            if mobile:
                try:
                    registry = p.devices
                except Exception:
                    registry = None
                prof = device_profile(device_name, max_dpr, registry)
                w, h = int(prof["viewport"]["width"]), int(prof["viewport"]["height"])
                dpr = prof["device_scale_factor"]
                ctx = browser.new_context(**prof, ignore_https_errors=bool(px))
            else:
                ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                          ignore_https_errors=bool(px))
            if css:
                ctx.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement('style');s.textContent=%s;document.head.appendChild(s);});" % __import__('json').dumps(css))
            page = ctx.new_page()
            page.set_default_timeout(NAV_TIMEOUT_MS)
            rec = _Recorder(page, frames_dir, fps)
            cdp = ctx.new_cdp_session(page) if mobile else None

            def touch(kind_, pt=None):
                pts = [{"x": float(pt[0]), "y": float(pt[1]), "radiusX": 6, "radiusY": 6, "force": 1}] if pt else []
                cdp.send("Input.dispatchTouchEvent", {"type": kind_, "touchPoints": pts})

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

                elif kind == "tap":
                    pt, b = _resolve_point(page, val)
                    if pt is None:
                        continue
                    if isinstance(val, str):
                        boxes[val] = b
                    rec.shot()                      # target before the tap (finger travels in)
                    rec.hold(frames_for(TAP_LEAD_SECONDS, fps) - 1)
                    events.append(make_event(rec.t, "tap", val if isinstance(val, str) else None, b,
                                             point=[pt[0], pt[1]]))
                    try:
                        if isinstance(val, str):
                            page.locator(val).first.tap(timeout=SELECTOR_TIMEOUT_MS)
                        else:
                            page.touchscreen.tap(pt[0], pt[1])
                        _settle(page)
                    except Exception as e:
                        warnings.warn(f"tap {val!r} failed: {e}")
                    for _ in range(max(1, frames_for(POST_ACTION_SECONDS, fps))):
                        rec.shot()

                elif kind == "long_press":
                    tg, sec = val["target"], val["seconds"]
                    pt, b = _resolve_point(page, tg)
                    if pt is None:
                        continue
                    if isinstance(tg, str):
                        boxes[tg] = b
                    rec.shot()
                    rec.hold(frames_for(TAP_LEAD_SECONDS, fps) - 1)
                    events.append(make_event(rec.t, "long_press", tg if isinstance(tg, str) else None, b,
                                             point=[pt[0], pt[1]], dur=sec))
                    try:
                        touch("touchStart", pt)
                        for _ in range(max(1, frames_for(sec, fps))):
                            rec.shot()               # live frames: the page may react (context menu)
                        touch("touchEnd")
                    except Exception as e:
                        warnings.warn(f"long_press {tg!r} failed: {e}")
                    for _ in range(max(1, frames_for(POST_ACTION_SECONDS, fps))):
                        rec.shot()

                elif kind == "swipe":
                    frm = val["from"]
                    if frm is None:
                        start, b = swipe_default_start(val["dir"], (w, h)), None
                    else:
                        start, b = _resolve_point(page, frm)
                        if start is None:
                            continue
                    p0, p1 = swipe_path(start, val["dir"], val["px"], (w, h))
                    n = max(2, frames_for(val["seconds"], fps))
                    y_before = page.evaluate("() => [window.scrollX, window.scrollY]")
                    events.append(make_event(rec.t, "swipe", frm if isinstance(frm, str) else None,
                                             point_box(p0), dir=val["dir"], px=val["px"],
                                             dur=round(n / float(fps), 4),
                                             **{"from": [p0[0], p0[1]], "to": [p1[0], p1[1]]}))
                    try:
                        touch("touchStart", p0)
                        for j in range(1, n + 1):
                            u = ease_in_out(j / n)
                            touch("touchMove", (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u))
                            rec.shot()
                        touch("touchEnd")
                    except Exception as e:
                        warnings.warn(f"swipe failed: {e}")
                    for _ in range(max(1, frames_for(POST_ACTION_SECONDS, fps))):
                        rec.shot()               # momentum settles on camera
                    # some pages swallow synthetic touch scrolling: fall back to a scroll of the same size
                    y_after = page.evaluate("() => [window.scrollX, window.scrollY]")
                    if val["dir"] in ("up", "down") and frm is None and abs(y_after[1] - y_before[1]) < 0.2 * val["px"]:
                        warnings.warn("swipe did not scroll the page; falling back to scrollBy")
                        _smooth_scroll(page, rec, (p0[1] - p1[1]) - (y_after[1] - y_before[1]))

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

    res = {"frames_dir": frames_dir, "fps": fps, "n_frames": n,
           "boxes": boxes, "events": events}
    if mobile:
        res.update(device="mobile", device_name=device_name or DEFAULT_DEVICE, dpr=dpr, viewport_css=[w, h])
        scale_geometry(res, dpr)
    return res


# ---------------------------------------------------------------- existing recording
def recording_touches(touches, scale=1.0):
    """Validate hand-written touch events for a phone recording (times in s, points in source video px)
    and turn them into capture events (points multiplied by `scale`).
      {"t": 1.2, "tap": [x, y]} | {"t": 2.0, "long_press": [x, y], "seconds": .8}
      {"t": 3.1, "swipe": [[x0, y0], [x1, y1]], "seconds": .45}"""
    out = []
    for i, tc in enumerate(touches or []):
        if not isinstance(tc, dict) or not _is_num(tc.get("t")) or tc["t"] < 0:
            raise ValueError(f"touch {i}: needs a time 't' >= 0")
        kinds = [k for k in TOUCH_KEYS if k in tc]
        if len(kinds) != 1:
            raise ValueError(f"touch {i}: needs exactly one of {', '.join(TOUCH_KEYS)}")
        k = kinds[0]; v = tc[k]; sc = lambda q: [q[0] * scale, q[1] * scale]
        if k == "swipe":
            if (not isinstance(v, (list, tuple)) or len(v) != 2 or any(_target(q) is None or isinstance(q, str) for q in v)):
                raise ValueError(f"touch {i}: swipe needs [[x0, y0], [x1, y1]]")
            p0, p1 = sc(v[0]), sc(v[1]); sec = tc.get("seconds", SWIPE_SECONDS)
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            d = ("left" if dx < 0 else "right") if abs(dx) > abs(dy) else ("up" if dy < 0 else "down")
            out.append(make_event(tc["t"], "swipe", None, point_box(p0), dir=d, px=round(math.hypot(dx, dy), 1),
                                  dur=float(sec), **{"from": p0, "to": p1}))
        else:
            if _target(v) is None or isinstance(v, str):
                raise ValueError(f"touch {i}: {k} needs an [x, y] point")
            pt = sc(v); extra = {"dur": float(tc.get("seconds", LONG_PRESS_SECONDS))} if k == "long_press" else {}
            out.append(make_event(tc["t"], k, None, point_box(pt, 60 * scale), point=pt, **extra))
    out.sort(key=lambda e: e["t"])
    for e in out:
        for key in ("box", "from", "to", "point"):
            if e.get(key):
                e[key] = [int(round(c)) for c in e[key]]
    return out


def _probe_size(mp4):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height", "-of", "csv=p=0:s=x", mp4], capture_output=True, text=True, timeout=60)
    try:
        w, h = r.stdout.strip().split("x")[:2]
        return int(w), int(h)
    except Exception:
        return None


def load_recording(mp4, out_dir, fps=30, device=None, marks=None, touches=None, max_height=1600):
    """Existing screen recording -> frame sequence. For a phone recording pass device="mobile",
    `marks` (beat boundaries in seconds, len(beats)-1 of them) and optional `touches` (see
    recording_touches) so compose can draw the finger. Tall videos are downscaled to max_height."""
    if not os.path.isfile(mp4):
        raise FileNotFoundError(mp4)
    if device not in (None, "desktop", "mobile"):
        raise ValueError(f"device must be 'mobile' or omitted, got {device!r}")
    marks = list(marks or [])
    if any(not _is_num(m) or m < 0 for m in marks) or marks != sorted(marks):
        raise ValueError("marks must be increasing times in seconds")
    os.makedirs(out_dir, exist_ok=True)
    frames_dir = _prepare_dir(out_dir)
    size = _probe_size(mp4); scale = 1.0
    vf = f"fps={fps}"
    if size and max_height and size[1] > max_height:
        scale = max_height / float(size[1])
        vf += f",scale=-2:{int(max_height)}:flags=lanczos"
    events = [make_event(m, "mark", name=f"m{i + 1}", frame=frames_for(m, fps)) for i, m in enumerate(marks)]
    events += recording_touches(touches, scale)   # validate before the (slow) decode
    events.sort(key=lambda e: e["t"])
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", vf,
           "-start_number", "0", os.path.join(frames_dir, "%05d.png")]
    subprocess.run(cmd, check=True, timeout=600)
    n = len([f for f in os.listdir(frames_dir) if f.endswith(".png")])
    res = {"frames_dir": frames_dir, "fps": fps, "n_frames": n, "boxes": {}, "events": events}
    if device == "mobile":
        res.update(device="mobile", device_name="recording", dpr=1.0)
    return res
