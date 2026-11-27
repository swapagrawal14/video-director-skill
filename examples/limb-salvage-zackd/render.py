import numpy as np, math, json, subprocess, sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W,H,FPS=1080,1920,30
F='/tmp/vds/fonts/'
def font(sz,w='baloo'):
    f=ImageFont.truetype(F+('baloo2.ttf' if w=='baloo' else 'fredoka.ttf'),sz)
    try: f.set_variation_by_axes([800 if w=='baloo' else 700])
    except Exception: pass
    return f
SC=W/768  # source->frame scale
def ease(x): x=min(max(x,0),1); return x*x*(3-2*x)
def eo(x): x=min(max(x,0),1); return 1-(1-x)**3
def back(x,s=1.7): x=min(max(x,0),1); x-=1; return x*x*((s+1)*x+s)+1
VO=[l for l in json.load(open('script.json'))]
durs=[float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f'vo/{i:02d}.wav'],capture_output=True,text=True).stdout) for i in range(8)]
LEAD=0.35; TAIL=[0.45]*7+[1.6]
SD=[LEAD+d+t for d,t in zip(durs,TAIL)]; ST=np.cumsum([0]+SD[:-1]).tolist(); TOT=sum(SD)
names=['s00_patient','s01_doctor','s02_scan','s03_tumor','s04_implant','s05_nerves','s06_walk','s07_end']
cache={}
def img(n,cut=False):
    k=n+('_cut' if cut else '')
    if k not in cache:
        im=Image.open(f'img/{k}.png').convert('RGBA'); cache[k]=im.resize((im.width*2,im.height*2),Image.LANCZOS)
    return cache[k]
def place(src,zoom,cx,cy,rot=0,blur=0):
    """render src (2x of 768x1376) so that source point (cx,cy) [orig coords] is at frame centre, scale SC*zoom"""
    s=SC*zoom/2  # frame px per 2x-src px
    a=math.cos(math.radians(rot))/s; b=math.sin(math.radians(rot))/s
    # inverse map frame (x,y) -> src
    ox,oy=cx*2,cy*2
    T=(a, b, ox-a*W/2-b*H/2, -b, a, oy+b*W/2-a*H/2)
    out=src.transform((W,H),Image.AFFINE,T,Image.BICUBIC)
    return out.filter(ImageFilter.GaussianBlur(blur)) if blur else out
def to_frame(cx,cy,zoom,px,py):
    return (W/2+(px-cx)*SC*zoom, H/2+(py-cy)*SC*zoom)
BG=(110,198,255)
def bgfill(): return Image.new('RGBA',(W,H),BG+(255,))
_yy,_xx=np.mgrid[0:H,0:W]; _r=np.sqrt(((_xx-W/2)/W)**2+((_yy-H*0.45)/H)**2)
_g=np.clip(1-_r*1.4,0,1)[...,None]; _c=np.array([150,220,255])*_g+np.array([70,165,235])*(1-_g)
GRAD=Image.fromarray(np.dstack([_c,np.full((H,W,1),255)]).astype(np.uint8),'RGBA')
# ---------- overlay helpers
def glow(fr,x,y,r,col,a):
    if a<=0: return
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    d.ellipse([x-r,y-r,x+r,y+r],fill=col+(int(255*min(a,1)),))
    fr.alpha_composite(L.filter(ImageFilter.GaussianBlur(r*0.45)))
