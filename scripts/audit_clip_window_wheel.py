"""Offline wheel/source equality and isolated native presentation cut smoke."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,site,subprocess,sys,time,zipfile
from pathlib import Path
from smoke_fragments import sha,save,frozen

ROOT=Path(__file__).resolve().parents[1]
def run(work,source_work):
    work.mkdir(parents=True,exist_ok=False);before=frozen()
    env=dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
        TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1',
        PIP_CACHE_DIR=str(ROOT/'product/.runtime/cache/pip'),AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    build=subprocess.run([sys.executable,'-B','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation',
        str(ROOT/'product'),'--wheel-dir',str(work/'dist')],cwd=ROOT,env=env,capture_output=True,timeout=300)
    (work/'build.stdout.log').write_bytes(build.stdout);(work/'build.stderr.log').write_bytes(build.stderr)
    assert build.returncode==0,(build.stdout,build.stderr)
    wheel=next((work/'dist').glob('*.whl'));isolated=work/'isolated-site';isolated.mkdir();files={}
    with zipfile.ZipFile(wheel) as z:
        for item in z.infolist():
            if item.is_dir():continue
            path=(isolated/item.filename).resolve();assert path.is_relative_to(isolated.resolve())
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(item))
            if item.filename.startswith('ai_ad_editor/'):
                assert path.read_bytes()==(ROOT/'product/src'/item.filename).read_bytes(),item.filename
                files[item.filename]={'sha256':sha(path),'bytes':path.stat().st_size}
    assert 'ai_ad_editor/clip_windows.py' in files
    optional=site.getusersitepackages()
    bootstrap=('import sys;from pathlib import Path;optional=sys.argv.pop(1);package=sys.argv.pop(1);'
        'sys.path.insert(0,optional);sys.path.insert(0,package);from ai_ad_editor.cli import main;code=main();'
        'assert all(Path(m.__file__).resolve().is_relative_to(Path(package).resolve()) for n,m in tuple(sys.modules.items()) '
        'if n.startswith("ai_ad_editor") and getattr(m,"__file__",None));raise SystemExit(code)')
    calls=[]
    def cli(*args):
        start=time.monotonic()
        result=subprocess.run([sys.executable,'-I','-B','-X','utf8','-c',bootstrap,optional,str(isolated),*map(str,args)],
            cwd=work,env=env,capture_output=True,timeout=300)
        index=len(calls)
        (work/f'{index:02}.stdout.log').write_bytes(result.stdout);(work/f'{index:02}.stderr.log').write_bytes(result.stderr)
        value=json.loads(result.stdout.decode('utf-8-sig')) if result.stdout.strip().startswith(b'{') else {'help':result.stdout.decode('utf-8','replace')}
        calls.append({'index':index,'args':list(map(str,args)),'exit_code':result.returncode,'seconds':time.monotonic()-start,
            'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest()})
        assert result.returncode==0,value
        return value
    public=ROOT/'docs/assets/clip-windows-20261018'
    project=work/'project';shutil.copytree(source_work/'C02',project)
    cli('version');manifest=cli('capabilities');assert 'presentation_cuts' in manifest['data']['capabilities']
    cli('timeline','compose','--help')
    request=work/'split.json';save(request,{'operations':[{'op':'split_clip','clip_id':'v_after','at_tick':90000}]})
    original=(project/'project.json').read_bytes()
    cli('timeline','compose','--project',project,'--input',request,'--dry-run')
    assert (project/'project.json').read_bytes()==original
    cli('timeline','compose','--project',project,'--input',request,'--idempotency-key','wheel-cut')
    cli('timeline','compose','--project',project,'--input',request,'--idempotency-key','wheel-cut')
    cli('validate','--project',project,'--strict-rights')
    movie=project/'renders/isolated-cut.mkv'
    cli('render','--project',project,'--output',movie,'--container','mkv','--crf',0,
        '--pixel-format','yuv444p','--audio-codec','pcm_f32le','--publish')
    expected=json.loads((public/'C02-verification.json').read_text(encoding='utf-8'));decoded={}
    for kind,flags in [('rgb',['-an','-pix_fmt','rgb24','-f','rawvideo']),('pcm',['-vn','-ar','48000','-ac','2','-f','f32le'])]:
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(movie),*flags,'pipe:1'])
        decoded[kind+'_sha256']='sha256:'+hashlib.sha256(raw).hexdigest()
        assert decoded[kind+'_sha256']==expected[kind+'_sha256']
    save(request,{'id':'wheel-window','version':1,'sequence_id':'seq_main','clip_ids':['v']})
    library=work/'library'
    cli('fragment','save','--project',project,'--library',library,'--input',request)
    cli('fragment','inspect','--library',library,'--id','wheel-window','--version',1)
    result={'status':'passed','source_files':files,'file_count':len(files),'source_bytes_exact':True,
        'wheel':{'filename':wheel.name,'bytes':wheel.stat().st_size,'sha256':sha(wheel)},'calls':calls,
        'isolated_product_imports':True,'existing_optional_dependency_site':optional,'decoded_matches_public_C02':decoded,
        'frozen_before':before,'frozen_after':frozen(),'frozen_equal':before==frozen(),
        'clean_machine_or_bundled_schema_accepted':False}
    assert result['frozen_equal'];save(work/'verification.json',result)
    print(json.dumps({'file_count':len(files),'cli_count':len(calls),'status':'passed'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--source-work',type=Path,required=True)
    a=p.parse_args();run(a.work.resolve(),a.source_work.resolve())
