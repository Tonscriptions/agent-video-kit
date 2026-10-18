"""Retain and fill failed development transfer ranges; verify original full hash."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(4*1024*1024):h.update(data)
    return h.hexdigest()


def main(args):
    evidence=args.evidence.resolve();evidence.mkdir(parents=True,exist_ok=False)
    plan=json.loads(args.plan.read_text(encoding='utf-8'))
    def save(name,value):(evidence/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    jobs=[]
    for model in plan['models']:
        output=Path(model['output']);assert output.is_relative_to(ROOT/'product/.runtime')
        for part in model.get('ranges',[]):
            path=Path(part['path']);expected=part['end']-part['start']+1
            if not path.exists() or path.stat().st_size!=expected:jobs.append((model,part))
    save('plan.json',{'source_plan_sha256':sha(args.plan),'missing_or_partial_ranges':len(jobs),'workers':4})
    def download(job):
        model,part=job;path=Path(part['path']);attempts=[];total=model['expected_bytes']
        for attempt in range(5):
            offset=path.stat().st_size if path.exists() else 0
            attempts.append({'offset':offset})
            try:
                url=f"https://hf-mirror.com/{model['repository']}/resolve/{model['revision']}/{model['filename']}"
                req=urllib.request.Request(url,headers={'Range':f"bytes={part['start']+offset}-{part['end']}"})
                with urllib.request.urlopen(req,timeout=30) as response:
                    assert response.status==206 and response.headers.get('Content-Range')==f"bytes {part['start']+offset}-{part['end']}/{total}"
                    with path.open('ab' if path.exists() else 'xb') as stream:
                        while data:=response.read(1024*1024):
                            assert stream.tell()+len(data)<=part['end']-part['start']+1
                            stream.write(data)
                assert path.stat().st_size==part['end']-part['start']+1
                row={**part,'status':'received','sha256':sha(path),'attempts':attempts}
                save(f"{part['language']}-{part['start']}.json",row)
                print(json.dumps({'language':part['language'],'start':part['start'],'status':'received'}),flush=True)
                return row
            except Exception as exc:
                attempts[-1]['error']=repr(exc);save(f"{part['language']}-{part['start']}.failure.json",{'attempts':attempts})
                if attempt==4:raise
                time.sleep(2*(attempt+1))
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:received=list(pool.map(download,jobs))
        for model in plan['models']:
            output=Path(model['output'])
            if output.exists():
                assert sha(output)==model.get('expected_sha256',model.get('sha256'))
                continue
            prefix=output.with_name(output.name+'.part.prefix')
            assert prefix.stat().st_size==model['prefix_bytes'] and sha(prefix)==model['prefix_sha256']
            assembled=output.with_name(output.name+'.assembled-repair')
            with assembled.open('xb') as stream:
                for part in [prefix,*(Path(r['path']) for r in model['ranges'])]:
                    with part.open('rb') as source:
                        while data:=source.read(4*1024*1024):stream.write(data)
            assert assembled.stat().st_size==model['expected_bytes'] and sha(assembled)==model['expected_sha256']
            assembled.rename(output)
            model.update(status='verified',sha256=sha(output))
        save('verification.json',{'status':'verified','models':plan['models'],'repaired_ranges':received,
            'development_network':True,'runtime_downloads':False,'weights_executed':False,'generator_sha256':sha(Path(__file__))})
        print(json.dumps({'status':'verified','models':len(plan['models']),'repaired_ranges':len(jobs)}))
    except Exception as exc:
        save('failure.json',{'status':'failed','error':repr(exc),'partials_preserved':True});raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);main(p.parse_args())
