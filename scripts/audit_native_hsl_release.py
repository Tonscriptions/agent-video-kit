"""Bind V77 native DLL, frozen inputs, offline resources, media, timing and failures."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
from PIL import Image
from run_frozen_regression import frozen
from sync_native_hsl_documents import BASE,CLI,CONTRACT,DOCUMENTS,INSTALLED,NATIVE,REPORT,ROOT

SKILLS=('video-cut-agent-editor','video-cut-timeline','video-cut-project-ops','video-cut-quality')
SCRIPTS=('build_native_hsl','probe_native_hsl_performance','probe_native_hsl_fastpath','probe_native_hsl_cli','profile_native_hsl_cli',
    'smoke_native_hsl','verify_native_hsl_install','sync_native_hsl_documents','audit_native_hsl_release',
    'publish_native_hsl','run_frozen_regression')
def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',action='store_true');args=parser.parse_args();output=args.output.resolve();assert not output.exists()
    current=frozen();assert len(current)==233
    focus=[(read(BASE/name),count) for name,count in [('native-targeted-r4.json',19),('hsl-targeted-r4.json',29),('offline-targeted-r3.json',22)]]
    dev=read(BASE/'native-r3/verification.json');install=read(BASE/'installed-r3/verification.json');media=read(BASE/'installed-r3/media/verification.json')
    performance=read(BASE/'fastpath-r5.json');cli=read(BASE/'cli-r2/verification.json')
    for value,count in focus:assert value['terminal_ok'] and value['methods']==count and value['skipped']==0
    for value in [*(x[0] for x in focus),dev,install,media,performance,cli]:
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    for value in (dev,install,media):assert value['status']=='passed' and all(row['ok'] for row in value['checks'])
    assert len(install['resource_hashes'])==153 and install['bundle']['wheels']==7
    assert install['isolated_cli_calls']==27 and install['module_origin_probes']==1 and len(install['checks'])==13
    assert dev['cli_calls']==media['cli_calls']==24 and len(dev['checks'])==len(media['checks'])==50
    assert len(dev['cases'])==len(media['cases'])==4
    keys=('name','effect','frames','fps','max_rgb_error','alpha_byte_equal','PCM_byte_equal','actual_decoded_sha256','independent_reference_sha256','kernel_metadata')
    assert [{k:x[k] for k in keys} for x in dev['cases']]==[{k:x[k] for k in keys} for x in media['cases']]
    assert dev['video_probes']==media['video_probes']
    package=ROOT/'product/src/ai_ad_editor';manifest=read(package/'native_hsl_manifest.json')
    assert manifest['format']=='avk-selective-hsl-native-v1' and manifest['platform']=='win32-amd64' and not manifest['runtime_compilation']
    assert sha(package/manifest['binary_filename'])==manifest['binary_sha256'] and sha(package/'native_hsl.c')==manifest['source_sha256']
    assert [p.name for p in package.glob('avk_hsl_*.dll')]==[manifest['binary_filename']]
    assert install['resource_hashes']['openfilm_text_bounds.mjs']==sha(package/'openfilm_text_bounds.mjs')
    assert install['resource_hashes'][manifest['binary_filename']]==manifest['binary_sha256']
    for value in (dev,media):
        assert value['new_model_inference']==0 and not value['network'] and not value['virtualization']
        for case in value['cases']:
            assert case['max_rgb_error']==1 and case['frames']==24 and case['fps']==12
            assert case['alpha_byte_equal'] and case['PCM_byte_equal'] and len(case['kernel_metadata'])==1
            kernel=case['kernel_metadata'][0]
            assert kernel['kind']=='selective-hsl' and kernel['engine']=='encoded-rgb-eight-band-hsl-v1' and kernel['backend']=='ffmpeg:frei0r'
            assert kernel['plugin_sha256']==manifest['binary_sha256'] and kernel['plugin_source_sha256']==manifest['source_sha256']
            assert kernel['program']['format']=='AVKHSL01' and 0<kernel['program']['bytes']<=32256 and kernel['program']['max_depth']<=128
            assert kernel['alpha']=='exact-input-alpha' and kernel['achromatic_policy']=='unchanged'
            assert kernel['sampled_frames']==24 and 0<kernel['kernel_bytes']<=64*1024 and not kernel['bypass']
    builds=[]
    for name in ('build-r2','build-r3','build-r5'):
        receipt=read(BASE/name/'verification.json');assert receipt['status']=='passed-build' and receipt['exit_code']==0
        assert sha(BASE/name/'executed-source.c')==receipt['source_sha256']==receipt['manifest']['source_sha256']
        binary=package/manifest['binary_filename'] if name=='build-r5' else BASE/name/receipt['manifest']['binary_filename']
        assert sha(binary)==receipt['manifest']['binary_sha256'];builds.append({'name':name,'source_sha256':receipt['source_sha256'],'binary_sha256':sha(binary)})
    assert read(BASE/'build-r5/verification.json')['manifest']==manifest
    for name in ('build-r1','build-r4'):assert read(BASE/name/'verification.json')['status']=='failed'
    assert read(BASE/'native-targeted-r1.json')['exit_code']!=0 and 'FAILED (failures=2)' in (BASE/'native-targeted-r1.log').read_text(encoding='utf8')
    assert read(BASE/'fastpath-r1.json')['status']=='failed'
    assert not read(BASE/'offline-targeted-r1-before-fix.json')['terminal_ok']
    assert read(BASE/'installed-r1/verification.json')['status']=='failed' and 'Unsupported wheel ABI' in (BASE/'installed-r1/install.stdout.log').read_text(encoding='utf8')
    assert read(BASE/'installed-r2/verification.json')['status']=='failed'
    omitted=read(BASE/'installed-r2/resource-diagnostic.json')
    assert omitted['source_resources']==153 and omitted['wheel_resources']==omitted['installed_resources']==152
    assert omitted['missing_from_wheel']==omitted['missing_from_installed']==['openfilm_text_bounds.mjs']
    assert omitted['wheel_and_installed_byte_equal'] and omitted['all_present_resources_equal_source']
    for name in ('full-r1','full-r2'):
        stopped=read(BASE/(name+'.json'));stop=read(BASE/(name+'-stop.json'))
        assert stopped['status']=='failed' and not stopped['terminal_ok'] and stopped['methods'] is None
        assert stop['owner_pid'] and stop['processes']
    assert performance['status']=='passed-execution-probe' and performance['frames_per_case']==60 and performance['repetitions']==3
    assert performance['filter_threads']==1 and len(performance['cases'])==4 and not performance['interactive_preview_accepted']
    for case in performance['cases']:
        assert len(case['samples'])==3 and all(x['frames']==60 for x in case['samples'])
        if case['name']!='control':assert case['kernel_metadata']['plugin_sha256']==manifest['binary_sha256'] and case['all_repeats_meet_30fps']
    for call in performance['calls']:
        assert call['exit_code']==0
        for row in call['logs'].values():assert sha(ROOT/row['path'])==row['sha256']
    assert cli['status']=='passed-execution-probe' and cli['frames_per_render']==60 and cli['repetitions']==3 and cli['cli_calls']==15
    assert cli['concurrent_load']=='full-r3' and len(cli['cases'])==3
    for case in cli['cases']:
        assert len(case['samples'])==3 and all(x['frames']==60 and x['every_PTS_checked'] for x in case['samples'])
        assert not case['all_repeats_meet_30fps']
        if case['name']!='control':assert case['kernel_metadata'][0]['plugin_sha256']==manifest['binary_sha256']
    profile=read(BASE/'profile-r1/verification.json')
    assert profile['status']=='passed-diagnostic' and profile['exit_code']==0 and not profile['fps_benchmark']
    assert profile['frozen_equal'] and profile['frozen_before']==profile['frozen_after']==current
    assert profile['concurrent_load']=='full-r3' and profile['kernel_metadata'][0]['plugin_sha256']==manifest['binary_sha256']
    assert sha(BASE/'profile-r1/cli.pstats')==profile['profile_sha256'] and sha(BASE/'profile-r1/manifest.json')==profile['render_manifest_sha256']
    for stream in ('stdout','stderr'):assert sha(BASE/'profile-r1'/(stream+'.log'))==profile[stream+'_sha256']
    for value,directory in ((cli,BASE/'cli-r2'),(dev,BASE/'native-r3'),(media,BASE/'installed-r3/media'),(install,BASE/'installed-r3')):
        for call in value['calls']:
            assert call['exit_code']==0
            label=call['label']
            for stream in ('stdout','stderr'):
                path=directory/(label+'.'+stream+'.log')
                if path.exists():assert sha(path)==call[stream+'_sha256'],path
    static=read(BASE/'static-review-r1.json');assert static['review_mode']=='static-PNG-only'
    assert not any(static[x] for x in ('continuous_playback_reviewed','audio_reviewed','natural_quality_accepted','full_capcut_parity'))
    for row in static['files']:assert sha(ROOT/row['path'])==row['sha256']
    files=[];videos=[];gifs=[];probe=shutil.which('ffprobe');assert probe
    pairs=[(ROOT/NATIVE,dev,24,12),(ROOT/INSTALLED,media,24,12),(ROOT/CLI,cli,60,30)]
    for name in ('native-r1','native-r2'):
        historical=read(BASE/name/'verification.json');assert historical['status']=='passed'
        pairs.append((ROOT/'docs/assets'/('native-hsl-20261020-v77-'+name),historical,24,12))
    historical=read(BASE/'cli-r1/verification.json');assert historical['status']=='passed-execution-probe'
    pairs.append((ROOT/'docs/assets/native-hsl-20261020-v77-cli-r1',historical,60,30))
    assert {d.name for d,_,_,_ in pairs}=={d.name for d in (ROOT/'docs/assets').glob('native-hsl-20261020-v77-*') if d.is_dir()}
    for directory,receipt,frames,fps in pairs:
        assert {p.name for p in directory.iterdir() if p.is_file()}==set(receipt['public_files'])
        for path in sorted(directory.iterdir()):
            assert path.is_file() and not path.is_symlink() and 0<path.stat().st_size<12*1024**2
            row={'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)}
            assert {'bytes':row['bytes'],'sha256':row['sha256']}==receipt['public_files'][path.name];files.append(row)
            if path.suffix in {'.mp4','.mkv'}:
                result=subprocess.run([probe,'-v','error','-select_streams','v:0','-show_streams','-show_frames',
                    '-show_entries','stream=width,height,pix_fmt,avg_frame_rate:frame=pts_time','-of','json',path],capture_output=True,timeout=60)
                assert result.returncode==0,(path,result.stderr);observed=json.loads(result.stdout)
                pts=[float(x['pts_time']) for x in observed['frames']]
                assert len(pts)==frames and all(abs(t-i/fps)<.0011 for i,t in enumerate(pts)),path
                videos.append({**row,'probe':observed})
            if path.suffix=='.gif':
                with Image.open(path) as im:
                    durations=[]
                    for i in range(im.n_frames):im.seek(i);durations.append(im.info['duration'])
                    assert sum(durations)==2000,path
                    gifs.append({**row,'physical_frames':im.n_frames,'durations_ms':durations,'total_duration_ms':sum(durations)})
    assert len(files)==130 and len(videos)==44 and len(gifs)==16,(len(files),len(videos),len(gifs))
    parsed=[]
    for name in SCRIPTS:
        path=ROOT/'scripts'/(name+'.py');ast.parse(path.read_text(encoding='utf8'),filename=str(path));parsed.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
    links=[]
    for path in (CONTRACT,REPORT,*(ROOT/name for name in DOCUMENTS)):
        text=path.read_text(encoding='utf8');assert b'\r\n' not in path.read_bytes(),path
        if path.relative_to(ROOT).as_posix() in DOCUMENTS:text=text.split('<!-- V77-CURRENT -->',1)[1].split('<!-- /V77-CURRENT -->',1)[0]
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target):continue
            resolved=(path.parent/urllib.parse.unquote(target)).resolve();assert resolved.exists(),(path,target)
            links.append({'source':path.relative_to(ROOT).as_posix(),'target':target})
    validator=Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py');skill_rows=[]
    for name in SKILLS:
        path=ROOT/'skills'/name;result=subprocess.run([sys.executable,'-E','-B','-X','utf8',validator,path],capture_output=True,timeout=30)
        assert result.returncode==0,(name,result.stdout,result.stderr)
        skill_rows.append({'name':name,'sha256':sha(path/'SKILL.md'),'exit_code':0,'stdout':result.stdout.decode('utf8','replace')})
    full=read(BASE/'full-r3.json')
    if not args.candidate:
        assert full['status']=='passed' and full['terminal_ok'] and full['exit_code']==0 and full['methods']==1746 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==current
        assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        skills=read(BASE/'skills-r1.json');assert skills['skill_count']==17 and skills['local_links_checked']==310
        assert all(x['installed_directory_resolves_to_repo'] for x in skills['results'])
        for row in skill_rows:assert next(x for x in skills['results'] if x['skill']==row['name'])['sha256']==row['sha256']
    record={'status':'passed-candidate-audit' if args.candidate else 'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(__file__),'frozen_inputs':current,'source_frozen_equal':current==frozen(),
        'focused_methods':{'native':19,'existing_HSL':29,'offline':22},'new_methods':21,
        'native_builds':builds,'native_module':manifest,'full_terminal':bool(full.get('terminal_ok')),'full_methods':full.get('methods') if full.get('terminal_ok') else None,
        'bounded_python_profile':{'receipt_sha256':sha(BASE/'profile-r1/verification.json'),'is_fps_benchmark':False},
        'current_media_runs':['native-r3','installed-r3','cli-r2'],'historical_media_runs':['native-r1','native-r2','cli-r1'],
        'public_files':files,'public_file_count':len(files),'public_bytes':sum(x['bytes'] for x in files),
        'video_probes':videos,'actual_video_probes':len(videos),'GIF_observations':gifs,'actual_GIF_probes':len(gifs),
        'syntax_parsed':parsed,'authored_document_links':links,'new_document_link_count':len(links),'changed_skills':skill_rows,
        'network':False,'virtualization':False,'new_model_inference':0,'continuous_playback_reviewed':False,
        'audio_reviewed':False,'natural_quality_accepted':False,'full_capcut_parity':False}
    assert record['source_frozen_equal'];output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','public_file_count','actual_video_probes','actual_GIF_probes','new_document_link_count','full_terminal')}))

if __name__=='__main__':main()
