"""Content validator: JSON Schema (Draft 2020-12) + cross-record checks. Produces a list of Issues.

Severity: error = the build must stop; warn = allowed but listed in the report for a human; info = coverage facts."""
import json, os, re
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from .common import ID_RE, LOCALE_RE, is_lt, walk_lt, vh, canonical
from . import legacy

PLACEHOLDER = re.compile(r'\{(\w+)\}')
TAG = re.compile(r'<\s*/?\s*([a-zA-Z][a-zA-Z0-9]*)[^>]*>')
BAD = re.compile(r'javascript:|\bon[a-z]+\s*=|<\s*script|<\s*iframe|data:text/html', re.I)
TYPE_PREFIX = {'world': ['world'], 'land': ['land'], 'deck': ['deck'], 'library': ['library'], 'lexicon': ['lexicon'],
               'character': ['character'], 'strings': ['ui', 'strings'], 'country': ['country'], 'topic': ['topic', 'region'],
               'source': ['source'], 'lesson': ['lesson'], 'learn-card': ['card'], 'activity': ['activity'],
               'quiz-bank': ['quizbank'], 'quiz-item': ['quiz'], 'story': ['story'], 'line': ['line'], 'media': ['media']}
# (record type, path regex) -> required target type(s). Paths use the walk() notation below.
REF_TYPES = [
    ('*', r'^tags\.topics\[\d+\]$', {'country', 'topic'}),
    ('*', r'^evidence\.sources\[\d+\]$', {'source'}),
    ('world', r'^payload\.lands\[\d+\]$', {'land'}),
    ('land', r'^payload\.places\[\d+\]\.(deck|objects)$', {'deck'}),
    ('land', r'^payload\.places\[\d+\]\.country$', {'country'}),
    ('library', r'^payload\.sections\[\d+\]\.source\.deck$', {'deck'}),
    ('country', r'^payload\.hub\.\w+$', {'line'}),
    ('country', r'^payload\.learn\.\w+$', {'lesson'}),
    ('country', r'^payload\.play\[\d+\]$', {'activity'}),
    ('country', r'^payload\.stories\[\d+\]$', {'story'}),
    ('country', r'^payload\.lines\[\d+\]$', {'line'}),
    ('country', r'^payload\.media\[\d+\]$', {'media'}),
    ('country', r'^payload\.quiz\.bank$', {'quiz-bank'}),
    ('lesson', r'^payload\.cards\[\d+\]$', {'learn-card'}),
    ('learn-card', r'^payload\.image$', {'media'}),
    ('*', r'^payload\.lines\[\d+\]$', {'line'}),
    ('line', r'^payload\.speaker$', {'character'}),
    ('quiz-bank', r'^payload\.items\[\d+\]$', {'quiz-item'}),
    ('quiz-bank', r'^payload\.sources\[\d+\]$', {'source'}),
    ('activity', r'^payload\.claimFromQuiz$', {'quiz-item'}),
    ('media', r'^payload\.assetId$', {'media'}),
]


class Issue:
    def __init__(self, sev, code, where, msg):
        self.sev, self.code, self.where, self.msg = sev, code, where, msg

    def __repr__(self):
        return f'{self.sev.upper():5} {self.code:18} {self.where}: {self.msg}'


