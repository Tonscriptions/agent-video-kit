"""Bind the actual twelve-before/after and34-related results to current packaging bytes."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/offline-media-profile-20261021-lab'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    output=REL/'development-audit-r1.json';assert not output.exists();current=frozen()
    before=json.loads((REL/'before-r1.json').read_bytes());after=json.loads((REL/'after-r1.json').read_bytes())
    related=json.loads((REL/'related-offline-r1.json').read_bytes());parent=json.loads((REL/'foundation-r1.json').read_bytes())['source_inputs']
    assert len(current)==260 and len(parent)==259
    assert current==after['frozen_before']==after['frozen_after']==related['frozen_before']==related['frozen_after']
    modified={'product/offline/build.py','product/offline/install.py','product/pyproject.toml'}
    added={'product/tests/test_offline_media_profile.py'}
    assert set(current)-set(parent)==added and {n for n in parent if parent[n]!=current[n]}==modified
    assert before['methods']==after['methods']==12 and before['exit_code']==1 and not before['terminal_ok']
    assert before['frozen_equal'] and before['skipped']==0
    log=(REL/'before-r1.log').read_text('utf8')
    assert len(re.findall(r'^FAIL:',log,re.M))==6 and len(re.findall(r'^ERROR:',log,re.M))==1
    for row,methods,name in ((after,12,'after-r1'),(related,34,'related-offline-r1')):
        assert row['methods']==methods and row['terminal_ok'] and row['exit_code']==0 and row['frozen_equal'] and row['skipped']==0
        assert sha(REL/(name+'.log'))==row['log_sha256']
    for name in added|{'scripts/run_frozen_regression.py'}:
        assert sha(ROOT/name)==sha(REL/'before-inputs-r1'/name)
    wheelhouse=json.loads((REL/'wheelhouse-r1.json').read_bytes())
    base=ROOT/wheelhouse['wheelhouse'];assert sha(base/'lock.json')==wheelhouse['lock_sha256']
    lock=json.loads((base/'lock.json').read_bytes());assert lock['runtime_profile']=='media-analysis-v1'
    for row in lock['artifacts']:assert sha(base/row['filename'])==row['sha256'] and (base/row['filename']).stat().st_size==row['bytes']
    record={'status':'passed-development-audit-awaiting-actual-install','at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_inputs':current,'source_parent_inputs':parent,'modified_inputs':sorted(modified),'added_inputs':sorted(added),
        'new_methods':12,'before_failures':6,'before_errors':1,'before_passed_controls':5,
        'before_sha256':sha(REL/'before-r1.json'),'after_sha256':sha(REL/'after-r1.json'),
        'related_methods':34,'related_seconds':related['suite_seconds'],'related_sha256':sha(REL/'related-offline-r1.json'),
        'wheelhouse_sha256':sha(REL/'wheelhouse-r1.json'),'new_official_numpy_wheel_RECORD_files':932,
        'development_network_used_for_pinned_source_capture':True,'runtime_network':False,
        'full_suite_started':False,'expected_future_full_methods':2043,'expected_published_parent_methods':2031,
        'main_integrated':False,'skills_registered':False,'full_capcut_parity':False,'generator_sha256':sha(__file__)}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','new_methods','before_failures','before_errors','related_methods','expected_future_full_methods')}))


if __name__=='__main__':main()
