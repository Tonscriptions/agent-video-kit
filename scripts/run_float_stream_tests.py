"""Actual stream/audio test receipts, with unchanged product inputs."""
from datetime import datetime,timezone
import argparse,json,os,subprocess,sys
from pathlib import Path
from run_frozen_regression import frozen,sha
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--revision',required=True);args=parser.parse_args()
    base=ROOT/'docs/validation/evidence/float-stream-20261022-lab';out=base/('stream-'+args.revision+'.json');child=out.with_suffix('.child.json');log=out.with_suffix('.log')
    assert not any(p.exists() for p in (out,child,log));before=frozen();assert len(before)==292
    value={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,
        'generator_sha256':sha(Path(__file__)),'native_windows':True,'virtualization':False,'network':False,'published':False,'default_renderer_integrated':False}
    def save():out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    bootstrap=('import sys,unittest,json,pathlib,time;sys.path[:0]=[sys.argv[1],sys.argv[2]];from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
        'import test_float_stream as m;start=time.monotonic();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(m));'
        'v={"methods":r.testsRun,"seconds":time.monotonic()-start,"failures":len(r.failures),"errors":len(r.errors),"skipped":len(r.skipped),"successful":r.wasSuccessful(),"script_native_calls":m.NATIVE_CALLS,"actual_encoder_receipts":m.ENCODE_RECEIPTS,"expected_and_actual_errors":m.ERROR_RECEIPTS};'
        'pathlib.Path(sys.argv[3]).write_text(json.dumps(v,indent=2)+"\\n",encoding="utf8");raise SystemExit(0 if r.wasSuccessful() and not r.skipped else 1)')
    command=list(map(str,[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,ROOT/'product/src',ROOT/'product/tests',child]));value['command']=command;save()
    env=dict(os.environ,TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'))
    try:
        with log.open('xb') as stream:result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        value.update(exit_code=result.returncode,result=json.loads(child.read_bytes()),log_sha256=sha(log));assert result.returncode==0 and value['result']['successful'] and value['result']['skipped']==0;assert frozen()==before
        value['status']='passed-native-FFV1-stereo-and-owned-pipe-lifecycle'
    except BaseException as exc:value.update(status='failed-preserved',error=repr(exc));raise
    finally:
        value.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen());save()
        out.with_suffix('.executed.py.txt').write_bytes(Path(__file__).read_bytes());print(json.dumps({k:value.get(k) for k in ('status','exit_code','error')}),flush=True)

if __name__=='__main__':main()
