"""Finishing pass: colour-grade LUT + optional film grain, vignette, chromatic aberration, letterbox.
Looks: horror | teal_orange | warm | bleach (LUT generated procedurally by make_lut.py, no licence issues) or a path to any .cube.
Usage: python3 scripts/grade.py in.mp4 out.mp4 --look horror [--grain 12] [--vignette 0.5] [--ca 2] [--bars 2.39] [--mix 0.85]
Recipe defaults: horror = --grain 14 --vignette 0.6 --ca 2 ; Product Hero = teal_orange --vignette 0.3 ; Storybook = warm --grain 6"""
import argparse, os, subprocess, sys, tempfile, json
ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('--look', default='teal_orange')
ap.add_argument('--grain', type=int, default=0); ap.add_argument('--vignette', type=float, default=0); ap.add_argument('--ca', type=int, default=0)
ap.add_argument('--bars', type=float, default=0); ap.add_argument('--mix', type=float, default=1.0)
A = ap.parse_args(); here = os.path.dirname(os.path.abspath(__file__))
cube = A.look if A.look.endswith('.cube') else os.path.join(tempfile.gettempdir(), f'{A.look}.cube')
if not os.path.exists(cube): subprocess.run([sys.executable, os.path.join(here, 'make_lut.py'), cube, A.look], check=True)
v = [f"split[a][b];[b]lut3d='{cube}'[g];[a][g]blend=all_mode=normal:all_opacity={A.mix}" if A.mix < 1 else f"lut3d='{cube}'"]
if A.ca: v.append(f"rgbashift=rh=-{A.ca}:bh={A.ca}")
if A.vignette: v.append(f"vignette=angle={0.3 + 0.5 * A.vignette:.2f}")
if A.grain: v.append(f"noise=c0s={A.grain}:c0f=t+u")
if A.bars:
    v.append(f"drawbox=x=0:y=0:w=iw:h=(ih-iw/{A.bars})/2:color=black:t=fill,drawbox=x=0:y=ih-(ih-iw/{A.bars})/2:w=iw:h=(ih-iw/{A.bars})/2:color=black:t=fill")
vf = 'scale=out_range=tv,' + ','.join(v) + ',format=yuv420p'
import shutil, tempfile
TMP = os.path.join(tempfile.gettempdir(), 'grade_' + os.path.basename(A.dst))
fps = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', A.src], capture_output=True, text=True).stdout.strip().strip(',')
g = max(1, round(eval(fps) / 2)) if fps else 12
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', A.src, '-filter_complex', vf, '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-g', str(g),
                '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-c:a', 'copy', '-movflags', '+faststart', TMP], check=True)
shutil.move(TMP, A.dst)  # write in /tmp first: faststart fails on some network filesystems
print('graded ->', A.dst)
