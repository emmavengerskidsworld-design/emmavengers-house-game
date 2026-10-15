"""Emmavengers World test (portrait phones 390x844 + 412x915):  python3 tools/test_world.py [shots_dir]
World map home -> every land -> Faith Land links (House / Bible / Mia) -> each activity played to the end,
no horizontal overflow, no JS errors, Back to Map / header back / Android emmaBack / browser history back,
then one online visit -> offline reload -> world map + lands + activities still load from the service worker."""
import asyncio,threading,functools,http.server,sys,json,os
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(sys.argv[1] if len(sys.argv)>1 else '/workspace/world-shots');OUT.mkdir(parents=True,exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
    def handle(self):
        try:super().handle()
        except Exception:pass
CHECK="""()=>{const W=innerWidth,bad=[];document.querySelectorAll('button,.btn,img,h1,h2,.prompt,.wmap,.wsign,.wcard').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||getComputedStyle(e).visibility=='hidden')return;if(r.left<-2||r.right>W+2)bad.push((e.id||e.className||e.tagName)+' x:'+Math.round(r.left)+'-'+Math.round(r.right))});
 const m=document.querySelector('#wmap');const mb=m?m.getBoundingClientRect():null;
 return {sw:document.documentElement.scrollWidth,W,bad:bad.slice(0,6),mapBottom:mb?Math.round(mb.bottom):0,H:innerHeight,broken:[...document.images].filter(i=>i.complete&&!i.naturalWidth).map(i=>i.src)}}"""
fails=[];log=print
def ok(c,msg):
    if not c: fails.append(msg); log('  FAIL',msg)
async def wait_scr(pg,name,t=4000):
    try: await pg.wait_for_function(f"screen==='{name}'",timeout=t)
    except Exception: pass
    return await pg.evaluate('screen')
async def check(pg,tag,shot=None):
    r=await pg.evaluate(CHECK)
    ok(r['sw']<=r['W']+1 and not r['bad'],f'{tag}: overflow {r["bad"]} sw={r["sw"]}')
    ok(not r['broken'],f'{tag}: broken images {r["broken"][:3]}')
    if r['mapBottom']: ok(r['mapBottom']<=r['H']+1,f'{tag}: map runs off screen ({r["mapBottom"]}>{r["H"]})')
    if shot: await pg.screenshot(path=str(OUT/shot))
    return r
async def play_quiz(pg,tag):
    for _ in range(12):
        if await pg.evaluate("screen")=='wreward':break
        await pg.wait_for_selector('[data-ok="1"]:not([disabled])',timeout=5000)
        await pg.click('[data-ok="1"]');await pg.wait_for_function("screen==='wreward'||!document.querySelector('[data-ok=\"1\"][disabled]')",timeout=8000)
    ok(await pg.evaluate("screen")=='wreward',f'{tag}: quiz did not reach reward')
async def run(b,url,vw,vh):
    log(f'--- {vw}x{vh}')
    ctx=await b.new_context(viewport={'width':vw,'height':vh},device_scale_factor=2,is_mobile=True,has_touch=True);pg=await ctx.new_page()
    errs=[];pg.on('pageerror',lambda e:errs.append('PAGEERR '+str(e)));pg.on('console',lambda m:m.type=='error' and errs.append('CONSOLE '+m.text))
    await pg.goto(url,wait_until='networkidle');await pg.evaluate('localStorage.clear()');await pg.reload(wait_until='networkidle')
    await pg.wait_for_function('LANDS!==null&&screen==="home"',timeout=10000)
    ok(await pg.title()=='Emmavengers World','document title'); ok((await pg.text_content('#title')).strip()=='Emmavengers World','header title')
    ok(await pg.is_visible('#parentBtn'),"Parents' Corner button on world home")
    n=await pg.evaluate("document.querySelectorAll('.wland').length");ok(n==5,f'5 lands on map (got {n})')
    await check(pg,'world map',f'world-map-{vw}.png')
    # every land opens its inner map with Back to Map
    for L in ['faith','letter','number','nature','world']:
        await pg.click(f'.wsignb[data-l="{L}"]');s=await wait_scr(pg,'land');ok(s=='land',f'{L}: land opens')
        ok(await pg.is_visible('#wback'),f'{L}: Back to Map visible')
        await check(pg,f'land {L}',f'{L}-land-{vw}.png')
        await pg.click('#wback');ok(await wait_scr(pg,'home')=='home',f'{L}: Back to Map returns home')
    # Faith Land links into the existing game
    await pg.click('.wsignb[data-l="faith"]');await wait_scr(pg,'land')
    for place,scr in [('house','house'),('bible','bible'),('mia','morning')]:
        await pg.click(f'.wplace[data-p="{place}"]');s=await wait_scr(pg,scr);ok(s==scr,f'Faith Land {place} -> {scr} (got {s})')
        if place=='house':
            await check(pg,'house',f'house-{vw}.png')
            await pg.click('.room[data-k="kitchen"]');ok(await wait_scr(pg,'levelmap')=='levelmap','house -> kitchen level map')
            await pg.go_back();ok(await wait_scr(pg,'house')=='house','browser back: level map -> house')
            await pg.go_back();ok(await wait_scr(pg,'land')=='land','browser back: house -> Faith Land')
        elif place=='bible':
            await pg.evaluate('emmaBack()');ok(await wait_scr(pg,'land')=='land','emmaBack: Bible -> Faith Land')
        else:
            await pg.wait_for_timeout(600);await pg.click('#backBtn');ok(await wait_scr(pg,'land')=='land','header back: Mia -> Faith Land')
    await pg.click('.wplace[data-p="prayer"]');await wait_scr(pg,'wcards');await pg.click('.wtile[data-i="0"]');await pg.wait_for_selector('.wcard')
    await check(pg,'prayer card',f'prayer-{vw}.png');await pg.click('#wdone')
    await pg.go_back();ok(await wait_scr(pg,'land')=='land','browser back: Prayer Corner -> Faith Land')
    await pg.go_back();ok(await wait_scr(pg,'home')=='home','browser back: Faith Land -> world map')
    st=await pg.evaluate('history.state');ok(st and st.get('emma')=='root',f'at map the next back leaves the app (state {st})')
    # Letter Land: ABC cards + Letter Hunt
    await pg.click('.wsignb[data-l="letter"]');await wait_scr(pg,'land');await pg.click('.wplace[data-p="abc"]');await wait_scr(pg,'wcards')
    await check(pg,'abc grid',f'abc-grid-{vw}.png')
    s0=await pg.evaluate('stars');await pg.click('.wtile[data-i="0"]');await pg.wait_for_selector('.wcard img.hero')
    await pg.wait_for_timeout(700);await check(pg,'abc card A',f'abc-activity-{vw}.png')
    ok(await pg.evaluate('stars')==s0+1,'first look at a letter gives a star')
    ok('Apple' in await pg.text_content('.wcard'),'A card says Apple')
    for i in range(25): await pg.click('#wnext');await pg.wait_for_timeout(40)
    ok(await pg.evaluate("JSON.parse(localStorage.emmaWorld).seen.letters.length")==26,'all 26 letters seen')
    ok(await pg.evaluate("document.querySelectorAll('.wtile.seen').length")==26,'26 tiles starred')
    await pg.click('#wdone');await pg.click('#backBtn');await wait_scr(pg,'land')
    await pg.click('.wplace[data-p="hunt"]');await wait_scr(pg,'wquiz');await check(pg,'letter hunt',f'letter-hunt-{vw}.png');await play_quiz(pg,'letter hunt')
    await check(pg,'reward',f'reward-{vw}.png');await pg.click('#tomap');ok(await wait_scr(pg,'land')=='land','reward Back to Map -> land')
    st=await pg.text_content('.wplace[data-p="hunt"]');ok('⭐' in st,'best stars shown on the place')
    await pg.click('#wback');await wait_scr(pg,'home')
    # Number Land: counting game
    await pg.click('.wsignb[data-l="number"]');await wait_scr(pg,'land');await pg.click('.wplace[data-p="count"]');await wait_scr(pg,'wcount')
    await check(pg,'count',f'count-{vw}.png')
    for r in range(8):
        await pg.wait_for_selector('.wobj',timeout=5000);n=await pg.evaluate("document.querySelectorAll('.wobj').length")
        for i in range(n): await pg.click(f'.wobj >> nth={i}')
        ok(await pg.evaluate("document.querySelectorAll('.wobj.counted').length")==n,'tap-to-count marks every object')
        await pg.click(f'.wn[data-n="{n}"]');await pg.wait_for_function(f"screen==='wreward'||document.querySelectorAll('.wn[disabled]').length===0",timeout=8000)
    ok(await wait_scr(pg,'wreward')=='wreward','counting reaches reward')
    await pg.click('#tomap');await wait_scr(pg,'land');await pg.click('#wback');await wait_scr(pg,'home')
    # Nature Land: animal cards + quiz
    await pg.click('.wsignb[data-l="nature"]');await wait_scr(pg,'land');await pg.click('.wplace[data-p="safari"]');await wait_scr(pg,'wcards')
    await pg.click('.wtile[data-i="2"]');await pg.wait_for_selector('.wcard .fact');ok('tallest' in await pg.text_content('.wcard .fact'),'giraffe fun fact');await check(pg,'animal card',f'animal-card-{vw}.png');await pg.click('#wdone')
    await pg.click('#backBtn');await wait_scr(pg,'land');await pg.click('.wplace[data-p="animalquiz"]');await wait_scr(pg,'wquiz');await play_quiz(pg,'animal quiz')
    await pg.click('#tomap');await wait_scr(pg,'land');await pg.click('#wback');await wait_scr(pg,'home')
    # World Land: country cards + flag quiz
    await pg.click('.wsignb[data-l="world"]');await wait_scr(pg,'land');await pg.click('.wplace[data-p="countries"]');await wait_scr(pg,'wcards')
    await pg.click('.wtile[data-i="0"]');await pg.wait_for_selector('.wcard .greet');ok('Bonjour' in await pg.text_content('.wcard'),'Cameroon greeting');await check(pg,'country card',f'country-card-{vw}.png');await pg.click('#wdone')
    await pg.click('#backBtn');await wait_scr(pg,'land');await pg.click('.wplace[data-p="flagquiz"]');await wait_scr(pg,'wquiz');await check(pg,'flag quiz',f'flag-quiz-{vw}.png');await play_quiz(pg,'flag quiz')
    await pg.click('#tomap');await wait_scr(pg,'land')
    # Android back chain from an activity: activity -> land -> map -> exit
    await pg.click('.wplace[data-p="countries"]');await wait_scr(pg,'wcards')
    ok(await pg.evaluate('emmaBack()') is True and await wait_scr(pg,'land')=='land','emmaBack activity -> land')
    ok(await pg.evaluate('emmaBack()') is True and await wait_scr(pg,'home')=='home','emmaBack land -> map')
    ok(await pg.evaluate('emmaBack()') is False,'emmaBack on map lets the app exit')
    real=[e for e in errs]
    ok(not real,f'JS/console errors: {real[:5]}')
    await ctx.close()
async def offline(b,url):
    log('--- offline (412x915)')
    ctx=await b.new_context(viewport={'width':412,'height':915},device_scale_factor=2,is_mobile=True,has_touch=True);pg=await ctx.new_page()
    net=[];errs=[];on={'x':False}
    pg.on('response',lambda r:on['x'] and r.url.startswith(url) and not r.from_service_worker and net.append(r.url))
    pg.on('pageerror',lambda e:errs.append(str(e)))
    await pg.goto(url,wait_until='networkidle')
    info=await pg.evaluate("""async()=>{await navigator.serviceWorker.ready;const t0=Date.now();for(;;){const sw=await fetch('sw.js').then(r=>r.text());const want=JSON.parse(sw.match(/ASSETS=(\\[.*?\\]);/)[1]);
      let have=0;const ks=(await caches.keys()).filter(k=>k.startsWith('emma-house-'));for(const k of ks)have+=(await (await caches.open(k)).keys()).length;
      if(have>=want.length&&navigator.serviceWorker.controller)return {have,want:want.length,world:want.filter(u=>/world|lands\\.json|fonts/.test(u)).length,ms:Date.now()-t0};
      if(Date.now()-t0>300000)return {timeout:true,have,want:want.length};await new Promise(z=>setTimeout(z,1000))}}""")
    log('  precache',info);ok(not info.get('timeout'),'precache finished')
    await ctx.set_offline(True);on['x']=True;await pg.reload(wait_until='load')
    await pg.wait_for_function('LANDS!==null&&screen==="home"',timeout=10000)
    res=await pg.evaluate("""async()=>{const bad=[];const chk=async u=>{try{const r=await fetch(u);if(!r.ok)bad.push(u)}catch(e){bad.push(u)}};await chk(LANDS.world.img);
      for(const L of LANDS.lands){go('land',{id:L.id});await new Promise(z=>setTimeout(z,250));await chk(L.img);for(const p of L.places){await chk(p.icon);if(p.type==='link')continue;
        go(p.type==='cards'?'wcards':p.type==='quiz'?'wquiz':'wcount',{l:L.id,p:p.id});await new Promise(z=>setTimeout(z,450));[...document.images].filter(i=>i.complete&&!i.naturalWidth).forEach(i=>bad.push(i.src))}}
      for(const d of Object.values(LANDS.decks))for(const it of d.items)for(const k of ['img','flag','foodImg'])if(it[k])await chk(it[k]);
      for(const t of __worldVoice())await chk(voiceUrl(t));go('home');return {bad,voice:__worldVoice().length}}""")
    await pg.wait_for_timeout(500);await pg.screenshot(path=str(OUT/'world-map-offline-412.png'))
    log('  offline world check:',res['voice'],'voice lines; problems',res['bad'][:5]);ok(not res['bad'],f'offline assets missing {res["bad"][:5]}')
    ok(not net,f'offline requests hit network {net[:3]}');ok(not errs,f'offline errors {errs[:3]}')
    await ctx.close()
async def main():
    srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Q,directory=str(ROOT)));port=srv.server_address[1];threading.Thread(target=srv.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{port}/'
    async with async_playwright() as p:
        b=await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for vw,vh in [(390,844),(412,915)]: await run(b,url,vw,vh)
        if '--no-offline' not in sys.argv: await offline(b,url)
        await b.close()
    print('screenshots in',OUT);print('WORLD TESTS','PASSED' if not fails else f'FAILED ({len(fails)})');sys.exit(1 if fails else 0)
asyncio.run(main())
