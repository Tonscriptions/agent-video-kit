"""Offline wheel build; fresh-process CLIs exercise the preserved HTML source."""
from __future__ import annotations
import argparse,json,os,site,subprocess,sys,time,zipfile
from pathlib import Path
from smoke_fragments import frozen,save,sha

ROOT=Path(__file__).resolve().parents[1]


def run(work,public,runtime):
    work.mkdir(parents=True,exist_ok=False);before=frozen()
    env=dict(os.environ);env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
        TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1',
        AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'),PIP_CACHE_DIR=str(ROOT/'product/.runtime/cache/pip'))
    result=subprocess.run([sys.executable,'-B','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation',str(ROOT/'product'),
        '--wheel-dir',str(work/'dist')],env=env,capture_output=True,timeout=300)
    (work/'build.stdout.log').write_bytes(result.stdout);(work/'build.stderr.log').write_bytes(result.stderr)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    wheel=next((work/'dist').glob('*.whl'));installed=work/'isolated-site';installed.mkdir()
    files={}
    with zipfile.ZipFile(wheel) as archive:
        for entry in archive.infolist():
            if entry.is_dir():continue
            path=(installed/entry.filename).resolve();assert path.is_relative_to(installed.resolve())
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(entry))
            if entry.filename.startswith('ai_ad_editor/'):
                assert path.read_bytes()==(ROOT/'product/src'/entry.filename).read_bytes(),entry.filename
                files[entry.filename]={'sha256':sha(path),'bytes':path.stat().st_size}
    for name in ('html_motion.py','browser_process.py','html_motion_worker.mjs','openfilm_frame_clock.mjs','OPENFILM_LICENSE.txt'):
        assert 'ai_ad_editor/'+name in files
    optional=site.getusersitepackages()
    boot=('import sys;from pathlib import Path;optional=sys.argv.pop(1);package=sys.argv.pop(1);'
          'sys.path.insert(0,optional);sys.path.insert(0,package);'
          'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
          'from ai_ad_editor.cli import main;code=main();'
          'assert all(Path(m.__file__).resolve().is_relative_to(Path(package).resolve()) '
          'for n,m in tuple(sys.modules.items()) if n.startswith("ai_ad_editor") and getattr(m,"__file__",None));'
          'raise SystemExit(code)')
    calls=[]
    def cli(*args,expected=0):
        start=time.monotonic()
        value=subprocess.run([sys.executable,'-I','-B','-X','utf8','-c',boot,optional,str(installed),*map(str,args)],
            cwd=work,env=env,capture_output=True,timeout=300)
        number=len(calls)+1
        (work/f'{number:02}.stdout.log').write_bytes(value.stdout);(work/f'{number:02}.stderr.log').write_bytes(value.stderr)
        record={'number':number,'args':list(map(str,args)),'exit_code':value.returncode,'seconds':time.monotonic()-start};calls.append(record)
        assert value.returncode==expected,(record,value.stdout.decode(errors='replace'),value.stderr.decode(errors='replace'))
        return json.loads(value.stdout)
    cli('version')
    assert cli('capabilities')['data']['capabilities']['html_motion']['engine']=='agent-local-html-motion-v1'
    project=work/'restored'
    cli('convert','import','--input',public/'editable-project.zip','--output',project)
    cli('motion','html-register','--project',project,'--input',runtime)
    cli('motion','html-inspect','--project',project,'--source-asset-id','editable')
    args=('motion','html-render','--project',project,'--from-asset-id','orange','--asset-id','wheel-orange')
    plan=cli(*args,'--dry-run')['data']['plan']
    first=cli(*args,'--expected-project-sha256',plan['project_sha256'],'--idempotency-key','wheel-orange')
    replay=cli(*args,'--expected-project-sha256',plan['project_sha256'],'--idempotency-key','wheel-orange')
    assert first['data']['asset']['sha256']==replay['data']['asset']['sha256']
    second=cli('motion','html-render','--project',project,'--from-asset-id','orange','--asset-id','wheel-blue','--params',public/'parameters.json')
    cli('policy','audit','--project',project)
    cli('rights','check','--project',project,expected=7)
    # Use a fresh interpreter for independent package-owned decoding paths too.
    decode_boot=('import subprocess,sys;from pathlib import Path;sys.path.insert(0,sys.argv.pop(1));'
        'from ai_ad_editor.media import ffmpeg_path;'
        'out=subprocess.check_output([ffmpeg_path(),"-v","error","-i",sys.argv[1],"-an","-pix_fmt","rgba","-f","rawvideo","pipe:1"]);'
        'Path(sys.argv[2]).write_bytes(out)')
    decoded=[]
    for key,value in [('S01',first),('S02',second)]:
        observed=work/(key+'.rgba');reference=work/(key+'-reference.rgba')
        for source,target in [(project/value['data']['asset']['uri'],observed),(public/(key+'-alpha.nut'),reference)]:
            subprocess.run([sys.executable,'-I','-B','-X','utf8','-c',decode_boot,str(installed),str(source),str(target)],
                           cwd=work,env=env,check=True,timeout=60)
        assert observed.read_bytes()==reference.read_bytes()
        decoded.append({'case':key,'frames':24,'rgba_bytes':observed.stat().st_size,'rgba_sha256':sha(observed)})
    report_path=Path(first['data']['report']);report=json.loads(report_path.read_text(encoding='utf-8'))
    assert report['cleanup']['all_children_reaped'] and report['encoded_clock']['all_frames_exact']
    assert frozen()==before,'product changed during wheel verification'
    record={'status':'passed','source_frozen_equal':True,'source_before':before,'source_after':frozen(),
        'wheel':str(wheel),'wheel_sha256':sha(wheel),'package_files':files,'package_file_count':len(files),
        'actual_fresh_process_clis':len(calls),'calls':calls,'decoded':decoded,
        'node_playwright_chromium':'explicit existing local toolchain, not bundled or downloaded',
        'optional_python_dependencies':'existing local user-site libraries, not a clean-machine install',
        'schema_packaging':'existing standalone schema packaging gap remains; not claimed accepted',
        'generator_sha256':sha(Path(__file__))}
    save(work/'verification.json',record);print(json.dumps({k:record[k] for k in ('package_file_count','actual_fresh_process_clis','decoded')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--public',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,required=True);args=parser.parse_args();run(args.work.resolve(),args.public.resolve(),args.runtime.resolve())
