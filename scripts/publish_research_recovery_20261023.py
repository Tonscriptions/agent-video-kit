"""Publish unchanged R17 research against the actual, passed V102 baseline."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
REL = Path('docs/validation/evidence/openfilm-reuse-20261022-r17')
WORK = ROOT/'product/.runtime/openfilm-r17-release/recovery-publication-r2'
BASELINE = '4178593b1e43b9cac25e5a4fac8569e8f538f3bc'
SELF = 'scripts/publish_research_recovery_20261023.py'


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    WORK.mkdir(parents=True, exist_ok=False)
    old = module(ROOT/'scripts/publish_openfilm_r17.py', 'r17_frozen_publisher')
    sha, read, save, git = old.sha, old.read, old.save, old.git
    state = dict(status='checking-actual-V102-for-research-only-publication', pid=os.getpid(),
                 started_at_utc=datetime.now(timezone.utc).isoformat(), main_mutated=False,
                 force_push=False, published=False, generator_sha256=sha(Path(__file__)))

    def checkpoint():
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(WORK/'run.json', state)

    checkpoint()
    try:
        previous_path = ROOT/'product/.runtime/openfilm-r17-release/publication-owner-r1/run.json'
        previous = read(previous_path)
        assert previous['status'] == 'failed-preserved' and not previous['main_mutated'] and not previous['published']
        manifest = read(ROOT/REL/'release-manifest-r1.json')
        rows = old.source_rows()
        assert rows == manifest['files']
        product = module(MAIN/'scripts/run_frozen_regression.py', 'r17_actual_product')
        inputs = product.frozen()
        full_path = MAIN/'docs/validation/evidence/float-curves-20261022-lab/full-r1.json'
        full = read(full_path)
        assert full['terminal_ok'] and full['methods'] == 2495 and full['skipped'] == 0
        assert len(inputs) == 311 and inputs == full['frozen_before'] == full['frozen_after']
        assert git(MAIN, 'branch', '--show-current').decode().strip() == 'main'
        assert git(MAIN, 'remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN, 'rev-parse', 'HEAD').decode().strip() == BASELINE
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == BASELINE
        assert not git(MAIN, 'status', '--porcelain', '-z')
        recovery = REL/'publication-recovery-r2'
        directory = ROOT/recovery
        directory.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(previous_path, directory/'previous-owner-failed.json')
        save(directory/'basis.json', dict(
            status='reviewed-research-only-recovery-on-actual-V102',
            at_utc=datetime.now(timezone.utc).isoformat(), parent_commit=BASELINE,
            reason='The V103 full regression failed; dependent full suites did not run. R17 has no product changes and does not require those unpublished candidates.',
            prior_owner_status=previous['status'], prior_owner_main_mutated=False,
            original_research_inputs=311, publication_inputs=inputs,
            existing_complete_regression={'receipt':full_path.relative_to(MAIN).as_posix(),
                'sha256':sha(full_path), 'methods':2495, 'skipped':0, 'rerun_here':False},
            upstream_tests={'passed':5, 'failed':1, 'skipped':0},
            mock_worker_cases=20, native_CommonJS_cases=2,
            new_product_code=0, new_product_test_executions=0, new_media=0,
            pending_functional_candidates_published=False, full_capcut_parity=False,
            prior_failures_rewritten=False, force_push=False))
        rows.update({SELF:sha(Path(__file__))})
        for path in directory.iterdir():
            rows[path.relative_to(ROOT).as_posix()] = sha(path)
        for name in ('release-manifest-r1.json', 'staging-preflight-r1.json'):
            path = ROOT/REL/name
            rows[path.relative_to(ROOT).as_posix()] = sha(path)
        original_documents = old.documents

        def documents(destination):
            names = original_documents(destination)
            for name in ('README.md', 'docs/README.md'):
                path = destination/name
                text = path.read_text('utf8')
                note = ('\n本次为基于已发布 V102 的独立研究更新，产品 311 输入保持不变；'
                        'V103 的 2,537 项完整回归出现 1 失败、1 错误，后续候选未发布。'
                        '旧等待发布流程的失败已保留，不计为本轮产品功能通过。'
                        + ('[发布恢复依据](docs/validation/evidence/openfilm-reuse-20261022-r17/publication-recovery-r2/basis.json)。\n'
                           if name == 'README.md' else '[发布恢复依据](validation/evidence/openfilm-reuse-20261022-r17/publication-recovery-r2/basis.json)。\n'))
                text = text.replace('<!-- /'+old.MARKER+' -->', note+'\n<!-- /'+old.MARKER+' -->', 1)
                path.write_text(text, encoding='utf8', newline='\n')
            path = destination/'.gitattributes'
            path.write_text(path.read_text('utf8')+'\n'+SELF+' -text whitespace=cr-at-eol\n', encoding='utf8', newline='\n')
            return names

        old.documents = documents
        state['status'] = 'reviewing-fresh-native-stage-on-V102'; checkpoint()
        preview, names, fresh = old.preflight(WORK/'fresh-preflight', rows)
        save(WORK/'fresh-preflight.json', fresh)
        assert git(MAIN, 'rev-parse', 'HEAD').decode().strip() == BASELINE
        assert not git(MAIN, 'status', '--porcelain', '-z') and product.frozen() == inputs
        for name, digest in rows.items():
            assert sha(ROOT/name) == digest
        state['status'] = 'publishing-reviewed-research-only'; checkpoint()
        for name, digest in rows.items():
            target = MAIN/name
            assert not target.exists(), name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, target)
            assert sha(target) == digest
        for name in names:
            target = MAIN/name
            if target.exists():
                backup = WORK/'original-main'/name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(target, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(preview/name, target)
        state['main_mutated'] = True; checkpoint()
        expected = {**rows, **{name:sha(MAIN/name) for name in names}}
        pathspec = WORK/'paths.nul'
        pathspec.write_bytes(b'\0'.join(name.encode('utf8') for name in sorted(expected))+b'\0')
        git(MAIN, 'add', '--force', '--pathspec-from-file='+str(pathspec), '--pathspec-file-nul')
        helper = module(MAIN/'scripts/native_index_release_tools.py', 'r17_recovery_index')
        compared = helper.staged_rows({**expected, **inputs})
        git(MAIN, 'diff', '--cached', '--check')
        assert product.frozen() == inputs and not git(MAIN, 'diff', '--name-only')
        receipt = REL/'publication-r2.json'
        save(MAIN/receipt, dict(status='passed-staged-research-only-publication-audit',
             parent_commit=BASELINE, product_unchanged=True, publication_product_inputs=inputs,
             staged_blobs=compared, virtual_publication_links=fresh['virtual_publication_links'],
             fresh_preflight_sha256=sha(WORK/'fresh-preflight.json'),
             original_research_manifest_sha256=sha(ROOT/REL/'release-manifest-r1.json'),
             upstream_tests={'passed':5, 'failed':1, 'skipped':0}, new_product_test_executions=0,
             new_media=0, force_push=False, prior_failure_preserved=True, full_capcut_parity=False))
        git(MAIN, 'add', '--force', '--', receipt.as_posix())
        helper.staged_rows({receipt.as_posix():sha(MAIN/receipt)})
        git(MAIN, 'diff', '--cached', '--check')
        git(MAIN, 'commit', '--quiet', '-m', 'docs: publish OpenFilm reuse review with preserved native failures')
        state['commit'] = git(MAIN, 'rev-parse', 'HEAD').decode().strip()
        assert git(MAIN, 'rev-parse', 'HEAD^').decode().strip() == BASELINE
        state['status'] = 'committed-awaiting-ordinary-push'; checkpoint()
        git(MAIN, 'push', 'origin', 'main')
        remote = git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
        assert remote == state['commit'] and product.frozen() == inputs
        assert not git(MAIN, 'status', '--porcelain', '-z')
        state.update(status='published-R17-research-on-actual-V102', published=True,
                     remote_main=remote, main_clean=True, product_inputs=311,
                     staged_blobs=fresh['staged_blobs'], links=fresh['virtual_publication_links'])
        checkpoint()
    except BaseException as exc:
        state.update(status='failed-preserved', error=repr(exc)); checkpoint(); raise
    finally:
        print(json.dumps({k:state.get(k) for k in ('status','commit','remote_main','error')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
