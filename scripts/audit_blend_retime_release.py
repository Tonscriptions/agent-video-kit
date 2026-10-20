"""Bind V74 native media, authoring, install, documents and release inputs."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
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
from sync_blend_retime_documents import BASE,CONTRACT,DOCUMENTS,INSTALLED,NATIVE,REPORT,ROOT

SKILLS=('video-cut-agent-editor','video-cut-timeline','video-cut-project-ops','video-cut-quality')
SCRIPTS=('probe_blend_retime_baseline','probe_silent_retime_baseline','smoke_blend_retime',
    'verify_blend_retime_install','sync_blend_retime_documents','audit_blend_retime_release','publish_blend_retime')


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',action='store_true');args=parser.parse_args();output=args.output.resolve();assert not output.exists()
    current=frozen();focus=read(BASE/'targeted-r7.json');dev=read(BASE/'native-r3/verification.json')
    install=read(BASE/'installed-r2/verification.json');media=read(BASE/'installed-r2/media/verification.json')
    assert focus['terminal_ok'] and focus['methods']==23 and focus['skipped']==0
    for value in (focus,dev,install,media):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    for value in (dev,install,media):assert value['status']=='passed' and all(x['ok'] for x in value['checks'])
    assert len(current)==222 and len(install['resource_hashes'])==146 and install['bundle']['wheels']==7
    assert dev['cli_calls']==media['cli_calls']==24 and len(dev['checks'])==len(media['checks'])==30
    assert install['isolated_cli_calls']==27 and install['module_origin_probes']==1 and len(install['checks'])==11
    assert len(dev['cases'])==len(media['cases'])==3
    comparable=('name','mode','transform','frames','fps','max_rgb_error','alpha_byte_equal','PCM_byte_equal',
        'actual_decoded_sha256','independent_reference_sha256','author_model')
    assert [{k:x[k] for k in comparable} for x in dev['cases']]==[{k:x[k] for k in comparable} for x in media['cases']]
    assert dev['video_probes']==media['video_probes']
    assert [x['max_rgb_error'] for x in dev['cases']]==[0,1,1]
    assert all(x['frames']==30 and x['alpha_byte_equal'] and x['PCM_byte_equal'] for x in dev['cases'])
    for value in (dev,media):
        assert value['new_model_inference']==0 and not value['network'] and not value['virtualization']
        for case in value['cases']:
            assert len(case['command_metadata'])==1
            control=case['command_metadata'][0]
            assert control['kind']=='blend-opacity-automation' and control['backend']=='colorchannelmixer'
            assert control['clock_stages']==1 and control['state_samples']==2*control['sampled_frames']
    for path,receipt in ((ROOT/NATIVE,dev),(ROOT/INSTALLED,media)):
        for name,row in receipt['public_files'].items():
            assert (path/name).stat().st_size==row['bytes'] and sha(path/name)==row['sha256']
    baseline=read(BASE/'baseline-r1.json');silence=read(BASE/'silent-audio-baseline-r2.json')
    assert baseline['status']=='reproduced' and baseline['frozen_equal'] and len(baseline['frozen_before'])==220
    assert baseline['rejection']['code']=='EDIT_RETIME_BLEND_CLOCK_UNSUPPORTED'
    assert silence['baseline_offset_reproduced'] and silence['cases'][0]['nonzero_samples']==96000
    assert silence['cases'][0]['minimum']==silence['cases'][0]['maximum']==-256 and silence['cases'][1]['nonzero_samples']==0
    before=read(BASE/'targeted-r5-audio-before-fix.json');old_media=read(BASE/'native-r1/verification.json')
    assert before['exit_code']!=0 and before['methods']==23 and not before['terminal_ok']
    assert old_media['status']=='failed' and old_media['error']['message']=='screen-reverse-hold-full-stereo-PCM-equal'
    stopped=read(BASE/'full-r1.json');assert stopped['status']=='failed' and not stopped['terminal_ok'] and stopped['methods'] is None
    assert (BASE/'full-r1-stop.json').is_file()
    static=read(BASE/'static-review-r1.json');assert static['review_mode']=='static-PNG-only'
    assert not any(static[x] for x in ('continuous_playback_reviewed','audio_reviewed','natural_quality_accepted','full_capcut_parity'))
    for row in static['files']:assert sha(ROOT/row['path'])==row['sha256']
    probe=shutil.which('ffprobe');assert probe;files=[];videos=[];gifs=[]
    for directory in sorted((ROOT/'docs/assets').glob('retime-blend-20261020-v74-*')):
        if not directory.is_dir():continue
        for path in sorted(directory.rglob('*')):
            if not path.is_file():continue
            assert not path.is_symlink() and 0<path.stat().st_size<12*1024**2
            row={'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)};files.append(row)
            if path.suffix.lower() in {'.mp4','.mkv','.nut'}:
                result=subprocess.run([probe,'-v','error','-select_streams','v:0','-show_streams','-show_frames',
                    '-show_entries','stream=width,height,pix_fmt,avg_frame_rate:frame=pts_time','-of','json',str(path)],capture_output=True,timeout=60)
                assert result.returncode==0,(path,result.stderr);value=json.loads(result.stdout)
                times=[float(x['pts_time']) for x in value['frames']]
                assert times and all(abs(t-i/10)<.0011 for i,t in enumerate(times)),path
                videos.append({**row,'probe':value})
            if path.suffix.lower()=='.gif':
                with Image.open(path) as im:
                    durations=[]
                    for frame in range(im.n_frames):im.seek(frame);durations.append(im.info['duration'])
                    assert sum(durations)==3000,path
                    gifs.append({**row,'physical_frames':im.n_frames,'durations_ms':durations,'total_duration_ms':sum(durations)})
    parsed=[]
    for name in SCRIPTS:
        path=ROOT/'scripts'/(name+'.py');ast.parse(path.read_text(encoding='utf8'),filename=str(path));parsed.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
    links=[]
    for path in (CONTRACT,REPORT,*(ROOT/name for name in DOCUMENTS),ROOT/'docs/specs/完整作者输出变速与磁吸联动契约_v0.1_2026-10-18.md'):
        text=path.read_text(encoding='utf8');assert b'\r\n' not in path.read_bytes(),path
        if path.relative_to(ROOT).as_posix() in DOCUMENTS:
            text=text.split('<!-- V74-CURRENT -->',1)[1].split('<!-- /V74-CURRENT -->',1)[0]
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
    full=read(BASE/'full-r2.json')
    if not args.candidate:
        assert full['status']=='passed' and full['terminal_ok'] and full['exit_code']==0 and full['methods']==1667 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==current
        assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        skills=read(BASE/'skills-r1.json');assert skills['skill_count']==17 and all(x['installed_directory_resolves_to_repo'] for x in skills['results'])
        for row in skill_rows:assert next(x for x in skills['results'] if x['skill']==row['name'])['sha256']==row['sha256']
    record={'status':'passed-candidate-audit' if args.candidate else 'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(__file__),'frozen_inputs':current,'source_frozen_equal':current==frozen(),
        'focused_methods':23,'full_terminal':bool(full.get('terminal_ok')),'full_methods':full.get('methods') if full.get('terminal_ok') else None,
        'public_files':files,'public_file_count':len(files),'public_bytes':sum(x['bytes'] for x in files),
        'video_probes':videos,'actual_video_probes':len(videos),'GIF_observations':gifs,'actual_GIF_probes':len(gifs),
        'syntax_parsed':parsed,'authored_document_links':links,'new_document_link_count':len(links),'changed_skills':skill_rows,
        'network':False,'virtualization':False,'new_model_inference':0,'continuous_playback_reviewed':False,'audio_reviewed':False,
        'natural_quality_accepted':False,'full_capcut_parity':False}
    assert record['source_frozen_equal'];output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','public_file_count','actual_video_probes','actual_GIF_probes','new_document_link_count','full_terminal')}))


if __name__=='__main__':main()
