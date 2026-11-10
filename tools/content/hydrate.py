"""Read a compiled library back into records - the Python twin of what library.js does in the browser:
catalog -> indexes -> packs, verifying every SHA-256 and joining each pack's language files back into
{"en": ..., "fr": ...} texts. Used by tests and by tools that need the app's view of the content."""
import hashlib, json, os


class LibraryError(Exception):
    pass


def _read(lib, ref):
    b = open(os.path.join(lib, ref['path']), 'rb').read()
    if len(b) != ref['bytes'] or hashlib.sha256(b).hexdigest() != ref['sha256']:
        raise LibraryError(f'hash/size mismatch for {ref["path"]}')
    return json.loads(b)


def hydrate_pack(struct, locale_files):
    for lp in locale_files:
        if lp['pack'] != struct['pack']:
            raise LibraryError('language file belongs to another pack')
    def fill(o):
        if isinstance(o, dict):
            if len(o) == 1 and '$t' in o:
                i = o['$t']
                lt = {lp['locale']: lp['strings'][i] for lp in locale_files if lp['strings'][i] is not None}
                return lt
            return {k: fill(v) for k, v in o.items()}
        if isinstance(o, list):
            return [fill(v) for v in o]
        return o
    return [fill(r) for r in struct['records']]


def load(lib, locales=('en', 'fr'), packs=None):
    """Return (catalog, {id: record}). packs=None loads every pack."""
    cat = json.load(open(os.path.join(lib, 'catalog.json'), 'rb'))
    recs, order = {}, 0
    for c in cat['collections']:
        idx = _read(lib, c['index'])
        for e in idx['packs']:
            if packs is not None and e['id'] not in packs:
                continue
            st = _read(lib, e['file'])
            lfs = []
            for lg in locales:
                if lg in e['locales']:
                    lf = _read(lib, e['locales'][lg])
                    if lf['struct'] != e['file']['sha256']:
                        raise LibraryError(f'{e["id"]}@{lg} was built for a different structure file')
                    lfs.append(lf)
            for r in hydrate_pack(st, lfs):
                r['_order'] = order; order += 1
                r['_pack'] = e['id']
                recs[r['id']] = r
    return cat, recs
