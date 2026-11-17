"""Render frames [start,end) to an mp4 chunk. Usage: python3 scripts/render.py <project-dir> START END out.mp4 [width]"""
import sys, os, base64, subprocess, time, json
sys.path.insert(0, os.path.dirname(__file__)); from _server import open_page
from playwright.sync_api import sync_playwright
d, a, b, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]; W = int(sys.argv[5]) if len(sys.argv) > 5 else 1280
fps = json.load(open(os.path.join(d, 'timing.json')))['fps']
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-vf', 'scale=in_range=full:out_range=tv,format=yuv420p', '-pix_fmt', 'yuv420p', '-color_range', 'tv', out], stdin=subprocess.PIPE)
t0 = time.time()
with sync_playwright() as p:
    br, pg, srv = open_page(p, d, W)
    for f in range(a, b):
        data = pg.evaluate(f'window.grab({f / fps},0.95)'); ff.stdin.write(base64.b64decode(data.split(',')[1]))
        if f % 50 == 0: print(f, round(time.time() - t0), 's', flush=True)
    br.close(); srv.shutdown()
ff.stdin.close(); ff.wait(); print('done', out, round(time.time() - t0), 's')
