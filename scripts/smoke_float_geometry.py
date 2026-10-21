"""Actual original/affine float media and independently checked animation frames."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np
from PIL import Image
from run_frozen_regression import frozen, sha

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'
ASSETS=ROOT/'docs/assets/color-precision-20261021-lab'
WIDTH,HEIGHT,FRAMES,FPS=160,96,20,10

def scalar_reference(source,matrix):
    result=np.zeros_like(source)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            sx=matrix[0][0]*x+matrix[0][1]*y+matrix[0][2]
            sy=matrix[1][0]*x+matrix[1][1]*y+matrix[1][2]
            rgb=np.zeros(3);alpha=0.
            for yy in (math.floor(sy),math.floor(sy)+1):
                for xx in (math.floor(sx),math.floor(sx)+1):
                    if not (0<=xx<WIDTH and 0<=yy<HEIGHT):continue
                    weight=(1-abs(sx-xx))*(1-abs(sy-yy))
                    a=float(source[yy,xx,3]);rgb+=source[yy,xx,:3].astype(np.float64)*a*weight;alpha+=a*weight
            result[y,x,3]=alpha
            if alpha>0:result[y,x,:3]=rgb/alpha
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision',required=True);args=parser.parse_args()
    evidence=REL/('geometry-media-'+args.revision);assets=ASSETS/('geometry-media-'+args.revision)
    assert not evidence.exists() and not assets.exists()
    evidence.mkdir(parents=True);assets.mkdir(parents=True)
    before=frozen();assert len(before)==271
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_before':before,'script_sha256':sha(Path(__file__)),'checks':[],'calls':[],'frames':[],
        'native_windows':True,'virtualization':False,'network':False,'editor_integrated':False,
        'HDR_accepted':False,'natural_quality_accepted':False,'full_capcut_parity':False,
        'rights':'Original generated high-precision RGB/alpha geometry. CC0-1.0; no external images/fonts/models.'}
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,condition,**details):
        record['checks'].append({'name':name,'ok':bool(condition),**details});save();assert condition,name
    ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
    record.update(ffmpeg={'path':ffmpeg,'sha256':sha(Path(ffmpeg))},ffprobe={'path':ffprobe,'sha256':sha(Path(ffprobe))})
    env=dict(os.environ,TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),
        TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1')
    def run(label,command,*,binary=False):
        command=list(map(str,command));start=time.monotonic()
        p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        (evidence/(label+'.stderr.log')).write_bytes(p.stderr)
        if not binary:(evidence/(label+'.stdout.log')).write_bytes(p.stdout)
        record['calls'].append({'label':label,'command':command,'exit_code':p.returncode,'wall_seconds':time.monotonic()-start,
            'output_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),'output_bytes':len(p.stdout)});save()
        assert p.returncode==0,(label,p.stderr[-2500:].decode('utf8','replace'))
        return p.stdout,p.stderr.decode('utf8','replace')
    sys.path.insert(0,str(ROOT/'product/src'))
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    from ai_ad_editor.float_geometry import resample_rgba
    from ai_ad_editor.float_raster import FloatRasterGraph
    try:
        y,x=np.indices((HEIGHT,WIDTH));original=[];warped=[]
        for frame in range(FRAMES):
            red=((x*397+y*11+frame*59)%65536)/65535
            green=((y*683+x*13+frame*131)%65536)/65535
            blue=((x*37+y*167+frame*257)%65536)/65535
            alpha=np.clip(np.minimum.reduce((x/10,(WIDTH-1-x)/10,y/10,(HEIGHT-1-y)/10)),0,1)
            alpha*=np.where(((x//16+y//16)%2)==0,.38,.93)
            rgba=np.stack((red,green,blue,alpha),axis=-1).astype(np.float32)
            t=frame/(FRAMES-1);angle=math.radians(-12+24*t);zoom=.82+.18*t
            cosine,sine=math.cos(angle)/zoom,math.sin(angle)/zoom
            cx,cy=(WIDTH-1)/2,(HEIGHT-1)/2;tx=8*math.sin(t*math.pi*2);ty=5*math.cos(t*math.pi*2)
            matrix=[[cosine,sine,cx-cosine*(cx+tx)-sine*(cy+ty)],
                [-sine,cosine,cy+sine*(cx+tx)-cosine*(cy+ty)]]
            value,metadata=resample_rgba(rgba,(WIDTH,HEIGHT),matrix,tile_pixels=997)
            original.append(rgba);warped.append(value)
            row={'frame':frame,'PTS':str(frame)+'/'+str(FPS),'inverse':matrix,'geometry_metadata':metadata,
                'original_RGBA_float_sha256':'sha256:'+hashlib.sha256(rgba.tobytes()).hexdigest(),
                'actual_RGBA_float_sha256':'sha256:'+hashlib.sha256(value.tobytes()).hexdigest()}
            if frame in (0,9,19):
                truth=scalar_reference(rgba,matrix);error=float(np.max(np.abs(value.astype(np.float64)-truth)))
                row.update(independent_all_pixel_reference_sha256='sha256:'+hashlib.sha256(truth.tobytes()).hexdigest(),
                    independent_maximum_absolute_error=error)
                check('frame-'+str(frame)+'-all-RGBA-values-match-independent-scalar',error<=1e-7,compared_channels=int(truth.size),maximum_error=error)
            record['frames'].append(row);save()
        original=np.stack(original);warped=np.stack(warped)
        background=np.zeros_like(original);background[...,:3]=.08;background[...,3]=1
        back=assets/'background.gbrapf32le';back.write_bytes(np.moveaxis(background[...,[1,2,0,3]],-1,1).tobytes())
        for name,rgba in [('original',original),('affine',warped)]:
            source=assets/(name+'.gbrapf32le');source.write_bytes(np.moveaxis(rgba[...,[1,2,0,3]],-1,1).tobytes())
            graph=FloatRasterGraph();target=graph.source_over('0:v','1:v')
            command=[ffmpeg,'-v','verbose','-filter_complex_threads','1']
            for path in (back,source):command+=['-f','rawvideo','-pixel_format','gbrapf32le','-video_size',f'{WIDTH}x{HEIGHT}',
                '-framerate',FPS,'-i',path]
            raw,stderr=run(name+'-actual-float-composition',[*command,'-filter_complex',graph.graph(),'-map','['+target+']',
                '-pix_fmt','gbrapf32le','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
            actual=np.moveaxis(np.frombuffer(raw,dtype='<f4').reshape(FRAMES,4,HEIGHT,WIDTH)[:,[2,0,1,3]],1,-1)
            expected=rgba[...,:3].astype(np.float64)*rgba[...,3:4]+background[...,:3]*(1-rgba[...,3:4])
            error=float(np.max(np.abs(actual[...,:3].astype(np.float64)-expected)))
            check(name+'-all-composited-RGB-channels-independent-over',error<=1e-7 and np.all(actual[...,3]==1),
                compared_RGB_channels=int(expected.size),maximum_error=error)
            check(name+'-no-auto-quantization-in-native-float-graph','auto-inserting filter' not in stderr)
            rgb=assets/(name+'-composite.gbrpf32le')
            rgb.write_bytes(np.moveaxis(actual[...,[1,2,0]],-1,1).tobytes())
            lossless=assets/(name+'-composite-16bit.mkv')
            run(name+'-native-16bit-export',[ffmpeg,'-v','error','-f','rawvideo','-pixel_format','gbrpf32le',
                '-video_size',f'{WIDTH}x{HEIGHT}','-framerate',FPS,'-i',rgb,'-vf',
                'zscale=rangein=full:range=full:dither=none,format=gbrp16le','-c:v','ffv1','-level','3',lossless])
            raw,unused=run(name+'-16bit-all-codes-decoded',[ffmpeg,'-v','error','-i',lossless,'-pix_fmt','gbrp16le',
                '-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
            integer=np.frombuffer(raw,dtype='<u2').reshape(FRAMES,3,HEIGHT,WIDTH)
            expected_integer=np.rint(np.clip(np.moveaxis(actual[...,[1,2,0]],-1,1),0,1).astype(np.float64)*65535).astype('<u2')
            maximum=int(np.max(np.abs(integer.astype(np.int32)-expected_integer.astype(np.int32))))
            check(name+'-16bit-quantization-within-one-code',maximum<=1,compared_channels=int(integer.size),maximum_code_error=maximum)
            browser=assets/(name+'.mp4')
            run(name+'-native-browser-export',[ffmpeg,'-v','error','-i',lossless,'-c:v','libx264','-crf','10','-pix_fmt','yuv444p10le',browser])
            raw,unused=run(name+'-native-every-frame-probe',[ffprobe,'-v','error','-show_frames','-select_streams','v:0',
                '-show_entries','frame=best_effort_timestamp_time,pix_fmt,width,height','-of','json',browser])
            frames=json.loads(raw)['frames']
            check(name+'-all-MP4-frame-PTS-and-size',len(frames)==FRAMES and all(abs(float(f['best_effort_timestamp_time'])-i/FPS)<1e-9
                and int(f['width'])==WIDTH and int(f['height'])==HEIGHT for i,f in enumerate(frames)),frames=len(frames))
            gif=assets/(name+'.gif')
            run(name+'-native-GIF-from-actual-output',[ffmpeg,'-v','error','-i',browser,'-vf',
                'split[a][b];[a]palettegen[p];[b][p]paletteuse',gif])
            with Image.open(gif) as image:
                durations=[]
                for i in range(image.n_frames):image.seek(i);durations.append(image.info.get('duration',0))
                check(name+'-all-GIF-frames-and-native-duration',image.n_frames==FRAMES and durations==[100]*FRAMES,
                    frames=image.n_frames,frame_durations_ms=durations)
            run(name+'-actual-MP4-first-frame',[ffmpeg,'-v','error','-i',browser,'-frames:v','1',assets/(name+'-frame0.png')])
        record.update(status='passed-native-float-geometry-media-not-editor-integration',native_commands=len(record['calls']))
    except BaseException as error:record.update(status='failed-preserved',error=repr(error));raise
    finally:
        record.update(frozen_after=frozen(),finished_at_utc=datetime.now(timezone.utc).isoformat())
        record['source_unchanged']=record['frozen_before']==record['frozen_after']
        record['assets']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(assets.rglob('*')) if p.is_file()}
        save();(evidence/'executed-smoke.py.txt').write_bytes(Path(__file__).read_bytes())
    assert record['source_unchanged'];print(json.dumps({'status':record['status'],'commands':record['native_commands'],
        'checks':len(record['checks']),'frames':len(record['frames']),'assets':len(record['assets'])}))

if __name__=='__main__':main()
