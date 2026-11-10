"""Compile content/src into the shipped library (content/library):

  catalog.json                       root of the release (small, the only file whose name never changes)
  indexes/<collection>.<h>.json      one small index per collection, listing its packs
  packs/<pack>.<h>.json              structure: language-neutral records; every text is {"$t": n}
  packs/<pack>@<lang>.<h>.json       the texts of that pack in one language (n-th entry = text n), bound to the structure hash
  packs/<pack>.assets.<h>.json       every picture / voice clip the pack needs, with bytes + SHA-256

<h> = first 16 hex digits of the file's SHA-256, so files are immutable: a changed pack gets a new name and the
app downloads only what changed. content/registry.lock.json keeps record + pack revisions, retired ids and the
release history (sequence numbers only go up)."""
import copy, datetime, os, re, shutil
from .common import FORMAT, SCHEMA_VERSION, dumps, canonical, sha256, is_lt, map_lt, walk_lt, vh, load_json, write_json
from . import legacy

H = 16


def content_hash(r):
    return sha256(canonical({k: r.get(k) for k in ('type', 'sourceLanguage', 'tags', 'evidence', 'payload')}))


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


class Build:
    def __init__(self, src, validator, lock, channel=None):
        self.S, self.V = src, validator
        self.lock = copy.deepcopy(lock) if lock else {'records': {}, 'retired': {}, 'packs': {}, 'releases': [], 'sequence': 0}
        self.channel = channel or src.cfg['build']['channel']
        self.files = {}          # relpath -> bytes
        self.notes = []          # human notes for the report
        self.pruned = []
        self.stats = {}

    def included(self):
        return self.S.in_channel(self.S.cfg['build']['channels'][self.channel]['statuses'])

    def run(self):
        S, cfg = self.S, self.S.cfg
        locales = [l['tag'] for l in cfg['locales']['locales']]
        inc = self.included()
        excluded = sorted(set(S.records) - inc)
        for rid in excluded:
            self.notes.append(f'left out of channel {self.channel}: {rid} ({S.records[rid]["status"]})')
        # ---- revisions (registry) ----
        L = self.lock
        for rid in sorted(S.records):
            if rid in L['retired']:
                raise SystemExit(f'ERROR {rid} was retired (sequence {L["retired"][rid].get("sequence")}); ids are never reused - choose a new id')
        for rid in S.records:
            h = content_hash(S.records[rid])
            e = L['records'].get(rid)
            if e is None:
                L['records'][rid] = {'rev': 1, 'hash': h, 'type': S.records[rid]['type']}
            elif e['hash'] != h:
                e['rev'] += 1; e['hash'] = h
        gone = sorted(set(L['records']) - set(S.records))
        for rid in gone:
            L['retired'][rid] = {'lastRevision': L['records'][rid]['rev'], 'type': L['records'][rid].get('type'), 'sequence': L.get('sequence', 0) + 1}
            del L['records'][rid]
            self.notes.append(f'retired id {rid} (removed from source; it can never be reused)')
        recs = {}
        for rid in inc:
            r = copy.deepcopy(S.records[rid])
            r['revision'] = L['records'][rid]['rev']
            recs[rid] = r
        # soft links to left-out records (World Land place -> draft country on the live channel) are pruned
        for r in recs.values():
            if r['type'] == 'land':
                keep = []
                for q in r['payload']['places']:
                    if q.get('country') and q['country'] not in recs:
                        self.pruned.append(f'{r["id"]} place {q["key"]} (points at {q["country"]}, not in channel {self.channel})')
                        continue
                    keep.append(q)
                r['payload']['places'] = keep
        # ---- packs ----
        coll_packs = {}
        caps = set(cfg['capabilities']['activityTemplates'])
        for pid in sorted(S.packs, key=lambda p: (p != 'core', p)):
            P = S.packs[pid]
            ids = [rid for rid in P['records'] if rid in recs]
            if not ids:
                self.notes.append(f'pack {pid} is empty in channel {self.channel} and is not published')
                continue
            entry = self.build_pack(pid, P, [recs[i] for i in ids], locales, recs)
            coll_packs.setdefault(P['meta']['collection'], []).append(entry)
        # ---- indexes + catalog ----
        cols = []
        for c in cfg['collections']['collections']:
            packs = coll_packs.get(c['id'])
            if not packs: continue
            idx = {'format': FORMAT, 'collection': c['id'], 'packs': packs}
            ref = self.put(f'indexes/{c["id"]}', idx)
            o = {'id': c['id'], 'kind': c['kind']}
            for k in ('land', 'region', 'title'):
                if k in c: o[k] = c[k]
            o['index'] = ref; o['packs'] = len(packs)
            cols.append(o)
        bcfg = cfg['build']
        cat = {'format': FORMAT, 'schemaVersion': SCHEMA_VERSION, 'channel': self.channel, 'sequence': 0, 'issued': '',
               'player': {k: v for k, v in bcfg['player'].items()},
               'locales': [{k: l[k] for k in ('tag', 'name', 'dir', 'status')} for l in cfg['locales']['locales']],
               'collections': cols, 'withdrawals': []}
        body = sha256(canonical({k: v for k, v in cat.items() if k not in ('sequence', 'issued')}))
        last = L['releases'][-1] if L['releases'] else None
        if last and last['contentHash'] == body and last.get('channel') == self.channel:
            cat['sequence'], cat['issued'] = last['sequence'], last['issued']
        else:
            L['sequence'] = L.get('sequence', 0) + 1
            cat['sequence'], cat['issued'] = L['sequence'], now_utc()
        b = dumps(cat)
        self.files['catalog.json'] = b
        if not last or last['sequence'] != cat['sequence']:
            L['releases'].append({'sequence': cat['sequence'], 'issued': cat['issued'], 'channel': self.channel, 'contentHash': body,
                                  'catalogSha256': sha256(b), 'files': sorted(self.files)})
        keep = bcfg.get('retainReleases', 2)
        L['releases'] = L['releases'][-keep:]
        self.catalog = cat
        self.recs = recs
        return self

    def put(self, base, obj):
        b = dumps(obj)
        h = sha256(b)
        path = f'{base}.{h[:H]}.json'
        self.files[path] = b
        return {'path': path, 'sha256': h, 'bytes': len(b)}

    def build_pack(self, pid, P, rs, locales, allrecs):
        S, cfg = self.S, self.S.cfg
        table, index = [], {}

        def ref(lt):
            k = canonical(lt)
            if k not in index:
                index[k] = len(table); table.append(lt)
            return {'$t': index[k]}

        out = []
        for r in rs:
            c = {k: r[k] for k in ('id', 'type', 'revision', 'status', 'sourceLanguage') if k in r}
            c['tags'] = map_lt(r['tags'], set(locales), ref)
            for k in ('evidence', 'review', 'l10n'):
                if k in r: c[k] = r[k]
            c['payload'] = map_lt(r['payload'], set(locales), ref)
            c['h'] = self.lock['records'][r['id']]['hash'][:H]
            out.append(c)
        struct = {'format': FORMAT, 'schemaVersion': SCHEMA_VERSION, 'pack': pid, 'revision': 0, 'strings': len(table), 'records': out}
        # pack revision: bump when structure or any language file changes
        sig = sha256(canonical({'records': out, 'table': table}))
        pe = self.lock['packs'].get(pid)
        if pe is None:
            pe = self.lock['packs'][pid] = {'rev': 1, 'hash': sig}
        elif pe['hash'] != sig:
            pe['rev'] += 1; pe['hash'] = sig
        struct['revision'] = pe['rev']
        sref = self.put(f'packs/{pid}', struct)
        if sref['bytes'] > cfg['build']['budgets']['packBytes']:
            raise SystemExit(f'ERROR pack {pid} is {sref["bytes"]} bytes, over the {cfg["build"]["budgets"]["packBytes"]} budget: split it')
        locs = {}
        for lg in locales:
            strs = [lt.get(lg) for lt in table]
            n = sum(1 for x in strs if x is not None)
            if not n: continue
            lr = self.put(f'packs/{pid}@{lg}', {'format': FORMAT, 'pack': pid, 'locale': lg, 'struct': sref['sha256'], 'strings': strs})
            lr['coverage'] = round(n / len(table), 4) if table else 1.0
            locs[lg] = lr
        # assets: pictures referenced by records + voice clips of the lines this pack speaks
        files = {}
        rules = sorted(cfg['rights']['rules'], key=lambda x: -len(x['prefix']))
        def asset(path, kind, locale=None):
            full = os.path.join(S.root, path)
            if path in files or not os.path.isfile(full): return
            data = open(full, 'rb').read()
            rule = next((x for x in rules if path.startswith(x['prefix'])), None)
            f = {'path': path, 'sha256': sha256(data), 'bytes': len(data), 'kind': kind}
            if locale: f['locale'] = locale
            if rule: f['rights'] = rule['licence']
            files[path] = f
        for r in rs:
            for _, v in _scalars(r['payload']):
                if isinstance(v, str) and re.match(r'^img/.+\.(webp|jpg|jpeg|png)$', v): asset(v, 'image')
        for t, (p, lg) in sorted(getattr(self.V, 'spoken', {}).items()):
            if p == pid: asset(f'voice/{vh(t)}.mp3', 'audio', lg)
        aref = self.put(f'packs/{pid}.assets', {'format': FORMAT, 'pack': pid, 'files': sorted(files.values(), key=lambda f: f['path'])})
        used = sorted({r['payload'].get('template') for r in rs if r['type'] == 'activity'} - {None})
        e = {'id': pid, 'revision': pe['rev'], 'preload': bool(P['meta'].get('preload')), 'records': len(out),
             'file': sref, 'locales': locs, 'assets': aref,
             'requires': {'schema': SCHEMA_VERSION.split('.')[0], 'templates': used,
                          'locales': P['meta']['locales']['required']}}
        sm = P['meta'].get('summary')
        if sm and sm in allrecs:
            R = allrecs[sm]
            e['summary'] = {'id': R['id'], 'type': R['type'], 'revision': R['revision'], 'name': R['payload'].get('name'), 'slug': R['payload'].get('slug'),
                            'tags': {k: R['tags'][k] for k in ('land', 'regions', 'ageBands', 'modes') if k in R['tags']}}
        elif P['meta'].get('title'):
            e['summary'] = {'name': P['meta']['title']}
        self.stats[pid] = {'records': len(out), 'strings': len(table), 'bytes': sref['bytes'],
                           'locales': {lg: (v['bytes'], v['coverage']) for lg, v in locs.items()},
                           'assets': len(files), 'assetBytes': sum(f['bytes'] for f in files.values())}
        return e

    def write(self, lib_dir, lock_path):
        os.makedirs(lib_dir, exist_ok=True)
        for rel, b in self.files.items():
            p = os.path.join(lib_dir, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if not (os.path.exists(p) and open(p, 'rb').read() == b):
                open(p, 'wb').write(b)
        keep = {'catalog.json'} | {f for rel in self.lock['releases'] for f in rel['files']}
        removed = []
        for d, ds, fs in os.walk(lib_dir):
            for f in fs:
                rel = os.path.relpath(os.path.join(d, f), lib_dir).replace(os.sep, '/')
                if rel not in keep:
                    os.remove(os.path.join(d, f)); removed.append(rel)
        write_json(lock_path, self.lock)
        return removed


def _scalars(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items(): yield from _scalars(v, f'{path}.{k}')
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from _scalars(v, f'{path}[{i}]')
    else:
        yield path, o
