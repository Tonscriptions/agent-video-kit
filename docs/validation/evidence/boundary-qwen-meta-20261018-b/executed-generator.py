"""Bounded, offline native Qwen boundary experiment, without upstream network APIs.

This research runner is deliberately separate from registered product engines.
It imports only reviewed local architecture files, never the upstream package's
ASR/URL/normalization entry points. Ground-truth placement files are not inputs.
"""
import argparse
import faulthandler
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback
import unicodedata
import wave

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def units(text):
    """Match reviewed space-language/CJK tokenization while retaining every index."""
    groups, pending, ignored = [], [], []
    def flush():
        if pending:
            groups.append({'text': ''.join(text[i] for i in pending), 'original_codepoints': pending.copy()})
            pending.clear()
    for i, ch in enumerate(text):
        code = ord(ch)
        cjk = (0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF or
               0x20000 <= code <= 0x2A6DF or 0x2A700 <= code <= 0x2B73F or
               0x2B740 <= code <= 0x2B81F or 0x2B820 <= code <= 0x2CEAF or 0xF900 <= code <= 0xFAFF)
        if cjk:
            flush()
            groups.append({'text': ch, 'original_codepoints': [i]})
        elif ch == "'" or unicodedata.category(ch)[0] in {'L', 'N'}:
            pending.append(i)
        else:
            ignored.append({'index': i, 'character': ch, 'reason': 'whitespace' if ch.isspace() else 'punctuation_or_symbol'})
            if ch.isspace():
                flush()
    flush()
    assert groups and len(text) <= 16384 and len(groups) <= 1024
    assert sorted([i for g in groups for i in g['original_codepoints']] + [x['index'] for x in ignored]) == list(range(len(text)))
    return groups, ignored


