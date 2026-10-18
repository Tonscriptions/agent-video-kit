"""Staged native CUDA loading of existing fixed Wan VACE components."""
from __future__ import annotations

import gc
from pathlib import Path
import time


def load_predictor(model_path, settings, generation, *, progress=None):
    # Imports happen only inside the isolated network-guarded worker.
    import torch
    from .cuda_admission import HEADROOM_BYTES, POLICY, admit_cuda, record_window, window_summary

    started=time.monotonic();root=Path(model_path)
    def phase(name):
        if progress:progress(name)
    phase('admitting-text-gpu-memory')
    text_check=admit_cuda(torch,settings['text_gpu_budget_mib']*1024**2+HEADROOM_BYTES,'text-weights')
    import accelerate
    from accelerate.hooks import remove_hook_from_module
    import diffusers
    import numpy as np
    from PIL import Image
    import safetensors
    import transformers
    from transformers import AutoTokenizer, UMT5Config, UMT5EncoderModel
    from diffusers import AutoencoderKLWan, UniPCMultistepScheduler, WanVACEPipeline, WanVACETransformer3DModel

    phase('tokenizing-local-prompt')
    tokenizer=AutoTokenizer.from_pretrained(str(root/'tokenizer'),local_files_only=True,trust_remote_code=False)
    token_count={}
    def tokens(text,name):
        plain=tokenizer(text,add_special_tokens=True,truncation=False)['input_ids']
        token_count[name]=len(plain)
        if len(plain)>generation['prompt_max_tokens']:raise ValueError('VACE_PROMPT_TOKEN_BUDGET_EXCEEDED_NO_TRUNCATION: '+name)
        return tokenizer(text,padding='max_length',max_length=generation['prompt_max_tokens'],truncation=False,return_attention_mask=True,return_tensors='pt')
    positive=tokens(generation['prompt'],'prompt');negative=tokens(generation['negative_prompt'],'negative_prompt')
    phase('loading-local-text-encoder')
    config=UMT5Config.from_pretrained(str(root/'text_encoder'),local_files_only=True)
    with torch.device('meta'):
        skeleton=UMT5EncoderModel(config)
    needed=sum(p.numel() for p in skeleton.parameters())*2;del skeleton
    if needed>(settings['text_gpu_budget_mib']+settings['text_cpu_budget_mib'])*1024**2:
        raise ValueError('VACE_TEXT_WEIGHT_BUDGET_INSUFFICIENT_NO_DISK_FALLBACK')
    encoder,loading=UMT5EncoderModel.from_pretrained(str(root/'text_encoder'),dtype=torch.bfloat16,local_files_only=True,use_safetensors=True,
        device_map='auto',max_memory={0:settings['text_gpu_budget_mib']*1024**2,'cpu':settings['text_cpu_budget_mib']*1024**2},
        low_cpu_mem_usage=True,output_loading_info=True)
    if loading.get('missing_keys') or loading.get('unexpected_keys') or loading.get('mismatched_keys') or loading.get('error_msgs'):
        raise ValueError('VACE_TEXT_WEIGHT_LOADING_MISMATCH: '+str(loading))
    placement={k:str(v) for k,v in encoder.hf_device_map.items()}
    if any(v=='disk' for v in placement.values()):raise ValueError('VACE_TEXT_DISK_FALLBACK_FORBIDDEN')
    encoder.eval();phase('encoding-local-prompt')
    def encode(value):
        with torch.inference_mode():
            encoded=encoder(value.input_ids.to('cuda'),attention_mask=value.attention_mask.to('cuda')).last_hidden_state
            length=int(value.attention_mask.sum())
            result=encoded.detach().to('cpu',dtype=torch.bfloat16)
            result[:,length:]=0
            return result
    prompt_embeds=encode(positive);negative_embeds=encode(negative)
    phase('releasing-local-text-encoder')
    remove_hook_from_module(encoder,recurse=True)
    del encoder,positive,negative
    gc.collect();torch.cuda.synchronize();torch.cuda.empty_cache()
    text_seconds=time.monotonic()-started
    phase('loading-local-video-transformer-and-vae')
    transformer,loading=WanVACETransformer3DModel.from_pretrained(str(root/'transformer'),local_files_only=True,use_safetensors=True,
                                                                torch_dtype=torch.bfloat16,low_cpu_mem_usage=True,output_loading_info=True)
    if any(loading.get(k) for k in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')):raise ValueError('VACE_TRANSFORMER_WEIGHT_LOADING_MISMATCH: '+str(loading))
    vae,loading=AutoencoderKLWan.from_pretrained(str(root/'vae'),local_files_only=True,use_safetensors=True,
                                                torch_dtype=torch.float32,low_cpu_mem_usage=True,output_loading_info=True)
    if any(loading.get(k) for k in ('missing_keys','unexpected_keys','mismatched_keys','error_msgs')):raise ValueError('VACE_VAE_WEIGHT_LOADING_MISMATCH: '+str(loading))
    scheduler=UniPCMultistepScheduler.from_pretrained(str(root/'scheduler'),local_files_only=True)
    scheduler=UniPCMultistepScheduler.from_config(scheduler.config,flow_shift=generation['flow_shift'])
    transformer.eval();vae.eval();vae.enable_tiling()
    pipe=WanVACEPipeline(tokenizer=tokenizer,text_encoder=None,transformer=transformer,vae=vae,scheduler=scheduler)
    video_weight_bytes=sum(value.numel()*value.element_size() for model in (transformer,vae)
                           for values in (model.parameters(),model.buffers()) for value in values)
    prompt_embedding_bytes=sum(value.numel()*value.element_size() for value in (prompt_embeds,negative_embeds))
    phase('admitting-video-gpu-memory')
    video_check=admit_cuda(torch,video_weight_bytes+prompt_embedding_bytes+HEADROOM_BYTES,'video-weights',
                          expected_uuid=text_check['device_uuid'])
    pipe.to('cuda');pipe.set_progress_bar_config(disable=True)
    stability=tuple(transformer._keep_in_fp32_modules)
    dtypes={}
    for name,p in transformer.named_parameters():
        allowed={torch.bfloat16,torch.float32} if any(part in stability for part in name.split('.')) else {torch.bfloat16}
        if p.device.type!='cuda' or p.dtype not in allowed:raise ValueError('VACE_TRANSFORMER_DEVICE_OR_PRECISION_MISMATCH: '+name)
        dtypes[str(p.dtype)]=dtypes.get(str(p.dtype),0)+p.numel()
    if any(p.device.type!='cuda' or p.dtype!=torch.float32 for p in vae.parameters()):raise ValueError('VACE_VAE_DEVICE_OR_PRECISION_MISMATCH')
    metadata={'versions':{'python':__import__('sys').version.split()[0],'numpy':np.__version__,'torch':torch.__version__,'diffusers':diffusers.__version__,
                         'transformers':transformers.__version__,'accelerate':accelerate.__version__,'safetensors':safetensors.__version__},
              'text_device_map':placement,'text_weight_bytes_bfloat16':needed,'text_encoder_released_before_generation':True,
              'text_offload_hooks_removed_before_generation':True,
              'prompt_token_counts':token_count,'prompt_truncated':False,'prompt_extension':False,'text_phase_seconds':text_seconds,
              'load_seconds':time.monotonic()-started,'cuda_device':torch.cuda.get_device_name(0),'cuda_total_bytes':text_check['torch_total_bytes'],
              'gpu_admission':{'policy':POLICY,'reservation':False,'oom_guarantee':False,'headroom_bytes':HEADROOM_BYTES,
                               'text':text_check,'video':video_check,'video_weight_bytes':video_weight_bytes,
                               'prompt_embedding_bytes':prompt_embedding_bytes,'windows':window_summary()},
              'transformer_precision':'bfloat16-with-declared-float32-stability-modules','transformer_parameter_dtype_elements':dtypes,
              'float32_stability_modules':list(stability),'vae_precision':'float32','vae_spatial_tiling':True,'window_seconds':[],
              'flow_shift':float(scheduler.config.flow_shift),'model_input_scale':generation['model_input_scale'],
              'window_input_shapes':[]}
    def predict(images,masks,window_generation):
        if {k:v for k,v in window_generation.items() if k!='seed'}!={k:v for k,v in generation.items() if k!='seed'}:raise ValueError('VACE_GENERATION_SETTINGS_CHANGED')
        phase('admitting-video-window-gpu-memory')
        summary=metadata['gpu_admission']['windows']
        check=admit_cuda(torch,HEADROOM_BYTES,'video-window-'+str(summary['count']+1),expected_uuid=text_check['device_uuid'])
        record_window(summary,check)
        phase('joint-video-denoising');begin=time.monotonic()
        def step_callback(_pipe,_step,_time,kwargs):
            phase('joint-video-denoising-step-'+str(_step+1));return kwargs
        with torch.inference_mode():
            value=pipe(video=[Image.fromarray(x) for x in images],mask=[Image.fromarray(x).convert('RGB') for x in masks],
                prompt_embeds=prompt_embeds.to('cuda'),negative_prompt_embeds=negative_embeds.to('cuda'),
                height=images.shape[1],width=images.shape[2],num_frames=len(images),
                num_inference_steps=window_generation['inference_steps'],guidance_scale=window_generation['guidance_scale'],
                conditioning_scale=window_generation['conditioning_scale'],generator=torch.Generator(device='cuda').manual_seed(window_generation['seed']),
                max_sequence_length=window_generation['prompt_max_tokens'],output_type='np',callback_on_step_end=step_callback).frames[0]
        metadata['window_seconds'].append(time.monotonic()-begin)
        metadata['window_input_shapes'].append(list(images.shape[:3]))
        return np.asarray(value,dtype=np.float32)
    phase('local-video-model-ready')
    return predict,metadata
