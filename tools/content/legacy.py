"""Rebuild the pre-Stage-1 shapes from library records, so today's screens (world.js, country.js) keep working
unchanged while the library is the single source of truth. library.js has the same adapter in JavaScript
(EWLib.legacy); tools/test_library.py checks both give identical results.

Also lists every line the app can speak (same rules as world.js worldVoice() and country.js ctStrings()),
so the validator can check that each one has a voice clip."""
from .common import is_lt, map_lt, flat_en

LEGACY_FILE = 'content/countries/{slug}.json'


def _key(recs, rid):
    return recs[rid]['payload']['key']


def lands(recs, locales):
    """lands.json (the world home, six lands, decks, phonemes, study) in English, as before Stage 1."""
    W = recs['ew.world.home']['payload']
    out = {'version': W.get('formatVersion', 1),
           'world': {'title': W['title']['en'], 'img': W['img'], 'intro': W['intro']['en'], 'layout': W['layout'], 'bg2': W['bg2']},
           'lands': [], 'decks': {}, 'phonemes': {}, 'study': None}
    for lid in W['lands']:
        if lid not in recs:
            continue
        p = flat_en(recs[lid]['payload'], locales)
        L = {'id': p['key'], 'name': p['name']}
        if 'landType' in p:
            L['type'] = p['landType']
        for k in ('color', 'img', 'music'):
            if k in p: L[k] = p[k]
        L.update({k: v for k, v in p['layout'].items() if k != 'm6'})
        L['intro'] = p['intro']
        places = []
        for q in p['places']:
            if q.get('country') and q['country'] not in recs:
                continue  # country left out of this channel (e.g. a draft on the live channel)
            o = {}
            for k, v in q.items():
                if k == 'key': o['id'] = v
                elif k in ('deck', 'objects'): o[k] = _key(recs, v)
                elif k == 'country': o[k] = recs[v]['payload']['slug']
                else: o[k] = v
            places.append(o)
        L['places'] = places
        if 'm6' in p['layout']: L['m6'] = p['layout']['m6']  # optional new map art (key order of a land is not used by the app)
        out['lands'].append(L)
    decks = sorted((r for r in recs.values() if r['type'] == 'deck'), key=lambda r: r.get('_order', 0))
    for r in decks:
        p = flat_en(r['payload'], locales)
        D = {'kind': p['kind']}
        if 'done' in p: D['done'] = p['done']
        D['items'] = [{k: (v['text'] if k == 'greeting' else v) for k, v in it.items()} for it in p['items']]
        out['decks'][p['key']] = D
    lex = recs.get('ew.lexicon.letter-sounds')
    if lex:
        out['phonemes'] = {e['text']: e['ipa'] for e in lex['payload']['entries']}
    st = recs.get('ew.library.study')
    if st:
        p = flat_en(st['payload'], locales)
        secs = []
        for s in p['sections']:
            o = {}
            for k, v in s.items():
                if k == 'key': o['id'] = v
                elif k == 'source':
                    o[k] = 'deck:' + _key(recs, v['deck']) if 'deck' in v else v.get('module', '')
                else: o[k] = v
            secs.append(o)
        out['study'] = {'prompt': p['prompt'], 'sections': secs}
        if st.get('evidence', {}).get('note'):
            out['study']['_help'] = st['evidence']['note']
    return out


def country_index(recs):
    cs = sorted((r for r in recs.values() if r['type'] == 'country'), key=lambda r: r.get('_order', 0))
    return {'schemaVersion': '1.0.0', 'id': 'ew.index.countries', 'revision': 1, 'status': 'draft',
            'countries': [{'id': r['id'], 'slug': r['payload']['slug'], 'revision': r.get('revision', 1),
                           'file': LEGACY_FILE.format(slug=r['payload']['slug']), 'land': r['tags'].get('land')} for r in cs]}


def ui_strings(recs, rid='ew.ui.country-player'):
    r = recs[rid]
    return {'schemaVersion': '1.0.0', 'id': r['id'], 'revision': r.get('revision', 1), 'status': r['status'],
            'note': r.get('evidence', {}).get('note', ''), 'strings': r['payload']['strings']}


def _locales(lz):
    out = {}
    for lg in list(lz.get('required', [])) + list(lz):
        if lg != 'required' and lg in lz and lg not in out: out[lg] = {'status': lz[lg]['status']}
    return out


