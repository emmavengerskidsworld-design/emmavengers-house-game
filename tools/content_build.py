"""Validate content/src and compile it into content/library (the files the app downloads).

  python3 tools/content_build.py            validate + compile + write content/library, registry lock and report
  python3 tools/content_build.py --check    validate and prove the committed library is up to date (writes nothing);
                                            exit 1 on any error - this is the required test (tools/run_tests.py)
  options: --channel live|preview   --src DIR --lib DIR --lock FILE --report FILE (for tests / scale runs)
           --no-files                skip picture/voice existence checks (scale tests with fake content)

After it succeeds, run python3 tools/build_sw.py so the offline cache knows the new files."""
import argparse, os, sys, tempfile, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content.source import Source
from content.validate import Validator
from content.compile import Build
from content.report import render
from content.common import load_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--channel')
    ap.add_argument('--src', default=os.path.join(ROOT, 'content', 'src'))
    ap.add_argument('--lib', default=os.path.join(ROOT, 'content', 'library'))
    ap.add_argument('--lock', default=os.path.join(ROOT, 'content', 'registry.lock.json'))
    ap.add_argument('--report', default=os.path.join(ROOT, 'content', 'build-report.md'))
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--no-files', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args(argv)
    S = Source(a.src, a.root)
    V = Validator(S, os.path.join(ROOT, 'content', 'schema', 'v1'), channel=a.channel, check_files=not a.no_files)
    issues = V.run()
    errs = [i for i in issues if i.sev == 'error']
    say = (lambda *x: None) if a.quiet else print
    for i in issues:
        if i.sev != 'info': say(i)
    if errs:
        print(f'FAILED: {len(errs)} errors, {sum(i.sev == "warn" for i in issues)} warnings', file=sys.stderr)
        return 1
    lock = load_json(a.lock) if os.path.exists(a.lock) else None
    B = Build(S, V, lock, channel=a.channel).run()
    if a.check:
        ok = B.lock == (lock or {}) or _same_except_nothing(B.lock, lock)
        stale = []
        for rel, b in B.files.items():
            p = os.path.join(a.lib, rel)
            if not os.path.exists(p) or open(p, 'rb').read() != b:
                stale.append(rel)
        if not ok or stale:
            print(f'FAILED: content/src changed but content/library is not rebuilt ({len(stale)} files differ, lock {"same" if ok else "differs"}).'
                  f' Run: python3 tools/content_build.py && python3 tools/build_sw.py', file=sys.stderr)
            for s in stale[:5]: print('  stale:', s, file=sys.stderr)
            return 1
        say(f'OK: {len(B.recs)} records valid, library up to date (sequence {B.catalog["sequence"]}), '
            f'{sum(i.sev == "warn" for i in issues)} warnings')
        return 0
    removed = B.write(a.lib, a.lock)
    rep = render(S, V, B, issues)
    open(a.report, 'w', encoding='utf-8').write(rep)
    say(f'OK: sequence {B.catalog["sequence"]}, {len(B.recs)} records, {len(B.files)} files, removed {len(removed)} old files; report {os.path.relpath(a.report, ROOT)}')
    return 0


def _same_except_nothing(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b or {}, sort_keys=True)


if __name__ == '__main__':
    sys.exit(main())
