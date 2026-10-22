"""CAS update private progress; retain a private backup outside publication files."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
REL = ROOT/'docs/validation/evidence/float-standard-20261022-lab'
WORK = ROOT/'product/.runtime/float-standard-20261022'


def main():
    target = MAIN/'product/.runtime/agent-video-kit-progress-20261021.json'
    previous = target.read_bytes(); data = json.loads(previous)
    native = json.loads((REL/'standard-r5/verification.json').read_bytes())
    media = json.loads((REL/'media-r4/verification.json').read_bytes())
    installed_path = REL/'installed-r1/verification.json'
    installed = json.loads(installed_path.read_bytes()) if installed_path.exists() else {}
    owner_path = WORK/'complete-r1/run.json'
    owner = json.loads(owner_path.read_bytes()) if owner_path.exists() else {}
    handles_path = WORK/'owned-tool-handles-r1.json'
    handles = json.loads(handles_path.read_bytes()) if handles_path.exists() else {}
    assert native['status'] == 'passed' and native['methods'] == 17
    assert media['status'] == 'passed-public-CLI-original-and-edited-native-float-media'
    assert native['frozen_after'] == media['frozen_after'] == frozen() and len(frozen()) == 298
    data['float_standard_render_lab'] = {
        'root': str(ROOT), 'status': 'native-17-and-real-public-CLI-media-passed-install-and-complete-status-below',
        'frozen_inputs': 298, 'parent_frozen_inputs': 296, 'changed_parent_files': 8, 'added_product_files': 2,
        'main_integrated': False, 'published': False, 'standard_render_integrated_in_lab': True,
        'default_backend_migrated': False, 'full_capcut_parity': False,
        'targeted_methods': 17, 'targeted_suite_seconds': 200.249,
        'targeted_receipt': str(REL/'standard-r5/verification.json'),
        'media_receipt': str(REL/'media-r4/verification.json'), 'actual_public_render_CLI_processes': 2,
        'media_script_calls': 12, 'media_checks': 16, 'media_frames_each': 20,
        'media_stereo_sample_frames_each': 96000,
        'static_review': str(REL/'static-review-r1.json'), 'viewed_frames': 6,
        'continuous_playback_review': False, 'listening_review': False,
        'installed_status': installed.get('status'), 'installed_owner_pid': installed.get('pid'),
        'installed_expected_methods': 220, 'installed_expected_resources': 179,
        'installed_actual_methods': installed.get('isolated_methods', {}).get('methods'),
        'installed_receipt': str(installed_path),
        'full_suite_status': owner.get('status', 'not-started'), 'full_suite_started': owner.get('suite_launched', False),
        'expected_full_methods': 2337, 'full_suite_owner': str(owner_path), 'full_suite_owner_pid': owner.get('pid'),
        'tools': handles, 'future_main_parent_note': 'Actual V95 full2320/installed203 plus actual published R16 documentation commit, same frozen296 product.',
        'readme_preview': str(WORK/'readme-preview-r1/README.md'),
        'report': str(ROOT/'docs/validation/标准CLI浮点交付实测_2026-10-22.md'),
        'remaining': ['default backend migration', 'all authored effects/transitions/text/crop and mask feather',
                      'preview and persistent cache integration', 'SAR/display matrix/interlace/HDR',
                      'original 2GiB/2hour limit and bounded concurrent total RSS',
                      'natural-media local AI quality and full CapCut parity'],
        'native_windows_only': True, 'virtualization': False, 'new_browser_tabs_opened': 0}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    private = WORK/'private-progress-backups'; private.mkdir(parents=True, exist_ok=True)
    backup = private/(stamp+'.before.json'); backup.write_bytes(previous)
    serialized = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode('utf8')
    temporary = target.with_name('.'+target.name+'.float-standard-'+stamp+'.tmp')
    assert target.read_bytes() == previous, 'concurrent private progress edit; preserve it'
    temporary.write_bytes(serialized)
    assert target.read_bytes() == previous, 'concurrent private progress edit; preserve it'
    os.replace(temporary, target)
    print(json.dumps({'status': 'updated-private-R96-progress', 'installed_status': installed.get('status'),
                      'full_status': owner.get('status'), 'source_inputs': 298}, ensure_ascii=False))


if __name__ == '__main__':
    main()
