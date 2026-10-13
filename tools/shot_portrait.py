"""Portrait screenshot pass + overflow check for phones."""
import asyncio,threading,functools,http.server,sys,json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(sys.argv[1] if len(sys.argv)>1 else '/workspace/app/portrait');OUT.mkdir(parents=True,exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
    def handle(self):
        try:super().handle()
        except Exception:pass
SCREENS=[('home',"go('home')"),('levelmap',"state.room='kitchen';go('levelmap')"),('learn1',"state.room='kitchen';startLevel(1)"),('find2',"state.room='kitchen';startLevel(2)"),('used3',"state.room='bedroom';startLevel(3)"),('settable',"state.room='kitchen';startLevel(4)"),('bedhunt',"state.room='bedroom';startLevel(4)"),('bubbles',"state.room='bathroom';startLevel(4)"),('tidy',"state.room='living room';startLevel(4)"),('bible',"go('bible')"),('reader',"go('reader',{b:'noah',i:1})"),('reader5',"go('reader',{b:'noah',i:5})"),('morning',"go('morning')"),('mstep',"go('mstep',{i:0})"),('mstep3',"go('mstep',{i:3})")]
CHECK="""()=>{const W=innerWidth,H=innerHeight,bad=[];document.querySelectorAll('button,.btn,img,video,h1,h2,.prompt,.nm').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||getComputedStyle(e).visibility=='hidden')return;if(r.left<-2||r.right>W+2)bad.push((e.id||e.className||e.tagName)+' x:'+Math.round(r.left)+'-'+Math.round(r.right))});return {sw:document.documentElement.scrollWidth,W,bad:bad.slice(0,6)}}"""
async def main():
    srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Q,directory=str(ROOT)));port=srv.server_address[1];threading.Thread(target=srv.serve_forever,daemon=True).start()
    errs=[];rep={}
    async with async_playwright() as p:
        b=await p.chromium.launch()
        for vw,vh in [(390,844),(412,915)]:
            ctx=await b.new_context(viewport={'width':vw,'height':vh},device_scale_factor=2,is_mobile=True,has_touch=True);pg=await ctx.new_page()
            pg.on('pageerror',lambda e:errs.append(str(e)))
            await pg.goto(f'http://127.0.0.1:{port}/',wait_until='networkidle')
            for name,arg in SCREENS:
                s=name
                try:
                    await pg.evaluate(f"()=>{{document.querySelectorAll('#vpanel,#ppanel').forEach(x=>x.remove());{arg}}}")
                except Exception as e: errs.append(f'{name}:{e}');continue
                await pg.wait_for_timeout(1500 if s.startswith('m') else 500)
                rep[f'{vw}-{name}']=await pg.evaluate(CHECK)
                await pg.screenshot(path=str(OUT/f'{vw}-{name}.png'))
            await pg.evaluate("go('home')");await pg.click('#voiceBtn');await pg.wait_for_timeout(300);rep[f'{vw}-voice']=await pg.evaluate(CHECK);await pg.screenshot(path=str(OUT/f'{vw}-voice.png'))
            await pg.evaluate("document.querySelector('#vpanel').remove()");await pg.click('#parentBtn');await pg.wait_for_timeout(300);rep[f'{vw}-parents']=await pg.evaluate(CHECK);await pg.screenshot(path=str(OUT/f'{vw}-parents.png'))
            await ctx.close()
    bad={k:v for k,v in rep.items() if v['sw']>v['W']+1 or v['bad']}
    print(json.dumps(bad,indent=0)[:3000]);print('errors',errs[:5]);print('PORTRAIT OK' if not bad and not errs else 'PORTRAIT ISSUES')
asyncio.run(main())
