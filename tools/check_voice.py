"""List every spoken prompt string that has no matching voice/<fnv>.mp3 clip.
Usage: python3 tools/check_voice.py [URL_or_local_dir]   (default: repo dir, served locally)
Prints missing lines as JSON [text, path] (feed to Kokoro gen.py). Exit 1 if any missing."""
import sys,os,json,asyncio,threading,http.server,functools
from playwright.async_api import async_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENUM=r"""()=>{const S=new Set(),A=x=>{(Array.isArray(x)?x:[x]).forEach(t=>t&&S.add(t))};
A(PRAISE);A(TRY);A(['Pick a room to play!',"Let's learn!",'This level is locked! Get 2 stars on the level before it.',
"Let's try again!","You need 2 stars to pass. Try again!",'Great job! Level complete!','You earned a room trophy! Amazing!','You unlocked the next level!',
'Pick a story to read!','Welcome to the Bible Library! Pick a story to read!',"Quiz time! Let's see what you remember!",'Or,']);
document.querySelectorAll('.room:not([data-k="bible"]) .nm').forEach(e=>A(e.textContent+' is coming soon!'));
ROOMS.forEach(r=>A('Welcome to the '+r.n.toLowerCase()+'! Pick a level!'));
for(const it of ITEMS){A([it.name,it.use,`Find the ${it.name}!`,`Where is the ${it.name}?`,`What is the ${it.name} used for?`,`Where does the ${it.name} go?`,`Spell ${it.name}!`,useQuestion(it),hideName(it)]);
 for(const c of it.name.toUpperCase())if(c.trim())A(c)}
if(typeof BIBLE!=='undefined')for(const b of Object.values(BIBLE)){b.pages.forEach(p=>A(p.say));A(b.done);(b.quiz||[]).forEach(q=>{A(q.q);(q.o||q.opts||q.options||[]).forEach(A)});
 document.querySelectorAll('.book[data-n]').forEach(e=>A(e.dataset.n+' is coming soon!'))}
if(typeof L4!=='undefined')JSON.stringify(L4,(k,v)=>{if(typeof v==='string'&&/[a-z] /i.test(v))A(v);return v});
if(window.__extraVoice)A(window.__extraVoice);
return [...S].map(t=>[t,vh(t)])}"""
async def main(target):
    srv=None
    if not target.startswith('http'):
        h=functools.partial(http.server.SimpleHTTPRequestHandler,directory=target)
        http.server.ThreadingHTTPServer.allow_reuse_address=True
        srv=http.server.ThreadingHTTPServer(('127.0.0.1',0),h);threading.Thread(target=srv.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{srv.server_port}/'
    else: url=target
    async with async_playwright() as p:
        b=await p.chromium.launch();pg=await b.new_page()
        pg.on('pageerror',lambda e:print('PAGEERR',e))
        await pg.goto(url,wait_until='networkidle')
        rows=await pg.evaluate(ENUM)
        st=await pg.evaluate("async r=>Promise.all(r.map(([t,h])=>fetch('voice/'+h+'.mp3',{method:'HEAD',cache:'no-store'}).then(x=>x.status)))",rows)
        await b.close()
    miss=[[t,f'voice/{h}.mp3'] for (t,h),s in zip(rows,st) if s!=200]
    print(f'{len(rows)} prompt strings, {len(rows)-len(miss)} with clips, {len(miss)} missing',file=sys.stderr)
    print(json.dumps(miss,ensure_ascii=False,indent=0))
    return 1 if miss else 0
sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv)>1 else ROOT)))
