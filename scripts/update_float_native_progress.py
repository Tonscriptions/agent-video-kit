"""Merge actual private progress without rewriting public or frozen inputs."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
REL = ROOT / 'docs/validation/evidence/float-render-20261022-lab'
WORK = ROOT / 'product/.runtime/float-render-20261022'


def read(path):
    for attempt in range(20):
        try: return json.loads(path.read_bytes())
        except (ValueError, PermissionError):
            if attempt == 19: raise
            time.sleep(.05)


def maybe(path): return read(path) if path.exists() else None


def main():
    target = MAIN / 'product/.runtime/agent-video-kit-progress-20261021.json'
    focus = read(REL / 'native-r2.json')
    installed = read(REL / 'installed-r1/verification.json')
    media = read(REL / 'media-r1/verification.json')
    full = maybe(WORK / 'complete-r1/run.json')
    release = maybe(WORK / 'release-chain-r1/run.json')
    handles = maybe(WORK / 'owned-tool-handles.json') or {}
    preview = maybe(REL / 'readme-preview-r2.json') or read(REL / 'readme-preview-r1.json')
    parent_states = []
    for folder, runtime, revision, key, full_session, release_session in (
        ('float-timeline-lab-20261022', 'float-timeline-20261022', 'r2', 'float_timeline_lab', 57563, 46591),
        ('float-stream-lab-20261022', 'float-stream-20261022', 'r1', 'float_stream_lab', 15470, 84163)):
        base = ROOT.parent / folder / 'product/.runtime' / runtime
        parent_full = read(base / ('complete-' + revision) / 'run.json')
        parent_release = read(base / ('release-chain-' + revision) / 'run.json')
        parent_states.append((key, base, parent_full, parent_release, full_session, release_session))
    if any(s[3]['status'].startswith('publishing-') for s in parent_states) or (release and release['status'].startswith('publishing-')):
        print(json.dumps({'status': 'deferred-private-merge-during-actual-publication'}))
        return
    for attempt in range(20):
        old = target.read_bytes()
        progress = json.loads(old)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = target.with_name('progress-before-native-window-' + stamp + '.json')
        for key, base, parent_full, parent_release, fs, rs in parent_states:
            lab = progress[key]
            if not lab.get('published'):
                lab.update(full_suite_owner=str(base / ('complete-r2/run.json' if key == 'float_timeline_lab' else 'complete-r1/run.json')),
                    full_suite_owner_pid=parent_full['pid'], full_suite_status=parent_full['status'],
                    full_suite_started=parent_full['suite_launched'], full_suite_tool_session_id=fs,
                    release_chain_status=parent_release['status'], release_chain_pid=parent_release['pid'],
                    release_chain_tool_session_id=rs)
        item = {'root': str(ROOT), 'status': 'native-window21-and-media-passed-isolated-install-' + installed['status'],
            'published': False, 'modules': ['float_native_pipe', 'float_native_source'],
            'frozen_inputs': 296, 'parent_frozen_inputs': 292, 'foundation_copied_files': 312,
            'targeted_methods': focus['result']['methods'], 'targeted_seconds': focus['result']['seconds'],
            'targeted_receipt': str(REL / 'native-r2.json'), 'targeted_native_tool_launches': len(focus['result']['audited_native_launches']),
            'actual_native_pipe_receipts': len(focus['result']['native_pipe_receipts']),
            'installed_status': installed['status'], 'installed_methods': installed.get('isolated_methods', {}).get('methods'),
            'installed_seconds': installed.get('isolated_methods', {}).get('suite_seconds'),
            'installed_resources': len(installed.get('resource_hashes', {})),
            'installed_origins': len(installed.get('isolated_methods', {}).get('origins', {})),
            'installed_receipt': str(REL / 'installed-r1/verification.json'),
            'installed_tool_session_id': handles.get('installed') if not installed['status'].startswith('passed') else None,
            'media_receipt': str(REL / 'media-r1/verification.json'), 'media_native_launches': media['actual_native_launches'],
            'media_encoders': media['actual_encoder_processes'], 'media_assets': len(media['assets']), 'media_checks': len(media['checks']),
            'media_author_frames_each': 20, 'media_PCM_sample_frames_each': 96000,
            'maximum_native_float_cache_bytes_each': 491520, 'whole_movie_input_float_bundle_required': False,
            'decoded_window_calls_including_baseline_oracle': sum(s['decoded_windows'] for s in media['native_window_source_receipts']),
            'readme_preview': str(Path(preview['preview']) / 'README.md'), 'readme_preview_documents': len(preview['documents']),
            'readme_preview_verified_links': preview['verified_local_links'], 'public_main_readme_updated': False,
            'default_render_preview_queue_cache_integrated': False, 'full_capcut_parity': False,
            'native_windows_only': True, 'virtualization': False, 'new_browser_tabs_opened': 0,
            'source_policy': 'registered local source and explicit RGB/YUV signal; independent Windows deny-write/delete handles',
            'remaining': ['standard CLI render/preview/queue/cache integration', 'all authored operators and audio stretch',
                'SAR/display-matrix presentation and formal output encoders', 'existing original-import 2GiB/2hour limit',
                'bounded concurrent total RSS and long-GOP reverse strategy', 'local AI quality, natural media, HDR and complete CapCut parity'],
            'preserved_failure': str(REL / 'native-r1.json'), 'repair_audit': str(REL / 'native-r1-repair-audit.json'),
            'full_discovered_methods': 2320, 'expected_full_methods': 2320, 'full_suite_passed': False,
            'full_suite_started': full['suite_launched'] if full else False}
        if full:
            item.update(full_suite_owner=str(WORK / 'complete-r1/run.json'), full_suite_owner_pid=full['pid'],
                full_suite_tool_session_id=handles.get('complete'), full_suite_status=full['status'])
        if release:
            item.update(release_chain_record=str(WORK / 'release-chain-r1/run.json'), release_chain_pid=release['pid'],
                release_chain_status=release['status'], release_chain_tool_session_id=handles.get('release'), publication_prepared=True)
        preflight = maybe(WORK / 'source-preflight-r1/run.json')
        if preflight:
            item.update(publication_preflight=str(WORK / 'source-preflight-r1/run.json'), publication_preflight_status=preflight['status'])
        if not progress.get('float_native_source_lab', {}).get('published'):
            progress['float_native_source_lab'] = item
        progress.update(updated_at_utc=datetime.now(timezone.utc).isoformat(), goal_status='active',
            previous_progress_snapshot=str(backup), current_goal_turn_classification='progress: native-window source21 and real original-source media passed; fresh install203 and serialized full2320 statuses retained; standard renderer and complete CapCut parity remain unfinished')
        progress['next_steps'] = [
            'Retain terminal V92 full2234/installed117 publication177765f; no duplicate full or force push.',
            'R93 actual full2280 owner57563/release46591, R94 full2299 owner15470/release84163 are already dispatched; do not mutate their frozen inputs/scripts.',
            'Inspect native-window installed203/full2320/release owners via float_native_source_lab; only actual terminal evidence permits ordinary publication and numbered README update.',
            'Continue standard render/preview/queue/cache integration using explicit source/color contracts, then all authored effects, audio/stretch, local AI, long-media/RSS, orientation/HDR and independent natural-media acceptance until complete parity is actually achieved.']
        if target.read_bytes() != old:
            continue
        backup.write_bytes(old)
        temporary = target.with_name('.native-window-progress-' + stamp + '.tmp')
        temporary.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        if target.read_bytes() != old:
            temporary.unlink()
            continue
        os.replace(temporary, target)
        print(json.dumps({'status': 'merged-actual-private-checkpoint', 'main': progress['main']['version'],
            'targeted': 21, 'installed': installed['status'], 'full': full['status'] if full else 'not-dispatched', 'goal': 'active'}))
        return
    raise RuntimeError('private checkpoint remained concurrent during all CAS attempts')


if __name__ == '__main__':
    main()
