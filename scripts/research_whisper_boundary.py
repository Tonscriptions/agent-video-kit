"""Offline supplied-text attention/DTW baseline, never an ASR rewrite."""
import argparse
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'product/src'), str(ROOT / 'scripts')]
from research_qwen_boundary import save, units


def main(args):
    evidence = args.evidence.resolve()
    assert evidence.is_relative_to(ROOT / 'docs/validation/evidence')
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    trace_stream = (evidence / 'stacks.log').open('w', encoding='utf-8')
    faulthandler.dump_traceback_later(60, repeat=True, file=trace_stream)
    report = {'status': 'failed', 'research_only': True, 'network': 'disabled',
              'blocked_network_events': [], 'model_forward_calls': 0, 'cases': [],
              'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    started = time.monotonic()
    try:
        from ai_ad_editor.whisper_worker import install_network_guard
        install_network_guard(report['blocked_network_events'])
        runtime = ROOT / 'product/.runtime/whisper-boundary-research'
        for key, sub in {'TEMP': 'temp', 'TMP': 'temp', 'TMPDIR': 'temp', 'HF_HOME': 'hf',
                         'TORCH_HOME': 'torch', 'XDG_CACHE_HOME': 'cache'}.items():
            path = runtime / sub
            path.mkdir(parents=True, exist_ok=True)
            os.environ[key] = str(path)
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                          DO_NOT_TRACK='1', TOKENIZERS_PARALLELISM='false', TQDM_DISABLE='1')
        from ai_ad_editor.artifact_locks import artifact_entry, verification_scope, verification_summary
        with verification_scope():
            import numpy as np
            import torch
            import transformers
            save(evidence / 'stage.json', {'stage': 'frameworks_imported', 'seconds': time.monotonic() - started})
            from transformers import WhisperFeatureExtractor, WhisperForConditionalGeneration, WhisperTokenizerFast
            from transformers.models.whisper.generation_whisper import _dynamic_time_warping, _median_filter
            torch.set_num_threads(4)
            assert torch.cuda.is_available(), 'No CUDA fallback permitted'
            torch.cuda.reset_peak_memory_stats()
            model_path = args.model.resolve()
            model_files = [artifact_entry(p, 'existing-whisper-bundle') for p in sorted(model_path.iterdir())
                           if p.is_file() and p.suffix in {'.safetensors', '.json', '.txt'}]
            assert any(x['path'].endswith('model.safetensors') for x in model_files)
            save(evidence / 'stage.json', {'stage': 'model_files_hashed_and_locked', 'seconds': time.monotonic() - started})
            model = WhisperForConditionalGeneration.from_pretrained(str(model_path), local_files_only=True,
                use_safetensors=True, trust_remote_code=False, attn_implementation='eager', dtype=torch.float32).to('cuda:0').eval()
            save(evidence / 'stage.json', {'stage': 'model_loaded', 'seconds': time.monotonic() - started})
            feature = WhisperFeatureExtractor.from_pretrained(str(model_path), local_files_only=True)
            tokenizer = WhisperTokenizerFast.from_pretrained(str(model_path), local_files_only=True)
            heads = model.generation_config.alignment_heads
            report.update(versions={'python': sys.version.split()[0], 'torch': torch.__version__,
                                    'transformers': transformers.__version__, 'numpy': np.__version__},
                          module_paths={'torch': str(torch.__file__), 'transformers': str(transformers.__file__)},
                          model_files=model_files, alignment_heads=heads, time_grid_ms=20,
                          dtype='float32', attention='eager', device=torch.cuda.get_device_name(0),
                          timestamp_method='teacher-forced previous-query alignment, normalized selected cross-attentions, median filter, HF DTW; no padding or segmentation truth')
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
                    assert 0 < samples <= 30 * 16000
                    pcm = np.frombuffer(stream.readframes(samples), dtype='<i2').astype(np.float32) / 32768
                encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
                ids, offsets = encoded['input_ids'], encoded['offset_mapping']
                assert tokenizer.decode(ids) == text, 'Tokenizer changed supplied text'
                assert len(ids) <= 400
                word_tokens = []
                for group in groups:
                    selected = [i for i, (a, b) in enumerate(offsets) if any(a <= c < b for c in group['original_codepoints'])]
                    assert selected and selected == list(range(selected[0], selected[-1] + 1))
                    word_tokens.append((selected[0], selected[-1] + 1))
                assert all(a[1] <= b[0] for a, b in zip(word_tokens, word_tokens[1:])), 'BPE crosses supplied unit boundary'
                prompt = [model.config.decoder_start_token_id] + [x[1] for x in tokenizer.get_decoder_prompt_ids(
                    language=language.lower(), task='transcribe', no_timestamps=True)]
                decoder = torch.tensor([prompt + ids + [tokenizer.eos_token_id]], device='cuda:0')
                features = feature(pcm, sampling_rate=16000, return_tensors='pt').input_features.to('cuda:0')
                with torch.inference_mode():
                    output = model(input_features=features, decoder_input_ids=decoder, output_attentions=True, use_cache=False)
                report['model_forward_calls'] += 1
                weights = torch.stack([output.cross_attentions[layer][0, head] for layer, head in heads])
                # Query at previous token predicts the supplied token; one extra row closes the last token.
                frames = (samples // feature.hop_length) // 2
                weights = weights[:, len(prompt) - 1:-1, :frames]
                assert weights.shape[1] == len(ids) + 1 and frames > 0
                std, mean = torch.std_mean(weights, dim=-2, keepdim=True, unbiased=False)
                report['attention_std_floor'] = 1e-10
                matrix = _median_filter((weights - mean) / std.clamp_min(1e-10), model.config.median_filter_width).mean(0)
                assert torch.isfinite(matrix).all()
                text_indices, time_indices = _dynamic_time_warping(-matrix.cpu().double().numpy())
                jumps = np.pad(np.diff(text_indices), (1, 0), constant_values=1).astype(bool)
                times = time_indices[jumps] * 20
                assert len(times) == len(ids) + 1
                aligned = [{**g, 'raw_start_ms': int(times[a]), 'raw_end_ms': int(times[b]),
                            'bpe_start': a, 'bpe_end': b} for g, (a, b) in zip(groups, word_tokens)]
                report['cases'].append({'audio': audio_entry, 'transcript': text_entry, 'original_text': text,
                    'language': language, 'samples': samples, 'sample_rate': 16000, 'units': aligned, 'ignored': ignored,
                    'raw_token_boundary_ms': times.tolist(), 'token_offsets': offsets, 'token_ids': ids,
                    'posthoc_timestamp_fix_applied': False, 'seconds': time.monotonic() - case_started})
                save(evidence / 'progress.json', report)
                print(json.dumps({'case': len(report['cases']), 'units': len(groups)}), flush=True)
                del output, weights, matrix
            assert not report['blocked_network_events']
            report.update(status='inference_succeeded', peak_cuda_bytes=torch.cuda.max_memory_allocated(0),
                          artifact_locks=verification_summary())
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
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--case', nargs=3, action='append', default=[])
    main(parser.parse_args())
