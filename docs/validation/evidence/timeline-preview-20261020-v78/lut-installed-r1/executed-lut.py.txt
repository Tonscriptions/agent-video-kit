"""Execute each direct LUT alias through real CLI before/after equal-size/mtime edits."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return 'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pixel(p):
    with Image.open(p) as im:return im.convert('RGBA').tobytes()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source-project','work','evidence'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--installed',type=Path);args=parser.parse_args()
    work=args.work.resolve();evidence=args.evidence.resolve();source=args.source_project.resolve()
    assert work.is_relative_to(ROOT/'product/.runtime') and evidence.is_relative_to(ROOT/'docs') and not work.exists() and not evidence.exists()
    work.mkdir(parents=True);evidence.mkdir(parents=True)
    (evidence/'executed-lut.py.txt').write_bytes(Path(__file__).read_bytes())
    root=work/'project';root.mkdir();shutil.copytree(source/'assets',root/'assets');shutil.copyfile(source/'project.json',root/'project.json')
    sys.path.insert(0,str(ROOT/'product/src'))
    from ai_ad_editor.project import ledger_file
    ledger=ledger_file(source);dest=root/ledger.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():shutil.copyfile(ledger,dest)
    prefix=[sys.executable,'-I','-S','-B','-X','utf8',args.installed.resolve()/'run.py'] if args.installed else [sys.executable,'-E','-B','-X','utf8','-c',
        'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())',ROOT/'product/src']
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':frozen(),'generator_sha256':sha(__file__),
        'calls':[],'cases':[],'network':False,'virtualization':False,'new_model_inference':0}
    def save():write(evidence/'verification.json',record)
    def cli(label,*args):
        command=list(map(str,[*prefix,*args]));result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=180)
        for stream in ('stdout','stderr'):(evidence/(label+'.'+stream+'.log')).write_bytes(getattr(result,stream))
        record['calls'].append({'label':label,'command':command,'exit_code':result.returncode,
            'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':'sha256:'+hashlib.sha256(result.stderr).hexdigest()});save()
        assert result.returncode==0,(label,result.stdout[-1800:],result.stderr[-1800:])
        return json.loads(result.stdout)['data']
    try:
        project=json.loads((root/'project.json').read_bytes());clip=project['sequences'][0]['tracks'][0]['clips'][0]
        path=root/'assets/look.cube';a='LUT_3D_SIZE 2\n'+''.join(f'{r} {g} {b}\n' for b in (0,1) for g in (0,1) for r in (0,1))
        b='LUT_3D_SIZE 2\n'+''.join(f'{1-r} {g} {v}\n' for v in (0,1) for g in (0,1) for r in (0,1))
        for alias in ('path','file','lut'):
            clip['effects']=[{'type':'lut3d','parameters':{alias:'assets/look.cube','intensity':1}}];write(root/'project.json',project)
            path.write_text(a,encoding='ascii',newline='\n');stamp=path.stat();before_sha=sha(path)
            argv=('preview','frame','--project',root,'--frame',3,'--height',144)
            first=cli(alias+'-original',*argv,'--output',root/'previews'/(alias+'-original'));old=pixel(first['path'])
            hit=cli(alias+'-hit',*argv);assert hit['cache_hit'] and not first['cache_hit']
            path.write_text(b,encoding='ascii',newline='\n');os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns));after_sha=sha(path)
            changed=cli(alias+'-changed',*argv,'--output',root/'previews'/(alias+'-changed'));new=pixel(changed['path'])
            assert before_sha!=after_sha and path.stat().st_size==stamp.st_size and path.stat().st_mtime_ns==stamp.st_mtime_ns
            assert not changed['cache_hit'] and first['cache_key']!=changed['cache_key'] and old!=new
            again=cli(alias+'-changed-hit',*argv);assert again['cache_hit'] and again['cache_key']==changed['cache_key']
            for label,file in [('original',first['path']),('changed',changed['path'])]:shutil.copyfile(file,evidence/(alias+'-'+label+'.png'))
            record['cases'].append({'alias':alias,'same_size_and_mtime':True,'source_before_sha256':before_sha,'source_after_sha256':after_sha,
                'original_cache_key':first['cache_key'],'changed_cache_key':changed['cache_key'],'old_cache_rejected':True,'new_content_hits':True,
                'old_rgba_sha256':'sha256:'+hashlib.sha256(old).hexdigest(),'new_rgba_sha256':'sha256:'+hashlib.sha256(new).hexdigest()});save()
        record.update(status='passed',cli_calls=len(record['calls']))
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal'];print(json.dumps({'status':record['status'],'cli_calls':record['cli_calls'],'frozen_equal':True}))

if __name__=='__main__':main()
