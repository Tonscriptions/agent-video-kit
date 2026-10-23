"""Fresh offline eight-wheel package; isolated real CLI media and 118 methods."""
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
REL = ROOT/'docs/validation/evidence/float-shaper-20261023-lab'


def main():
    work = ROOT/'product/.runtime/float-shaper-20261023/installed-r1'
    evidence = REL/'installed-r1'
    assert not work.exists() and not evidence.exists()
    work.mkdir(parents=True); evidence.mkdir()
    before = frozen(); assert len(before) == 331
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
              'calls': [], 'checks': [], 'frozen_before': before, 'generator_sha256': sha(Path(__file__)),
              'network': False, 'virtualization': False, 'native_windows': True, 'global_site_packages_changed': False,
              'published': False, 'full_capcut_parity': False}
    def save():
        (evidence/'verification.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    def check(name, ok, **details):
        record['checks'].append({'name': name, 'ok': bool(ok), **details}); save()
        assert ok, name
    env = dict(os.environ, TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'), TMPDIR=str(ROOT/'product/.runtime/temp'))
    env['AI_AD_EDITOR_TEST_HTML_RUNTIME']=str(ROOT.parents[2]/'product/.runtime/html-motion-runtime-20261018-e2.json')
    env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES', None)
    def run(name, command):
        command = list(map(str, command))
        p = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=7200, creationflags=subprocess.CREATE_NO_WINDOW)
        for stream in ['stdout', 'stderr']:
            (evidence/(name+'.'+stream+'.log')).write_bytes(getattr(p, stream))
        record['calls'].append({'name': name, 'command': command, 'exit_code': p.returncode,
            'stdout_sha256': sha(evidence/(name+'.stdout.log')), 'stderr_sha256': sha(evidence/(name+'.stderr.log'))}); save()
        assert p.returncode == 0, (name, p.stdout[-1500:].decode('utf8', 'replace'), p.stderr[-2000:].decode('utf8', 'replace'))
        return p.stdout
    try:
        foundation = json.loads((REL/'foundation-r1.json').read_bytes())
        deps = {k:v for k,v in foundation['copied_inputs'].items() if k.startswith('sources/python-runtime/cp313-win_amd64-media/')}; assert len(deps) == 9
        check('nine pinned wheelhouse inputs unchanged', all(sha(ROOT/k) == v for k,v in deps.items()))
        record['dependency_artifact_inputs']=deps
        standard=json.loads((REL/'native-r2/verification.json').read_bytes())
        check('actual 1D shaper source118 accepted', standard['status']=='passed' and standard['methods']==118 and standard['skipped']==0 and standard['frozen_before']==standard['frozen_after']==before)
        proof4k=json.loads((REL/'4k-r1/verification.json').read_bytes())
        check('actual default budget4K shaper proof bound', proof4k['status']=='passed-actual-default-budget-4K-formal-preview-and-independent-pixels' and proof4k['public_CLI_processes']==8 and proof4k['frozen_before']==proof4k['frozen_after']==before)
        reference=REL/'media-r1/verification.json'
        media=json.loads(reference.read_bytes())
        check('actual source public CLI shaper media accepted', media['status']=='passed-public-CLI-floating-shaper-and-native-float-previews' and media['actual_public_render_CLI_processes']==2 and media['actual_public_preview_CLI_processes']==3 and media['frozen_before']==media['frozen_after']==before)
        record['accepted_source_evidence']={'source':sha(REL/'native-r2/verification.json'),'4K':sha(REL/'4k-r1/verification.json'),'media':sha(reference)}
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
        check('197 source wheel site resources exact', len(source) == 197 and source == site == shipped, resource_count=len(source))
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
        run('isolated-real-media', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', ROOT/'scripts/smoke_float_shaper_media.py', '--revision', 'installed-r1', '--installed', installed, '--reference', reference])
        installed_media = REL/'media-installed-r1/verification.json'
        m = json.loads(installed_media.read_bytes())
        check('isolated source-identical real CLI media', m['status'] == 'passed-public-CLI-floating-shaper-and-native-float-previews' and m['isolated'] and m['actual_public_render_CLI_processes'] == 2 and m['actual_public_preview_CLI_processes'] == 3)
        record['actual_media_receipt_sha256'] = sha(installed_media)
        names = ['test_float_shaper','test_float_lut','test_lut_automation','test_float_preview']
        result = json.loads(run('isolated-118-methods', [sys.executable, '-I', '-S', '-B', '-X', 'utf8', ROOT/'scripts/run_float_shaper_installed_suite.py', installed/'site', ROOT/'product/tests', json.dumps(names)]))
        text = (evidence/'isolated-118-methods.stderr.log').read_text('utf8')
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
        check('118 actual isolated methods terminal OK no skip', bool(match) and int(match[1]) == result['methods'] == 118 and result['skipped'] == 0 and re.search(r'\bOK\s*$', text) is not None)
        check('all runtime modules from fresh installed site', all(Path(v).is_relative_to(installed/'site') for v in result['origins'].values()), actual_origins=len(result['origins']))
        record['isolated_methods'] = {**result, 'suite_seconds': float(match[2])}
        check('197 installed resources remain exact', all((installed/'site/ai_ad_editor'/k).read_bytes() == v for k, v in source.items()))
        check('331 product inputs and nine dependencies unchanged', frozen() == before and all(sha(ROOT/k) == v for k, v in deps.items()))
        record.update(status='passed-fresh-eight-wheel-197-resources-real-previews-and-118-methods', standard_render_integrated=True, native_float_preview_integrated=True, native_float_exposure_integrated=True,native_float_mask_integrated=True, native_float_crop_integrated=True, native_float_lut_integrated=True, native_float_curves_integrated=True, native_float_levels_integrated=True, native_animated_exposure_integrated=True, native_float_balance_integrated=True, native_float_selective_hsl_integrated=True, native_float_basic_tone_integrated=True, native_float_gaussian_integrated=True, native_float_spatial_means_integrated=True, native_float_sharpen_integrated=True, default_backend_migrated=False, native_float_keyer_integrated=True, native_float_1D_shaper_integrated=True)
    except BaseException as exc:
        record.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=frozen()); save()
        (evidence/'executed-script.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k: record.get(k) for k in ['status', 'error']}), flush=True)


if __name__ == '__main__':
    main()
