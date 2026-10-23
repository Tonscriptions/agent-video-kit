"""Publish explicit standard float render only after actual 2623/528 gates."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import float_hsl_release_docs as docs
from run_frozen_regression import frozen, sha

ROOT, MAIN = docs.ROOT, docs.MAIN
REL = docs.REL
WORK = ROOT/'product/.runtime/float-hsl-20261022'
spec = importlib.util.spec_from_file_location('r105_bounded_git', MAIN/'scripts/native_index_release_tools.py')
helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
git = helper.git


def save(path, value):
    docs.write(path, json.dumps(value, ensure_ascii=False, indent=2))


def read(path):
    return json.loads(path.read_bytes())


def verify(base, entries):
    assert all(sha(base/name) == digest for name, digest in entries.items())


def source_gate(complete):
    current,native,media,installed=docs.current()
    foundation=read(ROOT/REL/'foundation-r1.json')
    parent=foundation['parent_frozen_inputs'];assert len(parent)==316
    assert not set(parent)-set(current) and len(current)==318
    changed={n for n in current if parent.get(n)!=current[n]};assert len(changed)==5
    review=read(ROOT/REL/'static-review-r1.json')
    assert review['status']=='passed-static-contact-and-GIF-clock-review'
    assert review['GIF_frames']==14 and review['viewed_panels']==6 and not review['continuous_playback_review']
    assert review['contact_sha256']==sha(ROOT/docs.ASSETS/'contact.png')
    assert review['GIF_sha256']==sha(ROOT/docs.ASSETS/'comparison.gif')
    verify(ROOT,foundation['dependency_artifact_inputs'])
    assert installed['status']=='passed-fresh-eight-wheel-190-resources-real-previews-and-528-methods'
    assert installed['frozen_before']==installed['frozen_after']==current
    assert installed['isolated_methods']['methods']==528 and installed['isolated_methods']['skipped']==0
    assert len(installed['resource_hashes'])==190 and len(installed['numpy_distribution']['files'])==931
    replay=read(ROOT/REL/'media-installed-r1/verification.json')
    assert replay['status']==media['status'] and replay['isolated']
    assert replay['frozen_before']==replay['frozen_after']==current
    assert media['actual_public_preview_CLI_processes']==replay['actual_public_preview_CLI_processes']==3
    for name in media['decoded']:
        for key in ['native_yuv10_sha256','PCM_sha256']:
            assert replay['decoded'][name][key]==media['decoded'][name][key]
    for key in ['Float32_sha256','PCM_sha256','PNG16_sha256']:
        assert replay['preview_decoded'][key]==media['preview_decoded'][key]
    for rel in [media,replay]:
        for name,row in rel['assets'].items():assert sha(ROOT/name)==row['sha256']
    owner_path=WORK/'complete-r1/run.json'
    owner=read(owner_path) if owner_path.exists() else None
    if owner:
        verify(ROOT,owner['frozen_inputs']);verify(ROOT,owner['verification_scripts'])
    audit={'status':'passed-source-and-installed-preflight-not-full-acceptance','frozen_inputs':current,
        'parent_frozen_inputs':parent,'changed_product_files':sorted(changed),'native_methods':328,
        'native_receipt_sha256':sha(ROOT/REL/'native-r2/verification.json'),
        'installed_receipt_sha256':sha(ROOT/REL/'installed-r1/verification.json'),
        'source_media_receipt_sha256':sha(ROOT/REL/'media-r2/verification.json'),
        'installed_status':installed['status'],'complete_terminal_checked':False,
        'startup_frozen_scripts':len(owner['verification_scripts']) if owner else 0}
    full=None
    if complete:
        assert owner['status']=='passed-complete-native-suite-not-published' and owner['methods']==2623
        full=read(ROOT/REL/'full-r1.json')
        assert owner['full_receipt_sha256']==sha(ROOT/REL/'full-r1.json')
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2623 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==current and full['external_fixture_count']==8
        assert full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        verify(ROOT,owner['dependency_artifact_inputs']);verify(ROOT,owner['bound_evidence'])
        lineage=read(ROOT/REL/'parent-binding-r1.json')
        assert lineage['status']=='passed-actual-published-parent316-full2579' and lineage['parent_inputs']==parent
        audit.update(status='passed-native-installed-complete-gates',complete_terminal_checked=True,
            published_parent=lineage['published_parent_commit'],full_receipt_sha256=sha(ROOT/REL/'full-r1.json'))
    return audit,full


def publication_files(audit):
    names = set(audit['changed_product_files']) | {docs.CONTRACT, docs.REPORT}
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts').glob('*.py'))
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/REL).rglob('*') if p.is_file() and (audit['complete_terminal_checked'] or not p.name.startswith('full-r1')))
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/assets').glob('float-hsl-20261022-*/**/*') if p.is_file())
    result = {}
    for name in sorted(names):
        path = ROOT/name
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink() and path.stat().st_size < 95*1024**2
        result[name] = sha(path)
    return result


def attributes(text, changed):
    return (text.rstrip()+'\n\n# V105 immutable original/failed/native media and source evidence.\n'+REL+'/** -text -whitespace\n'
            +'docs/assets/float-hsl-20261022-*/** -text -whitespace\n'
            +''.join(name+' -text whitespace=cr-at-eol\n' for name in sorted(changed)))


def preflight(work):
    audit, _ = source_gate(False)
    stage = work/'native-staging'; stage.mkdir()
    rows = publication_files(audit)
    all_files = {**rows, **audit['frozen_inputs']}
    git(stage, 'init', '--quiet', '--initial-branch=main')
    git(stage, 'config', 'core.longpaths', 'true')
    # The real release checks a delta against the unchanged parent. Mirror
    # that here: historical EOF blanks and intentional Markdown hard breaks
    # are not new changes, and must not be reformatted in frozen inputs.
    parent_root = ROOT.parent/'float-balance-lab-20261022'
    baseline = {}
    for name, digest in audit['parent_frozen_inputs'].items():
        source = parent_root/name; assert sha(source) == digest
        dest = stage/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest); baseline[name] = digest
    for name in docs.LATEST_DOCS:
        dest = stage/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(MAIN/name, dest); baseline[name] = sha(dest)
    docs.write(stage/'.gitattributes', attributes((MAIN/'.gitattributes').read_text('utf8'), audit['frozen_inputs']))
    baseline['.gitattributes'] = sha(stage/'.gitattributes')
    baseline_paths = work/'baseline-paths.nul'
    baseline_paths.write_bytes(b'\0'.join(n.encode('utf8') for n in sorted(baseline))+b'\0')
    git(stage, 'add', '--force', '--pathspec-from-file='+str(baseline_paths), '--pathspec-file-nul')
    helper.MAIN = stage
    helper.staged_rows(baseline)
    git(stage, '-c', 'user.name=Agent Video Kit Preflight', '-c', 'user.email=codex-preflight@localhost',
        'commit', '--quiet', '-m', 'private exact parent baseline for delta verification')
    baseline_commit = git(stage, 'rev-parse', 'HEAD').decode().strip()
    for name, digest in all_files.items():
        dest = stage/name; dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dest); assert sha(dest) == digest
    docs.documents(stage)
    docs.write(stage/'.gitattributes', attributes((MAIN/'.gitattributes').read_text('utf8'), audit['frozen_inputs']))
    for name in [*docs.LATEST_DOCS, docs.REPORT, docs.CONTRACT, '.gitattributes']:
        all_files[name] = sha(stage/name)
    pathspec = work/'staging-paths.nul'; pathspec.write_bytes(b'\0'.join(n.encode('utf8') for n in sorted(all_files))+b'\0')
    git(stage, 'add', '--force', '--pathspec-from-file='+str(pathspec), '--pathspec-file-nul')
    helper.MAIN = stage
    compared = helper.staged_rows(all_files)
    git(stage, 'diff', '--cached', '--check')
    links = docs.links(stage, [*docs.LATEST_DOCS, docs.REPORT, docs.CONTRACT])
    record = {'status': 'passed-private-native-staging-and-document-preflight', 'main_mutated': False,
        'private_work': str(work), 'native_git_longpaths': True,
        'private_parent_baseline_commit': baseline_commit, 'parent_product_blobs': 316,
        'frozen_files': 318, 'compared_blobs': len(compared), 'virtual_publication_links': len(links),
        'all_staged_bytes_equal_workspace': True, 'source_audit': audit, 'generator_sha256': sha(Path(__file__)), 'documentation_generator_sha256': sha(Path(docs.__file__))}
    save(ROOT/REL/'staging-preflight-r1.json', record)
    return record


def publish(work):
    state = {'status': 'checking', 'force_push': False, 'main_integrated': False,
             'started_at_utc': datetime.now(timezone.utc).isoformat()}
    def checkpoint(): save(work/'run.json', state)
    checkpoint()
    try:
        audit, full = source_gate(True); parent = audit['published_parent']; current = audit['frozen_inputs']
        preflight_record=read(ROOT/REL/'staging-preflight-r1.json')
        assert preflight_record['status']=='passed-private-native-staging-and-document-preflight'
        assert preflight_record['generator_sha256']==sha(Path(__file__))
        assert preflight_record['documentation_generator_sha256']==sha(Path(docs.__file__))
        state.update(source_audit=audit); checkpoint()
        assert git(MAIN, 'branch', '--show-current').decode().strip() == 'main'
        assert git(MAIN, 'rev-parse', 'HEAD').decode().strip() == parent
        assert git(MAIN, 'remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == parent
        assert not git(MAIN, 'status', '--porcelain', '-z'), 'Preserve unexpected main edits'
        spec = importlib.util.spec_from_file_location('r105_main_frozen', MAIN/'scripts/run_frozen_regression.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        assert module.frozen() == audit['parent_frozen_inputs']
        docs.write(ROOT/docs.REPORT,docs.report(full,published=True))
        reviewed = publication_files(audit); state['source_files'] = reviewed; checkpoint()
        tracked = {n.decode('utf8') for n in git(MAIN, 'ls-files', '-z').split(b'\0') if n}
        for name in reviewed:
            target = MAIN/name
            assert target.resolve().is_relative_to(MAIN) and not target.is_symlink()
            assert name in tracked or not target.exists(), 'Existing untracked destination '+name
        for name, digest in reviewed.items():
            target = MAIN/name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, target); assert sha(target) == digest
        state.update(status='copied-reviewed-source', main_integrated=True); checkpoint()
        assert module.frozen() == current
        docs.documents(MAIN, full, published=True)
        attr = MAIN/'.gitattributes'; docs.write(attr, attributes(attr.read_text('utf8'), audit['changed_product_files']))
        skill_receipt = REL+'/skills-release-r1.json'
        command = [sys.executable, '-E', '-B', '-X', 'utf8', str(MAIN/'scripts/audit_source_edit_skills.py'), '--expected-count', '17', '--output', str(MAIN/skill_receipt)]
        result = subprocess.run(command, cwd=MAIN, capture_output=True, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
        for name in ('stdout', 'stderr'):
            (work/('skills.'+name+'.log')).write_bytes(getattr(result, name))
        assert result.returncode == 0
        skills = read(MAIN/skill_receipt); mapping_path = MAIN/'video-cut-install-manifest.json'; mapping = read(mapping_path)
        mapping.setdefault('audit_history', []).append(mapping['current_audit'])
        for entry in mapping['skills']:
            row = next(v for v in skills['results'] if v['skill'] == entry['name'])
            assert entry['skill_md_sha256'] == row['sha256'][7:]
            assert Path(entry['canonical_directory']).resolve() == (MAIN/'skills'/entry['name']).resolve()
        mapping['current_audit'] = {'date': '2026-10-22', 'skill_count': 17, 'record': skill_receipt,
            'record_sha256': sha(MAIN/skill_receipt), 'local_links_checked': skills['local_links_checked'],
            'semantics': 'V105 continuous Float32 eight-band HSL and explicit input gamut policies in the common render/preview host; actual full2623/installed528, 190 resources; existing 17 skill bodies unchanged; default migration/all effects/HDR/natural quality and full CapCut parity unfinished'}
        save(mapping_path, mapping)
        link_rows = docs.links(MAIN, [*docs.LATEST_DOCS, docs.REPORT, docs.CONTRACT])
        release_receipt = REL+'/release-main-r1.json'
        save(MAIN/release_receipt, {'status': 'passed-complete-installed-main-and-17-skill-gates', 'base_commit': parent,
            'frozen_inputs': current, 'source_files': reviewed, 'full_methods': 2623, 'full_seconds': full['suite_seconds'],
            'installed_methods': 528, 'resources': 190, 'skills': 17, 'links_checked': len(link_rows),
            'full_sha256': sha(MAIN/REL/'full-r1.json'), 'standard_render_integrated': True, 'native_float_preview_integrated': True,
            'default_backend_migrated': False, 'full_capcut_parity': False, 'generator_sha256': sha(Path(__file__))})
        changed = {n.decode('utf8') for n in git(MAIN, 'diff', '--name-only', '-z').split(b'\0') if n}
        changed.update(n.decode('utf8') for n in git(MAIN, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if n)
        allowed = set(reviewed)|set(docs.LATEST_DOCS)|{'.gitattributes', 'video-cut-install-manifest.json', skill_receipt, release_receipt}
        assert changed <= allowed, sorted(changed-allowed)
        changed.update(reviewed)
        paths = work/'paths.nul'; paths.write_bytes(b'\0'.join(n.encode('utf8') for n in sorted(changed))+b'\0')
        git(MAIN, 'add', '--force', '--pathspec-from-file='+str(paths), '--pathspec-file-nul')
        git(MAIN, 'add', '--renormalize', '--pathspec-from-file='+str(paths), '--pathspec-file-nul')
        assert not git(MAIN, 'diff', '--name-only')
        helper.MAIN = MAIN
        compared = helper.staged_rows({**{n: sha(MAIN/n) for n in changed}, **current})
        git(MAIN, 'diff', '--cached', '--check')
        stage_receipt = REL+'/staged-release-r1.json'
        save(MAIN/stage_receipt, {'status': 'passed', 'frozen_files': 318, 'compared_blobs': len(compared),
            'files': compared, 'all_staged_bytes_equal_workspace': True, 'base_commit': parent, 'full_sha256': sha(MAIN/REL/'full-r1.json')})
        git(MAIN, 'add', '--', stage_receipt); helper.staged_rows({stage_receipt: sha(MAIN/stage_receipt)})
        assert module.frozen() == current and not git(MAIN, 'diff', '--name-only')
        git(MAIN, 'diff', '--cached', '--check')
        git(MAIN, 'commit', '--quiet', '-m', 'feat: add continuous Float32 eight-band HSL and explicit input gamut policies to shared render and preview host')
        commit = git(MAIN, 'rev-parse', 'HEAD').decode().strip()
        assert git(MAIN, 'rev-parse', 'HEAD^').decode().strip() == parent
        state.update(status='committed-awaiting-ordinary-push', commit=commit); checkpoint()
        git(MAIN, 'push', 'origin', 'main')
        remote = git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
        assert remote == commit and not git(MAIN, 'status', '--porcelain', '-z') and module.frozen() == current
        state.update(status='published', remote_main=remote, main_clean=True, full_methods=2623, installed_methods=528)
    except BaseException as exc:
        state.update(status='failed-preserved', error=repr(exc)); raise
    finally:
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat(); checkpoint()
        print(json.dumps({k: state.get(k) for k in ['status', 'commit', 'remote_main', 'error']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args(); work = args.work.resolve()
    assert work.is_relative_to(WORK) and not work.exists(); work.mkdir(parents=True)
    if args.preflight_only:
        result = preflight(work); print(json.dumps({k: result[k] for k in ['status', 'compared_blobs', 'virtual_publication_links']}))
    else:
        publish(work)
