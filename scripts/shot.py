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
    im0 = Image.open(files[0]); vertical = im0.height > im0.width
    tw, th = (300, 533) if vertical else (640, 360); cols = 5 if vertical else 2   # keeps aspect for 9:16 projects
    ims = [Image.open(f).resize((tw, th)) for f in files]; rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (tw * cols, th * rows), 'black')
    for k, (im, t) in enumerate(zip(ims, times)):
        sheet.paste(im, ((k % cols) * tw, (k // cols) * th)); ImageDraw.Draw(sheet).text(((k % cols) * tw + 8, (k // cols) * th + 8), f't={t}', fill='yellow')
    sheet.save(os.path.join(d, 'shots', 'sheet.jpg'), quality=85); print('sheet ->', os.path.join(d, 'shots', 'sheet.jpg'))
except Exception as e: print('sheet skipped', e)
