"""One-time conversion of the pre-Stage-1 content (lands.json + content/countries/*.json) into the Stage-1
authoring source (content/src). Kept so tools/test_content.py can prove the conversion is lossless:
migrate the frozen originals (tools/fixtures/legacy-v0) -> compile -> read back -> rebuild old shapes -> deep-equal.

Usage: python3 tools/content/migrate_v0.py <legacy_dir> <out_src_dir>
"""
import copy, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from content.common import load_json, write_json

ALL = ['5-7', '8-10', '11-13']
LEGACY_REVIEW = {'legacy': True, 'note': 'Live on the main site before the Stage-1 review workflow existed. '
                 'Not yet re-reviewed under blueprint 05 (facts, sources, age bands are provisional).'}
LAND_SUBJECT = {'faith': ['faith'], 'letter': ['literacy'], 'number': ['numeracy'], 'study': [],
                'nature': ['science'], 'world': ['geography']}
DECK_META = {  # deck -> (land, subjects, ageBands, sensitivity)
    'letters': ('letter', ['literacy'], ['5-7'], []), 'numbers': ('number', ['numeracy'], ['5-7'], []),
    'objects': ('number', ['numeracy'], ['5-7'], []), 'animals': ('nature', ['science'], ALL, []),
    'countries': ('world', ['geography'], ALL, []), 'prayers': ('faith', ['faith'], ALL, ['christian-teaching'])}
DECK_LT = {'done', 'word', 'name', 'fact', 'meaning', 'language', 'food', 'text', 'plural', 'ask'}
GREETING_LANG = {'Bonjour!': 'fr', 'Sannu!': 'ha', 'Akwaaba!': 'tw', 'Jambo!': 'sw', 'Sawubona!': 'zu'}
EDITORIAL_SOURCES = {'10a': 'world-blueprint/10a-pilot-screens-cards-games.md (internal pilot design spec: practice map and activities)'}
PLACE_LT = {'name', 'sub', 'intro', 'ask'}


def en(s):
    return {'en': s}


def rec(id, type, payload, status='published', tags=None, evidence=None, review=None, **kw):
    r = {'id': id, 'type': type, 'status': status}
    if tags is not None: r['tags'] = tags
    r['payload'] = payload
    if evidence: r['evidence'] = evidence
    if review: r['review'] = review
    r.update(kw)
    return r


def src_file(records, note=None):
    f = {'$schema': '../../schema/v1/source-file.schema.json'}
    if note: f['note'] = note
    f['records'] = records
    return f


