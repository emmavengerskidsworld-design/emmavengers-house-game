"""Content library tests (no browser):  python3 tools/test_content.py
 1. the committed library is valid and up to date (the same check as tools/content_build.py --check)
 2. migration is lossless: frozen legacy files (tools/fixtures/legacy-v0) -> migrate -> compile -> hash-verified load
    -> legacy adapter gives back exactly the original files; and the committed library still equals them
    (skipped, with a note, once content/src has been edited on purpose after the migration)
 3. the validator catches each class of mistake (one small broken copy of the content per case)
 4. channels: 'live' ships published content only and drops links to unpublished countries
 5. registry: a changed record gets a new revision, a new release sequence, new file names only for changed packs;
    a removed id is retired and can never be reused; --check notices a stale library
 6. a tampered file is refused by the loader (hash check)"""
import os, sys, json, shutil, tempfile, copy, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content.source import Source
from content.validate import Validator
from content.compile import Build
from content import hydrate, legacy, migrate_v0
from content.common import load_json, write_json
import content_build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, SCHEMA, FIX = os.path.join(ROOT, 'content/src'), os.path.join(ROOT, 'content/schema/v1'), os.path.join(ROOT, 'tools/fixtures/legacy-v0')
SETTINGS = ('locales', 'taxonomy', 'capabilities', 'collections', 'build', 'rights')
fails, n = [], [0]
def ok(c, m):
    n[0] += 1
    print(('  ok  ' if c else '  FAIL ') + m)
    if not c: fails.append(m)

def tmp_src():
    d = tempfile.mkdtemp(prefix='ewc-'); shutil.copytree(SRC, os.path.join(d, 'src')); return d

def validate(src, channel=None, files=True):
    S = Source(src, ROOT); V = Validator(S, SCHEMA, channel=channel, check_files=files); return S, V, V.run()

def errors(issues): return [i for i in issues if i.sev == 'error']

def edit(src, rel, fn):
    p = os.path.join(src, rel); d = load_json(p); fn(d); write_json(p, d)

def rec(d, rid): return next(r for r in d['records'] if r['id'] == rid)

def quiet(f, *a):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()): return f(*a)

# Release 1 (2026-11-10): Emmanuel approved Cameroon for live, so review-state fields (status, reviewStatus, per-language
# status, editorial approval ref) legitimately differ from the frozen pre-Stage-1 drafts. Nothing the app renders differs.
def editorial_free(o, path=''):
    if isinstance(o, dict):
        return {k: editorial_free(v, path + '.' + k) for k, v in o.items()
                if not (k in ('status', 'reviewStatus') or (k == 'approvalRef' and path.endswith('.editorial')))}
    if isinstance(o, list): return [editorial_free(v, path + '[]') for v in o]
    return o

def fixtures(): return {k: load_json(os.path.join(FIX, k + '.json')) for k in ('lands', 'index', 'ui', 'cameroon', 'cameroon-quiz')}

def legacy_set(recs, locales):
    pk, bank = legacy.country(recs, 'ew.country.cameroon')
    return {'lands': legacy.lands(recs, locales), 'index': legacy.country_index(recs), 'ui': legacy.ui_strings(recs),
            'cameroon': pk, 'cameroon-quiz': bank}

# Key order is compared too (the app iterates some objects, e.g. options, lines, pages). One known exception: a land
# object's own keys (lands[i]) - only the optional 'm6' map-art entry moves; no code iterates a land's keys (grep: no
# Object.keys/entries/for-in over a land in world.js/country.js), so this cannot change behaviour.
ORDER_FREE = ('.lands[',)
def diff(a, b, path=''):
    if type(a) != type(b): return [f'{path}: {type(a).__name__} != {type(b).__name__}']
    if isinstance(a, dict):
        out = [f'{path}.{k}: only on one side' for k in set(a) ^ set(b)]
        if list(a) != list(b) and not out and not (path.startswith(ORDER_FREE) and path.count('.') == 1):
            out.append(f'{path}: key order differs')
        for k in a:
            if k in b: out += diff(a[k], b[k], f'{path}.{k}')
        return out
    if isinstance(a, list):
        if len(a) != len(b): return [f'{path}: {len(a)} items != {len(b)}']
        return [x for i, (p, q) in enumerate(zip(a, b)) for x in diff(p, q, f'{path}[{i}]')]
    return [] if a == b else [f'{path}: {a!r} != {b!r}']

