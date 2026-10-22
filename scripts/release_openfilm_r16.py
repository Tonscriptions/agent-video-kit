"""Publish source research by ordinary push after the three existing release owners."""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
REL = Path('docs/validation/evidence/openfilm-reuse-20261022-r16')
REPORT = 'docs/OpenFilm_0.2.5可拆模块与复用成本评估_2026-10-22.md'
MARKER = '<!-- R16-OPENFILM-025-REUSE -->'
PARENT = MAIN / 'product/.runtime/float-render-lab-20261022'
OWNER = PARENT / 'product/.runtime/float-render-20261022/release-chain-r1/run.json'
WORK = ROOT / 'product/.runtime/openfilm-r16-release'
OLD_REPORTS = ('docs/OpenFilm可拆模块与现有内核降本清单_2026-10-21.md',
               'docs/OpenFilm新增提交与复用结论更新_2026-10-21.md')


def sha(path): return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    for attempt in range(8):
        try: return json.loads(Path(path).read_bytes())
        except (OSError, json.JSONDecodeError):
            if attempt == 7: raise
            time.sleep(.025)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    os.replace(temporary, path)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_gate():
    capture = read(ROOT / REL / 'capture-r2/verification.json')
    tests = read(ROOT / REL / 'tests-r1/verification.json')
    assert capture['status'] == 'passed-pinned-source-capture' and capture['fixed_head'] == 'af5756a88d362bdcd71dc870a0e02590420e6944'
    assert capture['source_files'] == 788 and capture['commits_since_r15'] == 3 and capture['files_since_r15'] == 70
    assert capture['license_unchanged_from_r14']
    assert tests['status'] == 'passed-scoped-upstream-research' and tests['source_unchanged']
    assert tests['actual_upstream_test_totals'] == {'tests': 46, 'pass': 45, 'fail': 0, 'cancelled': 0, 'skipped': 1, 'todo': 0}
    assert len(tests['observations']['observations']) == 7
    assert capture['frozen_before'] == capture['frozen_after'] == tests['frozen_before'] == tests['frozen_after']
    assert len(capture['frozen_before']) == 282
    archive = ROOT / 'sources/upstream/openfilm-025-20261022-r16/repo.zip'
    assert sha(archive) == capture['archive_sha256']
    names = {REPORT, 'sources/upstream/openfilm-025-20261022-r16/repo.zip'}
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'scripts').glob('*') if p.is_file())
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / REL).rglob('*') if p.is_file()
                 and p.name not in ('release-manifest-r2.json', 'readme-preview-r2.json', 'publication-r2.json'))
    rows = {}
    for name in sorted(names):
        path = ROOT / name
        assert not path.is_symlink() and path.resolve().is_relative_to(ROOT) and path.stat().st_size < 95 * 1024 ** 2
        rows[name] = sha(path)
    return rows


def documents(destination):
    destination = Path(destination)
    names = ['README.md', REPORT, *OLD_REPORTS, '.gitattributes']
    section = (ROOT / REL / 'readme-section.md.txt').read_text('utf8')
    text = (MAIN / 'README.md').read_text('utf8')
    assert MARKER not in text, 'Already has the R16 section; inspect existing publication instead'
    title, rest = text.split('\n', 1)
    generated = {REPORT: (ROOT / REPORT).read_text('utf8'), 'README.md': title + '\n\n' + section + '\n' + rest}
    attributes = (MAIN / '.gitattributes').read_text('utf8')
    assert '# R16 immutable upstream source research.' not in attributes
    generated['.gitattributes'] = attributes.rstrip() + '''

# R16 immutable upstream source research.
docs/validation/evidence/openfilm-reuse-20261022-r16/** -text -whitespace
sources/upstream/openfilm-025-20261022-r16/** -text -whitespace
scripts/*openfilm_r16* -text whitespace=cr-at-eol
docs/OpenFilm_0.2.5可拆模块与复用成本评估_2026-10-22.md text eol=lf
'''
    for name in OLD_REPORTS:
        text = (MAIN / name).read_text('utf8')
        title, rest = text.split('\n', 1)
        note = '\n\n> 本页保留 R14/R15 历史快照；2026-10-22 的 v0.2.5 新增模块、实跑和取舍见 [R16 最新复核](OpenFilm_0.2.5可拆模块与复用成本评估_2026-10-22.md)。\n'
        generated[name] = title + note + rest
    for name, text in generated.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf8', newline='\n')
    return names


