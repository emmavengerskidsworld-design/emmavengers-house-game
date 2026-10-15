"""Render Emmavengers World map art (1080x1920) with Playwright: world map + 5 inner land maps.
Art = stylised 3D island built from MIT Fluent 3D icons + Pixar art already in the game. Outputs JPGs + hotspots.json."""
import json, random, math, asyncio, os
from playwright.async_api import async_playwright
ART='/workspace/world-art'; F='file://'+ART+'/fluent/'; REPO='file:///workspace/repos/emmavengers-house-game/'
W,H=1080,1920
A=json.load(open(ART+'/africa.json'))
def tx(lon,lat): return 70+(lon+17.7)*14.0, 230+(37.4-lat)*19.5
def smooth(pts):
    n=len(pts); d=f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(n):
        p0,p1,p2,p3=pts[i-1],pts[i],pts[(i+1)%n],pts[(i+2)%n]
        c1=(p1[0]+(p2[0]-p0[0])/6,p1[1]+(p2[1]-p0[1])/6); c2=(p2[0]-(p3[0]-p1[0])/6,p2[1]-(p3[1]-p1[1])/6)
        d+=f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d+'Z'
main=[tx(*p) for p in A['main'][:-1]]; mad=[tx(*p) for p in A['mad'][:-1]]
AF=smooth(main); MAD=smooth(mad)
FONT=f"@font-face{{font-family:LG;src:url(file://{ART}/LuckiestGuy-Regular.ttf)}}"
T3D="font-family:LG;color:#ffd21f;-webkit-text-stroke:3px #7a3a00;paint-order:stroke fill;text-shadow:0 4px 0 #e08a00,0 8px 0 #b8560a,0 12px 0 #7a3a00,0 18px 18px rgba(0,0,0,.45)"
def icon(name,x,y,s,rot=0,z=5,extra=''):
    return f'<img src="{F}{name}.png" style="position:absolute;left:{x-s/2:.0f}px;top:{y-s/2:.0f}px;width:{s}px;height:{s}px;transform:rotate({rot}deg);z-index:{z};filter:drop-shadow(0 10px 6px rgba(0,0,0,.35));{extra}">'
def badge(src,x,y,s,pos='center',z=6):
    return f'<div style="position:absolute;left:{x-s/2:.0f}px;top:{y-s/2:.0f}px;width:{s}px;height:{s}px;border-radius:50%;border:12px solid #fff;box-shadow:0 0 0 8px #ffc400,0 16px 22px rgba(0,0,0,.4);background:url({src}) {pos}/cover;z-index:{z}"></div>'
def sign(text,x,y,size=40,bg='#8a4f1f',fg='#fff',z=8):
    return f'<div style="position:absolute;left:{x}px;top:{y}px;transform:translate(-50%,-50%);z-index:{z};background:linear-gradient(#b5773a,#8a4f1f);border:6px solid #5a300f;border-radius:18px;padding:8px 22px 4px;font-family:LG;font-size:{size}px;color:{fg};white-space:nowrap;box-shadow:0 8px 0 #3e2009,0 14px 16px rgba(0,0,0,.35);text-shadow:0 3px 0 #5a300f">{text}</div>'
random.seed(7)
def page(body,bg):
    return f"""<html><head><style>{FONT}*{{margin:0;box-sizing:border-box}}body{{width:{W}px;height:{H}px;overflow:hidden;position:relative;background:{bg}}}</style></head><body>{body}</body></html>"""
def kente(y,h=46):
    return f'<div style="position:absolute;left:0;right:0;top:{y}px;height:{h}px;z-index:9;background:repeating-linear-gradient(90deg,#f2b705 0 36px,#1f8a2b 36px 54px,#d62828 54px 90px,#111 90px 100px),#f2b705;box-shadow:0 6px 10px rgba(0,0,0,.3);border-top:5px solid #5a300f;border-bottom:5px solid #5a300f"><div style="position:absolute;inset:12px 0;background:repeating-linear-gradient(90deg,transparent 0 14px,rgba(0,0,0,.35) 14px 20px)"></div></div>'
def clouds(n,ymax=1920):
    out=''
    for i in range(n):
        out+=icon('cloud',random.choice([random.uniform(40,200),random.uniform(880,1040)]),random.uniform(300,ymax),random.uniform(130,210),z=11,extra='opacity:.92')
    return out
