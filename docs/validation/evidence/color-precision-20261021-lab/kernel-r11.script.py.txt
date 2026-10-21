"""Preserve actual native kernel unit receipts without claiming editor integration."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'
BOOTSTRAP='''
import json,pathlib,sys,time,unittest
sys.path[:0]=[sys.argv[1],sys.argv[2]]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
import test_float_raster,test_float_geometry,test_float_pixels,test_float_video_source,test_float_yuv,test_float_color_signal,test_float_bundle
suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(module)
    for module in (test_float_raster,test_float_geometry,test_float_pixels,test_float_video_source,test_float_yuv,test_float_color_signal,test_float_bundle)])
expected=suite.countTestCases();started=time.monotonic()
result=unittest.TextTestRunner(verbosity=2).run(suite)
value={'methods':result.testsRun,'discovered_methods':expected,'suite_seconds':time.monotonic()-started,
    'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
    'terminal_success':result.wasSuccessful(),'native_calls':test_float_raster.NATIVE_CALLS+test_float_pixels.NATIVE_CALLS+test_float_video_source.NATIVE_CALLS+test_float_yuv.NATIVE_CALLS+[row for row in test_float_bundle.NATIVE_CALLS if row['kind']!='actual-in-process-CLI'],
    'cli_calls':[row for row in test_float_bundle.NATIVE_CALLS if row['kind']=='actual-in-process-CLI']}
pathlib.Path(sys.argv[3]).write_text(json.dumps(value,indent=2)+'\\n',encoding='utf8')
raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
'''
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision',required=True);args=parser.parse_args()
    path=REL/('kernel-'+args.revision+'.json');child=path.with_suffix('.child.json');log=path.with_suffix('.log')
    assert not any(p.exists() for p in (path,child,log))
    command=[sys.executable,'-E','-B','-X','utf8','-c',BOOTSTRAP,str(ROOT/'product/src'),str(ROOT/'product/tests'),str(child)]
    before=frozen();assert len(before)==282
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,
        'script_sha256':sha(Path(__file__)),'command':command,'native_windows':True,'virtualization':False,'network':False,
        'editor_integrated':False,'HDR_accepted':False,'full_capcut_parity':False}
    def save():path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save();temp=str(ROOT/'product/.runtime/temp')
    env=dict(os.environ,TEMP=temp,TMP=temp,TMPDIR=temp,PYTHONDONTWRITEBYTECODE='1')
    with log.open('xb') as stream:
        process=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    result=json.loads(child.read_bytes()) if child.exists() else {}
    record.update(exit_code=process.returncode,result=result,frozen_after=frozen(),finished_at_utc=datetime.now(timezone.utc).isoformat(),log_sha256=sha(log))
    record['source_unchanged']=record['frozen_before']==record['frozen_after']
    record['status']='passed-native-float-kernel-unit-only' if process.returncode==0 and result.get('terminal_success') and not result.get('skipped') and record['source_unchanged'] else 'failed-preserved'
    save();path.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':record['status'],'methods':result.get('methods'),'failures':result.get('failures'),
        'errors':result.get('errors'),'skipped':result.get('skipped'),'native_calls':len(result.get('native_calls',[]))}))
    return 0 if record['status']=='passed-native-float-kernel-unit-only' else 1

if __name__=='__main__':raise SystemExit(main())