def core(L, out):
    d = os.path.join(out, 'core')
    write_json(os.path.join(d, 'pack.json'), {
        '$schema': '../../schema/v1/pack-source.schema.json',
        'id': 'core', 'collection': 'core', 'preload': True,
        'title': {'en': 'Emmavengers World: home map, six lands and shared parts'},
        'locales': {'required': ['en']},
        'defaults': {'status': 'published', 'sourceLanguage': 'en', 'review': LEGACY_REVIEW}})
    W = L['world']
    world = rec('ew.world.home', 'world', {
        'formatVersion': L['version'], 'title': en(W['title']), 'img': W['img'], 'intro': en(W['intro']),
        'layout': W['layout'], 'bg2': W['bg2'], 'lands': ['ew.land.' + x['id'] for x in L['lands']]},
        tags={'land': None, 'ageBands': ALL, 'modes': [], 'subjects': []})
    write_json(os.path.join(d, 'world.json'), src_file([world], 'The world home map. lands = order of the six lands.'))
    lands = []
    for x in L['lands']:
        p = {'key': x['id'], 'name': en(x['name'])}
        if 'type' in x: p['landType'] = x['type']
        for k in ('color', 'img', 'music'): p[k] = x[k]
        p['intro'] = en(x['intro'])
        p['layout'] = {k: x[k] for k in ('x', 'y', 'sx', 'sy', 'w', 'h', 'm6') if k in x}
        places = []
        for q in x['places']:
            o = {}
            for k, v in q.items():
                if k == 'id': o['key'] = v
                elif k in PLACE_LT: o[k] = en(v)
                elif k in ('deck', 'objects'): o[k] = 'ew.deck.' + v
                elif k == 'country': o[k] = 'ew.country.' + v
                else: o[k] = v
            places.append(o)
        p['places'] = places
        extra = [k for k in x if k not in ('id', 'name', 'type', 'color', 'img', 'music', 'intro', 'places', 'x', 'y', 'sx', 'sy', 'w', 'h', 'm6')]
        assert not extra, extra
        lands.append(rec('ew.land.' + x['id'], 'land', p, tags={
            'land': x['id'], 'ageBands': ALL, 'modes': [], 'subjects': LAND_SUBJECT[x['id']],
            'sensitivity': ['christian-teaching'] if x['id'] == 'faith' else []}))
    write_json(os.path.join(d, 'lands.json'), src_file(lands, 'The six lands. Land keys are permanent (blueprint 05); renaming a land changes its name text only.'))
    decks = []
    for k, D in L['decks'].items():
        land, subj, ages, sens = DECK_META[k]
        items = []
        for it in D['items']:
            o = {}
            for f, v in it.items():
                if f == 'say': o[f] = [en(s) for s in v]
                elif f == 'greeting': o[f] = {'text': v, 'lang': GREETING_LANG[v]}
                elif f in DECK_LT: o[f] = en(v)
                else: o[f] = v
            items.append(o)
        p = {'key': k, 'kind': D['kind']}
        if 'done' in D: p['done'] = en(D['done'])
        p['items'] = items
        assert set(D) <= {'kind', 'done', 'items'}
        decks.append(rec('ew.deck.' + k, 'deck', p, tags={'land': land, 'ageBands': ages, 'modes': ['learn'], 'subjects': subj, 'sensitivity': sens}))
    write_json(os.path.join(d, 'decks.json'), src_file(decks, 'Card decks used by land places (cards / quiz / count) and Study Land shelves.'))
    S = L['study']
    secs = []
    for s in S['sections']:
        o = {}
        for f, v in s.items():
            if f == 'id': o['key'] = v
            elif f in ('name', 'intro'): o[f] = en(v)
            elif f == 'source':
                o[f] = {'deck': 'ew.deck.' + v[5:]} if v.startswith('deck:') else {'module': v}
            elif f == 'items':
                o[f] = [{kk: ([en(z) for z in vv] if kk == 'say' else en(vv) if kk in ('name', 'text') else vv) for kk, vv in i.items()} for i in v]
            else: o[f] = v
        secs.append(o)
    study = rec('ew.library.study', 'library', {'prompt': en(S['prompt']), 'sections': secs},
                tags={'land': 'study', 'ageBands': ALL, 'modes': ['learn'], 'subjects': []},
                evidence={'note': S['_help']})
    write_json(os.path.join(d, 'study.json'), src_file([study], 'Study Land shelves.'))
    lex = rec('ew.lexicon.letter-sounds', 'lexicon', {'language': 'en', 'purpose': 'voice-production',
              'entries': [{'text': t, 'ipa': ipa} for t, ipa in L['phonemes'].items()]},
              tags={'land': 'letter', 'ageBands': ['5-7'], 'modes': [], 'subjects': ['literacy']},
              evidence={'note': 'IPA used by tools/gen_voice.py to speak letter sounds. Keys are the exact spoken lines.'})
    write_json(os.path.join(d, 'lexicon.json'), src_file([lex], 'Pronunciation help for voice production (not shown to children).'))
    return d


