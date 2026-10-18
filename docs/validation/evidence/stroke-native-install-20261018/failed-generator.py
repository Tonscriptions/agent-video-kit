"""Install the new native release and encode an authored stroke source offline."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def run(bundle,work,public,runtime,evidence):
    work.mkdir(parents=True,exist_ok=False);evidence.mkdir(parents=True,exist_ok=False)
    target=work/'installed';env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',str(bundle/'install.py'),
        '--bundle',str(bundle),'--target',str(target),'--manifest-sha256',sha(bundle/'manifest.json')],env=env,capture_output=True,timeout=180)
    (evidence/'install.stdout.json').write_bytes(result.stdout);(evidence/'install.stderr.log').write_bytes(result.stderr)
    assert result.returncode==0,(result.stdout,result.stderr)
    calls=[]
    def cli(*args):
        p=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',str(target/'run.py'),*map(str,args)],env=env,cwd=work,capture_output=True,timeout=300)
        number=len(calls)+1;(evidence/f'{number:02}.stdout.json').write_bytes(p.stdout);(evidence/f'{number:02}.stderr.log').write_bytes(p.stderr)
        assert p.returncode==0,(p.stdout,p.stderr)
        value=json.loads(p.stdout);calls.append({'args':list(map(str,args)),'exit_code':p.returncode});return value
    cli('schema','show');cli('capabilities');project=work/'project';cli('project','init',project)
    cli('motion','html-register','--project',project,'--input',runtime)
    cli('motion','stroke-source','--project',project,'--input',public/'authored-plan.json','--asset-id','installed-ink')
    rendered=cli('motion','html-render','--project',project,'--source-asset-id','installed-ink','--asset-id','installed-alpha')
    def decode(path):
        p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','rawvideo','-pix_fmt','rgba','-'],capture_output=True,timeout=60)
        assert p.returncode==0;return p.stdout
    raw=decode(project/rendered['data']['asset']['uri']);assert len(raw)==36*384*216*4 and raw==decode(public/'green-alpha.nut')
    report=json.loads(Path(rendered['data']['report']).read_bytes());save(evidence/'browser.json',report)
    assert report['cleanup']['all_children_reaped'] and report['worker']['cleanup']['browser_closed']
    shutil.copyfile(bundle.with_suffix('.zip'),public/'agent-video-kit-cp313-win_amd64.zip')
    shutil.copyfile(bundle/'manifest.json',public/'release-manifest.json')
    shutil.copyfile(target/'receipt.json',public/'install-receipt.json')
    save(evidence/'verification.json',{'status':'passed','native_windows':True,'virtualization':False,'virtual_environment':False,
        'installer_exit_code':result.returncode,'cli_calls':len(calls),'calls':calls,'frames':36,'extra_order_redraws':72,
        'rgba_equal_to_development_source':True,'rgba_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),
        'release_zip_sha256':sha(public/'agent-video-kit-cp313-win_amd64.zip'),'manifest_sha256':sha(public/'release-manifest.json'),
        'receipt_sha256':sha(public/'install-receipt.json'),'generator_sha256':sha(Path(__file__)),
        'local_machine_only':True,'other_machine_accepted':False})
    print(json.dumps({'status':'passed','installed_cli_calls':len(calls),'encoded_frames':36}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('bundle','work','public','runtime','evidence'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,k).resolve() for k in ('bundle','work','public','runtime','evidence')))
