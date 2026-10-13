"""Build the offline precache: scans the repo and writes sw.js with every asset + a build id.
Run after ANY change (new room, images, voice clips, index.html):  python3 tools/build_sw.py

Voice packs: only the default flat voice/*.mp3 files are precached at install.
Other packs live under voice/<id>/*.mp3 and are cached on demand when a child picks them
(see cacheVoice message in sw.template.js).
"""
import os, hashlib, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', 'tools', 'node_modules', 'voice-samples'}
SKIP_FILES = {'sw.js', 'README.md', '.nojekyll'}
SKIP_EXT = ('.bak', '.py', '.log', '.md', '.DS_Store')
files = []
h = hashlib.sha256()
total = 0
voice_packs = {}  # id -> [./voice/id/...]

for d, ds, fs in os.walk(ROOT):
    ds[:] = sorted(x for x in ds if x not in SKIP_DIRS and not x.startswith('.'))
    rel_dir = os.path.relpath(d, ROOT).replace(os.sep, '/')
    # voice/<id>/ subfolders are NOT in the install precache (on-demand)
    under_voice_pack = rel_dir.startswith('voice/') and rel_dir != 'voice'
    for f in sorted(fs):
        rel = os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, '/')
        if f in SKIP_FILES or f.endswith(SKIP_EXT) or f.startswith('.'):
            continue
        data = open(os.path.join(ROOT, rel), 'rb').read()
        total += len(data)
        h.update(rel.encode() + b'\0' + hashlib.sha256(data).digest())
        url = './' + rel
        if under_voice_pack:
            pack = rel.split('/')[1]
            voice_packs.setdefault(pack, []).append(url)
        else:
            files.append(url)

# Also register default mia pack as the flat voice/*.mp3 list (for on-demand re-cache)
voice_packs['mia'] = [u for u in files if u.startswith('./voice/') and u.endswith('.mp3') and u.count('/') == 2]

build = h.hexdigest()[:12]
tpl = open(os.path.join(ROOT, 'tools', 'sw.template.js')).read()
out = (tpl.replace('__BUILD__', build)
          .replace('__ASSETS__', json.dumps(['./'] + files, separators=(',', ':')))
          .replace('__VOICE_PACKS__', json.dumps(voice_packs, separators=(',', ':'))))
open(os.path.join(ROOT, 'sw.js'), 'w').write(out)
pack_n = {k: len(v) for k, v in sorted(voice_packs.items())}
print(f'build {build}: {len(files)} files, {total/1e6:.1f} MB precached; voice packs {pack_n}')
