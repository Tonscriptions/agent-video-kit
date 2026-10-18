"""Bind V53 tests, source, actual media, installed bytes and current docs."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.parse
import zipfile

from run_frozen_regression import frozen
from sync_magnetic_reorder_documents import CONTRACT, DOCUMENTS, REPORT, PUBLIC

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'docs/validation/evidence'
PUBLIC_ROOT = ROOT/'docs/assets'/PUBLIC


def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())
def receipt(name): return json.loads((EVIDENCE/name).read_bytes())


def run(output):
    assert not output.exists()
    full = receipt('magnetic-reorder-tests-20261018/full-1.json')
    target = receipt('magnetic-reorder-tests-20261018/targeted-2.json')
    baseline = receipt('magnetic-reorder-v52-counterfactual-20261018/verification.json')
    smoke = receipt('magnetic-reorder-real-r5-20261018/verification.json')
    media = receipt('magnetic-reorder-real-r5-20261018/media-audit.json')
    static = receipt('magnetic-reorder-real-r5-20261018/static-review.json')
    install = receipt('magnetic-reorder-native-install-20261018/verification.json')
    skills = receipt('magnetic-reorder-skills-20261018.json')
    current = frozen();assert len(current) == 175
    assert full['methods'] == 1223 and full['terminal_ok'] and full['exit_code'] == full['skipped'] == 0
    assert target['methods'] == 40 and target['terminal_ok'] and target['exit_code'] == target['skipped'] == 0
    for value in (full, target, smoke, install): assert value['frozen_before'] == value['frozen_after'] == current
    for stem, value in [('full-1', full), ('targeted-2', target)]:
        assert sha(EVIDENCE/f'magnetic-reorder-tests-20261018/{stem}.log') == value['log_sha256']
    assert baseline['base_commit'] == 'bcab0e052e4e11d10696b8761c26fdd6f87666cf' and baseline['methods'] == 40
    assert len(baseline['failed_methods']) == 15 and len(baseline['error_methods']) == 23
    assert len(baseline['control_passed_methods']) == 2
    base = EVIDENCE/'magnetic-reorder-v52-counterfactual-20261018'
    assert sha(base/'baseline.log') == baseline['log_sha256']
    assert sha(base/'executed-test.py') == baseline['same_current_test_sha256'] == sha(ROOT/'product/tests/test_magnetic_reorder.py')
    assert sha(base/'executed-generator.py') == baseline['generator_sha256'] == sha(ROOT/'scripts/compare_magnetic_reorder_baseline.py')
    assert smoke['status'] == 'passed_scoped_magnetic_reorder' and len(smoke['cases']) == 10
    assert smoke['development_cli_calls'] == len(smoke['calls']) == 69
    assert smoke['main_frames'] == sum(row['frames'] for row in smoke['cases']) == 380
    assert smoke['main_stereo_sample_frames'] == sum(row['stereo_sample_frames'] for row in smoke['cases']) == 1824000
    assert sha(ROOT/'scripts/smoke_magnetic_reorder.py') == smoke['generator_sha256']
    assert sha(PUBLIC_ROOT/'verification.json') == sha(EVIDENCE/'magnetic-reorder-real-r5-20261018/verification.json')
    assert {row['code'] for row in smoke['negative_controls']} == {'EDIT_PROJECT_CHANGED', 'EDIT_REORDER_TRANSITION_CONFLICT',
        'EDIT_TRACK_LOCKED', 'EDIT_REORDER_SYNC_SPAN_UNSUPPORTED', 'EDIT_NEGATIVE_TIME'}
    for row in smoke['cases']:
        assert sha(PUBLIC_ROOT/row['path']) == row['output_sha256'] and row['quality']['ok']
        assert row['max_pts_error_seconds'] <= .00051
        if row['name'] == 'MR08': assert row['max_alpha_error'] == 0 and not row['audio_content_accepted']
        else: assert row['max_rgb_error'] == row['max_pcm_error'] == 0 and row['audio_content_accepted']
    for relative in ['magnetic-reorder-real-20261018', 'magnetic-reorder-real-final-20261018',
                     'magnetic-reorder-real-r3-20261018', 'magnetic-reorder-real-r4-20261018']:
        failed = receipt(relative+'/failure.json');assert failed['partials_preserved']
        assert failed['frozen_before'] == failed['frozen_after'] == current
    for relative in ['magnetic-reorder-real-final-20261018', 'magnetic-reorder-real-r3-20261018']:
        failed = receipt(relative+'/source-alpha-failure.json')
        assert failed['max_alpha_error'] == 1 and failed['changed_alpha_pixels'] == 306069 and failed['threshold'] == 0
    assert media['status'] == 'passed_scoped_media_audit' and media['main_frames'] == 380
    assert media['independent_PCM_sample_frames'] == 1152000 and media['independent_pure_cut_RGB_frames'] == 200
    assert media['independent_alpha_frames'] == 40 and media['max_alpha_error'] == 0
    assert media['pre_edit_reference_frames'] == 110 and media['gif']['frames'] == 40 and media['gif']['duration_ms'] == 4000
    assert media['generator_sha256'] == sha(ROOT/'scripts/audit_magnetic_reorder_media.py')
    assert static['static_moments_checked'] == 9 and len(static['images']) == 3
    assert not static['continuous_playback'] and not static['listening_review']
    assert media['static_review_sha256'] == sha(EVIDENCE/'magnetic-reorder-real-r5-20261018/static-review.json')
    assert static['contact_generator_sha256'] == sha(ROOT/'scripts/make_magnetic_reorder_contacts.py')
    assert set(media['public_files']) == {p.name for p in PUBLIC_ROOT.iterdir() if p.is_file()}
    for name, row in media['public_files'].items():
        assert sha(PUBLIC_ROOT/name) == row['sha256'] and (PUBLIC_ROOT/name).stat().st_size == row['bytes']
    assert install['status'] == 'passed' and install['installed_package_files'] == 118
    assert install['isolated_cli_calls'] == len(install['calls']) == 19
    assert install['actual_new_frames'] == sum(row['frames'] for row in install['outputs']) == 190
    assert install['actual_new_stereo_sample_frames'] == 912000
    assert install['package_bytes_equal_to_wheel_and_source'] and not install['other_machine_accepted']
    assert all(row['decoded_video_pcm_equal_to_development'] for row in install['outputs'])
    assert sha(ROOT/'scripts/verify_magnetic_reorder_native_install.py') == install['generator_sha256']
    install_path = EVIDENCE/'magnetic-reorder-native-install-20261018'
    assert sha(install_path/'executed-generator.py') == install['generator_sha256']
    for row in install['calls']:
        assert row['exit_code'] == 0 and '-I' in row['command'] and '-S' in row['command']
        assert sha(install_path/f"{row['index']:02d}.stdout.json") == row['stdout_sha256']
        assert sha(install_path/f"{row['index']:02d}.stderr.log") == row['stderr_sha256']
    assert sha(PUBLIC_ROOT/'agent-video-kit-cp313-win_amd64.zip') == install['release_zip_sha256']
    assert sha(PUBLIC_ROOT/'release-manifest.json') == install['manifest_sha256']
    with zipfile.ZipFile(PUBLIC_ROOT/'agent-video-kit-cp313-win_amd64.zip') as bundle:
        assert bundle.read('manifest.json') == (PUBLIC_ROOT/'release-manifest.json').read_bytes()
        manifest = json.loads(bundle.read('manifest.json'))
        assert len(manifest['wheels']) == 7 and not manifest['python_included'] and not manifest['ffmpeg_included']
        for row in manifest['files']:
            raw = bundle.read(row['path']);assert len(raw) == row['bytes'] and digest(raw) == row['sha256']
        product = next(row for row in manifest['wheels'] if row['name'] == 'ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(bundle.read(product['path']))) as wheel:
            names = [n for n in wheel.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')]
            assert len(names) == 118 and set(names) == set(install['installed_files'])
            for name in names:
                raw = wheel.read(name)
                assert raw == (ROOT/'product/src'/name).read_bytes() and digest(raw) == install['installed_files'][name]
    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 190
    manifest = json.loads((ROOT/'video-cut-install-manifest.json').read_bytes())
    assert manifest['current_audit']['record_sha256'] == sha(EVIDENCE/'magnetic-reorder-skills-20261018.json')
    assert any(row['record'].endswith('delivery-precision-skills-20261018.json') for row in manifest['audit_history'])
    checked = {row['skill']: row for row in skills['results']}
    for row in manifest['skills']:
        path = Path(row['canonical_directory'])/'SKILL.md'
        assert row['name'].startswith('video-cut-') and row['invocation'] == '$'+row['name']
        assert sha(path) == checked[row['name']]['sha256'] == 'sha256:'+row['skill_md_sha256']
        assert checked[row['name']]['validator_exit_code'] == 0
        assert Path(row['registration_directory']).resolve() == Path(row['canonical_directory']).resolve()
    docs = DOCUMENTS+['docs/validation/'+REPORT, 'docs/specs/'+CONTRACT, 'docs/OpenFilm当前复用决策_2026-10-18.md']
    document_hashes, links, destinations = {}, 0, []
    for name in docs:
        path = ROOT/name;text = path.read_text(encoding='utf-8-sig');assert 'V53_' not in text
        document_hashes[name] = sha(path)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', text):
            target = raw.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target): continue
            destination = (path.parent/urllib.parse.unquote(target)).resolve()
            # A report links to this audit; materialize that one destination last
            # and verify it exists along with every other target after writing.
            assert destination == output or destination.exists(), (name, target)
            destinations.append(destination)
            links += 1
    readme = (ROOT/'README.md').read_text(encoding='utf-8')
    assert '| V53 |' in readme and '最近 V53 完整' in readme and f'{PUBLIC}/reorder-before-after.gif' in readme
    assert f'{PUBLIC}/MR01.mp4' in readme and f'{PUBLIC}/source-frames.mkv' in readme
    progress = (ROOT/'docs/构建进度总表_2026-10-16.md').read_text(encoding='utf-8')
    assert '| 本次状态快照 | 2026-10-18，README V53' in progress and '| 最近完整产品回归 | V53' in progress
    assert '一般非整帧项目时长仍被发布门禁拒绝。' not in progress
    value = {'status': 'passed_scoped_release_audit', 'full_methods': 1223, 'full_suite_seconds': full['suite_seconds'],
        'new_targeted_methods_subset': 40, 'frozen_files': 175, 'baseline_failed_methods': 15,
        'baseline_missing_action_errors': 23, 'baseline_control_passes': 2, 'development_cli_calls': 69,
        'main_frames': 380, 'main_stereo_sample_frames': 1824000, 'independent_PCM_sample_frames': 1152000,
        'independent_pure_cut_RGB_frames': 200, 'independent_alpha_frames': 40, 'same_renderer_reference_frames': 140,
        'pre_edit_reference_frames': 110, 'installed_package_files': 118, 'isolated_installed_cli_calls': 19,
        'installed_frames': 190, 'installed_stereo_sample_frames': 912000, 'retained_partial_failure_runs': 4,
        'skills': 14, 'skill_local_links': 190, 'documents_checked': len(docs), 'document_local_links': links,
        'broken_links': 0, 'document_hashes': document_hashes, 'static_moments_checked': 9,
        'continuous_playback': False, 'listening_review': False, 'other_machine_accepted': False,
        'persistent_magnetic_mode_accepted': False, 'all_capcut_features_and_quality_accepted': False, 'goal_complete': False,
        'full_receipt_sha256': sha(EVIDENCE/'magnetic-reorder-tests-20261018/full-1.json'),
        'media_audit_sha256': sha(EVIDENCE/'magnetic-reorder-real-r5-20261018/media-audit.json'), 'generator_sha256': sha(Path(__file__))}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    assert all(path.exists() for path in destinations)
    print(json.dumps({k: value[k] for k in ('status', 'full_methods', 'frozen_files', 'documents_checked', 'document_local_links', 'broken_links')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args();run(args.output.resolve())
