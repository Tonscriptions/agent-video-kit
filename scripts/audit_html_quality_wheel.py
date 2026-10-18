"""Check offline wheel bytes and fresh native CLI layout/font gates."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,time,zipfile
from pathlib import Path
from smoke_fragments import frozen,save,sha

ROOT=Path(__file__).resolve().parents[1]


def run(work,smoke,public,runtime):
    work.mkdir(parents=True,exist_ok=False);before=frozen()
    env=dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),TMPDIR=str(ROOT/'product/.runtime/temp'),
        AI_AD_EDITOR_RUNTIME_DIR=str(work/'runtime'),PIP_CACHE_DIR=str(ROOT/'product/.runtime/cache/pip'),PYTHONDONTWRITEBYTECODE='1')
    built=subprocess.run([sys.executable,'-B','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation',str(ROOT/'product'),
        '--wheel-dir',str(work/'dist')],env=env,capture_output=True,timeout=300)
    (work/'build.stdout.log').write_bytes(built.stdout);(work/'build.stderr.log').write_bytes(built.stderr)
    assert built.returncode==0,built.stderr.decode(errors='replace')
    wheel=next((work/'dist').glob('*.whl'));installed=work/'isolated-site';installed.mkdir();files={}
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.infolist():
            if item.is_dir():continue
            path=(installed/item.filename).resolve();assert path.is_relative_to(installed.resolve())
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(item))
            if item.filename.startswith('ai_ad_editor/'):
                assert path.read_bytes()==(ROOT/'product/src'/item.filename).read_bytes(),item.filename
                files[item.filename]={'bytes':path.stat().st_size,'sha256':sha(path)}
    assert len(files)==104
    assert all('ai_ad_editor/'+name in files for name in ('font_coverage.py','html_quality.py','html_quality_dom.mjs','openfilm_text_bounds.mjs','OPENFILM_LICENSE.txt'))
    boot='''import builtins,socket,sys
from pathlib import Path
original=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in {'numpy','PIL','torch'}:raise ImportError('optional module deliberately blocked')
    return original(name,*args,**kwargs)
builtins.__import__=guarded
def denied(*args,**kwargs):raise RuntimeError('wheel host network forbidden')
socket.create_connection=denied;socket.socket.connect=denied;socket.socket.connect_ex=denied
package=sys.argv.pop(1);sys.path.insert(0,package)
from ai_ad_editor.cli import main
code=main()
assert all(Path(m.__file__).resolve().is_relative_to(Path(package).resolve()) for n,m in tuple(sys.modules.items()) if n.startswith('ai_ad_editor') and getattr(m,'__file__',None))
raise SystemExit(code)'''
    calls=[];reports=[]
    def cli(*args,expected=0):
        start=time.monotonic()
        result=subprocess.run([sys.executable,'-I','-B','-X','utf8','-c',boot,str(installed),*map(str,args)],
            cwd=work,env=env,capture_output=True,timeout=300)
        number=len(calls)+1
        (work/f'{number:02}.stdout.json').write_bytes(result.stdout);(work/f'{number:02}.stderr.log').write_bytes(result.stderr)
        calls.append({'number':number,'args':list(map(str,args)),'exit_code':result.returncode,'seconds':time.monotonic()-start})
        assert result.returncode==expected,(calls[-1],result.stdout.decode(errors='replace'),result.stderr.decode(errors='replace'))
        return json.loads(result.stdout)
    def browser(path,label):
        value=json.loads(Path(path).read_text(encoding='utf-8'))
        assert value['cleanup']['all_children_reaped'] and not value['cleanup']['active_after_cleanup']
        assert value['worker']['cleanup']['browser_closed'] and not value['worker']['cleanup']['denied_requests']
        save(work/(label+'.report.json'),value);reports.append({'label':label,'cleanup':value['cleanup'],'worker':value['worker']['cleanup']})
        return value
    cli('version');assert 'motion.html-quality' in cli('capabilities')['data']['capabilities']['html_motion']['commands']
    project=work/'restored';cli('convert','import','--input',smoke/'project.zip','--output',project)
    cli('motion','html-register','--project',project,'--input',runtime)
    inspect=cli('motion','html-quality','--project',project,'--source-asset-id','source-fixed')
    assert browser(inspect['data']['report'],'fixed')['quality_passed']
    missing=cli('motion','html-quality','--project',project,'--source-asset-id','source-legacy',expected=2)
    assert any(x['code']=='FONT_GLYPH_MISSING' for x in browser(missing['errors'][0]['path'],'missing')['issues'])
    args=('motion','html-render','--project',project,'--from-asset-id','fixed-output','--asset-id','wheel-strict','--idempotency-key','wheel-layout')
    first=cli(*args);assert first['data']['asset']['html_motion']['layout_check']=='strict'
    replay=cli(*args)
    assert first['data']['asset']['sha256']==replay['data']['asset']['sha256']
    assert any(x['code']=='IDEMPOTENT_REPLAY' for x in replay['warnings'])
    assert browser(first['data']['layout_report'],'strict-gate')['quality_passed']
    browser(first['data']['report'],'strict-render')
    state=(project/'project.json').read_bytes();ledger=(project/'rights-ledger.json').read_bytes();nuts=sorted((project/'assets/html-motion').glob('*.nut'))
    refused=cli('motion','html-render','--project',project,'--source-asset-id','source-outside','--asset-id','wheel-blocked','--layout-check','strict',expected=2)
    failed=browser(refused['errors'][0]['path'],'strict-rejected')
    assert {x['frame'] for x in failed['issues'] if x['code']=='TEXT_OUTSIDE_FRAME'}=={9,10,11}
    assert state==(project/'project.json').read_bytes() and ledger==(project/'rights-ledger.json').read_bytes() and nuts==sorted((project/'assets/html-motion').glob('*.nut'))
    previews=list((project/'cache/html-quality').rglob('*.png'));assert previews
    cli('policy','audit','--project',project);cli('rights','check','--project',project,expected=7)
    explicit=cli('motion','html-render','--project',project,'--from-asset-id','wheel-strict','--asset-id','wheel-off','--layout-check','off')
    assert explicit['data']['asset']['html_motion']['layout_check']=='off' and explicit['data']['layout_report'] is None
    browser(explicit['data']['report'],'explicit-off-render')
    cli('doctor','--project',project)
    dry=cli('motion','html-quality','--project',project,'--from-asset-id','wheel-strict','--dry-run')
    assert dry['status']=='planned'
    sys.path.insert(0,str(installed))
    from ai_ad_editor.media import ffmpeg_path
    def decoded(path):
        result=subprocess.run([ffmpeg_path(),'-v','error','-i',str(path),'-an','-pix_fmt','rgba','-f','rawvideo','-threads','1','pipe:1'],capture_output=True,env=env,timeout=60)
        assert result.returncode==0,result.stderr
        return result.stdout
    reference=decoded(public/'fixed-alpha.nut');decoded_checks=[]
    for label,result in [('strict',first),('explicit-off',explicit)]:
        value=decoded(project/result['data']['asset']['uri']);assert value==reference
        path=work/(label+'.rgba');path.write_bytes(value)
        decoded_checks.append({'id':label,'frames':12,'rgba_bytes':len(value),'rgba_sha256':sha(path)})
    assert frozen()==before
    record={'status':'passed','frozen_before':before,'frozen_after':frozen(),'frozen_equal':True,
        'package_files':files,'package_file_count':len(files),'wheel_sha256':sha(wheel),'calls':calls,'fresh_process_cli_calls':len(calls),
        'host_optional_numpy_pillow_torch_blocked':True,'host_socket_network_blocked':True,'decoded':decoded_checks,
        'browser_reports':reports,'encoded_html_frames':24,'render_extra_order_redraws':48,'quality_frames':48,'quality_reverse_redraws':48,
        'strict_inherited_and_rerun':True,'strict_rejected_evidence_survives':True,'idempotent_replay':True,
        'toolchain':'explicit existing native Node/Playwright/Chromium, not installed or bundled',
        'clean_machine_accepted':False,'standalone_schema_packaging_accepted':False,'generator_sha256':sha(Path(__file__))}
    save(work/'verification.json',record)
    print(json.dumps({'status':'passed','package_file_count':len(files),'fresh_cli_calls':len(calls)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('work','smoke','public','runtime'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,k).resolve() for k in ('work','smoke','public','runtime')))
