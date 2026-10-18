"""Actual registered native CTC inference; protocol mocks are not used here."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'scripts')]
from ai_ad_editor.cli import main as cli_main
from ai_ad_editor.local_ctc import ENGINE
from ai_ad_editor.project import load_project,save_project
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import sha256_file
from run_frozen_regression import frozen

NATIVE=Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe')


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main(args):
    root,evidence=args.project.resolve(),args.evidence.resolve()
    assert root.is_relative_to(ROOT) and not root.exists()
    assert evidence.is_relative_to(ROOT/'docs/validation/evidence')
    evidence.mkdir(parents=True,exist_ok=False)
    configure_local_runtime()
    before=frozen();calls=[];state={'status':'started','frozen_before':before,'model_inference':'actual native CTC; no mocks'}
    save(evidence/'state.json',state)
    def cli(*values,expected=0):
        out,err=io.StringIO(),io.StringIO();started=time.monotonic()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):code=cli_main(list(map(str,values)))
        result=json.loads(out.getvalue())
        row={'args':list(map(str,values)),'exit_code':code,'seconds':round(time.monotonic()-started,3),'stderr':err.getvalue(),'result':result}
        calls.append(row);save(evidence/'cli'/f'{len(calls):03}.json',row)
        print(json.dumps({'call':len(calls),'command':list(map(str,values[:2])),'code':code,'seconds':row['seconds']}),flush=True)
        assert code==expected,(len(calls),result)
        return result
    try:
        cli('project','init',root)
        cli('asr','adapter','register','--project',root,'--adapter-id','ctc','--engine',ENGINE,
            '--python-executable',NATIVE,'--model-path',args.model.resolve(),'--device','cuda','--threads','4',
            '--evidence',args.model_evidence.resolve(),'--license-spdx','Apache-2.0','--creator','upstream model authors')
        cli('asr','adapter','inspect','--project',root,'--adapter-id','ctc')
        if args.language=='en':
            public=ROOT/'docs/assets/ctc-alignment-20261018'
            source=public/'input.wav';text=public/'transcript.txt'
        else:
            public=None
            source=Path(json.loads((ROOT/'product/.runtime/asr-fixtures/s4-input.json').read_text(encoding='utf-8'))['input'])
            text=root/'authored-simplified-transcript.txt'
            text.write_text('我们会把责任扛起来。让台湾的经济结构转型。按部就班来规划与执行。是各国政府越来越关心的课题。照顾压力将会减轻。',encoding='utf-8')
            original=ROOT/'product/.runtime/asr-fixtures/s4-reference.txt'
            original_text=original.read_text(encoding='utf-8-sig').strip()
            supplied=text.read_text(encoding='utf-8')
            save(evidence/'script-choice.json',{'original_transcript_sha256':sha256_file(original),
                'authored_transcript_sha256':sha256_file(text),'same_codepoint_length':len(original_text)==len(supplied),
                'explicitly_authored_character_substitutions':[{'index':i,'original':a,'supplied':b} for i,(a,b) in enumerate(zip(original_text,supplied)) if a!=b],
                'automatic_runtime_script_conversion':False,'audio_published':False})
        cli('media','ingest','--project',root,'--input',source,'--asset-id','speech')
        if args.language=='en':
            cli('media','ingest','--project',root,'--input',public/'input.mp4','--asset-id','background')
            cli('media','ingest','--project',root,'--input',public/'font.ttf','--asset-id','font')
            _,project=load_project(root)
            truth=json.loads((public/'input-provenance.json').read_text(encoding='utf-8'))
            samples=truth['samples'];ticks=(samples*90000+8000)//16000
            project['settings']['canvas'].update(width=1280,height=720)
            project['settings']['timebase']['display_fps']={'num':30,'den':1}
            sequence=project['sequences'][0];sequence['duration_tick']=ticks
            sequence['tracks']=[{'id':'picture','kind':'video','order':0,'clips':[{'id':'base','asset_id':'background',
                'timeline_start_tick':0,'duration_tick':ticks,'source_in_tick':0,'source_out_tick':ticks}]},
                {'id':'audio','kind':'audio','order':1,'clips':[{'id':'voice','asset_id':'speech','timeline_start_tick':0,
                    'duration_tick':ticks,'source_in_tick':0,'source_out_tick':ticks}]},
                {'id':'captions','kind':'subtitle','order':2,'clips':[]}]
            for track in sequence['tracks']:track.update(locked=False,muted=False)
            save_project(root,project)
        common=['subtitle','align','--project',root,'--asset-id','speech','--adapter-id','ctc','--transcript',text,
                '--output','assets/aligned/short.json','--granularity','whitespace' if args.language=='en' else 'character']
        if args.language=='en':common+=['--apply','--track-id','captions','--font-asset-id','font']
        cli(*common,'--dry-run')
        first=cli(*common,'--idempotency-key','short-once')
        replay=cli(*common,'--idempotency-key','short-once')
        assert first['operation_id']==replay['operation_id']
        results={'short':first['data']['result']}
        if args.language=='zh':
            cli('subtitle','align','--project',root,'--asset-id','speech','--adapter-id','ctc','--transcript',
                ROOT/'product/.runtime/asr-fixtures/s4-reference.txt','--output','assets/aligned/traditional.json',expected=2)
            long_source=ROOT/'product/.runtime/asr-fixtures/s4-three-copies.wav'
            long_text=root/'authored-simplified-long.txt'
            long_text.write_text(text.read_text(encoding='utf-8')*3,encoding='utf-8')
        else:
            long_source=public/'input-long.wav';long_text=public/'transcript-long.txt'
        cli('media','ingest','--project',root,'--input',long_source,'--asset-id','speech-long')
        long_result=cli('subtitle','align','--project',root,'--asset-id','speech-long','--adapter-id','ctc','--transcript',long_text,
            '--output','assets/aligned/long.json','--granularity','whitespace' if args.language=='en' else 'character')
        results['long']=long_result['data']['result']
        assert results['long']['samples']>30*16000
        assert len(results['long']['segments'][0]['windows'])>=2
        if args.language=='en':
            units=results['short']['segments'][0]['units']
            assert len(units)==len(truth['words'])
            errors=[]
            for unit,reference in zip(units,truth['words']):
                assert unit['text']==reference['word']
                errors.append({'word':unit['text'],'start_error_seconds':(unit['start_sample']-reference['start_sample'])/16000,
                    'end_error_seconds':(unit['end_sample']-reference['end_sample'])/16000})
            maximum=max(abs(e[k]) for e in errors for k in ('start_error_seconds','end_error_seconds'))
            quality={'reference':'authored trimmed word blocks; not phonetic annotations',
                'predeclared_max_error_seconds':2/30,'observed_max_error_seconds':maximum,'passed':maximum<=2/30,'words':errors}
            save(evidence/'word-boundary-quality.json',quality)
            # A real SRT gives separate alignment windows and canonical text offsets.
            def stamp(sample):
                ms=sample*1000//16000;seconds,ms=divmod(ms,1000);minutes,seconds=divmod(seconds,60)
                return f'00:{minutes:02}:{seconds:02},{ms:03}'
            split=truth['words'][3]['start_sample']-4000
            srt=root/'authored-cues.srt'
            srt.write_text(f'1\n00:00:00,000 --> {stamp(split)}\nRED BLUE GREEN\n\n2\n{stamp(split)} --> {stamp(samples)}\nRED BLUE GREEN\n',encoding='utf-8')
            segmented=cli('subtitle','align','--project',root,'--asset-id','speech','--adapter-id','ctc','--transcript',srt,
                '--output','assets/aligned/srt.json','--granularity','whitespace')
            results['srt']=segmented['data']['result']
            assert len(results['srt']['segments'])==2
            # Render actual generated word timings, then retain editable project assets.
            render=cli('render','--project',root,'--output',root/'renders/aligned.mkv','--profile','custom','--width','1280','--height','720',
                '--container','mkv','--audio-codec','pcm_f32le','--pixel-format','yuv444p','--crf','0')
            shutil.copyfile(root/'renders/aligned.mkv',public/'aligned-lossless.mkv')
            shutil.copyfile(root/'assets/aligned/short.json',public/'short-alignment.json')
            shutil.copyfile(root/'assets/aligned/short.srt',public/'aligned.srt')
            results['render']=render['data']
        cli('validate','--project',root)
        cli('policy','audit','--project',root)
        after=frozen()
        model_runs=[r for r in results.values() if isinstance(r,dict) and r.get('engine')==ENGINE]
        state.update(status='verified',language=args.language,cli_calls=len(calls),frozen_after=after,frozen_equal=after==before,
            actual_worker_processes=len(model_runs),actual_model_forward_calls=sum(r['worker']['model_forward_calls'] for r in model_runs),
            actual_samples={k:r['samples'] for k,r in results.items() if isinstance(r,dict) and 'samples' in r},
            versions={k:r['worker']['versions'] for k,r in results.items() if isinstance(r,dict) and r.get('engine')==ENGINE},
            peak_cuda_bytes={k:r['worker']['peak_cuda_bytes'] for k,r in results.items() if isinstance(r,dict) and r.get('engine')==ENGINE},
            generator_sha256=sha256_file(Path(__file__)),continuous_playback_review=False,listening_review=False)
        assert state['frozen_equal']
        save(evidence/'results.json',results);save(evidence/'state.json',state)
    except BaseException as exc:
        state.update(status='failed',error=repr(exc),cli_calls=len(calls),frozen_after=frozen(),generator_sha256=sha256_file(Path(__file__)))
        save(evidence/'state.json',state);raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--language',choices=['en','zh'],required=True)
    for name in ('project','evidence','model','model-evidence'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
