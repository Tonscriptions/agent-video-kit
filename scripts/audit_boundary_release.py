"""Audit actual model, source, score, media, skill and unchanged product receipts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def main():
    output = EVIDENCE / 'boundary-release-audit-20261018.json'
    assert not output.exists()
    full = read(EVIDENCE / 'ctc-tests-20261018/full-2.json')
    assert full['methods'] == 1135 and full['terminal_ok'] and full['frozen_equal']
    assert full['frozen_before'] == full['frozen_after'] and len(full['frozen_after']) == 170
    assert all(sha(ROOT / name) == value for name, value in full['frozen_after'].items())
    assert sha(EVIDENCE / 'ctc-tests-20261018/full-2.log') == full['log_sha256']
    scores = read(EVIDENCE / 'boundary-final-score-20261018.json')
    assert scores['generator_sha256'] == sha(ROOT / 'scripts/score_boundary_candidates.py').removeprefix('sha256:')
    assert scores['unchanged_max_error_seconds'] == 2 / 30
    assert [c['max_error_ms'] for r in scores['results'] for c in r['cases']] == [724.3125, 559, 220, 161, 286.5]
    assert all(not c['passed'] for r in scores['results'] for c in r['cases'])
    for run in scores['results']:
        assert sha(ROOT / run['result_path']).removeprefix('sha256:') == run['result_sha256']
    workers = []
    for name, expected in [('boundary-whisper-real-20261018', 2), ('boundary-qwen-real-20261018', 3)]:
        folder = EVIDENCE / name
        result = read(folder / 'result.json')
        assert result['status'] == 'inference_succeeded' and result['model_forward_calls'] == expected
        assert result['network'] == 'disabled' and result['blocked_network_events'] == []
        assert result['generator_sha256'] == sha(folder / 'executed-generator.py').removeprefix('sha256:')
        for case in result['cases']:
            text = case['original_text']
            seen = []
            for unit in case['units']:
                points = unit['original_codepoints']
                assert unit['text'] == ''.join(text[i] for i in points)
                seen.extend(points)
            seen.extend(i['index'] for i in case['ignored'])
            assert sorted(seen) == list(range(len(text)))
            assert not case['posthoc_timestamp_fix_applied']
        workers.append({'run': name, 'forwards': expected, 'result_sha256': sha(folder / 'result.json'),
                        'seconds': result['seconds'], 'peak_cuda_bytes': result['peak_cuda_bytes']})
    qwen = read(EVIDENCE / 'boundary-qwen-real-20261018/result.json')
    assert qwen['timestamp_grid_ms'] == 80 and qwen['versions']['transformers'] == '4.57.6'
    assert qwen['model_forward_attempts'] == qwen['model_forward_calls'] == 3
    chinese = qwen['cases'][2]
    zero = [u for u in chinese['units'] if u['raw_start_ms'] == u['raw_end_ms']]
    overlaps = [(a, b) for a, b in zip(chinese['units'], chinese['units'][1:]) if a['raw_end_ms'] > b['raw_start_ms']]
    assert len(chinese['units']) == 50 and len(zero) == 1 and zero[0]['text'] == '我' and len(overlaps) == 6
    assert all(0 <= u['raw_start_ms'] <= u['raw_end_ms'] <= chinese['samples'] / 16 for u in chinese['units'])
    ctc = read(EVIDENCE / 'boundary-ctc-heldout-20261018/verification.json')
    assert ctc['status'] == 'verified' and ctc['cli_calls'] == 4 and ctc['actual_workers'] == ctc['actual_forward_calls'] == 1
    assert ctc['frozen_before'] == ctc['frozen_after'] == full['frozen_after']
    native = read(EVIDENCE / 'boundary-ctc-heldout-20261018/04.json')['result']['data']['result']
    assert native['worker']['model_forward_calls'] == 1 and not native['worker']['blocked_network_events']
    ctc_projection = read(EVIDENCE / 'boundary-ctc-heldout-20261018/result.json')['cases'][0]
    assert all(p['raw_start_ms'] * 16 == u['start_sample'] and p['raw_end_ms'] * 16 == u['end_sample']
               for p, u in zip(ctc_projection['units'], native['segments'][0]['units']))
    workers.append({'run': 'boundary-ctc-heldout-20261018', 'forwards': 1, 'cli_calls': 4})
    model = read(EVIDENCE / 'boundary-aligner-acquisition-20261018-d/verification.json')
    assert model['weight_bytes'] == 1835544544 and model['weight_sha256'] == 'sha256:47831d0e82f96b20e9034dba01a075ee06436654719f6a68289e49f1b65ce0e7'
    assert qwen['model_weight_sha256'] == model['weight_sha256']
    public = {}
    for name, frames, samples in [('boundary-known-readable-20261018', 236, 125850),
                                  ('boundary-heldout-readable-20261018', 222, 117985)]:
        folder = ROOT / 'docs/assets' / name
        report = read(folder / 'verification.json')
        assert report['status'] == 'verified' and report['frames'] == frames and report['samples'] == samples
        assert report['all_video_pts_checked'] and report['pcm_equal_to_original']
        assert report['research_measurement_not_product_render']
        for filename, item in report['files'].items():
            path = folder / filename
            assert path.stat().st_size == item['bytes'] and sha(path).removeprefix('sha256:') == item['sha256']
        assert report['generator_sha256'] == sha(folder / 'executed-generator.py').removeprefix('sha256:')
        assert not report['continuous_playback_review'] and not report['listening_review']
        public[name] = {'frames': frames, 'samples': samples, 'verification_sha256': sha(folder / 'verification.json')}
    for name in ['boundary-qwen-import-20261018', 'boundary-qwen-import-20261018-b',
                 'boundary-qwen-meta-20261018', 'boundary-qwen-meta-20261018-b', 'boundary-qwen-meta-20261018-c']:
        folder = EVIDENCE / name
        result = read(folder / 'result.json')
        assert result['model_forward_calls'] == 0
        assert result['generator_sha256'] == sha(folder / 'executed-generator.py').removeprefix('sha256:')
    skill = read(EVIDENCE / 'boundary-skills-20261018.json')
    assert skill['skill_count'] == 14 and skill['local_links_checked'] == 176
    for row in skill['results']:
        assert row['sha256'] == sha(ROOT / 'skills' / row['skill'] / 'SKILL.md')
    docs = [ROOT / 'README.md', ROOT / 'AGENTS.md', *sorted((ROOT / 'docs').rglob('*.md'))]
    links, broken = 0, []
    for path in docs:
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', path.read_text(encoding='utf-8-sig')):
            target = raw.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            resolved = (path.parent / urllib.parse.unquote(target)).resolve()
            links += 1
            if resolved != output and not resolved.exists():
                broken.append({'file': str(path), 'target': target})
    assert not broken, broken
    for path in (ROOT / 'scripts').glob('*boundary*.py'):
        compile(path.read_bytes(), str(path), 'exec')
    files = {p.relative_to(ROOT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
             for folder in sorted((ROOT / 'docs/assets').glob('boundary-*')) for p in sorted(folder.rglob('*')) if p.is_file()}
    result = {'status': 'research_verified_all_acoustic_gates_failed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'real_model_workers': 3, 'real_model_forwards': 6, 'product_cli_calls': 4,
        'zero_forward_probes': 5, 'workers': workers, 'all_candidate_gates_failed': True,
        'product_files_unchanged': 170, 'current_product_matches_historical_frozen': True,
        'historical_full_methods': 1135, 'full_regression_rerun': False, 'historical_full_sha256': sha(EVIDENCE / 'ctc-tests-20261018/full-2.json'),
        'final_chart_frames': 458, 'distinct_source_pcm_samples': 243835, 'public': public,
        'static_reviewed_final_frames': 2, 'continuous_playback_review': False, 'listening_review': False,
        'skills': 14, 'skill_local_links': 176, 'documents': len(docs), 'local_links': links, 'broken_links': broken,
        'files': files, 'generator_sha256': sha(Path(__file__))}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: result[k] for k in ['status', 'real_model_workers', 'real_model_forwards', 'product_files_unchanged', 'documents', 'local_links']}))


if __name__ == '__main__':
    main()
