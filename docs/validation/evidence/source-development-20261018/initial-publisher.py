"""Publish and cross-check the V40 source-edit evidence, without running tests."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT/'docs/validation/evidence'
RUNTIME = ROOT/'product/.runtime'
PUBLIC = ROOT/'docs/assets/source-edits-20261018'


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n',
                    encoding='utf-8', newline='\n')


def inventory(folder):
    return {p.relative_to(folder).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in sorted(folder.rglob('*')) if p.is_file()}


def support():
    development = EV/'source-development-20261018'
    development.mkdir(exist_ok=False)
    histories = []
    for name, note in (
        ('source-dev-targeted-20261018', '37 methods: 36 passed, one wrong padded-author fixture; not final source.'),
        ('source-dev-targeted-fixed-20261018', '40 passed on earlier source, before legacy compose routing and final capabilities.'),
        ('source-dev-previous-range-20261018', '53 prior range tests passed but source changed during run; frozen_equal=false.')):
        for ext in ('.json', '.log'):
            shutil.copyfile(RUNTIME/(name+ext), development/(name+ext))
        value = load(development/(name+'.json'))
        histories.append({'name': name, 'methods': value['methods'], 'exit_code': value['exit_code'],
                          'frozen_equal': value['frozen_equal'], 'note': note})
    interrupted = [RUNTIME/'source-public-dev-20261018', RUNTIME/'source-smoke-20261018']
    entries = {}
    with zipfile.ZipFile(development/'interrupted-media.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for folder in interrupted:
            assert folder.is_dir(), folder
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    name = folder.name+'/'+path.relative_to(folder).as_posix()
                    archive.write(path, name)
                    entries[name] = {'sha256': sha(path), 'bytes': path.stat().st_size}
        assert archive.testzip() is None
    save(development/'verification.json', {
        'status': 'retained-original-development-evidence', 'records': histories,
        'interrupted_media': {'status': 'explicitly-interrupted-before-final-freeze',
                             'completed_case_count': 0, 'note': 'Stopped to unify legacy compose/capabilities; no timeout restart or accepted media result.',
                             'files': entries},
        'files': inventory(development), 'cannot_add_pass_counts': True})

    wheel_source = RUNTIME/'source-wheel-final-20261018'
    wheel_target = EV/'source-wheel-20261018'
    wheel = load(wheel_source/'verification.json')
    assert wheel['status'] == 'passed'
    wheel_target.mkdir(exist_ok=False)
    shutil.copyfile(wheel_source/'verification.json', wheel_target/'verification.json')
    shutil.copyfile(wheel_source/'dist'/wheel['wheel']['filename'], wheel_target/wheel['wheel']['filename'])
    with zipfile.ZipFile(wheel_target/'raw-cli-and-build.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted([*wheel_source.glob('*.log'), wheel_source/'calls-in-progress.json']):
            archive.write(path, path.name)
        assert archive.testzip() is None
    save(EV/'source-static-review-20261018.json', {
        'status': 'reviewed-selected-stills', 'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
        'files': {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
                  for p in [PUBLIC/f'comparison-{index:02}.png' for index in (0, 6, 12, 19)]},
        'layout': 'Left fixed V39 manual author / right current actual; top S02 two-sided extension, bottom S07 linked roll.',
        'gif_frames': [0, 6, 12, 19], 'output_frames': [0, 12, 24, 38],
        'observed': 'Paired counters, gray backgrounds and white bars align at all four reviewed moments. Top source counters 010/022/034/048, bottom 010/022/034/058. Edge counter glyphs are partly clipped; synthetic low-resolution charts do not validate natural typography or advertising quality.',
        'continuous_playback': False, 'listening': False, 'new_model_inference': 0,
        'complete_capcut_parity_accepted': False})
    print(json.dumps({'development_records': len(histories), 'interrupted_files': len(entries),
                      'wheel_files': len(inventory(wheel_target)), 'static_frames': 4}))


def final():
    from smoke_fragments import frozen

    full = load(EV/'source-final-full-20261018.json')
    log = EV/'source-final-full-20261018.log'
    terminal = re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK\s*$', log.read_text(encoding='utf-8'))
    assert terminal and int(terminal[1]) == full['methods'] == 938
    assert full['exit_code'] == 0 and full['terminal_ok'] and full['skipped'] == 0 and full['frozen_equal']
    assert full['frozen_before'] == full['frozen_after'] == frozen()
    assert len(full['frozen_after']) == 132 and sha(log) == full['log_sha256']
    smoke = load(PUBLIC/'verification.json')
    assert smoke['status'] == 'passed' and smoke['worker_processes_exited']
    assert smoke['source_before'] == smoke['source_after'] == full['frozen_after']
    assert len(smoke['cases']) == smoke['case_count'] == 9 and smoke['cli_count'] == 79
    assert smoke['output_frames'] == 505 and smoke['output_stereo_sample_frames'] == 2424000
    calls = smoke['cli_calls']
    assert all(item['exit_code'] == item['expected_exit_code'] for item in calls)
    successes = sum(item['exit_code'] == 0 for item in calls)
    assert successes == 66 and sum(item['mismatches'] for item in smoke['source_frame_identities']) == 0
    media = load(EV/'source-media-audit-20261018.json')
    assert media['status'] == 'passed' and media['source_unchanged'] and media['public_files'] == 301
    for name, item in media['public_sha256'].items():
        assert sha(PUBLIC/name) == item['sha256'], name
    wheel_dir = EV/'source-wheel-20261018'
    wheel = load(wheel_dir/'verification.json')
    assert wheel['status'] == 'passed' and wheel['file_count'] == 90 and len(wheel['calls']) == 26
    assert wheel['frozen_before'] == wheel['frozen_after'] == full['frozen_after']
    for name, item in wheel['source_files'].items():
        assert sha(ROOT/'product/src'/name) == item['sha256'], name
    assert sha(wheel_dir/wheel['wheel']['filename']) == wheel['wheel']['sha256']
    skills = load(EV/'source-skills-20261018.json')
    assert skills['skill_count'] == 14 and skills['local_links_checked'] == 128
    for item in skills['results']:
        assert sha(ROOT/'skills'/item['skill']/'SKILL.md') == item['sha256']
    static = load(EV/'source-static-review-20261018.json')
    for name, item in static['files'].items():
        assert sha(ROOT/name) == item['sha256']
    development = EV/'source-development-20261018'
    for path in [development/'interrupted-media.zip', wheel_dir/'raw-cli-and-build.zip']:
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
    generators = ('scripts/smoke_source_edits.py', 'scripts/audit_source_edit_media.py',
                  'scripts/audit_source_edit_wheel.py', 'scripts/audit_source_edit_skills.py',
                  'scripts/finalize_source_edits.py', 'scripts/run_frozen_regression.py')
    record = {'status': 'passed', 'at_utc': datetime.now(timezone.utc).isoformat(), 'full': full,
              'source_methods_in_full': 41, 'public_smoke': {
                  'case_count': 9, 'cli_count': 79, 'cli_success': successes,
                  'current_expected_rejections': 4, 'fixed_v39_missing_feature_rejections': 9,
                  'output_frames': 505, 'output_stereo_sample_frames': 2424000,
                  'baseline': smoke['baseline'], 'source_frame_identities': smoke['source_frame_identities'],
                  'cli_execution': smoke['cli_execution'], 'worker_processes_exited': True,
                  'compatibility_reference': smoke['compatibility_reference']},
              'public_media_audit': media, 'static_review': static,
              'wheel': {**wheel, 'files': inventory(wheel_dir)}, 'skills': skills,
              'development': load(development/'verification.json'), 'development_files': inventory(development),
              'generators': {name: {'sha256': sha(ROOT/name)} for name in generators},
              'new_model_inference': 0, 'virtualization': False, 'local_browser_tabs_created': 0,
              'complete_capcut_parity_accepted': False, 'goal_still_active': True,
              'limits': [
                  'Source extension reauthors effects/edge fades/retiming; no old processed-body preservation claim.',
                  'Nested curves retain native duration renormalization and explicit warning; old-body sample clock preservation remains open.',
                  'Recorded finite source bounds; fractional head source ticks reject, minimal whole tail ticks are window-cropped.',
                  'Tracking-observation replanning and partial real-transition endpoint resize remain explicit errors.',
                  'Manual fixed V39 author projects use the same renderer; only two direct-source frame-identity checks are independent of author planning.',
                  'Synthetic short CC0 fixtures; no continuous playback/listening, natural advertising quality, HDR/VFR or long-project RSS acceptance.',
                  'Wheel product imports isolated, existing optional dependencies reused; clean machine and bundled schema not accepted.',
                  'Full magnetism, open content/template library scale and complete CapCut equivalence remain open.']}
    save(EV/'source-edits-20261018.json', record)
    print(json.dumps({'methods': full['methods'], 'suite_seconds': full['suite_seconds'],
                      'frozen_files': 132, 'public_files': media['public_files'],
                      'public_bytes': media['public_bytes'], 'wheel_cli': 26, 'skills_links': 128}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['support', 'final'])
    args = parser.parse_args()
    {'support': support, 'final': final}[args.phase]()
