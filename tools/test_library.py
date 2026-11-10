"""Content loader (library.js) tests in a real browser (Chromium, Playwright):  python3 tools/test_library.py
Builds small test releases in a temp folder from content/src and serves them, then checks:
  - the JS legacy adapter gives the app exactly the pre-Stage-1 files (lands, country index, ui, Cameroon pack + quiz)
  - first visit downloads and verifies; the next start works fully OFFLINE from the device copy (IndexedDB)
  - an update downloads ONLY the catalog + changed files; the running session keeps its content until applyUpdate()
  - a file whose SHA-256 does not match is refused and the last good release stays in use
  - a damaged device copy falls back to the previous release (offline) or repairs itself (online)
  - an older catalog (replay) is refused; a missing pack fails cleanly; an incompatible pack is skipped
  - with no IndexedDB (private mode) it still works for the visit (memory)"""
import os, sys, json, shutil, tempfile, threading, functools, http.server, asyncio, io, contextlib
from playwright.async_api import async_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content_build
from content.common import load_json, write_json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'tools/fixtures/legacy-v0')
fails, n = [], [0]
def ok(c, m):
    n[0] += 1; print(('  ok  ' if c else '  FAIL ') + m)
    if not c: fails.append(m)
def quiet(f, *a):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()): return f(*a)

# ---------- test releases ----------
T = tempfile.mkdtemp(prefix='ewlib-')
src, lib, lock = os.path.join(T, 'src'), os.path.join(T, 'lib'), os.path.join(T, 'lock.json')
shutil.copytree(os.path.join(ROOT, 'content/src'), src)
ARGS = ['--src', src, '--lib', lib, '--lock', lock, '--report', os.path.join(T, 'r.md'), '--quiet', '--no-files']
assert quiet(content_build.main, ARGS) == 0
REL = {'A': os.path.join(T, 'A')}; shutil.copytree(lib, REL['A'])
Q1 = 'ew.quiz.pilot-cameroon-q01'; NEW_HINT = 'A flag stands for a whole country.'
p = os.path.join(src, 'countries/cameroon/quiz.json'); d = load_json(p)
next(r for r in d['records'] if r['id'] == Q1)['payload']['hint']['en'] = NEW_HINT; write_json(p, d)
assert quiet(content_build.main, ARGS) == 0
REL['B'] = os.path.join(T, 'B'); shutil.copytree(lib, REL['B'])
catA, catB = load_json(os.path.join(REL['A'], 'catalog.json')), load_json(os.path.join(REL['B'], 'catalog.json'))
def entries(rel):
    c = load_json(os.path.join(rel, 'catalog.json')); out = {}
    for col in c['collections']:
        for e in load_json(os.path.join(rel, col['index']['path']))['packs']: out[e['id']] = e
    return out
eA, eB = entries(REL['A']), entries(REL['B'])
# C = B with one changed letter in the new Cameroon English file (same size -> only the hash check can catch it)
REL['C'] = os.path.join(T, 'C'); shutil.copytree(REL['B'], REL['C'])
fC = os.path.join(REL['C'], eB['country.cameroon']['locales']['en']['path']); b = open(fC, 'rb').read()
i = b.index(b'whole'); open(fC, 'wb').write(b[:i] + b'W' + b[i + 1:])
# D = B with the Cameroon structure file deleted (missing pack)
REL['D'] = os.path.join(T, 'D'); shutil.copytree(REL['B'], REL['D']); os.remove(os.path.join(REL['D'], eB['country.cameroon']['file']['path']))
# E = A, but Cameroon is not a starter pack (downloaded when first opened)
REL['E'] = os.path.join(T, 'E'); s2 = os.path.join(T, 'srcE'); shutil.copytree(os.path.join(ROOT, 'content/src'), s2)
pp = os.path.join(s2, 'countries/cameroon/pack.json'); d = load_json(pp); d['preload'] = False; write_json(pp, d)
assert quiet(content_build.main, ['--src', s2, '--lib', REL['E'], '--lock', os.path.join(T, 'lockE.json'), '--report', os.path.join(T, 'rE.md'), '--quiet', '--no-files']) == 0
eE = entries(REL['E'])
REL['F'] = os.path.join(T, 'F'); shutil.copytree(REL['E'], REL['F']); os.remove(os.path.join(REL['F'], eE['country.cameroon']['file']['path']))

SERVE = {'rel': 'A'}; LOG = []
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def translate_path(self, path):
        path = path.split('?')[0]
        if path.startswith('/lib-test/'):
            LOG.append(path[len('/lib-test/'):]); return os.path.join(REL[SERVE['rel']], path[len('/lib-test/'):])
        return super().translate_path(path)
    def do_GET(self):
        if self.path.split('?')[0] == '/t.html':
            b = b'<!doctype html><meta charset=utf-8><script>window.EW_LIBRARY_AUTO=false</script><script src="/library.js"></script>'
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b); return
        return super().do_GET()
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f'http://127.0.0.1:{srv.server_port}/t.html'