def links(destination, names):
    destination = Path(destination).resolve()
    rows = []
    checked = {}
    for name in names:
        if not name.endswith('.md'): continue
        for value in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', (destination / name).read_text('utf8')):
            if value.startswith(('https:', 'http:', 'app:', 'codex:', '#')): continue
            relative = Path(os.path.abspath((destination / name).parent / unquote(value.split('#', 1)[0].strip('<>')))).relative_to(destination)
            key = relative.as_posix()
            if key not in checked:
                checked[key] = next((p for p in (destination / relative, ROOT / relative, MAIN / relative) if p.exists()), None)
            actual = checked[key]
            assert actual is not None, (name, value)
            rows.append({'document': name, 'target': relative.as_posix()})
    return rows


def stage_preflight(preview, names, source_rows):
    """Verify actual Git normalization and whitespace in a separate native repository."""
    scratch = WORK / 'native-staging-r2'
    scratch.mkdir(parents=True, exist_ok=False)
    expected = dict(source_rows)
    expected.update({name: sha(preview / name) for name in names})
    for name in expected:
        source = preview / name if name in names else ROOT / name
        target = scratch / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    calls = []
    def git(*args):
        command = ['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args]
        result = subprocess.run(command, cwd=scratch, capture_output=True, timeout=120)
        calls.append({'command': command, 'exit_code': result.returncode,
                      'stdout_sha256': 'sha256:' + hashlib.sha256(result.stdout).hexdigest(),
                      'stderr_sha256': 'sha256:' + hashlib.sha256(result.stderr).hexdigest()})
        assert result.returncode == 0, result.stderr.decode('utf8', errors='replace')[-1200:]
        return result.stdout
    git('init', '--quiet', '--initial-branch=main')
    git('config', 'core.autocrlf', 'false')
    git('add', '--', *sorted(expected))
    git('diff', '--cached', '--check')
    proc = subprocess.Popen(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', 'cat-file', '--batch'],
                            cwd=scratch, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    compared = []
    try:
        for name, digest in sorted(expected.items()):
            proc.stdin.write((':' + name + '\n').encode('utf8'))
            proc.stdin.flush()
            header = proc.stdout.readline().rstrip(b'\n').rsplit(b' ', 2)
            assert len(header) == 3 and header[1] == b'blob', (name, header)
            remaining = int(header[2])
            checksum = hashlib.sha256()
            while remaining:
                chunk = proc.stdout.read(min(65536, remaining))
                assert chunk, name
                remaining -= len(chunk)
                checksum.update(chunk)
            assert proc.stdout.read(1) == b'\n'
            assert 'sha256:' + checksum.hexdigest() == digest, ('Git changed original bytes', name)
            compared.append(name)
        proc.stdin.close()
        assert proc.wait(timeout=30) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
    save(ROOT / REL / 'staging-preflight-r2.json', {
        'status': 'passed-fresh-native-git-staging-bytes-and-whitespace',
        'files': expected, 'compared_blobs': len(compared), 'calls': calls,
        'branch': 'main', 'main_git_index_or_working_files_changed': False,
        'generator_sha256': sha(Path(__file__))})
    return len(compared)


def prepare():
    assert not (ROOT / REL / 'release-manifest-r2.json').exists()
    preview = WORK / 'readme-preview-r2'
    assert not preview.exists()
    names = documents(preview)
    references = links(preview, names)
    save(ROOT / REL / 'readme-preview-r2.json', {
        'status': 'passed-unpublished-four-document-numbered-README-and-byte-attributes-preview',
        'documents': {n: sha(preview / n) for n in names}, 'verified_local_links': len(references),
        'links': references, 'main_changed': False, 'published': False})
    compared = stage_preflight(preview, names, source_gate())
    rows = source_gate()
    rows[(REL / 'readme-preview-r2.json').as_posix()] = sha(ROOT / REL / 'readme-preview-r2.json')
    save(ROOT / REL / 'release-manifest-r2.json', {
        'status': 'ready-verified-research-awaiting-serialized-V95-publication',
        'files': rows, 'generator_sha256': sha(Path(__file__)),
        'actual_upstream_tests': {'passed': 45, 'skipped': 1, 'failed': 0},
        'new_product_features': 0, 'new_media': 0, 'force_push': False})
    print(json.dumps({'status': 'passed-research-and-document-preflight', 'files': len(rows),
                      'markdown_documents': len(names) - 1, 'attributes_files': 1, 'links': len(references),
                      'staged_blobs_compared': compared, 'main_changed': False}))


def publish():
    work = WORK / 'serialized-owner-r1'
    work.mkdir(parents=True, exist_ok=False)
    manifest_path = ROOT / REL / 'release-manifest-r2.json'
    manifest = read(manifest_path)
    fixed_manifest = sha(manifest_path)
    assert manifest['generator_sha256'] == sha(Path(__file__))
    state = {'status': 'waiting-for-actual-V95-release-and-clean-main', 'pid': os.getpid(),
             'started_at_utc': datetime.now(timezone.utc).isoformat(), 'force_push': False,
             'generator_sha256': sha(Path(__file__)), 'manifest_sha256': fixed_manifest,
             'published': False, 'main_changed': False}
    def checkpoint(): save(work / 'run.json', state)
    checkpoint()
    try:
        while True:
            parent = read(OWNER)
            if parent['status'] == 'published-V95-with-actual-full2320-and-installed203': break
            assert parent['status'] in ('waiting-for-actual-full2320-r1', 'publishing-reviewed-V95-host'), parent
            for lab, series, complete in (
                ('float-timeline-lab-20261022', 'float-timeline-20261022', 'complete-r2'),
                ('float-stream-lab-20261022', 'float-stream-20261022', 'complete-r1'),
                ('float-render-lab-20261022', 'float-render-20261022', 'complete-r1')):
                owner = read(MAIN / 'product/.runtime' / lab / 'product/.runtime' / series / complete / 'run.json')
                assert not owner['status'].startswith(('failed', 'aborted')), (lab, owner.get('error'))
            time.sleep(5)
        assert parent['commit'] == parent['remote_main'] and parent['main_integrated']
        expected_parent = parent['commit']
        full = read(MAIN / 'docs/validation/evidence/float-render-20261022-lab/full-r1.json')
        assert full['status'] == 'passed' and full['terminal_ok'] and full['methods'] == 2320 and full['skipped'] == 0
        assert len(full['frozen_after']) == 296 and full['frozen_before'] == full['frozen_after']
        product = load(MAIN / 'scripts/run_frozen_regression.py', 'r16_product_frozen')
        helper_path = MAIN / 'scripts/native_index_release_tools.py'
        helper = load(helper_path, 'r16_git_verifier')
        git = helper.git
        assert product.frozen() == full['frozen_after']
        assert git(MAIN, 'branch', '--show-current').decode().strip() == 'main'
        assert git(MAIN, 'rev-parse', 'HEAD').decode().strip() == expected_parent
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == expected_parent
        assert not git(MAIN, 'status', '--porcelain', '-z'), 'Preserve unexpected user or publisher changes'
        assert sha(manifest_path) == fixed_manifest
        for name, digest in manifest['files'].items(): assert sha(ROOT / name) == digest, name
        assert source_gate() == {k: v for k, v in manifest['files'].items()
                                 if k != (REL / 'readme-preview-r2.json').as_posix()}
        state.update(status='publishing-verified-R16-research', parent_commit=expected_parent,
                     helper_sha256=sha(helper_path), product_frozen_count=296)
        checkpoint()
        for name in (*manifest['files'], (REL / 'release-manifest-r2.json').as_posix()):
            assert not (MAIN / name).exists(), ('Unexpected existing new research file', name)
            (MAIN / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, MAIN / name)
        names = documents(MAIN)
        references = links(MAIN, names)
        assert product.frozen() == full['frozen_after']
        rows = {name: sha(MAIN / name) for name in (*manifest['files'], (REL / 'release-manifest-r2.json').as_posix(), *names)}
        git(MAIN, 'add', '--', *sorted(rows))
        compared = helper.staged_rows(rows)
        git(MAIN, 'diff', '--cached', '--check')
        assert not git(MAIN, 'diff', '--name-only')
        receipt_name = (REL / 'publication-r2.json').as_posix()
        save(MAIN / receipt_name, {'status': 'passed-staged-research-publication-audit',
             'parent_commit': expected_parent, 'upstream_head': 'af5756a88d362bdcd71dc870a0e02590420e6944',
             'actual_upstream_tests': manifest['actual_upstream_tests'], 'new_product_features': 0,
             'new_media': 0, 'force_push': False, 'verified_links': len(references),
             'product_inputs_unchanged': product.frozen() == full['frozen_after'], 'staged_blobs': compared})
        git(MAIN, 'add', '--', receipt_name)
        helper.staged_rows({receipt_name: sha(MAIN / receipt_name)})
        git(MAIN, 'diff', '--cached', '--check')
        assert product.frozen() == full['frozen_after']
        git(MAIN, 'commit', '--quiet', '-m', 'docs: review OpenFilm 0.2.5 reuse candidates and verified boundaries')
        commit = git(MAIN, 'rev-parse', 'HEAD').decode().strip()
        assert git(MAIN, 'rev-parse', 'HEAD^').decode().strip() == expected_parent
        state.update(status='committed-awaiting-ordinary-push', commit=commit, main_changed=True)
        checkpoint()
        git(MAIN, 'push', 'origin', 'main')
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
        assert not git(MAIN, 'status', '--porcelain', '-z')
        state.update(status='published-R16-research', published=True, remote_main=commit,
                     verified_links=len(references), compared_blobs=len(compared) + 1)
        checkpoint()
        progress = MAIN / 'product/.runtime/agent-video-kit-progress-20261021.json'
        old = progress.read_bytes()
        data = json.loads(old)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = progress.with_name('progress-before-R16-research-' + stamp + '.json')
        backup.write_bytes(old)
        data['main'].update(commit=commit, remote_main=commit, clean=True,
                            latest_documentation_update='V95 actual full2320/installed203; R16 OpenFilm v0.2.5 research45pass1skip, no new product feature')
        data.setdefault('openfilm_r16', {}).update(status=state['status'], commit=commit, remote_main=commit,
                            report=str(MAIN / REPORT), upstream_passed=45, upstream_skipped=1,
                            new_product_features=0, publication_record=str(work / 'run.json'))
        data.update(updated_at_utc=datetime.now(timezone.utc).isoformat(), previous_progress_snapshot=str(backup), goal_status='active')
        assert progress.read_bytes() == old, 'Concurrent progress update: preserve publication state and merge separately'
        save(progress, data)
    except BaseException as exc:
        state.update(status='failed-preserved', error=repr(exc))
        raise
    finally:
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        checkpoint()
        print(json.dumps({k: state.get(k) for k in ('status', 'commit', 'remote_main', 'error')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    prepare() if args.prepare else publish()
