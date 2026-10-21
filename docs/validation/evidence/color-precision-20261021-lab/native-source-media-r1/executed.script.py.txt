"""Actual native RGB/YUV readers, affine animation and float compositing media.

This is an independent pipeline, not the editor timeline/preview backend.
"""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib,json,math,os
from pathlib import Path
import shutil,subprocess,sys,time
import numpy as np
from PIL import Image
from run_frozen_regression import frozen,sha
from smoke_float_geometry import scalar_reference

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'
ASSETS=ROOT/'docs/assets/color-precision-20261021-lab'
W,H,N,FPS=160,96,20,10

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision',required=True);args=parser.parse_args()
    evidence=REL/('native-source-media-'+args.revision);assets=ASSETS/('native-source-media-'+args.revision)
    assert not evidence.exists() and not assets.exists();evidence.mkdir(parents=True);assets.mkdir(parents=True)
    before=frozen();assert len(before)==278
    kernel=json.loads((REL/'kernel-r8.json').read_bytes())
    assert kernel['status']=='passed-native-float-kernel-unit-only' and kernel['frozen_after']==before
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_before':before,
        'script_sha256':sha(Path(__file__)),'independent_geometry_reference_script_sha256':sha(Path(__file__).with_name('smoke_float_geometry.py')),
        'calls':[],'reader_executions':[],'checks':[],'frames':[],'native_windows':True,'virtualization':False,'network':False,
        'editor_integrated':False,'timeline_CLI_after':False,'HDR_accepted':False,'natural_quality_accepted':False,
        'continuous_playback_reviewed':False,'full_capcut_parity':False,
        'working_colour_contract':{'primaries':'bt709','transfer':'bt709-source-nonlinear','linear_light':False,
            'source_tags_or_assumptions':'Both generated sources authored with this contract; YUV full matrix bt709 explicitly supplied.'},
        'rights':'Original procedural 16-bit RGB/alpha and YCbCr media. CC0-1.0. No external image, font, audio or model.'}
    ffmpeg,ffprobe=shutil.which('ffmpeg'),shutil.which('ffprobe');assert ffmpeg and ffprobe
    record.update(ffmpeg={'path':ffmpeg,'sha256':sha(Path(ffmpeg))},ffprobe={'path':ffprobe,'sha256':sha(Path(ffprobe))})
    def save():(evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(label,condition,**details):
        record['checks'].append({'label':label,'ok':bool(condition),**details});save();assert condition,label
    env=dict(os.environ,TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),TMPDIR=str(ROOT/'product/.runtime/temp'),PYTHONDONTWRITEBYTECODE='1')
    def run(label,command,*,binary=False):
        command=list(map(str,command));start=time.monotonic();p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        (evidence/(label+'.stderr.log')).write_bytes(p.stderr)
        if not binary:(evidence/(label+'.stdout.log')).write_bytes(p.stdout)
        row={'label':label,'command':command,'exit_code':p.returncode,'wall_seconds':time.monotonic()-start,
            'stdout_bytes':len(p.stdout),'stdout_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':'sha256:'+hashlib.sha256(p.stderr).hexdigest(),
            'automatic_conversions':[line for line in p.stderr.decode('utf8','replace').splitlines() if 'auto-inserting filter' in line]}
        record['calls'].append(row);save();assert p.returncode==0,(label,p.stderr[-2500:].decode('utf8','replace'))
        return p.stdout,p.stderr.decode('utf8','replace')
    sys.path.insert(0,str(ROOT/'product/src'))
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    from ai_ad_editor.float_video_source import NativeRGBSource
    from ai_ad_editor.float_yuv import YUVSpec
    from ai_ad_editor.float_yuv_source import NativeYUVSource
    from ai_ad_editor.float_geometry import resample_rgba
    from ai_ad_editor.float_raster import FloatRasterGraph
    try:
        y,x=np.indices((H,W));rgba_codes=[];yuv_codes=[]
        for frame in range(N):
            red=(x*397+y*11+frame*59)%65536;green=(y*683+x*13+frame*131)%65536;blue=(x*37+y*167+frame*257)%65536
            edge=np.clip(np.minimum.reduce((x/10,(W-1-x)/10,y/10,(H-1-y)/10)),0,1)
            alpha=np.rint(edge*np.where(((x//16+y//16)%2)==0,.38,.93)*65535)
            rgba_codes.append(np.stack((red,green,blue,alpha),-1).astype('<u2'))
            luminance=np.rint((.12+.65*x/(W-1)+.08*y/(H-1))*65535)
            cb=np.full((H,W),round(32768+.04*math.sin(frame*.4)*65535))
            cr=np.full((H,W),round(32768+.04*math.cos(frame*.4)*65535))
            yuv_codes.append(np.stack((luminance,cb,cr)).astype('<u2'))
        rgba_codes=np.stack(rgba_codes);yuv_codes=np.stack(yuv_codes)
        rgbraw=assets/'foreground.gbrap16le';rgbraw.write_bytes(np.moveaxis(rgba_codes[...,[1,2,0,3]],-1,1).tobytes())
        yuvraw=assets/'background.yuv444p16le';yuvraw.write_bytes(yuv_codes.tobytes())
        foreground=assets/'foreground-16bit.mkv';background=assets/'background-16bit.mkv'
        tags=['-color_range','pc','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709']
        run('encode-original-RGBA16',[ffmpeg,'-v','verbose','-f','rawvideo','-pixel_format','gbrap16le','-video_size',f'{W}x{H}','-framerate',FPS,'-i',rgbraw,
            '-c:v','ffv1','-level','3','-pix_fmt','gbrap16le',foreground])
        run('encode-original-YUV16',[ffmpeg,'-v','verbose','-f','rawvideo','-pixel_format','yuv444p16le','-video_size',f'{W}x{H}','-framerate',FPS,*tags,'-i',yuvraw,
            '-c:v','ffv1','-level','3','-pix_fmt','yuv444p16le',*tags,background])
        for label,source,pixel_format,expected in [('RGB',foreground,'gbrap16le',rgbraw.read_bytes()),('YUV',background,'yuv444p16le',yuvraw.read_bytes())]:
            raw,stderr=run('verify-encoded-original-'+label,[ffmpeg,'-v','verbose','-i',source,'-map','0:v:0','-an','-pix_fmt',pixel_format,'-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
            check(label+'-actual-encoded-original-all-native-codes-exact',raw==expected,compared_bytes=len(expected))
            check(label+'-original-encode-and-decode-no-automatic-conversion',not any(row['automatic_conversions'] for row in record['calls'] if row['label'] in ('encode-original-'+('RGBA16' if label=='RGB' else 'YUV16'),'verify-encoded-original-'+label)))
        readers=[('RGB',NativeRGBSource(ROOT,foreground,sha(foreground))),
                 ('YUV',NativeYUVSource(ROOT,background,sha(background),spec=YUVSpec('bt709','full','center'),scan='progressive'))]
        surfaces={}
        for label,reader in readers:
            with reader:
                frames=list(reader)
                check(label+'-all-original-PTS-and-durations',len(frames)==N and all(frame.pts*frame.time_base==Fraction(i,FPS) and frame.duration*frame.time_base==Fraction(1,FPS) for i,frame in enumerate(frames)))
                surfaces[label]=np.stack([f.rgba for f in frames]);metadata=dict(reader.metadata)
            record['reader_executions'].append({'label':label,'command':reader.metadata['command'],'exit_code':reader.pipe.process.poll(),
                'decoded_frames':reader.position,'metadata':metadata,'closed':reader.closed,
                'owned_threads_terminated':all(not thread.is_alive() for thread in reader.pipe.threads)})
            check(label+'-reader-complete-and-closed',reader.complete and reader.closed and reader.pipe.process.poll()==0)
        check('native-RGB-reader-all-RGBA16-codes-preserved',np.array_equal(np.rint(surfaces['RGB'].astype(np.float64)*65535).astype(np.uint16),rgba_codes),compared_channels=int(rgba_codes.size))
        # Independent whole-frame oracle, green solved via the luminance identity.
        for frame in (0,9,19):
            l=yuv_codes[frame,0].astype(np.float64)/65535;cb=(yuv_codes[frame,1].astype(np.float64)-32768)/65535;cr=(yuv_codes[frame,2].astype(np.float64)-32768)/65535
            r=l+1.5748*cr;b=l+1.8556*cb;g=(l-.2126*r-.0722*b)/.7152;truth=np.stack((r,g,b),-1)
            delta=float(np.max(np.abs(surfaces['YUV'][frame,...,:3].astype(np.float64)-truth)))
            check('YUV-frame-'+str(frame)+'-independent-all-RGB-samples',delta<=3e-8,maximum_absolute_error=delta,compared_channels=int(truth.size))
        warped=[]
        for frame,source in enumerate(surfaces['RGB']):
            t=frame/(N-1);angle=math.radians(-12+24*t);zoom=.82+.18*t;c,s=math.cos(angle)/zoom,math.sin(angle)/zoom
            cx,cy=(W-1)/2,(H-1)/2;tx=8*math.sin(t*math.pi*2);ty=5*math.cos(t*math.pi*2)
            matrix=[[c,s,cx-c*(cx+tx)-s*(cy+ty)],[-s,c,cy+s*(cx+tx)-c*(cy+ty)]]
            value,metadata=resample_rgba(source,(W,H),matrix,tile_pixels=997);warped.append(value)
            row={'frame':frame,'inverse_matrix':matrix,'geometry_metadata':metadata,'output_RGBA_sha256':'sha256:'+hashlib.sha256(value.tobytes()).hexdigest()}
            if frame in (0,9,19):
                reference=scalar_reference(source,matrix);delta=float(np.max(np.abs(value.astype(np.float64)-reference)))
                check('affine-frame-'+str(frame)+'-independent-all-RGBA-samples',delta<=1e-7,maximum_absolute_error=delta,compared_channels=int(value.size))
            record['frames'].append(row);save()
        warped=np.stack(warped);backraw=assets/'background.gbrapf32le';backraw.write_bytes(np.moveaxis(surfaces['YUV'][...,[1,2,0,3]],-1,1).tobytes())
        for label,front in [('original',surfaces['RGB']),('affine',warped)]:
            front_raw=assets/(label+'.gbrapf32le');front_raw.write_bytes(np.moveaxis(front[...,[1,2,0,3]],-1,1).tobytes())
            graph=FloatRasterGraph();target=graph.source_over('0:v','1:v')
            (evidence/(label+'.ffgraph.txt')).write_text(graph.graph(),encoding='utf8')
            command=[ffmpeg,'-v','verbose','-filter_complex_threads','1']
            for path in (backraw,front_raw):command+=['-f','rawvideo','-pixel_format','gbrapf32le','-video_size',f'{W}x{H}','-framerate',FPS,'-i',path]
            raw,stderr=run(label+'-actual-float-source-over',[*command,'-filter_complex',graph.graph(),'-map','['+target+']','-pix_fmt','gbrapf32le','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
            actual=np.moveaxis(np.frombuffer(raw,'<f4').reshape(N,4,H,W)[:,[2,0,1,3]],1,-1)
            expected=front[...,:3].astype(np.float64)*front[...,3:4]+surfaces['YUV'][...,:3].astype(np.float64)*(1-front[...,3:4])
            delta=float(np.max(np.abs(actual[...,:3].astype(np.float64)-expected)))
            check(label+'-all-composited-RGB-match-independent-over',delta<=1.5e-7 and np.all(actual[...,3]==1),maximum_absolute_error=delta,compared_channels=int(expected.size))
            check(label+'-float-graph-no-automatic-conversion','auto-inserting filter' not in stderr)
            rgb=assets/(label+'-composite.gbrpf32le');rgb.write_bytes(np.moveaxis(actual[...,[1,2,0]],-1,1).tobytes())
            master=assets/(label+'-composite-16bit.mkv')
            run(label+'-export-16bit',[ffmpeg,'-v','verbose','-f','rawvideo','-pixel_format','gbrpf32le','-video_size',f'{W}x{H}','-framerate',FPS,'-i',rgb,
                '-vf','zscale=rangein=full:range=full:dither=none,format=gbrp16le','-c:v','ffv1','-level','3',master])
            decoded,_=run(label+'-verify-16bit-master',[ffmpeg,'-v','error','-i',master,'-pix_fmt','gbrp16le','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
            integer=np.frombuffer(decoded,'<u2').reshape(N,3,H,W);truth=np.rint(np.clip(np.moveaxis(actual[...,[1,2,0]],-1,1).astype(np.float64),0,1)*65535).astype(np.int64)
            code_error=int(np.max(np.abs(integer.astype(np.int64)-truth)))
            check(label+'-all-16bit-master-quantization-values',code_error<=1,maximum_code_error=code_error,compared_channels=int(truth.size),explicit_output_clipping='0..1 integer export only')
            mp4=assets/(label+'.mp4');gif=assets/(label+'.gif')
            run(label+'-actual-browser-MP4',[ffmpeg,'-v','error','-i',master,'-vf',
                'zscale=matrixin=gbr:rangein=full:primariesin=bt709:transferin=bt709:matrix=bt709:range=limited:primaries=bt709:transfer=bt709,format=yuv420p',
                '-c:v','libx264','-crf','18','-colorspace','bt709','-color_range','tv','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',mp4])
            probe,_=run(label+'-probe-actual-MP4',[ffprobe,'-v','error','-select_streams','v:0','-show_frames','-show_streams','-show_format','-of','json',mp4])
            p=json.loads(probe);(evidence/(label+'-actual-MP4-probe.json')).write_bytes(probe)
            check(label+'-MP4-every-PTS-frame-duration-and-count',len(p['frames'])==N and all(abs(float(f['best_effort_timestamp_time'])-i/FPS)<1e-6 for i,f in enumerate(p['frames'])) and abs(float(p['format']['duration'])-N/FPS)<1e-6)
            run(label+'-GIF-from-actual-encoded-MP4',[ffmpeg,'-v','error','-i',mp4,'-filter_complex','[0:v]split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',gif])
            with Image.open(gif) as image:
                durations=[]
                for i in range(image.n_frames):image.seek(i);durations.append(image.info.get('duration'))
                check(label+'-actual-GIF-all-frame-durations',image.n_frames==N and durations==[100]*N,frame_durations_ms=durations)
        check('complete-frozen-source-epoch-unchanged',frozen()==before)
        record['status']='passed-native-RGB-YUV-readers-affine-float-media-not-editor-integration'
    except BaseException as exc:record.update(status='failed-preserved',exception=repr(exc));raise
    finally:
        record.update(frozen_after=frozen(),finished_at_utc=datetime.now(timezone.utc).isoformat(),
            assets=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(assets.iterdir()) if p.is_file()])
        save();(evidence/'executed.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':record['status'],'commands':len(record['calls']),'reader_executions':len(record['reader_executions']),
        'checks':len(record['checks']),'assets':len(record['assets']),'frames':N}))
if __name__=='__main__':main()