def cameroon(C, B, UI, out):
    d = os.path.join(out, 'countries', 'cameroon')
    P = C['payload']
    slug = P['slug']; assert slug == 'cameroon'
    pre = 'pilot-cameroon'
    lid = lambda k: f'ew.line.{pre}.{k}'
    mid = lambda k: f'ew.media.{pre}-{k}'
    sid = lambda k: f'ew.source.{pre}-{k.lower()}'
    cid = lambda k: f'ew.card.{pre}-{k.lower()}'
    base_tags = {'land': 'world', 'topics': ['ew.country.cameroon'], 'regions': ['africa'], 'subjects': ['geography']}
    fr_status = C['locales']['fr']['status']
    write_json(os.path.join(d, 'pack.json'), {
        '$schema': '../../../schema/v1/pack-source.schema.json',
        'id': 'country.cameroon', 'collection': 'countries.africa', 'preload': True,
        'summary': 'ew.country.cameroon',
        'title': {'en': 'Cameroon pilot (World Land)', 'fr': 'Pilote Cameroun (Terre du monde)'},
        'locales': {'required': ['en', 'fr']},
        'defaults': {'status': C['status'], 'sourceLanguage': C['sourceLanguage'], 'tags': base_tags,
                     'l10n': {'fr': {'status': fr_status}},
                     'review': {'note': 'Pilot draft: needs educator, cultural and Emmanuel review; French needs a fluent reviewer.'}}})
    # ---- sources: pack register (url, checkedOn) + quiz bank labels
    srcs = []
    for s in C['evidence']['sources']:
        k = s['sourceId']
        p = {'key': k, 'url': s['url'], 'checkedOn': s['checkedOn']}
        bl = B['sources'].get(k)
        if bl is not None and bl != s['url']:
            p['note'] = bl
        elif not s['url']:
            p['note'] = EDITORIAL_SOURCES.get(k, f'internal editorial source {k}')
        srcs.append(rec(sid(k), 'source', p, tags={'ageBands': ALL, 'modes': []}))
    assert all(k in [s['sourceId'] for s in C['evidence']['sources']] for k in B['sources'])
    write_json(os.path.join(d, 'sources.json'), src_file(srcs, 'Source register for Cameroon facts. Each fact record cites these by id.'))
    # ---- lines
    lines = [rec(lid(k), 'line', {'key': k, 'speaker': 'ew.character.' + l['speaker'], 'text': l['text']},
                 tags={'ageBands': ALL, 'modes': []}) for k, l in P['lines'].items()]
    write_json(os.path.join(d, 'lines.json'), src_file(lines, 'Pre-written guide lines (Ari, Ezra). Only these lines are ever shown or spoken.'))
    # ---- media
    media = []
    for k, m in P['media'].items():
        media.append(rec(mid(k), 'media', dict({'key': k}, **m), tags={'ageBands': ALL, 'modes': []}))
    write_json(os.path.join(d, 'media.json'), src_file(media, 'Pictures described for the player. kind=placeholder means final art is still to be made.'))
    # ---- learn cards + lessons
    cards, lessons = [], []
    for band, ages in (('little', ['5-7']), ('big', ['8-10', '11-13'])):
        Lx = P['learn'][band]
        refs = []
        for c in Lx['cards']:
            p = {'key': c['id'], 'kind': c['kind'], 'image': mid(c['image']), 'text': c['text']}
            if 'lines' in c: p['lines'] = [lid(x) for x in c['lines']]
            assert set(c) <= {'id', 'kind', 'image', 'text', 'lines', 'sources', 'band'}, c.keys()
            # a card with its own band (B9: optional, 11-13 only) keeps it as a narrower age tag
            cards.append(rec(cid(c['id']), 'learn-card', p, tags={'ageBands': [c['band']] if 'band' in c else ages, 'modes': ['learn']},
                             evidence={'sources': [sid(x) for x in c['sources']], 'factual': c['kind'] == 'info'}))
            refs.append(cid(c['id']))
        lessons.append(rec(Lx['lessonId'], 'lesson', {'key': band, 'cards': refs}, tags={'ageBands': ages, 'modes': ['learn']}))
    write_json(os.path.join(d, 'learn.json'), src_file(lessons + cards, 'Learn: one lesson per age mode; each card is its own record.'))
    # ---- activities
    acts = []
    for g in P['play']:
        p = {'key': g['id']}
        for k, v in g.items():
            if k in ('id', 'ref', 'bands', 'note'): continue
            p[k] = [lid(x) for x in v] if k == 'lines' else v
        ev = {'note': g['note']} if 'note' in g else None
        acts.append(rec(g['ref'], 'activity', p, tags={'ageBands': g['bands'], 'modes': ['play']}, evidence=ev))
    write_json(os.path.join(d, 'play.json'), src_file(acts, 'Play: each game is a known template (see content/src/capabilities.json) filled with data.'))
    # ---- quiz bank + items
    LK = P['quiz']['localeKeys']
    items = []
    for it in B['items']:
        assert set(it) == {'answerKey', 'band', 'construct', 'en', 'existingFrom10b', 'factCheckStatus', LK['fr'], 'id',
                           'readAloudAllowed', 'reviewStatus', 'revision', 'shuffleOptions', 'source', 'sourceKey', 'status', 'type'}, it.keys()
        # an item may cite several sources ("url ; url"): keep all of them, first = the legacy sourceKey
        by_val = {v: k for k, v in B['sources'].items()}
        skeys = [by_val[x] for x in it['source'].split(' ; ')]
        assert skeys[0] == it['sourceKey'], (it['id'], skeys)
        locs = {lg: it[k] for lg, k in LK.items()}
        p = {'responseType': it['type'], 'construct': it['construct']}
        p['prompt'] = {lg: x['prompt'] for lg, x in locs.items()}
        p['options'] = {o: {lg: x['options'][o] for lg, x in locs.items()} for o in locs['en']['options']}
        for f in ('hint', 'feedback'):
            p[f] = {lg: x[f] for lg, x in locs.items() if f in x}
        for lg, x in locs.items():
            assert set(x) == {'prompt', 'options', 'hint', 'feedback'} and list(x['options']) == list(locs['en']['options'])
        p['answerKey'] = it['answerKey']
        p['readAloudAllowed'] = it['readAloudAllowed']; p['shuffleOptions'] = it['shuffleOptions']
        items.append(rec(it['id'], 'quiz-item', p, status=it['status'], tags={'ageBands': [it['band']], 'modes': ['quiz']},
                         evidence={'sources': [sid(k) for k in skeys], 'factual': it['factCheckStatus'] != 'invented-example',
                                   'provenance': {'existingFrom10b': it['existingFrom10b']}},
                         review={'factCheck': it['factCheckStatus'], 'note': it['reviewStatus']}))
    assert set(B) == {'bank', 'revision', 'status', 'note', 'sources', 'items', 'roundRules'}
    bank = rec(B['bank'], 'quiz-bank', {'items': [x['id'] for x in B['items']], 'sources': [sid(k) for k in B['sources']],
               'roundRules': B['roundRules']}, status=B['status'], tags={'ageBands': ALL, 'modes': ['quiz']},
               evidence={'note': B['note']})
    write_json(os.path.join(d, 'quiz.json'), src_file([bank] + items, 'Quiz: finite bank of single-choice items. answerKey points at a stable option id; options are shuffled only on screen.'))
    # ---- stories
    stories = []
    for s in P['stories']:
        p = {k: v for k, v in s.items() if k not in ('id', 'bands', 'note')}
        stories.append(rec(s['id'], 'story', p, tags={'ageBands': s['bands'], 'modes': ['stories'], 'subjects': ['geography', 'reading']},
                           evidence={'note': s['note']} if 'note' in s else None))
    write_json(os.path.join(d, 'stories.json'), src_file(stories, 'Stories: made-up stories (classification original-fiction).'))
    # ---- country record
    Q = P['quiz']
    quiz = {'bank': B['bank'], 'legacyLocaleKeys': [[lg, k] for lg, k in LK.items()]}
    for k, v in Q.items():
        if k not in ('bank', 'localeKeys'): quiz[k] = v
    known = {'slug', 'name', 'flag', 'hub', 'lines', 'learn', 'practiceMap', 'play', 'quiz', 'stories', 'media', 'breakAfterMinutes', 'ui'}
    assert set(P) == known, set(P) ^ known
    cp = {'slug': slug, 'name': P['name'], 'externalIdentifiers': [{'issuer': 'ISO-3166-1-alpha-2', 'code': 'CM'}],
          'flag': P['flag'], 'hub': {k: lid(v) for k, v in P['hub'].items()},
          'learn': {b: P['learn'][b]['lessonId'] for b in ('little', 'big')},
          'practiceMap': P['practiceMap'], 'play': [g['ref'] for g in P['play']], 'quiz': quiz,
          'stories': [s['id'] for s in P['stories']], 'lines': [lid(k) for k in P['lines']],
          'media': [mid(k) for k in P['media']], 'breakAfterMinutes': P['breakAfterMinutes'], 'ui': P['ui']}
    T = C['tags']
    tags = dict(base_tags, relatedLands=T['relatedLands'], ageBands=T['ageBands'], modes=T['modes'], access=T['access'], sensitivity=T['sensitivity'])
    country = rec(C['id'], 'country', cp, status=C['status'], tags=tags,
                  evidence={'spec': C['evidence']['spec'], 'sources': [sid(s['sourceId']) for s in C['evidence']['sources']], 'gaps': C['evidence']['gaps']},
                  review={'ownerRole': C['editorial']['ownerRole'], 'records': C['editorial']['reviewRecordRefs'], 'approvalRef': C['editorial']['approvalRef'],
                          'note': 'Pilot draft: needs educator, cultural and Emmanuel review; French needs a fluent reviewer.'},
                  l10n={lg: {'status': v['status']} for lg, v in C['locales'].items()})
    assert C['schemaVersion'] == '1.0.0' and C['type'] == 'country-pack' and C['revision'] == 1
    write_json(os.path.join(d, 'country.json'), src_file([country], 'The Cameroon country record: what the player needs to open Cameroon, pointing at its lessons, games, quiz bank, stories, lines and pictures.'))
    return d


