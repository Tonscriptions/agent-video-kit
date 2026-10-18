"""Development-only pinned Qwen source/config/weights; never a product downloader."""
import argparse,hashlib,json,math,os,time,urllib.request,zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(4*1024*1024):h.update(chunk)
    return h.hexdigest()


def main(args):
    evidence=args.evidence.resolve();target=args.target.resolve();source=args.source.resolve()
    assert target.is_relative_to(ROOT/'product/.runtime') and source.is_relative_to(ROOT/'sources') and evidence.is_relative_to(ROOT/'docs')
    assert args.resume or (not target.exists() and not source.exists())
    target.mkdir(parents=True,exist_ok=args.resume);source.mkdir(parents=True,exist_ok=args.resume);evidence.mkdir(parents=True,exist_ok=False)
    inspection=json.loads(args.inspection.read_bytes());model=inspection['models']['Qwen/Qwen3-ForcedAligner-0.6B']
    repo,revision=model['repository'],model['revision'];assert model['card']['license']=='apache-2.0'
    def save(name,data):
        (evidence/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    def small(url,destination,limit):
        with urllib.request.urlopen(url,timeout=40) as response:body=response.read(limit+1)
        assert len(body)<=limit;destination.write_bytes(body);return body
    try:
        revision_source=inspection['sources']['QwenLM/Qwen3-ASR']['revision']
        archive=source/'source.zip'
        if not archive.exists():
            small('https://codeload.github.com/QwenLM/Qwen3-ASR/zip/'+revision_source,archive,16*1024*1024)
        with zipfile.ZipFile(archive) as z:
            assert sum(i.file_size for i in z.infolist())<64*1024*1024
            for item in z.infolist():
                dest=(source/item.filename).resolve()
                assert dest.is_relative_to(source) and not item.filename.startswith('/')
            if not any(p.is_dir() for p in source.iterdir()):z.extractall(source)
        source_root=next(p for p in source.iterdir() if p.is_dir())
        assert (source_root/'LICENSE').is_file()
        save('source.json',{'repository':'QwenLM/Qwen3-ASR','revision':revision_source,'archive_sha256':sha(archive),
            'files':{p.relative_to(source_root).as_posix():sha(p) for p in sorted(source_root.rglob('*')) if p.is_file()},'code_executed':False})
        files=[]
        for f in model['files']:
            name=f['rfilename']
            if name.endswith('.safetensors'):continue
            if not (name.endswith(('.json','.txt','.md')) or name in {'LICENSE','NOTICE'}):continue
            assert 0<f.get('size',0)<16*1024*1024 and not Path(name).is_absolute() and '..' not in Path(name).parts
            dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
            attempts=[]
            urls=['https://hf-mirror.com/'+repo+'/raw/'+revision+'/'+name,
                  'https://modelscope.cn/models/'+repo+'/resolve/master/'+name+'?download=true']
            for url in urls:
                try:
                    body=small(url,dest,16*1024*1024)
                    assert len(body)==f['size']
                    assert hashlib.sha1(('blob '+str(len(body))+'\0').encode()+body).hexdigest()==f['blobId']
                    break
                except Exception as exc:
                    attempts.append({'url':url,'error':repr(exc)})
                    save('config-'+name.replace('/','_')+'.failure.json',{'attempts':attempts})
            else:raise RuntimeError('Pinned configuration unavailable: '+name)
            files.append({'path':name,'bytes':len(body),'sha256':sha(dest),'attempts':attempts})
        save('configs.json',{'repository':repo,'revision':revision,'files':files})
        weights=[f for f in model['files'] if f['rfilename'].endswith('.safetensors')];assert len(weights)==1
        weight=weights[0];total=weight['size'];expected=weight['lfs']['sha256'];parts=[]
        part_root=target/'download-parts';part_root.mkdir(exist_ok=args.resume)
        chunk_size=64*1024*1024
        for start in range(0,total,chunk_size):parts.append({'start':start,'end':min(total,start+chunk_size)-1})
        save('plan.json',{'repository':repo,'revision':revision,'weight':weight,'parts':parts,'workers':8})
        def download(part):
            start,end=part['start'],part['end'];dest=part_root/(str(start)+'.part');attempts=[]
            for attempt in range(4):
                endpoint=['https://hf-mirror.com/'+repo+'/resolve/'+revision,
                          'https://modelscope.cn/models/'+repo+'/resolve/master'][attempt%2]
                offset=dest.stat().st_size if dest.exists() else 0
                try:
                    request=urllib.request.Request(endpoint+'/'+weight['rfilename']+f'?download=true&avk_range={start+offset}-{end}',
                        headers={'Range':f'bytes={start+offset}-{end}','User-Agent':'Agent-Video-Kit-pinned-development-download'})
                    with urllib.request.urlopen(request,timeout=45) as response:
                        assert response.status==206 and response.headers.get('Content-Range')==f'bytes {start+offset}-{end}/{total}'
                        with dest.open('ab' if offset else 'xb') as stream:
                            while body:=response.read(1024*1024):
                                assert stream.tell()+len(body)<=end-start+1;stream.write(body)
                    assert dest.stat().st_size==end-start+1
                    row={**part,'bytes':dest.stat().st_size,'sha256':sha(dest),'attempts':attempts}
                    save('range-'+str(start)+'.json',row)
                    print(json.dumps({'range_start':start,'bytes':row['bytes'],'status':'received'}),flush=True)
                    return row
                except Exception as exc:
                    attempts.append({'endpoint':endpoint,'offset':offset,'error':repr(exc)})
                    save('range-'+str(start)+'.failure.json',{'attempts':attempts})
            raise RuntimeError('Range failed with preserved partial: '+str(start))
        with ThreadPoolExecutor(max_workers=8) as pool:ranges=list(pool.map(download,parts))
        assembled=target/(weight['rfilename']+'.assembled')
        with assembled.open('xb') as stream:
            for part in parts:
                with (part_root/(str(part['start'])+'.part')).open('rb') as src:
                    while body:=src.read(4*1024*1024):stream.write(body)
        assert assembled.stat().st_size==total and sha(assembled)==expected
        assembled.rename(target/weight['rfilename'])
        save('verification.json',{'status':'downloaded_and_hashed','repository':repo,'revision':revision,
            'weight_bytes':total,'weight_sha256':'sha256:'+expected,'configs':files,'ranges':ranges,
            'development_network':True,'runtime_downloads':False,'code_or_weights_executed':False,
            'generator_sha256':'sha256:'+sha(Path(__file__))})
        print(json.dumps({'status':'downloaded_and_hashed','bytes':total}),flush=True)
    except Exception as exc:
        save('failure.json',{'status':'failed','error':repr(exc),'partials_preserved':True});raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['inspection','target','source','evidence']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--resume',action='store_true',help='Reuse retained development paths; final pinned digests are still mandatory')
    main(p.parse_args())