def country(recs, cid):
    """(country pack, quiz bank) in the shapes country.js reads."""
    C = recs[cid]
    P = C['payload']
    line = lambda rid: recs[rid]
    lkey = lambda rid: recs[rid]['payload']['key']
    pay = {'slug': P['slug'], 'name': P['name'], 'flag': P['flag'],
           'hub': {k: lkey(v) for k, v in P['hub'].items()},
           'lines': {}, 'learn': {}, 'practiceMap': P['practiceMap'], 'play': [], 'quiz': None, 'stories': [], 'media': {},
           'breakAfterMinutes': P['breakAfterMinutes'], 'ui': P['ui']}
    for rid in P['lines']:
        l = line(rid)['payload']
        pay['lines'][l['key']] = {'speaker': recs[l['speaker']]['payload']['key'], 'text': l['text']}
    src_key = lambda rid: recs[rid]['payload']['key']
    for band in ('little', 'big'):
        les = recs[P['learn'][band]]
        bands = les['tags']['ageBands']
        cards = []
        for rid in les['payload']['cards']:
            c = recs[rid]
            cp = c['payload']
            o = {'id': cp['key'], 'image': recs[cp['image']]['payload']['key'], 'text': cp['text'],
                 'sources': [src_key(s) for s in c.get('evidence', {}).get('sources', [])], 'kind': cp['kind']}
            if 'lines' in cp: o['lines'] = [lkey(x) for x in cp['lines']]
            cb = c['tags']['ageBands']
            if set(cb) < set(bands) and len(cb) == 1: o['band'] = cb[0]
            cards.append(o)
        pay['learn'][band] = {'lessonId': les['id'], 'cards': cards}
    for rid in P['play']:
        a = recs[rid]
        g = {'id': a['payload']['key'], 'ref': a['id'], 'template': a['payload']['template'], 'bands': a['tags']['ageBands']}
        for k, v in a['payload'].items():
            if k in ('key', 'template'): continue
            g[k] = [lkey(x) for x in v] if k == 'lines' else v
        if a.get('evidence', {}).get('note'): g['note'] = a['evidence']['note']
        pay['play'].append(g)
    Q = P['quiz']
    LK = {lg: k for lg, k in Q['legacyLocaleKeys']}
    q = {'bank': None, 'localeKeys': LK}
    for k, v in Q.items():
        if k not in ('bank', 'legacyLocaleKeys'): q[k] = v
    for rid in P['stories']:
        s = recs[rid]
        o = {'id': s['id']}
        if 'classification' in s['payload']: o['classification'] = s['payload']['classification']
        o['bands'] = s['tags']['ageBands']
        o.update({k: v for k, v in s['payload'].items() if k != 'classification'})
        if s.get('evidence', {}).get('note'): o['note'] = s['evidence']['note']
        pay['stories'].append(o)
    for rid in P['media']:
        m = dict(recs[rid]['payload'])
        k = m.pop('key')
        pay['media'][k] = m
    bankrec = recs[Q['bank']]
    q['bank'] = LEGACY_FILE.format(slug=P['slug'] + '-quiz')
    pay['quiz'] = q
    T = C['tags']
    pack = {'schemaVersion': '1.0.0', 'id': C['id'], 'type': 'country-pack', 'revision': C.get('revision', 1), 'status': C['status'],
            'sourceLanguage': C['sourceLanguage'],
            'locales': _locales(C.get('l10n', {})),
            'tags': {k: T[k] for k in ('land', 'relatedLands', 'ageBands', 'modes', 'access', 'sensitivity') if k in T},
            'evidence': {'spec': C['evidence'].get('spec'),
                         'sources': [{'sourceId': recs[s]['payload']['key'], 'url': recs[s]['payload']['url'], 'checkedOn': recs[s]['payload']['checkedOn']} for s in C['evidence']['sources']],
                         'gaps': C['evidence'].get('gaps', [])},
            'editorial': {'ownerRole': C['review'].get('ownerRole'), 'reviewRecordRefs': C['review'].get('records', []), 'approvalRef': C['review'].get('approvalRef')},
            'payload': pay}
    sval = lambda rid: recs[rid]['payload']['url'] or recs[rid]['payload'].get('note')
    sv = lambda rid: recs[rid]['payload'].get('note') or recs[rid]['payload']['url']
    bp = bankrec['payload']
    items = []
    for rid in bp['items']:
        it = recs[rid]
        ip = it['payload']
        srcs = it['evidence']['sources']
        o = {'id': it['id'], 'revision': it.get('revision', 1), 'status': it['status'], 'type': ip['responseType'],
             'band': it['tags']['ageBands'][0], 'construct': ip['construct'],
             'source': ' ; '.join(sv(s) for s in srcs), 'sourceKey': src_key(srcs[0]),
             'existingFrom10b': it['evidence'].get('provenance', {}).get('existingFrom10b'), 'answerKey': ip['answerKey']}
        for lg, k in LK.items():
            blk = {'prompt': ip['prompt'].get(lg), 'options': {o2: t.get(lg) for o2, t in ip['options'].items()}}
            for f in ('hint', 'feedback'):
                if f in ip and lg in ip[f]: blk[f] = ip[f][lg]
            if blk['prompt'] is not None:
                o[k] = blk
        o['readAloudAllowed'] = ip.get('readAloudAllowed')
        o['shuffleOptions'] = ip.get('shuffleOptions')
        o['factCheckStatus'] = it.get('review', {}).get('factCheck')
        o['reviewStatus'] = it.get('review', {}).get('note')
        items.append(o)
    bank = {'bank': bankrec['id'], 'revision': bankrec.get('revision', 1), 'status': bankrec['status'],
            'note': bankrec.get('evidence', {}).get('note'),
            'sources': {src_key(s): sv(s) for s in bp.get('sources', [])}, 'items': items, 'roundRules': bp.get('roundRules')}
    return pack, bank


