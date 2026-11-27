import numpy as np
from PIL import Image, ImageFilter
import sys
for n in sys.argv[1:]:
    im=np.asarray(Image.open(f'img/{n}.png').convert('RGB')).astype(np.float32)
    # bg reference: per-row median of left+right 30px columns (handles vertical gradient)
    edge=np.concatenate([im[:,:30],im[:,-30:]],1)
    ref=np.median(edge,1)[:,None,:]
    d=np.sqrt(((im-ref)**2).sum(2))
    a=np.clip((d-18)/22,0,1)
    A=Image.fromarray((a*255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
    out=Image.open(f'img/{n}.png').convert('RGBA'); out.putalpha(A); out.save(f'img/{n}_cut.png')
    # preview on magenta
    bg=Image.new('RGBA',out.size,(255,0,255,255)); bg.alpha_composite(out); bg.convert('RGB').resize((256,459)).save(f'/tmp/prev_{n}.jpg')
