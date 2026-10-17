"""Offline wheel bytes and source-isolated CLI fragment roundtrip checks."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, site, subprocess, sys, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

def run(work, source_work):
    work.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
        TMPDIR=str(ROOT/'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1',
        PIP_CACHE_DIR=str(ROOT/'product/.runtime/cache/pip'), AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    result = subprocess.run([sys.executable, '-B', '-m', 'pip', 'wheel', '--no-index', '--no-deps', '--no-build-isolation',
        str(ROOT/'product'), '--wheel-dir', str(work/'dist')], cwd=ROOT, env=env, capture_output=True, timeout=300)
    (work/'build.stdout.log').write_bytes(result.stdout); (work/'build.stderr.log').write_bytes(result.stderr)
    assert result.returncode == 0, (result.stdout, result.stderr)
    wheel = next((work/'dist').glob('*.whl')); isolated = work/'isolated-site'; isolated.mkdir()
    files = {}
    with zipfile.ZipFile(wheel) as z:
        for item in z.infolist():
            target = (isolated/item.filename).resolve(); assert target.is_relative_to(isolated.resolve())
            if item.is_dir():
                continue
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(z.read(item))
            if item.filename.startswith('ai_ad_editor/'):
                assert target.read_bytes() == (ROOT/'product/src'/item.filename).read_bytes(), item.filename
                files[item.filename] = {'sha256': sha(target), 'bytes': target.stat().st_size}
    assert 'ai_ad_editor/fragments.py' in files
    assert (isolated/'ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes() == (ROOT/'sources/upstream/openfilm/LICENSE').read_bytes()
    # The product is isolated from repository imports. Explicitly expose the
    # already installed optional libraries; this is not a clean-machine claim.
    optional_site = site.getusersitepackages()
    bootstrap = ('import sys;from pathlib import Path;optional=sys.argv.pop(1);package=sys.argv.pop(1);'
        'sys.path.insert(0,optional);sys.path.insert(0,package);'
        'from ai_ad_editor.cli import main;code=main();'
        'assert all(Path(m.__file__).resolve().is_relative_to(Path(package).resolve()) '
        'for n,m in tuple(sys.modules.items()) if n.startswith("ai_ad_editor") and getattr(m,"__file__",None));'
        'raise SystemExit(code)')
    calls = []
    def cli(*args):
        start = time.monotonic()
        r = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', bootstrap, optional_site, str(isolated), *map(str, args)],
            cwd=work, env=env, capture_output=True, timeout=300)
        index = len(calls)
        (work/f'{index:02}.stdout.log').write_bytes(r.stdout); (work/f'{index:02}.stderr.log').write_bytes(r.stderr)
        calls.append({'index': index, 'args': list(map(str, args)), 'exit_code': r.returncode, 'seconds': time.monotonic()-start,
            'stdout_sha256': 'sha256:'+hashlib.sha256(r.stdout).hexdigest(), 'stderr_sha256': 'sha256:'+hashlib.sha256(r.stderr).hexdigest()})
        value = json.loads(r.stdout.decode('utf-8-sig')) if r.stdout.strip().startswith(b'{') else {'help': r.stdout.decode('utf-8', 'replace')}
        assert r.returncode == 0, value
        return value
    public = ROOT/'docs/assets/fragments-20261018'
    library = work/'library'; shutil.copytree(public/'library', library)
    project = work/'project'; shutil.copytree(source_work/'N04', project)
    cli('version'); cli('capabilities'); cli('fragment', '--help')
    cli('fragment', 'list', '--library', library, '--query', 'partial')
    cli('fragment', 'inspect', '--library', library, '--id', 'cta', '--version', 2)
    request = work/'request.json'; save(request, {'id': 'cta', 'version': 2, 'sequence_id': 'seq_main',
        'track_id': 'track_video_1', 'at_tick': 90000, 'instance_id': 'wheel'})
    dry = cli('fragment', 'apply', '--project', project, '--library', library, '--input', request, '--dry-run')
    applied = cli('fragment', 'apply', '--project', project, '--library', library, '--input', request,
        '--expected-project-sha256', dry['data']['plan']['project_sha256'], '--expected-fragment-sha256', dry['data']['plan']['fragment_sha256'])
    cli('validate', '--project', project, '--strict-rights')
    path = project/'renders/isolated-fragment.mkv'
    cli('render', '--project', project, '--output', path, '--container', 'mkv', '--crf', 0,
        '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_f32le', '--publish')
    decoded = {}
    expected = json.loads((public/'C02-verification.json').read_text(encoding='utf-8'))
    for kind, flags in (('rgb', ['-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo']), ('pcm', ['-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le'])):
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), *flags, 'pipe:1'])
        decoded[kind+'_sha256'] = 'sha256:'+hashlib.sha256(raw).hexdigest()
        assert decoded[kind+'_sha256'] == expected[kind+'_sha256']
    resaved = work/'resaved'
    save(request, {'id': 'wheel-saved', 'version': 1, 'sequence_id': 'seq_main',
        'clip_ids': [applied['data']['plan']['entry_clip']['id']]})
    cli('fragment', 'save', '--project', project, '--library', resaved, '--input', request)
    cli('fragment', 'inspect', '--library', resaved, '--id', 'wheel-saved', '--version', 1)
    record = {'status': 'passed', 'wheel': {'filename': wheel.name, 'bytes': wheel.stat().st_size, 'sha256': sha(wheel)},
        'source_files': files, 'file_count': len(files), 'source_bytes_exact': True, 'license_bytes_exact': True,
        'calls': calls, 'decoded_matches_public_C02': decoded, 'resaved_nested_instance': True,
        'product_imports_confined_to_isolated_site': True, 'existing_optional_dependency_site': optional_site,
        'clean_machine_or_bundled_schema_accepted': False}
    save(work/'verification.json', record)
    print(json.dumps({'file_count': len(files), 'cli_count': len(calls), 'decoded_matches_public_C02': decoded}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--work', type=Path, required=True); parser.add_argument('--source-work', type=Path, required=True)
    args = parser.parse_args(); run(args.work.resolve(), args.source_work.resolve())
