"""Shared helpers: canonical JSON, hashes, localized text, voice clip names."""
import hashlib, json, re

FORMAT = 1                 # wire format of catalog / index / pack files (library.js checks it)
SCHEMA_VERSION = '1.0.0'   # content schema version (content/schema/v1)
LOCALE_RE = re.compile(r'^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$')
ID_RE = re.compile(r'^ew\.[a-z]+\.[a-z0-9]+(?:[.-][a-z0-9]+)*$')


def dumps(obj):
    """Exact bytes written for compiled files (keeps authored key order: option order is meaningful)."""
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def canonical(obj):
    """Order-independent canonical bytes used for record content hashes."""
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def is_lt(v, locales=None):
    """A localized text: {"en": "...", "fr": "..."} - non-empty, every key a language tag, every value a string,
    and (when the registry is known) at least one registered locale."""
    if not isinstance(v, dict) or not v:
        return False
    if not all(isinstance(k, str) and LOCALE_RE.match(k) and isinstance(x, str) for k, x in v.items()):
        return False
    return locales is None or any(k in locales for k in v)


def walk_lt(obj, locales, path=''):
    """Yield (path, lt) for every localized text inside obj."""
    if is_lt(obj, locales):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_lt(v, locales, f'{path}.{k}' if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_lt(v, locales, f'{path}[{i}]')


def map_lt(obj, locales, fn):
    """Return a copy of obj with every localized text replaced by fn(lt)."""
    if is_lt(obj, locales):
        return fn(obj)
    if isinstance(obj, dict):
        return {k: map_lt(v, locales, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [map_lt(v, locales, fn) for v in obj]
    return obj


def flat_en(obj, locales, lang='en'):
    """Localized texts -> plain strings in one language (the pre-Stage-1 world screens are English-only)."""
    return map_lt(obj, locales, lambda lt: lt.get(lang))


def vh(t):
    """FNV-1a over UTF-16LE code units: the voice clip file name used by the app (voice/<vh>.mp3)."""
    h = 0x811c9dc5
    b = t.encode('utf-16-le')
    for i in range(0, len(b), 2):
        h ^= b[i] | (b[i + 1] << 8)
        h = (h * 0x01000193) & 0xffffffff
    return f'{h:08x}'


assert vh('Pick a room to play!') == '2d584f8e'


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path, obj, pretty=True):
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write('\n')
        else:
            f.write(dumps(obj).decode('utf-8'))
