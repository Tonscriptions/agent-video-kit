"""Run complete2148 only against actual published V90 and bound native evidence."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
from audio_clock_release_common import ROOT, MAIN, REL, REPORT, CONTRACT, read, save, verify, source_gate
from run_frozen_regression import frozen, sha

def docs_status(message):
    marker = 'AUDIO-CLOCK-FULL-R2'
    for name in (REPORT, CONTRACT):
        path = ROOT/name; text = path.read_text('utf8')
        block = '<!-- '+marker+' -->\n'+message+'\n历史专项单独保留，完整回归以本段及原始收据为准。\n<!-- /'+marker+' -->'
        pattern = re.escape('<!-- '+marker+' -->')+'.*?'+re.escape('<!-- /'+marker+' -->')
        if re.search(pattern, text, re.S):
            text = re.sub(pattern, lambda _:block, text, flags=re.S)
        else:
            first, body = text.split('\n',1); text = first+'\n\n'+block+'\n'+body
        path.write_text(text, encoding='utf8', newline='\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path); parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args(); work = args.work.resolve()
    assert work.is_relative_to(ROOT/'product/.runtime') and not work.exists(); work.mkdir(parents=True)
    state = {'status':'checking', 'started_at_utc':datetime.now(timezone.utc).isoformat(), 'pid':os.getpid(),
             'suite_launched':False, 'expected_methods':2148, 'main_integrated':False}
    def checkpoint(): save(work/'run.json',state)
    checkpoint()
    try:
        audit = source_gate(); save(work/'source-preflight.json',audit)
        state.update(status='passed-preflight', source_preflight_sha256=sha(work/'source-preflight.json')); checkpoint()
        if args.preflight_only: return
        assert not (REL/'audit-r2.json').exists(); save(REL/'audit-r2.json', audit)
        save(REL/'external-fixtures-r2.json', {'status':'passed', 'fixture_count':8,
             'fixtures':[{'path':name, 'sha256':digest, 'bytes':(ROOT/name).stat().st_size}
                         for name,digest in audit['fixture_inputs'].items()],
             'source_commit':audit['published_parent_commit'], 'network':False, 'virtualization':False,
             'generator_sha256':sha(Path(__file__))})
        snapshots=REL/'before-full-documents-r2'; snapshots.mkdir()
        for name in audit['documents']: (snapshots/Path(name).name).write_bytes((ROOT/name).read_bytes())
        output=REL/'full-r2.json'; assert not output.exists()
        docs_status('已绑定实际发布V90 /2084及267产品输入，启动 **2148方法** 完整原生回归；尚未通过、合入或发布。')
        command=list(map(str,[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/run_with_regression_fixtures.py',
            '--fixture-manifest',REL/'external-fixtures-r2.json','--output',output,
            '--html-runtime',MAIN/'product/.runtime/html-motion-runtime-20261018-e2.json',
            '--rubberband',MAIN/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe']))
        env=dict(os.environ,AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES=str(REL/'original-r1/source-manifest.json'))
        state.update(status='running-complete-native-suite', suite_launched=True,command=command,
                     published_parent_commit=audit['published_parent_commit']); checkpoint()
        with (REL/'full-r2.launcher.log').open('xb') as stream:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        item=read(output)
        assert result.returncode==0 and item['status']=='passed' and item['terminal_ok']
        assert item['methods']==2148 and item['skipped']==0
        assert item['frozen_before']==item['frozen_after']==frozen()==audit['frozen_inputs']
        assert item['external_fixture_count']==8 and item['external_fixtures_equal'] and item['external_fixture_manifest_unchanged']
        assert item['verification_scripts_equal']
        verify(ROOT/'scripts',audit['verification_scripts']); verify(ROOT,audit['dependency_artifact_inputs'])
        verify(ROOT,audit['fixture_inputs']); verify(REL,audit['bound_evidence']); verify(ROOT,audit['media_inputs'])
        save(REL/'full-dependencies-r2.json', {'status':'passed-extra-frozen-inputs','scripts':audit['verification_scripts'],
             'dependencies':audit['dependency_artifact_inputs'],'fixtures':audit['fixture_inputs'],
             'media':audit['media_inputs'],'full_sha256':sha(output)})
        docs_status('完整原生回归 **2148方法 /'+format(item['suite_seconds'],'.3f')+'秒 /0跳过**，267输入、8夹具、16脚本和9依赖文件保持相同；历史2145回归4个队列失败及修复专项另行保留；尚未合入或发布。')
        state.update(status='passed-complete-suite-awaiting-reviewed-integration',methods=2148,
                     full_sha256=sha(output),suite_seconds=item['suite_seconds'])
    except BaseException as error:
        state.update(status='failed-preserved-for-review',error=repr(error))
        if state['suite_launched']: docs_status('完整回归或收据核验未通过，保留实际证据；尚未合入或发布。')
        raise
    finally:
        state['updated_at_utc']=datetime.now(timezone.utc).isoformat(); checkpoint()
        print({key:state.get(key) for key in ('status','suite_launched','methods','error')},flush=True)

if __name__=='__main__':main()
