"""Scale test:  python3 tools/test_scale.py [--countries 200] [--keep DIR]
Makes a fake library of N countries x 5 languages (en, fr, es, sw, and Arabic as a right-to-left language) by cloning
the Cameroon pilot under new ids, builds it, and measures in Chromium: first start, opening one country, opening every
country (worst case), offline restart with everything installed, an update after one country changed, plus JS heap.
Budgets (fail if exceeded): build < 120 s; catalog < 16 KB; any index < 256 KB; first start < 2.5 s on localhost and
< 200 KB gzipped transfer; update after a one-country edit downloads < 250 KB; JS heap with ALL countries open < 300 MB."""
import gzip, os, sys, json, shutil, tempfile, time, re, threading, functools, http.server, asyncio, io, contextlib, argparse
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content_build
from content.common import load_json, write_json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('--countries', type=int, default=200); ap.add_argument('--keep'); A = ap.parse_args()
N = A.countries
fails, rows = [], []
def ok(c, m):
    print(('  ok  ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
def quiet(f, *a):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()): return f(*a)

T = A.keep or tempfile.mkdtemp(prefix='ewscale-'); os.makedirs(T, exist_ok=True)
src, lib, lock = os.path.join(T, 'src'), os.path.join(T, 'lib'), os.path.join(T, 'lock.json')
shutil.rmtree(src, ignore_errors=True); shutil.rmtree(lib, ignore_errors=True)
if os.path.exists(lock): os.remove(lock)
shutil.copytree(os.path.join(ROOT, 'content/src'), src)
EXTRA = ['es', 'sw', 'ar']
L = load_json(os.path.join(src, 'locales.json'))
L['locales'] += [{'tag': 'es', 'name': 'Español', 'dir': 'ltr', 'status': 'active'}, {'tag': 'sw', 'name': 'Kiswahili', 'dir': 'ltr', 'status': 'active'},
                 {'tag': 'ar', 'name': 'العربية', 'dir': 'rtl', 'status': 'active'}]
write_json(os.path.join(src, 'locales.json'), L)
LANGS = ['en', 'fr'] + EXTRA
AR = 'نص تجريبي'; CNT = [0]
def add_langs(o):
    if isinstance(o, dict):
        if 'en' in o and isinstance(o['en'], str) and all(isinstance(v, str) for v in o.values()) and all(re.fullmatch(r'[a-z]{2,3}(-[A-Za-z0-9]+)*', k) for k in o):
            ph = ' '.join(re.findall(r'\{[a-zA-Z_]+\}', o['en']))
            for lg in EXTRA:
                CNT[0] += 1
                o.setdefault(lg, (f'{AR} {CNT[0]} {ph}'.strip() if lg == 'ar' else f'[{lg}] ' + o['en']))
            return
        for v in o.values(): add_langs(v)
    elif isinstance(o, list):
        for v in o: add_langs(v)
REG = ['africa', 'americas', 'asia', 'europe', 'oceania']
cam = os.path.join(src, 'countries/cameroon')
t0 = time.time()
for i in range(N):
    slug = f'testland{i:03d}'; reg = REG[i % 5]; d = os.path.join(src, 'countries', slug); os.makedirs(d)
    for f in os.listdir(cam):
        txt = open(os.path.join(cam, f), encoding='utf-8').read()
        txt = txt.replace('pilot-cameroon', 'pilot-' + slug).replace('ew.country.cameroon', 'ew.country.' + slug).replace('country.cameroon', 'country.' + slug) \
                 .replace('"cameroon"', f'"{slug}"').replace('Cameroon', f'Testland {i}').replace('Cameroun', f'Testland {i}').replace('"africa"', f'"{reg}"') \
                 .replace('countries.africa', 'countries.' + reg).replace('"CM"', f'"T{i:03d}"')
        doc = json.loads(txt)
        if f == 'pack.json': doc['preload'] = False
        add_langs(doc); write_json(os.path.join(d, f), doc)
gen = time.time() - t0
ARGS = ['--src', src, '--lib', lib, '--lock', lock, '--report', os.path.join(T, 'report.md'), '--quiet', '--no-files']
t0 = time.time(); rc = quiet(content_build.main, ARGS); build = time.time() - t0
if rc != 0:
    rc = content_build.main([a for a in ARGS if a != '--quiet'])
ok(rc == 0, f'{N} countries x {len(LANGS)} languages validate and build ({build:.1f} s, generation {gen:.1f} s)'); ok(build < 120, 'build under 120 s')
cat = load_json(os.path.join(lib, 'catalog.json'))
recs = sum(len(load_json(os.path.join(lib, c['index']['path']))['packs']) for c in cat['collections'])
sz = lambda p: os.path.getsize(os.path.join(lib, p))
cat_b = os.path.getsize(os.path.join(lib, 'catalog.json')); idx = {c['id']: c['index']['bytes'] for c in cat['collections']}
tot = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(lib) for f in fs)
nrec = sum(json.load(open(os.path.join(lib, 'catalog.json')))['collections'][k]['packs'] for k in range(len(cat['collections'])))
ok(cat_b < 16 * 1024, f'catalog {cat_b/1024:.1f} KB'); ok(max(idx.values()) < 256 * 1024, f'largest index {max(idx.values())/1024:.1f} KB ({len(idx)} indexes)')
print(f'  info library on disk: {tot/1e6:.1f} MB for {nrec} packs')
# one-country edit for the update measurement
q = os.path.join(src, 'countries/testland007/quiz.json'); d = load_json(q); d['records'][1]['payload']['hint']['en'] = 'Changed for the scale test.'; write_json(q, d)
REL = {'A': os.path.join(T, 'A')}; shutil.rmtree(REL['A'], ignore_errors=True); shutil.copytree(lib, REL['A'])
assert quiet(content_build.main, ARGS) == 0
REL['B'] = os.path.join(T, 'B'); shutil.rmtree(REL['B'], ignore_errors=True); shutil.copytree(lib, REL['B'])
SERVE = {'rel': 'A'}
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def translate_path(self, path):
        path = path.split('?')[0]
        if path.startswith('/lib-test/'): return os.path.join(REL[SERVE['rel']], path[len('/lib-test/'):])
        return super().translate_path(path)
    def do_GET(self):
        if self.path.split('?')[0] == '/t.html':
            b = b'<!doctype html><meta charset=utf-8><script>window.EW_LIBRARY_AUTO=false</script><script src="/library.js"></script>'
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b); return
        return super().do_GET()
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f'http://127.0.0.1:{srv.server_port}/t.html'
MK = """async ([db]) => { const t = performance.now(); const L = EWLibrary.create({ db, base: '/lib-test/', autoUpdate: false }); window.__L = L;
  await L.ready; return { ms: performance.now() - t, st: L.status() } }"""
