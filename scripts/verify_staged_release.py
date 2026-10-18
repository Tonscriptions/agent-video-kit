"""Compare staged blobs to workspace bytes and a completed regression's frozen input."""
from __future__ import annotations
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def git(*arguments):
    result=subprocess.run(['git',*arguments],cwd=ROOT,capture_output=True,check=True)
    return result.stdout


def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()


def run(full_path,output):
    assert not output.exists()
    full=json.loads(full_path.read_bytes())
    assert full['terminal_ok'] and full['exit_code']==0 and full['frozen_equal'] and full['skipped']==0
    assert full['frozen_before']==full['frozen_after']
    assert git('branch','--show-current').strip()==b'main'
    assert git('remote','get-url','origin').strip()==b'git@github.com:Tonscriptions/agent-video-kit.git'
    git('diff','--quiet');git('diff','--cached','--check')
    assert not git('ls-files','--others','--exclude-standard')
    changed=[raw.decode('utf-8') for raw in git('diff','--cached','--name-only','-z','--diff-filter=ACMRT').split(b'\0') if raw]
    assert changed
    names=sorted(set(changed)|set(full['frozen_after']))
    assert all('\n' not in name and '\r' not in name for name in names)
    batch=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,input=b''.join(b':'+name.encode('utf-8')+b'\n' for name in names),capture_output=True,check=True).stdout
    offset=0;rows=[]
    for name in names:
        end=batch.index(b'\n',offset);oid,kind,size=batch[offset:end].rsplit(b' ',2);size=int(size)
        assert kind==b'blob';offset=end+1;payload=batch[offset:offset+size];offset+=size
        assert batch[offset:offset+1]==b'\n';offset+=1
        assert payload==(ROOT/name).read_bytes(),name
        digest=sha(payload)
        if name in full['frozen_after']:assert digest==full['frozen_after'][name],name
        rows.append({'path':name,'git_blob':oid.decode(),'bytes':size,'sha256':digest,'changed':name in changed,'frozen':name in full['frozen_after']})
    assert offset==len(batch)
    record={'status':'passed','base_commit':git('rev-parse','HEAD').decode().strip(),'index_tree':git('write-tree').decode().strip(),'changed_files':len(changed),'frozen_files':len(full['frozen_after']),'compared_blobs':len(rows),'compared_bytes':sum(row['bytes'] for row in rows),'all_staged_bytes_equal_workspace':True,'all_frozen_bytes_equal_staged':True,'diff_check':'passed','regression_sha256':sha(full_path.read_bytes()),'files':rows,'generator_sha256':sha(Path(__file__).read_bytes())}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({key:record[key] for key in ('status','changed_files','frozen_files','compared_blobs','compared_bytes','index_tree')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--full',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();run(args.full.resolve(),args.output.resolve())
