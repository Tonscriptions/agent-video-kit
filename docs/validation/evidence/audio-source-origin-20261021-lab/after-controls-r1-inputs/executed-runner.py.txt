"""Freeze and preserve the same twelve real native audio-origin controls before/after a change."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/audio-source-origin-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',required=True);parser.add_argument('--rubberband',type=Path,required=True)
    parser.add_argument('--expect-failure',action='store_true');args=parser.parse_args()
    assert re.fullmatch('[a-z0-9-]+',args.attempt)
    output=REL/(args.attempt+'.json');log=REL/(args.attempt+'.log');snapshots=REL/(args.attempt+'-inputs')
    assert not output.exists() and not log.exists() and not snapshots.exists();snapshots.mkdir(parents=True)
    before=frozen();own_sha=sha(__file__)
    assert len(before)==259
    source_names=['product/src/ai_ad_editor/'+name+'.py' for name in ('multicam','render','audio_stretch','capabilities')]
    source_names+=['product/tests/test_audio_source_origin.py']
    pinned={}
    for name in source_names:
        source=ROOT/name;target=snapshots/Path(name).name;target.write_bytes(source.read_bytes());pinned[name]=sha(source)
    (snapshots/'executed-runner.py.txt').write_bytes(Path(__file__).read_bytes())
    env=dict(os.environ);temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1',
        AI_AD_EDITOR_TEST_RUBBERBAND=str(args.rubberband.resolve(strict=True)))
    code="import sys,unittest;sys.path[:0]=sys.argv[1:3];unittest.main(module=None,argv=['unittest','-v',sys.argv[3]])"
    command=[sys.executable,'-E','-B','-X','utf8','-c',code,str(ROOT/'product/src'),str(ROOT/'product/tests'),'test_audio_source_origin']
    started=datetime.now(timezone.utc).isoformat()
    with log.open('xb') as stream:result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
    text=log.read_text('utf8',errors='replace');match=re.search(r'Ran (\d+) tests? in ([0-9.]+)s',text);assert match,text[-2500:]
    ids=re.findall(r'^(test_\S+) \(([^)]+)\) \.\.\.',text,re.M)
    failed=len(re.findall(r'\.\.\. FAIL\r?\n',text));errors=len(re.findall(r'\.\.\. ERROR\r?\n',text))
    skipped=len(re.findall(r'\.\.\. skipped ',text));terminal=bool(re.search(r'\nOK\s*$',text))
    after=frozen();assert before==after and sha(__file__)==own_sha
    assert int(match[1])==12 and len(ids)==len(set(ids))==12 and skipped==0
    accepted=(result.returncode!=0 and not terminal and failed+errors>0) if args.expect_failure else (result.returncode==0 and terminal)
    record={'status':('expected-pre-fix-failure-observed' if args.expect_failure else 'passed') if accepted else 'unexpected-result',
        'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),'expected_failure':args.expect_failure,
        'command':command,'exit_code':result.returncode,'terminal_ok':terminal,'methods':12,'suite_seconds':float(match[2]),
        'failed_methods':failed,'error_methods':errors,'skipped':skipped,'method_ids':ids,'distinct_methods':len(set(ids)),
        'frozen_before':before,'frozen_after':after,'frozen_equal':before==after,'source_snapshots':pinned,
        'log_sha256':sha(log),'rubberband_sha256':sha(args.rubberband),'runner_sha256':own_sha,
        'native_windows':True,'virtualization':False,'network':False,'main_integrated':False,'full_capcut_parity':False}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','methods','suite_seconds','failed_methods','error_methods','skipped','frozen_equal')}))
    assert accepted,text[-3500:]


if __name__=='__main__':main()
