"""Integrate the reviewed reader candidate only after the old frozen suite ends."""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/video-outpainting-20261019-v66'


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()


def one(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new,1)


def main():
    old=frozen();full=json.loads((BASE/'full-r1.json').read_bytes())
    assert full['terminal_ok'] and full['exit_code']==0 and full['methods']==1454 and full['skipped']==0
    assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==old and len(old)==200
    prototype=BASE/'reader-candidate-r1'
    receipt=json.loads((prototype/'verification-r1.json').read_bytes())
    assert receipt['status']=='passed_contract_prototype_only' and receipt['methods']==8
    for name,entry in receipt['files'].items():assert digest((prototype/name).read_bytes())==entry['sha256']
    for name in ('vace-harmonic-r2','vace-harmonic-r3'):
        failure=json.loads((BASE/name/'verification.json').read_bytes())
        assert failure['status']=='failed' and failure['frozen_equal'] and failure['frozen_after']==old
    source=(prototype/'weight_reader.py').read_text(encoding='utf8')
    tree=ast.parse(source)
    pieces=[ast.get_source_segment(source,node) for node in tree.body
            if isinstance(node,(ast.Assign,ast.FunctionDef))]
    helper='\n\n\n'.join(pieces)
    tests=(prototype/'test_weight_reader.py').read_text(encoding='utf8')
    test_class=next(ast.get_source_segment(tests,node) for node in ast.parse(tests).body if isinstance(node,ast.ClassDef))
    updates={}
    p=ROOT/'product/src/ai_ad_editor/vace_model.py';text=p.read_text(encoding='utf8')
    text=one(text,'import gc\n','import gc\nimport threading\n')
    text=one(text,'def load_predictor(',helper+'\n\n\ndef load_predictor(')
    text=one(text,'started=time.monotonic();root=Path(model_path)','started=time.monotonic();root=Path(model_path);read_report=[]')
    text=one(text,"encoder,loading=UMT5EncoderModel.from_pretrained(str(root/'text_encoder'),", "encoder,loading=load_local_weights(UMT5EncoderModel.from_pretrained,root/'text_encoder',read_report=read_report,")
    text=one(text,"transformer,loading=WanVACETransformer3DModel.from_pretrained(str(root/'transformer'),", "transformer,loading=load_local_weights(WanVACETransformer3DModel.from_pretrained,root/'transformer',read_report=read_report,")
    text=one(text,"vae,loading=AutoencoderKLWan.from_pretrained(str(root/'vae'),", "vae,loading=load_local_weights(AutoencoderKLWan.from_pretrained,root/'vae',read_report=read_report,")
    text=one(text,"'text_device_map':placement,", "'local_weight_reads':read_report,'text_device_map':placement,")
    updates[p]=text
    p=ROOT/'product/src/ai_ad_editor/local_matting.py';text=p.read_text(encoding='utf8')
    text=one(text,"                    from .cuda_admission import validate_execution\n", "                    from .vace_model import validate_weight_reads\n                    validate_weight_reads(execution.get('local_weight_reads'))\n                    from .cuda_admission import validate_execution\n")
    updates[p]=text
    p=ROOT/'product/tests/test_local_vace.py';text=p.read_text(encoding='utf8')
    text=one(text,'import unittest\n','import unittest\nfrom types import ModuleType\n')
    text=one(text,'from ai_ad_editor.vace_frames import process_frames\n', 'from ai_ad_editor.vace_model import WEIGHT_FILES, load_local_weights, validate_weight_reads\nfrom ai_ad_editor.vace_frames import process_frames\n') if text.count('from ai_ad_editor.vace_frames import process_frames\n')==1 else text.replace('from ai_ad_editor.vace_frames import process_frames\n','from ai_ad_editor.vace_model import WEIGHT_FILES, load_local_weights, validate_weight_reads\nfrom ai_ad_editor.vace_frames import process_frames\n',1)
    marker="response['model_execution']['text_offload_hooks_removed_before_generation']=True\n"
    extra=("from ai_ad_editor.vace_model import WEIGHT_FILES\n"
           "response['model_execution']['local_weight_reads']=[{'component':component,'backend':'pread',"
           "'files':[{'path':component+'/'+name,'opens':1} for name in sorted(names)]} for component,names in WEIGHT_FILES.items()]\n")
    text=one(text,marker,marker+extra)
    marker="if mode=='bad_text_hooks':response['model_execution']['text_offload_hooks_removed_before_generation']=False\n"
    extra=("if mode=='missing_reads':response['model_execution'].pop('local_weight_reads')\n"
           "if mode=='bad_read_backend':response['model_execution']['local_weight_reads'][0]['backend']='mmap'\n"
           "if mode=='bad_read_inventory':response['model_execution']['local_weight_reads'][0]['files'].pop()\n"
           "if mode=='bad_read_count':response['model_execution']['local_weight_reads'][0]['files'][0]['opens']=True\n"
           "if mode=='bad_read_duplicate':response['model_execution']['local_weight_reads'][1]=response['model_execution']['local_weight_reads'][0]\n")
    text=one(text,marker,marker+extra)
    text=one(text,"'bad_gpu_cache','bad_text_hooks','fail'):","'bad_gpu_cache','bad_text_hooks','missing_reads','bad_read_backend','bad_read_inventory','bad_read_count','bad_read_duplicate','fail'):")
    assert 'class LocalWeightReaderTests' not in text
    guard="if __name__=='__main__':unittest.main()"
    if guard in text:text=one(text,guard,test_class+'\n\n\n'+guard)
    else:
        assert '__main__' not in text
        text=text.rstrip()+'\n\n\n'+test_class+'\n'
    updates[p]=text
    assert len(updates)==3
    for path,text in updates.items():ast.parse(text,filename=str(path))
    history=BASE/'pre-pread-source';history.mkdir(exist_ok=False)
    archive=history/'source-snapshot.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for relative,sha in old.items():
            raw=(ROOT/relative).read_bytes();assert digest(raw)==sha;bundle.writestr(relative,raw)
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None and set(bundle.namelist())==set(old)
        for relative,sha in old.items():assert digest(bundle.read(relative))==sha
    save(history/'source-snapshot.json',{'status':'archived_exact_before_reader_change','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'files':old,'archive_sha256':digest(archive.read_bytes()),'archive_bytes':archive.stat().st_size,
        'terminal_regression_sha256':digest((BASE/'full-r1.json').read_bytes()),'methods':1454})
    assert frozen()==old
    for path,text in updates.items():path.write_text(text,encoding='utf8',newline='\n')
    after=frozen();changed={name:{'before':old[name],'after':after[name]} for name in old if old[name]!=after[name]}
    assert len(after)==200 and set(changed)=={p.relative_to(ROOT).as_posix() for p in updates}
    methods=sum(isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_')
                for path in (ROOT/'product/tests').glob('test*.py') for node in ast.walk(ast.parse(path.read_text(encoding='utf8'))))
    assert methods==1462
    save(history/'integration.json',{'status':'integrated_after_old_suite_terminal','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'prototype_sha256':digest((prototype/'weight_reader.py').read_bytes()),'changed_files':changed,
        'before':old,'after':after,'methods_from_ast':methods,'raw_native_dependency_files_modified':False,
        'quality_parameters_modified':False,'new_model_forward_verified':False})
    print(json.dumps({'changed_files':list(changed),'frozen_files':len(after),'test_methods':methods}))


if __name__=='__main__':main()