async def heap(cdp):
    await cdp.send('HeapProfiler.collectGarbage'); h = await cdp.send('Runtime.getHeapUsage'); return h['usedSize'] / 1e6
async def main():
    async with async_playwright() as pw:
        br = await pw.chromium.launch(); ctx = await br.new_context(); pg = await ctx.new_page(); cdp = await ctx.new_cdp_session(pg)
        await pg.goto(URL); h0 = await heap(cdp)
        r = await pg.evaluate(MK, ['s1']); h1 = await heap(cdp)
        gz = sum(len(gzip.compress(open(os.path.join(REL['A'], f), 'rb').read(), 6)) for f in r['st']['fetched'])
        ok(r['ms'] < 2500 and gz < 200 * 1024, f'first start: {r["ms"]:.0f} ms, {len(r["st"]["fetched"])} files (catalog + {len(idx)} indexes + starter packs), '
           f'{r["st"]["bytes"]/1024:.0f} KB raw = {gz/1024:.0f} KB over the network (gzip, as GitHub Pages serves JSON); heap +{h1-h0:.1f} MB')
        c = await pg.evaluate("(async()=>{const t=performance.now();const c=await __L.legacy.country('testland042');return {ms:performance.now()-t,n:c.pack.payload.learn.little.cards.length, dir:__L.locales().find(l=>l.tag==='ar').dir, ar:__L.get('ew.country.testland042').payload.name.ar}})()")
        ok(c['n'] > 0, f'open one country on demand: {c["ms"]:.0f} ms'); ok(c['dir'] == 'rtl' and c['ar'], 'Arabic (right-to-left) text present and marked rtl')
        t = await pg.evaluate("(async()=>{const t=performance.now();for(const p of __L.packs())if(!p.installed)await __L.ensure(p.id);return {ms:performance.now()-t, n:__L.packs().filter(p=>p.installed).length, st:__L.status()}})()")
        h2 = await heap(cdp)
        ok(h2 < 300, f'open ALL {t["n"]-1} countries: {t["ms"]/1000:.1f} s, {t["st"]["bytes"]/1e6:.1f} MB downloaded in total; JS heap {h2:.0f} MB')
        q = await pg.evaluate("(()=>{const t=performance.now();const a=__L.find({type:'quiz-item',region:'asia',ageBand:'8-10'});const b=__L.find({type:'country',lang:'ar'});return {ms:performance.now()-t,a:a.length,b:b.length}})()")
        ok(q['a'] > 0 and q['b'] == N + 0 and q['ms'] < 200, f'queries over everything: {q["a"]} Asia quiz items for 8-10 + {q["b"]} countries with Arabic in {q["ms"]:.0f} ms')
        await ctx.set_offline(True)
        r = await pg.evaluate(MK, ['s1'])
        ok(r['st']['source'] == 'device' and not r['st']['fetched'], f'OFFLINE restart with all {t["n"]} packs: {r["ms"]:.0f} ms')
        await ctx.set_offline(False); SERVE['rel'] = 'B'
        u = await pg.evaluate('__L.checkForUpdates(true)')
        ok(u['result'] == 'updated' and u['bytes'] < 250 * 1024, f'update after a one-country edit: {len(u["files"])} files, {u["bytes"]/1024:.0f} KB ({u["changed"]})')
        await br.close()
        return r
asyncio.run(main())
print(f'  info fake library kept in {T}' if A.keep else '', end='')
if not A.keep: shutil.rmtree(T, ignore_errors=True)
print('\nSCALE ' + ('PASSED' if not fails else 'FAILED: ' + '; '.join(fails)))
sys.exit(1 if fails else 0)
