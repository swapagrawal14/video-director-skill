"""Preview stills. Usage: python3 scripts/shot.py <project-dir> <t1> <t2> ...  -> <dir>/shots/tXXXX.jpg (+ contact sheet)"""
import sys, os, base64, time
sys.path.insert(0, os.path.dirname(__file__)); from _server import open_page
from playwright.sync_api import sync_playwright
d = sys.argv[1]; times = [float(x) for x in sys.argv[2:]]; os.makedirs(os.path.join(d, 'shots'), exist_ok=True); files = []
with sync_playwright() as p:
    br, pg, srv = open_page(p, d)
    for t in times:
        t0 = time.time(); data = pg.evaluate(f'window.grab({t})'); f = os.path.join(d, 'shots', f't{t:06.1f}.jpg')
        open(f, 'wb').write(base64.b64decode(data.split(',')[1])); files.append(f); print(t, round(time.time() - t0, 2), 's')
    br.close(); srv.shutdown()
try:
    from PIL import Image, ImageDraw
    cols = 2; ims = [Image.open(f).resize((640, 360)) for f in files]; rows = (len(ims) + 1) // cols
    sheet = Image.new('RGB', (640 * cols, 360 * rows), 'black')
    for k, (im, t) in enumerate(zip(ims, times)):
        sheet.paste(im, ((k % cols) * 640, (k // cols) * 360)); ImageDraw.Draw(sheet).text(((k % cols) * 640 + 8, (k // cols) * 360 + 8), f't={t}', fill='yellow')
    sheet.save(os.path.join(d, 'shots', 'sheet.jpg'), quality=85); print('sheet ->', os.path.join(d, 'shots', 'sheet.jpg'))
except Exception as e: print('sheet skipped', e)
