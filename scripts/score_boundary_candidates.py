"""Independent integer-sample scoring; candidate workers never read these refs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(args):
    results = []
    fixtures = {}
    for name in ['ctc-alignment-20261018', 'boundary-heldout-20261018']:
        folder = ROOT / 'docs/assets' / name
        truth = json.loads((folder / 'input-provenance.json').read_bytes())
        assert truth['sample_rate'] == 16000
        assert truth['quality_goal']['boundary_error_seconds_max'] == 2 / 30
        for filename, row in truth['files'].items():
            data = (folder / filename).read_bytes()
            assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
        fixtures[str((folder / 'input.wav').resolve())] = (name, truth)
    for path in args.result:
        data = json.loads(path.read_bytes())
        assert data['status'] == 'inference_succeeded' and not data['blocked_network_events']
        cases = []
        for case in data['cases']:
            if case['audio']['path'] not in fixtures:
                continue
            name, truth = fixtures[case['audio']['path']]
            assert not case['posthoc_timestamp_fix_applied'] and case['samples'] == truth['samples']
            assert len(case['units']) == len(truth['words'])
            words, worst_samples = [], 0
            for actual, reference in zip(case['units'], truth['words']):
                assert actual['text'] == reference['word']
                start = actual['raw_start_ms'] * 16 - reference['start_sample']
                end = actual['raw_end_ms'] * 16 - reference['end_sample']
                worst_samples = max(worst_samples, abs(start), abs(end))
                words.append({'text': actual['text'], 'reference_start_sample': reference['start_sample'],
                    'reference_end_sample': reference['end_sample'], 'candidate_start_sample': actual['raw_start_ms'] * 16,
                    'candidate_end_sample': actual['raw_end_ms'] * 16, 'start_error_samples': start, 'end_error_samples': end,
                    'start_error_ms': start / 16, 'end_error_ms': end / 16,
                    'start_passed': abs(start) * 30 <= 2 * 16000, 'end_passed': abs(end) * 30 <= 2 * 16000})
            cases.append({'fixture': name, 'max_error_samples': worst_samples,
                'max_error_ms': worst_samples / 16, 'passed': worst_samples * 30 <= 2 * 16000,
                'words': words, 'truth_is_authored_blocks_not_phonetic_labels': True})
        results.append({'result_path': str(path), 'result_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'model_forward_calls': data['model_forward_calls'], 'cases': cases,
            'passed_both_fixtures': len(cases) == 2 and all(x['passed'] for x in cases)})
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'docs/validation/evidence') and not output.exists()
    output.write_text(json.dumps({'results': results, 'unchanged_max_error_seconds': 2 / 30,
        'scoring': 'integer signed samples; all starts and ends; no padding/shift or outlier deletion',
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2) + '\n',
        encoding='utf-8', newline='\n')
    print(json.dumps([{k: v for k, v in r.items() if k != 'cases'} | {'cases': [{k: v for k, v in c.items() if k != 'words'} for c in r['cases']]} for r in results]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
