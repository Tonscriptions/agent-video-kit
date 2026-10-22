"""CAS-merge actual owned task states without touching public main files."""
from datetime import datetime,timezone
import json,pathlib,time
ROOT=pathlib.Path(__file__).resolve().parents[1];MAIN=ROOT.parents[2]

def read(path):
    for attempt in range(20):
        try:return json.loads(path.read_bytes())
        except (ValueError,PermissionError):
            if attempt==19:raise
            time.sleep(.1)

def main():
    target=MAIN/'product/.runtime/agent-video-kit-progress-20261021.json';stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    timeline=MAIN/'product/.runtime/float-timeline-lab-20261022';state=timeline/'product/.runtime/float-timeline-20261022'
    complete=read(state/'complete-r2/run.json');release=read(state/'release-chain-r2/run.json')
    audio=read(ROOT/'docs/validation/evidence/float-stream-20261022-lab/audio-r3.json')
    stream=read(ROOT/'docs/validation/evidence/float-stream-20261022-lab/stream-r2.json')
    current=ROOT/'product/.runtime/float-stream-20261022'
    full=read(current/'complete-r1/run.json') if (current/'complete-r1/run.json').exists() else None
    chain=read(current/'release-chain-r1/run.json') if (current/'release-chain-r1/run.json').exists() else None
    handles=read(current/'owned-tool-handles.json') if (current/'owned-tool-handles.json').exists() else {}
    installed=read(ROOT/'docs/validation/evidence/float-stream-20261022-lab/installed-r1/verification.json')
    for attempt in range(20):
        old=target.read_bytes();progress=json.loads(old);backup=target.with_name('progress-before-float-stream-'+stamp+'.json')
        lab=progress['float_timeline_lab']
        if not lab.get('published'):
            lab.update(full_suite_owner=str(state/'complete-r2/run.json'),full_suite_owner_pid=complete['pid'],
                full_suite_tool_session_id=57563,full_suite_status=complete['status'],full_suite_started=complete['suite_launched'],
                publication_prepared=True,release_chain_record=str(state/'release-chain-r2/run.json'),
                release_chain_status=release['status'],release_chain_tool_session_id=46591,release_chain_pid=release['pid'],
                aborted_never_launched_owner=str(timeline/'docs/validation/evidence/float-timeline-20261022-lab/aborted-complete-r1/verification.json'),
                portable_replay_receipt=str(timeline/'docs/validation/evidence/float-timeline-20261022-lab/media-installed-r2/verification.json'),
                readme_preview=str(state/'readme-preview-r2/README.md'),readme_preview_verified_links=2769,
                readme_preview_receipt=str(timeline/'docs/validation/evidence/float-timeline-20261022-lab/readme-preview-r2.json'))
        stream_state={'root':str(ROOT),'status':'real-native-stream-19-targeted-and-isolated182-passed-awaiting-complete2299',
            'published':False,'default_render_preview_queue_integrated':False,'full_capcut_parity':False,
            'frozen_inputs':292,'foundation_copied_files':308,'parent_frozen_inputs':288,
            'parent_publication_at_foundation':False,'modules':['float_audio_graph','float_stream'],
            'audio_receipt':str(ROOT/'docs/validation/evidence/float-stream-20261022-lab/audio-r3.json'),
            'audio_status':audio['status'],'audio_methods':audio.get('result',{}).get('methods'),
            'audio_script_FFmpeg_calls':len(audio.get('result',{}).get('script_FFmpeg_calls',[])),
            'stream_receipt':str(ROOT/'docs/validation/evidence/float-stream-20261022-lab/stream-r2.json'),
            'stream_status':stream['status'],'stream_methods':stream.get('result',{}).get('methods'),
            'stream_tool_session_id':2125 if stream['status']=='running' else None,
            'installed_receipt':str(ROOT/'docs/validation/evidence/float-stream-20261022-lab/installed-r1/verification.json'),
            'installed_status':installed['status'],'installed_methods':installed.get('isolated_methods',{}).get('methods'),
            'installed_seconds':installed.get('isolated_methods',{}).get('suite_seconds'),
            'installed_resources':len(installed.get('resource_hashes',{})),'installed_origins':len(installed.get('isolated_methods',{}).get('origins',{})),
            'media_receipt':str(ROOT/'docs/validation/evidence/float-stream-20261022-lab/media-r4/verification.json'),
            'media_author_frames_each':20,'media_PCM_sample_frames_each':96000,'media_native_launches':20,
            'media_native_script_calls':16,'media_encoder_processes':2,'media_assets':20,'media_checks':19,
            'media_isolated_reexecution_passed':True,'media_isolated_origins':164,
            'readme_preview':str(current/'readme-preview-r3/README.md'),'readme_preview_documents':9,'readme_preview_verified_links':2815,
            'publication_preflight':str(current/'source-preflight-r1/run.json'),'publication_preflight_passed':True,
            'preserved_failures':['audio-r1.json','stream-r1.json','encoder-failure-probe-r1.json','media-r1/verification.json',
                'media-r2-count-audit.json','media-r3/verification.json','readme-preview-r1-failure.json'],
            'whole_movie_buffered':False,'delivery_boundary':'explicit nearest-even GBR(A) 16-bit FFV1; no HDR acceptance'}
        if full is not None:stream_state.update(full_suite_owner=str(current/'complete-r1/run.json'),full_suite_owner_pid=full['pid'],
            full_suite_status=full['status'],full_suite_started=full['suite_launched'],expected_full_methods=2299,full_suite_tool_session_id=handles.get('complete'))
        if chain is not None:stream_state.update(release_chain_record=str(current/'release-chain-r1/run.json'),release_chain_pid=chain['pid'],
            release_chain_status=chain['status'],release_chain_tool_session_id=handles.get('release'),publication_prepared=True)
        if not progress.get('float_stream_lab',{}).get('published'):progress['float_stream_lab']=stream_state
        progress.update(updated_at_utc=datetime.now(timezone.utc).isoformat(),goal_status='active',
            classification='PROGRESS: V92 actual2234 published; V93 full2280 running with auto release; real bounded stream/audio19 and fresh182 passed, full2299 gated behind V93; complete CapCut parity remains open.',
            previous_progress_snapshot=str(backup))
        progress['next_steps']=[
            'V92 actual2234/7549.898s/0skip and installed117 published as177765f; do not rerun terminal53704/51155.',
            'Inspect R93 full session57563 and release46591; old6425 stopped before suite launch with evidence. Ordinary publication is already dispatched after actual full2280.',
            'Inspect R94 owned full2299 and release states/handles; source292, actual19/fresh182/media and numbered README preview passed. Full is serialized behind actual R93 publication; retain failures and do not mutate frozen inputs or startup scripts.',
            'Connect verified streaming to normal CLI render/audio/preview/cache/queue and all author operations; finish remaining local AI, color/HDR, performance and natural-media quality until documented complete parity is actually proved.']
        if target.read_bytes()!=old:continue
        if not backup.exists():backup.write_bytes(old)
        temp=target.with_name('.progress-float-stream-'+stamp+'.tmp');temp.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        if target.read_bytes()!=old:temp.unlink();continue
        temp.replace(target);print(json.dumps({'status':'merged-actual-private-checkpoint','main':progress['main']['version'],
            'audio':audio['status'],'stream':stream['status'],'goal':'active'},ensure_ascii=False));return
    raise RuntimeError('private progress changed during all CAS attempts')

if __name__=='__main__':main()
