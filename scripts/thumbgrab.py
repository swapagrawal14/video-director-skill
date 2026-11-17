"""Clean 3D frame (no overlays) for thumbnails. Usage: python3 scripts/thumbgrab.py <project-dir> <t>  -> <dir>/clean_<t>.png"""
import sys, os, base64
sys.path.insert(0, os.path.dirname(__file__)); from _server import open_page
from playwright.sync_api import sync_playwright
d, t = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    br, pg, srv = open_page(p, d); data = pg.evaluate(f'window.grab3d({t})')
    open(os.path.join(d, f'clean_{t}.png'), 'wb').write(base64.b64decode(data.split(',')[1])); br.close(); srv.shutdown()
print('ok')
