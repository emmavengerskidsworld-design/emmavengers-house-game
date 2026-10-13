"""Build the offline precache: scans the repo and writes sw.js with every asset + a build id.
Run after ANY change (new room, images, voice clips, index.html):  python3 tools/build_sw.py"""
import os,hashlib,json
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS={'.git','tools','node_modules','voice-samples'}
SKIP_FILES={'sw.js','README.md','.nojekyll'}
SKIP_EXT=('.bak','.py','.log','.md','.DS_Store')
files=[];h=hashlib.sha256();total=0
for d,ds,fs in os.walk(ROOT):
    ds[:]=sorted(x for x in ds if x not in SKIP_DIRS and not x.startswith('.'))
    for f in sorted(fs):
        rel=os.path.relpath(os.path.join(d,f),ROOT).replace(os.sep,'/')
        if f in SKIP_FILES or f.endswith(SKIP_EXT) or f.startswith('.'):continue
        data=open(os.path.join(ROOT,rel),'rb').read();total+=len(data)
        h.update(rel.encode()+b'\0'+hashlib.sha256(data).digest());files.append('./'+rel)
build=h.hexdigest()[:12]
tpl=open(os.path.join(ROOT,'tools','sw.template.js')).read()
open(os.path.join(ROOT,'sw.js'),'w').write(tpl.replace('__BUILD__',build).replace('__ASSETS__',json.dumps(['./']+files,separators=(',',':'))))
print(f'build {build}: {len(files)} files, {total/1e6:.1f} MB precached')