def shared(UI, out):
    d = os.path.join(out, 'core')
    ui = rec(UI['id'], 'strings', {'strings': UI['strings']}, status=UI['status'],
             tags={'land': None, 'ageBands': ALL, 'modes': []}, evidence={'note': UI['note']},
             review={'note': UI['note']}, l10n={'required': ['en', 'fr'], 'fr': {'status': 'draft-pending-fluent-french-review'}})
    chars = [
        rec('ew.character.ari', 'character', {'key': 'ari', 'name': {'en': 'Ari', 'fr': 'Ari'}, 'species': 'lion cub',
            'images': {k: f'img/world/guides/ari-{k}.webp' for k in ('hello', 'map', 'cheer', 'think', 'thumbs')}},
            status='draft', tags={'land': None, 'ageBands': ALL, 'modes': []}, l10n={'required': ['en', 'fr']},
            evidence={'note': 'Ari the Emmavenger (Hebrew: lion). Speaks only pre-written, checked lines. Name clearance pending (lawyer).'}),
        rec('ew.character.ezra', 'character', {'key': 'ezra', 'name': {'en': 'Ezra', 'fr': 'Ezra'}, 'species': 'eagle',
            'images': {k: f'img/world/guides/ezra-{k}.webp' for k in ('face', 'carry')}},
            status='draft', tags={'land': None, 'ageBands': ALL, 'modes': []}, l10n={'required': ['en', 'fr']},
            evidence={'note': 'Ezra (Hebrew: help), eagle companion: travel, sky view, celebrations. Isaiah 40:31.'})]
    write_json(os.path.join(d, 'characters.json'), src_file(chars, 'Guide characters. Lines live with each topic (e.g. countries/cameroon/lines.json).'))
    write_json(os.path.join(d, 'ui-strings.json'), src_file([ui], 'Shared buttons and labels for the country player.'))


def main(legacy, out):
    L = load_json(os.path.join(legacy, 'lands.json'))
    C = load_json(os.path.join(legacy, 'cameroon.json'))
    B = load_json(os.path.join(legacy, 'cameroon-quiz.json'))
    UI = load_json(os.path.join(legacy, 'ui.json'))
    IX = load_json(os.path.join(legacy, 'index.json'))
    assert [c['slug'] for c in IX['countries']] == ['cameroon']
    core(L, out); shared(UI, out); cameroon(C, B, UI, out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
