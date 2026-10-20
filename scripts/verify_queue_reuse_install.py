"""Build/install existing local wheels and repeat actual batch reuse in isolation."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_frozen_regression import frozen


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'evidence', 'assets', 'wheelhouse', 'font', 'font-license', 'development'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    work, evidence = args.work.resolve(), args.evidence.resolve()
    if work.exists() or evidence.exists():
        raise ValueError('Choose new installation and evidence directories')
    work.mkdir(parents=True)
    evidence.mkdir(parents=True)
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'native_windows': sys.platform == 'win32', 'virtualization': False,
              'calls': [], 'checks': [], 'frozen_before': frozen(), 'goal_complete': False}
    def save():
        (evidence / 'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    def check(name, ok, **details):
        record['checks'].append({'name': name, 'ok': bool(ok), **details})
        save()
        if not ok:
            raise AssertionError(name)
    def run(label, argv):
        env = dict(os.environ)
        env.update(TEMP=str(ROOT / 'product/.runtime/temp'), TMP=str(ROOT / 'product/.runtime/temp'),
                   TMPDIR=str(ROOT / 'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1')
        command = [str(v) for v in argv]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=1200)
        (evidence / (label + '.stdout.log')).write_bytes(result.stdout)
        (evidence / (label + '.stderr.log')).write_bytes(result.stderr)
        record['calls'].append({'label': label, 'command': command, 'exit_code': result.returncode})
        save()
        if result.returncode:
            raise AssertionError(label + ': ' + result.stderr[-2000:].decode('utf-8', 'replace'))
        return result.stdout.decode('utf-8-sig')
    try:
        bundle = work / 'bundle'
        built = json.loads(run('build', [sys.executable, '-B', '-X', 'utf8', ROOT / 'product/offline/build.py',
            '--output', bundle, '--wheelhouse', args.wheelhouse.resolve()]))
        record['bundle'] = built
        installed = work / 'installed'
        receipt = json.loads(run('install', [sys.executable, '-I', '-B', '-X', 'utf8', bundle / 'install.py',
            '--target', installed, '--manifest-sha256', built['manifest_sha256']]))
        record['installation'] = receipt
        package = ROOT / 'product/src/ai_ad_editor'
        source = {p.name: p.read_bytes() for p in package.iterdir() if p.is_file() and p.suffix in {'.py', '.mjs', '.json', '.txt'}}
        manifest = json.loads((bundle / 'manifest.json').read_bytes())
        wheel = next(bundle / r['path'] for r in manifest['wheels'] if r['name'] == 'ai-ad-editor')
        with zipfile.ZipFile(wheel) as archive:
            shipped = {n.split('/', 1)[1]: archive.read(n) for n in archive.namelist()
                       if n.startswith('ai_ad_editor/') and not n.endswith('/')}
        actual = {p.name: p.read_bytes() for p in (installed / 'site/ai_ad_editor').iterdir()
                  if p.is_file() and p.suffix in {'.py', '.mjs', '.json', '.txt'}}
        check('source-wheel-installed-exact', source == shipped == actual, resources=len(source), wheels=len(manifest['wheels']))
        record['resource_hashes'] = {k: hashlib.sha256(v).hexdigest() for k, v in sorted(source.items())}
        for label, command in (('capabilities', ['capabilities']), ('schema', ['schema', 'show']), ('queue-help', ['queue', 'run', '--help'])):
            run(label, [sys.executable, '-I', '-S', '-B', '-X', 'utf8', installed / 'run.py', *command])
        origins = json.loads(run('module-origins', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c',
            'import sys,json,pathlib;sys.path.insert(0,sys.argv[1]);import ai_ad_editor.cli,ai_ad_editor.queue_reuse;'
            'print(json.dumps({m.__name__:m.__file__ for m in [ai_ad_editor.cli,ai_ad_editor.queue_reuse]}))', str(installed / 'site')]))
        check('isolated-imports-under-install', all(Path(path).resolve().is_relative_to(installed / 'site') for path in origins.values()), origins=origins)
        run('actual-installed-media', [sys.executable, '-B', '-X', 'utf8', ROOT / 'scripts/smoke_queue_reuse.py',
            '--work', work / 'media', '--evidence', evidence / 'media', '--assets', args.assets.resolve(),
            '--font', args.font.resolve(), '--font-license', args.font_license.resolve(), '--installed', installed])
        media = json.loads((evidence / 'media/verification.json').read_bytes())
        development = json.loads(args.development.resolve().read_bytes())
        check('both-native-runs-passed', media['status'] == development['status'] == 'passed' and media['frozen_equal'] and development['frozen_equal'])
        for name in media['decoded']:
            for field in ('frame_sha256', 'pts', 'pcm_sha256', 'pcm_float_values', 'frames', 'alpha_min', 'alpha_max'):
                check(name+'-'+field+'-equals-development', media['decoded'][name][field] == development['decoded'][name][field])
        record.update(status='passed', isolated_cli_calls=media['cli_calls']+3, module_origin_probes=1,
                      capcut_parity_accepted=False, no_external_dependencies_bundled=['Python', 'FFmpeg', 'system DLLs'])
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen())
        record['frozen_equal'] = record['frozen_before'] == record['frozen_after']
        save()
    if not record['frozen_equal']:
        raise AssertionError('Product input bytes changed')
    print(json.dumps({k: record[k] for k in ('status', 'isolated_cli_calls', 'frozen_equal')}))


if __name__ == '__main__':
    main()
