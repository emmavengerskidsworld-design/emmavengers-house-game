"""Offline PWA test: python3 tools/test_offline.py [URL]  (default: serves repo on localhost).
Loads online, waits for full precache (core + background Bible-book prefetch), goes offline, reloads, plays every room/level + Bible story,
and checks that every image/voice request is served by the service worker."""
import sys,os,asyncio,threading,http.server,functools,json,re
from playwright.async_api import async_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def serve():
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*a):pass
    h=functools.partial(Q,directory=ROOT)
    s=http.server.ThreadingHTTPServer(('127.0.0.1',0),h);threading.Thread(target=s.serve_forever,daemon=True).start();return f'http://127.0.0.1:{s.server_port}/'
async def main(url):
    async with async_playwright() as p:
        b=await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        ctx=await b.new_context(viewport={'width':1180,'height':820});pg=await ctx.new_page()
        bad=[];stats={'sw':0,'net':0,'voice':0,'img':0};off={'on':False}
        def onresp(r):
            if off['on'] and r.url.startswith(url) and re.search(r'/(img|voice)/',r.url):
                stats['voice' if '/voice/' in r.url else 'img']+=1
                if r.from_service_worker: stats['sw']+=1
                else: stats['net']+=1
                if r.status>=400: bad.append((r.status,r.url))
        pg.on('response',onresp);pg.on('requestfailed',lambda r:bad.append(('FAIL',r.url,r.failure)));pg.on('pageerror',lambda e:bad.append(('PAGEERR',str(e))))
        await pg.goto(url,wait_until='networkidle')
        info=await pg.evaluate("""async()=>{await navigator.serviceWorker.ready;const t0=Date.now();
          const n=async()=>{const k=(await caches.keys()).filter(k=>k.startsWith('emma-house-'));let c=0;for(const x of k)c+=(await (await caches.open(x)).keys()).length;return [k,c]};
          for(;;){const r=await fetch('sw.js').then(r=>r.text());const want=JSON.parse(r.match(/ASSETS=(\\[.*?\\]);/)[1]).length;const [k,c]=await n();
            const man=await fetch('bible-manifest.json',{cache:'no-store'}).then(r=>r.json()).catch(()=>({books:{}}));const bk=(await (await caches.open('emma-books')).keys()).map(r=>r.url);const booksReady=Object.entries(man.books).every(([s,b])=>bk.some(u=>u.includes('/__book__/'+s+'/'+b.v+'/')));
            if(c>=want&&navigator.serviceWorker.controller&&booksReady)return {caches:k,entries:c,want,ms:Date.now()-t0,quota:(await navigator.storage.estimate()).usage};
            if(Date.now()-t0>240000)return {timeout:true,c,want};await new Promise(z=>setTimeout(z,1000))}}""")
        print('precache',json.dumps(info))
        await ctx.set_offline(True);off['on']=True;await pg.reload(wait_until='load');await pg.wait_for_timeout(800)
        await pg.evaluate('localStorage.clear()')
        played=[]
        await pg.evaluate("""()=>{const o=say;window.__said=[];say=function(t,h,q){__said.push(t);return o(t,h,q)};
          const op=HTMLMediaElement.prototype.play;window.__pl={ok:0,err:0};HTMLMediaElement.prototype.play=function(){return op.call(this).then(()=>__pl.ok++).catch(e=>{if(e.name!=='AbortError')__pl.err++;throw e})}}""")
        for room in ['kitchen','bedroom','bathroom','living room']:
            for lv in [1,2,3,4]:
                await pg.evaluate("([r,l])=>{for(let i=1;i<l;i++)levelSet(r,i,3)}",[room,lv])
                await pg.evaluate("()=>go('home')");await pg.wait_for_timeout(200)
                await pg.click(f'.room[data-k="{room}"]');await pg.wait_for_timeout(500)
                await pg.click(f'.lnode[data-l="{lv}"]');await pg.wait_for_timeout(900)
                if await pg.query_selector('.mode'):await pg.click('.mode');await pg.wait_for_timeout(700)
                broken=await pg.evaluate("()=>[...document.images].filter(i=>i.complete&&!i.naturalWidth).map(i=>i.src)")
                imgs=await pg.evaluate("()=>[...document.images].filter(i=>i.naturalWidth).length")
                played.append((room,lv,imgs,len(broken)));bad+= [('BROKENIMG',x) for x in broken]
        await pg.evaluate("()=>go('home')");await pg.click('.room[data-k="bible"]');await pg.wait_for_timeout(700)
        await pg.click('.book[data-b]');await pg.wait_for_timeout(1200)
        pages=0
        while True:
            if not await pg.query_selector('#bnext'):break
            bi=await pg.evaluate("()=>[...document.images].filter(i=>i.complete&&!i.naturalWidth).length");pages+=1
            if bi:bad.append(('BIBLEIMG',pages))
            await pg.click('#bnext');await pg.wait_for_timeout(1300)
        await pg.wait_for_timeout(1500)
        pl=await pg.evaluate('__pl')
        print('offline screens (room,level,images ok,broken):',played)
        print('bible pages turned:',pages,'| audio play ok/err:',pl,'| requests:',stats)
        print('problems:',bad[:10],len(bad));await b.close();return 0 if not bad and pl['err']==0 and stats['net']==0 else 1
url=sys.argv[1] if len(sys.argv)>1 else serve()
sys.exit(asyncio.run(main(url)))
