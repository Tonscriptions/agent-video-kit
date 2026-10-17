"""Opt-in existing local Whisper -> segmentation -> rendered subtitle evidence.

Input audio, model, fonts and renders stay in the supplied local project.
Only a rights-safe metadata report is exported; this does not authorize their
publication. No downloads, package installation, GUI or browser.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.media import probe_media
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.runtime import configure_local_runtime


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    configure_local_runtime()
    root=args.project.resolve()
    if root.exists():raise ValueError('Use a new explicit local project')
    env=dict(os.environ);env['PYTHONPATH']=str(ROOT/'product/src');env['PYTHONDONTWRITEBYTECODE']='1'
    logdir=root.parent/(root.name+'-cli-logs');logdir.mkdir(exist_ok=False)
    calls=[]
    def cli(*argv,expected=0):
        p=subprocess.run([sys.executable,'-B','-X','utf8','-m','ai_ad_editor',*map(str,argv)],cwd=ROOT,env=env,capture_output=True)
        n=len(calls)+1
        (logdir/f'{n:03}.stdout.json').write_bytes(p.stdout);(logdir/f'{n:03}.stderr.log').write_bytes(p.stderr)
        value=json.loads(p.stdout)
        calls.append({'command':value.get('command'),'exit_code':p.returncode,'expected':expected,
                      'stdout_sha256':sha(logdir/f'{n:03}.stdout.json'),'stderr_sha256':sha(logdir/f'{n:03}.stderr.log')})
        print(json.dumps(calls[-1],ensure_ascii=False),flush=True)
        if p.returncode!=expected:raise RuntimeError(p.stdout.decode('utf-8'))
        return value
    cli('project','init',root)
    p=json.loads((root/'project.json').read_text(encoding='utf-8'))
    p['settings']['timebase']['display_fps']={'num':8,'den':1}
    atomic_write_json(root/'project.json',p)
    registered=cli('asr','adapter','register','--project',root,'--adapter-id','whisper_local',
        '--python-executable',args.python_executable.resolve(),'--model-path',args.model_path.resolve(),
        '--evidence',args.evidence.resolve(),'--device',args.device,'--threads','4')
    cli('asr','adapter','inspect','--project',root,'--adapter-id','whisper_local')
    audio=cli('media','ingest','--project',root,'--input',args.input.resolve())['data']['asset']
    font=cli('media','ingest','--project',root,'--input',args.font.resolve())['data']['asset']
    p=json.loads((root/'project.json').read_text(encoding='utf-8'))
    aud=next(t['id'] for t in p['sequences'][0]['tracks'] if t['kind']=='audio')
    tps=int(p['settings']['timebase']['ticks_per_second'])
    plan=root/'cache/setup.json'
    atomic_write_json(plan,{'operations':[{'op':'add_track','track_id':'raw_asr','kind':'subtitle','order':5},
        {'op':'add_track','track_id':'captions','kind':'subtitle','order':10},
        {'op':'append_clip','track_id':aud,'asset_id':audio['id'],'source_in_tick':0,
         'source_out_tick':round(audio['probe']['duration_seconds']*tps),'timeline_start_tick':0}]})
    cli('timeline','compose','--project',root,'--input',plan)
    asr=cli('subtitle','transcribe','--project',root,'--asset-id',audio['id'],'--adapter-id','whisper_local',
        '--language','zh','--output','assets/subtitles/asr-original.srt','--apply','--track-id','raw_asr','--font-asset-id',font['id'])
    evaluation=cli('subtitle','evaluate','--project',root,'--input',asr['data']['output'],
        '--reference',args.reference.resolve(),'--report',root/'validation/recognition-cer.json')
    raw_project=json.loads((root/'project.json').read_text(encoding='utf-8'))
    operations=[]
    for track in raw_project['sequences'][0]['tracks']:
        if track['id']=='raw_asr':
            for clip in track['clips']:
                sub=clip['subtitle'];sub['style']['fontsize']=24;sub['style']['y']='h-text_h-32'
                operations.append({'op':'update_clip','track_id':'raw_asr','clip_id':clip['id'],'patch':{'subtitle':sub}})
    atomic_write_json(plan,{'operations':operations});cli('timeline','compose','--project',root,'--input',plan)
    original=root/'renders/original-asr.mp4'
    cli('render','--project',root,'--output',original,'--profile','custom','--width','640','--height','360')
    rules=root/'cache/segmentation-rules.json';atomic_write_json(rules,{'maxCells':8,'minMs':500})
    options=['subtitle','segment','--project',root,'--input',asr['data']['output'],'--source-asset-id',asr['data']['subtitle_asset']['id'],
        '--output','assets/subtitles/segmented.json','--rules',rules,'--apply','--track-id','captions','--font-asset-id',font['id']]
    cli(*options,'--dry-run')
    segmented=cli(*options)
    project=json.loads((root/'project.json').read_text(encoding='utf-8'))
    operations=[{'op':'update_track','track_id':'raw_asr','patch':{'muted':True}}]
    for track in project['sequences'][0]['tracks']:
        if track['id']=='captions':
            for clip in track['clips']:
                sub=clip['subtitle'];sub['style']['fontsize']=24;sub['style']['y']='h-text_h-32'
                operations.append({'op':'update_clip','track_id':'captions','clip_id':clip['id'],'patch':{'subtitle':sub}})
    atomic_write_json(plan,{'operations':operations});cli('timeline','compose','--project',root,'--input',plan)
    actual=root/'renders/segmented-asr.mp4'
    cli('render','--project',root,'--output',actual,'--profile','custom','--width','640','--height','360')
    cli('quality','check','--project',root,'--input',actual,'--width','640','--height','360','--require-audio')
    cli('validate','--project',root);cli('policy','audit','--project',root)
    cli('rights','check','--project',root,expected=7)
    rejected=cli('render','--project',root,'--output',root/'renders/blocked-publish.mp4','--publish',expected=7)
    assert not (root/'renders/blocked-publish.mp4').exists()
    def decode(path,audio=False):
        flags=['-vn','-ac','2','-ar','48000','-f','f32le','pipe:1'] if audio else ['-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
        return subprocess.run(['ffmpeg','-v','error','-i',str(path),*flags],capture_output=True,check=True).stdout
    rgb=decode(actual);assert len(rgb)%(640*360*3)==0
    before_audio,after_audio=decode(original,True),decode(actual,True)
    assert before_audio==after_audio
    result=segmented['data']['plan']
    source_lines=result['source']['lines'];pieces=result['pieces']
    checks=[]
    for line in source_lines:
        parts=[p for p in pieces if p['line_id']==line['id']]
        reconstructed=''.join(p['text'] for p in parts)
        assert ''.join(reconstructed.split())==''.join(line['text'].split())
        assert all(line['start_tick']<=p['start_tick']<p['end_tick']<=line['end_tick'] for p in parts)
        checks.append({'line_id':line['id'],'source_text':line['text'],'start_tick':line['start_tick'],'end_tick':line['end_tick'],
                       'parts':len(parts),'text_preserved':True,'pieces_inside_source_clock':True})
    transcription=asr['data']['transcription']
    report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed','scope':'one existing Mandarin reference recording, reused corpus; no new independent speaker or word alignment',
        'new_model_inference':1,'device_requested':args.device,'audio_sha256':sha(args.input.resolve()),
        'reference_sha256':sha(args.reference.resolve()),'input_duration_seconds':audio['probe']['duration_seconds'],
        'adapter_sha256':registered['data']['adapter']['sha256'],'transcription':transcription,
        'cer':evaluation['data']['result'],'source_line_count':len(source_lines),'segmented_cue_count':len(pieces),'line_checks':checks,
        'timing_basis':sorted({p['timing_basis'] for p in pieces}),'rules':result['rules'],
        'render':{'sha256':sha(actual),'decoded_rgb_frames':len(rgb)//(640*360*3),'probe':probe_media(actual)},
        'audio_unchanged':True,'decoded_audio_sample_frames':len(after_audio)//8,
        'publication_blocked':True,'publication_error_codes':[e['code'] for e in rejected['errors']],
        'cli_calls':calls,'continuous_playback_reviewed':False,'audio_listened':False,'public_audio_or_video':False,
        'local_artifact_directory':str(root)}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    atomic_write_json(args.report,report)
    print(json.dumps({'status':'passed','source_lines':len(source_lines),'segmented_cues':len(pieces),'cer':report['cer']['cer'],'report':str(args.report)},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('project','input','reference','font','python-executable','model-path','evidence','report'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--device',choices=('cpu','cuda'),default='cpu')
    run(parser.parse_args())
