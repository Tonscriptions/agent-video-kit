"""Run existing registered CTC engine on the predeclared new holdout."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'product/src'), str(ROOT / 'scripts')]
from ai_ad_editor.cli import main as cli_main
from ai_ad_editor.runtime import configure_local_runtime
from run_frozen_regression import frozen


def main():
    evidence = ROOT / 'docs/validation/evidence/boundary-ctc-heldout-20261018'
    evidence.mkdir(exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    root = ROOT / 'workspace/boundary-ctc-heldout-20261018'
    assert not root.exists()
    before = frozen()
    configure_local_runtime()
    calls = []
    def cli(*args):
        out, err = io.StringIO(), io.StringIO()
        start = time.monotonic()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli_main(list(map(str, args)))
        result = json.loads(out.getvalue())
        calls.append({'args': list(map(str, args)), 'exit_code': code, 'seconds': time.monotonic() - start,
                      'stderr': err.getvalue(), 'result': result})
        (evidence / f'{len(calls):02}.json').write_text(json.dumps(calls[-1], indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
        assert code == 0, result
        print(json.dumps({'cli_call': len(calls), 'exit_code': code}), flush=True)
        return result
    cli('project', 'init', root)
    cli('asr', 'adapter', 'register', '--project', root, '--adapter-id', 'ctc',
        '--engine', 'transformers-wav2vec2-ctc-local-v1',
        '--python-executable', 'D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe',
        '--model-path', ROOT / 'product/.runtime/models/ctc-en-runtime', '--device', 'cuda', '--threads', '4',
        '--evidence', ROOT / 'docs/validation/evidence/ctc-model-conversion-20261018/en-runtime.json',
        '--license-spdx', 'Apache-2.0', '--creator', 'upstream model authors')
    fixture = ROOT / 'docs/assets/boundary-heldout-20261018'
    cli('media', 'ingest', '--project', root, '--asset-id', 'speech', '--input', fixture / 'input.wav')
    result = cli('subtitle', 'align', '--project', root, '--asset-id', 'speech', '--adapter-id', 'ctc',
        '--transcript', fixture / 'transcript.txt', '--output', 'assets/subtitles/heldout.json', '--case', 'upper',
        '--granularity', 'whitespace')
    result = result['data']['result']
    assert result['worker']['model_forward_calls'] == 1 and result['worker']['blocked_network_events'] == []
    raw_units = result['segments'][0]['units']
    # Convert exact native sample coordinates for the shared independent scorer.
    candidate = {'status': 'inference_succeeded', 'source': 'actual existing product CTC, one new worker',
        'blocked_network_events': [], 'model_forward_calls': 1, 'cases': [{
        'audio': {'path': str((fixture / 'input.wav').resolve())}, 'samples': result['samples'], 'sample_rate': 16000,
        'original_text': result['original_text'], 'language': 'English', 'posthoc_timestamp_fix_applied': False,
        'units': [{'text': u['text'], 'original_codepoints': list(range(u['start_char'], u['end_char'])),
                   'raw_start_ms': u['start_sample'] / 16, 'raw_end_ms': u['end_sample'] / 16} for u in raw_units]}]}
    (evidence / 'result.json').write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    after = frozen()
    assert before == after
    proof = {'status': 'verified', 'cli_calls': len(calls), 'actual_workers': 1, 'actual_forward_calls': 1,
             'frozen_before': before, 'frozen_after': after, 'frozen_equal': True,
             'native_alignment_result_sha256': hashlib.sha256((evidence / '04.json').read_bytes()).hexdigest(),
             'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (evidence / 'verification.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
