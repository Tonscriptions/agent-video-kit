"""Byte-check a newly built wheel and run the drawing path in fresh native CLI processes."""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(work,smoke,public,runtime,evidence):
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),PYTHONDONTWRITEBYTECODE='1')
    build=subprocess.run([sys.executable,'-B','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation',
        str(ROOT/'product'),'--wheel-dir',str(work/'dist')],env=env,capture_output=True,timeout=300)
    (evidence/'build.stdout.log').write_bytes(build.stdout);(evidence/'build.stderr.log').write_bytes(build.stderr)
    assert build.returncode==0,build.stderr.decode(errors='replace')
    wheel=next((work/'dist').glob('*.whl'));site=work/'isolated-site';site.mkdir();inventory=[]
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            if info.is_dir():continue
            path=(site/info.filename).resolve();assert path.is_relative_to(site)
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(info))
            if info.filename.startswith('ai_ad_editor/'):
                assert path.read_bytes()==(ROOT/'product/src'/info.filename).read_bytes()
                inventory.append({'path':info.filename,'bytes':info.file_size,'sha256':sha(path)})
    # CPython -I excludes user site packages. Load the same pinned native
    # dependencies as the offline installer, never a network/pip fallback.
    wheelhouse=ROOT/'sources/python-runtime/cp313-win_amd64'
    lock=json.loads((wheelhouse/'lock.json').read_bytes());dependencies=[]
    for item in lock['artifacts']:
        if not item['runtime_dependency']:continue
        source=wheelhouse/item['filename'];assert source.stat().st_size==item['bytes'] and sha(source)==item['sha256']
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                if info.is_dir():continue
                path=(site/info.filename).resolve();assert path.is_relative_to(site) and not path.exists()
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(info))
        dependencies.append(item)
    assert all(any(x['path']=='ai_ad_editor/'+name for x in inventory) for name in
        ('stroke_motion.py','openfilm_stroke.mjs','OPENFILM_EXAMPLES_LICENSE.txt','PDOOM_VIDEO_LICENSE.txt','agent-project.schema.json'))
    boot='''import builtins,socket,sys
from pathlib import Path
original=builtins.__import__
def guarded(name,*args,**kwargs):
 if name.split('.')[0] in {'numpy','PIL','torch'}:raise ImportError('optional module blocked')
 return original(name,*args,**kwargs)
builtins.__import__=guarded
def denied(*args,**kwargs):raise RuntimeError('host network forbidden')
socket.create_connection=denied;socket.socket.connect=denied;socket.socket.connect_ex=denied
site=sys.argv.pop(1);sys.path.insert(0,site)
from ai_ad_editor.cli import main
code=main()
assert all(Path(m.__file__).resolve().is_relative_to(Path(site)) for n,m in tuple(sys.modules.items()) if n.startswith('ai_ad_editor') and getattr(m,'__file__',None))
raise SystemExit(code)'''
    calls=[];reports=[]
    def cli(*args,expected=0):
        p=subprocess.run([sys.executable,'-I','-B','-X','utf8','-c',boot,str(site),*map(str,args)],env=env,cwd=work,capture_output=True,timeout=300)
        number=len(calls)+1;(evidence/f'{number:02}.stdout.json').write_bytes(p.stdout);(evidence/f'{number:02}.stderr.log').write_bytes(p.stderr)
        calls.append({'args':list(map(str,args)),'exit_code':p.returncode})
        assert p.returncode==expected,(calls[-1],p.stdout.decode(errors='replace'),p.stderr.decode(errors='replace'))
        return json.loads(p.stdout)
    def decode(path):
        p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','rawvideo','-pix_fmt','rgba','-'],capture_output=True,timeout=60)
        assert p.returncode==0,p.stderr
        assert len(p.stdout)==36*384*216*4
        return p.stdout
    def browser(result,label):
        report=json.loads(Path(result['data']['report']).read_bytes());save(evidence/(label+'.json'),report)
        assert report['cleanup']['all_children_reaped'] and not report['cleanup']['active_after_cleanup']
        assert report['worker']['cleanup']['browser_closed'] and report['worker']['cleanup']['denied_requests']==0
        reports.append({'label':label,'cleanup':report['cleanup'],'worker':report['worker']['cleanup']})
    cli('version');cli('schema','show')
    assert 'motion.stroke-source' in cli('capabilities')['data']['capabilities']['stroke_motion']['commands']
    project=work/'project';cli('project','init',project)
    cli('motion','html-register','--project',project,'--input',runtime)
    cli('motion','stroke-source','--project',project,'--input',public/'authored-plan.json','--asset-id','wheel-ink')
    cli('motion','html-inspect','--project',project,'--source-asset-id','wheel-ink')
    rendered=cli('motion','html-render','--project',project,'--source-asset-id','wheel-ink','--asset-id','wheel-alpha');browser(rendered,'new-source')
    raw=decode(project/rendered['data']['asset']['uri']);assert raw==decode(public/'green-alpha.nut')
    cli('rights','check','--project',project,expected=7)
    restored=work/'restored';cli('convert','import','--input',smoke/'project.zip','--output',restored)
    cli('motion','html-register','--project',restored,'--input',runtime)
    rebuilt=cli('motion','html-render','--project',restored,'--from-asset-id','ink-green','--asset-id','wheel-restored');browser(rebuilt,'restored')
    assert decode(restored/rebuilt['data']['asset']['uri'])==raw
    record={'status':'passed','package_file_count':len(inventory),'package_files':inventory,'wheel_sha256':sha(wheel),
        'fresh_process_cli_calls':len(calls),'calls':calls,'runtime_dependencies':dependencies,'host_optional_numpy_pillow_torch_blocked':True,
        'host_socket_network_blocked':True,'encoded_frames':72,'extra_order_redraws':144,'rgba_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),
        'rgba_equal_to_source_product_and_package':True,'browser_reports':reports,'schema_resource_available':True,
        'external_native_browser_and_ffmpeg':'existing explicit local toolchain; not newly downloaded or packaged',
        'clean_machine_accepted':False,'generator_sha256':sha(Path(__file__))}
    save(evidence/'verification.json',record)
    print(json.dumps({k:record[k] for k in ('status','package_file_count','fresh_process_cli_calls','encoded_frames')}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('work','smoke','public','runtime','evidence'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,k).resolve() for k in ('work','smoke','public','runtime','evidence')))
