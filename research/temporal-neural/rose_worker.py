"""Real, offline ROSE research inference; no hidden-background truth is read.

Uses pinned author architectures and strict checkpoint assignment. Text loading
is staged to fit a native 12 GiB GPU, then released before joint-video inference.
"""
from __future__ import annotations

import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while data := stream.read(8 * 1024**2):
            h.update(data)
    return 'sha256:' + h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                          encoding='utf-8', newline='\n')


def run(request, response):
    root = Path(request['project_root'])
    sys.path.insert(0, str(root/'product/src'))
    os.environ['AI_AD_EDITOR_RUNTIME_DIR'] = str(root/'product/.runtime')
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    from ai_ad_editor.rvm_worker import install_network_guard
    events = []
    install_network_guard(events)
    response.update(network='disabled', blocked_network_events=events, model_calls={
        'T5': 0, 'T5_blocks': 0, 'transformer': 0, 'transformer_blocks': 0,
        'VAE_encode': 0, 'VAE_decode': 0, 'CLIP': 0})
    calls = response['model_calls']
    response['phases'] = []
    started = time.monotonic()

    def phase(name, **details):
        row = {'phase': name, 'seconds': time.monotonic()-started, **details}
        response['phases'].append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        save(request['response'], response)

    def verify():
        for row in request['frozen_files']:
            path = Path(row['path'])
            if not path.is_file() or sha(path) != row['sha256']:
                raise RuntimeError('ROSE_RESEARCH_INPUT_CHANGED: '+str(path))

    phase('verifying-frozen-local-inputs')
    verify()
    if request.get('clip_reference') is not None:
        raise ValueError('ROSE_REFERENCE_IMAGE_UNSUPPORTED_NO_ZERO_CONTEXT_SUBSTITUTION')
    if request['options'] != {'steps': 50, 'guidance': 6.0, 'seed': 0, 'prompt': '', 'negative_prompt': '',
                              'text_dtype': 'bfloat16', 'transformer_dtype': 'bfloat16',
                              'time_embedding_dtype': 'float32', 'vae_dtype': 'float32',
                              'text_gpu_budget_mib': 7168, 'text_cpu_budget_mib': 8192}:
        raise ValueError('ROSE_PREDECLARED_FIRST_RUN_OPTIONS_CHANGED')
    import accelerate
    import diffusers
    import numpy as np
    from safetensors.torch import load_file
    import safetensors
    import torch
    import transformers
    import yaml
    if not torch.cuda.is_available():
        raise RuntimeError('ROSE_NATIVE_CUDA_REQUIRED_NO_FALLBACK')
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.cuda.reset_peak_memory_stats()
    torch.manual_seed(0)
    response['versions'] = {'python': sys.version.split()[0], 'torch': torch.__version__,
        'numpy': np.__version__, 'diffusers': diffusers.__version__, 'transformers': transformers.__version__,
        'accelerate': accelerate.__version__, 'safetensors': safetensors.__version__}
    response['cuda_device'] = torch.cuda.get_device_name(0)
    response['cuda_free_before_bytes'], response['cuda_total_bytes'] = torch.cuda.mem_get_info()
    if response['cuda_free_before_bytes'] < (7168+1024)*1024**2:
        raise RuntimeError('ROSE_EXPLICIT_TEXT_GPU_BUDGET_UNAVAILABLE')
    source = Path(request['source_root'])
    sys.path.insert(0, str(source))
    from rose.models import WanT5EncoderModel, WanTransformer3DModel, AutoencoderKLWan
    from rose.pipeline.pipeline_wan_fun_inpaint import WanFunInpaintPipeline
    from diffusers import FlowMatchEulerDiscreteScheduler
    bundle = Path(request['bundle_root'])
    config = yaml.safe_load((source/'configs/wan2.1/wan_civitai.yaml').read_text(encoding='utf-8'))
    options = request['options']
    response['loaded_checkpoints'] = []

    def assign(model, state, label):
        if not state or not all(isinstance(v, torch.Tensor) for v in state.values()):
            raise RuntimeError('ROSE_STATE_DICT_NOT_FLAT_TENSORS: '+label)
        metadata = {'component': label, 'tensor_count': len(state),
                    'elements': sum(v.numel() for v in state.values()), 'dtype_elements': {}}
        for tensor in state.values():
            key = str(tensor.dtype)
            metadata['dtype_elements'][key] = metadata['dtype_elements'].get(key, 0)+tensor.numel()
        result = model.load_state_dict(state, strict=True, assign=True)
        if result.missing_keys or result.unexpected_keys or any(p.is_meta for p in model.parameters()):
            raise RuntimeError('ROSE_STRICT_WEIGHT_ASSIGNMENT_FAILED: '+label)
        metadata.update(missing_keys=[], unexpected_keys=[], strict=True, assigned=True)
        response['loaded_checkpoints'].append(metadata)
        return model.eval()

    def count(label):
        def hook(*_args):
            calls[label] += 1
            if label == 'transformer' and (calls[label] == 1 or calls[label] % 5 == 0):
                phase('denoising-forward', completed_forwards=calls[label], expected_forwards=options['steps'])
        return hook

    phase('loading-local-tokenizer-and-meta-text-encoder')
    tokenizer = transformers.AutoTokenizer.from_pretrained(str(bundle/'base/google/umt5-xxl'),
        local_files_only=True, trust_remote_code=False)
    text_config = {k: config['text_encoder_kwargs'][k] for k in
                   ('vocab', 'dim', 'dim_attn', 'dim_ffn', 'num_heads', 'num_layers',
                    'num_buckets', 'shared_pos', 'dropout')}
    with accelerate.init_empty_weights(include_buffers=False):
        encoder = WanT5EncoderModel(**text_config)
    text_path = bundle/'base/models_t5_umt5-xxl-enc-bf16.pth'
    state = torch.load(text_path, map_location='cpu', weights_only=True, mmap=True)
    assign(encoder, state, 'T5')
    del state
    encoder.to(dtype=torch.bfloat16)
    device_map = accelerate.infer_auto_device_map(encoder,
        max_memory={0: options['text_gpu_budget_mib']*1024**2, 'cpu': options['text_cpu_budget_mib']*1024**2},
        no_split_module_classes=['T5SelfAttention'], dtype=torch.bfloat16)
    if any(str(v) == 'disk' for v in device_map.values()):
        raise RuntimeError('ROSE_TEXT_DISK_OFFLOAD_FORBIDDEN')
    response['text_device_map'] = {k: str(v) for k, v in device_map.items()}
    encoder = accelerate.dispatch_model(encoder, device_map=device_map, force_hooks=True)
    encoder.register_forward_pre_hook(count('T5'))
    for block in encoder.blocks:
        block.register_forward_pre_hook(count('T5_blocks'))
    del block
    phase('encoding-real-local-text')
    embeddings = []
    response['prompt_tokens'] = []
    # Both author prompts are empty in the first fixed experiment. Execute both
    # actual forwards so no cached or fabricated text feature can enter the run.
    for prompt in (options['prompt'], options['negative_prompt']):
        plain = tokenizer(prompt, truncation=False, add_special_tokens=True)['input_ids']
        if len(plain) > 512:
            raise ValueError('ROSE_PROMPT_BUDGET_EXCEEDED_NO_TRUNCATION')
        tokens = tokenizer([prompt], padding='max_length', max_length=512, truncation=False,
                           add_special_tokens=True, return_attention_mask=True, return_tensors='pt')
        response['prompt_tokens'].append(len(plain))
        with torch.inference_mode():
            encoded = encoder(tokens.input_ids.to('cuda'), attention_mask=tokens.attention_mask.to('cuda'))[0]
        length = int(tokens.attention_mask.sum())
        feature = encoded[0, :length].detach().to('cpu', dtype=torch.bfloat16).clone()
        if not torch.isfinite(feature).all():
            raise RuntimeError('ROSE_TEXT_EMBEDDINGS_NOT_FINITE')
        embeddings.append([feature])
        del encoded, tokens
    # Offload hooks can retain the model; explicitly remove them before release.
    accelerate.hooks.remove_hook_from_module(encoder, recurse=True)
    del encoder, tokenizer
    gc.collect()
    torch.cuda.synchronize()
    torch.cuda.empty_cache()
    response['text_encoder_released_before_generation'] = True
    response['cuda_allocated_after_text_release_bytes'] = torch.cuda.memory_allocated()

    phase('strict-loading-local-transformer-and-vae')
    transformer_config = json.loads((bundle/'transformer/config.json').read_bytes())
    with accelerate.init_empty_weights(include_buffers=False):
        transformer = WanTransformer3DModel.from_config(transformer_config)
    # Rotary tables are deliberately ordinary complex tensors, not parameters.
    if transformer.freqs.is_meta:
        raise RuntimeError('ROSE_ROTARY_TABLE_MUST_BE_REAL_NOT_META')
    state = load_file(str(bundle/'transformer/diffusion_pytorch_model.safetensors'), device='cpu')
    assign(transformer, state, 'ROSE-transformer')
    del state
    transformer.to(device='cuda', dtype=torch.bfloat16)
    transformer.time_embedding.float()
    transformer.time_projection.float()
    if transformer.sp_world_size != 1 or transformer.teacache is not None:
        raise RuntimeError('ROSE_APPROXIMATION_OR_DISTRIBUTED_PATH_FORBIDDEN')
    transformer.register_forward_pre_hook(count('transformer'))
    for block in transformer.blocks:
        block.register_forward_pre_hook(count('transformer_blocks'))
    with accelerate.init_empty_weights(include_buffers=False):
        vae = AutoencoderKLWan(latent_channels=16, temporal_compression_ratio=4,
                              spacial_compression_ratio=8)
    state = torch.load(bundle/'base/Wan2.1_VAE.pth', map_location='cpu', weights_only=True, mmap=True)
    assign(vae, {'model.'+key: value for key, value in state.items()}, 'Wan-VAE')
    del state
    vae.to(device='cuda', dtype=torch.float32)
    original_encode, original_decode = vae.encode, vae.decode

    def encode(*args, **kwargs):
        calls['VAE_encode'] += 1
        phase('vae-encode', input_shape=list(args[0].shape))
        return original_encode(*args, **kwargs)

    def decode(*args, **kwargs):
        calls['VAE_decode'] += 1
        phase('vae-decode', latent_shape=list(args[0].shape))
        return original_decode(*args, **kwargs)

    vae.encode, vae.decode = encode, decode
    scheduler_config = {k: v for k, v in config['scheduler_kwargs'].items() if k != 'scheduler_subpath'}
    scheduler = FlowMatchEulerDiscreteScheduler(**scheduler_config)
    pipe = WanFunInpaintPipeline(tokenizer=None, text_encoder=None, clip_image_encoder=None,
                                transformer=transformer, vae=vae, scheduler=scheduler)
    pipe.set_progress_bar_config(disable=True)
    source_frames = np.load(request['input_path'], allow_pickle=False)
    selection = np.load(request['selection_path'], allow_pickle=False)
    if source_frames.dtype != np.uint8 or source_frames.ndim != 4 or source_frames.shape[-1] != 4:
        raise RuntimeError('ROSE_SOURCE_RGBA_INVALID')
    n, h, w, _ = source_frames.shape
    if n != 32 or h % 16 or w % 16 or selection.shape != (n, h, w) or selection.dtype != bool:
        raise RuntimeError('ROSE_DECLARED_SOURCE_GEOMETRY_INVALID')
    if not selection.any():
        raise RuntimeError('ROSE_RESEARCH_EXPECTS_NONEMPTY_SELECTION')
    padded_rgb = np.concatenate([source_frames[:, :, :, :3], source_frames[-1:, :, :, :3]], axis=0)
    padded_mask = np.concatenate([selection, selection[-1:]], axis=0)
    video = torch.from_numpy(padded_rgb.copy()).permute(3, 0, 1, 2).unsqueeze(0).float()/255.
    mask = torch.from_numpy(padded_mask.astype(np.float32)).unsqueeze(0).unsqueeze(0)
    response['input'] = {'frames': n, 'model_frames': n+1, 'height': h, 'width': w,
        'padding': 'repeat last frame then crop back; no clock resampling', 'original_object_preserved_in_condition': True}
    response['options'] = options
    phase('joint-video-inference', video_shape=list(video.shape), mask_shape=list(mask.shape))
    positive, negative = [[x.to('cuda') for x in value] for value in embeddings]

    def callback(_pipe, step, _time, kwargs):
        if not torch.isfinite(kwargs['latents']).all():
            raise RuntimeError('ROSE_DENOISING_LATENTS_NOT_FINITE_AT_STEP_'+str(step))
        return kwargs

    with torch.inference_mode():
        result = pipe(prompt=None, negative_prompt=None, prompt_embeds=positive,
            negative_prompt_embeds=negative, video=video, mask_video=mask, height=h, width=w,
            num_frames=n+1, num_inference_steps=options['steps'], guidance_scale=options['guidance'],
            generator=torch.Generator(device='cuda').manual_seed(options['seed']),
            output_type='numpy', return_dict=False, max_sequence_length=512,
            callback_on_step_end=callback, callback_on_step_end_tensor_inputs=['latents']).videos
    value = result.detach().cpu().float().numpy()
    if value.shape != (1, 3, n+1, h, w) or not np.isfinite(value).all():
        raise RuntimeError('ROSE_RAW_MODEL_OUTPUT_INVALID: '+str(value.shape))
    # Author output is [0,1]. Quantize only at the declared delivery boundary.
    raw = np.rint(np.clip(value[0, :, :n].transpose(1, 2, 3, 0), 0, 1)*255).astype(np.uint8)
    output = Path(request['output_path'])
    np.save(output/'raw-result.npy', raw, allow_pickle=False)
    response.update(raw_sha256=sha(output/'raw-result.npy'), raw_frames=n,
                    raw_range=[int(raw.min()), int(raw.max())], clip_reference_supplied=False,
                    clip_zero_context_proof='source-backed no-reference branch only',
                    cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved())
    if calls != {'T5': 2, 'T5_blocks': 48, 'transformer': options['steps'],
                 'transformer_blocks': options['steps']*30, 'VAE_encode': 1, 'VAE_decode': 1, 'CLIP': 0}:
        raise RuntimeError('ROSE_ACTUAL_FORWARD_COUNTS_MISMATCH: '+str(calls))
    del pipe, transformer, vae, positive, negative, result, value, original_encode, original_decode
    gc.collect()
    torch.cuda.empty_cache()
    phase('verifying-frozen-inputs-after-inference')
    verify()
    response.update(status='succeeded', research_only=True, product_integrated=False,
                    natural_quality_accepted=False)


def main():
    request = json.loads(Path(sys.argv[1]).read_bytes())
    response = {'status': 'running', 'research_only': True}
    started = time.monotonic()
    try:
        run(request, response)
    except BaseException as error:
        response.update(status='failed', error=type(error).__name__+': '+str(error), traceback=traceback.format_exc())
        print(response['traceback'], file=sys.stderr, flush=True)
    response['elapsed_seconds'] = time.monotonic()-started
    save(request['response'], response)
    return 0 if response['status'] == 'succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
