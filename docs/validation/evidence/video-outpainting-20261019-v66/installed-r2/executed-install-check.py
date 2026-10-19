"""Check a native offline install and repeat real LaMa outpainting in isolation."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'work', 'evidence', 'public', 'development-evidence', 'development-assets'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    for name, value in vars(args).items():
        setattr(args, name, value.resolve())
    args.work.mkdir(parents=True, exist_ok=False)
    args.evidence.mkdir(parents=True, exist_ok=False)
    args.public.mkdir(parents=True, exist_ok=False)
    before = frozen(); calls = []; files = {}; comparisons = []
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'frozen_before': before, 'calls': calls, 'installed_product_files': files,
        'comparisons': comparisons, 'network': 'disabled', 'virtualization': False,
        'different_machine_accepted': False, 'vace_installed_inference_tested': False}
    shutil.copyfile(__file__, args.evidence/'executed-install-check.py')
    env = dict(os.environ, TEMP=str(args.work), TMP=str(args.work), TMPDIR=str(args.work),
               PYTHONDONTWRITEBYTECODE='1')

    def command(values, label, timeout=180):
        values = list(map(str, values))
        result = subprocess.run(values, cwd=ROOT, env=env, capture_output=True, timeout=timeout)
        out, err = args.evidence/(label+'.stdout.log'), args.evidence/(label+'.stderr.log')
        out.write_bytes(result.stdout); err.write_bytes(result.stderr)
        calls.append({'name': label, 'command': values, 'exit_code': result.returncode,
            'stdout': out.name, 'stderr': err.name, 'stdout_sha256': sha(out), 'stderr_sha256': sha(err)})
        save(args.evidence/'verification.json', record)
        if result.returncode: raise RuntimeError(label+' failed; see retained command logs')
        return result.stdout

    try:
        target = args.work/'installed'
        command([sys.executable, '-I', '-B', '-X', 'utf8', args.bundle/'install.py',
            '--bundle', args.bundle, '--target', target,
            '--manifest-sha256', sha(args.bundle/'manifest.json')], 'install')
        wheel = next((args.bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'): continue
                matches = list(target.rglob(name)); payload = archive.read(name)
                if len(matches) != 1 or matches[0].read_bytes() != payload or payload != (ROOT/'product/src'/name).read_bytes():
                    raise ValueError('installed/source/wheel bytes differ: '+name)
                files[name] = sha(matches[0])
        source_files = {p.relative_to(ROOT/'product/src').as_posix() for p in (ROOT/'product/src/ai_ad_editor').rglob('*')
                        if p.is_file() and p.suffix not in {'.pyc', '.pyo'} and '__pycache__' not in p.parts}
        if set(files) != source_files: raise ValueError('wheel omits or adds product resources')
        prefix = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', target/'run.py']
        caps = json.loads(command([*prefix, 'capabilities'], 'capabilities'))
        if 'agent-video-outpaint-mask-v1' not in json.dumps(caps): raise ValueError('outpaint capability absent')
        command([*prefix, 'schema', 'show'], 'schema')
        command([sys.executable, '-E', '-B', '-X', 'utf8', ROOT/'scripts/smoke_video_outpainting.py',
            '--work', args.work/'media', '--evidence', args.evidence/'media', '--public', args.public/'media',
            '--engine', 'lama', '--blend', 'harmonic', '--launcher', target/'run.py',
            '--source-assets', args.development_assets], 'actual-installed-outpaint', timeout=1800)
        actual = json.loads((args.evidence/'media/verification.json').read_bytes())
        expected = json.loads((args.development_evidence/'verification.json').read_bytes())
        if not actual['frozen_equal'] or actual['frozen_before'] != before: raise ValueError('media source closure changed')
        if expected['engine'] != 'lama' or expected['blend'] != 'harmonic': raise ValueError('wrong development comparison')
        for call in actual['calls']:
            if call['command'][0] == sys.executable:
                if not all(x in call['command'] for x in ('-I', '-S', str(target/'run.py'))):
                    raise ValueError('non-isolated installed CLI')
        for key in ('decoded_rgba_sha256', 'decoded_pcm_sha256', 'quality'):
            same = actual[key] == expected[key]
            comparisons.append({'field': key, 'equal': same, 'development': expected[key], 'installed': actual[key]})
            if not same: raise ValueError('development/install result differs: '+key)
        release = args.public/'release'; release.mkdir()
        for name, path in [('agent-video-kit-cp313-win_amd64.zip', args.bundle.with_suffix('.zip')),
                           ('manifest.json', args.bundle/'manifest.json'), ('install-receipt.json', target/'receipt.json')]:
            shutil.copyfile(path, release/name)
        record.update(status='passed', finished_at_utc=datetime.now(timezone.utc).isoformat(),
            packaged_files=len(files), isolated_cli_calls=actual['cli_calls']+2,
            actual_media=(args.evidence/'media/verification.json').relative_to(ROOT).as_posix(),
            release={p.name: sha(p) for p in release.iterdir()}, frozen_after=frozen())
        record['frozen_equal'] = before == record['frozen_after']
        if not record['frozen_equal']: raise ValueError('product changed during install checks')
    except Exception as exc:
        record.update(status='failed', error=type(exc).__name__+': '+str(exc), frozen_after=frozen())
        raise
    finally:
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(args.evidence/'verification.json', record)
    print(json.dumps({k: record[k] for k in ('status', 'packaged_files', 'isolated_cli_calls', 'frozen_equal')}))


if __name__ == '__main__': main()
