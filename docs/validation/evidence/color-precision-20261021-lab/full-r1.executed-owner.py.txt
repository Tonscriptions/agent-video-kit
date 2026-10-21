"""Complete native suite for the V91-rebased float CLI; preserve every gate."""
from datetime import datetime, timezone
import json, os
from pathlib import Path
import subprocess, sys
from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path('E:/dev/sandbox/AI广告剪辑')
REL = ROOT/'docs/validation/evidence/color-precision-20261021-lab'
PARENT = '18f5dc766a80e0b47f096b1b93ccfe1cee0fb5f6'

def read(path): return json.loads(path.read_bytes())
def utc(): return datetime.now(timezone.utc).isoformat()
def verify(base, mapping):
    for name, expected in mapping.items():
        assert sha(base/name) == expected, name+' changed'

def main():
    work = ROOT/'product/.runtime/color-precision-20261021/complete-r1'
    output = REL/'full-r1.json'
    assert not work.exists() and not output.exists()
    work.mkdir(parents=True)
    record = {'status':'checking','started_at_utc':utc(),'pid':os.getpid(),
              'suite_launched':False,'expected_methods':2234,'native_windows':True,
              'virtualization':False,'network':False,'published':False,
              'timeline_renderer_integrated':False}
    def save():
        (work/'run.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        lineage = read(REL/'parent-rebase-r1.json')
        assert lineage['status']=='passed-exact-two-file-rebase-from-published-V91'
        assert lineage['published_parent_commit']==PARENT
        before = frozen()
        assert before==lineage['frozen_after'] and len(before)==282
        parent_full = read(MAIN/'docs/validation/evidence/audio-discontinuity-20261021-lab/full-r2.json')
        assert parent_full['terminal_ok'] and parent_full['methods']==2148 and parent_full['skipped']==0
        assert subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false','rev-parse','HEAD'],
            cwd=MAIN,capture_output=True,text=True,check=True).stdout.strip()==PARENT
        deps = read(REL/'foundation-r1.json')['dependency_artifact_inputs']
        assert len(deps)==9
        verify(ROOT,deps)
        scripts = {p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'scripts').glob('*.py'))}
        evidence_inputs = {p.relative_to(ROOT).as_posix():sha(p) for p in (
            REL/'parent-rebase-r1.json',REL/'external-fixtures-r1.json',REL/'foundation-r1.json',REL/'kernel-r11.json')}
        env = dict(os.environ)
        env.pop('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES',None)
        record.update(audio_clock_fixtures='fresh native test-local generation; no borrowed original-r1 manifest',
                      frozen_inputs=before,verification_scripts=scripts,
                      dependency_artifact_inputs=deps,bound_evidence=evidence_inputs,
                      published_parent_commit=PARENT)
        discovery = ('import sys,unittest;sys.path.insert(0,sys.argv[1]);'
            'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
            's=unittest.defaultTestLoader.discover(sys.argv[2]);print(s.countTestCases())')
        count = subprocess.run([sys.executable,'-E','-B','-X','utf8','-c',discovery,
            str(ROOT/'product/src'),str(ROOT/'product/tests')],cwd=ROOT,env=env,capture_output=True,check=True)
        record['discovery_stdout']=count.stdout.decode('utf8','replace')
        record['discovery_stderr']=count.stderr.decode('utf8','replace')
        assert int(record['discovery_stdout'].strip())==2234
        command = list(map(str,[sys.executable,'-E','-B','-X','utf8',ROOT/'scripts/run_with_regression_fixtures.py',
            '--fixture-manifest',REL/'external-fixtures-r1.json','--output',output,
            '--html-runtime',MAIN/'product/.runtime/html-motion-runtime-20261018-e2.json',
            '--rubberband',MAIN/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe']))
        record.update(status='running-complete-native-suite',suite_launched=True,command=command)
        save()
        with (REL/'full-r1.launcher.log').open('xb') as stream:
            result = subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        receipt=read(output)
        record['suite_exit_code']=result.returncode
        assert result.returncode==0 and receipt['status']=='passed' and receipt['terminal_ok']
        assert receipt['methods']==2234 and receipt['skipped']==0
        assert receipt['frozen_before']==receipt['frozen_after']==frozen()==before
        assert receipt['external_fixture_count']==8 and receipt['external_fixtures_equal']
        assert receipt['external_fixture_manifest_unchanged'] and receipt['verification_scripts_equal']
        verify(ROOT,scripts);verify(ROOT,deps);verify(ROOT,evidence_inputs)
        record.update(status='passed-complete-native-suite-not-published',methods=receipt['methods'],
                      suite_seconds=receipt['suite_seconds'],full_receipt_sha256=sha(output),
                      frozen_equal=True,dependencies_equal=True,verification_scripts_equal=True)
    except BaseException as exc:
        record.update(status='failed-preserved',error=repr(exc))
        raise
    finally:
        record['updated_at_utc']=utc();save()
        (REL/'full-r1.executed-owner.py.txt').write_bytes(Path(__file__).read_bytes())
        print(json.dumps({k:record.get(k) for k in ('status','suite_launched','methods','error')}),flush=True)

if __name__=='__main__':main()
