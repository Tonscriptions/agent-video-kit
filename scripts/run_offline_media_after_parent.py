"""Run complete2043 after actual V88 publication; freeze nine distributable dependency files."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
UPSTREAM=MAIN/'product/.runtime/audio-source-origin-lab-20261021'
REL='docs/validation/evidence/offline-media-profile-20261021-lab'
UPSTREAM_REL='docs/validation/evidence/audio-source-origin-20261021-lab'
REPORT='docs/validation/八轮离线媒体运行时独立实验_2026-10-21.md'
CONTRACT='docs/specs/离线媒体运行时与NumPy交付_实验_v0.1_2026-10-21.md'
MODIFIED={'product/offline/build.py','product/offline/install.py','product/pyproject.toml'}
ADDED={'product/tests/test_offline_media_profile.py'}
SCRIPTS=('run_offline_media_after_parent.py','run_frozen_regression.py','run_with_regression_fixtures.py',
 'materialize_regression_fixtures.py','prepare_offline_media_lab.py','prepare_media_wheelhouse.py',
 'audit_media_profile_development.py','prepare_media_install_verifier.py','smoke_audio_source_origin.py',
 'verify_media_profile_install.py','finalize_media_profile_lab.py','run_media_profile_related.py',
 'prepare_media_profile_skills.py','finalize_media_profile_audit.py','prepare_media_full_gate.py')


def read(path):
    return json.loads(path.read_bytes())

def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.writing')
    with temporary.open('w', encoding='utf8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(60):
        try:
            os.replace(temporary, path)
            return
        except OSError as error:
            if getattr(error, 'winerror', None) not in {5, 32, 33} or attempt == 59:
                raise
            time.sleep(min(.05 * (attempt + 1), .25))

def git(*args):
    result = subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args],
                            cwd=MAIN, capture_output=True, timeout=1200)
    assert result.returncode == 0, result.stderr.decode('utf8', 'replace')
    return result.stdout

def dependency_inputs():
    base=ROOT/REL;captured=read(base/'wheelhouse-r1.json');directory=ROOT/captured['wheelhouse']
    assert sha(directory/'lock.json')==captured['lock_sha256']
    lock=read(directory/'lock.json')
    assert lock['target']=='cp313-win_amd64' and lock['runtime_profile']=='media-analysis-v1'
    assert len(lock['artifacts'])==8 and sum(row['runtime_dependency'] for row in lock['artifacts'])==7
    expected={directory/'lock.json':captured['lock_sha256']}
    for row in lock['artifacts']:
        path=directory/row['filename'];assert path.parent==directory and path.is_file() and not path.is_symlink()
        assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
        expected[path]=row['sha256']
    assert {p for p in directory.iterdir() if p.is_file()}==set(expected)
    assert len(expected)==9
    return {p.relative_to(ROOT).as_posix():digest for p,digest in expected.items()}


def source_gate():
    current=frozen();base=ROOT/REL;audit=read(base/'audit-r1.json')
    assert audit['status']=='passed-standalone-audit' and audit['targeted_methods']==260
    assert current==audit['frozen_inputs'] and len(current)==260
    for name,digest in audit['documents'].items():assert sha(ROOT/name)==digest
    for name,row in audit['media'].items():assert sha(ROOT/name)==row['sha256']
    assert len(audit['media'])==42 and audit['GIF_count']==14
    for key,name in (('media_manifest_sha256','media-manifest-r1.json'),('static_review_sha256','static-review-r1.json'),
        ('native_verification_sha256','native-r2/verification.json'),('isolated_verification_sha256','installed-r1/verification.json'),
        ('skill_draft_sha256','skills-draft-r1.json'),('wheelhouse_sha256','wheelhouse-r1.json'),('media_audit_sha256','media-audit-r1.json')):
        assert sha(base/name)==audit[key]
    related=read(base/'related-r1.json')
    assert related['status']=='passed-related-regressions' and related['terminal_ok'] and related['exit_code']==0
    assert related['methods']==related['distinct_methods']==260 and related['skipped']==0
    assert len(related['method_ids'])==len(set(related['method_ids']))==260
    assert related['frozen_before']==related['frozen_after']==current and related['frozen_equal']
    assert related['fixtures_unchanged'] and related['fixture_manifest_unchanged'] and related['scripts_unchanged']
    assert len(related['script_hashes'])==10 and len(related['fixture_inputs'])==8
    assert sha(base/'related-r1.json')==audit['related_sha256'] and sha(base/'related-r1.log')==related['log_sha256']
    assert sha(base/'foundation-r1.json')==related['fixture_manifest_sha256']
    for name,digest in related['script_hashes'].items():assert sha(ROOT/'scripts'/name)==digest
    for name,digest in related['fixture_inputs'].items():assert sha(ROOT/name)==digest
    installation=read(base/'installed-r1/verification.json')
    assert installation['status']=='passed' and installation['isolated_cli_calls']==26 and installation['module_origin_probes']==1
    assert installation['frozen_before']==installation['frozen_after']==current
    assert len(installation['checks'])==20 and all(row['ok'] for row in installation['checks'])
    assert len(installation['resource_hashes'])==161 and installation['bundle']['wheels']==8
    distribution=installation['numpy_distribution']
    assert distribution['base_bundle_includes_numpy'] and not distribution['host_site_copied']
    assert distribution['version']=='2.4.2' and len(distribution['original_wheel_files_except_rewritten_RECORD'])==931
    assert len(installation['installation']['audit']['modules'])==8 and len(distribution['native_audit']['extensions'])==2
    for name,digest in installation['resource_hashes'].items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest
    for name in ('native-r2/verification.json','installed-r1/media/verification.json'):
        item=read(base/name)
        assert item['status']=='passed' and item['cli_calls']==23 and item['native_commands']==32
        assert len(item['checks'])==39 and all(row['ok'] for row in item['checks'])
        assert item['frozen_before']==item['frozen_after']==current
        assert item['script_sha256']==sha(ROOT/'scripts/smoke_audio_source_origin.py')
    drafts=read(base/'skills-draft-r1.json')
    assert drafts['status']=='passed-four-unregistered-drafts' and drafts['skill_count']==4 and not drafts['registered']
    for row in drafts['skills'].values():
        assert sha(ROOT/row['path'])==row['sha256'] and row['validator_exit_code']==0 and not row['registered']
        assert sha(ROOT/row['parent_snapshot'])==row['parent_sha256']
    previous=read(base/'foundation-r1.json')['source_inputs']
    assert previous==audit['source_parent_inputs'] and len(previous)==259
    assert set(current)-set(previous)==ADDED
    assert {name for name in previous if previous[name]!=current[name]}==MODIFIED
    fixture=read(base/'external-fixtures-r1.json')
    assert fixture['status']=='passed' and fixture['fixture_count']==8
    for row in fixture['fixtures']:assert sha(ROOT/row['path'])==row['sha256']
    dependency_inputs()
    return current,previous,{name:sha(ROOT/'scripts'/name) for name in SCRIPTS}


def docs_status(message):
    base=ROOT/REL;snapshot=base/'before-full-documents-r1.json'
    if not snapshot.exists():
        audit=read(base/'audit-r1.json');directory=base/'before-full-documents-r1';directory.mkdir();rows={}
        for name,digest in audit['documents'].items():
            source=ROOT/name;assert sha(source)==digest;target=directory/source.name
            target.write_bytes(source.read_bytes());rows[name]={'sha256':digest,'snapshot':target.relative_to(ROOT).as_posix()}
        save(snapshot,{'status':'preserved','documents':rows,'audit_sha256':sha(base/'audit-r1.json')})
    marker='OFFLINE-MEDIA-FULL-R1'
    for name in ('README.md',REPORT,CONTRACT):
        path=ROOT/name;value=path.read_text('utf8')
        value=value.replace('完整2043仅为预计数量，尚未启动，须先绑定实际发布V88/2031；',
            '完整回归执行状态见文首，已绑定实际发布V88/2031；')
        value=value.replace('完整2043仅为预计方法数，须先绑定真实发布的V88/2031，尚未启动；',
            '完整回归执行状态见文首；')
        block='<!-- '+marker+' -->\n'+message+'\n早期MP表保留当时专项记录，当前完整回归状态以本段为准。\n<!-- /'+marker+' -->'
        pattern=re.escape('<!-- '+marker+' -->')+'.*?'+re.escape('<!-- /'+marker+' -->')
        if re.search(pattern,value,re.S):value=re.sub(pattern,lambda _:block,value,flags=re.S)
        else:
            at=value.index('\n');value=value[:at]+'\n\n'+block+'\n'+value[at:]
        path.write_text(value.rstrip()+'\n',encoding='utf8',newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--upstream-publication', type=Path)
    parser.add_argument('--html-runtime', type=Path)
    parser.add_argument('--rubberband', type=Path)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    work = args.work.resolve()
    assert sys.platform == 'win32' and work.is_relative_to(ROOT / 'product/.runtime') and (not work.exists())
    work.mkdir(parents=True)
    state = {'status': 'checking-source', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'suite_launched': False, 'expected_methods': 2043, 'main_integrated': False}

    def checkpoint():
        state['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(work / 'run.json', state)
    try:
        current, previous, scripts = source_gate()
        dependencies = dependency_inputs()
        state.update(status='passed-source-preflight-awaiting-published-audio', frozen_inputs=current, upstream_inputs=previous, verification_scripts=scripts, dependency_artifact_inputs=dependencies)
        checkpoint()
        if args.preflight_only:
            return
        assert args.upstream_publication and args.html_runtime and args.rubberband
        publication = args.upstream_publication.resolve(strict=True)
        assert publication.is_relative_to(UPSTREAM / 'product/.runtime') and publication.name == 'run.json'
        upstream = read(publication)
        assert upstream['status'] == 'published' and upstream['full_methods'] == 2031
        commit = upstream['commit']
        assert upstream['remote_main'] == commit and upstream['main_clean']
        full_previous = read(UPSTREAM / UPSTREAM_REL / 'full-r1.json')
        assert full_previous['status'] == 'passed' and full_previous['terminal_ok']
        assert full_previous['methods'] == 2031 and full_previous['skipped'] == 0
        assert full_previous['frozen_before'] == full_previous['frozen_after'] == previous
        assert full_previous['external_fixture_count'] == 8 and full_previous['external_fixtures_equal']
        assert full_previous['verification_scripts_equal'] and full_previous['external_fixture_manifest_unchanged']
        assert git('branch', '--show-current').decode().strip() == 'main'
        assert git('remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git('rev-parse', 'HEAD').decode().strip() == commit
        assert git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == commit
        assert not git('status', '--porcelain', '-z')
        spec = importlib.util.spec_from_file_location('audio_published_freeze', MAIN / 'scripts/run_frozen_regression.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.frozen() == previous and frozen() == current
        assert sha(MAIN / UPSTREAM_REL / 'full-r1.json') == sha(UPSTREAM / UPSTREAM_REL / 'full-r1.json')
        base = ROOT / REL
        save(base / 'published-audio-alignment-r1.json', {'status': 'passed', 'published_commit': commit, 'remote_main': commit, 'upstream_inputs': previous, 'candidate_inputs': current, 'modified_existing_inputs': sorted(MODIFIED), 'added_inputs': sorted(ADDED), 'main_clean_before_suite': True, 'upstream_full_sha256': sha(UPSTREAM / UPSTREAM_REL / 'full-r1.json'), 'publication_record_sha256': sha(publication), 'generator_sha256': sha(__file__)})
        output = base / 'full-r1.json'
        assert not output.exists()
        docs_status('已绑定音频起点发布提交 `' + commit[:12] + '`，启动此版本的 **2043 方法**完整原生回归；尚未标记通过、合入或发布。')
        command = [sys.executable, '-E', '-B', '-X', 'utf8', str(ROOT / 'scripts/run_with_regression_fixtures.py'), '--fixture-manifest', str(base / 'external-fixtures-r1.json'), '--output', str(output), '--html-runtime', str(args.html_runtime.resolve(strict=True)), '--rubberband', str(args.rubberband.resolve(strict=True))]
        state.update(status='running-complete-native-suite', suite_launched=True, published_audio_commit=commit, command=command)
        checkpoint()
        with (base / 'full-r1.launcher.log').open('xb') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        item = read(output)
        assert result.returncode == 0 and item['status'] == 'passed' and item['terminal_ok']
        assert item['methods'] == 2043 and item['skipped'] == 0
        assert item['frozen_before'] == item['frozen_after'] == frozen() == current
        assert item['external_fixture_count'] == 8 and item['external_fixtures_equal']
        assert item['verification_scripts_equal'] and item['external_fixture_manifest_unchanged']
        assert all((sha(ROOT / 'scripts' / name) == digest for name, digest in scripts.items()))
        dependencies_after = dependency_inputs()
        assert dependencies_after == dependencies
        save(base / 'full-dependencies-r1.json', {'status': 'passed-dependency-artifact-freeze', 'before': dependencies, 'after': dependencies_after, 'artifact_count': 9, 'includes_wheelhouse_lock': True, 'complete_suite_used_host_native_runtime': True, 'isolated_eight_wheel_media_separately_verified': True, 'full_sha256': sha(output), 'generator_sha256': sha(__file__)})
        state.update(dependency_artifacts_unchanged=True, dependency_freeze_sha256=sha(base / 'full-dependencies-r1.json'))
        docs_status('完整原生回归 **2043 方法、' + format(item['suite_seconds'], '.3f') + ' 秒、0 跳过**；260 产品输入及 8 外部夹具不变。尚未合入 main 或推送此实验。')
        state.update(status='passed-complete-suite-awaiting-reviewed-integration', methods=2043, full_sha256=sha(output), suite_seconds=item['suite_seconds'])
    except BaseException as error:
        state.update(status='failed', error={'type': type(error).__name__, 'message': str(error)})
        if state['suite_launched']:
            docs_status('完整回归或收据校验未通过；保留实际日志，尚未合入或发布此实验。')
        raise
    finally:
        checkpoint()
        print(json.dumps({k: state.get(k) for k in ('status', 'suite_launched', 'methods', 'error')}, ensure_ascii=False), flush=True)

if __name__=="__main__":main()
