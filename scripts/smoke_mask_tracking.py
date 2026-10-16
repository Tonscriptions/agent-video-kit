"""Render and independently measure an authored mask-to-anchor/reframe fixture."""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.cli import main
from ai_ad_editor.runtime import configure_local_runtime


def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def execute(argv, data=None):
    result = subprocess.run(argv, input=data, capture_output=True, timeout=180)
    if result.returncode: raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
    return result.stdout


def run(output, work):
    configure_local_runtime()
    from PIL import Image, ImageDraw, ImageFont, ImageSequence
    import PIL
    import numpy as np
    if work.exists(): raise ValueError('Use a fresh work directory; existing projects are never removed')
    work.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)
    project = work/'project'; calls=[]

    def cli(*argv, expected_code=0):
        stream = io.StringIO(); began=time.monotonic()
        with contextlib.redirect_stdout(stream): code=main(list(map(str,argv)))
        result=json.loads(stream.getvalue())
        calls.append({'argv':list(map(str,argv)), 'exit_code':code, 'seconds':time.monotonic()-began, 'result':result})
        save(work/'partial-calls.json',calls)
        assert code == expected_code, result
        return result

    def compose(operations):
        path=work/'changes.json'; save(path,{'operations':operations})
        return cli('timeline','compose','--project',project,'--input',path)

    sources=[]; masks=[]; truth=[]
    for index in range(64):
        x=68+round(184*index/63)+round(5*math.sin(index*math.pi/21))
        y=92+round(8*math.sin(index*math.pi/31.5))
        selection=Image.new('L',(320,180),0); d=ImageDraw.Draw(selection)
        d.rounded_rectangle((x-20,y-36,x+19,y+43),radius=7,fill=255)
        d.rectangle((x-10,y-50,x+9,y-35),fill=255)
        source=Image.new('RGB',(640,360),'#122338'); sd=ImageDraw.Draw(source)
        for gx in range(0,640,40): sd.line((gx,0,gx,359),fill='#1d354c')
        for gy in range(0,360,40): sd.line((0,gy,639,gy),fill='#1d354c')
        source.paste('#48cdb6',mask=selection.resize((640,360),Image.Resampling.NEAREST))
        sd.rectangle((2*x-20,2*y-100,2*x+19,2*y-72),fill='#efc66a')
        sd.rounded_rectangle((2*x-30,2*y-28,2*x+29,2*y+24),radius=6,fill='#ecf5ed')
        sd.text((2*x-18,2*y-15),'AVK',fill='#183b45',font=ImageFont.load_default(size=20))
        mask=Image.new('RGBA',(320,180),(72,205,182,0)); mask.putalpha(selection)
        sources.append(np.asarray(source).copy()); masks.append(np.asarray(mask).copy())
        # Half-open authored extent, independent of the product's bbox reducer.
        truth.append({'frame':index,'seconds':index/16,'bbox_source_pixels':[2*x-40,2*y-100,2*x+40,2*y+88],
                      'center_source_pixels':[2*x,2*y-6]})
    sources=np.stack(sources); masks=np.stack(masks)
    execute(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','640x360','-r','16','-i','pipe:0','-an',
             '-c:v','libx264','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(output/'source.mp4')],sources.tobytes())
    execute(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgba','-s','320x180','-r','16','-i','pipe:0','-an',
             '-c:v','qtrle','-pix_fmt','argb',str(output/'selected-mask.mov')],masks.tobytes())
    marker=Image.new('RGBA',(64,64),(0,0,0,0)); md=ImageDraw.Draw(marker)
    md.ellipse((8,8,55,55),outline=(255,0,255,255),width=4)
    md.line((0,31,63,31),fill=(255,0,255,255),width=2); md.line((31,0,31,63),fill=(255,0,255,255),width=2)
    marker.save(output/'marker.png')
    save(output/'truth.json',{'license_spdx':'CC0-1.0','kind':'authored-half-open-pixel-geometry','frames':truth})
    provenance=output/'fixture-provenance.json'
    save(provenance,{'kind':'procedural-mask-tracking-fixture','generator':'scripts/smoke_mask_tracking.py','generator_sha256':sha(Path(__file__)),
        'license_spdx':'CC0-1.0','learned_model_runs':0,'natural_segmentation_accuracy_claim':False,
        'purpose':'Measure geometry and actual rendered marker positions; selection is authored, not inferred.',
        'source_clock':'64 frames at 16/1 fps, 4 seconds, source 640x360 and matching-aspect half-size mask 320x180',
        'audio':'none; this fixture tests visual geometry only','raster_text':'Pillow built-in default; no font file distributed',
        'inputs':{name:sha(output/name) for name in ['source.mp4','selected-mask.mov','marker.png','truth.json']}})
    cli('project','init',project,'--name','Encoded mask to source-clock anchor and portrait')
    for asset,name in [('source','source.mp4'),('mask','selected-mask.mov'),('marker','marker.png')]:
        cli('media','ingest','--project',project,'--input',output/name,'--asset-id',asset,'--source-url','local://authored-mask-tracking-fixture',
            '--license-spdx','CC0-1.0','--evidence',provenance,'--verification-status','verified','--permitted-use','commercial_ad')
    value=json.loads((project/'project.json').read_text(encoding='utf-8-sig'))
    value['settings']['canvas'].update(width=640,height=360)
    value['settings']['timebase']['display_fps']={'num':16,'den':1}
    save(project/'project.json',value)
    compose([{'op':'append_clip','track_id':'track_video_1','id':'product','asset_id':'source','source_in_tick':0,'source_out_tick':360000},
             {'op':'add_track','track_id':'labels','kind':'video','order':3},
             {'op':'append_clip','track_id':'labels','id':'marker_label','asset_id':'marker','source_in_tick':0,'source_out_tick':360000,'duration_tick':360000,'transform':{'scale':.12}}])
    report=cli('media','track','--project',project,'--asset-id','source','--mask-asset-id','mask','--step-frames','1','--output','validation/mask-track.json')
    frames=report['data']['result']['frames']; assert len(frames)==65
    for actual,expected in zip(frames,truth):
        assert abs(actual['x']*640-expected['center_source_pixels'][0]) < 1e-9
        assert abs(actual['y']*360-expected['center_source_pixels'][1]) < 1e-9
    save(output/'mask-track-report.json',json.loads((project/'validation/mask-track.json').read_text(encoding='utf-8-sig')))
    binding=cli('media','track-bind','--project',project,'--asset-id','source','--mask-asset-id','mask','--step-frames','1',
        '--source-track-id','track_video_1','--source-clip-id','product','--target-track-id','labels','--target-clip-id','marker_label','--apply','--output','validation/mask-binding.json')
    save(output/'binding-report.json',json.loads((project/'validation/mask-binding.json').read_text(encoding='utf-8-sig')))

    def render(name,width,height):
        local=project/'renders'/name
        response=cli('render','--project',project,'--output',local,'--width',width,'--height',height,'--publish')
        (output/name).write_bytes(local.read_bytes())
        return response

    render('bound.mp4',640,360)
    compose([{'op':'update_clip','track_id':'track_video_1','clip_id':'product','patch':{'transform':{'scale':.78,'rotation':15,'position':{'x':.52,'y':.48}}}}])
    render('bound-transformed.mp4',640,360)
    compose([{'op':'update_clip','track_id':'track_video_1','clip_id':'product','patch':{'transform':{'scale':1,'rotation':0}}}])
    reframe=cli('media','reframe','--project',project,'--asset-id','source','--mask-asset-id','mask','--step-frames','1',
        '--track-id','track_video_1','--clip-id','product','--target-width','360','--target-height','640','--apply','--output','validation/mask-reframe.json')
    assert reframe['data']['plan']['clipped_frame_count']==0
    save(output/'reframe-report.json',json.loads((project/'validation/mask-reframe.json').read_text(encoding='utf-8-sig')))
    render('portrait.mp4',360,640)
    package=work/'portable.zip'; portable=work/'portable'
    cli('convert','export','--project',project,'--target-format','package','--output',package)
    cli('convert','import','--input',package,'--output',portable)
    cli('validate','--project',portable)
    copy=json.loads((portable/'project.json').read_text(encoding='utf-8-sig'))
    label=next(t for t in copy['sequences'][0]['tracks'] if t['id']=='labels')['clips'][0]
    assert {r['rights_ref'] for r in label['rights_dependencies']}=={'source','mask'}
    assert len(label['tracking_binding']['observations'])==65

    def decode(name,width,height):
        raw=execute(['ffmpeg','-v','error','-protocol_whitelist','file,pipe','-i',str(output/name),'-map','0:v:0','-an','-fps_mode','passthrough',
                     '-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
        array=np.frombuffer(raw,np.uint8).reshape(-1,height,width,3)
        assert len(array)==64
        return array

    decoded={name:decode(name,w,h) for name,w,h in [('source.mp4',640,360),('bound.mp4',640,360),('bound-transformed.mp4',640,360),('portrait.mp4',360,640)]}
    padding_errors=[]
    for index,row in enumerate(truth):
        x,y=row['center_source_pixels']
        for offset in [-30,30]:
            source=decoded['source.mp4'][index,y-1:y+2,x+offset-1:x+offset+2].astype(np.int16)
            actual=decoded['bound.mp4'][index,y-1:y+2,x+offset-1:x+offset+2].astype(np.int16)
            padding_errors.append(float(np.abs(actual-source).mean()))
    assert max(padding_errors) <= 20.,max(padding_errors)
    measurements={}
    for name in ['bound.mp4','bound-transformed.mp4','portrait.mp4']:
        rows=[]
        for index,array in enumerate(decoded[name]):
            selected=(array[:,:,0]>180)&(array[:,:,1]<95)&(array[:,:,2]>165)
            ys,xs=np.nonzero(selected); assert len(xs)>20,(name,index)
            observed=[float(xs.mean()),float(ys.mean())]; x,y=truth[index]['center_source_pixels']
            if name=='bound-transformed.mp4':
                dx,dy=(x-320)*.78,(y-180)*.78; angle=math.radians(15)
                expected=[.52*640+dx*math.cos(angle)-dy*math.sin(angle),.48*360+dx*math.sin(angle)+dy*math.cos(angle)]
            elif name=='portrait.mp4':
                # Animated crop size uses continuous source geometry; rounding is to six normalized decimals.
                crop_x=round(x/640-(360/640)/(640/360)/2,6)*640
                expected=[(x-crop_x)*(640/360),y*(640/360)]
            else: expected=[x,y]
            error=math.hypot(observed[0]-expected[0],observed[1]-expected[1])
            rows.append({'frame':index,'observed_center':observed,'expected_center':expected,'euclidean_error_pixels':error})
        maximum=max(r['euclidean_error_pixels'] for r in rows)
        assert maximum <= 3.,(name,maximum)
        measurements[name]={'frames_measured':64,'tolerance_pixels':3.,'max_error_pixels':maximum,
                            'mean_error_pixels':sum(r['euclidean_error_pixels'] for r in rows)/64,'rows':rows}
    preview=[]
    for index in range(64):
        image=Image.new('RGB',(1088,248),'#101c2a'); d=ImageDraw.Draw(image)
        for x,name,title,size in [(4,'source.mp4','ORIGINAL',(320,180)),(328,'bound.mp4','MASK -> ANCHOR',(320,180)),
                                  (652,'bound-transformed.mp4','SCALE + ROTATE',(320,180)),(980,'portrait.mp4','PORTRAIT',(101,180))]:
            image.paste(Image.fromarray(decoded[name][index]).resize(size,Image.Resampling.LANCZOS),(x,30))
            d.text((x,7),title,fill='white',font=ImageFont.load_default(size=14))
        d.text((8,218),f'FRAME {index:02d}/63 | 16 FPS | AUTHORED MASK / NO LEARNED MODEL | ACTUAL CLI RENDERS',fill='#bbccdd',font=ImageFont.load_default(size=13))
        preview.append(np.asarray(image))
    execute(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1088x248','-r','16','-i','pipe:0','-an',
             '-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(output/'mask-tracking-comparison.mp4')],np.stack(preview).tobytes())
    images=[Image.fromarray(frame).quantize(colors=96) for frame in preview[::2]]
    images[0].save(output/'mask-tracking-comparison.gif',save_all=True,append_images=images[1:],duration=[120,130]*16,loop=0,disposal=2,optimize=False)
    Image.fromarray(preview[32]).save(output/'contact-frame-32.png')
    with Image.open(output/'mask-tracking-comparison.gif') as handle:
        durations=[frame.info['duration'] for frame in ImageSequence.Iterator(handle)]
        assert len(durations)==32 and sum(durations)==4000
    probes={}
    for name in ['source.mp4','selected-mask.mov','bound.mp4','bound-transformed.mp4','portrait.mp4','mask-tracking-comparison.mp4']:
        probe=json.loads(execute(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(output/name)]))
        assert probe['streams'][0]['nb_read_frames']=='64' and probe['streams'][0]['avg_frame_rate']=='16/1'
        probes[name]=probe
    comparison=decode('mask-tracking-comparison.mp4',1088,248)
    save(output/'evidence.json',{'checked_at_utc':datetime.now(timezone.utc).isoformat(),'generator_sha256':sha(Path(__file__)),
        'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'product/src/ai_ad_editor').glob('*.py'))},
        'calls':calls,'mask_observations':65,'encoded_frames_per_video':64,'source_seconds':4.,'source_fps':'16/1',
        'half_size_mask_bbox_matches_authored_truth':True,'marker_measurements':measurements,'probes':probes,
        'transparent_padding':{'patches_checked':128,'max_mean_absolute_rgb_error':max(padding_errors),'tolerance':20.,'passed':True,
                               'method':'Independent 3x3 original/render patches on both sides outside the square alpha marker; all 64 frames'},
        'persistent_binding_survives_project_package':True,'publish_gate_passed_for_self_authored_CC0_fixture_only':True,
        'preview':{'mp4_all_frames_decoded':len(comparison)==64,'gif_frames':32,'gif_total_ms':4000,'gif_durations_ms':sorted(set(durations))},
        'numpy_and_pillow_demo_only':{'numpy':np.__version__,'pillow':PIL.__version__},'learned_model_runs':0,
        'natural_segmentation_quality_accepted':False,'continuous_natural_video_review':False,'audio_tested':False,
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file() and p.name!='evidence.json'}})
    print(json.dumps({'output':str(output),'actual_cli_calls':len(calls),'marker_max_errors':{k:v['max_error_pixels'] for k,v in measurements.items()}},ensure_ascii=False),flush=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True); parser.add_argument('--work-dir',type=Path,required=True)
    args=parser.parse_args(); run(args.output_dir.resolve(),args.work_dir.resolve())
