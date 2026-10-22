"""Ordinary publish after the final native suite and private exact-byte review."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import float_delivery_bundle as bundle

ROOT, MAIN, REL, WORK = bundle.ROOT, bundle.MAIN, bundle.REL, bundle.WORK
sha, save = bundle.sha, bundle.save


def read(path):
    for attempt in range(12):
        try:
            return bundle.read(path)
        except (OSError, ValueError):
            if attempt == 11:
                raise
            time.sleep(.025)


def update_progress(publication):
    path = MAIN/'product/.runtime/agent-video-kit-progress-20261021.json'
    old = path.read_bytes()
    data = json.loads(old)
    backup = WORK/'release-chain-r1/private-progress-before.json'
    backup.write_bytes(old)
    full = read(MAIN/REL/'full-r1.json')
    skills = read(MAIN/REL/'skills-release-r1.json')
    commit = publication['commit']
    data['main'].update(version='V97', branch='main', commit=commit, product_commit=commit,
        remote_main=publication['remote_main'], clean=True, frozen_inputs=300, full_methods=2355,
        suite_seconds=full['suite_seconds'], skipped=0, skills=17, skill_links=skills['local_links_checked'],
        full_receipt=str(MAIN/REL/'full-r1.json'), publication_record=str(WORK/'publication-r1/run.json'),
        readme_and_numbered_actual_media_updated=True, verified_document_links=publication['verified_links'],
        staged_blob_comparisons=publication['compared_blobs'],
        latest_documentation_update='V94-V97 cumulative native Float32 render/preview/cache, actual final full2355 and installed260; intermediate full2320/2337 not executed; default migration/all effects/natural/HDR/full parity unfinished')
    for key in ('float_stream_lab', 'float_render_lab', 'float_standard_render_lab', 'float_preview_lab'):
        if key not in data:
            continue
        data[key].update(status='delivered-with-V97-final300-full2355', published=True,
            published_commit=commit, remote_main=publication['remote_main'], combined_delivery=True,
            final_snapshot_inputs=300, final_full_methods=2355, final_full_receipt=str(MAIN/REL/'full-r1.json'),
            public_main_readme_updated=True, publication_record=str(WORK/'publication-r1/run.json'),
            historical_first_owner_status='failed-preserved-before-suite', standalone_publication=False)
    data.setdefault('float_delivery_bundle', {}).update(status='published-V97-cumulative-full2355-installed260',
        root=str(ROOT), commit=commit, remote_main=publication['remote_main'], frozen_inputs=300,
        full_methods=2355, full_seconds=full['suite_seconds'], full_suite_passed=True, installed_methods=260,
        installed_resources=180, intermediate_full_suites_claimed_passed=False, default_backend_migrated=False,
        full_capcut_parity=False, report=str(MAIN/bundle.REPORT), publication_record=str(WORK/'publication-r1/run.json'))
    data.update(updated_at_utc=datetime.now(timezone.utc).isoformat(), goal_status='active',
        previous_progress_snapshot=str(backup), current_goal_turn_classification='progress: cumulative native Float32 CLI render/preview/cache with actual final full2355/installed260 ordinarily published; all remaining full-product requirements stay active')
    assert path.read_bytes() == old, 'Concurrent private progress change preserved'
    temporary = path.with_name('progress-delivery-V97-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.tmp')
    save(temporary, data)
    os.replace(temporary, path)


def main():
    work = WORK/'release-chain-r1'
    assert not work.exists()
    work.mkdir(parents=True)
    state = {'status': 'waiting-for-actual-final2355-and-reviewed-preflight', 'pid': os.getpid(),
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'force_push': False, 'main_integrated': False}

    def checkpoint():
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(work/'run.json', state)

    checkpoint()
    try:
        preflight = read(ROOT/REL/'staging-preflight-r1.json')
        assert preflight['status'] == 'passed-private-cumulative-staging-and-document-preflight' and not preflight['main_mutated']
        publisher = ROOT/'scripts/publish_float_delivery.py'
        assert preflight['generator_sha256'] == sha(publisher)
        assert preflight['documentation_generator_sha256'] == sha(ROOT/'scripts/float_delivery_docs.py')
        owner_path = WORK/'complete-r1/run.json'
        while True:
            owner = read(owner_path)
            if owner['status'] == 'passed-complete-native-suite-not-published':
                break
            assert owner['status'] in ('checking-final-source-bundle',
                'waiting-for-actual-V94-full2299-before-final300-suite', 'running-complete-native-suite'), owner.get('error', owner['status'])
            time.sleep(5)
        full = read(ROOT/REL/'full-r1.json')
        assert owner['methods'] == full['methods'] == 2355 and full['terminal_ok'] and full['skipped'] == 0
        assert owner['full_receipt_sha256'] == sha(ROOT/REL/'full-r1.json')
        assert full['frozen_before'] == full['frozen_after'] == preflight['source_audit']['frozen_inputs']
        state.update(status='publishing-reviewed-cumulative-V97', full_receipt_sha256=sha(ROOT/REL/'full-r1.json'))
        checkpoint()
        publication_work = WORK/'publication-r1'
        command = [sys.executable, '-E', '-B', '-X', 'utf8', str(publisher), '--work', str(publication_work)]
        with (work/'publish.log').open('xb') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
        publication = read(publication_work/'run.json')
        assert result.returncode == 0 and publication['status'] == 'published', publication.get('error')
        assert publication['commit'] == publication['remote_main'] and publication['main_clean'] and not publication['force_push']
        state.update(status='published-V97-cumulative-full2355-installed260', main_integrated=True,
            commit=publication['commit'], remote_main=publication['remote_main'])
        checkpoint()
        try:
            update_progress(publication)
        except Exception as exc:
            state['private_progress_update_error'] = repr(exc)
    except BaseException as exc:
        state.update(status='failed-preserved', error=repr(exc))
        raise
    finally:
        checkpoint()
        print(json.dumps({k:state.get(k) for k in ('status','commit','remote_main','error')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
