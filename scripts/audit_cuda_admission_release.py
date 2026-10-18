"""Audit V60 native/rejection evidence; keep full model delivery explicitly pending."""
import argparse
import ast
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import zipfile
from run_frozen_regression import frozen
from sync_cuda_admission_documents import DOCS,REPORT,CONTRACT,BASE,INSTALL,FIRST,ASSETS,PACKAGE

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.cuda_admission import HEADROOM_BYTES,POLICY,_validate_idle_cache,validate_check
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def sha(path):return digest(path.read_bytes())
def read(path):return json.loads(path.read_bytes())
def require(condition,message):
    if not condition:raise ValueError(message)
def calls(value,folder,prefix=''):
    for row in value['calls']:
        require(row['stdout_sha256']==sha(folder/(prefix+row['name']+'.stdout.log')),'stdout changed')
        require(row['stderr_sha256']==sha(folder/(prefix+row['name']+'.stderr.log')),'stderr changed')

def audit(output,skills,preflight=False):
    import numpy as np
    from PIL import Image
    require(not output.exists(),'fresh audit output required')
    before=frozen();base=ROOT/BASE;first=ROOT/FIRST;install_root=ROOT/INSTALL
    require(len(before)==188,'unexpected frozen input inventory')
    for name,count in [('full-r2',1374),('unit-r2',16),('vace-r2',33)]:
        value=read(base/(name+'.json'))
        if preflight and name=='full-r2' and not value.get('terminal_ok'):
            require(value['frozen_before']==before,'running full regression input changed')
            continue
        require(value['terminal_ok'] and not value['exit_code'] and not value['skipped'] and value['methods']==count
                and value['frozen_before']==before==value['frozen_after'] and value['frozen_equal']
                and value['log_sha256']==sha(base/(name+'.log')),'current regression incomplete: '+name)
    # The old source bytes stay reproducible even though the first model failed.
    snapshot=read(base/'r1-source-snapshot.json');old=read(base/'full-r1.json')
    require(old['terminal_ok'] and old['methods']==1370 and not old['exit_code'] and not old['skipped']
            and old['frozen_before']==old['frozen_after']==snapshot['frozen_inputs'] and old['frozen_equal']
            and old['log_sha256']==sha(base/'full-r1.log'),'first completed regression missing')
    require(snapshot['archive_sha256']==sha(base/'r1-frozen-inputs.zip') and snapshot['files']==188
            and snapshot['generator_sha256']==sha(ROOT/'scripts/snapshot_cuda_admission_failure.py'),'first source archive receipt changed')
    with zipfile.ZipFile(base/'r1-frozen-inputs.zip') as archive:
        require(set(archive.namelist())==set(snapshot['frozen_inputs']),'first source archive inventory mismatch')
        for name,wanted in snapshot['frozen_inputs'].items():require(digest(archive.read(name))==wanted,'first source archive byte mismatch')
        for proof,folder,allocation in [(read(base/'native-r1.json'),base,128*1024**2),
                (read(ROOT/'docs/validation/evidence/cuda-admission-install-20261019-v60/native-installed.json'),ROOT/'docs/validation/evidence/cuda-admission-install-20261019-v60',0)]:
            require(proof['status']=='passed_native_cuda_sampling_allocation_and_loader_rejection'
                    and proof['actual_allocation_bytes']==allocation and proof['allocation_released'],'historical native proof incomplete')
            for name,wanted in proof['implementation_sha256'].items():
                require(digest(archive.read('product/src/ai_ad_editor/'+name))==wanted,'historical native source mismatch')
            executed=folder/('native-r1.executed.py' if folder==base else 'native-installed.executed.py')
            require(proof['generator_sha256']==sha(executed),'historical native executed source changed')
    failure=read(first/'verification.json');worker=read(first/'r1-worker-response.json')
    require(failure['status']=='failed' and snapshot['actual_failure_receipt_sha256']==sha(first/'verification.json')
            and snapshot['worker_response_sha256']==sha(first/'r1-worker-response.json')
            and snapshot['actual_stderr_sha256']==sha(first/'actual-vace.stderr.log'),'first real failure changed')
    calls(failure,first)
    require([row['exit_code'] for row in failure['calls']]==[0,1],'first attempt must remain a failed delivery')
    raw=(first/'actual-vace.stderr.log').read_text(encoding='utf-8')
    envelope=json.JSONDecoder().raw_decode(raw.split('RuntimeError: ',1)[1])[0]
    require(json.JSONDecoder().raw_decode(envelope['errors'][0]['cause'])[0]==worker,'archived actual worker response differs')
    rejection=worker['gpu_admission_failure']
    require(rejection==snapshot['rejection'] and rejection['stage']=='video-window-1'
            and rejection['error_code']=='CUDA_ADMISSION_INSUFFICIENT_TORCH_FREE'
            and rejection['torch_free_bytes']<HEADROOM_BYTES<=rejection['physical_free_bytes']
            and snapshot['video_denoising_windows_started']==0,'first failure scope changed')
    state=read(base/'failure-project-state.json');archived=ROOT/state['archived_project']
    project=read(archived)
    require(state['status']=='observed_failed_project_inputs_only_no_repaired_publication'
            and state['project_sha256']==sha(archived) and state['worker_response_sha256']==sha(first/'r1-worker-response.json')
            and state['generator_sha256']==sha(ROOT/'scripts/check_cuda_admission_failure_project.py')
            and not state['project_modified'] and not state['model_executed']
            and not state['repaired_output_registered'] and state['managed_asset_files']==2
            and state['timeline_clips']==state['project_outputs']==0,'failed project observation missing')
    require(len(project['assets'])==2 and {row['sha256'] for row in project['assets']}=={worker['source_sha256'],worker['mask_sha256']}
            and not project['outputs'] and not any(track['clips'] for seq in project['sequences'] for track in seq['tracks'])
            and [row['command'] for row in project['provenance']['change_log']]==state['completed_commands']
                ==['media.ingest','media.ingest','media.adapter.register'],'failed project published a repair or timeline change')
    for row in state['managed_assets']:
        source_name='source.mov' if row['sha256']==worker['source_sha256'] else 'mask.mov'
        public_source=ROOT/'docs/assets'/ASSETS/source_name
        require(sha(public_source)==row['sha256'] and public_source.stat().st_size==row['bytes']
                and any(asset['id']==row['asset_id'] and asset['uri']==row['uri'] and asset['sha256']==row['sha256'] for asset in project['assets']),
                'failed project managed input evidence differs')
    native=read(base/'native-r2.json');check=native['admission_failure']
    require(native['status']=='failed' and native['stage']=='sampling-before-small-allocation'
            and not native['model_forward_calls'] and not native['model_weights_loaded']
            and 'actual_allocation_bytes' not in native and not native['blocked_network_events']
            and native['generator_sha256']==sha(ROOT/'scripts/probe_vace_cuda_admission.py')
            and native['generator_sha256']==sha(base/'native-r2.executed.py'),'current physical rejection evidence missing')
    for name,wanted in native['implementation_sha256'].items():require(sha(ROOT/'product/src/ai_ad_editor'/name)==wanted,'native current source mismatch')
    _validate_idle_cache(check['idle_cache_release'])
    require(check['policy']==POLICY and check['device_uuid']==rejection['device_uuid']
            and check['error_code']=='CUDA_ADMISSION_INSUFFICIENT_PHYSICAL_FREE'
            and check['physical_free_bytes']<check['required_free_bytes']==HEADROOM_BYTES+128*1024**2<=check['torch_free_bytes']
            and check['effective_free_bytes']==min(check['physical_free_bytes'],check['torch_free_bytes'])
            and check['idle_cache_release']['allocated_before_bytes']==check['idle_cache_release']['allocated_after_bytes']==0,
            'native rejection counters/scope mismatch')
    resources=read(base/'resources-r1.json')
    require(resources['status']=='observed_shared_gpu_resources_no_mutation' and not resources['processes_modified']
            and not resources['torch_imported'] and not resources['cuda_context_created'] and not resources['allocations_performed']
            and not resources['per_process_gpu_bytes_attributed'] and resources['external_process_titles_paths_and_command_lines_redacted']
            and not any(row['matches_first_run_workdir'] for row in resources['original_run_pid_observations'])
            and resources['generator_sha256']==sha(ROOT/'scripts/record_cuda_admission_resources.py'),'resource observation/cleanup evidence incomplete')
    later=read(base/'resources-r3.json')
    require(later['status']=='observed_shared_gpu_resources_no_mutation' and not later['processes_modified']
            and not later['torch_imported'] and not later['cuda_context_created'] and not later['allocations_performed']
            and later['external_process_titles_paths_and_command_lines_redacted']
            and not later['per_process_gpu_bytes_attributed'] and later['generator_sha256']==resources['generator_sha256']
            and HEADROOM_BYTES+128*1024**2<later['physical_free_bytes']<7936*1024**2,
            'later small-probe resource observation missing')
    for current,folder,allocation in [(read(base/'native-r3.json'),base,128*1024**2),
            (read(install_root/'native-installed.json'),install_root,0)]:
        require(current['status']=='passed_native_cuda_sampling_allocation_and_loader_rejection'
                and current['actual_allocation_bytes']==allocation and current['allocation_released']
                and not current['model_forward_calls'] and not current['model_weights_loaded']
                and not current['blocked_network_events'] and not current['other_user_processes_modified']
                and current['components_before']==current['components_after']=={'diffusers':False,'accelerate':False,'transformers':False}
                and current['loader_phases']==['admitting-text-gpu-memory'],
                'current native allocation/early-loader refusal scope mismatch')
        executed=folder/('native-r3.executed.py' if folder==base else 'native-installed.executed.py')
        require(current['generator_sha256']==sha(executed)==sha(ROOT/'scripts/probe_vace_cuda_admission.py'),
                'current native executed recipe changed')
        for name,wanted in current['implementation_sha256'].items():
            require(sha(ROOT/'product/src/ai_ad_editor'/name)==wanted,'current native implementation mismatch')
        for name,stage,required in [('before_allocation','native-before-allocation',HEADROOM_BYTES+allocation),
                ('after_allocation','native-after-allocation',HEADROOM_BYTES),('after_release','native-after-release',HEADROOM_BYTES)]:
            validate_check(current[name],stage=stage,required=required,device_uuid=rejection['device_uuid'])
        live=current['after_allocation']['idle_cache_release'];released=current['after_release']['idle_cache_release']
        require(live['allocated_before_bytes']==live['allocated_after_bytes']==allocation
                and released['allocated_before_bytes']==released['allocated_after_bytes']==0
                and released['reserved_before_bytes']==allocation and released['reserved_after_bytes']==0
                and released['released_reserved_bytes']==allocation,'native current-worker active/cache byte proof missing')
        expected=current['expected_budget_rejection']
        require(expected['stage']=='text-weights' and expected['error_code']=='CUDA_ADMISSION_INSUFFICIENT_PHYSICAL_FREE'
                and expected['required_free_bytes']==(65536+768)*1024**2
                and expected['physical_free_bytes']<expected['required_free_bytes'],'native impossible budget admission was not refused')
        _validate_idle_cache(expected['idle_cache_release'])
    cpu_root=ROOT/'docs/validation/evidence/cuda-admission-install-20261019-v60-r2-cpu'
    cpu=read(cpu_root/'verification.json')
    require(cpu['status']=='passed_native_install_and_cli_cuda_pending' and cpu['cpu_only']
            and not cpu['cuda_probe_executed'] and cpu['installed_cuda_probe_sha256'] is None
            and cpu['frozen_before']==before==cpu['frozen_after'] and cpu['installed_package_files']==125,
            'earlier CPU-only receipt must retain its original pending scope')
    calls(cpu,cpu_root)
    install=read(install_root/'verification.json');public=ROOT/'docs/assets'/PACKAGE
    require(install['status']=='passed_native_install_and_cuda_admission' and not install['cpu_only']
            and install['cuda_probe_executed'] and install['installed_cuda_probe_sha256']==sha(install_root/'native-installed.json')
            and install['frozen_before']==before==install['frozen_after'] and install['installed_package_files']==125
            and install['isolated_cli_calls']==2 and install['package_bytes_equal_to_wheel_and_source']
            and install['generator_sha256']==sha(ROOT/'scripts/verify_cuda_admission_native_install.py')
            and install['generator_sha256']==sha(install_root/'executed-installer-check.py'),'current native installation scope mismatch')
    calls(install,install_root)
    require([row['name'] for row in install['calls']]==['install','capabilities','schema','native-installed']
            and not any(row['exit_code'] for row in install['calls']),'installation command results missing')
    for row in install['calls'][1:3]:require({'-I','-S'}.issubset(row['command']),'isolated CLI flags missing')
    require(install['capabilities_cuda_admission']['idle_cache_release']=='current_worker_before_each_admission'
            and install['capabilities_cuda_admission']['text_offload_hooks_removed_before_video'] is True,'installed capabilities stale')
    require(sha(public/'agent-video-kit-cp313-win_amd64.zip')==install['release_zip_sha256']
            and sha(public/'release-manifest.json')==install['manifest_sha256'],'public release archive changed')
    with zipfile.ZipFile(public/'agent-video-kit-cp313-win_amd64.zip') as archive:
        manifest=json.loads(archive.read('manifest.json'))
        require(digest(archive.read('manifest.json'))==install['manifest_sha256'] and len(manifest['wheels'])==7,'release manifest mismatch')
        for row in manifest['files']:
            raw=archive.read(row['path']);require(len(raw)==row['bytes'] and digest(raw)==row['sha256'],'release file mismatch')
        wheel=next(row for row in manifest['wheels'] if row['name']=='ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(archive.read(wheel['path']))) as package:
            names={name for name in package.namelist() if name.startswith('ai_ad_editor/') and not name.endswith('/')}
            require(names==set(install['installed_files']) and len(names)==125,'installed package inventory mismatch')
            for name in names:
                raw=package.read(name);require(raw==(ROOT/'product/src'/name).read_bytes() and digest(raw)==install['installed_files'][name],'installed/wheel/current byte mismatch')
    publication=read(base/'source-publication.json');source=ROOT/'docs/assets'/ASSETS
    require(publication['source_only'] and not publication['new_repaired_output'] and publication['model_forward_calls']==0
            and publication['frames']==8 and publication['new_source_scenes']==0
            and publication['generator_sha256']==sha(ROOT/'scripts/publish_cuda_admission_source.py'),'source-only media scope mismatch')
    for row in publication['files']:
        path=ROOT/row['path'];require(path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],'source-only public bytes changed')
    calls(publication,base,'source-')
    require(sha(source/'source.mov')==worker['source_sha256'] and sha(source/'mask.mov')==worker['mask_sha256'],'original fixture differs from actual attempt')
    def command(args):return subprocess.run(args,capture_output=True,check=True,timeout=120).stdout
    def decode(name):return np.frombuffer(command(['ffmpeg','-nostdin','-v','error','-i',str(source/name),'-an','-fps_mode','passthrough','-pix_fmt','rgba','-f','rawvideo','pipe:1']),np.uint8).reshape(8,128,192,4)
    original=decode('source.mov');mask=decode('mask.mov');truth=np.load(source/'ground-truth.npz',allow_pickle=False)['frames']
    require(truth.shape==original.shape and 128 in original[...,3] and not np.any(mask[0,...,3]) and np.any(mask[1:,...,3]),'source fixture geometry/alpha/mask differs')
    pts=json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=pts_time','-of','json',str(source/'source.mov')]))
    require([Fraction(row['pts_time']) for row in pts['frames']]==[Fraction(i,8) for i in range(8)],'original PTS differs')
    pcm=command(['ffmpeg','-nostdin','-v','error','-i',str(source/'source.mov'),'-map','0:a:0','-vn','-ar','48000','-ac','1','-f','s16le','pipe:1'])
    require(len(pcm)==96000,'original fixture audio differs')
    with Image.open(source/'input-only.gif') as gif:
        require(gif.n_frames==8 and gif.size==(576,176),'input-only GIF geometry differs')
        durations=[]
        for index in range(8):gif.seek(index);durations.append(gif.info['duration'])
        require(durations==[120,130]*4,'input GIF clock differs')
    review=read(base/'source-contact-review.json')
    require(review['status']=='reviewed_original_input_contact_only' and review['contact_sha256']==sha(source/'input-contact.png')
            and review['reviewed_frame_indices']==[0,4,7] and review['source_only'] and not review['new_repaired_output_reviewed']
            and not review['continuous_playback_reviewed'] and not review['audio_listening_reviewed'] and not review['broad_quality_accepted'],'static original-input review scope mismatch')
    if preflight:
        require(frozen()==before,'product changed during evidence preflight')
        result={'status':'passed_v60_evidence_preflight_not_release','frozen_inputs':188,'package_files':125,
            'isolated_cli_calls':2,'source_only_frames':8,'native_rejection_verified':True,
            'native_active_allocation_verified_current':True,'installed_cuda_verified_current':True,
            'full_regression_verified':False,'trained_model_delivery_verified':False,
            'generator_sha256':sha(Path(__file__))}
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(result));return
    skill=read(skills);mapping=read(ROOT/'video-cut-install-manifest.json')
    require(skill['skill_count']==14 and mapping['current_audit']['record_sha256']==sha(skills),'current Skill audit missing')
    for row in skill['results']:
        path=ROOT/'skills'/row['skill']/'SKILL.md'
        require(not row['validator_exit_code'] and row['installed_directory_resolves_to_repo'] and sha(path)==row['sha256'],'current Skill bytes/registration mismatch')
        require(next(item for item in mapping['skills'] if item['name']==row['skill'])['skill_md_sha256']==row['sha256'][7:],'Skill manifest stale')
    workflow=read(ROOT/'docs/validation/evidence/openfilm-workflow-map-20261019-r05/verification.json')
    require(workflow['status']=='passed_source_and_cli_declaration_mapping_only' and workflow['route_count']==22
            and len(workflow['workflow_sources'])==3 and workflow['frozen_before']==before==workflow['frozen_after']
            and workflow['frozen_equal'] and not workflow['editing_commands_executed'] and not workflow['models_executed']
            and not workflow['new_skills_installed'] and not workflow['new_repaired_or_edited_outputs']
            and not workflow['end_to_end_workflow_accepted']
            and workflow['generator_sha256']==sha(ROOT/'scripts/audit_openfilm_workflow_routes.py'),'OpenFilm workflow declaration scope changed')
    upstream=ROOT/'sources/upstream/openfilm-refresh-20261019-r05/repo.zip'
    require(sha(upstream)==workflow['upstream_archive_sha256'],'fixed OpenFilm archive changed')
    with zipfile.ZipFile(upstream) as archive:
        prefix='openfilm-openfilm-7a64d1f/'
        require(digest(archive.read(prefix+'LICENSE'))==workflow['upstream_license_sha256'],'OpenFilm license changed')
        for row in workflow['workflow_sources']:
            raw=archive.read(prefix+row['upstream_path'])
            require(digest(raw)==row['sha256'] and len(raw)==row['bytes'],'OpenFilm workflow source changed')
    docs=[*DOCS,'docs/validation/'+REPORT,'docs/specs/'+CONTRACT,'docs/OpenFilm创作流程本地适配设计_2026-10-19.md'];links=0
    for name in docs:
        path=ROOT/name;text=path.read_text(encoding='utf-8')
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            require((path.parent/urllib.parse.unquote(target)).resolve().exists(),'missing local doc link: '+name+' '+raw);links+=1
        if name in DOCS:
            block=text.split('<!-- V60-CURRENT -->',1)[1].split('<!-- /V60-CURRENT -->',1)[0]
            require(all(token in block for token in ('1374/1374','188 文件冻结','不预约显存','GPU 完整交付待验','无新修复成片')),'current documentation scope stale')
    readme=(ROOT/'README.md').read_text(encoding='utf-8')
    require([int(x) for x in re.findall(r'^\| V(\d{2}) \|',readme,re.M)]==list(range(1,61)) and '<!-- V60-DEMO -->' in readme,'README numbered verification/demo missing')
    sources=sorted([*(ROOT/'scripts').glob('*cuda_admission*.py'),ROOT/'scripts/audit_openfilm_workflow_routes.py'])
    for path in sources:ast.parse(path.read_text(encoding='utf-8'))
    require(frozen()==before,'product changed during final admission-scope audit')
    result={'status':'passed_v60_admission_release_audit_trained_model_delivery_pending','full_methods':1374,'frozen_inputs':188,
        'cuda_unit_methods':16,'vace_methods':33,'unit_and_vace_are_full_suite_subsets':True,
        'installed_package_files':125,'isolated_cli_calls':2,'native_active_allocation_verified_current':True,
        'installed_cuda_verified_current':True,'trained_model_delivery_verified_current':False,
        'successful_video_denoising_windows':0,'new_repaired_outputs':0,'source_only_frames':8,'source_pcm_bytes':len(pcm),
        'source_static_review_frames':[0,4,7],'reservation':False,'oom_guarantee':False,
        'natural_quality_accepted':False,'full_capcut_parity':False,'skill_count':14,
        'skill_local_links_checked':skill['local_links_checked'],'document_local_links_checked':links,
        'documents':{name:sha(ROOT/name) for name in docs},'verification_sources':{path.relative_to(ROOT).as_posix():sha(path) for path in sources},
        'full_regression_sha256':sha(base/'full-r2.json'),'current_native_rejection_sha256':sha(base/'native-r2.json'),
        'current_native_pass_sha256':sha(base/'native-r3.json'),'installed_native_pass_sha256':sha(install_root/'native-installed.json'),
        'earlier_cpu_install_receipt_sha256':sha(cpu_root/'verification.json'),
        'first_source_snapshot_sha256':sha(base/'r1-source-snapshot.json'),'native_install_receipt_sha256':sha(install_root/'verification.json'),
        'failed_project_observation_sha256':sha(base/'failure-project-state.json'),
        'skills_receipt_sha256':sha(skills),'install_manifest_sha256':sha(ROOT/'video-cut-install-manifest.json'),
        'openfilm_workflow_scope':'source_and_22_cli_declarations_only_no_new_skill_or_edited_output',
        'openfilm_workflow_receipt_sha256':sha(ROOT/'docs/validation/evidence/openfilm-workflow-map-20261019-r05/verification.json'),
        'generator_sha256':sha(Path(__file__))}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({key:result[key] for key in ('status','full_methods','document_local_links_checked')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--skills',type=Path)
    parser.add_argument('--preflight',action='store_true',help='Check completed evidence only; does not accept a release or running full regression')
    args=parser.parse_args()
    if not args.preflight and args.skills is None:parser.error('--skills is required for final audit')
    audit(args.output.resolve(),args.skills.resolve() if args.skills else None,args.preflight)
