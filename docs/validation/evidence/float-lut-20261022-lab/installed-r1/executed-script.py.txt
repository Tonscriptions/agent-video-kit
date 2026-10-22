"""Fresh offline eight-wheel package; isolated real CLI media and 360 methods."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
REL = ROOT/'docs/validation/evidence/float-lut-20261022-lab'


def main():
    work = ROOT/'product/.runtime/float-lut-20261022/installed-r1'
    evidence = REL/'installed-r1'
    assert not work.exists() and not evidence.exists()
    work.mkdir(parents=True); evidence.mkdir()
    before = frozen(); assert len(before) == 309
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
              'calls': [], 'checks': [], 'frozen_before': before, 'generator_sha256': sha(Path(__file__)),
              'network': False, 'virtualization': False, 'native_windows': True, 'global_site_packages_changed': False,
              'published': False, 'full_capcut_parity': False}
    def save():
        (evidence/'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    def check(name, ok, **details):
        record['checks'].append({'name': name, 'ok': bool(ok), **details}); save()
        assert ok, name
    env = dict(os.environ, TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'))
    env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES', None)
    def run(name, command):
        command = list(map(str, command))
        p = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=2400, creationflags=subprocess.CREATE_NO_WINDOW)
        for stream in ['stdout', 'stderr']:
            (evidence/(name+'.'+stream+'.log')).write_bytes(getattr(p, stream))
        record['calls'].append({'name': name, 'command': command, 'exit_code': p.returncode,
            'stdout_sha256': sha(evidence/(name+'.stdout.log')), 'stderr_sha256': sha(evidence/(name+'.stderr.log'))}); save()
        assert p.returncode == 0, (name, p.stdout[-1500:].decode('utf8', 'replace'), p.stderr[-2000:].decode('utf8', 'replace'))
        return p.stdout
    try:
        foundation = json.loads((REL/'foundation-r1.json').read_bytes())
        deps = {k:v for k,v in foundation['copied_inputs'].items() if k.startswith('sources/python-runtime/cp313-win_amd64-media/')}; assert len(deps) == 9
        check('nine pinned wheelhouse inputs unchanged', all(sha(ROOT/k) == v for k, v in deps.items()))
        record['dependency_artifact_inputs'] = deps
        standard = json.loads((REL/'native-r3/verification.json').read_bytes())
        check('actual native 160 methods accepted at this source', standard['status'] == 'passed' and standard['methods'] == 160 and standard['frozen_after'] == before)
        reference = REL/'media-r1/verification.json'
        media = json.loads(reference.read_bytes())
        check('actual source public CLI media accepted', media['status'] == 'passed-public-CLI-floating-LUTs-and-native-float-previews' and media['actual_public_render_CLI_processes'] == 2 and media['actual_public_preview_CLI_processes'] == 3 and media['frozen_after'] == before)
        bundle, installed = work/'bundle', work/'installed'
        record['build'] = json.loads(run('build', [sys.executable, '-E', '-B', '-X', 'utf8', ROOT/'product/offline/build.py', '--output', bundle, '--wheelhouse', ROOT/'sources/python-runtime/cp313-win_amd64-media']))
        record['installation'] = json.loads(run('install', [sys.executable, '-I', '-B', '-X', 'utf8', bundle/'install.py', '--target', installed, '--manifest-sha256', record['build']['manifest_sha256']]))
        manifest = json.loads((bundle/'manifest.json').read_bytes())
        check('eight pinned offline wheels', len(manifest['wheels']) == 8 and manifest['runtime_profile'] == 'media-analysis-v1')
        ext = {'.py', '.mjs', '.json', '.txt', '.c', '.dll'}
        source = {p.name: p.read_bytes() for p in (ROOT/'product/src/ai_ad_editor').iterdir() if p.is_file() and p.suffix in ext}
        site = {p.name: p.read_bytes() for p in (installed/'site/ai_ad_editor').iterdir() if p.is_file() and p.suffix in ext}
        wheel = next(bundle/w['path'] for w in manifest['wheels'] if w['name'] == 'ai-ad-editor')
        with zipfile.ZipFile(wheel) as z:
            shipped = {}
            for name in z.namelist():
                for prefix in ('ai_ad_editor/', 'ai_ad_editor-0.1.0.data/purelib/ai_ad_editor/'):
                    if name.startswith(prefix) and not name.endswith('/'):
                        key = name[len(prefix):]; assert '/' not in key and key not in shipped
                        shipped[key] = z.read(name)
            tag = z.read(next(n for n in z.namelist() if n.endswith('.dist-info/WHEEL'))).decode('utf8')
            check('native Windows wheel', 'Root-Is-Purelib: false' in tag and 'Tag: py3-none-win_amd64' in tag)
        check('185 source wheel site resources exact', len(source) == 185 and source == site == shipped, resource_count=len(source))
        record['resource_hashes'] = {k: 'sha256:'+hashlib.sha256(v).hexdigest() for k, v in sorted(source.items())}
        numpy = next(w for w in manifest['wheels'] if w['name'] == 'numpy')
        check('official NumPy 2.4.2 pinned artifact', numpy['version'] == '2.4.2' and sha(bundle/numpy['path']) == 'sha256:7df2de1e4fba69a51c06c28f5a3de36731eb9639feb8e1cf7e4a7b0daf4cf622')
        numpy_files, notices = {}, {}
        with zipfile.ZipFile(bundle/numpy['path']) as z:
            for name in z.namelist():
                if name.endswith('/') or name.endswith('.dist-info/RECORD'):
                    continue
                path = installed/'site'/name
                assert path.resolve().is_relative_to(installed/'site') and path.read_bytes() == z.read(name)
                numpy_files[name] = sha(path)
                if any(n in Path(name).name.upper() for n in ('LICENSE', 'COPYING', 'NOTICE')):
                    notice = bundle/'licenses/numpy'/name
                    assert notice.read_bytes() == z.read(name); notices[name] = sha(notice)
        check('931 NumPy files and original notices exact', len(numpy_files) == 931 and bool(notices))
        record['numpy_distribution'] = {'files': numpy_files, 'notices': notices, 'host_distribution_copied': False}
        prefix = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', installed/'run.py']
        cap = json.loads(run('capabilities', [*prefix, 'capabilities']))
        run('schema', [*prefix, 'schema', 'show']); run('effects', [*prefix, 'effects', 'list'])
        record['actual_discovery_CLI_processes'] = 3
        run('isolated-real-media', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', ROOT/'scripts/smoke_float_lut_media.py', '--revision', 'installed-r1', '--installed', installed, '--reference', reference])
        installed_media = REL/'media-installed-r1/verification.json'
        m = json.loads(installed_media.read_bytes())
        check('isolated source-identical real CLI media', m['status'] == 'passed-public-CLI-floating-LUTs-and-native-float-previews' and m['isolated'] and m['actual_public_render_CLI_processes'] == 2 and m['actual_public_preview_CLI_processes'] == 3)
        record['actual_media_receipt_sha256'] = sha(installed_media)
        names = ['test_float_raster', 'test_float_geometry', 'test_float_pixels', 'test_float_video_source', 'test_float_yuv', 'test_float_color_signal', 'test_float_bundle', 'test_queue_reuse', 'test_float_composite', 'test_float_timeline', 'test_float_bundle_source', 'test_float_audio_graph', 'test_float_stream', 'test_float_native_pipe', 'test_float_native_source', 'test_float_standard_render', 'test_timeline_preview', 'test_float_preview', 'test_float_exposure', 'test_float_mask', 'test_float_crop', 'test_float_lut']
        bootstrap = ('import sys,unittest,json,pathlib;sys.path[:0]=[sys.argv[1],sys.argv[2]];'
            'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
            'names=json.loads(sys.argv[3]);r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names));'
            'origins={n:str(pathlib.Path(m.__file__).resolve()) for n,m in sys.modules.items() if getattr(m,"__file__",None) and (n=="ai_ad_editor" or n.startswith("ai_ad_editor.") or n=="numpy" or n.startswith("numpy.") or n=="PIL" or n.startswith("PIL."))};'
            'print(json.dumps({"methods":r.testsRun,"skipped":len(r.skipped),"origins":origins,"native_test_records":{n:getattr(sys.modules[n],"NATIVE_CALLS",[]) for n in names}}));raise SystemExit(0 if r.wasSuccessful() and not r.skipped else 1)')
        result = json.loads(run('isolated-360-methods', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', bootstrap, installed/'site', ROOT/'product/tests', json.dumps(names)]))
        text = (evidence/'isolated-360-methods.stderr.log').read_text('utf8')
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
        check('360 actual isolated methods terminal OK no skip', bool(match) and int(match[1]) == result['methods'] == 360 and result['skipped'] == 0 and re.search(r'\bOK\s*$', text) is not None)
        check('all runtime modules from fresh installed site', all(Path(v).is_relative_to(installed/'site') for v in result['origins'].values()), actual_origins=len(result['origins']))
        record['isolated_methods'] = {**result, 'suite_seconds': float(match[2])}
        check('185 installed resources remain exact', all((installed/'site/ai_ad_editor'/k).read_bytes() == v for k, v in source.items()))
        check('309 product inputs and nine dependencies unchanged', frozen() == before and all(sha(ROOT/k) == v for k, v in deps.items()))
        record.update(status='passed-fresh-eight-wheel-185-resources-real-previews-and-360-methods', standard_render_integrated=True, native_float_preview_integrated=True, native_float_exposure_integrated=True,native_float_mask_integrated=True, native_float_crop_integrated=True, native_float_lut_integrated=True, default_backend_migrated=False)
    except BaseException as exc:
        record.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen()); save()
        (evidence/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k: record.get(k) for k in ['status', 'error']}), flush=True)


if __name__ == '__main__':
    main()