# ---------------- WORLD MAP ----------------
R={'faith':tx(14,24),'letter':tx(-6,12),'nature':tx(34,5),'number':tx(17,-6),'world':tx(24.5,-26)}
def world():
    o=''
    o+='<div style="position:absolute;inset:0;background:radial-gradient(circle at 50% 45%,#5fd3ff 0%,#2aa6ef 45%,#1e6fd9 85%,#174fae 100%)"></div>'
    # wave sparkles
    for i in range(70):
        x,y=random.uniform(0,W),random.uniform(60,H)
        o+=f'<div style="position:absolute;left:{x:.0f}px;top:{y:.0f}px;width:{random.uniform(40,90):.0f}px;height:14px;border-top:5px solid rgba(255,255,255,.35);border-radius:50%"></div>'
    paths=f'<path d="{AF}"/><path d="{MAD}"/>'
    # blobs for regions
    tint={'faith':'#ffd75a','letter':'#c79bff','nature':'#2fa84f','number':'#7cc8ff','world':'#ffab40'}
    blobs=''.join(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{230 if k!="world" else 170}" ry="{170 if k!="world" else 150}" fill="{tint[k]}" opacity=".55" filter="url(#bl)"/>' for k,(x,y) in R.items())
    tufts=''.join(f'<path d="M{x:.0f},{y:.0f} q6,-22 12,0 q6,-18 12,0" stroke="#2f8f2f" stroke-width="4" fill="none" opacity=".5"/>' for x,y in [(random.uniform(60,1040),random.uniform(220,1650)) for _ in range(420)])
    # winding path through lands
    seq=[R['letter'],R['faith'],R['nature'],R['number'],R['world']]
    pd=f"M{seq[0][0]:.0f},{seq[0][1]+90:.0f} C{seq[0][0]+120:.0f},{seq[0][1]-60:.0f} {seq[1][0]-160:.0f},{seq[1][1]+180:.0f} {seq[1][0]:.0f},{seq[1][1]+130:.0f} S{seq[2][0]-160:.0f},{seq[2][1]-40:.0f} {seq[2][0]-60:.0f},{seq[2][1]+120:.0f} S{seq[3][0]+60:.0f},{seq[3][1]-120:.0f} {seq[3][0]:.0f},{seq[3][1]+80:.0f} S{seq[4][0]-60:.0f},{seq[4][1]-150:.0f} {seq[4][0]:.0f},{seq[4][1]+30:.0f}"
    nile=f"M{tx(32.8,-1)[0]:.0f},{tx(32.8,-1)[1]:.0f} C{tx(32,8)[0]:.0f},{tx(32,8)[1]:.0f} {tx(34,18)[0]:.0f},{tx(34,18)[1]:.0f} {tx(31,30.8)[0]:.0f},{tx(31,30.8)[1]:.0f}"
    congo=f"M{tx(12.3,-6)[0]:.0f},{tx(12.3,-6)[1]:.0f} C{tx(17,-3)[0]:.0f},{tx(17,-3)[1]:.0f} {tx(20,3)[0]:.0f},{tx(20,3)[1]:.0f} {tx(25,0)[0]:.0f},{tx(25,0)[1]:.0f}"
    lv=tx(33,-1)
    o+=f'''<svg width="{W}" height="{H}" style="position:absolute;inset:0;z-index:2"><defs>
 <filter id="bl"><feGaussianBlur stdDeviation="55"/></filter><filter id="sh"><feGaussianBlur stdDeviation="22"/></filter>
 <radialGradient id="gr" cx="50%" cy="35%" r="70%"><stop offset="0" stop-color="#a6e86a"/><stop offset=".6" stop-color="#6cc94a"/><stop offset="1" stop-color="#3f9f36"/></radialGradient>
 <linearGradient id="cl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b07a45"/><stop offset="1" stop-color="#6b4220"/></linearGradient>
 <clipPath id="isl">{paths}</clipPath></defs>
 <g transform="translate(14,60)" fill="#0b3a7a" opacity=".45" filter="url(#sh)">{paths}</g>
 <g transform="translate(0,34)" fill="url(#cl)" stroke="#5a3418" stroke-width="6">{paths}</g>
 <g transform="translate(0,17)" fill="#8f5f33">{paths}</g>
 <g fill="none" stroke="rgba(255,255,255,.7)" stroke-width="40" stroke-linejoin="round">{paths}</g>
 <g fill="#f6dc93" stroke="#f6dc93" stroke-width="26" stroke-linejoin="round">{paths}</g>
 <g fill="url(#gr)">{paths}</g>
 <g clip-path="url(#isl)">{blobs}{tufts}
  <path d="{pd}" stroke="#a8743c" stroke-width="44" fill="none" stroke-linecap="round" opacity=".9"/>
  <path d="{pd}" stroke="#f2cf86" stroke-width="32" fill="none" stroke-linecap="round"/>
  <path d="{pd}" stroke="#fff3c4" stroke-width="5" fill="none" stroke-dasharray="14 22" stroke-linecap="round"/>
 </g></svg>'''
    # land clusters
    x,y=R['faith']
    o+=icon('house_with_garden',x-60,y-50,300,z=6)+icon('church',x+185,y-60,140)+icon('open_book',x+200,y+50,110,z=7)+icon('dove',x+40,y-170,90,rot=-8)
    o+=sign('Emmavengers House',x-40,y+112,40,z=9)
    x,y=R['letter']
    o+=icon('input_latin_uppercase',x,y-30,170)+icon('books',x-110,y+50,110)+icon('pencil',x+110,y+40,100,rot=10)+icon('crayon',x+90,y-110,80,rot=-20)
    x,y=R['nature']
    o+=icon('giraffe',x+70,y-80,170)+icon('elephant',x-80,y-10,165)+icon('gorilla',x+100,y+50,120)+icon('palm_tree',x-150,y-120,130)+icon('parrot',x-10,y-150,90)+icon('evergreen_tree',x+190,y-10,100)
    x,y=R['number']
    o+=icon('keycap_1',x-110,y-30,110,rot=-8)+icon('keycap_2',x,y-60,115)+icon('keycap_3',x+110,y-30,110,rot=8)+icon('abacus',x-40,y+60,110)+icon('input_numbers',x+80,y+70,90)
    x,y=R['world']
    o+=icon('globe_showing_europe-africa',x+50,y-30,150)+icon('hut',x-90,y-30,120)+icon('hut',x-30,y+40,95)+icon('long_drum',x+130,y+60,80)+icon('triangular_flag',x-140,y-110,70)
    # decor trees/flowers on island
    for (lon,lat,n,s) in [(0,30,'cactus',80),(-12,20,'palm_tree',85),(5,5,'deciduous_tree',80),(24,-14,'deciduous_tree',85),(38,-8,'sunflower',70),(12,0,'evergreen_tree',75),(20,15,'rock',60),(45,8,'cactus',70),(30,-20,'tulip',60),(18,-20,'hibiscus',60),(-10,7,'hibiscus',55),(47,-19,'palm_tree',80)]:
        xx,yy=tx(lon,lat);o+=icon(n,xx,yy,s,z=4)
    # sea decor
    o+=icon('sun_with_face',985,120,170,z=12)+icon('sailboat',150,1500,150,z=4)+icon('fish',960,1650,110,rot=-15,z=4)+icon('water_wave',110,1180,110,z=4)+icon('octopus',930,1830,100,z=4)+icon('turtle',220,1790,110,z=4)+icon('fish',90,520,90,rot=10,z=4)
    o+=''.join(icon('cloud',cx,cy,cs,z=11,extra='opacity:.92') for cx,cy,cs in [(70,110,170),(80,1350,150),(980,1250,140),(1000,1930,170),(560,1890,150)])
    return page(o,'#1e6fd9')
# ---------------- INNER LAND MAPS ----------------
def title(t,y=170,size=118):
    return f'<div style="position:absolute;left:0;right:0;top:{y-size*0.6:.0f}px;text-align:center;font-size:{size}px;{T3D};z-index:12;letter-spacing:2px">{t}</div>'
def ground(top,cols,path_pts,extra=''):
    a,b,c=cols
    pd='M'+' '.join(f'{x},{y}' for x,y in path_pts)
    return f'''<svg width="{W}" height="{H}" style="position:absolute;inset:0;z-index:1"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset=".55" stop-color="{b}"/><stop offset="1" stop-color="{c}"/></linearGradient></defs>
 <path d="M0,{top} C260,{top-90} 520,{top+60} 780,{top-40} S1040,{top-30} 1080,{top-60} L1080,1920 L0,1920Z" fill="url(#g)"/>
 <path d="M0,{top} C260,{top-90} 520,{top+60} 780,{top-40} S1040,{top-30} 1080,{top-60}" stroke="rgba(255,255,255,.35)" stroke-width="10" fill="none"/>
 {extra}
 <path d="{pd}" stroke="#a8743c" stroke-width="96" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity=".85"/>
 <path d="{pd}" stroke="#f2cf86" stroke-width="76" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
 <path d="{pd}" stroke="#fff3c4" stroke-width="8" fill="none" stroke-dasharray="20 30" stroke-linecap="round"/></svg>'''
def snake(pts):
    # smooth polyline via quadratic midpoints
    s=f'{pts[0][0]},{pts[0][1]}'
    out=[pts[0]]
    return pts
def curvy(points):
    d=f"M{points[0][0]},{points[0][1]}"
    for i in range(1,len(points)):
        x0,y0=points[i-1];x1,y1=points[i];my=(y0+y1)/2
        d+=f" C{x0},{my} {x1},{my} {x1},{y1}"
    return d
def ground2(top,cols,pts,extra=''):
    a,b,c=cols; pd=curvy(pts)
    return f'''<svg width="{W}" height="{H}" style="position:absolute;inset:0;z-index:1"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset=".55" stop-color="{b}"/><stop offset="1" stop-color="{c}"/></linearGradient></defs>
 <path d="M0,{top} C260,{top-90} 520,{top+60} 780,{top-40} S1040,{top-30} 1080,{top-60} L1080,1920 L0,1920Z" fill="url(#g)"/>
 {extra}
 <path d="{pd}" stroke="#a8743c" stroke-width="100" fill="none" stroke-linecap="round" opacity=".85"/>
 <path d="{pd}" stroke="#f2cf86" stroke-width="80" fill="none" stroke-linecap="round"/>
 <path d="{pd}" stroke="#fff3c4" stroke-width="8" fill="none" stroke-dasharray="20 30" stroke-linecap="round"/></svg>'''
def pads(spots,col='#fff'):
    return ''.join(f'<div style="position:absolute;left:{x-175}px;top:{y+70}px;width:350px;height:110px;border-radius:50%;background:radial-gradient(ellipse,rgba(0,0,0,.28),rgba(0,0,0,0) 70%);z-index:2"></div>' for x,y in spots)
SPOTS=[(300,640),(780,900),(300,1200),(780,1500)]
SPOTS2=[(330,760),(750,1240)]
PATH4=[(540,420),(300,640),(780,900),(300,1200),(780,1500),(540,1880)]
PATH2=[(540,420),(330,760),(750,1240),(540,1880)]
def deco(lst):
    return ''.join(icon(n,x,y,s,rot=r,z=z) for n,x,y,s,r,z in lst)
def faith():
    o='<div style="position:absolute;inset:0;background:linear-gradient(#7cc8ff,#bfe6ff 30%,#fff3c4 46%)"></div>'
    o+='<div style="position:absolute;left:540px;top:330px;width:900px;height:900px;margin:-450px;border-radius:50%;background:radial-gradient(circle,rgba(255,240,150,.9),rgba(255,240,150,0) 65%);z-index:0"></div>'
    o+=ground2(470,('#a6e86a','#6cc94a','#3f9f36'),PATH4)+pads(SPOTS)
    o+=deco([('rainbow',540,330,420,0,0),('dove',880,360,120,-10,3),('dove',200,330,90,12,3),('deciduous_tree',90,900,170,0,3),('evergreen_tree',1000,1150,150,0,3),('tulip',520,1060,80,0,3),('sunflower',560,780,90,0,3),('hibiscus',100,1500,90,0,3),('tulip',960,1780,90,0,3),('sunflower',150,1780,100,0,3),('deciduous_tree',560,1380,120,0,3),('herb',980,1350,90,0,3),('candle',590,1640,70,0,3)])
    o+=title('FAITH LAND')+clouds(3,520)
    return page(o,'#7cc8ff')
def letter():
    o='<div style="position:absolute;inset:0;background:linear-gradient(#ffb3e1,#e9c8ff 35%,#d8b4ff)"></div>'
    o+=ground2(480,('#c6f28a','#8edb5f','#55b84a'),PATH2)+pads(SPOTS2)
    o+=deco([('rainbow',860,330,260,0,0),('kite',150,380,140,-15,3),('balloon',950,520,120,8,3),('balloon',90,560,100,-8,3),('books',860,640,170,0,3),('pencil',180,1000,150,30,3),('crayon',900,980,140,-25,3),('artist_palette',820,1600,150,0,3),('notebook',250,1480,130,-10,3),('tulip',600,1000,80,0,3),('sunflower',90,1260,100,0,3),('teddy_bear',990,1780,120,0,3),('school',300,1760,170,0,3),('backpack',620,1600,110,0,3)])
    o+=title('LETTER LAND')+clouds(3,520)
    return page(o,'#e9c8ff')
def number():
    o='<div style="position:absolute;inset:0;background:linear-gradient(#9be7ff,#c4f1ff 35%,#e6fbff)"></div>'
    o+=ground2(480,('#b6f08a','#7dd65a','#4caf50'),PATH2)+pads(SPOTS2)
    o+=deco([('keycap_1',170,420,110,-12,3),('keycap_2',920,420,110,10,3),('keycap_3',860,620,120,6,3),('abacus',170,1020,150,0,3),('balloon',960,1000,110,8,3),('star',600,980,90,0,3),('glowing_star',150,1450,110,0,3),('red_apple',930,1500,100,0,3),('duck',990,1780,110,0,3),('banana',140,1780,110,-10,3),('soccer_ball',600,1620,100,0,3),('butterfly',430,1050,90,-10,3),('sunflower',990,1220,100,0,3)])
    o+=title('NUMBER LAND')+clouds(3,520)
    return page(o,'#c4f1ff')
def nature():
    o='<div style="position:absolute;inset:0;background:linear-gradient(#7fd6ff,#c8f0ff 35%,#e9ffd8)"></div>'
    o+='<div style="position:absolute;left:0;right:0;top:340px;height:240px;z-index:0;background:radial-gradient(ellipse at 20% 100%,#2f8f3f 0 40%,transparent 41%),radial-gradient(ellipse at 60% 100%,#3aa34a 0 45%,transparent 46%),radial-gradient(ellipse at 95% 100%,#2f8f3f 0 40%,transparent 41%)"></div>'
    o+=ground2(480,('#8ad35a','#4fb548','#2f8f3f'),PATH2)+pads(SPOTS2)
    o+=deco([('palm_tree',110,560,190,0,3),('palm_tree',980,520,170,0,3),('parrot',900,700,120,0,4),('elephant',870,1000,190,0,3),('zebra',170,1080,150,0,3),('evergreen_tree',600,960,110,0,3),('hibiscus',560,1100,80,0,3),('crocodile',250,1480,170,0,3),('hippopotamus',960,1520,150,0,3),('flamingo',100,1800,130,0,3),('butterfly',600,1450,80,10,3),('national_park',980,1800,120,0,3),('lion',560,1680,110,0,3),('honeybee',420,560,70,0,4)])
    o+=title('NATURE LAND')+clouds(3,480)
    return page(o,'#c8f0ff')
def worldland():
    o='<div style="position:absolute;inset:0;background:linear-gradient(#ffb347,#ffd27f 30%,#ffe9b8 45%)"></div>'
    o+='<div style="position:absolute;left:740px;top:380px;width:260px;height:260px;border-radius:50%;background:radial-gradient(circle,#fff3b0,#ffb800 70%);box-shadow:0 0 80px #ffd21f;z-index:0"></div>'
    o+=ground2(500,('#f2c46b','#d9a14a','#b77a2f'),PATH2)+pads(SPOTS2)
    o+=deco([('hut',150,620,170,0,3),('hut',930,700,150,0,3),('palm_tree',980,1000,160,0,3),('long_drum',150,1000,120,0,3),('maracas',600,1000,90,0,3),('world_map',180,1450,140,-6,3),('giraffe',980,1500,150,0,3),('cactus',560,1640,90,0,3),('hut',140,1790,120,0,3),('banjo',960,1800,110,-15,3),('ear_of_corn',600,1300,70,0,3),('mango',520,700,70,0,3)])
    o+=title('WORLD LAND')+clouds(2,480)
    return page(o,'#ffd27f')
async def main():
    os.makedirs(ART+'/out',exist_ok=True)
    jobs={'world-map':world(),'faith-land':faith(),'letter-land':letter(),'number-land':number(),'nature-land':nature(),'world-land':worldland()}
    async with async_playwright() as p:
        b=await p.chromium.launch();pg=await b.new_page(viewport={'width':W,'height':H})
        for k,html in jobs.items():
            fn=f'{ART}/out/{k}.html';open(fn,'w').write(html)
            await pg.goto('file://'+fn,wait_until='networkidle');await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'{ART}/out/{k}.png')
        await b.close()
    hs={k:[round(x/W*100,1),round(y/H*100,1)] for k,(x,y) in R.items()}
    json.dump({'world':hs,'spots4':[[round(x/W*100,1),round(y/H*100,1)] for x,y in SPOTS],'spots2':[[round(x/W*100,1),round(y/H*100,1)] for x,y in SPOTS2]},open(ART+'/out/hotspots.json','w'))
    print(hs)
asyncio.run(main())