print('1. committed library')
ok(quiet(content_build.main, ['--check']) == 0, 'content_build --check passes (valid + library up to date)')

print('2. lossless migration')
FX = fixtures()
d = tempfile.mkdtemp(prefix='ewm-'); src = os.path.join(d, 'src'); os.makedirs(src)
for s in SETTINGS: shutil.copy(os.path.join(SRC, s + '.json'), src)
for dd in ('core', 'countries/cameroon'):
    os.makedirs(os.path.join(src, dd)); shutil.copy(os.path.join(SRC, dd, 'pack.json'), os.path.join(src, dd))
migrate_v0.main(FIX, src)
S, V, iss = validate(src)
ok(not errors(iss), f'migrated content is valid ({len(S.records)} records)')
B = Build(S, V, None, channel='preview').run(); B.write(os.path.join(d, 'lib'), os.path.join(d, 'lock.json'))
cat, recs = hydrate.load(os.path.join(d, 'lib'))
got = legacy_set(recs, ['en', 'fr'])
for k in FX:
    dd = diff(got[k], FX[k]); ok(not dd, f'{k}: legacy shape identical to the original file' + (f' - {dd[:3]}' if dd else ''))
same_src = all(open(os.path.join(dp, f), 'rb').read() == open(os.path.join(SRC, os.path.relpath(os.path.join(dp, f), src)), 'rb').read()
               for dp, _, fs in os.walk(src) for f in fs)
if same_src:
    cat, recs = hydrate.load(os.path.join(ROOT, 'content/library'))
    got = legacy_set(recs, ['en', 'fr'])
    ok(all(editorial_free(got[k]) == editorial_free(FX[k]) for k in FX), 'committed content/library gives the app exactly the pre-Stage-1 data (review-state fields aside)')
else:
    print('  note content/src was edited after the migration: parity with the legacy files is no longer expected (skipped)')

print('3. validator catches mistakes')
Q = 'countries/cameroon/quiz.json'; LN = 'countries/cameroon/lines.json'; Q1 = 'ew.quiz.pilot-cameroon-q01'
def first_line(d): return d['records'][0]
CASES = [
    ('missing-text', 'a required French text is missing', Q, lambda d: rec(d, Q1)['payload']['prompt'].pop('fr')),
    ('locale', 'text in a language not in locales.json', Q, lambda d: rec(d, Q1)['payload']['prompt'].update({'de': 'Was?'})),
    ('answer', 'answer key is not one of the options', Q, lambda d: rec(d, Q1)['payload'].update({'answerKey': 'z'})),
    ('no-source', 'factual quiz item without a source', Q, lambda d: rec(d, Q1)['evidence'].update({'sources': []})),
    ('schema', 'unknown field (closed schema)', Q, lambda d: rec(d, Q1).update({'colour': 'red'})),
    ('id', 'malformed id', Q, lambda d: rec(d, Q1).update({'id': 'EW quiz 1'})),
    ('id-type', 'id prefix does not match the type', Q, lambda d: rec(d, Q1).update({'id': 'ew.story.pilot-x'})),
    ('duplicate-id', 'the same id twice', Q, lambda d: d['records'].append(copy.deepcopy(rec(d, Q1)))),
    ('unsafe-text', 'script/HTML in a text', Q, lambda d: rec(d, Q1)['payload']['hint'].update({'en': '<script>alert(1)</script>'})),
    ('markup', 'HTML tag where markup is not allowed', Q, lambda d: rec(d, Q1)['payload']['hint'].update({'en': 'A <i>flag</i>.', 'fr': 'Un <i>drapeau</i>.'})),
    ('ref', 'reference to a record that does not exist', LN, lambda d: first_line(d)['payload'].update({'speaker': 'ew.character.nobody'})),
    ('ref-type', 'reference to the wrong kind of record', LN, lambda d: first_line(d)['payload'].update({'speaker': 'ew.country.cameroon'})),
    ('missing-voice', 'changed spoken text has no recorded voice clip', LN, lambda d: first_line(d)['payload']['text'].update({'en': 'A brand new line nobody recorded yet.'})),
    (('tag', 'schema'), 'unknown age band', Q, lambda d: rec(d, Q1)['tags'].update({'ageBands': ['2-3']})),
    (('status', 'schema'), 'unknown status', Q, lambda d: rec(d, Q1).update({'status': 'maybe'})),
]
for code, what, rel, fn in CASES:
    t = tmp_src(); s = os.path.join(t, 'src'); edit(s, rel, fn)
    _, _, iss = validate(s); codes = {i.code for i in errors(iss)}; want = code if isinstance(code, tuple) else (code,)
    hit = bool(codes & set(want))
    ok(hit, f'{what} -> error "{"/".join(want)}"' + ('' if hit else f' (got {sorted(codes) or "no errors"})'))
    shutil.rmtree(t)
