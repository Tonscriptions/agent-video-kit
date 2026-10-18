"""Offline wheel and fresh stdlib-host CLI/package/edited-plan verification."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from smoke_fragments import frozen,save,sha


def run(work,public):
    assert not work.exists();work.mkdir(parents=True);before=frozen()
    env=dict(os.environ);env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
        TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1',PIP_CACHE_DIR=str(ROOT/'product/.runtime/cache/pip'),
        AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'))
    built=subprocess.run([sys.executable,'-B','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation',
        str(ROOT/'product'),'--wheel-dir',str(work/'dist')],env=env,capture_output=True,timeout=300)
    (work/'build.stdout.log').write_bytes(built.stdout);(work/'build.stderr.log').write_bytes(built.stderr)
    assert built.returncode==0,built.stderr.decode(errors='replace')
    wheel=next((work/'dist').glob('*.whl'));installed=work/'isolated-site';installed.mkdir();files={}
    with zipfile.ZipFile(wheel) as archive:
        for entry in archive.infolist():
            if entry.is_dir():continue
            path=(installed/entry.filename).resolve();assert path.is_relative_to(installed.resolve())
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(entry))
            if entry.filename.startswith('ai_ad_editor/'):
                assert path.read_bytes()==(ROOT/'product/src'/entry.filename).read_bytes(),entry.filename
                files[entry.filename]={'sha256':sha(path),'bytes':path.stat().st_size}
    assert {'ai_ad_editor/mask_edit.py','ai_ad_editor/mask_edit_geometry.py'}<=set(files)
    boot='''import builtins,socket,sys
from pathlib import Path
original=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in {'numpy','PIL','torch'}: raise ImportError('optional module deliberately blocked')
    return original(name,*args,**kwargs)
builtins.__import__=guarded
def denied(*args,**kwargs): raise RuntimeError('wheel host network forbidden')
socket.create_connection=denied;socket.socket.connect=denied;socket.socket.connect_ex=denied
package=sys.argv.pop(1);sys.path.insert(0,package)
from ai_ad_editor.cli import main
code=main()
assert all(Path(m.__file__).resolve().is_relative_to(Path(package).resolve()) for n,m in tuple(sys.modules.items()) if n.startswith('ai_ad_editor') and getattr(m,'__file__',None))
raise SystemExit(code)'''
    calls=[]
    def cli(*args,expected=0):
        started=time.monotonic()
        result=subprocess.run([sys.executable,'-I','-B','-X','utf8','-c',boot,str(installed),*map(str,args)],
            cwd=work,env=env,capture_output=True,timeout=180)
        number=len(calls)+1
        (work/f'{number:02}.stdout.log').write_bytes(result.stdout);(work/f'{number:02}.stderr.log').write_bytes(result.stderr)
        item={'number':number,'args':list(map(str,args)),'exit_code':result.returncode,'seconds':time.monotonic()-started};calls.append(item)
        assert result.returncode==expected,(item,result.stdout.decode(errors='replace'),result.stderr.decode(errors='replace'))
        return json.loads(result.stdout)
    cli('version');assert cli('capabilities')['data']['capabilities']['mask_edit']['engine']=='agent-local-mask-edit-v1'
    project=work/'restored';cli('convert','import','--input',public/'editable-project.zip','--output',project)
    args=('media','mask-edit','--project',project,'--asset-id','mask','--derived-asset-id','rebuilt','--edits-from-asset','edited')
    cli(*args,'--dry-run');first=cli(*args,'--idempotency-key','wheel-rebuild')
    replay=cli(*args,'--idempotency-key','wheel-rebuild');assert first['data']['asset']['sha256']==replay['data']['asset']['sha256']
    def native(argv):
        result=subprocess.run(argv,capture_output=True,env=env,timeout=90);assert result.returncode==0,result.stderr
        return result.stdout
    def decode(path):return native(['ffmpeg','-v','error','-i',str(path),'-an','-pix_fmt','rgba','-f','rawvideo','pipe:1'])
    observed=decode(project/first['data']['asset']['uri']);reference=decode(public/'independent-truth.mov')
    assert observed==reference
    document=json.loads((project/'project.json').read_text(encoding='utf-8'))
    plan=next(a for a in document['assets'] if a['id']=='edited')['source']['mask_edit']['plan']
    for op in plan['operations']:
        if op['id']=='arm':
            for k in op['keyframes']:k['radius_pixels']=6
    save(work/'wider-brush.json',plan)
    variant=cli('media','mask-edit','--project',project,'--asset-id','mask','--derived-asset-id','wider','--edits',work/'wider-brush.json')
    wider=decode(project/variant['data']['asset']['uri']);assert wider!=observed
    assert len(wider)==len(observed)==16*160*120*4
    assert all(new>=old for old,new in zip(observed[3::4],wider[3::4]))
    cli('validate','--project',project);cli('policy','audit','--project',project);cli('rights','check','--project',project)
    cli('convert','export','--project',project,'--target-format','package','--output',work/'revised-project.zip')
    assert before==frozen()
    logs={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(work.glob('*.log'))}
    record={'status':'passed','source_frozen_equal':True,'frozen_product':before,'wheel':str(wheel),'wheel_sha256':sha(wheel),
        'package_file_count':len(files),'package_files':files,'actual_fresh_process_clis':len(calls),'calls':calls,'logs':logs,
        'source_package':{'path':str(public/'editable-project.zip'),'sha256':sha(public/'editable-project.zip')},
        'revised_package':{'path':str(work/'revised-project.zip'),'sha256':sha(work/'revised-project.zip')},
        'decoded_rgba_bytes':len(observed),'decoded_rgba_sha256':'sha256:'+hashlib.sha256(observed).hexdigest(),
        'imported_plan_rebuild_exact':True,'wider_brush_new_version_changes_output':True,
        'host_optional_imports_blocked':['numpy','PIL','torch'],'external_runtime':'existing native FFmpeg/ffprobe, no downloads',
        'schema_packaging':'standalone schema is not bundled; existing workspace fallback remains; no clean-machine acceptance',
        'generator_sha256':sha(Path(__file__))}
    save(work/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('package_file_count','actual_fresh_process_clis','decoded_rgba_bytes','imported_plan_rebuild_exact')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--public',type=Path,required=True)
    args=parser.parse_args();run(args.work.resolve(),args.public.resolve())