def ring(fr,x,y,r,col,a,w=8):
    if a<=0: return
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    d.ellipse([x-r,y-r,x+r,y+r],outline=col+(int(255*min(a,1)),),width=w); fr.alpha_composite(L)
def pill(fr,text,x,y,p,col=(255,255,255),tc=(20,40,80),sz=54,anchor='c',sub=None):
    if p<=0: return
    s=back(p); f=font(sz)
    tw=f.getlength(text); bw=int(tw+64); bh=int(sz*1.55)
    if sub: fs=font(int(sz*0.62)); bw=max(bw,int(fs.getlength(sub)+64)); bh+=int(sz*0.75)
    L=Image.new('RGBA',(bw+40,bh+40),(0,0,0,0)); d=ImageDraw.Draw(L)
    d.rounded_rectangle([20,26,bw+20,bh+26],radius=bh//2 if not sub else 34,fill=(0,40,90,70))
    d.rounded_rectangle([20,20,bw+20,bh+20],radius=bh//2 if not sub else 34,fill=col+(255,))
    d.text((20+bw/2,20+sz*0.78),text,font=f,fill=tc,anchor='mm')
    if sub: d.text((20+bw/2,20+sz*1.62),sub,font=font(int(sz*0.62)),fill=tc,anchor='mm')
    L=L.resize((max(1,int(L.width*s)),max(1,int(L.height*s))),Image.BICUBIC)
    if p<1: 
        A=L.getchannel('A').point(lambda v:int(v*min(1,p*3))); L.putalpha(A)
    fr.alpha_composite(L,(int(x-L.width/2),int(y-L.height/2)))
def leader(fr,x0,y0,x1,y1,p,col=(255,255,255)):
    if p<=0: return
    d=ImageDraw.Draw(fr); q=eo(p); xe=x0+(x1-x0)*q; ye=y0+(y1-y0)*q
    d.line([x0,y0,xe,ye],fill=col+(255,),width=6); d.ellipse([x0-12,y0-12,x0+12,y0+12],fill=col+(255,),outline=(20,40,80,255),width=4)
def title(fr,lines,y,p,sizes,cols):
    if p<=0: return
    yy=y
    for i,(ln,sz,c) in enumerate(zip(lines,sizes,cols)):
        q=back(min(1,max(0,p*1.6-i*0.25)),2.2)
        if q<=0: yy+=sz*1.1; continue
        f=font(sz); L=Image.new('RGBA',(W,int(sz*1.6)),(0,0,0,0)); d=ImageDraw.Draw(L)
        d.text((W/2,sz*0.8+6),ln,font=f,fill=(0,40,90,120),anchor='mm')
        d.text((W/2,sz*0.8),ln,font=f,fill=c,anchor='mm',stroke_width=max(4,sz//14),stroke_fill=(15,35,75))
        L=L.resize((int(W*q),max(1,int(L.height*q))),Image.BICUBIC)
        fr.alpha_composite(L,(int(W/2-L.width/2),int(yy+sz*0.8*(1-q))))
        yy+=sz*1.12
def sparkle(fr,x,y,size,a):
    if a<=0: return
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L); c=(255,255,255,int(255*a))
    d.polygon([(x,y-size),(x+size*0.18,y-size*0.18),(x+size,y),(x+size*0.18,y+size*0.18),(x,y+size),(x-size*0.18,y+size*0.18),(x-size,y),(x-size*0.18,y-size*0.18)],fill=c)
    fr.alpha_composite(L.filter(ImageFilter.GaussianBlur(1.5)))
def shine(fr,mask_box,t,a=0.55):
    # diagonal light streak across box
    x0,y0,x1,y1=[int(v) for v in mask_box]
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    cx=x0-200+(x1-x0+400)*t
    d.polygon([(cx-40,y0),(cx+40,y0),(cx-60+120,y1),(cx-140,y1)],fill=(255,255,255,int(255*a)))
    L=L.filter(ImageFilter.GaussianBlur(18)); m=Image.new('L',(W,H),0); ImageDraw.Draw(m).rectangle([x0,y0,x1,y1],fill=255)
    L.putalpha(Image.composite(L.getchannel('A'),Image.new('L',(W,H),0),m)); fr.alpha_composite(L)
# ---------- captions (approx word timing by char length)
CAP=[]
for i,txt in enumerate(VO):
    ws=txt.replace(',', ',').split(); w8=[len(w.strip(',.!?:'))+2 for w in ws]; tot=sum(w8)
    t=ST[i]+LEAD+0.05; d=durs[i]-0.15
    for w,k in zip(ws,w8): CAP.append((t,t+d*k/tot,w,i)); t+=d*k/tot
KEY={'cancer','pair','nahi!','limb','salvage','surgery.','MRI','CT','tumor','healthy','poora','metal','implant','endoprosthesis','bone','graft','nasein','blood','vessels','Chemotherapy','physiotherapy','chalna','orthopaedic','oncosurgeon'}
def captions(fr,t):
    cur=[c for c in CAP if c[0]<=t<c[1]+0.25]
    if not cur: return
    i=cur[-1][3]; words=[c for c in CAP if c[3]==i]
    # chunk into groups of 3
    idx=[k for k,c in enumerate(words) if c[0]<=t]
    if not idx: return
    k=idx[-1]; g=k//3; grp=words[g*3:g*3+3]
    f=font(84); y=1640
    tw=sum(f.getlength(c[2]+' ') for c in grp); x=W/2-tw/2
    d=ImageDraw.Draw(fr)
    for c in grp:
        w=c[2]; act=c[0]<=t; p=eo((t-c[0])/0.12)
        clean=w.strip(',.!?:')
        col=(255,214,10) if (w in KEY or clean in KEY) else (255,255,255)
        if not act: x+=f.getlength(w+' '); continue
        sz=int(78*(0.7+0.3*back(min(1,(t-c[0])/0.18))))
        ff=font(sz)
        d.text((x+f.getlength(w)/2,y),w,font=ff,fill=col,anchor='mm',stroke_width=8,stroke_fill=(10,25,60))
        x+=f.getlength(w+' ')
# ---------- floating bokeh
rng=np.random.default_rng(7); BOK=[(rng.uniform(0,W),rng.uniform(0,H),rng.uniform(10,40),rng.uniform(0.3,1),rng.uniform(-20,20)) for _ in range(22)]
def bokeh(fr,t,a=0.35):
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    for x,y,r,sp,dx in BOK:
        yy=(y-t*60*sp)%H; xx=x+dx*math.sin(t*0.7+r)
        d.ellipse([xx-r,yy-r,xx+r,yy+r],fill=(255,255,255,int(255*a*sp*0.5)))
    fr.alpha_composite(L.filter(ImageFilter.GaussianBlur(6)))
# ---------- shots
def bbox_of(n):
    k=n+'_bb'
    if k not in cache:
        a=np.asarray(Image.open(f'img/{n}.png').convert('RGBA'))[...,3]; ys,xs=np.where(a>40); cache[k]=(xs.min(),ys.min(),xs.max(),ys.max())
    return cache[k]
def sprite(fr,n,cx,cy,z,sx,sy,tw,rot=0,alpha=1.0):
    """paste cut-out sprite n so its bbox centre lands at source point (sx,sy) of current camera, sized to tw source px wide"""
    x0,y0,x1,y1=bbox_of(n); im=Image.open(f'img/{n}.png').convert('RGBA').crop((x0,y0,x1+1,y1+1))
    k=tw/(x1-x0)*SC*z; im=im.resize((max(1,int(im.width*k)),max(1,int(im.height*k))),Image.LANCZOS)
    if rot: im=im.rotate(rot,expand=True,resample=Image.BICUBIC)
    if alpha<1: im.putalpha(im.getchannel('A').point(lambda v:int(v*alpha)))
    X,Y=to_frame(cx,cy,z,sx,sy); fr.alpha_composite(im,(int(X-im.width/2),int(Y-im.height/2)))
def posecut(fr,n,z,cx,cy,since,t,full=False,dy=0):
    """living pose: hard cut + squash on entry, breathing, sway"""
    q=min(1,since/0.18); sq=1+0.05*(1-q)*math.cos(q*math.pi*2)
    br=1+0.007*math.sin(t*2.4)
    zz=z*sq*br; rot=0.5*math.sin(t*1.1)
    src=img(n,not full)
    L=place(src,zz,cx,cy+ (1-sq)*-300,rot=rot)
    fr.alpha_composite(L,(0,int(dy)))
def pick(v,table):
    cur=table[0][1]; at=-9
    for tv,n in table:
        if v>=tv: cur=n; at=tv
    return cur,v-at
def shot(i,tl):
    global SD_cur
    SD_cur=SD[i]; u=tl/SD[i]; t=ST[i]+tl; n=names[i]; v=tl-LEAD
    if i==0:
        z=1.0+0.15*ease(u)+0.05*eo((v-3.0)/0.3); cx,cy=384,640
        pn,since=pick(v,[(-9,'s00_patient'),(3.0,'pat_scared')])
        fr=GRAD.copy(); posecut(fr,pn,z,cx,cy,since,t,full=True)
        kx,ky=to_frame(cx,cy,z,320,850)
        hb=abs(math.sin(tl*math.pi*1.25))**8
        glow(fr,kx,ky,90+30*hb,(255,40,30),0.35+0.45*hb)
        title(fr,['KYA PAIR','KAATNA PADEGA?'],170,eo((v-4.1)/0.5),[130,110],[(255,255,255),(255,80,70)])
    elif i==1:
        fr=GRAD.copy(); bokeh(fr,t)
        z=0.95+0.08*ease(u); cx,cy=384,600
        pn,since=pick(v,[(-9,'doc_explain'),(2.6,'doc_no'),(4.1,'doc_thumb')])
        pop=back(min(1,tl/0.5))
        posecut(fr,pn,z*(0.6+0.4*pop),cx,cy,since,t)
        if pn=='doc_thumb':
            tx,ty=to_frame(cx,cy,z,540,700)
            for k in range(3):
                ph=(since*1.6+k*0.33)%1; sparkle(fr,tx+(k-1)*60,ty-60-k*20,34*math.sin(ph*math.pi),math.sin(ph*math.pi))
        pill(fr,'LIMB SALVAGE SURGERY',W/2,300,(v-4.1)/0.5,col=(255,214,10),sz=66,sub='pair bachane wali surgery')
        if v<4.1: title(fr,['NAHI!'],170,eo((v-2.6)/0.35),[170],[(255,255,255)])
    elif i==2:
        fr=GRAD.copy(); bokeh(fr,t)
        z=1.0+0.12*ease(u); cx,cy=330+20*u,640
        pn,since=pick(v,[(-9,'s02_scan'),(3.0,'scan_explain')])
        posecut(fr,pn,z,cx,cy,since,t)
        mx,my=to_frame(cx,cy,z,246,496)
        x0,y0=to_frame(cx,cy,z,152,215); x1,y1=to_frame(cx,cy,z,640,905)
        sy=y0+(y1-y0)*((tl*0.55)%1)
        L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L); d.rectangle([x0,sy-6,x1-260,sy+6],fill=(150,255,255,200)); fr.alpha_composite(L.filter(ImageFilter.GaussianBlur(5)))
        for k in range(3):
            ph=((tl-1.0)*0.8+k/3)%1
            if tl>1.0: ring(fr,mx,my,20+110*ph,(255,60,60),(1-ph)*0.9,6)
        pill(fr,'MRI + CT = PLAN',W/2,260,(v-0.6)/0.5,sz=64)
        pill(fr,'size',mx-60,my-190,(v-3.0)/0.4,col=(255,214,10),sz=46); pill(fr,'position',mx+40,my+200,(v-3.6)/0.4,col=(255,214,10),sz=46)
    elif i==3:
        z=1.0+0.2*ease(u); cx,cy=420,620
        RM=4.0  # removal starts ("poora nikaala")
        fr=GRAD.copy()
        if v<RM:
            fr.alpha_composite(place(img('s03_tumor'),z,cx,cy)); bokeh(fr,t,0.2)
            tx,ty=to_frame(cx,cy,z,440,563); pul=0.5+0.5*math.sin(tl*7)
            glow(fr,tx,ty,120+25*pul,(255,70,40),0.3+0.3*pul)
            leader(fr,tx+60,ty-40,tx+200,ty-330,(v-0.6)/0.4); pill(fr,'TUMOR',min(tx+200,W-200),ty-360,(v-0.8)/0.4,col=(255,90,80),tc=(255,255,255),sz=60)
            leader(fr,tx-140,ty-160,tx-170,ty+380,(v-2.2)/0.4); pill(fr,'+ healthy margin',max(tx-170,260),ty+420,(v-2.4)/0.4,col=(140,255,230),sz=50)
            # cut line sweeps around just before removal
            cl=(v-(RM-0.7))/0.7
            if 0<cl<1: ring(fr,tx,ty,int(200*cl+40),(140,255,255),1-cl,10)
        else:
            q=(v-RM)/1.4
            fr.alpha_composite(place(img("leg_gap"),z,cx,cy)); bokeh(fr,t,0.2)
            e=ease(q); sx=440+520*e; sy=565-420*e+120*e*e
            sprite(fr,'seg_cut',cx,cy,z,sx,sy,150*(1+0.15*e),rot=-35*e,alpha=1-max(0,(q-0.75)/0.25))
            if q<0.25: glow(fr,*to_frame(cx,cy,z,440,565),220,(255,255,255),0.8*(1-q/0.25))
            pill(fr,'TUMOR OUT',W/2,280,(v-RM-0.4)/0.4,col=(140,255,170),sz=64)
    elif i==4:
        z=1.15-0.12*ease(u); cx,cy=400,700
        LAND=3.2
        fr=GRAD.copy()
        if v<LAND:
            fr.alpha_composite(place(img("leg_gap"),z,cx,cy)); bokeh(fr,t,0.2)
            q=back(min(1,max(0,(v+LEAD-0.1)/(LAND+LEAD-0.1))),1.2)
            sy=-500+(640+500)*q
            sprite(fr,'implant_cut',cx,cy,z,405,sy,120)
        else:
            k=v-LAND
            fr.alpha_composite(place(img('s04_implant'),z*(1+0.03*math.exp(-k*8)*math.cos(k*40)),cx,cy)); bokeh(fr,t,0.2)
            if k<0.3: glow(fr,*to_frame(cx,cy,z,405,640),420,(255,255,255),1-k/0.3)
            a0=to_frame(cx,cy,z,300,400); a1=to_frame(cx,cy,z,510,860)
            shine(fr,(a0[0],a0[1],a1[0],a1[1]),(k*0.7)%1.4/1.4)
            ix,iy=to_frame(cx,cy,z,405,650)
            for j in range(4):
                ph=(k*0.9+j*0.25)%1; sparkle(fr,ix+[-90,80,-40,110][j],iy+[-120,-30,90,140][j],36*math.sin(ph*math.pi),math.sin(ph*math.pi))
        pill(fr,'ENDOPROSTHESIS',W/2,240,(v-4.7)/0.5,col=(255,214,10),sz=64,sub='strong metal implant')
        pill(fr,'ya BONE GRAFT',W/2,470,(v-7.0)/0.4,sz=56)
    elif i==5:
        z=1.05+0.12*ease(u); cx,cy=430,690
        fr=GRAD.copy(); fr.alpha_composite(place(img(n),z,cx,cy)); bokeh(fr,t,0.2)
        for k in range(4):
            ph=(tl*0.45+k/4)%1; py=120+ph*1150; px=448+18*math.sin(py/180)
            x,y=to_frame(cx,cy,z,px,py); glow(fr,x,y,40,(255,255,160),0.9*math.sin(ph*math.pi))
        nx,ny=to_frame(cx,cy,z,455,420); vx,vy=to_frame(cx,cy,z,480,840)
        leader(fr,nx,ny,nx+190,ny-120,(v-0.5)/0.4); pill(fr,'NERVE',min(nx+220,W-160),ny-160,(v-0.7)/0.4,col=(255,214,10),sz=54)
        leader(fr,vx,vy,vx+170,vy+120,(v-1.6)/0.4); pill(fr,'BLOOD VESSELS',min(vx+150,W-260),vy+160,(v-1.8)/0.4,col=(255,90,80),tc=(255,255,255),sz=50)
        pill(fr,'SAFE!',W/2,250,(v-3.0)/0.4,col=(140,255,170),sz=70)
    elif i==6:
        fr=GRAD.copy(); bokeh(fr,t)
        z=0.95+0.12*ease(u); cx,cy=384-30*u,600
        step=int(max(0,tl)*3.2)%2
        pn='walk_a' if step==0 else 'walk_b'
        bob=-12*abs(math.sin(tl*3.2*math.pi))
        posecut(fr,pn,z,cx,cy,1.0,t,dy=bob)
        pill(fr,'CHEMO',300,300,(v-0.2)/0.4,col=(255,214,10),sz=60)
        pill(fr,'PHYSIO',780,300,(v-1.6)/0.4,col=(140,255,230),sz=60)
        pill(fr,'phir se chalna!',W/2,470,(v-3.2)/0.4,sz=54)
    elif i==7:
        fr=GRAD.copy(); bokeh(fr,t)
        z=0.95+0.05*ease(u); cx,cy=384,560
        pn,since=pick(v,[(-9,'s07_end'),(0.9,'end_wave')])
        posecut(fr,pn,z,cx,cy,since,t)
        if pn=='end_wave':
            hx,hy=to_frame(cx,cy,z,600,640)
            for k in range(2):
                ph=(since*1.4+k*0.5)%1; ring(fr,hx+75,hy-45,int(30+50*ph),(255,255,255),(1-ph)*0.8,5)
        title(fr,['Dr. Abhijeet Salunke'],150,eo((v-3.0)/0.6),[92],[(255,255,255)])
        pill(fr,'Orthopaedic Oncosurgeon',W/2,390,(v-3.6)/0.4,col=(255,214,10),sz=54,sub='Limb Salvage & Bone Cancer Care')
        d=ImageDraw.Draw(fr); fa=int(255*eo((v-4.6)/0.6))
        if fa>0:
            d.text((W/2,1800),'Educational video. Apne doctor se salaah lein.',font=font(36),fill=(255,255,255,fa),anchor='mm',stroke_width=3,stroke_fill=(10,25,60))
            d.text((W/2,1850),'Animation: Swapnil Agrawal',font=font(32),fill=(230,245,255,fa),anchor='mm',stroke_width=3,stroke_fill=(10,25,60))
    return fr
def frame(f):
    t=f/FPS
    i=max(k for k in range(8) if ST[k]<=t+1e-9); tl=t-ST[i]
    fr=shot(i,tl)
    # zoom-punch transition: last 0.18s of shot i -> blend into first 0.18 of i+1
    TR=0.18
    if i<7 and SD[i]-tl<TR:
        q=1-(SD[i]-tl)/TR; nx=shot(i+1,0.0)
        fr=Image.blend(fr.resize((int(W*(1+0.25*q)),int(H*(1+0.25*q)))).crop((int(W*0.125*q),int(H*0.125*q),int(W*0.125*q)+W,int(H*0.125*q)+H)).filter(ImageFilter.GaussianBlur(8*q)),nx,q*0.85)
    captions(fr,t)
    # progress bar
    d=ImageDraw.Draw(fr); d.rectangle([0,H-10,W*t/TOT,H],fill=(255,214,10,255))
    return fr.convert('RGB')
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='stills':
        ts=[float(x) for x in sys.argv[2:]]; ims=[frame(int(x*FPS)).resize((270,480)) for x in ts]
        s=Image.new('RGB',(270*len(ims),480))
        for k,im in enumerate(ims): s.paste(im,(k*270,0))
        s.save('stills2.jpg'); print(ST,SD,TOT)
    else:
        a,b=int(sys.argv[2]),int(sys.argv[3]); out=sys.argv[4]
        p=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',out],stdin=subprocess.PIPE)
        for f in range(a,b): p.stdin.write(frame(f).tobytes())
        p.stdin.close(); p.wait(); print('done',out)
