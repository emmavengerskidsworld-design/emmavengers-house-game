"""Playwright test for Parents' Corner (math gate, PIN, YouTube link, voice settings, back hook)."""
import asyncio, threading, functools, http.server, re
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]; SHOT=Path('/workspace/app/shots'); SHOT.mkdir(parents=True,exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
async def main():
    srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Q,directory=str(ROOT)))
    port=srv.server_address[1]; threading.Thread(target=srv.serve_forever,daemon=True).start()
    errs=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={'width':1280,'height':720})
        pg.on('pageerror',lambda e:errs.append(str(e)))
        await pg.goto(f'http://127.0.0.1:{port}/',wait_until='networkidle'); await pg.evaluate('localStorage.clear()'); await pg.reload(wait_until='networkidle')
        await pg.click('#parentBtn'); q=await pg.text_content('#ppanel .subh')
        a,bb=map(int,re.findall(r'(\d+) × (\d+)',q)[0])
        await pg.screenshot(path=str(SHOT/'parents-gate.png'))
        await pg.fill('#pIn','1'); await pg.click('#pOk'); assert 'try again' in await pg.text_content('#pErr')
        await pg.fill('#pIn',str(a*bb)); await pg.click('#pOk'); await pg.wait_for_selector('#pYt')
        assert 'youtube.com' in await pg.get_attribute('#pYt','href')
        await pg.screenshot(path=str(SHOT/'parents-corner.png'))
        await pg.fill('#pNew','4821'); await pg.click('#pSave'); assert await pg.evaluate("localStorage.emmaParentPin")=='4821'
        await pg.click('#pVoice'); await pg.wait_for_selector('#vpanel .vcard'); await pg.click('#vClose')
        await pg.click('#parentBtn'); assert 'PIN' in await pg.text_content('#ppanel .subh')
        await pg.fill('#pIn','0000'); await pg.click('#pOk'); assert await pg.query_selector('#pYt') is None
        await pg.fill('#pIn','4821'); await pg.click('#pOk'); await pg.wait_for_selector('#pYt')
        assert await pg.evaluate('emmaBack()') is True and await pg.query_selector('#ppanel') is None
        assert await pg.evaluate('emmaBack()') is False  # home screen -> app exits
        await pg.click('.room.bible'); assert await pg.evaluate('emmaBack()') is True
        await pg.wait_for_timeout(300); assert await pg.evaluate('screen')=='home'
        await b.close()
    assert not errs, errs; print('PARENTS TESTS PASSED')
asyncio.run(main())
