import json
from PIL import Image
D='/workspace/work/videoskill/examples/painted-duet/cast2/dadaji/'
rig=json.load(open(D+'rig.json'))
H=rig['head']; hs=rig['head_scale']
def head_with(sprites):
    h=Image.open(D+H['file']).convert('RGBA')
    for s in sprites:
        sp=H['sprites'][s]; h.alpha_composite(Image.open(D+sp['file']).convert('RGBA'),(sp['x'],sp['y']))
    return h
def compose(pose,sprites=('mouth.rest',)):
    b=rig['bodies'][pose]; body=Image.open(D+b['file']).convert('RGBA')
    h=head_with(sprites); hw,hh=round(h.width*hs),round(h.height*hs)
    h=h.resize((hw,hh),Image.LANCZOS)
    hx=b['neck'][0]-H['neck'][0]*hs; hy=b['neck'][1]-H['neck'][1]*hs
    ox=int(max(0,-hx))+10; oy=int(max(0,-hy))+10
    W=max(body.width,int(hx+hw))+ox+10; Ht=body.height+oy
    c=Image.new('RGBA',(W,Ht),(0,0,0,0))
    c.alpha_composite(h,(int(round(hx))+ox,int(round(hy))+oy))
    c.alpha_composite(body,(ox,oy))
    return c
if __name__=='__main__':
    poses=list(rig['bodies'])
    ims=[compose(p) for p in poses]
    H2=max(i.height for i in ims); W=sum(i.width for i in ims)+20*len(ims)
    bg=Image.new('RGBA',(W,H2+20),(236,214,180,255)); x=10
    for i in ims: bg.alpha_composite(i,(x,H2-i.height+10)); x+=i.width+20
    bg.convert('RGB').save(D+'qa_poses.jpg',quality=92)
    ms=['mouth.rest','mouth.M','mouth.A','mouth.E','mouth.O','mouth.laugh']
    extra=[['eyes.closed','mouth.rest'],['brows.angry','mouth.A'],['eyes.closed','mouth.laugh']]
    hs_=[head_with([m]) for m in ms]+[head_with(e) for e in extra]
    w,h=hs_[0].size
    bg=Image.new('RGBA',(w*5+60,(h+10)*2+10),(236,214,180,255))
    for k,im in enumerate(hs_): bg.alpha_composite(im,(10+(k%5)*(w+10),10+(k//5)*(h+10)))
    bg.convert('RGB').save(D+'qa_mouths.jpg',quality=92)
