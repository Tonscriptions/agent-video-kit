"""Build without downloads; exercise source transitions from an isolated wheel."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def run(work, project):
    work.mkdir(parents=True,exist_ok=False)
    runtime=ROOT/'product/.runtime/temp'
    env=dict(os.environ)
    env.update(TEMP=str(runtime),TMP=str(runtime),TMPDIR=str(runtime),PYTHONDONTWRITEBYTECODE='1',
               PIP_CACHE_DIR=str(ROOT/'product/.runtime/cache/pip'))
    cmd=[sys.executable,'-B','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation',
         str(ROOT/'product'),'--wheel-dir',str(work/'dist')]
    r=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True)
    (work/'build.stdout.log').write_bytes(r.stdout);(work/'build.stderr.log').write_bytes(r.stderr)
    assert r.returncode==0,(r.stdout,r.stderr)
    wheel=next((work/'dist').glob('*.whl'))
    site=work/'isolated-site';site.mkdir()
    file_records={}
    with zipfile.ZipFile(wheel) as z:
        for item in z.infolist():
            target=(site/item.filename).resolve()
            assert target.is_relative_to(site.resolve())
            if item.is_dir():continue
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(item))
            if item.filename.startswith('ai_ad_editor/'):
                original=ROOT/'product/src'/item.filename
                assert original.is_file() and target.read_bytes()==original.read_bytes(),item.filename
                file_records[item.filename]={'bytes':target.stat().st_size,'sha256':sha(target)}
    assert 'ai_ad_editor/source_transitions.py' in file_records
    assert (site/'ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()==(ROOT/'sources/upstream/openfilm/LICENSE').read_bytes()
    copy=work/'project'
    shutil.copytree(project,copy)
    before=json.loads((copy/'project.json').read_text(encoding='utf-8'))
    request=work/'request.json'
    save(request,{'action':'add','id':'isolated_tr','from_clip_id':'video_a_clip','to_clip_id':'video_b_clip','duration_tick':90000})
    bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    calls=[]
    def cli(*args):
        command=[sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(site),*map(str,args)]
        start=time.monotonic();r=subprocess.run(command,cwd=work,env=env,capture_output=True,timeout=300)
        index=len(calls)
        (work/f'{index:02}.stdout.log').write_bytes(r.stdout);(work/f'{index:02}.stderr.log').write_bytes(r.stderr)
        value=json.loads(r.stdout.decode('utf-8-sig')) if r.stdout.strip().startswith(b'{') else {'help':r.stdout.decode('utf-8','replace')}
        calls.append({'args':list(map(str,args)),'exit_code':r.returncode,'seconds':time.monotonic()-start,
                      'stdout_sha256':'sha256:'+hashlib.sha256(r.stdout).hexdigest(),
                      'stderr_sha256':'sha256:'+hashlib.sha256(r.stderr).hexdigest()})
        assert r.returncode==0,value
        return value
    cli('version');cli('capabilities');cli('timeline','transition','--help')
    dry=cli('timeline','transition','--project',copy,'--input',request,'--dry-run')
    cli('timeline','transition','--project',copy,'--input',request,'--expected-project-sha256',dry['data']['plan']['project_sha256'])
    rendered=cli('render','--project',copy,'--output',copy/'renders/isolated.mkv','--container','mkv',
                 '--crf',0,'--pixel-format','yuv444p','--audio-codec','pcm_f32le','--publish')
    save(request,{'action':'remove','id':'isolated_tr'})
    cli('timeline','transition','--project',copy,'--input',request)
    report=cli('validate','--project',copy,'--strict-rights')
    after=json.loads((copy/'project.json').read_text(encoding='utf-8'))
    assert before['sequences']==after['sequences']
    record={'wheel':{'filename':wheel.name,'bytes':wheel.stat().st_size,'sha256':sha(wheel)},
            'source_files':file_records,'file_count':len(file_records),'source_bytes_exact':True,
            'license_bytes_exact':True,'calls':calls,'restored_authored_sequences':True,
            'schema_engine':report['data']['validation']['schema_engine'] if 'validation' in report.get('data',{}) else report['data'].get('schema_engine'),
            'final_validation_response':report,'dry_run_response':dry,'render_response':rendered,
            'clean_machine_or_bundled_schema_accepted':False}
    save(work/'verification.json',record)
    print(json.dumps({'file_count':len(file_records),'cli_count':len(calls),'source_bytes_exact':True,'restored_authored_sequences':True},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--project',type=Path,required=True)
    args=p.parse_args();run(args.work.resolve(),args.project.resolve())
