"""Actual subprocess surface CLI -> linear-light independent compositing media.

The export is the public CLI. Compositing and movie encoding are a separate
explicit core pipeline, not ordinary timeline render or preview integration.
"""
from datetime import datetime, timezone
from fractions import Fraction
import argparse, hashlib, json, math, os
from pathlib import Path
import shutil, subprocess, sys, time
import numpy as np
from PIL import Image
from run_frozen_regression import frozen, sha
from smoke_float_geometry import scalar_reference

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'
ASSETS=ROOT/'docs/assets/color-precision-20261021-lab'
W,H,N,FPS=160,96,20,10

def inverse709(value):
    value=np.asarray(value,dtype=np.float64);v=np.abs(value)
    return np.where(v<.081,value/4.5,np.sign(value)*((v+.099)/1.099)**(1/.45))

def forward709(value):
    value=np.asarray(value,dtype=np.float64);v=np.abs(value)
    return np.where(v<.018,value*4.5,np.sign(value)*(1.099*v**.45-.099))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--installed',type=Path)
    parser.add_argument('--reference',type=Path)
    args=parser.parse_args()
    evidence=REL/('surface-cli-media-'+args.revision)
    assets=ASSETS/('surface-cli-media-'+args.revision)
    work=ROOT/'product/.runtime/color-precision-20261021'/('surface-cli-media-'+args.revision)
    assert not any(p.exists() for p in (evidence,assets,work))
    for p in (evidence,assets,work):p.mkdir(parents=True)
    before=frozen();assert len(before)==282
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_before':before,'generator_sha256':sha(Path(__file__)),
        'independent_affine_reference_script_sha256':sha(Path(__file__).with_name('smoke_float_geometry.py')),
        'calls':[],'checks':[],'bundles':{},'movie_outputs':{},'native_windows':True,
        'virtualization':False,'network':False,'CLI_surface_export_used':True,
        'ordinary_timeline_render_integrated':False,'movie_encoder_part_of_surface_CLI':False,
        'working_colour':'explicit relative D65 BT.709 primaries / linear-light RGB',
        'output_colour':'published rounded BT.709 camera OETF; not BT.1886 or HDR',
        'natural_quality_accepted':False,'HDR_accepted':False,'full_capcut_parity':False,
        'continuous_playback_reviewed':False,'audio_present':False,
        'rights':'Original procedural RGB/alpha16 and YCbCr16 sources; CC0-1.0, original source script retained.'}
    def save():
        (evidence/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save();assert ok,name
    env=dict(os.environ,TEMP=str(ROOT/'product/.runtime/temp'),TMP=str(ROOT/'product/.runtime/temp'),TMPDIR=str(ROOT/'product/.runtime/temp'))
    def run(name,command,kind='native',binary=False):
        command=list(map(str,command));start=time.monotonic()
        p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        (evidence/(name+'.stderr.log')).write_bytes(p.stderr)
        if not binary:(evidence/(name+'.stdout.log')).write_bytes(p.stdout)
        record['calls'].append({'name':name,'kind':kind,'command':command,'exit_code':p.returncode,
            'wall_seconds':time.monotonic()-start,'stdout_bytes':len(p.stdout),
            'stdout_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),
            'stderr_sha256':'sha256:'+hashlib.sha256(p.stderr).hexdigest()});save()
        assert p.returncode==0,(name,p.stdout[-800:].decode('utf8','replace'),p.stderr[-1800:].decode('utf8','replace'))
        return p.stdout
    installed=args.installed.resolve(strict=True) if args.installed else None
    site=installed/'site' if installed else ROOT/'product/src'
    if installed:prefix=[sys.executable,'-I','-S','-B','-X','utf8',installed/'run.py']
    else:
        bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())'
        prefix=[sys.executable,'-E','-B','-X','utf8','-c',bootstrap,site]
    def cli(name,*arguments):
        value=json.loads(run(name,[*prefix,*arguments],kind='actual-subprocess-CLI'))
        assert value['status'] in ('succeeded','planned'),value
        return value
    record.update(installed=bool(installed),product_site=str(site))
    try:
        old_evidence=REL/'native-source-media-r1/verification.json'
        old=json.loads(old_evidence.read_bytes());assert old['status'].startswith('passed-native-RGB-YUV')
        originals=ASSETS/'native-source-media-r1'
        names=('foreground-16bit.mkv','background-16bit.mkv','foreground.gbrap16le','background.yuv444p16le')
        original_rows={r['path']:r['sha256'] for r in old['assets']}
        inputs={p.relative_to(ROOT).as_posix():sha(p) for p in (originals/name for name in names)}
        check('reused-actual-original-source-bytes-match-previous-executed-receipt',all(original_rows[k]==v for k,v in inputs.items()))
        record.update(source_inputs=inputs,original_source_receipt_sha256=sha(old_evidence))
        ffmpeg,ffprobe=shutil.which('ffmpeg'),shutil.which('ffprobe');assert ffmpeg and ffprobe
        record.update(ffmpeg={'path':ffmpeg,'sha256':sha(Path(ffmpeg))},ffprobe={'path':ffprobe,'sha256':sha(Path(ffprobe))})
        project=work/'project';cli('init','project','init',project)
        for asset_id,name in [('foreground','foreground-16bit.mkv'),('background','background-16bit.mkv')]:
            cli('ingest-'+asset_id,'media','ingest','--project',project,'--input',originals/name,'--asset-id',asset_id,
                '--license-spdx','CC0-1.0','--creator','agent-video-kit procedural source generator',
                '--verification-status','verified','--permitted-use','commercial_ad',
                '--evidence','Original deterministic source script and full native code checks in native-source-media-r1/verification.json')
        authored={name:sha(project/name) for name in ('project.json','rights-ledger.json')}
        angle=math.radians(11);zoom=.86;c,s=math.cos(angle)/zoom,math.sin(angle)/zoom
        cx,cy=(W-1)/2,(H-1)/2;matrix=[[c,s,cx-c*(cx+5)-s*(cy-3)],[-s,c,cy+s*(cx+5)-c*(cy-3)]]
        transform=project/'inverse-affine.json';transform.write_text(json.dumps({'width':W,'height':H,'inverse':matrix}),encoding='utf8')
        base=['surface','export','--project',project,'--source-primaries','bt709','--source-transfer','bt709-oetf',
              '--working-primaries','bt709','--working-transfer','linear']
        plans={
            'foreground':['--asset-id','foreground'],
            'affine':['--asset-id','foreground','--transform-json',transform],
            'background':['--asset-id','background','--pixel-family','yuv','--yuv-matrix','bt709','--yuv-range','full',
                          '--chroma-location','center','--scan','progressive'],
            'selected':['--asset-id','foreground','--start-frame',3,'--stop-frame',8]}
        arrays={}
        for name,extra in plans.items():
            output=project/'renders'/('float-'+name)
            cli('plan-'+name,*base,*extra,'--output',output,'--dry-run')
            check(name+'-dry-run-no-output',not output.exists())
            result=cli('export-'+name,*base,*extra,'--output',output)
            inspection=cli('inspect-'+name,'surface','inspect','--project',project,'--input',output)
            m=json.loads((output/'bundle.json').read_bytes());count=m['frames']
            arrays[name]=np.fromfile(output/'frames.rgba-f32le','<f4').reshape(count,H,W,4)
            clock=np.fromfile(output/'clock.i64le','<i8').reshape(count,3)
            indices=range(3,8) if name=='selected' else range(N);tb=Fraction(m['native_time_base'])
            check(name+'-original-source-index-PTS-duration-exact',clock[:,0].tolist()==list(indices)
                and all(int(p)*tb==Fraction(i,FPS) and int(d)*tb==Fraction(1,FPS) for (i,p,d) in clock))
            check(name+'-reader-exit-and-derived-inspection',m['source_reader_process']['exit_code']==0
                and m['source_reader_process']['owned_threads_terminated'] and inspection['data']['derived_bytes_verified']
                and not inspection['data']['original_inputs_revalidated'])
            copy=assets/'bundles'/name;copy.parent.mkdir(exist_ok=True);shutil.copytree(output,copy)
            check(name+'-published-bundle-copy-byte-identical',all(sha(p)==sha(copy/p.name) for p in output.iterdir()))
            record['bundles'][name]={'frames':count,'pixel_sha256':sha(copy/'frames.rgba-f32le'),
                'clock_sha256':sha(copy/'clock.i64le'),'manifest_sha256':sha(copy/'bundle.json'),
                'path':copy.relative_to(ROOT).as_posix(),'all_source_frames_exported':m['all_source_frames_exported'],
                'source_reader_process':m['source_reader_process'],'CLI_result':result['data']}
        check('all-exports-preserve-project-and-rights-ledger',all(sha(project/name)==digest for name,digest in authored.items()))
        rgb=np.fromfile(originals/'foreground.gbrap16le','<u2').reshape(N,4,H,W)
        rgb=np.moveaxis(rgb[:,[2,0,1,3]],1,-1).astype(np.float32)/np.float32(65535)
        expected=rgb.copy();expected[...,:3]=inverse709(rgb[...,:3]).astype(np.float32)
        check('RGB-all-linearized-channels-independent-published-transfer',np.array_equal(arrays['foreground'],expected),compared_channels=int(expected.size))
        check('selected-source-window-is-exact-full-export-subset',np.array_equal(arrays['selected'],arrays['foreground'][3:8]))
        yuv=np.fromfile(originals/'background.yuv444p16le','<u2').reshape(N,3,H,W).astype(np.float64)
        y=yuv[:,0]/65535;cb=(yuv[:,1]-32768)/65535;cr=(yuv[:,2]-32768)/65535
        r=y+1.5748*cr;b=y+1.8556*cb;g=(y-.2126*r-.0722*b)/.7152
        yuv_rgb=np.stack((r,g,b),-1).astype(np.float32)
        truth=inverse709(yuv_rgb).astype(np.float32)
        delta=float(np.max(np.abs(arrays['background'][...,:3].astype(np.float64)-truth)))
        check('YUV-all-linearized-RGB-independent-range-matrix-transfer',delta<=6e-8 and np.all(arrays['background'][...,3]==1),maximum_absolute_error=delta,compared_channels=int(truth.size))
        for frame in (0,9,19):
            truth=scalar_reference(expected[frame],matrix)
            delta=float(np.max(np.abs(arrays['affine'][frame].astype(np.float64)-truth)))
            check('affine-'+str(frame)+'-all-linear-premultiplied-RGBA-independent-reference',delta<=1e-7,maximum_absolute_error=delta,compared_channels=int(truth.size))
        graph_script=('import sys,json,pathlib;sys.path.insert(0,sys.argv[1]);'
            'from ai_ad_editor.float_raster import FloatRasterGraph;'
            'g=FloatRasterGraph();o=g.source_over("0:v","1:v");'
            'print(json.dumps({"graph":g.graph(),"label":o,"origin":str(pathlib.Path(sys.modules[FloatRasterGraph.__module__].__file__).resolve())}))')
        graph=json.loads(run('build-actual-core-graph',[sys.executable,'-I','-S','-B','-X','utf8','-c',graph_script,site],kind='core-process'))
        check('graph-module-origin-is-requested-product-site',Path(graph['origin']).is_relative_to(site.resolve()))
        (evidence/'linear-source-over.ffgraph.txt').write_text(graph['graph'],encoding='utf8')
        for label,front in [('original',arrays['foreground']),('affine',arrays['affine'])]:
            command=[ffmpeg,'-v','error','-filter_complex_threads','1']
            for side,surface in [('background',arrays['background']),('foreground',front)]:
                raw=work/(label+'-'+side+'.gbrapf32le')
                raw.write_bytes(np.moveaxis(surface[...,[1,2,0,3]],-1,1).astype('<f4').tobytes())
                command+=['-f','rawvideo','-pixel_format','gbrapf32le','-video_size',f'{W}x{H}','-framerate',FPS,'-i',raw]
            data=run(label+'-linear-float-over',[*command,'-filter_complex',graph['graph'],'-map','['+graph['label']+']',
                '-pix_fmt','gbrapf32le','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
            actual=np.moveaxis(np.frombuffer(data,'<f4').reshape(N,4,H,W)[:,[2,0,1,3]],1,-1)
            truth=front[...,:3].astype(np.float64)*front[...,3:4]+arrays['background'][...,:3].astype(np.float64)*(1-front[...,3:4])
            delta=float(np.max(np.abs(actual[...,:3].astype(np.float64)-truth)))
            check(label+'-all-linear-light-over-RGB-independent-formula',delta<=1.5e-7 and np.all(actual[...,3]==1),maximum_absolute_error=delta,compared_channels=int(truth.size))
            # Output encoding is explicitly separate from the surface command.
            encoded=forward709(actual[...,:3]).astype(np.float32)
            raw=work/(label+'-output-transfer.gbrpf32le');raw.write_bytes(np.moveaxis(encoded[...,[1,2,0]],-1,1).astype('<f4').tobytes())
            master=assets/(label+'-linear-composite-16bit.mkv')
            run(label+'-16bit-master',[ffmpeg,'-v','error','-f','rawvideo','-pixel_format','gbrpf32le','-video_size',f'{W}x{H}','-framerate',FPS,'-i',raw,
                '-vf','zscale=rangein=full:range=full:dither=none,format=gbrp16le','-c:v','ffv1','-level','3',master])
            decoded=run(label+'-master-all-code-check',[ffmpeg,'-v','error','-i',master,'-pix_fmt','gbrp16le','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
            codes=np.frombuffer(decoded,'<u2').reshape(N,3,H,W).astype(np.int64)
            truth=np.rint(np.clip(np.moveaxis(encoded[...,[1,2,0]],-1,1).astype(np.float64),0,1)*65535).astype(np.int64)
            code_error=int(np.max(np.abs(codes-truth)))
            check(label+'-all-master-codes-match-explicit-integer-boundary',code_error<=1,maximum_code_error=code_error,compared_channels=int(truth.size))
            movie=assets/(label+'.mp4');gif=assets/(label+'.gif')
            run(label+'-MP4',[ffmpeg,'-v','error','-i',master,'-vf',
                'zscale=matrixin=gbr:rangein=full:primariesin=bt709:transferin=bt709:matrix=bt709:range=limited:primaries=bt709:transfer=bt709,format=yuv420p',
                '-c:v','libx264','-crf','18','-colorspace','bt709','-color_range','tv','-color_primaries','bt709','-color_trc','bt709','-movflags','+faststart',movie])
            probe=run(label+'-probe',[ffprobe,'-v','error','-select_streams','v:0','-show_frames','-show_streams','-show_format','-of','json',movie])
            p=json.loads(probe);(evidence/(label+'.probe.json')).write_bytes(probe)
            check(label+'-encoded-count-every-PTS-and-duration',len(p['frames'])==N
                and all(Fraction(f['best_effort_timestamp_time'])==Fraction(i,FPS) for i,f in enumerate(p['frames']))
                and Fraction(p['format']['duration'])==Fraction(N,FPS))
            run(label+'-GIF',[ffmpeg,'-v','error','-i',movie,'-filter_complex','[0:v]split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',gif])
            with Image.open(gif) as image:
                durations=[]
                for i in range(image.n_frames):image.seek(i);durations.append(image.info.get('duration'))
                check(label+'-GIF-from-actual-encoded-MP4-all-durations',image.n_frames==N and durations==[100]*N)
            record['movie_outputs'][label]={'frames':N,'fps':FPS,'duration_seconds':N/FPS,'float_linear_RGBA_sha256':'sha256:'+hashlib.sha256(actual.tobytes()).hexdigest(),
                'master_16bit_sha256':sha(master),'movie_sha256':sha(movie),'gif_sha256':sha(gif)}
        if args.reference:
            reference=json.loads(args.reference.resolve(strict=True).read_bytes())
            fields=('pixel_sha256','clock_sha256','frames')
            check('fresh-installed-four-bundle-payloads-and-clocks-equal-development',all(
                {k:record['bundles'][name][k] for k in fields}=={k:reference['bundles'][name][k] for k in fields} for name in plans))
            check('fresh-installed-linear-composite-RGBA-equals-development',all(record['movie_outputs'][name]['float_linear_RGBA_sha256']==reference['movie_outputs'][name]['float_linear_RGBA_sha256'] for name in ('original','affine')))
            record['development_reference_sha256']=sha(args.reference.resolve(strict=True))
        check('original-inputs-runtime-and-product-epoch-unchanged',all(sha(ROOT/k)==v for k,v in inputs.items())
            and sha(Path(ffmpeg))==record['ffmpeg']['sha256'] and sha(Path(ffprobe))==record['ffprobe']['sha256'] and frozen()==before)
        record['status']='passed-subprocess-surface-CLI-linear-core-media-not-timeline-integration'
    except BaseException as error:
        record.update(status='failed-preserved',error=repr(error));raise
    finally:
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen(),
            assets=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(assets.rglob('*')) if p.is_file()])
        record['CLI_calls']=sum(r['kind']=='actual-subprocess-CLI' for r in record['calls'])
        record['native_script_calls']=sum(r['kind']=='native' for r in record['calls'])
        save();(evidence/'executed.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({k:record[k] for k in ('status','CLI_calls','native_script_calls')}))

if __name__=='__main__':main()
