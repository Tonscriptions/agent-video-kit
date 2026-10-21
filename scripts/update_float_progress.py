"""Update the private checkpoint from actual receipts without changing main files."""
from datetime import datetime,timezone
import json,os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'

def main():
    progress=MAIN/'product/.runtime/agent-video-kit-progress-20261021.json'
    original=progress.read_bytes();value=json.loads(original)
    kernel=json.loads((REL/'kernel-r11.json').read_bytes());r=kernel['result']
    lineage=json.loads((REL/'parent-rebase-r1.json').read_bytes())
    media=json.loads((REL/'surface-cli-media-r1/verification.json').read_bytes())
    owner=json.loads((ROOT/'product/.runtime/color-precision-20261021/complete-r1/run.json').read_bytes())
    assert value['main']['commit']==lineage['published_parent_commit']=='18f5dc766a80e0b47f096b1b93ccfe1cee0fb5f6'
    lab=value['color_precision_lab']
    lab.update(status='surface-CLI-and-linear-core-media-passed-complete-suite-running',
        current_frozen_inputs=282,resources=171,new_methods=86,kernel_methods=86,
        kernel_native_calls=len(r['native_calls']),kernel_actual_in_process_CLI_calls=len(r['cli_calls']),
        kernel_seconds=r['suite_seconds'],kernel_receipt=str(REL/'kernel-r11.json'),
        source_queue_fix_rebase_pending=False,published_parent_commit=lineage['published_parent_commit'],
        rebase_receipt=str(REL/'parent-rebase-r1.json'),editor_surface_CLI_integrated=True,
        editor_integrated=True,editor_integration_scope='surface export/inspect data interface only',
        timeline_renderer_integrated=False,preview_cache_integrated=False,full_suite_started=owner['suite_launched'],
        expected_full_methods=2234,full_suite_owner=str(ROOT/'product/.runtime/color-precision-20261021/complete-r1/run.json'),
        full_suite_tool_session_id=53704,full_suite_pid=owner['pid'],full_suite_status=owner['status'],
        surface_CLI_media_receipt=str(REL/'surface-cli-media-r1/verification.json'),
        surface_CLI_media_calls=media['CLI_calls'],surface_media_native_script_calls=media['native_script_calls'],
        surface_media_checks=len(media['checks']),surface_media_assets=len(media['assets']),
        surface_bundle_frames={k:v['frames'] for k,v in media['bundles'].items()},
        working_colour='explicit relative D65 BT.709 / linear-light RGB',
        colour_transfer_and_primaries_not_transformed=False,
        colour_scope='bt709/display-p3/bt2020, explicit five transfers; no ICC/PQ/HLG/absolute nits/HDR acceptance',
        decode_boundary='native RGB/gray and explicit YCbCr formats to Float32; direct native alpha normalization',
        current_epoch_receipt=str(REL/'current-epoch-r3.json'),document_links_checked=78,
        static_surface_CLI_contact_sheet_viewed=True,published=False,full_capcut_parity=False,
        next_work=['Finish actual complete2234 and fresh eight-wheel117-method gates without editing frozen product.',
                   'Refresh README/numbered media evidence, docs and 17 Skills; ordinary V92 publication only after actual gates.',
                   'Integrate the shared high-precision policy and native float surfaces into ordinary timeline, preview, cache and all effects; preserve author/native clocks.'])
    installed=REL/'installed-r1/verification.json'
    if installed.exists():
        installed_value=json.loads(installed.read_bytes())
        lab.update(installed_receipt=str(installed),installed_status=installed_value['status'],
                   installed_tool_session_id=None if installed_value['status'].startswith('passed') else 68475)
        if installed_value.get('isolated_methods'):
            lab['installed_methods']=installed_value['isolated_methods']['methods']
    preview=REL/'release-preview-r3.json'
    if preview.exists():
        reviewed=json.loads(preview.read_bytes())
        lab.update(readme_preview_status=reviewed['status'],readme_preview_receipt=str(preview),
                   readme_preview=str(Path(reviewed['preview_root'])/'README.md'),readme_preview_links=len(reviewed['local_links']),
                   candidate_document_and_Skill_count=len(reviewed['documents']))
    chain=ROOT/'product/.runtime/color-precision-20261021/release-chain-r1/run.json'
    if chain.exists():
        chain_value=json.loads(chain.read_bytes())
        lab.update(release_chain_record=str(chain),release_chain_status=chain_value['status'],release_chain_tool_session_id=51155)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=progress.with_name('progress-before-surface-CLI-'+stamp+'.json');backup.write_bytes(original)
    value.update(updated_at_utc=datetime.now(timezone.utc).isoformat(),goal_status='active',previous_progress_snapshot=str(backup))
    value['current_goal_turn_classification']='V91 published; V92 float surface CLI and linear core media passed, full2234 and installed117 gates in progress; not complete CapCut parity'
    assert progress.read_bytes()==original,'concurrent progress update; preserve both and retry'
    temporary=progress.with_name('progress-surface-CLI-'+stamp+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');os.replace(temporary,progress)
    print(json.dumps({'status':lab['status'],'kernel':86,'full_state':owner['status'],'installed_state':lab.get('installed_status'),'main_unchanged':True}))

if __name__=='__main__':main()
