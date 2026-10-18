"""Bind V58 code, complete tests, actual media, installed bytes, failures, skills and docs."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import zipfile
from run_frozen_regression import frozen
from sync_color_automation_documents import ROOT, EVIDENCE, PUBLIC, NATIVE, CONTRACT, REPORT, DOCS

FINAL = EVIDENCE/'release.json'
def read(path): return json.loads(path.read_bytes())
def digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path): return digest(path.read_bytes())
def walk(rows):
    for row in rows:
        yield row
        if isinstance(row.get('inputs'), list): yield from walk(row['inputs'])

def run(output, preflight):
    assert not output.exists(); current = frozen(); assert len(current) == 186
    full = read(EVIDENCE/'full-final.json'); assert full['frozen_before'] == current
    if not preflight:
        assert full['terminal_ok'] and full['exit_code'] == full['skipped'] == 0 and full['methods'] == 1357
        assert full['frozen_before'] == full['frozen_after'] == current and full['frozen_equal']
        assert sha(EVIDENCE/'full-final.log') == full['log_sha256']
    targeted = read(EVIDENCE/'targeted-final.json')
    assert targeted['terminal_ok'] and targeted['methods'] == 28 and targeted['exit_code'] == targeted['skipped'] == 0
    assert targeted['frozen_before'] == targeted['frozen_after'] == current
    assert sha(EVIDENCE/'targeted-final.log') == targeted['log_sha256']
    smoke = read(PUBLIC/'verification.json'); native = read(NATIVE/'verification.json')
    assert smoke['status'] == native['status'] == 'passed'
    for r in (smoke, native): assert r['frozen_before'] == r['frozen_after'] == current
    assert smoke['cli_calls'] == 64 and len(smoke['cases']) == 14 and smoke['baseline_cli_calls'] == 5
    assert smoke['main_frames'] == 262 and smoke['stereo_sample_frames'] == 1158528
    assert len(smoke['independent_rgb_cases']) == 13
    assert max(c['max_rgb_error'] for c in smoke['cases'] if c['rgb_acceptance_applies']) == 1
    assert all(c['max_alpha_error'] == c['max_pcm_error'] == 0 for c in smoke['cases'])
    text = next(c for c in smoke['cases'] if c['name'] == 'CA12')
    assert text['animated_text_rgb_changes_observed'] and text['max_rgb_error'] == 122 and not text['rgb_acceptance_applies']
    assert sha(ROOT/'scripts/smoke_color_automation.py') == sha(PUBLIC/'executed-generator.py') == smoke['generator_sha256']
    for name, row in smoke['files'].items():
        p = PUBLIC/name; assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], p
    calls = read(PUBLIC/'calls.json'); assert len(calls) == 64
    for call in calls:
        assert call['exit_code'] == call['expected_exit_code'] == 0
        assert sha(PUBLIC/call['result']) == call['result_sha256'] and read(PUBLIC/call['result'])['ok']
    for case in smoke['cases']:
        manifest = read(PUBLIC/(case['name']+'.manifest.json'))
        instances = [row for row in walk(manifest['inputs']) if row.get('kind') == 'effect-automation']
        budget = [row for row in walk(manifest['inputs']) if row.get('kind') == 'effect-automation-budget']
        assert len(budget) == 1 and budget[0]['recursive_shared']
        assert len(instances) == len({row['target'] for row in instances}) == budget[0]['targets'] == case['runtime_instances']
        assert sum(row['state_samples'] for row in instances) == budget[0]['state_samples']
        assert sum(row['command_count'] for row in instances) == budget[0]['commands'] == case['command_count']
        assert sum(row['command_bytes'] for row in instances) == budget[0]['command_bytes']
        for ordinal, row in enumerate(instances):
            command = PUBLIC/f"{case['name']}-commands-{ordinal:02}.ffcmd"
            assert sha(command) == row['command_file_sha256'] and command.stat().st_size == row['command_bytes']
            assert row['backend']+'@'+row['target'] in manifest['filter_complex']
        for value, limit in budget[0]['limits'].items():
            assert budget[0][value] <= limit
    old = read(PUBLIC/'baseline-v57.json'); assert len(old['cases']) == 5
    assert old['commit'] == '2f6ee73c37ba05c33fe89495d19b6b4c3d2a612f'
    for row in old['cases']:
        assert row['exit_code'] == 0 and row['reference_error'] > 2 and not row['accepted']
        assert sha(PUBLIC/(row['name']+'-v57.mkv')) == row['output_sha256']
    media = read(EVIDENCE/'media-final.json'); static = read(EVIDENCE/'static-review-final.json')
    assert media['status'] == 'passed_scoped_media_audit' and media['source_receipt_sha256'] == sha(PUBLIC/'verification.json')
    assert media['generator_sha256'] == sha(ROOT/'scripts/audit_color_automation_media.py')
    assert len(media['masters']) == len(media['previews']) == 14 and len(static['images']) == 2
    assert media['master_frames'] == 262 and media['master_stereo_sample_frames'] == 1158528
    assert media['gif']['width'] == 640 and media['gif']['height'] == 432 and media['gif']['frames'] == 20 and media['gif']['duration_ms'] == 2000
    assert media['gif']['sha256'] == sha(PUBLIC/'color-automation.gif')
    assert not static['continuous_playback'] and not static['human_listening'] and not static['natural_ad_quality_accepted']
    for row in static['images']: assert sha(Path(row['path'])) == row['sha256']
    assert native['installer_exit_code'] == 0 and native['isolated_cli_calls'] == 65 and native['installed_package_files'] == 124
    assert native['package_bytes_equal_to_wheel_and_source'] and len(native['outputs']) == 15
    assert native['actual_new_frames'] == 282 and native['actual_new_stereo_sample_frames'] == 1254528
    assert all(r['max_rgb_error'] == r['max_alpha_error'] == r['max_pcm_error'] == 0 and r['exact'] for r in native['outputs'])
    assert native['negative']['unknown_property_exit'] == 2 and native['negative']['project_bytes_unchanged']
    assert native['negative']['cache_tamper_exit'] == 6 and native['negative']['cache_restored']
    assert sha(ROOT/'scripts/verify_color_automation_native.py') == sha(NATIVE/'executed-generator.py') == native['generator_sha256']
    group_path = ROOT/'docs/validation/evidence/color-group-native-r2-20261019-v58'
    group_public = ROOT/'docs/assets/color-group-r2-20261019-v58'
    group = read(group_path/'verification.json')
    assert group['status'] == 'passed' and group['frozen_before'] == group['frozen_after'] == current
    assert group['isolated_cli_calls'] == 6 and group['frames'] == 20 and group['stereo_sample_frames'] == 96000
    assert group['runtime_instances'] == 6 and group['unique_targets'] and group['repeated_instances_exact']
    assert group['max_rgb_error'] == group['max_alpha_error'] == group['max_pcm_error'] == 0
    assert group['container_changes_rgb_max'] == 14 and group['installed_files'] == native['installed_files']
    assert group['generator_sha256'] == sha(ROOT/'scripts/verify_color_automation_group.py') == sha(group_path/'executed-generator.py')
    assert group['source_package_sha256'] == sha(PUBLIC/'CA06.aevpkg.zip')
    group_calls = read(group_path/'calls.json'); assert len(group_calls) == 6
    for i, call in enumerate(group_calls, 1):
        assert '-I' in call['command'] and '-S' in call['command'] and call['exit_code'] == 0
        assert sha(group_path/f'{i:03}.stdout.json') == call['stdout_sha256']
        assert sha(group_path/f'{i:03}.stderr.log') == call['stderr_sha256']
    assert set(group['files']) == {p.relative_to(group_public).as_posix() for p in group_public.rglob('*') if p.is_file()}
    for name, row in group['files'].items():
        path = group_public/name; assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes']
    group_probes = {}
    for extension in ('mkv', 'mp4'):
        path = group_public/('CA15-group.'+extension)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(path)], capture_output=True, check=True, timeout=120)
        value = json.loads(probe.stdout); video = next(s for s in value['streams'] if s['codec_type'] == 'video')
        assert int(video['nb_read_frames']) == 20 and video['avg_frame_rate'] == '10/1'
        assert video['width'] == 160 and video['height'] == 96
        group_probes[extension] = {'command': ['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(path)],
                                  'exit_code': probe.returncode, 'stdout_sha256': digest(probe.stdout), 'probe': value}
    for kind, options, wanted in [('video', ['-map', '0:v:0', '-an', '-fps_mode', 'passthrough', '-pix_fmt', 'rgba', '-f', 'rawvideo'], group['decoded_rgba_sha256']),
                                  ('audio', ['-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2', '-f', 'f32le'], group['decoded_pcm_sha256'])]:
        decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(group_public/'CA15-group.mkv'), *options, 'pipe:1'], capture_output=True, check=True, timeout=120)
        assert digest(decoded.stdout) == wanted, kind
    first_group_path = ROOT/'docs/validation/evidence/color-group-native-20261019-v58'
    first_group = read(first_group_path/'failure.json'); first_group_calls = read(first_group_path/'calls.json')
    assert len(first_group_calls) == 4 and first_group_calls[-1]['exit_code'] == 2
    assert first_group['frozen_before'] == current and (first_group_path/'executed-generator.py').exists()
    for call in native['calls']:
        index = call['index']; assert '-I' in call['command'] and '-S' in call['command']
        assert call['exit_code'] == call['expected_exit_code']
        assert sha(NATIVE/f'{index:03}.stdout.json') == call['stdout_sha256'] and sha(NATIVE/f'{index:03}.stderr.log') == call['stderr_sha256']
    assert not native['virtual_environment'] and not native['network_used'] and not native['other_machine_accepted']
    release = PUBLIC/'agent-video-kit-cp313-win_amd64.zip'
    assert sha(release) == native['release_zip_sha256'] and sha(PUBLIC/'release-manifest.json') == native['manifest_sha256']
    with zipfile.ZipFile(release) as z:
        manifest = json.loads(z.read('manifest.json')); assert z.read('manifest.json') == (PUBLIC/'release-manifest.json').read_bytes()
        assert len(manifest['wheels']) == 7 and not manifest['python_included'] and not manifest['ffmpeg_included']
        for row in manifest['files']:
            raw = z.read(row['path']); assert len(raw) == row['bytes'] and digest(raw) == row['sha256']
        product = next(r for r in manifest['wheels'] if r['name'] == 'ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(z.read(product['path']))) as wheel:
            names = {n for n in wheel.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')}
            assert len(names) == 124 and names == set(native['installed_files'])
            for name in names:
                raw = wheel.read(name); assert raw == (ROOT/'product/src'/name).read_bytes() and digest(raw) == native['installed_files'][name]
            assert 'ai_ad_editor/effect_automation.py' in names
    schema = ROOT/'docs/specs/agent-project.schema.json'
    assert schema.read_bytes() == (ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes() and sha(schema) == manifest['schema_sha256']
    precision_path = EVIDENCE/'precision-reproduced'; precision = read(precision_path/'verification.json')
    assert precision['status'] == 'passed_scoped_boundary_diagnosis' and precision['original_threshold'] == 2 and not precision['threshold_changed']
    assert precision['summary'] == {'premature_direct_RGBA_reference_to_master': 3, 'direct_RGBA_reference_to_actual_raw_graph': 0,
        'same_composite_and_709_encoding_static_reference_to_master': 0}
    assert precision['generator_sha256'] == sha(ROOT/'scripts/audit_color_automation_precision.py') == sha(precision_path/'executed-generator.py')
    assert precision['actual_raw_graph_sha256'] == sha(precision_path/'CA04-actual-graph-rgba.nut')
    development = read(EVIDENCE/'development/index.json'); assert development['status'] == 'preserved_and_verified'
    assert development['generator_sha256'] == sha(ROOT/'scripts/audit_color_automation_development.py')
    assert len(development['runs']) == 8 and development['file_count'] == len(development['files']) == 941
    for row in development['files']:
        p = ROOT/row['path']; assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], p
    refresh_path = ROOT/'docs/validation/evidence/openfilm-refresh-20261019-r05/verification.json'
    research_path = ROOT/'docs/validation/evidence/openfilm-reuse-final-20261019-r05'
    refresh = read(refresh_path); research = read(research_path/'verification.json')
    assert research['status'] == 'passed_scoped_research' and research['refresh_receipt_sha256'] == sha(refresh_path)
    assert research['head'] == refresh['head'] == '7a64d1feacdb59fb631694af7501a4ca570254ca'
    assert research['totals'] == {'tests': 64, 'pass': 63, 'fail': 0, 'skipped': 1}
    assert research['source_before'] == research['source_after'] == refresh['head_hashes'] and research['source_files'] == 727
    assert len(research['core_files_unchanged']) == 148 and research['frozen_before'] == research['frozen_after'] == current
    assert not research['runtime_updated'] and not research['gui_started'] and not research['providers_called']
    assert research['generator_sha256'] == sha(ROOT/'scripts/audit_openfilm_r05.py') == sha(research_path/'executed-generator.py')
    assert sha(research_path/'upstream-selected.stdout.log') == research['stdout_sha256']
    assert sha(research_path/'upstream-selected.stderr.log') == research['stderr_sha256']
    assert sha(ROOT/refresh['source_archive']) == refresh['source_archive_sha256']
    skills = read(EVIDENCE/'skills.json'); mapping = read(ROOT/'video-cut-install-manifest.json')
    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 206
    assert mapping['current_audit']['record_sha256'] == sha(EVIDENCE/'skills.json')
    for row in skills['results']:
        name = row['skill']; assert name.startswith('video-cut-') and sha(ROOT/'skills'/name/'SKILL.md') == row['sha256']
        assert (Path('C:/Users/carzy/.codex/skills')/name).resolve() == (ROOT/'skills'/name).resolve()
        assert next(s for s in mapping['skills'] if s['name'] == name)['skill_md_sha256'] == row['sha256'][7:]
    docs = [ROOT/n for n in DOCS]+[ROOT/'docs/specs'/CONTRACT, ROOT/'docs/validation'/REPORT,
        ROOT/'docs/specs/本地效果目录与参数契约_v0.1_2026-10-14.md', ROOT/'docs/OpenFilm最新源码复核与降本清单_2026-10-18.md',
        ROOT/'docs/OpenFilm复用复核与开发成本更新_2026-10-19.md']
    links = []
    for doc in docs:
        source = doc.read_text(encoding='utf-8-sig')
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', source):
            target = raw.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target): continue
            path = (doc.parent/urllib.parse.unquote(target)).resolve(); assert path.exists() or path == FINAL, (doc, raw)
            links.append({'document': doc.relative_to(ROOT).as_posix(), 'target': raw})
        if not preflight and '<!-- V58-CURRENT -->' in source:
            assert '完整回归运行中' not in source.split('<!-- V58-CURRENT -->', 1)[1].split('<!-- /V58-CURRENT -->', 1)[0]
    process = subprocess.run(['powershell', '-NoProfile', '-Command',
        "@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.Name -in @('chrome-headless-shell.exe','chrome.exe','node.exe') -and ($_.CommandLine -like '*AI广告剪辑*html-toolchain*' -or $_.CommandLine -like '*AI广告剪辑*html_motion_worker.mjs*') } | Select-Object ProcessId,ParentProcessId,Name,CommandLine) | ConvertTo-Json -Depth 3 -Compress"], capture_output=True, check=True)
    residual = json.loads(process.stdout.decode('utf-8-sig').strip() or '[]')
    if isinstance(residual, dict): residual = [residual]
    if not preflight: assert not residual, residual
    extras = {'verification.json', 'encoded-static-review.png', 'timeline-static-review.png',
              'agent-video-kit-cp313-win_amd64.zip', 'release-manifest.json', 'install-receipt.json'}
    assert {p.relative_to(PUBLIC).as_posix() for p in PUBLIC.rglob('*') if p.is_file()} == set(smoke['files']) | extras
    record = {'status': 'passed_preflight_full_pending' if preflight else 'passed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'generator_sha256': sha(Path(__file__)), 'frozen_files': len(current), 'source_freeze': current,
        'full_methods': full.get('methods'), 'new_methods': 28, 'main_cli_calls': 64, 'main_frames': 262,
        'stereo_sample_frames': 1158528, 'native_cli_calls': 65, 'native_package_files': 124, 'native_frames': 282,
        'native_stereo_sample_frames': 1254528, 'skill_count': 14, 'skill_local_links': 206,
        'compound_own_effect_cli_calls': 6, 'compound_own_effect_frames': 20, 'compound_own_effect_sample_frames': 96000,
        'compound_own_effect_receipt_sha256': sha(group_path/'verification.json'),
        'compound_initial_failure_sha256': sha(first_group_path/'failure.json'),
        'compound_media_probes': group_probes,
        'documents': {p.relative_to(ROOT).as_posix(): sha(p) for p in docs}, 'document_local_links': len(links),
        'fixed_toolchain_residual_processes': residual, 'public_files': {p.relative_to(PUBLIC).as_posix():
            {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(PUBLIC.rglob('*')) if p.is_file()},
        'suite_receipt_sha256': sha(EVIDENCE/'full-final.json'), 'native_receipt_sha256': sha(NATIVE/'verification.json'),
        'media_receipt_sha256': sha(EVIDENCE/'media-final.json'), 'static_review_sha256': sha(EVIDENCE/'static-review-final.json'),
        'development_index_sha256': sha(EVIDENCE/'development/index.json'), 'full_capcut_parity_accepted': False,
        'openfilm_research_receipt_sha256': sha(research_path/'verification.json'), 'openfilm_research_pass': 63, 'openfilm_research_skipped': 1,
        'other_machine_accepted': False, 'natural_color_quality_accepted': False, 'human_listening': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: record[k] for k in ('status', 'frozen_files', 'full_methods', 'document_local_links', 'native_package_files', 'skill_count')}))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True); p.add_argument('--preflight', action='store_true')
    a = p.parse_args(); run(a.output.resolve(), a.preflight)
