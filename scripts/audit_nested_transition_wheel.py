"""Offline wheel bytes and isolated native CLI checks for nested transitions."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,sys,time,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path):return digest(path.read_bytes())
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def run(work,project):
    work.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
               TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1',
               PIP_CACHE_DIR=str(ROOT/'product/.runtime/cache/pip'))
    command=[sys.executable,'-B','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation',
             str(ROOT/'product'),'--wheel-dir',str(work/'dist')]
    result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=300)
    (work/'build.stdout.log').write_bytes(result.stdout);(work/'build.stderr.log').write_bytes(result.stderr)
    assert result.returncode==0,(result.stdout,result.stderr)
    wheel=next((work/'dist').glob('*.whl'));site=work/'isolated-site';site.mkdir()
    files={}
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.infolist():
            target=(site/item.filename).resolve();assert target.is_relative_to(site.resolve())
            if item.is_dir():continue
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(item))
            if item.filename.startswith('ai_ad_editor/'):
                original=ROOT/'product/src'/item.filename
                assert original.is_file() and target.read_bytes()==original.read_bytes(),item.filename
                files[item.filename]={'bytes':target.stat().st_size,'sha256':sha(target)}
    assert 'ai_ad_editor/inline_sequences.py' in files
    assert (site/'ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()==(ROOT/'sources/upstream/openfilm/LICENSE').read_bytes()
    copied=work/'project';shutil.copytree(project,copied)
    before=json.loads((copied/'project.json').read_text(encoding='utf-8'))
    bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    calls=[]
    def cli(*args):
        start=time.monotonic()
        r=subprocess.run([sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(site),*map(str,args)],
                         cwd=work,env=env,capture_output=True,timeout=300)
        index=len(calls)
        (work/f'{index:02}.stdout.log').write_bytes(r.stdout);(work/f'{index:02}.stderr.log').write_bytes(r.stderr)
        value=json.loads(r.stdout.decode('utf-8-sig')) if r.stdout.strip().startswith(b'{') else {'help':r.stdout.decode('utf-8','replace')}
        calls.append({'index':index,'args':list(map(str,args)),'exit_code':r.returncode,'seconds':time.monotonic()-start,
                      'stdout_sha256':digest(r.stdout),'stderr_sha256':digest(r.stderr)})
        assert r.returncode==0,value
        return value
    cli('version');cli('capabilities');cli('timeline','transition','--help')
    plan=cli('render','--project',copied,'--dry-run')
    output=copied/'renders/isolated-nested.mkv'
    rendered=cli('render','--project',copied,'--output',output,'--container','mkv','--crf',0,
                 '--pixel-format','yuv444p','--audio-codec','pcm_f32le','--publish')
    cli('validate','--project',copied,'--strict-rights')
    request=work/'request.json';save(request,{'action':'resize','id':'tr_bc','duration_tick':135000})
    dry=cli('timeline','transition','--project',copied,'--sequence-id','child','--input',request,'--dry-run')
    cli('timeline','transition','--project',copied,'--sequence-id','child','--input',request,
        '--expected-project-sha256',dry['data']['plan']['project_sha256'])
    save(request,{'action':'remove','id':'tr_bc'})
    cli('timeline','transition','--project',copied,'--sequence-id','child','--input',request)
    original=next(s for s in before['sequences'] if s['id']=='child')['source_transitions'][-1]
    restored={k:original[k] for k in ('id','from_clip_id','to_clip_id','type','duration_tick')}
    restored.update(action='add',audio='linked');save(request,restored)
    cli('timeline','transition','--project',copied,'--sequence-id','child','--input',request)
    validated=cli('validate','--project',copied,'--strict-rights')
    after=json.loads((copied/'project.json').read_text(encoding='utf-8'))
    # Re-add the last declaration in its original order; compare all authorship.
    assert before['sequences']==after['sequences']
    manifest_path=Path(rendered['data']['manifest']);manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    surfaces=[m for m in manifest['inputs'] if m.get('kind')=='sequence-inline-surface']
    assert surfaces and all(s['intermediate_files']==0 for s in surfaces)
    shutil.copyfile(manifest_path,work/'render-manifest.json')
    expected=json.loads((ROOT/'docs/assets/nested-transitions-20261018/C01-verification.json').read_text(encoding='utf-8'))
    decoded={}
    for kind,args in (('rgb',['-an','-pix_fmt','rgb24','-f','rawvideo']),('pcm',['-vn','-ar','48000','-ac','2','-f','f32le'])):
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(output),*args,'pipe:1'])
        decoded[kind+'_sha256']=digest(raw);assert decoded[kind+'_sha256']==expected[kind+'_sha256']
    record={'wheel':{'filename':wheel.name,'bytes':wheel.stat().st_size,'sha256':sha(wheel)},
            'source_files':files,'file_count':len(files),'source_bytes_exact':True,'license_bytes_exact':True,
            'calls':calls,'render_response':rendered,'render_dry_run_response':plan,'resize_dry_run_response':dry,
            'restored_authored_sequences':True,'nested_surface_count':len(surfaces),'intermediate_files':0,
            'decoded_matches_public_C01':decoded,'final_validation_response':validated,
            'clean_machine_or_bundled_schema_accepted':False}
    save(work/'verification.json',record)
    print(json.dumps({'file_count':len(files),'cli_count':len(calls),'source_bytes_exact':True,
                      'restored_authored_sequences':True,'decoded_matches_public_C01':True}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--project',type=Path,required=True)
    args=parser.parse_args();run(args.work.resolve(),args.project.resolve())
