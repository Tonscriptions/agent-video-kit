"""Run inspected upstream pure tests, with an explicit closed browser seam."""
from datetime import datetime, timezone
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
SOURCE = ROOT / 'product/.runtime/openfilm-r16-source'
REL = Path('docs/validation/evidence/openfilm-reuse-20261022-r16')
OUT = ROOT / REL / 'tests-r1'


def sha(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def freeze():
    spec = importlib.util.spec_from_file_location('main_freeze', MAIN / 'scripts/run_frozen_regression.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.frozen()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    capture = json.loads((ROOT / REL / 'capture-r2/verification.json').read_bytes())
    assert capture['status'] == 'passed-pinned-source-capture'
    expected = json.loads((ROOT / REL / 'capture-r2/source-tree.json').read_bytes())
    def verify_source():
        actual = {p.relative_to(SOURCE).as_posix(): {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
                  for p in SOURCE.rglob('*') if p.is_file()}
        assert actual == expected
    verify_source()
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'fixed_head': capture['fixed_head'], 'frozen_before': freeze(), 'calls': [],
              'browser_tabs_opened': 0, 'actual_browser_launched': False, 'virtualization': False,
              'upstream_install': False, 'provider_or_model_called': False,
              'new_product_tests': 0, 'new_rendered_media': 0}
    (OUT / 'executed-verifier.py.txt').write_bytes(Path(__file__).read_bytes())
    temp = ROOT / 'product/.runtime/openfilm-r16-temp'
    temp.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, TEMP=str(temp), TMP=str(temp), OPENFILM_HOME=str(temp / 'home'))
    node = shutil.which('node')
    assert node
    record['node'] = {'path': node, 'sha256': sha(Path(node).read_bytes())}

    def run(label, args, cwd=SOURCE):
        command = [node, *map(str, args)]
        start = time.monotonic()
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=120,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (OUT / (label + '.stdout.txt')).write_bytes(result.stdout)
        (OUT / (label + '.stderr.txt')).write_bytes(result.stderr)
        text = result.stdout.decode('utf8')
        row = {'label': label, 'command': command, 'cwd': str(cwd), 'exit_code': result.returncode,
               'seconds': time.monotonic() - start, 'stdout_sha256': sha(result.stdout),
               'stderr_sha256': sha(result.stderr)}
        row['summary'] = {k: int(v) for k, v in re.findall(r'^# (tests|pass|fail|cancelled|skipped|todo) (\d+)$', text, re.M)}
        record['calls'].append(row)
        save(OUT / 'verification.json', record)
        assert result.returncode == 0, (label, result.stderr.decode(errors='replace')[-1200:])
        return text
    try:
        record['node_version'] = run('node-version', ['--version']).strip()
        original = (
            'packages/openfilm/studio/server/fcpxml.test.mjs',
            'packages/openfilm/studio/server/diagnostics.test.mjs',
            'packages/openfilm/src/problems.test.mjs',
            'apps/desktop/src/pi-config.test.mjs',
            'apps/desktop/src/ffmpeg-runtime.test.mjs',
        )
        record['unmodified_original_test_files'] = {n: expected[n]['sha256'] for n in original}
        run('unmodified-originals', ['--test', '--test-concurrency=1', '--test-reporter=tap', *original])
        run('unmodified-typescript-loudness', ['--experimental-strip-types', '--test', '--test-reporter=tap',
                                            'packages/openfilm/studio/ui/src/lib/loudness.test.ts'])
        seam = temp / 'closed-browser-seam'
        seam.mkdir()
        mapping = {
            'browser-pool.mjs': 'packages/openfilm/src/browser-pool.mjs',
            'browser-pool.test.mjs': 'packages/openfilm/src/browser-pool.test.mjs',
            'shared.mjs': 'packages/openfilm/src/shared.mjs',
            'film-doc.mjs': 'packages/openfilm/src/film-doc.mjs',
            'media-links.mjs': 'packages/openfilm/src/media-links.mjs',
            'rate.mjs': 'packages/openfilm/src/rate.mjs',
            'encoders.mjs': 'packages/openfilm/src/encoders.mjs',
            'nle.mjs': 'packages/openfilm/studio/server/nle.mjs',
            'original-seekable.mjs.txt': 'packages/openfilm/src/seekable.mjs',
        }
        for target, source in mapping.items():
            raw = (SOURCE / source).read_bytes()
            if target == 'nle.mjs':
                raw = raw.replace(b"'../../src/film-doc.mjs'", b"'./film-doc.mjs'").replace(b"'../../src/rate.mjs'", b"'./rate.mjs'")
            (seam / target).write_bytes(raw)
        stub = b"export class FilmPage {}\nexport class FrameError extends Error {}\nexport const launch=()=>{throw new Error('Actual browser launch disabled in research')};\nexport const serve=()=>{throw new Error('Actual server launch disabled in research')};\n"
        (seam / 'host.mjs').write_bytes(stub)
        (OUT / 'disabled-host.mjs.txt').write_bytes(stub)
        probe = Path(__file__).with_name('probe_openfilm_r16.mjs').read_bytes()
        (seam / 'probe.mjs').write_bytes(probe)
        (OUT / 'executed-probe.mjs.txt').write_bytes(probe)
        record['closed_browser_seam'] = {'original_modules': mapping, 'host_stub_sha256': sha(stub),
                                         'nle_import_paths_rebased': True, 'other_module_bodies_modified': False,
                                         'tests_modified': False}
        run('original-mock-browser-pool', ['--test', '--test-reporter=tap', 'browser-pool.test.mjs'], seam)
        record['observations'] = json.loads(run('source-observations', ['probe.mjs'], seam))
        summaries = [x['summary'] for x in record['calls'] if x['summary']]
        record['actual_upstream_test_totals'] = {key: sum(s.get(key, 0) for s in summaries)
                                                for key in ('tests', 'pass', 'fail', 'cancelled', 'skipped', 'todo')}
        verify_source()
        record['frozen_after'] = freeze()
        assert record['frozen_after'] == record['frozen_before']
        record.update(status='passed-scoped-upstream-research', finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      source_files_verified=len(expected), source_unchanged=True,
                      original_tests_are_not_product_regression=True,
                      native_media_encoding_executed=False, full_upstream_suite_executed=False)
    except BaseException as exc:
        record.update(status='failed-preserved', error=repr(exc), frozen_after=freeze())
        raise
    finally:
        save(OUT / 'verification.json', record)
        print(json.dumps({k: record.get(k) for k in ('status', 'actual_upstream_test_totals', 'error')}, ensure_ascii=False))


if __name__ == '__main__': main()
