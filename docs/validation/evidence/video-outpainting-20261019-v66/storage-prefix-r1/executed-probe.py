"""Read bounded real weight prefixes; diagnose storage APIs, not model quality."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--backend',choices=('mmap','pread'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();assert not output.exists()
    output.parent.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    os.environ.update(TEMP=str(root/'product/.runtime/temp'),TMP=str(root/'product/.runtime/temp'),
                      TMPDIR=str(root/'product/.runtime/temp'),CUDA_VISIBLE_DEVICES='-1')
    sys.path.insert(0,str(root/'product/src'))
    from ai_ad_editor.rvm_worker import install_network_guard
    events=[];install_network_guard(events)
    import torch
    import safetensors
    torch.set_num_threads(4)
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'up to 128 scalar values per text weight tensor; not full tensors or model inference',
        'backend':args.backend,'versions':{'python':sys.version.split()[0],'torch':torch.__version__,
        'safetensors':safetensors.__version__},'source_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'blocked_network_events':events,'model_inference_executed':False,'full_weights_sha256_checked':False,
        'root_cause_proven':False,'rows':[]}
    def save():output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save();started=time.monotonic()
    try:
        for p in sorted((args.model/'text_encoder').glob('model-*.safetensors')):
            before=p.stat()
            with p.open('rb') as raw:
                size=struct.unpack('<Q',raw.read(8))[0];assert size<=16*1024**2
                header=json.loads(raw.read(size))
                with safetensors.safe_open(str(p),framework='pt',device='cpu',backend=args.backend) as reader:
                    for key in reader.keys():
                        spec=header[key];shape=spec['shape'];assert shape and all(d>0 for d in shape)
                        selectors=tuple([slice(0,1)]*(len(shape)-1)+[slice(0,min(128,shape[-1]))])
                        tensor=reader.get_slice(key)[selectors].clone().contiguous()
                        actual=tensor.view(torch.uint8).numpy().tobytes()
                        assert len(actual)<=512
                        raw.seek(8+size+spec['data_offsets'][0]);expected=raw.read(len(actual))
                        assert actual==expected,(p.name,key)
                        record['rows'].append({'file':p.name,'key':key,'shape':shape,'dtype':spec['dtype'],
                            'offset':spec['data_offsets'][0],'sample_bytes':len(actual),
                            'sha256':'sha256:'+hashlib.sha256(actual).hexdigest()})
                        save();del tensor
            after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
        assert record['rows'] and not events
        record.update(status='passed_sampled_prefixes',tensors=len(record['rows']),
            sampled_bytes=sum(row['sample_bytes'] for row in record['rows']))
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-started);save()
    print(json.dumps({key:record[key] for key in ('status','backend','tensors','sampled_bytes','seconds')}))


if __name__=='__main__':main()
