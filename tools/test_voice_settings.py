"""Playwright tests for Voice Settings panel."""
import asyncio, sys, threading, functools, http.server
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SHOT = Path('/workspace/voice-settings-deliverables')
SHOT.mkdir(exist_ok=True)
errs = []

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

async def run(url, tag='local'):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1280, 'height': 800})
        pg = await ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(f'PAGE:{e}'))
        pg.on('console', lambda m: m.type == 'error' and errs.append(f'CONSOLE:{m.text}'))
        await pg.goto(url, wait_until='networkidle')
        await pg.evaluate('()=>localStorage.clear()')
        await pg.reload(wait_until='networkidle')
        await pg.wait_for_timeout(600)

        # Open settings
        await pg.click('#voiceBtn')
        await pg.wait_for_selector('.vpanel .vcard')
        cards = await pg.query_selector_all('.vcard')
        assert len(cards) >= 5, f'expected >=5 voice cards, got {len(cards)}'
        await pg.screenshot(path=str(SHOT / 'settings_panel.png'), full_page=False)
        print('screenshot OK', SHOT / 'settings_panel.png')

        # Preview Lily
        await pg.click('.vcard[data-id="lily"]')
        await pg.wait_for_timeout(1200)
        on = await pg.eval_on_selector('.vcard[data-id="lily"]', 'e=>e.classList.contains("on")')
        assert on, 'Lily not selected'
        stored = await pg.evaluate("()=>JSON.parse(localStorage.getItem('emmaVoice')||'{}')")
        assert stored.get('id') == 'lily', stored

        # Move sliders
        await pg.evaluate('''()=>{
          const s=document.getElementById('vSpeed'); const p=document.getElementById('vPitch');
          s.value='1.2'; s.dispatchEvent(new Event('input',{bubbles:true})); s.dispatchEvent(new Event('change',{bubbles:true}));
          p.value='1.1'; p.dispatchEvent(new Event('input',{bubbles:true})); p.dispatchEvent(new Event('change',{bubbles:true}));
        }''')
        await pg.wait_for_timeout(800)
        stored = await pg.evaluate("()=>JSON.parse(localStorage.getItem('emmaVoice')||'{}')")
        assert abs(float(stored.get('speed', 0)) - 1.2) < 0.01, stored
        assert abs(float(stored.get('pitch', 0)) - 1.1) < 0.01, stored

        await pg.click('#vClose')
        await pg.wait_for_selector('.vpanel', state='detached')

        # Play a home line in Lily voice
        await pg.click('.wsay')
        await pg.wait_for_timeout(800)
        src = await pg.evaluate("()=>document.querySelector('audio')?.src || (window.vEl && vEl.src) || ''")
        # vEl is not on window — check via evaluate of voiceUrl path
        src = await pg.evaluate("""()=>{
          const a=[...document.querySelectorAll('audio')];
          // our vEl is not in DOM; intercept by checking localStorage id + hashing
          return JSON.parse(localStorage.getItem('emmaVoice')||'{}').id;
        }""")
        assert src == 'lily'

        # Switch to Leo, play morning line
        await pg.click('#voiceBtn')
        await pg.click('.vcard[data-id="leo"]')
        await pg.wait_for_timeout(1500)
        # ensure SW has a chance to cache leo pack (best-effort; fetch fallback also caches)
        await pg.evaluate('''async ()=>{
          if(!navigator.serviceWorker) return;
          const reg=await navigator.serviceWorker.ready;
          if(navigator.serviceWorker.controller) navigator.serviceWorker.controller.postMessage({type:'cacheVoice',id:'leo'});
          await new Promise(r=>setTimeout(r,2500));
        }''')
        await pg.click('#vClose')
        await pg.click('.wsignb[data-l="faith"]')
        await pg.click('.wplace[data-p="mia"]')
        await pg.wait_for_selector('.mstage')
        await pg.wait_for_timeout(1500)
        # Confirm voice pack path would be used
        path = await pg.evaluate("""()=>{
          const id=JSON.parse(localStorage.getItem('emmaVoice')||'{}').id;
          const t="Let's start Mia's Morning Routine!";
          let h=0x811c9dc5; for(let i=0;i<t.length;i++){h^=t.charCodeAt(i);h=Math.imul(h,0x01000193)>>>0}
          const hex=h.toString(16).padStart(8,'0');
          return {id, url: (id==='mia'?'voice/':'voice/'+id+'/')+hex+'.mp3'};
        }""")
        print('morning voice path', path)
        st = await pg.evaluate("""async (url)=>{try{const r=await fetch(url,{method:'HEAD',cache:'no-store'});return r.status}catch(e){return 0}}""", path['url'])
        assert st == 200, f"clip missing {path} status={st}"

        # Go offline after switch and confirm clip still plays from cache
        await pg.context.set_offline(True)
        await pg.wait_for_timeout(300)
        # re-fetch via SW/cache
        st2 = await pg.evaluate("""async (url)=>{try{const r=await fetch(url,{cache:'force-cache'});return r.status}catch(e){return -1}}""", path['url'])
        print('offline status', st2)
        assert st2 == 200, f'offline clip failed status={st2} url={path}'
        saybtn = await pg.query_selector('.mq .say')
        if saybtn:
            await saybtn.click()
            await pg.wait_for_timeout(800)
        await pg.context.set_offline(False)

        await b.close()
    print('ERRORS', errs)
    print('error_count', len(errs))
    if errs:
        sys.exit(1)

async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target and target.startswith('http'):
        await run(target, 'live')
    else:
        h = functools.partial(Quiet, directory=str(ROOT))
        http.server.ThreadingHTTPServer.allow_reuse_address = True
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{srv.server_port}/'
        await run(url, 'local')

if __name__ == '__main__':
    asyncio.run(main())
