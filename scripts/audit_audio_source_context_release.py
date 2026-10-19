"""Bind terminal V64 product/media/install/Skill receipts and preserved failures."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import zipfile
from run_frozen_regression import frozen
from sync_audio_source_context_documents import ROOT,BASE,MEDIA,AUDIT,INSTALL,OFFLINE,REPORT,CONTRACT,V63,DOCS

def read(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
def digest(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)

def run(output):
    need(not output.exists(),'choose fresh release receipt');before=frozen();rows={}
    def bind(p):
        p=p.resolve();need(p.is_file(),'missing '+str(p));rows[p.relative_to(ROOT).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
    def same(v):return v.get('frozen_equal') and v.get('frozen_before')==v.get('frozen_after')==before
    def logs(folder,calls):
        for c in calls:
            a,b=folder/c['stdout'],folder/c['stderr']
            need(sha(a)==c['stdout_sha256'] and sha(b)==c['stderr_sha256'],'command bytes changed')
            need(c['exit_code']==c.get('expected_exit_code',0),'unexpected native exit')
            raw=gzip.decompress(a.read_bytes()) if c.get('raw_compressed',c.get('compressed',a.suffix=='.gz')) else a.read_bytes()
            if 'decoded_stdout_sha256' in c:need(digest(raw)==c['decoded_stdout_sha256'],'decoded stdout changed')
            if 'decoded_stdout_bytes' in c:need(len(raw)==c['decoded_stdout_bytes'],'decoded stdout length changed')
            bind(a);bind(b)
    full=read(BASE/'full-r1.json');unit=read(BASE/'unit-r1.json')
    for p,v,count in ((BASE/'full-r1.json',full,1410),(BASE/'unit-r1.json',unit,9)):
        need(same(v) and v['terminal_ok'] and v['exit_code']==0 and v['skipped']==0 and v['methods']==count,'terminal frozen suite missing')
        need(sha(p.with_suffix('.log'))==v['log_sha256'],'suite log changed');bind(p);bind(p.with_suffix('.log'))
    need(len(before)==196,'wrong frozen product scope')
    for folder,installed in ((MEDIA,False),(OFFLINE/'media',True)):
        v=read(folder/'verification.json')
        need(same(v) and v['status']=='passed_real_cli_invariants_quality_failures_retained' and len(v['records'])==8,'actual media scope missing')
        need(sha(folder/'executed-generator.py')==v['generator_sha256'],'executed media script changed')
        need(sum(c['kind']=='cli' for c in v['calls'])==144 and sum(c['kind']=='baseline-cli' for c in v['calls'])==9,'CLI scope changed')
        need(sum(i['frames'] for r in v['records'] for k,i in r['variants'].items() if k!='baseline')==408,'media frame scope changed')
        need(sum(i['stereo_sample_frames'] for r in v['records'] for k,i in r['variants'].items() if k!='baseline')==816000,'media PCM scope changed')
        need(v['baseline_ref']=='c4fa46096021ee2fb25548c31fbdf9bef1821ef5','actual old baseline missing')
        logs(folder,v['calls']);bind(folder/'verification.json');bind(folder/'provenance.json');bind(folder/'executed-generator.py')
        for r in v['records']:
            for label,i in r['variants'].items():
                need(i['audio_stretch']['execution']['status']=='succeeded','native execution missing')
                need(i['audio_stretch']['execution']['stereo_phase_accepted'] is False,'phase scope misrepresented')
                for artifact in i['audio_stretch']['engine']['artifacts']:
                    need(sha(Path(artifact['path']))==artifact['sha256'],'registered R3 artifact changed')
                bind(folder/i['media']);bind((folder/i['media']).with_suffix('.mkv.manifest.json'))
    independent=read(AUDIT/'verification.json');need(same(independent) and independent['status']=='passed_independent_source_context_media_negative_quality_retained','fresh native source reference missing')
    need(independent['fresh_r3_calls_separate']==8 and independent['package_isolated_cli_calls_separate']==5,'independent/package scope changed')
    need(independent['package_frames_separate']==36 and independent['package_stereo_sample_frames_separate']==72000,'package scope changed')
    need(all(c['fresh_crop_pcm_max_error']==0 and c['fresh_source_handles_equal_original'] for c in independent['checks']),'fresh native crop failed')
    byid={c['id']:c for c in independent['checks']}
    need(not byid['C02']['pitch_passed'] and not byid['C06']['antiphase_exact_cancellation_passed'] and byid['C07']['antiphase_exact_cancellation_passed'],'negative gates concealed')
    need(byid['C05']['context_time_map_anchors']==110 and byid['C05']['output_crop']==[3775,75775],'nested curve reference changed')
    logs(AUDIT,independent['calls'])
    for name,item in independent['files'].items():
        p=ROOT/name;need(sha(p)==item['sha256'] and p.stat().st_size==item['bytes'],'independently decoded media changed');bind(p)
    bind(AUDIT/'verification.json');bind(AUDIT/'executed-audit.py')
    install=read(INSTALL/'verification.json')
    need(same(install) and install['status']=='passed_isolated_install_and_decoded_audio_context' and install['installed_package_files']==131,'actual installation missing')
    need(install['package_bytes_equal_to_wheel_and_source'] and install['isolated_control_cli_calls']==2 and install['isolated_media_cli_calls']==144,'isolated install scope changed')
    need(len(install['comparisons'])==16 and all(c['rgb_equal'] and c['pcm_equal'] for c in install['comparisons']),'source/installed media differ')
    for c in install['calls']:
        need(c['exit_code']==0 and sha(INSTALL/(c['name']+'.stdout.log'))==c['stdout_sha256'] and sha(INSTALL/(c['name']+'.stderr.log'))==c['stderr_sha256'],'install command changed')
    need(sha(OFFLINE/'agent-video-kit-cp313-win_amd64.zip')==install['release_zip_sha256'] and sha(OFFLINE/'release-manifest.json')==install['manifest_sha256'],'offline release bytes changed')
    manifest=read(ROOT/'video-cut-install-manifest.json');skills=read(BASE/'skills-r1.json')
    need(manifest['skill_count']==skills['skill_count']==17 and skills['local_links_checked']==232,'Skill registration scope changed')
    need(manifest['current_audit']['record_sha256']==sha(BASE/'skills-r1.json'),'Skill audit manifest stale')
    for item in skills['results']:
        p=ROOT/'skills'/item['skill']/'SKILL.md';entry=next(x for x in manifest['skills'] if x['name']==item['skill'])
        need(item['validator_exit_code']==0 and sha(p)==item['sha256']=='sha256:'+entry['skill_md_sha256'],'Skill bytes differ')
        need((Path('C:/Users/carzy/.codex/skills')/item['skill']).resolve()==p.parent.resolve(),'Skill directory junction differs');bind(p)
    preview=read(MEDIA/'preview/verification.json');review=read(MEDIA/'preview/static-review.json')
    need(preview['gif']['frames']==3 and preview['gif']['duration_ms']==6000 and preview['gif']['audio'] is False,'statistics GIF scope changed')
    need(review['reviewed_samples']==3 and not review['continuous_playback'] and not review['audio_listened'],'static-only review scope changed')
    for name,item in preview['files'].items():need(sha(MEDIA/'preview'/name)==item['sha256'],'preview bytes changed')
    logs(MEDIA/'preview',preview['calls'])
    development=read(BASE/'development/verification.json');need(development['native_calls_separate']==28,'research probe scope changed')
    for item in development['inventory']:
        if not item['public_copy']:continue
        p=ROOT/item['public_copy'];raw=gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()
        need(digest(raw)==item['sha256'] and len(raw)==item['bytes'],'negative probe selected bytes changed')
    candidate=BASE/'development/isolated-candidate';r2=read(candidate/'candidate-unit-r2.json')
    need(not read(candidate/'candidate-unit-r1.json')['terminal_ok'] and not r2['terminal_ok'] and read(candidate/'candidate-unit-r3.json')['terminal_ok'],'isolated failures missing')
    with zipfile.ZipFile(candidate/'candidate-unit-r2-sources.zip') as archive:
        need(set(archive.namelist())==set(r2['frozen_before']),'candidate snapshot inventory changed')
        for name,d in r2['frozen_before'].items():need(digest(archive.read(name))==d,'candidate snapshot differs')
    need(read(ROOT/'docs/assets/audio-source-context-20261019-v64-r1/failure.json')['status']=='failed','original output path failure missing')
    v63root=ROOT/'docs/validation/evidence/vace-delivery-20261019-v63-r1';v63=read(v63root/'admission-and-cleanup.json');old=read(v63root/'verification.json')
    need(v63['gpu_admission_failure']['physical_free_bytes']==3898605568 and v63['gpu_admission_failure']['required_free_bytes']==8321499136,'actual GPU rejection changed')
    need(v63['model_forwards']==0 and not v63['repaired_video'] and v63['timeline_clips']==v63['registered_output_files']==0,'rejected VACE delivery overstated')
    source_check=read(v63root/'source-check-after-failure.json')
    need(old['status']=='failed' and len(old['frozen_before'])==195 and source_check['before_equals_after']
         and old['frozen_before']==source_check['frozen_after'] and not source_check['new_full_regression_run'],
         'V63 original frozen failure changed')
    links=0
    for name in [*DOCS,'docs/validation/'+REPORT,'docs/specs/'+CONTRACT,'docs/validation/'+V63]:
        p=ROOT/name;body=p.read_text(encoding='utf-8')
        if name in DOCS:need('<!-- V64-CURRENT -->' in body and '<!-- V63-REJECTION -->' in body and '完整剪映等价' in body,'current doc scope missing')
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',body):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target):continue
            need((p.parent/urllib.parse.unquote(target)).resolve().exists(),'broken doc link '+name+' '+target);links+=1
        bind(p)
    body=(ROOT/'README.md').read_text(encoding='utf-8')
    need('| V63 |' in body and '| V64 |' in body and f'docs/assets/{MEDIA.name}/preview/comparison.gif' in body,'README numbered proof/demo absent')
    # A post-run snapshot; never stop unrelated browser sessions or workers.
    query="$audioOwnedJobs=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','ffmpeg.exe') -and $_.CommandLine -match 'run_frozen_regression.py|audio-context-native-install-20261019-v64-r1|audio-source-context-media-20261019-v64-r2|audio-context-independent-20261019-v64-r1' } | Select-Object ProcessId,Name,CommandLine); $audioOwnedBrowsers=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'chrome|chromium|msedge' -and $_.CommandLine -match 'html-motion|html-quality|ai-ad-editor|AI广告剪辑|regression-' } | Select-Object ProcessId,Name,CommandLine); [ordered]@{workers=$audioOwnedJobs;browsers=$audioOwnedBrowsers} | ConvertTo-Json -Depth 4 -Compress"
    p=subprocess.run(['powershell','-NoProfile','-Command',query],capture_output=True,check=True,timeout=30)
    snap=json.loads(p.stdout.decode('utf-8-sig'));need(not snap['workers'] and not snap['browsers'],'matching process still active; inspect ownership before cleanup')
    process_path=output.with_name(output.stem+'-processes.json')
    process_path.write_text(json.dumps({'checked_at_utc':datetime.now(timezone.utc).isoformat(),'query':query,'result':snap,
        'continuous_process_monitor':False,'interactive_browser_started':False,'unrelated_processes_stopped':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    bind(process_path)
    for folder in (BASE,MEDIA,AUDIT,INSTALL,OFFLINE,v63root):
        for p in folder.rglob('*'):
            if p.is_file() and p!=output:bind(p)
    bind(ROOT/'video-cut-install-manifest.json')
    for name in ('probe_audio_source_context.py','smoke_audio_source_context.py','verify_audio_source_context_install.py',
                 'audit_audio_source_context_media.py','build_audio_context_preview.py','collect_audio_context_development.py',
                 'collect_vace_retry_rejection.py','sync_audio_source_context_documents.py'):bind(ROOT/'scripts'/name)
    after=frozen();need(after==before,'product changed during release audit')
    result={'status':'passed_v64_audio_context_release','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'full_methods':1410,'targeted_methods_subset':9,'current_cli_calls':144,'current_frames':408,'current_stereo_sample_frames':816000,
        'isolated_install_control_and_media_cli':146,'isolated_package_cli_separate':5,'installed_frames':408,'package_frames_separate':36,
        'baseline_cli_per_source_and_install_run_separate':9,'research_native_probes_separate':28,'independent_fresh_r3_calls_separate':8,
        'skills':17,'skill_links':232,'doc_links_checked':links,'files':rows,'frozen_before':before,'frozen_after':after,'frozen_equal':True,
        'v63_real_resource_rejected_no_forward_or_delivery':True,'negative_pitch_and_phase_failures_retained':True,
        'natural_quality_accepted':False,'continuous_playback':False,'audio_listened':False,'full_capcut_parity':False,
        'generator_sha256':sha(Path(__file__))}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('status','full_methods','doc_links_checked','skills')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