MK = """async ([db, base, extra]) => { const L = EWLibrary.create(Object.assign({ db, base: base || '/lib-test/', autoUpdate: false, retries: 0, timeoutMs: 3000 }, extra || {}));
  window.__L = L; try { await L.ready; return { ok: true, st: L.status() } } catch (e) { return { ok: false, code: e.code, msg: e.message, st: L.status() } } }"""

async def main():
    async with async_playwright() as pw:
        br = await pw.chromium.launch(); ctx = await br.new_context(); pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(URL)
        mk = lambda db, base=None, extra=None: pg.evaluate(MK, [db, base, extra])

        print('1. legacy adapter (JS) = the original files')
        r = await mk('ew-real', '/content/library/'); ok(r['ok'], 'committed content/library loads')
        got = json.loads(await pg.evaluate("""async () => { const L = window.__L, c = await L.legacy.country('cameroon');
            return JSON.stringify({ lands: L.legacy.lands(), index: L.legacy.countryIndex(), ui: L.legacy.uiStrings(), cameroon: c.pack, 'cameroon-quiz': c.bank }) }"""))
        for k in ('lands', 'index', 'ui', 'cameroon', 'cameroon-quiz'):
            want = load_json(os.path.join(FIX, k + '.json'))
            same = got[k] == want
            strict = json.dumps(got[k]) == json.dumps(want) if k != 'lands' else json.dumps({**got[k], 'lands': None}) == json.dumps({**want, 'lands': None})
            ok(same and strict, f'{k}: identical' + (' (values and key order)' if strict else ''))

        print('2. first visit, then offline start')
        SERVE['rel'] = 'A'; LOG.clear()
        r = await mk('t1'); ok(r['ok'] and r['st']['source'] == 'network' and r['st']['sequence'] == catA['sequence'], f'first visit downloads release {catA["sequence"]} ({len(LOG)} files, {r["st"]["bytes"]/1024:.0f} KB)')
        ok(r['st']['storage'] == 'indexeddb', 'kept in IndexedDB')
        await ctx.set_offline(True); LOG.clear()
        r = await mk('t1'); ok(r['ok'] and r['st']['source'] == 'device' and not LOG and not r['st']['fetched'], 'OFFLINE start: everything from the device copy, nothing downloaded')
        h = await pg.evaluate(f"__L.get('{Q1}').payload.hint.en"); ok(h and h != NEW_HINT, 'offline content readable (quiz hint)')
        f = await pg.evaluate("(async()=>{try{return await __L.checkForUpdates(true)}catch(e){return {result:'threw'}}})()")
        ok(f['result'] in ('offline', 'failed'), f'update check while offline does nothing harmful ({f["result"]})')
        await ctx.set_offline(False)

        print('3. incremental update')
        SERVE['rel'] = 'B'; LOG.clear()
        r = await mk('t1'); res = await pg.evaluate('__L.checkForUpdates(true)')
        changed = set(eB) - {k for k in eB if eA.get(k) and eA[k]['file'] == eB[k]['file'] and eA[k]['locales'] == eB[k]['locales']}
        core_files = {eB['core']['file']['path']} | {v['path'] for v in eB['core']['locales'].values()}
        ok(res['result'] == 'updated' and res['sequence'] == catB['sequence'], f'update found: release {catA["sequence"]} -> {res.get("sequence")}')
        ok(not (set(res['files']) & core_files) and 'catalog.json' in res['files'], f'only changed files downloaded: {res["files"]} ({res["bytes"]/1024:.1f} KB)')
        ok(set(res['changed']) == {'country.cameroon'} == changed, f'changed packs reported: {res["changed"]}')
        h = await pg.evaluate(f"__L.get('{Q1}').payload.hint.en"); ok(h != NEW_HINT, 'the running session keeps its content (no change mid-game)')
        await pg.evaluate('__L.applyUpdate()'); h = await pg.evaluate(f"__L.get('{Q1}').payload.hint.en"); ok(h == NEW_HINT, 'applyUpdate() / next start shows the new text')
        LOG.clear(); r = await mk('t1'); ok(r['st']['source'] == 'device' and r['st']['sequence'] == catB['sequence'] and not r['st']['fetched'], 'next start uses the new release from the device, no download')
        res = await pg.evaluate('__L.checkForUpdates(true)'); ok(res['result'] == 'current' and res['files'] == ['catalog.json'], 'no change on server: only the small catalog is read')

        print('4. tampered file (hash mismatch)')
        SERVE['rel'] = 'A'; r = await mk('t4')
        SERVE['rel'] = 'C'; res = await pg.evaluate('__L.checkForUpdates(true)')
        ok(res['result'] == 'failed' and res['code'] == 'hash', f'changed letter detected: {res.get("code")} - {res.get("error", "")[:80]}')
        SERVE['rel'] = 'C'; r = await mk('t4'); ok(r['ok'] and r['st']['sequence'] == catA['sequence'], 'last good release still in use after the refused update')
        r = await mk('t4b'); ok(not r['ok'] and r['code'] == 'hash', 'first visit with a tampered file: refused (app shows the House instead of broken content)')

        print('5. damaged device copy')
        SERVE['rel'] = 'A'; await mk('t5'); SERVE['rel'] = 'B'; await mk('t5'); await pg.evaluate('__L.checkForUpdates(true)')
        sha = eB['country.cameroon']['file']['sha256']
        await pg.evaluate("""async sha => { const { store } = __L._debug(); await store.remove([sha]) }""", sha)
        await ctx.set_offline(True)
        r = await mk('t5'); ok(r['ok'] and r['st']['source'] == 'device-rollback' and r['st']['sequence'] == catA['sequence'], f'offline + damaged release {catB["sequence"]}: rolls back to {r["st"]["sequence"]}')
        await ctx.set_offline(False)
        await mk('t6a'); SERVE['rel'] = 'A'; await mk('t6'); SERVE['rel'] = 'B'; await pg.evaluate('__L.checkForUpdates(true)'); await mk('t6')
        await pg.evaluate("""async sha => { const { store } = __L._debug(); await store.remove([sha]) }""", sha)
        LOG.clear(); r = await mk('t6')
        ok(r['ok'] and r['st']['source'] == 'device' and r['st']['sequence'] == catB['sequence'] and LOG == [eB['country.cameroon']['file']['path']],
           f'online + damaged copy: re-downloads just the missing file ({LOG})')

        print('6. replay, missing pack, incompatible pack, no IndexedDB')
        SERVE['rel'] = 'B'; await mk('t7'); SERVE['rel'] = 'A'
        res = await pg.evaluate('__L.checkForUpdates(true)'); ok(res['result'] == 'failed' and res['code'] == 'replay', 'older catalog refused (sequence numbers only go up)')
        SERVE['rel'] = 'A'; await mk('t8'); SERVE['rel'] = 'D'
        res = await pg.evaluate('__L.checkForUpdates(true)'); ok(res['result'] == 'failed' and res['code'] == 'missing', f'update with a missing pack file fails cleanly ({res.get("code")})')
        r = await mk('t8'); ok(r['ok'] and r['st']['sequence'] == catA['sequence'], 'and the device keeps the last good release')
        SERVE['rel'] = 'E'; r = await mk('t9')
        ok(r['ok'] and r['st']['installed'] == ['core'], 'non-starter country is not downloaded at start')
        LOG.clear(); c = await pg.evaluate("(async()=>{const c=await __L.legacy.country('cameroon');return c.pack.payload.slug})()")
        ok(c == 'cameroon' and any(x.startswith('packs/country.cameroon') for x in LOG), 'opening it downloads it on demand')
        await ctx.set_offline(True); r = await mk('t9')
        ok(r['ok'] and 'country.cameroon' in r['st']['installed'], 'and then it is available offline')
        await ctx.set_offline(False)
        SERVE['rel'] = 'F'; r = await mk('t10')
        e = await pg.evaluate("(async()=>{try{await __L.ensure('country.cameroon');return 'loaded'}catch(e){return e.code}})()")
        ok(r['ok'] and e == 'missing', f'missing country pack on the server: clean "missing" error, rest of the app fine ({e})')
        SERVE['rel'] = 'A'
        r = await mk('t11', None, {'templates': ['grid-route.v1']})
        ok(r['ok'] and any(s['pack'] == 'country.cameroon' for s in r['st']['skipped']), f'pack needing activity types this app lacks is skipped, not crashed ({r["st"]["skipped"][:1]})')
        pg2 = await ctx.new_page(); await pg2.add_init_script("Object.defineProperty(window,'indexedDB',{value:undefined})"); await pg2.goto(URL)
        r = await pg2.evaluate(MK, ['t12', None, None]); ok(r['ok'] and r['st']['storage'] == 'memory', 'no IndexedDB (private mode): works for the visit from memory')
        sha_ok = await pg.evaluate("(async()=>{const b=new TextEncoder().encode('Emmavengers ✓ é');const a=await EWLibrary.sha256(b);return a===EWLibrary.sha256js(b)})()")
        ok(sha_ok, 'built-in SHA-256 fallback (old browsers / http) matches WebCrypto')
        ok(not errs, f'no page errors {errs[:2]}')
        await br.close()
asyncio.run(main())
shutil.rmtree(T, ignore_errors=True)
print(f'\n{n[0] - len(fails)}/{n[0]} checks passed')
if fails: print('FAILED:'); [print(' -', f) for f in fails]
sys.exit(1 if fails else 0)
