"""Retain exact native failure causes omitted by unittest's AppError string."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests'),str(ROOT/'scripts')]
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor import reverse_cache
from ai_ad_editor.errors import AppError
from run_frozen_regression import frozen
import test_reverse_cache as tests

def main():
    p=ROOT/'docs/validation/evidence/vfr-reverse-chunks-20261021-v82/probe-failure-r1.json'
    assert not p.exists()
    temporary=ROOT/'product/.runtime/temp';temporary.mkdir(parents=True,exist_ok=True)
    os.environ.update(TEMP=str(temporary),TMP=str(temporary),TMPDIR=str(temporary))
    configure_local_runtime();before=frozen();case=tests.ReverseChunkTests();case.setUp()
    calls=[];real=reverse_cache._capture
    def capture(command,**kw):
        entry={'command':list(map(str,command))};calls.append(entry)
        try:return real(command,**kw)
        except AppError as error:entry['error']=error.as_dict();raise
    reverse_cache._capture=capture
    value={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,'calls':calls}
    try:
        source,_,_=case.source();job=case.job(source);value['job']=job
        value['result']=case.execute(job)
    except AppError as error:
        value['error']=error.as_dict()
    finally:
        reverse_cache._capture=real;case.doCleanups();value['frozen_after']=frozen()
        p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(value.get('error',value.get('result')),ensure_ascii=False))

if __name__=='__main__':main()
