"""CAS update only this candidate's private progress; keep the full goal open."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from run_frozen_regression import frozen

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
REL = ROOT/'docs/validation/evidence/float-preview-20261022-lab'
WORK = ROOT/'product/.runtime/float-preview-20261022'


def read_optional(path):
    return json.loads(path.read_bytes()) if path.exists() else {}


def main():
    target = MAIN/'product/.runtime/agent-video-kit-progress-20261021.json'
    previous = target.read_bytes(); data = json.loads(previous)
    native = read_optional(REL/'native-r2/verification.json'); media = read_optional(REL/'media-r1/verification.json')
    installed = read_optional(REL/'installed-r1/verification.json'); owner = read_optional(WORK/'complete-r1/run.json')
    assert native['status'] == 'passed' and native['methods'] == 57
    assert media['status'] == 'passed-public-CLI-original-edited-and-native-float-previews'
    assert native['frozen_after'] == media['frozen_after'] == frozen() and len(frozen()) == 300
    data['float_preview_lab'] = {'root': str(ROOT), 'status': 'source57-and-real-CLI-previews-passed-install-full-status-below',
        'frozen_inputs': 300, 'parent_frozen_inputs': 298, 'changed_parent_files': 2, 'added_product_files': 2,
        'source_methods': 57, 'new_preview_methods': 18, 'legacy_preview_methods': 22, 'standard_render_methods': 17,
        'source_suite_seconds': 532.355, 'source_receipt': str(REL/'native-r2/verification.json'),
        'media_receipt': str(REL/'media-r1/verification.json'), 'actual_render_CLI_processes': 2,
        'actual_preview_CLI_processes': 3, 'media_script_calls': 20, 'media_checks': 27,
        'preview_frames': 14, 'preview_stereo_sample_frames': 67200,
        'static_review': str(REL/'static-review-r1.json'), 'viewed_panels': 6,
        'continuous_playback_review': False, 'listening_review': False,
        'installed_status': installed.get('status'), 'installed_actual_methods': installed.get('isolated_methods', {}).get('methods'),
        'installed_expected_methods': 260, 'installed_expected_resources': 180, 'installed_pid': installed.get('pid'),
        'installed_receipt': str(REL/'installed-r1/verification.json'),
        'full_status': owner.get('status', 'not-started'), 'full_suite_started': owner.get('suite_launched', False),
        'full_expected_methods': 2355, 'full_pid': owner.get('pid'), 'full_owner': str(WORK/'complete-r1/run.json'),
        'tools': read_optional(WORK/'owned-tool-handles-r1.json'),
        'readme_preview': str(WORK/'readme-preview-r1/README.md'), 'report': str(ROOT/'docs/validation/浮点时间线预览与缓存实测_2026-10-22.md'),
        'main_integrated': False, 'published': False, 'default_backend_migrated': False, 'full_capcut_parity': False,
        'remaining': ['default Float32 backend migration', 'port all effects transitions captions crop tracking and feather',
                      'natural local-model quality', 'SAR orientation interlace HDR and ICC',
                      'long-form original import limits and bounded total concurrent RSS', 'full CapCut parity'],
        'native_windows_only': True, 'virtualization': False, 'new_browser_tabs_opened': 0}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backups = WORK/'private-progress-backups'; backups.mkdir(parents=True, exist_ok=True)
    (backups/(stamp+'.before.json')).write_bytes(previous)
    temporary = target.with_name('.'+target.name+'.float-preview-'+stamp+'.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    assert target.read_bytes() == previous, 'concurrent private progress edit preserved'
    os.replace(temporary, target)
    print(json.dumps({'status': 'updated-private-R97-progress', 'installed': installed.get('status'), 'full': owner.get('status')}))


if __name__ == '__main__':
    main()
