import numpy as np
from PIL import Image
def key(path):
    a=np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    r,g,b=a[...,0],a[...,1],a[...,2]
    dom=g-np.maximum(r,b)
    alpha=np.clip(1-(dom-25)/(90-25),0,1)
    # despill
    mx=np.maximum(r,b)
    g2=np.where(g>mx, mx+ (g-mx)*0.15*alpha, g)
    out=np.dstack([r,g2,b,alpha*255]).clip(0,255).astype(np.uint8)
    return out
