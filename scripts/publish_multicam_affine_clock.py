"""Publish affine clock and float PCM only after the actual complete2084 receipt."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from native_index_release_tools import MAIN,sha,git,staged_rows
from run_frozen_regression import frozen
from multicam_affine_release_docs import (ROOT,REL,ASSETS,REPORT,CONTRACT,HISTORICAL_REPORT,HISTORICAL_CONTRACT,
    MARKER,SKILLS,LATEST_DOCS,documents,write)
MODIFIED={'product/src/ai_ad_editor/'+name+'.py' for name in ('cli','multicam','capabilities','render')}
ADDED={'product/src/ai_ad_editor/multicam_clock.py','product/tests/test_multicam_affine_clock.py','product/tests/test_audio_resample_precision.py'}
SCRIPTS=('run_multicam_affine_after_parent','run_frozen_regression','run_with_regression_fixtures',
 'materialize_regression_fixtures','prepare_multicam_affine_lab','smoke_multicam_affine_clock',
 'run_multicam_affine_related','run_audio_precision_regression','diagnose_multicam_affine_pcm',
 'prepare_multicam_affine_install','verify_multicam_affine_install','complete_multicam_affine_install',
 'finalize_multicam_affine_media','prepare_multicam_affine_skills','native_index_release_tools',
 'multicam_affine_release_docs','prepare_multicam_affine_publication','publish_multicam_affine_clock',
 'preview_multicam_affine_publication')

def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):write(path,json.dumps(value,ensure_ascii=False,indent=2))
def verify(root,values):
    for name,digest in values.items():assert sha(root/name)==digest,name

def source_audit():
    current=frozen();base=ROOT/REL;audit=read(base/'audit-r1.json')
    assert audit['status']=='passed-source-and-evidence-preflight' and current==audit['frozen_inputs'] and len(current)==263
    assert len(audit['verification_scripts'])==14 and len(audit['fixture_inputs'])==8 and len(audit['dependency_artifact_inputs'])==9
    verify(ROOT/'scripts',audit['verification_scripts']);verify(ROOT,audit['fixture_inputs']);verify(ROOT,audit['dependency_artifact_inputs'])
    verify(base,audit['bound_evidence'])
    assert set(current)-set(audit['published_parent_inputs'])==ADDED
    assert {name for name in audit['published_parent_inputs'] if current[name]!=audit['published_parent_inputs'][name]}==MODIFIED
    for name,digest in audit['documents'].items():
        assert sha(base/'before-full-documents-r1'/Path(name).name)==digest
    media=read(base/'media-manifest-r1.json')
    assert media['status']=='passed-media-inventory' and media['asset_count']==33 and media['GIF_count']==9
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    related=read(base/'related-r3.json')
    assert related['status']=='passed-related-regressions' and related['methods']==related['distinct_methods']==157 and related['skipped']==0
    assert related['frozen_before']==related['frozen_after']==current
    assert sha(base/'related-r3.log')==related['log_sha256']
    isolated=read(base/'installed-postflight-r3/verification.json')
    assert isolated['status']=='passed-isolated-postflight' and isolated['isolated_methods']==41 and isolated['isolated_skipped']==0
    assert isolated['frozen_before']==isolated['frozen_after']==current
    for name in ('native-r3/verification.json','installed-r1/media/verification.json'):
        item=read(base/name);assert item['status']=='passed' and len(item['checks'])==52 and all(row['ok'] for row in item['checks'])
        assert item['frozen_before']==item['frozen_after']==current
    drafts=read(base/'skills-draft-r1.json')
    assert drafts['status']=='passed-four-unregistered-drafts' and drafts['canonical_skill_count']==17 and not drafts['registered']
    for name,row in drafts['skills'].items():
        assert sha(ROOT/row['path'])==row['sha256'] and row['validator_exit_code']==0
        assert sha(MAIN/'skills'/name/'SKILL.md')==row['parent_sha256']
    return current

def source_files():
    names=MODIFIED|ADDED|{HISTORICAL_REPORT,HISTORICAL_CONTRACT}
    names|={'scripts/'+name+'.py' for name in SCRIPTS}
    names.add('scripts/multicam_affine_publication_prefix.py.txt')
    state=read(ROOT/'product/.runtime/multicam-affine-clock-20261021/full-after-media-r1/run.json')
    for prefix in (REL,ASSETS):
        for path in (ROOT/prefix).rglob('*'):
            if not path.is_file():continue
            name=path.relative_to(ROOT).as_posix()
            if state['status']=='running-complete-native-suite' and name.startswith(REL+'/full-'):continue
            names.add(name)
    for name in names:
        path=ROOT/name;assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT),name
        assert path.stat().st_size<100000000,name
    return {name:sha(ROOT/name) for name in sorted(names)}

def complete_gate(current):
    base=ROOT/REL;audit=read(base/'audit-r1.json')
    state=read(ROOT/'product/.runtime/multicam-affine-clock-20261021/full-after-media-r1/run.json')
    assert state['status']=='passed-complete-suite-awaiting-reviewed-integration' and state['methods']==2084
    full=read(base/'full-r1.json')
    assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2084 and full['skipped']==0
    assert full['frozen_before']==full['frozen_after']==current
    assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged']
    assert full['verification_scripts_equal'] and state['full_sha256']==sha(base/'full-r1.json')
    extra=read(base/'full-dependencies-r1.json');assert extra['status']=='passed-extra-frozen-inputs'
    assert extra['scripts']==audit['verification_scripts'] and extra['fixtures']==audit['fixture_inputs']
    assert extra['dependencies']==audit['dependency_artifact_inputs'] and extra['full_sha256']==sha(base/'full-r1.json')
    verify(ROOT/'scripts',audit['verification_scripts']);verify(ROOT,audit['fixture_inputs']);verify(ROOT,audit['dependency_artifact_inputs'])
    assert read(base/'audit-r1.json')==audit
    return full,{'published_commit':audit['main_documentation_commit'],'upstream_inputs':audit['published_parent_inputs']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    work = args.work.resolve()
    assert work.is_relative_to(ROOT / 'product/.runtime') and (not work.exists())
    work.mkdir(parents=True)
    state = {'status': 'checking-source', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'calls': [], 'force_push': False}

    def checkpoint():
        save(work / 'run.json', state)
    try:
        current = source_audit()
        reviewed = source_files()
        state.update(status='passed-source-preflight-awaiting-full', frozen_inputs=current, source_files=reviewed)
        checkpoint()
        if args.preflight_only:
            return
        full, alignment = complete_gate(current)
        base = alignment['published_commit']
        assert git(MAIN, 'branch', '--show-current').decode().strip() == 'main'
        assert git(MAIN, 'rev-parse', 'HEAD').decode().strip() == base
        assert git(MAIN, 'remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == base
        assert not git(MAIN, 'status', '--porcelain', '-z'), 'Preserve unexpected main changes; no implicit integration'
        spec = importlib.util.spec_from_file_location('nested_native_main_freeze', MAIN / 'scripts/run_frozen_regression.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.frozen() == alignment['upstream_inputs']
        tracked = {p.decode('utf8') for p in git(MAIN, 'ls-files', '-z').split(b'\x00') if p}
        generated = {REPORT, CONTRACT, REL + '/skills-release-r1.json', REL + '/release-main-r1.json', REL + '/publication-copy-r1.json', REL + '/staged-release-r1.json'}
        for name in set(reviewed) | generated:
            path = MAIN / name
            assert path.resolve().is_relative_to(MAIN) and (not path.is_symlink())
            assert name in tracked or not path.exists(), 'Existing untracked destination: ' + name
        assert source_files() == reviewed and frozen() == current
        state.update(status='copying-reviewed-source', base_commit=base)
        checkpoint()
        for name, digest in reviewed.items():
            target = MAIN / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
            assert sha(target) == digest, name
        assert module.frozen() == current
        modified_docs = documents(MAIN, full)
        command = [sys.executable, '-E', '-B', '-X', 'utf8', str(MAIN / 'scripts/audit_source_edit_skills.py'), '--expected-count', '17', '--output', str(MAIN / REL / 'skills-release-r1.json')]
        result = subprocess.run(command, cwd=MAIN, capture_output=True, timeout=600)
        (work / 'main-skills.stdout.log').write_bytes(result.stdout)
        (work / 'main-skills.stderr.log').write_bytes(result.stderr)
        state['calls'].append({'command': command, 'exit_code': result.returncode})
        checkpoint()
        assert result.returncode == 0
        skills = read(MAIN / REL / 'skills-release-r1.json')
        mapping_path = MAIN / 'video-cut-install-manifest.json'
        mapping = read(mapping_path)
        mapping.setdefault('audit_history', []).append(mapping['current_audit'])
        for entry in mapping['skills']:
            row = next((item for item in skills['results'] if item['skill'] == entry['name']))
            old, new = (entry['skill_md_sha256'], row['sha256'][7:])
            if old != new:
                entry.setdefault('skill_md_sha256_history', []).append(old)
                entry['previous_manifest_skill_md_sha256'] = old
            entry.update(skill_md_sha256=new, validation=row['validator_stdout'], prefix_verified=True, registration_verified=True)
            assert Path(entry['canonical_directory']).resolve() == (MAIN / 'skills' / entry['name']).resolve()
        mapping['current_audit'] = {'date': '2026-10-21', 'skill_count': 17, 'local_links_checked': skills['local_links_checked'], 'record': REL + '/skills-release-r1.json', 'record_sha256': sha(MAIN / REL / 'skills-release-r1.json'), 'previous_hashes_preserved': True, 'semantics': 'V90 explicit affine device clock with bounded observed intervals, preserved calibration rates and float PCM; native/isolated controls and actual2084 complete suite; no full CapCut parity acceptance'}
        save(mapping_path, mapping)
        links = []
        for name in sorted(modified_docs - {'.gitattributes'}):
            path = MAIN / name
            text = path.read_text('utf8')
            if name in LATEST_DOCS or name.startswith('skills/'):
                text = text.split('<!-- ' + MARKER + ' -->')[1].split('<!-- /' + MARKER + ' -->')[0]
            for token in re.findall('!?\\[[^\\]]*\\]\\(([^)\\n]+)\\)', text):
                target = token.strip('<>').split('#', 1)[0]
                if not target or re.match('^[a-zA-Z][\\w+.-]*:', target):
                    continue
                resolved = (path.parent / target).resolve()
                assert resolved.is_relative_to(MAIN) and resolved.exists(), (name, token)
                links.append({'document': name, 'target': resolved.relative_to(MAIN).as_posix()})
        for name, digest in current.items():
            assert sha(MAIN / name) == digest
        for name, row in full['external_fixtures_expected'].items():
            assert sha(MAIN / name) == row['sha256']
        save(MAIN / REL / 'release-main-r1.json', {'status': 'passed-main-byte-and-document-audit', 'base_commit': base, 'frozen_inputs': current, 'full_methods': 2084, 'full_skipped': 0, 'full_sha256': sha(MAIN / REL / 'full-r1.json'), 'targeted_methods': 157, 'resources': 162, 'skills': 17, 'local_links': links, 'documents': {name: sha(MAIN / name) for name in sorted(modified_docs)}, 'generator_sha256': sha(Path(__file__))})
        save(MAIN / REL / 'publication-copy-r1.json', {'status': 'passed-reviewed-copy', 'source': str(ROOT), 'copied_files': reviewed, 'frozen_inputs': current, 'base_commit': base})
        changed = {p.decode('utf8') for p in git(MAIN, 'diff', '--name-only', '-z').split(b'\x00') if p}
        changed.update((p.decode('utf8') for p in git(MAIN, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\x00') if p))
        allowed = set(reviewed) | modified_docs | generated | {'video-cut-install-manifest.json'}
        assert changed <= allowed, sorted(changed - allowed)
        stage = work / 'stage-paths.nul'
        stage.write_bytes(b'\x00'.join((name.encode('utf8') for name in sorted(changed))) + b'\x00')
        git(MAIN, 'add', '--pathspec-from-file=' + str(stage), '--pathspec-file-nul')
        git(MAIN, 'add', '--renormalize', '--pathspec-from-file=' + str(stage), '--pathspec-file-nul')
        assert not git(MAIN, 'diff', '--name-only')
        assert {p.decode('utf8') for p in git(MAIN, 'diff', '--cached', '--name-only', '-z').split(b'\x00') if p} == changed
        git(MAIN, 'diff', '--cached', '--check')
        rows = staged_rows({**{name: sha(MAIN / name) for name in changed}, **current})
        receipt = REL + '/staged-release-r1.json'
        save(MAIN / receipt, {'status': 'passed', 'frozen_files': 263, 'compared_blobs': len(rows), 'files': rows, 'all_staged_bytes_equal_workspace': True, 'all_frozen_bytes_equal_staged': True, 'stream_buffer_bytes': 65536, 'full_sha256': sha(MAIN / REL / 'full-r1.json'), 'base_commit': base})
        git(MAIN, 'add', '--', receipt)
        staged_rows({receipt: sha(MAIN / receipt)})
        assert module.frozen() == current and (not git(MAIN, 'diff', '--name-only'))
        git(MAIN, 'diff', '--cached', '--check')
        state.update(status='passed-staged-audit')
        checkpoint()
        git(MAIN, 'commit', '--quiet', '-m', 'feat: calibrate local camera clocks and preserve float resampling precision')
        commit = git(MAIN, 'rev-parse', 'HEAD').decode().strip()
        assert git(MAIN, 'rev-parse', 'HEAD^').decode().strip() == base
        state.update(status='committed-awaiting-ordinary-push', commit=commit)
        checkpoint()
        git(MAIN, 'push', 'origin', 'main')
        remote = git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
        assert remote == commit and (not git(MAIN, 'status', '--porcelain', '-z')) and (module.frozen() == current)
        state.update(status='published', remote_main=remote, main_clean=True, full_methods=2084)
    except BaseException as caught:
        state.update(status='failed', error={'type': type(caught).__name__, 'message': str(caught)})
        raise
    finally:
        checkpoint()
        print(json.dumps({k: state.get(k) for k in ('status', 'commit', 'remote_main', 'error')}, ensure_ascii=False), flush=True)

if __name__=='__main__':main()
