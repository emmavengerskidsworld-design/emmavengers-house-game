"""Tap-to-first-voice latency on a throttled phone. usage: latency.py URL label"""
# Run: python3 tools/throttle_server.py <repo> 8601 & ; python3 tools/test_voice_latency.py http://127.0.0.1:8601/ label nothrottle 60000
# Pass target: every tap-to-first-voice <= ~700 ms on slow 4G (200 KB/s shared, 150 ms RTT), cold and warm.
import asyncio,sys,json,time
from playwright.async_api import async_playwright
URL=sys.argv[1];LABEL=sys.argv[2];THR=len(sys.argv)<4 or sys.argv[3]!='nothrottle'
INIT="""window.__ev=[];window.__t0=0;addEventListener('pointerdown',()=>{window.__t0=performance.now()},true);
const op=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){const el=this;el.addEventListener('playing',()=>{if(!el.muted)__ev.push({t:performance.now(),src:el.currentSrc})},{once:true});return op.apply(this,arguments)};
if(window.speechSynthesis){const sp=speechSynthesis.speak.bind(speechSynthesis);speechSynthesis.speak=u=>{__ev.push({t:performance.now(),src:'TTS'});sp(u)}}"""
TAPS=[('Kitchen room','.room[data-k="kitchen"]'),('Level 1 node','.lnode[data-l="1"]'),('Find It (learn)','.mode[data-m]'),('BACK',None),('BACK',None),('BACK',None),('Bible Library','.room.bible'),('Noah book','.book[data-b="noah"]'),('BACK',None),('BACK',None),('Mia Morning','.room.mhome'),('BACK',None),('Bedroom room','.room[data-k="bedroom"]')]
async def measure(pg,sel):
    await pg.evaluate('__ev=[]');await pg.click(sel)
    for _ in range(200):
        r=await pg.evaluate('(()=>{const e=__ev.find(x=>x.t>=__t0);return e?[e.t-__t0,e.src]:null})()')
        if r:return round(r[0]),r[1].split('/')[-1]
        await pg.wait_for_timeout(100)
    return None,'NO AUDIO in 20s'
async def run(p,warm):
    b=await p.chromium.launch(args=['--autoplay-policy=user-gesture-required'])
    ctx=await b.new_context(**p.devices['Pixel 7'])
    await ctx.add_init_script(INIT);pg=await ctx.new_page()
    open('/tmp/emma-lat-rate','w').write('0' if warm else '200000')
    if warm:  # first visit unthrottled, let SW precache + book prefetch finish
        await pg.goto(URL,wait_until='load');await pg.wait_for_function("navigator.serviceWorker&&navigator.serviceWorker.controller",timeout=120000)
        await pg.wait_for_timeout(int(sys.argv[4]) if len(sys.argv)>4 else 20000)
    open('/tmp/emma-lat-rate','w').write('200000')
    if THR:
        cdp=await ctx.new_cdp_session(pg);await cdp.send('Network.enable');await cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':150,'downloadThroughput':200000,'uploadThroughput':90000})
    await pg.goto(URL,wait_until='load');await pg.wait_for_timeout(5000)
    await pg.tap('#title');await pg.wait_for_timeout(800)  # first tap unlock like a kid touching the screen
    out=[]
    for name,sel in TAPS:
        if sel is None:
            await pg.evaluate("emmaBack()");await pg.wait_for_timeout(700);continue
        ms,src=await measure(pg,sel);out.append((name,ms,src));print(name,ms,src,flush=True);await pg.wait_for_timeout(1500)
    await b.close();return out
async def main():
    async with async_playwright() as p:
        res={}
        for warm in (False,True):
            res['warm' if warm else 'cold']=await run(p,warm)
    print(LABEL);print(json.dumps(res));json.dump(res,open(f'/tmp/emma-lat-{LABEL}.json','w'))
asyncio.run(main())
