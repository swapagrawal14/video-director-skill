import sys, json, numpy as np
sys.path.insert(0,'/workspace/work/videoskill/examples/painted-duet/cast2/dadaji')
from key import key
from PIL import Image
from scipy import ndimage as ndi
D='/workspace/work/videoskill/examples/painted-duet/cast2/dadaji/'
R=D+'raw/'
POSES=['idle','talk','point','outraged','think','laugh']
YLIM=400            # max erase depth (sheet px)
X0,X1=220,562       # head column range (sheet px)
CROP=(215,60,565,410)  # head crop in sheet px -> head_raw 1024
S=None
def classify(rgb):
    r,g,b=[rgb[...,i].astype(int) for i in range(3)]
    cloth_white=(np.minimum(np.minimum(r,g),b)>160)&((np.maximum(np.maximum(r,g),b)-np.minimum(np.minimum(r,g),b))<35)
    brown=(r>90)&(r<165)&(g>60)&(g<140)&(b>30)&(b<100)&(r-b>45)&(g<r-20)
    return cloth_white|brown
def navy(rgb):
    r,g,b=[rgb[...,i].astype(int) for i in range(3)]
    return (r<90)&(g<90)&(b<120)
idle_rgb=np.asarray(Image.open(R+'idle.png').convert('RGB')).astype(int)
bodies={}; cuts={}
for p in POSES:
    rgb=np.asarray(Image.open(R+p+'.png').convert('RGB'))
    k=key(R+p+'.png')
    cl=classify(rgb); nv=navy(rgb)
    alpha=k[...,3].astype(np.float32)
    cut=np.zeros(rgb.shape[1],int)
    for x in range(X0,X1):
        col=cl[350:,x].astype(int)
        run=np.convolve(col,np.ones(20,int),'valid')
        idx=np.nonzero(run>=18)[0]
        if len(idx)==0: continue
        y=350+idx[0]
        while y>350 and nv[y-1,x]: y-=1
        cut[x]=min(y,YLIM)
    # smooth cut a little (median) to avoid spikes
    cs=cut.copy()
    for x in range(X0+5,X1-5):
        cs[x]=int(np.median(cut[x-5:x+6]))
    keep=np.ones(alpha.shape,bool)
    yy=np.arange(alpha.shape[0])[:,None]
    keep[:, X0:X1] = yy >= cs[None,X0:X1]
    if p=='think':
        d=np.abs(np.asarray(rgb).astype(int)-idle_rgb).sum(2)>70
        reg=np.zeros_like(d); reg[348:YLIM+5,370:530]=True
        hm=d&reg
        hm=ndi.binary_opening(hm,iterations=1)
        hm=ndi.binary_closing(hm,iterations=4)
        hm=ndi.binary_fill_holes(hm)
        lab,n=ndi.label(hm)
        if n:
            sizes=ndi.sum(hm,lab,range(1,n+1)); hm=lab==(1+int(np.argmax(sizes)))
        hm=ndi.binary_dilation(hm,iterations=2)
        keep|=hm
    # soft 1px edge on cut
    kf=ndi.uniform_filter(keep.astype(np.float32),3)
    alpha=alpha*np.clip(kf*1.5-0.25,0,1)
    k[...,3]=alpha.astype(np.uint8)
    xn=int(np.mean(np.nonzero((cs[300:480]>0))[0]))+300 if False else None
    bodies[p]=k; cuts[p]=cs
# neck centre: midpoint of neck skin at y=385 in idle sheet
rgb=idle_rgb
row=rgb[385]
skin=(row[:,0]>175)&(row[:,1]>100)&(row[:,1]<200)&(row[:,0]-row[:,2]>60)
xs=np.nonzero(skin[300:480])[0]+300
NX=int((xs.min()+xs.max())/2)
NY=int(cuts['idle'][NX])
print('neck skin span',xs.min(),xs.max(),'NX',NX,'NY',NY)
# common scale
foot=1355
S=520.0/(foot-NY)
print('scale',S)
out={'bodies':{}}
for p in POSES:
    im=Image.fromarray(bodies[p])
    W,H=im.size
    im=im.resize((round(W*S),round(H*S)),Image.LANCZOS)
    a=np.asarray(im)[...,3]
    ys,xs=np.nonzero(a>8)
    bb=(xs.min(),ys.min(),xs.max()+1,ys.max()+1)
    im=im.crop(bb)
    im.save(D+f'body_{p}.png')
    nx=NX*S-bb[0]; ny=cuts[p][NX]*S-bb[1]
    # foot x: centre of opaque pixels in bottom 3% rows
    aa=np.asarray(im)[...,3]
    fr=aa[int(aa.shape[0]*0.97):]
    fx=np.nonzero(fr.sum(0)>0)[0]
    out['bodies'][p]={'file':f'body_{p}.png','w':im.width,'h':im.height,
       'neck':[round(nx,1),round(ny,1)],'foot':[round((fx.min()+fx.max())/2,1),im.height]}
    print(p,im.size,out['bodies'][p])
