import sys, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
R='/workspace/skills-src/video-director-skill'; F=R+'/handdrawn/fonts/'
sys.path.insert(0,R+'/screencast'); import fx
W,H=1600,800
# background: yellow halftone left, dark chalk right, torn diagonal seam
y=Image.fromarray(fx.make_bg('sun',W,H)); c=Image.fromarray(fx.make_bg('chalk',W,H))
m=fx.torn_mask(H,W,.52,seed=11)  # 1 = left (yellow)
bg=Image.composite(y,c,Image.fromarray((m*255).astype(np.uint8)))
# white torn lip along seam
lip=np.clip(fx.torn_mask(H,W,.535,seed=11)-fx.torn_mask(H,W,.52,seed=11),0,1)
bg=Image.composite(Image.new('RGB',(W,H),(250,248,240)),bg,Image.fromarray((lip*255).astype(np.uint8)))
bg=bg.convert('RGBA'); d=ImageDraw.Draw(bg)
def f(n,s): return ImageFont.truetype(F+n,s)
ink=(28,26,34)
d.text((70,120),"Video",font=f('Baloo2-800-normal.ttf',150),fill=ink)
d.text((70,250),"Director",font=f('Baloo2-800-normal.ttf',150),fill=ink)
# red sticker "SKILL"
st=Image.new('RGBA',(330,120),(0,0,0,0)); sd=ImageDraw.Draw(st)
sd.rounded_rectangle((6,6,324,114),30,fill=(255,255,255)); sd.rounded_rectangle((14,14,316,106),24,fill=(226,52,64))
sd.text((165,58),"SKILL",font=f('Baloo2-800-normal.ttf',84),fill=(255,255,255),anchor='mm')
st=st.rotate(-6,expand=True,resample=Image.BICUBIC)
sh=Image.new('RGBA',st.size,(0,0,0,0)); sh.putalpha(st.split()[3].point(lambda a:a*.35)); sh=sh.filter(ImageFilter.GaussianBlur(6))
bg.alpha_composite(sh,(84,438)); bg.alpha_composite(st,(76,428))
d.text((76,575),"One prompt in. A finished reel out.",font=f('PermanentMarker-400-normal.ttf',40),fill=ink)
d.text((78,640),"talking characters · screencast tutorials",font=f('Nunito-700-normal.ttf',27),fill=(60,52,40))
d.text((78,690),"whiteboard · horror · 3D explainers · Hindi VO",font=f('Nunito-700-normal.ttf',27),fill=(60,52,40))
# phone cards
def card(p,wid,rot,frame=(255,255,255)):
    im=Image.open(p).convert('RGB'); k=wid/im.width; im=im.resize((wid,int(im.height*k)),Image.LANCZOS)
    b=10; cd=Image.new('RGBA',(im.width+2*b,im.height+2*b),frame+(255,)); cd.paste(im,(b,b))
    cd=cd.rotate(rot,expand=True,resample=Image.BICUBIC)
    s=Image.new('RGBA',cd.size,(0,0,0,0)); s.putalpha(cd.split()[3].point(lambda a:a*.45)); s=s.filter(ImageFilter.GaussianBlur(10))
    return cd,s
tape=Image.open(R+'/screencast/assets/tape.png').convert('RGBA'); tape=tape.resize((110,int(tape.height*110/tape.width)))
items=[('hyp.png',200,7,(905,90)),('w1.png',210,-5,(1105,40)),('painted-duet.png',190,4,(1320,120)),
       ('w2.png',190,-8,(980,410)),('dhai-baje.png',180,6,(1190,430)),('handdrawn.png',175,-4,(1390,440))]
for p,wid,rot,(x,yy) in items:
    cd,s=card(p,wid,rot); bg.alpha_composite(s,(x+10,yy+16)); bg.alpha_composite(cd,(x,yy))
    bg.alpha_composite(tape.rotate(rot*1.5+3,expand=True),(x+cd.width//2-55,yy-18))
# host waving, bottom-centre on the seam
h=Image.open(R+'/examples/screencast-wiki/host/wave.png').convert('RGBA'); k=430/h.height; h=h.resize((int(h.width*k),430),Image.LANCZOS)
bg.alpha_composite(h,(745,H-430+40))
# marker arrow pointing from host to cards
ar=Image.open(R+'/screencast/assets/marker_arrow.png').convert('RGBA'); ar=ar.resize((170,int(ar.height*170/ar.width))).rotate(18,expand=True)
bg.alpha_composite(ar,(850,300))
bg.convert('RGB').save(R+'/docs/img/hero.jpg',quality=90)