def walk(obj, path=''):
    """Yield (path, value) for every scalar."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f'{path}.{k}' if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f'{path}[{i}]')
    else:
        yield path, obj


def schema_registry(schema_dir):
    res = []
    for f in sorted(os.listdir(schema_dir)):
        if f.endswith('.schema.json'):
            s = json.load(open(os.path.join(schema_dir, f), encoding='utf-8'))
            res.append((s['$id'], Resource.from_contents(s)))
    reg = Registry().with_resources(res)
    by_name = {f[:-12]: json.load(open(os.path.join(schema_dir, f), encoding='utf-8')) for f in os.listdir(schema_dir) if f.endswith('.schema.json')}
    return reg, by_name


class Validator:
    def __init__(self, src, schema_dir, channel=None, check_files=True):
        self.S = src
        self.issues = []
        self.reg, self.schemas = schema_registry(schema_dir)
        self.check_files = check_files
        self.cfg = src.cfg
        self.channel = channel or self.cfg.get('build', {}).get('channel', 'preview')
        self.stats = {}

    def add(self, sev, code, where, msg):
        self.issues.append(Issue(sev, code, where, msg))

    def schema_errors(self, name, doc, where):
        v = Draft202012Validator(self.schemas[name], registry=self.reg)
        errs = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
        for e in errs[:20]:
            p = '.'.join(str(x) for x in e.absolute_path) or '(top)'
            msg = e.message if len(e.message) < 300 else e.message[:300] + '...'
            self.add('error', 'schema', where, f'{p}: {msg}')
        return bool(errs)

    # ------------------------------------------------------------------
    def run(self):
        S, cfg = self.S, self.cfg
        for e in S.errors:
            self.add('error', 'load', 'content/src', e)
        for c in ('locales', 'taxonomy', 'capabilities', 'collections', 'build', 'rights'):
            self.schema_errors(c, cfg.get(c, {}), f'content/src/{c}.json')
        for rel, doc, kind in S.raw_files:
            self.schema_errors(kind, doc, rel)
        for rid, a, b in S.duplicates:
            self.add('error', 'duplicate-id', f'{b[1]}', f'{rid} is already defined in {a[1]}')
        self.locales = set(S.locales)
        self.tax = cfg.get('taxonomy', {})
        self.cap = cfg.get('capabilities', {})
        chan = cfg.get('build', {}).get('channels', {}).get(self.channel)
        if not chan:
            self.add('error', 'channel', 'content/src/build.json', f'unknown channel {self.channel}')
            chan = {'statuses': []}
        self.allowed = set(chan['statuses'])
        colls = {c['id'] for c in cfg.get('collections', {}).get('collections', [])}
        for pid, P in S.packs.items():
            if P['meta'].get('collection') not in colls:
                self.add('error', 'collection', P['dir'] + '/pack.json', f'collection {P["meta"].get("collection")} is not in collections.json')
            for l in P['meta'].get('locales', {}).get('required', []):
                if l not in self.locales:
                    self.add('error', 'locale', P['dir'] + '/pack.json', f'required locale {l} is not in locales.json')
            sm = P['meta'].get('summary')
            if sm and S.pack_of(sm) != pid:
                self.add('error', 'summary', P['dir'] + '/pack.json', f'summary record {sm} is not in this pack')
        for rid, r in S.records.items():
            self.check_record(rid, r)
        self.check_refs()
        self.check_assets_and_voice()
        return self.issues

    # ------------------------------------------------------------------
    def check_record(self, rid, r):
        S = self.S
        w = S.where(rid)
        if not isinstance(rid, str) or not ID_RE.match(rid):
            self.add('error', 'id', w, f'id {rid!r} does not match ew.<type>.<slug> (lower-case, digits, dot or hyphen)')
            return
        if self.schema_errors('record', r, w):
            return
        t = r['type']
        if rid.split('.')[1] not in TYPE_PREFIX.get(t, []):
            self.add('error', 'id-type', w, f'a {t} id must start with ew.{TYPE_PREFIX[t][0]}.')
        n = len(canonical(r))
        if n > self.cfg['build']['budgets']['recordBytes']:
            self.add('error', 'budget', w, f'record is {n} bytes (limit {self.cfg["build"]["budgets"]["recordBytes"]})')
        # tags against the closed taxonomy
        T, X = r['tags'], self.tax
        if T.get('land') is not None and T['land'] not in X['lands']:
            self.add('error', 'tag', w, f'land {T["land"]!r} not in taxonomy')
        for k, allowed in (('relatedLands', 'lands'), ('subjects', 'subjects'), ('regions', 'regions'), ('sensitivity', 'sensitivity'), ('ageBands', 'ageBands'), ('modes', 'modes')):
            for v in T.get(k, []):
                if v not in X[allowed]:
                    self.add('error', 'tag', w, f'{k} value {v!r} not in taxonomy.{allowed}')
        if T.get('difficulty') not in (None, *X['difficulty']):
            self.add('error', 'tag', w, f'difficulty {T["difficulty"]!r} not in taxonomy')
        if r['status'] not in X['statuses']:
            self.add('error', 'status', w, f'status {r["status"]}')
        # languages
        pack = S.packs[S.pack_of(rid)]['meta']
        req = set(pack.get('locales', {}).get('required', [])) | set(r.get('l10n', {}).get('required', []))
        req.add(r['sourceLanguage'])
        if r['sourceLanguage'] not in self.locales:
            self.add('error', 'locale', w, f'sourceLanguage {r["sourceLanguage"]} not in locales.json')
        for lg in r.get('l10n', {}):
            if lg != 'required' and lg not in self.locales:
                self.add('error', 'locale', w, f'l10n has unknown locale {lg}')
        markup = self.cap.get('markupFields', {})
        for path, lt in walk_lt({'payload': r['payload'], 'tags': r['tags']}, self.locales):
            for lg in lt:
                if lg not in self.locales:
                    self.add('error', 'locale', w, f'{path}: language {lg!r} is not in locales.json (add it there first)')
            miss = sorted(req - set(lt))
            if miss:
                self.add('error', 'missing-text', w, f'{path}: no {"/".join(miss)} text (required for this pack)')
            ph = {lg: set(PLACEHOLDER.findall(s)) for lg, s in lt.items()}
            if len({frozenset(v) for v in ph.values()}) > 1:
                self.add('error', 'placeholders', w, f'{path}: placeholders differ between languages {ph}')
            for lg, s in lt.items():
                self.check_text(w, f'{path}.{lg}', s, None)
        for path, v in walk(r['payload'], 'payload'):
            if isinstance(v, str) and not ID_RE.match(v):
                field = path.rsplit('.', 1)[-1]
                self.check_text(w, path, v, markup.get(field))
        # sources for facts
        ev = r.get('evidence', {})
        factual = ev.get('factual', t in ('quiz-item',) or (t == 'learn-card' and r['payload'].get('kind') == 'info'))
        if factual and not ev.get('sources'):
            legacy_rec = r.get('review', {}).get('legacy')
            self.add('warn' if legacy_rec else 'error', 'no-source', w, 'states facts but cites no source')
        if t == 'deck' and r['payload']['kind'] in ('animal', 'country') and not ev.get('sources'):
            self.add('warn', 'no-source', w, f'{len(r["payload"]["items"])} {r["payload"]["kind"]} fact cards cite no sources (legacy content)')
        if t == 'source':
            p = r['payload']
            if not p.get('url') and not p.get('note'):
                self.add('error', 'source', w, 'a source needs a url or a note saying what it is')
            elif not p.get('url'):
                self.add('info', 'source-offline', w, f'editorial source without a web link: {p.get("note") or p["key"]}')
            if p.get('url') and not p.get('checkedOn'):
                self.add('warn', 'source-unchecked', w, 'url has no checkedOn date')
        # per type
        getattr(self, 'type_' + t.replace('-', '_'), lambda *a: None)(rid, r, w)
        # stale translations
        for lg, st in r.get('l10n', {}).items():
            if lg != 'required' and isinstance(st, dict) and st.get('sourceRevision') and r.get('revision') and st['sourceRevision'] < r['revision']:
                self.add('warn', 'stale-translation', w, f'{lg} was made from revision {st["sourceRevision"]}, record is now revision {r["revision"]}')

    def check_text(self, w, path, s, allowed_tags):
        if BAD.search(s):
            self.add('error', 'unsafe-text', w, f'{path}: looks like script/HTML: {s[:60]!r}')
            return
        tags = TAG.findall(s)
        if tags:
            bad = [x for x in tags if not allowed_tags or x.lower() not in allowed_tags]
            if bad:
                self.add('error', 'markup', w, f'{path}: HTML tags {bad} are not allowed here: {s[:60]!r}')
            else:
                self.add('info', 'markup', w, f'{path}: allowed markup {tags} in {s!r}')
        if len(s) > self.cfg['build']['budgets']['stringChars']:
            self.add('error', 'budget', w, f'{path}: text longer than {self.cfg["build"]["budgets"]["stringChars"]} characters')
        if s != s.strip() or '  ' in s:
            self.add('warn', 'whitespace', w, f'{path}: extra spaces in {s[:60]!r}')

    # ---- type checks -------------------------------------------------
    def type_land(self, rid, r, w):
        C = self.cap
        keys = set()
        for q in r['payload']['places']:
            if q['key'] in keys: self.add('error', 'duplicate-key', w, f'place {q["key"]} twice')
            keys.add(q['key'])
            if q['type'] not in C['placeTypes']:
                self.add('error', 'capability', w, f'place {q["key"]}: type {q["type"]!r} is not something the app can open ({C["placeTypes"]})')
            if q['type'] == 'link' and q.get('go') not in C['modules']:
                self.add('error', 'capability', w, f'place {q["key"]}: go={q.get("go")!r} is not a known module {C["modules"]}')
            if q['type'] == 'quiz' and q.get('mode') not in C.get('placeQuizModes', []):
                self.add('error', 'capability', w, f'place {q["key"]}: quiz mode {q.get("mode")!r} unknown')
            if q.get('ask') and q.get('deck') in self.S.records:
                items = self.S.records[q['deck']]['payload']['items']
                fields = set().union(*[set(i) for i in items]) | {'lname'}
                for lg, s in q['ask'].items():
                    for v in PLACEHOLDER.findall(s):
                        if v not in fields:
                            self.add('error', 'placeholders', w, f'place {q["key"]}: {{{v}}} is not a field of the deck items')
        if r['tags'].get('land') != r['payload']['key']:
            self.add('error', 'tag', w, 'tags.land must equal the land key')

    def type_deck(self, rid, r, w):
        p = r['payload']
        if p['kind'] not in self.cap.get('deckKinds', []):
            self.add('error', 'capability', w, f'deck kind {p["kind"]!r} unknown')
        seen = set()
        for it in p['items']:
            k = str(it.get('id', it.get('n')))
            if k in seen: self.add('error', 'duplicate-key', w, f'item {k} twice')
            seen.add(k)
        if p['kind'] == 'number':
            objs = {i['id'] for i in self.S.records.get('ew.deck.objects', {}).get('payload', {}).get('items', [])}
            for it in p['items']:
                if it.get('obj') and it['obj'] not in objs:
                    self.add('error', 'ref', w, f'number {it.get("n")}: object {it["obj"]!r} is not in ew.deck.objects')

    def type_library(self, rid, r, w):
        for s in r['payload']['sections']:
            m = s['source'].get('module')
            if m and m not in self.cap['modules']:
                self.add('error', 'capability', w, f'shelf {s["key"]}: module {m!r} unknown')

    def type_quiz_item(self, rid, r, w):
        p = r['payload']
        if p['responseType'] not in self.cap['quizResponseTypes']:
            planned = p['responseType'] in self.cap.get('plannedQuizResponseTypes', [])
            self.add('error', 'capability', w, f'responseType {p["responseType"]} is {"planned but not built yet" if planned else "unknown"}')
        if p['answerKey'] not in p['options']:
            self.add('error', 'answer', w, f'answerKey {p["answerKey"]!r} is not one of the options {list(p["options"])}')
        langs = set().union(*[set(t) for t in p['options'].values()])
        for lg in langs:
            texts = [t.get(lg) for t in p['options'].values() if t.get(lg)]
            if len(texts) != len(set(x.strip().lower() for x in texts)):
                self.add('error', 'answer', w, f'{lg}: two options have the same text')
        for f in ('hint', 'feedback'):
            if f not in p: self.add('warn', 'quiz', w, f'no {f}')

    def type_activity(self, rid, r, w):
        p = r['payload']
        if p['template'] not in self.cap['activityTemplates']:
            self.add('error', 'capability', w, f'template {p["template"]} is not built into the app {self.cap["activityTemplates"]}')
            return
        for q in p.get('questions', []) + ([p['next']] if p.get('next') else []):
            if q['key'] not in q['options']:
                self.add('error', 'answer', w, f'answer {q["key"]!r} not in options')
        if p['template'] == 'map-select.v1':
            ids = {n['id'] for n in p['neighbours']}
            for q in p['prompts']:
                bad = [a for a in q['accept'] if a not in ids]
                if bad: self.add('error', 'answer', w, f'prompt {q["dir"]}: accepts unknown {bad}')
                at = {n['id'] for n in p['neighbours'] if n['pos'] == q['dir']}
                if set(q['accept']) != at:
                    self.add('warn', 'answer', w, f'prompt {q["dir"]}: accepts {q["accept"]} but neighbours placed there are {sorted(at)}')
        if p['template'] == 'grid-route.v1':
            topic = self.topic_of(r)
            grid = topic and topic['payload'].get('practiceMap', {}).get('rows')
            if grid:
                cells = [c['id'] for row in grid for c in row]
                if p['goal'] not in cells: self.add('error', 'answer', w, f'goal {p["goal"]!r} is not on the practice map')
                y, x = p['start']
                if y >= len(grid) or x >= len(grid[0]): self.add('error', 'answer', w, f'start {p["start"]} is off the map')

    def type_story(self, rid, r, w):
        p = r['payload']
        if p['classification'] not in self.cap.get('storyClassifications', []):
            self.add('error', 'capability', w, f'classification {p["classification"]} unknown')
        if p['classification'] == 'bible-retelling':
            if not p.get('sourcePassages'): self.add('error', 'faith', w, 'a Bible retelling must name its passages (sourcePassages)')
            if 'bible-retelling' not in r['tags'].get('sensitivity', []): self.add('error', 'faith', w, 'a Bible retelling must carry sensitivity bible-retelling')

    def type_media(self, rid, r, w):
        if r['payload']['kind'] not in self.cap.get('mediaKinds', []):
            self.add('error', 'capability', w, f'media kind {r["payload"]["kind"]} unknown')
        if r['payload']['kind'] == 'placeholder':
            self.add('info', 'placeholder-art', w, f'placeholder picture: {r["payload"]["label"].get("en")}')

    def type_lesson(self, rid, r, w):
        for c in r['payload']['cards']:
            cr = self.S.records.get(c)
            if cr and not set(cr['tags']['ageBands']) <= set(r['tags']['ageBands']):
                self.add('error', 'tag', w, f'card {c} is for {cr["tags"]["ageBands"]}, outside the lesson ages {r["tags"]["ageBands"]}')

    def type_line(self, rid, r, w):
        for lg, s in r['payload']['text'].items():
            if len(s) > 160: self.add('warn', 'long-line', w, f'{lg}: guide line is {len(s)} characters (keep lines short for children)')

    def type_lexicon(self, rid, r, w):
        pass  # checked against spoken lines in check_assets_and_voice

    def topic_of(self, r):
        for t in r['tags'].get('topics', []):
            if t in self.S.records: return self.S.records[t]
        return None

    # ---- references ----------------------------------------------------
    def check_refs(self):
        S = self.S
        self.excluded = set(S.records) - S.in_channel(self.allowed)
        rules = [(t, re.compile(p), want) for t, p, want in REF_TYPES]
        self.soft_links = []
        for rid, r in S.records.items():
            if not isinstance(r, dict) or 'type' not in r: continue
            w = S.where(rid)
            mypack = S.pack_of(rid)
            for path, v in walk({k: r.get(k) for k in ('tags', 'evidence', 'payload')}):
                if not isinstance(v, str) or not v.startswith('ew.'): continue
                if not ID_RE.match(v):
                    self.add('error', 'ref', w, f'{path}: {v!r} looks like an id but is malformed'); continue
                tgt = S.records.get(v)
                if tgt is None:
                    self.add('error', 'ref', w, f'{path}: points at {v}, which does not exist'); continue
                want = next((wt for t, rx, wt in rules if (t == '*' or t == r['type']) and rx.match(path)), None)
                if want and tgt['type'] not in want:
                    self.add('error', 'ref-type', w, f'{path}: {v} is a {tgt["type"]}, expected {"/".join(sorted(want))}')
                tp = S.pack_of(v)
                soft = r['type'] == 'land' and path.endswith('.country')
                if tp != mypack and tp != 'core':
                    if soft: self.soft_links.append((rid, v))
                    else: self.add('error', 'pack-dependency', w, f'{path}: {v} is in pack {tp}; a pack may only use its own records and core')
                if rid not in self.excluded and v in self.excluded and not soft and path != 'payload.assetId':
                    self.add('error', 'ref-status', w, f'{path}: {v} has status {tgt["status"]}, which the {self.channel} channel leaves out')
                if tgt.get('status') == 'withdrawn' and rid not in self.excluded:
                    self.add('error', 'withdrawn', w, f'{path}: uses withdrawn record {v}')

    # ---- files on disk: pictures and voice clips -------------------------
    def check_assets_and_voice(self):
        if not self.check_files:
            return
        S, root = self.S, self.S.root
        rules = sorted(self.cfg.get('rights', {}).get('rules', []), key=lambda x: -len(x['prefix']))
        self.assets = {}
        map2 = os.path.join(root, 'img', 'world', 'map2')
        for rid, r in S.records.items():
            if 'payload' not in r: continue
            w = S.where(rid)
            for path, v in walk(r['payload'], 'payload'):
                if not isinstance(v, str): continue
                if re.match(r'^(img|voice|icons|fonts)/', v):
                    if not os.path.isfile(os.path.join(root, v)):
                        self.add('error', 'missing-file', w, f'{path}: file {v} does not exist')
                    elif not any(v.startswith(x['prefix']) for x in rules):
                        self.add('error', 'rights', w, f'{path}: no rights rule covers {v} (content/src/rights.json)')
                    self.assets.setdefault(v, set()).add(S.pack_of(rid))
                elif path.endswith(('.icon2', '.bg2', '.art2')) and not os.path.isfile(os.path.join(map2, v)):
                    self.add('info', 'optional-art', w, f'{path}: optional new art {v} not made yet (old art is used)')
        # spoken lines -> voice clips, using the same rules as the app
        self.spoken = {}
        recs = {rid: S.records[rid] for rid in S.in_channel(self.allowed)}
        try:
            L = legacy.lands(recs, self.locales)
            for t in legacy.world_spoken(L): self.spoken.setdefault(t, ('core', 'en'))
            ui = legacy.ui_strings(recs) if 'ew.ui.country-player' in recs else None
            for r in recs.values():
                if r['type'] == 'country':
                    pk, bank = legacy.country(recs, r['id'])
                    for t, lg in legacy.country_spoken(pk, bank, ui): self.spoken.setdefault(t, (S.pack_of(r['id']), lg))
        except Exception as e:
            self.add('error', 'adapter', 'content/src', f'could not build the app view of the content: {type(e).__name__}: {e}')
            return
        missing = [(t, p, lg) for t, (p, lg) in self.spoken.items() if not os.path.isfile(os.path.join(root, 'voice', vh(t) + '.mp3'))]
        for t, p, lg in missing[:40]:
            self.add('error', 'missing-voice', p, f'[{lg}] no voice clip voice/{vh(t)}.mp3 for: {t[:80]!r}')
        if len(missing) > 40:
            self.add('error', 'missing-voice', 'content', f'... and {len(missing) - 40} more lines without voice clips')
        self.stats['spoken'] = len(self.spoken)
        self.stats['voiceMissing'] = len(missing)
        lex = S.records.get('ew.lexicon.letter-sounds')
        if lex:
            for e in lex['payload']['entries']:
                if e['text'] not in self.spoken:
                    self.add('warn', 'lexicon', S.where(lex['id']), f'pronunciation entry {e["text"]!r} is not a spoken line')