# HEAD at 512 (0.5 of raw 1024)
HS=0.5
hk=key(R+'head_raw.png')
him=Image.fromarray(hk).resize((512,512),Image.LANCZOS)
a=np.asarray(him)[...,3]; ys,xs=np.nonzero(a>8)
hb=(xs.min(),ys.min(),xs.max()+1,ys.max()+1)
him=him.crop(hb); him.save(D+'head.png')
f=1024/350*HS   # sheet px -> head px
hnx=(NX-CROP[0])*f-hb[0]; hny=(NY-CROP[1])*f-hb[1]
head_scale=S/f
out['head']={'file':'head.png','w':him.width,'h':him.height,'neck':[round(hnx,1),round(hny,1)],'sprites':{}}
out['head_scale']=round(head_scale,5)
# sprites
base=np.asarray(Image.open(R+'head_raw.png').convert('RGB')).astype(int)
zones={'mouth':(280,560,960,1000),'eyes':(300,360,960,640),'brows':(300,230,920,430)}
spr=[('mouth.rest','m_rest','mouth'),('mouth.M','m_M','mouth'),('mouth.A','m_A','mouth'),('mouth.E','m_E','mouth'),
     ('mouth.O','m_O','mouth'),('mouth.laugh','m_laugh','mouth'),('eyes.closed','eyes_closed','eyes'),('brows.angry','brows_angry','brows')]
for name,fn,z in spr:
    v=np.asarray(Image.open(R+fn+'.png').convert('RGB')).astype(int)
    m=np.abs(v-base).sum(2)>60
    zm=np.zeros_like(m); x0,y0,x1,y1=zones[z]; zm[y0:y1,x0:x1]=True
    m&=zm
    m=ndi.binary_opening(m,iterations=2)
    ys,xs=np.nonzero(m)
    pad=10
    bx0,by0,bx1,by1=max(xs.min()-pad,0),max(ys.min()-pad,0),min(xs.max()+pad,1023),min(ys.max()+pad,1023)
    # snap to even for 0.5 scaling
    bx0-=bx0%2; by0-=by0%2; bx1+=(2-bx1%2); by1+=(2-by1%2)
    vk=Image.fromarray(key(R+fn+'.png')).resize((512,512),Image.LANCZOS)
    sx0,sy0,sx1,sy1=bx0//2,by0//2,bx1//2,by1//2
    sp=vk.crop((sx0,sy0,sx1,sy1))
    # feather the rect border so it blends into the head (inner 3px ramp)
    sa=np.asarray(sp).copy().astype(np.float32)
    h,w=sa.shape[:2]
    m2=np.abs(v-base).sum(2)>40
    m2&=zm
    m2=ndi.binary_opening(m2,iterations=1)
    m2=ndi.binary_dilation(m2,iterations=8)
    m2=ndi.binary_fill_holes(m2)
    soft=ndi.gaussian_filter(m2.astype(np.float32),3)
    soft=np.clip(soft*1.6,0,1)
    soft=np.asarray(Image.fromarray((soft*255).astype(np.uint8)).resize((512,512),Image.LANCZOS)).astype(np.float32)/255
    sa[...,3]*=soft[sy0:sy1,sx0:sx1]
    yy,xx=np.mgrid[0:h,0:w]; edge=np.minimum(np.minimum(xx,w-1-xx),np.minimum(yy,h-1-yy))
    sa[...,3]*=np.clip(edge/2.0,0,1)
    sp=Image.fromarray(sa.astype(np.uint8))
    fname=name.replace('.','_')+'.png'
    sp.save(D+fname)
    out['head']['sprites'][name]={'file':fname,'x':int(sx0-hb[0]),'y':int(sy0-hb[1]),'w':sp.width,'h':sp.height}
    print(name,out['head']['sprites'][name])
out['meta']={'character':'Dadaji','layer_order':['head','head sprites','body (drawn ON TOP of head so the collar covers the neck stub)'],
  'compose':'place head scaled by head_scale so head.neck*head_scale lands on body.neck; draw body after head','missing':['brows.up']}
json.dump(out,open(D+'rig.json','w'),indent=2)
