"""Exercise installed/native CUDA admission without a model or network request."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def run(source, runtime, output, allocation_mib):
    source=source.resolve(strict=True);runtime=runtime.resolve();output=output.resolve()
    if output.exists():raise ValueError('fresh native evidence output required')
    if type(allocation_mib) is not int or not 0<=allocation_mib<=256:raise ValueError('small allocation budget 0..256 MiB required')
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(Path(__file__),output.with_suffix('.executed.py'))
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'source':str(source),'runtime':str(runtime),'native_python':sys.executable,
        'python':sys.version.split()[0],'allocation_mib':allocation_mib,
        'model_forward_calls':0,'model_weights_loaded':False,'network':'disabled',
        'virtualization':False,'browser':False,'other_user_processes_modified':False,
        'generator_sha256':sha(Path(__file__))}
    def save():output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    save();started=time.monotonic();events=[];tensor=None
    try:
        os.environ['AI_AD_EDITOR_RUNTIME_DIR']=str(runtime)
        sys.path.insert(0,str(source))
        from ai_ad_editor.runtime import configure_local_runtime
        configure_local_runtime()
        from ai_ad_editor.rvm_worker import install_network_guard
        install_network_guard(events)
        from ai_ad_editor import cuda_admission
        from ai_ad_editor.cuda_admission import HEADROOM_BYTES,CudaAdmissionError,admit_cuda
        from ai_ad_editor.vace_model import load_predictor
        record['implementation_sha256']={name:sha(source/'ai_ad_editor'/name) for name in
            ('cuda_admission.py','vace_model.py','vace_worker.py','local_vace.py','local_matting.py')}
        record['imported_admission']=str(Path(cuda_admission.__file__).resolve())
        if Path(cuda_admission.__file__).resolve()!=source/'ai_ad_editor/cuda_admission.py':
            raise ValueError('native probe imported the wrong product source')
        record['stage']='importing-existing-native-torch';save()
        import torch
        if not torch.cuda.is_available():raise ValueError('native CUDA unavailable')
        torch.set_num_threads(2);torch.cuda.reset_peak_memory_stats()
        allocation_bytes=allocation_mib*1024**2
        record['torch']=torch.__version__;record['device']=torch.cuda.get_device_name(0)
        record['torch_uuid_type']=str(type(torch.cuda.get_device_properties(0).uuid))
        record['stage']='sampling-before-small-allocation';save()
        before=admit_cuda(torch,HEADROOM_BYTES+allocation_bytes,'native-before-allocation')
        record['before_allocation']=before
        allocated_before=torch.cuda.memory_allocated(0)
        if allocation_bytes:
            tensor=torch.zeros(allocation_bytes//4,dtype=torch.float32,device='cuda')
            torch.cuda.synchronize()
        record['actual_allocation_bytes']=torch.cuda.memory_allocated(0)-allocated_before
        if record['actual_allocation_bytes']!=allocation_bytes:raise ValueError('native allocation byte count differs')
        record['after_allocation']=admit_cuda(torch,HEADROOM_BYTES,'native-after-allocation',expected_uuid=before['device_uuid'])
        tensor=None;gc.collect();torch.cuda.synchronize()
        record['after_release']=admit_cuda(torch,HEADROOM_BYTES,'native-after-release',expected_uuid=before['device_uuid'])
        record['allocation_released']=torch.cuda.memory_allocated(0)==allocated_before
        if not record['allocation_released']:raise ValueError('native small allocation retained')
        record['stage']='rejecting-impossible-text-weight-budget';save()
        phases=[];components_before={name:name in sys.modules for name in ('diffusers','accelerate','transformers')}
        try:
            load_predictor(runtime/'nonexistent-model-must-not-be-opened',
                {'text_gpu_budget_mib':65536,'text_cpu_budget_mib':8192}, {}, progress=phases.append)
            raise AssertionError('impossible physical text budget was admitted')
        except CudaAdmissionError as exc:
            record['expected_budget_rejection']=exc.report
            if exc.report.get('error_code')!='CUDA_ADMISSION_INSUFFICIENT_PHYSICAL_FREE':raise
        if phases!=['admitting-text-gpu-memory']:raise ValueError('model loader progressed past admission')
        components_after={name:name in sys.modules for name in components_before}
        if components_before!=components_after:raise ValueError('model component imported after impossible budget')
        record.update(status='passed_native_cuda_sampling_allocation_and_loader_rejection',
            loader_phases=phases,components_before=components_before,components_after=components_after,
            cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
            reservation=False,oom_guarantee=False,quality_acceptance=False)
    except Exception as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc))
        if hasattr(exc,'report'):record['admission_failure']=exc.report
    finally:
        tensor=None
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,
                      blocked_network_events=events)
        save()
    print(json.dumps({k:record.get(k) for k in ('status','actual_allocation_bytes','allocation_released','elapsed_seconds')},ensure_ascii=False))
    return 0 if record['status']=='passed_native_cuda_sampling_allocation_and_loader_rejection' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'product/src')
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allocation-mib',type=int,default=128)
    args=parser.parse_args();raise SystemExit(run(args.source,args.runtime,args.output,args.allocation_mib))
