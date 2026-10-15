"""Study Land test (portrait 390x844 + 360x780): opens from the 6-land world map, every shelf from lands.json lists its
items with pictures, cards open with voice, Bible books open the reader and Back returns to the shelf; new map2 art is
swapped in only when listed in img/world/map2/ready.json. Then OFFLINE (after one online visit): every shelf, picture
and voice clip loads from the service worker.   usage: python3 tools/test_study.py [shots_dir]"""
import asyncio,threading,functools,http.server,sys,json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(sys.argv[1] if len(sys.argv)>1 else '/workspace/world6-shots');OUT.mkdir(parents=True,exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
    def handle(self):
        try:super().handle()
        except Exception:pass
fails=[]
def ok(c,m):
    print(('OK   ' if c else 'FAIL ')+m,flush=True)
    if not c:fails.append(m)
async def scr(pg,name):
    try:await pg.wait_for_function(f"screen==='{name}'",timeout=5000)
    except Exception:pass
    return await pg.evaluate('screen')
CHECK_SHELVES="""async()=>{const out=[];for(const s of LANDS.study.sections){go('ssec',{s:s.id});await new Promise(z=>setTimeout(z,150));
  document.querySelectorAll('img[data-src]').forEach(im=>{im.src=im.dataset.src;im.removeAttribute('data-src')});
  const imgs=[...document.querySelectorAll('.stile img')];await Promise.all(imgs.map(i=>i.complete?0:new Promise(z=>{i.onload=i.onerror=z})));
  const items=studyItems(s);const bad=imgs.filter(i=>!i.naturalWidth).map(i=>i.src);
  const vbad=[];for(const it of items)for(const t of (it.say||[])){try{const r=await fetch(voiceUrl(t));if(!r.ok)vbad.push(t)}catch(e){vbad.push(t)}}
  const big=[];for(const it of items){try{const r=await fetch(it.img);if(!r.ok)big.push(it.img)}catch(e){big.push(it.img)}}
  let iv=true;try{const r=await fetch(voiceUrl(s.intro));iv=r.ok}catch(e){iv=false}
  out.push({id:s.id,tiles:document.querySelectorAll('.stile').length,items:items.length,bad,vbad,big,intro:iv})}return out}"""
async def online(b,url,vw,vh):
    print(f'--- online {vw}x{vh}')
    ctx=await b.new_context(viewport={'width':vw,'height':vh},device_scale_factor=2,is_mobile=True,has_touch=True);pg=await ctx.new_page()
    errs=[];pg.on('pageerror',lambda e:errs.append(str(e)));pg.on('console',lambda m:m.type=='error' and errs.append(m.text))
    await pg.goto(url,wait_until='load');await pg.wait_for_function('LANDS!==null&&screen==="home"',timeout=15000)
    ok(await pg.evaluate("document.querySelectorAll('.w6 .wland').length")==6,f'{vw}: 6 lands on the world map')
    pos=await pg.evaluate("""()=>Object.fromEntries([...document.querySelectorAll('.w6land')].map(e=>{const r=e.getBoundingClientRect();return [e.dataset.l,[r.left+r.width/2,r.top+r.height/2,r.width]]}))""")
    ok(pos['number'][0]<pos['letter'][0]<pos['faith'][0] and max(pos[k][1] for k in ('number','letter','faith'))<pos['study'][1]<min(pos['nature'][1],pos['world'][1]) and pos['nature'][0]<pos['world'][0],f'{vw}: layout Number/Letter/Faith top, Study centre, Nature/World bottom')
    ok(pos['study'][2]>max(v[2] for k,v in pos.items() if k!='study'),f'{vw}: Study Land is the biggest island')
    fit=await pg.evaluate("(()=>{const r=document.querySelector('#wmap').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1})()");ok(fit,f'{vw}: map fits the screen width')
    await pg.screenshot(path=str(OUT/f'test-map-home-{vw}.png'))
    await pg.tap('.wsignb[data-l="study"]');ok(await scr(pg,'study')=='study',f'{vw}: Study Land opens from its sign')
    n=await pg.evaluate("document.querySelectorAll('.ssec').length");want=await pg.evaluate("LANDS.study.sections.length");ok(n==want==6,f'{vw}: {n} shelves (data has {want})')
    ok(not await pg.query_selector('.wquiz,.choices,.lnode'),f'{vw}: library has no games')
    await pg.wait_for_timeout(500);await pg.screenshot(path=str(OUT/f'test-study-land-{vw}.png'))
    await pg.tap('.ssec[data-s="animals"]');ok(await scr(pg,'ssec')=='ssec',f'{vw}: Animals shelf opens')
    await pg.wait_for_timeout(900);await pg.tap('.stile[data-i="0"]');await pg.wait_for_timeout(600)
    ok(await pg.is_visible('.spop .hero'),f'{vw}: animal card opens');ok('Lion' in (await pg.text_content('#bub')),f'{vw}: card speaks/shows the animal line')
    await pg.screenshot(path=str(OUT/f'test-section-animals-card-{vw}.png'))
    await pg.tap('#snext');await pg.wait_for_timeout(400);ok(await pg.is_visible('.spop'),f'{vw}: Next card');await pg.tap('#sdone')
    await pg.evaluate('emmaBack()');ok(await scr(pg,'study')=='study',f'{vw}: Back from shelf -> Study Land')
    await pg.tap('.ssec[data-s="bible"]');await scr(pg,'ssec');await pg.wait_for_timeout(500);await pg.tap('.stile[data-i="0"]')
    ok(await scr(pg,'reader')=='reader',f'{vw}: Bible book opens the reader');await pg.evaluate('emmaBack()')
    ok(await scr(pg,'ssec')=='ssec' and await pg.evaluate('state.sec')=='bible',f'{vw}: Back from reader -> Bible shelf')
    await pg.evaluate('emmaBack()');await pg.evaluate('emmaBack()');ok(await scr(pg,'home')=='home',f'{vw}: Back -> world map')
    if vw==390:
        await pg.tap('.wsignb[data-l="study"]');await scr(pg,'study');await pg.tap('.ssec[data-s="house"]');await scr(pg,'ssec');await pg.wait_for_timeout(1200)
        await pg.screenshot(path=str(OUT/'test-section-house-390.png'))
        g=await pg.evaluate("[...document.querySelectorAll('.sgrp')].map(e=>e.textContent)");ok(g==['Kitchen','Bedroom','Bathroom','Living Room'],f'house shelf grouped by room {g}')
        # map2 art swap: only files listed in ready.json are used; placeholders otherwise
        r=await pg.evaluate("""()=>{const a=m2('study-animals.jpg','PH');MAP2.add('study-animals.jpg');const b=m2('study-animals.jpg','PH');MAP2.delete('study-animals.jpg');return [a,b]}""")
        ready=json.load(open(ROOT/'img/world/map2/ready.json'))
        ok(r[1]=='img/world/map2/study-animals.jpg' and (r[0]=='PH' or 'study-animals.jpg' in ready),f'map2 art swap + placeholder fallback {r}')
        # adding a subject = one data entry
        c=await pg.evaluate("""()=>{LANDS.study.sections.push({id:'shapes',name:'Shapes',icon:'img/world/places/count.webp',source:'',intro:'Shapes!',items:[{name:'Star',img:'img/world/places/count.webp',say:['Star!']}]});go('study');return document.querySelectorAll('.ssec').length}""")
        ok(c==7,'a new subject shows from a data entry only');await pg.evaluate("LANDS.study.sections.pop();go('home')")
    ok(not errs,f'{vw}: no JS/console errors {errs[:3]}')
    await ctx.close()
async def offline(b,url):
    print('--- offline 412x915')
    ctx=await b.new_context(viewport={'width':412,'height':915},device_scale_factor=2,is_mobile=True,has_touch=True);pg=await ctx.new_page()
    net=[];on={'x':False};errs=[]
    pg.on('response',lambda r:on['x'] and r.url.startswith(url) and not r.from_service_worker and net.append(r.url));pg.on('pageerror',lambda e:errs.append(str(e)))
    await pg.goto(url,wait_until='load')
    info=await pg.evaluate("""async()=>{await navigator.serviceWorker.ready;const t0=Date.now();for(;;){const sw=await fetch('sw.js').then(r=>r.text());const want=JSON.parse(sw.match(/ASSETS=(\\[.*?\\]);/)[1]);
      let have=0;for(const k of (await caches.keys()).filter(k=>k.startsWith('emma-house-')))have+=(await (await caches.open(k)).keys()).length;
      if(have>=want.length&&navigator.serviceWorker.controller)return {have,want:want.length,ms:Date.now()-t0};if(Date.now()-t0>300000)return {timeout:true};await new Promise(z=>setTimeout(z,1000))}}""")
    print('  precache',info);ok(not info.get('timeout'),'precache finished')
    await ctx.set_offline(True);on['x']=True;await pg.reload(wait_until='load');await pg.wait_for_function('LANDS!==null&&screen==="home"',timeout=15000)
    await pg.tap('.wsignb[data-l="study"]');ok(await scr(pg,'study')=='study','offline: Study Land opens')
    res=await pg.evaluate(CHECK_SHELVES)
    for s in res:
        ok(s['tiles']==s['items']>0 and not s['bad'] and not s['big'],f"offline shelf {s['id']}: {s['tiles']} pictures load {s['bad'][:2]}{s['big'][:2]}")
        ok(not s['vbad'] and s['intro'],f"offline shelf {s['id']}: voice clips cached {s['vbad'][:2]}")
    ok(sum(s['items'] for s in res if s['id']=='house')==100,'house shelf has all 100 items')
    await pg.evaluate("go('ssec',{s:'flags'})");await pg.wait_for_timeout(800);await pg.screenshot(path=str(OUT/'test-section-flags-offline-412.png'))
    ok(not net,f'offline: no network requests {net[:3]}');ok(not errs,f'offline: no errors {errs[:3]}')
    await ctx.close()
async def main():
    srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Q,directory=str(ROOT)));threading.Thread(target=srv.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{srv.server_address[1]}/'
    async with async_playwright() as p:
        b=await p.chromium.launch()
        await online(b,url,390,844);await online(b,url,360,780);await offline(b,url);await b.close()
    print('STUDY TESTS '+('PASSED' if not fails else f'FAILED {len(fails)}: {fails}'));sys.exit(1 if fails else 0)
asyncio.run(main())
