"""Compare the new default against an existing verified pre-shutter installation."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]


def digest(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('work','evidence','older-install-proof','development','runtime','source'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();work=args.work.resolve();evidence=args.evidence.resolve()
    assert not work.exists() and not evidence.exists();work.mkdir(parents=True);evidence.mkdir(parents=True)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
            'script_sha256':digest(__file__),'frozen_before':frozen(),'calls':[],'checks':[],
            'scope':'one default 320x180 8fps 16-frame procedural fixture against verified pre-shutter installation',
            'virtualization':False,'network_media':False,'quality_accepted':False}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok,**detail):
        record['checks'].append({'name':name,'ok':bool(ok),**detail});save()
        if not ok:raise AssertionError(name)
    def run(label,argv,binary=False):
        env=dict(os.environ);env.update(TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run(list(map(str,argv)),cwd=ROOT,env=env,capture_output=True,timeout=600)
        (evidence/(label+'.stderr.log')).write_bytes(result.stderr)
        if not binary:(evidence/(label+'.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label':label,'command':list(map(str,argv)),'exit_code':result.returncode,
                               'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest()});save()
        assert result.returncode==0,(label,result.stdout[-1000:],result.stderr[-1000:])
        return result.stdout
    try:
        proof=json.loads(args.older_install_proof.resolve().read_bytes());assert proof['status']=='passed'
        installed=Path(proof['installation']['target']);package=installed/'site/ai_ad_editor'
        resources={p.name:digest(p)[7:] for p in package.iterdir() if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt'}}
        check('verified-existing-old-install-bytes',resources==proof['resource_hashes'] and len(resources)==144 and 'html_shutter.py' not in resources)
        record['older_install_proof']={'path':str(args.older_install_proof.resolve()),'sha256':digest(args.older_install_proof.resolve()),'resources':resources}
        prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py'];project=work/'project'
        def cli(label,*argv):return json.loads(run('cli-'+label,[*prefix,*argv]))
        cli('init','project','init',project)
        cli('register','motion','html-register','--project',project,'--input',args.runtime.resolve())
        cli('source','motion','html-source','--project',project,'--input',args.source.resolve(),'--asset-id','source')
        reply=cli('default','motion','html-render','--project',project,'--source-asset-id','source','--asset-id','old-default','--layout-check','strict')
        old=json.loads(Path(reply['data']['report']).read_bytes());(evidence/'old-browser.json').write_bytes(Path(reply['data']['report']).read_bytes())
        dev=json.loads(args.development.resolve().read_bytes());assert dev['frozen_equal'] and dev['frozen_before']==dev['frozen_after']==frozen()
        current=json.loads((args.development.resolve().parent/'sharp-browser.json').read_bytes())
        check('actual-source-png-hashes-identical',old['worker']['frame_hashes']==current['worker']['frame_hashes'])
        check('fresh-context-order-hashes-identical',old['worker']['verification']==current['worker']['verification'])
        check('actual-output-clock-identical',old['encoded_clock']==current['encoded_clock'])
        check('old-owned-process-tree-reaped',old['cleanup']['all_children_reaped'] and not old['cleanup']['active_after_cleanup'] and old['worker']['cleanup']['browser_closed'])
        path=project/reply['data']['asset']['uri']
        raw=run('decode-old',['ffmpeg','-v','error','-i',path,'-an','-f','rawvideo','-pix_fmt','rgba','-threads','1','pipe:1'],binary=True)
        size=320*180*4;hashes=['sha256:'+hashlib.sha256(raw[i:i+size]).hexdigest() for i in range(0,len(raw),size)]
        check('whole-old-decoded-rgba-identical',len(raw)==16*size and hashes==dev['renders']['sharp']['frame_rgba_sha256'])
        record.update(status='passed',older_default_sha256=digest(path),current_default_sha256=dev['renders']['sharp']['asset']['sha256'],
                      container_bytes_identical=digest(path)==dev['renders']['sharp']['asset']['sha256'],
                      frame_rgba_sha256=hashes,isolated_older_cli_calls=4)
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal'];print(json.dumps({k:record[k] for k in ('status','isolated_older_cli_calls','container_bytes_identical','frozen_equal')}))


if __name__=='__main__':main()
