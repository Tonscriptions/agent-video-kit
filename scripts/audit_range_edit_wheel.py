"""Build offline and exercise all six V39 actions from isolated wheel imports."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import site
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from smoke_fragments import frozen, save, sha

ROOT = Path(__file__).resolve().parents[1]


def run(work, source_work):
    work.mkdir(parents=True, exist_ok=False)
    before = frozen()
    env = dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
        TMPDIR=str(ROOT/'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1',
        PIP_CACHE_DIR=str(ROOT/'product/.runtime/cache/pip'), AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    built = subprocess.run([sys.executable, '-B', '-m', 'pip', 'wheel', '--no-index', '--no-deps', '--no-build-isolation',
        str(ROOT/'product'), '--wheel-dir', str(work/'dist')], cwd=ROOT, env=env, capture_output=True, timeout=300)
    (work/'build.stdout.log').write_bytes(built.stdout)
    (work/'build.stderr.log').write_bytes(built.stderr)
    assert built.returncode == 0, built.stdout.decode('utf-8', 'replace')
    wheel = next((work/'dist').glob('*.whl'))
    isolated = work/'isolated-site'; isolated.mkdir()
    files = {}
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            path = (isolated/item.filename).resolve()
            assert path.is_relative_to(isolated.resolve())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(item))
            if item.filename.startswith('ai_ad_editor/'):
                assert path.read_bytes() == (ROOT/'product/src'/item.filename).read_bytes(), item.filename
                files[item.filename] = {'sha256': sha(path), 'bytes': path.stat().st_size}
    assert 'ai_ad_editor/range_edits.py' in files
    optional = site.getusersitepackages()
    boot = ('import sys;from pathlib import Path;optional=sys.argv.pop(1);package=sys.argv.pop(1);'
        'sys.path.insert(0,optional);sys.path.insert(0,package);'
        'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
        'from ai_ad_editor.cli import main;code=main();'
        'assert all(Path(m.__file__).resolve().is_relative_to(Path(package).resolve()) '
        'for n,m in tuple(sys.modules.items()) if n.startswith("ai_ad_editor") and getattr(m,"__file__",None));'
        'raise SystemExit(code)')
    calls = []

    def cli(*args):
        started = time.monotonic()
        process = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', boot,
            optional, str(isolated), *map(str, args)], cwd=work, env=env, capture_output=True, timeout=300)
        index = len(calls)
        (work/f'{index:02}.stdout.log').write_bytes(process.stdout)
        (work/f'{index:02}.stderr.log').write_bytes(process.stderr)
        value = json.loads(process.stdout.decode('utf-8-sig')) if process.stdout.strip().startswith(b'{') else {'help': process.stdout.decode('utf-8', 'replace')}
        calls.append({'index': index, 'args': list(map(str, args)), 'exit_code': process.returncode,
            'seconds': time.monotonic()-started, 'stdout_sha256': 'sha256:'+hashlib.sha256(process.stdout).hexdigest(),
            'stderr_sha256': 'sha256:'+hashlib.sha256(process.stderr).hexdigest()})
        save(work/'calls-in-progress.json', calls)
        assert process.returncode == 0, value
        return value

    cli('version')
    manifest = cli('capabilities')
    assert 'range_edits' in manifest['data']['capabilities']
    cli('timeline', 'edit', '--help')
    public = ROOT/'docs/assets/range-edits-20261018'
    decoded = {}
    for name in ('R01', 'R02', 'R03', 'R04', 'R05', 'R06'):
        path = work/name
        shutil.copytree(source_work/(name+'-before'), path)
        project = json.loads((public/(name+'-before-project.json')).read_text(encoding='utf-8'))
        save(path/'project.json', project)
        req = public/(name+'-request.json')
        unchanged = (path/'project.json').read_bytes()
        plan = cli('timeline', 'edit', '--project', path, '--input', req, '--dry-run')['data']['plan']
        assert unchanged == (path/'project.json').read_bytes()
        cli('timeline', 'edit', '--project', path, '--input', req, '--expected-project-sha256', plan['base_project_sha256'], '--idempotency-key', 'wheel-'+name)
        saved = (path/'project.json').read_bytes()
        cli('timeline', 'edit', '--project', path, '--input', req, '--expected-project-sha256', plan['base_project_sha256'], '--idempotency-key', 'wheel-'+name)
        assert saved == (path/'project.json').read_bytes()
        cli('validate', '--project', path, '--strict-rights')
        if name in ('R02', 'R05', 'R06'):
            movie = path/'renders/isolated.mkv'
            cli('render', '--project', path, '--output', movie, '--container', 'mkv', '--crf', 0,
                '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_f32le', '--publish')
            expected = json.loads((public/(name+'-verification.json')).read_text(encoding='utf-8'))
            row = {}
            for kind, flags in [('rgb', ['-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo']),
                    ('pcm', ['-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le'])]:
                raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(movie), *flags, 'pipe:1'])
                row[kind+'_sha256'] = 'sha256:'+hashlib.sha256(raw).hexdigest()
                assert row[kind+'_sha256'] == expected[kind+'_sha256']
            decoded[name] = row
    after = frozen()
    assert before == after
    result = {'status': 'passed', 'source_files': files, 'file_count': len(files), 'source_bytes_exact': True,
        'wheel': {'filename': wheel.name, 'bytes': wheel.stat().st_size, 'sha256': sha(wheel)}, 'calls': calls,
        'isolated_product_imports': True, 'existing_optional_dependency_site': optional,
        'decoded_matches_public': decoded, 'all_six_actions': True,
        'frozen_before': before, 'frozen_after': after, 'frozen_equal': True,
        'clean_machine_or_bundled_schema_accepted': False}
    save(work/'verification.json', result)
    print(json.dumps({'status': 'passed', 'file_count': len(files), 'cli_count': len(calls), 'rendered_cases': list(decoded)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source-work', type=Path, required=True)
    args = parser.parse_args()
    run(args.work.resolve(), args.source_work.resolve())
