"""Bind V52 source, final regression, real media, offline install and docs."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import urllib.parse
import zipfile
from pathlib import Path

from run_frozen_regression import frozen
from sync_delivery_precision_documents import DOCUMENTS, REPORT, CONTRACT

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence'
PUBLIC = ROOT / 'docs/assets/delivery-precision-20261018'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(name):
    return json.loads((EVIDENCE / name).read_bytes())


def run(output):
    assert not output.exists(), output
    full = receipt('delivery-precision-tests-20261018/full-1.json')
    targeted = receipt('delivery-precision-tests-20261018/targeted-3.json')
    baseline = receipt('delivery-precision-baseline-20261018/verification.json')
    smoke = receipt('delivery-precision-real-20261018/verification.json')
    media = receipt('delivery-precision-real-20261018/media-audit.json')
    static = receipt('delivery-precision-real-20261018/static-review.json')
    installed = receipt('delivery-precision-native-install-20261018/verification.json')
    skills = receipt('delivery-precision-skills-20261018.json')
    current = frozen()
    assert len(current) == 173
    assert full['methods'] == 1183 and full['terminal_ok'] and full['exit_code'] == 0 and full['skipped'] == 0
    assert targeted['methods'] == 22 and targeted['terminal_ok'] and targeted['skipped'] == 0
    for entry in (full, targeted, smoke, installed):
        assert entry['frozen_before'] == entry['frozen_after'] == current
    for stem, value in [('full-1', full), ('targeted-3', targeted)]:
        assert sha(EVIDENCE / f'delivery-precision-tests-20261018/{stem}.log') == value['log_sha256']
    assert baseline['base_commit'] == '409c207009b7e6bb484d01d550b64291d5b4d4df'
    assert baseline['methods'] == 22 and baseline['control_passed_methods'] == 5
    assert len(baseline['failed_methods']) == 16 and len(baseline['error_methods']) == 1
    assert baseline['same_current_test_sha256'] == sha(ROOT / 'product/tests/test_delivery_precision.py')
    assert sha(EVIDENCE / 'delivery-precision-baseline-20261018/executed-test.py') == baseline['same_current_test_sha256']
    assert sha(EVIDENCE / 'delivery-precision-baseline-20261018/baseline.log') == baseline['log_sha256']
    assert sha(EVIDENCE / 'delivery-precision-baseline-20261018/executed-generator.py') == baseline['generator_sha256']
    assert sha(ROOT / 'scripts/compare_delivery_precision_baseline.py') == baseline['generator_sha256']

    assert smoke['status'] == 'passed_scoped_delivery_precision' and len(smoke['cases']) == 11
    assert smoke['development_cli_calls'] == 36 and smoke['baseline_cli_calls'] == 4
    assert len(smoke['calls']) == smoke['total_cli_calls'] == 40
    assert smoke['main_frames'] == sum(row['frames'] for row in smoke['cases']) == 251
    assert smoke['main_stereo_sample_frames'] == sum(row['stereo_sample_frames'] for row in smoke['cases']) == 1191904
    assert smoke['independent_original_pcm_content_frames'] == 76800
    assert smoke['fixed_V51_pcm_compatibility_sample_frames'] == 192480
    assert smoke['new_negative_control_frames'] == 205 and smoke['baseline_alpha_frames'] == 16
    assert smoke['source_checkerboard_preview_frames'] == 12
    assert sha(ROOT / 'scripts/smoke_delivery_precision.py') == smoke['generator_sha256']
    assert sha(PUBLIC / 'verification.json') == sha(EVIDENCE / 'delivery-precision-real-20261018/verification.json')
    cases = {row['name']: row for row in smoke['cases']}
    for name in ('DP01', 'DP02', 'DP07'):
        assert cases[name]['max_alpha_error'] == 0 and cases[name]['exact_alpha_gate_required']
        assert not cases[name]['delivery']['alpha']['rgba_lossless']
    assert cases['DP05']['max_alpha_error'] == 12 and cases['DP06']['max_alpha_error'] == 4
    for name in ('DP05', 'DP06'):
        assert not cases[name]['exact_alpha_gate_required']
        assert cases[name]['delivery']['alpha']['encoding_precision'] == 'lossy-yuv-alpha'
    for row in smoke['cases']:
        assert sha(PUBLIC / row['path']) == row['output_sha256']
        assert row['pts_max_error_seconds'] <= .00051
        assert row['quality']['ok']
    fractional = cases['DP09']['quality']['metrics']
    assert abs(fractional['av_duration_delta_seconds'] - .09) < 1e-9
    assert abs(fractional['expected_quantization_delta_seconds'] - .09) < 1e-9
    assert fractional['av_sync_residual_seconds'] < 1e-9
    assert cases['DP09']['stereo_sample_frames'] == cases['DP10']['stereo_sample_frames'] == 192512
    assert cases['DP09']['decoded_rgba_sha256'] == cases['DP10']['decoded_rgba_sha256']
    assert cases['DP09']['decoded_pcm_sha256'] == cases['DP10']['decoded_pcm_sha256']
    assert len(smoke['negative_controls']) == 6
    for row in smoke['negative_controls']:
        assert row['exit_code'] == 2
        assert any(error['code'] == 'OUTPUT_AV_SYNC_OUT_OF_RANGE' for error in row['errors'])
        if row['new_native_media']:
            assert row['frames'] == 41 and sha(PUBLIC / row['path']) == row['output_sha256']
    assert smoke['baseline_cases'][0]['max_alpha_error'] == 1
    assert smoke['baseline_cases'][0]['mismatched_alpha_pixels'] == 130048
    assert smoke['baseline_cases'][1]['exit_code'] == 6 and not smoke['baseline_cases'][1]['output_published']
    for row in smoke['baseline_cases'][2:]:
        assert row['old_exit_code'] == 0 and row['new_exit_code'] == 2
        assert sha(PUBLIC / row['path']) == row['same_input_sha256']

    assert media['status'] == 'passed_scoped_media_audit' and media['main_frames'] == 251
    assert media['lossless_original_alpha_max_error'] == 0 and not media['lossy_alpha_exact_accepted']
    assert media['independent_original_pcm_sample_frames'] == 76800
    assert len(media['gifs']) == 2 and [row['image_frames'] for row in media['gifs']] == [16, 41]
    assert sha(EVIDENCE / 'delivery-precision-real-20261018/static-review.json') == media['static_review_sha256']
    assert media['generator_sha256'] == sha(ROOT / 'scripts/audit_delivery_precision_media.py')
    assert static['static_moments_checked'] == 8 and len(static['images']) == 2
    assert not static['continuous_playback'] and not static['listening_review']
    for row in static['images']:
        assert sha(PUBLIC / row['path']) == row['sha256']
    assert set(media['public_files']) == {path.name for path in PUBLIC.iterdir() if path.is_file()}
    for name, row in media['public_files'].items():
        assert sha(PUBLIC / name) == row['sha256'] and (PUBLIC / name).stat().st_size == row['bytes']

    assert installed['status'] == 'passed' and installed['installed_package_files'] == 117
    assert installed['isolated_cli_calls'] == len(installed['calls']) == 13
    assert installed['actual_new_frames'] == sum(row['frames'] for row in installed['outputs']) == 98
    assert installed['actual_new_stereo_sample_frames'] == sum(row['stereo_sample_frames'] for row in installed['outputs']) == 461792
    assert all(row['decoded_video_pcm_equal_to_development'] for row in installed['outputs'])
    assert not installed['other_machine_accepted'] and installed['package_bytes_equal_to_wheel_and_source']
    assert sha(ROOT / 'scripts/verify_delivery_precision_native_install.py') == installed['generator_sha256']
    install_evidence = EVIDENCE / 'delivery-precision-native-install-20261018'
    assert sha(install_evidence / 'executed-generator.py') == installed['generator_sha256']
    for row in installed['calls']:
        assert row['exit_code'] == 0 and '-I' in row['command'] and '-S' in row['command']
        assert sha(install_evidence / f"{row['index']:02d}.stdout.json") == row['stdout_sha256']
        assert sha(install_evidence / f"{row['index']:02d}.stderr.log") == row['stderr_sha256']
    assert sha(PUBLIC / 'agent-video-kit-cp313-win_amd64.zip') == installed['release_zip_sha256']
    assert sha(PUBLIC / 'release-manifest.json') == installed['manifest_sha256']
    with zipfile.ZipFile(PUBLIC / 'agent-video-kit-cp313-win_amd64.zip') as bundle:
        manifest_raw = bundle.read('manifest.json')
        assert manifest_raw == (PUBLIC / 'release-manifest.json').read_bytes()
        release = json.loads(manifest_raw)
        assert len(release['wheels']) == 7 and not release['python_included'] and not release['ffmpeg_included']
        for row in release['files']:
            raw = bundle.read(row['path'])
            assert len(raw) == row['bytes'] and 'sha256:' + hashlib.sha256(raw).hexdigest() == row['sha256']
        product = next(row for row in release['wheels'] if row['name'] == 'ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(bundle.read(product['path']))) as wheel:
            names = [name for name in wheel.namelist() if name.startswith('ai_ad_editor/') and not name.endswith('/')]
            assert len(names) == 117 and set(names) == set(installed['installed_files'])
            for name in names:
                raw = wheel.read(name)
                assert raw == (ROOT / 'product/src' / name).read_bytes()
                assert 'sha256:' + hashlib.sha256(raw).hexdigest() == installed['installed_files'][name]

    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 186
    skill_manifest = json.loads((ROOT / 'video-cut-install-manifest.json').read_bytes())
    assert skill_manifest['current_audit']['record_sha256'] == sha(EVIDENCE / 'delivery-precision-skills-20261018.json')
    assert any(row['record'].endswith('nested-freeze-skills-final-20261018.json') for row in skill_manifest['audit_history'])
    checked = {row['skill']: row for row in skills['results']}
    for row in skill_manifest['skills']:
        canonical = Path(row['canonical_directory'])
        assert row['name'].startswith('video-cut-') and row['invocation'] == '$' + row['name']
        assert row['skill_md_sha256'] == sha(canonical / 'SKILL.md').split(':', 1)[1]
        assert checked[row['name']]['sha256'] == sha(canonical / 'SKILL.md')
        assert checked[row['name']]['validator_exit_code'] == 0
        assert Path(row['registration_directory']).resolve() == canonical.resolve()

    docs = DOCUMENTS + ['docs/validation/' + REPORT, 'docs/specs/' + CONTRACT,
                        'docs/OpenFilm当前复用决策_2026-10-18.md']
    links = 0
    document_hashes = {}
    for name in docs:
        path = ROOT / name
        text = path.read_text(encoding='utf-8-sig')
        assert 'V52_FULL_PENDING' not in text and 'V52_SKILLS_PENDING' not in text
        document_hashes[name] = sha(path)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', text):
            target = raw.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            assert (path.parent / urllib.parse.unquote(target)).resolve().exists(), (name, target)
            links += 1
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert '| V52 |' in readme and '最近 V52 完整' in readme
    assert 'delivery-precision-20261018/alpha-before-after.gif' in readme
    assert 'delivery-precision-20261018/DP09-fractional-mp4.mp4' in readme
    value = {
        'status': 'passed_scoped_release_audit', 'full_methods': 1183,
        'full_suite_seconds': full['suite_seconds'], 'frozen_files': 173,
        'new_targeted_methods_subset': 22, 'baseline_failed_methods': 16,
        'baseline_missing_new_metric_errors': 1, 'baseline_control_passes': 5,
        'development_cli_calls': 36, 'baseline_cli_calls': 4,
        'main_frames': 251, 'main_stereo_sample_frames': 1191904,
        'independent_original_pcm_sample_frames': 76800, 'compatibility_pcm_sample_frames': 192480,
        'extra_negative_media_frames': 205, 'lossless_alpha_max_error': 0,
        'lossy_vp9_alpha_max_error': 12, 'lossy_vp8_alpha_max_error': 4,
        'installed_package_files': 117, 'isolated_installed_cli_calls': 13,
        'installed_frames': 98, 'installed_stereo_sample_frames': 461792,
        'skills': 14, 'skill_local_links': 186,
        'documents_checked': len(docs), 'document_local_links': links, 'broken_links': 0,
        'document_hashes': document_hashes,
        'media_audit_sha256': sha(EVIDENCE / 'delivery-precision-real-20261018/media-audit.json'),
        'full_receipt_sha256': sha(EVIDENCE / 'delivery-precision-tests-20261018/full-1.json'),
        'static_moments_checked': 8, 'continuous_playback': False, 'listening_review': False,
        'lossy_alpha_exact_accepted': False, 'rgba_420_lossless': False,
        'other_machine_accepted': False, 'all_capcut_features_and_quality_accepted': False,
        'goal_complete': False, 'generator_sha256': sha(Path(__file__)),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: value[key] for key in ('status', 'full_methods', 'frozen_files',
                                                'documents_checked', 'document_local_links', 'broken_links')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve())
