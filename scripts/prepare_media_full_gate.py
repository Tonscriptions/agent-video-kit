"""Prepare a complete2043 gate with pinned distributable wheels and an actual V88 parent."""
import ast
import hashlib
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
DONOR=ROOT.parent/'audio-source-origin-lab-20261021'
REL=ROOT/'docs/validation/evidence/offline-media-profile-20261021-lab'
TARGET=ROOT/'scripts/run_offline_media_after_parent.py'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


DEPENDENCIES=r'''def dependency_inputs():
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
'''


SOURCE_GATE=r'''def source_gate():
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
'''


DOCS_STATUS=r'''def docs_status(message):
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
'''


def main():
    output=REL/'full-gate-preparation-r1.json';assert not output.exists() and not TARGET.exists()
    current=frozen();audit=json.loads((REL/'audit-r1.json').read_bytes());assert current==audit['frozen_inputs'] and len(current)==260
    donor=DONOR/'scripts/run_audio_origin_after_parent.py';source=donor.read_text('utf8');tree=ast.parse(source)
    functions={node.name:ast.get_source_segment(source,node) for node in tree.body if isinstance(node,ast.FunctionDef)}
    node=ast.parse(functions['main'])
    class UpdateParent(ast.NodeTransformer):
        def visit_Constant(self,node):
            if type(node.value) is int and node.value in {2019,2031}:
                return ast.copy_location(ast.Constant(value={2019:2031,2031:2043}[node.value]),node)
            if isinstance(node.value,str):
                value=node.value.replace('passed-source-preflight-awaiting-published-stream','passed-source-preflight-awaiting-published-audio')
                value=value.replace('published-stream-alignment-r1','published-audio-alignment-r1').replace('stream_published_freeze','audio_published_freeze')
                value=value.replace('已绑定原生视频覆盖发布提交','已绑定音频起点发布提交').replace('2031 方法','2043 方法').replace('259 产品输入','260 产品输入')
                return ast.copy_location(ast.Constant(value=value),node)
            return node
        def visit_keyword(self,node):
            node=self.generic_visit(node)
            if node.arg=='published_stream_commit':node.arg='published_audio_commit'
            return node
    adapted=ast.unparse(ast.fix_missing_locations(UpdateParent().visit(node)))
    before='current, previous, scripts = source_gate()';assert adapted.count(before)==1
    adapted=adapted.replace(before,before+'\n        dependencies = dependency_inputs()')
    before="verification_scripts=scripts)";assert adapted.count(before)==1
    adapted=adapted.replace(before,"verification_scripts=scripts, dependency_artifact_inputs=dependencies)")
    before="        docs_status('完整原生回归 **2043 方法、'";assert adapted.count(before)==1
    extra="""        dependencies_after = dependency_inputs()
        assert dependencies_after == dependencies
        save(base / 'full-dependencies-r1.json', {'status': 'passed-dependency-artifact-freeze', 'before': dependencies, 'after': dependencies_after, 'artifact_count': 9, 'includes_wheelhouse_lock': True, 'complete_suite_used_host_native_runtime': True, 'isolated_eight_wheel_media_separately_verified': True, 'full_sha256': sha(output), 'generator_sha256': sha(__file__)})
        state.update(dependency_artifacts_unchanged=True, dependency_freeze_sha256=sha(base / 'full-dependencies-r1.json'))
"""
    adapted=adapted.replace(before,extra+before)
    constants='''ROOT=Path(__file__).resolve().parents[1]
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
'''
    imports='\n'.join(ast.get_source_segment(source,n) for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom)))
    text='"""Run complete2043 after actual V88 publication; freeze nine distributable dependency files."""\n'
    text+='\n\n'.join([imports,constants,*[functions[n] for n in ('read','sha','save','git')],DEPENDENCIES,SOURCE_GATE,DOCS_STATUS,adapted])
    text+='\n\nif __name__=="__main__":main()\n';parsed=ast.parse(text);compile(parsed,str(TARGET),'exec')
    same={name:ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)==ast.dump(next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False) for name in ('read','sha','save','git')}
    assert all(same.values())
    fixture=DONOR/'docs/validation/evidence/audio-source-origin-20261021-lab/external-fixtures-r1.json'
    foundation=json.loads((REL/'foundation-r1.json').read_bytes());assert sha(fixture)==foundation['external_fixture_manifest_sha256']
    target_fixture=REL/'external-fixtures-r1.json';assert not target_fixture.exists()
    TARGET.write_text(text,encoding='utf8',newline='\n');target_fixture.write_bytes(fixture.read_bytes());assert frozen()==current
    record={'status':'prepared-not-launched','expected_future_methods':2043,'required_actual_parent_methods':2031,
        'frozen_inputs':current,'pinned_script_count':15,'dependency_artifact_files_including_lock':9,
        'donor_script':str(donor),'donor_sha256':sha(donor),'shared_helpers_AST_unchanged':same,
        'launcher_sha256':sha(TARGET),'fixture_manifest_sha256':sha(target_fixture),
        'complete_suite_is_native_source_not_all_installed_tests':True,'isolated_media_is_separate':True,
        'full_suite_started':False,'main_integrated':False,'generator_sha256':sha(__file__)}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','expected_future_methods','required_actual_parent_methods','pinned_script_count','dependency_artifact_files_including_lock')}))


if __name__=='__main__':main()
