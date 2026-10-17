"""Run native offline unittest discovery and retain byte-frozen evidence."""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def frozen():
    paths = [*(ROOT/'product/src').rglob('*.py'), *(ROOT/'product/tests').rglob('*.py'),
             *(ROOT/'product/src').rglob('*.mjs'), ROOT/'product/pyproject.toml',
             ROOT/'docs/specs/agent-project.schema.json', ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt']
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True, help='new JSON evidence path; adjacent .log is retained')
    parser.add_argument('--pattern', default='test*.py')
    parser.add_argument('--rubberband', type=Path, default=os.environ.get('AI_AD_EDITOR_TEST_RUBBERBAND'),
                        help='explicit existing native executable, with COPYING.txt and sndfile.dll beside it')
    args = parser.parse_args()
    output = args.output.resolve()
    log = output.with_suffix('.log')
    assert not output.exists() and not log.exists(), 'choose fresh evidence paths'
    output.parent.mkdir(parents=True, exist_ok=True)
    before = frozen()
    record = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'pattern': args.pattern, 'frozen_before': before,
              'native_windows': sys.platform == 'win32', 'virtualization': False}
    if args.rubberband:
        binary = args.rubberband.resolve(strict=True)
        paths = [binary, binary.with_name('COPYING.txt'), binary.with_name('sndfile.dll')]
        if not all(p.is_file() for p in paths):
            parser.error('--rubberband requires the existing executable, COPYING.txt and sndfile.dll')
        record['native_audio_toolchain'] = {str(p): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in paths}
    def save():
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    save()
    bootstrap = ('import sys,unittest;sys.path.insert(0,sys.argv.pop(1));'
                 'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
                 'unittest.main(module=None)')
    command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c', bootstrap, str(ROOT/'product/src'),
               'discover', '-s', str(ROOT/'product/tests'), '-p', args.pattern, '-v']
    env = dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
               TMPDIR=str(ROOT/'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=str(ROOT/'product/src'))
    if args.rubberband:
        env['AI_AD_EDITOR_TEST_RUBBERBAND'] = str(binary)
    record['subprocess_product_pythonpath'] = env['PYTHONPATH']
    record['command'] = command
    save()
    started = time.monotonic()
    with log.open('wb') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    text = log.read_text(encoding='utf-8')
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
    after = frozen()
    record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode,
                  wall_seconds=time.monotonic()-started, frozen_after=after, frozen_equal=before == after,
                  log_sha256=sha(log), methods=int(match[1]) if match else None,
                  suite_seconds=float(match[2]) if match else None,
                  skipped=len(re.findall(r'\.\.\. skipped ', text)), terminal_ok=bool(re.search(r'\bOK\s*$', text)))
    save()
    print(json.dumps({k: record[k] for k in ('exit_code', 'methods', 'suite_seconds', 'skipped', 'frozen_equal', 'terminal_ok')}))
    return 0 if result.returncode == 0 and record['terminal_ok'] and before == after else 1

if __name__ == '__main__':
    raise SystemExit(main())
