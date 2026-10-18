"""Bounded research invocation of a pinned FGT checkout, never a product adapter.

The parent supplies frame directories only; no hidden-background truth is read.
Compatibility patches and every imported checkout byte are frozen in the request.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import time
import traceback


def digest(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(request, response):
    root = Path(request['project_root'])
    runtime = root/'product/.runtime'
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false',
                      TEMP=str(runtime/'temp'), TMP=str(runtime/'temp'), PYTHONDONTWRITEBYTECODE='1')
    sys.path.insert(0, str(root/'product/src'))
    from ai_ad_editor.rvm_worker import install_network_guard
    events = []
    install_network_guard(events)
    response.update(network='disabled', blocked_network_events=events)
    for item in request['frozen_files']:
        if digest(item['path']) != item['sha256']:
            raise RuntimeError('FGT_RESEARCH_INPUT_CHANGED: ' + item['path'])
    source = Path(request['source_root'])
    for directory in (source/'LAFC', source/'FGT', source, source/'tool'):
        sys.path.insert(0, str(directory))
    import argparse
    import numpy as np
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('FGT_CUDA_REQUIRED_NO_FALLBACK')
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.cuda.reset_peak_memory_stats()
    torch.manual_seed(0)
    safe_load = torch.load
    allowed = {str(Path(x).resolve()) for x in request['model_files']}
    loaded = []

    def load(path, *args, **kwargs):
        if str(Path(path).resolve()) not in allowed:
            raise RuntimeError('FGT_UNDECLARED_CHECKPOINT')
        kwargs['weights_only'] = True
        value = safe_load(path, *args, **kwargs)
        loaded.append({'file': Path(path).name, 'weights_only': True})
        return value

    torch.load = load
    module = importlib.import_module('video_inpainting')
    calls = {'RAFT': 0, 'LAFC': 0, 'FGT': 0}
    # Count genuine module forwards; a count is not a quality or timing score.
    for name, label in [('initialize_RAFT', 'RAFT'), ('initialize_LAFC', 'LAFC'), ('initialize_FGT', 'FGT')]:
        initialize = getattr(module, name)

        def wrapped(*args, _initialize=initialize, _label=label, **kwargs):
            result = _initialize(*args, **kwargs)
            model = result[0] if isinstance(result, tuple) else result
            model.eval()

            def count(_module, _inputs):
                calls[_label] += 1
                if calls[_label] == 1 or calls[_label] % 10 == 0:
                    print(json.dumps({'stage': _label, 'model_calls': calls[_label]}), flush=True)

            model.register_forward_pre_hook(count)
            return result

        setattr(module, name, wrapped)
    args = argparse.Namespace(
        opt=request['options_path'], path=request['frames_path'], path_mask=request['masks_path'],
        outroot=request['output_path'], mode='object_removal', consistencyThres=5., alpha=.1,
        Nonlocal=False, raft_model=request['model_files'][0], small=False, mixed_precision=False,
        alternate_corr=False, lafc_ckpts=request['lafc_root'], fgt_ckpts=request['fgt_root'],
        H_scale=2., W_scale=2., imgH=request['height'], imgW=request['width'],
        flow_mask_dilates=12, frame_dilates=0, gpu=0, step=10, num_ref=-1, neighbor_stride=5,
        vis_flows=False, vis_completed_flows=False, vis_prop=False, vis_frame=False)
    module.video_inpainting(args)
    value = np.load(Path(request['output_path'])/'raw-result.npy', allow_pickle=False)
    if value.dtype != np.uint8 or list(value.shape) != [request['frames'], request['height'], request['width'], 3]:
        raise RuntimeError('FGT_RAW_OUTPUT_INVALID')
    for item in request['frozen_files']:
        if digest(item['path']) != item['sha256']:
            raise RuntimeError('FGT_RESEARCH_INPUT_CHANGED_AFTER_EXECUTION')
    response.update(status='succeeded', raw_sha256=digest(Path(request['output_path'])/'raw-result.npy'),
                    model_calls=calls, loaded_checkpoints=loaded,
                    versions={'python':sys.version.split()[0], 'torch':torch.__version__, 'numpy':np.__version__},
                    cuda_device=torch.cuda.get_device_name(), cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    source_frame_count=request['frames'], no_production_adapter=True,
                    quality_accepted=False)


def main():
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    response = {'status':'failed', 'research_only':True}
    started = time.monotonic()
    try:
        run(request, response)
    except Exception as error:
        response.update(error=type(error).__name__+': '+str(error), traceback=traceback.format_exc())
        print(response['traceback'], file=sys.stderr, flush=True)
    response['elapsed_seconds'] = time.monotonic()-started
    Path(request['response']).write_text(json.dumps(response, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return 0 if response['status']=='succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
