"""Development-only pinning of public alignment model metadata and source."""
import argparse,hashlib,json,urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main(args):
    out=args.output.resolve();assert out.is_relative_to(ROOT/'docs');out.mkdir(parents=True,exist_ok=False)
    def fetch(url,name):
        request=urllib.request.Request(url,headers={'User-Agent':'Agent-Video-Kit-development-source-review'})
        try:
            with urllib.request.urlopen(request,timeout=35) as response:
                body=response.read(8*1024*1024+1);assert len(body)<=8*1024*1024
            (out/name).write_bytes(body)
            return {'url':url,'file':name,'bytes':len(body),'sha256':'sha256:'+hashlib.sha256(body).hexdigest()},json.loads(body)
        except Exception as exc:
            (out/(name+'.failure.json')).write_text(json.dumps({'url':url,'error':repr(exc)})+'\n',encoding='utf-8')
            raise
    def model(repo):
        key=repo.replace('/','__'); attempts=[]
        for endpoint in ['https://huggingface.co','https://hf-mirror.com']:
            try:
                proof,data=fetch(endpoint+'/api/models/'+repo+'?blobs=true',key+'.json')
                return repo,{'repository':repo,'revision':data['sha'],'card':data.get('cardData'),
                    'files':data['siblings'],'source':proof,'failed_transports':attempts}
            except Exception as exc:attempts.append(repr(exc))
        return repo,{'repository':repo,'status':'unavailable','attempts':attempts}
    with ThreadPoolExecutor(max_workers=3) as pool:
        models=dict(pool.map(model,['Qwen/Qwen3-ForcedAligner-0.6B','charsiu/en_w2v2_fc_10ms','charsiu/zh_w2v2_tiny_fc_10ms']))
    sources={}
    for repo in ['QwenLM/Qwen3-ASR','lingjzhu/charsiu']:
        key=repo.replace('/','__')
        try:
            proof,data=fetch('https://api.github.com/repos/'+repo+'/commits/main',key+'.main.json')
            sources[repo]={'revision':data['sha'],'source':proof}
        except Exception as exc:sources[repo]={'error':repr(exc)}
    record={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'models':models,'sources':sources,
        'development_network_only':True,'weights_downloaded':False,'inference_runs':0,
        'generator_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'inspection.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'models':{k:{'revision':v.get('revision'),'license':(v.get('card') or {}).get('license'),
        'weight_files':[(f['rfilename'],f.get('size')) for f in v.get('files',[]) if f['rfilename'].endswith(('.safetensors','.bin'))]} for k,v in models.items()},'sources':sources},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args())