t = tmp_src(); s = os.path.join(t, 'src')
p = None
for dp, _, fs in os.walk(s):
    for f in fs:
        if f == 'pack.json': continue
        fp = os.path.join(dp, f); txt = open(fp, encoding='utf-8').read()
        if '{place}' in txt and p is None: p = fp
dd = load_json(p); hit = []
def strip(o):
    if isinstance(o, dict):
        if 'fr' in o and isinstance(o['fr'], str) and '{place}' in o['fr'] and not hit: o['fr'] = o['fr'].replace('{place}', 'ici'); hit.append(1)
        for v in o.values(): strip(v)
    elif isinstance(o, list):
        for v in o: strip(v)
strip(dd); write_json(p, dd); _, _, iss = validate(s)
ok(bool(hit) and 'placeholders' in {i.code for i in errors(iss)}, 'French text lost a {placeholder} -> error "placeholders"')
shutil.rmtree(t)
t = tmp_src(); s = os.path.join(t, 'src')
edit(s, 'countries/cameroon/pack.json', lambda d: d.update({'collection': 'countries.atlantis'}))
_, _, iss = validate(s); ok('collection' in {i.code for i in errors(iss)}, 'pack in an unknown collection -> error "collection"'); shutil.rmtree(t)
t = tmp_src(); s = os.path.join(t, 'src')
_, _, iss = validate(s, 'live')
ok(not errors(iss), 'the same content is valid for the live channel (drafts are simply left out)'); shutil.rmtree(t)

print('4. channels')
t = tmp_src(); s = os.path.join(t, 'src')
S, V, iss = validate(s, 'live'); B = Build(S, V, None, channel='live').run(); B.write(os.path.join(t, 'lib'), os.path.join(t, 'lock.json'))
cat, recs = hydrate.load(os.path.join(t, 'lib'))
ok(recs.get('ew.country.cameroon', {}).get('status') == 'published', 'published (owner-approved) Cameroon pilot is in the live library')
L = legacy.lands(recs, ['en', 'fr']); wl = next(x for x in L['lands'] if x['id'] == 'world')
ok(any(q.get('country') == 'cameroon' for q in wl['places']), 'World Land on live links to the published Cameroon')
shutil.rmtree(t)
# a country still in draft must not reach live (simulate by putting Cameroon back to draft)
t = tmp_src(); s = os.path.join(t, 'src')
edit(s, 'countries/cameroon/country.json', lambda d: rec(d, 'ew.country.cameroon').update({'status': 'draft'}))
S, V, iss = validate(s, 'live'); B = Build(S, V, None, channel='live').run(); B.write(os.path.join(t, 'lib'), os.path.join(t, 'lock.json'))
cat, recs = hydrate.load(os.path.join(t, 'lib'))
ok(all(r['status'] == 'published' for r in recs.values()), f'live library holds only published records ({len(recs)})')
ok('ew.country.cameroon' not in recs and not any(e['id'] == 'country.cameroon' for c in cat['collections'] for e in hydrate._read(os.path.join(t, 'lib'), c['index'])['packs']),
   'draft Cameroon pilot is not in the live library')
L = legacy.lands(recs, ['en', 'fr']); wl = next(x for x in L['lands'] if x['id'] == 'world')
ok(not any(q.get('type') == 'country' for q in wl['places']), 'World Land on live has no button to the unpublished country')
ok(len(L['lands']) == len(FX['lands']['lands']), 'all six lands still present on live')
shutil.rmtree(t)

