"""Explicit development acquisition of pinned ROSE weights; never a runtime downloader."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT/'product/.runtime/temporal-model-audit-20261018'
ROSE_REV = '8a5e57c9f25e73a4b62d324719cdf3367c13df59'
BASE_REV = '9bcbbcf673c0e6a996df6f3f25bee596ffa36d47'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while data := stream.read(8*1024**2): h.update(data)
    return 'sha256:'+h.hexdigest()
def read(path): return json.loads(path.read_bytes())
def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')

def run(output, evidence):
    output.mkdir(parents=True, exist_ok=False); evidence.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    rose = read(AUDIT/'models/Kunbyte__ROSE/metadata.json')
    base = read(AUDIT/'models/alibaba-pai__Wan2.1-Fun-1.3B-InP/metadata.json')
    assert rose['sha'] == ROSE_REV and base['sha'] == BASE_REV
    for name, value in [('rose-metadata.json', rose), ('base-metadata.json', base)]: save(evidence/name, value)
    source = AUDIT/'Kunbyte-AI__ROSE'
    acquisition = read(source/'acquisition.json')
    assert acquisition['commit'] == '6be41c5420bf331c6d491277d5a6feaf9b3a779a'
    selected = []
    for row in acquisition['selected']:
        name = row['path']
        if name in {'LICENSE','README.md','requirements.txt','configs/wan2.1/wan_civitai.yaml'} or name.startswith('rose/models/') or name.startswith('rose/pipeline/') or name == 'rose/__init__.py':
            path = source/'source'/name
            assert sha(path)[7:] == row['sha256'] and path.stat().st_size == row['bytes']
            target = output/'source'/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path,target)
            selected.append({'path':name, 'sha256':sha(target), 'bytes':target.stat().st_size})
    save(evidence/'source.json', {'acquisition_sha256':sha(source/'acquisition.json'), 'commit':acquisition['commit'], 'files':selected})
    jobs = []
    for model, revision, metadata, names, prefix in [
        ('Kunbyte/ROSE', ROSE_REV, rose, ['README.md','config.json','diffusion_pytorch_model.safetensors'], 'transformer'),
        ('alibaba-pai/Wan2.1-Fun-1.3B-InP', BASE_REV, base, ['LICENSE.txt','README.md','config.json','configuration.json',
         'Wan2.1_VAE.pth','models_t5_umt5-xxl-enc-bf16.pth','google/umt5-xxl/spiece.model',
         'google/umt5-xxl/special_tokens_map.json','google/umt5-xxl/tokenizer_config.json','google/umt5-xxl/tokenizer.json'], 'base')]:
        mapping = {r['rfilename']:r for r in metadata['siblings']}
        for name in names:
            row = mapping[name]; jobs.append((model,revision,name,row,prefix))
    lock = threading.Lock(); results = []; requests = []
    def record(row):
        with lock:
            requests.append(row); save(evidence/'requests.json', requests)
    def fetch(job):
        model,revision,name,metadata,prefix = job
        target = output/prefix/name; target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name+'.partial'); size = metadata['size']
        h = hashlib.sha256(); start = time.monotonic(); offset = 0; failures = []
        if partial.exists():
            with partial.open('rb') as stream:
                while data := stream.read(8*1024**2): h.update(data); offset += len(data)
        last_notice = offset
        for attempt in range(12):
            if offset == size: break
            domain = 'hf-mirror.com' if attempt % 2 == 0 else 'huggingface.co'
            url = f'https://{domain}/{model}/resolve/{revision}/{name}?download=true&avk_offset={offset}'
            headers = {'User-Agent':'agent-video-kit-development-research/1.0'}
            if offset: headers['Range'] = f'bytes={offset}-'
            began = offset
            try:
                with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=35) as response:
                    status = response.status
                    if offset and (status != 206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-')):
                        raise RuntimeError('server did not honor exact resume offset')
                    with partial.open('ab') as stream:
                        while data := response.read(4*1024**2):
                            if offset+len(data) > size: raise RuntimeError('response exceeds pinned metadata size')
                            stream.write(data); h.update(data); offset += len(data)
                            if offset-last_notice >= 128*1024**2:
                                print(json.dumps({'file':name,'bytes':offset,'total':size}),flush=True); last_notice=offset
                record({'model':model,'revision':revision,'path':name,'url':url,'range_start':began,
                        'received_bytes':offset-began,'status':status,'complete':offset==size})
            except Exception as exc:
                detail={'model':model,'revision':revision,'path':name,'url':url,'range_start':began,
                        'received_bytes':offset-began,'error':str(exc)}
                failures.append(detail); record(detail)
        assert offset == size, (name, offset, size, failures)
        digest = h.hexdigest(); lfs = metadata.get('lfs')
        if lfs: assert digest == lfs['sha256'], (name,'LFS digest mismatch')
        else:
            raw = partial.read_bytes(); blob = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            assert blob == metadata['blobId'], (name,'Git blob mismatch')
        partial.rename(target)
        result={'model':model,'revision':revision,'source_path':name,'path':str(target), 'bytes':size,
                'sha256':'sha256:'+digest,'lfs_sha256_verified':bool(lfs),'git_blob_verified':not bool(lfs),
                'seconds':time.monotonic()-start,'attempt_failures':len(failures)}
        with lock:
            results.append(result); save(evidence/'files.json',results)
        print(json.dumps({'file':name,'status':'verified','bytes':size}),flush=True)
        return result
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(fetch,j) for j in jobs]
            for future in as_completed(futures): future.result()
        result={'status':'acquired_and_verified','checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'files':sorted(results,key=lambda r:r['path']),'file_count':len(results),'bytes':sum(r['bytes'] for r in results),
            'code_files':len(selected),'code_receipt_sha256':sha(evidence/'source.json'),
            'generator_sha256':sha(Path(__file__)),'contract_sha256':sha(ROOT/'docs/specs/ROSE离线对象移除与副作用核验契约_v0.1_2026-10-19.md'),
            'clip_checkpoint_acquired':False,'base_transformer_acquired':False,'model_inference_calls':0,
            'runtime_downloader':False,'virtualization':False,'network_purpose':'explicit development acquisition only'}
        save(evidence/'verification.json',result); print(json.dumps({'status':result['status'],'files':len(results),'bytes':result['bytes']}))
    except BaseException as exc:
        save(evidence/'failure.json',{'error':repr(exc),'files':results,'requests':len(requests)}); raise

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    a=p.parse_args();run(a.output.resolve(),a.evidence.resolve())
