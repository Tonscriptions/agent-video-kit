"""Offline import and strict VAE checkpoint preflight, with zero model forwards."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_rose_research import sha, save


def run(prepared, bundle, output, all_checkpoints=False):
    output.mkdir(parents=True, exist_ok=False)
    (output/'executed-inspector.py').write_bytes(Path(__file__).read_bytes())
    started = time.monotonic()
    result = {'status': 'failed', 'model_forwards': 0, 'research_only': True}
    try:
        sys.path.insert(0, str(ROOT/'product/src'))
        os.environ['AI_AD_EDITOR_RUNTIME_DIR'] = str(ROOT/'product/.runtime')
        from ai_ad_editor.runtime import configure_local_runtime
        configure_local_runtime()
        from ai_ad_editor.rvm_worker import install_network_guard
        events = []
        install_network_guard(events)
        result.update(network='disabled', blocked_network_events=events)
        receipt = json.loads((prepared/'preparation.json').read_bytes())
        for row in receipt['prepared_files']:
            assert sha(Path(row['path'])) == row['sha256']
        sys.path.insert(0, str(prepared/'source'))
        import accelerate
        import diffusers
        import torch
        import transformers
        import yaml
        from rose.models import WanTransformer3DModel, WanT5EncoderModel, AutoencoderKLWan
        from rose.pipeline.pipeline_wan_fun_inpaint import WanFunInpaintPipeline
        config = yaml.safe_load((prepared/'source/configs/wan2.1/wan_civitai.yaml').read_text(encoding='utf-8'))
        text_config = {k: config['text_encoder_kwargs'][k] for k in
                       ('vocab', 'dim', 'dim_attn', 'dim_ffn', 'num_heads', 'num_layers',
                        'num_buckets', 'shared_pos', 'dropout')}
        with accelerate.init_empty_weights(include_buffers=False):
            text = WanT5EncoderModel(**text_config)
            model = WanTransformer3DModel.from_config(json.loads((bundle/'transformer/config.json').read_bytes()))
            vae = AutoencoderKLWan()
        assert all(p.is_meta for module in (text, model, vae) for p in module.parameters())
        assert not model.freqs.is_meta and not vae.mean.is_meta and not vae.std.is_meta
        result['parameter_counts'] = {name: sum(p.numel() for p in module.parameters())
                                      for name, module in [('T5', text), ('ROSE', model), ('VAE', vae)]}
        checkpoint = bundle/'base/Wan2.1_VAE.pth'
        state = torch.load(checkpoint, map_location='cpu', mmap=True, weights_only=True)
        loaded = vae.load_state_dict({'model.'+k: v for k, v in state.items()}, strict=True, assign=True)
        assert not loaded.missing_keys and not loaded.unexpected_keys
        assert not any(p.is_meta for p in vae.parameters())
        result['vae_loading'] = {'strict': True, 'weights_only': True, 'mmap': True,
                                 'tensors': len(state), 'checkpoint_sha256': sha(checkpoint)}
        del state
        if all_checkpoints:
            from safetensors.torch import load_file
            result['all_checkpoint_loading'] = []
            for label, module, path in [('T5', text, bundle/'base/models_t5_umt5-xxl-enc-bf16.pth'),
                                         ('ROSE', model, bundle/'transformer/diffusion_pytorch_model.safetensors')]:
                state = (load_file(str(path), device='cpu') if path.suffix == '.safetensors' else
                         torch.load(path, map_location='cpu', mmap=True, weights_only=True))
                loaded = module.load_state_dict(state, strict=True, assign=True)
                assert not loaded.missing_keys and not loaded.unexpected_keys
                assert not any(p.is_meta for p in module.parameters())
                result['all_checkpoint_loading'].append({'component': label, 'strict': True,
                    'missing_keys': [], 'unexpected_keys': [], 'tensor_count': len(state),
                    'elements': sum(v.numel() for v in state.values()), 'sha256': sha(path),
                    'loading': 'safetensors CPU' if path.suffix == '.safetensors' else 'weights_only mmap CPU'})
                del state
        result['native_modules'] = {name: {'path': str(Path(module.__file__).resolve()), 'sha256': sha(Path(module.__file__))}
            for name, module in sorted(sys.modules.items()) if name.startswith('rose') and getattr(module, '__file__', None)}
        assert not any(name.startswith('rose.dist') or 'hugging_face' in name for name in result['native_modules'])
        for row in receipt['prepared_files']:
            assert sha(Path(row['path'])) == row['sha256']
        result.update(status='preflight_passed_no_inference', versions={'python': sys.version.split()[0],
            'torch': torch.__version__, 'diffusers': diffusers.__version__, 'transformers': transformers.__version__,
            'accelerate': accelerate.__version__}, prepared_sha256=sha(prepared/'preparation.json'))
    except BaseException as error:
        result.update(error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        result.update(seconds=time.monotonic()-started, generator_sha256=sha(Path(__file__)))
        save(output/'verification.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prepared', 'bundle', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--all-checkpoints', action='store_true')
    args = parser.parse_args()
    run(args.prepared.resolve(), args.bundle.resolve(), args.output.resolve(), args.all_checkpoints)
