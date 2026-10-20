"""Resume only the reviewed R14 publication stopped by Git text normalization."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path('E:/dev/sandbox/AI广告剪辑')
REL = 'docs/validation/evidence/openfilm-reuse-20261021-r14/run-r1'
BASE = 'd1ae0967628405126517c1fd840fbc5104e1d786'
REMOTE = 'git@github.com:Tonscriptions/agent-video-kit.git'
RULES = ('\n# R14 preserves raw upstream responses and native execution evidence.\n'
         'docs/validation/evidence/openfilm-reuse-20261021-r14/** -text -whitespace\n'
         'scripts/*openfilm_r14*.py -text\n')


def sha_bytes(value):
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes())


def read(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf8', newline='\n')


def git(*args):
    return subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args],
                          cwd=ROOT, capture_output=True, check=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    assert work.is_relative_to(ROOT / 'product/.runtime') and not work.exists()
    work.mkdir(parents=True)
    state = {'status': 'preflight', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
             'script_sha256': sha(Path(__file__)), 'force_push': False, 'calls': []}
    try:
        old_proof = read(ROOT / REL / 'publication-audit-r1.json')
        expected = dict(old_proof['reviewed_files'])
        expected[REL + '/publication-audit-r1.json'] = sha(ROOT / REL / 'publication-audit-r1.json')
        staged = {p.decode('utf8') for p in git('diff', '--cached', '--name-only', '-z').split(b'\0') if p}
        assert staged == set(expected), 'Refuse unrelated staged changes'
        assert not git('diff', '--name-only'), 'Refuse unstaged tracked changes'
        assert git('rev-parse', 'HEAD').decode().strip() == BASE
        assert git('branch', '--show-current').decode().strip() == 'main'
        assert git('remote', 'get-url', 'origin').decode().strip() == REMOTE
        assert git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == BASE
        for name, digest in expected.items():
            assert sha(ROOT / name) == digest, name
        mismatches = [n for n, h in expected.items() if sha_bytes(git('show', ':' + n)) != h]
        assert set(mismatches) == {REL + '/' + n for n in
                                  ('node-version.stdout.txt', 'source-tree.json', 'verification.json')}
        spec = importlib.util.spec_from_file_location('frozen_r14_recovery', ROOT / 'scripts/run_frozen_regression.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        before = module.frozen()
        assert before == read(ROOT / REL / 'verification.json')['frozen_after'] and len(before) == 237
        state.update(base_commit=BASE, original_staged_count=len(staged),
                     normalization_mismatches=mismatches, frozen_before=before)
        save(work / 'run.json', state)

        amendments = {}
        for iteration in (1, 2):
            original = ROOT / 'product/.runtime/openfilm-r14-review' / f'publication-r{iteration}/run.json'
            failed = read(original)
            assert failed['status'] == 'failed'
            target = ROOT / REL / f'publication-failure-r{iteration}.json'
            assert not target.exists()
            target.write_bytes(original.read_bytes())
            amendments[target.relative_to(ROOT).as_posix()] = sha(target)
        publisher = ROOT / 'scripts/publish_openfilm_r14.py'
        executed = ROOT / REL / 'executed-publisher-r2.py.txt'
        assert not executed.exists()
        executed.write_bytes(publisher.read_bytes())
        amendments[executed.relative_to(ROOT).as_posix()] = sha(executed)
        old_attributes = sha(ROOT / '.gitattributes')
        with (ROOT / '.gitattributes').open('a', encoding='utf8', newline='\n') as handle:
            handle.write(RULES)
        amendments['.gitattributes'] = sha(ROOT / '.gitattributes')
        text = publisher.read_text(encoding='utf8')
        needle = "        proof = REL + '/publication-audit-r1.json'\n"
        assert text.count(needle) == 1
        fix = ("        attributes = MAIN / '.gitattributes'\n"
               "        rule = 'docs/validation/evidence/openfilm-reuse-20261021-r14/** -text -whitespace'\n"
               "        if rule not in attributes.read_text(encoding='utf8').splitlines():\n"
               "            with attributes.open('a', encoding='utf8', newline='\\n') as handle:\n"
               "                handle.write('\\n# Preserve raw R14 evidence.\\n' + rule + '\\n')\n"
               "        changed['.gitattributes'] = sha(attributes)\n")
        text = text.replace(needle, fix + needle)
        ast.parse(text)
        publisher.write_text(text, encoding='utf8', newline='\n')
        amendments['scripts/publish_openfilm_r14.py'] = sha(publisher)
        execution = ROOT / REL / 'executed-publication-recovery.py.txt'
        assert not execution.exists()
        execution.write_bytes(Path(__file__).read_bytes())
        amendments[execution.relative_to(ROOT).as_posix()] = sha(execution)
        amendments['scripts/recover_openfilm_r14.py'] = sha(Path(__file__))
        final = {**expected, **amendments}
        assert before == module.frozen()
        proof = ROOT / REL / 'publication-audit-r2.json'
        assert not proof.exists()
        save(proof, {'status': 'passed-review-before-commit', 'base_commit': BASE,
                     'previous_audit_preserved': REL + '/publication-audit-r1.json',
                     'failure': 'Git normalized three raw evidence files; no commit or push occurred',
                     'original_raw_bytes_unchanged': True, 'mismatched_staged_files': mismatches,
                     'attributes_before_sha256': old_attributes,
                     'reviewed_files': final, 'product_input_count': len(before),
                     'product_frozen_equal': True, 'research_tests_passed': 32,
                     'research_tests_skipped': 1, 'observations': 12,
                     'product_regression_rerun': False, 'ordinary_main_push_required': True})
        final[proof.relative_to(ROOT).as_posix()] = sha(proof)
        git('add', '--', *sorted(final))
        staged = {p.decode('utf8') for p in git('diff', '--cached', '--name-only', '-z').split(b'\0') if p}
        assert staged == set(final)
        for name, digest in final.items():
            assert sha(ROOT / name) == digest and sha_bytes(git('show', ':' + name)) == digest, name
        git('diff', '--cached', '--check')
        assert before == module.frozen()
        state.update(status='verified-staged-bytes', staged_files=final)
        save(work / 'run.json', state)
        git('commit', '-m', 'docs: review reusable OpenFilm modules and integration costs')
        commit = git('rev-parse', 'HEAD').decode().strip()
        assert git('rev-parse', 'HEAD^').decode().strip() == BASE
        assert not git('diff', BASE, '--name-only', '--', 'product', 'skills')
        state.update(status='committed-awaiting-ordinary-push', commit=commit)
        save(work / 'run.json', state)
        git('push', 'origin', 'main')
        remote = git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
        assert remote == commit and before == module.frozen()
        assert not git('status', '--porcelain', '--untracked-files=no')
        state.update(status='published', remote_main=remote, product_frozen_equal=True,
                     staged_byte_checks=len(final), product_input_count=len(before))
    except BaseException as error:
        state.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(work / 'run.json', state)
        print(json.dumps({k: state.get(k) for k in ('status', 'commit', 'remote_main', 'error')},
                         ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
