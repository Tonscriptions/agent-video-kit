"""Development-only public model metadata inspection; no model execution."""
import hashlib,json,urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MODELS={'zh':'jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn','en':'facebook/wav2vec2-base-960h'}


def run():
    output=ROOT/'docs/validation/evidence/ctc-model-source-20261018';output.mkdir(parents=True,exist_ok=False)
    def fetch(item):
        language,repo=item;url='https://huggingface.co/api/models/'+repo+'?blobs=true';started=datetime.now(timezone.utc).isoformat()
        request=urllib.request.Request(url,headers={'User-Agent':'Agent-Video-Kit-model-source-review','Cache-Control':'no-cache'})
        with urllib.request.urlopen(request,timeout=30) as response:raw=response.read(8*1024**2);status=response.status
        (output/(language+'.api.json')).write_bytes(raw);data=json.loads(raw)
        record={'repository':repo,'url':url,'started_at_utc':started,'http_status':status,'revision':data['sha'],'license_declared':data.get('cardData',{}).get('license'),'raw_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'files':data['siblings']}
        return language,record
    with ThreadPoolExecutor(max_workers=2) as pool:records=dict(pool.map(fetch,MODELS.items()))
    (output/'inspection.json').write_text(json.dumps({'status':'metadata_inspected','models':records,'development_network':True,'runtime_model_download':False,'generator_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for language,row in records.items():print(json.dumps({'language':language,'repo':row['repository'],'revision':row['revision'],'declared_license':row['license_declared'],'candidate_files':[x for x in row['files'] if x['rfilename'].endswith(('.json','.safetensors','.bin'))]},ensure_ascii=False))


if __name__=='__main__':run()
