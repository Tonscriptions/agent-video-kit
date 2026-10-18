"""Run the same final compound-freeze checks against the fixed V50 source."""
import argparse,hashlib,io,json,os,re,subprocess,sys,time,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE='79deb231fe92f61ed4e7644b2ccd1361129ae2bd'


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()


def run(output,work):
    output.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    data=subprocess.check_output(['git','archive','--format=zip',BASE,'product/src','docs/specs/agent-project.schema.json'],cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for item in archive.infolist():
            p=(work/item.filename).resolve();assert p.is_relative_to(work)
            if item.is_dir():continue
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.read(item))
    test=ROOT/'product/tests/test_nested_freeze.py'
    before=sha(test)
    env=dict(os.environ);env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
        TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1')
    bootstrap='import sys,unittest;sys.path[:0]=[sys.argv.pop(1),sys.argv.pop(1)];from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();unittest.main(module=None)'
    command=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,str(work/'product/src'),str(ROOT/'product/tests'),
             'discover','-s',str(ROOT/'product/tests'),'-p','test_nested_freeze.py','-v']
    start=time.monotonic()
    with (output/'baseline.log').open('wb') as f:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=360)
    log=(output/'baseline.log').read_text(encoding='utf-8')
    match=re.search(r'Ran (\d+) tests in ([\d.]+)s',log)
    failures=re.findall(r'^FAIL: (\w+)',log,re.M);errors=re.findall(r'^ERROR: (\w+)',log,re.M)
    assert match and result.returncode==1 and not errors and sha(test)==before
    required={'test_middle_freeze_has_exact_frame_identity_before_during_after',
              'test_child_transition_midpoint_is_held_then_progress_resumes',
              'test_transparent_native_child_hold_preserves_every_alpha_pixel'}
    assert required.issubset(failures),failures
    record={'status':'verified_counterfactual_failures','base_commit':BASE,'command':command,
        'exit_code':result.returncode,'methods':int(match[1]),'suite_seconds':float(match[2]),
        'failed_methods':failures,'error_methods':errors,'control_passed_methods':int(match[1])-len(failures),
        'same_current_test_sha256':before,'log_sha256':sha(output/'baseline.log'),
        'source_files':{p.relative_to(work).as_posix():sha(p) for p in sorted((work/'product/src').rglob('*')) if p.is_file()},
        'wall_seconds':time.monotonic()-start,'generator_sha256':sha(Path(__file__))}
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    (output/'verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','methods','control_passed_methods','failed_methods')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();run(a.output.resolve(),a.work.resolve())
