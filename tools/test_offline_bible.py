"""Offline Bible Library test:  python3 tools/test_offline_bible.py [URL] [--books noah,creation]
One online visit -> waits for core precache AND background prefetch of every Bible book (bible-manifest.json),
then goes fully offline, reloads, opens Home, the Bible Library, and reads each chosen book cover-to-end
(pages + narration), then answers its quiz. Passes only if every image/voice came from the service worker."""
import sys,os,asyncio,threading,http.server,functools,json,re
from playwright.async_api import async_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def serve():
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*a):pass
    h=functools.partial(Q,directory=ROOT)
    s=http.server.ThreadingHTTPServer(('127.0.0.1',0),h);threading.Thread(target=s.serve_forever,daemon=True).start();return f'http://127.0.0.1:{s.server_port}/'
async def main(url,want_books):
    async with async_playwright() as p:
        b=await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        ctx=await b.new_context(viewport={'width':1180,'height':820});pg=await ctx.new_page()
        bad=[];stats={'sw':0,'net':0,'voice':0,'img':0};phase={'off':False}
        def onresp(r):
            if phase['off'] and r.url.startswith(url) and re.search(r'/(img|voice)/',r.url):
                stats['voice' if '/voice/' in r.url else 'img']+=1
                if r.from_service_worker: stats['sw']+=1
                else: stats['net']+=1
                if r.status>=400: bad.append((r.status,r.url))
        pg.on('response',onresp)
        pg.on('requestfailed',lambda r:phase['off'] and bad.append(('FAIL',r.url,r.failure)));pg.on('pageerror',lambda e:bad.append(('PAGEERR',str(e))))
        await pg.goto(url,wait_until='networkidle')
        info=await pg.evaluate("""async()=>{await navigator.serviceWorker.ready;const t0=Date.now();
          const man=await fetch('bible-manifest.json',{cache:'no-store'}).then(r=>r.json());
          for(;;){const sw=await fetch('sw.js').then(r=>r.text());const want=JSON.parse(sw.match(/ASSETS=(\\[.*?\\]);/)[1]).length;
            let core=0;for(const k of (await caches.keys()).filter(k=>k.startsWith('emma-house-')))core+=(await (await caches.open(k)).keys()).length;
            const bc=await caches.open('emma-books');const keys=(await bc.keys()).map(r=>r.url);
            const ready=Object.entries(man.books).filter(([s,b])=>keys.some(u=>u.includes('/__book__/'+s+'/'+b.v+'/'))).map(([s])=>s);
            if(core>=want&&navigator.serviceWorker.controller&&ready.length===Object.keys(man.books).length)
              return {core,want,books:ready,bookEntries:keys.length,ms:Date.now()-t0,usageMB:Math.round((await navigator.storage.estimate()).usage/1e5)/10};
            if(Date.now()-t0>420000)return {timeout:true,core,want,ready};await new Promise(z=>setTimeout(z,1000))}}""")
        print('online visit:',json.dumps(info))
        if info.get('timeout'): bad.append(('TIMEOUT',info))
        await ctx.set_offline(True);phase['off']=True;await pg.reload(wait_until='load');await pg.wait_for_timeout(900)
        await pg.evaluate("""()=>{const o=say;window.__said=[];say=function(t,h,q){__said.push(t);return o(t,h,q)};
          window.__pl={ok:0,err:0};const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){return op.call(this).then(()=>__pl.ok++).catch(e=>{if(e.name!=='AbortError')__pl.err++;throw e})};
          if(window.AudioBufferSourceNode){const os=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(){if(this.__src)__pl.ok++;return os.apply(this,arguments)}}}""")
        lands=await pg.evaluate("()=>document.querySelectorAll('.wland').length");print('offline home (world map): lands shown',lands)
        if not lands: bad.append(('HOME','no lands'))
        await pg.click('.wsignb[data-l="faith"]');await pg.wait_for_timeout(600)
        await pg.click('.wplace[data-p="bible"]');await pg.wait_for_timeout(800)
        shelf=await pg.evaluate("()=>[...document.querySelectorAll('.book[data-b]')].map(e=>[e.dataset.b,e.querySelector('img').naturalWidth>0])")
        print('offline library shelf:',shelf); bad+=[('COVER',k) for k,ok in shelf if not ok]
        books=want_books or [k for k,_ in shelf]
        for bk in books:
            await pg.evaluate("()=>go('bible')");await pg.wait_for_timeout(400)
            await pg.click(f'.book[data-b="{bk}"]');await pg.wait_for_timeout(1200)
            pages=0;pl0=await pg.evaluate('__pl.ok')
            while await pg.query_selector('#bnext'):
                ok=await pg.evaluate("()=>{const i=document.querySelector('#bimg');return i.complete&&i.naturalWidth>0}");pages+=1
                if not ok: bad.append(('PAGEIMG',bk,pages))
                await pg.wait_for_timeout(900);await pg.click('#bnext');await pg.wait_for_timeout(500)
            q=0
            while await pg.query_selector('.opt[data-a="1"]') and q<5:
                await pg.wait_for_timeout(700);await pg.click('.opt[data-a="1"]');await pg.wait_for_timeout(1800);q+=1
            done=await pg.evaluate("()=>!!document.querySelector('.reward')")
            pl=await pg.evaluate('__pl.ok')
            print(f'offline book {bk}: pages {pages}, quiz answered {q}, reward {done}, voice clips played {pl-pl0}')
            if pl-pl0<3: bad.append(('NOVOICE',bk))
            if not done: bad.append(('NODONE',bk))
        pl=await pg.evaluate('__pl')
        print('audio ok/err:',pl,'| offline requests:',stats)
        print('problems:',bad[:10],len(bad));await b.close()
        return 0 if not bad and pl['err']==0 and stats['net']==0 else 1
args=[a for a in sys.argv[1:] if not a.startswith('--')]
wb=None
if '--books' in sys.argv: wb=sys.argv[sys.argv.index('--books')+1].split(',');args=[a for a in args if a!=sys.argv[sys.argv.index('--books')+1]]
url=args[0] if args else serve()
r=asyncio.run(main(url,wb));print('RESULT','PASS' if r==0 else 'FAIL');sys.exit(r)
