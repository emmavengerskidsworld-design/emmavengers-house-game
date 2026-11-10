"""Check the deployed preview site (online + offline, Cameroon opens, data identical to pre-Stage-1):  python3 tools/verify_preview.py"""
import asyncio,json,sys
from playwright.async_api import async_playwright
U='https://emmavengerskidsworld-design.github.io/emmavengers-world-preview/'
import os;F=os.path.join(os.path.dirname(os.path.abspath(__file__)),'fixtures','legacy-v0')+'/'
res=[]
def ok(c,m): res.append(c); print(('ok   ' if c else 'FAIL ')+m)
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch();ctx=await b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True);pg=await ctx.new_page();errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)));pg.on('console',lambda m:m.type=='error' and errs.append(m.text))
    await pg.goto(U,wait_until='load');await pg.wait_for_function('typeof LANDS!=="undefined"&&LANDS!==null&&screen==="home"&&window.CTRY_READY',timeout=60000)
    st=await pg.evaluate('EWLib.status()');ok(st['ready'] and st['source']=='network',f"online first visit: release {st['sequence']}, {len(st['fetched'])} files, {st['bytes']/1024:.0f} KB, storage {st['storage']}")
    L=json.loads(await pg.evaluate('JSON.stringify(LANDS)'));ok(L==json.load(open(F+'lands.json')),'LANDS identical to the pre-Stage-1 lands.json')
    pk=json.loads(await pg.evaluate('JSON.stringify(CT.packs.cameroon)'));ok(pk==json.load(open(F+'cameroon.json')),'Cameroon pack identical to the original')
    await pg.evaluate("go('land',{id:'world'})");await pg.wait_for_timeout(800)
    await pg.click('.wplace[data-p="cameroon"]');await pg.wait_for_timeout(1500)
    s=await pg.evaluate('screen');t=await pg.evaluate('document.querySelector("#main")?document.querySelector("#main").innerText.slice(0,120):document.body.innerText.slice(0,120)')
    ok(s in('ctry',) or 'Cameroon' in t,f'online: Cameroon opens (screen {s}: {t[:60]!r})');await pg.screenshot(path='/tmp/live-cameroon-online.png')
    info=await pg.evaluate("""async()=>{await navigator.serviceWorker.ready;const t0=Date.now();for(;;){const sw=await fetch('sw.js').then(r=>r.text());const want=JSON.parse(sw.match(/ASSETS=(\\[.*?\\]);/)[1]);
      let have=0;for(const k of (await caches.keys()).filter(k=>k.startsWith('emma-house-')))have+=(await (await caches.open(k)).keys()).length;
      if(have>=want.length&&navigator.serviceWorker.controller)return {have,want:want.length,s:(Date.now()-t0)/1000};if(Date.now()-t0>600000)return {timeout:true,have,want:want.length};await new Promise(z=>setTimeout(z,2000))}}""")
    ok(not info.get('timeout'),f'service worker precache complete {info}')
    await ctx.set_offline(True);await pg.reload(wait_until='load')
    await pg.wait_for_function('typeof LANDS!=="undefined"&&LANDS!==null&&screen==="home"&&window.CTRY_READY',timeout=30000)
    st=await pg.evaluate('EWLib.status()');ok(st['source']=='device' and not st['fetched'],f"OFFLINE reload: content from device copy, release {st['sequence']}")
    await pg.evaluate("go('land',{id:'world'})");await pg.wait_for_timeout(800);await pg.click('.wplace[data-p="cameroon"]');await pg.wait_for_timeout(1500)
    s=await pg.evaluate('screen');ok(s=='ctry',f'OFFLINE: Cameroon opens (screen {s})');await pg.screenshot(path='/tmp/live-cameroon-offline.png')
    ok(not errs,f'no page errors {errs[:3]}')
    await b.close()
asyncio.run(main());print('LIVE VERIFY','PASSED' if all(res) else 'FAILED');sys.exit(0 if all(res) else 1)