print('5. registry: revisions, releases, retired ids, stale check')
t = tmp_src(); s = os.path.join(t, 'src'); lib, lock = os.path.join(t, 'lib'), os.path.join(t, 'lock.json')
args = ['--src', s, '--lib', lib, '--lock', lock, '--report', os.path.join(t, 'r.md'), '--quiet', '--no-files']
ok(quiet(content_build.main, args) == 0, 'fresh build in a temp folder')
L1 = load_json(lock); f1 = set(os.listdir(os.path.join(lib, 'packs')))
ok(quiet(content_build.main, args + ['--check']) == 0 and load_json(lock)['sequence'] == L1['sequence'], 'rebuilding unchanged content keeps the same release')
edit(s, Q, lambda d: rec(d, Q1)['payload']['hint'].update({'en': 'A flag stands for a whole country.'}))
ok(quiet(content_build.main, args + ['--check']) == 1, '--check fails when content/src changed but the library was not rebuilt')
quiet(content_build.main, args)
L2 = load_json(lock); f2 = set(os.listdir(os.path.join(lib, 'packs')))
ok(L2['records'][Q1]['rev'] == 2 and L2['records']['ew.country.cameroon']['rev'] == 1, 'only the changed record gets revision 2')
ok(L2['sequence'] == L1['sequence'] + 1, f'release sequence goes up ({L1["sequence"]} -> {L2["sequence"]})')
new = f2 - f1
ok(new and all(x.startswith('country.cameroon') for x in new) and not any(x.startswith('core') for x in new),
   f'only the Cameroon pack got new files ({sorted(new)})')
ok(f1 <= f2, 'the previous release files are kept on the server for rollback (retainReleases)')
ok(len(new) <= 5, f'at most 5 new files for a one-line edit (structure, its language files, asset list) - got {len(new)}')
Q2 = 'ew.quiz.pilot-cameroon-q02'
def drop_everywhere(root, rid):
    for dp, _, fs in os.walk(root):
        for f in fs:
            fp = os.path.join(dp, f); d = load_json(fp)
            def strip(o):
                if isinstance(o, dict):
                    if isinstance(o.get('records'), list): o['records'] = [r for r in o['records'] if not (isinstance(r, dict) and r.get('id') == rid)]
                    for v in o.values(): strip(v)
                elif isinstance(o, list):
                    o[:] = [v for v in o if v != rid]
                    for v in o: strip(v)
            before = json.dumps(d); strip(d)
            if json.dumps(d) != before: write_json(fp, d)
t2 = tmp_src(); s2 = os.path.join(t2, 'src'); edit(s2, Q, lambda d: d['records'].remove(rec(d, Q2)))
_, _, iss = validate(s2, files=False)
ok('ref' in {i.code for i in errors(iss)}, 'deleting a record that others still use -> error "ref"'); shutil.rmtree(t2)
drop_everywhere(s, Q2)
rc = quiet(content_build.main, args); L3 = load_json(lock)
ok(rc == 0 and Q2 in L3['retired'], 'a removed id is recorded as retired in the registry lock')
edit(s, Q, lambda d: d['records'].append(dict(copy.deepcopy(rec(d, Q1)), id=Q2)))
try: rc2 = quiet(content_build.main, args)
except SystemExit: rc2 = 'refused'
ok(rc2 == 'refused', 'reusing a retired id is refused (ids are never reused)')
shutil.rmtree(t)

print('6. tampered file')
t = tempfile.mkdtemp(prefix='ewt-'); shutil.copytree(os.path.join(ROOT, 'content/library'), os.path.join(t, 'lib'))
cat = load_json(os.path.join(t, 'lib/catalog.json')); ix = load_json(os.path.join(t, 'lib', cat['collections'][0]['index']['path']))
pf = os.path.join(t, 'lib', ix['packs'][0]['file']['path']); b = open(pf, 'rb').read(); open(pf, 'wb').write(b.replace(b'"', b"'", 1) if False else b[:-2] + b' }')
try: hydrate.load(os.path.join(t, 'lib')); ok(False, 'tampered pack refused')
except hydrate.LibraryError as e: ok('hash' in str(e).lower(), f'tampered pack refused ({str(e)[:70]})')
shutil.rmtree(t)

print(f'\n{n[0] - len(fails)}/{n[0]} checks passed')
if fails:
    print('FAILED:'); [print(' -', f) for f in fails]
sys.exit(1 if fails else 0)
