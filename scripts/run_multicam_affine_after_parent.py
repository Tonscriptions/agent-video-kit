"""Gate and run complete2084 against actual published V89 and frozen independent evidence."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1];MAIN=Path('E:/dev/sandbox/AI广告剪辑')
PARENT=MAIN/'product/.runtime/offline-media-profile-lab-20261021'
REL=ROOT/'docs/validation/evidence/multicam-affine-clock-20261021-lab'
PARENT_REL=PARENT/'docs/validation/evidence/offline-media-profile-20261021-lab'
PUB=PARENT/'product/.runtime/offline-media-profile-20261021/publication-r1/run.json'
MODIFIED={'product/src/ai_ad_editor/'+n+'.py' for n in ('cli','multicam','capabilities','render')}
ADDED={'product/src/ai_ad_editor/multicam_clock.py','product/tests/test_multicam_affine_clock.py','product/tests/test_audio_resample_precision.py'}
SCRIPTS=('run_multicam_affine_after_parent.py','run_frozen_regression.py','run_with_regression_fixtures.py',
 'materialize_regression_fixtures.py','prepare_multicam_affine_lab.py','smoke_multicam_affine_clock.py',
 'run_multicam_affine_related.py','run_audio_precision_regression.py','diagnose_multicam_affine_pcm.py',
 'prepare_multicam_affine_install.py','verify_multicam_affine_install.py','complete_multicam_affine_install.py',
 'finalize_multicam_affine_media.py','prepare_multicam_affine_skills.py')
REPORT='docs/validation/多机位仿射时钟与浮点音频独立实验_2026-10-21.md'
CONTRACT='docs/specs/多机位仿射时钟与漂移校准_实验_v0.1_2026-10-21.md'

def read(path):return json.loads(Path(path).read_bytes())
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def git(*args):
    result=subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false',*map(str,args)],
        cwd=MAIN,capture_output=True,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,result.stderr.decode('utf8','replace')[-1000:]
    return result.stdout
def verify_map(root,items):
    for name,digest in items.items():assert sha(root/name)==digest,name

def gate():
    current=frozen();assert len(current)==263
    foundation=read(REL/'foundation-r1.json');previous=foundation['source_inputs'];assert len(previous)==260
    assert set(current)-set(previous)==ADDED
    assert {p for p in previous if previous[p]!=current[p]}==MODIFIED
    parent=read(PUB);full=read(PARENT_REL/'full-r1.json')
    assert parent['status']=='published' and parent['full_methods']==2043 and parent['main_clean']
    assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2043 and full['skipped']==0
    assert full['frozen_before']==full['frozen_after']==previous
    assert full['verification_scripts_equal'] and full['external_fixtures_equal']
    assert full['external_fixture_manifest_unchanged'] and full['external_fixture_count']==8
    assert git('branch','--show-current').decode().strip()=='main'
    assert git('remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'
    head=git('rev-parse','HEAD').decode().strip()
    assert git('ls-remote','--heads','origin','main').decode().split()[0]==head
    assert not git('status','--porcelain','-z')
    git('merge-base','--is-ancestor',parent['commit'],head)
    changes=[name.decode('utf8') for name in git('diff','--name-only','-z',parent['commit'],head).split(b'\0') if name]
    assert all(name=='README.md' or name.startswith('docs/') for name in changes)
    spec=importlib.util.spec_from_file_location('published_V89_freeze',MAIN/'scripts/run_frozen_regression.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.frozen()==previous
    related=read(REL/'related-r3.json')
    assert related['status']=='passed-related-regressions' and related['methods']==related['distinct_methods']==157
    assert related['terminal_ok'] and related['skipped']==0 and related['exit_code']==0
    assert len(related['method_ids'])==len(set(related['method_ids']))==157
    assert related['frozen_before']==related['frozen_after']==current
    assert sha(REL/'related-r3.log')==related['log_sha256']
    verify_map(ROOT/'scripts',related['script_hashes'])
    precision=read(REL/'audio-precision-after-r2.json')
    assert precision['status']=='passed' and precision['methods']==8 and precision['skipped']==0
    assert precision['frozen_before']==precision['frozen_after']==current
    native=read(REL/'native-r3/verification.json');isolated=read(REL/'installed-r1/media/verification.json')
    for item in (native,isolated):
        assert item['status']=='passed' and item['cli_calls']==39 and item['other_native_commands']==21
        assert len(item['checks'])==52 and all(row['ok'] for row in item['checks'])
        assert item['frozen_before']==item['frozen_after']==current
        assert item['generator_sha256']==sha(ROOT/'scripts/smoke_multicam_affine_clock.py')
    assert native['cases']==isolated['cases']
    failed_wrapper=read(REL/'installed-r1/verification.json');post=read(REL/'installed-postflight-r3/verification.json')
    assert failed_wrapper['status']=='failed' and failed_wrapper['error']=="KeyError('multicam_clock')"
    assert len(failed_wrapper['checks'])==20 and all(row['ok'] for row in failed_wrapper['checks'])
    assert failed_wrapper['frozen_before']==failed_wrapper['frozen_after']==current
    assert len(failed_wrapper['resource_hashes'])==162 and failed_wrapper['bundle']['wheels']==8
    assert post['status']=='passed-isolated-postflight' and post['isolated_methods']==41 and post['isolated_skipped']==0
    assert post['frozen_before']==post['frozen_after']==current and all(row['ok'] for row in post['checks'])
    assert post['previous_wrapper_receipt_sha256']==sha(REL/'installed-r1/verification.json')
    assert post['corrected_verifier_sha256']==sha(ROOT/'scripts/verify_multicam_affine_install.py')
    media=read(REL/'media-manifest-r1.json')
    assert media['status']=='passed-media-inventory' and media['asset_count']==33 and media['GIF_count']==9
    assert media['frozen_before']==media['frozen_after']==current
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256']
    drafts=read(REL/'skills-draft-r1.json')
    assert drafts['status']=='passed-four-unregistered-drafts' and not drafts['registered'] and drafts['canonical_skill_count']==17
    for name,row in drafts['skills'].items():
        assert sha(ROOT/row['path'])==row['sha256'] and row['validator_exit_code']==0
        assert sha(MAIN/'skills'/name/'SKILL.md')==row['parent_sha256']
    verify_map(ROOT,foundation['dependency_artifact_inputs']);assert len(foundation['dependency_artifact_inputs'])==9
    fixtures=[]
    for row in foundation['external_fixtures']:
        path=ROOT/row['path'];assert sha(path)==row['sha256']
        fixtures.append({'path':row['path'],'bytes':path.stat().st_size,'sha256':row['sha256']})
    assert len(fixtures)==8
    links=[]
    for name in ('README.md',REPORT,CONTRACT):
        path=ROOT/name
        for match in re.finditer(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)',path.read_text('utf8')):
            target=match.group(1).strip('<>')
            if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target) or target.startswith('#'):continue
            resolved=path.parent/target.split('#',1)[0]
            assert resolved.exists(),(name,target)
            links.append({'source':name,'target':target})
    evidence_names=('foundation-r1.json','related-r3.json','audio-precision-after-r2.json',
        'native-r3/verification.json','installed-r1/verification.json','installed-r1/media/verification.json',
        'installed-postflight-r3/verification.json','media-manifest-r1.json','skills-draft-r1.json','static-review-r1.json')
    audit={'status':'passed-source-and-evidence-preflight','frozen_inputs':current,'published_parent_inputs':previous,
        'published_parent_commit':parent['commit'],'main_documentation_commit':head,'main_clean':True,
        'parent_full_methods':2043,'parent_full_sha256':sha(PARENT_REL/'full-r1.json'),
        'parent_publication_sha256':sha(PUB),'modified_inputs':sorted(MODIFIED),'added_inputs':sorted(ADDED),
        'verification_scripts':{name:sha(ROOT/'scripts'/name) for name in SCRIPTS},
        'fixture_inputs':{row['path']:row['sha256'] for row in fixtures},
        'dependency_artifact_inputs':foundation['dependency_artifact_inputs'],
        'bound_evidence':{name:sha(REL/name) for name in evidence_names},'local_document_links':links,
        'documents':{name:sha(ROOT/name) for name in ('README.md',REPORT,CONTRACT)},
        'source_full_suite_uses_host_native_runtime':True,'isolated_eight_wheel_checks_separate':True,
        'full_suite_launched':False,'full_capcut_parity':False}
    return audit,fixtures

def docs_status(message):
    marker='MULTICAM-AFFINE-FULL-R1'
    for name in ('README.md',REPORT,CONTRACT):
        path=ROOT/name;text=path.read_text('utf8')
        text=text.replace('当前为独立实验，尚未合入产品或完成完整回归。','当前为独立实验；完整回归状态见文首，尚未合入产品。')
        text=text.replace('后续完整数量预计 **2084**，不能当作已通过。','完整回归状态以文首执行收据为准。')
        text=text.replace('**完整2084仅为预计数量，尚未启动，不是已合入或产品等价验收。**','**完整回归状态见文首；不表示产品等价验收。**')
        block='<!-- '+marker+' -->\n'+message+'\n历史专项结果保留，完整回归状态以本段为准。\n<!-- /'+marker+' -->'
        pattern=re.escape('<!-- '+marker+' -->')+'.*?'+re.escape('<!-- /'+marker+' -->')
        if re.search(pattern,text,re.S):text=re.sub(pattern,lambda _:block,text,flags=re.S)
        else:
            first,body=text.split('\n',1);text=first+'\n\n'+block+'\n'+body
        path.write_text(text,encoding='utf8',newline='\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--preflight-only',action='store_true');args=parser.parse_args()
    work=args.work.resolve();assert work.is_relative_to(ROOT/'product/.runtime') and not work.exists();work.mkdir(parents=True)
    state={'status':'checking','started_at_utc':datetime.now(timezone.utc).isoformat(),'pid':os.getpid(),'suite_launched':False,'expected_methods':2084,'main_integrated':False}
    def checkpoint():save(work/'run.json',state)
    checkpoint()
    try:
        audit,fixtures=gate();save(work/'source-preflight.json',audit)
        state.update(status='passed-preflight',source_preflight_sha256=sha(work/'source-preflight.json'));checkpoint()
        if args.preflight_only:return
        assert not (REL/'audit-r1.json').exists();save(REL/'audit-r1.json',audit)
        save(REL/'external-fixtures-r1.json',{'status':'passed','fixture_count':8,'fixtures':fixtures,'network':False,
            'virtualization':False,'source_commit':'0917d22739ac44a20d8c1ad8b7e8e99a14f1139a','generator_sha256':sha(Path(__file__))})
        snapshots=REL/'before-full-documents-r1';snapshots.mkdir()
        for name in audit['documents']:(snapshots/Path(name).name).write_bytes((ROOT/name).read_bytes())
        output=REL/'full-r1.json';assert not output.exists()
        docs_status('已绑定实际发布V89/2043及纯文档提交`'+audit['main_documentation_commit'][:12]+'`，启动**2084方法**完整原生回归；尚未通过、合入或发布。')
        command=[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/run_with_regression_fixtures.py',
            '--fixture-manifest',REL/'external-fixtures-r1.json','--output',output,
            '--html-runtime',MAIN/'product/.runtime/html-motion-runtime-20261018-e2.json',
            '--rubberband',MAIN/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe']
        command=list(map(str,command));state.update(status='running-complete-native-suite',suite_launched=True,command=command,
            published_parent_commit=audit['published_parent_commit'],main_documentation_commit=audit['main_documentation_commit']);checkpoint()
        with (REL/'full-r1.launcher.log').open('xb') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        item=read(output)
        assert result.returncode==0 and item['status']=='passed' and item['terminal_ok']
        assert item['methods']==2084 and item['skipped']==0
        assert item['frozen_before']==item['frozen_after']==frozen()==audit['frozen_inputs']
        assert item['external_fixture_count']==8 and item['external_fixtures_equal'] and item['external_fixture_manifest_unchanged']
        assert item['verification_scripts_equal']
        verify_map(ROOT/'scripts',audit['verification_scripts']);verify_map(ROOT,audit['dependency_artifact_inputs'])
        verify_map(ROOT,audit['fixture_inputs']);verify_map(REL,audit['bound_evidence'])
        save(REL/'full-dependencies-r1.json',{'status':'passed-extra-frozen-inputs','scripts':audit['verification_scripts'],
            'dependencies':audit['dependency_artifact_inputs'],'fixtures':audit['fixture_inputs'],'full_sha256':sha(output)})
        docs_status('完整原生回归**2084方法/'+format(item['suite_seconds'],'.3f')+'秒/0跳过**，263输入、8夹具、14脚本和9依赖文件保持相同；尚未合入或发布。')
        state.update(status='passed-complete-suite-awaiting-reviewed-integration',methods=2084,
            full_sha256=sha(output),suite_seconds=item['suite_seconds'])
    except BaseException as error:
        state.update(status='failed-preserved-for-review',error=repr(error))
        if state['suite_launched']:docs_status('完整回归或收据验证未通过，保留实际证据；尚未合入或发布。')
        raise
    finally:
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat();checkpoint()
        print(json.dumps({k:state.get(k) for k in ('status','suite_launched','methods','error')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
