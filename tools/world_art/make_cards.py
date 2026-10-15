import os, json, numpy as np, asyncio
from PIL import Image, ImageDraw, ImageFilter
from playwright.async_api import async_playwright
REPO='/workspace/repos/emmavengers-house-game/img/world'; FL='/workspace/world-art/fluent'
for d in ['letters','numbers','animals','countries','places','prayers']: os.makedirs(f'{REPO}/{d}',exist_ok=True)
def save(src,dst,size=256,fn=None):
    im=Image.open(f'{FL}/{src}.png').convert('RGBA')
    if fn: im=fn(im)
    im=im.resize((size,size),Image.LANCZOS); im.save(dst,'WEBP',quality=88,method=6)
LET={'a':'red_apple','b':'soccer_ball','c':'cat','d':'dog','e':'egg','f':'fish','g':'goat','h':'top_hat','i':'lady_beetle','j':'jeans','k':'kite','l':'lion','m':'monkey','n':'nest_with_eggs','o':'octopus','p':'pig','q':'crown','r':'rabbit','s':'sun','t':'tiger','u':'umbrella','v':'volcano','w':'watermelon','x':'fox','y':'yo-yo','z':'zebra'}
for k,v in LET.items(): save(v,f'{REPO}/letters/{k}.webp')
for k in ['lion','elephant','giraffe','zebra','gorilla','hippopotamus','leopard','crocodile','rhinoceros','flamingo']: save(k,f'{REPO}/animals/{k}.webp')
for k,v in {'apple':'red_apple','star':'star','duck':'duck','banana':'banana','butterfly':'butterfly','balloon':'balloon','fish':'fish','ball':'soccer_ball','egg':'egg','strawberry':'sunflower'}.items():
    if k=='strawberry': continue
    save(v,f'{REPO}/numbers/{k}.webp',160)
def jollof(im):
    a=np.array(im).astype(float); r,g,b,al=a[...,0],a[...,1],a[...,2],a[...,3]
    m=(r>170)&(g>170)&(b>170)  # white rice -> orange-red jollof
    lum=(r+g+b)/3/255
    a[...,0]=np.where(m,np.clip(235*lum+20,0,255),r); a[...,1]=np.where(m,np.clip(120*lum+10,0,255),g); a[...,2]=np.where(m,np.clip(40*lum,0,255),b)
    # sprinkle a few green peas / red pepper bits on rice
    out=Image.fromarray(a.astype('uint8'),'RGBA'); d=ImageDraw.Draw(out); rng=np.random.default_rng(3)
    ys,xs=np.where(m)
    for i in rng.choice(len(xs),40,replace=False):
        x,y=xs[i],ys[i]; c=(60,170,60,255) if i%3 else (200,30,30,255); d.ellipse([x-4,y-3,x+4,y+3],fill=c)
    return out
