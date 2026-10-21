"""Record actual source-clock regressions with stable native fixtures and frozen inputs."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from run_frozen_regression import sha,frozen
ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/audio-discontinuity-20261021-lab'
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('before','after'),required=True)
    parser.add_argument('--revision',default='r1');args=parser.parse_args()
    output=REL/(args.phase+'-'+args.revision+'.json');log=output.with_suffix('.log')
    assert not output.exists() and not log.exists()
    current=frozen();manifest=REL/'original-r1/source-manifest.json'
    assert json.loads(manifest.read_bytes())['status']=='passed-original-native-packet-clocks'
    bootstrap=('import sys,unittest;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];'
        'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
        'sys.argv=[sys.argv[0],"-v","test_audio_discontinuity"];unittest.main(module=None)')
    command=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,str(ROOT/'product/src'),str(ROOT/'product/tests')]
    temp=str(ROOT/'product/.runtime/temp')
    env=dict(os.environ,TEMP=temp,TMP=temp,TMPDIR=temp,PYTHONDONTWRITEBYTECODE='1',AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES=str(manifest))
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'phase':args.phase,
        'command':command,'frozen_before':current,'fixture_manifest_sha256':sha(manifest),'script_sha256':sha(Path(__file__)),
        'native_windows':True,'virtualization':False,'network':False,'expected_methods':13}
    def save():output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save();output.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
    with log.open('xb') as stream:r=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    text=log.read_text('utf8');match=re.search(r'Ran (\d+) tests in ([\d.]+)s',text)
    record.update(exit_code=r.returncode,methods=int(match[1]) if match else None,suite_seconds=float(match[2]) if match else None,
        failures=len(re.findall(r'^FAIL:',text,re.M)),errors=len(re.findall(r'^ERROR:',text,re.M)),
        skipped=len(re.findall(r'\.\.\. skipped ',text)),terminal_ok=bool(re.search(r'\bOK\s*$',text)),frozen_after=frozen(),
        log_sha256=sha(log),fixture_manifest_unchanged=sha(manifest)==record['fixture_manifest_sha256'],finished_at_utc=datetime.now(timezone.utc).isoformat())
    record['source_unchanged']=current==record['frozen_after']
    record['status']='passed' if r.returncode==0 and record['terminal_ok'] and record['methods']==13 and record['source_unchanged'] else 'failed'
    save();print(json.dumps({k:record[k] for k in ('status','phase','methods','suite_seconds','failures','errors','skipped')}))
    return 0 if args.phase=='before' and record['source_unchanged'] and record['methods']==13 else (0 if record['status']=='passed' else 1)
if __name__=='__main__':raise SystemExit(main())
