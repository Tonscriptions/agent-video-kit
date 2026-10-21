"""Run one frozen index suite after the existing V82 publication, never restart it."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
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
UPSTREAM=MAIN/'product/.runtime/worktrees/reverse-chunks-v82-release'
REL='docs/validation/evidence/native-frame-index-20261021-lab'
UPSTREAM_REL='docs/validation/evidence/vfr-reverse-chunks-20261021-v82'
REPORT='docs/validation/原生帧索引缓存独立实验_2026-10-21.md'
MODIFIED={f'product/src/ai_ad_editor/{name}.py' for name in
          ('capabilities','cli','preview','render','reverse_cache','reverse_video_clock')}
ADDED={f'product/src/ai_ad_editor/{name}.py' for name in ('native_video_index','derived_cache')}|{
       f'product/tests/{name}.py' for name in
       ('test_native_video_index','test_native_video_index_ops','test_native_video_index_render')}


def utc():return datetime.now(timezone.utc).isoformat()


def read(path):return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    with path.open('rb') as source:return 'sha256:'+hashlib.file_digest(source,'sha256').hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.writing')
    with temporary.open('w',encoding='utf8',newline='\n') as output:
        json.dump(value,output,ensure_ascii=False,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
    for attempt in range(60):
        try:
            os.replace(temporary,path)
            return
        except OSError as error:
            if getattr(error,'winerror',None) not in {5,32,33} or attempt==59:raise
            # A Windows observer may briefly hold a handle without FILE_SHARE_DELETE.
            # Retry the same fsynced replacement; preserve the original on failure.
            time.sleep(min(.05*(attempt+1),.25))


def git(*args):
    result=subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false',*args],
                          cwd=MAIN,capture_output=True,timeout=1200)
    assert result.returncode==0,result.stderr.decode('utf8','replace')
    return result.stdout


def process(pid):
    command=("[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
             f"Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'|"
             'Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine|ConvertTo-Json -Compress')
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
                          capture_output=True,timeout=30)
    assert result.returncode==0,result.stderr.decode('utf8','replace')
    value=result.stdout.decode('utf-8-sig').strip()
    return json.loads(value) if value else None


def docs_status(message):
    """Preserve the document bytes bound by the previous standalone audit."""
    marker='NATIVE-INDEX-FULL-R1';base=ROOT/REL
    snapshot=base/'before-full-documents-r1.json'
    if not snapshot.exists():
        audit=read(base/'audit-r2.json');directory=base/'before-full-documents-r1';directory.mkdir()
        files={}
        for name,digest in audit['documents'].items():
            path=ROOT/name;assert sha(path)==digest,name
            target=directory/path.name;target.write_bytes(path.read_bytes())
            files[name]={'sha256':digest,'snapshot':target.relative_to(ROOT).as_posix()}
        save(snapshot,{'status':'preserved','documents':files,'audit_sha256':sha(base/'audit-r2.json')})
    for name in ('README.md',REPORT):
        path=ROOT/name;value=path.read_text(encoding='utf8')
        value=value.replace('状态：独立实验，尚未合入 main，未执行该版本的完整回归。',
                            '状态：独立实验，尚未合入 main。完整回归以本文最新记录为准。')
        value=value.replace('实验尚未执行完整回归/合入/推送','专项阶段未执行完整回归；当前状态见最新记录')
        value=value.replace('尚未执行该实验版本完整回归，尚未合入或推送',
                            '专项阶段未执行完整回归，当前结果见最新记录；尚未合入或推送')
        block=f'<!-- {marker} -->\n{message}\n<!-- /{marker} -->'
        pattern=re.escape('<!-- '+marker+' -->')+'.*?'+re.escape('<!-- /'+marker+' -->')
        if re.search(pattern,value,re.S):value=re.sub(pattern,lambda _:block,value,flags=re.S)
        else:
            position=value.index('\n')
            value=value[:position]+'\n\n'+block+'\n'+value[position:]
        path.write_text(value,encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publisher-pid',type=int,required=True)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--html-runtime',type=Path,required=True)
    parser.add_argument('--rubberband',type=Path,required=True)
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args();work=args.work.resolve()
    assert sys.platform=='win32' and work.is_relative_to(ROOT/'product/.runtime') and not work.exists()
    work.mkdir(parents=True);base=ROOT/REL;state={'status':'checking','started_at_utc':utc(),'calls':[]}
    def checkpoint():state['updated_at_utc']=utc();save(work/'run.json',state)
    def read_publisher(path):
        # The existing publisher writes checkpoints in place. A partial JSON
        # read is an observation race, not evidence that the process failed.
        while True:
            try:return read(path)
            except (json.JSONDecodeError,PermissionError):
                observed=process(args.publisher_pid)
                if observed is None:
                    # It can exit immediately after its final checkpoint.
                    time.sleep(.2)
                    return read(path)
                assert all(word in observed['CommandLine'] for word in
                           ('finalize_reverse_chunks.py','--publish','publication-r2'))
                state.update(status='retrying-live-publisher-observation',
                             last_live_observation_utc=utc());checkpoint();time.sleep(1)
    try:
        current=frozen();audit=read(base/'audit-r2.json')
        assert len(current)==254 and audit['status']=='passed-standalone-audit' and audit['frozen_inputs']==current
        upstream=read(UPSTREAM/UPSTREAM_REL/'release-candidate-r2.json')['frozen_inputs']
        assert len(upstream)==249 and set(upstream)<=set(current)
        assert set(current)-set(upstream)==ADDED
        assert {name for name in upstream if upstream[name]!=current[name]}==MODIFIED
        fixture=read(base/'external-fixtures-r1.json');assert fixture['status']=='passed' and len(fixture['fixtures'])==8
        for item in fixture['fixtures']:
            path=ROOT/item['path'];assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
        publisher=UPSTREAM/'product/.runtime/reverse-chunks-20261021-v82/publication-r4/run.json'
        published=read_publisher(publisher);identity=process(args.publisher_pid)
        if published['status']!='published':
            assert identity is not None,'Existing publisher handle is missing; no restart performed'
            assert all(word in identity['CommandLine'] for word in
                       ('finalize_reverse_chunks.py','--publish','publication-r2'))
        else:assert published['remote_main']==published['commit']
        scripts={name:sha(ROOT/'scripts'/name) for name in ('run_native_index_after_v82.py',
            'run_with_regression_fixtures.py','run_frozen_regression.py','materialize_regression_fixtures.py')}
        state.update(status='passed-preflight',frozen_inputs=current,upstream_inputs=upstream,
                     publisher_identity=identity,verification_scripts=scripts,
                     fixture_manifest_sha256=sha(base/'external-fixtures-r1.json'),suite_launched=False,
                     expected_methods=1925,preflight_only=args.preflight_only);checkpoint()
        if args.preflight_only:return
        while True:
            published=read_publisher(publisher)
            if published['status']=='published':break
            assert published['status'] in {'checking','passed-preflight','waiting-for-existing-full-regression',
                'copying-reviewed-candidate','passed-staged-byte-audit','committed-awaiting-ordinary-push'},published['status']
            observed=process(args.publisher_pid)
            if observed is None:
                published=read_publisher(publisher)
                if published['status']=='published':break
                raise AssertionError('Publisher process is missing without a published terminal record; no restart performed')
            assert observed==identity,'Publisher process identity changed; no restart performed'
            state.update(status='waiting-for-live-v82-publisher',last_live_observation_utc=utc(),publisher_status=published['status'])
            checkpoint();time.sleep(15)
        full_upstream=read(UPSTREAM/UPSTREAM_REL/'full-r2.json')
        assert full_upstream['status']=='passed' and full_upstream['methods']==1888 and full_upstream['skipped']==0
        assert full_upstream['frozen_before']==full_upstream['frozen_after']==upstream
        assert full_upstream['external_fixtures_equal'] and full_upstream['verification_scripts_equal']
        commit=published['commit'];assert published['remote_main']==commit
        assert git('branch','--show-current').decode().strip()=='main'
        assert git('rev-parse','HEAD').decode().strip()==commit
        assert git('ls-remote','origin','refs/heads/main').decode().split()[0]==commit
        assert not git('status','--porcelain','-z'),'Main changed; preserve it and refuse implicit integration'
        spec=importlib.util.spec_from_file_location('index_v82_main_freeze',MAIN/'scripts/run_frozen_regression.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        assert module.frozen()==upstream and frozen()==current
        assert {name:sha(ROOT/'scripts'/name) for name in scripts}==scripts
        save(base/'published-v82-alignment-r1.json',{'status':'passed','published_commit':commit,
            'upstream_inputs':upstream,'candidate_inputs':current,'modified_existing_inputs':sorted(MODIFIED),
            'added_inputs':sorted(ADDED),'main_clean_before_suite':True,'remote_main':commit,
            'upstream_full_sha256':sha(UPSTREAM/UPSTREAM_REL/'full-r2.json'),'generator_sha256':sha(Path(__file__))})
        output=base/'full-r1.json';assert not output.exists()
        docs_status(f'2026-10-21：已绑定 V82 发布提交 `{commit[:12]}`，启动本实验版本的完整原生回归，预计 **1925 方法**；尚未标记通过或合入。')
        command=[sys.executable,'-E','-B','-X','utf8',str(ROOT/'scripts/run_with_regression_fixtures.py'),
            '--fixture-manifest',str(base/'external-fixtures-r1.json'),'--output',str(output),
            '--html-runtime',str(args.html_runtime.resolve(strict=True)),
            '--rubberband',str(args.rubberband.resolve(strict=True))]
        state.update(status='running-complete-native-suite',published_v82_commit=commit,command=command,suite_launched=True);checkpoint()
        with (base/'full-r1.launcher.log').open('xb') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        full=read(output)
        state['calls'].append({'command':command,'exit_code':result.returncode})
        assert result.returncode==0 and full['status']=='passed' and full['terminal_ok']
        assert full['methods']==1925 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==frozen()==current
        assert full['external_fixtures_equal'] and full['verification_scripts_equal']
        assert {name:sha(ROOT/'scripts'/name) for name in scripts}==scripts
        docs_status(f"2026-10-21：完整原生回归 **1925 方法、{full['suite_seconds']:.3f} 秒、0 跳过**，254 产品输入与 8 外部夹具不变；仍在独立实验目录，尚未合入或推送该功能。")
        state.update(status='passed-complete-suite-awaiting-reviewed-integration',methods=1925,
                     full_sha256=sha(output),main_integrated=False)
    except BaseException as caught:
        state.update(status='failed',error={'type':type(caught).__name__,'message':str(caught)})
        if state.get('suite_launched'):
            docs_status('2026-10-21：本轮完整原生回归或收据校验未通过；保留原始日志，尚未合入或发布。')
        raise
    finally:
        checkpoint();print(json.dumps({k:state.get(k) for k in ('status','suite_launched','methods','error')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
