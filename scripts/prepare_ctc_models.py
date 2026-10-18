"""Development-only pinned raw weights -> offline safetensors-only bundles.

Run with the already installed native Torch Python. Never installs a package,
fetches a model, imports repository code, or exposes pickle to product runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(4*1024*1024):h.update(chunk)
    return h.hexdigest()


def main(args):
    source, output, evidence = args.source.resolve(), args.output.resolve(), args.evidence.resolve()
    assert source.is_relative_to(ROOT/'product/.runtime') and output.is_relative_to(ROOT/'product/.runtime')
    evidence.parent.mkdir(parents=True, exist_ok=True)
    assert not output.exists() and not evidence.exists()
    metadata=json.loads((ROOT/'docs/validation/evidence/ctc-model-mirror-source-20261018/inspection.json').read_text(encoding='utf-8'))['models'][args.language]
    names=['config.json','preprocessor_config.json','special_tokens_map.json','vocab.json']
    names+=['tokenizer_config.json','model.safetensors'] if args.language=='en' else ['pytorch_model.bin']
    record={'language':args.language,'repository':metadata['repository'],'revision':metadata['revision'],
        'declared_model_license':metadata['license_declared'],'runtime_downloads':False,'source_files':[],
        'generator_sha256':digest(Path(__file__)),'weights_executed_for_inference':False}
    def save():evidence.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        for name in names:
            path=source/name
            expected=next(f for f in metadata['files'] if f['rfilename']==name)
            value=digest(path)
            assert path.stat().st_size==expected['size']
            if expected.get('lfs'):assert value==expected['lfs']['sha256']
            else:
                h=hashlib.sha1(('blob '+str(path.stat().st_size)+'\0').encode());h.update(path.read_bytes())
                assert h.hexdigest()==expected['blobId']
            record['source_files'].append({'name':name,'bytes':path.stat().st_size,'sha256':value})
        output.mkdir(parents=True,exist_ok=False)
        for name in names:
            if name.endswith('.json'):shutil.copyfile(source/name,output/name)
        if args.language=='en':
            shutil.copyfile(source/'model.safetensors',output/'model.safetensors')
            record['conversion']='none; source safetensors copied exactly'
        else:
            runtime=ROOT/'product/.runtime/ctc-conversion-cache'
            runtime.mkdir(exist_ok=True)
            for key in ('TEMP','TMP','TMPDIR','HF_HOME','TORCH_HOME','XDG_CACHE_HOME'):os.environ[key]=str(runtime)
            sys.path.insert(0,str(ROOT/'product/src'))
            from ai_ad_editor.whisper_worker import install_network_guard
            blocked=[];install_network_guard(blocked)
            import torch
            from safetensors.torch import save_file
            started=time.monotonic()
            # Exact pinned SHA checked above before any deserialization.
            state=torch.load(str(source/'pytorch_model.bin'),map_location='cpu',weights_only=True,mmap=True)
            assert isinstance(state,dict) and state and all(isinstance(k,str) and isinstance(v,torch.Tensor) for k,v in state.items())
            save_file(state,str(output/'model.safetensors'),metadata={'format':'pt'})
            assert not blocked
            tokenizer={'tokenizer_class':'Wav2Vec2CTCTokenizer','do_lower_case':False,'word_delimiter_token':'|',
                'bos_token':'<s>','eos_token':'</s>','unk_token':'<unk>','pad_token':'<pad>'}
            (output/'tokenizer_config.json').write_text(json.dumps(tokenizer,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            record.update(conversion='torch.load(weights_only=True,mmap=True,cpu) -> safetensors.save_file',
                converted_tensors=len(state),conversion_seconds=round(time.monotonic()-started,3),torch_version=torch.__version__,
                blocked_network_events=blocked,generated_tokenizer_configuration=tokenizer)
        record.update(status='verified',output_files=[{'name':p.name,'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(output.iterdir())])
        save()
        print(json.dumps({'status':record['status'],'language':args.language,'files':len(record['output_files'])}))
    except Exception as exc:
        record.update(status='failed',error=repr(exc));save();raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True);p.add_argument('--language',choices=['en','zh'],required=True)
    main(p.parse_args())