def main(args):
    evidence = args.evidence.resolve()
    assert evidence.is_relative_to(ROOT / 'docs/validation/evidence')
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    trace_stream = (evidence / 'stacks.log').open('w', encoding='utf-8')
    faulthandler.dump_traceback_later(60, repeat=True, file=trace_stream)
    started = time.monotonic()
    report = {'status': 'failed', 'research_only': True, 'product_engine_registered': False,
              'network': 'disabled', 'blocked_network_events': [], 'model_forward_calls': 0,
              'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        sys.path.insert(0, str(ROOT / 'product/src'))
        from ai_ad_editor.whisper_worker import install_network_guard
        install_network_guard(report['blocked_network_events'])
        runtime = ROOT / 'product/.runtime/qwen-boundary-research'
        for key, sub in {'TEMP': 'temp', 'TMP': 'temp', 'TMPDIR': 'temp', 'HF_HOME': 'hf',
                         'HF_HUB_CACHE': 'hf/hub', 'TORCH_HOME': 'torch', 'XDG_CACHE_HOME': 'cache'}.items():
            path = runtime / sub
            path.mkdir(parents=True, exist_ok=True)
            os.environ[key] = str(path)
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                          DO_NOT_TRACK='1', TOKENIZERS_PARALLELISM='false', TQDM_DISABLE='1')
        from ai_ad_editor.artifact_locks import artifact_entry, verification_scope, verification_summary
        with verification_scope():
            source = args.source.resolve()
            source_proof = json.loads(args.source_proof.read_bytes())
            assert source_proof['revision'] == '7c6daf77a2421100f5fb066495372c00129d39ff'
            backend = source / 'qwen_asr/core/transformers_backend'
            for path in sorted(backend.glob('*.py')):
                entry = artifact_entry(path, 'reviewed-qwen-source')
                assert entry['sha256'].removeprefix('sha256:') == source_proof['files'][path.relative_to(source).as_posix()]
            if args.overlay:
                assert not args.compatibility
                overlay = args.overlay.resolve()
                assert overlay.is_relative_to(ROOT / 'product/.runtime')
                proof = json.loads(args.overlay_proof.read_bytes())
                assert proof['status'] == 'downloaded_extracted_and_hashed'
                for name, expected in proof['files'].items():
                    path = (overlay / name).resolve()
                    assert path.is_relative_to(overlay)
                    assert artifact_entry(path, 'pinned-research-python-overlay')['sha256'] == 'sha256:' + expected
                sys.path.insert(0, str(overlay))
                report['explicit_native_module_overlay'] = str(overlay)
            import numpy as np
            import torch
            import transformers
            from transformers import Qwen2TokenizerFast, WhisperFeatureExtractor
            if args.overlay:
                assert transformers.__version__ == '4.57.6' and Path(transformers.__file__).resolve().is_relative_to(overlay)
            report.update(versions={'python': sys.version.split()[0], 'torch': torch.__version__,
                                    'transformers': transformers.__version__, 'numpy': np.__version__},
                          module_paths={'torch': str(torch.__file__), 'transformers': str(transformers.__file__)})
            torch.set_num_threads(4)
            assert torch.cuda.is_available(), 'No CUDA fallback permitted'
            torch.cuda.reset_peak_memory_stats()
            if args.compatibility:
                assert transformers.__version__ == '5.14.1'
                adapted = runtime / 'transformers-5.14.1-backend'
                adapted.mkdir(exist_ok=True)
                changes = []
                for path in sorted(backend.glob('*.py')):
                    raw = path.read_bytes()
                    after = raw
                    if path.name == 'modeling_qwen3_asr.py':
                        assert raw.count(b'@check_model_inputs()') == 1
                        after = raw.replace(b'@check_model_inputs()', b'@check_model_inputs')
                    destination = adapted / path.name
                    if destination.exists():
                        assert destination.read_bytes() == after
                    else:
                        destination.write_bytes(after)
                    artifact_entry(destination, 'explicit-research-compatibility-source')
                    changes.append({'file': path.name, 'original_sha256': hashlib.sha256(raw).hexdigest(),
                                    'adapted_sha256': hashlib.sha256(after).hexdigest(),
                                    'changed': raw != after})
                report['compatibility'] = {'target': transformers.__version__, 'files': changes,
                    'change': 'Current check_model_inputs takes function directly; remove obsolete decorator factory parentheses',
                    'upstream_and_installed_libraries_modified': False}
                backend = adapted
            spec = importlib.util.spec_from_file_location('_avk_reviewed_qwen_backend', backend / '__init__.py',
                                                         submodule_search_locations=[str(backend)])
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            report['source_import_succeeded'] = True
            if args.import_only:
                report['status'] = 'import_only_succeeded'
            elif args.construct_only:
                config_entry = artifact_entry(args.model.resolve() / 'config.json', 'qwen-config-meta-probe')
                report['config'] = config_entry
                config = module.Qwen3ASRConfig.from_pretrained(str(args.model.resolve()), local_files_only=True,
                                                            trust_remote_code=False)
                with torch.device('meta'):
                    model = module.Qwen3ASRForConditionalGeneration(config)
                report.update(status='architecture_constructed_on_meta', parameters=sum(p.numel() for p in model.parameters()),
                              weights_loaded=False, model_forward_calls=0)
            else:
                model_path = args.model.resolve()
                acquisition = json.loads(args.acquisition.read_bytes())
                assert acquisition['status'] == 'downloaded_and_hashed'
                assert acquisition['revision'] == 'c7cbfc2048c462b0d63a45797104fc9db3ad62b7'
                for row in acquisition['configs']:
                    artifact = artifact_entry(model_path / row['path'], 'qwen-model-configuration')
                    assert artifact['sha256'].removeprefix('sha256:') == row['sha256']
                weight = artifact_entry(model_path / 'model.safetensors', 'qwen-model-weights')
                assert weight['sha256'] == acquisition['weight_sha256']
                config = module.Qwen3ASRConfig.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False)
                assert config.timestamp_segment_time == 80
                report['timestamp_grid_ms'] = config.timestamp_segment_time
                model = module.Qwen3ASRForConditionalGeneration.from_pretrained(str(model_path), config=config,
                    dtype=torch.bfloat16, attn_implementation='eager', local_files_only=True, trust_remote_code=False,
                    use_safetensors=True)
                model.to('cuda:0').eval()
                feature = WhisperFeatureExtractor.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False)
                tokenizer = Qwen2TokenizerFast.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False,
                                                            fix_mistral_regex=True)
                processor = module.Qwen3ASRProcessor(feature, tokenizer)
                report.update(device=torch.cuda.get_device_name(0), dtype='bfloat16', attention='eager', cases=[])
                def counted(_module, _inputs, _output):
                    report['model_forward_calls'] += 1
                handle = model.thinker.register_forward_hook(counted)
                for raw_audio, raw_text, language in args.case:
                    case_started = time.monotonic()
                    audio_path, text_path = Path(raw_audio).resolve(), Path(raw_text).resolve()
                    audio_entry = artifact_entry(audio_path, 'research-audio')
                    text_entry = artifact_entry(text_path, 'research-original-transcript')
                    text = text_path.read_text(encoding='utf-8-sig')
                    groups, ignored = units(text)
                    with wave.open(str(audio_path), 'rb') as stream:
                        assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) == (16000, 1, 2)
                        samples = stream.getnframes()
                        assert 0 < samples <= 60 * 16000
                        pcm = np.frombuffer(stream.readframes(samples), dtype='<i2').astype(np.float32) / 32768
                    aligner_text = '<|audio_start|><|audio_pad|><|audio_end|>' + '<timestamp><timestamp>'.join(g['text'] for g in groups) + '<timestamp><timestamp>'
                    assert language in {'English', 'Chinese'}
                    inputs = processor(text=[aligner_text], audio=[pcm], return_tensors='pt', padding=True)
                    inputs = inputs.to(model.device).to(model.dtype)
                    with torch.inference_mode():
                        logits = model.thinker(**inputs).logits
                    timestamps = logits.argmax(dim=-1)[0][inputs['input_ids'][0] == config.timestamp_token_id].cpu().tolist()
                    assert len(timestamps) == len(groups) * 2
                    raw_times = [x * int(config.timestamp_segment_time) for x in timestamps]
                    aligned = [{**g, 'raw_start_ms': raw_times[i * 2], 'raw_end_ms': raw_times[i * 2 + 1]}
                               for i, g in enumerate(groups)]
                    report['cases'].append({'audio': audio_entry, 'transcript': text_entry, 'original_text': text,
                        'language': language, 'samples': samples, 'sample_rate': 16000, 'units': aligned, 'ignored': ignored,
                        'raw_timestamp_ids': timestamps, 'posthoc_timestamp_fix_applied': False,
                        'seconds': time.monotonic() - case_started})
                    save(evidence / 'progress.json', report)
                    print(json.dumps({'case': len(report['cases']), 'units': len(groups), 'forwards': report['model_forward_calls']}), flush=True)
                    del logits, inputs
                handle.remove()
                assert not report['blocked_network_events']
                report.update(status='inference_succeeded', peak_cuda_bytes=torch.cuda.max_memory_allocated(0),
                              model_weight_sha256=weight['sha256'])
            report['artifact_locks'] = verification_summary()
    except Exception as exc:
        report.update(error=repr(exc), traceback=traceback.format_exc())
        save(evidence / 'failure.json', report)
        raise
    finally:
        report['seconds'] = time.monotonic() - started
        save(evidence / 'result.json', report)
        faulthandler.cancel_dump_traceback_later()
        trace_stream.close()
    print(json.dumps({'status': report['status'], 'forwards': report['model_forward_calls']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for field in ['source', 'source-proof', 'model', 'acquisition', 'evidence']:
        parser.add_argument('--' + field, type=Path, required=True)
    parser.add_argument('--import-only', action='store_true')
    parser.add_argument('--construct-only', action='store_true')
    parser.add_argument('--compatibility', action='store_true')
    parser.add_argument('--overlay', type=Path)
    parser.add_argument('--overlay-proof', type=Path)
    parser.add_argument('--case', nargs=3, action='append', default=[], metavar=('WAV', 'TXT', 'LANGUAGE'))
    main(parser.parse_args())
