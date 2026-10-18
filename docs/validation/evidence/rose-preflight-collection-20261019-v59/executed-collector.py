"""Collect actual ROSE acquisition/strict-loading evidence without running a model."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from prepare_rose_research import sha, save
from smoke_fragments import frozen


def collect(acquisition, prepared, strict, public, natural, output):
    output.mkdir(parents=True, exist_ok=False)
    (output/'executed-collector.py').write_bytes(Path(__file__).read_bytes())
    acquired = json.loads((acquisition/'verification.json').read_bytes())
    native = json.loads((strict/'verification.json').read_bytes())
    preparation = json.loads((prepared/'preparation.json').read_bytes())
    assert acquired['status'] == 'acquired_and_verified' and acquired['file_count'] == 13
    assert acquired['bytes'] == 15019977880
    assert native['status'] == 'preflight_passed_no_inference' and native['model_forwards'] == 0
    assert native['network'] == 'disabled' and not native['blocked_network_events']
    assert len(native['all_checkpoint_loading']) == 2 and native['vae_loading']['strict']
    assert native['prepared_sha256'] == sha(prepared/'preparation.json')
    assert sha(strict/'executed-inspector.py') == native['generator_sha256']
    assert sha(acquisition/'executed-generator.py') == acquired['generator_sha256']
    current = frozen()
    full = json.loads((ROOT/'docs/validation/evidence/effect-automation-20261019-v58/full-final.json').read_bytes())
    assert len(current) == 186 and current == full['frozen_before'] == full['frozen_after']
    cases = []
    for name, work in [('public', public), ('natural', natural)]:
        case = json.loads((work/'case.json').read_bytes())
        assert case['status'] == 'prepared_not_inferred' and case['worker_sha256'] == sha(ROOT/'research/temporal-neural/rose_worker.py')
        assert case['runner_sha256'] == sha(ROOT/'scripts/run_rose_research.py')
        assert sha(work/'input.npy') == case['input_sha256'] and sha(work/'effective-selection.npy') == case['selection_sha256']
        assert json.loads((work/'product-before.json').read_bytes()) == current
        assert not (work/'request.json').exists() and not (work/'worker-response.json').exists()
        shutil.copyfile(work/'case.json', output/(name+'-prepared-case.json'))
        cases.append({'case': name, 'frames': case['frames'], 'width': case['width'], 'height': case['height'],
                      'input_sha256': case['input_sha256'], 'selection_sha256': case['selection_sha256'],
                      'model_forward_calls': 0, 'status': 'prepared_not_inferred'})
    expected_weights = {row['source_path']: row['sha256'] for row in acquired['files']}
    assert native['vae_loading']['checkpoint_sha256'] == expected_weights['Wan2.1_VAE.pth']
    for row in native['all_checkpoint_loading']:
        key = 'models_t5_umt5-xxl-enc-bf16.pth' if row['component'] == 'T5' else 'diffusion_pytorch_model.safetensors'
        assert row['sha256'] == expected_weights[key] and row['strict'] and not row['missing_keys'] and not row['unexpected_keys']
    for directory, prefix in [(acquisition, 'acquisition'), (strict, 'native'), (prepared, 'source')]:
        for path in directory.iterdir():
            if path.is_file():
                shutil.copyfile(path, output/(prefix+'-'+path.name))
    original = ROOT/'product/.runtime/temporal-model-audit-20261018/Kunbyte-AI__ROSE/source'
    with zipfile.ZipFile(output/'pinned-original-core.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for row in preparation['original_files']:
            path = original/row['path']
            assert sha(path) == row['sha256']
            archive.writestr(row['path'], path.read_bytes())
    query = ['nvidia-smi', '--query-gpu=name,memory.total,memory.free,utilization.gpu', '--format=csv,noheader,nounits']
    hardware = subprocess.run(query, capture_output=True, check=True, timeout=30)
    (output/'gpu-resource.stdout.log').write_bytes(hardware.stdout)
    name, total, free, utilization = [x.strip() for x in hardware.stdout.decode('utf-8').strip().split(',')]
    resource = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'command': query, 'name': name,
        'total_mib': int(total), 'free_mib': int(free), 'utilization_percent': int(utilization),
        'predeclared_text_weight_budget_mib': 7168, 'required_headroom_mib': 1024,
        'minimum_free_mib': 8192, 'budget_available': int(free) >= 8192, 'other_processes_modified': False,
        'worker_launched_by_collector': False, 'model_forward_calls': 0}
    save(output/'resources.json', resource)
    result = {'status': 'strict_local_loading_verified_inference_pending', 'research_only': True,
        'product_integrated': False, 'acquired_files': 13, 'acquired_bytes': acquired['bytes'],
        'original_source_files': len(preparation['original_files']), 'model_components_strict_loaded': 3,
        'model_forward_calls': 0, 'cases_prepared': cases, 'resource': resource,
        'quality_scores_available': False, 'natural_quality_accepted': False, 'full_capcut_parity_accepted': False,
        'production_files_frozen': 186, 'production_sha256': current, 'full_product_regression_rerun': False,
        'historical_product_regression': 'V58 1357/1357', 'generator_sha256': sha(Path(__file__)),
        'source_receipts': {'acquisition': sha(acquisition/'verification.json'), 'native': sha(strict/'verification.json'),
                            'preparation': sha(prepared/'preparation.json')},
        'files': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size}
                  for p in sorted(output.iterdir()) if p.is_file()]}
    save(output/'verification.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'acquired_files', 'acquired_bytes', 'model_forward_calls')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('acquisition', 'prepared', 'strict', 'public', 'natural', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    collect(**{k: v.resolve() for k, v in vars(args).items()})
