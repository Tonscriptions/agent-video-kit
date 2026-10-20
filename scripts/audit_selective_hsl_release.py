"""Bind V76 media, source bytes, author contracts, Skills and final release proof."""
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
from sync_selective_hsl_documents import BASE,CONTRACT,DOCUMENTS,INSTALLED,NATIVE,REPORT,ROOT

SKILLS=('video-cut-agent-editor','video-cut-timeline','video-cut-project-ops','video-cut-quality')
SCRIPTS=('probe_selective_hsl_baseline','smoke_selective_hsl','verify_selective_hsl_install',
         'probe_selective_hsl_performance','sync_selective_hsl_documents','audit_selective_hsl_release','publish_selective_hsl')
def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',action='store_true');args=parser.parse_args();output=args.output.resolve();assert not output.exists()
    current=frozen();focus=read(BASE/'targeted-r4.json');dev=read(BASE/'native-r2/verification.json')
    install=read(BASE/'installed-r1/verification.json');media=read(BASE/'installed-r1/media/verification.json')
    assert focus['terminal_ok'] and focus['methods']==29 and focus['skipped']==0 and len(current)==225
    for value in (focus,dev,install,media):assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    for value in (dev,install,media):assert value['status']=='passed' and all(row['ok'] for row in value['checks'])
    assert len(install['resource_hashes'])==147 and install['bundle']['wheels']==7
    assert install['isolated_cli_calls']==27 and install['module_origin_probes']==1 and len(install['checks'])==12
    assert dev['cli_calls']==media['cli_calls']==24 and len(dev['checks'])==len(media['checks'])==50
    assert len(dev['cases'])==len(media['cases'])==4
    keys=('name','effect','frames','fps','max_rgb_error','alpha_byte_equal','PCM_byte_equal','actual_decoded_sha256','independent_reference_sha256','kernel_metadata')
    assert [{k:x[k] for k in keys} for x in dev['cases']]==[{k:x[k] for k in keys} for x in media['cases']]
    assert dev['video_probes']==media['video_probes']
    for value in (dev,media):
        assert value['new_model_inference']==0 and not value['network'] and not value['virtualization']
        for case in value['cases']:
            assert case['max_rgb_error']==1 and case['frames']==24 and case['fps']==12
            assert case['alpha_byte_equal'] and case['PCM_byte_equal'] and len(case['kernel_metadata'])==1
            kernel=case['kernel_metadata'][0]
            assert kernel['kind']=='selective-hsl' and kernel['engine']=='encoded-rgb-eight-band-hsl-v1'
            assert kernel['alpha']=='exact-input-alpha' and kernel['achromatic_policy']=='unchanged'
            assert kernel['sampled_frames']==24 and 0<kernel['kernel_bytes']<=64*1024 and not kernel['bypass']
        names={x['name'] for x in value['checks'] if x['ok']}
        assert {'source-has-clear-partial-and-opaque-coverage','package-last-case-decoded-byte-equal'}<=names
    baseline=read(BASE/'baseline-r1.json');failed=read(BASE/'targeted-r1.json')
    assert baseline['status']=='observed-unsupported-and-unmodified-pixels' and baseline['frozen_equal'] and len(baseline['frozen_before'])==223
    assert baseline['source_commit']=='ea232b9d4da233c6e9e89289279eee68f2eb5eae'
    assert baseline['frames']==6 and baseline['decoded_bytes_equal_original'] and not baseline['compiled_filters']
    assert failed['exit_code']!=0 and failed['methods']==24 and not failed['terminal_ok']
    text=(BASE/'targeted-r1.log').read_text(encoding='utf8');assert 'FAILED (failures=1, errors=2)' in text and 'OverflowError' in text
    for name,count in [('targeted-r2.json',26),('targeted-r3.json',29),('color-regression-r1.json',28),('spatial-regression-r1.json',29),('lut-regression-r1.json',30)]:
        d=read(BASE/name);assert d['terminal_ok'] and d['methods']==count and d['skipped']==0 and d['frozen_equal']
    performance=read(BASE/'performance-r1.json')
    assert performance['status']=='passed-execution-probe' and performance['frozen_equal']
    assert performance['frozen_before']==performance['frozen_after']==current
    assert not performance['real_time_accepted'] and performance['frames_per_case']==3
    assert performance['filter_threads']==1 and performance['repetitions']==1 and len(performance['cases'])==3
    assert all(x['actual_frames']==3 for x in performance['cases'])
    assert not any(x['30fps_wall_target_met_in_this_probe'] for x in performance['cases'] if x['name']!='control')
    for call in performance['calls']:
        assert call['exit_code']==0
        for row in call['logs'].values():assert sha(ROOT/row['path'])==row['sha256']
    static=read(BASE/'static-review-r1.json');assert static['review_mode']=='static-PNG-only'
    assert not any(static[x] for x in ('continuous_playback_reviewed','audio_reviewed','natural_quality_accepted','full_capcut_parity'))
    for row in static['files']:assert sha(ROOT/row['path'])==row['sha256']
    files=[];videos=[];gifs=[];probe=shutil.which('ffprobe');assert probe
    receipt_pairs=[(ROOT/NATIVE,dev),(ROOT/INSTALLED,media)]
    for name,receipt_path in [('native-r1','native-r1/verification.json')]:
        historical=read(BASE/receipt_path);assert historical['status']=='passed'
        receipt_pairs.append((ROOT/'docs/assets'/('selective-hsl-20261020-v76-'+name),historical))
    assert {d.name for d,_ in receipt_pairs}=={d.name for d in (ROOT/'docs/assets').glob('selective-hsl-20261020-v76-*') if d.is_dir()}
    for directory,receipt in receipt_pairs:
        actual_names={p.name for p in directory.iterdir() if p.is_file()};assert actual_names==set(receipt['public_files'])
        for path in sorted(directory.iterdir()):
            assert path.is_file() and not path.is_symlink() and 0<path.stat().st_size<12*1024**2
            row={'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)}
            assert {'bytes':row['bytes'],'sha256':row['sha256']}==receipt['public_files'][path.name]
            files.append(row)
            if path.suffix in {'.mp4','.mkv'}:
                result=subprocess.run([probe,'-v','error','-select_streams','v:0','-show_streams','-show_frames',
                    '-show_entries','stream=width,height,pix_fmt,avg_frame_rate:frame=pts_time','-of','json',path],capture_output=True,timeout=60)
                assert result.returncode==0,(path,result.stderr);value=json.loads(result.stdout)
                pts=[float(x['pts_time']) for x in value['frames']]
                assert len(pts)==24 and all(abs(t-i/12)<.0011 for i,t in enumerate(pts)),path
                videos.append({**row,'probe':value})
            if path.suffix=='.gif':
                with Image.open(path) as im:
                    durations=[]
                    for i in range(im.n_frames):im.seek(i);durations.append(im.info['duration'])
                    assert sum(durations)==2000,path
                    gifs.append({**row,'physical_frames':im.n_frames,'durations_ms':durations,'total_duration_ms':sum(durations)})
    assert len(files)==84 and len(videos)==27 and len(gifs)==12
    parsed=[]
    for name in SCRIPTS:
        path=ROOT/'scripts'/(name+'.py');ast.parse(path.read_text(encoding='utf8'),filename=str(path));parsed.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
    links=[]
    for path in (CONTRACT,REPORT,*(ROOT/name for name in DOCUMENTS)):
        text=path.read_text(encoding='utf8');assert b'\r\n' not in path.read_bytes(),path
        if path.relative_to(ROOT).as_posix() in DOCUMENTS:text=text.split('<!-- V76-CURRENT -->',1)[1].split('<!-- /V76-CURRENT -->',1)[0]
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
    full=read(BASE/'full-r1.json')
    if not args.candidate:
        assert full['status']=='passed' and full['terminal_ok'] and full['exit_code']==0 and full['methods']==1725 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==current
        assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        skills=read(BASE/'skills-r1.json');assert skills['skill_count']==17 and skills['local_links_checked']==302
        assert all(x['installed_directory_resolves_to_repo'] for x in skills['results'])
        for row in skill_rows:assert next(x for x in skills['results'] if x['skill']==row['name'])['sha256']==row['sha256']
    record={'status':'passed-candidate-audit' if args.candidate else 'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(__file__),'frozen_inputs':current,'source_frozen_equal':current==frozen(),
        'focused_methods':29,'full_terminal':bool(full.get('terminal_ok')),'full_methods':full.get('methods') if full.get('terminal_ok') else None,
        'current_media_runs':['native-r2','installed-r1'],'historical_media_runs':['native-r1'],
        'public_files':files,'public_file_count':len(files),'public_bytes':sum(x['bytes'] for x in files),
        'video_probes':videos,'actual_video_probes':len(videos),'GIF_observations':gifs,'actual_GIF_probes':len(gifs),
        'syntax_parsed':parsed,'authored_document_links':links,'new_document_link_count':len(links),'changed_skills':skill_rows,
        'network':False,'virtualization':False,'new_model_inference':0,'continuous_playback_reviewed':False,
        'audio_reviewed':False,'natural_quality_accepted':False,'full_capcut_parity':False}
    assert record['source_frozen_equal'];output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','public_file_count','actual_video_probes','actual_GIF_probes','new_document_link_count','full_terminal')}))


if __name__=='__main__':main()