# ---------- every spoken line (mirrors world.js worldVoice / country.js ctStrings) ----------
import re as _re


def _wfill(t, it):
    def f(m):
        k = m.group(1)
        if k == 'lname': return str(it.get('name')).lower()
        if k == 'word': return str(it.get('word')).lower()
        v = it.get(k)
        return '' if v is None else str(v)
    return _re.sub(r'\{(\w+)\}', f, t)


def world_spoken(L):
    S = []
    A = lambda x: [S.append(t) for t in (x if isinstance(x, list) else [x]) if t]
    deck = lambda k: L['decks'].get(k)
    A(L['world']['intro'])
    for Ld in L['lands']:
        A(Ld.get('intro'))
        for p in Ld['places']:
            A(p.get('intro'))
            if p['type'] == 'quiz':
                for it in deck(p['deck'])['items']:
                    if it.get('hunt') is not False: A(_wfill(p['ask'], it))
            if p['type'] == 'count':
                for o in deck(p['objects'])['items']: A(o.get('ask'))
    if L.get('study'):
        A(L['study']['prompt'])
        for s in L['study']['sections']:
            A(s.get('intro'))
            for it in s.get('items', []): A(it.get('say'))
    for D in L['decks'].values():
        A(D.get('done'))
        for it in D.get('items', []): A(it.get('say'))
    A(['Great job! Level complete!', 'Amen!'])
    return list(dict.fromkeys(S))


def country_spoken(pk, bank, ui):
    out = []
    def add(o):
        if not o: return
        if isinstance(o, str): out.append((o, 'en')); return
        if o.get('en'): out.append((o['en'], 'en'))
        if o.get('fr'): out.append((o['fr'], 'fr'))
    P = pk['payload']
    for l in P['lines'].values(): add(l['text'])
    for b in ('little', 'big'):
        for c in P['learn'][b]['cards']: add(c['text'])
    for g in P['play']:
        for k in ('title', 'mission', 'prompt', 'hint', 'success', 'caption', 'task', 'feedback'):
            v = g.get(k)
            if isinstance(v, dict) and not is_lt(v):
                continue
            add(v)
        if isinstance(g.get('feedback'), dict) and g['feedback'].get('success'):
            for v in g['feedback'].values(): add(v)
        for p in g.get('prompts', []): add(p.get('ask'))
        for q in g.get('questions', []):
            add(q.get('ask'))
            for v in q['options'].values(): add(v)
        if g.get('next'):
            for v in g['next']['options'].values(): add(v)
    Q = P['quiz']
    add(Q.get('exhausted'))
    for it in bank['items']:
        for lg, k in Q['localeKeys'].items():
            x = it.get(k)
            if not x: continue
            for t in [x.get('prompt'), x.get('hint'), x.get('feedback'), *x['options'].values()]:
                if t: out.append((t, lg))
    for s in P['stories']:
        add(s.get('title')); add(s.get('banner'))
        for ps in s['pages'].values():
            for p in ps: add(p['text'])
        for v in s['reflection'].values(): add(v)
    if ui:
        for k in ('shorter', 'needToKnow'): add(ui['strings'].get(k))
    return out
