"""Byte-check native wheel/install and repeat actual hardware CLI in isolation."""
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
    parser = argparse.ArgumentParser()
    for flag in ('bundle', 'work', 'output', 'assets', 'source', 'source-assets'):
        parser.add_argument('--'+flag, type=Path, required=True)
    args = parser.parse_args()
    bundle, work, output, assets, source, source_assets = [getattr(args, k.replace('-', '_')).resolve() for k in
        ('bundle', 'work', 'output', 'assets', 'source', 'source-assets')]
    work.mkdir(parents=True, exist_ok=False); output.mkdir(parents=True, exist_ok=False)
    before = frozen(); calls = []; installed_files = {}; comparisons = []
    record = {'status': 'running', 'frozen_before': before, 'calls': calls, 'network': 'disabled',
              'virtual_environment': False, 'other_machine_accepted': False}
    shutil.copyfile(__file__, output/'executed-install-check.py')
    env = dict(os.environ, TEMP=str(work), TMP=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1')
    def command(values, label, timeout=180):
        values = list(map(str, values))
        result = subprocess.run(values, cwd=ROOT, env=env, capture_output=True, timeout=timeout)
        out, err = output/(label+'.stdout.log'), output/(label+'.stderr.log')
        out.write_bytes(result.stdout); err.write_bytes(result.stderr)
        calls.append({'id': label, 'command': values, 'exit_code': result.returncode,
            'stdout': out.name, 'stderr': err.name, 'stdout_sha256': sha(out), 'stderr_sha256': sha(err)})
        save(output/'verification.json', record)
        assert result.returncode == 0, label+' '+result.stdout.decode('utf8', 'replace')[-4000:]+' '+result.stderr.decode('utf8', 'replace')[-4000:]
        return result.stdout
    try:
        target = work/'installed'
        command([sys.executable, '-I', '-B', '-X', 'utf8', bundle/'install.py', '--bundle', bundle,
                 '--target', target, '--manifest-sha256', sha(bundle/'manifest.json')], 'install')
        wheel = next((bundle/'wheels').glob('ai_ad_editor-*.whl'))
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not name.startswith('ai_ad_editor/') or name.endswith('/'): continue
                matches = list(target.rglob(name)); payload = archive.read(name)
                assert len(matches) == 1 and matches[0].read_bytes() == payload == (ROOT/'product/src'/name).read_bytes(), name
                installed_files[name] = sha(matches[0])
        assert len(installed_files) == 132
        prefix = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', target/'run.py']
        caps = json.loads(command([*prefix, 'capabilities'], 'capabilities'))
        assert 'forced_d3d11va_cuda_frames_download_compared_to_cpu_framemd5' in json.dumps(caps)
        schema = json.loads(command([*prefix, 'schema', 'show'], 'schema'))
        assert 'probe_max_bytes' in json.dumps(schema)
        command([sys.executable, '-E', '-B', '-X', 'utf8', ROOT/'scripts/smoke_hardware_acceleration.py',
            '--output', output/'media', '--work', work/'media', '--assets', assets,
            '--installed', target, '--source-assets', source_assets], 'installed-media', timeout=1800)
        actual = json.loads((output/'media/verification.json').read_bytes())
        expected = json.loads((source/'verification.json').read_bytes())
        assert actual['frozen_equal'] and actual['frozen_before'] == before
        for call in actual['calls']:
            if call['command'][0] == sys.executable:
                assert '-I' in call['command'] and '-S' in call['command'] and str(target/'run.py') in call['command']
        for item, baseline in zip(actual['artifacts'], expected['artifacts'], strict=True):
            assert item['id'] == baseline['id']
            left, right = ROOT/item['path'], ROOT/baseline['path']
            equal = {}
            for kind, options in [('video', ['-map', '0:v:0', '-pix_fmt', 'yuv420p10le' if 'hevc10' in item['id'] else 'yuv420p']),
                                   ('audio', ['-map', '0:a:0', '-c:a', 'pcm_s16le'])]:
                values = []
                for label, media in [('installed', left), ('development', right)]:
                    raw = command([shutil.which('ffmpeg'), '-v', 'error', '-i', media, *options,
                        '-f', 'framemd5', '-'], item['id']+'-'+kind+'-'+label)
                    # The generated software/header fields are not content.
                    values.append([line.strip() for line in raw.decode().splitlines() if line and not line.startswith('#')])
                equal[kind] = bool(values[0]) and values[0] == values[1]
                assert equal[kind], item['id']+' '+kind+' decoded difference'
            comparisons.append({'id': item['id'], 'decoded_video_equal': equal['video'],
                'decoded_pcm_equal': equal['audio'], 'frames': item['frames'], 'audio_sample_frames': item['audio_sample_frames']})
        release = assets/'release'; release.mkdir()
        for name, path in [('agent-video-kit-cp313-win_amd64.zip', bundle.with_suffix('.zip')),
                           ('manifest.json', bundle/'manifest.json'), ('install-receipt.json', target/'receipt.json')]:
            shutil.copyfile(path, release/name)
        record.update(status='passed', finished_at_utc=datetime.now(timezone.utc).isoformat(),
            installed_files=installed_files, packaged_files=len(installed_files), comparisons=comparisons,
            isolated_cli_calls=actual['cli_calls']+2, actual_media= str((output/'media/verification.json').relative_to(ROOT)),
            release={p.name: sha(p) for p in release.iterdir()}, frozen_after=frozen())
        record['frozen_equal'] = record['frozen_before'] == record['frozen_after']
        assert record['frozen_equal']
    except Exception as exc:
        record.update(status='failed', error=str(exc), frozen_after=frozen())
        save(output/'verification.json', record)
        raise
    save(output/'verification.json', record)
    print(json.dumps({key: record[key] for key in ('status', 'packaged_files', 'isolated_cli_calls', 'frozen_equal')}))


if __name__ == '__main__': main()
