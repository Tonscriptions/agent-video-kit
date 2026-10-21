"""Public CLI proof with native 4K frames crossing the default reverse budget."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from PIL import Image,ImageDraw
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
W,H,COUNT,SOURCE_COUNT,RATE=3840,2160,8,9,25

def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()

def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')

def walk(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from walk(child)
    elif isinstance(value,list):
        for child in value:yield from walk(child)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','evidence','assets'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--installed',type=Path)
    args=parser.parse_args();work,evidence,assets=(getattr(args,n).resolve() for n in ('work','evidence','assets'))
    assert work.is_relative_to(ROOT/'product/.runtime') and assets.is_relative_to(ROOT/'docs/assets')
    assert evidence.is_relative_to(ROOT/'docs') and not any(p.exists() for p in (work,evidence,assets))
    for path in (work,evidence,assets):path.mkdir(parents=True)
    (evidence/'executed-smoke.py.txt').write_bytes(Path(__file__).read_bytes())
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_before':frozen(),'calls':[],'checks':[], 'source_frame_hashes':[],
        'native_windows':sys.platform=='win32','virtualization':False,'network':False,
        'long_duration_latency_accepted':False,'peak_process_memory_measured':False,
        'cache_decode_counters_scope':'chunk-preparation-only-excludes-clock-index-probe',
        'repeated_render_still_decodes_native_source_index':True,
        'natural_quality_accepted':False,'HDR_accepted':False,'full_capcut_parity':False,
        'continuous_playback_reviewed':False,'audio_reviewed':False}
    def save():write(evidence/'verification.json',record)
    def check(name,ok,**details):
        record['checks'].append({'name':name,'ok':bool(ok),**details});save();assert ok,name
    env=dict(os.environ);temp=ROOT/'product/.runtime/temp';temp.mkdir(parents=True,exist_ok=True)
    env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
    def run(label,command):
        command=list(map(str,command));started=time.monotonic()
        value=subprocess.run(command,capture_output=True,env=env,cwd=ROOT,timeout=900)
        (evidence/(label+'.stdout.log')).write_bytes(value.stdout)
        (evidence/(label+'.stderr.log')).write_bytes(value.stderr)
        record['calls'].append({'label':label,'command':command,'exit_code':value.returncode,
            'wall_seconds':time.monotonic()-started,'stdout_sha256':'sha256:'+hashlib.sha256(value.stdout).hexdigest()})
        save();assert value.returncode==0,label+': '+value.stderr[-2000:].decode('utf8','replace')+value.stdout[-1000:].decode('utf8','replace')
        return value.stdout
    bootstrap='import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();from ai_ad_editor.cli import main;raise SystemExit(main())'
    prefix=([sys.executable,'-I','-S','-B','-X','utf8',args.installed.resolve()/'run.py'] if args.installed else
        [sys.executable,'-E','-B','-X','utf8','-c',bootstrap,ROOT/'product/src'])
    def cli(label,*argv):return json.loads(run(label,[*prefix,*argv]))
    exe,probe=shutil.which('ffmpeg'),shutil.which('ffprobe');assert exe and probe
    record.update(ffmpeg={'path':exe,'sha256':sha(exe)},ffprobe={'path':probe,'sha256':sha(probe)})
    source=assets/'source-4k.nut';project=work/'project';review=[]
    try:
        command=[exe,'-hide_banner','-nostdin','-v','error','-n','-f','rawvideo','-pixel_format','rgba',
            '-video_size',f'{W}x{H}','-framerate',str(RATE),'-i','pipe:0','-an',
            '-c:v','ffv1','-threads','1','-pix_fmt','bgra',str(source)]
        with (evidence/'source-encode.stderr.log').open('wb') as stderr:
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=stderr,env=env)
            try:
                for index in range(SOURCE_COUNT):
                    image=Image.new('RGBA',(W,H),(28+index*19,46+index*13,214-index*17,255))
                    draw=ImageDraw.Draw(image)
                    draw.rectangle((240+index*280,280,640+index*280,1880),fill=(244,210,44,255))
                    draw.rectangle((300,1600,900+index*200,1920),fill=(35,221,175,255))
                    payload=image.tobytes();record['source_frame_hashes'].append('sha256:'+hashlib.sha256(payload).hexdigest())
                    process.stdin.write(payload);del payload
                    if index<COUNT:review.append(image.resize((384,216),Image.Resampling.LANCZOS).convert('RGB'))
                    image.close()
                process.stdin.close();code=process.wait(timeout=120)
                assert code==0,'source-encode'
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=10)
                if process.stdin and not process.stdin.closed:process.stdin.close()
        record['calls'].append({'label':'source-encode','command':command,'exit_code':code,'streamed_one_frame_at_a_time':True})
        cli('init','project','init',project)
        cli('ingest','media','ingest','--project',project,'--input',source,'--asset-id','source4k',
            '--source-url','local://reverse-chunks/source-4k','--license-spdx','CC0-1.0',
            '--license-url','local://reverse-chunks/CC0-1.0','--verification-status','verified',
            '--permitted-use','commercial_ad','--creator','agent-video-kit',
            '--evidence','Original indexed 4K geometry generated by scripts/smoke_reverse_chunks.py; CC0-1.0')
        p=json.loads((project/'project.json').read_bytes())
        p['settings']['canvas']={'width':W,'height':H}
        p['settings']['timebase']={'ticks_per_second':90000,'display_fps':{'num':RATE,'den':1}}
        write(project/'project.json',p)
        request={'operations':[{'op':'append_clip','id':'reverse4k','asset_id':'source4k',
            'track_id':'track_video_1','timeline_start_tick':0,'duration_tick':28800,
            'source_in_tick':0,'source_out_tick':28800,'reverse':True},
            {'op':'set_sequence_duration','duration_tick':28800,'trim':True}]}
        write(assets/'compose-request.json',request)
        cli('compose','timeline','compose','--project',project,'--input',assets/'compose-request.json')
        cli('validate','validate','--project',project)
        argv=['render','--project',project,'--profile','custom','--width',W,'--height',H]
        planned=cli('plan',*argv,'--output',project/'renders/plan.mp4','--dry-run')['data']['plan']
        planned_jobs=[row['reverse_cache'] for row in walk(planned['inputs']) if 'reverse_cache' in row]
        check('default-budget-uses-four-two-frame-chunks',len(planned_jobs)==1 and
            [part['frames'] for part in planned_jobs[0]['recipe']['ranges']]==[2,2,2,2])
        check('plan-does-not-write-reverse-cache',not (project/'cache/reverse-video').exists())
        first=cli('render',*argv,'--output',project/'renders/reverse4k.mp4')['data']
        manifest=json.loads(Path(first['manifest']).read_bytes());write(evidence/'render-manifest.json',manifest)
        jobs=[row['reverse_cache'] for row in walk(manifest['inputs']) if 'reverse_cache' in row];job=jobs[0]
        cache_path=Path(job['output']);cache_hash=sha(cache_path)
        receipt=json.loads(Path(job['receipt']).read_bytes());write(evidence/'reverse-cache-receipt.json',receipt)
        check('chunk-count-and-native-raster',len(receipt['chunks'])==4 and
            all(x['stream']['width']==W and x['stream']['height']==H for x in receipt['chunks']))
        # Hash each native 4K decoded frame in bounded blocks. The expected
        # hashes were made directly from the independently generated pixels.
        command=[exe,'-v','error','-i',str(cache_path),'-map','0:v:0','-fps_mode','passthrough',
            '-f','rawvideo','-pix_fmt','rgba','pipe:1']
        hashes=[]
        with (evidence/'cache-decode.stderr.log').open('wb') as stderr:
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=stderr,env=env)
            try:
                for index in range(COUNT):
                    digest=hashlib.sha256();remaining=W*H*4
                    while remaining:
                        part=process.stdout.read(min(65536,remaining));assert part,'native frame truncated'
                        digest.update(part);remaining-=len(part)
                    hashes.append('sha256:'+digest.hexdigest())
                assert process.stdout.read(1)==b''
                code=process.wait(timeout=30);assert code==0
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=10)
                process.stdout.close()
        record['calls'].append({'label':'cache-native-decode','command':command,'exit_code':code,'read_block_bytes':65536})
        record['cache_frame_hashes']=hashes
        check('all-eight-selected-4k-RGBA-frames-bit-exact',hashes==record['source_frame_hashes'][:COUNT][::-1])
        second=cli('render-hit',*argv,'--output',project/'renders/second.mp4')['data']
        second_manifest=json.loads(Path(second['manifest']).read_bytes());write(evidence/'render-hit-manifest.json',second_manifest)
        repeated=next(row['reverse_cache'] for row in walk(second_manifest['inputs']) if 'reverse_cache' in row)
        check('second-render-no-new-cache-preparation-decode-or-chunk-encode',repeated['execution']['status']=='cache-hit' and
            repeated['execution']['new_encodings']==0 and repeated['execution']['new_source_decodes']==0 and sha(cache_path)==cache_hash)
        result=cli('preview','preview','range','--project',project,'--start-frame',0,'--end-frame',COUNT,'--height',72)['data']
        again=cli('preview-hit','preview','range','--project',project,'--start-frame',0,'--end-frame',COUNT,'--height',72)['data']
        check('preview-reuses-author-content',again['cache_hit'] and again['cache_key']==result['cache_key'])
        native=run('source-reference',[exe,'-v','error','-i',source,'-an','-vf',
            'format=bgra,scale=128:72:flags=lanczos,format=rgba','-frames:v',str(COUNT),
            '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1'])
        master=run('preview-master-frames',[exe,'-v','error','-i',result['master'],'-map','0:v:0',
            '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1'])
        size=128*72*4;expected=b''.join(native[n*size:(n+1)*size] for n in range(COUNT-1,-1,-1))
        check('lossless-preview-complete-frames-match-independent-forward-source',
            len(native)==len(master)==COUNT*size and expected==master)
        record['preview_reference']={'bytes':len(master),'max_RGBA_error':0,
            'expected_sha256':'sha256:'+hashlib.sha256(expected).hexdigest(),
            'actual_sha256':'sha256:'+hashlib.sha256(master).hexdigest()}
        timeline=json.loads(run('render-PTS',[probe,'-v','error','-select_streams','v:0','-show_frames','-show_streams',
            '-show_entries','frame=pts:stream=time_base,width,height,r_frame_rate','-of','json',first['path']]))
        stream=timeline['streams'][0];pts=[int(frame['pts'])*Fraction(stream['time_base']) for frame in timeline['frames']]
        check('encoded-4k-raster-and-every-frame-PTS',pts==[Fraction(n,RATE) for n in range(COUNT)] and
            stream['width']==W and stream['height']==H)
        for label,path in [('source-review',source),('reverse-review',Path(first['path']))]:
            run(label,[exe,'-v','error','-i',path,'-an','-vf','scale=384:216:flags=lanczos','-c:v','libx264',
                '-preset','ultrafast','-crf','16','-pix_fmt','yuv420p',assets/(label+'.mp4')])
        # Public visual evidence must be decoded from the actual encoded
        # videos, rather than displaying only the expected source oracle.
        actual={}
        for label in ('source-review','reverse-review'):
            pixels=run(label+'-frames',[exe,'-v','error','-i',assets/(label+'.mp4'),'-an',
                '-frames:v',str(COUNT),'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
            size=384*216*3;check(label+'-decoded-frame-count',len(pixels)==COUNT*size)
            actual[label]=[Image.frombytes('RGB',(384,216),pixels[i*size:(i+1)*size]) for i in range(COUNT)]
        errors=[max(abs(a-b) for a,b in zip(image.getpixel((380,10)),
            (28+(COUNT-1-n)*19,46+(COUNT-1-n)*13,214-(COUNT-1-n)*17)))
            for n,image in enumerate(actual['reverse-review'])]
        colors=[(28+n*19,46+n*13,214-n*17) for n in range(COUNT)]
        identities=[min(range(COUNT),key=lambda n:sum(abs(a-b) for a,b in zip(image.getpixel((380,10)),colors[n])))
            for image in actual['reverse-review']]
        check('encoded-render-eight-source-identities',identities==list(range(COUNT-1,-1,-1)),
            source_indices=identities,observed_lossy_background_max_RGB_error=max(errors))
        for label,name in [('source-review','source.gif'),('reverse-review','reverse.gif')]:
            frames=actual[label];frames[0].save(assets/name,save_all=True,append_images=frames[1:],duration=40,loop=0)
        sheet=Image.new('RGB',(384*4,216*2),(0,0,0))
        for n,image in enumerate(actual['reverse-review']):sheet.paste(image,((n%4)*384,(n//4)*216))
        sheet.save(assets/'reverse-order.png')
        inventory=cli('cache-list','cache','list','--project',project)['data']
        check('public-cache-list-matches-built-entry',len(inventory['entries'])==1 and inventory['entries'][0]['key']==job['key'])
        dry=cli('cache-prune-plan','cache','prune','--project',project,'--key',job['key'],'--dry-run')['data']
        check('public-cache-prune-plan-preserves-bytes',dry['removed']==[job['key']] and sha(cache_path)==cache_hash)
        pruned=cli('cache-prune','cache','prune','--project',project,'--key',job['key'])['data']
        check('public-cache-prune-removes-only-selected-entry',pruned['removed']==[job['key']] and not cache_path.exists() and source.is_file())
        rebuilt=cli('preview-after-prune','preview','range','--project',project,'--start-frame',0,'--end-frame',COUNT,'--height',72)['data']
        check('preview-rebuilds-missing-cache-with-identical-native-bytes',not rebuilt['cache_hit'] and cache_path.is_file() and sha(cache_path)==cache_hash)
        write(assets/'rights.json',{'license':'CC0-1.0','creator':'agent-video-kit','generator':'scripts/smoke_reverse_chunks.py',
            'source':source.name,'description':'Original 4K indexed geometry; synthesized without external assets.'})
        record['media']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(assets.iterdir()) if p.is_file()}
        record['frozen_after']=frozen();check('frozen-inputs-unchanged',record['frozen_before']==record['frozen_after'])
        record.update(status='succeeded',cli_calls=sum(c['label'] not in {'source-encode','cache-native-decode',
            'source-review','reverse-review','source-review-frames','reverse-review-frames',
            'source-reference','preview-master-frames','render-PTS'} for c in record['calls']),
            finished_at_utc=datetime.now(timezone.utc).isoformat());save()
        print(json.dumps({'status':record['status'],'checks':len(record['checks']),'calls':len(record['calls']),
            'frames':COUNT,'native_raster':[W,H],'source_seconds':COUNT/RATE,'frozen_inputs':len(record['frozen_before'])}))
    except BaseException as error:
        record.update(status='failed',error=repr(error),finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen());save();raise

if __name__=='__main__':main()
