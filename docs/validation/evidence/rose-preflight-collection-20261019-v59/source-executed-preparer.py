"""Freeze a minimal, single-GPU research copy of the pinned ROSE sources.

This is a development tool, not a product backend or installer. Originals stay
untouched; every compatibility change is exported as a unified patch.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
COMMIT = '6be41c5420bf331c6d491277d5a6feaf9b3a779a'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while data := stream.read(8 * 1024**2):
            h.update(data)
    return 'sha256:' + h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8', newline='\n')


def prepare(output):
    original = ROOT/'product/.runtime/temporal-model-audit-20261018/Kunbyte-AI__ROSE'
    receipt = json.loads((original/'acquisition.json').read_bytes())
    if receipt['commit'] != COMMIT:
        raise ValueError('ROSE_SOURCE_COMMIT_MISMATCH')
    output.mkdir(parents=True, exist_ok=False)
    (output/'executed-preparer.py').write_bytes(Path(__file__).read_bytes())
    source = output/'source'
    selected = []
    names = {'LICENSE', 'configs/wan2.1/wan_civitai.yaml',
             'rose/__init__.py', 'rose/models/__init__.py',
             'rose/models/wan_transformer3d.py', 'rose/models/wan_text_encoder.py',
             'rose/models/wan_vae.py', 'rose/models/wan_image_encoder.py',
             'rose/models/wan_xlm_roberta.py', 'rose/models/cache_utils.py',
             'rose/pipeline/__init__.py', 'rose/pipeline/pipeline_wan_fun_inpaint.py'}
    for row in receipt['selected']:
        if row['path'] not in names:
            continue
        path = original/'source'/row['path']
        if sha(path) != 'sha256:'+row['sha256'] or path.stat().st_size != row['bytes']:
            raise ValueError('ROSE_SOURCE_BYTES_MISMATCH: '+row['path'])
        target = source/row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        selected.append({'path': row['path'], 'sha256': sha(path), 'bytes': path.stat().st_size})
    if {x['path'] for x in selected} != names:
        raise ValueError('ROSE_SOURCE_INCOMPLETE')
    patches = []

    def change(name, replacements):
        path = source/name
        before = path.read_text(encoding='utf-8')
        after = before
        for old, new, count in replacements:
            if after.count(old) != count:
                raise ValueError('ROSE_PATCH_CONTEXT_MISMATCH: '+name+' '+old)
            after = after.replace(old, new)
        path.write_text(after, encoding='utf-8', newline='\n')
        patches.append(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                       fromfile='upstream/'+name, tofile='research/'+name)))

    # The constructor already defaults to world size 1. Reject attempts to use
    # distributed or optional proprietary accelerator routes in this invocation.
    change('rose/models/wan_transformer3d.py', [(
        'from ..dist import (get_sequence_parallel_rank,\n'
        '                    get_sequence_parallel_world_size, get_sp_group,\n'
        '                    xFuserLongContextAttention)\n'
        'from ..dist.wan_xfuser import usp_attn_forward\n',
        'def get_sequence_parallel_rank():\n    return 0\n\n'
        'def get_sequence_parallel_world_size():\n    return 1\n\n'
        'def get_sp_group():\n    raise RuntimeError("ROSE_RESEARCH_SINGLE_GPU_ONLY")\n\n'
        'def usp_attn_forward(*args, **kwargs):\n'
        '    raise RuntimeError("ROSE_RESEARCH_DISTRIBUTED_ATTENTION_FORBIDDEN")\n\n'
        'xFuserLongContextAttention = None\n', 1)])
    # Only the inpainting pipeline is needed. No utils, Gradio, provider, demo,
    # distributed, or ProPainter source is imported by this curated package.
    path = source/'rose/pipeline/__init__.py'
    change('rose/pipeline/__init__.py', [(path.read_text(encoding='utf-8'),
        'from .pipeline_wan_fun_inpaint import WanFunInpaintPipeline\n', 1)])
    old_check = '''        if prompt_embeds is not None and negative_prompt_embeds is not None:
            if prompt_embeds.shape != negative_prompt_embeds.shape:
                raise ValueError(
                    "`prompt_embeds` and `negative_prompt_embeds` must have the same shape when passed directly, but"
                    f" got: `prompt_embeds` {prompt_embeds.shape} != `negative_prompt_embeds`"
                    f" {negative_prompt_embeds.shape}."
                )'''
    new_check = '''        if prompt_embeds is not None and negative_prompt_embeds is not None:
            if ([tuple(x.shape) for x in prompt_embeds] !=
                    [tuple(x.shape) for x in negative_prompt_embeds]):
                raise ValueError("ROSE_PRECOMPUTED_EMBEDDING_SHAPE_MISMATCH")'''
    old_clip = '''            clip_image = Image.new("RGB", (512, 512), color=(0, 0, 0))  
            clip_image = TF.to_tensor(clip_image).sub_(0.5).div_(0.5).to(device, weight_dtype) 
            clip_context = self.clip_image_encoder([clip_image[:, None, :, :]])
            clip_context = (
                torch.cat([clip_context] * 2) if do_classifier_free_guidance else clip_context
            )
            clip_context = torch.zeros_like(clip_context)'''
    new_clip = '''            # The author's no-reference branch zeros every CLIP feature.
            # ViT-H/14: 224/14 = 16, hence 16*16+1 tokens, width 1280.
            clip_context = torch.zeros(
                (2 if do_classifier_free_guidance else 1, 257, 1280),
                device=device, dtype=weight_dtype)'''
    change('rose/pipeline/pipeline_wan_fun_inpaint.py', [
        ('batch_size = prompt_embeds.shape[0]', 'batch_size = len(prompt_embeds)', 2),
        ('weight_dtype = self.text_encoder.dtype', 'weight_dtype = self.transformer.dtype', 1),
        (old_check, new_check, 1), (old_clip, new_clip, 1)])
    (output/'compatibility.patch').write_text(''.join(patches), encoding='utf-8', newline='\n')
    frozen = [{'path': str(p.resolve()), 'sha256': sha(p), 'bytes': p.stat().st_size}
              for p in sorted(source.rglob('*')) if p.is_file()]
    result = {'status': 'prepared_not_inferred', 'upstream_commit': COMMIT,
              'original_acquisition_sha256': sha(original/'acquisition.json'), 'original_files': selected,
              'prepared_files': frozen, 'patch_sha256': sha(output/'compatibility.patch'),
              'generator_sha256': sha(Path(__file__)), 'single_gpu_only': True,
              'clip_reference_supported': False, 'clip_context_shape': [1, 257, 1280],
              'clip_no_reference_algebra': 'zeros_like(any finite CLIP output); shape from original ViT-H/14 source',
              'runtime_downloader': False, 'product_integrated': False}
    save(output/'preparation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output.resolve()), ensure_ascii=False))
