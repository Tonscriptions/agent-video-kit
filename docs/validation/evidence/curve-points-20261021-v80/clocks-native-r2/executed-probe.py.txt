"""Independent analytic RGB curve clocks: nonlinear nesting, reverse and fractional offset."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--installed',type=Path);args=parser.parse_args()
    work=args.work.resolve();evidence=args.evidence.resolve()
    assert not work.exists() and not evidence.exists()
    assert work.is_relative_to(ROOT/'product/.runtime') and evidence.is_relative_to(ROOT/'docs')
    work.mkdir(parents=True);evidence.mkdir(parents=True)
    (evidence/'executed-probe.py.txt').write_bytes(Path(__file__).read_bytes())
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'script_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'frozen_before':frozen(),'network':False,'virtualization':False,'new_model_inference':0,'calls':[],'cases':[]}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    def run(label,command,*,cwd=ROOT,cli=False):
        command=list(map(str,command));env=dict(os.environ);temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
        env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,timeout=300)
        (evidence/(label+'.stderr.log')).write_bytes(result.stderr)
        if cli:(evidence/(label+'.stdout.log')).write_bytes(result.stdout)
        record['calls'].append({'label':label,'cli':cli,'command':command,'exit_code':result.returncode,
            'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest()});save()
        assert result.returncode==0,label+': '+result.stderr[-1000:].decode('utf8','replace')+result.stdout[-1000:].decode('utf8','replace')
        return result.stdout
    if args.installed:prefix=[sys.executable,'-I','-S','-B','-X','utf8',args.installed.resolve()/'run.py']
    else:
        bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
        prefix=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,ROOT/'product/src']
    def cli(label,*argv):return json.loads(run(label,[*prefix,*argv],cli=True))
    try:
        project=work/'project';cli('init','project','init',project)
        source=work/'plate.png';Image.new('RGB',(64,64),(32,96,192)).save(source)
        cli('ingest','media','ingest','--project',project,'--input',source,'--asset-id','plate')
        p=json.loads((project/'project.json').read_bytes());p['settings']['canvas']={'width':64,'height':64,'background':'#000000'}
        p['settings']['timebase']={'ticks_per_second':90000,'display_fps':{'num':10,'den':1}}
        root_sequence=p['sequences'][0];sid=root_sequence['id'];duration=round(2*math.log(3)*90000)
        leaf={'id':'leaf','asset_id':'plate','timeline_start_tick':0,'duration_tick':180000,'source_in_tick':0,'source_out_tick':180000,
            'effects':[{'type':'curves','parameters':{'all':'0/0 1/1'},'keyframes':[{'property':'all.1.y','keyframes':[
                {'at_tick':0,'value':.3,'interpolation':'linear'},{'at_tick':180000,'value':1,'interpolation':'linear'}]}]}]}
        child={'id':'child','name':'child','duration_tick':180000,'tracks':[{'id':'child_track','kind':'video','order':0,'clips':[leaf]}]}
        curved={'id':'curved','sequence_id':'child','timeline_start_tick':0,'duration_tick':duration,
            'source_in_tick':0,'source_out_tick':180000,'speed_curve':{'keyframes':[{'at_tick':0,'speed':.5},{'at_tick':180000,'speed':1.5}]}}
        for name in ('curved-forward','curved-inside-reversed-2x-ancestor','fractional-offset'):
            candidate=copy.deepcopy(p);seq=candidate['sequences'][0];candidate['sequences'].append(copy.deepcopy(child))
            if name=='curved-forward':seq['duration_tick']=duration;seq['tracks'][0]['clips']=[copy.deepcopy(curved)]
            elif name!='fractional-offset':
                host={'id':'curve_host','name':'host','duration_tick':duration,'tracks':[{'id':'host_track','kind':'video','order':0,'clips':[copy.deepcopy(curved)]}]}
                candidate['sequences'].append(host);seq['duration_tick']=round(duration/2)
                seq['tracks'][0]['clips']=[{'id':'outer','sequence_id':'curve_host','timeline_start_tick':0,
                    'duration_tick':seq['duration_tick'],'source_in_tick':0,'source_out_tick':duration,'reverse':True,'speed':2}]
            rate=10.
            if name=='fractional-offset':
                candidate['sequences']=[seq];candidate['settings']['timebase']['display_fps']={'num':30000,'den':1001};rate=30000/1001
                seq['duration_tick']=135000;clip=copy.deepcopy(leaf);clip.update(timeline_start_tick=9900,duration_tick=90000,source_out_tick=90000)
                clip['effects'][0]['keyframes'][0]['keyframes'][1]['at_tick']=90000;seq['tracks'][0]['clips']=[clip]
            (project/'project.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            output=project/'renders'/(name+'.mp4')
            options=['render','--project',project,'--output',output,'--profile','custom','--width',64,'--height',64]
            plan=cli(name+'-plan',*options,'--dry-run')['data']['plan'];cli(name+'-render',*options)
            command=plan['command'];inputs=command[1:command.index('-filter_complex')]
            if '-progress' in inputs:
                i=inputs.index('-progress');del inputs[i:i+2]
            raw=run(name+'-raw',[command[0],*inputs,'-filter_complex',plan['filter_complex'],'-map','[vout]',
                '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1','-map','[aout]','-f','null','NUL'],cwd=project)
            count=math.ceil(seq['duration_tick']/90000*rate);size=64*64*4;assert len(raw)==count*size
            rows=[];maximum=0;scale=(duration/90000)/(2*math.log(3))
            for i in range(count):
                display=i/rate
                host_time=display if name=='curved-forward' else duration/90000-display*duration/seq['duration_tick']
                source_time=math.exp(host_time/(2*scale))-1
                strength=.3+.7*max(0,min(1,source_time/2))
                if name=='fractional-offset':source_time=display-.11;strength=.3+.7*source_time if .11<=display<1.11 else 0.
                expected=tuple(round(c*strength) for c in (32,96,192))
                frame=raw[i*size:(i+1)*size]
                error=max(abs(value-expected[j%4]) for j,value in enumerate(frame) if j%4!=3)
                maximum=max(maximum,error);assert frame[3::4]==bytes([255])*(64*64)
                rows.append({'display':display,'independent_source_seconds':source_time,'expected_rgb':expected,'actual_rgb':list(frame[:3]),'max_error':error})
            case={'name':name,'frames':count,'max_rgb_error':maximum,'alpha_byte_equal':True,
                'decoded_sha256':'sha256:'+hashlib.sha256(raw).hexdigest(),'oracle':'integral ds/(0.5+0.5*s), analytic exponential inverse; outer author reverse/2x',
                'effect_targets':[m for m in plan['inputs'] if m.get('kind')=='curve-point-automation'],'samples':rows,'ok':maximum<=1}
            if name=='fractional-offset':
                import re
                graph=re.sub(r",sendcmd=filename='[^']+'",'',plan['filter_complex'])
                graph=re.sub(r",curves@avk_cp_[^\[]+",'',graph)
                baseline=run(name+'-static-baseline',[command[0],*inputs,'-filter_complex',graph,'-map','[vout]',
                    '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1','-map','[aout]','-f','null','NUL'],cwd=project)
                expected_visible=[i for i in range(count) if .11<=i/rate<1.11]
                visible=[i for i in range(count) if baseline[i*size:i*size+3]!=bytes(3)]
                missing=sorted(set(expected_visible)-set(visible))
                curve_visible=[i for i in range(count) if raw[i*size:i*size+3]!=bytes(3)]
                accepted_error=max(row['max_error'] for i,row in enumerate(rows) if i not in missing)
                assert missing==[33] and curve_visible==visible and accepted_error<=1
                case.update(ok=False,classification='known-CFR-01-unaccepted',
                    inherited_static_coverage_gap=True,expected_visible_frames=expected_visible,
                    actual_visible_frames=visible,missing_visible_frames=missing,
                    static_baseline_sha256='sha256:'+hashlib.sha256(baseline).hexdigest(),
                    max_error_excluding_missing_frame=accepted_error,
                    oracle='actual 30000/1001 CFR grid; missing display frame33 at1.1011s reproduces with every curve command removed')
            record['cases'].append(case);save()
            if name!='fractional-offset':assert case['ok'],name
        record.update(status='completed-with-known-CFR-01-gap',accepted_cases=2,unaccepted_cases=1,cli_calls=sum(x['cli'] for x in record['calls']))
    except BaseException as exc:
        record.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)});raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        record['frozen_equal']=record['frozen_before']==record['frozen_after'];save()
    assert record['frozen_equal']
    print(json.dumps({'status':record['status'],'cli_calls':record['cli_calls'],'cases':len(record['cases']),'frozen_equal':record['frozen_equal']}))


if __name__=='__main__':main()
