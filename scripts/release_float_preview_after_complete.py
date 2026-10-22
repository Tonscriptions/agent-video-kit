"""Wait for actual complete2355, then ordinary-push the reviewed V97 result."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
WORK = ROOT/'product/.runtime/float-preview-20261022'
REL = ROOT/'docs/validation/evidence/float-preview-20261022-lab'


def read(path):
    for attempt in range(12):
        try:
            return json.loads(path.read_bytes())
        except (OSError, ValueError):
            if attempt == 11:
                raise
            time.sleep(.025)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def update_private(publication):
    path = MAIN/'product/.runtime/agent-video-kit-progress-20261021.json'
    previous = path.read_bytes(); data = json.loads(previous)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backups = WORK/'private-progress-backups'; backups.mkdir(exist_ok=True)
    (backups/(stamp+'.before-publication.json')).write_bytes(previous)
    data['main'].update(commit=publication['commit'], remote_main=publication['remote_main'], clean=True)
    data.setdefault('float_preview_lab', {}).update(status='published-V97-with-actual-full2355-and-installed260',
        main_integrated=True, published=True, commit=publication['commit'], remote_main=publication['remote_main'],
        full_suite_status='passed', full_suite_started=True, full_suite_passed=True, actual_full_methods=2355,
        installed_status='passed-fresh-eight-wheel-180-resources-real-previews-and-260-methods', installed_actual_methods=260,
        default_backend_migrated=False, full_capcut_parity=False)
    temporary = path.with_name('.'+path.name+'.r97-'+stamp+'.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    assert path.read_bytes() == previous, 'concurrent private progress edit preserved'
    os.replace(temporary, path)


def main():
    work = WORK/'release-chain-r1'
    assert not work.exists(); work.mkdir()
    state = {'status': 'waiting-for-actual-full2355-and-reviewed-preflight', 'pid': os.getpid(),
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'force_push': False, 'main_integrated': False}
    def checkpoint(): save(work/'run.json', state)
    checkpoint()
    try:
        preview = read(REL/'staging-preflight-r1.json')
        assert preview['status'] == 'passed-private-native-staging-and-document-preflight' and not preview['main_mutated']
        assert preview['generator_sha256'] == sha(ROOT/'scripts/publish_float_preview.py')
        while True:
            owner = read(WORK/'complete-r1/run.json')
            assert 'failed' not in owner['status'], owner.get('error')
            if owner['status'] == 'passed-complete-native-suite-not-published':
                break
            time.sleep(5)
        full = read(REL/'full-r1.json')
        assert full['status'] == 'passed' and full['terminal_ok'] and full['methods'] == 2355 and full['skipped'] == 0
        assert full['frozen_before'] == full['frozen_after'] == preview['source_audit']['frozen_inputs'] == frozen()
        state.update(status='publishing-reviewed-V97', full_receipt_sha256=sha(REL/'full-r1.json')); checkpoint()
        publication_work = WORK/'publication-r1'
        command = [sys.executable, '-E', '-B', '-X', 'utf8', str(ROOT/'scripts/publish_float_preview.py'), '--work', str(publication_work)]
        with (work/'publication.log').open('xb') as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        state['publisher_exit_code'] = result.returncode
        publication = read(publication_work/'run.json')
        assert result.returncode == 0 and publication['status'] == 'published'
        assert publication['commit'] == publication['remote_main'] and publication['main_clean'] and not publication['force_push']
        state.update(status='published-V97-with-actual-full2355-and-installed260', commit=publication['commit'],
                     remote_main=publication['remote_main'], main_integrated=True, full_methods=2355, installed_methods=260)
        try:
            update_private(publication)
        except BaseException as exc:
            state['private_progress_note'] = repr(exc)
    except BaseException as exc:
        state.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat(); checkpoint()
        print(json.dumps({k: state.get(k) for k in ['status', 'commit', 'remote_main', 'error']}), flush=True)


if __name__ == '__main__':
    main()
