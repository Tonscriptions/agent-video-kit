"""Development-only pinned downloads; runtime inference never calls this helper."""
from __future__ import annotations
import argparse,hashlib,json,os,time,urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n');os.replace(temporary,path)


def run(target,evidence,endpoint):
    assert target.is_relative_to((ROOT/'product/.runtime').resolve()) and not target.is_symlink()
    target.mkdir(parents=True,exist_ok=True);evidence.mkdir(parents=True,exist_ok=False)
    metadata=json.loads((ROOT/'docs/validation/evidence/ctc-model-mirror-source-20261018/inspection.json').read_bytes())
    def model(item):
        language,record=item;folder=target/language;folder.mkdir(exist_ok=True)
        names=['config.json','preprocessor_config.json','special_tokens_map.json','vocab.json']
        if language=='en':names+=['tokenizer_config.json','model.safetensors']
        else:names+=['pytorch_model.bin']
        rows=[]
        for name in names:
            entry=next(x for x in record['files'] if x['rfilename']==name);output=folder/name;part=folder/(name+'.part')
            primary='https://huggingface.co/'+record['repository']+'/resolve/'+record['revision']+'/'+name
            url=endpoint.rstrip('/')+'/'+record['repository']+'/resolve/'+record['revision']+'/'+name
            row={'language':language,'filename':name,'primary_url':primary,'transport_url':url,'expected':entry,'attempts':[]}
            def checked():
                raw_hash=hashlib.sha256();blob_hash=hashlib.sha1(('blob '+str(output.stat().st_size)+'\0').encode())
                with output.open('rb') as stream:
                    while chunk:=stream.read(4*1024**2):raw_hash.update(chunk);blob_hash.update(chunk)
                assert output.stat().st_size==entry['size']
                if entry.get('lfs'):assert raw_hash.hexdigest()==entry['lfs']['sha256']
                else:assert blob_hash.hexdigest()==entry['blobId']
                return raw_hash.hexdigest()
            if not output.exists():
                for attempt in range(3):
                    try:
                        offset=part.stat().st_size if part.exists() else 0
                        headers={'User-Agent':'Agent-Video-Kit-development-pinned-download'}
                        if offset:headers['Range']=f'bytes={offset}-'
                        started=time.monotonic();row['attempts'].append({'offset':offset,'started_at_utc':datetime.now(timezone.utc).isoformat()})
                        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30) as response:
                            if offset and (response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-')):
                                raise ValueError('Server did not honor byte-range resume; existing partial preserved')
                            with part.open('ab' if offset else 'xb') as stream:
                                last=offset
                                while chunk:=response.read(4*1024**2):
                                    stream.write(chunk);offset+=len(chunk)
                                    if offset>entry['size']:raise ValueError('Response exceeds pinned size')
                                    if offset-last>=32*1024**2:
                                        save(evidence/(language+'.progress.json'),{'file':name,'received':offset,'expected':entry['size']});last=offset
                                stream.flush();os.fsync(stream.fileno())
                        if offset!=entry['size']:raise ValueError('Incomplete pinned response')
                        part.rename(output);break
                    except Exception as exc:
                        row['attempts'][-1]['error']=repr(exc);save(evidence/(language+'.current.json'),row)
                        if attempt==2:raise
            row.update(status='verified',bytes=output.stat().st_size,sha256='sha256:'+checked());rows.append(row)
            save(evidence/(language+'.json'),{'status':'in_progress','revision':record['revision'],'files':rows})
            print(json.dumps({'language':language,'file':name,'bytes':row['bytes'],'status':'verified'}),flush=True)
        save(evidence/(language+'.json'),{'status':'verified','repository':record['repository'],'revision':record['revision'],'files':rows,'weights_executed':False})
        return language,rows
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:results=dict(pool.map(model,metadata['models'].items()))
        save(evidence/'verification.json',{'status':'downloaded_verified','files':results,'development_network':True,'runtime_downloads':False,
            'generator_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    except Exception as exc:
        save(evidence/'failure.json',{'status':'failed','error':repr(exc),'partials_preserved':True});raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--endpoint',default='https://hf-mirror.com')
    a=p.parse_args();run(a.target.resolve(),a.evidence.resolve(),a.endpoint)