FOOD={'cameroon':('ear_of_corn',None),'nigeria':('cooked_rice',jollof),'ghana':('chocolate_bar',None),'kenya':('cooked_rice',None),'south-africa':('meat_on_bone',None)}
for k,(v,fn) in FOOD.items(): save(v,f'{REPO}/countries/{k}-food.webp',256,fn)
for k,v in {'morning':'sunrise','meal':'fork_and_knife_with_plate','bedtime':'crescent_moon','thanks':'folded_hands'}.items(): save(v,f'{REPO}/prayers/{k}.webp')
for k,v in {'abc':'input_latin_uppercase','hunt':'pencil','numbers':'input_numbers','count':'abacus','safari':'giraffe','animalquiz':'lion','countries':'globe_showing_europe-africa','flagquiz':'triangular_flag','prayer':'church','house':'house_with_garden'}.items(): save(v,f'{REPO}/places/{k}.webp',256)
# --- accurate flags (SVG, 3:2) ---
def star(cx,cy,r,fill):
    import math
    pts=[]
    for i in range(10):
        a=-math.pi/2+i*math.pi/5; rr=r if i%2==0 else r*0.382
        pts.append(f'{cx+rr*math.cos(a):.2f},{cy+rr*math.sin(a):.2f}')
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'
SV={
'cameroon':'<rect width="9" height="6" fill="#007a5e"/><rect x="3" width="3" height="6" fill="#ce1126"/><rect x="6" width="3" height="6" fill="#fcd116"/>'+star(4.5,3,1.0,'#fcd116'),
'nigeria':'<rect width="9" height="6" fill="#008751"/><rect x="3" width="3" height="6" fill="#fff"/>',
'ghana':'<rect width="9" height="2" fill="#ce1126"/><rect y="2" width="9" height="2" fill="#fcd116"/><rect y="4" width="9" height="2" fill="#006b3f"/>'+star(4.5,3,1.0,'#000'),
'kenya':'<rect width="9" height="6" fill="#fff"/><rect width="9" height="1.8" fill="#000"/><rect y="2.1" width="9" height="1.8" fill="#bb0000"/><rect y="4.2" width="9" height="1.8" fill="#006600"/>'
 '<g stroke="#fff" stroke-width=".16" stroke-linecap="round"><line x1="3.2" y1="5.5" x2="5.8" y2=".5"/><line x1="5.8" y1="5.5" x2="3.2" y2=".5"/></g>'
 '<g fill="#fff"><path d="M5.8,.35 l.18,.55 -.36,0z"/><path d="M3.2,.35 l.18,.55 -.36,0z"/></g>'
 '<ellipse cx="4.5" cy="3" rx=".95" ry="2.05" fill="#bb0000"/>'
 '<path d="M4.5,.95 C3.3,1.6 3.3,4.4 4.5,5.05 C3.85,4.2 3.85,1.8 4.5,.95Z" fill="#000"/><path d="M4.5,.95 C5.7,1.6 5.7,4.4 4.5,5.05 C5.15,4.2 5.15,1.8 4.5,.95Z" fill="#000"/>'
 '<g fill="#fff"><ellipse cx="4.5" cy="3" rx=".14" ry=".42"/><ellipse cx="4.5" cy="1.85" rx=".1" ry=".3"/><ellipse cx="4.5" cy="4.15" rx=".1" ry=".3"/></g>',
'south-africa':'<rect width="9" height="3" fill="#e03c31"/><rect y="3" width="9" height="3" fill="#001489"/>'
 '<path d="M0,0 4.5,3 0,6M4.5,3H9" stroke="#fff" stroke-width="2" fill="none"/>'
 '<polygon points="0,0.721 3.418,3 0,5.279" fill="#ffb81c"/>'
 '<path d="M0,0 4.5,3 0,6M4.5,3H9" stroke="#007749" stroke-width="1.2" fill="none"/>'
 '<polygon points="0,1.202 2.697,3 0,4.798" fill="#000"/>'}
async def render():
    async with async_playwright() as p:
        b=await p.chromium.launch();pg=await b.new_page(viewport={'width':900,'height':600})
        for k,body in SV.items():
            await pg.set_content(f'<html><body style="margin:0"><svg width="900" height="600" viewBox="0 0 9 6" style="display:block">{body}</svg></body></html>')
            await pg.screenshot(path=f'/workspace/world-art/flags/{k}.png')
        await b.close()
asyncio.run(render())
def wave(k):
    f=np.array(Image.open(f'/workspace/world-art/flags/{k}.png').convert('RGB').resize((480,320),Image.LANCZOS)).astype(float)
    Wd,Hd=640,460; out=np.zeros((Hd,Wd,4)); x0,y0=110,50; A=16
    for x in range(480):
        ph=x/480*2.4*np.pi; dy=A*np.sin(ph)*(x/480*0.8+0.2); shade=1+0.22*np.cos(ph)*(x/480*0.8+0.2)
        col=np.clip(f[:,x,:]*shade,0,255)
        yy=int(round(y0+dy)); out[yy:yy+320,x0+x,:3]=col; out[yy:yy+320,x0+x,3]=255
    im=Image.fromarray(out.astype('uint8'),'RGBA')
    # soft shadow + pole
    sh=Image.new('RGBA',(Wd,Hd),(0,0,0,0)); a=np.array(im)[...,3]; sha=Image.fromarray((a*0.35).astype('uint8')).filter(ImageFilter.GaussianBlur(10))
    shadow=Image.new('RGBA',(Wd,Hd),(0,0,0,255)); shadow.putalpha(sha); base=Image.new('RGBA',(Wd,Hd),(0,0,0,0)); base.paste(shadow,(10,16),shadow)
    d=ImageDraw.Draw(base)
    for i in range(22):  # 3D pole
        c=int(120+120*np.cos((i-8)/22*np.pi)); d.line([(88+i,30),(88+i,450)],fill=(c,c-30,c-90,255))
    d.ellipse([84,14,124,54],fill=(255,200,40,255),outline=(180,120,0,255),width=3); d.ellipse([92,20,106,34],fill=(255,240,170,255))
    base.alpha_composite(im); base.save(f'{REPO}/countries/{k}-flag.webp','WEBP',quality=90,method=6)
for k in SV: wave(k)
print(sorted(os.listdir(REPO+'/countries')))
