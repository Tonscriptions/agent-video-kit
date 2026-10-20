"""Restore required committed media fixtures into a sparse native checkout.

Only these five known files may be created; existing different bytes are never
overwritten. No network, external repository, renderer or model is invoked.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=('docs/assets/source-transitions-20261017/source-a.mp4',
    'docs/assets/source-transitions-20261017/sound-a.wav',
    'docs/assets/fragments-20261018/agent-grid-cc0.ttf',
    'docs/assets/html-template-20261018/template/font.ttf',
    'docs/assets/openfilm-workflow-screen-20261019-v61-r3/screen-input.mkv')


def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def git(*args):return subprocess.run(['git',*args],cwd=ROOT,check=True,capture_output=True).stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ref',default='HEAD')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--materialize',action='store_true')
    args=parser.parse_args();output=args.output.resolve();assert output.is_relative_to(ROOT/'docs') and not output.exists()
    output.parent.mkdir(parents=True,exist_ok=True)
    record={'status':'checking','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__).read_bytes()),'network':False,'virtualization':False,
        'fixture_scope':'five committed media/font inputs referenced by native regression tests','fixtures':[]}
    try:
        commit=git('rev-parse',args.ref+'^{commit}').decode().strip();record['source_commit']=commit
        for name in FIXTURES:
            blob=git('rev-parse',commit+':'+name).decode().strip();data=git('cat-file','blob',blob)
            assert 0<len(data)<=4*1024**2;target=ROOT/name
            assert target.resolve().is_relative_to(ROOT) and not target.is_symlink()
            created=False
            if target.exists():assert target.is_file() and target.read_bytes()==data,'different existing fixture: '+name
            else:
                assert args.materialize,'missing committed fixture: '+name
                target.parent.mkdir(parents=True,exist_ok=True)
                try:
                    with target.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
                    created=True
                except BaseException:
                    if created:target.unlink(missing_ok=True)
                    raise
            assert target.read_bytes()==data
            record['fixtures'].append({'path':name,'git_blob':blob,'bytes':len(data),'sha256':sha(data),
                'materialized':created,'all_bytes_equal_committed_blob':True})
        record['status']='passed';record['fixture_count']=len(record['fixtures'])
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':record['status'],'fixture_count':len(record['fixtures']),
        'materialized':sum(x['materialized'] for x in record['fixtures']),'network':False}))


if __name__=='__main__':main()
