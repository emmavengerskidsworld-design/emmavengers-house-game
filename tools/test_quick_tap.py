"""Quick-tap test: open screens, wait 1 s, tap answers/cards fast; each tap's voice must start <=150 ms,
and parts of multi-part lines must follow with gaps <=120 ms.
usage: python3 tools/test_quick_tap.py URL   (serve repo e.g. with tools/throttle_server.py <repo> 8602 0)"""
import asyncio,sys,json
from playwright.async_api import async_playwright
sys.argv+=[] ;URL=sys.argv[1]
INIT=open(__file__.replace('test_quick_tap.py','test_voice_latency.py')).read().split('INIT="""')[1].split('"""')[0]
async def tap_measure(pg,sel,idx=0):
    await pg.evaluate('__ev=[]')
    els=await pg.query_selector_all(sel)
    if len(els)<=idx: return None,'missing '+sel
    await els[idx].click()
    for _ in range(60):
        r=await pg.evaluate('(()=>{const e=__ev.find(x=>x.t>=__t0);return e?e.t-__t0:null})()')
        if r is not None: return round(r),''
        await pg.wait_for_timeout(25)
    return None,'no audio 1.5s'
async def gaps(pg,ms):
    await pg.wait_for_timeout(ms)
    return await pg.evaluate('(()=>{const b=__ev.filter(x=>x.t>=__t0&&(x.k==="buf"||x.k==="el")&&x.end).sort((a,c)=>a.t-c.t);const g=[];for(let i=1;i<b.length;i++)if(b[i].sid===b[i-1].sid)g.push(Math.round(b[i].t-b[i-1].end));return g})()')
async def main():
    fails=[];res=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(args=['--autoplay-policy=user-gesture-required'])
        ctx=await b.new_context(**p.devices['Pixel 7']);await ctx.add_init_script(INIT);pg=await ctx.new_page()
        await pg.goto(URL,wait_until='load')
        if '--cold' not in sys.argv:  # installed-app state: let the service worker finish its first precache, then reopen
            await pg.wait_for_function('navigator.serviceWorker&&navigator.serviceWorker.controller',timeout=120000);await pg.wait_for_timeout(15000);await pg.reload(wait_until='load')
        await pg.wait_for_timeout(3000);await pg.evaluate("(()=>{const o=window.say;window.__sid=0;window.say=function(){window.__sid++;return o.apply(this,arguments)}})()");await pg.tap('#title');await pg.wait_for_timeout(500)
        async def step(name,sel,idx=0,wait=1000,check=True):
            ms,err=await tap_measure(pg,sel,idx);res.append((name,ms,err));print(name,ms,err,flush=True)
            if check and (ms is None or ms>150):fails.append(f'{name}: {ms} {err}')
            await pg.wait_for_timeout(wait)
        # world map -> Letter Land -> ABC cards: rapid card taps
        await step('Letter Land sign','.wsignb[data-l="letter"]',check=False)
        await step('ABC Sounds','.wplace[data-p="abc"]',check=False)
        for i in range(5):
            await pg.evaluate("document.querySelectorAll('.pop').forEach(x=>x.remove())")
            await step(f'Card {i}','.wtile',i,wait=350)
        g=await gaps(pg,2500);print('card multi-part gaps',g);res.append(('gaps',g,''))
        if any(x>120 for x in g):fails.append(f'gap>120ms {g}')
        await pg.evaluate("document.querySelectorAll('.pop').forEach(x=>x.remove());emmaBack()");await pg.wait_for_timeout(600)
        # quiz: tap wrong answers quickly then right
        await step('Letter quiz place','.wplace[data-p]',1,check=False)
        n=await pg.evaluate("document.querySelectorAll('[data-ok]').length")
        for i in range(n):
            ok=await pg.evaluate(f"document.querySelectorAll('[data-ok]')[{i}].dataset.ok")
            if ok=='0': await step(f'Wrong answer {i}','[data-ok]',i,wait=400)
        await step('Right answer','[data-ok="1"]',0,wait=400)
        g=await gaps(pg,3000);print('praise multi-part gaps',g);res.append(('gaps2',g,''))
        if any(x>120 for x in g):fails.append(f'gap>120ms {g}')
        await b.close()
    json.dump(res,open('/tmp/emma-quicktap.json','w'))
    print('FAILS',fails) if fails else print('QUICKTAP PASS')
    sys.exit(1 if fails else 0)
asyncio.run(main())
