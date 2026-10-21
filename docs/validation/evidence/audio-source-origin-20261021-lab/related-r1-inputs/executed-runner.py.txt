"""Run distinct audio/clock/media controls with frozen source and explicit native tools."""
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


def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rubberband',type=Path,required=True)
    args=parser.parse_args();output=REL/'related-r1.json';log=REL/'related-r1.log';snapshots=REL/'related-r1-inputs'
    assert not output.exists() and not log.exists() and not snapshots.exists();snapshots.mkdir()
    parent_path=ROOT.parent/'multicam-stream-coverage-lab-20261021/docs/validation/evidence/multicam-stream-coverage-20261021-lab/related-r2.json'
    parent=json.loads(parent_path.read_bytes());assert parent['methods']==parent['distinct_methods']==104 and parent['terminal_ok']
    names=['test_audio_source_origin',*parent['selected_test_names'],'test_audio_unity','test_audio_tempo_context',
        'test_audio_source_context','test_audio_channel_modes','test_audio_routing','test_audio_buses','test_audio_stretch']
    before=frozen();assert len(before)==259
    foundation_path=REL/'foundation-r1.json';foundation=json.loads(foundation_path.read_bytes())
    fixtures={r['path']:r['sha256'] for r in foundation['external_fixtures']};assert len(fixtures)==8
    assert all(sha(ROOT/name)==digest for name,digest in fixtures.items())
    scripts={name:sha(ROOT/'scripts'/name) for name in ('run_audio_origin_related.py','run_audio_origin_regressions.py',
        'probe_audio_source_origin.py','run_frozen_regression.py','prepare_audio_origin_lab.py','materialize_regression_fixtures.py')}
    source_names=['product/src/ai_ad_editor/'+name+'.py' for name in ('multicam','render','audio_stretch','capabilities')]
    source_names+=['product/tests/test_audio_source_origin.py']
    for name in source_names:(snapshots/Path(name).name).write_bytes((ROOT/name).read_bytes())
    (snapshots/'executed-runner.py.txt').write_bytes(Path(__file__).read_bytes())
    env=dict(os.environ);temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1',
        AI_AD_EDITOR_TEST_RUBBERBAND=str(args.rubberband.resolve(strict=True)))
    prefix=[sys.executable,'-E','-B','-X','utf8','-c']
    collect="import sys,json,unittest;sys.path[:0]=sys.argv[1:3];s=unittest.TestLoader().loadTestsFromNames(json.loads(sys.argv[3]));f=lambda s:[i for t in s for i in (f(t) if isinstance(t,unittest.TestSuite) else [t.id()])];print(json.dumps(f(s)))"
    arguments=[str(ROOT/'product/src'),str(ROOT/'product/tests'),json.dumps(names)]
    collected=subprocess.run([*prefix,collect,*arguments],env=env,cwd=ROOT,capture_output=True,timeout=60)
    assert collected.returncode==0,collected.stderr.decode('utf8','replace')
    ids=json.loads(collected.stdout);assert len(ids)==len(set(ids)) and len(ids)>=116
    assert not any('_FailedTest' in value for value in ids)
    record={'status':'running-related-regressions','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'selected_test_names':names,'expected_methods':len(ids),'expected_method_ids':ids,
        'parent_related_sha256':sha(parent_path),'frozen_before':before,'fixture_inputs':fixtures,
        'fixture_manifest_sha256':sha(foundation_path),'script_hashes':scripts,
        'rubberband_sha256':sha(args.rubberband),'native_windows':True,'virtualization':False,'network':False,
        'full_suite_started':False,'main_integrated':False,'full_capcut_parity':False}
    code="import sys,json,unittest;sys.path[:0]=sys.argv[1:3];unittest.main(module=None,argv=['unittest','-v',*json.loads(sys.argv[3])])"
    command=[*prefix,code,*arguments];record['command']=command;write(output,record)
    with log.open('xb') as stream:result=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=3600)
    text=log.read_text('utf8',errors='replace');match=re.search(r'Ran (\d+) tests? in ([0-9.]+)s',text)
    actual=re.findall(r'^test_\S+ \(([^)]+)\) \.\.\.',text,re.M)
    record.update(exit_code=result.returncode,terminal_ok=bool(re.search(r'\nOK\s*$',text)),
        methods=int(match[1]) if match else None,suite_seconds=float(match[2]) if match else None,
        skipped=len(re.findall(r'\.\.\. skipped ',text)),method_ids=actual,distinct_methods=len(set(actual)),
        frozen_after=frozen(),finished_at_utc=datetime.now(timezone.utc).isoformat(),log_sha256=sha(log))
    record.update(frozen_equal=before==record['frozen_after'],
        fixtures_unchanged=all(sha(ROOT/name)==digest for name,digest in fixtures.items()),
        fixture_manifest_unchanged=sha(foundation_path)==record['fixture_manifest_sha256'],
        scripts_unchanged=all(sha(ROOT/'scripts'/name)==digest for name,digest in scripts.items()))
    passed=result.returncode==0 and record['terminal_ok'] and record['skipped']==0 and record['methods']==len(ids)
    passed=passed and len(actual)==len(set(actual))==len(ids) and set(actual)==set(ids)
    passed=passed and all(record[k] for k in ('frozen_equal','fixtures_unchanged','fixture_manifest_unchanged','scripts_unchanged'))
    record['status']='passed-related-regressions' if passed else 'failed-related-regressions';write(output,record)
    print(json.dumps({k:record[k] for k in ('status','methods','suite_seconds','skipped','frozen_equal')}))
    assert passed,text[-3500:]


if __name__=='__main__':main()
