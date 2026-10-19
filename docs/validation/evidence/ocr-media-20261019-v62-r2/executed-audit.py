"""Independently audit real OCR camera encodes, glyph geometry, PTS and PCM."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
W,H,FPS,SR=640,360,8,48000


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def edit_distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        next_row=[i]
        for j,y in enumerate(b,1):next_row.append(min(next_row[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=next_row
    return row[-1]


def glyphs(image,region,dark=False):
    x0,y0,x1,y1=map(int,region);crop=image[y0:y1,x0:x1]
    mask=np.max(crop,axis=2)<100 if dark else np.min(crop,axis=2)>180
    ys,xs=np.nonzero(mask)
    if not len(xs):raise ValueError('independent target glyph region is empty')
    return xs+x0,ys+y0,[int(xs.min()+x0),int(ys.min()+y0),int(xs.max()+x0+1),int(ys.max()+y0+1)]


def box_geometry(image,region,box,dark=False):
    xs,ys,bounds=glyphs(image,region,dark)
    coverage=Image.new('1',(image.shape[1],image.shape[0]));ImageDraw.Draw(coverage).polygon([tuple(p) for p in box['polygon']],fill=1)
    ratio=float(np.asarray(coverage)[ys,xs].mean())
    polygon=np.asarray(box['polygon']);center=(polygon.min(axis=0)+polygon.max(axis=0))/2
    target=np.array([(bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2])
    error=float(np.max(np.abs(center-target)))
    if ratio<.8 or error>12:raise ValueError(f'OCR target geometry failed: coverage={ratio},center={error}')
    return {'glyph_bbox':bounds,'glyph_pixels':len(xs),'glyph_coverage':ratio,'center_max_axis_error_px':error,
            'recognized_text':box['text'],'recognized_polygon':box['polygon']}


def run(english,chinese,output):
    output.mkdir(parents=True,exist_ok=False);shutil.copyfile(Path(__file__),output/'executed-audit.py')
    before=frozen();calls=[];files={}
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,
            'generator_sha256':sha(Path(__file__)),'calls':calls,'natural_quality_accepted':False,
            'continuous_playback_or_listening':False,'targets_selected_after_development_scan':True,
            'geometry_truth':'independent authored page control regions and original glyph pixels; no OCR bbox supplied to native model'}
    def command(args):
        args=list(map(str,args));p=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=240)
        stem=f'{len(calls)+1:03d}';gz=len(p.stdout)>65536
        out=output/(stem+('.stdout.gz' if gz else '.stdout'));err=output/(stem+'.stderr')
        out.write_bytes(gzip.compress(p.stdout,mtime=0) if gz else p.stdout);err.write_bytes(p.stderr)
        calls.append({'command':args,'exit_code':p.returncode,'stdout':out.name,'stderr':err.name,
            'stdout_sha256':sha(out),'stderr_sha256':sha(err),'stdout_decoded_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),
            'stdout_decoded_bytes':len(p.stdout),'stdout_compressed':gz});save(output/'verification.json',record)
        if p.returncode:raise ValueError(p.stderr.decode('utf-8','replace')[-2000:])
        return p.stdout
    def video(path):
        return np.frombuffer(command(['ffmpeg','-nostdin','-v','error','-i',path,'-map','0:v:0','-an','-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1']),np.uint8).reshape(-1,H,W,3)
    def audio(path):
        return np.frombuffer(command(['ffmpeg','-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-ar',SR,'-ac','2','-f','f32le','pipe:1']),'<f4').reshape(-1,2)
    def pts(path):
        v=json.loads(command(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',path]))
        values=[float(f['best_effort_timestamp_time']) for f in v['frames']]
        if len(values)!=48 or max(abs(t-i/FPS) for i,t in enumerate(values))>1e-6:raise ValueError('encoded source clock mismatch')
        return {'frames':len(values),'fps':FPS,'last_pts':values[-1]}
    def bind(path):files[path.relative_to(ROOT).as_posix()]={'sha256':sha(path),'bytes':path.stat().st_size}
    try:
        for folder in (english,chinese):
            receipt=json.loads((folder/'verification.json').read_bytes())
            if receipt['status']!='passed_native_scan' or not receipt['frozen_equal'] or receipt['frozen_after']!=before:raise ValueError('native scan did not qualify against current product')
            for c in receipt['calls']:
                if c['exit_code']!=c['expected_exit_code'] or sha(folder/c['stdout'])!=c['stdout_sha256'] or sha(folder/c['stderr'])!=c['stderr_sha256']:raise ValueError('native log/hash mismatch')
            bind(folder/'verification.json');bind(folder/'ocr-report.json')
        source=english/'original-screen.mkv'
        original=video(source);source_pcm=audio(source);source_pts=pts(source);bind(source)
        if original.shape!=(48,H,W,3) or source_pcm.shape!=(288000,2):raise ValueError('original source dimensions changed')
        report=json.loads((english/'ocr-report.json').read_bytes());targets=[];checks=[];contacts=[];home_checks=0;active_checks=0;pcm_frames=0
        regions={'select':(38,136,246,176),'preview':(38,240,246,280),'save':(296,200,602,240),'result':(296,136,602,186)}
        for name,query,index in (('select','Select local campaign',0),('preview','Preview headline',8),('save','Save plan in this page',0),('result','Plan saved locally in page state.',32)):
            matches=[b for f in report['frames'] if f['frame_index']==index for b in f['boxes'] if b['text']==query]
            if len(matches)!=1:raise ValueError('exact target not uniquely recognized')
            box=matches[0];truth=box_geometry(original[index],regions[name],box)
            targets.append({'name':name,'query':query,'source_frame':index,**truth})
            path=english/(name+'.mkv');frames=video(path);pcm=audio(path);clock=pts(path);bind(path)
            if frames.shape!=original.shape or pcm.shape!=source_pcm.shape or not np.array_equal(pcm,source_pcm):raise ValueError('final frames/audio changed beyond contract')
            pcm_frames+=len(pcm);active=[];home=[]
            # Independent camera equation: original pixels scaled around canvas
            # center, then translated. Quadratic ease-out return from 0.5s to 1s.
            polygon=np.asarray(box['polygon']);center=(polygon.min(axis=0)+polygon.max(axis=0))/2
            focused=np.clip(np.array([W/2,H/2])+1.5*(np.array([W/2,H/2])-center),np.array([W,H])*.25,np.array([W,H])*.75)
            for n,current in enumerate(frames):
                if index<=n<index+8:
                    t=(n-index)/FPS;fraction=0 if t<=.5 else 1-(1-(t-.5)/.5)**2
                    scale=1.5-.5*fraction;position=focused+(np.array([W/2,H/2])-focused)*fraction
                    bb=np.array(truth['glyph_bbox'],float).reshape(2,2)
                    predicted=(bb-np.array([W/2,H/2]))*scale+position
                    region=[max(0,int(np.floor(predicted[0,0]-10))),max(0,int(np.floor(predicted[0,1]-10))),
                            min(W,int(np.ceil(predicted[1,0]+10))),min(H,int(np.ceil(predicted[1,1]+10)))]
                    _,_,actual=glyphs(current,region)
                    error=float(np.max(np.abs(np.asarray(actual).reshape(2,2)-predicted)))
                    if error>5:raise ValueError(f'encoded glyph projection failed: {name} frame {n}: {error}')
                    active.append({'frame':n,'scale':scale,'predicted_edges':predicted.reshape(-1).tolist(),'encoded_glyph_edges':actual,'edge_max_error_px':error})
                else:
                    error=int(np.abs(current.astype(np.int16)-original[n].astype(np.int16)).max())
                    if error>3:raise ValueError(f'full-view RGB failed: {name} frame {n}: {error}')
                    home.append({'frame':n,'max_rgb_error':error})
            active_checks+=len(active);home_checks+=len(home)
            package=english/(name+'.aevpkg.zip');bind(package)
            with zipfile.ZipFile(package) as archive:
                project_names=[p for p in archive.namelist() if p.endswith('project.json')]
                if len(project_names)!=1:raise ValueError('package project is not unique')
                project=json.loads(archive.read(project_names[0]));clip=next(c for s in project['sequences'] for t in s['tracks'] for c in t['clips'] if c['id']=='screen')
                if {k['property'] for k in clip['keyframes']}!={'transform.position.x','transform.position.y','transform.scale'} or not any(p.endswith('validation/text.json') for p in archive.namelist()):raise ValueError('package lost editable camera or OCR report')
            checks.append({'name':name,'clock':clock,'active_frames':active,'full_view_frames':home,'pcm_max_error':0.,'pcm_sample_frames':len(pcm),'package_editable_and_report_retained':True})
            contacts.append((name,original[index],frames[index],frames[index+8]))
            for suffix in ('.mp4','.gif','.anchor.json','.render-manifest.json'):bind(english/(name+suffix))
        raw_expected=['LOCAL CAMPAIGN PLANNER','CONTROLLED ORIGINAL TEST APP / NO EDITOR GUI CLAIM','1. Configure a plan',
                      '2. Review the result','Select local campaign','No campaign selected.','DRAFT','Save plan in this page',
                      'Preview headline','All fields are fixture data. Nothing is sent or downloaded.']
        recognized=report['frames'][0]['boxes']
        if len(recognized)!=len(raw_expected):raise ValueError('frame-zero line count changed; align explicitly for reporting')
        lines=[{'expected':a,'raw_recognized':b['text'],'exact':a==b['text'],'edit_distance':edit_distance(a,b['text'])} for a,b in zip(raw_expected,recognized)]
        line_summary={'scope':'all 10 authored frame-zero lines including failures; not a held-out benchmark','lines':lines,
            'exact_lines':sum(x['exact'] for x in lines),'expected_characters':sum(len(x) for x in raw_expected),
            'character_edits':sum(x['edit_distance'] for x in lines)}
        chinese_report=json.loads((chinese/'ocr-report.json').read_bytes());expect=json.loads((chinese/'expected-chinese.json').read_bytes())
        image=np.asarray(Image.open(chinese/'original-chinese.png').convert('RGB'));chinese_targets=[]
        for truth in expect['targets']:
            matches=[b for b in chinese_report['frames'][0]['boxes'] if b['text']==truth['text']]
            if len(matches)!=1:raise ValueError('Chinese exact text failed: '+truth['text'])
            bb=truth['glyph_bbox'];region=[max(0,int(bb[0])-2),max(0,int(bb[1])-2),min(960,int(bb[2])+2),min(540,int(bb[3])+2)]
            chinese_targets.append({'expected':truth['text'],'authored_font_bbox':bb,**box_geometry(image,region,matches[0],dark=True)})
        for name in ('original-chinese.png','expected-chinese.json'):bind(chinese/name)
        font=ImageFont.truetype(str(ROOT/'docs/assets/openfilm-workflow-screen-20261019-v61-r3/DejaVuSans.ttf'),17)
        contact=Image.new('RGB',(W*3,(H+32)*4))
        for row,(name,*images) in enumerate(contacts):
            for col,(label,img) in enumerate(zip(('ORIGINAL','OCR CAMERA','RETURNED FULL VIEW'),images)):
                contact.paste(Image.fromarray(img),(col*W,row*(H+32)+32));ImageDraw.Draw(contact).text((col*W+12,row*(H+32)+5),name.upper()+' / '+label,font=font,fill='white')
        contact.save(output/'source-focus-return-contact.png');bind(output/'source-focus-return-contact.png')
        record.update(status='passed_independent_controlled_ocr_media_checks',english_targets=targets,chinese_targets=chinese_targets,
            camera_checks=checks,english_all_frame_zero_lines=line_summary,final_video_frames=48*len(checks),
            encoded_geometry_frames=active_checks,full_view_frames=home_checks,stereo_pcm_sample_frames=pcm_frames,
            source_clock=source_pts,neural_forwards={'english':{k:report['response'][k] for k in ('detector_forwards','recognizer_forwards')},
            'chinese':{k:chinese_report['response'][k] for k in ('detector_forwards','recognizer_forwards')}},files=files)
    except BaseException as exc:
        record.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
    finally:
        after=frozen();record.update(frozen_after=after,frozen_equal=after==before,finished_at_utc=datetime.now(timezone.utc).isoformat());save(output/'verification.json',record)
    if not record['frozen_equal']:raise ValueError('product inputs changed')
    print(json.dumps({k:record[k] for k in ('status','final_video_frames','encoded_geometry_frames','full_view_frames','stereo_pcm_sample_frames')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('english','chinese','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.english.resolve(),a.chinese.resolve(),a.output.resolve())
