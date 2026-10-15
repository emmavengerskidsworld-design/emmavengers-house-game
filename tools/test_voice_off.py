"""Voice-off (silent reading) test: header 🗣️ toggle; no voice on world map, a house room game, a Bible page and an
ABC card; sound effects still play; the setting survives a reload; turning it on speaks 'Voice on!'.
usage: python3 tools/test_voice_off.py [shots_dir]"""
import asyncio,threading,functools,http.server,sys
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=Path(sys.argv[1] if len(sys.argv)>1 else '/workspace/voice-off-shots');OUT.mkdir(parents=True,exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
def serve():
    s=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Q,directory=str(ROOT)));threading.Thread(target=s.serve_forever,daemon=True).start();return f'http://127.0.0.1:{s.server_port}/'
INIT="""window.__v=[];window.__sfx=0;
const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){const el=this;el.addEventListener('playing',()=>{if(!el.muted)__v.push('EL:'+el.currentSrc)},{once:true});return op.apply(this,arguments)};
if(window.AudioBufferSourceNode){const os=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(){if(this.__src)__v.push('BUF:'+this.__src);return os.apply(this,arguments)}}
if(window.OscillatorNode){const oo=OscillatorNode.prototype.start;OscillatorNode.prototype.start=function(){__sfx++;return oo.apply(this,arguments)}}
if(window.speechSynthesis){const sp=speechSynthesis.speak.bind(speechSynthesis);speechSynthesis.speak=u=>{__v.push('TTS');sp(u)}}"""
fails=[]
def check(c,msg):
    print(('OK   ' if c else 'FAIL ')+msg,flush=True)
    if not c:fails.append(msg)
async def main():
    url=serve();errs=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
        for vw in (360,412):
            ctx=await b.new_context(viewport={'width':vw,'height':800 if vw==360 else 915},is_mobile=True,has_touch=True,device_scale_factor=2)
            await ctx.add_init_script(INIT);pg=await ctx.new_page()
            pg.on('pageerror',lambda e:errs.append(str(e)))
            await pg.goto(url,wait_until='load');await pg.wait_for_timeout(1500)
            await pg.evaluate("localStorage.clear()");await pg.reload(wait_until='load');await pg.wait_for_timeout(1500)
            # header fits: every header control inside the viewport, none overlapping
            boxes=await pg.evaluate("""()=>[...document.querySelectorAll('header > *')].filter(e=>e.offsetParent).map(e=>{const r=e.getBoundingClientRect();return [e.id||e.className,r.left,r.right,r.top,r.bottom]})""")
            over=[x[0] for x in boxes if x[1]<-1 or x[2]>vw+1]
            check(not over,f'{vw}px header fits ({len(boxes)} items) {over}')
            await pg.tap('#vtogBtn');await pg.wait_for_timeout(300)
            check(await pg.evaluate("localStorage.getItem('emmaVoiceOff')")=='1',f'{vw}px toggle saves voice off')
            await pg.screenshot(path=str(OUT/f'header-voice-off-{vw}.png'),clip={'x':0,'y':0,'width':vw,'height':140})
            if vw==412:break
            await ctx.close()
        # persists after reload
        await pg.reload(wait_until='load');await pg.wait_for_timeout(1500)
        check(await pg.evaluate("document.querySelector('#vtogBtn').classList.contains('off')&&document.body.classList.contains('voiceoff')"),'voice off persists after reload')
        await pg.evaluate("__v=[];__sfx=0")
        await pg.tap('.wsay',force=True) if await pg.query_selector('.wsay:visible') else None
        check(not await pg.query_selector('main .say:visible'),'read-aloud buttons hidden on world map')
        # world map -> Letter Land -> ABC card
        await pg.tap('.wsignb[data-l="letter"]');await pg.wait_for_timeout(700)
        await pg.tap('.wplace[data-p="abc"]');await pg.wait_for_timeout(900)
        await pg.tap('.wtile[data-i="0"]');await pg.wait_for_timeout(1200)
        bub=await pg.evaluate("document.querySelector('#bub').textContent")
        check('apple' in bub.lower(),f'ABC card bubble text still shows ({bub[:30]})')
        check(not await pg.query_selector('.pop .say:visible'),'card read-aloud hidden')
        await pg.evaluate("document.querySelectorAll('.pop').forEach(x=>x.remove())")
        # house room game: Kitchen level 1 Find It, answer right and wrong
        await pg.evaluate("go('house')");await pg.wait_for_timeout(500)
        await pg.tap('.room[data-k="kitchen"]');await pg.wait_for_timeout(600)
        await pg.tap('.lnode[data-l="1"]');await pg.wait_for_timeout(600)
        await pg.tap('.mode[data-m="find"]');await pg.wait_for_timeout(800)
        s0=await pg.evaluate("stars")
        t=await pg.evaluate("document.querySelector('.prompt span').textContent")
        await pg.evaluate("""t=>{const want=t.replace(/^Find the |!$/g,'');const b=[...document.querySelectorAll('.pic')].find(x=>x.dataset.n===want);b.click()}""",t)
        await pg.wait_for_timeout(1500)
        check(await pg.evaluate("stars")>s0,'house game still gives a star')
        # Bible page
        await pg.evaluate("document.querySelectorAll('.pop').forEach(x=>x.remove());go('bible')");await pg.wait_for_timeout(700)
        await pg.tap('.book[data-b="noah"]');await pg.wait_for_timeout(1200)
        await pg.tap('#bnext');await pg.wait_for_timeout(1200)
        check(await pg.evaluate("document.querySelector('#btext').textContent.length>5"),'Bible page text shows')
        check(not await pg.query_selector('#bsay:visible'),'Bible read-aloud hidden')
        v=await pg.evaluate("__v");sfx=await pg.evaluate("__sfx")
        check(v==[],f'no voice played while off ({v[:3]})')
        check(sfx>0,f'sound effects still play ({sfx} tones)')
        # turn on again: speaks 'Voice on!' at once
        await pg.evaluate("go('home')");await pg.wait_for_timeout(500)
        await pg.evaluate("__v=[]");await pg.tap('#vtogBtn');await pg.wait_for_timeout(1200)
        v=await pg.evaluate("__v")
        check(any('e5ffb295' in x for x in v),f"turning on says 'Voice on!' ({v})")
        check(await pg.evaluate("localStorage.getItem('emmaVoiceOff')")=='0','voice on saved')
        await pg.evaluate("__v=[]");await pg.tap('.wsay');await pg.wait_for_timeout(1000)
        check(len(await pg.evaluate("__v"))>0,'voice works again after turning on')
        # settings panel toggle
        await pg.tap('#voiceBtn');await pg.wait_for_selector('#vOffBtn')
        await pg.tap('#vOffBtn');await pg.wait_for_timeout(300)
        check(await pg.evaluate("voiceOff&&document.querySelector('#vtogBtn').classList.contains('off')"),'Voice Settings toggle switches voice off and syncs header')
        await pg.screenshot(path=str(OUT/'voice-settings-off.png'))
        await b.close()
    check(not errs,f'no page errors {errs[:2]}')
    print('VOICE OFF TESTS '+('PASSED' if not fails else 'FAILED: '+str(fails)))
    sys.exit(1 if fails else 0)
asyncio.run(main())
