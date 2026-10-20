"""Recheck retained V73 bytes, clocks, links and optional final regression."""
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
import urllib.parse
from run_frozen_regression import frozen
from sync_lut_automation_documents import BASE,REL,REPORT,CONTRACT,DOCUMENTS,NATIVE,INSTALLED,ROOT


def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',action='store_true');args=parser.parse_args();output=args.output.resolve()
    assert output.is_relative_to(ROOT/'docs') and not output.exists()
    current=frozen();focus=read(BASE/'targeted-r5.json');dev=read(BASE/'native-r5/verification.json')
    install=read(BASE/'installed-r1/verification.json');installed_media=read(BASE/'installed-r1/media/verification.json')
    for value in (focus,dev,install,installed_media):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
        assert value['status']=='passed'
    assert focus['terminal_ok'] and focus['methods']==30 and focus['skipped']==0
    assert dev['decoded_sha256']==installed_media['decoded_sha256']
    clocks=[read(BASE/(name+'/verification.json')) for name in ('clocks-native-r2','clocks-installed-r2')]
    for value in clocks:
        assert value['status']=='passed' and value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
        assert len(value['cases'])==2 and all(row['ok'] and row['max_rgb_error']<=1 and row['alpha_byte_equal'] for row in value['cases'])
    assert [row['decoded_sha256'] for row in clocks[0]['cases']]==[row['decoded_sha256'] for row in clocks[1]['cases']]
    baseline=read(BASE/'baseline-r1.json')
    assert [x['pixel_rgba'] for x in baseline['observations']]==[[32,96,192,128],[112,96,112,128],[32,96,192,128]]
    for path,receipt in ((ROOT/NATIVE,dev),(ROOT/INSTALLED,installed_media)):
        for name,row in receipt['public_files'].items():assert sha(path/name)==row['sha256'] and (path/name).stat().st_size==row['bytes']
    videos=[];files=[];probe=shutil.which('ffprobe');assert probe
    for directory in sorted((ROOT/'docs/assets').glob('lut-intensity-20261020-v73-*')):
        if not directory.is_dir():continue
        for path in sorted(directory.rglob('*')):
            if not path.is_file():continue
            assert not path.is_symlink() and path.stat().st_size<12*1024**2
            row={'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)};files.append(row)
            if path.suffix.lower() in {'.mp4','.mkv','.nut','.webm'}:
                result=subprocess.run([probe,'-v','error','-select_streams','v:0','-show_frames','-show_streams',
                    '-show_entries','stream=width,height,pix_fmt,avg_frame_rate:frame=pts_time','-of','json',str(path)],capture_output=True,timeout=60)
                assert result.returncode==0,(path,result.stderr)
                value=json.loads(result.stdout);assert value['frames'] and value['streams']
                videos.append({**row,'probe':value})
    parsed=[]
    for name in ('probe_lut_intensity_baseline','smoke_lut_automation','verify_lut_automation_install',
                 'probe_lut_automation_clocks','sync_lut_automation_documents','audit_lut_automation_release','publish_lut_automation'):
        path=ROOT/'scripts'/(name+'.py');ast.parse(path.read_text(encoding='utf8'),filename=str(path));parsed.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
    links=[]
    for path in (REPORT,CONTRACT,*(ROOT/name for name in DOCUMENTS)):
        text=path.read_text(encoding='utf8')
        if path not in (REPORT,CONTRACT):text=text.split('<!-- V73-CURRENT -->',1)[1].split('<!-- /V73-CURRENT -->',1)[0]
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target):continue
            resolved=(path.parent/urllib.parse.unquote(target)).resolve();assert resolved.exists(),(path,target)
            links.append({'source':path.relative_to(ROOT).as_posix(),'target':target})
    static=read(BASE/'static-review-r1.json')
    assert static['review_mode']=='static-PNG-only' and not static['continuous_playback_reviewed'] and not static['audio_reviewed']
    for row in static['files']:assert sha(ROOT/row['path'])==row['sha256']
    full=read(BASE/'full-r1.json')
    if not args.candidate:
        assert full['terminal_ok'] and full['exit_code']==0 and full['methods']==1644 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==current
        assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        skills=read(BASE/'skills-r1.json');assert skills['skill_count']==17 and all(row['installed_directory_resolves_to_repo'] for row in skills['results'])
    record={'status':'passed-candidate-audit' if args.candidate else 'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(__file__),'source_frozen_equal':current==frozen(),'frozen_inputs':current,
        'focus_methods':focus['methods'],'new_product_methods':30,'full_terminal':bool(full.get('terminal_ok')),
        'full_methods':full.get('methods') if full.get('terminal_ok') else None,
        'public_file_count':len(files),'actual_video_probes':len(videos),'public_files':files,'video_probes':videos,
        'syntax_parsed':parsed,'new_document_links':links,'new_document_link_count':len(links),
        'analytic_clock_cases_per_environment':2,'clock_cli_calls_per_environment':clocks[0]['cli_calls'],
        'network':False,'virtualization':False,'new_model_inference':0,'continuous_playback_reviewed':False,
        'audio_reviewed':False,'natural_quality_accepted':False,'full_capcut_parity':False}
    assert record['source_frozen_equal'];output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:record[k] for k in ('status','public_file_count','actual_video_probes','new_document_link_count','full_terminal')}))


if __name__=='__main__':main()
