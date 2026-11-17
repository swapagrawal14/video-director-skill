"""Chunked, parallel, resumable render + assemble.
Usage: python3 scripts/render_all.py <project-dir> [--jobs 2] [--chunk 200] [--width 1280]
Chunks already complete (right frame count) are skipped, so just re-run after a crash/timeout."""
import sys, os, json, subprocess, argparse, concurrent.futures as cf
ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--jobs', type=int, default=2); ap.add_argument('--chunk', type=int, default=200); ap.add_argument('--width', type=int, default=1280)
A = ap.parse_args(); d = A.dir; T = json.load(open(os.path.join(d, 'timing.json'))); N = T['frames']
cd = os.path.join(d, 'chunks'); os.makedirs(cd, exist_ok=True); here = os.path.dirname(os.path.abspath(__file__))
def frames(f):
    r = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.strip().strip(',')
    return int(r) if r.isdigit() else 0
jobs = [(k, s, min(N, s + A.chunk)) for k, s in enumerate(range(0, N, A.chunk))]
def run(j):
    k, s, e = j; out = os.path.join(cd, f'c{k:03d}.mp4')
    if os.path.exists(out) and frames(out) == e - s: return k, 'skip'
    subprocess.run([sys.executable, os.path.join(here, 'render.py'), d, str(s), str(e), out, str(A.width)], check=True)
    return k, frames(out)
with cf.ThreadPoolExecutor(A.jobs) as ex:
    for r in ex.map(run, jobs): print('chunk', r, flush=True)
lst = os.path.join(cd, 'list.txt'); open(lst, 'w').write(''.join(f"file 'c{k:03d}.mp4'\n" for k, _, _ in jobs))
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', os.path.join(d, 'video_only.mp4')], check=True)
got = frames(os.path.join(d, 'video_only.mp4')); print(f'assembled {got}/{N} frames', 'OK' if abs(got - N) <= 1 else 'MISMATCH: re-run')
