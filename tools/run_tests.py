"""Run every test:  python3 tools/run_tests.py [--quick] [--scale] [--install-hook]
  1. REQUIRED first: content validator + "library is up to date" (tools/content_build.py --check). If it fails, nothing
     else runs - broken or un-built content must never reach the app.
  2. content tests (test_content.py) and loader tests in a browser (test_library.py)
  3. the existing game suites (world, Cameroon pilot, study, parents, voice, offline, Bible offline, voice clip check)
  --quick         only 1 + 2 (about 20 s)       --scale   also the 200-country x 5-language scale test
  --install-hook  install a local git pre-commit hook that runs --quick (never pushes anything)
Writes a summary to stdout; each suite's full log goes to /tmp/ew-tests/<name>.log."""
import os, sys, subprocess, time, socket, signal
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
LOGS = '/tmp/ew-tests'

def port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p

def run(name, cmd, timeout=1800):
    os.makedirs(LOGS, exist_ok=True); t = time.time(); log = os.path.join(LOGS, name + '.log')
    with open(log, 'w') as f:
        try: rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired: rc = 'timeout'
    dt = time.time() - t
    tail = open(log, encoding='utf-8', errors='replace').read().strip().splitlines()[-1:] or ['']
    print(f'{"PASS" if rc == 0 else "FAIL"}  {name:<20} {dt:6.0f} s   {tail[0][:110]}', flush=True)
    return rc == 0

def main():
    a = sys.argv[1:]
    if '--install-hook' in a:
        hp = os.path.join(ROOT, '.git', 'hooks', 'pre-commit')
        open(hp, 'w').write('#!/bin/sh\n# installed by tools/run_tests.py --install-hook\nexec python3 tools/run_tests.py --quick\n'); os.chmod(hp, 0o755)
        print('pre-commit hook installed:', hp); return 0
    print('== required: content validator ==')
    if not run('content_check', [PY, 'tools/content_build.py', '--check']):
        print('STOP: content is invalid or content/library is out of date. See /tmp/ew-tests/content_check.log'); return 1
    res = [run('test_content', [PY, 'tools/test_content.py']), run('test_library', [PY, 'tools/test_library.py'])]
    if '--quick' not in a:
        print('== game suites ==')
        for name, cmd in [('test_world', ['tools/test_world.py']), ('test_cameroon', ['tools/test_cameroon.py', os.path.join(LOGS, 'cameroon-shots')]),
                          ('test_study', ['tools/test_study.py']), ('test_parents', ['tools/test_parents.py']),
                          ('test_voice_off', ['tools/test_voice_off.py']), ('test_voice_settings', ['tools/test_voice_settings.py']),
                          ('check_voice', ['tools/check_voice.py', ROOT]), ('test_offline', ['tools/test_offline.py']),
                          ('test_offline_bible', ['tools/test_offline_bible.py', '--books', 'noah'])]:
            res.append(run(name, [PY] + cmd))
        p = port(); srv = subprocess.Popen([PY, 'tools/throttle_server.py', ROOT, str(p), '0'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        try: res.append(run('test_quick_tap', [PY, 'tools/test_quick_tap.py', f'http://127.0.0.1:{p}/', '--cold']))
        finally: srv.send_signal(signal.SIGTERM)
    if '--scale' in a:
        res.append(run('test_scale', [PY, 'tools/test_scale.py']))
    print(f'\n{sum(res)}/{len(res)} suites passed (+ required content check)')
    return 0 if all(res) else 1

if __name__ == '__main__':
    sys.exit(main())
