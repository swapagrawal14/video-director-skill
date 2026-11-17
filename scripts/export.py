"""Platform exports from one finished 16:9 master.
Presets:  youtube  1920x1080 (or source size) CRF 18, GOP fps/2, BT.709, AAC 384k, faststart
          shorts   1080x1920 9:16 (YouTube Shorts / Reels / TikTok), <=60 s recommended (Shorts accept up to 3 min)
          square   1080x1080 1:1 (LinkedIn / Instagram feed)
          portrait 1080x1350 4:5 (Instagram / LinkedIn feed)
Reframe for vertical/square: --fit blur (default: sharp centre over blurred fill) | crop (centre crop, use --x 0.0-1.0 to pan).
Captions: --ass captions_9x16.ass burns captions made for that size (scripts/captions.py --w 1080 --h 1920).
Clip: --start/--end seconds (cut a Short out of a long tutorial). Usage:
  python3 scripts/export.py master.mp4 shorts out_short.mp4 [--fit crop --x 0.4] [--start 12 --end 58] [--ass c.ass]"""
import argparse, os, subprocess
ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('preset', choices=['youtube', 'shorts', 'square', 'portrait']); ap.add_argument('dst')
ap.add_argument('--fit', default='blur', choices=['blur', 'crop']); ap.add_argument('--x', type=float, default=0.5)
ap.add_argument('--start', type=float); ap.add_argument('--end', type=float); ap.add_argument('--ass')
A = ap.parse_args(); fonts = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts')
size = {'youtube': (1920, 1080), 'shorts': (1080, 1920), 'square': (1080, 1080), 'portrait': (1080, 1350)}[A.preset]; W, H = size
fps = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', A.src], capture_output=True, text=True).stdout.strip().strip(',')
g = max(1, round(eval(fps) / 2))
if A.preset == 'youtube': vf = f'scale={W}:{H}:flags=lanczos'
elif A.fit == 'crop': vf = f"scale=-2:{H}:flags=lanczos,crop={W}:{H}:(iw-{W})*{A.x}:0"
else: vf = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,eq=brightness=-0.08[bg];"
            f"[b]scale={W}:-2:flags=lanczos[fg];[bg][fg]overlay=0:(H-h)/2")
if A.ass: vf += f",ass={A.ass}:fontsdir={fonts}"
vf += ',setsar=1,scale=out_range=tv,format=yuv420p'
cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + (['-ss', str(A.start)] if A.start is not None else []) + (['-to', str(A.end)] if A.end is not None else []) + ['-i', A.src]
cmd += ['-filter_complex', vf, '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-g', str(g), '-bf', '2', '-profile:v', 'high',
        '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-c:a', 'aac', '-b:a', '384k', '-ar', '48000', '-movflags', '+faststart', A.dst]
subprocess.run(cmd, check=True); print(A.preset, f'{W}x{H} ->', A.dst)
